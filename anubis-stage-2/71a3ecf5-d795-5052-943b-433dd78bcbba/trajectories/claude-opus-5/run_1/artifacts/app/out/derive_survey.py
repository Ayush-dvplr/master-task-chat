#!/usr/bin/env python3
"""HAS-7 Household Activity Statistics derivation.

Usage: python3 derive_survey.py DATA_DIR OUT_DIR
"""
import csv
import glob
import json
import math
import os
import re
import sys
import tomllib
import unicodedata
from datetime import datetime, timezone
from fractions import Fraction

# ---------------------------------------------------------------- utilities


def nfc(s):
    return unicodedata.normalize("NFC", s)


UNIT_RE = re.compile(r"^RH-([A-Z]{2})-(\d+)$")


def canon_unit(raw):
    if raw is None:
        return None
    s = nfc(str(raw)).strip().replace("_", "-").replace(".", "-").upper()
    m = UNIT_RE.match(s)
    if not m:
        return None
    return "RH-%s-%06d" % (m.group(1), int(m.group(2)))


def truthy(v):
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    return nfc(str(v)).strip().lower() in ("y", "yes", "true")


def in_scope(rec, field_names=("active", "Active", "ACTIVE")):
    for f in field_names:
        if isinstance(rec, dict) and f in rec:
            return truthy(rec[f])
    return True


def rdiv(n, d):
    """Integer division rounding to nearest, halves away from zero."""
    if d < 0:
        n, d = -n, -d
    if n >= 0:
        return (2 * n + d) // (2 * d)
    return -((-2 * n + d) // (2 * d))


def rnd_frac(fr):
    if isinstance(fr, int):
        return fr
    return rdiv(fr.numerator, fr.denominator)


def isqrt_round(v):
    if v <= 0:
        return 0
    s = math.isqrt(v)
    if 4 * v >= (2 * s + 1) ** 2:
        s += 1
    return s


def median_low(values):
    vs = sorted(values)
    n = len(vs)
    if n == 0:
        return 0
    if n % 2:
        return vs[n // 2]
    return vs[n // 2 - 1]


# ---------------------------------------------------------------- parsers


def read_text(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def read_delim(path, delim):
    with open(path, encoding="utf-8", newline="") as f:
        return [dict(r) for r in csv.DictReader(f, delimiter=delim)]


DELIMS = {".csv": ",", ".tsv": "\t", ".psv": "|"}


def read_table(path):
    ext = os.path.splitext(path)[1]
    if ext in DELIMS:
        return read_delim(path, DELIMS[ext])
    if ext == ".jsonl":
        return [json.loads(l) for l in read_text(path).splitlines() if l.strip()]
    if ext == ".fwf":
        return read_fwf(path)
    raise ValueError("unsupported table %s" % path)


def read_fwf(path):
    lines = read_text(path).split("\n")
    header = lines[0]
    cols = [(m.group(0), m.start()) for m in re.finditer(r"\S+", header)]
    out = []
    for line in lines[1:]:
        if not line.strip():
            continue
        rec = {}
        for i, (name, start) in enumerate(cols):
            end = cols[i + 1][1] if i + 1 < len(cols) else len(line)
            rec[name] = line[start:end].strip()
        out.append(rec)
    return out


def read_props(path):
    """key = value lines (.properties / .conf), '#' and ';' comments."""
    out = {}
    for line in read_text(path).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        k, sep, v = line.partition("=")
        if not sep:
            continue
        out[k.strip()] = v.strip()
    return out


def read_toml(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def read_ini(path):
    """Minimal ini reader: returns {section: {key: value}}."""
    out = {}
    cur = None
    for line in read_text(path).splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1].strip()
            out.setdefault(cur, {})
            continue
        k, sep, v = line.partition("=")
        if sep and cur is not None:
            out[cur][k.strip()] = v.strip()
    return out


def read_sexp(path):
    """(node (key value) ...) per line -> list of (node, {key: value})."""
    out = []
    for line in read_text(path).splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        m = re.match(r"^\((\S+)\s+(.*)\)\s*$", line)
        if not m:
            continue
        node, body = m.group(1), m.group(2)
        fields = {}
        for fm in re.finditer(r"\(([^()\s]+)\s+([^()]*)\)", body):
            fields[fm.group(1)] = fm.group(2).strip()
        out.append((node, fields))
    return out


def read_rfc822(path):
    blocks = []
    for block in re.split(r"\n\s*\n", read_text(path)):
        if not block.strip():
            continue
        rec = {}
        for line in block.strip().split("\n"):
            k, sep, v = line.partition(":")
            if sep:
                rec[k.strip()] = v.strip()
        blocks.append(rec)
    return blocks


def read_logfmt(path):
    out = []
    for line in read_text(path).splitlines():
        if not line.strip():
            continue
        rec = {}
        for tok in line.split():
            k, sep, v = tok.partition("=")
            if sep:
                rec[k] = v
        out.append(rec)
    return out


def read_rfc5424(path):
    out = []
    for line in read_text(path).splitlines():
        if not line.strip():
            continue
        m = re.match(r"^<\d+>\d+\s+(\S+)\s+.*?\[\S+\s+(.*)\]\s*$", line)
        if not m:
            continue
        rec = {"timestamp": m.group(1)}
        for fm in re.finditer(r'([A-Za-z0-9_\-]+)="([^"]*)"', m.group(2)):
            rec[fm.group(1)] = fm.group(2)
        out.append(rec)
    return out


def parse_instant(raw):
    """Canonical UTC instant with the fractional part truncated."""
    if raw is None:
        return None
    s = nfc(str(raw)).strip()
    if not s:
        return None
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt


def fmt_instant(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def inst_key(dt):
    return (0, "") if dt is None else (1, fmt_instant(dt))


def pick(rec, *names):
    for n in names:
        if n in rec and rec[n] not in (None, ""):
            return rec[n]
    for n in names:
        if n in rec:
            return rec[n]
    return None


def to_int(v, default=None):
    if v is None:
        return default
    s = nfc(str(v)).strip()
    if s == "":
        return default
    try:
        return int(s)
    except ValueError:
        try:
            return int(Fraction(s))
        except (ValueError, ZeroDivisionError):
            return default


# ---------------------------------------------------------------- registers


class Corpus(object):
    def __init__(self, data_dir):
        self.dir = data_dir
        self.path = lambda name: os.path.join(data_dir, name)

    def files(self, pattern):
        return sorted(glob.glob(os.path.join(self.dir, pattern)))


def load_reference(c):
    ref = {}
    # regions
    regions = {}
    for r in read_table(c.path("ref__region-codes.csv")):
        if not in_scope(r):
            continue
        code = nfc(r["region_code"]).strip().upper()
        regions[code] = {
            "name": nfc(r["region_name"]).strip(),
            "rank": to_int(r.get("rank_order"), 0),
        }
    ref["regions"] = regions
    # strata
    strata = {}
    for r in read_table(c.path("ref__stratum-params.tsv")):
        if not in_scope(r):
            continue
        code = nfc(r["stratum_code"]).strip()
        strata[code] = {
            "region": nfc(r["region_code"]).strip().upper(),
            "group": nfc(r["stratum_group"]).strip(),
            "population": to_int(r["population_units"], 0),
            "collapse_partner": nfc(r["collapse_partner"]).strip(),
        }
    ref["strata"] = strata
    names = {}
    for code, s in strata.items():
        rname = regions.get(s["region"], {}).get("name")
        if rname:
            names[nfc(rname + " " + s["group"])] = code
    ref["stratum_names"] = names
    # tenure classes
    tenures = {}
    tj = json.loads(read_text(c.path("ref__tenure-classes.json")))
    for key, val in tj.get("classes", {}).items():
        if isinstance(val, dict) and not in_scope(val):
            continue
        tenures[nfc(key).strip()] = {
            "class": nfc(str(val.get("tenure_class", key))).strip(),
            "rank": to_int(val.get("sort_rank"), 0),
        }
    ref["tenures"] = tenures
    # bands
    bands = {}
    for k, v in read_props(c.path("ref__band-definitions.properties")).items():
        parts = k.split(".")
        if len(parts) != 3 or parts[0] != "band":
            continue
        bands.setdefault(parts[1], {})[parts[2]] = v
    blist = []
    for code, f in bands.items():
        if "lower_hours_inclusive" not in f or "upper_hours_inclusive" not in f:
            continue
        if "active" in f and not truthy(f["active"]):
            continue
        blist.append(
            (
                to_int(f["sort_rank"], 0),
                code,
                to_int(f["lower_hours_inclusive"], 0),
                to_int(f["upper_hours_inclusive"], 0),
            )
        )
    blist.sort()
    ref["bands"] = blist
    # contact bands
    cbands = []
    for node, f in read_sexp(c.path("ref__contact-bands.sexp")):
        if node != "contact-band":
            continue
        if not truthy(f.get("active", "yes")):
            continue
        cbands.append(
            (
                to_int(f.get("sort-rank"), 0),
                nfc(f["code"]).strip(),
                to_int(f["min-attempts"], 0),
                to_int(f["max-attempts"], 0),
            )
        )
    cbands.sort()
    ref["contact_bands"] = cbands
    # dispositions
    disp = {}
    for r in read_table(c.path("rules__disposition-precedence.csv")):
        if not in_scope(r):
            continue
        disp[nfc(r["disposition_code"]).strip()] = {
            "severity": to_int(r["severity_rank"], 0),
            "eligible": truthy(r["eligible"]),
            "responding": truthy(r["responding"]),
            "superseded": truthy(r["superseded"]),
        }
    ref["dispositions"] = disp
    # unit conversions
    conv = {}
    for r in read_table(c.path("bench__unit-conversions.csv")):
        if not in_scope(r):
            continue
        conv[nfc(r["unit_name"]).strip()] = Fraction(nfc(r["persons_per_unit"]).strip())
    ref["conversions"] = conv
    # subsample register
    sub = read_props(c.path("frame__subsample.conf"))
    ref["subsample_factor_bp"] = to_int(sub.get("subsample_factor_bp"), 10000)
    subs = {}
    for k, v in sub.items():
        m = re.match(r"^unit\.(.*)\.subsampled$", k)
        if m:
            uid = canon_unit(m.group(1))
            if uid:
                subs[uid] = truthy(v)
    ref["subsampled"] = subs
    # rules
    adj = read_toml(c.path("rules__adjustment-cells.toml"))
    ref["min_response_rate_bp"] = to_int(adj.get("min_response_rate_bp"), 0)
    ref["min_cell_count"] = to_int(adj.get("min_cell_count"), 0)
    ref["max_collapse_rounds"] = to_int(adj.get("max_collapse_rounds"), 0)
    ref["reference_wave"] = to_int(adj.get("reference_wave"), 3)
    prior = adj.get("prior_waves") or [1, 2]
    ref["prior_waves"] = [to_int(w, 0) for w in prior]
    trim = read_props(c.path("rules__trimming.conf"))
    ref["trim_ratio_bp"] = to_int(trim.get("trim_ratio_bp"), 0)
    ref["trim_trigger_deff_bp"] = to_int(trim.get("trim_trigger_deff_bp"), 0)
    ini = read_ini(c.path("rules__margin-order.ini"))
    ref["tolerance_uw"] = to_int(ini.get("raking", {}).get("tolerance_uw"), 0)
    ref["max_iterations"] = to_int(ini.get("raking", {}).get("max_iterations"), 0)
    listed = []
    for sec, body in ini.items():
        if not sec.startswith("margin."):
            continue
        if not truthy(body.get("active", "yes")):
            continue
        listed.append(nfc(body["control_dimension"]).strip())
    ref["listed_margins"] = listed
    disc = read_toml(c.path("disclosure__parameters.toml"))
    ref["min_publish_count"] = to_int(disc.get("min_publish_count"), 0)
    ref["max_publish_cv_bp"] = to_int(disc.get("max_publish_cv_bp"), 0)
    ref["dominance_bp"] = to_int(disc.get("dominance_bp"), 0)
    ref["max_cascade_rounds"] = to_int(disc.get("max_cascade_rounds"), 0)
    # reference period
    period = None
    std = c.path("HAS-7-standard.md")
    if os.path.exists(std):
        m = re.search(r"survey reference period is `([^`]+)`", read_text(std))
        if m:
            period = m.group(1)
    ref["reference_period"] = period or "2026-H1"
    # cell registry
    reg = {}
    for r in read_table(c.path("disclosure__cell-registry.csv")):
        if not in_scope(r):
            continue
        t = nfc(r["table_name"]).strip()
        axis = nfc(r["axis"]).strip()
        reg.setdefault(t, {"row": [], "column": []})[axis].append(
            (to_int(r["sort_rank"], 0), nfc(r["level_key"]).strip())
        )
    registry = {}
    for t, ax in reg.items():
        registry[t] = {
            "row": [k for _, k in sorted(ax["row"])],
            "column": [k for _, k in sorted(ax["column"])],
        }
    ref["registry"] = registry
    return ref


def band_of_hours(bands, hours):
    for _, code, lo, hi in bands:
        if lo <= hours <= hi:
            return code
    return None


def contact_band_of(cbands, attempts):
    for _, code, lo, hi in cbands:
        if lo <= attempts <= hi:
            return code
    return None


# ---------------------------------------------------------------- frame


FRAME_FIELD_ALIASES = {
    "region_code": ("region_code", "reg", "region"),
    "serial": ("serial",),
    "stratum": ("stratum", "strat"),
    "psu_code": ("psu_code", "psu"),
    "vintage_rank": ("vintage_rank", "vr"),
    "edit_timestamp": ("edit_timestamp",),
    "tenure": ("tenure",),
    "record_id": ("record_id",),
}


def frame_field(rec, name):
    for alias in FRAME_FIELD_ALIASES[name]:
        if alias in rec:
            return rec[alias]
    return None


def resolve_frame(c, ref):
    repairs = {"M%d" % i: 0 for i in range(1, 9)}
    strata = ref["strata"]
    names = ref["stratum_names"]
    candidates = {}
    discarded = []
    register_files = []
    for letter in ("a", "b", "c"):
        register_files.extend(c.files("frame__register-%s.*" % letter))
    for path in sorted(register_files):
        for rec in read_table(path):
            if not in_scope(rec):
                continue
            raw_serial = frame_field(rec, "serial")
            raw_region = frame_field(rec, "region_code")
            raw_stratum = frame_field(rec, "stratum")
            if raw_serial is None or raw_region is None:
                continue
            serial = nfc(str(raw_serial))
            region = nfc(str(raw_region)).strip()
            stratum_raw = nfc(str(raw_stratum or "")).strip()
            # stratum scope decides whether the record is in the frame at all
            m7 = False
            if stratum_raw in strata:
                stratum = stratum_raw
            elif stratum_raw in names:
                stratum = names[stratum_raw]
                m7 = True
            else:
                continue
            m1 = serial != serial.strip()
            serial = serial.strip()
            m2 = len(serial) < 6
            serial = serial.rjust(6, "0")
            m3 = region != region.upper()
            region = region.upper()
            if m1:
                repairs["M1"] += 1
            if m2:
                repairs["M2"] += 1
            if m3:
                repairs["M3"] += 1
            if m7:
                repairs["M7"] += 1
            ts = parse_instant(frame_field(rec, "edit_timestamp"))
            rid = nfc(str(frame_field(rec, "record_id") or "")).strip()
            entry = {
                "unit_id": "RH-%s-%s" % (region, serial),
                "region": region,
                "serial": serial,
                "stratum": stratum,
                "psu_code": nfc(str(frame_field(rec, "psu_code") or "")).strip(),
                "tenure": nfc(str(frame_field(rec, "tenure") or "")).strip(),
                "vintage_rank": to_int(frame_field(rec, "vintage_rank"), 0),
                "edit_ts": fmt_instant(ts) if ts else "",
                "record_id": rid,
            }
            candidates.setdefault((region, serial), []).append(entry)
    units = {}
    for key in sorted(candidates):
        recs = candidates[key]
        ordered = sorted(
            recs,
            key=lambda e: (e["vintage_rank"], e["edit_ts"], e["record_id"]),
            reverse=True,
        )
        survivor = ordered[0]
        for loser in ordered[1:]:
            discarded.append(loser["record_id"])
            repairs["M8"] += 1
        units[survivor["unit_id"]] = survivor
    # reissue copy lends psu_code only
    reissue = {}
    for path in c.files("frame__register-d.*"):
        for rec in read_table(path):
            if not in_scope(rec):
                continue
            uid = canon_unit(pick(rec, "unit_id", "unit"))
            if uid is None:
                continue
            psu = nfc(str(rec.get("psu_code") or "")).strip()
            if not psu:
                continue
            ts = parse_instant(rec.get("edit_timestamp"))
            cand = (
                to_int(rec.get("vintage_rank"), 0),
                fmt_instant(ts) if ts else "",
                nfc(str(rec.get("record_id") or "")).strip(),
                psu,
            )
            if uid not in reissue or cand > reissue[uid]:
                reissue[uid] = cand
    for uid, u in units.items():
        if not u["psu_code"] and uid in reissue:
            u["psu_code"] = reissue[uid][3]
    # address register
    addr = {}
    for path in c.files("frame__addresses.*"):
        blocks = read_rfc822(path)
        blocks.sort(key=lambda r: sorted(r.items()))
        for rec in blocks:
            if not in_scope(rec, ("Active", "active")):
                continue
            uid = canon_unit(rec.get("Unit-Id"))
            if uid is None:
                continue
            addr.setdefault(uid, rec)
    self_ref = []
    dangling = []
    for uid in sorted(units):
        u = units[uid]
        rec = addr.get(uid)
        du = None
        parent = None
        if rec is not None:
            du = to_int(rec.get("Dwelling-Units"), None)
            parent = canon_unit(rec.get("Parent-Unit"))
        if du is None:
            repairs["M4"] += 1
            du = 1
        u["dwelling_units"] = du
        if parent is not None:
            if parent == uid:
                repairs["M5"] += 1
                self_ref.append(uid)
                parent = None
            elif parent not in units:
                repairs["M6"] += 1
                dangling.append(uid)
                parent = None
        u["parent_unit"] = parent
    return {
        "units": units,
        "repairs": repairs,
        "discarded": sorted(discarded),
        "self_ref": sorted(self_ref),
        "dangling": sorted(dangling),
    }


# ---------------------------------------------------------------- contacts


CONTACT_READERS = {
    ".rfc5424": read_rfc5424,
    ".logfmt": read_logfmt,
    ".csv": lambda p: read_table(p),
    ".jsonl": lambda p: read_table(p),
    ".tsv": lambda p: read_table(p),
    ".psv": lambda p: read_table(p),
}


def load_contacts(c, ref):
    attempts = []  # (unit, wave, attempt_no, instant, outcome)
    corrections = []  # (unit, wave, attempt_no, instant, kind)
    for path in c.files("contact__*"):
        ext = os.path.splitext(path)[1]
        reader = CONTACT_READERS.get(ext)
        if reader is None:
            continue
        for rec in reader(path):
            if not in_scope(rec):
                continue
            uid = canon_unit(pick(rec, "unit_id", "unit"))
            if uid is None:
                continue
            wave = to_int(pick(rec, "wave"), None)
            attempt = to_int(pick(rec, "attempt_no", "attempt"), None)
            inst = parse_instant(pick(rec, "contact_datetime", "ts", "timestamp"))
            corr = pick(rec, "correction")
            if corr not in (None, ""):
                corrections.append(
                    (uid, wave, attempt, inst, nfc(str(corr)).strip().lower())
                )
                continue
            outcome = pick(rec, "outcome_code", "outcome")
            if outcome in (None, ""):
                continue
            attempts.append((uid, wave, attempt, inst, nfc(str(outcome)).strip()))
    # net correction state per (unit, wave, attempt)
    void = {}
    bykey = {}
    for uid, wave, attempt, inst, kind in corrections:
        bykey.setdefault((uid, wave, attempt), []).append((inst, kind))
    for key, lst in bykey.items():
        # latest instant wins; a tie goes to the reinstatement
        best = max(lst, key=lambda x: (inst_key(x[0]), 1 if x[1] == "reinstate" else 0))
        void[key] = best[1] == "void"
    disp = ref["dispositions"]
    attempt_counts = {}
    resolved = {}
    pool = {}
    for uid, wave, attempt, inst, outcome in attempts:
        attempt_counts[(uid, wave)] = attempt_counts.get((uid, wave), 0) + 1
        if void.get((uid, wave, attempt)):
            continue
        if outcome not in disp:
            continue
        pool.setdefault((uid, wave), []).append((attempt, inst, outcome))
    for key, lst in pool.items():
        best = max(
            lst,
            key=lambda x: (
                disp[x[2]]["severity"],
                inst_key(x[1]),
                x[0] if x[0] is not None else 0,
                x[2],
            ),
        )
        resolved[key] = {
            "disposition": best[2],
            "attempt_no": best[0],
            "resolved_utc": fmt_instant(best[1]) if best[1] else "",
        }
    return {"resolved": resolved, "attempt_counts": attempt_counts}


# ---------------------------------------------------------------- interviews


def load_interviews(c):
    found = {}
    for path in sorted(c.files("interview__*")):
        for rec in read_table(path):
            if not in_scope(rec):
                continue
            uid = canon_unit(pick(rec, "unit_id", "unit"))
            if uid is None:
                continue
            wave = to_int(pick(rec, "wave"), None)
            entry = {
                "activity": nfc(str(rec.get("activity_code") or "")).strip(),
                "sector": nfc(str(rec.get("sector_code") or "")).strip(),
                "hours": to_int(pick(rec, "hours_worked"), None),
            }
            found.setdefault((uid, wave), []).append(entry)
    out = {}
    for key, entries in found.items():
        entries.sort(key=lambda e: (e["activity"], e["sector"], e["hours"] is None,
                                    e["hours"] or 0))
        out[key] = entries[0]
    return out


def load_prior_bands(c):
    found = {}
    for path in sorted(c.files("prior__wave*-bands.*")):
        for rec in read_table(path):
            if not in_scope(rec):
                continue
            uid = canon_unit(pick(rec, "unit_id", "unit"))
            if uid is None:
                continue
            wave = to_int(pick(rec, "source_wave"), None)
            band = nfc(str(rec.get("prior_band") or "")).strip()
            found.setdefault((uid, wave), []).append(band)
    return {k: sorted(v)[0] for k, v in found.items()}


# ---------------------------------------------------------------- weighting


def build_adjustment_cells(unit_keys, eligible, responding, dweight, ref):
    """Collapse cells; returns (assignment, cells, rounds)."""
    cur = {u: unit_keys[u] for u in eligible}
    rounds = 0
    maxr = ref["max_collapse_rounds"]
    while rounds < maxr:
        rounds += 1
        groups = {}
        for u, key in cur.items():
            groups.setdefault(key, []).append(u)
        moved = False
        for key in sorted(groups):
            members = groups[key]
            depth = key.count("|")
            if depth == 0:
                continue
            ew = sum(dweight[u] for u in members)
            rw = sum(dweight[u] for u in members if u in responding)
            rc = sum(1 for u in members if u in responding)
            rate = rdiv(rw * 10000, ew) if ew else 0
            if rate >= ref["min_response_rate_bp"] and rc >= ref["min_cell_count"]:
                continue
            parent = key.rsplit("|", 1)[0]
            for u in members:
                cur[u] = parent
            moved = True
        if not moved:
            break
    cells = {}
    for u, key in cur.items():
        cells.setdefault(key, []).append(u)
    info = {}
    for key, members in cells.items():
        ew = sum(dweight[u] for u in members)
        rw = sum(dweight[u] for u in members if u in responding)
        rc = sum(1 for u in members if u in responding)
        info[key] = {
            "cell_key": key,
            "depth": key.count("|"),
            "eligible_weight_uw": ew,
            "responding_weight_uw": rw,
            "responding_count": rc,
            "response_rate_bp": rdiv(rw * 10000, ew) if ew else 0,
            "adjustment_factor_uw": rdiv(ew * 1000000, rw) if rw else 0,
        }
    return cur, info, rounds


def rake(weights, margin_levels, margin_order, controls, tolerance, max_iter, mode):
    """weights: dict unit -> int.  margin_levels: dim -> {unit: level}."""
    units = sorted(weights)
    w = [weights[u] for u in units]
    combos = {}
    for i, u in enumerate(units):
        key = tuple(margin_levels[d].get(u) for d in margin_order)
        combos.setdefault(key, []).append(i)
    combo_keys = sorted(combos, key=lambda k: tuple("" if x is None else x for x in k))
    per_iteration = []
    iterations = 0
    converged = False
    dev = 0
    for it in range(1, max_iter + 1):
        iterations = it
        if mode == "each":
            for j, dim in enumerate(margin_order):
                sums = {}
                for key in combo_keys:
                    lev = key[j]
                    if lev is None or lev not in controls[dim]:
                        continue
                    s = sums.get(lev, 0)
                    for i in combos[key]:
                        s += w[i]
                    sums[lev] = s
                for key in combo_keys:
                    lev = key[j]
                    if lev is None or lev not in controls[dim]:
                        continue
                    s = sums.get(lev, 0)
                    if s == 0:
                        continue
                    ctl = controls[dim][lev]
                    for i in combos[key]:
                        w[i] = rdiv(w[i] * ctl, s)
        else:
            factors = {key: Fraction(1) for key in combo_keys}
            totals = {key: sum(w[i] for i in combos[key]) for key in combo_keys}
            for j, dim in enumerate(margin_order):
                sums = {}
                for key in combo_keys:
                    lev = key[j]
                    if lev is None or lev not in controls[dim]:
                        continue
                    sums[lev] = sums.get(lev, 0) + factors[key] * totals[key]
                lev_factor = {}
                for lev, s in sums.items():
                    if s == 0:
                        continue
                    lev_factor[lev] = Fraction(controls[dim][lev]) / s
                for key in combo_keys:
                    lev = key[j]
                    if lev in lev_factor:
                        factors[key] = factors[key] * lev_factor[lev]
            for key in combo_keys:
                fr = factors[key]
                num, den = fr.numerator, fr.denominator
                if den == 1 and num == 1:
                    continue
                for i in combos[key]:
                    w[i] = rdiv(w[i] * num, den)
        dev = 0
        for j, dim in enumerate(margin_order):
            sums = {}
            for key in combo_keys:
                lev = key[j]
                if lev is None or lev not in controls[dim]:
                    continue
                s = sums.get(lev, 0)
                for i in combos[key]:
                    s += w[i]
                sums[lev] = s
            for lev, ctl in controls[dim].items():
                dev = max(dev, abs(sums.get(lev, 0) - ctl))
        per_iteration.append({"iteration": it, "max_deviation_uw": dev})
        if dev <= tolerance:
            converged = True
            break
    return {
        "weights": {u: w[i] for i, u in enumerate(units)},
        "iterations_used": iterations,
        "converged": converged,
        "final_max_deviation_uw": dev,
        "per_iteration": per_iteration,
    }


def trim(raked, unit_stratum, ref, trigger=None):
    """Returns (final weights, trimmed set, ceilings, deffs)."""
    if trigger is None:
        trigger = ref["trim_trigger_deff_bp"]
    by_stratum = {}
    for u, w in raked.items():
        by_stratum.setdefault(unit_stratum[u], []).append(u)
    final = dict(raked)
    trimmed = set()
    ceilings = {}
    for st in sorted(by_stratum):
        members = sorted(by_stratum[st])
        ws = [raked[u] for u in members]
        med = median_low(ws)
        ceiling = rdiv(med * ref["trim_ratio_bp"], 10000)
        ceilings[st] = ceiling
        total = sum(ws)
        if total == 0:
            continue
        deff = rdiv(10000 * len(ws) * sum(x * x for x in ws), total * total)
        if deff <= trigger:
            continue
        above = [u for u in members if raked[u] > ceiling]
        if not above:
            continue
        removed = sum(raked[u] - ceiling for u in above)
        for u in above:
            final[u] = ceiling
            trimmed.add(u)
        below = [u for u in members if raked[u] <= ceiling]
        base = sum(raked[u] for u in below)
        if not below or base == 0:
            continue
        handed = 0
        for u in below:
            share = rdiv(removed * raked[u], base)
            final[u] = raked[u] + share
            handed += share
        diff = removed - handed
        if diff:
            target = min(below, key=lambda u: (-final[u], u))
            final[target] += diff
    return final, trimmed, ceilings


# ---------------------------------------------------------------- output


def write_json(path, obj):
    with open(path, "w", encoding="utf-8", newline="") as f:
        json.dump(obj, f, sort_keys=True, indent=2, ensure_ascii=False)
        f.write("\n")


def write_delim(path, header, rows, delim=","):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(delim.join(header) + "\n")
        for row in rows:
            f.write(delim.join(str(x) for x in row) + "\n")


def yn(flag):
    return "Y" if flag else "N"


# ---------------------------------------------------------------- benchmarks


def benchmark_rows(path):
    """Returns (defaults, rows) for one benchmark file."""
    ext = os.path.splitext(path)[1]
    if ext in DELIMS:
        return {}, read_table(path)
    if ext == ".jsonl":
        return {}, read_table(path)
    if ext == ".json":
        doc = json.loads(read_text(path))
        defaults = {k: v for k, v in doc.items() if not isinstance(v, (list, dict))}
        rows = doc.get("series", [])
        return defaults, rows
    if ext == ".toml":
        doc = read_toml(path)
        defaults = {k: v for k, v in doc.items() if not isinstance(v, (list, dict))}
        rows = doc.get("series", [])
        return defaults, rows
    if ext == ".properties":
        flat = read_props(path)
        defaults = {}
        rows = {}
        for k, v in flat.items():
            parts = k.split(".")
            if parts[0] == "series" and len(parts) == 3:
                rows.setdefault(parts[1], {})[parts[2]] = v
            elif len(parts) == 1:
                defaults[k] = v
        return defaults, [rows[k] for k in sorted(rows)]
    if ext == ".ini":
        doc = read_ini(path)
        defaults = {}
        rows = []
        for sec in sorted(doc):
            if sec.startswith("series"):
                rows.append(doc[sec])
            else:
                defaults.update(doc[sec])
        return defaults, rows
    raise ValueError("unsupported benchmark %s" % path)


def load_controls(c, ref):
    period = ref["reference_period"]
    conv = ref["conversions"]
    best = {}
    for path in c.files("bench__*"):
        if "unit-conversions" in os.path.basename(path):
            continue
        defaults, rows = benchmark_rows(path)
        for row in rows:
            if not isinstance(row, dict):
                continue
            if not in_scope(row) or not in_scope(defaults):
                continue
            get = lambda *names: pick(row, *names) if pick(row, *names) is not None \
                else pick(defaults, *names)
            if nfc(str(get("reference_period"))).strip() != period:
                continue
            dim = nfc(str(get("dimension"))).strip()
            level = nfc(str(get("level_key", "key"))).strip()
            rank = to_int(get("rank"), 0)
            pub = nfc(str(get("published_date"))).strip()
            src = nfc(str(get("source_id"))).strip()
            unit = nfc(str(get("unit"))).strip()
            if unit not in conv:
                continue
            value = Fraction(nfc(str(get("value"))).strip()) * conv[unit] * 1000000
            cand = (rank, pub, src, rnd_frac(value))
            key = (dim, level)
            if key not in best or cand[:3] > best[key][:3]:
                best[key] = cand
    controls = {}
    meta = {}
    for (dim, level), (rank, pub, src, val) in best.items():
        controls.setdefault(dim, {})[level] = val
        meta[(dim, level)] = (rank, src)
    return controls, meta


# ---------------------------------------------------------------- pipeline


def weight_round(dweights, unit_keys, eligible, responding, ref, margin_levels,
                 margin_order, controls, unit_stratum, mode, max_iter=None,
                 tolerance=None, trim_trigger=None):
    """Nonresponse adjustment, raking and trimming over one set of design weights."""
    assign, cells, rounds = build_adjustment_cells(
        unit_keys, eligible, responding, dweights, ref
    )
    adjusted = {}
    for u in responding:
        factor = cells[assign[u]]["adjustment_factor_uw"]
        adjusted[u] = rdiv(dweights[u] * factor, 1000000)
    rk = rake(
        adjusted,
        margin_levels,
        margin_order,
        controls,
        ref["tolerance_uw"] if tolerance is None else tolerance,
        ref["max_iterations"] if max_iter is None else max_iter,
        mode,
    )
    final, trimmed, ceilings = trim(rk["weights"], unit_stratum, ref, trim_trigger)
    return {
        "assign": assign,
        "cells": cells,
        "collapse_rounds": rounds,
        "adjusted": adjusted,
        "raked": rk["weights"],
        "raking": rk,
        "final": final,
        "trimmed": trimmed,
        "ceilings": ceilings,
    }


def build_groups(frame_units, ref):
    """Replication groups: strata with fewer than two PSUs merge into their partner."""
    strata = sorted(set(u["stratum"] for u in frame_units.values()))
    psus = {}
    for u in frame_units.values():
        psus.setdefault(u["stratum"], set()).add(u["psu_code"])
    group_of = {st: st for st in strata}

    def root(st):
        seen = set()
        while group_of[st] != st and st not in seen:
            seen.add(st)
            st = group_of[st]
        return st

    changed = True
    while changed:
        changed = False
        members = {}
        for st in strata:
            members.setdefault(root(st), []).append(st)
        for g in sorted(members):
            gpsus = set()
            for st in members[g]:
                gpsus |= psus.get(st, set())
            if len(gpsus) >= 2:
                continue
            partner = ref["strata"].get(g, {}).get("collapse_partner", "")
            if not partner or partner not in group_of:
                continue
            target = root(partner)
            if target == g:
                continue
            group_of[g] = target
            changed = True
            break
    groups = {}
    for st in strata:
        groups.setdefault(root(st), []).append(st)
    out = {}
    for g, sts in groups.items():
        gpsus = set()
        for st in sts:
            gpsus |= psus.get(st, set())
        out[g] = {"psus": sorted(gpsus), "size": len(gpsus), "strata": sorted(sts)}
    return out


def calibrate_raking(c, ref):
    """The pilot record settles the margin order and the rounding point."""
    import itertools

    doc = json.loads(read_text(c.path("calib__pilot-round.json")))
    controls = {d: dict(v) for d, v in doc["controls_uw"].items()}
    units = [u for u in doc["units"] if in_scope(u)]
    dims = sorted(controls)
    weights = {}
    margin_levels = {d: {} for d in dims}
    for u in units:
        uid = nfc(str(u["pilot_id"])).strip()
        weights[uid] = to_int(u["adjusted_weight_uw"], 0)
        for d in dims:
            margin_levels[d][uid] = nfc(str(u.get(d, ""))).strip()
    published = doc["published"]
    want_iter = to_int(published.get("iterations_used"), None)
    want_totals = published.get("raked_totals_uw", {})
    results = []
    for order in itertools.permutations(dims):
        for mode in ("each", "end"):
            rk = rake(
                weights,
                margin_levels,
                list(order),
                controls,
                ref["tolerance_uw"],
                ref["max_iterations"],
                mode,
            )
            sums = {d: {} for d in dims}
            for uid, w in rk["weights"].items():
                for d in dims:
                    lev = margin_levels[d][uid]
                    sums[d][lev] = sums[d].get(lev, 0) + w
            score = 1 if rk["iterations_used"] == want_iter else 0
            for d, levels in want_totals.items():
                for lev, val in levels.items():
                    if sums.get(d, {}).get(lev, 0) == val:
                        score += 1
            total = 1 + sum(len(v) for v in want_totals.values())
            results.append((score, total, list(order), mode))
    results.sort(key=lambda r: (-r[0], r[2], r[3]))
    best = results[0]
    return {"margin_order": best[2], "mode": best[3], "results": results}


# ---------------------------------------------------------------- derivation


def derive(data_dir, options=None):
    """Runs the whole derivation and returns every intermediate figure."""
    opt = dict(options or {})
    c = Corpus(data_dir)
    ref = load_reference(c)
    for key in ("min_publish_count", "max_publish_cv_bp", "dominance_bp",
                "max_cascade_rounds", "max_iterations", "trim_trigger_deff_bp"):
        if key in opt:
            ref[key] = opt[key]
    frame = resolve_frame(c, ref)
    units = frame["units"]
    controls, cmeta = load_controls(c, ref)
    contacts = load_contacts(c, ref)
    interviews = load_interviews(c)
    priors = load_prior_bands(c)
    cal = calibrate_raking(c, ref)
    margin_order = opt.get("margin_order", cal["margin_order"])
    mode = opt.get("mode", cal["mode"])
    rw = ref["reference_wave"]
    disp = ref["dispositions"]

    # ---- response status
    resolved_rw = {}
    for (uid, wave), info in contacts["resolved"].items():
        if wave == rw:
            resolved_rw[uid] = info
    disposition_counts = {}
    for info in resolved_rw.values():
        disposition_counts[info["disposition"]] = (
            disposition_counts.get(info["disposition"], 0) + 1
        )
    superseded = sorted(
        u for u, i in resolved_rw.items() if disp[i["disposition"]]["superseded"]
    )
    eligible = []
    responding = []
    for uid in sorted(units):
        info = resolved_rw.get(uid)
        if info is None:
            continue
        flags = disp[info["disposition"]]
        if flags["eligible"] and units[uid]["dwelling_units"] != 0:
            eligible.append(uid)
            if (
                flags["responding"]
                and not flags["superseded"]
                and (uid, rw) in interviews
            ):
                responding.append(uid)
    eligible_set, responding_set = set(eligible), set(responding)

    # ---- unit attributes
    attrs = {}
    for uid in sorted(units):
        u = units[uid]
        tenure = u["tenure"]
        tclass = ref["tenures"].get(tenure, {}).get("class", tenure)
        attempts12 = sum(
            contacts["attempt_counts"].get((uid, w), 0)
            for w in ref["prior_waves"]
        )
        cband = contact_band_of(ref["contact_bands"], attempts12) or ""
        iv3 = interviews.get((uid, rw))
        iv2 = interviews.get((uid, 2))
        iv1 = interviews.get((uid, 1))
        band_ref = None
        if iv3 is not None:
            if iv2 is not None and iv2["hours"] is not None:
                band_ref = band_of_hours(ref["bands"], iv2["hours"])
            elif priors.get((uid, 2)):
                band_ref = priors[(uid, 2)]
            elif priors.get((uid, 1)):
                band_ref = priors[(uid, 1)]
            else:
                band_ref = band_of_hours(ref["bands"], 0)
        band_w1 = None
        if iv1 is not None:
            if iv1["hours"] is not None:
                band_w1 = band_of_hours(ref["bands"], iv1["hours"])
            elif priors.get((uid, 1)):
                band_w1 = priors[(uid, 1)]
            else:
                band_w1 = band_of_hours(ref["bands"], 0)
        attrs[uid] = {
            "region": u["region"],
            "stratum": u["stratum"],
            "psu": u["psu_code"],
            "tenure": tenure,
            "tenure_class": tclass,
            "contact_band": cband,
            "attempts12": attempts12,
            "activity": iv3["activity"] if iv3 else None,
            "sector": iv3["sector"] if iv3 else None,
            "band_ref": band_ref,
            "band_w1": band_w1,
            "cell_key": "|".join([u["stratum"], tclass, cband]),
        }

    # ---- design weights
    stratum_n = {}
    for uid in units:
        st = attrs[uid]["stratum"]
        stratum_n[st] = stratum_n.get(st, 0) + 1
    dweights = {}
    subsampled = ref["subsampled"]
    for uid in sorted(units):
        st = attrs[uid]["stratum"]
        pop = ref["strata"][st]["population"]
        dw = rdiv(pop * 1000000, stratum_n[st])
        if subsampled.get(uid):
            dw = rdiv(dw * 10000, ref["subsample_factor_bp"])
        dweights[uid] = dw

    margin_levels = {
        "region_tenure": {
            u: "%s|%s" % (attrs[u]["region"], attrs[u]["tenure"]) for u in attrs
        },
        "activity": {u: attrs[u]["activity"] for u in attrs},
        "band": {u: attrs[u]["band_ref"] for u in attrs},
    }
    unit_keys = {u: attrs[u]["cell_key"] for u in attrs}
    unit_stratum = {u: attrs[u]["stratum"] for u in attrs}

    full = weight_round(
        dweights, unit_keys, eligible, responding_set, ref, margin_levels,
        margin_order, controls, unit_stratum, mode,
    )

    # ---- replicates
    groups = build_groups(units, ref)
    group_of_stratum = {}
    for g, info in groups.items():
        for st in info["strata"]:
            group_of_stratum[st] = g
    replicates = []
    for g in sorted(groups):
        info = groups[g]
        k = info["size"]
        if k < 2:
            continue
        for psu in info["psus"]:
            replicates.append((g, psu, k))
    replicates.sort(key=lambda r: "%s::%s" % (r[0], r[1]))
    rep_results = []
    for g, psu, k in replicates:
        rdw = {}
        for uid in sorted(units):
            st = attrs[uid]["stratum"]
            if group_of_stratum.get(st) != g:
                rdw[uid] = dweights[uid]
            elif attrs[uid]["psu"] == psu:
                rdw[uid] = 0
            else:
                rdw[uid] = rdiv(dweights[uid] * k, k - 1)
        rel = [u for u in eligible if rdw[u] != 0]
        rrs = set(u for u in responding if rdw[u] != 0)
        res = weight_round(
            {u: rdw[u] for u in rel}, unit_keys, rel, rrs, ref, margin_levels,
            margin_order, controls, unit_stratum, mode,
        )
        rep_results.append(
            {
                "replicate_id": "%s::%s" % (g, psu),
                "group": g,
                "dropped_psu": psu,
                "group_size": k,
                "result": res,
            }
        )

    return {
        "ref": ref,
        "corpus": c,
        "frame": frame,
        "units": units,
        "attrs": attrs,
        "controls": controls,
        "control_meta": cmeta,
        "contacts": contacts,
        "interviews": interviews,
        "resolved_rw": resolved_rw,
        "disposition_counts": disposition_counts,
        "superseded": superseded,
        "eligible": eligible,
        "responding": responding,
        "dweights": dweights,
        "margin_levels": margin_levels,
        "margin_order": margin_order,
        "mode": mode,
        "calibration": cal,
        "full": full,
        "groups": groups,
        "group_of_stratum": group_of_stratum,
        "replicates": rep_results,
    }


# ---------------------------------------------------------------- estimates


def cell_membership(state):
    """unit -> {table: (row_level, column_level)} for the published tables."""
    attrs = state["attrs"]
    final = state["full"]["final"]
    responding = state["responding"]
    order = sorted(responding, key=lambda u: (final[u], u))
    n = len(order)
    quintile = {}
    for i, u in enumerate(order):
        quintile[u] = "Q%d" % (1 + (5 * i) // n) if n else "Q1"
    out = {}
    for u in responding:
        a = attrs[u]
        out[u] = {
            "activity_by_region": (a["activity"], a["region"]),
            "tenure_by_wquintile": (a["tenure"], quintile[u]),
            "hours_by_sector": (a["sector"], a["band_ref"]),
            "band_transition": (a["band_w1"], a["band_ref"]),
        }
    return out


def table_cells(state, membership):
    """Per table: ordered cell keys and the responding units in each."""
    registry = state["ref"]["registry"]
    tables = {}
    for t, ax in registry.items():
        rows, cols = ax["row"], ax["column"]
        cells = {}
        order = []
        for r in rows:
            for col in cols:
                key = "%s|%s" % (r, col)
                cells[key] = []
                order.append((key, r, col))
        for u, m in membership.items():
            lv = m.get(t)
            if lv is None:
                continue
            key = "%s|%s" % (lv[0], lv[1])
            if key in cells:
                cells[key].append(u)
        tables[t] = {"order": order, "cells": cells}
    return tables


def estimate_tables(state):
    membership = cell_membership(state)
    tables = table_cells(state, membership)
    final = state["full"]["final"]
    reps = state["replicates"]
    rep_finals = [(r, r["result"]["final"]) for r in reps]
    out = {}
    for t, info in tables.items():
        cells = {}
        group_var = {}
        total_var = 0
        for key, _row, _col in info["order"]:
            members = sorted(info["cells"][key])
            total = sum(final[u] for u in members)
            count = len(members)
            maxw = max((final[u] for u in members), default=0)
            var = 0
            for r, rfinal in rep_finals:
                k = r["group_size"]
                rt = sum(rfinal.get(u, 0) for u in members)
                term = ((k - 1) * (rt - total) ** 2) // k
                var += term
                group_var[r["group"]] = group_var.get(r["group"], 0) + term
            se = isqrt_round(var)
            cells[key] = {
                "cell_key": key,
                "point_estimate_uw": total,
                "unweighted_count": count,
                "maximum_weight_uw": maxw,
                "variance_uw2": var,
                "standard_error_uw": se,
                "cv_bp": rdiv(se * 10000, total) if total else 0,
                "dominance_bp": rdiv(maxw * 10000, total) if total else 0,
            }
            total_var += var
        out[t] = {
            "order": info["order"],
            "cells": cells,
            "summed_cell_variance_uw2": total_var,
            "by_group": group_var,
        }
    return out


# ---------------------------------------------------------------- disclosure


def screen_cells(state, est, min_count=None, max_cv=None, dom=None):
    ref = state["ref"]
    min_count = ref["min_publish_count"] if min_count is None else min_count
    max_cv = ref["max_publish_cv_bp"] if max_cv is None else max_cv
    dom = ref["dominance_bp"] if dom is None else dom
    allcells = []
    for t in sorted(est):
        for key, _r, _c in est[t]["order"]:
            cell = est[t]["cells"][key]
            reasons = []
            if cell["unweighted_count"] < min_count:
                reasons.append("count")
            if cell["cv_bp"] > max_cv:
                reasons.append("cv")
            if cell["dominance_bp"] > dom:
                reasons.append("dominance")
            allcells.append((t, key, cell, reasons))
    ranked = sorted(allcells, key=lambda x: (-x[2]["cv_bp"], x[0], x[1]))
    ranks = {}
    for i, (t, key, _cell, _rs) in enumerate(ranked):
        ranks[(t, key)] = i + 1
    primary = {}
    for t, key, cell, reasons in allcells:
        if reasons:
            primary.setdefault(t, {})[key] = reasons
    return {"ranks": ranks, "primary": primary, "cells": allcells}


def secondary_suppression(state, est, primary, max_rounds=None):
    ref = state["ref"]
    if max_rounds is None:
        max_rounds = ref["max_cascade_rounds"]
    registry = ref["registry"]
    out = {}
    rounds_used = {}
    for t in sorted(est):
        rows = registry[t]["row"]
        cols = registry[t]["column"]
        cells = est[t]["cells"]
        suppressed = set(primary.get(t, {}).keys())
        picks = []
        rnd = 0
        while rnd < max_rounds:
            rnd += 1
            changed = False
            axes = [("row", lev, ["%s|%s" % (lev, cc) for cc in cols]) for lev in rows]
            axes += [
                ("column", lev, ["%s|%s" % (rr, lev) for rr in rows]) for lev in cols
            ]
            for axis, lev, keys in axes:
                hidden = [k for k in keys if k in suppressed]
                if len(hidden) != 1:
                    continue
                free = [k for k in keys if k not in suppressed]
                if not free:
                    continue
                choice = min(free, key=lambda k: (cells[k]["unweighted_count"], k))
                suppressed.add(choice)
                picks.append(
                    {
                        "cell_key": choice,
                        "axis": axis,
                        "axis_level": lev,
                        "round": rnd,
                    }
                )
                changed = True
            if not changed:
                break
        out[t] = picks
        rounds_used[t] = rnd
    return out, rounds_used


# ---------------------------------------------------------------- reports


def margin_level_sums(state, weights):
    sums = {}
    for dim, levels in state["margin_levels"].items():
        acc = {}
        for u, w in weights.items():
            lev = levels.get(u)
            if lev is None:
                continue
            acc[lev] = acc.get(lev, 0) + w
        sums[dim] = acc
    return sums


def margin_deviation(state, weights):
    sums = margin_level_sums(state, weights)
    dev = 0
    for dim, levels in state["controls"].items():
        for lev, ctl in levels.items():
            dev = max(dev, abs(sums.get(dim, {}).get(lev, 0) - ctl))
    return dev


def write_reports(state, out_dir):
    ref = state["ref"]
    units = state["units"]
    attrs = state["attrs"]
    full = state["full"]
    final = full["final"]
    raked = full["raked"]
    responding = sorted(state["responding"])
    path = lambda name: os.path.join(out_dir, name)

    # -- frame audit
    write_json(
        path("frame_audit.json"),
        {
            "repair_counts": state["frame"]["repairs"],
            "self_referencing_units": state["frame"]["self_ref"],
            "dangling_parent_units": state["frame"]["dangling"],
            "discarded_record_ids": state["frame"]["discarded"],
            "resolved_unit_count": len(units),
            "subsample_factor_bp": ref["subsample_factor_bp"],
        },
    )

    # -- control totals and margins
    controls = state["controls"]
    grand = sum(controls.get("region_tenure", {}).values())
    write_json(
        path("control_totals.json"),
        {
            "reference_period": ref["reference_period"],
            "grand_total_uw": grand,
            "dimensions": {d: dict(v) for d, v in controls.items()},
            "level_counts": {d: len(v) for d, v in controls.items()},
        },
    )
    rows = []
    for dim in sorted(controls):
        for lev in sorted(controls[dim]):
            rank, src = state["control_meta"][(dim, lev)]
            rows.append([dim, lev, controls[dim][lev], rank, src])
    write_delim(
        path("control_margins.tsv"),
        ["dimension", "level_key", "control_total_uw", "chosen_rank", "chosen_source"],
        rows,
        "\t",
    )

    # -- response status
    unit_block = {}
    for uid, info in state["resolved_rw"].items():
        unit_block[uid] = {
            "disposition": info["disposition"],
            "attempt_no": info["attempt_no"],
            "resolved_utc": info["resolved_utc"],
            "attempts": state["contacts"]["attempt_counts"].get(
                (uid, ref["reference_wave"]), 0
            ),
        }
    write_json(
        path("response_status.json"),
        {
            "reference_wave": ref["reference_wave"],
            "disposition_counts": state["disposition_counts"],
            "eligible_count": len(state["eligible"]),
            "responding_count": len(state["responding"]),
            "superseded_units": state["superseded"],
            "units": unit_block,
        },
    )

    # -- design weights
    write_delim(
        path("design_weights.csv"),
        ["unit_id", "stratum", "psu_code", "subsampled", "design_weight_uw"],
        [
            [
                uid,
                attrs[uid]["stratum"],
                attrs[uid]["psu"],
                yn(ref["subsampled"].get(uid)),
                state["dweights"][uid],
            ]
            for uid in sorted(units)
        ],
    )

    # -- adjustment cells
    cells = full["cells"]
    depth_counts = {"0": 0, "1": 0, "2": 0}
    for cell in cells.values():
        depth_counts[str(cell["depth"])] = depth_counts.get(str(cell["depth"]), 0) + 1
    write_json(
        path("adjustment_cells.json"),
        {
            "collapse_rounds": full["collapse_rounds"],
            "cell_count": len(cells),
            "cells": [cells[k] for k in sorted(cells)],
            "depth_counts": depth_counts,
        },
    )
    write_delim(
        path("adjusted_weights.csv"),
        ["unit_id", "cell_key", "adjustment_factor_uw", "adjusted_weight_uw"],
        [
            [
                uid,
                full["assign"][uid],
                cells[full["assign"][uid]]["adjustment_factor_uw"],
                full["adjusted"][uid],
            ]
            for uid in responding
        ],
    )

    # -- raking trace
    rk = full["raking"]
    write_json(
        path("raking_trace.json"),
        {
            "margin_order": list(state["margin_order"]),
            "tolerance_uw": ref["tolerance_uw"],
            "max_iterations": ref["max_iterations"],
            "iterations_used": rk["iterations_used"],
            "converged": bool(rk["converged"]),
            "final_max_deviation_uw": rk["final_max_deviation_uw"],
            "per_iteration": rk["per_iteration"],
        },
    )

    # -- final weights and diagnostics
    write_delim(
        path("final_weights.csv"),
        ["unit_id", "stratum", "raked_weight_uw", "trimmed", "final_weight_uw"],
        [
            [
                uid,
                attrs[uid]["stratum"],
                raked[uid],
                yn(uid in full["trimmed"]),
                final[uid],
            ]
            for uid in responding
        ],
    )
    total_final = sum(final.values())
    stratum_totals = {}
    for uid in responding:
        st = attrs[uid]["stratum"]
        stratum_totals[st] = stratum_totals.get(st, 0) + final[uid]
    sq = sum(final[u] * final[u] for u in responding)
    write_json(
        path("weight_diagnostics.json"),
        {
            "responding_count": len(responding),
            "final_weight_total_uw": total_final,
            "design_effect_bp": (
                rdiv(10000 * len(responding) * sq, total_final * total_final)
                if total_final
                else 0
            ),
            "median_weight_uw": median_low([final[u] for u in responding]),
            "maximum_weight_uw": max((final[u] for u in responding), default=0),
            "minimum_weight_uw": min((final[u] for u in responding), default=0),
            "trimmed_count": len(full["trimmed"]),
            "trimmed_units": sorted(full["trimmed"]),
            "stratum_totals_uw": stratum_totals,
            "stratum_ceilings_uw": {
                st: full["ceilings"][st] for st in sorted(full["ceilings"])
            },
        },
    )

    # -- replicate design and summary
    groups = state["groups"]
    write_json(
        path("replicate_design.json"),
        {
            "replicate_count": len(state["replicates"]),
            "group_count": len(groups),
            "groups": {
                g: {
                    "psus": groups[g]["psus"],
                    "size": groups[g]["size"],
                    "strata": groups[g]["strata"],
                }
                for g in groups
            },
            "merged_groups": {
                g: groups[g]["strata"] for g in groups if len(groups[g]["strata"]) > 1
            },
        },
    )
    rep_rows = []
    for rep in sorted(state["replicates"], key=lambda r: r["replicate_id"]):
        res = rep["result"]
        rep_rows.append(
            [
                rep["replicate_id"],
                rep["group"],
                rep["dropped_psu"],
                rep["group_size"],
                res["raking"]["iterations_used"],
                yn(res["raking"]["converged"]),
                len(res["trimmed"]),
                sum(res["final"].values()),
            ]
        )
    write_delim(
        path("replicate_summary.csv"),
        [
            "replicate_id",
            "group",
            "dropped_psu",
            "group_size",
            "iterations_used",
            "converged",
            "trimmed_count",
            "final_total_uw",
        ],
        rep_rows,
    )

    # -- estimates
    est = estimate_tables(state)
    for t in sorted(est):
        rows = []
        for key, row_level, col_level in est[t]["order"]:
            cell = est[t]["cells"][key]
            rows.append(
                [
                    key,
                    row_level,
                    col_level,
                    cell["point_estimate_uw"],
                    cell["unweighted_count"],
                    cell["standard_error_uw"],
                    cell["cv_bp"],
                    cell["dominance_bp"],
                ]
            )
        write_delim(
            path("estimates_%s.csv" % t),
            [
                "cell_key",
                "row_level",
                "column_level",
                "point_estimate_uw",
                "unweighted_count",
                "standard_error_uw",
                "cv_bp",
                "dominance_bp",
            ],
            rows,
        )
    write_json(
        path("variance_components.json"),
        {
            "replicate_count": len(state["replicates"]),
            "tables": {
                t: {
                    "summed_cell_variance_uw2": est[t]["summed_cell_variance_uw2"],
                    "by_group": est[t]["by_group"],
                }
                for t in est
            },
        },
    )

    # -- disclosure
    screen = screen_cells(state, est)
    ranks = screen["ranks"]
    primary = screen["primary"]
    cv_tables = {}
    for t in sorted(est):
        entries = []
        for key, _r, _c in est[t]["order"]:
            cell = est[t]["cells"][key]
            entries.append(
                {
                    "cell_key": key,
                    "screening_rank": ranks[(t, key)],
                    "cv_bp": cell["cv_bp"],
                    "dominance_bp": cell["dominance_bp"],
                    "unweighted_count": cell["unweighted_count"],
                    "reasons": primary.get(t, {}).get(key, []),
                }
            )
        entries.sort(key=lambda e: e["screening_rank"])
        cv_tables[t] = entries
    write_json(
        path("cv_screening.json"),
        {
            "min_publish_count": ref["min_publish_count"],
            "max_publish_cv_bp": ref["max_publish_cv_bp"],
            "dominance_bp": ref["dominance_bp"],
            "tables": cv_tables,
        },
    )
    prim_tables = {}
    prim_counts = {}
    for t in sorted(est):
        keys = sorted(primary.get(t, {}))
        prim_tables[t] = [{"cell_key": k, "reasons": primary[t][k]} for k in keys]
        prim_counts[t] = len(keys)
    write_json(
        path("primary_suppression.json"),
        {
            "tables": prim_tables,
            "counts": prim_counts,
            "total": sum(prim_counts.values()),
        },
    )
    sec, rounds_used = secondary_suppression(state, est, primary)
    sec_tables = {}
    sec_counts = {}
    for t in sorted(est):
        entries = sorted(sec.get(t, []), key=lambda e: e["cell_key"])
        sec_tables[t] = entries
        sec_counts[t] = len(entries)
    write_json(
        path("secondary_suppression.json"),
        {
            "tables": sec_tables,
            "cascade_rounds": rounds_used,
            "counts": sec_counts,
            "total": sum(sec_counts.values()),
        },
    )
    audit = []
    for t in sorted(est):
        sec_keys = set(e["cell_key"] for e in sec.get(t, []))
        for key, _r, _c in est[t]["order"]:
            cell = est[t]["cells"][key]
            if key in primary.get(t, {}):
                status, reason = "suppressed", "primary"
            elif key in sec_keys:
                status, reason = "suppressed", "secondary"
            else:
                status, reason = "published", "none"
            audit.append(
                (
                    ranks[(t, key)],
                    t,
                    key,
                    status,
                    reason,
                    cell["point_estimate_uw"],
                    cell["unweighted_count"],
                    cell["cv_bp"],
                )
            )
    audit.sort(key=lambda r: (r[0], r[1], r[2]))
    write_delim(
        path("disclosure_audit.tsv"),
        [
            "screening_rank",
            "table_name",
            "cell_key",
            "status",
            "reason",
            "point_estimate_uw",
            "unweighted_count",
            "cv_bp",
        ],
        [list(r) for r in audit],
        "\t",
    )

    # -- closure
    table_block = {}
    residual_total = 0
    for t in sorted(est):
        sec_keys = set(e["cell_key"] for e in sec.get(t, []))
        total = 0
        published = 0
        suppressed = 0
        for key, _r, _c in est[t]["order"]:
            value = est[t]["cells"][key]["point_estimate_uw"]
            total += value
            if key in primary.get(t, {}) or key in sec_keys:
                suppressed += value
            else:
                published += value
        residual = total - published - suppressed
        residual_total += residual
        table_block[t] = {
            "total_uw": total,
            "published_uw": published,
            "suppressed_uw": suppressed,
            "residual_uw": residual,
            "coverage_gap_uw": total_final - total,
        }
    dev = margin_deviation(state, final)
    gap = total_final - grand
    checks_raw = [
        ("raking_converged", bool(rk["converged"])),
        ("final_total_within_tolerance", abs(gap) <= ref["tolerance_uw"]),
        ("trimming_preserves_total", sum(raked.values()) == total_final),
        ("suppression_conservation", residual_total == 0),
    ]
    checks = [
        {
            "name": name,
            "expected": 1,
            "observed": 1 if ok else 0,
            "verdict": "pass" if ok else "fail",
        }
        for name, ok in checks_raw
    ]
    write_json(
        path("closure_report.json"),
        {
            "post_trim_margin_deviation_uw": dev,
            "final_weight_total_uw": total_final,
            "control_grand_total_uw": grand,
            "conservation_residual_uw": residual_total,
            "final_total_gap_uw": gap,
            "responding_count": len(responding),
            "replicate_count": len(state["replicates"]),
            "primary_suppression_total": sum(prim_counts.values()),
            "secondary_suppression_total": sum(sec_counts.values()),
            "tables": table_block,
            "checks": checks,
            "all_checks_pass": all(ok for _n, ok in checks_raw),
        },
    )
    return {"est": est, "screen": screen, "secondary": sec, "cascade": rounds_used}


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: %s DATA_DIR OUT_DIR\n" % argv[0])
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    state = derive(data_dir)
    write_reports(state, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

