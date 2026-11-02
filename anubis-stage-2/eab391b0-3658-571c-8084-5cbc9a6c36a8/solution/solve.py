"""Workspace lock resolver, rebuilt from conventions.md and the worked examples."""
import csv
import hashlib
import json
import sys
from collections import deque
from pathlib import Path

INPUT_NAMES = ("index.jsonl", "workspace.json", "pins.csv", "lock.prev.json", "manifest.json")
HEX = set("0123456789abcdef")
NAME_HEAD = set("abcdefghijklmnopqrstuvwxyz")
NAME_TAIL = NAME_HEAD | set("0123456789-")
OPERATORS = (">=", "<", "=", "^", "~")
PUBLISH_FIELDS = {"seq", "pkg", "ver", "deps", "sha"}
YANK_FIELDS = {"seq", "pkg", "ver", "yank"}
BIT_WIDE_CARET = 0x02
BIT_NO_STICKY = 0x04
BIT_STACK_QUEUE = 0x08
BIT_MEMBER_PIN_SKIP = 0x10
BIT_RELAY_SEQLESS = 0x20
BIT_DEPTH_CAP = 0x40
BIT_YANK_GAP = 0x80
YANK_GAP_SPAN = 8
DEPTH_LIMIT = 3


class Version:
    """A parsed version; release candidates sort below their release."""

    __slots__ = ("major", "minor", "patch", "rc", "text")

    def __init__(self, major, minor, patch, rc, text):
        self.major, self.minor, self.patch, self.rc, self.text = major, minor, patch, rc, text

    @property
    def order(self):
        return (self.major, self.minor, self.patch, self.rc is None, self.rc or 0)

    @property
    def release(self):
        return (self.major, self.minor, self.patch)


def _number(part):
    if not part.isdigit() or not part.isascii() or (len(part) > 1 and part[0] == "0"):
        return None
    return int(part)


def read_version(text):
    if not isinstance(text, str):
        return None
    head, sep, tail = text.partition("-")
    rc = None
    if sep:
        if not tail.startswith("rc."):
            return None
        rc = _number(tail[3:])
        if rc is None:
            return None
    parts = head.split(".")
    if len(parts) != 3:
        return None
    nums = [_number(p) for p in parts]
    if None in nums:
        return None
    return Version(nums[0], nums[1], nums[2], rc, text)


def valid_name(name):
    return (isinstance(name, str) and 1 <= len(name) <= 40 and name[0] in NAME_HEAD
            and all(ch in NAME_TAIL for ch in name))


def _ceiling(op, v, wide):
    if op == "~":
        return (v.major, v.minor + 1, 0, True, 0)
    if v.major or wide:
        return (v.major + 1, 0, 0, True, 0)
    if v.minor:
        return (0, v.minor + 1, 0, True, 0)
    return (0, 0, v.patch + 1, True, 0)


class Range:
    """OR groups of AND clauses, each clause an (operator, Version) pair."""

    wide = False

    def __init__(self, groups):
        self.groups = groups

    @classmethod
    def parse(cls, text):
        if not isinstance(text, str) or text.strip() == "":
            return None
        groups = []
        for alternative in text.split("|"):
            clauses = []
            for piece in (p.strip() for p in alternative.split(",")):
                if piece == "*":
                    clauses.append(("*", None))
                    continue
                op = next((o for o in OPERATORS if piece.startswith(o)), None)
                bound = read_version(piece[len(op):].strip()) if op else None
                if bound is None:
                    return None
                clauses.append((op, bound))
            groups.append(clauses)
        return cls(groups)

    @classmethod
    def _meets(cls, op, bound, v):
        if op == "*":
            return True
        if op == "=":
            return v.order == bound.order
        if op == ">=":
            return v.order >= bound.order
        if op == "<":
            return v.order < bound.order
        return bound.order <= v.order < _ceiling(op, bound, cls.wide)

    def admits(self, v):
        for clauses in self.groups:
            if not all(self._meets(op, b, v) for op, b in clauses):
                continue
            if v.rc is None or any(b is not None and b.rc is not None and b.release == v.release
                                   for _, b in clauses):
                return True
        return False


def classify(record):
    if not isinstance(record, dict):
        return None
    seq = record.get("seq")
    if type(seq) is not int or seq < 1 or not valid_name(record.get("pkg")):
        return None
    if read_version(record.get("ver")) is None:
        return None
    fields = set(record)
    if fields == YANK_FIELDS:
        return "yank" if record["yank"] is True else None
    if fields != PUBLISH_FIELDS:
        return None
    sha, deps = record["sha"], record["deps"]
    if not (isinstance(sha, str) and len(sha) == 40 and set(sha) <= HEX):
        return None
    if not isinstance(deps, dict):
        return None
    for dep, text in deps.items():
        if dep == record["pkg"] or not valid_name(dep) or Range.parse(text) is None:
            return None
    return "publish"


class Index:
    """The screened feed: kept copies per package version and the yanks that apply."""

    def __init__(self, blob, mode):
        self.tally = dict.fromkeys(("malformed", "retransmitted", "republished",
                                    "yanks_applied", "yanks_ignored"), 0)
        accepted, publishes, yanks = set(), [], []
        for line in blob.split(b"\n"):
            if line.strip() == b"":
                continue
            try:
                record = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                self.tally["malformed"] += 1
                continue
            kind = classify(record)
            if kind is None:
                self.tally["malformed"] += 1
                continue
            shown = record if not mode & BIT_RELAY_SEQLESS else {k: x for k, x in record.items() if k != "seq"}
            fingerprint = json.dumps(shown, sort_keys=True)
            if fingerprint in accepted:
                self.tally["retransmitted"] += 1
                continue
            accepted.add(fingerprint)
            (publishes if kind == "publish" else yanks).append(record)
        self.kept = {}
        for record in publishes:
            key = (record["pkg"], record["ver"])
            current = self.kept.get(key)
            if current is not None:
                self.tally["republished"] += 1
                if record["seq"] >= current["seq"]:
                    continue
            self.kept[key] = record
        self.withdrawn = set()
        gap = YANK_GAP_SPAN if mode & BIT_YANK_GAP else 0
        for record in yanks:
            key = (record["pkg"], record["ver"])
            target = self.kept.get(key)
            if target is not None and record["seq"] > target["seq"] + gap:
                self.withdrawn.add(key)
                self.tally["yanks_applied"] += 1
            else:
                self.tally["yanks_ignored"] += 1

    def offers(self, pkg):
        return [(read_version(ver), rec) for (name, ver), rec in self.kept.items()
                if name == pkg and (name, ver) not in self.withdrawn]


def read_pins(text):
    pins = {}
    for row in csv.DictReader(text.splitlines()):
        pkg = (row.get("pkg") or "").strip()
        rule = Range.parse(row.get("range") or "")
        if valid_name(pkg) and rule is not None and pkg not in pins:
            pins[pkg] = rule
    return pins


def queue_order(deps):
    return sorted(deps.items(), key=lambda item: item[0], reverse=True)


def settle(blobs):
    mode = json.loads(blobs["manifest.json"].decode("utf-8"))["mode"]
    Range.wide = bool(mode & BIT_WIDE_CARET)
    index = Index(blobs["index.jsonl"], mode)
    members = json.loads(blobs["workspace.json"].decode("utf-8"))["members"]
    pins = read_pins(blobs["pins.csv"].decode("utf-8"))
    previous = json.loads(blobs["lock.prev.json"].decode("utf-8")).get("packages", {})
    pending = deque()
    for member in members:
        pending.extend((pkg, text, "member:" + member["name"], 1) for pkg, text in queue_order(member["deps"]))
    lock, records, sticky = {}, [], 0
    while pending:
        pkg, text, requester, depth = pending.pop() if mode & BIT_STACK_QUEUE else pending.popleft()
        wanted = Range.parse(text)
        if pkg in lock:
            held = read_version(lock[pkg]["version"])
            if not wanted.admits(held):
                records.append({"by": requester, "kind": "conflict", "picked": held.text,
                                "pkg": pkg, "range": text})
            continue
        pin = None if mode & BIT_MEMBER_PIN_SKIP and requester.startswith("member:") else pins.get(pkg)
        options = [(v, rec) for v, rec in index.offers(pkg)
                   if wanted.admits(v) and (pin is None or pin.admits(v))]
        if not options:
            records.append({"by": requester, "kind": "unresolved", "pkg": pkg, "range": text})
            continue
        prior = previous.get(pkg)
        chosen = None
        if isinstance(prior, dict) and not mode & BIT_NO_STICKY:
            chosen = next((rec for v, rec in options
                           if rec["ver"] == prior.get("version") and rec["sha"] == prior.get("sha")), None)
        if chosen is None:
            chosen = max(options, key=lambda pair: pair[0].order)[1]
        else:
            sticky += 1
        lock[pkg] = {"sha": chosen["sha"], "version": chosen["ver"], "via": requester}
        if mode & BIT_DEPTH_CAP and depth >= DEPTH_LIMIT:
            continue
        source = pkg + "@" + chosen["ver"]
        pending.extend((dep, rule, source, depth + 1) for dep, rule in queue_order(chosen["deps"]))
    lines = "".join(f"{pkg}@{lock[pkg]['version']}:{lock[pkg]['sha']}\n" for pkg in sorted(lock))
    summary = dict(index.tally)
    summary["picked"] = len(lock)
    summary["sticky"] = sticky
    summary["conflicts"] = sum(r["kind"] == "conflict" for r in records)
    summary["unresolved"] = sum(r["kind"] == "unresolved" for r in records)
    summary["pins"] = len(pins)
    summary["lock_digest"] = hashlib.sha256(lines.encode("utf-8")).hexdigest()
    return {
        "lock.json": json.dumps({"packages": lock}, indent=2, sort_keys=True) + "\n",
        "issues.jsonl": "".join(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n" for r in records),
        "summary.json": json.dumps(summary, indent=2, sort_keys=True) + "\n",
    }


def main(args):
    if len(args) != 2:
        print("usage: lockres.py IN_DIR OUT_DIR", file=sys.stderr)
        return 2
    source, target = Path(args[0]), Path(args[1])
    blobs = {name: (source / name).read_bytes() for name in INPUT_NAMES}
    target.mkdir(parents=True, exist_ok=True)
    for name, text in settle(blobs).items():
        (target / name).write_bytes(text.encode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
