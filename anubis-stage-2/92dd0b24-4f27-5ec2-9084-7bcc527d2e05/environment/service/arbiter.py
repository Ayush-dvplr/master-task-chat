"""Circuit arbiter of record for one adjudication slate.

The arbiter stores adjudication outcomes and keeps the operation journal
that the circuit audits. It holds no legality policy of its own. The
advisory numbers returned by GET /advice are a convenience for console
operators and are superseded by the published slate corpus wherever the
two disagree, so nothing here should be read as a ruling.

Start it with:

    python3 /app/service/arbiter.py --seed /app/data/registry_seed.json

It listens on loopback only and keeps no state on disk.
"""

import argparse
import configparser
import csv
import hashlib
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

OPERATIONS = ("register", "seat", "amend", "flag", "bar", "defer",
              "reinstate")
STATES = ("intake", "seated", "amended", "flagged", "barred", "deferred")
FORMATS = ("classic", "singleton", "relic")
SCOPES = ("global", "addendum", "rider", "base")
CHANNELS = ("api", "console")
CONSOLE_ONLY = ("bar", "reinstate")
REFUSALS = ("unknown_entry", "state_conflict", "channel_denied",
            "stale_etag", "malformed", "scope_invalid")

TRANSITIONS = {
    ("intake", "register"): "intake",
    ("intake", "seat"): "seated",
    ("intake", "amend"): "amended",
    ("intake", "flag"): "flagged",
    ("intake", "bar"): "barred",
    ("intake", "defer"): "deferred",
    ("seated", "amend"): "amended",
    ("seated", "flag"): "flagged",
    ("seated", "bar"): "barred",
    ("seated", "defer"): "deferred",
    ("amended", "flag"): "flagged",
    ("amended", "bar"): "barred",
    ("amended", "defer"): "deferred",
    ("flagged", "amend"): "amended",
    ("flagged", "bar"): "barred",
    ("flagged", "defer"): "deferred",
    ("deferred", "seat"): "seated",
    ("deferred", "amend"): "amended",
    ("deferred", "flag"): "flagged",
    ("deferred", "bar"): "barred",
    ("barred", "reinstate"): "deferred",
}

LOCK = threading.Lock()
CFG = {}
STATE = {}
JOURNAL = []
REFUSED = {}
PAGES = []
LAGLOG = []
PENDING = {}
SEEN = {}
SHAPE = {}
REVISED = set()
COUNT = {"requests": 0, "ticks": 0, "seq": 0, "renewals": 0}
DIGEST = {"value": ""}


def _etag(entry, slot):
    raw = "%s:%s:%d" % (entry, slot["state"], slot["rev"])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _snapshot(entry):
    slot = STATE[entry]
    LAGLOG.append((COUNT["ticks"], entry, {
        "state": slot["state"], "scope": slot["scope"],
        "channel": slot["channel"], "last_seq": slot["last_seq"]}))


def _lagged():
    horizon = COUNT["ticks"] - CFG["list_lag_requests"]
    view = {}
    for entry in STATE:
        view[entry] = {"state": CFG["initial_state"], "scope": "none",
                       "channel": "none", "last_seq": 0}
    for mark, entry, body in LAGLOG:
        if mark <= horizon:
            view[entry] = dict(body)
    return view


def _apply(entry, op, scope, channel):
    slot = STATE[entry]
    COUNT["seq"] += 1
    seq = COUNT["seq"]
    slot["state"] = TRANSITIONS[(slot["state"], op)]
    slot["scope"] = scope
    slot["channel"] = channel
    slot["last_seq"] = seq
    slot["rev"] += 1
    line = "%d:%s:%s:%s:%s" % (seq, op, entry, scope, channel)
    DIGEST["value"] = hashlib.sha256(
        (DIGEST["value"] + "|" + line).encode("utf-8")).hexdigest()
    JOURNAL.append({"seq": seq, "op": op, "entry": entry, "scope": scope,
                    "channel": channel})
    _snapshot(entry)
    return {"applied": True, "seq": seq, "entry": entry, "op": op,
            "scope": scope, "channel": channel, "state": slot["state"],
            "digest": DIGEST["value"]}


def _refuse(code):
    REFUSED[code] = REFUSED.get(code, 0) + 1
    return 409, {"applied": False, "refusal": code}


def _write(body, channel, key, match):
    op = body.get("operation")
    entry = body.get("entry")
    shape = body.get("format")
    if op not in OPERATIONS or not isinstance(entry, str) or not entry:
        return _refuse("malformed")
    if shape not in FORMATS:
        return _refuse("malformed")
    held = SHAPE.get(entry)
    if held is not None and held != shape:
        return _refuse("malformed")
    scope = body.get("scope")
    if scope is None:
        scope = CFG["console_default_scope"] if channel == "console" \
            else CFG["api_default_scope"]
    if scope not in SCOPES:
        return _refuse("scope_invalid")
    if op in CONSOLE_ONLY and channel != "console":
        return _refuse("channel_denied")
    if key:
        stored = SEEN.get(key)
        if stored is not None:
            return 200, stored
    if op == "register":
        if entry in STATE:
            return _refuse("state_conflict")
        STATE[entry] = {"state": CFG["initial_state"], "scope": "none",
                        "channel": "none", "last_seq": 0, "rev": 1}
        SHAPE[entry] = shape
        result = _apply(entry, op, scope, channel)
        if key:
            SEEN[key] = result
        return 200, result
    if entry not in STATE:
        return _refuse("unknown_entry")
    slot = STATE[entry]
    if match != _etag(entry, slot):
        return _refuse("stale_etag")
    if (slot["state"], op) not in TRANSITIONS:
        return _refuse("state_conflict")
    SHAPE[entry] = shape
    if shape == CFG["async_format"]:
        token = "OPN%06d" % (len(PENDING) + 1)
        PENDING[token] = {"entry": entry, "op": op, "scope": scope,
                          "channel": channel, "key": key}
        return 202, {"applied": False, "operation_id": token,
                     "state": "pending"}
    result = _apply(entry, op, scope, channel)
    if key:
        SEEN[key] = result
    return 200, result


def _complete(token):
    held = PENDING.pop(token, None)
    if held is None:
        return 404, {"operation_id": token, "state": "unknown"}
    result = _apply(held["entry"], held["op"], held["scope"],
                    held["channel"])
    if held["key"]:
        SEEN[held["key"]] = result
    result["operation_id"] = token
    result["state"] = STATE[held["entry"]]["state"]
    return 200, result


def _state_body():
    entries = {}
    for entry, slot in STATE.items():
        entries[entry] = {"state": slot["state"], "scope": slot["scope"],
                          "channel": slot["channel"],
                          "last_seq": slot["last_seq"]}
    return {"slate_id": CFG["slate_id"], "journal_seq": COUNT["seq"],
            "digest": DIGEST["value"], "entries": entries,
            "refusals": dict(REFUSED)}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def _send(self, code, payload):
        raw = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _charge(self, path):
        if path == "/renew":
            COUNT["requests"] = 0
            COUNT["renewals"] += 1
            return None
        COUNT["requests"] += 1
        COUNT["ticks"] += 1
        if COUNT["requests"] > CFG["request_budget"]:
            return CFG["expiry_code"]
        return None

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        with LOCK:
            if url.path == "/health":
                self._send(200, {"slate_id": CFG["slate_id"],
                                 "ready": True})
                return
            spent = self._charge(url.path)
            if spent is not None:
                self._send(401, {"refusal": spent})
                return
            if url.path == "/state":
                self._send(200, _state_body())
            elif url.path == "/journal":
                self._send(200, {"entries": list(JOURNAL),
                                 "refusals": dict(REFUSED),
                                 "journal_seq": COUNT["seq"]})
            elif url.path == "/advice":
                self._send(200, dict(CFG["advice"]))
            elif url.path == "/entries":
                mark = query.get("cursor", ["p0"])[0]
                try:
                    index = int(mark[1:]) if mark.startswith("p") else -1
                except ValueError:
                    index = -1
                if index < 0 or index >= len(PAGES):
                    self._send(400, {"refusal": "malformed"})
                    return
                view = _lagged()
                shown = [dict(view[e], entry=e) for e in PAGES[index]]
                body = {"page": index, "entries": shown}
                if index + 1 < len(PAGES):
                    body["next_cursor"] = "p%d" % (index + 1)
                self._send(200, body)
            elif url.path == "/entry":
                entry = query.get("id", [""])[0]
                slot = STATE.get(entry)
                if slot is None:
                    self._send(404, {"refusal": "unknown_entry"})
                    return
                tag = _etag(entry, slot)
                if entry in CFG["contested"] and entry not in REVISED:
                    REVISED.add(entry)
                    slot["rev"] += 1
                self._send(200, {"entry": entry, "state": slot["state"],
                                 "scope": slot["scope"],
                                 "channel": slot["channel"],
                                 "last_seq": slot["last_seq"],
                                 "etag": tag})
            elif url.path == "/operation":
                code, body = _complete(query.get("id", [""])[0])
                self._send(code, body)
            else:
                self._send(404, {"refusal": "malformed"})

    def do_POST(self):
        url = urlparse(self.path)
        size = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(size) if size else b"{}"
        with LOCK:
            if url.path == "/renew":
                self._charge(url.path)
                self._send(200, {"token": CFG["token"],
                                 "request_budget": CFG["request_budget"]})
                return
            spent = self._charge(url.path)
            if spent is not None:
                self._send(401, {"refusal": spent})
                return
            if url.path != "/act":
                self._send(404, {"refusal": "malformed"})
                return
            try:
                body = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                code, out = _refuse("malformed")
                self._send(code, out)
                return
            if not isinstance(body, dict):
                code, out = _refuse("malformed")
                self._send(code, out)
                return
            channel = self.headers.get(CFG["channel_header"]) or "api"
            if channel not in CHANNELS:
                code, out = _refuse("malformed")
                self._send(code, out)
                return
            key = self.headers.get(CFG["key_header"]) or ""
            match = self.headers.get("If-Match") or ""
            code, out = _write(body, channel, key, match)
            self._send(code, out)


ADVICE = {"note": "console convenience only, superseded by the corpus",
          "default_copies": 4, "points_budget_cpt": 1600,
          "charge_ceiling_cpt": 700, "carry_cap": 5}


def boot(seed_path):
    home = os.path.dirname(os.path.abspath(seed_path))
    with open(seed_path, "r", encoding="utf-8") as fh:
        seed = json.load(fh)
    CFG.update(seed)
    with open(os.path.join(home, "service_token.json"), "r",
              encoding="utf-8") as fh:
        CFG.update(json.load(fh))
    CFG["advice"] = ADVICE
    policy = configparser.ConfigParser()
    policy.read(os.path.join(home, "channel_policy.ini"), encoding="utf-8")
    if policy.has_section("channels"):
        for name in ("api_default_scope", "console_default_scope"):
            if policy.has_option("channels", name):
                CFG[name] = policy.get("channels", name).strip()
    CFG.setdefault("api_default_scope", "global")
    CFG.setdefault("console_default_scope", "addendum")
    CFG.setdefault("channel_header", "X-Arbiter-Channel")
    CFG.setdefault("key_header", "X-Arbiter-Key")
    CFG.setdefault("initial_state", "intake")
    CFG["contested"] = set()
    feed = os.path.join(home, os.path.basename(seed["contested_feed"]))
    if os.path.exists(feed):
        with open(feed, "r", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                CFG["contested"].add(row["submission_id"])
    DIGEST["value"] = hashlib.sha256(
        CFG["slate_id"].encode("utf-8")).hexdigest()
    for entry in seed["preseeded_entries"]:
        STATE[entry] = {"state": CFG["initial_state"], "scope": "none",
                        "channel": "none", "last_seq": 0, "rev": 1}
    ordered = sorted(STATE)
    size = CFG["page_size"]
    chunks = [ordered[i:i + size] for i in range(0, len(ordered), size)]
    run = 0
    for chunk in chunks:
        PAGES.append(chunk)
        run += 1
        if run % CFG["empty_page_after_pages"] == 0 and chunk is not chunks[-1]:
            PAGES.append([])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", default="/app/data/registry_seed.json")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8814)
    args = ap.parse_args()
    boot(args.seed)
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print("arbiter ready on %s:%d" % (args.host, args.port), flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
