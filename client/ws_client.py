import argparse
import asyncio
import json
import secrets
from typing import Optional

import websockets


async def run(ws_url: str):
    # Always generate a fresh token
    tok = secrets.token_urlsafe(16)
    print(f"Using token: {tok}")
    print("Connect REST callers with Authorization: Bearer <token>\n")

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
                side = data.get("side", "both")
                print(f"Received whip command: {duration}s, side={side}.")
            else:
                print(f"Received message: {data}")


def main():
    parser = argparse.ArgumentParser(description="WebSocket client for Whip API")
    parser.add_argument("--ws-url", default="ws://whip.martinevsky.ru:60606/ws", help="WebSocket URL")
    args = parser.parse_args()

    asyncio.run(run(args.ws_url))


if __name__ == "__main__":
    main()
