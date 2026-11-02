"""Replay a login attempt journal into lockout reports.

Usage: python3 lockout.py IN_DIR OUT_DIR
"""
import hashlib
import json
import os
import re
import sys

REPORT_NAMES = ("locks.json", "decisions.jsonl", "summary.json")
FIELDS = {"seq", "kind", "user", "src", "at", "agent"}
KIND_ORDER = {"reset": 0, "pass": 1, "fail": 2, "probe": 3}

PREV_IGNORED = 2
OVERRIDES_IGNORED = 4
PASS_RESETS = 8
SOURCE_BAN = 16
RELAY_SEQLESS = 32
PROBE_COUNTS = 64
LOCK_SLIDES = 128

USER_PATTERN = re.compile(r"[a-z][a-z0-9._-]{0,30}")
AGENT_PATTERN = re.compile(r"[A-Za-z0-9/._-]{1,40}")
LIMIT_PATTERN = re.compile(r"[1-9]")
OCTET_PATTERN = re.compile(r"0|[1-9][0-9]{0,2}")


def is_count(value):
    """True for a real integer, never a bool."""
    return isinstance(value, int) and not isinstance(value, bool)


def is_address(text):
    """A dotted quad with four decimal octets, no leading zeros."""
    if not isinstance(text, str):
        return False
    pieces = text.split(".")
    if len(pieces) != 4:
        return False
    for part in pieces:
        if not OCTET_PATTERN.fullmatch(part) or int(part) > 255:
            return False
    return True


def is_user(text):
    return isinstance(text, str) and USER_PATTERN.fullmatch(text) is not None


def record_ok(item):
    """Check one parsed journal record against the record schema."""
    if not isinstance(item, dict) or set(item) != FIELDS:
        return False
    if not is_count(item["seq"]) or item["seq"] < 1:
        return False
    if item["kind"] not in KIND_ORDER or not is_user(item["user"]) or not is_address(item["src"]):
        return False
    if not is_count(item["at"]) or item["at"] < 0:
        return False
    agent = item["agent"]
    return agent is None or (isinstance(agent, str) and AGENT_PATTERN.fullmatch(agent) is not None)


def screen_journal(blob, mode):
    """Drop malformed, retransmitted and conflicting lines; keep the rest in arrival order."""
    tally = {"malformed": 0, "retransmitted": 0, "conflicting": 0}
    fingerprints = set()
    kept = {}
    for chunk in blob.split(b"\n"):
        if not chunk.strip():
            continue
        try:
            item = json.loads(chunk.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            tally["malformed"] += 1
            continue
        if not record_ok(item):
            tally["malformed"] += 1
            continue
        body = {k: v for k, v in item.items() if not (mode & RELAY_SEQLESS and k == "seq")}
        mark = json.dumps(body, sort_keys=True)
        if mark in fingerprints:
            tally["retransmitted"] += 1
            continue
        fingerprints.add(mark)
        if item["seq"] in kept:
            tally["conflicting"] += 1
            continue
        kept[item["seq"]] = item
    return list(kept.values()), tally


def read_policy(path):
    with open(path, "rb") as fh:
        doc = json.loads(fh.read().decode("utf-8"))
    return {key: doc[key] for key in ("window", "threshold", "lock", "ban_after", "ban")}


def read_overrides(path):
    """First valid row for a user stands; later rows for the same user are ignored."""
    limits = {}
    with open(path, "rb") as fh:
        lines = fh.read().decode("utf-8").splitlines()
    if not lines or lines[0].strip() != "user,limit,note":
        return limits
    for line in lines[1:]:
        cells = line.split(",")
        if len(cells) != 3 or not is_user(cells[0]) or not LIMIT_PATTERN.fullmatch(cells[1]):
            continue
        if cells[0] not in limits:
            limits[cells[0]] = int(cells[1])
    return limits


def read_previous(path):
    with open(path, "rb") as fh:
        doc = json.loads(fh.read().decode("utf-8"))
    rows = []
    for row in doc.get("locks", []):
        if not isinstance(row, dict) or not is_user(row.get("user")):
            continue
        if not is_count(row.get("until")) or not is_count(row.get("strikes")) or row["strikes"] < 1:
            continue
        rows.append(row)
    return rows


def read_mode(path):
    with open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8")).get("mode", 0)


class Ledger:
    """Per user and per source state while the journal is replayed."""

    def __init__(self, policy, limits, mode):
        self.policy = policy
        self.limits = {} if mode & OVERRIDES_IGNORED else limits
        self.mode = mode
        self.accounts = {}
        self.source_hits = {}
        self.bans = {}

    def entry_for(self, user):
        return self.accounts.setdefault(user, {"fails": [], "until": None, "strikes": 0, "length": 0})

    def seed(self, rows):
        for row in rows:
            if row["user"] in self.accounts:
                continue
            entry = self.entry_for(row["user"])
            entry["until"] = row["until"]
            entry["strikes"] = row["strikes"]
            entry["length"] = self.lock_span(row["strikes"])

    def lock_span(self, strikes):
        """Each further lock doubles the policy lock length."""
        return self.policy["lock"] * 2 ** (strikes - 1)

    def in_window(self, then, now):
        """A failure still counts at exactly window seconds old."""
        return now - then <= self.policy["window"]

    @staticmethod
    def is_locked(entry, now):
        """A lock ends at its until second: that second is already free."""
        return entry["until"] is not None and now < entry["until"]

    def record_failure(self, user, now):
        entry = self.entry_for(user)
        if self.is_locked(entry, now):
            if self.mode & LOCK_SLIDES:
                entry["until"] = now + entry["length"]
            return "deny"
        entry["fails"] = [t for t in entry["fails"] if self.in_window(t, now)] + [now]
        if len(entry["fails"]) >= self.limits.get(user, self.policy["threshold"]):
            entry["strikes"] += 1
            entry["length"] = self.lock_span(entry["strikes"])
            entry["until"] = now + entry["length"]
            entry["fails"] = []
            return "lock"
        return "fail"

    def record_source(self, src, now, outcome):
        if not self.mode & SOURCE_BAN:
            return outcome
        recent = [t for t in self.source_hits.get(src, []) if self.in_window(t, now)] + [now]
        if len(recent) >= self.policy["ban_after"]:
            self.bans[src] = now + self.policy["ban"]
            recent = []
            outcome = "ban"
        self.source_hits[src] = recent
        return outcome

    def decide(self, item):
        now, user, kind, src = item["at"], item["user"], item["kind"], item["src"]
        if kind == "reset":
            entry = self.entry_for(user)
            was_locked = self.is_locked(entry, now)
            entry["fails"] = []
            entry["until"] = None
            return "unlock" if was_locked else "ignore"
        if self.mode & SOURCE_BAN and now < self.bans.get(src, -1):
            return "deny"
        if kind == "probe" and not self.mode & PROBE_COUNTS:
            return self.record_source(src, now, "ignore")
        if kind in ("fail", "probe"):
            return self.record_source(src, now, self.record_failure(user, now))
        entry = self.entry_for(user)
        if self.is_locked(entry, now):
            return "deny"
        if self.mode & PASS_RESETS:
            entry["fails"] = []
        return "allow"


def replay_order(records):
    """Same second: reset, pass, fail, probe; then by seq."""
    return sorted(records, key=lambda r: (r["at"], KIND_ORDER[r["kind"]], r["seq"]))


def table_lines(rows, key):
    return "".join(sorted("%s %d\n" % (name, row[key]) for name, row in rows.items()))


def build_reports(ledger, decisions, tally, overrides):
    last = decisions[-1]["at"] if decisions else 0
    locks = {user: {"strikes": a["strikes"], "until": a["until"]}
             for user, a in ledger.accounts.items() if ledger.is_locked(a, last)}
    bans = {src: {"until": until} for src, until in ledger.bans.items() if last < until}
    counted = {}
    for row in decisions:
        counted[row["result"]] = counted.get(row["result"], 0) + 1
    summary = dict(tally)
    summary.update({
        "events": len(decisions),
        "allows": counted.get("allow", 0),
        "fails": counted.get("fail", 0),
        "locks": counted.get("lock", 0),
        "denies": counted.get("deny", 0),
        "unlocks": counted.get("unlock", 0),
        "bans": counted.get("ban", 0),
        "ignored": counted.get("ignore", 0),
        "active": len(locks),
        "banned": len(bans),
        "overrides": overrides,
        "table_digest": hashlib.sha256(table_lines(locks, "until").encode()).hexdigest(),
    })
    return {
        "locks.json": json.dumps({"bans": bans, "locks": locks}, sort_keys=True, indent=2) + "\n",
        "decisions.jsonl": "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in decisions),
        "summary.json": json.dumps(summary, sort_keys=True, indent=2) + "\n",
    }


def replay(in_dir):
    mode = read_mode(os.path.join(in_dir, "manifest.json"))
    with open(os.path.join(in_dir, "attempts.jsonl"), "rb") as fh:
        records, tally = screen_journal(fh.read(), mode)
    limits = read_overrides(os.path.join(in_dir, "overrides.csv"))
    ledger = Ledger(read_policy(os.path.join(in_dir, "policy.json")), limits, mode)
    if not mode & PREV_IGNORED:
        ledger.seed(read_previous(os.path.join(in_dir, "locks.prev.json")))
    decisions = []
    for item in replay_order(records):
        decisions.append({"at": item["at"], "seq": item["seq"], "user": item["user"], "src": item["src"],
                          "kind": item["kind"], "result": ledger.decide(item)})
    return build_reports(ledger, decisions, tally, len(limits))


def write_reports(out_dir, reports):
    os.makedirs(out_dir, exist_ok=True)
    for name in REPORT_NAMES:
        with open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(reports[name])


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: lockout.py IN_DIR OUT_DIR\n")
        return 2
    write_reports(argv[2], replay(argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
