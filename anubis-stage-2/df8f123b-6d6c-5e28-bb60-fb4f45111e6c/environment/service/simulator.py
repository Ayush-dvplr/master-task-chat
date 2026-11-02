#!/usr/bin/env python3
"""Settlement interface for the pledge docket.

Serves the endpoints described in /app/data/service_protocol.md over the
loopback address. State is held in memory for the lifetime of the process.
"""

import argparse
import json
import re
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

TERMINAL = {
    "discharge": "discharged",
    "breach": "breached",
    "waive": "waived",
    "block": "blocked",
    "hold": "held",
    "lapse": "lapsed",
}

FINAL_STATES = [
    "cleared",
    "tempered_clear",
    "breached",
    "waived",
    "blocked",
    "held",
    "lapsed",
]

INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$")

LOCK = threading.Lock()

STATE = {
    "sealed": False,
    "window": None,
    "pledges": {},
    "order": [],
    "transcript": [],
    "accepted": 0,
    "rejected": 0,
    "granted_total": 0,
    "lateness_total": 0,
    "seal_sequence": 0,
}


def parse_instant(text):
    if not isinstance(text, str) or not INSTANT.match(text):
        raise ValueError("instant")
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S+00:00").replace(
        tzinfo=timezone.utc
    )


def fingerprint():
    registered = len(STATE["order"])
    discharged = 0
    waived = 0
    breached = 0
    for rec in STATE["pledges"].values():
        if rec["final_state"] in ("cleared", "tempered_clear"):
            discharged += 1
        elif rec["final_state"] == "waived":
            waived += 1
        elif rec["final_state"] == "breached":
            breached += 1
    return "%d:%d:%d:%d:%d:%d" % (
        registered,
        discharged,
        waived,
        breached,
        STATE["lateness_total"],
        STATE["granted_total"],
    )


def state_counts():
    counts = {name: 0 for name in FINAL_STATES}
    for rec in STATE["pledges"].values():
        if rec["final_state"] in counts:
            counts[rec["final_state"]] += 1
    return counts


def snapshot():
    return {
        "sealed": STATE["sealed"],
        "window_id": (STATE["window"] or {}).get("window_id", ""),
        "registered": len(STATE["order"]),
        "accepted_transitions": STATE["accepted"],
        "rejected_calls": STATE["rejected"],
        "state_counts": state_counts(),
        "grace_granted_total": STATE["granted_total"],
        "total_lateness_minutes": STATE["lateness_total"],
        "settlement_fingerprint": fingerprint() if STATE["sealed"] else "",
    }


def handle_window(body):
    needed = (
        "window_id",
        "window_open",
        "window_close",
        "settlement_cutoff",
        "grace_pool_minutes",
        "mode",
    )
    for key in needed:
        if key not in body:
            return 400, {"error": "missing_field", "reason": "missing_field"}
    try:
        opened = parse_instant(body["window_open"])
        closed = parse_instant(body["window_close"])
        parse_instant(body["settlement_cutoff"])
        pool = int(body["grace_pool_minutes"])
    except (ValueError, TypeError):
        return 400, {"error": "bad_field", "reason": "bad_field"}
    if closed <= opened or pool < 0:
        return 400, {"error": "bad_window", "reason": "bad_window"}
    if body["mode"] not in ("strict", "tempered"):
        return 400, {"error": "bad_mode", "reason": "bad_mode"}
    if STATE["window"] is not None:
        return 409, {"error": "window_declared", "reason": "window_declared"}
    STATE["window"] = {
        "window_id": body["window_id"],
        "open": opened,
        "close": closed,
        "cutoff": body["settlement_cutoff"],
        "pool": pool,
        "mode": body["mode"],
    }
    return 200, {"accepted": True, "window_id": body["window_id"], "pool_left": pool}


def handle_register(body):
    if STATE["sealed"]:
        return 423, {"error": "already_sealed", "reason": "already_sealed"}
    if STATE["window"] is None:
        return 409, {"error": "window_unset", "reason": "window_unset"}
    for key in ("pledge_id", "counterparty_key", "pledge_class", "due_instant"):
        if key not in body:
            return 400, {"error": "missing_field", "reason": "missing_field"}
    try:
        due = parse_instant(body["due_instant"])
    except (ValueError, TypeError):
        return 400, {"error": "bad_field", "reason": "bad_field"}
    pid = body["pledge_id"]
    prereqs = body.get("prereqs") or []
    external = body.get("external_prereqs") or []
    if not isinstance(prereqs, list) or not isinstance(external, list):
        return 400, {"error": "bad_field", "reason": "bad_field"}
    floor = None
    for item in external:
        if not isinstance(item, dict) or "effective_instant" not in item:
            return 400, {"error": "bad_field", "reason": "bad_field"}
        try:
            moment = parse_instant(item["effective_instant"])
        except (ValueError, TypeError):
            return 400, {"error": "bad_field", "reason": "bad_field"}
        floor = moment if floor is None or moment > floor else floor
    window = STATE["window"]
    if not (window["open"] <= due < window["close"]):
        return 409, {
            "error": "out_of_window",
            "reason": "out_of_window",
            "pledge_id": pid,
        }
    if pid in STATE["pledges"]:
        return 409, {
            "error": "duplicate_registration",
            "reason": "duplicate_registration",
            "pledge_id": pid,
        }
    for ref in prereqs:
        if ref not in STATE["pledges"]:
            return 409, {
                "error": "unknown_prereq",
                "reason": "unknown_prereq",
                "pledge_id": pid,
                "prereq_pledge_id": ref,
            }
    STATE["pledges"][pid] = {
        "pledge_id": pid,
        "counterparty_key": body["counterparty_key"],
        "pledge_class": body["pledge_class"],
        "due_instant": body["due_instant"],
        "prereqs": list(prereqs),
        "external_floor": floor,
        "phase": "registered",
        "final_state": "",
        "effective_instant": None,
        "lateness_minutes": 0,
        "granted_minutes": 0,
    }
    STATE["order"].append(pid)
    return 200, {"accepted": True, "pledge_id": pid, "registered": len(STATE["order"])}


def handle_transition(body):
    if STATE["sealed"]:
        return 423, {"error": "already_sealed", "reason": "already_sealed"}
    for key in ("pledge_id", "event"):
        if key not in body:
            return 400, {"error": "missing_field", "reason": "missing_field"}
    pid = body["pledge_id"]
    event = body["event"]
    rec = STATE["pledges"].get(pid)
    if rec is None:
        return 409, {"error": "unknown_pledge", "reason": "unknown_pledge"}
    if event == "acknowledge":
        if rec["phase"] != "registered":
            return 409, {"error": "bad_phase", "reason": "bad_phase"}
        rec["phase"] = "acknowledged"
        STATE["accepted"] += 1
        return 200, {"accepted": True, "pledge_id": pid, "phase": "acknowledged"}
    if event not in TERMINAL:
        return 400, {"error": "unknown_event", "reason": "unknown_event"}
    if rec["phase"] != "acknowledged":
        return 409, {"error": "not_acknowledged", "reason": "not_acknowledged"}
    moment = None
    if body.get("effective_instant") is not None:
        try:
            moment = parse_instant(body["effective_instant"])
        except (ValueError, TypeError):
            return 400, {"error": "bad_field", "reason": "bad_field"}
    try:
        lateness = int(body.get("lateness_minutes", 0))
    except (ValueError, TypeError):
        return 400, {"error": "bad_field", "reason": "bad_field"}
    if lateness < 0:
        return 400, {"error": "bad_field", "reason": "bad_field"}
    if event in ("discharge", "breach", "waive"):
        if moment is None and event != "breach":
            return 400, {"error": "missing_field", "reason": "missing_field"}
        floor = rec["external_floor"]
        for ref in rec["prereqs"]:
            other = STATE["pledges"].get(ref)
            if other is None or other["phase"] != "terminal":
                return 409, {
                    "error": "prereq_open",
                    "reason": "prereq_open",
                    "pledge_id": pid,
                }
            if other["effective_instant"] is not None:
                if floor is None or other["effective_instant"] > floor:
                    floor = other["effective_instant"]
        if event == "discharge" and floor is not None and moment is not None and moment < floor:
            return 409, {
                "error": "effective_regression",
                "reason": "effective_regression",
                "pledge_id": pid,
            }
    rec["phase"] = "terminal"
    rec["effective_instant"] = moment
    rec["lateness_minutes"] = lateness
    if event == "discharge":
        rec["final_state"] = "cleared" if lateness == 0 else "breached"
    elif event == "waive":
        rec["final_state"] = "waived"
    else:
        rec["final_state"] = TERMINAL[event]
    STATE["lateness_total"] += lateness
    STATE["accepted"] += 1
    return 200, {
        "accepted": True,
        "pledge_id": pid,
        "final_state": rec["final_state"],
        "lateness_minutes": lateness,
    }


def handle_grace(body):
    if STATE["sealed"]:
        return 423, {"error": "already_sealed", "reason": "already_sealed"}
    if STATE["window"] is None:
        return 409, {"error": "window_unset", "reason": "window_unset"}
    for key in ("pledge_id", "granted_minutes", "lateness_minutes"):
        if key not in body:
            return 400, {"error": "missing_field", "reason": "missing_field"}
    pid = body["pledge_id"]
    rec = STATE["pledges"].get(pid)
    if rec is None:
        return 409, {"error": "unknown_pledge", "reason": "unknown_pledge"}
    try:
        granted = int(body["granted_minutes"])
        lateness = int(body["lateness_minutes"])
    except (ValueError, TypeError):
        return 400, {"error": "bad_field", "reason": "bad_field"}
    if granted < 0 or lateness < 0:
        return 400, {"error": "bad_field", "reason": "bad_field"}
    if rec["final_state"] != "breached":
        return 409, {
            "error": "grace_ineligible_state",
            "reason": "grace_ineligible_state",
            "pledge_id": pid,
        }
    if granted > lateness:
        return 409, {
            "error": "grace_over_grant",
            "reason": "grace_over_grant",
            "pledge_id": pid,
        }
    left = STATE["window"]["pool"] - STATE["granted_total"]
    if granted > left:
        return 409, {
            "error": "pool_exhausted",
            "reason": "pool_exhausted",
            "pledge_id": pid,
        }
    rec["granted_minutes"] = granted
    STATE["granted_total"] += granted
    if granted >= rec["lateness_minutes"]:
        rec["final_state"] = "tempered_clear"
    STATE["accepted"] += 1
    return 200, {
        "accepted": True,
        "pledge_id": pid,
        "granted_minutes": granted,
        "final_state": rec["final_state"],
        "pool_left": STATE["window"]["pool"] - STATE["granted_total"],
    }


def handle_seal():
    if STATE["window"] is None:
        return 409, {"error": "window_unset", "reason": "window_unset"}
    if STATE["sealed"]:
        return 423, {"error": "already_sealed", "reason": "already_sealed"}
    open_phase = [
        pid for pid, rec in STATE["pledges"].items() if rec["phase"] != "terminal"
    ]
    if open_phase:
        return 409, {
            "error": "open_pledges",
            "reason": "open_pledges",
            "count": len(open_phase),
        }
    STATE["sealed"] = True
    return 200, snapshot()


def handle_transcript():
    return 200, {
        "calls": list(STATE["transcript"]),
        "count": len(STATE["transcript"]),
        "seal_sequence": STATE["seal_sequence"],
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "docket/1.0"

    def log_message(self, fmt, *args):
        return

    def _send(self, status, payload):
        raw = (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _channel(self):
        value = self.headers.get("X-Docket-Channel", "api")
        return "cli" if value == "cli" else "api"

    def _record(self, endpoint, status, payload, body):
        seq = len(STATE["transcript"]) + 1
        entry = {
            "sequence": seq,
            "endpoint": endpoint,
            "channel": self._channel(),
            "status": status,
            "accepted": status == 200,
            "reason": "" if status == 200 else str(payload.get("reason", "")),
            "pledge_id": str((body or {}).get("pledge_id", "")),
            "event": str((body or {}).get("event", "")),
        }
        STATE["transcript"].append(entry)
        if status == 200:
            if endpoint == "/seal":
                STATE["seal_sequence"] = seq
        else:
            STATE["rejected"] += 1
        return seq

    def do_GET(self):
        path = self.path.split("?")[0]
        with LOCK:
            if path == "/health":
                status, payload = 200, {"ok": True, "endpoint_count": 8}
            elif path == "/state":
                status, payload = 200, snapshot()
            elif path == "/transcript":
                status, payload = handle_transcript()
            else:
                status, payload = 404, {
                    "error": "unknown_path",
                    "reason": "unknown_path",
                }
        self._send(status, payload)

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
            if not isinstance(body, dict):
                raise ValueError("body")
        except (ValueError, UnicodeDecodeError):
            with LOCK:
                self._record(path, 400, {"reason": "bad_json"}, None)
            self._send(400, {"error": "bad_json", "reason": "bad_json"})
            return
        with LOCK:
            if path == "/window":
                status, payload = handle_window(body)
            elif path == "/register":
                status, payload = handle_register(body)
            elif path == "/transition":
                status, payload = handle_transition(body)
            elif path == "/grace":
                status, payload = handle_grace(body)
            elif path == "/seal":
                status, payload = handle_seal()
            else:
                status, payload = 404, {
                    "error": "unknown_path",
                    "reason": "unknown_path",
                }
            seq = self._record(path, status, payload, body)
            payload = dict(payload)
            payload["sequence"] = seq
        self._send(status, payload)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
