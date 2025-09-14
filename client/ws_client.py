import argparse
import asyncio
import json
import secrets
import time

import websockets

try:
    import RPi.GPIO as GPIO  # type: ignore
    HAS_GPIO = True
except Exception:  # pragma: no cover - running off Pi
    HAS_GPIO = False


class Relay:
    def __init__(self, pin: int, active_low: bool = True):
        self.pin = pin
        self.active_low = active_low
        self.state = False
        if HAS_GPIO:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            initial = GPIO.HIGH if active_low else GPIO.LOW
            GPIO.setup(self.pin, GPIO.OUT, initial=initial)

    def on(self):
        self.state = True
        if HAS_GPIO:
            GPIO.output(self.pin, GPIO.LOW if self.active_low else GPIO.HIGH)
        else:
            print(f"[GPIO MOCK] Pin {self.pin} -> ON")

    def off(self):
        self.state = False
        if HAS_GPIO:
            GPIO.output(self.pin, GPIO.HIGH if self.active_low else GPIO.LOW)
        else:
            print(f"[GPIO MOCK] Pin {self.pin} -> OFF")

    @staticmethod
    def cleanup():
        if HAS_GPIO:
            try:
                GPIO.cleanup()
            except Exception:
                pass


class SideState:
    def __init__(self, relay: Relay):
        self.relay = relay
        self.expiry: float = 0.0  # monotonic seconds
        self.event = asyncio.Event()
        self.lock = asyncio.Lock()


async def side_worker(name: str, state: SideState):
    while True:
        # Wait for a (re)trigger
        await state.event.wait()
        state.event.clear()

        while True:
            now = time.monotonic()
            exp = state.expiry
            if exp <= now:
                state.relay.off()
                break

            # Ensure relay is ON during active window
            state.relay.on()
            timeout = max(0.0, exp - now)
            try:
                # Wake early if another extend arrives
                await asyncio.wait_for(state.event.wait(), timeout=timeout)
                state.event.clear()
                # loop to recompute with new expiry
            except asyncio.TimeoutError:
                # Expired; turn off on next loop iteration
                state.expiry = 0.0
                # Continue loop to switch off


async def extend(state: SideState, seconds: int) -> float:
    async with state.lock:
        now = time.monotonic()
        base = state.expiry if state.expiry > now else now
        state.expiry = base + max(0, int(seconds))
        state.event.set()
        return state.expiry


async def run(ws_url: str):
    # Always generate a fresh token
    tok = secrets.token_urlsafe(16)
    print(f"Using token: {tok}")
    print("Connect REST callers with Authorization: Bearer <token>\n")

    # Initialize relays and side workers
    # Channel mapping (BCM): Ch2=20 (left), Ch3=21 (right); active-low relays
    left = SideState(Relay(20, active_low=True))
    right = SideState(Relay(21, active_low=True))
    workers = [
        asyncio.create_task(side_worker("left", left)),
        asyncio.create_task(side_worker("right", right)),
    ]

    try:
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
                if cmd != "whip":
                    print(f"Received message: {data}")
                    continue

                # Parse inputs
                try:
                    duration = int(data.get("duration"))
                except Exception:
                    print(f"Ignoring whip with invalid duration: {data.get('duration')}")
                    continue
                side = str(data.get("side", "both")).lower()

                # Apply per side, accumulating durations
                if side in ("left", "both"):
                    new_exp = await extend(left, duration)
                    print(f"Left whip extended by {duration}s; off at t={new_exp:.2f}")
                if side in ("right", "both"):
                    new_exp = await extend(right, duration)
                    print(f"Right whip extended by {duration}s; off at t={new_exp:.2f}")

    finally:
        # Turn everything off and cleanup
        left.relay.off()
        right.relay.off()
        for w in workers:
            w.cancel()
        try:
            await asyncio.gather(*workers, return_exceptions=True)
        finally:
            Relay.cleanup()


def main():
    parser = argparse.ArgumentParser(description="WebSocket client for Whip API (Raspberry Pi relays)")
    parser.add_argument("--ws-url", default="ws://whip.martinevsky.ru:60606/ws", help="WebSocket URL")
    args = parser.parse_args()

    asyncio.run(run(args.ws_url))


if __name__ == "__main__":
    main()
