import argparse
import sys

import requests


def trigger(base_url: str, token: str, duration: int) -> int:
    url = base_url.rstrip("/") + "/whip"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.post(url, json={"duration": duration}, headers=headers, timeout=10)
    print(f"Response [{resp.status_code}]: {resp.text}")
    return resp.status_code


def main():
    parser = argparse.ArgumentParser(description="Trigger a whip command via REST API")
    parser.add_argument("--base-url", default="http://localhost:8080", help="Server base URL")
    parser.add_argument("--token", required=True, help="Bearer token matching the WS client")
    parser.add_argument("--duration", type=int, required=True, help="Duration in seconds (1..60)")
    args = parser.parse_args()

    if not (1 <= args.duration <= 60):
        print("Duration must be between 1 and 60 seconds", file=sys.stderr)
        sys.exit(2)

    code = trigger(args.base_url, args.token, args.duration)
    sys.exit(0 if 200 <= code < 300 else 1)


if __name__ == "__main__":
    main()

