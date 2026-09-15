"""TOWER challenge policy server template (``tower-openpi-v1``).

Edit ``Policy`` and keep the transport. The wire format is the openpi
``WebsocketPolicyServer`` protocol, so an existing openpi ``serve_policy.py`` works too.

    pip install numpy "msgpack>=1,<2" "websockets>=15,<16"
    TOWER_API_KEY=... python serve_policy.py --port 8000

Protocol:
  * on connect the server sends a msgpack metadata dict;
  * each request is an observation dict, each reply is ``{"actions": float [H, 18]}``;
  * a text frame instead of bytes reports an error (the evaluator records it and stops);
  * the evaluator opens one connection per episode, so per-connection state is episode state.
"""

from __future__ import annotations

import argparse
import functools
import hmac
import http
import logging
import os
import threading
import traceback
from typing import Any

import msgpack
import numpy as np
from websockets.exceptions import ConnectionClosed
from websockets.sync.server import serve

CAMERAS = ("left_back_camera", "right_front_camera", "left_wrist_camera", "back_wrist_camera")
ACTION_DIM = 18  # left J1-J7, left gripper, back J1-J7, back gripper, left/back lifter (mm)
ACTION_HORIZON = 16  # the evaluator executes the first 16 rows at 10 Hz, then asks again


class Policy:
    """Replace with your model. Load weights once in ``__init__``."""

    def __init__(self, checkpoint: str | None) -> None:
        self.checkpoint = checkpoint

    def infer(self, obs: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
        """Map one observation to an action chunk.

        obs["images"][camera]: uint8 [H, W, 3] for each name in ``CAMERAS``
        obs["state"]:          float32 [18], same layout as the action
        obs["prompt"]:         task instruction
        session:               empty dict per connection (= per episode) for recurrent state
        """
        state = np.asarray(obs["state"], dtype=np.float32)
        return {"actions": np.tile(state, (ACTION_HORIZON, 1))}  # hold the current pose


def _pack_array(obj: Any) -> Any:
    if isinstance(obj, np.ndarray):
        return {b"__ndarray__": True, b"data": obj.tobytes(), b"dtype": obj.dtype.str,
                b"shape": obj.shape}
    if isinstance(obj, np.generic):
        return {b"__npgeneric__": True, b"data": obj.item(), b"dtype": obj.dtype.str}
    return obj


def _unpack_array(obj: dict[Any, Any]) -> Any:
    if b"__ndarray__" in obj:
        return np.ndarray(buffer=obj[b"data"], dtype=np.dtype(obj[b"dtype"]), shape=obj[b"shape"])
    if b"__npgeneric__" in obj:
        return np.dtype(obj[b"dtype"]).type(obj[b"data"])
    return obj


packb = functools.partial(msgpack.packb, default=_pack_array)
unpackb = functools.partial(msgpack.unpackb, object_hook=_unpack_array)


def make_server(policy: Policy, host: str, port: int, *, api_key: str | None = None,
                metadata: dict[str, Any] | None = None, max_message_bytes: int = 64_000_000):
    """Create the server; call ``serve_forever()`` on the result (``shutdown()`` stops it)."""
    metadata = {"protocol": "tower-openpi-v1", "action_dim": ACTION_DIM,
                "action_horizon": ACTION_HORIZON, **(metadata or {})}
    gpu = threading.Lock()  # concurrent episodes share one model; serialize inference

    def process_request(connection, request):
        if request.path == "/healthz":
            return connection.respond(http.HTTPStatus.OK, "OK\n")
        if api_key is not None:
            supplied = request.headers.get("Authorization", "")
            if not hmac.compare_digest(supplied, f"Api-Key {api_key}"):
                return connection.respond(http.HTTPStatus.UNAUTHORIZED, "invalid api key\n")
        return None

    def handler(connection) -> None:
        session: dict[str, Any] = {}
        connection.send(packb(metadata))
        while True:
            try:
                obs = unpackb(connection.recv())
                with gpu:
                    reply = policy.infer(obs, session)
                connection.send(packb(reply))
            except ConnectionClosed:
                return
            except Exception:
                logging.exception("inference failed")
                connection.send(traceback.format_exc())
                connection.close()
                return

    return serve(handler, host, port, process_request=process_request, compression=None,
                 max_size=max_message_bytes)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--checkpoint", default=None)
    parser.add_argument("--api-key-env", default="TOWER_API_KEY",
                        help="environment variable holding the key the evaluator must send")
    args = parser.parse_args()
    api_key = os.environ.get(args.api_key_env) or None
    if api_key is None:
        logging.warning("%s is unset; the server accepts unauthenticated connections",
                        args.api_key_env)
    with make_server(Policy(args.checkpoint), args.host, args.port, api_key=api_key) as server:
        logging.info("serving tower-openpi-v1 on ws://%s:%d", args.host, args.port)
        server.serve_forever()


if __name__ == "__main__":
    main()
