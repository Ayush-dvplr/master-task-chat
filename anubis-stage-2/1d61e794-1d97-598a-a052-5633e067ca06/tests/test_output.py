"""Verifier for the VDL-26 precise levelling recomputation task.

The first half of this module is the seeded corpus generator together with the reference
derivation of every report; the grading harness regenerates the shipped campaign and nine held-out
campaigns from it, runs the delivered program on fresh copies, and compares the reports under the
output contract. Nothing here reads the agent's input directory.
"""
from __future__ import annotations

# ============================================================================ generator core
# Seeded corpus generator for the VDL-26 precise levelling recomputation task. Every name in
# this module starts with _G so the whole module can be embedded verbatim in the verifier,
# which regenerates held-out corpora at grade time and derives their expected reports.
import csv as _Gcsv
import hashlib as _Ghashlib
import io as _Gio
import json as _Gjson
import math as _Gmath
import re as _Gre
import sqlite3 as _Gsqlite3
import zipfile as _Gzipfile
import zlib as _Gzlib
from datetime import date as _Gdate, datetime as _Gdt, timedelta as _Gtd, timezone as _Gtz
from fractions import Fraction as _GF
from pathlib import Path as _GPath

_GUTC = _Gtz.utc
_GM64 = 0xFFFFFFFFFFFFFFFF

_GDEFAULT = {
    "campaign": "VDL-26",
    "prev_campaign": "VDL-24",
    "agency": "Vellmar Delta Geodetic Office",
    "zone_rule": "eu",
    "base_offset": 60,
    "start": "2026-09-07",
    "days": 52,
    "ref_date": "2026-11-02",
    "ref24": "2024-10-14",
    "date1904": True,
    "n_blocks": 8,
    "junctions": [5, 7],
    "line_sections": [2, 5],
    "spurs": [1, 2],
    "rev_rate": 0.07,
    "void_rate": 0.025,
    "dup_rate": 0.05,
    "conflict_rate": 0.012,
    "void_runs": 3,
    "gap_runs": 3,
    "rerun_rate": 0.11,
    "reject_sections": 2,
    "outliers": 4,
    "pair_outliers": 1,
    "noise_scale": "1.30",
    "mixed_pairs": False,
    "feet_share": 1,
    "pdf_octal": False,
    "pdf_td": False,
    "xlsx_runs": False,
    "xlsx_no_r": False,
    "yaml_flow": False,
    "tol": {"I": ["3.0", "4.0"], "II": ["4.5", "6.0"], "III": ["6.0", "8.0"]},
    "tol_erratum": ["II", "5.0"],
    "sigma": {"I": "0.70", "II": "1.00", "III": "1.50"},
    "k_crit": "3.29",
    "r_min": 2,
    "max_removals": 3,
    "c_limit": "3.000",
    "k_ref": "0.13",
    "rod_types": {"INV-F": ["FULL", "0.80"], "INV-H": ["HALF", "1.10"], "INV-B": ["FULL", "0.60"]},
    "alert": "-8.00",
    "k_rate": "2.00",
    "earth_radius": 6371000,
    "fallback_temp": "18.0",
    "met_max_gap": 30,
    "cert_sheet": "Certs_2026B",
    "control_drop": 0,
    "unconstrained_block": False,
    "demote_control": True,
    "extra_journal": 0,
    "extra_rulings": 0,
    "spring_test_tie": False,
    "rename": False,
}


class _GRng:
    """splitmix64 stream; stable across Python releases and platforms."""

    def __init__(self, seed: int):
        self.s = seed & _GM64

    def _next(self) -> int:
        self.s = (self.s + 0x9E3779B97F4A7C15) & _GM64
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _GM64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _GM64
        return z ^ (z >> 31)

    def random(self) -> float:
        return (self._next() >> 11) / 9007199254740992.0

    def randint(self, a: int, b: int) -> int:
        return a + self._next() % (b - a + 1)

    def choice(self, seq):
        return seq[self.randint(0, len(seq) - 1)]

    def shuffle(self, x) -> None:
        for i in range(len(x) - 1, 0, -1):
            j = self.randint(0, i)
            x[i], x[j] = x[j], x[i]

    def sample(self, seq, k: int) -> list:
        pool = list(seq)
        self.shuffle(pool)
        return pool[:k]

    def normal(self) -> float:
        return sum(self.random() for _ in range(12)) - 6.0


def _G_rng(seed: int, tag: str) -> _GRng:
    h = _Ghashlib.blake2b(f"{seed}:{tag}".encode(), digest_size=8).digest()
    return _GRng(int.from_bytes(h, "big"))


def _Gcfg(over, seed: int) -> dict:
    cfg = _Gjson.loads(_Gjson.dumps(_GDEFAULT))
    for k, v in (over or {}).items():
        cfg[k] = v
    cfg["seed"] = seed
    return cfg


# ---------------------------------------------------------------------------- exact numbers
def _Gsqrtf(x: float) -> float:
    return _Gmath.sqrt(x)


def _GQ(text) -> _GF:
    """Exact rational from a decimal string or int."""
    return _GF(str(text).strip())


def _Gq(x: _GF, dp: int) -> _GF:
    """Round half to even to dp decimal places."""
    scale = 10 ** dp
    y = _GF(x) * scale
    n, r = divmod(y.numerator, y.denominator)
    twice = 2 * r
    if twice > y.denominator or (twice == y.denominator and n % 2 == 1):
        n += 1
    return _GF(n, scale)


def _Gs(x: _GF, dp: int) -> str:
    """Fixed-point text of x rounded half to even to dp places; never a negative zero."""
    y = _Gq(x, dp) * 10 ** dp
    n = y.numerator
    neg = n < 0
    n = abs(n)
    if dp == 0:
        body = str(n)
    else:
        digits = str(n).rjust(dp + 1, "0")
        body = digits[:-dp] + "." + digits[-dp:]
    return ("-" if neg and n else "") + body


def _Gsqrt_q(x: _GF, dp: int) -> _GF:
    """sqrt(x) rounded half to even to dp places, exactly."""
    from math import isqrt
    y = _GF(x) * 10 ** (2 * dp)
    if y < 0:
        raise ValueError("negative")
    n = isqrt(y.numerator // y.denominator)
    half = (_GF(2 * n + 1, 2)) ** 2
    if y > half or (y == half and n % 2 == 1):
        n += 1
    return _GF(n, 10 ** dp)


# ---------------------------------------------------------------------------- site clock
def _G_last_sunday(y: int, m: int) -> int:
    d = _Gdate(y, m + 1, 1) - _Gtd(days=1) if m < 12 else _Gdate(y, 12, 31)
    while d.weekday() != 6:
        d -= _Gtd(days=1)
    return d.day


def _G_nth_sunday(y: int, m: int, n: int) -> int:
    d = _Gdate(y, m, 1)
    while d.weekday() != 6:
        d += _Gtd(days=1)
    return (d + _Gtd(days=7 * (n - 1))).day


def _G_transitions(rule: str, base: int, y0: int = 1996, y1: int = 2096) -> list:
    """(utc instant, offset minutes in force from that instant) for every change."""
    out = []
    for y in range(y0, y1 + 1):
        if rule == "eu":
            on = _Gdt(y, 3, _G_last_sunday(y, 3), 1, 0, tzinfo=_GUTC)
            off = _Gdt(y, 10, _G_last_sunday(y, 10), 1, 0, tzinfo=_GUTC)
        else:
            on = _Gdt(y, 3, _G_nth_sunday(y, 3, 2), 2, 0, tzinfo=_GUTC) - _Gtd(minutes=base)
            off = _Gdt(y, 11, _G_nth_sunday(y, 11, 1), 2, 0, tzinfo=_GUTC) - _Gtd(minutes=base + 60)
        out.append((on, base + 60))
        out.append((off, base))
    return out


def _Goffset_at(u, clock) -> int:
    off = clock["base"]
    for t, o in clock["trans"]:
        if t <= u:
            off = o
        else:
            break
    return off


def _Gwall_to_utc(w, clock):
    """Naive local wall time to an aware UTC instant (repeated hour: earlier instant)."""
    hits = []
    for o in sorted({clock["base"], clock["base"] + 60}):
        u = (w - _Gtd(minutes=o)).replace(tzinfo=_GUTC)
        if _Goffset_at(u, clock) == o:
            hits.append(u)
    if hits:
        return min(hits)
    probe = (w - _Gtd(minutes=clock["base"] + 60)).replace(tzinfo=_GUTC)
    return (w - _Gtd(minutes=_Goffset_at(probe, clock))).replace(tzinfo=_GUTC)


def _Gutc_to_wall(u, clock):
    return (u + _Gtd(minutes=_Goffset_at(u, clock))).replace(tzinfo=None)


def _Goff_text(m: int) -> str:
    sign = "+" if m >= 0 else "-"
    m = abs(m)
    return f"{sign}{m // 60:02d}:{m % 60:02d}"


def _Giso_z(u) -> str:
    return u.strftime("%Y-%m-%dT%H:%M:%SZ")


def _Gdate_of(text: str) -> _Gdate:
    return _Gdate.fromisoformat(text)


# ---------------------------------------------------------------------------- shard layouts
# id, file, format, reading unit, distance unit, temperature, time style, rods, run id style
_GLAYOUTS = [
    {"id": "L01", "file": "fb_3kq7.csv", "fmt": "csv", "ru": "m", "du": "m", "temp": "C", "time": "z", "rods": "explicit", "rid": "canon"},
    {"id": "L02", "file": "fb_8wd2.tsv", "fmt": "tsv", "ru": "mm", "du": "dm", "temp": None, "time": "off", "rods": "pair", "rid": "compact"},
    {"id": "L03", "file": "fb_1mz5.psv", "fmt": "psv", "ru": "m", "du": "m", "temp": "C", "time": "local", "rods": "explicit", "rid": "canon"},
    {"id": "L04", "file": "fb_6tr0.txt", "fmt": "fixed", "ru": "cmm", "du": "dm", "temp": "C", "time": "fw", "rods": "pair", "rid": "compact"},
    {"id": "L05", "file": "fb_2hx9.jsonl", "fmt": "jsonl", "ru": "m", "du": "m", "temp": "C", "time": "off", "rods": "explicit", "rid": "canon"},
    {"id": "L06", "file": "fb_9vb4.ndjson", "fmt": "ndjson", "ru": "mm", "du": "m", "temp": "F", "time": "epoch", "rods": "pair", "rid": "slash"},
    {"id": "L07", "file": "fb_4nc1.json", "fmt": "json", "ru": "m", "du": "m", "temp": None, "time": "z", "rods": "explicit", "rid": "canon"},
    {"id": "L08", "file": "fb_7pj3.xml", "fmt": "xmlattr", "ru": "mm", "du": "dm", "temp": "C", "time": "local", "rods": "explicit", "rid": "canon"},
    {"id": "L09", "file": "fb_0ys6.yaml", "fmt": "yamlblk", "ru": "m", "du": "m", "temp": "C", "time": "off", "rods": "pair", "rid": "compact"},
    {"id": "L10", "file": "fb_5gl8.yml", "fmt": "ymlrun", "ru": "mm", "du": "m", "temp": None, "time": "epoch", "rods": "explicit", "rid": "canon"},
    {"id": "L11", "file": "fb_3ru2.md", "fmt": "md", "ru": "m", "du": "m", "temp": "F", "time": "local", "rods": "explicit", "rid": "slash"},
    {"id": "L12", "file": "fb_8ek5.sqlite", "fmt": "sqlite", "ru": "cmm", "du": "dm", "temp": "C", "time": "epoch", "rods": "pair", "rid": "canon"},
    {"id": "L13", "file": "fb_1dq9.db", "fmt": "eav", "ru": "m", "du": "m", "temp": "C", "time": "z", "rods": "explicit", "rid": "canon"},
    {"id": "L14", "file": "fb_6af4.csv", "fmt": "csvsemi", "ru": "mm", "du": "m", "temp": "C", "time": "dmy", "rods": "explicit", "rid": "compact"},
    {"id": "L15", "file": "fb_2cw7.tsv", "fmt": "tsvft", "ru": "m", "du": "ft", "temp": "F", "time": "off", "rods": "explicit", "rid": "canon"},
    {"id": "L16", "file": "fb_9lt3.xml", "fmt": "xmlelem", "ru": "cmm", "du": "ft", "temp": None, "time": "z", "rods": "pair", "rid": "canon"},
]
_GRETIRED = {"id": "L01", "file": "fb_4ox8.csv", "fmt": "csv", "ru": "m", "du": "m", "temp": "C", "time": "z", "rods": "explicit", "rid": "canon"}
_GAUTOSAVE = {"id": "L05", "file": "fb_7zi1.jsonl", "fmt": "jsonl", "ru": "m", "du": "m", "temp": "C", "time": "off", "rods": "explicit", "rid": "canon"}

_GBLOCK_NAMES = ["Aldermeer", "Brakwater", "Corsloot", "Dijkhoek", "Eemvlak", "Ferwoude", "Graspolder", "Hollumer", "Ijzendam", "Jutterveen"]
_GMARK_DESC = ["bolt in bridge abutment", "disc in concrete pillar", "rod mark in culvert headwall", "bolt in church wall",
               "deep rod mark, cased", "disc in lock chamber wall", "bolt in pumping station plinth", "rivet in sluice sill",
               "underground mark, buried plate", "bolt in dike crest revetment", "disc in railway bridge pier", "bolt in water tower base"]
_GOBS_NAMES = ["AVR", "BKL", "CDM", "DJS", "EHV", "FKO", "GLW", "HNB", "IPT", "JRS", "KAV", "LMD", "MPE", "NQW", "ORH", "PSV",
               "QTB", "RUK", "SVL", "TWN", "UXE", "VYD", "WZA", "XAB", "YBC", "ZCD", "AEF", "BFG", "CGH", "DHI"]


def _G_mm(x) -> _GF:
    return _GF(x) / 1000


def _G_world(seed: int, cfg: dict) -> dict:  # noqa: C901
    rng = _G_rng(seed, "topology")
    W = {"cfg": cfg, "seed": seed}
    W["clock"] = {"base": cfg["base_offset"], "rule": cfg["zone_rule"], "trans": _G_transitions(cfg["zone_rule"], cfg["base_offset"])}
    W["start"] = _Gdate_of(cfg["start"])
    W["days"] = cfg["days"]
    W["ref_date"] = _Gdate_of(cfg["ref_date"])
    W["ref24"] = _Gdate_of(cfg["ref24"])
    pool = list(range(1000, 1999))
    rng.shuffle(pool)
    W["bm_pool"] = pool
    bms, lines, sections, blocks = {}, {}, {}, []
    sec_pool = list(range(1, 990))
    rng.shuffle(sec_pool)
    names = list(_GBLOCK_NAMES)
    rng.shuffle(names)
    line_no = 10

    def new_bm(block, kind):
        n = pool.pop()
        bid = f"VD-{n:04d}"
        bms[bid] = {"id": bid, "block": block, "kind": kind, "desc": rng.choice(_GMARK_DESC), "nbr": []}
        return bid

    for b in range(cfg["n_blocks"]):
        block = f"BLK-{chr(65 + b)}"
        blocks.append({"id": block, "name": names[b]})
        J = rng.randint(cfg["junctions"][0], cfg["junctions"][1])
        jn = [new_bm(block, "JUNCTION") for _ in range(J)]
        edges = [(jn[i], jn[(i + 1) % J]) for i in range(J)]
        chords = 2 if J <= 5 else 3
        tries = 0
        while chords and tries < 50:
            tries += 1
            i, j = sorted(rng.sample(range(J), 2))
            if j - i in (1, J - 1) or (jn[i], jn[j]) in edges:
                continue
            edges.append((jn[i], jn[j]))
            chords -= 1
        chains = [(u, v, False) for u, v in edges]
        for _ in range(rng.randint(cfg["spurs"][0], cfg["spurs"][1])):
            chains.append((rng.choice(jn), None, True))
        for u, v, spur in chains:
            line_no += rng.randint(1, 3)
            lid = f"DL-{line_no:03d}"
            klass = rng.choice(["I", "I", "I", "II", "II", "III"])
            lines[lid] = {"id": lid, "block": block, "class": klass, "spur": spur}
            n = rng.randint(1, 2) if spur else rng.randint(cfg["line_sections"][0], cfg["line_sections"][1])
            path = [u] + [new_bm(block, "SPUR" if spur else "LINE") for _ in range(n - (0 if spur else 1))]
            if not spur:
                path.append(v)
            for a, c in zip(path, path[1:]):
                sid = f"S-{sec_pool.pop():04d}"
                fr, to = (a, c) if rng.random() < 0.5 else (c, a)
                L = _GF(rng.randint(3500, 18500), 10)
                sections[sid] = {"id": sid, "from": fr, "to": to, "line": lid, "block": block, "len": L}
                bms[a]["nbr"].append(c)
                bms[c]["nbr"].append(a)
    W["bms"], W["lines"], W["sections"], W["blocks"] = bms, lines, sections, blocks

    # true heights by breadth-first walk from the first junction of each block
    for blk in blocks:
        first = next(k for k, v in bms.items() if v["block"] == blk["id"])
        bms[first]["h"] = _Gq(_GF(rng.randint(200000, 650000), 100000), 5)
        queue = [first]
        while queue:
            x = queue.pop(0)
            for y in bms[x]["nbr"]:
                if "h" not in bms[y]:
                    h = bms[x]["h"] + _GF(rng.randint(-110000, 110000), 100000)
                    h = min(max(h, _GF(30, 100)), _GF(1150, 100))
                    bms[y]["h"] = _Gq(h, 5)
                    queue.append(y)

    # line class history (the effective class is the latest entry on or before the reference date)
    for lid, ln in lines.items():
        hist = []
        old = rng.choice(["II", "III", ln["class"]])
        hist.append({"from": (_Gdate(2014 + rng.randint(0, 6), rng.randint(1, 12), 1)).isoformat(), "class": old})
        if old != ln["class"] or rng.random() < 0.4:
            hist.append({"from": (_Gdate(2022 + rng.randint(0, 3), rng.randint(1, 12), 1)).isoformat(), "class": ln["class"]})
        if rng.random() < 0.18:
            fut = rng.choice([c for c in ("I", "II", "III") if c != ln["class"]])
            hist.append({"from": (W["ref_date"] + _Gtd(days=rng.randint(20, 300))).isoformat(), "class": fut})
        if hist[-1]["class"] != ln["class"] and _Gdate_of(hist[-1]["from"]) <= W["ref_date"]:
            hist.append({"from": (_Gdate(2025, 7, 1)).isoformat(), "class": ln["class"]})
        ln["hist"] = hist
    return W


def _G_controls(W, rng) -> None:
    """Profile control points, Table C-2 / C-1 heights, disturbances and legacy names."""
    cfg, bms = W["cfg"], W["bms"]
    ctrl = []
    for i, blk in enumerate(W["blocks"]):
        cand = [k for k, v in bms.items() if v["block"] == blk["id"] and v["kind"] == "JUNCTION"]
        rng.shuffle(cand)
        n = 1 if i == 0 else 3 if i == 3 else 2
        ctrl += cand[:n]
    W["control_true"] = list(ctrl)
    demoted = []
    if cfg["demote_control"]:
        demoted.append(ctrl[2])
    if cfg["unconstrained_block"]:
        last = W["blocks"][-1]["id"]
        demoted += [c for c in ctrl if bms[c]["block"] == last and c not in demoted]
    W["demoted"] = demoted
    for c in demoted:
        bms[c]["moved"] = _GF(rng.choice([-1, 1]) * rng.randint(9, 16), 1000)
    others = [k for k, v in bms.items() if v["kind"] == "JUNCTION" and k not in ctrl]
    rng.shuffle(others)
    extra_net = others[:12]
    outside = [f"VD-{n:04d}" for n in rng.sample(range(1, 999), 40)]
    c2 = {}
    for b in ctrl + extra_net:
        h = bms[b]["h"] - bms[b].get("moved", 0)
        c2[b] = _Gs(h, 5)
    for b in outside:
        c2[b] = _Gs(_GF(rng.randint(30000, 1100000), 100000), 5)
    c1 = {}
    for b, v in c2.items():
        if rng.random() < 0.9:
            c1[b] = _Gs(_GQ(v) + _GF(rng.choice([-1, 1]) * rng.randint(2, 7), 1000), 5)
    W["c2"], W["c1"] = c2, c1
    for b in ctrl:
        if b not in demoted:
            c1[b] = _Gs(_GQ(c2[b]) + _GF(rng.choice([-1, 1]) * rng.randint(3, 8), 1000), 5)
    drop = cfg["control_drop"]
    prof = [c for c in ctrl]
    if drop:
        keep = [c for c in ctrl if c not in demoted]
        rng.shuffle(keep)
        for c in keep[:drop]:
            if sum(1 for x in prof if bms[x]["block"] == bms[c]["block"]) > 1:
                prof.remove(c)
    nt = rng.choice(outside[:5])
    W["profile_controls"] = prof + [nt]
    W["c2"].pop(nt, None)
    W["c1"][nt] = _Gs(_GF(rng.randint(30000, 900000), 100000), 5)

    # legacy names and number reuse
    legacy = {}
    ids = sorted(bms)
    lpool = list(range(1, 999))
    rng.shuffle(lpool)
    for b in ids:
        if rng.random() < 0.16:
            mid = f"VD-{lpool.pop():04d}"
            while mid in bms or mid in c2:
                mid = f"VD-{lpool.pop():04d}"
            mb = f"MB-{lpool.pop():03d}" if rng.random() < 0.6 else None
            legacy[b] = (mid, mb)
    W["legacy"] = legacy
    reuse = []
    cands = [b for b in ids if bms[b]["kind"] == "LINE" and b not in legacy]
    rng.shuffle(cands)
    for old in cands[:3]:
        # the old mark keeps its canonical id; its former number now names a new mark nearby
        newid = old
        oldid = f"VD-{W['bm_pool'].pop():04d}"
        bms[oldid] = dict(bms[old])
        bms[oldid]["id"] = oldid
        del bms[old]
        for s in W["sections"].values():
            if s["from"] == old:
                s["from"] = oldid
            if s["to"] == old:
                s["to"] = oldid
        for v in bms.values():
            v["nbr"] = [oldid if x == old else x for x in v["nbr"]]
        day = W["start"] + _Gtd(days=rng.randint(14, 30))
        reuse.append({"token": newid, "old": oldid, "until": day})
    W["reuse"] = reuse
    # the new marks: a spur hanging from the old mark, observed only after the reuse date
    for r in reuse:
        old, new = r["old"], r["token"]
        bms[new] = {"id": new, "block": bms[old]["block"], "kind": "SPUR", "desc": rng.choice(_GMARK_DESC), "nbr": [old],
                    "h": _Gq(bms[old]["h"] + _GF(rng.randint(-40000, 40000), 100000), 5), "since": r["until"]}
        bms[old]["nbr"].append(new)
        lid = f"DL-{900 + len([x for x in W['lines'] if x.startswith('DL-9')]):03d}"
        W["lines"][lid] = {"id": lid, "block": bms[old]["block"], "class": "II", "spur": True,
                           "hist": [{"from": "2026-01-01", "class": "II"}]}
        sid = f"S-{rng.randint(990, 999):04d}"
        while sid in W["sections"]:
            sid = f"S-{rng.randint(990, 999):04d}"
        fr, to = (old, new) if rng.random() < 0.5 else (new, old)
        W["sections"][sid] = {"id": sid, "from": fr, "to": to, "line": lid, "block": bms[old]["block"],
                              "len": _GF(rng.randint(4000, 9000), 10), "after": r["until"]}


def _G_instruments(W, rng) -> None:
    cfg = W["cfg"]
    start = W["start"]
    limit = _GQ(cfg["c_limit"])
    nums = rng.sample(range(100, 400), 30)
    inst = {}
    for k, n in enumerate(nums):
        iid = f"LV-{n:04d}"
        inst[iid] = {"id": iid, "campaign": k < 8, "tokens": [iid, f"lv{n}", f"Level {n}", f"DNA03-{n}"]}
    W["instruments"] = inst
    used = [i for i in inst if inst[i]["campaign"]]
    W["inst_used"] = used
    tests = []
    tid = 3000 + rng.randint(0, 400)
    bad = used[3]
    new = used[6]
    W["new_inst"] = new
    W["new_inst_first"] = start + _Gtd(days=9)
    for i in inst:
        c = _GF(rng.randint(-2100, 2100), 1000)
        d = start - _Gtd(days=rng.randint(40, 120)) if inst[i]["campaign"] else start - _Gtd(days=rng.randint(200, 500))
        if i == new:
            d = W["new_inst_first"]
        end = start + _Gtd(days=W["days"] + 10)
        while d <= end:
            hh, mm = (rng.randint(6, 7), rng.randint(0, 59)) if rng.random() < 0.6 else (rng.randint(11, 14), rng.randint(0, 59))
            if i == new and d == W["new_inst_first"]:
                hh = 12
            local = _Gdt(d.year, d.month, d.day, hh, mm, rng.randint(0, 59))
            u = _Gwall_to_utc(local, W["clock"])
            cv = c + _GF(rng.randint(-300, 300), 1000)
            res = "PASS"
            if i == bad and start + _Gtd(days=15) <= d <= start + _Gtd(days=27):
                d += _Gtd(days=1)
                continue
            if rng.random() < 0.07 and not (i == new and d == W["new_inst_first"]):
                tid += 1
                tests.append({"id": tid, "inst": i, "at": u, "c": _GF(rng.randint(-9000, 9000), 1000), "result": "RETEST",
                              "operator": rng.choice(_GOBS_NAMES)})
            tid += 1
            tests.append({"id": tid, "inst": i, "at": u + _Gtd(minutes=rng.randint(20, 50)), "c": cv, "result": res,
                          "operator": rng.choice(_GOBS_NAMES)})
            d += _Gtd(days=rng.randint(5, 9) if inst[i]["campaign"] else rng.randint(20, 60))
    for day, hh, bad_c in ((18, 7, True), (24, 12, False)):
        local = _Gdt((start + _Gtd(days=day)).year, (start + _Gtd(days=day)).month, (start + _Gtd(days=day)).day, hh, rng.randint(0, 50), 0)
        tid += 1
        sign = rng.choice([-1, 1])
        cv = sign * (limit + _GF(rng.randint(150, 600), 1000)) if bad_c else _GF(rng.randint(-900, 900), 1000)
        tests.append({"id": tid, "inst": bad, "at": _Gwall_to_utc(local, W["clock"]), "c": cv, "result": "PASS",
                      "operator": rng.choice(_GOBS_NAMES)})
    if cfg.get("spring_test_tie"):
        t = next(x for x in tests if x["inst"] == used[0] and x["at"].date() > start)
        tests.append({"id": tid + 7, "inst": t["inst"], "at": t["at"], "c": t["c"] + _GF(410, 1000), "result": "PASS", "operator": "AVR"})
    W["tests"] = tests
    W["bad_inst"] = bad


def _G_rods(W, rng) -> None:
    cfg = W["cfg"]
    start = W["start"]
    types = list(cfg["rod_types"])
    serials = rng.sample(range(2100, 9800), 90)
    rods = {}
    for k, s in enumerate(serials):
        sid = str(s)
        rods[sid] = {"serial": sid, "type": rng.choice(types), "former": None, "campaign": False, "legacy_only": False}
    used = serials[:24]
    plan = ["INV-F"] * 6 + ["INV-H"] * 4 + ["INV-B"] * 2
    pairs = {}
    for p in range(12):
        a, b = str(used[2 * p]), str(used[2 * p + 1])
        ta = tb = plan[p]
        if cfg["mixed_pairs"] and p in (2, 7, 9):
            tb = "INV-H" if ta != "INV-H" else "INV-F"
        rods[a]["type"], rods[b]["type"] = ta, tb
        rods[a]["campaign"] = rods[b]["campaign"] = True
        pairs[f"P{p + 1:02d}"] = (a, b)
    for s in rng.sample([str(x) for x in used], 5):
        rods[s]["former"] = str(rng.randint(300, 1999))
    for s in rng.sample([str(x) for x in used if rods[str(x)]["former"] is None], 2):
        rods[s]["legacy_only"] = True
    W["rods"], W["pairs"] = rods, pairs
    certs = []
    cid = 7100
    gap_rod = str(used[5])
    for s, r in rods.items():
        base = _GF(rng.randint(-350, 350), 10)
        t0 = rng.choice(["20.0", "20.0", "20.0", "19.5", "21.0"])
        if r["campaign"]:
            v1 = start - _Gtd(days=rng.randint(150, 320))
            t1 = start + _Gtd(days=rng.randint(20, 32))
            if s == gap_rod:
                t1 = start + _Gtd(days=19)
                v2 = start + _Gtd(days=22)
            else:
                v2 = t1 - _Gtd(days=rng.randint(0, 6))
            cid += 1
            certs.append({"cert": f"RC-{cid}", "serial": s, "ppm": base, "t0": t0, "from": v1, "to": t1})
            cid += 1
            certs.append({"cert": f"RC-{cid}", "serial": s, "ppm": base + _GF(rng.randint(-40, 40), 10), "t0": rng.choice(["20.0", t0]),
                          "from": v2, "to": v2 + _Gtd(days=rng.randint(330, 400))})
        elif rng.random() < 0.55:
            v1 = start - _Gtd(days=rng.randint(100, 600))
            cid += 1
            certs.append({"cert": f"RC-{cid}", "serial": s, "ppm": base, "t0": t0, "from": v1, "to": v1 + _Gtd(days=365)})
    W["certs"] = certs
    W["gap_rod"] = gap_rod


def _G_met(W, rng) -> None:
    """Three campaign met stations logging every ten minutes in daylight, with outages."""
    start, days = W["start"], W["days"]
    stations = {"WX-N": {"file": "wx_7dn2.csv", "unit": "C", "name": "Noordpolder AWS"},
                "WX-C": {"file": "wx_3fk8.tsv", "unit": "F", "name": "Centrumdijk AWS"},
                "WX-S": {"file": "wx_5qm1.jsonl", "unit": "dC", "name": "Zuidsluis AWS"}}
    W["stations"] = stations
    W["station_tokens"] = {st: [st, st.lower(), v["name"], v["name"].upper()] for st, v in stations.items()}
    W["met"] = {}
    W["met_raw"] = {}
    W["outage"] = {"station": "WX-C", "sub": "WX-N", "from": start + _Gtd(days=rng.randint(8, 14))}
    W["outage"]["to"] = W["outage"]["from"] + _Gtd(days=2)
    W["proposed"] = {"station": "WX-S", "sub": "WX-C", "from": start + _Gtd(days=rng.randint(30, 40))}
    W["proposed"]["to"] = W["proposed"]["from"] + _Gtd(days=3)
    for st in stations:
        recs = {}
        for d in range(-3, days + 4):
            day = start + _Gtd(days=d)
            if st == W["outage"]["station"] and W["outage"]["from"] <= day <= W["outage"]["to"]:
                continue
            tmin = 6 + rng.randint(0, 80) / 10 - d * 0.08
            tmax = tmin + 5 + rng.randint(0, 70) / 10
            gaps = []
            if rng.random() < 0.3:
                g0 = rng.randint(7 * 6, 16 * 6)
                gaps.append((g0, g0 + rng.randint(4, 9)))
            for slot in range(5 * 6, 20 * 6 + 1):
                if any(a <= slot < b for a, b in gaps):
                    continue
                h = slot / 6
                if h <= 14.5:
                    t = tmin + (tmax - tmin) * (h - 5) / 9.5
                else:
                    t = tmax - (tmax - (tmin + tmax) / 2) * (h - 14.5) / 5.5
                t += rng.normal() * 0.15
                local = _Gdt(day.year, day.month, day.day, slot // 6, (slot % 6) * 10, 0)
                u = _Gwall_to_utc(local, W["clock"])
                if stations[st]["unit"] == "F":
                    raw = _GF(round((t * 9 / 5 + 32) * 10), 10)
                    recs[u] = (raw, (raw - 32) * 5 / 9)
                else:
                    raw = _GF(round(t * 10), 10)
                    recs[u] = (raw, raw)
        items = sorted(recs.items())
        W["met"][st] = [(u, v[1]) for u, v in items]
        W["met_raw"][st] = [(u, v[0]) for u, v in items]


def _G_observers(W, rng) -> None:
    start = W["start"]
    obs = {}
    for k, code in enumerate(_GOBS_NAMES):
        recs = []
        y = 2016 + rng.randint(0, 6)
        while y < 2028:
            fr = _Gdate(y, rng.randint(1, 12), rng.randint(1, 28))
            to = fr + _Gtd(days=rng.randint(700, 1100))
            recs.append({"from": fr, "to": to, "level": rng.choice(["L1", "L2"])})
            y = to.year + (1 if rng.random() < 0.8 else 0)
        obs[code] = recs
    lapse = rng.sample(_GOBS_NAMES[:20], 2)
    for code in lapse:
        cut = start + _Gtd(days=rng.randint(15, 35))
        recs = [r for r in obs[code] if r["to"] < start - _Gtd(days=200)]
        recs.append({"from": cut - _Gtd(days=900), "to": cut, "level": "L2"})
        recs.append({"from": cut + _Gtd(days=60), "to": cut + _Gtd(days=900), "level": "L2"})
        obs[code] = recs
    W["observers"] = obs
    W["lapsed"] = lapse


def _G_cert_for(W, serial, day):
    best = None
    for c in W["certs"]:
        if c["serial"] == serial and c["from"] <= day <= c["to"]:
            if best is None or c["from"] > best["from"]:
                best = c
    return best


def _G_test_for(W, inst, u):
    best = None
    for t in W["tests"]:
        if t["inst"] == inst and t["result"] != "RETEST" and t["at"] <= u:
            if best is None or (t["at"], t["id"]) > (best["at"], best["id"]):
                best = t
    return best


def _G_obs_ok(W, code, day) -> bool:
    return any(r["from"] <= day <= r["to"] for r in W["observers"][code])


def _G_corr(r, D, T, cert, alpha, c, k, R):
    """Corrected reading (m) under H10."""
    s = _GF(cert["ppm"]) / 10 ** 6 if cert else 0
    t0 = _GQ(cert["t0"]) if cert else T
    return r * (1 + s + alpha / 10 ** 6 * (T - t0)) - c * D / 100000 - (1 - k) * D * D / (2 * R)


def _G_met_at(W, st, u):
    """(value C, source) for an instant from the station log under H7."""
    recs = W["met"].get(st, [])
    lo, hi = None, None
    a, b = 0, len(recs)
    while a < b:
        m = (a + b) // 2
        if recs[m][0] < u:
            a = m + 1
        else:
            b = m
    if a < len(recs) and recs[a][0] == u:
        return _Gq(recs[a][1], 1), "MET"
    if a > 0:
        lo = recs[a - 1]
    if a < len(recs):
        hi = recs[a]
    gap = W["prof"]["met_max_gap"]
    if lo is None or hi is None or (hi[0] - lo[0]) > _Gtd(minutes=gap):
        return None, "FALLBACK"
    span = _GF(int((hi[0] - lo[0]).total_seconds()))
    off = _GF(int((u - lo[0]).total_seconds()))
    return _Gq(lo[1] + (hi[1] - lo[1]) * off / span, 1), "MET"


def _G_station(W, line, u):
    day = _Gutc_to_wall(u, W["clock"]).date()
    st = None
    for d0, sid in sorted(W["line_station"][line]):
        if d0 <= day:
            st = sid
    o = W["outage"]
    if st == o["station"] and o["from"] <= day <= o["to"]:
        return o["sub"]
    return st


def _G_run_reason(W, run):
    """First failing run-level reason among observer, test, collimation and certificates (None when valid)."""
    day = run["day"]
    if not _G_obs_ok(W, run["obs"], day):
        return "UNCERTIFIED_OBSERVER"
    t = _G_test_for(W, run["inst"], run["t0"])
    if t is None:
        return "NO_TEST"
    if abs(t["c"]) > _GQ(W["cfg"]["c_limit"]):
        return "INVALID_COLLIMATION"
    a, b = W["pairs"][run["pair"]]
    if _G_cert_for(W, a, day) is None or _G_cert_for(W, b, day) is None:
        return "NO_CERTIFICATE"
    return None


_GWANT = {"lapsed": "UNCERTIFIED_OBSERVER", "notest": "NO_TEST", "early": "NO_TEST", "bad_inst": "INVALID_COLLIMATION",
          "cert_gap": "NO_CERTIFICATE"}


def _G_pick_slot(W, rng, run, want, sec):
    """Choose day, start instant, instrument, pair and observer so that the run is valid (or fails as wanted)."""
    start, days = W["start"], W["days"]
    lo, hi = 0, days - 1
    if sec.get("after"):
        lo = (sec["after"] - start).days + 1
    if run.get("before"):
        hi = min(hi, (run["before"] - start).days - 1)
    goal = _GWANT.get(want)
    for _ in range(6000):
        day = start + _Gtd(days=rng.randint(lo, hi))
        run["inst"] = rng.choice(W["inst_used"])
        run["pair"] = rng.choice(sorted(W["pairs"]))
        run["obs"] = rng.choice(_GOBS_NAMES)
        hh, mm = rng.randint(7, 15), rng.randint(0, 59)
        if want == "bad_inst":
            run["inst"] = W["bad_inst"]
            day = start + _Gtd(days=rng.randint(19, 23))
        elif want == "notest":
            run["inst"] = W["new_inst"]
            day = start + _Gtd(days=rng.randint(0, 7))
        elif want == "early":
            run["inst"] = W["new_inst"]
            day = W["new_inst_first"]
            hh, mm = 7, rng.randint(0, 40)
        elif want == "cert_gap":
            run["pair"] = next(p for p, ab in sorted(W["pairs"].items()) if W["gap_rod"] in ab)
            day = start + _Gtd(days=rng.randint(20, 21))
        elif want == "lapsed":
            run["obs"] = rng.choice(W["lapsed"])
        if not (lo <= (day - start).days <= hi):
            continue
        local = _Gdt(day.year, day.month, day.day, hh, mm, rng.randint(0, 59))
        run["day"] = day
        run["t0"] = _Gwall_to_utc(local, W["clock"])
        if _G_run_reason(W, run) == goal:
            return True
    raise RuntimeError(f"no slot for {want} in {sec['id']}")


def _G_plan_runs(W, rng) -> None:  # noqa: C901
    cfg = W["cfg"]
    secs = [W["sections"][k] for k in sorted(W["sections"])]
    ids = rng.sample(range(1, 9999), 2000)
    W["runs"] = {}
    sig_true = _GQ(cfg["noise_scale"])
    special = [s for s in secs if not s.get("after")]
    rng.shuffle(special)
    ring = [s for s in special if not W["lines"][s["line"]]["spur"]]
    outl = set(s["id"] for s in ring[:cfg["outliers"]])
    blocks = sorted({s["block"] for s in ring})
    rng.shuffle(blocks)
    for blk in blocks[:cfg["pair_outliers"]]:
        cand = [s for s in ring if s["block"] == blk and s["id"] not in outl]
        lines_used = set()
        picked = 0
        for s in cand:
            if s["line"] in lines_used:
                continue
            outl.add(s["id"])
            lines_used.add(s["line"])
            picked += 1
            if picked == 2:
                break
    special = [s for s in special if s["id"] not in outl]
    rej = set(s["id"] for s in special[:cfg["reject_sections"]])
    invalid_kinds = (["void"] * cfg["void_runs"] + ["gap"] * cfg["gap_runs"] + ["bad_inst"] * 3 + ["notest"] * 2 + ["cert_gap"] * 2
                     + ["lapsed"] * 2 + ["ruled"] * 2 + ["early"])
    pool = [s for s in special if s["id"] not in outl and s["id"] not in rej]
    inv_at = {}
    for kind, s in zip(invalid_kinds, pool[: len(invalid_kinds)]):
        inv_at[s["id"]] = kind
    reuse_old = {r["old"]: r for r in W["reuse"]}
    for s in secs:
        klass = W["lines"][s["line"]]["class"]
        sig = _GQ(cfg["sigma"][klass])
        K = float(s["len"]) / 1000
        tol = float(_GQ(W["tol_true"][klass][0])) * _Gsqrtf(K)
        plan = [("F", "ok"), ("B", "ok")]
        if s["id"] in rej:
            plan = [("F", "blunder"), ("B", "ok")] if rng.random() < 0.5 else [("F", "ok"), ("B", "blunder")]
        elif s["id"] in inv_at:
            kind = inv_at[s["id"]]
            d = rng.choice(["F", "B"])
            plan = [(d, kind), ("B" if d == "F" else "F", "ok")]
            if rng.random() < 0.75 or kind in ("gap", "early"):
                plan.append((d, "ok"))
        elif rng.random() < cfg["rerun_rate"]:
            d = rng.choice(["F", "B"])
            plan = [(d, "blunder"), ("B" if d == "F" else "F", "ok"), (d, "ok")]
        elif rng.random() < 0.08:
            plan.append((rng.choice(["F", "B"]), "ok"))
        delta = 0.0
        if s["id"] in outl:
            delta = rng.choice([-1, 1]) * rng.randint(85, 125) / 10 * float(sig) * _Gsqrtf(K)
        errs = []
        for direction, kind in plan:
            e = rng.normal() * float(sig * sig_true) * _Gsqrtf(K)
            if kind == "blunder":
                e = rng.choice([-1, 1]) * (tol + 1.5 + rng.random() * 2.5)
            errs.append(e)
        if s["id"] not in rej:
            good_f = [e for (d, kd), e in zip(plan, errs) if d == "F" and kd == "ok"]
            good_b = [e for (d, kd), e in zip(plan, errs) if d == "B" and kd == "ok"]
            if good_f and good_b and min(abs(a + b) for a in good_f for b in good_b) > 0.9 * tol:
                plan.append(("F", "ok"))
                errs.append(-good_b[0] + rng.normal() * 0.3 * tol)
        for (direction, kind), e in zip(plan, errs):
            rid = f"R-26-{ids.pop():04d}"
            run = {"id": rid, "sec": s["id"], "dir": direction, "kind": kind}
            if (s["from"] in reuse_old or s["to"] in reuse_old) and not s.get("after"):
                r = reuse_old.get(s["from"]) or reuse_old.get(s["to"])
                if rng.random() < 0.7:
                    run["before"] = r["until"]
                    run["reuse_token"] = r
            _G_pick_slot(W, rng, run, kind, s)
            run["err_mm"] = e + (delta if direction == "F" else -delta)
            W["runs"][rid] = run


def _G_setups(W, rng) -> None:
    """Readings, distances, instants and temperatures for every setup of every run."""
    W["setups"] = {}
    for rid in sorted(W["runs"]):
        _G_run_setups(W, rng, rid)


def _G_run_setups(W, rng, rid) -> None:
    """Readings, distances, instants and temperatures for every setup of one run."""
    cfg = W["cfg"]
    k = _GQ(cfg["k_ref"])
    R = _GF(cfg["earth_radius"])
    types = cfg["rod_types"]
    run = W["runs"][rid]
    s = W["sections"][run["sec"]]
    dh_true = W["bms"][s["to"]]["h"] - W["bms"][s["from"]]["h"]
    if run["dir"] == "B":
        dh_true = -dh_true
    target = dh_true + _GQ(f"{run['err_mm']:.4f}") / 1000
    L = s["len"] * (1 + _GF(rng.randint(-300, 300), 10000))
    dm = rng.randint(22, 42)
    n = max(2, round(float(L) / (2 * dm)))
    while abs(float(target)) / n > 1.6:
        n += 1
    run["n"] = n
    test = _G_test_for(W, run["inst"], run["t0"])
    c = test["c"] if test else _GF(0)
    a, b = W["pairs"][run["pair"]]
    ca, cb = _G_cert_for(W, a, run["day"]), _G_cert_for(W, b, run["day"])
    js = [_GF(rng.randint(-30000, 30000), 100000) for _ in range(n)]
    mean = sum(js) / n
    parts = [target / n + j - mean for j in js]
    t = run["t0"]
    lay = run["layout"]
    for i in range(n):
        seq = i + 1
        back, fore = (a, b) if seq % 2 == 1 else (b, a)
        cbk, cfr = (ca, cb) if seq % 2 == 1 else (cb, ca)
        half = (L / (2 * n))
        imb = _GF(round(rng.normal() * 9), 10)
        if rng.random() < 0.06:
            imb = _GF(rng.choice([-1, 1]) * rng.randint(25, 50), 10)
        db = max(_GF(5), _Gq(half + imb / 2 + _GF(rng.randint(-20, 20), 10), 1))
        df = max(_GF(5), _Gq(half - imb / 2 + _GF(rng.randint(-20, 20), 10), 1))
        st = _G_station(W, s["line"], t)
        met, src = _G_met_at(W, st, t)
        temp = None
        if lay["temp"] and rng.random() < 0.85:
            base = met if met is not None else _GQ(cfg["fallback_temp"])
            temp = _Gq(base + _GF(rng.randint(8, 38), 10), 1)
        T = temp if temp is not None else (met if met is not None else _GQ(cfg["fallback_temp"]))
        ab_ = _GQ(types[W["rods"][back]["type"]][1])
        af_ = _GQ(types[W["rods"][fore]["type"]][1])
        lo_b = max(_GF(50000, 100000), parts[i] + _GF(33000, 100000))
        hi_b = min(_GF(290000, 100000), parts[i] + _GF(297000, 100000))
        bv = lo_b + (hi_b - lo_b) * _GF(rng.randint(0, 10000), 10000)
        bv = _Gq(bv, 5)
        cbv = _G_corr(bv, db, T, cbk, ab_, c, k, R)
        cfv = cbv - parts[i]
        s_f = _GF(cfr["ppm"]) / 10 ** 6 if cfr else 0
        t0f = _GQ(cfr["t0"]) if cfr else T
        fv = (cfv + c * df / 100000 + (1 - k) * df * df / (2 * R)) / (1 + s_f + af_ / 10 ** 6 * (T - t0f))
        fv = _Gq(fv, 5)
        W["setups"][(rid, seq)] = {"run": rid, "seq": seq, "at": t, "back": bv, "fore": fv, "db": db, "df": df,
                                   "temp": temp, "rb": back, "rf": fore}
        t = t + _Gtd(seconds=rng.randint(150, 330))


def _G_assign_layouts(W, rng) -> None:
    lays = list(_GLAYOUTS)
    for rid in sorted(W["runs"]):
        W["runs"][rid]["layout"] = rng.choice(lays)
    feet = [x for x in lays if x["du"] == "ft"]
    if W["cfg"]["feet_share"] > 1:
        for rid in sorted(W["runs"]):
            if rng.random() < 0.25:
                W["runs"][rid]["layout"] = rng.choice(feet)


def _G_same_cap(lay, rec) -> bool:
    return rec["temp"] is None or lay["temp"] is not None


def _G_emit(W, rng) -> None:  # noqa: C901
    """Revision, void, duplicate and conflict records for every setup, spread over the shards."""
    cfg = W["cfg"]
    order = list(_GLAYOUTS)
    rng.shuffle(order)
    W["catalog_order"] = [x["file"] for x in order]
    pos = {x["file"]: i for i, x in enumerate(order)}
    recs = []
    gap_runs = [r for r in sorted(W["runs"]) if W["runs"][r]["kind"] == "gap"]

    def variant(c):
        v = dict(c)
        v["fore"] = c["fore"] + _GF(rng.choice([-1, 1]) * rng.randint(4, 90), 100000)
        return v

    for key in sorted(W["setups"]):
        c = W["setups"][key]
        run = W["runs"][key[0]]
        home = run["layout"]
        others = [x for x in _GLAYOUTS if x is not home and _G_same_cap(x, c)]
        n = run["n"]
        u = rng.random()
        if run["id"] in gap_runs and key[1] == max(2, n // 2):
            recs.append((home, key, 1, False, c))
            recs.append((rng.choice(others), key, 2, True, variant(c)))
            continue
        if u < cfg["void_rate"]:
            recs.append((rng.choice(others + [home]), key, 1, True, variant(c)))
            recs.append((home, key, 2, False, c))
            final = 2
        elif u < cfg["void_rate"] * 2:
            recs.append((rng.choice(others), key, 1, False, variant(c)))
            recs.append((rng.choice(others + [home]), key, 2, True, variant(c)))
            recs.append((home, key, 3, False, c))
            final = 3
        elif u < cfg["void_rate"] * 2 + cfg["rev_rate"]:
            recs.append((rng.choice(others + [home]), key, 1, False, variant(c)))
            recs.append((home, key, 2, False, c))
            final = 2
        else:
            recs.append((home, key, 1, False, c))
            final = 1
        v = rng.random()
        if v < cfg["dup_rate"]:
            recs.append((rng.choice(others), key, final, False, c))
        elif v < cfg["dup_rate"] + cfg["conflict_rate"]:
            other = rng.choice(others)
            if pos[other["file"]] < pos[home["file"]]:
                recs = [r for r in recs if not (r[1] == key and r[2] == final and r[0] is home)]
                recs.append((other, key, final, False, c))
                recs.append((home, key, final, False, variant(c)))
            else:
                recs.append((other, key, final, False, variant(c)))
    W["records"] = recs
    # stale copies in the retired shard and the uncatalogued autosave
    keys = sorted(W["setups"])
    stale = []
    for key in rng.sample(keys, 260):
        c = W["setups"][key]
        stale.append((_GRETIRED, key, 9, False, variant(c)))
    auto = []
    for key in rng.sample(keys, 320):
        c = W["setups"][key]
        if c["temp"] is None and rng.random() < 0.5:
            continue
        auto.append((_GAUTOSAVE, key, rng.randint(4, 7), rng.random() < 0.3, variant(c)))
    W["stale"], W["autosave"] = stale, auto


def _G_profile(W, rng) -> None:
    """Effective settings, the profile file values and the overlay that turns one into the other."""
    cfg = W["cfg"]
    eff = {"met_max_gap": cfg["met_max_gap"], "fallback_temp": cfg["fallback_temp"], "cert_sheet": cfg["cert_sheet"]}
    W["prof"] = eff
    W["prof_file"] = {"met_max_gap": eff["met_max_gap"] - 10, "fallback_temp": eff["fallback_temp"], "cert_sheet": eff["cert_sheet"]}
    camp = cfg["campaign"]
    ref = W["ref_date"]
    ov = []
    for y in range(16, 27):
        c = f"VDL-{y}"
        for key, vals in (("met_max_gap_min", ["20", "25", "40", "45"]), ("fallback_temp_c", ["14.0", "16.5", "19.0"]),
                          ("rod_certificate_sheet", ["Certs_2023", f"Certs_20{y}A", "Certs_2026_DRAFT"])):
            for _ in range(rng.randint(1, 2)):
                if c == camp:
                    continue
                ov.append({"campaign": c, "effective": _Gdate(2000 + y, rng.randint(1, 12), rng.randint(1, 28)).isoformat(),
                           "key": key, "value": rng.choice(vals), "note": "season setting"})
    rng.shuffle(ov)
    mine = [
        {"campaign": camp, "effective": (W["start"] - _Gtd(days=20)).isoformat(), "key": "met_max_gap_min",
         "value": str(eff["met_max_gap"] - 5), "note": "provisional gap limit"},
        {"campaign": camp, "effective": (ref + _Gtd(days=45)).isoformat(), "key": "fallback_temp_c",
         "value": "15.0", "note": "winter programme setting"},
        {"campaign": camp, "effective": (W["start"] - _Gtd(days=3)).isoformat(), "key": "met_max_gap_min",
         "value": str(eff["met_max_gap"]), "note": "gap limit confirmed by the met desk"},
        {"campaign": camp.lower(), "effective": (W["start"] - _Gtd(days=1)).isoformat(), "key": "rod_certificate_sheet",
         "value": "Certs_2026_DRAFT", "note": "typed campaign id, not this campaign"},
    ]
    at = sorted(rng.sample(range(len(ov) + 1), len(mine)))
    for k, (i, e) in enumerate(zip(at, mine)):
        ov.insert(i + k, e)
    W["overlay"] = ov
    W["tol_true"] = {k: list(v) for k, v in cfg["tol"].items()}
    W["tol_true"][cfg["tol_erratum"][0]][0] = cfg["tol_erratum"][1]
    W["line_station"] = {}
    sts = sorted(W["stations"])
    for lid in sorted(W["lines"]):
        first = rng.choice(sts)
        hist = [(_Gdate(2019 + rng.randint(0, 5), rng.randint(1, 12), 1), first)]
        if rng.random() < 0.18:
            hist.append((W["start"] + _Gtd(days=rng.randint(6, 40)), rng.choice([x for x in sts if x != first])))
        if rng.random() < 0.1:
            hist.append((W["ref_date"] + _Gtd(days=rng.randint(10, 90)), rng.choice(sts)))
        W["line_station"][lid] = hist


def _G_norm_bm(tok: str):
    t = tok.strip().upper().replace(" ", "")
    m = _Gre.fullmatch(r"VD-?(\d{1,4})", t)
    if m:
        return f"VD-{int(m.group(1)):04d}"
    m = _Gre.fullmatch(r"(\d{1,4})", t)
    if m:
        return f"VD-{int(m.group(1)):04d}"
    m = _Gre.fullmatch(r"MB-?(\d{1,3})", t)
    if m:
        return f"MB-{int(m.group(1)):03d}"
    return t


def _G_aliases(W, rng) -> None:
    rows = []
    for b, (mid, mb) in sorted(W["legacy"].items()):
        rows.append({"token": mid, "canonical": b, "from": _Gdate(2021, 5, 1) + _Gtd(days=rng.randint(0, 200)), "to": None, "note": "renumbering 2021"})
        if mb:
            rows.append({"token": mb, "canonical": mid, "from": _Gdate(2015, 1, 1) + _Gtd(days=rng.randint(0, 300)), "to": None, "note": "polder board number"})
    for r in W["reuse"]:
        rows.append({"token": r["token"], "canonical": r["old"], "from": _Gdate(2009, 6, 1), "to": r["until"],
                     "note": "number released when the mark was renumbered; reissued to a new mark"})
    ids = sorted(b for b in W["bms"] if W["bms"][b]["kind"] != "SPUR" or "since" not in W["bms"][b])
    for b in rng.sample(ids, 4):
        rows.append({"token": b, "canonical": f"VD-{W['bm_pool'].pop():04d}", "from": W["ref_date"] + _Gtd(days=rng.randint(30, 200)), "to": None,
                     "note": "planned renumbering, not yet in effect"})
    for b in rng.sample(ids, 3):
        rows.append({"token": f"VD-{rng.randint(1, 999):04d}", "canonical": b, "from": _Gdate(2012, 1, 1), "to": _Gdate(2019, 1, 1),
                     "note": "expired provisional number"})
    used = {r["token"] for r in rows}
    while len(rows) < 236:
        n = rng.randint(1, 999)
        tok = f"MB-{n:03d}" if rng.random() < 0.5 else f"VD-{n:04d}"
        if tok in used:
            continue
        used.add(tok)
        rows.append({"token": tok, "canonical": f"WS-{rng.randint(100, 999)}", "from": _Gdate(2010 + rng.randint(0, 12), rng.randint(1, 12), 1),
                     "to": None, "note": "western sector mark"})
    W["alias_rows"] = rows


def _G_resolve(W, token: str, day):
    """(canonical or None, hops) under H13."""
    t = _G_norm_bm(token)
    hops = 0
    for _ in range(12):
        best = None
        for r in W["alias_rows"]:
            if r["token"] == t and r["from"] <= day and (r["to"] is None or day < r["to"]):
                if best is None or r["from"] > best["from"]:
                    best = r
        if best is None:
            break
        t = best["canonical"]
        hops += 1
    return (t if t in W["master"] else None), hops


def _G_bm_token(W, rng, bm, run=None) -> str:
    if run and run.get("reuse_token") and run["reuse_token"]["old"] == bm:
        return rng.choice([run["reuse_token"]["token"], run["reuse_token"]["token"].lower()])
    n = int(bm[3:])
    opts = [bm, bm, bm, bm.lower(), f"VD{n:04d}", f"VD {n}", str(n)]
    if bm in W["legacy"]:
        mid, mb = W["legacy"][bm]
        opts += [mid, mid, str(int(mid[3:]))]
        if mb:
            opts += [mb, mb.lower().replace("-", " ")]
    return rng.choice(opts)


def _G_registers(W, rng) -> None:  # noqa: C901
    cfg = W["cfg"]
    W["master"] = set(W["bms"]) | {b for b in W["c2"]} | {b for b in W["c1"]}
    _G_aliases(W, rng)
    # run register and late amendments
    rows, late = [], []
    amend = rng.randint(100, 300)
    for rid in sorted(W["runs"]):
        run = W["runs"][rid]
        s = W["sections"][run["sec"]]
        a, b = (s["from"], s["to"]) if run["dir"] == "F" else (s["to"], s["from"])
        inst_tok = rng.choice(W["instruments"][run["inst"]]["tokens"])
        row = {"run": rid, "campaign": cfg["campaign"], "start": _G_bm_token(W, rng, a, run), "end": _G_bm_token(W, rng, b, run),
               "booked": (run["day"] + _Gtd(days=rng.choice([0, 0, 0, 0, 1, -1]))).isoformat(), "level": inst_tok,
               "pair": run["pair"], "observer": run["obs"] if rng.random() < 0.8 else run["obs"].lower(), "setups": run["n"],
               "status": "OK", "note": ""}
        u = rng.random()
        if run["kind"] == "void":
            if u < 0.5:
                row["status"] = "VOID"
                row["note"] = "abandoned, wind"
            else:
                amend += rng.randint(1, 4)
                late.append({"amend_no": amend, "run": rid, "campaign": cfg["campaign"], "field": "status", "value": "VOID"})
        elif run["kind"] == "ok" and u < 0.05:
            row["status"] = "VOID"
            amend += rng.randint(1, 4)
            late.append({"amend_no": amend, "run": rid, "campaign": cfg["campaign"], "field": "status", "value": "OK"})
        elif run["kind"] == "ok" and u < 0.12:
            row["setups"] = run["n"] + 1
            amend += rng.randint(1, 4)
            hi = amend + rng.randint(30, 60)
            late.append({"amend_no": hi, "run": rid, "campaign": cfg["campaign"], "field": "setups", "value": str(run["n"])})
            late.append({"amend_no": amend, "run": rid, "campaign": cfg["campaign"], "field": "setups", "value": str(run["n"] + 2)})
        elif run["kind"] == "ok" and u < 0.17:
            wrong = W["bad_inst"] if run["inst"] != W["bad_inst"] else W["inst_used"][0]
            row["level"] = rng.choice(W["instruments"][wrong]["tokens"])
            amend += rng.randint(1, 4)
            late.append({"amend_no": amend, "run": rid, "campaign": cfg["campaign"], "field": "level", "value": inst_tok})
        rows.append(row)
    for k in range(70):
        rid = f"R-25-{rng.randint(1, 9999):04d}"
        rows.append({"run": rid, "campaign": "VDL-25", "start": f"VD-{rng.randint(1000, 1999)}", "end": f"VD-{rng.randint(1000, 1999)}",
                     "booked": (W["start"] - _Gtd(days=rng.randint(300, 400))).isoformat(), "level": rng.choice(rng.choice(list(W["instruments"].values()))["tokens"]),
                     "pair": f"P{rng.randint(1, 12):02d}", "observer": rng.choice(_GOBS_NAMES), "setups": rng.randint(8, 30),
                     "status": "OK", "note": "previous season"})
        if rng.random() < 0.3:
            amend += 1
            late.append({"amend_no": amend, "run": rid, "campaign": "VDL-25", "field": "status", "value": "VOID"})
    rng.shuffle(rows)
    rng.shuffle(late)
    while len(late) < 205:
        amend += 1
        late.append({"amend_no": amend, "run": f"R-24-{rng.randint(1, 9999):04d}", "campaign": "VDL-24",
                     "field": rng.choice(["setups", "observer", "status"]), "value": rng.choice(["12", "OBS", "OK", "VOID"])})
        rng.shuffle(late)
    W["run_rows"], W["late"] = rows, late
    # rulings: memo tables J-1 (in force) and J-0 (withdrawn), plus the addendum
    j1, j0, add = [], [], []
    n = 1
    ruled = [r for r in sorted(W["runs"]) if W["runs"][r]["kind"] == "ruled"]
    for rid in ruled:
        j1.append({"id": f"J-26-{n:02d}", "target": rid, "action": "REJECT_RUN", "effective": (W["start"] + _Gtd(days=5)).isoformat(),
                   "note": "rod support settled during run"})
        n += 1
    oks = [r for r in sorted(W["runs"]) if W["runs"][r]["kind"] == "ok"]
    cancel_run = rng.choice(oks)
    j1.append({"id": f"J-26-{n:02d}", "target": cancel_run, "action": "REJECT_RUN", "effective": (W["start"] + _Gtd(days=9)).isoformat(),
               "note": "suspected rod swap"})
    add.append({"id": "A-26-03", "campaign": cfg["campaign"], "action": "CANCEL", "target": f"J-26-{n:02d}",
                "issued": (W["ref_date"] - _Gtd(days=4)).isoformat(), "note": "rod swap not confirmed by the field book"})
    n += 1
    plain = [s for s in sorted(W["sections"]) if not W["sections"][s].get("after")]
    rsec = rng.choice(plain)
    j1.append({"id": f"J-26-{n:02d}", "target": rsec, "action": "REJECT_SECTION", "effective": (W["start"] + _Gtd(days=2)).isoformat(),
               "note": "mark suspected loose"})
    n += 1
    W["ruled_section"] = rsec
    late_run = rng.choice(oks)
    add.append({"id": "A-26-05", "campaign": cfg["campaign"], "action": "REJECT_RUN", "target": late_run,
                "issued": (W["ref_date"] + _Gtd(days=6)).isoformat(), "note": "issued after the reference date"})
    in_run = rng.choice([r for r in oks if r not in (cancel_run, late_run)])
    add.append({"id": "A-26-04", "campaign": cfg["campaign"], "action": "REJECT_RUN", "target": in_run,
                "issued": (W["ref_date"] - _Gtd(days=8)).isoformat(), "note": "observer reported instrument knock"})
    for k in range(cfg["extra_rulings"]):
        tgt = rng.choice([r for r in oks if r not in (cancel_run, late_run, in_run)])
        add.append({"id": f"A-26-{10 + k:02d}", "campaign": cfg["campaign"], "action": "REJECT_RUN", "target": tgt,
                    "issued": (W["ref_date"] - _Gtd(days=rng.randint(1, 30))).isoformat(), "note": "extra review"})
    for k in range(9):
        j0.append({"id": f"J-26-{90 + k:02d}", "target": rng.choice(oks if rng.random() < 0.7 else plain),
                   "action": "REJECT_RUN", "effective": (W["start"] + _Gtd(days=rng.randint(1, 30))).isoformat(), "note": "withdrawn ruling"})
    for k in range(j0.__len__()):
        if j0[k]["target"].startswith("S-"):
            j0[k]["action"] = "REJECT_SECTION"
    for y in range(19, 26):
        for k in range(rng.randint(28, 36)):
            add.append({"id": f"A-{y}-{k + 1:02d}", "campaign": f"VDL-{y}", "action": rng.choice(["REJECT_RUN", "REJECT_SECTION", "CANCEL"]),
                        "target": rng.choice([f"R-{y}-{rng.randint(1, 9999):04d}", f"S-{rng.randint(1, 989):04d}", f"J-{y}-{rng.randint(1, 30):02d}"]),
                        "issued": _Gdate(2000 + y, rng.randint(1, 12), rng.randint(1, 28)).isoformat(), "note": "season review"})
    rng.shuffle(add)
    W["j1"], W["j0"], W["addendum"] = j1, j0, add
    # disturbance journal
    jr = []
    eid = rng.randint(400, 700)
    ids = sorted(b for b in W["bms"])
    ref = W["ref_date"]
    for c in W["demoted"]:
        eid += rng.randint(1, 5)
        jr.append({"entry": eid, "mark": c, "event": "DISTURBED", "date": (W["start"] - _Gtd(days=rng.randint(10, 60))).isoformat(), "refers": "",
                   "note": "excavation beside the mark"})
    ctrl_ok = [c for c in W["control_true"] if c not in W["demoted"]]
    rng.shuffle(ctrl_ok)
    if len(ctrl_ok) >= 3:
        c = ctrl_ok[0]
        eid += 3
        jr.append({"entry": eid, "mark": c, "event": "DISTURBED", "date": "2025-04-11", "refers": "", "note": "lock works"})
        eid += 4
        jr.append({"entry": eid, "mark": c, "event": "REVERIFIED", "date": (W["start"] - _Gtd(days=30)).isoformat(), "refers": "",
                   "note": "tie to two neighbours within tolerance"})
        c = ctrl_ok[1]
        eid += 2
        jr.append({"entry": eid, "mark": c, "event": "DISTURBED", "date": (W["start"] + _Gtd(days=4)).isoformat(), "refers": "",
                   "note": "reported hit by mower"})
        bad = eid
        eid += 6
        jr.append({"entry": eid, "mark": c, "event": "ERRATUM", "date": (W["start"] + _Gtd(days=6)).isoformat(), "refers": str(bad),
                   "note": "entry referred to the neighbouring mark"})
        c = ctrl_ok[2]
        eid += 3
        jr.append({"entry": eid, "mark": c, "event": "DISTURBED", "date": (ref + _Gtd(days=10)).isoformat(), "refers": "",
                   "note": "after the reference date"})
    disturbed_rate = rng.sample([b for b in ids if b not in W["control_true"]], 6)
    W["disturbed_marks"] = disturbed_rate
    for b in disturbed_rate:
        eid += rng.randint(1, 4)
        jr.append({"entry": eid, "mark": b, "event": "DISTURBED", "date": (W["ref24"] + _Gtd(days=rng.randint(60, 600))).isoformat(), "refers": "",
                   "note": "road works"})
        if rng.random() < 0.5:
            eid += rng.randint(1, 4)
            jr.append({"entry": eid, "mark": b, "event": "REVERIFIED", "date": (W["start"] - _Gtd(days=rng.randint(5, 40))).isoformat(), "refers": "",
                       "note": "re-levelled"})
    canc = rng.choice([b for b in ids if b not in disturbed_rate and b not in W["control_true"]])
    eid += 2
    jr.append({"entry": eid, "mark": canc, "event": "DISTURBED", "date": (W["ref24"] + _Gtd(days=200)).isoformat(), "refers": "", "note": "mis-booked"})
    eid += 2
    jr.append({"entry": eid, "mark": canc, "event": "ERRATUM", "date": (W["ref24"] + _Gtd(days=210)).isoformat(), "refers": str(eid - 2),
               "note": "booking error"})
    old = rng.choice([b for b in ids if b not in disturbed_rate and b != canc and b not in W["control_true"]])
    eid += 2
    jr.append({"entry": eid, "mark": old, "event": "DISTURBED", "date": (W["ref24"] - _Gtd(days=90)).isoformat(), "refers": "", "note": "before the 2024 epoch"})
    for k in range(cfg["extra_journal"]):
        b = rng.choice([x for x in ids if x not in W["control_true"]])
        eid += rng.randint(1, 3)
        jr.append({"entry": eid, "mark": b, "event": rng.choice(["DISTURBED", "REVERIFIED"]),
                   "date": (W["ref24"] + _Gtd(days=rng.randint(10, 700))).isoformat(), "refers": "", "note": "extra survey note"})
        if rng.random() < 0.3:
            eid += 1
            jr.append({"entry": eid, "mark": b, "event": "ERRATUM", "date": (W["ref24"] + _Gtd(days=rng.randint(10, 700))).isoformat(),
                       "refers": str(eid - 1), "note": "withdrawn note"})
    while len(jr) < 212:
        eid += rng.randint(1, 3)
        jr.append({"entry": eid, "mark": f"WS-{rng.randint(100, 999)}", "event": rng.choice(["DISTURBED", "REVERIFIED", "INSPECTED"]),
                   "date": _Gdate(2019 + rng.randint(0, 7), rng.randint(1, 12), rng.randint(1, 28)).isoformat(), "refers": "", "note": "western sector"})
    rng.shuffle(jr)
    W["journal"] = jr
    # loops from fundamental cycles of each block
    loops = []
    for blk in W["blocks"]:
        secs = [s for s in W["sections"].values() if s["block"] == blk["id"] and not s.get("after")]
        adj = {}
        for s in secs:
            adj.setdefault(s["from"], []).append(s["to"])
            adj.setdefault(s["to"], []).append(s["from"])
        root = min(adj)
        par, order = {root: None}, [root]
        i = 0
        while i < len(order):
            x = order[i]
            i += 1
            for y in sorted(adj[x]):
                if y not in par:
                    par[y] = x
                    order.append(y)
        tree = {frozenset((k, v)) for k, v in par.items() if v}
        k = 0
        for s in sorted(secs, key=lambda z: z["id"]):
            e = frozenset((s["from"], s["to"]))
            if e in tree:
                continue

            def path(x):
                p = [x]
                while par[p[-1]] is not None:
                    p.append(par[p[-1]])
                return p
            pa, pb = path(s["from"]), path(s["to"])
            common = next(x for x in pa if x in pb)
            cyc = pa[:pa.index(common) + 1] + list(reversed(pb[:pb.index(common)]))
            if rng.random() < 0.5:
                cyc = list(reversed(cyc))
            rot = rng.randint(0, len(cyc) - 1)
            cyc = cyc[rot:] + cyc[:rot]
            k += 1
            klass = rng.choice(["I", "I", "II"])
            loops.append({"id": f"LP-{blk['id'][-1]}{k:02d}", "class": klass, "marks": cyc})
    W["loops"] = loops
    # epoch register
    ep = []
    years = _GF((W["ref_date"] - W["ref24"]).days * 4, 1461)
    base_rate = {blk["id"]: -_GF(rng.randint(10, 70), 10) for blk in W["blocks"]}
    for b in sorted(W["bms"]):
        v = W["bms"][b]
        if v.get("since"):
            continue
        if rng.random() < 0.03:
            continue
        rate = base_rate[v["block"]] + _GF(rng.randint(-25, 25), 10)
        if rng.random() < 0.05:
            rate = -_GF(rng.randint(95, 140), 10)
        h24 = v["h"] - v.get("moved", 0) - rate * years / 1000 + _GF(rng.randint(-8, 8), 10000)
        tok = b
        if b in W["legacy"] and rng.random() < 0.5:
            tok = W["legacy"][b][0]
        for r in W["reuse"]:
            if r["old"] == b and rng.random() < 0.8:
                tok = r["token"]
        ep.append({"epoch": "VDL-24", "mark": tok, "h": _Gq(h24, 5), "sigma": _GF(rng.randint(6, 26), 10)})
    for b in rng.sample(sorted(W["bms"]), 60):
        if W["bms"][b].get("since"):
            continue
        ep.append({"epoch": "VDL-24P", "mark": b, "h": _Gq(W["bms"][b]["h"] + _GF(rng.randint(-60, 60), 10000), 5), "sigma": _GF(rng.randint(6, 26), 10)})
        ep.append({"epoch": "VDL-22", "mark": b, "h": _Gq(W["bms"][b]["h"] + _GF(rng.randint(10, 300), 10000), 5), "sigma": _GF(rng.randint(8, 30), 10)})
    rng.shuffle(ep)
    W["epoch_rows"] = ep
    W["epochs"] = [{"epoch": "VDL-22", "ref": "2022-10-03", "status": "SUPERSEDED"},
                   {"epoch": "VDL-24", "ref": W["ref24"].isoformat(), "status": "ADOPTED"},
                   {"epoch": "VDL-24P", "ref": (W["ref24"] - _Gtd(days=21)).isoformat(), "status": "PROVISIONAL"}]


_GRUN_ORDER = ["VOID", "NO_SETUPS", "UNRESOLVED_BM", "UNKNOWN_SECTION", "SEQUENCE_GAP", "UNCERTIFIED_OBSERVER", "NO_TEST",
               "INVALID_COLLIMATION", "NO_CERTIFICATE", "RULED_OUT"]


def _G_content_key(c):
    return (c["at"], c["back"], c["fore"], c["db"], c["df"], c["temp"], c["rb"], c["rf"])


def _G_inverse(M):
    """Exact Gauss-Jordan inverse of a square Fraction matrix."""
    n = len(M)
    A = [list(row) + [_GF(int(i == j)) for j in range(n)] for i, row in enumerate(M)]
    for col in range(n):
        piv = next(r for r in range(col, n) if A[r][col] != 0)
        A[col], A[piv] = A[piv], A[col]
        pv = A[col][col]
        A[col] = [x / pv for x in A[col]]
        for r in range(n):
            if r != col and A[r][col] != 0:
                f = A[r][col]
                rowc = A[col]
                A[r] = [x - f * y for x, y in zip(A[r], rowc)]
    return [row[n:] for row in A]


def _G_adjust(obs, fixed):
    """Exact weighted least squares for one component; heights and observations in mm."""
    free = sorted(({o["from"] for o in obs} | {o["to"] for o in obs}) - set(fixed))
    ix = {b: i for i, b in enumerate(free)}
    u = len(free)
    N = [[_GF(0)] * u for _ in range(u)]
    nv = [_GF(0)] * u
    rows = []
    for o in obs:
        a = {}
        l = o["value"]
        if o["to"] in ix:
            a[ix[o["to"]]] = a.get(ix[o["to"]], 0) + 1
        else:
            l -= fixed[o["to"]]
        if o["from"] in ix:
            a[ix[o["from"]]] = a.get(ix[o["from"]], 0) - 1
        else:
            l += fixed[o["from"]]
        rows.append((a, l))
        p = o["p"]
        for i, ai in a.items():
            nv[i] += ai * p * l
            for j, aj in a.items():
                N[i][j] += ai * p * aj
    Q = _G_inverse(N) if u else []
    x = [sum(Q[i][j] * nv[j] for j in range(u)) for i in range(u)]
    H = dict(fixed)
    for b, i in ix.items():
        H[b] = x[i]
    out = []
    vtpv = _GF(0)
    for o, (a, l) in zip(obs, rows):
        v = sum(ai * x[i] for i, ai in a.items()) - l
        aqa = sum(ai * Q[i][j] * aj for i, ai in a.items() for j, aj in a.items())
        qvv = 1 / o["p"] - aqa
        vtpv += o["p"] * v * v
        out.append({"sec": o["sec"], "v": v, "qvv": qvv})
    qxx = {b: Q[i][i] for b, i in ix.items()}
    return H, out, vtpv, len(obs) - u, qxx


def _G_compute(W, flip=frozenset()):  # noqa: C901
    cfg = W["cfg"]
    S = {"flip": flip}
    ref = W["ref_date"]
    clock = W["clock"]
    order = W["catalog_order"]
    pos = {f: i for i, f in enumerate(order)}
    # ------------------------------------------------------------------ settlement
    lineage = {f: {"file": f, "status": "READ", "records": 0, "kept": 0, "superseded": 0, "void_selected": 0, "duplicates": 0,
                   "conflicts_lost": 0} for f in order}
    groups = {}
    for lay, key, rev, void, c in W["records"]:
        f = W["fname"][lay["file"]]
        lineage_key = lay["file"]
        lineage[lineage_key]["records"] += 1
        groups.setdefault(key, []).append((pos[lay["file"]], rev, void, c, lay["file"]))
    setups = {}
    excl = []
    cnt = {"records_read": sum(v["records"] for v in lineage.values()), "setup_keys": len(groups), "superseded_revisions": 0,
           "duplicates": 0, "conflicts": 0, "void_setups": 0, "kept_setups": 0}
    for key in sorted(groups):
        g = sorted(groups[key], key=lambda r: (r[0], -r[1]))
        top = max(r[1] for r in g)
        for r in g:
            if r[1] < top:
                cnt["superseded_revisions"] += 1
                lineage[r[4]]["superseded"] += 1
        cand = sorted([r for r in g if r[1] == top], key=lambda r: r[0])
        win = cand[0]
        for r in cand[1:]:
            if r[2] == win[2] and _G_content_key(r[3]) == _G_content_key(win[3]):
                cnt["duplicates"] += 1
                lineage[r[4]]["duplicates"] += 1
            else:
                cnt["conflicts"] += 1
                lineage[r[4]]["conflicts_lost"] += 1
        if win[2]:
            cnt["void_setups"] += 1
            lineage[win[4]]["void_selected"] += 1
            excl.append({"kind": "setup", "id": f"{key[0]}#{key[1]}", "reason": "VOID_SETUP"})
            continue
        lineage[win[4]]["kept"] += 1
        cnt["kept_setups"] += 1
        setups[key] = win[3]
    S["counters"] = cnt
    S["lineage"] = [lineage[f] for f in order]
    # ------------------------------------------------------------------ run register
    reg = {}
    for row in W["run_rows"]:
        if row["campaign"] != cfg["campaign"]:
            continue
        reg[row["run"]] = dict(row)
    for a in sorted(W["late"], key=lambda e: e["amend_no"]):
        if a["campaign"] != cfg["campaign"] or a["run"] not in reg:
            continue
        fld = {"status": "status", "setups": "setups", "level": "level", "observer": "observer"}[a["field"]]
        reg[a["run"]][fld] = int(a["value"]) if fld == "setups" else a["value"]
    by_run = {}
    for (rid, seq), c in setups.items():
        by_run.setdefault(rid, {})[seq] = c
    sec_by_pair = {}
    for s in W["sections"].values():
        sec_by_pair[(s["from"], s["to"])] = (s["id"], "F")
        sec_by_pair[(s["to"], s["from"])] = (s["id"], "B")
    inst_alias = {}
    for iid, v in W["instruments"].items():
        for t in v["tokens"]:
            inst_alias[" ".join(t.upper().split())] = iid
    rulings = {}
    cancelled = {a["target"] for a in W["addendum"] if a["campaign"] == cfg["campaign"] and a["action"] == "CANCEL"
                 and _Gdate_of(a["issued"]) <= ref}
    for j in W["j1"]:
        if j["id"] in cancelled or _Gdate_of(j["effective"]) > ref:
            continue
        rulings.setdefault(j["target"], []).append(j)
    if "withdrawn_rulings" in flip:
        for j in W["j0"]:
            rulings.setdefault(j["target"], []).append(j)
    for a in W["addendum"]:
        if a["campaign"] == cfg["campaign"] and a["action"] in ("REJECT_RUN", "REJECT_SECTION") and _Gdate_of(a["issued"]) <= ref:
            rulings.setdefault(a["target"], []).append(a)
    k = _GQ(W["memo"]["k_ref"])
    R = _GF(W["memo"]["earth_radius"])
    limit = _GQ(W["memo"]["c_limit"])
    res_rows = {}
    runs_out = {}
    run_setups = {}
    for rid in sorted(reg):
        row = reg[rid]
        ks = by_run.get(rid, {})
        out = {"run": rid, "status": None, "section": "", "dir": "", "start": "", "end": "", "date": "", "setups": len(ks), "length": None,
               "dh": None, "c": None, "test": "", "row": row}
        runs_out[rid] = out
        if row["status"] == "VOID":
            out["status"] = "VOID"
            continue
        if not ks:
            out["status"] = "NO_SETUPS"
            continue
        first = min(c["at"] for c in ks.values())
        day = _Gutc_to_wall(first, clock).date()
        if "booked_date" in flip:
            day = _Gdate_of(row["booked"])
        out["date"] = day.isoformat()
        a, ha = _G_resolve(W, row["start"], day)
        b, hb = _G_resolve(W, row["end"], day)
        res_rows[("run", row["start"], day)] = (a, ha)
        res_rows[("run", row["end"], day)] = (b, hb)
        out["start"], out["end"] = a or "", b or ""
        if a is None or b is None:
            out["status"] = "UNRESOLVED_BM"
            continue
        if (a, b) not in sec_by_pair:
            out["status"] = "UNKNOWN_SECTION"
            continue
        sid, d = sec_by_pair[(a, b)]
        out["section"], out["dir"] = sid, d
        if sorted(ks) != list(range(1, int(row["setups"]) + 1)):
            out["status"] = "SEQUENCE_GAP"
            continue
        obs = row["observer"].strip().upper()
        if not _G_obs_ok(W, obs, day):
            out["status"] = "UNCERTIFIED_OBSERVER"
            continue
        inst = inst_alias.get(" ".join(row["level"].upper().split()))
        t = _G_test_for(W, inst, first) if inst else None
        if t is None:
            out["status"] = "NO_TEST"
            continue
        out["c"], out["test"] = t["c"], str(t["id"])
        if abs(t["c"]) > limit:
            out["status"] = "INVALID_COLLIMATION"
            continue
        sheet = "Certs_2026_DRAFT" if "draft_certs" in flip else W["prof"]["cert_sheet"]
        missing = False
        for c in ks.values():
            for rod in (c["rb"], c["rf"]):
                if _G_cert_for_sheet(W, sheet, rod, day) is None:
                    missing = True
        if missing:
            out["status"] = "NO_CERTIFICATE"
            continue
        if any(r["action"] == "REJECT_RUN" for r in rulings.get(rid, [])):
            out["status"] = "RULED_OUT"
            continue
        out["status"] = "VALID"
        sec = W["sections"][sid]
        dh_sum = _GF(0)
        length = _GF(0)
        rows = []
        for seq in sorted(ks):
            c = ks[seq]
            T, src = c["temp"], "FIELD"
            if T is None:
                st = _G_station(W, sec["line"], c["at"])
                T, src = _G_met_at(W, st, c["at"])
                if T is None:
                    T, src = _GQ(W["prof"]["fallback_temp"]), "FALLBACK"
            cb = _G_cert_for_sheet(W, sheet, c["rb"], day)
            cf = _G_cert_for_sheet(W, sheet, c["rf"], day)
            ab = _GQ(W["memo"]["rod_types"][W["rods"][c["rb"]]["type"]][1])
            af = _GQ(W["memo"]["rod_types"][W["rods"][c["rf"]]["type"]][1])
            if "no_thermal" in flip:
                ab = af = _GF(0)
            kk = _GF(1) if "no_curvature" in flip else k
            if "single_scale" in flip:
                cf = cb
            vb = _G_corr(c["back"], c["db"], T, cb, ab, t["c"], kk, R)
            vf = _G_corr(c["fore"], c["df"], T, cf, af, t["c"], kk, R)
            raw = c["back"] - c["fore"]
            dh = (vb - vf) if "round_once" in flip else _Gq(vb - vf, 5)
            dh_sum += dh
            length += c["db"] + c["df"]
            rows.append({"run": rid, "seq": seq, "at": c["at"], "rb": c["rb"], "rf": c["rf"], "back": c["back"], "fore": c["fore"],
                         "db": c["db"], "df": c["df"], "temp": T, "src": src, "raw": raw, "dh": dh, "cb": cb["cert"], "cf": cf["cert"]})
        run_setups[rid] = rows
        out["dh"], out["length"] = dh_sum, length
    S["runs"] = runs_out
    S["setups"] = run_setups
    for rid, o in runs_out.items():
        if o["status"] != "VALID":
            excl.append({"kind": "run", "id": rid, "reason": o["status"]})
    # ------------------------------------------------------------------ sections
    line_class = {}
    for lid, ln in W["lines"].items():
        eff = None
        for h in sorted(ln["hist"], key=lambda z: z["from"]):
            if _Gdate_of(h["from"]) <= ref:
                eff = h["class"]
        line_class[lid] = eff
    S["line_class"] = line_class
    tol = W["memo"]["tol"]
    secs_out = {}
    for sid in sorted(W["sections"]):
        s = W["sections"][sid]
        klass = line_class[s["line"]]
        fw = sorted((r for r in runs_out.values() if r["status"] == "VALID" and r["section"] == sid and r["dir"] == "F"), key=lambda r: r["run"])
        bw = sorted((r for r in runs_out.values() if r["status"] == "VALID" and r["section"] == sid and r["dir"] == "B"), key=lambda r: r["run"])
        o = {"sec": sid, "from": s["from"], "to": s["to"], "line": s["line"], "class": klass, "f": "", "b": "", "dhf": None, "dhb": None,
             "d": None, "K": None, "tol": None, "cands": len(fw) * len(bw), "status": None, "value": None}
        secs_out[sid] = o
        if any(r["action"] == "REJECT_SECTION" for r in rulings.get(sid, [])):
            o["status"] = "RULED_OUT"
            continue
        if not fw or not bw:
            o["status"] = "INCOMPLETE"
            continue
        t = _GQ(tol[klass][0])
        best = None
        for f in fw:
            for b in bw:
                d = f["dh"] + b["dh"]
                K = (f["length"] + b["length"]) / 2000
                ok = (1000 * d) ** 2 <= t * t * K
                if "first_pair" in flip:
                    ok = ok and f is fw[0] and b is bw[0]
                if not ok:
                    continue
                keyv = (abs(d), -max(_Gdate_of(f["date"]), _Gdate_of(b["date"])).toordinal(), f["run"], b["run"])
                if best is None or keyv < best[0]:
                    best = (keyv, f, b, d, K)
        if best is None:
            f, b = fw[0], bw[0]
            o.update({"status": "REJECTED_TOLERANCE"})
            continue
        _, f, b, d, K = best
        val = (f["dh"] - b["dh"]) / 2 if "round_once" in flip else _Gq((f["dh"] - b["dh"]) / 2, 5)
        o.update({"f": f["run"], "b": b["run"], "dhf": f["dh"], "dhb": b["dh"], "d": d, "K": K, "tol": t * 1, "status": "ACCEPTED",
                  "value": val})
    S["sections"] = secs_out
    for sid, o in secs_out.items():
        if o["status"] != "ACCEPTED":
            excl.append({"kind": "section", "id": sid, "reason": o["status"]})
    # ------------------------------------------------------------------ control
    state = {}
    jr = sorted(W["journal"], key=lambda e: e["entry"])
    cancelled_e = {e["refers"] for e in jr if e["event"] == "ERRATUM"}
    for e in jr:
        if str(e["entry"]) in cancelled_e or e["event"] == "ERRATUM":
            continue
        if _Gdate_of(e["date"]) > ref:
            continue
        if e["event"] == "DISTURBED":
            state[e["mark"]] = "DISTURBED"
        elif e["event"] == "REVERIFIED":
            state[e["mark"]] = "SOUND"
    c2 = W["memo"]["c2_true"] if "withdrawn_control" not in flip else W["memo"]["c1"]
    controls = []
    fixed = {}
    for tok in W["profile_controls_tokens"]:
        m, hops = _G_resolve(W, tok, ref)
        res_rows[("control", tok, ref)] = (m, hops)
        entry = {"token": tok, "mark": m or "", "status": None, "height": None}
        if m is None:
            entry["status"] = "UNRESOLVED"
        elif m not in c2:
            entry["status"] = "NOT_IN_TABLE"
        elif state.get(m) == "DISTURBED" and "ignore_journal" not in flip:
            entry["status"] = "DEMOTED_DISTURBED"
            entry["height"] = _GQ(c2[m])
        else:
            entry["status"] = "FIXED"
            entry["height"] = _GQ(c2[m])
            fixed[m] = _GQ(c2[m])
        controls.append(entry)
    S["controls"] = controls
    # ------------------------------------------------------------------ components and adjustment
    acc = [o for o in secs_out.values() if o["status"] == "ACCEPTED"]
    parent = {}

    def find(x):
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for o in acc:
        ra, rb = find(o["from"]), find(o["to"])
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    comps = {}
    for o in acc:
        comps.setdefault(find(o["from"]), []).append(o)
    sig = W["memo"]["sigma"]
    kc2 = _GQ(W["memo"]["k_crit"]) ** 2
    r_min, max_rem = W["memo"]["r_min"], W["memo"]["max_removals"]
    iters, nets, heights, resid = [], {}, {}, {}
    for cid in sorted(comps):
        cobs = sorted(comps[cid], key=lambda o: o["sec"])
        marks = sorted({o["from"] for o in cobs} | {o["to"] for o in cobs})
        cid_name = min(marks)
        fx = {m: fixed[m] * 1000 for m in marks if m in fixed}
        net = {"component": cid_name, "marks": len(marks), "fixed": sorted(fx), "status": None, "removed": [], "obs": len(cobs)}
        nets[cid_name] = net
        if not fx:
            net["status"] = "UNCONSTRAINED"
            for o in cobs:
                resid[o["sec"]] = {"sec": o["sec"], "comp": cid_name, "status": "UNCONSTRAINED"}
            continue
        active = [{"sec": o["sec"], "from": o["from"], "to": o["to"], "value": o["value"] * 1000,
                   "p": 1 / (_GQ(sig[o["class"]]) ** 2 * o["K"])} for o in cobs]
        removed = []
        it = 0
        while True:
            it += 1
            H, res, vtpv, r, qxx = _G_adjust(active, fx)
            tested = []
            for x in res:
                if x["qvv"] > 0:
                    w2 = x["v"] * x["v"] / x["qvv"]
                    if "aposteriori" in flip and r > 0:
                        w2 = w2 / (vtpv / r)
                    x["w2"] = w2
                    tested.append((w2, x["sec"]))
            over = [t for t in tested if t[0] > kc2]
            top = sorted(tested, key=lambda t: (-t[0], t[1]))[0] if tested else None
            rec = {"component": cid_name, "iteration": it, "observations": len(active), "unknowns": len(active) - r, "redundancy": r,
                   "vtpv": vtpv, "max_w_section": top[1] if top else "", "max_w2": top[0] if top else None, "action": None}
            if not over:
                rec["action"] = "STOP_CLEAN"
            elif len(removed) >= max_rem:
                rec["action"] = "STOP_BUDGET"
            elif r - 1 < r_min:
                rec["action"] = "STOP_REDUNDANCY"
            else:
                rec["action"] = "REMOVE"
            iters.append(rec)
            if rec["action"] != "REMOVE":
                break
            removed.append(top[1])
            active = [o for o in active if o["sec"] != top[1]]
        net["status"] = {"STOP_CLEAN": "SNOOPED" if removed else "CLEAN", "STOP_BUDGET": "STOP_BUDGET",
                         "STOP_REDUNDANCY": "STOP_REDUNDANCY"}[rec["action"]]
        net["removed"] = removed
        net.update({"redundancy": r, "vtpv": vtpv, "unknowns": len(active) - r, "obs": len(active)})
        for b in marks:
            heights[b] = {"mark": b, "comp": cid_name, "h_mm": H[b], "status": "FIXED" if b in fx else "ADJUSTED",
                          "qxx": _GF(0) if b in fx else qxx[b]}
        for x in res:
            resid[x["sec"]] = {"sec": x["sec"], "comp": cid_name, "status": "USED" if x["qvv"] > 0 else "UNTESTABLE", "v": x["v"],
                               "qvv": x["qvv"], "w2": x.get("w2")}
        for sid in removed:
            o = next(o for o in cobs if o["sec"] == sid)
            v = H[o["to"]] - H[o["from"]] - o["value"] * 1000
            resid[sid] = {"sec": sid, "comp": cid_name, "status": "REMOVED", "v": v, "qvv": None, "w2": None}
            excl.append({"kind": "section", "id": sid, "reason": "SNOOPED"})
    S["iterations"], S["nets"], S["heights"], S["resid"] = iters, nets, heights, resid
    # ------------------------------------------------------------------ loops
    loops_out = []
    by_pair = {}
    for o in secs_out.values():
        if o["status"] == "ACCEPTED":
            by_pair[(o["from"], o["to"])] = (o, 1)
            by_pair[(o["to"], o["from"])] = (o, -1)
    for lp in W["loops"]:
        toks = lp["tokens"]
        marks = []
        for t in toks:
            m, hops = _G_resolve(W, t, ref)
            res_rows[("loop", t, ref)] = (m, hops)
            marks.append(m)
        entry = {"id": lp["id"], "class": lp["class"], "n": len(marks), "status": None, "w": None, "K": None, "tol": None}
        loops_out.append(entry)
        tot, K, ok = _GF(0), _GF(0), True
        for a, b in zip(marks, marks[1:] + marks[:1]):
            hit = by_pair.get((a, b)) if a and b else None
            if hit is None:
                ok = False
                break
            o, sgn = hit
            tot += sgn * o["value"]
            K += o["K"]
        if not ok:
            entry["status"] = "INCOMPLETE"
            continue
        t = _GQ(tol[lp["class"]][1])
        w = tot * 1000
        entry.update({"w": w, "K": K, "tol": t, "status": "PASS" if w * w <= t * t * K else "FAIL"})
    S["loops"] = loops_out
    # ------------------------------------------------------------------ rates
    ep = {e["epoch"]: e for e in W["epochs"]}
    e24 = ep[W["prof_epoch"]]
    d24 = _Gdate_of(e24["ref"])
    years = _GF((ref - d24).days * 4, 1461)
    prior = {}
    for r in W["epoch_rows"]:
        if r["epoch"] != W["prof_epoch"]:
            continue
        m, hops = _G_resolve(W, r["mark"], d24)
        res_rows[("epoch", r["mark"], d24)] = (m, hops)
        if m:
            prior[m] = r
    dist = set()
    for e in jr:
        if str(e["entry"]) in cancelled_e or e["event"] != "DISTURBED":
            continue
        if d24 < _Gdate_of(e["date"]) <= ref:
            dist.add(e["mark"])
    kr2 = _GQ(W["memo"]["k_rate"]) ** 2
    alert = _GQ(W["memo"]["alert"])
    rates = {}
    for b, h in heights.items():
        h26 = _Gq(h["h_mm"] / 1000, 5)
        s26 = _Gsqrt_q(h["qxx"], 2)
        o = {"mark": b, "h24": None, "h26": h26, "rate": None, "srate": None, "class": None}
        rates[b] = o
        if h["status"] == "FIXED":
            o["class"] = "CONTROL"
            continue
        if b in dist:
            o["class"] = "DISTURBED"
            continue
        if b not in prior:
            o["class"] = "NEW"
            continue
        p = prior[b]
        o["h24"] = p["h"]
        rate = (h26 - p["h"]) * 1000 / years
        var = (s26 * s26 + p["sigma"] * p["sigma"]) / (years * years)
        o["rate"], o["srate"] = rate, var
        sigf = rate * rate > kr2 * var
        if sigf and rate <= alert:
            o["class"] = "ALERT"
        elif sigf and rate < 0:
            o["class"] = "SUBSIDING"
        elif sigf and rate > 0:
            o["class"] = "UPLIFT"
        else:
            o["class"] = "STABLE"
    S["rates"] = rates
    S["years"] = years
    S["resolution"] = res_rows
    S["excluded"] = excl
    S["state"] = state
    return S


def _G_cert_for_sheet(W, sheet, serial, day):
    best = None
    for c in W["cert_sheets"].get(sheet, []):
        if c["serial"] == serial and c["from"] <= day <= c["to"]:
            if best is None or c["from"] > best["from"]:
                best = c
    return best


# chi-square quantiles (2.5 % and 97.5 %) for 1..80 degrees of freedom, three decimals
_GCHI2 = [('0.001', '5.024'), ('0.051', '7.378'), ('0.216', '9.348'), ('0.484', '11.143'), ('0.831', '12.833'), ('1.237', '14.449'), ('1.690', '16.013'), ('2.180', '17.535'), ('2.700', '19.023'), ('3.247', '20.483'), ('3.816', '21.920'), ('4.404', '23.337'), ('5.009', '24.736'), ('5.629', '26.119'), ('6.262', '27.488'), ('6.908', '28.845'), ('7.564', '30.191'), ('8.231', '31.526'), ('8.907', '32.852'), ('9.591', '34.170'), ('10.283', '35.479'), ('10.982', '36.781'), ('11.689', '38.076'), ('12.401', '39.364'), ('13.120', '40.646'), ('13.844', '41.923'), ('14.573', '43.195'), ('15.308', '44.461'), ('16.047', '45.722'), ('16.791', '46.979'), ('17.539', '48.232'), ('18.291', '49.480'), ('19.047', '50.725'), ('19.806', '51.966'), ('20.569', '53.203'), ('21.336', '54.437'), ('22.106', '55.668'), ('22.878', '56.896'), ('23.654', '58.120'), ('24.433', '59.342'), ('25.215', '60.561'), ('25.999', '61.777'), ('26.785', '62.990'), ('27.575', '64.201'), ('28.366', '65.410'), ('29.160', '66.617'), ('29.956', '67.821'), ('30.755', '69.023'), ('31.555', '70.222'), ('32.357', '71.420'), ('33.162', '72.616'), ('33.968', '73.810'), ('34.776', '75.002'), ('35.586', '76.192'), ('36.398', '77.380'), ('37.212', '78.567'), ('38.027', '79.752'), ('38.844', '80.936'), ('39.662', '82.117'), ('40.482', '83.298'), ('41.303', '84.476'), ('42.126', '85.654'), ('42.950', '86.830'), ('43.776', '88.004'), ('44.603', '89.177'), ('45.431', '90.349'), ('46.261', '91.519'), ('47.092', '92.689'), ('47.924', '93.856'), ('48.758', '95.023'), ('49.592', '96.189'), ('50.428', '97.353'), ('51.265', '98.516'), ('52.103', '99.678'), ('52.942', '100.839'), ('53.782', '101.999'), ('54.623', '103.158'), ('55.466', '104.316'), ('56.309', '105.473'), ('57.153', '106.629')]
_GCHI2_ONE = ['3.841', '5.991', '7.815', '9.488', '11.070', '12.592', '14.067', '15.507', '16.919', '18.307', '19.675', '21.026', '22.362', '23.685', '24.996', '26.296', '27.587', '28.869', '30.144', '31.410', '32.671', '33.924', '35.172', '36.415', '37.652', '38.885', '40.113', '41.337', '42.557', '43.773', '44.985', '46.194', '47.400', '48.602', '49.802', '50.998', '52.192', '53.384', '54.572', '55.758', '56.942', '58.124', '59.304', '60.481', '61.656', '62.830', '64.001', '65.171', '66.339', '67.505', '68.669', '69.832', '70.993', '72.153', '73.311', '74.468', '75.624', '76.778', '77.931', '79.082', '80.232', '81.381', '82.529', '83.675', '84.821', '85.965', '87.108', '88.250', '89.391', '90.531', '91.670', '92.808', '93.945', '95.081', '96.217', '97.351', '98.484', '99.617', '100.749', '101.879']


def _G_memo(W, rng) -> None:
    """Effective governance memo values (tables after errata) plus the printed tables."""
    cfg = W["cfg"]
    m = {"tol": W["tol_true"], "tol_printed": {k: list(v) for k, v in cfg["tol"].items()}, "sigma": dict(cfg["sigma"]),
         "k_crit": cfg["k_crit"], "r_min": cfg["r_min"], "max_removals": cfg["max_removals"], "c_limit": cfg["c_limit"],
         "k_ref": cfg["k_ref"], "rod_types": {k: list(v) for k, v in cfg["rod_types"].items()}, "alert": cfg["alert"],
         "k_rate": cfg["k_rate"], "earth_radius": cfg["earth_radius"]}
    c2 = dict(W["c2"])
    printed = dict(c2)
    errata = []
    ctrl = [c for c in W["control_true"] if c not in W["demoted"] and c in c2]
    rng.shuffle(ctrl)
    tgt = ctrl[0]
    txt = c2[tgt]
    ip, fp = txt.split(".")
    swapped = fp[:2] + fp[3] + fp[2] + fp[4:]
    if swapped == fp:
        swapped = fp[:2] + str((int(fp[2]) + 3) % 10) + fp[3:]
    printed[tgt] = ip + "." + swapped
    errata.append({"id": "E-2", "table": "C-2", "text": f"Table C-2, mark {tgt}: for {printed[tgt]} read {txt}"})
    errata.append({"id": "E-3", "table": "T-1", "text": f"Table T-1, class {cfg['tol_erratum'][0]}, section column: for {cfg['tol'][cfg['tol_erratum'][0]][0]} read {cfg['tol_erratum'][1]}"})
    m["c2_true"], m["c2_printed"], m["c1"], m["errata"] = c2, printed, dict(W["c1"]), errata
    W["memo"] = m


def _G_sheets(W, rng) -> None:
    sheets = {W["prof"]["cert_sheet"]: W["certs"]}
    dr = []
    for c in W["certs"]:
        d = dict(c)
        d["ppm"] = c["ppm"] + _GF(rng.choice([-1, 1]) * rng.randint(30, 90), 10)
        dr.append(d)
    sheets["Certs_2026_DRAFT"] = dr
    old = []
    for c in W["certs"]:
        d = dict(c)
        d["ppm"] = c["ppm"] + _GF(rng.randint(-60, 60), 10)
        d["from"] = c["from"] - _Gtd(days=1100)
        d["to"] = c["to"] - _Gtd(days=1100)
        d["cert"] = "RC-" + str(int(c["cert"][3:]) - 2500)
        old.append(d)
    sheets["Certs_2023"] = old
    if W["prof"]["cert_sheet"] != "Certs_2026B":
        alt = []
        for c in W["certs"]:
            d = dict(c)
            d["ppm"] = c["ppm"] + _GF(rng.choice([-1, 1]) * rng.randint(15, 45), 10)
            alt.append(d)
        sheets["Certs_2026B"] = alt
    W["cert_sheets"] = sheets


def _G_tokens(W, rng) -> None:
    W["profile_controls_tokens"] = [_G_bm_token(W, rng, c) if c in W["bms"] else c.lower() for c in W["profile_controls"]]
    for lp in W["loops"]:
        lp["tokens"] = [_G_bm_token(W, rng, b) for b in lp["marks"]]
    W["prof_epoch"] = "VDL-24"


def _G_x_run_id(W, rng) -> str:
    used = set(W["runs"]) | {r["run"] for r in W["run_rows"]}
    while True:
        rid = f"R-26-{rng.randint(1, 9998):04d}"
        if rid not in used:
            return rid


def _G_x_line(W, rng, block) -> str:
    while True:
        lid = f"DL-{rng.randint(700, 899):03d}"
        if lid not in W["lines"]:
            break
    W["lines"][lid] = {"id": lid, "block": block, "class": "II", "spur": False,
                       "hist": [{"from": _Gdate(2019 + rng.randint(0, 4), rng.randint(1, 12), 1).isoformat(), "class": "II"}]}
    W["line_station"][lid] = [(_Gdate(2019 + rng.randint(0, 5), rng.randint(1, 12), 1), rng.choice(sorted(W["stations"])))]
    return lid


def _G_x_mark(W, rng, block, kind, h) -> str:
    bid = f"VD-{W['bm_pool'].pop():04d}"
    W["bms"][bid] = {"id": bid, "block": block, "kind": kind, "desc": rng.choice(_GMARK_DESC), "nbr": [],
                     "h": _Gq(min(max(h, _GF(30, 100)), _GF(1150, 100)), 5)}
    W["master"].add(bid)
    return bid


def _G_x_section(W, rng, a, b, lid) -> str:
    while True:
        sid = f"S-{rng.randint(1, 989):04d}"
        if sid not in W["sections"]:
            break
    fr, to = (a, b) if rng.random() < 0.5 else (b, a)
    W["sections"][sid] = {"id": sid, "from": fr, "to": to, "line": lid, "block": W["bms"][a]["block"], "len": _GF(rng.randint(5000, 9000), 10)}
    W["bms"][a]["nbr"].append(b)
    W["bms"][b]["nbr"].append(a)
    return sid


def _G_x_run(W, rng, sid, direction, want="ok", err=0.0, setups=True) -> dict:
    """A run of a section placed by _G_pick_slot, with its setups generated."""
    run = {"id": _G_x_run_id(W, rng), "sec": sid, "dir": direction, "kind": want}
    _G_pick_slot(W, rng, run, want, W["sections"][sid])
    run["err_mm"] = err
    run["layout"] = rng.choice(list(_GLAYOUTS))
    run["n"] = rng.randint(10, 20)
    W["runs"][run["id"]] = run
    if setups:
        _G_run_setups(W, rng, run["id"])
    return run


def _G_x_emit(W, rng, run, gap=False) -> None:
    """One booking per setup in the run's home shard; with gap, a void second revision drops a middle setup."""
    home = run["layout"]
    for seq in range(1, run["n"] + 1):
        key = (run["id"], seq)
        c = W["setups"][key]
        W["records"].append((home, key, 1, False, c))
        if gap and seq == max(2, run["n"] // 2):
            v = dict(c)
            v["fore"] = c["fore"] + _GF(rng.choice([-1, 1]) * rng.randint(4, 90), 100000)
            others = [x for x in _GLAYOUTS if x is not home and _G_same_cap(x, c)]
            W["records"].append((rng.choice(others), key, 2, True, v))


def _G_x_row(W, rng, run, start=None, end=None, level=None, status="OK", note="") -> None:
    s = W["sections"][run["sec"]]
    a, b = (s["from"], s["to"]) if run["dir"] == "F" else (s["to"], s["from"])
    row = {"run": run["id"], "campaign": W["cfg"]["campaign"],
           "start": start if start is not None else _G_bm_token(W, rng, a),
           "end": end if end is not None else _G_bm_token(W, rng, b),
           "booked": (run["day"] + _Gtd(days=rng.choice([0, 0, 0, 1]))).isoformat(),
           "level": level if level is not None else rng.choice(W["instruments"][run["inst"]]["tokens"]),
           "pair": run["pair"], "observer": run["obs"] if rng.random() < 0.8 else run["obs"].lower(), "setups": run["n"],
           "status": status, "note": note}
    W["run_rows"].insert(rng.randint(0, len(W["run_rows"])), row)


def _G_x_dead_tokens(W, rng, k) -> list:
    """Tokens that resolve to nothing: expired provisional numbers first, then numbers no register knows."""
    known = {r["token"] for r in W["alias_rows"]}
    live = {r["token"] for r in W["alias_rows"] if r["to"] is None or r["to"] > W["start"]}
    out = sorted({r["token"] for r in W["alias_rows"] if r["note"] == "expired provisional number"} - live - W["master"])
    rng.shuffle(out)
    while len(out) < k:
        tok = f"VD-{rng.randint(1, 999):04d}"
        if tok not in W["master"] and tok not in known and tok not in out:
            out.append(tok)
    return out[:k]


def _G_extras(W, rng) -> None:  # noqa: C901
    """Fixtures for the precedence pairs of H9, H14, H16 and H17, the r = 0 global test and the H10 and H13 ties."""
    cfg = W["cfg"]
    camp = cfg["campaign"]
    ref = W["ref_date"]
    start = W["start"]
    block = W["blocks"][-1]["id"]
    plain = [s for s in sorted(W["sections"]) if not W["sections"][s].get("after") and s != W["ruled_section"]]
    dead = _G_x_dead_tokens(W, rng, 3)

    # H9 VOID before NO_SETUPS: voided in the register, nothing booked anywhere
    r = _G_x_run(W, rng, rng.choice(plain), rng.choice(["F", "B"]), setups=False)
    del W["runs"][r["id"]]
    _G_x_row(W, rng, r, status="VOID", note="abandoned before the first setup")
    # NO_SETUPS before UNRESOLVED_BM: an unresolvable start token, setups only in the retired shard
    r = _G_x_run(W, rng, rng.choice(plain), rng.choice(["F", "B"]))
    for seq in range(1, r["n"] + 1):
        W["stale"].append((_GRETIRED, (r["id"], seq), 9, False, W["setups"][(r["id"], seq)]))
    _G_x_row(W, rng, r, start=dead[0])
    # UNRESOLVED_BM before UNKNOWN_SECTION and the observer test: an expired end token, booked by a lapsed observer
    r = _G_x_run(W, rng, rng.choice(plain), rng.choice(["F", "B"]), want="lapsed")
    _G_x_emit(W, rng, r)
    _G_x_row(W, rng, r, end=dead[1])
    # UNKNOWN_SECTION before SEQUENCE_GAP: from one mark to the next but one along a line, a middle setup voided
    chain = []
    pairs = {(s["from"], s["to"]) for s in W["sections"].values()}
    for b in sorted(W["bms"]):
        v = W["bms"][b]
        if v["kind"] == "LINE" and not v.get("since") and len(v["nbr"]) == 2:
            a, c = v["nbr"]
            if (a, c) not in pairs and (c, a) not in pairs:
                sid = next((s for s in plain if {W["sections"][s]["from"], W["sections"][s]["to"]} == {a, b}), None)
                if sid:
                    chain.append((a, c, sid))
    a, c, sid = rng.choice(chain)
    r = _G_x_run(W, rng, sid, rng.choice(["F", "B"]))
    _G_x_emit(W, rng, r, gap=True)
    _G_x_row(W, rng, r, start=_G_bm_token(W, rng, a), end=_G_bm_token(W, rng, c))
    # SEQUENCE_GAP before UNCERTIFIED_OBSERVER: a voided middle setup and a lapsed observer
    r = _G_x_run(W, rng, rng.choice(plain), rng.choice(["F", "B"]), want="lapsed")
    _G_x_emit(W, rng, r, gap=True)
    _G_x_row(W, rng, r)
    # UNCERTIFIED_OBSERVER before NO_TEST: a lapsed observer on a level first tested after the run
    used_n = {int(i[3:]) for i in W["instruments"]}
    n = rng.choice([x for x in range(100, 400) if x not in used_n])
    iid = f"LV-{n:04d}"
    W["instruments"][iid] = {"id": iid, "campaign": False, "tokens": [iid, f"lv{n}", f"Level {n}", f"DNA03-{n}"]}
    r = _G_x_run(W, rng, rng.choice(plain), rng.choice(["F", "B"]), want="lapsed", setups=False)
    r["inst"] = iid
    _G_run_setups(W, rng, r["id"])
    _G_x_emit(W, rng, r)
    _G_x_row(W, rng, r)
    first = r["day"] + _Gtd(days=rng.randint(2, 6))
    W["tests"].append({"id": max(t["id"] for t in W["tests"]) + rng.randint(1, 4), "inst": iid,
                       "at": _Gwall_to_utc(_Gdt(first.year, first.month, first.day, 7, rng.randint(0, 59), 0), W["clock"]),
                       "c": _GF(rng.randint(-1500, 1500), 1000), "result": "PASS", "operator": rng.choice(_GOBS_NAMES)})
    # INVALID_COLLIMATION before NO_CERTIFICATE: the out-of-limit level on a day the gap rod has no certificate
    run = {"id": _G_x_run_id(W, rng), "dir": rng.choice(["F", "B"]), "kind": "x"}
    run["sec"] = rng.choice(plain)
    run["pair"] = next(p for p, ab in sorted(W["pairs"].items()) if W["gap_rod"] in ab)
    run["inst"] = W["bad_inst"]
    while True:
        day = start + _Gtd(days=rng.randint(20, 21))
        run["obs"] = rng.choice(_GOBS_NAMES)
        run["day"] = day
        run["t0"] = _Gwall_to_utc(_Gdt(day.year, day.month, day.day, rng.randint(9, 15), rng.randint(0, 59), rng.randint(0, 59)), W["clock"])
        t = _G_test_for(W, run["inst"], run["t0"])
        if _G_obs_ok(W, run["obs"], day) and t is not None and abs(t["c"]) > _GQ(cfg["c_limit"]) and _G_cert_for(W, W["gap_rod"], day) is None:
            break
    run.update({"err_mm": 0.0, "layout": rng.choice(list(_GLAYOUTS))})
    W["runs"][run["id"]] = run
    _G_run_setups(W, rng, run["id"])
    _G_x_emit(W, rng, run)
    _G_x_row(W, rng, run)
    # NO_CERTIFICATE before RULED_OUT: a run on the gap days that an addendum ruling also rejects
    r = _G_x_run(W, rng, rng.choice(plain), rng.choice(["F", "B"]), want="cert_gap")
    _G_x_emit(W, rng, r)
    _G_x_row(W, rng, r)
    W["addendum"].insert(rng.randint(0, len(W["addendum"])), {"id": "A-26-06", "campaign": camp, "action": "REJECT_RUN", "target": r["id"],
                                                             "issued": (ref - _Gtd(days=rng.randint(5, 12))).isoformat(),
                                                             "note": "rod pair swapped in the field"})

    sig = float(_GQ(W["memo"]["sigma"]["II"]))

    def double_run(sid, delta=0.0):
        K = float(W["sections"][sid]["len"]) / 1000
        for d in ("F", "B"):
            e = rng.normal() * 0.2 * sig * _Gsqrtf(K)
            r = _G_x_run(W, rng, sid, d, err=e + (delta if d == "F" else -delta))
            _G_x_emit(W, rng, r)
            _G_x_row(W, rng, r)

    def control(mark):
        txt = _Gs(W["bms"][mark]["h"], 5)
        W["c2"][mark] = W["memo"]["c2_true"][mark] = W["memo"]["c2_printed"][mark] = txt
        W["profile_controls_tokens"].insert(rng.randint(0, len(W["profile_controls_tokens"])), _G_bm_token(W, rng, mark))

    # H18 NO_REDUNDANCY: a fixed mark with a two-section tree; H14 RULED_OUT before INCOMPLETE on its single-run tail
    lid = _G_x_line(W, rng, block)
    h = _GF(rng.randint(250000, 600000), 100000)
    tree = [_G_x_mark(W, rng, block, "JUNCTION", h)]
    for kind in ("LINE", "LINE", "SPUR"):
        h = h + _GF(rng.randint(-90000, 90000), 100000)
        tree.append(_G_x_mark(W, rng, block, kind, h))
    control(tree[0])
    for a, b in zip(tree[:2], tree[1:3]):
        double_run(_G_x_section(W, rng, a, b, lid))
    tail = _G_x_section(W, rng, tree[2], tree[3], lid)
    r = _G_x_run(W, rng, tail, rng.choice(["F", "B"]))
    _G_x_emit(W, rng, r)
    _G_x_row(W, rng, r)
    W["addendum"].insert(rng.randint(0, len(W["addendum"])), {"id": "A-26-07", "campaign": camp, "action": "REJECT_SECTION", "target": tail,
                                                             "issued": (ref - _Gtd(days=3)).isoformat(), "note": "mark not recovered at resurvey"})
    # H17 STOP_BUDGET with the redundancy floor also reached: two fixed marks joined by five two-section paths,
    # four of them carrying outliers of decreasing size
    h = _GF(rng.randint(250000, 600000), 100000)
    ends = [_G_x_mark(W, rng, block, "JUNCTION", h), _G_x_mark(W, rng, block, "JUNCTION", h + _GF(rng.randint(-80000, 80000), 100000))]
    for m in ends:
        control(m)
    sizes = [17.0, 13.0, 9.5, 6.5, 0.0]
    rng.shuffle(sizes)
    for w in sizes:
        lid = _G_x_line(W, rng, block)
        mid = _G_x_mark(W, rng, block, "LINE", h + _GF(rng.randint(-90000, 90000), 100000))
        sa = _G_x_section(W, rng, ends[0], mid, lid)
        sb = _G_x_section(W, rng, mid, ends[1], lid)
        K = (float(W["sections"][sa]["len"]) + float(W["sections"][sb]["len"])) / 1000
        double_run(sa, rng.choice([-1, 1]) * w * sig * _Gsqrtf(K))
        double_run(sb)

    # H10 equal instants: a twin of an effective test with a lower id and another collimation
    eff = set()
    for run in W["runs"].values():
        if run["kind"] == "ok" and run["inst"] not in (W["bad_inst"], W["new_inst"]):
            t = _G_test_for(W, run["inst"], run["t0"])
            if t is not None:
                eff.add(t["id"])
    tid = rng.choice(sorted(eff))
    t = next(x for x in W["tests"] if x["id"] == tid)
    W["tests"].append({"id": min(x["id"] for x in W["tests"]) - rng.randint(2, 30), "inst": t["inst"], "at": t["at"],
                       "c": t["c"] - _GF(410, 1000) if t["c"] > 0 else t["c"] + _GF(410, 1000), "result": "PASS", "operator": rng.choice(_GOBS_NAMES)})
    # H13 several applicable rows: an older row for a legacy number that run tokens use
    toks = {_G_norm_bm(x) for row in W["run_rows"] if row["campaign"] == camp for x in (row["start"], row["end"])}
    cands = [b for b in sorted(W["legacy"]) if W["legacy"][b][0] in toks]
    b = rng.choice(cands)
    other = rng.choice([x for x in sorted(W["bms"]) if x != b and W["bms"][x]["kind"] == "JUNCTION"])
    W["alias_rows"].append({"token": W["legacy"][b][0], "canonical": other, "from": _Gdate(2015 + rng.randint(0, 4), rng.randint(1, 12), 1),
                            "to": None, "note": "board number, superseded by the 2021 renumbering"})
    # H16 UNRESOLVED before NOT_IN_TABLE before DEMOTED_DISTURBED: a dead control token, and a disturbance of the mark with no C-2 height
    W["profile_controls_tokens"].insert(rng.randint(0, len(W["profile_controls_tokens"])), dead[2])
    nt = next(m for m in W["profile_controls"] if m not in W["memo"]["c2_true"])
    W["journal"].insert(rng.randint(0, len(W["journal"])), {"entry": max(e["entry"] for e in W["journal"]) + rng.randint(1, 3), "mark": nt,
                                                            "event": "DISTURBED", "date": (start + _Gtd(days=rng.randint(3, 30))).isoformat(),
                                                            "refers": "", "note": "pillar tilted"})


def _Gbuild(seed: int, over=None) -> dict:
    cfg = _Gcfg(over, seed)
    W = _G_world(seed, cfg)
    _G_controls(W, _G_rng(seed, "controls"))
    _G_instruments(W, _G_rng(seed, "instruments"))
    _G_rods(W, _G_rng(seed, "rods"))
    _G_met(W, _G_rng(seed, "met"))
    _G_observers(W, _G_rng(seed, "observers"))
    _G_profile(W, _G_rng(seed, "profile"))
    _G_memo(W, _G_rng(seed, "memo"))
    _G_sheets(W, _G_rng(seed, "sheets"))
    _G_plan_runs(W, _G_rng(seed, "plan"))
    _G_assign_layouts(W, _G_rng(seed, "layouts"))
    _G_setups(W, _G_rng(seed, "setups"))
    _G_emit(W, _G_rng(seed, "emit"))
    _G_registers(W, _G_rng(seed, "registers"))
    _G_tokens(W, _G_rng(seed, "tokens"))
    _G_extras(W, _G_rng(seed, "extras"))
    W["chi2"] = _GCHI2
    files = [x["file"] for x in _GLAYOUTS] + [_GRETIRED["file"]]
    if cfg["rename"]:
        W["fname"] = {f: f"zz{i:02d}_{f.split('.')[0][3:][::-1]}.{f.split('.')[1]}" for i, f in enumerate(sorted(files))}
    else:
        W["fname"] = {f: f for f in files}
    return W


def _Ggenerate(data, seed: int, over=None) -> dict:
    W = _Gbuild(seed, over)
    _G_decoys(W, _G_rng(seed, "decoys"))
    data = _GPath(data)
    data.mkdir(parents=True, exist_ok=True)
    wr = _G_rng(seed, "write")
    _G_write_shards(W, data, wr)
    _G_write_met(W, data, wr)
    _G_write_registers(W, data, wr)
    _G_write_profile(W, data, wr)
    _G_write_workbook(W, data, wr)
    _G_write_memo(W, data, wr)
    _G_write_texts(W, data, wr)
    _G_write(data / _GFILES["handbook"], _GHANDBOOK)
    _G_write(data / _GFILES["layouts"], _G_layouts_md(W))
    _G_write(data / _GFILES["contract"], _G_contract_md())
    return W


def _G_derive(W, flip=frozenset()) -> dict:
    return _G_render(W, _G_compute(W, frozenset(flip)))


_GREPORTS = ["setup_ledger.csv", "run_summaries.tsv", "section_pairs.psv", "benchmark_resolution.csv", "control_points.json",
             "adjustment_iterations.jsonl", "adjusted_heights.csv", "residuals.tsv", "network_summary.json", "loop_closures.xml",
             "subsidence_rates.csv", "excluded_records.jsonl", "dedup_report.json", "source_lineage.json", "rod_certificates_used.tsv",
             "parameters_used.yaml", "variance_vs_published.csv", "rate_vs_published.psv", "dashboard_disagreements.csv",
             "cache_divergence.jsonl", "reconciliation.md"]
_GCORE = ["setup_ledger.csv", "run_summaries.tsv", "section_pairs.psv", "adjustment_iterations.jsonl", "adjusted_heights.csv",
          "residuals.tsv", "network_summary.json", "subsidence_rates.csv"]
_GPUBLISHED_FLIPS = frozenset({"withdrawn_control", "single_scale", "no_thermal", "first_pair", "aposteriori", "booked_date"})


class _GN(str):
    """A number already written as exact decimal text."""


def _Gjson_text(o) -> str:
    if isinstance(o, _GN):
        return str(o)
    if o is None:
        return "null"
    if isinstance(o, bool):
        return "true" if o else "false"
    if isinstance(o, int):
        return str(o)
    if isinstance(o, str):
        return _Gjson.dumps(o)
    if isinstance(o, list):
        return "[" + ",".join(_Gjson_text(x) for x in o) + "]"
    if isinstance(o, dict):
        return "{" + ",".join(_Gjson.dumps(k) + ":" + _Gjson_text(v) for k, v in o.items()) + "}"
    raise TypeError(type(o))


def _Gtab(header, rows, sep) -> str:
    out = [sep.join(header)]
    for r in rows:
        out.append(sep.join("" if v is None else str(v) for v in r))
    return "\n".join(out) + "\n"


def _GNs(x, dp):
    return None if x is None else _GN(_Gs(x, dp))


def _G_w(v, qvv):
    if qvv is None or qvv == 0:
        return None
    w = _Gsqrt_q(v * v / qvv, 2)
    return -w if v < 0 else w


def _G_render(W, S) -> dict:  # noqa: C901
    cfg = W["cfg"]
    out = {}
    rows = []
    for rid in sorted(S["setups"]):
        for r in S["setups"][rid]:
            rows.append([rid, r["seq"], _Giso_z(r["at"]), r["rb"], r["rf"], _Gs(r["back"], 5), _Gs(r["fore"], 5), _Gs(r["db"], 1), _Gs(r["df"], 1),
                         _Gs(r["temp"], 1), r["src"], _Gs(r["raw"], 5), _Gs(r["dh"], 5)])
    out["setup_ledger.csv"] = _Gtab(["run_id", "seq", "instant_utc", "back_rod", "fore_rod", "back_m", "fore_m", "back_dist_m", "fore_dist_m",
                                     "temp_c", "temp_source", "dh_raw_m", "dh_m"], rows, ",")
    rows = []
    for rid in sorted(S["runs"]):
        o = S["runs"][rid]
        valid = o["status"] == "VALID"
        rows.append([rid, o["section"], o["dir"], o["start"], o["end"], o["date"], o["setups"], _Gs(o["length"], 1) if valid else "",
                     _Gs(o["dh"], 5) if valid else "", o["test"], _Gs(o["c"], 3) if o["c"] is not None else "", o["status"]])
    out["run_summaries.tsv"] = _Gtab(["run_id", "section_id", "direction", "start_mark", "end_mark", "run_date", "setups", "length_m", "dh_m",
                                      "test_id", "collimation_mm_per_100m", "status"], rows, "\t")
    rows = []
    for sid in sorted(S["sections"]):
        o = S["sections"][sid]
        a = o["status"] == "ACCEPTED"
        rows.append([sid, o["from"], o["to"], o["line"], o["class"], o["f"], o["b"], _Gs(o["dhf"], 5) if a else "", _Gs(o["dhb"], 5) if a else "",
                     _Gs(o["d"] * 1000, 2) if a else "", _Gs(o["K"], 5) if a else "",
                     _Gs(_Gsqrt_q(o["tol"] * o["tol"] * o["K"], 2), 2) if a else "", o["cands"], o["status"], _Gs(o["value"], 5) if a else ""])
    out["section_pairs.psv"] = _Gtab(["section_id", "from_mark", "to_mark", "line_id", "class", "forward_run", "backward_run", "dh_forward_m",
                                      "dh_backward_m", "discrepancy_mm", "length_km", "tolerance_mm", "candidates", "status", "value_m"], rows, "|")
    rows = []
    for (ctx, tok, day), (m, hops) in sorted(S["resolution"].items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        rows.append([ctx, tok, day.isoformat(), m or "", hops, "RESOLVED" if m else "UNRESOLVED"])
    out["benchmark_resolution.csv"] = _Gtab(["context", "token", "resolve_date", "mark", "hops", "status"], rows, ",")
    ctl = [{"token": c["token"], "mark": c["mark"], "status": c["status"], "height_m": _GNs(c["height"], 5)} for c in S["controls"]]
    out["control_points.json"] = _Gjson_text({"campaign": cfg["campaign"], "reference_date": W["ref_date"].isoformat(), "table": "C-2",
                                              "controls": ctl}) + "\n"
    lines = []
    for it in S["iterations"]:
        lines.append(_Gjson_text({"component": it["component"], "iteration": it["iteration"], "observations": it["observations"],
                                  "unknowns": it["unknowns"], "redundancy": it["redundancy"], "vtpv": _GN(_Gs(it["vtpv"], 4)),
                                  "max_w": _GNs(_Gsqrt_q(it["max_w2"], 2), 2) if it["max_w2"] is not None else None,
                                  "max_w_section": it["max_w_section"] or None, "action": it["action"]}))
    out["adjustment_iterations.jsonl"] = "".join(x + "\n" for x in lines)
    rows = []
    for b in sorted(S["heights"]):
        h = S["heights"][b]
        rows.append([b, h["comp"], _Gs(h["h_mm"] / 1000, 5), _Gs(_Gsqrt_q(h["qxx"], 2), 2), h["status"]])
    out["adjusted_heights.csv"] = _Gtab(["mark", "component", "height_m", "sigma_mm", "status"], rows, ",")
    rows = []
    for sid in sorted(S["resid"]):
        x = S["resid"][sid]
        if x["status"] == "UNCONSTRAINED":
            rows.append([sid, x["comp"], "", "", "", "UNCONSTRAINED"])
            continue
        rows.append([sid, x["comp"], _Gs(x["v"], 2), _Gs(x["qvv"], 4) if x["qvv"] is not None else "",
                     _Gs(_G_w(x["v"], x["qvv"]), 2) if x["status"] == "USED" else "", x["status"]])
    out["residuals.tsv"] = _Gtab(["section_id", "component", "v_mm", "qvv_mm2", "w", "status"], rows, "\t")
    comps = []
    chi = W["chi2"]
    for cid in sorted(S["nets"]):
        n = S["nets"][cid]
        if n["status"] == "UNCONSTRAINED":
            comps.append({"component": cid, "marks": n["marks"], "observations": n["obs"], "unknowns": None, "redundancy": None, "fixed": [],
                          "status": "UNCONSTRAINED", "removed": [], "vtpv": None, "s0": None, "chi2_lower": None, "chi2_upper": None,
                          "global_test": "UNCONSTRAINED"})
            continue
        r = n["redundancy"]
        lo = hi = None
        if r == 0:
            gt = "NO_REDUNDANCY"
        elif r > len(chi):
            gt = "OUT_OF_TABLE"
        else:
            lo, hi = _GQ(chi[r - 1][0]), _GQ(chi[r - 1][1])
            gt = "PASS" if lo <= n["vtpv"] <= hi else "FAIL"
        comps.append({"component": cid, "marks": n["marks"], "observations": n["obs"], "unknowns": n["unknowns"], "redundancy": r,
                      "fixed": n["fixed"], "status": n["status"], "removed": n["removed"], "vtpv": _GN(_Gs(n["vtpv"], 4)),
                      "s0": _GN(_Gs(_Gsqrt_q(n["vtpv"] / r, 3), 3)) if r else None, "chi2_lower": _GNs(lo, 3), "chi2_upper": _GNs(hi, 3),
                      "global_test": gt})
    out["network_summary.json"] = _Gjson_text({"campaign": cfg["campaign"], "components": comps}) + "\n"
    xs = [f'<loops campaign="{cfg["campaign"]}">']
    for lp in sorted(S["loops"], key=lambda z: z["id"]):
        if lp["status"] == "INCOMPLETE":
            xs.append(f'  <loop id="{lp["id"]}" class="{lp["class"]}" marks="{lp["n"]}" misclosure_mm="" length_km="" tolerance_mm="" status="INCOMPLETE"/>')
        else:
            xs.append(f'  <loop id="{lp["id"]}" class="{lp["class"]}" marks="{lp["n"]}" misclosure_mm="{_Gs(lp["w"], 2)}" length_km="{_Gs(lp["K"], 5)}" '
                      f'tolerance_mm="{_Gs(_Gsqrt_q(lp["tol"] * lp["tol"] * lp["K"], 2), 2)}" status="{lp["status"]}"/>')
    xs.append("</loops>")
    out["loop_closures.xml"] = "\n".join(xs) + "\n"
    rows = []
    for b in sorted(S["rates"]):
        o = S["rates"][b]
        rows.append([b, _Gs(o["h24"], 5) if o["h24"] is not None else "", _Gs(o["h26"], 5), _Gs(o["rate"], 2) if o["rate"] is not None else "",
                     _Gs(_Gsqrt_q(o["srate"], 2), 2) if o["srate"] is not None else "", o["class"]])
    out["subsidence_rates.csv"] = _Gtab(["mark", "height_2024_m", "height_2026_m", "rate_mm_per_yr", "sigma_rate_mm_per_yr", "class"], rows, ",")
    ex = sorted(S["excluded"], key=lambda e: (e["kind"], e["id"], e["reason"]))
    out["excluded_records.jsonl"] = "".join(_Gjson_text(e) + "\n" for e in ex)
    c = dict(S["counters"])
    c["files_read"] = len(W["catalog_order"])
    c["files_ignored"] = sorted([W["fname"][_GRETIRED["file"]], _GAUTOSAVE["file"]])
    out["dedup_report.json"] = _Gjson_text(c) + "\n"
    files = [dict(x) for x in S["lineage"]]
    for f in files:
        f["file"] = W["fname"][f["file"]]
    ign = [(W["fname"][_GRETIRED["file"]], "RETIRED"), (_GAUTOSAVE["file"], "UNCATALOGUED")]
    for name, st in sorted(ign):
        files.append({"file": name, "status": st, "records": 0, "kept": 0, "superseded": 0, "void_selected": 0, "duplicates": 0, "conflicts_lost": 0})
    out["source_lineage.json"] = _Gjson_text({"files": files}) + "\n"
    use = {}
    for rid, rs in S["setups"].items():
        for r in rs:
            for rod, cert in ((r["rb"], r["cb"]), (r["rf"], r["cf"])):
                use[(rod, cert)] = use.get((rod, cert), 0) + 1
    sheet = W["cert_sheets"][W["prof"]["cert_sheet"]]
    rows = []
    for (rod, cert), n in sorted(use.items()):
        cr = next(x for x in sheet if x["cert"] == cert)
        ty = W["rods"][rod]["type"]
        rows.append([rod, ty, W["memo"]["rod_types"][ty][0], cert, _Gs(cr["ppm"], 1), _Gs(_GQ(cr["t0"]), 1), cr["from"].isoformat(),
                     cr["to"].isoformat(), n])
    out["rod_certificates_used.tsv"] = _Gtab(["rod_serial", "rod_type", "graduation", "certificate", "scale_ppm", "t0_c", "valid_from", "valid_to",
                                              "readings"], rows, "\t")
    out["parameters_used.yaml"] = _G_params_yaml(W)
    pub = W["published"]
    rows = []
    for b in sorted(set(pub["heights"]) | set(S["heights"])):
        p = pub["heights"].get(b)
        h = S["heights"].get(b)
        hv = _Gq(h["h_mm"] / 1000, 5) if h else None
        if p is None:
            st = "MISSING_PUBLISHED"
        elif h is None:
            st = "MISSING_RECOMPUTED"
        else:
            st = "MATCH" if p == hv else "DIFFERENT"
        rows.append([b, _Gs(p, 5) if p is not None else "", _Gs(hv, 5) if hv is not None else "",
                     _Gs((hv - p) * 1000, 2) if (p is not None and hv is not None) else "", st])
    out["variance_vs_published.csv"] = _Gtab(["mark", "published_m", "recomputed_m", "diff_mm", "status"], rows, ",")
    rows = []
    for b in sorted(set(pub["rates"]) | set(S["rates"])):
        p = pub["rates"].get(b)
        o = S["rates"].get(b)
        pr = p["rate"] if p else None
        rr = _Gq(o["rate"], 2) if (o and o["rate"] is not None) else None
        pc = p["class"] if p else ""
        rc = o["class"] if o else ""
        if p is None:
            st = "MISSING_PUBLISHED"
        elif o is None:
            st = "MISSING_RECOMPUTED"
        elif pc != rc:
            st = "CLASS_DIFFERS"
        elif pr != rr:
            st = "RATE_DIFFERS"
        else:
            st = "MATCH"
        rows.append([b, _Gs(pr, 2) if pr is not None else "", _Gs(rr, 2) if rr is not None else "", pc, rc, st])
    out["rate_vs_published.psv"] = _Gtab(["mark", "published_rate", "recomputed_rate", "published_class", "recomputed_class", "status"], rows, "|")
    rows = []
    for sid in sorted(set(W["dashboard"]) | set(S["sections"])):
        ds = W["dashboard"].get(sid, "")
        rs = S["sections"][sid]["status"] if sid in S["sections"] else ""
        if sid in S["resid"] and S["resid"][sid]["status"] == "REMOVED":
            rs = "SNOOPED"
        if ds != rs:
            rows.append([sid, ds, rs])
    out["dashboard_disagreements.csv"] = _Gtab(["section_id", "dashboard_status", "recomputed_status"], rows, ",")
    lines = []
    c2 = W["memo"]["c2_true"]
    for r in sorted(W["cache"], key=lambda z: (z["mark"], z["epoch"], z["height"])):
        if r["epoch"] != "VDH-2025":
            continue
        m, _ = _G_resolve(W, r["mark"], W["ref_date"])
        if m is None or m not in c2:
            continue
        if _GQ(r["height"]) != _GQ(c2[m]):
            lines.append(((m, r["mark"]), _Gjson_text({"mark": m, "cache_token": r["mark"], "cache_m": _GN(r["height"]), "in_force_m": _GN(c2[m]),
                                                     "diff_mm": _GN(_Gs((_GQ(r["height"]) - _GQ(c2[m])) * 1000, 2))})))
    out["cache_divergence.jsonl"] = "".join(x[1] + "\n" for x in sorted(lines))
    out["reconciliation.md"] = _G_recon_md(W, S, out)
    return out


def _G_params_yaml(W) -> str:
    m = W["memo"]
    p = W["prof"]
    kv = [("campaign", W["cfg"]["campaign"]), ("reference_date", W["ref_date"].isoformat()), ("epoch_reference", W["prof_epoch"]),
          ("rod_certificate_sheet", p["cert_sheet"]), ("fallback_temp_c", _Gs(_GQ(p["fallback_temp"]), 1)),
          ("met_max_gap_min", str(p["met_max_gap"])), ("refraction_coefficient", m["k_ref"]), ("earth_radius_m", str(m["earth_radius"])),
          ("collimation_limit_mm_per_100m", m["c_limit"]), ("critical_w", m["k_crit"]), ("min_redundancy", str(m["r_min"])),
          ("max_removals", str(m["max_removals"])), ("alert_rate_mm_per_yr", m["alert"]), ("k_rate", m["k_rate"])]
    for cl in ("I", "II", "III"):
        kv.append((f"tolerance_section_{cl}_mm", m["tol"][cl][0]))
        kv.append((f"tolerance_loop_{cl}_mm", m["tol"][cl][1]))
        kv.append((f"sigma_{cl}_mm_per_sqrt_km", m["sigma"][cl]))
    for ty in sorted(m["rod_types"]):
        kv.append((f"graduation_{ty}", m["rod_types"][ty][0]))
        kv.append((f"alpha_{ty}_ppm_per_c", m["rod_types"][ty][1]))
    return "".join(f"{k}: {v}\n" for k, v in kv)


_GPACK_KEYS = [("control_table", "C-2"), ("certificate_sheet", None), ("refraction_coefficient", None), ("earth_radius_m", None),
               ("tolerance_class_II_section_mm", None), ("snooping_variance", "A_PRIORI"), ("met_max_gap_min", None),
               ("fallback_temp_c", None), ("pair_selection", "MIN_DISCREPANCY"), ("run_date_source", "FIRST_SETUP_INSTANT"),
               ("rod_scale_applied_to", "EACH_READING"), ("thermal_correction", "APPLIED")]


def _G_used_setting(W, key, fixed):
    if fixed:
        return fixed
    return {"certificate_sheet": W["prof"]["cert_sheet"], "refraction_coefficient": W["memo"]["k_ref"],
            "earth_radius_m": str(W["memo"]["earth_radius"]), "tolerance_class_II_section_mm": W["memo"]["tol"]["II"][0],
            "met_max_gap_min": str(W["prof"]["met_max_gap"]), "fallback_temp_c": _Gs(_GQ(W["prof"]["fallback_temp"]), 1)}[key]


def _G_recon_md(W, S, out) -> str:
    runs = S["runs"].values()
    secs = S["sections"].values()
    nets = S["nets"].values()
    cnt = [("runs_valid", sum(1 for r in runs if r["status"] == "VALID")), ("runs_rejected", sum(1 for r in runs if r["status"] != "VALID")),
           ("sections_accepted", sum(1 for s in secs if s["status"] == "ACCEPTED")),
           ("sections_not_accepted", sum(1 for s in secs if s["status"] != "ACCEPTED")),
           ("components", len(S["nets"])), ("components_unconstrained", sum(1 for n in nets if n["status"] == "UNCONSTRAINED")),
           ("sections_snooped", sum(len(n["removed"]) for n in nets)), ("marks_adjusted", len(S["heights"])),
           ("marks_alert", sum(1 for o in S["rates"].values() if o["class"] == "ALERT")),
           ("loops_failing", sum(1 for lp in S["loops"] if lp["status"] == "FAIL"))]
    lines = [f"# {W['cfg']['campaign']} recomputation summary", "", "## Counts", "", "| item | value |", "| --- | --- |"]
    lines += [f"| {k} | {v} |" for k, v in cnt]
    lines += ["", "## Run pack settings", "", "| setting | pack | used |", "| --- | --- | --- |"]
    for key, fixed in _GPACK_KEYS:
        lines.append(f"| {key} | {W['pack'][key]} | {_G_used_setting(W, key, fixed)} |")
    diffs = []
    pub = W["published"]["heights"]
    for b, h in S["heights"].items():
        if b in pub:
            d = _Gq(h["h_mm"] / 1000, 5) - pub[b]
            diffs.append((-abs(d), b, pub[b], _Gq(h["h_mm"] / 1000, 5), d))
    diffs.sort()
    lines += ["", "## Largest height differences", "", "| mark | published_m | recomputed_m | diff_mm |", "| --- | --- | --- | --- |"]
    for _, b, p, h, d in diffs[:10]:
        lines.append(f"| {b} | {_Gs(p, 5)} | {_Gs(h, 5)} | {_Gs(d * 1000, 2)} |")
    return "\n".join(lines) + "\n"


def _G_decoys(W, rng) -> None:
    """Published results, dashboard, cache and run pack, each made by a flawed reading of the same corpus."""
    P = _G_compute(W, _GPUBLISHED_FLIPS)
    heights = {b: _Gq(h["h_mm"] / 1000, 5) for b, h in P["heights"].items()}
    rates = {}
    for b, o in P["rates"].items():
        rates[b] = {"rate": _Gq(o["rate"], 2) if o["rate"] is not None else None, "class": o["class"]}
    for b in rng.sample(sorted(heights), 4):
        heights.pop(b)
    W["published"] = {"heights": heights, "rates": rates, "S": P}
    D = _G_compute(W, frozenset({"draft_certs", "withdrawn_rulings"}))
    dash = {}
    for sid, o in D["sections"].items():
        st = o["status"]
        if rng.random() < 0.04:
            st = "PENDING_REVIEW"
        dash[sid] = st
    W["dashboard"] = dash
    cache = []
    for b, v in W["memo"]["c1"].items():
        cache.append({"mark": b, "epoch": "VDH-2023", "height": v})
    for b, v in W["memo"]["c2_printed"].items():
        h = v
        if rng.random() < 0.12:
            h = _Gs(_GQ(v) + _GF(rng.choice([-1, 1]) * rng.randint(1, 4), 1000), 5)
        tok = b if rng.random() < 0.8 else b.lower()
        cache.append({"mark": tok, "epoch": "VDH-2025", "height": h})
    for b, v in sorted(W["memo"]["c2_true"].items()):
        cache.append({"mark": b, "epoch": "VDH-2021", "height": _Gs(_GQ(v) + _GF(rng.randint(5, 40), 1000), 5)})
        if rng.random() < 0.5:
            cache.append({"mark": b, "epoch": "VDH-2019", "height": _Gs(_GQ(v) + _GF(rng.randint(10, 70), 1000), 5)})
    rng.shuffle(cache)
    W["cache"] = cache
    W["pack"] = {"control_table": "C-1", "certificate_sheet": "Certs_2026_DRAFT", "refraction_coefficient": "0.14", "earth_radius_m": "6378137",
                 "tolerance_class_II_section_mm": W["memo"]["tol_printed"]["II"][0], "snooping_variance": "A_POSTERIORI",
                 "met_max_gap_min": str(W["prof_file"]["met_max_gap"]), "fallback_temp_c": "20.0", "pair_selection": "FIRST_PAIR",
                 "run_date_source": "BOOKED_DATE", "rod_scale_applied_to": "BACK_ROD_ONLY", "thermal_correction": "OMITTED"}


_GFILES = {"catalog": "ic_0vd6.json", "runs": "rg_4lm8.csv", "late": "rg_9am2.ndjson", "sections": "sx_7tq1.tsv", "lines": "ln_4pk2.json",
           "master": "ms_4tz9.csv", "alias": "ax_2fh8.sqlite", "tests": "tp_9cd3.db", "journal": "jr_5wn6.xml", "addendum": "ad_6rk0.xml",
           "epoch": "ep_3vb1.sqlite", "stations": "st_8mr4.psv", "observers": "ob_6hq2.ndjson", "loops": "lp_1xk7.yml",
           "rod_legacy": "rl_2ny5.yaml", "workbook": "vdo_rods_2026.xlsx", "memo": "gm_vdl26_memo.pdf", "profile": "campaign_profile.yml",
           "overlay": "profile_overlay.yaml", "clock": "site_clock.yaml", "handbook": "levelling_handbook.md", "layouts": "feed_layouts.md",
           "contract": "output_contract.md", "quickref": "quick_reference_card.txt", "bulletin": "field_bulletin_q3.txt",
           "pack": "adjustment_run_pack.md", "pub_heights": "adjusted_heights_published.csv", "pub_rates": "subsidence_published.json",
           "dashboard": "network_dashboard.csv", "cache": "control_heights_cache.jsonl"}


def _G_write(path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _G_rid(rid: str, style: str) -> str:
    n = rid.split("-")[2]
    if style == "compact":
        return "R26" + n
    if style == "slash":
        return "26/" + n
    return rid


def _G_rod_tok(W, rng, serial) -> str:
    r = W["rods"][serial]
    opts = [serial, serial, "R" + serial, "INV-" + serial, serial.zfill(6)]
    if r["former"]:
        opts += [r["former"], "R" + r["former"], r["former"]]
    return rng.choice(opts)


def _G_rec_reading(W, serial, v) -> _GF:
    return v * 2 if W["memo"]["rod_types"][W["rods"][serial]["type"]][0] == "HALF" else v


def _G_fmt_read(x, unit) -> str:
    if unit == "m":
        return _Gs(x, 5)
    if unit == "mm":
        return _Gs(x * 1000, 2)
    return str(int(x * 100000))


def _G_fmt_dist(x, unit) -> str:
    if unit == "m":
        return _Gs(x, 1)
    if unit == "dm":
        return str(int(x * 10))
    return _Gs(x * 3937 / 1200, 3)


def _G_fmt_temp(t, unit) -> str:
    if t is None:
        return ""
    if unit == "F":
        return _Gs(t * 9 / 5 + 32, 1)
    return _Gs(t, 1)


def _G_fmt_time(u, style, clock) -> str:
    if style == "z":
        return _Giso_z(u)
    if style == "epoch":
        return str(int(u.timestamp()))
    w = _Gutc_to_wall(u, clock)
    if style == "off":
        return w.strftime("%Y-%m-%dT%H:%M:%S") + _Goff_text(_Goffset_at(u, clock))
    if style == "local":
        return w.strftime("%Y-%m-%d %H:%M:%S")
    if style == "fw":
        return w.strftime("%Y%m%d %H%M%S")
    return w.strftime("%d.%m.%Y %H:%M:%S")


def _G_shard_rows(W, recs, lay, rng):
    out = []
    for _l, key, rev, void, c in recs:
        run = W["runs"][key[0]]
        d = {"run": _G_rid(key[0], lay["rid"]), "seq": key[1], "rev": rev, "void": void, "time": _G_fmt_time(c["at"], lay["time"], W["clock"]),
             "pair": run["pair"], "rb": _G_rod_tok(W, rng, c["rb"]), "rf": _G_rod_tok(W, rng, c["rf"]),
             "bs": _G_fmt_read(_G_rec_reading(W, c["rb"], c["back"]), lay["ru"]), "fs": _G_fmt_read(_G_rec_reading(W, c["rf"], c["fore"]), lay["ru"]),
             "db": _G_fmt_dist(c["db"], lay["du"]), "df": _G_fmt_dist(c["df"], lay["du"]), "temp": _G_fmt_temp(c["temp"], lay["temp"]),
             "dir": run["dir"] if rng.random() < 0.85 else ("B" if run["dir"] == "F" else "F")}
        out.append(d)
    rng.shuffle(out)
    return out


def _G_write_shard(W, path, lay, recs, rng):  # noqa: C901
    rows = _G_shard_rows(W, recs, lay, rng)
    fmt = lay["fmt"]
    camp = W["cfg"]["campaign"]
    if fmt == "csv":
        lines = [f"# field book export {lay['id']} campaign {camp}", "# readings and distances in metres; rod_temp_c may be empty",
                 "run,setup,rev,void,time_utc,rod_bs,rod_fs,bs_m,fs_m,dist_bs_m,dist_fs_m,rod_temp_c"]
        for d in rows:
            lines.append(",".join(str(x) for x in (d["run"], d["seq"], d["rev"], int(d["void"]), d["time"], d["rb"], d["rf"], d["bs"], d["fs"],
                                                   d["db"], d["df"], d["temp"])))
        _G_write(path, "\n".join(lines) + "\n")
    elif fmt == "tsv":
        lines = ["run\tset\tr\tstatus\ttime\tpair\tbs_mm\tfs_mm\tdbs_dm\tdfs_dm\tdir_note"]
        for i, d in enumerate(rows):
            lines.append("\t".join(str(x) for x in (d["run"], d["seq"], d["rev"], "VOID" if d["void"] else "OK", d["time"], d["pair"], d["bs"],
                                                    d["fs"], d["db"], d["df"], d["dir"])))
            if i % 97 == 50:
                lines.append("")
        _G_write(path, "\n".join(lines) + "\n")
    elif fmt == "psv":
        lines = ["RUN|SETUP|REV|VOIDED|LOCAL_TIME|BACK_ROD|FORE_ROD|BACK_READING_M|FORE_READING_M|BACK_DIST_M|FORE_DIST_M|TEMP_C"]
        for d in rows:
            lines.append("|".join(str(x) for x in (d["run"], d["seq"], d["rev"], "Y" if d["void"] else "", d["time"], d["rb"], d["rf"], d["bs"],
                                                   d["fs"], d["db"], d["df"], d["temp"])))
        _G_write(path, "\n".join(lines) + "\n")
    elif fmt == "fixed":
        lines = [f"VDO FIXED FIELD BOOK {lay['id']} {camp}", "RUN     SEQ RVVDATE     TIME  PAIRBS     FS     DBS DFS TEMP "]
        for d in rows:
            t = d["temp"]
            tt = "" if t == "" else ("+" if not t.startswith("-") else "-") + str(abs(int(_GQ(t) * 10))).zfill(4)
            dt, tm = d["time"].split(" ")
            lines.append(f"{d['run']:<8}{d['seq']:>4}{d['rev']:>2}{'V' if d['void'] else ' '}{dt}{tm}{d['pair']:<4}{d['bs']:>7}{d['fs']:>7}"
                         f"{d['db']:>4}{d['df']:>4}{tt:>5}")
        _G_write(path, "\n".join(lines) + "\n")
    elif fmt == "jsonl":
        lines = []
        for d in rows:
            lines.append(_Gjson.dumps({"run": {"id": d["run"]}, "setup": {"n": d["seq"], "rev": d["rev"], "void": d["void"]}, "time": d["time"],
                                       "bs": {"rod": d["rb"], "r": d["bs"], "d": d["db"]}, "fs": {"rod": d["rf"], "r": d["fs"], "d": d["df"]},
                                       "temp_c": d["temp"] or None}))
        _G_write(path, "\n".join(lines) + "\n")
    elif fmt == "ndjson":
        lines = []
        for d in rows:
            lines.append(_Gjson.dumps({"run_ref": d["run"], "seq": d["seq"], "rev": d["rev"], "deleted": d["void"], "epoch_s": int(d["time"]),
                                       "pair": d["pair"], "bs_mm": d["bs"], "fs_mm": d["fs"], "dbs_m": d["db"], "dfs_m": d["df"], "temp_f": d["temp"]}))
        _G_write(path, "\n".join(lines) + "\n")
    elif fmt == "json":
        items = [{"run": d["run"], "seq": d["seq"], "revision": d["rev"], "state": "void" if d["void"] else "ok", "utc": d["time"],
                  "back": {"rod": d["rb"], "reading_m": d["bs"], "distance_m": d["db"]}, "fore": {"rod": d["rf"], "reading_m": d["fs"], "distance_m": d["df"]}}
                 for d in rows]
        _G_write(path, _Gjson.dumps({"export": {"layout": lay["id"], "campaign": camp, "units": "metres"}, "setups": items}, indent=1) + "\n")
    elif fmt == "xmlattr":
        lines = [f'<fieldbook layout="{lay["id"]}" campaign="{camp}" units="mm,dm">']
        for d in rows:
            lines.append(f'  <setup run="{d["run"]}" seq="{d["seq"]}" rev="{d["rev"]}" void="{"true" if d["void"] else "false"}" local="{d["time"]}" '
                         f'brod="{d["rb"]}" frod="{d["rf"]}" bs_mm="{d["bs"]}" fs_mm="{d["fs"]}" dbs_dm="{d["db"]}" dfs_dm="{d["df"]}" temp_c="{d["temp"]}"/>')
        lines.append("</fieldbook>")
        _G_write(path, "\n".join(lines) + "\n")
    elif fmt == "yamlblk":
        lines = [f"# layout {lay['id']} campaign {camp}", "setups:"]
        flow = W["cfg"]["yaml_flow"]
        for d in rows:
            vals = [("run", d["run"]), ("set", d["seq"]), ("rev", d["rev"]), ("void", "yes" if d["void"] else "no"), ("time", f"'{d['time']}'"),
                    ("pair", d["pair"]), ("bs", d["bs"]), ("fs", d["fs"]), ("d_bs", d["db"]), ("d_fs", d["df"]), ("temp", d["temp"] or "~"),
                    ("dir", d["dir"])]
            if flow and rng.random() < 0.6:
                lines.append("  - {" + ", ".join(f"{k}: {v}" for k, v in vals) + "}")
            else:
                lines.append(f"  - {vals[0][0]}: {vals[0][1]}")
                lines += [f"    {k}: {v}" for k, v in vals[1:]]
        _G_write(path, "\n".join(lines) + "\n")
    elif fmt == "ymlrun":
        lines = [f"# layout {lay['id']}: setups grouped by run; columns seq, rev, void, epoch_s, back rod, fore rod, bs_mm, fs_mm, dbs_m, dfs_m",
                 "runs:"]
        by = {}
        for d in rows:
            by.setdefault(d["run"], []).append(d)
        for run in sorted(by, key=lambda z: rng.random()):
            lines.append(f"  {run}:")
            for d in by[run]:
                lines.append(f"    - [{d['seq']}, {d['rev']}, {'true' if d['void'] else 'false'}, {d['time']}, '{d['rb']}', '{d['rf']}', {d['bs']}, "
                             f"{d['fs']}, {d['db']}, {d['df']}]")
        _G_write(path, "\n".join(lines) + "\n")
    elif fmt == "md":
        lines = [f"# Field book transcript {lay['id']}", "", f"Campaign {camp}. Local site time. Rod temperature in degrees Fahrenheit.", "",
                 "| run | setup | rev | status | local time | back rod | fore rod | back m | fore m | back dist m | fore dist m | temp F |",
                 "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for d in rows:
            lines.append("| " + " | ".join(str(x) for x in (d["run"], d["seq"], d["rev"], "void" if d["void"] else "kept", d["time"], d["rb"], d["rf"],
                                                         d["bs"], d["fs"], d["db"], d["df"], d["temp"])) + " |")
        _G_write(path, "\n".join(lines) + "\n")
    elif fmt == "sqlite":
        con = _Gsqlite3.connect(str(path))
        con.execute("CREATE TABLE obs (run TEXT, seq INTEGER, rev INTEGER, void INTEGER, epoch INTEGER, pair TEXT, bs INTEGER, fs INTEGER, "
                    "dbs INTEGER, dfs INTEGER, temp_c TEXT)")
        con.execute("CREATE TABLE meta (k TEXT, v TEXT)")
        con.executemany("INSERT INTO meta VALUES (?, ?)", [("layout", lay["id"]), ("campaign", camp), ("bs_fs_unit", "1e-5 m"), ("dist_unit", "dm")])
        con.executemany("INSERT INTO obs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        [(d["run"], d["seq"], d["rev"], int(d["void"]), int(d["time"]), d["pair"], int(d["bs"]), int(d["fs"]), int(d["db"]),
                          int(d["df"]), d["temp"] or None) for d in rows])
        con.commit()
        con.close()
    elif fmt == "eav":
        con = _Gsqlite3.connect(str(path))
        con.execute("CREATE TABLE setup_key (uid INTEGER PRIMARY KEY, run TEXT, seq INTEGER, rev INTEGER)")
        con.execute("CREATE TABLE setup_attr (uid INTEGER, attr TEXT, value TEXT)")
        uid = 100
        for d in rows:
            uid += rng.randint(1, 3)
            con.execute("INSERT INTO setup_key VALUES (?,?,?,?)", (uid, d["run"], d["seq"], d["rev"]))
            attrs = [("time_utc", d["time"]), ("rod_b", d["rb"]), ("rod_f", d["rf"]), ("bs_m", d["bs"]), ("fs_m", d["fs"]), ("dist_b_m", d["db"]),
                     ("dist_f_m", d["df"]), ("void", "1" if d["void"] else "0")]
            if d["temp"]:
                attrs.append(("temp_c", d["temp"]))
            rng.shuffle(attrs)
            con.executemany("INSERT INTO setup_attr VALUES (?,?,?)", [(uid, a, v) for a, v in attrs])
        con.commit()
        con.close()
    elif fmt == "csvsemi":
        lines = ["run;opstelling;rev;vervallen;tijd;baak_a;baak_v;a_mm;v_mm;afst_a_m;afst_v_m;temp_c"]
        for d in rows:
            vals = [d["run"], d["seq"], d["rev"], "ja" if d["void"] else "nee", d["time"], d["rb"], d["rf"], d["bs"].replace(".", ","),
                    d["fs"].replace(".", ","), d["db"].replace(".", ","), d["df"].replace(".", ","), d["temp"].replace(".", ",")]
            lines.append(";".join(str(x) for x in vals))
        _G_write(path, "\n".join(lines) + "\n")
    elif fmt == "tsvft":
        lines = ["run\tseq\trev\tvoid\ttime\trod_b\trod_f\tbs_m\tfs_m\tdist_b_ft\tdist_f_ft\ttemp_f"]
        for d in rows:
            lines.append("\t".join(str(x) for x in (d["run"], d["seq"], d["rev"], int(d["void"]), d["time"], d["rb"], d["rf"], d["bs"], d["fs"],
                                                    d["db"], d["df"], d["temp"])))
        _G_write(path, "\n".join(lines) + "\n")
    elif fmt == "xmlelem":
        lines = [f'<setups layout="{lay["id"]}" campaign="{camp}">']
        for d in rows:
            lines.append(f"  <setup><run>{d['run']}</run><seq>{d['seq']}</seq><rev>{d['rev']}</rev><void>{int(d['void'])}</void><utc>{d['time']}</utc>"
                         f"<pair>{d['pair']}</pair><bs>{d['bs']}</bs><fs>{d['fs']}</fs><dbs_ft>{d['db']}</dbs_ft><dfs_ft>{d['df']}</dfs_ft></setup>")
        lines.append("</setups>")
        _G_write(path, "\n".join(lines) + "\n")


def _G_write_shards(W, data, rng) -> None:
    by = {}
    for r in W["records"]:
        by.setdefault(r[0]["file"], []).append(r)
    for lay in _GLAYOUTS:
        _G_write_shard(W, data / W["fname"][lay["file"]], lay, by.get(lay["file"], []), rng)
    _G_write_shard(W, data / W["fname"][_GRETIRED["file"]], _GRETIRED, W["stale"], rng)
    _G_write_shard(W, data / _GAUTOSAVE["file"], _GAUTOSAVE, W["autosave"], rng)


def _G_write_met(W, data, rng) -> None:
    for st, info in W["stations"].items():
        recs = W["met_raw"][st]
        if info["unit"] == "C":
            lines = ["epoch_s,temp_c,rh_pct,station"]
            for u, raw in recs:
                lines.append(f"{int(u.timestamp())},{_Gs(raw, 1)},{rng.randint(55, 97)},{st}")
        elif info["unit"] == "F":
            lines = ["utc\ttemp\twind_ms"]
            for u, raw in recs:
                lines.append(f"{_Giso_z(u)}\t{_Gs(raw, 1)}\t{rng.randint(0, 90) / 10}")
        else:
            lines = []
            for u, raw in recs:
                w = _Gutc_to_wall(u, W["clock"])
                lines.append(_Gjson.dumps({"t": w.strftime("%Y-%m-%dT%H:%M:%S") + _Goff_text(_Goffset_at(u, W["clock"])), "ta": int(raw * 10),
                                           "qc": "ok"}))
        _G_write(data / info["file"], "\n".join(lines) + "\n")


def _G_write_registers(W, data, rng) -> None:  # noqa: C901
    cfg = W["cfg"]
    camp = cfg["campaign"]
    F = _GFILES
    # catalog
    ent = []
    for i, f in enumerate(W["catalog_order"]):
        lay = next(x for x in _GLAYOUTS if x["file"] == f)
        ent.append({"campaign": camp, "file": W["fname"][f], "layout": lay["id"], "status": "ACTIVE",
                    "registered": (W["start"] + _Gtd(days=i)).isoformat()})
    ent.insert(rng.randint(0, 3), {"campaign": camp, "file": W["fname"][_GRETIRED["file"]], "layout": "L01", "status": "RETIRED",
                                   "registered": (W["start"] - _Gtd(days=2)).isoformat()})
    for y in (22, 23, 24, 25):
        for k in range(rng.randint(48, 60)):
            e = {"campaign": f"VDL-{y}", "file": f"fb_{rng.randint(0, 9)}{chr(97 + rng.randint(0, 25))}{chr(97 + rng.randint(0, 25))}{rng.randint(0, 9)}.csv",
                 "layout": f"L{rng.randint(1, 16):02d}", "status": rng.choice(["ACTIVE", "ACTIVE", "RETIRED"]),
                 "registered": _Gdate(2000 + y, rng.randint(1, 12), rng.randint(1, 28)).isoformat()}
            ent.insert(rng.randint(0, len(ent)), e)
    _G_write(data / F["catalog"], _Gjson.dumps({"catalog": "VDO field book ingest catalog", "revision": 41, "entries": ent}, indent=2) + "\n")
    # run register and amendments
    lines = ["run_id,campaign,start_bm,end_bm,booked,level,pair,observer,setups,status,note"]
    for r in W["run_rows"]:
        lines.append(",".join(str(x) for x in (r["run"], r["campaign"], r["start"], r["end"], r["booked"], r["level"], r["pair"], r["observer"],
                                               r["setups"], r["status"], r["note"])))
    _G_write(data / F["runs"], "\n".join(lines) + "\n")
    lines = [_Gjson.dumps({"amend_no": a["amend_no"], "campaign": a["campaign"], "run": a["run"], "field": a["field"], "value": a["value"],
                           "logged": (W["start"] + _Gtd(days=rng.randint(0, 60))).isoformat()}) for a in W["late"]]
    _G_write(data / F["late"], "\n".join(lines) + "\n")
    # sections
    lines = ["section_id\tfrom_mark\tto_mark\tline_id\tnominal_length_m\tblock\tstatus"]
    secs = [W["sections"][k] for k in sorted(W["sections"])]
    for s in secs:
        lines.append("\t".join((s["id"], s["from"], s["to"], s["line"], str(int(round(float(s["len"]) / 10) * 10)), s["block"], "ACTIVE")))
    for k in range(24):
        lines.append("\t".join((f"S-{rng.randint(1100, 1999):04d}", f"WS-{rng.randint(100, 999)}", f"WS-{rng.randint(100, 999)}", f"WL-{rng.randint(10, 99)}",
                                str(rng.randint(40, 180) * 10), "BLK-W", "ABANDONED")))
    _G_write(data / F["sections"], "\n".join(lines) + "\n")
    # lines
    lns = []
    for lid in sorted(W["lines"]):
        ln = W["lines"][lid]
        lns.append({"line": lid, "block": ln["block"], "class_history": [{"from": h["from"], "class": h["class"]} for h in ln["hist"]],
                    "met_note": "station per campaign profile"})
    for k in range(140):
        lns.append({"line": f"WL-{10 + k:03d}", "block": "BLK-W", "class_history": [{"from": f"{2008 + rng.randint(0, 10)}-0{rng.randint(1, 9)}-01",
                                                                               "class": rng.choice(["II", "III"])}], "met_note": "western sector"})
    rng.shuffle(lns)
    _G_write(data / F["lines"], _Gjson.dumps({"register": "levelling lines", "lines": lns}, indent=2) + "\n")
    # benchmark master
    lines = ["mark,block,description,established,status,easting,northing"]
    for b in sorted(W["master"]):
        v = W["bms"].get(b)
        blk = v["block"] if v else "OUTSIDE"
        est = (v.get("since") or _Gdate(1990 + rng.randint(0, 30), rng.randint(1, 12), 1)) if v else _Gdate(1980 + rng.randint(0, 30), 1, 1)
        lines.append(f"{b},{blk},{v['desc'] if v else 'regional mark'},{est.isoformat()},ACTIVE,{rng.randint(150000, 190000)},{rng.randint(520000, 580000)}")
    _G_write(data / F["master"], "\n".join(lines) + "\n")
    # alias register
    path = data / F["alias"]
    con = _Gsqlite3.connect(str(path))
    con.execute("CREATE TABLE bm_alias (token TEXT, canonical TEXT, valid_from TEXT, valid_to TEXT, note TEXT)")
    rows = list(W["alias_rows"])
    rng.shuffle(rows)
    con.executemany("INSERT INTO bm_alias VALUES (?,?,?,?,?)", [(r["token"], r["canonical"], r["from"].isoformat(), r["to"].isoformat() if r["to"] else None,
                                                                r["note"]) for r in rows])
    con.commit()
    con.close()
    # instrument tests
    con = _Gsqlite3.connect(str(data / F["tests"]))
    con.execute("CREATE TABLE instrument_alias (token TEXT, instrument TEXT)")
    con.execute("CREATE TABLE two_peg (test_id INTEGER, instrument TEXT, tested_utc TEXT, c_mm_per_100m TEXT, result TEXT, operator TEXT)")
    al = []
    for iid, v in W["instruments"].items():
        for t in v["tokens"]:
            al.append((" ".join(t.upper().split()), iid))
    rng.shuffle(al)
    con.executemany("INSERT INTO instrument_alias VALUES (?,?)", al)
    ts = list(W["tests"])
    rng.shuffle(ts)
    con.executemany("INSERT INTO two_peg VALUES (?,?,?,?,?,?)", [(t["id"], t["inst"], t["at"].strftime("%Y-%m-%d %H:%M:%S"), _Gs(t["c"], 3), t["result"],
                                                                 t["operator"]) for t in ts])
    con.commit()
    con.close()
    # journal
    lines = ['<journal register="mark disturbance">']
    for e in W["journal"]:
        lines.append(f'  <entry id="{e["entry"]}" mark="{e["mark"]}" event="{e["event"]}" date="{e["date"]}" refers="{e["refers"]}">{e["note"]}</entry>')
    lines.append("</journal>")
    _G_write(data / F["journal"], "\n".join(lines) + "\n")
    # rulings addendum
    lines = ['<addendum memo="GM-VDL" title="Rulings addendum">']
    for a in W["addendum"]:
        lines.append(f'  <ruling id="{a["id"]}" campaign="{a["campaign"]}" action="{a["action"]}" target="{a["target"]}" issued="{a["issued"]}">'
                     f'{a["note"]}</ruling>')
    lines.append("</addendum>")
    _G_write(data / F["addendum"], "\n".join(lines) + "\n")
    # epoch register
    con = _Gsqlite3.connect(str(data / F["epoch"]))
    con.execute("CREATE TABLE epochs (epoch_id TEXT, reference_date TEXT, status TEXT)")
    con.execute("CREATE TABLE heights (epoch_id TEXT, mark TEXT, height_m TEXT, sigma_mm TEXT, note TEXT)")
    con.executemany("INSERT INTO epochs VALUES (?,?,?)", [(e["epoch"], e["ref"], e["status"]) for e in W["epochs"]])
    con.executemany("INSERT INTO heights VALUES (?,?,?,?,?)", [(r["epoch"], r["mark"], _Gs(r["h"], 5), _Gs(r["sigma"], 1), "") for r in W["epoch_rows"]])
    con.commit()
    con.close()
    # stations
    lines = ["station_id|tokens|name|log_file|unit|status"]
    srows = []
    for st, info in W["stations"].items():
        toks = W["station_tokens"][st]
        srows.append(f"{st}|{';'.join(toks)}|{info['name']}|{info['file']}|{ {'C': 'degC', 'F': 'degF', 'dC': 'tenths degC'}[info['unit']]}|ACTIVE")
    for k in range(200):
        sid = f"WX-{rng.randint(100, 999)}"
        srows.append(f"{sid}|{sid.lower()};AWS {sid[3:]}|regional station {sid[3:]}|archive/{sid.lower()}.csv|degC|{rng.choice(['ACTIVE', 'CLOSED'])}")
    rng.shuffle(srows)
    _G_write(data / F["stations"], "\n".join(lines + srows) + "\n")
    # observers
    lines = []
    for code in sorted(W["observers"]):
        for r in W["observers"][code]:
            lines.append(_Gjson.dumps({"observer": code, "level": r["level"], "valid_from": r["from"].isoformat(), "valid_to": r["to"].isoformat(),
                                       "issued_by": "VDO training board"}))
    while len(lines) < 210:
        lines.append(_Gjson.dumps({"observer": f"X{rng.randint(10, 99)}", "level": "L3", "valid_from": "2019-01-01", "valid_to": "2021-01-01",
                                   "issued_by": "contractor"}))
    rng.shuffle(lines)
    _G_write(data / F["observers"], "\n".join(lines) + "\n")
    # loops
    lines = ["# loop register, campaign " + camp, "loops:"]
    for lp in W["loops"]:
        lines.append(f"  - id: {lp['id']}")
        lines.append(f"    class: {lp['class']}")
        if rng.random() < 0.5:
            lines.append("    marks: [" + ", ".join(lp["tokens"]) + "]")
        else:
            lines.append("    marks:")
            lines += [f"      - {t}" for t in lp["tokens"]]
    _G_write(data / F["loops"], "\n".join(lines) + "\n")
    # legacy rod register
    lines = ["# legacy rod register (types only; scale values here are historical)", "rods:"]
    for s in sorted(W["rods"]):
        r = W["rods"][s]
        lines.append(f"  - serial: '{s}'")
        lines.append(f"    type: {r['type']}")
        lines.append(f"    scale_ppm: {_Gs(_GF(rng.randint(-400, 400), 10), 1)}")
    _G_write(data / F["rod_legacy"], "\n".join(lines) + "\n")


def _G_write_profile(W, data, rng) -> None:
    cfg = W["cfg"]
    F = _GFILES
    pf = W["prof_file"]
    flow = cfg["yaml_flow"]
    lines = [f"# campaign profile, {cfg['agency']}", f"campaign_id: {cfg['campaign']}", f"reference_date: {W['ref_date'].isoformat()}",
             f"epoch_reference: {W['prof_epoch']}", f"rod_certificate_sheet: {pf['cert_sheet']}", f"fallback_temp_c: {pf['fallback_temp']}",
             f"met_max_gap_min: {pf['met_max_gap']}", "# overlay entries in profile_overlay.yaml are layered on top of these settings", "",
             "control_points:"]
    for t in W["profile_controls_tokens"]:
        lines.append(f"  - '{t}'" if rng.random() < 0.4 else f"  - {t}")
    lines += ["", "# rod pairs: first serial is rod A (backsight at odd setups), second is rod B", "rod_pairs:"]
    for p in sorted(W["pairs"]):
        a, b = W["pairs"][p]
        ta, tb = (W["rods"][a]["former"] or a) if rng.random() < 0.3 else a, (W["rods"][b]["former"] or b) if rng.random() < 0.3 else b
        if flow or rng.random() < 0.5:
            lines.append(f"  {p}: ['{ta}', '{tb}']")
        else:
            lines += [f"  {p}:", f"    - '{ta}'", f"    - '{tb}'"]
    lines += ["", "# met station of each levelling line from the given site date (station register tokens)", "line_stations:"]
    for lid in sorted(W["line_station"]):
        lines.append(f"  {lid}:")
        hist = list(W["line_station"][lid])
        rng.shuffle(hist)
        for d0, sid in hist:
            lines.append(f"    - from: {d0.isoformat()}")
            lines.append(f"      station: {rng.choice(W['station_tokens'][sid])}")
    lines += ["", "blocks:"]
    for blk in W["blocks"]:
        lines += [f"  {blk['id']}:", f"    name: {blk['name']}", "    note: polder block, double-run precise levelling"]
    _G_write(data / F["profile"], "\n".join(lines) + "\n")
    lines = ["# profile overlay: entries apply in file order", "overlay:"]
    for e in W["overlay"]:
        lines += [f"  - campaign: {e['campaign']}", f"    effective: {e['effective']}", f"    key: {e['key']}", f"    value: '{e['value']}'",
                  f"    note: {e['note']}"]
    _G_write(data / F["overlay"], "\n".join(lines) + "\n")
    rule = {"eu": "last Sunday of March 01:00 UTC to last Sunday of October 01:00 UTC",
            "us": "second Sunday of March 02:00 local to first Sunday of November 02:00 local"}[W["clock"]["rule"]]
    lines = ["# site clock for field book local times", f"zone: VDO-site", f"standard_offset: '{_Goff_text(W['clock']['base'])}'",
             f"summer_rule: {rule}", "transitions:"]
    for t, o in W["clock"]["trans"]:
        lines.append(f"  - {{utc: '{t.strftime('%Y-%m-%dT%H:%M:%SZ')}', offset: '{_Goff_text(o)}'}}")
    _G_write(data / F["clock"], "\n".join(lines) + "\n")


def _G_xesc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _G_col(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _G_xlsx(path, sheets, file_order, rng, date1904, runs=False, no_r=False):  # noqa: C901
    strings, index = [], {}

    def sidx(s):
        if s not in index:
            index[s] = len(strings)
            strings.append(s)
        return index[s]

    sheet_xml = []
    for _, rows, _h in sheets:
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
               '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for r, row in enumerate(rows, 1):
            cells = []
            last = -2
            for c, val in enumerate(row):
                if val is None or val == "":
                    continue
                ref = f"{_G_col(c)}{r}"
                omit = no_r and c == last + 1 and rng.random() < 0.5
                last = c
                at = "" if omit else f' r="{ref}"'
                if isinstance(val, int) and not isinstance(val, bool):
                    cells.append(f'<c{at}><v>{val}</v></c>')
                elif isinstance(val, _GN):
                    cells.append(f'<c{at}><v>{val}</v></c>')
                elif rng.random() < 0.2:
                    cells.append(f'<c{at} t="inlineStr"><is><t xml:space="preserve">{_G_xesc(str(val))}</t></is></c>')
                else:
                    cells.append(f'<c{at} t="s"><v>{sidx(str(val))}</v></c>')
            out.append(f'<row r="{r}">' + "".join(cells) + "</row>")
        out.append("</sheetData></worksheet>")
        sheet_xml.append("".join(out))
    n = len(sheets)
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
          '<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
          '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>',
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
    for k in range(n):
        ct.append(f'<Override PartName="/xl/worksheets/sheet{k + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    ct.append("</Types>")
    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
          + ('<workbookPr date1904="1"/>' if date1904 else '<workbookPr defaultThemeVersion="164011"/>') + "<sheets>"]
    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for k, (name, _, hidden) in enumerate(sheets):
        st = ' state="hidden"' if hidden else ""
        wb.append(f'<sheet name="{_G_xesc(name)}" sheetId="{k + 1}"{st} r:id="rId{k + 1}"/>')
        rels.append(f'<Relationship Id="rId{k + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
                    f'Target="worksheets/sheet{file_order[k]}.xml"/>')
    wb.append("</sheets></workbook>")
    rels.append(f'<Relationship Id="rId{n + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>')
    rels.append(f'<Relationship Id="rId{n + 2}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    rels.append("</Relationships>")
    sst = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(strings)}" uniqueCount="{len(strings)}">']
    for s in strings:
        if runs and len(s) > 3 and rng.random() < 0.35:
            k = rng.randint(1, len(s) - 1)
            sst.append(f'<si><r><t xml:space="preserve">{_G_xesc(s[:k])}</t></r><r><rPr><b/></rPr><t xml:space="preserve">{_G_xesc(s[k:])}</t></r></si>')
        else:
            sst.append(f'<si><t xml:space="preserve">{_G_xesc(s)}</t></si>')
    sst.append("</sst>")
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                 "</Relationships>")
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
              '<borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="1"><xf/></cellXfs></styleSheet>')
    with _Gzipfile.ZipFile(path, "w", _Gzipfile.ZIP_DEFLATED) as z:
        def put(name, payload):
            info = _Gzipfile.ZipInfo(name, date_time=(2026, 10, 30, 9, 0, 0))
            info.compress_type = _Gzipfile.ZIP_DEFLATED
            z.writestr(info, payload)
        put("[Content_Types].xml", "".join(ct))
        put("_rels/.rels", root_rels)
        put("xl/workbook.xml", "".join(wb))
        put("xl/_rels/workbook.xml.rels", "".join(rels))
        put("xl/sharedStrings.xml", "".join(sst))
        put("xl/styles.xml", styles)
        for k in range(n):
            put(f"xl/worksheets/sheet{file_order[k]}.xml", sheet_xml[k])


def _G_serial(d, date1904) -> int:
    return (d - (_Gdate(1904, 1, 1) if date1904 else _Gdate(1899, 12, 30))).days


def _G_cell_num(rng, text):
    u = rng.random()
    if u < 0.55:
        return _GN(text)
    if u < 0.8:
        return " " + text
    return text


def _G_cell_date(rng, d, d1904):
    return _G_serial(d, d1904) if rng.random() < 0.8 else d.isoformat()


def _G_write_workbook(W, data, rng) -> None:
    cfg = W["cfg"]
    d1904 = cfg["date1904"]
    sheets = [("Read_Me", [["VDO levelling rod calibration workbook"], ["Certificates in force are on the sheet the campaign profile names."],
                           ["Draft sheets are kept for laboratory review only and are never used for reductions."],
                           ["Dates are serial day numbers in the workbook date system or ISO text."]], False)]
    rows = [["Levelling rods"], [], ["serial", "former_serial", "type", "owner", "status"]]
    for s in sorted(W["rods"], key=lambda z: rng.random()):
        r = W["rods"][s]
        if r["legacy_only"]:
            continue
        rows.append([s if rng.random() < 0.7 else _GN(s), r["former"] or "", r["type"], rng.choice(["VDO", "VDO", "Polder board"]),
                     "IN SERVICE" if r["campaign"] else rng.choice(["IN SERVICE", "STORE", "RETIRED"])])
    sheets.append(("Rods", rows, False))

    def cert_sheet(title, certs):
        rows = [[title], ["scale in parts per million; t0 is the calibration temperature in degC"], [],
                ["rod_serial", "certificate", "scale_ppm", "t0_c", "valid_from", "valid_to", "lab"]]
        cs = list(certs)
        rng.shuffle(cs)
        for i, c in enumerate(cs):
            if i == len(cs) // 2:
                rows.append(["continued"])
            rows.append([c["serial"], c["cert"], _G_cell_num(rng, _Gs(c["ppm"], 1)), _G_cell_num(rng, c["t0"]), _G_cell_date(rng, c["from"], d1904),
                         _G_cell_date(rng, c["to"], d1904), rng.choice(["NMi-VSL", "PTB", "VDO lab"])])
        return rows

    names = sorted(W["cert_sheets"])
    for name in names:
        hidden = "DRAFT" in name
        title = {"Certs_2026_DRAFT": "DRAFT rod certificates, not for reductions", "Certs_2023": "Rod certificates, 2023 programme"}.get(
            name, f"Rod certificates, sheet {name}")
        sheets.append((name, cert_sheet(title, W["cert_sheets"][name]), hidden))
    order = list(range(1, len(sheets) + 1))
    rng.shuffle(order)
    _G_xlsx(data / _GFILES["workbook"], sheets, order, rng, d1904, cfg["xlsx_runs"], cfg["xlsx_no_r"])


def _G_pesc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _G_oct(s, rng, on):
    if not on:
        return _G_pesc(s)
    out = []
    for ch in s:
        if ch in "\\()" or (ch.isalnum() and rng.random() < 0.25):
            out.append("\\%03o" % ord(ch))
        else:
            out.append(ch)
    return "".join(out)


def _G_pdf(path, pages, rng, label, octal=False, td=False):
    objs = []
    n_pages = len(pages)
    page_ids = [4 + 2 * p for p in range(n_pages)]
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = " ".join(f"{i} 0 R" for i in page_ids)
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for p, rows in enumerate(pages):
        ops = []
        y = 806
        for cells in rows:
            shows = []
            for cell in cells:
                u = rng.random()
                if len(cell) > 3 and u < 0.22:
                    cut = rng.randint(1, len(cell) - 1)
                    show = f"[({_G_oct(cell[:cut], rng, octal)}) {-rng.randint(8, 30)} ({_G_oct(cell[cut:], rng, octal)})] TJ"
                elif u < 0.45:
                    show = "<" + cell.encode("latin-1").hex().upper() + "> Tj"
                else:
                    show = f"({_G_oct(cell, rng, octal)}) Tj"
                shows.append(show)
            if td and len(shows) > 1 and rng.random() < 0.6:
                ops.append(f"BT /F1 7 Tf 1 0 0 1 36 {y} Tm {shows[0]} " + " ".join(f"92 0 Td {sh}" for sh in shows[1:]) + " ET")
            else:
                for k, show in enumerate(shows):
                    ops.append(f"BT /F1 7 Tf 1 0 0 1 {36 + 92 * k} {y} Tm {show} ET")
            y -= 10
        ops.append(f"BT /F1 6 Tf 1 0 0 1 36 24 Tm ({label} page {p + 1} of {n_pages}) Tj ET")
        rng.shuffle(ops)
        raw = ("\n".join(ops) + "\n").encode("latin-1")
        plain = td and rng.random() < 0.4
        comp = raw if plain else _Gzlib.compress(raw, 9)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {page_ids[p] + 1} 0 R >>".encode())
        head = f"<< /Length {len(comp)} >>" if plain else f"<< /Length {len(comp)} /Filter /FlateDecode >>"
        objs.append(f"{head}\nstream\n".encode() + comp + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))


def _G_write_memo(W, data, rng) -> None:  # noqa: C901
    cfg = W["cfg"]
    m = W["memo"]
    blocks = []

    def table(tid, title, status, head, rows):
        blocks.append((f"Table {tid}: {title} [{status}]", head, rows))

    prose = [["Governance memo GM-VDL-26: reduction, adjustment and rate parameters for campaign " + cfg["campaign"]],
             ["Issued by the geodetic quality board. Tables marked IN FORCE govern the recomputation."],
             ["Tables marked WITHDRAWN or SUPERSEDED are kept for audit history only."],
             ["The errata at the end of this memo amend the tables they cite and take precedence over the printed values."]]
    old = {"I": ["4.0", "5.0"], "II": ["6.0", "7.0"], "III": ["8.0", "10.0"]}
    table("T-0", "Double-run tolerances, 2019 issue", "SUPERSEDED", ["class", "section mm per sqrt km", "loop mm per sqrt km"],
          [[k, v[0], v[1]] for k, v in sorted(old.items())])
    table("T-1", "Double-run and loop tolerances", "IN FORCE", ["class", "section mm per sqrt km", "loop mm per sqrt km"],
          [[k, v[0], v[1]] for k, v in sorted(m["tol_printed"].items())])
    table("K-1", "Observation precision and data snooping", "IN FORCE", ["parameter", "value"],
          [[f"sigma class {k} mm per sqrt km", v] for k, v in sorted(m["sigma"].items())]
          + [["critical value of w", m["k_crit"]], ["minimum redundancy after a removal", str(m["r_min"])],
             ["maximum removals per component", str(m["max_removals"])]])
    table("I-1", "Instrument acceptance and refraction", "IN FORCE", ["parameter", "value"],
          [["collimation limit mm per 100 m", m["c_limit"]], ["refraction coefficient", m["k_ref"]]])
    table("A-1", "Rod types", "IN FORCE", ["rod type", "graduation", "alpha ppm per degC"],
          [[k, v[0], v[1]] for k, v in sorted(m["rod_types"].items())])
    table("R-1", "Rate classification", "IN FORCE", ["parameter", "value"],
          [["alert rate mm per yr", m["alert"]], ["significance factor", m["k_rate"]]])
    c1 = sorted(m["c1"].items())
    table("C-1", "Control heights, adjustment VDH-2023", "WITHDRAWN", ["mark", "height m"], [[k, v] for k, v in c1])
    c2 = sorted(m["c2_printed"].items(), key=lambda kv: rng.random())
    c2.sort(key=lambda kv: kv[0])
    table("C-2", "Control heights, adjustment VDH-2025", "IN FORCE", ["mark", "height m"], [[k, v] for k, v in c2])
    table("X-2", "Chi-square bounds for the global test", "IN FORCE", ["degrees of freedom", "lower 2.5 percent", "upper 97.5 percent"],
          [[str(i + 1), lo, hi] for i, (lo, hi) in enumerate(W["chi2"])])
    table("J-0", "Run and section rulings, first issue", "WITHDRAWN", ["ruling", "target", "action", "effective"],
          [[j["id"], j["target"], j["action"], j["effective"]] for j in W["j0"]])
    table("J-1", "Run and section rulings", "IN FORCE", ["ruling", "target", "action", "effective", "note"],
          [[j["id"], j["target"], j["action"], j["effective"], j["note"]] for j in W["j1"]])
    pages, cur = [], list(prose) + [[]]
    per = 72
    for title, head, rows in blocks:
        if len(cur) > per - 5:
            pages.append(cur)
            cur = []
        cur.append([title])
        cur.append(head)
        for r in rows:
            if len(cur) >= per:
                pages.append(cur)
                cur = [[title.replace(": ", " (continued): ", 1)], head]
            cur.append(r)
        cur.append([])
    cur.append(["Errata"])
    cur.append(["Erratum E-1: Table K-1 heading, for per km read per square root km"])
    for e in m["errata"]:
        cur.append([f"Erratum {e['id']}: {e['text']}"])
    pages.append(cur)
    _G_pdf(data / _GFILES["memo"], pages, rng, "GM-VDL-26", cfg["pdf_octal"], cfg["pdf_td"])


def _G_write_texts(W, data, rng) -> None:  # noqa: C901
    cfg = W["cfg"]
    F = _GFILES
    camp = cfg["campaign"]
    # quick reference card
    q = ["VDO QUICK REFERENCE CARD, levelling office edition 12", "", "PHYSICAL CONSTANTS",
         f"  mean earth radius R ............................ {W['memo']['earth_radius']} m",
         "  refraction coefficient k (typical day) ......... 0.14",
         "  semi-major axis GRS80 ........................... 6378137 m (not used for curvature)",
         "  normal gravity at 52 deg ........................ 9.8125 m/s2", "",
         "UNITS", "  US survey foot ................................. 1200/3937 m", "  international foot ............................. 0.3048 m",
         "  degrees Fahrenheit to Celsius .................. C = (F - 32) x 5/9", "", "FEET TO METRES (international foot, office drawings only)"]
    for ft in range(5, 605, 5):
        q.append(f"  {ft:>4} ft = {_Gs(_GF(ft) * _GF(3048, 10000), 4)} m")
    q += ["", "CHI-SQUARE ONE-SIDED 95 PERCENT POINTS (training sheet)"]
    for i, v in enumerate(_GCHI2_ONE):
        q.append(f"  dof {i + 1:>2}: {v}")
    q += ["", "TOLERANCES (2019 card)", "  class I section 4.0 mm per sqrt km", "  class II section 6.0 mm per sqrt km", "  class III section 8.0 mm per sqrt km"]
    _G_write(data / F["quickref"], "\n".join(q) + "\n")
    # field bulletin
    o, pr = W["outage"], W["proposed"]
    nb = [f"VDO FIELD BULLETIN, third quarter, campaign {camp}", ""]
    notices = []
    st = W["stations"]
    notices.append(["OPERATIONAL NOTICE ON-26-07", "status: IN FORCE", f"campaign: {camp}",
                    f"met station {o['station']} ({st[o['station']]['name']}) offline from {o['from'].isoformat()} to {o['to'].isoformat()} inclusive (site dates)",
                    f"substitute station: {o['sub']}"])
    notices.append(["PROPOSED NOTICE PN-26-02", "status: PROPOSED", f"campaign: {camp}",
                    f"met station {pr['station']} ({st[pr['station']]['name']}) maintenance planned from {pr['from'].isoformat()} to {pr['to'].isoformat()}",
                    f"substitute station: {pr['sub']}"])
    notices.append(["OPERATIONAL NOTICE ON-25-11", "status: IN FORCE", "campaign: VDL-25",
                    f"met station WX-S ({st['WX-S']['name']}) offline from {(W['start'] - _Gtd(days=360)).isoformat()} to {(W['start'] - _Gtd(days=355)).isoformat()}",
                    "substitute station: WX-C"])
    notices.append(["OPERATIONAL NOTICE ON-26-09", "status: CANCELLED", f"campaign: {camp}",
                    f"met station WX-N ({st['WX-N']['name']}) offline from {(W['start'] + _Gtd(days=20)).isoformat()} to {(W['start'] + _Gtd(days=22)).isoformat()}",
                    "substitute station: WX-S"])
    topics = ["rod transport cases replaced", "office closed for the regional holiday", "instrument batteries recalled", "new tripod shoes issued",
              "field vehicle schedule changed", "safety briefing for dike crest work", "data upload window moved to 18:00", "thermometers recalibrated",
              "night work not permitted near locks", "polder access permits renewed"]
    for k in range(38):
        notices.append([f"INFORMATION NOTE IN-26-{k + 10:02d}", "status: INFORMATION", f"campaign: {camp}", rng.choice(topics),
                        f"date: {(W['start'] + _Gtd(days=rng.randint(-20, 60))).isoformat()}"])
    rng.shuffle(notices)
    for n in notices:
        nb += n + [""]
    _G_write(data / F["bulletin"], "\n".join(nb) + "\n")
    # run pack
    P = W["published"]["S"]
    pk = W["pack"]
    lines = ["# Adjustment run pack AP-26-03", "", f"Saved run pack used to produce the published {camp} adjusted heights and rates.", "",
             "## Settings", "", "```"]
    lines += [f"{k}: {v}" for k, v in pk.items()]
    lines += ["```", "", "## Steps", "", "1. load every shard in the folder, newest file first",
              "2. rod scale from the back rod applied to the setup height difference",
              "3. tolerance test on the first forward and first backward run of each section",
              "4. control heights from Table C-1, all profile control points fixed",
              "5. data snooping with the a posteriori variance factor", "6. heights rounded at the end", "",
              "## Section dump", "", "| section | status | value_m |", "|---|---|---|"]
    for sid in sorted(P["sections"]):
        s = P["sections"][sid]
        lines.append(f"| {sid} | {s['status']} | {_Gs(s['value'], 5) if s['value'] is not None else ''} |")
    _G_write(data / F["pack"], "\n".join(lines) + "\n")
    # published heights and rates
    pub = W["published"]
    lines = ["# published adjusted heights, run pack AP-26-03", "mark,height_m,status"]
    for b in sorted(pub["heights"]):
        lines.append(f"{b},{_Gs(pub['heights'][b], 5)},{P['heights'][b]['status']}")
    _G_write(data / F["pub_heights"], "\n".join(lines) + "\n")
    items = []
    for b in sorted(pub["rates"]):
        r = pub["rates"][b]
        items.append({"mark": b, "rate_mm_per_yr": _Gs(r["rate"], 2) if r["rate"] is not None else None, "class": r["class"]})
    _G_write(data / F["pub_rates"], _Gjson.dumps({"campaign": camp, "source": "run pack AP-26-03", "rates": items}, indent=1) + "\n")
    lines = ["section_id,status,updated"]
    for sid in sorted(W["dashboard"]):
        lines.append(f"{sid},{W['dashboard'][sid]},{(W['ref_date'] - _Gtd(days=rng.randint(1, 9))).isoformat()}")
    _G_write(data / F["dashboard"], "\n".join(lines) + "\n")
    lines = [_Gjson.dumps({"mark": r["mark"], "epoch": r["epoch"], "height_m": r["height"]}) for r in W["cache"]]
    _G_write(data / F["cache"], "\n".join(lines) + "\n")


_GHANDBOOK = """# VDO precise levelling recomputation handbook (revision 7)

This handbook governs the recomputation of a double-run precise levelling campaign of the Vellmar Delta
Geodetic Office: field book shards are settled into setups, setups are reduced to run height differences,
runs are paired into section values, the section values of every connected network component are adjusted
by exact weighted least squares with iterative data snooping, and the adjusted heights are compared with
an earlier epoch to classify subsidence rates. Rules are numbered H1 to H22. Where a rule names a table,
the table is in the governance memo (the PDF file); where it names a sheet, the sheet is in the rod
workbook (the XLSX file).

## H1 Authority

Order of authority, highest first:

1. this handbook;
2. memo tables whose title ends in [IN FORCE], as amended by the errata at the end of the memo;
3. the campaign profile `campaign_profile.yml` with the overlay `profile_overlay.yaml` layered on it (H4);
4. the registers listed in H2 and the workbook sheets the profile names;
5. the quick reference card, for the mean earth radius only;
6. OPERATIONAL NOTICE entries of the field bulletin whose status is IN FORCE, for met station
   substitutions only (H11).

Not authoritative for any figure: the saved adjustment run pack, the published heights and rates, the
network dashboard, the control height cache, memo tables marked [WITHDRAWN] or [SUPERSEDED], workbook sheets
other than the one the profile names, the scale values of the legacy rod register, PROPOSED or CANCELLED
bulletin notices, the refraction coefficient and tables printed on the quick reference card, shards that the
catalog does not list as ACTIVE for the campaign, and the `dir` notes written in some shards.

## H2 Registers

Registers are recognised by their content, not by their file names:

- ingest catalog: JSON whose top-level key `catalog` names it, with an `entries` list;
- run register: CSV with header `run_id,campaign,start_bm,end_bm,booked,level,pair,observer,setups,status,note`;
- run amendments: NDJSON objects carrying `amend_no`, `campaign`, `run`, `field` and `value`;
- section register: TSV with header starting `section_id	from_mark	to_mark	line_id`;
- line register: JSON with `"register": "levelling lines"` and a `lines` list with `class_history`;
- benchmark master: CSV with header `mark,block,description,established,status,easting,northing`;
- benchmark alias register: SQLite table `bm_alias`;
- instrument test register: SQLite tables `instrument_alias` and `two_peg`;
- disturbance journal: XML whose root element is `journal`;
- rulings addendum: XML whose root element is `addendum`;
- epoch register: SQLite tables `epochs` and `heights`;
- met station register: PSV with header `station_id|tokens|name|log_file|unit|status`;
- observer roster: NDJSON objects carrying `observer`, `level`, `valid_from`, `valid_to`;
- loop register: YAML with a top-level `loops` list;
- legacy rod register: YAML with a top-level `rods` list of `serial` and `type`.

## H3 Catalog and shards

Only catalog entries whose `campaign` equals the profile `campaign_id` and whose `status` is `ACTIVE` are
read. Each entry gives the file name and its layout id; `feed_layouts.md` defines every layout. The order
of those entries in the `entries` list is the catalog precedence order (first is highest). A file that is
not such an entry is not read, whatever it contains.

## H4 Profile layering

The profile gives `campaign_id`, `reference_date`, `epoch_reference`, `rod_certificate_sheet`,
`fallback_temp_c`, `met_max_gap_min`, the control point list, the rod pairs and the met station of every
line. An overlay entry applies when its `campaign` equals `campaign_id` exactly and its `effective` date is
on or before `reference_date`; applying entries in file order, each sets its `key` to its `value`, so a
later applying entry wins over an earlier one and every applying entry wins over the profile.

## H5 Setup settlement

A setup is identified by (run id, setup number). Among all records of a setup in the read shards, the
records with the highest revision number compete. When every competing record has the same decoded content
(instant, back and fore reading in metres, back and fore distance, rod temperature or its absence, back and
fore rod serial) and the same void state, the first in catalog precedence is kept and each other one is a
duplicate. Otherwise the record from the shard earliest in catalog precedence wins and each competing
record that differs from it in content or void state is a lost conflict, while one that matches it is a
duplicate. A winning record that is void drops the setup; a void record at a lower revision has no effect.
Every record at a lower revision than the highest is superseded.

## H6 Decoding

Run ids are written `R-26-dddd`, `R26dddd` or `26/dddd` and all denote `R-26-dddd`. Readings are in the
unit the layout states. A reading taken on a rod whose type has HALF graduation (Table A-1) is recorded in
half-centimetre units: its value in metres is the decoded value divided by 2. Distances given in US survey
feet are converted with 1 ft = 1200/3937 m and rounded half to even to 0.1 m; other distances are exact in
the unit stated. A rod temperature in degrees Fahrenheit is converted with C = (F - 32) x 5/9 and rounded
half to even to 0.1 degC. An empty temperature field, `~`, `null` or a missing attribute means the setup has
no field temperature. Times are UTC, UTC with an offset, epoch seconds or local wall clock as the layout
states; a local wall clock time is converted with the transitions of `site_clock.yaml`.

## H7 Rods and certificates

The serial of a rod token is the run of digits in the token with leading zeros removed. When that serial
appears in the `former_serial` column of the workbook `Rods` sheet it is replaced by the `serial` of that
row. The rod type is the `type` of the serial in the `Rods` sheet; a serial absent from that sheet takes its
type from the legacy rod register. A layout that names a rod pair instead of rods takes the pair from the
run register after amendments; the profile `rod_pairs` entry lists rod A then rod B (as rod tokens); at odd
setup numbers rod A is the back rod and rod B the fore rod, at even setup numbers the other way round.

The certificate of a rod on a run date d is taken from the workbook sheet named by the effective
`rod_certificate_sheet`: among the rows of that rod with valid_from <= d <= valid_to, the one with the
greatest valid_from. A row whose only cell reads `continued` is not data.

## H8 Run register

Only rows whose `campaign` equals `campaign_id` are runs of the campaign. Amendments of the campaign are
applied to existing runs in ascending `amend_no`, whatever their order in the file; each sets the named
field (`status`, `setups`, `level` or `observer`) and a later amendment of the same field wins. The run
date is the site-local calendar date of the earliest instant among the run's kept setups. The `booked`
column is the office booking date and is not the run date.

## H9 Run validity

Each run receives the first status of this list that applies:

1. `VOID`: the status after amendments is VOID;
2. `NO_SETUPS`: no kept setup;
3. `UNRESOLVED_BM`: the start or end token does not resolve at the run date (H13);
4. `UNKNOWN_SECTION`: the resolved (start, end) pair is neither the (from, to) nor the (to, from) pair of a
   section; a run from the from-mark to the to-mark is forward (F), the other way round backward (B);
5. `SEQUENCE_GAP`: the kept setup numbers are not exactly 1 to `setups`;
6. `UNCERTIFIED_OBSERVER`: no roster record of the observer (codes compare case-insensitively) has
   valid_from <= run date <= valid_to;
7. `NO_TEST`: the instrument has no effective two-peg test (H10);
8. `INVALID_COLLIMATION`: the absolute collimation error of the effective test exceeds the Table I-1 limit;
   the `result` column of the test register is not used for this decision;
9. `NO_CERTIFICATE`: a back or fore rod of any kept setup has no certificate on the run date;
10. `RULED_OUT`: a ruling in force rejects the run (H15);
11. `VALID` otherwise.

## H10 Two-peg tests

An instrument token is upper-cased with runs of whitespace collapsed to one space and looked up in
`instrument_alias`. `tested_utc` is a UTC time written YYYY-MM-DD HH:MM:SS. The effective test of a run is the `two_peg` row of that instrument with the greatest
`tested_utc` that is not later than the instant of the run's earliest kept setup, ignoring rows whose result
is RETEST; equal instants go to the greater `test_id`. The collimation error c is in mm per 100 m of sight
length and is positive when the line of sight points upward, so every reading is too high by c x D / 100 mm.

## H11 Rod temperature

A setup with a field temperature uses it (source FIELD). Otherwise the met station of the run's section line is
used: profile `line_stations` lists for each line its stations, each with the site date `from` which it
applies, and the setup takes the entry with the latest `from` on or before the site-local date of its instant;
the station token resolves through the station register by `station_id` or any of its `tokens`,
case-insensitively. That station is replaced when an IN FORCE OPERATIONAL NOTICE of this campaign takes that station
offline on the site-local date of the setup instant: the notice's substitute station is then used instead.
The station's log file and unit come from the station register. Every log record is converted to degC
exactly (degF with C = (F - 32) x 5/9, tenths of degC divided by 10). The temperature at the setup instant
is the linear interpolation in time between the last record at or before the instant and the first record
at or after it (a record at the instant itself is used as it is), rounded half to even to 0.1 degC (source
MET). When either record is missing, or the two are more than `met_max_gap_min` minutes apart, the setup
uses `fallback_temp_c` (source FALLBACK).

## H12 Setup reduction

Each reading r (metres) with sight distance D (metres), taken on a rod with certificate scale s (ppm) and
calibration temperature T0, rod type expansion alpha (ppm per degC, Table A-1), rod temperature T (H11), the
run's collimation error c (H10), the refraction coefficient k (Table I-1) and the mean earth radius R (quick
reference card) is reduced to

    r_c = r x (1 + s x 1e-6 + alpha x 1e-6 x (T - T0)) - c x D / 100000 - (1 - k) x D x D / (2 x R)

The scale and the expansion of each reading use that reading's own rod. The setup height difference is the
reduced back reading minus the reduced fore reading, rounded half to even to 0.00001 m; the raw difference is
the decoded back reading minus the decoded fore reading. The run height difference is the sum of its setup
height differences and the run length is the sum of all back and fore distances.

Worked example with c = 1.250, k = 0.13, R = 6371000, T = 24.3 and alpha = 0.80 for both rods: a back reading
1.52340 m at D = 32.4 m on a rod with s = -12.5, T0 = 20.0 reduces to 1.522909522... m; a fore reading 0.87655 m at
D = 29.8 m on a rod with s = 8.1, T0 = 20.0 reduces to 0.876126982... m; the setup height difference is
0.646782541... m, reported 0.64678 m, while the raw difference is 0.64685 m.

## H13 Benchmark tokens

A token is trimmed, upper-cased and stripped of spaces. `VD` followed by up to four digits, with or without
a hyphen, becomes `VD-` and the digits zero-padded to four; up to four bare digits become `VD-` and the
digits zero-padded to four; `MB` followed by up to three digits becomes `MB-` and the digits zero-padded to
three. The result then follows the alias register at the resolution date d: a row applies when its `token`
equals the current value, valid_from <= d and valid_to is empty or later than d (valid_to is exclusive);
when several rows apply, the one with the greatest valid_from wins; the current value becomes the row's
`canonical` and the lookup repeats until no row applies. The token resolves when the final value is a mark
of the benchmark master. Run tokens resolve at the run date, profile control points and loop marks at the
reference date, epoch register marks at the reference date of their epoch.

## H14 Sections

A section's class is the class of its line: the `class_history` entry of the line with the latest `from`
that is not after the reference date. For a section with at least one VALID forward and one VALID backward
run, every (forward, backward) pair is a candidate with discrepancy d = dh_forward + dh_backward (m) and
length K = (forward length + backward length) / 2000 (km). A candidate is accepted when
(1000 x d)^2 <= t^2 x K, where t is the Table T-1 section tolerance of the class. The section takes the
accepted candidate with the smallest |d|; ties go to the candidate whose later run date is latest, then to
the smaller forward run id, then to the smaller backward run id. Its value is (dh_forward - dh_backward) / 2
rounded half to even to 0.00001 m, from the from-mark to the to-mark. Status, first that applies:
`RULED_OUT` (a ruling in force rejects the section), `INCOMPLETE` (a direction has no VALID run),
`REJECTED_TOLERANCE` (no accepted candidate), `ACCEPTED`.

## H15 Rulings

Table J-1 rulings whose effective date is on or before the reference date are in force unless an addendum
ruling of this campaign with action CANCEL, issued on or before the reference date, targets their ruling id.
Addendum rulings of this campaign with action REJECT_RUN or REJECT_SECTION issued on or before the
reference date are in force. A ruling in force rejects its target run or section outright.

## H16 Control

Disturbance journal entries are replayed in ascending entry id. An ERRATUM entry cancels the entry whose id
its `refers` attribute names, whatever the erratum's own date, and does nothing else. For control status,
entries dated after the reference date are ignored; DISTURBED makes a mark disturbed, REVERIFIED makes it
sound again and INSPECTED changes nothing. Each profile control point, resolved at the reference date,
receives the first status that applies: `UNRESOLVED`, `NOT_IN_TABLE` (no Table C-2 height), 
`DEMOTED_DISTURBED` (disturbed at the reference date), `FIXED`. A FIXED mark is held at its Table C-2
height as amended by the errata; every other mark is an unknown.

## H17 Adjustment

Accepted sections form a graph on their marks; each connected component is adjusted on its own and is named
by its lowest mark id. A component without a FIXED mark is UNCONSTRAINED and is not adjusted. Heights and
section values are taken in millimetres; each section is an observation H_to - H_from with weight
p = 1 / (sigma^2 x K), sigma being the Table K-1 sigma of the section class, so the a priori unit variance is
1. The least squares solution is computed exactly in rational arithmetic. The residual of an observation is
v = adjusted H_to - adjusted H_from - section value (mm). Its cofactor is qvv = 1/p - a Qxx a', where a is
its design row and Qxx the inverse normal matrix. Observations with qvv = 0 are untestable; every other
observation has w = v / sqrt(qvv) and is tested against the Table K-1 critical value c_w by comparing the
squares: w^2 > c_w^2. The a priori unit variance is used; s0 never enters the test.

Data snooping repeats the adjustment: after each adjustment, if no tested observation has w^2 > c_w^2 the
loop stops (STOP_CLEAN); else if the component has already lost the Table K-1 maximum number of removals it
stops (STOP_BUDGET); else if removing one observation would leave the redundancy below the Table K-1
minimum it stops (STOP_REDUNDANCY); else the tested observation with the largest w^2 (ties: smaller section
id) is removed and the component is adjusted again (REMOVE). The final adjustment is the last one made.
Component status: CLEAN (stopped clean without a removal), SNOOPED (stopped clean after removals),
STOP_BUDGET, STOP_REDUNDANCY, UNCONSTRAINED.

## H18 Statistics

For the final adjustment of a component: vtpv = sum of p x v^2, redundancy r = observations - unknowns,
s0 = sqrt(vtpv / r) when r > 0. The global test passes when lower <= vtpv <= upper with the Table X-2 bounds
for r degrees of freedom; r = 0 gives NO_REDUNDANCY. The standard deviation of an adjusted height is
sqrt(qxx) mm with the a priori unit variance; FIXED marks have 0.

## H19 Loops

Each loop of the loop register lists its marks in traversal order and closes from the last mark back to the
first; marks resolve at the reference date. Every consecutive pair must be joined by an ACCEPTED section
(H14, whether or not snooping later removed it and whether or not its component is constrained), else the
loop is INCOMPLETE. The misclosure is the sum of the section values along the traversal (a section traversed
from its to-mark to its from-mark counts negative) in mm, K is the sum of the section lengths K, and the loop
passes when misclosure^2 <= t^2 x K with t the Table T-1 loop tolerance of the loop class.

## H20 Rates

The prior epoch is the epoch register epoch named by `epoch_reference`; its heights rows are the marks of
that epoch. The interval in years is the number of days from that epoch's reference date to the profile
reference date divided by 365.25. For every mark with an adjusted height (FIXED or ADJUSTED), using the
reported height and the reported standard deviation of this campaign (H22) and the prior height and sigma:
rate = (height - prior height) x 1000 / years (mm per year), sigma_rate = sqrt(sigma^2 + prior sigma^2) /
years. A rate is significant when rate^2 > k^2 x sigma_rate^2 with k the Table R-1 significance factor.
Class, first that applies: CONTROL (FIXED mark), DISTURBED (a journal DISTURBED entry that is not cancelled,
dated after the prior epoch's reference date and on or before the profile reference date; a later
REVERIFIED does not clear it), NEW (no prior height), ALERT (significant and rate <= the Table R-1 alert
rate), SUBSIDING (significant and negative), UPLIFT (significant and positive), STABLE.

## H21 Comparisons

The comparison reports set the recomputed figures against the published heights, the published rates, the
network dashboard and the control height cache. Their shapes are fixed by the output contract.

## H22 Rounding and reporting

Every rounding is half to even. Values are rounded only at these stages: decoded feet distances (0.1 m),
rod temperatures (0.1 degC), setup height differences (0.00001 m) and section values (0.00001 m). All other
quantities are carried exactly and rounded only when reported, to the decimals of the output contract.
Rates and their classes use the reported heights and the reported standard deviations.
"""


def _G_layouts_md(W) -> str:
    L = {x["id"]: x for x in _GLAYOUTS}
    unit = {"m": "metres, five decimals", "mm": "millimetres, two decimals", "cmm": "integers in units of 0.00001 m"}
    dist = {"m": "metres, one decimal", "dm": "integer decimetres", "ft": "US survey feet, three decimals"}
    temp = {"C": "rod temperature in degC", "F": "rod temperature in degF", None: "no temperature field"}
    tim = {"z": "UTC, ISO 8601 with a Z suffix", "off": "ISO 8601 local time with its UTC offset", "local": "local wall clock YYYY-MM-DD HH:MM:SS",
           "epoch": "UTC epoch seconds", "fw": "local wall clock YYYYMMDD HHMMSS", "dmy": "local wall clock DD.MM.YYYY HH:MM:SS"}
    rid = {"canon": "R-26-dddd", "compact": "R26dddd", "slash": "26/dddd"}
    out = ["# Field book shard layouts", "", "Every shard holds setup records of one layout. The catalog names the layout of each file.",
           "Common to all layouts: one record is one setup revision; `rev` is the revision number; the run id style, reading",
           "unit, distance unit, temperature unit and time style are given per layout. Rod tokens follow H7, run ids H6.", ""]
    spec = {
        "L01": ("CSV, comma separated, lines starting with # are comments",
                "run,setup,rev,void,time_utc,rod_bs,rod_fs,bs_m,fs_m,dist_bs_m,dist_fs_m,rod_temp_c", "void is 1 for a void record and 0 otherwise"),
        "L02": ("TSV, tab separated, blank lines carry no record", "run, set, r, status, time, pair, bs_mm, fs_mm, dbs_dm, dfs_dm, dir_note",
                "status VOID marks a void record; the rods follow from the pair (H7); dir_note is the observer's note and is not used"),
        "L03": ("PSV, pipe separated", "RUN|SETUP|REV|VOIDED|LOCAL_TIME|BACK_ROD|FORE_ROD|BACK_READING_M|FORE_READING_M|BACK_DIST_M|FORE_DIST_M|TEMP_C",
                "VOIDED is Y for a void record and empty otherwise"),
        "L04": ("fixed width text; the first two lines are a title and a column ruler",
                "columns 1-8 run, 9-12 setup, 13-14 rev, 15 void flag V, 16-23 date, 24-29 time, 30-33 pair, 34-40 back reading, 41-47 fore reading, "
                "48-51 back distance, 52-55 fore distance, 56-60 temperature",
                "the temperature is a sign and four digits in tenths of degC, blank when absent; the rods follow from the pair (H7)"),
        "L05": ("JSON Lines", "objects with run.id, setup.n, setup.rev, setup.void, time, bs.rod, bs.r, bs.d, fs.rod, fs.r, fs.d, temp_c",
                "readings and distances are strings; temp_c is null when absent"),
        "L06": ("NDJSON", "objects with run_ref, seq, rev, deleted, epoch_s, pair, bs_mm, fs_mm, dbs_m, dfs_m, temp_f",
                "deleted true marks a void record; temp_f is an empty string when absent; the rods follow from the pair (H7)"),
        "L07": ("JSON document", "export header plus a setups list of objects with run, seq, revision, state, utc, back and fore objects of rod, reading_m, distance_m",
                "state void marks a void record"),
        "L08": ("XML, one setup element per record", "attributes run, seq, rev, void, local, brod, frod, bs_mm, fs_mm, dbs_dm, dfs_dm, temp_c",
                "void true marks a void record; temp_c is empty when absent"),
        "L09": ("YAML list under setups, block or flow mappings", "keys run, set, rev, void, time, pair, bs, fs, d_bs, d_fs, temp, dir",
                "void yes marks a void record; temp ~ when absent; the rods follow from the pair (H7); dir is not used"),
        "L10": ("YAML, setups grouped under runs", "each list item is seq, rev, void, epoch_s, back rod, fore rod, bs_mm, fs_mm, dbs_m, dfs_m",
                "void true marks a void record"),
        "L11": ("Markdown table", "run, setup, rev, status, local time, back rod, fore rod, back m, fore m, back dist m, fore dist m, temp F",
                "status void marks a void record; temp F is empty when absent"),
        "L12": ("SQLite, table obs", "run, seq, rev, void, epoch, pair, bs, fs, dbs, dfs, temp_c",
                "void 1 marks a void record; bs and fs in units of 0.00001 m, dbs and dfs in decimetres; temp_c NULL when absent; the rods follow from the pair (H7)"),
        "L13": ("SQLite, tables setup_key (uid, run, seq, rev) and setup_attr (uid, attr, value)",
                "attributes time_utc, rod_b, rod_f, bs_m, fs_m, dist_b_m, dist_f_m, void, temp_c", "void 1 marks a void record; temp_c is missing when absent"),
        "L14": ("CSV, semicolon separated, decimal comma", "run;opstelling;rev;vervallen;tijd;baak_a;baak_v;a_mm;v_mm;afst_a_m;afst_v_m;temp_c",
                "vervallen ja marks a void record; baak_a is the back rod and baak_v the fore rod; a_mm and v_mm are back and fore readings"),
        "L15": ("TSV, tab separated", "run, seq, rev, void, time, rod_b, rod_f, bs_m, fs_m, dist_b_ft, dist_f_ft, temp_f", "void 1 marks a void record"),
        "L16": ("XML, element per field", "setup elements with run, seq, rev, void, utc, pair, bs, fs, dbs_ft, dfs_ft",
                "void 1 marks a void record; bs and fs in units of 0.00001 m; the rods follow from the pair (H7)"),
    }
    for k in sorted(spec):
        lay = L[k]
        fmt, cols, notes = spec[k]
        out += [f"## Layout {k}", "", f"- encoding: {fmt}", f"- fields: {cols}", f"- run id style: {rid[lay['rid']]}",
                f"- readings: {unit[lay['ru']]}", f"- distances: {dist[lay['du']]}", f"- temperature: {temp[lay['temp']]}",
                f"- time: {tim[lay['time']]}", f"- rods: {'rod tokens per record' if lay['rods'] == 'explicit' else 'rod pair id of the run'}",
                f"- notes: {notes}",
                f"- revision: the rev field is an integer, 1 for the first booking; a higher revision replaces a lower one (H5)",
                f"- void: a void record is a revision like any other; only the winning revision decides whether the setup is dropped",
                f"- setup number: an integer counted from 1 along the run", ""]
    out += ["## Met station logs", "", "- degC CSV: epoch_s, temp_c, rh_pct, station", "- degF TSV: utc (ISO Z), temp (degF), wind_ms",
            "- tenths JSON Lines: t (ISO local time with offset), ta (integer tenths of degC), qc", "",
            "The unit of each log is the `unit` column of the station register.", ""]
    return "\n".join(out) + "\n"


_GCONTRACT = [
    ("setup_ledger.csv", "CSV", "one row per kept setup of every VALID run, sorted by run_id then seq", [
        ("run_id", "run id R-26-dddd"), ("seq", "setup number"), ("instant_utc", "setup instant, ISO 8601 UTC with a Z suffix, whole seconds"),
        ("back_rod", "serial of the back rod (H7)"), ("fore_rod", "serial of the fore rod (H7)"),
        ("back_m", "decoded back reading in metres after half-centimetre decoding, 5 decimals"), ("fore_m", "decoded fore reading, 5 decimals"),
        ("back_dist_m", "back sight distance, 1 decimal"), ("fore_dist_m", "fore sight distance, 1 decimal"),
        ("temp_c", "rod temperature used (H11), 1 decimal"), ("temp_source", "FIELD, MET or FALLBACK"),
        ("dh_raw_m", "back_m - fore_m, 5 decimals"), ("dh_m", "reduced setup height difference (H12), 5 decimals")]),
    ("run_summaries.tsv", "TSV", "one row per run of the campaign in the run register, sorted by run_id", [
        ("run_id", "run id"), ("section_id", "matched section, empty when not matched"), ("direction", "F or B, empty when not matched"),
        ("start_mark", "resolved start mark, empty when unresolved or not reached"), ("end_mark", "resolved end mark, empty when unresolved or not reached"),
        ("run_date", "run date (H8), empty for VOID and NO_SETUPS"), ("setups", "number of kept setups of the run"),
        ("length_m", "run length, 1 decimal, VALID runs only"), ("dh_m", "run height difference, 5 decimals, VALID runs only"),
        ("test_id", "effective two-peg test id when one was found"), ("collimation_mm_per_100m", "c of that test, 3 decimals"),
        ("status", "status of H9")]),
    ("section_pairs.psv", "PSV", "one row per ACTIVE section of the section register, sorted by section_id", [
        ("section_id", "section id"), ("from_mark", "register from mark"), ("to_mark", "register to mark"), ("line_id", "line"),
        ("class", "effective line class (H14)"), ("forward_run", "selected forward run, ACCEPTED only"), ("backward_run", "selected backward run, ACCEPTED only"),
        ("dh_forward_m", "5 decimals, ACCEPTED only"), ("dh_backward_m", "5 decimals, ACCEPTED only"),
        ("discrepancy_mm", "1000 x d, 2 decimals, ACCEPTED only"), ("length_km", "K, 5 decimals, ACCEPTED only"),
        ("tolerance_mm", "t x sqrt(K), 2 decimals, ACCEPTED only"), ("candidates", "number of candidate pairs"),
        ("status", "status of H14"), ("value_m", "section value, 5 decimals, ACCEPTED only")]),
    ("benchmark_resolution.csv", "CSV", "one row per distinct (context, token, resolve_date) that was resolved, sorted by context, token, resolve_date", [
        ("context", "run, control, loop or epoch"), ("token", "the token as written"), ("resolve_date", "ISO date of the resolution"),
        ("mark", "resolved mark, empty when unresolved"), ("hops", "number of alias rows followed"), ("status", "RESOLVED or UNRESOLVED")]),
    ("control_points.json", "JSON", "keys campaign, reference_date, table (C-2), controls", [
        ("controls", "every profile control point in profile order"), ("token", "token as written in the profile"),
        ("mark", "resolved mark or an empty string"), ("status", "status of H16"), ("height_m", "Table C-2 height after errata, 5 decimals; null for UNRESOLVED and NOT_IN_TABLE")]),
    ("adjustment_iterations.jsonl", "JSON Lines", "one object per adjustment of every constrained component, in component then iteration order", [
        ("component", "component name"), ("iteration", "1, 2, ..."), ("observations", "observations in that adjustment"),
        ("unknowns", "unknown heights"), ("redundancy", "observations - unknowns"), ("vtpv", "4 decimals"),
        ("max_w", "sqrt of the largest tested w^2, 2 decimals, null when nothing is testable"),
        ("max_w_section", "its section, null when nothing is testable"), ("action", "REMOVE, STOP_CLEAN, STOP_BUDGET or STOP_REDUNDANCY")]),
    ("adjusted_heights.csv", "CSV", "one row per mark of every constrained component, sorted by mark", [
        ("mark", "mark id"), ("component", "component name"), ("height_m", "5 decimals"), ("sigma_mm", "sqrt(qxx), 2 decimals"), ("status", "FIXED or ADJUSTED")]),
    ("residuals.tsv", "TSV", "one row per ACCEPTED section, sorted by section_id", [
        ("section_id", "section"), ("component", "component name"), ("v_mm", "residual from the final adjustment, 2 decimals; empty for UNCONSTRAINED"),
        ("qvv_mm2", "4 decimals; empty for REMOVED and UNCONSTRAINED"), ("w", "v / sqrt(qvv), 2 decimals, USED only"),
        ("status", "USED, UNTESTABLE, REMOVED or UNCONSTRAINED")]),
    ("network_summary.json", "JSON", "keys campaign, components (sorted by component name)", [
        ("component", "name"), ("marks", "marks of the component"), ("observations", "observations of the final adjustment (all accepted sections when UNCONSTRAINED)"),
        ("unknowns", "unknowns of the final adjustment"), ("redundancy", "redundancy of the final adjustment"), ("fixed", "sorted FIXED marks"),
        ("status", "status of H17"), ("removed", "removed sections in removal order"), ("vtpv", "4 decimals"), ("s0", "3 decimals, null when r = 0"),
        ("chi2_lower", "Table X-2 lower bound, 3 decimals, null when r = 0"), ("chi2_upper", "Table X-2 upper bound, 3 decimals, null when r = 0"),
        ("global_test", "PASS, FAIL, NO_REDUNDANCY or UNCONSTRAINED"),
        ("UNCONSTRAINED components", "unknowns, redundancy, vtpv, s0, chi2_lower and chi2_upper are null; fixed and removed are empty lists")]),
    ("loop_closures.xml", "XML", "root element loops with attribute campaign, one loop element per register loop sorted by id", [
        ("id", "loop id"), ("class", "loop class"), ("marks", "number of marks"), ("misclosure_mm", "2 decimals"), ("length_km", "sum of K, 5 decimals"),
        ("tolerance_mm", "t x sqrt(K), 2 decimals"), ("status", "PASS, FAIL or INCOMPLETE; the three numbers are empty strings for INCOMPLETE")]),
    ("subsidence_rates.csv", "CSV", "one row per mark with an adjusted height, sorted by mark", [
        ("mark", "mark id"), ("height_2024_m", "prior height, 5 decimals; empty for CONTROL, DISTURBED and NEW"), ("height_2026_m", "reported height, 5 decimals"),
        ("rate_mm_per_yr", "2 decimals for ALERT, SUBSIDING, UPLIFT, STABLE"), ("sigma_rate_mm_per_yr", "2 decimals for the same classes"),
        ("class", "class of H20")]),
    ("excluded_records.jsonl", "JSON Lines", "sorted by kind, id, reason", [
        ("kind", "setup, run or section"), ("id", "setup as run#seq, run id or section id"),
        ("reason", "VOID_SETUP for a dropped setup, the H9 status of a run that is not VALID, the H14 status of a section that is not ACCEPTED, SNOOPED for a section removed by data snooping")]),
    ("dedup_report.json", "JSON", "one object with these keys in order", [
        ("records_read", "records read from the read shards"), ("setup_keys", "distinct setups"), ("superseded_revisions", "records below the highest revision"),
        ("duplicates", "duplicates of H5"), ("conflicts", "lost conflicts of H5"), ("void_setups", "setups dropped by a void winner"),
        ("kept_setups", "setups kept"), ("files_read", "number of shards read"), ("files_ignored", "sorted names of the setup shards present but not read")]),
    ("source_lineage.json", "JSON", "key files: the read shards in catalog precedence order, then the ignored setup shards sorted by name", [
        ("file", "file name"), ("status", "READ, RETIRED (listed RETIRED in the catalog) or UNCATALOGUED"), ("records", "records read"),
        ("kept", "winning records kept"), ("superseded", "records below the highest revision"), ("void_selected", "void winners"),
        ("duplicates", "duplicate records"), ("conflicts_lost", "records that lost a conflict; an ignored shard reports zeros")]),
    ("rod_certificates_used.tsv", "TSV", "one row per (rod, certificate) used by a reading of a VALID run, sorted by rod_serial then certificate", [
        ("rod_serial", "serial"), ("rod_type", "type"), ("graduation", "Table A-1 graduation"), ("certificate", "certificate id"),
        ("scale_ppm", "1 decimal"), ("t0_c", "1 decimal"), ("valid_from", "ISO date"), ("valid_to", "ISO date"), ("readings", "back and fore readings using it")]),
    ("parameters_used.yaml", "YAML", "flat key: value lines in this order", [
        ("campaign, reference_date, epoch_reference", "profile values"), ("rod_certificate_sheet, fallback_temp_c, met_max_gap_min", "effective values after the overlay"),
        ("refraction_coefficient, earth_radius_m, collimation_limit_mm_per_100m", "Table I-1 and the quick reference card"),
        ("critical_w, min_redundancy, max_removals, alert_rate_mm_per_yr, k_rate", "Tables K-1 and R-1"),
        ("tolerance_section_<class>_mm, tolerance_loop_<class>_mm, sigma_<class>_mm_per_sqrt_km", "for classes I, II, III in that order, after errata"),
        ("graduation_<type>, alpha_<type>_ppm_per_c", "for each rod type of Table A-1 in sorted order")]),
    ("variance_vs_published.csv", "CSV", "one row per mark in the published heights or the adjusted heights, sorted by mark", [
        ("mark", "mark id"), ("published_m", "published height, 5 decimals"), ("recomputed_m", "reported height, 5 decimals"),
        ("diff_mm", "recomputed - published, 2 decimals, when both exist"), ("status", "MATCH, DIFFERENT, MISSING_PUBLISHED or MISSING_RECOMPUTED")]),
    ("rate_vs_published.psv", "PSV", "one row per mark in the published rates or subsidence_rates.csv, sorted by mark", [
        ("mark", "mark id"), ("published_rate", "2 decimals"), ("recomputed_rate", "2 decimals"), ("published_class", "published class"),
        ("recomputed_class", "class of H20"), ("status", "first of MISSING_PUBLISHED, MISSING_RECOMPUTED, CLASS_DIFFERS, RATE_DIFFERS, MATCH")]),
    ("dashboard_disagreements.csv", "CSV", "one row per section whose dashboard status differs from its recomputed status, sorted by section_id", [
        ("section_id", "section"), ("dashboard_status", "dashboard value"),
        ("recomputed_status", "the section_pairs status, or SNOOPED for a section removed by data snooping")]),
    ("cache_divergence.jsonl", "JSON Lines", "sorted by mark then cache_token", [
        ("mark", "mark the cache token resolves to at the reference date"), ("cache_token", "token as cached"), ("cache_m", "cached height"),
        ("in_force_m", "Table C-2 height after errata"), ("diff_mm", "cache - in force, 2 decimals; only VDH-2025 rows of marks with a different Table C-2 height")]),
    ("reconciliation.md", "Markdown", "title line # <campaign> recomputation summary, then three sections", [
        ("## Counts", "a table with columns item and value and these rows in this order"),
        ("runs_valid, runs_rejected", "run_summaries.tsv rows with status VALID, and with any other status"),
        ("sections_accepted, sections_not_accepted", "section_pairs.psv rows with status ACCEPTED, and with any other status"),
        ("components, components_unconstrained", "network_summary.json components, and those with status UNCONSTRAINED"),
        ("sections_snooped", "sections removed by data snooping over all components"),
        ("marks_adjusted", "rows of adjusted_heights.csv, FIXED and ADJUSTED together"),
        ("marks_alert, loops_failing", "subsidence_rates.csv rows of class ALERT, and loop_closures.xml loops with status FAIL"),
        ("## Run pack settings", "a table with columns setting, pack and used, one row for each of the twelve settings of the run pack settings block in its order"),
        ("used values", "control_table C-2, snooping_variance A_PRIORI, pair_selection MIN_DISCREPANCY, run_date_source FIRST_SETUP_INSTANT, "
                        "rod_scale_applied_to EACH_READING, thermal_correction APPLIED; every other setting takes its governing value"),
        ("## Largest height differences", "a table with columns mark, published_m, recomputed_m and diff_mm for the ten marks of largest absolute difference, ties to the smaller mark")]),
]


def _G_contract_md() -> str:
    out = ["# Output contract", "", "Every report, and manifest.json, is UTF-8 with LF line endings and a final newline. Delimited",
           "reports start with the header of their column list and quote nothing. Numbers are plain decimals with the stated number of decimals, never a",
           "negative zero. JSON numbers are written as decimals; JSON keys appear in the order listed. Empty fields are empty strings",
           "in delimited files and attribute values, null in JSON.", "",
           "manifest.json lists every report below in this order as objects name, bytes and sha256 under a `files` key.", ""]
    for name, kind, order, cols, *rest in _GCONTRACT:
        out += [f"## {name}", "", f"- format: {kind}", f"- rows: {order}", "", "| field | content |", "| --- | --- |"]
        for c, d in cols:
            out.append(f"| {c} | {d} |")
        out.append("")
    return "\n".join(out) + "\n"


# ============================================================================ grading harness
import ast as _ast
import os as _os
import shutil as _shutil
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import threading as _threading
import xml.etree.ElementTree as _ET
from decimal import Decimal as _GD, InvalidOperation as _InvalidOperation

from rewardkit import criteria, criterion

SHIPPED_SEED = 6800948404603382707
OUT = _GPath("/app/out")
PROGRAM = OUT / "run_levelnet.py"
NAMES = list(_GREPORTS)
CORE = list(_GCORE)
_LOCK = _threading.RLock()
_MEMO: dict = {}
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
HELD = {
    "h_reseed": (8823190451277310093, {"pdf_octal": True, "xlsx_runs": True, "yaml_flow": True, "pair_outliers": 2}),
    "h_spring": (2871604438890512271, {"zone_rule": "us", "base_offset": -300, "start": "2027-02-22", "days": 46, "ref_date": "2027-04-20",
                                       "ref24": "2025-04-07", "date1904": False, "xlsx_no_r": True}),
    "h_zone": (6109342237558170091, {"zone_rule": "us", "base_offset": -480, "start": "2026-09-14", "days": 50, "ref_date": "2026-11-09",
                                     "xlsx_runs": True, "yaml_flow": True}),
    "h_memo": (4419987305512338737, {"tol": {"I": ["2.5", "3.5"], "II": ["4.0", "5.5"], "III": ["5.5", "7.0"]}, "tol_erratum": ["I", "3.0"],
                                     "sigma": {"I": "0.60", "II": "0.90", "III": "1.30"}, "k_crit": "3.89", "r_min": 3, "max_removals": 1,
                                     "c_limit": "2.500", "k_ref": "0.11",
                                     "rod_types": {"INV-F": ["FULL", "0.95"], "INV-H": ["HALF", "1.25"], "INV-B": ["HALF", "0.55"]},
                                     "alert": "-6.50", "k_rate": "2.50", "pdf_td": True, "pdf_octal": True, "outliers": 4, "pair_outliers": 3}),
    "h_profile": (5140337712096621873, {"cert_sheet": "Certs_2026C", "fallback_temp": "16.5", "met_max_gap": 50, "control_drop": 3,
                                        "yaml_flow": True, "xlsx_no_r": True}),
    "h_dense": (7307715526630918821, {"rev_rate": 0.14, "void_rate": 0.05, "dup_rate": 0.09, "conflict_rate": 0.03, "void_runs": 6, "gap_runs": 6,
                                      "rerun_rate": 0.2, "reject_sections": 5, "outliers": 9, "unconstrained_block": True, "max_removals": 2,
                                      "xlsx_runs": True, "pdf_td": True, "pair_outliers": 3}),
    "h_mixed": (3318520977461023541, {"mixed_pairs": True, "feet_share": 3, "pdf_octal": True, "xlsx_no_r": True}),
    "m_journal": (None, {"extra_journal": 40}),
    "m_rulings": (None, {"extra_rulings": 8, "control_drop": 2}),
}


# ---------------------------------------------------------------------------- corpora
def _seal(root: _GPath) -> None:
    for p in root.iterdir():
        p.chmod(0o644)
    root.chmod(0o755)
    root.parent.chmod(0o755)


def _corpus(name: str) -> tuple:
    """(data directory, world) for a named corpus, generated once."""
    with _LOCK:
        key = "corpus:" + name
        if key not in _MEMO:
            base = _GPath(_tempfile.mkdtemp(prefix=f"lvn-{name}-"))
            base.chmod(0o755)
            root = base / "data"
            if name in HELD:
                seed, over = HELD[name]
                W = _Ggenerate(root, seed or SHIPPED_SEED, over)
            elif name == "renamed":
                W = _Ggenerate(root, SHIPPED_SEED, {"rename": True})
            else:
                W = _Ggenerate(root, SHIPPED_SEED, None)
            _seal(root)
            _MEMO[key] = (root, W)
        return _MEMO[key]


def _expected(name: str, flip: str = "") -> dict:
    with _LOCK:
        key = f"expected:{name}:{flip}"
        if key not in _MEMO:
            _MEMO[key] = _G_derive(_corpus(name)[1], frozenset({flip}) if flip else frozenset())
        return _MEMO[key]


# ---------------------------------------------------------------------------- running the delivered program
def _root_only_tests_present() -> bool:
    try:
        st = _GPath("/tests").stat()
    except FileNotFoundError:
        return False
    return st.st_uid == 0 and (st.st_mode & 0o077) == 0


def _untrusted(command: list) -> list:
    if _os.name == "posix" and _os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if _os.name == "posix" and _os.geteuid() == 0:
        return [*_SETPRIV, *command]
    return command


def _staged_program():
    """Copy the delivered program into a verifier-owned directory readable by the unprivileged runner."""
    with _LOCK:
        if "staged" not in _MEMO:
            _MEMO["staged"] = None
            if PROGRAM.is_file():
                stage = _GPath(_tempfile.mkdtemp(prefix="lvn-prog-"))
                stage.chmod(0o755)
                staged = stage / "run_levelnet.py"
                _shutil.copyfile(PROGRAM, staged)
                staged.chmod(0o755)
                _MEMO["staged"] = staged
        return _MEMO["staged"]


def _run(name: str, tag: str = ""):
    """Run the delivered program on a fresh copy of a corpus; the output directory or None."""
    with _LOCK:
        key = f"run:{name}:{tag}"
        if key in _MEMO:
            return _MEMO[key]
        _MEMO[key] = None
        prog = _staged_program()
        if prog is None:
            return None
        src = _corpus(name)[0]
        work = _GPath(_tempfile.mkdtemp(prefix=f"lvn-run-{name}-"))
        work.chmod(0o777)
        data = work / ("input" + tag) / "campaign"
        data.parent.mkdir()
        data.parent.chmod(0o755)
        _shutil.copytree(src, data)
        _seal(data)
        out = work / "result"
        try:
            proc = _subprocess.Popen(_untrusted([_sys.executable, str(prog), str(data), str(out)]), stdout=_subprocess.DEVNULL,
                                     stderr=_subprocess.DEVNULL, start_new_session=True)
            try:
                code = proc.wait(timeout=120)
            except _subprocess.TimeoutExpired:
                code = -1
            finally:
                try:
                    _os.killpg(proc.pid, 9)
                except OSError:
                    pass
                proc.wait()
            if code == 0 and out.is_dir():
                _MEMO[key] = out
        except (OSError, _subprocess.SubprocessError):
            _MEMO[key] = None
        return _MEMO[key]


# ---------------------------------------------------------------------------- comparison
_DECRE = _Gre.compile(r"^-?(\d+\.?\d*|\.\d+)$")


def _cell_key(s: str) -> str:
    s = s.strip()
    if _DECRE.match(s):
        d = _GD(s)
        return "#" + ("0" if d == 0 else format(d.normalize(), "f"))
    return s


def _rows_of(text: str, sep: str):
    rd = list(_Gcsv.reader(_Gio.StringIO(text), delimiter=sep))
    return (rd[0] if rd else []), sorted(tuple(_cell_key(c) for c in r) for r in rd[1:])


def _json_norm(o, key=""):
    """Canonical form: numbers by exact value; lists of objects as multisets except the ordered file list."""
    if isinstance(o, dict):
        return {k: _json_norm(v, k) for k, v in o.items()}
    if isinstance(o, list):
        items = [_json_norm(v) for v in o]
        if items and all(isinstance(v, dict) for v in items) and key not in ("files", "controls"):
            items = sorted(items, key=lambda v: _Gjson.dumps(v, sort_keys=True))
        return items
    if isinstance(o, bool) or o is None or isinstance(o, str):
        return o
    if isinstance(o, (int, _GD)):
        d = _GD(o)
        return "#" + ("0" if d == 0 else format(d.normalize(), "f"))
    return repr(o)


def _jload(text: str):
    return _json_norm(_Gjson.loads(text, parse_float=_GD, parse_int=int))


def _md_rows(text: str):
    """Table rows keyed by their section heading, compared as a multiset."""
    out, head = [], ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            head = line.lstrip("#").strip()
        elif line.startswith("|") and not _Gre.fullmatch(r"\|(\s*-+\s*\|)+", line):
            out.append((head, tuple(_cell_key(c) for c in line.strip("|").split("|"))))
    return sorted(out)


def _xml_rows(text: str):
    root = _ET.fromstring(text)
    head = (root.tag, tuple(sorted((k, _cell_key(v)) for k, v in root.attrib.items())))
    return head, sorted((c.tag, tuple(sorted((k, _cell_key(v)) for k, v in c.attrib.items()))) for c in root)


def _yaml_map(text: str):
    out = {}
    for line in text.splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
                v = v[1:-1]
            out[k.strip()] = _cell_key(v)
    return out


def _same(name: str, got, want: str) -> bool:
    """True when the delivered report text equals the expected one under the contract."""
    if got is None:
        return False
    try:
        if name.endswith((".csv", ".tsv", ".psv")):
            sep = {".csv": ",", ".tsv": "\t", ".psv": "|"}[name[-4:]]
            return _rows_of(got, sep) == _rows_of(want, sep)
        if name.endswith(".jsonl"):
            g = sorted(_Gjson.dumps(_jload(x), sort_keys=True) for x in got.splitlines() if x.strip())
            w = sorted(_Gjson.dumps(_jload(x), sort_keys=True) for x in want.splitlines() if x.strip())
            return g == w
        if name.endswith(".json"):
            return _jload(got) == _jload(want)
        if name.endswith(".xml"):
            return _xml_rows(got) == _xml_rows(want)
        if name.endswith(".md"):
            return _md_rows(got) == _md_rows(want)
        if name.endswith(".yaml"):
            return _yaml_map(got) == _yaml_map(want)
    except Exception:
        return False
    return got == want


def _text(base, name: str):
    if base is None:
        return None
    try:
        return (base / name).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _exact_shipped(name: str) -> bool:
    return _same(name, _text(OUT, name), _expected("shipped")[name])


def _all_exact(out, corpus: str, names) -> bool:
    if out is None:
        return False
    want = _expected(corpus)
    return all(_same(n, _text(out, n), want[n]) for n in names)


def _full_core() -> bool:
    """The spine: every core report exact in /app/out and in the rerun on every held-out corpus."""
    with _LOCK:
        if "full_core" not in _MEMO:
            ok = all(_exact_shipped(n) for n in CORE)
            for name in HELD:
                if not ok:
                    break
                ok = _all_exact(_run(name), name, CORE)
            _MEMO["full_core"] = ok
        return _MEMO["full_core"]


def _leaf(*names: str) -> bool:
    return _full_core() and all(_exact_shipped(n) for n in names)


def _held_out_exact(name: str) -> bool:
    return _full_core() and _all_exact(_run(name), name, NAMES)


def _matches_flip(flip: str, name: str) -> bool:
    """True when the delivered shipped report equals one engineered wrong reading that differs from the truth."""
    want = _expected("shipped")[name]
    alt = _expected("shipped", flip)[name]
    return not _same(name, alt, want) and _same(name, _text(OUT, name), alt)


def _safe(fn) -> bool:
    try:
        return bool(fn())
    except Exception:
        return False


def _contract_files() -> list:
    return NAMES + ["manifest.json"]


# ============================================================================ ungated shape checks
@criterion(description="The program run_levelnet.py, all twenty-one contract reports and manifest.json exist under /app/out")
def deliverables_present(workspace: _GPath) -> bool:
    return _safe(lambda: PROGRAM.is_file() and all((OUT / n).is_file() for n in _contract_files()))


@criterion(description="The program runs on a fresh copy of the shipped campaign at another path and writes exactly the twenty-two contract files there")
def program_writes_contract_files(workspace: _GPath) -> bool:
    def chk() -> bool:
        out = _run("shipped", "a")
        return out is not None and sorted(p.name for p in out.iterdir()) == sorted(_contract_files())
    return _safe(chk)


@criterion(description="Every delimited report in /app/out starts with the header columns of the output contract, in order")
def delimited_headers_exact(workspace: _GPath) -> bool:
    def chk() -> bool:
        want = _expected("shipped")
        for n in NAMES:
            if n.endswith((".csv", ".tsv", ".psv")):
                got = _text(OUT, n)
                if got is None or got.split("\n", 1)[0] != want[n].split("\n", 1)[0]:
                    return False
        return True
    return _safe(chk)


@criterion(description="The JSON reports in /app/out parse and carry exactly the top-level keys the output contract names, in order")
def json_report_keys(workspace: _GPath) -> bool:
    try:
        want = _expected("shipped")
        for n in NAMES:
            if n.endswith(".json"):
                got = _Gjson.loads(_text(OUT, n) or "null")
                if not isinstance(got, dict) or list(got) != list(_Gjson.loads(want[n])):
                    return False
        return True
    except Exception:
        return False


@criterion(description="manifest.json lists every report in contract order with its true size and SHA-256 digest")
def manifest_consistent(workspace: _GPath) -> bool:
    try:
        man = _Gjson.loads(_text(OUT, "manifest.json") or "{}")
        files = man.get("files")
        if not isinstance(files, list) or [f.get("name") for f in files] != NAMES:
            return False
        for f in files:
            b = (OUT / f["name"]).read_bytes()
            if f.get("bytes") != len(b) or f.get("sha256") != _Ghashlib.sha256(b).hexdigest():
                return False
        return True
    except Exception:
        return False


@criterion(description="Every report in /app/out is UTF-8 text with LF line endings and a final newline")
def text_serialization(workspace: _GPath) -> bool:
    try:
        for n in _contract_files():
            b = (OUT / n).read_bytes()
            b.decode("utf-8")
            if not b.endswith(b"\n") or b"\r" in b:
                return False
        return True
    except Exception:
        return False


# ============================================================================ shipped reports behind the full-core gate
@criterion(description="The benchmark token resolution is exact for the shipped campaign, with every core report exact")
def benchmark_resolution_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("benchmark_resolution.csv"))


@criterion(description="The control point statuses and heights are exact for the shipped campaign, with every core report exact")
def control_points_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("control_points.json"))


@criterion(description="The loop misclosures are exact for the shipped campaign, with every core report exact")
def loop_closures_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("loop_closures.xml"))


@criterion(description="The excluded setups, runs and sections are exact for the shipped campaign, with every core report exact")
def excluded_records_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("excluded_records.jsonl"))


@criterion(description="The settlement counters are exact for the shipped campaign, with every core report exact")
def dedup_report_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("dedup_report.json"))


@criterion(description="The per-shard source lineage is exact for the shipped campaign, with every core report exact")
def source_lineage_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("source_lineage.json"))


@criterion(description="The rod certificate usage is exact for the shipped campaign, with every core report exact")
def rod_certificates_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("rod_certificates_used.tsv"))


@criterion(description="The governing settings applied are exact for the shipped campaign, with every core report exact")
def parameters_used_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("parameters_used.yaml"))


@criterion(description="The comparison with the published heights is exact for the shipped campaign, with every core report exact")
def variance_vs_published_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("variance_vs_published.csv"))


@criterion(description="The comparison with the published rates is exact for the shipped campaign, with every core report exact")
def rate_vs_published_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("rate_vs_published.psv"))


@criterion(description="The dashboard disagreement list is exact for the shipped campaign, with every core report exact")
def dashboard_disagreements_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("dashboard_disagreements.csv"))


@criterion(description="The control height cache comparison is exact for the shipped campaign, with every core report exact")
def cache_divergence_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("cache_divergence.jsonl"))


@criterion(description="The reconciliation summary is exact for the shipped campaign, with every core report exact")
def reconciliation_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("reconciliation.md"))


# ============================================================================ held-out re-execution
@criterion(description="Rerun on a reseeded campaign with other networks, reruns, rulings and paired outliers, every report is exact")
def heldout_reseed_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_reseed"))


@criterion(description="Rerun on a spring campaign under another site clock across a clock change and the 1900 date system, every report is exact")
def heldout_spring_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_spring"))


@criterion(description="Rerun on a campaign whose site clock puts afternoon setups on the next UTC date, every report is exact")
def heldout_zone_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_zone"))


@criterion(description="Rerun on a campaign whose memo changes tolerances, precision, snooping limits, rod types and rate thresholds, every report is exact")
def heldout_memo_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_memo"))


@criterion(description="Rerun on a campaign whose profile names another certificate sheet, fallback temperature, gap limit and control list, every report is exact")
def heldout_profile_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_profile"))


@criterion(description="Rerun on a denser campaign with more revisions, voids, conflicts, reruns, rejections and outliers, every report is exact")
def heldout_dense_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_dense"))


@criterion(description="Rerun on a campaign with mixed half and full graduation rod pairs and more survey feet shards, every report is exact")
def heldout_mixed_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_mixed"))


@criterion(description="Rerun on the shipped campaign with forty added disturbance journal entries, every report is exact")
def metamorphic_journal_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("m_journal"))


@criterion(description="Rerun on the shipped campaign with added addendum rulings and fewer profile control points, every report is exact")
def metamorphic_rulings_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("m_rulings"))


# ============================================================================ negative checks (True when the cheat or wrong reading is present)
def _echoes_shipped() -> bool:
    want_h = _expected("h_reseed")["adjusted_heights.csv"]
    want_s = _expected("shipped")["adjusted_heights.csv"]
    if _same("adjusted_heights.csv", want_h, want_s):
        return False
    got = _text(_run("h_reseed"), "adjusted_heights.csv")
    return got is not None and _same("adjusted_heights.csv", got, want_s)


@criterion(description="The program ignores its input and replays the shipped adjusted heights on a held-out campaign")
def negative_hardcoded_sample_answers(workspace: _GPath) -> bool:
    # inverted: True when the reseeded run reproduces the shipped adjusted heights
    return _safe(_echoes_shipped)


@criterion(description="The program is exact on a copy of the shipped campaign and wrong once only the shard file names change")
def negative_filename_dependent_behaviour(workspace: _GPath) -> bool:
    # inverted: True when renaming the shards alone breaks an otherwise exact run (a replay is priced by the check above)
    def chk() -> bool:
        if _echoes_shipped():
            return False
        if not _all_exact(_run("shipped", "a"), "shipped", NAMES):
            return False
        return not _all_exact(_run("renamed"), "renamed", NAMES)
    return _safe(chk)


@criterion(description="Two runs of the program on copies of the same campaign write different report bytes")
def negative_nondeterministic_output(workspace: _GPath) -> bool:
    # inverted: True when two runs on identical input differ in any report
    def chk() -> bool:
        a, b = _run("shipped", "a"), _run("shipped", "b")
        if a is None or b is None:
            return False
        return any(_text(a, n) != _text(b, n) for n in NAMES)
    return _safe(chk)


@criterion(description="The delivered source imports a third-party package")
def negative_third_party_import(workspace: _GPath) -> bool:
    # inverted: True when any delivered .py file imports a package outside the standard library
    try:
        banned = {"requests", "urllib3", "httpx", "pandas", "numpy", "openpyxl", "pypdf", "PyPDF2", "yaml", "xlrd", "fitz", "pdfplumber",
                  "lxml", "pdfminer", "scipy", "statsmodels", "polars", "duckdb", "sympy", "mpmath", "networkx", "dateutil", "pytz"}
        for p in sorted(OUT.glob("*.py")):
            for node in _ast.walk(_ast.parse(p.read_text(encoding="utf-8"))):
                names = ({a.name.split(".")[0] for a in node.names} if isinstance(node, _ast.Import) else
                         {(node.module or "").split(".")[0]} if isinstance(node, _ast.ImportFrom) else set())
                if names & banned:
                    return True
        return False
    except Exception:
        return False


def _echoes_published() -> bool:
    """True when half or more of the marks adjusted_heights.csv shares with the published file carry exactly the published height."""
    pub = {}
    for line in (_corpus("shipped")[0] / "adjusted_heights_published.csv").read_text(encoding="utf-8").splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0].startswith("VD-"):
            pub[parts[0]] = _GD(parts[1])
    hit = tot = 0
    for r in _Gcsv.DictReader(_Gio.StringIO(_text(OUT, "adjusted_heights.csv") or "")):
        m = str(r.get("mark", "")).strip()
        try:
            v = _GD(str(r.get("height_m") or "").strip())
        except _InvalidOperation:
            continue
        if m in pub:
            tot += 1
            hit += v == pub[m]
    return tot >= 50 and hit * 2 >= tot


@criterion(description="adjusted_heights.csv repeats the published height for at least half of the marks it shares with the published file")
def negative_echoes_published(workspace: _GPath) -> bool:
    # inverted: True when half or more of the shared marks carry exactly the published height
    return _safe(_echoes_published)


@criterion(description="adjusted_heights.csv holds at least half of its FIXED marks at their withdrawn memo Table C-1 heights and under half of its shared marks at the published height")
def negative_withdrawn_control_table(workspace: _GPath) -> bool:
    # inverted: True when half or more of the FIXED rows carry the Table C-1 height where it differs from Table C-2;
    # a copy of the published heights already holds C-1 controls and is priced once, by negative_echoes_published
    try:
        if _safe(_echoes_published):
            return False
        memo = _corpus("shipped")[1]["memo"]
        c1, c2 = memo["c1"], memo["c2_true"]
        hit = tot = 0
        for r in _Gcsv.DictReader(_Gio.StringIO(_text(OUT, "adjusted_heights.csv") or "")):
            m = str(r.get("mark", "")).strip()
            if str(r.get("status", "")).strip() != "FIXED" or m not in c1 or c1[m] == c2.get(m):
                continue
            try:
                v = _GD(str(r.get("height_m") or "").strip())
            except _InvalidOperation:
                continue
            tot += 1
            hit += v == _GD(c1[m])
        return tot >= 3 and hit * 2 >= tot
    except Exception:
        return False


@criterion(description="network_summary.json equals the data snooping that scales each test by the a posteriori variance factor")
def negative_aposteriori_snooping(workspace: _GPath) -> bool:
    # inverted: True when the shipped component summary matches the a posteriori snooping reading exactly
    return _safe(lambda: _matches_flip("aposteriori", "network_summary.json"))


criteria.deliverables_present(weight=1)
criteria.program_writes_contract_files(weight=1)
criteria.delimited_headers_exact(weight=1)
criteria.json_report_keys(weight=1)
criteria.manifest_consistent(weight=1)
criteria.text_serialization(weight=1)
criteria.benchmark_resolution_exact(weight=3)
criteria.control_points_exact(weight=3)
criteria.loop_closures_exact(weight=3)
criteria.excluded_records_exact(weight=3)
criteria.dedup_report_exact(weight=3)
criteria.source_lineage_exact(weight=3)
criteria.rod_certificates_exact(weight=1)
criteria.parameters_used_exact(weight=1)
criteria.variance_vs_published_exact(weight=1)
criteria.rate_vs_published_exact(weight=1)
criteria.dashboard_disagreements_exact(weight=1)
criteria.cache_divergence_exact(weight=1)
criteria.reconciliation_exact(weight=1)
criteria.heldout_reseed_exact(weight=5)
criteria.heldout_spring_exact(weight=5)
criteria.heldout_zone_exact(weight=5)
criteria.heldout_memo_exact(weight=5)
criteria.heldout_profile_exact(weight=5)
criteria.heldout_dense_exact(weight=5)
criteria.heldout_mixed_exact(weight=5)
criteria.metamorphic_journal_exact(weight=5)
criteria.metamorphic_rulings_exact(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_third_party_import(weight=-3)
criteria.negative_echoes_published(weight=-3)
criteria.negative_withdrawn_control_table(weight=-3)
criteria.negative_aposteriori_snooping(weight=-3)
