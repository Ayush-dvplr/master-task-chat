import ast
import csv
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
from collections import deque
from pathlib import Path

from rewardkit import criteria, criterion


VER_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-rc\.(0|[1-9][0-9]*))?$")
NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
CLAUSE_OPS = (">=", "<", "=", "^", "~")
PUBLISH_KEYS = frozenset(("seq", "pkg", "ver", "deps", "sha"))
YANK_KEYS = frozenset(("seq", "pkg", "ver", "yank"))
REFERENCE = {"u1": "ref", "u2": "ref", "u3": "ref", "u4": "ref", "u5": "ref", "u6": "ref"}
WRONG_READINGS = {
    "u1": ("last", "first"),
    "u2": ("open", "never", "eqonly", "whole"),
    "u3": ("any",),
    "u4": ("nosha",),
    "u5": ("asc", "file"),
    "u6": ("last",),
}
REPORTS = ("lock.json", "issues.jsonl", "summary.json")
CARET_WIDE = 0x02
NO_STICKY = 0x04
STACK_QUEUE = 0x08
MEMBER_PIN_SKIP = 0x10
RELAY_SEQLESS = 0x20
DEPTH_CAP = 0x40
YANK_GAP = 0x80
MODE_BITS = (CARET_WIDE, NO_STICKY, STACK_QUEUE, MEMBER_PIN_SKIP, RELAY_SEQLESS, DEPTH_CAP, YANK_GAP)


def parse_ver(text):
    if not isinstance(text, str):
        return None
    m = VER_RE.match(text)
    if not m:
        return None
    a, b, c, r = m.groups()
    return (int(a), int(b), int(c), None if r is None else int(r))


def ver_key(v):
    return (v[0], v[1], v[2], 1 if v[3] is None else 0, 0 if v[3] is None else v[3])


def fmt_ver(v):
    base = "%d.%d.%d" % v[:3]
    return base if v[3] is None else base + "-rc.%d" % v[3]


def parse_range(text):
    """A requirement as a list of OR groups, each a list of (op, version) clauses, or None."""
    if not isinstance(text, str) or not text.strip():
        return None
    groups = []
    for part in text.split("|"):
        clauses = []
        for raw in part.split(","):
            item = raw.strip()
            if item == "*":
                clauses.append(("*", None))
                continue
            op = next((o for o in CLAUSE_OPS if item.startswith(o)), None)
            if op is None:
                return None
            v = parse_ver(item[len(op):].strip())
            if v is None:
                return None
            clauses.append((op, v))
        groups.append(clauses)
    return groups


def _upper_caret(v, wide=False):
    if v[0] > 0 or wide:
        return (v[0] + 1, 0, 0, None)
    if v[1] > 0:
        return (0, v[1] + 1, 0, None)
    return (0, 0, v[2] + 1, None)


def _clause_holds(op, bound, v, wide=False):
    k = ver_key(v)
    if op == "*":
        return True
    if op == "=":
        return v == bound
    if op == ">=":
        return k >= ver_key(bound)
    if op == "<":
        return k < ver_key(bound)
    if op == "^":
        return ver_key(bound) <= k < ver_key(_upper_caret(bound, wide))
    return ver_key(bound) <= k < ver_key((bound[0], bound[1] + 1, 0, None))


def satisfies(v, groups, variant):
    wide = bool(variant.get("eff", 0) & CARET_WIDE)
    for clauses in groups:
        if not all(_clause_holds(op, bound, v, wide) for op, bound in clauses):
            continue
        if v[3] is not None and variant["u2"] == "whole":
            if not any(b is not None and b[3] is not None and b[:3] == v[:3] for g in groups for _, b in g):
                continue
        if v[3] is not None and variant["u2"] == "never":
            continue
        if v[3] is not None and variant["u2"] == "eqonly":
            if not any(op == "=" and b == v for op, b in clauses):
                continue
        if v[3] is not None and variant["u2"] == "ref":
            # A release candidate counts only for a group that names a candidate of its own release.
            if not any(b is not None and b[3] is not None and b[:3] == v[:3] for _, b in clauses):
                continue
        return True
    return False


def _strict_int(value):
    return type(value) is int


def _well_formed(obj):
    if not isinstance(obj, dict):
        return None
    keys = frozenset(obj)
    if not _strict_int(obj.get("seq")) or obj["seq"] < 1:
        return None
    if not isinstance(obj.get("pkg"), str) or not NAME_RE.match(obj["pkg"]):
        return None
    if parse_ver(obj.get("ver")) is None:
        return None
    if keys == YANK_KEYS:
        return "yank" if obj["yank"] is True else None
    if keys != PUBLISH_KEYS:
        return None
    if not isinstance(obj["sha"], str) or not SHA_RE.match(obj["sha"]):
        return None
    deps = obj["deps"]
    if not isinstance(deps, dict):
        return None
    for name, rng in deps.items():
        if not NAME_RE.match(name) or name == obj["pkg"] or parse_range(rng) is None:
            return None
    return "publish"


def screen_index(raw_bytes, variant):
    counts = {"malformed": 0, "retransmitted": 0, "republished": 0, "yanks_applied": 0, "yanks_ignored": 0}
    seen = set()
    publishes = []
    yanks = []
    for raw in raw_bytes.split(b"\n"):
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            counts["malformed"] += 1
            continue
        kind = _well_formed(obj)
        if kind is None:
            counts["malformed"] += 1
            continue
        bare = obj if not variant.get("eff", 0) & RELAY_SEQLESS else {k: x for k, x in obj.items() if k != "seq"}
        canon = json.dumps(bare, sort_keys=True, separators=(",", ":"))
        if canon in seen:
            counts["retransmitted"] += 1
            continue
        seen.add(canon)
        (publishes if kind == "publish" else yanks).append(obj)
    groups = {}
    for position, obj in enumerate(publishes):
        groups.setdefault((obj["pkg"], obj["ver"]), []).append((position, obj))
    kept = {}
    for key, copies in groups.items():
        counts["republished"] += len(copies) - 1
        if variant["u1"] == "ref":
            kept[key] = min(copies, key=lambda pair: pair[1]["seq"])[1]
        elif variant["u1"] == "last":
            kept[key] = copies[-1][1]
        else:
            kept[key] = copies[0][1]
    yanked = set()
    for obj in yanks:
        key = (obj["pkg"], obj["ver"])
        target = kept.get(key)
        if target is not None and (variant["u3"] == "any" or obj["seq"] > target["seq"] + (8 if variant.get("eff", 0) & YANK_GAP else 0)):
            counts["yanks_applied"] += 1
            yanked.add(key)
        else:
            counts["yanks_ignored"] += 1
    return kept, yanked, counts


def read_pins(text, variant):
    pins = {}
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        pkg = (row.get("pkg") or "").strip()
        groups = parse_range(row.get("range") or "")
        if not NAME_RE.match(pkg) or groups is None:
            continue
        if pkg in pins and variant["u6"] == "ref":
            continue
        pins[pkg] = groups
    return pins


def _order(deps, variant):
    names = list(deps)
    if variant["u5"] == "ref":
        return sorted(names, reverse=True)
    if variant["u5"] == "asc":
        return sorted(names)
    return names


def resolve(files, variant=None):
    """files maps index.jsonl, workspace.json, pins.csv, lock.prev.json to bytes; returns report texts."""
    variant = dict(variant or REFERENCE)
    mode = json.loads(files["manifest.json"].decode("utf-8"))["mode"]
    eff = variant["eff"] = mode & ~variant.get("blind", 0)
    kept, yanked, counts = screen_index(files["index.jsonl"], variant)
    workspace = json.loads(files["workspace.json"].decode("utf-8"))
    pins = read_pins(files["pins.csv"].decode("utf-8"), variant)
    prev = json.loads(files["lock.prev.json"].decode("utf-8")).get("packages", {})
    versions = {}
    for (pkg, ver), obj in kept.items():
        versions.setdefault(pkg, []).append((parse_ver(ver), obj))
    queue = deque()
    for member in workspace["members"]:
        for pkg in _order(member["deps"], variant):
            queue.append((pkg, member["deps"][pkg], "member:" + member["name"], 1))
    picks = {}
    issues = []
    sticky = 0
    while queue:
        pkg, rng, by, depth = queue.pop() if eff & STACK_QUEUE else queue.popleft()
        groups = parse_range(rng)
        if pkg in picks:
            v = parse_ver(picks[pkg]["version"])
            if not satisfies(v, groups, variant):
                issues.append({"kind": "conflict", "pkg": pkg, "range": rng, "by": by, "picked": picks[pkg]["version"]})
            continue
        cands = []
        for v, obj in versions.get(pkg, []):
            if (pkg, obj["ver"]) in yanked or not satisfies(v, groups, variant):
                continue
            if pkg in pins and not (eff & MEMBER_PIN_SKIP and by.startswith("member:")) and not satisfies(v, pins[pkg], variant):
                continue
            cands.append((v, obj))
        if not cands:
            issues.append({"kind": "unresolved", "pkg": pkg, "range": rng, "by": by})
            continue
        chosen = None
        held = prev.get(pkg)
        if isinstance(held, dict) and not eff & NO_STICKY:
            for v, obj in cands:
                if obj["ver"] == held.get("version") and (variant["u4"] == "nosha" or obj["sha"] == held.get("sha")):
                    chosen = obj
                    sticky += 1
        if chosen is None:
            chosen = max(cands, key=lambda pair: ver_key(pair[0]))[1]
        picks[pkg] = {"version": chosen["ver"], "sha": chosen["sha"], "via": by}
        if eff & DEPTH_CAP and depth >= 3:
            continue
        for dep in _order(chosen["deps"], variant):
            queue.append((dep, chosen["deps"][dep], "%s@%s" % (pkg, chosen["ver"]), depth + 1))
    digest = hashlib.sha256("".join("%s@%s:%s\n" % (p, picks[p]["version"], picks[p]["sha"]) for p in sorted(picks)).encode("utf-8")).hexdigest()
    summary = dict(counts)
    summary.update({
        "picked": len(picks),
        "sticky": sticky,
        "conflicts": sum(1 for i in issues if i["kind"] == "conflict"),
        "unresolved": sum(1 for i in issues if i["kind"] == "unresolved"),
        "pins": len(pins),
        "lock_digest": digest,
    })
    return {
        "lock.json": json.dumps({"packages": picks}, sort_keys=True, indent=2) + "\n",
        "issues.jsonl": "".join(json.dumps(i, sort_keys=True, separators=(",", ":")) + "\n" for i in issues),
        "summary.json": json.dumps(summary, sort_keys=True, indent=2) + "\n",
    }



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

    def hex40(self):
        return "".join("%016x" % self.next() for _ in range(3))[:40]


STEMS = ["anvil", "basil", "cobalt", "delta", "ember", "fjord", "garnet", "harbor", "indigo", "juniper",
         "kestrel", "lumen", "marble", "nectar", "onyx", "pylon", "quartz", "raven", "sable", "tundra",
         "umber", "vortex", "willow", "xenon", "yarrow", "zephyr"]
SUFFIX = ["core", "io", "net", "util", "cfg", "log", "auth", "ui", "db", "cli", "fmt", "rpc"]


def _names(rng, n):
    pool = ["%s-%s" % (s, x) for s in STEMS for x in SUFFIX]
    return sorted(rng.shuffle(pool)[:n])


def _versions(rng):
    major = rng.pick([0, 0, 1, 1, 2, 3])
    minor = rng.below(4)
    patch = rng.below(3)
    out = []
    for _ in range(rng.between(3, 6)):
        out.append((major, minor, patch, None))
        step = rng.below(10)
        if step < 5:
            patch += 1 + rng.below(2)
        elif step < 8:
            minor += 1
            patch = 0
        else:
            major += 1
            minor = rng.below(2)
            patch = 0
    return out


def _range_for(rng, vers):
    releases = [v for v in vers if v[3] is None]
    a = rng.pick(releases)
    form = rng.below(12)
    if form < 4:
        return "^" + fmt_ver(a)
    if form < 6:
        return "~" + fmt_ver(a)
    if form < 8:
        higher = [v for v in releases if ver_key(v) > ver_key(a)]
        if higher:
            return ">=%s, <%s" % (fmt_ver(a), fmt_ver(rng.pick(higher)))
        return ">=" + fmt_ver(a)
    if form < 9:
        return "=" + fmt_ver(a)
    if form < 10:
        return "*"
    b = rng.pick(releases)
    return "^%s | ~%s" % (fmt_ver(a), fmt_ver(b))


def _line(obj):
    return json.dumps(obj, separators=(",", ":"))


def build_corpus(seed, traps, size=24, members=4, noise=True, mode=0, fan=4):
    """A fresh intake as a dict of file name to bytes; traps is a set drawn from u1..u6."""
    rng = Rng(seed)
    names = _names(rng, size)
    vers = {n: _versions(rng) for n in names}
    if "u2" in traps:
        for n in rng.shuffle(names)[: max(2, size // 6)]:
            top = max(vers[n], key=ver_key)
            vers[n].append((top[0], top[1] + 1, 0, rng.between(1, 3)))
            low = vers[n][0]
            vers[n].append((low[0], low[1], low[2] + 1, 1))
    entries = []
    seqs = rng.shuffle(range(1, 40 * size))
    cursor = [0]

    def next_seq():
        cursor[0] += 1
        return seqs[cursor[0] - 1]

    shas = {}
    for i, n in enumerate(names):
        for v in vers[n]:
            deps = {}
            below = names[i + 1:]
            for d in rng.shuffle(below)[: rng.below(fan) if below else 0]:
                deps[d] = _range_for(rng, vers[d])
                if "u2" in traps and rng.below(3) == 0:
                    rcs = [x for x in vers[d] if x[3] is not None]
                    if rcs:
                        rc = rng.pick(rcs)
                        deps[d] = rng.pick((">=", "^", "~", "=")) + fmt_ver(rc)
                        if rng.below(2) == 0:
                            low = rng.pick(rcs)
                            base = [x for x in vers[d] if x[3] is None and ver_key(x) < ver_key(low)]
                            if base:
                                deps[d] = "^%s | >=%s" % (fmt_ver(base[-1]), fmt_ver(low[:3] + (low[3] + 5,)))
            sha = rng.hex40()
            shas[(n, v)] = sha
            entries.append({"seq": next_seq(), "pkg": n, "ver": fmt_ver(v), "deps": deps, "sha": sha})
    by_key = {(e["pkg"], e["ver"]): e for e in entries}
    tops = [max((v for v in vers[n] if v[3] is None), key=ver_key) for n in names]
    lines = [_line(e) for e in entries]
    extra = []
    for n, top in zip(names, tops):
        if rng.below(6) == 0:
            target = by_key[(n, fmt_ver(rng.pick(vers[n])))]
            extra.append({"seq": target["seq"] + 1 + rng.below(50), "pkg": n, "ver": target["ver"], "yank": True})
    if "u3" in traps:
        for n in rng.shuffle(names)[: max(2, size // 6)]:
            target = by_key[(n, fmt_ver(max((v for v in vers[n] if v[3] is None), key=ver_key)))]
            if target["seq"] > 1:
                extra.append({"seq": rng.between(1, target["seq"] - 1), "pkg": n, "ver": target["ver"], "yank": True})
    if mode & YANK_GAP:
        for n in rng.shuffle(names)[: max(2, size // 6)]:
            target = by_key[(n, fmt_ver(rng.pick(vers[n])))]
            extra.append({"seq": target["seq"] + rng.between(1, 8), "pkg": n, "ver": target["ver"], "yank": True})
    if mode & RELAY_SEQLESS:
        for e in rng.shuffle(entries)[: max(2, size // 8)]:
            relay = dict(e)
            relay["seq"] = e["seq"] + 1 + rng.below(60)
            extra.append(relay)
        for y in rng.shuffle(extra)[:2]:
            relay = dict(y)
            relay["seq"] = y["seq"] + 1 + rng.below(20)
            extra.append(relay)
    lines.extend(_line(e) for e in extra)
    lines = rng.shuffle(lines)
    if "u1" in traps:
        for slot, n in enumerate(rng.shuffle(names)[: max(2, size // 6)]):
            target = by_key[(n, fmt_ver(max((v for v in vers[n] if v[3] is None), key=ver_key)))]
            imposter = dict(target)
            imposter["seq"] = target["seq"] + 1 + rng.below(80)
            imposter["sha"] = rng.hex40()
            imposter["deps"] = dict(target["deps"])
            original = _line(target)
            lines.remove(original)
            first, second = (original, _line(imposter)) if slot % 2 == 0 else (_line(imposter), original)
            at = rng.below(len(lines) + 1)
            lines.insert(at, first)
            lines.insert(rng.between(at + 1, len(lines)), second)
    if noise:
        damaged = []
        sample = [json.loads(x) for x in rng.shuffle(lines)[:12]]
        kinds = ["truncated", "missing", "badver", "badsha", "strseq", "boolseq", "selfdep", "badrange", "array", "yankfalse", "floatseq", "extra"]
        for kind, obj in zip(rng.shuffle(kinds)[: rng.between(8, 12)], sample):
            obj = dict(obj)
            if kind == "truncated":
                text = _line(obj)
                damaged.append(text[: len(text) // 2])
                continue
            if kind == "array":
                damaged.append(_line([obj["pkg"], obj["ver"]]))
                continue
            if kind == "missing":
                obj.pop("ver")
            elif kind == "badver":
                obj["ver"] = obj["ver"].rsplit(".", 1)[0]
            elif kind == "badsha":
                obj["sha"] = "Z" * 40
            elif kind == "strseq":
                obj["seq"] = str(obj["seq"])
            elif kind == "boolseq":
                obj["seq"] = True
            elif kind == "selfdep":
                obj["deps"] = {obj["pkg"]: "*"}
            elif kind == "badrange":
                obj["deps"] = {names[-1]: "^^1.0.0"} if obj["pkg"] != names[-1] else {names[0]: "1.0"}
            elif kind == "yankfalse":
                obj = {"seq": obj["seq"], "pkg": obj["pkg"], "ver": obj["ver"], "yank": False}
            elif kind == "floatseq":
                text = _line(obj).replace('"seq":%d' % obj["seq"], '"seq":%d.0' % obj["seq"])
                damaged.append(text)
                continue
            elif kind == "extra":
                obj["note"] = "relay"
            damaged.append(_line(obj))
        for text in damaged:
            lines.insert(rng.below(len(lines) + 1), text)
        for text in rng.shuffle(lines)[: rng.between(3, 7)]:
            lines.insert(rng.below(len(lines) + 1), text)
    ws = []
    for m in range(members):
        deps = {}
        for d in rng.shuffle(names[: max(4, size // 2)])[: rng.between(2, 4) if fan > 2 else 1]:
            deps[d] = _range_for(rng, vers[d])
        ws.append({"name": "app-%s" % STEMS[(seed + m * 7) % len(STEMS)] + str(m), "deps": deps})
    prev = {}
    for n in names:
        if rng.below(3) == 0:
            v = rng.pick([x for x in vers[n] if x[3] is None])
            prev[n] = {"version": fmt_ver(v), "sha": shas[(n, v)]}
    if "u4" in traps:
        for n in rng.shuffle(names)[: max(3, size // 5)]:
            releases = [x for x in vers[n] if x[3] is None]
            v = rng.pick(releases[:-1] or releases)
            prev[n] = {"version": fmt_ver(v), "sha": rng.hex40()}
    pin_rows = []
    for n in rng.shuffle(names)[: rng.between(1, 2)]:
        pin_rows.append((n, _range_for(rng, vers[n]), "hold"))
    if "u6" in traps:
        for n in rng.shuffle(names[: size // 2])[:2]:
            releases = [x for x in vers[n] if x[3] is None]
            pin_rows.append((n, "<" + fmt_ver(releases[-1]), "freeze"))
            pin_rows.append((n, "*", "thaw"))
    if mode & MEMBER_PIN_SKIP:
        for member in ws[:2]:
            n = sorted(member["deps"])[0]
            releases = [x for x in vers[n] if x[3] is None]
            pin_rows.append((n, "<" + fmt_ver(releases[-1]), "hold"))
    pin_rows.append(("Bad Name", "*", "typo"))
    pin_rows.append((names[0], "~~1", "typo"))
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["pkg", "range", "reason"])
    for row in pin_rows:
        writer.writerow(row)
    files = {
        "index.jsonl": ("\n".join(lines) + "\n").encode("utf-8"),
        "workspace.json": (json.dumps({"members": ws}, indent=2) + "\n").encode("utf-8"),
        "pins.csv": out.getvalue().encode("utf-8"),
        "lock.prev.json": (json.dumps({"packages": prev}, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        "manifest.json": _manifest(mode, None),
    }
    files["manifest.json"] = _manifest(mode, resolve(files))
    return files


def _manifest(mode, reports):
    """The input manifest: the mode word plus digests of the expected reports and of each member's share."""
    body = {"mode": mode}
    if reports is not None:
        body["reports"] = {n: hashlib.sha256(reports[n].encode("utf-8")).hexdigest() for n in REPORTS}
        body["members"] = member_digests(reports["lock.json"])
    return (json.dumps(body, indent=2, sort_keys=True) + "\n").encode("utf-8")


def member_digests(lock_text):
    picks = json.loads(lock_text)["packages"]
    shares = {}
    for pkg in picks:
        via, seen = picks[pkg]["via"], {pkg}
        while not via.startswith("member:"):
            parent = via.rsplit("@", 1)[0]
            if parent in seen or parent not in picks:
                break
            seen.add(parent)
            via = picks[parent]["via"]
        shares.setdefault(via.split(":", 1)[-1], []).append("%s@%s:%s\n" % (pkg, picks[pkg]["version"], picks[pkg]["sha"]))
    return {m: hashlib.sha256("".join(sorted(lines)).encode("utf-8")).hexdigest() for m, lines in sorted(shares.items())}


def flipped(rule, reading):
    v = dict(REFERENCE)
    v[rule] = reading
    return v


def separation(files):
    """Which wrong readings change at least one report on this intake."""
    ref = resolve(files)
    moved = set()
    for rule, readings in WRONG_READINGS.items():
        for reading in readings:
            if resolve(files, flipped(rule, reading)) != ref:
                moved.add((rule, reading))
    return moved


def bit_moves(files):
    """Which mode bits change the reports when a program ignores just that bit."""
    ref = resolve(files)
    out = set()
    for bit in MODE_BITS:
        v = dict(REFERENCE)
        v["blind"] = bit
        if resolve(files, v) != ref:
            out.add(bit)
    return out


def isolated_case(seed, rule, size=18, wanted=None):
    """Search seeds from seed for an intake where only the wanted readings of one rule move the reports."""
    traps = {rule} if rule in ("u1", "u2", "u3", "u4", "u6") else set()
    wanted = wanted if wanted is not None else {(rule, r) for r in WRONG_READINGS[rule]}
    lean = rule == "u2"
    for attempt in range(3000):
        files = build_corpus(seed + attempt * 7919, traps, size=size, members=5 if lean else 3, noise=False, fan=2 if lean else 4)
        if separation(files) == wanted:
            return files
    raise RuntimeError("no isolated case for " + rule)


def plain_case(seed, size=16, noise=False):
    for attempt in range(400):
        files = build_corpus(seed + attempt * 104729, set(), size=size, members=3, noise=noise)
        if not separation(files):
            return files
    raise RuntimeError("no plain case")


def mixed_case(seed, size=30, need=None, mode=0):
    """An intake where every needed reading and every set mode bit moves the reports."""
    need = need if need is not None else {(r, x) for r, xs in WRONG_READINGS.items() for x in xs}
    bits = {b for b in MODE_BITS if mode & b}
    for attempt in range(400):
        files = build_corpus(seed + attempt * 15485863, {"u1", "u2", "u3", "u4", "u6"}, size=size, members=4, noise=True, mode=mode)
        if need <= separation(files) and bits <= bit_moves(files):
            return files
    raise RuntimeError("no mixed case")


def bit_case(seed, bit, size=20):
    """An intake whose mode word is the single bit, where ignoring it changes the reports and no reading does."""
    for attempt in range(600):
        files = build_corpus(seed + attempt * 6151, set(), size=size, members=3, noise=False, mode=bit)
        allowed = {("u3", "any")} if bit == YANK_GAP else set()
        if bit_moves(files) == {bit} and separation(files) <= allowed:
            return files
    raise RuntimeError("no case for bit %#x" % bit)


def empty_issue_case(seed):
    """A small clean intake whose reference resolution raises no issue at all."""
    for attempt in range(600):
        files = build_corpus(seed + attempt * 2741, set(), size=8, members=1, noise=False)
        if resolve(files)["issues.jsonl"] == "" and not separation(files):
            return files
    raise RuntimeError("no empty issue case")


SHIPPED_SEED = 219689146772702551 ^ 3
EXAMPLE_SEED = 219689146772702551 ^ 1
SECOND_EXAMPLE_SEED = 219689146772702551 ^ 2
_MODE_NEED = {("u1", "last"), ("u3", "any"), ("u5", "asc")}
_LIVE_NEED = {("u1", "last"), ("u1", "first"), ("u2", "open"), ("u3", "any"), ("u5", "asc"), ("u5", "file")}
CASES = {
    "plain": lambda: plain_case(0x51A7E0001, size=16),
    "noisy-plain": lambda: plain_case(0x51A7E0002, size=20, noise=True),
    "screen": lambda: mixed_case(0x3A1E00007, size=30),
    "iso-u1": lambda: isolated_case(0x1D0000001, "u1"),
    "iso-u2a": lambda: isolated_case(0x7700, "u2", wanted={("u2", "open"), ("u2", "whole")}),
    "iso-u2b": lambda: isolated_case(0x7700, "u2", wanted={("u2", "never"), ("u2", "eqonly")}),
    "iso-u3": lambda: isolated_case(0x1D0000003, "u3"),
    "iso-u4": lambda: isolated_case(0x1D0000004, "u4"),
    "iso-u5": lambda: isolated_case(0x1D0000005, "u5"),
    "iso-u6": lambda: isolated_case(0x1D0000006, "u6"),
    "mixed-a": lambda: mixed_case(0x3A1E00001, size=32),
    "mixed-b": lambda: mixed_case(0x3A1E00002, size=36),
    "large": lambda: mixed_case(0x3A1E00003, size=140, need=_MODE_NEED, mode=0x6A),
    "mode-alpha": lambda: mixed_case(0x3A1E00011, size=32, need=_MODE_NEED, mode=0xFE),
    "mode-beta": lambda: mixed_case(0x3A1E00012, size=34, need=_MODE_NEED, mode=0xB6),
    "bit-02": lambda: bit_case(0x51A0 + CARET_WIDE, CARET_WIDE),
    "bit-04": lambda: bit_case(0x51A0 + NO_STICKY, NO_STICKY),
    "bit-08": lambda: bit_case(0x51A0 + STACK_QUEUE, STACK_QUEUE),
    "bit-10": lambda: bit_case(0x51A0 + MEMBER_PIN_SKIP, MEMBER_PIN_SKIP),
    "bit-20": lambda: bit_case(0x51A0 + RELAY_SEQLESS, RELAY_SEQLESS),
    "bit-40": lambda: bit_case(0x51A0 + DEPTH_CAP, DEPTH_CAP),
    "bit-80": lambda: bit_case(0x51A0 + YANK_GAP, YANK_GAP),
    "empty": lambda: empty_issue_case(0x0E0000001),
    "stale": lambda: mixed_case(0x3A1E00004, size=24),
    "example": lambda: mixed_case(EXAMPLE_SEED, size=26),
    "repeat": lambda: mixed_case(0x3A1E00005, size=28),
    "untouched": lambda: mixed_case(0x3A1E00006, size=28),
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
    "lock.json": '{"packages": {"left-over": {"sha": "0", "version": "9.9.9", "via": "member:gone"}}}\n',
    "issues.jsonl": '{"by":"member:gone","kind":"unresolved","pkg":"left-over","range":"*"}\n',
    "summary.json": '{"picked": 99}\n',
}


def _case(label):
    if label not in _FILES:
        _FILES[label] = CASES[label]()
    return _FILES[label]


def _script(workspace):
    return os.path.join(str(workspace), "out", "lockres.py")


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


def _run(workspace, label, prefill=False):
    key = (str(workspace), label)
    if key in _RUNS:
        return _RUNS[key]
    script = _script(workspace)
    if not os.path.isfile(script):
        return None
    _open_up(script)
    _grant_read(os.path.dirname(script))
    _grant_read(script)
    work = tempfile.mkdtemp(prefix="wlr-" + label + "-")
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
    code = _launch([sys.executable, script, data, out], scratch)
    _RUNS[key] = (data, out, scratch, code, before)
    return _RUNS[key]


def _artifact(out, name):
    path = os.path.join(out, name)
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as handle:
        return handle.read()


def _report_matches(workspace, label, names=REPORTS, prefill=False):
    """True when the program exits 0 and writes the named reports byte for byte."""
    try:
        run = _run(workspace, label, prefill)
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


@criterion(description="the resolver program exists at out/lockres.py under the workspace and exits 0 on a fresh intake")
def program_is_delivered(workspace: Path) -> bool:
    try:
        run = _run(workspace, "plain")
        return run is not None and run[3] == 0
    except Exception:
        return False


@criterion(description="on a clean fresh intake with no undocumented rule in play the lock file matches byte for byte")
def plain_intake_lock_matches(workspace: Path) -> bool:
    return _report_matches(workspace, "plain", ("lock.json",))


@criterion(description="on a clean fresh intake with no undocumented rule in play the issues file matches byte for byte")
def plain_intake_issues_match(workspace: Path) -> bool:
    return _report_matches(workspace, "plain", ("issues.jsonl",))


@criterion(description="on a clean fresh intake with no undocumented rule in play the summary matches byte for byte")
def plain_intake_summary_matches(workspace: Path) -> bool:
    return _report_matches(workspace, "plain", ("summary.json",))


@criterion(description="on a fresh intake with damaged and repeated index lines the summary screening counts match")
def screening_counts_match(workspace: Path) -> bool:
    try:
        run = _run(workspace, "screen")
        if run is None or run[3] != 0:
            return False
        got = json.loads((_artifact(run[1], "summary.json") or b"{}").decode("utf-8"))
        want = json.loads(resolve(_case("screen"))["summary.json"])
        return isinstance(got, dict) and all(got.get(k) == want[k] for k in ("malformed", "retransmitted", "republished"))
    except Exception:
        return False


@criterion(description="on a fresh intake with damaged and repeated index lines all three reports match byte for byte")
def screened_intake_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "noisy-plain")


@criterion(description="an intake where only the choice among republished copies matters resolves byte for byte")
def republished_copy_choice_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u1")


@criterion(description="an intake where only release candidate eligibility matters resolves byte for byte")
def release_candidate_eligibility_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u2a") and _report_matches(workspace, "iso-u2b")


@criterion(description="an intake where only the timing of yank records matters resolves byte for byte")
def yank_timing_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u3")


@criterion(description="an intake where only the honouring of the previous lock matters resolves byte for byte")
def previous_lock_honouring_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u4")


@criterion(description="an intake where only the order requirements enter the queue matters resolves byte for byte")
def queue_order_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u5")


@criterion(description="an intake where only the choice among repeated pins rows matters resolves byte for byte")
def duplicate_pin_choice_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u6")


@criterion(description="a fresh screened intake where every undocumented rule matters resolves byte for byte")
def mixed_intake_alpha_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "mixed-a")


@criterion(description="a second fresh screened intake where every undocumented rule matters resolves byte for byte")
def mixed_intake_beta_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "mixed-b")


@criterion(description="the lock digest in the summary agrees with the lock file the same run wrote")
def lock_digest_agrees_with_lock(workspace: Path) -> bool:
    try:
        run = _run(workspace, "mixed-a")
        if run is None or run[3] != 0:
            return False
        lock = json.loads((_artifact(run[1], "lock.json") or b"{}").decode("utf-8"))
        summary = json.loads((_artifact(run[1], "summary.json") or b"{}").decode("utf-8"))
        packages = lock.get("packages")
        if not isinstance(packages, dict) or not packages:
            return False
        text = "".join("%s@%s:%s\n" % (p, packages[p]["version"], packages[p]["sha"]) for p in sorted(packages))
        return summary.get("lock_digest") == hashlib.sha256(text.encode("utf-8")).hexdigest()
    except Exception:
        return False


@criterion(description="an intake that raises no issue still gets an empty issues file and matching reports")
def empty_issues_file_written(workspace: Path) -> bool:
    return _report_matches(workspace, "empty")


@criterion(description="reports left in the output directory by an earlier run are replaced by the new ones")
def stale_outputs_replaced(workspace: Path) -> bool:
    return _report_matches(workspace, "stale", prefill=True)


@criterion(description="the first worked example intake reproduces its shipped reports byte for byte")
def worked_example_reproduces(workspace: Path) -> bool:
    return _report_matches(workspace, "example")


@criterion(description="a large fresh intake of a hundred and forty packages under a nonzero mode word resolves byte for byte")
def large_intake_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "large")


@criterion(description="a fresh intake whose mode word is 2 alone resolves byte for byte")
def mode_bit_two_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-02")


@criterion(description="a fresh intake whose mode word is 4 alone resolves byte for byte")
def mode_bit_four_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-04")


@criterion(description="a fresh intake whose mode word is 8 alone resolves byte for byte")
def mode_bit_eight_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-08")


@criterion(description="a fresh intake whose mode word is 16 alone resolves byte for byte")
def mode_bit_sixteen_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-10")


@criterion(description="a fresh intake whose mode word is 32 alone resolves byte for byte")
def mode_bit_thirty_two_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-20")


@criterion(description="a fresh intake whose mode word is 64 alone resolves byte for byte")
def mode_bit_sixty_four_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-40")


@criterion(description="a fresh intake whose mode word is 128 alone resolves byte for byte")
def mode_bit_one_hundred_twenty_eight_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-80")


@criterion(description="a fresh screened intake under mode word 254 resolves byte for byte")
def mode_word_alpha_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "mode-alpha")


@criterion(description="a second fresh screened intake under mode word 182 resolves byte for byte")
def mode_word_beta_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "mode-beta")


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


@criterion(description="the delivered program carries content hashes or the lock digest of a shipped intake as literals")
def negative_hardcoded_shipped_answers(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        source = _delivered_source(workspace)
        if source is None:
            return False
        answers = []
        shipped = ((SHIPPED_SEED, 44, _LIVE_NEED, 0xFE), (EXAMPLE_SEED, 26, None, 0), (SECOND_EXAMPLE_SEED, 26, None, 0))
        for seed, size, need, mode in shipped:
            reports = resolve(mixed_case(seed, size=size, need=need, mode=mode))
            lock = json.loads(reports["lock.json"])["packages"]
            marks = sorted({entry["sha"] for entry in lock.values()})
            answers.append((json.loads(reports["summary.json"])["lock_digest"], marks))
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
        return any(digest in blob or sum(1 for mark in marks if mark in blob) >= 3 for digest, marks in answers)
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


criteria.program_is_delivered(weight=1)
criteria.plain_intake_lock_matches(weight=3)
criteria.plain_intake_issues_match(weight=1)
criteria.plain_intake_summary_matches(weight=1)
criteria.screening_counts_match(weight=1)
criteria.screened_intake_resolves(weight=1)
criteria.republished_copy_choice_isolated(weight=3)
criteria.release_candidate_eligibility_isolated(weight=3)
criteria.yank_timing_isolated(weight=3)
criteria.previous_lock_honouring_isolated(weight=3)
criteria.queue_order_isolated(weight=3)
criteria.duplicate_pin_choice_isolated(weight=3)
criteria.mixed_intake_alpha_resolves(weight=3)
criteria.mixed_intake_beta_resolves(weight=3)
criteria.lock_digest_agrees_with_lock(weight=1)
criteria.empty_issues_file_written(weight=1)
criteria.stale_outputs_replaced(weight=1)
criteria.worked_example_reproduces(weight=1)
criteria.mode_bit_two_resolves(weight=5)
criteria.mode_bit_four_resolves(weight=5)
criteria.mode_bit_eight_resolves(weight=5)
criteria.mode_bit_sixteen_resolves(weight=5)
criteria.mode_bit_thirty_two_resolves(weight=5)
criteria.mode_bit_sixty_four_resolves(weight=5)
criteria.mode_bit_one_hundred_twenty_eight_resolves(weight=5)
criteria.mode_word_alpha_resolves(weight=3)
criteria.mode_word_beta_resolves(weight=3)
criteria.large_intake_resolves(weight=3)
criteria.negative_input_folder_mutated(weight=-5)
criteria.negative_hardcoded_shipped_answers(weight=-5)
criteria.negative_third_party_dependency(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
