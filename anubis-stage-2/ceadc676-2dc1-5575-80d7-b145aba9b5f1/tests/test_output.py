"""Verifier for the EA-IRMS normalization correction task.

The first half of this module is the seeded corpus generator together with the reference
derivation of every report; the grading harness regenerates the shipped batch and eight held-out
batches from it, runs the delivered program on fresh copies, and compares the reports under the
output contract. Nothing here reads the agent's input directory.
"""
from __future__ import annotations

# ============================================================================ generator core
# Seeded corpus generator for the EA-IRMS normalization correction task. Every name in this
# module starts with _G so the whole module can be embedded verbatim in the verifier, which
# regenerates held-out corpora at grade time and derives their expected reports.
import csv as _Gcsv
import hashlib as _Ghashlib
import io as _Gio
import json as _Gjson
import math as _Gmath
import random as _Grandom
import re as _Gre
import sqlite3 as _Gsqlite3
import zipfile as _Gzipfile
import zlib as _Gzlib
from datetime import date as _Gdate, datetime as _Gdt, timedelta as _Gtd, timezone as _Gtz
from decimal import Decimal as _GD, ROUND_HALF_EVEN as _GHE, localcontext as _Glocalcontext
from fractions import Fraction as _GF
from pathlib import Path as _GPath

_GUTC = _Gtz.utc
_GELEMENTS = ("N", "C")

_GDEFAULT = {
    "project": "HSI-2611",
    "other": "HSI-2598",
    "facility": "Halvorsen Stable Isotope Facility",
    "zone_rule": "eu",
    "base_offset": 60,
    "pivot_year": 2026,
    "pivot_kind": "fall",
    "date1904": True,
    "rm_sheet": "RM_Certified_2026",
    "elements": ["N", "C"],
    "sets": {"N": ["RM-GLU-L", "RM-GLU-H"], "C": ["RM-GLU-L", "RM-GLU-H", "RM-CAF"]},
    "withdrawn_sets": {"N": ["RM-GLU-L", "RM-CAF"], "C": ["RM-GLU-H", "RM-CAF"]},
    "reject_limit": {"N": "0.30", "C": "0.25"},
    "max_reject": {"N": 2, "C": 3},
    "slope_window": ["0.950", "1.050"],
    "lin_thr": {"N": "0.0040", "C": "0.0025"},
    "amp_window": {"N": [600, 9000], "C": [1000, 16000]},
    "blank_max": {"N": "0.3000", "C": "0.9000"},
    "qc_tol": {"QC-SED": {"N": "0.25", "C": "0.20"}, "QC-MUS": {"N": "0.20", "C": "0.15"}, "QC-ALG": {"N": "0.30", "C": "0.25"}},
    "lookback": 2,
    "a_ref": {"N": "15.0", "C": "45.0"},
    "drift_material": "QC-ALG",
    "drift_min": 3,
    "alpha": "0.05",
    "lin_min": 5,
    "scope_drop": 4,
    "skips": 6,
    "pauses": 5,
    "journal_chains": 26,
    "revision_rate": 0.065,
    "void_rate": 0.025,
    "extra_journal": 0,
    "extra_rulings": 0,
    "rename": False,
    "outlier_sessions": 4,
    "spring_gap_pause": False,
    "pdf_octal": False,
    "xlsx_runs": False,
    "short_lin": 0,
    "pdf_td": False,
    "xlsx_no_r": False,
    "yaml_flow": False,
    "two_outliers": "",
    "no_norm": False,
    "no_blank": False,
    "no_elm": False,
    "ruling_tie": False,
    "request_tie": False,
    "leak_tie": False,
    "stack_reasons": False,
    "ruled_flag": False,
    "stale_refs": False,
    "limit_and_max": "",
}

_GCFG: dict = {}


def _Gcfg(over: dict | None, seed: int) -> dict:
    cfg = _Gjson.loads(_Gjson.dumps(_GDEFAULT))
    for k, v in (over or {}).items():
        cfg[k] = v
    cfg["seed"] = seed
    return cfg


# ---------------------------------------------------------------------------- exact numbers
def _Gq(x, dp: int) -> _GF:
    """Round an exact rational half to even at dp decimals."""
    x = _GF(x)
    s = 10 ** dp
    v = x * s
    n = v.numerator // v.denominator
    rem = v - n
    if rem > _GF(1, 2) or (rem == _GF(1, 2) and n % 2 == 1):
        n += 1
    return _GF(n, s)


def _Gs(x, dp: int) -> str:
    """Fixed-decimal text of an exact rational already rounded at dp (or rounds it first)."""
    q = _Gq(x, dp)
    n = q * 10 ** dp
    n = n.numerator // n.denominator
    sign = "-" if n < 0 else ""
    n = abs(n)
    if dp == 0:
        return f"{sign}{n}"
    body = str(n).rjust(dp + 1, "0")
    return f"{sign}{body[:-dp]}.{body[-dp:]}"


def _Gfrac(text) -> _GF:
    return _GF(_GD(str(text).strip()))


def _Gsqrt_dec(x: _GF, dp: int) -> str:
    with _Glocalcontext() as ctx:
        ctx.prec = 60
        d = (_GD(x.numerator) / _GD(x.denominator)).sqrt()
        return str(d.quantize(_GD(1).scaleb(-dp), rounding=_GHE))


def _Gmean(vals):
    return sum(vals, _GF(0)) / len(vals)


def _Gols(xs, ys):
    n = len(xs)
    mx = sum(xs, _GF(0)) / n
    my = sum(ys, _GF(0)) / n
    sxx = sum(((x - mx) ** 2 for x in xs), _GF(0))
    sxy = sum(((x - mx) * (y - my) for x, y in zip(xs, ys)), _GF(0))
    if sxx == 0:
        return None
    m = sxy / sxx
    return m, my - m * mx


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


def _G_transitions(rule: str, base: int) -> list:
    out = []
    for y in range(1990, 2090):
        if rule == "eu":
            out.append((_Gdt(y, 3, _G_last_sunday(y, 3), 1, 0, tzinfo=_GUTC), base + 60))
            out.append((_Gdt(y, 10, _G_last_sunday(y, 10), 1, 0, tzinfo=_GUTC), base))
        else:
            s = _Gdt(y, 3, _G_nth_sunday(y, 3, 2), 2, 0, tzinfo=_GUTC) - _Gtd(minutes=base)
            f = _Gdt(y, 11, _G_nth_sunday(y, 11, 1), 2, 0, tzinfo=_GUTC) - _Gtd(minutes=base + 60)
            out.append((s, base + 60))
            out.append((f, base))
    return out


def _Goffset_at(u, clock) -> int:
    off = clock["base"]
    for t, o in clock["trans"]:
        if u >= t:
            off = o
        else:
            break
    return off


def _Gwall_to_utc(w, clock):
    cands = []
    for o in sorted({clock["base"]} | {o for _, o in clock["trans"]}):
        u = (w - _Gtd(minutes=o)).replace(tzinfo=_GUTC)
        if _Goffset_at(u, clock) == o:
            cands.append(u)
    if cands:
        return min(cands)
    prev = clock["base"]
    for t, o in clock["trans"]:
        a = (w - _Gtd(minutes=prev)).replace(tzinfo=_GUTC)
        b = (w - _Gtd(minutes=o)).replace(tzinfo=_GUTC)
        if a >= t > b:
            return a
        prev = o
    raise ValueError("unmappable wall time")


def _Gutc_to_wall(u, clock):
    return (u + _Gtd(minutes=_Goffset_at(u, clock))).replace(tzinfo=None)


def _Goff_text(m: int) -> str:
    s = "+" if m >= 0 else "-"
    m = abs(m)
    return f"{s}{m // 60:02d}:{m % 60:02d}"


def _Gis_ambiguous_second(u, clock) -> bool:
    """True when the wall time of instant u also names an earlier instant (second pass of a repeated hour)."""
    w = _Gutc_to_wall(u, clock)
    return _Gwall_to_utc(w, clock) != u


# ---------------------------------------------------------------------------- statistics for tables
def _G_betacf(a, b, x):
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 500):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        de = d * c
        h *= de
        if abs(de - 1.0) < 1e-15:
            break
    return h


def _G_ibeta(a, b, x):
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lb = _Gmath.lgamma(a + b) - _Gmath.lgamma(a) - _Gmath.lgamma(b)
    front = _Gmath.exp(lb + a * _Gmath.log(x) + b * _Gmath.log(1 - x))
    if x < (a + 1) / (a + b + 2):
        return front * _G_betacf(a, b, x) / a
    return 1 - front * _G_betacf(b, a, 1 - x) / b


def _G_tcdf(t, df):
    x = df / (df + t * t)
    p = 0.5 * _G_ibeta(df / 2.0, 0.5, x)
    return 1 - p if t > 0 else p


def _G_tq(p, df):
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if _G_tcdf(mid, df) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def _G_grubbs(n, alpha, two_sided=True):
    p = 1 - alpha / (2 * n) if two_sided else 1 - alpha / n
    t = _G_tq(p, n - 2)
    return (n - 1) / _Gmath.sqrt(n) * _Gmath.sqrt(t * t / (n - 2 + t * t))
# ============================================================================ world model
_GSCHED_A = [("K1", -5, 9, 10), ("K1", -4, 19, 20), ("K1", -3, 8, 45), ("K1", -1, 17, 30), ("K1", 1, 9, 5), ("K1", 3, 0, 25),
             ("K1", 3, 18, 50), ("K1", 5, 8, 30), ("K1", 6, 19, 10), ("K1", 9, 9, 0), ("K1", 11, 8, 55),
             ("K2", -5, 20, 15), ("K2", -4, 8, 50), ("K2", -2, 9, 30), ("K2", -1, 21, 30), ("K2", 1, 19, 40), ("K2", 3, 9, 15),
             ("K2", 4, 20, 5), ("K2", 6, 8, 40), ("K2", 7, 19, 30), ("K2", 8, 9, 20), ("K2", 10, 8, 35)]
_GSCHED_L = [("K1", -5, 6, 40), ("K1", -3, 6, 20), ("K1", -1, 13, 50), ("K1", 1, 6, 40), ("K1", 3, 16, 10), ("K1", 5, 6, 5), ("K1", 11, 6, 30),
             ("K2", -5, 17, 40), ("K2", -4, 6, 20), ("K2", -2, 7, 0), ("K2", -1, 18, 55), ("K2", 1, 17, 10), ("K2", 3, 6, 45),
             ("K2", 6, 6, 15), ("K2", 8, 6, 55), ("K2", 10, 6, 10)]
_GSCHED_O = [("K1", -2, 9, 40), ("K2", 0, 10, 15), ("K1", 4, 9, 25), ("K2", 5, 9, 50), ("K1", 7, 8, 50), ("K2", 9, 9, 5)]

_GTRAY_A = (["COND", "BLK", "BLK", "BLK", "ELM-ACT", "ELM-ACT", "ELM-ACT", "RM-GLU-L", "RM-GLU-H", "RM-CAF", "QC-ALG", "QC-SED"]
            + (["S"] * 5 + ["QC-ALG"]) * 3 + ["RM-GLU-L", "RM-GLU-H", "RM-CAF", "QC-MUS"] + (["S"] * 5 + ["QC-ALG"]) * 2
            + ["RM-GLU-L", "RM-GLU-H", "RM-CAF", "QC-SED", "QC-MUS", "QC-ALG", "BLK"])
_GLIN_MASS = ["0.040", "0.052", "0.066", "0.083", "0.105", "0.131", "0.164", "0.202", "0.248", "0.296", "0.351", "0.402"]

_GCOMP = {"RM-GLU-L": ("9.52", "40.82"), "RM-GLU-H": ("9.52", "40.82"), "RM-CAF": ("28.85", "49.48"),
          "QC-ALG": ("7.85", "45.10"), "QC-SED": ("0.36", "3.95"), "QC-MUS": ("10.90", "42.60")}
_GLOTS = {"RM-GLU-L": ["GL-24A", "GL-25B"], "RM-GLU-H": ["GH-23C", "GH-25A"], "RM-CAF": ["CF-22A", "CF-25C"],
          "QC-ALG": ["QA-2601"], "QC-SED": ["QS-2512"], "QC-MUS": ["QM-2604"], "ELM-ACT": ["EA-1", "EA-2"]}
_GCERT = {"GL-24A": ("-4.52", "-26.39"), "GL-25B": ("-4.49", "-26.36"), "GH-23C": ("47.57", "36.55"), "GH-25A": ("47.62", "36.60"),
          "CF-22A": ("1.00", "-27.77"), "CF-25C": ("0.96", "-27.73")}
_GCERT_R = {"GL-24A": ("-4.52", "-26.39"), "GL-25B": ("-4.47", "-26.33"), "GH-23C": ("47.57", "36.55"), "GH-25A": ("47.59", "36.63"),
            "CF-22A": ("1.00", "-27.77"), "CF-25C": ("0.99", "-27.70")}
_GCERT_D = {"GL-24A": ("-4.50", "-26.30"), "GL-25B": ("-4.46", "-26.31"), "GH-23C": ("47.55", "36.48"), "GH-25A": ("47.68", "36.66"),
            "CF-22A": ("1.03", "-27.71"), "CF-25C": ("0.92", "-27.80")}
_GCERT_OLD = {"GL-19A": ("-4.50", "-26.24"), "GH-19B": ("47.60", "36.50"), "CF-18A": ("0.97", "-27.80"), "GL-24A": ("-4.48", "-26.34")}
_GQC_ASSIGNED = {"QC-ALG": ("5.21", "-20.35"), "QC-SED": ("6.84", "-24.12"), "QC-MUS": ("9.37", "-18.44")}
_GQC_FORMER = {"QC-ALG": ("5.18", "-20.41"), "QC-SED": ("6.90", "-24.05"), "QC-MUS": ("9.31", "-18.50")}
_GELM = {"EA-1": ("10.36", "71.09"), "EA-2": ("10.33", "71.15")}
_GELM_OLD = {"EA-1": ("10.36", "71.09"), "EA-2": ("10.36", "71.09")}
_GELM_D = ("1.18", "-29.53")
_GRM_TOKENS = {"RM-GLU-L": ["RM-GLU-L", "GLU-L", "RMGL", "glu-l"], "RM-GLU-H": ["RM-GLU-H", "GLU-H", "RMGH", " glu-h"],
               "RM-CAF": ["RM-CAF", "CAF", "CAFF-1"], "ELM-ACT": ["ELM-ACT", "ACET", "ELM"], "QC-ALG": ["QC-ALG", "ALGAE", "QC-A"],
               "QC-SED": ["QC-SED", "SED-7"], "QC-MUS": ["QC-MUS", "MUS", "QC-M"], "BLK": ["BLK", "BLANK", "TIN"], "COND": ["COND", "CND"]}
_GCLASS = {"RM-GLU-L": "RM", "RM-GLU-H": "RM", "RM-CAF": "RM", "ELM-ACT": "ELM", "QC-ALG": "QC", "QC-SED": "QC", "QC-MUS": "QC",
           "BLK": "BLK", "COND": "COND"}
_GFLAG_CODES = [("F-DROP", "capsule dropped during loading", "EXCLUDE"), ("F-TEAR", "tin capsule torn", "EXCLUDE"),
                ("F-ASH", "incomplete combustion residue", "EXCLUDE"), ("F-WET", "sample visibly wet", "EXCLUDE"),
                ("F-SWAP", "suspected capsule swap", "EXCLUDE"), ("F-NOTE", "free text note", "KEEP"), ("F-LATE", "weighed after cutoff", "KEEP"),
                ("F-LOWV", "low amplitude noted", "KEEP"), ("F-REWT", "reweighed once", "KEEP"), ("F-DUST", "dust on tray noted", "KEEP"),
                ("F-STAT", "static on balance", "KEEP"), ("F-COLR", "unusual colour", "KEEP"), ("F-SMLL", "small capsule fold", "KEEP"),
                ("F-OLDB", "old batch label", "KEEP"), ("F-RECK", "rechecked by second analyst", "KEEP"), ("F-HUMD", "humid day note", "KEEP")]
_GREASONS = [("RI-01", "baseline drift under the peak", "ACCEPTED"), ("RI-02", "peak tailing truncated", "ACCEPTED"),
             ("RI-03", "split peak merged", "ACCEPTED"), ("RI-04", "shoulder from previous peak", "ACCEPTED"),
             ("RI-05", "start point moved to valley", "ACCEPTED"), ("RI-06", "end point moved to baseline", "ACCEPTED"),
             ("RI-07", "analyst preference", "REJECTED"), ("RI-08", "value looked unexpected", "REJECTED"),
             ("RI-09", "match published value", "REJECTED"), ("RI-10", "unrecorded reason", "REJECTED"),
             ("RI-11", "noise spike removed", "ACCEPTED"), ("RI-12", "reference pulse overlap", "ACCEPTED"),
             ("RI-13", "smoothing changed", "REJECTED"), ("RI-14", "threshold lowered to include peak", "REJECTED"),
             ("RI-15", "background subtraction window moved", "ACCEPTED"), ("RI-16", "integration batch default", "REJECTED"),
             ("RI-17", "carry-over correction", "REJECTED"), ("RI-18", "detector saturation flag cleared", "REJECTED"),
             ("RI-19", "manual baseline from blank", "ACCEPTED"), ("RI-20", "duplicate peak removed", "ACCEPTED")]


def _G_pivot(cfg) -> _Gdate:
    y = cfg["pivot_year"]
    if cfg["zone_rule"] == "eu":
        return _Gdate(y, 10, _G_last_sunday(y, 10)) if cfg["pivot_kind"] == "fall" else _Gdate(y, 3, _G_last_sunday(y, 3))
    return _Gdate(y, 11, _G_nth_sunday(y, 11, 1)) if cfg["pivot_kind"] == "fall" else _Gdate(y, 3, _G_nth_sunday(y, 3, 2))


def _G_sid(kind: str, project: str, n: int) -> str:
    return f"{'SQ' if kind in 'AO' else 'LN'}-{project.split('-')[1]}-{n:02d}"


def _G_sample_ids(rng, n, lo, hi):
    ids = set()
    while len(ids) < n:
        ids.add(rng.randint(lo, hi))
    return [f"HS-{i:04d}" for i in sorted(ids)]


def _G_world(seed: int, cfg: dict) -> dict:  # noqa: C901
    rng = _Grandom.Random(seed)
    W: dict = {"cfg": cfg}
    W["clock"] = {"base": cfg["base_offset"], "trans": _G_transitions(cfg["zone_rule"], cfg["base_offset"])}
    P = _G_pivot(cfg)
    W["pivot"] = P
    W["qcx_switch"] = P + _Gtd(days=3)
    proj, other = cfg["project"], cfg["other"]
    # ------------------------------------------------------------------ sessions
    sessions = []
    for kind, plan in (("A", _GSCHED_A), ("L", _GSCHED_L), ("O", _GSCHED_O)):
        rows = []
        for inst, dd, hh, mm in plan:
            jit = rng.randint(-6, 6)
            start = _Gdt.combine(P + _Gtd(days=dd), _Gdt.min.time()) + _Gtd(hours=hh, minutes=mm + jit)
            rows.append((start, inst))
        rows.sort()
        for i, (start, inst) in enumerate(rows, 1):
            sessions.append({"id": _G_sid(kind, other if kind == "O" else proj, i), "kind": kind, "inst": inst,
                             "project": other if kind == "O" else proj, "start_wall": start})
    W["sessions"] = sessions
    A = [s for s in sessions if s["kind"] == "A"]
    L = [s for s in sessions if s["kind"] == "L"]
    # ------------------------------------------------------------------ samples
    samples = _G_sample_ids(rng, 240, 1000, 7999)
    others = _G_sample_ids(_Grandom.Random(seed ^ 0x2598), 24, 8000, 9899)
    W["samples"] = samples
    W["other_samples"] = others
    truth = {}
    for sid in samples + others:
        npct = rng.uniform(0.3, 9.0)
        cpct = min(52.0, npct * rng.uniform(4.0, 16.0) + rng.uniform(0.5, 3.0))
        truth[sid] = {"N": rng.uniform(-1.5, 14.0), "C": rng.uniform(-31.0, -12.0), "pN": npct, "pC": cpct}
    W["sample_truth"] = truth
    scope = list(samples)
    drop = rng.sample(samples, cfg["scope_drop"])
    W["scope"] = [s for s in scope if s not in drop]
    W["scope_dropped"] = drop
    W["client_id"] = {}
    used = set()
    for sid in samples + others:
        while True:
            cid = f"CL-{rng.randint(3000, 4999)}-{rng.randint(1, 40):02d}"
            if cid not in used:
                used.add(cid)
                break
        W["client_id"][sid] = cid
    # replicate plan
    counts = {s: 2 for s in samples}
    pool = list(samples)
    rng.shuffle(pool)
    for s in pool[:10]:
        counts[s] = 1
    for s in pool[10:44]:
        counts[s] = 3
    for s in pool[44:56]:
        counts[s] = 4
    for s in pool[56:62]:
        counts[s] = 5
    W["outlier_samples"] = {s: rng.choice("NC") for s in pool[44:52] + pool[10:12]}
    reps = [s for s in samples for _ in range(counts[s])] + rng.sample(others, 4)
    rng.shuffle(reps)
    per = [[] for _ in A]
    order = sorted(range(len(reps)), key=lambda i: i)
    k = 0
    for i in order:
        s = reps[i]
        tries = 0
        while True:
            j = (k + tries) % len(A)
            if len(per[j]) < 25 and s not in per[j]:
                per[j].append(s)
                break
            tries += 1
            if tries > len(A):
                j = min(range(len(A)), key=lambda q: len(per[q]))
                per[j].append(s)
                break
        k += 1
    # ------------------------------------------------------------------ trays
    capn = [1000]

    def capsule() -> str:
        capn[0] += rng.randint(1, 7)
        return f"TC-{capn[0]:05d}"

    for si, s in enumerate(A):
        names = list(_GTRAY_A)
        smp = list(per[si])
        rng.shuffle(smp)
        trays = []
        for t, nm in enumerate(names, 1):
            mat = smp.pop() if nm == "S" else nm
            trays.append({"tray": t, "true": mat})
        s["trays"] = trays
    short = set(range(1, 1 + 2 * cfg["short_lin"], 2))
    for i, s in enumerate(L):
        masses = _GLIN_MASS[::3] if i in short else _GLIN_MASS
        s["trays"] = [{"tray": 1, "true": "COND"}] + [{"tray": t + 2, "true": "ELM-ACT", "lin_mass": m} for t, m in enumerate(masses)]
    for s in sessions:
        if s["kind"] == "O":
            n = 20
            mats = ["COND", "BLK", "ELM-ACT", "RM-GLU-L", "RM-GLU-H", "QC-ALG"] + rng.sample(others, 12) + ["RM-GLU-L", "RM-GLU-H"]
            s["trays"] = [{"tray": t, "true": m} for t, m in enumerate(mats[:n], 1)]
    # material class, capsule, lot, mass
    for s in sessions:
        for sl in s["trays"]:
            m = sl["true"]
            sl["class"] = _GCLASS.get(m, "SAMPLE")
            sl["capsule"] = capsule() if sl["class"] not in ("BLK", "COND") else ""
            sl["lot"] = rng.choice(_GLOTS[m]) if m in _GLOTS else ""
            if sl["class"] == "SAMPLE":
                t = truth[m]
                mass = max(0.08, min(6.0, rng.uniform(7.0, 28.0) / (t["pN"] * 10)))
            elif m in ("RM-GLU-L", "RM-GLU-H"):
                mass = rng.uniform(0.110, 0.190)
            elif m == "RM-CAF":
                mass = rng.uniform(0.045, 0.075)
            elif m == "ELM-ACT":
                mass = float(sl["lin_mass"]) if "lin_mass" in sl else rng.uniform(0.120, 0.170)
            elif m == "QC-ALG":
                mass = rng.uniform(0.18, 0.24)
            elif m == "QC-SED":
                mass = rng.uniform(1.2, 1.6)
            elif m == "QC-MUS":
                mass = rng.uniform(0.14, 0.20)
            else:
                mass = None
            sl["mass"] = None if mass is None else _Gs(_GF(mass), 3)
    # amplitude-window RM capsules (tiny or overloaded)
    rm_slots = [(s, sl) for s in A for sl in s["trays"] if sl["class"] == "RM"]
    W["rm_hits"] = set()
    picks = []
    for s, sl in rng.sample(rm_slots, len(rm_slots)):
        if (s["id"], sl["true"]) not in W["rm_hits"] and len(picks) < 5 and not (len(picks) >= 3 and sl["true"] == "RM-CAF"):
            picks.append((s, sl))
            W["rm_hits"].add((s["id"], sl["true"]))
    for i, (s, sl) in enumerate(picks):
        sl["mass"] = ("0.031" if sl["true"] != "RM-CAF" else "0.012") if i < 3 else "0.452"
    # balances and weigh dates
    bal = {}
    d0 = P - _Gtd(days=175)
    for b in ("BAL-2", "BAL-3", "BAL-5"):
        rows, d = [], d0
        while d < P + _Gtd(days=60):
            span = rng.randint(2, 4)
            rows.append((d, d + _Gtd(days=span), _Gq(_GF(1 + rng.uniform(-0.0004, 0.0004)), 6)))
            d += _Gtd(days=span)
        bal[b] = rows
    W["balances"] = bal
    for s in sessions:
        for sl in s["trays"]:
            if sl["mass"] is None:
                continue
            sl["balance"] = rng.choice(list(bal))
            wd = s["start_wall"].date() - _Gtd(days=rng.randint(1, 3))
            if rng.random() < 0.08:
                cands = [r[0] for r in bal[sl["balance"]] if abs((r[0] - wd).days) <= 3]
                wd = cands[0] if cands else wd
            sl["weighed"] = wd
            fac = next(f for a, b, f in bal[sl["balance"]] if a <= wd < b)
            sl["mass_corr"] = _Gq(_Gfrac(sl["mass"]) * fac, 4)
    # ------------------------------------------------------------------ journal (tray corrections) and sequence tokens
    W["journal"] = []
    jseq = [rng.randint(400, 600)]

    def jput(s, tray, value, action, status="POSTED", target=None, project=None):
        jseq[0] += rng.randint(1, 4)
        e = {"seq": jseq[0], "project": project or s["project"], "session": s["id"], "tray": tray, "field": "token", "value": value,
             "action": action, "status": status, "reverses": target}
        W["journal"].append(e)
        return jseq[0]

    for s in sessions:
        for sl in s["trays"]:
            sl["seq_token"] = None
            sl["journal_seq"] = None
    sample_slots = [(s, sl) for s in A for sl in s["trays"] if sl["class"] == "SAMPLE" and sl["true"] in samples]
    picks = rng.sample(sample_slots, cfg["journal_chains"])
    special = [(s, sl) for s in A for sl in s["trays"] if sl["true"] == "RM-CAF" and sl["tray"] == 10][:1]
    special += [(s, sl) for s in A[5:] for sl in s["trays"] if sl["true"] == "QC-MUS" and sl["tray"] == 34][:1]
    for i, (s, sl) in enumerate(picks + special):
        kind = i % 8
        true = sl["true"]
        if sl["class"] == "SAMPLE":
            wrong = rng.choice([x for x in samples if x != true])
        elif true == "RM-CAF":
            wrong = "RM-GLU-L"
            kind = 0
        else:
            wrong = "QC-SED"
            kind = 3
        wrong2 = rng.choice([x for x in samples if x not in (true, wrong)]) if sl["class"] == "SAMPLE" else "QC-ALG"
        if kind == 0:
            sl["seq_token"] = wrong
            sl["journal_seq"] = jput(s, sl["tray"], true, "SET")
        elif kind == 1:
            sl["seq_token"] = wrong
            jput(s, sl["tray"], wrong2, "SET")
            sl["journal_seq"] = jput(s, sl["tray"], true, "SET")
        elif kind == 2:
            sl["seq_token"] = true
            a = jput(s, sl["tray"], wrong, "SET")
            jput(s, sl["tray"], "", "REVERSE", target=a)
        elif kind == 3:
            sl["seq_token"] = wrong2
            a = jput(s, sl["tray"], true, "SET")
            b = jput(s, sl["tray"], wrong, "SET")
            jput(s, sl["tray"], "", "REVERSE", target=b)
            sl["journal_seq"] = a
        elif kind == 4:
            sl["seq_token"] = wrong
            a = jput(s, sl["tray"], true, "set")
            b = jput(s, sl["tray"], "", "REVERSE", target=a)
            jput(s, sl["tray"], "", "Reverse", target=b)
            sl["journal_seq"] = a
        elif kind == 5:
            sl["seq_token"] = true
            jput(s, sl["tray"], wrong, "SET", status="PENDING")
        elif kind == 6:
            sl["seq_token"] = wrong
            sl["journal_seq"] = jput(s, sl["tray"], true, "SET", status="posted")
        else:
            sl["seq_token"] = wrong
            a = jput(s, sl["tray"], true, "SET")
            jput(s, sl["tray"], "", "REVERSE", status="DRAFT", target=a)
            sl["journal_seq"] = a
    for s in [x for x in sessions if x["kind"] == "O"][:3]:
        jput(s, 9, rng.choice(others), "SET")
    # ------------------------------------------------------------------ autosampler jams (counter cursor drift)
    W["skips"] = {}
    jam_sessions = rng.sample(A, cfg["skips"])
    for i, s in enumerate(jam_sessions):
        cand = [sl["tray"] for sl in s["trays"] if 14 <= sl["tray"] <= 50 and sl["class"] in ("SAMPLE", "QC")]
        n = 2 if i % 3 == 0 else 1
        jams = sorted(rng.sample(cand, n))
        if i == 0:
            jams = [jams[0], jams[0] + 1] if jams[0] + 1 in cand else jams
        s["jams"] = jams
    for s in sessions:
        s.setdefault("jams", [])
    return W


def _G_assign_tokens(W, rng):
    """Sequence-table tokens for every slot; aliases chosen per slot."""
    proj = W["cfg"]["project"]
    for s in W["sessions"]:
        for sl in s["trays"]:
            base = sl["seq_token"] if sl["seq_token"] is not None else sl["true"]
            sl["seq_token"] = _G_token_for(W, s, base, rng)
        if s["kind"] == "A" and s["start_wall"].hour < 2 and s["start_wall"].date() >= W["qcx_switch"]:
            mus = [sl for sl in s["trays"] if sl["true"] == "QC-MUS" and sl.get("journal_seq") is None]
            if mus:
                mus[0]["seq_token"] = "QCX"
    return proj


def _G_token_for(W, s, mat, rng) -> str:
    if mat in _GRM_TOKENS:
        if mat in ("QC-SED", "QC-MUS") and rng.random() < 0.25:
            boundary = W["qcx_switch"]
            d = s["start_wall"].date()
            if (mat == "QC-SED" and d < boundary) or (mat == "QC-MUS" and d >= boundary):
                return "QCX"
        return rng.choice(_GRM_TOKENS[mat])
    u = rng.random()
    if mat in W["other_samples"]:
        return mat if u < 0.6 else (W["client_id"][mat] if u < 0.8 else mat.lower())
    if u < 0.55:
        return mat
    if u < 0.72:
        return mat.replace("-", "")
    if u < 0.86:
        return W["client_id"][mat]
    return mat.lower() + (" " if rng.random() < 0.5 else "")
# ============================================================================ measurement simulation
def _G_ceil_min(u):
    if u.second or u.microsecond:
        u = u.replace(second=0, microsecond=0) + _Gtd(minutes=1)
    return u


def _G_typed(u, clock) -> str:
    """Operator-typed wall time; inside the first hour after a forward jump the unadjusted clock is used."""
    prev = clock["base"]
    for t, o in clock["trans"]:
        if o > prev and t <= u < t + _Gtd(minutes=o - prev):
            return (u + _Gtd(minutes=prev)).replace(tzinfo=None).strftime("%Y-%m-%d %H:%M")
        prev = o
    return _Gutc_to_wall(u, clock).strftime("%Y-%m-%d %H:%M")


def _G_timeline(W, rng):
    cfg, clock = W["cfg"], W["clock"]
    A = [s for s in W["sessions"] if s["kind"] == "A"]
    trans = [t for t, o in clock["trans"] if abs((t.date() - W["pivot"]).days) <= 1]
    tr = trans[0] if trans else None
    # pause plan
    special = [s for s in A if s["inst"] == "K1" and (s["start_wall"].date() - W["pivot"]).days == -1]
    cross = [s for s in A if s["inst"] == "K2" and (s["start_wall"].date() - W["pivot"]).days == -1]
    pool = [s for s in A if s not in special + cross]
    paused = rng.sample(pool, cfg["pauses"])
    for s in W["sessions"]:
        s["pause"] = None
        s["t1"] = _Gwall_to_utc(s["start_wall"], clock)
        meas = [sl for sl in s["trays"] if sl["tray"] not in s["jams"]]
        n = len(meas)
        p = rng.randint(18, 36) if (s in paused or (cfg["spring_gap_pause"] and s in cross)) else None
        dur = rng.randint(40, 95)
        times = [s["t1"]]
        for c in range(2, n + 1):
            prevt = times[-1]
            if p is not None and c == p + 1:
                ps = _G_ceil_min(prevt + _Gtd(seconds=240))
                if cfg["spring_gap_pause"] and s in cross and tr is not None:
                    ps = max(ps, tr + _Gtd(minutes=7))
                while _Gis_ambiguous_second(ps, clock) or _Gis_ambiguous_second(ps + _Gtd(minutes=dur), clock):
                    ps += _Gtd(minutes=70)
                pe = ps + _Gtd(minutes=dur)
                s["pause"] = (ps, pe)
                times.append(pe + _Gtd(seconds=150 + rng.randint(0, 40)))
            else:
                times.append(prevt + _Gtd(seconds=630 + rng.randint(-18, 18)))
        s["inj"] = []
        for c, (sl, t) in enumerate(zip(meas, times), 1):
            sec = (t - s["t1"]).total_seconds()
            if s["pause"] and t >= s["pause"][1]:
                sec -= (s["pause"][1] - s["pause"][0]).total_seconds()
            s["inj"].append({"counter": c, "tray": sl["tray"], "utc": t, "rt": _GF(int(sec), 60), "slot": sl, "peaks": {}})
        s["t_last"] = times[-1]
        s["local_date"] = _Gutc_to_wall(s["t1"], clock).date()


def _G_measure(W, rng):  # noqa: C901
    cfg = W["cfg"]
    sheet = {"RM_Certified_2026": _GCERT, "RM_Certified_2026R": _GCERT_R}.get(cfg["rm_sheet"], _GCERT)
    A = [s for s in W["sessions"] if s["kind"] == "A"]
    roles = list(A)
    rng.shuffle(roles)
    ls = next(x for x in roles if (x["id"], "RM-CAF") not in W["rm_hits"])
    roles.remove(ls)
    roles.insert(6, ls)
    W["rm_hits"].add((ls["id"], "RM-CAF"))
    W["role"] = {"qcfail": roles[0]["id"], "override": roles[1]["id"], "slope": roles[2]["id"], "leak": roles[3]["id"],
                 "two": roles[4]["id"], "carousel": roles[5]["id"], "limitstop": roles[6]["id"]}
    outl = [x["id"] for x in roles[7:7 + cfg["outlier_sessions"]]]
    dirty = {roles[8]["id"], roles[12]["id"]}
    W["spare"] = [x["id"] for x in roles[::-1][:6]]
    nb = W["spare"][0] if cfg["no_blank"] else None
    if cfg["no_norm"]:
        for sl in [x for x in next(x for x in A if x["id"] == W["spare"][1])["trays"] if x["true"] == "RM-GLU-H"][:2]:
            sl["mass"] = "0.031"
            sl["mass_corr"] = _Gq(_Gfrac("0.031") * next(f for a, b, f in W["balances"][sl["balance"]] if a <= sl["weighed"] < b), 4)
    ktrue = {}
    for s in W["sessions"]:
        prm = {}
        for e in _GELEMENTS:
            a = rng.uniform(0.978, 1.022)
            if e == "C" and s["id"] == W["role"]["slope"]:
                a = 1.068
            prm[e] = {"a": a, "b": rng.uniform(-2.5, 2.5) if e == "N" else rng.uniform(-1.8, 1.8),
                      "K": rng.uniform(0.96, 1.08) if e == "N" else rng.uniform(1.48, 1.66),
                      "Ab": rng.uniform(0.05, 0.11) if e == "N" else rng.uniform(0.16, 0.30),
                      "db": rng.uniform(-0.8, 2.6) if e == "N" else rng.uniform(-28.2, -25.4),
                      "d": rng.uniform(-0.0009, 0.0009)}
        s["prm"] = prm
        if s["inst"] not in ktrue:
            kk = {}
            for e in _GELEMENTS:
                hi = (0.003, 0.012) if e == "N" else (0.0015, 0.006)
                kk[e] = rng.uniform(*hi) * rng.choice((-1, 1))
            ktrue[s["inst"]] = kk
        key = (s["inst"], s["local_date"])
        if key not in ktrue:
            ktrue[key] = {e: ktrue[s["inst"]][e] * rng.uniform(0.55, 1.45) for e in _GELEMENTS}
        s["k"] = ktrue[key]
    W["ktrue"] = ktrue
    aref = {e: float(cfg["a_ref"][e]) for e in _GELEMENTS}
    fac = {"N": 101.0, "C": 178.0}
    sig = {"N": 0.035, "C": 0.025}
    for s in W["sessions"]:
        bumps = {}
        if cfg["limit_and_max"] and s["id"] == W["spare"][5]:
            e = cfg["limit_and_max"]
            by = {}
            for ij in s["inj"]:
                if ij["slot"]["class"] == "RM":
                    by.setdefault(ij["slot"]["true"], []).append(ij)
            a, b = [m for m in cfg["sets"][e] if (s["id"], m) not in W["rm_hits"] and len(by.get(m, [])) >= 3][:2]
            bumps[(by[a][0]["counter"], e)] = 0.9
            bumps[(by[b][0]["counter"], e)] = 0.6
            sl1 = by[b][1]["slot"]
            sl1["mass"] = "0.012" if b == "RM-CAF" else "0.031"
            sl1["mass_corr"] = _Gq(_Gfrac(sl1["mass"]) * next(f for x, y, f in W["balances"][sl1["balance"]] if x <= sl1["weighed"] < y), 4)
            W["rm_hits"].update({(s["id"], a), (s["id"], b)})
        if s["id"] in outl or s["id"] == W["role"]["limitstop"]:
            rms = [ij for ij in s["inj"] if ij["slot"]["class"] == "RM"]
            e = rng.choice(_GELEMENTS)
            if s["id"] == W["role"]["limitstop"]:
                cafs = [ij for ij in rms if ij["slot"]["true"] == "RM-CAF"]
                e = "C"
                bumps[(cafs[0]["counter"], e)] = 0.9
                sl1 = cafs[1]["slot"]
                sl1["mass"] = "0.009"
                sl1["mass_corr"] = _Gq(_Gfrac("0.009") * next(f for a, b, f in W["balances"][sl1["balance"]] if a <= sl1["weighed"] < b), 4)
            else:
                fx = bool(cfg["two_outliers"]) and s["id"] == outl[0]
                if fx:
                    e = cfg["two_outliers"]
                    rms = [x for x in rms if x["slot"]["true"] in cfg["sets"][e] and (s["id"], x["slot"]["true"]) not in W["rm_hits"]]
                first = rng.choice(rms)
                chosen = [first] + ([rng.choice([x for x in rms if x["slot"]["true"] != first["slot"]["true"]])] if s["id"] == outl[0] else [])
                if fx:
                    W["rm_hits"].update((s["id"], x["slot"]["true"]) for x in chosen)
                for ij in chosen:
                    bumps[(ij["counter"], e)] = rng.choice((1, -1)) * rng.uniform(0.62, 0.88)
        dirt = rng.choice([ij["counter"] for ij in s["inj"] if ij["slot"]["class"] == "BLK"]) if s["id"] in dirty else None
        for ij in s["inj"]:
            sl = ij["slot"]
            m = sl["true"]
            for e in _GELEMENTS:
                p = s["prm"][e]
                abi = p["Ab"] * rng.uniform(0.92, 1.08)
                if sl["class"] == "BLK":
                    area = p["Ab"] * rng.uniform(0.85, 1.15) * (12.0 if s["id"] == nb else 5.5 if ij["counter"] == dirt else 1.0)
                    delta = p["db"] + rng.gauss(0, 0.35 if e == "N" else 0.22)
                else:
                    if sl["class"] == "SAMPLE":
                        t = W["sample_truth"][m]
                        pct, dtrue = (t["pN"] if e == "N" else t["pC"]), t[e]
                        if m in W["outlier_samples"] and W["outlier_samples"][m] == e and not W.get("_bumped", {}).get(m):
                            W.setdefault("_bumped", {})[m] = True
                            dtrue += rng.choice((1, -1)) * rng.uniform(1.6, 2.4)
                    elif m == "ELM-ACT":
                        pct = float(_GELM[sl["lot"]][0 if e == "N" else 1])
                        dtrue = float(_GELM_D[0 if e == "N" else 1])
                    elif m == "COND":
                        pct, dtrue = (10.36 if e == "N" else 71.09), float(_GELM_D[0 if e == "N" else 1])
                    elif sl["class"] == "RM":
                        pct = float(_GCOMP[m][0 if e == "N" else 1])
                        dtrue = float(sheet[sl["lot"]][0 if e == "N" else 1])
                    else:
                        pct = float(_GCOMP[m][0 if e == "N" else 1])
                        dtrue = float(_GQC_ASSIGNED[m][0 if e == "N" else 1])
                        if s["id"] == W["role"]["qcfail"] and m == "QC-MUS" and e == "N":
                            dtrue += 0.42
                        if s["id"] == W["role"]["override"] and m == "QC-SED" and e == "C":
                            dtrue -= 0.34
                        if cfg["stack_reasons"] and s["id"] == W["role"]["slope"] and m == "QC-SED" and e == "C":
                            dtrue -= 0.34
                        if s["id"] == W["role"]["two"] and m == "QC-SED" and e == "N":
                            dtrue += 0.37
                    mass = float(sl["mass_corr"]) if sl.get("mass_corr") is not None else 0.5
                    anet = mass * 1000 * pct / 100 / p["K"]
                    area = anet + abi
                    dinst = (dtrue - p["b"]) / p["a"]
                    mix = (dinst * anet + p["db"] * abi) / area
                    delta = mix + p["d"] * (float(ij["rt"]) - 280) + s["k"][e] * (area - aref[e]) + rng.gauss(0, sig[e])
                    delta += bumps.get((ij["counter"], e), 0.0)
                A = _Gq(_GF(area), 4)
                ij["peaks"][e] = {"revs": [{"rev": 0, "area": A, "amp": int(round(float(A) * fac[e] * rng.uniform(0.96, 1.04))),
                                            "delta": _Gq(_GF(delta), 3), "void": False}]}


def _G_revisions(W, rng):  # noqa: C901
    cfg = W["cfg"]
    acc = [c for c, _, st in _GREASONS if st == "ACCEPTED"]
    rej = [c for c, _, st in _GREASONS if st == "REJECTED"]
    audit = []
    eid = [rng.randint(7000, 7400)]

    def put(s, ij, e, rev, action, reason, when):
        eid[0] += rng.randint(1, 5)
        audit.append({"entry": eid[0], "project": s["project"], "session": s["id"], "counter": ij["counter"], "element": e,
                      "revision": rev, "action": action, "reason": reason, "entered": when, "analyst": rng.choice(["MKV", "TJL", "ARS", "PNB"])})

    for s in W["sessions"]:
        for ij in s["inj"]:
            for e in _GELEMENTS:
                pk = ij["peaks"][e]
                pk["admitted"] = {0}
                if s["kind"] == "O" or rng.random() >= cfg["revision_rate"]:
                    continue
                nrev = 2 if rng.random() < 0.25 else 1
                for r in range(1, nrev + 1):
                    last = pk["revs"][-1]
                    pk["revs"].append({"rev": r, "area": _Gq(last["area"] * _GF(1 + rng.uniform(-0.015, 0.015)), 4), "amp": last["amp"],
                                       "delta": _Gq(last["delta"] + _GF(rng.uniform(-0.09, 0.09)), 3), "void": False})
                    base = ij["utc"] + _Gtd(days=rng.randint(1, 4), minutes=rng.randint(0, 600))
                    case = rng.random()
                    if case < 0.40:
                        put(s, ij, e, r, "APPROVE", rng.choice(acc), base)
                        pk["admitted"].add(r)
                    elif case < 0.55:
                        put(s, ij, e, r, "APPROVE", rng.choice(rej), base)
                    elif case < 0.67:
                        put(s, ij, e, r, "APPROVE", rng.choice(acc), base)
                        put(s, ij, e, r, "REVOKE", "RI-10", base + _Gtd(hours=rng.randint(2, 30)))
                    elif case < 0.79:
                        put(s, ij, e, r, "APPROVE", rng.choice(rej), base)
                        put(s, ij, e, r, "APPROVE", rng.choice(acc), base + _Gtd(hours=rng.randint(2, 30)))
                        pk["admitted"].add(r)
                    elif case < 0.90:
                        pass
                    else:
                        put(s, ij, e, r, "REVOKE", "RI-10", base)
                        put(s, ij, e, r, "APPROVE", rng.choice(acc), base)
                        pk["admitted"].add(r)
    # noise: entries for revisions that do not exist and for the other project
    for s in rng.sample(W["sessions"], 10):
        ij = rng.choice(s["inj"])
        put(s, ij, rng.choice(_GELEMENTS), 3, "APPROVE", rng.choice(acc), ij["utc"] + _Gtd(days=2))
    for s in W["sessions"]:
        for ij in s["inj"]:
            for e in _GELEMENTS:
                pk = ij["peaks"][e]
                pk["sel"] = max(r for r in pk["admitted"] if r < len(pk["revs"]))
                pk["void"] = False
    # voids
    for s in W["sessions"]:
        if s["kind"] == "O":
            continue
        for ij in s["inj"]:
            for e in _GELEMENTS:
                pk = ij["peaks"][e]
                u = rng.random()
                hit = (s["id"], ij["slot"]["true"])
                if ij["slot"]["class"] == "RM" and u < cfg["void_rate"]:
                    if hit in W["rm_hits"]:
                        continue
                    W["rm_hits"].add(hit)
                if u < cfg["void_rate"]:
                    pk["revs"][pk["sel"]]["void"] = True
                    pk["void"] = True
                elif u < cfg["void_rate"] * 1.4 and len(pk["revs"]) > 1:
                    other = [r for r in range(len(pk["revs"])) if r != pk["sel"]]
                    pk["revs"][rng.choice(other)]["void"] = True
    W["audit"] = audit


def _G_flags_rulings_events(W, rng):  # noqa: C901
    cfg, clock = W["cfg"], W["clock"]
    proj = cfg["project"]
    A = [s for s in W["sessions"] if s["kind"] == "A"]
    excl = [c for c, _, st in _GFLAG_CODES if st == "EXCLUDE"]
    keep = [c for c, _, st in _GFLAG_CODES if st == "KEEP"]
    flags = []
    caps = [(s, ij) for s in A for ij in s["inj"] if ij["slot"]["capsule"]]
    groups = {"RM": 3, "QC-ALG": 2, "ELM": 1, "SAMPLE": 6, "QC": 1}
    chosen = []
    for g, n in groups.items():
        pool = [x for x in caps if (x[1]["slot"]["true"] == g if g == "QC-ALG" else x[1]["slot"]["class"] == g) and x not in chosen
                and (x[0]["id"], x[1]["slot"]["true"]) not in W["rm_hits"]]
        got = rng.sample(pool, n)
        for s, ij in got:
            if ij["slot"]["class"] == "RM":
                W["rm_hits"].add((s["id"], ij["slot"]["true"]))
        chosen += got
    for s, ij in chosen:
        flags.append({"capsule": ij["slot"]["capsule"], "code": rng.choice(excl), "when": ij["utc"] - _Gtd(hours=rng.randint(1, 6))})
        ij["slot"]["flag"] = flags[-1]["code"]
    for s, ij in rng.sample([x for x in caps if x not in chosen], 210):
        flags.append({"capsule": ij["slot"]["capsule"], "code": rng.choice(keep), "when": ij["utc"] - _Gtd(hours=rng.randint(1, 30))})
    if cfg["no_elm"]:
        for s, ij in [x for x in caps if x[0]["id"] == W["spare"][2] and x[1]["slot"]["class"] == "ELM" and "flag" not in x[1]["slot"]]:
            flags.append({"capsule": ij["slot"]["capsule"], "code": rng.choice(excl), "when": ij["utc"] - _Gtd(hours=rng.randint(1, 6))})
            ij["slot"]["flag"] = flags[-1]["code"]
    rng.shuffle(flags)
    W["flags"] = flags
    # rulings
    R = []
    rid = [rng.randint(300, 340)]

    def rule(project, target, element, action, status, when, note):
        rid[0] += rng.randint(1, 3)
        R.append({"id": f"RL-{rid[0]:04d}", "date": when, "project": project, "target": target, "element": element, "action": action,
                  "status": status, "note": note})
        return R[-1]["id"]

    role = W["role"]
    byid = {s["id"]: s for s in W["sessions"]}
    P = W["pivot"]
    for i in range(70):
        rule(rng.choice(["HSI-2577", "HSI-2581", cfg["other"]]), f"SQ-{rng.choice(['2577', '2581', '2598'])}-{rng.randint(1, 30):02d}",
             rng.choice(["N", "C", "ALL"]), rng.choice(["REJECT_SESSION", "ACCEPT_SESSION", "EXCLUDE_POSITION"]),
             rng.choice(["IN FORCE", "IN FORCE", "RESCINDED", "SUPERSEDED"]), P - _Gtd(days=rng.randint(40, 400)), "historical batch")
    R.sort(key=lambda r: r["date"])
    W["ruling_effect"] = {}
    W["excluded_by_ruling"] = {}
    d = P + _Gtd(days=13)
    rule(proj, byid[role["override"]]["id"], "C", "ACCEPT_SESSION", "IN FORCE", d, "sediment QC deviation traced to a single capsule batch")
    rule(proj, byid[role["carousel"]]["id"], "N", "REJECT_SESSION", "IN FORCE", d, "carousel jam reported by the operator")
    x = rng.choice([s for s in A if s["id"] not in role.values()])
    rule(proj, x["id"], "ALL", "REJECT_SESSION", "RESCINDED", d - _Gtd(days=2), "leak suspected, retest passed")
    rule(proj, byid[role["two"]]["id"], "ALL", "REJECT_SESSION", "IN FORCE", d - _Gtd(days=1), "nitrogen QC excursion")
    rule(proj, byid[role["two"]]["id"], "ALL", "ACCEPT_SESSION", "IN FORCE", d + _Gtd(days=2), "excursion explained by QC-SED bottle swap")
    short = byid[role["slope"]]["id"]
    rule(cfg["other"], "SQ-" + short.split("-")[2], "ALL", "ACCEPT_SESSION", "IN FORCE", d, "other project, short session token")
    pos = []
    for cls in ("SAMPLE", "RM", "QC-ALG"):
        cand = [(s, ij) for s in A for ij in s["inj"] if (ij["slot"]["true"] == cls if cls == "QC-ALG" else ij["slot"]["class"] == cls)
                and "flag" not in ij["slot"] and (s["id"], ij["slot"]["true"]) not in W["rm_hits"]]
        pos.append(rng.choice(cand))
        if cls == "RM":
            W["rm_hits"].add((pos[-1][0]["id"], pos[-1][1]["slot"]["true"]))
    for s, ij in pos:
        r = rule(proj, f"{s['id']}/{ij['tray']}", "ALL", "EXCLUDE_POSITION", "IN FORCE", d + _Gtd(days=1), "position excluded on review")
        W["excluded_by_ruling"][(s["id"], ij["tray"])] = r
    if cfg["ruled_flag"]:
        s, ij = next((s, ij) for s in A for ij in s["inj"] if ij["slot"].get("flag") in excl and ij["slot"]["class"] == "SAMPLE")
        r = rule(proj, f"{s['id']}/{ij['tray']}", "ALL", "EXCLUDE_POSITION", "IN FORCE", d + _Gtd(days=1), "position excluded on review")
        W["excluded_by_ruling"][(s["id"], ij["tray"])] = r
    s, ij = rng.choice([(s, ij) for s in A for ij in s["inj"] if ij["slot"]["class"] == "SAMPLE"])
    rule(proj, f"{s['id']}/{ij['tray']}", "ALL", "EXCLUDE_POSITION", "RESCINDED", d + _Gtd(days=1), "exclusion withdrawn")
    for i in range(cfg["extra_rulings"]):
        s = rng.choice(A)
        rule(proj, s["id"], rng.choice(["N", "C", "ALL"]), rng.choice(["REJECT_SESSION", "ACCEPT_SESSION"]), rng.choice(["IN FORCE", "RESCINDED"]),
             d + _Gtd(days=3 + i), "review board decision")
    if cfg["ruling_tie"]:
        tie = W["spare"][3]
        rule(proj, tie, "ALL", "REJECT_SESSION", "IN FORCE", d + _Gtd(days=30), "board vote recorded")
        rule(proj, tie, "ALL", "ACCEPT_SESSION", "IN FORCE", d + _Gtd(days=30), "board vote corrected")
        if cfg["ruling_tie"] == "printed_late":
            R[-2], R[-1] = R[-1], R[-2]
    W["rulings"] = R
    # session events
    ev = []
    eid = [rng.randint(100, 160)]

    def evt(s, kind, u, detail=""):
        while _Gis_ambiguous_second(u, clock):
            u += _Gtd(minutes=61)
        eid[0] += rng.randint(1, 3)
        ev.append({"id": eid[0], "project": s["project"], "session": s["id"], "inst": s["inst"], "event": kind, "local": _G_typed(u, clock),
                   "detail": detail, "_u": u})

    leak2 = rng.choice([s for s in A if s["id"] not in role.values()])
    ltie = next(x for x in W["spare"][4:] if x != leak2["id"]) if cfg["leak_tie"] else None
    stack = {role["slope"], W["spare"][1]} if cfg["stack_reasons"] else set()
    for s in W["sessions"]:
        lt = _G_ceil_min(s["t1"] - _Gtd(minutes=35))
        if s["id"] in stack:
            evt(s, "LEAK_CHECK", lt, "FAIL")
        elif s["id"] == ltie:
            evt(s, "LEAK_CHECK", lt, "FAIL")
            evt(s, "LEAK_CHECK", lt, "PASS")
        elif s["id"] == leak2["id"]:
            evt(s, "LEAK_CHECK", lt - _Gtd(minutes=20), "FAIL")
            evt(s, "LEAK_CHECK", lt, "PASS")
        elif s["id"] == role["leak"]:
            evt(s, "LEAK_CHECK", lt - _Gtd(minutes=20), "PASS")
            evt(s, "LEAK_CHECK", lt, "FAIL")
        else:
            evt(s, "LEAK_CHECK", lt, "PASS")
        evt(s, "START", _G_ceil_min(s["t1"] - _Gtd(minutes=3)), "sequence loaded")
        if s["pause"]:
            evt(s, "PAUSE", s["pause"][0], "helium cylinder change")
            evt(s, "RESUME", s["pause"][1], "flow stable")
        for q in range(rng.randint(1, 3)):
            evt(s, "NOTE", _G_ceil_min(s["inj"][(len(s["inj"]) * (q + 1)) // 4]["utc"]), rng.choice(["room temperature 21.4 C", "ash crucible ok", "trap checked"]))
        evt(s, "END", _G_ceil_min(s["t_last"] + _Gtd(minutes=9)), "sequence complete")
    rng.shuffle(ev)
    W["events"] = ev
    W["leak_fail"] = {role["leak"]} | stack
# ============================================================================ reference derivation
_GREPORTS = ["injection_ledger.csv", "position_resolution.csv", "alias_resolution.psv", "dedup_report.json", "source_lineage.json",
             "linearity_slopes.json", "drift_fits.tsv", "blank_corrections.psv", "normalization_fits.json", "corrected_injections.jsonl",
             "elemental_factors.tsv", "session_acceptance.csv", "qc_results.xml", "isotope_results.csv", "replicate_screening.jsonl",
             "parameters_used.yaml", "variance_vs_published.csv", "session_param_diff.json", "dashboard_disagreements.csv",
             "cache_divergence.jsonl", "reconciliation.md"]
_GCORE = ["injection_ledger.csv", "linearity_slopes.json", "drift_fits.tsv", "normalization_fits.json", "corrected_injections.jsonl",
          "session_acceptance.csv", "isotope_results.csv", "replicate_screening.jsonl"]
_GMOLAR = {"C": "12.0106", "N": "14.0067"}


def _G_cert(W):
    return {"RM_Certified_2026": _GCERT, "RM_Certified_2026R": _GCERT_R}[W["cfg"]["rm_sheet"]]


def _G_ingest(W, flip=""):  # noqa: C901
    proj = W["cfg"]["project"]
    seen, cand = set(), {}
    tot = {k: 0 for k in ("records", "other_project", "reference_peaks", "inactive_segment", "duplicates")}
    lineage = []
    for f in W["file_order"]:
        row = {"file": W["fname"][f], "layout": W["layout_of"][f], "records": 0, "other_project": 0, "reference_peaks": 0,
               "inactive_segment": 0, "duplicates": 0, "unique": 0}
        for r in W["records"][f]:
            row["records"] += 1
            if r["project"] != proj:
                row["other_project"] += 1
            elif r["ptype"] == "R":
                row["reference_peaks"] += 1
            elif (f, r["session"]) not in W["active"]:
                row["inactive_segment"] += 1
            else:
                ident = (r["session"], r["counter"], r["element"], r["rev"])
                if ident in seen:
                    row["duplicates"] += 1
                else:
                    seen.add(ident)
                    row["unique"] += 1
                    cand.setdefault(ident[:3], {})[r["rev"]] = r
        for k in tot:
            tot[k] += row[k]
        lineage.append(row)
    na = sup = vd = kept = 0
    keep = {}
    for key, revs in cand.items():
        adm = [r for r in revs if r == 0 or (key + (r,)) in W["admitted"]]
        na += len(revs) - len(adm)
        sel = max(adm)
        sup += len(adm) - 1
        if revs[sel]["void"]:
            vd += 1
        else:
            kept += 1
            keep[key] = revs[sel]
    dedup = {"files_read": len(W["file_order"]), "records_read": tot["records"], "other_project": tot["other_project"],
             "reference_peaks": tot["reference_peaks"], "inactive_segment": tot["inactive_segment"], "duplicates": tot["duplicates"],
             "revisions_not_admitted": na, "revisions_superseded": sup, "voided": vd, "kept": kept}
    return keep, dedup, lineage


def _G_state(W, flip=""):  # noqa: C901
    cfg, clock = W["cfg"], W["clock"]
    keep, dedup, lineage = _G_ingest(W, flip)
    sess = {s["id"]: s for s in W["sessions"] if s["project"] == cfg["project"]}
    S = {"dedup": dedup, "lineage": lineage, "sess": sess}
    # injections per session
    INJ = {}
    for (sid, cnt, e), r in keep.items():
        if sid not in sess:
            continue
        INJ.setdefault(sid, {}).setdefault(cnt, {})[e] = r
    skips = W["skip_counters"]
    slots = {(s["id"], sl["tray"]): sl for s in sess.values() for sl in s["trays"]}
    ledger = []
    per = {}
    for sid in sorted(INJ):
        s = sess[sid]
        t1 = None
        for cnt in sorted(INJ[sid]):
            for e in INJ[sid][cnt]:
                t1 = INJ[sid][cnt][e]["utc"] if t1 is None else t1
        t1 = W["t1"][sid]
        pause = s["pause"]
        for cnt in sorted(INJ[sid]):
            tray = cnt if flip == "skip_ignored" else cnt + sum(1 for q in skips.get(sid, []) if q <= cnt)
            sl = slots.get((sid, tray))
            for e in cfg["elements"]:
                r = INJ[sid][cnt].get(e)
                if r is None:
                    continue
                sec = int((r["utc"] - t1).total_seconds())
                if pause and r["utc"] >= pause[1]:
                    sec -= int((pause[1] - pause[0]).total_seconds())
                exc = ""
                if sl is not None:
                    if (sid, tray) in W["excluded_by_ruling"]:
                        exc = "RULING:" + W["excluded_by_ruling"][(sid, tray)]
                    elif sl.get("flag") in W["exclude_codes"]:
                        exc = "FLAG:" + sl["flag"]
                rec = {"session": sid, "inst": s["inst"], "counter": cnt, "tray": tray, "slot": sl, "element": e, "rev": r["rev"],
                       "area": r["area"], "amp": r["amp"], "delta": r["delta"], "utc": r["utc"], "rt": _GF(sec, 60), "excluded": exc,
                       "material": sl["true"] if sl else "", "class": sl["class"] if sl else ""}
                ledger.append(rec)
                per.setdefault((sid, e), []).append(rec)
    S["ledger"] = ledger
    S["per"] = per
    S["t1"] = {sid: W["t1"][sid] for sid in sess}
    S["local_date"] = {sid: _Gutc_to_wall(W["t1"][sid], clock).date() for sid in sess}
    return S


def _G_compute(W, flip=""):  # noqa: C901
    cfg = W["cfg"]
    S = _G_state(W, flip)
    sess, per = S["sess"], S["per"]
    els = cfg["elements"]
    cert = _G_cert(W)
    sets = cfg["withdrawn_sets"] if flip == "withdrawn_set" else cfg["sets"]
    aref = {e: _Gfrac(cfg["a_ref"][e]) for e in els}
    # ---- linearity slopes per LIN session
    lin = {}
    for sid, s in sess.items():
        if s["kind"] != "L":
            continue
        for e in els:
            pts = [r for r in per.get((sid, e), []) if r["class"] == "ELM" and not r["excluded"]]
            k = None
            if len(pts) >= cfg["lin_min"]:
                f = _Gols([r["area"] for r in pts], [r["delta"] for r in pts])
                k = None if f is None else _Gq(f[0], 6)
            lin[(sid, e)] = {"n": len(pts), "k": k}
    S["lin"] = lin
    lins = sorted([sid for sid, s in sess.items() if s["kind"] == "L"], key=lambda x: S["t1"][x])
    assign = {}
    for sid, s in sess.items():
        if s["kind"] != "A":
            continue
        D = S["local_date"][sid]
        for e in els:
            found = None
            same = [l for l in lins if sess[l]["inst"] == s["inst"] and S["local_date"][l] == D and S["t1"][l] < S["t1"][sid]
                    and lin[(l, e)]["k"] is not None]
            if same:
                found = same[-1]
            else:
                back = [l for l in lins if sess[l]["inst"] == s["inst"] and D - _Gtd(days=cfg["lookback"]) <= S["local_date"][l] < D
                        and lin[(l, e)]["k"] is not None]
                if back:
                    found = back[-1]
            if found is None:
                assign[(sid, e)] = {"lin": None, "k": None, "applied": _GF(0), "status": "NONE"}
            else:
                k = lin[(found, e)]["k"]
                ok = abs(k) >= _Gfrac(cfg["lin_thr"][e])
                assign[(sid, e)] = {"lin": found, "k": k, "applied": k if ok else _GF(0), "status": "APPLIED" if ok else "BELOW_THRESHOLD"}
    S["assign"] = assign
    # ---- per analytical session and element
    drift, blank, norm, elem, acc, corr = {}, {}, {}, {}, {}, {}
    win = cfg["amp_window"]
    for sid, s in sess.items():
        if s["kind"] != "A":
            continue
        for e in els:
            rows = [r for r in per.get((sid, e), []) if not r["excluded"]]
            k = assign[(sid, e)]["applied"]
            work = {}
            bl = [r for r in rows if r["class"] == "BLK"]
            good = [r for r in bl if r["area"] <= _Gfrac(cfg["blank_max"][e])]
            if good:
                Ab = _Gq(_Gmean([r["area"] for r in good]), 4)
                db = _Gq(_Gmean([r["delta"] for r in good]), 3)
            else:
                Ab, db = _GF(0), _GF(0)
            blank[(sid, e)] = {"n": len(good), "rej": len(bl) - len(good), "Ab": Ab, "db": db}
            meas = [r for r in rows if r["class"] in ("RM", "QC", "ELM", "SAMPLE")]

            def bcorr(dv, A):
                return _Gq((dv * A - db * Ab) / (A - Ab), 4)

            for r in meas:
                work[id(r)] = {"d1": _Gq(r["delta"] - k * (r["area"] - aref[e]), 4)}
            dm = cfg["drift_material"]
            dp = [r for r in meas if r["material"] == dm]
            xs = [r["rt"] for r in dp]
            if len(dp) >= cfg["drift_min"]:
                f = _Gols(xs, [work[id(r)]["d1"] for r in dp])
                dslope = _Gq(f[0], 8) if f else _GF(0)
                status = "FITTED"
            else:
                dslope, status = _GF(0), "INSUFFICIENT"
            anchor = _Gq(_Gmean(xs), 4) if xs else _GF(0)
            drift[(sid, e)] = {"n": len(dp), "slope": dslope, "anchor": anchor, "status": status}
            for r in meas:
                w = work[id(r)]
                w["d2"] = _Gq(w["d1"] - dslope * (r["rt"] - anchor), 4)
                w["d3"] = bcorr(w["d2"], r["area"])
            # normalization
            pts = [r for r in meas if r["class"] == "RM" and r["material"] in sets[e] and win[e][0] <= r["amp"] <= win[e][1]]
            fit = {"set": list(sets[e]), "n": len(pts), "removed": [], "fits": 0, "m": None, "b": None, "status": "NO_NORMALIZATION"}
            if all(sum(1 for r in pts if r["material"] == m) >= 2 for m in sets[e]):
                live = list(pts)
                while True:
                    xv = [work[id(r)]["d3"] for r in live]
                    yv = [_Gfrac(cert[r["slot"]["lot"]][0 if e == "N" else 1]) for r in live]
                    m, b = _Gols(xv, yv)
                    fit["fits"] += 1
                    res = [(abs(y - (m * x + b)), r["tray"], r, y - (m * x + b)) for x, y, r in zip(xv, yv, live)]
                    worst = max(res, key=lambda t: (t[0], -t[1]))
                    if worst[0] <= _Gfrac(cfg["reject_limit"][e]):
                        fit["status"] = "CONVERGED"
                        break
                    mat = worst[2]["material"]
                    if sum(1 for r in live if r["material"] == mat) - 1 < 2:
                        fit["status"] = "LIMIT_STOP"
                        break
                    if len(fit["removed"]) >= cfg["max_reject"][e]:
                        fit["status"] = "MAX_REJECT"
                        break
                    fit["removed"].append({"tray": worst[1], "material": mat, "residual": _Gq(worst[3], 4)})
                    live.remove(worst[2])
                fit["m"], fit["b"], fit["n"] = _Gq(m, 6), _Gq(b, 6), len(live)
            norm[(sid, e)] = fit
            # elemental response
            stds = [r for r in meas if r["class"] == "ELM" and r["slot"].get("mass_corr") is not None]
            K = None
            if stds:
                fs = [r["slot"]["mass_corr"] * 1000 * _Gfrac(W["elm_comp"][r["slot"]["lot"]][0 if e == "N" else 1]) / 100 / (r["area"] - Ab) for r in stds]
                K = _Gq(_Gmean(fs), 6)
            elem[(sid, e)] = {"n": len(stds), "K": K}
            for r in meas:
                w = work[id(r)]
                w["d4"] = None if fit["m"] is None else _Gq(fit["m"] * w["d3"] + fit["b"], 3)
                mc = r["slot"].get("mass_corr")
                w["pct"] = None if (K is None or mc is None or r["class"] == "ELM") else _Gq((r["area"] - Ab) * K / (mc * 1000) * 100, 3)
                corr[(sid, r["tray"], e)] = (r, w)
            # acceptance
            reasons = []
            slope_ok = fit["m"] is not None and _Gfrac(cfg["slope_window"][0]) <= fit["m"] <= _Gfrac(cfg["slope_window"][1])
            if fit["m"] is None:
                reasons.append("NO_NORMALIZATION")
            elif not slope_ok:
                reasons.append("SLOPE")
            qcs = []
            for qm in W["qc_order"]:
                if qm == dm or e not in cfg["qc_tol"].get(qm, {}):
                    continue
                vals = [corr[(sid, r["tray"], e)][1]["d4"] for r in meas if r["material"] == qm and corr[(sid, r["tray"], e)][1]["d4"] is not None]
                if not vals:
                    continue
                mean = _Gq(_Gmean(vals), 3)
                assigned = _Gfrac(W["qc_assigned"][qm][0 if e == "N" else 1])
                dev = mean - assigned
                ok = abs(dev) <= _Gfrac(cfg["qc_tol"][qm][e])
                qcs.append({"material": qm, "n": len(vals), "mean": mean, "assigned": assigned, "dev": dev, "tol": _Gfrac(cfg["qc_tol"][qm][e]),
                            "pass": ok})
                if not ok:
                    reasons.append("QC:" + qm)
            leak = sid in W["leak_fail"]
            if leak:
                reasons.append("LEAK")
            computed = "ACCEPT" if not reasons else "REJECT"
            rl = W["ruling_effect"].get((sid, e))
            decision = rl["action"] if rl else computed
            acc[(sid, e)] = {"slope_ok": slope_ok, "qcs": qcs, "leak": leak, "computed": computed, "ruling": rl["id"] if rl else "",
                             "decision": decision, "reasons": reasons}
    S.update({"drift": drift, "blank": blank, "norm": norm, "elem": elem, "acc": acc, "corr": corr})
    # ---- samples
    res, screen = {}, []
    for smp in W["scope"]:
        for e in els:
            req = W["requested"].get(smp, "N+C")
            if e not in req.split("+"):
                res[(smp, e)] = {"status": "NOT_REQUESTED"}
                continue
            vals = []
            for (sid, tray, ee), (r, w) in corr.items():
                if ee == e and r["material"] == smp and w["d4"] is not None and acc[(sid, e)]["decision"] == "ACCEPT":
                    vals.append((S["t1"][sid], tray, w["d4"], w["pct"]))
            vals.sort(key=lambda t: (t[0], t[1]))
            live = list(vals)
            removed = []
            while len(live) >= 3:
                xs = [v[2] for v in live]
                mu = _Gmean(xs)
                var = sum(((x - mu) ** 2 for x in xs), _GF(0)) / (len(xs) - 1)
                if var == 0:
                    break
                dev = [abs(x - mu) for x in xs]
                j = max(range(len(xs)), key=lambda i: (dev[i], -i))
                gc = _Gfrac(W["grubbs"][len(xs)][cfg["alpha"]])
                if dev[j] ** 2 > gc * gc * var:
                    removed.append({"value": xs[j], "g": _Gsqrt_dec(dev[j] ** 2 / var, 4), "g_crit": W["grubbs"][len(xs)][cfg["alpha"]], "n": len(xs)})
                    live.pop(j)
                else:
                    break
            n = len(live)
            out = {"n": n, "status": "REPORTED" if n >= 2 else "SINGLE" if n == 1 else "NO_DATA"}
            if n:
                xs = [v[2] for v in live]
                out["mean"] = _Gq(_Gmean(xs), 2)
                if n >= 2:
                    mu = _Gmean(xs)
                    out["sd"] = _Gsqrt_dec(sum(((x - mu) ** 2 for x in xs), _GF(0)) / (n - 1), 2)
                ps = [v[3] for v in live if v[3] is not None]
                out["pct"] = _Gq(_Gmean(ps), 2) if ps else None
            res[(smp, e)] = out
            if vals:
                screen.append({"sample": smp, "element": e, "initial_n": len(vals), "values": [v[2] for v in vals], "removed": removed, "final_n": n})
    S["res"], S["screen"] = res, screen
    return S
# ============================================================================ rendering
class _GNum(str):
    """Marker: a JSON number whose exact decimal text is the string value."""


def _GN(x, dp):
    return None if x is None else _GNum(_Gs(x, dp))


def _Gjson_text(o) -> str:
    if o is None:
        return "null"
    if isinstance(o, bool):
        return "true" if o else "false"
    if isinstance(o, _GNum):
        return str(o)
    if isinstance(o, int):
        return str(o)
    if isinstance(o, str):
        return _Gjson.dumps(o)
    if isinstance(o, list):
        return "[" + ", ".join(_Gjson_text(x) for x in o) + "]"
    if isinstance(o, dict):
        return "{" + ", ".join(_Gjson.dumps(k) + ": " + _Gjson_text(v) for k, v in o.items()) + "}"
    raise TypeError(type(o))


def _Gtab(header, rows, sep) -> str:
    buf = _Gio.StringIO()
    w = _Gcsv.writer(buf, delimiter=sep, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow(["" if v is None else v for v in r])
    return buf.getvalue()


def _G_cn(pc, pn):
    if pc is None or pn is None or pn == 0:
        return None
    return _Gq((pc / _Gfrac(_GMOLAR["C"])) / (pn / _Gfrac(_GMOLAR["N"])), 2)


def _G_render(W, S) -> dict:  # noqa: C901
    cfg = W["cfg"]
    els = cfg["elements"]
    eo = {e: i for i, e in enumerate(els)}
    O = {}
    led = sorted(S["ledger"], key=lambda r: (r["session"], r["counter"], eo[r["element"]]))
    O["injection_ledger.csv"] = _Gtab(
        ["session", "instrument", "counter_position", "tray_position", "material", "element", "revision", "area_vs", "amplitude_mv",
         "delta_raw", "utc_time", "run_minutes", "excluded"],
        [[r["session"], r["inst"], r["counter"], r["tray"], r["material"], r["element"], r["rev"], _Gs(r["area"], 4), r["amp"],
          _Gs(r["delta"], 3), r["utc"].strftime("%Y-%m-%dT%H:%M:%SZ"), _Gs(r["rt"], 4), r["excluded"]] for r in led], ",")
    # position resolution
    rows = []
    for sid in sorted(S["sess"]):
        s = S["sess"][sid]
        mx = W["maxc"].get(sid, 0)
        tr = {}
        for c in range(1, mx + 1):
            t = c if S.get("flip") == "skip_ignored" else c + sum(1 for q in W["skip_counters"].get(sid, []) if q <= c)
            tr[t] = c
        exc = {}
        for r in S["ledger"]:
            if r["session"] == sid and r["excluded"]:
                exc[r["tray"]] = True
        for sl in s["trays"]:
            t = sl["tray"]
            st = "SKIPPED" if t not in tr else ("EXCLUDED" if exc.get(t) else "MEASURED")
            rows.append([sid, t, tr.get(t, ""), sl["seq_token"].strip(), sl["journal_seq"] or "", sl["true"], sl["class"], sl["capsule"],
                         "" if sl.get("mass_corr") is None else _Gs(sl["mass_corr"], 4), st])
    O["position_resolution.csv"] = _Gtab(["session", "tray_position", "counter_position", "sequence_token", "journal_seq", "material",
                                          "material_class", "capsule_id", "mass_mg", "status"], rows, ",")
    O["alias_resolution.psv"] = _Gtab(["kind", "token", "canonical"], [list(x) for x in sorted(W["alias_seen"])], "|")
    d = S["dedup"]
    O["dedup_report.json"] = _Gjson_text(d) + "\n"
    O["source_lineage.json"] = _Gjson_text({"files": S["lineage"]}) + "\n"
    sess = S["sess"]
    ls = []
    for sid in sorted(s for s in sess if sess[s]["kind"] == "L"):
        for e in els:
            L = S["lin"][(sid, e)]
            ls.append({"session": sid, "instrument": sess[sid]["inst"], "local_date": S["local_date"][sid].isoformat(), "element": e,
                       "n_points": L["n"], "slope": _GN(L["k"], 6)})
    asg = []
    A = sorted(s for s in sess if sess[s]["kind"] == "A")
    for sid in A:
        for e in els:
            a = S["assign"][(sid, e)]
            asg.append({"session": sid, "element": e, "lin_session": a["lin"], "lin_slope": _GN(a["k"], 6), "applied_slope": _GN(a["applied"], 6),
                        "status": a["status"]})
    O["linearity_slopes.json"] = _Gjson_text({"lin_sessions": ls, "assignments": asg}) + "\n"
    O["drift_fits.tsv"] = _Gtab(["session", "element", "drift_material", "n_points", "slope_per_min", "anchor_min", "status"],
                                [[sid, e, cfg["drift_material"], S["drift"][(sid, e)]["n"], _Gs(S["drift"][(sid, e)]["slope"], 8),
                                  _Gs(S["drift"][(sid, e)]["anchor"], 4), S["drift"][(sid, e)]["status"]] for sid in A for e in els], "\t")
    O["blank_corrections.psv"] = _Gtab(["session", "element", "n_blanks", "n_rejected", "mean_area_vs", "mean_delta"],
                                       [[sid, e, S["blank"][(sid, e)]["n"], S["blank"][(sid, e)]["rej"], _Gs(S["blank"][(sid, e)]["Ab"], 4),
                                         _Gs(S["blank"][(sid, e)]["db"], 3)] for sid in A for e in els], "|")
    fits = []
    for sid in A:
        for e in els:
            f = S["norm"][(sid, e)]
            fits.append({"session": sid, "element": e, "reference_set": f["set"], "n_points": f["n"], "fits": f["fits"], "slope": _GN(f["m"], 6),
                         "intercept": _GN(f["b"], 6),
                         "removed": [{"tray_position": x["tray"], "material": x["material"], "residual": _GN(x["residual"], 4)} for x in f["removed"]],
                         "status": f["status"]})
    O["normalization_fits.json"] = _Gjson_text({"fits": fits}) + "\n"
    lines = []
    for (sid, tray, e) in sorted(S["corr"], key=lambda k: (k[0], k[1], eo[k[2]])):
        r, w = S["corr"][(sid, tray, e)]
        lines.append(_Gjson_text({"session": sid, "tray_position": tray, "material": r["material"], "material_class": r["class"], "element": e,
                                  "d_lin": _GN(w["d1"], 4), "d_drift": _GN(w["d2"], 4), "d_blank": _GN(w["d3"], 4), "d_norm": _GN(w["d4"], 3),
                                  "pct": _GN(w["pct"], 3)}))
    O["corrected_injections.jsonl"] = "".join(x + "\n" for x in lines)
    O["elemental_factors.tsv"] = _Gtab(["session", "element", "n_standards", "factor_ug_per_vs"],
                                       [[sid, e, S["elem"][(sid, e)]["n"], "" if S["elem"][(sid, e)]["K"] is None else _Gs(S["elem"][(sid, e)]["K"], 6)]
                                        for sid in A for e in els], "\t")
    rows = []
    qx = ['<?xml version="1.0" encoding="UTF-8"?>', f'<qc_results project="{cfg["project"]}">']
    for sid in A:
        for e in els:
            a = S["acc"][(sid, e)]
            f = S["norm"][(sid, e)]
            qc = ";".join(f"{q['material']}:{_Gs(q['dev'], 3)}:{'PASS' if q['pass'] else 'FAIL'}" for q in a["qcs"])
            rows.append([sid, e, sess[sid]["inst"], "" if f["m"] is None else _Gs(f["m"], 6), "Y" if a["slope_ok"] else "N", qc,
                         "Y" if a["leak"] else "N", a["computed"], a["ruling"], a["decision"], ";".join(a["reasons"])])
            for q in a["qcs"]:
                qx.append(f'  <check session="{sid}" element="{e}" material="{q["material"]}" n="{q["n"]}" mean="{_Gs(q["mean"], 3)}" '
                          f'assigned="{_Gs(q["assigned"], 2)}" deviation="{_Gs(q["dev"], 3)}" tolerance="{_Gs(q["tol"], 2)}" '
                          f'result="{"PASS" if q["pass"] else "FAIL"}"/>')
    qx.append("</qc_results>")
    O["session_acceptance.csv"] = _Gtab(["session", "element", "instrument", "norm_slope", "slope_ok", "qc_checks", "leak", "computed", "ruling",
                                         "decision", "reasons"], rows, ",")
    O["qc_results.xml"] = "\n".join(qx) + "\n"
    rows = []
    for smp in sorted(W["scope"]):
        rN, rC = S["res"][(smp, "N")], S["res"][(smp, "C")]

        def cells(r):
            if r["status"] == "NOT_REQUESTED":
                return ["", "", "", "", "NOT_REQUESTED"]
            return ["" if r.get("mean") is None else _Gs(r["mean"], 2), r.get("sd", ""), r["n"],
                    "" if r.get("pct") is None else _Gs(r["pct"], 2), r["status"]]
        cn = None
        if rN["status"] in ("REPORTED", "SINGLE") and rC["status"] in ("REPORTED", "SINGLE"):
            cn = _G_cn(rC.get("pct"), rN.get("pct"))
        rows.append([smp] + cells(rN) + cells(rC) + ["" if cn is None else _Gs(cn, 2)])
    O["isotope_results.csv"] = _Gtab(["sample_id", "d15N_air", "d15N_sd", "n_N", "pct_N", "status_N", "d13C_vpdb", "d13C_sd", "n_C", "pct_C",
                                     "status_C", "cn_molar"], rows, ",")
    sc = sorted(S["screen"], key=lambda x: (x["sample"], eo[x["element"]]))
    O["replicate_screening.jsonl"] = "".join(_Gjson_text({"sample": x["sample"], "element": x["element"], "initial_n": x["initial_n"],
                                                          "values": [_GN(v, 3) for v in x["values"]],
                                                          "removed": [{"value": _GN(r["value"], 3), "g": _GNum(r["g"]), "g_crit": _GNum(r["g_crit"]),
                                                                       "n": r["n"]} for r in x["removed"]],
                                                          "final_n": x["final_n"]}) + "\n" for x in sc)
    O["parameters_used.yaml"] = "".join(f"{k}: {v}\n" for k, v in _G_params(W))
    # published comparisons
    rows = []
    pub = W["published"]
    keys = sorted(set(pub) | {k for k, v in S["res"].items() if v["status"] in ("REPORTED", "SINGLE")}, key=lambda k: (k[0], eo[k[1]]))
    for k in keys:
        a = pub.get(k)
        r = S["res"].get(k, {})
        b = r.get("mean") if r.get("status") in ("REPORTED", "SINGLE") else None
        if a is None and b is None:
            continue
        if a is None:
            rows.append([k[0], k[1], "", _Gs(b, 2), "", "ONLY_RECOMPUTED"])
        elif b is None:
            rows.append([k[0], k[1], _Gs(a, 2), "", "", "ONLY_PUBLISHED"])
        else:
            dlt = b - a
            rows.append([k[0], k[1], _Gs(a, 2), _Gs(b, 2), _Gs(dlt, 2), "MATCH" if abs(dlt) <= _GF(5, 100) else "DIFF"])
    O["variance_vs_published.csv"] = _Gtab(["sample_id", "element", "published", "recomputed", "diff", "status"], rows, ",")
    sp = []
    for (sid, e), (m, b) in sorted(W["pub_params"].items(), key=lambda kv: (kv[0][0], eo[kv[0][1]])):
        f = S["norm"].get((sid, e), {})
        rm, rb = f.get("m"), f.get("b")
        sp.append({"session": sid, "element": e, "published_slope": _GN(m, 6), "recomputed_slope": _GN(rm, 6), "published_intercept": _GN(b, 6),
                   "recomputed_intercept": _GN(rb, 6), "slope_diff": None if rm is None else _GN(rm - m, 6),
                   "intercept_diff": None if rb is None else _GN(rb - b, 6), "published_points": W["pub_points"].get((sid, e), 0),
                   "recomputed_points": f.get("n") if rm is not None else None})
    O["session_param_diff.json"] = _Gjson_text({"sessions": sp}) + "\n"
    rows = []
    for (sid, e), st in sorted(W["dash_status"].items(), key=lambda kv: (kv[0][0], eo[kv[0][1]])):
        dec = S["acc"][(sid, e)]["decision"]
        rows.append([sid, e, st, dec, "Y" if (st == "PASS") == (dec == "ACCEPT") else "N"])
    O["dashboard_disagreements.csv"] = _Gtab(["session", "element", "dashboard_status", "recomputed_decision", "agrees"], rows, ",")
    lines = []
    for (smp, e), v in sorted(W["cache"].items(), key=lambda kv: (kv[0][0], eo[kv[0][1]])):
        r = S["res"].get((smp, e), {})
        b = r.get("mean") if r.get("status") in ("REPORTED", "SINGLE") else None
        st = "STALE" if b is None or abs(b - v) > _GF(5, 100) else "CURRENT"
        lines.append(_Gjson_text({"sample": smp, "element": e, "cached": _GN(v, 2), "recomputed": _GN(b, 2), "status": st}))
    O["cache_divergence.jsonl"] = "".join(x + "\n" for x in lines)
    O["reconciliation.md"] = _G_recon_md(W, S, rows=O)
    return O


def _G_params(W):
    cfg = W["cfg"]
    kv = [("project", cfg["project"]), ("rm_sheet", cfg["rm_sheet"]), ("normalization_table", "N-2")]
    for e in cfg["elements"]:
        kv += [(f"reference_set_{e}", ",".join(cfg["sets"][e])), (f"reject_limit_{e}", cfg["reject_limit"][e]), (f"max_reject_{e}", cfg["max_reject"][e]),
               (f"linearity_threshold_{e}", cfg["lin_thr"][e]), (f"a_ref_{e}", cfg["a_ref"][e]), (f"amplitude_min_{e}", cfg["amp_window"][e][0]),
               (f"amplitude_max_{e}", cfg["amp_window"][e][1]), (f"blank_area_max_{e}", cfg["blank_max"][e])]
    kv += [("slope_min", cfg["slope_window"][0]), ("slope_max", cfg["slope_window"][1]), ("linearity_lookback_days", cfg["lookback"]),
           ("drift_material", cfg["drift_material"]), ("drift_min_points", cfg["drift_min"]), ("grubbs_table", "G-1"), ("grubbs_alpha", cfg["alpha"]),
           ("molar_mass_C", _GMOLAR["C"]), ("molar_mass_N", _GMOLAR["N"]), ("date_system", "1904" if cfg["date1904"] else "1900"),
           ("clock_base_offset", _Goff_text(cfg["base_offset"]))]
    for qm in W["qc_order"]:
        if qm == cfg["drift_material"]:
            continue
        for e in _GELEMENTS:
            if e in cfg["qc_tol"].get(qm, {}):
                kv.append((f"qc_tolerance_{qm}_{e}", cfg["qc_tol"][qm][e]))
    return kv


def _G_recon_md(W, S, rows):
    cfg = W["cfg"]
    els = cfg["elements"]
    out = [f"# {cfg['project']} reconciliation", "", "## Summary", "", "| element | recomputed_reported | published_reported | compared | diff_count | mean_shift |",
           "|---|---|---|---|---|---|"]
    for e in els:
        rec = [k for k, v in S["res"].items() if k[1] == e and v["status"] in ("REPORTED", "SINGLE")]
        pub = [k for k in W["published"] if k[1] == e]
        both = [k for k in rec if k in W["published"]]
        diffs = [S["res"][k]["mean"] - W["published"][k] for k in both]
        nd = sum(1 for x in diffs if abs(x) > _GF(5, 100))
        shift = _Gs(_Gmean(diffs), 3) if diffs else ""
        out.append(f"| {e} | {len(rec)} | {len(pub)} | {len(both)} | {nd} | {shift} |")
    out += ["", "## Session decisions", "", "| session | element | computed | ruling | decision | reasons |", "|---|---|---|---|---|---|"]
    for (sid, e) in sorted(S["acc"], key=lambda k: (k[0], els.index(k[1]))):
        a = S["acc"][(sid, e)]
        if a["decision"] == "REJECT" or a["ruling"] or a["computed"] == "REJECT":
            out.append(f"| {sid} | {e} | {a['computed']} | {a['ruling']} | {a['decision']} | {';'.join(a['reasons'])} |")
    out += ["", "## Run settings", "", "| setting | published_run | in_force |", "|---|---|---|"]
    for k, v, inf in W["rerun_settings"]:
        out.append(f"| {k} | {v} | {inf} |")
    out += ["", "## Superseded notices", "", "| notice | material | lot | element | notice_value | in_force_value |", "|---|---|---|---|---|---|"]
    cert = _G_cert(W)
    for nid, mat, lot, e, val in sorted(W["rm_notices"]):
        inf = cert.get(lot)
        if inf is None:
            continue
        iv = inf[0 if e == "N" else 1]
        if _Gfrac(iv) != _Gfrac(val):
            out.append(f"| {nid} | {mat} | {lot} | {e} | {val} | {iv} |")
    return "\n".join(out) + "\n"


def _G_derive(W, flip=""):
    S = _G_compute(W, flip)
    S["flip"] = flip
    return _G_render(W, S)
# ============================================================================ tokens, records, catalog
_GLAYOUTS = [
    # id, file, family, time, area, amp, delta, element map, peak map, void tokens, decimal comma
    ("L01", "xr_07ka.csv", "csv", "local_iso", "Vs", "mV", "permil", "E1", "P1", ("V", ""), False),
    ("L02", "pm_3qd1.tsv", "tsv", "epoch_s", "mVs", "V", "permil", "E2", "P2", ("VOID", "OK"), False),
    ("L03", "ln_8vw2.psv", "psv", "local_dmy", "Vs", "mV", "permil", "E3", "P3", ("DEAD", "LIVE"), True),
    ("L04", "qh_5tb6.jsonl", "jsonl_flat", "epoch_ms", "Vs", "mV", "milli", "E3", "P3i", (True, False), False),
    ("L05", "dw_2ms9.ndjson", "ndjson_nested", "iso_off", "Vs", "mV", "permil", "E2", "P2", ("Y", "N"), False),
    ("L06", "kf_9ze4.xml", "xml_attr", "iso_z", "mVs", "mV", "permil", "E1", "P1", ("1", "0"), False),
    ("L07", "ts_4hn0.sqlite", "sqlite_split", "local_compact", "Vs", "mV", "milli", "E1", "P2", (1, 0), False),
    ("L08", "bc_6rp3.db", "sqlite_flat", "epoch_s", "Vs", "V", "permil", "E2", "P1", ("VOID", ""), False),
    ("L09", "vy_1lc8.yaml", "yaml_blocks", "iso_off", "Vs", "mV", "permil", "E1", "P2", ("true", "false"), False),
    ("L10", "gj_0px5.yml", "yml_grouped", "local_iso", "mVs", "mV", "permil", "E5", "P4", ("void", "ok"), False),
    ("L11", "ue_7fs2.json", "json_columnar", "epoch_s", "mVs", "mV", "milli", "E2", "P1", (1, 0), False),
    ("L12", "oz_3kd7.txt", "fixed", "local_compact", "Vs", "mV", "permil", "E1", "P5", ("X", "-"), False),
    ("L13", "ma_5gw1.md", "md", "iso_z", "Vs", "V", "permil", "E3", "P2", ("VOID", ""), False),
    ("L14", "rk_2bn4.csv", "csv_semi", "local_dmy_slash", "Vs", "mV", "permil", "E2", "P1", ("V", ""), True),
    ("L15", "hx_8yq0.tsv", "tsv_wide", "epoch_ms", "Vs", "mV", "permil", "", "", ("1", ""), False),
    ("L16", "cp_6jm3.jsonl", "jsonl_nested", "iso_z", "Vs", "mV", "ratio", "E1", "P2", (True, False), False),
    ("L17", "wq_4ld0.csv", "csv_comment", "iso_off", "mVs", "V", "permil", "E4", "P3", ("1", "0"), False),
    ("L18", "jn_9ks2.psv", "psv", "epoch_ms", "mVs", "mV", "milli", "E4", "P5", ("Y", "N"), False),
    ("L19", "fe_2vb7.xml", "xml_child", "local_t", "Vs", "mV", "milli", "E5", "P4", ("true", "false"), False),
    ("L20", "sz_5pt3.ndjson", "ndjson_flat", "basic_z", "Vs", "V", "permil", "E1", "P1", ("void", "ok"), False),
    ("L21", "rd_1mx6.sqlite", "sqlite_runlog", "iso_off", "mVs", "mV", "permil", "E1", "P2", ("VOID", ""), False),
    ("L22", "nl_7cy8.db", "sqlite_eav", "epoch_s", "Vs", "mV", "permil", "E2", "P1", ("1", "0"), False),
]
_GFIELDS = {
    "L01": ["proj", "seq", "inst", "pos", "gas", "ptype", "rev", "void", "t_local", "area_vs", "amp_mv", "d_permil"],
    "L02": ["Project", "Sequence", "Line", "Counter", "Species", "PeakKind", "Revision", "Status", "EpochS", "Area_mVs", "Amp_V", "dRaw"],
    "L03": ["projekt", "lauf", "geraet", "position", "isotop", "peaktyp", "revision", "zustand", "zeit", "flaeche_vs", "amplitude_mv", "delta"],
    "L04": ["prj", "run", "ln", "slot", "el", "pk", "rv", "void", "ts_ms", "a", "amp", "dm"],
    "L08": ["project", "sequence", "instrument", "counter", "gas", "peaktype", "revision", "void_flag", "epoch", "area", "amplitude", "delta"],
    "L11": ["project", "sequence", "instrument", "counter", "species", "peak", "revision", "void", "epoch_s", "area_mvs", "amp_mv", "d_milli"],
    "L12": ["PROJECT", "SEQUENCE", "INST", "POS", "GAS", "PT", "REV", "VOID", "TIME", "AREA_VS", "AMP_MV", "D_PERMIL"],
    "L13": ["project", "sequence", "instrument", "position", "isotope", "peak", "rev", "void", "time_utc", "area_vs", "amp_v", "delta"],
    "L14": ["Projekt", "Sequenz", "Geraet", "Pos", "Element", "Typ", "Rev", "Void", "Zeit", "Flaeche", "Amplitude", "Delta"],
    "L17": ["rev", "void", "mass", "peak", "counter", "sequence", "project", "instrument", "ts", "area_mvs", "amp_v", "d"],
    "L18": ["PRJ", "SEQ", "INST", "CTR", "MZ", "PT", "REV", "VD", "EPOCHMS", "AREA_MVS", "AMP_MV", "D_MILLI"],
    "L19": ["project", "sequence", "instrument", "counter", "species", "kind", "revision", "void", "time", "area_vs", "amp_mv", "d_milli"],
    "L20": ["PROJ", "SEQ", "INST", "POS", "GAS", "PT", "REV", "STATUS", "TS", "AREA", "AMP_V", "DELTA"],
    "L22": ["project", "seq", "inst", "pos", "el", "type", "rev", "void", "t", "area", "amp", "d"],
}
_GEMAP = {"E1": {"N": "N2", "C": "CO2"}, "E2": {"N": "N", "C": "C"}, "E3": {"N": "15N", "C": "13C"}, "E4": {"N": "28", "C": "44"},
          "E5": {"N": "nitrogen", "C": "carbon"}}
_GPMAP = {"P1": {"S": "S", "R": "R"}, "P2": {"S": "SAMPLE", "R": "REF"}, "P3": {"S": "1", "R": "0"}, "P3i": {"S": 1, "R": 0},
          "P4": {"S": "analyte", "R": "reference"}, "P5": {"S": "PK", "R": "RG"}}
_GLOCAL = {"local_iso", "local_dmy", "local_dmy_slash", "local_compact", "local_t"}
_GWIDTHS = [10, 14, 9, 5, 5, 4, 4, 5, 16, 11, 7, 9]


def _G_sess_tokens(sid: str, inst: str) -> list:
    kind, num, n = sid.split("-")
    if kind == "SQ":
        return [sid, f"SQ{num}-{n}", f"sq-{num}-{int(n)}", f"{num}/{n}", f"SQ-{n}", f"RUN-{inst}-{num[2:]}{n}"]
    return [sid, f"LN{num}-{n}", f"lin-{num}-{int(n)}", f"{num}/L{n}", f"LN-{n}", f"LINRUN-{inst}-{num[2:]}{n}"]


def _G_aliases(W, rng):
    """Alias register rows (token, canonical, project, valid_from) with chains and project scope."""
    cfg = W["cfg"]
    sess_rows, inst_rows, mat_rows = [], [], []
    for s in W["sessions"]:
        t = _G_sess_tokens(s["id"], s["inst"])
        sess_rows.append((t[1], s["id"], "*"))
        sess_rows.append((t[2].upper(), s["id"], "*"))
        sess_rows.append((t[3], s["id"], "*"))
        sess_rows.append((t[4], s["id"], s["project"]))
        sess_rows.append((t[5], t[1], "*"))
    for k, toks in (("K1", ["IRMS-K1", "K-1", "LINE-A"]), ("K2", ["IRMS-K2", "K-2", "LINE-B"])):
        inst_rows.append((toks[0], k))
        inst_rows.append((toks[1], k))
        inst_rows.append((toks[2], toks[0]))
    early = W["pivot"] - _Gtd(days=400)
    for canon, toks in _GRM_TOKENS.items():
        for t in toks[1:]:
            tu = t.strip().upper()
            if tu == canon:
                continue
            target = canon
            if tu == "RMGL":
                target = "GLU-L"
            if tu == "RMGH":
                target = "GLU-H"
            if tu == "CND":
                target = "COND"
            mat_rows.append((tu, target, "*", early.isoformat()))
    mat_rows.append(("QCX", "QC-SED", cfg["project"], early.isoformat()))
    mat_rows.append(("QCX", "QC-MUS", cfg["project"], W["qcx_switch"].isoformat()))
    mat_rows.append(("QCX", "QC-ALG", cfg["other"], early.isoformat()))
    for smp in W["samples"]:
        mat_rows.append((smp.replace("-", ""), smp, cfg["project"], early.isoformat()))
    for smp in W["other_samples"]:
        mat_rows.append((smp.replace("-", ""), smp, cfg["other"], early.isoformat()))
    for smp in rng.sample(W["samples"], 12):
        mat_rows.append((smp.replace("-", ""), "HS-9" + smp[4:], cfg["other"], early.isoformat()))
    W["alias_rows"] = {"session": sess_rows, "instrument": inst_rows, "material": mat_rows}


def _G_resolve_material(W, token: str, project: str, day) -> str:
    t = token.strip().upper()
    canon = set(_GCLASS) | set(W["samples"]) | set(W["other_samples"])
    for _ in range(12):
        if t in canon:
            return t
        rows = [r for r in W["alias_rows"]["material"] if r[0] == t and r[2] in ("*", project) and _Gdate.fromisoformat(r[3]) <= day]
        if not rows:
            break
        t = max(rows, key=lambda r: r[3])[1]
    cid = {v: k for k, v in W["client_id"].items()}
    return cid.get(t, "")


def _G_note_alias(W, kind, token, canon):
    t = str(token).strip().upper()
    if t != canon:
        W["alias_seen"].add((kind, t, canon))


def _G_emit(W, rng):  # noqa: C901
    """Build every shard record, the catalog and the processing order."""
    cfg = W["cfg"]
    proj = cfg["project"]
    A = [s for s in W["sessions"] if s["kind"] == "A"]
    L = [s for s in W["sessions"] if s["kind"] == "L"]
    O = [s for s in W["sessions"] if s["kind"] == "O"]
    clock = W["clock"]
    lay = {x[0]: x for x in _GLAYOUTS}
    cap = {x[0]: 1 for x in _GLAYOUTS}
    cap["L15"], cap["L13"], cap["L19"] = 3, 0, 0
    second = {s["id"] for s in A if any(_Gis_ambiguous_second(ij["utc"], clock) for ij in s["inj"])}
    primary = {}
    order = list(A)
    rng.shuffle(order)
    spec = [s for s in A if s["inst"] == "K1" and (s["start_wall"].date() - W["pivot"]).days == -1]
    for s in spec + [x for x in order if x not in spec]:
        if s in spec and s["id"] not in second:
            ok = ["L01"]
        else:
            ok = [l for l in cap if cap[l] > 0 and not (s["id"] in second and lay[l][3] in _GLOCAL)]
        ok = [l for l in ok if cap[l] > 0]
        l = ok[0] if s in spec else rng.choice(ok)
        cap[l] -= 1
        primary[s["id"]] = l
    lin_l = ["L13", "L13", "L19", "L19"] + rng.sample([x[0] for x in _GLAYOUTS if x[0] not in ("L13", "L19", "L15")], 12)
    for s, l in zip(L, lin_l):
        primary[s["id"]] = l
    for s, l in zip(O, ["L13", "L19", "L15", "L15", "L16", "L16"]):
        primary[s["id"]] = l
    W["primary"] = primary
    # records
    recs = {x[1]: [] for x in _GLAYOUTS}
    recs["ab_0re7.csv"] = []
    recs["mv_full_export.csv"] = []
    seg_tok = {}

    def tok_for(s, f):
        key = (s["id"], f)
        if key not in seg_tok:
            toks = _G_sess_tokens(s["id"], s["inst"])
            seg_tok[key] = rng.choice(toks)
        return seg_tok[key]

    itoks = {"K1": ["K1", "IRMS-K1", "k-1", "LINE-A"], "K2": ["K2", "IRMS-K2", "k-2", "LINE-B"]}
    W["alias_seen"] = set()

    def inj_records(s, f, stale=False, rev0=False, subset=None):
        out = []
        st = tok_for(s, f)
        it = rng.choice(itoks[s["inst"]])
        for ij in s["inj"]:
            if subset is not None and ij["counter"] not in subset:
                continue
            grp = []
            for e in _GELEMENTS:
                pk = ij["peaks"][e]
                if (not stale or cfg["stale_refs"]) and f != "mv_full_export.csv":
                    for _ in range(rng.choice((1, 1, 2))):
                        grp.append({"project": s["project"], "session": s["id"], "tok": st, "itok": it, "counter": ij["counter"], "element": e,
                                    "ptype": "R", "rev": 0, "void": False, "utc": ij["utc"], "area": _Gq(_GF(rng.uniform(18, 22)), 4),
                                    "amp": rng.randint(1900, 3900), "delta": _Gq(_GF(rng.gauss(0, 0.02)), 3)})
                revs = pk["revs"][:1] if (rev0 or stale or s["kind"] == "O") else pk["revs"]
                for rv in revs:
                    area, delta = rv["area"], rv["delta"]
                    if stale:
                        area = _Gq(area * _GF(1 + rng.uniform(-0.02, 0.02)), 4)
                        delta = _Gq(delta + _GF(rng.uniform(-0.25, 0.25)), 3)
                    grp.append({"project": s["project"], "session": s["id"], "tok": st, "itok": it, "counter": ij["counter"], "element": e,
                                "ptype": "S", "rev": rv["rev"], "void": rv["void"] if not stale else False, "utc": ij["utc"], "area": area,
                                "amp": rv["amp"], "delta": delta})
            out += grp
        return out

    for s in A + L + O:
        f = lay[primary[s["id"]]][1]
        recs[f] += [r for r in inj_records(s, f) if not (f == "hx_8yq0.tsv" and r["ptype"] == "R")]
    # overlap duplicates in another file with an active segment
    dup_src = rng.sample(A, 3)
    W["dup_segments"] = []
    for s in dup_src:
        cands = [x[1] for x in _GLAYOUTS if x[1] != lay[primary[s["id"]]][1] and not (s["id"] in second and x[3] in _GLOCAL)]
        f = "fe_2vb7.xml" if (s is dup_src[0] and s["id"] not in second and "fe_2vb7.xml" in cands) else rng.choice(cands)
        sub = set(rng.sample([ij["counter"] for ij in s["inj"]], len(s["inj"]) // 5))
        recs[f] += [dict(r) for r in inj_records(s, f, subset=sub) if r["ptype"] == "S"]
        W["dup_segments"].append((f, s["id"]))
    # stale copies under retired segments
    stale_src = rng.sample([s for s in A if s not in dup_src], 3)
    W["stale_segments"] = []
    for i, s in enumerate(stale_src):
        cands = [x[1] for x in _GLAYOUTS if x[1] != lay[primary[s["id"]]][1] and not (s["id"] in second and x[3] in _GLOCAL)]
        f = "ma_5gw1.md" if i == 0 else rng.choice(cands)
        recs[f] += [r for r in inj_records(s, f, stale=True) if not (f == "hx_8yq0.tsv" and r["ptype"] == "R")]
        W["stale_segments"].append((f, s["id"]))
    # rows of a project session never registered in that file
    s = rng.choice([x for x in A if x not in dup_src + stale_src])
    f = rng.choice([x[1] for x in _GLAYOUTS if x[1] != lay[primary[s["id"]]][1] and not (s["id"] in second and x[3] in _GLOCAL)])
    recs[f] += [r for r in inj_records(s, f, stale=True, subset=set(range(1, 9))) if not (f == "hx_8yq0.tsv" and r["ptype"] == "R")]
    # within-file duplicate rows
    for f in rng.sample([x[1] for x in _GLAYOUTS if x[2] not in ("tsv_wide",)], 2):
        k = rng.randint(20, max(21, len(recs[f]) - 10))
        recs[f][k:k] = [dict(r) for r in recs[f][k - 5:k]]
    # decoy shards
    for s in rng.sample(A, 2):
        recs["ab_0re7.csv"] += inj_records(s, "ab_0re7.csv", stale=True)
    for s in A:
        recs["mv_full_export.csv"] += inj_records(s, "mv_full_export.csv", rev0=True)
    W["recs_raw"] = recs
    # catalog events
    files = [x[1] for x in _GLAYOUTS] + ["ab_0re7.csv"]
    rng.shuffle(files)
    segs = {}
    for f in files:
        sids = []
        for r in recs[f]:
            if r["project"] == proj and r["session"] not in sids:
                sids.append(r["session"])
        segs[f] = sids
    never = (f, s["id"])
    ev = []
    t = _Gdt.combine(W["pivot"] + _Gtd(days=12), _Gdt.min.time()).replace(tzinfo=_GUTC) + _Gtd(hours=6)
    layout_of = {x[1]: x[0] for x in _GLAYOUTS}
    layout_of["ab_0re7.csv"] = "L01"
    sess_by = {s["id"]: s for s in W["sessions"]}

    def put(action, f, sid):
        nonlocal t
        t += _Gtd(minutes=rng.randint(1, 9))
        e = {"event": 0, "at": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "action": action, "file": f, "session": tok_for(sess_by[sid], "cat:" + f)}
        if action == "REGISTER":
            e["layout"] = layout_of[f]
        ev.append(e)

    retired = set(W["stale_segments"]) | {(f2, s2) for f2 in ["ab_0re7.csv"] for s2 in segs["ab_0re7.csv"]}
    for f in files:
        for sid in segs[f]:
            if (f, sid) == never:
                continue
            put("REGISTER", f, sid)
    keys = [(f, sid) for f in files for sid in segs[f] if (f, sid) != never]
    for _ in range(3):
        for f, sid in rng.sample(keys, len(keys)):
            put("VERIFY", f, sid)
    cycle = rng.sample([k for k in keys if k not in retired], 4)
    for f, sid in keys:
        if (f, sid) in retired:
            put("RETIRE", f, sid)
    for f, sid in cycle:
        put("RETIRE", f, sid)
        put("VERIFY", f, sid)
        put("REGISTER", f, sid)
    for i, e in enumerate(ev, 1):
        e["event"] = 1000 + 3 * i
    W["catalog"] = ev
    active = set()
    state = {}
    for e in ev:
        if e["action"] in ("REGISTER", "RETIRE"):
            state[(e["file"], _G_session_of(W, e["session"], proj))] = e["action"]
    for k, v in state.items():
        if v == "REGISTER":
            active.add(k)
    first = []
    for e in ev:
        if e["action"] == "REGISTER" and e["file"] not in first:
            first.append(e["file"])
    W["file_order"] = [f for f in first if any((f, sid) in active for sid in segs[f])]
    W["active"] = active
    W["layout_of"] = layout_of
    W["records"] = {f: recs[f] for f in W["file_order"]}
    # alias bookkeeping
    for f in W["file_order"]:
        for r in recs[f]:
            if r["project"] == proj and r["ptype"] == "S" and (f, r["session"]) in active:
                _G_note_alias(W, "session", r["tok"], r["session"])
                _G_note_alias(W, "instrument", r["itok"], sess_by[r["session"]]["inst"])
    W["admitted"] = {(s["id"], ij["counter"], e, r) for s in W["sessions"] for ij in s["inj"] for e in _GELEMENTS
                     for r in ij["peaks"][e]["admitted"] if r > 0}
    W["maxc"] = {s["id"]: max(ij["counter"] for ij in s["inj"]) for s in W["sessions"]}
    W["t1"] = {s["id"]: s["t1"] for s in W["sessions"]}


def _G_session_of(W, token, project):
    t = token.strip().upper()
    ids = {s["id"] for s in W["sessions"]}
    rows = W["alias_rows"]["session"]
    for _ in range(10):
        if t in ids:
            return t
        nxt = [r[1] for r in rows if r[0] == t and r[2] in ("*", project)]
        if not nxt:
            return ""
        t = nxt[0].upper()
    return ""
# ============================================================================ finishing the world, decoys
def _G_finish(W, rng):  # noqa: C901
    cfg = W["cfg"]
    proj = cfg["project"]
    W["exclude_codes"] = {c for c, _, st in _GFLAG_CODES if st == "EXCLUDE"}
    W["qc_order"] = ["QC-SED", "QC-MUS", "QC-ALG"]
    W["qc_assigned"] = _GQC_ASSIGNED
    W["elm_comp"] = _GELM
    g = {}
    for n in range(3, 141):
        g[n] = {"0.05": f"{_G_grubbs(n, 0.05):.4f}", "0.01": f"{_G_grubbs(n, 0.01):.4f}"}
    W["grubbs"] = g
    W["grubbs_one"] = {n: (f"{_G_grubbs(n, 0.05, False):.4f}", f"{_G_grubbs(n, 0.01, False):.4f}") for n in range(3, 61)}
    # ruling effects (latest in-force ACCEPT/REJECT per session element)
    eff = {}
    for r in sorted(W["rulings"], key=lambda r: (r["date"], r["id"])):
        if r["project"] != proj or r["status"] != "IN FORCE" or r["action"] == "EXCLUDE_POSITION":
            continue
        sid = r["target"]
        if sid not in {s["id"] for s in W["sessions"] if s["kind"] == "A"}:
            continue
        for e in (_GELEMENTS if r["element"] == "ALL" else [r["element"]]):
            eff[(sid, e)] = {"id": r["id"], "action": "ACCEPT" if r["action"] == "ACCEPT_SESSION" else "REJECT"}
    W["ruling_effect"] = eff
    # autosampler skip counters
    W["skip_counters"] = {}
    for s in W["sessions"]:
        cs = []
        for i, t in enumerate(sorted(s["jams"])):
            cs.append(t - i)
        if cs:
            W["skip_counters"][s["id"]] = cs
    # client requests
    req, eff_req = [], {}
    rid = [rng.randint(5000, 5100)]
    P = W["pivot"]

    def rq(ref, els, status, when):
        rid[0] += rng.randint(1, 3)
        req.append({"id": f"RQ-{rid[0]}", "ref": ref, "elements": els, "status": status, "date": when})

    for smp in W["samples"] + W["other_samples"]:
        ref = smp if rng.random() < 0.7 else W["client_id"][smp]
        u = rng.random()
        final = "N+C" if u < 0.78 else ("N" if u < 0.89 else "C")
        when = P - _Gtd(days=rng.randint(20, 60))
        if rng.random() < 0.18:
            rq(ref, rng.choice(["N", "C", "N+C"]), "SUPERSEDED", when - _Gtd(days=5))
        if rng.random() < 0.08:
            rq(ref, "N+C", "CANCELLED", when - _Gtd(days=2))
        rq(ref, final, "ACTIVE", when)
        if cfg["request_tie"] and smp in W["scope"][:6]:
            final = "C" if final != "C" else "N+C"
            rq(smp, final, "ACTIVE", when)
        if rng.random() < 0.06:
            alt = "N" if final == "N+C" else "N+C"
            rq(smp, alt, "ACTIVE", when + _Gtd(days=3))
            final = alt
        eff_req[smp] = final
    rng.shuffle(req)
    W["requests"] = req
    W["requested"] = eff_req
    # journal padding: confirmations, other fields, other project
    J = W["journal"]
    seq = max(e["seq"] for e in J)
    A = [s for s in W["sessions"] if s["kind"] == "A"]
    touched = {(e["session"], e["tray"]) for e in J}
    for s, sl in rng.sample([(s, sl) for s in A for sl in s["trays"] if (s["id"], sl["tray"]) not in touched and sl["class"] != "COND"], 70):
        seq += rng.randint(1, 4)
        J.append({"seq": seq, "project": proj, "session": s["id"], "tray": sl["tray"], "field": "token", "value": sl["true"], "action": "SET",
                  "status": "POSTED", "reverses": None})
        sl["journal_seq"] = seq
        touched.add((s["id"], sl["tray"]))
    for s, sl in rng.sample([(s, sl) for s in A for sl in s["trays"]], 55):
        seq += rng.randint(1, 4)
        J.append({"seq": seq, "project": proj, "session": s["id"], "tray": sl["tray"], "field": rng.choice(["capsule_note", "weigh_comment"]),
                  "value": rng.choice(["recrimped", "label smudged", "rechecked"]), "action": "SET", "status": "POSTED", "reverses": None})
    O = [s for s in W["sessions"] if s["kind"] == "O"]
    for _ in range(25):
        s = rng.choice(O)
        seq += rng.randint(1, 4)
        J.append({"seq": seq, "project": cfg["other"], "session": s["id"], "tray": rng.randint(1, 20), "field": "token",
                  "value": rng.choice(W["other_samples"]), "action": "SET", "status": "POSTED", "reverses": None})
    for i in range(cfg["extra_journal"]):
        s = rng.choice(A)
        sl = rng.choice([x for x in s["trays"] if x["class"] == "SAMPLE" and x["true"] in W["samples"]])
        new = rng.choice([x for x in W["samples"] if x != sl["true"]])
        seq += rng.randint(1, 4)
        J.append({"seq": seq, "project": proj, "session": s["id"], "tray": sl["tray"], "field": "token", "value": new, "action": "SET",
                  "status": "POSTED", "reverses": None})
        u = rng.random()
        if u < 0.3:
            seq += rng.randint(1, 4)
            J.append({"seq": seq, "project": proj, "session": s["id"], "tray": sl["tray"], "field": "token", "value": "", "action": "REVERSE",
                      "status": "POSTED", "reverses": seq - 0})
            J[-1]["reverses"] = J[-2]["seq"]
        else:
            if u < 0.5:
                a = seq
                seq += rng.randint(1, 4)
                J.append({"seq": seq, "project": proj, "session": s["id"], "tray": sl["tray"], "field": "token", "value": "", "action": "REVERSE",
                          "status": "POSTED", "reverses": a})
                seq += rng.randint(1, 4)
                J.append({"seq": seq, "project": proj, "session": s["id"], "tray": sl["tray"], "field": "token", "value": "", "action": "REVERSE",
                          "status": "POSTED", "reverses": seq - 0})
                J[-1]["reverses"] = J[-2]["seq"]
                sl["journal_seq"] = a
            else:
                sl["journal_seq"] = seq
            sl["true"] = new
    rng.shuffle(J)


def _G_decoys(W, S, rng):  # noqa: C901
    cfg = W["cfg"]
    els = cfg["elements"]
    pub = {}
    for (smp, e), r in sorted(S["res"].items()):
        if r["status"] not in ("REPORTED", "SINGLE"):
            if r["status"] == "NO_DATA" or rng.random() < 0.3:
                continue
            base = _GF(rng.uniform(-1, 14) if e == "N" else rng.uniform(-31, -12))
        else:
            if rng.random() < 0.04:
                continue
            base = r["mean"]
        bias = rng.uniform(0.06, 0.32) if e == "N" else rng.choice((-1, 1)) * rng.uniform(0.03, 0.18)
        v = _Gq(base + _GF(bias), 2)
        if v == r.get("mean"):
            v += _GF(1, 100)
        pub[(smp, e)] = v
    W["published"] = pub
    cache = {}
    for k, v in sorted(pub.items()):
        if rng.random() < 0.82:
            c = _Gq(v + _GF(rng.uniform(-0.04, 0.04)), 2)
            if c == S["res"].get(k, {}).get("mean"):
                c += _GF(2, 100)
            cache[k] = c
    W["cache"] = cache
    pp, pts = {}, {}
    for (sid, e), f in sorted(S["norm"].items()):
        if f["m"] is None:
            continue
        pp[(sid, e)] = (_Gq(f["m"] + _GF(rng.uniform(-0.004, 0.004)), 6), _Gq(f["b"] + _GF(rng.uniform(-0.12, 0.12)), 6))
        pts[(sid, e)] = max(4, f["n"] + rng.choice((-1, 0, 1, 1, 2)))
    W["pub_params"] = pp
    W["pub_points"] = pts
    # dashboard status per session element
    dash = {}
    for (sid, e), a in sorted(S["acc"].items()):
        st = "PASS" if a["decision"] == "ACCEPT" else "FAIL"
        if rng.random() < 0.18:
            st = "FAIL" if st == "PASS" else "PASS"
        dash[(sid, e)] = st
    W["dash_status"] = dash
    # notices with RM values
    cert = _G_cert(W)
    notes = []
    lots = sorted(cert)
    for i in range(12):
        lot = lots[i % len(lots)]
        mat = next(m for m, ls in _GLOTS.items() if lot in ls)
        e = rng.choice(els)
        base = cert[lot][0 if e == "N" else 1]
        val = base if i % 4 == 0 else _Gs(_Gfrac(base) + _GF(rng.choice((-1, 1)) * rng.randint(1, 9), 100), 2)
        notes.append((f"NB-{2000 + 17 * i + rng.randint(0, 9)}", mat, lot, e, val))
    W["rm_notices"] = notes
    params = dict(_G_params(W))
    W["rerun_settings"] = [
        ("rm_sheet", "RM_Certified_DRAFT", params["rm_sheet"]),
        ("normalization_table", "N-1", "N-2"),
        ("reference_set_N", ",".join(cfg["withdrawn_sets"]["N"]), ",".join(cfg["sets"]["N"])),
        ("reference_set_C", ",".join(cfg["withdrawn_sets"]["C"]), ",".join(cfg["sets"]["C"])),
        ("grubbs_table", "G-0", "G-1"),
        ("drift_axis", "counter_position", "run_minutes"),
        ("linearity_partition", "session", "instrument_local_day"),
        ("correction_order", "blank,linearity,drift,normalization", "linearity,drift,blank,normalization"),
        ("revision_rule", "latest_revision", "audit_admitted"),
        ("autosampler_skips", "ignored", "applied"),
        ("session_rulings", "dashboard", "R-1_in_force"),
        ("arithmetic", "binary_float_round_at_end", "exact_decimal_stage_rounding"),
    ]
# ============================================================================ shard writers
def _G_write(path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def _G_time(u, fmt, clock):
    if fmt in _GLOCAL:
        w = _Gutc_to_wall(u, clock)
        return w.strftime({"local_iso": "%Y-%m-%d %H:%M:%S", "local_dmy": "%d.%m.%Y %H:%M:%S", "local_dmy_slash": "%d/%m/%Y %H:%M:%S",
                           "local_compact": "%Y%m%d%H%M%S", "local_t": "%Y-%m-%dT%H:%M:%S"}[fmt])
    if fmt == "epoch_s":
        return int(u.timestamp())
    if fmt == "epoch_ms":
        return int(u.timestamp()) * 1000
    if fmt == "iso_z":
        return u.strftime("%Y-%m-%dT%H:%M:%SZ")
    if fmt == "basic_z":
        return u.strftime("%Y%m%dT%H%M%SZ")
    w = _Gutc_to_wall(u, clock)
    return w.strftime("%Y-%m-%dT%H:%M:%S") + _Goff_text(_Goffset_at(u, clock))


def _G_vals(r, L, clock):
    lid, _f, fam, tf, au, mu, dm, em, pm, vt, comma = L
    area = _Gs(r["area"], 4) if au == "Vs" else _Gs(r["area"] * 1000, 1)
    amp = str(r["amp"]) if mu == "mV" else _Gs(_GF(r["amp"], 1000), 3)
    if dm == "permil":
        d = _Gs(r["delta"], 3)
    elif dm == "milli":
        d = str(int(r["delta"] * 1000))
    else:
        d = _Gs(1 + r["delta"] / 1000, 6)
    if comma:
        area, amp, d = area.replace(".", ","), amp.replace(".", ","), d.replace(".", ",")
    return {"proj": r["project"], "seq": r["tok"], "inst": r["itok"], "pos": r["counter"], "el": _GEMAP[em][r["element"]] if em else r["element"],
            "pt": _GPMAP[pm][r["ptype"]] if pm else r["ptype"], "rev": r["rev"], "void": vt[0] if r["void"] else vt[1],
            "time": _G_time(r["utc"], tf, clock), "area": area, "amp": amp, "d": d}


_GKEYS = ["proj", "seq", "inst", "pos", "el", "pt", "rev", "void", "time", "area", "amp", "d"]


def _G_groups(rows):
    out = []
    for r in rows:
        k = (r["project"], r["tok"], r["itok"], r["counter"], r["utc"])
        if out and out[-1][0] == k:
            out[-1][1].append(r)
        else:
            out.append((k, [r]))
    return out


def _G_num(s):
    return _Gjson.loads(s) if _Gre.fullmatch(r"-?\d+(\.\d+)?", s) else s


def _G_flow(items):
    return "{" + ", ".join(f"{k}: {v}" for k, v in items) + "}"


def _G_write_shard(path, L, rows, clock, rng, flow=False):  # noqa: C901
    lid, fname, fam = L[0], L[1], L[2]
    V = [_G_vals(r, L, clock) for r in rows]
    F = _GFIELDS.get(lid)
    if fam in ("csv", "tsv", "psv", "csv_semi", "csv_comment"):
        sep = {"csv": ",", "tsv": "\t", "psv": "|", "csv_semi": ";", "csv_comment": ","}[fam]
        order = _GKEYS
        if lid == "L17":
            order = ["rev", "void", "el", "pt", "pos", "seq", "proj", "inst", "time", "area", "amp", "d"]
        head = F if lid != "L17" else _GFIELDS["L17"]
        text = _Gtab(head, [[v[k] for k in order] for v in V], sep)
        if fam == "csv_comment":
            text = "# instrument export, interface revision 4.2\n# one row per peak; see feed_layouts.md\n# exported for facility review\n" + text
        _G_write(path, text)
    elif fam == "fixed":
        widths = [10, 16, 9, 5, 5, 4, 4, 5, 16, 11, 7, 9]
        lines = ["".join(h.ljust(w) for h, w in zip(F, widths)).rstrip(), "".join(("-" * (w - 1)).ljust(w) for w in widths).rstrip()]
        for v in V:
            lines.append("".join(str(v[k]).ljust(w) for k, w in zip(_GKEYS, widths)).rstrip())
        _G_write(path, "\n".join(lines) + "\n")
    elif fam == "md":
        lines = [f"# Peak export {fname}", "", "Exported peak table. Times are UTC.", "", "| " + " | ".join(F) + " |", "|" + "---|" * len(F)]
        for v in V:
            lines.append("| " + " | ".join(str(v[k]) for k in _GKEYS) + " |")
        _G_write(path, "\n".join(lines) + "\n")
    elif fam == "jsonl_flat":
        out = []
        for v in V:
            o = {}
            for k, h in zip(_GKEYS, F):
                o[h] = v[k]
            o["slot"] = int(o["slot"])
            o["rv"] = int(o["rv"])
            o["a"] = _G_num(o["a"])
            o["amp"] = int(o["amp"])
            o["dm"] = int(o["dm"])
            out.append(_Gjson.dumps(o))
        _G_write(path, "\n".join(out) + "\n")
    elif fam == "ndjson_flat":
        out = []
        for v in V:
            o = {h: v[k] for k, h in zip(_GKEYS, F)}
            o["POS"], o["REV"] = int(o["POS"]), int(o["REV"])
            o["AREA"], o["AMP_V"], o["DELTA"] = _G_num(o["AREA"]), _G_num(o["AMP_V"]), _G_num(o["DELTA"])
            out.append(_Gjson.dumps(o))
        _G_write(path, "\n".join(out) + "\n")
    elif fam == "ndjson_nested":
        out = []
        for v in V:
            pad = " " if rng.random() < 0.15 else ""
            out.append(_Gjson.dumps({"meta": {"project": v["proj"], "sequence": v["seq"], "instrument": v["inst"]},
                                     "inj": {"position": int(v["pos"]), "time": v["time"]},
                                     "peak": {"gas": v["el"], "type": v["pt"], "area": pad + v["area"], "height_mv": int(v["amp"]), "delta": v["d"] + pad},
                                     "rev": int(v["rev"]), "void": v["void"]}))
        _G_write(path, "\n".join(out) + "\n")
    elif fam == "jsonl_nested":
        out = []
        for (k, grp) in [(k + (e,), [r for r in g if r["element"] == e]) for k, g in _G_groups(rows) for e in _GELEMENTS]:
            if not grp:
                continue
            vv = [_G_vals(r, L, clock) for r in grp]
            out.append(_Gjson.dumps({"project": vv[0]["proj"], "sequence": vv[0]["seq"], "instrument": vv[0]["inst"], "position": int(vv[0]["pos"]),
                                     "time": vv[0]["time"],
                                     "peaks": [{"gas": v["el"], "type": v["pt"], "rev": int(v["rev"]), "void": v["void"], "area": _G_num(v["area"]),
                                                "amp": int(v["amp"]), "ratio": v["d"]} for v in vv]}))
        _G_write(path, "\n".join(out) + "\n")
    elif fam == "json_columnar":
        cols = F
        data = []
        for v in V:
            data.append([v["proj"], v["seq"], v["inst"], int(v["pos"]), v["el"], v["pt"], int(v["rev"]), v["void"], v["time"], _G_num(v["area"]),
                         int(v["amp"]), int(v["d"])])
        body = ",\n".join("      " + _Gjson.dumps(x) for x in data)
        _G_write(path, '{\n  "export": {\n    "interface": "columnar-2",\n    "columns": ' + _Gjson.dumps(cols) + ',\n    "rows": [\n' + body + "\n    ]\n  }\n}\n")
    elif fam == "xml_attr":
        lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<export>"]
        for (k, grp) in _G_groups(rows):
            vv = [_G_vals(r, L, clock) for r in grp]
            v0 = vv[0]
            lines.append(f'  <inj project="{v0["proj"]}" seq="{v0["seq"]}" inst="{v0["inst"]}" pos="{v0["pos"]}" t="{v0["time"]}">')
            for v in vv:
                lines.append(f'    <peak el="{v["el"]}" kind="{v["pt"]}" rev="{v["rev"]}" void="{v["void"]}" area_mvs="{v["area"]}" amp_mv="{v["amp"]}" d="{v["d"]}"/>')
            lines.append("  </inj>")
        lines.append("</export>")
        _G_write(path, "\n".join(lines) + "\n")
    elif fam == "xml_child":
        lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<records>"]
        for v in V:
            lines.append("  <record>" + "".join(f"<{h}>{v[k]}</{h}>" for k, h in zip(_GKEYS, F)) + "</record>")
        lines.append("</records>")
        _G_write(path, "\n".join(lines) + "\n")
    elif fam == "yaml_blocks":
        lines = []
        for (k, grp) in _G_groups(rows):
            vv = [_G_vals(r, L, clock) for r in grp]
            v0 = vv[0]
            lines += [f"- project: {v0['proj']}", f"  sequence: {v0['seq']}", f"  instrument: {v0['inst']}", f"  position: {v0['pos']}",
                      f'  time: "{v0["time"]}"', "  peaks:"]
            for v in vv:
                if flow and rng.random() < 0.4:
                    lines.append("    - " + _G_flow([("gas", v["el"]), ("type", v["pt"]), ("revision", v["rev"]), ("void", v["void"]),
                                                    ("area_vs", v["area"]), ("amp_mv", v["amp"]), ("delta", v["d"])]))
                    continue
                lines += [f"    - gas: {v['el']}", f"      type: {v['pt']}", f"      revision: {v['rev']}", f"      void: {v['void']}",
                          f"      area_vs: {v['area']}", f"      amp_mv: {v['amp']}", f"      delta: {v['d']}"]
        _G_write(path, "\n".join(lines) + "\n")
    elif fam == "yml_grouped":
        groups = {}
        for r, v in zip(rows, V):
            groups.setdefault((v["proj"], v["seq"], v["inst"]), []).append(v)
        lines = ["export: peak-list", "sequences:"]
        for (p, sq, ins), vv in groups.items():
            lines += [f"  - sequence: {sq}", f"    project: {p}", f"    instrument: {ins}", "    peaks:"]
            for v in vv:
                if flow and rng.random() < 0.4:
                    lines.append("      - " + _G_flow([("pos", v["pos"]), ("t", '"' + str(v["time"]) + '"'), ("species", v["el"]), ("kind", v["pt"]),
                                                      ("rev", v["rev"]), ("state", v["void"]), ("area_mvs", v["area"]), ("amp_mv", v["amp"]),
                                                      ("d", v["d"])]))
                    continue
                lines += [f"      - pos: {v['pos']}", f'        t: "{v["time"]}"', f"        species: {v['el']}", f"        kind: {v['pt']}",
                          f"        rev: {v['rev']}", f"        state: {v['void']}", f"        area_mvs: {v['area']}", f"        amp_mv: {v['amp']}",
                          f"        d: {v['d']}"]
        _G_write(path, "\n".join(lines) + "\n")
        rows[:] = [r for key in groups for r in rows if (r["project"], r["tok"], r["itok"]) == key]
    elif fam == "tsv_wide":
        head = ["project", "sequence", "instrument", "counter", "epoch_ms", "rev_N", "void_N", "area_N", "amp_N", "d_N", "rev_C", "void_C", "area_C",
                "amp_C", "d_C"]
        out, order = [], []
        for (k, grp) in _G_groups(rows):
            n = [r for r in grp if r["element"] == "N"]
            c = [r for r in grp if r["element"] == "C"]
            for i in range(max(len(n), len(c))):
                row = []
                first = (n[i] if i < len(n) else c[i])
                v0 = _G_vals(first, L, clock)
                row = [v0["proj"], v0["seq"], v0["inst"], v0["pos"], v0["time"]]
                for part in (n[i] if i < len(n) else None, c[i] if i < len(c) else None):
                    if part is None:
                        row += ["", "", "", "", ""]
                    else:
                        v = _G_vals(part, L, clock)
                        row += [v["rev"], v["void"], v["area"], v["amp"], v["d"]]
                        order.append(part)
                out.append(row)
        rows[:] = order
        _G_write(path, _Gtab(head, out, "\t"))
    else:
        if path.exists():
            path.unlink()
        con = _Gsqlite3.connect(str(path))
        cur = con.cursor()
        if fam == "sqlite_flat":
            cur.execute("CREATE TABLE export (project TEXT, sequence TEXT, instrument TEXT, counter INTEGER, gas TEXT, peaktype TEXT, revision INTEGER, "
                        "void_flag TEXT, epoch TEXT, area REAL, amplitude REAL, delta TEXT)")
            cur.executemany("INSERT INTO export VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                            [(v["proj"], v["seq"], v["inst"], v["pos"], v["el"], v["pt"], v["rev"], v["void"], str(v["time"]), float(v["area"]),
                              float(v["amp"]), v["d"]) for v in V])
        elif fam == "sqlite_split":
            cur.execute("CREATE TABLE injections (inj_id INTEGER PRIMARY KEY, project TEXT, seq TEXT, inst TEXT, pos INTEGER, t_local TEXT)")
            cur.execute("CREATE TABLE peaks (peak_id INTEGER PRIMARY KEY, inj_id INTEGER, el TEXT, kind TEXT, rev INTEGER, voided INTEGER, area_vs TEXT, "
                        "amp_mv INTEGER, d_milli INTEGER)")
            iid = rng.randint(300, 400)
            pid = 0
            for (k, grp) in _G_groups(rows):
                iid += rng.randint(1, 3)
                v0 = _G_vals(grp[0], L, clock)
                cur.execute("INSERT INTO injections VALUES (?,?,?,?,?,?)", (iid, v0["proj"], v0["seq"], v0["inst"], v0["pos"], v0["time"]))
                for r in grp:
                    v = _G_vals(r, L, clock)
                    pid += 1
                    cur.execute("INSERT INTO peaks VALUES (?,?,?,?,?,?,?,?,?)", (pid, iid, v["el"], v["pt"], v["rev"], v["void"], v["area"], int(v["amp"]),
                                                                              int(v["d"])))
        elif fam == "sqlite_runlog":
            cur.execute("CREATE TABLE runlog (run_key TEXT PRIMARY KEY, project TEXT, sequence TEXT, instrument TEXT)")
            cur.execute("CREATE TABLE peaktab (row_id INTEGER PRIMARY KEY, run_key TEXT, counter INTEGER, gas TEXT, peak TEXT, rev INTEGER, flag TEXT, "
                        "t TEXT, area_mvs REAL, amp_mv INTEGER, delta REAL)")
            keys = {}
            for v in V:
                kk = (v["proj"], v["seq"], v["inst"])
                if kk not in keys:
                    keys[kk] = f"R{len(keys) + 11:03d}"
                    cur.execute("INSERT INTO runlog VALUES (?,?,?,?)", (keys[kk],) + kk)
            for i, v in enumerate(V, 1):
                cur.execute("INSERT INTO peaktab VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (i, keys[(v["proj"], v["seq"], v["inst"])], v["pos"], v["el"], v["pt"], v["rev"], v["void"], v["time"], float(v["area"]),
                             int(v["amp"]), float(v["d"])))
        elif fam == "sqlite_eav":
            cur.execute("CREATE TABLE kv (rec INTEGER, field TEXT, value TEXT)")
            items = []
            for i, v in enumerate(V, 1):
                fl = [(1000 + i, h, str(v[k])) for k, h in zip(_GKEYS, F)]
                rng.shuffle(fl)
                items += fl
            cur.executemany("INSERT INTO kv VALUES (?,?,?)", items)
        con.commit()
        con.close()


# ============================================================================ support file writers
def _G_tokpick(W, s, rng, key, scoped=True):
    toks = _G_sess_tokens(s["id"], s["inst"])
    if not scoped:
        toks = toks[:4] + toks[5:]
    return rng.choice(toks)


def _G_write_support(W, data, rng):  # noqa: C901
    cfg, clock = W["cfg"], W["clock"]
    proj = cfg["project"]
    sess = {s["id"]: s for s in W["sessions"]}
    # site clock
    lines = [f"site: {cfg['facility']}", "zone_label: facility-local", f'base_offset: "{_Goff_text(cfg["base_offset"])}"', "transitions:"]
    for t, o in W["clock"]["trans"]:
        lines += [f'  - at_utc: "{t.strftime("%Y-%m-%dT%H:%M:%SZ")}"', f'    offset_after: "{_Goff_text(o)}"']
    _G_write(data / "site_clock.yaml", "\n".join(lines) + "\n")
    # profile
    lines = [f"project: {proj}", "profile_revision: 7", f"rm_sheet: {cfg['rm_sheet']}", "qc_sheet: QC_Assigned", "elemental_sheet: Elemental_Std",
             "weights_sheet: Capsule_Weights", "elements:"] + [f"  - {e}" for e in cfg["elements"]]
    lines += ["a_ref_vs:"] + [f'  {e}: "{cfg["a_ref"][e]}"' for e in _GELEMENTS]
    lines += [f"drift_material: {cfg['drift_material']}", f"drift_min_points: {cfg['drift_min']}", f"linearity_lookback_days: {cfg['lookback']}",
              f"linearity_min_points: {cfg['lin_min']}", f'grubbs_alpha: "{cfg["alpha"]}"', "samples_in_scope:"]
    lines += [f"  - {s}" for s in W["scope"]]
    _G_write(data / "analysis_profile.yml", "\n".join(lines) + "\n")
    # sequence tables
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', f'<sequence_tables facility="{cfg["facility"]}">']
    order = list(W["sessions"])
    rng.shuffle(order)
    for s in order:
        tok = s["id"] if rng.random() < 0.6 else _G_tokpick(W, s, rng, "seq")
        if s["project"] == proj:
            _G_note_alias(W, "session", tok, s["id"])
        kind = {"A": "ANALYTICAL", "L": "LINEARITY", "O": "ANALYTICAL"}[s["kind"]]
        lines.append(f'  <sequence id="{tok}" project="{s["project"]}" instrument="{s["inst"]}" kind="{kind}">')
        slots = list(s["trays"])
        if rng.random() < 0.3:
            rng.shuffle(slots)
        for sl in slots:
            capv = sl["capsule"].lower() if sl["capsule"] and rng.random() < 0.1 else sl["capsule"]
            lines.append(f'    <slot tray="{sl["tray"]}" token="{sl["seq_token"]}" capsule="{capv}"/>')
            if s["project"] == proj:
                _G_note_alias(W, "material", sl["seq_token"], _G_resolve_material(W, sl["seq_token"], proj, s["local_date"]))
        lines.append("  </sequence>")
    lines.append("</sequence_tables>")
    _G_write(data / "sequence_tables.xml", "\n".join(lines) + "\n")
    # journal
    out = []
    for e in sorted(W["journal"], key=lambda e: rng.random()):
        s = sess[e["session"]]
        tok = _G_tokpick(W, s, rng, "j") if rng.random() < 0.5 else s["id"]
        val = e["value"]
        if e["field"] == "token" and val and rng.random() < 0.4:
            val = _G_token_for(W, s, val, rng)
        if e["project"] == proj:
            _G_note_alias(W, "session", tok, s["id"])
            if e["field"] == "token" and val:
                _G_note_alias(W, "material", val, _G_resolve_material(W, val, proj, s["local_date"]))
        o = {"seq": e["seq"], "project": e["project"], "session": tok, "tray": e["tray"], "field": e["field"], "value": val,
             "action": e["action"], "status": e["status"]}
        if e["reverses"] is not None:
            o["reverses"] = e["reverses"]
        o["entered"] = (s["t1"] + _Gtd(days=2, minutes=e["seq"] % 300)).strftime("%Y-%m-%dT%H:%M:%SZ")
        out.append(_Gjson.dumps(o))
    _G_write(data / "tray_corrections.ndjson", "\n".join(out) + "\n")
    # alias register
    p = data / "alias_register.sqlite"
    if p.exists():
        p.unlink()
    con = _Gsqlite3.connect(str(p))
    con.execute("CREATE TABLE session_alias (token TEXT, canonical TEXT, project TEXT)")
    con.execute("CREATE TABLE instrument_alias (token TEXT, canonical TEXT)")
    con.execute("CREATE TABLE material_alias (token TEXT, canonical TEXT, project TEXT, valid_from TEXT)")
    rows = list(W["alias_rows"]["session"])
    rng.shuffle(rows)
    con.executemany("INSERT INTO session_alias VALUES (?,?,?)", rows)
    con.executemany("INSERT INTO instrument_alias VALUES (?,?)", W["alias_rows"]["instrument"])
    rows = list(W["alias_rows"]["material"])
    rng.shuffle(rows)
    con.executemany("INSERT INTO material_alias VALUES (?,?,?,?)", rows)
    con.commit()
    con.close()
    # audit trail
    p = data / "reintegration_audit.db"
    if p.exists():
        p.unlink()
    con = _Gsqlite3.connect(str(p))
    con.execute("CREATE TABLE audit_trail (entry_id INTEGER, project TEXT, sequence TEXT, counter INTEGER, gas TEXT, revision INTEGER, action TEXT, "
                "reason_code TEXT, entered_utc TEXT, analyst TEXT)")
    for a in W["audit"]:
        s = sess[a["session"]]
        con.execute("INSERT INTO audit_trail VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (a["entry"], a["project"], _G_tokpick(W, s, rng, "a"), a["counter"], {"N": "N2", "C": "CO2"}[a["element"]] if rng.random() < 0.5 else a["element"],
                     a["revision"], a["action"], a["reason"], a["entered"].strftime("%Y-%m-%d %H:%M:%S"), a["analyst"]))
    con.commit()
    con.close()
    # session events
    rows = [[e["id"], e["project"], _G_tokpick(W, sess[e["session"]], rng, "e"), e["inst"], e["event"], e["local"], e["detail"]] for e in W["events"]]
    _G_write(data / "session_events.psv", _Gtab(["event_id", "project", "session", "instrument", "event", "local_time", "detail"], rows, "|"))
    # manifest
    mats = ["leaf", "root", "soil", "litter", "algae", "sediment", "muscle"]
    rows = []
    for smp in W["samples"] + W["other_samples"]:
        rows.append([smp, proj if smp in W["samples"] else cfg["other"], W["client_id"][smp], rng.choice(mats),
                     (W["pivot"] - _Gtd(days=rng.randint(25, 70))).isoformat(), "dropped from scope" if smp in W["scope_dropped"] else ""])
    rng.shuffle(rows)
    _G_write(data / "sample_manifest.csv", _Gtab(["sample_id", "project", "client_id", "matrix", "received", "note"], rows, ","))
    # balance calibration
    rows = []
    for b, segs in W["balances"].items():
        for a, z, f in segs:
            rows.append([b, a.isoformat(), z.isoformat(), _Gs(f, 6)])
    rng.shuffle(rows)
    _G_write(data / "balance_calibration.tsv", _Gtab(["balance", "valid_from", "valid_to", "factor"], rows, "\t"))
    # capsule flags
    out = []
    for fl in W["flags"]:
        cap = fl["capsule"] if rng.random() < 0.85 else fl["capsule"].lower()
        out.append(_Gjson.dumps({"capsule": cap, "code": fl["code"], "flagged_utc": fl["when"].strftime("%Y-%m-%dT%H:%M:%SZ"),
                                 "by": rng.choice(["MKV", "TJL", "ARS", "PNB"])}))
    _G_write(data / "capsule_flags.jsonl", "\n".join(out) + "\n")
    # autosampler events
    lines = ["# autosampler controller log, carousel events", "# fields: event id | local time | instrument | sequence | event | detail | state"]
    ev = []
    n = 4000
    for s in W["sessions"]:
        for i, c in enumerate(W["skip_counters"].get(s["id"], [])):
            ij = next(x for x in s["inj"] if x["counter"] == c)
            n += rng.randint(1, 6)
            ev.append((ij["utc"] - _Gtd(seconds=20), f"AS-{n}", s, "SKIP", f"counter {c}", "ok"))
            if rng.random() < 0.5:
                ev.append((ij["utc"] - _Gtd(seconds=19), f"AS-{n}", s, "SKIP", f"counter {c}", "ok"))
        for _ in range(rng.randint(3, 6)):
            ij = rng.choice(s["inj"])
            n += rng.randint(1, 6)
            ev.append((ij["utc"] - _Gtd(seconds=40), f"AS-{n}", s, rng.choice(["VIAL_CHECK", "PURGE", "RESEAT", "ARM_HOME"]), f"counter {ij['counter']}", "ok"))
        if s["kind"] == "A" and rng.random() < 0.3:
            ij = rng.choice(s["inj"][10:40])
            n += rng.randint(1, 6)
            ev.append((ij["utc"] - _Gtd(seconds=30), f"AS-{n}", s, "SKIP", f"counter {ij['counter']}", "cancelled"))
    ev = [((u + _Gtd(minutes=61)) if _Gis_ambiguous_second(u, clock) else u,) + x[1:] for x in ev for u in [x[0]]]
    ev.sort(key=lambda x: x[0])
    for u, eid, s, kind, det, state in ev:
        lines.append(" | ".join([eid, _Gutc_to_wall(u, clock).strftime("%Y-%m-%d %H:%M:%S"), s["inst"], _G_tokpick(W, s, rng, "x", s["project"] == proj), kind, det, state]))
    W["as_lines"] = len(ev)
    _G_write(data / "autosampler_events.txt", "\n".join(lines) + "\n")
    # rm capsule register
    rows = []
    for s in W["sessions"]:
        for sl in s["trays"]:
            if sl["class"] in ("RM", "QC", "ELM"):
                rows.append([sl["capsule"], sl["true"], sl["lot"], f"B{rng.randint(10, 99)}", (s["start_wall"].date() - _Gtd(days=rng.randint(3, 20))).isoformat()])
    rng.shuffle(rows)
    _G_write(data / "rm_capsule_register.psv", _Gtab(["capsule_id", "material", "lot", "batch", "prepared"], rows, "|"))
    # requests
    rows = [[r["id"], r["ref"], r["elements"], r["status"], r["date"].isoformat()] for r in W["requests"]]
    _G_write(data / "client_requests.tsv", _Gtab(["request_id", "sample_ref", "elements", "status", "requested_on"], rows, "\t"))
    # catalog
    body = ",\n".join("    " + _Gjson.dumps(e) for e in W["catalog"])
    _G_write(data / "ingest_catalog.json", '{\n  "project": "' + proj + '",\n  "catalog": "peak-export segments",\n  "events": [\n' + body + "\n  ]\n}\n")


def _G_write_decoys(W, S, data, rng):  # noqa: C901
    cfg = W["cfg"]
    proj = cfg["project"]
    els = cfg["elements"]
    sess = {s["id"]: s for s in W["sessions"]}
    rows = []
    for smp in sorted({k[0] for k in W["published"]}):
        row = [smp]
        for e in ("N", "C"):
            v = W["published"].get((smp, e))
            row += ["" if v is None else _Gs(v, 2), "" if v is None else rng.choice(["0.05", "0.08", "0.11", "0.04"]),
                    "" if v is None else rng.choice([2, 2, 3])]
        rows.append(row)
    _G_write(data / "published_results.csv", _Gtab(["sample_id", "d15N_air", "d15N_sd", "n_N", "d13C_vpdb", "d13C_sd", "n_C"], rows, ","))
    lines = []
    for k, v in sorted(W["cache"].items()):
        lines.append(_Gjson.dumps({"sample": k[0], "element": k[1], "value": float(_Gs(v, 2)), "cached_utc": "2026-11-09T04:00:00Z",
                                   "source": "lims-batch-export"}))
    _G_write(data / "lims_result_cache.jsonl", "\n".join(lines) + "\n")
    sp = []
    for (sid, e), (m, b) in sorted(W["pub_params"].items()):
        sp.append({"session": sid, "element": e, "slope": float(_Gs(m, 6)), "intercept": float(_Gs(b, 6)), "rm_points": W["pub_points"][(sid, e)]})
    pts = []
    for (sid, tray, e), (r, w) in sorted(S["corr"].items()):
        if r["class"] == "RM":
            pts.append({"session": sid, "tray": tray, "element": e, "material": r["material"], "measured": float(_Gs(w["d3"] + _GF(rng.uniform(-0.05, 0.05)), 3))})
    _G_write(data / "published_session_params.json", _Gjson.dumps({"project": proj, "run": "published-batch-v1", "sessions": sp, "rm_points": pts}, indent=1) + "\n")
    rows = []
    for (sid, tray, e), (r, w) in sorted(S["corr"].items()):
        if r["class"] != "QC":
            continue
        st = W["dash_status"][(sid, e)]
        dv = _Gs(w["d3"], 3)
        rows.append([sid, r["counter"], r["slot"]["seq_token"].strip(), e, dv, "FAIL" if st == "FAIL" and rng.random() < 0.6 else "PASS"])
    seen = {}
    for row in rows:
        seen.setdefault((row[0], row[3]), []).append(row)
    for k, rs in seen.items():
        if W["dash_status"][k] == "FAIL" and not any(x[5] == "FAIL" for x in rs):
            rs[0][5] = "FAIL"
    out = []
    for row in rows:
        out.append([_G_tokpick(W, sess[row[0]], rng, "d")] + row[1:])
    _G_write(data / "qc_dashboard.csv", _Gtab(["session", "counter", "material", "element", "dashboard_delta", "status"], out, ","))
    # noticeboard
    lines = ["Halvorsen facility noticeboard export", "notice | posted | channel | text", ""]
    topics = ["Cold room 3 defrost scheduled", "Helium delivery moved to Thursday", "Balance BAL-3 serviced", "Fume hood inspection",
              "Autosampler carousel cleaned", "Training: tin capsule folding", "Holiday rota posted", "Reference gas tank swapped on K2",
              "Ash crucible replaced on K1", "Drying oven temperature log reviewed", "Water trap regenerated", "Fire drill at 10:00"]
    P = W["pivot"]
    allnotes = []
    for i in range(210):
        d = P - _Gtd(days=rng.randint(-10, 300))
        allnotes.append((d, f"NB-{1000 + i * 4 + rng.randint(0, 3)}", rng.choice(["FACILITIES", "SAFETY", "INSTRUMENT", "ADMIN"]), rng.choice(topics)))
    for nid, mat, lot, e, val in W["rm_notices"]:
        name = "d15N" if e == "N" else "d13C"
        allnotes.append((P - _Gtd(days=rng.randint(5, 200)), nid, "REFERENCE", f"{mat} lot {lot} {name} {val} permil (provisional, see workbook)"))
    allnotes.sort()
    for d, nid, ch, text in allnotes:
        lines.append(f"{nid} | {d.isoformat()} | {ch} | {text}")
    _G_write(data / "lab_noticeboard.txt", "\n".join(lines) + "\n")
    # rerun pack
    lines = [f"# Saved rerun pack for {proj} (published batch v1)", "", "This pack records how the published batch report was produced.",
             "It is kept for traceability. The facility handbook, the governance memo and the reference workbook govern any recomputation.", "",
             "## Run settings", "", "| setting | value |", "|---|---|"]
    for k, v, _ in W["rerun_settings"]:
        lines.append(f"| {k} | {v} |")
    lines += ["", "## Steps", "", "1. Load every peak row of every shard in the data folder, newest revision first.",
              "2. Subtract the session blank mean from every delta value.", "3. Fit a linearity slope from the three ELM-ACT capsules of each session.",
              "4. Fit drift against autosampler counter position.", "5. Normalize with Table N-1 sets and RM_Certified_DRAFT values.",
              "6. Screen replicates with Table G-0.", "7. Take session status from the QC dashboard.", "8. Round the final means to two decimals.", "",
              "## Session log", ""]
    for (sid, e), (m, b) in sorted(W["pub_params"].items()):
        lines.append(f"- {sid} {e}: slope {_Gs(m, 6)} intercept {_Gs(b, 6)} points {W['pub_points'][(sid, e)]} dashboard {W['dash_status'][(sid, e)]}")
    for s in sorted(sess):
        if sess[s]["project"] == proj:
            lines.append(f"- {s} loaded from shard export, instrument {sess[s]['inst']}")
    for (sid, e), f in sorted(S["norm"].items()):
        lines.append(f"- {sid} {e}: session linearity fit from ELM-ACT capsules, drift by counter, blank subtracted first")
        lines.append(f"- {sid} {e}: replicate screen G-0 one-sided, rounding at the end")
    lines += ["", "## Session notes", ""]
    for s in sorted(sess):
        if sess[s]["project"] == proj and sess[s]["kind"] == "A":
            lines.append(f"- {s}: autosampler log not consulted; status copied from the dashboard export")
    _G_write(data / "rerun_pack.md", "\n".join(lines) + "\n")
    # quick reference
    lines = ["FACILITY STATISTICS AND CONSTANTS QUICK REFERENCE (printed 2024)", "",
             "Section AW. Molar masses used for C:N reporting (g/mol)", "element | molar_mass", "C | 12.0106", "N | 14.0067", "H | 1.00794",
             "O | 15.9994", "S | 32.065", "", "Section GO. Grubbs critical values, one-sided (superseded by the governance memo)", "n | alpha_0.05 | alpha_0.01"]
    for n, (a, b) in sorted(W["grubbs_one"].items()):
        lines.append(f"{n} | {a} | {b}")
    lines += ["", "Section T. Student t, two-sided 95 percent", "df | t"]
    for df in range(1, 101):
        lines.append(f"{df} | {_G_tq(0.975, df):.4f}")
    lines += ["", "Section U. Unit conversions", "quantity | factor", "mVs to Vs | 0.001", "mV to V | 0.001", "milli-permil to permil | 0.001",
              "mg to ug | 1000", "permil to ratio | 1 + d / 1000", "minutes to hours | 1 / 60"]
    lines += ["", "Section Q. Dixon Q critical values, 95 percent", "n | q"]
    dix = [0.970, 0.829, 0.710, 0.625, 0.568, 0.526, 0.493, 0.466, 0.444, 0.426, 0.410, 0.396, 0.384, 0.374, 0.365, 0.356, 0.349, 0.342, 0.337,
           0.331, 0.326, 0.321, 0.317, 0.312, 0.308, 0.305, 0.301, 0.290]
    for i, q in enumerate(dix, 3):
        lines.append(f"{i} | {q:.3f}")
    _G_write(data / "stat_quick_reference.txt", "\n".join(lines) + "\n")
    # decoy shards
    for fname in ("ab_0re7.csv", "mv_full_export.csv"):
        L = ("L01", fname, "csv", "local_iso", "Vs", "mV", "permil", "E1", "P1", ("V", ""), False)
        _G_write_shard(data / fname, L, W["recs_raw"][fname], W["clock"], rng)
# ============================================================================ written specification
_GHANDBOOK = """# EA-IRMS batch recomputation handbook (revision 9)

Applies to facility batch reports of d15N versus AIR and d13C versus VPDB measured by elemental
analyser isotope-ratio mass spectrometry. Rules are numbered H1 to H17. Every rule carries a worked
example on toy values that do not come from any batch.

## H1 Authority

1. This handbook.
2. The governance memo `governance_memo.pdf`. Only tables whose title ends in `[IN FORCE]` apply.
   Tables marked `[WITHDRAWN ...]` or `[SUPERSEDED]` have no force, even when printed first.
3. The reference workbook `reference_workbook.xlsx`, and within it only the sheets that the analysis
   profile names (`rm_sheet`, `qc_sheet`, `elemental_sheet`, `weights_sheet`).
4. `analysis_profile.yml` and `site_clock.yaml`.
5. Operational records: shard exports, `ingest_catalog.json`, `sequence_tables.xml`,
   `tray_corrections.ndjson`, `alias_register.sqlite`, `reintegration_audit.db`,
   `session_events.psv`, `autosampler_events.txt`, `rm_capsule_register.psv`, `capsule_flags.jsonl`,
   `balance_calibration.tsv`, `sample_manifest.csv`, `client_requests.tsv`.

The published results, the published session parameters, the saved rerun pack, the LIMS cache, the
QC dashboard and the noticeboard carry no authority; they are inputs only to the comparison reports.
In `stat_quick_reference.txt` only Section AW (molar masses) is authoritative; its statistical
tables are superseded by the memo.

## H2 Tokens and aliases

Tokens are compared after trimming surrounding whitespace and upper-casing.

- A canonical session id matches `SQ-dddd-dd` or `LN-dddd-dd`. Any other session token resolves
  through table `session_alias`: a row applies when its `project` is `*` or equals the project of the
  record that carries the token. Follow rows until a canonical id is reached.
- A canonical instrument is `K1` or `K2`. Other instrument tokens resolve through
  `instrument_alias`, following rows until a canonical instrument is reached.
- Canonical materials are `RM-GLU-L`, `RM-GLU-H`, `RM-CAF` (class RM), `QC-SED`, `QC-MUS`, `QC-ALG`
  (class QC), `ELM-ACT` (class ELM), `BLK` (class BLK), `COND` (class COND) and every `sample_id` of
  `sample_manifest.csv` (class SAMPLE). Other material tokens resolve through `material_alias`: a row
  applies when its `project` is `*` or the session's project and its `valid_from` is on or before the
  session date (H6). When several rows apply to one token the row with the latest `valid_from`
  wins. Follow rows until a canonical material is reached. A token with no applicable row that equals
  a `client_id` of `sample_manifest.csv` resolves to that sample.

Example: rows `RUN-K9-9901 -> SQ9999-01` (`*`) and `SQ9999-01 -> SQ-9999-01` (`*`) resolve
`run-k9-9901 ` in two steps. Rows `QX -> QC-SED` (`*`, valid_from 2020-01-01) and `QX -> QC-MUS`
(`*`, valid_from 2026-05-02) send `QX` to QC-SED in a session dated 2026-05-01 and to QC-MUS in a
session dated 2026-05-02.

## H3 Site clock

The offset in effect at instant u is `base_offset`, replaced by `offset_after` of every transition
whose `at_utc` is on or before u. A local wall time maps to the instant u with u + offset(u) equal to
it. A wall time that names two instants (a repeated hour) means the earlier instant. A wall time
that names no instant (a skipped hour) is read with the offset in effect before that transition.

Example with base +01:00 and a transition to +02:00 at 2030-03-31T01:00:00Z and back to +01:00 at
2030-10-27T01:00:00Z: `2030-10-27 02:30` is 2030-10-27T00:30:00Z (the earlier of 00:30Z and 01:30Z);
`2030-03-31 02:30` does not exist and is read with +01:00 as 2030-03-31T01:30:00Z.

## H4 Ingestion

1. Replay `ingest_catalog.json` events in event order. A segment (file, session) is active when its
   latest REGISTER or RETIRE event is REGISTER. VERIFY events change nothing. The session of an
   event resolves with the catalog project.
2. Read only files that have at least one active segment. Process files in the order of each file's
   first REGISTER event, and records within a file in document order (SQLite rows in ascending
   primary key or rowid order, the EAV table in ascending `rec`).
3. A peak record is one peak of one element. In the wide layout every filled element block of a row
   is one record.
4. Filters, applied in this order to every record: another project (`other_project`); a reference
   gas peak (`reference_peaks`); a session whose segment in this file is not active
   (`inactive_segment`); a record whose canonical session, counter, element and revision equal those
   of an earlier record that passed every filter (`duplicates`).
5. Revision admission. Revision 0 is always admitted. Revision r of (session, counter, element),
   r of 1 or more, is admitted when the latest `audit_trail` entry for that project, session,
   counter, element and revision (latest `entered_utc`, ties broken by the higher `entry_id`) has
   action APPROVE and a `reason_code` whose status in memo Table C-1 is ACCEPTED. The `gas` column of
   the audit trail uses the element tokens of maps E1 or E2 of the feed layouts.
6. The selected revision is the highest admitted revision. The void test applies to the selected
   revision only: when it is void the injection element is dropped, with no fall back to an older
   revision. Counters: `revisions_not_admitted` counts candidate revisions that are not admitted,
   `revisions_superseded` counts admitted revisions below the selected one, `voided` counts injection
   elements dropped by the void test, `kept` counts the rest.

Example: revisions 0, 1, 2 with revision 2 not admitted and revision 1 void: the selected revision is
1, it is void, the element is dropped; counters not admitted 1, superseded 1, voided 1.

## H5 Positions and materials

The position on a record is the autosampler counter. In `autosampler_events.txt` only SKIP events
in state `ok` count, once per event id; the counter of a SKIP event is the number in its detail
field, and its session token resolves with the profile project. In a session the tray position of counter c is c plus the
number of counted SKIP events (one per event id) whose counter is less than or equal to c; two
SKIP events with different ids at the same counter count twice. Trays no counter reaches were
skipped and never measured.

The material of a tray is its token in `sequence_tables.xml`, unless `tray_corrections.ndjson`
settles otherwise. Consider entries of the session's project with field `token` and status POSTED;
statuses and actions compare case-insensitively. A REVERSE entry cancels the entry its `reverses`
names; cancelling a REVERSE restores its target. The tray takes the value of the SET entry with the
highest `seq` that is still in effect; with none in effect it keeps the sequence token. The token then
resolves under H2. The capsule of a tray is its `capsule` attribute, compared case-insensitively.

Example: SKIP at counter 17 and counter 30 put counter 16 on tray 16, counter 17 on tray 18 and
counter 30 on tray 32. Entries 11 SET X, 12 SET Y, 13 REVERSE 12 leave X; adding 14 REVERSE 13
restores Y.

## H6 Times

All records of one injection carry the same time. The session start is the time of counter 1, and
the session date is the local calendar date of the session start. Run minutes of an injection are the
seconds from the session start to the injection, less the part of each PAUSE to RESUME interval of
that session in `session_events.psv` that lies before the injection, divided by 60 exactly. Event
times are typed local wall times (H3). A session fails the leak check when its last LEAK_CHECK event
(by time, ties by event id) has detail FAIL.

Example: start 10:00:00Z, pause 11:00 to 11:40 local at +01:00, injection at 10:55:00Z: run minutes
are 55 - 40 = 15.

## H7 Exclusions

Before any computation an injection (both elements) is excluded when memo Table R-1 has an IN FORCE
EXCLUDE_POSITION ruling of the session's project whose target is `<session token>/<tray>`, or when
its capsule has a flag in `capsule_flags.jsonl` whose effect in memo Table X-1 is EXCLUDE. Capsule
ids compare case-insensitively everywhere. An
excluded injection takes part in nothing below. The ledger names the ruling id, else the flag code.

## H8 Linearity

Linearity sessions are the sequences of kind LINEARITY. For each linearity session and element the
points are its non-excluded ELM-ACT injections with x = area (Vs) and y = raw delta. With at least
`linearity_min_points` points the slope is the least-squares slope rounded to 6 decimals; with fewer
the session has no slope for that element.

An analytical session on instrument I with session date D uses, per element, the latest linearity
session on I with session date D that started before it and has a slope; failing that, the latest
linearity session on I with a slope whose session date lies from D minus `linearity_lookback_days`
to D minus 1. The slope is applied when its absolute value is at least the memo Table L-1 threshold
(status APPLIED); a smaller slope is not applied (BELOW_THRESHOLD); with no linearity session the
status is NONE. The slope not applied counts as 0.

d_lin = d_raw - k x (A - a_ref), with a_ref per element from the profile, rounded to 4 decimals.

Example: k = 0.006000, A = 20.0000, a_ref = 15: 1.2340 - 0.006 x 5 = 1.2040.

## H9 Drift

Drift points are the non-excluded injections of the profile `drift_material`, x = run minutes,
y = d_lin. With at least `drift_min_points` points the slope is the least-squares slope rounded to 8
decimals (status FITTED); otherwise 0 (INSUFFICIENT). The anchor is the mean x of the drift points
rounded to 4 decimals. d_drift = d_lin - slope x (x - anchor), rounded to 4 decimals.

## H10 Blank

Blank capsules are the non-excluded BLK injections whose area is at most the memo Table A-1
`blank_area_max_vs`; BLK injections above it are rejected. A_b is their mean area (4 decimals) and
d_b their mean raw delta (3 decimals); with no blank both are 0.
d_blank = (d_drift x A - d_b x A_b) / (A - A_b), rounded to 4 decimals.

Example: d_drift 2.0000, A 10.0000, d_b -1.000, A_b 0.1000: (20 + 0.1) / 9.9 = 2.0303.

## H11 Normalization

The reference set of an element is memo Table N-2. Candidate points are the non-excluded RM
injections of set materials whose amplitude lies inside memo Table A-1 (bounds included). Every set
material needs at least 2 candidates; otherwise the status is NO_NORMALIZATION. The y value of a
point is the certified value of its capsule lot (`rm_capsule_register.psv`) in the workbook sheet
named `rm_sheet`, column `d15N_air` or `d13C_vpdb`; x is d_blank.

Fit y = slope x x + intercept by least squares. While the point with the largest absolute residual
exceeds the N-2 reject limit: stop with LIMIT_STOP when removing it would leave its
material with fewer than 2 points; stop with MAX_REJECT when N-2 `max_rejections` points are already
removed; otherwise remove it and refit. With no residual above the limit the status is CONVERGED.
`fits` counts the fits made. A residual is the certified value minus the fitted value; removed
residuals are reported to 4 decimals; the final slope and
intercept are rounded to 6 decimals and d_norm = slope x d_blank + intercept, rounded to 3 decimals,
for RM, QC, ELM and SAMPLE injections.

## H12 Elemental content

Capsule mass = `mass_mg` of `weights_sheet` times the factor of `balance_calibration.tsv` for the
capsule's balance with valid_from on or before the weigh date and valid_to after it, rounded to 4
decimals. The response factor of a session and element is the mean over its non-excluded ELM-ACT
injections of (mass x 1000 x pct / 100) / (A - A_b) in micrograms per Vs, rounded to 6 decimals,
where pct is the `elemental_sheet` row of the capsule lot with status IN USE. For RM, QC and SAMPLE
injections pct = (A - A_b) x K / (mass x 1000) x 100, rounded to 3 decimals.

## H13 Session acceptance

Per session and element the reasons, in this order, are NO_NORMALIZATION; SLOPE when the slope lies
outside the N-2 `slope_min` to `slope_max` (bounds included); `QC:<material>` for every acceptance QC
material that fails; LEAK when the session failed the leak check. Acceptance QC materials are the
memo Table Q-1 materials for the element, in table order, except the profile `drift_material`. A
material is checked when the session holds at least one of its injections with d_norm: the mean
d_norm rounded to 3 decimals minus the assigned value (`qc_sheet` row with status CURRENT) is the
deviation, which fails when its absolute value exceeds the tolerance. The computed decision is
ACCEPT with no reason and REJECT otherwise. The latest (date, then ruling id) IN FORCE
ACCEPT_SESSION or REJECT_SESSION ruling of Table R-1 of the project whose target resolves to the
session and whose element is the element or ALL replaces the computed decision.

## H14 Replicates and reporting

Samples are the `samples_in_scope` of the profile. The effective request of a sample is its latest
ACTIVE row of `client_requests.tsv` (by requested_on, ties by request_id); `sample_ref` is a sample id
or a client id. An element outside the request is NOT_REQUESTED. The values are the d_norm of the
sample's non-excluded injections in sessions accepted for the element, ordered by session start and
tray. While at least 3 values remain: with s the n-1 standard deviation, stop when s is 0; take the
value farthest from the mean, G = its distance / s, and remove it when G
exceeds the memo Table G-1 value for n in the column of the profile `grubbs_alpha`; otherwise stop.
Comparisons are exact.

A sample element with n values is REPORTED (n of 2 or more), SINGLE (1) or NO_DATA (0). The mean is
rounded to 2 decimals, the sd (n of 2 or more) to 2 decimals and the mean pct of the kept injections
to 2 decimals. C:N molar = (pct_C / M_C) / (pct_N / M_N) from the reported 2 decimal pct values and
the molar masses of quick reference Section AW, rounded to 2 decimals, when both elements are
REPORTED or SINGLE.

Example: values 5.000, 5.010, 7.000, n = 3: mean 5.67, s 1.1518, G 1.1547 exceeds 1.1543, so 7.000
goes and 5.000, 5.010 are reported as 5.00 with sd 0.01.

## H15 Arithmetic and rounding

Arithmetic is exact on the decimal values written in the files: no binary floating point. Every
rounding is round half to even at the stated decimals, and every stage consumes the rounded value of
the stage before it:

| stage | decimals |
|---|---|
| linearity slope | 6 |
| drift slope, anchor | 8, 4 |
| blank mean area, mean delta | 4, 3 |
| d_lin, d_drift, d_blank | 4 |
| normalization slope, intercept | 6 |
| d_norm, QC mean | 3 |
| response factor, capsule mass | 6, 4 |
| injection pct | 3 |
| sample mean, sd, mean pct, C:N | 2 |
| run minutes in the ledger | 4 (exact value used in fits) |

Example: 2.0345 rounds to 2.034 and 2.0355 to 2.036 at 3 decimals; the mean of 1.244 and 1.246 is
exactly 1.245 and rounds to 1.24 at 2 decimals.

## H16 Reading the workbook

Sheets are found by name through `xl/workbook.xml` and its relationships, never by part file name.
The workbook is an ECMA-376 SpreadsheetML package; read cells, shared strings and positions as that
standard defines them, not by the habits of one writer.
The header row of a sheet is the first row whose first cell equals the key column name (`material`
or `capsule_id`); rows below whose second cell is empty are notes. Numeric text is trimmed. Date
cells are serial day numbers counted from 1904-01-01 when the `workbookPr` element carries
`date1904` set to 1 or true, and from 1899-12-30 otherwise.

Example: serial 45000 is 2027-03-16 under date1904 and 2023-03-15 otherwise.

Example rows: a header row `capsule_id | project | mass_mg | balance | weighed | operator` may sit
below two title rows; a later row holding only `continued from bench sheet 2` is a note.

## H17 Reading the memo

A table starts at a title row `Table <id>: <title> [<status>]` and continues on later pages under a
row `Table <id> (continued)` that repeats the header. Rows are rebuilt from the positioned text of
each page; a text line that begins with the word Table but is not a title row is prose.

The memo is a PDF 1.4 file. Its strings, text objects and text-positioning operators follow ISO
32000-1 (sections 7.3, 7.8 and 9.4); read them as that standard defines them, not by the habits of
one writer.

Example: three text objects at y 700 with x 36, 114 and 192 form one row of three cells, whatever
their order in the content stream; a cell may be a literal string, a hexadecimal string or a TJ
array whose numbers are spacing and carry no text.

## Glossary

- Session: one analytical or linearity sequence on one instrument.
- Injection element: one element (N or C) of one injection.
- Run minutes: elapsed time with pauses removed (H6).
- Reference set: the RM materials used to normalize one element (H11).
"""


def _G_layouts_md(W) -> str:
    fam_note = {
        "csv": "comma-separated, one header row, one record per row",
        "tsv": "tab-separated, one header row, one record per row",
        "psv": "pipe-separated, one header row, one record per row",
        "csv_semi": "semicolon-separated, one header row, decimal comma in every numeric field",
        "csv_comment": "comma-separated after leading lines that begin with #, columns in the order of the header",
        "jsonl_flat": "one JSON object per line",
        "ndjson_flat": "one JSON object per line",
        "ndjson_nested": "one JSON object per line with objects meta, inj and peak; area and delta are JSON strings that may carry spaces",
        "jsonl_nested": "one JSON object per injection with a peaks array; every array element is one record",
        "json_columnar": "one JSON document; export.columns names the fields of every array in export.rows",
        "xml_attr": "element inj holds project, seq, inst, pos and t; each child peak is one record",
        "xml_child": "each record element holds one child element per field",
        "yaml_blocks": "a YAML 1.2 list of injection blocks; each item of peaks is one record",
        "yml_grouped": "a YAML 1.2 document; sequences is a list of groups with sequence, project and instrument; each item of peaks is one record",
        "fixed": "fixed-width text; a header line and a ruler line; field i starts at the column given in the table",
        "md": "a Markdown table after a heading; one row per record",
        "tsv_wide": "tab-separated; one row per injection and revision index with an N block and a C block; an empty block is no record",
        "sqlite_flat": "SQLite table export",
        "sqlite_split": "SQLite tables injections and peaks joined on inj_id; one peaks row per record",
        "sqlite_runlog": "SQLite tables runlog and peaktab joined on run_key; one peaktab row per record",
        "sqlite_eav": "SQLite table kv(rec, field, value); all rows of one rec form one record",
    }
    timen = {"local_iso": "local wall time YYYY-MM-DD HH:MM:SS (H3)", "local_dmy": "local wall time DD.MM.YYYY HH:MM:SS (H3)",
             "local_dmy_slash": "local wall time DD/MM/YYYY HH:MM:SS (H3)", "local_compact": "local wall time YYYYMMDDHHMMSS (H3)",
             "local_t": "local wall time YYYY-MM-DDTHH:MM:SS without offset (H3)", "epoch_s": "UTC epoch seconds", "epoch_ms": "UTC epoch milliseconds",
             "iso_z": "UTC YYYY-MM-DDTHH:MM:SSZ", "iso_off": "ISO 8601 with the offset in effect", "basic_z": "UTC YYYYMMDDTHHMMSSZ"}
    out = ["# Shard feed layouts", "",
           "Every shard is a peak export. The catalog names the layout of each file in its REGISTER events; file names carry no meaning.",
           "Each record carries the project, a session token, an instrument token, the autosampler counter, the element, the peak type,",
           "the revision, the void flag, the injection time, the peak area, the amplitude and the raw delta versus the reference gas.",
           "", "Units: area `Vs` is volt-seconds with 4 decimals; `mVs` is millivolt-seconds (area x 1000) with 1 decimal. Amplitude `mV` is",
           "an integer; `V` is volts with 3 decimals. Delta `permil` has 3 decimals; `milli` is an integer in thousandths of a permil;",
           "`ratio` is 1 + delta / 1000 with 6 decimals. Element tokens: E1 N2/CO2, E2 N/C, E3 15N/13C, E4 28/44 (mass channel),",
           "E5 nitrogen/carbon. Peak tokens (analyte/reference): P1 S/R, P2 SAMPLE/REF, P3 1/0 text, P3i 1/0 integer, P4 analyte/reference,",
           "P5 PK/RG.", "", "## Layout summary", "", "| layout | family | time | area | amplitude | delta | element | peak | void true | void false | decimal comma |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    for lid, f, fam, tf, au, mu, dm, em, pm, vt, cm in _GLAYOUTS:
        out.append(f"| {lid} | {fam} | {tf} | {au} | {mu} | {dm} | {em or 'per block'} | {pm or 'none'} | {_Gjson.dumps(vt[0])} | {_Gjson.dumps(vt[1])} | "
                   f"{'yes' if cm else 'no'} |")
    out += ["", "## Field map", "", "| layout | field | meaning | notes |", "|---|---|---|---|"]
    meaning = ["project", "session token", "instrument token", "autosampler counter", "element", "peak type", "revision", "void flag", "injection time",
               "peak area", "amplitude", "raw delta"]
    starts = []
    pos = 1
    for w in [10, 16, 9, 5, 5, 4, 4, 5, 16, 11, 7, 9]:
        starts.append(pos)
        pos += w
    for lid, f, fam, tf, au, mu, dm, em, pm, vt, cm in _GLAYOUTS:
        if fam == "tsv_wide":
            for h, m in [("project", "project"), ("sequence", "session token"), ("instrument", "instrument token"), ("counter", "autosampler counter"),
                         ("epoch_ms", "injection time, " + timen[tf])]:
                out.append(f"| {lid} | {h} | {m} | shared by both blocks |")
            for e in ("N", "C"):
                for h, m in [("rev", "revision"), ("void", "void flag"), ("area", "peak area, " + au), ("amp", "amplitude, " + mu), ("d", "raw delta, " + dm)]:
                    out.append(f"| {lid} | {h}_{e} | {m} | element {e} block |")
            continue
        if fam in ("ndjson_nested", "jsonl_nested", "xml_attr", "yaml_blocks", "yml_grouped", "sqlite_split", "sqlite_runlog"):
            names = {"ndjson_nested": ["meta.project", "meta.sequence", "meta.instrument", "inj.position", "peak.gas", "peak.type", "rev", "void", "inj.time",
                                       "peak.area", "peak.height_mv", "peak.delta"],
                     "jsonl_nested": ["project", "sequence", "instrument", "position", "peaks[].gas", "peaks[].type", "peaks[].rev", "peaks[].void", "time",
                                      "peaks[].area", "peaks[].amp", "peaks[].ratio"],
                     "xml_attr": ["inj@project", "inj@seq", "inj@inst", "inj@pos", "peak@el", "peak@kind", "peak@rev", "peak@void", "inj@t", "peak@area_mvs",
                                  "peak@amp_mv", "peak@d"],
                     "yaml_blocks": ["project", "sequence", "instrument", "position", "peaks.gas", "peaks.type", "peaks.revision", "peaks.void", "time",
                                     "peaks.area_vs", "peaks.amp_mv", "peaks.delta"],
                     "yml_grouped": ["sequences.project", "sequences.sequence", "sequences.instrument", "peaks.pos", "peaks.species", "peaks.kind",
                                     "peaks.rev", "peaks.state", "peaks.t", "peaks.area_mvs", "peaks.amp_mv", "peaks.d"],
                     "sqlite_split": ["injections.project", "injections.seq", "injections.inst", "injections.pos", "peaks.el", "peaks.kind", "peaks.rev",
                                      "peaks.voided", "injections.t_local", "peaks.area_vs", "peaks.amp_mv", "peaks.d_milli"],
                     "sqlite_runlog": ["runlog.project", "runlog.sequence", "runlog.instrument", "peaktab.counter", "peaktab.gas", "peaktab.peak",
                                       "peaktab.rev", "peaktab.flag", "peaktab.t", "peaktab.area_mvs", "peaktab.amp_mv", "peaktab.delta"]}[fam]
        elif lid == "L17":
            names = ["project", "sequence", "instrument", "counter", "mass", "peak", "rev", "void", "ts", "area_mvs", "amp_v", "d"]
        else:
            names = _GFIELDS[lid]
        for i, (h, m) in enumerate(zip(names, meaning)):
            note = ""
            if i == 8:
                note = timen[tf]
            elif i == 9:
                note = au + (", decimal comma" if cm else "")
            elif i == 10:
                note = mu + (", decimal comma" if cm and mu == "V" else "")
            elif i == 11:
                note = dm + (", decimal comma" if cm else "")
            elif i == 4:
                note = em
            elif i == 5:
                note = pm
            elif i == 7:
                note = f"{_Gjson.dumps(vt[0])} means void"
            if fam == "fixed":
                note = (note + "; " if note else "") + f"starts at column {starts[i]}"
            out.append(f"| {lid} | {h} | {m} | {note} |")
    out += ["", "## Family notes", ""]
    for fam, note in fam_note.items():
        out.append(f"- `{fam}`: {note}.")
    out += ["", "The wide layout L15 carries no reference peaks. In the EAV layout the field names are those of the field map."]
    return "\n".join(out) + "\n"


_GCONTRACT = [
    ("injection_ledger.csv", "csv", "one row per kept injection element of every project session, linearity sessions included; sorted by session, counter_position, profile element order",
     [("session", "canonical session id"), ("instrument", "K1 or K2"), ("counter_position", "integer"), ("tray_position", "integer (H5)"),
      ("material", "canonical material"), ("element", "N or C"), ("revision", "selected revision"), ("area_vs", "4 decimals, Vs"),
      ("amplitude_mv", "integer mV"), ("delta_raw", "3 decimals"), ("utc_time", "YYYY-MM-DDTHH:MM:SSZ"), ("run_minutes", "4 decimals (H6)"),
      ("excluded", "RULING:<id>, FLAG:<code> or empty (H7)")]),
    ("position_resolution.csv", "csv", "one row per tray of every project session; sorted by session, tray_position",
     [("session", "canonical session id"), ("tray_position", "integer"), ("counter_position", "integer, empty when skipped"),
      ("sequence_token", "token of sequence_tables.xml, trimmed"), ("journal_seq", "seq of the SET entry in effect, empty when none"),
      ("material", "canonical material"), ("material_class", "RM, QC, ELM, BLK, COND or SAMPLE"), ("capsule_id", "as in the sequence table, upper case"),
      ("mass_mg", "corrected mass, 4 decimals, empty when the tray has no weighed capsule"), ("status", "MEASURED, EXCLUDED or SKIPPED")]),
    ("alias_resolution.psv", "psv", "one row per distinct kind, normalized token and canonical value where the canonical value differs from the token (a time-gated token can give two rows), seen as a session or instrument token on analyte peak records of active segments of the project, a sequence id or slot token of a project sequence, or a session token or token value of a project journal entry; sorted by kind, token",
     [("kind", "session, instrument or material"), ("token", "trimmed, upper case"), ("canonical", "resolved canonical value")]),
    ("dedup_report.json", "json", "one object",
     [("files_read", "integer"), ("records_read", "integer"), ("other_project", "integer"), ("reference_peaks", "integer"),
      ("inactive_segment", "integer"), ("duplicates", "integer"), ("revisions_not_admitted", "integer"), ("revisions_superseded", "integer"),
      ("voided", "integer"), ("kept", "integer")]),
    ("source_lineage.json", "json", "object with key files: one object per read file in processing order",
     [("file", "file name"), ("layout", "layout id"), ("records", "integer"), ("other_project", "integer"), ("reference_peaks", "integer"),
      ("inactive_segment", "integer"), ("duplicates", "integer"), ("unique", "records passing every filter")]),
    ("linearity_slopes.json", "json", "object with lin_sessions (per linearity session and element, sorted by session then element order) and assignments (per analytical session and element)",
     [("lin_sessions[].session", "canonical id"), ("lin_sessions[].instrument", "K1 or K2"), ("lin_sessions[].local_date", "YYYY-MM-DD session date"),
      ("lin_sessions[].element", "N or C"), ("lin_sessions[].n_points", "integer"), ("lin_sessions[].slope", "6 decimals or null"),
      ("assignments[].session", "canonical id"), ("assignments[].element", "N or C"), ("assignments[].lin_session", "id or null"),
      ("assignments[].lin_slope", "6 decimals or null"), ("assignments[].applied_slope", "6 decimals"),
      ("assignments[].status", "APPLIED, BELOW_THRESHOLD or NONE")]),
    ("drift_fits.tsv", "tsv", "one row per analytical session and element; sorted by session, element order",
     [("session", "canonical id"), ("element", "N or C"), ("drift_material", "profile drift material"), ("n_points", "integer"),
      ("slope_per_min", "8 decimals"), ("anchor_min", "4 decimals"), ("status", "FITTED or INSUFFICIENT")]),
    ("blank_corrections.psv", "psv", "one row per analytical session and element",
     [("session", "canonical id"), ("element", "N or C"), ("n_blanks", "integer"), ("n_rejected", "integer"), ("mean_area_vs", "4 decimals"),
      ("mean_delta", "3 decimals")]),
    ("normalization_fits.json", "json", "object with key fits: one object per analytical session and element",
     [("session", "canonical id"), ("element", "N or C"), ("reference_set", "list of materials in N-2 order"), ("n_points", "points in the final fit"),
      ("fits", "integer"), ("slope", "6 decimals or null"), ("intercept", "6 decimals or null"),
      ("removed", "list of objects tray_position, material, residual (certified minus fitted, 4 decimals) in removal order"),
      ("status", "CONVERGED, LIMIT_STOP, MAX_REJECT or NO_NORMALIZATION")]),
    ("corrected_injections.jsonl", "jsonl", "one object per non-excluded RM, QC, ELM or SAMPLE injection element of the analytical sessions; sorted by session, tray_position, element order",
     [("session", "canonical id"), ("tray_position", "integer"), ("material", "canonical"), ("material_class", "class"), ("element", "N or C"),
      ("d_lin", "4 decimals"), ("d_drift", "4 decimals"), ("d_blank", "4 decimals"), ("d_norm", "3 decimals or null"),
      ("pct", "3 decimals or null; null for ELM")]),
    ("elemental_factors.tsv", "tsv", "one row per analytical session and element",
     [("session", "canonical id"), ("element", "N or C"), ("n_standards", "integer"), ("factor_ug_per_vs", "6 decimals or empty")]),
    ("session_acceptance.csv", "csv", "one row per analytical session and element",
     [("session", "canonical id"), ("element", "N or C"), ("instrument", "K1 or K2"), ("norm_slope", "6 decimals or empty"), ("slope_ok", "Y or N"),
      ("qc_checks", "<material>:<deviation 3 decimals, minus sign only when negative>:<PASS|FAIL> joined by ; in Q-1 order"), ("leak", "Y or N"),
      ("computed", "ACCEPT or REJECT"), ("ruling", "ruling id or empty"), ("decision", "ACCEPT or REJECT"), ("reasons", "reasons joined by ; (H13)")]),
    ("qc_results.xml", "xml", "root qc_results with attribute project; one check element per checked QC material, session and element",
     [("check@session", "canonical id"), ("check@element", "N or C"), ("check@material", "QC material"), ("check@n", "integer"),
      ("check@mean", "3 decimals"), ("check@assigned", "2 decimals"), ("check@deviation", "3 decimals"), ("check@tolerance", "2 decimals"),
      ("check@result", "PASS or FAIL")]),
    ("isotope_results.csv", "csv", "one row per sample in scope; sorted by sample_id; empty cells where a value does not apply",
     [("sample_id", "canonical"), ("d15N_air", "2 decimals"), ("d15N_sd", "2 decimals"), ("n_N", "integer, 0 for NO_DATA, empty for NOT_REQUESTED"), ("pct_N", "2 decimals"),
      ("status_N", "REPORTED, SINGLE, NO_DATA or NOT_REQUESTED"), ("d13C_vpdb", "2 decimals"), ("d13C_sd", "2 decimals"), ("n_C", "integer, 0 for NO_DATA, empty for NOT_REQUESTED"),
      ("pct_C", "2 decimals"), ("status_C", "status"), ("cn_molar", "2 decimals")]),
    ("replicate_screening.jsonl", "jsonl", "one object per in-scope sample and requested element with at least one value; sorted by sample, element order",
     [("sample", "canonical"), ("element", "N or C"), ("initial_n", "integer"), ("values", "d_norm values in H14 order, 3 decimals"),
      ("removed", "objects value (3 decimals), g (4 decimals), g_crit (the G-1 value, 4 decimals), n; value, g and g_crit are JSON numbers"), ("final_n", "integer")]),
    ("parameters_used.yaml", "yaml", "flat key: value lines in this order",
     [("project", "profile"), ("rm_sheet", "profile"), ("normalization_table", "id of the table applied"), ("reference_set_<e>", "comma list"),
      ("reject_limit_<e>", "N-2"), ("max_reject_<e>", "N-2"), ("linearity_threshold_<e>", "L-1"), ("a_ref_<e>", "profile"),
      ("amplitude_min_<e>", "A-1"), ("amplitude_max_<e>", "A-1"), ("blank_area_max_<e>", "A-1"), ("slope_min", "N-2"), ("slope_max", "N-2"),
      ("linearity_lookback_days", "profile"), ("drift_material", "profile"), ("drift_min_points", "profile"), ("grubbs_table", "id of the table applied"),
      ("grubbs_alpha", "profile"), ("molar_mass_C", "Section AW"), ("molar_mass_N", "Section AW"), ("date_system", "1904 or 1900"),
      ("clock_base_offset", "site clock"), ("qc_tolerance_<material>_<e>", "Q-1, acceptance materials only")]),
    ("variance_vs_published.csv", "csv", "one row per sample and element published or recomputed as REPORTED or SINGLE; sorted by sample_id, element order",
     [("sample_id", "canonical"), ("element", "N or C"), ("published", "2 decimals or empty"), ("recomputed", "2 decimals or empty"),
      ("diff", "recomputed minus published, 2 decimals"), ("status", "MATCH when the absolute diff is at most 0.05, DIFF, ONLY_PUBLISHED, ONLY_RECOMPUTED")]),
    ("session_param_diff.json", "json", "object with key sessions: one object per session and element of the published parameters, sorted by session, element order",
     [("session", "id"), ("element", "N or C"), ("published_slope", "6 decimals"), ("recomputed_slope", "6 decimals or null"),
      ("published_intercept", "6 decimals"), ("recomputed_intercept", "6 decimals or null"), ("slope_diff", "recomputed minus published or null"),
      ("intercept_diff", "recomputed minus published or null"), ("published_points", "rm_points of the published session"),
      ("recomputed_points", "n_points or null")]),
    ("dashboard_disagreements.csv", "csv", "one row per session and element present on the dashboard; sorted by session, element order",
     [("session", "canonical id"), ("element", "N or C"), ("dashboard_status", "FAIL when any dashboard row of it is FAIL, else PASS"),
      ("recomputed_decision", "ACCEPT or REJECT"), ("agrees", "Y when PASS meets ACCEPT or FAIL meets REJECT, else N")]),
    ("cache_divergence.jsonl", "jsonl", "one object per cache entry; sorted by sample, element order",
     [("sample", "canonical"), ("element", "N or C"), ("cached", "2 decimals"), ("recomputed", "2 decimals or null"),
      ("status", "CURRENT when recomputed exists and differs by at most 0.05, else STALE")]),
    ("reconciliation.md", "md", "sections Summary, Session decisions, Run settings, Superseded notices, each one Markdown table",
     [("Summary", "per element: recomputed_reported (sample elements REPORTED or SINGLE), published_reported (published values), compared (both present), diff_count (absolute diff above 0.05), mean_shift (mean of recomputed minus published over the compared values, 3 decimals); one row per element in profile element order"),
      ("Session decisions", "session elements whose computed or final decision is REJECT or that carry a ruling, sorted by session then element order: session, element, computed, ruling, decision, reasons"),
      ("Run settings", "every setting of the rerun pack Run settings table in its order: setting, published_run, in_force; in_force is the profile rm_sheet, N-2 for normalization_table, the N-2 set joined by commas for reference_set_N and reference_set_C, G-1 for grubbs_table, and otherwise drift_axis run_minutes, linearity_partition instrument_local_day, correction_order linearity,drift,blank,normalization, revision_rule audit_admitted, autosampler_skips applied, session_rulings R-1_in_force, arithmetic exact_decimal_stage_rounding"),
      ("Superseded notices", "noticeboard REFERENCE notices whose value differs from the in-force certified value, sorted by notice: notice, material, lot, element, notice_value, in_force_value (2 decimals)")]),
]


def _G_contract_md() -> str:
    out = ["# Output contract", "",
           "Every report is UTF-8 with LF line endings and a final newline. Delimited reports carry exactly the header named here, in this order,",
           "unquoted. Negative numbers carry a leading minus sign and no number carries a plus sign.",
           "JSON reports are one document; JSON Lines reports hold one object per line. Numbers carry the decimals stated here and are",
           "compared by value. Empty cells and null stand for values that do not apply. `manifest.json` lists the other reports in the order",
           "of this contract: one JSON object whose only key `files` holds an array of objects name, bytes, sha256. Rows of delimited reports and JSON Lines objects compare as sets, as do the",
           "objects of JSON arrays except the `files` array of source_lineage.json, whose order is the processing order; arrays of plain",
           "values keep their stated order. Session tokens of the QC dashboard and of the published session parameters",
           "resolve under handbook H2 with the profile project.", "", "| report | format | column or key | content |", "|---|---|---|---|"]
    for name, fmt, rows_note, cols in _GCONTRACT:
        out.append(f"| {name} | {fmt} | (rows) | {rows_note} |")
        for c, note in cols:
            out.append(f"| {name} | {fmt} | {c} | {note} |")
    out += ["", "Element order is the order of `elements` in the analysis profile. Session order is ascending canonical id."]
    return "\n".join(out) + "\n"
# ============================================================================ workbook and memo
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
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    cells.append(f'<c{at}><v>{val!r}</v></c>')
                elif rng.random() < 0.2:
                    cells.append(f'<c{at} t="inlineStr"><is><t>{_G_xesc(str(val))}</t></is></c>')
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
        def put(name, data):
            info = _Gzipfile.ZipInfo(name, date_time=(2026, 11, 20, 9, 0, 0))
            info.compress_type = _Gzipfile.ZIP_DEFLATED
            z.writestr(info, data)
        put("[Content_Types].xml", "".join(ct))
        put("_rels/.rels", root_rels)
        put("xl/workbook.xml", "".join(wb))
        put("xl/_rels/workbook.xml.rels", "".join(rels))
        put("xl/sharedStrings.xml", "".join(sst))
        put("xl/styles.xml", styles)
        for k in range(n):
            put(f"xl/worksheets/sheet{file_order[k]}.xml", sheet_xml[k])


def _G_serial(d, date1904):
    return (d - (_Gdate(1904, 1, 1) if date1904 else _Gdate(1899, 12, 30))).days


def _G_cell(rng, text):
    """A decimal value written either as a number cell or as padded text."""
    u = rng.random()
    if u < 0.5:
        return float(text)
    if u < 0.75:
        return " " + text
    return text


def _G_write_workbook(W, data, rng):  # noqa: C901
    cfg = W["cfg"]
    d1904 = cfg["date1904"]
    hdr = ["material", "lot", "d15N_air", "u15N", "d13C_vpdb", "u13C", "status"]

    def rm_sheet(title, table, extra=()):
        rows = [[title], ["values in permil; uncertainties are standard uncertainties"], [], hdr]
        for lot, (n, c) in sorted(table.items()):
            mat = next((m for m, ls in _GLOTS.items() if lot in ls), "RM-GLU-L" if lot.startswith("GL") else "RM-GLU-H" if lot.startswith("GH") else "RM-CAF")
            rows.append([mat if rng.random() < 0.8 else mat.lower(), lot, _G_cell(rng, n), _G_cell(rng, "0.04"), _G_cell(rng, c), _G_cell(rng, "0.03"), "CERTIFIED"])
        rows += list(extra)
        return rows

    sheets = [("Cover", [["Halvorsen Stable Isotope Facility reference workbook"], ["Certified values in force are on the sheet named by rm_sheet in the analysis profile."],
                         ["Draft sheets are kept for review only."]], False),
              ("RM_Certified_2026", rm_sheet("Certified reference material values, revision 2026", _GCERT), False),
              ("RM_Certified_DRAFT", rm_sheet("DRAFT certified values, not for use", _GCERT_D), True),
              ("RM_Legacy_2019", rm_sheet("Legacy certified values, 2019 programme", _GCERT_OLD), False),
              ("RM_Certified_2026R", rm_sheet("Certified reference material values, revision 2026R", _GCERT_R), False)]
    qc = [["QC material assigned values"], [], ["material", "d15N_air", "d13C_vpdb", "status", "assigned_on"]]
    for m in ("QC-ALG", "QC-SED", "QC-MUS"):
        qc.append([m, _G_cell(rng, _GQC_FORMER[m][0]), _G_cell(rng, _GQC_FORMER[m][1]), "FORMER", _G_serial(W["pivot"] - _Gtd(days=300), d1904)])
        qc.append([m, _G_cell(rng, _GQC_ASSIGNED[m][0]), _G_cell(rng, _GQC_ASSIGNED[m][1]), "CURRENT", _G_serial(W["pivot"] - _Gtd(days=60), d1904)])
    sheets.append(("QC_Assigned", qc, False))
    el = [["Elemental standard composition"], ["material", "lot", "N_pct", "C_pct", "basis", "status"]]
    for lot in ("EA-1", "EA-2"):
        el.append(["ELM-ACT", lot, _G_cell(rng, _GELM_OLD[lot][0]), _G_cell(rng, _GELM_OLD[lot][1]), "THEORETICAL", "SUPERSEDED"])
        el.append(["ELM-ACT", lot, _G_cell(rng, _GELM[lot][0]), _G_cell(rng, _GELM[lot][1]), "ASSAYED", "IN USE"])
    sheets.append(("Elemental_Std", el, False))
    cw = [["Capsule weigh sheet"], ["masses in mg as read from the balance before calibration correction"], [],
          ["capsule_id", "project", "mass_mg", "balance", "weighed", "operator"]]
    caps = [(s, sl) for s in W["sessions"] for sl in s["trays"] if sl.get("mass") is not None]
    rng.shuffle(caps)
    for i, (s, sl) in enumerate(caps):
        if i == len(caps) // 2:
            cw.append(["continued from bench sheet 2"])
        cid = sl["capsule"] if rng.random() < 0.9 else sl["capsule"].lower()
        cw.append([cid, s["project"], _G_cell(rng, sl["mass"]), sl["balance"], _G_serial(sl["weighed"], d1904), rng.choice(["MKV", "TJL", "ARS"])])
    sheets.append(("Capsule_Weights", cw, False))
    order = list(range(1, len(sheets) + 1))
    rng.shuffle(order)
    _G_xlsx(data / "reference_workbook.xlsx", sheets, order, rng, d1904, cfg["xlsx_runs"], cfg["xlsx_no_r"])


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
            for k, cell in enumerate(cells):
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
                ops.append(f"BT /F1 7 Tf 1 0 0 1 36 {y} Tm {shows[0]} " + " ".join(f"78 0 Td {sh}" for sh in shows[1:]) + " ET")
            else:
                for k, show in enumerate(shows):
                    ops.append(f"BT /F1 7 Tf 1 0 0 1 {36 + 78 * k} {y} Tm {show} ET")
            y -= 10
        ops.append(f"BT /F1 6 Tf 1 0 0 1 36 24 Tm ({label} page {p + 1} of {n_pages}) Tj ET")
        rng.shuffle(ops)
        if td:
            text, i = [], 0
            while i < len(ops):
                k = rng.randint(1, 3)
                text.append(" ".join(ops[i:i + k]))
                i += k
            raw = ("\n".join(text) + "\n").encode("latin-1")
        else:
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


def _G_write_memo(W, data, rng):  # noqa: C901
    cfg = W["cfg"]
    sess = {s["id"]: s for s in W["sessions"]}
    blocks = []

    def table(tid, title, status, head, rows):
        blocks.append((tid, f"Table {tid}: {title} [{status}]", head, rows))

    prose = [["Governance memo GM-14: EA-IRMS normalization, acceptance and replicate screening"],
             ["Issued by the facility quality board. Tables marked IN FORCE govern every batch recomputation."],
             ["Table N-1 is kept for audit history only; batches use the table that follows it."]]
    wl = {"N": ("0.40", 3, "0.900", "1.100"), "C": ("0.35", 2, "0.900", "1.100")}
    table("N-1", "Normalization reference sets", "WITHDRAWN 2026-03-01", ["element", "reference_set", "reject_limit_permil", "max_rejections", "slope_min", "slope_max"],
          [[e, ";".join(cfg["withdrawn_sets"][e]), wl[e][0], str(wl[e][1]), wl[e][2], wl[e][3]] for e in _GELEMENTS])
    table("N-2", "Normalization reference sets", "IN FORCE", ["element", "reference_set", "reject_limit_permil", "max_rejections", "slope_min", "slope_max"],
          [[e, ";".join(cfg["sets"][e]), cfg["reject_limit"][e], str(cfg["max_reject"][e]), cfg["slope_window"][0], cfg["slope_window"][1]] for e in _GELEMENTS])
    table("A-1", "Amplitude windows and blank limits", "IN FORCE", ["element", "amplitude_min_mv", "amplitude_max_mv", "blank_area_max_vs"],
          [[e, str(cfg["amp_window"][e][0]), str(cfg["amp_window"][e][1]), cfg["blank_max"][e]] for e in _GELEMENTS])
    table("L-1", "Linearity application thresholds", "IN FORCE", ["element", "threshold_permil_per_vs"], [[e, cfg["lin_thr"][e]] for e in _GELEMENTS])
    table("Q-0", "QC acceptance tolerances", "SUPERSEDED", ["material", "element", "tolerance_permil"],
          [[m, e, "0.30" if e == "N" else "0.25"] for m in ("QC-SED", "QC-MUS") for e in _GELEMENTS])
    table("Q-1", "QC acceptance tolerances", "IN FORCE", ["material", "element", "tolerance_permil"],
          [[m, e, cfg["qc_tol"][m][e]] for m in W["qc_order"] for e in _GELEMENTS if e in cfg["qc_tol"].get(m, {})])
    table("X-1", "Capsule flag codes", "IN FORCE", ["code", "description", "effect"], [[c, d, st] for c, d, st in _GFLAG_CODES])
    table("C-1", "Reintegration reason codes", "IN FORCE", ["code", "description", "status"], [[c, d, st] for c, d, st in _GREASONS])
    table("G-0", "Grubbs critical values, one-sided", "SUPERSEDED", ["n", "alpha_0.05", "alpha_0.01"],
          [[str(n), a, b] for n, (a, b) in sorted(W["grubbs_one"].items())])
    table("G-1", "Grubbs critical values, two-sided", "IN FORCE", ["n", "alpha_0.05", "alpha_0.01"],
          [[str(n), v["0.05"], v["0.01"]] for n, v in sorted(W["grubbs"].items())])
    rr = []
    for r in W["rulings"]:
        tgt = r["target"]
        if "/" in tgt:
            sid, tray = tgt.split("/")
            tok = _G_tokpick(W, sess[sid], rng, "r") if sid in sess else sid
            tgt = f"{tok}/{tray}"
        elif tgt in sess and rng.random() < 0.5:
            tgt = _G_tokpick(W, sess[tgt], rng, "r")
        rr.append([r["id"], r["date"].isoformat(), r["project"], tgt, r["element"], r["action"], r["status"]])
    table("R-1", "Session rulings", "IN FORCE", ["ruling", "date", "project", "target", "element", "action", "status"], rr)
    pages, cur = [], list(prose)
    per = 72
    for tid, title, head, rows in blocks:
        if len(cur) + 3 > per:
            pages.append(cur)
            cur = []
        cur += [[title], head]
        for row in rows:
            if len(cur) >= per:
                pages.append(cur)
                cur = [[f"Table {tid} (continued)"], head]
            cur.append(row)
        cur.append(["Table rows above apply as printed."] if rng.random() < 0.3 else [""])
    pages.append(cur)
    pages = [[c for c in pg if c != [""]] for pg in pages]
    _G_pdf(data / "governance_memo.pdf", pages, rng, "Governance memo GM-14", cfg["pdf_octal"], cfg["pdf_td"])
# ============================================================================ entry point
def _G_rng(seed, tag):
    return _Grandom.Random(int(_Ghashlib.blake2b(f"{seed}:{tag}".encode(), digest_size=8).hexdigest(), 16))


def _Ggenerate(data, seed: int, over: dict | None = None) -> dict:
    cfg = _Gcfg(over, seed)
    W = _G_world(seed, cfg)
    _G_assign_tokens(W, _G_rng(seed, "tokens"))
    _G_timeline(W, _G_rng(seed, "time"))
    _G_measure(W, _G_rng(seed, "measure"))
    _G_revisions(W, _G_rng(seed, "rev"))
    _G_flags_rulings_events(W, _G_rng(seed, "flags"))
    _G_aliases(W, _G_rng(seed, "alias"))
    _G_finish(W, _G_rng(seed, "finish"))
    _G_emit(W, _G_rng(seed, "emit"))
    files = [x[1] for x in _GLAYOUTS] + ["ab_0re7.csv"]
    if cfg["rename"]:
        fn = {f: f"zq{i:02d}_{f.rsplit('.', 1)[0][::-1]}.{f.rsplit('.', 1)[1]}" for i, f in enumerate(sorted(files))}
        for e in W["catalog"]:
            e["file"] = fn[e["file"]]
    else:
        fn = {f: f for f in files}
    W["fname"] = fn
    S = _G_compute(W)
    _G_decoys(W, S, _G_rng(seed, "decoy"))
    data = _GPath(data)
    data.mkdir(parents=True, exist_ok=True)
    wr = _G_rng(seed, "write")
    for L in _GLAYOUTS:
        _G_write_shard(data / fn[L[1]], L, W["recs_raw"][L[1]], W["clock"], wr, cfg["yaml_flow"])
    _G_write_support(W, data, wr)
    _G_write_decoys(W, S, data, wr)
    if cfg["rename"]:
        (data / "ab_0re7.csv").rename(data / fn["ab_0re7.csv"])
    _G_write_workbook(W, data, wr)
    _G_write_memo(W, data, wr)
    _G_write(data / "method_handbook.md", _GHANDBOOK)
    _G_write(data / "feed_layouts.md", _G_layouts_md(W))
    _G_write(data / "output_contract.md", _G_contract_md())
    return W


# ============================================================================ grading harness
import ast as _ast
import os as _os
import shutil as _shutil
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import threading as _threading
import xml.etree.ElementTree as _ET
from decimal import InvalidOperation as _InvalidOperation

from rewardkit import criteria, criterion

SHIPPED_SEED = 5593611315082672162
OUT = _GPath("/app/out")
PROGRAM = OUT / "run_irms.py"
NAMES = list(_GREPORTS)
CORE = list(_GCORE)
_LOCK = _threading.RLock()
_MEMO: dict = {}
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
HELD = {
    "h_reseed": (8823190451277310093, {"pdf_octal": True, "xlsx_runs": True, "pdf_td": True, "yaml_flow": True, "no_norm": True,
                                       "ruling_tie": "printed_late", "stack_reasons": True}),
    "h_spring": (2871604438890512271, {"pivot_kind": "spring", "pivot_year": 2027, "date1904": False, "spring_gap_pause": True,
                                       "short_lin": 2, "xlsx_no_r": True, "request_tie": True}),
    "h_zone": (6109342237558170091, {"zone_rule": "us", "base_offset": -300, "pivot_year": 2027, "xlsx_runs": True, "xlsx_no_r": True, "yaml_flow": True,
                                     "no_elm": True, "leak_tie": True}),
    "h_memo": (4419987305512338737, {"sets": {"N": ["RM-GLU-L", "RM-GLU-H", "RM-CAF"], "C": ["RM-GLU-L", "RM-GLU-H"]},
                                     "withdrawn_sets": {"N": ["RM-GLU-H", "RM-CAF"], "C": ["RM-GLU-L", "RM-CAF"]},
                                     "reject_limit": {"N": "0.25", "C": "0.30"}, "max_reject": {"N": 1, "C": 2}, "slope_window": ["0.960", "1.040"],
                                     "lin_thr": {"N": "0.0060", "C": "0.0015"}, "amp_window": {"N": [800, 8500], "C": [1500, 15000]},
                                     "blank_max": {"N": "0.2500", "C": "0.7500"}, "alpha": "0.01", "pdf_octal": True, "pdf_td": True,
                                     "qc_tol": {"QC-SED": {"N": "0.30", "C": "0.25"}, "QC-MUS": {"N": "0.25", "C": "0.20"},
                                                "QC-ALG": {"N": "0.25", "C": "0.20"}}, "two_outliers": "N",
                                     "limit_and_max": "N"}),
    "h_profile": (5140337712096621873, {"rm_sheet": "RM_Certified_2026R", "drift_material": "QC-SED", "elements": ["C", "N"],
                                        "a_ref": {"N": "12.0", "C": "50.0"}, "lookback": 0, "drift_min": 2, "lin_min": 8, "scope_drop": 9,
                                        "short_lin": 2, "pdf_octal": True, "xlsx_no_r": True, "stale_refs": True}),
    "h_dense": (7307715526630918821, {"revision_rate": 0.12, "void_rate": 0.04, "skips": 10, "pauses": 9, "journal_chains": 40,
                                      "outlier_sessions": 7, "extra_rulings": 4, "short_lin": 3, "xlsx_runs": True, "pdf_td": True, "yaml_flow": True,
                                      "no_blank": True, "ruling_tie": "printed_early", "leak_tie": True}),
    "m_journal": (None, {"extra_journal": 36}),
    "m_rulings": (None, {"extra_rulings": 6, "scope_drop": 7, "ruled_flag": True}),
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
            base = _GPath(_tempfile.mkdtemp(prefix=f"irms-{name}-"))
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
            _MEMO[key] = _G_derive(_corpus(name)[1], flip)
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
                stage = _GPath(_tempfile.mkdtemp(prefix="irms-prog-"))
                stage.chmod(0o755)
                staged = stage / "run_irms.py"
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
        work = _GPath(_tempfile.mkdtemp(prefix=f"irms-run-{name}-"))
        work.chmod(0o777)
        data = work / ("input" + tag) / "batch"
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


def _dec(s: str):
    try:
        d = _GD(s.strip())
    except (_InvalidOperation, ValueError):
        return None
    return d if d.is_finite() else None


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
        if items and all(isinstance(v, dict) for v in items) and key != "files":
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


def _sources() -> str:
    try:
        return "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in sorted(OUT.glob("*.py")))
    except OSError:
        return ""


def _contract_files() -> list:
    return NAMES + ["manifest.json"]


# ============================================================================ ungated shape checks
@criterion(description="The program run_irms.py, all twenty-one contract reports and manifest.json exist under /app/out")
def deliverables_present(workspace: _GPath) -> bool:
    return _safe(lambda: PROGRAM.is_file() and all((OUT / n).is_file() for n in _contract_files()))


@criterion(description="The program runs on a fresh copy of the shipped corpus at another path and writes exactly the twenty-two contract files there")
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
                sep = {".csv": ",", ".tsv": "\t", ".psv": "|"}[n[-4:]]
                if got is None or _rows_of(got, sep)[0] != _rows_of(want[n], sep)[0]:
                    return False
        return True
    return _safe(chk)


@criterion(description="The JSON reports in /app/out parse and carry exactly the top-level keys the output contract names")
def json_report_keys(workspace: _GPath) -> bool:
    try:
        want = _expected("shipped")
        for n in NAMES:
            if n.endswith(".json"):
                got = _Gjson.loads(_text(OUT, n) or "")
                if not isinstance(got, dict) or set(got) != set(_Gjson.loads(want[n])):
                    return False
        return True
    except Exception:
        return False


@criterion(description="manifest.json lists every other report in contract order with its true size and SHA-256 digest")
def manifest_consistent(workspace: _GPath) -> bool:
    try:
        man = _Gjson.loads((OUT / "manifest.json").read_text(encoding="utf-8"))
        if [x["name"] for x in man["files"]] != NAMES:
            return False
        for x in man["files"]:
            blob = (OUT / x["name"]).read_bytes()
            if x["bytes"] != len(blob) or x["sha256"] != _Ghashlib.sha256(blob).hexdigest():
                return False
        return True
    except Exception:
        return False


@criterion(description="Every report in /app/out is UTF-8 text with LF line endings and a final newline")
def text_serialization(workspace: _GPath) -> bool:
    try:
        for n in _contract_files():
            text = (OUT / n).read_bytes().decode("utf-8")
            if not text.endswith("\n") or "\r" in text:
                return False
        return True
    except Exception:
        return False


# ============================================================================ gated shipped reports
@criterion(description="The tray position resolution is exact for the shipped corpus, with every core report exact")
def position_resolution_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("position_resolution.csv"))


@criterion(description="The alias resolution table is exact for the shipped corpus, with every core report exact")
def alias_resolution_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("alias_resolution.psv"))


@criterion(description="The ingest counters are exact for the shipped corpus, with every core report exact")
def dedup_report_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("dedup_report.json"))


@criterion(description="The per-file source lineage is exact for the shipped corpus, with every core report exact")
def source_lineage_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("source_lineage.json"))


@criterion(description="The blank corrections are exact for the shipped corpus, with every core report exact")
def blank_corrections_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("blank_corrections.psv"))


@criterion(description="The elemental response factors are exact for the shipped corpus, with every core report exact")
def elemental_factors_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("elemental_factors.tsv"))


@criterion(description="The QC check results are exact for the shipped corpus, with every core report exact")
def qc_results_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("qc_results.xml"))


@criterion(description="The governing settings applied are exact for the shipped corpus, with every core report exact")
def parameters_used_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("parameters_used.yaml"))


@criterion(description="The comparison with the published results is exact for the shipped corpus, with every core report exact")
def variance_vs_published_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("variance_vs_published.csv"))


@criterion(description="The comparison with the published session parameters is exact for the shipped corpus, with every core report exact")
def session_param_diff_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("session_param_diff.json"))


@criterion(description="The QC dashboard comparison is exact for the shipped corpus, with every core report exact")
def dashboard_disagreements_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("dashboard_disagreements.csv"))


@criterion(description="The LIMS cache comparison is exact for the shipped corpus, with every core report exact")
def cache_divergence_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("cache_divergence.jsonl"))


@criterion(description="The reconciliation summary is exact for the shipped corpus, with every core report exact")
def reconciliation_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("reconciliation.md"))


# ============================================================================ held-out re-execution
@criterion(description="Rerun on a reseeded batch with other sessions, revisions, jams and rulings, every report is exact")
def heldout_reseed_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_reseed"))


@criterion(description="Rerun on a spring batch across a skipped clock hour with a pause typed inside it and the 1900 date system, every report is exact")
def heldout_spring_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_spring"))


@criterion(description="Rerun on a batch under another site clock with a negative base offset, every report is exact")
def heldout_zone_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_zone"))


@criterion(description="Rerun on a batch whose memo changes the reference sets, limits, thresholds, windows and tolerances, every report is exact")
def heldout_memo_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_memo"))


@criterion(description="Rerun on a batch whose profile changes the certified sheet, drift material, element order and fit settings, every report is exact")
def heldout_profile_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_profile"))


@criterion(description="Rerun on a denser batch with more revisions, voids, jams, pauses, corrections and outliers, every report is exact")
def heldout_dense_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_dense"))


@criterion(description="Rerun on the shipped batch with added tray corrections and reversal chains, every report is exact")
def metamorphic_journal_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("m_journal"))


@criterion(description="Rerun on the shipped batch with added session rulings and a smaller scope, every report is exact")
def metamorphic_rulings_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("m_rulings"))


# ============================================================================ negative checks (True when the cheat or wrong reading is present)
def _echoes_shipped() -> bool:
    want_h = _expected("h_reseed")["isotope_results.csv"]
    want_s = _expected("shipped")["isotope_results.csv"]
    if _same("isotope_results.csv", want_h, want_s):
        return False
    got = _text(_run("h_reseed"), "isotope_results.csv")
    return got is not None and _same("isotope_results.csv", got, want_s)


@criterion(description="The program ignores its input and replays the shipped sample results on a held-out batch")
def negative_hardcoded_sample_answers(workspace: _GPath) -> bool:
    # inverted: True when the reseeded batch run reproduces the shipped isotope results
    return _safe(_echoes_shipped)


@criterion(description="The program is exact on a copy of the shipped batch and wrong once only the shard file names change")
def negative_filename_dependent_behaviour(workspace: _GPath) -> bool:
    # inverted: True when renaming the shards alone breaks an otherwise exact run (a replay is priced by the check above)
    def chk() -> bool:
        if _echoes_shipped():
            return False
        if not _all_exact(_run("shipped", "a"), "shipped", NAMES):
            return False
        return not _all_exact(_run("renamed"), "renamed", NAMES)
    return _safe(chk)


@criterion(description="Two runs of the program on copies of the same batch write different report bytes")
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
        banned = {"requests", "urllib3", "httpx", "pandas", "numpy", "openpyxl", "pypdf", "PyPDF2", "yaml", "xlrd", "fitz",
                  "pdfplumber", "lxml", "pdfminer", "scipy", "statsmodels", "polars", "duckdb"}
        for p in sorted(OUT.glob("*.py")):
            for node in _ast.walk(_ast.parse(p.read_text(encoding="utf-8"))):
                names = ({a.name.split(".")[0] for a in node.names} if isinstance(node, _ast.Import) else
                         {(node.module or "").split(".")[0]} if isinstance(node, _ast.ImportFrom) else set())
                if names & banned:
                    return True
        return False
    except Exception:
        return False


@criterion(description="isotope_results.csv repeats the published d15N or d13C value for at least half of the compared sample elements")
def negative_echoes_published(workspace: _GPath) -> bool:
    # inverted: True when half or more of the compared values equal the published numbers
    try:
        pub = {}
        for r in _Gcsv.DictReader(_Gio.StringIO((_corpus("shipped")[0] / "published_results.csv").read_text(encoding="utf-8"))):
            for col in ("d15N_air", "d13C_vpdb"):
                if r[col].strip():
                    pub[(r["sample_id"].strip(), col)] = _GD(r[col].strip())
        hit = tot = 0
        for r in _Gcsv.DictReader(_Gio.StringIO(_text(OUT, "isotope_results.csv") or "")):
            for col in ("d15N_air", "d13C_vpdb"):
                k = (str(r.get("sample_id", "")).strip(), col)
                v = _dec(str(r.get(col) or ""))
                if k in pub and v is not None:
                    tot += 1
                    hit += v == pub[k]
        return tot >= 50 and hit * 2 >= tot
    except Exception:
        return False


@criterion(description="normalization_fits.json equals the fits made with the reference sets of the withdrawn memo Table N-1")
def negative_withdrawn_reference_set(workspace: _GPath) -> bool:
    # inverted: True when the shipped fits match the withdrawn-table reading exactly
    return _safe(lambda: _matches_flip("withdrawn_set", "normalization_fits.json"))


@criterion(description="position_resolution.csv equals the tray mapping that treats every autosampler counter as its tray position")
def negative_skip_events_ignored(workspace: _GPath) -> bool:
    # inverted: True when the shipped tray mapping matches the reading that ignores SKIP events
    return _safe(lambda: _matches_flip("skip_ignored", "position_resolution.csv"))


criteria.deliverables_present(weight=1)
criteria.program_writes_contract_files(weight=1)
criteria.delimited_headers_exact(weight=1)
criteria.json_report_keys(weight=1)
criteria.manifest_consistent(weight=1)
criteria.text_serialization(weight=1)
criteria.position_resolution_exact(weight=3)
criteria.alias_resolution_exact(weight=3)
criteria.dedup_report_exact(weight=3)
criteria.source_lineage_exact(weight=3)
criteria.blank_corrections_exact(weight=3)
criteria.elemental_factors_exact(weight=3)
criteria.qc_results_exact(weight=1)
criteria.parameters_used_exact(weight=1)
criteria.variance_vs_published_exact(weight=1)
criteria.session_param_diff_exact(weight=1)
criteria.dashboard_disagreements_exact(weight=1)
criteria.cache_divergence_exact(weight=1)
criteria.reconciliation_exact(weight=1)
criteria.heldout_reseed_exact(weight=5)
criteria.heldout_spring_exact(weight=5)
criteria.heldout_zone_exact(weight=5)
criteria.heldout_memo_exact(weight=5)
criteria.heldout_profile_exact(weight=5)
criteria.heldout_dense_exact(weight=5)
criteria.metamorphic_journal_exact(weight=5)
criteria.metamorphic_rulings_exact(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_third_party_import(weight=-3)
criteria.negative_echoes_published(weight=-3)
criteria.negative_withdrawn_reference_set(weight=-3)
criteria.negative_skip_events_ignored(weight=-3)
