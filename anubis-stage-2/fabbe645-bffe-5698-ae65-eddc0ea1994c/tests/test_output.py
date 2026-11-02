"""Grading for the KCBA replica retention and tape packing planner.

The submitted planner is run on estates it has never seen.  The estates are
rebuilt here, from fixed seeds, by the reference model of the archive defined
in plain source further down this file, so the expected plan is known for
every scenario.  Each check grades one rule family on the records whose
inputs the planner already got right, so one wrong rule costs one check.
"""

import base64
import csv
import datetime as dt
import hashlib
import io
import json
import os
import shutil
import signal
import sqlite3
import struct
import subprocess
import sys
import tempfile
import threading
import time
import types
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape as _xml_escape

from rewardkit import criteria, criterion

SAMPLE_SEED = 8464834090596949564
FIELD_SEED = 269486165629311385
FIELD_OBJECTS = 1800
EVAL_SEED = 7281053437700648341
EVAL_OBJECTS = 5000
SPEED_SEED = 5170326849021347523
SPEED_OBJECTS = 15000

OUT = Path("/app/out")
SUBMISSION = OUT / "optimize.py"
STAGED_NAME = "optimize.py"
POISON_ROOT = Path("/app") / "data"
RUN_CAP_SEC = 120
SPEED_CAP_SEC = 60
SCRATCH_DIRS = ("/tmp", "/var/tmp", "/dev/shm")
PUBLISHED_JSON = (
    "scenario_visible.json",
    "scenario_peak.json",
    "scenario_steady.json",
    "scenario_burst.json",
    "scenario_latency.json",
    "perf_report.json",
    "bottleneck_analysis.json",
    "recommendations.json",
    "data_quality.json",
)
VAULT_CODES = ("KLH", "MRG", "NSK", "RTN")
SPECIAL_ROLES = frozenset(("amend1", "r3old", "r3new", "rights_up", "rights_down",
                           "rights_pub", "rights_r2", "hold"))

_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]


# ---------------------------------------------------------------------------
# reference model of the archive: estate builder and reference planner
# ---------------------------------------------------------------------------

MASK = (1 << 64) - 1
VAULTS = ("KLH", "MRG", "NSK", "RTN")
VAULT_NAME = {"KLH": "kolhapur", "MRG": "margao", "NSK": "nashik", "RTN": "ratnagiri"}
RENDITIONS = ("master", "mezzanine", "proxy")
EXT = {"master": "mxf", "mezzanine": "mov", "proxy": "mp4"}
MIB = 1 << 20
GIB = 1 << 30


def derive(seed, label):
    raw = hashlib.blake2b(("%d:%s" % (seed, label)).encode(), digest_size=8).digest()
    return int.from_bytes(raw, "big") or 0x9E3779B97F4A7C15


class Rng:
    def __init__(self, seed):
        self.s = (seed & MASK) or 0x2545F4914F6CDD1D

    def u64(self):
        x = self.s
        x ^= (x >> 12)
        x ^= (x << 25) & MASK
        x ^= (x >> 27)
        self.s = x & MASK
        return (x * 0x2545F4914F6CDD1D) & MASK

    def below(self, n):
        return self.u64() % n if n > 0 else 0

    def between(self, lo, hi):
        return lo + self.below(hi - lo + 1)

    def choice(self, seq):
        return seq[self.below(len(seq))]

    def pct(self, p):
        return self.below(10000) < int(p * 100)

    def shuffle(self, items):
        for i in range(len(items) - 1, 0, -1):
            j = self.below(i + 1)
            items[i], items[j] = items[j], items[i]
        return items

    def sample(self, seq, k):
        pool = list(seq)
        self.shuffle(pool)
        return pool[:k]

    def digest(self):
        return b"".join(self.u64().to_bytes(8, "big") for _ in range(4))


def iso(d):
    return d.isoformat()


def add_days(d, n):
    return d + dt.timedelta(days=n)


def half_even_ratio(num, den):
    q, r = divmod(num, den)
    if 2 * r > den or (2 * r == den and q % 2 == 1):
        q += 1
    return q


def footprint(nbytes, header, block):
    return header + -(-nbytes // block) * block


# --------------------------------------------------------------------------
# parameters
# --------------------------------------------------------------------------

SCENARIO_NAMES = ("visible", "peak", "steady", "burst", "latency")
CART_BASE = (("KT-180", 180), ("KT-240", 240), ("KT-300", 300))


def make_params(seed):
    r = Rng(derive(seed, "params"))
    s0 = add_days(dt.date(2024, 3, 1), r.below(61))
    dates = [s0]
    for _ in range(4):
        dates.append(add_days(dates[-1], 70 + r.below(51)))
    names = list(SCENARIO_NAMES)
    r.shuffle(names)
    scen = {names[i]: dates[i] for i in range(5)}
    s = dates

    def inside(lo, hi):  # (lo, hi]
        return add_days(lo, 1 + r.below((hi - lo).days))

    void_i = r.below(3)
    carts = {}
    for name, base in CART_BASE:
        carts[name] = base * 10 ** 9 + (1 + r.below(999)) * 10 ** 6
    vault_cart = {v: r.choice([c for c, _ in CART_BASE]) for v in VAULTS}
    reserves = {}
    for _c, _base in CART_BASE:
        _native = carts[_c]
        _unit = _native // 20000
        _target = (2 if _base <= 180 else 3) * GIB
        _m = round(_target / _unit)
        _k = (_m - 1) // 2
        if _k % 2:
            _k -= 1
        reserves[_c] = _unit * (2 * _k + 1)
    blocks = {v: r.choice((65536, 131072, 262144, 524288)) for v in VAULTS}
    letters = r.sample("ACFMPQXZ", 3)
    prefs = {}
    for cls in ("R1", "R2", "R3", "R4"):
        order = list(VAULTS)
        r.shuffle(order)
        prefs[cls] = order
    enc_codes = r.sample(("k7", "q2", "t9", "w4", "h5", "b8"), 2)
    stale_header = r.choice((2048, 32768, 65536))
    P = {
        "dates": s,
        "scenarios": scen,
        "d1": inside(s[0], s[1]),
        "d2": s[3],
        "d3": inside(s[1], s[2]),
        "d4": inside(s[2], s[3]),
        "dN": inside(s[void_i], s[void_i + 1]),
        "void_node": "N-%02d" % (1 + r.below(6)),
        "watch_node": None,
        "r1_min": r.choice((3, 4)),
        "header": r.choice((4096, 8192, 16384)),
        "stale_header": stale_header,
        "blocks": blocks,
        "carts": carts,
        "vault_cart": vault_cart,
        "reserves": reserves,
        "sidecar": r.choice((1, 2, 3, 4)) * MIB,
        "label_width": r.choice((4, 5)),
        "endian": r.choice(("<", ">")),
        "klh_letters": {"master": letters[0], "mezzanine": letters[1], "proxy": letters[2]},
        "rtn_drift_shard": 2 + r.below(3),
        "rtn_hex_field": r.choice(("len_hex", "size_hex")),
        "mrg_b32_shard": 1 + r.below(4),
        "mrg_enc": {"base64": enc_codes[0], "base32": enc_codes[1]},
        "hold_rule": r.choice(("PLACE", "SEQUENCE")),
        "split_year": r.choice((1994, 1998, 2002, 2006)),
        "prefs": prefs,
        "plan_seq": derive(seed, "plan") & 0xFFFFFF,
    }
    others = [n for n in range(1, 7) if "N-%02d" % n != P["void_node"]]
    P["watch_node"] = "N-%02d" % r.choice(others)
    P["nodes"] = ["N-%02d" % n for n in range(1, 7)]
    return P


def class_min(P, cls):
    return {"R1": P["r1_min"], "R2": 2, "R3": 2, "R4": 1, "R3A": 1, "R3B": 3}[cls]


# --------------------------------------------------------------------------
# collections, holds, rights, crosswalk
# --------------------------------------------------------------------------

WORDS = ("Konkan", "Sahyadri", "Tarang", "Malvani", "Dashavatar", "Lavani", "Abhang",
         "Koli", "Gomantak", "Sindhudurg", "Varkari", "Bhajan", "Natya", "Sangeet",
         "Kirtan", "Powada", "Ovi", "Jatra", "Shimga", "Ganeshotsav", "Monsoon",
         "Harbour", "Fisherfolk", "Coastline", "Newsreel", "Bulletin", "Yuvavani",
         "Krishi", "Gramin", "Akashvani", "Doordarshan", "Chitra", "Rangmanch")

ROLES = (["amend1"] * 4 + ["r2pub"] * 2 + ["r3old"] * 4 + ["r3new"] * 4 + ["rights_up"] * 3
         + ["rights_down"] * 2 + ["rights_pub"] * 2 + ["rights_r2"] * 2 + ["plain"] * 6
         + ["hold"] * 6 + ["misc"] * 7)

PLAIN_SPEC = [("R1", "commercial"), ("R4", "public"), ("R1", "public"), ("R4", "commercial"),
              ("R1", "commercial"), ("R4", "public")]
MISC_SPEC = [("R1", "commercial"), ("R2", "public"), ("R4", "public"), ("R1", "public"),
             ("R4", "commercial"), ("R2", "public"), ("R1", "commercial")]
HOLD_SPEC = [("R1", "commercial"), ("R4", "public"), ("R1", "public"), ("R4", "commercial"),
             ("R2", "public"), ("R4", "public")]


def make_collections(seed, P):
    r = Rng(derive(seed, "collections"))
    nums = r.sample(range(100, 900), 42)
    roles = list(ROLES)
    r.shuffle(roles)
    Y = P["split_year"]
    counters = {}
    colls = []
    for num, role in zip(nums, roles):
        k = counters.get(role, 0)
        counters[role] = k + 1
        year = r.between(1978, 2021)
        if role == "amend1":
            cls, seg = "R2", "commercial"
        elif role == "r2pub":
            cls, seg = "R2", "public"
        elif role == "r3old":
            cls, seg, year = "R3", r.choice(("commercial", "public")), r.between(1976, Y - 1)
        elif role == "r3new":
            cls, seg, year = "R3", r.choice(("commercial", "public")), r.between(Y, 2022)
        elif role == "rights_up":
            cls, seg = "R4", "commercial"
        elif role == "rights_down":
            cls, seg = "R1", "commercial"
        elif role == "rights_pub":
            cls, seg = "R4", "public"
        elif role == "rights_r2":
            cls, seg = "R4", "commercial"
        elif role == "plain":
            cls, seg = PLAIN_SPEC[k]
        elif role == "hold":
            cls, seg = HOLD_SPEC[k]
        else:
            cls, seg = MISC_SPEC[k]
        title = "%s %s %s" % (r.choice(WORDS), r.choice(WORDS), r.choice(("Archive", "Series", "Reels", "Sessions", "Recordings", "Collection")))
        colls.append({"id": "KC-%03d" % num, "title": title, "segment": seg, "cls": cls,
                      "year": year, "role": role, "k": k})
    colls.sort(key=lambda c: c["id"])
    return colls


def by_role(colls, role):
    return sorted([c for c in colls if c["role"] == role], key=lambda c: c["k"])


def make_crosswalk(seed, P, colls):
    r = Rng(derive(seed, "crosswalk"))
    used = {int(c["id"][3:]) for c in colls}
    legacy_nums = [n for n in r.sample(range(10, 99), 12)]
    simple = by_role(colls, "plain")[:5]
    misc = by_role(colls, "misc")
    pairs = [(misc[0], misc[1]), (misc[2], misc[3]), (misc[4], misc[5])]
    rows = []
    legacy_simple = {}
    legacy_pair = {}
    i = 0
    for c in simple:
        lid = "KCB-%03d" % legacy_nums[i]
        i += 1
        legacy_simple[c["id"]] = lid
        rows.append((lid, c["id"], "1990-01-01", "series renumbered at 2023 cutover"))
    for a, b in pairs:
        lid = "KCB-%03d" % legacy_nums[i]
        i += 1
        cut = dt.date(2018 + r.below(6), 1 + r.below(12), 1 + r.below(28))
        legacy_pair[a["id"]] = (lid, "before", cut)
        legacy_pair[b["id"]] = (lid, "from", cut)
        rows.append((lid, a["id"], "1990-01-01", "parent series"))
        rows.append((lid, b["id"], iso(cut), "split series, catalogued on or after this date"))
    rows.sort()
    return {"rows": rows, "simple": legacy_simple, "pair": legacy_pair}


def ist_stamp(d, hh, mm, zone):
    if zone == "Z":
        return "%sT%02d:%02d:00Z" % (iso(d), hh, mm)
    return "%sT%02d:%02d:00+05:30" % (iso(d), hh, mm)


def make_holds(seed, P, colls, epoch):
    r = Rng(derive(seed, "holds"))
    s = P["dates"]
    hc = by_role(colls, "hold")
    ev = []  # (collection, action, stamp)
    ev.append((hc[0]["id"], "PLACE", ist_stamp(add_days(s[0], -30), 11, 15, "+")))
    ev.append((hc[0]["id"], "PLACE", ist_stamp(s[2], 10, 0, "+")))
    ev.append((hc[0]["id"], "RELEASE", ist_stamp(s[2], 16, 45, "+")))
    ev.append((hc[1]["id"], "PLACE", ist_stamp(add_days(s[0], -40), 6, 0, "Z")))
    ev.append((hc[1]["id"], "RELEASE", ist_stamp(s[1], 20, 10, "Z")))
    ev.append((hc[2]["id"], "PLACE", ist_stamp(s[3], 19, 0, "Z")))
    ev.append((hc[3]["id"], "PLACE", ist_stamp(add_days(s[0], -100), 9, 30, "+")))
    ev.append((hc[3]["id"], "RELEASE", ist_stamp(add_days(s[3], -5), 15, 0, "+")))
    ev.append((hc[4]["id"], "PLACE", ist_stamp(s[1], 0, 0, "+")))
    ev.append((hc[4]["id"], "RELEASE", ist_stamp(s[4], 23, 59, "+")))
    ev.append((hc[5]["id"], "PLACE", ist_stamp(add_days(s[1], 3), 3, 0, "Z")))
    ev.append((hc[5]["id"], "RELEASE", ist_stamp(add_days(s[2], -1), 12, 0, "+")))
    if epoch == "B":
        extra = by_role(colls, "misc")[6]
        ev.append((extra["id"], "PLACE", ist_stamp(add_days(s[0], -2), 14, 20, "+")))
        ev.append((hc[3]["id"], "PLACE", ist_stamp(add_days(s[3], -1), 8, 0, "+")))
    # same-day tie ids: the later listed event of hc[0] must carry the higher id
    ids = r.sample(range(1000, 9999), len(ev))
    tie_lo, tie_hi = sorted((ids[1], ids[2]))
    ids[1], ids[2] = tie_lo, tie_hi
    out = []
    for (coll, act, stamp), num in zip(ev, ids):
        out.append({"id": "LH-%04d" % num, "collection": coll, "action": act,
                    "stamp": stamp, "ref": "MAT/%d/%03d" % (2019 + r.below(5), r.below(1000))})
    r.shuffle(out)
    return out


def stamp_ist_date(stamp):
    day, rest = stamp.split("T")
    d = dt.date.fromisoformat(day)
    hh, mm = int(rest[0:2]), int(rest[3:5])
    minutes = hh * 60 + mm
    if rest.endswith("Z"):
        minutes += 330
    return add_days(d, minutes // 1440)


def held_at(P, holds, coll, as_of):
    rank_place = 1 if P["hold_rule"] == "PLACE" else 0
    best = None
    for e in holds:
        if e["collection"] != coll:
            continue
        d = stamp_ist_date(e["stamp"])
        if d > as_of:
            continue
        key = (d, rank_place if e["action"] == "PLACE" else 0, e["id"])
        if best is None or key > best[0]:
            best = (key, e["action"])
    return best is not None and best[1] == "PLACE"


def make_rights(seed, P, colls):
    r = Rng(derive(seed, "rights"))
    s = P["dates"]
    lic = []
    up = by_role(colls, "rights_up")
    down = by_role(colls, "rights_down")
    pub = by_role(colls, "rights_pub")
    windows = [(up[0], "R1", add_days(s[2], -20), add_days(s[4], 40)),
               (up[1], "R1", add_days(s[1], -30), add_days(s[3], -1)),
               (up[2], "R1", s[3], add_days(s[4], 10)),
               (down[0], "R4", add_days(s[0], -50), add_days(s[4], 60)),
               (down[1], "R4", s[2], s[3]),
               (pub[0], "R1", add_days(s[0], -50), add_days(s[4], 60)),
               (pub[1], "R1", add_days(s[1], -10), add_days(s[4], 30))]
    r2 = by_role(colls, "rights_r2")
    inside = [d for d in sorted(s) if max(P["d1"], P["d3"]) <= d < P["d2"]]
    anchor = inside[0]
    for c in r2:
        windows.append((c, "R2", add_days(anchor, -45), add_days(P["d2"], -1)))
    plain = [c for c in by_role(colls, "plain") if c["segment"] == "commercial"]
    for c in plain[:2]:
        windows.append((c, "R2", add_days(s[0], -400), add_days(s[0], -40)))
    licensees = ("Sahyadri Media Pvt Ltd", "Coastal Lines OTT", "Ratnakar Films", "Mandovi Telecast",
                 "Western Ghats Studio", "Laxmi Audio House", "Arabian Sea Networks")
    for c, cls, a, b in windows:
        lic.append({"id": "LIC-%05d" % r.between(10000, 99999), "collection": c["id"],
                    "class": cls, "from": a, "to": b, "licensee": r.choice(licensees)})
    r.shuffle(lic)
    return lic


def effective_class(P, coll, rights, as_of):
    cls = coll["cls"]
    if as_of >= P["d3"] and coll["segment"] == "commercial":
        for l in rights:
            if l["collection"] == coll["id"] and l["from"] <= as_of <= l["to"]:
                cls = l["class"]
    if cls == "R3" and as_of >= P["d4"]:
        cls = "R3A" if coll["year"] < P["split_year"] else "R3B"
    mn = class_min(P, cls)
    if cls == "R2" and coll["segment"] == "commercial" and P["d1"] <= as_of < P["d2"]:
        mn = 3
    return cls, mn


def rendition_need(mn, rendition):
    if rendition == "proxy":
        return 1
    if rendition == "mezzanine":
        return max(1, mn - 1)
    return mn


# --------------------------------------------------------------------------
# objects and replica rows
# --------------------------------------------------------------------------

SERIES = ("news", "folk", "drama", "agri", "youth", "music", "sports", "doc", "kids", "talk",
          "ritual", "coast", "film", "radio", "field")
SLUGS = ("reel", "tape", "take", "session", "bulletin", "episode", "clip", "feature", "segment",
         "recital", "interview", "broadcast")
COMMA_SLUGS = ("Konkan Folk, Vol", "Malvani Natya, Part", "Koli Geet, Side")
VAULT_COUNT = ((1, 15), (2, 35), (3, 35), (4, 15))


def _vault_count(r):
    x = r.below(100)
    acc = 0
    for n, w in VAULT_COUNT:
        acc += w
        if x < acc:
            return n
    return 4


def _size(r, P, kind):
    T = P["sidecar"]
    if kind == "sidecar":
        return r.between(4096, T - 1)
    if kind == "klh_trap":
        return T - r.between(1, 511)
    if kind == "at_threshold":
        return T
    e = r.between(22, 31)
    return (1 << e) + r.below(1 << e)


def make_objects(seed, P, colls, xwalk, n, epoch, counter_base=0, label="objects"):
    r = Rng(derive(seed, label))
    plain_misc = [c for c in colls if c["role"] in ("plain", "misc")]
    objs = []
    clone_pool = []
    counter = counter_base
    for i in range(n):
        x = r.below(10000)
        if x < 500:
            kind = "sidecar"
        elif x < 800:
            kind = "klh_trap"
        elif x < 900:
            kind = "at_threshold"
        else:
            kind = "normal"
        coll = r.choice(colls)
        rend_x = r.below(100)
        rendition = "master" if rend_x < 55 else ("mezzanine" if rend_x < 80 else "proxy")
        size = _size(r, P, kind)
        if kind == "normal" and clone_pool and r.below(100) < 4:
            size = r.choice(clone_pool)
        elif kind == "normal" and r.below(100) < 3:
            clone_pool.append(size)
        k = _vault_count(r)
        vaults = r.sample(VAULTS, k)
        if kind == "klh_trap" and "KLH" not in vaults:
            vaults[0] = "KLH"
        vaults = sorted(set(vaults))
        tag = coll["role"]
        second = None
        if coll["role"] in ("plain", "misc") and len(vaults) >= 2 and r.below(100) < 9:
            cands = [c for c in plain_misc if c["id"] != coll["id"] and c["cls"] != coll["cls"]]
            second = r.choice(cands)
            tag = "multi"
        counter += 1
        series = r.choice(SERIES)
        slug = r.choice(SLUGS)
        year = r.between(1979, 2023)
        obj = {"digest": r.digest().hex(), "bytes": size, "rendition": rendition,
               "coll": coll["id"], "tag": tag, "kind": kind, "rows": []}
        second_vault = None
        if second is not None:
            non_mrg = [v for v in vaults if v != "MRG"] or vaults
            second_vault = r.choice(non_mrg)
        for v in vaults:
            vslug = slug
            if v == "NSK" and r.below(100) < 1:
                vslug = r.choice(COMMA_SLUGS) + " %d" % r.between(1, 9)
            path = "%s/%s/%d/%s_%06d.%s" % (VAULT_NAME[v], series, year, vslug, counter, EXT[rendition])
            rc = second["id"] if v == second_vault else coll["id"]
            objs_row = {"vault": v, "path": path, "collection": rc, "dup": False}
            obj["rows"].append(objs_row)
        # same-vault duplicate row (plain collection objects only, never sidecars)
        if tag == "plain" and kind == "normal" and r.below(100) < 12:
            base = r.choice(obj["rows"])
            dyear = year
            while dyear == year:
                dyear = r.between(1979, 2023)
            dpath = "%s/%s/%d/%s_%06d.%s" % (VAULT_NAME[base["vault"]], series, dyear, slug, counter, EXT[rendition])
            obj["rows"].append({"vault": base["vault"], "path": dpath, "collection": base["collection"], "dup": True})
        objs.append(obj)
    _decorate_rows(r, P, colls, xwalk, objs)
    return objs


def _decorate_rows(r, P, colls, xwalk, objs):
    cmap = {c["id"]: c for c in colls}
    for obj in objs:
        multi_v = len({row["vault"] for row in obj["rows"]}) >= 2
        has_dup = any(row["dup"] for row in obj["rows"])
        for row in obj["rows"]:
            v = row["vault"]
            row["node"] = None
            row["legacy"] = None
            row["catalogued"] = dt.date(2008 + r.below(16), 1 + r.below(12), 1 + r.below(28))
            row["written"] = "%sT%02d:%02d:%02dZ" % (iso(row["catalogued"]), r.below(24), r.below(60), r.below(60))
            if v == "NSK":
                node = r.choice([n for n in P["nodes"] if n != P["void_node"]])
                if multi_v and not has_dup and obj["kind"] == "normal" and r.below(100) < 6:
                    node = P["void_node"]
                row["node"] = node
            if v == "MRG":
                cid = row["collection"]
                if cid in xwalk["simple"] and r.below(100) < 70:
                    row["legacy"] = xwalk["simple"][cid]
                elif cid in xwalk["pair"] and r.below(100) < 70:
                    lid, side, cut = xwalk["pair"][cid]
                    row["legacy"] = lid
                    if side == "before":
                        span = (cut - dt.date(2008, 1, 1)).days
                        row["catalogued"] = add_days(dt.date(2008, 1, 1), r.below(span))
                    else:
                        span = (dt.date(2024, 1, 1) - cut).days
                        row["catalogued"] = add_days(cut, r.below(span))
                    row["written"] = "%sT08:00:00Z" % iso(row["catalogued"])


def mutate_epoch_b(seed, P, colls, xwalk, objs):
    r = Rng(derive(seed, "epochB"))
    keep = list(objs)
    drop_idx = set()
    normals = [i for i, o in enumerate(keep) if o["kind"] == "normal" and o["tag"] == "plain"]
    for i in r.sample(normals, min(8, len(normals))):
        drop_idx.add(i)
    kept = [o for i, o in enumerate(keep) if i not in drop_idx]
    extra_n = max(30, len(objs) * 3 // 100)
    extra = make_objects(seed, P, colls, xwalk, extra_n, "B", counter_base=900000, label="objectsB")
    return kept + extra


# --------------------------------------------------------------------------
# manifest rendering
# --------------------------------------------------------------------------

def _shards(r, rows):
    rows = list(rows)
    r.shuffle(rows)
    n = len(rows)
    cuts = [n * i // 4 for i in range(5)]
    return [rows[cuts[i]:cuts[i + 1]] for i in range(4)]


def _xa(s):
    return _xml_escape(s, {'"': "&quot;"})


def render_manifests(seed, P, objs, epoch):
    r = Rng(derive(seed, "shards" + epoch))
    by_vault = {v: [] for v in VAULTS}
    for o in objs:
        for row in o["rows"]:
            row["obj"] = o
            by_vault[row["vault"]].append(row)
    files = {}
    # Nashik CSV
    for i, part in enumerate(_shards(r, by_vault["NSK"]), 1):
        name = "nashik_manifest_%02d.csv" % i
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["object_path", "bytes", "sha256", "collection", "rendition", "node", "written_utc"])
        for row in part:
            o = row["obj"]
            row["file"] = name
            w.writerow([row["path"], o["bytes"], o["digest"], row["collection"], o["rendition"], row["node"], row["written"]])
        files[name] = buf.getvalue().encode()
    # Margao XML
    for i, part in enumerate(_shards(r, by_vault["MRG"]), 1):
        name = "margao_inventory_%02d.xml" % i
        b32 = (i == P["mrg_b32_shard"])
        code = P["mrg_enc"]["base32" if b32 else "base64"]
        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<inv:inventory xmlns:inv="urn:kcba:margao:inventory:2" vault="margao" batch="%d" records="%d">' % (i, len(part))]
        for row in part:
            o = row["obj"]
            row["file"] = name
            raw = bytes.fromhex(o["digest"])
            enc = base64.b32encode(raw).decode().rstrip("=") if b32 else base64.b64encode(raw).decode()
            coll = row["legacy"] or row["collection"]
            lines.append('  <inv:obj path="%s" size="%d" coll="%s" form="%s" catalogued="%s">'
                         % (_xa(row["path"]), o["bytes"], coll, o["rendition"], iso(row["catalogued"])))
            lines.append('    <inv:digest alg="sha256" enc="%s">%s</inv:digest>' % (code, enc))
            lines.append('  </inv:obj>')
        lines.append('</inv:inventory>')
        files[name] = ("\n".join(lines) + "\n").encode()
    # Ratnagiri JSONL
    for i, part in enumerate(_shards(r, by_vault["RTN"]), 1):
        name = "ratnagiri_objects_%02d.jsonl" % i
        drift = i >= P["rtn_drift_shard"]
        out = []
        for row in part:
            o = row["obj"]
            row["file"] = name
            rec = {"p": row["path"]}
            if drift:
                rec[P["rtn_hex_field"]] = "%x" % o["bytes"]
            else:
                rec["len"] = o["bytes"]
            rec["dg"] = "SHA256:" + o["digest"].upper()
            rec["col"] = row["collection"]
            rec["kind"] = o["rendition"].upper()
            out.append(json.dumps(rec, separators=(",", ":")))
        files[name] = ("\n".join(out) + "\n").encode()
    # Kolhapur DAT + IDX
    e = P["endian"]
    for i, part in enumerate(_shards(r, by_vault["KLH"]), 1):
        dname = "kolhapur_catalogue_%02d.dat" % i
        iname = "kolhapur_index_%02d.idx" % i
        lines = []
        recs = []
        for seq, row in enumerate(part, 1):
            o = row["obj"]
            row["file"] = dname
            sectors = -(-o["bytes"] // 512)
            lines.append("%-72s%07d%11d%-10s%s%s" % (row["path"], seq, sectors, row["collection"],
                                                     P["klh_letters"][o["rendition"]],
                                                     row["catalogued"].strftime("%Y%m%d")))
            recs.append(struct.pack(e + "IQ", seq, o["bytes"]) + bytes.fromhex(o["digest"]))
        r.shuffle(recs)
        files[dname] = ("\n".join(lines) + "\n").encode()
        files[iname] = b"KLHIDX" + struct.pack(e + "HI", 3, len(recs)) + b"".join(recs)
    return files


def record_count(name, data):
    if name.endswith(".csv") and name.startswith("nashik_"):
        return max(0, data.count(b"\n") - 1)
    if name.endswith(".xml") and name.startswith("margao_"):
        return data.count(b"<inv:obj ")
    if name.endswith(".jsonl"):
        return sum(1 for ln in data.split(b"\n") if ln.strip())
    if name.endswith(".dat"):
        return sum(1 for ln in data.split(b"\n") if ln.strip())
    if name.endswith(".idx"):
        return (len(data) - 12) // 44
    if name in ("legal_holds.psv", "collection_crosswalk.tsv"):
        return max(0, sum(1 for ln in data.split(b"\n") if ln.strip()) - 1)
    return None


# --------------------------------------------------------------------------
# structured side files
# --------------------------------------------------------------------------

def render_catalogue_db(colls):
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.unlink(path)
    try:
        con = sqlite3.connect(path)
        con.execute("CREATE TABLE collection (collection_id TEXT PRIMARY KEY, title TEXT NOT NULL, "
                    "segment TEXT NOT NULL, retention_class TEXT NOT NULL, ingest_year INTEGER NOT NULL)")
        con.execute("CREATE TABLE note (collection_id TEXT, remark TEXT)")
        for c in colls:
            con.execute("INSERT INTO collection VALUES (?,?,?,?,?)",
                        (c["id"], c["title"], c["segment"], c["cls"], c["year"]))
        for c in colls[:5]:
            con.execute("INSERT INTO note VALUES (?,?)", (c["id"], "segment confirmed by rights desk"))
        con.commit()
        con.close()
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        if os.path.exists(path):
            os.unlink(path)


def render_holds(holds):
    lines = ["event_id|collection|action|effective|matter_ref"]
    for e in holds:
        lines.append("%s|%s|%s|%s|%s" % (e["id"], e["collection"], e["action"], e["stamp"], e["ref"]))
    return ("\n".join(lines) + "\n").encode()


def render_rights(rights):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<rr:register xmlns:rr="urn:kcba:rights:1" issued_by="KCBA Rights Desk">']
    for l in rights:
        lines.append('  <rr:licence id="%s" collection="%s" class_override="%s" from="%s" to="%s" licensee="%s"/>'
                     % (l["id"], l["collection"], l["class"], iso(l["from"]), iso(l["to"]), _xa(l["licensee"])))
    lines.append("</rr:register>")
    return ("\n".join(lines) + "\n").encode()


def render_crosswalk(xw):
    lines = ["legacy_id\tcollection_id\teffective_from\tnote"]
    for row in xw["rows"]:
        lines.append("\t".join(row))
    return ("\n".join(lines) + "\n").encode()


def render_vault_ini(P):
    out = ["; KCBA vault profiles, maintained by the media operations cell", ""]
    for v in VAULTS:
        out.append("[vault.%s]" % VAULT_NAME[v])
        out.append("code = %s" % v)
        out.append("cartridge = %s" % P["vault_cart"][v])
        out.append("block_size = %d" % P["blocks"][v])
        out.append("")
    return "\n".join(out).encode()


def render_media(P):
    media = []
    for name, base in CART_BASE:
        media.append({"type": name, "native_capacity_bytes": P["carts"][name],
                      "compressed_capacity_bytes": P["carts"][name] * 5 // 2,
                      "generation": "KT gen %d" % (base // 60)})
    return (json.dumps({"vendor": "Kestrel Tape Systems", "media": media}, indent=2) + "\n").encode()


def _xlsx(sheets):
    strings = []
    index = {}

    def sid(s):
        if s not in index:
            index[s] = len(strings)
            strings.append(s)
        return index[s]

    sheet_xml = []
    for title, rows in sheets:
        body = []
        for ri, row in enumerate(rows, 1):
            cells = []
            for ci, val in enumerate(row):
                ref = "%s%d" % ("ABCDEFGH"[ci], ri)
                if isinstance(val, int):
                    cells.append('<c r="%s"><v>%d</v></c>' % (ref, val))
                else:
                    cells.append('<c r="%s" t="s"><v>%d</v></c>' % (ref, sid(val)))
            body.append('<row r="%d">%s</row>' % (ri, "".join(cells)))
        sheet_xml.append('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                         '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                         '<sheetData>%s</sheetData></worksheet>' % "".join(body))
    sst = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
           '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="%d" uniqueCount="%d">%s</sst>'
           % (len(strings), len(strings), "".join("<si><t>%s</t></si>" % _xml_escape(s) for s in strings)))
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>']
    wb_sheets = []
    rels = []
    for i, (title, _) in enumerate(sheets, 1):
        ct.append('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % i)
        wb_sheets.append('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (title, i, i))
        rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i, i))
    n = len(sheets)
    rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>' % (n + 1))
    ct.append("</Types>")
    parts = [
        ("[Content_Types].xml", "".join(ct)),
        ("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
         '</Relationships>'),
        ("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
         '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
         'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>%s</sheets></workbook>' % "".join(wb_sheets)),
        ("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
         '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">%s</Relationships>' % "".join(rels)),
        ("xl/sharedStrings.xml", sst),
    ]
    for i, x in enumerate(sheet_xml, 1):
        parts.append(("xl/worksheets/sheet%d.xml" % i, x))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        for name, text in parts:
            info = zipfile.ZipInfo(name, date_time=(2022, 6, 30, 9, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            z.writestr(info, text.encode())
    return buf.getvalue()


def render_capacity_xlsx(P):
    summary = [["cartridge", "planned_capacity_bytes", "vaults", "comment"]]
    for name, base in CART_BASE:
        vaults = ",".join(VAULT_NAME[v] for v in VAULTS if P["vault_cart"][v] == name) or "none"
        summary.append([name, base * 10 ** 9 - 7 * 10 ** 9, vaults, "2022 tender figure"])
    reserve = [["cartridge", "capacity_bytes_2022", "reserve_bytes", "basis"]]
    for name, base in CART_BASE:
        reserve.append([name, base * 10 ** 9 - 7 * 10 ** 9, P["reserves"][name], "end of tape guard and index area"])
    return _xlsx([("Summary", summary), ("Reserve", reserve)])


def render_schedule_csv(P):
    stale = {"R1": 2, "R2": 1, "R3": 3, "R4": 2}
    lines = ["class,min_replicas,vault_preference,review_due"]
    for cls in ("R1", "R2", "R3", "R4"):
        lines.append("%s,%d,%s,2021-03-31" % (cls, stale[cls], ">".join(P["prefs"][cls])))
    return ("\n".join(lines) + "\n").encode()


def toml_str(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def render_census(plan_id, files):
    out = ["# KCBA estate census. One [[file]] table per input file of this planning cycle.",
           "[census]", "plan_id = %s" % toml_str(plan_id), "file_count = %d" % len(files), ""]
    for name in sorted(files):
        data = files[name]
        out.append("[[file]]")
        out.append("name = %s" % toml_str(name))
        out.append("bytes = %d" % len(data))
        out.append("sha256 = %s" % toml_str(hashlib.sha256(data).hexdigest()))
        rc = record_count(name, data)
        if rc is not None:
            out.append("records = %d" % rc)
        out.append("")
    return "\n".join(out).encode()


# --------------------------------------------------------------------------
# prose documents
# --------------------------------------------------------------------------

def _mib(n):
    return "%d MiB" % (n // MIB)


def _dl(d):
    return d.strftime("%d %B %Y").lstrip("0")


def doc_brief(P, plan_id):
    s = P["dates"]
    return """# KCBA Archive Desk Brief: Replica Retention and Tape Packing

Prepared by the Archive Desk, Konkan Coast Broadcast Archive (KCBA), for planning cycle %(plan)s.

## 1. Why this cycle exists

KCBA keeps digitised masters, mezzanine files and viewing proxies of its radio and television
holdings in four vaults. Over twenty years of ingest projects many files were copied to more
vaults than the retention charter asks for, while some files never reached enough vaults. Each
planning cycle the desk decides, for every scenario date listed in `run_control.json`:

1. which replicas of each stored file must be kept and which may be released,
2. how the kept replicas in each vault are packed onto fresh tape volumes,
3. whether the estate census reconciles, because nothing is published when it does not.

The plan is produced by a small program that the desk re-runs every cycle on that cycle's
export. The exports change shape from cycle to cycle, so the program must read the rules from
the documents in this folder and never from memory of an earlier cycle.

## 2. Where the rules live

| Topic | Document |
|---|---|
| Governing rules, classes, holds, precedence between documents | `retention_charter.md` |
| Dated changes to the charter | `charter_amendment_01.md`, `charter_amendment_02.md`, `charter_amendment_03.md` |
| Tape volume layout and packing order | `volume_layout.md` |
| Output files, field names, sort orders, status literals | `plan_output_contract.md` |
| Margao XML export | `margao_export_readme.md` |
| Kolhapur fixed width catalogue and binary index | `kolhapur_index_format.md` |
| Ratnagiri JSON lines export | `ratnagiri_changelog.md` |
| Collections, segments, classes, ingest years | `catalogue.db` (SQLite, table `collection`) |
| Census of every input file | `estate_census.toml` |
| Plan id and scenario dates | `run_control.json` |

Several older desk papers are also in this folder. They were written before charter version 4
and most of what they say has been replaced. Section 10 of the charter names the one item in
each of them that is still in force. Read that section before trusting any older paper.

## 3. The four vaults

| Code | Vault | Export family | Notes |
|---|---|---|---|
| KLH | Kolhapur | `kolhapur_catalogue_NN.dat` with `kolhapur_index_NN.idx` | fixed width text plus a binary index, joined per shard |
| MRG | Margao | `margao_inventory_NN.xml` | namespaced XML, digests encoded, some legacy collection ids |
| NSK | Nashik | `nashik_manifest_NN.csv` | standard CSV with a header row, RFC 4180 quoting |
| RTN | Ratnagiri | `ratnagiri_objects_NN.jsonl` | one JSON object per line |

Every family is split into four numbered shards. A shard holds an arbitrary slice of its vault;
shard numbers carry no meaning beyond the format notes in the changelogs. Vault codes are
always written in upper case and sort in the order KLH, MRG, NSK, RTN.

## 4. Primer

A **replica** is one row in a vault export. It names a stored file by its path inside the vault
and gives the file's exact size in bytes and its SHA-256 digest. Two rows that carry the same
digest are copies of the same **object**, whether they sit in the same vault or in different
vaults. An object belongs to the collection named on each of its rows; rows of one object can
name different collections, and then the object belongs to all of them.

A **collection** has a segment (`commercial` or `public`), a retention class and an ingest year,
all held in `catalogue.db`. The retention class sets how many vaults must hold the object.
The rendition (master, mezzanine or proxy) lowers that number for derived files.

A **volume** is one tape cartridge. Every kept replica in a vault is written to exactly one
volume of that vault. Volumes are filled in a fixed order so that two runs of the plan give
the same volumes.

## 5. Glossary

- **as_of date**: the scenario date from `run_control.json`. Every rule is evaluated as of
  this date.
- **required replicas**: the number of distinct vaults that must hold an object on the as_of
  date, after the charter, its amendments and the rendition rule are applied.
- **governing collection**: the collection whose class sets the required replicas of an
  object; charter section 6 says how it is chosen when there are several.
- **duplicate**: a second or later row of the same object inside the same vault.
- **sidecar**: a small companion file that is not planned at all; see charter section 9.
- **under replicated**: an object that sits in fewer distinct vaults than it requires.
- **held**: an object whose collection is under legal hold on the as_of date.
- **footprint**: the bytes a replica occupies on tape, defined in `volume_layout.md`.
- **usable capacity**: the bytes of a volume that may carry footprints.
- **fill_bps**: used bytes of a volume as basis points of its usable capacity.
- **census**: the list in `estate_census.toml` of every input file with its byte count,
  SHA-256 and, for record files, its record count.

## 6. How records are counted for the census

| File kind | One record is |
|---|---|
| `nashik_manifest_NN.csv` | one data row after the header row |
| `margao_inventory_NN.xml` | one `inv:obj` element |
| `ratnagiri_objects_NN.jsonl` | one non empty line |
| `kolhapur_catalogue_NN.dat` | one non empty line |
| `kolhapur_index_NN.idx` | one 44 byte index record after the 12 byte header |
| `legal_holds.psv`, `collection_crosswalk.tsv` | one data line after the header line |

A census entry without a `records` key is checked on bytes and SHA-256 only. The census does
not list itself.

## 7. Cycle calendar

The first scenario of this cycle falls on %(s0)s and the last on %(s4)s. Amendment dates are
in the amendments themselves; do not infer them from this calendar.
""" % {"plan": plan_id, "s0": iso(s[0]), "s4": iso(s[4])}


def doc_charter(P):
    s = P["dates"]
    adopted = add_days(s[0], -200)
    return """# KCBA Retention Charter, version 4

Adopted by the KCBA Preservation Board on %(adopted)s. This charter governs which replicas of
archive objects KCBA keeps, in which vaults, and how holds and exports are read for planning.

## 1. Authority and precedence

1. This charter is the governing document for replica planning.
2. A numbered amendment (`charter_amendment_NN.md`) changes this charter from the effective
   date it states, and only within the window and scope it states. Inside that window and
   scope the amendment prevails over this charter.
3. Where any older desk paper disagrees with this charter or an amendment, the charter or
   the amendment wins. Section 10 lists the single item that each older paper still
   decides.
4. The format notes for each vault export (`margao_export_readme.md`,
   `kolhapur_index_format.md`, `ratnagiri_changelog.md`) decide how an export is read. They
   do not change any planning rule.

## 2. Planning date

Every rule is evaluated as of the scenario's as_of date. A dated event counts when its date
is on or before the as_of date. A dated window counts when the as_of date lies between its
start and end dates, both ends included, unless the window says an end date is excluded.

## 3. Retention classes

| Class | Minimum distinct vaults for a master |
|---|---|
| R1 | %(r1)d |
| R2 | 2 |
| R3 | 2 |
| R4 | 1 |

The class of a collection is the `retention_class` column of table `collection` in
`catalogue.db`, as changed by any amendment in force on the as_of date.

## 4. Collections and legacy ids

Every replica row names a collection. Rows from the Margao vault may carry a legacy id that
starts with `KCB-`; such an id is resolved to a current `KC-` id with
`collection_crosswalk.tsv` under the rule kept in force by section 10. All other rows carry
current ids.

## 5. Renditions

The class minimum applies to masters. A mezzanine file needs one vault fewer than the class
minimum, but never fewer than one. A proxy needs exactly one vault whatever its class.

## 6. Objects in several collections

When the rows of one object name more than one collection, each collection gives a minimum
through sections 3, 5 and the amendments. The object needs the largest of these. The
governing collection is the collection that gives this largest minimum; when several give
it, the governing collection is the one with the smallest collection id in plain text
order. The class of the governing collection, after amendments, is the class reported for
the object and decides the vault preference order.

## 7. Choosing the replicas to keep

1. Only distinct vaults count towards the required number. Inside one vault the replica
   whose `object_path` sorts first in plain byte order is the vault's primary replica. Every
   other replica of the object in that vault is a duplicate.
2. When an object is not held, keep the primary replica in the first vaults of the
   preference order of its reported class, taking only vaults that hold the object, until the
   required number is reached. Every other replica of the object, duplicates included, may be
   released.
3. When the object sits in fewer distinct vaults than it requires, keep every primary
   replica, release its duplicates, and report the object as under replicated.
4. The preference order for a class is the `vault_preference` column of
   `retention_schedule_2019.csv` (vault codes separated by `>`, most preferred first). Classes
   R3A and R3B use the order of R3.

## 8. Legal holds

1. `legal_holds.psv` is the hold register. Each line places or releases a hold on one
   collection.
2. A collection is under hold on the as_of date when the last of its events that counts on
   that date is a `PLACE`. Which events count, and which event is last when two fall on the
   same date, is decided by the item of `legal_hold_faq.md` kept in force by section 10.
3. A hold lasts until a `RELEASE`; no hold lapses on its own.
4. Every replica of an object that names a held collection on any of its rows is kept,
   duplicates included. The object is still reported with its required number and its
   under replicated flag.

## 9. Rows that are not planned

1. A sidecar is a file whose exact size in bytes is below the threshold kept in force by
   section 10. Sidecar rows are not planned, are not replicas of any object and are not
   packed. They are counted in the data quality report.
2. A row on a Nashik storage node that was decommissioned on or before the as_of date is not
   a replica on that date. The decommissioned node and its date are the finding kept in
   force by section 10. Such rows are left out of every planning step for that scenario and
   counted per scenario in the data quality report.

## 10. Older papers and the one item each still decides

| Paper | Item still in force | Everything else in the paper |
|---|---|---|
| `ops_handbook_2021.md` | the volume label format | replaced by `volume_layout.md` |
| `migration_memo_2023.md` | how a legacy id that maps to two collections is resolved | replaced |
| `sidecar_policy_note.md` | the sidecar size threshold | replaced |
| `legal_hold_faq.md` | which calendar date an event counts on, and the order of events on one date | replaced; see section 8 |
| `nashik_audit_2024.html` | the decommissioned node and its decommission date | other findings are advisory only |
| `kolhapur_tape_notes.txt` | the rendition letter codes of the Kolhapur catalogue | replaced by `kolhapur_index_format.md` |
| `retention_schedule_2019.csv` | the `vault_preference` column | `min_replicas` replaced by section 3 |
| `capacity_planning_2022.xlsx` | the `reserve_bytes` column of the Reserve sheet | capacities replaced by `media_catalogue.json` |

## 11. Publication

A plan is published only when every file listed in `estate_census.toml` is present and
matches its listed byte count, SHA-256 and record count. Otherwise the plan is held and the
reasons are reported as set out in `plan_output_contract.md`.
""" % {"adopted": iso(adopted), "r1": P["r1_min"]}


def doc_amend1(P):
    return """# Charter Amendment 01: Commercial R2 collections

Approved by the Preservation Board on %(appr)s.

1. Scope: collections of class R2 in the `commercial` segment. Public segment R2
   collections are not changed by this amendment.
2. Window: from %(d1)s up to but excluding %(d2)s.
3. Rule: inside the window the class minimum of an R2 commercial collection is 3 instead of
   2. The rendition rule of charter section 5 is applied to this minimum as usual.
4. The class of a collection is first settled by Amendment 02 where it applies; this
   amendment then looks at the settled class.
5. On and after %(d2)s the charter minimum of 2 applies again.
""" % {"appr": iso(add_days(P["d1"], -21)), "d1": iso(P["d1"]), "d2": iso(P["d2"])}


def doc_amend2(P):
    return """# Charter Amendment 02: Rights register as a source of class

Approved by the Preservation Board on %(appr)s.

1. From %(d3)s the rights register `rights_register.xml` is authoritative for the
   retention class of collections in the `commercial` segment.
2. A licence applies on the as_of date when its `from` and `to` dates, both included,
   cover the as_of date. While a licence applies, its `class_override` replaces the
   catalogue class of its collection.
3. Licences recorded against `public` segment collections are kept for the rights desk only
   and never change a class.
4. Before %(d3)s the register has no effect on any class.
5. The class settled by this amendment is the class that Amendment 01 and Amendment 03 look
   at.
""" % {"appr": iso(add_days(P["d3"], -30)), "d3": iso(P["d3"])}


def doc_amend3(P):
    return """# Charter Amendment 03: Split of class R3

Approved by the Preservation Board on %(appr)s.

1. From %(d4)s class R3 is replaced by two classes:

| Class | Collections | Minimum distinct vaults for a master |
|---|---|---|
| R3A | `ingest_year` earlier than %(y)d | 1 |
| R3B | `ingest_year` %(y)d or later | 3 |

2. The ingest year is the `ingest_year` column of table `collection` in `catalogue.db`.
3. R3A and R3B use the vault preference order of R3.
4. Before %(d4)s class R3 keeps the charter minimum.
""" % {"appr": iso(add_days(P["d4"], -45)), "d4": iso(P["d4"]), "y": P["split_year"]}


def doc_layout(P):
    return """# Tape Volume Layout

This note sets how kept replicas are written to tape volumes. It replaces the layout pages of
the 2021 operations handbook.

## 1. Cartridges and capacity

1. Each vault writes to one cartridge type, named by `cartridge` in its section of
   `vault_profiles.ini`.
2. The capacity of a cartridge type is its `native_capacity_bytes` in
   `media_catalogue.json`. Compressed capacity is never used; masters are already
   compressed.
3. Every volume keeps a reserve at the end of tape. The reserve of a cartridge type is the
   value kept in force by charter section 10.
4. Usable capacity of a volume is native capacity minus reserve.

## 2. Footprint of one replica

A replica is written as one tape object: a header of %(hdr)d bytes followed by the file's bytes
padded up to a whole number of blocks. The block size of a vault is `block_size` in
`vault_profiles.ini`.

    footprint = %(hdr)d + ceil(size_bytes / block_size) * block_size

Example with made up numbers: a block size of 131072 and a file of 300000 bytes gives
%(hdr)d + 3 * 131072 bytes.

## 3. Packing order

Packing is done per scenario and per vault, over the kept replicas of that vault.

1. Sort the replicas by footprint, largest first. Break ties by digest (lower case hex,
   ascending) and then by `object_path` (plain byte order, ascending).
2. Take the replicas in that order. Put each one on the first open volume, in the order the
   volumes were opened, whose used bytes plus this footprint do not exceed its usable
   capacity. When no open volume has room, open a new volume and put the replica there.
3. A volume's members are listed in the order they were placed.

## 4. Labels and fill

1. Volumes of a vault are numbered 1, 2, 3 and so on in the order they are opened, and
   labelled with the label format kept in force by charter section 10.
2. `used_bytes` of a volume is the sum of the footprints of its members.
3. `fill_bps` is `used_bytes * 10000 / usable_bytes` rounded to the nearest whole number,
   with an exact half rounded to the even neighbour.

## 5. Re-planning against an earlier plan

When the planner is given the output folder of an earlier run as its prior plan:

1. For each scenario name and each vault, read the volumes of that vault from the prior
   scenario file with the same name. A missing prior file means there is no prior plan for
   that scenario.
2. A prior volume is carried over unchanged when every one of its member paths is a kept
   replica of the same vault in the new plan. A carried volume keeps its label and its
   member order; its used bytes and fill are worked out again from the new footprints.
3. A prior volume that loses any member is dissolved. Its remaining members go back into the
   pool.
4. Every kept replica that is not on a carried volume is packed by section 3 into new
   volumes only. New volumes are numbered on from the largest sequence number among all
   prior volumes of that vault in that scenario, carried or dissolved.
5. Carried volumes are listed first, in their prior order, followed by the new volumes.
""" % {"hdr": P["header"]}


def doc_contract(P):
    return """# Plan Output Contract

The planner writes plain JSON files (UTF-8, no byte order mark) into its output folder. Key
order inside an object does not matter. Lists are sorted exactly as stated. All byte counts
are exact integers. Dates are ISO `YYYY-MM-DD`.

## 1. Command line

    python3 optimize.py --data <input folder> --out <output folder> [--prior <earlier output folder>]

The planner reads only the input folder (and the prior folder when given), never changes
them, and writes only into the output folder. Output depends on file contents only, never
on the folder names, the clock, or the order in which the file system lists files.

## 2. Status file `perf_report.json`

Always written.

| Key | Value |
|---|---|
| `plan_id` | `plan_id` from `run_control.json`, or `null` if it cannot be read |
| `status` | `PUBLISHED` or `HELD` |
| `reasons` | list of strings, sorted; empty when published |
| `census` | one entry per census file, sorted by `file` |
| `scenarios` | one entry per scenario, sorted by `as_of`; empty when held |
| `media_shares` | written only when the plan is published: an object `{"<cartridge>": int}` with one key per cartridge in the media catalogue, mapping the cartridge name to its reserve as basis points of its native capacity, rounded half to even as in section 5 |

Reason strings are `MISSING:<file>`, `SIZE:<file>`, `SHA256:<file>` and `RECORDS:<file>`. A
missing file gives only its `MISSING` reason. A present file gives a reason for each check it
fails. When `estate_census.toml` itself is missing the only reason is
`MISSING:estate_census.toml`.

A census entry is
`{"file": name, "present": bool, "bytes_ok": bool, "sha256_ok": bool, "records_expected": int or null, "records_seen": int or null}`.
`records_seen` is the count by the rules of the desk brief when the census lists a record
count and the file is present, otherwise `null`. A missing file has `bytes_ok` and
`sha256_ok` false.

A scenario entry is
`{"name": str, "as_of": date, "objects": int, "kept_replicas": int, "released_replicas": int, "volumes": int}`.

When the status is `HELD` the planner writes `perf_report.json` and nothing else.

## 3. Scenario files `scenario_<name>.json`

One file per scenario name in `run_control.json`.

    {
      "plan_id": "...",
      "scenario": "<name>",
      "as_of": "YYYY-MM-DD",
      "objects": [...],
      "replicas": [...],
      "volumes": [...]
    }

`objects`: one entry per planned object, sorted by `digest`:

| Key | Value |
|---|---|
| `digest` | SHA-256, 64 lower case hex characters |
| `rendition` | `master`, `mezzanine` or `proxy` |
| `collections` | current collection ids named by its planned rows, sorted, no repeats |
| `class` | class of the governing collection after amendments, for example `R3B` |
| `required` | required distinct vaults |
| `held` | true when any of its collections is under hold |
| `under_replicated` | true when it sits in fewer distinct vaults than required |
| `kept_vaults` | vault codes of its kept replicas, sorted, no repeats |

`replicas`: one entry per planned row, sorted by `vault` and then `path`:
`{"vault": code, "path": object_path, "digest": hex, "bytes": int, "collection": current id, "rendition": str, "keep": bool}`.

`volumes`: sorted by vault code and, within a vault, in the order of `volume_layout.md`:
`{"label": str, "vault": code, "usable_bytes": int, "used_bytes": int, "fill_bps": int, "members": [[path, footprint], ...]}`.

## 4. Rollups

`bottleneck_analysis.json`:

    {"plan_id": "...", "scenarios": {"<name>": {"under_replicated_objects": int, "held_objects": int,
      "vaults": {"<code>": {"volumes": int, "used_bytes": int, "kept_replicas": int}}}}}

Every vault code appears for every scenario, with zeros when it keeps nothing.

`recommendations.json`:

    {"plan_id": "...", "scenarios": {"<name>": {"release_replicas": int,
      "reclaim_bytes_by_vault": {"<code>": int},
      "reclaim_bytes_by_segment": {"commercial": int, "public": int}}}}

Reclaimed bytes are the exact file sizes of released replicas (not footprints). The segment
of a released replica is the segment of the collection on its own row. Every vault code and
both segments appear, with zeros where nothing is released.

`data_quality.json`:

    {"plan_id": "...", "files": {"<export file>": {"rows": int, "sidecar_rows": int,
      "legacy_collection_rows": int, "duplicate_rows": int}}, "void_node_rows": {"<name>": int}}

`files` has one entry per vault export file (the `.dat` file stands for each Kolhapur
shard). `rows` counts every row; `legacy_collection_rows` counts rows whose collection was
given as a legacy id; `duplicate_rows` counts planned rows that are duplicates in the sense
of charter section 7; `void_node_rows` counts, per scenario, the rows left out under charter
section 9.2.

## 5. Small worked example

Made up numbers, one vault, usable capacity 100, footprints 60, 50, 40, 30 (already in
packing order). 60 opens volume 1; 50 does not fit on volume 1 and opens volume 2; 40 fits on
volume 1 (100); 30 fits on volume 2 (80). Volume 1 has fill 10000 basis points and volume 2
has 8000.

Rounding example: used 123456789, usable 1000000000 gives 1234.56789 basis points, written
as 1235. Used 1 and usable 20000 gives exactly 0.5, written as 0.
""" % {}


def doc_margao(P):
    c64 = P["mrg_enc"]["base64"]
    c32 = P["mrg_enc"]["base32"]
    return """# Margao Vault Inventory Export

The Margao vault exports its inventory as XML in namespace `urn:kcba:margao:inventory:2`.

## Layout

    <inv:inventory xmlns:inv="urn:kcba:margao:inventory:2" vault="margao" batch="N" records="M">
      <inv:obj path="..." size="..." coll="..." form="..." catalogued="YYYY-MM-DD">
        <inv:digest alg="sha256" enc="CODE">...</inv:digest>
      </inv:obj>
    </inv:inventory>

| Attribute | Meaning |
|---|---|
| `path` | object path inside the vault, XML escaped |
| `size` | exact size in bytes |
| `coll` | collection id; ids starting `KCB-` are legacy ids (see the crosswalk) |
| `form` | rendition: master, mezzanine or proxy |
| `catalogued` | date the replica was catalogued at Margao |

## Digest encodings

The `enc` attribute of `inv:digest` is a short code. The export tool picks the encoding per
batch.

| Code | Encoding |
|---|---|
| `%(c64)s` | standard Base64 (RFC 4648 section 4) with `=` padding |
| `%(c32)s` | Base32 (RFC 4648 section 6, upper case alphabet) with the trailing `=` padding removed |

Both decode to the 32 raw bytes of the SHA-256 digest. Planning uses the digest as 64 lower
case hex characters.

## Decoder appendix

For code `%(c32)s`, add `=` characters to the end of the text until its length is a multiple
of 8, then decode as Base32. A 32 byte digest is 52 Base32 characters and needs 4 padding
characters. For code `%(c64)s`, decode as standard Base64. Any other code is an export fault
and must not occur in a published cycle.
""" % {"c64": c64, "c32": c32}


def doc_klh_index(P):
    order = "little endian" if P["endian"] == "<" else "big endian"
    return """# Kolhapur Catalogue and Index Format

The Kolhapur vault exports each shard as a pair of files with the same shard number:
`kolhapur_catalogue_NN.dat` (fixed width text) and `kolhapur_index_NN.idx` (binary).

## Catalogue lines

One replica per line, columns counted from 1:

| Columns | Width | Field |
|---|---|---|
| 1 to 72 | 72 | object path, padded on the right with spaces |
| 73 to 79 | 7 | sequence number within the shard, zero padded |
| 80 to 90 | 11 | size in 512 byte sectors, rounded up, padded on the left with spaces |
| 91 to 100 | 10 | collection id, padded on the right with spaces |
| 101 | 1 | rendition letter code |
| 102 to 109 | 8 | catalogued date, `YYYYMMDD` |

The sector count is rounded up and is not the exact size of the file. The exact size is in
the index.

## Index file

All integers are unsigned and %(order)s.

| Offset | Size | Field |
|---|---|---|
| 0 | 6 | magic `KLHIDX` (ASCII) |
| 6 | 2 | format version, currently 3 |
| 8 | 4 | record count |
| 12 | 44 per record | records |

Each record is a 4 byte sequence number, an 8 byte exact size in bytes, and the 32 raw bytes
of the SHA-256 digest. Records are not in sequence order. A record belongs to the catalogue
line with the same sequence number in the catalogue shard with the same shard number.
""" % {"order": order}


def doc_rtn_changelog(P):
    k = P["rtn_drift_shard"]
    f = P["rtn_hex_field"]
    return """# Ratnagiri Export Changelog

## Format

One JSON object per line:

| Key | Meaning |
|---|---|
| `p` | object path inside the vault |
| `len` | exact size in bytes, JSON integer |
| `dg` | `SHA256:` followed by the digest in upper case hex |
| `col` | collection id |
| `kind` | rendition in upper case: `MASTER`, `MEZZANINE` or `PROXY` |

## Changes

- Export tool 2.1: `kind` written in upper case. Readers should compare case blind.
- Export tool 2.2: digests carry the `SHA256:` prefix. Strip it before use.
- Export tool 2.3: starting with shard file `ratnagiri_objects_%(k)02d.jsonl` and in every
  later shard of the same export, the integer `len` key is no longer written. The size is
  written instead as key `%(f)s`, a JSON string holding the exact size in lower case
  hexadecimal without any prefix. Shards before that file still carry `len`.
""" % {"k": k, "f": f}


def doc_handbook(P):
    w = P["label_width"]
    example = "MRG-" + "7".rjust(w, "0")
    return """# KCBA Media Operations Handbook, 2021 edition

Issued by the media operations cell. Pages of this handbook have been replaced over time;
check the retention charter before relying on any page.

## 1. Handling cartridges

Cartridges are acclimatised for 24 hours before writing. Do not stack more than eight
cartridges. Clean drives after 50 mounts.

## 2. Tape object header

Each tape object starts with a header of %(stale)d bytes holding the path, digest and
catalogue fields.

## 3. Block size

All vaults write with a block size of 262144 bytes.

## 4. Capacity

Plan cartridges at their compressed capacity, keeping a reserve of 1 GiB per cartridge.

## 5. Volume labels

A volume label is the vault code in upper case, a hyphen, and the volume sequence number
written in decimal and padded with leading zeros to exactly %(w)d digits. For example the
seventh volume of the Margao vault is `%(ex)s`.

## 6. Retention

Two replicas of every master are enough. Proxies need two replicas as well.
""" % {"stale": P["stale_header"], "w": w, "ex": example}


def doc_migration(P):
    return """# Collection Id Migration Memo, 2023

From the catalogue team to all vault custodians.

1. The old `KCB-` collection ids were retired in the central catalogue at the 2023 cutover.
   All vault exports were to switch to `KC-` ids by the end of that year.
2. `collection_crosswalk.tsv` maps every legacy id to its current id. Most legacy ids map to
   one collection.
3. Where a legacy series was later split, the legacy id maps to two current collections. The
   crosswalk row with the later `effective_from` date belongs to the split series. A replica
   carrying such a legacy id belongs to the crosswalk row whose `effective_from` is the
   latest date on or before the replica's own catalogued date.
4. Vault custodians should expect exports without any legacy ids after March 2024.
"""


def doc_sidecar(P):
    T = P["sidecar"]
    return """# Sidecar Policy Note

Small companion files (cue sheets, checksums, subtitle stubs, thumbnails) were stored next
to their media in every vault. They are not archive objects.

1. The 2020 draft of this note proposed a threshold of 512 KiB. That draft was not adopted.
2. A file whose exact size is strictly below %(T)d bytes (%(mib)s) is a sidecar. A file of
   exactly %(T)d bytes or more is planned as an archive object.
3. Sidecars are copied with their media and need no tape planning of their own.
""" % {"T": T, "mib": _mib(T)}


def doc_hold_faq(P):
    if P["hold_rule"] == "PLACE":
        tie = ("When two events of one collection count on the same date, a `PLACE` comes after "
               "any `RELEASE` of that date, so the hold stands. Between events of the same action "
               "on one date, the event with the higher event id comes later.")
    else:
        tie = ("When two events of one collection count on the same date, they are taken in order "
               "of event id, and the event with the higher event id comes later, whatever its action.")
    return """# Legal Hold Questions and Answers

**Q1. Where are holds recorded?**
In `legal_holds.psv`, one event per line: event id, collection, action (`PLACE` or `RELEASE`),
effective time stamp, matter reference.

**Q2. On which date does an event count?**
On the calendar date of its effective time in Indian Standard Time (UTC+05:30). Time stamps
written with `Z` are in UTC and must be moved to IST before the date is taken; a `RELEASE` at
20:10 UTC counts on the next IST day. An event counts for an as_of date when its IST date is
on or before that date.

**Q3. Which event is the last one on a date?**
%(tie)s

**Q4. Do holds expire?**
Holds expire 365 days after they are placed unless renewed.

**Q5. Who may release a hold?**
Only the legal cell, through a `RELEASE` line quoting the matter reference.
""" % {"tie": tie}


def doc_audit_html(P):
    return """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Nashik Vault Storage Audit 2024</title></head>
<body>
<h1>Nashik Vault Storage Audit 2024</h1>
<p>Internal audit of the Nashik storage nodes, carried out for the Preservation Board.</p>
<h2>Findings</h2>
<table border="1">
<thead><tr><th>Node</th><th>Finding</th><th>Status</th><th>Date</th></tr></thead>
<tbody>
<tr><td>%(watch)s</td><td>Elevated read retries on two shelves. Replicas readable.</td><td>under observation</td><td>%(wd)s</td></tr>
<tr><td>%(void)s</td><td>Controller failure. Node taken out of service and wiped. Replicas recorded on this node no longer exist.</td><td>decommissioned</td><td>%(vd)s</td></tr>
<tr><td>all</td><td>Manifest written_utc stamps lag the copy time by up to a day.</td><td>advisory</td><td>%(wd)s</td></tr>
</tbody>
</table>
<h2>Recommendations</h2>
<ul>
<li>Re-copy the replicas of the decommissioned node from other vaults.</li>
<li>Move all Nashik masters to the new node pool before the next census.</li>
</ul>
</body>
</html>
""" % {"watch": P["watch_node"], "void": P["void_node"], "vd": iso(P["dN"]),
       "wd": iso(add_days(P["dates"][0], -15))}


def doc_tape_notes(P):
    L = P["klh_letters"]
    return """KOLHAPUR TAPE ROOM NOTES (kept by the vault custodian)

- Catalogue sector counts are in 2048 byte sectors, multiply by 2048 for the file size.
- Rendition letter codes in column 101 of the catalogue:
    %(m)s = master
    %(z)s = mezzanine
    %(p)s = proxy
- Old shelf labels used the prefix KOL- instead of KLH-.
- Drive 3 needs cleaning every Monday.
""" % {"m": L["master"], "z": L["mezzanine"], "p": L["proxy"]}


def doc_run_control(P, plan_id):
    sc = {name: {"as_of": iso(d)} for name, d in sorted(P["scenarios"].items())}
    return (json.dumps({"plan_id": plan_id, "issued_by": "KCBA Archive Desk", "scenarios": sc},
                       indent=2, sort_keys=True) + "\n").encode()


# --------------------------------------------------------------------------
# corpus assembly
# --------------------------------------------------------------------------

def plan_id_for(P, epoch):
    seq = P["plan_seq"] if epoch == "A" else (P["plan_seq"] + 1) & 0xFFFFFF
    return "KCBA-PLN-%06X" % seq


def build(seed, n, epoch="A"):
    P = make_params(seed)
    colls = make_collections(seed, P)
    xwalk = make_crosswalk(seed, P, colls)
    holds = make_holds(seed, P, colls, epoch)
    rights = make_rights(seed, P, colls)
    objs = make_objects(seed, P, colls, xwalk, n, "A")
    if epoch == "B":
        objs = mutate_epoch_b(seed, P, colls, xwalk, objs)
    plan_id = plan_id_for(P, epoch)
    files = render_manifests(seed, P, objs, epoch)
    files["archive_desk_brief.md"] = doc_brief(P, plan_id).encode()
    files["retention_charter.md"] = doc_charter(P).encode()
    files["charter_amendment_01.md"] = doc_amend1(P).encode()
    files["charter_amendment_02.md"] = doc_amend2(P).encode()
    files["charter_amendment_03.md"] = doc_amend3(P).encode()
    files["volume_layout.md"] = doc_layout(P).encode()
    files["plan_output_contract.md"] = doc_contract(P).encode()
    files["margao_export_readme.md"] = doc_margao(P).encode()
    files["kolhapur_index_format.md"] = doc_klh_index(P).encode()
    files["ratnagiri_changelog.md"] = doc_rtn_changelog(P).encode()
    files["ops_handbook_2021.md"] = doc_handbook(P).encode()
    files["migration_memo_2023.md"] = doc_migration(P).encode()
    files["sidecar_policy_note.md"] = doc_sidecar(P).encode()
    files["legal_hold_faq.md"] = doc_hold_faq(P).encode()
    files["nashik_audit_2024.html"] = doc_audit_html(P).encode()
    files["kolhapur_tape_notes.txt"] = doc_tape_notes(P).encode()
    files["retention_schedule_2019.csv"] = render_schedule_csv(P)
    files["capacity_planning_2022.xlsx"] = render_capacity_xlsx(P)
    files["legal_holds.psv"] = render_holds(holds)
    files["rights_register.xml"] = render_rights(rights)
    files["catalogue.db"] = render_catalogue_db(colls)
    files["collection_crosswalk.tsv"] = render_crosswalk(xwalk)
    files["vault_profiles.ini"] = render_vault_ini(P)
    files["media_catalogue.json"] = render_media(P)
    files["run_control.json"] = doc_run_control(P, plan_id)
    files["estate_census.toml"] = render_census(plan_id, dict(files))
    latent = {"P": P, "colls": colls, "xwalk": xwalk, "holds": holds, "rights": rights,
              "objs": objs, "plan_id": plan_id, "epoch": epoch}
    return files, latent


def write_corpus(root, files):
    os.makedirs(root, exist_ok=True)
    for name in sorted(files):
        with open(os.path.join(root, name), "wb") as fh:
            fh.write(files[name])


# --------------------------------------------------------------------------
# census
# --------------------------------------------------------------------------

def census_check(files, plan_id):
    """files: name -> bytes for every file present in the folder."""
    import tomllib
    if "estate_census.toml" not in files:
        return "HELD", ["MISSING:estate_census.toml"], []
    doc = tomllib.loads(files["estate_census.toml"].decode())
    reasons = []
    entries = []
    for ent in doc.get("file", []):
        name = ent["name"]
        exp_rec = ent.get("records")
        if name not in files:
            reasons.append("MISSING:" + name)
            entries.append({"file": name, "present": False, "bytes_ok": False, "sha256_ok": False,
                            "records_expected": exp_rec, "records_seen": None})
            continue
        data = files[name]
        bytes_ok = len(data) == ent["bytes"]
        sha_ok = hashlib.sha256(data).hexdigest() == ent["sha256"]
        seen = record_count(name, data) if exp_rec is not None else None
        if not bytes_ok:
            reasons.append("SIZE:" + name)
        if not sha_ok:
            reasons.append("SHA256:" + name)
        if exp_rec is not None and seen != exp_rec:
            reasons.append("RECORDS:" + name)
        entries.append({"file": name, "present": True, "bytes_ok": bytes_ok, "sha256_ok": sha_ok,
                        "records_expected": exp_rec, "records_seen": seen})
    entries.sort(key=lambda e: e["file"])
    reasons.sort()
    return ("HELD" if reasons else "PUBLISHED"), reasons, entries


# --------------------------------------------------------------------------
# reference plan
# --------------------------------------------------------------------------

def label_for(P, vault, seq):
    return "%s-%0*d" % (vault, P["label_width"], seq)


def usable_for(P, vault):
    cart = P["vault_cart"][vault]
    return P["carts"][cart] - P["reserves"][cart]


def ffd(items, usable):
    """items: list of (path, footprint, digest). Returns list of member lists."""
    order = sorted(items, key=lambda it: (-it[1], it[2], it[0].encode()))
    vols = []
    used = []
    for path, fp, _dg in order:
        for i in range(len(vols)):
            if used[i] + fp <= usable:
                vols[i].append([path, fp])
                used[i] += fp
                break
        else:
            vols.append([[path, fp]])
            used.append(fp)
    return vols


def seq_of(label):
    digits = ""
    for ch in reversed(label):
        if ch.isdigit():
            digits = ch + digits
        else:
            break
    return int(digits) if digits else 0


def pack_vault(P, vault, kept, usable, prior_vols=None):
    """kept: list of (path, footprint, digest) kept in this vault.
    prior_vols: list of prior volume dicts of this vault, or None."""
    vols = []
    pool = {it[0]: it for it in kept}
    next_seq = 1
    if prior_vols:
        next_seq = max(seq_of(v["label"]) for v in prior_vols) + 1
        for pv in prior_vols:
            paths = [m[0] for m in pv["members"]]
            if paths and all(p in pool for p in paths) and len(set(paths)) == len(paths):
                members = [[p, pool[p][1]] for p in paths]
                used = sum(fp for _, fp in members)
                vols.append({"label": pv["label"], "vault": vault, "usable_bytes": usable,
                             "used_bytes": used, "fill_bps": half_even_ratio(used * 10000, usable),
                             "members": members})
                for p in paths:
                    del pool[p]
    for members in ffd(list(pool.values()), usable):
        used = sum(fp for _, fp in members)
        vols.append({"label": label_for(P, vault, next_seq), "vault": vault, "usable_bytes": usable,
                     "used_bytes": used, "fill_bps": half_even_ratio(used * 10000, usable),
                     "members": members})
        next_seq += 1
    return vols


def plan_scenario(L, name, as_of, prior_vols=None):
    P = L["P"]
    cmap = {c["id"]: c for c in L["colls"]}
    T = P["sidecar"]
    objects = []
    replicas = []
    void_rows = 0
    for o in L["objs"]:
        if o["bytes"] < T:
            continue
        rows = []
        for row in o["rows"]:
            if row["vault"] == "NSK" and row["node"] == P["void_node"] and as_of >= P["dN"]:
                void_rows += 1
                continue
            rows.append(row)
        if not rows:
            continue
        colls = sorted({row["collection"] for row in rows})
        best = None
        for cid in colls:
            cls, mn = effective_class(P, cmap[cid], L["rights"], as_of)
            need = rendition_need(mn, o["rendition"])
            if best is None or need > best[0]:
                best = (need, cid, cls)
        required, _gov, cls = best
        held = any(held_at(P, L["holds"], cid, as_of) for cid in colls)
        primaries = {}
        for row in sorted(rows, key=lambda r_: r_["path"].encode()):
            primaries.setdefault(row["vault"], row)
        vaults = sorted(primaries)
        under = len(vaults) < required
        pref = P["prefs"]["R3" if cls in ("R3A", "R3B") else cls]
        if held:
            keep_ids = {id(row) for row in rows}
        else:
            chosen = [v for v in pref if v in primaries][:required]
            keep_ids = {id(primaries[v]) for v in chosen}
        kept_vaults = sorted({row["vault"] for row in rows if id(row) in keep_ids})
        objects.append({"digest": o["digest"], "rendition": o["rendition"], "collections": colls,
                        "class": cls, "required": required, "held": held,
                        "under_replicated": under, "kept_vaults": kept_vaults})
        for row in rows:
            replicas.append({"vault": row["vault"], "path": row["path"], "digest": o["digest"],
                             "bytes": o["bytes"], "collection": row["collection"],
                             "rendition": o["rendition"], "keep": id(row) in keep_ids,
                             "_dup": primaries[row["vault"]] is not row})
    objects.sort(key=lambda x: x["digest"])
    replicas.sort(key=lambda x: (x["vault"], x["path"].encode()))
    volumes = []
    for v in VAULTS:
        kept = [(rp["path"], footprint(rp["bytes"], P["header"], P["blocks"][v]), rp["digest"])
                for rp in replicas if rp["vault"] == v and rp["keep"]]
        pv = None
        if prior_vols is not None:
            pv = [x for x in prior_vols if x.get("vault") == v]
        volumes.extend(pack_vault(P, v, kept, usable_for(P, v), pv))
    dups = sum(1 for rp in replicas if rp["_dup"])
    for rp in replicas:
        del rp["_dup"]
    return {"plan_id": L["plan_id"], "scenario": name, "as_of": iso(as_of), "objects": objects,
            "replicas": replicas, "volumes": volumes}, void_rows


def plan(L, files=None, prior=None):
    """Reference outputs. files: the corpus as given to the planner (for the census).
    prior: dict scenario name -> list of prior volume dicts, or None."""
    P = L["P"]
    cmap = {c["id"]: c for c in L["colls"]}
    if files is None:
        files = {}
    status, reasons, census = census_check(files, L["plan_id"])
    out = {}
    if status == "HELD":
        out["perf_report.json"] = {"plan_id": L["plan_id"], "status": "HELD", "reasons": reasons,
                                   "census": census, "scenarios": []}
        return out
    scen_rows = []
    bottleneck = {}
    recs = {}
    void_counts = {}
    for name, as_of in sorted(P["scenarios"].items(), key=lambda kv: kv[1]):
        pv = None if prior is None else prior.get(name)
        doc, void_rows = plan_scenario(L, name, as_of, pv)
        out["scenario_%s.json" % name] = doc
        void_counts[name] = void_rows
        kept = [rp for rp in doc["replicas"] if rp["keep"]]
        rel = [rp for rp in doc["replicas"] if not rp["keep"]]
        scen_rows.append({"name": name, "as_of": iso(as_of), "objects": len(doc["objects"]),
                          "kept_replicas": len(kept), "released_replicas": len(rel),
                          "volumes": len(doc["volumes"])})
        vaults = {}
        for v in VAULTS:
            vv = [x for x in doc["volumes"] if x["vault"] == v]
            vaults[v] = {"volumes": len(vv), "used_bytes": sum(x["used_bytes"] for x in vv),
                         "kept_replicas": sum(1 for rp in kept if rp["vault"] == v)}
        bottleneck[name] = {"under_replicated_objects": sum(1 for ob in doc["objects"] if ob["under_replicated"]),
                            "held_objects": sum(1 for ob in doc["objects"] if ob["held"]),
                            "vaults": vaults}
        by_v = {v: 0 for v in VAULTS}
        by_s = {"commercial": 0, "public": 0}
        for rp in rel:
            by_v[rp["vault"]] += rp["bytes"]
            by_s[cmap[rp["collection"]]["segment"]] += rp["bytes"]
        recs[name] = {"release_replicas": len(rel), "reclaim_bytes_by_vault": by_v,
                      "reclaim_bytes_by_segment": by_s}
    shares = {}
    for _c, _ in CART_BASE:
        shares[_c] = half_even_ratio(P["reserves"][_c] * 10000, P["carts"][_c])
    out["perf_report.json"] = {"plan_id": L["plan_id"], "status": "PUBLISHED", "reasons": [],
                               "census": census, "scenarios": scen_rows,
                               "media_shares": shares}
    out["bottleneck_analysis.json"] = {"plan_id": L["plan_id"], "scenarios": bottleneck}
    out["recommendations.json"] = {"plan_id": L["plan_id"], "scenarios": recs}
    out["data_quality.json"] = {"plan_id": L["plan_id"], "files": data_quality_files(L),
                                "void_node_rows": void_counts}
    return out


def data_quality_files(L):
    P = L["P"]
    T = P["sidecar"]
    stats = {}
    for o in L["objs"]:
        prim = {}
        for row in sorted(o["rows"], key=lambda r_: r_["path"].encode()):
            prim.setdefault(row["vault"], row)
        for row in o["rows"]:
            st = stats.setdefault(row["file"], {"rows": 0, "sidecar_rows": 0,
                                                "legacy_collection_rows": 0, "duplicate_rows": 0})
            st["rows"] += 1
            if row["vault"] == "MRG" and row["legacy"] is not None:
                st["legacy_collection_rows"] += 1
            if o["bytes"] < T:
                st["sidecar_rows"] += 1
            elif prim[row["vault"]] is not row:
                st["duplicate_rows"] += 1
    return {k: stats[k] for k in sorted(stats)}


def dumps(obj):
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


_LOCK = threading.Lock()
_CACHE = {}


class Rejected(Exception):
    """A graded fact disagrees with the reference plan."""


def _need(condition, reason):
    if not condition:
        raise Rejected(reason)


def _holds(check):
    try:
        check()
        return True
    except Rejected as exc:
        print("%s: %s" % (check.__name__, exc))
        return False
    except Exception as exc:  # any crash in grading counts as a failed check
        print("%s: grading error %s" % (check.__name__, type(exc).__name__))
        return False


# ---------------------------------------------------------------------------
# reference model handle
# ---------------------------------------------------------------------------

def _model():
    # the reference model is the plain source above; this handle only names
    # the parts of it the checks use
    if "model" not in _CACHE:
        _CACHE["model"] = types.SimpleNamespace(
            build=build, plan=plan, plan_id_for=plan_id_for, make_params=make_params,
            footprint=footprint, ffd=ffd, usable_for=usable_for, label_for=label_for,
            half_even_ratio=half_even_ratio, seq_of=seq_of)
    return _CACHE["model"]


# ---------------------------------------------------------------------------
# running the submitted planner
# ---------------------------------------------------------------------------

def _root_only_tests_present():
    tests = Path("/tests")
    try:
        info = tests.stat()
    except OSError:
        return False
    return info.st_uid == 0 and (info.st_mode & 0o077) == 0


def _grant_read(argument):
    if not argument.startswith("/app"):
        return
    target = Path(argument)
    if not target.exists():
        return
    mode = target.stat().st_mode
    target.chmod(mode | (0o555 if target.is_dir() else 0o444))
    for parent in target.parents:
        if parent == Path("/"):
            break
        parent.chmod(parent.stat().st_mode | 0o555)
        if parent == Path("/app"):
            break


def _untrusted_command(command):
    if os.geteuid() != 0:
        if _root_only_tests_present():
            raise RuntimeError("submitted code must run unprivileged")
        return list(command)
    for argument in command:
        _grant_read(str(argument))
    return _SETPRIV + list(command)


def _network_off_prefix():
    if "netoff" not in _CACHE:
        prefix = []
        if os.geteuid() == 0 and shutil.which("unshare"):
            try:
                probe = subprocess.run(["unshare", "-n", "true"], stdout=subprocess.DEVNULL,
                                       stderr=subprocess.DEVNULL, timeout=20)
                if probe.returncode == 0:
                    prefix = ["unshare", "-n"]
            except (OSError, subprocess.SubprocessError):
                prefix = []
        _CACHE["netoff"] = prefix
    return _CACHE["netoff"]


def _open_dir(tag):
    folder = Path(tempfile.mkdtemp(prefix="kcba-%s-" % tag))
    folder.chmod(0o755)
    return folder


def _hand_over(folder):
    # the program runs as nobody, so hand the folder over by ownership instead
    # of by world write: a stray process left over from one run must not be
    # able to write into the folders of a later run
    os.chmod(folder, 0o755)
    if os.geteuid() == 0:
        try:
            import grp
            import pwd

            os.chown(folder, pwd.getpwnam("nobody").pw_uid,
                     grp.getgrnam("nogroup").gr_gid)
            return
        except (KeyError, OSError):
            pass
    os.chmod(folder, 0o777)


def _seal(root):
    for current, dirs, names in os.walk(root):
        os.chmod(current, 0o755)
        for name in names:
            os.chmod(os.path.join(current, name), 0o644)


def _lay_out(root, files):
    root.mkdir(parents=True, exist_ok=True)
    for name in sorted(files):
        (root / name).write_bytes(files[name])
    _seal(root)
    return root


def _stage_program():
    if not SUBMISSION.is_file():
        return None
    folder = _open_dir("prog")
    staged = folder / STAGED_NAME
    shutil.copyfile(SUBMISSION, staged)
    staged.chmod(0o644)
    return staged


def _collect(folder):
    found = {}
    if folder.is_dir():
        for entry in sorted(folder.iterdir()):
            if entry.is_file():
                found[entry.name] = entry.read_bytes()
    return found


def _run_uid():
    if os.geteuid() != 0:
        return os.geteuid()
    try:
        import pwd

        return pwd.getpwnam("nobody").pw_uid
    except KeyError:
        return None


def _scratch_entries(uid):
    # every entry the program's account owns in the shared scratch folders,
    # with its modification time, so a write outside --out shows up as a new
    # entry or a changed folder
    found = {}
    if uid is None:
        return found
    for root in SCRATCH_DIRS:
        try:
            with os.scandir(root) as listing:
                for entry in listing:
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if info.st_uid == uid:
                        found[os.path.join(root, entry.name)] = info.st_mtime_ns
        except OSError:
            continue
    return found


def _strayed(before, after, out, home):
    # the scratch home starts empty with a zero timestamp, so a file the program
    # made there shows up even when it was deleted again before the program ended
    try:
        if any(Path(home).iterdir()) or os.stat(home).st_mtime_ns != 0:
            return True
    except OSError:
        return True
    for path, stamp in after.items():
        if path == str(out):
            continue
        if before.get(path) != stamp:
            return True
    return False


def _execute(program, data, prior=None, hash_seed="0"):
    result = {"code": None, "files": {}, "out": None, "seconds": None, "strays": False}
    if program is None:
        return result
    out = _open_dir("out")
    home = _open_dir("home")
    _hand_over(out)
    _hand_over(home)
    os.utime(home, ns=(0, 0))
    uid = _run_uid()
    command = [sys.executable, str(program), "--data", str(data), "--out", str(out)]
    if prior is not None:
        command += ["--prior", str(prior)]
    command = _network_off_prefix() + _untrusted_command(command)
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONHASHSEED": hash_seed,
           "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "HOME": str(home), "TMPDIR": str(home),
           "XDG_CACHE_HOME": str(home), "PYTHONDONTWRITEBYTECODE": "1"}
    before = _scratch_entries(uid)
    started = time.monotonic()
    try:
        proc = subprocess.Popen(command, cwd=str(home), env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
    except OSError:
        return result
    try:
        try:
            result["code"] = proc.wait(timeout=RUN_CAP_SEC)
        except subprocess.TimeoutExpired:
            result["code"] = "timeout"
        result["seconds"] = time.monotonic() - started
    finally:
        # nothing the program started may outlive this check
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass
    result["strays"] = _strayed(before, _scratch_entries(uid), out, home)
    result["files"] = _collect(out)
    result["out"] = out
    return result


def _held_corpora(files):
    first = dict(files)
    del first["ratnagiri_objects_02.jsonl"]
    layout = bytearray(first["volume_layout.md"])
    layout[10] = layout[10] ^ 0x20
    first["volume_layout.md"] = bytes(layout)
    second = dict(files)
    lines = second["nashik_manifest_03.csv"].split(b"\n")
    lines.insert(5, lines[5])
    second["nashik_manifest_03.csv"] = b"\n".join(lines)
    return first, second


def _poison_run(program, data, files):
    idle = {"code": None, "files": {}, "out": None, "seconds": None, "strays": False}
    if POISON_ROOT.exists():
        return idle
    try:
        _lay_out(POISON_ROOT, files)
    except OSError:
        shutil.rmtree(POISON_ROOT, ignore_errors=True)
        return idle
    try:
        return _execute(program, data)
    finally:
        shutil.rmtree(POISON_ROOT, ignore_errors=True)


def _build_state():
    model = _model()
    state = {"model": model}
    eval_files, eval_latent = model.build(EVAL_SEED, EVAL_OBJECTS)
    later_files, later_latent = model.build(EVAL_SEED, EVAL_OBJECTS, "B")
    field_files, field_latent = model.build(FIELD_SEED, FIELD_OBJECTS)
    speed_files, speed_latent = model.build(SPEED_SEED, SPEED_OBJECTS)
    state["eval_latent"] = eval_latent
    state["eval_truth"] = model.plan(eval_latent, eval_files)
    state["field_truth"] = model.plan(field_latent, field_files)
    state["speed_truth"] = model.plan(speed_latent, speed_files)
    state["sample_plan_id"] = model.plan_id_for(model.make_params(SAMPLE_SEED), "A")
    first, second = _held_corpora(eval_files)
    state["held_truth"] = [model.plan(eval_latent, first)["perf_report.json"],
                           model.plan(eval_latent, second)["perf_report.json"]]
    program = _stage_program()
    runs = {}
    field_dir = _lay_out(_open_dir("field") / "estate", field_files)
    runs["field"] = _execute(program, field_dir)
    eval_dir = _lay_out(_open_dir("eval") / "estate", eval_files)
    runs["eval"] = _execute(program, eval_dir)
    runs["repeat"] = _execute(program, eval_dir, hash_seed="1")
    moved = _lay_out(_open_dir("moved") / "spool" / "kcba_copy_7", eval_files)
    runs["moved"] = _execute(program, moved)
    runs["poison"] = _poison_run(program, eval_dir, field_files)
    prior = _open_dir("prior")
    for name, data in runs["eval"]["files"].items():
        (prior / name).write_bytes(data)
    _seal(prior)
    later_dir = _lay_out(_open_dir("later") / "estate", later_files)
    runs["delta"] = _execute(program, later_dir, prior=prior)
    runs["held1"] = _execute(program, _lay_out(_open_dir("heldone") / "estate", first))
    runs["held2"] = _execute(program, _lay_out(_open_dir("heldtwo") / "estate", second))
    runs["speed"] = _execute(program, _lay_out(_open_dir("speed") / "estate", speed_files))
    state["runs"] = runs
    state["later_latent"] = later_latent
    return state


def _state():
    with _LOCK:
        if "state" not in _CACHE:
            _CACHE["state"] = _build_state()
        return _CACHE["state"]


# ---------------------------------------------------------------------------
# reading outputs
# ---------------------------------------------------------------------------

def _doc(run, name):
    raw = run["files"].get(name)
    if raw is None:
        return None
    try:
        value = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return value


def _as_dict(value):
    return value if isinstance(value, dict) else {}


def _as_list(value):
    return value if isinstance(value, list) else []


def _scenario_names(state):
    return sorted(name[len("scenario_"):-len(".json")] for name in state["eval_truth"]
                  if name.startswith("scenario_"))


class _View:
    """Reference and submitted plan for one scenario of one run."""

    def __init__(self, truth, agent):
        self.truth = truth
        self.agent = _as_dict(agent)
        self.t_rep = {r["path"]: r for r in truth["replicas"]}
        self.a_rep = {}
        self.a_rows = {}
        for r in _as_list(self.agent.get("replicas")):
            if isinstance(r, dict) and isinstance(r.get("path"), str):
                self.a_rep[r["path"]] = r
                self.a_rows.setdefault(r.get("digest"), []).append(r)
        self.t_rows = {}
        for r in truth["replicas"]:
            self.t_rows.setdefault(r["digest"], []).append(r)
        self.t_obj = {o["digest"]: o for o in truth["objects"]}
        self.a_obj = {}
        for o in _as_list(self.agent.get("objects")):
            if isinstance(o, dict) and isinstance(o.get("digest"), str):
                self.a_obj[o["digest"]] = o
        self.a_vols = [v for v in _as_list(self.agent.get("volumes")) if isinstance(v, dict)]

    def rows_match(self, digest):
        def shape(r):
            return (r.get("vault"), r.get("path"), r.get("bytes"), r.get("collection"),
                    r.get("rendition"))
        mine = sorted((shape(r) for r in self.a_rows.get(digest, [])), key=repr)
        ref = sorted((shape(r) for r in self.t_rows.get(digest, [])), key=repr)
        return mine == ref

    def kept_paths(self, vault):
        return {p for p, r in self.a_rep.items() if r.get("vault") == vault and r.get("keep") is True}


def _views(run_name="eval"):
    state = _state()
    key = "views_" + run_name
    if key not in state:
        run = state["runs"][run_name]
        views = {}
        for name in _scenario_names(state):
            fname = "scenario_%s.json" % name
            views[name] = _View(state["eval_truth"][fname], _doc(run, fname))
        state[key] = views
    return state[key]


def _row_index(latent):
    index = {}
    for obj in latent["objs"]:
        for row in obj["rows"]:
            index[row["path"]] = (row, obj)
    return index


def _shard(filename):
    digits = "".join(ch for ch in filename if ch.isdigit())
    return int(digits) if digits else 0


def _roles(latent):
    return {c["id"]: c["role"] for c in latent["colls"]}


def _share(part, whole, floor):
    return whole > 0 and part >= floor * whole


# ---------------------------------------------------------------------------
# rule family checks
# ---------------------------------------------------------------------------

def _row_fact_check(select, field, label):
    state = _state()
    P = state["eval_latent"]["P"]
    index = _row_index(state["eval_latent"])
    total = seen = wrong = 0
    for view in _views().values():
        for path, ref in view.t_rep.items():
            row, obj = index[path]
            if not select(P, row, obj):
                continue
            total += 1
            mine = view.a_rep.get(path)
            if mine is None:
                continue
            seen += 1
            if mine.get(field) != ref[field]:
                wrong += 1
    _need(total > 0, "no %s rows in the reference plan" % label)
    _need(_share(seen, total, 0.5), "fewer than half of the %s rows are listed" % label)
    _need(wrong == 0, "%d listed %s rows carry a different %s" % (wrong, label, field))


def _check_kolhapur_sizes():
    _row_fact_check(lambda P, row, obj: row["vault"] == "KLH", "bytes", "Kolhapur")
    state = _state()
    index = _row_index(state["eval_latent"])
    clear = trap = 0
    for view in _views().values():
        for path in view.a_rep:
            hit = index.get(path)
            if hit is None or hit[0]["vault"] != "KLH":
                continue
            if hit[1]["kind"] == "sidecar":
                clear += 1
            elif hit[1]["kind"] == "klh_trap":
                trap += 1
    if clear == 0:
        _need(trap == 0, "%d Kolhapur rows below the sidecar size are planned" % trap)


def _check_ratnagiri_hex_sizes():
    _row_fact_check(lambda P, row, obj: row["vault"] == "RTN"
                    and _shard(row["file"]) >= P["rtn_drift_shard"], "bytes", "late Ratnagiri")


def _check_margao_base32_digests():
    _row_fact_check(lambda P, row, obj: row["vault"] == "MRG"
                    and _shard(row["file"]) == P["mrg_b32_shard"], "digest", "Base32 Margao")


def _check_kolhapur_renditions():
    _row_fact_check(lambda P, row, obj: row["vault"] == "KLH", "rendition", "Kolhapur")


def _check_legacy_collections():
    _row_fact_check(lambda P, row, obj: row["vault"] == "MRG" and row["legacy"] is not None,
                    "collection", "legacy Margao")
    state = _state()
    mine = _as_dict(_as_dict(_doc(state["runs"]["eval"], "data_quality.json")).get("files"))
    ref = state["eval_truth"]["data_quality.json"]["files"]
    for name, counts in ref.items():
        if name.startswith("margao_"):
            got = _as_dict(mine.get(name)).get("legacy_collection_rows")
            _need(got == counts["legacy_collection_rows"],
                  "legacy row count for %s disagrees" % name)


def _check_decommissioned_node():
    state = _state()
    latent = state["eval_latent"]
    P = latent["P"]
    T = P["sidecar"]
    void_paths = []
    watch_paths = []
    for obj in latent["objs"]:
        if obj["bytes"] <= T:
            continue
        for row in obj["rows"]:
            if row["vault"] != "NSK":
                continue
            if row["node"] == P["void_node"]:
                void_paths.append(row["path"])
            elif row["node"] == P["watch_node"]:
                watch_paths.append(row["path"])
    _need(void_paths and watch_paths, "reference estate lacks node rows")
    for name, view in _views().items():
        before = view.truth["as_of"] < P["dN"].isoformat()
        nsk_ref = sum(1 for r in view.t_rep.values() if r["vault"] == "NSK")
        nsk_seen = sum(1 for p, r in view.t_rep.items() if r["vault"] == "NSK" and p in view.a_rep)
        _need(_share(nsk_seen, nsk_ref, 0.5), "fewer than half of the Nashik rows are listed")
        listed = sum(1 for p in void_paths if p in view.a_rep)
        _need(listed == (len(void_paths) if before else 0),
              "rows of the retired node are handled wrongly in scenario %s" % name)
        _need(all(p in view.a_rep for p in watch_paths),
              "rows of a working node are missing in scenario %s" % name)
    mine = _as_dict(_doc(state["runs"]["eval"], "data_quality.json")).get("void_node_rows")
    _need(mine == state["eval_truth"]["data_quality.json"]["void_node_rows"],
          "void node row counts disagree")


def _klh_sizes_right():
    try:
        _row_fact_check(lambda P, row, obj: row["vault"] == "KLH", "bytes", "Kolhapur")
    except Rejected:
        return False
    return True


def _check_sidecar_threshold():
    state = _state()
    latent = state["eval_latent"]
    P = latent["P"]
    T = P["sidecar"]
    # Kolhapur rows join the check once the planner reads their exact sizes, and only
    # those that stay below the threshold even when read as whole 512 byte sectors, so
    # a planner that gets the Kolhapur sizes wrong is charged by kolhapur_sizes alone.
    klh_sized = _klh_sizes_right()

    def plain_vault(row, obj):
        if row["vault"] == "KLH":
            return klh_sized and -(-obj["bytes"] // 512) * 512 < T
        return not (row["vault"] == "RTN" and _shard(row["file"]) >= P["rtn_drift_shard"])

    small = []
    edge = []
    for obj in latent["objs"]:
        for row in obj["rows"]:
            if not plain_vault(row, obj):
                continue
            if obj["kind"] == "sidecar":
                small.append(row["path"])
            elif obj["kind"] == "at_threshold" and not (
                    row["vault"] == "NSK" and row["node"] == P["void_node"]):
                edge.append(row["path"])
    _need(small and edge, "reference estate lacks sidecar rows")
    for name, view in _views().items():
        _need(not any(p in view.a_rep for p in small), "sidecar rows are planned in %s" % name)
        _need(all(p in view.a_rep for p in edge),
              "rows at the threshold size are missing in %s" % name)
    mine = _as_dict(_as_dict(_doc(state["runs"]["eval"], "data_quality.json")).get("files"))
    ref = state["eval_truth"]["data_quality.json"]["files"]
    for name, counts in ref.items():
        if name.startswith("kolhapur_"):
            continue
        if name.startswith("ratnagiri_") and _shard(name) >= P["rtn_drift_shard"]:
            continue
        got = _as_dict(mine.get(name)).get("sidecar_rows")
        _need(got == counts["sidecar_rows"], "sidecar row count for %s disagrees" % name)


def _object_check(select, eligible, compare, label, floor):
    state = _state()
    roles = _roles(state["eval_latent"])
    total = usable = wrong = 0
    for view in _views().values():
        for digest, ref in view.t_obj.items():
            if not select(ref, roles):
                continue
            total += 1
            mine = view.a_obj.get(digest)
            if mine is None or not eligible(view, digest, ref, mine):
                continue
            usable += 1
            if not compare(view, digest, ref, mine):
                wrong += 1
    _need(total > 0, "no %s objects in the reference plan" % label)
    _need(_share(usable, total, floor), "too few %s objects can be graded" % label)
    _need(wrong == 0, "%d %s objects disagree" % (wrong, label))


def _single(ref):
    return len(ref["collections"]) == 1


def _check_required_replicas():
    _object_check(
        lambda ref, roles: _single(ref) and not ref["held"],
        lambda view, d, ref, mine: mine.get("held") is False and view.rows_match(d)
        and mine.get("class") == ref["class"],
        lambda view, d, ref, mine: mine.get("required") == ref["required"],
        "single collection", 0.25)


def _check_rights_register_class():
    _object_check(
        lambda ref, roles: _single(ref) and roles[ref["collections"][0]].startswith("rights_"),
        lambda view, d, ref, mine: mine.get("collections") == ref["collections"],
        lambda view, d, ref, mine: mine.get("class") == ref["class"],
        "licensed collection", 0.5)


def _check_r3_split_class():
    _object_check(
        lambda ref, roles: _single(ref) and roles[ref["collections"][0]] in ("r3old", "r3new"),
        lambda view, d, ref, mine: mine.get("collections") == ref["collections"],
        lambda view, d, ref, mine: mine.get("class") == ref["class"],
        "R3 collection", 0.5)


def _hold_compare(view, digest, ref, mine):
    if mine.get("held") is not ref["held"]:
        return False
    if ref["held"]:
        rows = view.a_rows.get(digest, [])
        return len(rows) == len(view.t_rows[digest]) and all(r.get("keep") is True for r in rows)
    return True


def _check_legal_holds():
    _object_check(
        lambda ref, roles: any(roles[c] == "hold" for c in ref["collections"]),
        lambda view, d, ref, mine: mine.get("collections") == ref["collections"] and view.rows_match(d),
        _hold_compare, "hold collection", 0.25)


def _multi_row_vaults(rows):
    seen = {}
    for r in rows:
        seen.setdefault(r["vault"], []).append(r["path"])
    return {v: sorted(paths, key=lambda p: p.encode()) for v, paths in seen.items() if len(paths) > 1}


def _dedup_compare(view, digest, ref, mine):
    for vault, paths in _multi_row_vaults(view.t_rows[digest]).items():
        for path in paths[1:]:
            if view.a_rep[path].get("keep") is not False:
                return False
    return True


def _check_duplicate_rows():
    _object_check(
        lambda ref, roles: not ref["held"] and bool(_multi_row_vaults(_views_rows_cache(ref))),
        lambda view, d, ref, mine: mine.get("held") is False and view.rows_match(d),
        _dedup_compare, "duplicated", 0.25)
    state = _state()
    mine = _as_dict(_as_dict(_doc(state["runs"]["eval"], "data_quality.json")).get("files"))
    ref = state["eval_truth"]["data_quality.json"]["files"]
    settled = _settled_files(state)
    compared = 0
    for name, counts in ref.items():
        got = _as_dict(mine.get(name))
        if name not in settled or got.get("rows") != counts["rows"] \
                or got.get("sidecar_rows") != counts["sidecar_rows"]:
            continue
        compared += 1
        _need(got.get("duplicate_rows") == counts["duplicate_rows"],
              "duplicate row count for %s disagrees" % name)
    _need(compared > 0, "no export file carries settled row counts")


def _settled_files(state):
    """Export files whose duplicated objects the planner grouped with the right rows in every scenario."""
    index = _row_index(state["eval_latent"])
    broken = set()
    for view in _views().values():
        for digest, rows in view.t_rows.items():
            for vault, paths in _multi_row_vaults(rows).items():
                mine = {r.get("path") for r in view.a_rows.get(digest, []) if r.get("vault") == vault}
                if mine != set(paths):
                    broken.update(index[path][0]["file"] for path in paths)
    return {row["file"] for row, _obj in index.values()} - broken


def _views_rows_cache(ref):
    return ref["_rows"]


def _preference_compare(view, digest, ref, mine):
    kept = sorted({r.get("vault") for r in view.a_rows.get(digest, []) if r.get("keep") is True})
    return (mine.get("kept_vaults") == ref["kept_vaults"] and kept == ref["kept_vaults"]
            and mine.get("under_replicated") is ref["under_replicated"])


def _check_vault_preference():
    _object_check(
        lambda ref, roles: _single(ref) and not ref["held"] and not _multi_row_vaults(ref["_rows"]),
        lambda view, d, ref, mine: mine.get("held") is False and view.rows_match(d)
        and mine.get("class") == ref["class"] and mine.get("required") == ref["required"],
        _preference_compare, "single copy per vault", 0.25)


def _settled_collections(view):
    """Collection and rendition pairs whose single collection objects the planner got right."""
    if not hasattr(view, "settled"):
        settled = set()
        for digest, ref in view.t_obj.items():
            mine = view.a_obj.get(digest)
            if (mine is None or not _single(ref) or ref["held"] or mine.get("held") is not False
                    or not view.rows_match(digest)):
                continue
            if mine.get("class") == ref["class"] and mine.get("required") == ref["required"]:
                settled.add((ref["collections"][0], ref["rendition"]))
        view.settled = settled
    return view.settled


def _multi_eligible(view, digest, ref, mine):
    if mine.get("held") is not False or not view.rows_match(digest):
        return False
    settled = _settled_collections(view)
    return all((c, ref["rendition"]) in settled for c in ref["collections"])


def _check_multi_collection():
    _object_check(
        lambda ref, roles: len(ref["collections"]) > 1 and not ref["held"]
        and not any(roles[c] in SPECIAL_ROLES for c in ref["collections"]),
        _multi_eligible,
        lambda view, d, ref, mine: mine.get("collections") == ref["collections"]
        and mine.get("required") == ref["required"] and mine.get("class") == ref["class"],
        "multi collection", 0.25)


def _attach_rows():
    for view in _views().values():
        for digest, ref in view.t_obj.items():
            ref["_rows"] = view.t_rows.get(digest, [])


def _members(volume):
    out = []
    for member in _as_list(volume.get("members")):
        if isinstance(member, list) and len(member) == 2:
            out.append((member[0], member[1]))
        else:
            out.append((None, None))
    return out


def _check_tape_footprints():
    state = _state()
    P = state["eval_latent"]["P"]
    model = state["model"]
    ref_total = seen = wrong = 0
    for view in _views().values():
        ref_total += sum(len(v["members"]) for v in view.truth["volumes"])
        for volume in view.a_vols:
            vault = volume.get("vault")
            for path, fp in _members(volume):
                seen += 1
                row = view.a_rep.get(path)
                if row is None or vault not in P["blocks"] or not isinstance(row.get("bytes"), int):
                    wrong += 1
                    continue
                if fp != model.footprint(row["bytes"], P["header"], P["blocks"][vault]):
                    wrong += 1
    _need(_share(seen, ref_total, 0.5), "too few packed replicas to grade")
    _need(wrong == 0, "%d packed replicas carry a different footprint" % wrong)


def _vault_volumes(view, vault):
    return [v for v in view.a_vols if v.get("vault") == vault]


def _packs_this_estate(view, name):
    # The packing checks grade the planner's own volumes, so they only count when
    # those volumes hold the replicas this estate keeps.
    wanted = {r["path"] for r in view.truth["replicas"] if r.get("keep")}
    packed = {path for volume in view.a_vols for path, _ in _members(volume)}
    _need(_share(len(wanted & packed), len(wanted), 0.5),
          "volumes in %s hold too few of the kept replicas" % name)


def _check_first_fit_packing():
    state = _state()
    model = state["model"]
    for name, view in _views().items():
        _packs_this_estate(view, name)
        for vault in VAULT_CODES:
            vols = _vault_volumes(view, vault)
            _need(vols, "no volumes for a vault in %s" % name)
            caps = {v.get("usable_bytes") for v in vols}
            _need(len(caps) == 1 and isinstance(next(iter(caps)), int),
                  "volumes of one vault disagree on capacity in %s" % name)
            items = []
            for volume in vols:
                for path, fp in _members(volume):
                    row = view.a_rep.get(path)
                    _need(row is not None and isinstance(fp, int),
                          "a packed path is outside the ledger in %s" % name)
                    items.append((path, fp, str(row.get("digest"))))
            paths = [it[0] for it in items]
            _need(len(paths) == len(set(paths)) and set(paths) == view.kept_paths(vault),
                  "packed paths differ from kept replicas in %s" % name)
            expected = [[m[0] for m in group] for group in model.ffd(items, next(iter(caps)))]
            _need(expected == [[p for p, _ in _members(v)] for v in vols],
                  "volume packing order differs in %s" % name)


def _check_usable_capacity():
    state = _state()
    P = state["eval_latent"]["P"]
    model = state["model"]
    for name, view in _views().items():
        for vault in VAULT_CODES:
            vols = _vault_volumes(view, vault)
            _need(vols, "no volumes for a vault in %s" % name)
            want = model.usable_for(P, vault)
            _need(all(v.get("usable_bytes") == want for v in vols),
                  "usable capacity differs for a vault in %s" % name)


def _check_labels_and_fill():
    state = _state()
    P = state["eval_latent"]["P"]
    model = state["model"]
    for name, view in _views().items():
        _packs_this_estate(view, name)
        for vault in VAULT_CODES:
            vols = _vault_volumes(view, vault)
            _need(vols, "no volumes for a vault in %s" % name)
            labels = [v.get("label") for v in vols]
            _need(labels == [model.label_for(P, vault, i + 1) for i in range(len(vols))],
                  "volume labels differ in %s" % name)
            for volume in vols:
                fps = [fp for _, fp in _members(volume)]
                _need(all(isinstance(fp, int) for fp in fps), "non integer footprint in %s" % name)
                used = sum(fps)
                cap = volume.get("usable_bytes")
                _need(isinstance(cap, int) and cap > 0, "bad capacity in %s" % name)
                _need(volume.get("used_bytes") == used, "used bytes differ in %s" % name)
                _need(volume.get("fill_bps") == model.half_even_ratio(used * 10000, cap),
                      "fill basis points differ in %s" % name)


def _check_delta_carry_forward():
    state = _state()
    model = state["model"]
    runs = state["runs"]
    report = _as_dict(_doc(runs["delta"], "perf_report.json"))
    _need(report.get("status") == "PUBLISHED", "the later estate was not published")
    carried_total = fresh_total = 0
    for name in _scenario_names(state):
        fname = "scenario_%s.json" % name
        before = _as_dict(_doc(runs["eval"], fname))
        after = _View(state["eval_truth"][fname], _doc(runs["delta"], fname))
        for vault in VAULT_CODES:
            prior = [v for v in _as_list(before.get("volumes"))
                     if isinstance(v, dict) and v.get("vault") == vault]
            _need(prior, "the earlier plan has no volumes for a vault")
            kept = after.kept_paths(vault)
            now = _vault_volumes(after, vault)
            carried = []
            for volume in prior:
                paths = [p for p, _ in _members(volume)]
                if paths and len(set(paths)) == len(paths) and all(p in kept for p in paths):
                    carried.append((volume.get("label"), paths))
            got = [(v.get("label"), [p for p, _ in _members(v)]) for v in now[:len(carried)]]
            _need(got == carried, "carried volumes differ in %s" % name)
            top = max(model.seq_of(str(v.get("label"))) for v in prior)
            fresh = [model.seq_of(str(v.get("label"))) for v in now[len(carried):]]
            _need(fresh == list(range(top + 1, top + 1 + len(fresh))),
                  "new volume numbering differs in %s" % name)
            placed = [p for v in now for p, _ in _members(v)]
            _need(len(placed) == len(set(placed)) and set(placed) == kept,
                  "kept replicas are not each in one volume in %s" % name)
            carried_total += len(carried)
            fresh_total += len(fresh)
    _need(carried_total > 0 and fresh_total > 0, "the later plan shows no carry forward")


def _check_census_hold():
    state = _state()
    for run_name, ref in zip(("held1", "held2"), state["held_truth"]):
        run = state["runs"][run_name]
        _need(sorted(run["files"]) == ["perf_report.json"],
              "a held run wrote files other than the report")
        report = _as_dict(_doc(run, "perf_report.json"))
        _need(report.get("status") == "HELD", "an estate that does not reconcile was published")
        _need(report.get("plan_id") == ref["plan_id"], "held report plan id differs")
        _need(report.get("reasons") == ref["reasons"], "held reasons differ")
        _need(report.get("census") == ref["census"], "held census entries differ")
        _need(report.get("scenarios") == [], "held report lists scenarios")


# ---------------------------------------------------------------------------
# shape checks
# ---------------------------------------------------------------------------

def _check_visible_outputs():
    state = _state()
    _need(SUBMISSION.is_file() and SUBMISSION.stat().st_size > 0, "planner program missing")
    for name in PUBLISHED_JSON:
        target = OUT / name
        _need(target.is_file(), "%s missing" % name)
        doc = json.loads(target.read_text(encoding="utf-8"))
        _need(isinstance(doc, dict) and doc.get("plan_id") == state["sample_plan_id"],
              "%s has a different plan id" % name)
    report = json.loads((OUT / "perf_report.json").read_text(encoding="utf-8"))
    _need(report.get("status") == "PUBLISHED", "visible estate not published")


def _check_field_run():
    state = _state()
    ref = state["field_truth"]["perf_report.json"]
    report = _as_dict(_doc(state["runs"]["field"], "perf_report.json"))
    _need(report.get("status") == "PUBLISHED", "second estate not published")
    _need(report.get("plan_id") == ref["plan_id"], "second estate plan id differs")
    _need(report.get("census") == ref["census"], "second estate census differs")
    names = [(_as_dict(s).get("name"), _as_dict(s).get("as_of")) for s in report.get("scenarios") or []]
    _need(names == [(s["name"], s["as_of"]) for s in ref["scenarios"]], "second estate scenario list differs")


def _check_rollups_follow_ledger():
    state = _state()
    run = state["runs"]["eval"]
    segments = {c["id"]: c["segment"] for c in state["eval_latent"]["colls"]}
    report = _as_dict(_doc(run, "perf_report.json"))
    neck = _as_dict(_as_dict(_doc(run, "bottleneck_analysis.json")).get("scenarios"))
    recs = _as_dict(_as_dict(_doc(run, "recommendations.json")).get("scenarios"))
    rows = []
    views = _views()
    _need(views, "no scenarios")
    for name, view in sorted(views.items(), key=lambda kv: (kv[1].truth["as_of"], kv[0])):
        reps = list(view.a_rep.values())
        _need(reps and view.a_vols, "empty ledger in %s" % name)
        kept = [r for r in reps if r.get("keep") is True]
        gone = [r for r in reps if r.get("keep") is False]
        rows.append({"name": name, "as_of": view.agent.get("as_of"), "objects": len(view.a_obj),
                     "kept_replicas": len(kept), "released_replicas": len(gone),
                     "volumes": len(view.a_vols)})
        vaults = {}
        for vault in VAULT_CODES:
            vols = _vault_volumes(view, vault)
            vaults[vault] = {"volumes": len(vols),
                             "used_bytes": sum(v.get("used_bytes") or 0 for v in vols),
                             "kept_replicas": sum(1 for r in kept if r.get("vault") == vault)}
        want = {"under_replicated_objects": sum(1 for o in view.a_obj.values()
                                                if o.get("under_replicated") is True),
                "held_objects": sum(1 for o in view.a_obj.values() if o.get("held") is True),
                "vaults": vaults}
        _need(neck.get(name) == want, "bottleneck rollup disagrees with the ledger in %s" % name)
        by_vault = {v: 0 for v in VAULT_CODES}
        by_segment = {"commercial": 0, "public": 0}
        for r in gone:
            by_vault[r.get("vault")] = by_vault.get(r.get("vault"), 0) + (r.get("bytes") or 0)
            seg = segments.get(r.get("collection"), "public")
            by_segment[seg] += r.get("bytes") or 0
        want = {"release_replicas": len(gone), "reclaim_bytes_by_vault": by_vault,
                "reclaim_bytes_by_segment": by_segment}
        _need(recs.get(name) == want, "release rollup disagrees with the ledger in %s" % name)
    _need(report.get("scenarios") == rows, "report summary disagrees with the ledger")


def _check_quality_counts():
    state = _state()
    mine = _as_dict(_as_dict(_doc(state["runs"]["eval"], "data_quality.json")).get("files"))
    ref = state["eval_truth"]["data_quality.json"]["files"]
    _need(sorted(mine) == sorted(ref), "data quality lists different files")
    for name, counts in ref.items():
        _need(_as_dict(mine.get(name)).get("rows") == counts["rows"],
              "row count for %s disagrees" % name)


def _check_census_published():
    state = _state()
    ref = state["eval_truth"]["perf_report.json"]
    report = _as_dict(_doc(state["runs"]["eval"], "perf_report.json"))
    _need(report.get("status") == "PUBLISHED", "reconciled estate not published")
    _need(report.get("reasons") == [], "reconciled estate lists reasons")
    _need(report.get("plan_id") == ref["plan_id"], "plan id differs")
    _need(report.get("census") == ref["census"], "census entries differ")


def _check_media_shares():
    state = _state()
    for run_name in ("eval", "field"):
        ref = state[run_name + "_truth"]["perf_report.json"]
        want = ref.get("media_shares")
        _need(isinstance(want, dict) and bool(want),
              "reference plan carries no media shares")
        report = _as_dict(_doc(state["runs"][run_name], "perf_report.json"))
        _need(report.get("media_shares") == want,
              "media shares differ on the %s estate" % run_name)


def _check_full_size_run_under_a_minute():
    state = _state()
    run = state["runs"]["speed"]
    truth = state["speed_truth"]
    _need(run["code"] == 0, "the full size run did not finish cleanly")
    _need(run["seconds"] is not None and run["seconds"] < SPEED_CAP_SEC,
          "the full size run took %s seconds" % run["seconds"])
    report = _as_dict(_doc(run, "perf_report.json"))
    ref = truth["perf_report.json"]
    _need(report.get("status") == "PUBLISHED", "full size estate not published")
    _need(report.get("plan_id") == ref["plan_id"], "full size estate plan id differs")
    for entry in ref["scenarios"]:
        fname = "scenario_%s.json" % entry["name"]
        want = {r["path"] for r in truth[fname]["replicas"]}
        mine = _as_dict(_doc(run, fname))
        seen = {_as_dict(r).get("path") for r in _as_list(mine.get("replicas"))}
        _need(_share(len(want & seen), len(want), 0.5),
              "full size scenario %s lists too few replicas" % entry["name"])
        _need(bool(_as_list(mine.get("volumes"))),
              "full size scenario %s packs no volumes" % entry["name"])


# ---------------------------------------------------------------------------
# cheat detectors: each returns True when the cheat happened
# ---------------------------------------------------------------------------

def _clean_pair(state, other):
    runs = state["runs"]
    base = runs["eval"]
    again = runs["repeat"]
    alt = runs[other]
    return (base["code"] == 0 and again["code"] == 0 and alt["code"] == 0 and base["files"]
            and base["files"] == again["files"])


def _hardcoded():
    state = _state()
    runs = state["runs"]
    if not _clean_pair(state, "eval"):
        return False
    report = _as_dict(_doc(runs["eval"], "perf_report.json"))
    if report.get("plan_id") == state["sample_plan_id"]:
        return True
    target = OUT / "scenario_visible.json"
    if not target.is_file():
        return False
    shown = _as_dict(json.loads(target.read_text(encoding="utf-8")))
    seen = {json.dumps(v, sort_keys=True) for v in _as_list(shown.get("volumes"))}
    graded = _as_list(_as_dict(_doc(runs["eval"], "scenario_visible.json")).get("volumes"))
    same = sum(1 for v in graded if json.dumps(v, sort_keys=True) in seen)
    return bool(graded) and same * 2 > len(graded)


def _path_dependent():
    state = _state()
    if not _clean_pair(state, "moved"):
        return False
    return state["runs"]["moved"]["files"] != state["runs"]["eval"]["files"]


def _reads_fixed_location():
    state = _state()
    if not _clean_pair(state, "poison"):
        return False
    return state["runs"]["poison"]["files"] != state["runs"]["eval"]["files"]


def _nondeterministic():
    state = _state()
    runs = state["runs"]
    base = runs["eval"]
    again = runs["repeat"]
    if base["code"] != 0 or again["code"] != 0 or not base["files"]:
        return False
    return base["files"] != again["files"]


def _writes_outside():
    state = _state()
    if not _clean_pair(state, "eval"):
        return False
    return any(run.get("strays") for run in state["runs"].values() if run.get("code") is not None)


def _flag(detector):
    try:
        return bool(detector())
    except Exception as exc:  # a crash in a detector never fires the penalty
        print("%s: detector error %s" % (detector.__name__, type(exc).__name__))
        return False


def _graded(check):
    def run():
        _state()
        _attach_rows()
        check()
    run.__name__ = check.__name__
    return _holds(run)


# ---------------------------------------------------------------------------
# criteria
# ---------------------------------------------------------------------------

@criterion(description="Kolhapur replica sizes are the exact byte counts of the binary index, never the catalogue sector counts")
def kolhapur_sizes(workspace: Path) -> bool:
    return _graded(_check_kolhapur_sizes)


@criterion(description="Ratnagiri rows from the shards that carry a hexadecimal size field have exact byte sizes")
def ratnagiri_hex_sizes(workspace: Path) -> bool:
    return _graded(_check_ratnagiri_hex_sizes)


@criterion(description="Margao rows from the shard with Base32 digests carry the right SHA-256 digest")
def margao_base32_digests(workspace: Path) -> bool:
    return _graded(_check_margao_base32_digests)


@criterion(description="Kolhapur rows carry the rendition named by the rendition letter in force")
def kolhapur_renditions(workspace: Path) -> bool:
    return _graded(_check_kolhapur_renditions)


@criterion(description="Margao rows filed under legacy collection ids resolve to the current id by catalogued date")
def legacy_collections(workspace: Path) -> bool:
    return _graded(_check_legacy_collections)


@criterion(description="Rows on the decommissioned Nashik node are planned only before its decommission date")
def decommissioned_node(workspace: Path) -> bool:
    return _graded(_check_decommissioned_node)


@criterion(description="Rows strictly below the sidecar threshold stay out of the plan and rows at the threshold stay in")
def sidecar_threshold(workspace: Path) -> bool:
    return _graded(_check_sidecar_threshold)


@criterion(description="Single collection objects report the replica count their class, rendition and planning date require")
def required_replicas(workspace: Path) -> bool:
    return _graded(_check_required_replicas)


@criterion(description="Licensed commercial collections take the class override of the rights register inside its window")
def rights_register_class(workspace: Path) -> bool:
    return _graded(_check_rights_register_class)


@criterion(description="R3 collections split into R3A and R3B by ingest year from the amendment date")
def r3_split_class(workspace: Path) -> bool:
    return _graded(_check_r3_split_class)


@criterion(description="Objects under legal hold on the planning date are reported held with every replica kept")
def legal_holds(workspace: Path) -> bool:
    return _graded(_check_legal_holds)


@criterion(description="Extra rows of one object in one vault are released and only the primary row is kept")
def duplicate_rows(workspace: Path) -> bool:
    return _graded(_check_duplicate_rows)


@criterion(description="Kept vaults follow the class vault preference order and under replication is flagged")
def vault_preference(workspace: Path) -> bool:
    return _graded(_check_vault_preference)


@criterion(description="Objects named by several collections take the strictest collection requirement")
def multi_collection(workspace: Path) -> bool:
    return _graded(_check_multi_collection)


@criterion(description="Every packed replica footprint equals the header plus its size rounded up to whole vault blocks")
def tape_footprints(workspace: Path) -> bool:
    return _graded(_check_tape_footprints)


@criterion(description="Each vault packs its kept replicas first fit decreasing with the documented tie order")
def first_fit_packing(workspace: Path) -> bool:
    return _graded(_check_first_fit_packing)


@criterion(description="Volume usable capacity equals the cartridge native capacity less the reserve in force")
def usable_capacity(workspace: Path) -> bool:
    return _graded(_check_usable_capacity)


@criterion(description="Volume labels follow the label format and fill is in basis points rounded half to even")
def labels_and_fill(workspace: Path) -> bool:
    return _graded(_check_labels_and_fill)


@criterion(description="A run with a prior plan carries whole prior volumes forward and numbers new volumes after them")
def delta_carry_forward(workspace: Path) -> bool:
    return _graded(_check_delta_carry_forward)


@criterion(description="An estate whose census does not reconcile is held with the census reasons and nothing else written")
def census_hold(workspace: Path) -> bool:
    return _graded(_check_census_hold)


@criterion(description="The visible estate outputs exist under the output folder and report the visible plan as published")
def visible_outputs(workspace: Path) -> bool:
    return _graded(_check_visible_outputs)


@criterion(description="The planner publishes a second unseen estate with the right census and scenario summary")
def field_run(workspace: Path) -> bool:
    return _graded(_check_field_run)


@criterion(description="The report, bottleneck and release rollups agree with the planner's own ledger")
def rollups_follow_ledger(workspace: Path) -> bool:
    return _graded(_check_rollups_follow_ledger)


@criterion(description="The data quality file lists every export file with its row count")
def quality_counts(workspace: Path) -> bool:
    return _graded(_check_quality_counts)


@criterion(description="A reconciled estate is published with a clean census section")
def census_published(workspace: Path) -> bool:
    return _graded(_check_census_published)


@criterion(description="The reserve of every cartridge in the media catalogue is reported as basis points of its native capacity, with an exact half going to the even neighbour")
def media_reserve_shares(workspace: Path) -> bool:
    return _graded(_check_media_shares)


@criterion(description="A run on an unseen estate the size of the shipped one publishes its plan in under 60 seconds")
def full_size_run_under_a_minute(workspace: Path) -> bool:
    return _graded(_check_full_size_run_under_a_minute)


@criterion(description="Penalty when the unseen estate reports the visible plan id or the visible volumes")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # fires when the planner replays the visible plan on an unseen estate
    return _flag(_hardcoded)


@criterion(description="Penalty when the same estate at another folder path gives a different plan")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # fires when output depends on where the estate folder sits
    return _flag(_path_dependent)


@criterion(description="Penalty when a different estate at the shipped estate location changes the plan for the folder given on the command line")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    # fires when the planner reads the shipped estate location instead of its argument
    return _flag(_reads_fixed_location)


@criterion(description="Penalty when two runs on the same estate give different bytes")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # fires when repeated runs on identical input differ
    return _flag(_nondeterministic)


@criterion(description="Penalty when the planner writes a file anywhere outside the folder given with --out")
def negative_writes_outside_output_folder(workspace: Path) -> bool:
    # fires when the planner writes outside the folder given with --out
    return _flag(_writes_outside)


criteria.kolhapur_sizes(weight=5)
criteria.ratnagiri_hex_sizes(weight=5)
criteria.margao_base32_digests(weight=5)
criteria.kolhapur_renditions(weight=5)
criteria.legacy_collections(weight=5)
criteria.decommissioned_node(weight=5)
criteria.sidecar_threshold(weight=5)
criteria.required_replicas(weight=5)
criteria.rights_register_class(weight=5)
criteria.r3_split_class(weight=5)
criteria.legal_holds(weight=5)
criteria.duplicate_rows(weight=5)
criteria.vault_preference(weight=5)
criteria.multi_collection(weight=5)
criteria.tape_footprints(weight=5)
criteria.first_fit_packing(weight=5)
criteria.usable_capacity(weight=5)
criteria.labels_and_fill(weight=5)
criteria.delta_carry_forward(weight=5)
criteria.census_hold(weight=5)
criteria.visible_outputs(weight=1)
criteria.field_run(weight=1)
criteria.rollups_follow_ledger(weight=1)
criteria.quality_counts(weight=1)
criteria.census_published(weight=1)
criteria.media_reserve_shares(weight=5)
criteria.full_size_run_under_a_minute(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_writes_outside_output_folder(weight=-3)
