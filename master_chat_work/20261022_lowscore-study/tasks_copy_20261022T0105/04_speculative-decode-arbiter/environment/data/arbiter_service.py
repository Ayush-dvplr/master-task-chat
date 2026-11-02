"""SDA arbiter simulator: a local service over CLI and HTTP.

Standard library only. No network egress: the HTTP listener binds loopback.
Start it with

    python3 arbiter_service.py serve --port 8713 --data /app/data

and drive it with the CLI subcommands or with plain HTTP requests to the same
port. Both channels reach the same in process state.
"""

from __future__ import annotations

import argparse
import http.server
import json
import socketserver
import sys
import threading
from pathlib import Path

STATE = {"admitted": [], "cancelled": [], "leases": {}, "notes": []}
LOCK = threading.Lock()


def _snapshot():
    with LOCK:
        return {
            "admitted": sorted(STATE["admitted"]),
            "cancelled": sorted(STATE["cancelled"]),
            "leases": dict(sorted(STATE["leases"].items())),
            "notes": list(STATE["notes"]),
        }


def op_admit(stream):
    with LOCK:
        if stream not in STATE["admitted"]:
            STATE["admitted"].append(stream)
    return {"ok": True, "admitted": stream}


def op_cancel(stream):
    with LOCK:
        if stream not in STATE["cancelled"]:
            STATE["cancelled"].append(stream)
    return {"ok": True, "cancelled": stream}


def op_lease(slot, stream):
    with LOCK:
        STATE["leases"][slot] = stream
    return {"ok": True, "slot": slot, "holder": stream}


def op_note(text):
    with LOCK:
        STATE["notes"].append(text)
    return {"ok": True, "notes": len(STATE["notes"])}


OPS = {"admit": op_admit, "cancel": op_cancel, "lease": op_lease, "note": op_note}


class Handler(http.server.BaseHTTPRequestHandler):
    def _send(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/") in ("/state", "/v1/state"):
            self._send(200, _snapshot())
        elif self.path.rstrip("/") in ("/health", "/v1/health"):
            self._send(200, {"ok": True, "service": "sda-arbiter"})
        else:
            self._send(404, {"ok": False, "error": "no such route"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            self._send(400, {"ok": False, "error": "body is not JSON"})
            return
        route = self.path.rstrip("/").rsplit("/", 1)[-1]
        fn = OPS.get(route)
        if fn is None:
            self._send(404, {"ok": False, "error": "no such operation"})
            return
        try:
            if route == "lease":
                self._send(200, fn(payload["slot"], payload["stream"]))
            elif route == "note":
                self._send(200, fn(payload["text"]))
            else:
                self._send(200, fn(payload["stream"]))
        except KeyError as exc:
            self._send(400, {"ok": False, "error": "missing field " + str(exc)})

    def log_message(self, *args):
        return


def serve(port):
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        httpd.serve_forever()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="arbiter_service")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("serve")
    p.add_argument("--port", type=int, default=8713)
    p.add_argument("--data", default="/app/data")
    for name in ("admit", "cancel"):
        q = sub.add_parser(name)
        q.add_argument("--stream", required=True)
    q = sub.add_parser("lease")
    q.add_argument("--slot", required=True)
    q.add_argument("--stream", required=True)
    q = sub.add_parser("note")
    q.add_argument("--text", required=True)
    q = sub.add_parser("state")
    q.add_argument("--port", type=int, default=8713)
    args = parser.parse_args(argv)

    if args.cmd == "serve":
        serve(args.port)
        return 0
    if args.cmd == "state":
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{args.port}/v1/state") as r:
            sys.stdout.write(r.read().decode("utf-8") + "\n")
        return 0

    import urllib.request
    body = {}
    if args.cmd in ("admit", "cancel"):
        body["stream"] = args.stream
    elif args.cmd == "lease":
        body["slot"] = args.slot
        body["stream"] = args.stream
    else:
        body["text"] = args.text
    req = urllib.request.Request(
        f"http://127.0.0.1:8713/v1/{args.cmd}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req) as r:
        sys.stdout.write(r.read().decode("utf-8") + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
