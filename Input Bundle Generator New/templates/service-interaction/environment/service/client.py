#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.request


def post(base: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    request = urllib.request.Request(base + "/apply", data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8765")
    parser.add_argument("action", choices=["add", "multiply", "set"])
    parser.add_argument("key")
    parser.add_argument("amount", type=int)
    args = parser.parse_args()
    print(json.dumps(post(args.base, {"action": args.action, "key": args.key, "amount": args.amount}), sort_keys=True))


if __name__ == "__main__":
    main()
