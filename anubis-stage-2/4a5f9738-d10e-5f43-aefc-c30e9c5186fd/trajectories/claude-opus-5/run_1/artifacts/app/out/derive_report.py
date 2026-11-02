#!/usr/bin/env python3
"""Derive the coexistence occupancy measurement from the register corpus.

Usage: python3 derive_report.py <corpus_dir> <output_dir>

Standard library only.  Reads nothing outside <corpus_dir>, writes nothing
outside <output_dir>, leaves the corpus unchanged.
"""

import csv
import json
import os
import re
import sys
from bisect import bisect_right

# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

DAY = 86400
ZONES = ["East", "North", "South", "West"]
LAYERS = ["coord", "core", "office"]
GROUPS = ["identity", "time", "frequency"]
PUBLISHED_RANK = {"coord": 1, "core": 2, "office": 3}

REJECT_ORDER = [
    "TERM_MISSING",
    "SPAN_INVERTED",
    "UNIT_AMBIGUOUS",
    "BAND_OUTSIDE",
    "RASTER_MISALIGNED",
    "HOLDER_UNKNOWN",
    "ZONE_MISMATCH",
    "PARENT_UNKNOWN",
    "PARENT_CYCLE",
    "PARENT_RETRACTED",
]

NOTE_CODES = [
    "ALIAS_RESOLVED",
    "CLIPPED_TO_BAND",
    "CLIPPED_TO_HORIZON",
    "OPEN_ENDED",
    "WIDTH_MISMATCH",
    "ZONE_OF_RECORD_DIFFERS",
    "SPLIT_BY_RASTER",
    "STATE_ANOMALY",
    "ZERO_SPAN",
]

def days_from_civil(y, m, d):
    """Days since 1970-01-01 (proleptic Gregorian)."""
    yy = y - (1 if m <= 2 else 0)
    era = (yy if yy >= 0 else yy - 399) // 400
    yoe = yy - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z):
    z += 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    return (y + (1 if m <= 2 else 0), m, d)


def epoch_of_date(s):
    y, m, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
    return days_from_civil(y, m, d) * DAY


def parse_naive(s):
    """'YYYY-MM-DD[T ]HH:MM[:SS]' -> seconds since epoch treating it as UTC."""
    s = s.strip()
    y, mo, d = int(s[0:4]), int(s[5:7]), int(s[8:10])
    hh = mm = ss = 0
    if len(s) > 10:
        hh = int(s[11:13])
        mm = int(s[14:16])
        if len(s) >= 19:
            ss = int(s[17:19])
    return days_from_civil(y, mo, d) * DAY + hh * 3600 + mm * 60 + ss


def parse_utc(s):
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1]
    return parse_naive(s)


_OFF_RE = re.compile(r"([+-])(\d{2}):(\d{2})$")


def parse_offset_stamp(s):
    s = s.strip()
    if s.endswith("Z"):
        return parse_naive(s[:-1])
    m = _OFF_RE.search(s)
    if not m:
        return parse_naive(s)
    sign = 1 if m.group(1) == "+" else -1
    off = sign * (int(m.group(2)) * 3600 + int(m.group(3)) * 60)
    return parse_naive(s[: m.start()]) - off


def fmt_utc(t):
    d, rem = divmod(t, DAY)
    y, mo, dd = civil_from_days(d)
    hh, rem = divmod(rem, 3600)
    mi, ss = divmod(rem, 60)
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (y, mo, dd, hh, mi, ss)


def round_half_even(num, den):
    """round(num/den) with banker's rounding, integers only."""
    q, r = divmod(num, den)
    twice = 2 * r
    if twice > den or (twice == den and q % 2 == 1):
        q += 1
    return q


def largest_remainder(weights, total):
    """Allocate `total` integer units over dict weights by largest remainder."""
    keys = sorted(weights)
    s = sum(weights[k] for k in keys)
    if s <= 0:
        return {k: 0 for k in keys}
    base = {}
    rema = {}
    for k in keys:
        q, r = divmod(weights[k] * total, s)
        base[k] = q
        rema[k] = r
    left = total - sum(base.values())
    order = sorted(keys, key=lambda k: (-rema[k], k))
    for k in order[:left]:
        base[k] += 1
    return base


# --------------------------------------------------------------------------
# interval algebra on half open integer intervals
# --------------------------------------------------------------------------

def norm_iv(ivs):
    """sort and merge a list of (a, b) half open intervals"""
    out = []
    for a, b in sorted(ivs):
        if b <= a:
            continue
        if out and a <= out[-1][1]:
            if b > out[-1][1]:
                out[-1][1] = b
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def iv_intersect(xs, ys):
    out = []
    i = j = 0
    while i < len(xs) and j < len(ys):
        a = max(xs[i][0], ys[j][0])
        b = min(xs[i][1], ys[j][1])
        if b > a:
            out.append((a, b))
        if xs[i][1] < ys[j][1]:
            i += 1
        else:
            j += 1
    return out


def iv_subtract(xs, ys):
    """xs minus ys, both normalised"""
    out = []
    j = 0
    for a, b in xs:
        cur = a
        k = j
        while k < len(ys) and ys[k][1] <= cur:
            k += 1
        j = k
        while k < len(ys) and ys[k][0] < b:
            ya, yb = ys[k]
            if ya > cur:
                out.append((cur, min(ya, b)))
            cur = max(cur, yb)
            if cur >= b:
                break
            k += 1
        if cur < b:
            out.append((cur, b))
    return out


def iv_measure(xs):
    return sum(b - a for a, b in xs)


# --------------------------------------------------------------------------
# zone clocks
# --------------------------------------------------------------------------

class ZoneClock(object):
    def __init__(self, name, std, summer, win_utc):
        self.name = name
        self.std = std
        self.summer = summer
        self.win = win_utc  # (start, end) in utc or None

    def offset_at_utc(self, t):
        if self.win and self.win[0] <= t < self.win[1]:
            return self.summer
        return self.std

    def to_utc(self, local):
        """local wall clock seconds -> utc seconds"""
        cands = []
        for off in (self.std, self.summer):
            t = local - off
            if self.offset_at_utc(t) == off:
                cands.append(t)
        if len(cands) == 1:
            return cands[0]
        return local - self.std

    def to_local(self, t):
        return t + self.offset_at_utc(t)


# --------------------------------------------------------------------------
# corpus reading
# --------------------------------------------------------------------------

def md_table(path):
    rows = []
    header = None
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line.startswith("|"):
                continue
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-: ") and c for c in cells):
                continue
            if header is None:
                header = cells
            else:
                rows.append(dict(zip(header, cells)))
    return rows


def read_csv(path, delim=","):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh, delimiter=delim))


def read_ini(path):
    out = {}
    sec = None
    with open(path) as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                sec = line[1:-1]
                out[sec] = {}
            elif "=" in line and sec is not None:
                k, v = line.split("=", 1)
                out[sec][k.strip()] = v.strip()
    return out


class Corpus(object):
    def __init__(self, root):
        self.root = root

    def p(self, name):
        return os.path.join(self.root, name)


# --------------------------------------------------------------------------
# main derivation
# --------------------------------------------------------------------------

class Record(object):
    __slots__ = (
        "aid", "layer", "revision", "recorded_at", "action", "file",
        "zone", "holder_ref", "parent_id", "has_identity",
        "eff_from", "eff_to", "eff_to_open", "eff_to_deferred", "has_time",
        "has_freq", "f_lo", "f_hi", "f_width", "freq_bad", "width_mismatch",
    )

    def __init__(self):
        self.has_identity = False
        self.has_time = False
        self.has_freq = False
        self.zone = None
        self.holder_ref = None
        self.parent_id = ""
        self.eff_from = None
        self.eff_to = None
        self.eff_to_open = False
        self.eff_to_deferred = False
        self.f_lo = None
        self.f_hi = None
        self.f_width = None
        self.freq_bad = False
        self.width_mismatch = False


def build(corpus_dir, as_of_override=None):
    C = Corpus(corpus_dir)
    rep = {}

    cfg = read_ini(C.p("measure_config.ini"))
    H0 = parse_utc(cfg["horizon"]["start"])
    H1 = parse_utc(cfg["horizon"]["end"])
    AS_OF = parse_utc(cfg["horizon"]["as_of"])
    AS_OF_DECLARED = AS_OF
    if as_of_override is not None:
        AS_OF = as_of_override
    SHARE_BP = int(cfg["measure"]["share_total_bp"])
    PPM = int(cfg["measure"]["ppm_scale"])
    SHARED_MIN = int(cfg["measure"]["shared_multiplicity_min"])
    TOP_HOLDERS = int(cfg["limits"]["top_holders"])
    TOP_EXCESS = int(cfg["limits"]["top_excess"])
    TOP_DEFICIT = int(cfg["limits"]["top_deficit"])

    units = read_ini(C.p("unit_declarations.ini"))

    # ---- band plan ------------------------------------------------------
    bands = []
    for r in md_table(C.p("band_plan.md")):
        if not r.get("band", "").startswith("B"):
            continue
        bands.append((r["band"], int(r["f_low_khz"]), int(r["f_high_khz"]), int(r["raster_khz"])))
    band_ids = [b[0] for b in bands]

    # ---- channel raster -------------------------------------------------
    raster = read_csv(C.p("channel_raster.csv"))
    usable_by_band = {}
    lower_edges = set()
    upper_edges = set()
    for r in raster:
        lo = int(r["f_low_khz"])
        hi = int(r["f_high_khz"])
        lower_edges.add(lo)
        upper_edges.add(hi)
        if r["status"] == "usable":
            usable_by_band.setdefault(r["band"], []).append((lo, hi))
    usable_all = norm_iv([iv for v in usable_by_band.values() for iv in v])
    for k in usable_by_band:
        usable_by_band[k] = norm_iv(usable_by_band[k])
    band_span = {b[0]: [(b[1], b[2])] for b in bands}

    # ---- zone clocks ----------------------------------------------------
    zrules = {}
    for r in md_table(C.p("zone_time_rules.md")):
        z = r.get("zone")
        if z not in ZONES:
            continue
        zrules[z] = r

    marks = [r for r in read_csv(C.p("zone_clock_marks.csv"))
             if r["jurisdiction"] == units["zone_clock_marks"]["authoritative_jurisdiction"]]

    def clocks_for(keying):
        out = {}
        for z in ZONES:
            r = zrules[z]
            std = int(r["standard_offset_sec"])
            summer = int(r["summer_offset_sec"])
            if r["summer_from"] == "none":
                out[z] = ZoneClock(z, std, summer, None)
            else:
                a = parse_naive(r["summer_from"])
                b = parse_naive(r["summer_to"])
                if keying == "local_standard":
                    a -= std
                    b -= std
                out[z] = ZoneClock(z, std, summer, (a, b))
        return out

    keying_scores = {}
    for keying in ("local_standard", "utc"):
        cl = clocks_for(keying)
        bad = 0
        for r in marks:
            z = r["zone"]
            t = parse_utc(r["utc_stamp"])
            if cl[z].to_local(t) != parse_naive(r["local_stamp"]):
                bad += 1
        keying_scores[keying] = bad
    clock_keying = min(sorted(keying_scores), key=lambda k: keying_scores[k])
    rep["clock_keying"] = clock_keying
    rep["clock_keying_scores"] = keying_scores
    CLOCK = clocks_for(clock_keying)

    # ---- duplicate tiebreak --------------------------------------------
    flags = read_csv(C.p("register_governing_flags.csv"))
    groups = {}
    for r in flags:
        groups.setdefault((r["assignment_id"], r["layer"], int(r["revision"])), []).append(r)
    votes = {"earliest_recorded_at": 0, "latest_recorded_at": 0}
    for k, v in groups.items():
        if len(v) < 2:
            continue
        true_rows = [x for x in v if x["governing"].strip().lower() == "true"]
        if len(true_rows) != 1:
            continue
        stamps = sorted(parse_utc(x["recorded_at"]) for x in v)
        t = parse_utc(true_rows[0]["recorded_at"])
        if t == stamps[0]:
            votes["earliest_recorded_at"] += 1
        if t == stamps[-1]:
            votes["latest_recorded_at"] += 1
    tiebreak = max(sorted(votes), key=lambda k: votes[k])
    rep["duplicate_tiebreak"] = tiebreak
    rep["tiebreak_votes"] = votes

    # ---- source records -------------------------------------------------
    index = {}
    for r in md_table(C.p("corpus_index.md")):
        if "file" in r:
            index[r["file"]] = r["layer"]
    record_files = sorted(index)

    rows_read = dict((f, 0) for f in record_files)
    rows_visible = dict((f, 0) for f in record_files)
    rows_governing = dict((f, 0) for f in record_files)

    records = []  # all grant layer records

    def hz_to_khz(v):
        """returns (khz, ok)"""
        if v % 1000 != 0:
            return (0, False)
        return (v // 1000, True)

    # core
    for fname in [f for f in record_files if index[f] == "core"]:
        for r in read_csv(C.p(fname)):
            rows_read[fname] += 1
            rec = Record()
            rec.file = fname
            rec.layer = "core"
            rec.aid = r["assignment_id"]
            rec.revision = int(r["revision"])
            rec.recorded_at = parse_utc(r["recorded_at"])
            rec.action = r["action"]
            rec.has_identity = True
            rec.zone = r["zone"]
            rec.holder_ref = r["holder_ref"]
            rec.parent_id = r["parent_id"]
            rec.has_time = True
            rec.eff_from = parse_utc(r["effective_from"])
            if r["effective_to"] == "":
                rec.eff_to_open = True
                rec.eff_to = H1
            elif r["effective_to"].lower() in ("null", "none"):
                rec.eff_to_deferred = True
            else:
                rec.eff_to = parse_utc(r["effective_to"])
            rec.has_freq = True
            rec.f_lo = int(r["f_low_khz"])
            rec.f_width = int(r["bandwidth_khz"]) if r["bandwidth_khz"] != "" else None
            if r["f_high_khz"] != "":
                rec.f_hi = int(r["f_high_khz"])
                if rec.f_width is not None and rec.f_lo + rec.f_width != rec.f_hi:
                    rec.width_mismatch = True
            elif rec.f_width is not None:
                rec.f_hi = rec.f_lo + rec.f_width
            else:
                rec.freq_bad = True
            records.append(rec)

    # office
    offu = units["zone_office_log"]
    for fname in [f for f in record_files if index[f] == "office"]:
        zone = fname.split("_")[3].capitalize()
        clk = CLOCK[zone]
        for r in read_csv(C.p(fname), "\t"):
            rows_read[fname] += 1
            rec = Record()
            rec.file = fname
            rec.layer = "office"
            rec.aid = r["assignment_id"]
            rec.revision = int(r["revision"])
            rec.recorded_at = clk.to_utc(parse_naive(r["recorded_at_local"]))
            rec.action = r["action"]
            rec.has_identity = True
            rec.zone = zone
            rec.holder_ref = r["holder_label"]
            rec.parent_id = ""
            rec.has_time = True
            rec.eff_from = clk.to_utc(parse_naive(r["effective_from_local"]))
            if r["effective_to_local"] == "":
                rec.eff_to_open = True
                rec.eff_to = H1
            else:
                rec.eff_to = clk.to_utc(parse_naive(r["effective_to_local"]))
            if r[offu["f_low_column"]] != "":
                rec.has_freq = True
                lo, ok1 = hz_to_khz(int(r[offu["f_low_column"]]))
                wraw = r[offu["width_column"]]
                if wraw == "":
                    rec.freq_bad = True
                    rec.f_lo = lo
                else:
                    w, ok2 = hz_to_khz(int(wraw))
                    rec.f_lo = lo
                    rec.f_width = w
                    rec.f_hi = lo + w
                    if not (ok1 and ok2):
                        rec.freq_bad = True
            records.append(rec)

    # coord
    cu = units["coordination_decisions"]
    accepted = [t.strip() for t in cu["accepted_unit_tokens"].split(",")]
    unit_factor = {"kHz": 1, "Hz": None}
    for fname in [f for f in record_files if index[f] == "coord"]:
        with open(C.p(fname)) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                d = json.loads(line)
                rows_read[fname] += 1
                rec = Record()
                rec.file = fname
                rec.layer = "coord"
                rec.aid = d["assignment_id"]
                rec.revision = int(d["revision"])
                rec.recorded_at = parse_offset_stamp(d["recorded_at"])
                rec.action = d["action"]
                if "zone" in d or "holder_ref" in d:
                    rec.has_identity = True
                    rec.zone = d.get("zone")
                    rec.holder_ref = d.get("holder_ref")
                    rec.parent_id = d.get("parent_id") or ""
                if "effective_from" in d or "effective_to" in d:
                    rec.has_time = True
                    ef = d.get("effective_from")
                    et = d.get("effective_to", "")
                    if ef is None:
                        rec.eff_to_deferred = True
                    else:
                        rec.eff_from = parse_offset_stamp(ef)
                    if et is None:
                        rec.eff_to_deferred = True
                    elif et == "":
                        rec.eff_to_open = True
                        rec.eff_to = H1
                    else:
                        rec.eff_to = parse_offset_stamp(et)
                if "f_low_khz" in d:
                    rec.has_freq = True
                    rec.f_lo = int(d["f_low_khz"])
                    tok = d.get(cu["unit_column"])
                    w = d.get("bandwidth")
                    if tok is None or tok not in accepted:
                        rec.freq_bad = True
                    elif w is None:
                        rec.freq_bad = True
                    else:
                        w = int(w)
                        if tok == "Hz":
                            if w % 1000 != 0:
                                rec.freq_bad = True
                            else:
                                rec.f_width = w // 1000
                        else:
                            rec.f_width = w
                    if "f_high_khz" in d and d["f_high_khz"] is not None:
                        rec.f_hi = int(d["f_high_khz"])
                        if rec.f_width is not None and rec.f_lo + rec.f_width != rec.f_hi:
                            rec.width_mismatch = True
                    elif rec.f_width is not None:
                        rec.f_hi = rec.f_lo + rec.f_width
                    else:
                        rec.freq_bad = True
                records.append(rec)

    # non grant record files: just count rows
    for fname in record_files:
        if index[fname] != "reference":
            continue
        if fname.endswith(".csv"):
            rows_read[fname] = len(read_csv(C.p(fname)))
        elif fname.endswith(".tsv"):
            rows_read[fname] = len(read_csv(C.p(fname), "\t"))

    # ---- visibility and governing records -------------------------------
    visible = [r for r in records if r.recorded_at < AS_OF]
    for r in visible:
        rows_visible[r.file] += 1

    by_layer = {}
    for r in visible:
        by_layer.setdefault((r.aid, r.layer), []).append(r)

    sign = 1 if tiebreak == "earliest_recorded_at" else -1
    governing = {}
    for k, v in by_layer.items():
        best = min(v, key=lambda r: (-r.revision, sign * r.recorded_at))
        governing[k] = best
        rows_governing[best.file] += 1

    all_ids = sorted(set(r.aid for r in records))
    visible_ids = sorted(set(r.aid for r in visible))

    rep["all_ids"] = all_ids
    rep["visible_ids"] = visible_ids

    # ---- holder normalisation and alias map -----------------------------
    def canon(ref):
        s = (ref or "").upper()
        s = "".join(ch for ch in s if ch.isalnum())
        if s.startswith("HL"):
            s = s[2:]
        if len(s) > 6:
            s = s[-6:]
        elif len(s) < 6:
            s = s.rjust(6, "0")
        return s

    alias = {}
    for r in read_csv(C.p("holder_alias_map.csv")):
        alias[r["alias_id"]] = r["canonical_id"]
    amap = dict((k, v) for k, v in alias.items() if k != v)

    cycle_set = set()
    seen_global = set()
    n_cycles = 0
    for k in amap:
        if k in seen_global:
            continue
        path = []
        pos = {}
        cur = k
        while cur in amap and cur not in pos:
            pos[cur] = len(path)
            path.append(cur)
            cur = amap[cur]
        if cur in pos:
            cyc = path[pos[cur]:]
            if not (set(cyc) & cycle_set):
                n_cycles += 1
            cycle_set.update(cyc)
        seen_global.update(path)

    resolve_cache = {}

    def resolve_alias(cid):
        hit = resolve_cache.get(cid)
        if hit is not None:
            return hit
        path = [cid]
        pos = {cid: 0}
        cur = cid
        while cur in amap:
            nxt = amap[cur]
            if nxt in pos:
                cyc = path[pos[nxt]:]
                target = min(cyc)
                depth = pos[target]
                res = (target, depth)
                break
            pos[nxt] = len(path)
            path.append(nxt)
            cur = nxt
        else:
            res = (cur, len(path) - 1)
        resolve_cache[cid] = res
        return res

    rep["alias_cycles"] = n_cycles
    rep["resolve_alias"] = resolve_alias
    rep["canon"] = canon
    rep["amap"] = amap

    # ---- holder registry -------------------------------------------------
    registry = {}
    for z in ZONES:
        fname = "holder_registry_%s.csv" % z.lower()
        for i, r in enumerate(read_csv(C.p(fname))):
            registry.setdefault(r["canonical_id"], []).append(
                (epoch_of_date(r["as_of"]), r["zone_of_record"], r["holder_class"], fname, i)
            )

    def registry_row(cid, grant_zone):
        rows = registry.get(cid)
        if not rows:
            return None
        best = None
        for row in rows:
            key = (-row[0], 0 if row[1] == grant_zone else 1, row[1], row[3], row[4])
            if best is None or key < best[0]:
                best = (key, row)
        return best[1]

    status_hist = {}
    for r in read_csv(C.p("holder_status_history.csv")):
        status_hist.setdefault(r["canonical_id"], []).append(
            (epoch_of_date(r["status_from"]), r["status"])
        )
    for k in status_hist:
        status_hist[k].sort()

    def holder_status(cid, at):
        rows = status_hist.get(cid)
        if not rows:
            return "provisional"
        best = None
        for t, st in rows:
            if t <= at:
                if best is None or (t, st) > best:
                    best = (t, st)
            else:
                break
        if best is None:
            return "provisional"
        return best[1]

    rep.update(dict(
        H0=H0, H1=H1, AS_OF=AS_OF, cfg=cfg, bands=bands, band_ids=band_ids,
        usable_all=usable_all, usable_by_band=usable_by_band, band_span=band_span,
        lower_edges=lower_edges, upper_edges=upper_edges,
        CLOCK=CLOCK, governing=governing, records=records, visible=visible,
        rows_read=rows_read, rows_visible=rows_visible, rows_governing=rows_governing,
        index=index, record_files=record_files, registry=registry,
        registry_row=registry_row, holder_status=holder_status,
        SHARE_BP=SHARE_BP, PPM=PPM, SHARED_MIN=SHARED_MIN,
        TOP_HOLDERS=TOP_HOLDERS, TOP_EXCESS=TOP_EXCESS, TOP_DEFICIT=TOP_DEFICIT,
        corpus=C,
    ))
    return rep


# --------------------------------------------------------------------------
# rectangle sets
# --------------------------------------------------------------------------

def rects_to_strips(rects):
    """rects: list of (f0, f1, t0, t1) -> canonical strip list [(f0, f1, ivs)]"""
    if not rects:
        return []
    bounds = sorted(set([r[0] for r in rects] + [r[1] for r in rects]))
    starts = {}
    ends = {}
    for i, r in enumerate(rects):
        starts.setdefault(r[0], []).append(i)
        ends.setdefault(r[1], []).append(i)
    active = set()
    out = []
    for i in range(len(bounds) - 1):
        a = bounds[i]
        b = bounds[i + 1]
        for j in ends.get(a, ()):
            active.discard(j)
        for j in starts.get(a, ()):
            active.add(j)
        if not active:
            continue
        ivs = norm_iv([(rects[j][2], rects[j][3]) for j in active])
        if ivs:
            out.append((a, b, ivs))
    return strip_canon(out)


def strip_canon(strips):
    out = []
    for f0, f1, ivs in strips:
        if not ivs or f1 <= f0:
            continue
        if out and out[-1][1] == f0 and out[-1][2] == ivs:
            out[-1][1] = f1
        else:
            out.append([f0, f1, ivs])
    return [(a, b, c) for a, b, c in out]


def _strip_lookup(strips):
    keys = [s[0] for s in strips]

    def get(x):
        i = bisect_right(keys, x) - 1
        if i < 0:
            return None
        s = strips[i]
        if s[0] <= x < s[1]:
            return s[2]
        return None

    return get


def strip_combine(A, B, fn):
    if not A and not B:
        return []
    bounds = sorted(set([s[0] for s in A] + [s[1] for s in A] +
                        [s[0] for s in B] + [s[1] for s in B]))
    ga = _strip_lookup(A)
    gb = _strip_lookup(B)
    out = []
    for i in range(len(bounds) - 1):
        a = bounds[i]
        b = bounds[i + 1]
        ivs = fn(ga(a) or [], gb(a) or [])
        if ivs:
            out.append((a, b, ivs))
    return strip_canon(out)


def strip_subtract(A, B):
    return strip_combine(A, B, lambda x, y: iv_subtract(x, y) if y else list(x))


def strip_intersect(A, B):
    return strip_combine(A, B, lambda x, y: iv_intersect(x, y) if (x and y) else [])


def strip_measure(S):
    return sum((f1 - f0) * iv_measure(ivs) for f0, f1, ivs in S)


def strips_to_rects(S):
    out = []
    for f0, f1, ivs in S:
        for a, b in ivs:
            out.append((f0, f1, a, b))
    return out


def reduce_rects(rects):
    cur = list(rects)
    while True:
        changed = False
        # merge touching in frequency sharing both time bounds
        by_t = {}
        for r in cur:
            by_t.setdefault((r[2], r[3]), []).append(r)
        nxt = []
        for key in by_t:
            grp = sorted(by_t[key])
            run = list(grp[0])
            for r in grp[1:]:
                if r[0] == run[1]:
                    run[1] = r[1]
                    changed = True
                else:
                    nxt.append(tuple(run))
                    run = list(r)
            nxt.append(tuple(run))
        cur = nxt
        # merge touching in time sharing both frequency bounds
        by_f = {}
        for r in cur:
            by_f.setdefault((r[0], r[1]), []).append(r)
        nxt = []
        for key in by_f:
            grp = sorted(by_f[key], key=lambda r: (r[2], r[3]))
            run = list(grp[0])
            for r in grp[1:]:
                if r[2] == run[3]:
                    run[3] = r[3]
                    changed = True
                else:
                    nxt.append(tuple(run))
                    run = list(r)
            nxt.append(tuple(run))
        cur = nxt
        if not changed:
            return sorted(cur)


def rect_measure(rects):
    return sum((r[1] - r[0]) * (r[3] - r[2]) for r in rects)


# --------------------------------------------------------------------------
# arrangement sweep
# --------------------------------------------------------------------------

def arrange(rects, extra_time_bounds=()):
    """rects: list of (f0, f1, t0, t1, key).

    Yields (f0, f1, t0, t1, [keys]) for every atomic cell with coverage,
    where keys may repeat if several extents of the same key cover the cell.
    """
    if not rects:
        return
    fb = sorted(set([r[0] for r in rects] + [r[1] for r in rects]))
    fstart = {}
    fend = {}
    for i, r in enumerate(rects):
        fstart.setdefault(r[0], []).append(i)
        fend.setdefault(r[1], []).append(i)
    extra = tuple(extra_time_bounds)
    active = set()
    for i in range(len(fb) - 1):
        a = fb[i]
        b = fb[i + 1]
        for j in fend.get(a, ()):
            active.discard(j)
        for j in fstart.get(a, ()):
            active.add(j)
        if not active:
            continue
        items = [(rects[j][2], rects[j][3], rects[j][4]) for j in active]
        tb = set(extra)
        for t0, t1, k in items:
            tb.add(t0)
            tb.add(t1)
        tbs = sorted(tb)
        tstart = {}
        tend = {}
        for idx, (t0, t1, k) in enumerate(items):
            tstart.setdefault(t0, []).append(idx)
            tend.setdefault(t1, []).append(idx)
        act = set()
        for u in range(len(tbs) - 1):
            c = tbs[u]
            dd = tbs[u + 1]
            for j in tend.get(c, ()):
                act.discard(j)
            for j in tstart.get(c, ()):
                act.add(j)
            if not act:
                continue
            yield (a, b, c, dd, [items[j][2] for j in act])


# --------------------------------------------------------------------------
# part two of the derivation
# --------------------------------------------------------------------------

def derive(corpus_dir, out_dir, as_of_override=None, write=True):
    R = build(corpus_dir, as_of_override)
    C = R["corpus"]
    H0 = R["H0"]
    H1 = R["H1"]
    AS_OF = R["AS_OF"]
    CLOCK = R["CLOCK"]
    gov = R["governing"]
    canon = R["canon"]
    resolve_alias = R["resolve_alias"]
    registry_row = R["registry_row"]
    holder_status = R["holder_status"]
    registry = R["registry"]
    usable_all = R["usable_all"]
    lower_edges = R["lower_edges"]
    upper_edges = R["upper_edges"]
    bands = R["bands"]
    band_ids = R["band_ids"]
    all_ids = R["all_ids"]
    SHARED_MIN = R["SHARED_MIN"]

    notes = dict((k, 0) for k in NOTE_CODES)
    rejects = dict((k, 0) for k in REJECT_ORDER)

    GROUP_ATTR = {"identity": "has_identity", "time": "has_time", "frequency": "has_freq"}

    def supplies(rec, group):
        if rec.action == "note":
            return False
        return getattr(rec, GROUP_ATTR[group])

    supply = {}
    for aid in all_ids:
        s = {}
        for g in GROUPS:
            s[g] = [L for L in LAYERS if (aid, L) in gov and supplies(gov[(aid, L)], g)]
        supply[aid] = s

    def winner(aid, group, ranks):
        ls = supply[aid][group]
        if not ls:
            return None
        return min(ls, key=lambda L: ranks[L])

    # ---- identity, holder, segment --------------------------------------
    ident = {}
    seg_of = {}
    holder_of = {}
    alias_depth_of = {}
    reg_of = {}
    for aid in all_ids:
        L = winner(aid, "identity", PUBLISHED_RANK)
        rec = gov[(aid, L)]
        ident[aid] = (L, rec)
        cid, dep = resolve_alias(canon(rec.holder_ref))
        holder_of[aid] = cid
        alias_depth_of[aid] = dep
        row = registry_row(cid, rec.zone)
        reg_of[aid] = row
        seg_of[aid] = row[2] if row else None

    # ---- precedence exception -------------------------------------------
    dev = {}
    for o in read_csv(C.p("precedence_observations.csv")):
        aid = o["assignment_id"]
        if aid not in supply:
            continue
        g = o["field_group"]
        L = o["layer_followed"]
        if winner(aid, g, PUBLISHED_RANK) != L:
            dev[(seg_of[aid], g, L)] = dev.get((seg_of[aid], g, L), 0) + 1
    if dev:
        exc = max(sorted(dev), key=lambda k: dev[k])
        exception = {"segment": exc[0], "field_group": exc[1], "layer": exc[2]}
    else:
        exception = {"segment": None, "field_group": None, "layer": None}

    exc_ranks = dict(PUBLISHED_RANK)
    if exception["layer"]:
        others = sorted([L for L in LAYERS if L != exception["layer"]],
                        key=lambda L: PUBLISHED_RANK[L])
        exc_ranks = {exception["layer"]: 1}
        for i, L in enumerate(others):
            exc_ranks[L] = i + 2

    def ranks_for(aid, group):
        if group == exception["field_group"] and seg_of[aid] == exception["segment"]:
            return exc_ranks
        return PUBLISHED_RANK

    group_winner = {}
    for aid in all_ids:
        for g in GROUPS:
            group_winner[(aid, g)] = winner(aid, g, ranks_for(aid, g))

    # ---- retraction notices ---------------------------------------------
    notice_rows = read_csv(C.p("retraction_notices.csv"))
    nb = {}
    for r in notice_rows:
        if parse_utc(r["recorded_at"]) >= AS_OF:
            continue
        nb.setdefault((r["assignment_id"], r["notice_date"]), []).append(
            (parse_utc(r["recorded_at"]), r["scope"]))
    live_notice = set()
    for key, rows in nb.items():
        rows.sort()
        fulls = [t for t, s in rows if s == "full"]
        cancels = [t for t, s in rows if s == "withdrawn"]
        alive = []
        for t in fulls:
            alive.append([t, True])
        for ct in cancels:
            for item in alive:
                if item[1] and item[0] < ct:
                    item[1] = False
                    break
        if any(item[1] for item in alive):
            live_notice.add(key[0])

    withdrawn = set()
    for aid in all_ids:
        rec = ident[aid][1]
        if rec.action == "retract" or aid in live_notice:
            withdrawn.add(aid)

    # ---- layer governing counts -----------------------------------------
    layer_counts = dict((L, 0) for L in LAYERS)
    tested = [aid for aid in all_ids if aid not in withdrawn]
    for aid in tested:
        for g in GROUPS:
            L = group_winner[(aid, g)]
            if L:
                layer_counts[L] += 1

    # ---- field values ----------------------------------------------------
    info = {}
    for aid in all_ids:
        iL, irec = ident[aid]
        tL = group_winner[(aid, "time")]
        fL = group_winner[(aid, "frequency")]
        trec = gov[(aid, tL)] if tL else None
        frec = gov[(aid, fL)] if fL else None
        info[aid] = dict(iL=iL, irec=irec, tL=tL, trec=trec, fL=fL, frec=frec,
                         zone=irec.zone, parent=irec.parent_id or "")

    # ---- reject tests -----------------------------------------------------
    reject_of = {}

    for aid in tested:
        d = info[aid]
        trec = d["trec"]
        frec = d["frec"]
        code = None
        if trec is None or trec.eff_to_deferred or trec.eff_from is None or trec.eff_to is None:
            code = "TERM_MISSING"
        elif trec.eff_to < trec.eff_from:
            code = "SPAN_INVERTED"
        elif frec is None or frec.freq_bad or frec.f_lo is None or frec.f_hi is None:
            code = "UNIT_AMBIGUOUS"
        elif not iv_intersect(norm_iv([(frec.f_lo, frec.f_hi)]), usable_all):
            code = "BAND_OUTSIDE"
        elif frec.f_lo not in lower_edges or frec.f_hi not in upper_edges:
            code = "RASTER_MISALIGNED"
        elif reg_of[aid] is None:
            code = "HOLDER_UNKNOWN"
        elif (reg_of[aid][1] != d["zone"]
              and holder_status(holder_of[aid], trec.eff_from) == "provisional"):
            code = "ZONE_MISMATCH"
        if code:
            reject_of[aid] = code

    # parent tests
    def parent_of(aid):
        return info[aid]["parent"]

    in_register = set(all_ids)
    for aid in tested:
        if aid in reject_of:
            continue
        p = parent_of(aid)
        if not p:
            continue
        if p not in in_register or info[p]["zone"] != info[aid]["zone"]:
            reject_of[aid] = "PARENT_UNKNOWN"

    for aid in tested:
        if aid in reject_of:
            continue
        if _chain_returns(aid, parent_of, in_register):
            reject_of[aid] = "PARENT_CYCLE"

    # PARENT_RETRACTED resolved in dependency order
    memo = {}

    def bad_parent(aid):
        """True when aid is withdrawn or rejected"""
        if aid in withdrawn:
            return True
        if aid in reject_of:
            return True
        if aid in memo:
            return memo[aid]
        memo[aid] = False  # guard against cycles
        p = parent_of(aid)
        res = False
        if p and p in in_register and bad_parent(p):
            reject_of[aid] = "PARENT_RETRACTED"
            res = True
        memo[aid] = res
        return res

    for aid in tested:
        bad_parent(aid)

    for aid in tested:
        if aid in reject_of:
            rejects[reject_of[aid]] += 1

    passed = [aid for aid in tested if aid not in reject_of]
    passed_set = set(passed)

    # ---- state events ----------------------------------------------------
    EV_PRIO = {"terminate": 0, "suspend": 1, "restore": 2, "activate": 3}
    events = {}
    suspend_events = {}
    for z in ZONES:
        for r in read_csv(C.p("state_events_%s.csv" % z.lower())):
            if parse_utc(r["recorded_at"]) >= AS_OF:
                continue
            ts = parse_utc(r["event_ts"])
            events.setdefault(r["assignment_id"], []).append((ts, EV_PRIO[r["event"]], r["event"]))
            if r["event"] == "suspend":
                suspend_events.setdefault(r["assignment_id"], []).append(ts)
    for k in events:
        events[k].sort()

    anomalies = {}

    def active_intervals(aid, t0, t1):
        out = []
        if t1 <= t0:
            return out
        state = "active"
        cur = t0
        anom = 0
        for ts, prio, ev in events.get(aid, ()):
            if ts >= t1:
                continue
            t = ts if ts > t0 else t0
            if state == "terminated":
                continue
            if state == "active":
                if ev == "suspend":
                    if t > cur:
                        out.append((cur, t))
                    state = "suspended"
                elif ev == "terminate":
                    if t > cur:
                        out.append((cur, t))
                    state = "terminated"
                elif ev == "restore":
                    anom += 1
            else:
                if ev == "restore":
                    state = "active"
                    cur = t
                elif ev == "terminate":
                    state = "terminated"
        if state == "active" and t1 > cur:
            out.append((cur, t1))
        if anom:
            anomalies[aid] = anom
        return norm_iv(out)

    # ---- reservations ------------------------------------------------------
    def iso_weekday(day):
        return (day + 3) % 7 + 1

    guard_rules = {}
    for z in ZONES:
        for r in read_csv(C.p("guard_windows_%s.csv" % z.lower())):
            guard_rules[(z, r["rule_id"])] = r

    occ_raw = {}
    for (z, rid), r in guard_rules.items():
        if r["status"] != "active":
            continue
        d0 = epoch_of_date(r["valid_from"]) // DAY
        d1 = epoch_of_date(r["valid_to"]) // DAY
        rec = r["recurrence"]
        if rec == "daily":
            match = lambda day, dd: True
        elif rec.startswith("weekly:"):
            n = int(rec.split(":")[1])
            match = lambda day, dd, n=n: iso_weekday(day) == n
        elif rec.startswith("monthly:"):
            n = int(rec.split(":")[1])
            match = lambda day, dd, n=n: dd == n
        else:
            continue
        hh, mi = r["local_start"].split(":")
        local_off = int(hh) * 3600 + int(mi) * 60
        dur = int(r["duration_min"]) * 60
        for day in range(d0, d1):
            yy, mm, dd = civil_from_days(day)
            if not match(day, dd):
                continue
            occ_raw[(z, rid, "%04d-%02d-%02d" % (yy, mm, dd))] = (day * DAY + local_off, dur)

    cancelled = 0
    added = 0
    exceptions = read_csv(C.p("guard_exceptions.csv"))
    for e in exceptions:
        if e["kind"] != "cancel":
            continue
        key = (e["zone"], e["rule_id"], e["occurrence_date"])
        if key in occ_raw:
            st, dur = occ_raw[key]
            clk = CLOCK[e["zone"]]
            u = clk.to_utc(st)
            if min(u + dur, H1) > max(u, H0):
                cancelled += 1
            del occ_raw[key]
    for e in exceptions:
        if e["kind"] != "add":
            continue
        z = e["zone"]
        rid = e["rule_id"]
        if (z, rid) not in guard_rules or guard_rules[(z, rid)]["status"] != "active":
            continue
        hh, mi = e["local_start"].split(":")
        day = epoch_of_date(e["occurrence_date"]) // DAY
        st = day * DAY + int(hh) * 3600 + int(mi) * 60
        dur = int(e["duration_min"]) * 60
        occ_raw[(z, rid, e["occurrence_date"])] = (st, dur)
        u = CLOCK[z].to_utc(st)
        if min(u + dur, H1) > max(u, H0):
            added += 1

    guard_occ = dict((z, 0) for z in ZONES)
    guard_rects = dict((z, []) for z in ZONES)
    for (z, rid, dstr), (st, dur) in occ_raw.items():
        u = CLOCK[z].to_utc(st)
        a = max(u, H0)
        b = min(u + dur, H1)
        if b <= a:
            continue
        guard_occ[z] += 1
        r = guard_rules[(z, rid)]
        guard_rects[z].append((int(r["f_lo_khz"]), int(r["f_hi_khz"]), a, b))
    guard_strips = dict((z, rects_to_strips(guard_rects[z])) for z in ZONES)

    # ---- extents ------------------------------------------------------------
    pre_guard = {}
    post_guard = {}
    for aid in passed:
        d = info[aid]
        trec = d["trec"]
        frec = d["frec"]
        runs = iv_intersect(norm_iv([(frec.f_lo, frec.f_hi)]), usable_all)
        t0 = max(trec.eff_from, H0)
        t1 = min(trec.eff_to, H1)
        act = active_intervals(aid, trec.eff_from, trec.eff_to)
        act = iv_intersect(act, [(H0, H1)]) if act else []
        rects = [(a, b, c, e) for (a, b) in runs for (c, e) in act]
        S = rects_to_strips(rects)
        pre_guard[aid] = S
        post_guard[aid] = strip_subtract(S, guard_strips[d["zone"]]) if S else []

    # parent clipping in dependency order
    final_strips = {}

    def final_of(aid):
        if aid in final_strips:
            return final_strips[aid]
        final_strips[aid] = []  # cycle guard, cycles are already rejected
        p = info[aid]["parent"]
        S = post_guard[aid]
        if p and p in passed_set:
            S = strip_intersect(S, final_of(p))
        elif p:
            S = []
        final_strips[aid] = S
        return S

    for aid in passed:
        final_of(aid)

    final_rects = {}
    own_measure = {}
    for aid in passed:
        rl = reduce_rects(strips_to_rects(final_strips[aid]))
        final_rects[aid] = rl
        own_measure[aid] = rect_measure(rl)

    measurable = [aid for aid in passed if own_measure[aid] > 0]
    measurable_set = set(measurable)

    # parent chain depth over measurable grants
    def depth_of(aid):
        n = 1
        seen = set([aid])
        cur = aid
        while True:
            p = info[cur]["parent"]
            if not p or p not in in_register or p in seen:
                return n
            seen.add(p)
            n += 1
            cur = p

    parent_chain_max_depth = max([depth_of(a) for a in measurable] or [0])

    # ---- notes ---------------------------------------------------------------
    zero_span = 0
    for aid in passed:
        d = info[aid]
        trec = d["trec"]
        frec = d["frec"]
        if alias_depth_of[aid] >= 1:
            notes["ALIAS_RESOLVED"] += 1
        runs = iv_intersect(norm_iv([(frec.f_lo, frec.f_hi)]), usable_all)
        if iv_measure(runs) < frec.f_hi - frec.f_lo:
            notes["CLIPPED_TO_BAND"] += 1
        if len(runs) > 1:
            notes["SPLIT_BY_RASTER"] += 1
        if trec.eff_from < H0 or trec.eff_to > H1:
            notes["CLIPPED_TO_HORIZON"] += 1
        if trec.eff_to_open:
            notes["OPEN_ENDED"] += 1
        if frec.width_mismatch:
            notes["WIDTH_MISMATCH"] += 1
        if reg_of[aid][1] != d["zone"]:
            notes["ZONE_OF_RECORD_DIFFERS"] += 1
        if aid in anomalies:
            notes["STATE_ANOMALY"] += anomalies[aid]
        if trec.eff_from == trec.eff_to:
            notes["ZERO_SPAN"] += 1
            zero_span += 1

    # ---- months --------------------------------------------------------------
    def zone_months(z):
        clk = CLOCK[z]
        lt = clk.to_local(H0)
        y, m, _ = civil_from_days(lt // DAY)
        out = []
        while True:
            t0 = clk.to_utc(days_from_civil(y, m, 1) * DAY)
            ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
            t1 = clk.to_utc(days_from_civil(ny, nm, 1) * DAY)
            if t1 > H0 and t0 < H1:
                out.append(("%04d-%02d" % (y, m), max(t0, H0), min(t1, H1)))
            if t0 >= H1:
                break
            y, m = ny, nm
        return out

    months = dict((z, zone_months(z)) for z in ZONES)
    month_full = {}
    for z in ZONES:
        clk = CLOCK[z]
        for key, a, b in months[z]:
            y, m = int(key[:4]), int(key[5:7])
            ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
            month_full[(z, key)] = (clk.to_utc(days_from_civil(y, m, 1) * DAY),
                                    clk.to_utc(days_from_civil(ny, nm, 1) * DAY))
    all_month_bounds = set([H0, H1])
    for z in ZONES:
        for key, a, b in months[z]:
            all_month_bounds.add(a)
            all_month_bounds.add(b)
    all_month_bounds = sorted(all_month_bounds)

    # ---- holder zone for the duty audit --------------------------------------
    def holder_zone(cid):
        rows = registry.get(cid)
        if not rows:
            return None
        best = None
        for row in rows:
            key = (-row[0], row[1])
            if best is None or key < best:
                best = key
        return best[1]

    # ---- per zone arrangement -------------------------------------------------
    band_of_freq = []
    for bid, lo, hi, _r in bands:
        band_of_freq.append((lo, hi, bid))

    def band_at(f):
        for lo, hi, bid in band_of_freq:
            if lo <= f < hi:
                return bid
        return None

    zone_stats = {}
    charge_by_grant = dict((a, 0) for a in measurable)
    holder_union = {}
    holder_month_union = {}
    seg_holder_union = {}
    seg_union = {"commercial": 0, "public": 0}
    seg_excl = {"commercial": 0, "public": 0}
    seg_shared = {"commercial": 0, "public": 0}
    seg_zone_union = {"commercial": dict((z, 0) for z in ZONES),
                      "public": dict((z, 0) for z in ZONES)}
    cross_segment = 0
    total_union = 0
    total_excl = 0
    total_shared = 0

    for z in ZONES:
        zrects = []
        for aid in measurable:
            if info[aid]["zone"] != z:
                continue
            for (f0, f1, t0, t1) in final_rects[aid]:
                zrects.append((f0, f1, t0, t1, aid))
        mkeys = [m[0] for m in months[z]]
        union = excl = shared = 0
        band_u = dict((b, 0) for b in band_ids)
        month_u = dict((k, 0) for k in mkeys)
        zmonth_starts = [m[1] for m in months[z]]
        for (f0, f1, t0, t1, keys) in arrange(zrects, all_month_bounds):
            w = f1 - f0
            cell = w * (t1 - t0)
            n = len(keys)
            union += cell
            if n == 1:
                excl += cell
            if n >= SHARED_MIN:
                shared += cell
            bid = band_at(f0)
            if bid is not None:
                band_u[bid] += cell
            mi = bisect_right(zmonth_starts, t0) - 1
            if 0 <= mi < len(mkeys):
                month_u[mkeys[mi]] += cell
            if n >= 2:
                best = min(keys, key=lambda a: (-own_measure[a], a))
                for a in keys:
                    if a != best:
                        charge_by_grant[a] += cell
            segs = set(seg_of[a] for a in keys)
            for s in segs:
                if s in seg_union:
                    seg_union[s] += cell
                    seg_zone_union[s][z] += cell
            if len(segs) >= 2:
                cross_segment += cell
            for s in ("commercial", "public"):
                c = sum(1 for a in keys if seg_of[a] == s)
                if c == 1:
                    seg_excl[s] += cell
                elif c >= SHARED_MIN:
                    seg_shared[s] += cell
            for sh in set((seg_of[a], holder_of[a]) for a in keys):
                seg_holder_union[sh] = seg_holder_union.get(sh, 0) + cell
            hs = set(holder_of[a] for a in keys)
            for h in hs:
                holder_union[h] = holder_union.get(h, 0) + cell
                hz = holder_zone(h)
                if hz is not None:
                    hmb = [m[1] for m in months[hz]]
                    hmk = [m[0] for m in months[hz]]
                    j = bisect_right(hmb, t0) - 1
                    if 0 <= j < len(hmk):
                        holder_month_union.setdefault(h, {})
                        k2 = hmk[j]
                        holder_month_union[h][k2] = holder_month_union[h].get(k2, 0) + cell
        zone_grants = [a for a in measurable if info[a]["zone"] == z]
        pre_u = strip_measure(union_strips([pre_guard[a] for a in passed
                                           if info[a]["zone"] == z]))
        post_u = strip_measure(union_strips([post_guard[a] for a in passed
                                            if info[a]["zone"] == z]))
        zone_stats[z] = dict(
            union=union, excl=excl, shared=shared,
            band_u=band_u, month_u=month_u, mkeys=mkeys,
            grants=zone_grants,
            rect_count=sum(len(final_rects[a]) for a in zone_grants),
            total_assigned=sum(own_measure[a] for a in zone_grants),
            guard_sub=pre_u - post_u,
        )
        total_union += union
        total_excl += excl
        total_shared += shared

    # ---- duty audit -----------------------------------------------------------
    holder_suspends = {}
    for aid, stamps in suspend_events.items():
        h = holder_of.get(aid)
        if h is None:
            continue
        holder_suspends.setdefault(h, []).extend(stamps)
    for h in holder_suspends:
        holder_suspends[h].sort()

    duty_rows = {}
    for segment in ("commercial", "public"):
        for r in read_csv(C.p("duty_budget_%s.csv" % segment)):
            duty_rows.setdefault(segment, {}).setdefault(r["canonical_id"], {})[r["month"]] = r

    duty_total = dict(holders_audited=0, months_in_deficit=0, total_allowance=0,
                      total_consumed=0, carry_forward_end=0, carry_resets=0)
    top_deficit_rows = []
    seg_duty = {}
    for segment in ("commercial", "public"):
        s_deficit_months = 0
        s_carry_end = 0
        for cid in sorted(duty_rows.get(segment, {})):
            hz = holder_zone(cid)
            if hz is None:
                continue
            duty_total["holders_audited"] += 1
            carry = 0
            last_carry = 0
            for key, _a, _b in months[hz]:
                row = duty_rows[segment][cid].get(key)
                allowance = 0
                if row is not None:
                    v = int(row["allowance_khz_s"])
                    if row["notes"].strip() == "unit=khz_min":
                        v *= 60
                    allowance = v
                occupancy = holder_month_union.get(cid, {}).get(key, 0)
                available = allowance + carry
                consumed = available if available < occupancy else occupancy
                deficit = occupancy - available
                if deficit < 0:
                    deficit = 0
                carry_out = available - occupancy
                if carry_out < 0:
                    carry_out = 0
                mf0, mf1 = month_full[(hz, key)]
                susp = False
                for t in holder_suspends.get(cid, ()):
                    if mf0 <= t < mf1:
                        susp = True
                        break
                if susp:
                    if available > occupancy:
                        duty_total["carry_resets"] += 1
                    carry_out = 0
                duty_total["total_allowance"] += allowance
                duty_total["total_consumed"] += consumed
                if deficit > 0:
                    duty_total["months_in_deficit"] += 1
                    s_deficit_months += 1
                    top_deficit_rows.append((deficit, cid, key))
                carry = carry_out
                last_carry = carry_out
            duty_total["carry_forward_end"] += last_carry
            s_carry_end += last_carry
        seg_duty[segment] = dict(deficit_months=s_deficit_months, carry_end=s_carry_end)
    top_deficit_rows.sort(key=lambda r: (-r[0], r[1], r[2]))
    top_deficit = [[r[1], r[2], r[0]] for r in top_deficit_rows[:R["TOP_DEFICIT"]]]

    # ---- assembled documents ---------------------------------------------------
    area_total_assigned = sum(own_measure[a] for a in measurable)
    area_union = total_union
    area_excess = area_total_assigned - area_union
    excess_charge_total = sum(charge_by_grant.values())
    shared_ratio_ppm = round_half_even(total_shared * R["PPM"], area_union) if area_union else 0
    zone_union = dict((z, zone_stats[z]["union"]) for z in ZONES)
    zone_share_bp = largest_remainder(zone_union, R["SHARE_BP"])
    segment_share_bp = largest_remainder(dict(seg_union), R["SHARE_BP"])
    guard_sub_total = sum(zone_stats[z]["guard_sub"] for z in ZONES)

    summary = {
        "horizon": {"start": fmt_utc(H0), "end": fmt_utc(H1), "as_of": fmt_utc(AS_OF)},
        "assignments_total": len(all_ids),
        "assignments_measurable": len(measurable),
        "rectangles": sum(len(final_rects[a]) for a in measurable),
        "area_total_assigned": area_total_assigned,
        "area_union": area_union,
        "area_exclusive": total_excl,
        "area_shared": total_shared,
        "area_excess": area_excess,
        "excess_charge_total": excess_charge_total,
        "shared_ratio_ppm": shared_ratio_ppm,
        "zone_area_union": zone_union,
        "zone_share_bp": zone_share_bp,
        "segment_area_union": dict(seg_union),
        "segment_share_bp": segment_share_bp,
        "cross_segment_shared_area": cross_segment,
        "guard_subtracted_area": guard_sub_total,
    }

    regions = {}
    for z in ZONES:
        st = zone_stats[z]
        clk = CLOCK[z]
        win = None
        if clk.win:
            win = [fmt_utc(clk.win[0]), fmt_utc(clk.win[1])]
        charged = [(charge_by_grant[a], a) for a in st["grants"] if charge_by_grant[a] > 0]
        charged.sort(key=lambda x: (-x[0], x[1]))
        regions[z] = {
            "zone": z,
            "utc_offset_standard_sec": clk.std,
            "utc_offset_summer_sec": clk.summer,
            "summer_window_utc": win,
            "assignments_measurable": len(st["grants"]),
            "rectangles": st["rect_count"],
            "area_total_assigned": st["total_assigned"],
            "area_union": st["union"],
            "area_exclusive": st["excl"],
            "area_shared": st["shared"],
            "area_excess": st["total_assigned"] - st["union"],
            "guard_occurrences": guard_occ[z],
            "guard_subtracted_area": st["guard_sub"],
            "excess_charge_top": [[a, c] for c, a in charged[:R["TOP_EXCESS"]]],
            "band_area_union": st["band_u"],
            "month_area_union": st["month_u"],
        }

    segments = {}
    for s in ("commercial", "public"):
        grants = [a for a in measurable if seg_of[a] == s]
        hold = sorted(set(holder_of[a] for a in grants))
        tops = sorted(((seg_holder_union.get((s, h), 0), h) for h in hold),
                      key=lambda x: (-x[0], x[1]))
        segments[s] = {
            "segment": s,
            "holders": len(hold),
            "assignments_measurable": len(grants),
            "area_union": seg_union[s],
            "area_exclusive": seg_excl[s],
            "area_shared": seg_shared[s],
            "zone_area_union": seg_zone_union[s],
            "top_holders": [[h, m] for m, h in tops[:R["TOP_HOLDERS"]]],
            "duty_deficit_months": seg_duty[s]["deficit_months"],
            "duty_carry_end": seg_duty[s]["carry_end"],
        }

    seen_refs = set()
    for rec in R["records"]:
        if rec.has_identity and rec.holder_ref is not None:
            seen_refs.add(canon(rec.holder_ref))
    alias_fixpoint_depth = max([resolve_alias(x)[1] for x in seen_refs] or [0])

    policy_audit = {
        "as_of": fmt_utc(AS_OF),
        "precedence_exception": exception,
        "duplicate_tiebreak": R["duplicate_tiebreak"],
        "clock_keying": R["clock_keying"],
        "layer_governing_counts": layer_counts,
        "alias_fixpoint_depth": alias_fixpoint_depth,
        "alias_cycles": R["alias_cycles"],
        "parent_chain_max_depth": parent_chain_max_depth,
        "parent_rejects": dict((k, rejects[k]) for k in
                              ("PARENT_UNKNOWN", "PARENT_CYCLE", "PARENT_RETRACTED")),
        "duty": {
            "holders_audited": duty_total["holders_audited"],
            "months_in_deficit": duty_total["months_in_deficit"],
            "total_allowance": duty_total["total_allowance"],
            "total_consumed": duty_total["total_consumed"],
            "carry_forward_end": duty_total["carry_forward_end"],
            "carry_resets": duty_total["carry_resets"],
            "top_deficit": top_deficit,
        },
        "guard": {
            "occurrences": sum(guard_occ[z] for z in ZONES),
            "cancelled": cancelled,
            "added": added,
            "subtracted_area": guard_sub_total,
        },
    }

    manifest = {}
    for r in md_table(C.p("source_manifest.md")):
        if "file" in r:
            manifest[r["file"]] = int(r["rows_declared"])
    rows_read = R["rows_read"]
    rows_visible = R["rows_visible"]
    rows_governing = R["rows_governing"]
    mismatches = sorted(f for f in R["record_files"]
                        if manifest.get(f) != rows_read[f])
    data_quality = {
        "assignments_total": len(all_ids),
        "rows_read_total": sum(rows_read.values()),
        "rejects": rejects,
        "notes": notes,
        "retracted": len(withdrawn),
        "zero_span": zero_span,
        "manifest_mismatches": mismatches,
        "source_counts": dict((f, {"rows_read": rows_read[f],
                                   "rows_visible": rows_visible[f],
                                   "rows_governing": rows_governing[f]})
                              for f in R["record_files"]),
    }

    docs = {
        "summary.json": summary,
        "policy_audit.json": policy_audit,
        "data_quality.json": data_quality,
    }
    for z in ZONES:
        docs["region_%s.json" % z] = regions[z]
    for s in ("commercial", "public"):
        docs["segment_%s.json" % s] = segments[s]

    if not write:
        return R, locals()
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    for name in sorted(docs):
        check_no_float(docs[name], name)
        with open(os.path.join(out_dir, name), "w") as fh:
            json.dump(docs[name], fh, sort_keys=True, indent=2)
            fh.write("\n")

    return R, locals()


def check_no_float(obj, where):
    if isinstance(obj, float):
        raise ValueError("floating point value in %s" % where)
    if isinstance(obj, dict):
        for k, v in obj.items():
            check_no_float(v, where)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            check_no_float(v, where)


def union_strips(list_of_strips):
    rects = []
    for S in list_of_strips:
        for f0, f1, ivs in S:
            for a, b in ivs:
                rects.append((f0, f1, a, b))
    return rects_to_strips(rects)


def _chain_returns(aid, parent_of, in_register):
    seen = set()
    cur = aid
    while True:
        p = parent_of(cur)
        if not p or p not in in_register:
            return False
        if p == aid:
            return True
        if p in seen:
            return False
        seen.add(p)
        cur = p


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py <corpus_dir> <output_dir>\n")
        return 2
    derive(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
