import argparse
import asyncio
import json
import secrets
from typing import Optional

import websockets


async def run(ws_url: str, token: Optional[str], use_subprotocol: bool):
    # Generate a token if not provided
    tok = token or secrets.token_urlsafe(16)
    print(f"Using token: {tok}")
    print("Connect REST callers with Authorization: Bearer <token>\n")

    if use_subprotocol:
        # Send token as Sec-WebSocket-Protocol
        async with websockets.connect(ws_url, subprotocols=[tok]) as ws:
            print(f"Connected to {ws_url}. Waiting for commands...\n")
            while True:
                raw = await ws.recv()
                try:
                    data = json.loads(raw)
                except Exception:
                    print(f"Received non-JSON message: {raw}")
                    continue
                cmd = data.get("command")
                if cmd == "whip":
                    duration = data.get("duration")
                    print(f"Received whip command for {duration} seconds.")
                else:
                    print(f"Received message: {data}")
    else:
        # Send token in Authorization header
        async with websockets.connect(ws_url, extra_headers={"Authorization": f"Bearer {tok}"}) as ws:
            print(f"Connected to {ws_url}. Waiting for commands...\n")
            while True:
                raw = await ws.recv()
                try:
                    data = json.loads(raw)
                except Exception:
                    print(f"Received non-JSON message: {raw}")
                    continue
                cmd = data.get("command")
                if cmd == "whip":
                    duration = data.get("duration")
                    print(f"Received whip command for {duration} seconds.")
                else:
                    print(f"Received message: {data}")


def main():
    parser = argparse.ArgumentParser(description="WebSocket client for Whip API")
    parser.add_argument("--ws-url", default="ws://whip.martinevsky.ru:60606/ws", help="WebSocket URL")
    parser.add_argument("--token", default=None, help="Optional pre-chosen token (Bearer secret)")
    parser.add_argument("--use-subprotocol", action="store_true", help="Send token in Sec-WebSocket-Protocol instead of Authorization header")
    args = parser.parse_args()

    asyncio.run(run(args.ws_url, args.token, args.use_subprotocol))


if __name__ == "__main__":
    main()
