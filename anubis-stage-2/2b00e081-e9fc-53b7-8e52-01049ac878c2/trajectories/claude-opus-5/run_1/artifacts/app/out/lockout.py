#!/usr/bin/env python3
"""Replay a sign-in attempt journal into a lockout table.

Usage: python3 lockout.py IN_DIR OUT_DIR

IN_DIR holds attempts.jsonl, policy.json, overrides.csv, locks.prev.json and
manifest.json.  The three reports locks.json, decisions.jsonl and summary.json
are written into OUT_DIR, replacing any copies already there.
"""

import hashlib
import json
import os
import re
import sys

USER_RE = re.compile(r"\A[a-z][a-z0-9._-]{0,30}\Z")
AGENT_RE = re.compile(r"\A[A-Za-z0-9/._-]{1,40}\Z")
QUAD_PART_RE = re.compile(r"\A(?:0|[1-9][0-9]{0,2})\Z")
LIMIT_RE = re.compile(r"\A[1-9]\Z")

RECORD_KEYS = frozenset(("seq", "kind", "user", "src", "at", "agent"))

# Records that share one second are replayed in this order of `kind`, then by
# ascending `seq`.
KIND_ORDER = {"reset": 0, "pass": 1, "fail": 2, "probe": 3}

RESULTS = ("allow", "fail", "lock", "deny", "unlock", "ban", "ignore")

REPORT_NAMES = ("locks.json", "decisions.jsonl", "summary.json")

# Mode word bits.  The value 1 is reserved and always clear.
BIT_SCREENING = 2
BIT_SEEDING = 4
BIT_LIMITS = 8
BIT_COUNTING = 16
BIT_SOURCE = 32
BIT_RESET = 64
BIT_EXTEND = 128

SOURCE_KINDS = frozenset(("fail", "probe"))


def is_plain_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def valid_user(value):
    return isinstance(value, str) and USER_RE.match(value) is not None


def valid_src(value):
    if not isinstance(value, str):
        return False
    parts = value.split(".")
    if len(parts) != 4:
        return False
    for part in parts:
        if QUAD_PART_RE.match(part) is None or int(part) > 255:
            return False
    return True


def valid_agent(value):
    if value is None:
        return True
    return isinstance(value, str) and AGENT_RE.match(value) is not None


def config_from_mode(mode):
    """Turn a mode word into the behaviour switches used by the replay."""
    if not is_plain_int(mode) or mode < 0:
        raise ValueError("manifest mode must be a non-negative integer")
    return {
        # Screening: the later line of a `seq` conflict replaces the earlier one.
        "conflict_later_wins": bool(mode & BIT_SCREENING),
        # Seeding: seeded strike counts are discarded; seeded users start at 0.
        "seed_strikes_zero": bool(mode & BIT_SEEDING),
        # Limits: the last valid overrides row for a user stands.
        "override_last_wins": bool(mode & BIT_LIMITS),
        # Failure counting: counted failures never fall out of the window.
        "window_unbounded": bool(mode & BIT_COUNTING),
        # Source handling: per-source counting, with `ban_after` and `ban`.
        "bans_enabled": bool(mode & BIT_SOURCE),
        # Lock handling: a reset only reports; it clears nothing.
        "reset_clears_nothing": bool(mode & BIT_RESET),
        # Lock handling: a denied failure pushes the lock end out again.
        "deny_extends_lock": bool(mode & BIT_EXTEND),
    }


def parse_record(text):
    """Return the record dict, or None when the line breaks a journal rule."""
    try:
        obj = json.loads(text)
    except ValueError:
        return None
    if not isinstance(obj, dict):
        return None
    if frozenset(obj) != RECORD_KEYS:
        return None
    if not is_plain_int(obj["seq"]) or obj["seq"] < 1:
        return None
    if obj["kind"] not in KIND_ORDER:
        return None
    if not valid_user(obj["user"]):
        return None
    if not valid_src(obj["src"]):
        return None
    if not is_plain_int(obj["at"]) or obj["at"] < 0:
        return None
    if not valid_agent(obj["agent"]):
        return None
    return obj


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def read_lines(path):
    """Split the journal into lines without assuming it decodes as UTF-8."""
    with open(path, "rb") as handle:
        data = handle.read()
    if data.endswith(b"\n"):
        data = data[:-1]
    if data == b"":
        return []
    return data.split(b"\n")


def screen(raw_lines, config):
    """Apply the four screening steps and return accepted records plus counts."""
    seen = set()
    by_seq = {}
    arrival = []
    counts = {"malformed": 0, "retransmitted": 0, "conflicting": 0}
    for raw in raw_lines:
        if raw.strip() == b"":
            continue
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            counts["malformed"] += 1
            continue
        record = parse_record(text)
        if record is None:
            counts["malformed"] += 1
            continue
        key = canonical(record)
        if key in seen:
            counts["retransmitted"] += 1
            continue
        seen.add(key)
        seq = record["seq"]
        if seq in by_seq:
            counts["conflicting"] += 1
            if config["conflict_later_wins"]:
                by_seq[seq] = record
            continue
        by_seq[seq] = record
        arrival.append(seq)
    records = [by_seq[seq] for seq in arrival]
    records.sort(key=lambda r: (r["at"], KIND_ORDER[r["kind"]], r["seq"]))
    return records, counts


def load_policy(path):
    with open(path, "r", encoding="utf-8") as handle:
        policy = json.load(handle)
    return {name: policy[name]
            for name in ("window", "threshold", "lock", "ban_after", "ban")}


def load_overrides(path, config):
    """Return the per-user failure limits taken from overrides.csv."""
    limits = {}
    with open(path, "r", encoding="utf-8") as handle:
        rows = handle.read().split("\n")
    for row in rows[1:]:
        if row == "":
            continue
        fields = row.split(",")
        if len(fields) != 3:
            continue
        user, limit = fields[0], fields[1]
        if not valid_user(user) or LIMIT_RE.match(limit) is None:
            continue
        if user in limits and not config["override_last_wins"]:
            continue
        limits[user] = int(limit)
    return limits


def load_seeds(path, config):
    """Return seeded (until, strikes) pairs taken from locks.prev.json."""
    with open(path, "r", encoding="utf-8") as handle:
        doc = json.load(handle)
    seeds = {}
    rows = doc.get("locks")
    if not isinstance(rows, list):
        return seeds
    for row in rows:
        if not isinstance(row, dict):
            continue
        user, until, strikes = row.get("user"), row.get("until"), row.get("strikes")
        if not valid_user(user):
            continue
        if not is_plain_int(until) or not is_plain_int(strikes) or strikes < 1:
            continue
        if user in seeds:
            continue
        seeds[user] = (until, 0 if config["seed_strikes_zero"] else strikes)
    return seeds


class Replay:
    """Per-user and per-source state carried through the journal."""

    def __init__(self, policy, limits, seeds, config):
        self.policy = policy
        self.limits = limits
        self.config = config
        self.users = {}
        self.sources = {}
        for user, (until, strikes) in seeds.items():
            state = self.user_state(user)
            state["until"] = until
            state["strikes"] = strikes

    def user_state(self, user):
        state = self.users.get(user)
        if state is None:
            state = {"fails": [], "until": None, "strikes": 0, "limit": self.limit_for(user)}
            self.users[user] = state
        return state

    def source_state(self, src):
        state = self.sources.get(src)
        if state is None:
            state = {"hits": [], "until": None}
            self.sources[src] = state
        return state

    def is_held(self, until, now):
        return until is not None and now < until

    def in_window(self, stamp, now):
        if self.config["window_unbounded"]:
            return True
        return now - stamp <= self.policy["window"]

    def lock_length(self, strikes):
        return self.policy["lock"] * 2 ** (max(1, strikes) - 1)

    def limit_for(self, user):
        return self.limits.get(user, self.policy["threshold"])

    def note_source(self, record):
        """Count a record against its source; True when that source is banned."""
        if not self.config["bans_enabled"] or record["kind"] not in SOURCE_KINDS:
            return False
        now = record["at"]
        state = self.source_state(record["src"])
        window = self.policy["window"]
        state["hits"] = [s for s in state["hits"] if now - s <= window]
        state["hits"].append(now)
        if len(state["hits"]) >= self.policy["ban_after"]:
            state["until"] = now + self.policy["ban"]
            state["hits"] = []
            return True
        return False

    def handle_reset(self, state, now):
        was_locked = self.is_held(state["until"], now)
        if not self.config["reset_clears_nothing"]:
            state["fails"] = []
            state["until"] = None
        return "unlock" if was_locked else "ignore"

    def handle_pass(self, state, now):
        return "deny" if self.is_held(state["until"], now) else "allow"

    def handle_fail(self, state, now):
        if self.is_held(state["until"], now):
            if self.config["deny_extends_lock"]:
                state["until"] = now + self.lock_length(state["strikes"])
            return "deny"
        state["fails"] = [s for s in state["fails"] if self.in_window(s, now)]
        state["fails"].append(now)
        if len(state["fails"]) < state["limit"]:
            return "fail"
        state["strikes"] += 1
        state["until"] = now + self.lock_length(state["strikes"])
        state["fails"] = []
        return "lock"

    def handle(self, record):
        kind = record["kind"]
        now = record["at"]
        if kind == "probe":
            result = "ignore"
        elif kind == "reset":
            result = self.handle_reset(self.user_state(record["user"]), now)
        elif kind == "pass":
            result = self.handle_pass(self.user_state(record["user"]), now)
        else:
            result = self.handle_fail(self.user_state(record["user"]), now)
        if self.note_source(record):
            result = "ban"
        return result

    def tables(self, now):
        locks = {}
        bans = {}
        if now is None:
            return {"bans": bans, "locks": locks}
        for user, state in self.users.items():
            if self.is_held(state["until"], now):
                locks[user] = {"strikes": state["strikes"], "until": state["until"]}
        for src, state in self.sources.items():
            if self.is_held(state["until"], now):
                bans[src] = {"until": state["until"]}
        return {"bans": bans, "locks": locks}


def table_digest(entries):
    """SHA-256 of the sorted `<key> <until>\\n` lines of one table."""
    lines = ["%s %d\n" % (key, value["until"]) for key, value in entries.items()]
    return hashlib.sha256("".join(sorted(lines)).encode("utf-8")).hexdigest()


def render_locks(tables):
    return json.dumps(tables, sort_keys=True, indent=2) + "\n"


def render_decisions(decisions):
    out = []
    for record, result in decisions:
        line = {
            "at": record["at"],
            "kind": record["kind"],
            "result": result,
            "seq": record["seq"],
            "src": record["src"],
            "user": record["user"],
        }
        out.append(json.dumps(line, sort_keys=True, separators=(",", ":")) + "\n")
    return "".join(out)


def render_summary(counts, decisions, tables, override_count):
    tally = {name: 0 for name in RESULTS}
    for _, result in decisions:
        tally[result] += 1
    doc = {
        "active": len(tables["locks"]),
        "allows": tally["allow"],
        "banned": len(tables["bans"]),
        "bans": tally["ban"],
        "conflicting": counts["conflicting"],
        "denies": tally["deny"],
        "events": len(decisions),
        "fails": tally["fail"],
        "ignored": tally["ignore"],
        "locks": tally["lock"],
        "malformed": counts["malformed"],
        "overrides": override_count,
        "retransmitted": counts["retransmitted"],
        "table_digest": table_digest(tables["locks"]),
        "unlocks": tally["unlock"],
    }
    return json.dumps(doc, sort_keys=True, indent=2) + "\n"


def load_mode(path):
    with open(path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    return manifest["mode"]


def run(in_dir, config=None):
    """Replay one intake folder and return the three report file bodies."""
    if config is None:
        config = config_from_mode(load_mode(os.path.join(in_dir, "manifest.json")))
    policy = load_policy(os.path.join(in_dir, "policy.json"))
    limits = load_overrides(os.path.join(in_dir, "overrides.csv"), config)
    seeds = load_seeds(os.path.join(in_dir, "locks.prev.json"), config)
    records, counts = screen(read_lines(os.path.join(in_dir, "attempts.jsonl")), config)

    replay = Replay(policy, limits, seeds, config)
    decisions = [(record, replay.handle(record)) for record in records]
    tables = replay.tables(records[-1]["at"] if records else None)

    return {
        "locks.json": render_locks(tables),
        "decisions.jsonl": render_decisions(decisions),
        "summary.json": render_summary(counts, decisions, tables, len(limits)),
    }


def write_reports(out_dir, reports):
    os.makedirs(out_dir, exist_ok=True)
    for name in REPORT_NAMES:
        path = os.path.join(out_dir, name)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(reports[name])


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: lockout.py IN_DIR OUT_DIR\n")
        return 2
    write_reports(argv[2], run(argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
