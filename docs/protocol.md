# Policy server protocol (`tower-openpi-v1`)

You host your policy behind a WebSocket endpoint. The TOWER evaluator connects to it,
runs the simulation on the organizers' GPUs, and sends observations; your server replies
with action chunks. You never need Isaac Sim or the benchmark scenes.

The protocol is the [openpi](https://github.com/Physical-Intelligence/openpi)
`WebsocketPolicyServer` wire format. If you already serve a policy with openpi
(for example pi-0.5), only the observation/action mapping below is new.

## Message flow

```text
evaluator                                   your server
    |  WebSocket handshake                       |
    |  Authorization: Api-Key <key>  -------->   |
    |  <--------  metadata (msgpack map)         |
    |                                            |
    |  observation (msgpack-numpy)  -------->    |   repeated every
    |  <--------  {"actions": [H, 18]}           |   16 executed actions
    |                    ...                     |
    |  close  -------->                          |   end of episode
```

| Rule | Detail |
|---|---|
| One connection per episode | Anything stored per connection is episode state; reset it on a new connection. |
| Metadata | First message after connect, e.g. `{"protocol": "tower-openpi-v1", "action_dim": 18, "action_horizon": 16}`. |
| Encoding | msgpack with openpi's NumPy extension (`__ndarray__`, `data`, `dtype`, `shape`). Pickle is never used. |
| Errors | Send a **text** frame with the traceback and close. The episode is recorded as a policy error. |
| Health | `GET /healthz` on the same port returns `200 OK`. |
| Timeout | No reply within 60 s ends the episode. The simulation is paused during inference, so latency does not change scores. |
| Message size | At most 64 MB per message. |
| Concurrency | The evaluator may run several episodes at once, each on its own connection. |

## Observation

```python
{
    "images": {
        "left_back_camera":   uint8 [H, W, 3],   # third-person
        "right_front_camera": uint8 [H, W, 3],   # third-person
        "left_wrist_camera":  uint8 [H, W, 3],   # left-arm wrist
        "back_wrist_camera":  uint8 [H, W, 3],   # back-arm wrist
    },
    "state":  float32 [18],   # measured state in the action layout below
    "prompt": str,            # task instruction
}
```

Camera names match TOWER-SimData `observations/images/*`. Images arrive RGB at the
simulator's native resolution; resize inside your server.

## Action

Reply with `{"actions": float [H, 18]}`, `H >= 16`: absolute commands at 10 Hz in the
TOWER-SimData layout `concat(leader/qpos, lifter/action_mm)`:

| Index | Meaning | Unit |
|---|---|---|
| 0–6 | left arm J1–J7 | rad |
| 7 | left gripper opening | absolute command |
| 8–14 | back arm J1–J7 | rad |
| 15 | back gripper opening | absolute command |
| 16 | left lifter | mm |
| 17 | back lifter | mm |

The evaluator executes the first 16 rows and then sends a new observation; extra rows are
ignored. Lifters are stationary in the benchmark scenes: lifter commands are recorded but
not executed. Non-finite values or a wrong shape end the episode as a policy error.

## Reference implementations

- Server template: [`policy_server/serve_policy.py`](../policy_server/serve_policy.py)
- Evaluator-equivalent checker: [`tools/check_policy.py`](../tools/check_policy.py)
- Python client with openpi installed:

```python
from openpi_client import websocket_client_policy

client = websocket_client_policy.WebsocketClientPolicy("wss://your-host", 8000, api_key="...")
actions = client.infer(observation)["actions"]
```

## Security

- Always set an API key (`TOWER_API_KEY`); the template rejects other connections with 401.
- Prefer `wss://` (TLS) through a reverse proxy such as Caddy or nginx, or a tunnel.
- Use a dedicated key for the challenge and rotate it after evaluation.
- The server only needs to accept inbound WebSocket connections on one port.
