"""Command line front end for the relay seating service.

Reads one JSON batch body from a file or from standard input and posts it, or
fetches one of the read endpoints. Prints whatever the service answered.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from typing import Any, Dict


def fetch(base: str, route: str) -> Dict[str, Any]:
    with urllib.request.urlopen(base.rstrip("/") + route, timeout=30) as answer:
        return json.loads(answer.read().decode("utf-8"))


def post(base: str, body: Dict[str, Any]) -> Dict[str, Any]:
    payload = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        base.rstrip("/") + "/apply", data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=60) as answer:
            return json.loads(answer.read().decode("utf-8"))
    except urllib.error.HTTPError as problem:
        return json.loads(problem.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="relay service client")
    parser.add_argument("--base", default="http://127.0.0.1:8731")
    parser.add_argument("--action", choices=["health", "state", "transcript", "apply"],
                        default="health")
    parser.add_argument("--body", default="-")
    args = parser.parse_args()
    if args.action == "apply":
        text = sys.stdin.read() if args.body == "-" else open(args.body, encoding="utf-8").read()
        print(json.dumps(post(args.base, json.loads(text)), indent=2))
        return 0
    print(json.dumps(fetch(args.base, "/" + args.action), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
