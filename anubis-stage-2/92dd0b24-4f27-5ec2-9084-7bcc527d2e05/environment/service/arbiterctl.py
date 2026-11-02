"""Console for the circuit arbiter.

Every request this console sends is marked as coming from the console
channel, so the operations the circuit reserves for the console go
through here. Reads and writes share one command set:

    python3 /app/service/arbiterctl.py state
    python3 /app/service/arbiterctl.py entry --id SB000001
    python3 /app/service/arbiterctl.py bar --entry SB000001 \
        --format classic --scope global --match <etag> --key <idem>

The console leaves the scope out of the request body when no scope is
given, which lets the arbiter fall back to the console default named in
the channel policy. The body is printed as sorted JSON and the exit
status is zero only for a 200 reply.
"""

import argparse
import json
import sys
import urllib.error
import urllib.request

WRITES = ("register", "seat", "amend", "flag", "bar", "defer", "reinstate")
READS = ("state", "journal", "health", "advice", "entries", "entry",
         "operation")


def call(url, payload, headers):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers,
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=WRITES + READS + ("renew",))
    ap.add_argument("--entry", default="")
    ap.add_argument("--format", dest="shape", default="")
    ap.add_argument("--scope", default="")
    ap.add_argument("--key", default="")
    ap.add_argument("--match", default="")
    ap.add_argument("--cursor", default="")
    ap.add_argument("--id", dest="ident", default="")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8814)
    args = ap.parse_args()
    root = "http://%s:%d" % (args.host, args.port)
    headers = {"X-Arbiter-Channel": "console",
               "Content-Type": "application/json"}
    if args.command in WRITES:
        body = {"operation": args.command, "entry": args.entry,
                "format": args.shape}
        if args.scope:
            body["scope"] = args.scope
        if args.key:
            headers["X-Arbiter-Key"] = args.key
        if args.match:
            headers["If-Match"] = args.match
        code, text = call(root + "/act", body, headers)
    elif args.command == "renew":
        code, text = call(root + "/renew", {}, headers)
    elif args.command == "entries":
        mark = args.cursor or "p0"
        code, text = call(root + "/entries?cursor=" + mark, None, headers)
    elif args.command == "entry":
        code, text = call(root + "/entry?id=" + (args.ident or args.entry),
                          None, headers)
    elif args.command == "operation":
        code, text = call(root + "/operation?id=" + args.ident, None,
                          headers)
    else:
        code, text = call(root + "/" + args.command, None, headers)
    try:
        print(json.dumps(json.loads(text), sort_keys=True))
    except ValueError:
        print(text)
    sys.exit(0 if code == 200 else 1)


if __name__ == "__main__":
    main()
