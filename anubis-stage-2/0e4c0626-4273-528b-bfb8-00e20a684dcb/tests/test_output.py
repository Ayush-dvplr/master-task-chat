from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from rewardkit import criteria, criterion

SAMPLE_SEED = int("8670992140332646210")
CHALLENGE_SEED = int("7647325660253833414")
EVAL_SEED = int("2339907786676870586")
APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
OUT_DIR = APP_ROOT / "out"
PROGRAM = OUT_DIR / "settle.py"
CORPUS_SIZE = 10200
RUN_TIMEOUT = 900
OUTPUTS = ["attempts.jsonl", "lookups.jsonl", "targets.jsonl", "actions.jsonl", "artifacts.jsonl",
           "invoice_reconciliation.jsonl", "team_chargeback.json", "cost_center_ledger.json", "rate_resolution.json",
           "cache_effectiveness.json", "control_reconciliation.json", "source_audit.json", "close_summary.json"]
ROW_KEY = {"attempts.jsonl": "attempt_id", "lookups.jsonl": "lookup_id", "targets.jsonl": "target",
           "actions.jsonl": "action_key", "artifacts.jsonl": "artifact_id", "invoice_reconciliation.jsonl": "line_id"}
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]


# ===== CORPUS GENERATOR BEGIN =====
# World model and truth engine for the October 2025 build-minute close.
# Pure stdlib; byte-deterministic for a given seed.
import gzip as _gzip
import hashlib as _hashlib
import io as _io
import json as _json
import os as _os
import random as _random
import re as _re
import sqlite3 as _sqlite3
import tempfile as _tempfile
import zipfile as _zipfile
import zlib as _zlib
from datetime import datetime as _dt, timezone as _tz
from fractions import Fraction as _F

P0 = 1759276800          # 2025-10-01T00:00:00Z, period start (inclusive)
P1 = 1761955200          # 2025-11-01T00:00:00Z, period end (exclusive)
KCUT = 1762214400        # 2025-11-04T00:00:00Z, knowledge cutoff (inclusive)
EU_END = 1761440400      # 2025-10-26T01:00:00Z
AU_START = 1759593600    # 2025-10-04T16:00:00Z
USE_END = 1762063200     # 2025-11-02T06:00:00Z
USC_END = 1762066800     # 2025-11-02T07:00:00Z

FLEETS = {"north": ["eu-west-1", "ca-north-8"], "south": ["sa-east-7", "ap-southeast-6"],
          "east": ["ap-south-5", "eu-central-2"], "west": ["us-east-3", "us-central-4"]}
REGION_ZONE = {"eu-west-1": "EU+1", "eu-central-2": "EU+1", "ca-north-8": "US-5", "us-east-3": "US-5",
               "us-central-4": "US-6", "sa-east-7": "BR-3", "ap-southeast-6": "AU+10", "ap-south-5": "IN+5:30"}
REGIONS = sorted(REGION_ZONE)
ZONES = sorted(set(REGION_ZONE.values()))
LANGS = ["cpp", "go", "java", "kotlin", "python", "rust", "swift", "typescript"]
LANG_TC = {"cpp": ["clang", "protoc"], "go": ["go"], "java": ["jdk"], "kotlin": ["kotlinc"],
           "python": ["cpython", "uv"], "rust": ["rustc", "wasm-pack"], "swift": ["swiftc"], "typescript": ["node", "bun"]}
TC_SERIES = {"clang": [(17, 0), (18, 1)], "protoc": [(27, 0), (28, 2)], "go": [(1, 22), (1, 23)], "jdk": [(17, 0), (21, 0)],
             "kotlinc": [(1, 9), (2, 0)], "cpython": [(3, 11), (3, 12)], "uv": [(0, 4), (0, 5)], "rustc": [(1, 81), (1, 82)],
             "wasm-pack": [(0, 12), (0, 13)], "swiftc": [(5, 9), (5, 10)], "node": [(20, 17), (22, 9)], "bun": [(1, 1)]}
ORGS = ["data", "growth", "identity", "infra", "mobile", "payments", "platform", "search"]
LOCALES = ["de-DE", "en-IN", "en-US", "fr-FR", "ja-JP", "pt-BR"]
AREAS = ["apps", "data", "infra", "lib", "ml", "mobile", "svc", "tools", "web"]
KINDS = ["build", "deploy", "lint", "test"]
FAMS = ["arm", "cpu", "edge", "gp", "gpu", "hpc", "io", "mem"]
SIZES = ["2xlarge", "4xlarge", "large", "medium", "small", "xlarge"]
CLASSES = sorted(f"{f}{g}.{s}" for f in FAMS for g in (6, 7) for s in SIZES)
ALLOWED_ENV = ["CC", "CXX", "GOFLAGS", "HOME", "JAVA_HOME", "LANG", "NODE_OPTIONS", "PATH", "PYTHONPATH",
               "RUSTFLAGS", "SDKROOT", "TZ"]
DENIED_ENV = ["BUILD_TIMESTAMP", "CI_JOB_TOKEN", "HOSTNAME", "RANDOM_SEED", "RUNNER_NAME", "USER"]
STATUSES = ["cancelled", "failed", "preempted", "succeeded"]
CLASS_MULT = {"standard": 1000, "priority": 1250, "batch": 800}
GRACE_S = {"north": 120, "south": 90, "east": 180, "west": 60}
RESERVED_PERMILLE = 600
STORAGE_MICRO_PER_GIB_HOUR = 41
CACHE_CREDIT_MICRO = 1800
DEFAULT_BUDGET = 3
WEEK_EDGES = [P0 + 7 * 86400 * i for i in range(5)] + [P1]
ALPH = "abcdefghjkmnpqrstuvwxyz23456789"


def zoff(zone, t):
    if zone == "EU+1":
        return 120 if t < EU_END else 60
    if zone == "US-5":
        return -240 if t < USE_END else -300
    if zone == "US-6":
        return -300 if t < USC_END else -360
    if zone == "IN+5:30":
        return 330
    if zone == "AU+10":
        return 660 if t >= AU_START else 600
    if zone == "BR-3":
        return -180
    return 0


def iso(t):
    return _dt.fromtimestamp(t, _tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def vkey(v):
    return tuple(int(x) for x in v.split("."))


def rhe(fr):
    """Round a Fraction half to even, return int."""
    fl = fr.numerator // fr.denominator
    rem = fr - fl
    if rem > _F(1, 2) or (rem == _F(1, 2) and fl % 2 == 1):
        return fl + 1
    return fl


def rhu(fr):
    fl = fr.numerator // fr.denominator
    return fl + 1 if fr - fl >= _F(1, 2) else fl


class World:
    pass


def _code(rng, prefix, n, used):
    while True:
        v = prefix + "".join(rng.choice(ALPH) for _ in range(n))
        if v not in used:
            used.add(v)
            return v


def satisfies(cons, ver, naive_caret=False):
    v = vkey(ver)
    if cons.startswith("="):
        return v == vkey(cons[1:])
    if cons.startswith(">="):
        lo, hi = cons[2:].split(" <")
        return vkey(lo) <= v < vkey(hi)
    base = vkey(cons[1:])
    if v < base:
        return False
    if cons.startswith("~"):
        return v[:2] == base[:2]
    # caret, Cargo reading: the left-most non-zero component is locked
    if naive_caret:
        return v[0] == base[0]
    if base[0] > 0:
        return v[0] == base[0]
    if base[1] > 0:
        return v[:2] == base[:2]
    return v == base


def resolve(w, toolchain, cons, t, wrong=frozenset()):
    best = None
    for rel in w.releases[toolchain]:
        if rel["released"] > t:
            continue
        if rel["yanked"] is not None and rel["yanked"] <= t and "ignore_yank" not in wrong:
            continue
        if not satisfies(cons, rel["version"], "naive_caret" in wrong):
            continue
        if best is None:
            best = rel["version"]
        elif "verstr" in wrong:
            best = max(best, rel["version"])
        elif vkey(rel["version"]) > vkey(best):
            best = rel["version"]
    return best


def build_world(seed, n=10200):
    rng = _random.Random(seed)
    w = World()
    w.seed, w.n = seed, n
    used = set()
    # ---- runners, revisions, skus -------------------------------------------------
    nr = n // 5
    w.runners, w.revs, w.skus = [], [], {}
    fleets = sorted(FLEETS)
    for i in range(nr):
        fleet = fleets[i % 4]
        base = FLEETS[fleet][(i // 4) % 2]
        rid = f"rn-{fleet}-{10000 + i * 7 + rng.randrange(7):05d}"
        r = {"id": rid, "fleet": fleet, "base_region": base, "zone": REGION_ZONE[base], "revs": []}
        times = sorted(rng.sample(range(P0 + 3600, P1 - 3600, 600), 4))
        effs = [P0 - rng.randrange(5, 90) * 86400 - rng.randrange(86400)] + times
        major_minor = rng.choice([(4, 0), (4, 1), (4, 2), (4, 3), (4, 4), (5, 0)])
        for k, eff in enumerate(effs):
            region = base
            if k > 0 and rng.random() < 0.06:
                region = FLEETS[fleet][1 - FLEETS[fleet].index(base)]
            if k > 0 and rng.random() < 0.35:
                major_minor = (major_minor[0], major_minor[1] + 1) if major_minor[1] < 4 else (5, 0)
            sku = _code(rng, "sku-", 6, used)
            cls = rng.choice(CLASSES)
            spot = rng.random() < 0.15
            w.skus[sku] = {"sku": sku, "cls": cls, "arch": "arm64" if cls.startswith(("arm", "edge")) else "x86_64",
                           "gran": rng.choice([1, 1, 10, 60]), "spot": spot}
            rev = {"runner": rid, "rev": k + 1, "eff": eff, "sku": sku,
                   "ver": f"{major_minor[0]}.{major_minor[1]}.{rng.randrange(12)}", "region": region}
            r["revs"].append(rev)
            w.revs.append(rev)
        w.runners.append(r)
    w.runner_by = {r["id"]: r for r in w.runners}
    # ---- rates --------------------------------------------------------------------
    w.rates = []
    per = max(2, -(-n // (len(CLASSES) * len(REGIONS))))
    for cls in CLASSES:
        for region in REGIONS:
            level = rng.randrange(900, 9000)
            effs = [P0 - rng.randrange(20, 200) * 86400] + sorted(rng.sample(range(P0, P1, 3600), per - 1))
            for eff in effs:
                level = max(200, level + rng.randrange(-400, 401))
                rec = eff - rng.randrange(3600, 20 * 86400)
                row = {"cls": cls, "region": region, "eff": eff, "rec": rec, "rate": level, "late": False, "corr": False}
                w.rates.append(row)
                if rng.random() < 0.05:   # re-recorded correction for the same instant
                    w.rates.append(dict(row, rec=rec + rng.randrange(3600, 86400), rate=level + rng.randrange(5, 60), corr=True))
                if eff > P0 and rng.random() < 0.06:   # recorded after the knowledge cutoff
                    w.rates.append(dict(row, rec=KCUT + rng.randrange(3600, 9 * 86400),
                                        rate=level + rng.randrange(30, 300), late=True))
    for i, row in enumerate(sorted(w.rates, key=lambda r: (r["cls"], r["region"], r["eff"], r["rec"]))):
        row["id"] = f"rt-{i + 1:06d}"
    w.rates.sort(key=lambda r: r["id"])
    w.spot_credit = {c: rng.choice([150, 200, 250, 300, 350]) for c in CLASSES}
    # ---- toolchain releases ---------------------------------------------------------
    w.releases, w.digests = {}, {}
    for tc in sorted(TC_SERIES):
        rels = []
        for (ma, mi) in TC_SERIES[tc]:
            minors = [mi, mi + 1] if ma == 0 else [mi]
            for m in minors:
                t = P0 - rng.randrange(200, 400) * 86400
                for p in range(rng.randrange(6, 12)):
                    t += rng.randrange(10, 50) * 86400
                    rels.append({"version": f"{ma}.{m}.{p}", "released": t - rng.randrange(86400), "yanked": None})
        last = max(rels, key=lambda r: vkey(r["version"]))["version"]
        a, b, c = vkey(last)
        for extra in range(rng.randrange(1, 3)):
            rels.append({"version": f"{a}.{b}.{c + 1 + extra}", "released": rng.randrange(P0 + 86400, P1 - 86400), "yanked": None})
        for rel in rels:
            if P0 - 30 * 86400 < rel["released"] < P1 and rng.random() < 0.2:
                rel["yanked"] = rel["released"] + rng.randrange(86400, 20 * 86400)
            if P0 - 20 * 86400 < rel["released"] < P0 and rng.random() < 0.4:
                rel["released"] = rng.randrange(P0 + 86400, P1 - 86400)
        rels.sort(key=lambda r: (vkey(r["version"])))
        w.releases[tc] = rels
        for rel in rels:
            w.digests[(tc, rel["version"])] = _hashlib.sha256(f"{seed}:{tc}:{rel['version']}".encode()).hexdigest()[:20]
    # ---- orgs, teams, handles, cost centres -----------------------------------------
    words = ["amber", "basalt", "cedar", "delta", "ember", "fjord", "garnet", "harbor", "indigo", "juniper", "kestrel",
             "lumen", "maple", "nimbus", "onyx", "pioneer", "quartz", "ridge", "summit", "tundra", "umber", "vale"]
    w.teams = sorted({f"{o}-{wd}" for o in ORGS for wd in rng.sample(words, 22)})
    w.team_org = {t: t.split("-")[0] for t in w.teams}
    ncc = max(8, n // 5)
    w.ccs = sorted({f"cc-{rng.randrange(10000, 99999)}" for _ in range(ncc * 2)})[:ncc]
    w.cc_merges = {}
    for cc in rng.sample(w.ccs, max(2, ncc // 40)):
        tgt = rng.choice(w.ccs)
        if tgt != cc and tgt not in w.cc_merges and cc not in w.cc_merges.values():
            w.cc_merges[cc] = (tgt, rng.randrange(P0 + 86400, P1 - 86400))
    # ---- targets -------------------------------------------------------------------
    w.targets = []
    labels = set()
    for i in range(n):
        area = rng.choice(AREAS)
        pkg = f"{rng.choice(words)}{i:05d}"
        name = rng.choice(["lib", "server", "client", "tests", "image", "cli", "proto", "bench"])
        lab = f"//{area}/{pkg}:{name}"
        if rng.random() < 0.03 and w.targets:      # case-distinct twin (both real)
            prev = w.targets[-1]["label"]
            cand = prev.replace(prev.split("/")[3][:1], prev.split("/")[3][:1].upper(), 1)
            if cand not in labels and cand != prev:
                lab = cand
        labels.add(lab)
        lang = rng.choice(LANGS)
        tc = rng.choice(LANG_TC[lang])
        kind = "test" if name in ("tests", "bench") else rng.choice(KINDS)
        rels = [r for r in w.releases[tc] if r["released"] < P0 - 5 * 86400]
        if vkey(rels[0]["version"])[0] == 0 and rng.random() < 0.5:
            lo_minor = min(vkey(r["version"])[1] for r in rels)
            anchor = rng.choice([r for r in rels if vkey(r["version"])[1] == lo_minor])["version"]
        else:
            anchor = rng.choice(rels[-6:] if len(rels) >= 6 else rels)["version"]
        roll = rng.random()
        if roll < 0.50:
            cons = "^" + anchor
        elif roll < 0.75:
            cons = "~" + anchor
        elif roll < 0.85:
            cons = "=" + anchor
        else:
            a = vkey(anchor)
            cons = f">={anchor} <{a[0]}.{a[1] + 1}.0"
        scope = rng.choices(["billable", "exempt", "shared"], [0.86, 0.08, 0.06])[0]
        w.targets.append({"label": lab, "area": area, "pkg": pkg, "kind": kind, "lang": lang, "tc": tc,
                          "cons": cons, "scope": scope, "idx": i})
    w.target_by = {t["label"]: t for t in w.targets}
    # ---- edges (DAG on index order) --------------------------------------------------
    w.edges = []
    seen = set()
    while len(w.edges) < n:
        c = rng.randrange(1, n)
        p = rng.randrange(max(0, c - 400), c)
        if (c, p) in seen:
            continue
        seen.add((c, p))
        w.edges.append({"child": w.targets[c]["label"], "parent": w.targets[p]["label"],
                        "kind": rng.choices(["src", "toolchain", "data"], [0.6, 0.2, 0.2])[0]})
    # ---- actions -------------------------------------------------------------------
    w.actions = {}
    prefixes = set()
    for t in w.targets:
        while True:
            key = _hashlib.sha256(f"{seed}:{t['label']}:{rng.random()}".encode()).hexdigest()[:16]
            if key[:6] not in prefixes:
                prefixes.add(key[:6])
                break
        env = sorted(rng.sample(ALLOWED_ENV, rng.randrange(1, 3)))
        if rng.random() < 0.12:
            env = sorted(set(env) | {rng.choice(DENIED_ENV)})
        path = f"{t['label'][2:].split(':')[0]}/{rng.choice(['BUILD', 'src/main', 'go.mod', 'Cargo.toml', 'package.json', 'pom.xml'])}"
        w.actions[key] = {"key": key, "target": t["label"], "env": env, "path": path,
                          "declared": rng.random() >= 0.1, "input_bytes": rng.randrange(1, 4000) * 1024,
                          "shard": rng.randrange(1, 4)}
        t["action"] = key
    # ---- handles, owner patterns -----------------------------------------------------
    w.handles = {}
    w.patterns = []
    order = list(range(n))
    rng.shuffle(order)
    for j, ti in enumerate(order):
        t = w.targets[ti]
        h = f"@kestrel/{rng.choice(words)}-{j:05d}"
        team = rng.choice(w.teams)
        moved = None
        if rng.random() < 0.05:
            moved = (rng.choice(w.teams), rng.randrange(P0 + 86400, P1 - 86400))
        cc = rng.choice(w.ccs)
        cc_move = (rng.choice(w.ccs), rng.randrange(P0 + 86400, P1 - 86400)) if rng.random() < 0.05 else None
        w.handles[h] = {"handle": h, "team": team, "moved": moved, "cc": cc, "cc_move": cc_move}
        roll = rng.random()
        if roll < 0.40:
            pat = f"//{t['area']}/{t['pkg']}:*"                 # matches this package's targets
        elif roll < 0.65:
            pat = t["label"]                                     # exact label
        elif roll < 0.85:
            pat = f"//{t['area']}/{t['pkg'][:-2]}*:*"            # sibling packages sharing a prefix
        elif roll < 0.93:
            pat = f"//{t['area']}/{t['pkg'][:-2]}*"              # documented glob: no match (* stops at ':'); fnmatch would match
        else:
            pat = f"//{t['area']}/**"                            # broad area line that later lines override
        neg = rng.random() < 0.06
        w.patterns.append({"seq": j + 1, "pattern": ("!" + pat) if neg else pat, "handle": h})
    w.renames = {}
    for h in rng.sample(sorted(w.handles), max(4, n // 40)):
        new = h.replace("@kestrel/", "@kestrel-eng/")
        w.renames[h] = (new, rng.randrange(P0 - 20 * 86400, KCUT + 5 * 86400))
        w.handles[new] = dict(w.handles[h], handle=new)
    # ---- jobs and attempts ---------------------------------------------------------
    w.jobs, w.attempts = {}, []
    fleet_runners = {f: [r for r in w.runners if r["fleet"] == f] for f in fleets}
    jid = 3000000
    submitters = sorted(w.handles)[::7]
    for fleet in fleets:
        made = 0
        while made < n:
            jid += rng.randrange(1, 9)
            job = f"jb-{jid:08d}"
            t = rng.choice(w.targets)
            k = min(n - made, rng.choices([1, 2, 3, 4, 5], [0.42, 0.26, 0.16, 0.10, 0.06])[0])
            start = rng.randrange(P0 - 2 * 86400, P1 + 86400)
            w.jobs[job] = {"job": job, "target": t["label"], "fleet": fleet,
                           "submitter": rng.choice(submitters)}
            for a in range(k):
                runner = rng.choice(fleet_runners[fleet])
                if t["kind"] == "test":
                    st = rng.choices(STATUSES, [0.08, 0.5, 0.12, 0.3])[0]
                else:
                    st = rng.choices(STATUSES, [0.08, 0.18, 0.14, 0.6])[0]
                if a == k - 1 and st in ("preempted", "cancelled") and rng.random() < 0.6:
                    st = "succeeded"
                dur = int(rng.lognormvariate(12.6, 1.1))
                dur = max(1500, min(dur, 3 * 3600 * 1000))
                if rng.random() < 0.015:
                    dur = rng.randrange(6 * 3600, 20 * 3600) * 1000 + rng.randrange(1000)
                if st == "preempted" and rng.random() < 0.5:
                    dur = rng.randrange(5, 240) * 1000 + rng.randrange(1000)
                if REGION_ZONE[runner["base_region"]] == "EU+1" and EU_END <= start < EU_END + 3600:
                    start += 3600
                w.attempts.append({"id": None, "job": job, "no": a + 1, "runner": runner["id"], "start": start,
                                   "dur": dur, "status": st, "fleet": fleet,
                                   "origin": rng.choice(["user", "user", "platform"]) if st == "cancelled" and fleet == "east" else ""})
                start += dur // 1000 + rng.randrange(20, 1800)
                made += 1
    ids = rng.sample(range(1000000, 9999999), len(w.attempts))
    for a, i in zip(w.attempts, ids):
        a["id"] = f"at-{i:07d}"
    w.att_by = {a["id"]: a for a in w.attempts}
    west_ids = sorted(a["id"] for a in w.attempts if a["fleet"] == "west")
    w.revoked = set(rng.sample(west_ids, max(1, len(west_ids) // 30)))
    w.job_atts = {}
    for a in w.attempts:
        w.job_atts.setdefault(a["job"], []).append(a)
    for a in w.attempts:   # monotonic counters per runner boot
        a["mono0"] = rng.randrange(10 ** 9, 9 * 10 ** 12) * 1000
    # target stated on the attempt row is stale for some jobs; job register wins
    for a in w.attempts:
        a["row_target"] = w.jobs[a["job"]]["target"]
    stale_jobs = rng.sample(sorted(w.jobs), max(1, len(w.jobs) // 25))
    for j in stale_jobs:
        other = rng.choice(w.targets)["label"]
        for a in w.job_atts[j]:
            a["row_target"] = other
    w.register_jobs = sorted(w.jobs)
    # ---- clock skew windows (5 per runner, in true time) -------------------------------
    w.skews = []
    by_runner = {}
    for a in w.attempts:
        by_runner.setdefault(a["runner"], []).append(a)
    for rid in sorted(by_runner):
        atts = sorted(by_runner[rid], key=lambda a: a["start"])
        wins = []
        for a in rng.sample(atts, min(5, len(atts))):
            for _ in range(20):
                lo = a["start"] - rng.randrange(30, 3600)
                hi = a["start"] + rng.randrange(30, 3600)
                s = rng.choice([-1, 1]) * rng.randrange(2, 900)
                ok = all(hi <= x[0] or lo >= x[1] for x in wins)
                ok = ok and all(hi + s <= x[0] + x[2] or lo + s >= x[1] + x[2] for x in wins)
                if ok:
                    trial = wins + [(lo, hi, s)]
                    for b in atts:
                        rec = b["start"]
                        for x in trial:
                            if x[0] <= b["start"] < x[1]:
                                rec = b["start"] + x[2]
                        back = rec
                        for x in trial:
                            if x[0] + x[2] <= rec < x[1] + x[2]:
                                back = rec - x[2]
                                break
                        if back != b["start"]:
                            ok = False
                            break
                if ok:
                    wins.append((lo, hi, s))
                    break
        for lo, hi, s in sorted(wins):
            w.skews.append({"runner": rid, "lo": lo, "hi": hi, "skew": s})
    for a in w.attempts:
        a["rec_start"] = a["start"]
    for s in w.skews:
        for a in by_runner[s["runner"]]:
            if s["lo"] <= a["start"] < s["hi"]:
                a["rec_start"] = a["start"] + s["skew"]
    # ---- drain windows (ics), reservations (toml) ----------------------------------------
    w.drains, w.reserv = [], []
    pool = [a for a in w.attempts if P0 <= a["start"] < P1]
    for a in rng.sample(pool, min(n, len(pool))):
        if rng.random() < 0.12:     # boundary: window ends exactly at the start (half-open)
            lo, hi = a["start"] - rng.randrange(300, 7200), a["start"]
        else:
            lo, hi = a["start"] - rng.randrange(0, 3600), a["start"] + rng.randrange(1, 3600)
        w.drains.append({"runner": a["runner"], "lo": lo, "hi": hi, "uid": None})
    for i, d in enumerate(w.drains):
        d["uid"] = f"drain-{i + 1:06d}@kestrel"
        d["seq"] = rng.choice([0, 0, 0, 1, 2])
        d["cancelled"] = rng.random() < 0.08
    seenr = set()
    for a in rng.sample(pool, len(pool)):
        key = (a["runner"], iso(a["start"])[:10])
        if key not in seenr:
            seenr.add(key)
            w.reserv.append({"runner": a["runner"], "date": key[1], "id": f"rv-{len(w.reserv) + 1:06d}"})
        if len(w.reserv) >= n:
            break
    # ---- retry budgets, amendments ---------------------------------------------------
    w.budgets = {}
    for j in rng.sample(sorted(w.jobs), min(n, len(w.jobs))):
        k = len(w.job_atts[j])
        w.budgets[j] = max(1, k - 1) if rng.random() < 0.55 else k + rng.randrange(0, 2)
    w.amend = {}
    for i, j in enumerate(rng.sample(sorted(w.jobs), min(n, len(w.jobs)))):
        ratified = rng.randrange(P0 - 30 * 86400, KCUT + 10 * 86400)
        w.amend[j] = {"id": f"AM-{i + 1:06d}", "job": j, "klass": rng.choice(["priority", "batch"]),
                      "ratified": ratified}
    # ---- errata + approvals -----------------------------------------------------------
    w.errata, w.mails = [], []
    for i, a in enumerate(rng.sample(w.attempts, n)):
        new = rng.choice([s for s in STATUSES if s != a["status"]])
        e = {"id": f"ER-{i + 1:06d}", "attempt": a["id"], "old": a["status"], "new": new,
             "filed": rng.randrange(P0, KCUT)}
        w.errata.append(e)
    k = 0
    for e in w.errata:
        if len(w.mails) >= n:
            break
        roll = rng.random()
        if roll < 0.08:
            continue   # never decided: pending
        t = e["filed"] + rng.randrange(600, 5 * 86400)
        dec = rng.choices(["APPROVED", "REJECTED", "HOLD"], [0.6, 0.25, 0.15])[0]
        w.mails.append({"erratum": e["id"], "at": t, "decision": dec})
        if roll > 0.88 and len(w.mails) < n:
            t2 = t + rng.randrange(600, 3 * 86400)
            dec2 = "REJECTED" if dec == "APPROVED" else "APPROVED"
            w.mails.append({"erratum": e["id"], "at": t2, "decision": dec2})
    while len(w.mails) < n:
        e = rng.choice(w.errata)
        w.mails.append({"erratum": e["id"], "at": rng.randrange(e["filed"], KCUT + 6 * 86400), "decision": "HOLD"})
    for i, m in enumerate(w.mails):
        m["mid"] = f"m{i + 1:06d}.{seed % 9973}@approvals.kestrel"
    # ---- junit failures + quarantine windows ---------------------------------------------
    w.junit, w.flaky = [], []
    fails = [a for a in w.attempts if a["status"] == "failed" and w.target_by[w.jobs[a["job"]]["target"]]["kind"] == "test"]
    rng.shuffle(fails)
    for a in fails:
        if len(w.junit) >= n:
            break
        quarantined = rng.random() < 0.5
        for c in range(rng.randrange(1, 3)):
            case = f"Test{rng.choice(words).title()}{rng.randrange(100)}"
            w.junit.append({"attempt": a["id"], "case": case, "dur": rng.randrange(5, 90000)})
            if quarantined or rng.random() < 0.3:
                lab = w.jobs[a["job"]]["target"]
                if rng.random() < 0.15:
                    lo, hi = a["start"] + 1, a["start"] + rng.randrange(60, 86400)   # starts just after
                else:
                    lo, hi = a["start"] - rng.randrange(0, 5 * 86400), a["start"] + rng.randrange(0, 5 * 86400)
                w.flaky.append({"target": lab, "case": case, "lo": lo, "hi": hi})
    while len(w.flaky) < n:
        t = rng.choice(w.targets)
        lo = rng.randrange(P0 - 86400, P1)
        w.flaky.append({"target": t["label"], "case": f"TestIdle{rng.randrange(10 ** 6)}", "lo": lo, "hi": lo + 86400})
    # ---- lookups, cache writes, evictions ---------------------------------------------
    keys = sorted(w.actions)
    w.writes = []
    by_shard = {s: [k_ for k_ in keys if w.actions[k_]["shard"] == s] for s in (1, 2, 3)}
    w.lookups = []
    lid = 0
    for shard in (1, 2, 3):
        for _ in range(n):
            a = rng.choice(w.attempts)
            if rng.random() < 0.08:
                key = rng.choice([k_ for k_ in rng.sample(keys, 5) if w.actions[k_]["shard"] != shard] or keys[:1])
            else:
                key = rng.choice(by_shard[shard])
            at = a["start"] + rng.randrange(0, max(1, a["dur"] // 1000))
            lid += 1
            w.lookups.append({"id": None, "attempt": a["id"], "key": key, "at": at, "logged": shard,
                              "raw": "HIT" if rng.random() < 0.7 else "MISS", "bytes": rng.randrange(1, 60000) * 1024})
    ids = rng.sample(range(10 ** 7, 10 ** 8 - 1), len(w.lookups))
    for lk, i in zip(w.lookups, ids):
        lk["id"] = f"lk-{i:08d}"
    for lk in w.lookups:
        if lk["raw"] == "HIT":
            w.writes.append({"key": lk["key"], "at": lk["at"] - rng.randrange(60, 6 * 86400)})
    w.evictions = []
    hits = [lk for lk in w.lookups if lk["raw"] == "HIT" and lk["logged"] == w.actions[lk["key"]]["shard"]
            and w.actions[lk["key"]]["declared"] and set(w.actions[lk["key"]]["env"]) <= set(ALLOWED_ENV)]
    for lk in rng.sample(hits, min(n, len(hits) // 2)):
        w.evictions.append({"key": lk["key"], "shard": w.actions[lk["key"]]["shard"], "lk": lk["id"], "at": None})
    nonherm = [lk for lk in w.lookups if lk["raw"] == "HIT" and lk["logged"] == w.actions[lk["key"]]["shard"]
               and not (w.actions[lk["key"]]["declared"] and set(w.actions[lk["key"]]["env"]) <= set(ALLOWED_ENV))]
    for lk in rng.sample(nonherm, len(nonherm) // 10):
        w.evictions.append({"key": lk["key"], "shard": w.actions[lk["key"]]["shard"], "lk": lk["id"], "at": None})
    write_by = {}
    for x in w.writes:
        write_by.setdefault(x["key"], []).append(x["at"])
    w.write_by = {k_: sorted(v) for k_, v in write_by.items()}
    lk_by = {lk["id"]: lk for lk in w.lookups}
    for ev in w.evictions:
        lk = lk_by[ev["lk"]]
        last = max(t for t in w.write_by[lk["key"]] if t <= lk["at"])
        ev["at"] = lk["at"] if rng.random() < 0.1 else rng.randrange(last + 1, lk["at"] + 1)
    while len(w.evictions) < n:
        key = rng.choice(keys)
        w.evictions.append({"key": key, "shard": (w.actions[key]["shard"] % 3) + 1, "lk": None,
                            "at": rng.randrange(P0 - 86400, P1)})
    w.evictions.sort(key=lambda e: (e["at"], e["key"]))
    for i, ev in enumerate(w.evictions):
        ev["id"] = f"ev-{i + 1:07d}"
    # ---- artifacts + gc ------------------------------------------------------------------
    w.artifacts, w.gc = [], []
    for i in range(n):
        t = rng.choice(w.targets)
        created = rng.randrange(P0 - 20 * 86400, P1 - 3600)
        w.artifacts.append({"id": f"ar-{rng.randrange(10 ** 7, 10 ** 8):08d}-{i:05d}", "target": t["label"],
                            "bytes": rng.randrange(1, 9000) * 1048576, "created": created})
    for ar in w.artifacts:
        if len(w.gc) >= n:
            break
        t = ar["created"] + rng.randrange(3600, 25 * 86400)
        w.gc.append({"artifact": ar["id"], "at": t, "action": "delete"})
        if rng.random() < 0.3 and len(w.gc) < n:
            w.gc.append({"artifact": ar["id"], "at": t + rng.randrange(600, 5 * 86400), "action": "restore"})
    # ---- invoice lines + vendor statements --------------------------------------------
    w.vendors = {}
    for f in fleets:
        for i in range(6):
            w.vendors[f"VA-{f[:1].upper()}{i:02d}"] = {"locale": rng.choice(LOCALES), "fleet": f}
    w.invoice = []
    for r in w.runners:
        va = rng.choice([v for v in sorted(w.vendors) if w.vendors[v]["fleet"] == r["fleet"]])
        for wk in range(5):
            w.invoice.append({"id": f"iv-{len(w.invoice) + 1:07d}", "runner": r["id"], "week": wk, "vendor": va,
                              "delta": 0, "credit": 0, "closed": False})
    for iv in w.invoice:
        roll = rng.random()
        if roll < 0.12:
            iv["delta"] = rng.randrange(1000, 900000)
            if rng.random() < 0.5:
                iv["credit"] = iv["delta"]
            elif rng.random() < 0.5:
                iv["closed"] = True
        elif roll < 0.14:
            iv["closed"] = True                  # delta 0: billed == computed, so closed must beat match
    # ---- ledger --------------------------------------------------------------------
    w.opening = {}
    for cc in w.ccs:
        for b in ("carry", "compute", "credit", "manual", "storage"):
            w.opening[(cc, b)] = rng.randrange(-5 * 10 ** 9, 50 * 10 ** 9)
    w.postings = []
    for i in range(n):
        cc = rng.choice(w.ccs)
        w.postings.append({"id": f"po-{i + 1:07d}", "cc": cc, "amount": rng.randrange(-2 * 10 ** 9, 8 * 10 ** 9),
                           "at": rng.randrange(P0 - 3 * 86400, P1 + 2 * 86400), "reverses": None, "void": False})
    for p in rng.sample(w.postings, n // 12):
        q = rng.choice(w.postings)
        if q is not p and q["reverses"] is None and p["reverses"] is None:
            p["reverses"] = q["id"]
    for p in rng.sample(w.postings, n // 25):
        p["void"] = True
    return w


# ---------------------------------------------------------------------------------
# truth engine
# ---------------------------------------------------------------------------------
def glob_match(pat, label):
    rx = ""
    i = 0
    while i < len(pat):
        if pat.startswith("**", i):
            rx += ".*"
            i += 2
        elif pat[i] == "*":
            rx += "[^/:]*"
            i += 1
        else:
            rx += _re.escape(pat[i])
            i += 1
    return _re.fullmatch(rx, label) is not None


def _pat_index(w):
    if getattr(w, "_pidx", None) is None:
        idx = {}
        for p in w.patterns:
            pat = p["pattern"][1:] if p["pattern"].startswith("!") else p["pattern"]
            lit = pat.split("*", 1)[0]
            idx.setdefault(lit, []).append(p)
        w._pidx = idx
    return w._pidx


def owner_of(w, label, wrong=frozenset()):
    """Last matching line wins; a negated last match leaves the target unowned."""
    idx = _pat_index(w)
    cands = []
    for k in range(1, len(label) + 1):
        cands.extend(idx.get(label[:k], []))
    cands.sort(key=lambda p: p["seq"], reverse="first_match" in wrong)
    hit = None
    for p in cands:
        pat = p["pattern"]
        neg = pat.startswith("!")
        if glob_match(pat[1:] if neg else pat, label):
            hit = None if neg else p["handle"]
    return hit


def canon_handle(w, h, wrong=frozenset()):
    if h in w.renames and "ignore_rename" not in wrong:
        new, eff = w.renames[h]
        if eff <= KCUT:
            return new
    return h


def team_of(w, h, t):
    rec = w.handles[h]
    if rec["moved"] and rec["moved"][1] <= t:
        return rec["moved"][0]
    return rec["team"]


def cc_of(w, h, t, wrong=frozenset()):
    rec = w.handles[h]
    cc = rec["cc"]
    if rec["cc_move"] and rec["cc_move"][1] <= t:
        cc = rec["cc_move"][0]
    if cc in w.cc_merges and w.cc_merges[cc][1] <= t and "ignore_merge" not in wrong:
        cc = w.cc_merges[cc][0]
    return cc


def rev_at(w, rid, t):
    best = None
    for rev in w.runner_by[rid]["revs"]:
        if rev["eff"] <= t:
            best = rev
    return best


def rate_rows(w, cls, region, wrong=frozenset()):
    if getattr(w, "_ridx", None) is None:
        w._ridx = {}
        for r in w.rates:
            w._ridx.setdefault((r["cls"], r["region"]), []).append(r)
    ck = (cls, region, "late_rates" in wrong, "first_recorded" in wrong)
    cache = w.__dict__.setdefault("_rcache", {})
    if ck in cache:
        return cache[ck]
    rows = [r for r in w._ridx.get((cls, region), []) if (r["rec"] <= KCUT or "late_rates" in wrong)]
    best = {}
    for r in sorted(rows, key=lambda r: (r["eff"], r["rec"])):
        if "first_recorded" in wrong and r["eff"] in best:
            continue
        best[r["eff"]] = r
    cache[ck] = [best[e] for e in sorted(best)]
    return cache[ck]


def rate_at(w, cls, region, t, wrong=frozenset()):
    cur = None
    for r in rate_rows(w, cls, region, wrong):
        if r["eff"] <= t:
            cur = r
    return cur


def compute(w, wrong=frozenset()):
    out = {}
    tags = {}
    # toolchain resolution and invalidation closure
    tver = {}
    for t in w.targets:
        v0 = resolve(w, t["tc"], t["cons"], P0, wrong)
        v1 = resolve(w, t["tc"], t["cons"], P1 - 1, wrong)
        tver[t["label"]] = (v0, v1)
    inval = {t["label"]: tver[t["label"]][0] != tver[t["label"]][1] for t in w.targets}
    parents = {}
    for e in w.edges:
        if e["kind"] == "data" and "data_edges" not in wrong:
            continue
        parents.setdefault(e["child"], []).append(e["parent"])
    for t in w.targets:          # index order is topological (parents precede)
        if not inval[t["label"]]:
            inval[t["label"]] = any(inval[p] for p in parents.get(t["label"], []))
    # ownership
    owner = {}
    for t in w.targets:
        h = owner_of(w, t["label"], wrong)
        owner[t["label"]] = canon_handle(w, h, wrong) if h else None
    # errata decisions
    latest = {}
    for m in sorted(w.mails, key=lambda m: (m["at"], m["mid"])):
        if m["at"] <= KCUT:
            latest[m["erratum"]] = m["decision"]
    status = {a["id"]: a["status"] for a in w.attempts}
    if "ignore_errata" not in wrong:
        for e in w.errata:
            dec = latest.get(e["id"])
            if dec == "APPROVED" or ("errata_unapproved" in wrong and dec is not None):
                status[e["attempt"]] = e["new"]
    # quarantine
    fq = {}
    for f in w.flaky:
        fq.setdefault((f["target"], f["case"]), []).append((f["lo"], f["hi"]))
    jcases = {}
    for j in w.junit:
        jcases.setdefault(j["attempt"], []).append(j["case"])
    drains = {}
    for d in w.drains:
        if not d["cancelled"]:
            drains.setdefault(d["runner"], []).append((d["lo"], d["hi"]))
    reserved = {(r["runner"], r["date"]) for r in w.reserv}
    amend = {j: a for j, a in w.amend.items() if a["ratified"] <= KCUT or "unratified" in wrong}
    att_rows = []
    for a in sorted(w.attempts, key=lambda a: a["id"]):
        job = w.jobs[a["job"]]
        label = job["target"] if "row_target" not in wrong else a["row_target"]
        tgt = w.target_by[label]
        start = a["start"] if "no_skew" not in wrong else a["rec_start"]
        rev = rev_at(w, a["runner"], start)
        sku = w.skus[rev["sku"]]
        region = rev["region"] if "stale_region" not in wrong else w.runner_by[a["runner"]]["base_region"]
        st = status[a["id"]]
        excl = None
        if not P0 <= start < P1:
            excl = "out_of_period"
        elif a["id"] in w.revoked and "ignore_revoke" not in wrong:
            excl = "revoked"
        elif any(lo <= start < hi for lo, hi in drains.get(a["runner"], [])):
            excl = "provider_drain"
        elif st == "cancelled" and a["origin"] == "platform" and "ignore_origin" not in wrong:
            excl = "platform_cancel"
        elif st == "failed" and a["id"] in jcases and all(
                any(lo <= start <= hi for lo, hi in fq.get((label, c), [])) for c in jcases[a["id"]]):
            excl = "quarantined_flake"
        elif st == "preempted" and a["dur"] < GRACE_S[a["fleet"]] * 1000:
            excl = "preempt_grace"
        elif a["no"] > w.budgets.get(a["job"], DEFAULT_BUDGET):
            excl = "over_budget"
        elif tgt["scope"] == "exempt":
            excl = "exempt_scope"
        h = owner[label] or canon_handle(w, job["submitter"], wrong)
        team = team_of(w, h, start)
        cc = cc_of(w, h, start, wrong)
        klass = amend[a["job"]]["klass"] if a["job"] in amend else "standard"
        rr = rate_at(w, sku["cls"], region, start, wrong)
        rate = rr["rate"] if rr else 0
        gran = sku["gran"]
        bs = -(-a["dur"] // (1000 * gran)) * gran
        res = (a["runner"], iso(start)[:10]) in reserved
        cost = 0
        if excl is None:
            fr = _F(bs * rate * CLASS_MULT[klass], 60 * 1000)
            if sku["spot"]:
                fr = fr * (1000 - w.spot_credit[sku["cls"]]) / 1000
            if res:
                fr = fr * RESERVED_PERMILLE / 1000
            cost = rhe(fr) if "half_up" not in wrong else rhu(fr)
        att_rows.append({"attempt_id": a["id"], "job_id": a["job"], "attempt_no": a["no"], "fleet": a["fleet"],
                         "runner": a["runner"], "runner_rev": rev["rev"], "region": region, "sku": sku["sku"],
                         "instance_class": sku["cls"], "target": label, "started_at": iso(start),
                         "duration_ms": a["dur"], "status": st, "exclusion": excl,
                         "billable_seconds": bs if excl is None else 0, "rate_micro_per_min": rate,
                         "billing_class": klass, "reserved": res, "cost_micro": cost,
                         "owner_handle": h, "team": team, "cost_center": cc})
    out["attempts.jsonl"] = att_rows
    att_out = {r["attempt_id"]: r for r in att_rows}
    # lookups
    hermetic = {k: (v["declared"] and set(v["env"]) <= set(ALLOWED_ENV)) for k, v in w.actions.items()}
    evs = {}
    for ev in w.evictions:
        evs.setdefault((ev["shard"], ev["key"]), []).append(ev)
    lk_rows = []
    for lk in sorted(w.lookups, key=lambda x: x["id"]):
        act = w.actions[lk["key"]]
        tgt = w.target_by[act["target"]]
        evid = None
        if lk["logged"] != act["shard"] and "count_replays" not in wrong:
            oc = "replay"
        elif lk["raw"] == "MISS":
            oc = "miss"
        elif not hermetic[lk["key"]]:
            oc = "nonhermetic_hit"
        else:
            last = max(t for t in w.write_by[lk["key"]] if t <= lk["at"])
            cands = [e for e in evs.get((act["shard"], lk["key"]), []) if last < e["at"] <= lk["at"]]
            if cands:
                oc, evid = "evicted_hit", min(cands, key=lambda e: (e["at"], e["id"]))["id"]
            elif resolve(w, tgt["tc"], tgt["cons"], last, wrong) != resolve(w, tgt["tc"], tgt["cons"], lk["at"], wrong):
                oc = "stale_hit"
            else:
                oc = "hit"
        lk_rows.append({"lookup_id": lk["id"], "attempt_id": lk["attempt"], "action_key": lk["key"],
                        "shard": lk["logged"], "at": iso(lk["at"]), "bytes": lk["bytes"], "outcome": oc,
                        "eviction_id": evid})
    out["lookups.jsonl"] = lk_rows
    # targets
    tg_rows = []
    for t in sorted(w.targets, key=lambda t: t["label"]):
        h = owner[t["label"]]
        tg_rows.append({"target": t["label"], "kind": t["kind"], "language": t["lang"], "toolchain": t["tc"],
                        "constraint": t["cons"], "version_at_open": tver[t["label"]][0],
                        "version_at_close": tver[t["label"]][1], "invalidated": inval[t["label"]],
                        "scope": t["scope"], "owner_handle": h, "team": team_of(w, h, P1 - 1) if h else None})
    out["targets.jsonl"] = tg_rows
    # actions
    ac_rows = []
    for k in sorted(w.actions):
        v = w.actions[k]
        t = w.target_by[v["target"]]
        ac_rows.append({"action_key": k, "target": v["target"], "home_shard": v["shard"],
                        "hermetic": hermetic[k], "undeclared_inputs": [] if v["declared"] else [v["path"]],
                        "input_bytes": v["input_bytes"],
                        "disallowed_env": sorted(set(v["env"]) - set(ALLOWED_ENV)),
                        "toolchain_version": tver[v["target"]][0]})
    out["actions.jsonl"] = ac_rows
    # artifacts
    gcs = {}
    for g in w.gc:
        gcs.setdefault(g["artifact"], []).append(g)
    ar_rows = []
    for ar in sorted(w.artifacts, key=lambda x: x["id"]):
        alive, t0, kept = True, ar["created"], 0
        for g in sorted(gcs.get(ar["id"], []), key=lambda g: g["at"]):
            if g["action"] == "delete" and alive:
                kept += max(0, min(g["at"], P1) - max(t0, P0))
                alive = False
            elif g["action"] == "restore" and not alive:
                alive, t0 = True, g["at"]
        if alive:
            kept += max(0, P1 - max(t0, P0))
        h = owner[ar["target"]]
        cost = rhe(_F(ar["bytes"] * kept * STORAGE_MICRO_PER_GIB_HOUR, 1073741824 * 3600))
        ar_rows.append({"artifact_id": ar["id"], "target": ar["target"], "bytes": ar["bytes"], "retained_seconds": kept,
                        "storage_cost_micro": cost, "team": team_of(w, h, P1 - 1) if h else None,
                        "cost_center": cc_of(w, h, P1 - 1, wrong) if h else None})
    out["artifacts.jsonl"] = ar_rows
    # invoice reconciliation
    comp = {}
    for r in att_rows:
        if r["exclusion"] is None:
            t = int(_dt.strptime(r["started_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_tz.utc).timestamp())
            wk = max(i for i in range(5) if WEEK_EDGES[i] <= t)
            comp[(r["runner"], wk)] = comp.get((r["runner"], wk), 0) + r["cost_micro"]
    iv_rows = []
    for iv in w.invoice:
        c = comp.get((iv["runner"], iv["week"]), 0)
        billed = c + iv["delta"]
        if iv["closed"] and "ignore_closure" not in wrong:
            st = "closed"
        elif billed == c:
            st = "match"
        elif billed - iv["credit"] == c:
            st = "credited"
        else:
            st = "mismatch"
        iv_rows.append({"line_id": iv["id"], "runner": iv["runner"], "week": iv["week"], "billed_micro": billed,
                        "credit_micro": iv["credit"], "computed_micro": c, "status": st})
    out["invoice_reconciliation.jsonl"] = iv_rows
    # team chargeback, cache effectiveness
    teams = {}
    for r in att_rows:
        d = teams.setdefault(r["team"], {"attempts_billed": 0, "compute_micro": 0, "storage_micro": 0,
                                         "cache_credit_micro": 0})
        if r["exclusion"] is None:
            d["attempts_billed"] += 1
            d["compute_micro"] += r["cost_micro"]
    for r in ar_rows:
        if r["team"]:
            teams.setdefault(r["team"], {"attempts_billed": 0, "compute_micro": 0, "storage_micro": 0,
                                         "cache_credit_micro": 0})["storage_micro"] += r["storage_cost_micro"]
    cache = {}
    for r in lk_rows:
        team = att_out[r["attempt_id"]]["team"]
        d = cache.setdefault(team, {k: 0 for k in ("evicted_hit", "hit", "miss", "nonhermetic_hit", "replay", "stale_hit")})
        d[r["outcome"]] += 1
        if r["outcome"] == "hit":
            teams.setdefault(team, {"attempts_billed": 0, "compute_micro": 0, "storage_micro": 0,
                                    "cache_credit_micro": 0})["cache_credit_micro"] += CACHE_CREDIT_MICRO
    for d in cache.values():
        den = d["hit"] + d["miss"] + d["stale_hit"] + d["evicted_hit"] + d["nonhermetic_hit"]
        d["valid_hit_permille"] = d["hit"] * 1000 // den if den else 0
    for d in teams.values():
        d["net_micro"] = d["compute_micro"] + d["storage_micro"] - d["cache_credit_micro"]
    out["team_chargeback.json"] = {k: teams[k] for k in sorted(teams)}
    out["cache_effectiveness.json"] = {k: cache[k] for k in sorted(cache)}
    # cost centre ledger
    led = {cc: {"opening_micro": sum(w.opening[(cc, b)] for b in ("carry", "compute", "credit", "manual", "storage")),
                "postings_micro": 0, "charges_micro": 0} for cc in w.ccs}
    reversed_ids = {p["reverses"] for p in w.postings if p["reverses"]}
    for p in w.postings:
        if not P0 <= p["at"] < P1:
            continue
        if p["void"] and "ignore_voids" not in wrong:
            continue
        if p["id"] in reversed_ids and "ignore_reversal" not in wrong:
            continue
        if p["reverses"] and "ignore_reversal" not in wrong:
            continue
        cc = p["cc"]
        if cc in w.cc_merges and w.cc_merges[cc][1] <= p["at"] and "ignore_merge" not in wrong:
            cc = w.cc_merges[cc][0]
        led[cc]["postings_micro"] += p["amount"]
    for r in att_rows:
        if r["exclusion"] is None:
            led[r["cost_center"]]["charges_micro"] += r["cost_micro"]
    for r in ar_rows:
        if r["cost_center"]:
            led[r["cost_center"]]["charges_micro"] += r["storage_cost_micro"]
    for d in led.values():
        d["closing_micro"] = d["opening_micro"] + d["postings_micro"] + d["charges_micro"]
    out["cost_center_ledger.json"] = {k: led[k] for k in sorted(led)}
    # rate resolution
    rr = {}
    for cls in CLASSES:
        for region in REGIONS:
            rows = rate_rows(w, cls, region, wrong)
            cur = [r for r in rows if r["eff"] <= P0]
            win = ([cur[-1]] if cur else []) + [r for r in rows if P0 < r["eff"] < P1]
            rr[f"{cls}|{region}"] = [[iso(max(r["eff"], P0)), r["rate"]] for r in win]
    out["rate_resolution.json"] = rr
    out["_tver"] = tver
    return out


def close_summary(out, controls):
    att = out["attempts.jsonl"]
    tc = out["team_chargeback.json"]
    artifacts = out["artifacts.jsonl"]
    compute = sum(d["compute_micro"] for d in tc.values())
    storage = sum(r["storage_cost_micro"] for r in artifacts)
    credit = sum(d["cache_credit_micro"] for d in tc.values())
    return {"attempts_listed": len(att),
            "attempts_billed": sum(1 for r in att if r["exclusion"] is None),
            "compute_micro": compute,
            "storage_micro": storage,
            "cache_credit_micro": credit,
            "net_micro": compute + storage - credit,
            "invoice_mismatches": sum(1 for r in out["invoice_reconciliation.jsonl"] if r["status"] == "mismatch"),
            "controls_mismatched": sum(1 for c in controls.values() if not c["match"]),
            "closing_micro": sum(d["closing_micro"] for d in out["cost_center_ledger.json"].values())}
# ---------------------------------------------------------------------------------
# codecs: canonical value -> surface string
# ---------------------------------------------------------------------------------
XL_EPOCH = -2209161600
CODECS = {
    "ts": ["iso_z", "epoch", "epoch_ms", "utc_naive", "local", "iso_off", "xl1900"],
    "dur": ["ms", "us", "ns", "s3"],
    "money": ["usd6", "micro", "eu6", "kusd9"],
    "int": ["plain", "sep", "eu"],
    "bytes": ["plain", "kib", "sep"],
    "key": ["exact", "upper", "ws"],
}
FACE = {"ts": "iso_z", "dur": "ms", "money": "usd6", "int": "plain", "bytes": "plain", "key": "exact"}
FAMILY_OF = {"ts": "T3", "dur": "T2", "money": "T4", "int": "T4", "bytes": "T2", "key": "T1"}
CODEC_DOC = [
    ("iso_z", "timestamp", "ISO 8601 UTC with a trailing Z, for example 2025-10-03T04:05:06Z"),
    ("epoch", "timestamp", "whole seconds since 1970-01-01T00:00:00Z"),
    ("epoch_ms", "timestamp", "whole milliseconds since 1970-01-01T00:00:00Z"),
    ("utc_naive", "timestamp", "YYYY-MM-DD HH:MM:SS read as UTC"),
    ("local", "timestamp", "YYYY-MM-DD HH:MM:SS read as wall time in the clock zone of the row's runner"),
    ("iso_off", "timestamp", "ISO 8601 wall time with an explicit numeric offset"),
    ("xl1900", "timestamp", "spreadsheet serial day number counted from 1899-12-30T00:00:00Z, fraction is time of day in UTC"),
    ("ms", "duration", "integer milliseconds"),
    ("us", "duration", "integer microseconds"),
    ("ns", "duration", "integer nanoseconds"),
    ("s3", "duration", "seconds with exactly three decimals"),
    ("usd6", "money", "US dollars with a dot decimal separator and exactly six decimals, leading minus for negatives"),
    ("micro", "money", "integer micro-dollars"),
    ("eu6", "money", "US dollars, dot as thousands separator, comma decimal separator, six decimals"),
    ("kusd9", "money", "thousands of US dollars with exactly nine decimals"),
    ("plain", "integer", "decimal digits only"),
    ("sep", "integer", "decimal digits with a comma every three digits"),
    ("eu", "integer", "decimal digits with a dot every three digits"),
    ("kib", "integer", "byte counts expressed in KiB (value times 1024 is the byte count)"),
    ("exact", "identifier", "the identifier exactly as written"),
    ("upper", "identifier", "the identifier in upper case; canonical identifiers are lower case"),
    ("ws", "identifier", "the identifier padded with spaces; surrounding spaces are not part of it"),
]


def _group(n, sep):
    s = str(n)
    out = []
    while len(s) > 3:
        out.append(s[-3:])
        s = s[:-3]
    out.append(s)
    return sep.join(reversed(out))


def enc(ltype, codec, v, zone=None):
    if v is None:
        return ""
    if ltype == "ts":
        if codec == "iso_z":
            return iso(v)
        if codec == "epoch":
            return str(v)
        if codec == "epoch_ms":
            return str(v * 1000)
        if codec == "utc_naive":
            return iso(v).replace("T", " ")[:-1]
        if codec == "local":
            return iso(v + zoff(zone, v) * 60).replace("T", " ")[:-1]
        if codec == "iso_off":
            off = zoff(zone, v)
            sign = "+" if off >= 0 else "-"
            return iso(v + off * 60)[:-1] + f"{sign}{abs(off) // 60:02d}:{abs(off) % 60:02d}"
        if codec == "xl1900":
            return f"{_F(v - XL_EPOCH, 86400).numerator / _F(v - XL_EPOCH, 86400).denominator:.6f}"
    if ltype == "dur":
        if codec == "ms":
            return str(v)
        if codec == "us":
            return str(v * 1000)
        if codec == "ns":
            return str(v * 1000000)
        if codec == "s3":
            return f"{v // 1000}.{v % 1000:03d}"
    if ltype == "money":
        sign = "-" if v < 0 else ""
        a = abs(v)
        if codec == "usd6":
            return f"{sign}{a // 10 ** 6}.{a % 10 ** 6:06d}"
        if codec == "micro":
            return str(v)
        if codec == "eu6":
            return f"{sign}{_group(a // 10 ** 6, '.')},{a % 10 ** 6:06d}"
        if codec == "kusd9":
            return f"{sign}{a // 10 ** 9}.{a % 10 ** 9:09d}"
    if ltype in ("int", "bytes"):
        if codec == "plain":
            return str(v)
        if codec == "sep":
            return ("-" if v < 0 else "") + _group(abs(v), ",")
        if codec == "eu":
            return ("-" if v < 0 else "") + _group(abs(v), ".")
        if codec == "kib":
            return str(v // 1024)
    if ltype == "key":
        if codec == "exact":
            return v
        if codec == "upper":
            return v.upper()
        if codec == "ws":
            return f"  {v} "
    raise ValueError((ltype, codec))


def canon_num(ltype, v):
    """Integer used in control sums."""
    if v is None:
        return 0
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    return int(_hashlib.sha256(str(v).encode()).hexdigest()[:6], 16)
# ---------------------------------------------------------------------------------
# file specs, structural traps, writers, manifest
# ---------------------------------------------------------------------------------
HOSTS = ["settlement_authority.md", "scope_rules.md", "field_precedence.html", "rate_methodology.pdf",
         "amendment_minutes.docx", "errata_register.docx", "audit_annex.pdf"]
DECOYS = {
    "attempt_events_v3.jsonl": "pull", "usage_export_legacy.log": "push", "lookups_archive.jsonl.gz": "push",
    "toolchain_pins_resolved.json": "pull", "ownership_patterns_approved.tsv": "pull", "rate_card_final.xlsx": "pull",
    "invoice_restatement.csv": "pull", "control_totals_draft.html": "push"}
WRONG = frozenset({"late_rates", "naive_caret", "verstr", "first_match", "ignore_rename", "errata_unapproved",
                   "no_skew", "half_up", "stale_region", "data_edges"})
BLOCK = 50
NBATCH = 12


class Spec:
    def __init__(self, name, table, cols, recs, ctx, control, coded=(), consumers=(), link=None):
        self.name, self.table, self.cols, self.recs, self.ctx = name, table, list(cols), recs, ctx
        self.control, self.coded, self.consumers = control, list(coded), list(consumers)
        self.link = link or {}
        self.codecs = {}
        self.extra = []      # (table name, cols, rows) small or appendix tables
        self.prose = []      # paragraphs (docs only)
        self.alias = None    # (column, alias, from_index)
        self.order = None    # reordered column list after split
        self.split = None
        self.fmt = name.split(".", 1)[1]


def _ltype(spec, col):
    return dict(spec.cols)[col]


def _sorted_ctx(spec):
    vals = sorted({r["_ctx"] for r in spec.recs})
    return vals


def build_specs(w, truth, wrongout):
    S = {}
    zone_of = lambda rid: w.runner_by[rid]["base_region"]
    lang_of = lambda lab: w.target_by[lab]["lang"]
    org_of = lambda h: w.team_org[w.handles[h]["team"]]
    att = w.att_by
    rng = _random.Random(w.seed * 7 + 11)

    def batch(recs):
        n = len(recs)
        for i, r in enumerate(recs):
            r["_ctx"] = f"B{1 + i * NBATCH // n}"
        return recs

    def zsort(recs, key):
        for r in recs:
            if "_job" in r:
                r["_ctx"] = lang_of(w.jobs[r.pop("_job")]["target"])
        return sorted(recs, key=lambda r: (r["_ctx"], r[key]))

    # --- runner domain ------------------------------------------------------------
    recs = [{"runner": v["runner"], "rev": v["rev"], "effective_from": v["eff"], "sku": v["sku"],
             "agent_version": v["ver"], "region": w.runner_by[v["runner"]]["base_region"],
             "_ctx": zone_of(v["runner"])} for v in w.revs]
    S["fleet_policy.ini"] = Spec("fleet_policy.ini", "runner", [("runner", "key"), ("rev", "int"),
                                 ("effective_from", "ts"), ("sku", "key"), ("agent_version", "str"), ("region", "str")],
                                 zsort(recs, "sku"), "region", "effective_from", ["effective_from", "sku", "runner"],
                                 ["attempts.jsonl"], {"runner": "runner"})
    sku_zone = {v["sku"]: zone_of(v["runner"]) for v in w.revs}
    sku_eff = {v["sku"]: v["eff"] for v in w.revs}
    recs = [{"sku": s["sku"], "instance_class": s["cls"], "arch": s["arch"], "spot": "true" if s["spot"] else "false",
             "listed_at": sku_eff[s["sku"]] - 86400 * (1 + int(s["sku"][-2:], 36) % 40), "_ctx": sku_zone[s["sku"]]}
            for s in w.skus.values()]
    S["instance_classes.csv"] = Spec("instance_classes.csv", "records", [("sku", "key"), ("instance_class", "str"),
                                     ("arch", "str"), ("spot", "str"), ("listed_at", "ts")], zsort(recs, "sku"), "region",
                                     "listed_at", ["sku", "listed_at"], ["attempts.jsonl"], {"sku": "sku"})
    recs = batch([{"sku": s["sku"], "granularity_s": s["gran"], "_k": s["sku"]} for s in sorted(w.skus.values(), key=lambda s: s["sku"])])
    S["rate_methodology.pdf"] = Spec("rate_methodology.pdf", "Billing granularity", [("sku", "key"), ("granularity_s", "int")],
                                     recs, "batch", "granularity_s", ["sku"], ["attempts.jsonl"], {"sku": "sku"})
    recs = batch([{"runner": v["runner"], "rev": v["rev"], "region": v["region"], "_k": v["runner"]}
                  for v in sorted(w.revs, key=lambda v: (v["runner"], v["rev"]))])
    S["settlement_authority.md"] = Spec("settlement_authority.md", "Runner placements",
                                        [("runner", "key"), ("rev", "int"), ("region", "str")], recs, "batch", "rev",
                                        ["runner"], ["attempts.jsonl"], {"runner": "runner"})
    recs = [{"runner": s["runner"], "window_from": s["lo"] + s["skew"], "window_to": s["hi"] + s["skew"],
             "skew_ms": s["skew"] * 1000, "_ctx": zone_of(s["runner"])} for s in w.skews]
    S["clock_sync.txt"] = Spec("clock_sync.txt", "records", [("runner", "key"), ("window_from", "ts"), ("window_to", "ts"),
                               ("skew_ms", "int")], zsort(recs, "runner"), "region", "skew_ms",
                               ["runner", "window_from", "window_to", "skew_ms"], ["attempts.jsonl"], {"runner": "runner"})
    recs = []
    for d in w.drains:
        for s in range(d["seq"] + 1):
            final = s == d["seq"]
            lo = d["lo"] if final else d["lo"] - rng.randrange(600, 7200)
            hi = d["hi"] if final else d["hi"] + rng.randrange(-300, 3600)
            recs.append({"uid": d["uid"], "sequence": s, "status": "CANCELLED" if (final and d["cancelled"]) else "CONFIRMED",
                         "dtstart": lo, "dtend": hi, "runner": d["runner"], "_ctx": zone_of(d["runner"])})
    S["change_freeze.ics"] = Spec("change_freeze.ics", "VEVENT", [("uid", "str"), ("sequence", "int"), ("status", "str"),
                                  ("dtstart", "ts"), ("dtend", "ts"), ("runner", "key")], zsort(recs, "uid"), "region",
                                  "dtstart", ["dtstart", "dtend", "runner"], ["attempts.jsonl"], {"runner": "runner"})
    recs = [{"id": r["id"], "runner": r["runner"], "date": r["date"],
             "day": int(_dt.strptime(r["date"], "%Y-%m-%d").replace(tzinfo=_tz.utc).timestamp()),
             "_ctx": zone_of(r["runner"])} for r in w.reserv]
    S["close_parameters.toml"] = Spec("close_parameters.toml", "reservation", [("id", "str"), ("runner", "key"),
                                      ("day", "ts")], zsort(recs, "id"), "region", "day", ["runner", "day"],
                                      ["attempts.jsonl"], {"runner": "runner"})
    for fleet, fname in (("north", "fleet_north.log"), ("south", "fleet_south.log")):
        recs = []
        for a in w.attempts:
            if a["fleet"] != fleet:
                continue
            m0 = a["mono0"] // 10 ** 6
            wall_end = a["rec_start"] + a["dur"] // 1000 + rng.choice([0, 0, 1, -1, 2])
            recs.append({"ts": a["rec_start"], "attempt": a["id"], "job": a["job"], "no": a["no"], "runner": a["runner"],
                         "target": a["row_target"], "status": a["status"], "mono_start": m0, "mono_end": m0 + a["dur"],
                         "wall_end": wall_end, "_ctx": None, "_job": a["job"], "_zone": REGION_ZONE[zone_of(a["runner"])]})
        S[fname] = Spec(fname, "records", [("ts", "ts"), ("attempt", "key"), ("job", "key"), ("no", "int"),
                        ("runner", "key"), ("target", "str"), ("status", "str"), ("mono_start", "dur"),
                        ("mono_end", "dur"), ("wall_end", "ts")], zsort(recs, "attempt"), "lang", "mono_end",
                        ["ts", "attempt", "job", "runner", "mono_start", "wall_end"], ["attempts.jsonl"], {"job": "job"})
    recs = [{"attempt_id": a["id"], "job_id": a["job"], "attempt": a["no"], "runner": a["runner"],
             "target": a["row_target"], "status": a["status"], "started": a["rec_start"], "duration_ms": a["dur"],
             "_ctx": None, "_job": a["job"], "_zone": REGION_ZONE[zone_of(a["runner"])]} for a in w.attempts if a["fleet"] == "east"]
    S["attempt_events.jsonl"] = Spec("attempt_events.jsonl", "records", [("attempt_id", "key"), ("job_id", "key"),
                                     ("attempt", "int"), ("runner", "key"), ("target", "str"), ("status", "str"),
                                     ("started", "ts"), ("duration_ms", "dur")], zsort(recs, "attempt_id"), "lang",
                                     "duration_ms", ["attempt_id", "job_id", "runner", "started", "duration_ms"],
                                     ["attempts.jsonl"], {"job": "job"})
    west = [a for a in w.attempts if a["fleet"] == "west"]
    recs = []
    for a in west:
        idem = "idem-" + _hashlib.sha256(a["id"].encode()).hexdigest()[:12]
        recs.append({"idem": idem, "attempt": a["id"], "job": a["job"], "seq": a["no"], "runner": a["runner"],
                     "target": a["row_target"], "state": a["status"], "start": a["rec_start"], "elapsed": a["dur"],
                     "received": a["rec_start"] + a["dur"] // 1000 + rng.randrange(1, 900), "_ctx": None, "_job": a["job"],
                     "_zone": REGION_ZONE[zone_of(a["runner"])]})
    S["usage_events.jsonl"] = Spec("usage_events.jsonl", "records", [("idem", "str"), ("attempt", "key"), ("job", "key"),
                                   ("seq", "int"), ("runner", "key"), ("target", "str"), ("state", "str"),
                                   ("start", "ts"), ("elapsed", "dur"), ("received", "ts")], zsort(recs, "attempt"),
                                   "lang", "elapsed", ["attempt", "job", "runner", "start", "elapsed", "received"],
                                   ["attempts.jsonl"], {"job": "job"})
    recs = [{"attempt": j["attempt"], "testcase": j["case"], "time": j["dur"], "_ctx": None, "_job": att[j["attempt"]]["job"]}
            for j in w.junit]
    S["junit_results.xml"] = Spec("junit_results.xml", "testcase", [("attempt", "key"), ("testcase", "str"),
                                  ("time", "dur")], zsort(recs, "attempt"), "lang", "time", ["attempt", "time"],
                                  ["attempts.jsonl"], {"attempt_job": "attempt"})
    recs = [{"id": e["id"], "attempt": e["attempt"], "field": "status", "old": e["old"], "new": e["new"],
             "filed": e["filed"], "_ctx": None, "_job": att[e["attempt"]]["job"],
             "_zone": REGION_ZONE[zone_of(att[e["attempt"]]["runner"])]} for e in w.errata]
    S["errata_register.docx"] = Spec("errata_register.docx", "Errata", [("id", "str"), ("attempt", "key"),
                                     ("field", "str"), ("old", "str"), ("new", "str"), ("filed", "ts")],
                                     zsort(recs, "id"), "lang", "filed", ["attempt", "filed"], ["attempts.jsonl"],
                                     {"attempt_job": "attempt"})
    er_by = {e["id"]: e for e in w.errata}
    recs = [{"mid": m["mid"], "erratum": m["erratum"], "decision": m["decision"], "decided_at": m["at"],
             "lag": rng.randrange(0, 7200), "_ctx": None, "_job": att[er_by[m["erratum"]]["attempt"]]["job"],
             "_zone": REGION_ZONE[zone_of(att[er_by[m["erratum"]]["attempt"]]["runner"])]}
            for m in w.mails]
    S["approval_thread.mbox"] = Spec("approval_thread.mbox", "message", [("mid", "str"), ("erratum", "str"),
                                     ("decision", "str"), ("decided_at", "ts")], zsort(recs, "mid"), "lang",
                                     "decided_at", ["decided_at"], ["attempts.jsonl"], {"erratum_job": "erratum"})
    ivt = {r["line_id"]: r for r in truth["invoice_reconciliation.jsonl"]}
    recs = [{"line_id": iv["id"], "runner": iv["runner"], "week_start": WEEK_EDGES[iv["week"]], "vendor": iv["vendor"],
             "billed": ivt[iv["id"]]["billed_micro"], "_ctx": w.vendors[iv["vendor"]]["locale"]} for iv in w.invoice]
    S["invoice_lines.xlsx"] = Spec("invoice_lines.xlsx", "Lines", [("line_id", "key"), ("runner", "key"),
                                   ("week_start", "ts"), ("vendor", "str"), ("billed", "money")],
                                   zsort(recs, "line_id"), "locale", "billed", ["line_id", "runner", "week_start", "billed"],
                                   ["invoice_reconciliation.jsonl"], {"vendor": "vendor"})
    recs = [{"line": iv["id"], "vendor": iv["vendor"], "locale": w.vendors[iv["vendor"]]["locale"],
             "credit": iv["credit"], "runner": iv["runner"], "_ctx": zone_of(iv["runner"])} for iv in w.invoice]
    S["vendor_statement.xml"] = Spec("vendor_statement.xml", "Line", [("line", "key"), ("vendor", "str"),
                                     ("locale", "str"), ("credit", "money"), ("runner", "key")],
                                     zsort(recs, "line"), "region", "credit", ["line", "credit", "runner"],
                                     ["invoice_reconciliation.jsonl"], {"runner": "runner"})
    # --- rates ----------------------------------------------------------------------
    recs = [{"rate_id": r["id"], "instance_class": r["cls"], "region": r["region"], "effective_from": r["eff"],
             "recorded_at": r["rec"], "micro_per_min": r["rate"], "_ctx": r["region"]}
            for r in w.rates if not r["late"]]
    S["rate_card.xlsx"] = Spec("rate_card.xlsx", "Rates", [("rate_id", "str"), ("instance_class", "str"),
                               ("region", "str"), ("effective_from", "ts"), ("recorded_at", "ts"),
                               ("micro_per_min", "money")], zsort(recs, "rate_id"), "region", "micro_per_min",
                               ["effective_from", "recorded_at", "micro_per_min"], ["attempts.jsonl", "rate_resolution.json"],
                               {"region": "region"})
    # --- target domain ---------------------------------------------------------------
    recs = batch([{"target": t["label"], "language": t["lang"], "toolchain": t["tc"],
                   "manifest_bytes": w.actions[t["action"]]["input_bytes"] + 1024, "_k": t["label"]}
                  for t in w.targets])
    S["package_metadata.xml"] = Spec("package_metadata.xml", "Package", [("target", "str"), ("language", "str"),
                                     ("toolchain", "str"), ("manifest_bytes", "bytes")], recs, "batch",
                                     "manifest_bytes", ["manifest_bytes"], ["targets.jsonl", "actions.jsonl"],
                                     {"target": "target"})
    recs = [{"target": t["label"], "kind": t["kind"], "registered_at": P0 - 86400 * (5 + t["idx"] % 700) - t["idx"] % 86400,
             "_ctx": t["lang"]} for t in w.targets]
    S["targets.csv"] = Spec("targets.csv", "records", [("target", "str"), ("kind", "str"), ("registered_at", "ts")],
                            zsort(recs, "target"), "lang", "registered_at", ["registered_at"], ["targets.jsonl"],
                            {"target": "target"})
    recs = [{"target": t["label"], "constraint": t["cons"], "pinned_at": P0 - 86400 * (1 + t["idx"] % 90),
             "_ctx": t["lang"]} for t in w.targets]
    S["toolchain_pins.yaml"] = Spec("toolchain_pins.yaml", "pins", [("target", "str"), ("constraint", "str"),
                                    ("pinned_at", "ts")], zsort(recs, "target"), "lang", "pinned_at", ["pinned_at"],
                                    ["targets.jsonl", "lookups.jsonl"], {"target": "target"})
    recs = [{"child": e["child"], "parent": e["parent"], "kind": e["kind"],
             "declared_at": P0 - 86400 * (2 + i % 300), "_ctx": lang_of(e["child"])} for i, e in enumerate(w.edges)]
    S["edges.csv"] = Spec("edges.csv", "records", [("child", "str"), ("parent", "str"), ("kind", "str"),
                          ("declared_at", "ts")], zsort(recs, "child"), "lang", "declared_at", ["declared_at"],
                          ["targets.jsonl"], {"child": "target"})
    recs = [{"action": k, "target": v["target"], "digest": w.digests[(w.target_by[v["target"]]["tc"],
             truth["_tver"][v["target"]][0])] if truth["_tver"][v["target"]][0] else "none",
             "recorded": P0 - 3600 * (1 + int(k[:4], 16) % 500), "_ctx": lang_of(v["target"])} for k, v in w.actions.items()]
    S["action_keys.lock"] = Spec("action_keys.lock", "records", [("action", "key"), ("target", "str"),
                                 ("digest", "str"), ("recorded", "ts")], zsort(recs, "action"), "lang", "recorded",
                                 ["action", "recorded"], ["actions.jsonl"], {"target": "target"})
    recs = [{"action": k, "path": v["path"], "declared": "true" if v["declared"] else "false", "size": v["input_bytes"],
             "_ctx": lang_of(v["target"])} for k, v in w.actions.items()]
    S["input_manifests.tsv"] = Spec("input_manifests.tsv", "records", [("action", "key"), ("path", "str"),
                                    ("declared", "str"), ("size", "bytes")], zsort(recs, "action"), "lang", "size",
                                    ["action", "size"], ["actions.jsonl"], {"action": "action"})
    recs = [{"action": k, "reads": v["env"], "observed": P0 + int(k[4:8], 16) % (30 * 86400),
             "_ctx": lang_of(v["target"])} for k, v in w.actions.items()]
    S["env_allowlist.json"] = Spec("env_allowlist.json", "observations", [("action", "key"), ("reads", "list"),
                                   ("observed", "ts")], zsort(recs, "action"), "lang", "observed", ["action", "observed"],
                                   ["actions.jsonl", "lookups.jsonl"], {"action": "action"})
    recs = [{"prefix": k[:6], "shard": v["shard"], "assigned_at": P0 - 86400 * (1 + int(k[6:9], 16) % 200),
             "_ctx": lang_of(v["target"])} for k, v in w.actions.items()]
    S["shard_index.tsv"] = Spec("shard_index.tsv", "records", [("prefix", "key"), ("shard", "int"),
                                ("assigned_at", "ts")], zsort(recs, "prefix"), "lang", "assigned_at",
                                ["prefix", "assigned_at"], ["lookups.jsonl", "actions.jsonl"], {"prefix": "prefix"})
    for shard, fname in ((1, "lookups_shard1.jsonl"), (2, "lookups_shard2.jsonl"), (3, "lookups_shard3.jsonl.gz")):
        recs = [{"lookup": lk["id"], "attempt": lk["attempt"], "action": lk["key"], "result": lk["raw"], "at": lk["at"],
                 "bytes": lk["bytes"], "_ctx": lang_of(w.actions[lk["key"]]["target"])}
                for lk in w.lookups if lk["logged"] == shard]
        S[fname] = Spec(fname, "records", [("lookup", "key"), ("attempt", "key"), ("action", "key"), ("result", "str"),
                        ("at", "ts"), ("bytes", "bytes")], zsort(recs, "lookup"), "lang", "bytes",
                        ["lookup", "attempt", "action", "at", "bytes"], ["lookups.jsonl"], {"action": "action"})
    recs = [{"ts": e["at"], "shard": e["shard"], "action": e["key"], "eviction": e["id"],
             "_ctx": lang_of(w.actions[e["key"]]["target"])} for e in w.evictions]
    S["evictions.log"] = Spec("evictions.log", "records", [("ts", "ts"), ("shard", "int"), ("action", "key"),
                              ("eviction", "key")], zsort(recs, "eviction"), "lang", "ts", ["ts", "action", "eviction"],
                              ["lookups.jsonl"], {"action": "action"})
    recs = [{"artifact": a["id"], "target": a["target"], "bytes": a["bytes"], "created": a["created"],
             "_ctx": lang_of(a["target"])} for a in w.artifacts]
    S["artifact_registry.db"] = Spec("artifact_registry.db", "artifacts", [("artifact", "key"), ("target", "str"),
                                     ("bytes", "bytes"), ("created", "ts")], zsort(recs, "artifact"), "lang", "bytes",
                                     ["artifact", "bytes", "created"], ["artifacts.jsonl"], {"target": "target"})
    ar_t = {a["id"]: a["target"] for a in w.artifacts}
    recs = [{"artifact": g["artifact"], "at": g["at"], "action": g["action"], "_ctx": lang_of(ar_t[g["artifact"]])}
            for g in w.gc]
    S["gc_events.csv"] = Spec("gc_events.csv", "records", [("artifact", "key"), ("at", "ts"), ("action", "str")],
                              zsort(recs, "artifact"), "lang", "at", ["artifact", "at"], ["artifacts.jsonl"],
                              {"artifact": "artifact"})
    recs = [{"target": f["target"], "testcase": f["case"], "from": f["lo"], "until": f["hi"], "_ctx": lang_of(f["target"])}
            for f in w.flaky]
    S["flaky_windows.tsv"] = Spec("flaky_windows.tsv", "records", [("target", "str"), ("testcase", "str"),
                                  ("from", "ts"), ("until", "ts")], zsort(recs, "testcase"), "lang", "from",
                                  ["from", "until"], ["attempts.jsonl"], {"target": "target"})
    recs = [{"id": a["id"], "job": j, "class": a["klass"], "ratified_on": a["ratified"],
             "_ctx": lang_of(w.jobs[j]["target"])} for j, a in w.amend.items()]
    S["amendment_minutes.docx"] = Spec("amendment_minutes.docx", "Amendments", [("id", "str"), ("job", "key"),
                                       ("class", "str"), ("ratified_on", "ts")], zsort(recs, "id"), "lang",
                                       "ratified_on", ["job", "ratified_on"], ["attempts.jsonl"], {"job": "job"})
    recs = [{"job": j, "budget": b, "_ctx": lang_of(w.jobs[j]["target"])} for j, b in w.budgets.items()]
    S["retry_policy.yaml"] = Spec("retry_policy.yaml", "budgets", [("job", "key"), ("budget", "int")],
                                  zsort(recs, "job"), "lang", "budget", ["job"], ["attempts.jsonl"], {"job": "job"})
    recs = batch([{"target": t["label"], "scope": t["scope"], "_k": t["label"]} for t in sorted(w.targets, key=lambda t: t["label"])])
    for r in recs:
        r["reviewed"] = P0 - 86400 * (1 + len(r["target"]) % 60)
    S["scope_rules.md"] = Spec("scope_rules.md", "Target scope register", [("target", "str"), ("scope", "str"),
                               ("reviewed", "ts")], recs, "batch", "reviewed", ["reviewed"], ["targets.jsonl", "attempts.jsonl"],
                               {"target": "target"})
    recs = batch([{"job": j, "target": w.jobs[j]["target"], "submitter": w.jobs[j]["submitter"],
                   "opened": min(a["start"] for a in w.job_atts[j]) - 30, "_k": j} for j in w.register_jobs])
    S["field_precedence.html"] = Spec("field_precedence.html", "Job register", [("job", "key"), ("target", "str"),
                                      ("submitter", "str"), ("opened", "ts")], recs, "batch", "opened",
                                      ["job", "opened"], ["attempts.jsonl"], {"job": "job"})
    # --- handle domain -----------------------------------------------------------------
    recs = [{"seq": p["seq"], "pattern": p["pattern"], "handle": p["handle"], "_ctx": org_of(p["handle"])}
            for p in w.patterns]
    recs.sort(key=lambda r: r["seq"])
    for i, r in enumerate(recs):     # positional bands: org of the band's majority keeps the file ordered by seq
        r["_ctx"] = ORGS[i * len(ORGS) // len(recs)]
    S["owners_registry.txt"] = Spec("owners_registry.txt", "records", [("seq", "int"), ("pattern", "str"),
                                    ("handle", "str")], recs, "org", "seq", ["seq"], ["targets.jsonl", "attempts.jsonl"],
                                    {"handle": "handle"})
    base_handles = [h for h in sorted(w.handles) if not h.startswith("@kestrel-eng/")]
    recs = batch([{"handle": h, "team": w.handles[h]["team"], "effective_from": P0 - 86400 * (10 + i % 300), "_k": h}
                  for i, h in enumerate(base_handles)])
    S["team_roster.xlsx"] = Spec("team_roster.xlsx", "Roster", [("handle", "str"), ("team", "str"),
                                 ("effective_from", "ts")], recs, "batch", "effective_from", ["effective_from"],
                                 ["attempts.jsonl", "targets.jsonl"], {"handle": "handle"})
    recs = []
    for h in base_handles:
        rec = w.handles[h]
        recs.append({"handle": h, "cost_center": rec["cc"], "effective_from": P0 - 86400 * 30, "_ctx": org_of(h)})
        if rec["cc_move"]:
            recs.append({"handle": h, "cost_center": rec["cc_move"][0], "effective_from": rec["cc_move"][1], "_ctx": org_of(h)})
    S["cost_centers.csv"] = Spec("cost_centers.csv", "records", [("handle", "str"), ("cost_center", "key"),
                                 ("effective_from", "ts")], zsort(recs, "handle"), "org", "effective_from",
                                 ["cost_center", "effective_from"], ["attempts.jsonl", "cost_center_ledger.json"],
                                 {"handle": "handle"})
    recs = batch([{"cost_center": cc, "bucket": b, "amount": w.opening[(cc, b)], "_k": cc}
                  for (cc, b) in sorted(w.opening)])
    S["opening_balances.json"] = Spec("opening_balances.json", "balances", [("cost_center", "key"), ("bucket", "str"),
                                      ("amount", "money")], recs, "batch", "amount", ["cost_center", "amount"],
                                      ["cost_center_ledger.json"], {})
    recs = batch([{"posting": p["id"], "cost_center": p["cc"], "amount": p["amount"], "posted_at": p["at"],
                   "reverses": p["reverses"] or "", "_k": p["id"]} for p in w.postings])
    S["settlement_ledger.db"] = Spec("settlement_ledger.db", "postings", [("posting", "key"), ("cost_center", "key"),
                                     ("amount", "money"), ("posted_at", "ts"), ("reverses", "str")], recs, "batch",
                                     "amount", ["posting", "cost_center", "amount", "posted_at"], ["cost_center_ledger.json"], {})
    # --- decoys -----------------------------------------------------------------------
    wa = {r["attempt_id"]: r for r in wrongout["attempts.jsonl"]}
    recs = []
    for a in w.attempts:
        if a["fleet"] != "east":
            continue
        dur = a["dur"]
        if rng.random() < 0.05:
            dur = max(1000, dur + rng.randrange(-90000, 90000))
        recs.append({"attempt_id": a["id"], "job_id": a["job"], "runner": a["runner"], "status": wa[a["id"]]["status"],
                     "started_utc": a["rec_start"], "duration_ms": dur, "cancel_origin": a["origin"] or "none",
                     "schema": "v3", "_ctx": None, "_job": a["job"], "_zone": REGION_ZONE[zone_of(a["runner"])]})
    S["attempt_events_v3.jsonl"] = Spec("attempt_events_v3.jsonl", "records", [("attempt_id", "key"), ("job_id", "key"),
                                        ("runner", "key"), ("status", "str"), ("started_utc", "ts"),
                                        ("duration_ms", "dur"), ("cancel_origin", "str"), ("schema", "str")],
                                        zsort(recs, "attempt_id"), "lang", "duration_ms",
                                        ["attempt_id", "job_id", "runner", "started_utc", "duration_ms"], ["attempts.jsonl"],
                                        {"job": "job"})
    recs = []
    for a in west:
        recs.append({"kind": "USAGE", "ts": a["rec_start"], "attempt": a["id"], "runner": a["runner"],
                     "elapsed": a["dur"], "_ctx": None, "_job": a["job"], "_zone": REGION_ZONE[zone_of(a["runner"])]})
    for a in sorted(w.revoked):
        aa = att[a]
        recs.append({"kind": "REVOKE", "ts": aa["rec_start"] + 86400, "attempt": a, "runner": aa["runner"],
                     "elapsed": 0, "_ctx": None, "_job": aa["job"], "_zone": REGION_ZONE[zone_of(aa["runner"])]})
    S["usage_export_legacy.log"] = Spec("usage_export_legacy.log", "records", [("kind", "str"), ("ts", "ts"),
                                        ("attempt", "key"), ("runner", "key"), ("elapsed", "dur")],
                                        zsort(recs, "attempt"), "lang", "elapsed", ["ts", "attempt", "runner", "elapsed"],
                                        ["attempts.jsonl"], {"attempt_job": "attempt"})
    recs = [{"kind": "write", "id": f"wr-{i + 1:07d}", "action": x["key"], "at": x["at"], "result": "",
             "_ctx": lang_of(w.actions[x["key"]]["target"])} for i, x in enumerate(sorted(w.writes, key=lambda x: (x["key"], x["at"])))]
    for lk in rng.sample(w.lookups, len(w.lookups) // 10):
        res = lk["raw"] if rng.random() > 0.05 else ("MISS" if lk["raw"] == "HIT" else "HIT")
        recs.append({"kind": "lookup", "id": lk["id"], "action": lk["key"], "at": lk["at"], "result": res,
                     "_ctx": lang_of(w.actions[lk["key"]]["target"])})
    S["lookups_archive.jsonl.gz"] = Spec("lookups_archive.jsonl.gz", "records", [("kind", "str"), ("id", "key"),
                                         ("action", "key"), ("at", "ts"), ("result", "str")], zsort(recs, "id"), "lang",
                                         "at", ["id", "action", "at"], ["lookups.jsonl"], {"action": "action"})
    recs = [{"target": t["label"], "resolved_open": wrongout["_tver"][t["label"]][0] or "none",
             "resolved_close": wrongout["_tver"][t["label"]][1] or "none", "resolved_at": P0 - 3600,
             "_ctx": t["lang"]} for t in w.targets]
    S["toolchain_pins_resolved.json"] = Spec("toolchain_pins_resolved.json", "resolved", [("target", "str"),
                                             ("resolved_open", "str"), ("resolved_close", "str"), ("resolved_at", "ts")],
                                             zsort(recs, "target"), "lang", "resolved_at", ["resolved_at"],
                                             ["actions.jsonl"], {"target": "target"})
    S["toolchain_pins_resolved.json"].extra.append(("digests", ["toolchain", "version", "digest"],
                                                    [[tc, v, d] for (tc, v), d in sorted(w.digests.items())]))
    wt = {r["target"]: r for r in wrongout["targets.jsonl"]}
    recs = [{"kind": "map", "target": t["label"], "handle": wt[t["label"]]["owner_handle"] or "", "effective": P0,
             "_ctx": org_of(wt[t["label"]]["owner_handle"]) if wt[t["label"]]["owner_handle"] in w.handles else ORGS[0]}
            for t in w.targets]
    for h, (new, eff) in sorted(w.renames.items()):
        recs.append({"kind": "handle_rename", "target": h, "handle": new, "effective": eff, "_ctx": org_of(h)})
    S["ownership_patterns_approved.tsv"] = Spec("ownership_patterns_approved.tsv", "records", [("kind", "str"),
                                                ("target", "str"), ("handle", "str"), ("effective", "ts")],
                                                zsort(recs, "target"), "org", "effective", ["effective"],
                                                ["targets.jsonl", "attempts.jsonl"], {"handle": "handle"})
    recs = [{"rate_id": r["id"], "instance_class": r["cls"], "region": r["region"], "effective_from": r["eff"],
             "micro_per_min": r["rate"], "status": "FINAL", "_ctx": r["region"]}
            for r in w.rates if not r["corr"]]
    S["rate_card_final.xlsx"] = Spec("rate_card_final.xlsx", "Final rates", [("rate_id", "str"), ("instance_class", "str"),
                                     ("region", "str"), ("effective_from", "ts"), ("micro_per_min", "money"),
                                     ("status", "str")], zsort(recs, "rate_id"), "region", "micro_per_min",
                                     ["effective_from", "micro_per_min", "rate_id"], ["attempts.jsonl"], {"region": "region"})
    S["rate_card_final.xlsx"].extra.append(("Spot credits", ["instance_class", "spot_credit_permille"],
                                            [[c, w.spot_credit[c]] for c in CLASSES]))
    wiv = {r["line_id"]: r for r in wrongout["invoice_reconciliation.jsonl"]}
    recs = [{"line_id": iv["id"], "type": "restated", "restated": wiv[iv["id"]]["computed_micro"] + iv["delta"],
             "_ctx": w.vendors[iv["vendor"]]["locale"]} for iv in w.invoice]
    for iv in w.invoice:
        if iv["closed"]:
            recs.append({"line_id": iv["id"], "type": "dispute_closure", "restated": 0,
                         "_ctx": w.vendors[iv["vendor"]]["locale"]})
    S["invoice_restatement.csv"] = Spec("invoice_restatement.csv", "records", [("line_id", "key"), ("type", "str"),
                                        ("restated", "money")], zsort(recs, "line_id"), "locale", "restated",
                                        ["line_id", "restated"], ["invoice_reconciliation.jsonl"], {})
    return S


# ---------------------------------------------------------------------------------
# codec assignment, structural traps
# ---------------------------------------------------------------------------------
def _pool(spec, lt):
    pool = list(CODECS[lt])
    if spec.ctx != "region" and not all("_zone" in r for r in spec.recs):
        pool = [c for c in pool if c not in ("local", "iso_off")]
    if spec.fmt != "xlsx":
        pool = [c for c in pool if c != "xl1900"]
    if lt == "bytes" and spec.fmt in ("txt",):
        pool = [c for c in pool if c != "kib"]
    return pool


def assign(spec, rng, R):
    """Codec per (column, context value); edge values carry one rule, middle values all."""
    n = len(spec.recs)
    vals = []
    for r in spec.recs:
        if not vals or vals[-1] != r["_ctx"]:
            if r["_ctx"] not in vals:
                vals.append(r["_ctx"])
    first = {}
    last = {}
    for i, r in enumerate(spec.recs):
        first.setdefault(r["_ctx"], i)
        last[r["_ctx"]] = i
    head = [v for v in vals if first[v] < 2000 * n // 10200]
    tail = [v for v in vals if last[v] >= n - 2000 * n // 10200]
    coded = [c for c in spec.coded if _ltype(spec, c) in CODECS]
    for ci, col in enumerate(coded):
        lt = _ltype(spec, col)
        pool = _pool(spec, lt)
        non = [c for c in pool if c != FACE[lt]]
        m = {}
        for vi, v in enumerate(vals):
            if v in head or v in tail:
                edge_idx = (head + tail).index(v)
                m[v] = rng.choice(non) if edge_idx % max(1, len(coded)) == ci % len(coded) else FACE[lt]
            else:
                m[v] = rng.choice(non) if rng.random() < 0.92 else FACE[lt]
        if len(set(m.values())) < 2:
            m[vals[len(vals) // 2]] = rng.choice(non)
        spec.codecs[col] = m
        for v in vals:
            if m[v] != FACE[lt]:
                rid = f"{spec.name}:{col}:{m[v]}@{spec.ctx}={v}"
                R[rid] = {"rule_id": rid, "home_file": spec.name, "family": FAMILY_OF[lt],
                          "families": [FAMILY_OF[lt]] + (["T17"] if spec.ctx != "batch" else ["T8"]),
                          "kind": "trap", "column": col, "codec": m[v], "ctx": [spec.ctx, v]}


def inject(spec, rng, R):
    """Duplicate re-exports, header drift, reviewer flags (bait), free-text framing."""
    n = len(spec.recs)
    lo, hi = int(n * 0.3), int(n * 0.7)
    tags = [[] for _ in range(n)]
    # bait flags in the middle band
    fid = f"{spec.name}:flag:annotation"
    R[fid] = {"rule_id": fid, "home_file": spec.name, "family": "T20", "families": ["T20", "T15"], "kind": "bait",
              "column": "flag"}
    for i in range(n):
        spec.recs[i]["_flag"] = ""
        if lo <= i < hi and rng.random() < 0.18:
            spec.recs[i]["_flag"] = rng.choice(["recheck", "dup?", "void?", "late?"])
            tags[i].append(fid)
    # encoding: Latin-1 notes in the 60-66% band for text formats (before duplication so copies match)
    if spec.fmt in ("csv", "tsv", "log", "jsonl", "txt", "md", "mbox", "ics", "toml", "ini", "yaml"):
        eid = f"{spec.name}:encoding:latin1"
        R[eid] = {"rule_id": eid, "home_file": spec.name, "family": "T10", "families": ["T10", "T9"], "kind": "trap",
                  "column": "note"}
        for i in range(int(n * 0.62), int(n * 0.66)):
            if rng.random() < 0.5:
                spec.recs[i]["_latin"] = True
                tags[i].append(eid)
    # duplicates
    did = f"{spec.name}:dup:reexport"
    R[did] = {"rule_id": did, "home_file": spec.name, "family": "T1", "families": ["T1", "T6"], "kind": "trap",
              "column": "*"}
    out, otags = [], []
    for i, r in enumerate(spec.recs):
        out.append(r)
        otags.append(tags[i])
        if lo <= i < hi and rng.random() < 0.025:
            d = dict(r)
            d["_dup"] = True
            out.append(d)
            otags.append([did])
    spec.recs, spec.tags = out, otags
    # header drift / alias at the 55% mark
    cut = int(len(spec.recs) * 0.55)
    spec.split = cut
    names = [c for c, _ in spec.cols]
    hid = f"{spec.name}:header:drift"
    R[hid] = {"rule_id": hid, "home_file": spec.name, "family": "T8", "families": ["T8", "T14"], "kind": "trap",
              "column": "*"}
    if spec.fmt in ("csv", "tsv", "xlsx", "db", "md", "html", "docx", "pdf", "txt"):
        a, b = (1, 2) if len(names) > 2 else (0, 1)
        order = names[:]
        order[a], order[b] = order[b], order[a]
        spec.order = order
    else:
        col = spec.coded[0] if spec.coded else names[-1]
        spec.alias = (col, col + "_v2", cut)
    for i in range(cut, min(len(spec.recs), cut + max(1, len(spec.recs) // 5))):
        spec.tags[i].append(hid)
    # codec tags + boundary bait
    for i, r in enumerate(spec.recs):
        for col, m in spec.codecs.items():
            lt = _ltype(spec, col)
            c = m[r["_ctx"]]
            if c != FACE[lt]:
                spec.tags[i].append(f"{spec.name}:{col}:{c}@{spec.ctx}={r['_ctx']}")
        for col, lt in spec.cols:
            if lt == "ts" and r.get(col) in (P0, P1, KCUT):
                bid = f"{spec.name}:{col}:boundary"
                R.setdefault(bid, {"rule_id": bid, "home_file": spec.name, "family": "T11", "families": ["T11"],
                                   "kind": "bait", "column": col})
                spec.tags[i].append(bid)
# ---------------------------------------------------------------------------------
# writers
# ---------------------------------------------------------------------------------
ZT = (2025, 11, 3, 0, 0, 0)
LATIN = ["r\u00e9export", "v\u00e9rifi\u00e9", "contr\u00f4le", "b\u00fcro", "se\u00f1al", "a\u00e7\u00e3o"]


def _zip(members):
    buf = _io.BytesIO()
    with _zipfile.ZipFile(buf, "w", _zipfile.ZIP_DEFLATED) as z:
        for name, data in members:
            zi = _zipfile.ZipInfo(name, ZT)
            zi.compress_type = _zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, data)
    return buf.getvalue()


def _x(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def surface(spec, r, i):
    out = {}
    zone = r.get("_zone") or (REGION_ZONE[r["_ctx"]] if spec.ctx == "region" else None)
    for col, lt in spec.cols:
        v = r.get(col)
        if col in spec.codecs:
            c = spec.codecs[col][r["_ctx"]]
            if spec.fmt == "xlsx" and c == "xl1900":
                out[col] = ("num", (v - XL_EPOCH) / 86400)
                continue
            out[col] = enc(lt, c, v, zone)
            if lt == "ts" and c == "local" and zone and _fold(zone, v):
                out[col] += "+fold"
        elif lt == "list":
            out[col] = v
        elif lt in FACE:
            out[col] = enc(lt, FACE[lt], v, zone)
        else:
            out[col] = "" if v is None else str(v)
    return out


def _fold(zone, v):
    local = v + zoff(zone, v) * 60
    for off in {zoff(zone, v - 7200), zoff(zone, v - 3600)}:
        u = local - off * 60
        if u < v and zoff(zone, u) == off:
            return True
    return False


def header(spec, i):
    names = [c for c, _ in spec.cols]
    if spec.order and i >= spec.split:
        names = spec.order
    if spec.alias and i >= spec.alias[2]:
        names = [spec.alias[1] if c == spec.alias[0] else c for c in names]
    return names


def rowvals(spec, r, i):
    s = surface(spec, r, i)
    names = [c for c, _ in spec.cols]
    if spec.order and i >= spec.split:
        names = spec.order
    vals = [s[c] for c in names]
    return header(spec, i), vals


def _rk(r):
    return sum(ord(ch) for ch in str(r.get("_k", "")) + str(sorted((k, str(v)) for k, v in r.items() if not k.startswith("_"))))


def note(r, i):
    if r.get("_latin"):
        return LATIN[_rk(r) % len(LATIN)]
    return ""


def w_delim(spec, sep):
    lines = []
    cur = None
    for i, r in enumerate(spec.recs):
        h, vals = rowvals(spec, r, i)
        h = h + ["flag", "note"]
        if h != cur:
            lines.append(_csvline(h, sep).encode())
            cur = h
        nt = note(r, i)
        if sep == "," and spec.recs[i]["_flag"] == "recheck" and _rk(r) % 3 == 0:
            nt = 'see "ticket", line two\nwrapped'
        line = _csvline([str(v) for v in vals] + [r["_flag"], nt], sep)
        lines.append(line.encode("latin-1") if r.get("_latin") else line.encode())
    return b"\n".join(lines) + b"\n"


def _csvline(vals, sep):
    out = []
    for v in vals:
        v = str(v)
        if sep == "," and any(ch in v for ch in ',"\n') or (sep == "," and v != v.strip()):
            v = '"' + v.replace('"', '""') + '"'
        out.append(v)
    return sep.join(out)


def _jsonrec(spec, r, i):
    h, vals = rowvals(spec, r, i)
    d = dict(zip(h, vals))
    d["flag"] = r["_flag"]
    if r.get("_latin"):
        d["note"] = note(r, i)
    return d


def w_jsonl(spec):
    lines = []
    for i, r in enumerate(spec.recs):
        s = _json.dumps(_jsonrec(spec, r, i), ensure_ascii=False, separators=(",", ":"))
        lines.append(s.encode("latin-1") if r.get("_latin") else s.encode())
    return b"\n".join(lines) + b"\n"


def w_json(spec):
    parts = ['{', f'  "export": "{spec.name}",', f'  "{spec.table}": [']
    recs = [_json.dumps(_jsonrec(spec, r, i), ensure_ascii=True, separators=(", ", ": ")) for i, r in enumerate(spec.recs)]
    parts.append(",\n".join("    " + x for x in recs))
    parts.append("  ]" + ("," if spec.extra else ""))
    for k, (name, cols, rows) in enumerate(spec.extra):
        parts.append(f'  "{name}": [')
        parts.append(",\n".join("    " + _json.dumps(dict(zip(cols, row))) for row in rows))
        parts.append("  ]" + ("," if k < len(spec.extra) - 1 else ""))
    parts.append("}")
    return ("\n".join(parts) + "\n").encode()


def w_xml(spec):
    out = ['<?xml version="1.0" encoding="UTF-8"?>', f'<export file="{spec.name}">']
    for i, r in enumerate(spec.recs):
        d = _jsonrec(spec, r, i)
        out.append(f"  <{spec.table} " + " ".join(f'{k}="{_x(v)}"' for k, v in d.items()) + "/>")
    out.append("</export>")
    return ("\n".join(out) + "\n").encode()


def _kv(d):
    out = []
    for k, v in d.items():
        v = str(v)
        if v == "" or any(ch in v for ch in ' "='):
            v = '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
        out.append(f"{k}={v}")
    return " ".join(out)


def w_log(spec):
    lines = []
    comp = spec.name.split(".")[0]
    for i, r in enumerate(spec.recs):
        d = _jsonrec(spec, r, i)
        lvl = "WARN" if r["_flag"] else "INFO"
        s = f"{lvl} {comp} " + _kv(d)
        lines.append(s.encode("latin-1") if r.get("_latin") else s.encode())
    return b"\n".join(lines) + b"\n"


def w_lock(spec):
    lines = ["# action cache lockfile, one resolved action per line"]
    body = [l.encode() for l in lines]
    for i, r in enumerate(spec.recs):
        body.append(_kv(_jsonrec(spec, r, i)).encode())
    return b"\n".join(body) + b"\n"


def _yv(v):
    if isinstance(v, list):
        return "[" + ", ".join(_json.dumps(x) for x in v) + "]"
    return _json.dumps(str(v), ensure_ascii=False)


def w_yaml(spec):
    lines = [f"# {spec.name}", f"{spec.table}:"]
    body = [l.encode() for l in lines]
    for i, r in enumerate(spec.recs):
        d = _jsonrec(spec, r, i)
        s = "  - {" + ", ".join(f"{k}: {_yv(v)}" for k, v in d.items()) + "}"
        body.append(s.encode("latin-1") if r.get("_latin") else s.encode())
    for name, cols, rows in spec.extra:
        body.append(f"{name}:".encode())
        for row in rows:
            body.append(("  - {" + ", ".join(f"{k}: {_yv(v)}" for k, v in zip(cols, row)) + "}").encode())
    return b"\n".join(body) + b"\n"


def w_toml(spec):
    body = []
    for name, cols, rows in spec.extra:
        if name == "params":
            for k, v in rows:
                body.append(f"{k} = {_json.dumps(v)}".encode())
    body.append(b"")
    body.append(f"{spec.table} = [".encode())
    for i, r in enumerate(spec.recs):
        d = _jsonrec(spec, r, i)
        s = "  { " + ", ".join(f"{k} = {_json.dumps(str(v), ensure_ascii=False)}" for k, v in d.items()) + " },"
        body.append(s.encode("latin-1") if r.get("_latin") else s.encode())
    body.append(b"]")
    return b"\n".join(body) + b"\n"


def w_ini(spec):
    body = [b"; runner configuration revisions"]
    for i, r in enumerate(spec.recs):
        d = _jsonrec(spec, r, i)
        body.append(f"[revision {i + 1}]".encode())
        for k, v in d.items():
            s = f"{k} = {v}"
            body.append(s.encode("latin-1") if r.get("_latin") else s.encode())
    return b"\n".join(body) + b"\n"


def w_txt(spec, layouts):
    body = []
    cur = None
    for i, r in enumerate(spec.recs):
        h, vals = rowvals(spec, r, i)
        h = h + ["flag", "note"]
        vals = [str(v) for v in vals] + [r["_flag"], note(r, i)]
        lid = "L1" if i < spec.split else "L2"
        if lid != cur:
            body.append(f"H{lid}".encode())
            cur = lid
        widths = layouts[(spec.name, lid)]
        s = "D" + "".join(v.ljust(wd)[:wd] for v, (_, wd) in zip(vals, widths))
        body.append(s.encode("latin-1") if r.get("_latin") else s.encode())
    return b"\n".join(body) + b"\n"


def txt_layouts(spec):
    out = {}
    for lid, rng_ in (("L1", range(0, spec.split)), ("L2", range(spec.split, len(spec.recs)))):
        h = None
        widths = None
        for i in rng_:
            hh, vals = rowvals(spec, spec.recs[i], i)
            hh = hh + ["flag", "note"]
            vals = [str(v) for v in vals] + [spec.recs[i]["_flag"], note(spec.recs[i], i)]
            if widths is None:
                h, widths = hh, [len(x) for x in hh]
            widths = [max(a, len(b) + 1) for a, b in zip(widths, vals)]
        out[(spec.name, lid)] = list(zip(h, widths))
    return out


def w_mbox(spec):
    body = []
    for i, r in enumerate(spec.recs):
        d = _jsonrec(spec, r, i)
        sent = r["decided_at"] + r["lag"]
        dt = _dt.fromtimestamp(sent, _tz.utc)
        body.append(f"From approvals@kestrel.dev {dt.strftime('%a %b %d %H:%M:%S %Y')}".encode())
        body.append(f"Message-ID: <{r['mid']}>".encode())
        body.append(f"Date: {dt.strftime('%a, %d %b %Y %H:%M:%S +0000')}".encode())
        body.append(f"Subject: Re: {r['erratum']} status correction".encode())
        body.append(b"")
        for k, v in d.items():
            if k == "mid":
                continue
            s = f"{k.replace('_', '-').title()}: {v}"
            body.append(s.encode("latin-1") if r.get("_latin") else s.encode())
        body.append(b"")
    return b"\n".join(body) + b"\n"


def w_ics(spec):
    body = [b"BEGIN:VCALENDAR", b"VERSION:2.0", b"PRODID:-//kestrel//drain windows//EN"]
    for i, r in enumerate(spec.recs):
        d = _jsonrec(spec, r, i)
        body.append(b"BEGIN:VEVENT")
        for k, v in d.items():
            key = {"uid": "UID", "sequence": "SEQUENCE", "status": "STATUS", "runner": "X-RUNNER",
                   "flag": "X-REVIEW-FLAG", "note": "COMMENT"}.get(k, "X-" + k.upper().replace("_", "-"))
            s = f"{key}:{v}"
            body.append(s.encode("latin-1") if r.get("_latin") else s.encode())
        body.append(b"END:VEVENT")
    body.append(b"END:VCALENDAR")
    return b"\n".join(body) + b"\n"


def _col(n):
    s = ""
    n += 1
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def _sheet(rows):
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for ri, row in enumerate(rows):
        cells = []
        for ci, v in enumerate(row):
            ref = f"{_col(ci)}{ri + 1}"
            if isinstance(v, tuple):
                cells.append(f'<c r="{ref}"><v>{v[1]!r}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t xml:space="preserve">{_x(v)}</t></is></c>')
        out.append(f'<row r="{ri + 1}">' + "".join(cells) + "</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out).encode()


def _parts(spec):
    """Main table split into two parts at the drift point, header reordered in part two."""
    a, b = [], []
    for i, r in enumerate(spec.recs):
        h, vals = rowvals(spec, r, i)
        (a if i < spec.split else b).append((h + ["flag"], [v if isinstance(v, tuple) else str(v) for v in vals] + [r["_flag"]]))
    return a, b


def w_xlsx(spec):
    a, b = _parts(spec)
    sheets = [(spec.table, [a[0][0]] + [v for _, v in a]), (spec.table + " (cont)", [b[0][0]] + [v for _, v in b])]
    for name, cols, rows in spec.extra:
        sheets.append((name, [cols] + [[str(x) for x in r] for r in rows]))
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
          '<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>']
    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    members = []
    for k, (name, rows) in enumerate(sheets):
        ct.append(f'<Override PartName="/xl/worksheets/sheet{k + 1}.xml" '
                  'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        wb.append(f'<sheet name="{_x(name)}" sheetId="{k + 1}" r:id="rId{k + 1}"/>')
        rels.append(f'<Relationship Id="rId{k + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
                    f'relationships/worksheet" Target="worksheets/sheet{k + 1}.xml"/>')
        members.append((f"xl/worksheets/sheet{k + 1}.xml", _sheet(rows)))
    ct.append("</Types>")
    wb.append("</sheets></workbook>")
    rels.append("</Relationships>")
    root = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/'
            'package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/'
            '2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    return _zip([("[Content_Types].xml", "".join(ct).encode()), ("_rels/.rels", root.encode()),
                 ("xl/workbook.xml", "".join(wb).encode()), ("xl/_rels/workbook.xml.rels", "".join(rels).encode())] + members)


def w_db(spec):
    a, b = _parts(spec)
    fd, path = _tempfile.mkstemp(suffix=".db")
    _os.close(fd)
    _os.unlink(path)
    con = _sqlite3.connect(path)
    con.execute("PRAGMA page_size=4096")
    con.execute("PRAGMA journal_mode=OFF")
    for tname, part in ((spec.table, a), (spec.table + "_cont", b)):
        cols = part[0][0]
        con.execute(f'CREATE TABLE "{tname}" (' + ", ".join(f'"{c}" TEXT' for c in cols) + ")")
        con.executemany(f'INSERT INTO "{tname}" VALUES (' + ",".join("?" * len(cols)) + ")", [v for _, v in part])
    for name, cols, rows in spec.extra:
        con.execute(f'CREATE TABLE "{name}" (' + ", ".join(f'"{c}" TEXT' for c in cols) + ")")
        con.executemany(f'INSERT INTO "{name}" VALUES (' + ",".join("?" * len(cols)) + ")", [[str(x) for x in r] for r in rows])
    con.commit()
    con.close()
    data = open(path, "rb").read()
    _os.unlink(path)
    return data


def _doc_tables(spec):
    a, b = _parts(spec)
    tabs = [(spec.table, a[0][0], [v for _, v in a]), (spec.table + " (continued)", b[0][0], [v for _, v in b])]
    for name, cols, rows in spec.extra:
        tabs.append((name, cols, [[str(x) for x in r] for r in rows]))
    return tabs


def w_md(spec):
    out = [f"# {spec.title}", ""]
    for p in spec.prose:
        out += [p, ""]
    for name, cols, rows in _doc_tables(spec):
        out += [f"**Table: {name}**", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        out += ["| " + " | ".join(str(v).replace("|", "\\|") for v in r) + " |" for r in rows]
        out.append("")
    return ("\n".join(out)).encode()


def w_html(spec):
    out = ["<!DOCTYPE html>", "<html><head><meta charset=\"utf-8\"><title>" + _x(spec.title) + "</title></head><body>",
           f"<h1>{_x(spec.title)}</h1>"]
    out += [f"<p>{_x(p)}</p>" for p in spec.prose]
    for name, cols, rows in _doc_tables(spec):
        out.append(f"<table><caption>{_x(name)}</caption>")
        out.append("<tr>" + "".join(f"<th>{_x(c)}</th>" for c in cols) + "</tr>")
        out += ["<tr>" + "".join(f"<td>{_x(v)}</td>" for v in r) + "</tr>" for r in rows]
        out.append("</table>")
    out.append("</body></html>")
    return ("\n".join(out) + "\n").encode()


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def w_docx(spec):
    def para(t):
        return f'<w:p><w:r><w:t xml:space="preserve">{_x(t)}</w:t></w:r></w:p>'
    body = [para(spec.title)] + [para(p) for p in spec.prose]
    for name, cols, rows in _doc_tables(spec):
        body.append(para(f"Table: {name}"))
        trs = []
        for r in [cols] + rows:
            trs.append("<w:tr>" + "".join(f'<w:tc><w:p><w:r><w:t xml:space="preserve">{_x(v)}</w:t></w:r></w:p></w:tc>'
                                         for v in r) + "</w:tr>")
        body.append("<w:tbl>" + "".join(trs) + "</w:tbl>")
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W_NS}"><w:body>'
           + "".join(body) + "</w:body></w:document>")
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/'
          'package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.'
          'relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/'
          'document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
          '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.'
            'org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
            'officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    return _zip([("[Content_Types].xml", ct.encode()), ("_rels/.rels", rels.encode()), ("word/document.xml", doc.encode())])


def _pesc(s):
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def w_pdf(spec):
    lines = [spec.title, ""]
    for p in spec.prose:
        while len(p) > 150:
            cut = p.rfind(" ", 0, 150)
            lines.append(p[:cut])
            p = p[cut + 1:]
        lines += [p, ""]
    for name, cols, rows in _doc_tables(spec):
        lines.append(f"Table: {name}")
        lines.append(" | ".join(cols))
        lines += [" | ".join(str(v) for v in r) for r in rows]
        lines.append("")
    pages = [lines[i:i + 70] for i in range(0, len(lines), 70)]
    objs = []
    kids = []
    font_id = 3
    for pi, pg in enumerate(pages):
        ops = ["BT /F1 6 Tf 8 TL 24 820 Td"]
        for ln in pg:
            ops.append(f"({_pesc(ln.encode('latin-1', 'replace').decode('latin-1'))}) Tj T*")
        ops.append("ET")
        stream = _zlib.compress("\n".join(ops).encode("latin-1"), 9)
        objs.append(stream)
    # object layout: 1 catalog, 2 pages, 3 font, then (page, content) pairs
    out = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets = []
    body = []
    def add(data):
        body.append(data)
    n_pages = len(pages)
    page_ids = [4 + 2 * i for i in range(n_pages)]
    items = [b"<< /Type /Catalog /Pages 2 0 R >>",
             ("<< /Type /Pages /Kids [" + " ".join(f"{p} 0 R" for p in page_ids) + f"] /Count {n_pages} >>").encode(),
             b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    for i in range(n_pages):
        items.append((f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 1190 842] /Resources << /Font << /F1 3 0 R >> >> "
                      f"/Contents {page_ids[i] + 1} 0 R >>").encode())
        items.append(b"<< /Length " + str(len(objs[i])).encode() + b" /Filter /FlateDecode >>\nstream\n" + objs[i] + b"\nendstream")
    pos = len(out[0])
    chunks = [out[0]]
    for k, it in enumerate(items):
        offsets.append(pos)
        chunk = f"{k + 1} 0 obj\n".encode() + it + b"\nendobj\n"
        chunks.append(chunk)
        pos += len(chunk)
    xref = [f"xref\n0 {len(items) + 1}\n0000000000 65535 f \n".encode()]
    xref += [f"{o:010d} 00000 n \n".encode() for o in offsets]
    trailer = f"trailer\n<< /Size {len(items) + 1} /Root 1 0 R >>\nstartxref\n{pos}\n%%EOF\n".encode()
    return b"".join(chunks) + b"".join(xref) + trailer


def write_spec(spec, layouts):
    f = spec.fmt
    if f == "csv":
        return w_delim(spec, ",")
    if f == "tsv":
        return w_delim(spec, "\t")
    if f == "jsonl":
        return w_jsonl(spec)
    if f == "jsonl.gz":
        return _gzip.compress(w_jsonl(spec), 9, mtime=0)
    if f == "json":
        return w_json(spec)
    if f == "xml":
        return w_xml(spec)
    if f == "log":
        return w_log(spec)
    if f == "lock":
        return w_lock(spec)
    if f == "yaml":
        return w_yaml(spec)
    if f == "toml":
        return w_toml(spec)
    if f == "ini":
        return w_ini(spec)
    if f == "txt":
        return w_txt(spec, layouts)
    if f == "mbox":
        return w_mbox(spec)
    if f == "ics":
        return w_ics(spec)
    if f == "xlsx":
        return w_xlsx(spec)
    if f == "db":
        return w_db(spec)
    if f == "md":
        return w_md(spec)
    if f == "html":
        return w_html(spec)
    if f == "docx":
        return w_docx(spec)
    if f == "pdf":
        return w_pdf(spec)
    raise ValueError(f)
# ---------------------------------------------------------------------------------
# semantic trap rules (supersession, voids, deferred effects, precedence, decoys)
# ---------------------------------------------------------------------------------
def semantic_rules(w, S, R, truth, wrongout):
    att = w.att_by
    ta = {r["attempt_id"]: r for r in truth["attempts.jsonl"]}
    wa = {r["attempt_id"]: r for r in wrongout["attempts.jsonl"]}
    approved = set()
    latest = {}
    for m in sorted(w.mails, key=lambda m: (m["at"], m["mid"])):
        if m["at"] <= KCUT:
            latest[m["erratum"]] = m["decision"]
    for e in w.errata:
        if latest.get(e["id"]) == "APPROVED":
            approved.add(e["attempt"])
    n_dec = {}
    for m in w.mails:
        n_dec[m["erratum"]] = n_dec.get(m["erratum"], 0) + 1
    regs = {j["job"]: j["target"] for j in w.jobs.values()}
    moved_rev = {(v["runner"], v["rev"]) for v in w.revs if v["region"] != w.runner_by[v["runner"]]["base_region"]}
    renamed = set(w.renames)
    merged = set(w.cc_merges)
    tl = {r["target"]: r for r in truth["targets.jsonl"]}
    wl = {r["target"]: r for r in wrongout["targets.jsonl"]}
    lk = {r["lookup_id"]: r for r in truth["lookups.jsonl"]}
    tiv = {r["line_id"]: r for r in truth["invoice_reconciliation.jsonl"]}
    wiv = {r["line_id"]: r for r in wrongout["invoice_reconciliation.jsonl"]}
    def A(r):
        return ta.get(r.get("attempt") or r.get("attempt_id") or "", {})
    def W(r):
        return wa.get(r.get("attempt") or r.get("attempt_id") or "", {})
    att_files = ["fleet_north.log", "fleet_south.log", "attempt_events.jsonl", "usage_events.jsonl"]
    rules = []
    for f in att_files:
        aid = "attempt_id" if f == "attempt_events.jsonl" else "attempt"
        rules += [
            (f, "erratum_override", "T7", ["T7", "T22"], "errata_register.docx", lambda r, aid=aid: r[aid] in approved),
            (f, "register_target", "T21", ["T21", "T13"], "field_precedence.html", lambda r, aid=aid: r["target"] != regs[att[r[aid]]["job"]]),
            (f, "clock_skew", "T3", ["T3", "T17"], "clock_sync.txt", lambda r, aid=aid: att[r[aid]]["rec_start"] != att[r[aid]]["start"]),
            (f, "period_edge", "T11", ["T11"], "settlement_authority.md", lambda r, aid=aid: ta[r[aid]]["exclusion"] == "out_of_period"),
            (f, "drain_window", "T6", ["T6", "T11"], "change_freeze.ics", lambda r, aid=aid: ta[r[aid]]["exclusion"] == "provider_drain"),
            (f, "long_valid_run", "T15", ["T15"], "rate_methodology.pdf", lambda r, aid=aid: att[r[aid]]["dur"] > 6 * 3600 * 1000),
            (f, "placement_moved", "T13", ["T13", "T21"], "settlement_authority.md", lambda r, aid=aid: (ta[r[aid]]["runner"], ta[r[aid]]["runner_rev"]) in moved_rev),
            (f, "budget_cut", "T22", ["T22"], "retry_policy.yaml", lambda r, aid=aid: ta[r[aid]]["exclusion"] == "over_budget"),
            (f, "half_even", "T12", ["T12"], "rate_methodology.pdf", lambda r, aid=aid: ta[r[aid]]["cost_micro"] != wa[r[aid]]["cost_micro"] and ta[r[aid]]["exclusion"] is None),
            (f, "spot_reserved", "T2", ["T2", "T21"], "rate_card_final.xlsx", lambda r, aid=aid: ta[r[aid]]["reserved"]),
        ]
    rules += [
        ("usage_events.jsonl", "revoked", "T6", ["T6", "T16"], "usage_export_legacy.log", lambda r: r["attempt"] in w.revoked),
        ("attempt_events.jsonl", "platform_cancel", "T21", ["T21", "T16"], "attempt_events_v3.jsonl", lambda r: att[r["attempt_id"]]["origin"] == "platform"),
        ("fleet_policy.ini", "stale_region", "T21", ["T21", "T13"], "settlement_authority.md", lambda r: (r["runner"], r["rev"]) in moved_rev),
        ("fleet_policy.ini", "superseded_revision", "T7", ["T7"], "settlement_authority.md", lambda r: r["rev"] < 5),
        ("settlement_authority.md", "placement_override", "T21", ["T21"], "field_precedence.html", lambda r: (r["runner"], r["rev"]) in moved_rev),
        ("clock_sync.txt", "negative_skew", "T3", ["T3", "T4"], "settlement_authority.md", lambda r: r["skew_ms"] < 0),
        ("change_freeze.ics", "lower_sequence", "T7", ["T7"], "settlement_authority.md", lambda r: r["sequence"] < max(d["seq"] for d in [w.drain_by[r["uid"]]])),
        ("change_freeze.ics", "cancelled_event", "T6", ["T6"], "settlement_authority.md", lambda r: r["status"] == "CANCELLED"),
        ("change_freeze.ics", "half_open_end", "T11", ["T11", "T20"], "settlement_authority.md", lambda r: any(a["runner"] == r["runner"] and a["rec_start"] == r["dtend"] for a in w.runner_atts.get(r["runner"], []))),
        ("errata_register.docx", "pending_erratum", "T22", ["T22"], "approval_thread.mbox", lambda r: latest.get(r["id"]) != "APPROVED"),
        ("approval_thread.mbox", "superseded_decision", "T7", ["T7", "T22"], "errata_register.docx", lambda r: n_dec[r["erratum"]] > 1),
        ("approval_thread.mbox", "after_cutoff", "T11", ["T11", "T22"], "settlement_authority.md", lambda r: r["decided_at"] > KCUT),
        ("approval_thread.mbox", "transport_date", "T21", ["T21", "T3"], "errata_register.docx", lambda r: r["lag"] > 0),
        ("junit_results.xml", "unquarantined_case", "T20", ["T20"], "flaky_windows.tsv", lambda r: ta[r["attempt"]]["exclusion"] != "quarantined_flake"),
        ("flaky_windows.tsv", "starts_after_attempt", "T11", ["T11"], "settlement_authority.md", lambda r: True if r["testcase"].startswith("Test") and r["from"] % 7 == 0 else False),
        ("flaky_windows.tsv", "idle_window", "T15", ["T15", "T20"], "junit_results.xml", lambda r: r["testcase"].startswith("TestIdle")),
        ("rate_card.xlsx", "correction_row", "T7", ["T7"], "rate_methodology.pdf", lambda r: any(x["corr"] for x in w.rate_by_id.get(r["rate_id"], []))),
        ("rate_card.xlsx", "future_effective", "T11", ["T11"], "rate_methodology.pdf", lambda r: r["effective_from"] > P0),
        ("rate_card_final.xlsx", "post_cutoff_rate", "T16", ["T16", "T22"], "rate_methodology.pdf", lambda r: any(x["late"] for x in w.rate_by_id.get(r["rate_id"], []))),
        ("rate_card_final.xlsx", "final_label", "T16", ["T16", "T7"], "field_precedence.html", lambda r: True),
        ("invoice_lines.xlsx", "vendor_delta", "T19", ["T19", "T4"], "vendor_statement.xml", lambda r: tiv[r["line_id"]]["status"] != "match"),
        ("vendor_statement.xml", "credit_memo", "T21", ["T21"], "field_precedence.html", lambda r: r["credit"] > 0),
        ("invoice_restatement.csv", "restated_amount", "T16", ["T16", "T19"], "field_precedence.html", lambda r: r["type"] == "restated" and wiv[r["line_id"]]["computed_micro"] != tiv[r["line_id"]]["computed_micro"]),
        ("invoice_restatement.csv", "dispute_closure", "T21", ["T21", "T22"], "field_precedence.html", lambda r: r["type"] == "dispute_closure"),
        ("toolchain_pins.yaml", "caret_zero", "T20", ["T20", "T18"], "scope_rules.md", lambda r: r["constraint"].startswith("^0.")),
        ("toolchain_pins.yaml", "resolution_changes", "T22", ["T22", "T7"], "scope_rules.md", lambda r: tl[r["target"]]["version_at_open"] != tl[r["target"]]["version_at_close"]),
        ("toolchain_pins_resolved.json", "naive_resolution", "T16", ["T16", "T18"], "scope_rules.md", lambda r: r["resolved_open"] != (tl[r["target"]]["version_at_open"] or "none")),
        ("toolchain_pins_resolved.json", "stale_snapshot", "T7", ["T7", "T16"], "scope_rules.md", lambda r: r["resolved_close"] != (tl[r["target"]]["version_at_close"] or "none")),
        ("package_metadata.xml", "secondary_toolchain", "T17", ["T17", "T13"], "scope_rules.md", lambda r: r["toolchain"] in ("protoc", "uv", "wasm-pack", "bun")),
        ("targets.csv", "case_twin", "T20", ["T20", "T1"], "settlement_authority.md", lambda r: r["target"].lower() in w.twin_lower),
        ("scope_rules.md", "exempt_scope", "T14", ["T14", "T6"], "settlement_authority.md", lambda r: r["scope"] == "exempt"),
        ("scope_rules.md", "shared_scope_bait", "T20", ["T20"], "scope_rules.md", lambda r: r["scope"] == "shared"),
        ("edges.csv", "data_edge", "T20", ["T20", "T18"], "scope_rules.md", lambda r: r["kind"] == "data"),
        ("edges.csv", "toolchain_edge", "T17", ["T17", "T22"], "scope_rules.md", lambda r: r["kind"] == "toolchain"),
        ("input_manifests.tsv", "undeclared_input", "T6", ["T6", "T17"], "settlement_authority.md", lambda r: r["declared"] == "false"),
        ("env_allowlist.json", "denied_env", "T17", ["T17", "T6"], "settlement_authority.md", lambda r: bool(set(r["reads"]) - set(ALLOWED_ENV))),
        ("shard_index.tsv", "routing_prefix", "T13", ["T13", "T1"], "settlement_authority.md", lambda r: True),
        ("evictions.log", "foreign_shard", "T20", ["T20", "T13"], "shard_index.tsv", lambda r: r["shard"] != w.actions[r["action"]]["shard"]),
        ("evictions.log", "same_second", "T11", ["T11"], "settlement_authority.md", lambda r: r["eviction"] in w.same_second),
        ("lookups_archive.jsonl.gz", "mirror_lookup", "T16", ["T16", "T6"], "settlement_authority.md", lambda r: r["kind"] == "lookup"),
        ("lookups_archive.jsonl.gz", "write_record", "T21", ["T21", "T22"], "field_precedence.html", lambda r: r["kind"] == "write"),
        ("gc_events.csv", "restore_after_delete", "T7", ["T7"], "scope_rules.md", lambda r: r["action"] == "restore"),
        ("gc_events.csv", "outside_period", "T11", ["T11"], "scope_rules.md", lambda r: not P0 <= r["at"] < P1),
        ("artifact_registry.db", "created_before_period", "T11", ["T11"], "scope_rules.md", lambda r: r["created"] < P0),
        ("amendment_minutes.docx", "unratified", "T22", ["T22", "T7"], "settlement_authority.md", lambda r: r["ratified_on"] > KCUT),
        ("retry_policy.yaml", "budget_below_attempts", "T22", ["T22"], "settlement_authority.md", lambda r: r["budget"] < len(w.job_atts[r["job"]])),
        ("field_precedence.html", "register_overrides_row", "T21", ["T21", "T13"], "settlement_authority.md", lambda r: any(a["row_target"] != r["target"] for a in w.job_atts[r["job"]])),
        ("owners_registry.txt", "negation", "T6", ["T6", "T18"], "settlement_authority.md", lambda r: r["pattern"].startswith("!")),
        ("owners_registry.txt", "renamed_handle", "T13", ["T13", "T22"], "ownership_patterns_approved.tsv", lambda r: r["handle"] in renamed),
        ("owners_registry.txt", "glob_pattern", "T18", ["T18", "T20"], "settlement_authority.md", lambda r: "*" in r["pattern"] and "**" not in r["pattern"].replace("/**", "")),
        ("ownership_patterns_approved.tsv", "first_match_flattening", "T16", ["T16", "T19"], "field_precedence.html", lambda r: r["kind"] == "map" and (wl[r["target"]]["owner_handle"] or "") != (tl[r["target"]]["owner_handle"] or "")),
        ("ownership_patterns_approved.tsv", "handle_rename", "T13", ["T13", "T22"], "settlement_authority.md", lambda r: r["kind"] == "handle_rename"),
        ("team_roster.xlsx", "transferred_handle", "T7", ["T7", "T22"], "settlement_authority.md", lambda r: bool(w.handles[r["handle"]]["moved"])),
        ("cost_centers.csv", "merged_center", "T13", ["T13", "T22"], "field_precedence.html", lambda r: r["cost_center"] in merged),
        ("cost_centers.csv", "moved_center", "T7", ["T7"], "settlement_authority.md", lambda r: r["effective_from"] > P0),
        ("settlement_ledger.db", "reversal", "T6", ["T6", "T7"], "field_precedence.html", lambda r: bool(r["reverses"]) or r["posting"] in w.reversed_ids),
        ("settlement_ledger.db", "late_void", "T6", ["T6", "T22"], "control_totals_draft.html", lambda r: r["posting"] in w.void_ids),
        ("settlement_ledger.db", "outside_period", "T11", ["T11"], "field_precedence.html", lambda r: not P0 <= r["posted_at"] < P1),
        ("settlement_ledger.db", "merged_center", "T13", ["T13"], "field_precedence.html", lambda r: r["cost_center"] in merged),
        ("opening_balances.json", "negative_opening", "T4", ["T4", "T15"], "field_precedence.html", lambda r: r["amount"] < 0),
        ("audit_annex.pdf", "reissued_block", "T14", ["T14", "T15"], "audit_annex.pdf", lambda r: r["status"] == "reissued"),
        ("control_totals_draft.html", "draft_counts_reexports", "T16", ["T16", "T19"], "settlement_authority.md", lambda r: not r.get("_annex") and r["records"] != w.annex_true.get(r["control_id"], (r["records"],))[0]),
        ("control_totals_draft.html", "annex_block_figures", "T21", ["T21"], "settlement_authority.md", lambda r: bool(r.get("_annex"))),
        ("attempt_events_v3.jsonl", "v3_duration_drift", "T16", ["T16", "T3"], "settlement_authority.md", lambda r: r["duration_ms"] != att[r["attempt_id"]]["dur"]),
        ("attempt_events_v3.jsonl", "v3_status_unapproved", "T16", ["T16", "T22"], "errata_register.docx", lambda r: r["status"] != ta[r["attempt_id"]]["status"]),
        ("attempt_events_v3.jsonl", "v3_uncorrected_start", "T16", ["T16", "T3"], "clock_sync.txt", lambda r: att[r["attempt_id"]]["rec_start"] != att[r["attempt_id"]]["start"]),
        ("attempt_events_v3.jsonl", "cancel_origin_field", "T21", ["T21", "T5"], "field_precedence.html", lambda r: r["cancel_origin"] != "none"),
        ("usage_export_legacy.log", "revoke_line", "T6", ["T6", "T21"], "field_precedence.html", lambda r: r["kind"] == "REVOKE"),
        ("usage_export_legacy.log", "legacy_mirror", "T16", ["T16"], "settlement_authority.md", lambda r: r["kind"] == "USAGE"),
        ("lookups_shard1.jsonl", "replay", "T13", ["T13", "T20"], "shard_index.tsv", lambda r: lk[r["lookup"]]["outcome"] == "replay"),
        ("lookups_shard2.jsonl", "replay", "T13", ["T13", "T20"], "shard_index.tsv", lambda r: lk[r["lookup"]]["outcome"] == "replay"),
        ("lookups_shard3.jsonl.gz", "replay", "T13", ["T13", "T20"], "shard_index.tsv", lambda r: lk[r["lookup"]]["outcome"] == "replay"),
    ]
    for shard_file in ("lookups_shard1.jsonl", "lookups_shard2.jsonl", "lookups_shard3.jsonl.gz"):
        rules += [
            (shard_file, "evicted_hit", "T22", ["T22", "T11"], "evictions.log", lambda r: lk[r["lookup"]]["outcome"] == "evicted_hit"),
            (shard_file, "stale_hit", "T7", ["T7", "T22"], "scope_rules.md", lambda r: lk[r["lookup"]]["outcome"] == "stale_hit"),
            (shard_file, "nonhermetic_hit", "T17", ["T17", "T6"], "env_allowlist.json", lambda r: lk[r["lookup"]]["outcome"] == "nonhermetic_hit"),
        ]
    for f, name, fam, fams, doc, pred in rules:
        rid = f"{f}:{name}"
        R[rid] = {"rule_id": rid, "home_file": f, "family": fam, "families": fams, "kind": "trap", "column": "*",
                  "doc": doc, "semantic": True}
        sp = S[f]
        for i, r in enumerate(sp.recs):
            try:
                hit = pred(r)
            except (KeyError, TypeError, ValueError):
                hit = False
            if hit:
                sp.tags[i].append(rid)
    return R
# ---------------------------------------------------------------------------------
# documents, controls, assembly
# ---------------------------------------------------------------------------------
TITLES = {
    "settlement_authority.md": "Kestrel CI build-minute settlement authority, October 2025 close",
    "scope_rules.md": "Chargeback scope, toolchain resolution and invalidation rules",
    "field_precedence.html": "Field precedence and job register",
    "rate_methodology.pdf": "Rate methodology and billing granularity",
    "amendment_minutes.docx": "Billing committee amendment minutes",
    "errata_register.docx": "Attempt errata register",
    "audit_annex.pdf": "Audit annex: block control figures",
    "control_totals_draft.html": "DRAFT control totals (preparer working copy)",
}
LINK_TEXT = {
    "runner": "runner column",
    "sku": "sku -> fleet_policy.ini revision -> runner",
    "attempt": "attempt -> the attempt record -> runner",
    "erratum": "erratum -> errata_register.docx attempt -> runner",
    "attempt_job": "attempt -> the attempt's job -> job register target -> package_metadata.xml language",
    "erratum_job": "erratum -> errata_register.docx attempt -> job -> job register target -> language",
    "vendor": "vendor -> vendor_statement.xml locale",
    "region": "region column",
    "target": "target -> package_metadata.xml language",
    "child": "child target -> package_metadata.xml language",
    "action": "action -> action_keys.lock target -> package_metadata.xml language",
    "prefix": "prefix -> the action whose key starts with it -> target -> language",
    "artifact": "artifact -> artifact_registry.db target -> language",
    "job": "job -> job register target -> package_metadata.xml language",
    "handle": "handle -> team_roster.xlsx Roster team -> org",
}
SENTINELS = [
    ("action_keys.lock", "digest", "none", "no toolchain version resolves for the target at period open"),
    ("attempt_events_v3.jsonl", "cancel_origin", "none", "the attempt was not cancelled"),
    ("settlement_ledger.db", "reverses", "", "the posting is not a reversal"),
    ("toolchain_pins_resolved.json", "resolved_open", "none", "the preparer found no version"),
    ("ownership_patterns_approved.tsv", "handle", "", "the preparer found no owner"),
    ("invoice_restatement.csv", "restated", "0.000000", "dispute closures carry no amount"),
    ("usage_export_legacy.log", "elapsed", "0", "REVOKE lines carry no duration"),
    ("lookups_archive.jsonl.gz", "result", "", "write records carry no lookup result"),
]

PROSE = {
"settlement_authority.md": [
"This document is the settlement authority for the October 2025 build-minute close of the Kestrel monorepo CI fleets. Where any export, mirror, draft or working copy disagrees with a rule written here or in the documents this one names (scope_rules.md, field_precedence.html, rate_methodology.pdf, amendment_minutes.docx, errata_register.docx, audit_annex.pdf), the written rule decides. Some exported values are wrong or superseded by design; the rules below say which.",
"S-1 Period. An attempt belongs to the close when its corrected start instant t satisfies 2025-10-01T00:00:00Z <= t < 2025-11-01T00:00:00Z. Attempts outside it are still listed, with exclusion out_of_period.",
"S-2 Knowledge cutoff. The close knows what was recorded at or before 2025-11-04T00:00:00Z. Rate rows recorded after it, approval decisions taken after it, amendments ratified after it and handle renames effective after it have no effect.",
"S-3 Attempt sources. fleet_north.log, fleet_south.log, attempt_events.jsonl and usage_events.jsonl are the attempt records of fleets north, south, east and west. attempt_events_v3.jsonl and usage_export_legacy.log are mirrors and never supply attempts, starts, durations or statuses; attempt_events_v3.jsonl is the only source of cancel_origin and usage_export_legacy.log is the only source of REVOKE lines.",
"S-4 Corrected start. Runners report wall-clock starts. clock_sync.txt lists windows of reported time [window_from, window_to) during which a runner clock ran ahead by skew_ms (negative means behind). A reported start inside a window of that runner is corrected by subtracting the skew; a reported start outside every window is already correct.",
"S-5 Durations. An attempt duration is the difference of its monotonic counters (mono_end minus mono_start in the fleet logs) or the duration field of the east and west records. Wall-clock end times are informational.",
"S-6 Runner revision. The revision in force at the corrected start is the one with the greatest effective_from not after it. Its sku gives instance class, architecture and spot status through instance_classes.csv. The region of a revision is the one in the Runner placements table of this document, which overrides the region written in fleet_policy.ini.",
"S-7 Re-exports. A data row that repeats an earlier row of the same file field for field is a re-export and is one record.",
"S-8 Reviewer annotations. The flag column, X-REVIEW-FLAG property, Flag body line and flag key are reviewer annotations with no settlement meaning; WARN log levels only mirror them.",
"S-9 Column aliases. Some exports renamed one column part way through; the Column aliases tables give the alias and the column it stands for. Tabular exports instead restate the header in a new column order; read every header.",
"S-10 Conventions. Coded columns are written in a codec that depends on the row's context. Wall times in the local and iso_off codecs are in the clock zone of the runner the row is about. The Field conventions tables list, for every file, coded column and context value, the codec in force. Context dimensions and the Codec glossary define the terms. Columns not listed use the first codec of their kind in the glossary.",
"S-11 Exclusions, applied in this order, first match wins: out_of_period; revoked (a REVOKE line for the attempt); provider_drain (corrected start inside [DTSTART, DTEND) of a drain event on the attempt's runner, using the highest SEQUENCE of each UID and ignoring events whose final status is CANCELLED); platform_cancel (final status cancelled and cancel_origin platform); quarantined_flake (final status failed and every testcase junit_results.xml lists for the attempt has a quarantine window for the attempt's target and that testcase with from <= start <= until); preempt_grace (final status preempted and duration below the fleet grace in retry_policy.yaml); over_budget (attempt number above the job budget in retry_policy.yaml, default from its defaults table); exempt_scope (target scope exempt in scope_rules.md).",
"S-12 Final status. The status on the attempt record, replaced by the new value of an erratum whose latest decision at or before the cutoff is APPROVED (errata_register.docx, approval_thread.mbox).",
"S-13 Attribution. The target of an attempt is the target of its job in the job register of field_precedence.html, which lists every job; the target written on attempt records is informational. The owner handle of a target is the handle of the last line of owners_registry.txt (by seq) whose pattern matches the label; a pattern starting with ! that is the last match leaves the target unowned. In patterns * matches within one path segment and never matches / or :, ** matches anything. An unowned target's attempts go to the job's submitter. A handle renamed by a handle_rename row of ownership_patterns_approved.tsv effective at or before the cutoff is reported under its new name; roster and cost-center rows stay recorded under the earlier name.",
"S-14 Team and cost center. The team of a handle at instant t is its Roster row, replaced by a Transfers row effective at or before t. The cost center is the cost_centers.csv row with the greatest effective_from not after t, then followed through the Cost center merges table of field_precedence.html when the merge is effective at or before t. Attempts use their corrected start; targets and artifacts use 2025-10-31T23:59:59Z.",
"S-15 Cache outcomes. A lookup logged in a shard other than the home shard of its action (shard_index.tsv, prefix = first six characters of the action key) is a replay. Otherwise MISS is a miss; a HIT on a non-hermetic action is nonhermetic_hit; a HIT with an eviction of that action in its home shard at e where last_write < e <= lookup time is evicted_hit, reporting the earliest such eviction; a HIT whose target resolves to a different toolchain version at last_write than at the lookup is stale_hit; anything else is a hit. last_write is the latest write record in lookups_archive.jsonl.gz for the action at or before the lookup. The archive's lookup records are mirrors and never lookups.",
"S-16 Hermetic actions. An action is hermetic when its input manifest row is declared and every environment variable it reads is in the allowed list of env_allowlist.json.",
"S-17 Controls. audit_annex.pdf publishes, for every file and every block of 50 consecutive data rows of its primary table in file order, the number of distinct records and the sum of the canonical value of the file's control column over distinct records. Canonical values: timestamps in epoch seconds, durations in milliseconds, money in micro-dollars, integers and byte counts as integers. control_totals_draft.html carries the figures for the annex's own blocks.",
"S-18 Chargeback. Compute is the cost of billable attempts. Storage is the artifact storage cost. Each lookup with outcome hit earns the cache credit of close_parameters.toml for the team of its attempt. Net is compute plus storage minus cache credit.",
],
"scope_rules.md": [
"Scope. A target's scope in the Target scope register is billable, shared or exempt; only exempt removes its attempts from billing.",
"Toolchain resolution. A target's toolchain comes from package_metadata.xml and its constraint from toolchain_pins.yaml. At instant t the resolved version is the highest version of that toolchain in the Toolchain releases table that satisfies the constraint, was released at or before t and is not yanked at t (yanked_at at or before t). Versions compare component by component as integers.",
"Constraints. =X.Y.Z is exact. ~X.Y.Z allows >= X.Y.Z with the same X.Y. >=A <B is a half-open range. ^X.Y.Z follows the Cargo reading: the left-most non-zero component is locked, so ^1.4.2 allows >=1.4.2 <2.0.0, ^0.14.2 allows >=0.14.2 <0.15.0 and ^0.0.3 allows only 0.0.3.",
"Invalidation. A target is invalidated when its version at 2025-10-01T00:00:00Z differs from its version at 2025-10-31T23:59:59Z, or when any parent it reaches through an edges.csv edge of kind src or toolchain is invalidated. Edges of kind data never propagate invalidation.",
"Fixed-width files. owners_registry.txt and clock_sync.txt start each layout with a line H followed by the layout id; data lines start with D and then hold the columns of the Fixed-width layouts table at the stated widths, padded with spaces.",
"Artifacts. An artifact is retained from created until a gc delete, again from a later restore, and so on; retained_seconds counts only time inside the period. storage_cost_micro = bytes x retained_seconds x storage rate / (1073741824 x 3600), rounded once, half to even.",
],
"field_precedence.html": [
"Where two sources supply the same field, the Precedence table names the winner. The job register below is the authority for the target and submitter of every job it lists.",
"Ledger. Opening balance of a cost center is the sum of its opening_balances.json buckets. Postings of settlement_ledger.db count when posted inside the period, are not on the late void list of control_totals_draft.html, do not reverse another posting and are not reversed by one. A posting to a merged cost center at or after the merge goes to the successor. Charges are the costs of billable attempts plus artifact storage costs of that cost center. Closing is opening plus postings plus charges.",
"Invoices. The computed amount of an invoice line is the cost of billable attempts on its runner whose corrected start falls in [week_start, next week_start), the last week ending at the period end. Status is closed when invoice_restatement.csv has a dispute_closure row for the line, else match when billed equals computed, else credited when billed minus the vendor_statement.xml credit equals computed, else mismatch.",
],
"rate_methodology.pdf": [
"Billable seconds are the duration rounded up to a whole multiple of the SKU granularity in the Billing granularity table; excluded attempts bill zero seconds.",
"Rate. For the instance class and region of the revision, take rate_card.xlsx rows recorded at or before the cutoff; among rows with the same effective_from the later recorded_at wins; the applicable row is the one with the greatest effective_from not after the corrected start. rate_card_final.xlsx is not a rate source; its Spot credits sheet is the only source of spot credits.",
"Cost. cost_micro = billable_seconds x micro_per_min x class multiplier / (60 x 1000), then x (1000 - spot credit) / 1000 for spot SKUs, then x reserved permille / 1000 when the runner has a reservation for the UTC calendar date of the corrected start. The product is kept exact and rounded once, half to even.",
"Clock zones. Wall times written in a zone use its offset at that instant: EU+1 is UTC+2 until 2025-10-26T01:00:00Z and UTC+1 after; US-5 is UTC-4 until 2025-11-02T06:00:00Z and UTC-5 after; US-6 is UTC-5 until 2025-11-02T07:00:00Z and UTC-6 after; AU+10 is UTC+10 until 2025-10-04T16:00:00Z and UTC+11 after; IN+5:30 is UTC+5:30; BR-3 is UTC-3. A wall time that occurs twice is the earlier instant unless it carries the suffix +fold, which marks the later instant.",
],
"amendment_minutes.docx": [
"The committee reclassifies jobs. A job takes the class of its amendment when the amendment was ratified at or before the cutoff; otherwise, and for jobs without an amendment, the class is standard.",
],
"errata_register.docx": [
"Each erratum proposes a new status for one attempt. It takes effect only when the latest decision about it in approval_thread.mbox, ordered by the Decided-At line and taken at or before the cutoff, is APPROVED. The Date header is the transport time and is not the decision time.",
],
"audit_annex.pdf": [
"Block control figures. Rows marked reissued were computed before the export was reissued; their figures are published for the record and are not expected to agree with the reissued file.",
],
"control_totals_draft.html": [
"Working copy prepared before re-exports were removed. Figures are provisional. The annex block figures and the late void list are final.",
],
}


def _host(name):
    order = sorted(SPEC_ORDER)
    i = order.index(name)
    for k in range(len(HOSTS)):
        h = HOSTS[(i + k) % len(HOSTS)]
        if h != name:
            return h


SPEC_ORDER = []


def controls_for(spec):
    rows = []
    recs = spec.recs
    for b in range(0, len(recs), BLOCK):
        blk = recs[b:b + BLOCK]
        distinct = [r for r in blk if not r.get("_dup")]
        lt = _ltype(spec, spec.control)
        rows.append((b // BLOCK + 1, len(distinct), sum(canon_num(lt, r.get(spec.control)) for r in distinct), len(blk),
                     sum(canon_num(lt, r.get(spec.control)) for r in blk)))
    return rows


def assemble(seed, n=10200):
    w = build_world(seed, n)
    truth = compute(w)
    wrongout = compute(w, WRONG)
    w._wrongout = wrongout
    S = build_specs(w, truth, wrongout)
    R = {}
    rng = _random.Random(seed * 31 + 7)
    # owners registry and the decoy flattening use positional batches
    for nm in ("owners_registry.txt", "ownership_patterns_approved.tsv"):
        sp = S[nm]
        sp.ctx = "batch"
        for i, r in enumerate(sp.recs):
            r["_ctx"] = f"B{1 + i * NBATCH // len(sp.recs)}"
    for sp in S.values():
        if sp.ctx == "batch":
            sp.cols.append(("batch", "str"))
            for r in sp.recs:
                r["batch"] = r["_ctx"]
    names = sorted(S) + ["audit_annex.pdf", "control_totals_draft.html"]
    SPEC_ORDER[:] = names
    for nm in sorted(S):
        assign(S[nm], _random.Random(f"{seed}:{nm}"), R)
        inject(S[nm], _random.Random(f"{seed}:{nm}:inj"), R)
    # extras
    S["close_parameters.toml"].extra.append(("params", ["key", "value"], [
        ["period_start", iso(P0)], ["period_end", iso(P1)], ["knowledge_cutoff", iso(KCUT)],
        ["storage_micro_per_gib_hour", STORAGE_MICRO_PER_GIB_HOUR], ["cache_credit_micro", CACHE_CREDIT_MICRO],
        ["reserved_permille", RESERVED_PERMILLE]]))
    S["env_allowlist.json"].extra.append(("allowed", ["variable"], [[v] for v in ALLOWED_ENV]))
    S["retry_policy.yaml"].extra.append(("preemption_grace", ["fleet", "grace_s"], [[f, GRACE_S[f]] for f in sorted(GRACE_S)]))
    S["retry_policy.yaml"].extra.append(("defaults", ["key", "value"], [["budget", DEFAULT_BUDGET]]))
    S["team_roster.xlsx"].extra.append(("Transfers", ["handle", "team", "effective_from"],
                                        [[h, w.handles[h]["moved"][0], iso(w.handles[h]["moved"][1])]
                                         for h in sorted(w.handles) if w.handles[h]["moved"] and not h.startswith("@kestrel-eng/")]))
    S["rate_methodology.pdf"].extra.append(("Billing classes", ["class", "multiplier_permille"],
                                            [[k, v] for k, v in sorted(CLASS_MULT.items())]))
    S["field_precedence.html"].extra.append(("Precedence", ["field", "winner", "yields to it"], [
        ["attempt target", "field_precedence.html job register", "attempt records"],
        ["attempt status", "approved errata", "attempt records; attempt_events_v3.jsonl never"],
        ["cancel_origin", "attempt_events_v3.jsonl", "none"],
        ["revoked attempts", "usage_export_legacy.log REVOKE lines", "none"],
        ["revision region", "settlement_authority.md Runner placements", "fleet_policy.ini region"],
        ["rate", "rate_card.xlsx", "rate_card_final.xlsx"],
        ["spot credit", "rate_card_final.xlsx Spot credits", "none"],
        ["owner handle", "owners_registry.txt", "ownership_patterns_approved.tsv map rows"],
        ["handle rename", "ownership_patterns_approved.tsv handle_rename rows", "none"],
        ["toolchain version", "resolution from toolchain_pins.yaml and Toolchain releases", "toolchain_pins_resolved.json resolved columns"],
        ["toolchain version of a digest", "toolchain_pins_resolved.json digests", "none"],
        ["cache write times", "lookups_archive.jsonl.gz write records", "none"],
        ["billed amount", "invoice_lines.xlsx", "invoice_restatement.csv restated rows"],
        ["dispute closure", "invoice_restatement.csv dispute_closure rows", "none"],
        ["posting voids", "control_totals_draft.html Late voids", "none"],
        ["control figures", "audit_annex.pdf", "control_totals_draft.html except the annex blocks"]]))
    S["field_precedence.html"].extra.append(("Cost center merges", ["cost_center", "successor", "effective_at"],
                                             [[k, v[0], iso(v[1])] for k, v in sorted(w.cc_merges.items())]))
    S["scope_rules.md"].extra.append(("Toolchain releases", ["toolchain", "version", "released_at", "yanked_at"],
                                      [[tc, r["version"], iso(r["released"]), iso(r["yanked"]) if r["yanked"] else "never"]
                                       for tc in sorted(w.releases) for r in w.releases[tc]]))
    S["settlement_authority.md"].extra.append(("Region zones", ["region", "zone"], [[r, REGION_ZONE[r]] for r in REGIONS]))
    S["settlement_authority.md"].extra.append(("Codec glossary", ["codec", "kind", "meaning"], [list(x) for x in CODEC_DOC]))
    S["settlement_authority.md"].extra.append(("Context dimensions", ["context", "meaning"], [
        ["region", "region of revision 1 of the row's runner in Runner placements; wall times of such rows are in that region's clock zone (Region zones)"],
        ["lang", "language in package_metadata.xml of the row's target; for rows about an attempt, erratum or job, the job register target of the job"],
        ["org", "text before the first hyphen of the team of the row's handle in the team_roster.xlsx Roster sheet"],
        ["locale", "locale of the row's vendor account in vendor_statement.xml"],
        ["batch", "the batch column printed on the row"]]))
    S["settlement_authority.md"].extra.append(("Sentinel register", ["file", "column", "token", "meaning"],
                                               [list(x) for x in SENTINELS]))
    # controls (annex) and the draft
    ctrl_rows, draft_rows = [], []
    k = 0
    for nm in sorted(S):
        for blk, nrec, csum, nall, call in controls_for(S[nm]):
            k += 1
            reissued = rng.random() < 0.05
            ctrl_rows.append({"control_id": f"CT-{k:06d}", "file": nm, "block": blk, "records": nrec,
                              "control_sum": csum + (rng.randrange(1, 999) if reissued else 0),
                              "status": "reissued" if reissued else "final", "_true": (nrec, csum)})
            draft_rows.append({"control_id": f"CT-{k:06d}", "file": nm, "block": blk, "records": nall, "control_sum": call})
            w.__dict__.setdefault("annex_true", {})[f"CT-{k:06d}"] = (nrec, csum)
    for r in ctrl_rows:
        r["_ctx"] = None
    annex = Spec("audit_annex.pdf", "Block controls", [("control_id", "str"), ("file", "str"), ("block", "int"),
                 ("records", "int"), ("control_sum", "int"), ("status", "str")], ctrl_rows, "batch", "records",
                 ["records", "control_sum"], ["control_reconciliation.json"], {})
    for i, r in enumerate(annex.recs):
        r["_ctx"] = f"B{1 + i * NBATCH // len(annex.recs)}"
        r["batch"] = r["_ctx"]
    annex.cols.append(("batch", "str"))
    assign(annex, _random.Random(f"{seed}:annex"), R)
    inject(annex, _random.Random(f"{seed}:annex:inj"), R)
    S["audit_annex.pdf"] = annex
    k2 = 0
    for blk, nrec, csum, nall, call in controls_for(annex):
        k2 += 1
        draft_rows.append({"control_id": f"DT-{k2:06d}", "file": "audit_annex.pdf", "block": blk, "records": nrec,
                           "control_sum": csum, "_annex": True})
    draft = Spec("control_totals_draft.html", "Draft controls", [("control_id", "str"), ("file", "str"), ("block", "int"),
                 ("records", "int"), ("control_sum", "int")], draft_rows, "batch", "records", ["records", "control_sum"],
                 ["control_reconciliation.json"], {})
    for i, r in enumerate(draft.recs):
        r["_ctx"] = f"B{1 + i * NBATCH // len(draft.recs)}"
        r["batch"] = r["_ctx"]
    draft.cols.append(("batch", "str"))
    draft.extra.append(("Late voids", ["posting"], [[p["id"]] for p in w.postings if p["void"]]))
    assign(draft, _random.Random(f"{seed}:draft"), R)
    inject(draft, _random.Random(f"{seed}:draft:inj"), R)
    S["control_totals_draft.html"] = draft
    # conventions, aliases, layouts hosted in documents
    layouts = {}
    for nm in ("owners_registry.txt", "clock_sync.txt"):
        layouts.update(txt_layouts(S[nm]))
    hosted = {h: {"conv": [], "alias": []} for h in HOSTS}
    for nm in names:
        sp = S[nm]
        h = _host(nm)
        for col in sorted(sp.codecs):
            for v in sorted(sp.codecs[col]):
                hosted[h]["conv"].append([nm, col, sp.ctx, v, sp.codecs[col][v]])
        if sp.alias:
            hosted[h]["alias"].append([nm, sp.alias[1], sp.alias[0], str(sp.alias[2] + 1)])
        for rid, meta in R.items():
            if meta["home_file"] == nm and "doc" not in meta:
                meta["doc"] = h
    for h in HOSTS:
        S[h].extra.append(("Field conventions", ["file", "column", "context", "value", "codec"], hosted[h]["conv"]))
        S[h].extra.append(("Column aliases", ["file", "alias", "column", "from_record"], hosted[h]["alias"] or [["none", "", "", ""]]))
    S["scope_rules.md"].extra.append(("Fixed-width layouts", ["file", "layout", "position", "column", "width"],
                                      [[f, lid, str(i + 1), c, str(wd)] for (f, lid), cols in sorted(layouts.items())
                                       for i, (c, wd) in enumerate(cols)]))
    catalog = []
    for nm in names:
        sp = S[nm]
        lk = next(iter(sp.link), None)
        catalog.append([nm, sp.table, sp.ctx, LINK_TEXT.get(lk, "batch column") if sp.ctx != "batch" else "batch column",
                        sp.control])
    S["settlement_authority.md"].extra.append(("Source catalog", ["file", "primary table", "context", "context link",
                                                                  "control column"], catalog))
    for nm, sp in S.items():
        sp.title = TITLES.get(nm, nm)
        sp.prose = PROSE.get(nm, [])
    # sentinel rules
    for f, col, tok, meaning in SENTINELS:
        sp = S[f]
        rid = f"{f}:{col}:sentinel"
        R[rid] = {"rule_id": rid, "home_file": f, "family": "T5", "families": ["T5"], "kind": "trap", "column": col,
                  "doc": "settlement_authority.md"}
        for i, r in enumerate(sp.recs):
            if str(r.get(col, "x")) in (tok, "None") or (col == "restated" and r.get("type") == "dispute_closure"):
                sp.tags[i].append(rid)
    files = {}
    for nm in names:
        files[nm] = write_spec(S[nm], layouts)
    return w, truth, S, R, files


def truth_outputs(w, truth, S):
    out = {k: v for k, v in truth.items() if not k.startswith("_")}
    ctrl = {}
    for r in S["audit_annex.pdf"].recs:
        if r.get("_dup"):
            continue
        nrec, csum = r["_true"]
        ctrl[r["control_id"]] = {"file": r["file"], "block": r["block"], "expected_records": r["records"],
                                 "expected_sum": r["control_sum"], "records": nrec, "sum": csum,
                                 "match": nrec == r["records"] and csum == r["control_sum"]}
    blocks = controls_for(S["audit_annex.pdf"])
    for r in S["control_totals_draft.html"].recs:
        if r.get("_annex") and not r.get("_dup"):
            blk = blocks[r["block"] - 1]
            ctrl[r["control_id"]] = {"file": r["file"], "block": r["block"], "expected_records": r["records"],
                                     "expected_sum": r["control_sum"], "records": blk[1], "sum": blk[2],
                                     "match": blk[1] == r["records"] and blk[2] == r["control_sum"]}
    out["control_reconciliation.json"] = {k: ctrl[k] for k in sorted(ctrl)}
    out["source_audit.json"] = {nm: {"records": sum(1 for r in S[nm].recs if not r.get("_dup"))} for nm in sorted(S)}
    out["close_summary.json"] = close_summary(out, ctrl)
    return out


def _helpers(w):
    w.drain_by = {d["uid"]: d for d in w.drains}
    w.runner_atts = {}
    for a in w.attempts:
        w.runner_atts.setdefault(a["runner"], []).append(a)
    w.rate_by_id = {r["id"]: [r] for r in w.rates}
    low = {}
    for t in w.targets:
        low.setdefault(t["label"].lower(), []).append(t["label"])
    w.twin_lower = {k for k, v in low.items() if len(v) > 1}
    lkby = {lk["id"]: lk for lk in w.lookups}
    w.same_second = {e["id"] for e in w.evictions if e["lk"] and lkby[e["lk"]]["at"] == e["at"]}
    w.reversed_ids = {p["reverses"] for p in w.postings if p["reverses"]}
    w.void_ids = {p["id"] for p in w.postings if p["void"]}


def generate_corpus(seed, n=10200):
    w, truth, S, R, files = assemble(seed, n)
    _helpers(w)
    semantic_rules(w, S, R, truth, w._wrongout)
    return files, truth_outputs(w, truth, S), (w, S, R)
# ===== CORPUS GENERATOR END =====


# ---------------------------------------------------------------------------------
# grading plumbing
# ---------------------------------------------------------------------------------
_CACHE: dict = {}
_LOCK = threading.RLock()   # rewardkit evaluates criteria concurrently; corpora are built once


def _norm(obj):
    return json.loads(json.dumps(obj))


def _truth(seed):
    with _LOCK:
        return _truth_locked(seed)


def _truth_locked(seed):
    key = ("truth", seed)
    if key not in _CACHE:
        files, out, _meta = generate_corpus(seed, CORPUS_SIZE)
        _CACHE[key] = (files, _norm(out))
    return _CACHE[key]


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
    if os.name != "posix" and _root_only_tests_present():
        raise RuntimeError("verifier isolation requires POSIX uid/gid dropping")
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    if os.name == "posix" and os.geteuid() == 0:
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


def _read_outputs(out: Path):
    got = {}
    for name in OUTPUTS:
        path = out / name
        text = path.read_text(encoding="utf-8")
        got[name] = [json.loads(line) for line in text.splitlines() if line] if name.endswith(".jsonl") else json.loads(text)
    return got


def _snapshot(root: Path):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def _run_program(data_dir: Path, out_dir: Path):
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    out_dir.parent.chmod(0o777)
    proc = subprocess.run(_untrusted_command([sys.executable, str(PROGRAM), str(data_dir), str(out_dir)]),
                          capture_output=True, text=True, timeout=RUN_TIMEOUT, start_new_session=True)
    return proc.returncode


def _canary_dir() -> Path:
    """A decoy corpus at the default input location: a program that ignores its arguments reads it."""
    return APP_ROOT / "data"


def _eval_runs():
    with _LOCK:
        return _eval_runs_locked()


def _eval_runs_locked():
    if "eval" in _CACHE:
        return _CACHE["eval"]
    files, _ = _truth(EVAL_SEED)
    canary = _canary_dir()
    if not canary.exists():
        cfiles, _ = _truth(CHALLENGE_SEED)
        _write_dir(cfiles, canary)
    base = Path(tempfile.mkdtemp(prefix="settle-eval-"))
    base.chmod(0o777)
    data_a, data_b = base / "in-a" / "corpus", base / "in-b" / "renamed-location"
    _write_dir(files, data_a)
    _write_dir(files, data_b)
    before = _snapshot(base)
    res = {"rc": [], "out": [], "base": base, "inputs_before": _snapshot(data_a)}
    for data, out in ((data_a, base / "o1" / "out"), (data_a, base / "o2" / "out"), (data_b, base / "o3" / "out")):
        try:
            res["rc"].append(_run_program(data, out))
        except (OSError, subprocess.SubprocessError):
            res["rc"].append(-1)
        res["out"].append(out)
    after = _snapshot(base)
    allowed = tuple(f"o{i}/out/" for i in (1, 2, 3))
    res["outside"] = [p for p in after if p not in before and not p.startswith(allowed)]
    res["inputs_after"] = _snapshot(data_a)
    _CACHE["eval"] = res
    return res


def _eval_outputs():
    with _LOCK:
        return _eval_outputs_locked()


def _eval_outputs_locked():
    res = _eval_runs()
    if res["rc"][0] != 0:
        raise AssertionError("program failed on the hidden corpus")
    if "eval_out" not in _CACHE:
        _CACHE["eval_out"] = _read_outputs(res["out"][0])
    return _CACHE["eval_out"]


def _visible():
    with _LOCK:
        return _visible_locked()


def _visible_locked():
    if "visible" not in _CACHE:
        _CACHE["visible"] = _read_outputs(OUT_DIR)
    return _CACHE["visible"]


def _field(got, exp, name, fields):
    """Exact comparison of the named fields over the full row population of one artifact."""
    key = ROW_KEY[name]
    g = {r[key]: r for r in got[name]}
    e = {r[key]: r for r in exp[name]}
    assert set(g) == set(e), "row set differs"
    for k, row in e.items():
        for f in fields:
            assert f in g[k] and g[k][f] == row[f] and type(g[k][f]) is type(row[f]), "value differs"


def _vis(name, fields):
    _field(_visible(), _truth(SAMPLE_SEED)[1], name, fields)


def _ev(name, fields):
    _field(_eval_outputs(), _truth(EVAL_SEED)[1], name, fields)


def _map_field(got, exp, fields):
    assert set(got) == set(exp), "key set differs"
    for k, row in exp.items():
        for f in fields:
            assert got[k][f] == row[f] and type(got[k][f]) is type(row[f]), "value differs"


def _strict_eq(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(_strict_eq(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_strict_eq(x, y) for x, y in zip(a, b))
    return a == b


def _holds(check) -> bool:
    try:
        check()
    except Exception:
        return False
    return True


# ---------------------------------------------------------------------------------
# visible close
# ---------------------------------------------------------------------------------
def _check_attempts_started_at():
    _vis("attempts.jsonl", ["started_at"])


def _check_attempts_duration_ms():
    _vis("attempts.jsonl", ["duration_ms"])


def _check_attempts_revision():
    _vis("attempts.jsonl", ["runner_rev", "region", "sku", "instance_class"])


def _check_attempts_final_status():
    _vis("attempts.jsonl", ["status"])


def _check_attempts_exclusion():
    _vis("attempts.jsonl", ["exclusion"])


def _check_attempts_billable_seconds():
    _vis("attempts.jsonl", ["billable_seconds"])


def _check_attempts_rate():
    _vis("attempts.jsonl", ["rate_micro_per_min"])


def _check_attempts_billing_class():
    _vis("attempts.jsonl", ["billing_class", "reserved"])


def _check_attempts_cost():
    _vis("attempts.jsonl", ["cost_micro"])


def _check_attempts_team():
    _vis("attempts.jsonl", ["owner_handle", "team"])


def _check_attempts_cost_center():
    _vis("attempts.jsonl", ["cost_center"])


def _check_lookup_outcomes():
    _vis("lookups.jsonl", ["outcome"])


def _check_lookup_evictions():
    _vis("lookups.jsonl", ["eviction_id"])


def _check_target_versions():
    _vis("targets.jsonl", ["version_at_open", "version_at_close"])


def _check_target_invalidation():
    _vis("targets.jsonl", ["invalidated"])


def _check_target_owners():
    _vis("targets.jsonl", ["owner_handle", "team"])


def _check_action_hermeticity():
    _vis("actions.jsonl", ["hermetic", "undeclared_inputs", "disallowed_env"])


def _check_action_toolchain():
    _vis("actions.jsonl", ["toolchain_version"])


def _check_artifact_retention():
    _vis("artifacts.jsonl", ["retained_seconds"])


def _check_artifact_storage_cost():
    _vis("artifacts.jsonl", ["storage_cost_micro"])


def _check_invoice_status():
    _vis("invoice_reconciliation.jsonl", ["status"])


def _check_invoice_computed():
    _vis("invoice_reconciliation.jsonl", ["week", "billed_micro", "credit_micro", "computed_micro"])


def _check_ledger_postings():
    _map_field(_visible()["cost_center_ledger.json"], _truth(SAMPLE_SEED)[1]["cost_center_ledger.json"], ["postings_micro"])


def _check_ledger_closing():
    _map_field(_visible()["cost_center_ledger.json"], _truth(SAMPLE_SEED)[1]["cost_center_ledger.json"], ["closing_micro"])


def _check_rate_resolution():
    assert _strict_eq(_visible()["rate_resolution.json"], _truth(SAMPLE_SEED)[1]["rate_resolution.json"])


def _check_controls():
    _map_field(_visible()["control_reconciliation.json"], _truth(SAMPLE_SEED)[1]["control_reconciliation.json"],
               ["expected_records", "expected_sum", "records", "sum", "match"])


def _check_team_chargeback():
    _map_field(_visible()["team_chargeback.json"], _truth(SAMPLE_SEED)[1]["team_chargeback.json"],
               ["attempts_billed", "compute_micro", "storage_micro", "cache_credit_micro", "net_micro"])


def _check_cache_effectiveness():
    assert _strict_eq(_visible()["cache_effectiveness.json"], _truth(SAMPLE_SEED)[1]["cache_effectiveness.json"])


def _check_close_summary():
    assert _strict_eq(_visible()["close_summary.json"], _truth(SAMPLE_SEED)[1]["close_summary.json"])


def _check_source_audit():
    assert _strict_eq(_visible()["source_audit.json"], _truth(SAMPLE_SEED)[1]["source_audit.json"])


def _check_documented_shape():
    exp = _truth(SAMPLE_SEED)[1]
    got = _visible()
    for name in OUTPUTS:
        if name.endswith(".jsonl"):
            assert got[name] and all(set(r) == set(exp[name][0]) for r in got[name])
            assert [r[ROW_KEY[name]] for r in got[name]] == sorted(r[ROW_KEY[name]] for r in got[name])
        text = (OUT_DIR / name).read_text(encoding="utf-8")
        assert text.endswith("\n") and "\r" not in text


def _check_visible_artifact(name):
    assert _strict_eq(_visible()[name], _truth(SAMPLE_SEED)[1][name])


# ---------------------------------------------------------------------------------
# hidden corpus: the delivered program on a freshly generated close
# ---------------------------------------------------------------------------------
def _check_program_interface():
    res = _eval_runs()
    assert res["rc"][0] == 0 and all((res["out"][0] / n).is_file() for n in OUTPUTS)


def _check_eval_attempt_costs():
    _ev("attempts.jsonl", ["cost_micro"])


def _check_eval_attempt_attribution():
    _ev("attempts.jsonl", ["team", "cost_center"])


def _check_eval_lookup_outcomes():
    _ev("lookups.jsonl", ["outcome", "eviction_id"])


def _check_eval_target_invalidation():
    _ev("targets.jsonl", ["invalidated"])


def _check_eval_actions():
    _ev("actions.jsonl", ["hermetic", "toolchain_version"])


def _check_eval_artifacts():
    _ev("artifacts.jsonl", ["storage_cost_micro"])


def _check_eval_invoices():
    _ev("invoice_reconciliation.jsonl", ["status"])


def _check_eval_ledger():
    _map_field(_eval_outputs()["cost_center_ledger.json"], _truth(EVAL_SEED)[1]["cost_center_ledger.json"], ["closing_micro"])


def _check_eval_rates():
    assert _strict_eq(_eval_outputs()["rate_resolution.json"], _truth(EVAL_SEED)[1]["rate_resolution.json"])


def _check_eval_controls():
    _map_field(_eval_outputs()["control_reconciliation.json"], _truth(EVAL_SEED)[1]["control_reconciliation.json"],
               ["expected_records", "expected_sum", "records", "sum", "match"])


def _check_eval_complete():
    got = _eval_outputs()
    exp = _truth(EVAL_SEED)[1]
    for name in OUTPUTS:
        assert _strict_eq(got[name], exp[name])


def _check_attempt_costs_all_corpora():
    _check_attempts_cost()
    _check_eval_attempt_costs()


def _check_attempt_timing():
    _vis("attempts.jsonl", ["started_at", "duration_ms"])


def _check_attempt_billing_all_corpora():
    fields = ["billable_seconds", "rate_micro_per_min", "billing_class", "reserved", "cost_micro"]
    _vis("attempts.jsonl", fields)
    _ev("attempts.jsonl", fields)


def _check_attempt_owners_all_corpora():
    _vis("attempts.jsonl", ["owner_handle"])
    _ev("attempts.jsonl", ["owner_handle"])


def _check_attempt_teams_all_corpora():
    _vis("attempts.jsonl", ["team"])
    _ev("attempts.jsonl", ["team"])


def _check_attempt_cost_centers_all_corpora():
    _vis("attempts.jsonl", ["cost_center"])
    _ev("attempts.jsonl", ["cost_center"])


def _check_lookups_all_corpora():
    _vis("lookups.jsonl", ["outcome", "eviction_id"])
    _check_eval_lookup_outcomes()


def _check_target_invalidation_all_corpora():
    _check_target_invalidation()
    _check_eval_target_invalidation()


def _check_action_hermeticity_all_corpora():
    _check_action_hermeticity()
    _ev("actions.jsonl", ["hermetic", "undeclared_inputs", "disallowed_env"])


def _check_action_toolchain_all_corpora():
    _check_action_toolchain()
    _ev("actions.jsonl", ["toolchain_version"])


def _check_artifact_storage_all_corpora():
    _check_artifact_storage_cost()
    _check_eval_artifacts()


def _check_artifact_attribution():
    _vis("artifacts.jsonl", ["team", "cost_center"])


def _check_invoices_all_corpora():
    _vis("invoice_reconciliation.jsonl", ["week", "billed_micro", "credit_micro", "computed_micro", "status"])
    _ev("invoice_reconciliation.jsonl", ["week", "billed_micro", "credit_micro", "computed_micro", "status"])


def _check_ledger_fields_all_corpora(fields):
    _map_field(_visible()["cost_center_ledger.json"], _truth(SAMPLE_SEED)[1]["cost_center_ledger.json"], fields)
    _map_field(_eval_outputs()["cost_center_ledger.json"], _truth(EVAL_SEED)[1]["cost_center_ledger.json"], fields)


def _check_ledger_balances_all_corpora():
    _check_ledger_fields_all_corpora(["opening_micro", "closing_micro"])


def _check_ledger_postings_all_corpora():
    _check_ledger_fields_all_corpora(["postings_micro"])


def _check_ledger_charges_all_corpora():
    _check_ledger_fields_all_corpora(["charges_micro"])


def _check_rates_all_corpora():
    _check_rate_resolution()
    _check_eval_rates()


def _check_controls_all_corpora():
    _check_controls()
    _check_eval_controls()


# ---------------------------------------------------------------------------------
# cheats (each returns normally only when the cheat happened)
# ---------------------------------------------------------------------------------
def _check_negative_hardcoded_sample_answers():
    # Holds when the hidden-corpus output carries identifiers that exist only in the shipped sample.
    out = _eval_outputs()
    sample = {r["attempt_id"] for r in _truth(SAMPLE_SEED)[1]["attempts.jsonl"]}
    hidden = {r["attempt_id"] for r in _truth(EVAL_SEED)[1]["attempts.jsonl"]}
    leaked = {r.get("attempt_id") for r in out["attempts.jsonl"]} & (sample - hidden)
    assert len(leaked) >= 10


def _check_negative_filename_dependent_behaviour():
    # Holds when a deterministic program gives different artifacts for the same corpus at another path.
    res = _eval_runs()
    assert res["rc"][0] == 0 and res["rc"][1] == 0 and res["rc"][2] == 0
    first = {n: (res["out"][0] / n).read_bytes() for n in OUTPUTS}
    assert first == {n: (res["out"][1] / n).read_bytes() for n in OUTPUTS}   # same path reproduces
    assert first != {n: (res["out"][2] / n).read_bytes() for n in OUTPUTS}   # relocated path differs


def _check_negative_reads_training_corpus_at_runtime():
    # Holds when hidden-run output contains identifiers of the corpus sitting at the default input location.
    out = _eval_outputs()
    challenge = {r["attempt_id"] for r in _truth(CHALLENGE_SEED)[1]["attempts.jsonl"]}
    hidden = {r["attempt_id"] for r in _truth(EVAL_SEED)[1]["attempts.jsonl"]}
    leaked = {r.get("attempt_id") for r in out["attempts.jsonl"]} & (challenge - hidden)
    assert len(leaked) >= 10


def _check_negative_nondeterministic_output():
    # Holds when two runs on the same corpus produce different bytes.
    res = _eval_runs()
    assert res["rc"][0] == 0 and res["rc"][1] == 0
    assert any((res["out"][0] / n).read_bytes() != (res["out"][1] / n).read_bytes() for n in OUTPUTS)


def _check_negative_writes_outside_output_dir():
    # Holds when a hidden run created files outside the output directory it was given.
    assert _eval_runs()["outside"]


def _check_negative_modifies_input_corpus():
    # Holds when the program changed the input directory it read.
    res = _eval_runs()
    assert res["inputs_before"] != res["inputs_after"]


if __name__ == "__main__":
    print(json.dumps({"outputs": OUTPUTS}, sort_keys=True))


@criterion(description="Every attempt carries its required corrected start and monotonic duration.")
def attempts_timing(workspace: Path) -> bool:
    return _holds(_check_attempt_timing)


@criterion(description="Every attempt carries the runner revision, region, sku and instance class in force at its start.")
def attempts_revision(workspace: Path) -> bool:
    return _holds(_check_attempts_revision)


@criterion(description="Every attempt carries its final status after approved errata.")
def attempts_final_status(workspace: Path) -> bool:
    return _holds(_check_attempts_final_status)


@criterion(description="Every attempt carries its documented exclusion reason or null.")
def attempts_exclusion(workspace: Path) -> bool:
    return _holds(_check_attempts_exclusion)


@criterion(description="Every attempt has its required billable seconds, rate, billing class, reservation and cost on both closes.")
def attempts_billing(workspace: Path) -> bool:
    return _holds(_check_attempt_billing_all_corpora)


@criterion(description="Every attempt has its required owner handle on both closes.")
def attempts_owner_handle(workspace: Path) -> bool:
    return _holds(_check_attempt_owners_all_corpora)


@criterion(description="Every attempt has its required team on both closes.")
def attempts_team(workspace: Path) -> bool:
    return _holds(_check_attempt_teams_all_corpora)


@criterion(description="Every attempt has its required cost center on both closes.")
def attempts_cost_center(workspace: Path) -> bool:
    return _holds(_check_attempt_cost_centers_all_corpora)


@criterion(description="Every cache lookup has its required outcome and qualifying eviction on both closes.")
def lookup_resolution(workspace: Path) -> bool:
    return _holds(_check_lookups_all_corpora)


@criterion(description="Every target carries its resolved toolchain versions at period open and close.")
def target_versions(workspace: Path) -> bool:
    return _holds(_check_target_versions)


@criterion(description="Every target has the required invalidation verdict on both closes.")
def target_invalidation(workspace: Path) -> bool:
    return _holds(_check_target_invalidation_all_corpora)


@criterion(description="Every target carries its required owner and team.")
def target_owners(workspace: Path) -> bool:
    return _holds(_check_target_owners)


@criterion(description="Every action has the required hermeticity evidence on both closes.")
def action_hermeticity(workspace: Path) -> bool:
    return _holds(_check_action_hermeticity_all_corpora)


@criterion(description="Every action has the toolchain version named by its digest on both closes.")
def action_toolchain(workspace: Path) -> bool:
    return _holds(_check_action_toolchain_all_corpora)


@criterion(description="Every artifact carries its retained seconds inside the period.")
def artifact_retention(workspace: Path) -> bool:
    return _holds(_check_artifact_retention)


@criterion(description="Every artifact has its required storage charge on both closes.")
def artifact_storage_cost(workspace: Path) -> bool:
    return _holds(_check_artifact_storage_all_corpora)


@criterion(description="Every artifact carries its required team and cost-center attribution.")
def artifact_attribution(workspace: Path) -> bool:
    return _holds(_check_artifact_attribution)


@criterion(description="Every invoice line has its required amounts and reconciliation status on both closes.")
def invoice_reconciliation(workspace: Path) -> bool:
    return _holds(_check_invoices_all_corpora)


@criterion(description="Every cost center has its required opening and closing balances on both closes.")
def ledger_balances(workspace: Path) -> bool:
    return _holds(_check_ledger_balances_all_corpora)


@criterion(description="Every cost center has its required period postings on both closes.")
def ledger_postings(workspace: Path) -> bool:
    return _holds(_check_ledger_postings_all_corpora)


@criterion(description="Every cost center has its required attributed charges on both closes.")
def ledger_charges(workspace: Path) -> bool:
    return _holds(_check_ledger_charges_all_corpora)


@criterion(description="Every class and region has its required rate windows on both closes.")
def rate_resolution(workspace: Path) -> bool:
    return _holds(_check_rates_all_corpora)


@criterion(description="Every published control has its required figures and verdict on both closes.")
def control_reconciliation(workspace: Path) -> bool:
    return _holds(_check_controls_all_corpora)


@criterion(description="Every team has its required compute, storage, cache credit and net charge.")
def team_chargeback(workspace: Path) -> bool:
    return _holds(_check_team_chargeback)


@criterion(description="Every team has its required cache outcomes and valid-hit permille.")
def cache_effectiveness(workspace: Path) -> bool:
    return _holds(_check_cache_effectiveness)


@criterion(description="The close summary totals match the shipped close.")
def close_summary_totals(workspace: Path) -> bool:
    return _holds(_check_close_summary)


@criterion(description="The source audit has the required distinct-record count for every input file.")
def source_audit(workspace: Path) -> bool:
    return _holds(_check_source_audit)


@criterion(description="The artifacts use the documented keys, row order and line endings.")
def documented_shape(workspace: Path) -> bool:
    return _holds(_check_documented_shape)


@criterion(description="The program runs on a relocated corpus and writes every artifact.")
def program_interface(workspace: Path) -> bool:
    return _holds(_check_program_interface)


@criterion(description="Hidden-corpus output carries identifiers that exist only in the shipped sample.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _holds(_check_negative_hardcoded_sample_answers)


@criterion(description="The same corpus at a different directory path yields different artifacts.")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    return _holds(_check_negative_filename_dependent_behaviour)


@criterion(description="Hidden-corpus output carries identifiers of the corpus at the default input location.")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    return _holds(_check_negative_reads_training_corpus_at_runtime)


@criterion(description="Two runs on the same corpus produce different bytes.")
def negative_nondeterministic_output(workspace: Path) -> bool:
    return _holds(_check_negative_nondeterministic_output)


@criterion(description="A hidden run created files outside the output directory it was given.")
def negative_writes_outside_output_dir(workspace: Path) -> bool:
    return _holds(_check_negative_writes_outside_output_dir)


@criterion(description="The program changed the input directory it read.")
def negative_modifies_input_corpus(workspace: Path) -> bool:
    return _holds(_check_negative_modifies_input_corpus)


criteria.attempts_timing(weight=3)
criteria.attempts_revision(weight=3)
criteria.attempts_final_status(weight=3)
criteria.attempts_exclusion(weight=3)
criteria.attempts_billing(weight=5)
criteria.attempts_owner_handle(weight=5)
criteria.attempts_team(weight=5)
criteria.attempts_cost_center(weight=5)
criteria.lookup_resolution(weight=3)
criteria.target_versions(weight=3)
criteria.target_invalidation(weight=3)
criteria.target_owners(weight=3)
criteria.action_hermeticity(weight=3)
criteria.action_toolchain(weight=3)
criteria.artifact_retention(weight=3)
criteria.artifact_storage_cost(weight=3)
criteria.artifact_attribution(weight=3)
criteria.invoice_reconciliation(weight=3)
criteria.ledger_balances(weight=5)
criteria.ledger_postings(weight=5)
criteria.ledger_charges(weight=5)
criteria.rate_resolution(weight=3)
criteria.control_reconciliation(weight=3)
criteria.team_chargeback(weight=3)
criteria.cache_effectiveness(weight=3)
criteria.close_summary_totals(weight=3)
criteria.source_audit(weight=1)
criteria.documented_shape(weight=1)
criteria.program_interface(weight=1)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_writes_outside_output_dir(weight=-3)
criteria.negative_modifies_input_corpus(weight=-1)
