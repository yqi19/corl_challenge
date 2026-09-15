"""Self-check a TOWER challenge policy server exactly as the evaluator calls it.

    pip install -r requirements.txt
    python tools/check_policy.py wss://your-host:8000 --api-key-env TOWER_API_KEY \
        --output check_report.json

Attach the generated ``check_report.json`` to your submission.
"""

from __future__ import annotations

import argparse
import functools
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from typing import Any

import msgpack
import numpy as np
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

PROTOCOL = "tower-openpi-v1"
CAMERAS = ("left_back_camera", "right_front_camera", "left_wrist_camera", "back_wrist_camera")
ACTION_DIM = 18
MIN_HORIZON = 16


def _pack_array(obj: Any) -> Any:
    if isinstance(obj, np.ndarray):
        return {b"__ndarray__": True, b"data": obj.tobytes(), b"dtype": obj.dtype.str,
                b"shape": obj.shape}
    if isinstance(obj, np.generic):
        return {b"__npgeneric__": True, b"data": obj.item(), b"dtype": obj.dtype.str}
    return obj


def _unpack_array(obj: dict[Any, Any]) -> Any:
    if b"__ndarray__" in obj:
        dtype = np.dtype(obj[b"dtype"])
        if dtype.kind in ("V", "O", "c"):
            raise ValueError(f"unsupported dtype {dtype}")
        return np.ndarray(buffer=obj[b"data"], dtype=dtype, shape=obj[b"shape"])
    if b"__npgeneric__" in obj:
        return np.dtype(obj[b"dtype"]).type(obj[b"data"])
    return obj


packb = functools.partial(msgpack.packb, default=_pack_array)
unpackb = functools.partial(msgpack.unpackb, object_hook=_unpack_array)


class CheckFailed(RuntimeError):
    pass


def _receive(socket: Any, timeout_s: float) -> Any:
    try:
        frame = socket.recv(timeout=timeout_s)
    except TimeoutError as exc:
        raise CheckFailed(f"no reply within {timeout_s:g} s") from exc
    except ConnectionClosed as exc:
        raise CheckFailed(f"server closed the connection: {exc}") from exc
    if isinstance(frame, str):
        raise CheckFailed("server returned an error:\n" + frame[-4000:])
    try:
        return unpackb(frame)
    except Exception as exc:
        raise CheckFailed(f"reply is not valid msgpack-numpy: {exc}") from exc


def _validate(reply: Any) -> np.ndarray:
    if not isinstance(reply, dict) or "actions" not in reply:
        raise CheckFailed("reply must be a map with an 'actions' entry")
    try:
        actions = np.asarray(reply["actions"], dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise CheckFailed(f"actions are not numeric: {exc}") from exc
    if actions.ndim != 2 or actions.shape[1] != ACTION_DIM:
        raise CheckFailed(f"actions must have shape [H, {ACTION_DIM}], got {list(actions.shape)}")
    if actions.shape[0] < MIN_HORIZON:
        raise CheckFailed(f"action horizon {actions.shape[0]} is below {MIN_HORIZON}")
    if not np.isfinite(actions).all():
        raise CheckFailed("actions contain NaN or infinity")
    return actions


def check(url: str, *, api_key: str | None, episodes: int, requests: int, height: int,
          width: int, prompt: str, timeout_s: float) -> dict[str, Any]:
    if not url.startswith(("ws://", "wss://")):
        raise CheckFailed("URL must start with ws:// or wss://")
    headers = {"Authorization": f"Api-Key {api_key}"} if api_key else None
    rng = np.random.default_rng(0)
    latencies: list[float] = []
    metadata: Any = None
    shape: list[int] = []
    for episode in range(episodes):  # the evaluator opens one connection per episode
        try:
            socket = connect(url, open_timeout=timeout_s, compression=None, max_size=64_000_000,
                             additional_headers=headers)
        except Exception as exc:
            raise CheckFailed(f"cannot connect to {url}: {exc}") from exc
        with socket:
            metadata = _receive(socket, timeout_s)
            if not isinstance(metadata, dict):
                raise CheckFailed("the first message must be a metadata map")
            if metadata.get("action_dim", ACTION_DIM) != ACTION_DIM:
                raise CheckFailed(f"metadata declares action_dim={metadata['action_dim']}")
            for _ in range(requests):
                obs = {
                    "images": {name: rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
                               for name in CAMERAS},
                    "state": rng.uniform(-0.5, 0.5, ACTION_DIM).astype(np.float32),
                    "prompt": prompt,
                }
                started = time.perf_counter()
                socket.send(packb(obs))
                shape = list(_validate(_receive(socket, timeout_s)).shape)
                latencies.append((time.perf_counter() - started) * 1000)
        print(f"episode {episode}: {requests} requests OK", file=sys.stderr)
    return {
        "status": "ok",
        "protocol": PROTOCOL,
        "url": url,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "server_metadata": metadata,
        "episodes": episodes,
        "requests_per_episode": requests,
        "image_shape": [height, width, 3],
        "action_shape": shape,
        "latency_ms": {
            "mean": round(float(np.mean(latencies)), 2),
            "p95": round(float(np.percentile(latencies, 95)), 2),
            "max": round(float(np.max(latencies)), 2),
        },
        "client": {"python": platform.python_version(), "platform": platform.platform()},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Self-check a TOWER challenge policy server")
    parser.add_argument("url", help="ws:// or wss:// endpoint of your policy server")
    parser.add_argument("--api-key-env", default="TOWER_API_KEY",
                        help="environment variable holding your API key (unset = no key)")
    parser.add_argument("--episodes", type=int, default=2)
    parser.add_argument("--requests", type=int, default=5, help="requests per episode")
    parser.add_argument("--height", type=int, default=480)
    parser.add_argument("--width", type=int, default=640)
    parser.add_argument("--prompt", default="transfer the tower")
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--output", help="write the JSON report to this file")
    args = parser.parse_args()
    try:
        report = check(args.url, api_key=os.environ.get(args.api_key_env) or None,
                       episodes=args.episodes, requests=args.requests, height=args.height,
                       width=args.width, prompt=args.prompt, timeout_s=args.timeout_s)
    except CheckFailed as exc:
        print(f"CHECK FAILED: {exc}", file=sys.stderr)
        return 1
    text = json.dumps(report, indent=2, default=str)
    if args.output:
        with open(args.output, "w") as stream:
            stream.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
