#!/usr/bin/env python3
"""Desk client for the settlement interface.

Every call this client sends carries the desk channel header with the value
cli, so the interface transcript records the call as a client call. Calls sent
straight to the interface without that header are recorded as api calls.

Examples
  client.py get /state
  client.py post /transition --field pledge_id=PL-10001 --field event=waive
  client.py post /transition --json '{"pledge_id": "PL-10001", "event": "waive"}'
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

CHANNEL_HEADER = "X-Docket-Channel"
CHANNEL_VALUE = "cli"
DEFAULT_BASE = "http://127.0.0.1:8765"

INT_FIELDS = (
    "grace_pool_minutes",
    "granted_minutes",
    "lateness_minutes",
)
BOOL_FIELDS = ("boundary",)
LIST_FIELDS = ("prereqs",)


def coerce(key, raw):
    """Turn one command line field value into its JSON shape."""
    if key in INT_FIELDS:
        return int(raw)
    if key in BOOL_FIELDS:
        return raw.strip().lower() in ("1", "true", "yes")
    if key in LIST_FIELDS:
        text = raw.strip()
        if not text:
            return []
        return [part.strip() for part in text.split(",") if part.strip()]
    return raw


def build_body(args):
    """Assemble the request body from the raw json flag and the field flags."""
    body = {}
    if args.json:
        parsed = json.loads(args.json)
        if not isinstance(parsed, dict):
            raise ValueError("the json flag must carry an object")
        body.update(parsed)
    for item in args.field or []:
        if "=" not in item:
            raise ValueError("field %r needs the form key=value" % item)
        key, _, raw = item.partition("=")
        body[key.strip()] = coerce(key.strip(), raw)
    return body


def call(base, endpoint, method, body):
    """Send one request and return the status code with the decoded payload."""
    url = base.rstrip("/") + endpoint
    data = None
    headers = {CHANNEL_HEADER: CHANNEL_VALUE}
    if method == "POST":
        data = json.dumps(body or {}).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as err:
        raw = err.read().decode("utf-8")
        payload = json.loads(raw) if raw.strip() else {}
        return err.code, payload


def main(argv=None):
    parser = argparse.ArgumentParser(description="Desk client for the settlement interface")
    parser.add_argument("--base", default=DEFAULT_BASE, help="interface base address")
    sub = parser.add_subparsers(dest="verb", required=True)

    getter = sub.add_parser("get", help="send a GET request")
    getter.add_argument("endpoint", help="endpoint path, for example /state")

    poster = sub.add_parser("post", help="send a POST request")
    poster.add_argument("endpoint", help="endpoint path, for example /transition")
    poster.add_argument("--field", action="append", help="body field in the form key=value")
    poster.add_argument("--json", help="body as a json object")

    args = parser.parse_args(argv)
    endpoint = args.endpoint if args.endpoint.startswith("/") else "/" + args.endpoint

    if args.verb == "get":
        status, payload = call(args.base, endpoint, "GET", None)
    else:
        status, payload = call(args.base, endpoint, "POST", build_body(args))

    print(json.dumps({"status": status, "payload": payload}, sort_keys=True))
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
