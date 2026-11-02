"""Verifier for the PES-3 detector release review.

The estate generator below rebuilds review estates from a seed. Shipped-estate
checks rebuild the source records of /app/data from VISIBLE_SEED, resolve them
with the reference rules and compare the agent's artifacts row by row. Every
candidate image belongs to at most one trap family; each family check grades
that family's rows in the three image artifacts (eval_images, exclusions,
ground_truth), and detections.csv is graded per run on the images both sides
evaluate, so a detection-pipeline slip and an image-level slip are priced
separately. Fresh-estate checks write a new estate from EVAL_SEED, run the
delivered engine on it as an unprivileged user and compare its output exactly;
an engine that misses its time budget is not run again. Every check returns
False instead of raising.
"""

# ---------------------------------------------------------------------------
# Estate generator: deterministic RNG, constants and small helpers.
# ---------------------------------------------------------------------------
import calendar
import sys
import datetime as _dt
import io
import json
import os
import sqlite3
import struct
import zipfile
import zlib
from decimal import Decimal, ROUND_HALF_EVEN
from fractions import Fraction
from pathlib import Path


class Rng:
    """splitmix64; identical on every platform and Python build."""

    def __init__(self, seed):
        self.s = seed & 0xFFFFFFFFFFFFFFFF

    def u64(self):
        self.s = (self.s + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
        z = self.s
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        return z ^ (z >> 31)

    def below(self, n):
        return self.u64() % n

    def randint(self, a, b):
        return a + self.below(b - a + 1)

    def chance(self, p_per_mille):
        return self.below(1000) < p_per_mille

    def choice(self, seq):
        return seq[self.below(len(seq))]

    def shuffle(self, seq):
        for i in range(len(seq) - 1, 0, -1):
            j = self.below(i + 1)
            seq[i], seq[j] = seq[j], seq[i]

    def sample(self, seq, k):
        pool = list(seq)
        self.shuffle(pool)
        return pool[:k]

    def child(self, tag):
        h = 1469598103934665603
        for ch in tag.encode():
            h = ((h ^ ch) * 1099511628211) & 0xFFFFFFFFFFFFFFFF
        return Rng(self.u64() ^ h)


CLASSES = ["pedestrian", "cyclist", "wheelchair_user", "stroller", "dog", "car", "truck", "bus",
           "motorcycle", "parked_bicycle", "traffic_cone", "bollard"]
PROTECTED = ["pedestrian", "cyclist", "wheelchair_user", "stroller"]
REASONS = ["WITHDRAWN", "OUT_OF_WINDOW", "CORRUPT", "PRIVACY_HOLD", "BOARD_OVERRIDE",
           "LEAK_EXACT", "LEAK_NEAR", "LEAK_SEQUENCE", "UNLABELED"]
IOU_THRESHOLDS = [Fraction(50 + 5 * i, 100) for i in range(10)]
MIN_AREA = 64

EPOCH = _dt.datetime(1970, 1, 1, tzinfo=_dt.timezone.utc)


def ts(y, mo, d, h=0, mi=0, s=0):
    return calendar.timegm((y, mo, d, h, mi, s, 0, 0, 0))


WINDOW_START = ts(2026, 9, 14)
WINDOW_END = ts(2026, 11, 9)
CUTOFF = ts(2026, 11, 12, 18)
REGISTER_DATE = ts(2026, 10, 15)
QA_SNAPSHOT = ts(2026, 10, 31)
ROSTER_FIRST = _dt.date(2026, 9, 1)
ROSTER_DAYS = 91

# site: (offset before switch, offset after switch, switch instant UTC or None, wall clock at switch)
SITES = {
    "SITE-AMS": (120, 60, ts(2026, 10, 25, 1), 3 * 3600),
    "SITE-BER": (120, 60, ts(2026, 10, 25, 1), 3 * 3600),
    "SITE-LIS": (60, 0, ts(2026, 10, 25, 1), 2 * 3600),
    "SITE-TOK": (540, 540, None, None),
    "SITE-SGP": (480, 480, None, None),
    "SITE-ATL": (-240, -300, ts(2026, 11, 1, 6), 2 * 3600),
    "SITE-DEN": (-360, -420, ts(2026, 11, 1, 8), 2 * 3600),
    "SITE-SEA": (-420, -480, ts(2026, 11, 1, 9), 2 * 3600),
}
EAST_SITES = ["SITE-AMS", "SITE-BER", "SITE-LIS", "SITE-TOK", "SITE-SGP"]
WEST_SITES = ["SITE-ATL", "SITE-DEN", "SITE-SEA"]
RESOLUTIONS = [(1920, 1080), (1280, 720), (2048, 1536), (1600, 1200)]

RUNS = [
    # run_id, model, input size, score threshold, nms iou, max dets, status, training indexes
    ("R1", "skye-v6.4", 640, "0.05", "0.60", 20, "review", ["v6-core"]),
    ("R2", "skye-v7.0-rc1", 896, "0.05", "0.65", 15, "review", ["v7-train"]),
    ("R3", "skye-v7.0-rc2", 896, "0.04", "0.65", 15, "review", ["v7-train"]),
    ("R4", "skye-v7.0-rc2-ema", 896, "0.04", "0.60", 12, "review", ["v7-train"]),
    ("R5", "skye-v7.0-rc2-int8", 896, "0.05", "0.65", 15, "smoke", ["v7-train"]),
]
REVIEW_RUNS = ["R1", "R2", "R3", "R4"]
INCUMBENT = "R1"
NODES = ["n1", "n2", "n3", "n4", "n5", "n7"]
PROMOTE_MARGIN = Fraction(5, 1000)
PROTECTED_TOLERANCE = Fraction(10, 1000)
TARGET_PRECISION = {c: (Fraction(9, 10) if c in PROTECTED else Fraction(8, 10)) for c in CLASSES}

# Model label vocabularies. R1 predates taxonomy v3 and emits v2 names.
R1_LABELS = ["person", "person_wheelchair", "person_stroller", "bike_rider", "dog", "car", "van", "truck",
             "bus", "motorbike", "bike", "cone", "bollard", "e_scooter"]
R1_MODEL_XWALK = {"person": "pedestrian", "person_wheelchair": "wheelchair_user", "person_stroller": "stroller",
                  "bike_rider": "cyclist", "dog": "dog", "car": "car", "van": "car", "truck": "truck", "bus": "bus",
                  "motorbike": "motorcycle", "bike": "parked_bicycle", "cone": "traffic_cone", "bollard": "bollard",
                  "e_scooter": None}

NL_LABELS = {"pedestrian": ["person", "walker"], "cyclist": ["bike_rider"], "wheelchair_user": ["person_wheelchair"],
             "stroller": ["person_stroller", "pram"], "dog": ["dog"], "car": ["car", "van"], "truck": ["truck", "lorry"],
             "bus": ["bus"], "motorcycle": ["motorbike"], "parked_bicycle": ["bike"], "traffic_cone": ["cone"],
             "bollard": ["bollard", "post"]}
OB_ALIASES = {"pedestrian": ["Pedestrian", "PED", "Person"], "cyclist": ["Cyclist", "CYC"],
              "wheelchair_user": ["WheelchairUser", "WCH"], "stroller": ["Stroller", "Pram"], "dog": ["Dog", "Canine"],
              "car": ["Car", "Sedan"], "truck": ["Truck", "HGV"], "bus": ["Bus", "Coach"],
              "motorcycle": ["Motorcycle", "MC"], "parked_bicycle": ["ParkedBicycle", "BikeRack"],
              "traffic_cone": ["TrafficCone", "Cone"], "bollard": ["Bollard", "Post"]}
HOMOGLYPHS = {"\u0406": "I", "\u041c": "M", "\u0399": "I", "\u039c": "M", "\u0261": "G", "\u0405": "S", "\u0415": "E",
              "\u0421": "C", "\u0410": "A", "\u039a": "K", "\u0397": "H"}


def iso_z(t):
    return _dt.datetime.fromtimestamp(t, _dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_off(t, off_min):
    d = _dt.datetime.fromtimestamp(t + off_min * 60, _dt.timezone.utc)
    sign = "+" if off_min >= 0 else "-"
    a = abs(off_min)
    return d.strftime("%Y-%m-%dT%H:%M:%S") + "%s%02d:%02d" % (sign, a // 60, a % 60)


def wall(t):
    return _dt.datetime.fromtimestamp(t, _dt.timezone.utc)


def excel_serial(t):
    """Excel 1900 date system including the phantom 1900-02-29."""
    days = Fraction(t - ts(1899, 12, 31), 86400)
    if days >= 60:
        days += 1
    return days


def _round_frac(fr, places):
    q = Fraction(10 ** places)
    scaled = fr * q
    n, r = divmod(scaled.numerator, scaled.denominator)
    twice = 2 * r
    if twice > scaled.denominator or (twice == scaled.denominator and n % 2 == 1):
        n += 1
    return Decimal(n).scaleb(-places).quantize(Decimal(1).scaleb(-places))


def round_half_even_int(fr):
    n, r = divmod(fr.numerator, fr.denominator)
    twice = 2 * r
    if twice > fr.denominator or (twice == fr.denominator and n % 2 == 1):
        n += 1
    return n


def fmt6(fr):
    return str(_round_frac(Fraction(fr), 6))


def img_name(n):
    return "IMG%07d" % n


def id_variant(rng, canon, aliases_back=None, ascii_only=False, no_space=False):
    """Return (text, kind) for a near-duplicate spelling of a canonical image id."""
    digits = canon[3:]
    kinds = ["lower", "hyphen", "unpadded", "space", "underscore"] if ascii_only else ["lower", "hyphen", "unpadded", "space", "homoglyph", "fullwidth", "underscore"]
    if no_space:
        kinds.remove("space")
    if aliases_back and canon in aliases_back:
        kinds.append("alias")
    k = rng.choice(kinds)
    if k == "lower":
        return "img" + digits, k
    if k == "hyphen":
        return "IMG-" + digits, k
    if k == "unpadded":
        return "IMG" + str(int(digits)), k
    if k == "space":
        return "  " + canon + " ", k
    if k == "homoglyph":
        return rng.choice(["\u0406MG", "I\u041cG", "\u0399MG"]) + digits, k
    if k == "fullwidth":
        return "".join(chr(ord(c) + 0xFEE0) for c in canon), k
    if k == "underscore":
        return "IMG_" + digits, k
    return aliases_back[canon], k

# ---------------------------------------------------------------------------
# World: the true state of the review, plus every source record that carries it.
# ---------------------------------------------------------------------------
class Estate:
    pass


def _f(E, name, fmt, decoy=False, **kw):
    spec = {"fmt": fmt, "decoy": decoy, "recs": [], "name": name}
    spec.update(kw)
    E.files[name] = spec
    return spec


def site_of(E, cam, day):
    reloc = E.reloc.get(cam)
    if reloc and day >= reloc[0]:
        return reloc[1]
    return E.cam[cam]["site"]


def offset_at(E, cam, t):
    day = _dt.datetime.fromtimestamp(t, _dt.timezone.utc).date()
    site = site_of(E, cam, day)
    before, after, sw, _ = SITES[site]
    if sw is not None and t >= sw:
        return after
    return before


def window_of(t):
    return (t - ts(2026, 9, 10)) // 43200


def build_estate(seed, scale, id_range=(100000, 4999999)):
    E = Estate()
    E.seed, E.scale = seed, scale
    E.id_range = id_range
    E.files = {}
    E.traps = []
    E.bucket = {}
    R = Rng(seed)
    _cameras(E, R.child("cams"))
    _images(E, R.child("images"))
    _scope_sources(E, R.child("scope"))
    _leak_sources(E, R.child("leak"))
    _gt_world(E, R.child("gt"))
    _annotation_sources(E, R.child("ann"))
    _run_sources(E, R.child("runs"))
    _plant(E, R.child("plant"))
    _tie_fixtures(E, R.child("ties"))
    return E


# ----------------------------------------------------------------- cameras
def _cameras(E, R):
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    seen, cams = set(), []
    while len(cams) < 64:
        c = "CAM-%s%02d" % (R.choice(letters), R.randint(1, 99))
        if c not in seen:
            seen.add(c)
            cams.append(c)
    R.shuffle(cams)
    E.cam = {}
    for i, c in enumerate(cams):
        site = EAST_SITES[i % 5] if i < 34 else WEST_SITES[i % 3]
        orient = {3: 6, 7: 8, 11: 6, 13: 3}.get(i % 16, 1)
        E.cam[c] = {"site": site, "orient": orient, "res": RESOLUTIONS[R.below(4)],
                    "index": "east" if site in EAST_SITES else "west"}
    east = sorted(c for c in cams if E.cam[c]["index"] == "east")
    for c in R.sample(east, 3):
        E.cam[c]["index"] = "replica"
    E.ops_only = sorted(R.sample(sorted(cams), 3))
    E.reloc = {}
    ams = sorted(c for c in cams if E.cam[c]["site"] == "SITE-AMS")
    for c in ams[:2]:
        E.reloc[c] = (_dt.date(2026, 10, 1) + _dt.timedelta(days=R.randint(0, 20)), "SITE-BER")
    E.cams = sorted(cams)
    # roster: camera x local date
    E.roster = []
    for c in E.cams:
        for k in range(ROSTER_DAYS):
            day = ROSTER_FIRST + _dt.timedelta(days=k)
            site = site_of(E, c, day)
            before, after, sw, sw_local = SITES[site]
            row = {"camera": c, "date": day, "site": site, "off": before, "switch": None, "after": None}
            if sw is not None:
                sw_day = _dt.datetime.fromtimestamp(sw + before * 60, _dt.timezone.utc).date()
                if day > sw_day:
                    row["off"] = after
                elif day == sw_day:
                    row["switch"], row["after"] = sw_local, after
            E.roster.append(row)
    # clock-sync windows
    E.skew = {}
    E.ics = []
    uid = R.randint(10000, 20000)
    for c in E.cams:
        for j in range(130):
            sk = 0 if R.chance(860) else R.choice([-1, 1]) * R.randint(2, 45)
            E.skew[(c, j)] = sk
            start = ts(2026, 9, 10) + 43200 * j
            uid += R.randint(1, 4)
            E.ics.append({"uid": "cs-%d" % uid, "camera": c, "start": start, "end": start + 43200, "skew": sk,
                          "status": "CONFIRMED", "unit": "s"})
            if R.chance(20):
                uid += 1
                E.ics.append({"uid": "cs-%d" % uid, "camera": c, "start": start, "end": start + 43200,
                              "skew": sk + R.choice([-30, 30, 60]), "status": "CANCELLED", "unit": "s"})


# ----------------------------------------------------------------- images
def _local_parts(E, cam, cam_utc):
    off = offset_at(E, cam, cam_utc)
    local = cam_utc + off * 60
    day = _dt.datetime.fromtimestamp(local, _dt.timezone.utc).date()
    site = site_of(E, cam, day)
    before, after, sw, sw_local = SITES[site]
    fold = None
    if sw is not None:
        sw_day = _dt.datetime.fromtimestamp(sw + before * 60, _dt.timezone.utc).date()
        sod = local % 86400
        delta = (before - after) * 60
        if day == sw_day and sw_local - delta <= sod < sw_local:
            fold = 1 if cam_utc >= sw else 0
    return local, fold, site


def _images(E, R):
    n_seq = max(60, int(1250 * E.scale))
    lo, hi = E.id_range
    E.images = {}
    E.seqs = {}
    used = set()
    seq_used = set()
    span_lo, span_hi = ts(2026, 9, 12), ts(2026, 11, 10)
    specials = []
    for k in range(max(6, n_seq // 80)):
        specials.append(("edge", WINDOW_START if k % 2 == 0 else WINDOW_END))
    for k in range(max(6, n_seq // 60)):
        specials.append(("fold", None))
    for s in range(n_seq):
        cam = E.cams[R.below(64)]
        while True:
            sid = "SEQ-%05d" % R.randint(1000, 99999)
            if sid not in seq_used:
                seq_used.add(sid)
                break
        start = span_lo + R.below(span_hi - span_lo - 3600)
        if s < len(specials):
            kind, edge = specials[s]
            if kind == "edge":
                start = edge - R.randint(4, 14)
            else:
                site_cams = [c for c in E.cams if SITES[E.cam[c]["site"]][2] is not None]
                cam = site_cams[R.below(len(site_cams))]
                sw = SITES[E.cam[cam]["site"]][2]
                start = sw + R.choice([-1, 1]) * R.randint(60, 3000) - 10
        nfr = R.randint(6, 14)
        frames = []
        cam_utc = start
        for fi in range(nfr):
            cam_utc += R.randint(1, 3)
            while True:
                n = R.randint(lo, hi)
                if n not in used:
                    used.add(n)
                    break
            iid = img_name(n)
            sk = E.skew.get((cam, window_of(cam_utc)), 0)
            true_t = cam_utc - sk
            local, fold, site = _local_parts(E, cam, cam_utc)
            w, h = E.cam[cam]["res"]
            E.images[iid] = {"id": iid, "seq": sid, "frame": fi + 1, "camera": cam, "cam_utc": cam_utc,
                             "t": true_t, "local": local, "fold": fold, "site": site, "w": w, "h": h,
                             "dw": w, "dh": h, "orient": E.cam[cam]["orient"], "hash": R.u64() | 1,
                             "reenc": False}
            frames.append(iid)
        E.seqs[sid] = {"camera": cam, "frames": frames}
    E.ids = sorted(E.images)
    for iid in E.ids:
        im = E.images[iid]
        if R.chance(10):
            im["reenc"] = True
            im["dw"], im["dh"] = im["w"] // 2, im["h"] // 2
        if R.chance(6):
            im["hash"] = 0
    E.aliases = {}
    E.alias_of = {}
    pool = R.sample(E.ids, min(len(E.ids), max(400, int(6200 * E.scale))))
    for iid in sorted(pool):
        while True:
            a = "LGC-%s%04d" % (R.choice("ABCDEFGHKLMNPRSTUVWXYZ"), R.randint(0, 9999))
            if a not in E.aliases:
                break
        if R.chance(150) and E.alias_of:
            prev = E.alias_of[R.choice(sorted(E.alias_of))]
            E.aliases[a] = prev
            continue
        E.aliases[a] = iid
        E.alias_of[iid] = a
    # chained aliases: some legacy ids point at another legacy id
    keys = sorted(E.aliases)
    for a in keys[: max(20, len(keys) // 40)]:
        tgt = E.aliases[a]
        if tgt.startswith("IMG"):
            while True:
                b = "LGC-Q%04d" % R.randint(0, 9999)
                if b not in E.aliases:
                    break
            E.aliases[b] = tgt
            E.aliases[a] = b


def upright(im):
    w, h = (im["dw"], im["dh"])
    return (h, w) if im["orient"] in (6, 8) else (w, h)


# ----------------------------------------------------------------- scope sources
def _scope_sources(E, R):
    ids = E.ids
    frozen = [i for i in ids if not R.chance(20)]
    E.freeze = []
    for i in frozen:
        E.freeze.append({"image": i, "batch": "FZ-%02d" % (1 + R.below(12))})
    phantom = 0
    while phantom < max(10, len(ids) // 100):
        n = R.randint(100000, 9999999)
        if img_name(n) not in E.images:
            E.freeze.append({"image": img_name(n), "batch": "FZ-%02d" % (1 + R.below(12)), "phantom": True})
            phantom += 1
    E.freeze.sort(key=lambda r: r["image"])
    E.amend = []
    unfrozen = [i for i in ids if i not in set(frozen)]
    for i in unfrozen[: len(unfrozen) // 2]:
        E.amend.append({"image": i, "action": "add", "status": "ratified" if R.chance(700) else "proposed"})
    for i in R.sample(frozen, max(8, len(ids) // 300)):
        E.amend.append({"image": i, "action": "remove", "status": "ratified" if R.chance(600) else "proposed"})
    # observation orientation
    E.exif = {}
    E.corrections = []
    cid = R.randint(30000, 40000)
    for i in ids:
        im = E.images[i]
        val = im["orient"]
        r = R.below(1000)
        need = False
        if r < 40:
            val = R.choice([o for o in (1, 3, 6, 8) if o != im["orient"]])
            need = True
        elif r < 52:
            val = 0
            need = im["orient"] != 1
        E.exif[i] = val
        if need or R.chance(380):
            day = ts(2026, 9, 20) + R.below(50 * 86400)
            if R.chance(120):
                wrong = R.choice([o for o in (1, 3, 6, 8) if o != im["orient"]])
                cid += 1
                E.corrections.append({"id": "OC-%d" % cid, "image": i, "orient": wrong, "status": "confirmed",
                                      "t": day - 86400 * R.randint(1, 9)})
            if R.chance(90):
                cid += 1
                E.corrections.append({"id": "OC-%d" % cid, "image": i,
                                      "orient": R.choice([o for o in (1, 3, 6, 8) if o != im["orient"]]),
                                      "status": "proposed", "t": day + 3600})
            cid += 1
            E.corrections.append({"id": "OC-%d" % cid, "image": i, "orient": im["orient"], "status": "confirmed",
                                  "t": day})
    R.shuffle(E.corrections)
    # integrity audit
    E.integrity = {}
    for i in ids:
        im = E.images[i]
        st = "PASS"
        r = R.below(1000)
        if r < 15:
            st = "FAIL"
        elif r < 25:
            st = "FAIL-RECOVERED"
        if im["reenc"]:
            st = "REENCODED"
        E.integrity[i] = st
    E.geom_zero = set(i for i in ids if E.images[i]["reenc"] and R.chance(500))
    # lifecycle
    E.events = []
    ev = R.randint(500000, 600000)
    for i in ids:
        t0 = E.images[i]["t"] + R.randint(3600, 86400)
        ev += R.randint(1, 3)
        E.events.append({"id": "EV%07d" % ev, "image": i, "type": "ingested", "t": t0})
        r = R.below(1000)
        seq = []
        if r < 20:
            seq = ["withdrawn"]
        elif r < 30:
            seq = ["withdrawn", "restored", "withdrawn"]
        elif r < 45:
            seq = ["withdrawn", "restored"]
        elif r < 52:
            seq = ["late_withdrawn"]
        elif r < 120:
            seq = ["reviewed"]
        t = t0
        for typ in seq:
            t += R.randint(3600, 5 * 86400)
            ev += R.randint(1, 3)
            if typ == "late_withdrawn":
                E.events.append({"id": "EV%07d" % ev, "image": i, "type": "withdrawn", "t": CUTOFF + R.randint(60, 9 * 86400)})
            else:
                E.events.append({"id": "EV%07d" % ev, "image": i, "type": typ, "t": min(t, CUTOFF - 7200)})
        if R.chance(8):
            E.events.append(dict(E.events[-1]))
    E.events.sort(key=lambda e: (e["t"], e["id"]))
    # privacy
    E.privacy_reg = []
    E.privacy_msgs = []
    E.legal_holds = []
    rq = R.randint(70000, 80000)
    for i in ids:
        r = R.below(1000)
        if r < 410:
            rq += R.randint(1, 3)
            st = "HOLD" if r < 12 else "RELEASED"
            E.privacy_reg.append({"id": "PR-%d" % rq, "image": i, "status": st})
            if st == "HOLD" and R.chance(80):
                E.privacy_msgs.append({"image": i, "action": "RELEASE", "t": REGISTER_DATE + R.randint(86400, 20 * 86400), "valid": True})
        elif r < 418:
            E.privacy_msgs.append({"image": i, "action": "TAKEDOWN", "t": REGISTER_DATE + R.randint(3600, 25 * 86400), "valid": True})
        elif r < 421:
            E.privacy_msgs.append({"image": i, "action": "TAKEDOWN", "t": REGISTER_DATE + R.randint(3600, 20 * 86400), "valid": False})
        elif r < 423:
            E.privacy_msgs.append({"image": i, "action": "TAKEDOWN", "t": CUTOFF + R.randint(60, 86400 * 5), "valid": True})
        elif r < 425:
            E.privacy_msgs.append({"image": i, "action": "TAKEDOWN", "t": REGISTER_DATE - R.randint(0, 86400 * 3), "valid": True})
        elif r < 429:
            E.legal_holds.append({"image": i, "status": "LEGAL-HOLD"})
    # pad message volume with routine acknowledgements that change nothing
    for i in R.sample(ids, min(len(ids), max(200, int(5200 * E.scale)))):
        E.privacy_msgs.append({"image": i, "action": "ACK", "t": REGISTER_DATE + R.randint(3600, 25 * 86400), "valid": True})
    E.privacy_msgs.sort(key=lambda m: (m["t"], m["image"]))
    # board decisions
    E.board = []
    E.board_v2 = []
    did = R.randint(1000, 2000)
    for i in ids:
        r = R.below(1000)
        if r < 400:
            did += 1
            dec = "EXCLUDE" if r < 14 else "CONFIRM"
            day = ts(2026, 9, 25) + 86400 * R.below(40)
            E.board.append({"id": "BD-%05d" % did, "image": i, "decision": dec, "t": day})
            if dec == "EXCLUDE" and R.chance(120):
                did += 1
                E.board.append({"id": "BD-%05d" % did, "image": i, "decision": "CONFIRM", "t": day + 86400 * R.randint(1, 9)})
        if R.chance(430):
            did += 1
            dec = "EXCLUDE" if R.chance(30) else "CONFIRM"
            t = ts(2026, 10, 20) + 86400 * R.below(30)
            E.board_v2.append({"id": "BV-%05d" % did, "image": i, "decision": dec, "t": t, "_t16": t > CUTOFF and dec == "EXCLUDE"})


# ----------------------------------------------------------------- leakage
def _flip(h, nbits, R):
    bits = R.sample(list(range(64)), nbits)
    for b in bits:
        h ^= 1 << b
    return h


def _leak_sources(E, R):
    per = max(2500, int(9000 * E.scale))
    shards = {k: [] for k in ["a", "b", "c", "d", "e", "h"]}
    for k in shards:
        for _ in range(per):
            shards[k].append({"h": R.u64(), "purged": R.chance(30), "tag": "v7-train" if not (k == "d" and R.chance(120)) else "v7-calib"})
        shards[k].append({"h": 0, "purged": False, "tag": "v7-train"})
    legacy = [{"h": R.u64(), "purged": False, "tag": "v6-core" if R.chance(750) else "v6-synthetic"} for _ in range(per)]
    fdedup = []
    for _ in range(max(1500, int(5200 * E.scale))):
        src = R.choice(["a", "b", "c", "d", "e", "h", "g", "g"])
        fdedup.append({"h": R.u64(), "src": src, "purged": False})
    E.waivers = []
    wid = R.randint(9000, 9999)
    for i in E.ids:
        im = E.images[i]
        if im["hash"] == 0:
            continue
        r = R.below(1000)
        h = im["hash"]
        tgt = None
        if r < 20:
            tgt = ("v7", h, "plain")
        elif r < 45:
            tgt = ("v7", _flip(h, R.randint(1, 4), R), "plain")
        elif r < 55:
            tgt = ("v7", _flip(h, 4, R), "plain")
        elif r < 65:
            tgt = ("v7", _flip(h, 5, R), "plain")
        elif r < 72:
            tgt = ("v7", h, "purged")
        elif r < 75:
            tgt = ("d", h, "calib")
        elif r < 80:
            tgt = ("legacy", _flip(h, R.randint(0, 3), R), "v6-core")
        elif r < 83:
            tgt = ("legacy", h, "v6-synthetic-x")
        elif r < 90:
            hh = _flip(h, R.randint(0, 4), R)
            tgt = ("v7", hh, "plain")
            wid += 1
            st = R.choice(["granted", "granted", "denied", "expired"])
            E.waivers.append({"id": "WV-%05d" % wid, "image": i, "h": hh, "status": st,
                              "decided": ts(2026, 10, 1) + R.below(30 * 86400),
                              "expires": (ts(2026, 11, 1) if st == "expired" else None)})
        elif r < 94:
            tgt = ("f", _flip(h, R.randint(0, 2), R), "g")
        elif r < 97:
            tgt = ("f", h, "stale")
        if tgt is None:
            continue
        where, hh, mode = tgt
        if where == "v7":
            shards[R.choice(sorted(shards))].append({"h": hh, "purged": mode == "purged", "tag": "v7-train"})
        elif where == "d":
            shards["d"].append({"h": hh, "purged": False, "tag": "v7-calib"})
        elif where == "legacy":
            if mode == "v6-synthetic-x":
                legacy.append({"h": hh, "purged": False, "tag": "v6-synthetic", "_t16": True})
            else:
                legacy.append({"h": hh, "purged": False, "tag": mode})
        else:
            fdedup.append({"h": hh, "src": "g" if mode == "g" else R.choice(["a", "b", "e"]), "purged": False, "_t16": mode != "g"})
    # routine waivers that grant nothing relevant
    for i in R.sample(E.ids, min(len(E.ids), max(300, int(5100 * E.scale)))):
        wid += 1
        E.waivers.append({"id": "WV-%05d" % wid, "image": i, "h": R.u64(), "status": R.choice(["granted", "denied"]),
                          "decided": ts(2026, 9, 20) + R.below(40 * 86400), "expires": None})
    for k in shards:
        R.shuffle(shards[k])
    R.shuffle(legacy)
    R.shuffle(fdedup)
    E.shards, E.legacy, E.fdedup = shards, legacy, fdedup
    # training sequence register
    E.trainseq = []
    seqs = sorted(E.seqs)
    leakseq = set(R.sample(seqs, max(3, len(seqs) * 3 // 100)))
    for s in seqs:
        if s in leakseq:
            E.trainseq.append({"seq": s, "status": "trained", "index": R.choice(["v7-train", "v6-core"])})
        elif R.chance(20):
            E.trainseq.append({"seq": s, "status": "held-out", "index": "v7-train"})
        elif R.chance(15):
            E.trainseq.append({"seq": s, "status": "trained", "index": "v5-archive"})
    used = set(E.seqs)
    while len(E.trainseq) < max(1200, int(6100 * E.scale)):
        s = "SEQ-%05d" % R.randint(1000, 99999)
        if s in used:
            continue
        used.add(s)
        E.trainseq.append({"seq": s, "status": R.choice(["trained", "trained", "held-out"]),
                           "index": R.choice(["v7-train", "v6-core", "v5-archive"])})
    R.shuffle(E.trainseq)

# ----------------------------------------------------------------- ground truth world
CLASS_WEIGHTS = [30, 8, 3, 4, 4, 20, 6, 3, 4, 6, 7, 5]
# Fresh-estate fixture (scale below 1 only; the shipped estate is built at scale 1 and is unchanged):
# no object of this class exists, so its gt_count is 0, its AP columns are NA and the means skip it.
EVAL_NO_GT_CLASS = "bus"
EVAL_CLASS_WEIGHTS = [0 if c == EVAL_NO_GT_CLASS else w for c, w in zip(CLASSES, CLASS_WEIGHTS)]
CLASS_SIZE = {"pedestrian": (40, 420, 0.42), "cyclist": (50, 380, 0.7), "wheelchair_user": (50, 300, 0.8),
              "stroller": (40, 220, 0.9), "dog": (20, 160, 1.3), "car": (60, 600, 1.8), "truck": (90, 800, 1.6),
              "bus": (120, 900, 2.0), "motorcycle": (40, 300, 1.2), "parked_bicycle": (30, 200, 1.5),
              "traffic_cone": (14, 120, 0.6), "bollard": (16, 160, 0.35)}


def _wchoice(R, items, weights):
    tot = sum(weights)
    x = R.below(tot)
    for it, w in zip(items, weights):
        if x < w:
            return it
        x -= w
    return items[-1]


def _rand_box(R, cls, W, H):
    lo, hi, ar = CLASS_SIZE[cls]
    hgt = min(H - 2, R.randint(lo, hi))
    wid = max(4, min(W - 2, int(hgt * ar * (80 + R.below(41)) / 100)))
    x1 = R.randint(0, W - wid)
    y1 = R.randint(0, H - hgt)
    return (x1, y1, x1 + wid, y1 + hgt)


def _jitter(R, box, W, H, amt):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    dx = lambda: R.randint(-max(1, w * amt // 100), max(1, w * amt // 100))
    dy = lambda: R.randint(-max(1, h * amt // 100), max(1, h * amt // 100))
    nx1, ny1, nx2, ny2 = x1 + dx(), y1 + dy(), x2 + dx(), y2 + dy()
    nx1, nx2 = max(0, min(nx1, W - 2)), max(0, min(nx2, W))
    ny1, ny2 = max(0, min(ny1, H - 2)), max(0, min(ny2, H))
    if nx2 <= nx1 + 1:
        nx2 = min(W, nx1 + 2)
    if ny2 <= ny1 + 1:
        ny2 = min(H, ny1 + 2)
    return (nx1, ny1, nx2, ny2)


def _gt_world(E, R):
    E.objects = {}
    oid = 0
    weights = CLASS_WEIGHTS if E.scale >= 1 else EVAL_CLASS_WEIGHTS
    for i in E.ids:
        im = E.images[i]
        W, H = upright(im)
        n = R.choice([0, 1, 2, 3, 4, 5, 5, 6, 6, 7, 7, 8, 9, 10, 11])
        objs = []
        for _ in range(n):
            cls = _wchoice(R, CLASSES, weights)
            box = _rand_box(R, cls, W, H)
            r = R.below(1000)
            disp, crowd = "eval", 0
            if r < 40:
                s = R.randint(4, 9)
                box = (box[0], box[1], box[0] + s, box[1] + max(2, 63 // s))
            elif r < 46:
                box = (box[0], box[1], min(W, box[0] + 8), min(H, box[1] + 8))
                if box[2] - box[0] != 8 or box[3] - box[1] != 8:
                    box = (0, 0, 8, 8)
            elif r < 51:
                box = (R.randint(0, 20), R.randint(0, 20), W - R.randint(0, 20), H - R.randint(0, 20))
            elif r < 66:
                disp = "ignore"
            elif r < 76:
                disp = "drop"
            oid += 1
            objs.append({"oid": oid, "cls": cls, "box": box, "crowd": crowd, "disp": disp})
        if R.chance(30):
            oid += 1
            x1 = R.randint(0, W // 2)
            y1 = R.randint(0, H // 2)
            objs.append({"oid": oid, "cls": "pedestrian", "box": (x1, y1, min(W, x1 + W // 3), min(H, y1 + H // 3)),
                         "crowd": 1, "disp": "eval"})
        E.objects[i] = objs
    # vendor assignment
    E.vendor = {}
    for i in E.ids:
        r = R.below(100)
        E.vendor[i] = "NL" if r < 40 else ("KS" if r < 80 else "OB")


def _mapping_tables(E, R):
    # NL crosswalk
    E.nl_x = {}
    nl_projects = ["NLP-%04d" % k for k in range(1, max(60, int(420 * min(1, E.scale * 2))) + 1)]
    french = set(R.sample(nl_projects, max(4, len(nl_projects) // 12)))
    for p in nl_projects:
        for cls in CLASSES:
            for lab in NL_LABELS[cls]:
                tgt = cls
                if lab == "van" and R.chance(120):
                    tgt = "truck"
                if lab == "post" and R.chance(150):
                    tgt = "traffic_cone"
                E.nl_x[(p, lab)] = (tgt, "eval")
        E.nl_x[(p, "unknown_vru")] = ("pedestrian", "ignore")
        E.nl_x[(p, "e_scooter")] = ("e_scooter", "drop")
        if p in french:
            E.nl_x[(p, "pi\u00e9ton")] = ("pedestrian", "eval")
            E.nl_x[(p, "v\u00e9lo")] = ("parked_bicycle", "eval")
    E.nl_projects = nl_projects
    E.nl_french = french
    # KS codebook with renumbering
    E.ks_book = []
    ks_projects = ["KSP-%03d" % k for k in range(1, max(40, int(300 * min(1, E.scale * 2))) + 1)]
    names = CLASSES + ["unknown", "e_scooter"]
    for p in ks_projects:
        perm = list(range(1, len(names) + 1))
        R.shuffle(perm)
        renum = R.chance(320)
        cut = ts(2026, 9, 20) + 86400 * R.below(40)
        for nm, code in zip(names, perm):
            cls, disp = (nm, "eval")
            if nm == "unknown":
                cls, disp = "pedestrian", "ignore"
            if nm == "e_scooter":
                disp = "drop"
            E.ks_book.append({"project": p, "code": code, "cls": cls, "disp": disp, "from": ts(2026, 1, 1),
                              "to": cut if renum else None})
        if renum:
            perm2 = list(perm)
            R.shuffle(perm2)
            for nm, code in zip(names, perm2):
                cls, disp = (nm, "eval")
                if nm == "unknown":
                    cls, disp = "pedestrian", "ignore"
                if nm == "e_scooter":
                    disp = "drop"
                E.ks_book.append({"project": p, "code": code, "cls": cls, "disp": disp, "from": cut, "to": None})
    E.ks_projects = ks_projects
    # OB aliases
    E.ob_x = {}
    ob_projects = ["OBP-%04d" % k for k in range(1, max(60, int(400 * min(1, E.scale * 2))) + 1)]
    for p in ob_projects:
        for cls in CLASSES:
            for al in OB_ALIASES[cls]:
                tgt = cls
                if al == "Post" and R.chance(200):
                    tgt = "traffic_cone"
                E.ob_x[(p, al)] = (tgt, "eval")
        E.ob_x[(p, "Unknown")] = ("pedestrian", "ignore")
        E.ob_x[(p, "EScooter")] = ("e_scooter", "drop")
    E.ob_projects = ob_projects


def _label_for(E, R, vendor, project, cls, disp, t):
    """Pick a vendor label in `project` that maps to (cls, disp); None when the project has none."""
    if vendor in ("NL", "OB"):
        idx = E.label_index[vendor]
        opts = idx.get((project, (cls if disp != "drop" else "e_scooter", disp)), [])
        return R.choice(opts) if opts else None
    for row in E.ks_index.get(project, []):
        if row["from"] <= t and (row["to"] is None or t < row["to"]):
            want = (cls if disp != "drop" else "e_scooter", disp)
            if (row["cls"], row["disp"]) == want:
                return row["code"]
    return None


def _perturb_box(R, box, W, H):
    b = _jitter(R, box, W, H, 25)
    if b == box:
        b = (box[0], box[1], min(W, box[2] + 3), box[3])
        if b == box:
            b = (max(0, box[0] - 3), box[1], box[2], box[3])
    return b


def _annotation_sources(E, R):
    _mapping_tables(E, R)
    E.label_index = {"NL": {}, "OB": {}}
    for vend, table in (("NL", E.nl_x), ("OB", E.ob_x)):
        for (p, lab), v in table.items():
            E.label_index[vend].setdefault((p, v), []).append(lab)
        for v in E.label_index[vend].values():
            v.sort()
    E.ks_index = {}
    for row in E.ks_book:
        E.ks_index.setdefault(row["project"], []).append(row)
    E.anns = []          # vendor annotation records, all vendors, before file assignment
    E.qa = []            # portal decisions
    E.qa_export = []     # export decisions (decoy)
    E.errata = []
    E.campaign_items, E.campaign_boxes, E.campaign_status = [], [], []
    counters = {"NL": R.randint(100000, 200000), "KS": R.randint(2000000, 3000000), "OB": R.randint(300000, 400000)}
    unlabeled = set(i for i in E.ids if R.chance(10))
    E.intent_unlabeled = unlabeled
    proj_of = {}
    t_ann = {}
    camp_imgs = set(R.sample(E.ids, len(E.ids) * 41 // 100))
    camp_state = {}
    for i in sorted(camp_imgs):
        r = R.below(1000)
        camp_state[i] = "approved" if r < 85 else ("late" if r < 95 else ("rejected" if r < 400 else "pending"))
    E.camp_state = camp_state

    def new_ann(v):
        counters[v] += R.randint(1, 4)
        return counters[v]

    def emit(v, i, cls, disp, box, crowd, project, status="live", rev=1, t=None, extra=None):
        n = new_ann(v)
        rec = {"vendor": v, "num": n, "ann": "%s-%07d" % (v, n), "image": i, "cls": cls, "disp": disp,
               "box": box, "crowd": crowd, "project": project, "rev": rev, "status": status,
               "t": t if t is not None else E.images[i]["t"] + R.randint(86400, 30 * 86400)}
        if extra:
            rec.update(extra)
        lab = _label_for(E, R, v, project, cls, disp, rec["t"])
        if lab is None:
            return None
        rec["label"] = lab
        E.anns.append(rec)
        return rec

    for i in E.ids:
        im = E.images[i]
        W, H = upright(im)
        v = E.vendor[i]
        projects = {"NL": E.nl_projects, "KS": E.ks_projects, "OB": E.ob_projects}
        project = R.choice(projects[v])
        objs = E.objects[i]
        if i in camp_imgs:
            item = "CI-%06d" % (100000 + len(E.campaign_items))
            E.campaign_items.append({"item": item, "image": i, "opened": ts(2026, 10, 1) + R.below(25 * 86400)})
            st = camp_state[i]
            base = ts(2026, 10, 20) + R.below(20 * 86400)
            hist = [("pending", base)]
            if st == "approved":
                hist.append(("approved", base + R.randint(3600, 86400 * 5)))
                if R.chance(80):
                    hist[-1] = ("approved", CUTOFF)
            elif st == "late":
                hist.append(("approved", CUTOFF + R.randint(1, 86400 * 4)))
            elif st == "rejected":
                hist.append(("approved", base + 7200))
                hist.append(("rejected", base + 86400 * 2))
            for s, t in hist:
                E.campaign_status.append({"item": item, "status": s, "t": t})
            for o in objs:
                if o["disp"] == "drop":
                    continue
                box = o["box"] if st == "approved" else _perturb_box(R, o["box"], W, H)
                E.campaign_boxes.append({"box_id": "RC-%07d" % (len(E.campaign_boxes) + 500000), "item": item,
                                         "cls": o["cls"], "box": box, "crowd": 1 if (o["crowd"] or o["disp"] == "ignore") else 0})
        if i in unlabeled:
            if R.chance(500):
                ov = R.choice([x for x in ("NL", "KS", "OB") if x != v])
                for o in objs[:3]:
                    emit(ov, i, o["cls"], o["disp"], _perturb_box(R, o["box"], W, H), o["crowd"], R.choice(projects[ov]))
            continue
        camp_ok = i in camp_imgs and camp_state[i] == "approved"
        for o in objs:
            box, cls = o["box"], o["cls"]
            if camp_ok and R.chance(300):
                box = _perturb_box(R, box, W, H)
            r = R.below(1000)
            if r < 60 and not camp_ok:
                # older revisions carry other geometry
                rec = emit(v, i, cls, o["disp"], _perturb_box(R, box, W, H), o["crowd"], project, rev=1)
                if rec is None:
                    continue
                for k in range(2, R.randint(2, 3) + 1):
                    nr = dict(rec)
                    nr["rev"] = k
                    nr["box"] = _perturb_box(R, box, W, H)
                    nr["t"] = rec["t"] + 3600 * k
                    E.anns.append(nr)
                nr["box"] = box
                if R.chance(250):
                    rj = dict(nr)
                    rj["rev"] = nr["rev"] + 1
                    rj["box"] = _perturb_box(R, box, W, H)
                    rj["t"] = nr["t"] + 3600
                    E.anns.append(rj)
                    if R.chance(500):
                        E.qa.append({"ann": rj["ann"], "rev": rj["rev"], "decision": "rejected", "t": QA_SNAPSHOT - R.randint(3600, 86400 * 9)})
                    else:
                        E.qa_export.append({"ann": rj["ann"], "rev": rj["rev"], "decision": "rejected", "t": QA_SNAPSHOT + R.randint(3600, 86400 * 9), "state": "final"})
                continue
            if r < 160 and not camp_ok:
                # errata-corrected annotations: the vendor row carries the pre-errata value
                kind = R.choice(["RECLASS", "REBOX", "REBOX", "LATE"])
                if kind == "RECLASS":
                    alt = R.choice([c for c in CLASSES if c != cls])
                    rec = emit(v, i, alt, o["disp"] if o["disp"] != "drop" else "eval", box, o["crowd"], project)
                    if rec is None:
                        continue
                    if o["disp"] == "drop":
                        E.anns.remove(rec)
                        continue
                    E.errata.append({"ann": rec["ann"], "action": "RECLASS", "value": cls, "eff": ts(2026, 10, 1) + 86400 * R.below(40)})
                    if R.chance(200):
                        E.errata.insert(len(E.errata) - 1, {"ann": rec["ann"], "action": "RECLASS", "value": R.choice(CLASSES), "eff": ts(2026, 9, 25)})
                elif kind == "REBOX":
                    rec = emit(v, i, cls, o["disp"], _perturb_box(R, box, W, H), o["crowd"], project)
                    if rec is None:
                        continue
                    E.errata.append({"ann": rec["ann"], "action": "REBOX", "value": box, "eff": ts(2026, 10, 1) + 86400 * R.below(42)})
                else:
                    rec = emit(v, i, cls, o["disp"], box, o["crowd"], project)
                    if rec is None:
                        continue
                    E.errata.append({"ann": rec["ann"], "action": "REBOX", "value": _perturb_box(R, box, W, H), "eff": CUTOFF + 86400 * R.randint(1, 6)})
                continue
            rec = emit(v, i, cls, o["disp"], box, o["crowd"], project)
            if rec is None:
                continue
            if r < 170:
                # resurrected: an older deleted revision precedes the live one
                old = dict(rec)
                old["rev"] = 1
                old["status"] = "deleted"
                rec["rev"] = 2
                E.anns.append(old)
        # phantom annotations: deleted at their latest revision or voided by errata
        if not camp_ok and R.chance(150):
            cls = _wchoice(R, CLASSES, CLASS_WEIGHTS)
            b = _rand_box(R, cls, W, H)
            rec = emit(v, i, cls, "eval", b, 0, project, status="deleted", rev=2)
            if rec is not None:
                live = dict(rec)
                live["rev"], live["status"] = 1, "live"
                E.anns.append(live)
        if not camp_ok and R.chance(90):
            cls = _wchoice(R, CLASSES, CLASS_WEIGHTS)
            rec = emit(v, i, cls, "eval", _rand_box(R, cls, W, H), 0, project)
            if rec is not None:
                E.errata.append({"ann": rec["ann"], "action": "VOID", "value": "", "eff": ts(2026, 10, 3) + 86400 * R.below(30)})
        # cross-vendor pilot annotations
        if R.chance(80):
            ov = R.choice([x for x in ("NL", "KS", "OB") if x != v])
            for o in objs[:4]:
                emit(ov, i, o["cls"], o["disp"], _perturb_box(R, o["box"], W, H), o["crowd"], R.choice(projects[ov]))
    # QA portal: routine accept decisions
    pool = [a for a in E.anns]
    for a in R.sample(pool, min(len(pool), max(600, int(5600 * E.scale)))):
        E.qa.append({"ann": a["ann"], "rev": a["rev"], "decision": "accepted", "t": QA_SNAPSHOT - R.randint(3600, 86400 * 30)})
    for a in R.sample(pool, min(len(pool), max(1000, int(10400 * E.scale)))):
        st = "draft" if R.chance(300) else "final"
        dec = "rejected" if st == "draft" else "accepted"
        t = QA_SNAPSHOT + R.randint(3600, 86400 * 10) if R.chance(800) else QA_SNAPSHOT - R.randint(3600, 86400 * 10)
        if st == "final" and t <= QA_SNAPSHOT:
            dec = "rejected"
        E.qa_export.append({"ann": a["ann"], "rev": a["rev"], "decision": dec, "t": t, "state": st})
    # errata ids
    R.shuffle(E.errata)
    E.errata.sort(key=lambda e: e["eff"])
    for k, e in enumerate(E.errata):
        e["id"] = "ER-%06d" % (10000 + k)
    # batches
    E.batches = {}
    E.anns.sort(key=lambda a: (a["vendor"], a["image"], a["num"], a["rev"]))
    cur = None
    bid = {"NL": R.randint(1000, 5000), "KS": R.randint(1000, 5000), "OB": R.randint(1000, 5000)}
    left = 0
    for a in E.anns:
        key = (a["vendor"], a["image"])
        if cur is None or cur[0] != a["vendor"] or (left <= 0 and key != last_key):
            bid[a["vendor"]] += R.randint(1, 3)
            pref = {"NL": "NB", "KS": "KB", "OB": "OB"}[a["vendor"]]
            cur = (a["vendor"], "%s-%05d" % (pref, bid[a["vendor"]]))
            left = R.randint(3, 7)
            dfmt = {"NL": ("xywh", "stored"), "KS": ("cxcywh_norm", "upright"), "OB": ("xyxy_inclusive", "upright")}[a["vendor"]]
            if R.chance(100):
                dfmt = {"NL": ("xyxy", "upright"), "KS": ("xyxy", "upright"), "OB": ("xywh", "stored")}[a["vendor"]]
            rcv = CUTOFF - R.randint(3600, 86400 * 20)
            r = R.below(1000)
            if r < 4:
                rcv = CUTOFF + R.randint(1, 86400 * 3)
            elif r < 6:
                rcv = CUTOFF
            E.batches[cur[1]] = {"vendor": a["vendor"], "fmt": dfmt[0], "frame": dfmt[1], "received": rcv,
                                 "resub": a["vendor"] in ("KS", "OB") and R.chance(25), "errata": None}
        a["batch"] = cur[1]
        last_key = key
        left -= 1
    # convention errata: the appendix row is wrong for these batches, the errata page says so
    for b in R.sample(sorted(E.batches), max(10, len(E.batches) // 400)):
        bb = E.batches[b]
        alt = {"xywh": "xyxy", "xyxy": "xywh", "cxcywh_norm": "xyxy", "xyxy_inclusive": "xyxy"}[bb["fmt"]]
        bb["errata"] = bb["fmt"]
        bb["fmt_table"] = alt
    # file placement for vendor records (one batch lives in one file)
    nl_files = ["nl_boxes_batch01.csv", "nl_boxes_batch02.csv", "nl_boxes_batch03.tsv", "nl_boxes_batch04.csv",
                "nl_boxes_q3_extra.xlsx#north", "nl_boxes_q3_extra.xlsx#south"]
    ks_files = ["ks_boxes_part1.jsonl", "ks_boxes_part2.jsonl", "ks_boxes_part3.json", "ks_boxes_part4.parquet",
                "ks_boxes_part5.json", "ks_boxes_part6.csv"]
    E.batch_file = {}
    for b in sorted(E.batches):
        v = E.batches[b]["vendor"]
        if v == "NL":
            E.batch_file[b] = nl_files[R.below(6)]
        elif v == "KS":
            E.batch_file[b] = ks_files[R.below(6)]
        else:
            E.batch_file[b] = "ob_boxes_east.xml" if R.chance(500) else "ob_boxes_west.xml"
    # resubmissions (decoys): accepted batches carry the true records, the originals are damaged
    E.resub = {"KS": [], "OB": []}
    by_batch = {}
    for a in E.anns:
        by_batch.setdefault(a["batch"], []).append(a)
    for b in sorted(E.batches):
        bb = E.batches[b]
        if bb["vendor"] not in ("KS", "OB"):
            continue
        if bb["resub"]:
            for a in by_batch[b]:
                E.resub[bb["vendor"]].append(dict(a))
                W, H = upright(E.images[a["image"]])
                a["box"] = _perturb_box(R, a["box"], W, H)
        elif R.chance(230 if bb["vendor"] == "KS" else 420):
            for a in by_batch[b]:
                na = dict(a)
                W, H = upright(E.images[a["image"]])
                if R.chance(300):
                    na["box"] = _perturb_box(R, a["box"], W, H)
                E.resub[bb["vendor"]].append(na)
    # NL batch02 truncation: missing tail partitions are re-extracted (decoy file)
    E.receipts = {b: E.batches[b]["received"] for b in E.batches}

# ----------------------------------------------------------------- inference runs
RUN_QUALITY = {
    "R1": {"recall": 760, "jit": 20, "fp": 3, "dup": 300, "lo": 300, "weak": {}},
    "R2": {"recall": 840, "jit": 14, "fp": 3, "dup": 280, "lo": 330, "weak": {"stroller": 520}},
    "R3": {"recall": 850, "jit": 12, "fp": 2, "dup": 260, "lo": 340, "weak": {}},
    "R4": {"recall": 880, "jit": 11, "fp": 2, "dup": 250, "lo": 350, "weak": {"wheelchair_user": 450}},
    "R5": {"recall": 700, "jit": 25, "fp": 4, "dup": 300, "lo": 250, "weak": {}},
}
# Fresh-estate run quality (scale below 1 only). R2 is incumbent-like and R4 loses its weak class, so
# R2, R3 and R4 can all be promoted; jit and lo draw no extra random numbers, so each run's values
# tune that run alone. _fx_release_gate then plants EVAL_GATE_FPS (run, class, raw score in 1/1000).
EVAL_RUN_QUALITY = dict(RUN_QUALITY,
                        R2={"recall": 780, "jit": 20, "fp": 3, "dup": 300, "lo": 420, "weak": {}},
                        R3={"recall": 850, "jit": 12, "fp": 2, "dup": 260, "lo": 340, "weak": {"cyclist": 720}},
                        R4={"recall": 850, "jit": 13, "fp": 2, "dup": 250, "lo": 470, "weak": {}})
EVAL_GATE_FPS = (("R2", "motorcycle", 956), ("R2", "parked_bicycle", 999), ("R2", "parked_bicycle", 850),
                 ("R3", "cyclist", 999), ("R3", "cyclist", 756), ("R3", "cyclist", 360),
                 ("R4", "bollard", 844))


def run_cfg(run):
    for r in RUNS:
        if r[0] == run:
            return r
    return None


def letterbox(S, W, H):
    scale = Fraction(S, max(W, H))
    nw, nh = round_half_even_int(W * scale), round_half_even_int(H * scale)
    return scale, (S - nw) // 2, (S - nh) // 2


def knots_x():
    return [Fraction(round_half_even_int(Fraction(k * 10 ** 6, 511)), 10 ** 6) for k in range(512)]


KNOT_X = None


def calibrate(knots, s):
    xs = KNOT_X
    lo, hi = 0, 510
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if xs[mid] <= s:
            lo = mid
        else:
            hi = mid - 1
    i = lo
    y0, y1 = knots[i], knots[i + 1]
    return y0 + (y1 - y0) * (s - xs[i]) / (xs[i + 1] - xs[i])


def _make_knots(R, run, cls):
    ys = [0]
    total = 0
    incs = []
    for k in range(511):
        if R.chance(120):
            incs.append(0)
        else:
            incs.append(R.randint(1, 6))
    scale_to = 980000 + R.below(19000)
    s = sum(incs) or 1
    acc = 0
    out = [Fraction(0)]
    run_sum = 0
    for k, inc in enumerate(incs):
        run_sum += inc
        acc = run_sum * scale_to // s
        out.append(Fraction(acc, 10 ** 6))
    for k in range(1, 512):
        if out[k] < out[k - 1]:
            out[k] = out[k - 1]
    return out


def _run_sources(E, R):
    global KNOT_X
    KNOT_X = knots_x()
    E.labelmap = {}
    for run, model, S, thr, nms, md, status, idx in RUNS:
        if run == "R1":
            labs = list(R1_LABELS)
        else:
            labs = CLASSES + ["e_scooter"]
            R.shuffle(labs)
        E.labelmap[run] = labs
    # node assignment per (run, sequence)
    E.assign, E.assign_mirror = {}, {}
    E.late_seqs = set(R.sample(sorted(E.seqs), max(3, len(E.seqs) // 50)))
    for run in [r[0] for r in RUNS]:
        for s in sorted(E.seqs):
            node = NODES[R.below(6)]
            E.assign[(run, s)] = node
            m = node if not R.chance(50) else NODES[R.below(6)]
            E.assign_mirror[(run, s)] = node if s in E.late_seqs else m
    # calibration maps
    E.calib = {}
    for run in REVIEW_RUNS + ["R5"]:
        for cls in CLASSES:
            E.calib[(run, cls)] = _make_knots(R, run, cls)
    E.deferred = sorted(R.sample(CLASSES, 2))
    E.calib_reissue = {}
    for cls in CLASSES:
        if cls in E.deferred:
            E.calib_reissue[cls] = E.calib[("R3", cls)]
        else:
            alt = list(E.calib[("R3", cls)])
            for k in range(1, 512, 37):
                alt[k] = min(alt[k + 1] if k + 1 < 512 else alt[k], alt[k] + Fraction(1, 10 ** 6) * R.randint(1, 3))
            E.calib_reissue[cls] = alt
    # detections
    E.dets = {}            # (run, image) -> list of det dicts (true resolved raw records)
    E.det_counter = {r[0]: R.randint(10 ** 8, 3 * 10 ** 8) for r in RUNS}
    E.prep = {}            # (run, image) -> (scale, padx, pady)
    quality = RUN_QUALITY if E.scale >= 1 else EVAL_RUN_QUALITY
    for i in E.ids:
        im = E.images[i]
        W, H = upright(im)
        objs = E.objects[i]
        for run, model, S, thr, nms, md, status, idx in RUNS:
            q = quality[run]
            E.prep[(run, i)] = letterbox(S, W, H)
            out = []

            def add(cls_label, box, score):
                E.det_counter[run] += R.randint(1, 5)
                out.append({"det": E.det_counter[run], "run": run, "image": i, "label": cls_label,
                            "box": box, "score": max(1, min(999, score))})

            for o in objs:
                if o["crowd"]:
                    for _ in range(R.randint(0, 3)):
                        b = _jitter(R, (o["box"][0] + 10, o["box"][1] + 10, o["box"][0] + 60, o["box"][1] + 140), W, H, 10)
                        add(_model_label(run, "pedestrian"), b, R.randint(200, 900))
                    continue
                if o["disp"] == "drop":
                    if R.chance(500):
                        add(_model_label(run, None), _jitter(R, o["box"], W, H, q["jit"]), R.randint(100, 900))
                    continue
                rec = q["weak"].get(o["cls"], q["recall"])
                if not R.chance(rec):
                    continue
                b = _jitter(R, o["box"], W, H, q["jit"])
                cls = o["cls"] if not R.chance(25) else _wchoice(R, CLASSES, CLASS_WEIGHTS)
                sc = R.randint(q["lo"], 999)
                add(_model_label(run, cls), b, sc)
                if R.chance(q["dup"]):
                    add(_model_label(run, cls), _jitter(R, b, W, H, 6), max(1, sc - R.randint(1, 200)))
                if R.chance(20):
                    add(_model_label(run, cls), b, sc)
            for _ in range(R.below(q["fp"] + 2)):
                cls = _wchoice(R, CLASSES, CLASS_WEIGHTS)
                add(_model_label(run, cls if not R.chance(40) else None), _rand_box(R, cls, W, H), R.randint(1, 650))
            if R.chance(20):
                b = out[-1]["box"] if out else _rand_box(R, "car", W, H)
                ext = R.randint(1, 9)
                out.append({"det": E.det_counter[run] + 1, "run": run, "image": i, "label": out[-1]["label"] if out else _model_label(run, "car"),
                            "box": (b[0] - ext, b[1], b[2], b[3]), "score": R.randint(300, 900)})
                E.det_counter[run] += 2
            E.dets[(run, i)] = out
    # keep every calibrated score clear of its run threshold
    for (run, i), lst in E.dets.items():
        if run not in REVIEW_RUNS:
            continue
        thr = Fraction(run_cfg(run)[3])
        for d in lst:
            cls = _canon_label(run, d["label"])
            if cls is None:
                continue
            for _ in range(5):
                c = calibrate(_calib_for(E, run, cls), Fraction(d["score"], 1000))
                if c != thr and abs(c - thr) < Fraction(1, 10 ** 7):
                    d["score"] += 1
                else:
                    break
    # reruns, quarantine, spill-over, misfiled rows
    E.reruns = []
    E.quarantine = []
    E.rerun_rows = {}     # (run, image) -> (store, rows, prep)
    E.failed_rerun_rows = {}
    E.orig_override = {}  # (run, image) -> rows actually written to the original node (when not authoritative)
    E.spill = {}
    E.prep_missing = set()
    E.prep_retry = {}
    keys = sorted(k for k in E.dets if k[0] in REVIEW_RUNS)
    for key in keys:
        run, i = key
        r = R.below(1000)
        seq = E.images[i]["seq"]
        node = E.assign[(run, seq)]
        if r < 18:
            E.quarantine.append({"run": run, "node": node, "image": i})
            bad = [dict(d, score=999) for d in E.dets[key]]
            E.orig_override[key] = bad
            if R.chance(700):
                store = "n6"
                if run == "R3" and node == "n2" and R.chance(600):
                    store = "n2-replay"
                elif R.chance(250):
                    store = "n6-replica"
                E.reruns.append({"run": run, "image": i, "store": store, "status": "completed"})
                E.rerun_rows[key] = store
            else:
                E.dets[key] = []
                E.reruns.append({"run": run, "image": i, "store": "n6", "status": R.choice(["failed", "abandoned"])})
                if R.chance(500):
                    E.failed_rerun_rows[key] = [dict(d, score=max(1, d["score"] - 50)) for d in bad]
        elif r < 40:
            store = "n6" if not (run == "R3" and node == "n2" and R.chance(500)) else "n2-replay"
            E.reruns.append({"run": run, "image": i, "store": store, "status": "completed"})
            E.rerun_rows[key] = store
            orig = [dict(d) for d in E.dets[key]]
            if orig:
                orig.pop(R.below(len(orig)))
            E.orig_override[key] = orig
        elif r < 120:
            E.reruns.append({"run": run, "image": i, "store": R.choice(["n6", "n6-replica"]), "status": R.choice(["failed", "abandoned", "queued"])})
            E.failed_rerun_rows[key] = [dict(d, score=max(1, d["score"] - 30)) for d in E.dets[key]]
        elif r < 128:
            other = R.choice([n for n in NODES if n != node])
            E.spill[key] = (other, [dict(d, det=d["det"] + 350000000, score=max(1, d["score"] - 11)) for d in E.dets[key]])
        elif r < 131 and key not in E.rerun_rows:
            E.prep_missing.add(key)
            E.orig_override[key] = E.dets[key]
            E.dets[key] = []
        if key in E.rerun_rows:
            # rerun rows get fresh detection ids
            fresh = []
            for d in E.dets[key]:
                E.det_counter[run] += R.randint(1, 5)
                fresh.append(dict(d, det=E.det_counter[run]))
            E.dets[key] = fresh
        if R.chance(50) and key not in E.prep_missing:
            E.prep_retry[key] = R.randint(1, 2)
    E.misfiled = set(k for k in keys if k[0] == "R4" and E.assign[("R4", E.images[k[1]]["seq"])] != "n7" and R.chance(5))


def _model_label(run, cls):
    if run == "R1":
        if cls is None:
            return "e_scooter"
        inv = {"pedestrian": "person", "wheelchair_user": "person_wheelchair", "stroller": "person_stroller",
               "cyclist": "bike_rider", "dog": "dog", "car": "car", "truck": "truck", "bus": "bus",
               "motorcycle": "motorbike", "parked_bicycle": "bike", "traffic_cone": "cone", "bollard": "bollard"}
        return inv[cls]
    return cls if cls is not None else "e_scooter"


def _canon_label(run, label):
    if run == "R1":
        return R1_MODEL_XWALK.get(label)
    return None if label == "e_scooter" else label


def _calib_for(E, run, cls):
    return E.calib[(run, cls)]

# ----------------------------------------------------------------- file assembly
TRAIN_SHARDS = {"a": ("train_hash_index_a.parquet", "parquet"), "b": ("train_hash_index_b.csv", "csv"),
                "c": ("train_hash_index_c.db", "sqlite"), "d": ("train_hash_index_d.txt", "txt"),
                "e": ("train_hash_index_e.jsonl", "jsonl"), "h": ("train_hash_index_h.txt", "txt")}
NODE_FMT = {"n1": "csv", "n2": "jsonl", "n3": "parquet", "n4": "tsv", "n5": "xml", "n7": "xlsx"}
NODE_EXT = {"csv": "csv", "jsonl": "jsonl", "parquet": "parquet", "tsv": "tsv", "xml": "xml", "xlsx": "xlsx"}


def pred_file(run, node):
    fmt = NODE_FMT[node]
    if node == "n7" and run == "R1":
        fmt = "csv"
    return "preds_%s_%s.%s" % (run.lower(), node, NODE_EXT[fmt]), fmt


def _assemble(E, R):
    F = E.files
    ids = E.ids
    # frames
    east = _f(E, "frames_index_east.csv", "csv", kind="frames")
    west = _f(E, "frames_index_west.csv", "csv", kind="frames")
    rep = _f(E, "frames_index_east_v2.csv", "csv", decoy=True, kind="frames")
    for i in sorted(ids, key=lambda x: (E.images[x]["local"], x)):
        im = E.images[i]
        rec = {"image": i, "camera": im["camera"], "local": im["local"], "fold": im["fold"]}
        idx = E.cam[im["camera"]]["index"]
        if idx == "east":
            east["recs"].append(rec)
            r2 = dict(rec)
            if R.chance(50):
                r2["local"] = rec["local"] + R.choice([-3600, 3600, 7200])
                r2["_t16"] = True
            rep["recs"].append(r2)
        elif idx == "west":
            west["recs"].append(rec)
        else:
            rep["recs"].append(dict(rec))
    for r in rep["recs"]:
        im = E.images[r["image"]]
        r["utc_naive"] = r["local"] - SITES[im["site"]][0] * 60
    geo = _f(E, "frame_geometry.tsv", "tsv", kind="geometry")
    exif = _f(E, "exif_orientation_scan.jsonl", "jsonl", kind="exif")
    dh = _f(E, "frame_dhash.parquet", "parquet", kind="dhash")
    integ = _f(E, "frame_integrity_audit.pdf", "pdf", kind="integrity")
    for i in ids:
        im = E.images[i]
        z = i in E.geom_zero
        geo["recs"].append({"image": i, "w": 0 if z else im["w"], "h": 0 if z else im["h"], "scale": 1,
                            "bytes": im["w"] * im["h"] // 9 + R.below(90000)})
        exif["recs"].append({"image": i, "orient": E.exif[i]})
        dh["recs"].append({"image": i, "hash": im["hash"]})
        integ["recs"].append({"image": i, "status": E.integrity[i], "dw": im["dw"], "dh": im["dh"]})
    R.shuffle(exif["recs"])
    cor = _f(E, "orientation_corrections.pdf", "pdf", kind="corrections")
    cor["recs"] = list(E.corrections)
    seqm = _f(E, "sequence_membership.xlsx", "xlsx", kind="seqmem")
    for i in sorted(ids, key=lambda x: (E.images[x]["seq"], E.images[x]["frame"])):
        im = E.images[i]
        sheet = "west" if E.cam[im["camera"]]["index"] == "west" else "east"
        seqm["recs"].append({"image": i, "seq": im["seq"], "frame": im["frame"], "_sheet": sheet})
    life = _f(E, "image_lifecycle_events.xml", "xml", kind="lifecycle")
    for k, e in enumerate(E.events):
        rec = dict(e)
        rec["seq_no"] = k + 1
        rec["off"] = SITES[E.images[e["image"]]["site"]][0]
        life["recs"].append(rec)
    al = _f(E, "image_id_aliases.ini", "ini", kind="aliases")
    al["recs"] = [{"alias": a, "target": E.aliases[a]} for a in sorted(E.aliases)]
    fz = _f(E, "eval_standard_v3.md", "md", kind="freeze")
    fz["recs"] = [dict(r) for r in E.freeze]
    am = _f(E, "eval_standard_v3_1_draft.md", "md", decoy=True, kind="amend")
    frozen_set = set(r["image"] for r in E.freeze)
    unfrozen_all = [i for i in ids if i not in frozen_set]
    am["recs"] = [dict(r) for r in E.amend]
    extra = R.sample([r["image"] for r in E.freeze if not r.get("phantom")], max(200, int(5100 * E.scale)))
    for i in sorted(extra):
        am["recs"].append({"image": i, "action": "confirm", "status": "ratified"})
    for i in R.sample(unfrozen_all, min(len(unfrozen_all), max(20, int(150 * E.scale)))):
        am["recs"].append({"image": i, "action": "confirm", "status": "ratified", "_t16": True})
    am["recs"].sort(key=lambda r: r["image"])
    ics = _f(E, "camera_clock_sync.ics", "ics", kind="ics")
    ics["recs"] = [dict(e) for e in E.ics]
    ros = _f(E, "camera_deployment_roster.yaml", "yaml", kind="roster")
    ops = _f(E, "camera_deployment_roster_ops.yaml", "yaml", decoy=True, kind="roster")
    for row in E.roster:
        if row["camera"] not in E.ops_only:
            ros["recs"].append(dict(row))
        o = dict(row)
        if row["camera"] not in E.ops_only:
            if o["switch"] is not None:
                o["switch"], o["after"] = None, None
                o["_t16"] = True
            elif R.chance(40):
                o["site"] = R.choice(sorted(SITES))
                o["_t16"] = True
        ops["recs"].append(o)
    # training indexes
    for k, (name, fmt) in TRAIN_SHARDS.items():
        sp = _f(E, name, fmt, kind="train", shard=k)
        sp["recs"] = [dict(r) for r in E.shards[k]]
    lg = _f(E, "train_hash_index_legacy.txt", "txt", decoy=True, kind="legacy")
    lg["recs"] = [dict(r) for r in E.legacy]
    fd = _f(E, "train_hash_index_f_dedup.parquet", "parquet", decoy=True, kind="fdedup")
    fd["recs"] = [dict(r) for r in E.fdedup]
    # copy some active v7 rows into the dedup index as stale purged/active mixes
    for k in sorted(E.shards):
        for r in R.sample(E.shards[k], max(50, len(E.shards[k]) // 20)):
            fd["recs"].append({"h": r["h"], "src": k, "purged": not r["purged"], "_t16": True})
    R.shuffle(fd["recs"])
    ts_ = _f(E, "training_sequence_register.pdf", "pdf", kind="trainseq")
    ts_["recs"] = [dict(r) for r in E.trainseq]
    wv = _f(E, "leakage_waivers.json", "json", kind="waivers")
    wv["recs"] = [dict(r) for r in E.waivers]
    pr = _f(E, "exclusion_policy.docx", "docx", kind="privacy_reg")
    pr["recs"] = [dict(r) for r in E.privacy_reg]
    pe = _f(E, "privacy_register_export.tsv", "tsv", decoy=True, kind="privacy_export")
    for r in E.privacy_reg:
        r2 = dict(r)
        if R.chance(50):
            r2["status"] = "HOLD" if r["status"] == "RELEASED" else "RELEASED"
            r2["_t16"] = True
        pe["recs"].append(r2)
    rq = 900000
    for h in E.legal_holds:
        rq += R.randint(1, 4)
        pe["recs"].append({"id": "LH-%d" % rq, "image": h["image"], "status": "LEGAL-HOLD"})
    R.shuffle(pe["recs"])
    mb = _f(E, "privacy_requests.mbox", "mbox", kind="mbox")
    mb["recs"] = [dict(m) for m in E.privacy_msgs]
    gv = _f(E, "release_governance.docx", "docx", kind="board")
    gv["recs"] = [dict(r) for r in E.board]
    g2 = _f(E, "release_governance_v2_signed.docx", "docx", decoy=True, kind="board")
    g2["recs"] = [dict(r) for r in E.board_v2]
    asg = _f(E, "data_authority_policy.docx", "docx", kind="assign")
    asg["recs"] = [{"image": i, "vendor": E.vendor[i], "assigned": ts(2026, 9, 1) + R.below(20 * 86400)} for i in ids]
    bc = _f(E, "annotation_batch_conventions.docx", "docx", kind="batches")
    bc["recs"] = [dict(E.batches[b], batch=b) for b in sorted(E.batches)]
    rc = _f(E, "vendor_batch_receipts.docx", "docx", kind="receipts")
    rc["recs"] = [{"batch": b, "vendor": E.batches[b]["vendor"], "received": E.receipts[b]} for b in sorted(E.batches)]
    tx = _f(E, "taxonomy_v3_charter.docx", "docx", kind="nlx")
    tx["recs"] = [{"project": p, "label": l, "cls": v[0], "disp": v[1]} for (p, l), v in sorted(E.nl_x.items())]
    kb = _f(E, "ks_class_codebook.pdf", "pdf", kind="ksbook")
    kb["recs"] = [dict(r) for r in E.ks_book]
    ob = _f(E, "ob_label_aliases.yaml", "yaml", kind="obx")
    ob["recs"] = [{"project": p, "alias": a, "cls": v[0], "disp": v[1]} for (p, a), v in sorted(E.ob_x.items())]
    er = _f(E, "annotation_errata_register.md", "md", kind="errata")
    er["recs"] = [dict(e) for e in E.errata]
    qa = _f(E, "labeling_qa_portal.html", "html", kind="qa")
    qa["recs"] = sorted((dict(d) for d in E.qa), key=lambda d: (d["t"], d["ann"], d["rev"]))
    qx = _f(E, "labeling_qa_export.xlsx", "xlsx", decoy=True, kind="qa_export")
    qrecs = sorted((dict(d) for d in E.qa_export), key=lambda d: (d["t"], d["ann"], d["rev"]))
    half = len(qrecs) // 2
    for k, d in enumerate(qrecs):
        d["_sheet"] = "decisions_a" if k < half else "decisions_b"
        if d["t"] <= QA_SNAPSHOT:
            d["_t16"] = True
    qx["recs"] = qrecs
    cp = _f(E, "relabel_campaign_2026q3.xlsx", "xlsx", kind="camp")
    cp["recs"] = [dict(r, _sheet="items") for r in E.campaign_items] + [dict(r, _sheet="boxes") for r in E.campaign_boxes]
    cs = _f(E, "relabel_campaign_status.json", "json", kind="camp_status")
    cs["recs"] = sorted((dict(r) for r in E.campaign_status), key=lambda r: (r["item"], r["t"]))
    R.shuffle(cs["recs"])
    # vendor annotation shards
    for name in ["nl_boxes_batch01.csv", "nl_boxes_batch02.csv", "nl_boxes_batch03.tsv", "nl_boxes_batch04.csv"]:
        _f(E, name, name.rsplit(".", 1)[1], kind="nl")
    _f(E, "nl_boxes_q3_extra.xlsx", "xlsx", kind="nl")
    for name in ["ks_boxes_part1.jsonl", "ks_boxes_part2.jsonl", "ks_boxes_part3.json", "ks_boxes_part4.parquet",
                 "ks_boxes_part5.json", "ks_boxes_part6.csv"]:
        _f(E, name, name.rsplit(".", 1)[1], kind="ks")
    for name in ["ob_boxes_east.xml", "ob_boxes_west.xml"]:
        _f(E, name, "xml", kind="ob")
    for a in E.anns:
        target = E.batch_file[a["batch"]]
        rec = dict(a)
        if "#" in target:
            target, sheet = target.split("#")
            rec["_sheet"] = sheet
        F[target]["recs"].append(rec)
    for name in list(F):
        if F[name]["kind"] in ("nl", "ks", "ob"):
            F[name]["recs"].sort(key=lambda a: (a["batch"], a["num"], a["rev"]))
    ksr = _f(E, "ks_boxes_resubmitted.json", "json", decoy=True, kind="ks")
    ksr["recs"] = sorted((dict(a) for a in E.resub["KS"]), key=lambda a: (a["batch"], a["num"], a["rev"]))
    obr = _f(E, "ob_boxes_resubmitted.xml", "xml", decoy=True, kind="ob")
    obr["recs"] = sorted((dict(a) for a in E.resub["OB"]), key=lambda a: (a["batch"], a["num"], a["rev"]))
    for r in ksr["recs"] + obr["recs"]:
        if not E.batches[r["batch"]]["resub"]:
            r["_t16"] = True
    # NL batch02 truncation and its re-extract
    b2 = F["nl_boxes_batch02.csv"]
    full = b2["recs"]
    keep_parts = max(1, (len(full) // 100) - max(2, len(full) // 2000))
    b2["present"] = keep_parts * 100
    rx = _f(E, "nl_boxes_batch02_reextract.csv", "csv", decoy=True, kind="nl")
    for k, a in enumerate(full):
        r2 = dict(a)
        if k < b2["present"] and R.chance(50):
            W, H = upright(E.images[a["image"]])
            r2["box"] = _perturb_box(R, a["box"], W, H)
            r2["_t16"] = True
        rx["recs"].append(r2)
    # registry
    reg = _f(E, "inference_run_registry.html", "html", kind="registry")
    mir = _f(E, "inference_run_registry_mirror.html", "html", decoy=True, kind="registry")
    for (run, s), node in sorted(E.assign.items()):
        if s not in E.late_seqs:
            reg["recs"].append({"run": run, "seq": s, "node": node})
        m = E.assign_mirror[(run, s)]
        mir["recs"].append({"run": run, "seq": s, "node": m, "_t16": m != node})
    rr = _f(E, "rerun_batches.toml", "toml", kind="reruns")
    rr["recs"] = sorted((dict(r) for r in E.reruns), key=lambda r: (r["run"], r["image"]))
    qr = _f(E, "node_quarantine_report.pdf", "pdf", kind="quarantine")
    qr["recs"] = sorted((dict(r, status="quarantined") for r in E.quarantine), key=lambda r: (r["run"], r["node"], r["image"]))
    # filler quarantine entries for R5 (not under review) keep the report realistic
    for i in R.sample(ids, max(100, int(5000 * E.scale))):
        qr["recs"].append({"run": "R5", "node": E.assign[("R5", E.images[i]["seq"])], "image": i, "status": "quarantined"})
    # detection stores
    n6 = _f(E, "node6_rerun_store.db", "sqlite", kind="n6db")
    n6r = _f(E, "node6_ingest_replica.db", "sqlite", decoy=True, kind="n6db")
    replay = _f(E, "preds_r3_n2_replay.jsonl", "jsonl", decoy=True, kind="pred", node="n2", replay=True)
    preds = {}
    for run in [r[0] for r in RUNS]:
        for node in NODES:
            name, fmt = pred_file(run, node)
            if run == "R5":
                continue
            preds[(run, node)] = _f(E, name, fmt, kind="pred", node=node, run=run)
    logs = {n: _f(E, "preprocess_%s.log" % n, "log", kind="log", node=n) for n in ["n1", "n2", "n3", "n4", "n5"]}
    E.prep_rows = {"n6": [], "n6-replica": []}
    for run in [r[0] for r in RUNS]:
        for i in ids:
            key = (run, i)
            seq = E.images[i]["seq"]
            node = E.assign[(run, seq)]
            sc, px, py = E.prep[key]
            if run == "R5":
                if not R.chance(100):
                    continue
                rows = E.dets[key]
                tgt_run = "R4"
            else:
                rows = E.orig_override.get(key, E.dets[key] if key not in E.rerun_rows else [])
                tgt_run = run
                if key in E.misfiled:
                    tgt_run = "R3"
            fspec = preds[(tgt_run, node)]
            for d in rows:
                rec = dict(d)
                if node == "n7":
                    rec["prep"] = (sc, px, py)
                fspec["recs"].append(rec)
            if node != "n7":
                attempts = []
                if key in E.prep_retry:
                    for k in range(E.prep_retry[key]):
                        attempts.append(("fail", sc, px + R.randint(5, 40), py))
                if key in E.prep_missing:
                    attempts.append(("fail", sc, px, py + 12))
                else:
                    if R.chance(5):
                        attempts.append(("ok", sc, px + 16, py + 16))
                    attempts.append(("ok", sc, px, py))
                W, H = upright(E.images[i])
                for k, (st, a, b, c) in enumerate(attempts):
                    logs[node]["recs"].append({"run": run, "image": i, "attempt": k + 1, "of": len(attempts),
                                               "status": st, "scale": a, "px": b, "py": c, "W": W, "H": H,
                                               "orient": E.images[i]["orient"], "S": run_cfg(run)[2],
                                               "t": E.images[i]["t"] + 86400 * 3 + R.below(86400 * 20)})
            if key in E.spill:
                other, srows = E.spill[key]
                for d in srows:
                    rec = dict(d)
                    if other == "n7":
                        rec["prep"] = (sc, px + 8, py)
                    preds[(run, other)]["recs"].append(rec)
            if key in E.rerun_rows:
                store = E.rerun_rows[key]
                for d in E.dets[key]:
                    rec = dict(d)
                    if store == "n2-replay":
                        rec["prep"] = (sc, px, py)
                        replay["recs"].append(rec)
                    elif store == "n6":
                        n6["recs"].append(rec)
                    else:
                        n6r["recs"].append(rec)
                if store in ("n6", "n6-replica"):
                    E.prep_rows[store].append({"run": run, "image": i, "scale": sc, "px": px, "py": py, "status": "ok"})
            if key in E.failed_rerun_rows:
                for d in E.failed_rerun_rows[key]:
                    n6["recs"].append(dict(d, det=d["det"] + 500000000))
                E.prep_rows["n6"].append({"run": run, "image": i, "scale": sc, "px": px, "py": py + 4, "status": "failed"})
            if run == "R3" and node == "n2" and key not in E.rerun_rows and R.chance(600):
                for d in rows:
                    replay["recs"].append(dict(d, prep=(sc, px + 24, py), _t16=True))
    # replica copies of the main rerun store (stale)
    for rec in n6["recs"]:
        if R.chance(400):
            r2 = dict(rec)
            if R.chance(100):
                r2["score"] = max(1, r2["score"] - 40)
                r2["_t16"] = True
            n6r["recs"].append(r2)
    for p in E.prep_rows["n6"]:
        if R.chance(400):
            E.prep_rows["n6-replica"].append(dict(p))
    for spec in preds.values():
        spec["recs"].sort(key=lambda d: (d["image"], d["det"]))
    for spec in (n6, n6r, replay):
        spec["recs"].sort(key=lambda d: (d["run"], d["image"], d["det"]))
    for spec in logs.values():
        spec["recs"].sort(key=lambda r: (r["t"], r["run"], r["image"], r["attempt"]))
    # calibration
    _f(E, "calibration_r1_v64.yaml", "yaml", kind="calib", run="R1")
    _f(E, "calibration_r2_rc1.toml", "toml", kind="calib", run="R2")
    _f(E, "calibration_certificate_rc2.pdf", "pdf", kind="calib", run="R3")
    _f(E, "calibration_r4_ema.ini", "ini", kind="calib", run="R4")
    _f(E, "calibration_certificate_rc2_reissue.pdf", "pdf", decoy=True, kind="calib", run="R3", reissue=True)
    for name in ["calibration_r1_v64.yaml", "calibration_r2_rc1.toml", "calibration_certificate_rc2.pdf",
                 "calibration_r4_ema.ini", "calibration_certificate_rc2_reissue.pdf"]:
        spec = F[name]
        run = spec["run"]
        for cls in CLASSES:
            if name == "calibration_certificate_rc2.pdf" and cls in E.deferred:
                continue
            knots = E.calib_reissue[cls] if spec.get("reissue") else E.calib[(run, cls)]
            for k in range(512):
                spec["recs"].append({"cls": cls, "k": k, "x": KNOT_X[k], "y": knots[k],
                                     "_t16": bool(spec.get("reissue")) and knots[k] != E.calib[(run, cls)][k]})
    _f(E, "delivery_manifest.toml", "toml", kind="manifest")

# ----------------------------------------------------------------- trap planting
TEXT_FMTS = {"csv", "tsv", "jsonl", "log", "txt"}


def _clean(rec):
    return {k: v for k, v in rec.items() if not k.startswith("_") or k == "_sheet"}


def _has_img(E, rec):
    return isinstance(rec.get("image"), str) and rec["image"] in E.images


def _k_flag(flag, fmts=None, need_img=True, pred=None):
    def fn(E, R, spec, idx):
        rec = spec["recs"][idx]
        if fmts is not None and spec["fmt"] not in fmts:
            return False
        if need_img and not _has_img(E, rec):
            return False
        if pred is not None and not pred(E, spec, rec):
            return False
        if rec.get(flag):
            return False
        rec[flag] = True
        return True
    return fn


def _k_idv(E, R, spec, idx):
    rec = spec["recs"][idx]
    if not _has_img(E, rec) or rec.get("_idv") or rec.get("_alias"):
        return False
    rec["_idv"] = id_variant(R, rec["image"], ascii_only=spec["fmt"] == "pdf", no_space=spec["fmt"] in ("log", "mbox"))[0]
    return True


def _k_alias(E, R, spec, idx):
    rec = spec["recs"][idx]
    if not _has_img(E, rec) or rec["image"] not in E.alias_of or rec.get("_idv"):
        return False
    rec["_alias"] = E.alias_of[rec["image"]]
    return True


def _k_mark(pred):
    def fn(E, R, spec, idx):
        rec = spec["recs"][idx]
        if rec.get("_marked") or not pred(E, spec, rec):
            return False
        rec["_marked"] = True
        return True
    return fn


def _k_ann_deleted(E, R, spec, idx):
    rec = spec["recs"][idx]
    if "vendor" not in rec:
        return False
    new = dict(rec)
    new["num"] = rec["num"] + 5000000 + idx
    new["ann"] = "%s-%07d" % (rec["vendor"], new["num"])
    new["status"] = "deleted"
    W, H = upright(E.images[rec["image"]])
    new["box"] = _perturb_box(R, rec["box"], W, H)
    new = _clean(new)
    spec["recs"].insert(idx + 1, new)
    return True


def _k_ann_oldrev(E, R, spec, idx):
    rec = spec["recs"][idx]
    if "vendor" not in rec or rec["status"] != "live":
        return False
    same = [r for r in spec["recs"] if r.get("ann") == rec["ann"]]
    if len(same) != 1:
        return False
    old = dict(rec)
    W, H = upright(E.images[rec["image"]])
    old["box"] = _perturb_box(R, rec["box"], W, H)
    old = _clean(old)
    rec["rev"] = rec["rev"] + 1
    for qname in ("labeling_qa_portal.html", "labeling_qa_export.xlsx"):
        for q in E.files[qname]["recs"]:
            if q.get("ann") == rec["ann"] and q.get("rev") == old["rev"]:
                q["rev"] = rec["rev"]
    spec["recs"].insert(idx, old)
    return True


def _k_ann_tiny64(E, R, spec, idx):
    rec = spec["recs"][idx]
    if "vendor" not in rec or rec["status"] != "live":
        return False
    W, H = upright(E.images[rec["image"]])
    x1, y1 = rec["box"][0], rec["box"][1]
    if x1 + 8 > W or y1 + 8 > H:
        return False
    for r in spec["recs"]:
        if r.get("ann") == rec["ann"]:
            r["box"] = (x1, y1, x1 + 8, y1 + 8)
    return True


def _k_ann_giant(E, R, spec, idx):
    rec = spec["recs"][idx]
    if "vendor" not in rec or rec["status"] != "live":
        return False
    W, H = upright(E.images[rec["image"]])
    for r in spec["recs"]:
        if r.get("ann") == rec["ann"]:
            r["box"] = (1, 2, W - 1, H - 3)
    return True


def _k_ann_crowd_sentinel(E, R, spec, idx):
    rec = spec["recs"][idx]
    if "vendor" not in rec or rec["crowd"] != 0 or rec.get("_t5"):
        return False
    rec["_t5"] = True
    return True


def _k_ks_boundary(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("vendor") != "KS":
        return False
    rows = [r for r in E.ks_index.get(rec["project"], []) if r["to"] is not None]
    if not rows:
        return False
    cut = rows[0]["to"]
    lab = _label_for(E, R, "KS", rec["project"], *_ks_meaning(E, rec), cut)
    if lab is None:
        return False
    for r in spec["recs"]:
        if r.get("ann") == rec["ann"]:
            r["t"] = cut
            r["label"] = lab
    return True


def _ks_meaning(E, rec):
    for row in E.ks_index[rec["project"]]:
        if row["from"] <= rec["t"] and (row["to"] is None or rec["t"] < row["to"]) and row["code"] == rec["label"]:
            cls = "e_scooter" if row["disp"] == "drop" else row["cls"]
            return (row["cls"] if row["disp"] != "drop" else row["cls"], row["disp"])
    return (rec["cls"], rec["disp"])


def _k_pred_r5(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("run") not in REVIEW_RUNS:
        return False
    new = _clean(rec)
    new["label"] = _canon_label(rec["run"], rec["label"]) or "e_scooter"
    new["run"] = "R5"
    new["det"] = rec["det"] + 400000000
    spec["recs"].insert(idx + 1, new)
    return True


def _k_pred_sentinel(E, R, spec, idx):
    rec = spec["recs"][idx]
    if "det" not in rec:
        return False
    new = _clean(rec)
    new["det"] = rec["det"] + 450000000
    new["score"] = -1
    spec["recs"].insert(idx + 1, new)
    return True


def _k_pred_dup(E, R, spec, idx):
    rec = spec["recs"][idx]
    if "det" not in rec:
        return False
    new = _clean(rec)
    spec["recs"].insert(idx + 1, new)
    return True


def _k_pred_score999(E, R, spec, idx):
    rec = spec["recs"][idx]
    if "det" not in rec or rec.get("run") not in REVIEW_RUNS or rec["score"] < 1:
        return False
    rec["score"] = 999
    return True


def _k_life_dup(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("type") != "withdrawn":
        return False
    new = _clean(rec)
    new["seq_no"] = rec["seq_no"]
    spec["recs"].append(new)
    return True


def _k_life_pair(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("type") != "ingested" or rec["t"] > CUTOFF - 30 * 86400:
        return False
    base = _clean(rec)
    w = dict(base, id=rec["id"] + "W", type="withdrawn", t=rec["t"] + 7200)
    r_ = dict(base, id=rec["id"] + "R", type="restored", t=rec["t"] + 9000)
    spec["recs"].insert(idx + 1, r_)
    spec["recs"].insert(idx + 1, w)
    return True


def _k_corr_old(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("status") != "confirmed" or rec["orient"] != E.images[rec["image"]]["orient"]:
        return False
    wrong = R.choice([o for o in (1, 3, 6, 8) if o != rec["orient"]])
    spec["recs"].insert(idx + 1, {"id": rec["id"] + "A", "image": rec["image"], "orient": wrong, "status": "confirmed", "t": rec["t"] - 86400})
    return True


def _k_corr_proposed(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("status") != "confirmed":
        return False
    wrong = R.choice([o for o in (1, 3, 6, 8) if o != rec["orient"]])
    spec["recs"].insert(idx + 1, {"id": rec["id"] + "P", "image": rec["image"], "orient": wrong, "status": "proposed", "t": rec["t"] + 86400})
    return True


def _train_row(spec, h, purged):
    if spec["kind"] == "fdedup":
        return {"h": h, "src": "g", "purged": purged}
    return {"h": h, "purged": purged, "tag": "v6-core" if spec["kind"] == "legacy" else "v7-train"}


def _k_train_near5(E, R, spec, idx):
    rec = spec["recs"][idx]
    cands = [i for i in E.ids if E.images[i]["hash"] and i not in E.bucket]
    if not cands:
        return False
    i = R.choice(cands)
    row = _train_row(spec, _flip(E.images[i]["hash"], 5, R), False)
    row["_target"] = i
    spec["recs"].insert(idx + 1, row)
    return True


def _k_train_purged(E, R, spec, idx):
    cands = [i for i in E.ids if E.images[i]["hash"] and i not in E.bucket]
    if not cands:
        return False
    i = R.choice(cands)
    row = _train_row(spec, E.images[i]["hash"], True)
    row["_target"] = i
    spec["recs"].insert(idx + 1, row)
    return True


def _k_train_sentinel(E, R, spec, idx):
    spec["recs"].insert(idx + 1, _train_row(spec, 0, False))
    return True


def _k_waiver_old(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("status") != "denied":
        return False
    spec["recs"].insert(idx, dict(_clean(rec), id=rec["id"] + "G", status="granted", decided=rec["decided"] - 86400))
    return True


def _k_waiver_cutoff(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("status") != "granted" or rec.get("expires") is not None:
        return False
    rec["expires"] = CUTOFF
    return True


def _k_msg_forward(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("action") not in ("TAKEDOWN", "RELEASE"):
        return False
    spec["recs"].insert(idx + 1, dict(_clean(rec), valid=False,
                                      action="RELEASE" if rec["action"] == "TAKEDOWN" else "TAKEDOWN", t=rec["t"] + 600))
    return True


def _k_msg_register(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("action") != "ACK":
        return False
    rec["action"] = "TAKEDOWN"
    rec["t"] = REGISTER_DATE
    return True


def _k_status_old(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("status") != "approved":
        return False
    spec["recs"].insert(idx, {"item": rec["item"], "status": "rejected", "t": rec["t"] - 3600})
    return True


def _k_qa_old(E, R, spec, idx):
    rec = spec["recs"][idx]
    spec["recs"].insert(idx, dict(_clean(rec),
                                  decision="rejected" if rec["decision"] == "accepted" else "accepted", t=rec["t"] - 3600))
    return True


def _k_rerun_dup(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("status") != "completed":
        return False
    spec["recs"].insert(idx, dict(_clean(rec), status="failed"))
    return True


def _k_log_fail(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("status") != "ok" or rec["attempt"] != rec["of"]:
        return False
    same = [r for r in spec["recs"] if r["run"] == rec["run"] and r["image"] == rec["image"]]
    for r in same:
        r["of"] += 1
        r["attempt"] += 1
    bad = dict(_clean(rec), attempt=1, status="fail", py=rec["py"] + 30)
    bad["of"] = rec["of"]
    spec["recs"].insert(idx, bad)
    return True


def _k_errata_cutoff(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("action") != "REBOX" or rec["eff"] > CUTOFF:
        return False
    rec["eff"] = ts(2026, 11, 12)
    return True


def _k_errata_chain(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("action") != "RECLASS" or rec["eff"] > CUTOFF:
        return False
    spec["recs"].insert(idx, {"id": rec["id"] + "a", "ann": rec["ann"], "action": "RECLASS",
                              "value": R.choice([c for c in CLASSES if c != rec["value"]]), "eff": rec["eff"] - 86400})
    return True


def _k_errata_foreign(E, R, spec, idx):
    rec = spec["recs"][idx]
    spec["recs"].insert(idx + 1, {"id": rec["id"] + "x", "ann": "OB-9%06d" % R.below(10 ** 6), "action": "VOID",
                                  "value": "", "eff": rec["eff"]})
    return True


def _k_ics_ms(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("unit") != "s" or rec["status"] != "CONFIRMED" or rec["skew"] == 0:
        return False
    rec["unit"] = "ms"
    return True


def _k_ics_big(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec["status"] != "CONFIRMED" or rec["skew"] != 0:
        return False
    rec["skew"] = R.choice([-1, 1]) * R.randint(900, 1800)
    E.skew[(rec["camera"], window_of(rec["start"]))] = rec["skew"]
    return True


def _k_roster_dup(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("camera") not in E.ops_only:
        return False
    spec["recs"].insert(idx, dict(_clean(rec), site=R.choice(sorted(SITES)), off=0))
    return True


def _k_roster_inactive(E, R, spec, idx):
    rec = spec["recs"][idx]
    spec["recs"].insert(idx + 1, dict(_clean(rec), camera="CAM-Z%02d" % R.below(100), inactive=True))
    return True


def _k_reg_dup(E, R, spec, idx):
    rec = spec["recs"][idx]
    spec["recs"].insert(idx, dict(_clean(rec), node=R.choice(NODES)))
    return True


def _k_board_old(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("decision") != "CONFIRM":
        return False
    spec["recs"].insert(idx, dict(_clean(rec), id=rec["id"] + "E", decision="EXCLUDE", t=rec["t"] - 86400))
    return True


def _k_freeze_struck(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("phantom") or rec.get("_struck"):
        return False
    rec["_struck"] = True
    return True


def _k_amend_old(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("status") != "ratified" or rec.get("action") not in ("add", "remove"):
        return False
    spec["recs"].insert(idx, dict(_clean(rec),
                                  action="remove" if rec["action"] == "add" else "add"))
    return True


def _k_amend_proposed(E, R, spec, idx):
    rec = spec["recs"][idx]
    spec["recs"].insert(idx + 1, {"image": rec["image"], "action": "remove", "status": "proposed"})
    return True


def _k_calib_block(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("k") is None or rec.get("_stale"):
        return False
    stale = dict(_clean(rec), y=min(Fraction(1), rec["y"] + Fraction(3, 10 ** 6)))
    stale["_stale"] = True
    spec["recs"].insert(idx, stale)
    return True


def _k_frames_dup(E, R, spec, idx):
    rec = spec["recs"][idx]
    if E.cam[rec["camera"]]["index"] != "replica" or rec.get("void"):
        return False
    spec["recs"].insert(idx, dict(_clean(rec), local=rec["local"] - 60, utc_naive=rec["utc_naive"] - 60))
    return True


def _k_frames_void(E, R, spec, idx):
    rec = spec["recs"][idx]
    if E.cam[rec["camera"]]["index"] != "replica" or rec.get("void"):
        return False
    spec["recs"].insert(idx + 1, dict(_clean(rec), local=rec["local"] + 3600, void=True))
    return True


def _k_quar_released(E, R, spec, idx):
    rec = spec["recs"][idx]
    i = R.choice(E.ids)
    run = R.choice(REVIEW_RUNS)
    spec["recs"].insert(idx + 1, {"run": run, "node": E.assign[(run, E.images[i]["seq"])], "image": i, "status": "released"})
    return True


def _k_assign_old(E, R, spec, idx):
    rec = spec["recs"][idx]
    if "vendor" not in rec:
        return False
    spec["recs"].insert(idx, dict(_clean(rec),
                                  vendor=R.choice([v for v in ("NL", "KS", "OB") if v != rec["vendor"]]), assigned=rec["assigned"] - 86400 * 3))
    return True


def _k_obx_dup(E, R, spec, idx):
    rec = spec["recs"][idx]
    if rec.get("disp") != "eval":
        return False
    spec["recs"].insert(idx, dict(_clean(rec),
                                  cls=R.choice([c for c in CLASSES if c != rec["cls"]])))
    return True


def _menu(E, spec):
    fmt, kind, decoy = spec["fmt"], spec["kind"], spec["decoy"]
    idv = ("T1", _k_idv)
    ali = ("T13", _k_alias)
    t4 = ("T4", _k_flag("_t4", need_img=False))
    t3 = ("T3", _k_flag("_t3", need_img=False))
    t8 = ("T8", _k_flag("_t8", fmts={"csv", "tsv", "xlsx"}, need_img=False))
    t9 = ("T9", _k_flag("_t9", fmts={"csv", "tsv"}, need_img=False))
    t10 = ("T10", _k_flag("_t10", fmts=TEXT_FMTS | {"ini"}, need_img=False))
    t14 = ("T14", _k_flag("_t14", need_img=False))
    t16 = ("T16", _k_mark(lambda E, s, r: bool(r.get("_t16"))))
    text = [t8, t9, t10] if fmt in ("csv", "tsv") else ([t10] if fmt in TEXT_FMTS else [])
    m = []
    if kind == "frames":
        m = [idv, ali, ("T3", _k_mark(lambda E, s, r: r.get("fold") is not None)),
             ("T11", _k_mark(lambda E, s, r: _has_img(E, r) and min(abs(E.images[r["image"]]["t"] - WINDOW_START), abs(E.images[r["image"]]["t"] - WINDOW_END)) < 120))] + text
        if decoy:
            m += [t16, ("T7", _k_frames_dup), ("T6", _k_frames_void)]
    elif kind == "geometry":
        m = [idv, ali, ("T2", _k_flag("_t2", pred=lambda E, s, r: r["w"] % 2 == 0 and r["h"] % 2 == 0 and r["w"] > 0)),
             ("T5", _k_flag("_t5", pred=lambda E, s, r: r["w"] > 0)), t4] + text
    elif kind == "exif":
        m = [idv, ali, ("T5", _k_flag("_t5", pred=lambda E, s, r: r["orient"] == 1 and E.images[r["image"]]["orient"] == 1)), t10]
    elif kind == "dhash":
        m = [idv, ali, ("T2", _k_flag("_t2", pred=lambda E, s, r: r["hash"] != 0)), ("T5", _k_mark(lambda E, s, r: r.get("hash") == 0))]
    elif kind == "seqmem":
        m = [idv, ali, t8, t4]
    elif kind == "lifecycle":
        m = [idv, ali, t3, ("T6", _k_life_pair), ("T7", _k_life_dup)]
    elif kind == "integrity":
        m = [idv, ali, t14, ("T5", _k_flag("_t5", pred=lambda E, s, r: r["status"] == "PASS"))]
    elif kind == "corrections":
        m = [idv, ali, t14, t3, ("T7", _k_corr_old), ("T6", _k_corr_proposed)]
    elif kind == "aliases":
        m = [("T13", _k_mark(lambda E, s, r: not r["target"].startswith("IMG"))), ("T1", _k_flag("_t1t", need_img=False)),
             ("T9", _k_flag("_t9", need_img=False)), t10]
    elif kind == "freeze":
        m = [idv, ali, t14, ("T6", _k_freeze_struck)]
    elif kind == "amend":
        m = [idv, ali, t14, t16, ("T6", _k_amend_proposed), ("T7", _k_amend_old)]
    elif kind == "ics":
        m = [("T2", _k_ics_ms), ("T6", _k_mark(lambda E, s, r: r["status"] == "CANCELLED")), t4, ("T15", _k_ics_big),
             ("T1", _k_flag("_t1c", need_img=False))]
    elif kind == "roster":
        m = [("T1", _k_flag("_t1c", need_img=False)), t4, ("T3", _k_mark(lambda E, s, r: r.get("switch") is not None)),
             ("T15", _k_mark(lambda E, s, r: r["camera"] in E.reloc and r["site"] != E.cam[r["camera"]]["site"]))]
        if decoy:
            m += [t16, ("T7", _k_roster_dup), ("T6", _k_roster_inactive), ("T13", _k_mark(lambda E, s, r: r["camera"] in E.ops_only))]
    elif kind in ("train", "legacy", "fdedup"):
        m = [("T5", _k_train_sentinel), ("T6", _k_train_purged), ("T11", _k_train_near5), ("T2", _k_flag("_t2", need_img=False))] + text
        if kind == "train" and spec.get("shard") == "d":
            m.append(("T13", _k_mark(lambda E, s, r: r.get("tag") == "v7-calib")))
        if decoy:
            m += [t16, ("T7", _k_mark(lambda E, s, r: r.get("tag") == "v6-synthetic" or r.get("src") not in (None, "g"))),
                  ("T13", _k_mark(lambda E, s, r: r.get("tag") == "v6-core" or r.get("src") == "g"))]
    elif kind == "trainseq":
        m = [("T1", _k_flag("_t1s", need_img=False)), ("T6", _k_mark(lambda E, s, r: r["status"] == "held-out")),
             ("T13", _k_mark(lambda E, s, r: r["index"] == "v5-archive")), t14]
    elif kind == "waivers":
        m = [idv, ali, ("T6", _k_mark(lambda E, s, r: r["status"] == "denied")), ("T7", _k_waiver_old), t3, ("T11", _k_waiver_cutoff)]
    elif kind == "privacy_reg":
        m = [idv, ali, t14, ("T6", _k_mark(lambda E, s, r: r["status"] == "RELEASED"))]
    elif kind == "privacy_export":
        m = [idv, ali, t16, ("T6", _k_mark(lambda E, s, r: r["status"] == "RELEASED")), ("T7", _k_mark(lambda E, s, r: r["status"] == "HOLD")),
             ("T13", _k_mark(lambda E, s, r: r["status"] == "LEGAL-HOLD"))] + text
    elif kind == "mbox":
        m = [idv, ali, t3, ("T6", _k_msg_forward), ("T11", _k_msg_register), ("T7", _k_mark(lambda E, s, r: r.get("action") == "RELEASE"))]
    elif kind == "board":
        m = [idv, ali, t14, ("T7", _k_board_old)]
        if decoy:
            m += [t16, ("T6", _k_mark(lambda E, s, r: r["t"] > CUTOFF)), ("T13", _k_mark(lambda E, s, r: r["decision"] == "EXCLUDE"))]
    elif kind == "assign":
        m = [idv, ali, t14, ("T7", _k_assign_old)]
    elif kind == "batches":
        m = [("T14", _k_mark(lambda E, s, r: r.get("errata") is not None)), ("T2", _k_flag("_t2", need_img=False)),
             ("T1", _k_flag("_t1b", need_img=False)), ("T5", _k_flag("_t5", need_img=False, pred=lambda E, s, r: r["fmt"] == {"NL": "xywh", "KS": "cxcywh_norm", "OB": "xyxy_inclusive"}[r["vendor"]] and r["frame"] == {"NL": "stored", "KS": "upright", "OB": "upright"}[r["vendor"]] and not r.get("errata")))]
    elif kind == "receipts":
        m = [t3, ("T11", _k_mark(lambda E, s, r: r["received"] == CUTOFF)), ("T1", _k_flag("_t1b", need_img=False)), t14]
    elif kind == "nlx":
        m = [("T10", _k_mark(lambda E, s, r: not r["label"].isascii())), t14, ("T1", _k_flag("_t1p", need_img=False)),
             ("T13", _k_mark(lambda E, s, r: r["disp"] == "drop"))]
    elif kind == "ksbook":
        m = [("T11", _k_mark(lambda E, s, r: r["to"] is not None)), ("T7", _k_mark(lambda E, s, r: r["from"] != ts(2026, 1, 1))), t14,
             ("T1", _k_flag("_t1p", need_img=False))]
    elif kind == "obx":
        m = [("T1", _k_flag("_t1p", need_img=False)), ("T13", _k_mark(lambda E, s, r: r["disp"] != "eval")),
             ("T5", _k_flag("_t5", need_img=False, pred=lambda E, s, r: r["disp"] == "eval")), ("T7", _k_obx_dup)]
    elif kind == "errata":
        m = [("T7", _k_errata_chain), ("T11", _k_errata_cutoff), ("T3", _k_mark(lambda E, s, r: r["eff"] > CUTOFF)), t14,
             ("T13", _k_errata_foreign), ("T1", _k_flag("_t1a", need_img=False))]
    elif kind == "qa":
        m = [("T1", _k_flag("_t1a", need_img=False)), ("T7", _k_qa_old), t14, t3]
    elif kind == "qa_export":
        m = [("T1", _k_flag("_t1a", need_img=False)), t16, ("T6", _k_mark(lambda E, s, r: r["state"] == "draft")), ("T7", _k_qa_old),
             t3, t8, ("T13", _k_mark(lambda E, s, r: r["t"] > QA_SNAPSHOT and r["decision"] == "rejected"))]
    elif kind == "camp":
        m = [idv, ali, t3, t8, ("T15", _k_mark(lambda E, s, r: r.get("crowd") == 1))]
    elif kind == "camp_status":
        m = [("T7", _k_status_old), ("T11", _k_mark(lambda E, s, r: r["t"] == CUTOFF and r["status"] == "approved")), t3,
             ("T6", _k_mark(lambda E, s, r: r["status"] == "rejected"))]
    elif kind in ("nl", "ks", "ob"):
        m = [idv, ali, ("T6", _k_ann_deleted), ("T7", _k_ann_oldrev), ("T11", _k_ann_tiny64), ("T15", _k_ann_giant)] + text
        if kind in ("ks", "ob") or kind == "nl":
            m.append(("T5", _k_ann_crowd_sentinel))
        if kind == "ks":
            m += [("T2", _k_flag("_t2", need_img=False)), ("T12", _k_flag("_t12", need_img=False)), ("T3", _k_flag("_t3", need_img=False))]
        if kind == "nl":
            m.append(("T4", _k_flag("_t4", need_img=False)))
        if decoy:
            m += [t16, ("T13", _k_mark(lambda E, s, r: r.get("batch") in E.batches and not E.batches[r["batch"]]["resub"]))]
    elif kind == "registry":
        m = [("T1", _k_flag("_t1s", need_img=False)), t14, ("T13", _k_mark(lambda E, s, r: r["run"] == "R5")), ("T7", _k_reg_dup)]
        if decoy:
            m += [t16, ("T6", _k_mark(lambda E, s, r: r["seq"] in E.late_seqs))]
    elif kind == "reruns":
        m = [idv, ali, ("T6", _k_mark(lambda E, s, r: r["status"] != "completed")), ("T7", _k_rerun_dup)]
    elif kind == "quarantine":
        m = [idv, ali, t14, ("T13", _k_mark(lambda E, s, r: r["run"] == "R5")), ("T6", _k_quar_released)]
    elif kind == "n6db":
        m = [idv, ali, ("T5", _k_pred_sentinel), ("T12", _k_flag("_t12", need_img=False))]
        if decoy:
            m += [t16, ("T6", _k_pred_r5), ("T7", _k_pred_dup),
                  ("T13", _k_mark(lambda E, s, r: E.rerun_rows.get((r.get("run"), r.get("image"))) != "n6-replica"))]
    elif kind == "log":
        m = [idv, ali, ("T7", _k_mark(lambda E, s, r: r["status"] == "ok" and r["attempt"] < r["of"])), ("T6", _k_log_fail), t10,
             ("T8", _k_flag("_t8", need_img=False))]
    elif kind == "calib":
        m = [("T7", _k_calib_block), t4, t14 if fmt == "pdf" else ("T9", _k_flag("_t9", need_img=False)),
             ("T2", _k_flag("_t2", need_img=False))]
        if decoy:
            m += [t16, ("T6", _k_mark(lambda E, s, r: r["cls"] not in E.deferred)),
                  ("T13", _k_mark(lambda E, s, r: r["cls"] in E.deferred))]
    elif kind == "pred":
        m = [idv, ali, ("T13", _k_pred_r5), ("T5", _k_pred_sentinel), ("T12", _k_flag("_t12", need_img=False)),
             ("T15", _k_pred_score999), ("T2", _k_flag("_t2", need_img=False))] + text
        if spec["fmt"] in ("csv", "jsonl", "xml", "xlsx"):
            m.append(t4)
        if decoy:
            m += [t16, ("T7", _k_pred_dup), ("T6", _k_mark(lambda E, s, r: E.rerun_rows.get((r.get("run"), r.get("image"))) != "n2-replay"))]
    elif kind == "manifest":
        m = []
    return m


def _plant(E, R):
    _assemble(E, R.child("assemble"))
    order = sorted(E.files)
    for name in order:
        spec = E.files[name]
        menu = _menu(E, spec)
        if not menu:
            continue
        n = len(spec["recs"])
        bands = max(1, (n + 499) // 500)
        want = max(bands, (R.randint(25, 30) if spec["decoy"] else R.randint(12, 20)))
        fams_needed = 6 if spec["decoy"] else 4
        planted = []
        fam_cycle = list(range(len(menu)))
        R.shuffle(fam_cycle)
        if spec["decoy"]:
            req = [k for k, (fam, _) in enumerate(menu) if fam in ("T6", "T7", "T13", "T16")]
            fam_cycle = req + [k for k in fam_cycle if k not in req]
        slot = 0
        attempts = 0
        while len(planted) < want and attempts < want * 60:
            attempts += 1
            band = len(planted) if len(planted) < bands else R.below(bands)
            n = len(spec["recs"])
            lo = min(band * 500, max(0, n - 1))
            hi = min(n, lo + 500)
            mi = fam_cycle[slot % len(fam_cycle)]
            fam, fn = menu[mi]
            ok = False
            for _ in range(40):
                idx = R.randint(lo, hi - 1) if hi > lo else 0
                rec = spec["recs"][idx]
                img = rec.get("image") if isinstance(rec.get("image"), str) else None
                if img is not None and (img not in E.images or E.bucket.get(img, fam) != fam):
                    continue
                if rec.get("_trap"):
                    continue
                if fn(E, R, spec, idx):
                    tgt = spec["recs"][idx]
                    tgt["_trap"] = fam
                    if img is not None:
                        E.bucket[img] = fam
                    elif tgt.get("_target"):
                        E.bucket.setdefault(tgt["_target"], fam)
                    planted.append(fam)
                    E.traps.append({"file": name, "row": idx, "family": fam, "decoy": spec["decoy"],
                                    "image": img or tgt.get("_target")})
                    ok = True
                    break
            slot += 1 if ok or attempts % 3 == 0 else 0
        need = 6 if spec["decoy"] else 4
        must = {"T6", "T7", "T13", "T16"} if spec["decoy"] else set()
        for mi in range(len(menu)):
            fam, fn = menu[mi]
            have = set(planted)
            if fam in have or (len(have) >= need and must <= have):
                continue
            n = len(spec["recs"])
            start = R.below(max(1, n))
            for step in range(n):
                idx = (start + step) % n
                rec = spec["recs"][idx]
                img = rec.get("image") if isinstance(rec.get("image"), str) else None
                if img is not None and (img not in E.images or E.bucket.get(img, fam) != fam):
                    continue
                if rec.get("_trap"):
                    continue
                if fn(E, R, spec, idx):
                    tgt = spec["recs"][idx]
                    tgt["_trap"] = fam
                    if img is not None:
                        E.bucket[img] = fam
                    elif tgt.get("_target"):
                        E.bucket.setdefault(tgt["_target"], fam)
                    planted.append(fam)
                    E.traps.append({"file": name, "row": idx, "family": fam, "decoy": spec["decoy"], "image": img or tgt.get("_target")})
                    break
        spec["n_traps"] = len(planted)
        spec["families"] = sorted(set(planted))


# ----------------------------------------------------------------- tie-break fixtures
# Inputs where only a stated precedence or tie-break rule decides the answer. They are added after
# trap planting, so every earlier record and trap is unchanged, and in each fixture the record the
# rules select carries the value the rest of the estate was built from.
def _plain(rec):
    return not any(k.startswith("_") for k in rec)


def _likely_eval(E):
    """Frozen images with no planted exclusion evidence, so a fixture on them is most likely graded."""
    F = E.files
    frozen = set(r["image"] for r in F["eval_standard_v3.md"]["recs"] if not r.get("_struck") and not r.get("phantom"))
    for r in F["eval_standard_v3_1_draft.md"]["recs"]:
        if r.get("action") == "remove":
            frozen.discard(r["image"])
    bad = set(e["image"] for e in E.events if e["type"] == "withdrawn")
    bad |= set(r["image"] for r in E.privacy_reg if r["status"] == "HOLD")
    bad |= set(m["image"] for m in E.privacy_msgs if m["action"] == "TAKEDOWN")
    bad |= set(h["image"] for h in E.legal_holds)
    bad |= set(b["image"] for b in E.board + E.board_v2 if b["decision"] == "EXCLUDE")
    bad |= E.intent_unlabeled
    trained = set(s["seq"] for s in E.trainseq if s["status"] == "trained")
    out = []
    for i in sorted(frozen):
        im = E.images.get(i)
        if im is None or i in bad or E.integrity.get(i) != "PASS" or im["seq"] in trained:
            continue
        if WINDOW_START + 86400 <= im["t"] < WINDOW_END - 86400:
            out.append(i)
    return out


def _index_of(recs, rec):
    return next(k for k, r in enumerate(recs) if r is rec)


def _fx_leak_exact_and_near(E, R, likely, n=4):
    """A candidate with an exact training hash in one shard and a distance 1-4 hash in another (LEAK_EXACT wins)."""
    F = E.files
    shard_of = {}
    for k in sorted(TRAIN_SHARDS):
        for r in F[TRAIN_SHARDS[k][0]]["recs"]:
            if r.get("tag") == "v7-train" and not r.get("purged") and r.get("h"):
                shard_of.setdefault(r["h"], k)
    waived = set((w["image"], w["h"]) for w in F["leakage_waivers.json"]["recs"])
    pool = [i for i in likely if E.images[i]["hash"] in shard_of and (i, E.images[i]["hash"]) not in waived]
    for i in R.sample(pool, min(n, len(pool))):
        h = E.images[i]["hash"]
        other = R.choice([k for k in sorted(TRAIN_SHARDS) if k != shard_of[h]])
        recs = F[TRAIN_SHARDS[other][0]]["recs"]
        recs.insert(R.below(len(recs) + 1), {"h": _flip(h, R.randint(1, 4), R), "purged": False, "tag": "v7-train"})


def _fx_correction_id_tie(E, R, likely, n=4):
    """A wrong confirmed correction with the same decided time and a smaller id than the true one."""
    recs = E.files["orientation_corrections.pdf"]["recs"]
    by_img = {}
    for r in recs:
        by_img.setdefault(r["image"], []).append(r)
    pool = []
    for i in likely:
        rs = by_img.get(i, [])
        conf = [r for r in rs if r["status"] == "confirmed"]
        if not conf or not all(_plain(r) and r["id"][3:].isdigit() and len(r["id"]) == 8 for r in rs):
            continue
        top = max(conf, key=lambda r: (r["t"], r["id"]))
        if top["orient"] == E.images[i]["orient"] and sum(1 for r in conf if r["t"] == top["t"]) == 1:
            pool.append(top)
    used = set(r["id"] for r in recs)
    num = 20000
    for k, top in enumerate(R.sample(pool, min(n, len(pool)))):
        while "OC-%d" % num in used:
            num += 1
        used.add("OC-%d" % num)
        new = {"id": "OC-%d" % num, "image": top["image"], "status": "confirmed", "t": top["t"],
               "orient": R.choice([o for o in (1, 3, 6, 8) if o != top["orient"]])}
        at = _index_of(recs, top)
        recs.insert(at + 1 if k % 2 == 0 else at, new)


def _fx_waiver_id_tie(E, R, likely, n=4):
    """Two decisions on one waiver pair at the same instant; the larger waiver_id stands."""
    recs = E.files["leakage_waivers.json"]["recs"]
    pairs = {}
    for r in recs:
        pairs.setdefault((r["image"], r["h"]), []).append(r)
    nums = [int(r["id"][3:]) for r in recs if r["id"][3:].isdigit()]
    hi, lo = max(nums), 1000
    used = set(r["id"] for r in recs)
    keep = set(likely)
    pool = []
    for r in recs:
        h = E.images[r["image"]]["hash"] if r["image"] in E.images else 0
        if (_plain(r) and r["status"] == "granted" and r["expires"] is None and r["image"] in keep
                and len(pairs[(r["image"], r["h"])]) == 1 and h and _popcount(h ^ r["h"]) <= 4):
            pool.append(r)
    for k, r in enumerate(R.sample(pool, min(n, len(pool)))):
        at = _index_of(recs, r)
        if k % 2 == 0:
            hi += 1
            new = dict(r, id="WV-%05d" % hi, status="denied")
            recs.insert(at, new)
        else:
            while "WV-%05d" % lo in used:
                lo += 1
            new = dict(r, id="WV-%05d" % lo, status="denied")
            recs.insert(at, new)
        used.add(new["id"])


def _fx_errata_id_tie(E, R, likely, n=4):
    """Two RECLASS errata on one annotation with the same effective date; they apply in errata id order."""
    recs = E.files["annotation_errata_register.md"]["recs"]
    per_ann = {}
    for r in recs:
        per_ann[r["ann"]] = per_ann.get(r["ann"], 0) + 1
    ann_img = {a["ann"]: a for a in E.anns}
    nums = [int(r["id"][3:]) for r in recs if r["id"][3:].isdigit()]
    hi, lo = max(nums), 1000
    keep = set(likely)
    pool = []
    for r in recs:
        a = ann_img.get(r["ann"])
        if (a is None or not _plain(r) or r["action"] != "RECLASS" or r["eff"] > CUTOFF or per_ann[r["ann"]] != 1
                or a["image"] not in keep or a["vendor"] != E.vendor[a["image"]] or E.camp_state.get(a["image"]) == "approved"):
            continue
        pool.append(r)
    for k, r in enumerate(R.sample(pool, min(n, len(pool)))):
        at = _index_of(recs, r)
        value = R.choice([c for c in CLASSES if c != r["value"]])
        if k % 2 == 0:
            hi += 1
            recs.insert(at, {"id": "ER-%06d" % hi, "ann": r["ann"], "action": "RECLASS", "value": value, "eff": r["eff"]})
        else:
            lo += 1
            recs.insert(at + 1, {"id": "ER-%06d" % lo, "ann": r["ann"], "action": "RECLASS", "value": value, "eff": r["eff"]})


def _fx_cap_tie(E, R, likely, per_run=2):
    """max_detections + 1 equal top scores on one image, so the per-image cap cuts inside the tie."""
    F = E.files
    quarantined = set((q["run"], q["image"]) for q in E.quarantine)
    order = [i for i in likely if not E.images[i]["hash"]] + [i for i in likely if E.images[i]["hash"]]
    for run in REVIEW_RUNS:
        md = run_cfg(run)[5]
        top_raw = Fraction(999, 1000)
        cls = max((c for c in CLASSES if c not in PROTECTED), key=lambda c: (calibrate(E.calib[(run, c)], top_raw), c))
        top = calibrate(E.calib[(run, cls)], top_raw)
        label = _model_label(run, cls)
        rows_of = {}
        done = 0
        for i in order:
            key = (run, i)
            if key in E.rerun_rows or key in quarantined or key in E.prep_missing or key in E.misfiled or key in E.spill:
                continue
            node = E.assign[(run, E.images[i]["seq"])]
            spec = F[pred_file(run, node)[0]]
            if spec["name"] not in rows_of:
                idx = {}
                for d in spec["recs"]:
                    idx.setdefault(d.get("image"), []).append(d)
                rows_of[spec["name"]] = idx
            rows = [d for d in rows_of[spec["name"]].get(i, []) if d.get("run") == run]
            above = 0
            taken = []
            for d in rows:
                c = _canon_label(run, d["label"])
                if c is None or d["score"] < 0:
                    continue
                if calibrate(E.calib[(run, c)], Fraction(d["score"], 1000)) > top:
                    above += 1
                if c == cls:
                    taken.append(d["box"])
            if above >= md:
                continue
            W, H = upright(E.images[i])
            boxes = []
            for y in range(4, H - 28, 32):
                for x in range(4, W - 28, 32):
                    b = (x, y, x + 24, y + 24)
                    if all(min(b[2], t[2]) <= max(b[0], t[0]) or min(b[3], t[3]) <= max(b[1], t[1]) for t in taken):
                        boxes.append(b)
                    if len(boxes) > md:
                        break
                if len(boxes) > md:
                    break
            if len(boxes) <= md:
                continue
            new = []
            for b in boxes:
                E.det_counter[run] += 1
                d = {"det": E.det_counter[run], "run": run, "image": i, "label": label, "box": b, "score": 999}
                if node == "n7":
                    d["prep"] = E.prep[key]
                new.append(d)
            recs = spec["recs"]
            last = [k for k, d in enumerate(recs) if d.get("image") == i]
            at = last[-1] + 1 if last else next((k for k, d in enumerate(recs) if str(d.get("image")) > i), len(recs))
            for d in sorted(new, key=lambda d: -d["det"]):
                recs.insert(at, d)
                at += 1
            done += 1
            if done == per_run:
                break


def _fx_release_gate(E):
    """Fresh estate only: planted false positives that put every promotion comparison on its bound.

    Each (run, class, raw score) becomes one detection on an image the reference resolution evaluates
    (detection records cannot change an image decision), on a clean run and image pair with no record
    of the class, in a spot no object or record of the image touches, so it is a false positive at
    every IoU threshold and moves nothing else. With EVAL_RUN_QUALITY on EVAL_SEED they make R2's map_50_95
    gain exactly 0.005000 as written (exactly, just under 0.005), R3's cyclist ap_50 delta exactly
    -0.010000 as written (exactly, just under -0.010) and R4's map_50_95 equal to R3's as written
    (exactly, just under it): only the inclusive bounds, the six-decimal comparison, the highest-map
    choice and the smaller-run-id tie-break make R3 the release candidate.
    """
    F = E.files
    evaluated = resolve(E)["_evals"]
    quarantined = set((q["run"], q["image"]) for q in E.quarantine)
    rows_of = {}
    used = set()
    for run, cls, score in EVAL_GATE_FPS:
        md = run_cfg(run)[5]
        for i in evaluated:
            key = (run, i)
            if (i in used or key in E.rerun_rows or key in quarantined or key in E.prep_missing or key in E.misfiled
                    or key in E.spill):
                continue
            node = E.assign[(run, E.images[i]["seq"])]
            spec = F[pred_file(run, node)[0]]
            if spec["name"] not in rows_of:
                idx = {}
                for d in spec["recs"]:
                    idx.setdefault(d.get("image"), []).append(d)
                rows_of[spec["name"]] = idx
            rows = [d for d in rows_of[spec["name"]].get(i, []) if d.get("run") == run]
            objs = E.objects[i]
            if len(rows) > md - 2 or any(_canon_label(run, d["label"]) == cls for d in rows) or any(o["cls"] == cls for o in objs):
                continue
            taken = [d["box"] for d in rows] + [o["box"] for o in objs]
            W, H = upright(E.images[i])
            spot = next(((x, y, x + 24, y + 24) for y in range(4, H - 28, 32) for x in range(4, W - 28, 32)
                         if all(min(x + 24, t[2]) <= max(x, t[0]) or min(y + 24, t[3]) <= max(y, t[1]) for t in taken)), None)
            if spot is None:
                continue
            E.det_counter[run] += 1
            d = {"det": E.det_counter[run], "run": run, "image": i, "label": _model_label(run, cls), "box": spot, "score": score}
            if node == "n7":
                d["prep"] = E.prep[key]
            recs = spec["recs"]
            last = [k for k, r in enumerate(recs) if r.get("image") == i]
            at = last[-1] + 1 if last else next((k for k, r in enumerate(recs) if str(r.get("image")) > i), len(recs))
            recs.insert(at, d)
            rows_of[spec["name"]].setdefault(i, []).append(d)
            used.add(i)
            break


def _tie_fixtures(E, R):
    likely = _likely_eval(E)
    _fx_leak_exact_and_near(E, R, likely)
    _fx_correction_id_tie(E, R, likely)
    _fx_waiver_id_tie(E, R, likely)
    _fx_errata_id_tie(E, R, likely)
    _fx_cap_tie(E, R, likely)
    if E.scale < 1:
        _fx_release_gate(E)

# ----------------------------------------------------------------- reference resolution (verifier truth)
def _iou(a, b):
    iw = min(a[2], b[2]) - max(a[0], b[0])
    ih = min(a[3], b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return Fraction(0)
    inter = iw * ih
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return Fraction(inter, ua)


def _iof(d, g):
    iw = min(d[2], g[2]) - max(d[0], g[0])
    ih = min(d[3], g[3]) - max(d[1], g[1])
    if iw <= 0 or ih <= 0:
        return Fraction(0)
    return Fraction(iw * ih, (d[2] - d[0]) * (d[3] - d[1]))


def _iou_pair(a, b):
    iw = min(a[2], b[2]) - max(a[0], b[0])
    ih = min(a[3], b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return 0, 1
    inter = iw * ih
    return inter, (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter


def _popcount(x):
    return bin(x).count("1")


def resolve(E):
    F = E.files
    T = {}
    # --- freeze and candidates
    freeze = set(r["image"] for r in F["eval_standard_v3.md"]["recs"] if not r.get("_struck"))
    for r in F["eval_standard_v3_1_draft.md"]["recs"]:
        if r["status"] == "ratified" and r["action"] == "add":
            freeze.add(r["image"])
        elif r["status"] == "ratified" and r["action"] == "remove":
            freeze.discard(r["image"])
    frames = {}
    for name in ("frames_index_east.csv", "frames_index_west.csv"):
        for r in F[name]["recs"]:
            frames[r["image"]] = r
    for r in F["frames_index_east_v2.csv"]["recs"]:
        if E.cam[r["camera"]]["index"] == "replica":
            if r.get("void"):
                continue
            frames[r["image"]] = r
    cands = sorted(i for i in freeze if i in frames)
    # --- capture time
    roster = {}
    for r in F["camera_deployment_roster.yaml"]["recs"]:
        roster[(r["camera"], r["date"])] = r
    for r in F["camera_deployment_roster_ops.yaml"]["recs"]:
        if r["camera"] in E.ops_only and not r.get("inactive"):
            roster[(r["camera"], r["date"])] = r
    skew = {}
    for e in F["camera_clock_sync.ics"]["recs"]:
        if e["status"] == "CONFIRMED":
            skew.setdefault(e["camera"], []).append(e)
    info = {}
    for i in cands:
        fr = frames[i]
        cam = fr["camera"]
        local = fr["local"]
        day = _dt.datetime.fromtimestamp(local, _dt.timezone.utc).date()
        ro = roster[(cam, day)]
        off = ro["off"]
        if ro["switch"] is not None:
            sod = local % 86400
            delta = (ro["off"] - ro["after"]) * 60
            if sod >= ro["switch"]:
                off = ro["after"]
            elif sod >= ro["switch"] - delta and fr["fold"] == 1:
                off = ro["after"]
        ucam = local - off * 60
        sk = 0
        for e in skew.get(cam, []):
            if e["start"] <= ucam < e["end"]:
                sk = e["skew"]
        info[i] = {"camera": cam, "site": ro["site"], "t": ucam - sk}
    # --- orientation and dims
    exif = {r["image"]: r["orient"] for r in F["exif_orientation_scan.jsonl"]["recs"]}
    corr = {}
    for r in F["orientation_corrections.pdf"]["recs"]:
        if r["status"] == "confirmed":
            cur = corr.get(r["image"])
            if cur is None or (r["t"], r["id"]) > (cur["t"], cur["id"]):
                corr[r["image"]] = r
    geo = {r["image"]: r for r in F["frame_geometry.tsv"]["recs"]}
    integ = {r["image"]: r for r in F["frame_integrity_audit.pdf"]["recs"]}
    for i in cands:
        o = exif.get(i, 0) or 1
        if i in corr:
            o = corr[i]["orient"]
        g, it = geo[i], integ[i]
        if g["w"] == 0 or g.get("_t5") or it["status"] == "REENCODED":
            w, h = it["dw"], it["dh"]
        else:
            w, h = g["w"], g["h"]
        W, H = (h, w) if o in (6, 8) else (w, h)
        info[i].update(orient=o, W=W, H=H)
    seqm = {r["image"]: r["seq"] for r in F["sequence_membership.xlsx"]["recs"]}
    # --- exclusion evidence
    withdrawn = {}
    seen = set()
    evs = []
    for r in F["image_lifecycle_events.xml"]["recs"]:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        if r["t"] <= CUTOFF and r["type"] in ("withdrawn", "restored"):
            evs.append(r)
    evs.sort(key=lambda r: (r["t"], r["seq_no"]))
    for r in evs:
        withdrawn[r["image"]] = r["type"] == "withdrawn"
    hold = {}
    for r in F["exclusion_policy.docx"]["recs"]:
        if r["status"] == "HOLD":
            hold[r["image"]] = True
        else:
            hold.setdefault(r["image"], False)
    msgs = [m for m in F["privacy_requests.mbox"]["recs"] if m["valid"] and REGISTER_DATE < m["t"] <= CUTOFF]
    msgs.sort(key=lambda m: m["t"])
    for m in msgs:
        if m["action"] == "TAKEDOWN":
            hold[m["image"]] = True
        elif m["action"] == "RELEASE":
            hold[m["image"]] = False
    for r in F["privacy_register_export.tsv"]["recs"]:
        if r["status"] == "LEGAL-HOLD":
            hold[r["image"]] = True
    board = {}
    for name in ("release_governance.docx", "release_governance_v2_signed.docx"):
        for r in F[name]["recs"]:
            if r["t"] <= CUTOFF:
                cur = board.get(r["image"])
                if cur is None or (r["t"], r["id"]) > (cur["t"], cur["id"]):
                    board[r["image"]] = r
    train = []
    for k in TRAIN_SHARDS:
        for r in F[TRAIN_SHARDS[k][0]]["recs"]:
            if not r["purged"] and r["tag"] == "v7-train" and r["h"] != 0:
                train.append(r["h"])
    for r in F["train_hash_index_legacy.txt"]["recs"]:
        if r["tag"] == "v6-core" and not r["purged"] and r["h"] != 0:
            train.append(r["h"])
    for r in F["train_hash_index_f_dedup.parquet"]["recs"]:
        if r["src"] == "g" and not r["purged"] and r["h"] != 0:
            train.append(r["h"])
    index = [dict() for _ in range(5)]
    for h in set(train):
        for c in range(5):
            index[c].setdefault((h >> (13 * c)) & 0x1FFF, []).append(h)
    wv = {}
    for r in F["leakage_waivers.json"]["recs"]:
        key = (r["image"], r["h"])
        cur = wv.get(key)
        if cur is None or (r["decided"], r["id"]) > (cur["decided"], cur["id"]):
            wv[key] = r
    waived = set(k for k, r in wv.items() if r["status"] == "granted" and (r["expires"] is None or r["expires"] > CUTOFF))
    hashes = {r["image"]: r["hash"] for r in F["frame_dhash.parquet"]["recs"]}
    trained_seq = set(r["seq"] for r in F["training_sequence_register.pdf"]["recs"]
                      if r["status"] == "trained" and r["index"] in ("v7-train", "v6-core"))
    # --- annotations
    late = set(b for b, t in E.receipts.items() if t > CUTOFF)
    vend_files = {"NL": [n for n in F if F[n]["kind"] == "nl" and not F[n]["decoy"]],
                  "KS": [n for n in F if F[n]["kind"] == "ks" and not F[n]["decoy"]],
                  "OB": [n for n in F if F[n]["kind"] == "ob" and not F[n]["decoy"]]}
    recs_by_img = {}
    b2 = F["nl_boxes_batch02.csv"]
    for v, names in vend_files.items():
        for n in sorted(names):
            rows = F[n]["recs"]
            if n == "nl_boxes_batch02.csv":
                rows = rows[: b2["present"]] + F["nl_boxes_batch02_reextract.csv"]["recs"][b2["present"]:]
            for r in rows:
                if r["batch"] in late or (r["vendor"] in ("KS", "OB") and E.batches[r["batch"]]["resub"]):
                    continue
                recs_by_img.setdefault(r["image"], []).append(r)
    for n in ("ks_boxes_resubmitted.json", "ob_boxes_resubmitted.xml"):
        for r in F[n]["recs"]:
            if E.batches[r["batch"]]["resub"] and r["batch"] not in late:
                recs_by_img.setdefault(r["image"], []).append(r)
    decisions = {}
    for q in F["labeling_qa_portal.html"]["recs"]:
        k = (q["ann"], q["rev"])
        if k not in decisions or q["t"] >= decisions[k]["t"]:
            decisions[k] = q
    for q in F["labeling_qa_export.xlsx"]["recs"]:
        if q["state"] == "final" and QA_SNAPSHOT < q["t"] <= CUTOFF:
            k = (q["ann"], q["rev"])
            if k not in decisions or q["t"] >= decisions[k]["t"]:
                decisions[k] = q
    errata = {}
    for e in F["annotation_errata_register.md"]["recs"]:
        if e["eff"] <= CUTOFF:
            errata.setdefault(e["ann"], []).append(e)
    for v in errata.values():
        v.sort(key=lambda e: (e["eff"], e["id"]))
    camp_status = {}
    for s in F["relabel_campaign_status.json"]["recs"]:
        if s["t"] <= CUTOFF:
            cur = camp_status.get(s["item"])
            if cur is None or s["t"] >= cur["t"]:
                camp_status[s["item"]] = s
    camp_item = {}
    camp_boxes = {}
    for r in F["relabel_campaign_2026q3.xlsx"]["recs"]:
        if r["_sheet"] == "items":
            camp_item[r["image"]] = r["item"]
        else:
            camp_boxes.setdefault(r["item"], []).append(r)

    def mapping(r):
        if r["vendor"] == "NL":
            return E.nl_x.get((r["project"], r["label"]))
        if r["vendor"] == "OB":
            return E.ob_x.get((r["project"], r["alias"] if "alias" in r else r["label"]))
        for row in E.ks_index.get(r["project"], []):
            if row["code"] == r["label"] and row["from"] <= r["t"] and (row["to"] is None or r["t"] < row["to"]):
                return (row["cls"], row["disp"])
        return None

    vendor_of = {}
    for r in F["data_authority_policy.docx"]["recs"]:
        cur = vendor_of.get(r["image"])
        if cur is None or r["assigned"] >= cur["assigned"]:
            vendor_of[r["image"]] = r

    def gt_for(i):
        item = camp_item.get(i)
        if item and camp_status.get(item, {}).get("status") == "approved":
            out = []
            for b in camp_boxes.get(item, []):
                x1, y1, x2, y2 = b["box"]
                ign = b["crowd"] == 1 or (x2 - x1) * (y2 - y1) < MIN_AREA
                out.append({"gt": b["box_id"], "cls": b["cls"], "box": b["box"], "ignore": ign, "src": "CAMPAIGN"})
            return out, True
        v = vendor_of[i]["vendor"]
        rows = [r for r in recs_by_img.get(i, []) if r["vendor"] == v]
        if not rows:
            return [], False
        by_ann = {}
        for r in rows:
            by_ann.setdefault(r["ann"], []).append(r)
        out = []
        for ann in sorted(by_ann):
            revs = [r for r in by_ann[ann] if decisions.get((ann, r["rev"]), {}).get("decision") != "rejected"]
            if not revs:
                continue
            top = max(revs, key=lambda r: r["rev"])
            if top["status"] != "live":
                continue
            m = mapping(top)
            if m is None:
                continue
            cls, disp = m
            box = top["box"]
            dead = False
            for e in errata.get(ann, []):
                if e["action"] == "VOID":
                    dead = True
                elif e["action"] == "RECLASS":
                    cls = e["value"]
                elif e["action"] == "REBOX":
                    box = e["value"]
            if dead or disp == "drop":
                continue
            ign = disp == "ignore" or top["crowd"] == 1 or (box[2] - box[0]) * (box[3] - box[1]) < MIN_AREA
            out.append({"gt": ann, "cls": cls, "box": box, "ignore": ign, "src": v})
        return out, True

    reasons = {}
    gts = {}
    for i in cands:
        inf = info[i]
        rs = []
        if withdrawn.get(i):
            rs.append("WITHDRAWN")
        if not (WINDOW_START <= inf["t"] < WINDOW_END):
            rs.append("OUT_OF_WINDOW")
        if integ[i]["status"] == "FAIL":
            rs.append("CORRUPT")
        if hold.get(i):
            rs.append("PRIVACY_HOLD")
        if i in board and board[i]["decision"] == "EXCLUDE":
            rs.append("BOARD_OVERRIDE")
        h = hashes.get(i, 0)
        if h:
            best = 99
            cand = set()
            for c in range(5):
                cand.update(index[c].get((h >> (13 * c)) & 0x1FFF, []))
            for th in cand:
                if (i, th) in waived:
                    continue
                d = _popcount(h ^ th)
                if d < best:
                    best = d
            if best == 0:
                rs.append("LEAK_EXACT")
            elif best <= 4:
                rs.append("LEAK_NEAR")
        if seqm.get(i) in trained_seq:
            rs.append("LEAK_SEQUENCE")
        g, labeled = gt_for(i)
        if not labeled:
            rs.append("UNLABELED")
        reasons[i] = rs[0] if rs else None
        gts[i] = g
    evals = [i for i in cands if reasons[i] is None]
    T["eval_images"] = []
    for i in evals:
        inf = info[i]
        T["eval_images"].append([i, seqm[i], inf["camera"], inf["site"], iso_z(inf["t"]), str(inf["W"]), str(inf["H"]),
                                 str(inf["orient"]), str(sum(1 for g in gts[i] if not g["ignore"])),
                                 str(sum(1 for g in gts[i] if g["ignore"]))])
    T["exclusions"] = [[i, reasons[i]] for i in cands if reasons[i] is not None]
    T["ground_truth"] = []
    for i in evals:
        for g in sorted(gts[i], key=lambda g: g["gt"]):
            T["ground_truth"].append([i, g["gt"], g["cls"]] + [str(v) for v in g["box"]] + ["1" if g["ignore"] else "0"])
    # --- detections
    assign = {}
    for r in F["inference_run_registry.html"]["recs"]:
        assign[(r["run"], r["seq"])] = r["node"]
    for r in F["inference_run_registry_mirror.html"]["recs"]:
        if r["seq"] in E.late_seqs:
            assign[(r["run"], r["seq"])] = r["node"]
    rerun = {}
    for r in F["rerun_batches.toml"]["recs"]:
        rerun[(r["run"], r["image"])] = r
    quar = set((r["run"], r["node"], r["image"]) for r in F["node_quarantine_report.pdf"]["recs"] if r["status"] == "quarantined")
    prep = {}
    for n in ("n1", "n2", "n3", "n4", "n5"):
        for r in F["preprocess_%s.log" % n]["recs"]:
            if r["status"] == "ok":
                k = (n, r["run"], r["image"])
                if k not in prep or r["attempt"] > prep[k][0]:
                    prep[k] = (r["attempt"], (r["scale"], r["px"], r["py"]))
    store_rows = {"n6": {}, "n6-replica": {}, "n2-replay": {}}
    for sname, fname in (("n6", "node6_rerun_store.db"), ("n6-replica", "node6_ingest_replica.db"), ("n2-replay", "preds_r3_n2_replay.jsonl")):
        seen_d = set()
        for d in F[fname]["recs"]:
            if (d["run"], d["det"], d["image"]) in seen_d:
                continue
            seen_d.add((d["run"], d["det"], d["image"]))
            store_rows[sname].setdefault((d["run"], d["image"]), []).append(d)
    node_rows = {}
    for (run, node), _x in [((r, n), 0) for r in REVIEW_RUNS for n in NODES]:
        name = pred_file(run, node)[0]
        seen_d = set()
        for d in F[name]["recs"]:
            key = (d["run"], d["det"], d["image"])
            if key in seen_d:
                continue
            seen_d.add(key)
            node_rows.setdefault((node, d["run"], d["image"]), []).append(d)
    calib = {}
    for run in REVIEW_RUNS:
        for cls in CLASSES:
            calib[(run, cls)] = E.calib[(run, cls)]
    T["detections"] = []
    T["_final"] = {}
    recon_det = {}
    for run in REVIEW_RUNS:
        cfg = run_cfg(run)
        thr, nms, md = Fraction(cfg[3]), Fraction(cfg[4]), cfg[5]
        cnt = {"accepted": 0, "after_threshold": 0, "after_nms": 0, "final": 0}
        for i in evals:
            inf = info[i]
            W, H = inf["W"], inf["H"]
            node = assign[(run, seqm[i])]
            rr = rerun.get((run, i))
            if rr is not None and rr["status"] == "completed":
                rows = store_rows[rr["store"]].get((run, i), [])
            else:
                if (run, node, i) in quar:
                    rows = []
                else:
                    rows = node_rows.get((node, run, i), [])
                    if node != "n7" and (node, run, i) not in prep:
                        rows = []
            cand_d = []
            for d in rows:
                if d["score"] < 0:
                    continue
                cls = _canon_label(run, d["label"])
                if cls is None:
                    continue
                x1, y1, x2, y2 = d["box"]
                b = (max(0, min(W, x1)), max(0, min(H, y1)), max(0, min(W, x2)), max(0, min(H, y2)))
                if b[2] <= b[0] or b[3] <= b[1]:
                    continue
                cal = calibrate(calib[(run, cls)], Fraction(d["score"], 1000))
                cand_d.append({"det": d["det"], "cls": cls, "box": b, "cal": cal, "ck": cal.numerator * 10 ** 30 // cal.denominator})
            cnt["accepted"] += len(cand_d)
            cand_d = [d for d in cand_d if d["cal"] >= thr]
            cnt["after_threshold"] += len(cand_d)
            kept = []
            nn, nd = nms.numerator, nms.denominator
            for cls in CLASSES:
                cs = sorted((d for d in cand_d if d["cls"] == cls), key=lambda d: (-d["ck"], d["det"]))
                k2 = []
                for d in cs:
                    ok = True
                    for k in k2:
                        a, u = _iou_pair(d["box"], k["box"])
                        if a * nd > nn * u:
                            ok = False
                            break
                    if ok:
                        k2.append(d)
                kept.extend(k2)
            cnt["after_nms"] += len(kept)
            kept.sort(key=lambda d: (-d["ck"], d["det"]))
            kept = kept[:md]
            cnt["final"] += len(kept)
            T["_final"][(run, i)] = kept
            for d in sorted(kept, key=lambda d: d["det"]):
                T["detections"].append([run, i, "D%09d" % d["det"], d["cls"]] + [str(v) for v in d["box"]] + [fmt6(d["cal"])])
        recon_det[run] = cnt
    # --- metrics
    metrics = {}
    T["class_metrics"] = []
    T["operating_points"] = []
    gt_by = {}
    for i in evals:
        for g in gts[i]:
            gt_by.setdefault((g["cls"], i), [[], []])[1 if g["ignore"] else 0].append(g)
    for v in gt_by.values():
        v[0].sort(key=lambda g: g["gt"])
    for run in REVIEW_RUNS:
        det_by = {}
        for i in evals:
            for d in T["_final"][(run, i)]:
                det_by.setdefault((d["cls"], i), []).append(d)
        for v in det_by.values():
            v.sort(key=lambda d: (-d["ck"], d["det"]))
        for cls in sorted(CLASSES):
            gtc = sum(len(v[0]) for (c, i), v in gt_by.items() if c == cls)
            detc = sum(len(v) for (c, i), v in det_by.items() if c == cls)
            imgs = sorted(i for (c, i) in det_by if c == cls)
            aps = []
            tp50 = fp50 = 0
            outcomes50 = []
            for t in IOU_THRESHOLDS:
                tn, td = t.numerator, t.denominator
                seq = []
                for i in imgs:
                    dets = det_by[(cls, i)]
                    gl, ig = gt_by.get((cls, i), [[], []])
                    used = set()
                    for d in dets:
                        best, bi = None, None
                        for g in gl:
                            if g["gt"] in used:
                                continue
                            a, u = _iou_pair(d["box"], g["box"])
                            if a * td >= tn * u and (best is None or a * best[1] > best[0] * u):
                                best, bi = (a, u), g["gt"]
                        if bi is not None:
                            used.add(bi)
                            seq.append((d["ck"], d["det"], 1, d["cal"]))
                            continue
                        dx = d["box"]
                        darea = (dx[2] - dx[0]) * (dx[3] - dx[1])
                        hit = False
                        for g in ig:
                            iw = min(dx[2], g["box"][2]) - max(dx[0], g["box"][0])
                            ih = min(dx[3], g["box"][3]) - max(dx[1], g["box"][1])
                            if iw > 0 and ih > 0 and iw * ih * td >= tn * darea:
                                hit = True
                                break
                        if not hit:
                            seq.append((d["ck"], d["det"], 0, d["cal"]))
                seq.sort(key=lambda x: (-x[0], x[1]))
                if t == IOU_THRESHOLDS[0]:
                    tp50 = sum(x[2] for x in seq)
                    fp50 = len(seq) - tp50
                    outcomes50 = seq
                if gtc == 0:
                    continue
                tps, ns = [], []
                tp = 0
                for n_, x in enumerate(seq):
                    tp += x[2]
                    tps.append(tp)
                    ns.append(n_ + 1)
                env = list(zip(tps, ns))
                for k in range(len(env) - 2, -1, -1):
                    a, b = env[k + 1]
                    c, d_ = env[k]
                    if a * d_ > c * b:
                        env[k] = env[k + 1]
                s = Fraction(0)
                j = 0
                for k in range(101):
                    while j < len(tps) and tps[j] * 100 < k * gtc:
                        j += 1
                    if j < len(tps):
                        s += Fraction(env[j][0], env[j][1])
                aps.append(s / 101)
            if gtc:
                ap50, ap75, apm = aps[0], aps[5], sum(aps) / 10
                metrics[(run, cls)] = (ap50, ap75, apm)
                T["class_metrics"].append([run, cls, str(gtc), str(detc), str(tp50), str(fp50), fmt6(ap50), fmt6(ap75), fmt6(apm)])
            else:
                T["class_metrics"].append([run, cls, "0", str(detc), str(tp50), str(fp50), "NA", "NA", "NA"])
            tgt = TARGET_PRECISION[cls]
            best = None
            if gtc:
                taus = sorted(set(x[0] for x in outcomes50), reverse=True)
                calof = {x[0]: x[3] for x in outcomes50}
                tp = fp = 0
                k = 0
                for tau in taus:
                    while k < len(outcomes50) and outcomes50[k][0] >= tau:
                        tp += outcomes50[k][2]
                        fp += 1 - outcomes50[k][2]
                        k += 1
                    p = Fraction(tp, tp + fp)
                    rcl = Fraction(tp, gtc)
                    if p >= tgt and (best is None or rcl > best[2] or (rcl == best[2] and calof[tau] > best[0])):
                        best = (calof[tau], p, rcl)
            if best is None:
                T["operating_points"].append([run, cls, fmt6(tgt), "NA", "NA", "NA"])
            else:
                T["operating_points"].append([run, cls, fmt6(tgt), fmt6(best[0]), fmt6(best[1]), fmt6(best[2])])
    # --- leaderboard
    def r6(x):
        return Decimal(fmt6(x))

    lb_runs = []
    maps = {}
    for run in REVIEW_RUNS:
        vals = [metrics[(run, c)] for c in CLASSES if (run, c) in metrics]
        n = len(vals)
        maps[run] = (sum(v[0] for v in vals) / n, sum(v[1] for v in vals) / n, sum(v[2] for v in vals) / n)
    cands_rc = []
    for run in REVIEW_RUNS:
        cfg = run_cfg(run)
        prot = {}
        for c in PROTECTED:
            if (run, c) in metrics and (INCUMBENT, c) in metrics:
                prot[c] = str((r6(metrics[(run, c)][0]) - r6(metrics[(INCUMBENT, c)][0])).quantize(Decimal("0.000001")))
            else:
                prot[c] = "NA"
        if run == INCUMBENT:
            dec = "INCUMBENT"
        else:
            ok = r6(maps[run][2]) - r6(maps[INCUMBENT][2]) >= Decimal("0.005")
            for c in PROTECTED:
                if prot[c] != "NA" and Decimal(prot[c]) < Decimal("-0.010"):
                    ok = False
            dec = "PROMOTE" if ok else "HOLD"
            if ok:
                cands_rc.append((-r6(maps[run][2]), run))
        lb_runs.append({"run_id": run, "model": cfg[1], "map_50": fmt6(maps[run][0]), "map_75": fmt6(maps[run][1]),
                        "map_50_95": fmt6(maps[run][2]), "protected_ap_50_delta": prot, "decision": dec})
    T["leaderboard"] = {"incumbent": INCUMBENT, "runs": lb_runs,
                        "release_candidate": sorted(cands_rc)[0][1] if cands_rc else None}
    # --- reconciliation
    excl = {r: 0 for r in REASONS}
    for i in cands:
        if reasons[i]:
            excl[reasons[i]] += 1
    src = {"CAMPAIGN": 0, "KS": 0, "NL": 0, "OB": 0}
    for i in evals:
        for g in gts[i]:
            src[g["src"]] += 1
    deliveries = {}
    for name in sorted(F):
        if name == "delivery_manifest.toml":
            continue
        spec = F[name]
        n = len(spec["recs"])
        deliveries[name] = {"declared": n, "parsed": spec.get("present", n)}
    T["reconciliation"] = {
        "freeze_list_ids": len(freeze), "candidates": len(cands), "eval_images": len(evals), "excluded": excl,
        "gt_boxes": sum(1 for i in evals for g in gts[i] if not g["ignore"]),
        "ignore_regions": sum(1 for i in evals for g in gts[i] if g["ignore"]),
        "gt_by_source": src, "detections": recon_det, "deliveries": deliveries}
    T["_reasons"] = reasons
    T["_evals"] = evals
    del T["_final"]
    return T

# ----------------------------------------------------------------- serialisation helpers
import csv as _csv


def rid(rec):
    if rec.get("_idv"):
        return rec["_idv"]
    if rec.get("_alias"):
        return rec["_alias"]
    return rec["image"]


def loc_num(s):
    """Render a plain decimal string in the comma-decimal / dot-grouping form."""
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    if "." in s:
        ip, fp = s.split(".")
    else:
        ip, fp = s, "0"
    groups = []
    while len(ip) > 3:
        groups.insert(0, ip[-3:])
        ip = ip[:-3]
    groups.insert(0, ip)
    out = ".".join(groups) + "," + fp
    return "(" + out + ")" if neg else out


def dec2(fr):
    return str(_round_frac(fr, 2))


def dstr(fr, places):
    return str(_round_frac(Fraction(fr), places))


def _h32(*vals):
    h = 2166136261
    for v in vals:
        for ch in str(v).encode():
            h = ((h ^ ch) * 16777619) & 0xFFFFFFFF
    return h


def model_box(rec, prep, half=False):
    """Model-space x1, y1, x2, y2 (Fractions on a 0.01 grid) that invert to the canonical box."""
    sc, px, py = prep
    out = []
    pads = (px, py, px, py)
    for k, X in enumerate(rec["box"]):
        pad = pads[k]
        exact = X * sc + pad
        j = Fraction(int(_h32(rec["det"], k) % 41) - 20, 100) * sc
        cand = Fraction(round_half_even_int((exact + j) * 100), 100)
        if round_half_even_int((cand - pad) / sc) != X:
            cand = Fraction(round_half_even_int(exact * 100), 100)
        out.append(cand)
    if half:
        for k, X in enumerate(rec["box"]):
            if X % 2 != 0:
                continue
            pad = pads[k]
            for target in (Fraction(2 * X + 1, 2), Fraction(2 * X - 1, 2)):
                v = target * sc + pad
                if (v * 100).denominator == 1:
                    out[k] = v
                    rec["_half_done"] = True
                    return out
    return out


def cxcywh(mb):
    x1, y1, x2, y2 = mb
    return ((x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1)


def cxcywh_ok(mb, box, prep):
    sc, px, py = prep
    cx, cy, w, h = [Fraction(round_half_even_int(v * 100), 100) for v in cxcywh(mb)]
    back = (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
    pads = (px, py, px, py)
    return all(round_half_even_int((back[k] - pads[k]) / sc) == box[k] for k in range(4)), (cx, cy, w, h)


def stored_box(box, orient, W, H):
    """Upright canonical box -> stored-frame box (W, H are stored dims)."""
    x1, y1, x2, y2 = box
    if orient == 1:
        return box
    if orient == 3:
        return (W - x2, H - y2, W - x1, H - y1)
    if orient == 6:
        return (y1, H - x2, y2, H - x1)
    return (W - y2, x1, W - y1, x2)


def vendor_coords(E, rec, fmt, frame):
    im = E.images[rec["image"]]
    sw, sh = im["dw"], im["dh"]
    W, H = upright(im)
    box = rec["box"]
    fw, fh = W, H
    if frame == "stored":
        box = stored_box(box, im["orient"], sw, sh)
        fw, fh = sw, sh
    x1, y1, x2, y2 = box
    if fmt == "xywh":
        return [str(x1), str(y1), str(x2 - x1), str(y2 - y1)]
    if fmt == "xyxy":
        return [str(x1), str(y1), str(x2), str(y2)]
    if fmt == "xyxy_inclusive":
        return [str(x1), str(y1), str(x2 - 1), str(y2 - 1)]
    vals = None
    if rec.get("_t12") and frame == "upright":
        opts = []
        if x1 % 2 == 0:
            opts += [(x1 + Fraction(1, 2), y1, x2, y2), (x1 - Fraction(1, 2), y1, x2, y2)]
        if y1 % 2 == 0:
            opts += [(x1, y1 + Fraction(1, 2), x2, y2), (x1, y1 - Fraction(1, 2), x2, y2)]
        for a, b, c, d in opts:
            a, b, c, d = Fraction(a), Fraction(b), Fraction(c), Fraction(d)
            cand = ((a + c) / (2 * fw), (b + d) / (2 * fh), (c - a) / fw, (d - b) / fh)
            if all((v * 10 ** 6).denominator == 1 for v in cand):
                vals = cand
                rec["_half_done"] = True
                break
    if vals is None:
        vals = (Fraction(x1 + x2, 2 * fw), Fraction(y1 + y2, 2 * fh), Fraction(x2 - x1, fw), Fraction(y2 - y1, fh))
        vals = tuple(Fraction(round_half_even_int(v * 10 ** 6), 10 ** 6) for v in vals)
    if rec.get("_t2"):
        return [dstr(vals[0] * fw, 4), dstr(vals[1] * fh, 4), dstr(vals[2] * fw, 4), dstr(vals[3] * fh, 4)]
    return [dstr(v, 6) for v in vals]


NOTE_PLAIN = ["", "", "", "checked", "", "night", "", "rain", "", "glare"]


def _note(rec, k):
    if rec.get("_t9"):
        return 'relabelled, see "QA" ticket\n%d' % (k % 9000)
    if rec.get("_t10"):
        return "Z\u00fcrich depot"
    return NOTE_PLAIN[k % 10]


def write_table(path, header, rows, recs, delim=",", bom=False, eol="\n", comments=(), alt_header=None, encoding="utf-8"):
    """rows[k] belongs to recs[k]; flags on the record drive header drift, quoting and encoding traps."""
    out = bytearray()
    if bom:
        out += b"\xef\xbb\xbf"
    for c in comments:
        out += (c + eol).encode(encoding)
    cur_order = list(range(len(header)))
    names = list(header)

    def line(cells, enc, term):
        buf = io.StringIO()
        w = _csv.writer(buf, delimiter=delim, lineterminator=term, quoting=_csv.QUOTE_MINIMAL)
        w.writerow(cells)
        try:
            return buf.getvalue().encode(enc)
        except UnicodeEncodeError:
            return buf.getvalue().encode("utf-8")

    out += line(names, encoding, eol)
    for k, (row, rec) in enumerate(zip(rows, recs)):
        if rec.get("_t8") and alt_header:
            perm = list(range(len(header)))
            perm = perm[1:] + perm[:1]
            names = [alt_header.get(header[p], header[p]) for p in perm]
            cur_order = perm
            out += line(names, encoding, eol)
        cells = [row[p] for p in cur_order]
        if rec.get("_t9") and k % 2 == 0:
            cells = cells + [""]
        enc = encoding
        term = eol
        if rec.get("_t10"):
            enc = "latin-1" if encoding == "utf-8" else "utf-8"
            term = "\r\n" if eol == "\n" else "\n"
        out += line(cells, enc, term)
    Path(path).write_bytes(bytes(out))


def _xml_esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def _col(n):
    s = ""
    n += 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def write_xlsx(path, sheets):
    """sheets: list of (name, list of rows); a row is a list of str/int/Fraction-free floats."""
    def cell(ref, v):
        if isinstance(v, bool):
            v = int(v)
        if isinstance(v, (int,)) or (isinstance(v, float)):
            return '<c r="%s"><v>%s</v></c>' % (ref, repr(v) if isinstance(v, float) else v)
        return '<c r="%s" t="inlineStr"><is><t xml:space="preserve">%s</t></is></c>' % (ref, _xml_esc(v))

    zf = zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED)
    def put(name, data):
        zi = zipfile.ZipInfo(name, date_time=(2026, 11, 14, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(zi, data)
    ct = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
          '<Default Extension="xml" ContentType="application/xml"/>',
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>']
    for k in range(len(sheets)):
        ct.append('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (k + 1))
    ct.append("</Types>")
    put("[Content_Types].xml", "".join(ct))
    put("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>']
    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">']
    for k, (name, _) in enumerate(sheets):
        wb.append('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (_xml_esc(name), k + 1, k + 1))
        rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (k + 1, k + 1))
    wb.append("</sheets></workbook>")
    rels.append("</Relationships>")
    put("xl/workbook.xml", "".join(wb))
    put("xl/_rels/workbook.xml.rels", "".join(rels))
    for k, (name, rows) in enumerate(sheets):
        parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for r, row in enumerate(rows):
            parts.append('<row r="%d">' % (r + 1))
            for c, v in enumerate(row):
                if v is None or v == "":
                    continue
                parts.append(cell("%s%d" % (_col(c), r + 1), v))
            parts.append("</row>")
        parts.append("</sheetData></worksheet>")
        put("xl/worksheets/sheet%d.xml" % (k + 1), "".join(parts))
    zf.close()


def xlsx_rows(header, rows, recs, alt_header):
    out = [list(header)]
    order = list(range(len(header)))
    for row, rec in zip(rows, recs):
        if rec.get("_t8") and alt_header:
            order = order[1:] + order[:1]
            out.append([alt_header.get(header[p], header[p]) for p in order])
        out.append([row[p] for p in order])
    return out


def write_docx(path, blocks):
    """blocks: ("h1"|"h2"|"p", text) or ("table", [header, rows...])."""
    body = []
    for kind, val in blocks:
        if kind in ("h1", "h2"):
            style = "Heading1" if kind == "h1" else "Heading2"
            body.append('<w:p><w:pPr><w:pStyle w:val="%s"/></w:pPr><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % (style, _xml_esc(val)))
        elif kind == "p":
            body.append('<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>' % _xml_esc(val))
        else:
            t = ['<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>']
            for row in val:
                t.append("<w:tr>")
                for c in row:
                    t.append('<w:tc><w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p></w:tc>' % _xml_esc(c))
                t.append("</w:tr>")
            t.append("</w:tbl>")
            body.append("".join(t))
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
           + "".join(body) + '<w:sectPr/></w:body></w:document>')
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
              '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>'
              '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/></w:style>'
              '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/></w:style>'
              '<w:style w:type="table" w:default="1" w:styleId="TableNormal"><w:name w:val="Normal Table"/></w:style></w:styles>')
    zf = zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED)
    def put(name, data):
        zi = zipfile.ZipInfo(name, date_time=(2026, 11, 14, 0, 0, 0))
        zi.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(zi, data)
    put("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
    put("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    put("word/_rels/document.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    put("word/document.xml", doc)
    put("word/styles.xml", styles)
    zf.close()


def write_pdf(path, lines):
    """Plain text-layer PDF: Courier 7pt, 70 lines per page."""
    per = 70
    pages = [lines[k:k + per] for k in range(0, max(1, len(lines)), per)] or [[]]
    objs = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    kids = []
    n_pages = len(pages)
    font_id = 3
    objs.append(None)
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    for k, pg in enumerate(pages):
        content = ["BT", "/F1 7 Tf", "9 TL", "28 812 Td"]
        for ln in pg:
            s = ln.encode("cp1252", "replace").decode("latin-1")
            s = s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            content.append("(%s) Tj T*" % s)
        content.append("ET")
        data = "\n".join(content).encode("latin-1")
        stream = zlib.compress(data, 6)
        cid = len(objs) + 1
        objs.append(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(stream) + stream + b"\nendstream")
        pid = len(objs) + 1
        objs.append(("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /CropBox [0 0 595 842] /Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>" % (font_id, cid)).encode())
        kids.append(pid)
    objs[1] = ("<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join("%d 0 R" % p for p in kids), n_pages)).encode()
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offs = []
    for k, o in enumerate(objs):
        offs.append(len(out))
        out += b"%d 0 obj\n" % (k + 1) + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for o in offs:
        out += b"%010d 00000 n \n" % o
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xref)
    Path(path).write_bytes(bytes(out))


def pdf_table_lines(title, prose, header, rows, errata=None):
    lines = [title, ""]
    for p in prose:
        lines.extend(_wrap(p, 120))
        lines.append("")
    lines.append("APPENDIX REGISTER")
    lines.append(" | ".join(header))
    for r in rows:
        lines.append(" | ".join(r))
    lines.append("END OF REGISTER")
    if errata:
        lines.append("")
        lines.append("ERRATA TO THE REGISTER")
        lines.extend(errata)
    return lines


def _wrap(text, width):
    words = text.split()
    out, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            out.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        out.append(cur)
    return out


def md_doc(title, sections, header, rows, errata=None, appendix_title="Appendix A - Register"):
    out = ["# " + title, ""]
    for h, paras in sections:
        out.append("## " + h)
        out.append("")
        for p in paras:
            out.append(p)
            out.append("")
    out.append("## " + appendix_title)
    out.append("")
    out.append("| " + " | ".join(header) + " |")
    out.append("|" + "---|" * len(header))
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    out.append("")
    if errata:
        out.append("## Errata to the register")
        out.append("")
        out.extend(errata)
        out.append("")
    return "\n".join(out)


def html_doc(title, sections, tables, appendix_title, header, rows, errata=None, note=None):
    h = ["<!DOCTYPE html>", "<html><head><meta charset=\"utf-8\"><title>%s</title></head><body>" % _xml_esc(title),
         "<h1>%s</h1>" % _xml_esc(title)]
    if note:
        h.append('<p class="banner">%s</p>' % _xml_esc(note))
    for hd, paras in sections:
        h.append("<h2>%s</h2>" % _xml_esc(hd))
        for p in paras:
            h.append("<p>%s</p>" % _xml_esc(p))
    for tt, thead, trows in tables:
        h.append("<h2>%s</h2>" % _xml_esc(tt))
        h.append("<table><thead><tr>%s</tr></thead><tbody>" % "".join("<th>%s</th>" % _xml_esc(c) for c in thead))
        for r in trows:
            h.append("<tr>%s</tr>" % "".join("<td>%s</td>" % _xml_esc(c) for c in r))
        h.append("</tbody></table>")
    h.append("<h2>%s</h2>" % _xml_esc(appendix_title))
    h.append('<table class="register"><thead><tr>%s</tr></thead><tbody>' % "".join("<th>%s</th>" % _xml_esc(c) for c in header))
    for r in rows:
        h.append("<tr>%s</tr>" % "".join("<td>%s</td>" % _xml_esc(c) for c in r))
    h.append("</tbody></table>")
    if errata:
        h.append("<h2>Errata to the register</h2><ul>")
        for e in errata:
            h.append("<li>%s</li>" % _xml_esc(e))
        h.append("</ul>")
    h.append("</body></html>")
    return "\n".join(h) + "\n"


def docx_blocks(title, sections, header, rows, errata=None, appendix_title="Appendix - Register", extra_tables=()):
    b = [("h1", title)]
    for hd, paras in sections:
        b.append(("h2", hd))
        for p in paras:
            b.append(("p", p))
    for tt, thead, trows in extra_tables:
        b.append(("h2", tt))
        b.append(("table", [thead] + trows))
    b.append(("h2", appendix_title))
    b.append(("table", [header] + rows))
    if errata:
        b.append(("h2", "Errata to the register"))
        for e in errata:
            b.append(("p", e))
    return b

# ----------------------------------------------------------------- per-file writers
def _t3(rec, t, default_off=0):
    if rec.get("_t3"):
        return iso_off(t, 330 if (_h32(t) % 2) else -300)
    return iso_off(t, default_off) if default_off else iso_z(t)


def _num(rec, s):
    return loc_num(s) if rec.get("_t4") else s


def _cam(rec, c):
    if rec.get("_t1c"):
        return c.lower().replace("-", " ") if _h32(c, rec.get("date", 0)) % 2 else c.lower()
    return c


def _seqid(rec, s):
    if rec.get("_t1s"):
        return s.lower() if _h32(s) % 2 else s.replace("-", "")
    return s


def _proj(rec, p):
    return p.lower() if rec.get("_t1p") else p


def _ann(rec, a):
    if rec.get("_t1a"):
        return " " + a.lower() + " "
    return a


def _batch(rec, b):
    return b.lower() if rec.get("_t1b") else b


def _date(t):
    return wall(t).strftime("%Y-%m-%d")


def _local_str(t, style):
    d = wall(t)
    return d.strftime("%Y-%m-%d %H:%M:%S") if style == 0 else d.strftime("%Y-%m-%dT%H:%M:%S")


def write_estate(E, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    F = E.files
    for name in sorted(F):
        spec = F[name]
        fn = WRITERS[spec["kind"]]
        fn(E, spec, out / name)
    return out


def _w_frames(E, spec, path):
    name = spec["name"]
    recs = spec["recs"]
    if name == "frames_index_west.csv":
        header = ["frame", "camera", "local_time", "fold", "note"]
        rows = [[rid(r), _cam(r, r["camera"]), _local_str(r["local"], 1), "" if r["fold"] is None else str(r["fold"]), _note(r, k)]
                for k, r in enumerate(recs)]
        write_table(path, header, rows, recs, eol="\n", alt_header={"frame": "image_id", "camera": "camera_id", "local_time": "captured_local"})
    elif name == "frames_index_east.csv":
        header = ["image_id", "camera_id", "captured_local", "dst_fold", "note"]
        rows = [[rid(r), _cam(r, r["camera"]), _local_str(r["local"], 0), "" if r["fold"] is None else str(r["fold"]), _note(r, k)]
                for k, r in enumerate(recs)]
        write_table(path, header, rows, recs, bom=True, eol="\r\n", alt_header={"image_id": "frame", "camera_id": "camera", "captured_local": "local_time"})
    else:
        header = ["image_id", "camera_id", "captured_local", "captured_utc", "dst_fold"]
        rows = [[rid(r), r["camera"], _local_str(r["local"], 0), "" if r.get("void") else iso_z(r["utc_naive"]), "" if r["fold"] is None else str(r["fold"])]
                for r in recs]
        write_table(path, header, rows, recs, comments=["# ingest-replica re-export of the east frames index (replica build 2026-11-13).",
                                                         "# captured_utc is derived by the replica with each site's standard offset."],
                    alt_header={"image_id": "frame", "camera_id": "camera"})


def _w_geometry(E, spec, path):
    recs = spec["recs"]
    rows = []
    for k, r in enumerate(recs):
        w, h, sc = r["w"], r["h"], 1
        if r.get("_t5"):
            w, h = 0, 0
        elif r.get("_t2"):
            w, h, sc = w // 2, h // 2, 2
        rows.append([rid(r), _num(r, str(w)), _num(r, str(h)), str(sc), str(r["bytes"])])
    write_table(path, ["image_id", "stored_width", "stored_height", "dim_scale", "file_bytes"], rows, recs, delim="\t",
                alt_header={"image_id": "frame", "stored_width": "width_px", "stored_height": "height_px"})


def _w_exif(E, spec, path):
    out = bytearray()
    for r in spec["recs"]:
        o = 0 if r.get("_t5") else r["orient"]
        obj = {"image": rid(r), "exif_orientation": o, "scanner": "exiftool-12.76"}
        if r.get("_t10"):
            obj["site_note"] = "Z\u00fcrich"
            out += json.dumps(obj, ensure_ascii=False).encode("latin-1") + b"\r\n"
        else:
            out += json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n"
    path.write_bytes(bytes(out))


def _parquet(path, cols):
    import pyarrow as pa
    import pyarrow.parquet as pq
    tbl = pa.table(cols)
    pq.write_table(tbl, str(path), compression="snappy")


def _signed(h):
    return h - (1 << 64) if h >= (1 << 63) else h


def _w_dhash(E, spec, path):
    ids, vals, order = [], [], []
    for r in spec["recs"]:
        h = r["hash"]
        bo = "le"
        if r.get("_t2"):
            h = int.from_bytes(h.to_bytes(8, "little"), "big")
            bo = "be"
        ids.append(rid(r))
        vals.append(_signed(h))
        order.append(bo)
    import pyarrow as pa
    _parquet(path, {"image_id": pa.array(ids, pa.string()), "dhash": pa.array(vals, pa.int64()), "byte_order": pa.array(order, pa.string())})


def _w_seqmem(E, spec, path):
    sheets = []
    for sh in ("east", "west"):
        recs = [r for r in spec["recs"] if r["_sheet"] == sh]
        rows = [[rid(r), r["seq"], _num(r, str(r["frame"])) if r.get("_t4") else r["frame"]] for r in recs]
        sheets.append((sh, xlsx_rows(["image_id", "sequence_id", "frame_index"], rows, recs,
                                     {"image_id": "frame", "sequence_id": "sequence", "frame_index": "frame_no"})))
    write_xlsx(path, sheets)


def _w_lifecycle(E, spec, path):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<lifecycle source="image-catalogue" exported="2026-11-13T06:00:00Z">']
    for r in spec["recs"]:
        at = iso_off(r["t"], r["off"]) if not r.get("_t3") else iso_off(r["t"], -420)
        lines.append('  <event id="%s" seq="%d" image="%s" type="%s" at="%s"/>' % (r["id"], r["seq_no"], _xml_esc(rid(r)), r["type"], at))
    lines.append("</lifecycle>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _errata_lines(recs, keyf, valf, stale_note):
    out = []
    for r in recs:
        if r.get("_t14"):
            out.append("%s: %s. %s" % (keyf(r), valf(r), stale_note))
    return out


def _w_integrity(E, spec, path):
    rows, errata = [], []
    for r in spec["recs"]:
        st, dw, dh = r["status"], str(r["dw"]), str(r["dh"])
        if r.get("_t5"):
            st, dw, dh = "N/A", "-", "-"
        if r.get("_t14"):
            errata.append("Line %s: status is %s (re-audit 2026-11-10)." % (rid(r), st))
            st = "FAIL" if st != "FAIL" else "PASS"
        rows.append([rid(r), st, dw, dh])
    write_pdf(path, pdf_table_lines("FRAME INTEGRITY AUDIT - Q3 2026 EVALUATION CANDIDATES", PROSE["frame_integrity_audit.pdf"],
                                    ["IMAGE_ID", "STATUS", "DECODED_W", "DECODED_H"], rows, errata))


def _w_corrections(E, spec, path):
    rows, errata = [], []
    for r in spec["recs"]:
        o = r["orient"]
        if r.get("_t14"):
            errata.append("Correction %s: orientation is %d." % (r["id"], o))
            o = {1: 6, 6: 1, 3: 8, 8: 3}[o]
        rows.append([r["id"], rid(r), str(o), r["status"], _t3(r, r["t"])])
    write_pdf(path, pdf_table_lines("ORIENTATION CORRECTIONS REGISTER", PROSE["orientation_corrections.pdf"],
                                    ["CORRECTION_ID", "IMAGE_ID", "ORIENTATION", "STATUS", "DECIDED_AT"], rows, errata))


def _w_aliases(E, spec, path):
    lines = ["; legacy image identifier aliases (catalogue migration 2026-08)", "[homoglyphs]"]
    for ch in sorted(HOMOGLYPHS):
        lines.append("U+%04X = %s" % (ord(ch), HOMOGLYPHS[ch]))
    lines.append("")
    lines.append("[aliases]")
    raw = bytearray("\n".join(lines).encode("utf-8") + b"\n")
    for r in spec["recs"]:
        tgt = r["target"]
        if r.get("_t1t") and tgt.startswith("IMG"):
            tgt = "img-" + tgt[3:]
        line = "%s = %s" % (r["alias"], tgt)
        if r.get("_t9"):
            line += " ; migrated in batch M-%02d" % (_h32(r["alias"]) % 40)
        if r.get("_t10"):
            raw += ("; reviewed at Z\u00fcrich depot\r\n").encode("latin-1")
        raw += (line + "\n").encode("utf-8")
    path.write_bytes(bytes(raw))


def _w_freeze(E, spec, path):
    rows, errata = [], []
    for r in spec["recs"]:
        iid = rid(r)
        if r.get("_t14"):
            n = int(r["image"][3:])
            stale = "IMG%07d" % (n + 9 if n < 9999990 else n - 9)
            errata.append("Row listing %s is a transcription error; the frozen image is %s." % (stale, r["image"]))
            iid = stale
        if r.get("_struck"):
            iid = "~~%s~~" % iid
        rows.append([iid, r["batch"]])
    path.write_text(md_doc("Perception Evaluation Standard v3 (PES-3)", PROSE["eval_standard_v3.md"], ["image_id", "freeze_batch"],
                           rows, errata, appendix_title="Appendix A - Frozen candidate register"), encoding="utf-8")


def _w_amend(E, spec, path):
    rows, errata = [], []
    for n, r in enumerate(spec["recs"]):
        iid = rid(r)
        if r.get("_t14"):
            errata.append("Row %d (%s): action is %s." % (n + 1, r["image"], r["action"]))
        rows.append([iid, r["action"] if not r.get("_t14") else ("remove" if r["action"] == "add" else "add"), r["status"]])
    path.write_text(md_doc("Perception Evaluation Standard v3.1 (PES-3.1) - DRAFT", PROSE["eval_standard_v3_1_draft.md"],
                           ["image_id", "action", "status"], rows, errata, appendix_title="Appendix A' - Freeze amendments"), encoding="utf-8")


def _ics_dt(t):
    return wall(t).strftime("%Y%m%dT%H%M%SZ")


def _w_ics(E, spec, path):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//skye fleet ops//clock sync//EN", "CALSCALE:GREGORIAN"]
    for r in spec["recs"]:
        sk = r["skew"]
        if r["unit"] == "ms":
            val = "skew_ms=%+d" % (sk * 1000)
        else:
            val = "skew_s=%+d" % sk
            if r.get("_t4"):
                val = "skew_s=" + (("(%s)" % loc_num(str(-sk))[0:]) if sk < 0 else loc_num(str(sk)))
                if sk < 0:
                    val = "skew_s=(" + loc_num(str(-sk)) + ")"
        lines += ["BEGIN:VEVENT", "UID:%s@clocksync.skye.example" % r["uid"], "DTSTAMP:20261113T060000Z",
                  "DTSTART:%s" % _ics_dt(r["start"]), "DTEND:%s" % _ics_dt(r["end"]),
                  "SUMMARY:CLOCKSYNC %s" % _cam(r, r["camera"]), "DESCRIPTION:%s" % val, "STATUS:%s" % r["status"], "END:VEVENT"]
    lines.append("END:VCALENDAR")
    path.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))


def _off(m, compact=False):
    s = "+" if m >= 0 else "-"
    a = abs(m)
    return ("%s%02d%02d" if compact else "%s%02d:%02d") % (s, a // 60, a % 60)


def _w_roster(E, spec, path):
    ops = spec["decoy"]
    lines = []
    if ops:
        lines += ["# Fleet-ops working copy of the deployment roster (exported 2026-11-13 from the ops planner).",
                  "# Maintained by hand for cameras not yet on the main roster; switch rows are not carried for the rest."]
    lines.append("roster:")
    for r in spec["recs"]:
        comp = bool(r.get("_t4"))
        lines.append("  - camera: %s" % _cam(r, r["camera"]))
        lines.append("    date: %s" % r["date"].isoformat())
        lines.append("    site: %s" % r["site"])
        lines.append('    utc_offset: "%s"' % _off(r["off"], comp))
        if r["switch"] is not None:
            lines.append('    switch_local: "%02d:%02d:%02d"' % (r["switch"] // 3600, r["switch"] % 3600 // 60, r["switch"] % 60))
            lines.append('    offset_after: "%s"' % _off(r["after"], comp))
        if r.get("inactive"):
            lines.append("    active: false")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _hexs(h):
    return "%016x" % h


def _w_train(E, spec, path):
    k = spec.get("shard")
    recs = spec["recs"]
    fmt = spec["fmt"]
    import pyarrow as pa
    if spec["kind"] == "legacy":
        lines = ["# skye-v6 training index (legacy). Columns: dhash_hex(1-16) dataset(18-29) flag(31). Flag A=active P=purged."]
        raw = bytearray(("\n".join(lines) + "\n").encode())
        for r in recs:
            hx = _hexs(r["h"]).upper() if r.get("_t2") else _hexs(r["h"])
            ln = "%-16s %-12s %s" % (hx, r["tag"], "P" if r["purged"] else "A")
            raw += (ln + ("\r\n" if r.get("_t10") else "\n")).encode()
        path.write_bytes(bytes(raw))
        return
    if spec["kind"] == "fdedup":
        _parquet(path, {"dhash_hex": pa.array([("0x" + _hexs(r["h"]).upper()) if r.get("_t2") else _hexs(r["h"]) for r in recs], pa.string()),
                        "source_shard": pa.array([r["src"] for r in recs], pa.string()),
                        "purged": pa.array([bool(r["purged"]) for r in recs], pa.bool_())})
        return
    if k == "a":
        _parquet(path, {"dhash_hex": pa.array([("0x" + _hexs(r["h"]).upper()) if r.get("_t2") else _hexs(r["h"]) for r in recs], pa.string()),
                        "status": pa.array(["purged" if r["purged"] else "active" for r in recs], pa.string()),
                        "set_tag": pa.array([r["tag"] for r in recs], pa.string())})
    elif k == "b":
        rows = [[("0x" + _hexs(r["h"])) if r.get("_t2") else str(r["h"]), "P" if r["purged"] else "A", r["tag"], ""] for r in recs]
        write_table(path, ["dhash_u64", "state", "set_tag", "note"], rows, recs, alt_header={"dhash_u64": "hash", "state": "status"})
    elif k == "c":
        if path.exists():
            path.unlink()
        con = sqlite3.connect(str(path))
        con.execute("CREATE TABLE train_hashes (h TEXT NOT NULL, purged INTEGER NOT NULL, set_tag TEXT NOT NULL)")
        con.executemany("INSERT INTO train_hashes VALUES (?,?,?)",
                        [((_hexs(r["h"]).lstrip("0") or "0").lower() if r.get("_t2") else _hexs(r["h"]).upper(), 1 if r["purged"] else 0, r["tag"]) for r in recs])
        con.commit()
        con.close()
    elif k == "d":
        raw = bytearray()
        for r in recs:
            hx = _hexs(r["h"]).upper() if r.get("_t2") else _hexs(r["h"])
            ln = "%-16s %-8s %s" % (hx, r["tag"], "P" if r["purged"] else "A")
            raw += (ln + ("\r\n" if r.get("_t10") else "\n")).encode()
        path.write_bytes(bytes(raw))
    elif k == "e":
        raw = bytearray()
        for r in recs:
            obj = {"purged": bool(r["purged"]), "tag": r["tag"]}
            if r.get("_t2"):
                obj["h_dec"] = str(r["h"])
            else:
                obj["h"] = "0x" + _hexs(r["h"])
            raw += json.dumps(obj).encode() + (b"\r\n" if r.get("_t10") else b"\n")
        path.write_bytes(bytes(raw))
    elif k == "h":
        raw = bytearray()
        for r in recs:
            val = ("x" + _hexs(r["h"])).rjust(20) if r.get("_t2") else str(r["h"]).rjust(20)
            ln = "%s %-8s %s" % (val, r["tag"], "P" if r["purged"] else "A")
            raw += (ln + ("\r\n" if r.get("_t10") else "\n")).encode()
        path.write_bytes(bytes(raw))


def _w_trainseq(E, spec, path):
    rows, errata = [], []
    for r in spec["recs"]:
        st = r["status"]
        if r.get("_t14"):
            errata.append("Sequence %s: status is %s." % (r["seq"], st))
            st = "held-out" if st == "trained" else "trained"
        rows.append([_seqid(r, r["seq"]), st, r["index"]])
    write_pdf(path, pdf_table_lines("TRAINING SEQUENCE REGISTER", PROSE["training_sequence_register.pdf"],
                                    ["SEQUENCE_ID", "STATUS", "TRAINING_INDEX"], rows, errata))


def _w_waivers(E, spec, path):
    out = []
    for r in spec["recs"]:
        out.append({"waiver_id": r["id"], "image": rid(r), "train_dhash": _hexs(r["h"]), "status": r["status"],
                    "decided_at": _t3(r, r["decided"]), "expires_at": None if r["expires"] is None else iso_z(r["expires"])})
    path.write_text(json.dumps({"issuer": "leakage review board", "waivers": out}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _w_privacy_reg(E, spec, path):
    rows, errata = [], []
    for r in spec["recs"]:
        st = r["status"]
        if r.get("_t14"):
            errata.append("Request %s: status is %s." % (r["id"], st))
            st = "RELEASED" if st == "HOLD" else "HOLD"
        rows.append([r["id"], rid(r), st])
    write_docx(path, docx_blocks("Evaluation Exclusion Policy (EXP-4)", PROSE["exclusion_policy.docx"], ["REQUEST_ID", "IMAGE_ID", "STATUS"],
                                 rows, errata, appendix_title="Appendix - Privacy takedown register (as of 2026-10-15)"))


def _w_privacy_export(E, spec, path):
    recs = spec["recs"]
    rows = [[r["id"], rid(r), r["status"], _note(r, k)] for k, r in enumerate(recs)]
    write_table(path, ["request_id", "image_id", "status", "note"], rows, recs, delim="\t",
                comments=["# privacy desk spreadsheet export (unofficial working copy, 2026-11-11)"],
                alt_header={"request_id": "request", "image_id": "frame"})


def _w_mbox(E, spec, path):
    out = []
    for k, r in enumerate(spec["recs"]):
        off = SITES[E.images[r["image"]]["site"]][0] if r["image"] in E.images else 0
        if r.get("_t3"):
            off = 330
        d = wall(r["t"] + off * 60)
        sign = "+" if off >= 0 else "-"
        datestr = d.strftime("%a, %d %b %Y %H:%M:%S ") + "%s%02d%02d" % (sign, abs(off) // 60, abs(off) % 60)
        sender = "takedowns@privacy-office.skye.example" if r["valid"] else "relay@mailhub.partner.example"
        subj = "%s %s" % (r["action"], rid(r))
        if not r["valid"]:
            subj = "Fwd: " + subj
        out.append("From %s %s" % (sender, wall(r["t"]).strftime("%a %b %d %H:%M:%S %Y")))
        out.append("From: %s" % sender)
        out.append("To: eval-board@skye.example")
        out.append("Date: %s" % datestr)
        if not subj.isascii():
            import email.header
            subj = email.header.Header(subj, "utf-8").encode()
        out.append("Subject: %s" % subj)
        out.append("Message-ID: <pr-%d-%d@skye.example>" % (k, _h32(r["image"], r["t"])))
        out.append("")
        out.append("Request reference %s." % ("routine acknowledgement" if r["action"] == "ACK" else r["action"].lower()))
        out.append(">From the privacy desk queue.")
        out.append("")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _w_board(E, spec, path):
    rows, errata = [], []
    for r in spec["recs"]:
        dec = r["decision"]
        if r.get("_t14"):
            errata.append("Decision %s: decision is %s." % (r["id"], dec))
            dec = "CONFIRM" if dec == "EXCLUDE" else "EXCLUDE"
        rows.append([r["id"], rid(r), dec, _date(r["t"])])
    key = spec["name"]
    title = "Release Governance Policy (RGP-7)" if not spec["decoy"] else "Release Governance Policy (RGP-7) - Version 2, signed"
    write_docx(path, docx_blocks(title, PROSE[key], ["DECISION_ID", "IMAGE_ID", "DECISION", "DECIDED_ON"], rows, errata,
                                 appendix_title="Appendix - Board image decisions"))


def _w_assign(E, spec, path):
    rows, errata = [], []
    for r in spec["recs"]:
        v = r["vendor"]
        if r.get("_t14"):
            errata.append("Image %s assigned on %s: vendor is %s." % (r["image"], _date(r["assigned"]), v))
            v = {"NL": "KS", "KS": "OB", "OB": "NL"}[v]
        rows.append([rid(r), v, _date(r["assigned"])])
    write_docx(path, docx_blocks("Data Authority Policy (DAP-2)", PROSE["data_authority_policy.docx"], ["IMAGE_ID", "VENDOR", "ASSIGNED_ON"],
                                 rows, errata, appendix_title="Appendix - Vendor assignment register"))


FMT_SYNONYM = {"xywh": "x,y,w,h", "xyxy": "x1,y1,x2,y2", "cxcywh_norm": "cx,cy,w,h/norm", "xyxy_inclusive": "x1,y1,x2,y2/incl"}


def _w_batches(E, spec, path):
    rows, errata = [], []
    for r in spec["recs"]:
        fmt = r.get("fmt_table", r["fmt"]) if r.get("errata") else r["fmt"]
        if r.get("errata"):
            errata.append("Batch %s was delivered as %s in the %s frame; the register row is wrong." % (r["batch"], r["fmt"], r["frame"]))
        if r.get("_t2"):
            fmt = FMT_SYNONYM[fmt]
        frame = "-" if r.get("_t5") else r["frame"]
        rows.append([_batch(r, r["batch"]), r["vendor"], fmt, frame, "Y" if r["resub"] else "N"])
    write_docx(path, docx_blocks("Annotation Batch Conventions (ABC-5)", PROSE["annotation_batch_conventions.docx"],
                                 ["BATCH_ID", "VENDOR", "COORD_FORMAT", "FRAME", "RESUBMISSION_ACCEPTED"], rows, errata,
                                 appendix_title="Appendix - Batch convention register"))


def _w_receipts(E, spec, path):
    rows, errata = [], []
    for r in spec["recs"]:
        t = r["received"]
        if r.get("_t14"):
            errata.append("Batch %s: received at %s." % (r["batch"], iso_z(t)))
            t = t + 86400 * 4 if t <= CUTOFF else t - 86400 * 4
        rows.append([_batch(r, r["batch"]), r["vendor"], _t3(r, t)])
    write_docx(path, docx_blocks("Vendor Batch Receipts", PROSE["vendor_batch_receipts.docx"], ["BATCH_ID", "VENDOR", "RECEIVED_AT"],
                                 rows, errata, appendix_title="Appendix - Receipt register"))


def _w_nlx(E, spec, path):
    rows, errata = [], []
    for r in spec["recs"]:
        cls = r["cls"]
        if r.get("_t14"):
            errata.append("Project %s label %s: class is %s." % (r["project"], r["label"], cls))
            cls = "car" if cls != "car" else "truck"
        rows.append([_proj(r, r["project"]), r["label"], cls, r["disp"]])
    model = [[lab, R1_MODEL_XWALK[lab] or "-", "drop" if R1_MODEL_XWALK[lab] is None else "eval"] for lab in R1_LABELS]
    write_docx(path, docx_blocks("Taxonomy v3 Charter", PROSE["taxonomy_v3_charter.docx"], ["PROJECT", "RAW_LABEL", "CLASS", "DISPOSITION"],
                                 rows, errata, appendix_title="Appendix - Northlake label crosswalk",
                                 extra_tables=[("Model vocabulary crosswalk (taxonomy v2 model labels)", ["MODEL_LABEL", "CLASS", "DISPOSITION"], model)]))


def _w_ksbook(E, spec, path):
    rows, errata = [], []
    for r in spec["recs"]:
        cls = r["cls"]
        if r.get("_t14"):
            errata.append("Project %s code %d from %s: class is %s." % (r["project"], r["code"], _date(r["from"]), cls))
            cls = "dog" if cls != "dog" else "car"
        rows.append([_proj(r, r["project"]), str(r["code"]), cls, r["disp"], iso_z(r["from"]), "-" if r["to"] is None else iso_z(r["to"])])
    write_pdf(path, pdf_table_lines("KESTREL CLASS CODEBOOK", PROSE["ks_class_codebook.pdf"],
                                    ["PROJECT", "CODE", "CLASS", "DISPOSITION", "VALID_FROM", "VALID_TO"], rows, errata))


def _w_obx(E, spec, path):
    lines = ["# Orbis label aliases by project", "aliases:"]
    for r in spec["recs"]:
        lines.append("  - project: %s" % _proj(r, r["project"]))
        lines.append('    alias: "%s"' % r["alias"])
        lines.append("    class: %s" % r["cls"])
        lines.append("    disposition: %s" % ("~" if r.get("_t5") else r["disp"]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _w_errata(E, spec, path):
    rows, notes = [], []
    for r in spec["recs"]:
        if r["action"] == "REBOX":
            val = ",".join(str(v) for v in r["value"])
        else:
            val = r["value"]
        shown = val
        if r.get("_t14"):
            notes.append("%s: value is %s." % (r["id"], val if val else "(empty)"))
            shown = "pedestrian" if r["action"] == "RECLASS" and val != "pedestrian" else ("car" if r["action"] == "RECLASS" else ("0,0,10,10" if r["action"] == "REBOX" else "see note"))
        rows.append([r["id"], _ann(r, r["ann"]), r["action"], shown, _date(r["eff"])])
    path.write_text(md_doc("Annotation Errata Register", PROSE["annotation_errata_register.md"],
                           ["errata_id", "annotation_id", "action", "value", "effective"], rows, notes,
                           appendix_title="Appendix - Errata entries"), encoding="utf-8")


def _w_qa(E, spec, path):
    rows, notes = [], []
    for r in spec["recs"]:
        dec = r["decision"]
        if r.get("_t14"):
            notes.append("Decision on %s revision %d at %s is %s." % (r["ann"], r["rev"], iso_z(r["t"]), dec))
            dec = "accepted" if dec == "rejected" else "rejected"
        rows.append([_ann(r, r["ann"]), str(r["rev"]), dec, _t3(r, r["t"])])
    path.write_text(html_doc("Labeling QA Portal - decision log", PROSE["labeling_qa_portal.html"], [],
                             "Appendix - QA decisions (snapshot 2026-10-31T00:00:00Z)", ["annotation_id", "revision", "decision", "decided_at"],
                             rows, notes), encoding="utf-8")


def _xl_time(rec, t):
    if rec.get("_t3"):
        return iso_z(t)
    v = excel_serial(t)
    return float(Fraction(round_half_even_int(v * 10 ** 6), 10 ** 6))


def _w_qa_export(E, spec, path):
    sheets = []
    for sh in ("decisions_a", "decisions_b"):
        recs = [r for r in spec["recs"] if r["_sheet"] == sh]
        rows = [[_ann(r, r["ann"]), r["rev"], r["decision"], _xl_time(r, r["t"]), r["state"]] for r in recs]
        sheets.append((sh, xlsx_rows(["annotation_id", "revision", "decision", "decided_at", "state"], rows, recs,
                                     {"annotation_id": "annotation", "decided_at": "decided"})))
    write_xlsx(path, sheets)


def _w_camp(E, spec, path):
    items = [r for r in spec["recs"] if r["_sheet"] == "items"]
    boxes = [r for r in spec["recs"] if r["_sheet"] == "boxes"]
    s1 = xlsx_rows(["item_id", "image_id", "opened_at"], [[r["item"], rid(r), _xl_time(r, r["opened"])] for r in items], items,
                   {"item_id": "item", "image_id": "frame"})
    s2 = xlsx_rows(["box_id", "item_id", "class", "x1", "y1", "x2", "y2", "crowd"],
                   [[r["box_id"], r["item"], r["cls"], r["box"][0], r["box"][1], r["box"][2], r["box"][3], r["crowd"]] for r in boxes], boxes,
                   {"box_id": "box", "item_id": "item"})
    write_xlsx(path, [("items", s1), ("boxes", s2)])


def _w_camp_status(E, spec, path):
    out = [{"item": r["item"], "status": r["status"], "at": _t3(r, r["t"])} for r in spec["recs"]]
    path.write_text(json.dumps({"campaign": "RC-2026Q3", "statuses": out}, indent=1) + "\n", encoding="utf-8")


def _nl_row(E, r, k):
    bb = E.batches[r["batch"]]
    c = vendor_coords(E, r, bb["fmt"], bb["frame"])
    if r.get("_t4"):
        c = [loc_num(v) for v in c]
    crowd = "U" if r.get("_t5") else ("Y" if r["crowd"] else "N")
    return [r["ann"], rid(r), _batch(r, r["batch"]), r["project"], r["label"]] + c + [crowd, str(r["rev"]), r["status"], _note(r, k)]


NL_HEADER = ["annotation_id", "image_id", "batch_id", "project", "label", "coord_1", "coord_2", "coord_3", "coord_4", "crowd", "revision", "status", "note"]
NL_ALT = {"annotation_id": "ann_id", "image_id": "frame", "label": "category", "revision": "rev"}


def _w_nl(E, spec, path):
    recs = spec["recs"]
    if spec["name"] == "nl_boxes_batch02.csv":
        recs = recs[: spec["present"]]
    if spec["fmt"] == "xlsx":
        sheets = []
        for sh in ("north", "south"):
            rs = [r for r in recs if r.get("_sheet") == sh]
            rows = [_nl_row(E, r, k) for k, r in enumerate(rs)]
            sheets.append((sh, xlsx_rows(NL_HEADER, rows, rs, NL_ALT)))
        write_xlsx(path, sheets)
        return
    rows = [_nl_row(E, r, k) for k, r in enumerate(recs)]
    comments = []
    if spec["decoy"]:
        comments = ["# re-extract of delivery nl_boxes_batch02 from the Northlake portal (2026-11-14); not a delivery of record."]
    write_table(path, NL_HEADER, rows, recs, delim="\t" if spec["fmt"] == "tsv" else ",", comments=comments, alt_header=NL_ALT)


def _ks_obj(E, r):
    bb = E.batches[r["batch"]]
    c = vendor_coords(E, r, bb["fmt"], bb["frame"])
    o = {"id": r["num"], "img": rid(r), "batch": _batch(r, r["batch"]), "proj": r["project"], "code": r["label"]}
    vals = [float(v) for v in c]
    if r.get("_t2") and bb["fmt"] == "cxcywh_norm":
        o["bbox_px"] = vals
    else:
        if r.get("_t2"):
            r.pop("_t2")
            c = vendor_coords(E, r, bb["fmt"], bb["frame"])
            vals = [float(v) for v in c]
            r["_t2"] = True
        o["bbox"] = vals
    o["crowd"] = -1 if r.get("_t5") else r["crowd"]
    o["rev"] = r["rev"]
    o["state"] = "active" if r["status"] == "live" else "void"
    o["ts"] = r["t"] if r.get("_t3") else r["t"] * 1000
    return o, c


def _w_ks(E, spec, path):
    recs = spec["recs"]
    fmt = spec["fmt"]
    objs = [_ks_obj(E, r) for r in recs]
    if fmt == "jsonl":
        raw = bytearray()
        for r, (o, _) in zip(recs, objs):
            raw += json.dumps(o).encode() + (b"\r\n" if r.get("_t10") else b"\n")
        path.write_bytes(bytes(raw))
    elif fmt == "json":
        head = {"vendor": "Kestrel", "delivery": spec["name"].rsplit(".", 1)[0]}
        if spec["decoy"]:
            head = {"vendor": "Kestrel", "delivery": "resubmission", "note": "Resubmitted after the freeze cutoff; applies only where the batch register accepts the resubmission."}
        head["records"] = [o for o, _ in objs]
        path.write_text(json.dumps(head, indent=None) + "\n", encoding="utf-8")
    elif fmt == "parquet":
        import pyarrow as pa
        _parquet(path, {"id": pa.array([o["id"] for o, _ in objs], pa.int64()), "img": pa.array([o["img"] for o, _ in objs], pa.string()),
                        "batch": pa.array([o["batch"] for o, _ in objs], pa.string()), "proj": pa.array([o["proj"] for o, _ in objs], pa.string()),
                        "code": pa.array([o["code"] for o, _ in objs], pa.int32()),
                        "b1": pa.array([c[0] for _, c in objs], pa.string()), "b2": pa.array([c[1] for _, c in objs], pa.string()),
                        "b3": pa.array([c[2] for _, c in objs], pa.string()), "b4": pa.array([c[3] for _, c in objs], pa.string()),
                        "bbox_unit": pa.array(["px" if ("bbox_px" in o) else "native" for o, _ in objs], pa.string()),
                        "crowd": pa.array([o["crowd"] for o, _ in objs], pa.int32()), "rev": pa.array([o["rev"] for o, _ in objs], pa.int32()),
                        "state": pa.array([o["state"] for o, _ in objs], pa.string()), "ts": pa.array([o["ts"] for o, _ in objs], pa.int64())})
    else:
        header = ["id", "img", "batch", "proj", "code", "b1", "b2", "b3", "b4", "bbox_unit", "crowd", "rev", "state", "ts", "note"]
        rows = []
        for k, (r, (o, c)) in enumerate(zip(recs, objs)):
            rows.append([str(o["id"]), o["img"], o["batch"], o["proj"], str(o["code"])] + list(c) +
                        ["px" if "bbox_px" in o else "native", str(o["crowd"]), str(o["rev"]), o["state"], str(o["ts"]), _note(r, k)])
        write_table(path, header, rows, recs, alt_header={"img": "image_id", "proj": "project"})


def _w_ob(E, spec, path):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>']
    if spec["decoy"]:
        lines.append("<!-- Orbis corrected resubmission, received 2026-11-16; accepted only for batches the batch register marks Y. -->")
    lines.append('<annotations vendor="Orbis" delivery="%s">' % spec["name"].rsplit(".", 1)[0])
    for r in spec["recs"]:
        bb = E.batches[r["batch"]]
        c = vendor_coords(E, r, bb["fmt"], bb["frame"])
        lines.append('  <object id="ob:%d" image="%s" batch="%s" project="%s">' % (r["num"], _xml_esc(rid(r)), _batch(r, r["batch"]), r["project"]))
        lines.append("    <name>%s</name>" % _xml_esc(r["label"]))
        lines.append('    <bndbox c1="%s" c2="%s" c3="%s" c4="%s"/>' % tuple(c))
        lines.append("    <crowd>%s</crowd>" % ("-1" if r.get("_t5") else r["crowd"]))
        lines.append("    <revision>%d</revision>" % r["rev"])
        lines.append("    <deleted>%d</deleted>" % (0 if r["status"] == "live" else 1))
        lines.append("  </object>")
    lines.append("</annotations>")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _w_registry(E, spec, path):
    runs = [[r[0], r[1], r[6], str(r[2]), r[3], r[4], str(r[5]), ",".join(r[7])] for r in RUNS]
    if spec["decoy"]:
        runs = [list(x) for x in runs]
        runs[2][4] = "0.05"
        runs[3][6] = "100"
    labels = []
    for run in [r[0] for r in RUNS]:
        for k, lab in enumerate(E.labelmap[run]):
            labels.append([run, str(k), lab])
    rows, notes = [], []
    for n, r in enumerate(spec["recs"]):
        node = r["node"]
        if r.get("_t14"):
            notes.append("Row %d (run %s, sequence %s): node is %s." % (n + 1, r["run"], r["seq"], node))
            node = "n1" if node != "n1" else "n2"
        rows.append([r["run"], _seqid(r, r["seq"]), node])
    nodes = [["n1", "csv", "xyxy", "fraction", "preprocess_n1.log"], ["n2", "jsonl", "cxcywh", "percent", "preprocess_n2.log"],
             ["n3", "parquet", "xyxy", "permille", "preprocess_n3.log"], ["n4", "tsv (Latin-1, decimal comma)", "xyxy", "fraction", "preprocess_n4.log"],
             ["n5", "xml", "xyxy", "fraction", "preprocess_n5.log"], ["n7", "xlsx (csv for skye-v6.4)", "xyxy", "fraction", "per-row letterbox columns"],
             ["n6", "sqlite rerun store", "cxcywh", "basis points", "preprocess table in the store"]]
    note = None
    if spec["decoy"]:
        note = "Read-only mirror of the inference run registry, refreshed nightly. Snapshot taken 2026-11-02; later registry edits are not reflected."
    path.write_text(html_doc("Inference Run Registry" + (" (mirror)" if spec["decoy"] else ""), PROSE[spec["name"]],
                             [("Runs", ["run_id", "model", "status", "input_size", "score_threshold", "nms_iou", "max_detections", "training_index"], runs),
                              ("Label maps", ["run_id", "class_index", "label"], labels),
                              ("Nodes", ["node", "dump format", "box format", "score unit", "letterbox source"], nodes)],
                             "Appendix - Sequence node assignments", ["run_id", "sequence_id", "node"], rows, notes, note=note), encoding="utf-8")


def _w_reruns(E, spec, path):
    lines = ["# rerun ledger maintained by the inference scheduler", ""]
    for r in spec["recs"]:
        lines += ["[[rerun]]", 'run = "%s"' % r["run"], 'image = "%s"' % rid(r), 'store = "%s"' % r["store"], 'status = "%s"' % r["status"], ""]
    path.write_text("\n".join(lines), encoding="utf-8")


def _w_quarantine(E, spec, path):
    rows, notes = [], []
    for n, r in enumerate(spec["recs"]):
        node = r["node"]
        if r.get("_t14"):
            notes.append("Row %d (%s, run %s): node is %s." % (n + 1, r["image"], r["run"], node))
            node = "n7" if node != "n7" else "n1"
        rows.append([r["run"], node, rid(r), r["status"]])
    write_pdf(path, pdf_table_lines("NODE QUARANTINE REPORT", PROSE["node_quarantine_report.pdf"], ["RUN", "NODE", "IMAGE_ID", "STATUS"], rows, notes))


def _label_index(E, run, label):
    return E.labelmap[run].index(label)


def _w_n6db(E, spec, path):
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE dets (run_id TEXT, image_id TEXT, det_id INTEGER, class_index INTEGER, cx TEXT, cy TEXT, w TEXT, h TEXT, score_bp INTEGER)")
    con.execute("CREATE TABLE preprocess (run_id TEXT, image_id TEXT, scale TEXT, pad_x INTEGER, pad_y INTEGER, status TEXT)")
    if spec["decoy"]:
        con.execute("CREATE TABLE meta (key TEXT, value TEXT)")
        con.execute("INSERT INTO meta VALUES ('role', 'ingest replica of node6 store; authoritative only for reruns the ledger routes to n6-replica')")
    rows = []
    for d in spec["recs"]:
        prep = E.prep[(d["run"], d["image"])]
        mb = model_box(d, prep, half=bool(d.get("_t12")))
        ok, vals = cxcywh_ok(mb, d["box"], prep)
        if not ok:
            mb = model_box(dict(d, _t12=False), prep)
            ok, vals = cxcywh_ok(mb, d["box"], prep)
        sc = -1 if d["score"] < 0 else d["score"] * 10
        rows.append((d["run"], rid(d), d["det"], _label_index(E, d["run"], d["label"]), dec2(vals[0]), dec2(vals[1]), dec2(vals[2]), dec2(vals[3]), sc))
    con.executemany("INSERT INTO dets VALUES (?,?,?,?,?,?,?,?,?)", rows)
    store = "n6-replica" if spec["decoy"] else "n6"
    con.executemany("INSERT INTO preprocess VALUES (?,?,?,?,?,?)",
                    [(p["run"], p["image"], "%d/%d" % (p["scale"].numerator, p["scale"].denominator), p["px"], p["py"], p["status"]) for p in E.prep_rows[store]])
    con.commit()
    con.close()


def _w_log(E, spec, path):
    node = spec["node"]
    raw = bytearray()
    model = {r[0]: r[1] for r in RUNS}
    for r in spec["recs"]:
        sc = r["scale"]
        frac = "%d/%d" % (sc.numerator, sc.denominator)
        t = r["t"]
        iid = rid(r)
        ok = r["status"] == "ok"
        if r.get("_t8"):
            ln = "PREP|%s|%s|%s|%s|%d|%d|%d/%d|%s" % (iso_z(t), r["run"], iid, frac, r["px"], r["py"], r["attempt"], r["of"], r["status"])
        elif node == "n1":
            ln = "%s INFO prep run=%s img=%s src=%dx%d rot=%d dst=%d scale=%s pad=%d,%d attempt=%d/%d status=%s" % (
                iso_z(t), r["run"], iid, r["W"], r["H"], r["orient"], r["S"], frac, r["px"], r["py"], r["attempt"], r["of"], r["status"])
        elif node == "n2":
            d = wall(t + 3600)
            ln = '[%s +0100] PREP image="%s" run="%s" letterbox(scale=%s, pad_x=%d, pad_y=%d) try=%d of %d %s' % (
                d.strftime("%d/%b/%Y:%H:%M:%S"), iid, model[r["run"]], frac, r["px"], r["py"], r["attempt"], r["of"], "OK" if ok else "FAILED")
        elif node == "n3":
            ln = "n3|%s|%s|%s|%s|%d|%d|%d/%d|%s" % (wall(t).strftime("%Y-%m-%d %H:%M:%S"), r["run"], iid, frac, r["px"], r["py"], r["attempt"], r["of"], r["status"])
        elif node == "n4":
            ln = "%s n4 evalprep[311]: %s %s scale %s pads %d %d attempt %d of %d -> %s" % (
                wall(t).strftime("%b %d %H:%M:%S"), r["run"], iid, frac, r["px"], r["py"], r["attempt"], r["of"], r["status"])
        else:
            ln = "%s,%03d [prep] run=%s image=%s s=%s (%s) px=%d py=%d a=%d/%d %s" % (
                wall(t).strftime("%Y-%m-%d %H:%M:%S"), t % 1000, r["run"], iid, dstr(sc, 6), frac, r["px"], r["py"], r["attempt"], r["of"], "OK" if ok else "ERR")
        if r.get("_t10"):
            raw += (ln + " host=Z\u00fcrich-rack\r\n").encode("latin-1")
        else:
            raw += (ln + "\n").encode("utf-8")
    path.write_bytes(bytes(raw))


def _calib_val(r):
    return dstr(r["y"], 6)


def _w_calib(E, spec, path):
    name, run = spec["name"], spec["run"]
    recs = spec["recs"]
    if spec["fmt"] == "yaml":
        lines = ["calibration:", "  run: %s" % run, "  model: %s" % run_cfg(run)[1], "  method: isotonic-piecewise-linear", "  knots:"]
        for r in recs:
            y = _calib_val(r)
            if r.get("_t2"):
                lines.append("    - {class: %s, k: %d, x: %s, y_pct: %s}" % (r["cls"], r["k"], dstr(r["x"], 6), dstr(r["y"] * 100, 4)))
                continue
            if r.get("_t4"):
                y = '"%s"' % loc_num(y)
            if r.get("_t9"):
                lines += ["    - class: %s" % r["cls"], "      k: %d" % r["k"], "      x: %s" % dstr(r["x"], 6), "      y: %s" % y]
            else:
                lines.append("    - {class: %s, k: %d, x: %s, y: %s}" % (r["cls"], r["k"], dstr(r["x"], 6), y))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif spec["fmt"] == "toml":
        lines = ['run = "%s"' % run, 'method = "isotonic-piecewise-linear"', ""]
        for r in recs:
            y = _calib_val(r)
            if r.get("_t2"):
                lines.append('[[knot]]\nclass = "%s"\nk = %d\nx = "%s"\ny = "%s"\nunit = "pct"\n' % (r["cls"], r["k"], dstr(r["x"], 6), dstr(r["y"] * 100, 4)))
                continue
            if r.get("_t4"):
                y = loc_num(y)
            if r.get("_t9"):
                lines.append('[[knot]]\nclass = "%s"\nk = %d\nx = "%s"\ny = "%s" # checked\n' % (r["cls"], r["k"], dstr(r["x"], 6), y))
            else:
                lines.append('[[knot]]\nclass = "%s"\nk = %d\nx = "%s"\ny = "%s"\n' % (r["cls"], r["k"], dstr(r["x"], 6), y))
        path.write_text("\n".join(lines), encoding="utf-8")
    elif spec["fmt"] == "ini":
        lines = ["; isotonic calibration map for %s" % run_cfg(run)[1], "[meta]", "run = %s" % run, ""]
        cur = None
        for r in recs:
            if r["cls"] != cur:
                cur = r["cls"]
                lines.append("[%s]" % cur)
            y = _calib_val(r)
            xs = dstr(r["x"], 6)
            if r.get("_t2"):
                lines.append("k%03d = x=%s y%%=%s" % (r["k"], xs, dstr(r["y"] * 100, 4)))
                continue
            if r.get("_t4"):
                xs, y = loc_num(xs), loc_num(y)
            ln = "k%03d = x=%s y=%s" % (r["k"], xs, y)
            if r.get("_t9"):
                ln += " ; verified"
            lines.append(ln)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        rows, notes = [], []
        for n, r in enumerate(recs):
            y = _calib_val(r)
            if r.get("_t2"):
                y = dstr(r["y"] * 100, 4) + "%"
            elif r.get("_t4"):
                y = loc_num(y)
            if r.get("_t14"):
                notes.append("Row %d (class %s, knot %d): y is %s." % (n + 1, r["cls"], r["k"], _calib_val(r)))
                y = dstr(min(Fraction(1), r["y"] + Fraction(5, 1000)), 6)
            rows.append([r["cls"], str(r["k"]), dstr(r["x"], 6), y])
        title = "CALIBRATION CERTIFICATE - skye-v7.0-rc2" + (" - REISSUE 2026-11-20" if spec.get("reissue") else "")
        prose = [p % ", ".join(E.deferred) if "%s" in p else p for p in PROSE[name]]
        write_pdf(path, pdf_table_lines(title, prose, ["CLASS", "K", "X", "Y"], rows, notes))


def _pred_cells(E, d, node, rec_flags):
    prep = E.prep[(d["run"], d["image"])]
    mb = model_box(d, prep, half=bool(d.get("_t12")))
    return mb, prep


def _score_str(d, unit):
    s = d["score"]
    if s < 0:
        return "-1"
    if unit == "fraction":
        return dstr(Fraction(s, 1000), 3)
    if unit == "percent":
        return dstr(Fraction(s, 10), 1)
    return str(s)


def _w_pred(E, spec, path):
    node = spec["node"]
    fmt = spec["fmt"]
    recs = spec["recs"]
    model = {r[0]: r[1] for r in RUNS}
    if fmt in ("csv", "tsv") and node in ("n1", "n7", "n4"):
        rows = []
        for k, d in enumerate(recs):
            mb, prep = _pred_cells(E, d, node, d)
            cells = [dec2(v) for v in mb]
            sc = _score_str(d, "fraction")
            if d.get("_t2") and d["score"] >= 0:
                sc = _score_str(d, "percent") + "%"
            if node == "n4":
                cells = [c.replace(".", ",") for c in cells]
                if not d.get("_t4"):
                    sc = sc.replace(".", ",")
                row = ["%09d" % d["det"], rid(d), d["run"], str(_label_index(E, d["run"], d["label"]))] + cells + [sc, _note(d, k)]
            elif node == "n1":
                if d.get("_t4"):
                    sc = sc.replace(".", ",")
                row = [str(d["det"]), rid(d), d["run"], str(_label_index(E, d["run"], d["label"]))] + cells + [sc, _note(d, k)]
            else:
                if d.get("_t4"):
                    sc = sc.replace(".", ",")
                p = d["prep"]
                row = [str(d["det"]), rid(d), model[d["run"]], str(_label_index(E, d["run"], d["label"]))] + cells + [sc, "%d/%d" % (p[0].numerator, p[0].denominator), str(p[1]), str(p[2]), _note(d, k)]
            rows.append(row)
        if node == "n7":
            header = ["det_id", "image_id", "model", "class_index", "x1", "y1", "x2", "y2", "score", "lb_scale", "lb_pad_x", "lb_pad_y", "note"]
        else:
            header = ["det_id", "image_id", "run", "class_index", "x1", "y1", "x2", "y2", "score", "note"]
        write_table(path, header, rows, recs, delim="\t" if fmt == "tsv" else ",", encoding="latin-1" if node == "n4" else "utf-8",
                    alt_header={"det_id": "det", "image_id": "frame", "class_index": "cls"})
    elif fmt == "jsonl":
        raw = bytearray()
        for d in recs:
            prep = E.prep[(d["run"], d["image"])]
            mb = model_box(d, prep, half=bool(d.get("_t12")))
            ok, vals = cxcywh_ok(mb, d["box"], prep)
            if not ok:
                ok, vals = cxcywh_ok(model_box(dict(d, _t12=False), prep), d["box"], prep)
            o = {"det": "D%09d" % d["det"], "image": rid(d), "run": model[d["run"]], "cls": _label_index(E, d["run"], d["label"]),
                 "box_cxcywh": [float(dec2(v)) for v in vals]}
            if d.get("_t2") and d["score"] >= 0:
                o["score"] = float(_score_str(d, "fraction"))
            elif d.get("_t4") and d["score"] >= 0:
                o["score_pct"] = _score_str(d, "percent").replace(".", ",")
            else:
                o["score_pct"] = -1 if d["score"] < 0 else float(_score_str(d, "percent"))
            if spec.get("replay"):
                p = d["prep"]
                o["letterbox"] = {"scale": "%d/%d" % (p[0].numerator, p[0].denominator), "pad_x": p[1], "pad_y": p[2]}
                o["replay"] = True
            if d.get("_t10"):
                o["host"] = "Z\u00fcrich-rack"
                raw += json.dumps(o, ensure_ascii=False).encode("latin-1") + b"\r\n"
            else:
                raw += json.dumps(o).encode() + b"\n"
        path.write_bytes(bytes(raw))
    elif fmt == "parquet":
        import pyarrow as pa
        cols = {k: [] for k in ["det_id", "image_id", "run_tag", "class_index", "x1", "y1", "x2", "y2", "score", "score_unit"]}
        for d in recs:
            mb, prep = _pred_cells(E, d, node, d)
            cols["det_id"].append(d["det"])
            cols["image_id"].append(rid(d))
            cols["run_tag"].append(model[d["run"]])
            cols["class_index"].append(_label_index(E, d["run"], d["label"]))
            for k, v in zip(("x1", "y1", "x2", "y2"), mb):
                cols[k].append(float(dec2(v)))
            if d.get("_t2") and d["score"] >= 0:
                cols["score"].append(d["score"] * 10)
                cols["score_unit"].append("bp")
            else:
                cols["score"].append(-1 if d["score"] < 0 else d["score"])
                cols["score_unit"].append("permille")
        _parquet(path, {"det_id": pa.array(cols["det_id"], pa.int64()), "image_id": pa.array(cols["image_id"], pa.string()),
                        "run_tag": pa.array(cols["run_tag"], pa.string()), "class_index": pa.array(cols["class_index"], pa.int32()),
                        "x1": pa.array(cols["x1"], pa.float64()), "y1": pa.array(cols["y1"], pa.float64()),
                        "x2": pa.array(cols["x2"], pa.float64()), "y2": pa.array(cols["y2"], pa.float64()),
                        "score": pa.array(cols["score"], pa.int32()), "score_unit": pa.array(cols["score_unit"], pa.string())})
    elif fmt == "xml":
        lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<detections node="%s">' % node]
        for d in recs:
            mb, prep = _pred_cells(E, d, node, d)
            c = [dec2(v) for v in mb]
            if d.get("_t4"):
                c = [x.replace(".", ",") for x in c]
            lines.append('  <det id="d%d" run="%s" image="%s" cls="%d">' % (d["det"], d["run"], _xml_esc(rid(d)), _label_index(E, d["run"], d["label"])))
            lines.append('    <box x1="%s" y1="%s" x2="%s" y2="%s"/>' % tuple(c))
            if d.get("_t2") and d["score"] >= 0:
                lines.append('    <score unit="pct">%s</score>' % _score_str(d, "percent"))
            else:
                lines.append("    <score>%s</score>" % _score_str(d, "fraction"))
            lines.append("  </det>")
        lines.append("</detections>")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    elif fmt == "xlsx":
        header = ["det_id", "image_id", "model", "class_index", "x1", "y1", "x2", "y2", "score", "lb_scale", "lb_pad_x", "lb_pad_y"]
        half = len(recs) // 2
        sheets = []
        for sh, rs in (("part_1", recs[:half]), ("part_2", recs[half:])):
            rows = []
            for d in rs:
                mb, prep = _pred_cells(E, d, node, d)
                p = d["prep"]
                sc = float(_score_str(d, "fraction")) if d["score"] >= 0 else -1
                if d.get("_t2") and d["score"] >= 0:
                    sc = _score_str(d, "percent") + "%"
                elif d.get("_t4") and d["score"] >= 0:
                    sc = _score_str(d, "fraction").replace(".", ",")
                rows.append([d["det"], rid(d), model[d["run"]], _label_index(E, d["run"], d["label"])] + [float(dec2(v)) for v in mb] +
                            [sc, "%d/%d" % (p[0].numerator, p[0].denominator), p[1], p[2]])
            sheets.append((sh, xlsx_rows(header, rows, rs, {"det_id": "det", "image_id": "frame", "class_index": "cls"})))
        write_xlsx(path, sheets)


def _w_manifest(E, spec, path):
    lines = ["# Delivery manifest for the PES-3 Q3 2026 review drop.", "# One entry per 100-record partition, in delivery order.", ""]
    k = 0
    for name in sorted(E.files):
        if name == "delivery_manifest.toml":
            continue
        n = len(E.files[name]["recs"])
        parts = max(1, (n + 99) // 100)
        for p in range(parts):
            cnt = min(100, n - p * 100) if n else 0
            k += 1
            if k % 431 == 7:
                lines += ["[[partition]]", 'file = "%s"' % name, "part = %d" % (p + 1), "records = %d" % max(0, cnt - 3), 'status = "superseded"', ""]
            if k % 577 == 13:
                lines += ["[[partition]]", 'file = "%s"' % name, "part = %d" % (parts + 1 + p), "records = 100", 'status = "voided"', ""]
            if k % 2003 == 101:
                ghost = name.rsplit(".", 1)[0] + "_v1." + name.rsplit(".", 1)[1]
                lines += ["[[partition]]", 'file = "%s"' % ghost, "part = 1", "records = 100", 'status = "withdrawn"', ""]
            rec_s = ("%d_%02d" % (cnt // 100, cnt % 100)) if (k % 389 == 11 and cnt >= 100) else str(cnt)
            lines += ["[[partition]]", 'file = "%s"' % name, "part = %d" % (p + 1), "records = %s" % rec_s, ""]
    path.write_text("\n".join(lines), encoding="utf-8")


WRITERS = {"frames": _w_frames, "geometry": _w_geometry, "exif": _w_exif, "dhash": _w_dhash, "seqmem": _w_seqmem,
           "lifecycle": _w_lifecycle, "integrity": _w_integrity, "corrections": _w_corrections, "aliases": _w_aliases,
           "freeze": _w_freeze, "amend": _w_amend, "ics": _w_ics, "roster": _w_roster, "train": _w_train, "legacy": _w_train,
           "fdedup": _w_train, "trainseq": _w_trainseq, "waivers": _w_waivers, "privacy_reg": _w_privacy_reg,
           "privacy_export": _w_privacy_export, "mbox": _w_mbox, "board": _w_board, "assign": _w_assign, "batches": _w_batches,
           "receipts": _w_receipts, "nlx": _w_nlx, "ksbook": _w_ksbook, "obx": _w_obx, "errata": _w_errata, "qa": _w_qa,
           "qa_export": _w_qa_export, "camp": _w_camp, "camp_status": _w_camp_status, "nl": _w_nl, "ks": _w_ks, "ob": _w_ob,
           "registry": _w_registry, "reruns": _w_reruns, "quarantine": _w_quarantine, "n6db": _w_n6db, "log": _w_log,
           "calib": _w_calib, "pred": _w_pred, "manifest": _w_manifest}

# ----------------------------------------------------------------- document prose
PROSE = {}

PROSE["eval_standard_v3.md"] = [
    ("1. Scope and authority", [
        "PES-3 governs the Q3 2026 release review of the SKYE sidewalk-robot object detector. It defines which images are evaluated, how their ground truth and detections are assembled from the delivered sources, how the detector runs are scored, and the exact layout of every review artifact.",
        "This standard is the governing document of the review. Where two sources disagree, the document this standard names for that topic decides: the Data Authority Policy (data_authority_policy.docx) decides which delivery is authoritative for which records, the Evaluation Exclusion Policy (exclusion_policy.docx) defines the exclusion reasons, the Annotation Batch Conventions (annotation_batch_conventions.docx) decide how vendor coordinates are read, the Taxonomy v3 Charter (taxonomy_v3_charter.docx) decides classes, the Inference Run Registry (inference_run_registry.html) decides runs, nodes and label maps, and the Release Governance Policy (release_governance.docx) decides promotion. A later file date, a cleaner schema or a word such as FINAL, signed or fixed does not make a file authoritative.",
        "The freeze cutoff is 2026-11-12T18:00:00Z. Evidence dated after the cutoff (decisions, statuses, errata, messages, receipts, lifecycle events, calibration reissues) has no effect unless a rule below says otherwise. An instant exactly equal to the cutoff is on time.",
        "The evaluation window is the half-open interval [2026-09-14T00:00:00Z, 2026-11-09T00:00:00Z) on the corrected capture instant of section 6.",
        "Runs under review are the registry runs whose status is review. The incumbent is skye-v6.4 (run R1). Runs with any other status are not scored and their records are ignored wherever they appear. A record's run is the run named in the record itself, never the file it was delivered in."]),
    ("2. Deliverables", [
        "The review engine reads one estate directory laid out like this delivery and writes eight artifacts into an output directory: eval_images.csv, exclusions.csv, ground_truth.csv, detections.csv, class_metrics.csv, operating_points.csv, leaderboard.json and reconciliation.json.",
        "Every CSV artifact is UTF-8 without a byte order mark, uses LF line endings, a comma delimiter, a single header row and no quoting; it ends with a newline. Every JSON artifact is a single UTF-8 JSON object. Counts are JSON integers. Every non-integer metric is written as a string with exactly six decimals after rounding half to even (for example \"0.500000\"), JSON included. Where a metric is undefined the string NA is written.",
        "eval_images.csv columns: image_id,sequence_id,camera_id,site_id,captured_utc,width,height,orientation,gt_boxes,ignore_regions. One row per evaluated image, ordered by image_id. sequence_id comes from sequence_membership.xlsx, camera_id from the frames index and site_id is the roster site of the camera on the local capture date (section 6). captured_utc is the corrected capture instant as YYYY-MM-DDTHH:MM:SSZ. width and height are the upright pixel dimensions, orientation is the final EXIF orientation code, gt_boxes counts the image's non-ignore ground-truth boxes and ignore_regions its ignore regions.",
        "exclusions.csv columns: image_id,reason. One row per excluded candidate, ordered by image_id, with the single reason that wins under the precedence of section 9.",
        "ground_truth.csv columns: image_id,gt_id,class,x1,y1,x2,y2,ignore. One row per ground-truth box of an evaluated image, ordered by image_id then gt_id. Coordinates are canonical (section 7). ignore is 1 for ignore regions and 0 otherwise.",
        "detections.csv columns: run_id,image_id,det_id,class,x1,y1,x2,y2,score. One row per final detection (after threshold, NMS and the per-image cap of section 11) of an evaluated image, ordered by run_id, image_id, det_id. det_id is D followed by the nine-digit detection number. score is the calibrated score.",
        "class_metrics.csv columns: run_id,class,gt_count,det_count,tp_50,fp_50,ap_50,ap_75,ap_50_95. One row per reviewed run and taxonomy class, ordered by run_id then class name (byte order). gt_count counts non-ignore ground truth of the class, det_count the final detections of the class, tp_50 and fp_50 the true and false positives at IoU 0.50 (ignored detections are neither). ap_50, ap_75 and ap_50_95 are NA when gt_count is 0.",
        "operating_points.csv columns: run_id,class,target_precision,threshold,precision,recall, ordered like class_metrics.csv (section 13).",
        "leaderboard.json has the keys incumbent (a run id), release_candidate (a run id or null) and runs, a list ordered by run_id of objects with the keys run_id, model, map_50, map_75, map_50_95, protected_ap_50_delta (an object keyed by protected class) and decision (section 14).",
        "reconciliation.json has the keys freeze_list_ids, candidates, eval_images, excluded (an object with every exclusion reason as a key, zero included), gt_boxes, ignore_regions, gt_by_source (keys CAMPAIGN, KS, NL, OB, counting all ground-truth boxes including ignore regions by origin), detections (an object keyed by reviewed run id, each with accepted, after_threshold, after_nms and final) and deliveries (section 15)."]),
    ("3. Identifiers", [
        "Image identifiers are canonicalised before any join: apply Unicode NFKC, remove surrounding whitespace, map every character listed in the [homoglyphs] section of image_id_aliases.ini to its Latin replacement, upper-case, remove hyphens and underscores, and zero-pad the digits after IMG to seven places. A legacy identifier (LGC-...) is resolved through the [aliases] section of image_id_aliases.ini, following an alias that points at another alias until a canonical IMG identifier is reached. Alias values may carry a trailing ; comment. An identifier that resolves to nothing known is ignored.",
        "Camera identifiers are upper-cased and spaces or underscores become hyphens (CAM-K07). Sequence identifiers are upper-cased and written SEQ- followed by five digits (seq-01234 and SEQ01234 are SEQ-01234). Project codes and batch identifiers are upper-cased. Annotation identifiers are upper-cased and trimmed; Orbis ob:N identifiers are OB- followed by N zero-padded to seven digits; Kestrel numeric identifiers are KS- followed by seven digits. Detection numbers are integers however they are written (D000123456, d123456, 000123456 and 123456 are the same number) and are unique within a run."]),
    ("4. Reading delivered files", [
        "Text deliveries are decoded line by line: a line that is valid UTF-8 is UTF-8, any other line is Latin-1. A byte order mark at the start of a file is not data. Lines may end in LF or CRLF. Lines starting with # in CSV, TSV and fixed-width deliveries are comments.",
        "CSV and TSV deliveries use double-quote quoting; a quoted field may contain the delimiter, quotes and line breaks. A row may carry a trailing empty field. A delivery may repeat its header row at any point, possibly with the columns in another order; columns are always identified by name and the most recent header row applies to the rows after it. The same applies to every sheet of a workbook. Column synonyms: frame = image_id, camera = camera_id, local_time = captured_local, fold = dst_fold, width_px = stored_width, height_px = stored_height, sequence = sequence_id, frame_no = frame_index, hash = dhash_u64, status = state (training index b), ann_id = annotation_id, annotation = annotation_id, decided = decided_at, category = label, rev = revision, image_id = img (Kestrel), project = proj, det = det_id, cls = class_index, request = request_id, item = item_id, box = box_id.",
        "Numbers may use a decimal point or a decimal comma. When both appear, the last of them is the decimal separator and the others group thousands. A value in parentheses is negative. -0 is 0.",
        "Timestamps carrying an offset or Z are instants. The local wall-clock columns of the frames indexes are the only timestamps without an offset. Workbook date columns hold Excel serial dates in the 1900 date system (serial 1 is 1900-01-01 and serial 60 is the nonexistent 1900-02-29), with fractional days as time of day, interpreted as UTC; a workbook cell holding an ISO text timestamp is read as that instant.",
        "Values that are stated in another unit carry that unit on the record: a trailing % or unit=pct means percent, a key or column naming pct, permille, bp or px names its unit.",
        "Document registers: every policy document, certificate and register in this delivery carries its records in the table headed Appendix (or APPENDIX REGISTER in the PDF certificates and reports). Where the document has an Errata to the register section (ERRATA TO THE REGISTER in the PDFs), each erratum replaces the register value it names; an erratum that names a row number counts register rows from 1 in table order. In Markdown registers a row whose identifier is struck through (~~...~~) is void."]),
    ("5. Freeze and candidates", [
        "The frozen candidate register is Appendix A below. Amendments to it are published only in Appendix A' of the PES-3.1 draft (eval_standard_v3_1_draft.md): its rows whose status is ratified apply in table order (add puts the image in the freeze, remove takes it out, a later row for the same image overrides an earlier one); confirm and proposed rows change nothing. Nothing else in the PES-3.1 draft has force.",
        "A candidate is a frozen image that appears in a frames index. freeze_list_ids in reconciliation.json counts the distinct canonical identifiers of the amended freeze, including identifiers that match no frame.",
        "The frames indexes are frames_index_east.csv and frames_index_west.csv. The replica re-export frames_index_east_v2.csv is authoritative only for cameras that appear in neither of them (Data Authority Policy, section 2)."]),
    ("6. Capture instant", [
        "captured_local is camera wall-clock time at the camera's site. The site and UTC offset of a camera on a local date come from camera_deployment_roster.yaml (for cameras absent from it, from the operations copy as the Data Authority Policy allows). On a date with a switch_local entry the offset is utc_offset before the wall-clock switch time and offset_after from it on; wall-clock times that occur twice (the hour before switch_local, when clocks went back) use dst_fold: 0 or blank is the first occurrence, 1 the second.",
        "The camera clock instant is the wall-clock time minus the offset. The corrected capture instant is the camera clock instant minus the camera skew of the camera_clock_sync.ics event for that camera whose [DTSTART, DTEND) contains the camera clock instant. Only CONFIRMED events count; the DESCRIPTION gives skew_s (seconds) or skew_ms (milliseconds). A camera clock instant covered by no event has zero skew."]),
    ("7. Geometry and canonical boxes", [
        "Stored dimensions come from frame_geometry.tsv; dim_scale multiplies both dimensions. When a geometry row is 0 x 0, or the integrity audit status is REENCODED, the decoded dimensions of frame_integrity_audit.pdf are the stored dimensions.",
        "The final orientation is the EXIF orientation of exif_orientation_scan.jsonl (0 means unknown and is read as 1) unless orientation_corrections.pdf holds a confirmed correction for the image, in which case the latest confirmed correction (by decided time, then correction id) wins. Proposed corrections have no effect. Upright dimensions swap width and height for orientations 6 and 8.",
        "Canonical boxes are x1,y1,x2,y2 in the upright image with x2 and y2 exclusive. Every conversion into canonical coordinates is computed exactly (rational arithmetic on the delivered decimals and fractions), rounded half to even to integers only at the end, then clipped to [0, width] and [0, height]. A box with no area after clipping is discarded."]),
    ("8. Leakage", [
        "A candidate leaks when its perceptual hash is close to a hash in the training index of any reviewed run. The training index of each run is named in the registry (training_index). v7-train is made of training_hash_index shards a, b, c, d, e and h, plus the rows of train_hash_index_f_dedup.parquet whose source_shard is g (shard g was never delivered separately). v6-core is the rows of train_hash_index_legacy.txt tagged v6-core. A row tagged with any other set, or flagged purged, is not in any index.",
        "Hashes are 64-bit unsigned integers. frame_dhash.parquet stores them as signed 64-bit integers (two's complement); rows whose byte_order is be were stored byte-swapped. Shard a holds lowercase hex (status, set_tag); shard b unsigned decimal (state A or P); shard c upper-case hex in table train_hashes (purged 0 or 1); shard d is fixed width (hex in columns 1-16, set tag in 18-25, flag A or P in 27); shard e is JSON lines with h (hex) or h_dec (decimal); shard h is fixed width (unsigned decimal right-aligned in columns 1-20, set tag in 22-29, flag in 31). In every shard a value prefixed 0x or x is hex; hex digits are case-insensitive and leading zeros may be omitted. A hash of 0 means not computed: it never matches and a candidate without a hash cannot leak by hash.",
        "The distance is the Hamming distance. LEAK_EXACT is distance 0 and LEAK_NEAR distance 1 to 4 inclusive, over training hashes not waived for the candidate. leakage_waivers.json waives one (image, training hash) pair: the latest decision for the pair (by decided_at, then waiver_id) counts, and it waives only when it is granted and its expires_at is null or later than the cutoff.",
        "LEAK_SEQUENCE: the candidate's sequence (sequence_membership.xlsx) is registered trained in training_sequence_register.pdf for an index that a reviewed run uses."]),
    ("9. Exclusions", [
        "Each candidate is checked for every reason; it is excluded with the first reason in this precedence: WITHDRAWN, OUT_OF_WINDOW, CORRUPT, PRIVACY_HOLD, BOARD_OVERRIDE, LEAK_EXACT, LEAK_NEAR, LEAK_SEQUENCE, UNLABELED. The reasons are defined in the Evaluation Exclusion Policy, OUT_OF_WINDOW by section 1 and the leak reasons by section 8. Candidates with no reason are evaluated."]),
    ("10. Ground truth", [
        "The ground truth of an evaluated image is built as the Data Authority Policy, the Annotation Batch Conventions, the Taxonomy v3 Charter, the Kestrel codebook, the Orbis aliases, the QA portal and the errata register describe, in this order: approved relabel campaign items replace vendor annotation entirely (an item is approved when its latest status in relabel_campaign_status.json at or before the cutoff is approved); otherwise the assigned vendor's annotations are taken from on-time batches, the surviving revision of each annotation is chosen, deleted annotations are dropped, errata are applied, labels are mapped to a class and disposition, and coordinates are converted to canonical boxes.",
        "A box is an ignore region when its disposition is ignore, when it is flagged crowd, or when its canonical area is below 64 square pixels (area exactly 64 is not small). Boxes whose disposition is drop are not ground truth. gt_id is the canonical annotation identifier, or the campaign box_id for campaign boxes."]),
    ("11. Detections", [
        "For each reviewed run and evaluated image the detection records come from exactly one place. If rerun_batches.toml routes the pair to a store with status completed (a later entry for the same run and image overrides an earlier one), the records are those of that store: n6 is node6_rerun_store.db, n6-replica is node6_ingest_replica.db and n2-replay is preds_r3_n2_replay.jsonl. Otherwise they are the records of the node the registry assigns to the image's sequence for that run, taken from every delivered file of that node; when the node quarantine report lists the run, node and image, the pair has no detections.",
        "A node record is usable only with its letterbox parameters: for nodes n1 to n5 the preprocess log of the node gives them, and the line with status ok and the highest attempt number for the run and image applies; a pair with no such line has no usable records. Node n7 records, replay records and store records carry their own parameters (the stores in their preprocess table, status ok). Model coordinates are recorded to 0.01 px; values stored as binary floating point are read as the nearest 0.01. The canonical coordinate is (model coordinate - pad) / scale, with pad_x for x and pad_y for y, using the exact fraction of the scale. cx,cy,w,h boxes become x1 = cx - w/2, x2 = cx + w/2 (likewise y) before that.",
        "A record with score -1 was suppressed by the node and is dropped. Exact repeats of a record (same run, detection number and image) count once. Class indexes are read through the run's label map; labels of the taxonomy v2 vocabulary go through the model vocabulary crosswalk of the Taxonomy v3 Charter; a label that maps to no evaluation class is dropped. These are the accepted records.",
        "The raw score is converted to a fraction with the unit of the record (section 4) and calibrated with the run's isotonic map: for knots x_0 < ... < x_511 of the class, with i the largest index such that x_i <= s, the calibrated score is y_i + (y_(i+1) - y_i) * (s - x_i) / (x_(i+1) - x_i). Knot rows are keyed by class and k; a later row for the same class and k overrides an earlier one. A knot whose y is given as y_pct or y% or carries unit = pct holds percent. The calibration certificate of skye-v7.0-rc2 defers some classes; for those classes, and only those, the reissued certificate applies.",
        "Records whose calibrated score is below the run's score_threshold are dropped. Class-wise NMS follows: within an image and class, records are visited by calibrated score descending then detection number ascending, and a record is suppressed when its IoU with an already kept record of that class is greater than the run's nms_iou. Finally each image keeps at most max_detections records across classes, by calibrated score descending then detection number ascending. All score comparisons use the exact calibrated value."]),
    ("12. Matching and average precision", [
        "Matching is per run, class and IoU threshold t in 0.50, 0.55, ..., 0.95, image by image. The image's final detections of the class are visited by calibrated score descending then detection number ascending. A detection matches the unmatched non-ignore ground-truth box of the class with the highest IoU, provided that IoU is at least t; IoU ties go to the smaller gt_id. A detection that matches nothing is ignored when its intersection with an ignore region of the class divided by the detection's own area is at least t; otherwise it is a false positive.",
        "Across all evaluated images the non-ignored detections of the run and class are ranked by calibrated score descending then detection number ascending; precision and recall are taken after each detection, recall over gt_count. Precision is replaced by its running maximum from the right (the precision envelope). AP at t is the mean over the 101 recall points r = 0.00, 0.01, ..., 1.00 of the envelope at the first rank whose recall is at least r, or 0 when no rank reaches r. ap_50 and ap_75 are AP at 0.50 and 0.75; ap_50_95 is the mean of the ten. map_50, map_75 and map_50_95 are means over the classes with gt_count above 0. Means are computed on exact values and rounded only when written."]),
    ("13. Operating points", [
        "For each run and class with gt_count above 0, consider the matching at IoU 0.50 and every distinct calibrated score tau of its non-ignored detections; the detections at or above tau give a precision and a recall. The operating point is the tau whose precision is at least the class's target precision (Release Governance Policy) with the highest recall, the higher tau on a recall tie. threshold, precision and recall are written to six decimals; all three are NA when no tau qualifies or gt_count is 0. target_precision is always written."]),
    ("14. Leaderboard", [
        "The leaderboard reports every reviewed run. protected_ap_50_delta holds, for each protected class, the run's ap_50 minus the incumbent's ap_50, both as written to six decimals (NA when either is NA); it is 0.000000 for the incumbent. decision is INCUMBENT for the incumbent and PROMOTE or HOLD for the others under the Release Governance Policy; release_candidate is chosen there too."]),
    ("15. Reconciliation", [
        "candidates, eval_images, excluded, gt_boxes and ignore_regions count the populations of sections 5 to 10. For each run, accepted counts accepted records of evaluated images whose clipped box has area, after_threshold those at or above the threshold, after_nms those kept by NMS, and final those kept by the per-image cap.",
        "deliveries has one key per delivered file listed in delivery_manifest.toml (the manifest does not list itself) with declared (the sum of the records of the file's manifest partitions; entries with a status of superseded, voided or withdrawn do not count, and entries naming a file that was not delivered are ignored) and parsed (the records actually present in the file). A record is a data row of a CSV, TSV or fixed-width file (header rows and comments are not records), a JSON-lines line, an element of the top-level record array of a JSON file (records, waivers or statuses), an event, object or det element of an XML file, a data row of any workbook sheet, a row of a Parquet file, a row of any table of a SQLite file except preprocess and meta, a line of a preprocess log, a message of a mailbox, a VEVENT of a calendar, an entry of the list of a YAML file, a [[...]] table of a TOML file, a key of a data section of an INI file ([aliases], or each class section of a calibration map) and a register row of a document.",
        "When a delivery holds fewer records than its manifest declares, the delivery is short by whole partitions; the Data Authority Policy says where the missing partitions are recovered from."]),
]

PROSE["eval_standard_v3_1_draft.md"] = [
    ("Status", [
        "DRAFT circulated 2026-11-15 for comment. Not adopted. The body of this draft has no force until the review board adopts it; Appendix A' records freeze amendments with their own status."]),
    ("Proposed changes", [
        "Proposed: LEAK_NEAR is widened to Hamming distance 5.",
        "Proposed: the evaluation window becomes closed at both ends, [2026-09-14T00:00:00Z, 2026-11-09T00:00:00Z].",
        "Proposed: max_detections becomes 100 for every run and NMS uses IoU at or above the threshold.",
        "Proposed: ignore regions match on IoU instead of intersection over the detection area.",
        "Proposed: AP uses all-point interpolation instead of the 101-point grid."]),
]

PROSE["data_authority_policy.docx"] = [
    ("1. Purpose", ["DAP-2 decides which delivered source is authoritative for which records of the PES-3 review. A source that is not authoritative for a record is ignored for that record even when it looks newer, cleaner or more complete."]),
    ("2. Image catalogue", [
        "The frames indexes frames_index_east.csv and frames_index_west.csv are authoritative for capture records. The ingest replica's re-export frames_index_east_v2.csv is authoritative only for cameras that appear in neither frames index; for all other cameras its rows are ignored, and its captured_utc column is never used except that a row with an empty captured_utc was voided by the replica and is ignored. Within the re-export a later row for the same image overrides an earlier one.",
        "camera_deployment_roster.yaml is authoritative for camera sites and offsets. The operations copy camera_deployment_roster_ops.yaml is authoritative only for cameras absent from the main roster; within it a later entry for the same camera and date overrides an earlier one and entries marked active: false are ignored."]),
    ("3. Annotation", [
        "Each image is annotated by the vendor the vendor assignment register (appendix) names; when an image has several register rows, the row with the latest assigned_on wins. Annotations of an image from any other vendor are ignored.",
        "A vendor batch counts only when the receipt register of vendor_batch_receipts.docx records it received at or before the cutoff. Kestrel and Orbis resubmissions (ks_boxes_resubmitted.json, ob_boxes_resubmitted.xml) replace the whole of a batch only when the batch convention register marks that batch RESUBMISSION_ACCEPTED Y; then every original record of the batch is ignored. Resubmitted records of other batches are ignored.",
        "nl_boxes_batch02.csv is short of its manifest. Its missing partitions, and only those, are taken from nl_boxes_batch02_reextract.csv, which preserves the delivery's record order (partition p is records 100(p-1)+1 to 100p of the re-extract). Rows of the re-extract inside partitions present in the delivery are ignored.",
        "QA decisions come from the labeling QA portal snapshot. The spreadsheet export labeling_qa_export.xlsx is authoritative only for its final decisions dated after the portal snapshot and at or before the cutoff; its draft rows and its rows dated at or before the snapshot are ignored."]),
    ("4. Inference", [
        "The inference run registry is authoritative for runs, label maps and node assignments; when it lists a run and sequence more than once, the later row stands. Its mirror inference_run_registry_mirror.html is authoritative only for node assignments of sequences that the registry does not list (again the later of two rows for the same run and sequence stands).",
        "The rerun ledger rerun_batches.toml decides where a rerun's records live; node6_ingest_replica.db and preds_r3_n2_replay.jsonl are authoritative only for the run and image pairs the ledger routes to them with status completed.",
        "Calibration maps are those delivered for each run. The reissued skye-v7.0-rc2 certificate is authoritative only for the classes the original certificate defers to it."]),
    ("5. Exclusion evidence", [
        "The privacy register export privacy_register_export.tsv is a working copy; only its LEGAL-HOLD rows are authoritative (legal holds are recorded nowhere else). Board decisions recorded in any revision of the Release Governance Policy count if decided on or before the cutoff, but only release_governance.docx states the promotion rule.",
        "train_hash_index_legacy.txt and train_hash_index_f_dedup.parquet contribute to the training indexes only as PES-3 section 8 says."]),
]

PROSE["exclusion_policy.docx"] = [
    ("1. Reasons", [
        "WITHDRAWN: the image's lifecycle, read from image_lifecycle_events.xml, ends withdrawn. Events are taken in order of their instant then seq; an event id seen again is a duplicate and only its first occurrence counts; only withdrawn and restored events change the state, and events after the cutoff are ignored.",
        "CORRUPT: the integrity audit status is FAIL. FAIL-RECOVERED, PASS and REENCODED are not corrupt; N/A means the frame was not re-audited and counts as PASS.",
        "PRIVACY_HOLD: the image is held under section 2.",
        "BOARD_OVERRIDE: the latest board decision for the image (by decision date, then decision id) is EXCLUDE.",
        "UNLABELED: the image has no approved relabel campaign item and its assigned vendor delivered no record for it in any batch that counts (deleted and superseded records still count as delivered)."]),
    ("2. Privacy holds", [
        "The appendix lists the privacy takedown register as of 2026-10-15T00:00:00Z: an image with a HOLD row is held, an image with only RELEASED rows is not.",
        "After the register date, messages in privacy_requests.mbox from the privacy office (sender domain privacy-office.skye.example) apply in order of their Date header: TAKEDOWN holds the image, RELEASE releases it, ACK changes nothing. Messages dated at or before the register date are already reflected in the register; messages after the cutoff and messages from any other sender (forwarded copies included) are ignored.",
        "A legal hold (status LEGAL-HOLD in the privacy desk export) holds the image whatever the register and mailbox say."]),
]

PROSE["release_governance.docx"] = [
    ("1. Promotion rule", [
        "A challenger run is promoted (PROMOTE) when its map_50_95 is at least 0.005 above the incumbent's and, for every protected class whose ap_50 is defined for both, its ap_50 is not more than 0.010 below the incumbent's. Both comparisons use the values as written to six decimals; a difference exactly at a bound passes. Otherwise the decision is HOLD.",
        "The release candidate is the promoted run with the highest map_50_95, the smaller run id on a tie; it is null when no run is promoted."]),
    ("2. Protected classes and operating targets", [
        "Protected classes: pedestrian, cyclist, wheelchair_user, stroller. Target precision for operating points is 0.90 for protected classes and 0.80 for every other class."]),
    ("3. Board image decisions", [
        "The appendix records the board's image decisions (EXCLUDE or CONFIRM). Decisions recorded in later revisions of this policy are part of the same record."]),
]

PROSE["release_governance_v2_signed.docx"] = [
    ("Status", ["Version 2, signed by the release lead on 2026-11-18. Awaiting ratification by the review board; until ratified the version 1 promotion rule stays in force."]),
    ("1. Promotion rule (version 2)", [
        "A challenger run is promoted when its map_50_95 is at least 0.003 above the incumbent's and no protected class ap_50 drops by more than 0.020.",
        "Target precision for operating points is 0.85 for every class."]),
    ("2. Board image decisions", ["The appendix continues the board's image decision record."]),
]

PROSE["annotation_batch_conventions.docx"] = [
    ("1. Coordinate formats", [
        "Every vendor record carries four coordinates (coord_1..coord_4, b1..b4, bbox or bbox_px, or the c1..c4 attributes) whose meaning the batch register gives. xywh: x, y, width, height. xyxy: x1, y1, x2, y2 with x2, y2 exclusive. xyxy_inclusive: x1, y1, x2, y2 with x2, y2 inclusive pixel indexes, so the exclusive edge is the value plus 1. cxcywh_norm: centre and size as fractions of the frame width and height. Synonyms used in the register: x,y,w,h = xywh; x1,y1,x2,y2 = xyxy; cx,cy,w,h/norm = cxcywh_norm; x1,y1,x2,y2/incl = xyxy_inclusive.",
        "A Kestrel record whose box is given as bbox_px (or bbox_unit px) holds the cxcywh_norm values multiplied by the frame width and height, in pixels."]),
    ("2. Frames", [
        "upright: the displayed image after applying the final EXIF orientation. stored: the pixel array as stored, before orientation, with the stored dimensions W x H. A stored-frame box is turned upright as follows. Orientation 1: unchanged. Orientation 3: (W - x2, H - y2, W - x1, H - y1). Orientation 6: (H - y2, x1, H - y1, x2). Orientation 8: (y1, W - x2, y2, W - x1). A frame of - in the register means the vendor default: Northlake stored, Kestrel upright, Orbis upright. The default formats are Northlake xywh, Kestrel cxcywh_norm and Orbis xyxy_inclusive."]),
    ("3. Vendor record fields", [
        "Northlake: crowd is Y, N or U (U means not reviewed and is N); status live or deleted. Kestrel: crowd 1, 0 or -1 (-1 means not reviewed and is 0); state active or void (void is deleted); ts is milliseconds since the epoch, or seconds when the value is below 100000000000. Orbis: crowd 1, 0 or -1 as Kestrel; deleted 1 means deleted.",
        "Each annotation may appear in several revisions. A revision that the QA decision log rejects (the latest decision for that annotation and revision) cannot be used; the surviving revision is the highest remaining revision number, and the annotation is dropped when that revision is deleted or when no revision remains."]),
    ("4. Resubmissions", ["RESUBMISSION_ACCEPTED Y in the register means the vendor's resubmitted version of the batch replaces the original delivery of that batch."]),
]

PROSE["vendor_batch_receipts.docx"] = [
    ("Receipts", ["The appendix records when each vendor batch was received. A batch received after the freeze cutoff 2026-11-12T18:00:00Z does not count for PES-3; a batch received exactly at the cutoff does."]),
]

PROSE["taxonomy_v3_charter.docx"] = [
    ("1. Classes", [
        "Taxonomy v3 evaluation classes: pedestrian, cyclist, wheelchair_user, stroller, dog, car, truck, bus, motorcycle, parked_bicycle, traffic_cone, bollard.",
        "Every label of every vendor maps to a class and a disposition: eval (scored ground truth), ignore (an ignore region of the class) or drop (not ground truth)."]),
    ("2. Northlake labels", ["Northlake labels map through the appendix, keyed by project code and raw label; the same raw label can map differently in different projects. Raw labels are matched exactly, accents included."]),
    ("3. Model vocabulary", ["Runs trained on taxonomy v2 emit the v2 model vocabulary; their labels map through the model vocabulary crosswalk below. Labels of later runs are taxonomy v3 class names; e_scooter is not an evaluation class and is dropped."]),
    ("4. Orbis aliases", ["Orbis labels map through ob_label_aliases.yaml, keyed by project code and alias. When the file lists the same project and alias more than once, the later entry overrides the earlier one. A disposition of ~ means the alias was not re-reviewed this cycle and keeps the default disposition eval."]),
]

PROSE["ks_class_codebook.pdf"] = [
    "Kestrel numeric class codes are assigned per project. A code means the class of the row whose validity interval [VALID_FROM, VALID_TO) contains the annotation's ts; VALID_TO - is open. Several projects renumbered their codes during the quarter.",
]

PROSE["annotation_errata_register.md"] = [
    ("Application", [
        "Errata change vendor annotations after the surviving revision is chosen. Entries effective on or before the cutoff date apply in order of effective date then errata id: VOID removes the annotation, RECLASS sets its class (the disposition of its label is kept), REBOX replaces its box with the canonical box x1,y1,x2,y2 given. The effective date is a UTC calendar date. Entries naming an annotation that does not exist change nothing."]),
]

PROSE["labeling_qa_portal.html"] = [
    ("Decision log", ["Each row is one QA decision on one revision of an annotation. The latest decision for an annotation and revision is the one that stands."]),
]

PROSE["frame_integrity_audit.pdf"] = [
    "Statuses: PASS, FAIL (frame does not decode), FAIL-RECOVERED (decoded on retry, usable), REENCODED (frame was re-encoded at ingest; DECODED_W x DECODED_H are its stored dimensions), N/A (not re-audited this cycle; treat as PASS).",
]

PROSE["orientation_corrections.pdf"] = [
    "Corrections to the scanned EXIF orientation. Only confirmed corrections take effect; for an image with several confirmed corrections the latest DECIDED_AT wins (then the larger correction id).",
]

PROSE["training_sequence_register.pdf"] = [
    "Sequences used by the training indexes. STATUS trained means at least one frame of the sequence was in the named training index; held-out sequences were reserved and are not in it.",
]

PROSE["node_quarantine_report.pdf"] = [
    "Run, node and image triples whose node output was quarantined after a scoring fault. Output of a triple whose status is quarantined is void; a released triple was cleared and its output stands.",
]

PROSE["calibration_certificate_rc2.pdf"] = [
    "Isotonic calibration map for skye-v7.0-rc2 (run R3), 512 knots per class. The knots of the classes %s are deferred to the reissue of this certificate.",
]
PROSE["calibration_certificate_rc2_reissue.pdf"] = [
    "Reissue dated 2026-11-20, after the freeze. Contains the full map, including revised knots for every class.",
]

PROSE["inference_run_registry.html"] = [
    ("Rules", [
        "Each run lists its model, status, letterbox input size, score_threshold, nms_iou, max_detections and the training indexes it was trained on. Label maps give the label of each class index per run.",
        "Node dump files are named preds_<run>_<node>.<ext>: the node in the name is the node that wrote the dump, the run in the name only says which run the dump was opened for, and the run of each record is the record's own run field. Each node writes its dumps in its own format (Nodes table). Scores are fractions on n1, n4, n5 and n7, percent on n2 (score_pct; a record with a score key holds a fraction), permille on n3 (score_unit bp means basis points) and basis points on the n6 store. n2 and n6 boxes are cx, cy, w, h; the others x1, y1, x2, y2. Runs are named by run id on n1, n4, n5 and n6 and by model name on n2, n3 and n7.",
        "Preprocess logs record one line per attempt. Line grammars: n1 key=value pairs with pad=x,y and attempt=a/n; n2 letterbox(scale=..., pad_x=..., pad_y=...) with try=a of n and OK or FAILED; n3 and the generic grammar are pipe-separated (node or PREP, time, run, image, scale, pad_x, pad_y, a/n, status); n4 'scale S pads X Y attempt a of n -> status'; n5 s=decimal (fraction) px= py= a=a/n OK or ERR. Any node may also write the generic grammar PREP|time|run|image|scale|pad_x|pad_y|a/n|status. The fraction is the scale."]),
]
PROSE["inference_run_registry_mirror.html"] = PROSE["inference_run_registry.html"]

# ---------------------------------------------------------------------------
# Grading. Everything above this line rebuilds review estates from a seed:
# the shipped /app/data (VISIBLE_SEED), a fresh estate the delivered engine
# has never seen (EVAL_SEED) and a canary estate (CANARY_SEED) that is placed
# where the shipped data would be, so an engine that ignores its ESTATE_DIR
# argument is caught. Expected values come from the reference resolution of
# each estate's source records, never from the agent's files.
# ---------------------------------------------------------------------------
import shutil
import signal
import subprocess
import tempfile
import threading

from rewardkit import criteria, criterion

VISIBLE_SEED = 734190
VISIBLE_SCALE = 1.0
EVAL_SEED = 6151908437711
EVAL_SCALE = 0.12
CANARY_SEED = 90210417
CANARY_SCALE = 0.05
RUN_BUDGET_SEC = 1800
SHIPPED_ESTATE_RECORDS = 1049992
BUDGET_MARGIN = Fraction(5, 4)
OUT = Path("/app/out")
ENGINE = OUT / "evalctl.py"
CSV_ARTIFACTS = {
    "eval_images.csv": ["image_id", "sequence_id", "camera_id", "site_id", "captured_utc", "width", "height", "orientation", "gt_boxes", "ignore_regions"],
    "exclusions.csv": ["image_id", "reason"],
    "ground_truth.csv": ["image_id", "gt_id", "class", "x1", "y1", "x2", "y2", "ignore"],
    "detections.csv": ["run_id", "image_id", "det_id", "class", "x1", "y1", "x2", "y2", "score"],
    "class_metrics.csv": ["run_id", "class", "gt_count", "det_count", "tp_50", "fp_50", "ap_50", "ap_75", "ap_50_95"],
    "operating_points.csv": ["run_id", "class", "target_precision", "threshold", "precision", "recall"],
}
JSON_ARTIFACTS = {"leaderboard.json": ["incumbent", "release_candidate", "runs"],
                  "reconciliation.json": ["candidates", "deliveries", "detections", "eval_images", "excluded", "freeze_list_ids",
                                          "gt_boxes", "gt_by_source", "ignore_regions"]}
IMAGE_COL = {"eval_images.csv": 0, "exclusions.csv": 0, "ground_truth.csv": 0, "detections.csv": 1}
# Image-level artifacts graded per trap family; detections.csv is graded per run so that one
# detection-pipeline slip does not erase the credit for the image decisions and ground truth.
IMAGE_ARTIFACTS = ("eval_images.csv", "exclusions.csv", "ground_truth.csv")
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_VLOCK = threading.Lock()
_HLOCK = threading.Lock()
_CACHE = {}


def _visible():
    with _VLOCK:
        if "vis" not in _CACHE:
            est = build_estate(VISIBLE_SEED, VISIBLE_SCALE)
            truth = resolve(est)
            _CACHE["vis"] = {"truth": truth, "bucket": dict(est.bucket)}
            del est
    return _CACHE["vis"]


def _read_artifacts(folder):
    out = {}
    for name in list(CSV_ARTIFACTS) + list(JSON_ARTIFACTS):
        p = Path(folder) / name
        try:
            out[name] = p.read_bytes() if p.is_file() else None
        except OSError:
            out[name] = None
    return out


def _csv_rows(blob, name):
    """Rows of a well-formed artifact (exact header, LF, trailing newline) or None."""
    if blob is None:
        return None
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError:
        return None
    if "\r" in text or text.startswith("\ufeff") or not text.endswith("\n"):
        return None
    lines = text[:-1].split("\n")
    if lines[0].split(",") != CSV_ARTIFACTS[name]:
        return None
    rows = [ln.split(",") for ln in lines[1:]]
    if any(len(r) != len(CSV_ARTIFACTS[name]) for r in rows):
        return None
    return rows


def _json_obj(blob):
    if blob is None:
        return None
    try:
        return json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None


def _same(a, b):
    """Strict equality: types must match too, so 1, 1.0 and True are all different."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return set(a) == set(b) and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    return a == b


def _rows_for(rows, name, keep):
    col = IMAGE_COL[name]
    return [r for r in rows if keep(r[col])]


def _family_ok(rows, truth, keep):
    for name in IMAGE_ARTIFACTS:
        want = truth[name.rsplit(".", 1)[0]]
        if _rows_for(rows[name], name, keep) != _rows_for(want, name, keep):
            return False
    return True


def _visible_family(fam):
    try:
        art = _read_artifacts(OUT)
        rows = {name: _csv_rows(art.get(name), name) for name in IMAGE_ARTIFACTS}
        if any(v is None for v in rows.values()):
            return False
        vis = _visible()
        bucket = vis["bucket"]
        if fam is None:
            return _family_ok(rows, vis["truth"], lambda i: i not in bucket)
        return _family_ok(rows, vis["truth"], lambda i: bucket.get(i) == fam)
    except Exception:
        return False


def _visible_detections(run):
    """detections.csv rows of one run, exact, on the images both the agent and the truth evaluate.

    Every row must belong to an image of the agent's own eval_images.csv (PES-3 s2). Images the
    agent evaluates wrongly are graded by the image checks, not here; at least half of the truth's
    evaluated images must be shared so an empty or token evaluation set cannot pass.
    """
    try:
        art = _read_artifacts(OUT)
        dets = _csv_rows(art.get("detections.csv"), "detections.csv")
        evals = _csv_rows(art.get("eval_images.csv"), "eval_images.csv")
        if dets is None or evals is None:
            return False
        mine = set(r[0] for r in evals)
        got = [r for r in dets if r[0] == run]
        if any(r[1] not in mine for r in got):
            return False
        truth = _visible()["truth"]
        both = mine & set(truth["_evals"])
        if not both or 2 * len(both) < len(truth["_evals"]):
            return False
        want = [r for r in truth["detections"] if r[0] == run and r[1] in both]
        return [r for r in got if r[1] in both] == want
    except Exception:
        return False


def _plant_canary(est):
    """Put a different estate where the shipped data lives, unless something is already there."""
    target = Path("/app/data")
    if target.exists():
        return None
    write_estate(est, target)
    _open_tree(target)
    return target


def _open_tree(root):
    root = Path(root)
    root.chmod(0o755)
    for p in root.rglob("*"):
        p.chmod(0o755 if p.is_dir() else 0o644)


def _run_budget(est):
    """The instruction's 1800 s for an estate the size of /app/data, scaled to this estate's record volume."""
    records = sum(len(s["recs"]) for n, s in est.files.items() if n != "delivery_manifest.toml")
    budget = Fraction(RUN_BUDGET_SEC * records, SHIPPED_ESTATE_RECORDS) * BUDGET_MARGIN
    return min(RUN_BUDGET_SEC, -(-budget.numerator // budget.denominator))


def _run_engine(engine_copy, estate, out, budget):
    """Run the delivered engine as an unprivileged user; returns (artifacts, finished)."""
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    out.chmod(0o777)
    cmd = [sys.executable, str(engine_copy), str(estate), str(out)]
    if os.geteuid() == 0:
        cmd = _SETPRIV + cmd
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "HOME": "/tmp", "PYTHONHASHSEED": "random"}
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, start_new_session=True, cwd="/tmp")
    finished = True
    try:
        proc.wait(timeout=budget)
    except subprocess.TimeoutExpired:
        finished = False
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    proc.wait()
    return _read_artifacts(out), finished and proc.returncode == 0


def _hidden():
    with _HLOCK:
        if "hid" in _CACHE:
            return _CACHE["hid"]
        res = {"ok": False}
        root = Path(tempfile.mkdtemp(prefix="pes3-eval-"))
        canary = None
        try:
            root.chmod(0o755)
            if not ENGINE.is_file():
                _CACHE["hid"] = res
                return res
            eng_dir = root / "engine"
            eng_dir.mkdir()
            engine_copy = eng_dir / "evalctl.py"
            shutil.copyfile(ENGINE, engine_copy)
            est = build_estate(EVAL_SEED, EVAL_SCALE, (5000000, 7499999))
            estate = root / "review" / "drop_q3"
            write_estate(est, estate)
            res["estate"] = est
            moved = root / "elsewhere" / "inputs"
            shutil.copytree(estate, moved)
            _open_tree(root)
            canary = _plant_canary(build_estate(CANARY_SEED, CANARY_SCALE, (7500000, 9999999)))
            res["canary"] = canary is not None
            budget = _run_budget(est)
            res["budget"] = budget
            runs = (("1", estate, root / "result"), ("2", estate, root / "result"), ("3", moved, root / "other_out"))
            finished = True
            for tag, src, dst in runs:
                if finished:
                    res["a" + tag], res["f" + tag] = _run_engine(engine_copy, src, dst, budget)
                    finished = res["f" + tag]
                else:
                    # An engine that already missed the budget is not run again, so a hang
                    # cannot push grading past the verifier timeout and void the reward.
                    res["a" + tag], res["f" + tag] = {}, False
            res["ok"] = True
        except Exception:
            res["ok"] = False
        finally:
            if canary is not None:
                shutil.rmtree(canary, ignore_errors=True)
        _CACHE["hid"] = res
        return res


def _hidden_truth(h):
    with _HLOCK:
        if "truth" not in h:
            h["truth"] = resolve(h["estate"])
    return h["truth"]


def _hidden_csv(names):
    try:
        h = _hidden()
        if not h.get("ok") or not h.get("f1"):
            return False
        got = [_csv_rows(h["a1"].get(name), name) for name in names]
        if any(g is None for g in got):
            return False
        truth = _hidden_truth(h)
        return all(g == truth[name.rsplit(".", 1)[0]] for g, name in zip(got, names))
    except Exception:
        return False


def _hidden_json(name, key):
    try:
        h = _hidden()
        if not h.get("ok") or not h.get("f1"):
            return False
        obj = _json_obj(h["a1"].get(name))
        if not isinstance(obj, dict) or not obj:
            return False
        return _same(obj, _hidden_truth(h)[key])
    except Exception:
        return False


def _image_numbers(art):
    nums = set()
    for name, col in IMAGE_COL.items():
        rows = _csv_rows(art.get(name), name) or []
        for r in rows:
            if len(r[col]) == 10 and r[col].startswith("IMG") and r[col][3:].isdigit():
                nums.add(int(r[col][3:]))
    return nums


def _phantom_numbers(h):
    """Frozen ids of the fresh estate that match no frame; an engine that wrongly treats them as
    candidates has a candidate-set bug, not a cheat, so the anti-cheat probes skip them."""
    return set(int(r["image"][3:]) for r in h["estate"].freeze if r.get("phantom"))


def _complete(art):
    return all(art.get(n) is not None for n in list(CSV_ARTIFACTS) + list(JSON_ARTIFACTS))


@criterion(description="Rows of images carrying no planted trap are exact in eval_images.csv, exclusions.csv and ground_truth.csv, and no row exists for an image outside the candidate set.")
def baseline_rows_exact(workspace: Path) -> bool:
    return _visible_family(None)


@criterion(description="Images whose records use near-duplicate identifier spellings are exact in the three image artifacts.")
def family_t01_identifier_variants(workspace: Path) -> bool:
    return _visible_family("T1")


@criterion(description="Images whose records state a value in another unit or scale are exact in the three image artifacts.")
def family_t02_units_and_scales(workspace: Path) -> bool:
    return _visible_family("T2")


@criterion(description="Images whose records involve time zones, the DST fold hour, Excel serials or epoch variants are exact in the three image artifacts.")
def family_t03_time_representations(workspace: Path) -> bool:
    return _visible_family("T3")


@criterion(description="Images whose records use decimal commas, digit grouping or parenthesised negatives are exact in the three image artifacts.")
def family_t04_locale_numbers(workspace: Path) -> bool:
    return _visible_family("T4")


@criterion(description="Images whose records carry documented sentinel values are exact in the three image artifacts.")
def family_t05_sentinels(workspace: Path) -> bool:
    return _visible_family("T5")


@criterion(description="Images with deleted, voided, purged, denied or released records that look live are exact in the three image artifacts.")
def family_t06_void_records(workspace: Path) -> bool:
    return _visible_family("T6")


@criterion(description="Images with superseded revisions, decisions, attempts or entries are exact in the three image artifacts.")
def family_t07_superseded_records(workspace: Path) -> bool:
    return _visible_family("T7")


@criterion(description="Images whose rows follow a repeated or reordered header are exact in the three image artifacts.")
def family_t08_header_drift(workspace: Path) -> bool:
    return _visible_family("T8")


@criterion(description="Images whose rows carry quoted delimiters, quoted line breaks or trailing empty fields are exact in the three image artifacts.")
def family_t09_delimiter_quirks(workspace: Path) -> bool:
    return _visible_family("T9")


@criterion(description="Images whose rows sit on lines with another encoding or line ending are exact in the three image artifacts.")
def family_t10_mixed_encodings(workspace: Path) -> bool:
    return _visible_family("T10")


@criterion(description="Images placed on an inclusive or exclusive boundary of a documented window, distance or area are exact in the three image artifacts.")
def family_t11_boundaries(workspace: Path) -> bool:
    return _visible_family("T11")


@criterion(description="Images with coordinates that convert to an exact half pixel are exact in the three image artifacts.")
def family_t12_half_even_rounding(workspace: Path) -> bool:
    return _visible_family("T12")


@criterion(description="Images reached through legacy alias chains or records pointing at out-of-scope entities are exact in the three image artifacts.")
def family_t13_references(workspace: Path) -> bool:
    return _visible_family("T13")


@criterion(description="Images whose register values are corrected by an errata section of a document are exact in the three image artifacts.")
def family_t14_document_errata(workspace: Path) -> bool:
    return _visible_family("T14")


@criterion(description="Images with valid outliers such as giant boxes, large clock skews or near-certain false positives are exact in the three image artifacts.")
def family_t15_valid_outliers(workspace: Path) -> bool:
    return _visible_family("T15")


@criterion(description="Images where a non-authoritative delivery disagrees with the authoritative one are exact in the three image artifacts.")
def family_t16_decoy_disagreements(workspace: Path) -> bool:
    return _visible_family("T16")


@criterion(description="detections.csv rows of run R1 on the shipped estate are exact for the evaluated images, in PES-3 section 2 order.")
def detections_r1_exact(workspace: Path) -> bool:
    return _visible_detections("R1")


@criterion(description="detections.csv rows of run R2 on the shipped estate are exact for the evaluated images, in PES-3 section 2 order.")
def detections_r2_exact(workspace: Path) -> bool:
    return _visible_detections("R2")


@criterion(description="detections.csv rows of run R3 on the shipped estate are exact for the evaluated images, in PES-3 section 2 order.")
def detections_r3_exact(workspace: Path) -> bool:
    return _visible_detections("R3")


@criterion(description="detections.csv rows of run R4 on the shipped estate are exact for the evaluated images, in PES-3 section 2 order.")
def detections_r4_exact(workspace: Path) -> bool:
    return _visible_detections("R4")


@criterion(description="class_metrics.csv for the shipped estate matches PES-3 sections 11 and 12 exactly.")
def class_metrics_exact(workspace: Path) -> bool:
    try:
        got = _csv_rows(_read_artifacts(OUT)["class_metrics.csv"], "class_metrics.csv")
        return got is not None and got == _visible()["truth"]["class_metrics"]
    except Exception:
        return False


@criterion(description="operating_points.csv for the shipped estate matches PES-3 section 13 and the governance targets exactly.")
def operating_points_exact(workspace: Path) -> bool:
    try:
        got = _csv_rows(_read_artifacts(OUT)["operating_points.csv"], "operating_points.csv")
        return got is not None and got == _visible()["truth"]["operating_points"]
    except Exception:
        return False


@criterion(description="leaderboard.json for the shipped estate matches PES-3 section 14 and the Release Governance Policy exactly.")
def leaderboard_exact(workspace: Path) -> bool:
    try:
        obj = _json_obj(_read_artifacts(OUT)["leaderboard.json"])
        return isinstance(obj, dict) and bool(obj) and _same(obj, _visible()["truth"]["leaderboard"])
    except Exception:
        return False


@criterion(description="reconciliation.json population and detection counts for the shipped estate are exact.")
def reconciliation_counts_exact(workspace: Path) -> bool:
    try:
        obj = _json_obj(_read_artifacts(OUT)["reconciliation.json"])
        if not isinstance(obj, dict) or not obj:
            return False
        want = _visible()["truth"]["reconciliation"]
        return all(_same(obj.get(k), want[k]) for k in want if k != "deliveries")
    except Exception:
        return False


@criterion(description="reconciliation.json deliveries reports the declared and parsed record counts of every manifest file exactly.")
def reconciliation_deliveries_exact(workspace: Path) -> bool:
    try:
        obj = _json_obj(_read_artifacts(OUT)["reconciliation.json"])
        if not isinstance(obj, dict) or not obj:
            return False
        return _same(obj.get("deliveries"), _visible()["truth"]["reconciliation"]["deliveries"])
    except Exception:
        return False


@criterion(description="On a fresh estate the delivered engine writes eval_images.csv and exclusions.csv exactly.")
def eval_estate_image_decisions_exact(workspace: Path) -> bool:
    return _hidden_csv(["eval_images.csv", "exclusions.csv"])


@criterion(description="On a fresh estate the delivered engine writes ground_truth.csv exactly.")
def eval_estate_ground_truth_exact(workspace: Path) -> bool:
    return _hidden_csv(["ground_truth.csv"])


@criterion(description="On a fresh estate the delivered engine writes detections.csv exactly.")
def eval_estate_detections_exact(workspace: Path) -> bool:
    return _hidden_csv(["detections.csv"])


@criterion(description="On a fresh estate the delivered engine writes class_metrics.csv, operating_points.csv and leaderboard.json exactly.")
def eval_estate_scoring_exact(workspace: Path) -> bool:
    return _hidden_csv(["class_metrics.csv", "operating_points.csv"]) and _hidden_json("leaderboard.json", "leaderboard")


@criterion(description="On a fresh estate the delivered engine writes reconciliation.json exactly.")
def eval_estate_reconciliation_exact(workspace: Path) -> bool:
    return _hidden_json("reconciliation.json", "reconciliation")


@criterion(description="The engine run on a fresh estate emits image identifiers that only exist in the shipped estate.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # True when the cheat happened: fresh-estate ids are all 5000000 or above.
    try:
        h = _hidden()
        if not h.get("ok") or not h.get("f1"):
            return False
        return any(n < 5000000 for n in _image_numbers(h["a1"]) - _phantom_numbers(h))
    except Exception:
        return False


@criterion(description="The engine writes different artifacts for the same estate when the estate and output directories have other names.")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # True when the cheat happened: same bytes in, different bytes out.
    # Only an engine that is deterministic at one location (runs 1 and 2 identical) can be
    # location dependent; a nondeterministic engine is priced once, by the -3 check below.
    try:
        h = _hidden()
        if not h.get("ok") or not (h.get("f1") and h.get("f2") and h.get("f3")):
            return False
        if not (_complete(h["a1"]) and _complete(h["a2"]) and _complete(h["a3"])):
            return False
        if any(h["a1"][n] != h["a2"][n] for n in h["a1"]):
            return False
        return any(h["a1"][n] != h["a3"][n] for n in h["a1"])
    except Exception:
        return False


@criterion(description="The engine reads the canary estate placed at the shipped data location instead of the estate it was given.")
def negative_reads_shipped_estate_at_runtime(workspace: Path) -> bool:
    # True when the cheat happened: canary-only ids (7500000 and above) leak into the output.
    try:
        h = _hidden()
        if not h.get("ok") or not h.get("canary"):
            return False
        return any(n >= 7500000 for n in (_image_numbers(h["a1"]) | _image_numbers(h["a3"])) - _phantom_numbers(h))
    except Exception:
        return False


@criterion(description="Two runs of the engine on the same estate and output path produce different bytes.")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # True when the cheat happened: identical inputs, different outputs.
    try:
        h = _hidden()
        if not h.get("ok") or not (h.get("f1") and h.get("f2")) or not (_complete(h["a1"]) and _complete(h["a2"])):
            return False
        return any(h["a1"][n] != h["a2"][n] for n in h["a1"])
    except Exception:
        return False


criteria.baseline_rows_exact(weight=5)
criteria.family_t01_identifier_variants(weight=5)
criteria.family_t02_units_and_scales(weight=5)
criteria.family_t03_time_representations(weight=5)
criteria.family_t04_locale_numbers(weight=5)
criteria.family_t05_sentinels(weight=5)
criteria.family_t06_void_records(weight=5)
criteria.family_t07_superseded_records(weight=5)
criteria.family_t08_header_drift(weight=5)
criteria.family_t09_delimiter_quirks(weight=5)
criteria.family_t10_mixed_encodings(weight=5)
criteria.family_t11_boundaries(weight=5)
criteria.family_t12_half_even_rounding(weight=5)
criteria.family_t13_references(weight=5)
criteria.family_t14_document_errata(weight=5)
criteria.family_t15_valid_outliers(weight=5)
criteria.family_t16_decoy_disagreements(weight=5)
criteria.detections_r1_exact(weight=5)
criteria.detections_r2_exact(weight=5)
criteria.detections_r3_exact(weight=5)
criteria.detections_r4_exact(weight=5)
criteria.class_metrics_exact(weight=5)
criteria.operating_points_exact(weight=5)
criteria.leaderboard_exact(weight=5)
criteria.reconciliation_counts_exact(weight=3)
criteria.reconciliation_deliveries_exact(weight=3)
criteria.eval_estate_image_decisions_exact(weight=5)
criteria.eval_estate_ground_truth_exact(weight=5)
criteria.eval_estate_detections_exact(weight=5)
criteria.eval_estate_scoring_exact(weight=5)
criteria.eval_estate_reconciliation_exact(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_reads_shipped_estate_at_runtime(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
