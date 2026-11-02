import ast
import hashlib
import io
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import tokenize
from pathlib import Path

from rewardkit import criteria, criterion


# Harness core: corpus generation and the reference resolver.
REFERENCE = {"u1": "at", "u2": "through", "u3": "first", "u4": "deny", "u5": "escalate", "u6": "kind"}
WRONG_READINGS = {"u1": ("after",), "u2": ("before",), "u3": ("last",), "u4": ("clear",), "u5": ("fixed",), "u6": ("seq",)}
REPORTS = ("locks.json", "decisions.jsonl", "summary.json")
INPUTS = ("attempts.jsonl", "policy.json", "overrides.csv", "locks.prev.json", "manifest.json")

PREV_IGNORED = 0x02
OVERRIDES_IGNORED = 0x04
PASS_RESETS = 0x08
SOURCE_BAN = 0x10
RELAY_SEQLESS = 0x20
PROBE_COUNTS = 0x40
LOCK_SLIDES = 0x80
MODE_BITS = (PREV_IGNORED, OVERRIDES_IGNORED, PASS_RESETS, SOURCE_BAN, RELAY_SEQLESS, PROBE_COUNTS, LOCK_SLIDES)
KIND_RANK = {"reset": 0, "pass": 1, "fail": 2, "probe": 3}

USER_RE = re.compile(r"^[a-z][a-z0-9._-]{0,30}$")
AGENT_RE = re.compile(r"^[A-Za-z0-9/._-]{1,40}$")
LIMIT_RE = re.compile(r"^[1-9]$")
EVENT_KEYS = {"seq", "kind", "user", "src", "at", "agent"}


def ip_num(text):
    if not isinstance(text, str):
        return None
    parts = text.split(".")
    if len(parts) != 4:
        return None
    n = 0
    for p in parts:
        if not p.isdigit() or not p.isascii() or (len(p) > 1 and p[0] == "0") or int(p) > 255:
            return None
        n = n * 256 + int(p)
    return n


def ip_text(n):
    return ".".join(str((n >> s) & 255) for s in (24, 16, 8, 0))


def _strict_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def check_event(rec):
    if not isinstance(rec, dict) or set(rec) != EVENT_KEYS:
        return False
    if not _strict_int(rec["seq"]) or rec["seq"] < 1:
        return False
    if rec["kind"] not in KIND_RANK:
        return False
    if not isinstance(rec["user"], str) or not USER_RE.fullmatch(rec["user"]):
        return False
    if ip_num(rec["src"]) is None:
        return False
    if not _strict_int(rec["at"]) or rec["at"] < 0:
        return False
    return rec["agent"] is None or (isinstance(rec["agent"], str) and AGENT_RE.fullmatch(rec["agent"]) is not None)


def screen(blob, eff):
    counts = {"malformed": 0, "retransmitted": 0, "conflicting": 0}
    seen = set()
    by_seq = {}
    for raw in blob.split(b"\n"):
        if not raw.strip():
            continue
        try:
            rec = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            counts["malformed"] += 1
            continue
        if not check_event(rec):
            counts["malformed"] += 1
            continue
        body = dict(rec)
        if eff & RELAY_SEQLESS:
            body.pop("seq")
        fp = json.dumps(body, sort_keys=True)
        if fp in seen:
            counts["retransmitted"] += 1
            continue
        seen.add(fp)
        if rec["seq"] in by_seq:
            counts["conflicting"] += 1
            continue
        by_seq[rec["seq"]] = rec
    return list(by_seq.values()), counts


def read_policy(blob):
    doc = json.loads(blob.decode("utf-8"))
    return {k: doc[k] for k in ("window", "threshold", "lock", "ban_after", "ban")}


def read_overrides(text, variant):
    out = {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "user,limit,note":
        return out
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) != 3 or not USER_RE.fullmatch(parts[0]) or not LIMIT_RE.fullmatch(parts[1]):
            continue
        if variant["u3"] == "first":
            out.setdefault(parts[0], int(parts[1]))
        else:
            out[parts[0]] = int(parts[1])
    return out


def read_prev(blob):
    doc = json.loads(blob.decode("utf-8"))
    out = []
    for row in doc.get("locks", []):
        if not isinstance(row, dict) or not isinstance(row.get("user"), str) or not USER_RE.fullmatch(row["user"]):
            continue
        if not _strict_int(row.get("until")) or not _strict_int(row.get("strikes")) or row["strikes"] < 1:
            continue
        out.append((row["user"], row["until"], row["strikes"]))
    return out


class Account:
    def __init__(self):
        self.fails = []
        self.until = None
        self.strikes = 0
        self.length = 0


class State:
    def __init__(self, policy, limits, variant, eff):
        self.policy, self.limits, self.variant, self.eff = policy, limits, variant, eff
        self.users = {}
        self.src_fails = {}
        self.bans = {}

    def account(self, user):
        if user not in self.users:
            self.users[user] = Account()
        return self.users[user]

    def counts(self, f, t):
        w = self.policy["window"]
        return t - f <= w if self.variant["u2"] == "through" else t - f < w

    def locked(self, acct, t):
        if acct.until is None:
            return False
        return t < acct.until if self.variant["u1"] == "at" else t <= acct.until

    def lock_length(self, strikes):
        if self.variant["u5"] == "escalate":
            return self.policy["lock"] * 2 ** (strikes - 1)
        return self.policy["lock"]

    def limit(self, user):
        if not self.eff & OVERRIDES_IGNORED and user in self.limits:
            return self.limits[user]
        return self.policy["threshold"]

    def user_fail(self, user, t):
        acct = self.account(user)
        if self.locked(acct, t):
            if self.eff & LOCK_SLIDES:
                acct.until = t + acct.length
            return "deny"
        acct.fails = [f for f in acct.fails if self.counts(f, t)] + [t]
        n, lim = len(acct.fails), self.limit(user)
        if n >= lim:
            acct.strikes += 1
            acct.length = self.lock_length(acct.strikes)
            acct.until = t + acct.length
            acct.fails = []
            return "lock"
        return "fail"

    def src_fail(self, src, t, result):
        if not self.eff & SOURCE_BAN:
            return result
        hits = [f for f in self.src_fails.get(src, []) if self.counts(f, t)] + [t]
        if len(hits) >= self.policy["ban_after"]:
            self.bans[src] = t + self.policy["ban"]
            hits = []
            result = "ban"
        self.src_fails[src] = hits
        return result

    def apply(self, ev):
        t, user, kind, src = ev["at"], ev["user"], ev["kind"], ev["src"]
        if kind == "reset":
            acct = self.account(user)
            was = self.locked(acct, t)
            acct.fails = []
            acct.until = None
            return "unlock" if was else "ignore"
        if self.eff & SOURCE_BAN and src in self.bans and t < self.bans[src]:
            return "deny"
        if kind == "probe" and not self.eff & PROBE_COUNTS:
            return self.src_fail(src, t, "ignore")
        if kind in ("fail", "probe"):
            return self.src_fail(src, t, self.user_fail(user, t))
        acct = self.account(user)
        if self.locked(acct, t):
            if self.variant["u4"] == "deny":
                return "deny"
            acct.until = None
            acct.fails = []
            return "allow"
        if self.eff & PASS_RESETS:
            acct.fails = []
        return "allow"


def resolve(files, variant=None):
    variant = dict(REFERENCE if variant is None else variant)
    mode = json.loads(files["manifest.json"].decode("utf-8")).get("mode", 0)
    eff = mode & ~variant.get("blind", 0)
    events, counts = screen(files["attempts.jsonl"], eff)
    policy = read_policy(files["policy.json"])
    limits = read_overrides(files["overrides.csv"].decode("utf-8"), variant)
    st = State(policy, limits, variant, eff)
    if not eff & PREV_IGNORED:
        for user, until, strikes in read_prev(files["locks.prev.json"]):
            if user not in st.users:
                acct = st.account(user)
                acct.until, acct.strikes, acct.length = until, strikes, st.lock_length(strikes)
    if variant["u6"] == "kind":
        events.sort(key=lambda e: (e["at"], KIND_RANK[e["kind"]], e["seq"]))
    else:
        events.sort(key=lambda e: (e["at"], e["seq"]))
    log = []
    tally = {}
    for ev in events:
        result = st.apply(ev)
        tally[result] = tally.get(result, 0) + 1
        log.append({"at": ev["at"], "seq": ev["seq"], "user": ev["user"], "src": ev["src"], "kind": ev["kind"],
                    "result": result})
    last = events[-1]["at"] if events else 0
    return render(st, log, tally, counts, len(limits), last)


def lock_lines(locks):
    return "".join(sorted("%s %d\n" % (u, row["until"]) for u, row in locks.items()))


def ban_lines(bans):
    return "".join(sorted("%s %d\n" % (s, row["until"]) for s, row in bans.items()))


def render(st, log, tally, counts, n_overrides, last):
    locks = {u: {"strikes": a.strikes, "until": a.until} for u, a in st.users.items() if st.locked(a, last)}
    bans = {s: {"until": e} for s, e in st.bans.items() if last < e}
    summary = dict(counts)
    summary.update({
        "events": len(log),
        "allows": tally.get("allow", 0),
        "fails": tally.get("fail", 0),
        "locks": tally.get("lock", 0),
        "denies": tally.get("deny", 0),
        "unlocks": tally.get("unlock", 0),
        "bans": tally.get("ban", 0),
        "ignored": tally.get("ignore", 0),
        "active": len(locks),
        "banned": len(bans),
        "overrides": n_overrides,
        "table_digest": hashlib.sha256(lock_lines(locks).encode()).hexdigest(),
    })
    return {
        "locks.json": json.dumps({"bans": bans, "locks": locks}, sort_keys=True, indent=2) + "\n",
        "decisions.jsonl": "".join(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n" for r in log),
        "summary.json": json.dumps(summary, sort_keys=True, indent=2) + "\n",
    }


def table_digests(locks_text):
    doc = json.loads(locks_text)
    return {"bans": hashlib.sha256(ban_lines(doc["bans"]).encode()).hexdigest(),
            "locks": hashlib.sha256(lock_lines(doc["locks"]).encode()).hexdigest()}


def manifest(mode, reports):
    doc = {"mode": mode, "reports": {n: hashlib.sha256(t.encode()).hexdigest() for n, t in reports.items()},
           "tables": table_digests(reports["locks.json"])}
    return (json.dumps(doc, sort_keys=True, indent=2) + "\n").encode()


class Rng:
    """splitmix64, so corpora do not depend on the random module."""

    def __init__(self, seed):
        self.state = seed & 0xFFFFFFFFFFFFFFFF

    def next(self):
        self.state = (self.state + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        return z ^ (z >> 31)

    def below(self, n):
        return self.next() % n

    def between(self, lo, hi):
        return lo + self.below(hi - lo + 1)

    def pick(self, items):
        return items[self.below(len(items))]

    def shuffle(self, items):
        items = list(items)
        for i in range(len(items) - 1, 0, -1):
            j = self.below(i + 1)
            items[i], items[j] = items[j], items[i]
        return items


NAMES = ["ana", "bo", "chen", "dara", "eli", "fern", "gus", "hana", "ivo", "jun", "kai", "lena", "milo", "nia",
         "omar", "pia", "quin", "rosa", "sami", "tess", "uma", "vik", "wren", "yara", "zeke"]
AGENTS = ["ssh/9.6", "imap.v2", "vpn-gw", "web/4.1", "sftp", "rdp/10"]
STEPS = (0, 0, 0, 60, 60, 60, 120, 180, 240, 300)
KINDS = ("fail", "fail", "fail", "fail", "fail", "pass", "pass", "pass", "reset", "probe", "probe")
NOISE = ("truncated", "array", "missing", "extra", "strseq", "boolseq", "zeroseq", "badkind", "baduser",
         "badsrc", "zerosrc", "negat", "floatat", "badagent", "numuser")


def _noise(kind, rec):
    r = dict(rec)
    if kind == "truncated":
        return json.dumps(r, sort_keys=True)[:-6]
    if kind == "array":
        return json.dumps([r["user"], r["at"]])
    if kind == "missing":
        r.pop("agent")
    elif kind == "extra":
        r["tries"] = 3
    elif kind == "strseq":
        r["seq"] = str(r["seq"])
    elif kind == "boolseq":
        r["seq"] = True
    elif kind == "zeroseq":
        r["seq"] = 0
    elif kind == "badkind":
        r["kind"] = "lookup"
    elif kind == "baduser":
        r["user"] = r["user"].capitalize()
    elif kind == "badsrc":
        r["src"] = "10.0.300.1"
    elif kind == "zerosrc":
        r["src"] = "10.020.0.1"
    elif kind == "negat":
        r["at"] = -r["at"] - 1
    elif kind == "floatat":
        r["at"] = float(r["at"])
    elif kind == "badagent":
        r["agent"] = "curl 8.5"
    elif kind == "numuser":
        r["user"] = "9" + r["user"]
    return json.dumps(r, sort_keys=bool(rec["seq"] % 2))


def build_corpus(seed, traps=(), clients=8, count=30, noise=True, mode=0, relay=True, kinds=KINDS):
    rng = Rng(seed)
    users = rng.shuffle(NAMES)[:clients]
    base = 10 * 2 ** 24 + rng.between(1, 200) * 2 ** 16 + rng.between(0, 255) * 256
    srcs = [ip_text(base + rng.between(2, 250)) for _ in range(max(2, clients // 2))]
    srcs = sorted(set(srcs))
    home = {u: rng.pick(srcs) for u in users}
    policy = {"window": rng.pick((180, 240, 300)), "threshold": rng.pick((2, 3)), "lock": rng.pick((600, 900, 1200, 1800)),
              "ban_after": rng.pick((4, 5)), "ban": rng.pick((1800, 2700, 3600))}
    t = rng.between(1000, 5000) // 60 * 60
    recs = []
    user = rng.pick(users)
    for _ in range(count):
        t += rng.pick(STEPS)
        if rng.below(2):
            user = rng.pick(users)
        kind = rng.pick(kinds)
        src = home[user] if rng.below(3) else rng.pick(srcs)
        agent = rng.pick(AGENTS) if rng.below(4) else None
        recs.append({"kind": kind, "user": user, "src": src, "at": t, "agent": agent})
    lines = [dict(r) for r in recs]
    if relay and mode & RELAY_SEQLESS:
        for r in rng.shuffle(recs)[: rng.between(2, 4)]:
            lines.append(dict(r))
    lines = rng.shuffle(lines)
    seqs = rng.shuffle(list(range(1, len(lines) + 1)))
    for r, s in zip(lines, seqs):
        r["seq"] = s
    out = [json.dumps(r, sort_keys=bool(rng.below(2))) for r in lines]
    if noise:
        for _ in range(rng.between(3, 6)):
            k = rng.below(len(out))
            out.insert(k + 1, out[k])
        for _ in range(rng.between(1, 3)):
            c = dict(rng.pick(lines))
            c["at"] = c["at"] + rng.pick((60, 120))
            out.insert(rng.below(len(out) + 1), json.dumps(c, sort_keys=True))
        for kind in rng.shuffle(NOISE)[: rng.between(7, 11)]:
            out.insert(rng.below(len(out) + 1), _noise(kind, rng.pick(lines)))
        out.insert(rng.below(len(out) + 1), "")
        out.insert(rng.below(len(out) + 1), "collector restarted, journal resumes below")
    blob = ("\n".join(out) + "\n").encode("utf-8")
    rows = ["user,limit,note"]
    for u in rng.shuffle(users)[: rng.between(1, 3)]:
        rows.append("%s,%d,%s" % (u, rng.between(1, 4), rng.pick(("service", "kiosk", "vip"))))
        if "u3" in traps and rng.below(2):
            rows.append("%s,%d,%s" % (u, rng.between(1, 4), "raised"))
    if noise:
        rows.append("%s,%d,typo" % (users[0].capitalize(), 2))
        rows.append("%s,0,disabled" % rng.pick(users))
        rows.append("%s,%d" % (rng.pick(users), 3))
    prev = []
    for u in rng.shuffle(users)[: rng.between(0, 3)]:
        prev.append({"user": u, "until": recs[0]["at"] + rng.pick((0, 60, 120, 300, 600)), "strikes": rng.between(1, 2)})
    if noise and prev:
        prev.append({"user": rng.pick(users), "until": recs[0]["at"] + 900, "strikes": 0})
    files = {"attempts.jsonl": blob,
             "policy.json": (json.dumps(policy, indent=2) + "\n").encode(),
             "overrides.csv": ("\n".join(rows) + "\n").encode(),
             "locks.prev.json": (json.dumps({"locks": prev}, sort_keys=True, indent=2) + "\n").encode(),
             "manifest.json": json.dumps({"mode": mode}).encode()}
    files["manifest.json"] = manifest(mode, resolve(files))
    return files


def flipped(rule, reading):
    v = dict(REFERENCE)
    v[rule] = reading
    return v


def separation(files):
    ref = resolve(files)
    return {(r, x) for r, xs in WRONG_READINGS.items() for x in xs if resolve(files, flipped(r, x)) != ref}


def bit_moves(files):
    ref = resolve(files)
    out = set()
    for bit in MODE_BITS:
        v = dict(REFERENCE)
        v["blind"] = bit
        if resolve(files, v) != ref:
            out.add(bit)
    return out


def _search(start, step, tries, build, accept):
    for attempt in range(tries):
        files = build(start + attempt * step)
        if accept(files):
            return files
    raise RuntimeError("no case found")


def _all_readings(rule):
    return {(rule, x) for x in WRONG_READINGS[rule]}


def isolated_case(seed, rule, wanted=None):
    """A clean mode zero journal where only the readings of one rule change the reports."""
    wanted = _all_readings(rule) if wanted is None else wanted
    traps = (rule,) if rule == "u3" else ()
    return _search(seed, 7919, 3000, lambda s: build_corpus(s, traps, clients=3 + s % 4, count=8 + s % 8, noise=False),
                   lambda f: separation(f) == wanted)


def plain_case(seed):
    """A clean mode zero journal that no rule reading moves."""
    return _search(seed, 104729, 3000, lambda s: build_corpus(s, (), clients=3 + s % 3, count=6 + s % 5, noise=False),
                   lambda f: not separation(f))


QUIET_KINDS = ("fail", "fail", "fail", "fail", "fail", "pass", "pass", "pass", "reset")


def effect_case(seed, bit):
    """A clean journal under mode word 254 where only the effect behind one bit moves the reports.

    Clearing any other bit, or swapping any of the six rule readings, leaves
    every report unchanged, so the case grades what the bit does and not
    which numeric bit value carries it.
    """
    kinds = KINDS if bit == PROBE_COUNTS else QUIET_KINDS
    return _search(seed, 6151, 3000,
                   lambda s: build_corpus(s, (), clients=3 + s % 4, count=8 + s % 8, noise=False, mode=0xFE,
                                          relay=bit == RELAY_SEQLESS, kinds=kinds),
                   lambda f: bit_moves(f) == {bit} and not separation(f))


def mixed_case(seed, clients=8, count=30, need=None, mode=0):
    """A noisy journal where every needed reading and every set mode bit moves the reports."""
    need = {(r, x) for r in REFERENCE for x in WRONG_READINGS[r]} if need is None else need
    bits = {b for b in MODE_BITS if mode & b}
    return _search(seed, 15485863, 3000, lambda s: build_corpus(s, ("u3",), clients=clients, count=count, mode=mode),
                   lambda f: need <= separation(f) and bit_moves(f) == bits)


def noisy_plain_case(seed):
    """A damaged mode zero journal that no rule reading moves."""
    return _search(seed, 2741, 3000, lambda s: build_corpus(s, (), clients=3 + s % 3, count=8 + s % 5, noise=True),
                   lambda f: not separation(f))


def empty_events_case(seed):
    """A journal where every line is damaged, so no event is replayed and the event file is empty."""
    files = dict(plain_case(seed))
    files["attempts.jsonl"] = b'\nauth relay restarted, journal resumes below\n{"seq": 0, "kind": "fail"}\n[1, 2]\n'
    files["locks.prev.json"] = (json.dumps({"locks": []}, sort_keys=True, indent=2) + "\n").encode()
    files["manifest.json"] = manifest(0, resolve(files))
    return files


def _with_manifest(files):
    files = dict(files)
    files["manifest.json"] = manifest(0, resolve(files))
    return files


def _boundary_lines(files):
    events, _ = screen(files["attempts.jsonl"], 0)
    top = max(e["seq"] for e in events)
    last = max(e["at"] for e in events)
    src = events[0]["src"]
    good = {"kind": "fail", "src": src, "agent": None}
    lines = [
        # Accepted: a user name of the longest allowed length, a forty character agent, a zero second.
        dict(good, seq=top + 1, user="q" + "x" * 30, at=last + 4000),
        dict(good, seq=top + 2, user="qa.b-c_9", at=last + 4060, agent="A" * 40),
        dict(good, seq=top + 3, user="qz", at=0, agent="ssh/9.6"),
        dict(good, seq=top + 4, user="qy", at=last + 4120, src="255.255.255.255"),
        # Rejected: one character too long, an empty, overlong or numeric agent, a boolean second.
        dict(good, seq=top + 5, user="q" + "x" * 31, at=last + 4180),
        dict(good, seq=top + 6, user="qw", at=last + 4240, agent=""),
        dict(good, seq=top + 7, user="qv", at=last + 4300, agent="A" * 41),
        dict(good, seq=top + 8, user="qu", at=last + 4360, agent=7),
        dict(good, seq=top + 9, user="qt", at=True),
        dict(good, seq=top + 10, user="qs", at=last + 4420, src="10.0.0.256"),
        dict(good, seq=top + 11, user="qr", at=last + 4480, kind="Fail"),
    ]
    return "".join(json.dumps(r, sort_keys=True) + "\n" for r in lines).encode()


def boundary_case(seed):
    """A clean mode zero journal with appended records that sit on each side of every field boundary."""
    def build(s):
        files = dict(plain_case(s))
        files["attempts.jsonl"] = files["attempts.jsonl"] + _boundary_lines(files)
        return _with_manifest(files)
    return _search(seed, 7907, 40, build, lambda f: not separation(f))


def _prev_rows(files):
    events, _ = screen(files["attempts.jsonl"], 0)
    users = sorted({e["user"] for e in events})
    first = min(e["at"] for e in events)
    late = max(e["at"] for e in events) + 7200
    who, other = users[0], users[-1]
    rows = [
        {"user": who, "until": first + 120, "strikes": 1},
        # A second row for an already seeded user is skipped.
        {"user": who, "until": late, "strikes": 3},
        {"user": other.capitalize(), "until": late, "strikes": 2},
        {"user": "9" + other, "until": late, "strikes": 2},
        {"user": other, "until": str(late), "strikes": 2},
        {"user": other, "until": float(late), "strikes": 2},
        {"user": other, "until": late, "strikes": True},
        {"user": other, "until": late, "strikes": "2"},
        {"user": other, "until": late, "strikes": 0},
        {"user": other, "until": late, "strikes": 2.0},
    ]
    # What a lenient reader would make of each skipped row (index 1 is the repeat).
    lenient = {
        1: [rows[1]] + rows[2:],
        2: dict(rows[2], user=other),
        # A reader that strips the stray leading digit would seed the user it names.
        3: dict(rows[3], user=other),
        4: dict(rows[4], until=late),
        5: dict(rows[5], until=late),
        6: dict(rows[6], strikes=1),
        7: dict(rows[7], strikes=2),
        8: dict(rows[8], strikes=1),
        9: dict(rows[9], strikes=2),
    }
    return rows, lenient


def _prev_blob(rows):
    return (json.dumps({"locks": rows}, sort_keys=True, indent=2) + "\n").encode()


def prev_rows_case(seed):
    """A clean mode zero journal whose previous table mixes one usable row with rows that must be skipped.

    The search keeps a journal where taking the second row for the seeded user,
    or accepting any one skipped row the way a lenient reader would, changes the reports.
    """
    def build(s):
        files = dict(plain_case(s))
        rows, _ = _prev_rows(files)
        files["locks.prev.json"] = _prev_blob(rows)
        return _with_manifest(files)

    def accept(files):
        if separation(files):
            return False
        ref = resolve(files)
        rows, lenient = _prev_rows(files)
        for i, alt in lenient.items():
            table = alt if i == 1 else rows[:1] + [alt] + rows[i + 1:]
            trial = dict(files)
            trial["locks.prev.json"] = _prev_blob(table)
            if resolve(trial) == ref:
                return False
        return True
    return _search(seed, 7919, 400, build, accept)


def live_journal_ok(files):
    """The shipped live journal: every bit moves it and at least three locks, one ban and one conflict survive."""
    if bit_moves(files) != set(MODE_BITS) or not _MODE_NEED <= separation(files):
        return False
    summary = json.loads(resolve(files)["summary.json"])
    return summary["active"] >= 3 and summary["banned"] >= 1 and summary["conflicting"] >= 1


def live_journal_case(seed):
    return _search(seed, 15485863, 6000, lambda s: build_corpus(s, ("u3",), clients=10, count=44, mode=0xFE), live_journal_ok)


SHIPPED_SEED = 8750233513784853266 ^ 15
EXAMPLE_SEED = 8750233513784853266 ^ 1
SECOND_EXAMPLE_SEED = 8750233513784853266 ^ 2
# Only the shipped live journal search uses this; no graded case depends on it.
_MODE_NEED = {("u4", "clear"), ("u6", "seq")}
CASES = {
    "plain": lambda: plain_case(0x51A7E0001),
    "noisy-plain": lambda: noisy_plain_case(0x51A7E0002),
    "screen": lambda: mixed_case(0x3A1E00007, clients=6, count=22),
    "iso-u1": lambda: isolated_case(0x1D0000001, "u1"),
    "iso-u2": lambda: isolated_case(0x1D0000002, "u2"),
    "iso-u3": lambda: isolated_case(0x1D0000003, "u3"),
    "iso-u4": lambda: isolated_case(0x1D0000004, "u4"),
    "iso-u5": lambda: isolated_case(0x1D0000005, "u5"),
    "iso-u6": lambda: isolated_case(0x1D0000006, "u6"),
    "mixed-a": lambda: mixed_case(0x3A1E00001, clients=6, count=24),
    "thousand": lambda: build_corpus(0x7A0000001, ("u3",), clients=40, count=960),
    "mode-alpha": lambda: mixed_case(0x3A1E00011, clients=8, count=30, need=set(), mode=0xFE),
    "effect-02": lambda: effect_case(0xEFF000 + PREV_IGNORED * 1000, PREV_IGNORED),
    "effect-04": lambda: effect_case(0xEFF000 + OVERRIDES_IGNORED * 1000, OVERRIDES_IGNORED),
    "effect-08": lambda: effect_case(0xEFF000 + PASS_RESETS * 1000, PASS_RESETS),
    "effect-10": lambda: effect_case(0xEFF000 + SOURCE_BAN * 1000, SOURCE_BAN),
    "effect-20": lambda: effect_case(0xEFF000 + RELAY_SEQLESS * 1000, RELAY_SEQLESS),
    "effect-40": lambda: effect_case(0xEFF000 + PROBE_COUNTS * 1000, PROBE_COUNTS),
    "effect-80": lambda: effect_case(0xEFF000 + LOCK_SLIDES * 1000, LOCK_SLIDES),
    "boundary": lambda: boundary_case(0x51A7E0101),
    "prev-rows": lambda: prev_rows_case(0x51A7E0201),
    "empty": lambda: empty_events_case(0x0E0000001),
    "stale": lambda: mixed_case(0x3A1E00004, clients=5, count=20),
    "repeat": lambda: mixed_case(0x3A1E00005, clients=5, count=20),
    "untouched": lambda: mixed_case(0x3A1E00006, clients=5, count=20),
}
_FILES = {}
_TMP_ROOT = os.path.realpath(tempfile.gettempdir())
_RUNS = {}
# Each launch gets at most _RUN_BUDGET seconds, and all launches together share
# _TOTAL_BUDGET seconds, so a hanging delivery cannot outlast the verifier.
_RUN_BUDGET = 90
_TOTAL_BUDGET = 2200
_DEADLINE = time.monotonic() + _TOTAL_BUDGET
_STALE = {
    "locks.json": '{"bans": {}, "locks": {"zed": {"strikes": 1, "until": 1}}}\n',
    "decisions.jsonl": '{"at":0,"kind":"fail","result":"lock","seq":1,"src":"10.0.0.1","user":"zed"}\n',
    "summary.json": '{"locks": 99}\n',
}


def _case(label):
    if label not in _FILES:
        _FILES[label] = CASES[label]()
    return _FILES[label]


def _script(workspace):
    return os.path.join(str(workspace), "out", "lockout.py")


def _inside_sandbox(path):
    resolved = os.path.realpath(path)
    return resolved != _TMP_ROOT and resolved.startswith(_TMP_ROOT + os.sep)


def _open_up(path):
    node = os.path.realpath(path)
    while _inside_sandbox(node):
        try:
            os.chmod(node, (os.stat(node).st_mode & 0o7777) | 0o111 | 0o044)
        except OSError:
            pass
        node = os.path.dirname(node)


def _grant_read(path):
    # A directory needs its search bit as well as its read bit, or the
    # unprivileged runner cannot traverse into it to open the program.
    extra = 0o044 | (0o011 if os.path.isdir(path) else 0o000)
    try:
        os.chmod(path, (os.stat(path).st_mode & 0o7777) | extra)
    except OSError:
        pass


def _demoted(argv):
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups", "--"] + argv
    return argv


def _terminate(proc):
    # start_new_session makes the child its own group leader, so its pid is the pgid.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, AttributeError):
        pass
    try:
        proc.kill()
    except OSError:
        pass
    try:
        proc.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _launch(argv, scratch, budget=_RUN_BUDGET):
    """Run the delivered program demoted; returns its exit code, or None on timeout."""
    budget = min(budget, _DEADLINE - time.monotonic())
    if budget <= 0:
        return None
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": scratch,
        "TMPDIR": scratch,
        "LC_ALL": "C",
    }
    with open(os.path.join(scratch, "stdout.txt"), "wb") as sink, open(os.path.join(scratch, "stderr.txt"), "wb") as errsink:
        proc = subprocess.Popen(
            _demoted(argv),
            stdout=sink,
            stderr=errsink,
            stdin=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        try:
            code = proc.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            code = None
        _terminate(proc)
        return code


def _tree_digest(root):
    hasher = hashlib.sha256()
    for base, dirs, files in sorted(os.walk(root)):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(base, name)
            hasher.update(os.path.relpath(path, root).encode("utf-8") + b"\0")
            with open(path, "rb") as handle:
                hasher.update(handle.read() + b"\0")
    return hasher.hexdigest()


def _run(workspace, label, prefill=False, budget=_RUN_BUDGET):
    key = (str(workspace), label)
    if key in _RUNS:
        return _RUNS[key]
    script = _script(workspace)
    if not os.path.isfile(script):
        return None
    _open_up(script)
    _grant_read(os.path.dirname(script))
    _grant_read(script)
    work = tempfile.mkdtemp(prefix="llr-" + label + "-")
    data = os.path.join(work, "data")
    out = os.path.join(work, "out")
    scratch = os.path.join(work, "scratch")
    for node in (data, out, scratch):
        os.makedirs(node)
    for name, body in _case(label).items():
        with open(os.path.join(data, name), "wb") as handle:
            handle.write(body)
        os.chmod(os.path.join(data, name), 0o644)
    if prefill:
        for name, body in _STALE.items():
            with open(os.path.join(out, name), "w", encoding="utf-8") as handle:
                handle.write(body)
            os.chmod(os.path.join(out, name), 0o666)
    for node in (work, data, out, scratch):
        os.chmod(node, 0o777)
    before = _tree_digest(data)
    code = _launch([sys.executable, script, data, out], scratch, budget)
    _RUNS[key] = (data, out, scratch, code, before)
    return _RUNS[key]


def _artifact(out, name):
    path = os.path.join(out, name)
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as handle:
        return handle.read()


def _report_matches(workspace, label, names=REPORTS, prefill=False, budget=_RUN_BUDGET):
    """True when the program exits 0 and writes the named reports byte for byte."""
    try:
        run = _run(workspace, label, prefill, budget)
        if run is None or run[3] != 0:
            return False
        expected = resolve(_case(label))
        return all(_artifact(run[1], name) == expected[name].encode("utf-8") for name in names)
    except Exception:
        return False


def _delivered_source(workspace):
    script = _script(workspace)
    if not os.path.isfile(script):
        return None
    _grant_read(script)
    with open(script, "rb") as handle:
        return handle.read().decode("utf-8", "replace")


@criterion(description="the lockout program exists at out/lockout.py under the workspace and exits 0 on a fresh journal")
def program_is_delivered(workspace: Path) -> bool:
    try:
        run = _run(workspace, "plain")
        return run is not None and run[3] == 0
    except Exception:
        return False


@criterion(description="on a clean fresh journal with no undocumented rule in play the lock table matches byte for byte")
def plain_journal_locks_match(workspace: Path) -> bool:
    return _report_matches(workspace, "plain", ("locks.json",))


@criterion(description="on a clean fresh journal with no undocumented rule in play the decision file matches byte for byte")
def plain_journal_decisions_match(workspace: Path) -> bool:
    return _report_matches(workspace, "plain", ("decisions.jsonl",))


@criterion(description="on a clean fresh journal with no undocumented rule in play the summary matches byte for byte")
def plain_journal_summary_matches(workspace: Path) -> bool:
    return _report_matches(workspace, "plain", ("summary.json",))


@criterion(description="on a fresh journal with damaged, repeated and conflicting lines the summary screening counts match")
def screening_counts_match(workspace: Path) -> bool:
    try:
        run = _run(workspace, "screen")
        if run is None or run[3] != 0:
            return False
        got = json.loads((_artifact(run[1], "summary.json") or b"{}").decode("utf-8"))
        want = json.loads(resolve(_case("screen"))["summary.json"])
        return isinstance(got, dict) and all(got.get(k) == want[k] for k in ("malformed", "retransmitted", "conflicting"))
    except Exception:
        return False


@criterion(description="on a fresh journal with damaged, repeated and conflicting lines all three reports match byte for byte")
def screened_journal_replays(workspace: Path) -> bool:
    return _report_matches(workspace, "noisy-plain")


@criterion(description="a journal where only the second a lock ends matters replays byte for byte")
def lock_end_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u1")


@criterion(description="a journal where only a failure exactly one window old matters replays byte for byte")
def window_edge_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u2")


@criterion(description="a journal where only the choice between duplicate override rows matters replays byte for byte")
def duplicate_override_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u3")


@criterion(description="a journal where only a correct password from a locked user matters replays byte for byte")
def locked_pass_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u4")


@criterion(description="a journal where only the length of a repeat lock matters replays byte for byte")
def repeat_lock_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u5")


@criterion(description="a journal where only the order of events within one second matters replays byte for byte")
def same_second_order_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u6")


@criterion(description="a fresh screened journal where every undocumented rule matters replays byte for byte")
def mixed_journal_alpha_replays(workspace: Path) -> bool:
    return _report_matches(workspace, "mixed-a")


@criterion(description="the table digest in the summary agrees with the lock table the same run wrote")
def table_digest_agrees_with_locks(workspace: Path) -> bool:
    try:
        run = _run(workspace, "mixed-a")
        if run is None or run[3] != 0:
            return False
        table = json.loads((_artifact(run[1], "locks.json") or b"{}").decode("utf-8"))
        summary = json.loads((_artifact(run[1], "summary.json") or b"{}").decode("utf-8"))
        locks = table.get("locks")
        if not isinstance(locks, dict) or not locks:
            return False
        text = "".join(sorted("%s %d\n" % (user, row["until"]) for user, row in locks.items()))
        return summary.get("table_digest") == hashlib.sha256(text.encode("utf-8")).hexdigest()
    except Exception:
        return False


@criterion(description="a journal whose every line is damaged still gets an empty decision file and matching locks and summary")
def empty_outputs_written(workspace: Path) -> bool:
    return _report_matches(workspace, "empty")


@criterion(description="reports left in the output folder by an earlier run are replaced by the fresh reports byte for byte")
def stale_outputs_replaced(workspace: Path) -> bool:
    return _report_matches(workspace, "stale", prefill=True)


@criterion(description="a fresh screened journal of about a thousand lines replays byte for byte within sixty seconds")
def thousand_line_journal_replays(workspace: Path) -> bool:
    return _report_matches(workspace, "thousand", budget=60)


@criterion(description="a fresh journal with records on each side of the user, agent, source and second boundaries replays byte for byte")
def journal_boundary_records_screened(workspace: Path) -> bool:
    return _report_matches(workspace, "boundary")


@criterion(description="a previous table with a repeated user and rows of the wrong shape seeds only its first usable rows")
def previous_table_rows_screened(workspace: Path) -> bool:
    return _report_matches(workspace, "prev-rows")


@criterion(description="a fresh screened journal under mode word 254 replays byte for byte")
def mode_word_alpha_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "mode-alpha")


@criterion(description="under mode word 254, a journal where only skipping the previous lock table matters replays byte for byte")
def mode_effect_previous_table_skipped(workspace: Path) -> bool:
    return _report_matches(workspace, "effect-02")


@criterion(description="under mode word 254, a journal where only ignoring the overrides file matters replays byte for byte")
def mode_effect_overrides_skipped(workspace: Path) -> bool:
    return _report_matches(workspace, "effect-04")


@criterion(description="under mode word 254, a journal where only a correct password clearing counted failures matters replays byte for byte")
def mode_effect_pass_clears_failures(workspace: Path) -> bool:
    return _report_matches(workspace, "effect-08")


@criterion(description="under mode word 254, a journal where only banning a source after repeated failures matters replays byte for byte")
def mode_effect_source_ban(workspace: Path) -> bool:
    return _report_matches(workspace, "effect-10")


@criterion(description="under mode word 254, a journal where only retransmissions that differ in seq alone matter replays byte for byte")
def mode_effect_seqless_retransmission(workspace: Path) -> bool:
    return _report_matches(workspace, "effect-20")


@criterion(description="under mode word 254, a journal where only probes counting as failures matters replays byte for byte")
def mode_effect_probe_counts(workspace: Path) -> bool:
    return _report_matches(workspace, "effect-40")


@criterion(description="under mode word 254, a journal where only a failure during a lock restarting the lock matters replays byte for byte")
def mode_effect_lock_slides(workspace: Path) -> bool:
    return _report_matches(workspace, "effect-80")


@criterion(description="the delivered program changes, adds or removes a file inside the input directory it was given")
def negative_input_folder_mutated(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        run = _run(workspace, "untouched")
        if run is None or run[3] is None:
            return False
        return _tree_digest(run[0]) != run[4]
    except Exception:
        return False


@criterion(description="the delivered program carries locked user names, banned source addresses or the table digest of a shipped journal as literals")
def negative_hardcoded_shipped_answers(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        source = _delivered_source(workspace)
        if source is None:
            return False
        answers = []
        shipped = (live_journal_case(SHIPPED_SEED), mixed_case(EXAMPLE_SEED, clients=6, count=24), mixed_case(SECOND_EXAMPLE_SEED, clients=6, count=24))
        for files in shipped:
            reports = resolve(files)
            table = json.loads(reports["locks.json"])
            marks = sorted(set(table["locks"]) | set(table["bans"]))
            answers.append((json.loads(reports["summary.json"])["table_digest"], marks))
        literals = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                literals.append(node.value)
        # Comments never reach the syntax tree, so pick them up separately.
        try:
            for tok in tokenize.generate_tokens(io.StringIO(source).readline):
                if tok.type == tokenize.COMMENT:
                    literals.append(tok.string)
        except (tokenize.TokenError, SyntaxError):
            pass
        blob = "\n".join(literals)
        # Short user names would match by accident inside longer text, so a
        # mark only counts when some literal is exactly that name or address.
        exact = set(literals)
        return any(digest in blob or (len(marks) >= 3 and sum(1 for mark in marks if mark in exact) >= 3) for digest, marks in answers)
    except Exception:
        return False


@criterion(description="the delivered program pulls in a module outside the standard library")
def negative_third_party_dependency(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        source = _delivered_source(workspace)
        if source is None:
            return False
        wanted = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                wanted.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                wanted.add(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
                if name in ("__import__", "import_module") and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        wanted.add(first.value.split(".")[0])
        return bool(wanted - set(sys.stdlib_module_names))
    except Exception:
        return False


@criterion(description="repeated runs of the delivered program over one input write differing bytes")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        run = _run(workspace, "repeat")
        if run is None or run[3] != 0:
            return False
        data, out, scratch = run[0], run[1], run[2]
        first = {name: _artifact(out, name) for name in REPORTS}
        for _attempt in range(3):
            again = _launch([sys.executable, _script(workspace), data, out], scratch)
            if again is None:
                return False
            if again != 0:
                return True
            for name, body in first.items():
                if _artifact(out, name) != body:
                    return True
        return False
    except Exception:
        return False


def _delivered_tree(workspace):
    source = _delivered_source(workspace)
    if source is None:
        return None
    try:
        return ast.parse(source)
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return None


@criterion(description="the delivered program has a bare except clause")
def negative_bare_except_present(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    tree = _delivered_tree(workspace)
    return tree is not None and any(isinstance(n, ast.ExceptHandler) and n.type is None for n in ast.walk(tree))


@criterion(description="the delivered program prints to standard output, calls breakpoint, or imports pdb")
def negative_debug_print_present(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    # A print aimed at another stream, such as a usage line on stderr, is not a debug print.
    tree = _delivered_tree(workspace)
    if tree is None:
        return False
    for n in ast.walk(tree):
        name = getattr(n.func, "id", None) if isinstance(n, ast.Call) else None
        if name == "breakpoint":
            return True
        if name == "print":
            stream = next((k.value for k in n.keywords if k.arg == "file"), None)
            if stream is None or (isinstance(stream, ast.Attribute) and stream.attr == "stdout"):
                return True
        if isinstance(n, ast.Import) and any(a.name.split(".")[0] == "pdb" for a in n.names):
            return True
        if isinstance(n, ast.ImportFrom) and (n.module or "").split(".")[0] == "pdb":
            return True
    return False


@criterion(description="the delivered program defines no named function and runs as one flat script")
def negative_no_named_functions(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    tree = _delivered_tree(workspace)
    return tree is not None and not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) for n in ast.walk(tree))


_NETWORK_MODULES = {"socket", "ssl", "http", "urllib", "ftplib", "smtplib", "telnetlib", "xmlrpc", "asyncio"}


@criterion(description="the delivered program imports a standard library module that reaches the network")
def negative_network_module_imported(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    tree = _delivered_tree(workspace)
    if tree is None:
        return False
    for n in ast.walk(tree):
        if isinstance(n, ast.Import) and any(a.name.split(".")[0] in _NETWORK_MODULES for a in n.names):
            return True
        if isinstance(n, ast.ImportFrom) and n.level == 0 and (n.module or "").split(".")[0] in _NETWORK_MODULES:
            return True
    return False


criteria.program_is_delivered(weight=1)
criteria.plain_journal_locks_match(weight=1)
criteria.plain_journal_decisions_match(weight=1)
criteria.plain_journal_summary_matches(weight=1)
criteria.screening_counts_match(weight=1)
criteria.screened_journal_replays(weight=1)
criteria.lock_end_isolated(weight=1)
criteria.window_edge_isolated(weight=1)
criteria.duplicate_override_isolated(weight=1)
criteria.locked_pass_isolated(weight=1)
criteria.repeat_lock_isolated(weight=1)
criteria.same_second_order_isolated(weight=1)
criteria.mixed_journal_alpha_replays(weight=1)
criteria.table_digest_agrees_with_locks(weight=1)
criteria.empty_outputs_written(weight=1)
criteria.stale_outputs_replaced(weight=1)
criteria.thousand_line_journal_replays(weight=1)
criteria.journal_boundary_records_screened(weight=1)
criteria.previous_table_rows_screened(weight=1)
criteria.mode_word_alpha_resolves(weight=5)
criteria.mode_effect_previous_table_skipped(weight=5)
criteria.mode_effect_overrides_skipped(weight=5)
criteria.mode_effect_pass_clears_failures(weight=5)
criteria.mode_effect_source_ban(weight=5)
criteria.mode_effect_seqless_retransmission(weight=5)
criteria.mode_effect_probe_counts(weight=5)
criteria.mode_effect_lock_slides(weight=5)
criteria.negative_input_folder_mutated(weight=-5)
criteria.negative_hardcoded_shipped_answers(weight=-5)
criteria.negative_third_party_dependency(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_bare_except_present(weight=-1)
criteria.negative_debug_print_present(weight=-1)
criteria.negative_no_named_functions(weight=-1)
criteria.negative_network_module_imported(weight=-3)
