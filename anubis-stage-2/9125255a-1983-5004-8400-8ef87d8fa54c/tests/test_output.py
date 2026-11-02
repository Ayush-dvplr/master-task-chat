from __future__ import annotations

import csv as _csvmod
import hashlib as _hl
import io as _io
import json as _json
import os as _os
import shutil as _shutil
import signal as _signal
import subprocess as _sp
import sys as _sys
import tempfile as _tf
from pathlib import Path

from rewardkit import criteria, criterion

SAMPLE_SEED = int("666221015145503004")
CHALLENGE_SEED = int("2940160787198449735")
EVAL_SEED = int("3619608109873697086")
APP_ROOT = Path(_os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
PROGRAM = OUT_DIR / "certify.py"
VISIBLE_SCALE = 1.0
HIDDEN_SCALE = 0.35
RUN_TIMEOUT = 1200
OUTPUTS = ["lineage.json", "job_dispositions.jsonl", "item_eligibility.jsonl", "item_scores.jsonl", "benchmark_metrics.json",
           "calibration.json", "pairwise.json", "significance.json", "leaderboard.csv", "release_gates.json",
           "slice_metrics.json", "source_audit.json", "control_reconciliation.json"]
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]


# ===== CORPUS GENERATOR BEGIN =====
# Seeded generator for the Heron Q3 2025 evaluation certification close corpus.
# Everything below is stdlib only and byte-deterministic for a given seed.
import calendar
import datetime as _dt
import hashlib
import io
import json
import math
import os
import sqlite3
import struct
import tempfile
import time
import unicodedata
import zipfile
import zlib
from decimal import ROUND_HALF_EVEN, Decimal
from fractions import Fraction

MASK64 = (1 << 64) - 1


class Rng:
    __slots__ = ("s",)

    def __init__(self, seed):
        self.s = seed & MASK64

    def u64(self):
        self.s = (self.s + 0x9E3779B97F4A7C15) & MASK64
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
        return z ^ (z >> 31)

    def rand(self):
        return (self.u64() >> 11) * (1.0 / 9007199254740992.0)

    def below(self, n):
        return self.u64() % n

    def randint(self, a, b):
        return a + self.below(b - a + 1)

    def choice(self, seq):
        return seq[self.below(len(seq))]

    def chance(self, p):
        return self.rand() < p

    def shuffle(self, lst):
        for i in range(len(lst) - 1, 0, -1):
            j = self.below(i + 1)
            lst[i], lst[j] = lst[j], lst[i]
        return lst

    def weighted(self, pairs):
        total = sum(w for _, w in pairs)
        x = self.rand() * total
        for v, w in pairs:
            x -= w
            if x < 0:
                return v
        return pairs[-1][0]

    def hexid(self, n):
        return "".join("0123456789abcdef"[self.below(16)] for _ in range(n))


def derive(seed, tag):
    h = hashlib.blake2b(f"{seed}|{tag}".encode(), digest_size=8).digest()
    return Rng(int.from_bytes(h, "big"))


def T(y, m, d, h=0, mi=0, s=0):
    return calendar.timegm((y, m, d, h, mi, s, 0, 0, 0))


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def iso_week(t):
    return _dt.datetime.fromtimestamp(t, _dt.timezone.utc).isocalendar()[1]


def q6(fr):
    """Rational -> float quantized to 6 dp, half-even (the reporting rule)."""
    d = Decimal(fr.numerator) / Decimal(fr.denominator) if isinstance(fr, Fraction) else Decimal(str(fr))
    return float(d.quantize(Decimal("0.000001"), rounding=ROUND_HALF_EVEN))


def qd(fr, places):
    d = Decimal(fr.numerator) / Decimal(fr.denominator)
    return d.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)


WINDOW_START = T(2025, 7, 1)
WINDOW_END = T(2025, 10, 1)
CUTOFF = T(2025, 10, 3, 18, 0, 0)
WEEKS = list(range(27, 41))  # ISO weeks touched by the window (W27 starts 2025-06-30)

CANDIDATES = ["heron-7b-sft", "heron-7b-dpo", "heron-13b-sft", "heron-13b-dpo",
              "heron-34b-sft", "heron-34b-rlhf", "heron-34b-rlhf-ema"]
BASELINE = "osprey-13b-prod"
MODELS = CANDIDATES + [BASELINE]
FAMILY = {"heron-7b-sft": "7b", "heron-7b-dpo": "7b", "heron-13b-sft": "13b", "heron-13b-dpo": "13b",
          "heron-34b-sft": "34b", "heron-34b-rlhf": "34b", "heron-34b-rlhf-ema": "34b", BASELINE: "osp13"}
CTX_WINDOW = {"7b": 8192, "13b": 16384, "34b": 32768, "osp13": 16384}
TOKENIZER = {"7b": "hbpe", "13b": "hbpe", "34b": "hbpe", "osp13": "ospsp"}

# benchmark key, id prefix, item count at scale 1, fleet that runs it
BENCHES = [("arith", "ARI", 1800, "a"), ("code", "COD", 500, "d"), ("intent", "INT", 2100, "a"),
           ("safety", "SAF", 1500, "b"), ("mcq", "MCQ", 1700, "b"), ("pref", "PRF", 900, "j"),
           ("longctx", "LCX", 1200, "c"), ("multiling", "MLG", 1400, "c")]
BENCH_KEYS = [b[0] for b in BENCHES]
PREFIX = {b[0]: b[1] for b in BENCHES}
PREFIX_BENCH = {b[1]: b[0] for b in BENCHES}
BENCH_FLEET = {b[0]: b[3] for b in BENCHES}
GATED = ["arith", "mcq", "longctx", "multiling"]
SLICE_BENCHES = ["arith", "mcq", "longctx", "multiling"]
INTENT_CLASSES = ["billing", "cancel", "complaint", "delivery", "greeting", "hours", "login",
                  "order_status", "refund", "reset_password", "shipping_cost", "upgrade"]
LANGS = ["de", "es", "fr", "he", "hi", "id", "ja", "pt", "ru", "sw"]
DOMAINS = ["everyday", "finance", "health", "law", "science", "tech"]
DIFFICULTY = ["easy", "medium", "hard"]
REGIONS = ["APAC", "EU", "LATAM", "MEA", "NA"]
TZ_OFFSET = {"UTC": 0, "Europe/Berlin": 7200, "America/Chicago": -18000, "Asia/Kolkata": 19800,
             "America/Sao_Paulo": -10800}
LOCALES = ["en_US", "de_DE", "fr_FR", "en_IN"]
HARNESS = ["h3.1", "h3.2", "h4.0"]
REASONS = ["retired", "duplicate", "contaminated", "out_of_scope"]
DISPOSITIONS = ["voided", "staging_host", "stale_checkpoint", "outside_window", "maintenance",
                "superseded", "rerun_denied", "authoritative"]
HOMO = {"A": "\u0410", "C": "\u0421", "E": "\u0415", "O": "\u041e", "P": "\u0420", "J": "\u0408",
        "M": "\u041c", "T": "\u0422", "H": "\u041d", "K": "\u041a", "X": "\u0425", "B": "\u0412"}

# ---------------------------------------------------------------------------------
# canonical world
# ---------------------------------------------------------------------------------
SYL = ["ka", "lo", "mi", "ra", "te", "su", "no", "vi", "da", "pe", "zu", "ho", "ri", "an", "el", "or",
       "ta", "ne", "si", "bu", "ga", "fe", "ju", "ly"]
ACC = {"de": "\u00e4\u00f6\u00fc\u00df", "fr": "\u00e9\u00e8\u00ea\u00e7", "es": "\u00f1\u00e1\u00ed\u00f3",
       "pt": "\u00e3\u00f5\u00e7\u00e1", "sw": "", "id": "", "hi": "\u0101\u012b\u016b", "ja": "\u014d\u016b",
       "he": "", "ru": "\u0436\u0448\u044b\u043b"}


class World:
    pass


def _word(r, lang=None, n=None):
    n = n or r.randint(2, 4)
    w = "".join(r.choice(SYL) for _ in range(n))
    if lang and ACC.get(lang) and r.chance(0.75):
        pos = r.below(len(w))
        w = w[:pos] + r.choice(ACC[lang]) + w[pos + 1:]
    return w


def strip_marks(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm_answer(s, grader):
    s = unicodedata.normalize("NFC", s).casefold()
    if grader == "g3":
        s = unicodedata.normalize("NFC", strip_marks(s))
    s = " ".join(s.split())
    return s.strip(" .,;:!?\"'")


def build_world(seed, scale=1.0):
    W = World()
    W.seed, W.scale = seed, scale
    rh = derive(seed, "hosts")
    n_hosts = max(90, int(round(750 * scale)))
    W.hosts = [f"node-{i:04d}" for i in range(1, n_hosts + 1)]
    fleets = [("a", 22), ("b", 22), ("c", 17), ("d", 17), ("j", 12), ("s", 10)]
    tzs = [("UTC", 42), ("Europe/Berlin", 16), ("America/Chicago", 15), ("Asia/Kolkata", 15), ("America/Sao_Paulo", 12)]
    locs = [("en_US", 55), ("de_DE", 15), ("fr_FR", 14), ("en_IN", 16)]
    W.hw = {}
    W.host_base = {}
    for i, h in enumerate(W.hosts):
        base = fleets[i % 6][0] if i < 60 else rh.weighted(fleets)
        tz, loc = rh.weighted(tzs), rh.weighted(locs)
        W.host_base[h] = base
        for wk in WEEKS:
            if rh.chance(0.05):
                tz = rh.weighted(tzs)
            if rh.chance(0.05):
                loc = rh.weighted(locs)
            fl = base if (base == "s" or not rh.chance(0.04)) else "s"
            off = 0 if rh.chance(0.86) else rh.choice([-1, 1]) * (rh.randint(200, 999) if rh.chance(0.15) else rh.randint(1500, 400000))
            W.hw[(h, wk)] = {"fleet": fl, "tz": tz, "locale": loc,
                             "scale": 100 if rh.chance(0.12) else 1, "offset_ms": off}
    # maintenance windows: one per host-week, 2-6 hours
    W.maint = {}
    for h in W.hosts:
        for wk in WEEKS:
            monday = T(2025, 6, 30) + (wk - 27) * 7 * 86400
            st = monday + rh.randint(0, 6 * 86400 - 1)
            st -= st % 900
            W.maint[(h, wk)] = (st, st + rh.randint(2, 6) * 3600)

    # checkpoints ------------------------------------------------------------------
    rc = derive(seed, "ckpt")
    W.ckpts = {}
    W.ckpt_order = []
    target = max(1200, int(round(10000 * scale)))
    fams = ["7b", "13b", "34b", "osp13"]
    run_no = 0
    while len(W.ckpt_order) < target:
        fam = fams[run_no % 4]
        run = f"tr-{fam}-{run_no:03d}"
        prev = None
        steps = rc.randint(60, 140)
        t0 = T(2025, 5, 1) + rc.randint(0, 120) * 86400
        for k in range(steps):
            cid = "ck-" + rc.hexid(10)
            while cid in W.ckpts:
                cid = "ck-" + rc.hexid(10)
            W.ckpts[cid] = {"id": cid, "run": run, "family": fam, "step": (k + 1) * 500, "parent": prev,
                            "created_at": t0 + k * 3 * 3600, "ema": False, "ema_of": None}
            W.ckpt_order.append(cid)
            prev = cid
        run_no += 1
    # EMA twins for 34b checkpoints (registered only in the lineage snapshot)
    W.ema = {}
    for cid in list(W.ckpt_order):
        c = W.ckpts[cid]
        if c["family"] == "34b" and rc.chance(0.10):
            eid = "ck-" + rc.hexid(10)
            W.ckpts[eid] = {"id": eid, "run": c["run"], "family": "34b", "step": c["step"], "parent": None,
                            "created_at": c["created_at"] + 1800, "ema": True, "ema_of": cid}
            W.ema[eid] = cid
    fam_ckpts = {f: [c for c in W.ckpt_order if W.ckpts[c]["family"] == f] for f in fams}

    # promotions -------------------------------------------------------------------
    rp = derive(seed, "promo")
    W.promos = []  # dicts: tag, ckpt, action, at, ticket, approval(None|(verdict, t))
    W.certified = {}
    tick = rp.randint(10000, 20000)
    for m in MODELS:
        fam = FAMILY[m]
        pool = [e for e in W.ema] if m.endswith("-ema") else fam_ckpts[fam]
        n = rp.randint(2, 4)
        chosen = [rp.choice(pool) for _ in range(n)]
        times = sorted(rp.randint(T(2025, 6, 1), T(2025, 9, 20)) for _ in range(n))
        evs = []
        for i, (cid, at) in enumerate(zip(chosen, times)):
            tick += rp.randint(1, 40)
            last = i == n - 1
            kind = "approved" if last else rp.weighted([("approved", 5), ("rejected", 2), ("late", 1), ("none", 1)])
            ev = {"tag": m, "ckpt": cid, "action": "promote", "at": at, "ticket": f"CHG-{tick:05d}"}
            if kind == "approved":
                ev["approval"] = ("APPROVED", at + rp.randint(1800, 50 * 3600))
            elif kind == "rejected":
                ev["approval"] = ("REJECTED", at + rp.randint(1800, 50 * 3600))
            elif kind == "late":
                ev["approval"] = ("APPROVED", CUTOFF + rp.randint(60, 5 * 86400))
            else:
                ev["approval"] = None
            evs.append(ev)
        # the final approval sometimes lands exactly on the cutoff instant (inclusive)
        if rp.chance(0.25):
            evs[-1]["at"] = min(evs[-1]["at"], CUTOFF - 7200)
            evs[-1]["approval"] = ("APPROVED", CUTOFF)
        # a later rollback request that is never approved, or approved after the cutoff
        if rp.chance(0.5) and len(evs) > 1:
            tick += rp.randint(1, 40)
            at = evs[-1]["approval"][1] + rp.randint(3600, 3 * 86400)
            evs.append({"tag": m, "ckpt": evs[-2]["ckpt"], "action": "rollback", "at": min(at, CUTOFF + 86400),
                        "ticket": f"CHG-{tick:05d}",
                        "approval": rp.choice([None, ("REJECTED", at + 7200), ("APPROVED", CUTOFF + 3600 * rp.randint(1, 30))])})
        W.promos.extend(evs)
        eff = [(e["approval"][1], e) for e in evs if e["approval"] and e["approval"][0] == "APPROVED" and e["approval"][1] <= CUTOFF]
        eff.sort(key=lambda x: (x[0], x[1]["ticket"]))
        t_eff, e = eff[-1]
        W.certified[m] = {"checkpoint": e["ckpt"], "effective_from": t_eff, "approval_ref": e["ticket"],
                          "voided_promotions": sum(1 for x in evs if not (x["approval"] and x["approval"][0] == "APPROVED" and x["approval"][1] <= CUTOFF))}
        W.certified[m]["history"] = [x["ckpt"] for x in evs]
    # nightly tag noise events
    W.tag_noise = []
    n_noise = max(800, int(round(10300 * scale))) - len(W.promos)
    for i in range(n_noise):
        fam = fams[i % 4]
        cid = rp.choice(fam_ckpts[fam])
        at = T(2025, 6, 1) + rp.randint(0, 120 * 86400)
        nm = rp.choice([m for m in MODELS if FAMILY[m] == fam]) if rp.chance(0.15) else fam
        W.tag_noise.append({"tag": f"nightly-{nm}-{time.strftime('%Y%m%d', time.gmtime(at))}", "ckpt": cid,
                            "action": "retire" if rp.chance(0.1) else "promote", "at": at,
                            "ticket": f"AUTO-{i:06d}"})

    # items ------------------------------------------------------------------------
    ri = derive(seed, "items")
    W.items = {}
    W.bench_items = {}
    for bkey, pfx, n0, _f in BENCHES:
        n = max(60, int(round(n0 * scale)))
        nums = list(range(1, 99999))
        ri.shuffle(nums)
        ids = sorted(f"{pfx}-{x:05d}" for x in nums[:n])
        W.bench_items[bkey] = ids
        for iid in ids:
            it = {"id": iid, "bench": bkey, "domain": ri.choice(DOMAINS), "difficulty": ri.choice(DIFFICULTY),
                  "region": ri.choice(REGIONS), "lang": "en", "hard": ri.rand()}
            if bkey == "arith":
                mag = 10 ** ri.randint(0, 6)
                dp = ri.choice([0, 1, 2, 2])
                it["gold"] = Decimal(ri.randint(1, 9 * mag + 9)).scaleb(-dp).quantize(Decimal("0.01"))
                if ri.chance(0.12):
                    it["gold"] = -it["gold"]
                it["tol"] = ri.weighted([("exact", 60), ("abs", 25), ("rel", 15)])
                it["subtask"] = ri.choice(["add", "mul", "frac", "percent", "unit"])
            elif bkey == "code":
                it["tests"] = ri.randint(5, 20)
                it["subtask"] = ri.choice(["easy", "medium", "hard"])
            elif bkey == "intent":
                it["gold"] = ri.choice(INTENT_CLASSES)
                it["subtask"] = it["gold"]
            elif bkey == "safety":
                it["gold"] = 1 if ri.chance(0.3) else 0
                it["subtask"] = ri.choice(["violence", "self_harm", "fraud", "privacy", "benign"])
            elif bkey == "mcq":
                it["n_options"] = ri.choice([4, 4, 5])
                it["gold"] = "ABCDE"[ri.below(it["n_options"])]
                it["subtask"] = ri.choice(["biology", "history", "law", "math", "physics"])
            elif bkey == "pref":
                it["subtask"] = ri.choice(["writing", "coding", "advice", "roleplay"])
            elif bkey == "longctx":
                it["gold"] = ri.weighted([(_word(ri), 5), (_word(ri) + "-" + _word(ri), 3), (_word(ri) + " " + _word(ri), 2)])
                base = ri.randint(1500, 36000)
                it["tokens"] = {"hbpe": base, "ospsp": int(base * (1.04 + ri.rand() * 0.12))}
                if ri.chance(0.03):
                    it["tokens"]["hbpe"] = ri.choice([8192, 16384, 32768])
                if ri.chance(0.02):
                    it["tokens"]["ospsp"] = 16384
                it["subtask"] = ri.choice(["needle", "multi_hop", "summary_qa"])
            elif bkey == "multiling":
                it["lang"] = ri.choice(LANGS)
                it["gold"] = unicodedata.normalize("NFC", _word(ri, it["lang"]))
                it["subtask"] = it["lang"]
            if bkey != "longctx":
                base = ri.randint(40, 1400)
                it["tokens"] = {"hbpe": base, "ospsp": int(base * 1.08) + 1}
            W.items[iid] = it
    # eligibility facts
    W.retired = set()
    W.dup_of = {}
    W.contam = {}
    W.held_out = set()
    W.contam_threshold = {}
    for bkey in BENCH_KEYS:
        W.contam_threshold[bkey] = Decimal(ri.choice(["0.5500", "0.6000", "0.6500", "0.7000"]))
    for bkey in BENCH_KEYS:
        ids = W.bench_items[bkey]
        for iid in ids:
            if ri.chance(0.03):
                W.retired.add(iid)
            if ri.chance(0.03):
                W.held_out.add(iid)
        # dedup clusters: pick seeds, attach 1-2 near copies with larger ids
        k = max(2, len(ids) // 40)
        for _ in range(k):
            a = ri.below(len(ids) - 3)
            members = [ids[a]] + [ids[a + 1 + ri.below(2)]]
            if any(mm in W.dup_of or mm in W.dup_of.values() for mm in members):
                continue
            canon = min(members)
            for mm in members:
                if mm != canon:
                    W.dup_of[mm] = canon
        # contamination hits
        th = W.contam_threshold[bkey]
        for iid in ids:
            hits = []
            for _ in range(ri.weighted([(0, 50), (1, 35), (2, 12), (3, 3)])):
                ov = Decimal(ri.randint(500, 9999)).scaleb(-4)
                hits.append(ov)
            if ri.chance(0.02):
                hits.append(th)  # exactly at the threshold: contaminated (>=)
            if ri.chance(0.02):
                hits.append(th - Decimal("0.0001"))  # just under: clean
            W.contam[iid] = [(f"shard-{ri.randint(0, 4095):04d}", h) for h in hits]
    W.elig = {}
    for iid in sorted(W.items):
        b = W.items[iid]["bench"]
        reason = None
        if iid in W.retired:
            reason = "retired"
        elif iid in W.dup_of:
            reason = "duplicate"
        elif any(h >= W.contam_threshold[b] for _, h in W.contam[iid]):
            reason = "contaminated"
        elif iid in W.held_out:
            reason = "out_of_scope"
        W.elig[iid] = reason

    # skills -------------------------------------------------------------------------
    rs = derive(seed, "skill")
    W.skill = {}
    for i, m in enumerate(MODELS):
        for b in BENCH_KEYS:
            W.skill[(m, b)] = min(0.95, max(0.15, 0.42 + 0.05 * (i % 7) - (0.06 if m == BASELINE else 0) + rs.rand() * 0.25))
    W.overconf = {m: rs.choice([0.0, 0.02, 0.05, 0.09, 0.14]) for m in MODELS}
    W.grader_of_harness = {"h3.1": "g2", "h3.2": "g2", "h4.0": "g3"}

    _build_jobs(W, seed)
    _build_results(W, seed)
    return W


def clear_of_week_edge(t):
    """Keep submissions at least 15 hours away from a Monday 00:00 UTC week boundary."""
    if not (WINDOW_START + 86400 <= t < WINDOW_END - 86400):
        return t
    ph = (t - T(2025, 6, 30)) % (7 * 86400)
    if ph < 15 * 3600:
        return t + 15 * 3600
    if ph > 7 * 86400 - 15 * 3600:
        return t - 15 * 3600
    return t


def _pick_host(W, r, fleet, t):
    wk = iso_week(t)
    for _ in range(4000):
        h = r.choice(W.hosts)
        if W.host_base[h] == fleet and W.hw[(h, wk)]["fleet"] == fleet:
            if not any(W.maint[(h, w)][0] <= t < W.maint[(h, w)][1] for w in (wk - 1, wk) if (h, w) in W.maint):
                return h
    raise RuntimeError("no host")


def _pick_staging(W, r, fleet, t):
    wk = iso_week(t)
    for _ in range(4000):
        h = r.choice(W.hosts)
        if W.host_base[h] == fleet and W.hw[(h, wk)]["fleet"] == "s":
            return h
    for _ in range(4000):
        h = r.choice(W.hosts)
        if W.hw[(h, wk)]["fleet"] == "s":
            return h
    raise RuntimeError("no staging host")


def _build_jobs(W, seed):
    r = derive(seed, "jobs")
    W.jobs = {}
    used = set()

    def new_id():
        while True:
            j = f"J{r.randint(100000, 9999999):07d}"
            if j not in used:
                used.add(j)
                return j

    W.shards = {}
    W.exempt = set()
    W.rerun_of = {}
    W.rerun_decision = {}
    W.job_void = set()
    W.unregistered = set()
    for m in CANDIDATES:
        cert = W.certified[m]["checkpoint"]
        hist = [c for c in W.certified[m]["history"] if c != cert]
        for b in BENCH_KEYS:
            if b not in W.shards:
                ids = list(W.bench_items[b])
                derive(seed, "shards|" + b).shuffle(ids)
                size = 5 if b == "code" else 10
                W.shards[b] = [sorted(ids[k:k + size]) for k in range(0, len(ids), size)]
            shards = W.shards[b]
            fleet = BENCH_FLEET[b]
            for sn, sh in enumerate(shards):
                harness = r.weighted([("h3.1", 3), ("h3.2", 4), ("h4.0", 5)])
                t = r.randint(WINDOW_START + 3600, WINDOW_END - 7200)
                if r.chance(0.004):
                    t = WINDOW_START  # exactly on the opening instant: inside the half-open window
                base = {"model": m, "bench": b, "shard": sn, "items": sh, "ckpt": cert, "harness": harness}

                def mk(kind, t, host=None, ckpt=cert, harness=harness):
                    j = new_id()
                    t = clear_of_week_edge(t)
                    host = host or _pick_host(W, r, fleet, t)
                    job = dict(base, id=j, kind=kind, submitted=t, host=host, ckpt=ckpt, harness=harness,
                               temperature="0.8" if b == "code" else "0.0", samples=10 if b == "code" else 1)
                    W.jobs[j] = job
                    return job

                roll = r.rand()
                auth = None
                if roll < 0.09:  # approved rerun: original superseded
                    o = mk("superseded", t)
                    rr = mk("authoritative", min(WINDOW_END - 60, t + r.randint(3600, 4 * 86400)))
                    W.rerun_of[rr["id"]] = o["id"]
                    W.rerun_decision[rr["id"]] = "approved"
                    auth = rr
                elif roll < 0.125:  # denied rerun
                    o = mk("authoritative", t)
                    rr = mk("rerun_denied", min(WINDOW_END - 60, t + r.randint(3600, 4 * 86400)))
                    W.rerun_of[rr["id"]] = o["id"]
                    W.rerun_decision[rr["id"]] = r.choice(["denied", "missing"])
                    auth = o
                else:
                    auth = mk("authoritative", t)
                    if r.chance(0.04):  # authoritative job inside a maintenance window with an exemption
                        wk = iso_week(auth["submitted"])
                        ms, me = W.maint[(auth["host"], wk)]
                        nt = ms + r.randint(0, me - ms - 1)
                        if WINDOW_START <= nt < WINDOW_END and iso_week(nt) == wk and clear_of_week_edge(nt) == nt and not any(
                                W.maint[(auth["host"], w)][0] <= nt < W.maint[(auth["host"], w)][1] for w in (wk - 1,) if (auth["host"], w) in W.maint):
                            auth["submitted"] = nt
                            W.exempt.add(auth["id"])
                # extra noise jobs for the same shard
                if r.chance(0.08) and hist:
                    mk("stale_checkpoint", r.randint(WINDOW_START + 3600, WINDOW_END - 7200), ckpt=r.choice(hist))
                if r.chance(0.03):
                    v = mk("voided", min(WINDOW_END - 60, auth["submitted"] + r.randint(600, 86400)))
                    W.job_void.add(v["id"])
                if r.chance(0.015):
                    ts = r.randint(WINDOW_START + 3600, WINDOW_END - 7200)
                    mk("staging_host", ts, host=_pick_staging(W, r, fleet, ts))
                if r.chance(0.025):
                    if r.chance(0.5):
                        ts = WINDOW_START - r.randint(60, 5 * 3600)
                    else:
                        ts = WINDOW_END + r.choice([0, 0, r.randint(1, 3 * 3600)])
                    mk("outside_window", ts)
                if r.chance(0.03):
                    ts = r.randint(WINDOW_START + 3600, WINDOW_END - 7200)
                    wk = iso_week(ts)
                    for _ in range(200):
                        h = r.choice(W.hosts)
                        if W.host_base[h] == fleet and W.hw[(h, wk)]["fleet"] == fleet:
                            break
                    ms, me = W.maint[(h, wk)]
                    nt = ms + r.randint(0, me - ms - 1)
                    if WINDOW_START <= nt < WINDOW_END and iso_week(nt) == wk and W.hw[(h, wk)]["fleet"] == fleet and clear_of_week_edge(nt) == nt:
                        mk("maintenance", nt, host=h)
                if r.chance(0.02):
                    u = mk("unregistered", r.randint(WINDOW_START + 3600, WINDOW_END - 7200))
                    W.unregistered.add(u["id"])
    _add_precedence_pairs(W, seed)
    W.job_ids = sorted(j for j in W.jobs if j not in W.unregistered)


# Neighbouring steps of the policy's disposition order; each pair must meet on at least one job.
PAIR_KINDS = [("voided", "staging_host"), ("staging_host", "stale_checkpoint"), ("stale_checkpoint", "outside_window"),
              ("outside_window", "maintenance"), ("maintenance", "superseded"), ("superseded", "rerun_denied")]


def _disposition_conditions(W, j):
    """Every disposition condition that holds for job j, in policy order (several can hold at once)."""
    job = W.jobs[j]
    t = job["submitted"]
    held = []
    if j in W.job_void:
        held.append("voided")
    if W.hw[(job["host"], iso_week(t))]["fleet"] == "s":
        held.append("staging_host")
    if job["ckpt"] != W.certified[job["model"]]["checkpoint"]:
        held.append("stale_checkpoint")
    if not (WINDOW_START <= t < WINDOW_END):
        held.append("outside_window")
    if in_maint(W, job["host"], t) and j not in W.exempt:
        held.append("maintenance")
    if any(o == j and W.rerun_decision[rr] == "approved" for rr, o in W.rerun_of.items()):
        held.append("superseded")
    if j in W.rerun_of and W.rerun_decision[j] != "approved":
        held.append("rerun_denied")
    return held


def _add_precedence_pairs(W, seed, per_pair=3):
    """Jobs on which two neighbouring disposition conditions hold at once, so the policy order decides.

    Uses its own random stream and runs after the main job loop, so no existing job changes
    except the approved-rerun originals reused for the last two pairs."""
    r = derive(seed, "pairs")
    used = set(W.jobs)
    made = []

    def new_id():
        while True:
            j = f"J{r.randint(100000, 9999999):07d}"
            if j not in used:
                used.add(j)
                return j

    def harness():
        return r.weighted([("h3.1", 3), ("h3.2", 4), ("h4.0", 5)])

    def add(kind, m, b, sn, t, host, ckpt, hv):
        j = new_id()
        W.jobs[j] = {"model": m, "bench": b, "shard": sn, "items": W.shards[b][sn], "ckpt": ckpt, "harness": hv,
                     "id": j, "kind": kind, "submitted": t, "host": host,
                     "temperature": "0.8" if b == "code" else "0.0", "samples": 10 if b == "code" else 1}
        made.append(j)
        return j

    def stale_of(m):
        return [c for c in W.certified[m]["history"] if c != W.certified[m]["checkpoint"]]

    def slot(need_stale=False):
        while True:
            m, b = r.choice(CANDIDATES), r.choice(BENCH_KEYS)
            if not need_stale or stale_of(m):
                return m, b, r.below(len(W.shards[b]))

    def in_window():
        while True:
            t = clear_of_week_edge(r.randint(WINDOW_START + 86400, WINDOW_END - 86400))
            if WINDOW_START <= t < WINDOW_END:
                return t

    def outside():
        return WINDOW_START - r.randint(60, 5 * 3600) if r.chance(0.5) else WINDOW_END + r.randint(0, 3 * 3600)

    for _ in range(per_pair):
        # voided + staging_host
        m, b, sn = slot()
        t = in_window()
        W.job_void.add(add("voided", m, b, sn, t, _pick_staging(W, r, BENCH_FLEET[b], t), W.certified[m]["checkpoint"], harness()))
        # staging_host + stale_checkpoint
        m, b, sn = slot(need_stale=True)
        t = in_window()
        add("staging_host", m, b, sn, t, _pick_staging(W, r, BENCH_FLEET[b], t), r.choice(stale_of(m)), harness())
        # stale_checkpoint + outside_window
        m, b, sn = slot(need_stale=True)
        t = outside()
        add("stale_checkpoint", m, b, sn, t, _pick_host(W, r, BENCH_FLEET[b], t), r.choice(stale_of(m)), harness())
        # outside_window + maintenance: a production host whose week-27 or week-40 window reaches outside the quarter
        m, b, sn = slot()
        fleet = BENCH_FLEET[b]
        for _try in range(20000):
            h, wk = r.choice(W.hosts), r.choice([WEEKS[0], WEEKS[-1]])
            if W.host_base[h] != fleet or W.hw[(h, wk)]["fleet"] != fleet:
                continue
            lo, hi = (T(2025, 6, 30, 19), WINDOW_START) if wk == WEEKS[0] else (WINDOW_END, T(2025, 10, 4))
            ms, me = W.maint[(h, wk)]
            a, z = max(ms, lo), min(me, hi)
            if a < z:
                add("outside_window", m, b, sn, a + r.below(z - a), h, W.certified[m]["checkpoint"], harness())
                break
        else:
            raise RuntimeError("no maintenance window outside the quarter")

    approved = sorted((rr, o) for rr, o in W.rerun_of.items() if W.rerun_decision[rr] == "approved")
    r.shuffle(approved)
    taken = set()
    # maintenance + superseded: move an approved-rerun original into its host's window (no exemption)
    n = 0
    for rr, o in approved:
        if n >= per_pair:
            break
        job = W.jobs[o]
        wk = iso_week(job["submitted"])
        ms, me = W.maint[(job["host"], wk)]
        lo, hi = max(ms, WINDOW_START), min(me, WINDOW_END, W.jobs[rr]["submitted"])
        for _try in range(50):
            if lo >= hi:
                break
            nt = lo + r.below(hi - lo)
            if iso_week(nt) == wk and clear_of_week_edge(nt) == nt:
                job["submitted"], job["kind"] = nt, "maintenance"
                taken.add(o)
                made.append(o)
                n += 1
                break
    # superseded + rerun_denied: an approved-rerun original that is itself a denied rerun of a voided job
    n = 0
    for rr, o in approved:
        if n >= per_pair:
            break
        if o in taken or o in W.rerun_of:
            continue
        job = W.jobs[o]
        t1 = clear_of_week_edge(job["submitted"] - r.randint(3600, 2 * 86400))
        if not (WINDOW_START <= t1 < WINDOW_END):
            continue
        o1 = add("voided", job["model"], job["bench"], job["shard"], t1, _pick_host(W, r, BENCH_FLEET[job["bench"]], t1),
                 W.certified[job["model"]]["checkpoint"], job["harness"])
        W.job_void.add(o1)
        W.rerun_of[o] = o1
        W.rerun_decision[o] = "denied"
        taken.add(o)
        made.append(o)
        n += 1

    conds = {j: _disposition_conditions(W, j) for j in made}
    for j in made:
        assert conds[j] and conds[j][0] == W.jobs[j]["kind"], (j, conds[j], W.jobs[j]["kind"])
    for a, b in PAIR_KINDS:
        assert any(a in c and b in c for c in conds.values()), ("precedence pair never constructed", a, b)


def _gen_values(W, r, m, it, grader, quality):
    b = it["bench"]
    p = min(0.97, max(0.03, W.skill[(m, b)] * quality + (0.5 - it["hard"]) * 0.3))
    if b == "arith":
        g = it["gold"]
        if r.chance(0.03):
            return {"answer": None}
        if r.chance(p):
            if it["tol"] == "abs" and r.chance(0.3):
                return {"answer": g + r.choice([Decimal("0.01"), Decimal("-0.01")])}
            if it["tol"] == "rel" and r.chance(0.3):
                d = (abs(g) / 100).quantize(Decimal("0.01"), rounding="ROUND_DOWN")
                return {"answer": g + d}
            return {"answer": g}
        bump = r.choice([Decimal("0.02"), Decimal("1"), Decimal("10"), (abs(g) / 10).quantize(Decimal("0.01")) + Decimal("0.03")])
        return {"answer": g + bump if r.chance(0.5) else g - bump}
    if b == "code":
        passes = [1 if r.chance(p) else 0 for _ in range(10)]
        return {"passed": [it["tests"] if x else r.randint(0, it["tests"] - 1) for x in passes]}
    if b == "intent":
        if r.chance(p):
            return {"label": it["gold"]}
        return {"label": r.choice([c for c in INTENT_CLASSES if c != it["gold"]])}
    if b == "safety":
        if it["gold"]:
            x = 0.35 + 0.65 * (r.rand() ** (1.0 - 0.6 * p))
        else:
            x = 0.65 * (r.rand() ** (1.0 + 2.0 * p))
        v = Decimal(int(x * 40 + 0.5)).scaleb(0) / 40  # coarse grid -> many ties
        if r.chance(0.04):
            v = Decimal(1) if it["gold"] else Decimal(0)
        return {"score": v.quantize(Decimal("0.001"))}
    if b == "mcq":
        bias = W.overconf[m]
        c = min(0.9999, max(0.2001, p + (r.rand() - 0.5) * 0.3))
        ok = r.chance(min(0.99, max(0.01, c - bias)))
        opt = it["gold"] if ok else r.choice([o for o in "ABCDE"[:it["n_options"]] if o != it["gold"]])
        conf = Decimal(int(c * 10000)).scaleb(-4)
        if r.chance(0.03):
            conf = Decimal("1.0000")
        return {"option": opt, "conf": conf}
    if b == "longctx":
        if r.chance(p):
            g = it["gold"]
            return {"answer": r.choice([g, g, g.upper(), g + ".", g.title()])}
        return {"answer": _word(r)}
    if b == "multiling":
        g = it["gold"]
        if r.chance(p):
            v = r.weighted([("nfc", 5), ("nfd", 2), ("upper", 2), ("strip", 2)])
            if v == "nfd":
                return {"answer": unicodedata.normalize("NFD", g)}
            if v == "upper":
                return {"answer": g.upper()}
            if v == "strip":
                return {"answer": strip_marks(g)}
            return {"answer": g}
        return {"answer": _word(r, it["lang"])}
    raise ValueError(b)


def _pref_verdicts(W, r, m, it, quality):
    s = W.skill[(m, "pref")] * quality
    roll = r.rand()
    truth = "win" if roll < s * 0.8 else ("loss" if roll < s * 0.8 + (1 - s) * 0.8 else "even")
    out = {}
    for order in ("AB", "BA"):
        cand_first = order == "AB"
        if truth == "even":
            pick = r.choice(["cand", "base", "tie"])
        elif r.chance(0.82):
            pick = "cand" if truth == "win" else "base"
        else:
            pick = r.choice(["tie", "cand" if truth == "loss" else "base"])
        if pick == "tie":
            out[order] = "T"
        elif pick == "cand":
            out[order] = "A" if cand_first else "B"
        else:
            out[order] = "B" if cand_first else "A"
    return out


def _build_results(W, seed):
    r = derive(seed, "results")
    W.res = {}  # job -> {(item, sample/order): fields}
    for j in sorted(W.jobs):
        job = W.jobs[j]
        quality = 1.0 if job["kind"] == "authoritative" else 0.7
        rr = derive(seed, "res|" + j)
        grader = W.grader_of_harness[job["harness"]]
        rows = {}
        for iid in job["items"]:
            it = W.items[iid]
            if job["bench"] == "pref":
                for order, v in _pref_verdicts(W, rr, job["model"], it, quality).items():
                    rows[(iid, order)] = {"verdict": v}
            elif job["bench"] == "code":
                vals = _gen_values(W, rr, job["model"], it, grader, quality)
                for s, pv in enumerate(vals["passed"]):
                    rows[(iid, s)] = {"passed": pv, "total": it["tests"]}
            else:
                rows[(iid, 0)] = _gen_values(W, rr, job["model"], it, grader, quality)
        W.res[j] = rows
    # baseline reference results (item level, no jobs)
    W.base_res = {}
    for iid in sorted(W.items):
        it = W.items[iid]
        if it["bench"] == "pref":
            continue
        vals = _gen_values(W, r, BASELINE, it, "g3", 1.0)
        if it["bench"] == "code":
            vals = {"c": sum(1 for pv in vals["passed"] if pv == it["tests"])}
        W.base_res[iid] = vals

# ---------------------------------------------------------------------------------
# truth: the certified close computed from the canonical world
# ---------------------------------------------------------------------------------
SLICE_POOL = [("hard_items", [("difficulty", ["hard"])]), ("finance_law", [("domain", ["finance", "law"])]),
              ("eu_region", [("region", ["EU"])]), ("apac_health", [("region", ["APAC"]), ("domain", ["health"])]),
              ("easy_everyday", [("difficulty", ["easy"]), ("domain", ["everyday"])]),
              ("latam_mea", [("region", ["LATAM", "MEA"])]), ("science_tech", [("domain", ["science", "tech"])]),
              ("medium_na", [("difficulty", ["medium"]), ("region", ["NA"])])]


def world_params(W):
    r = derive(W.seed, "params")
    P = {}
    P["weights"] = {b: Decimal(r.choice(["0.50", "0.75", "1.00", "1.25", "1.50"])) for b in BENCH_KEYS}
    P["ece_cap"] = Decimal(r.choice(["0.080", "0.100", "0.120"]))
    P["auroc_floor"] = Decimal(r.choice(["0.700", "0.750", "0.800"]))
    P["alpha"] = Decimal("0.05")
    pool = list(SLICE_POOL)
    r.shuffle(pool)
    P["slices"] = sorted(pool[:5])
    P["min_support"] = r.choice([20, 25, 30]) if W.scale >= 0.5 else r.choice([4, 5, 6])
    P["lang_min_support"] = r.choice([15, 20]) if W.scale >= 0.5 else 3
    return P


def in_maint(W, h, t):
    wk = iso_week(t)
    for w in (wk - 1, wk):
        if (h, w) in W.maint:
            ms, me = W.maint[(h, w)]
            if ms <= t < me:
                return True
    return False


def job_disposition(W, j):
    job = W.jobs[j]
    wk = iso_week(job["submitted"])
    if j in W.job_void:
        return "voided"
    if W.hw[(job["host"], wk)]["fleet"] == "s":
        return "staging_host"
    if job["ckpt"] != W.certified[job["model"]]["checkpoint"]:
        return "stale_checkpoint"
    if not (WINDOW_START <= job["submitted"] < WINDOW_END):
        return "outside_window"
    if in_maint(W, job["host"], job["submitted"]) and j not in W.exempt:
        return "maintenance"
    if any(o == j and W.rerun_decision[rr] == "approved" for rr, o in W.rerun_of.items()):
        return "superseded"
    if j in W.rerun_of and W.rerun_decision[j] != "approved":
        return "rerun_denied"
    return "authoritative"


def item_correct(W, m, it, vals, grader):
    b = it["bench"]
    if b == "arith":
        a = vals["answer"]
        if a is None:
            return 0
        g = it["gold"]
        if it["tol"] == "exact":
            return int(a == g)
        if it["tol"] == "abs":
            return int(abs(a - g) <= Decimal("0.01"))
        return int(abs(a - g) <= abs(g) / 100)
    if b == "intent":
        return int(vals["label"] == it["gold"])
    if b == "mcq":
        return int(vals["option"] == it["gold"])
    if b == "longctx":
        fam = FAMILY[m]
        if it["tokens"][TOKENIZER[fam]] > CTX_WINDOW[fam]:
            return 0
        return int(norm_answer(vals["answer"], "g2") == norm_answer(it["gold"], "g2"))
    if b == "multiling":
        return int(norm_answer(vals["answer"], grader) == norm_answer(it["gold"], grader))
    return None


def _auroc(pairs):
    pos = [s for s, y in pairs if y == 1]
    neg = [s for s, y in pairs if y == 0]
    if not pos or not neg:
        return Fraction(1, 2)
    allv = sorted(set(pos + neg))
    cn = {v: 0 for v in allv}
    for v in neg:
        cn[v] += 1
    less = 0
    acc = Fraction(0)
    cum = {}
    for v in allv:
        cum[v] = less
        less += cn[v]
    for s in pos:
        acc += cum[s] + Fraction(cn[s], 2)
    return acc / (len(pos) * len(neg))


def _passk(n, c, k):
    if n - c < k:
        return Fraction(1)
    return 1 - Fraction(math.comb(n - c, k), math.comb(n, k))


def _ece(rows):
    rows = sorted(rows, key=lambda x: (x[0], x[2]))
    N = len(rows)
    bins = []
    base, extra = divmod(N, 10)
    pos = 0
    ece = Fraction(0)
    for bi in range(10):
        sz = base + (1 if bi < extra else 0)
        chunk = rows[pos:pos + sz]
        pos += sz
        if not chunk:
            bins.append({"count": 0, "mean_confidence": None, "accuracy": None})
            continue
        mc = sum(Fraction(c) for c, _, _ in chunk) / sz
        ac = Fraction(sum(y for _, y, _ in chunk), sz)
        ece += Fraction(sz, N) * abs(ac - mc)
        bins.append({"count": sz, "mean_confidence": q6(mc), "accuracy": q6(ac)})
    return ece, bins


def _mcnemar_p(b, c):
    n = b + c
    if n == 0:
        return Fraction(1)
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(k + 1))
    return min(Fraction(1), Fraction(2 * tail, 2 ** n))


def fmt_answer(a):
    return None if a is None else format(a.quantize(Decimal("0.01")), "f")


def compute_truth(W):
    P = world_params(W)
    W.params = P
    out = {}
    out["lineage.json"] = {m: {"checkpoint": W.certified[m]["checkpoint"], "effective_from": iso(W.certified[m]["effective_from"]),
                               "approval_ref": W.certified[m]["approval_ref"], "voided_promotions": W.certified[m]["voided_promotions"]}
                           for m in sorted(MODELS)}
    disp = {}
    rows = []
    for j in W.job_ids:
        d = job_disposition(W, j)
        assert d == W.jobs[j]["kind"], (j, d, W.jobs[j]["kind"])
        disp[j] = d
        job = W.jobs[j]
        rows.append({"job_id": j, "model": job["model"], "benchmark": job["bench"], "shard": job["shard"],
                     "checkpoint": job["ckpt"], "host": job["host"], "submitted_at": iso(job["submitted"]), "disposition": d})
    out["job_dispositions.jsonl"] = rows
    W.disp = disp
    out["item_eligibility.jsonl"] = [{"item_id": i, "benchmark": W.items[i]["bench"], "eligible": W.elig[i] is None,
                                      "reason": W.elig[i]} for i in sorted(W.items)]
    auth = {}
    for j, d in disp.items():
        if d == "authoritative":
            job = W.jobs[j]
            key = (job["model"], job["bench"], job["shard"])
            assert key not in auth, key
            auth[key] = j
    W.auth = auth
    # item scores ---------------------------------------------------------------------
    scores = []
    per = {}  # (model, bench) -> list of per-item tuples
    W.item_value = {}
    for m in CANDIDATES:
        for b in BENCH_KEYS:
            lst = []
            for sn, sh in enumerate(W.shards[b]):
                j = auth[(m, b, sn)]
                grader = W.grader_of_harness[W.jobs[j]["harness"]]
                res = W.res[j]
                for iid in sh:
                    if W.elig[iid] is not None:
                        continue
                    it = W.items[iid]
                    conf = None
                    corr = None
                    if b == "code":
                        c = sum(1 for s in range(10) if res[(iid, s)]["passed"] == it["tests"])
                        value = c
                    elif b == "pref":
                        v = {}
                        for order in ("AB", "BA"):
                            x = res[(iid, order)]["verdict"]
                            cand = "A" if order == "AB" else "B"
                            v[order] = "tie" if x == "T" else ("win" if x == cand else "loss")
                        value = "win" if v["AB"] == v["BA"] == "win" else ("loss" if v["AB"] == v["BA"] == "loss" else "tie")
                    else:
                        vals = res[(iid, 0)]
                        corr = item_correct(W, m, it, vals, grader)
                        if b == "arith":
                            value = fmt_answer(vals["answer"])
                        elif b == "intent":
                            value = v2(vals["label"])
                        elif b == "safety":
                            value = float(vals["score"])
                        elif b == "mcq":
                            value = vals["option"]
                            conf = float(vals["conf"])
                        else:
                            value = norm_answer(vals["answer"], grader if b == "multiling" else "g2")
                    scores.append({"model": m, "item_id": iid, "benchmark": b, "value": value, "confidence": conf, "correct": corr})
                    lst.append((iid, value, conf, corr))
            per[(m, b)] = lst
    scores.sort(key=lambda x: (x["model"], x["item_id"]))
    out["item_scores.jsonl"] = scores
    # baseline per-item
    for b in BENCH_KEYS:
        if b == "pref":
            continue
        lst = []
        for iid in W.bench_items[b]:
            if W.elig[iid] is not None:
                continue
            it = W.items[iid]
            vals = W.base_res[iid]
            if b == "code":
                lst.append((iid, vals["c"], None, None))
            elif b == "safety":
                lst.append((iid, float(vals["score"]), None, None))
            elif b == "mcq":
                lst.append((iid, vals["option"], float(vals["conf"]), item_correct(W, BASELINE, it, vals, "g3")))
            else:
                lst.append((iid, None, None, item_correct(W, BASELINE, it, vals, "g3")))
        per[(BASELINE, b)] = lst
    W.per = per
    # metrics -----------------------------------------------------------------------------
    met = {}
    raw = {}
    for m in MODELS:
        mm = {}
        for b in BENCH_KEYS:
            if b == "pref":
                continue
            lst = per[(m, b)]
            n = len(lst)
            if b in ("arith", "longctx", "mcq"):
                a = Fraction(sum(x[3] for x in lst), n)
                mm[b] = {"accuracy": q6(a), "n": n}
                raw[(m, b)] = a
            elif b == "code":
                p1 = sum((_passk(10, x[1], 1) for x in lst), Fraction(0)) / n
                p5 = sum((_passk(10, x[1], 5) for x in lst), Fraction(0)) / n
                mm[b] = {"pass@1": q6(p1), "pass@5": q6(p5), "n": n}
                raw[(m, b)] = p1
            elif b == "intent":
                gold = {iid: W.items[iid]["gold"] for iid, *_ in lst}
                if m == BASELINE:
                    pred = {iid: W.base_res[iid]["label"] for iid, *_ in lst}
                else:
                    inv = {v2(c): c for c in INTENT_CLASSES}
                    pred = {iid: inv[v] for iid, v, _, _ in lst}
                classes = sorted(set(gold.values()) | set(pred.values()))
                f1s = []
                for c in classes:
                    tp = sum(1 for i in gold if gold[i] == c and pred[i] == c)
                    fp = sum(1 for i in gold if gold[i] != c and pred[i] == c)
                    fn = sum(1 for i in gold if gold[i] == c and pred[i] != c)
                    f1s.append(Fraction(2 * tp, 2 * tp + fp + fn))
                f = sum(f1s, Fraction(0)) / len(f1s)
                mm[b] = {"macro_f1": q6(f), "n": n}
                raw[(m, b)] = f
            elif b == "safety":
                pairs = [(Fraction(Decimal(str(x[1]))), W.items[x[0]]["gold"]) for x in lst]
                a = _auroc(pairs)
                mm[b] = {"auroc": q6(a), "n": n}
                raw[(m, b)] = a
            elif b == "multiling":
                bylang = {}
                for iid, _v, _c, corr in lst:
                    bylang.setdefault(W.items[iid]["lang"], []).append(corr)
                langs = sorted(l for l, v in bylang.items() if len(v) >= P["lang_min_support"])
                a = sum((Fraction(sum(bylang[l]), len(bylang[l])) for l in langs), Fraction(0)) / len(langs)
                mm[b] = {"macro_accuracy": q6(a), "n": n, "languages": len(langs)}
                raw[(m, b)] = a
        met[m] = mm
    out["benchmark_metrics.json"] = met
    # calibration ---------------------------------------------------------------------------
    cal = {}
    W.ece = {}
    for m in MODELS:
        e, bins = _ece([(Fraction(Decimal(str(c))), y, iid) for iid, _v, c, y in per[(m, "mcq")]])
        W.ece[m] = e
        if m in CANDIDATES:
            cal[m] = {"ece": q6(e), "bins": bins}
    out["calibration.json"] = cal
    # pairwise ------------------------------------------------------------------------------
    pw = {}
    for m in CANDIDATES:
        vals = [x[1] for x in per[(m, "pref")]]
        w, t, l = vals.count("win"), vals.count("tie"), vals.count("loss")
        wr = Fraction(2 * w + t, 2 * len(vals))
        raw[(m, "pref")] = wr
        pw[m] = {"wins": w, "ties": t, "losses": l, "win_rate": q6(wr)}
    raw[(BASELINE, "pref")] = Fraction(1, 2)
    out["pairwise.json"] = pw
    # significance ----------------------------------------------------------------------------
    sig = {}
    W.sig = {}
    for m in CANDIDATES:
        sm = {}
        for b in GATED:
            bc = {iid: corr for iid, _v, _c, corr in per[(BASELINE, b)]}
            bb = cc = 0
            for iid, _v, _c, corr in per[(m, b)]:
                if corr == 1 and bc[iid] == 0:
                    bb += 1
                elif corr == 0 and bc[iid] == 1:
                    cc += 1
            p = _mcnemar_p(bb, cc)
            dec = "no_change"
            if p < Fraction(P["alpha"]):
                dec = "improved" if bb > cc else ("regressed" if cc > bb else "no_change")
            sm[b] = {"b": bb, "c": cc, "p_value": q6(p), "decision": dec}
        sig[m] = sm
    out["significance.json"] = sig
    # leaderboard -------------------------------------------------------------------------------
    chance = {"arith": Fraction(0), "code": Fraction(0), "intent": Fraction(1, len(INTENT_CLASSES)), "safety": Fraction(1, 2),
              "pref": Fraction(1, 2), "longctx": Fraction(0), "multiling": Fraction(0)}
    mcq_items = [x[0] for x in per[(CANDIDATES[0], "mcq")]]
    chance["mcq"] = sum((Fraction(1, W.items[i]["n_options"]) for i in mcq_items), Fraction(0)) / len(mcq_items)
    W.chance = chance
    lb = []
    agg = {}
    for m in MODELS:
        norms = {}
        for b in BENCH_KEYS:
            norms[b] = (raw[(m, b)] - chance[b]) / (1 - chance[b])
        wsum = sum((Fraction(P["weights"][b]) for b in BENCH_KEYS), Fraction(0))
        a = sum((Fraction(P["weights"][b]) * norms[b] for b in BENCH_KEYS), Fraction(0)) / wsum
        agg[m] = a
        lb.append((m, a, raw[(m, "code")], norms))
    lb.sort(key=lambda x: (-x[1], -x[2], x[0]))
    out["leaderboard.csv"] = [{"rank": i + 1, "model": m, "aggregate": q6(a), **{b: q6(n[b]) for b in BENCH_KEYS}}
                              for i, (m, a, _p, n) in enumerate(lb)]
    W.agg = agg
    gates = {}
    for m in CANDIDATES:
        g = {"aggregate_vs_baseline": agg[m] >= agg[BASELINE],
             "no_regression": all(sig[m][b]["decision"] != "regressed" for b in GATED),
             "ece_within_cap": W.ece[m] <= Fraction(P["ece_cap"]),
             "safety_floor": raw[(m, "safety")] >= Fraction(P["auroc_floor"])}
        g["release"] = all(g.values())
        gates[m] = g
    out["release_gates.json"] = gates
    # slices -------------------------------------------------------------------------------------
    sl = {}
    for m in CANDIDATES:
        sm = {}
        for b in SLICE_BENCHES:
            bm = {}
            for name, conds in P["slices"]:
                vals = [corr for iid, _v, _c, corr in per[(m, b)]
                        if all(W.items[iid][f] in allowed for f, allowed in conds)]
                bm[name] = q6(Fraction(sum(vals), len(vals))) if len(vals) >= P["min_support"] else None
            sm[b] = bm
        sl[m] = sm
    out["slice_metrics.json"] = sl
    return out

# ---------------------------------------------------------------------------------
# format writers (stdlib only, deterministic)
# ---------------------------------------------------------------------------------
_ZDATE = (2025, 10, 3, 18, 0, 0)


def xesc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def _zip(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in members:
            info = zipfile.ZipInfo(name, date_time=_ZDATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, data if isinstance(data, bytes) else data.encode("utf-8"))
    return buf.getvalue()


def _col(n):
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def xlsx_bytes(sheets):
    """sheets: list of (name, rows); a cell is str (inline string), int/float (number) or None."""
    wb_sheets, rels, ctypes = [], [], []
    members = []
    for i, (name, rows) in enumerate(sheets, 1):
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for ri, row in enumerate(rows, 1):
            cells = []
            for ci, v in enumerate(row):
                if v is None:
                    continue
                ref = f"{_col(ci)}{ri}"
                if isinstance(v, bool):
                    v = str(v).lower()
                if isinstance(v, (int, float)):
                    cells.append(f'<c r="{ref}"><v>{v!r}</v></c>' if isinstance(v, float) else f'<c r="{ref}"><v>{v}</v></c>')
                else:
                    sv = xesc(v).replace("\r", "&#13;")
                    cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{sv}</t></is></c>')
            out.append(f'<row r="{ri}">' + "".join(cells) + "</row>")
        out.append("</sheetData></worksheet>")
        members.append((f"xl/worksheets/sheet{i}.xml", "".join(out)))
        wb_sheets.append(f'<sheet name="{xesc(name)}" sheetId="{i}" r:id="rId{i}"/>')
        rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
        ctypes.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    head = [
        ("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' + "".join(ctypes) + "</Types>"),
        ("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'),
        ("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + "".join(wb_sheets) + "</sheets></workbook>"),
        ("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + "".join(rels) + "</Relationships>"),
    ]
    return _zip(head + members)


def docx_bytes(blocks):
    """blocks: ("p", text) paragraphs or ("t", rows) tables (rows of str cells)."""
    body = []
    for kind, val in blocks:
        if kind == "p":
            body.append(f'<w:p><w:r><w:t xml:space="preserve">{xesc(val)}</w:t></w:r></w:p>')
        elif kind == "h0":
            pass
        elif kind == "h":
            body.append(f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t xml:space="preserve">{xesc(val)}</w:t></w:r></w:p>')
        else:
            trs = []
            for row in val:
                tcs = "".join(f'<w:tc><w:p><w:r><w:t xml:space="preserve">{xesc(c).replace(chr(13), "&#13;")}</w:t></w:r></w:p></w:tc>' for c in row)
                trs.append(f"<w:tr>{tcs}</w:tr>")
            body.append("<w:tbl>" + "".join(trs) + "</w:tbl><w:p/>")
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           + "".join(body) + "</w:body></w:document>")
    return _zip([
        ("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'),
        ("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'),
        ("word/document.xml", doc),
    ])


def _pdf_esc(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_bytes(lines, per_page=62):
    """Plain text layer, Helvetica 7pt, one text line per table row; ASCII only."""
    pages = [lines[i:i + per_page] for i in range(0, len(lines), per_page)] or [[]]
    objs = {1: b"<< /Type /Catalog /Pages 2 0 R >>", 3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"}
    kids = []
    nxt = 4
    for pg in pages:
        ops = ["BT", "/F1 7 Tf", "9 TL", "28 815 Td"]
        for ln in pg:
            ops.append(f"({_pdf_esc(ln)}) Tj T*")
        ops.append("ET")
        raw = zlib.compress("\n".join(ops).encode("latin-1"), 9)
        cid, pid = nxt, nxt + 1
        nxt += 2
        objs[cid] = b"<< /Length " + str(len(raw)).encode() + b" /Filter /FlateDecode >>\nstream\n" + raw + b"\nendstream"
        objs[pid] = f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 3 0 R >> >> /Contents {cid} 0 R >>".encode()
        kids.append(pid)
    objs[2] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>".encode()
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offs = {}
    for n in sorted(objs):
        offs[n] = out.tell()
        out.write(f"{n} 0 obj\n".encode() + objs[n] + b"\nendobj\n")
    xref = out.tell()
    n = max(objs) + 1
    out.write(f"xref\n0 {n}\n0000000000 65535 f \n".encode())
    for i in range(1, n):
        out.write(f"{offs[i]:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return out.getvalue()


# --- parquet (thrift compact, PLAIN, uncompressed, REQUIRED columns) ---------------
def _uvar(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _zz(n):
    return _uvar((n << 1) ^ (n >> 63))


class _TC:
    def __init__(self):
        self.b = bytearray()
        self.last = [0]

    def fh(self, fid, t):
        d = fid - self.last[-1]
        if 0 < d <= 15:
            self.b.append((d << 4) | t)
        else:
            self.b.append(t)
            self.b += _zz(fid)
        self.last[-1] = fid

    def i32(self, fid, v):
        self.fh(fid, 5)
        self.b += _zz(v)

    def i64(self, fid, v):
        self.fh(fid, 6)
        self.b += _zz(v)

    def bin(self, fid, v):
        self.fh(fid, 8)
        v = v.encode() if isinstance(v, str) else v
        self.b += _uvar(len(v)) + v

    def begin(self, fid):
        self.fh(fid, 12)
        self.last.append(0)

    def end(self):
        self.b.append(0)
        self.last.pop()

    def lst(self, fid, etype, n):
        self.fh(fid, 9)
        self.b.append((n << 4) | etype if n < 15 else 0xF0 | etype)
        if n >= 15:
            self.b += _uvar(n)

    def lbegin(self):
        self.last.append(0)


def parquet_bytes(columns, row_groups, created_by="heron-export 2.3"):
    """columns: [(name, kind)] kind in int64|double|string; row_groups: list of list-of-row-tuples."""
    PT = {"int64": 2, "double": 5, "string": 6}
    out = bytearray(b"PAR1")
    rg_meta = []
    for rows in row_groups:
        chunks = []
        for ci, (name, kind) in enumerate(columns):
            vals = [r[ci] for r in rows]
            if kind == "int64":
                data = b"".join(struct.pack("<q", v) for v in vals)
            elif kind == "double":
                data = b"".join(struct.pack("<d", v) for v in vals)
            else:
                data = b"".join(struct.pack("<I", len(x.encode())) + x.encode() for x in vals)
            ph = _TC()
            ph.i32(1, 0)
            ph.i32(2, len(data))
            ph.i32(3, len(data))
            ph.begin(5)
            ph.i32(1, len(vals))
            ph.i32(2, 0)
            ph.i32(3, 3)
            ph.i32(4, 3)
            ph.end()
            ph.b.append(0)
            off = len(out)
            out += ph.b + data
            chunks.append((name, kind, off, len(ph.b) + len(data), len(vals)))
        rg_meta.append((chunks, len(rows)))
    fm = _TC()
    fm.i32(1, 1)
    fm.lst(2, 12, len(columns) + 1)
    fm.lbegin()
    fm.bin(4, "schema")
    fm.i32(5, len(columns))
    fm.end()
    for name, kind in columns:
        fm.lbegin()
        fm.i32(1, PT[kind])
        fm.i32(3, 0)
        fm.bin(4, name)
        if kind == "string":
            fm.i32(6, 0)
        fm.end()
    fm.i64(3, sum(n for _, n in rg_meta))
    fm.lst(4, 12, len(rg_meta))
    for chunks, nrows in rg_meta:
        fm.lbegin()
        fm.lst(1, 12, len(chunks))
        for name, kind, off, size, nv in chunks:
            fm.lbegin()
            fm.i64(2, off)
            fm.begin(3)
            fm.i32(1, PT[kind])
            fm.lst(2, 5, 1)
            fm.b += _zz(0)
            fm.lst(3, 8, 1)
            fm.b += _uvar(len(name.encode())) + name.encode()
            fm.i32(4, 0)
            fm.i64(5, nv)
            fm.i64(6, size)
            fm.i64(7, size)
            fm.i64(9, off)
            fm.end()
            fm.end()
        fm.i64(2, sum(c[3] for c in chunks))
        fm.i64(3, nrows)
        fm.end()
    fm.bin(6, created_by)
    fm.b.append(0)
    out += fm.b + struct.pack("<I", len(fm.b)) + b"PAR1"
    return bytes(out)


def sqlite_bytes(statements):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    try:
        con = sqlite3.connect(path)
        con.execute("PRAGMA page_size=4096")
        con.execute("PRAGMA journal_mode=OFF")
        for sql, rows in statements:
            if rows is None:
                con.execute(sql)
            else:
                con.executemany(sql, rows)
        con.commit()
        con.execute("VACUUM")
        con.close()
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        if os.path.exists(path):
            os.unlink(path)


def mbox_bytes(messages):
    out = []
    for frm_line, headers, body in messages:
        out.append(frm_line)
        for k, v in headers:
            out.append(f"{k}: {v}")
        out.append("")
        for ln in body.split("\n"):
            out.append(">" + ln if ln.startswith("From ") else ln)
        out.append("")
    return ("\n".join(out) + "\n").encode("utf-8")

# ---------------------------------------------------------------------------------
# row plan for the result-bearing sources
# ---------------------------------------------------------------------------------
PAIRS = {"arith": ("results_fleet_a.log", "legacy_results.txt"),
         "intent": ("intent_predictions.csv", "results_fleet_a.log", "scores_shard2.parquet"),
         "safety": ("results_fleet_b.log", "scores_shard2.parquet"),
         "mcq": ("results_fleet_b.log", "scores_shard1.parquet"),
         "longctx": ("results_fleet_c.log", "eval_store.db"),
         "multiling": ("results_fleet_c.log", "scores_shard1.parquet"),
         "code": ("code_samples.jsonl", "eval_store.db"),
         "pref": ("judge_verdicts.jsonl",)}
FIELDS = {"arith": ["answer"], "intent": ["label"], "safety": ["score"], "mcq": ["option", "conf"],
          "longctx": ["answer"], "multiling": ["answer"], "code": ["passed"], "pref": ["verdict"]}
RESULT_SOURCES = ["results_fleet_a.log", "results_fleet_b.log", "results_fleet_c.log", "code_samples.jsonl",
                  "judge_verdicts.jsonl", "scores_shard1.parquet", "scores_shard2.parquet", "eval_store.db",
                  "legacy_results.txt", "intent_predictions.csv", "rerun_results.jsonl", "scores_staging.parquet",
                  "eval_store_mirror.db", "judge_verdicts_rescored.jsonl"]
RID_PREFIX = {s: "r" for s in RESULT_SOURCES}
# taxonomy version by harness
TAXO = {"h3.1": "v1", "h3.2": "v1", "h4.0": "v2"}


class RRow:
    __slots__ = ("src", "rid", "job", "item", "sub", "bench", "vals", "emitted", "kind", "ctx", "rules", "target", "line")

    def __init__(self, src, job, item, sub, bench, vals, emitted, kind):
        self.src, self.job, self.item, self.sub, self.bench = src, job, item, sub, bench
        self.vals, self.emitted, self.kind = vals, emitted, kind
        self.rid, self.ctx, self.rules, self.target, self.line = None, {}, [], None, None


def perturb(W, r, bench, field, v, item):
    it = W.items[item]
    if field == "answer" and bench == "arith":
        if v is None:
            return it["gold"] + Decimal(r.randint(1, 50))
        return v + r.choice([Decimal("1"), Decimal("-1"), Decimal("0.10"), Decimal("100")])
    if field == "answer":
        return v[: max(1, len(v) - 2)] + r.choice(SYL)
    if field == "label":
        return r.choice([c for c in INTENT_CLASSES if c != v])
    if field == "score":
        return min(Decimal(1), max(Decimal(0), (v + r.choice([Decimal("0.125"), Decimal("-0.125"), Decimal("0.050")])))).quantize(Decimal("0.001"))
    if field == "option":
        return r.choice([o for o in "ABCDE"[:it["n_options"]] if o != v])
    if field == "conf":
        return (v + Decimal(r.randint(1, 900)).scaleb(-4)) if v < Decimal("0.9") else (v - Decimal(r.randint(1, 900)).scaleb(-4))
    if field == "passed":
        return it["tests"] - 1 - r.below(it["tests"]) if v == it["tests"] else it["tests"]
    if field == "verdict":
        return r.choice([x for x in "ABT" if x != v])
    raise ValueError(field)


def degrade(W, r, bench, field, v, item):
    """The losing copy's value: plausible, different, systematic per field."""
    if field == "conf":
        return (v * 100).to_integral_value(rounding="ROUND_DOWN") / 100
    if field == "score":
        return v.quantize(Decimal("0.1"), rounding="ROUND_HALF_UP")
    if field == "answer" and bench == "arith":
        return None if v is None else v.to_integral_value(rounding="ROUND_HALF_UP")
    return perturb(W, r, bench, field, v, item)


def plan_results(W, seed):
    r = derive(seed, "plan")
    P = W.params
    W.route = {}
    W.copy_src = {}
    W.jclass = {}
    W.seal = {}
    W.rescue = set()
    W.legacy_jobno = {}
    rows = {s: [] for s in RESULT_SOURCES}
    # precedence defaults: (bench, field) -> winning source family for jobs carrying two copies
    W.prec = {}
    for b, f in sorted((b, f) for b in FIELDS for f in FIELDS[b]):
        if b == "pref":
            continue
        W.prec[(b, f)] = r.choice(["primary_family", "secondary_family"])
    for j in sorted(W.jobs):
        job = W.jobs[j]
        b = job["bench"]
        srcs = PAIRS[b]
        if j in W.rerun_of:
            prim = "rerun_results.jsonl"
        elif job["kind"] == "staging_host":
            prim = "scores_staging.parquet"
        else:
            if b == "intent":
                prim = r.weighted([(srcs[0], 56), (srcs[1], 22), (srcs[2], 22)])
            elif b == "arith":
                prim = srcs[0] if r.chance(0.35) else srcs[1]
            else:
                prim = srcs[0] if len(srcs) == 1 else (srcs[0] if r.chance(0.55) else srcs[1])
        sec = None
        if prim not in ("rerun_results.jsonl", "scores_staging.parquet") and len(srcs) > 1 and r.chance(0.11):
            others = [s for s in srcs if s != prim]
            sec = (srcs[2] if prim != srcs[2] else r.choice(srcs[:2])) if b == "intent" else others[0]
        if job["kind"] == "authoritative" and prim not in ("rerun_results.jsonl",) and b in ("mcq", "multiling", "safety", "intent") and r.chance(0.012):
            W.rescue.add(j)
            prim, sec = "scores_staging.parquet", None
        W.route[j] = prim
        W.copy_src[j] = sec
        W.jclass[j] = "bridge" if r.chance(0.30 if sec else 0.02) else "standard"
        if r.chance(0.04) and job["submitted"] < T(2025, 8, 1):
            W.legacy_jobno[j] = f"L-{r.randint(10000, 99999)}"
        # emission times
        t0 = job["submitted"] + r.randint(300, 6 * 3600)
        keys = sorted(W.res[j])
        times = {}
        t = t0
        for k in keys:
            t += r.randint(1, 40)
            times[k] = t
        seal = t + r.randint(1800, 12 * 3600)
        W.seal[j] = seal
        for k in keys:
            vals = dict(W.res[j][k])
            item, sub = k
            if b == "mcq":
                vals["conf"] = vals["conf"]
            canon = RRow(prim, j, item, sub, b, vals, times[k], "canon")
            two = sec is not None
            if two:
                cp = RRow(sec, j, item, sub, b, dict(vals), times[k] + r.randint(0, 900), "copy")
                for f in FIELDS[b]:
                    win_primary = (W.prec[(b, f)] == "primary_family") == (prim != srcs[-1])
                    if W.jclass[j] == "bridge":
                        win_primary = not win_primary
                    loser = cp if win_primary else canon
                    if r.chance(0.5):
                        loser.vals[f] = degrade(W, r, b, f, loser.vals[f], item)
                rows[sec].append(cp)
            rows[prim].append(canon)
            if job["kind"] != "authoritative" or prim == "scores_staging.parquet":
                if job["kind"] == "authoritative" and b in ("mcq", "multiling", "safety", "intent") and r.chance(0.0):
                    pass
                continue
            if b in ("mcq", "multiling", "safety", "intent") and r.chance(0.19):
                v = dict(vals)
                if r.chance(0.05):
                    f = FIELDS[b][0]
                    v[f] = perturb(W, r, b, f, v[f], item)
                rows["scores_staging.parquet"].append(RRow("scores_staging.parquet", j, item, sub, b, v, times[k] + (r.randint(60, 1800) if r.chance(0.85) else r.randint(13 * 3600, 3 * 86400)), "stgcopy"))
            # row level noise in the primary source
            roll = r.rand()
            def alt():
                v = dict(vals)
                f = r.choice(FIELDS[b])
                v[f] = perturb(W, r, b, f, v[f], item)
                return v
            if roll < 0.10:
                rows[prim].append(RRow(prim, j, item, sub, b, alt(), times[k] - r.randint(60, max(61, times[k] - job["submitted"] - 1)), "older"))
            elif roll < 0.14:
                late = seal + (r.randint(1, 4 * 3600) if r.chance(0.6) else r.randint(4 * 3600, 2 * 86400))
                rows[prim].append(RRow(prim, j, item, sub, b, alt(), late, "late"))
            elif roll < 0.19:
                rows[prim].append(RRow(prim, j, item, sub, b, alt(), r.randint(max(times.values()) + 1, seal - 1), "void"))
            elif roll < 0.20 and prim.endswith(".log"):
                rows[prim].append(RRow(prim, j, item, sub, b, alt(), r.randint(times[k] + 1, seal - 1), "revd"))
            elif roll < 0.215 and prim.endswith(".log"):
                rows[prim].append(RRow(prim, j, item, sub, b, alt(), r.randint(times[k] + 1, seal - 1), "shadow"))
            elif roll < 0.225:
                # a row emitted exactly at the seal instant still counts (at or before)
                canon.emitted = seal
            elif roll < 0.245:
                others = [s for s in ("results_fleet_a.log", "results_fleet_b.log", "results_fleet_c.log", "scores_shard1.parquet", "scores_shard2.parquet", "eval_store.db")
                          if s != prim and s != sec and b in {"results_fleet_a.log": ("arith", "intent"), "results_fleet_b.log": ("safety", "mcq"), "results_fleet_c.log": ("longctx", "multiling"),
                                                             "scores_shard1.parquet": ("mcq", "multiling"), "scores_shard2.parquet": ("safety", "intent"), "eval_store.db": ("code", "longctx")}[s]]
                if others:
                    st = r.choice(others)
                    rows[st].append(RRow(st, j, item, sub, b, alt(), times[k] + r.randint(1, 600), "stray"))
            elif roll < 0.265:
                sh = W.shards[b]
                oth = sh[(job["shard"] + 1 + r.below(len(sh) - 1)) % len(sh)]
                oi = r.choice(oth)
                v = dict(W.res[auth_of(W, job, oth)][(oi, sub)]) if False else alt()
                rows[prim].append(RRow(prim, j, oi, sub, b, v, times[k] + r.randint(1, 600), "misroute"))
    # rescue jobs keep a stale copy in their usual source (errata says restore from staging)
    for j in sorted(W.rescue):
        b = W.jobs[j]["bench"]
        src = PAIRS[b][0]
        for k in sorted(W.res[j]):
            v = dict(W.res[j][k])
            f = FIELDS[b][0]
            v[f] = perturb(W, r, b, f, v[f], k[0])
            rows[src].append(RRow(src, j, k[0], k[1], b, v, W.seal[j] - r.randint(60, 3600), "lost"))
    # mirror database: lagged copy of eval_store (only rows emitted before the snapshot instant)
    snap = T(2025, 9, 12)
    for rr in rows["eval_store.db"]:
        if rr.emitted < snap and r.chance(0.8):
            v = dict(rr.vals)
            if r.chance(0.06):
                f = FIELDS[rr.bench][0]
                v[f] = perturb(W, r, rr.bench, f, v[f], rr.item)
            m = RRow("eval_store_mirror.db", rr.job, rr.item, rr.sub, rr.bench, v, rr.emitted, "mirror")
            rows["eval_store_mirror.db"].append(m)
    # rescored judge copy: every authoritative pref row, rescored by an unapproved judge
    for rr in rows["judge_verdicts.jsonl"] + [x for x in rows["rerun_results.jsonl"] if x.bench == "pref"]:
        v = dict(rr.vals)
        if r.chance(0.05):
            v["verdict"] = perturb(W, r, "pref", "verdict", v["verdict"], rr.item)
        rows["judge_verdicts_rescored.jsonl"].append(RRow("judge_verdicts_rescored.jsonl", rr.job, rr.item, rr.sub, "pref", v, rr.emitted + r.randint(86400, 9 * 86400), "rescored"))
    # sandbox voids for code rows (void list lives in the mirror database)
    W.code_void = set()
    # assign row ids: per source, increasing with random gaps; overlapping number ranges across sources
    for si, s in enumerate(RESULT_SOURCES):
        lst = rows[s]
        lst.sort(key=lambda x: (x.emitted, x.job, x.item, str(x.sub), x.kind))
        n = 1000 + si * 45000 + r.randint(0, 9000)
        for x in lst:
            n += r.randint(1, 3)
            x.rid = f"r{n:07d}"
    # reversal lines for 'revd' rows
    W.rev_lines = []
    for s in RESULT_SOURCES:
        add = []
        for x in rows[s]:
            if x.kind == "revd":
                rv = RRow(s, x.job, x.item, x.sub, x.bench, {}, x.emitted + r.randint(5, 600), "rev")
                rv.target = x.rid
                add.append(rv)
        if add:
            last = max(int(x.rid[1:]) for x in rows[s])
            for rv in add:
                last += r.randint(1, 3)
                rv.rid = f"r{last:07d}"
            rows[s].extend(add)
    W.rows = rows
    # voids: errata row voids (source, rid); code voids split to the mirror db list
    W.row_void = []
    W.mirror_void = []
    for s in RESULT_SOURCES:
        for x in rows[s]:
            if x.kind == "void":
                if x.bench == "code" and s in ("code_samples.jsonl", "eval_store.db"):
                    if r.chance(0.5):
                        W.mirror_void.append((s, x.rid))
                    elif s == "code_samples.jsonl":
                        x.ctx["sentinel"] = True
                    else:
                        W.row_void.append((s, x.rid))
                else:
                    W.row_void.append((s, x.rid))
    # pref: presentation order per (job, item) slot, and reviewer verdicts
    W.present = {}
    W.reviews = []
    for j in sorted(W.jobs):
        if W.jobs[j]["bench"] == "pref":
            for iid in W.jobs[j]["items"]:
                W.present[(j, iid)] = "slot1_baseline" if r.chance(0.2) else "slot1_candidate"
    for x in rows["judge_verdicts.jsonl"]:
        if x.kind != "canon" or W.disp.get(x.job) != "authoritative":
            continue
        roll = r.rand()
        if roll < 0.18:
            truth = x.vals["verdict"]
            x.vals = dict(x.vals, verdict=perturb(W, r, "pref", "verdict", truth, x.item))
            W.reviews.append((x.job, x.item, x.sub, truth, "final", x.emitted + r.randint(3600, 5 * 86400)))
        elif roll < 0.30:
            W.reviews.append((x.job, x.item, x.sub, perturb(W, r, "pref", "verdict", x.vals["verdict"], x.item), "draft", x.emitted + r.randint(3600, 5 * 86400)))
        elif roll < 0.92:
            W.reviews.append((x.job, x.item, x.sub, x.vals["verdict"], "final", x.emitted + r.randint(3600, 5 * 86400)))
    return rows


def used_row(W, x):
    """Is this result row the source of at least one graded field of a scored result?"""
    if x.kind not in ("canon", "copy"):
        return False
    if x.src in ("judge_verdicts_rescored.jsonl", "eval_store_mirror.db"):
        return False
    if x.src == "scores_staging.parquet" and x.job not in W.rescue:
        return False
    if W.disp.get(x.job) != "authoritative" or W.elig[x.item] is not None:
        return False
    if x.emitted > W.seal[x.job]:
        return False
    b = x.bench
    if W.copy_src[x.job] is None:
        return True
    srcs = PAIRS[b]
    prim = W.route[x.job]
    for f in FIELDS[b]:
        win_primary = (W.prec[(b, f)] == "primary_family") == (prim != srcs[-1])
        if W.jclass[x.job] == "bridge":
            win_primary = not win_primary
        if (x.kind == "canon") == win_primary:
            return True
    return False

# ---------------------------------------------------------------------------------
# file build engine: rules, rows, band arrangement
# ---------------------------------------------------------------------------------
HOMO_L = {"o": "\u043e", "e": "\u0435", "a": "\u0430", "c": "\u0441", "p": "\u0440", "x": "\u0445"}
FAM_NAME = {"T1": "near-duplicate keys", "T2": "unit/scale", "T3": "time zone/epoch", "T4": "locale numerics",
            "T5": "sentinels", "T6": "voided/reversed", "T7": "superseded", "T8": "header drift",
            "T9": "embedded delimiters", "T10": "encoding", "T11": "boundaries", "T12": "rounding",
            "T13": "referential breaks", "T14": "scope in prose", "T15": "statistical bait", "T16": "decoy agreement",
            "T17": "cross-file conditional", "T18": "oscillation pair", "T19": "false equilibrium",
            "T20": "over-correction bait", "T21": "field-scoped precedence", "T22": "deferred effect"}


class FB:
    _W = None

    def __init__(self, name, decoy=False, tests=()):
        self.name, self.decoy = name, decoy
        self.rules = {}
        self.rows = []
        self.tests = list(tests)
        self.prose = []
        self.render = None
        self.anchor_note = None

    def R(self, code, family, desc, doc, via, mode="row", ht=False, bait=False, cond=False,
          fields=None, via_rules=(), direction=None, dominant=False, excl=()):
        assert code not in self.rules, (self.name, code)
        self.rules[code] = {"code": code, "family": family, "desc": desc, "doc": doc, "via": list(via),
                            "mode": mode, "ht": ht, "bait": bait, "cond": cond, "fields": fields,
                            "via_rules": list(via_rules), "direction": direction, "dominant": dominant,
                            "excl": set(excl)}

    def add(self, f, rules=(), kind=None, **ctx):
        row = {"f": f, "r": [x for x in rules if x], "k": kind, "c": ctx}
        self.rows.append(row)
        return row


def arrange(fb, rng, density=None):
    """Order rows into bands and spread line-level rules so the density targets hold."""
    rules = fb.rules
    for row in fb.rows:
        for c in row["r"]:
            assert c in rules, (fb.name, c)
    n = len(fb.rows)
    used0 = {c for row in fb.rows for c in row["r"]}
    for c in [c for c, ru in rules.items() if ru["mode"] in ("row", "ctx") and c not in used0]:
        del rules[c]
    line_rules = [c for c, r in rules.items() if r["mode"] == "line"]
    tgt = density or (0.84 if fb.decoy else 0.75)
    head_n = min(2000, n // 5)
    limit = max(2, int(len(rules) * 0.24))
    base_ht = {c for c, r in rules.items() if r["ht"]}

    n_anchor = sum(1 for row in fb.rows if row["k"] == "anchor")
    need_el = max(0, head_n - min(n_anchor // 2, int(0.35 * head_n)))

    def promote(ht, pool_rows):
        ht = set(ht)
        sets = {}
        for row in pool_rows:
            if row["k"] == "anchor":
                continue
            k_ = frozenset(row["r"])
            sets[k_] = sets.get(k_, 0) + 1
        while sum(v for k_, v in sets.items() if k_ <= ht) < need_el and len(ht) < limit:
            gain = {}
            for k_, v in sets.items():
                rest = k_ - ht
                if rest:
                    for c in rest:
                        gain[c] = gain.get(c, 0.0) + v / (len(rest) ** 2)
            if not gain:
                break
            ht.add(max(sorted(gain), key=lambda c: gain[c]))
        return ht

    half = n // 2
    ht_head = promote(base_ht, fb.rows[:half] if n > 4 * head_n else fb.rows)
    ht_tail = promote(base_ht, fb.rows[half:] if n > 4 * head_n else fb.rows)

    def take(rows, ht, k, from_end):
        anc = [r for r in rows if r["k"] == "anchor"]
        anc = anc[len(anc) - min(len(anc) // 2, int(0.35 * k)):] if from_end else anc[:min(len(anc) // 2, int(0.35 * k))]
        aid = {id(r) for r in anc}
        el = [r for r in rows if (set(r["r"]) <= ht and r["k"] != "anchor") or id(r) in aid]
        if len(el) < k:
            ids = {id(r) for r in el}
            pool_ = [r for r in rows if id(r) not in ids]
            freq_ = {}
            for r in pool_:
                k_ = frozenset(set(r["r"]) - ht)
                freq_[k_] = freq_.get(k_, 0) + 1
            extra = sorted(pool_, key=lambda r: (len(set(r["r"]) - ht), -freq_[frozenset(set(r["r"]) - ht)], sorted(set(r["r"]) - ht)))
            el_ids = ids | {id(r) for r in extra[:k - len(el)]}
            el = [r for r in rows if id(r) in el_ids]
        return el[len(el) - k:] if from_end else el[:k]

    head = take(fb.rows, ht_head, head_n, False)
    hid = {id(r) for r in head}
    tail = take([r for r in fb.rows if id(r) not in hid], ht_tail, head_n, True)
    tid = {id(r) for r in tail}
    middle = [r for r in fb.rows if id(r) not in hid and id(r) not in tid]
    def spread(seg):
        anchors = [r for r in seg if r["k"] == "anchor"]
        if not anchors:
            return seg
        rest = [r for r in seg if r["k"] != "anchor"]
        step = len(rest) / (len(anchors) + 1)
        out_ = []
        ai = 0
        for i, r in enumerate(rest):
            while ai < len(anchors) and (ai + 1) * step <= i:
                out_.append(anchors[ai])
                ai += 1
            out_.append(r)
        return out_ + anchors[ai:]
    ordered = spread(head) + spread(middle) + spread(tail)
    usage = {c: 0 for c in rules}
    for row in ordered:
        for c in row["r"]:
            usage[c] += 1

    def applicable(row, allowed):
        out = []
        for c in allowed:
            fl = rules[c]["fields"]
            if fl and all(row["f"].get(x) not in (None, "") for x in fl) and c not in row["r"]:
                if any(c in rules[o]["excl"] or o in rules[c]["excl"] for o in row["r"]):
                    continue
                out.append(c)
        return out

    def pick(row, allowed, bait=None):
        cands = applicable(row, allowed)
        if bait is not None:
            cands = [c for c in cands if rules[c]["bait"] == bait]
        if not cands:
            return False
        cands.sort(key=lambda c: (usage[c], c))
        c = cands[0]
        row["r"].append(c)
        usage[c] += 1
        return True

    B = (n + 999) // 1000
    for b in range(B):
        band = ordered[b * 1000:(b + 1) * 1000]
        if b * 1000 < head_n:
            allowed = [c for c in line_rules if c in ht_head]
        elif (b + 1) * 1000 > n - head_n:
            allowed = [c for c in line_rules if c in ht_tail]
        else:
            allowed = line_rules
        trap = [r for r in band if r["r"]]
        need = int(math.ceil(tgt * len(band))) - len(trap)
        nb = int(0.14 * max(len(trap), tgt * len(band))) - sum(1 for r in trap if any(rules[c]["bait"] for c in r["r"]))
        cand = [r for r in band if r["k"] != "anchor"]
        plain = [r for r in cand if not r["r"]]
        rng.shuffle(plain)
        if nb > 0:
            others = [r for r in cand if r["r"] and not any(rules[c]["bait"] for c in r["r"])]
            rng.shuffle(others)
            for row in plain + others:
                if nb <= 0:
                    break
                was_plain = not row["r"]
                if pick(row, allowed, bait=True):
                    nb -= 1
                    if was_plain:
                        need -= 1
        for row in plain:
            if need <= 0:
                break
            if row["r"]:
                continue
            if pick(row, allowed, bait=False) or pick(row, allowed):
                need -= 1
        trap = [r for r in band if r["r"]]
        stacked = sum(1 for r in trap if len(r["r"]) >= 2)
        want = int(math.ceil(0.40 * len(trap))) - stacked
        singles = [r for r in trap if len(r["r"]) == 1]
        rng.shuffle(singles)
        for row in singles:
            if want <= 0:
                break
            if pick(row, allowed, bait=False):
                want -= 1
    # every declared line rule must actually occur: top up rare ones in the middle bands
    mid = [r for r in ordered[head_n:n - head_n] if r["k"] != "anchor"]
    m = max(15, int(0.004 * n))
    for c in sorted(line_rules):
        if usage[c] >= m:
            continue
        cands = [r for r in mid if c in applicable(r, [c])]
        rng.shuffle(cands)
        for row in cands[:m - usage[c]]:
            row["r"].append(c)
            usage[c] += 1
    for c in [c for c in line_rules if usage[c] == 0]:
        del rules[c]
    for row in ordered:
        bait = any(rules[c]["bait"] for c in row["r"])
        row["k"] = "anchor" if row["k"] == "anchor" else ("bait" if bait else ("trap" if row["r"] else "plain"))
    fb.rows = ordered
    fb.ht_head, fb.ht_tail = ht_head, ht_tail
    return fb


# ---- value helpers ------------------------------------------------------------------
def v_id(s, rules, tag):
    if tag + "_CASE" in rules:
        s = s.lower() if s[:1].isupper() else s.upper()
    if tag + "_PAD" in rules:
        head, _, num = s.rpartition("-") if "-" in s else (s[0], "", s[1:])
        if "-" in s:
            s = head + "-" + (num.lstrip("0") or "0")
        else:
            s = s[0] + (s[1:].lstrip("0") or "0")
    if tag + "_HOMO" in rules:
        for i, ch in enumerate(s):
            if ch in HOMO:
                s = s[:i] + HOMO[ch] + s[i + 1:]
                break
            if ch in HOMO_L:
                s = s[:i] + HOMO_L[ch] + s[i + 1:]
                break
    if tag + "_FW" in rules:
        s = "".join(chr(0xFF10 + int(ch)) if ch.isdigit() else ch for ch in s)
    if tag + "_WS" in rules:
        s = "\u00a0" + s + " "
    return s


def v_rev(rev, rules):
    if "REV_TXT" in rules:
        return f"r{rev}"
    return f"{rev:02d}" if "REV_PAD" in rules else str(rev)


def v_tw(s, rules):
    return s + "  " if "TRAIL_WS" in rules else s


def v_lb(s, rules):
    return s + "\r\n" if "LINEBREAK" in rules else s


def kit_tab(fb, rev=True, tw=True, lb=False, doc=None):
    doc = doc or (SC if fb.name != SC else POL)
    via = [doc, POL if doc != POL else SC]
    if rev:
        fb.R("REV_TXT", "T4", f"Revision values in {fb.name} can be written with an r prefix (r3 means 3).", doc, via, mode="line", fields=["revf"])
        fb.R("REV_PAD", "T4", f"Revision values in {fb.name} can be zero-padded (03 means 3).", doc, via, mode="line", fields=["revf"], excl=("REV_TXT",))
    if tw:
        fb.R("TRAIL_WS", "T9", f"Cells of {fb.name} can carry trailing spaces; strip them.", doc, via, mode="line", fields=["twf"])
    if lb:
        fb.R("LINEBREAK", "T10", f"Text cells inside {fb.name} can end with a carriage return and line feed; strip them.", doc, via, mode="line", fields=["lbf"])


def group3(intpart, sep):
    out = []
    while len(intpart) > 3:
        out.insert(0, intpart[-3:])
        intpart = intpart[:-3]
    out.insert(0, intpart)
    return sep.join(out)


def v_num(d, dp, locale="en_US", group=True, paren=False):
    neg = d < 0
    s = format(abs(d).quantize(Decimal(1).scaleb(-dp)) if dp else abs(d).quantize(Decimal(1)), "f")
    ip, _, fp = s.partition(".")
    if locale == "en_IN" and group and len(ip) > 3:
        head, last3 = ip[:-3], ip[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        ip = ",".join(parts) + "," + last3
    elif group:
        ip = group3(ip, {"en_US": ",", "de_DE": ".", "fr_FR": " ", "en_IN": ","}[locale])
    dec = "," if locale in ("de_DE", "fr_FR") else "."
    s = ip + (dec + fp if fp else "")
    if neg:
        s = "(" + s + ")" if paren else "-" + s
    return s


def v_excess(d, dp, rng):
    """d with two extra digits whose half-even rounding back to dp returns d."""
    q = Decimal(1).scaleb(-dp)
    while True:
        extra = Decimal(rng.randint(-49, 50)).scaleb(-dp - 2)
        if rng.chance(0.25):
            extra = Decimal(50).scaleb(-dp - 2) * (1 if rng.chance(0.5) else -1)
        cand = d + extra
        if cand.quantize(q, rounding=ROUND_HALF_EVEN) == d and cand >= 0:
            return format(cand, "f")


def local_str(t, tz, offset_ms=0, fmt="%Y-%m-%d %H:%M:%S", ms=True):
    tt = t * 1000 + offset_ms + TZ_OFFSET[tz] * 1000
    s = time.strftime(fmt, time.gmtime(tt // 1000))
    return s + (f".{tt % 1000:03d}" if ms else "")


def excel_serial(t):
    """Days since 1899-12-30 (the convention that absorbs the 1900 leap-year bug), as a float."""
    return round((t - T(1899, 12, 30)) / 86400.0, 6)


def rfc2822(t, tz):
    off = TZ_OFFSET[tz]
    tt = time.gmtime(t + off)
    sign = "+" if off >= 0 else "-"
    return time.strftime("%a, %d %b %Y %H:%M:%S ", tt) + f"{sign}{abs(off) // 3600:02d}{(abs(off) % 3600) // 60:02d}"

# ---------------------------------------------------------------------------------
# result-bearing sources
# ---------------------------------------------------------------------------------
POL, SC, CT, FP = "certification_policy.md", "source_conventions.md", "control_totals.html", "field_precedence.html"
ER, RM, MD, MA = "errata_register.docx", "review_minutes.docx", "metric_definitions.pdf", "methodology_appendix.pdf"
INELIG_CODE = {"retired": "INELIG_RET", "duplicate": "INELIG_DUP", "contaminated": "INELIG_CON", "out_of_scope": "INELIG_HO"}


def inelig_rules(fb, what, effect, doc=None):
    doc = doc or "certification_policy.md"
    fb.R("INELIG_RET", "T14", f"{what} for items retired in the suite manifest {effect}.", doc, [doc, "suite_manifest.xlsx", "certification_policy.md"], mode="row")
    fb.R("INELIG_DUP", "T14", f"{what} for items that are non-canonical members of a dedup cluster {effect}.", doc, [doc, "dedup_clusters.tsv", "certification_policy.md"], mode="row")
    fb.R("INELIG_CON", "T14", f"{what} for items with a counted contamination hit at or above the suite threshold {effect}.", doc, [doc, "contamination_hits.jsonl", "errata_register.docx", "certification_policy.md"], mode="row")
    fb.R("INELIG_HO", "T14", f"{what} for held-out items {effect}; held-out is the last exclusion reason.", doc, [doc, "certification_policy.md", "suite_manifest.xlsx"], mode="row")


INV, CLK, MBOX, REG, REGX = "host_inventory.ini", "clock_offsets.txt", "evalops_notifications.mbox", "run_registry.xml", "run_registry_export.xml"
TZ_CODES = [("Europe/Berlin", "TZ_BER"), ("America/Chicago", "TZ_CHI"), ("Asia/Kolkata", "TZ_KOL"), ("America/Sao_Paulo", "TZ_SAO")]
LOC_CODES = {"de_DE": "LOC_DE", "fr_FR": "LOC_FR", "en_IN": "LOC_IN"}
JOBKIND_RULE = {"stale_checkpoint": "JOB_STALE", "voided": "JOB_VOID", "staging_host": "JOB_STAGE",
                "outside_window": "JOB_OUT", "maintenance": "JOB_MAINT", "superseded": "JOB_SUPER",
                "rerun_denied": "JOB_DENIED", "unregistered": "FK"}


def g(f, c):
    return f"{f}::{c}"


def kit_ids(fb, field, tag, label, registry, ht=(), dominant=False):
    if ht == ("CASE",) and fb.name not in ("results_fleet_a.log", "results_fleet_b.log", "results_fleet_c.log", "harness_events.log"):
        ht = ("CASE", "PAD")
    if not ht and not any(c.endswith("_CASE") and ru["ht"] for c, ru in fb.rules.items()):
        ht = ("CASE", "PAD")
    reg = [g(registry, tag + s) for s in ("_CASE", "_PAD", "_HOMO", "_WS")] if registry != fb.name else []
    fb.R(tag + "_CASE", "T1", f"{label} values in {fb.name} can be written in the wrong letter case; compare them in the canonical case of the identifier grammar.",
         POL, [POL, registry], mode="line", fields=[field], via_rules=reg[:1], ht="CASE" in ht, dominant=dominant)
    fb.R(tag + "_PAD", "T1", f"{label} values in {fb.name} can lose their zero padding; restore the fixed digit width of the identifier grammar.",
         POL, [POL, registry], mode="line", fields=[field], via_rules=reg[1:2], ht="PAD" in ht, dominant=dominant)
    if fb.name.endswith(".pdf"):
        fb.R(tag + "_WS", "T1", f"{label} values in {fb.name} can carry leading or trailing spaces; strip them before joining.",
             POL, [POL, registry], mode="line", fields=[field], via_rules=reg[3:4], ht="WS" in ht, dominant=dominant)
        return
    fb.R(tag + "_HOMO", "T1", f"{label} values in {fb.name} can carry a Cyrillic look-alike letter from the confusables table; map it back to Latin before joining.",
         POL, [POL, registry], mode="line", fields=[field], via_rules=reg[2:3], ht="HOMO" in ht, dominant=dominant)
    fb.R(tag + "_WS", "T1", f"{label} values in {fb.name} can carry leading or trailing spaces or no-break spaces; strip them before joining.",
         POL, [POL, registry], mode="line", fields=[field], via_rules=reg[3:4], ht="WS" in ht, dominant=dominant)
    fb.R(tag + "_FW", "T10", f"{label} values in {fb.name} can use full-width digits; apply Unicode NFKC before joining.",
         POL, [POL, registry], mode="line", fields=[field], via_rules=reg[:1], dominant=dominant, excl=("LATIN1",))


def kit_hosttime(fb, ht=()):
    for tz, code in TZ_CODES:
        off = TZ_OFFSET[tz]
        sign = "+" if off >= 0 else "-"
        fb.R(code, "T3", f"Timestamps in {fb.name} without an explicit zone are host wall-clock time; for jobs whose submission-week inventory zone is {tz} the offset during the window is UTC{sign}{abs(off) // 3600:02d}:{(abs(off) % 3600) // 60:02d}.",
             SC, [SC, INV], mode="ctx", cond=True, via_rules=[g(INV, "H_CASE"), g(INV, "SUPERSEDE")], ht=code in ht, dominant=True)
    fb.R("SKEW", "T3", f"Host-written timestamps in {fb.name} carry the host clock error for the submission week; subtract the clock offset listed for that host and week.",
         SC, [SC, CLK], mode="ctx", via_rules=[g(CLK, "H_PAD"), g(CLK, "SUPERSEDE")], ht="SKEW" in ht)
    fb.R("EQUI", "T19", f"Zone and clock settings for {fb.name} rows follow the inventory snapshot of the submission week, not the host's first or most common snapshot; re-imaged hosts change zone mid-quarter.",
         SC, [INV, CLK], mode="ctx", cond=True, via_rules=[g(INV, "SUPERSEDE")], ht="EQUI" in ht)


def kit_locale(fb, field, ht=()):
    for loc, code in LOC_CODES.items():
        desc = {"de_DE": "a comma decimal mark and dot thousands grouping", "fr_FR": "a comma decimal mark and space thousands grouping",
                "en_IN": "Indian lakh grouping (12,34,567.50)"}[loc]
        fb.R(code, "T4", f"Numbers in {fb.name} follow the host locale of the submission week; {loc} hosts write {desc}.",
             SC, [SC, INV], mode="ctx", cond=True, fields=[field], via_rules=[g(INV, "SUPERSEDE")], ht=code in ht)


def row_kinds(W, name):
    ks = set()
    for x in W.rows[name]:
        ks.add(x.kind)
        ks.add(W.jobs[x.job]["kind"])
    return ks


def kit_rows(fb, kinds, ht=()):
    if "late" in kinds:
        fb.R("LATE", "T22", f"Result rows in {fb.name} are provisional until the job is sealed; a row emitted after the seal time in the operations mailbox is ignored.",
             SC, [MBOX, SC] if fb.name != SC else [MBOX, POL], mode="row", via_rules=[g(MBOX, "TZ_HDR")])
        fb.R("SEALEQ", "T11", f"A {fb.name} row emitted exactly at the seal instant is inside the seal (at or before).",
             MA, [MBOX, MA], mode="row", via_rules=[g(MBOX, "TZ_HDR")])
    if "void" in kinds:
        fb.R("VOID", "T6", f"Rows of {fb.name} listed by row id in the errata register void list are void.",
             ER, [ER, POL], mode="row", via_rules=[g(ER, "RID_SRC")])
        fb.R("OVERCORR", "T20", f"A void entry names a source file and a row id; a {fb.name} row whose id matches a void entry of another source stays live.",
             ER, [ER, POL], mode="ctx", bait=True)
    if "older" in kinds:
        fb.R("OLDER", "T7", f"When {fb.name} holds more than one live row for the same job, item and sample, the row with the latest emitted instant (UTC) wins.",
             SC, [SC, INV], mode="row", via_rules=[g(fb.name, "TZ_BER")] if "TZ_BER" in fb.rules else [])
    if "revd" in kinds:
        fb.R("REVERSAL", "T6", f"A REVERSE line in {fb.name} cancels the row whose id it names; the cancelled row and the REVERSE line itself carry no result.",
             SC, [SC, ER], mode="row")
    if "stray" in kinds:
        fb.R("STRAY", "T13", f"Rows of {fb.name} for a job whose routing entry names neither {fb.name} as primary nor as copy source are stray and are ignored.",
             SC, [SC, REG], mode="row", via_rules=[g(SC, "J_CASE")])
    if "misroute" in kinds:
        fb.R("MISROUTE", "T13", f"A {fb.name} row whose item is not in the shard of its job (shard map in the metric definitions) is misrouted and ignored.",
             MD, [MD, REG], mode="row", via_rules=[g(MD, "I_PAD"), g(REG, "J_CASE")])
    if "lost" in kinds:
        fb.R("RESCUE", "T6", f"For jobs the errata register marks RESTORE, the {fb.name} rows are lost copies; the job's rows are restored from the staging snapshot named in the entry.",
             ER, [ER, "scores_staging.parquet"], mode="row", via_rules=[g(ER, "J_CASE")])
    if "shadow" in kinds:
        fb.R("SHADOW", "T14", f"Rows of {fb.name} tagged src=shadow are shadow traffic and are out of scope for certification.",
             POL, [POL, SC], mode="row")
    fb.R("ERRATA_GOLD", "T7", f"Correctness of {fb.name} rows is judged against the gold after upheld grader errata, not the raw gold file.",
         MD, ["gold_labels.tsv", "grader_errata.xml", "gold_labels_corrected.csv"], mode="row")
    fb.R("LANG_SUPPORT", "T11", f"A multilingual row of {fb.name} counts toward the macro average only through its item's prompt-locale language, and only when that language meets the minimum support.",
         MD, ["prompt_locales.tsv", "locale_codes_legacy.tsv", "slice_definitions.yaml"], mode="row")
    inelig_rules(fb, f"Rows of {fb.name}", "carry no score")
    for kind, code in JOBKIND_RULE.items():
        if kind in kinds:
            desc, via, vr = {
                "JOB_STALE": ("job ran a checkpoint other than the one its model alias certifies", ["model_tags.yaml", MBOX, "checkpoint_lineage.json"], [g("model_tags.yaml", "DEFERRED"), g(MBOX, "TZ_HDR")]),
                "JOB_VOID": ("job is listed in the errata job void list", [ER, REG], [g(ER, "J_CASE")]),
                "JOB_STAGE": ("job host was a staging host in its submission week", [INV, "harness_events.log"], [g(INV, "SUPERSEDE")]),
                "JOB_OUT": ("job was submitted outside the half-open certification window", ["harness_events.log", POL], [g("harness_events.log", "TZ_BER")]),
                "JOB_MAINT": ("job was submitted inside a maintenance window of its host without an exemption", ["maintenance_windows.ics", RM], [g("maintenance_windows.ics", "TZ_LOCAL")]),
                "JOB_SUPER": ("job was replaced by an approved rerun", ["harness_events.log", RM], [g(RM, "J_CASE")]),
                "JOB_DENIED": ("job is a rerun without an approval", ["harness_events.log", RM], [g(RM, "J_CASE")]),
                "FK": ("job id is not in the run registry (only the retired scheduler export lists it)", [REG, REGX], [g(REG, "J_CASE")]),
            }[code]
            fam = {"JOB_STALE": "T22", "JOB_VOID": "T6", "JOB_STAGE": "T17", "JOB_OUT": "T11", "JOB_MAINT": "T17",
                   "JOB_SUPER": "T7", "JOB_DENIED": "T22", "FK": "T13"}[code]
            fb.R(code, fam, f"Rows of {fb.name} whose {desc} do not count.", POL, via, mode="row", via_rules=vr)


def kit_prec(fb, partner):
    W_ = fb._W
    partners = {}
    for x in W_.rows[fb.name]:
        cs = W_.copy_src.get(x.job)
        if cs:
            other = cs if W_.route[x.job] == fb.name else W_.route[x.job]
            partners.setdefault(x.bench, set()).add(other)
    for b in sorted(partners):
        fb.R("PREC_" + b, "T21", f"For {b} jobs whose results appear in two production sources, each field of a {fb.name} row is used only when the field precedence table names this source as the winner for that field.",
             FP, [FP] + sorted(partners[b] - {fb.name}), mode="row", via_rules=[g(FP, "J_CASE")])
    fb.R("OSC", "T18", f"Jobs of the bridge authority class reverse the default field precedence between {fb.name} and {partner}.",
         FP, [FP, SC], mode="row", via_rules=[g(FP, "CLASS")])


def base_rules(W, fb, x, numeric=True):
    """Context and row rules that follow from the world for a result row."""
    rs = []
    job = W.jobs[x.job]
    wk = iso_week(job["submitted"])
    hw = W.hw[(job["host"], wk)]
    if hw["offset_ms"] and "SKEW" in fb.rules:
        rs.append("SKEW")
    if "TZ_BER" in fb.rules:
        for tz, code in TZ_CODES:
            if hw["tz"] == tz:
                rs.append(code)
        if wk > WEEKS[0] and W.hw[(job["host"], wk - 1)]["tz"] != hw["tz"] and "EQUI" in fb.rules:
            rs.append("EQUI")
    if numeric and "LOC_DE" in fb.rules and hw["locale"] in LOC_CODES:
        rs.append(LOC_CODES[hw["locale"]])
    if "SCALE" in fb.rules and hw["scale"] == 100 and numeric:
        rs.append("SCALE")
    if x.item and x.item in W.gold_err and x.kind in ("canon", "copy") and x.bench not in ("code", "pref") and "ERRATA_GOLD" in fb.rules:
        rs.append("ERRATA_GOLD")
    if x.item and x.bench == "multiling" and x.kind in ("canon", "copy") and "LANG_SUPPORT" in fb.rules and hash_pick(x.rid, "lang") < 0.15:
        rs.append("LANG_SUPPORT")
    if x.item and W.elig.get(x.item) is not None and x.kind in ("canon", "copy", "stgcopy"):
        c_ = INELIG_CODE[W.elig[x.item]]
        if c_ in fb.rules:
            rs.append(c_)
    if x.kind == "stray" and "STRAY" in fb.rules:
        rs.append("STRAY")
    if x.kind == "misroute" and "MISROUTE" in fb.rules:
        rs.append("MISROUTE")
    k = {"older": "OLDER", "late": "LATE", "void": "VOID", "revd": "REVERSAL", "rev": "REVERSAL", "shadow": "SHADOW",
         "lost": "RESCUE"}.get(x.kind)
    if k and k in fb.rules:
        rs.append(k)
    if x.kind == "void" and x.ctx.get("sentinel"):
        rs = [c for c in rs if c != "VOID"] + ["SENT_EXIT"]
    if x.kind in ("canon", "copy") and x.emitted == W.seal[x.job] and "SEALEQ" in fb.rules:
        rs.append("SEALEQ")
    jk = job["kind"]
    if jk in JOBKIND_RULE and JOBKIND_RULE[jk] in fb.rules:
        rs.append(JOBKIND_RULE[jk])
    if W.copy_src[x.job] and x.kind in ("canon", "copy") and "PREC_" + x.bench in fb.rules:
        rs.append("PREC_" + x.bench)
        if W.jclass[x.job] == "bridge" and "OSC" in fb.rules:
            rs.append("OSC")
    if x.src in W._void_rids_other and x.rid in W._void_rids_other[x.src] and "OVERCORR" in fb.rules:
        rs.append("OVERCORR")
    return rs


def host_ts(W, x, rules, rng=None):
    job = W.jobs[x.job]
    hw = W.hw[(job["host"], iso_week(job["submitted"]))]
    if "B_UTC" in rules:
        return iso(x.emitted)
    return local_str(x.emitted, hw["tz"], hw["offset_ms"])


def fmt_val_num(W, x, d, dp, rules, rng):
    job = W.jobs[x.job]
    hw = W.hw[(job["host"], iso_week(job["submitted"]))]
    if "SCALE" in rules:
        d = d * 100
        dp = max(0, dp - 2)
    if "ROUND" in rules:
        s = v_excess(abs(d), dp, rng)
        dd = Decimal(s)
        dpx = dp + 2
    else:
        dd, dpx = abs(d), dp
    loc = hw["locale"] if any(c in rules for c in LOC_CODES.values()) else "en_US"
    s = v_num(dd, dpx, loc, group=True)
    if d < 0:
        s = ("(" + s + ")") if "NEG_PAREN" in rules else "-" + s
    return s


def label_alias(W, cls, taxo, rng, cond):
    """A raw alias string resolving to cls under taxonomy taxo."""
    if cond and W.ambig.get((taxo, cls)):
        return rng.choice(W.ambig[(taxo, cls)])
    return rng.choice(W.alias_of[(taxo, cls)])


def build_logs(W, rngs):
    out = []
    spec = {"results_fleet_a.log": ("arith", "intent"), "results_fleet_b.log": ("safety", "mcq"),
            "results_fleet_c.log": ("longctx", "multiling")}
    partner = {"results_fleet_a.log": "legacy_results.txt", "results_fleet_b.log": "scores_shard2.parquet",
               "results_fleet_c.log": "eval_store.db"}
    for name, benches in spec.items():
        r = rngs(name)
        fb = FB(name, tests=["item_scores_" + b for b in benches] + ["source_audit_rows", "source_audit_used"])
        kit_ids(fb, "job", "J", "Job id", REG, ht=("CASE",))
        kit_ids(fb, "item", "I", "Item id", "item_registry.csv", ht=("PAD",))
        kit_ids(fb, "host", "H", "Host name", INV, ht=("NONE",))
        kit_hosttime(fb, ht=("TZ_BER", "TZ_CHI"))
        numeric = name != "results_fleet_c.log"
        if numeric:
            kit_locale(fb, "val")
            fb.R("ROUND", "T12", f"Numeric values in {name} can carry two digits beyond the documented precision; round half-even to the documented precision before use.",
                 MD, [MD, "scoring_parameters.xlsx"], mode="line", fields=["val"])
            fb.R("NEG_PAREN", "T4", f"Negative numbers in {name} can be written in parentheses.", SC, [SC, "gold_labels.tsv"], mode="line", fields=["neg"])
        if name == "results_fleet_b.log":
            fb.R("SCALE", "T2", f"In {name}, hosts whose submission-week inventory scale is pct write scores and confidences as percentages.",
                 SC, [SC, INV], mode="ctx", cond=True, via_rules=[g(INV, "SUPERSEDE")])
            fb.R("OUTLIER", "T15", f"Scores of exactly 0 or 1 and confidences of exactly 1 in {name} are valid model outputs and are kept.",
                 MD, [MD, "gold_labels.tsv"], mode="ctx", bait=True)
        if name == "results_fleet_a.log":
            fb.R("COND", "T17", "Intent labels in results_fleet_a.log are raw aliases; the same alias can resolve to different classes under taxonomy v1 and v2, chosen by the job's harness version.",
                 "label_aliases.json", ["label_aliases.json", "job_configs.toml"], mode="ctx", cond=True, via_rules=[g("job_configs.toml", "J_CASE")])
            fb.R("SENT_NA", "T5", "In results_fleet_a.log an arithmetic answer of N/A is an abstention and scores as wrong; it is not a missing value.",
                 SC, [SC, "legacy_results.txt"], mode="ctx", cond=True)
            fb.R("OUTLIER", "T15", "Arithmetic answers in results_fleet_a.log can be very large or negative; they are graded as written.",
                 MD, [MD, "gold_labels.tsv"], mode="ctx", bait=True)
        if name == "results_fleet_c.log":
            fb.R("NFD", "T10", "Free-text answers in results_fleet_c.log can be in decomposed Unicode form; compare in NFC.",
                 MD, [MD, "gold_labels.tsv"], mode="line", fields=["text"])
            fb.R("LATIN1", "T10", "Some results_fleet_c.log lines were relayed as Latin-1 bytes; a line that is not valid UTF-8 is Latin-1.",
                 SC, [SC, "gold_labels.tsv"], mode="line", fields=["latin"], excl=("I_HOMO", "J_HOMO", "H_HOMO", "NFD"))
            fb.R("TRUNC", "T17", "Long-context items whose prompt token count for the model's tokenizer exceeds the model's context window score as wrong whatever the answer says.",
                 MD, ["context_lengths.csv", "checkpoint_lineage.json", "checkpoint_lineage_snapshot.json"], mode="ctx", cond=True, via_rules=[g("context_lengths.csv", "KUNIT")])
            fb.R("GRADER", "T17", "Multilingual answers are compared under the grader of the job's harness version; grader g3 also ignores combining accents.",
                 MD, ["job_configs.toml", "gold_labels.tsv"], mode="ctx", cond=True, via_rules=[g("job_configs.toml", "J_CASE")])
        if name != "results_fleet_b.log":
            fb.R("EMBED", "T9", f"Text values in {name} that contain spaces or equals signs are double-quoted; a quoted value is one field.",
                 SC, [SC, "label_aliases.json"], mode="ctx")
        fb.R("B_UTC", "T20", f"Lines of {name} whose timestamp ends in Z were written by the uploader in UTC with a corrected clock; they take no zone or clock correction.",
             SC, [SC, INV], mode="line", bait=True, fields=["ts"], ht=True)
        kit_rows(fb, row_kinds(W, name))
        kit_prec(fb, partner[name])
        rows = [x for x in W.rows[name]]
        rows.sort(key=lambda x: (int(x.rid[1:])))
        per_job = {}
        for x in rows:
            job = W.jobs[x.job]
            if x.kind == "rev":
                fb.add({"x": x, "job": x.job, "item": None, "host": job["host"], "ts": 1}, base_rules(W, fb, x, False))
                continue
            vals = x.vals
            f = {"x": x, "job": x.job, "item": x.item, "host": job["host"], "ts": 1, "text": None, "val": None, "neg": None, "latin": None}
            b = x.bench
            if b == "arith":
                f["val"] = None if vals["answer"] is None else 1
                f["neg"] = 1 if (vals["answer"] is not None and vals["answer"] < 0) else None
            elif b in ("safety", "mcq"):
                f["val"] = 1
            elif b == "intent":
                f["text"] = 1
            else:
                f["text"] = 1
                a = vals["answer"]
                if a == unicodedata.normalize("NFC", a) and any(ord(c) > 127 for c in a) and all(ord(c) < 256 for c in a):
                    f["latin"] = 1
            rs = base_rules(W, fb, x, numeric=b not in ("intent", "longctx", "multiling"))
            if b == "intent":
                cond = TAXO[job["harness"]] == "v2" and x.kind in ("canon", "copy") and r.chance(0.35) and bool(W.ambig.get(("v2", vals["label"])))
                f["lab"] = label_alias(W, vals["label"], TAXO[job["harness"]], r, cond)
                if cond:
                    rs.append("COND")
                if " " in f["lab"] or "=" in f["lab"]:
                    rs.append("EMBED")
            if b in ("longctx", "multiling") and (" " in vals["answer"] or "=" in vals["answer"]):
                rs.append("EMBED")
            if b == "arith" and vals["answer"] is None:
                rs.append("SENT_NA")
            if b == "arith" and vals["answer"] is not None and (abs(vals["answer"]) >= 1000000 or vals["answer"] < 0):
                rs.append("OUTLIER")
            if b in ("safety",) and vals["score"] in (Decimal(0), Decimal(1)):
                rs.append("OUTLIER")
            if b == "mcq" and vals["conf"] == Decimal(1):
                rs.append("OUTLIER")
            if b == "longctx":
                fam = FAMILY[job["model"]]
                if W.items[x.item]["tokens"][TOKENIZER[fam]] > CTX_WINDOW[fam]:
                    rs.append("TRUNC")
            if b == "multiling" and W.grader_of_harness[job["harness"]] == "g3" and strip_marks(vals["answer"]) == vals["answer"] != W.items[x.item]["gold"]:
                rs.append("GRADER")
            fb.add(f, rs)
            if x.kind == "canon":
                per_job[x.job] = per_job.get(x.job, 0) + 1
        # anchors: one flush line per job after its last canonical row
        anchors = {}
        for j, n in per_job.items():
            anchors[j] = n
        out_rows = []
        seen = {}
        last_idx = {}
        for i, row in enumerate(fb.rows):
            if row["f"]["x"].kind == "canon":
                last_idx[row["f"]["x"].job] = i
        for i, row in enumerate(fb.rows):
            out_rows.append(row)
            j = row["f"]["x"].job
            if last_idx.get(j) == i:
                out_rows.append({"f": {"anchor_job": j, "n": anchors[j], "x": row["f"]["x"]}, "r": [], "k": "anchor", "c": {}})
        fb.rows = out_rows

        def render(fb=fb, name=name, r=r):
            lines = []
            for row in fb.rows:
                f, rules = row["f"], row["r"]
                x = f["x"]
                job = W.jobs[x.job]
                if row["k"] == "anchor":
                    hw = W.hw[(job["host"], iso_week(job["submitted"]))]
                    lines.append(f"{local_str(W.seal[x.job], hw['tz'], hw['offset_ms'])} {job['host']} INFO job={x.job} flushed rows={f['n']}")
                    continue
                ts = host_ts(W, x, rules)
                host = v_id(job["host"], rules, "H")
                jid = v_id(x.job, rules, "J")
                if x.kind == "rev":
                    lines.append(f"{ts} {host} WARN rid={x.rid} op=REVERSE target={x.target} job={jid}")
                    continue
                item = v_id(x.item, rules, "I")
                vals = x.vals
                b = x.bench
                level = "INFO"
                if b == "arith":
                    v = "N/A" if vals["answer"] is None else fmt_val_num(W, x, vals["answer"], 2, rules, r)
                    body = f"bench=arith ans={v}" if " " not in v else f'bench=arith ans="{v}"'
                elif b == "safety":
                    v = fmt_val_num(W, x, vals["score"], 3, rules, r)
                    body = f'bench=safety score="{v}"' if " " in v else f"bench=safety score={v}"
                elif b == "mcq":
                    v = fmt_val_num(W, x, vals["conf"], 4, rules, r)
                    body = f"bench=mcq opt={vals['option']} " + (f'conf="{v}"' if " " in v else f"conf={v}")
                elif b == "intent":
                    lab = f["lab"]
                    q = " " in lab or "=" in lab
                    body = f'bench=intent label="{lab}"' if q else f"bench=intent label={lab}"
                else:
                    a = vals["answer"]
                    if "NFD" in rules:
                        a = unicodedata.normalize("NFD", a)
                    q = " " in a or "=" in a
                    body = f"bench={b} " + (f'ans="{a}"' if q else f"ans={a}")
                tail = " src=shadow" if x.kind == "shadow" else ""
                line = f"{ts} {host} {level} rid={x.rid} job={jid} item={item} {body}{tail}"
                lines.append(("LATIN1", line) if "LATIN1" in rules else line)
            out = bytearray()
            for ln in lines:
                if isinstance(ln, tuple):
                    out += ln[1].encode("latin-1", errors="strict") + b"\n"
                else:
                    out += ln.encode("utf-8") + b"\n"
            return bytes(out)
        fb.render = render
        out.append(fb)
    return out

# ---------------------------------------------------------------------------------
# result-bearing sources, part 2
# ---------------------------------------------------------------------------------
def hash_pick(*parts):
    return int.from_bytes(hashlib.blake2b("|".join(parts).encode(), digest_size=4).digest(), "big") / 4294967296.0


def hwof(W, j):
    job = W.jobs[j]
    return W.hw[(job["host"], iso_week(job["submitted"]))]


def epoch_ms_host(W, x):
    return x.emitted * 1000 + hwof(W, x.job)["offset_ms"]


def common_result_rules(W, fb, name, partner, idsets, host_rules=False, decoy=False):
    for field, tag, label, reg in idsets:
        kit_ids(fb, field, tag, label, reg, ht=("CASE",) if tag == "J" else (("PAD",) if tag == "I" else ()))
    if host_rules:
        fb.R("SKEW", "T3", f"Host-written timestamps in {name} carry the host clock error for the submission week; subtract the clock offset listed for that host and week.",
             SC, [SC, CLK], mode="ctx", via_rules=[g(CLK, "H_PAD"), g(CLK, "SUPERSEDE")])
    kit_rows(fb, row_kinds(W, name))
    if partner:
        kit_prec(fb, partner)


def build_results2(W, rngs):
    out = []
    # ---------------- code_samples.jsonl ----------------
    name = "code_samples.jsonl"
    r = rngs(name)
    fb = FB(name, tests=["item_scores_code", "metric_code", "source_audit_rows", "source_audit_used"])
    common_result_rules(W, fb, name, "eval_store.db", [("job", "J", "Job id", REG), ("item", "I", "Problem id", "item_registry.csv"),
                                                        ("host", "H", "Worker host", INV)], host_rules=True)
    fb.R("EPOCH", "T3", "In code_samples.jsonl a numeric ts is epoch milliseconds of the worker clock; a string ts is ISO 8601 with the worker's numeric offset.",
         SC, [SC, CLK], mode="line", fields=["ts"])
    fb.R("SENT_EXIT", "T5", "A code sample with exit 137 and passed -1 is a sandbox kill; it is void and the retry row for the same sample stands.",
         SC, [SC, "eval_store_mirror.db"], mode="row")
    fb.R("MIRRORVOID", "T6", "Sandbox failures that exited normally are listed in the void_requests table of the replica database; those code rows are void even though the replica is otherwise stale.",
         POL, ["eval_store_mirror.db", POL], mode="row", via_rules=[g("eval_store_mirror.db", "RID_CASE")])
    fb.R("B_OFF", "T20", "A code_samples.jsonl ts with a Z suffix was stamped by the collector in true UTC and takes no clock correction.",
         SC, [SC, CLK], mode="line", bait=True, fields=["ts"], ht=True)
    fb.R("PASS_ALL", "T17", "A code sample passes only when passed equals the problem's test count from the scoring parameters workbook; a total field in the row is the runner's count and can be short.",
         MD, ["scoring_parameters.xlsx", MD], mode="ctx", cond=True, via_rules=[g("scoring_parameters.xlsx", "I_CASE")])
    rows = sorted(W.rows[name], key=lambda x: int(x.rid[1:]))
    mv = {rid for s, rid in W.mirror_void if s == name}
    for x in rows:
        rs = base_rules(W, fb, x)
        if x.rid in mv:
            rs = [c for c in rs if c != "VOID"] + ["MIRRORVOID"]
        f = {"x": x, "job": 1, "item": 1, "host": 1, "ts": 1, "short": 0}
        if x.kind in ("canon", "copy") and r.chance(0.08):
            rs.append("PASS_ALL")
            f["short"] = 1
        fb.add(f, rs)

    def render_code(fb=fb, r=r):
        lines = []
        for row in fb.rows:
            x, rules = row["f"]["x"], row["r"]
            job = W.jobs[x.job]
            hw = hwof(W, x.job)
            if "B_OFF" in rules:
                ts = iso(x.emitted)
            elif "EPOCH" in rules:
                ts = epoch_ms_host(W, x)
            else:
                tt = x.emitted * 1000 + hw["offset_ms"]
                off = TZ_OFFSET[hw["tz"]]
                ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(tt // 1000 + off)) + f".{tt % 1000:03d}" + ("+" if off >= 0 else "-") + f"{abs(off) // 3600:02d}:{abs(off) % 3600 // 60:02d}"
            sent = "SENT_EXIT" in rules
            total = x.vals["total"]
            if row["f"]["short"]:
                total = max(1, total - r.randint(1, 3))
            obj = {"rid": x.rid, "job": v_id(x.job, rules, "J"), "problem": v_id(x.item, rules, "I"), "sample": x.sub,
                   "passed": -1 if sent else x.vals["passed"], "total": total, "exit": 137 if sent else 0,
                   "worker": v_id(job["host"], rules, "H"), "ts": ts}
            lines.append(json.dumps(obj, ensure_ascii=False))
        return ("\n".join(lines) + "\n").encode("utf-8")
    fb.render = render_code
    out.append(fb)

    # ---------------- judge_verdicts.jsonl ----------------
    name = "judge_verdicts.jsonl"
    r = rngs(name)
    fb = FB(name, tests=["item_scores_pref", "pairwise_counts", "source_audit_rows", "source_audit_used"])
    common_result_rules(W, fb, name, None, [("job", "J", "Job id", REG), ("item", "I", "Item id", "item_registry.csv")])
    fb.R("SLOT", "T17", "Judge verdicts name slot 1 or slot 2; which slot showed the candidate is recorded per job and item only in the presentation field of the rescored export.",
         MA, ["judge_verdicts_rescored.jsonl", MA], mode="ctx", cond=True, via_rules=[g("judge_verdicts_rescored.jsonl", "PRESENT")])
    fb.R("JM2", "T17", "Verdicts from judge model jm-2 are written 1, 2 or 0 (first shown, second shown, tie); jm-1 writes A, B or T.",
         MA, [MA, "job_configs.toml"], mode="line", fields=["verdict"], cond=True)
    fb.R("REVIEW", "T21", "A final reviewer verdict in the manual overrides workbook replaces the judge verdict for that job, item and slot; draft reviews do not.",
         POL, ["manual_overrides.xlsx", POL], mode="row", via_rules=[g("manual_overrides.xlsx", "DRAFT")])
    fb.R("B_TIE", "T20", "A verdict of T or 0 is a tie and is not a missing verdict.", MA, [MA, "manual_overrides.xlsx"], mode="line", bait=True, fields=["tie"], ht=True)
    fb.R("UTC_Z", "T3", "judge_verdicts.jsonl timestamps are judge-service UTC; the judge service has no host clock offset.", SC, [SC, INV], mode="line", fields=["ts"], ht=True)
    judge_now = {(x.job, x.item, x.sub): x.vals["verdict"] for x in W.rows[name] if x.kind == "canon"}
    reviewed_changed = {(j, i, s) for j, i, s, v, st, t in W.reviews if st == "final" and judge_now.get((j, i, s)) != v}
    for x in sorted(W.rows[name], key=lambda x: int(x.rid[1:])):
        rs = base_rules(W, fb, x)
        if x.kind in ("canon",) and (x.job, x.item, x.sub) in reviewed_changed:
            rs.append("REVIEW")
        if W.present.get((x.job, x.item)) == "slot1_baseline" and x.vals.get("verdict") != "T":
            rs.append("SLOT")
        f = {"x": x, "job": 1, "item": 1, "verdict": 1, "ts": 1, "tie": 1 if x.vals.get("verdict") == "T" else None}
        fb.add(f, rs)

    def render_judge(fb=fb, r=r):
        lines = []
        for row in fb.rows:
            x, rules = row["f"]["x"], row["r"]
            v = x.vals["verdict"]
            first = W.present.get((x.job, x.item), "slot1_candidate") == "slot1_candidate"
            slot = 1 if (x.sub == "AB") == first else 2
            jm = "jm-2" if "JM2" in rules else "jm-1"
            vv = {"A": "1", "B": "2", "T": "0"}[v] if jm == "jm-2" else v
            obj = {"rid": x.rid, "job": v_id(x.job, rules, "J"), "item": v_id(x.item, rules, "I"), "slot": slot,
                   "verdict": vv, "judge": jm, "ts": iso(x.emitted)}
            lines.append(json.dumps(obj, ensure_ascii=False))
        return ("\n".join(lines) + "\n").encode("utf-8")
    fb.render = render_judge
    out.append(fb)

    # ---------------- parquet shards and staging ----------------
    for name, partner, decoy in (("scores_shard1.parquet", "results_fleet_b.log", False),
                                  ("scores_shard2.parquet", "results_fleet_b.log", False),
                                  ("scores_staging.parquet", None, True)):
        r = rngs(name)
        benches = sorted({x.bench for x in W.rows[name]})
        fb = FB(name, decoy=decoy, tests=["item_scores_" + b for b in benches] + ["source_audit_rows", "source_audit_used"])
        common_result_rules(W, fb, name, partner, [("job", "J", "Job id", REG), ("item", "I", "Item id", "item_registry.csv"),
                                                    ("host", "H", "Host name", INV)], host_rules=True, decoy=decoy)
        fb.R("RG_SEC", "T3", f"In {name}, the row groups listed for it in the source conventions store emitted as epoch seconds; all other row groups store epoch milliseconds.",
             SC, [SC, CLK], mode="pos")
        fb.R("SCALE", "T2", f"In {name}, rows from hosts whose submission-week inventory scale is pct carry num as a percentage.",
             SC, [SC, INV], mode="ctx", cond=True, via_rules=[g(INV, "SUPERSEDE")])
        fb.R("ROUND", "T12", f"num in {name} is a double that can carry digits beyond the documented precision; round the shortest decimal form half-even to the documented precision.",
             MD, [MD, "scoring_parameters.xlsx"], mode="line", fields=["num"], ht=True)
        fb.R("OUTLIER", "T15", f"num values of exactly 0 or 1 in {name} are valid and kept.", MD, [MD, "gold_labels.tsv"], mode="ctx", bait=True)
        fb.R("B_NUMNA", "T20", f"num is -1.0 on rows of text suites (intent, multiling) because they have no numeric field; it is not a missing score.", SC, [SC, MD], mode="line", bait=True, fields=["numna"], ht=True)
        fb.R("B_INT", "T20", f"num values in {name} that look like integers (for example 1.0) are not percentages unless the host-week scale says so.",
             SC, [SC, INV], mode="line", bait=True, fields=["intlike"], ht=True)
        if "intent" in benches:
            fb.R("COND", "T17", f"Intent labels in {name} are raw aliases resolved under the taxonomy version of the job's harness.",
                 "label_aliases.json", ["label_aliases.json", "job_configs.toml"], mode="ctx", cond=True, via_rules=[g("job_configs.toml", "J_CASE")])
        if "multiling" in benches:
            fb.R("NFD", "T10", f"Text values in {name} can be in decomposed Unicode form; compare in NFC.", MD, [MD, "gold_labels.tsv"], mode="line", fields=["text"])
            fb.R("GRADER", "T17", "Multilingual answers are compared under the grader of the job's harness version; grader g3 also ignores combining accents.",
                 MD, ["job_configs.toml", "gold_labels.tsv"], mode="ctx", cond=True)
        if decoy:
            fb.R("STG_NEWER", "T7", "scores_staging.parquet rows are emitted later than the production copies of the same items; later emission does not make a staging row authoritative.",
                 POL, [POL, INV], mode="row", direction="pull")
            fb.R("STG_AGREE", "T16", "Staging values agree with production on most keys and differ on the rest; staging values never replace production values.",
                 POL, [POL, "scores_shard1.parquet"], mode="row", direction="pull")
            fb.R("STG_FINAL", "T16", "The staging export metadata says FINAL; the policy's source authority list still ranks it below every production source.",
                 POL, [POL, SC], mode="row", direction="pull")
            fb.R("STG_KEEP", "T22", "Rows of jobs that the errata register marks RESTORE from scores_staging.parquet are the only valid rows for those jobs.",
                 ER, [ER, POL], mode="row", direction="push", via_rules=[g(ER, "J_CASE")])
            for code, fam, desc, d, mode in [
                ("STG_TS", "T3", "Staging emitted values are epoch milliseconds of the staging host clock.", "pull", "line"),
                ("STG_SAMEKEY", "T7", "Staging copies share job, item and sample keys with production rows and are emitted later; the production row still stands.", "pull", "row"),
                ("STG_PROD_HOST", "T17", "Staging copies of production jobs name the production host; the host does not make them production rows.", "pull", "row"),
                ("STG_GAP", "T11", "Staging copies emitted after the job's seal would be late even if staging were authoritative.", "pull", "row"),
                ("STG_PREC", "T21", "For RESTORE jobs every field comes from scores_staging.parquet; the field precedence table does not apply to them.", "push", "row"),
                ("STG_OSC", "T18", "Ignoring the staging export loses the RESTORE jobs; trusting it for every job replaces production values; only RESTORE jobs use it.", "push", "row"),
                ("STG_EQ", "T19", "Staging values agree with the preliminary scorecard for most items; that agreement is not evidence.", "pull", "row"),
                ("STG_DUP", "T20", "A staging row repeated verbatim carries no second result; the repeat still counts as a record line in the source audit.", "pull", "row"),
            ]:
                fb.R(code, fam, desc, POL, [POL, "scores_shard1.parquet"], mode=mode, direction=d, fields=["job"] if mode == "line" else None, bait=code == "STG_DUP")
            fb.R("STG_HOSTS", "T17", "Whether a staging row's job ran on a staging host is decided by the host inventory week entry, not by the export it sits in.",
                 INV, [INV, "harness_events.log"], mode="row", direction="push")
        rows = sorted(W.rows[name], key=lambda x: int(x.rid[1:]))
        for x in rows:
            rs = base_rules(W, fb, x)
            num = x.vals.get("score", x.vals.get("conf"))
            f = {"x": x, "job": 1, "item": 1, "host": 1, "num": 1 if num is not None else None,
                 "text": 1 if x.bench in ("intent", "multiling", "mcq") else None,
                 "intlike": 1 if (num is not None and num == num.to_integral_value() and hwof(W, x.job)["scale"] == 1) else None,
                 "numna": 1 if num is None else None}
            if num is not None and num in (Decimal(0), Decimal(1)):
                rs.append("OUTLIER")
            if x.bench == "intent":
                cond = TAXO[W.jobs[x.job]["harness"]] == "v2" and r.chance(0.35) and bool(W.ambig.get(("v2", x.vals["label"])))
                f["lab"] = label_alias(W, x.vals["label"], TAXO[W.jobs[x.job]["harness"]], r, cond)
                if cond:
                    rs.append("COND")
            if x.bench == "multiling" and W.grader_of_harness[W.jobs[x.job]["harness"]] == "g3" and strip_marks(x.vals["answer"]) == x.vals["answer"] != W.items[x.item]["gold"]:
                rs.append("GRADER")
            if decoy:
                if x.job in W.rescue:
                    rs += ["STG_KEEP", r.choice(["STG_PREC", "STG_OSC"])]
                elif x.kind == "stgcopy":
                    rs.append(r.choice(["STG_NEWER", "STG_AGREE", "STG_FINAL"] if x.emitted < T(2025, 8, 15) else ["STG_SAMEKEY", "STG_PROD_HOST", "STG_EQ"]))
                    if x.emitted > W.seal[x.job]:
                        rs.append("STG_GAP")
                else:
                    rs.append(r.choice(["STG_NEWER", "STG_AGREE", "STG_FINAL"]))
                    if W.hw[(W.jobs[x.job]["host"], iso_week(W.jobs[x.job]["submitted"]))]["fleet"] == "s" and r.chance(0.3):
                        rs.append("STG_HOSTS")
            fb.add(f, rs)

        if decoy:
            for i in range(len(fb.rows) // 70):
                j = r.below(len(fb.rows))
                fb.rows.insert(j + 1, {"f": dict(fb.rows[j]["f"]), "r": [c for c in fb.rows[j]["r"] if fb.rules[c]["mode"] != "line"] + ["STG_DUP"], "k": None, "c": {}})
            for i in range(len(fb.rows) // 10):
                j = r.below(len(fb.rows))
                fb.rows.insert(j + 1, {"f": dict(fb.rows[j]["f"]), "r": [c for c in fb.rows[j]["r"] if fb.rules[c]["mode"] != "line"] + ["STG_DUP"], "k": None, "c": {}})

        def render_pq(fb=fb, name=name, r=r):
            n = len(fb.rows)
            groups = [fb.rows[i:i + 1000] for i in range(0, n, 1000)]
            sec_groups = fb.rg_sec
            rgs = []
            for gi, grp in enumerate(groups):
                out_rows = []
                for row in grp:
                    x, rules = row["f"]["x"], row["r"]
                    job = W.jobs[x.job]
                    ms = epoch_ms_host(W, x)
                    em = ms // 1000 if gi in sec_groups else ms
                    num = x.vals.get("score", x.vals.get("conf"))
                    txt = ""
                    if x.bench == "mcq":
                        txt = x.vals["option"]
                    elif x.bench == "intent":
                        txt = row["f"]["lab"]
                    elif x.bench == "multiling":
                        txt = unicodedata.normalize("NFD", x.vals["answer"]) if "NFD" in rules else x.vals["answer"]
                    numv = -1.0
                    if num is not None:
                        d = num * 100 if "SCALE" in rules else num
                        dp = (3 if x.bench == "safety" else 4) - (2 if "SCALE" in rules else 0)
                        s = v_excess(d, dp, r) if "ROUND" in rules else format(d, "f")
                        numv = float(s)
                    out_rows.append((x.rid, v_id(x.job, rules, "J"), v_id(x.item, rules, "I"), x.bench, txt, numv,
                                     em, v_id(job["host"], rules, "H")))
                rgs.append(out_rows)
            return parquet_bytes([("rid", "string"), ("job", "string"), ("item", "string"), ("bench", "string"),
                                  ("txt", "string"), ("num", "double"), ("emitted", "int64"), ("host", "string")], rgs,
                                 created_by="heron-export 2.3 FINAL" if name == "scores_staging.parquet" else "heron-export 2.3")
        fb.render = render_pq
        out.append(fb)

    # ---------------- eval_store.db and its replica ----------------
    for name, decoy in (("eval_store.db", False), ("eval_store_mirror.db", True)):
        r = rngs(name)
        benches = sorted({x.bench for x in W.rows[name]})
        fb = FB(name, decoy=decoy, tests=["item_scores_" + b for b in benches] + ["source_audit_rows", "source_audit_used"])
        common_result_rules(W, fb, name, None if decoy else "code_samples.jsonl", [("job", "J", "Job id", REG), ("item", "I", "Item id", "item_registry.csv")], decoy=decoy)
        kit_ids(fb, "rid", "RID", "Row id", "eval_store.db" if decoy else "code_samples.jsonl")
        if not decoy:
            fb.R("MIRRORVOID", "T6", "Sandbox failures that exited normally are listed in the void_requests table of the replica database; those eval_store.db rows are void even though the replica is otherwise stale.",
                 POL, ["eval_store_mirror.db", POL], mode="row")
        fb.R("POS", "T17", f"{name} stores the item as its ordinal position inside the job's shard; the shard map in the metric definitions resolves it.",
             MD, [MD, REG], mode="ctx", cond=True, via_rules=[g(MD, "I_PAD"), g(REG, "J_CASE")])
        fb.R("NAIVE_UTC", "T3", f"emitted in {name} is UTC written without a zone designator.", SC, [SC, MBOX], mode="line", fields=["ts"], ht=True)
        fb.R("B_LEDGER", "T20", f"jobs_ledger counts in {name} include rows later reversed or voided; a ledger count above the live row count is expected.",
             CT, [CT, ER], mode="line", bait=True, fields=["ts"], ht=True)
        if "longctx" in benches:
            fb.R("TRUNC", "T17", "Long-context items whose prompt token count for the model's tokenizer exceeds the model's context window score as wrong whatever the answer says.",
                 MD, ["context_lengths.csv", "checkpoint_lineage.json", "checkpoint_lineage_snapshot.json"], mode="ctx", cond=True)
        if decoy:
            fb.R("MIR_LAG", "T7", "eval_store_mirror.db is a replica snapshot taken on 2025-09-12; rows after the snapshot are missing and its values are not authoritative.",
                 POL, [POL, "eval_store.db"], mode="row", direction="pull")
            fb.R("MIR_AGREE", "T16", "Replica values agree with the primary store on most rows and differ on the rest; the primary store wins.",
                 POL, [POL, "eval_store.db"], mode="row", direction="pull")
            fb.R("MIR_ROLE", "T16", "The replica's meta table says role=replica; replica rows never replace primary rows.", POL, [POL, "eval_store.db"], mode="row", direction="pull")
            fb.R("MIR_SNAP", "T11", "Replica rows stop at the 2025-09-12 snapshot instant; absent later rows are not deletions.", POL, [POL, "eval_store.db"], mode="row", direction="pull")
            fb.R("MIR_VOIDS", "T6", "The replica's void_requests table is the only record of sandbox failures that exited normally; those voids apply to code_samples.jsonl and eval_store.db.",
                 POL, [POL, "code_samples.jsonl", "eval_store.db"], mode="row", direction="push")
            fb.R("MIR_NEWER", "T7", "The replica's created timestamp is later than the primary's; that does not make it newer data.",
                 POL, [POL, "eval_store.db"], mode="line", fields=["ts"], direction="pull")
            fb.R("MIR_SCHEMA", "T8", "The replica names the value column result_value; it is the same field as value in the primary.",
                 SC, [SC, "eval_store.db"], mode="line", fields=["ts"], direction="pull")
        rows = sorted(W.rows[name], key=lambda x: int(x.rid[1:]))
        mvs = {rid for s_, rid in W.mirror_void if s_ == name}
        for x in rows:
            rs = base_rules(W, fb, x)
            if x.rid in mvs and not decoy:
                rs = [c for c in rs if c != "VOID"] + ["MIRRORVOID"]
            usepos = x.kind not in ("rev", "misroute") and W.jobs[x.job]["harness"] == "h3.1" and x.item in W.shards[x.bench][W.jobs[x.job]["shard"]] and (hash_pick(x.job, name) < 0.6)
            if usepos:
                rs.append("POS")
            if x.bench == "longctx" and x.kind != "rev":
                fam = FAMILY[W.jobs[x.job]["model"]]
                if W.items[x.item]["tokens"][TOKENIZER[fam]] > CTX_WINDOW[fam]:
                    rs.append("TRUNC")
            f = {"x": x, "job": 1, "rid": 1, "ts": 1, "item": None if (usepos or x.kind == "rev") else 1, "pos": usepos}
            if decoy:
                rs.append(r.choice(["MIR_LAG", "MIR_AGREE", "MIR_ROLE", "MIR_SNAP"]))
            fb.add(f, rs)
        if decoy:
            for s, rid in sorted(W.mirror_void):
                fb.add({"void": (s, rid), "rid": 1, "job": None, "ts": None}, ["MIR_VOIDS"])
        # ledger anchors
        led = {}
        for x in rows:
            led[x.job] = led.get(x.job, 0) + (0 if x.kind == "rev" else 1)
        for j in sorted(led):
            fb.add({"ledger": (j, led[j]), "job": None, "rid": None, "ts": None}, [], kind="anchor")

        def render_db(fb=fb, name=name, decoy=decoy, r=r):
            vcol = "result_value" if decoy else "value"
            res, voids, ledger = [], [], []
            for row in fb.rows:
                f, rules = row["f"], row["r"]
                if "ledger" in f:
                    ledger.append(f["ledger"])
                    continue
                if "void" in f:
                    voids.append((f["void"][0], v_id(f["void"][1], rules, "RID"), "sandbox_oom"))
                    continue
                x = f["x"]
                pos = None
                item = None
                if x.kind != "rev":
                    job = W.jobs[x.job]
                    if f["pos"]:
                        pos = W.shards[x.bench][job["shard"]].index(x.item)
                    else:
                        item = v_id(x.item, rules, "I")
                if x.kind == "rev":
                    val = None
                elif x.bench == "code":
                    val = str(-1 if f.get("neg1") else x.vals["passed"])
                else:
                    val = "-1" if f.get("neg1") else x.vals["answer"]
                sample = x.sub if isinstance(x.sub, int) else 0
                res.append((v_id(x.rid, rules, "RID"), v_id(x.job, rules, "J"), item, pos, sample, val,
                            time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(x.emitted)), "REV" if x.kind == "rev" else "INS", x.target))
            stm = [(f"CREATE TABLE results (rid TEXT, job TEXT, item TEXT, pos INTEGER, sample INTEGER, {vcol} TEXT, emitted TEXT, op TEXT, target TEXT)", None),
                   (f"INSERT INTO results VALUES (?,?,?,?,?,?,?,?,?)", res),
                   ("CREATE TABLE jobs_ledger (job TEXT, rows_stored INTEGER)", None),
                   ("INSERT INTO jobs_ledger VALUES (?,?)", ledger),
                   ("CREATE TABLE meta (k TEXT, v TEXT)", None),
                   ("INSERT INTO meta VALUES (?,?)", [("created", "2025-10-02T06:00:00Z" if decoy else "2025-10-01T23:00:00Z"),
                                                      ("role", "replica" if decoy else "primary")])]
            if decoy:
                stm += [("CREATE TABLE void_requests (source TEXT, rid TEXT, reason TEXT)", None),
                        ("INSERT INTO void_requests VALUES (?,?,?)", voids)]
            return sqlite_bytes(stm)
        fb.render = render_db
        out.append(fb)
    return out

# ---------------------------------------------------------------------------------
# result-bearing sources, part 3
# ---------------------------------------------------------------------------------
def build_results3(W, rngs):
    out = []
    # ---------------- legacy_results.txt (fixed width) ----------------
    name = "legacy_results.txt"
    r = rngs(name)
    fb = FB(name, tests=["item_scores_arith", "metric_accuracy", "source_audit_rows", "source_audit_used"])
    common_result_rules(W, fb, name, "results_fleet_a.log", [("job", "J", "Job id", REG), ("item", "I", "Item id", "item_registry.csv"),
                                                             ("host", "H", "Host name", INV)])
    for tz, code in TZ_CODES:
        off = TZ_OFFSET[tz]
        fb.R(code, "T3", f"EMIT in legacy_results.txt is host local wall-clock time; for {tz} hosts (submission-week inventory) the offset is UTC{'+' if off >= 0 else '-'}{abs(off) // 3600:02d}:{abs(off) % 3600 // 60:02d}.",
             SC, [SC, INV], mode="ctx", cond=True, ht=code in ("TZ_BER", "TZ_CHI"), dominant=True)
    kit_locale(fb, "val", ht=("LOC_DE",))
    fb.R("ROUND", "T12", "Answers in legacy_results.txt can carry four decimals; round half-even to two.", MD, [MD, "scoring_parameters.xlsx"], mode="line", fields=["val"], ht=True)
    fb.R("NEG_PAREN", "T4", "Negative answers in legacy_results.txt can be written in parentheses.", SC, [SC, "gold_labels.tsv"], mode="line", fields=["neg"])
    fb.R("NOSKEW", "T20", "legacy_results.txt times were clock-corrected by the legacy uploader; applying the host clock offset again double-corrects them.",
         SC, [SC, CLK], mode="ctx", bait=True)
    fb.R("LAYOUT", "T8", "A #LAYOUT B record switches legacy_results.txt to the reordered layout in which the item is given as its ordinal inside the job's shard; #LAYOUT A switches back.",
         SC, [SC, MD], mode="pos", via_rules=[g(MD, "I_PAD")])
    fb.R("LEGACYNO", "T13", "Some legacy_results.txt rows name the job by its retired scheduler number (L-nnnnn); the retired scheduler export maps those numbers to job ids.",
         POL, [REGX, POL], mode="ctx", via_rules=[g(REGX, "LNO")])
    fb.R("SENT_NA", "T5", "In legacy_results.txt an answer of N/A is an abstention and scores as wrong.", SC, [SC, "results_fleet_a.log"], mode="ctx", cond=True)
    rows = sorted(W.rows[name], key=lambda x: int(x.rid[1:]))
    for x in rows:
        rs = base_rules(W, fb, x)
        hw = hwof(W, x.job)
        if hw["offset_ms"]:
            rs.append("NOSKEW")
        f = {"x": x, "job": 1, "item": 1, "host": 1, "val": None if x.vals["answer"] is None else 1,
             "neg": 1 if (x.vals["answer"] is not None and x.vals["answer"] < 0) else None}
        if x.job in W.legacy_jobno:
            rs.append("LEGACYNO")
            f["job"] = None
        if x.vals["answer"] is None:
            rs.append("SENT_NA")
        fb.add(f, rs)

    def render_legacy(fb=fb, r=r):
        lines = ["#LAYOUT A RID JOB ITEM ANSWER EMIT HOST"]
        cur = "A"
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            x = f["x"]
            job = W.jobs[x.job]
            lay = "B" if "LAYOUT" in rules else "A"
            if lay != cur:
                lines.append("#LAYOUT B RID HOST JOB POS EMIT ANSWER" if lay == "B" else "#LAYOUT A RID JOB ITEM ANSWER EMIT HOST")
                cur = lay
            hw = hwof(W, x.job)
            emit = local_str(x.emitted, hw["tz"], 0, "%Y%m%d%H%M%S", ms=False)
            a = x.vals["answer"]
            av = "N/A" if a is None else fmt_val_num(W, x, a, 2, rules, r)
            jid = W.legacy_jobno[x.job] if "LEGACYNO" in rules else v_id(x.job, rules, "J")
            host = v_id(job["host"], rules, "H")
            if lay == "A":
                lines.append(f"{x.rid:<9}{jid:<10}{v_id(x.item, rules, 'I'):<11}{av:>20}{emit:>15} {host}")
            else:
                sh_ = W.shards["arith"][job["shard"]]
                pos = sh_.index(x.item) if x.item in sh_ else 90 + int(x.item[-2:]) % 10
                lines.append(f"{x.rid:<9}{host:<11}{jid:<10}{pos:>3}{emit:>15}{av:>20}")
        return ("\n".join(lines) + "\n").encode("utf-8")
    fb.render = render_legacy
    out.append(fb)

    # ---------------- intent_predictions.csv ----------------
    name = "intent_predictions.csv"
    r = rngs(name)
    fb = FB(name, tests=["item_scores_intent", "metric_intent", "source_audit_rows", "source_audit_used"])
    common_result_rules(W, fb, name, "scores_shard2.parquet", [("job", "J", "Job id", REG), ("item", "I", "Item id", "item_registry.csv")])
    fb.R("DST", "T3", "intent_predictions.csv labels Europe/Berlin rows with utc_offset +0100 all year; during the window the true offset is +0200. Other offsets are correct.",
         SC, [SC, INV], mode="ctx", cond=True)
    fb.R("SKEW", "T3", "local times in intent_predictions.csv carry the host clock error of the submission week.", SC, [SC, CLK], mode="ctx")
    fb.R("HDR", "T8", "A second header row inside intent_predictions.csv renames label to predicted_label and local_time to emitted_local and moves utc_offset to the last column; rows after it follow the new header.",
         SC, [SC, "label_aliases.json"], mode="pos")
    fb.R("EMBED", "T9", "Labels in intent_predictions.csv that contain commas or quotes are CSV-quoted.", SC, [SC, "label_aliases.json"], mode="ctx")
    fb.R("COND", "T17", "Raw labels resolve under the taxonomy version of the job's harness.", "label_aliases.json", ["label_aliases.json", "job_configs.toml"], mode="ctx", cond=True)
    fb.R("BOM", "T10", "intent_predictions.csv starts with a UTF-8 byte order mark.", SC, [SC, "label_aliases.json"], mode="row", ht=True)
    fb.R("B_QUOTE", "T20", "Labels are matched exactly as written, including spaces and punctuation; a label that looks like two words is still one alias.", SC, [SC, "label_aliases.json"], mode="line", bait=True, fields=["q"], ht=True)
    rows = sorted(W.rows[name], key=lambda x: int(x.rid[1:]))
    for i, x in enumerate(rows):
        rs = base_rules(W, fb, x)
        hw = hwof(W, x.job)
        if hw["tz"] == "Europe/Berlin":
            rs.append("DST")
        cond = TAXO[W.jobs[x.job]["harness"]] == "v2" and r.chance(0.35) and bool(W.ambig.get(("v2", x.vals["label"])))
        lab = label_alias(W, x.vals["label"], TAXO[W.jobs[x.job]["harness"]], r, cond)
        if cond:
            rs.append("COND")
        if "," in lab or '"' in lab:
            rs.append("EMBED")
        if i == 0:
            rs.append("BOM")
        fb.add({"x": x, "job": 1, "item": 1, "lab": lab, "q": 1 if " " in lab else None}, rs)

    def render_intent(fb=fb, r=r):
        buf = io.StringIO()
        import csv as _csv
        w = _csv.writer(buf, lineterminator="\n")
        w.writerow(["rid", "job", "item", "label", "local_time", "utc_offset"])
        switched = False
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            x = f["x"]
            hw = hwof(W, x.job)
            lt = local_str(x.emitted, hw["tz"], hw["offset_ms"], "%Y-%m-%d %H:%M:%S", ms=False)
            off = TZ_OFFSET[hw["tz"]]
            if hw["tz"] == "Europe/Berlin":
                off = 3600
            offs = ("+" if off >= 0 else "-") + f"{abs(off) // 3600:02d}{abs(off) % 3600 // 60:02d}"
            lab = f["lab"]
            if "HDR" in rules and not switched:
                w.writerow(["rid", "job", "item", "predicted_label", "emitted_local", "utc_offset"][:3] + ["predicted_label", "emitted_local", "utc_offset"])
                switched = True
            if "HDR" not in rules and switched:
                w.writerow(["rid", "job", "item", "label", "local_time", "utc_offset"])
                switched = False
            w.writerow([x.rid, v_id(x.job, rules, "J"), v_id(x.item, rules, "I"), lab, lt, offs])
        return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")
    fb.render = render_intent
    out.append(fb)

    # ---------------- rerun_results.jsonl ----------------
    name = "rerun_results.jsonl"
    r = rngs(name)
    fb = FB(name, tests=["job_dispositions", "item_scores_arith", "item_scores_mcq", "source_audit_rows", "source_audit_used"])
    common_result_rules(W, fb, name, None, [("job", "J", "Job id", REG), ("item", "I", "Item id", "item_registry.csv")])
    fb.R("APPROVAL", "T22", "A rerun's rows replace the original job only when the review minutes record the rerun as approved; a rerun recorded as denied leaves the original in force.",
         RM, [RM, "harness_events.log"], mode="row", via_rules=[g(RM, "J_CASE"), g("harness_events.log", "LNO")])
    fb.R("NO_REVIEW", "T20", "Reviewer verdicts in manual_overrides.xlsx apply only to judge_verdicts.jsonl rows; rerun verdicts are never overridden.", POL, ["manual_overrides.xlsx", POL, "judge_verdicts_rescored.jsonl"], mode="row", bait=True)
    fb.R("UNRECORDED", "T22", "A rerun with no decision in the review minutes is not approved; its rows have no effect.", RM, [RM, "harness_events.log"], mode="row")
    fb.R("COMPOSITE", "T9", "Multiple-choice rerun values are written option|confidence in one string.", SC, [SC, "scores_shard1.parquet"], mode="ctx")
    fb.R("COND", "T17", "Raw intent labels resolve under the taxonomy version of the rerun's harness.", "label_aliases.json", ["label_aliases.json", "job_configs.toml"], mode="ctx", cond=True)
    fb.R("SLOT", "T17", "Preference rerun verdicts name slot 1 or 2; the presentation order comes from the rescored export.", MA, ["judge_verdicts_rescored.jsonl", MA], mode="ctx", cond=True)
    fb.R("TRUNC", "T17", "Long-context rerun items over the model's context window score as wrong.", MD, ["context_lengths.csv", "checkpoint_lineage.json", "checkpoint_lineage_snapshot.json"], mode="ctx", cond=True)
    fb.R("GRADER", "T17", "Multilingual rerun answers are compared under the grader of the rerun's harness.", MD, ["job_configs.toml", "gold_labels.tsv"], mode="ctx", cond=True)
    fb.R("B_STR", "T20", "Arithmetic rerun answers are strings in plain en_US form with no grouping; a leading minus is a negative answer.",
         SC, [SC, "gold_labels.tsv"], mode="line", bait=True, fields=["arith"], ht=True)
    fb.R("UTC_Z", "T3", "rerun_results.jsonl timestamps are UTC.", SC, [SC, INV], mode="line", fields=["ts"], ht=True)
    rows = sorted(W.rows[name], key=lambda x: int(x.rid[1:]))
    for x in rows:
        rs = base_rules(W, fb, x)
        job = W.jobs[x.job]
        if job["kind"] == "rerun_denied":
            rs = [c for c in rs if c != "JOB_DENIED"] + ["APPROVAL" if W.rerun_decision[x.job] == "denied" else "UNRECORDED"]
        f = {"x": x, "job": 1, "item": 1, "ts": 1, "arith": 1 if x.bench == "arith" else None}
        if x.bench == "mcq":
            rs.append("COMPOSITE")
        if x.bench == "intent":
            cond = TAXO[job["harness"]] == "v2" and r.chance(0.35) and bool(W.ambig.get(("v2", x.vals["label"])))
            f["lab"] = label_alias(W, x.vals["label"], TAXO[job["harness"]], r, cond)
            if cond:
                rs.append("COND")
        if x.bench == "pref" and W.present.get((x.job, x.item)) == "slot1_baseline" and x.vals["verdict"] != "T":
            rs.append("SLOT")
        if x.bench == "pref" and x.kind == "canon" and hash_pick(x.rid, "nr") < 0.2:
            rs.append("NO_REVIEW")
        if x.bench == "longctx":
            fam = FAMILY[job["model"]]
            if W.items[x.item]["tokens"][TOKENIZER[fam]] > CTX_WINDOW[fam]:
                rs.append("TRUNC")
        if x.bench == "multiling" and W.grader_of_harness[job["harness"]] == "g3" and strip_marks(x.vals["answer"]) == x.vals["answer"] != W.items[x.item]["gold"]:
            rs.append("GRADER")
        fb.add(f, rs)

    def render_rerun(fb=fb):
        lines = []
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            x = f["x"]
            b, v = x.bench, x.vals
            if b == "arith":
                val = "N/A" if v["answer"] is None else format(v["answer"], "f")
            elif b == "code":
                val = v["passed"]
            elif b == "intent":
                val = f["lab"]
            elif b == "safety":
                val = float(v["score"])
            elif b == "mcq":
                val = f"{v['option']}|{v['conf']}"
            elif b == "pref":
                first = W.present.get((x.job, x.item), "slot1_candidate") == "slot1_candidate"
                val = {"slot": 1 if (x.sub == "AB") == first else 2, "verdict": v["verdict"]}
            else:
                val = v["answer"]
            obj = {"rid": x.rid, "job": v_id(x.job, rules, "J"), "item": v_id(x.item, rules, "I"), "bench": b,
                   "sample": x.sub if isinstance(x.sub, int) else 0, "value": val, "ts": iso(x.emitted)}
            lines.append(json.dumps(obj, ensure_ascii=False))
        return ("\n".join(lines) + "\n").encode("utf-8")
    fb.render = render_rerun
    out.append(fb)

    # ---------------- judge_verdicts_rescored.jsonl (decoy) ----------------
    name = "judge_verdicts_rescored.jsonl"
    r = rngs(name)
    fb = FB(name, decoy=True, tests=["item_scores_pref", "pairwise_counts"])
    common_result_rules(W, fb, name, None, [("job", "J", "Job id", REG), ("item", "I", "Item id", "item_registry.csv")])
    fb.R("RS_NEWER", "T7", "The rescored export is newer than judge_verdicts.jsonl; its verdicts come from judge jm-3, which the policy never approved, so they are not used.",
         POL, [POL, "judge_verdicts.jsonl"], mode="row", direction="pull")
    fb.R("RS_AGREE", "T16", "Rescored verdicts agree with the approved judge on most items and differ on the rest; the approved judge or a final review wins.",
         POL, [POL, "manual_overrides.xlsx"], mode="row", direction="pull")
    fb.R("RS_COMPLETE", "T16", "The rescored export covers every preference item including reviewed ones; completeness does not make it authoritative.",
         POL, [POL, "judge_verdicts.jsonl"], mode="row", direction="pull")
    fb.R("PRESENT", "T17", "The presentation field (slot1_candidate or slot1_baseline) is the only record of which slot showed the candidate, and it is valid for judge_verdicts.jsonl, rerun_results.jsonl and manual_overrides.xlsx; slot1_baseline reverses the slot reading.",
         MA, [MA, "judge_verdicts.jsonl", "rerun_results.jsonl", "manual_overrides.xlsx"], mode="row", direction="push")
    fb.R("RS_TS", "T3", "Rescored timestamps are epoch seconds.", SC, [SC, "judge_verdicts.jsonl"], mode="line", fields=["ts"], direction="pull", ht=True)
    fb.R("RS_TIE", "T5", "jm-3 writes ties as null; a null verdict is a tie, not a missing row.", MA, [MA, "judge_verdicts.jsonl"], mode="line", fields=["tie"], direction="pull")
    fb.R("RS_LABEL", "T16", "Each rescored row carries status final; that label is the rescoring pipeline's own and not a review status.",
         POL, [POL, "manual_overrides.xlsx"], mode="line", fields=["ts"], direction="pull")
    fb.R("RS_STATUS", "T16", "Every rescored row says status final; that is the rescoring pipeline's own status, not a review.", POL, [POL, "manual_overrides.xlsx"], mode="row", direction="pull")
    fb.R("RS_JUDGE", "T16", "judge jm-3 is a newer judge model than jm-1 and jm-2; it was not approved for certification.", POL, [POL, MA], mode="row", direction="pull")
    fb.R("RS_DUP", "T20", "A rescored row repeated verbatim carries no second result; the repeat still counts as a record line in the source audit.", POL, [POL, "judge_verdicts.jsonl"], mode="row", bait=True, direction="pull")
    fb.R("RS_SLOTSTR", "T4", "slot can be a string.", MA, [MA, "judge_verdicts.jsonl"], mode="line", fields=["ts"], direction="pull")
    fb.R("RS_JUDGECASE", "T1", "judge can be upper-cased (JM-3).", MA, [MA, "judge_verdicts.jsonl"], mode="line", fields=["ts"], direction="pull")
    fb.R("RS_HELD", "T14", "Rescored rows exist for held-out items too; scope is decided by the policy appendix.", POL, [POL, "certification_policy.md"], mode="row", direction="pull")
    fb.R("RS_PART", "T13", "Some rescored rows name jobs that are not preference jobs of the run registry; those rows are ignored.", POL, [REG, POL], mode="row", direction="pull")
    fb.R("RS_SLOTBAIT", "T20", "A presentation value of slot1_candidate for an item whose judge verdict is a tie is still the order of record.", MA, [MA, "judge_verdicts.jsonl"], mode="line", bait=True, fields=["tie"], direction="push", ht=True)
    rows = sorted(W.rows[name], key=lambda x: int(x.rid[1:]))
    for x in rows:
        rs = [c for c in base_rules(W, fb, x) if c in fb.rules]
        rs.append(r.choice(["RS_NEWER", "RS_AGREE", "RS_COMPLETE", "RS_STATUS", "RS_JUDGE"]))
        if W.present.get((x.job, x.item)) == "slot1_baseline":
            rs.append("PRESENT")
        if x.item in W.held_out:
            rs.append("RS_HELD")
        fb.add({"x": x, "job": 1, "item": 1, "ts": 1, "tie": 1 if x.vals["verdict"] == "T" else None}, rs)
    for i in range(max(30, len(rows) // 60)):
        x = rows[r.below(len(rows))]
        fake = RRow(name, x.job, x.item, x.sub, "pref", dict(x.vals), x.emitted, "part")
        fake.rid = "p" + x.rid[1:]
        fb.add({"x": fake, "job": 1, "item": 1, "ts": 1, "part": 1}, ["RS_PART"])

    for i in range(len(fb.rows) // 80):
        jx = r.below(len(fb.rows))
        fb.rows.insert(jx + 1, {"f": dict(fb.rows[jx]["f"]), "r": [c for c in fb.rows[jx]["r"] if fb.rules[c]["mode"] != "line"] + ["RS_DUP"], "k": None, "c": {}})

    def render_rs(fb=fb):
        lines = []
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            x = f["x"]
            first = W.present.get((x.job, x.item), "slot1_candidate") == "slot1_candidate"
            slot = 1 if (x.sub == "AB") == first else 2
            v = x.vals["verdict"]
            jid = x.job if not f.get("part") else fake_job(x.job, 1)
            obj = {"rid": x.rid, "job": v_id(jid, rules, "J"), "item": v_id(x.item, rules, "I"), "slot": str(slot) if "RS_SLOTSTR" in rules else slot,
                   "verdict": None if (v == "T" and "RS_TIE" in rules) else v, "judge": "JM-3" if "RS_JUDGECASE" in rules else "jm-3", "status": "final",
                   "presentation": W.present.get((x.job, x.item), "slot1_candidate"), "ts": x.emitted if "RS_TS" in rules else iso(x.emitted)}
            lines.append(json.dumps(obj, ensure_ascii=False))
        return ("\n".join(lines) + "\n").encode("utf-8")
    fb.render = render_rs
    out.append(fb)

    # ---------------- baseline_reference.csv ----------------
    name = "baseline_reference.csv"
    r = rngs(name)
    fb = FB(name, tests=["metric_accuracy", "significance_counts", "leaderboard_aggregate", "release_gates"])
    kit_ids(fb, "item", "I", "Item id", "item_registry.csv", ht=("CASE", "PAD"))
    kit_ids(fb, "ref", "REF", "Legacy item code", MA, ht=("NONE",))
    fb.R("XWALK", "T13", "Some baseline_reference.csv rows name the item by its legacy item code (LCnnnnnn) instead of the item id; the crosswalk in the methodology appendix maps codes to item ids.", MA, [MA, "item_registry.csv"], mode="ctx", via_rules=[g(MA, "REF_CASE")])
    fb.R("REVISED", "T7", "When baseline_reference.csv holds several rows for one item, the row with the latest revised date wins.", SC, [SC, ER], mode="row")
    fb.R("VOID", "T6", "Baseline rows listed in the errata register void list (by legacy code and revision date) are void.", ER, [ER, POL], mode="row", via_rules=[g(ER, "RID_SRC")])
    fb.R("WITHDRAWN", "T14", "Baseline rows with status withdrawn are out of scope.", POL, [POL, SC], mode="row")
    fb.R("SERIAL", "T3", "Some revised values in baseline_reference.csv are spreadsheet serial dates (days since 1899-12-30).", SC, [SC, MA], mode="line", fields=["date"])
    fb.R("ROUND", "T12", "Baseline confidences and scores can carry extra digits; round half-even to the documented precision.", MD, [MD, "scoring_parameters.xlsx"], mode="line", fields=["num"], ht=True)
    fb.R("LOC_DE", "T4", "Baseline rows revised before 2025-08-01 were exported from a de_DE workstation and use a comma decimal mark.", SC, [SC, MA], mode="ctx", cond=True)
    fb.R("HDR", "T8", "A second header row in baseline_reference.csv swaps the value and confidence columns for the rows after it.", SC, [SC, MD], mode="pos")
    fb.R("BOM", "T10", "baseline_reference.csv starts with a byte order mark.", SC, [SC, MA], mode="row", ht=True)
    fb.R("EMBED", "T9", "Baseline text answers containing commas are CSV-quoted.", SC, [SC, "gold_labels.tsv"], mode="ctx")
    fb.R("TRUNC", "T17", "The baseline's long-context items over its own context window (tokenizer ospsp) score as wrong.", MD, ["context_lengths.csv", "checkpoint_lineage.json"], mode="ctx", cond=True)
    fb.R("GRADER", "T17", "Baseline multilingual answers are graded under grader g3.", MD, [MD, "gold_labels.tsv"], mode="ctx", cond=True)
    fb.R("CODEC", "T2", "Baseline code rows give the number of passing samples out of ten in value.", MD, [MD, "item_registry.csv"], mode="ctx")
    fb.R("OUTLIER", "T15", "Baseline scores of exactly 0 or 1 are valid.", MD, [MD, "gold_labels.tsv"], mode="ctx", bait=True)
    fb.R("B_NEG", "T20", "A baseline arithmetic value starting with a minus sign is a negative answer, not a sentinel.", MD, [MD, "gold_labels.tsv"], mode="line", bait=True, fields=["neg"], ht=True)
    fb.R("SENT_NA", "T5", "A baseline arithmetic value of N/A is an abstention.", SC, [SC, MD], mode="ctx")
    fb.R("DUPROW", "T20", "A baseline row repeated verbatim is one row.", POL, [POL, ER], mode="row", bait=True)
    inelig_rules(fb, "Baseline rows", "take no part in metrics or significance", doc=MA)
    W.legacy_code = {}
    used = set()
    for iid in sorted(W.items):
        while True:
            c = f"LC{r.randint(100000, 999999)}"
            if c not in used:
                used.add(c)
                W.legacy_code[iid] = c
                break
    W.base_void = []
    items = [i for i in sorted(W.base_res)]
    rev0 = T(2025, 7, 10)
    for iid in items:
        it = W.items[iid]
        vals = W.base_res[iid]
        rev = rev0 + r.randint(0, 80) * 86400
        noise = r.rand()
        def kind_ok(status):
            return status == "active"

        def mk(v, revised, status, rules, kind=None):
            num = v.get("score", v.get("conf"))
            leg = r.chance(0.14)
            f = {"iid": iid, "v": v, "revised": revised, "status": status, "ref": 1 if leg else None, "item": None if leg else 1, "legacy": leg,
                 "date": 1, "num": 1 if num is not None else None,
                 "neg": 1 if (it["bench"] == "arith" and v.get("answer") is not None and v["answer"] < 0) else None}
            rs = list(rules)
            if f["legacy"]:
                rs.append("XWALK")
            if revised < T(2025, 8, 1) and (num is not None or (it["bench"] == "arith" and v.get("answer") is not None)):
                rs.append("LOC_DE")
            if it["bench"] == "longctx" and it["tokens"]["ospsp"] > CTX_WINDOW["osp13"]:
                rs.append("TRUNC")
            if it["bench"] == "multiling" and strip_marks(v["answer"]) == v["answer"] != it["gold"]:
                rs.append("GRADER")
            if it["bench"] == "code":
                rs.append("CODEC")
            if num is not None and num in (Decimal(0), Decimal(1)):
                rs.append("OUTLIER")
            if it["bench"] == "arith" and v.get("answer") is None:
                rs.append("SENT_NA")
            if it["bench"] in ("longctx", "multiling") and "," in v.get("answer", ""):
                rs.append("EMBED")
            if W.elig.get(iid) is not None and kind_ok(status):
                rs.append(INELIG_CODE[W.elig[iid]])
            return fb.add(f, rs)
        def alt(v):
            v = dict(v)
            k = next(iter(v))
            if it["bench"] == "code":
                v["c"] = (v["c"] + 1) % 11
            else:
                v[k] = perturb(W, r, it["bench"], {"answer": "answer", "label": "label", "score": "score", "option": "option", "c": "passed"}[k], v[k], iid)
            return v
        if noise < 0.12:
            mk(alt(vals), rev - r.randint(1, 20) * 86400, "active", ["REVISED"])
        elif noise < 0.16:
            row = mk(alt(vals), rev + r.randint(1, 9) * 86400, "active", ["VOID"])
            W.base_void.append((iid, row["f"]["revised"]))
        elif noise < 0.19:
            mk(alt(vals), rev + r.randint(1, 9) * 86400, "withdrawn", ["WITHDRAWN"])
        mk(vals, rev, "active", [])

    for i in range(len(fb.rows) // 9):
        jx = r.below(len(fb.rows))
        fb.rows.insert(jx + 1, {"f": dict(fb.rows[jx]["f"]), "r": [c for c in fb.rows[jx]["r"] if fb.rules[c]["mode"] != "line"] + ["DUPROW"], "k": None, "c": {}})

    def render_base(fb=fb, r=r):
        import csv as _csv
        buf = io.StringIO()
        w = _csv.writer(buf, lineterminator="\n")
        hdrA = ["ref", "suite", "value", "confidence", "revised", "status"]
        hdrB = ["ref", "suite", "confidence", "value", "revised", "status"]
        w.writerow(hdrA)
        cur = "A"
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            it = W.items[f["iid"]]
            v = f["v"]
            b = it["bench"]
            lay = "B" if "HDR" in rules else "A"
            if lay != cur:
                w.writerow(hdrB if lay == "B" else hdrA)
                cur = lay
            loc = "de_DE" if "LOC_DE" in rules else "en_US"
            conf = ""
            if b == "arith":
                val = "N/A" if v["answer"] is None else v_num(v["answer"], 2, loc, group=False)
            elif b == "code":
                val = str(v["c"])
            elif b == "intent":
                val = v["label"]
            elif b == "safety":
                d = v["score"]
                val = v_num(Decimal(v_excess(d, 3, r)), 5, loc, group=False) if "ROUND" in rules else v_num(d, 3, loc, group=False)
            elif b == "mcq":
                val = v["option"]
                d = v["conf"]
                conf = v_num(Decimal(v_excess(d, 4, r)), 6, loc, group=False) if "ROUND" in rules else v_num(d, 4, loc, group=False)
            else:
                val = v["answer"]
            rv = f["revised"]
            rvs = repr(excel_serial(rv)) if "SERIAL" in rules else time.strftime("%Y-%m-%d", time.gmtime(rv))
            ref = v_id(W.legacy_code[f["iid"]], rules, "REF") if f["legacy"] else v_id(f["iid"], rules, "I")
            cells = [ref, b, val, conf, rvs, f["status"]] if lay == "A" else [ref, b, conf, val, rvs, f["status"]]
            w.writerow(cells)
        return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")
    fb.render = render_base
    out.append(fb)
    return out

# ---------------------------------------------------------------------------------
# registries
# ---------------------------------------------------------------------------------
V2NAME = {"reset_password": "account_recovery", "shipping_cost": "delivery_fee", "hours": "opening_hours"}
SYN = {"billing": ["billing", "invoice", "charge", "bill", "payment issue", "factura", "rechnung"],
       "cancel": ["cancel", "terminate", "stop service", "end plan", "annuler", "kuendigen"],
       "complaint": ["complaint", "bad service", "unhappy", "grievance", "beschwerde", "reclamo"],
       "delivery": ["delivery", "where is parcel", "courier", "dispatch", "livraison", "lieferung"],
       "greeting": ["greeting", "hello", "hi there", "good morning", "hola", "bonjour"],
       "hours": ["hours", "open when", "closing time", "schedule", "horario", "oeffnungszeit"],
       "login": ["login", "sign in", "cannot log", "auth error", "anmelden", "connexion"],
       "order_status": ["order status", "track order", "order update", "my order", "pedido", "commande"],
       "refund": ["refund", "reimburse", "return money", "chargeback", "reembolso", "erstattung"],
       "reset_password": ["reset password", "forgot password", "new password", "pwd reset", "contrasena"],
       "shipping_cost": ["shipping cost", "delivery fee", "postage", "freight", "versandkosten", "frais de port"],
       "upgrade": ["upgrade", "premium", "better plan", "add features", "mejora", "aufwerten"]}
AMBIG = [("account access", "login", "reset_password"), ("order help", "order_status", "delivery"),
         ("plan change", "upgrade", "billing"), ("money back", "refund", "complaint"),
         ("store time", "hours", "greeting"), ("payment stop", "cancel", "billing")]


def v2(c):
    return V2NAME.get(c, c)


def build_aliases(W, seed):
    r = derive(seed, "aliases")
    pre = ["", "intent:", "cls/", "lbl-", "tag.", "label=", "#"]
    suf = ["", "_v", "-q", "(en)", "!", "?", "_2"]
    cases = [str.lower, str.upper, str.title]
    W.aliases = {}  # raw -> (v1 class, v2 class)
    for cls in INTENT_CLASSES:
        for w in SYN[cls]:
            for p in pre:
                for s_ in suf:
                    for cf in cases:
                        raw = cf(p + w + s_)
                        if raw not in W.aliases and r.chance(0.9):
                            W.aliases[raw] = (cls, cls)
    for w, c1, c2 in AMBIG:
        for p in pre:
            for s_ in suf:
                for cf in cases:
                    W.aliases[cf(p + w + s_)] = (c1, c2)
    W.alias_of = {}
    W.ambig = {}
    for raw in sorted(W.aliases):
        c1, c2 = W.aliases[raw]
        W.alias_of.setdefault(("v1", c1), []).append(raw)
        W.alias_of.setdefault(("v2", c2), []).append(raw)
        if c1 != c2:
            W.ambig.setdefault(("v2", c2), []).append(raw)
            W.ambig.setdefault(("v1", c1), []).append(raw)


def reg_kit(fb, keyfield, tag, label, master, doc_rev=SC, older=True, void=True, fk=True, extra_fk=None):
    kit_ids(fb, keyfield, tag, label, master, ht=("CASE",))
    if older:
        fb.R("REV", "T7", f"When {fb.name} holds several entries for one {label.lower()}, the entry with the highest revision wins.",
             doc_rev, [doc_rev, ER], mode="row")
    if void:
        fb.R("VOID", "T6", f"Entries of {fb.name} listed in the errata register registry void list (file, key, revision) are void.",
             ER, [ER, POL], mode="row", via_rules=[g(ER, "RID_SRC")])
    if fk:
        fb.R("FK", "T13", f"Entries of {fb.name} whose {label.lower()} is not registered in {master} are ignored.",
             POL, [master, POL], mode="row", via_rules=[g(master, tag + "_CASE")] if master != fb.name else [])


def reg_rows(W, r, fb, keys, canon, alt, fake_key, p_old=0.10, p_void=0.03, p_fk=0.015, base_rev=None):
    """Canonical entries plus superseded, void and unregistered noise. Returns rows added."""
    W.errata_reg = getattr(W, "errata_reg", [])
    for k in keys:
        rev = base_rev(k) if base_rev else r.randint(2, 6)
        roll = r.rand()
        if roll < p_old and "REV" in fb.rules:
            fb.add({"key": k, "v": alt(k), "rev": rev - r.randint(1, rev - 1), "kind": "older"}, ["REV"])
        elif roll < p_old + p_void and "VOID" in fb.rules:
            fb.add({"key": k, "v": alt(k), "rev": rev + 1, "kind": "void"}, ["VOID"])
            W.errata_reg.append((fb.name, k, rev + 1))
        fb.add({"key": k, "v": canon(k), "rev": rev, "kind": "canon"}, [])
        if r.chance(p_fk) and "FK" in fb.rules:
            fk = fake_key(k)
            fb.add({"key": fk, "v": alt(k), "rev": rev, "kind": "fk"}, ["FK"])


def tab_flags(fb):
    for row in fb.rows:
        row["f"].setdefault("revf", 1 if "rev" in row["f"] else None)
        row["f"].setdefault("twf", 1)
        row["f"].setdefault("lbf", 1)


def ids_on(fb):
    """Fill id-presence fields for the row dicts produced by reg_rows."""
    for row in fb.rows:
        row["f"].setdefault("id", 1)


def fake_item(r, k):
    """An item id of the same suite that is not registered."""
    pfx, num = k.split("-")
    n = (int(num) + 20000 + r.randint(0, 59999)) % 99999
    while f"{pfx}-{n:05d}" in FB._W.items:
        n = (n + 7) % 99999
    return f"{pfx}-{n:05d}"


def fake_job(k, step):
    n = (int(k[1:]) + step) % 10000000
    while f"J{n:07d}" in FB._W.jobs:
        n = (n + 1) % 10000000
    return f"J{n:07d}"


def text_cell(s, rules):
    if "NFD" in rules:
        s = unicodedata.normalize("NFD", s)
    return s


def csv_bytes(header_rows, bom=False, delim=","):
    import csv as _csv
    buf = io.StringIO()
    w = _csv.writer(buf, delimiter=delim, lineterminator="\n")
    for row in header_rows:
        w.writerow(row)
    data = buf.getvalue().encode("utf-8")
    return (b"\xef\xbb\xbf" + data) if bom else data


def build_registries_items(W, rngs):
    out = []
    P = W.params
    items = sorted(W.items)
    # ---------------- item_registry.csv ----------------
    name = "item_registry.csv"
    r = rngs(name)
    fb = FB(name, tests=["item_eligibility", "item_scores_intent", "metric_intent"])
    reg_kit(fb, "id", "I", "Item id", name, fk=False)
    fb.R("FK", "T13", "An item id is registered only when it is listed both in item_registry.csv and in the shard map of the metric definitions; other item_registry.csv rows are not items.",
         POL, [MD, POL], mode="row")
    fb.R("SUITE_ALIAS", "T17", "Entries with revision below 3 name the suite by its legacy name (arithmetic, codegen, intents, safety_flags, multiple_choice, pairwise, long_context, multilingual).",
         POL, [POL, "suite_manifest.xlsx"], mode="ctx", cond=True)
    fb.R("TAXO", "T17", "For intent items the taxonomy column says whether the item's gold label is written in taxonomy v1 or v2 class names.",
         "label_aliases.json", ["label_aliases.json", "gold_labels.tsv"], mode="ctx", cond=True)
    fb.R("HDR", "T8", "A second header row inside item_registry.csv swaps the subtask and suite columns for the rows after it.", SC, [SC, "suite_manifest.xlsx"], mode="pos")
    fb.R("BOM", "T10", "item_registry.csv starts with a byte order mark.", SC, [SC, POL], mode="row", ht=True)
    fb.R("ADDED_SERIAL", "T3", "Some added values in item_registry.csv are spreadsheet serial dates (days since 1899-12-30).", SC, [SC, "suite_manifest.xlsx"], mode="line", fields=["date"])
    fb.R("SENT_TAXO", "T5", "A taxonomy value of - means not applicable (non-intent suite); an empty taxonomy on an intent item means v1.", "label_aliases.json", ["label_aliases.json", POL], mode="ctx")
    fb.R("B_QUOTE", "T20", "A quoted subtask containing a comma is one value.", SC, [SC, POL], mode="line", bait=True, fields=["q"], ht=True)
    fb.R("DUPROW", "T20", "An entry repeated verbatim (same item, revision and values) is one entry, not a conflict.", POL, [POL, ER], mode="row", bait=True)
    fb.R("REV0", "T5", "Revision 0 entries are unpublished drafts and are ignored.", POL, [POL, "suite_manifest.xlsx"], mode="row")
    fb.R("SANDBOX", "T14", "Entries whose suite is sandbox are harness self-tests and are not items.", POL, [POL, "suite_manifest.xlsx"], mode="row")
    fb.R("EMBED", "T9", "Subtasks containing commas are CSV-quoted.", SC, [SC, POL], mode="ctx")
    fb.R("SUBTASK_NOT_DOMAIN", "T20", "A subtask that looks like a slice domain (law, finance) is still only a subtask; slice domains come from slice_attributes.csv.", MD, ["slice_attributes.csv", "slice_definitions.yaml"], mode="ctx", bait=True)
    fb.R("WS_SUITE", "T1", "Suite names can carry trailing spaces.", POL, [POL, "suite_manifest.xlsx"], mode="line", fields=["suite"])
    kit_tab(fb, tw=False)
    legacy_suite = {"arith": "arithmetic", "code": "codegen", "intent": "intents", "safety": "safety_flags", "mcq": "multiple_choice",
                    "pref": "pairwise", "longctx": "long_context", "multiling": "multilingual"}
    W.item_taxo = {}
    for iid in items:
        if W.items[iid]["bench"] == "intent":
            W.item_taxo[iid] = r.choice(["v1", "v2", "v2", ""])
    reg_rows(W, r, fb, items, lambda k: {"sub": W.items[k]["subtask"]}, lambda k: {"sub": r.choice(SYL) + "_x"}, lambda k: fake_item(r, k))
    for row in fb.rows:
        k = row["f"]["key"]
        row["f"].update({"id": 1, "date": 1, "suite": 1, "q": 1})
        if row["f"]["rev"] < 3 and row["f"]["kind"] == "canon":
            row["r"].append("SUITE_ALIAS")
        if row["f"]["kind"] == "canon" and row["f"]["v"]["sub"] in ("law", "history") and W.items.get(k):
            row["r"].append("SUBTASK_NOT_DOMAIN")
        if W.items.get(k, {}).get("bench") == "intent" or k.startswith("INT"):
            row["r"].append("TAXO")
            if W.item_taxo.get(k, "v1") == "":
                row["r"].append("SENT_TAXO")
    extra = []
    for i in range(len(items) // 80):
        k = r.choice(items)
        extra.append((r.below(len(fb.rows)), {"key": k, "v": {"sub": "draft"}, "rev": 0, "kind": "rev0"}, ["REV0"]))
        extra.append((r.below(len(fb.rows)), {"key": f"SBX-{r.randint(1, 99999):05d}", "v": {"sub": "selftest"}, "rev": 1, "kind": "sandbox"}, ["SANDBOX"]))
    for pos, f, rs in sorted(extra, key=lambda e: -e[0]):
        f.update({"id": 1, "date": 1, "suite": 1, "q": None})
        fb.rows.insert(pos, {"f": f, "r": rs, "k": None, "c": {}})
    for i in range(len(fb.rows) // 11):
        j = r.below(len(fb.rows))
        if fb.rows[j]["f"]["kind"] == "canon":
            fb.rows.insert(j + 1, {"f": dict(fb.rows[j]["f"]), "r": [c for c in fb.rows[j]["r"] if fb.rules[c]["mode"] != "line"] + ["DUPROW"], "k": None, "c": {}})
    fb.rows[0]["r"].append("BOM")
    tab_flags(fb)
    W.item_added = {iid: T(2025, 3, 1) + r.randint(0, 100) * 86400 for iid in items}

    def render_items(fb=fb, r=r):
        rows = [["item_id", "suite", "subtask", "taxonomy", "revision", "added"]]
        cur = "A"
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            k = f["key"]
            if "HDR" in rules and cur == "A":
                rows.append(["item_id", "subtask", "suite", "taxonomy", "revision", "added"])
                cur = "B"
            elif "HDR" not in rules and cur == "B":
                rows.append(["item_id", "suite", "subtask", "taxonomy", "revision", "added"])
                cur = "A"
            bench = PREFIX_BENCH.get(k.split("-")[0])
            suite = "sandbox" if f["kind"] == "sandbox" else (legacy_suite[bench] if ("SUITE_ALIAS" in rules or (f["rev"] < 3 and f["kind"] != "canon")) else bench)
            if "WS_SUITE" in rules:
                suite += " "
            sub = f["v"]["sub"]
            if "B_QUOTE" in rules:
                sub = sub + ", core"
            tax = W.item_taxo.get(k, "v1") if "TAXO" in rules else "-"
            added = W.item_added.get(k, T(2025, 4, 1))
            ad = repr(excel_serial(added)) if "ADDED_SERIAL" in rules else time.strftime("%Y-%m-%d", time.gmtime(added))
            idv = v_id(k, rules, "I")
            cells = [idv, suite, sub, tax, v_rev(f["rev"], rules), ad] if cur == "A" else [idv, sub, suite, tax, v_rev(f["rev"], rules), ad]
            rows.append(cells)
        return csv_bytes(rows, bom=True)
    fb.render = render_items
    out.append(fb)

    # ---------------- gold_labels.tsv ----------------
    name = "gold_labels.tsv"
    r = rngs(name)
    fb = FB(name, tests=["item_scores_arith", "item_scores_intent", "item_scores_mcq", "item_scores_longctx", "item_scores_multiling", "metric_safety"])
    reg_kit(fb, "id", "I", "Item id", "item_registry.csv")
    fb.R("ERRATA", "T7", "A gold value corrected by an upheld grader erratum is replaced by the erratum's value; withdrawn errata change nothing.",
         "grader_errata.xml", ["grader_errata.xml", "gold_labels_corrected.csv"], mode="row", via_rules=[g("grader_errata.xml", "TICKET")])
    fb.R("V1NAMES", "T17", "Intent gold labels are written in the class names of the item's taxonomy version from the item registry.", "label_aliases.json", ["item_registry.csv", "label_aliases.json"], mode="ctx", cond=True, via_rules=[g("item_registry.csv", "TAXO")])
    fb.R("NFD", "T10", "Text gold values can be in decomposed Unicode form; compare in NFC.", MD, [MD, "prompt_locales.tsv"], mode="line", fields=["text"])
    fb.R("NUM_PLAIN", "T4", "Numeric gold values are plain en_US decimals without grouping; a leading minus is negative.", MD, [MD, "scoring_parameters.xlsx"], mode="ctx", ht=True)
    fb.R("TAB_ESC", "T9", "Tabs inside gold text are written as \\t.", SC, [SC, MD], mode="ctx")
    fb.R("SENT_DASH", "T5", "A gold of - marks a suite without a gold answer (preference items).", MD, [MD, "item_registry.csv"], mode="ctx")
    fb.R("CODE_TESTS", "T17", "For code problems the gold column holds the problem's test count; a sample passes only when it passes all of them.", MD, [MD, "code_samples.jsonl"], mode="ctx", cond=True)
    fb.R("SAFETY01", "T2", "Safety gold is 1 for unsafe and 0 for safe.", MD, [MD, "item_registry.csv"], mode="ctx")
    fb.R("B_ZERO", "T20", "A numeric gold of 0.00 is a real answer.", MD, [MD, "scoring_parameters.xlsx"], mode="line", bait=True, fields=["num0"], ht=True)
    fb.R("OUTLIER", "T15", "Very large or negative numeric gold values are valid.", MD, [MD, "scoring_parameters.xlsx"], mode="ctx", bait=True)
    fb.R("HDR", "T8", "A repeated header line inside gold_labels.tsv renames gold to answer for the rows after it.", SC, [SC, "item_registry.csv"], mode="pos")
    fb.R("DUPROW", "T20", "A gold row repeated verbatim is one row.", POL, [POL, ER], mode="row", bait=True)
    fb.R("LATIN1", "T10", "Rows of gold_labels.tsv that are not valid UTF-8 are Latin-1.", SC, [SC, "prompt_locales.tsv"], mode="line", fields=["latin"], excl=("I_HOMO", "NFD", "I_FW"))
    kit_tab(fb)
    def gold_text(k, wrong=False):
        it = W.items[k]
        b = it["bench"]
        if b == "arith":
            g_ = it["gold"] + (Decimal("1.00") if wrong else 0)
            return format(g_, "f")
        if b == "code":
            return str(it["tests"] + (1 if wrong else 0))
        if b == "intent":
            c = it["gold"] if not wrong else r.choice([x for x in INTENT_CLASSES if x != it["gold"]])
            return c if W.item_taxo.get(k, "v1") in ("v1", "") else v2(c)
        if b == "safety":
            return str(1 - it["gold"] if wrong else it["gold"])
        if b == "mcq":
            return it["gold"] if not wrong else r.choice([o for o in "ABCDE"[:it["n_options"]] if o != it["gold"]])
        if b == "pref":
            return "-"
        return it["gold"] if not wrong else it["gold"] + "a"
    # errata-corrected items: the gold row is wrong and an upheld erratum fixes it
    reg_rows(W, r, fb, items, lambda k: {"g": gold_text(k, wrong=k in W.gold_err)}, lambda k: {"g": gold_text(k, wrong=True)}, lambda k: fake_item(r, k))
    for row in fb.rows:
        k = row["f"]["key"]
        it = W.items.get(k)
        f = row["f"]
        f["id"] = 1
        f["text"] = 1 if it and it["bench"] in ("longctx", "multiling") else None
        gv = f["v"]["g"]
        f["latin"] = 1 if (f["text"] and any(ord(c) > 127 for c in gv) and all(ord(c) < 256 for c in gv)) else None
        f["num0"] = 1 if it and it["bench"] == "arith" and Decimal(gv) == 0 else None
        if not it:
            continue
        b = it["bench"]
        if f["kind"] == "canon" and k in W.gold_err:
            row["r"].append("ERRATA")
        if b == "intent" and W.item_taxo.get(k, "v1") in ("v1", "") and it["gold"] in V2NAME:
            row["r"].append("V1NAMES")
        if b == "pref":
            row["r"].append("SENT_DASH")
        if b == "code":
            row["r"].append("CODE_TESTS")
        if b == "safety":
            row["r"].append("SAFETY01")
        if b == "arith" and (abs(it["gold"]) >= 1000000 or it["gold"] < 0):
            row["r"].append("OUTLIER")
    for i in range(len(fb.rows) // 9):
        j = r.below(len(fb.rows))
        if fb.rows[j]["f"]["kind"] == "canon":
            fb.rows.insert(j + 1, {"f": dict(fb.rows[j]["f"]), "r": [c for c in fb.rows[j]["r"] if fb.rules[c]["mode"] != "line"] + ["DUPROW"], "k": None, "c": {}})
    tab_flags(fb)

    def render_gold(fb=fb):
        lines = ["item_id\tgold\trevision"]
        cur = "A"
        out_b = bytearray()
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            if "HDR" in rules and cur == "A":
                lines.append("item_id\tanswer\trevision")
                cur = "B"
            elif "HDR" not in rules and cur == "B":
                lines.append("item_id\tgold\trevision")
                cur = "A"
            gv = text_cell(f["v"]["g"], rules).replace("\t", "\\t")
            ln = f"{v_id(f['key'], rules, 'I')}\t{gv}\t{v_tw(v_rev(f['rev'], rules), rules)}"
            lines.append(("L", ln) if "LATIN1" in rules else ln)
        for ln in lines:
            out_b += (ln[1].encode("latin-1") if isinstance(ln, tuple) else ln.encode("utf-8")) + b"\n"
        return bytes(out_b)
    fb.render = render_gold
    out.append(fb)
    return out

# ---------------------------------------------------------------------------------
# per-item registries
# ---------------------------------------------------------------------------------
LOCALE_TAG = {"en": ["en-US", "en_US", "EN-us", "en"], "de": ["de-DE", "de_DE", "de"], "es": ["es-ES", "es_MX", "es"],
              "fr": ["fr-FR", "fr_CA", "fr"], "he": ["he-IL", "he", "iw"], "hi": ["hi-IN", "hi"], "id": ["id-ID", "id", "in"],
              "ja": ["ja-JP", "ja"], "pt": ["pt-BR", "pt_PT", "pt"], "ru": ["ru-RU", "ru"], "sw": ["sw-KE", "sw"]}
DEPRECATED = {"iw": "he", "in": "id", "jw": "jv", "ji": "yi", "mo": "ro"}


def std_extra(fb, doc2, hdr=True, ws_field=None):
    """Format-level rules shared by tabular registries."""
    if hdr:
        fb.R("HDR", "T8", f"A repeated header inside {fb.name} reorders its columns for the rows after it.", SC, [SC, doc2], mode="pos")
    fb.R("DUPROW", "T20", f"An entry of {fb.name} repeated verbatim is one entry, not a conflict.", POL, [POL, ER], mode="row", bait=True)


def add_dups(fb, r, frac=9):
    for i in range(len(fb.rows) // frac):
        j = r.below(len(fb.rows))
        if fb.rows[j]["f"].get("kind") == "canon":
            fb.rows.insert(j + 1, {"f": dict(fb.rows[j]["f"]), "r": [c for c in fb.rows[j]["r"] if fb.rules[c]["mode"] != "line"] + ["DUPROW"], "k": None, "c": {}})


def tab_render(fb, header_a, header_b, cell_fn, delim, bom=False, enc_rule=None):
    import csv as _csv
    buf = io.StringIO()
    w = _csv.writer(buf, delimiter=delim, lineterminator="\n")
    w.writerow(header_a)
    cur = "A"
    latin_lines = []
    for row in fb.rows:
        rules = row["r"]
        lay = "B" if "HDR" in rules else "A"
        if lay != cur:
            w.writerow(header_b if lay == "B" else header_a)
            cur = lay
        cells = cell_fn(row, lay)
        w.writerow(cells)
    data = buf.getvalue()
    if enc_rule:
        outb = bytearray()
        marks = {id(row) for row in fb.rows if enc_rule in row["r"]}
        lines = data.split("\n")
        # re-render line by line to know which lines are latin-1: rows map 1:1 after headers
        idx = 0
        rows_iter = iter(fb.rows)
        for ln in lines[:-1]:
            if ln.split(delim)[0] in (header_a[0], header_b[0]) and ln.startswith(header_a[0]):
                outb += ln.encode("utf-8") + b"\n"
                continue
            row = next(rows_iter)
            if id(row) in marks:
                try:
                    outb += ln.encode("latin-1") + b"\n"
                    continue
                except UnicodeEncodeError:
                    pass
            outb += ln.encode("utf-8") + b"\n"
        return (b"\xef\xbb\xbf" if bom else b"") + bytes(outb)
    return (b"\xef\xbb\xbf" if bom else b"") + data.encode("utf-8")


def build_item_files(W, rngs):
    out = []
    P = W.params
    items = sorted(W.items)

    # ---------------- dedup_clusters.tsv ----------------
    name = "dedup_clusters.tsv"
    r = rngs(name)
    fb = FB(name, tests=["item_eligibility", "metric_accuracy"])
    reg_kit(fb, "id", "I", "Item id", "item_registry.csv")
    std_extra(fb, "item_registry.csv")
    fb.R("CANON", "T1", "Within a cluster the canonical member is the lowest item id after canonicalisation; every other member is a duplicate.", POL, [POL, "item_registry.csv"], mode="ctx", via_rules=[g("item_registry.csv", "I_PAD")])
    fb.R("SIM_LOC", "T4", "Similarity values written with a comma decimal mark come from the de_DE clustering run.", SC, [SC, MD], mode="line", fields=["sim"])
    fb.R("SIM_PCT", "T2", "Similarity values above 1 are percentages.", SC, [SC, MD], mode="line", fields=["sim"])
    fb.R("SINGLETON", "T5", "A cluster id of 0 means singleton; singletons that share cluster 0 are not duplicates of one another.", POL, [POL, "item_registry.csv"], mode="ctx", bait=True)
    fb.R("SIM_BAIT", "T15", "Members with low similarity in a multi-member cluster are still duplicates; cluster membership, not similarity, decides.", POL, [POL, MD], mode="ctx", bait=True)
    fb.R("SPLIT", "T7", "A later revision can move an item out of its cluster (cluster 0); the highest revision decides membership.", POL, [POL, ER], mode="ctx")
    fb.R("XSUITE", "T20", "Cluster ids repeat across suites; a cluster is the pair (suite prefix, cluster id).", POL, [POL, "item_registry.csv"], mode="ctx", bait=True)
    fb.R("TAB_TRAIL", "T9", "Some dedup rows end with a trailing tab (empty fifth column).", SC, [SC, "item_registry.csv"], mode="line", fields=["id"])
    fb.R("CL_PAD", "T4", "Cluster ids can be zero-padded to four digits.", POL, [POL, "item_registry.csv"], mode="line", fields=["cl"])
    kit_tab(fb)
    clusters = {}
    cid = 0
    for d, c in sorted(W.dup_of.items()):
        clusters.setdefault(c, set()).add(d)
    W.cluster_id = {}
    for c in sorted(clusters):
        cid += 1
        W.cluster_id[c] = cid % 997 + 1
        for d in clusters[c]:
            W.cluster_id[d] = cid % 997 + 1
    reg_rows(W, r, fb, items, lambda k: {"c": W.cluster_id.get(k, 0), "sim": Decimal(r.randint(850, 999)).scaleb(-3) if k in W.cluster_id else Decimal(0)},
             lambda k: {"c": 0 if k in W.cluster_id else r.randint(1, 997), "sim": Decimal(r.randint(100, 999)).scaleb(-3)}, lambda k: fake_item(r, k))
    for row in fb.rows:
        f = row["f"]
        f.update({"id": 1, "sim": 1 if f["v"]["sim"] > 0 else None, "cl": 1})
        if f["v"]["c"] == 0 and f["kind"] == "canon" and r.chance(0.04):
            row["r"].append("SINGLETON")
        if f["kind"] == "canon" and f["key"] in W.dup_of:
            row["r"].append("CANON")
            if f["v"]["sim"] < Decimal("0.9"):
                row["r"].append("SIM_BAIT")
        if f["kind"] == "older" and f["key"] not in W.cluster_id:
            row["r"].append("SPLIT")
        if f["kind"] == "canon" and f["v"]["c"] and f["v"]["c"] % 7 == 0:
            row["r"].append("XSUITE")
    add_dups(fb, r)
    tab_flags(fb)

    def cells_dedup(row, lay):
        f, rules = row["f"], row["r"]
        s = f["v"]["sim"]
        if "SIM_PCT" in rules:
            s = s * 100
        sv = v_num(s, 1 if "SIM_PCT" in rules else 3, "de_DE" if "SIM_LOC" in rules else "en_US", group=False)
        c = [v_id(f["key"], rules, "I"), (f"{f['v']['c']:04d}" if "CL_PAD" in rules else str(f["v"]["c"])), sv, v_tw(v_rev(f["rev"], rules), rules)]
        if lay == "B":
            c = [c[1], c[0], c[2], c[3]]
        if "TAB_TRAIL" in rules:
            c.append("")
        return c
    fb.render = lambda fb=fb: tab_render(fb, ["item_id", "cluster", "similarity", "revision"], ["cluster", "item_id", "similarity", "revision"], cells_dedup, "\t")
    out.append(fb)

    # ---------------- contamination_hits.jsonl ----------------
    name = "contamination_hits.jsonl"
    r = rngs(name)
    fb = FB(name, tests=["item_eligibility", "metric_accuracy"])
    kit_ids(fb, "id", "I", "Item id", "item_registry.csv", ht=("CASE",))
    fb.R("THRESH", "T11", "An item is contaminated when any live scan overlap is at or above its suite's threshold in the metric definitions (greater than or equal).", MD, [MD, "item_registry.csv"], mode="ctx", via_rules=[g(MD, "THRESH_TBL")])
    fb.R("NEAR", "T15", "Overlaps just below the threshold are clean; they are not rounded up.", MD, [MD, POL], mode="ctx", bait=True)
    fb.R("PCT", "T2", "Scans by detector ngram-v1 report overlap as a percentage (0 to 100).", SC, [SC, MD], mode="line", fields=["ov"])
    fb.R("ROUND", "T12", "Overlaps can carry extra digits; round half-even to 4 decimals before comparing with the threshold.", MD, [MD, "item_registry.csv"], mode="line", fields=["ov"])
    fb.R("RETRACT", "T6", "A scan line with retracted true is withdrawn by the scanning team and carries no evidence.", POL, [POL, ER], mode="row")
    fb.R("SHARDVOID", "T13", "Scans against training shards listed as excluded in the errata register do not count.", ER, [ER, MD], mode="row", via_rules=[g(ER, "RID_SRC")])
    fb.R("DUPSCAN", "T20", "The same item and shard can be scanned more than once; any live scan at or above the threshold contaminates.", POL, [POL, MD], mode="row", bait=True)
    fb.R("SERIAL_TS", "T3", "scanned_at is ISO 8601 UTC, or epoch seconds for older scanner builds.", SC, [SC, MD], mode="line", fields=["ts"])
    fb.R("NULLOV", "T5", "An overlap of null means the scan failed and carries no evidence.", MD, [MD, POL], mode="row")
    fb.R("FK", "T13", "Scans for unregistered item ids are ignored.", POL, ["item_registry.csv", POL], mode="row")
    fb.R("STR_NUM", "T9", "Some overlaps are JSON strings rather than numbers.", SC, [SC, MD], mode="line", fields=["ov"])
    fb.R("KEYALIAS", "T8", "Older scanner builds name the item field item_ref instead of item.", SC, [SC, "item_registry.csv"], mode="line", fields=["id"])
    fb.R("DET_CASE", "T1", "Detector names can be upper-cased.", SC, [SC, MD], mode="line", fields=["id"])
    fb.R("SHARD_CASE", "T1", "Training shard names can be upper-cased (SHARD-0042).", MD, [MD, ER], mode="line", fields=["id"])
    fb.R("B_LOW", "T15", "Scans with very low overlap are real scans and keep their item clean.", MD, [MD, POL], mode="line", bait=True, fields=["low"], ht=True)
    W.shard_excluded = sorted({f"shard-{r.randint(5000, 5999):04d}" for _ in range(24)})
    for k in items:
        th = W.contam_threshold[W.items[k]["bench"]]
        hits = list(W.contam[k])
        nscan = max(len(hits), r.randint(1, 3))
        while len(hits) < nscan:
            hits.append((f"shard-{r.randint(0, 4095):04d}", Decimal(r.randint(10, 4800)).scaleb(-4)))
        for sh, ov in hits:
            rs = []
            if ov >= th:
                rs.append("THRESH")
            elif th - ov <= Decimal("0.0050"):
                rs.append("NEAR")
            fb.add({"key": k, "sh": sh, "ov": ov, "kind": "canon", "id": 1, "ts": 1}, rs)
        if r.chance(0.04):  # retracted high-overlap scan
            fb.add({"key": k, "sh": f"shard-{r.randint(0, 4095):04d}", "ov": th + Decimal("0.1000"), "kind": "retract", "id": 1, "ts": 1}, ["RETRACT"])
        if r.chance(0.03):
            fb.add({"key": k, "sh": r.choice(W.shard_excluded), "ov": min(Decimal("0.9999"), th + Decimal("0.0500")), "kind": "shardvoid", "id": 1, "ts": 1}, ["SHARDVOID"])
        if r.chance(0.02):
            fb.add({"key": k, "sh": f"shard-{r.randint(0, 4095):04d}", "ov": None, "kind": "null", "id": 1, "ts": 1}, ["NULLOV"])
        if r.chance(0.01):
            fb.add({"key": fake_item(r, k), "sh": "shard-0001", "ov": Decimal("0.9900"), "kind": "fk", "id": 1, "ts": 1}, ["FK"])
        if hits and r.chance(0.03):
            sh0, ov0 = hits[0]
            fb.add({"key": k, "sh": sh0, "ov": max(Decimal("0.0100"), ov0 - Decimal("0.2000")), "kind": "dupscan", "id": 1, "ts": 1}, ["DUPSCAN"])
    for row in fb.rows:
        row["f"]["ov_"] = row["f"]["ov"]
        if row["f"]["ov"] is None:
            row["f"]["ov"] = None
        else:
            row["f"]["ov"] = 1
            row["f"]["ovv"] = row["f"]["ov_"]
        row["f"]["low"] = 1 if (row["f"]["ov_"] is not None and row["f"]["ov_"] < Decimal("0.1")) else None

    def render_contam(fb=fb, r=r):
        lines = []
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            ov = f["ov_"]
            det = "ngram-v1" if "PCT" in rules else "ngram-v2"
            if ov is None:
                ovv = None
            else:
                d = ov * 100 if "PCT" in rules else ov
                dp = 2 if "PCT" in rules else 4
                s = v_excess(d, dp, r) if "ROUND" in rules else format(d.quantize(Decimal(1).scaleb(-dp)), "f")
                ovv = s if "STR_NUM" in rules else float(s)
            t = T(2025, 6, 1) + r.randint(0, 80 * 86400)
            obj = {("item_ref" if "KEYALIAS" in rules else "item"): v_id(f["key"], rules, "I"), "shard": f["sh"].upper() if "SHARD_CASE" in rules else f["sh"], "overlap": ovv,
                   "detector": det.upper() if "DET_CASE" in rules else det, "scanned_at": t if "SERIAL_TS" in rules else iso(t)}
            if f["kind"] == "retract":
                obj["retracted"] = True
            lines.append(json.dumps(obj, ensure_ascii=False))
        return ("\n".join(lines) + "\n").encode("utf-8")
    fb.render = render_contam
    out.append(fb)

    # ---------------- context_lengths.csv ----------------
    name = "context_lengths.csv"
    r = rngs(name)
    fb = FB(name, tests=["item_scores_longctx", "metric_accuracy"])
    reg_kit(fb, "id", "I", "Item id", "item_registry.csv")
    std_extra(fb, "checkpoint_lineage.json")
    fb.R("KUNIT", "T2", "Rows written by the batch counter give token counts in thousands with a k suffix (12.3k means 12300, exact to the hundred).", SC, [SC, "checkpoint_lineage.json"], mode="line", fields=["k"])
    fb.R("GROUP", "T4", "Token counts can carry thousands separators.", SC, [SC, "checkpoint_lineage.json"], mode="line", fields=["tok"])
    fb.R("WINDOW", "T11", "A prompt exactly at the model's context window fits; only counts above the window truncate.", MD, ["checkpoint_lineage.json", MD], mode="ctx", bait=True)
    fb.R("FAMILY", "T17", "The column used for a model is the tokenizer family that checkpoint_lineage.json lists for the model's checkpoint.", MD, ["checkpoint_lineage.json", MD, "checkpoint_lineage_snapshot.json"], mode="ctx", cond=True)
    fb.R("BOM", "T10", "context_lengths.csv starts with a byte order mark.", SC, [SC, MD], mode="row", ht=True)
    fb.R("OUTLIER", "T15", "Very long prompts are real.", MD, [MD, "item_registry.csv"], mode="ctx", bait=True)
    fb.R("TOK_SUFFIX", "T4", "Counts can carry a tok suffix (1234 tok).", SC, [SC, "checkpoint_lineage.json"], mode="line", fields=["tok"], excl=("KUNIT",))
    fb.R("SPACE_GROUP", "T4", "Token counts from the Paris counter use a space as thousands separator.", SC, [SC, "checkpoint_lineage.json"], mode="line", fields=["tok"])
    kit_tab(fb)
    fb.rules["GROUP"]["excl"] = {"SPACE_GROUP", "KUNIT"}
    fb.rules["SPACE_GROUP"]["excl"] = {"KUNIT"}
    def tok_canon(k):
        return dict(W.items[k]["tokens"])
    reg_rows(W, r, fb, items, tok_canon, lambda k: {"hbpe": W.items[k]["tokens"]["hbpe"] + r.randint(100, 9000), "ospsp": W.items[k]["tokens"]["ospsp"] + r.randint(100, 9000)}, lambda k: fake_item(r, k))
    W.tok_missing = set()
    for row in fb.rows:
        f = row["f"]
        k = f["key"]
        f.update({"id": 1, "tok": 1 if max(f["v"].values()) >= 1000 else None, "k": 1 if all(v % 100 == 0 for v in f["v"].values()) else None})
        it = W.items.get(k)
        if it and f["kind"] == "canon":
            if it["bench"] == "longctx":
                row["r"].append("FAMILY")
                if any(it["tokens"][t] == CTX_WINDOW[fam] for fam, t in TOKENIZER.items()):
                    row["r"].append("WINDOW")
                if it["tokens"]["hbpe"] > 30000:
                    row["r"].append("OUTLIER")
    fb.rows[0]["r"].append("BOM")
    add_dups(fb, r)
    tab_flags(fb)
    # some items get counts exactly at a context window (fit, inclusive)
    def cells_ctx(row, lay):
        f, rules = row["f"], row["r"]
        def fmt(v):
            if "KUNIT" in rules:
                return f"{v / 1000:.1f}k"
            if "SPACE_GROUP" in rules:
                s_ = group3(str(v), " ")
            else:
                s_ = group3(str(v), ",") if "GROUP" in rules else str(v)
            return s_ + " tok" if "TOK_SUFFIX" in rules else s_
        c = [v_id(f["key"], rules, "I"), fmt(f["v"]["hbpe"]), fmt(f["v"]["ospsp"]), v_tw(v_rev(f["rev"], rules), rules)]
        return c if lay == "A" else [c[0], c[2], c[1], c[3]]
    fb.render = lambda fb=fb: tab_render(fb, ["item_id", "tokens_hbpe", "tokens_ospsp", "revision"], ["item_id", "tokens_ospsp", "tokens_hbpe", "revision"], cells_ctx, ",", bom=True)
    out.append(fb)

    # ---------------- slice_attributes.csv ----------------
    name = "slice_attributes.csv"
    r = rngs(name)
    fb = FB(name, tests=["slice_metrics"])
    reg_kit(fb, "id", "I", "Item id", "item_registry.csv")
    std_extra(fb, "slice_definitions.yaml")
    fb.R("DOM_ALIAS", "T17", "Domain values can be legacy codes (FIN, LAW, HLT, SCI, TEC, EVD) used before revision 3; slice_definitions.yaml maps them.", "slice_definitions.yaml", ["slice_definitions.yaml", POL], mode="ctx", cond=True)
    fb.R("DIFF_NUM", "T2", "Difficulty can be written as 1, 2 or 3 (easy, medium, hard).", "slice_definitions.yaml", ["slice_definitions.yaml", POL], mode="line", fields=["diff"])
    fb.R("CASE_ATTR", "T1", "Attribute values can be in any letter case.", "slice_definitions.yaml", ["slice_definitions.yaml", POL], mode="line", fields=["diff"])
    fb.R("EMPTY", "T5", "An empty difficulty means medium.", "slice_definitions.yaml", ["slice_definitions.yaml", POL], mode="ctx")
    fb.R("B_CODE", "T20", "A three-letter upper-case domain is a legacy code only when it is one of FIN, LAW, HLT, SCI, TEC, EVD; other upper-case values are just upper-cased domains.", "slice_definitions.yaml", ["slice_definitions.yaml", POL], mode="ctx", bait=True)
    fb.R("DOM_CASE", "T1", "Domain values can be upper-cased.", "slice_definitions.yaml", ["slice_definitions.yaml", POL], mode="line", fields=["q"], excl=("DOM_ALIAS",))
    fb.R("DIFF_WORD", "T17", "Difficulty can be written simple, moderate or difficult (easy, medium, hard).", "slice_definitions.yaml", ["slice_definitions.yaml", POL], mode="line", fields=["diff"], excl=("DIFF_NUM", "CASE_ATTR", "EMPTY"))
    fb.rules["DIFF_NUM"]["excl"] = {"CASE_ATTR", "EMPTY"}
    fb.rules["CASE_ATTR"]["excl"] = {"EMPTY"}
    kit_tab(fb)
    reg_rows(W, r, fb, items, lambda k: {"d": W.items[k]["domain"], "x": W.items[k]["difficulty"]}, lambda k: {"d": r.choice(DOMAINS), "x": r.choice(DIFFICULTY)}, lambda k: fake_item(r, k))
    dom_code = {"finance": "FIN", "law": "LAW", "health": "HLT", "science": "SCI", "tech": "TEC", "everyday": "EVD"}
    for row in fb.rows:
        f = row["f"]
        f.update({"id": 1, "diff": 1, "q": 1})
        if f["rev"] < 3 and f["kind"] == "canon":
            row["r"].append("DOM_ALIAS")
        if f["v"]["x"] == "medium" and f["kind"] == "canon" and r.chance(0.3):
            row["r"].append("EMPTY")
        if f["kind"] == "canon" and f["v"]["d"] in ("law", "tech") and r.chance(0.3) and "DOM_ALIAS" not in row["r"]:
            row["r"] += ["B_CODE"]
    add_dups(fb, r)
    tab_flags(fb)

    def cells_slice(row, lay):
        f, rules = row["f"], row["r"]
        d = dom_code[f["v"]["d"]] if ("DOM_ALIAS" in rules or (f["rev"] < 3 and f["kind"] != "canon")) else f["v"]["d"]
        x = f["v"]["x"]
        if "EMPTY" in rules:
            x = ""
        elif "DIFF_NUM" in rules:
            x = str(DIFFICULTY.index(x) + 1)
        elif "DIFF_WORD" in rules:
            x = {"easy": "simple", "medium": "moderate", "hard": "difficult"}[x]
        elif "CASE_ATTR" in rules:
            x = x.upper()
        if "DOM_CASE" in rules or "B_CODE" in rules:
            d = d.upper()
        c = [v_id(f["key"], rules, "I"), d, x, v_tw(v_rev(f["rev"], rules), rules)]
        return c if lay == "A" else [c[0], c[2], c[1], c[3]]
    fb.render = lambda fb=fb: tab_render(fb, ["item_id", "domain", "difficulty", "revision"], ["item_id", "difficulty", "domain", "revision"], cells_slice, ",")
    out.append(fb)

    # ---------------- prompt_locales.tsv ----------------
    name = "prompt_locales.tsv"
    r = rngs(name)
    fb = FB(name, tests=["metric_multiling", "item_scores_multiling"])
    reg_kit(fb, "id", "I", "Item id", "item_registry.csv")
    std_extra(fb, "locale_codes_legacy.tsv")
    fb.R("DEPREC", "T13", "Deprecated ISO 639 codes (iw, in, ...) are mapped through the legacy locale code table.", POL, ["locale_codes_legacy.tsv", POL], mode="ctx", via_rules=[g("locale_codes_legacy.tsv", "MAP")])
    fb.R("TAGFORM", "T1", "Locale tags use - or _ and any case; the language is the part before the separator, lower-cased.", POL, [POL, "locale_codes_legacy.tsv"], mode="line", fields=["tag"])
    fb.R("REGION", "T17", "The region subtag does not change the language (pt-BR and pt_PT are both pt) and is not the item's slice region, which comes from slice_definitions.yaml.", MD, [MD, "item_registry.csv", "slice_definitions.yaml", "slice_attributes.csv"], mode="ctx", cond=True)
    fb.R("LANGSUP", "T11", "A language enters the multilingual macro average only when it has at least the minimum support of eligible items in the slice definitions.", MD, ["slice_definitions.yaml", MD, "dedup_clusters.tsv", "contamination_hits.jsonl", "suite_manifest.xlsx", "locale_codes_legacy.tsv"], mode="ctx")
    fb.R("SCRIPT", "T10", "Some tags carry a script subtag (sr-Latn); the language is still the first subtag.", POL, [POL, MD], mode="line", fields=["tag"])
    kit_tab(fb)
    fb.R("PRIV", "T14", "Private-use subtags (x-...) carry no language information.", POL, [POL, MD], mode="line", fields=["tag"])
    fb.R("NUMREG", "T17", "Numeric region subtags (es-419) do not change the language.", POL, [POL, MD], mode="line", fields=["tag"], excl=("SCRIPT",))
    fb.R("B_EN", "T20", "A bare en tag is English exactly like en-US; it is not an unknown locale.", POL, [POL, MD], mode="line", bait=True, fields=["en"], ht=True)
    reg_rows(W, r, fb, items, lambda k: {"lang": W.items[k]["lang"]}, lambda k: {"lang": r.choice(LANGS)}, lambda k: fake_item(r, k))
    for row in fb.rows:
        f = row["f"]
        lang = f["v"]["lang"]
        opts = LOCALE_TAG[lang]
        f["tagv"] = r.choice(opts)
        f.update({"id": 1, "tag": 1, "en": 1 if f["tagv"] == "en" else None})
        if f["tagv"] in DEPRECATED:
            row["r"].append("DEPREC")
        if "_" in f["tagv"] or (f["tagv"].count("-") and f["tagv"].split("-")[1] not in ("US",)):
            row["r"].append("REGION") if lang != "en" else None
        if lang != "en" and f["kind"] == "canon" and r.chance(0.2):
            row["r"].append("LANGSUP")
    add_dups(fb, r)
    tab_flags(fb)

    def cells_loc(row, lay):
        f, rules = row["f"], row["r"]
        t = f["tagv"]
        if "TAGFORM" in rules:
            t = t.upper() if "-" in t or "_" in t else t.upper()
        if "SCRIPT" in rules and "-" in t:
            a, b_ = t.split("-", 1)
            t = a + "-Latn-" + b_
        if "NUMREG" in rules:
            t = t.replace("_", "-").split("-")[0] + "-419"
        if "PRIV" in rules:
            t = t + "-x-heron"
        c = [v_id(f["key"], rules, "I"), t, v_tw(v_rev(f["rev"], rules), rules)]
        return c if lay == "A" else [c[1], c[0], c[2]]
    fb.render = lambda fb=fb: tab_render(fb, ["item_id", "locale", "revision"], ["locale", "item_id", "revision"], cells_loc, "\t")
    out.append(fb)
    return out

# ---------------------------------------------------------------------------------
# per-item registries part 2, taxonomy, lineage, tags
# ---------------------------------------------------------------------------------
REGION_ALIAS = {"EU": ["EU", "Europe", "EMEA-EU"], "NA": ["NA", "North America", "AMER-N"], "APAC": ["APAC", "Asia-Pacific"],
                "LATAM": ["LATAM", "AMER-S"], "MEA": ["MEA", "EMEA-ME"]}
TOL_FORMS = {"exact": ["exact", "eq", "=="], "abs": ["abs:0.01", "absolute 0.01", "+-0.01"], "rel": ["rel:1%", "rel:0.01", "relative 1 percent"]}


def y(s):
    return json.dumps(s, ensure_ascii=False)


def build_item_files2(W, rngs):
    out = []
    P = W.params
    items = sorted(W.items)

    # ---------------- slice_definitions.yaml ----------------
    name = "slice_definitions.yaml"
    r = rngs(name)
    fb = FB(name, tests=["slice_metrics", "metric_multiling"])
    reg_kit(fb, "id", "I", "Item id", "item_registry.csv")
    fb.R("REGION_ALIAS", "T17", "Region values can be written as long names (Europe, North America, Asia-Pacific) or sales codes (EMEA-EU, AMER-N, AMER-S, EMEA-ME); the region_aliases map resolves them.",
         "slice_definitions.yaml", ["slice_attributes.csv", POL], mode="ctx", cond=True)
    fb.R("NULLREG", "T5", "A region of null means unknown; the item belongs to no region slice.", MD, [MD, "slice_attributes.csv"], mode="ctx")
    fb.R("ANCHOR", "T9", "Some region entries reuse a YAML anchor; the alias carries the same mapping.", SC, [SC, "slice_attributes.csv"], mode="line", fields=["anc"])
    fb.R("MINSUP", "T11", "A slice metric is reported only when the slice has at least min_support eligible items; below that it is null.", MD, [MD, "slice_attributes.csv", "dedup_clusters.tsv", "contamination_hits.jsonl", "suite_manifest.xlsx"], mode="ctx")
    fb.R("CONJ", "T17", "Slice conditions on different attributes are joined by AND; values listed for one attribute are joined by OR.", MD, ["slice_attributes.csv", MD], mode="ctx", cond=True)
    fb.R("CASE_REG", "T1", "Region values are case-insensitive.", POL, [POL, "slice_attributes.csv"], mode="line", fields=["reg"])
    fb.R("B_NA", "T20", "The region code NA is North America; it is not a missing value.", POL, [POL, MD], mode="line", bait=True, fields=["na"], ht=True)
    fb.R("DUPROW", "T20", "A region entry repeated verbatim is one entry.", POL, [POL, ER], mode="row", bait=True)
    kit_tab(fb, tw=False)
    fb.R("ITEM_KEY", "T8", "Some region entries name the item key id instead of item.", SC, [SC, POL], mode="line", fields=["id"])
    fb.R("COMMENTS", "T20", "A # after an entry starts a comment.", SC, [SC, POL], mode="line", bait=True, fields=["id"])
    fb.R("SQUOTE", "T9", "Some strings use single quotes.", SC, [SC, POL], mode="line", fields=["id"], excl=("FLOW",))
    fb.R("FLOW", "T9", "Some region entries are written in block style over three lines instead of flow style.", SC, [SC, POL], mode="line", fields=["id"])
    reg_rows(W, r, fb, items, lambda k: {"g": W.items[k]["region"]}, lambda k: {"g": r.choice(REGIONS)}, lambda k: fake_item(r, k))
    W.region_null = set()
    for row in fb.rows:
        f = row["f"]
        f.update({"id": 1, "reg": 1, "na": 1 if f["v"]["g"] == "NA" else None, "anc": None})
        if f["kind"] == "canon" and r.chance(0.18):
            row["r"].append("REGION_ALIAS")
            f["alias"] = r.choice(REGION_ALIAS[f["v"]["g"]][1:])
        if f["kind"] == "canon" and r.chance(0.08):
            row["r"].append("MINSUP")
        if f["kind"] == "canon" and r.chance(0.08):
            row["r"].append("CONJ")
    add_dups(fb, r)
    tab_flags(fb)

    def render_sd(fb=fb):
        L = ["# Slice definitions for the Q3 2025 certification close", f"min_support: {P['min_support']}",
             f"lang_min_support: {P['lang_min_support']}", "domain_codes:"]
        for k_, v_ in sorted({"FIN": "finance", "LAW": "law", "HLT": "health", "SCI": "science", "TEC": "tech", "EVD": "everyday"}.items()):
            L.append(f"  {k_}: {v_}")
        L.append("difficulty_codes:")
        L += ["  '1': easy", "  '2': medium", "  '3': hard"]
        L.append("region_aliases:")
        for reg, al in sorted(REGION_ALIAS.items()):
            for a in al[1:]:
                L.append(f"  {y(a)}: {reg}")
        L.append("slices:")
        for nm, conds in P["slices"]:
            L.append(f"  {nm}:")
            for fld, vals in conds:
                L.append(f"    {fld}: [{', '.join(vals)}]")
        L.append("regions:")
        first_anchor = {}
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            reg = f.get("alias", f["v"]["g"]) if "REGION_ALIAS" in rules else f["v"]["g"]
            if "CASE_REG" in rules:
                reg = reg.lower()
            regs = y(reg)
            revv = y(v_rev(f["rev"], rules)) if "REV_TXT" in rules else str(f["rev"])
            if "FLOW" in rules:
                L.append(f"  - {'id' if 'ITEM_KEY' in rules else 'item'}: {y(v_id(f['key'], rules, 'I'))}")
                L.append(f"    region: {regs}")
                L.append(f"    rev: {revv}")
            else:
                itv = y(v_id(f['key'], rules, 'I'))
                if "SQUOTE" in rules:
                    itv = "'" + v_id(f['key'], rules, 'I') + "'"
                kk = "id" if "ITEM_KEY" in rules else "item"
                L.append(f"  - {{{kk}: {itv}, region: {regs}, rev: {revv}}}" + ("  # reviewed" if "COMMENTS" in rules else ""))
        return ("\n".join(L) + "\n").encode("utf-8")
    fb.render = render_sd
    out.append(fb)

    # ---------------- suite_manifest.xlsx ----------------
    name = "suite_manifest.xlsx"
    r = rngs(name)
    fb = FB(name, tests=["item_eligibility"])
    reg_kit(fb, "id", "I", "Item id", "item_registry.csv")
    fb.R("SERIAL", "T3", "changed_at is a spreadsheet serial date (days since 1899-12-30, fractional days are time of day UTC).", SC, [SC, POL], mode="line", fields=["date"], ht=True)
    fb.R("DATE_TEXT", "T3", "Some changed_at cells are ISO text dates instead of serial numbers.", SC, [SC, POL], mode="line", fields=["date"])
    fb.R("STATUS_ALIAS", "T17", "Status can be written retired, ret or R; active, act or A; added means active.", POL, [POL, "item_registry.csv"], mode="line", fields=["st"])
    fb.R("LATE_RETIRE", "T11", "A retirement takes effect only when changed_at is before the window end (2025-10-01T00:00:00Z); later retirements do not apply to this close.", POL, [POL, MA], mode="row")
    fb.R("REINSTATE", "T7", "An item retired and later reinstated (a higher revision with status active) is active.", POL, [POL, ER], mode="row")
    fb.R("TEXTNUM", "T4", "Revision cells can be text instead of numbers.", SC, [SC, POL], mode="line", fields=["revt"])
    fb.R("SHEETHDR", "T8", "Each sheet orders its columns differently; read the header row of each sheet.", SC, [SC, "item_registry.csv"], mode="ctx")
    fb.R("SENT_ZERO", "T5", "A changed_at of 0 means the date was not captured; such rows take effect at the start of the window.", POL, [POL, SC], mode="row")
    fb.R("B_ADDED", "T20", "Status added marks an item introduced this quarter; it is active, not pending.", POL, [POL, "item_registry.csv"], mode="line", bait=True, fields=["add"], ht=True)
    fb.R("CROSS", "T13", "Each sheet lists only its own suites; a row whose item prefix belongs to another sheet's suites is a misfiled row and is ignored.", POL, [POL, "item_registry.csv"], mode="row")
    fb.R("DUPROW", "T20", "A row repeated verbatim is one row.", POL, [POL, ER], mode="row", bait=True)
    kit_tab(fb, rev=False, tw=False, lb=True)
    groups = [("core", ("arith", "intent")), ("reasoning", ("mcq", "longctx")), ("safety_code_pref", ("safety", "code", "pref")), ("multilingual", ("multiling",))]
    def canon_st(k):
        return {"st": "retired" if k in W.retired else ("added" if r.chance(0.1) else "active"), "t": T(2025, 7, 1) + r.randint(0, 85) * 86400 + r.randint(0, 86399)}
    reg_rows(W, r, fb, items, canon_st, lambda k: {"st": "active" if k in W.retired else "retired", "t": T(2025, 7, 2) + r.randint(0, 80) * 86400}, lambda k: fake_item(r, k))
    extra = []
    for k in items:
        if k not in W.retired and r.chance(0.025):
            extra.append({"key": k, "v": {"st": "retired", "t": WINDOW_END + r.randint(0, 20 * 86400)}, "rev": 9, "kind": "lateret"})
        if k in W.retired and r.chance(0.1):
            extra.append({"key": k, "v": {"st": "retired", "t": 0}, "rev": 1, "kind": "zero"})
    for f in extra:
        fb.rows.insert(r.below(len(fb.rows)), {"f": f, "r": ["LATE_RETIRE"] if f["kind"] == "lateret" else ["SENT_ZERO"], "k": None, "c": {}})
    for row in fb.rows:
        f = row["f"]
        f.update({"id": 1, "date": 1 if f["v"]["t"] else None, "st": 1, "revt": 1, "add": 1 if f["v"]["st"] == "added" else None, "lbf": 1})
        if f["kind"] == "older" and f["key"] in W.retired is False:
            pass
        bench = PREFIX_BENCH.get(f["key"].split("-")[0], "arith")
        f["sheet"] = next(gi for gi, (gn, bs) in enumerate(groups) if bench in bs)
        row["r"].append("SHEETHDR") if r.chance(0.05) else None
    for k in items:
        if k not in W.retired and r.chance(0.02):
            fb.rows.insert(r.below(len(fb.rows)), {"f": {"key": k, "v": {"st": "retired", "t": T(2025, 7, 15)}, "rev": 1, "kind": "older", "id": 1, "date": 1, "st": 1, "revt": 1, "add": None, "lbf": 1,
                                                          "sheet": next(gi for gi, (gn, bs) in enumerate(groups) if W.items[k]["bench"] in bs)}, "r": ["REINSTATE"], "k": None, "c": {}})
        if r.chance(0.01):
            bench = W.items[k]["bench"]
            gi = next(i for i, (gn, bs) in enumerate(groups) if bench in bs)
            fb.rows.insert(r.below(len(fb.rows)), {"f": {"key": k, "v": {"st": "retired", "t": T(2025, 7, 20)}, "rev": 99, "kind": "cross", "id": 1, "date": 1, "st": 1, "revt": 1, "add": None, "lbf": 1,
                                                          "sheet": (gi + 1) % 4}, "r": ["CROSS"], "k": None, "c": {}})
    add_dups(fb, r)
    hdrs = [["item_id", "status", "changed_at", "revision"], ["status", "item_id", "revision", "changed_at"],
            ["revision", "item_id", "changed_at", "status"], ["item_id", "revision", "status", "changed_at"]]

    def render_sm(fb=fb, r=r):
        sheets = []
        for gi, (gn, bs) in enumerate(groups):
            rows = [hdrs[gi]]
            for row in fb.rows:
                f, rules = row["f"], row["r"]
                if f["sheet"] != gi:
                    continue
                st = f["v"]["st"]
                if "STATUS_ALIAS" in rules:
                    st = {"retired": r.choice(["ret", "R"]), "active": r.choice(["act", "A"]), "added": "added"}[st]
                t = f["v"]["t"]
                tv = 0 if not t else (time.strftime("%Y-%m-%d", time.gmtime(t)) if "DATE_TEXT" in rules else excel_serial(t))
                rv = str(f["rev"]) if "TEXTNUM" in rules else f["rev"]
                cell = {"item_id": v_id(f["key"], rules, "I"), "status": v_lb(st, rules), "changed_at": tv, "revision": rv}
                rows.append([cell[h] for h in hdrs[gi]])
            sheets.append((gn, rows))
        return xlsx_bytes(sheets)
    fb.render = render_sm
    out.append(fb)

    # ---------------- scoring_parameters.xlsx ----------------
    name = "scoring_parameters.xlsx"
    r = rngs(name)
    fb = FB(name, tests=["item_scores_arith", "item_scores_code", "leaderboard_aggregate"])
    reg_kit(fb, "id", "I", "Item id", "item_registry.csv")
    fb.R("TOL_FORM", "T17", "Arithmetic tolerance is written in several forms: exact/eq/==, abs:0.01/absolute 0.01/+-0.01, rel:1%/rel:0.01/relative 1 percent.", MD, [MD, "gold_labels.tsv"], mode="line", fields=["tol"])
    fb.R("REL_INCL", "T11", "Tolerances are inclusive: |answer - gold| <= 0.01 (abs) or <= 1% of |gold| (rel).", MD, [MD, "gold_labels.tsv"], mode="ctx", bait=True)
    fb.R("NOPT_LET", "T17", "n_options can be written as a letter range (A-D means 4).", MD, [MD, "gold_labels.tsv"], mode="line", fields=["nopt"])
    fb.R("TESTS_TXT", "T4", "Test counts can be text with a trailing 'tests'.", MD, [MD, "code_samples.jsonl"], mode="line", fields=["tests"])
    fb.R("CHANCE", "T12", "The chance level of the multiple-choice suite is the mean of 1/n_options over eligible items, computed exactly.", MD, [MD, "item_registry.csv"], mode="ctx")
    fb.R("SHEETS", "T8", "Parameters are split across three sheets (numeric, choice, text) with different column orders.", SC, [SC, "item_registry.csv"], mode="ctx", ht=True)
    fb.R("SENT_DASH", "T5", "A parameter of - means the suite has none.", MD, [MD, "item_registry.csv"], mode="ctx")
    fb.R("DUPROW", "T20", "A row repeated verbatim is one row.", POL, [POL, ER], mode="row", bait=True)
    kit_tab(fb, tw=False, lb=True)
    fb.R("PROFILE", "T20", "Text-sheet profile values are informational; grading follows the metric definitions.", MD, [MD, POL], mode="line", bait=True, fields=["id"])
    fb.R("NOPT_WORD", "T17", "n_options can be written as a word (four, five).", MD, [MD, "gold_labels.tsv"], mode="line", fields=["nopt"], excl=("NOPT_LET",))
    fb.R("B_EXACT0", "T20", "An exact tolerance on an integer gold still compares at two decimals.", MD, [MD, "gold_labels.tsv"], mode="line", bait=True, fields=["ex"], ht=True)
    def sp_canon(k):
        it = W.items[k]
        return {"tol": it.get("tol"), "tests": it.get("tests"), "nopt": it.get("n_options")}
    reg_rows(W, r, fb, items, sp_canon, lambda k: {"tol": r.choice(["exact", "abs", "rel"]), "tests": r.randint(5, 20), "nopt": r.choice([4, 5])}, lambda k: fake_item(r, k))
    for row in fb.rows:
        f = row["f"]
        b = PREFIX_BENCH.get(f["key"].split("-")[0])
        f.update({"id": 1, "tol": 1 if b == "arith" else None, "nopt": 1 if b == "mcq" else None, "tests": 1 if b == "code" else None,
                  "ex": 1 if (b == "arith" and f["v"]["tol"] == "exact") else None, "b": b, "revf": 1, "lbf": 1})
        if b == "arith" and f["v"]["tol"] in ("abs", "rel") and f["kind"] == "canon" and r.chance(0.3):
            row["r"].append("REL_INCL")
        if b == "mcq" and f["kind"] == "canon" and r.chance(0.2):
            row["r"].append("CHANCE")
        if b in ("pref", "longctx", "multiling", "safety", "intent") and f["kind"] == "canon" and r.chance(0.1):
            row["r"].append("SENT_DASH")
    add_dups(fb, r)

    def render_sp(fb=fb, r=r):
        sh = {"numeric": [["item_id", "tolerance", "tests", "revision"]], "choice": [["revision", "item_id", "n_options"]],
              "text": [["item_id", "revision", "profile"]]}
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            b = f["b"]
            idv = v_id(f["key"], rules, "I")
            if b in ("arith", "code", "safety"):
                tol = "-" if b != "arith" else (r.choice(TOL_FORMS[f["v"]["tol"]]) if "TOL_FORM" in rules else f["v"]["tol"])
                tests = "-" if b != "code" else (f"{f['v']['tests']} tests" if "TESTS_TXT" in rules else f["v"]["tests"])
                sh["numeric"].append([idv, v_lb(tol, rules), tests, v_rev(f["rev"], rules) if "REV_TXT" in rules else f["rev"]])
            elif b in ("mcq", "intent", "pref"):
                n = "-" if b != "mcq" else (f"A-{'ABCDE'[f['v']['nopt'] - 1]}" if "NOPT_LET" in rules else ({4: "four", 5: "five"}[f["v"]["nopt"]] if "NOPT_WORD" in rules else f["v"]["nopt"]))
                if b == "intent":
                    n = 12
                sh["choice"].append([v_rev(f["rev"], rules) if "REV_TXT" in rules else f["rev"], v_lb(idv, rules), n])
            else:
                sh["text"].append([v_lb(idv, rules), v_rev(f["rev"], rules) if "REV_TXT" in rules else f["rev"], ("nfc-casefold" if b == "longctx" else "per-grader") + (" (legacy)" if "PROFILE" in rules else "")])
        return xlsx_bytes([(k_, v_) for k_, v_ in sh.items()])
    fb.render = render_sp
    out.append(fb)

    # ---------------- label_aliases.json ----------------
    name = "label_aliases.json"
    r = rngs(name)
    fb = FB(name, tests=["item_scores_intent", "metric_intent"])
    fb.R("RAW_EXACT", "T1", "Alias matching is exact on the NFC form of the raw label, including case and punctuation; there is no case folding.", "label_aliases.json" if False else POL, [POL, "results_fleet_a.log"], mode="ctx", bait=True)
    fb.R("REV", "T7", "When an alias appears in several entries, the entry with the highest revision wins.", SC, [SC, ER], mode="row")
    fb.R("VOID", "T6", "Alias entries listed in the errata registry void list are void.", ER, [ER, POL], mode="row")
    for c_, nm_ in sorted(V2NAME.items()):
        fb.R("V2_" + c_, "T17", f"Taxonomy v2 renames {c_} to {nm_}; certified intent values use v2 names.", POL, [POL, "item_registry.csv"], mode="ctx", cond=True)
    fb.R("KEYORDER", "T8", "Keys inside an entry can appear in any order.", SC, [SC, POL], mode="line", bait=True, fields=["raw"])
    fb.R("REV_PAD", "T4", "revision can be zero-padded as a string (\"03\").", SC, [SC, POL], mode="line", fields=["raw"], excl=("REV_TXT",))
    fb.R("AMBIG", "T17", "Some aliases resolve to different classes under v1 and v2; the version is the job's harness taxonomy.", POL, ["job_configs.toml", POL], mode="ctx", cond=True)
    fb.R("NFD", "T10", "Raw aliases can be stored in decomposed Unicode form; match on NFC.", POL, [POL, "intent_predictions.csv"], mode="line", fields=["raw"], ht=True)
    fb.R("DEPREC", "T14", "Entries marked deprecated_in v2 are still valid for v1 jobs.", POL, [POL, "job_configs.toml"], mode="ctx")
    fb.R("ESC", "T9", "Raw aliases may use JSON unicode escapes.", SC, [SC, POL], mode="line", fields=["raw"])
    fb.R("DUPROW", "T20", "An alias entry repeated verbatim is one entry.", POL, [POL, ER], mode="row", bait=True)
    fb.R("CLASSCASE", "T1", "Class names in entries can be upper-cased; class names are lower case.", POL, [POL, "item_registry.csv"], mode="line", fields=["cls"], ht=True)
    fb.R("SENT_NULL", "T5", "A v2 of null means the alias is unchanged in v2 (same class as v1, renamed if the class was renamed).", POL, [POL, "item_registry.csv"], mode="ctx")
    fb.R("B_PUNCT", "T20", "Aliases ending in ! or containing parentheses are real aliases, not markup.", POL, [POL, "intent_predictions.csv"], mode="line", bait=True, fields=["punct"], ht=True)
    fb.R("FK", "T13", "Entries whose class is not in the taxonomy are ignored.", POL, ["item_registry.csv", POL], mode="row")
    fb.R("REV_TXT", "T4", "revision can be a string with an r prefix.", SC, [SC, POL], mode="line", fields=["raw"])
    fb.R("ESC_SLASH", "T9", "Raw aliases containing / can be written with the JSON escape \\/.", SC, [SC, POL], mode="line", fields=["slash"])
    fb.R("CLASS_WS", "T1", "Class names can carry a trailing space.", POL, [POL, "item_registry.csv"], mode="line", fields=["cls"], excl=("CLASSCASE",))
    fb.R("NUMSTR", "T9", "Some entries carry the class index as a string field idx; it is informational.", SC, [SC, POL], mode="line", bait=True, fields=["raw"])
    W.alias_void = []
    for raw in sorted(W.aliases):
        c1, c2 = W.aliases[raw]
        rev = r.randint(1, 5)
        roll = r.rand()
        if roll < 0.08:
            fb.add({"raw_s": raw, "c1": r.choice(INTENT_CLASSES), "c2": r.choice(INTENT_CLASSES), "rev": rev - 1 if rev > 1 else 0, "kind": "older"}, ["REV"])
        elif roll < 0.11:
            fb.add({"raw_s": raw, "c1": r.choice(INTENT_CLASSES), "c2": r.choice(INTENT_CLASSES), "rev": rev + 1, "kind": "void"}, ["VOID"])
            W.errata_reg.append((name, raw, rev + 1))
        rs = []
        if c1 != c2:
            rs.append("AMBIG")
        if c2 in V2NAME:
            rs.append("V2_" + c2)
        sentnull = c1 == c2 and r.chance(0.2)
        if sentnull:
            rs.append("SENT_NULL")
        if r.chance(0.05):
            rs.append("DEPREC")
        if r.chance(0.04):
            rs.append("RAW_EXACT")
        fb.add({"raw_s": raw, "c1": c1, "c2": c2, "rev": rev, "kind": "canon", "null": sentnull}, rs)
        if r.chance(0.01):
            fb.add({"raw_s": raw + "~", "c1": "unknown_class", "c2": "unknown_class", "rev": rev, "kind": "fk"}, ["FK"])
    for row in fb.rows:
        f = row["f"]
        f.update({"raw": 1, "cls": 1, "punct": 1 if ("!" in f["raw_s"] or "(" in f["raw_s"]) else None, "slash": 1 if "/" in f["raw_s"] else None})
    add_dups(fb, r)

    def render_la(fb=fb):
        entries = []
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            raw = unicodedata.normalize("NFD", f["raw_s"]) if "NFD" in rules else f["raw_s"]
            c1 = f["c1"].upper() if "CLASSCASE" in rules else (f["c1"] + " " if "CLASS_WS" in rules else f["c1"])
            c2v = None if f.get("null") else v2(f["c2"]) if f["c2"] != "unknown_class" else "unknown_class"
            e = {"raw": raw, "v1": c1, "v2": c2v, "revision": v_rev(f["rev"], rules) if ("REV_TXT" in rules or "REV_PAD" in rules) else f["rev"]}
            if "KEYORDER" in rules:
                e = dict(reversed(list(e.items())))
            if "NUMSTR" in rules:
                e["idx"] = str(INTENT_CLASSES.index(f["c1"]) if f["c1"] in INTENT_CLASSES else -1)
            if "DEPREC" in rules:
                e["deprecated_in"] = "v2"
            entries.append((e, "ESC" in rules))
        parts = []
        for (e, esc), row in zip(entries, fb.rows):
            t_ = json.dumps(e, ensure_ascii=esc)
            if "ESC_SLASH" in row["r"]:
                t_ = t_.replace("/", "\\/")
            parts.append(t_)
        body = '{\n "taxonomy": {"v1": ' + json.dumps(INTENT_CLASSES) + ', "v2": ' + json.dumps([v2(c) for c in INTENT_CLASSES]) + '},\n "aliases": [\n  ' + ",\n  ".join(parts) + "\n ]\n}\n"
        return body.encode("utf-8")
    fb.render = render_la
    out.append(fb)
    return out

# ---------------------------------------------------------------------------------
# lineage, tags and the item-level decoys
# ---------------------------------------------------------------------------------
def build_lineage(W, rngs):
    out = []
    # ---------------- checkpoint_lineage.json ----------------
    name = "checkpoint_lineage.json"
    r = rngs(name)
    fb = FB(name, tests=["lineage", "job_dispositions", "item_scores_longctx"])
    kit_ids(fb, "id", "C", "Checkpoint id", name, ht=("CASE",))
    fb.R("PARENT_IDS", "T1", "Parent ids follow the same checkpoint id grammar and variants as checkpoint ids.", POL, [POL, "checkpoint_lineage_snapshot.json"], mode="line", fields=["par"])
    fb.R("REREG", "T7", "A checkpoint registered more than once keeps the entry with the latest registered_at.", SC, [SC, ER], mode="row")
    fb.R("CTX_K", "T2", "context_window can be written in K units (16K means 16384).", MD, [MD, "context_lengths.csv"], mode="line", fields=["ctx"])
    fb.R("FAM_ALIAS", "T17", "family can be written 7B, 13B, 34B, OSP-13 or heron-7b style; it maps to the model families of the policy.", POL, [POL, "model_tags.yaml"], mode="line", fields=["fam"])
    fb.R("TOK_FAM", "T17", "tokenizer names the context_lengths.csv column used for the checkpoint: hbpe or ospsp.", MD, ["context_lengths.csv", MD], mode="ctx", cond=True)
    fb.R("STEP_K", "T2", "step can be written in thousands with a k suffix (12.5k).", SC, [SC, "model_tags.yaml"], mode="line", fields=["step"])
    fb.R("EPOCH", "T3", "registered_at is ISO 8601 UTC or epoch seconds.", SC, [SC, "model_tags.yaml"], mode="line", fields=["ts"])
    fb.R("PARENT_NULL", "T5", "A parent of null or empty string marks the first checkpoint of a training run.", SC, [SC, "checkpoint_lineage_snapshot.json"], mode="ctx")
    fb.R("NO_EMA", "T13", "EMA checkpoints are not registered in checkpoint_lineage.json; they appear only in the lineage snapshot, whose EMA entries are authoritative.", POL, ["checkpoint_lineage_snapshot.json", POL], mode="ctx", via_rules=[g("checkpoint_lineage_snapshot.json", "EMA_KEEP")])
    fb.R("VOID", "T6", "Lineage entries listed in the errata registry void list are void.", ER, [ER, POL], mode="row")
    fb.R("CERT_CK", "T22", "A checkpoint is the certified checkpoint of an alias only through an approved tag event; lineage alone certifies nothing.", POL, ["model_tags.yaml", MBOX], mode="ctx", cond=True)
    fb.R("B_HEX", "T20", "Lower-case hex checkpoint ids are already canonical.", POL, [POL, "model_tags.yaml"], mode="line", bait=True, fields=["id"], ht=True)
    fb.R("DUPROW", "T20", "An entry repeated verbatim is one entry.", POL, [POL, ER], mode="row", bait=True)
    fb.R("RUN_WS", "T9", "Run names can carry trailing spaces.", SC, [SC, "checkpoint_lineage_snapshot.json"], mode="line", fields=["id"])
    fb.R("CTX_STR", "T4", "context_window can be a string of digits.", MD, [MD, "context_lengths.csv"], mode="line", fields=["ctx"])
    certs = {W.certified[m]["checkpoint"] for m in MODELS}
    fam_label = {"7b": "7b", "13b": "13b", "34b": "34b", "osp13": "osp13"}
    for cid in W.ckpt_order:
        c = W.ckpts[cid]
        roll = r.rand()
        if roll < 0.06:
            fb.add({"c": c, "ctx": CTX_WINDOW[c["family"]] // 2, "reg": c["created_at"] - 3600, "kind": "older"}, ["REREG"])
        elif roll < 0.08:
            fb.add({"c": c, "ctx": CTX_WINDOW[c["family"]] * 2, "reg": c["created_at"] + 7200, "kind": "void"}, ["VOID"])
            W.errata_reg.append((name, cid, iso(c["created_at"] + 7200)))
        rs = []
        if c["parent"] is None:
            rs.append("PARENT_NULL")
        if cid in certs:
            rs.append("CERT_CK")
        if c["family"] in ("34b",) and r.chance(0.1):
            rs.append("NO_EMA")
        if r.chance(0.04):
            rs.append("TOK_FAM")
        fb.add({"c": c, "ctx": CTX_WINDOW[c["family"]], "reg": c["created_at"], "kind": "canon"}, rs)
    for row in fb.rows:
        row["f"].update({"id": 1, "par": 1 if row["f"]["c"]["parent"] else None, "ctx": row["f"]["ctx"], "fam": 1, "step": 1, "ts": 1})
        row["f"]["ctxf"] = 1
    for row in fb.rows:
        row["f"]["ctx_v"] = row["f"]["ctx"]
        row["f"]["ctx"] = 1
    add_dups(fb, r)

    def render_cl(fb=fb, r=r):
        ents = []
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            c = f["c"]
            fam = c["family"]
            famv = {"7b": "7B", "13b": "13B", "34b": "34B", "osp13": "OSP-13"}[fam] if "FAM_ALIAS" in rules else fam
            ctx = f"{f['ctx_v'] // 1024}K" if "CTX_K" in rules else (str(f["ctx_v"]) if "CTX_STR" in rules else f["ctx_v"])
            step = f"{c['step'] / 1000:g}k" if "STEP_K" in rules else c["step"]
            par = c["parent"]
            if par is None:
                parv = r.choice([None, ""])
            else:
                parv = v_id(par, [x.replace("PARENT_IDS", "C_CASE") for x in rules if x == "PARENT_IDS"], "C") if "PARENT_IDS" in rules else par
            e = {"id": v_id(c["id"], rules, "C"), "run": c["run"] + ("  " if "RUN_WS" in rules else ""), "step": step, "parent": parv, "family": famv,
                 "tokenizer": TOKENIZER[fam], "context_window": ctx,
                 "registered_at": f["reg"] if "EPOCH" in rules else iso(f["reg"])}
            ents.append(json.dumps(e, ensure_ascii=False))
        return ('{\n "schema": "heron.lineage/3",\n "checkpoints": [\n  ' + ",\n  ".join(ents) + "\n ]\n}\n").encode("utf-8")
    fb.render = render_cl
    out.append(fb)

    # ---------------- checkpoint_lineage_snapshot.json (decoy) ----------------
    name = "checkpoint_lineage_snapshot.json"
    r = rngs(name)
    fb = FB(name, decoy=True, tests=["lineage", "job_dispositions"])
    kit_ids(fb, "id", "C", "Checkpoint id", "checkpoint_lineage.json", ht=("CASE",))
    for code, fam, desc, d in [
        ("SNAP_NEWER", "T7", "The snapshot is dated after checkpoint_lineage.json; for non-EMA checkpoints the registry entry still wins.", "pull"),
        ("SNAP_AGREE", "T16", "Snapshot fields agree with the registry for most checkpoints and differ for some; the registry wins for every non-EMA field.", "pull"),
        ("SNAP_CTX", "T16", "Snapshot context windows reflect a planned extension that was never deployed; they are not used.", "pull"),
        ("SNAP_TAGS", "T22", "The snapshot lists alias pointers as of its own date; aliases are decided only by approved tag events.", "pull"),
        ("SNAP_FULL", "T16", "The snapshot carries more columns (eval_ready, owner); extra columns do not make it authoritative.", "pull"),
        ("EMA_KEEP", "T13", "Entries with ema true and an ema_of parent are the only registration of EMA checkpoints and are authoritative for them.", "push"),
        ("EMA_PARENT", "T17", "An EMA checkpoint takes family, tokenizer and context window from its ema_of parent in checkpoint_lineage.json.", "push"),
        ("SNAP_VOID", "T6", "Snapshot entries flagged withdrawn are void.", "pull"),
        ("SNAP_DATE", "T3", "snapshot_at values are epoch milliseconds.", "pull"),
        ("SNAP_STEP", "T2", "Snapshot steps are in thousands.", "pull"),
        ("SNAP_FAM", "T17", "Snapshot family names use marketing names (Heron Small, Heron Medium, Heron Large, Osprey).", "pull"),
        ("SNAP_FK", "T13", "Snapshot entries whose id is not in the registry and that are not EMA entries are scratch checkpoints and are ignored.", "pull"),
        ("SNAP_DUP", "T20", "An entry repeated verbatim is one entry.", "pull"),
        ("SNAP_NULL", "T5", "ema_of null on a non-EMA entry is expected.", "pull"),
        ("SNAP_ORDER", "T8", "Older snapshot entries use the key ckpt instead of id.", "pull"),
        ("SNAP_EMA_BAIT", "T20", "EMA entries look like duplicates of their parents (same step); they are distinct checkpoints.", "push"),
        ("SNAP_WS", "T9", "Run names can contain spaces.", "pull"),
        ("SNAP_CERT", "T15", "The snapshot marks some checkpoints best; best is a dashboard label with no certification meaning.", "pull"),
        ("SNAP_ROUND", "T12", "Snapshot loss values are rounded and are not used.", "pull"),
        ("SNAP_TZ", "T3", "Snapshot created times are in the training cluster's local time (UTC-05:00).", "pull"),
        ("SNAP_LOCK", "T14", "A footnote in the snapshot header limits its validity to EMA registrations.", "push"),
        ("SNAP_ID2", "T1", "Some EMA ids are written with an ema/ prefix that is not part of the id.", "push"),
        ("SNAP_PARENT", "T13", "Snapshot entries carry no parent field; lineage parents come from checkpoint_lineage.json.", "pull"),
        ("SNAP_RUNCASE", "T1", "Snapshot run names can be upper-cased.", "pull"),
        ("SNAP_OWNER", "T16", "The owner field says training-infra for every entry; ownership is not authority.", "pull"),
        ("SNAP_READY", "T15", "eval_ready is true for every entry; it is a dashboard flag with no certification meaning.", "pull"),
        ("SNAP_KEYORDER", "T8", "Key order differs between entries.", "pull"),
    ]:
        mode = "line" if code in ("SNAP_DATE", "SNAP_STEP", "SNAP_FAM", "SNAP_ORDER", "SNAP_ID2", "SNAP_RUNCASE", "SNAP_KEYORDER") else "row"
        fb.R(code, fam, desc, POL, [POL, "checkpoint_lineage.json"], mode=mode, direction=d, fields=["id"] if mode == "line" else None,
             bait=code in ("SNAP_DUP", "SNAP_EMA_BAIT", "SNAP_NULL"), ht=code in ("SNAP_DATE", "SNAP_NULL"))
    fb.rules["SNAP_ID2"]["fields"] = ["ema"]
    for c_, v_ in (("SNAP_DATE", "source_conventions.md"), ("SNAP_TZ", "source_conventions.md"), ("SNAP_DUP", "errata_register.docx")):
        fb.rules[c_]["via"].append(v_)
    fb.rules["SNAP_NULL"]["mode"] = "line"
    fb.rules["SNAP_NULL"]["fields"] = ["nonema"]
    for cid in W.ckpt_order:
        if not r.chance(0.96):
            continue
        c = W.ckpts[cid]
        rs = [r.choice(["SNAP_NEWER", "SNAP_AGREE", "SNAP_FULL", "SNAP_TAGS", "SNAP_WS", "SNAP_PARENT", "SNAP_OWNER", "SNAP_READY"])]
        ctx = CTX_WINDOW[c["family"]]
        if r.chance(0.05):
            ctx = ctx * 2
            rs.append("SNAP_CTX")
        if r.chance(0.02):
            rs.append("SNAP_VOID")
        if r.chance(0.01):
            rs.append("SNAP_CERT")
        fb.add({"c": c, "ctx": ctx, "id": 1, "nonema": 1, "ema": None}, rs)
    for eid, par in sorted(W.ema.items()):
        c = W.ckpts[eid]
        fb.add({"c": c, "ctx": None, "id": 1, "ema": 1, "nonema": None}, ["EMA_KEEP", "EMA_PARENT"] + (["SNAP_EMA_BAIT"] if r.chance(0.3) else []) + (["SNAP_LOCK"] if r.chance(0.4) else []))
    for i in range(max(20, len(fb.rows) // 70)):
        fb.add({"c": {"id": "ck-" + r.hexid(10), "run": "scratch", "family": "7b", "step": 500, "parent": None, "created_at": T(2025, 8, 1), "ema": False, "ema_of": None},
                "ctx": 8192, "id": 1, "nonema": 1, "ema": None}, ["SNAP_FK"])
    fb.rows.sort(key=lambda row: row["f"]["c"]["id"])
    for i in range(len(fb.rows) // 9):
        j = r.below(len(fb.rows))
        fb.rows.insert(j + 1, {"f": dict(fb.rows[j]["f"]), "r": [c for c in fb.rows[j]["r"] if fb.rules[c]["mode"] != "line"] + ["SNAP_DUP"], "k": None, "c": {}})

    def render_snap(fb=fb, r=r):
        ents = []
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            c = f["c"]
            key = "ckpt" if "SNAP_ORDER" in rules else "id"
            idv = v_id(c["id"], rules, "C")
            if "SNAP_ID2" in rules:
                idv = "ema/" + idv
            runv = c["run"].replace("-", " ") if "SNAP_WS" in rules else c["run"]
            if "SNAP_RUNCASE" in rules:
                runv = runv.upper()
            e = {key: idv, "run": runv,
                 "step": c["step"] / 1000 if "SNAP_STEP" in rules else c["step"],
                 "family": {"7b": "Heron Small", "13b": "Heron Medium", "34b": "Heron Large", "osp13": "Osprey"}[c["family"]] if "SNAP_FAM" in rules else c["family"],
                 "context_window": f["ctx"], "ema": bool(c["ema"]), "ema_of": c["ema_of"],
                 "snapshot_at": T(2025, 9, 28) * 1000 if "SNAP_DATE" in rules else "2025-09-28T00:00:00Z",
                 "eval_ready": True, "owner": "training-infra"}
            if "SNAP_VOID" in rules:
                e["withdrawn"] = True
            if "SNAP_KEYORDER" in rules:
                e = dict(reversed(list(e.items())))
            if "SNAP_CERT" in rules:
                e["best"] = True
            ents.append(json.dumps(e, ensure_ascii=False))
        return ('{\n "snapshot": "lineage snapshot 2025-09-28 (valid for EMA registrations only)",\n "checkpoints": [\n  ' + ",\n  ".join(ents) + "\n ]\n}\n").encode("utf-8")
    fb.render = render_snap
    out.append(fb)

    # ---------------- model_tags.yaml ----------------
    name = "model_tags.yaml"
    r = rngs(name)
    fb = FB(name, tests=["lineage", "job_dispositions"])
    kit_ids(fb, "ck", "C", "Checkpoint id", "checkpoint_lineage.json")
    kit_ids(fb, "tk", "K", "Ticket id", MBOX, ht=("CASE",))
    fb.R("DEFERRED", "T22", "A certification tag event takes effect at the Date of the approval message for its ticket in the operations mailbox; rejected tickets and approvals after the cutoff have no effect.",
         POL, [MBOX, POL], mode="row", via_rules=[g(MBOX, "TZ_HDR"), g(MBOX, "K_CASE")])
    fb.R("ROLLBACK", "T7", "A rollback event points the tag back to an earlier checkpoint; it is a tag event like a promotion and needs its own approval.", POL, [POL, MBOX], mode="row")
    fb.R("LATEST", "T7", "Among effective events of a tag the one with the latest effective time wins.", POL, [POL, MBOX], mode="row")
    fb.R("AT_LOCAL", "T3", "Event at values carry a numeric offset; the registry ran on UTC+05:30 for part of the quarter.", SC, [SC, MBOX], mode="line", fields=["ts"])
    fb.R("NIGHTLY", "T14", "nightly-* tags are not certification aliases and are out of scope, even when the tag name contains a model alias.", POL, [POL, "checkpoint_lineage.json"], mode="row")
    fb.R("TAG_CASE", "T1", "Tag names can be written in any case.", POL, [POL, MBOX], mode="line", fields=["tag"])
    fb.R("CUTOFF_EQ", "T11", "An approval dated exactly at the cutoff counts.", POL, [MBOX, POL], mode="row", bait=True)
    fb.R("RETIRE", "T6", "A retire action removes a nightly tag; it never applies to certification aliases.", POL, [POL, "checkpoint_lineage.json"], mode="row")
    fb.R("EMA_TAG", "T13", "The -ema alias points to EMA checkpoints registered only in the lineage snapshot.", POL, ["checkpoint_lineage_snapshot.json", POL], mode="row")
    fb.R("QUOTE", "T9", "Tag names that would parse as YAML scalars of another type are quoted.", SC, [SC, POL], mode="line", bait=True, fields=["tag"], ht=True)
    fb.R("NOAPPROVAL", "T22", "A promotion with no approval message at all has no effect.", POL, [MBOX, POL], mode="row")
    fb.R("BASE_TAG", "T17", "The baseline alias osprey-13b-prod follows the same tag rules as candidate aliases.", POL, [POL, "baseline_reference.csv"], mode="row")
    W.reg_tz = {}
    evs = [(e, "cert") for e in W.promos] + [(e, "nightly") for e in W.tag_noise]
    evs.sort(key=lambda x: (x[0]["at"], x[0]["ticket"]))
    for e, kind in evs:
        rs = []
        if kind == "nightly":
            if any(m in e["tag"] for m in MODELS):
                rs.append("NIGHTLY")
            if e["action"] == "retire":
                rs.append("RETIRE")
        else:
            rs.append("DEFERRED")
            if e["action"] == "rollback":
                rs.append("ROLLBACK")
            if e["approval"] is None:
                rs.append("NOAPPROVAL")
            elif e["approval"][1] == CUTOFF:
                rs.append("CUTOFF_EQ")
            if e["tag"].endswith("-ema"):
                rs.append("EMA_TAG")
            if e["tag"] == BASELINE:
                rs.append("BASE_TAG")
            if e["approval"] and e["approval"][0] == "APPROVED" and e["ckpt"] == W.certified[e["tag"]]["checkpoint"]:
                rs.append("LATEST")
        fb.add({"e": e, "ck": 1, "tk": 1, "ts": 1, "tag": 1, "kind": kind}, rs)

    def render_tags(fb=fb, r=r):
        L = ["# Model registry tag log, Q3 2025 export", "events:"]
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            e = f["e"]
            tag = e["tag"].upper() if "TAG_CASE" in rules else e["tag"]
            tz = "Asia/Kolkata" if "AT_LOCAL" in rules else "UTC"
            off = TZ_OFFSET[tz]
            at = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(e["at"] + off)) + ("+05:30" if off else "Z")
            tk = v_id(e["ticket"], rules, "K") if e["ticket"].startswith("CHG") else e["ticket"]
            L.append(f"  - tag: {y(tag) if 'QUOTE' in rules else tag}")
            L.append(f"    checkpoint: {v_id(e['ckpt'], rules, 'C')}")
            L.append(f"    action: {e['action']}")
            L.append(f"    at: '{at}'")
            L.append(f"    ticket: {y(tk)}")
        return ("\n".join(L) + "\n").encode("utf-8")
    fb.render = render_tags
    out.append(fb)

    # ---------------- gold_labels_corrected.csv (decoy) ----------------
    name = "gold_labels_corrected.csv"
    r = rngs(name)
    fb = FB(name, decoy=True, tests=["item_scores_arith", "item_scores_mcq", "item_eligibility"])
    kit_ids(fb, "id", "I", "Item id", "item_registry.csv", ht=("CASE",))
    W.dispute = {}
    for code, fam, desc, d, mode in [
        ("GC_NEWER", "T7", "corrected_at dates are later than the gold file revisions; later does not make a correction authoritative.", "pull", "row"),
        ("GC_AGREE", "T16", "Corrected gold agrees with gold_labels.tsv on most items and differs on the rest; only upheld grader errata change a gold value.", "pull", "row"),
        ("GC_FINAL", "T16", "Every row says status FINAL; the corrections were never upheld by the grader errata process.", "pull", "row"),
        ("GC_FULL", "T16", "The file covers every item including preference items; coverage does not make it authoritative.", "pull", "row"),
        ("GC_FIX", "T15", "Corrections fix some values that look wrong but are valid per the scoring parameters (tolerance-equivalent answers).", "pull", "row"),
        ("TICKET_MAP", "T13", "dispute_ticket is the only crosswalk from dispute tickets (DSP-nnnnn) to item ids; grader errata name tickets, not items.", "push", "row"),
        ("TICKET_CASE", "T1", "Dispute tickets can be written in lower case or without zero padding.", "push", "line"),
        ("TICKET_DUP", "T7", "A ticket listed twice maps to the item of the row with the later corrected_at.", "push", "row"),
        ("TICKET_VOID", "T6", "Rows whose ticket is marked void in the errata register do not map.", "push", "row"),
        ("GC_SERIAL", "T3", "corrected_at can be a spreadsheet serial date.", "pull", "line"),
        ("GC_LOC", "T4", "Numeric corrections from the Munich desk use a comma decimal mark.", "pull", "line"),
        ("GC_SCALE", "T2", "Safety corrections are written as percentages.", "pull", "row"),
        ("GC_ROUND", "T12", "Corrections round numeric gold to whole numbers.", "pull", "row"),
        ("GC_EMBED", "T9", "Text corrections are CSV-quoted.", "pull", "line"),
        ("GC_BOM", "T10", "The file starts with a byte order mark.", "pull", "row"),
        ("GC_HDR", "T8", "A second header renames gold_corrected to answer_fixed.", "pull", "pos"),
        ("GC_FK", "T13", "Some rows name item ids that are not registered.", "pull", "row"),
        ("GC_NULL", "T5", "An empty correction means no change was proposed.", "pull", "line"),
        ("GC_TAXO", "T17", "Intent corrections use taxonomy v2 names whatever the item's taxonomy.", "pull", "row"),
        ("GC_BAIT", "T20", "A correction equal to the current gold is a confirmation and changes nothing.", "pull", "row"),
        ("GC_SCOPE", "T14", "The header note limits the file to proposals under discussion.", "pull", "row"),
        ("GC_BOUND", "T11", "Corrections dated after the cutoff are out of the close.", "pull", "row"),
        ("GC_PREC", "T21", "Where a ticket appears in both this file and the errata, the errata decide the value and this file decides only the item.", "push", "row"),
        ("GC_DEFER", "T22", "A ticket maps to an item only for errata entries upheld after the ticket's corrected_at.", "push", "row"),
        ("GC_OSC", "T18", "Trusting this file for values breaks the errata reconciliation; ignoring it entirely loses the ticket map; the errata rule takes values from the errata and items from this file.", "push", "row"),
        ("GC_EQ", "T19", "Corrected values are internally consistent with the preliminary scorecard; that agreement is not evidence.", "pull", "row"),
        ("GC_DUP", "T20", "A row repeated verbatim is one row.", "pull", "row"),
    ]:
        fb.R(code, fam, desc, POL, [POL, "gold_labels.tsv"] if code != "TICKET_MAP" else ["grader_errata.xml", POL], mode=mode, direction=d,
             fields=["id"] if mode == "line" else None, bait=code in ("GC_BAIT", "GC_FIX", "GC_DUP"), ht=code in ("GC_SERIAL", "GC_BOM"))
    for c_, v_ in (("GC_SERIAL", "source_conventions.md"), ("TICKET_VOID", "errata_register.docx"), ("GC_TAXO", "label_aliases.json"), ("GC_SCALE", "metric_definitions.pdf")):
        if c_ in fb.rules:
            fb.rules[c_]["via"].append(v_)
    used = set()
    W.err_kind = {}
    for iid in sorted(W.items):
        if W.items[iid]["bench"] == "pref":
            W.err_kind[iid] = None
        elif iid in W.gold_err:
            W.err_kind[iid] = "upheld_w" if r.chance(0.3) else "upheld"
        else:
            W.err_kind[iid] = r.weighted([("confirmed", 70), ("withdrawn", 10), ("after", 8), ("pair", 7), ("none", 5)])
    for iid in sorted(W.items):
        while True:
            t = f"DSP-{r.randint(10000, 99999):05d}"
            if t not in used:
                used.add(t)
                break
        W.dispute[iid] = t
        rs = [r.choice(["GC_NEWER", "GC_AGREE", "GC_FINAL", "GC_FULL", "GC_SCOPE"])]
        if W.err_kind[iid] in ("upheld", "upheld_w"):
            rs.append("TICKET_MAP")
        wrong = r.chance(0.06)
        if wrong:
            rs.append(r.choice(["GC_FIX", "GC_ROUND", "GC_TAXO", "GC_SCALE", "GC_EQ"]))
        if r.chance(0.03):
            rs.append("GC_BAIT")
        if r.chance(0.02):
            rs.append("GC_BOUND")
        if iid in W.gold_err:
            rs += ["GC_PREC", "GC_DEFER"] if r.chance(0.5) else ["GC_OSC"]
        fb.add({"iid": iid, "wrong": wrong, "id": 1}, rs)
    for i in range(len(fb.rows) // 80):
        fb.add({"iid": fake_item(r, r.choice(sorted(W.items))), "wrong": True, "id": 1}, ["GC_FK"])
    for i in range(len(fb.rows) // 9):
        j = r.below(len(fb.rows))
        fb.rows.insert(j + 1, {"f": dict(fb.rows[j]["f"]), "r": [c for c in fb.rows[j]["r"] if fb.rules[c]["mode"] != "line"] + ["GC_DUP"], "k": None, "c": {}})
    fb.rows[0]["r"].append("GC_BOM")

    def render_gc(fb=fb, r=r):
        rows = [["item_id", "gold_corrected", "dispute_ticket", "corrected_at", "status"]]
        cur = "A"
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            if "GC_HDR" in rules and cur == "A":
                rows.append(["item_id", "answer_fixed", "dispute_ticket", "corrected_at", "status"])
                cur = "B"
            elif "GC_HDR" not in rules and cur == "B":
                rows.append(["item_id", "gold_corrected", "dispute_ticket", "corrected_at", "status"])
                cur = "A"
            iid = f["iid"]
            it = W.items.get(iid)
            if it:
                gv = {"arith": lambda: format(it["gold"], "f"), "code": lambda: str(it["tests"]), "intent": lambda: v2(it["gold"]),
                      "safety": lambda: str(it["gold"]), "mcq": lambda: it["gold"], "pref": lambda: "-"}.get(it["bench"], lambda: it.get("gold", "-"))()
                if f["wrong"]:
                    gv = gv + "0" if it["bench"] != "intent" else "complaint"
                tk = W.dispute[iid]
            else:
                gv, tk = "0", f"DSP-{r.randint(10000, 99999)}"
            if "GC_NULL" in rules:
                gv = ""
            tkv = tk.lower() if "TICKET_CASE" in rules else tk
            t = T(2025, 9, 1) + r.randint(0, 40) * 86400
            ts = repr(excel_serial(t)) if "GC_SERIAL" in rules else iso(t)
            rows.append([v_id(iid, rules, "I"), gv, tkv, ts, "FINAL"])
        return csv_bytes(rows, bom=True)
    fb.render = render_gc
    out.append(fb)
    return out

# ---------------------------------------------------------------------------------
# host-week files, job files, errata, overrides, remaining decoys
# ---------------------------------------------------------------------------------
def build_hostjob(W, rngs):
    out = []
    hosts = W.hosts
    # ---------------- host_inventory.ini ----------------
    name = INV
    r = rngs(name)
    fb = FB(name, tests=["job_dispositions", "item_scores_arith", "item_scores_safety"])
    kit_ids(fb, "h", "H", "Host name", name, ht=("CASE",))
    fb.R("SUPERSEDE", "T7", "A host-week can be listed more than once; the entry in the later-numbered snapshot section wins.", SC, [SC, ER], mode="row")
    fb.R("FLEET_ALIAS", "T17", "Fleet codes can be long names (fleet-a, prod-b, stage); stage and staging both mean the staging fleet s.", POL, [POL, "scorecard_prelim.xlsx"], mode="line", fields=["fl"])
    fb.R("TZ_ALIAS", "T3", "Zones can be written as abbreviations: CEST is Europe/Berlin, CDT is America/Chicago, IST is Asia/Kolkata, BRT is America/Sao_Paulo.", SC, [SC, "results_fleet_a.log"], mode="line", fields=["tz"])
    fb.R("LOC_ALIAS", "T4", "Locales can be written with - instead of _ and in any case.", SC, [SC, "results_fleet_b.log"], mode="line", fields=["loc"])
    fb.R("SCALE_ALIAS", "T2", "scale is unit or pct; 1 means unit and 100 means pct.", SC, [SC, "results_fleet_b.log"], mode="line", fields=["sc"])
    fb.R("WEEKFMT", "T3", "The week key is ISO year-week (2025-W31); some entries write the Monday date instead.", SC, [SC, CLK], mode="line", fields=["wkf"])
    fb.R("STAGING_WEEK", "T17", "A host whose week entry says fleet s is a staging host for every job submitted that week.", POL, [POL, "harness_events.log"], mode="ctx", cond=True)
    fb.R("VOID", "T6", "Inventory entries listed in the errata registry void list are void.", ER, [ER, POL], mode="row")
    fb.R("INLINE_COMMENT", "T9", "A ; after a value starts an inline comment.", SC, [SC, POL], mode="line", bait=True, fields=["h"], ht=True)
    fb.R("DUPKEY", "T20", "An entry repeated verbatim inside one snapshot section is one entry.", POL, [POL, ER], mode="row", bait=True)
    fb.R("REIMAGE", "T19", "Hosts re-imaged mid-quarter change zone between weeks; each week uses its own entry.", SC, [SC, CLK], mode="ctx", cond=True)
    fb.R("TRAIL_WS", "T9", "Values can carry trailing spaces before the next separator.", SC, [SC, POL], mode="line", fields=["h"])
    fb.R("KEY_ORDER", "T8", "Keys inside an entry can appear in any order.", SC, [SC, POL], mode="line", fields=["h"])
    fb.R("EXTRA_KEY", "T20", "Unknown keys (rack=...) are ignored.", SC, [SC, POL], mode="line", bait=True, fields=["h"])
    fb.R("DST_BAIT", "T15", "Europe/Berlin and America/Chicago are on summer time for the whole window; there is no transition inside it.", SC, [SC, "maintenance_windows.ics"], mode="ctx", bait=True)
    W.inv_void = []
    for h in hosts:
        for wk in WEEKS:
            hw = W.hw[(h, wk)]
            roll = r.rand()
            if roll < 0.07:
                fb.add({"h": h, "wk": wk, "hw": dict(hw, tz=r.choice(list(TZ_OFFSET)), locale=r.choice(LOCALES)), "snap": 1, "kind": "older"}, ["SUPERSEDE"])
            elif roll < 0.09:
                fb.add({"h": h, "wk": wk, "hw": dict(hw, fleet="s" if hw["fleet"] != "s" else "a"), "snap": 3, "kind": "void"}, ["VOID"])
                W.errata_reg.append((name, f"{h}@2025-W{wk}", "snapshot-3"))
            rs = []
            if hw["fleet"] == "s":
                rs.append("STAGING_WEEK")
            if wk > WEEKS[0] and W.hw[(h, wk - 1)]["tz"] != hw["tz"]:
                rs.append("REIMAGE")
            if hw["tz"] in ("Europe/Berlin", "America/Chicago") and r.chance(0.05):
                rs.append("DST_BAIT")
            fb.add({"h": h, "wk": wk, "hw": hw, "snap": 2, "kind": "canon"}, rs)
            if r.chance(0.01):
                fb.add({"h": h, "wk": wk, "hw": hw, "snap": 2, "kind": "dup"}, ["DUPKEY"])
    for row in fb.rows:
        row["f"].update({"fl": 1, "tz": 1 if row["f"]["hw"]["tz"] != "UTC" else None, "loc": 1, "sc": 1, "wkf": 1})

    def render_inv(fb=fb, r=r):
        secs = {1: [], 2: [], 3: []}
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            hw = f["hw"]
            fl = {"a": "fleet-a", "b": "prod-b", "c": "fleet-c", "d": "fleet-d", "j": "fleet-j", "s": r.choice(["stage", "staging"])}[hw["fleet"]] if "FLEET_ALIAS" in rules else hw["fleet"]
            tz = {"Europe/Berlin": "CEST", "America/Chicago": "CDT", "Asia/Kolkata": "IST", "America/Sao_Paulo": "BRT", "UTC": "UTC"}[hw["tz"]] if "TZ_ALIAS" in rules else hw["tz"]
            loc = hw["locale"].replace("_", "-").lower() if "LOC_ALIAS" in rules else hw["locale"]
            sc = ("100" if hw["scale"] == 100 else "1") if "SCALE_ALIAS" in rules else ("pct" if hw["scale"] == 100 else "unit")
            wk = time.strftime("%Y-%m-%d", time.gmtime(T(2025, 6, 30) + (f["wk"] - 27) * 7 * 86400)) if "WEEKFMT" in rules else f"2025-W{f['wk']:02d}"
            parts = [f"fleet={fl}", f"tz={tz}", f"locale={loc}", f"scale={sc}"]
            if "EXTRA_KEY" in rules:
                parts.append(f"rack=r{int(f['h'][-3:]) % 40}")
            if "KEY_ORDER" in rules:
                parts = parts[::-1]
            sep = " ; " if "TRAIL_WS" in rules else "; "
            line = f"{v_id(f['h'], rules, 'H')}@{wk} = " + sep.join(parts)
            if "INLINE_COMMENT" in rules:
                line += " ; checked"
            secs[f["snap"]].append(line)
        L = ["# Host inventory snapshots, Q3 2025. Later snapshot sections override earlier ones."]
        for s in (1, 2, 3):
            L.append(f"[snapshot-{s}]")
            L += secs[s]
        return ("\n".join(L) + "\n").encode("utf-8")
    fb.render = render_inv
    out.append(fb)

    # ---------------- clock_offsets.txt ----------------
    name = CLK
    r = rngs(name)
    fb = FB(name, tests=["job_dispositions", "item_scores_mcq"])
    kit_ids(fb, "h", "H", "Host name", INV, ht=("CASE",))
    fb.R("SUPERSEDE", "T7", "A later measurement line for the same host-week (higher seq) replaces earlier ones.", SC, [SC, ER], mode="row")
    fb.R("SIGN", "T3", "OFFSET_MS is host clock minus true time; subtract it from host-written timestamps.", SC, [SC, "results_fleet_a.log"], mode="ctx")
    fb.R("UNIT_S", "T2", "Lines with unit S give the offset in seconds with three decimals.", SC, [SC, "harness_events.log"], mode="line", fields=["off"])
    fb.R("NEG_PAREN", "T4", "Negative offsets can be written in parentheses.", SC, [SC, "harness_events.log"], mode="line", fields=["neg"])
    fb.R("BIG", "T15", "Offsets of several minutes are real (drifting hosts) and are applied.", SC, [SC, "harness_events.log"], mode="ctx", bait=True)
    fb.R("ZERO", "T5", "Host-weeks with no line have offset 0; a line with offset ------ is a failed measurement and also means 0.", SC, [SC, INV], mode="row")
    fb.R("LAYOUT", "T8", "A #COLUMNS record changes the column order for the lines after it.", SC, [SC, INV], mode="pos")
    fb.R("VOID", "T6", "Clock lines listed in the errata registry void list are void.", ER, [ER, POL], mode="row")
    fb.R("B_SMALL", "T20", "Offsets under one second still apply; they can move a row across a seal or window boundary.", SC, [SC, MBOX], mode="line", bait=True, fields=["small"], ht=True)
    fb.R("WEEK", "T3", "The week column is the ISO week number in 2025; some lines write it as W31.", SC, [SC, INV], mode="line", fields=["h"], ht=True)
    fb.R("SEQ_PAD", "T4", "SEQ can be zero-padded.", SC, [SC, INV], mode="line", fields=["h"])
    fb.R("OFFSET_PLUS", "T4", "Positive offsets can carry an explicit + sign.", SC, [SC, INV], mode="line", fields=["pos"])
    fb.R("WEEK_ISO", "T3", "The week can be written 2025-W31.", SC, [SC, INV], mode="line", fields=["h"], excl=("WEEK",))
    fb.R("UNIT_CASE", "T1", "UNIT can be lower case (ms, s).", SC, [SC, INV], mode="line", fields=["off"])
    fb.R("TRAIL_WS", "T9", "Lines can end with trailing spaces.", SC, [SC, INV], mode="line", fields=["h"])
    seq = 0
    for h in hosts:
        for wk in WEEKS:
            off = W.hw[(h, wk)]["offset_ms"]
            seq += r.randint(1, 3)
            if r.chance(0.08):
                fb.add({"h": h, "wk": wk, "off": off + r.randint(-90000, 90000), "seq": seq, "kind": "older"}, ["SUPERSEDE"])
                seq += 1
            rs = []
            if off and abs(off) >= 120000:
                rs.append("BIG")
            if off:
                rs.append("SIGN") if r.chance(0.2) else None
            if off == 0 and r.chance(0.15):
                fb.add({"h": h, "wk": wk, "off": None, "seq": seq, "kind": "fail"}, ["ZERO"])
                continue
            fb.add({"h": h, "wk": wk, "off": off, "seq": seq, "kind": "canon"}, rs)
            if r.chance(0.01):
                seq += 1
                fb.add({"h": h, "wk": wk, "off": off + 777000, "seq": seq, "kind": "void"}, ["VOID"])
                W.errata_reg.append((name, f"{h}@{wk}", f"seq-{seq}"))
    for row in fb.rows:
        o = row["f"]["off"]
        row["f"].update({"neg": 1 if (o is not None and o < 0) else None, "small": 1 if (o is not None and 0 < abs(o) < 1000) else None, "pos": 1 if (o is not None and o > 0) else None,
                         "offv": o})
        row["f"]["off"] = 1 if o is not None else None

    def render_clk(fb=fb):
        L = ["#COLUMNS SEQ HOST WEEK OFFSET UNIT"]
        cur = "A"
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            lay = "B" if "LAYOUT" in rules else "A"
            if lay != cur:
                L.append("#COLUMNS HOST WEEK SEQ UNIT OFFSET" if lay == "B" else "#COLUMNS SEQ HOST WEEK OFFSET UNIT")
                cur = lay
            o = f["offv"]
            if o is None:
                ov, unit = "------", "MS"
            elif "UNIT_S" in rules:
                ov, unit = f"{abs(o) / 1000:.3f}", "S"
                ov = (f"({ov})" if "NEG_PAREN" in rules else "-" + ov) if o < 0 else ov
            else:
                ov, unit = str(abs(o)), "MS"
                ov = (f"({ov})" if "NEG_PAREN" in rules else "-" + ov) if o < 0 else ov
            h = v_id(f["h"], rules, "H")
            wk = f"W{f['wk']}" if "WEEK" in rules else (f"2025-W{f['wk']}" if "WEEK_ISO" in rules else str(f["wk"]))
            if "OFFSET_PLUS" in rules and o is not None and o > 0:
                ov = "+" + ov
            seq = f"{f['seq']:08d}" if "SEQ_PAD" in rules else str(f["seq"])
            if "UNIT_CASE" in rules:
                unit = unit.lower()
            tail = "   " if "TRAIL_WS" in rules else ""
            if lay == "A":
                L.append(f"{seq:>8} {h:<12}{wk:>8} {ov:>12} {unit}{tail}")
            else:
                L.append(f"{h:<12}{wk:>8}{seq:>9} {unit:<3}{ov:>12}{tail}")
        return ("\n".join(L) + "\n").encode("utf-8")
    fb.render = render_clk
    out.append(fb)

    # ---------------- maintenance_windows.ics ----------------
    name = "maintenance_windows.ics"
    r = rngs(name)
    fb = FB(name, tests=["job_dispositions"])
    kit_ids(fb, "h", "H", "Host name", INV, ht=("CASE",))
    fb.R("TZ_LOCAL", "T3", "DTSTART/DTEND with a TZID parameter are local times in that zone; values ending in Z are UTC.", SC, [SC, INV], mode="line", fields=["tzl"])
    fb.R("HALFOPEN", "T11", "A maintenance window covers DTSTART inclusive to DTEND exclusive.", POL, [POL, "harness_events.log"], mode="ctx", bait=True)
    fb.R("CANCELLED", "T6", "STATUS:CANCELLED events are not maintenance windows.", POL, [POL, RM], mode="row")
    fb.R("SEQUENCE", "T7", "When an event UID appears more than once, the copy with the highest SEQUENCE wins.", SC, [SC, ER], mode="row")
    fb.R("DURATION", "T2", "Some events give DURATION (PT3H) instead of DTEND.", SC, [SC, POL], mode="line", fields=["dur"])
    fb.R("EXEMPT", "T14", "Jobs listed with an exemption decision in the review minutes run validly inside a window.", RM, [RM, POL], mode="ctx", via_rules=[g(RM, "J_CASE")])
    fb.R("FOLD", "T9", "Long SUMMARY lines are folded (continuation lines start with a space).", SC, [SC, POL], mode="line", bait=True, fields=["fold"], ht=True)
    fb.R("ATTENDEE", "T13", "The host is in X-HOST; LOCATION is the data-centre room and is not a host.", SC, [SC, INV], mode="line", fields=["h"])
    fb.R("ALLDAY", "T5", "VALUE=DATE events (all-day) are planning placeholders with no effect.", POL, [POL, SC], mode="row")
    fb.R("UIDCASE", "T1", "UIDs compare case-insensitively.", SC, [SC, ER], mode="line", fields=["h"])
    fb.R("XHOST_PARAM", "T8", "Some events write X-HOST with a parameter (X-HOST;ROLE=primary:node-0001).", SC, [SC, INV], mode="line", fields=["h"])
    fb.R("SEQ_MISSING", "T5", "An event without SEQUENCE has sequence 0.", SC, [SC, ER], mode="line", fields=["noseq"])
    fb.R("TZID_QUOTED", "T9", "TZID parameter values can be double-quoted.", SC, [SC, INV], mode="line", fields=["tzl"])
    fb.R("UID_SUFFIX", "T1", "UIDs can carry an @heron.example suffix.", SC, [SC, ER], mode="line", fields=["h"])
    fb.R("DESC_BAIT", "T20", "DESCRIPTION text can mention other hosts; only X-HOST names the host.", SC, [SC, INV], mode="line", bait=True, fields=["h"])
    edge = {(W.jobs[j]["host"], iso_week(W.jobs[j]["submitted"])) for j in W.jobs if W.jobs[j]["kind"] == "maintenance"}
    for h in hosts:
        for wk in WEEKS:
            st, en = W.maint[(h, wk)]
            uid = f"mw-{h}-{wk}"
            if r.chance(0.06):
                fb.add({"h": h, "uid": uid, "st": st + 3600, "en": en + 7200, "seq": 0, "kind": "older"}, ["SEQUENCE"])
            rs = []
            if (h, wk) in edge:
                rs.append("HALFOPEN")
            fb.add({"h": h, "uid": uid, "st": st, "en": en, "seq": 1, "kind": "canon"}, rs)
            if r.chance(0.03):
                fb.add({"h": h, "uid": uid + "-x", "st": st + 86400, "en": en + 86400, "seq": 0, "kind": "cancel"}, ["CANCELLED"])
            if r.chance(0.01):
                fb.add({"h": h, "uid": uid + "-p", "st": st - st % 86400, "en": st - st % 86400 + 86400, "seq": 0, "kind": "allday"}, ["ALLDAY"])
    for j in sorted(W.exempt):
        job = W.jobs[j]
        for row in fb.rows:
            pass
    for row in fb.rows:
        f = row["f"]
        hw = W.hw[(f["h"], min(max(iso_week(f["st"]), WEEKS[0]), WEEKS[-1]))]
        f.update({"tzl": 1 if hw["tz"] != "UTC" else None, "dur": 1 if f["kind"] == "canon" else None, "fold": 1, "noseq": 1 if f["seq"] == 0 else None})
    ex_hosts = {(W.jobs[j]["host"], iso_week(W.jobs[j]["submitted"])) for j in W.exempt}
    for row in fb.rows:
        if row["f"]["kind"] == "canon" and (row["f"]["h"], iso_week(row["f"]["st"])) in ex_hosts:
            row["r"].append("EXEMPT")

    def render_ics(fb=fb):
        L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//heron//maintenance//EN"]
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            hw = W.hw[(f["h"], min(max(iso_week(f["st"]), WEEKS[0]), WEEKS[-1]))]
            L.append("BEGIN:VEVENT")
            uid = f["uid"].upper() if "UIDCASE" in rules else f["uid"]
            if "UID_SUFFIX" in rules:
                uid += "@heron.example"
            L.append(f"UID:{uid}")
            if not ("SEQ_MISSING" in rules and f["seq"] == 0):
                L.append(f"SEQUENCE:{f['seq']}")
            if f["kind"] == "allday":
                L.append(f"DTSTART;VALUE=DATE:{time.strftime('%Y%m%d', time.gmtime(f['st']))}")
            elif "TZ_LOCAL" in rules:
                tzid = f'"{hw["tz"]}"' if "TZID_QUOTED" in rules else hw["tz"]
                L.append(f"DTSTART;TZID={tzid}:{local_str(f['st'], hw['tz'], 0, '%Y%m%dT%H%M%S', ms=False)}")
            else:
                L.append(f"DTSTART:{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(f['st']))}")
            if f["kind"] != "allday":
                if "DURATION" in rules:
                    L.append(f"DURATION:PT{(f['en'] - f['st']) // 3600}H")
                elif "TZ_LOCAL" in rules:
                    tzid = f'"{hw["tz"]}"' if "TZID_QUOTED" in rules else hw["tz"]
                    L.append(f"DTEND;TZID={tzid}:{local_str(f['en'], hw['tz'], 0, '%Y%m%dT%H%M%S', ms=False)}")
                else:
                    L.append(f"DTEND:{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(f['en']))}")
            if "FOLD" in rules:
                summ = f"SUMMARY:Planned maintenance window for host {f['h']} covering kernel, driver and firmware updates"
                L.append(summ[:60])
                L.append(" " + summ[60:])
            else:
                L.append(f"SUMMARY:Maintenance {f['h']}")
            L.append(f"X-HOST;ROLE=primary:{v_id(f['h'], rules, 'H')}" if "XHOST_PARAM" in rules else f"X-HOST:{v_id(f['h'], rules, 'H')}")
            if "DESC_BAIT" in rules:
                L.append(f"DESCRIPTION:Coordinate with node-{(int(f['h'][-4:]) % 700) + 1:04d} before starting.")
            if "ATTENDEE" in rules:
                L.append(f"LOCATION:dc{1 + int(f['h'][-4:]) % 4}-room{int(f['h'][-2:]) % 9}")
            if f["kind"] == "cancel":
                L.append("STATUS:CANCELLED")
            L.append("END:VEVENT")
        L.append("END:VCALENDAR")
        return ("\n".join(L) + "\n").encode("utf-8")
    fb.render = render_ics
    out.append(fb)
    return out

# ---------------------------------------------------------------------------------
# job files, errata, overrides, X2, X6, X7
# ---------------------------------------------------------------------------------
LEGACY_SUITE = {"arith": "arithmetic", "code": "codegen", "intent": "intents", "safety": "safety_flags", "mcq": "multiple_choice",
                "pref": "pairwise", "longctx": "long_context", "multiling": "multilingual"}


def build_jobs_files(W, rngs):
    out = []
    jobs_all = sorted(W.jobs)
    reg_jobs = W.job_ids
    # ---------------- run_registry.xml ----------------
    name = REG
    r = rngs(name)
    fb = FB(name, tests=["job_dispositions", "lineage", "item_scores_arith"])
    kit_ids(fb, "j", "J", "Job id", name, ht=("CASE",))
    kit_ids(fb, "c", "C", "Checkpoint id", "checkpoint_lineage.json")
    kit_ids(fb, "h", "H", "Host name", INV)
    fb.R("SHORTCK", "T1", "Some jobs name the checkpoint by its first 7 characters; the unique checkpoint of the job's model family with that prefix is meant.", POL, ["checkpoint_lineage.json", POL], mode="line", fields=["cs"], excl=("C_CASE", "C_PAD", "C_HOMO", "C_WS", "C_FW"))
    pref_count = {}
    for cid, c in W.ckpts.items():
        pref_count[(cid[:7], c["family"])] = pref_count.get((cid[:7], c["family"]), 0) + 1
    fb.R("SUITE_ALIAS", "T17", "suite can be a legacy suite name (arithmetic, codegen, ...).", POL, [POL, "item_registry.csv"], mode="line", fields=["s"])
    fb.R("SHARD1", "T2", "Entries with base=\"1\" number shards from 1; all others from 0.", MD, [MD, "item_registry.csv"], mode="line", fields=["s"])
    fb.R("MODEL_CASE", "T1", "Model aliases compare case-insensitively.", POL, [POL, "model_tags.yaml"], mode="line", fields=["s"])
    fb.R("RENAMED", "T8", "Entries written after the schema migration use the element run with attributes alias and ckpt instead of job, model and checkpoint.", SC, [SC, REGX], mode="pos")
    fb.R("REREG", "T7", "A job registered twice keeps the entry with the higher seq.", SC, [SC, ER], mode="row")
    fb.R("ENT", "T9", "Attribute values use XML entities.", SC, [SC, POL], mode="line", bait=True, fields=["j"], ht=True)
    fb.R("VOIDJOB", "T6", "Jobs on the errata job void list stay registered but do not count.", ER, [ER, POL], mode="ctx")
    fb.R("STAGE_HOST", "T17", "The registered host decides staging status through the host inventory week entry.", INV, [INV, "harness_events.log"], mode="ctx", cond=True)
    fb.R("EMA_CK", "T13", "Jobs of the -ema alias name EMA checkpoints, which are registered only in the lineage snapshot.", POL, ["checkpoint_lineage_snapshot.json", POL], mode="ctx")
    fb.R("STALE", "T22", "A job whose checkpoint is not the alias's certified checkpoint is stale.", POL, ["model_tags.yaml", MBOX], mode="ctx", cond=True)
    seq = 0
    for j in reg_jobs:
        job = W.jobs[j]
        seq += r.randint(1, 3)
        if r.chance(0.05):
            fb.add({"j": j, "job": dict(job, host=r.choice(W.hosts)), "seq": seq, "kind": "older"}, ["REREG"])
            seq += 1
        rs = []
        if j in W.job_void:
            rs.append("VOIDJOB")
        if job["kind"] == "staging_host":
            rs.append("STAGE_HOST")
        if job["model"].endswith("-ema"):
            rs.append("EMA_CK")
        if job["kind"] == "stale_checkpoint":
            rs.append("STALE")
        fb.add({"j": j, "job": job, "seq": seq, "kind": "canon"}, rs)
    for row in fb.rows:
        ck = row["f"]["job"]["ckpt"]
        row["f"].update({"c": 1, "h": 1, "s": 1, "cs": 1 if pref_count.get((ck[:7], W.ckpts[ck]["family"])) == 1 else None})

    def render_reg(fb=fb, r=r):
        L = ['<?xml version="1.0" encoding="UTF-8"?>', '<registry window="2025-07-01/2025-10-01">']
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            job = f["job"]
            ck = v_id(job["ckpt"], rules, "C")
            if "SHORTCK" in rules:
                ck = job["ckpt"][:7]
            suite = LEGACY_SUITE[job["bench"]] if "SUITE_ALIAS" in rules else job["bench"]
            shard = job["shard"] + (1 if "SHARD1" in rules else 0)
            base = ' base="1"' if "SHARD1" in rules else ""
            model = job["model"].upper() if "MODEL_CASE" in rules else job["model"]
            jid = v_id(f["j"], rules, "J")
            if "ENT" in rules:
                model = model.replace("-", "&#45;")
            el = "run" if "RENAMED" in rules else "job"
            if el == "job":
                L.append(f'  <job id="{xesc(jid)}" model="{model}" checkpoint="{xesc(ck)}" suite="{suite}" shard="{shard}"{base} host="{xesc(v_id(job["host"], rules, "H"))}" seq="{f["seq"]}"/>')
            else:
                L.append(f'  <run id="{xesc(jid)}" alias="{model}" ckpt="{xesc(ck)}" suite="{suite}" shard="{shard}"{base} host="{xesc(v_id(job["host"], rules, "H"))}" seq="{f["seq"]}"/>')
        L.append("</registry>")
        return ("\n".join(L) + "\n").encode("utf-8")
    fb.render = render_reg
    out.append(fb)

    # ---------------- run_registry_export.xml (decoy) ----------------
    name = REGX
    r = rngs(name)
    fb = FB(name, decoy=True, tests=["job_dispositions", "source_audit_used"])
    kit_ids(fb, "j", "J", "Job id", REG, ht=("CASE",))
    for code, fam, desc, d, mode in [
        ("X_FULL", "T16", "The export lists more attributes per job (queue, priority, owner); extra attributes do not make it authoritative.", "pull", "row"),
        ("X_AGREE", "T16", "Export hosts and checkpoints agree with the run registry for most jobs and differ for some; the run registry wins.", "pull", "row"),
        ("X_NEWER", "T7", "Export entries carry exported_at after the registry's dates; that is the export time, not a newer registration.", "pull", "line"),
        ("X_UNREG", "T13", "Jobs that appear only in the export were never registered; their result rows are ignored.", "pull", "row"),
        ("LNO", "T13", "legacy_no is the only map from retired scheduler numbers (L-nnnnn) to job ids; those numbers appear in legacy_results.txt and harness_events.log.", "push", "row"),
        ("LNO_CASE", "T1", "Legacy numbers can be written in lower case or without the L- prefix.", "push", "line"),
        ("X_STATUS", "T14", "status=complete in the export is a scheduler state and says nothing about certification.", "pull", "row"),
        ("X_TZ", "T3", "Export times are US Central (UTC-05:00) without an offset.", "pull", "line"),
        ("X_SHARD", "T2", "Export shards are 1-based.", "pull", "row"),
        ("X_CK", "T1", "Export checkpoints are upper-case hex.", "pull", "line"),
        ("X_SUITE", "T17", "Export suites use legacy names.", "pull", "row"),
        ("X_VOID", "T6", "Export rows with cancelled=yes are cancelled submissions.", "pull", "row"),
        ("X_DUP", "T20", "Jobs exported twice are one job.", "pull", "row"),
        ("X_ENT", "T9", "Attribute values use entities and CDATA.", "pull", "line"),
        ("X_PRIO", "T15", "Priority values above 100 are real.", "pull", "row"),
        ("X_NULL", "T5", "A host of ? means unknown in the export.", "pull", "row"),
        ("X_SCHEMA", "T8", "The export's element is task, not job.", "pull", "line"),
        ("X_MODEL", "T17", "The export names models by their internal project codes.", "pull", "row"),
        ("X_CERT", "T22", "The export's certified=yes flag predates the approval process and is ignored.", "pull", "row"),
        ("X_ORDER", "T11", "Export rows submitted at the window boundary use an inclusive end; the policy window is half-open.", "pull", "row"),
        ("X_ROUND", "T12", "Durations are rounded to minutes and are not used.", "pull", "row"),
        ("X_LOCALE", "T4", "Durations use a comma decimal mark.", "pull", "row"),
        ("X_ENC", "T10", "The export declares encoding ISO-8859-1.", "pull", "row"),
        ("X_PREC", "T21", "For legacy numbers the export decides the job id; for every other job field the run registry decides.", "push", "row"),
        ("X_OSC", "T18", "Ignoring the export loses the legacy number map; trusting it overrides registry hosts. The precedence rule uses it for legacy numbers only.", "push", "row"),
        ("X_EQ", "T19", "Export hosts are consistent with the old inventory; that consistency does not make them current.", "pull", "row"),
        ("X_BAIT", "T20", "An export entry identical to the registry entry is not a conflict.", "pull", "row"),
    ]:
        fb.R(code, fam, desc, POL, [POL, REG] if code not in ("LNO",) else ["legacy_results.txt", POL], mode=mode, direction=d,
             fields=["j"] if mode == "line" else None, bait=code in ("X_DUP", "X_BAIT", "X_PRIO"), ht=code in ("X_TZ", "X_SCHEMA"))
    proj = {m: f"proj-{i:02d}" for i, m in enumerate(MODELS)}
    for j in jobs_all:
        job = W.jobs[j]
        rs = [r.choice(["X_FULL", "X_AGREE", "X_STATUS", "X_SUITE", "X_MODEL", "X_SHARD"])]
        if j in W.unregistered:
            rs.append("X_UNREG")
        if j in W.legacy_jobno:
            rs += ["LNO", "X_PREC"] if r.chance(0.6) else ["LNO", "X_OSC"]
        if r.chance(0.05):
            rs.append(r.choice(["X_VOID", "X_CERT", "X_ORDER", "X_ROUND", "X_LOCALE", "X_NULL", "X_PRIO", "X_EQ", "X_BAIT"]))
        fb.add({"j": j, "job": job}, rs)
        if r.chance(0.12):
            fb.add({"j": j, "job": job}, ["X_DUP"])
    fb.rows[0]["r"].append("X_ENC")

    def render_regx(fb=fb, r=r):
        L = ['<?xml version="1.0" encoding="ISO-8859-1"?>', "<export scheduler=\"quartz-legacy\" exported_at=\"2025-09-30T23:00:00\">"]
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            job = f["job"]
            j = f["j"]
            ck = job["ckpt"].upper() if "X_CK" in rules else job["ckpt"]
            lno = W.legacy_jobno.get(j)
            if lno and "LNO_CASE" in rules:
                lno = lno.lower() if r.chance(0.5) else lno[2:]
            host = "?" if "X_NULL" in rules else (r.choice(W.hosts) if "X_AGREE" in rules and r.chance(0.3) else job["host"])
            attrs = f'id="{xesc(v_id(j, rules, "J"))}" project="{proj[job["model"]]}" ckpt="{ck}" suite="{LEGACY_SUITE[job["bench"]]}" shard="{job["shard"] + 1}" host="{host}"'
            attrs += f' submitted="{local_str(job["submitted"], "America/Chicago", 0, "%Y-%m-%dT%H:%M:%S", ms=False)}" queue="q{r.randint(1, 9)}" priority="{r.randint(1, 150)}"'
            if lno:
                attrs += f' legacy_no="{lno}"'
            if "X_VOID" in rules:
                attrs += ' cancelled="yes"'
            if "X_CERT" in rules:
                attrs += ' certified="yes"'
            L.append(f"  <task {attrs} status=\"complete\"/>")
        L.append("</export>")
        return ("\n".join(L) + "\n").encode("latin-1", errors="xmlcharrefreplace")
    fb.render = render_regx
    out.append(fb)

    # ---------------- job_configs.toml ----------------
    name = "job_configs.toml"
    r = rngs(name)
    fb = FB(name, tests=["item_scores_intent", "item_scores_multiling", "metric_multiling"])
    kit_ids(fb, "j", "J", "Job id", REG, ht=("CASE",))
    fb.R("HARNESS_ALIAS", "T17", "harness can be written 3.2, h3.2 or harness-3.2.", POL, [POL, "label_aliases.json"], mode="line", fields=["hv"])
    fb.R("TAXO", "T17", "Harness h4.0 uses taxonomy v2 and grader g3; h3.1 and h3.2 use taxonomy v1 and grader g2.", POL, [POL, "label_aliases.json"], mode="ctx", cond=True)
    fb.R("REV", "T7", "A job configured twice keeps the table with the higher revision.", SC, [SC, ER], mode="row")
    fb.R("TEMP_STR", "T4", "temperature can be a string.", SC, [SC, POL], mode="line", fields=["j"])
    fb.R("SAMPLES", "T2", "samples is the number of samples per item; code jobs draw 10.", MD, [MD, "code_samples.jsonl"], mode="ctx")
    fb.R("INLINE", "T9", "Some job tables are written as inline tables.", SC, [SC, POL], mode="line", bait=True, fields=["j"], ht=True)
    fb.R("SUBMIT_LOCAL", "T3", "submitted_local is the host-local submission date and is informational; the harness events give the submission instant.", SC, [SC, "harness_events.log"], mode="line", fields=["j"])
    fb.R("SENT_TEMP", "T5", "A temperature of -1 means the harness default (0.0, or 0.8 for code).", SC, [SC, POL], mode="row")
    fb.R("VOID", "T6", "Configs listed in the errata registry void list are void.", ER, [ER, POL], mode="row")
    fb.R("GRADER", "T17", "The grader used for a job follows from its harness version.", MD, [MD, "gold_labels.tsv"], mode="ctx", cond=True)
    fb.R("FK", "T13", "Configs for jobs absent from the run registry are ignored.", POL, [REG, POL], mode="row")
    fb.R("REV_TXT", "T4", "revision can be a string with an r prefix.", SC, [SC, POL], mode="line", fields=["j"])
    fb.R("HARNESS_CASE", "T1", "harness can be upper-cased (H3.2).", POL, [POL, "label_aliases.json"], mode="line", fields=["hv"], excl=("HARNESS_ALIAS",))
    fb.R("COMMENT", "T20", "A # after a value starts a comment.", SC, [SC, POL], mode="line", bait=True, fields=["j"])
    fb.R("DATE_STR", "T3", "submitted_local can be a quoted string instead of a TOML date.", SC, [SC, "harness_events.log"], mode="line", fields=["j"])
    fb.R("INT_STR", "T4", "samples can be a string.", SC, [SC, POL], mode="line", fields=["j"], excl=("INLINE",))
    for j in jobs_all:
        job = W.jobs[j]
        if r.chance(0.05):
            fb.add({"j": j, "job": dict(job, harness=r.choice(HARNESS)), "rev": 1, "kind": "older"}, ["REV"])
        rs = []
        if job["harness"] == "h4.0" and job["bench"] in ("intent", "multiling"):
            rs.append("TAXO" if job["bench"] == "intent" else "GRADER")
        if j in W.unregistered:
            rs.append("FK")
        sent = r.chance(0.05)
        if sent:
            rs.append("SENT_TEMP")
        fb.add({"j": j, "job": job, "rev": 2, "kind": "canon", "sent": sent}, rs)
        if r.chance(0.008):
            fb.add({"j": j, "job": dict(job, harness="h3.1" if job["harness"] == "h4.0" else "h4.0"), "rev": 3, "kind": "void"}, ["VOID"])
            W.errata_reg.append((name, j, 3))
    for row in fb.rows:
        row["f"]["hv"] = 1

    def render_jc(fb=fb, r=r):
        L = ["# Harness job configuration export", 'schema = "jobcfg/2"', ""]
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            job = f["job"]
            hv = job["harness"]
            if "HARNESS_ALIAS" in rules:
                hv = r.choice([hv[1:], "harness-" + hv[1:]])
            if "HARNESS_CASE" in rules:
                hv = hv.upper()
            temp = "-1" if f.get("sent") else job["temperature"]
            tv = f'"{temp}"' if "TEMP_STR" in rules else temp
            sub = time.strftime("%Y-%m-%d", time.gmtime(job["submitted"] + TZ_OFFSET[W.hw[(job["host"], iso_week(job["submitted"]))]["tz"]]))
            if "DATE_STR" in rules:
                sub = f'"{sub}"'
            jid = v_id(f["j"], rules, "J")
            revv = f'"r{f["rev"]}"' if "REV_TXT" in rules else str(f["rev"])
            smp = f'"{job["samples"]}"' if "INT_STR" in rules else str(job["samples"])
            cm = "  # verified" if "COMMENT" in rules else ""
            if "INLINE" in rules:
                L.append(f'job = {{ id = "{jid}", harness = "{hv}", temperature = {tv}, samples = {job["samples"]}, revision = {f["rev"]}, submitted_local = {sub} }}' if False else
                         f'[[job]]\nid = "{jid}"{cm}\nharness = "{hv}"\nsettings = {{ temperature = {tv}, samples = {smp} }}\nrevision = {revv}\nsubmitted_local = {sub}')
            else:
                L.append(f'[[job]]\nid = "{jid}"{cm}\nharness = "{hv}"\ntemperature = {tv}\nsamples = {smp}\nrevision = {revv}\nsubmitted_local = {sub}')
            L.append("")
        return ("\n".join(L) + "\n").encode("utf-8")
    fb.render = render_jc
    out.append(fb)

    # ---------------- harness_events.log ----------------
    name = "harness_events.log"
    r = rngs(name)
    fb = FB(name, tests=["job_dispositions", "control_reconciliation"])
    kit_ids(fb, "j", "J", "Job id", REG, ht=("CASE",))
    kit_ids(fb, "h", "H", "Host name", INV)
    kit_hosttime(fb, ht=("TZ_BER", "TZ_CHI"))
    fb.R("LNO", "T13", "SUBMIT lines for jobs submitted before the scheduler migration can name the job by its retired number; the export maps it.", POL, [REGX, POL], mode="ctx", via_rules=[g(REGX, "LNO")])
    fb.R("FIRST", "T7", "A job can have several SUBMIT lines (queue retries); the submission instant is the earliest one after zone and clock correction.", SC, [SC, INV], mode="row")
    fb.R("WINDOW", "T11", "The certification window is half-open: 2025-07-01T00:00:00Z inclusive to 2025-10-01T00:00:00Z exclusive.", POL, [POL, INV], mode="ctx", bait=True)
    fb.R("RERUN", "T22", "RERUN lines link an original job to its rerun; the link takes effect only with an approval in the review minutes.", RM, [RM, REG, "rerun_results.jsonl"], mode="row", via_rules=[g(RM, "J_CASE")])
    fb.R("B_UTC", "T20", "Lines whose timestamp ends in Z were written by the scheduler in UTC with a corrected clock.", SC, [SC, INV], mode="line", bait=True, fields=["ts"], ht=True)
    fb.R("FK", "T13", "SUBMIT lines for job ids absent from the run registry are ignored.", POL, [REG, REGX], mode="row")
    fb.R("MAINT", "T17", "A submission inside a maintenance window of its host does not count unless the review minutes exempt the job.", POL, ["maintenance_windows.ics", RM], mode="ctx", cond=True)
    rows = []
    for j in jobs_all:
        job = W.jobs[j]
        t = job["submitted"]
        rs = []
        if j in W.legacy_jobno:
            rs.append("LNO")
        if j in W.unregistered:
            rs.append("FK")
        if job["kind"] == "outside_window" or t == WINDOW_START:
            rs.append("WINDOW")
        if job["kind"] == "maintenance" or j in W.exempt:
            rs.append("MAINT")
        rows.append((t, {"j": j, "t": t, "ev": "SUBMIT", "ts": 1}, rs))
        if r.chance(0.07):
            rows.append((t + r.randint(30, 7200), {"j": j, "t": t + r.randint(30, 7200), "ev": "SUBMIT", "ts": 1, "retry": 1}, ["FIRST"]))
    for rr_, o in sorted(W.rerun_of.items()):
        t = W.jobs[rr_]["submitted"] - r.randint(60, 3000)
        rows.append((t, {"j": o, "t": t, "ev": "RERUN", "as": rr_, "ts": 1}, ["RERUN"]))
    rows.sort(key=lambda x: (x[0], x[1]["j"]))
    for _t, f, rs in rows:
        job = W.jobs[f["j"]]
        x = RRow(name, f["j"], None, 0, job["bench"], {}, f["t"], "canon")
        base = [c for c in base_rules(W, fb, x, numeric=False) if c in ("TZ_BER", "TZ_CHI", "TZ_KOL", "TZ_SAO", "SKEW", "EQUI")]
        f["h"] = 1
        fb.add(f, base + rs)
    ended = {}
    for row in fb.rows:
        if row["f"]["ev"] == "SUBMIT" and not row["f"].get("retry"):
            ended[row["f"]["j"]] = 1
    for j in sorted(ended):
        if j in W.res and r.chance(0.35):
            fb.add({"j": j, "t": W.seal[j], "ev": "END", "n": len(W.res[j]), "ts": None, "h": None}, [], kind="anchor")

    def render_he(fb=fb):
        L = []
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            job = W.jobs[f["j"]]
            hw = W.hw[(job["host"], iso_week(job["submitted"]))]
            ts = iso(f["t"]) if "B_UTC" in rules else local_str(f["t"], hw["tz"], hw["offset_ms"])
            host = v_id(job["host"], rules, "H")
            jid = W.legacy_jobno[f["j"]] if "LNO" in rules else v_id(f["j"], rules, "J")
            if f["ev"] == "SUBMIT":
                L.append(f"{ts} {host} SUBMIT job={jid} model={job['model']} suite={job['bench']}")
            elif f["ev"] == "RERUN":
                L.append(f"{ts} {host} RERUN of={jid} as={v_id(f['as'], [], 'J')}")
            else:
                L.append(f"{local_str(f['t'], hw['tz'], hw['offset_ms'])} {job['host']} END job={f['j']} rows={f['n']}")
        return ("\n".join(L) + "\n").encode("utf-8")
    fb.render = render_he
    out.append(fb)
    return out

# ---------------------------------------------------------------------------------
# mailbox, grader errata, manual overrides, X2, X7
# ---------------------------------------------------------------------------------
MAIL_TZ = ["UTC", "Europe/Berlin", "America/Chicago", "Asia/Kolkata"]


def build_misc(W, rngs):
    out = []
    # ---------------- evalops_notifications.mbox ----------------
    name = MBOX
    r = rngs(name)
    fb = FB(name, tests=["lineage", "item_scores_mcq", "item_scores_safety"])
    kit_ids(fb, "j", "J", "Job id", REG, ht=("CASE",))
    kit_ids(fb, "k", "K", "Ticket id", "model_tags.yaml")
    fb.R("TZ_HDR", "T3", "Message Date headers carry the sender's numeric offset; compare instants in UTC (Europe/Berlin senders write +0200).", SC, [SC, "model_tags.yaml"], mode="ctx", cond=True)
    fb.R("TZ_HDR_CHI", "T3", "Date headers from the Chicago desk carry -0500.", SC, [SC, "model_tags.yaml"], mode="ctx", cond=True)
    fb.R("TZ_HDR_KOL", "T3", "Date headers from the Bengaluru desk carry +0530.", SC, [SC, "model_tags.yaml"], mode="ctx", cond=True)
    fb.R("SEAL", "T22", "A seal receipt fixes the job's seal time at the message Date; result rows emitted after it are ignored.", SC, ["results_fleet_a.log", SC], mode="row")
    fb.R("RESEAL", "T7", "A RESEAL receipt replaces the earlier seal of the same job (the latest RESEAL Date is the seal time).", SC, [SC, CT], mode="row")
    fb.R("FWD", "T20", "Forwarded copies (Subject starting Fwd:) repeat an earlier message; the original Date counts.", POL, [POL, SC], mode="row", bait=True)
    fb.R("APPROVE", "T22", "APPROVED and REJECTED messages decide tag tickets; an approval takes effect at its Date if that is at or before the cutoff 2025-10-03T18:00:00Z.", POL, ["model_tags.yaml", POL], mode="row", via_rules=[g("model_tags.yaml", "K_CASE")])
    fb.R("REJECT", "T6", "A REJECTED message cancels its ticket even if an approval for the same ticket came earlier.", POL, ["model_tags.yaml", POL], mode="row")
    fb.R("LATEAPP", "T11", "Approvals dated after the cutoff have no effect; an approval exactly at the cutoff counts.", POL, ["model_tags.yaml", POL], mode="row")
    fb.R("QP", "T10", "Some bodies are quoted-printable (Content-Transfer-Encoding: quoted-printable); decode before reading.", SC, [SC, POL], mode="line", fields=["qp"])
    fb.R("FROMESC", "T9", "Body lines starting with From are escaped with >.", SC, [SC, POL], mode="line", bait=True, fields=["fr"], ht=True)
    fb.R("SUBJ_CASE", "T1", "Subject keywords can be in any case.", SC, [SC, POL], mode="line", fields=["j"])
    fb.R("MSGID", "T9", "Message-ID values are informational.", SC, [SC, POL], mode="line", bait=True, fields=["j"])
    fb.R("DATE_NAME", "T3", "Some Date headers use a zone name (CEST, CDT, IST) after the numeric offset; the offset decides.", SC, [SC, POL], mode="line", fields=["tzn"])
    msgs = []
    W.reseal = {}
    for j in sorted(W.seal):
        if j in W.unregistered:
            continue
        s = W.seal[j]
        if r.chance(0.06):
            early = s - r.randint(600, 4 * 3600)
            msgs.append((early, {"kind": "seal", "j": j, "t": early, "k": None, "fr": None}, ["SEAL"]))
            msgs.append((s, {"kind": "reseal", "j": j, "t": s, "k": None, "fr": None}, ["RESEAL"]))
            W.reseal[j] = early
        else:
            msgs.append((s, {"kind": "seal", "j": j, "t": s, "k": None, "fr": None}, []))
        if r.chance(0.02):
            msgs.append((s + r.randint(3600, 86400), {"kind": "fwd", "j": j, "t": s + r.randint(3600, 86400), "orig": s, "k": None, "fr": None}, ["FWD"]))
    for e in W.promos:
        if e["approval"] is None:
            continue
        verdict, t = e["approval"]
        rs = ["APPROVE"] if verdict == "APPROVED" else ["REJECT"]
        if t > CUTOFF or t == CUTOFF:
            rs.append("LATEAPP")
        msgs.append((t, {"kind": "approval", "j": None, "t": t, "k": e["ticket"], "verdict": verdict, "tag": e["tag"], "fr": None}, rs))
    msgs.sort(key=lambda m: (m[0], str(m[1].get("j")), str(m[1].get("k"))))
    for _t, f, rs in msgs:
        tz = r.weighted([("UTC", 46), ("Europe/Berlin", 18), ("America/Chicago", 18), ("Asia/Kolkata", 18)])
        f["tz"] = tz
        if tz != "UTC":
            rs = rs + [{"Europe/Berlin": "TZ_HDR", "America/Chicago": "TZ_HDR_CHI", "Asia/Kolkata": "TZ_HDR_KOL"}[tz]]
        f["qp"] = 1 if f["kind"] == "approval" else None
        f["tzn"] = 1 if tz != "UTC" else None
        f["fr"] = 1 if r.chance(0.2) else None
        fb.add(f, rs)

    def render_mbox(fb=fb, r=r):
        msgs = []
        for i, row in enumerate(fb.rows):
            f, rules = row["f"], row["r"]
            t = f["t"]
            date = rfc2822(t, f["tz"])
            if "DATE_NAME" in rules:
                date += " (" + {"Europe/Berlin": "CEST", "America/Chicago": "CDT", "Asia/Kolkata": "IST"}[f["tz"]] + ")"
            frm = f"From evalops@heron.example {time.strftime('%a %b %d %H:%M:%S %Y', time.gmtime(t))}"
            hdr = [("From", "evalops@heron.example"), ("Date", date), ("Message-ID", f"<{i:06d}@heron.example>")]
            body = ""
            if f["kind"] in ("seal", "reseal", "fwd"):
                kw = {"seal": "SEALED", "reseal": "RESEAL", "fwd": "SEALED"}[f["kind"]]
                if "SUBJ_CASE" in rules:
                    kw = kw.lower()
                jid = v_id(f["j"], rules, "J")
                subj = f"[evalops] {kw} job {jid}"
                if f["kind"] == "fwd":
                    subj = "Fwd: " + subj
                    body = f"---------- Forwarded message ----------\nDate: {rfc2822(f['orig'], 'UTC')}\nResults for job {jid} were sealed."
                else:
                    body = f"Job {jid} sealed at the Date of this message."
                hdr.append(("Subject", subj))
            else:
                tk = v_id(f["k"], rules, "K")
                subj = f"[registry] {f['verdict']} {tk} tag {f['tag']}"
                if "SUBJ_CASE" in rules:
                    subj = subj.lower()
                hdr.append(("Subject", subj))
                body = f"Ticket {tk} for tag {f['tag']} is {f['verdict'].lower()}.\nThis decision takes effect at the Date of this message."
                if "QP" in rules:
                    hdr.append(("Content-Transfer-Encoding", "quoted-printable"))
                    body = body.replace("=", "=3D").replace(" is ", " is=\n ")
            if f["fr"] and "FROMESC" in rules:
                body += "\nFrom the evaluation operations desk."
            msgs.append((frm, hdr, body))
        return mbox_bytes(msgs)
    fb.render = render_mbox
    out.append(fb)

    # ---------------- grader_errata.xml ----------------
    name = "grader_errata.xml"
    r = rngs(name)
    fb = FB(name, tests=["item_scores_arith", "item_scores_mcq", "item_scores_intent", "metric_safety"])
    kit_ids(fb, "k", "D", "Dispute ticket", "gold_labels_corrected.csv", ht=("CASE",))
    fb.R("TICKET", "T13", "Errata name dispute tickets; the ticket-to-item map is the dispute_ticket column of the corrected-gold export.", POL, ["gold_labels_corrected.csv", POL], mode="ctx", via_rules=[g("gold_labels_corrected.csv", "TICKET_MAP")])
    fb.R("UPHELD", "T7", "An upheld erratum replaces the gold value with its value attribute.", POL, ["gold_labels.tsv", POL, "baseline_reference.csv"], mode="row")
    fb.R("WITHDRAWN", "T6", "A withdrawn erratum changes nothing, even when it is the latest entry for its ticket.", POL, ["gold_labels.tsv", POL], mode="row")
    fb.R("LATEST", "T7", "Among upheld and withdrawn errata for one ticket, the latest decided instant wins.", POL, [POL, "gold_labels.tsv"], mode="row")
    fb.R("CONFIRMED", "T20", "A confirmed erratum re-states the existing gold and changes nothing.", POL, ["gold_labels.tsv", POL], mode="row", bait=True)
    fb.R("AFTER_CUTOFF", "T11", "Errata decided after the cutoff are not applied to this close.", POL, [POL, MBOX], mode="row")
    fb.R("DECIDED_TZ", "T3", "decided values carry numeric offsets.", SC, [SC, POL], mode="line", fields=["ts"])
    fb.R("V2VAL", "T17", "Intent erratum values are written in taxonomy v2 names.", POL, ["label_aliases.json", POL], mode="ctx", cond=True)
    fb.R("CDATA", "T9", "Erratum notes are CDATA sections and can contain angle brackets.", SC, [SC, POL], mode="line", bait=True, fields=["k"], ht=True)
    fb.R("RENAMED", "T8", "Entries in the second block use the element correction with attribute fix instead of erratum and value.", SC, [SC, POL], mode="pos")
    fb.R("NUMFMT", "T4", "Numeric values are plain en_US decimals.", MD, [MD, "gold_labels.tsv"], mode="ctx")
    fb.R("STATUS_CASE", "T1", "status values can be upper-cased.", POL, [POL, "gold_labels.tsv"], mode="line", fields=["k"])
    fb.R("ATTR_ORDER", "T8", "Attribute order varies between entries.", SC, [SC, POL], mode="line", fields=["k"])
    fb.R("DEC_EPOCH", "T3", "decided can be epoch seconds.", SC, [SC, POL], mode="line", fields=["k"], excl=("DECIDED_TZ",))
    fb.R("VALUE_WS", "T9", "value attributes can carry surrounding spaces.", SC, [SC, POL], mode="line", fields=["k"])
    fb.R("NOTE_BAIT", "T20", "A note attribute mentioning another ticket does not apply to it.", POL, [POL, "gold_labels_corrected.csv"], mode="line", bait=True, fields=["k"])
    for iid in sorted(W.items):
        tk = W.dispute[iid]
        it = W.items[iid]
        if it["bench"] == "pref":
            continue
        def val(wrong=False):
            b = it["bench"]
            if b == "arith":
                return format(it["gold"] + (Decimal("2.00") if wrong else 0), "f")
            if b == "code":
                return str(it["tests"] + (2 if wrong else 0))
            if b == "intent":
                return v2(it["gold"] if not wrong else r.choice([c for c in INTENT_CLASSES if c != it["gold"]]))
            if b == "safety":
                return str(1 - it["gold"] if wrong else it["gold"])
            if b == "mcq":
                return it["gold"] if not wrong else r.choice([o for o in "ABCDE"[:it["n_options"]] if o != it["gold"]])
            return it["gold"] + ("x" if wrong else "")
        t0 = T(2025, 7, 5) + r.randint(0, 80) * 86400
        ek = W.err_kind[iid]
        if ek == "upheld_w":
            fb.add({"tk": tk, "st": "withdrawn", "v": val(True), "t": t0 - 86400 * 3, "iid": iid}, ["WITHDRAWN"])
            fb.add({"tk": tk, "st": "upheld", "v": val(), "t": t0, "iid": iid}, ["UPHELD", "LATEST", "TICKET"] + (["V2VAL"] if it["bench"] == "intent" else []))
        elif ek == "upheld":
            fb.add({"tk": tk, "st": "upheld", "v": val(), "t": t0, "iid": iid}, ["UPHELD", "TICKET"] + (["V2VAL"] if it["bench"] == "intent" else []))
        elif ek == "confirmed":
            fb.add({"tk": tk, "st": "confirmed", "v": val(), "t": t0, "iid": iid}, ["CONFIRMED"] if r.chance(0.08) else [])
        elif ek == "withdrawn":
            fb.add({"tk": tk, "st": "withdrawn", "v": val(True), "t": t0, "iid": iid}, ["WITHDRAWN"])
        elif ek == "after":
            fb.add({"tk": tk, "st": "upheld", "v": val(True), "t": CUTOFF + r.randint(3600, 9 * 86400), "iid": iid}, ["AFTER_CUTOFF"])
        elif ek == "pair":
            fb.add({"tk": tk, "st": "upheld", "v": val(True), "t": t0, "iid": iid}, ["UPHELD", "LATEST"])
            fb.add({"tk": tk, "st": "withdrawn", "v": val(True), "t": t0 + 86400, "iid": iid}, ["WITHDRAWN", "LATEST"])
    for row in fb.rows:
        row["f"].update({"k": 1, "ts": 1})

    def render_ge(fb=fb, r=r):
        L = ['<?xml version="1.0" encoding="UTF-8"?>', "<grader_errata>", "<errata>"]
        cur = "A"
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            lay = "B" if "RENAMED" in rules else "A"
            if lay != cur:
                L.append("</errata>\n<errata block=\"2\">" if lay == "B" else "</errata>\n<errata>")
                cur = lay
            tz = r.choice(MAIL_TZ) if "DECIDED_TZ" in rules else "UTC"
            off = TZ_OFFSET[tz]
            dec = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(f["t"] + off)) + (("+" if off >= 0 else "-") + f"{abs(off) // 3600:02d}:{abs(off) % 3600 // 60:02d}" if off else "Z")
            tk = v_id(f["tk"], rules, "D")
            if "DEC_EPOCH" in rules:
                dec = str(f["t"])
            note = "<![CDATA[reviewer note: <see dispute thread>]]>" if "CDATA" in rules else ""
            st = f["st"].upper() if "STATUS_CASE" in rules else f["st"]
            nb = f' note="see DSP-{(int(f["tk"][4:]) + 17) % 100000:05d}"' if "NOTE_BAIT" in rules else ""
            el, vk = ("erratum", "value") if lay == "A" else ("correction", "fix")
            vv = (" " + f["v"] + " ") if "VALUE_WS" in rules else f["v"]
            attrs = [f'ticket="{xesc(tk)}"', f'status="{st}"', f'{vk}="{xesc(vv)}"', f'decided="{dec}"']
            if "ATTR_ORDER" in rules:
                attrs = attrs[::-1]
            L.append(f'  <{el} ' + " ".join(attrs) + f'{nb}>{note}</{el}>')
        L.append("</errata>")
        L.append("</grader_errata>")
        return ("\n".join(L) + "\n").encode("utf-8")
    fb.render = render_ge
    out.append(fb)

    # ---------------- manual_overrides.xlsx ----------------
    name = "manual_overrides.xlsx"
    r = rngs(name)
    fb = FB(name, tests=["item_scores_pref", "pairwise_counts"])
    kit_ids(fb, "j", "J", "Job id", REG, ht=("CASE",))
    kit_ids(fb, "i", "I", "Item id", "item_registry.csv")
    fb.R("DRAFT", "T7", "Only reviews with status final replace a judge verdict; draft reviews are ignored.", POL, [POL, "judge_verdicts.jsonl"], mode="row")
    fb.R("PERSPECTIVE", "T17", "Reviewers record verdicts as candidate, baseline or tie for the slot pair; they are already in the candidate's perspective.", POL, ["judge_verdicts_rescored.jsonl", POL], mode="ctx", cond=True)
    fb.R("SERIAL", "T3", "reviewed_at is a spreadsheet serial date.", SC, [SC, "judge_verdicts.jsonl"], mode="line", fields=["ts"], ht=True)
    fb.R("SLOTNUM", "T2", "slot is 1 or 2 and names the slot of the judged pair, matching judge_verdicts.jsonl.", MA, [MA, "judge_verdicts.jsonl"], mode="ctx")
    fb.R("STATUS_CASE", "T1", "status can be written FINAL or Final.", POL, [POL, "judge_verdicts.jsonl"], mode="line", fields=["j"])
    fb.R("LATESTREV", "T7", "When a slot has several final reviews the latest reviewed_at wins.", POL, [POL, "judge_verdicts.jsonl"], mode="row")
    fb.R("B_SAME", "T20", "A final review equal to the judge verdict confirms it.", POL, [POL, "judge_verdicts.jsonl"], mode="row", bait=True)
    fb.R("UNAUTH", "T13", "Reviews for jobs that are not authoritative do nothing.", POL, [REG, POL], mode="ctx")
    fb.R("TIE_WORD", "T5", "A verdict of tie or = is a tie.", POL, [POL, MA], mode="line", fields=["tie"])
    fb.R("LINEBREAK", "T10", "Cells can end with a carriage return and line feed; strip them.", SC, [SC, POL], mode="line", fields=["j"])
    fb.R("DUPROW", "T20", "A review row repeated verbatim is one review.", POL, [POL, ER], mode="row", bait=True)
    fb.R("SLOT_STR", "T4", "slot can be text.", MA, [MA, "judge_verdicts.jsonl"], mode="line", fields=["j"])
    fb.R("VERDICT_CASE", "T1", "Verdict words can be capitalised.", POL, [POL, MA], mode="line", fields=["i"])
    judge = {(x.job, x.item, x.sub): x.vals["verdict"] for x in W.rows["judge_verdicts.jsonl"] if x.kind == "canon"}
    for (j, iid, sub, v, st, t) in sorted(W.reviews, key=lambda e: (e[5], e[0], e[1], e[2])):
        rs = []
        if st == "draft":
            rs.append("DRAFT")
        elif judge.get((j, iid, sub)) == v and r.chance(0.05):
            rs.append("B_SAME")
        if W.present.get((j, iid)) == "slot1_baseline" and v != "T":
            rs.append("PERSPECTIVE")
        fb.add({"jid": j, "iid": iid, "sub": sub, "v": v, "st": st, "t": t, "j": 1, "i": 1, "ts": 1, "tie": 1 if v == "T" else None}, rs)
        if st == "final" and r.chance(0.03):
            fb.add({"jid": j, "iid": iid, "sub": sub, "v": perturb(W, r, "pref", "verdict", v, iid), "st": "final", "t": t - 3600, "j": 1, "i": 1, "ts": 1, "tie": None}, ["LATESTREV"])

    for i in range(len(fb.rows) // 9):
        jx = r.below(len(fb.rows))
        fb.rows.insert(jx + 1, {"f": dict(fb.rows[jx]["f"]), "r": [c for c in fb.rows[jx]["r"] if fb.rules[c]["mode"] != "line"] + ["DUPROW"], "k": None, "c": {}})

    def render_mo(fb=fb, r=r):
        rows = [["job", "item", "slot", "verdict", "status", "reviewed_at"]]
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            first = W.present.get((f["jid"], f["iid"]), "slot1_candidate") == "slot1_candidate"
            slot = 1 if (f["sub"] == "AB") == first else 2
            cand = "A" if f["sub"] == "AB" else "B"
            word = "tie" if f["v"] == "T" else ("candidate" if f["v"] == cand else "baseline")
            if word == "tie" and "TIE_WORD" in rules:
                word = "="
            st = f["st"].upper() if "STATUS_CASE" in rules else f["st"]
            if "VERDICT_CASE" in rules:
                word = word.capitalize()
            rows.append([v_id(f["jid"], rules, "J"), v_id(f["iid"], rules, "I"), str(slot) if "SLOT_STR" in rules else slot, v_lb(word, rules), st, excel_serial(f["t"])])
        return xlsx_bytes([("reviews", rows)])
    fb.render = render_mo
    out.append(fb)

    # ---------------- scorecard_prelim.xlsx (decoy) ----------------
    name = "scorecard_prelim.xlsx"
    r = rngs(name)
    fb = FB(name, decoy=True, tests=["leaderboard_aggregate", "item_scores_arith"])
    kit_ids(fb, "i", "I", "Item id", "item_registry.csv", ht=("CASE",))
    for code, fam, desc, d, mode in [
        ("PS_SCORE", "T16", "Preliminary per-item correctness agrees with the certified computation for most items and differs for the rest; it is never used as a result.", "pull", "row"),
        ("PS_FINAL", "T16", "The workbook title says board pack FINAL; the policy ranks it as a preliminary working file.", "pull", "row"),
        ("PS_NEWER", "T7", "prepared_at is later than every result source; preparation time is not evidence.", "pull", "line"),
        ("PS_METRIC", "T16", "Preliminary metrics are computed with naive conventions (micro averages, equal-width calibration bins) and do not match the metric definitions.", "pull", "row"),
        ("WEIGHT", "T21", "suite_weight is the board-adopted weight of the item's suite for the leaderboard aggregate; the weight column is authoritative even though the rest of the workbook is not.", "push", "row"),
        ("WEIGHT_UNIFORM", "T17", "All items of one suite carry the same suite_weight; that value is the suite's weight.", "push", "row"),
        ("WEIGHT_FMT", "T4", "Weights can be written with a comma decimal mark.", "push", "line"),
        ("PS_SERIAL", "T3", "Dates are spreadsheet serials in the 1904 date system (days since 1904-01-01).", "pull", "line"),
        ("PS_PCT", "T2", "Preliminary scores are percentages.", "pull", "row"),
        ("PS_ROUND", "T12", "Preliminary values are rounded half-up to two decimals.", "pull", "row"),
        ("PS_STALE", "T13", "Some rows name items retired before the close.", "pull", "row"),
        ("PS_VOID", "T6", "Rows struck through in the board pack are marked struck=yes and void.", "pull", "row"),
        ("PS_SCOPE", "T14", "A cover-sheet note limits the workbook to discussion use.", "pull", "row"),
        ("PS_EQ", "T19", "Preliminary values agree with the rescored judge export and the corrected-gold export; that agreement does not make any of the three authoritative.", "pull", "row"),
        ("PS_OSC", "T18", "Taking the workbook's weights and values together breaks the control reconciliation; dropping the workbook loses the weights; only the weight column is used.", "push", "row"),
        ("PS_DUP", "T20", "Repeated rows are one row.", "pull", "row"),
        ("PS_NULL", "T5", "A blank correctness cell means not yet scored.", "pull", "line"),
        ("PS_HDR", "T8", "Each sheet orders columns differently.", "pull", "row"),
        ("PS_EMBED", "T9", "Model names in one sheet are joined with semicolons in a single cell.", "pull", "row"),
        ("PS_ENC", "T10", "Some cells hold non-breaking spaces.", "pull", "line"),
        ("PS_BOUND", "T11", "The workbook's window runs to 2025-09-30 inclusive end of day, which matches the half-open policy window.", "pull", "row"),
        ("PS_OUT", "T15", "Items with extreme preliminary scores were flagged for review; the flag has no effect.", "pull", "row"),
        ("PS_DEFER", "T22", "Weights adopted by the board apply from the board meeting; the meeting was before the window, so they apply to the whole close.", "push", "row"),
        ("PS_COND", "T17", "Preliminary correctness for multilingual items uses grader g2 for every job.", "pull", "row"),
        ("PS_KEY", "T1", "Model names in the workbook are title-cased.", "pull", "row"),
        ("PS_BAIT", "T20", "A suite_weight of 1 is a real weight, not a placeholder.", "push", "line"),
    ]:
        fb.R(code, fam, desc, POL, [POL, "item_registry.csv"] if code not in ("WEIGHT",) else [POL, "item_scores_placeholder"] if False else [POL, "item_registry.csv"],
             mode=mode, direction=d, fields=["i"] if mode == "line" else None, bait=code in ("PS_DUP", "PS_BAIT"), ht=code in ("PS_SERIAL", "PS_NEWER"))
    fb.rules["PS_BAIT"]["fields"] = ["w1"]
    for iid in sorted(W.items):
        rs = ["WEIGHT"] if r.chance(0.2) else [r.choice(["PS_SCORE", "PS_FINAL", "PS_METRIC", "PS_PCT", "PS_ROUND"])]
        if r.chance(0.2):
            rs.append("WEIGHT_UNIFORM")
        if r.chance(0.04):
            rs.append(r.choice(["PS_STALE", "PS_SCOPE", "PS_EQ", "PS_OSC", "PS_HDR", "PS_EMBED", "PS_BOUND", "PS_OUT", "PS_DEFER", "PS_COND", "PS_KEY", "PS_VOID"]))
        w = W.params["weights"][W.items[iid]["bench"]]
        fb.add({"iid": iid, "i": 1, "w": w, "w1": 1 if w == 1 else None}, rs)
    for i in range(len(fb.rows) // 9):
        j = r.below(len(fb.rows))
        fb.rows.insert(j + 1, {"f": dict(fb.rows[j]["f"]), "r": [c for c in fb.rows[j]["r"] if fb.rules[c]["mode"] != "line"] + ["PS_DUP"], "k": None, "c": {}})

    def render_ps(fb=fb, r=r):
        rows = [["item_id", "suite", "suite_weight", "prelim_correct", "prepared_at", "struck"]]
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            it = W.items[f["iid"]]
            wv = str(f["w"]).replace(".", ",") if "WEIGHT_FMT" in rules else float(f["w"])
            pc = None if "PS_NULL" in rules else r.choice([0, 1])
            iid = v_id(f["iid"], rules, "I")
            if "PS_ENC" in rules:
                iid = iid + "\u00a0"
            rows.append([iid, it["bench"], wv, pc, (T(2025, 10, 2) - T(1904, 1, 1)) / 86400.0, "yes" if "PS_VOID" in rules else "no"])
        return xlsx_bytes([("board_pack_FINAL", rows)])
    fb.render = render_ps
    out.append(fb)

    # ---------------- locale_codes_legacy.tsv (decoy) ----------------
    name = "locale_codes_legacy.tsv"
    r = rngs(name)
    fb = FB(name, decoy=True, tests=["metric_multiling", "item_scores_multiling"])
    kit_ids(fb, "i", "I", "Item id", "item_registry.csv", ht=("CASE",))
    for code, fam, desc, d, mode in [
        ("LL_FULL", "T16", "The legacy table lists a locale for every item; prompt_locales.tsv is the authority for item locales.", "pull", "row"),
        ("LL_AGREE", "T16", "Legacy item locales agree with prompt_locales.tsv for most items and differ for some.", "pull", "row"),
        ("LL_NEWER", "T7", "The legacy table's updated column is later than prompt_locales.tsv revisions; it is an archive refresh date.", "pull", "row"),
        ("MAP", "T13", "Rows of kind map give the deprecated-code mapping (iw to he, in to id, jw to jv, ji to yi, mo to ro); this mapping is authoritative.", "push", "row"),
        ("MAP_CASE", "T1", "Mapping codes can be upper case.", "push", "line"),
        ("LL_SCRIPT", "T10", "Legacy locales for some languages carry a script subtag.", "pull", "line"),
        ("LL_REGION", "T17", "Legacy locales use country codes as languages for some items (BR for pt).", "pull", "row"),
        ("LL_VOID", "T6", "Rows marked retired in the legacy table are void.", "pull", "row"),
        ("LL_DUP", "T20", "Repeated rows are one row.", "pull", "row"),
        ("LL_NULL", "T5", "A locale of ?? means unknown.", "pull", "row"),
        ("LL_HDR", "T8", "A second header swaps the columns.", "pull", "pos"),
        ("LL_FK", "T13", "Rows for unregistered items are ignored.", "pull", "row"),
        ("LL_TS", "T3", "updated is epoch seconds.", "pull", "line"),
        ("LL_ENC", "T10", "The file is Latin-1 in places.", "pull", "row"),
        ("LL_SCOPE", "T14", "The header comment marks the item rows as historical.", "pull", "row"),
        ("LL_EMBED", "T9", "Notes after a tab are free text.", "pull", "row"),
        ("LL_COUNT", "T2", "Support counts in the legacy table are in hundreds.", "pull", "row"),
        ("LL_ROUND", "T12", "Legacy support ratios are rounded.", "pull", "row"),
        ("LL_LOC", "T4", "Legacy support ratios use a comma decimal mark.", "pull", "row"),
        ("LL_BOUND", "T11", "Legacy minimum support is a strict greater-than; the slice definitions use at least.", "pull", "row"),
        ("LL_OUT", "T15", "Rare languages in the legacy table are flagged; the flag has no effect.", "pull", "row"),
        ("LL_PREC", "T21", "For deprecated codes the legacy map decides the language; for item locales prompt_locales.tsv decides.", "push", "row"),
        ("LL_OSC", "T18", "Taking item locales from the legacy table breaks the per-language support counts; ignoring the table leaves deprecated codes unresolved; only the map rows are used.", "push", "row"),
        ("LL_EQ", "T19", "Legacy item locales agree with the preliminary scorecard's language split; that agreement is not evidence.", "pull", "row"),
        ("LL_DEFER", "T22", "Mappings take effect from the locale migration date, which is before the window.", "push", "row"),
        ("LL_BAIT", "T20", "A mapping row whose source and target look alike (in to id) is correct.", "push", "row"),
        ("LL_KEY", "T1", "Item ids in the legacy table are lower case.", "pull", "row"),
        ("LL_SENT", "T5", "A mapping target of - means the code is retired with no successor.", "push", "row"),
        ("LL_DATE", "T3", "The migration date is written as a spreadsheet serial.", "push", "row"),
        ("LL_PUSH2", "T17", "Mapped codes keep the region subtag of the original tag; only the language changes.", "push", "row"),
    ]:
        fb.R(code, fam, desc, POL, [POL, "prompt_locales.tsv"], mode=mode, direction=d, fields=["i"] if mode == "line" else None,
             bait=code in ("LL_DUP", "LL_BAIT"), ht=code in ("LL_TS",))
    fb.rules["MAP_CASE"]["fields"] = ["m"]
    for code_, tgt in sorted(DEPRECATED.items()):
        fb.add({"kind": "map", "code": code_, "tgt": tgt, "i": None, "m": 1}, ["MAP", "LL_PREC", "LL_DEFER", "LL_PUSH2"] + (["LL_BAIT"] if code_ == "in" else []))
    for iid in sorted(W.items):
        lang = W.items[iid]["lang"]
        wrong = r.chance(0.05)
        tag = r.choice(LOCALE_TAG[r.choice(LANGS)] if wrong else LOCALE_TAG[lang])
        rs = [r.choice(["LL_FULL", "LL_AGREE", "LL_NEWER", "LL_SCOPE", "LL_COUNT"])]
        if wrong:
            rs.append(r.choice(["LL_REGION", "LL_EQ", "LL_OSC"]))
        if r.chance(0.04):
            rs.append(r.choice(["LL_VOID", "LL_NULL", "LL_EMBED", "LL_ROUND", "LL_LOC", "LL_BOUND", "LL_OUT", "LL_KEY", "LL_ENC"]))
        fb.add({"kind": "item", "iid": iid, "tag": tag, "i": 1, "m": None}, rs)
    for i in range(len(fb.rows) // 90):
        fb.add({"kind": "item", "iid": fake_item(r, r.choice(sorted(W.items))), "tag": "en", "i": 1, "m": None}, ["LL_FK"])
    for i in range(len(fb.rows) // 9):
        j = r.below(len(fb.rows))
        fb.rows.insert(j + 1, {"f": dict(fb.rows[j]["f"]), "r": [c for c in fb.rows[j]["r"] if fb.rules[c]["mode"] != "line"] + ["LL_DUP"], "k": None, "c": {}})
    fb.rows.append({"f": {"kind": "map", "code": "sh", "tgt": "-", "i": None, "m": 1}, "r": ["MAP", "LL_SENT", "LL_DATE"], "k": None, "c": {}})

    def render_ll(fb=fb, r=r):
        L = ["kind\tkey\tvalue\tupdated"]
        cur = "A"
        for row in fb.rows:
            f, rules = row["f"], row["r"]
            lay = "B" if "LL_HDR" in rules else "A"
            if lay != cur:
                L.append("kind\tvalue\tkey\tupdated" if lay == "B" else "kind\tkey\tvalue\tupdated")
                cur = lay
            upd = str(T(2025, 9, 20)) if "LL_TS" in rules else "2025-09-20"
            if f["kind"] == "map":
                k_ = f["code"].upper() if "MAP_CASE" in rules else f["code"]
                v_ = f["tgt"]
                upd = repr(excel_serial(T(2025, 5, 1))) if "LL_DATE" in rules else "2025-05-01"
                kind = "map"
            else:
                k_ = v_id(f["iid"], rules, "I")
                if "LL_KEY" in rules:
                    k_ = k_.lower()
                v_ = "??" if "LL_NULL" in rules else f["tag"]
                kind = "retired" if "LL_VOID" in rules else "item"
            cells = [kind, k_, v_, upd] if lay == "A" else [kind, v_, k_, upd]
            L.append("\t".join(cells))
        return ("\n".join(L) + "\n").encode("utf-8")
    fb.render = render_ll
    out.append(fb)
    return out

# ---------------------------------------------------------------------------------
# documents: policy, conventions, control totals, precedence, errata, minutes, metrics, methodology
# ---------------------------------------------------------------------------------
PROD_SOURCES = ['results_fleet_a.log', 'results_fleet_b.log', 'results_fleet_c.log', 'code_samples.jsonl', 'judge_verdicts.jsonl', 'scores_shard1.parquet', 'scores_shard2.parquet', 'eval_store.db', 'legacy_results.txt', 'intent_predictions.csv', 'rerun_results.jsonl']


def doc_kit(fb, keyfield, tag, label, master, hdr=True):
    kit_ids(fb, keyfield, tag, label, master, ht=("CASE",))
    fb.R("REV", "T7", f"Where a table in {fb.name} lists a key twice, the row with the higher revision wins.", POL if fb.name != POL else SC, [POL if fb.name != POL else SC, ER], mode="row")
    fb.R("VOID", "T6", f"Rows of {fb.name} tables listed in the errata registry void list are void.", ER if fb.name != ER else POL, [ER if fb.name != ER else POL, POL if fb.name != POL else SC], mode="row")
    if hdr:
        fb.R("HDR", "T8", f"A continuation table in {fb.name} repeats the header with its columns reordered.", SC if fb.name != SC else POL, [SC if fb.name != SC else POL, master], mode="pos")
    fb.R("DUPROW", "T20", f"A table row repeated verbatim in {fb.name} is one row.", POL if fb.name != POL else SC, [POL if fb.name != POL else SC, ER], mode="row", bait=True)
    kit_tab(fb, lb=fb.name in (ER, RM))
    fb.R("CELLQ", "T9", f"Some cells in {fb.name} tables are wrapped in double quotes; the quotes are not part of the value.", SC if fb.name != SC else POL, [SC if fb.name != SC else POL, master], mode="line", fields=["revf"])
    fb.R("NBSPC", "T10", f"The first cell of some {fb.name} table rows ends with a no-break space.", SC if fb.name != SC else POL, [SC if fb.name != SC else POL, master], mode="line", fields=["revf"])


def doc_rows(W, r, fb, keys, canon, alt, fake, p_old=0.08, p_void=0.025, p_fk=0.01):
    for k in keys:
        rev = r.randint(2, 5)
        roll = r.rand()
        if roll < p_old:
            fb.add({"key": k, "v": alt(k), "rev": rev - 1, "kind": "older"}, ["REV"])
        elif roll < p_old + p_void:
            fb.add({"key": k, "v": alt(k), "rev": rev + 1, "kind": "void"}, ["VOID"])
            W.errata_reg.append((fb.name, k, rev + 1))
        fb.add({"key": k, "v": canon(k), "rev": rev, "kind": "canon"}, [])
        if fake and r.chance(p_fk) and "FK" in fb.rules:
            fb.add({"key": fake(k), "v": alt(k), "rev": rev, "kind": "fk"}, ["FK"])
    for row in fb.rows:
        row["f"].update({"revf": 1, "twf": 1, "lbf": 1})
    for i in range(len(fb.rows) // 9):
        j = r.below(len(fb.rows))
        if fb.rows[j]["f"]["kind"] == "canon":
            fb.rows.insert(j + 1, {"f": dict(fb.rows[j]["f"]), "r": ["DUPROW"], "k": None, "c": {}})


def statements_for(all_fbs, doc):
    """Rule statements rendered into one document. A rule whose own doc is not a rendered
    document (a data file such as slice_definitions.yaml) is stated in the source conventions,
    so every rule the corpus applies is written somewhere the solver can read it."""
    out = {}
    for fb in all_fbs:
        for c, ru in sorted(fb.rules.items()):
            target = ru["doc"] if ru["doc"] in DOC_FMT else SC
            if target == doc:
                out.setdefault(fb.name, []).append(ru["desc"])
    return out


def md_table(header, rows):
    L = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for row in rows:
        L.append("| " + " | ".join(str(c).replace("|", "\\|") for c in row) + " |")
    return L


def build_docs_tables(W, rngs):
    """Builds the doc FileBuilds with their tables; prose is attached at render time from all rules."""
    out = []
    P = W.params
    items = sorted(W.items)
    # ---------------- certification_policy.md ----------------
    name = POL
    r = rngs(name)
    fb = FB(name, tests=["item_eligibility", "release_gates", "lineage"])
    doc_kit(fb, "id", "I", "Item id", "item_registry.csv")
    fb.R("FK", "T13", "Scope rows for unregistered items are ignored.", SC, ["item_registry.csv", SC], mode="row")
    fb.R("SCOPE_ALIAS", "T17", "Scope values: in, in_scope and yes mean in scope; held_out, HO and private mean held out.", MD, [MD, "item_registry.csv"], mode="line", fields=["sc"])
    fb.R("ORDER", "T14", "Held-out is the last exclusion reason: an item that is retired, a duplicate or contaminated keeps that reason even when it is also held out.", MD, [MD, "suite_manifest.xlsx", "dedup_clusters.tsv", "contamination_hits.jsonl"], mode="ctx")
    fb.R("SLICE_SCOPE", "T14", "Held-out items take no part in slice metrics either.", MD, [MD, "slice_attributes.csv", "slice_definitions.yaml"], mode="ctx")
    fb.R("ESC", "T9", "Pipes inside table cells are escaped as \\|.", SC, [SC, "item_registry.csv"], mode="line", bait=True, fields=["id"], ht=True)
    fb.R("SCOPE_FROM", "T11", "A held-out entry with an effective date on or after the window end does not apply.", MD, [MD, "suite_manifest.xlsx"], mode="row")
    fb.R("SENT", "T5", "A scope of - means the default, in scope.", MD, [MD, "item_registry.csv"], mode="ctx")
    fb.R("CASE_SC", "T1", "Scope values compare case-insensitively.", MD, [MD, "item_registry.csv"], mode="line", fields=["sc"])
    def scope_c(k):
        return {"s": "held_out" if k in W.held_out else ("-" if r.chance(0.12) else "in")}
    doc_rows(W, r, fb, items, scope_c, lambda k: {"s": "in" if k in W.held_out else "held_out"}, lambda k: fake_item(r, k))
    for k in items:
        if k not in W.held_out and r.chance(0.02):
            fb.rows.insert(r.below(len(fb.rows)), {"f": {"key": k, "v": {"s": "held_out"}, "rev": 9, "kind": "late", "from": WINDOW_END + r.randint(0, 9) * 86400}, "r": ["SCOPE_FROM"], "k": None, "c": {}})
    for row in fb.rows:
        f = row["f"]
        f.update({"id": 1, "sc": 1})
        if f["kind"] == "canon" and f["key"] in W.held_out and W.elig[f["key"]] != "out_of_scope":
            row["r"].append("ORDER")
        if f["kind"] == "canon" and f["v"]["s"] == "-":
            row["r"].append("SENT")
        if f["kind"] == "canon" and f["key"] in W.held_out and W.elig[f["key"]] == "out_of_scope":
            row["r"].append("SLICE_SCOPE")
    fb.table = ("Appendix A - item scope register", ["item_id", "scope", "effective", "revision"], ["scope", "item_id", "revision", "effective"])

    def cells_pol(row, lay, r=r):
        f, rules = row["f"], row["r"]
        s = f["v"]["s"]
        if "SCOPE_ALIAS" in rules:
            s = {"in": "in_scope", "-": "-", "held_out": r.choice(["HO", "private"])}[s]
        if "CASE_SC" in rules:
            s = s.upper()
        eff = time.strftime("%Y-%m-%d", time.gmtime(f.get("from", T(2025, 6, 15))))
        c = [v_id(f["key"], rules, "I"), s, eff, v_tw(v_rev(f["rev"], rules), rules)]
        return c if lay == "A" else [c[1], c[0], c[3], c[2]]
    fb.cells = cells_pol
    out.append(fb)

    # ---------------- source_conventions.md ----------------
    name = SC
    r = rngs(name)
    fb = FB(name, tests=["source_audit_used", "item_scores_arith"])
    doc_kit(fb, "j", "J", "Job id", REG)
    fb.R("FK", "T13", "Routing rows for unregistered jobs are ignored.", POL, [REG, POL], mode="row")
    fb.R("SRC_ALIAS", "T17", "Source names can be written without extension or in upper case.", POL, [POL, REG], mode="line", fields=["src"])
    fb.R("NOCOPY", "T5", "A copy source of - means the job has no second copy.", POL, [POL, FP] + PROD_SOURCES, mode="ctx")
    fb.R("RESTORE", "T22", "A routing entry whose primary is scores_staging.parquet takes effect only for jobs the errata register marks RESTORE.", ER, [ER, "scores_staging.parquet"], mode="row")
    fb.R("RERUNSRC", "T17", "Reruns are routed to rerun_results.jsonl whatever their suite.", RM, [RM, "harness_events.log", "rerun_results.jsonl"], mode="ctx")
    fb.R("ESC", "T9", "Pipes inside table cells are escaped as \\|.", POL, [POL, REG], mode="line", bait=True, fields=["j"], ht=True)
    reg = W.job_ids
    doc_rows(W, r, fb, reg, lambda k: {"p": W.route[k], "c": W.copy_src[k] or "-"},
             lambda k: {"p": r.choice(RESULT_SOURCES[:11]), "c": "-"}, lambda k: fake_job(k, 7))
    for row in fb.rows:
        f = row["f"]
        f.update({"j": 1, "src": 1})
        if f["kind"] == "canon":
            if f["v"]["c"] == "-" and r.chance(0.15):
                row["r"].append("NOCOPY")
            if f["key"] in W.rescue:
                row["r"].append("RESTORE")
            if f["key"] in W.rerun_of:
                row["r"].append("RERUNSRC")
    fb.table = ("Appendix R - job routing", ["job", "primary_source", "copy_source", "revision"], ["job", "copy_source", "primary_source", "revision"])

    def cells_sc(row, lay):
        f, rules = row["f"], row["r"]
        p, c = f["v"]["p"], f["v"]["c"]
        if "SRC_ALIAS" in rules:
            p = p.rsplit(".", 1)[0].upper()
        cc = [v_id(f["key"], rules, "J"), p, c, v_tw(v_rev(f["rev"], rules), rules)]
        return cc if lay == "A" else [cc[0], cc[2], cc[1], cc[3]]
    fb.cells = cells_sc
    out.append(fb)

    # ---------------- control_totals.html ----------------
    name = CT
    r = rngs(name)
    fb = FB(name, tests=["control_reconciliation", "source_audit_rows"])
    doc_kit(fb, "j", "J", "Job id", REG)
    fb.R("FK", "T13", "Control rows for unregistered jobs are ignored.", POL, [REG, POL], mode="row")
    fb.R("SUMFMT", "T4", "value_sum is written with en_US grouping; the de_DE desk's rows use dot grouping and a comma decimal mark.", SC, [SC, INV], mode="line", fields=["sum"])
    fb.R("ROWS_INCL", "T20", "expected_rows is the number of results the job produced (items times samples or orderings), including results for ineligible items.", MD, [MD, REG, "eval_store_mirror.db"] + PROD_SOURCES, mode="ctx", bait=True)
    fb.R("ROWS_TXT", "T4", "expected_rows can carry a rows suffix (40 rows).", MD, [MD, REG], mode="line", fields=["sum"])
    fb.R("SUMDEF", "T17", "value_sum is the sum of the job's primary numeric field (answer, passes, score, confidence) or the count of non-empty answers for text suites.", MD, [MD, REG] + PROD_SOURCES, mode="ctx", cond=True)
    fb.R("ENT", "T9", "Cells use HTML entities.", SC, [SC, REG], mode="line", bait=True, fields=["j"], ht=True)
    def ctl(k):
        res = W.res.get(k, {})
        b = W.jobs[k]["bench"]
        n = len(res)
        if b == "arith":
            s = sum((v["answer"] for v in res.values() if v.get("answer") is not None), Decimal(0))
        elif b == "code":
            s = Decimal(sum(1 for v in res.values() if v["passed"] == v["total"]))
        elif b == "safety":
            s = sum((v["score"] for v in res.values()), Decimal(0))
        elif b == "mcq":
            s = sum((v["conf"] for v in res.values()), Decimal(0))
        elif b == "pref":
            s = Decimal(sum(1 for v in res.values() if v["verdict"] == "A"))
        else:
            s = Decimal(sum(1 for v in res.values() if (v.get("answer") or v.get("label"))))
        return {"n": n, "s": s}
    doc_rows(W, r, fb, W.job_ids, ctl, lambda k: {"n": len(W.res.get(k, {})) + r.randint(1, 3), "s": Decimal(r.randint(1, 999))}, lambda k: fake_job(k, 11))
    for row in fb.rows:
        f = row["f"]
        f.update({"j": 1, "sum": 1})
        if f["kind"] == "canon" and r.chance(0.08):
            row["r"].append("SUMDEF")
        if f["kind"] == "canon" and r.chance(0.02):
            row["r"].append("ROWS_INCL")
    fb.table = ("Per-job control totals", ["job", "expected_rows", "value_sum", "revision"], ["job", "value_sum", "expected_rows", "revision"])

    def cells_ct(row, lay):
        f, rules = row["f"], row["r"]
        s = f["v"]["s"]
        sv = v_num(s, 4 if s != s.to_integral_value() else 0, "de_DE" if "SUMFMT" in rules else "en_US")
        c = [xesc(v_id(f["key"], rules, "J")), str(f["v"]["n"]) + (" rows" if "ROWS_TXT" in rules else ""), sv, v_tw(v_rev(f["rev"], rules), rules)]
        return c if lay == "A" else [c[0], c[2], c[1], c[3]]
    fb.cells = cells_ct
    out.append(fb)

    # ---------------- field_precedence.html ----------------
    name = FP
    r = rngs(name)
    fb = FB(name, tests=["item_scores_mcq", "item_scores_safety", "source_audit_used"])
    doc_kit(fb, "j", "J", "Job id", REG)
    fb.R("FK", "T13", "Class rows for unregistered jobs are ignored.", POL, [REG, POL], mode="row")
    fb.R("CLASS", "T18", "The bridge class reverses the default winner for every field of the job.", POL, [POL, SC], mode="ctx")
    fb.R("BRIDGE_ONLY", "T19", "Only jobs that carry a second copy can be of the bridge class; a bridge entry for a single-copy job is a data-entry error and is treated as standard.", POL, [SC, POL], mode="ctx", bait=True)
    fb.R("CLASS_ALIAS", "T17", "Class can be written std, standard, br or bridge.", POL, [POL, SC], mode="line", fields=["cl"])
    fb.R("CLASS_CASE", "T1", "Class values can be upper-cased.", POL, [POL, SC], mode="line", fields=["cl"])
    fb.R("ENT", "T9", "Cells use HTML entities.", SC, [SC, REG], mode="line", bait=True, fields=["j"], ht=True)
    W.class_err = set()
    doc_rows(W, r, fb, W.job_ids, lambda k: {"c": W.jclass[k]}, lambda k: {"c": "standard" if W.jclass[k] == "bridge" else "bridge"}, lambda k: fake_job(k, 13))
    for row in fb.rows:
        f = row["f"]
        f.update({"j": 1, "cl": 1})
        if f["kind"] == "canon" and f["v"]["c"] == "bridge":
            if W.copy_src[f["key"]]:
                row["r"].append("CLASS")
            else:
                row["r"].append("BRIDGE_ONLY")
    fb.table = ("Appendix - job authority class", ["job", "class", "revision"], ["class", "job", "revision"])

    def cells_fp(row, lay, r=r):
        f, rules = row["f"], row["r"]
        c = f["v"]["c"]
        if "CLASS_ALIAS" in rules:
            c = {"standard": "std", "bridge": "br"}[c]
        if "CLASS_CASE" in rules:
            c = c.upper()
        cc = [xesc(v_id(f["key"], rules, "J")), c, v_tw(v_rev(f["rev"], rules), rules)]
        return cc if lay == "A" else [cc[1], cc[0], cc[2]]
    fb.cells = cells_fp
    out.append(fb)

    # ---------------- review_minutes.docx ----------------
    name = RM
    r = rngs(name)
    fb = FB(name, tests=["job_dispositions"])
    doc_kit(fb, "j", "J", "Job id", REG, hdr=False)
    fb.R("FK", "T13", "Decisions for unregistered jobs are ignored.", POL, [REG, POL], mode="row")
    fb.R("APPROVED", "T22", "rerun-approved makes the rerun authoritative and supersedes the original named in the harness events.", POL, ["harness_events.log", POL, "rerun_results.jsonl", CT], mode="row")
    fb.R("DENIED", "T22", "rerun-denied, or no decision at all for a rerun, leaves the rerun without effect.", POL, ["harness_events.log", POL], mode="row")
    fb.R("EXEMPT", "T14", "exempt-maintenance lets a job submitted inside a maintenance window count.", POL, ["maintenance_windows.ics", POL], mode="row")
    fb.R("DEC_ALIAS", "T17", "Decisions can be written approve, ok, deny, no, exempt.", POL, [POL, "harness_events.log"], mode="line", fields=["dec"])
    fb.R("MEETING", "T3", "Each decision row carries its meeting date; for one job the decision of the latest meeting wins.", POL, [POL, "harness_events.log"], mode="row")
    fb.R("B_ACCEPT", "T20", "accepted is the routine decision and changes nothing.", POL, [POL, REG], mode="ctx", bait=True)
    fb.R("DATE", "T3", "Meeting dates can be written day/month/year.", POL, [POL, "harness_events.log"], mode="line", fields=["dec"], ht=True)
    for j in sorted(W.jobs):
        if j in W.unregistered:
            continue
        if j in W.rerun_of:
            d = W.rerun_decision[j]
            if d == "approved":
                rs = ["APPROVED"]
                dec = "rerun-approved"
            elif d == "denied":
                rs = ["DENIED"]
                dec = "rerun-denied"
            else:
                continue
        elif j in W.exempt:
            rs, dec = ["EXEMPT"], "exempt-maintenance"
        else:
            rs, dec = (["B_ACCEPT"] if r.chance(0.08) else []), "accepted"
        if r.chance(0.04) and j in W.rerun_of:
            fb.add({"key": j, "v": {"d": "rerun-denied" if dec == "rerun-approved" else "rerun-approved"}, "rev": 1, "kind": "older", "j": 1, "dec": 1}, ["MEETING"])
        elif r.chance(0.04):
            fb.add({"key": j, "v": {"d": "exempt-maintenance" if dec != "exempt-maintenance" else "accepted"}, "rev": 1, "kind": "older", "j": 1, "dec": 1}, ["REV"])
        elif r.chance(0.015):
            fb.add({"key": j, "v": {"d": "exempt-maintenance" if dec != "exempt-maintenance" else "accepted"}, "rev": 3, "kind": "void", "j": 1, "dec": 1}, ["VOID"])
            W.errata_reg.append((name, j, 3))
        fb.add({"key": j, "v": {"d": dec}, "rev": 2, "kind": "canon", "j": 1, "dec": 1}, rs)
        if r.chance(0.008):
            fb.add({"key": fake_job(j, 3), "v": {"d": "rerun-approved"}, "rev": 2, "kind": "fk", "j": 1, "dec": 1}, ["FK"])
    for i in range(len(fb.rows) // 70):
        jx = r.below(len(fb.rows))
        if fb.rows[jx]["f"]["kind"] == "canon":
            fb.rows.insert(jx + 1, {"f": dict(fb.rows[jx]["f"]), "r": ["DUPROW"], "k": None, "c": {}})
    for row in fb.rows:
        row["f"].update({"revf": 1, "twf": 1, "lbf": 1})
    fb.table = ("Decisions", ["job", "decision", "meeting"], None)

    def cells_rm(row, lay, r=r):
        f, rules = row["f"], row["r"]
        d = f["v"]["d"]
        if "DEC_ALIAS" in rules:
            d = {"rerun-approved": "approve", "rerun-denied": "deny", "exempt-maintenance": "exempt", "accepted": "ok"}[d]
        day = 22 + f["rev"]
        md = f"{day}/09/2025" if "DATE" in rules else f"2025-09-{day}"
        return [v_id(f["key"], rules, "J"), v_lb(v_tw(d, rules), rules), md + (" r" + str(f["rev"]) if "REV_TXT" in rules else "")]
    fb.cells = cells_rm
    out.append(fb)

    # ---------------- metric_definitions.pdf ----------------
    name = MD
    r = rngs(name)
    fb = FB(name, tests=["item_scores_longctx", "metric_code", "calibration_ece", "metric_auroc"])
    doc_kit(fb, "i", "I", "Item id", "item_registry.csv")
    fb.R("SHARD_PAD", "T4", "Shard numbers can be zero-padded to four digits.", MA, [MA, REG], mode="line", fields=["s"])
    fb.R("SUITE_CASE", "T1", "Suite names in the shard map can be upper-cased.", POL, [POL, REG], mode="line", fields=["s"], excl=("SUITE_ALIAS",))
    fb.R("ORD_PAD", "T4", "Ordinals can be zero-padded to two digits.", MA, [MA, "eval_store.db"], mode="line", fields=["s"])
    fb.R("SPLITROW", "T9", "A table row too long for the page continues on the next text line; a line ending in a backslash is joined with the line after it.", SC, [SC, REG], mode="line", fields=["s"])
    fb.R("BASE1", "T2", "Rows in continuation tables number ordinals from 1.", MA, [MA, REG], mode="pos")
    fb.R("SUITE_ALIAS", "T17", "Suite names in the shard map can be legacy names.", POL, [POL, REG], mode="line", fields=["s"])
    fb.R("ORD", "T11", "Ordinals run from 0 to shard size minus 1 in the main table; ordinal 0 is the first item of the shard.", MA, [MA, "eval_store.db"], mode="ctx", bait=True)
    fb.R("FK", "T13", "Shard map rows for unregistered items are ignored.", POL, ["item_registry.csv", POL], mode="row")
    pos = {}
    for b in BENCH_KEYS:
        for sn, sh in enumerate(W.shards[b]):
            for o, iid in enumerate(sh):
                pos[iid] = (b, sn, o)
    doc_rows(W, r, fb, items, lambda k: {"b": pos[k][0], "s": pos[k][1], "o": pos[k][2]}, lambda k: {"b": pos[k][0], "s": pos[k][1] + 1, "o": pos[k][2]}, lambda k: fake_item(r, k))
    for row in fb.rows:
        row["f"].update({"i": 1, "s": 1})
        if row["f"]["kind"] == "canon" and row["f"]["v"]["o"] == 0 and r.chance(0.5):
            row["r"].append("ORD")
    fb.table = ("Appendix S - shard map", ["suite", "shard", "ordinal", "item_id", "revision"], ["item_id", "suite", "shard", "ordinal", "revision"])

    def cells_md(row, lay):
        f, rules = row["f"], row["r"]
        v = f["v"]
        suite = LEGACY_SUITE[v["b"]] if "SUITE_ALIAS" in rules else (v["b"].upper() if "SUITE_CASE" in rules else v["b"])
        o = v["o"] + (1 if "BASE1" in rules else 0)
        c = [suite, f"{v['s']:04d}" if "SHARD_PAD" in rules else str(v["s"]), f"{o:02d}" if "ORD_PAD" in rules else str(o), v_id(f["key"], rules, "I"), v_tw(v_rev(f["rev"], rules), rules)]
        return c if lay == "A" else [c[3], c[0], c[1], c[2], c[4]]
    fb.cells = cells_md
    fb.rules["HDR"]["mode"] = "pos"
    out.append(fb)

    # ---------------- methodology_appendix.pdf ----------------
    name = MA
    r = rngs(name)
    fb = FB(name, tests=["significance_counts", "metric_accuracy"])
    doc_kit(fb, "i", "I", "Item id", "item_registry.csv")
    kit_ids(fb, "ref", "REF", "Legacy item code", "baseline_reference.csv")
    fb.R("FK", "T13", "Crosswalk rows for unregistered items are ignored.", POL, ["item_registry.csv", POL], mode="row")
    fb.R("CODE_SPACE", "T1", "Legacy codes can be written with a space after LC (LC 457842).", POL, [POL, "baseline_reference.csv"], mode="line", fields=["ref"])
    fb.R("ITEM_STAR", "T20", "An asterisk after an item id marks an item added this quarter; it is a footnote marker, not part of the id.", POL, [POL, "item_registry.csv"], mode="line", bait=True, fields=["i"])
    fb.R("SPLITROW", "T9", "A table row too long for the page continues on the next text line; a line ending in a backslash is joined with the line after it.", SC, [SC, "baseline_reference.csv"], mode="line", fields=["i"])
    fb.R("MULTI", "T17", "A legacy code maps to exactly one item; a code listed with two items keeps the higher revision.", POL, [POL, "baseline_reference.csv"], mode="ctx")
    doc_rows(W, r, fb, items, lambda k: {"c": W.legacy_code[k]}, lambda k: {"c": f"LC{r.randint(100000, 999999)}"}, lambda k: fake_item(r, k))
    for row in fb.rows:
        row["f"].update({"i": 1, "ref": 1})
        if row["f"]["kind"] == "older":
            row["r"].append("MULTI")
    fb.table = ("Appendix L - legacy item code crosswalk", ["legacy_code", "item_id", "revision"], ["item_id", "legacy_code", "revision"])

    def cells_ma(row, lay):
        f, rules = row["f"], row["r"]
        code = v_id(f["v"]["c"], rules, "REF")
        if "CODE_SPACE" in rules:
            code = code[:2] + " " + code[2:]
        c = [code, v_id(f["key"], rules, "I") + ("*" if "ITEM_STAR" in rules else ""), v_tw(v_rev(f["rev"], rules), rules)]
        return c if lay == "A" else [c[1], c[0], c[2]]
    fb.cells = cells_ma
    out.append(fb)
    # ---------------- errata_register.docx ----------------
    name = ER
    r = rngs(name)
    fb = FB(name, tests=["job_dispositions", "item_scores_arith", "source_audit_used"])
    kit_ids(fb, "key", "RID", "Row id", "results_fleet_a.log", ht=("CASE",))
    fb.R("RID_SRC", "T20", "A row void entry names its source file; it voids that row in that file only.", POL, [POL, "eval_store_mirror.db"] + PROD_SOURCES, mode="ctx", bait=True)
    fb.R("SRC_ALIAS", "T17", "Source files can be named without extension.", POL, [POL, SC], mode="line", fields=["src"])
    fb.R("J_CASE", "T1", "Job ids in the job void list can be in the wrong case.", POL, [POL, REG], mode="line", fields=["jv"])
    for gname, gdesc in (("items", "item registry, gold, dedup, context and slice files"), ("items2", "locale, manifest, scoring parameter and alias files"), ("jobs", "job, checkpoint and tag registries"), ("hosts", "host inventory and clock files"), ("docs", "document tables")):
        fb.R("VE_" + gname, "T17", f"VOID-ENTRY rows for {gdesc} name the file, the key and the revision (or snapshot or seq) of the voided entry.", POL, [POL, SC], mode="ctx")
    fb.R("LINEBREAK", "T10", "Cells can end with a carriage return and line feed; strip them.", SC, [SC, POL], mode="line", fields=["lbf"])
    fb.R("UNDO", "T7", "An UNDO entry cancels an earlier entry with the same target.", POL, [POL, SC], mode="row")
    fb.R("WRAP", "T9", "Long targets wrap inside the table cell with a line break.", SC, [SC, POL], mode="line", bait=True, fields=["key"], ht=True)
    fb.R("DATE", "T3", "logged dates are day/month/year.", SC, [SC, POL], mode="line", fields=["key"])
    fb.R("SHARD", "T13", "EXCLUDE-SHARD entries list training shards whose contamination scans do not count.", MD, [MD, "contamination_hits.jsonl"], mode="row")
    fb.R("RESTORE_E", "T22", "RESTORE entries name jobs whose primary rows were lost; the job's rows come from the staging snapshot.", POL, ["scores_staging.parquet", POL], mode="row")
    fb.R("BASEV", "T6", "VOID-BASELINE entries name a baseline item (item id) and revision date.", POL, ["baseline_reference.csv", POL], mode="row")
    fb.R("JOBV", "T6", "VOID-JOB entries void every row of the job.", POL, [REG, POL, CT], mode="row")
    fb.R("DUPENTRY", "T20", "An entry repeated verbatim is one entry.", POL, [POL, SC], mode="row", bait=True)
    ents = []
    for s, rid in W.row_void:
        ents.append(("VOID-ROW", s, rid))
    for f_, k_, rv in W.errata_reg:
        ents.append(("VOID-ENTRY", f_, f"{k_} rev {rv}"))
    for j in sorted(W.job_void):
        ents.append(("VOID-JOB", "-", j))
    for iid, rv in getattr(W, "base_void", []):
        ents.append(("VOID-BASELINE", "baseline_reference.csv", f"{iid} {time.strftime('%Y-%m-%d', time.gmtime(rv))}"))
    for j in sorted(W.rescue):
        ents.append(("RESTORE", "scores_staging.parquet", j))
    for sh in W.shard_excluded:
        ents.append(("EXCLUDE-SHARD", "-", sh))
    r.shuffle(ents)
    for kind, src, tgt in ents:
        grp = "items" if src in ("item_registry.csv", "gold_labels.tsv", "dedup_clusters.tsv", "context_lengths.csv", "slice_attributes.csv", "slice_definitions.yaml") else \
            "items2" if src in ("prompt_locales.tsv", "suite_manifest.xlsx", "scoring_parameters.xlsx", "label_aliases.json") else \
            ("hosts" if src in (INV, CLK) else ("docs" if src in DOC_FMT else "jobs"))
        rs = {"VOID-ROW": [], "VOID-ENTRY": ["VE_" + grp], "VOID-JOB": ["JOBV"], "VOID-BASELINE": ["BASEV"], "RESTORE": ["RESTORE_E"], "EXCLUDE-SHARD": ["SHARD"]}[kind]
        if kind == "VOID-ROW" and tgt in W._void_rid_multi:
            rs = rs + ["RID_SRC"]
        fb.add({"kind_": kind, "src_": src, "tgt": tgt, "key": 1 if kind == "VOID-ROW" else None, "src": 1 if src != "-" else None, "jv": 1 if kind == "VOID-JOB" else None, "kind": "canon", "lbf": 1}, rs)
    for i in range(max(10, len(fb.rows) // 100)):
        j = r.below(len(fb.rows))
        f = fb.rows[j]["f"]
        if f["kind_"] == "VOID-ROW":
            n_ = int(f["tgt"][1:]) + 1
            taken = {(e[1], e[2]) for e in ents}
            while (f["src_"], f"r{n_:07d}") in taken:
                n_ += 1
            fake = f"r{n_:07d}"
            fb.rows.insert(j, {"f": dict(f, tgt=fake), "r": ["UNDO"], "k": None, "c": {}})
            fb.rows.insert(j + 2, {"f": dict(f, tgt=fake, kind_="UNDO"), "r": ["UNDO"], "k": None, "c": {}})
    for i in range(len(fb.rows) // 12):
        j = r.below(len(fb.rows))
        if fb.rows[j]["f"]["kind_"] not in ("UNDO",):
            fb.rows.insert(j + 1, {"f": dict(fb.rows[j]["f"]), "r": [c for c in fb.rows[j]["r"] if fb.rules[c]["mode"] != "line"] + ["DUPENTRY"], "k": None, "c": {}})
    fb.table = ("Register", ["entry", "kind", "source", "target", "logged"], None)

    def cells_er(row, lay, r=r):
        f, rules = row["f"], row["r"]
        tgt = f["tgt"]
        if f["kind_"] == "VOID-ROW":
            tgt = v_id(tgt, rules, "RID")
        if f["kind_"] == "VOID-JOB" and "J_CASE" in rules:
            tgt = tgt.lower()
        src = f["src_"]
        if "SRC_ALIAS" in rules and src != "-":
            src = src.rsplit(".", 1)[0]
        if "WRAP" in rules:
            tgt = tgt[:4] + "\n" + tgt[4:] if len(tgt) > 6 else tgt
        logged = time.strftime("%d/%m/%Y", time.gmtime(T(2025, 9, 1) + r.randint(0, 30) * 86400))
        return [str(len(row["f"]["tgt"]) % 7), f["kind_"], src, v_lb(tgt, rules), logged]
    fb.cells = cells_er
    out.append(fb)

    return out

# ---------------------------------------------------------------------------------
# document prose (parameters live here; every rule statement is appended per source)
# ---------------------------------------------------------------------------------
def prose_policy(W):
    P = W.params
    conf = ", ".join(f"{v} for {k}" for k, v in sorted(list(HOMO.items()) + list(HOMO_L.items())))
    return [
        ("h", "Heron evaluation certification policy, Q3 2025 close"),
        ("p", "This policy governs the certified scorecard for the Q3 2025 candidate checkpoints. Where sources overlap or disagree, the rules below and the per-source notes decide; a value is never taken from a file just because it is newer, more complete or labelled final."),
        ("h", "Source authority"),
        ("p", "The baseline model is osprey-13b-prod. Candidate models are the model aliases of the run registry."),
        ("p", "Production result sources are results_fleet_a.log, results_fleet_b.log, results_fleet_c.log, code_samples.jsonl, judge_verdicts.jsonl, scores_shard1.parquet, scores_shard2.parquet, eval_store.db, legacy_results.txt, intent_predictions.csv and rerun_results.jsonl. The baseline reference is baseline_reference.csv."),
        ("p", "The following files are not authoritative for results or registry values, with the single exceptions stated: scores_staging.parquet (only the rows of jobs the errata register marks RESTORE), eval_store_mirror.db (only its void_requests table), judge_verdicts_rescored.jsonl (only the presentation field), checkpoint_lineage_snapshot.json (only entries with ema true), run_registry_export.xml (only the legacy_no map), locale_codes_legacy.tsv (only rows of kind map), gold_labels_corrected.csv (only the dispute_ticket to item map) and scorecard_prelim.xlsx (only the suite_weight column, which is the board-adopted leaderboard weight of the item's suite)."),
        ("h", "Identifier grammar"),
        ("p", "Job ids are J followed by 7 digits. Item ids are a suite prefix (ARI, COD, INT, SAF, MCQ, PRF, LCX, MLG), a hyphen and 5 digits. Host names are node- and 4 digits. Checkpoint ids are ck- and 10 lower-case hex digits. Change tickets are CHG- and 5 digits; dispute tickets are DSP- and 5 digits; legacy item codes are LC and 6 digits; row ids are r and 7 digits. Canonical case is as written here. Values can arrive in the wrong case, without zero padding, with surrounding spaces or no-break spaces, or with a Cyrillic look-alike letter; the confusables are " + conf + "."),
        ("h", "Model aliases and checkpoints"),
        ("p", "Each model alias is certified on exactly one checkpoint: the checkpoint of the latest tag event (promotion or rollback) for that alias that took effect. A tag event takes effect at the Date of its APPROVED message in evalops_notifications.mbox when that Date is at or before the cutoff 2025-10-03T18:00:00Z and no REJECTED message exists for the ticket. Events without an approval, with a rejection, or approved after the cutoff have no effect; they are counted as voided promotions of the alias."),
        ("h", "Job dispositions"),
        ("p", "Every registered job gets exactly one disposition, decided in this order (the first that applies): voided (errata job void list), staging_host (the job's host is in fleet s in the inventory entry for the ISO week of the submission instant), stale_checkpoint (the job ran a checkpoint other than its alias's certified checkpoint), outside_window (submission instant outside 2025-07-01T00:00:00Z inclusive to 2025-10-01T00:00:00Z exclusive), maintenance (submitted inside a maintenance window of its host, DTSTART inclusive, DTEND exclusive, without an exemption in the review minutes), superseded (an approved rerun replaces it), rerun_denied (it is a rerun without an approval) and otherwise authoritative. The submission instant is the earliest SUBMIT line of the job in harness_events.log after zone and clock correction. For each model, suite and shard exactly one job is authoritative."),
        ("h", "Item eligibility"),
        ("p", "An item is ineligible for the first of these reasons that applies: retired (suite manifest), duplicate (a non-canonical member of a dedup cluster), contaminated (a live contamination scan at or above the suite threshold), out_of_scope (held out in Appendix A). Otherwise it is eligible. Only eligible items are scored."),
        ("h", "Release gates"),
        ("p", f"A candidate is released when all four gates hold: its leaderboard aggregate is at least the baseline aggregate (compared exactly before rounding); none of its gated suites (arith, mcq, longctx, multiling) is regressed; its multiple-choice expected calibration error is at most {P['ece_cap']}; its safety AUROC is at least {P['auroc_floor']}."),
    ]


def prose_conventions(W, fbs):
    L = [("h", "Source conventions"),
         ("p", "Host-written times are host wall-clock time unless they carry an explicit zone. Zone, locale and score scale follow the host inventory entry for the ISO week (UTC) of the job's submission instant, and every row of a job uses that entry. Offsets during the window: UTC +00:00, Europe/Berlin +02:00, America/Chicago -05:00, Asia/Kolkata +05:30, America/Sao_Paulo -03:00. Clock offsets are host clock minus true time in milliseconds; subtract them from host-written times."),
         ("p", "Number formats by locale: en_US 1,234.50; de_DE 1.234,50; fr_FR 1 234,50; en_IN 12,34,567.50. Documented precisions: arithmetic answers 2 decimals, safety scores 3 decimals, confidences 4 decimals, contamination overlaps 4 decimals. A pct scale divides by 100 (precision drops by 2 decimals in the written unit)."),
         ("p", "Parquet row groups hold 1000 rows each, numbered from 0."),
         ("p", "legacy_results.txt is fixed width. Layout A: RID columns 1-9, JOB 10-19, ITEM 20-30, ANSWER 31-50 (right-aligned), EMIT 51-65 (right-aligned, YYYYMMDDHHMMSS), then a space and HOST. Layout B: RID 1-9, HOST 10-20, JOB 21-30, POS 31-33 (right-aligned), EMIT 34-48, ANSWER 49-68."),
         ("p", "suite_manifest.xlsx sheets hold these suites: core (arith, intent), reasoning (mcq, longctx), safety_code_pref (safety, code, pref), multilingual (multiling).")]
    for fb in fbs:
        if getattr(fb, "rg_sec", None):
            L.append(("p", f"{fb.name}: row groups {', '.join(str(g) for g in sorted(fb.rg_sec))} store emitted as epoch seconds."))
    return L


def prose_precedence(W):
    L = [("h", "Field precedence"),
         ("p", "When one job's results appear in two production sources, each field is taken from the winning source below. Jobs of the bridge authority class (appendix) reverse the winner for every field. A job with a single copy takes every field from that copy.")]
    rows = []
    for (b, f), win in sorted(W.prec.items()):
        srcs = PAIRS[b]
        if b == "intent":
            pair = [(srcs[0], srcs[2]), (srcs[1], srcs[2])]
        else:
            pair = [(srcs[0], srcs[1])]
        for a, c in pair:
            fam_a = a if b != "intent" else a
            winner = (a if win == "primary_family" else c) if b != "intent" else (a if win == "primary_family" else c)
            rows.append([b, f, a, c, winner])
    L.append(("t", [["suite", "field", "source_1", "source_2", "winner"]] + rows))
    return L


def prose_metrics(W):
    P = W.params
    th = ", ".join(f"{b} {W.contam_threshold[b]}" for b in BENCH_KEYS)
    return [
        ("h", "Metric definitions"),
        ("p", "All metrics are computed exactly (rational arithmetic) over eligible items and rounded only when reported: to 6 decimals, half to even."),
        ("p", "arith: correct when the answer, rounded half-even to 2 decimals, is within the item tolerance: exact means equal at 2 decimals, abs means |answer - gold| <= 0.01, rel means |answer - gold| <= |gold| / 100. N/A is an abstention and wrong. Primary metric: accuracy."),
        ("p", "code: a sample passes when passed equals the problem's test count. With c passing samples of n = 10, pass@k = 1 - C(n - c, k) / C(n, k) per problem, averaged over problems; report pass@1 and pass@5. Primary metric: pass@1."),
        ("p", "intent: predicted raw labels resolve through label_aliases.json under the job's taxonomy version; certified values use taxonomy v2 class names. Macro F1 averages per-class F1 = 2TP / (2TP + FP + FN) over the classes that occur as gold or prediction among eligible items."),
        ("p", "safety: AUROC of the score against gold (1 = unsafe), with tied scores counted one half (Mann-Whitney)."),
        ("p", "mcq: accuracy of the chosen option. Expected calibration error uses 10 equal-mass bins: sort items by confidence ascending, ties by item id; bin sizes are N // 10, and the first N mod 10 bins get one more item; ECE = sum over bins of (bin size / N) * |bin accuracy - bin mean confidence|."),
        ("p", "pref: for each item the two orderings are judged; a judgment is a win only when both orderings prefer the candidate, a loss only when both prefer the baseline, and a tie otherwise. win rate = (wins + ties / 2) / items."),
        ("p", "longctx: correct when the normalised answer equals the normalised gold (NFC, case-folded, whitespace collapsed, surrounding punctuation . , ; : ! ? \" ' removed) and the prompt token count for the model's tokenizer is at most the model's context window; longer prompts are wrong."),
        ("p", "multiling: graders g2 and g3 normalise like longctx; g3 also removes combining marks. Per-language accuracy uses the language of the item's prompt locale; languages with fewer than lang_min_support eligible items (slice definitions) are left out; the suite metric is the mean over the remaining languages."),
        ("p", "Normalised score per suite = (metric - chance) / (1 - chance) with chance 0 for arith, code, longctx and multiling, 1/12 for intent, 1/2 for safety and pref, and the exact mean of 1/n_options over eligible items for mcq. The baseline's pref metric is 1/2 by definition. The leaderboard aggregate is the weighted mean of the eight normalised scores using the board-adopted suite weights."),
        ("p", "Contamination thresholds: " + th + "."),
        ("p", "Slice metrics are accuracies of the gated suites over eligible items matching the slice; a slice below min_support items is reported as null."),
    ]


def prose_methodology(W):
    P = W.params
    return [
        ("h", "Methodology appendix"),
        ("p", f"Significance against the baseline uses the exact two-sided McNemar test on items eligible in the suite: b counts items the candidate gets right and the baseline wrong, c the reverse; p = min(1, 2 * sum over i = 0..min(b, c) of C(b + c, i) / 2^(b + c)), and p = 1 when b + c = 0. A suite is improved when p < {P['alpha']} and b > c, regressed when p < {P['alpha']} and c > b, otherwise no_change."),
        ("p", "Judge models: jm-1 writes A, B or T for first shown, second shown, tie; jm-2 writes 1, 2 or 0. jm-3 (rescored export) is not approved. The presentation field of the rescored export says whether slot 1 showed the candidate (slot1_candidate) or the baseline (slot1_baseline); in ordering AB the candidate is shown first."),
        ("p", "Boundaries: the window is half-open; a row emitted exactly at its job's seal is inside the seal; an approval exactly at the cutoff counts; contamination thresholds and tolerances are inclusive."),
        ("p", "Leaderboard ties are broken by higher unrounded pass@1, then by model alias in ascending order."),
        ("p", "The baseline is graded with grader g3 and tokenizer ospsp with a 16384 token window."),
    ]


def _ascii(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def render_doc(fb, prose, statements, fmt):
    title, ha, hb = fb.table
    blocks = list(prose)
    blocks.append(("h", "Per-source notes"))
    for src in sorted(statements):
        blocks.append(("p", f"{src}:"))
        for s_ in statements[src]:
            blocks.append(("li", s_))
    # table segments
    segs = []
    cur, buf = "A", []
    for row in fb.rows:
        lay = "B" if ("HDR" in row["r"] or "BASE1" in row["r"]) and hb else "A"
        if lay != cur and buf:
            segs.append((cur, buf))
            buf = []
        cur = lay
        cells = list(fb.cells(row, lay))
        if "CELLQ" in row["r"] and len(cells) > 1:
            cells[1] = '"' + cells[1] + '"'
        if "NBSPC" in row["r"]:
            cells[0] = cells[0] + "\u00a0"
        buf.append((cells, "SPLITROW" in row["r"]) if fmt == "pdf" else cells)
    if buf:
        segs.append((cur, buf))
    if fmt == "md":
        L = []
        for kind, val in blocks:
            if kind == "h":
                L.append(("# " if not L else "## ") + val)
            elif kind == "p":
                L.append("")
                L.append(val)
            elif kind == "li":
                L.append("- " + val)
            elif kind == "t":
                L.append("")
                L += md_table(val[0], val[1:])
        L.append("")
        L.append("## " + title)
        for lay, rows in segs:
            L.append("")
            L += md_table(ha if lay == "A" else hb, rows)
        return ("\n".join(L) + "\n").encode("utf-8")
    if fmt == "html":
        L = ["<!DOCTYPE html>", "<html><head><meta charset=\"utf-8\"><title>" + xesc(fb.name) + "</title></head><body>"]
        inlist = False
        for kind, val in blocks:
            if kind != "li" and inlist:
                L.append("</ul>")
                inlist = False
            if kind == "h":
                L.append(f"<h2>{xesc(val)}</h2>")
            elif kind == "p":
                L.append(f"<p>{xesc(val)}</p>")
            elif kind == "li":
                if not inlist:
                    L.append("<ul>")
                    inlist = True
                L.append(f"<li>{xesc(val)}</li>")
            elif kind == "t":
                L.append("<table>")
                L.append("<tr>" + "".join(f"<th>{xesc(c)}</th>" for c in val[0]) + "</tr>")
                for row in val[1:]:
                    L.append("<tr>" + "".join(f"<td>{xesc(c)}</td>" for c in row) + "</tr>")
                L.append("</table>")
        if inlist:
            L.append("</ul>")
        L.append(f"<h2>{xesc(title)}</h2>")
        for lay, rows in segs:
            L.append('<table class="data">')
            L.append("<tr>" + "".join(f"<th>{c}</th>" for c in (ha if lay == "A" else hb)) + "</tr>")
            for row in rows:
                L.append("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>")
            L.append("</table>")
        L.append("</body></html>")
        return ("\n".join(L) + "\n").encode("utf-8")
    if fmt == "docx":
        out = []
        for kind, val in blocks:
            if kind == "li":
                out.append(("p", "\u2022 " if False else "* " + val))
            elif kind == "t":
                out.append(("t", val))
            else:
                out.append((kind, val))
        out.append(("h", title))
        for lay, rows in segs:
            out.append(("t", [ha if lay == "A" else hb] + rows))
        return docx_bytes(out)
    if fmt == "pdf":
        import textwrap as _tw
        L = []
        for kind, val in blocks:
            if kind == "t":
                for row in val:
                    L.append(" | ".join(_ascii(str(c)) for c in row))
                continue
            text = _ascii(val)
            pre = "== " if kind == "h" else ("* " if kind == "li" else "")
            for i, ln in enumerate(_tw.wrap(text, 160) or [""]):
                L.append((pre if i == 0 else "  ") + ln)
        L.append("== " + title)
        for lay, rows in segs:
            L.append("TABLE " + " | ".join(ha if lay == "A" else hb))
            for row, split in rows:
                cells = [_ascii(str(c)) for c in row]
                if split:
                    L.append(" | ".join(cells[:2]) + " \\")
                    L.append("  " + " | ".join(cells[2:]))
                else:
                    L.append(" | ".join(cells))
        return pdf_bytes(L)
    raise ValueError(fmt)

# ---------------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------------
DOC_FMT = {POL: "md", SC: "md", CT: "html", FP: "html", ER: "docx", RM: "docx", MD: "pdf", MA: "pdf"}


def assign_pos(fb, rng):
    pos_rules = sorted((c for c, ru in fb.rules.items() if ru["mode"] == "pos"), key=lambda c: (c != "HDR", c))
    if not pos_rules:
        return
    n = len(fb.rows)
    head_n = min(2000, n // 5)
    lo, hi = head_n, n - head_n
    fb.rg_sec = []
    seg_of = {}
    for c in pos_rules:
        if fb.name == MD and c == "BASE1" and "HDR" in seg_of:
            seg_of[c] = seg_of["HDR"]
            continue
        if c == "RG_SEC":
            groups = [g for g in range(n // 1000 + 1) if g * 1000 >= lo and (g + 1) * 1000 <= hi]
            k = 1 if len(groups) < 6 else 2
            chosen = sorted(groups[i] for i in sorted({rng.below(len(groups)) for _ in range(k)}))
            fb.rg_sec = chosen
            seg_of[c] = [range(g * 1000, (g + 1) * 1000) for g in chosen]
            continue
        ln = max(300, int(0.08 * n))
        st = lo + rng.below(max(1, hi - lo - ln))
        seg_of[c] = [range(st, min(hi, st + ln))]
    for c, segs in seg_of.items():
        ex = fb.rules[c]["excl"]
        for sg in segs:
            for i in sg:
                row = fb.rows[i]
                if row["k"] == "anchor":
                    continue
                row["r"] = [x for x in row["r"] if x not in ex] + [c]
    for row in fb.rows:
        if row["k"] == "anchor":
            continue
        bait = any(fb.rules[c]["bait"] for c in row["r"])
        row["k"] = "bait" if bait else ("trap" if row["r"] else "plain")


def source_audit_truth(W, fbs):
    reviewed = {(j, i, s) for j, i, s, v, st, t in W.reviews if st == "final"}
    mv = set(W.mirror_void)
    out = {}
    for fb in fbs:
        if fb.name not in RESULT_SOURCES:
            continue
        seen = set()
        n = used = 0
        for row in fb.rows:
            x = row["f"].get("x")
            if x is None or row["k"] == "anchor" or x.kind == "rev":
                continue
            n += 1
            if id(x) in seen:
                continue
            seen.add(id(x))
            ok = used_row(W, x)
            if ok and fb.name == "judge_verdicts.jsonl" and (x.job, x.item, x.sub) in reviewed:
                ok = False
            if ok and (fb.name, x.rid) in mv:
                ok = False
            if ok and x.ctx.get("sentinel"):
                ok = False
            used += 1 if ok else 0
        out[fb.name] = {"result_rows": n, "used": used, "discarded": n - used}
    return out


def control_truth(W, truth):
    out = {}
    tot = {"authoritative_jobs": 0, "scored_items": 0, "expected_results": 0}
    for m in CANDIDATES:
        aj = [j for j, d in W.disp.items() if d == "authoritative" and W.jobs[j]["model"] == m]
        si = sum(1 for x in truth["item_scores.jsonl"] if x["model"] == m)
        ex = sum(len(W.res[j]) for j in aj)
        out[m] = {"authoritative_jobs": len(aj), "scored_items": si, "expected_results": ex}
        for k in tot:
            tot[k] += out[m][k]
    out["_total"] = tot
    return out


def generate_corpus(seed, scale=1.0):
    W = build_world(seed, scale)
    build_aliases(W, seed)
    truth = compute_truth(W)
    plan_results(W, seed)
    gr = derive(seed, "gold_err")
    W.gold_err = {k: True for k in sorted(W.items) if W.items[k]["bench"] != "pref" and gr.chance(0.04)}
    W.errata_reg = []
    allv = W.row_void + W.mirror_void
    W._void_rids_other = {s: {rid for s2, rid in allv if s2 != s} for s in RESULT_SOURCES}
    present = {}
    for s in RESULT_SOURCES:
        for x in W.rows[s]:
            present.setdefault(x.rid, set()).add(s)
    W._void_rid_multi = {rid for s, rid in allv if len(present.get(rid, ())) > 1}
    rngs = lambda name: derive(seed, "file|" + name)
    FB._W = W
    fbs = []
    fbs += build_logs(W, rngs)
    fbs += build_results2(W, rngs)
    fbs += build_results3(W, rngs)
    fbs += build_registries_items(W, rngs)
    fbs += build_item_files(W, rngs)
    fbs += build_item_files2(W, rngs)
    fbs += build_lineage(W, rngs)
    fbs += build_hostjob(W, rngs)
    fbs += build_jobs_files(W, rngs)
    fbs += build_misc(W, rngs)
    docs = build_docs_tables(W, rngs)
    fbs += docs
    add_decoy_conflicts(fbs)
    for fb in fbs:
        arrange(fb, rngs("arrange|" + fb.name))
        assign_pos(fb, rngs("pos|" + fb.name))
    files = {}
    for fb in fbs:
        if fb.name in DOC_FMT:
            continue
        files[fb.name] = fb.render()
    prose = {POL: prose_policy(W), SC: prose_conventions(W, fbs), CT: [("h", "Control totals"), ("p", "Per-job control figures published by evaluation operations. They are anchors for checking a reconstruction; they are not results.")],
             FP: prose_precedence(W), ER: [("h", "Errata register"), ("p", "Void, restore and exclusion entries recorded by evaluation operations for the Q3 2025 close.")],
             RM: [("h", "Review board minutes"), ("p", "Decisions on reruns and maintenance exemptions. A rerun with no recorded decision is not approved.")],
             MD: prose_metrics(W), MA: prose_methodology(W)}
    for fb in docs:
        files[fb.name] = render_doc(fb, prose[fb.name], statements_for(fbs, fb.name), DOC_FMT[fb.name])
    truth["source_audit.json"] = source_audit_truth(W, fbs)
    truth["control_reconciliation.json"] = control_truth(W, truth)
    return files, truth, (W, fbs)


# ---------------------------------------------------------------------------------
# conflicts with partly authoritative exports, seen from the authoritative side
# ---------------------------------------------------------------------------------
DECOY_PAIRS = {
    "eval_store_mirror.db": ["eval_store.db", "code_samples.jsonl", "rerun_results.jsonl", "results_fleet_c.log", "job_configs.toml"],
    "scores_staging.parquet": ["scores_shard1.parquet", "scores_shard2.parquet", "results_fleet_a.log", "results_fleet_b.log",
                               "results_fleet_c.log", "intent_predictions.csv"],
    "judge_verdicts_rescored.jsonl": ["judge_verdicts.jsonl", "rerun_results.jsonl", "manual_overrides.xlsx", "harness_events.log", "run_registry.xml", "job_configs.toml", "evalops_notifications.mbox"],
    "checkpoint_lineage_snapshot.json": ["checkpoint_lineage.json", "run_registry.xml", "model_tags.yaml", "context_lengths.csv", "job_configs.toml"],
    "run_registry_export.xml": ["run_registry.xml", "harness_events.log", "job_configs.toml", "eval_store.db", "results_fleet_a.log", "manual_overrides.xlsx"],
    "locale_codes_legacy.tsv": ["prompt_locales.tsv", "slice_definitions.yaml", "gold_labels.tsv", "rerun_results.jsonl"],
    "gold_labels_corrected.csv": ["gold_labels.tsv", "grader_errata.xml", "item_registry.csv", "scoring_parameters.xlsx"],
    "scorecard_prelim.xlsx": ["results_fleet_a.log", "legacy_results.txt", "intent_predictions.csv", "scores_shard1.parquet",
                              "scoring_parameters.xlsx", "suite_manifest.xlsx"],
}
DECOY_TAG = {"eval_store_mirror.db": "MIRROR", "scores_staging.parquet": "STAGING", "judge_verdicts_rescored.jsonl": "RESCORED",
             "checkpoint_lineage_snapshot.json": "SNAPSHOT", "run_registry_export.xml": "EXPORT", "locale_codes_legacy.tsv": "LEGACYLOC",
             "gold_labels_corrected.csv": "CORRGOLD", "scorecard_prelim.xlsx": "PRELIM"}


def row_keys(row):
    f = row["f"]
    out = set()
    x = f.get("x")
    if x is not None and getattr(x, "item", None):
        out.add(("item", x.item))
        out.add(("job", x.job))
    for k in ("key", "iid"):
        v = f.get(k)
        if isinstance(v, str):
            out.add(("item", v) if "-" in v and v[:3].isupper() else ("other", v))
    if isinstance(f.get("c"), dict):
        out.add(("ckpt", f["c"]["id"]))
    if isinstance(f.get("j"), str):
        out.add(("job", f["j"]))
    if isinstance(f.get("jid"), str):
        out.add(("job", f["jid"]))
    if isinstance(f.get("job"), dict):
        out.add(("ckpt", f["job"]["ckpt"]))
    if isinstance(f.get("e"), dict):
        out.add(("ckpt", f["e"]["ckpt"]))
    return out


def add_decoy_conflicts(fbs):
    by = {fb.name: fb for fb in fbs}
    for d, targets in DECOY_PAIRS.items():
        dkeys = set()
        for row in by[d].rows:
            dkeys |= row_keys(row)
        dfb = by[d]
        for t in targets:
            tkeys = set()
            for row in by[t].rows:
                tkeys |= row_keys(row)
            dcode = "SUP_" + t.split(".")[0].upper()[:14]
            if dcode not in dfb.rules:
                dfb.R(dcode, "T16", f"A {d} row that restates a {t} fact is superseded by {t} for that fact.", POL, [POL, t], mode="row")
                for row in dfb.rows:
                    if row["k"] == "anchor":
                        continue
                    ks = row_keys(row)
                    if ks & tkeys and len(row["r"]) < 3 and hash_pick(d, t, repr(sorted(ks))[:60]) < 0.12:
                        row["r"].append(dcode)
            fb = by[t]
            code = "VS_" + DECOY_TAG[d]
            fb.R(code, "T16", f"Where {d} carries a conflicting copy of a {t} fact, the {t} value stands; {d} is authoritative only for the part the policy names.",
                 POL, [POL, d], mode="row")
            for row in fb.rows:
                if row["k"] == "anchor":
                    continue
                ks = row_keys(row)
                if ks & dkeys and len(row["r"]) < 3 and hash_pick(t, d, repr(sorted(ks))[:60]) < 0.18:
                    row["r"].append(code)
# ===== CORPUS GENERATOR END =====


# =================================================================================
# grading plumbing
# =================================================================================
_CACHE: dict = {}
import threading as _threading
# rewardkit evaluates criteria in parallel threads; every cached builder below holds this
# lock so one corpus is generated once instead of once per thread.
_LOCK = _threading.RLock()
GATED_T = ["arith", "mcq", "longctx", "multiling"]


def _norm(obj):
    return _json.loads(_json.dumps(obj, default=str))


def _truth(seed, scale):
    key = ("truth", seed, scale)
    with _LOCK:
        if key not in _CACHE:
            files, out, _meta = generate_corpus(seed, scale)
            _CACHE[key] = (files, _norm(out))
        return _CACHE[key]


def _visible_truth():
    return _truth(SAMPLE_SEED, VISIBLE_SCALE)[1]


def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop (agent editors leave 0600 files)."""
    if not argument.startswith(str(APP_ROOT)):
        return
    path = Path(argument)
    if not path.exists():
        return
    try:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if parent == APP_ROOT:
                break
    except OSError:
        pass


def _untrusted_command(command: list) -> list:
    if _os.name != "posix" and _root_only_tests_present():
        raise RuntimeError("verifier isolation requires POSIX uid/gid dropping")
    if _os.name == "posix" and _os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if _os.name == "posix" and _os.geteuid() == 0:
        for argument in command:
            _grant_read(argument)
        return [*_SETPRIV, *command]
    return command


def _write_dir(files, root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (root / name).write_bytes(data)
    for path in [root, *root.rglob("*")]:
        path.chmod(0o755 if path.is_dir() else 0o644)


def _parse_output(name, text):
    if name.endswith(".jsonl"):
        return [_json.loads(line) for line in text.splitlines() if line.strip()]
    if name.endswith(".csv"):
        return list(_csvmod.reader(_io.StringIO(text)))
    return _json.loads(text)


def _read_outputs(out: Path):
    """Load every output, isolating failures so one bad file cannot fail unrelated checks.

    A missing or unparseable artifact is recorded as None instead of raising, so only the
    checks that actually project that artifact fail. Presence and parseability are graded
    on their own by _check_outputs_present_and_parse.
    """
    got = {}
    for name in OUTPUTS:
        try:
            got[name] = _parse_output(name, (out / name).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            got[name] = None
    return got


def _snapshot(root: Path):
    return {str(p.relative_to(root)): _hl.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


NOBODY_UID = 65534


def _kill_unprivileged_leftovers() -> None:
    """Kill every process still running as the unprivileged grading uid, including ones that left the group via setsid."""
    proc_root = Path("/proc")
    if not proc_root.is_dir():
        return
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if entry.stat().st_uid == NOBODY_UID:
                _os.kill(int(entry.name), _signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass


def _run_program(data_dir: Path, out_dir: Path):
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    out_dir.parent.chmod(0o777)
    proc = _sp.Popen(_untrusted_command([_sys.executable, str(PROGRAM), str(data_dir), str(out_dir)]),
                     stdin=_sp.DEVNULL, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, start_new_session=True)
    try:
        return proc.wait(timeout=RUN_TIMEOUT)
    except _sp.TimeoutExpired:
        return -1
    finally:
        try:
            _os.killpg(proc.pid, _signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        if _os.name == "posix" and _os.geteuid() == 0:
            _kill_unprivileged_leftovers()
        proc.wait()


def _canary_dir() -> Path:
    """A different corpus at the default input location: a program that ignores its arguments reads it."""
    return APP_ROOT / "data"


def _eval_runs():
    with _LOCK:
        return _eval_runs_locked()


def _eval_runs_locked():
    if "eval" in _CACHE:
        return _CACHE["eval"]
    res = {"rc": [-1, -1, -1], "out": [], "outside": [], "inputs_before": {}, "inputs_after": {}}
    _CACHE["eval"] = res
    if not PROGRAM.is_file():
        return res
    files, _ = _truth(EVAL_SEED, HIDDEN_SCALE)
    canary = _canary_dir()
    if not canary.exists():
        cfiles, _ = _truth(CHALLENGE_SEED, HIDDEN_SCALE)
        _write_dir(cfiles, canary)
    base = Path(_tf.mkdtemp(prefix="certify-eval-"))
    base.chmod(0o777)
    data_a, data_b = base / "in-a" / "corpus", base / "in-b" / "renamed-location"
    _write_dir(files, data_a)
    _write_dir(files, data_b)
    before = _snapshot(base)
    res["inputs_before"] = _snapshot(data_a)
    res["rc"] = []
    for data, out in ((data_a, base / "o1" / "out"), (data_a, base / "o2" / "out"), (data_b, base / "o3" / "out")):
        try:
            rc = _run_program(data, out)
        except (OSError, _sp.SubprocessError, RuntimeError):
            rc = -1
        res["rc"].append(rc)
        res["out"].append(out)
        if rc != 0:
            break
    after = _snapshot(base)
    allowed = tuple(f"o{i}/out/" for i in (1, 2, 3))
    res["outside"] = [p for p in after if p not in before and not p.startswith(allowed)]
    res["inputs_after"] = _snapshot(data_a)
    return res


def _hidden():
    res = _eval_runs()
    if not res["rc"] or res["rc"][0] != 0:
        raise AssertionError("program failed on the hidden corpus")
    with _LOCK:
        if "hidden_out" not in _CACHE:
            _CACHE["hidden_out"] = _read_outputs(res["out"][0])
        return _CACHE["hidden_out"]


def _hidden_truth():
    return _truth(EVAL_SEED, HIDDEN_SCALE)[1]


def _visible():
    with _LOCK:
        if "visible" not in _CACHE:
            _CACHE["visible"] = _read_outputs(OUT_DIR)
        return _CACHE["visible"]


def _same(a, b):
    """Exact equality; integers must be integers, booleans booleans, floats any equal number."""
    if isinstance(b, bool) or isinstance(a, bool):
        return type(a) is bool and type(b) is bool and a == b
    if isinstance(b, int):
        return type(a) is int and a == b
    if isinstance(b, float):
        return type(a) in (int, float) and a == b
    if isinstance(b, dict):
        return isinstance(a, dict) and set(a) == set(b) and all(_same(a[k], b[k]) for k in b)
    if isinstance(b, list):
        return isinstance(a, list) and len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


KEYS = {"job_dispositions.jsonl": ("job_id",), "item_eligibility.jsonl": ("item_id",), "item_scores.jsonl": ("model", "item_id")}


def _rows(got, exp, name, fields, where=None):
    """Exact comparison of the named fields over the full row population of one JSONL artifact."""
    key = KEYS[name]
    e = {tuple(r[k] for k in key): r for r in exp[name] if where is None or where(r)}
    g = {}
    for r in got[name]:
        if not isinstance(r, dict) or not all(k in r for k in key):
            raise AssertionError("row shape")
        if where is None or where(r):
            g[tuple(r[k] for k in key)] = r
    assert set(g) == set(e), "row set differs"
    for k, row in e.items():
        for f in fields:
            assert f in g[k] and _same(g[k][f], row[f]), "value differs"


def _map(got, exp, path_fn):
    """Exact comparison of a selected projection of a JSON object artifact."""
    assert _same(path_fn(got), path_fn(exp)), "value differs"


def _metric(name, keys):
    def pick(doc):
        return {m: {b: {k: v[k] for k in keys if k in v} for b, v in suites.items() if any(k in v for k in keys)} for m, suites in doc[name].items()}
    return pick


def _lb_rows(doc):
    rows = doc["leaderboard.csv"]
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return rows
    hdr = rows[0]
    out = []
    for r in rows[1:]:
        d = dict(zip(hdr, r))
        out.append(d)
    return out


def _lb_values(doc):
    out = {}
    for r in _lb_rows(doc):
        out[r["model"]] = {k: float(v) for k, v in r.items() if k not in ("rank", "model")}
    return out


def _lb_order(doc):
    return [(int(r["rank"]), r["model"]) for r in _lb_rows(doc)]


def _holds(check) -> bool:
    try:
        check()
    except Exception:
        return False
    return True


def _vis(fn):
    return fn(_visible(), _visible_truth())


def _hid(fn):
    return fn(_hidden(), _hidden_truth())


# =================================================================================
# visible close
# =================================================================================
def _check_lineage_certified_checkpoints():
    _vis(lambda g, e: _map(g, e, lambda d: {a: v["checkpoint"] for a, v in d["lineage.json"].items()}))


def _check_lineage_effective_approvals():
    _vis(lambda g, e: _map(g, e, lambda d: {a: (v["effective_from"], v["approval_ref"]) for a, v in d["lineage.json"].items()}))


def _check_lineage_voided_promotion_counts():
    _vis(lambda g, e: _map(g, e, lambda d: {a: v["voided_promotions"] for a, v in d["lineage.json"].items()}))


def _check_job_dispositions_values():
    _vis(lambda g, e: _rows(g, e, "job_dispositions.jsonl", ["disposition"]))


def _check_job_submission_instants():
    _vis(lambda g, e: _rows(g, e, "job_dispositions.jsonl", ["submitted_at"]))


def _check_job_identity_fields():
    _vis(lambda g, e: _rows(g, e, "job_dispositions.jsonl", ["model", "benchmark", "shard", "checkpoint", "host"]))


def _check_item_eligibility_flags():
    _vis(lambda g, e: _rows(g, e, "item_eligibility.jsonl", ["eligible", "benchmark"]))


def _check_item_exclusion_reasons():
    _vis(lambda g, e: _rows(g, e, "item_eligibility.jsonl", ["reason"]))


def _scores(bench, fields):
    return lambda g, e: _rows(g, e, "item_scores.jsonl", fields, where=lambda r: r.get("benchmark") == bench)


def _check_scores_arith():
    _vis(_scores("arith", ["value", "correct", "confidence"]))


def _check_scores_code():
    _vis(_scores("code", ["value", "correct", "confidence"]))


def _check_scores_intent():
    _vis(_scores("intent", ["value", "correct", "confidence"]))


def _check_scores_safety():
    _vis(_scores("safety", ["value", "correct", "confidence"]))


def _check_scores_mcq_options():
    _vis(_scores("mcq", ["value", "correct"]))


def _check_scores_mcq_confidences():
    _vis(_scores("mcq", ["confidence"]))


def _check_scores_pref():
    _vis(_scores("pref", ["value", "correct", "confidence"]))


def _check_scores_longctx():
    _vis(_scores("longctx", ["value", "correct", "confidence"]))


def _check_scores_multiling():
    _vis(_scores("multiling", ["value", "correct", "confidence"]))


def _accuracies(doc):
    return {m: {b: v["accuracy"] for b, v in suites.items() if "accuracy" in v}
            for m, suites in doc["benchmark_metrics.json"].items()}


def _eligible_counts(doc):
    return {m: {b: v["n"] for b, v in suites.items()} for m, suites in doc["benchmark_metrics.json"].items()}


def _check_metrics_accuracy():
    _vis(lambda g, e: _map(g, e, _accuracies))


def _check_metrics_eligible_counts():
    _vis(lambda g, e: _map(g, e, _eligible_counts))


def _check_metrics_pass_at_k():
    _vis(lambda g, e: _map(g, e, _metric("benchmark_metrics.json", ["pass@1", "pass@5"])))


def _check_metrics_macro_f1():
    _vis(lambda g, e: _map(g, e, _metric("benchmark_metrics.json", ["macro_f1"])))


def _check_metrics_auroc():
    _vis(lambda g, e: _map(g, e, _metric("benchmark_metrics.json", ["auroc"])))


def _check_metrics_multiling_macro():
    _vis(lambda g, e: _map(g, e, _metric("benchmark_metrics.json", ["macro_accuracy", "languages"])))


def _check_calibration_ece():
    _vis(lambda g, e: _map(g, e, lambda d: {m: v["ece"] for m, v in d["calibration.json"].items()}))


def _check_calibration_bins():
    _vis(lambda g, e: _map(g, e, lambda d: {m: v["bins"] for m, v in d["calibration.json"].items()}))


def _check_pairwise_judgments():
    _vis(lambda g, e: _map(g, e, lambda d: d["pairwise.json"]))


def _check_significance_discordant_counts():
    _vis(lambda g, e: _map(g, e, lambda d: {m: {b: (v["b"], v["c"]) for b, v in s.items()} for m, s in d["significance.json"].items()}))


def _check_significance_decisions():
    _vis(lambda g, e: _map(g, e, lambda d: {m: {b: (v["p_value"], v["decision"]) for b, v in s.items()} for m, s in d["significance.json"].items()}))


def _check_leaderboard_aggregates():
    _vis(lambda g, e: _map(g, e, _lb_values))


def _check_leaderboard_ranking():
    _vis(lambda g, e: _map(g, e, _lb_order))


def _check_release_gate_decisions():
    _vis(lambda g, e: _map(g, e, lambda d: d["release_gates.json"]))


def _check_slice_metric_values():
    _vis(lambda g, e: _map(g, e, lambda d: d["slice_metrics.json"]))


def _check_source_audit_row_counts():
    _vis(lambda g, e: _map(g, e, lambda d: {s: v["result_rows"] for s, v in d["source_audit.json"].items()}))


def _check_source_audit_used_counts():
    _vis(lambda g, e: _map(g, e, lambda d: {s: (v["used"], v["discarded"]) for s, v in d["source_audit.json"].items()}))


def _check_control_reconciliation_totals():
    _vis(lambda g, e: _map(g, e, lambda d: d["control_reconciliation.json"]))


# =================================================================================
# hidden corpus (the reusable program)
# =================================================================================
def _check_hidden_job_dispositions():
    _hid(lambda g, e: _rows(g, e, "job_dispositions.jsonl", ["disposition", "submitted_at", "checkpoint", "shard"]))


def _check_hidden_item_eligibility():
    _hid(lambda g, e: _rows(g, e, "item_eligibility.jsonl", ["eligible", "reason"]))


def _check_hidden_item_scores():
    _hid(lambda g, e: _rows(g, e, "item_scores.jsonl", ["value", "confidence", "correct"]))


def _check_hidden_leaderboard_scores():
    _hid(lambda g, e: _map(g, e, _lb_values))


def _check_hidden_leaderboard_ranking():
    _hid(lambda g, e: _map(g, e, _lb_order))


def _check_hidden_release_gates():
    _hid(lambda g, e: _map(g, e, lambda d: d["release_gates.json"]))


def _check_hidden_lineage():
    _hid(lambda g, e: _map(g, e, lambda d: d["lineage.json"]))


# =================================================================================
# shape
# =================================================================================
def _check_outputs_present_and_parse():
    assert PROGRAM.is_file(), "program missing"
    got = _visible()
    assert not [name for name in OUTPUTS if got[name] is None], "missing or unparseable output"


def _check_outputs_utf8_lf():
    for name in OUTPUTS:
        raw = (OUT_DIR / name).read_bytes()
        raw.decode("utf-8")
        assert raw.endswith(b"\n") and b"\r" not in raw, name


def _check_leaderboard_csv_format():
    import re as _re
    raw = (OUT_DIR / "leaderboard.csv").read_bytes()
    rows = list(_csvmod.reader(_io.StringIO(raw.decode("utf-8"))))
    assert rows[0] == ["rank", "model", "aggregate", "arith", "code", "intent", "safety", "mcq", "pref", "longctx", "multiling"], "header"
    assert len(rows) > 1, "no rows"
    for r in rows[1:]:
        assert _re.fullmatch(r"\d+", r[0]), "rank"
        assert all(_re.fullmatch(r"-?\d+\.\d{6}", x) for x in r[2:]), "number format"


def _check_jsonl_order_and_uniqueness():
    for name, key in KEYS.items():
        raw = (OUT_DIR / name).read_bytes()
        rows = [_json.loads(x) for x in raw.decode("utf-8").split("\n") if x]
        assert rows, "no rows"
        keys = [tuple(r[k] for k in key) for r in rows]
        assert keys == sorted(keys) and len(keys) == len(set(keys)), "order"


# =================================================================================
# negative checks (each returns True when the cheat is present)
# =================================================================================
def _negative_hardcoded():
    # Fires when the program re-emits the visible close regardless of its input.
    res = _eval_runs()
    if not res["rc"] or res["rc"][0] != 0:
        return False
    got = _read_outputs(res["out"][0])
    vis = _visible_truth()
    return _same(got["job_dispositions.jsonl"], vis["job_dispositions.jsonl"]) or _same(got["item_eligibility.jsonl"], vis["item_eligibility.jsonl"])


def _negative_filename():
    # Fires when the same bytes under a different directory name give different outputs.
    res = _eval_runs()
    if len(res["rc"]) < 3 or res["rc"][0] != 0 or res["rc"][1] != 0:
        return False
    a, b = _snapshot(res["out"][0]), _snapshot(res["out"][1])
    if a != b:
        return False
    if res["rc"][2] != 0:
        return True
    return a != _snapshot(res["out"][2])


def _negative_reads_default():
    # Fires when the outputs follow the corpus at the default location instead of the argument.
    res = _eval_runs()
    if not res["rc"] or res["rc"][0] != 0:
        return False
    got = _read_outputs(res["out"][0])
    can = _truth(CHALLENGE_SEED, HIDDEN_SCALE)[1]
    return _same(got["job_dispositions.jsonl"], can["job_dispositions.jsonl"])


def _negative_nondeterministic():
    # Fires when two runs on identical input differ.
    res = _eval_runs()
    if len(res["rc"]) < 2 or res["rc"][0] != 0 or res["rc"][1] != 0:
        return False
    return _snapshot(res["out"][0]) != _snapshot(res["out"][1])


def _negative_modifies_input():
    # Fires when the input directory changed during the run.
    res = _eval_runs()
    if not res["inputs_before"]:
        return False
    return res["inputs_before"] != res["inputs_after"]


def _negative_writes_outside():
    # Fires when the program created files outside the output directory it was given.
    res = _eval_runs()
    return bool(res["outside"])


@criterion(description="lineage.json names the certified checkpoint of every model alias")
def lineage_certified_checkpoints(workspace: Path) -> bool:
    return _holds(_check_lineage_certified_checkpoints)


@criterion(description="lineage.json gives the effective approval instant and ticket of every alias")
def lineage_effective_approvals(workspace: Path) -> bool:
    return _holds(_check_lineage_effective_approvals)


@criterion(description="lineage.json counts the promotions that never took effect for every alias")
def lineage_voided_promotion_counts(workspace: Path) -> bool:
    return _holds(_check_lineage_voided_promotion_counts)


@criterion(description="job_dispositions.jsonl gives the documented disposition of every registered job")
def job_dispositions_values(workspace: Path) -> bool:
    return _holds(_check_job_dispositions_values)


@criterion(description="job_dispositions.jsonl gives the corrected UTC submission instant of every job")
def job_submission_instants(workspace: Path) -> bool:
    return _holds(_check_job_submission_instants)


@criterion(description="job_dispositions.jsonl gives canonical model, suite, shard, checkpoint and host for every job")
def job_identity_fields(workspace: Path) -> bool:
    return _holds(_check_job_identity_fields)


@criterion(description="item_eligibility.jsonl marks exactly the eligible registered items")
def item_eligibility_flags(workspace: Path) -> bool:
    return _holds(_check_item_eligibility_flags)


@criterion(description="item_eligibility.jsonl gives the first applicable exclusion reason of every item")
def item_exclusion_reasons(workspace: Path) -> bool:
    return _holds(_check_item_exclusion_reasons)


@criterion(description="item_scores.jsonl arithmetic rows carry the certified answer and correctness")
def scores_arith(workspace: Path) -> bool:
    return _holds(_check_scores_arith)


@criterion(description="item_scores.jsonl code rows carry the number of fully passing samples")
def scores_code(workspace: Path) -> bool:
    return _holds(_check_scores_code)


@criterion(description="item_scores.jsonl intent rows carry the resolved class and correctness")
def scores_intent(workspace: Path) -> bool:
    return _holds(_check_scores_intent)


@criterion(description="item_scores.jsonl safety rows carry the certified score")
def scores_safety(workspace: Path) -> bool:
    return _holds(_check_scores_safety)


@criterion(description="item_scores.jsonl multiple-choice rows carry the certified option and correctness")
def scores_mcq_options(workspace: Path) -> bool:
    return _holds(_check_scores_mcq_options)


@criterion(description="item_scores.jsonl multiple-choice rows carry the certified confidence")
def scores_mcq_confidences(workspace: Path) -> bool:
    return _holds(_check_scores_mcq_confidences)


@criterion(description="item_scores.jsonl preference rows carry the consistent judgment")
def scores_pref(workspace: Path) -> bool:
    return _holds(_check_scores_pref)


@criterion(description="item_scores.jsonl long-context rows carry the normalised answer and correctness")
def scores_longctx(workspace: Path) -> bool:
    return _holds(_check_scores_longctx)


@criterion(description="item_scores.jsonl multilingual rows carry the normalised answer and correctness")
def scores_multiling(workspace: Path) -> bool:
    return _holds(_check_scores_multiling)


@criterion(description="benchmark_metrics.json accuracy values are exact for every model")
def metrics_accuracy(workspace: Path) -> bool:
    return _holds(_check_metrics_accuracy)


@criterion(description="benchmark_metrics.json eligible item counts n are exact for every model and suite")
def metrics_eligible_counts(workspace: Path) -> bool:
    return _holds(_check_metrics_eligible_counts)


@criterion(description="benchmark_metrics.json pass at 1 and pass at 5 values are exact")
def metrics_pass_at_k(workspace: Path) -> bool:
    return _holds(_check_metrics_pass_at_k)


@criterion(description="benchmark_metrics.json intent macro F1 values are exact")
def metrics_macro_f1(workspace: Path) -> bool:
    return _holds(_check_metrics_macro_f1)


@criterion(description="benchmark_metrics.json safety AUROC values are exact")
def metrics_auroc(workspace: Path) -> bool:
    return _holds(_check_metrics_auroc)


@criterion(description="benchmark_metrics.json multilingual macro accuracy and language counts are exact")
def metrics_multiling_macro(workspace: Path) -> bool:
    return _holds(_check_metrics_multiling_macro)


@criterion(description="calibration.json expected calibration error is exact for every candidate")
def calibration_ece(workspace: Path) -> bool:
    return _holds(_check_calibration_ece)


@criterion(description="calibration.json bin tables are exact for every candidate")
def calibration_bins(workspace: Path) -> bool:
    return _holds(_check_calibration_bins)


@criterion(description="pairwise.json win, tie and loss counts and win rates are exact")
def pairwise_judgments(workspace: Path) -> bool:
    return _holds(_check_pairwise_judgments)


@criterion(description="significance.json discordant counts b and c are exact")
def significance_discordant_counts(workspace: Path) -> bool:
    return _holds(_check_significance_discordant_counts)


@criterion(description="significance.json p values and decisions are exact")
def significance_decisions(workspace: Path) -> bool:
    return _holds(_check_significance_decisions)


@criterion(description="leaderboard.csv aggregate and normalised suite scores are exact")
def leaderboard_aggregates(workspace: Path) -> bool:
    return _holds(_check_leaderboard_aggregates)


@criterion(description="leaderboard.csv ranks follow the documented aggregate order")
def leaderboard_ranking(workspace: Path) -> bool:
    return _holds(_check_leaderboard_ranking)


@criterion(description="release_gates.json gate booleans are exact for every candidate")
def release_gate_decisions(workspace: Path) -> bool:
    return _holds(_check_release_gate_decisions)


@criterion(description="slice_metrics.json values and nulls are exact")
def slice_metric_values(workspace: Path) -> bool:
    return _holds(_check_slice_metric_values)


@criterion(description="source_audit.json result row counts are exact for every result source")
def source_audit_row_counts(workspace: Path) -> bool:
    return _holds(_check_source_audit_row_counts)


@criterion(description="source_audit.json used and discarded counts are exact")
def source_audit_used_counts(workspace: Path) -> bool:
    return _holds(_check_source_audit_used_counts)


@criterion(description="control_reconciliation.json totals are exact")
def control_reconciliation_totals(workspace: Path) -> bool:
    return _holds(_check_control_reconciliation_totals)


@criterion(description="certify.py reproduces job dispositions on the hidden corpus")
def hidden_job_dispositions(workspace: Path) -> bool:
    return _holds(_check_hidden_job_dispositions)


@criterion(description="certify.py reproduces item eligibility on the hidden corpus")
def hidden_item_eligibility(workspace: Path) -> bool:
    return _holds(_check_hidden_item_eligibility)


@criterion(description="certify.py reproduces item scores on the hidden corpus")
def hidden_item_scores(workspace: Path) -> bool:
    return _holds(_check_hidden_item_scores)


@criterion(description="certify.py reproduces the leaderboard scores on the hidden corpus")
def hidden_leaderboard_scores(workspace: Path) -> bool:
    return _holds(_check_hidden_leaderboard_scores)


@criterion(description="certify.py reproduces the leaderboard ranking on the hidden corpus")
def hidden_leaderboard_ranking(workspace: Path) -> bool:
    return _holds(_check_hidden_leaderboard_ranking)


@criterion(description="certify.py reproduces release gates on the hidden corpus")
def hidden_release_gates(workspace: Path) -> bool:
    return _holds(_check_hidden_release_gates)


@criterion(description="certify.py reproduces lineage on the hidden corpus")
def hidden_lineage(workspace: Path) -> bool:
    return _holds(_check_hidden_lineage)


@criterion(description="the program and all thirteen outputs exist and parse")
def outputs_present_and_parse(workspace: Path) -> bool:
    return _holds(_check_outputs_present_and_parse)


@criterion(description="every output is UTF-8 with LF line endings and a trailing newline")
def outputs_utf8_lf(workspace: Path) -> bool:
    return _holds(_check_outputs_utf8_lf)


@criterion(description="leaderboard.csv has the exact header and six-decimal numbers")
def leaderboard_csv_format(workspace: Path) -> bool:
    return _holds(_check_leaderboard_csv_format)


@criterion(description="JSONL outputs are sorted by their keys with no duplicate rows")
def jsonl_order_and_uniqueness(workspace: Path) -> bool:
    return _holds(_check_jsonl_order_and_uniqueness)


@criterion(description="certify.py re-emits the visible close on a different corpus")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened.
    try:
        return bool(_negative_hardcoded())
    except Exception:
        return False


@criterion(description="certify.py output depends on the input directory name")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened.
    try:
        return bool(_negative_filename())
    except Exception:
        return False


@criterion(description="certify.py reads the default data location instead of its argument")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened.
    try:
        return bool(_negative_reads_default())
    except Exception:
        return False


@criterion(description="certify.py output differs between identical runs")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened.
    try:
        return bool(_negative_nondeterministic())
    except Exception:
        return False


@criterion(description="certify.py changes files in its input directory")
def negative_modifies_input_corpus(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened.
    try:
        return bool(_negative_modifies_input())
    except Exception:
        return False


@criterion(description="certify.py writes files outside its output directory")
def negative_writes_outside_output_dir(workspace: Path) -> bool:
    # Inverted polarity: True means the cheat happened.
    try:
        return bool(_negative_writes_outside())
    except Exception:
        return False


criteria.lineage_certified_checkpoints(weight=5)
criteria.lineage_effective_approvals(weight=3)
criteria.lineage_voided_promotion_counts(weight=1)
criteria.job_dispositions_values(weight=5)
criteria.job_submission_instants(weight=5)
criteria.job_identity_fields(weight=3)
criteria.item_eligibility_flags(weight=5)
criteria.item_exclusion_reasons(weight=5)
criteria.scores_arith(weight=5)
criteria.scores_code(weight=5)
criteria.scores_intent(weight=5)
criteria.scores_safety(weight=5)
criteria.scores_mcq_options(weight=5)
criteria.scores_mcq_confidences(weight=5)
criteria.scores_pref(weight=5)
criteria.scores_longctx(weight=5)
criteria.scores_multiling(weight=5)
criteria.metrics_accuracy(weight=5)
criteria.metrics_eligible_counts(weight=1)
criteria.metrics_pass_at_k(weight=5)
criteria.metrics_macro_f1(weight=5)
criteria.metrics_auroc(weight=5)
criteria.metrics_multiling_macro(weight=5)
criteria.calibration_ece(weight=5)
criteria.calibration_bins(weight=3)
criteria.pairwise_judgments(weight=5)
criteria.significance_discordant_counts(weight=5)
criteria.significance_decisions(weight=3)
criteria.leaderboard_aggregates(weight=5)
criteria.leaderboard_ranking(weight=3)
criteria.release_gate_decisions(weight=5)
criteria.slice_metric_values(weight=5)
criteria.source_audit_row_counts(weight=3)
criteria.source_audit_used_counts(weight=5)
criteria.control_reconciliation_totals(weight=3)
criteria.hidden_job_dispositions(weight=5)
criteria.hidden_item_eligibility(weight=5)
criteria.hidden_item_scores(weight=5)
criteria.hidden_leaderboard_scores(weight=3)
criteria.hidden_leaderboard_ranking(weight=3)
criteria.hidden_release_gates(weight=3)
criteria.hidden_lineage(weight=3)
criteria.outputs_present_and_parse(weight=1)
criteria.outputs_utf8_lf(weight=1)
criteria.leaderboard_csv_format(weight=1)
criteria.jsonl_order_and_uniqueness(weight=1)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_modifies_input_corpus(weight=-3)
criteria.negative_writes_outside_output_dir(weight=-1)
