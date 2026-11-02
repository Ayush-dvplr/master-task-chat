"""HTTP front end for the relay seating reducer.

Run it with the host python interpreter. It holds the booted state in memory for
as long as it runs and serves the endpoints the runbook names.
"""
from __future__ import annotations

import argparse
import configparser
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import relay_core

LOCK = threading.Lock()
STATE: Dict[str, Any] = {}
TRANSCRIPT: List[Dict[str, Any]] = []
SEEN: Dict[str, Dict[str, Any]] = {}
SETTINGS: Dict[str, Any] = {}


def load_settings(data_dir: str) -> Dict[str, Any]:
    with open(os.path.join(data_dir, "horizon_config.json"), "r", encoding="utf-8") as handle:
        horizon = json.load(handle)
    with open(os.path.join(data_dir, "relay_policy_baseline.json"), "r", encoding="utf-8") as handle:
        policy = json.load(handle)
    ini = configparser.ConfigParser()
    ini.read(os.path.join(data_dir, "channel_budgets.ini"))
    cap = int(ini["defaults"]["advisory_cap"])
    return {
        "data_dir": data_dir,
        "decision_instant": horizon["decision_instant"],
        "batch_limit": cap // len(policy["ladder"]),
        "actor": policy["actor"],
        "cycle_id": policy["cycle_id"],
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send(self, code: int, payload: Dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route == "/health":
            self._send(200, {"status": "ready", "api_version": relay_core.API_VERSION,
                             "cycle_id": SETTINGS["cycle_id"]})
            return
        if route == "/state":
            with LOCK:
                self._send(200, json.loads(json.dumps(STATE)))
            return
        if route == "/transcript":
            with LOCK:
                self._send(200, {"calls": json.loads(json.dumps(TRANSCRIPT))})
            return
        self._send(404, {"error": "unknown_route", "route": route})

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        if route != "/apply":
            self._send(404, {"error": "unknown_route", "route": route})
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except ValueError:
            self._send(400, {"ok": False, "reason": "bad_json"})
            return
        with LOCK:
            answer = relay_core.apply_batch(STATE, TRANSCRIPT, SEEN, body,
                                            SETTINGS["batch_limit"], SETTINGS["actor"])
        self._send(200, answer)


def main() -> int:
    parser = argparse.ArgumentParser(description="relay seating service")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8731)
    parser.add_argument("--data", default="/app/data")
    args = parser.parse_args()
    SETTINGS.update(load_settings(args.data))
    STATE.update(relay_core.boot(args.data, SETTINGS["decision_instant"]))
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
