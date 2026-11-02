import ast
import datetime
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


REFERENCE = {"u1": "oldest", "u2": "sunday", "u3": "strict", "u4": "skip", "u5": "lowest", "u6": "utc"}
WRONG_READINGS = {"u1": ("newest",), "u2": ("iso",), "u3": ("inclusive",), "u4": ("count",), "u5": ("last", "first"), "u6": ("local",)}
REPORTS = ("keep.json", "prune.jsonl", "summary.json")
INPUTS = ("snapshots.jsonl", "policy.json", "holds.csv", "manifest.json")

KEEP_FIRST = 0x02
QUARTER = 0x04
DAY_ROLL = 0x08
HOLD_FOREVER = 0x10
RELAY_SEQLESS = 0x20
PARTIAL_CHAIN = 0x40
SIZE_CAP = 0x80
MODE_BITS = (KEEP_FIRST, QUARTER, DAY_ROLL, HOLD_FOREVER, RELAY_SEQLESS, PARTIAL_CHAIN, SIZE_CAP)
ROLL_HOURS = 4
CLASSES = ("hourly", "daily", "weekly", "monthly")

NAME_RE = re.compile(r"^[a-z][a-z0-9-]{0,30}$")
ID_RE = re.compile(r"^s[0-9a-f]{12}$")
TAKEN_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(Z|[+-]\d{2}:\d{2})$")
SNAP_KEYS = {"seq", "host", "vol", "id", "taken", "size", "parent", "state"}


def parse_taken(text):
    """Return (utc datetime, local datetime) or None."""
    if not isinstance(text, str):
        return None
    m = TAKEN_RE.match(text)
    if not m:
        return None
    y, mo, d, h, mi, s, off = m.groups()
    try:
        local = datetime.datetime(int(y), int(mo), int(d), int(h), int(mi), int(s))
    except ValueError:
        return None
    if off == "Z":
        minutes = 0
    else:
        oh, om = int(off[1:3]), int(off[4:6])
        if oh > 14 or om > 59:
            return None
        minutes = (oh * 60 + om) * (1 if off[0] == "+" else -1)
    return local - datetime.timedelta(minutes=minutes), local


def _strict_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def check_line(rec):
    if not isinstance(rec, dict) or set(rec) != SNAP_KEYS:
        return False
    if not _strict_int(rec["seq"]) or rec["seq"] < 1:
        return False
    for k in ("host", "vol"):
        if not isinstance(rec[k], str) or not NAME_RE.match(rec[k]):
            return False
    if not isinstance(rec["id"], str) or not ID_RE.match(rec["id"]):
        return False
    if parse_taken(rec["taken"]) is None:
        return False
    if not _strict_int(rec["size"]) or rec["size"] < 1:
        return False
    p = rec["parent"]
    if p is not None and (not isinstance(p, str) or not ID_RE.match(p) or p == rec["id"]):
        return False
    return rec["state"] in ("ok", "partial")


def screen(blob, variant, eff):
    counts = {"malformed": 0, "retransmitted": 0, "republished": 0}
    seen = set()
    by_id = {}
    order = []
    for raw in blob.split(b"\n"):
        if not raw.strip():
            continue
        try:
            rec = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            counts["malformed"] += 1
            continue
        if not check_line(rec):
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
        by_id.setdefault(rec["id"], []).append(rec)
        order.append(rec["id"])
    snaps = {}
    for sid, copies in by_id.items():
        contents = {json.dumps({k: v for k, v in c.items() if k != "seq"}, sort_keys=True) for c in copies}
        if len(contents) > 1:
            counts["republished"] += 1
        if variant["u5"] == "lowest":
            snaps[sid] = min(copies, key=lambda c: c["seq"])
        elif variant["u5"] == "last":
            snaps[sid] = copies[-1]
        else:
            snaps[sid] = copies[0]
    return snaps, counts


def read_policy(blob):
    doc = json.loads(blob.decode("utf-8"))
    return doc.get("default", {}), doc.get("hosts", {})


def read_holds(text):
    out = []
    lines = text.splitlines()
    if not lines or lines[0].strip() != "id,until,reason":
        return out
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) != 3 or not ID_RE.match(parts[0]):
            continue
        try:
            until = datetime.date.fromisoformat(parts[1]) if re.match(r"^\d{4}-\d{2}-\d{2}$", parts[1]) else None
        except ValueError:
            until = None
        if until is None:
            continue
        out.append((parts[0], until))
    return out


def _wall(snap, variant):
    utc, local = parse_taken(snap["taken"])
    return utc if variant["u6"] == "utc" else local


def bucket_key(cls, wall, variant, eff):
    if cls == "hourly":
        return wall.strftime("%Y-%m-%dT%H")
    if cls == "daily":
        if eff & DAY_ROLL:
            wall = wall - datetime.timedelta(hours=ROLL_HOURS)
        return wall.date().isoformat()
    if cls == "weekly":
        d = wall.date()
        back = (d.weekday() + 1) % 7 if variant["u2"] == "sunday" else d.weekday()
        return (d - datetime.timedelta(days=back)).isoformat()
    if eff & QUARTER:
        return "%04d-Q%d" % (wall.year, (wall.month - 1) // 3 + 1)
    return "%04d-%02d" % (wall.year, wall.month)


def resolve(files, variant=None):
    variant = dict(REFERENCE if variant is None else variant)
    mode = json.loads(files["manifest.json"].decode("utf-8")).get("mode", 0)
    eff = mode & ~variant.get("blind", 0)
    snaps, counts = screen(files["snapshots.jsonl"], variant, eff)
    default, hosts = read_policy(files["policy.json"])
    holds = read_holds(files["holds.csv"].decode("utf-8"))
    series = {}
    for s in snaps.values():
        series.setdefault(s["host"] + "/" + s["vol"], []).append(s)
    keep_all = {}
    for name in sorted(series):
        members = sorted(series[name], key=lambda s: (parse_taken(s["taken"])[0], s["id"]))
        pol = hosts.get(members[0]["host"], default)
        kept = {}
        pool = [s for s in members if variant["u4"] == "count" or s["state"] == "ok"]
        for cls in CLASSES:
            n = pol.get(cls, 0)
            groups = {}
            for s in pool:
                groups.setdefault(bucket_key(cls, _wall(s, variant), variant, eff), []).append(s)
            for key in sorted(groups, reverse=True)[:n]:
                g = groups[key]
                rep = g[0] if variant["u1"] == "oldest" else g[-1]
                kept.setdefault(rep["id"], cls)
        if eff & KEEP_FIRST:
            oks = [s for s in members if s["state"] == "ok"]
            if oks:
                kept.setdefault(oks[0]["id"], "anchor")
        newest_day = _wall(members[-1], variant).date()
        ids = {s["id"] for s in members}
        for hid, until in holds:
            if hid in ids:
                active = bool(eff & HOLD_FOREVER) or (until > newest_day if variant["u3"] == "strict" else until >= newest_day)
                if active:
                    kept[hid] = "hold"
        if eff & SIZE_CAP and "max_bytes" in pol:
            size = {s["id"]: s["size"] for s in members}
            for s in members:
                if sum(size[k] for k in kept) <= pol["max_bytes"]:
                    break
                if s["id"] in kept and kept[s["id"]] != "hold":
                    del kept[s["id"]]
        by = {s["id"]: s for s in members}
        for sid in list(kept):
            cur = by[sid]["parent"]
            while cur in by:
                if eff & PARTIAL_CHAIN and by[cur]["state"] == "partial":
                    break
                if cur not in kept:
                    kept[cur] = "parent"
                cur = by[cur]["parent"]
        keep_all[name] = (members, kept)
    return render(keep_all, counts, len(holds), mode)


def render(keep_all, counts, n_holds, mode):
    keep_doc = {}
    prune = []
    lines = []
    tally = {"hold": 0, "parent": 0}
    partial = 0
    for name, (members, kept) in keep_all.items():
        keep_doc[name] = [{"id": s["id"], "reason": kept[s["id"]]} for s in members if s["id"] in kept]
        for s in members:
            partial += s["state"] == "partial"
            if s["id"] in kept:
                lines.append(name + "/" + s["id"] + "\n")
                if kept[s["id"]] in tally:
                    tally[kept[s["id"]]] += 1
            else:
                prune.append({"id": s["id"], "series": name, "taken": s["taken"]})
    lines.sort()
    summary = dict(counts)
    summary.update({
        "snapshots": sum(len(m) for m, _ in keep_all.values()),
        "kept": len(lines),
        "pruned": len(prune),
        "held": tally["hold"],
        "parents": tally["parent"],
        "partial": partial,
        "holds": n_holds,
        "plan_digest": hashlib.sha256("".join(lines).encode()).hexdigest(),
    })
    return {
        "keep.json": json.dumps({"series": keep_doc}, sort_keys=True, indent=2) + "\n",
        "prune.jsonl": "".join(json.dumps(p, sort_keys=True, separators=(",", ":")) + "\n" for p in prune),
        "summary.json": json.dumps(summary, sort_keys=True, indent=2) + "\n",
    }


def host_digests(keep_text):
    doc = json.loads(keep_text)
    per = {}
    for name, rows in doc["series"].items():
        host = name.split("/")[0]
        per.setdefault(host, []).extend(name + "/" + r["id"] + "\n" for r in rows)
    return {h: hashlib.sha256("".join(sorted(v)).encode()).hexdigest() for h, v in sorted(per.items())}


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


HOSTS = ["atlas", "birch", "cedar", "dune", "ember", "flint", "grove", "heron", "iris", "jade", "kelp", "lumen"]
VOLS = ["root", "home", "data", "logs", "db", "media"]
OFFSETS = [0, 330, -420, 540, -210, 60, -300, 345]
GAPS = [17, 41, 95, 200, 610, 1310, 1500, 2900, 4400, 9800, 21000, 44000]
EPOCH = datetime.datetime(2026, 1, 3, 0, 0, 0)


def fmt_taken(utc, offset, rng):
    local = utc + datetime.timedelta(minutes=offset)
    if offset == 0 and rng.below(2):
        suffix = "Z"
    else:
        sign = "+" if offset >= 0 else "-"
        suffix = "%s%02d:%02d" % (sign, abs(offset) // 60, abs(offset) % 60)
    return local.strftime("%Y-%m-%dT%H:%M:%S") + suffix


def _sid(rng, used):
    while True:
        sid = "s%012x" % (rng.next() & 0xFFFFFFFFFFFF)
        if sid not in used:
            used.add(sid)
            return sid


NOISE = ("truncated", "array", "missing", "extra", "strseq", "boolseq", "zeroseq", "badid", "baddate",
         "badoffset", "badsize", "selfparent", "badstate", "badhost", "floatsize")


def _noise(kind, rec):
    r = dict(rec)
    if kind == "truncated":
        return json.dumps(r, sort_keys=True)[:-7]
    if kind == "array":
        return json.dumps([r["id"], r["taken"]])
    if kind == "missing":
        r.pop("state")
    elif kind == "extra":
        r["note"] = "manual"
    elif kind == "strseq":
        r["seq"] = str(r["seq"])
    elif kind == "boolseq":
        r["seq"] = True
    elif kind == "zeroseq":
        r["seq"] = 0
    elif kind == "badid":
        r["id"] = r["id"].upper()
    elif kind == "baddate":
        r["taken"] = "2026-02-30" + r["taken"][10:]
    elif kind == "badoffset":
        r["taken"] = r["taken"][:19] + "+15:00"
    elif kind == "badsize":
        r["size"] = 0
    elif kind == "selfparent":
        r["parent"] = r["id"]
    elif kind == "badstate":
        r["state"] = "done"
    elif kind == "badhost":
        r["host"] = "Bad_Host"
    elif kind == "floatsize":
        r["size"] = float(r["size"])
    return json.dumps(r, sort_keys=bool(rec["seq"] % 2))


def build_corpus(seed, traps, series=4, per=10, noise=True, mode=0, hosts=None):
    rng = Rng(seed)
    used = set()
    names = rng.shuffle(HOSTS)
    host_list = names[: hosts or max(1, series // 2 + rng.below(2))]
    offsets = {h: rng.pick(OFFSETS) for h in host_list}
    pairs = []
    while len(pairs) < series:
        p = (rng.pick(host_list), rng.pick(VOLS))
        if p not in pairs:
            pairs.append(p)
    recs = []
    newest = {}
    for host, vol in pairs:
        t = EPOCH + datetime.timedelta(minutes=rng.below(20000))
        prev = None
        for _ in range(rng.between(max(3, per - 3), per + 3)):
            t = t + datetime.timedelta(minutes=rng.pick(GAPS) + rng.below(30))
            sid = _sid(rng, used)
            parent = prev if prev and rng.below(2) else None
            if parent is None and rng.below(9) == 0:
                parent = _sid(rng, used)
            recs.append({"host": host, "vol": vol, "id": sid, "taken": fmt_taken(t, offsets[host], rng),
                         "size": rng.between(1, 40), "parent": parent, "state": "partial" if rng.below(6) == 0 else "ok"})
            prev = sid
        newest[(host, vol)] = (t, recs[-1])
    lines = [dict(r) for r in recs]
    if "u5" in traps:
        for r in rng.shuffle(recs)[: rng.between(2, 4)]:
            c = dict(r)
            c["size"] = r["size"] + rng.between(1, 9)
            utc = parse_taken(r["taken"])[0] + datetime.timedelta(minutes=rng.between(70, 900))
            c["taken"] = fmt_taken(utc, offsets[r["host"]], rng)
            lines.append(c)
    if mode & RELAY_SEQLESS:
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
        for kind in rng.shuffle(NOISE)[: rng.between(7, 11)]:
            out.insert(rng.below(len(out) + 1), _noise(kind, rng.pick(lines)))
        out.insert(rng.below(len(out) + 1), "")
        out.insert(rng.below(len(out) + 1), "\xff\xfe".encode("latin-1").decode("latin-1"))
    blob = ("\n".join(out) + "\n").encode("utf-8")
    if noise:
        blob = blob.replace("\xff\xfe".encode("utf-8"), b"\xff\xfe{")
    total = sum(r["size"] for r in recs)
    default = {"hourly": rng.between(0, 3), "daily": rng.between(1, 3), "weekly": rng.between(1, 2),
               "monthly": rng.between(1, 2), "max_bytes": max(20, total // (2 * series))}
    hosts_pol = {}
    for h in host_list:
        if rng.below(2):
            hosts_pol[h] = {"hourly": rng.between(0, 2), "daily": rng.between(1, 4), "weekly": rng.between(0, 2),
                            "monthly": rng.between(0, 2), "max_bytes": rng.between(25, 70)}
    policy = json.dumps({"default": default, "hosts": hosts_pol}, sort_keys=True, indent=2) + "\n"
    rows = ["id,until,reason"]
    for (host, vol), (t, last) in newest.items():
        day = (t + datetime.timedelta(minutes=offsets[host])).date() if rng.below(2) else t.date()
        pick = rng.pick([r for r in recs if r["host"] == host and r["vol"] == vol])
        delta = 0 if "u3" in traps and rng.below(3) else rng.pick((-3, -1, 1, 4))
        rows.append("%s,%s,%s" % (pick["id"], (day + datetime.timedelta(days=delta)).isoformat(), rng.pick(("audit", "legal", "migrate"))))
    if noise:
        rows.append("S0BAD,2026-04-01,typo")
        rows.append("%s,2026-13-01,typo" % rng.pick(recs)["id"])
        rows.append("%s,2026-04-01" % rng.pick(recs)["id"])
    files = {"snapshots.jsonl": blob, "policy.json": policy.encode(), "holds.csv": ("\n".join(rows) + "\n").encode(),
             "manifest.json": json.dumps({"mode": mode}).encode()}
    files["manifest.json"] = manifest(mode, resolve(files))
    return files


def manifest(mode, reports):
    doc = {"mode": mode, "reports": {n: hashlib.sha256(t.encode()).hexdigest() for n, t in reports.items()},
           "hosts": host_digests(reports["keep.json"])}
    return (json.dumps(doc, sort_keys=True, indent=2) + "\n").encode()


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
    """A clean mode zero intake where only the readings of one rule change the reports."""
    wanted = _all_readings(rule) if wanted is None else wanted
    traps = (rule,) if rule in ("u3", "u5") else ()
    return _search(seed, 7919, 3000, lambda s: build_corpus(s, traps, series=1 + s % 3, per=4 + s % 4, noise=False),
                   lambda f: separation(f) == wanted)


def plain_case(seed):
    """A clean mode zero intake that no rule reading moves."""
    return _search(seed, 104729, 3000, lambda s: build_corpus(s, (), series=1 + s % 2, per=3 + s % 3, noise=False),
                   lambda f: not separation(f))


def bit_case(seed, bit):
    """A clean intake whose mode word is one bit, and only that bit moves the reports."""
    allowed = {("u1", "newest")} if bit == QUARTER else set()
    return _search(seed, 6151, 3000, lambda s: build_corpus(s, (), series=1 + s % 2, per=4 + s % 3, noise=False, mode=bit),
                   lambda f: bit_moves(f) == {bit} and separation(f) <= allowed)


def mixed_case(seed, series=4, per=10, need=None, mode=0):
    """A noisy intake where every needed reading and every set mode bit moves the reports."""
    need = {(r, x) for r in REFERENCE for x in WRONG_READINGS[r]} if need is None else need
    bits = {b for b in MODE_BITS if mode & b}
    return _search(seed, 15485863, 3000, lambda s: build_corpus(s, ("u3", "u5"), series=series, per=per, mode=mode),
                   lambda f: need <= separation(f) and bit_moves(f) == bits)


def noisy_plain_case(seed):
    """A damaged mode zero intake that no rule reading moves."""
    return _search(seed, 2741, 3000, lambda s: build_corpus(s, (), series=2 + s % 2, per=5 + s % 3, noise=True),
                   lambda f: not separation(f))


def empty_prune_case(seed):
    """A small clean intake where every snapshot stays, so nothing is pruned."""
    return _search(seed, 3301, 6000, lambda s: build_corpus(s, (), series=1, per=2 + s % 2, noise=False),
                   lambda f: resolve(f)["prune.jsonl"] == "" and not separation(f))


SHIPPED_SEED = 1157670525787833105 ^ 3
EXAMPLE_SEED = 1157670525787833105 ^ 1
SECOND_EXAMPLE_SEED = 1157670525787833105 ^ 2
_MODE_NEED = {("u1", "newest"), ("u2", "iso"), ("u6", "local")}
_LIVE_NEED = {("u1", "newest"), ("u2", "iso"), ("u4", "count"), ("u5", "first"), ("u5", "last"), ("u6", "local")}
CASES = {
    "plain": lambda: plain_case(0x51A7E0001),
    "noisy-plain": lambda: noisy_plain_case(0x51A7E0002),
    "screen": lambda: mixed_case(0x3A1E00007, series=4, per=9),
    "iso-u1": lambda: isolated_case(0x1D0000001, "u1"),
    "iso-u2": lambda: isolated_case(0x1D0000002, "u2"),
    "iso-u3": lambda: isolated_case(0x1D0000003, "u3"),
    "iso-u4": lambda: isolated_case(0x1D0000004, "u4"),
    "iso-u5": lambda: isolated_case(0x1D0000005, "u5"),
    "iso-u6": lambda: isolated_case(0x1D0000006, "u6"),
    "mixed-a": lambda: mixed_case(0x3A1E00001, series=4, per=10),
    "mixed-b": lambda: mixed_case(0x3A1E00002, series=5, per=10),
    "large": lambda: mixed_case(0x3A1E00003, series=14, per=26, need=_MODE_NEED, mode=0x6A),
    "mode-alpha": lambda: mixed_case(0x3A1E00011, series=5, per=11, need=_MODE_NEED, mode=0xFE),
    "mode-beta": lambda: mixed_case(0x3A1E00012, series=5, per=12, need=_MODE_NEED, mode=0xB6),
    "pair-06": lambda: mixed_case(0x3A1E00021, series=4, per=10, need=_MODE_NEED, mode=0x06),
    "pair-18": lambda: mixed_case(0x3A1E00022, series=4, per=10, need=_MODE_NEED, mode=0x18),
    "pair-60": lambda: mixed_case(0x3A1E00023, series=4, per=10, need=_MODE_NEED, mode=0x60),
    "pair-82": lambda: mixed_case(0x3A1E00024, series=4, per=10, need=_MODE_NEED, mode=0x82),
    "bit-02": lambda: bit_case(0x51A0 + KEEP_FIRST, KEEP_FIRST),
    "bit-04": lambda: bit_case(0x51A0 + QUARTER, QUARTER),
    "bit-08": lambda: bit_case(0x51A0 + DAY_ROLL, DAY_ROLL),
    "bit-10": lambda: bit_case(0x51A0 + HOLD_FOREVER, HOLD_FOREVER),
    "bit-20": lambda: bit_case(0x51A0 + RELAY_SEQLESS, RELAY_SEQLESS),
    "bit-40": lambda: bit_case(0x51A0 + PARTIAL_CHAIN, PARTIAL_CHAIN),
    "bit-80": lambda: bit_case(0x51A0 + SIZE_CAP, SIZE_CAP),
    "empty": lambda: empty_prune_case(0x0E0000001),
    "stale": lambda: mixed_case(0x3A1E00004, series=3, per=9),
    "example": lambda: mixed_case(EXAMPLE_SEED, series=4, per=10),
    "repeat": lambda: mixed_case(0x3A1E00005, series=3, per=10),
    "untouched": lambda: mixed_case(0x3A1E00006, series=3, per=10),
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
    "keep.json": '{"series": {"gone/root": [{"id": "s000000000000", "reason": "hold"}]}}\n',
    "prune.jsonl": '{"id":"s000000000001","series":"gone/root","taken":"2026-01-01T00:00:00Z"}\n',
    "summary.json": '{"kept": 99}\n',
}


def _case(label):
    if label not in _FILES:
        _FILES[label] = CASES[label]()
    return _FILES[label]


def _script(workspace):
    return os.path.join(str(workspace), "out", "prune.py")


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
    work = tempfile.mkdtemp(prefix="srp-" + label + "-")
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


@criterion(description="the pruning program exists at out/prune.py under the workspace and exits 0 on a fresh intake")
def program_is_delivered(workspace: Path) -> bool:
    try:
        run = _run(workspace, "plain")
        return run is not None and run[3] == 0
    except Exception:
        return False


@criterion(description="on a clean fresh intake with no undocumented rule in play the keep file matches byte for byte")
def plain_intake_keep_matches(workspace: Path) -> bool:
    return _report_matches(workspace, "plain", ("keep.json",))


@criterion(description="on a clean fresh intake with no undocumented rule in play the prune file matches byte for byte")
def plain_intake_prune_matches(workspace: Path) -> bool:
    return _report_matches(workspace, "plain", ("prune.jsonl",))


@criterion(description="on a clean fresh intake with no undocumented rule in play the summary matches byte for byte")
def plain_intake_summary_matches(workspace: Path) -> bool:
    return _report_matches(workspace, "plain", ("summary.json",))


@criterion(description="on a fresh intake with damaged and repeated snapshot lines the summary screening counts match")
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


@criterion(description="on a fresh intake with damaged and repeated snapshot lines all three reports match byte for byte")
def screened_intake_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "noisy-plain")


@criterion(description="an intake where only the choice of which snapshot stands for a bucket matters plans byte for byte")
def bucket_member_choice_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u1")


@criterion(description="an intake where only the day a weekly bucket starts matters plans byte for byte")
def week_start_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u2")


@criterion(description="an intake where only the comparison of a hold until date matters plans byte for byte")
def hold_expiry_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u3")


@criterion(description="an intake where only the standing of partial snapshots in buckets matters plans byte for byte")
def partial_standing_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u4")


@criterion(description="an intake where only the choice among republished copies matters plans byte for byte")
def republished_copy_choice_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u5")


@criterion(description="an intake where only the clock used to place snapshots in buckets matters plans byte for byte")
def bucket_clock_isolated(workspace: Path) -> bool:
    return _report_matches(workspace, "iso-u6")


@criterion(description="a fresh screened intake where every undocumented rule matters plans byte for byte")
def mixed_intake_alpha_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "mixed-a")


@criterion(description="a second fresh screened intake where every undocumented rule matters plans byte for byte")
def mixed_intake_beta_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "mixed-b")


@criterion(description="the plan digest in the summary agrees with the keep file the same run wrote")
def plan_digest_agrees_with_keep(workspace: Path) -> bool:
    try:
        run = _run(workspace, "mixed-a")
        if run is None or run[3] != 0:
            return False
        keep = json.loads((_artifact(run[1], "keep.json") or b"{}").decode("utf-8"))
        summary = json.loads((_artifact(run[1], "summary.json") or b"{}").decode("utf-8"))
        series = keep.get("series")
        if not isinstance(series, dict) or not series:
            return False
        text = "".join(sorted(name + "/" + row["id"] + "\n" for name, rows in series.items() for row in rows))
        return summary.get("plan_digest") == hashlib.sha256(text.encode("utf-8")).hexdigest()
    except Exception:
        return False


@criterion(description="an intake where every snapshot stays still gets an empty prune file and matching reports")
def empty_prune_file_written(workspace: Path) -> bool:
    return _report_matches(workspace, "empty")


@criterion(description="reports left in the output directory by an earlier run are replaced by the new ones")
def stale_outputs_replaced(workspace: Path) -> bool:
    return _report_matches(workspace, "stale", prefill=True)


@criterion(description="the first worked example intake reproduces its shipped reports byte for byte")
def worked_example_reproduces(workspace: Path) -> bool:
    return _report_matches(workspace, "example")


@criterion(description="a large fresh intake of fourteen series under a nonzero mode word plans byte for byte")
def large_intake_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "large")


@criterion(description="a fresh intake whose mode word is 2 alone plans byte for byte")
def mode_bit_two_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-02")


@criterion(description="a fresh intake whose mode word is 4 alone plans byte for byte")
def mode_bit_four_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-04")


@criterion(description="a fresh intake whose mode word is 8 alone plans byte for byte")
def mode_bit_eight_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-08")


@criterion(description="a fresh intake whose mode word is 16 alone plans byte for byte")
def mode_bit_sixteen_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-10")


@criterion(description="a fresh intake whose mode word is 32 alone plans byte for byte")
def mode_bit_thirty_two_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-20")


@criterion(description="a fresh intake whose mode word is 64 alone plans byte for byte")
def mode_bit_sixty_four_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-40")


@criterion(description="a fresh intake whose mode word is 128 alone plans byte for byte")
def mode_bit_one_hundred_twenty_eight_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "bit-80")


@criterion(description="a fresh screened intake under mode word 254 plans byte for byte")
def mode_word_alpha_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "mode-alpha")


@criterion(description="a second fresh screened intake under mode word 182 plans byte for byte")
def mode_word_beta_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "mode-beta")


@criterion(description="fresh screened intakes under the two bit mode words 6 and 130 both plan byte for byte")
def mode_pairs_with_bit_two_resolve(workspace: Path) -> bool:
    return _report_matches(workspace, "pair-06") and _report_matches(workspace, "pair-82")


@criterion(description="a fresh screened intake under the two bit mode word 24 plans byte for byte")
def mode_pair_twenty_four_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "pair-18")


@criterion(description="a fresh screened intake under the two bit mode word 96 plans byte for byte")
def mode_pair_ninety_six_resolves(workspace: Path) -> bool:
    return _report_matches(workspace, "pair-60")


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


@criterion(description="the delivered program carries kept snapshot ids or the plan digest of a shipped intake as literals")
def negative_hardcoded_shipped_answers(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        source = _delivered_source(workspace)
        if source is None:
            return False
        answers = []
        shipped = ((SHIPPED_SEED, 6, 12, _LIVE_NEED, 0xFE), (EXAMPLE_SEED, 4, 10, None, 0), (SECOND_EXAMPLE_SEED, 4, 10, None, 0))
        for seed, series, per, need, mode in shipped:
            reports = resolve(mixed_case(seed, series=series, per=per, need=need, mode=mode))
            rows = json.loads(reports["keep.json"])["series"].values()
            marks = sorted({row["id"] for group in rows for row in group})
            answers.append((json.loads(reports["summary.json"])["plan_digest"], marks))
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
        return any(digest in blob or sum(1 for mark in marks if mark in blob) >= 5 for digest, marks in answers)
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
criteria.plain_intake_keep_matches(weight=1)
criteria.plain_intake_prune_matches(weight=1)
criteria.plain_intake_summary_matches(weight=1)
criteria.screening_counts_match(weight=1)
criteria.screened_intake_resolves(weight=1)
criteria.bucket_member_choice_isolated(weight=1)
criteria.week_start_isolated(weight=1)
criteria.hold_expiry_isolated(weight=1)
criteria.partial_standing_isolated(weight=1)
criteria.republished_copy_choice_isolated(weight=1)
criteria.bucket_clock_isolated(weight=1)
criteria.mixed_intake_alpha_resolves(weight=1)
criteria.mixed_intake_beta_resolves(weight=1)
criteria.plan_digest_agrees_with_keep(weight=1)
criteria.empty_prune_file_written(weight=1)
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
criteria.mode_pairs_with_bit_two_resolve(weight=5)
criteria.mode_pair_twenty_four_resolves(weight=3)
criteria.mode_pair_ninety_six_resolves(weight=3)
criteria.large_intake_resolves(weight=3)
criteria.negative_input_folder_mutated(weight=-5)
criteria.negative_hardcoded_shipped_answers(weight=-5)
criteria.negative_third_party_dependency(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
