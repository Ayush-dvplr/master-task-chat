"""Verifier for the Thornvale cadastral levy engine.

The submitted engine is copied out of /app/out and run, as an unprivileged
user, against survey exports that this module rebuilds from its own seeds:
the shipped current export, an evaluation export with different seeds, book
counts, file names, datums, land uses and policy tables, and a set of small
fixtures that each switch on one rule of the retired engine. Every report the engine
writes is compared, value for value and type for type, with an independent
reference computed here in exact rational arithmetic.

Negative checks return True when the named cheat is present.
"""

from __future__ import annotations

import ast
import heapq
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

from rewardkit import criteria, criterion

# allow: SIZE_OK - QC requires one verifier module, including its independent corpus builder.

SAMPLE_SEED = 5203117796408113
EVAL_SEED = 8841920375521067
FIXTURE_SEED = 3360718842950491

OUT_DIR = Path("/app/out")
ENGINE = "derive_report.py"
SUBMISSION = OUT_DIR / ENGINE
RUN_TIMEOUT_SEC = 60
MARKET_SMALL = 24
MARKET_LARGE = 1600
CELL = 6500

REGION_NAMES = ("North", "East", "South", "West")
SEGMENT_NAMES = ("commercial", "public")
REPORTS = (
    "summary.json",
    "policy_audit.json",
    "data_quality.json",
    "region_North.json",
    "region_South.json",
    "region_West.json",
    "region_East.json",
    "segment_commercial.json",
    "segment_public.json",
)
CODES = (
    "UNKNOWN_DATUM",
    "UNKNOWN_USE",
    "MALFORMED_NUMBER",
    "OPEN_RING",
    "TOO_FEW_VERTICES",
    "SELF_INTERSECTING",
    "ZERO_AREA",
)
ALL_FEATURES = (
    "revisions",
    "voids",
    "format2",
    "datum_rev",
    "override",
    "diagonal",
    "clockwise",
    "dupes",
    "defects",
    "ruleset_switch",
    "zero_weight",
    "shuffle",
    "crlf",
    "ov_partial",
    "ov_nested",
    "ov_shared",
    "ov_cover",
    "ov_split",
    "ov_datums",
    "ov_cross",
    "ov_dead",
)
OVERLAPS = ("ov_partial", "ov_nested", "ov_shared", "ov_cover", "ov_split")


# ---------------------------------------------------------------- corpus builder

_MASK = (1 << 64) - 1


class _Rng:
    """splitmix64, integer only, identical on every platform."""

    def __init__(self, seed):
        self.state = seed & _MASK

    def next(self):
        self.state = (self.state + 0x9E3779B97F4A7C15) & _MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK
        return z ^ (z >> 31)

    def below(self, n):
        return self.next() % n

    def between(self, lo, hi):
        return lo + self.below(hi - lo + 1)

    def chance(self, num, den):
        return self.below(den) < num

    def pick(self, seq):
        seq = list(seq)
        return seq[self.below(len(seq))]

    def shuffled(self, seq):
        out = list(seq)
        for i in range(len(out) - 1, 0, -1):
            j = self.below(i + 1)
            out[i], out[j] = out[j], out[i]
        return out


_WORDS = (
    "ash", "birch", "cedar", "dell", "elm", "fen", "gorse", "heath",
    "ivy", "juniper", "knoll", "larch", "moss", "nettle", "oak", "pine",
    "quill", "rowan", "sedge", "thorn", "umber", "vale", "willow", "yarrow",
)
_DATUM_POOL = ("HLN", "BRK", "OSW", "MRD", "KST", "VLE", "CRW", "DNM")
_MARKET_DATUMS = ("MKS", "BZR", "SQR")
_TRIPLES = ((3, 4, 5), (5, 12, 13), (8, 15, 17), (7, 24, 25), (20, 21, 29), (9, 40, 41))
_BOGUS_DATUMS = ("QZD", "XNT", "OLDG")
_USE_POOL = ("AGR", "CIV", "DEP", "FRM", "HAR", "MKT", "MIL", "PRK", "RES", "SCH", "WHF", "WDL")
_BOGUS_USES = ("QRY", "ORC", "TMPX")
_WEIGHTS = ("1", "3/2", "2", "5/4", "2/3", "7/4", "3", "1/2", "9/8", "4/3")
_METHODS = ("jefferson", "webster", "huntington_hill")
_DIRS = (
    (1000, 0), (924, 383), (707, 707), (383, 924),
    (0, 1000), (-383, 924), (-707, 707), (-924, 383),
    (-1000, 0), (-924, -383), (-707, -707), (-383, -924),
    (0, -1000), (383, -924), (707, -707), (924, -383),
)
_IDENTITY = tuple(Fraction(v) for v in (1, 0, 0, 0, 1, 0))


def _dec(value):
    value = Fraction(value)
    for places in range(7):
        scaled = value * 10 ** places
        if scaled.denominator == 1:
            n = scaled.numerator
            sign = "-" if n < 0 else ""
            n = abs(n)
            if places == 0:
                return sign + str(n)
            whole, part = divmod(n, 10 ** places)
            return sign + str(whole) + "." + str(part).rjust(places, "0")
    return str(value.numerator) + "/" + str(value.denominator)


def _star_offsets(rng):
    while True:
        k = rng.between(5, 10)
        idx = sorted(rng.shuffled(range(16))[:k])
        gaps = [(idx[(i + 1) % k] - idx[i]) % 16 for i in range(k)]
        if max(gaps) < 8:
            break
    out = []
    for i in idx:
        r = rng.between(300, 2400)
        out.append((Fraction(_DIRS[i][0] * r, 1000), Fraction(_DIRS[i][1] * r, 1000)))
    return out


def _sym_offsets(rng):
    k = rng.between(2, 4)
    idx = sorted(rng.shuffled(range(8))[:k])
    radii = [rng.between(300, 2400) for _ in idx]
    half = [(Fraction(_DIRS[i][0] * r, 1000), Fraction(_DIRS[i][1] * r, 1000)) for i, r in zip(idx, radii)]
    return half + [(-x, -y) for x, y in half]


def _dense_offsets(rng, lo, hi):
    while True:
        k = rng.between(10, 16)
        idx = sorted(rng.shuffled(range(16))[:k])
        gaps = [(idx[(i + 1) % k] - idx[i]) % 16 for i in range(k)]
        if max(gaps) <= 3:
            break
    out = []
    for i in idx:
        r = rng.between(lo, hi)
        out.append((Fraction(_DIRS[i][0] * r, 1000), Fraction(_DIRS[i][1] * r, 1000)))
    return out


def _rect(x0, y0, x1, y1):
    return [(Fraction(x0), Fraction(y0)), (Fraction(x1), Fraction(y0)),
            (Fraction(x1), Fraction(y1)), (Fraction(x0), Fraction(y1))]


def _shift(pts, dx, dy):
    return [(x + dx, y + dy) for x, y in pts]


def _cluster_shapes(rng, kind, size=0):
    """Grid offsets of one planted overlap cluster, listed in claim order."""
    if kind == "partial":
        dx = rng.between(250, 550) * rng.pick((1, -1))
        dy = rng.between(250, 550) * rng.pick((1, -1))
        return [_dense_offsets(rng, 1100, 1700), _shift(_dense_offsets(rng, 1100, 1700), dx, dy)]
    if kind == "nested_hole":
        return [_dense_offsets(rng, 200, 500), _dense_offsets(rng, 1800, 2300)]
    if kind == "nested_eclipse":
        return [_dense_offsets(rng, 1800, 2300), _dense_offsets(rng, 200, 500)]
    if kind == "identical":
        first = _dense_offsets(rng, 1100, 2000)
        turn = rng.between(1, len(first) - 1)
        return [first, first[turn:] + first[:turn]]
    if kind == "shared":
        q = 2 * rng.between(250, 440)
        half = q // 2
        shapes = [_rect(0, 0, q, q), _rect(q, 0, 2 * q, q), _rect(q, q, 2 * q, 2 * q),
                  _rect(2 * q, half, 3 * q, q + half), _rect(half, 0, q + half, half),
                  [(Fraction(-q), Fraction(q)), (Fraction(0), Fraction(q)), (Fraction(-half), Fraction(2 * q))]]
        return [_shift(s, -3 * half, -q) for s in rng.shuffled(shapes)]
    if kind == "cover":
        q = 2 * rng.between(300, 600)
        half = q // 2
        shapes = [_rect(0, 0, 2 * q, 2 * q), _rect(q, 0, 3 * q, 2 * q), _rect(half, half, 5 * half, 3 * half)]
        return [_shift(s, -3 * half, -q) for s in shapes]
    if kind == "market":
        # rows and lanes run across the whole square, booths sit on top of them
        stalls = []
        pitch = 4800 // (size // 2)
        for i in range(size // 2):
            lo = -2400 + i * pitch + rng.between(0, pitch // 3)
            hi = lo + rng.between(max(1, pitch // 3), max(2, pitch * 2 // 3))
            a, b = -2400 + rng.between(0, 200), 2400 - rng.between(0, 200)
            stalls.append(_rect(a, lo, b, hi))
            stalls.append(_rect(lo, a, hi, b))
        for _ in range(size // 40):
            w, h = rng.between(60, 300), rng.between(60, 300)
            x0, y0 = rng.between(-2400, 2400 - w), rng.between(-2400, 2400 - h)
            stalls.append(_rect(x0, y0, x0 + w, y0 + h))
        return rng.shuffled(stalls)
    if kind == "triple":
        return [_shift(_dense_offsets(rng, 900, 1500), rng.between(-300, 300), rng.between(-300, 300))
                for _ in range(3)]
    k = 2 * rng.between(200, 500)
    half = k // 2
    u_shape = [(0, 0), (3 * k, 0), (3 * k, 3 * k), (2 * k, 3 * k), (2 * k, k), (k, k), (k, 3 * k), (0, 3 * k)]
    u_shape = [(Fraction(x), Fraction(y)) for x, y in u_shape]
    bar = _rect(-half, 2 * k, 7 * half, 5 * half)
    shapes = [u_shape, bar] if kind == "split_bar_later" else [bar, u_shape]
    return [_shift(s, -3 * half, -3 * half) for s in shapes]


def _apply(tf, p):
    a, b, c, d, e, f = tf
    return (a * p[0] + b * p[1] + c, d * p[0] + e * p[1] + f)


def _invert(tf, p):
    a, b, c, d, e, f = tf
    x, y = p[0] - c, p[1] - f
    det = a * e - b * d
    return ((e * x - b * y) / det, (a * y - d * x) / det)


def _scale(rng):
    if rng.chance(1, 3):
        return Fraction(rng.between(940, 1060), 1001)
    return Fraction(1000 + rng.between(-60, 60), 1000)


def _make_tf(rng):
    return (
        _scale(rng),
        Fraction(rng.between(-90, 90), 1000),
        Fraction(rng.between(-400000, 400000), 4),
        Fraction(rng.between(-90, 90), 1000),
        _scale(rng),
        Fraction(rng.between(-400000, 400000), 4),
    )


def _tf_at(datums, code, seq):
    entry = datums.get(code)
    if entry is None:
        return None
    best, best_from = entry["base"], None
    for from_book, tf in entry["revisions"]:
        if from_book <= seq and (best_from is None or from_book > best_from):
            best, best_from = tf, from_book
    return best


def _open(pts):
    pts = list(pts)
    while len(pts) > 1 and pts[-1] == pts[0]:
        pts.pop()
    return pts


def _dupe(rng, pts):
    ring = list(pts[:-1])
    mode = rng.below(3)
    if mode == 1:
        return ring + [ring[0], ring[0]]
    i = rng.below(len(ring))
    extra = [ring[i]] if mode == 0 else [ring[i], ring[i]]
    ring = ring[: i + 1] + extra + ring[i + 1:]
    return ring + [ring[0]]


def _variant(rng, value):
    """A valid spelling of value that the shipped export never uses."""
    text = _dec(value)
    sign, body = ("-", text[1:]) if text.startswith("-") else ("", text)
    if "/" in body:
        p, q = body.split("/")
        k = rng.between(2, 9)
        return sign + str(int(p) * k) + "/" + str(int(q) * k)
    if "." in body:
        return text + "0" * rng.between(1, 3)
    if rng.chance(1, 2):
        return sign + "0" * rng.between(1, 2) + body
    k = rng.between(2, 9)
    return sign + str(int(body) * k) + "/" + str(k)


def _malformed(rng, value):
    """A spelling of value that section 3 rejects although Python's Fraction accepts it."""
    text = _dec(value)
    sign, body = ("-", text[1:]) if text.startswith("-") else ("", text)
    options = [text + "e0", sign + body + "E+00"]
    if not sign:
        options.append("+" + body)
    if body.startswith("0."):
        options.append(sign + body[1:])
    if "." not in body and "/" not in body:
        options.append(text + ".")
        if len(body) >= 2:
            options.append(sign + body[0] + "_" + body[1:])
    return rng.pick(options)


def _render(rng, spec):
    """Turn a corpus description into a mapping of file name to text."""
    feats = spec["feats"]
    grammar = "grammar" in feats
    files = {}
    spoiled = set()
    if grammar:
        pool = [rec for book in spec["books"] for rec in book["recs"] if rec["kind"] == "PARCEL" and not rec.get("keep")]
        spoiled = {id(rec) for rec in pool if rec.get("spoil")}
        for rec in rng.shuffled(pool)[: max(2, len(pool) // 15)]:
            spoiled.add(id(rec))
    book_names = []
    for book in spec["books"]:
        crlf = "crlf" in feats and rng.chance(1, 2)
        sep = "  " if crlf else " "

        def line(*words):
            joined = sep.join(words)
            if grammar:
                joined = joined.replace(" ", rng.pick(["\t", " \t", "\t\t", " "]))
                roll = rng.below(9)
                if roll == 0:
                    joined += " # field note " + str(rng.below(100))
                elif roll == 1:
                    joined += "\t#re-read"
                elif roll == 2:
                    joined += "#" + rng.pick(_WORDS)
            return joined

        lines = [
            "THORNVALE SURVEY BOOK",
            line("BOOK", str(book["seq"])),
            line("FORMAT", str(book["fmt"])),
            line("DATUM", book["datum"]),
            "# transcribed by the Thornvale survey office",
        ]

        def num(value):
            if grammar and rng.chance(1, 5):
                return _variant(rng, value)
            return _dec(value)

        for rec in rng.shuffled(book["recs"]):
            roll = rng.below(8)
            if roll == 0:
                lines.append("")
            elif roll == 1:
                lines.append("# checked against the field sheet")
            if rec["kind"] == "VOID":
                lines.append(line("VOID", rec["id"], "REV", str(rec["rev"])))
                continue
            head = ["PARCEL", rec["id"], "REV", str(rec["rev"]), "USE", rec["use"]]
            if rec["datum"]:
                head += ["DATUM", rec["datum"]]
            lines.append(line(*head))
            bad_at = rng.below(2 * len(rec["pts"])) if id(rec) in spoiled else -1
            prev = None
            for i, p in enumerate(rec["pts"]):
                if book["fmt"] == 2 and prev is not None:
                    word, pair = "D", (p[0] - prev[0], p[1] - prev[1])
                else:
                    word, pair = "V", p
                toks = [num(pair[0]), num(pair[1])]
                if bad_at // 2 == i:
                    toks[bad_at % 2] = _malformed(rng, pair[bad_at % 2])
                lines.append(line(word, *toks))
                prev = p
            lines.append(line("END"))
        newline = "\r\n" if crlf else "\n"
        while True:
            name = rng.pick(_WORDS) + "-" + rng.pick(_WORDS) + ".svy"
            if name not in files:
                break
        files[name] = newline.join(lines) + newline
        book_names.append(name)
    if grammar:
        # several books may share one file, each opened by its own banner
        names = rng.shuffled(book_names)
        while len(names) >= 2:
            first, second = names.pop(), names.pop()
            files[first] += files.pop(second)
            if not rng.chance(1, 2):
                break

    def tf_json(tf):
        return dict(zip("abcdef", (_dec(v) for v in tf)))

    datum_rows = []
    for code in rng.shuffled(sorted(spec["datums"])):
        entry = spec["datums"][code]
        revs = [{"from_book": fb, "transform": tf_json(tf)} for fb, tf in rng.shuffled(entry["revisions"])]
        datum_rows.append({"code": code, "transform": tf_json(entry["base"]), "revisions": revs})
    origin = {"x": _dec(spec["origin"][0]), "y": _dec(spec["origin"][1])}
    tables = {
        "datums.json": {"grid": "TVG", "datums": datum_rows},
        "land_use.json": {"uses": spec["uses"]},
        "regions.json": {"origin": origin, "order": spec["order"], "origin_region": spec["origin_region"]},
        "policy.json": {"rulesets": spec["rulesets"]},
        "quality.json": {"precedence": spec["precedence"]},
    }
    for name, body in tables.items():
        files[name] = json.dumps(body, indent=2) + "\n"
    return files


def build_corpus(seed, feats=(), books=(4, 5), per_book=(6, 9), method=None, market=0):
    rng = _Rng(seed)
    feats = set(feats)
    nb = rng.between(*books)
    seqs = []
    seq = rng.between(2, 40)
    for _ in range(nb):
        seqs.append(seq)
        seq += rng.between(1, 5)
    origin = (Fraction(rng.between(-400000, 400000), 4), Fraction(rng.between(-400000, 400000), 4))
    if "shuffle" in feats:
        order = rng.shuffled(REGION_NAMES)
        origin_region = rng.pick(REGION_NAMES)
    else:
        order = list(REGION_NAMES)
        origin_region = "North"

    codes = rng.shuffled(_USE_POOL)[: rng.between(5, 7)]
    uses = []
    for i, code in enumerate(codes):
        segment = "commercial" if i == 0 else "public" if i == 1 else rng.pick(SEGMENT_NAMES)
        uses.append({"code": code, "segment": segment, "weight": rng.pick(_WEIGHTS)})
    if "zero_weight" in feats:
        uses[-1]["weight"] = "0"

    names = rng.shuffled(_DATUM_POOL)[: rng.between(2, 3)]
    datums = {"TVG": dict(base=_IDENTITY, revisions=[])}
    for name in names:
        datums[name] = {"base": _make_tf(rng), "revisions": []}
    if "clockwise" in feats:
        a, b, c, d, e, f = datums[names[0]]["base"]
        datums[names[0]]["base"] = (a, b, c, d, -e, f)

    book_list = []
    for i in range(nb):
        fmt = 2 if "format2" in feats and (i % 2 == 1 or rng.chance(1, 3)) else 1
        book_list.append({"seq": seqs[i], "fmt": fmt, "datum": names[i] if i < len(names) else rng.pick(names), "recs": []})
    all_seqs = list(seqs)
    if "defects" in feats:
        free = [q for q in range(seqs[0] + 1, seqs[-1]) if q not in seqs]
        orphan_seq = rng.pick(free) if free else seqs[0] - 1
        all_seqs.append(orphan_seq)
        book_list.append({"seq": orphan_seq, "fmt": 1, "datum": rng.pick(_BOGUS_DATUMS), "recs": []})

    if "datum_rev" in feats:
        for name in names:
            users = sorted(bk["seq"] for bk in book_list[:nb] if bk["datum"] == name)
            if not users:
                continue
            start = users[1] if len(users) > 1 else users[0]
            steps = [start]
            if rng.chance(1, 2):
                later = start + 1
                while later in all_seqs:
                    later += 1
                steps.append(later)
            current = datums[name]["base"]
            for step in steps:
                a, b, c, d, e, f = current
                k1 = Fraction(1000 + rng.pick((-1, 1)) * rng.between(10, 40), 1000)
                k2 = Fraction(1000 + rng.pick((-1, 1)) * rng.between(10, 40), 1000)
                current = (
                    a * k1, b, c + Fraction(rng.between(-4000, 4000), 4),
                    d, e * k2, f + Fraction(rng.between(-4000, 4000), 4),
                )
                datums[name]["revisions"].append((step, current))

    top = max(all_seqs)
    froms = [max(1, min(all_seqs) - rng.between(0, 2))]
    if "ruleset_switch" in feats:
        froms += [seqs[nb // 2], top, top + rng.between(1, 6)]
    rulesets = []
    taken = set()
    for from_book in froms:
        m = rng.between(0, 2)
        while True:
            rid = "LV-" + str(rng.between(100, 999))
            if rid not in taken:
                break
        taken.add(rid)
        rulesets.append({
            "id": rid,
            "from_book": from_book,
            "method": method or rng.pick(_METHODS),
            "house_size": rng.between(4 * m + 5, 4 * m + 36),
            "minimum_seats": m,
            "levy_total_cents": rng.between(10 ** 6, 10 ** 9),
        })
    rulesets = rng.shuffled(rulesets)

    used = set()
    present = {}
    # every shape gets its own grid cell, so land is shared only where a cluster plants it
    diag_m = rng.shuffled(range(1, 10))[:2]
    blocked = {(sx * m, sy * m) for m in diag_m for sx in (1, -1) for sy in (1, -1)} | {(0, 0)}
    cells = rng.shuffled([(cx, cy) for cx in range(-12, 13) for cy in range(-12, 13) if (cx, cy) not in blocked])

    def new_id():
        while True:
            pid = "TV-" + str(rng.between(10000, 99999))
            if pid not in used:
                used.add(pid)
                return pid

    def spot():
        cx, cy = cells.pop()
        return (origin[0] + cx * CELL + rng.between(-200, 200), origin[1] + cy * CELL + rng.between(-200, 200))

    def anchor(bi, dcode):
        tf = _tf_at(datums, dcode, book_list[bi]["seq"]) or _IDENTITY
        src = _invert(tf, spot())
        return (Fraction(round(src[0])), Fraction(round(src[1])))

    def plan(bi, dcode, target=None):
        if target is None:
            centre = anchor(bi, dcode)
            offs = _star_offsets(rng)
        else:
            centre = _invert(_tf_at(datums, dcode, book_list[bi]["seq"]), target)
            offs = _sym_offsets(rng)
        pts = [(centre[0] + dx, centre[1] + dy) for dx, dy in offs]
        return pts + [pts[0]]

    def add(bi, rec):
        rec["book"] = bi
        book_list[bi]["recs"].append(rec)
        present.setdefault(rec["id"], set()).add(bi)
        return rec

    def parcel(pid, rev, use, datum, pts):
        return {"kind": "PARCEL", "id": pid, "rev": rev, "use": use, "datum": datum, "pts": pts}

    deep = "revisions" in feats or "voids" in feats
    ordinary = []
    counter = 0
    for bi in range(nb):
        for _ in range(rng.between(*per_book)):
            counter += 1
            dcode = book_list[bi]["datum"]
            override = None
            if "override" in feats and counter % 5 == 0:
                override = rng.pick([n for n in names + ["TVG"] if n != dcode])
                dcode = override
            pts = plan(bi, dcode)
            if "clockwise" in feats and counter % 4 == 1:
                pts = pts[::-1]
            if "dupes" in feats and counter % 3 == 0:
                pts = _dupe(rng, pts)
            rev = rng.between(2, 3) if deep else 1
            ordinary.append(add(bi, parcel(new_id(), rev, rng.pick(codes), override, pts)))

    pool = rng.shuffled(ordinary)

    def grab(direction):
        for k in range(len(pool) - 1, -1, -1):
            rec = pool[k]
            if (direction > 0 and rec["book"] < nb - 1) or (direction < 0 and rec["book"] > 0):
                return pool.pop(k)
        return None

    def other_book(rec, direction):
        choices = [j for j in range(nb) if j not in present[rec["id"]] and (j - rec["book"]) * direction > 0]
        return rng.pick(choices) if choices else None

    def revise(rec, j, delta, good=True):
        pts = plan(j, rec["datum"] or book_list[j]["datum"])
        if not good:
            pts = _open(pts)
        add(j, parcel(rec["id"], rec["rev"] + delta, rng.pick(codes), rec["datum"], pts))

    reps = 2 if nb >= 6 else 1
    if "revisions" in feats:
        kinds = [("bump", 1, 1), ("tie", 1, 0), ("stale", 1, -1), ("early_bump", -1, 1)]
        if "defects" in feats:
            kinds += [("fix", 1, 1), ("break", 1, 1)]
        for _ in range(reps):
            for kind, direction, delta in kinds:
                rec = grab(direction)
                if rec is None:
                    continue
                j = other_book(rec, direction)
                if j is None:
                    continue
                if kind == "fix":
                    rec["pts"] = _open(rec["pts"])
                revise(rec, j, delta, good=kind != "break")
    if "voids" in feats:
        kinds = [("void", 1, 1), ("stale_void", 1, -1), ("tie_void", 1, 0), ("early_void", -1, 0), ("resurrect", 1, 1)]
        for _ in range(reps):
            for kind, direction, delta in kinds:
                rec = grab(direction)
                if rec is None:
                    continue
                j = other_book(rec, direction)
                if j is None:
                    continue
                add(j, {"kind": "VOID", "id": rec["id"], "rev": rec["rev"] + delta})
                if kind == "resurrect":
                    rest = [k for k in range(nb) if k not in present[rec["id"]]]
                    if rest:
                        revise(rec, rng.pick(rest), 2)

    if "diagonal" in feats:
        for n, m in enumerate(diag_m):
            t = m * CELL
            signs = [(1, 1), (1, -1), (-1, -1), (-1, 1)] + ([(0, 0)] if n == 0 else [])
            for sx, sy in signs:
                bi = rng.below(nb)
                target = (origin[0] + sx * t, origin[1] + sy * t)
                add(bi, parcel(new_id(), 1, rng.pick(codes), None, plan(bi, book_list[bi]["datum"], target)))

    def member(bi, datum, grid_pts, use=None, rev=1, pid=None):
        tf = _tf_at(datums, datum or book_list[bi]["datum"], book_list[bi]["seq"])
        pts = [_invert(tf, p) for p in grid_pts]
        if rng.chance(1, 3):
            pts = pts[::-1]
        return add(bi, parcel(pid or new_id(), rev, use or rng.pick(codes), datum, pts + [pts[0]]))

    def plant(kind, cross=False, override=False):
        shapes = _cluster_shapes(rng, kind)
        centre = spot()
        grids = [_shift(s, centre[0], centre[1]) for s in shapes]
        if cross:
            # claims run from the highest book down, so the first shape goes to the latest book
            books_used = sorted(rng.shuffled(range(nb))[: len(grids)], reverse=True)
            for bi, grid in zip(books_used, grids):
                member(bi, None, grid)
            return
        bi = rng.below(nb)
        ids = sorted(new_id() for _ in grids)
        for i, (pid, grid) in enumerate(zip(ids, grids)):
            datum = None
            if override and i == len(grids) - 1:
                datum = rng.pick([n for n in names + ["TVG"] if n != book_list[bi]["datum"]])
            member(bi, datum, grid, pid=pid)

    plantings = {
        "ov_partial": ["partial", "partial"],
        "ov_nested": ["nested_hole", "nested_eclipse", "identical", "nested_hole", "nested_eclipse", "identical"],
        "ov_shared": ["shared", "shared"],
        "ov_cover": ["cover", "triple", "cover", "triple"],
        "ov_split": ["split_bar_later", "split_u_later", "split_bar_later", "split_u_later"],
    }
    for feat, kinds in plantings.items():
        if feat in feats:
            for kind in kinds:
                plant(kind)
    if market:
        # a market square: stalls from every book stacked over one cell, surveyed on a turned frame
        mcode = rng.pick(_MARKET_DATUMS)
        p, q, r = rng.pick(_TRIPLES)
        if rng.chance(1, 2):
            p, q = q, p
        cos, sin = Fraction(p * rng.pick((1, -1)), r), Fraction(q * rng.pick((1, -1)), r)
        s = Fraction(rng.between(860, 900), 1000)
        mx, my = spot()
        datums[mcode] = {"base": (s * cos, -s * sin, mx, s * sin, s * cos, my), "revisions": []}
        for src in _cluster_shapes(rng, "market", market):
            pts = src[::-1] if rng.chance(1, 3) else list(src)
            add(rng.below(nb), parcel(new_id(), 1, rng.pick(codes), mcode, pts + [pts[0]]))["keep"] = True
    if "ov_datums" in feats:
        for kind in ("partial", "nested_hole", "partial", "nested_eclipse"):
            plant(kind, override=True)
    if "ov_cross" in feats and nb >= 2:
        for kind in ("partial", "nested_eclipse", "nested_hole", "identical", "partial"):
            plant(kind, cross=True)
    if "ov_dead" in feats and nb >= 2:
        # a parcel that never claims leaves its land open to the parcel nested inside it
        for fate in ("quarantined", "voided", "stale"):
            bi = rng.below(nb - 1)
            big, small = _cluster_shapes(rng, "nested_eclipse")
            centre = spot()
            ids = sorted(new_id() for _ in range(2))
            use = rng.pick(_BOGUS_USES) if fate == "quarantined" else None
            first = member(bi, None, _shift(big, centre[0], centre[1]), use=use, pid=ids[0])
            member(bi, None, _shift(small, centre[0], centre[1]), pid=ids[1])
            later = rng.between(bi + 1, nb - 1)
            if fate == "voided":
                add(later, {"kind": "VOID", "id": first["id"], "rev": first["rev"] + 1})
            elif fate == "stale":
                add(later, parcel(first["id"], first["rev"] + 1, rng.pick(codes), None,
                                  plan(later, book_list[later]["datum"])))

    if "defects" in feats:
        kinds = ["open", "single", "aba", "aaba", "bowtie", "touch", "zero",
                 "unknown_use", "use_bowtie", "open_bowtie", "open_zero", "open_pair",
                 "use_open", "use_few", "use_zero"]
        if "override" in feats:
            kinds += ["unknown_datum", "datum_open"]
        for kind in kinds:
            bi = rng.below(nb)
            dcode = book_list[bi]["datum"]
            s = anchor(bi, dcode)
            m = rng.between(200, 900)
            k = rng.between(100, 500)
            a_pt, b_pt = s, (s[0] + 5, s[1] + 3)
            bow = [(s[0] - m, s[1] - m), (s[0] + m, s[1] - m), (s[0] - m, s[1] + m), (s[0] + m, s[1] + m)]
            line = [a_pt, (a_pt[0] + k, a_pt[1] + 2 * k), (a_pt[0] + 3 * k, a_pt[1] + 6 * k)]
            use = rng.pick(codes)
            datum = None
            if kind in ("open", "use_open"):
                pts = _open(plan(bi, dcode))
            elif kind == "single":
                pts = [s]
            elif kind in ("aba", "use_few"):
                pts = [a_pt, b_pt, a_pt]
            elif kind == "aaba":
                pts = [a_pt, a_pt, b_pt, a_pt]
            elif kind in ("bowtie", "use_bowtie"):
                pts = bow + [bow[0]]
            elif kind == "touch":
                pent = [(0, 0), (4 * k, 0), (4 * k, 4 * k), (2 * k, 0), (0, 4 * k)]
                pts = [(s[0] + x, s[1] + y) for x, y in pent]
                pts.append(pts[0])
            elif kind in ("zero", "use_zero"):
                pts = line + [a_pt]
            elif kind == "open_bowtie":
                pts = bow
            elif kind == "open_zero":
                pts = line
            elif kind == "open_pair":
                pts = [a_pt, b_pt]
            elif kind == "unknown_datum":
                pts = plan(bi, dcode)
                datum = rng.pick(_BOGUS_DATUMS)
            elif kind == "datum_open":
                pts = _open(plan(bi, dcode))
                datum = rng.pick(_BOGUS_DATUMS)
            else:
                pts = plan(bi, dcode)
            if kind.startswith("use_") or kind == "unknown_use":
                use = rng.pick(_BOGUS_USES)
            rev = rng.between(2, 3) if deep else 1
            add(bi, parcel(new_id(), rev, use, datum, pts))
        ob = nb
        orphan_recs = [
            parcel(new_id(), 1, rng.pick(codes), None, plan(ob, "TVG")),
            parcel(new_id(), 1, rng.pick(codes), None, plan(ob, "TVG")),
            parcel(new_id(), 1, rng.pick(_BOGUS_USES), None, plan(ob, "TVG")),
            parcel(new_id(), 1, rng.pick(codes), None, _open(plan(ob, "TVG"))),
        ]
        # the orphan datum stacks UNKNOWN_DATUM on each geometric defect
        s = anchor(ob, "TVG")
        m = rng.between(200, 900)
        k = rng.between(100, 500)
        b_pt = (s[0] + 5, s[1] + 3)
        bow = [(s[0] - m, s[1] - m), (s[0] + m, s[1] - m), (s[0] - m, s[1] + m), (s[0] + m, s[1] + m)]
        line = [s, (s[0] + k, s[1] + 2 * k), (s[0] + 3 * k, s[1] + 6 * k)]
        for pts in ([s, b_pt, s], bow + [bow[0]], line + [s]):
            orphan_recs.append(parcel(new_id(), 1, rng.pick(codes), None, pts))
        if "override" in feats:
            known = rng.pick(names + ["TVG"])
            orphan_recs.append(parcel(new_id(), 1, rng.pick(codes), known, plan(ob, known)))
        for rec in orphan_recs:
            add(ob, rec)

    precedence = list(CODES)
    if "defects" in feats or "shuffle" in feats:
        precedence = rng.shuffled(precedence)

    spec = {
        "feats": feats,
        "books": book_list,
        "datums": datums,
        "uses": uses,
        "origin": origin,
        "order": order,
        "origin_region": origin_region,
        "rulesets": rulesets,
        "precedence": precedence,
    }
    return _render(rng, spec)


def build_tie_corpus(seed):
    rng = _Rng(seed)
    origin = (Fraction(rng.between(-90000, 90000)), Fraction(rng.between(-90000, 90000)))
    dist = rng.between(20000, 50000)
    side = rng.between(2500, 5000)
    offs = _sym_offsets(rng)
    use, idle = rng.shuffled(_USE_POOL)[:2]
    idle_slot = rng.between(0, 2)
    recs = []
    taken = set()
    for slot, (tx, ty) in enumerate(((0, dist), (0, -dist), (-dist, 0), (dist, side), (dist, -side))):
        while True:
            pid = "TV-" + str(rng.between(10000, 99999))
            if pid not in taken:
                break
        taken.add(pid)
        pts = [(origin[0] + tx + dx, origin[1] + ty + dy) for dx, dy in offs]
        code = idle if slot == idle_slot else use
        recs.append({"kind": "PARCEL", "id": pid, "rev": 1, "use": code, "datum": None, "pts": pts + [pts[0]], "keep": True})
    seq = rng.between(2, 90)
    spoil = dict(recs[0], id="TV-" + str(rng.between(100000, 999999)), keep=False, spoil=True)
    spec = {
        "feats": {"grammar"},
        "books": [{"seq": seq, "fmt": 1, "datum": "TVG", "recs": recs},
                  {"seq": seq - rng.between(1, 2) if seq > 3 else seq + 1, "fmt": 1, "datum": "TVG", "recs": [spoil]}],
        "datums": {"TVG": dict(base=_IDENTITY, revisions=[])},
        "uses": [
            {"code": use, "segment": rng.pick(SEGMENT_NAMES), "weight": rng.pick(_WEIGHTS)},
            {"code": idle, "segment": rng.pick(SEGMENT_NAMES), "weight": "0"},
        ],
        "origin": origin,
        "order": rng.shuffled(REGION_NAMES),
        "origin_region": rng.pick(REGION_NAMES),
        "rulesets": [{
            "id": "LV-" + str(rng.between(100, 999)),
            "from_book": seq,
            "method": rng.pick(_METHODS),
            "house_size": rng.between(6, 11),
            "minimum_seats": 0,
            "levy_total_cents": rng.between(10 ** 6, 10 ** 9),
        }],
        "precedence": list(CODES),
    }
    # East holds two equal parcels; an odd East share forces the parcel cent tie to the smaller id.
    for _ in range(64):
        files = _render(_Rng(seed ^ 0x7E57), spec)
        if reference_reports(files)["region_East.json"]["levy_cents"] % 2 == 1:
            break
        spec["rulesets"][0]["levy_total_cents"] += 1
    return files


def build_allocation_corpus(seed: int, mode: str, method: str) -> dict[str, str]:
    rng = _Rng(seed)
    origin = (Fraction(rng.between(-90000, 90000), 7), Fraction(rng.between(-90000, 90000), 11))
    side = rng.between(50, 300)
    dist = 20 * side
    order = (
        ("South", "West", "North", "East"),
        ("West", "North", "East", "South"),
        ("North", "South", "West", "East"),
    )[_METHODS.index(method)]
    match mode:
        case "seats":
            house, minimum, levy = 9, 0, 9 * rng.between(1000, 9999)
        case "levy":
            house, minimum, levy = 8, 2, 4 * (2 * rng.between(1000, 9999) + 1) + 1
        case _:
            raise ValueError(mode)
    seq = rng.between(10, 60)
    books = [{"seq": seq + 3 * i, "fmt": 1 + i % 2, "datum": "TVG", "recs": []} for i in range(4)]
    uses = rng.shuffled(_USE_POOL)[:2]
    weight = rng.pick(_WEIGHTS)
    first_id = rng.between(10000, 80000)
    for region, (tx, ty) in enumerate(((0, dist), (dist, 0), (0, -dist), (-dist, 0))):
        for pair in range(2):
            x = origin[0] + tx + (4 * pair - 2) * side
            y = origin[1] + ty
            pts = _rect(x, y, x + side, y + side)
            rec = {"kind": "PARCEL", "id": "TV-" + str(first_id + region * 20 + 1 - pair),
                   "rev": 1, "use": uses[pair], "datum": None, "pts": pts + [pts[0]], "keep": True}
            books[(region + pair) % 4]["recs"].append(rec)
    return _render(rng, {
        "feats": {"grammar", "crlf"}, "books": books,
        "datums": {"TVG": dict(base=_IDENTITY, revisions=[])},
        "uses": [{"code": code, "segment": segment, "weight": weight}
                 for code, segment in zip(uses, SEGMENT_NAMES)],
        "origin": origin, "order": order, "origin_region": order[0],
        "rulesets": [{"id": "LV-" + str(rng.between(100, 999)), "from_book": seq,
                      "method": method, "house_size": house, "minimum_seats": minimum,
                      "levy_total_cents": levy}],
        "precedence": list(CODES),
    })


FIXTURES = (
    ("base_jefferson", OVERLAPS, "jefferson", MARKET_LARGE),
    ("base_webster", OVERLAPS, "webster", MARKET_LARGE),
    ("base_huntington_hill", OVERLAPS, "huntington_hill", MARKET_LARGE),
    ("lever_cross_book_revisions", ("revisions",), None, 0),
    ("lever_void_records", ("voids",), None, 0),
    ("lever_format2_deltas", ("format2",), None, 0),
    ("lever_datum_revisions", ("datum_rev", "override"), None, 0),
    ("lever_diagonal_and_origin_centroids", ("diagonal", "shuffle"), None, 0),
    ("lever_ring_repairs", ("clockwise", "dupes"), None, 0),
    ("lever_quarantine_precedence", ("defects",), None, 0),
    ("lever_ruleset_by_last_book", ("ruleset_switch",), None, 0),
    ("lever_seat_tie_break", None, None, 0),
    ("claim_partial_overlap", ("ov_partial",), None, MARKET_LARGE),
    ("claim_nested_and_identical", ("ov_nested",), None, MARKET_LARGE),
    ("claim_shared_edges_and_corners", ("ov_shared",), None, MARKET_LARGE),
    ("claim_union_cover_and_triple", ("ov_cover", "ov_dead", "revisions", "voids", "defects", "format2"), None, MARKET_LARGE),
    ("claim_split_regions", ("ov_split", "diagonal", "datum_rev", "override", "clockwise", "dupes", "zero_weight", "shuffle", "format2", "crlf"), None, MARKET_LARGE),
    ("claim_order_by_latest_book", ("ov_cross", "revisions", "voids", "ov_dead", "ruleset_switch", "format2", "crlf", "shuffle"), None, MARKET_LARGE),
    ("claim_across_datums", ("ov_datums", "ov_dead"), None, MARKET_LARGE),
) + tuple(("allocation_" + mode + "_" + method, (mode,), method, 0)
          for mode in ("seats", "levy") for method in _METHODS)


def build_fixture(index):
    name, feats, method, market = FIXTURES[index]
    seed = FIXTURE_SEED + 7919 * (index + 1)
    if name.startswith("allocation_"):
        return build_allocation_corpus(seed, feats[0], method)
    if feats is None:
        return build_tie_corpus(seed)
    book_counts = {
        "claim_union_cover_and_triple": (11, 11),
        "claim_split_regions": (12, 12),
        "claim_order_by_latest_book": (12, 12),
    }
    return build_corpus(seed, tuple(feats) + ("grammar",), book_counts.get(name, (4, 5)), (6, 9), method, market)


def build_shipped():
    # The shipped copy keeps LF line ends; CRLF books appear only in hidden exports.
    files = build_corpus(SAMPLE_SEED, ALL_FEATURES + ("grammar",), (6, 8), (8, 12), None, MARKET_SMALL)
    return {name: text.replace("\r\n", "\n") for name, text in files.items()}


def build_eval():
    return build_corpus(EVAL_SEED, ALL_FEATURES + ("grammar",), (7, 10), (10, 16), None, MARKET_LARGE)


def rename_books(files, seed):
    rng = _Rng(seed)
    out = {}
    for name in sorted(files):
        if name.endswith(".svy"):
            while True:
                fresh = "copy-" + rng.pick(_WORDS) + "-" + str(rng.between(1000, 9999)) + ".svy"
                if fresh not in out:
                    break
            out[fresh] = files[name]
        else:
            out[name] = files[name]
    return out


# ---------------------------------------------------------------- reference reports


def _q(value):
    return str(Fraction(value))


def _orientation(p, q, r):
    v = (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return (v > 0) - (v < 0)


def _within(p, q, r):
    return min(p[0], r[0]) <= q[0] <= max(p[0], r[0]) and min(p[1], r[1]) <= q[1] <= max(p[1], r[1])


def _touch(p1, p2, p3, p4):
    d1 = _orientation(p3, p4, p1)
    d2 = _orientation(p3, p4, p2)
    d3 = _orientation(p1, p2, p3)
    d4 = _orientation(p1, p2, p4)
    if d1 * d2 < 0 and d3 * d4 < 0:
        return True
    return (
        (d1 == 0 and _within(p3, p1, p4))
        or (d2 == 0 and _within(p3, p2, p4))
        or (d3 == 0 and _within(p1, p3, p2))
        or (d4 == 0 and _within(p1, p4, p2))
    )


def _crosses_itself(ring):
    n = len(ring)
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _touch(ring[i], ring[(i + 1) % n], ring[j], ring[(j + 1) % n]):
                return True
    return False


def _twice_area(ring):
    n = len(ring)
    return sum(ring[i][0] * ring[(i + 1) % n][1] - ring[(i + 1) % n][0] * ring[i][1] for i in range(n))


def _reduce(pts):
    ring = list(pts)
    if len(ring) >= 2 and ring[-1] == ring[0]:
        ring = ring[:-1]
    kept = []
    for p in ring:
        if not kept or kept[-1] != p:
            kept.append(p)
    while len(kept) > 1 and kept[-1] == kept[0]:
        kept.pop()
    return kept


def _centroid_sums(ring):
    n = len(ring)
    sx = sy = Fraction(0)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        cr = x0 * y1 - x1 * y0
        sx += (x0 + x1) * cr
        sy += (y0 + y1) * cr
    return sx, sy


def _box(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return min(xs), min(ys), max(xs), max(ys)


def _boxes_meet(a, b):
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def _axis_box(g):
    if len(g) != 4:
        return None
    for i in range(4):
        a, b = g[i], g[(i + 1) % 4]
        if a[0] != b[0] and a[1] != b[1]:
            return None
    xs = [p[0] for p in g]
    ys = [p[1] for p in g]
    return (min(xs), min(ys), max(xs), max(ys))


def _settle_boxes(boxes):
    """Claimed area and centroid of axis aligned boxes in claim order, by one sweep over x."""
    ys = sorted({v for b in boxes for v in (b[1], b[3])})
    pos = {y: i for i, y in enumerate(ys)}
    size = len(boxes)
    cells = len(ys) - 1
    lens = [ys[c + 1] - ys[c] for c in range(cells)]
    sqs = [ys[c + 1] * ys[c + 1] - ys[c] * ys[c] for c in range(cells)]
    owner = [-1] * cells
    stacks = [[] for _ in range(cells)]
    alive = [False] * size
    own = [0] * size
    own2 = [0] * size
    since = [0] * size
    area = [0] * size
    mx2 = [0] * size
    my2 = [0] * size

    def flush(r, x):
        d = x - since[r]
        if d and own[r]:
            area[r] += own[r] * d
            mx2[r] += own[r] * (x * x - since[r] * since[r])
            my2[r] += own2[r] * d
        since[r] = x

    events = sorted([(b[0], 1, r) for r, b in enumerate(boxes)] + [(b[2], 0, r) for r, b in enumerate(boxes)])
    for x, kind, r in events:
        lo, hi = pos[boxes[r][1]], pos[boxes[r][3]]
        flush(r, x)
        if kind:
            alive[r] = True
            for c in range(lo, hi):
                heapq.heappush(stacks[c], r)
                o = owner[c]
                if o < 0 or r < o:
                    if o >= 0:
                        flush(o, x)
                        own[o] -= lens[c]
                        own2[o] -= sqs[c]
                    own[r] += lens[c]
                    own2[r] += sqs[c]
                    owner[c] = r
            continue
        alive[r] = False
        for c in range(lo, hi):
            if owner[c] != r:
                continue
            stack = stacks[c]
            while stack and not alive[stack[0]]:
                heapq.heappop(stack)
            own[r] -= lens[c]
            own2[r] -= sqs[c]
            if stack:
                nxt = stack[0]
                flush(nxt, x)
                own[nxt] += lens[c]
                own2[nxt] += sqs[c]
                owner[c] = nxt
            else:
                owner[c] = -1
    out = []
    for r in range(size):
        if area[r] == 0:
            out.append((Fraction(0), None, None))
        else:
            out.append((Fraction(area[r]), Fraction(mx2[r], 2 * area[r]), Fraction(my2[r], 2 * area[r])))
    return out


def _settle(grids, frames=None):
    """Exact claimed area and centroid of every grid polygon, listed in claim order.

    A polygon claims the part of itself that no earlier polygon covers. One vertical
    sweep per group of touching polygons hands each slab piece to its earliest cover.
    frames optionally pairs each polygon with its source ring and datum transform.
    """
    out = [None] * len(grids)
    boxes = [_box(g) for g in grids]
    parent = list(range(len(grids)))

    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    live = []
    for i in sorted(range(len(grids)), key=lambda k: boxes[k][0]):
        live = [j for j in live if boxes[j][2] >= boxes[i][0]]
        for j in live:
            if root(i) != root(j) and _boxes_meet(boxes[i], boxes[j]):
                parent[root(i)] = root(j)
        live.append(i)
    groups = {}
    for i in range(len(grids)):
        groups.setdefault(root(i), []).append(i)
    for members in groups.values():
        if len(members) == 1:
            g = grids[members[0]]
            tw = _twice_area(g)
            sx, sy = _centroid_sums(g)
            out[members[0]] = (tw / 2, sx / (3 * tw), sy / (3 * tw))
            continue
        tfs = {frames[m][1] for m in members} if frames else set()
        if len(tfs) == 1:
            # one affine frame for the whole group: settle the source rings, then map back
            tf = next(iter(tfs))
            src = [_axis_box(frames[m][0]) for m in members]
            if all(src):
                det = abs(tf[0] * tf[4] - tf[1] * tf[3])
                unit = math.lcm(*(v.denominator for b in src for v in b))
                scaled = [tuple(int(v * unit) for v in b) for b in src]
                for m, (a, cx, cy) in zip(members, _settle_boxes(scaled)):
                    if cx is None:
                        out[m] = (a * det / unit / unit, None, None)
                    else:
                        gx, gy = _apply(tf, (cx / unit, cy / unit))
                        out[m] = (a * det / unit / unit, gx, gy)
                continue
        rects = [_axis_box(grids[m]) for m in members]
        if all(rects):
            unit = math.lcm(*(v.denominator for b in rects for v in b))
            scaled = [tuple(int(v * unit) for v in b) for b in rects]
            for m, (a, cx, cy) in zip(members, _settle_boxes(scaled)):
                out[m] = (a / unit / unit, None, None) if cx is None else (a / unit / unit, cx / unit, cy / unit)
            continue
        _sweep(grids, members, out)
    return out


def _whole(v):
    return v.numerator if v.denominator == 1 else v




def _sweep(grids, members, out):
    edges = []
    xs = set()
    for rank in members:
        g = [(_whole(x), _whole(y)) for x, y in grids[rank]]
        n = len(g)
        for k in range(n):
            (ax, ay), (bx, by) = g[k], g[(k + 1) % n]
            xs.add(ax)
            if ax == bx:
                continue
            if bx < ax:
                ax, ay, bx, by = bx, by, ax, ay
            slope = Fraction(by - ay) / (bx - ax) if by != ay else 0
            edges.append((ax, ay, bx, by, slope, rank))
    by_slope = {}
    for e in edges:
        by_slope.setdefault(e[4], []).append(e)
    slopes = list(by_slope)
    for a in range(len(slopes)):
        for b in range(a + 1, len(slopes)):
            for e in by_slope[slopes[a]]:
                for f in by_slope[slopes[b]]:
                    if e[5] == f[5] or e[2] < f[0] or f[2] < e[0]:
                        continue
                    x = (f[1] - e[1] + e[4] * e[0] - f[4] * f[0]) / (e[4] - f[4])
                    if max(e[0], f[0]) <= x <= min(e[2], f[2]):
                        xs.add(_whole(x) if isinstance(x, Fraction) else x)
    xs = sorted(xs)
    edges.sort(key=lambda e: e[0])
    acc = {rank: [0, 0, 0] for rank in members}
    nxt = 0
    active = []
    for x0, x1 in zip(xs, xs[1:]):
        while nxt < len(edges) and edges[nxt][0] <= x0:
            active.append(edges[nxt])
            nxt += 1
        active = [e for e in active if e[2] >= x1]
        if not active:
            continue
        xm = Fraction(x0 + x1) / 2
        w = x1 - x0
        rows = sorted(((e[1] + e[4] * (xm - e[0]) if e[4] else e[1], e) for e in active), key=lambda r: r[0])
        inside = set()
        heap = []
        for k in range(len(rows) - 1):
            rank = rows[k][1][5]
            if rank in inside:
                inside.discard(rank)
            else:
                inside.add(rank)
                heapq.heappush(heap, rank)
            while heap and heap[0] not in inside:
                heapq.heappop(heap)
            lm, lo = rows[k]
            hm, hi = rows[k + 1]
            if not heap or hm == lm:
                continue
            if lo[4] or hi[4]:
                l0 = lo[1] + lo[4] * (x0 - lo[0])
                l1 = lo[1] + lo[4] * (x1 - lo[0])
                h0 = hi[1] + hi[4] * (x0 - hi[0])
                h1 = hi[1] + hi[4] * (x1 - hi[0])
            else:
                l0 = l1 = lm
                h0 = h1 = hm
            a = acc[heap[0]]
            a[0] += w * (hm - lm)
            a[1] += w * (x0 * (h0 - l0) + 2 * (x0 + x1) * (hm - lm) + x1 * (h1 - l1))
            a[2] += w * ((h0 * h0 - l0 * l0) + 4 * (hm * hm - lm * lm) + (h1 * h1 - l1 * l1))
    for rank in members:
        area, mx6, my12 = acc[rank]
        area = Fraction(area)
        out[rank] = (area, Fraction(mx6) / 6 / area, Fraction(my12) / 12 / area) if area else (area, None, None)


_NUMBER = re.compile(r"-?[0-9]+(?:\.[0-9]+)?|-?[0-9]+/[0-9]*[1-9][0-9]*")


def _read_records(files):
    records = []
    books = []
    for name in sorted(files):
        if not name.endswith(".svy"):
            continue
        header = None
        current = None
        for raw in files[name].split("\n"):
            tok = raw.split("#", 1)[0].split()
            if not tok:
                continue
            word = tok[0]
            if word == "THORNVALE":
                header = {"found": []}
                books.append(header)
                continue
            if word == "BOOK":
                header["seq"] = int(tok[1])
            elif word == "DATUM":
                header["datum"] = tok[1]
            elif word == "PARCEL":
                current = {"kind": "PARCEL", "id": tok[1], "rev": int(tok[3]), "use": tok[5],
                           "datum": tok[7] if len(tok) > 7 else None, "pts": []}
            elif word in ("V", "D"):
                if not all(_NUMBER.fullmatch(t) for t in tok[1:3]):
                    current["malformed"] = True
                elif current.get("malformed"):
                    pass
                elif word == "V" or not current["pts"]:
                    current["pts"].append((Fraction(tok[1]), Fraction(tok[2])))
                else:
                    last = current["pts"][-1]
                    current["pts"].append((last[0] + Fraction(tok[1]), last[1] + Fraction(tok[2])))
            elif word == "END":
                header["found"].append(current)
                current = None
            elif word == "VOID":
                header["found"].append({"kind": "VOID", "id": tok[1], "rev": int(tok[3])})
    for header in books:
        for rec in header["found"]:
            rec["book"] = header["seq"]
            rec["book_datum"] = header["datum"]
        records.append((header["seq"], header["found"]))
    return records


def _conv(t):
    return tuple(Fraction(t[k]) for k in "abcdef")


def reference_reports(files):
    tables = {name: json.loads(files[name]) for name in ("datums.json", "land_use.json", "regions.json", "policy.json", "quality.json")}
    datums = {}
    for row in tables["datums.json"]["datums"]:
        datums[row["code"]] = {"base": _conv(row["transform"]), "revisions": [(r["from_book"], _conv(r["transform"])) for r in row["revisions"]]}
    uses = {u["code"]: (u["segment"], Fraction(u["weight"])) for u in tables["land_use.json"]["uses"]}
    reg = tables["regions.json"]
    ox, oy = Fraction(reg["origin"]["x"]), Fraction(reg["origin"]["y"])
    order = list(reg["order"])
    precedence = list(tables["quality.json"]["precedence"])

    books = _read_records(files)
    seqs = sorted(seq for seq, _ in books)
    every = [rec for _, recs in books for rec in recs]
    grouped = {}
    for rec in every:
        grouped.setdefault(rec["id"], []).append(rec)
    winners = {}
    superseded = []
    for pid, recs in grouped.items():
        best = max(recs, key=lambda r: (r["rev"], r["book"]))
        winners[pid] = best
        superseded.extend(r for r in recs if r is not best)
    superseded.sort(key=lambda r: (r["id"], r["book"], r["rev"]))

    voided = sorted(pid for pid, r in winners.items() if r["kind"] == "VOID")
    quarantined = []
    counts = {code: 0 for code in precedence}
    active = []
    standing = []
    reoriented = 0
    collapsed = 0
    for pid in sorted(winners):
        rec = winners[pid]
        if rec["kind"] != "PARCEL":
            continue
        pts = rec["pts"]
        eff = rec["datum"] or rec["book_datum"]
        flags = set()
        if eff not in datums:
            flags.add("UNKNOWN_DATUM")
        if rec["use"] not in uses:
            flags.add("UNKNOWN_USE")
        if rec.get("malformed"):
            flags.add("MALFORMED_NUMBER")
        elif len(pts) < 2 or pts[-1] != pts[0]:
            flags.add("OPEN_RING")
        ring = _reduce(pts)
        if rec.get("malformed"):
            pass
        elif len(ring) < 3:
            flags.add("TOO_FEW_VERTICES")
        elif len(ring) >= 4 and _crosses_itself(ring):
            flags.add("SELF_INTERSECTING")
        elif _twice_area(ring) == 0:
            flags.add("ZERO_AREA")
        if flags:
            code = next(c for c in precedence if c in flags)
            counts[code] += 1
            quarantined.append({"id": pid, "rev": rec["rev"], "book": rec["book"], "code": code})
            continue
        tf = _tf_at(datums, eff, rec["book"])
        grid = [_apply(tf, p) for p in ring]
        tw = _twice_area(grid)
        if tw < 0:
            grid.reverse()
            tw = -tw
            reoriented += 1
        collapsed += len(pts) - 1 - len(ring)
        standing.append((rec, grid, tw / 2, (ring, tf)))

    # land goes to the latest book first, then to the lower identifier within a book
    standing.sort(key=lambda item: (-item[0]["book"], item[0]["id"]))
    eclipsed = []
    settled = _settle([item[1] for item in standing], [item[3] for item in standing])
    for (rec, grid, area, _), (claimed, cx, cy) in zip(standing, settled):
        if claimed == 0:
            eclipsed.append(rec["id"])
            continue
        dx, dy = cx - ox, cy - oy
        if dx == 0 and dy == 0:
            region = reg["origin_region"]
        elif abs(dy) > abs(dx):
            region = "North" if dy > 0 else "South"
        elif abs(dx) > abs(dy):
            region = "East" if dx > 0 else "West"
        elif dx > 0:
            region = "East" if dy > 0 else "South"
        else:
            region = "West" if dy < 0 else "North"
        segment, weight = uses[rec["use"]]
        active.append({"id": rec["id"], "rev": rec["rev"], "book": rec["book"], "use": rec["use"], "segment": segment,
                       "area": area, "claimed": claimed, "base": claimed * weight, "centroid": (cx, cy),
                       "region": region, "levy_cents": 0})
    active.sort(key=lambda p: p["id"])
    eclipsed.sort()

    top = max(seqs)
    live = [r for r in tables["policy.json"]["rulesets"] if r["from_book"] <= top]
    rs = max(live, key=lambda r: r["from_book"])
    method, house, minimum, levy = rs["method"], rs["house_size"], rs["minimum_seats"], rs["levy_total_cents"]
    base_r = {r: sum((p["base"] for p in active if p["region"] == r), Fraction(0)) for r in REGION_NAMES}
    area_r = {r: sum((p["claimed"] for p in active if p["region"] == r), Fraction(0)) for r in REGION_NAMES}
    eligible = [r for r in order if base_r[r] > 0]
    seats = {r: (minimum if r in eligible else 0) for r in REGION_NAMES}
    awards = []
    spare = max(0, house - minimum * len(eligible)) if eligible else 0
    for k in range(spare):
        best = None
        for idx, r in enumerate(order):
            if r not in eligible:
                continue
            n, b = seats[r], base_r[r]
            if method == "jefferson":
                pri = (0, b / (n + 1))
            elif method == "webster":
                pri = (0, b / (n + Fraction(1, 2)))
            elif n == 0:
                pri = (1, Fraction(0))
            else:
                pri = (0, b * b / (n * (n + 1)))
            key = (pri, b, -idx)
            if best is None or key > best[0]:
                best = (key, r, pri)
        _, r, pri = best
        seats[r] += 1
        awards.append({"seat": k + 1, "region": r, "priority": "inf" if pri[0] else _q(pri[1]), "seats_after": seats[r]})

    def largest_remainder(total, shares, tie):
        whole = sum(shares.values(), Fraction(0))
        if whole == 0:
            return {key: 0 for key in shares}
        quota = {key: Fraction(total) * w / whole for key, w in shares.items()}
        alloc = {key: q.numerator // q.denominator for key, q in quota.items()}
        left = total - sum(alloc.values())
        for key in sorted(shares, key=lambda key: (-(quota[key] - alloc[key]), tie(key)))[:left]:
            alloc[key] += 1
        return alloc

    cents_r = largest_remainder(levy, {r: Fraction(seats[r]) for r in REGION_NAMES}, order.index)
    for r in REGION_NAMES:
        members = {p["id"]: p["base"] for p in active if p["region"] == r}
        if not members:
            continue
        split = largest_remainder(cents_r[r], members, lambda pid: pid)
        for p in active:
            if p["region"] == r:
                p["levy_cents"] = split[p["id"]]

    out = {}
    out["summary.json"] = {
        "books": seqs,
        "ruleset": rs["id"],
        "method": method,
        "house_size": house,
        "records": len(every),
        "superseded": len(superseded),
        "voided": len(voided),
        "quarantined": len(quarantined),
        "active": len(active),
        "eclipsed": len(eclipsed),
        "total_area": _q(sum((p["claimed"] for p in active), Fraction(0))),
        "total_base": _q(sum((p["base"] for p in active), Fraction(0))),
        "seats": dict(seats),
        "levy_cents": dict(cents_r),
    }
    out["policy_audit.json"] = {
        "ruleset": rs["id"],
        "method": method,
        "house_size": house,
        "minimum_seats": minimum,
        "levy_total_cents": levy,
        "eligible": eligible,
        "awards": awards,
        "region_quotas": {r: _q(Fraction(levy * seats[r], house)) for r in REGION_NAMES},
    }
    out["data_quality.json"] = {
        "quarantined": quarantined,
        "counts": counts,
        "repairs": {"reoriented": reoriented, "collapsed_vertices": collapsed},
        "voided": voided,
        "eclipsed": eclipsed,
        "superseded": [{"id": r["id"], "rev": r["rev"], "book": r["book"], "kind": r["kind"]} for r in superseded],
    }
    for r in REGION_NAMES:
        rows = [p for p in active if p["region"] == r]
        out["region_" + r + ".json"] = {
            "region": r,
            "seats": seats[r],
            "levy_cents": cents_r[r],
            "area": _q(area_r[r]),
            "base": _q(base_r[r]),
            "parcels": [
                {"id": p["id"], "rev": p["rev"], "book": p["book"], "use": p["use"], "segment": p["segment"],
                 "area": _q(p["area"]), "claimed": _q(p["claimed"]), "base": _q(p["base"]),
                 "centroid": [_q(p["centroid"][0]), _q(p["centroid"][1])], "levy_cents": p["levy_cents"]}
                for p in rows
            ],
        }
    for s in SEGMENT_NAMES:
        rows = [p for p in active if p["segment"] == s]
        by_region = {}
        for r in REGION_NAMES:
            sub = [p for p in rows if p["region"] == r]
            by_region[r] = {"parcels": len(sub), "base": _q(sum((p["base"] for p in sub), Fraction(0))),
                            "levy_cents": sum(p["levy_cents"] for p in sub)}
        out["segment_" + s + ".json"] = {
            "segment": s,
            "parcel_count": len(rows),
            "area": _q(sum((p["claimed"] for p in rows), Fraction(0))),
            "base": _q(sum((p["base"] for p in rows), Fraction(0))),
            "by_region": by_region,
            "levy_cents": sum(p["levy_cents"] for p in rows),
        }
    return json.loads(json.dumps(out))


# ---------------------------------------------------------------- running the submission

_LOCK = threading.Lock()
_CACHE: dict = {}
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups", "--no-new-privs"]


def _untrusted(cmd):
    if os.name == "posix" and os.geteuid() == 0 and shutil.which("setpriv"):
        return _SETPRIV + list(cmd)
    return list(cmd)


def _write_dir(root, files):
    root.mkdir(parents=True, exist_ok=True)
    os.chmod(root, 0o755)
    for name, text in files.items():
        path = root / name
        with open(path, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        os.chmod(path, 0o644)


_STRAYS: list = []
_BASELINE: set = set()


def _dropped_uid():
    if _untrusted([]) == []:
        return None
    try:
        import pwd

        return pwd.getpwnam("nobody").pw_uid
    except (ImportError, KeyError):
        return None


def _owned_paths(uid, keep):
    found = set()
    for top in ("/", "/dev/shm"):
        for root, dirs, files in os.walk(top):
            if root == "/":
                dirs[:] = [d for d in dirs if d not in ("proc", "sys", "dev")]
            descend = []
            for name in dirs:
                path = os.path.join(root, name)
                if keep and (path == keep or path.startswith(keep + os.sep)):
                    continue
                try:
                    owned = os.lstat(path).st_uid == uid
                except OSError:
                    continue
                if owned:
                    found.add(path)
                else:
                    descend.append(name)
            dirs[:] = descend
            for name in files:
                path = os.path.join(root, name)
                if keep and path.startswith(keep + os.sep):
                    continue
                try:
                    if os.lstat(path).st_uid == uid:
                        found.add(path)
                except OSError:
                    continue
    return found


def _reap(uid):
    for _ in range(50):
        alive = False
        try:
            entries = os.listdir("/proc")
        except OSError:
            return
        for entry in entries:
            if not entry.isdigit():
                continue
            try:
                with open("/proc/" + entry + "/status", encoding="utf-8") as fh:
                    fields = dict(line.split(":", 1) for line in fh if ":" in line)
            except OSError:
                continue
            try:
                owner = int(fields.get("Uid", "-1").split()[0])
            except (ValueError, IndexError):
                continue
            if owner == uid and not fields.get("State", "").strip().startswith("Z"):
                alive = True
                try:
                    os.kill(int(entry), signal.SIGKILL)
                except OSError:
                    pass
        if not alive:
            return


def _seal(out_dir):
    if not out_dir.is_dir() or out_dir.is_symlink():
        return
    for root, dirs, files in os.walk(out_dir):
        for name in dirs + files:
            try:
                os.lchown(os.path.join(root, name), 0, 0)
            except OSError:
                pass
    try:
        os.lchown(out_dir, 0, 0)
        os.chmod(out_dir, 0o700)
    except OSError:
        pass


def _contain(out_dir, finished):
    uid = _dropped_uid()
    if uid is None:
        return
    _reap(uid)
    for path in sorted(_owned_paths(uid, str(out_dir)) - _BASELINE):
        if finished:
            _STRAYS.append(path)
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path, ignore_errors=True)
            else:
                os.unlink(path)
        except OSError:
            pass
    _seal(out_dir)


def _run_program(code_dir, data_dir, out_dir, hashseed, create=True):
    if create:
        out_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(out_dir, 0o777)
    else:
        out_dir.parent.mkdir(parents=True, exist_ok=True)
        os.chmod(out_dir.parent, 0o777)
    program = code_dir / ENGINE
    os.chmod(program, 0o644)
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONHASHSEED": hashseed,
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "HOME": "/tmp",
    }
    proc = subprocess.Popen(
        _untrusted([sys.executable, "-s", "-P", str(program), str(data_dir), str(out_dir)]),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
        cwd=str(code_dir),
        start_new_session=True,
    )
    try:
        proc.wait(timeout=RUN_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        proc.wait()
        _contain(out_dir, finished=False)
        return None
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
    result = {}
    for name in REPORTS:
        try:
            result[name] = (out_dir / name).read_bytes()
        except OSError:
            result[name] = None
    _contain(out_dir, finished=True)
    return result


def _same(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _decode(blob):
    if blob is None:
        return None
    try:
        return json.loads(blob.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None


def _state():
    with _LOCK:
        if "error" in _CACHE:
            raise RuntimeError("grading state unavailable") from _CACHE["error"]
        if "state" not in _CACHE:
            try:
                _CACHE["state"] = _build_state()
            except Exception as exc:
                _CACHE["error"] = exc
                raise RuntimeError("grading state unavailable") from exc
        return _CACHE["state"]


def _build_state():
    st = SimpleNamespace()
    shipped = build_shipped()
    evaluation = build_eval()
    twin = rename_books(evaluation, EVAL_SEED ^ 0x5A5A)
    fixtures = [build_fixture(i) for i in range(len(FIXTURES))]
    st.shipped_ref = reference_reports(shipped)
    st.eval_ref = reference_reports(evaluation)
    st.fixture_ref = {FIXTURES[i][0]: reference_reports(fixtures[i]) for i in range(len(FIXTURES))}
    st.source = SUBMISSION.read_text(encoding="utf-8", errors="replace")

    work = Path(tempfile.mkdtemp(prefix="thornvale-grade-"))
    os.chmod(work, 0o755)
    code = work / "code"
    code.mkdir()
    os.chmod(code, 0o755)
    shutil.copyfile(SUBMISSION, code / ENGINE)
    os.chmod(code / ENGINE, 0o644)
    _write_dir(work / "eval", evaluation)
    _write_dir(work / "twin", twin)
    _write_dir(work / "shipped", shipped)
    (work / "fixtures").mkdir()
    os.chmod(work / "fixtures", 0o755)
    for i, files in enumerate(fixtures):
        _write_dir(work / "fixtures" / FIXTURES[i][0], files)
    runs = work / "runs"
    runs.mkdir()
    os.chmod(runs, 0o755)
    uid = _dropped_uid()
    if uid is not None:
        _BASELINE.update(_owned_paths(uid, None))

    st.main = _run_program(code, work / "eval", runs / "main", "0")
    st.twin = st.h1 = st.h2 = None
    if st.main is not None:
        st.twin = _run_program(code, work / "twin", runs / "twin", "0")
        st.h1 = _run_program(code, work / "eval", runs / "h1", "1")
        st.h2 = _run_program(code, work / "eval", runs / "h2", "2")
    st.fresh = _run_program(code, work / "shipped", work / "fresh" / "out", "0", create=False)
    st.fixture_runs = {}
    for name, _, _, _ in FIXTURES:
        st.fixture_runs[name] = _run_program(code, work / "fixtures" / name, runs / name, "0")
    st.strays = list(_STRAYS)
    return st


def _reports(run):
    if run is None:
        return None
    return {name: _decode(run.get(name)) for name in REPORTS}


def _all_match(run, ref):
    got = _reports(run)
    if got is None:
        return False
    return all(_same(got[name], ref[name]) for name in REPORTS)


def _fixture_ok(name):
    st = _state()
    return _all_match(st.fixture_runs.get(name), st.fixture_ref[name])


def _claim_view(reports):
    claims = {k: [v[1].get("claimed"), v[1].get("centroid")] for k, v in _parcel_rows(reports).items()}
    return claims, reports["data_quality.json"].get("eclipsed")


def _claims_ok(name):
    st = _state()
    got = _reports(st.fixture_runs.get(name))
    if got is None:
        return False
    have, have_gone = _claim_view(got)
    want, want_gone = _claim_view(st.fixture_ref[name])
    return have.keys() == want.keys() and _same(have, want) and _same(have_gone, want_gone)


def _main_report(name):
    got = _reports(_state().main)
    if got is None:
        return None
    return got[name]


def _parcel_rows(reports):
    rows = {}
    for region in REGION_NAMES:
        body = reports["region_" + region + ".json"]
        for row in body["parcels"]:
            rows[row["id"]] = (region, row)
    return rows


def _skeleton(value):
    if isinstance(value, dict):
        return {k: _skeleton(v) for k, v in value.items()}
    if isinstance(value, list):
        kinds = sorted({json.dumps(_skeleton(v), sort_keys=True) for v in value})
        return ["list"] + kinds
    return type(value).__name__


# ---------------------------------------------------------------- criteria


@criterion(description="The reports left in /app/out are the nine reports that /app/out/derive_report.py writes when it is run again on the shipped sample export into an out_dir that does not exist yet.")
def shipped_outputs_present(workspace) -> bool:
    try:
        st = _state()
        fresh = _reports(st.fresh)
        if fresh is None:
            return False
        for name in REPORTS:
            on_disk = _decode((OUT_DIR / name).read_bytes())
            if on_disk is None or not _same(on_disk, fresh[name]):
                return False
        return True
    except Exception:
        return False


@criterion(description="Run on the shipped current export, the engine writes all nine reports exactly as the retired engine would.")
def shipped_reports_match_reference(workspace) -> bool:
    try:
        return _all_match(_state().fresh, _state().shipped_ref)
    except Exception:
        return False


@criterion(description="On an export with single revisions, no defects and planted overlap clusters of every shape, the engine reproduces every report when the ruleset in force uses the jefferson divisor method.")
def base_jefferson(workspace) -> bool:
    try:
        return _fixture_ok("base_jefferson")
    except Exception:
        return False


@criterion(description="On an export with single revisions, no defects and planted overlap clusters of every shape, the engine reproduces every report when the ruleset in force uses the webster divisor method.")
def base_webster(workspace) -> bool:
    try:
        return _fixture_ok("base_webster")
    except Exception:
        return False


@criterion(description="On an export with single revisions, no defects and planted overlap clusters of every shape, the engine reproduces every report when the ruleset in force uses the huntington_hill method, including the inf priority for regions holding no seat.")
def base_huntington_hill(workspace) -> bool:
    try:
        return _fixture_ok("base_huntington_hill")
    except Exception:
        return False


@criterion(description="When parcels are revised across books, including equal revision numbers in a later book, stale lower revisions and higher revisions placed in earlier books, every report matches the rule that the highest revision wins and a later book wins a tie.")
def lever_cross_book_revisions(workspace) -> bool:
    try:
        return _fixture_ok("lever_cross_book_revisions")
    except Exception:
        return False


@criterion(description="When VOID records retire, fail to retire, tie with or are overtaken by parcel records, every report matches the reference, including the voided and superseded lists.")
def lever_void_records(workspace) -> bool:
    try:
        return _fixture_ok("lever_void_records")
    except Exception:
        return False


@criterion(description="When some books use format 2, whose D lines are offsets from the previous vertex, every report matches the reference.")
def lever_format2_deltas(workspace) -> bool:
    try:
        return _fixture_ok("lever_format2_deltas")
    except Exception:
        return False


@criterion(description="When datum transforms are revised from a given book onward, with the revision applying to that book itself, and some parcel records override the book datum, every report matches the reference.")
def lever_datum_revisions(workspace) -> bool:
    try:
        return _fixture_ok("lever_datum_revisions")
    except Exception:
        return False


@criterion(description="When centroids fall exactly on a diagonal through the regional origin or on the origin itself, and the region order is not the default, every report matches the clockwise tie rule and the origin region from the tables.")
def lever_diagonal_and_origin_centroids(workspace) -> bool:
    try:
        return _fixture_ok("lever_diagonal_and_origin_centroids")
    except Exception:
        return False


@criterion(description="When rings are listed clockwise, a datum mirrors the plane or rings repeat vertices including a doubled closing vertex, every report matches the reference, including both repair counters.")
def lever_ring_repairs(workspace) -> bool:
    try:
        return _fixture_ok("lever_ring_repairs")
    except Exception:
        return False


@criterion(description="When defective parcels carry several defects at once, a whole book uses an unknown datum and the precedence list is permuted, every report matches the reference, including the reported quarantine code for each parcel.")
def lever_quarantine_precedence(workspace) -> bool:
    try:
        return _fixture_ok("lever_quarantine_precedence")
    except Exception:
        return False


@criterion(description="When the policy table holds several rulesets, including one that starts after the last book, every report uses the ruleset with the greatest from_book not after the highest book number present.")
def lever_ruleset_by_last_book(workspace) -> bool:
    try:
        return _fixture_ok("lever_ruleset_by_last_book")
    except Exception:
        return False


@criterion(description="Across all three apportionment methods, exact equal-base seat priorities follow the runtime region order rather than alphabetical order, including zero-seat huntington_hill priorities. Full reports must match on symmetric mixed-format exports and the original seat/parcel-cent tie export.")
def lever_seat_tie_break(workspace) -> bool:
    try:
        return _fixture_ok("lever_seat_tie_break") and all(
            _fixture_ok("allocation_seats_" + method) for method in _METHODS
        )
    except Exception:
        return False


@criterion(description="When two parcels share part of their land, the later claimant keeps exactly its polygon minus the earlier claim, with the exact area and centroid of what remains.")
def claim_partial_overlap(workspace) -> bool:
    try:
        return _claims_ok("claim_partial_overlap")
    except Exception:
        return False


@criterion(description="When a small parcel lies inside a large one or two parcels have identical rings listed from different starting vertices, the claimed areas, claimed centroids and eclipsed list match the reference.")
def claim_nested_and_identical(workspace) -> bool:
    try:
        return _claims_ok("claim_nested_and_identical")
    except Exception:
        return False


@criterion(description="When parcels meet along whole edges, part edges or single corners and one rectangle straddles a seam, shared boundaries claim no land and every claimed area, claimed centroid and the eclipsed list match the reference.")
def claim_shared_edges_and_corners(workspace) -> bool:
    try:
        return _claims_ok("claim_shared_edges_and_corners")
    except Exception:
        return False


@criterion(description="On a twelve-book export with union-only cover, triple overlaps and a large turned market, revisions, voids and quarantined records must be resolved before claiming land; all nine reports must match the reference within 60 seconds.")
def claim_union_cover_and_triple(workspace) -> bool:
    try:
        return _fixture_ok("claim_union_cover_and_triple")
    except Exception:
        return False


@criterion(description="On a twelve-book export with disconnected claimed pieces and a large turned market, revised and overridden datums, ring repairs and exact regional boundaries must propagate through membership, zero-weight bases and levy allocation; all nine reports must match the reference within 60 seconds.")
def claim_split_regions(workspace) -> bool:
    try:
        return _fixture_ok("claim_split_regions")
    except Exception:
        return False


@criterion(description="On a twelve-book export with cross-book overlaps and a large turned market, revision and void reconciliation precede latest-book claim ordering, while the highest book selects the active ruleset; mixed formats and line endings must yield all nine reference reports within 60 seconds.")
def claim_order_by_latest_book(workspace) -> bool:
    try:
        return _fixture_ok("claim_order_by_latest_book")
    except Exception:
        return False


@criterion(description="When overlapping parcels are surveyed in different datums, or a quarantined, voided or superseded parcel would have covered another, only standing parcels claim land and the claimed values and eclipsed list match the reference.")
def claim_across_datums(workspace) -> bool:
    try:
        return _claims_ok("claim_across_datums")
    except Exception:
        return False


@criterion(description="On the evaluation export the summary report lists the reference book numbers, record count, active and eclipsed parcel counts, total claimed area and total base.")
def eval_summary(workspace) -> bool:
    try:
        got = _main_report("summary.json")
        want = _state().eval_ref["summary.json"]
        return isinstance(got, dict) and all(_same(got.get(k), want[k]) for k in ("books", "records", "active", "eclipsed", "total_area", "total_base"))
    except Exception:
        return False


@criterion(description="On the evaluation export every active parcel row, including its containing region and every reported field, exactly matches the reference row.")
def eval_parcel_rows(workspace) -> bool:
    try:
        have = _parcel_rows(_reports(_state().main))
        want = _parcel_rows(_state().eval_ref)
        if have.keys() != want.keys():
            return False
        return all(have[k][0] == want[k][0] and _same(have[k][1], want[k][1]) for k in want)
    except Exception:
        return False


@criterion(description="On the evaluation export each region report has the exact region name, seat count, levy, claimed area and base totals of the reference.")
def eval_region_totals(workspace) -> bool:
    try:
        got = _reports(_state().main)
        ref = _state().eval_ref
        for region in REGION_NAMES:
            body = got["region_" + region + ".json"]
            want = ref["region_" + region + ".json"]
            if not isinstance(body, dict):
                return False
            if not all(_same(body.get(field), want[field]) for field in ("region", "seats", "levy_cents", "area", "base")):
                return False
        return True
    except Exception:
        return False


@criterion(description="On three mixed-format allocation exports, minimum seats fill the house so seat ties cannot mask levy behavior; equal region remainders follow table order, equal parcel remainders follow identifier order, and all nine reports match the reference.")
def eval_levy_allocations(workspace) -> bool:
    try:
        return all(_fixture_ok("allocation_levy_" + method) for method in _METHODS)
    except Exception:
        return False


@criterion(description="On the evaluation export both segment reports match the reference.")
def eval_segment_reports(workspace) -> bool:
    try:
        ref = _state().eval_ref
        return all(_same(_main_report("segment_" + s + ".json"), ref["segment_" + s + ".json"]) for s in SEGMENT_NAMES)
    except Exception:
        return False


@criterion(description="On the evaluation export the policy audit matches the reference, including the ruleset in force, eligible regions, every seat award with its priority and the region quotas.")
def eval_seat_awards(workspace) -> bool:
    try:
        return _same(_main_report("policy_audit.json"), _state().eval_ref["policy_audit.json"])
    except Exception:
        return False


@criterion(description="On the evaluation export the data quality report lists the same quarantined parcels with the same codes, the same counts, the same voided ids and the same superseded records as the reference.")
def eval_quarantine_report(workspace) -> bool:
    try:
        got = _main_report("data_quality.json")
        want = _state().eval_ref["data_quality.json"]
        return isinstance(got, dict) and all(_same(got.get(k), want[k]) for k in ("quarantined", "counts", "voided", "superseded"))
    except Exception:
        return False


@criterion(description="On the evaluation export the repair counters for reoriented rings and collapsed vertices match the reference.")
def eval_repair_counters(workspace) -> bool:
    try:
        got = _main_report("data_quality.json")
        return isinstance(got, dict) and _same(got.get("repairs"), _state().eval_ref["data_quality.json"]["repairs"])
    except Exception:
        return False


@criterion(description="On the evaluation export every report uses the same JSON value types as the reference, with exact values as strings and counts, seats and cents as integers.")
def eval_exact_value_types(workspace) -> bool:
    try:
        got = _reports(_state().main)
        ref = _state().eval_ref
        return got is not None and all(got[n] is not None and _skeleton(got[n]) == _skeleton(ref[n]) for n in REPORTS)
    except Exception:
        return False


@criterion(description="Cheat detector, true when the engine source contains at least three of the long exact area, base or centroid strings from the shipped sample answers.")
def negative_hardcoded_sample_answers(workspace) -> bool:
    try:
        # inverted polarity: True means sample answers are pasted into the engine
        st = _state()
        found = set()
        for r in REGION_NAMES:
            for row in st.shipped_ref["region_" + r + ".json"]["parcels"]:
                for value in [row["area"], row["base"]] + row["centroid"]:
                    if len(value) >= 12:
                        found.add(value)
        return sum(1 for value in found if value in st.source) >= 3
    except Exception:
        return False


@criterion(description="Cheat detector, true when the same evaluation export with every survey book renamed makes the engine write different reports, while runs with different hash seeds agree.")
def negative_filename_dependent_behaviour(workspace) -> bool:
    try:
        # inverted polarity: True means the engine keys its behaviour on file names
        st = _state()
        if st.main is None:
            return False
        if st.h1 != st.main or st.h2 != st.main:
            return False
        base = _reports(st.main)
        twin = _reports(st.twin)
        if twin is None:
            return True
        return any(not _same(base[n], twin[n]) for n in REPORTS)
    except Exception:
        return False


@criterion(description="Cheat detector, true when repeated evaluation runs with different hash seeds write different report bytes.")
def negative_nondeterministic_output(workspace) -> bool:
    try:
        # inverted polarity: True means output bytes depend on the hash seed
        st = _state()
        if st.main is None:
            return False
        return any(h != st.main for h in (st.h1, st.h2))
    except Exception:
        return False


@criterion(description="Rule breach detector, true when /app/out/derive_report.py imports a top level module that is not part of the Python standard library, by an import statement or by a literal name passed to __import__ or import_module.")
def negative_engine_imports_non_stdlib(workspace) -> bool:
    try:
        # inverted polarity: True means a third party import was found
        tree = ast.parse(SUBMISSION.read_text(encoding="utf-8", errors="replace"))
        names = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.extend(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.append(node.module.split(".")[0])
            elif isinstance(node, ast.Call):
                fn = node.func
                fname = fn.id if isinstance(fn, ast.Name) else fn.attr if isinstance(fn, ast.Attribute) else ""
                if fname in ("__import__", "import_module") and node.args:
                    arg = node.args[0]
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        names.append(arg.value.split(".")[0])
        return any(n not in sys.stdlib_module_names and n != "__future__" for n in names)
    except Exception:
        return False


@criterion(description="Rule breach detector, true when a finished grading run of /app/out/derive_report.py leaves a file or directory behind outside the out_dir it was given.")
def negative_writes_outside_out_dir(workspace) -> bool:
    try:
        # inverted polarity: True means a stray path owned by the run was found
        return bool(getattr(_state(), "strays", None))
    except Exception:
        return False


criteria.shipped_outputs_present(weight=1)
criteria.shipped_reports_match_reference(weight=3)
criteria.base_jefferson(weight=3)
criteria.base_webster(weight=3)
criteria.base_huntington_hill(weight=3)
criteria.lever_cross_book_revisions(weight=1)
criteria.lever_void_records(weight=1)
criteria.lever_format2_deltas(weight=1)
criteria.lever_datum_revisions(weight=1)
criteria.lever_diagonal_and_origin_centroids(weight=1)
criteria.lever_ring_repairs(weight=1)
criteria.lever_quarantine_precedence(weight=1)
criteria.lever_ruleset_by_last_book(weight=1)
criteria.lever_seat_tie_break(weight=5)
criteria.claim_partial_overlap(weight=5)
criteria.claim_nested_and_identical(weight=5)
criteria.claim_shared_edges_and_corners(weight=3)
criteria.claim_union_cover_and_triple(weight=5)
criteria.claim_split_regions(weight=5)
criteria.claim_order_by_latest_book(weight=5)
criteria.claim_across_datums(weight=5)
criteria.eval_summary(weight=3)
criteria.eval_parcel_rows(weight=5)
criteria.eval_region_totals(weight=5)
criteria.eval_levy_allocations(weight=5)
criteria.eval_segment_reports(weight=1)
criteria.eval_seat_awards(weight=3)
criteria.eval_quarantine_report(weight=3)
criteria.eval_repair_counters(weight=1)
criteria.eval_exact_value_types(weight=1)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_engine_imports_non_stdlib(weight=-3)
criteria.negative_writes_outside_out_dir(weight=-3)
