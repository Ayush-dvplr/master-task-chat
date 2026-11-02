#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


STATE = {"alpha": 0, "beta": 0, "mode_code": 0}


def apply(payload: dict) -> dict:
    key = str(payload["key"])
    amount = int(payload["amount"])
    action = payload["action"]
    if key not in STATE:
        raise ValueError("unknown key")
    if action == "add":
        STATE[key] += amount
    elif action == "multiply":
        STATE[key] *= amount
    elif action == "set":
        STATE[key] = amount
    else:
        raise ValueError("unknown action")
    return dict(STATE)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def _send(self, status: int, body: dict) -> None:
        data = json.dumps(body, sort_keys=True).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/health":
            self._send(200, {"ok": True})
        elif self.path == "/state":
            self._send(200, dict(STATE))
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/apply":
            self._send(404, {"error": "not found"})
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        try:
            result = apply(json.loads(body.decode()))
        except Exception as exc:
            self._send(400, {"error": type(exc).__name__})
        else:
            self._send(200, result)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
