"""Verifier for the night planning task.

Every expected document is derived inside this file from the book it grades. The
shipped book is regenerated here from its seed and checked against a pinned hash,
and further books are generated here, so no expected answer is stored anywhere.
The delivered program runs on each generated book as an unprivileged user from a
foreign working directory.

Test polarity for negative-weight tests: the assertion HOLDS when the cheat is
present. Honest agent -> assertion fails -> negative weight not added.
"""
# pyright: reportUndefinedVariable=false, reportUnhashable=false, reportArgumentType=false

from __future__ import annotations

import configparser
import csv
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import tomllib
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

OUT = Path("/app/out")
SCRIPT = OUT / "derive_report.py"
REGION_NAMES = ("North", "South", "West", "East")
SEGMENT_NAMES = ("commercial", "public")
REGION_DOCS = tuple("region_%s.json" % r for r in REGION_NAMES)
SEGMENT_DOCS = tuple("segment_%s.json" % s for s in SEGMENT_NAMES)
ARTIFACT_NAMES = ("summary.json", "policy_audit.json", "data_quality.json") + REGION_DOCS + SEGMENT_DOCS
SECONDS_PER_NIGHT = 2
DAY_END = 1440
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_NEG = -(10 ** 12)

_HORIZON = 1440
_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"


class _Rng:
    """xorshift64*: identical streams on every Python version."""

    def __init__(self, seed):
        self.s = (seed * 0x9E3779B97F4A7C15 + 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF or 1
        for _ in range(4):
            self.next()

    def next(self):
        x = self.s
        x ^= (x >> 12)
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27)
        self.s = x
        return (x * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def randint(self, lo, hi):
        return lo + self.next() % (hi - lo + 1)

    def choice(self, seq):
        return seq[self.randint(0, len(seq) - 1)]

    def shuffle(self, seq):
        for i in range(len(seq) - 1, 0, -1):
            k = self.randint(0, i)
            seq[i], seq[k] = seq[k], seq[i]

    def sample(self, seq, k):
        pool = list(seq)
        self.shuffle(pool)
        return pool[:k]


def _codes(rng, n, make):
    seen = []
    while len(seen) < n:
        c = make(rng)
        if c not in seen:
            seen.append(c)
    return seen


def book_setup(seed, n_nights, n_clients, n_sites, max_jobs, thresholds, start_day):
    """Book-level identities: families, bays, clients, sites, night ids, dates, job and window ids."""
    assert 1 <= n_nights <= 500
    rng = _Rng(seed)
    fams = _codes(rng, 3, lambda r: "".join(r.choice(_LETTERS) for _ in range(3)))
    ghost_fams = _codes(rng, 6, lambda r: "".join(r.choice(_LETTERS) for _ in range(3)))
    ghost_fams = [g for g in ghost_fams if g not in fams][:2]
    bay_ids = _codes(rng, 3, lambda r: "BAY-%s%d" % (r.choice(_LETTERS), r.randint(10, 99)))
    rates = rng.sample([1, 2, 3, 4], 3)
    while True:
        quals = {}
        for b in bay_ids:
            k = rng.randint(2, 3)
            quals[b] = sorted(rng.sample(fams, k), key=fams.index)
        if all(sum(f in q for q in quals.values()) >= 2 for f in fams):
            break
    bays = [{"bay_id": b, "minute_rate": r, "initial_family": rng.choice(quals[b])}
            for b, r in zip(bay_ids, rates)]
    sites = _codes(rng, n_sites, lambda r: "ST%05d" % r.randint(0, 99999))
    regions = {s: rng.choice(["North", "South", "West", "East"]) for s in sites}
    used_sites = sites[: max(4, n_sites * 3 // 4)]
    allc = _codes(rng, n_clients + 3, lambda r: "CL%06d" % r.randint(0, 999999))
    clients = allc[:n_clients]
    ghost_clients = allc[n_clients:]
    client_site = {c: rng.choice(used_sites) for c in clients}
    segments = {c: rng.choice(["commercial", "public"]) for c in clients}
    night_ids = _codes(rng, n_nights, lambda r: "NT%05d" % r.randint(0, 99999))
    days, d = [], start_day
    for _ in range(n_nights):
        d += rng.randint(1, 3)
        days.append(d)
    job_ids = _codes(rng, max_jobs, lambda r: "JB%06d" % r.randint(0, 999999))
    win_ids = _codes(rng, max_jobs + max_jobs // 8 + 4, lambda r: "WN%06d" % r.randint(0, 999999))
    return {"seed": seed, "fams": fams, "ghost_fams": ghost_fams, "bays": bays, "quals": quals,
            "sites": sites, "regions": regions, "clients": clients, "ghost_clients": ghost_clients,
            "client_site": client_site, "segments": segments, "night_ids": night_ids, "days": days,
            "job_ids": job_ids, "win_ids": win_ids, "thresholds": thresholds,
            "next_job": 0, "next_win": 0}


def _intervals(rng, n_jobs, max_overlap, dur_lo, dur_hi):
    while True:
        iv, tries = [], 0
        while len(iv) < n_jobs and tries < 40000:
            tries += 1
            d = rng.randint(dur_lo, dur_hi)
            s = rng.randint(0, _HORIZON - d)
            e = s + d
            pts = [s] + [a for a, b in iv if s <= a < e]
            if all(sum(1 for a, b in iv + [(s, e)] if a <= p < b) <= max_overlap for p in pts):
                iv.append((s, e))
        if len(iv) == n_jobs:
            return iv


def night_data(ctx, k, spec, attempt):
    """Night k (date order). spec keys: jobs, overlap, mand, crew, fee, defects, values, dur.

    Job and window ids come from book-level pools by position, so redrawing a night
    (new attempt) changes only its content."""
    n_jobs = spec["jobs"]
    pass
    assert 1 <= spec["values"][0] <= spec["values"][1] <= 2000
    assert 1 <= spec["fee"][0] <= spec["fee"][1] <= 500 and 5 <= spec["crew"][0] <= spec["crew"][1] <= 120
    rng = _Rng(ctx["seed"] * 1000003 + k * 7919 + attempt * 104729 + 17)
    ids = ctx["job_ids"][ctx["next_job"]: ctx["next_job"] + n_jobs]
    wids = ctx["win_ids"][ctx["next_win"]: ctx["next_win"] + n_jobs]
    ctx["next_job"] += n_jobs
    ctx["next_win"] += n_jobs
    iv = _intervals(rng, n_jobs, spec["overlap"], spec["dur"][0], spec["dur"][1])
    jobs = []
    for jid, wid, (s, e) in zip(ids, wids, iv):
        jobs.append({"job_id": jid, "window_id": wid, "start": s, "end": e,
                     "family": rng.choice(ctx["fams"]), "client_id": rng.choice(ctx["clients"]),
                     "value": rng.randint(spec["values"][0], spec["values"][1])})
    mand = sorted(rng.sample(ids, min(spec["mand"], n_jobs)))
    fees = []
    for a in ctx["fams"]:
        for b in ctx["fams"]:
            if a != b:
                fees.append([a, b, rng.randint(spec["fee"][0], spec["fee"][1]),
                             rng.randint(spec["crew"][0], spec["crew"][1])])
    rows = [dict(j) for j in jobs]
    windows = [[j["window_id"], j["start"], j["end"]] for j in jobs]
    for kind in spec.get("defects", ()):
        if kind == "dup":
            src = rows[rng.randint(0, len(rows) - 1)]
            extra = dict(src, value=rng.randint(spec["values"][0], spec["values"][1]))
            extra["window_id"] = ctx["win_ids"][ctx["next_win"]]
            ctx["next_win"] += 1
            windows.append([extra["window_id"], src["start"], src["end"]])
            rows.append(extra)
        elif kind == "win_missing":
            r = rows[rng.randint(0, len(rows) - 1)]
            r["window_id"] = ctx["win_ids"][ctx["next_win"]]
            ctx["next_win"] += 1
        elif kind == "win_reversed":
            r = rows[rng.randint(0, len(rows) - 1)]
            for w in windows:
                if w[0] == r["window_id"]:
                    w[1], w[2] = w[2], w[1]
        elif kind == "win_late":
            r = rows[rng.randint(0, len(rows) - 1)]
            for w in windows:
                if w[0] == r["window_id"]:
                    w[2] = _HORIZON + rng.randint(1, 90)
        elif kind == "unk_family":
            rows[rng.randint(0, len(rows) - 1)]["family"] = ctx["ghost_fams"][0]
        elif kind == "unk_client":
            rows[rng.randint(0, len(rows) - 1)]["client_id"] = ctx["ghost_clients"][0]
        elif kind == "fee_missing":
            del fees[rng.randint(0, len(fees) - 1)]
    nid = ctx["night_ids"][k]
    return {"night_id": nid, "day": ctx["days"][k], "jobs": jobs, "rows": rows, "windows": windows,
            "mand": mand, "fees": fees, "defects": list(spec.get("defects", ()))}


def _date(day):
    y, m = 2026, 1
    lens = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    d = day
    while d >= lens[m - 1]:
        d -= lens[m - 1]
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return "%04d-%02d-%02d" % (y, m, d + 1)


def render(ctx, nights):
    """Files of the book as {name: text}."""
    rng = _Rng(ctx["seed"] * 31 + 5)
    rows = [r for n in nights for r in ((r, n["night_id"]) for r in n["rows"])]
    rng.shuffle(rows)
    jobs = "job_id,night_id,window_id,client_id,family,value\n" + "".join(
        "%s,%s,%s,%s,%s,%d\n" % (r["job_id"], nid, r["window_id"], r["client_id"], r["family"], r["value"])
        for r, nid in rows)
    wins = [w for n in nights for w in n["windows"]]
    rng.shuffle(wins)
    windows = "window_id\tstart\tend\n" + "".join("%s\t%d\t%d\n" % tuple(w) for w in wins)
    fees = [[n["night_id"]] + f for n in nights for f in n["fees"]]
    rng.shuffle(fees)
    fee_text = "night_id,from_family,to_family,fee,crew_minutes\n" + "".join(
        "%s,%s,%s,%d,%d\n" % tuple(f) for f in fees)
    bays = json.dumps({"bays": ctx["bays"]}, indent=2) + "\n"
    ini = "[catalog]\nfamilies = %s\n" % ", ".join(ctx["fams"])
    for b in ctx["bays"]:
        ini += "\n[%s]\nfamilies = %s\n" % (b["bay_id"], ", ".join(ctx["quals"][b["bay_id"]]))
    cl = list(ctx["clients"])
    rng.shuffle(cl)
    clients = "".join(json.dumps({"client_id": c, "site": ctx["client_site"][c]}) + "\n" for c in cl)
    st = list(ctx["sites"])
    rng.shuffle(st)
    regions = "site,region\n" + "".join("%s,%s\n" % (s, ctx["regions"][s]) for s in st)
    rng.shuffle(cl)
    segments = "client_id\tsegment\n" + "".join("%s\t%s\n" % (c, ctx["segments"][c]) for c in cl)
    mand = json.dumps({n["night_id"]: n["mand"] for n in nights if n["mand"]}, indent=2, sort_keys=True) + "\n"
    order = list(nights)
    rng.shuffle(order)
    th = ctx["thresholds"]
    audit = "[thresholds]\ncrew_minutes_limit = %d\nmargin_floor = %d\n" % (th[0], th[1])
    for n in order:
        audit += '\n[[night]]\nid = "%s"\ndate = "%s"\n' % (n["night_id"], _date(n["day"]))
    return {"jobs.csv": jobs, "windows.tsv": windows, "bays.json": bays, "qualifications.ini": ini,
            "setup_fees.csv": fee_text, "clients.jsonl": clients, "regions.csv": regions,
            "segments.tsv": segments, "mandatory.json": mand, "audit.toml": audit}


def make_book(seed, specs, attempts, n_clients, n_sites, thresholds, start_day):
    max_jobs = sum(s["jobs"] for s in specs)
    ctx = book_setup(seed, len(specs), n_clients, n_sites, max_jobs, thresholds, start_day)
    nights = [night_data(ctx, k, s, a) for k, (s, a) in enumerate(zip(specs, attempts))]
    return render(ctx, nights)

_SHIPPED_DEFECTS = [["dup"], ["win_missing"], ["win_reversed"], ["win_late"], ["unk_family"], ["unk_client"],
                    ["fee_missing"], ["dup", "win_missing"], ["win_reversed", "fee_missing"],
                    ["unk_client", "fee_missing"], ["dup", "unk_family"], ["win_late", "unk_family"]]


def _shipped_specs() -> list[dict[str, Any]]:
    r = _Rng(666279)
    out = []
    for _ in range(360):
        n = r.randint(4, 10)
        out.append({"jobs": n, "overlap": min(n, r.randint(3, 5)), "mand": r.randint(0, 2),
                    "crew": (15, 60), "fee": (20, 200), "values": (200, 900), "dur": (30, 180)})
    for _ in range(25):
        n = r.randint(11, 30)
        out.append({"jobs": n, "overlap": r.randint(4, 6), "mand": r.randint(1, 3),
                    "crew": (20, 50), "fee": (30, 180), "values": (200, 900), "dur": (30, 180)})
    for _ in range(15):
        n = r.randint(31, 72)
        out.append({"jobs": n, "overlap": r.randint(6, 7), "mand": r.randint(2, 4),
                    "crew": (25, 60), "fee": (20, 160), "values": (200, 900), "dur": (30, 180)})
    for d in _SHIPPED_DEFECTS:
        out.append({"jobs": r.randint(5, 9), "overlap": 4, "mand": 1, "crew": (15, 60), "fee": (20, 200),
                    "values": (200, 900), "dur": (30, 180), "defects": d})
    for _ in range(3):
        out.append({"jobs": 0, "overlap": 1, "mand": 0, "crew": (15, 60), "fee": (20, 200),
                    "values": (200, 900), "dur": (30, 180)})
    r.shuffle(out)
    return out


_BOOKS: dict[str, dict[str, Any]] = {'H1': {'attempts': [0, 0, 0, 0, 0, 0],
        'clients': 400,
        'seed': 91001,
        'sha256': '628690b73e13a6fe524a51a7c5c593eb007e343052087b07d2b3e923579e72e1',
        'sites': 300,
        'specs': [{'crew': [30, 60],
                   'dur': [30, 180],
                   'fee': [20, 120],
                   'jobs': 71,
                   'mand': 2,
                   'overlap': 7,
                   'values': [200, 900]},
                  {'crew': [30, 60],
                   'dur': [30, 180],
                   'fee': [20, 120],
                   'jobs': 71,
                   'mand': 3,
                   'overlap': 7,
                   'values': [200, 900]},
                  {'crew': [30, 60],
                   'defects': ['dup', 'fee_missing'],
                   'dur': [30, 180],
                   'fee': [20, 120],
                   'jobs': 9,
                   'mand': 1,
                   'overlap': 4,
                   'values': [200, 900]},
                  {'crew': [30, 60],
                   'dur': [30, 180],
                   'fee': [20, 120],
                   'jobs': 70,
                   'mand': 2,
                   'overlap': 7,
                   'values': [200, 900]},
                  {'crew': [30, 60],
                   'dur': [30, 180],
                   'fee': [20, 120],
                   'jobs': 69,
                   'mand': 2,
                   'overlap': 7,
                   'values': [200, 900]},
                  {'crew': [30, 60],
                   'dur': [30, 180],
                   'fee': [20, 120],
                   'jobs': 68,
                   'mand': 4,
                   'overlap': 7,
                   'values': [200, 900]}],
        'start': 61,
        'thresholds': [119, 2985]},
 'H2': {'attempts': [1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        'clients': 500,
        'seed': 92001,
        'sha256': '6ff1ed1404b6bf641d98d983d854275ae5d8b7c0b3a8c574848699f5cb09ad29',
        'sites': 350,
        'specs': [{'crew': [20, 45],
                   'dur': [20, 150],
                   'fee': [40, 200],
                   'jobs': 37,
                   'mand': 2,
                   'overlap': 6,
                   'values': [300, 1200]},
                  {'crew': [20, 45],
                   'dur': [20, 150],
                   'fee': [40, 200],
                   'jobs': 27,
                   'mand': 2,
                   'overlap': 6,
                   'values': [300, 1200]},
                  {'crew': [20, 45],
                   'dur': [20, 150],
                   'fee': [40, 200],
                   'jobs': 43,
                   'mand': 2,
                   'overlap': 6,
                   'values': [300, 1200]},
                  {'crew': [20, 45],
                   'defects': ['win_late', 'unk_client'],
                   'dur': [20, 150],
                   'fee': [40, 200],
                   'jobs': 10,
                   'mand': 1,
                   'overlap': 4,
                   'values': [300, 1200]},
                  {'crew': [20, 45],
                   'dur': [20, 150],
                   'fee': [40, 200],
                   'jobs': 26,
                   'mand': 1,
                   'overlap': 6,
                   'values': [300, 1200]},
                  {'crew': [20, 45],
                   'dur': [20, 150],
                   'fee': [40, 200],
                   'jobs': 47,
                   'mand': 2,
                   'overlap': 6,
                   'values': [300, 1200]},
                  {'crew': [20, 45],
                   'dur': [20, 150],
                   'fee': [40, 200],
                   'jobs': 37,
                   'mand': 3,
                   'overlap': 6,
                   'values': [300, 1200]},
                  {'crew': [20, 45],
                   'defects': ['fee_missing'],
                   'dur': [20, 150],
                   'fee': [40, 200],
                   'jobs': 8,
                   'mand': 1,
                   'overlap': 4,
                   'values': [300, 1200]},
                  {'crew': [20, 45],
                   'dur': [20, 150],
                   'fee': [40, 200],
                   'jobs': 29,
                   'mand': 3,
                   'overlap': 6,
                   'values': [300, 1200]},
                  {'crew': [20, 45],
                   'dur': [20, 150],
                   'fee': [40, 200],
                   'jobs': 25,
                   'mand': 3,
                   'overlap': 6,
                   'values': [300, 1200]}],
        'start': 200,
        'thresholds': [105, 3666]},
 'H3': {'attempts': [0, 0, 0, 0, 0, 0, 0, 0],
        'clients': 450,
        'seed': 93002,
        'sha256': 'da9a0dfbf03a58a7f0c9fbf042e1cc761ce370d06c1fff827e226d1cc15e39b4',
        'sites': 320,
        'specs': [{'crew': [25, 60],
                   'dur': [30, 180],
                   'fee': [30, 160],
                   'jobs': 60,
                   'mand': 2,
                   'overlap': 7,
                   'values': [150, 1000]},
                  {'crew': [25, 60],
                   'defects': ['win_missing', 'unk_family'],
                   'dur': [30, 180],
                   'fee': [30, 160],
                   'jobs': 9,
                   'mand': 1,
                   'overlap': 4,
                   'values': [150, 1000]},
                  {'crew': [25, 60],
                   'dur': [30, 180],
                   'fee': [30, 160],
                   'jobs': 64,
                   'mand': 3,
                   'overlap': 7,
                   'values': [150, 1000]},
                  {'crew': [25, 60],
                   'dur': [30, 180],
                   'fee': [30, 160],
                   'jobs': 64,
                   'mand': 3,
                   'overlap': 7,
                   'values': [150, 1000]},
                  {'crew': [25, 60],
                   'dur': [30, 180],
                   'fee': [30, 160],
                   'jobs': 71,
                   'mand': 3,
                   'overlap': 7,
                   'values': [150, 1000]},
                  {'crew': [25, 60],
                   'defects': ['unk_client'],
                   'dur': [30, 180],
                   'fee': [30, 160],
                   'jobs': 7,
                   'mand': 1,
                   'overlap': 4,
                   'values': [150, 1000]},
                  {'crew': [25, 60],
                   'dur': [30, 180],
                   'fee': [30, 160],
                   'jobs': 62,
                   'mand': 2,
                   'overlap': 7,
                   'values': [150, 1000]},
                  {'crew': [25, 60],
                   'dur': [30, 180],
                   'fee': [30, 160],
                   'jobs': 72,
                   'mand': 4,
                   'overlap': 7,
                   'values': [150, 1000]}],
        'start': 400,
        'thresholds': [108, 1564]},
 'M': {'attempts': [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
       'clients': 300,
       'seed': 94001,
       'sha256': 'ce2d161fef8757db947167b5bf4e4ea198d1b4505b66d2f5bec69b7bd3663a92',
       'sites': 250,
       'specs': [{'crew': [15, 50],
                  'dur': [30, 180],
                  'fee': [20, 200],
                  'jobs': 10,
                  'mand': 2,
                  'overlap': 6,
                  'values': [200, 900]},
                 {'crew': [15, 50],
                  'dur': [30, 180],
                  'fee': [20, 200],
                  'jobs': 21,
                  'mand': 2,
                  'overlap': 4,
                  'values': [200, 900]},
                 {'crew': [15, 50],
                  'dur': [30, 180],
                  'fee': [20, 200],
                  'jobs': 19,
                  'mand': 2,
                  'overlap': 4,
                  'values': [200, 900]},
                 {'crew': [15, 50],
                  'dur': [30, 180],
                  'fee': [20, 200],
                  'jobs': 19,
                  'mand': 0,
                  'overlap': 5,
                  'values': [200, 900]},
                 {'crew': [15, 50],
                  'dur': [30, 180],
                  'fee': [20, 200],
                  'jobs': 17,
                  'mand': 2,
                  'overlap': 6,
                  'values': [200, 900]},
                 {'crew': [15, 50],
                  'dur': [30, 180],
                  'fee': [20, 200],
                  'jobs': 10,
                  'mand': 0,
                  'overlap': 4,
                  'values': [200, 900]},
                 {'crew': [15, 50],
                  'defects': ['win_reversed', 'unk_client'],
                  'dur': [30, 180],
                  'fee': [20, 200],
                  'jobs': 8,
                  'mand': 1,
                  'overlap': 4,
                  'values': [200, 900]},
                 {'crew': [15, 50],
                  'dur': [30, 180],
                  'fee': [20, 200],
                  'jobs': 14,
                  'mand': 2,
                  'overlap': 5,
                  'values': [200, 900]},
                 {'crew': [15, 50],
                  'dur': [30, 180],
                  'fee': [20, 200],
                  'jobs': 19,
                  'mand': 0,
                  'overlap': 4,
                  'values': [200, 900]},
                 {'crew': [15, 50],
                  'dur': [30, 180],
                  'fee': [20, 200],
                  'jobs': 24,
                  'mand': 1,
                  'overlap': 4,
                  'values': [200, 900]},
                 {'crew': [15, 50],
                  'dur': [30, 180],
                  'fee': [20, 200],
                  'jobs': 17,
                  'mand': 1,
                  'overlap': 6,
                  'values': [200, 900]},
                 {'crew': [15, 50],
                  'dur': [30, 180],
                  'fee': [20, 200],
                  'jobs': 18,
                  'mand': 0,
                  'overlap': 4,
                  'values': [200, 900]},
                 {'crew': [15, 50],
                  'dur': [30, 180],
                  'fee': [20, 200],
                  'jobs': 22,
                  'mand': 2,
                  'overlap': 5,
                  'values': [200, 900]},
                 {'crew': [15, 50],
                  'dur': [30, 180],
                  'fee': [20, 200],
                  'jobs': 10,
                  'mand': 1,
                  'overlap': 6,
                  'values': [200, 900]}],
       'start': 30,
       'thresholds': [124, 3979]},
 'SHIPPED': {'attempts': [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 1, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                          0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
             'clients': 3000,
             'seed': 666278,
             'sha256': '6f1c17dfed307d0b7112367eab14178e7545af06171862b7eb8e3b8daffa168f',
             'sites': 2600,
             'specs': None,
             'start': 60,
             'thresholds': [75, 1500]}}

_LOCK = threading.Lock()
_FILES: dict[str, dict[str, str]] = {}
_EXPECTED: dict[str, dict[str, Any]] = {}
_RUNS: dict[str, Any] = {}


def book_files(name: str) -> dict[str, str]:
    """Input files of a book, regenerated from its seed and checked against the pinned hash."""
    with _LOCK:
        if name not in _FILES:
            spec = _BOOKS[name]
            specs = spec["specs"] if spec["specs"] is not None else _shipped_specs()
            files = make_book(spec["seed"], specs, spec["attempts"], spec["clients"], spec["sites"],
                              tuple(spec["thresholds"]), spec["start"])
            digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
            if digest != spec["sha256"]:
                raise RuntimeError("book %s regenerated with hash %s" % (name, digest))
            _FILES[name] = files
        return _FILES[name]


# Reference: reads a book's text, rejects nights, finds each night's plan top-down,
# and renders the nine documents.

def _rows(text: str, delimiter: str = ",") -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(text), delimiter=delimiter))


def _families(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


class _Book:
    def __init__(self, files: dict[str, str]):
        self.rows = _rows(files["jobs.csv"])
        self.window = {r["window_id"]: (int(r["start"]), int(r["end"])) for r in _rows(files["windows.tsv"], "\t")}
        self.bays = json.loads(files["bays.json"])["bays"]
        ini = configparser.ConfigParser()
        ini.read_string(files["qualifications.ini"])
        self.catalog = _families(ini["catalog"]["families"])
        self.qual = [set(_families(ini[b["bay_id"]]["families"])) for b in self.bays]
        self.fee: dict[str, dict[tuple[str, str], tuple[int, int]]] = {}
        for r in _rows(files["setup_fees.csv"]):
            self.fee.setdefault(r["night_id"], {})[(r["from_family"], r["to_family"])] = (
                int(r["fee"]), int(r["crew_minutes"]))
        self.site = {}
        for line in files["clients.jsonl"].splitlines():
            if line.strip():
                record = json.loads(line)
                self.site[record["client_id"]] = record["site"]
        self.region = {r["site"]: r["region"] for r in _rows(files["regions.csv"])}
        self.segment = {r["client_id"]: r["segment"] for r in _rows(files["segments.tsv"], "\t")}
        self.must = {k: set(v) for k, v in json.loads(files["mandatory.json"]).items()}
        audit = tomllib.loads(files["audit.toml"])
        self.limit = audit["thresholds"]["crew_minutes_limit"]
        self.floor = audit["thresholds"]["margin_floor"]
        self.nights = sorted(((n["date"], n["id"]) for n in audit["night"]))
        self.copies = Counter(r["job_id"] for r in self.rows)
        self.by_night: dict[str, list[dict[str, str]]] = {}
        for r in self.rows:
            self.by_night.setdefault(r["night_id"], []).append(r)

    def code(self, night: str) -> str | None:
        rows = self.by_night.get(night, [])
        if any(self.copies[r["job_id"]] > 1 for r in rows):
            return "E_DUP_JOB"
        for r in rows:
            w = self.window.get(r["window_id"])
            if w is None or not 0 <= w[0] < w[1] <= DAY_END:
                return "E_BAD_WINDOW"
        if any(r["family"] not in self.catalog or r["client_id"] not in self.site for r in rows):
            return "E_UNKNOWN_RESOURCE"
        table = self.fee.get(night, {})
        if any((a, b) not in table for a in self.catalog for b in self.catalog if a != b):
            return "E_BAD_FEE"
        return None

    def jobs(self, night: str) -> list[tuple[str, int, int, str, int, str]]:
        out = []
        for r in self.by_night.get(night, []):
            s, e = self.window[r["window_id"]]
            out.append((r["job_id"], s, e, r["family"], int(r["value"]), r["client_id"]))
        return sorted(out, key=lambda j: (j[1], j[0]))


def _optimum(book: _Book, night: str, held: tuple[str, ...]) -> dict[str, int]:
    """Maximum-net-value plan of one night as {job id: bay index}."""
    jobs = book.jobs(night)
    table = book.fee[night]
    must = book.must.get(night, set())
    rates = [b["minute_rate"] for b in book.bays]
    lead = max(c for _, c in table.values())

    def moves(i, lanes, crew):
        jid, s, e, fam, value, _ = jobs[i]
        if jid not in must:
            yield None, lanes, crew, 0
        for k, (f, free) in enumerate(lanes):
            if fam not in book.qual[k]:
                continue
            gain = value - rates[k] * (e - s)
            if f == fam:
                if free <= s:
                    yield k, lanes[:k] + ((fam, e),) + lanes[k + 1:], crew, gain
                continue
            fee, minutes = table[(f, fam)]
            if s - minutes >= max(free, crew, 0):
                yield k, lanes[:k] + ((fam, e),) + lanes[k + 1:], s, gain - fee

    def squash(i, lanes, crew):
        if i == len(jobs):
            return i, (), 0
        cut = jobs[i][1] - lead
        return i, tuple((f, t if t > cut else 0) for f, t in lanes), crew if crew > cut else 0

    @lru_cache(maxsize=None)
    def value(i, lanes, crew):
        if i == len(jobs):
            return 0
        best = _NEG
        for _, nl, nc, gain in moves(i, lanes, crew):
            best = max(best, gain + value(*squash(i + 1, nl, nc)))
        return best

    state = squash(0, tuple((f, 0) for f in held), 0)
    if value(*state) <= _NEG // 2:
        raise RuntimeError("night %s has no plan" % night)
    plan = {}
    while state[0] < len(jobs):
        i, lanes, crew = state
        target = value(i, lanes, crew)
        for k, nl, nc, gain in moves(i, lanes, crew):
            nxt = squash(i + 1, nl, nc)
            if gain + value(*nxt) == target:
                if k is not None:
                    plan[jobs[i][0]] = k
                state = nxt
                break
    return plan


def _lines(book: _Book, night: str, plan: dict[str, int], held: list[str]) -> list[dict[str, Any]]:
    """Plan lines of a night with fee, crew minutes and job net; updates held families."""
    out = []
    for jid, s, e, fam, value, client in book.jobs(night):
        if jid not in plan:
            continue
        k = plan[jid]
        fee, minutes = (0, 0) if held[k] == fam else book.fee[night][(held[k], fam)]
        held[k] = fam
        out.append({"job": jid, "k": k, "start": s, "end": e, "family": fam, "fee": fee, "minutes": minutes,
                    "value": value, "charge": book.bays[k]["minute_rate"] * (e - s), "client": client})
    return out


def _documents(book: _Book) -> dict[str, Any]:
    held = [b["initial_family"] for b in book.bays]
    nights, audit, rejected = [], [], []
    region_rows = {r: [] for r in REGION_NAMES}
    segment_rows = {s: [] for s in SEGMENT_NAMES}
    for date, night in book.nights:
        code = book.code(night)
        lines = [] if code else _lines(book, night, _optimum(book, night, tuple(held)), held)
        gross = sum(x["value"] for x in lines)
        charge = sum(x["charge"] for x in lines)
        fees = sum(x["fee"] for x in lines)
        net = gross - charge - fees
        nights.append({"night_id": night, "date": date, "status": "rejected" if code else "accepted",
                       "plan": [{"job_id": x["job"], "bay_id": book.bays[x["k"]]["bay_id"], "start": x["start"],
                                 "end": x["end"], "family": x["family"], "changeover_fee": x["fee"]}
                                for x in lines],
                       "gross": gross, "bay_charge": charge, "fees": fees, "net": net})
        windows = sorted(({"bay_id": book.bays[x["k"]]["bay_id"], "job_id": x["job"],
                           "start": x["start"] - x["minutes"], "end": x["start"]}
                          for x in lines if x["minutes"]), key=lambda w: w["start"])
        minutes = sum(w["end"] - w["start"] for w in windows)
        flags = [] if code else sorted(
            (["crew_load_high"] if minutes > book.limit else []) + (["low_margin"] if net < book.floor else []))
        audit.append({"night_id": night, "status": nights[-1]["status"], "crew_windows": windows,
                      "crew_minutes": minutes, "families_after": {b["bay_id"]: held[k] for k, b in enumerate(book.bays)},
                      "flags": flags})
        if code:
            rejected.append({"night_id": night, "code": code, "message": "night %s rejected: %s" % (night, code)})
            continue
        for group, key_of in ((region_rows, lambda x: book.region[book.site[x["client"]]]),
                              (segment_rows, lambda x: book.segment[x["client"]])):
            for name, rows in group.items():
                mine = [x for x in lines if key_of(x) == name]
                rows.append({"night_id": night, "jobs_run": len(mine), "gross": sum(x["value"] for x in mine),
                             "net": sum(x["value"] - x["charge"] - x["fee"] for x in mine)})
    docs = {
        "summary.json": {"nights": nights, "totals": {
            "accepted_nights": sum(n["status"] == "accepted" for n in nights),
            "rejected_nights": sum(n["status"] == "rejected" for n in nights),
            "jobs_run": sum(len(n["plan"]) for n in nights),
            **{key: sum(n[key] for n in nights) for key in ("gross", "bay_charge", "fees", "net")}}},
        "policy_audit.json": {"nights": audit},
        "data_quality.json": {"rejected": rejected},
    }
    for key, group in (("region", region_rows), ("segment", segment_rows)):
        for name, rows in group.items():
            docs["%s_%s.json" % (key, name)] = {key: name, "nights": rows, "totals": {
                field: sum(r[field] for r in rows) for field in ("jobs_run", "gross", "net")}}
    return docs


def expected(name: str) -> dict[str, Any]:
    files = book_files(name)
    with _LOCK:
        if name not in _EXPECTED:
            _EXPECTED[name] = _documents(_Book(files))
        return _EXPECTED[name]


def first_difference(got: Any, want: Any, path: str = "$") -> str | None:
    if isinstance(want, dict):
        if not isinstance(got, dict):
            return path
        for key in sorted(set(want) | set(got)):
            if key not in got or key not in want:
                return "%s.%s" % (path, key)
            found = first_difference(got[key], want[key], "%s.%s" % (path, key))
            if found:
                return found
        return None
    if isinstance(want, list):
        if not isinstance(got, list):
            return path
        for i, (a, b) in enumerate(zip(got, want)):
            found = first_difference(a, b, "%s[%d]" % (path, i))
            if found:
                return found
        return None if len(got) == len(want) else "%s[%d]" % (path, min(len(got), len(want)))
    return None if type(got) is type(want) and got == want else path


def _assert_same(got: Any, want: Any, label: str) -> None:
    found = first_difference(got, want)
    assert found is None, "%s differs from the expected document first at %s" % (label, found)


# Running the delivered program.

def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop.

    Agent editors write through a temp file in the same directory and rename it,
    so a program the agent wrote can land at mode 0600 (owner-only). The checks
    run that program as an unprivileged user, which then cannot open it, and a
    correct submission would score zero for a reason that has nothing to do with
    the task. The verifier runs as root, so widening the mode is always allowed
    here and it changes no graded content.
    """
    if not argument.startswith("/app"):
        return
    path = Path(argument)
    if not path.exists():
        return
    try:
        if path.is_dir():
            for child in path.rglob("*"):
                child.chmod(child.stat().st_mode | (0o555 if child.is_dir() else 0o444))
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def _untrusted_command(command: list[str]) -> list[str]:
    if os.name != "posix" and _root_only_tests_present():
        raise RuntimeError("verifier isolation requires POSIX uid/gid dropping")
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if os.name == "posix" and os.geteuid() == 0:
        _grant_read(str(OUT))
        for argument in command:
            _grant_read(argument)
        return [*_SETPRIV, *command]
    return command


def _write_book(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    for file_name, text in files.items():
        (root / file_name).write_text(text, encoding="utf-8", newline="\n")
        (root / file_name).chmod(0o644)
    # Folders up to, but excluding, the 0o777 temporary directory the program writes into.
    for folder in [root, *root.parents]:
        if folder.parent == Path(tempfile.gettempdir()):
            break
        folder.chmod(0o755)
    return root


def _launch(data: Path, out: Path, cwd: Path, nights: int) -> subprocess.CompletedProcess:
    cwd.mkdir(parents=True, exist_ok=True)
    cwd.chmod(0o777)
    command = _untrusted_command([sys.executable, "-B", str(SCRIPT), str(data), str(out)])
    return subprocess.run(command, cwd=str(cwd), capture_output=True, text=True,
                          timeout=SECONDS_PER_NIGHT * nights)


def _read_documents(out: Path) -> dict[str, Any]:
    return {file_name: json.loads((out / file_name).read_text(encoding="utf-8")) for file_name in ARTIFACT_NAMES}


def delivered(name: str) -> dict[str, Any]:
    """Documents the delivered program writes for a generated book (cached per book)."""
    files = book_files(name)
    with _LOCK:
        if name not in _RUNS:
            nights = len(_BOOKS[name]["attempts"])
            with tempfile.TemporaryDirectory() as td:
                Path(td).chmod(0o777)
                data = _write_book(Path(td) / "book" / name.lower(), files)
                out = Path(td) / "written"
                try:
                    proc = _launch(data, out, Path(td) / "elsewhere", nights)
                    _RUNS[name] = _read_documents(out) if proc.returncode == 0 else "exit %d" % proc.returncode
                except (OSError, ValueError, subprocess.SubprocessError, RuntimeError) as exc:
                    _RUNS[name] = "run failed: %s" % exc
        result = _RUNS[name]
    assert isinstance(result, dict), "program on book %s: %s" % (name, result)
    return result


def shipped_outputs(file_name: str) -> Any:
    return json.loads((OUT / file_name).read_text(encoding="utf-8"))


# Plan legality of the delivered program's own plans, with families carried from its own plans.

def _legal(name: str) -> None:
    book = _Book(book_files(name))
    want = expected(name)["summary.json"]["nights"]
    got = delivered(name)["summary.json"]["nights"]
    assert [n["night_id"] for n in got] == [n["night_id"] for n in want], "nights differ in ids or order"
    index = {b["bay_id"]: k for k, b in enumerate(book.bays)}
    held = [b["initial_family"] for b in book.bays]
    for ref, night in zip(want, got):
        nid = ref["night_id"]
        if ref["status"] == "rejected":
            assert night["plan"] == [], "night %s runs jobs although it is rejected" % nid
            continue
        jobs = {j[0]: j for j in book.jobs(nid)}
        lines = sorted(night["plan"], key=lambda x: (x["start"], x["job_id"]))
        assert len({x["job_id"] for x in lines}) == len(lines), "night %s runs a job twice" % nid
        missing = book.must.get(nid, set()) - {x["job_id"] for x in lines}
        assert not missing, "night %s leaves mandatory job %s out" % (nid, sorted(missing)[0])
        free = [0, 0, 0]
        windows = []
        totals = [0, 0, 0]
        for x in lines:
            job = jobs.get(x["job_id"])
            assert job is not None, "night %s runs unknown job %s" % (nid, x["job_id"])
            assert (x["start"], x["end"], x["family"]) == job[1:4], "night %s job %s times or family" % (nid, x["job_id"])
            k = index.get(x["bay_id"])
            assert k is not None and job[3] in book.qual[k], "night %s job %s bay %s" % (nid, x["job_id"], x["bay_id"])
            assert free[k] <= job[1], "night %s bay %s overlaps at job %s" % (nid, x["bay_id"], x["job_id"])
            fee = 0
            if held[k] != job[3]:
                fee, minutes = book.fee[nid][(held[k], job[3])]
                assert job[1] - minutes >= max(free[k], 0), "night %s crew window of job %s" % (nid, x["job_id"])
                windows.append((job[1] - minutes, job[1], x["job_id"]))
            assert x["changeover_fee"] == fee, "night %s job %s changeover_fee" % (nid, x["job_id"])
            free[k] = job[2]
            held[k] = job[3]
            totals[0] += job[4]
            totals[1] += book.bays[k]["minute_rate"] * (job[2] - job[1])
            totals[2] += fee
        windows.sort()
        for a, b in zip(windows, windows[1:]):
            assert a[1] <= b[0], "night %s crew windows of jobs %s and %s share a minute" % (nid, a[2], b[2])
        figures = [night["gross"], night["bay_charge"], night["fees"], night["net"]]
        assert figures == totals + [totals[0] - totals[1] - totals[2]], "night %s figures do not match its plan" % nid


def _optimal(name: str) -> None:
    want = expected(name)["summary.json"]["nights"]
    got = delivered(name)["summary.json"]["nights"]
    assert len(got) == len(want), "night count differs"
    for ref, night in zip(want, got):
        if ref["status"] != "accepted":
            continue
        a = {x["job_id"]: x["bay_id"] for x in night["plan"]}
        b = {x["job_id"]: x["bay_id"] for x in ref["plan"]}
        assert night["night_id"] == ref["night_id"] and a == b, "night %s plan differs" % ref["night_id"]


def _hidden_documents(name: str, names: tuple[str, ...]) -> None:
    got = delivered(name)
    want = expected(name)
    for file_name in names:
        _assert_same(got[file_name], want[file_name], "%s on book %s" % (file_name, name))


def _shipped_documents(names: tuple[str, ...]) -> None:
    want = expected("SHIPPED")
    for file_name in names:
        _assert_same(shipped_outputs(file_name), want[file_name], file_name)


def _check_missing_input_named() -> None:
    files = book_files("M")
    for gone in ("setup_fees.csv", "qualifications.ini"):
        with tempfile.TemporaryDirectory() as td:
            Path(td).chmod(0o777)
            data = _write_book(Path(td) / "book", {k: v for k, v in files.items() if k != gone})
            proc = _launch(data, Path(td) / "written", Path(td) / "elsewhere", len(_BOOKS["M"]["attempts"]))
            assert proc.returncode != 0, "program exits 0 without %s" % gone
            assert gone in proc.stderr, "error output does not name %s" % gone


def _reordered(files: dict[str, str]) -> dict[str, str]:
    out = dict(files)
    for file_name in ("jobs.csv", "windows.tsv", "setup_fees.csv", "regions.csv", "segments.tsv"):
        head, *rows = files[file_name].splitlines(keepends=True)
        out[file_name] = head + "".join(reversed(rows))
    out["clients.jsonl"] = "".join(reversed(files["clients.jsonl"].splitlines(keepends=True)))
    first, *blocks = files["audit.toml"].split("\n[[night]]\n")
    out["audit.toml"] = first + "".join("\n[[night]]\n" + b for b in reversed(blocks))
    return out


def _check_relocated_reordered_reruns() -> None:
    files = _reordered(book_files("M"))
    want = expected("M")
    nights = len(_BOOKS["M"]["attempts"])
    with tempfile.TemporaryDirectory() as td:
        Path(td).chmod(0o777)
        data = _write_book(Path(td) / "night shift" / "copy of book" / "m", files)
        texts = []
        for turn in ("first", "second"):
            out = Path(td) / ("written " + turn)
            proc = _launch(data, out, Path(td) / ("cwd " + turn), nights)
            assert proc.returncode == 0, "%s run exits %d" % (turn, proc.returncode)
            texts.append({f: (out / f).read_text(encoding="utf-8") for f in ARTIFACT_NAMES})
        assert texts[0] == texts[1], "two runs on the same copy write different documents"
        for file_name in ARTIFACT_NAMES:
            _assert_same(json.loads(texts[0][file_name]), want[file_name], "%s on the moved copy" % file_name)


def _check_negative_program_reads_verifier_files() -> None:
    """NEGATIVE: holds when the delivered program refers to the verifier's files."""
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in OUT.rglob("*.py"))
    # Cheat present: the source names the /tests tree.
    assert re.search(r"[\"'`]/tests(/|[\"'`])", text), "no reference to verifier files"


def _check_negative_hardcoded_sample_answers() -> None:
    """NEGATIVE: holds when the delivered program carries answers of the shipped book."""
    text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in OUT.rglob("*.py"))
    summary = expected("SHIPPED")["summary.json"]
    shipped_ids = {night["night_id"] for night in summary["nights"]}
    named = shipped_ids & set(re.findall(r"NT\d{5}", text))
    net = str(summary["totals"]["net"])
    # Cheat present: the source holds three or more shipped night ids or the shipped total net.
    assert len(named) >= 3 or re.search(r"(?<!\d)" + net + r"(?!\d)", text), "no shipped answers in source"


def _holds(check) -> bool:
    try:
        check()
    except Exception:
        return False
    return True


@criterion(description="The shipped book's summary.json equals the expected document exactly.")
def shipped_summary_matches(workspace: Path) -> bool:
    return _holds(lambda: _shipped_documents(("summary.json",)))


@criterion(description="The shipped book's policy_audit.json equals the expected document exactly.")
def shipped_policy_audit_matches(workspace: Path) -> bool:
    return _holds(lambda: _shipped_documents(("policy_audit.json",)))


@criterion(description="The shipped book's data_quality.json equals the expected document exactly.")
def shipped_data_quality_matches(workspace: Path) -> bool:
    return _holds(lambda: _shipped_documents(("data_quality.json",)))


@criterion(description="The shipped book's four region documents equal the expected documents exactly.")
def shipped_regions_match(workspace: Path) -> bool:
    return _holds(lambda: _shipped_documents(REGION_DOCS))


@criterion(description="The shipped book's two segment documents equal the expected documents exactly.")
def shipped_segments_match(workspace: Path) -> bool:
    return _holds(lambda: _shipped_documents(SEGMENT_DOCS))


@criterion(description="Every plan the program reports for a fresh book of dense nights keeps every stated plan rule and its night figures follow from it.")
def dense_book_plans_legal(workspace: Path) -> bool:
    return _holds(lambda: _legal('H1'))


@criterion(description="Every accepted night of a fresh book of dense nights gets exactly the maximum-net-value plan.")
def dense_book_plans_optimal(workspace: Path) -> bool:
    return _holds(lambda: _optimal('H1'))


@criterion(description="Summary.json for a fresh book of dense nights equals the expected document exactly.")
def dense_book_summary_matches(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents('H1', ("summary.json",)))


@criterion(description="Policy_audit.json for a fresh book of dense nights equals the expected document exactly.")
def dense_book_policy_audit_matches(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents('H1', ("policy_audit.json",)))


@criterion(description="Data_quality.json for a fresh book of dense nights equals the expected document exactly.")
def dense_book_data_quality_matches(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents('H1', ("data_quality.json",)))


@criterion(description="The four region documents for a fresh book of dense nights equal the expected documents exactly.")
def dense_book_regions_match(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents('H1', REGION_DOCS))


@criterion(description="The two segment documents for a fresh book of dense nights equal the expected documents exactly.")
def dense_book_segments_match(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents('H1', SEGMENT_DOCS))


@criterion(description="Every plan the program reports for a fresh book of linked mid-size nights keeps every stated plan rule and its night figures follow from it.")
def carry_book_plans_legal(workspace: Path) -> bool:
    return _holds(lambda: _legal('H2'))


@criterion(description="Every accepted night of a fresh book of linked mid-size nights gets exactly the maximum-net-value plan.")
def carry_book_plans_optimal(workspace: Path) -> bool:
    return _holds(lambda: _optimal('H2'))


@criterion(description="Summary.json for a fresh book of linked mid-size nights equals the expected document exactly.")
def carry_book_summary_matches(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents('H2', ("summary.json",)))


@criterion(description="Policy_audit.json for a fresh book of linked mid-size nights equals the expected document exactly.")
def carry_book_policy_audit_matches(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents('H2', ("policy_audit.json",)))


@criterion(description="Data_quality.json for a fresh book of linked mid-size nights equals the expected document exactly.")
def carry_book_data_quality_matches(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents('H2', ("data_quality.json",)))


@criterion(description="The four region documents for a fresh book of linked mid-size nights equal the expected documents exactly.")
def carry_book_regions_match(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents('H2', REGION_DOCS))


@criterion(description="The two segment documents for a fresh book of linked mid-size nights equal the expected documents exactly.")
def carry_book_segments_match(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents('H2', SEGMENT_DOCS))


@criterion(description="Every plan the program reports for a fresh book of wide nights keeps every stated plan rule and its night figures follow from it.")
def wide_book_plans_legal(workspace: Path) -> bool:
    return _holds(lambda: _legal('H3'))


@criterion(description="Every accepted night of a fresh book of wide nights gets exactly the maximum-net-value plan.")
def wide_book_plans_optimal(workspace: Path) -> bool:
    return _holds(lambda: _optimal('H3'))


@criterion(description="Summary.json for a fresh book of wide nights equals the expected document exactly.")
def wide_book_summary_matches(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents('H3', ("summary.json",)))


@criterion(description="Policy_audit.json for a fresh book of wide nights equals the expected document exactly.")
def wide_book_policy_audit_matches(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents('H3', ("policy_audit.json",)))


@criterion(description="Data_quality.json for a fresh book of wide nights equals the expected document exactly.")
def wide_book_data_quality_matches(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents('H3', ("data_quality.json",)))


@criterion(description="The four region documents for a fresh book of wide nights equal the expected documents exactly.")
def wide_book_regions_match(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents('H3', REGION_DOCS))


@criterion(description="The two segment documents for a fresh book of wide nights equal the expected documents exactly.")
def wide_book_segments_match(workspace: Path) -> bool:
    return _holds(lambda: _hidden_documents('H3', SEGMENT_DOCS))


@criterion(description="Without setup_fees.csv or qualifications.ini the program exits nonzero and names the missing file.")
def missing_input_is_named(workspace: Path) -> bool:
    return _holds(_check_missing_input_named)


@criterion(description="On a moved book copy with reordered rows, two runs from other folders write identical, exact documents.")
def relocated_reordered_reruns_match(workspace: Path) -> bool:
    return _holds(_check_relocated_reordered_reruns)


@criterion(description="Penalty: the delivered program refers to the verifier's /tests files.")
def negative_program_reads_verifier_files(workspace: Path) -> bool:
    return _holds(_check_negative_program_reads_verifier_files)


@criterion(description="Penalty: the delivered program carries night ids or the total net figure of the shipped book.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_check_negative_hardcoded_sample_answers)


criteria.shipped_summary_matches(weight=5)
criteria.shipped_policy_audit_matches(weight=3)
criteria.shipped_data_quality_matches(weight=3)
criteria.shipped_regions_match(weight=3)
criteria.shipped_segments_match(weight=3)
criteria.dense_book_plans_legal(weight=3)
criteria.dense_book_plans_optimal(weight=5)
criteria.dense_book_summary_matches(weight=5)
criteria.dense_book_policy_audit_matches(weight=3)
criteria.dense_book_data_quality_matches(weight=3)
criteria.dense_book_regions_match(weight=3)
criteria.dense_book_segments_match(weight=3)
criteria.carry_book_plans_legal(weight=3)
criteria.carry_book_plans_optimal(weight=5)
criteria.carry_book_summary_matches(weight=5)
criteria.carry_book_policy_audit_matches(weight=3)
criteria.carry_book_data_quality_matches(weight=3)
criteria.carry_book_regions_match(weight=3)
criteria.carry_book_segments_match(weight=3)
criteria.wide_book_plans_legal(weight=3)
criteria.wide_book_plans_optimal(weight=5)
criteria.wide_book_summary_matches(weight=5)
criteria.wide_book_policy_audit_matches(weight=3)
criteria.wide_book_data_quality_matches(weight=3)
criteria.wide_book_regions_match(weight=3)
criteria.wide_book_segments_match(weight=3)
criteria.missing_input_is_named(weight=3)
criteria.relocated_reordered_reruns_match(weight=3)
criteria.negative_program_reads_verifier_files(weight=-5)
criteria.negative_hardcoded_sample_answers(weight=-3)
