"""Verifier for the streamflow rating-shift correction task.

The first half of this module is the seeded corpus generator together with the reference
derivation of every report; the grading harness regenerates the shipped network and nine held-out
networks from it, runs the delivered program on fresh copies, and compares the reports under the
output contract. Nothing here reads the agent's input directory.
"""
from __future__ import annotations

# ============================================================================ generator core
# Seeded corpus generator for the streamflow rating-shift correction task. Every name in this
# module starts with _G so the whole module can be embedded verbatim in the verifier, which
# regenerates held-out corpora at grade time and derives their expected reports.
import csv as _Gcsv
import hashlib as _Ghashlib
import io as _Gio
import json as _Gjson
import math as _Gmath
import random as _Grandom
import sqlite3 as _Gsqlite3
import zipfile as _Gzipfile
import zlib as _Gzlib
from datetime import date as _Gdate, datetime as _Gdt, timedelta as _Gtd, timezone as _Gtz
from decimal import Decimal as _GD
from fractions import Fraction as _GF
from pathlib import Path as _GPath

_GUTC = _Gtz.utc
_GEPOCH = _Gdt(1970, 1, 1, tzinfo=_GUTC)

_GDEFAULT = {
    "agency": "Corvel Basin Hydrometric Service",
    "network": "CBHS-N",
    "period_start": "2026-01-01",
    "period_end": "2026-04-01",
    "std_offset": -360,
    "dst_rule": "us",
    "date1904": False,
    "rating_sheet": "Ratings_2026A",
    "index_sheet": "RatingIndex_26",
    "site_sheet": "Sites_2026",
    "max_gap_min": 60,
    "min_cov": "0.90",
    "margin_h": 24,
    "drift_tol": "0.02",
    "tol": {"E": "2.0", "G": "5.0", "F": "8.0"},
    "tol_old": {"E": "3.0", "G": "6.0", "F": "10.0"},
    "n_sites": 10,
    "n_backup": 4,
    "n_new_rating": 4,
    "ice_sites": 5,
    "no_meas_ice": 1,
    "revision_rate": 0.04,
    "void_rate": 0.008,
    "dup_hours": 5,
    "conflicts": 14,
    "outages": 6,
    "fault_runs": 5,
    "edits": 70,
    "rejects": 4,
    "regrades": 7,
    "errata": 4,
    "disregard": 2,
    "visit_amends": 6,
    "meas_per_site": 7,
    "dev_tie": 2,
    "err_tie": 1,
    "midnight_gaps": 4,
    "low_flow_site": True,
    "above_top_site": True,
    "overlay_gap_site": True,
    "unit_swap": True,
    "datum_change": True,
    "alias_switch": True,
    "extra_visits": 0,
    "extra_meas": 0,
    "extra_ice_amend": 0,
    "open_ice": False,
    "pdf_octal": False,
    "pdf_td": False,
    "xlsx_runs": False,
    "xlsx_no_r": False,
    "yaml_flow": False,
    "num_text": 0.3,
    "rename": False,
    "long_chain": False,
    "order_fix": False,
    "dead_month": False,
    "lower_method": False,
}


def _Gcfg(over, seed):
    cfg = {k: (dict(v) if isinstance(v, dict) else v) for k, v in _GDEFAULT.items()}
    for k, v in (over or {}).items():
        cfg[k] = v
    cfg["seed"] = seed
    return cfg


def _G_rng(seed, tag):
    return _Grandom.Random(int(_Ghashlib.blake2b(f"{seed}:{tag}".encode(), digest_size=8).hexdigest(), 16))


# ---------------------------------------------------------------------------- exact arithmetic
_GFR_CACHE: dict = {}


def _Gfr(text):
    """Exact rational of a decimal text (or a Fraction / int)."""
    if isinstance(text, _GF):
        return text
    if isinstance(text, int):
        return _GF(text)
    v = _GFR_CACHE.get(text)
    if v is None:
        v = _GF(_GD(str(text).strip()))
        if len(_GFR_CACHE) < 500000:
            _GFR_CACHE[text] = v
    return v


def _Grnd(x, exp10):
    """Round an exact rational half to even to a multiple of 10**exp10."""
    x = _GF(x)
    if exp10 <= 0:
        m = 10 ** (-exp10)
        num, den = x.numerator * m, x.denominator
    else:
        m = 10 ** exp10
        num, den = x.numerator, x.denominator * m
    n, rem = divmod(num, den)
    if 2 * rem > den or (2 * rem == den and n % 2 == 1):
        n += 1
    return _GF(n, m) if exp10 <= 0 else _GF(n * m)


def _Gq(x, dp):
    return _Grnd(x, -dp)


def _Gge10(a, k):
    if k >= 0:
        return a.numerator >= a.denominator * 10 ** k
    return a.numerator * 10 ** (-k) >= a.denominator


def _Gmag(a):
    """floor(log10(a)) for a positive rational, exactly."""
    a = _GF(a)
    k = int(_Gmath.floor(_Gmath.log10(a.numerator) - _Gmath.log10(a.denominator)))
    while _Gge10(a, k + 1):
        k += 1
    while not _Gge10(a, k):
        k -= 1
    return k


def _Gsig(x, n):
    """Round to n significant figures, half to even, from the exact value of x (float or rational)."""
    x = _GF(x)
    if x == 0:
        return _GF(0)
    k = _Gmag(abs(x))
    return _Grnd(x, k - n + 1)


def _Gdv(x):
    """The discharge rounding table of handbook H18 (band chosen from the unrounded value)."""
    x = _GF(x)
    if x < 1:
        return _Gq(x, 2)
    if x < 10:
        return _Gq(x, 1)
    if x < 1000:
        return _Gq(x, 0)
    return _Gsig(x, 3)


def _Gtxt(x, dp=None):
    """Plain decimal text of an exact rational: fixed dp decimals, or the shortest exact form."""
    if x is None:
        return ""
    x = _GF(x)
    if dp is not None:
        x = _Gq(x, dp)
        n = x * 10 ** dp
        n = n.numerator // n.denominator
        sign = "-" if n < 0 else ""
        n = abs(n)
        if dp == 0:
            return f"{sign}{n}"
        body = str(n).rjust(dp + 1, "0")
        return f"{sign}{body[:-dp]}.{body[-dp:]}"
    for d in range(0, 30):
        v = x * 10 ** d
        if v.denominator == 1:
            return _Gtxt(x, d)
    raise ValueError("non-terminating decimal")


class _GNum(str):
    """A JSON number written verbatim."""


def _GN(x, dp=None):
    return None if x is None else _GNum(_Gtxt(x, dp))


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


# ---------------------------------------------------------------------------- time
def _Gday_utc(d):
    """Epoch seconds of 00:00 UTC on date d."""
    return (d - _Gdate(1970, 1, 1)).days * 86400


def _Gdate_of(text):
    y, m, d = (int(x) for x in str(text).split("-"))
    return _Gdate(y, m, d)


def _G_nth_sunday(y, m, n):
    d = _Gdate(y, m, 1)
    d += _Gtd(days=(6 - d.weekday()) % 7)
    return d + _Gtd(days=7 * (n - 1))


def _G_last_sunday(y, m):
    d = _Gdate(y, m + 1, 1) - _Gtd(days=1) if m < 12 else _Gdate(y, 12, 31)
    return d - _Gtd(days=(d.weekday() + 1) % 7)


def _Gdst_span(rule, year, std):
    """UTC [start, end) of daylight time in a year, or None."""
    if rule == "us":
        a = _Gday_utc(_G_nth_sunday(year, 3, 2)) + 2 * 3600 - std * 60
        b = _Gday_utc(_G_nth_sunday(year, 11, 1)) + 1 * 3600 - std * 60
        return a, b
    if rule == "eu":
        a = _Gday_utc(_G_last_sunday(year, 3)) + 3600
        b = _Gday_utc(_G_last_sunday(year, 10)) + 3600
        return a, b
    return None


def _Gis_dst(u, clock):
    y = (_GEPOCH + _Gtd(seconds=u + clock["std"] * 60)).year
    sp = _Gdst_span(clock["rule"], y, clock["std"])
    return sp is not None and sp[0] <= u < sp[1]


def _Gwall_of(u, clock):
    return u + clock["std"] * 60 + (3600 if _Gis_dst(u, clock) else 0)


def _Gwall_to_utc(w, clock):
    """UTC of a local wall-clock instant (w = naive wall seconds since epoch)."""
    u_std = w - clock["std"] * 60
    u_dst = u_std - 3600
    if _Gis_dst(u_dst, clock):
        return u_dst
    return u_std


def _Gnaive(u):
    return _GEPOCH + _Gtd(seconds=u)


def _Glst(u, clock):
    """LST text YYYY-MM-DD HH:MM of a UTC instant."""
    return _Gnaive(u + clock["std"] * 60).strftime("%Y-%m-%d %H:%M")


def _Glst_date(u, clock):
    return _Gnaive(u + clock["std"] * 60).date()


def _Gparse_naive(text):
    """Seconds since epoch of a naive YYYY-MM-DD HH:MM[:SS] text."""
    text = text.strip().replace("T", " ")
    d, _, t = text.partition(" ")
    y, m, dd = (int(x) for x in d.split("-"))
    parts = [int(x) for x in t.split(":")] if t else [0, 0]
    hh, mi = parts[0], parts[1]
    ss = parts[2] if len(parts) > 2 else 0
    return _Gday_utc(_Gdate(y, m, dd)) + hh * 3600 + mi * 60 + ss


def _Glst_to_utc(text, clock):
    return _Gparse_naive(text) - clock["std"] * 60


def _Gserial(d, date1904):
    return (d - (_Gdate(1904, 1, 1) if date1904 else _Gdate(1899, 12, 30))).days
# ---------------------------------------------------------------------------- the world
_GRIVERS = ["Corvel River", "Ashby Creek", "Linden Brook", "Marrow Fork", "Teal Run", "Oxbow Creek", "Harlan River", "Pike Branch",
            "Sable Creek", "Wren Fork", "Duskwater River", "Fennel Creek", "Brannock Run", "Quill River", "Morrow Creek", "Tansy Brook",
            "Ellery Fork", "Garnet Creek", "Holloway River", "Juniper Run", "Kestrel Creek", "Larch Brook", "Mosby River", "Nettle Creek"]
_GPLACES = [("at Ashby Weir", "WR"), ("near Halden", "HD"), ("below Mill Dam", "MD"), ("above Teal Lake", "TL"), ("at Route 9 Bridge", "R9"),
            ("near Orrin", "OR"), ("at Cobb Ford", "CF"), ("below Granite Falls", "GF"), ("near Pellston", "PL"), ("at Kerr Landing", "KL"),
            ("above Fenwick", "FW"), ("at Stroud Gap", "SG"), ("near Vail Crossing", "VC"), ("below Upton", "UP")]
_GNETS = ["CBHS-N", "CBHS-S", "CBHS-E", "CBHS-W"]
_GUNIT_RES = {"FT": 2, "M": 3, "CM": 1, "MM": 0}
_GUNIT_DIV = {"FT": _GF(1), "M": _GF(3048, 10000), "CM": _GF(3048, 100), "MM": _GF(3048, 10)}


def _G_station_ids(rng, n):
    out = set()
    while len(out) < n:
        out.add(rng.choice(["04", "05", "03"]) + "".join(str(rng.randint(0, 9)) for _ in range(5)) + rng.choice("0123456789"))
    return sorted(out)


def _G_rating_points(rng, e1, top_q_scale):
    """A two-control rating as (gh, q, offset) decimal texts."""
    b1 = rng.uniform(1.9, 2.6)
    c1 = rng.uniform(6.0, 40.0) * top_q_scale
    hb = round(e1 + rng.uniform(1.4, 2.2), 1)
    e2 = round(e1 + rng.uniform(0.35, 0.85), 2)
    b2 = rng.uniform(1.35, 1.75)
    c2 = c1 * (hb - e1) ** b1 / (hb - e2) ** b2
    h0 = round(e1 + rng.choice([0.3, 0.4, 0.5]), 1)
    top = round(e1 + rng.uniform(6.5, 8.5), 1)
    hs, h = [], h0
    while h < hb - 1e-9:
        hs.append(round(h, 2))
        h += 0.2
    h = hb
    while h <= top + 1e-9:
        hs.append(round(h, 2))
        h += 0.5
    pts = []
    for h in hs:
        if h < hb - 1e-9:
            q, e = c1 * (h - e1) ** b1, e1
        else:
            q, e = c2 * (h - e2) ** b2, e2
        qs = _Gsig(q, 3)
        if pts and qs <= _Gfr(pts[-1][1]):
            qs = _Gfr(pts[-1][1]) + _GF(1, 10) ** max(0, 2 - _Gmag(qs))
        pts.append((f"{h:.2f}", _Gtxt(qs), f"{e:.2f}"))
    return pts


def _G_rq(points, h):
    """Float rating evaluation over (gh, q, offset) float triples (handbook H10)."""
    n = len(points)
    for hi, qi, ei in points:
        if h == hi:
            return qi
    if h < points[0][0]:
        h0, q0, e0 = points[0]
        h1, q1, _ = points[1]
        if h <= e0:
            return 0.0
        beta = _Gmath.log(q1 / q0) / _Gmath.log((h1 - e0) / (h0 - e0))
        return q0 * ((h - e0) / (h0 - e0)) ** beta
    i = n - 2
    for k in range(n - 1):
        if points[k][0] <= h < points[k + 1][0]:
            i = k
            break
    hi, qi, ei = points[i]
    hj, qj, _ = points[i + 1]
    beta = _Gmath.log(qj / qi) / _Gmath.log((hj - ei) / (hi - ei))
    return qi * ((h - ei) / (hi - ei)) ** beta


def _G_rinv(points, q):
    """Float inverse of the rating (handbook H10)."""
    n = len(points)
    for hi, qi, ei in points:
        if q == qi:
            return hi
    if q < points[0][1]:
        i = 0
    else:
        i = n - 2
        for k in range(n - 1):
            if points[k][1] <= q < points[k + 1][1]:
                i = k
                break
    hi, qi, ei = points[i]
    hj, qj, _ = points[i + 1]
    beta = _Gmath.log(qj / qi) / _Gmath.log((hj - ei) / (hi - ei))
    return ei + (hi - ei) * (q / qi) ** (1.0 / beta)


def _Gfpts(points):
    return [(float(h), float(q), float(e)) for h, q, e in points]


def _G_world(seed, cfg):  # noqa: C901
    rng = _G_rng(seed, "world")
    W = {"cfg": cfg, "seed": seed}
    clock = {"std": int(cfg["std_offset"]), "rule": cfg["dst_rule"]}
    W["clock"] = clock
    ps, pe = _Gdate_of(cfg["period_start"]), _Gdate_of(cfg["period_end"])
    W["ps"], W["pe"] = ps, pe
    W["pstart"] = _Gday_utc(ps) - clock["std"] * 60
    W["pend"] = _Gday_utc(pe) - clock["std"] * 60
    W["ws"] = W["pstart"] - int(cfg["margin_h"]) * 3600
    W["we"] = W["pend"] + int(cfg["margin_h"]) * 3600
    ids = _G_station_ids(rng, 200)
    rng.shuffle(ids)
    scope = sorted(ids[: cfg["n_sites"]])
    rivers = list(_GRIVERS)
    rng.shuffle(rivers)
    stations = []
    for k, sid in enumerate(ids):
        river = rivers[k % len(rivers)]
        place, code = _GPLACES[(k * 7 + rng.randint(0, 13)) % len(_GPLACES)]
        if sid in scope:
            net, status = cfg["network"], "ACTIVE"
        else:
            u = rng.random()
            net = cfg["network"] if u < 0.12 else rng.choice([n for n in _GNETS if n != cfg["network"]])
            status = "INACTIVE" if net == cfg["network"] else rng.choice(["ACTIVE", "ACTIVE", "ACTIVE", "DISCONTINUED"])
        stations.append({"id": sid, "name": f"{river} {place}", "short": f"{river.split()[0][:5].upper()}-{code}", "network": net,
                         "status": status, "area_km2": _Gtxt(_Gq(_GF(rng.randint(150, 480000), 100), 1)),
                         "area_mi2": _Gtxt(_Gq(_GF(rng.randint(60, 185000), 100), 1)), "drift_tol": rng.choice(["0.02", "0.03", "0.01", "0.02"])})
    W["stations"] = stations
    W["station"] = {s["id"]: s for s in stations}
    shorts = set()
    for s in stations:
        while s["short"] in shorts:
            s["short"] = s["short"] + rng.choice("ABCDEFGH")
        shorts.add(s["short"])
    W["scope"] = scope
    sites = []
    backup_ids = set(rng.sample(scope, cfg["n_backup"]))
    new_ids = set(rng.sample(scope, cfg["n_new_rating"]))
    ice_ids = set(rng.sample(scope, cfg["ice_sites"]))
    top_id = rng.choice([s for s in scope if s not in ice_ids]) if cfg["above_top_site"] else None
    low_id = rng.choice([s for s in scope if s not in ice_ids and s != top_id]) if cfg["low_flow_site"] else None
    for sid in scope:
        st = W["station"][sid]
        site = {"id": sid, "name": st["name"], "short": st["short"], "interval": rng.choice([900, 900, 900, 1800]),
                "backup": sid in backup_ids, "ice": sid in ice_ids, "low": sid == low_id, "top": sid == top_id}
        e1 = round(rng.uniform(0.6, 2.4), 2)
        scale = rng.choice([0.3, 1.0, 2.5, 6.0])
        base_no = rng.randint(8, 22)
        v1 = {"id": f"{sid}-R{base_no:02d}", "site": sid, "points": _G_rating_points(rng, e1, scale), "status": "ACTIVE",
              "eff_u": W["ws"] - rng.randint(40, 300) * 86400 + rng.choice([8, 9, 10, 13]) * 3600}
        versions = [v1]
        if sid in new_ids:
            eff = W["pstart"] + rng.randint(25, 70) * 86400 + rng.choice([7, 8, 11, 14]) * 3600 + rng.choice([0, 1800])
            e1b = round(e1 + rng.uniform(-0.06, 0.09), 2)
            sub = _G_rng(seed, f"rate2:{sid}")
            v2 = {"id": f"{sid}-R{base_no + 1:02d}", "site": sid, "points": _G_rating_points(sub, e1b, scale), "status": "ACTIVE", "eff_u": eff}
            versions.append(v2)
        site["versions"] = versions
        site["fpts"] = {v["id"]: _Gfpts(v["points"]) for v in versions}
        sites.append(site)
    W["sites"] = sites
    W["site"] = {s["id"]: s for s in sites}
    for s in sites:
        for v in s["versions"]:
            old = []
            for h, q, e in v["points"]:
                old.append((h, _Gtxt(_Gsig(_Gfr(q) * _GF(rng.uniform(0.93, 1.06)), 3)), e))
            for k in range(1, len(old)):
                if _Gfr(old[k][1]) <= _Gfr(old[k - 1][1]):
                    old[k] = (old[k][0], _Gtxt(_Gfr(old[k - 1][1]) + 1), old[k][2])
            v["old_points"] = old
    W["withdrawn_versions"], W["draft_versions"] = [], []
    for kind, num_add, lo, hi, spread in (("WITHDRAWN", 1, 10, 80, 0.1), ("DRAFT", 5, 5, 60, 0.15)):
        for s in rng.sample(sites, 2):
            v = s["versions"][-1]
            num = int(v["id"].rsplit("R", 1)[1]) + num_add
            pts = [(h, _Gtxt(_Gsig(_Gfr(q) * _GF(rng.uniform(1 - spread, 1 + spread)), 3)), e) for h, q, e in v["points"]]
            for k in range(1, len(pts)):
                if _Gfr(pts[k][1]) <= _Gfr(pts[k - 1][1]):
                    pts[k] = (pts[k][0], _Gtxt(_Gfr(pts[k - 1][1]) + 1), pts[k][2])
            rec = {"id": f"{s['id']}-R{num:02d}", "site": s["id"], "points": pts, "status": kind,
                   "eff_u": W["pstart"] + rng.randint(lo, hi) * 86400 + (9 if kind == "WITHDRAWN" else 10) * 3600}
            (W["withdrawn_versions"] if kind == "WITHDRAWN" else W["draft_versions"]).append(rec)
    # site overlay: per-site settings that win over the workbook site sheet and the profile
    ov = {}
    for sid in rng.sample(scope, 2):
        ov[sid] = {"drift_tolerance_ft": rng.choice(["0.03", "0.01", "0.04"])}
    if cfg["overlay_gap_site"]:
        cand = [s["id"] for s in sites if s["interval"] == 1800] or [sites[0]["id"]]
        ov.setdefault(rng.choice(cand), {})["max_gap_minutes"] = 90
    W["overlay"] = ov
    free = [sid for sid in scope if "drift_tolerance_ft" not in ov.get(sid, {})]
    W["station"][rng.choice(free)]["drift_tol"] = ""
    W["overlay_other"] = {s["id"]: {"drift_tolerance_ft": rng.choice(["0.05", "0.03"]), "max_gap_minutes": rng.choice([45, 120])}
                          for s in rng.sample([x for x in stations if x["id"] not in scope], 45)}
    return W


def _G_version_at(site, u):
    best = None
    for v in site["versions"]:
        if v["eff_u"] <= u and (best is None or v["eff_u"] > best["eff_u"]):
            best = v
    return best
# ---------------------------------------------------------------------------- hydrology timeline
def _G_lin(knots, t):
    if t <= knots[0][0]:
        return knots[0][1]
    for (a, va), (b, vb) in zip(knots, knots[1:]):
        if a <= t < b:
            return va + (vb - va) * (t - a) / (b - a)
    return knots[-1][1]


def _G_qtrue(p, t, std):
    x = (t - p["t0"]) / 86400.0
    q = p["base"] * (p["floor"] + (1 - p["floor"]) * _Gmath.exp(-max(x, 0.0) / p["tau"]))
    for tk, amp, tp, a in p["events"]:
        dx = (t - tk) / 3600.0
        if dx > 0:
            q += amp * (dx / tp) ** a * _Gmath.exp(a * (1 - dx / tp))
    if t > p["melt0"]:
        frac = min(1.0, (t - p["melt0"]) / (10 * 86400.0))
        hour = ((t + std * 60) % 86400) / 3600.0
        q += p["melt"] * frac * (0.6 + 0.4 * _Gmath.sin(2 * _Gmath.pi * (hour - 9) / 24))
    return q


def _G_in(periods, t):
    for a, b in periods:
        if a <= t and (b is None or t < b):
            return True
    return False


def _G_ktrue(site, t):
    for (a, b), knots in zip(site["ice_true"], site["k_knots"]):
        if a <= t and (b is None or t < b):
            return _G_lin(knots, t)
    return 1.0


def _G_hopen(W, site, t):
    v = _G_version_at(site, t)
    if site["low"] and site.get("dry") and site["dry"][0] <= t < site["dry"][1]:
        return site["fpts"][v["id"]][0][2] - 0.04 - _G_lin(site["s_true"][v["id"]], t)
    q = _G_qtrue(site["hp"], t, W["clock"]["std"]) / _G_ktrue(site, t)
    return _G_rinv(site["fpts"][v["id"]], q) - _G_lin(site["s_true"][v["id"]], t)


def _G_daytime(t, std, rng, lo_h, hi_h, step=300):
    """t moved to a random LST clock time between lo_h and hi_h of its LST day."""
    t = t - (t + std * 60) % 86400
    return t + rng.randint(lo_h * 3600 // step, hi_h * 3600 // step) * step


def _G_timeline(W, rng):  # noqa: C901
    std = W["clock"]["std"]
    ws, we, p0 = W["ws"], W["we"], W["pstart"]
    for site in W["sites"]:
        pts = site["fpts"][site["versions"][0]["id"]]
        n = len(pts)
        base = pts[max(1, int(n * rng.uniform(0.18, 0.4)))][1]
        if site["low"]:
            base = pts[0][1] * 1.3
        hp = {"t0": ws, "base": base, "floor": rng.uniform(0.45, 0.75), "tau": rng.uniform(25, 70), "events": [],
              "melt0": p0 + rng.randint(72, 84) * 86400, "melt": base * rng.uniform(0.2, 0.7)}
        if site["low"]:
            hp["floor"], hp["melt"] = 0.55, base * 0.1
        for _ in range(rng.randint(2, 4)):
            tk = p0 + rng.randint(28, 86) * 86400 + rng.randint(0, 23) * 3600
            amp = base * (rng.uniform(0.1, 0.3) if site["low"] else rng.uniform(0.6, 2.8))
            hp["events"].append((tk, amp, rng.uniform(6, 20), rng.uniform(2.0, 3.0)))
        if site["top"]:
            hp["events"].append((p0 + rng.randint(60, 78) * 86400 + 6 * 3600, pts[-1][1] * 1.3, 10.0, 2.5))
        site["hp"] = hp
        if site["low"]:
            a = p0 + rng.randint(40, 70) * 86400 + rng.randint(0, 23) * 3600
            site["dry"] = (a, a + rng.randint(8, 30) * 3600)
        ice = []
        if site["ice"]:
            on = p0 + rng.randint(-6, 9) * 86400 + rng.randint(0, 95) * 900
            off = p0 + rng.randint(38, 62) * 86400 + rng.randint(0, 95) * 900
            ice.append((on, off))
            if rng.random() < 0.6:
                on2 = off + rng.randint(6, 12) * 86400 + rng.randint(0, 95) * 900
                off2 = on2 + rng.randint(3, 9) * 86400 + rng.randint(0, 95) * 900
                ice.append((on2, off2 if off2 < we - 86400 else None))
        if ice and W["cfg"]["open_ice"] and not any(s.get("ice_true") and s["ice_true"][-1][1] is None for s in W["sites"]):
            ice[-1] = (ice[-1][0], None)
        site["ice_true"] = ice
        site["k_knots"] = []
        for a, b in ice:
            bb = b if b is not None else we
            site["k_knots"].append([(a, rng.uniform(0.8, 0.95)), ((a + bb) / 2, rng.uniform(0.5, 0.75)), (bb, rng.uniform(0.75, 0.92))])
        site["s_true"] = {}
        for k, v in enumerate(site["versions"]):
            start = v["eff_u"]
            end = site["versions"][k + 1]["eff_u"] if k + 1 < len(site["versions"]) else we + 30 * 86400
            knots, t, val = [(start, 0.0)], start, 0.0
            while t < end:
                t += rng.randint(12, 24) * 86400
                val = max(-0.18, min(0.18, val + rng.uniform(-0.1, 0.1)))
                knots.append((t, val))
            site["s_true"][v["id"]] = knots
    _G_visits(W, rng)
    _G_readings(W, rng)


def _G_visits(W, rng):  # noqa: C901
    cfg = W["cfg"]
    std = W["clock"]["std"]
    vid = 1000 + rng.randint(0, 400)
    W["visits"] = []
    tie_sites = set(rng.sample([s["id"] for s in W["sites"]], cfg["err_tie"]))
    for site in W["sites"]:
        t = _G_daytime(W["ws"] - rng.randint(4, 14) * 86400, std, rng, 9, 14)
        d0, rate, last_t = 0.0, 0.0, t
        visits = []
        tie_done = site["id"] not in tie_sites
        while True:
            h = _G_hopen(W, site, t)
            drift_here = d0 + rate * (t - last_t) / 86400.0
            display = round(h + drift_here + rng.uniform(-0.003, 0.003), 2)
            tape = round(h, 2)
            action = "RESET" if not visits or rng.random() < 0.8 else "NONE"
            refs = []
            u = rng.random()
            if u < 0.72:
                refs.append(("TAPE", tape))
                if rng.random() < 0.5:
                    refs.append(("WIRE", round(tape + rng.choice([-0.01, 0.01]), 2)))
            elif u < 0.9:
                refs.append(("WIRE", tape))
            refs.append(("STAFF", round(tape + rng.choice([-0.02, -0.01, 0.01, 0.02]), 2)))
            if rng.random() < 0.6:
                refs.append(("CSG", round(tape + rng.uniform(0.2, 1.4), 2)))
            if not tie_done and visits and t > W["pstart"] + 10 * 86400:
                tol = _Gfr(site_tol(W, site["id"]))
                display = float(_Gfr(f"{refs[0][1]:.2f}") - tol * rng.choice([1, -1]))
                tie_done = True
            v = {"vid": vid, "site": site["id"], "t": t, "display": f"{display:.2f}", "action": action,
                 "refs": [(m, f"{x:.2f}") for m, x in refs], "party": rng.choice(["JKL", "MRV", "TSO", "AHB", "PDQ"])}
            d0 = 0.0 if action == "RESET" else drift_here
            rate = rng.uniform(-0.0045, 0.0045)
            last_t = t
            v["_d0"], v["_rate"] = d0, rate
            visits.append(v)
            vid += rng.randint(1, 3)
            if t > W["we"] + 86400:
                break
            t = _G_daytime(t + rng.randint(13, 24) * 86400, std, rng, 9, 15)
            if t > W["we"] and rng.random() < 0.35:
                break
        site["visits"] = visits
        W["visits"].extend(visits)


def site_tol(W, sid):
    """Drift tolerance in force for a site (overlay over workbook site sheet)."""
    ov = W["overlay"].get(sid, {})
    if "drift_tolerance_ft" in ov:
        return ov["drift_tolerance_ft"]
    return W["station"][sid]["drift_tol"] or W["cfg"]["drift_tol"]


def _G_drift(site, t):
    k = None
    for i, v in enumerate(site["visits"]):
        if v["t"] <= t:
            k = i
        else:
            break
    if k is None:
        return 0.0
    v = site["visits"][k]
    return v["_d0"] + v["_rate"] * (t - v["t"]) / 86400.0


def _G_readings(W, rng):  # noqa: C901
    """True logger readings per site: sensor, instant, logger-datum value in feet (float) and quality."""
    cfg = W["cfg"]
    std = W["clock"]["std"]
    ws, we = W["ws"], W["we"]
    sites = W["sites"]
    nonb = [s for s in sites if not s["backup"]]
    # equipment units and datum offsets
    W["equip"], W["datum"] = [], []
    swap_site = rng.choice([s for s in sites if not s["backup"]]) if cfg["unit_swap"] else None
    datum_site = rng.choice([s for s in sites if s is not swap_site]) if cfg["datum_change"] else None
    for s in sites:
        u0 = "M" if s is swap_site else rng.choice(["FT", "FT", "FT", "M"])
        s["unit_tl"] = {"P": [(ws - 400 * 86400, u0)], "B": [(ws - 300 * 86400, rng.choice(["FT", "M"]))]}
        if s is swap_site:
            ts = W["pstart"] + rng.randint(20, 60) * 86400 + rng.randint(30, 60) * 900
            s["unit_tl"]["P"].append((ts, "FT"))
            s["swap_t"] = ts
        o1 = rng.choice(["0.00", "0.00", "-0.50", "1.20", "0.35"])
        s["datum_tl"] = {"P": [(ws - 900 * 86400, o1)], "B": [(ws - 500 * 86400, rng.choice(["0.12", "-0.08", "0.25"]))]}
        if s is datum_site:
            td = W["pstart"] + rng.randint(15, 70) * 86400 + rng.randint(36, 60) * 900
            s["datum_tl"]["P"].append((td, _Gtxt(_Gfr(o1) + _Gfr(rng.choice(["-0.15", "0.22", "-0.30"])), 2)))
            s["datum_t"] = td
    # outages, faults, backup logging windows, midnight gaps
    for s in sites:
        s["out"], s["faults"], s["bwin"], s["mgap"] = [], [], [], set()
    for _ in range(cfg["outages"]):
        s = rng.choice(sites)
        a = W["pstart"] + rng.randint(2, 86) * 86400 + rng.randint(0, 95) * 900
        dur = rng.choice([2, 3, 5, 7, 9, 14, 20, 30]) * 3600
        s["out"].append((a, a + dur))
        if s["backup"]:
            s["bwin"].append((a - 6 * 3600, a + dur + 6 * 3600))
    for s in sites:
        if s["backup"]:
            a = W["pstart"] + rng.randint(5, 60) * 86400
            s["bwin"].append((a, a + rng.randint(6, 14) * 86400))
            if not any(True for _ in s["out"]):
                a = W["pstart"] + rng.randint(10, 80) * 86400 + rng.randint(0, 95) * 900
                s["out"].append((a, a + rng.choice([4, 8, 12]) * 3600))
                s["bwin"].append((a - 3 * 3600, a + 15 * 3600))
    for _ in range(cfg["fault_runs"]):
        s = rng.choice(sites)
        a = W["pstart"] + rng.randint(2, 86) * 86400 + rng.randint(0, 95) * 900
        s["faults"].append((a, a + rng.randint(2, 8) * s["interval"]))
    for _ in range(cfg["midnight_gaps"]):
        s = rng.choice(nonb)
        d = W["ps"] + _Gtd(days=rng.randint(3, (W["pe"] - W["ps"]).days - 3))
        m = _Gday_utc(d) - std * 60
        s["mgap"].add(m)
        if s["interval"] == 900:
            s["mgap"].add(m + 900)
    for sid, ov in W["overlay"].items():
        if "max_gap_minutes" in ov:
            s = W["site"][sid]
            k = int(ov["max_gap_minutes"]) * 60 // s["interval"] - 1
            for _ in range(3):
                a = W["pstart"] + rng.randint(5, 85) * 86400 + rng.randint(1, 40) * 1800
                a -= a % s["interval"]
                for j in range(k):
                    s["mgap"].add(a + (j + 1) * s["interval"])
    W["dead_month"] = None
    if cfg["dead_month"]:
        s = next(x for x in sites if not x["backup"])
        m0 = (W["ps"].replace(day=1) + _Gtd(days=32)).replace(day=1)
        m1 = (m0 + _Gtd(days=32)).replace(day=1)
        s["out"].append((_Gday_utc(m0) - std * 60 - 3600, _Gday_utc(m1) - std * 60 + 3600))
        W["dead_month"] = (s["id"], m0)
    for s in sites:
        recs = []
        step = s["interval"]
        t = ws - ws % step
        if t < ws:
            t += step
        while t < we:
            missing = _G_in(s["out"], t) or t in s["mgap"]
            h = _G_hopen(W, s, t)
            drift = _G_drift(s, t)
            if not missing:
                v = h + drift + rng.uniform(-0.004, 0.004)
                q = "G"
                if _G_in(s["faults"], t):
                    v, q = v + rng.uniform(1.5, 4.0), "X"
                else:
                    u = rng.random()
                    q = "S" if u < 0.01 else "E" if u < 0.013 else "G"
                off = float(_G_tl(s["datum_tl"]["P"], t))
                recs.append({"sensor": "P", "t": t, "vft": v - off, "q": q})
            if s["backup"] and _G_in(s["bwin"], t):
                vb = h + drift + rng.uniform(-0.006, 0.006) - float(_G_tl(s["datum_tl"]["B"], t))
                recs.append({"sensor": "B", "t": t, "vft": vb, "q": "G" if rng.random() < 0.98 else "S"})
            t += step
        s["recs"] = recs


def _G_tl(tl, t):
    """Value of a (from, value) timeline in force at instant t."""
    best = tl[0][1]
    for a, val in tl:
        if a <= t:
            best = val
    return best


def _G_value_text(vft, unit):
    f = _GF(vft).limit_denominator(10 ** 9) * _GUNIT_DIV[unit]
    return _Gtxt(_Gq(f, _GUNIT_RES[unit]), _GUNIT_RES[unit])
# ---------------------------------------------------------------------------- measurements, ice, edits
def _G_measurements(W, rng):  # noqa: C901
    cfg = W["cfg"]
    std = W["clock"]["std"]
    W["meas"], W["meas_late"] = [], []
    mno = 4100 + rng.randint(0, 600)
    norec_done = False
    for site in W["sites"]:
        n = cfg["meas_per_site"] + cfg["extra_meas"]
        span = (W["pend"] - W["pstart"] - 6 * 86400) / n
        slots = []
        for k in range(n):
            t = int(W["pstart"] + 3 * 86400 + span * k + rng.uniform(0, span * 0.6))
            slots.append(_G_daytime(t, std, rng, 9, 14))
        if not norec_done and not site["backup"] and site["out"]:
            a, b = site["out"][0]
            if b - a >= 3 * 3600:
                slots.append(a + 1800 - a % 300)
                norec_done = True
        for start in sorted(slots):
            dur = rng.choice([20, 25, 30, 40, 45, 55, 60, 75]) * 60
            if site.get("dry") and site["dry"][0] - 2 * 86400 <= start < site["dry"][1] + 2 * 86400:
                start = site["dry"][1] + 3 * 86400 - (site["dry"][1] + 3 * 86400) % 300
            if any(a <= start < b for a, b in site["out"]):
                dur = 30 * 60
            end = start + dur
            mid = start + dur // 2
            mid -= mid % 60
            ice = _G_in(site["ice_true"], mid)
            qt = _G_qtrue(site["hp"], mid, std)
            q = _Gsig(qt * (1 + rng.gauss(0, 0.04)), 4)
            grade = rng.choices("EGFP", weights=[1, 5, 3, 1])[0]
            cover = "ICE" if ice else "OPEN"
            if rng.random() < 0.08:
                cover = "SLUSH" if ice else "ICE"
            fgh = round(_G_hopen(W, site, mid) + rng.uniform(-0.04, 0.04), 2)
            m = {"no": mno, "site": site["id"], "start": start, "end": end, "q": q, "grade": grade, "cover": cover,
                 "field_gh": f"{fgh:.2f}", "entered": end + rng.randint(2, 40) * 3600, "method": rng.choice(["ADCP", "AA-METER", "ADV", "FLUME"]),
                 "party": rng.choice(["JKL", "MRV", "TSO", "AHB", "PDQ"]), "cms": False}
            mno += rng.randint(1, 4)
            W["meas"].append(m)
    # late re-entries: corrected discharge in m3/s, mostly entered later than the main file
    inscope = list(W["meas"])
    for m in rng.sample(inscope, min(8, len(inscope))):
        late = dict(m)
        late["q"] = _Gsig(m["q"] * _GF(rng.uniform(0.95, 1.05)) * _GUNIT_DIV["M"] ** 3, 4) / (_GUNIT_DIV["M"] ** 3)
        late["cms"] = True
        late["entered"] = m["entered"] + rng.randint(1, 20) * 86400
        if rng.random() < 0.25:
            late["entered"] = m["entered"] - rng.randint(1, 10) * 3600
        W["meas_late"].append(late)
    for site in rng.sample(W["sites"], 3):
        start = _G_daytime(W["pstart"] + rng.randint(10, 80) * 86400, std, rng, 9, 14)
        if site.get("dry") and site["dry"][0] - 2 * 86400 <= start < site["dry"][1] + 2 * 86400:
            start += 6 * 86400
        dur = 40 * 60
        mid = start + dur // 2
        mid -= mid % 60
        qt = _G_qtrue(site["hp"], mid, std)
        q = _Gsig(qt * (1 + rng.gauss(0, 0.04)) * float(_GUNIT_DIV["M"] ** 3), 4) / (_GUNIT_DIV["M"] ** 3)
        late = {"no": mno, "site": site["id"], "start": start, "end": start + dur, "q": q, "grade": rng.choice("GF"),
                "cover": "ICE" if _G_in(site["ice_true"], mid) else "OPEN", "field_gh": f"{round(_G_hopen(W, site, mid), 2):.2f}",
                "entered": start + 5 * 86400, "method": "ADCP", "party": "LATE", "cms": True}
        mno += 2
        W["meas_late"].append(late)
    W["meas_next"] = mno
    # out-of-scope measurements (ignored by scope)
    others = [s for s in W["stations"] if s["id"] not in W["site"]]
    W["meas_other"] = []
    for k in range(200 + cfg["extra_meas"] * 5):
        st = rng.choice(others)
        start = _G_daytime(W["pstart"] + rng.randint(0, 88) * 86400, std, rng, 8, 15)
        W["meas_other"].append({"no": mno + k * 3, "site": st["id"], "start": start, "end": start + rng.choice([30, 45, 60]) * 60,
                                "q": _Gsig(_GF(rng.uniform(3, 4000)), 4), "grade": rng.choice("EGFP"), "cover": rng.choice(["OPEN", "ICE"]),
                                "field_gh": f"{rng.uniform(1, 9):.2f}", "entered": start + 86400, "method": "ADCP", "party": "EXT", "cms": False})


def _G_icelog(W, rng):  # noqa: C901
    cfg = W["cfg"]
    entries = []
    std = W["clock"]["std"]
    raw = []  # (kind, site, at) in replay intent order with optional amend/withdraw follow-ups

    def add(e):
        entries.append(e)
        return e
    no = [300 + rng.randint(0, 50)]

    def nxt():
        no[0] += rng.randint(1, 3)
        return no[0]
    for site in W["sites"]:
        for a, b in site["ice_true"]:
            if rng.random() < 0.35:
                e = add({"entry": nxt(), "site": site["id"], "kind": "ON", "at": a + rng.choice([-3, -2, 2, 4, 6]) * 3600})
                raw.append(("AMEND", e, a))
            else:
                add({"entry": nxt(), "site": site["id"], "kind": "ON", "at": a})
            if b is not None:
                if rng.random() < 0.25:
                    e = add({"entry": nxt(), "site": site["id"], "kind": "OFF", "at": b + rng.choice([-5, -1, 3]) * 3600})
                    raw.append(("AMEND", e, b))
                else:
                    add({"entry": nxt(), "site": site["id"], "kind": "OFF", "at": b})
    # a spurious pair at one ice site during a thaw, later withdrawn
    ice_sites = [s for s in W["sites"] if s["ice"]]
    for site in rng.sample(ice_sites, min(2, len(ice_sites))):
        a, b = site["ice_true"][0]
        t = (b if b is not None else W["we"]) + rng.randint(1, 4) * 86400
        if len(site["ice_true"]) > 1 and t >= site["ice_true"][1][0]:
            t = b + 86400
        e1 = add({"entry": nxt(), "site": site["id"], "kind": "ON", "at": t})
        e2 = add({"entry": nxt(), "site": site["id"], "kind": "OFF", "at": t + rng.randint(10, 30) * 3600})
        raw.append(("WITHDRAW", e1, None))
        raw.append(("WITHDRAW", e2, None))
    for k in range(cfg["extra_ice_amend"]):
        site = rng.choice(ice_sites)
        a, b = site["ice_true"][0]
        e = add({"entry": nxt(), "site": site["id"], "kind": "ON", "at": a - rng.randint(1, 5) * 3600})
        raw.append(("AMEND", e, a))
    rng.shuffle(raw)
    for kind, e, at in raw:
        if kind == "AMEND":
            if rng.random() < 0.3:
                add({"entry": nxt(), "kind": "AMEND", "target": e["entry"], "at": at + 3600})
            add({"entry": nxt(), "kind": "AMEND", "target": e["entry"], "at": at})
        else:
            add({"entry": nxt(), "kind": "WITHDRAW", "target": e["entry"]})
    # entries of other stations and an amend of an unknown entry
    others = [s for s in W["stations"] if s["id"] not in W["site"]]
    for k in range(175):
        st = rng.choice(others)
        add({"entry": nxt(), "site": st["id"], "kind": rng.choice(["ON", "OFF"]), "at": W["pstart"] + rng.randint(-20, 85) * 86400 + rng.randint(0, 95) * 900})
    add({"entry": nxt(), "kind": "AMEND", "target": 17, "at": W["pstart"] + 86400})
    W["icelog"] = entries


def _G_ice_replay(entries):
    """Ice periods per site after replaying the observation log in entry order (handbook H13)."""
    ev = {}
    for e in sorted(entries, key=lambda x: x["entry"]):
        if e["kind"] in ("ON", "OFF"):
            ev[e["entry"]] = {"site": e["site"], "kind": e["kind"], "at": e["at"], "entry": e["entry"]}
        elif e["kind"] == "AMEND":
            if e["target"] in ev:
                ev[e["target"]]["at"] = e["at"]
        elif e["kind"] == "WITHDRAW":
            ev.pop(e["target"], None)
    per = {}
    for x in ev.values():
        per.setdefault(x["site"], []).append(x)
    out = {}
    for sid, xs in per.items():
        xs.sort(key=lambda x: (x["at"], x["entry"]))
        periods, cur = [], None
        for x in xs:
            if x["kind"] == "ON" and cur is None:
                cur = x
            elif x["kind"] == "OFF" and cur is not None:
                periods.append((cur["at"], x["at"], cur["entry"], x["entry"]))
                cur = None
        if cur is not None:
            periods.append((cur["at"], None, cur["entry"], None))
        out[sid] = periods
    return out


def _G_edits(W, rng):  # noqa: C901
    cfg = W["cfg"]
    edits = []
    seq = [10 + rng.randint(0, 30)]

    def nxt():
        seq[0] += rng.randint(1, 4)
        return seq[0]
    std = W["clock"]["std"]
    keyed = []
    for s in W["sites"]:
        for r in s["recs"]:
            if W["pstart"] <= r["t"] < W["pend"]:
                keyed.append((s, r))
    for k in range(cfg["edits"]):
        s, r = rng.choice(keyed)
        pat = rng.choices(["SET", "DEL", "DELRES", "DELSET", "RES", "DRD", "SETX", "MISS"], weights=[30, 16, 16, 6, 6, 6, 8, 6])[0]
        unit = rng.choice(["FT", "FT", "M"])
        if pat == "SETX":
            xs = [(s2, r2) for s2, r2 in keyed if r2["q"] == "X"]
            if xs:
                s, r = rng.choice(xs)
            pat = "SET"
        if pat == "MISS":
            t = r["t"] + s["interval"] // 3 * 2 // 60 * 60
            edits.append({"seq": nxt(), "site": s["id"], "sensor": r["sensor"], "t": t, "op": "SET", "value": _G_value_text(r["vft"], unit), "unit": unit})
            continue
        v2 = r["vft"] + rng.choice([-1, 1]) * rng.uniform(0.02, 0.15)
        if pat == "SET":
            edits.append({"seq": nxt(), "site": s["id"], "sensor": r["sensor"], "t": r["t"], "op": "SET", "value": _G_value_text(v2, unit), "unit": unit})
        elif pat == "DEL":
            edits.append({"seq": nxt(), "site": s["id"], "sensor": r["sensor"], "t": r["t"], "op": "DELETE"})
        elif pat == "DELRES":
            edits.append({"seq": nxt(), "site": s["id"], "sensor": r["sensor"], "t": r["t"], "op": "DELETE"})
            edits.append({"seq": nxt(), "site": s["id"], "sensor": r["sensor"], "t": r["t"], "op": "RESTORE"})
        elif pat == "DELSET":
            edits.append({"seq": nxt(), "site": s["id"], "sensor": r["sensor"], "t": r["t"], "op": "DELETE"})
            edits.append({"seq": nxt(), "site": s["id"], "sensor": r["sensor"], "t": r["t"], "op": "SET", "value": _G_value_text(v2, unit), "unit": unit})
        elif pat == "RES":
            edits.append({"seq": nxt(), "site": s["id"], "sensor": r["sensor"], "t": r["t"], "op": "RESTORE"})
        else:
            edits.append({"seq": nxt(), "site": s["id"], "sensor": r["sensor"], "t": r["t"], "op": "SET", "value": _G_value_text(v2, unit), "unit": unit})
            edits.append({"seq": nxt(), "site": s["id"], "sensor": r["sensor"], "t": r["t"], "op": "DELETE"})
            edits.append({"seq": nxt(), "site": s["id"], "sensor": r["sensor"], "t": r["t"], "op": "RESTORE"})
            edits.append({"seq": nxt(), "site": s["id"], "sensor": r["sensor"], "t": r["t"], "op": "DELETE"})
    others = [x for x in W["stations"] if x["id"] not in W["site"]]
    for k in range(140):
        st = rng.choice(others)
        edits.append({"seq": nxt(), "site": st["id"], "sensor": "P", "t": W["pstart"] + rng.randint(0, 89) * 86400 + rng.randint(0, 95) * 900,
                      "op": rng.choice(["SET", "DELETE"]), "value": f"{rng.uniform(1, 9):.2f}", "unit": "FT"})
    for e in edits:
        if e["op"] != "SET":
            e.pop("value", None)
            e.pop("unit", None)
    W["edits"] = edits


# ---------------------------------------------------------------------------- aliases
def _G_aliases(W, rng):  # noqa: C901
    cfg = W["cfg"]
    rows, add_rows = [], []
    far = "2009-06-01T00:00:00Z"
    W["tok"] = {}
    legacy_n = 100 + rng.randint(0, 50)
    for st in W["stations"]:
        sid = st["id"]
        toks = {"canon": [sid], "strip": [sid.lstrip("0") or sid], "lower": [sid]}
        rows.append({"token": "CB" + sid, "target": sid, "from": far, "to": "", "kind": "PREFIX"})
        toks["cb"] = ["CB" + sid, "cb" + sid]
        rows.append({"token": st["short"], "target": sid, "from": far, "to": "", "kind": "SHORT"})
        chain = st["short"].replace("-", "")
        rows.append({"token": chain, "target": st["short"], "from": far, "to": "", "kind": "CHAIN"})
        toks["short"] = [st["short"], st["short"].lower()]
        toks["chain"] = [chain]
        legacy_n += rng.randint(1, 3)
        lt = f"L-{legacy_n}"
        rows.append({"token": lt, "target": sid, "from": far, "to": "", "kind": "LEGACY"})
        toks["legacy"] = [lt]
        W["tok"][sid] = toks
    # one legacy token reassigned to another in-scope site part way through the record
    W["switch"] = None
    if cfg["alias_switch"]:
        a, b = rng.sample(W["sites"], 2)
        ts = W["pstart"] + rng.randint(20, 60) * 86400 + rng.randint(0, 23) * 3600
        lt = W["tok"][a["id"]]["legacy"][0]
        for r in rows:
            if r["token"] == lt:
                r["to"] = _Giso(ts)
        rows.append({"token": lt, "target": b["id"], "from": _Giso(ts), "to": "", "kind": "LEGACY"})
        W["switch"] = (lt, a["id"], b["id"], ts)
    # addendum: a corrected target for one register row and new spellings
    c, d = rng.sample([s for s in W["sites"] if not W["switch"] or s["id"] not in W["switch"][1:3]], 2)
    fix_tok = f"L-{legacy_n + 7}"
    rows.append({"token": fix_tok, "target": c["id"], "from": "2018-03-01T00:00:00Z", "to": "", "kind": "LEGACY"})
    add_rows.append({"token": fix_tok, "target": d["id"], "from": "2018-03-01T00:00:00Z", "to": "", "kind": "LEGACY", "note": "target corrected"})
    W["fix_alias"] = (fix_tok, c["id"], d["id"])
    for s in W["sites"]:
        sp = s["short"].replace("-", " ")
        frm = W["pstart"] + rng.randint(-30, 20) * 86400
        add_rows.append({"token": sp, "target": s["id"], "from": _Giso(frm), "to": "", "kind": "SPACED", "note": "new spelling"})
        W["tok"][s["id"]]["spaced"] = [(sp, frm)]
    others = [x for x in W["stations"] if x["id"] not in W["site"]]
    for st in rng.sample(others, 190):
        add_rows.append({"token": st["short"].replace("-", "_"), "target": st["id"], "from": _Giso(W["pstart"] - rng.randint(0, 400) * 86400),
                         "to": "", "kind": "UNDERSCORE", "note": "export spelling"})
    W["long_chain"] = None
    if cfg["long_chain"]:
        s = W["sites"][0]
        prev, chain = s["id"], []
        for k in range(1, 8):
            tok = f"LK{k}-{s['id'][-4:]}"
            rows.append({"token": tok, "target": prev, "from": far, "to": "", "kind": "CHAIN"})
            chain.append(tok)
            prev = tok
        W["long_chain"] = (s["id"], chain[5], chain[6])
    W["aliases"], W["alias_add"] = rows, add_rows


def _Giso(u):
    return _Gnaive(u).strftime("%Y-%m-%dT%H:%M:%SZ")


def _Gparse_iso(text):
    text = text.strip()
    if text.endswith("Z"):
        return _Gparse_naive(text[:-1])
    base, sign, off = text[:-6], text[-6], text[-5:]
    m = int(off[:2]) * 60 + int(off[3:])
    return _Gparse_naive(base) - (m if sign == "+" else -m) * 60


def _G_norm_token(tok):
    t = str(tok).strip().upper()
    if t.isdigit() and len(t) < 8:
        t = t.zfill(8)
    return t


def _G_resolver(W):
    """token, UTC instant -> canonical station id or None (handbook H4)."""
    rows = {}
    for r in W["aliases"]:
        rows[(_G_norm_token(r["token"]), r["from"])] = r
    for r in W["alias_add"]:
        rows[(_G_norm_token(r["token"]), r["from"])] = r
    by_tok = {}
    for (tok, _), r in rows.items():
        by_tok.setdefault(tok, []).append((_Gparse_iso(r["from"]), _Gparse_iso(r["to"]) if r["to"] else None, _G_norm_token(r["target"])))
    known = W["station"]
    cache = {}

    def resolve(tok, u):
        key = (tok, u)
        if key in cache:
            return cache[key]
        t = _G_norm_token(tok)
        hops = 0
        while t not in known and hops < 6:
            nxt_t = None
            for a, b, tgt in by_tok.get(t, []):
                if a <= u and (b is None or u < b):
                    nxt_t = tgt
            if nxt_t is None:
                cache[key] = None
                return None
            t, hops = nxt_t, hops + 1
        cache[key] = t if t in known else None
        return cache[key]
    return resolve
# ---------------------------------------------------------------------------- shards and catalog
_GLAYOUTS = [
    ("L01", "lg_7q2k.csv", {"void": 1, "q": 1, "sensor": "PB", "unit": "reg", "tok": ["canon", "strip", "cb"]}),
    ("L02", "hx_31mw.csv", {"void": 0, "q": 0, "sensor": "P", "unit": "row", "tok": ["canon", "short"]}),
    ("L03", "rf_08tn.tsv", {"void": 1, "q": 1, "sensor": "PB", "unit": "rec", "tok": ["canon", "short", "chain"]}),
    ("L04", "pw_52dx.tsv", {"void": 0, "q": 1, "sensor": "PB", "unit": "reg", "tok": ["short", "canon"]}),
    ("L05", "vk_19cs.psv", {"void": 1, "q": 1, "sensor": "PB", "unit": "CM", "tok": ["canon", "strip"]}),
    ("L06", "jm_66ra.psv", {"void": 0, "q": 1, "sensor": "P", "unit": "suffix", "tok": ["legacy", "canon", "cb"]}),
    ("L07", "tq_40ub.jsonl", {"void": 1, "q": 1, "sensor": "PB", "unit": "rec", "tok": ["canon", "lower", "spaced"]}),
    ("L08", "ob_27ge.jsonl", {"void": 1, "q": 1, "sensor": "PB", "unit": "rec", "tok": ["cb", "short"]}),
    ("L09", "cz_83hp.ndjson", {"void": 0, "q": 0, "sensor": "P", "unit": "row", "tok": ["canon", "strip"]}),
    ("L10", "ue_14ko.ndjson", {"void": 1, "q": 1, "sensor": "B", "unit": "M", "tok": ["canon", "short"]}),
    ("L11", "kd_58zy.xml", {"void": 1, "q": 1, "sensor": "PB", "unit": "reg", "tok": ["canon", "legacy"]}),
    ("L12", "ny_92fa.xml", {"void": 0, "q": 1, "sensor": "P", "unit": "rec", "tok": ["canon", "short"]}),
    ("L13", "fw_36lc.txt", {"void": 0, "q": 1, "sensor": "P", "unit": "rec", "tok": ["canon", "strip"]}),
    ("L14", "pr_71ev.txt", {"void": 1, "q": 1, "sensor": "PB", "unit": "suffix", "tok": ["canon", "chain", "cb"]}),
    ("L15", "yb_45wt.yaml", {"void": 0, "q": 1, "sensor": "PB", "unit": "block", "tok": ["short", "canon"]}),
    ("L16", "qs_63nb.yml", {"void": 0, "q": 0, "sensor": "P", "unit": "rec", "tok": ["canon"]}),
    ("L17", "ma_29vo.json", {"void": 0, "q": 0, "sensor": "PB", "unit": "meta", "tok": ["canon", "cb"]}),
    ("L18", "ix_50gj.sqlite", {"void": 1, "q": 1, "sensor": "PB", "unit": "rec", "tok": ["canon", "short", "legacy"]}),
    ("L19", "ws_17hm.db", {"void": 1, "q": 1, "sensor": "PB", "unit": "MM", "tok": ["canon", "strip"]}),
    ("L20", "zz_04rt.csv", {"void": 0, "q": 0, "sensor": "P", "unit": "FT", "tok": ["canon"]}),
]
_GLAY = {L[1]: L for L in _GLAYOUTS}
_GARCHIVED = ["lg_6p1m.csv", "kd_31tq.xml"]


def _G_pick_token(W, sid, style, t):
    tk = W["tok"][sid]
    if style == "legacy":
        lt = tk["legacy"][0]
        if W["switch"] and lt == W["switch"][0]:
            a, b, ts = W["switch"][1], W["switch"][2], W["switch"][3]
            if (sid == a and t < ts) or (sid == b and t >= ts):
                return lt
            return sid
        if W["fix_alias"][0] == lt:
            return sid
        return lt
    if style == "spaced":
        sp, frm = tk["spaced"][0]
        return sp if t >= frm else sid
    if style == "lower":
        return W["station"][sid]["short"].lower()
    return tk[style][0]


def _G_shards(W, rng):  # noqa: C901
    cfg = W["cfg"]
    files = {L[1]: [] for L in _GLAYOUTS}
    seen = set()
    routes = []
    active = [L[1] for L in _GLAYOUTS if L[0] not in ("L10", "L20")]
    pcap = [f for f in active if "P" in _GLAY[f][2]["sensor"]]
    regu = [f for f in pcap if _GLAY[f][2]["unit"] == "reg" and _GLAY[f][2]["q"]]
    load = {f: 0 for f in files}
    W["chunk_file"] = {}

    def emit(f, sid, r, rev=1, void=False, vft=None, style=None, q=None):
        caps = _GLAY[f][2]
        q = r["q"] if q is None else q
        if not caps["q"]:
            if q == "X":
                return False
            q = "G"
        key = (f, sid, r["sensor"], r["t"], rev)
        if key in seen:
            return False
        seen.add(key)
        st = W["site"].get(sid)
        if style is None:
            style = W["style"].setdefault((f, sid), rng.choice(caps["tok"]))
            if caps["unit"] not in ("row",) and _GLAY[f][0] not in ("L02", "L09", "L15", "L16", "L17") and rng.random() < 0.15:
                style = rng.choice(caps["tok"])
        tok = _G_pick_token(W, sid, style, r["t"]) if st is not None or style == "canon" else sid
        u = caps["unit"]
        if u in ("reg", "rec", "suffix", "row", "block", "meta"):
            unit = _G_tl(st["unit_tl"][r["sensor"]], r["t"]) if st is not None else "FT"
            if u != "reg" and rng.random() < 0.1:
                unit = "M" if unit == "FT" else "FT"
        else:
            unit = u
        val = "" if void else _G_value_text(r["vft"] if vft is None else vft, unit)
        files[f].append({"tok": tok, "site": sid, "sensor": r["sensor"], "t": r["t"], "val": val, "unit": unit,
                         "q": q, "rev": rev, "void": void})
        load[f] += 1
        return True
    W["style"] = {}
    swap = next((s for s in W["sites"] if "swap_t" in s), None)
    for s in W["sites"]:
        n = rng.choice([2, 3, 3, 4])
        cuts = sorted(rng.sample(range(8, 82), n - 1))
        bounds = [W["ws"] - 3 * 86400] + [W["pstart"] + c * 86400 + rng.randint(0, 23) * 3600 for c in cuts] + [W["we"] + 3 * 86400]
        prev = None
        for k in range(n):
            a, b = bounds[k], bounds[k + 1]
            b_ext = b + cfg["dup_hours"] * 3600 if k + 1 < n else b
            cand = sorted(pcap, key=lambda f: (load[f], f))[:6]
            cand = [f for f in cand if f != prev] or cand
            if s is swap and a <= s["swap_t"] < b:
                cand = [f for f in regu if f != prev] or regu
            f = rng.choice(cand)
            prev = f
            routes.append({"file": f, "site": s["id"], "sensor": "P", "from": a, "to": b_ext, "status": "ACTIVE"})
            W["chunk_file"].setdefault(s["id"], []).append((f, a, b_ext))
            for r in s["recs"]:
                if r["sensor"] == "P" and a <= r["t"] < b_ext:
                    emit(f, s["id"], r)
            if k == 0 or k == n - 1:
                lo, hi = (W["ws"] - 2 * 86400, W["ws"]) if k == 0 else (W["we"], W["we"] + 86400)
                t = lo - lo % s["interval"] + s["interval"]
                while t < hi:
                    h = _G_hopen(W, s, t) + _G_drift(s, t) - float(_G_tl(s["datum_tl"]["P"], t))
                    emit(f, s["id"], {"sensor": "P", "t": t, "vft": h, "q": "G"})
                    t += s["interval"]
        if s["backup"]:
            bfiles = ["ue_14ko.ndjson"] + [f for f in pcap if "B" in _GLAY[f][2]["sensor"]]
            for a, b in s["bwin"]:
                f = "ue_14ko.ndjson" if rng.random() < 0.6 else rng.choice(bfiles)
                routes.append({"file": f, "site": s["id"], "sensor": "B", "from": a, "to": b, "status": "ACTIVE"})
                for r in s["recs"]:
                    if r["sensor"] == "B" and a <= r["t"] < b:
                        emit(f, s["id"], r)
    # revisions and voids of routed records
    allrecs = [(f, x) for f in files for x in list(files[f]) if x["site"] in W["site"]]
    for f, x in rng.sample(allrecs, int(len(allrecs) * cfg["revision_rate"])):
        if x["void"] or x["rev"] != 1:
            continue
        s = W["site"][x["site"]]
        base = {"sensor": x["sensor"], "t": x["t"], "q": x["q"], "vft": None}
        vft = float(_Gfr(x["val"]) / _GUNIT_DIV[x["unit"]]) + rng.choice([-1, 1]) * rng.uniform(0.01, 0.08)
        emit(f, x["site"], base, rev=2, vft=vft, style="canon")
        if rng.random() < 0.2:
            emit(f, x["site"], base, rev=3, vft=vft + rng.uniform(-0.03, 0.03), style="canon")
    voidable = [(f, x) for f, x in allrecs if _GLAY[f][2]["void"] and not x["void"]]
    for f, x in rng.sample(voidable, int(len(allrecs) * cfg["void_rate"])):
        emit(f, x["site"], {"sensor": x["sensor"], "t": x["t"], "q": x["q"], "vft": 0.0}, rev=x["rev"] + 1, void=True, style="canon")
    # same-revision conflicts across files inside overlap windows
    bykey = {}
    for f in files:
        for x in files[f]:
            if x["rev"] == 1 and not x["void"] and x["site"] in W["site"]:
                bykey.setdefault((x["site"], x["sensor"], x["t"]), []).append((f, x))
    multi = sorted([v for v in bykey.values() if len(v) > 1], key=lambda v: (v[0][1]["site"], v[0][1]["t"]))
    for v in rng.sample(multi, min(cfg["conflicts"], len(multi))):
        f, x = v[rng.randint(0, len(v) - 1)]
        vft = float(_Gfr(x["val"]) / _GUNIT_DIV[x["unit"]]) + rng.choice([-1, 1]) * rng.uniform(0.02, 0.09)
        x["val"] = _G_value_text(vft, x["unit"])
    # unrouted copies with a high revision, stale dumps before a route, retired cache
    for f in rng.sample(pcap, 5):
        mine = {x["site"] for x in files[f]}
        other = [s for s in W["sites"] if s["id"] not in mine]
        if not other:
            continue
        s = rng.choice(other)
        a = W["pstart"] + rng.randint(5, 70) * 86400
        for r in s["recs"]:
            if r["sensor"] == "P" and a <= r["t"] < a + rng.randint(6, 30) * 3600:
                emit(f, s["id"], r, rev=3, vft=r["vft"] + rng.uniform(0.05, 0.4), style="canon")
    for s in rng.sample(W["sites"], 3):
        f, a, b = W["chunk_file"][s["id"]][-1]
        if a <= W["pstart"]:
            continue
        for r in s["recs"]:
            if r["sensor"] == "P" and a - 18 * 3600 <= r["t"] < a:
                emit(f, s["id"], r, rev=2, vft=r["vft"] + rng.uniform(-0.05, 0.05))
        routes.append({"file": f, "site": s["id"], "sensor": "P", "from": a - 30 * 86400, "to": a, "status": "RETIRED"})
    for s in rng.sample(W["sites"], 3):
        a = W["pstart"] + rng.randint(0, 60) * 86400
        for r in s["recs"]:
            if r["sensor"] == "P" and a <= r["t"] < a + 12 * 86400 and r["t"] % 3600 == 0:
                emit("zz_04rt.csv", s["id"], r, vft=r["vft"] + rng.uniform(-0.06, 0.06), style="canon")
        routes.append({"file": "zz_04rt.csv", "site": s["id"], "sensor": "P", "from": a, "to": a + 12 * 86400, "status": "RETIRED"})
    # other-network stations and unknown tokens
    others = [x for x in W["stations"] if x["id"] not in W["site"]]
    for st in rng.sample(others, 3):
        for f in rng.sample(pcap, 3):
            a = W["pstart"] + rng.randint(0, 80) * 86400
            t = a - a % 900
            while t < a + 36 * 3600:
                emit(f, st["id"], {"sensor": "P", "t": t, "vft": rng.uniform(2, 6), "q": "G"}, style="canon")
                t += 900
            routes.append({"file": f, "site": st["id"], "sensor": "P", "from": a - 86400, "to": a + 3 * 86400, "status": "ACTIVE"})
    for f in rng.sample(pcap, 4):
        for k in range(3):
            t = W["pstart"] + rng.randint(0, 85) * 86400
            t -= t % 900
            uu = _GLAY[f][2]["unit"] if _GLAY[f][2]["unit"] in _GUNIT_DIV else "FT"
            files[f].append({"tok": rng.choice(["SPARE-07", "TEST-LOG", "UNASSIGND"]), "site": None, "sensor": "P", "t": t,
                             "val": _G_value_text(rng.uniform(1, 5), uu), "unit": uu, "q": "G", "rev": 1, "void": False})
    # extra retired and active route rows of history
    for s in W["sites"]:
        for f in rng.sample(pcap, 2):
            a = W["ws"] - rng.randint(60, 400) * 86400
            routes.append({"file": f, "site": s["id"], "sensor": "P", "from": a, "to": a + rng.randint(10, 50) * 86400, "status": "RETIRED"})
    for st in rng.sample(others, 120):
        f = rng.choice(pcap)
        a = W["ws"] - rng.randint(0, 100) * 86400
        routes.append({"file": f, "site": st["id"], "sensor": "P", "from": a, "to": a + rng.randint(30, 200) * 86400, "status": rng.choice(["ACTIVE", "RETIRED"])})
    # time-gated and addendum-corrected legacy tokens on records of the sites they name
    picks = sorted(f for f in files if f not in ("zz_04rt.csv", "ue_14ko.ndjson"))
    for f in picks:
        for x in files[f]:
            if W["switch"] and ((x["site"] == W["switch"][1] and x["t"] < W["switch"][3]) or (x["site"] == W["switch"][2] and x["t"] >= W["switch"][3])):
                if rng.random() < 0.12:
                    x["tok"] = W["switch"][0]
            if x["site"] == W["fix_alias"][2] and rng.random() < 0.12:
                x["tok"] = W["fix_alias"][0]
    for f in files:
        rng.shuffle(files[f])
        files[f].sort(key=lambda x: (x["t"], x["rev"]))
    order = [L[1] for L in _GLAYOUTS] + list(_GARCHIVED)
    rng.shuffle(order)
    rng.shuffle(routes)
    for k, r in enumerate(routes):
        r["route"] = 500 + k
    W["files"] = files
    W["catalog"] = {"order": order, "routes": routes}
    if cfg["long_chain"] and W.get("long_chain"):
        sid, ok_tok, bad_tok = W["long_chain"]
        f0 = W["chunk_file"][sid][0][0]
        mine = [x for x in files[f0] if x["site"] == sid and x["sensor"] == "P" and not x["void"] and W["pstart"] <= x["t"] < W["pend"]]
        picks = _G_rng(W["seed"], "longchain").sample(mine, min(12, len(mine)))
        for k, x in enumerate(picks):
            x["tok"] = ok_tok if k % 2 == 0 else bad_tok
    if cfg["order_fix"]:
        r3 = _G_rng(W["seed"], "orderfix")
        routed = {(r["file"], r["site"]) for r in routes if r["status"] == "ACTIVE"}
        longf = [f for f in ("lg_7q2k.csv", "rf_08tn.tsv", "pr_71ev.txt", "kd_58zy.xml") if f in files]
        touched = set()
        for f in longf:
            st = next((x for x in others if (f, x["id"]) not in routed), None)
            if st is not None:
                a = W["pstart"] + r3.randint(5, 60) * 86400
                for k in range(6):
                    files[f].append({"tok": st["id"], "site": st["id"], "sensor": "P", "t": a + k * 1800,
                                     "val": _G_value_text(r3.uniform(2, 6), "FT"), "unit": "FT", "q": "G", "rev": 1, "void": False})
                touched.add(f)
            s = next((x for x in W["sites"] if (f, x["id"]) not in routed), None)
            if s is not None:
                a = W["ws"] - 2 * 86400 - (W["ws"] % s["interval"])
                for k in range(6):
                    files[f].append({"tok": s["id"], "site": s["id"], "sensor": "P", "t": a + k * s["interval"],
                                     "val": _G_value_text(r3.uniform(2, 6), "FT"), "unit": "FT", "q": "G", "rev": 1, "void": False})
                touched.add(f)
        for f in sorted(touched):
            files[f].sort(key=lambda x: (x["t"], x["rev"]))


def _G_memo_data(W, rng):  # noqa: C901
    cfg = W["cfg"]
    M = {}
    M["tol_old"] = dict(cfg["tol_old"])
    M["tol"] = dict(cfg["tol"])
    wk = {}
    for st in W["stations"]:
        wk[st["id"]] = _Gtxt(_GF(rng.randint(48, 88), 100), 2)
    M["winter"] = wk
    M["winter_old"] = {k: _Gtxt(_GF(rng.randint(40, 95), 100), 2) for k in wk}
    errata = []
    for s in rng.sample(W["sites"], cfg["errata"]):
        v = rng.choice(s["versions"])
        hs = sorted(r["vft"] for r in s["recs"] if r["sensor"] == "P")
        lo, hi = hs[len(hs) // 10], hs[len(hs) * 9 // 10]
        pts = v["points"]
        cand = [k for k in range(1, len(pts) - 1) if lo - 0.5 <= float(pts[k][0]) <= hi + 0.5] or list(range(1, len(pts) - 1))
        k = rng.choice(cand)
        qa, qk, qb = _Gfr(pts[k - 1][1]), _Gfr(pts[k][1]), _Gfr(pts[k + 1][1])
        for _ in range(20):
            nq = _Gsig(qk * _GF(rng.choice([rng.uniform(1.02, 1.07), rng.uniform(0.94, 0.98)])), 3)
            if qa < nq < qb and nq != qk:
                break
        else:
            nq = qk
        if nq != qk:
            errata.append({"rating": v["id"], "gh": pts[k][0], "q": _Gtxt(nq), "was": pts[k][1]})
    for v in W["withdrawn_versions"][:1]:
        errata.append({"rating": v["id"], "gh": v["points"][3][0], "q": _Gtxt(_Gfr(v["points"][3][1]) + 1), "was": v["points"][3][1]})
    M["errata"] = errata
    old_err = []
    for s in rng.sample(W["sites"], 3):
        v = s["versions"][0]
        k = rng.randint(1, len(v["points"]) - 2)
        old_err.append({"rating": v["id"], "gh": v["points"][k][0], "q": _Gtxt(_Gsig(_Gfr(v["points"][k][1]) * _GF(rng.uniform(0.9, 1.1)), 3)),
                        "was": v["points"][k][1]})
    M["errata_old"] = old_err
    cand = [v for v in W["visits"] if W["pstart"] < v["t"] < W["pend"] and v is not W["site"][v["site"]]["visits"][0]]
    M["disregard"] = sorted(rng.sample(cand, cfg["disregard"]), key=lambda v: v["vid"])
    W["memo"] = M


def _G_review(W, rng):
    """Board review of measurements (memo Table M-1): verdict and grade per listed measurement."""
    cfg = W["cfg"]
    rev = {}
    ins = [m for m in W["meas"]]
    rng.shuffle(ins)
    k = 0
    for m in ins[: cfg["rejects"]]:
        rev[m["no"]] = ("REJECT", m["grade"], rng.choice(["meter fault", "boat drift", "transect count below minimum", "edge estimate"]))
        k += 1
    for m in ins[cfg["rejects"]: cfg["rejects"] + cfg["regrades"]]:
        g = {"E": "G", "G": "F", "F": rng.choice(["P", "G"]), "P": "F"}[m["grade"]]
        rev[m["no"]] = ("REGRADE", g, "grade revised on review")
    for m in ins[cfg["rejects"] + cfg["regrades"]: cfg["rejects"] + cfg["regrades"] + 25]:
        rev[m["no"]] = ("ACCEPT", m["grade"], "reviewed")
    for m in W["meas_other"]:
        if rng.random() < 0.8:
            rev[m["no"]] = (rng.choice(["ACCEPT", "ACCEPT", "REJECT", "REGRADE"]), rng.choice("EGFP"), "network review")
    W["review"] = rev


def _G_other_visits(W, rng):
    others = [x for x in W["stations"] if x["id"] not in W["site"]]
    vid = max(v["vid"] for v in W["visits"]) + 50
    out = []
    for st in rng.sample(others, 45):
        t = _G_daytime(W["ws"] + rng.randint(-10, 20) * 86400, W["clock"]["std"], rng, 8, 15)
        for _ in range(rng.randint(2, 4)):
            h = rng.uniform(1.5, 9.0)
            refs = [("TAPE", f"{h:.2f}"), ("STAFF", f"{h + 0.01:.2f}")]
            out.append({"vid": vid, "site": st["id"], "t": t, "display": f"{h + rng.uniform(-0.05, 0.05):.2f}", "action": "RESET",
                        "refs": refs, "party": "EXT"})
            vid += 2
            t += rng.randint(14, 30) * 86400
    W["visits_other"] = out


def _G_visit_amends(W, rng):  # noqa: C901
    cfg = W["cfg"]
    am = []
    no = [60 + rng.randint(0, 40)]

    def nxt():
        no[0] += rng.randint(1, 3)
        return no[0]
    ins = [v for v in W["visits"] if W["ws"] - 20 * 86400 < v["t"] < W["we"] and v is not W["site"][v["site"]]["visits"][0]]
    picks = rng.sample(ins, min(len(ins), cfg["visit_amends"] + cfg["extra_visits"]))
    for k, v in enumerate(picks):
        kind = ["REF", "ACTION", "TIME", "REF", "VOID", "LOGGER"][k % 6]
        if kind == "REF":
            m = v["refs"][0][0] if v["refs"][0][0] != "STAFF" else "TAPE"
            am.append({"no": nxt(), "visit": v["vid"], "field": "reference", "method": m, "value": _Gtxt(_Gfr(v["refs"][0][1]) + _GF(rng.choice([-3, -2, 2, 3]), 100), 2)})
        elif kind == "ACTION":
            am.append({"no": nxt(), "visit": v["vid"], "field": "action", "value": "NONE" if v["action"] == "RESET" else "RESET"})
        elif kind == "TIME":
            am.append({"no": nxt(), "visit": v["vid"], "field": "time", "value": _Glst(v["t"] + rng.choice([-2, -1, 1, 3]) * 3600, W["clock"])})
        elif kind == "LOGGER":
            am.append({"no": nxt(), "visit": v["vid"], "field": "logger", "value": _Gtxt(_Gfr(v["display"]) + _GF(rng.choice([-2, 1, 2]), 100), 2)})
        else:
            am.append({"no": nxt(), "visit": v["vid"], "field": "void"})
            am.append({"no": nxt(), "visit": v["vid"], "field": "action", "value": "NONE"})
    for v in rng.sample(W["visits_other"], len(W["visits_other"])) + rng.sample(W["visits_other"], min(len(W["visits_other"]), 80)):
        am.append({"no": nxt(), "visit": v["vid"], "field": rng.choice(["reference", "action"]), "method": "TAPE",
                   "value": "RESET" if rng.random() < 0.5 else f"{rng.uniform(1, 9):.2f}"})
    for a in am:
        if a["field"] == "action" and a["value"] not in ("RESET", "NONE"):
            a["value"] = "RESET"
        if a["field"] == "reference" and a["value"] in ("RESET", "NONE"):
            a["value"] = "4.20"
    if cfg["lower_method"]:
        mine = {v["vid"] for v in W["visits"]}
        for a in am:
            if a["field"] == "reference" and a["visit"] in mine:
                a["method"] = a["method"].lower()
    W["visit_amends"] = am
# ---------------------------------------------------------------------------- reference computation
_GREPORTS = ["unit_values.csv", "gh_corrections.tsv", "visit_errors.psv", "measurement_eval.csv", "shift_curves.json", "ice_periods.jsonl",
             "rating_tables_used.json", "daily_values.csv", "monthly_summary.xml", "period_statistics.json", "alias_resolution.csv",
             "dedup_report.json", "source_lineage.json", "reading_exclusions.jsonl", "amendment_ledger.psv", "parameters_used.yaml",
             "variance_vs_published.csv", "shift_vs_published.csv", "dashboard_disagreements.tsv", "cache_divergence.jsonl", "reconciliation.md"]
_GCORE = ["unit_values.csv", "gh_corrections.tsv", "measurement_eval.csv", "shift_curves.json", "ice_periods.jsonl", "daily_values.csv",
          "monthly_summary.xml", "period_statistics.json"]
_GCFS = _GF(3048, 10000) ** 3
_GAF = _GF(86400, 43560)
_GPUB = frozenset({"old_ratings", "tol_old", "field_gh", "mean_stage", "utc_days", "no_errata", "no_visit_corr", "dev_base", "edits_file_order"})


def _G_params(W):
    cfg = W["cfg"]
    P = {"network": cfg["network"], "period_start": cfg["period_start"], "period_end": cfg["period_end"],
         "rating_sheet": cfg["rating_sheet"], "index_sheet": cfg["index_sheet"], "site_sheet": cfg["site_sheet"],
         "max_gap": int(cfg["max_gap_min"]), "min_cov": _Gfr(cfg["min_cov"]), "margin_h": int(cfg["margin_h"]),
         "drift_tol": cfg["drift_tol"]}
    tol, gap = {}, {}
    for sid in W["scope"]:
        ov = W["overlay"].get(sid, {})
        if "drift_tolerance_ft" in ov:
            tol[sid] = ov["drift_tolerance_ft"]
        elif W["station"][sid]["drift_tol"]:
            tol[sid] = W["station"][sid]["drift_tol"]
        else:
            tol[sid] = P["drift_tol"]
        gap[sid] = int(ov.get("max_gap_minutes", P["max_gap"]))
    P["tol_site"], P["gap_site"] = tol, gap
    return P


def _G_rating_set(W, flip):
    """ACTIVE versions per in-scope site with their points after the in-force errata."""
    errata = {} if "no_errata" in flip else {(e["rating"], e["gh"]): e["q"] for e in W["memo"]["errata"]}
    out = {}
    for s in W["sites"]:
        vs = []
        for v in s["versions"]:
            src = v["old_points"] if "old_ratings" in flip else v["points"]
            pts, applied = [], []
            for h, q, e in src:
                if (v["id"], h) in errata:
                    applied.append({"gh": h, "from": q, "to": errata[(v["id"], h)]})
                    q = errata[(v["id"], h)]
                pts.append((h, q, e))
            vs.append({"id": v["id"], "eff_u": v["eff_u"], "points": pts, "fpts": _Gfpts(pts), "applied": applied})
        vs.sort(key=lambda v: v["eff_u"])
        out[s["id"]] = vs
    return out


def _G_vat(vs, u):
    best = None
    for v in vs:
        if v["eff_u"] <= u:
            best = v
    return best


def _G_sig4_rating(v, h):
    """Q = rating(h) at 4 significant figures and the above-rating flag (handbook H10)."""
    memo = v.setdefault("memo", {})
    hit = memo.get(h)
    if hit is None:
        hf = float(h)
        hit = (_Gsig(_G_rq(v["fpts"], hf), 4), hf > v["fpts"][-1][0])
        memo[h] = hit
    return hit


def _G_compute(W, flip=frozenset()):  # noqa: C901
    P = _G_params(W)
    clock = W["clock"]
    std = clock["std"]
    resolve = _G_resolver(W)
    scope = set(W["scope"])
    ws, we, p0, p1 = W["ws"], W["we"], W["pstart"], W["pend"]
    S = {"P": P}
    # ---- H4 ingest
    act = {}
    for r in W["catalog"]["routes"]:
        if r["status"] == "ACTIVE":
            act.setdefault((r["file"], r["site"], r["sensor"]), []).append((r["from"], r["to"]))
    order = [f for f in W["catalog"]["order"] if f in W["files"]]
    C = {k: 0 for k in ["files_read", "records_read", "unknown_site", "out_of_scope", "unrouted", "out_of_window", "admitted",
                        "superseded", "duplicates", "voided", "edit_deleted", "sensor_fault", "backup_unused", "kept",
                        "edits_applied", "edits_ignored"]}
    lineage, copies, toks = [], {}, {}
    for fi, f in enumerate(order):
        C["files_read"] += 1
        n = {"file": f, "layout": W["lay"][f][0], "records": 0, "unknown_site": 0, "out_of_scope": 0, "unrouted": 0, "out_of_window": 0, "admitted": 0}
        for rec in W["files"][f]:
            n["records"] += 1
            sid = resolve(rec["tok"], rec["t"])
            if sid is None:
                n["unknown_site"] += 1
                continue
            if sid not in scope:
                n["out_of_scope"] += 1
                continue
            nt = _G_norm_token(rec["tok"])
            if nt != sid:
                toks[(nt, sid)] = toks.get((nt, sid), 0) + 1
            if not any(a <= rec["t"] < b for a, b in act.get((f, sid, rec["sensor"]), [])):
                n["unrouted"] += 1
                continue
            if not (ws <= rec["t"] < we):
                n["out_of_window"] += 1
                continue
            n["admitted"] += 1
            copies.setdefault((sid, rec["sensor"], rec["t"]), []).append((rec["rev"], fi, rec))
        for k in ("records", "unknown_site", "out_of_scope", "unrouted", "out_of_window", "admitted"):
            C[k if k != "records" else "records_read"] += n[k]
        lineage.append(n)
    S["lineage"], S["toks"] = lineage, toks
    # ---- H5 revisions, duplicates, voids
    readings, excl = {}, []
    for key, cs in copies.items():
        top = max(c[0] for c in cs)
        win = max((c for c in cs if c[0] == top), key=lambda c: c[1])
        C["superseded"] += sum(1 for c in cs if c[0] < top)
        C["duplicates"] += sum(1 for c in cs if c[0] == top) - 1
        if win[2]["void"]:
            C["voided"] += 1
            excl.append((key, "VOIDED", order[win[1]]))
            continue
        readings[key] = {"val": win[2]["val"], "unit": win[2]["unit"], "q": win[2]["q"], "file": order[win[1]]}
    # ---- H6 unit-value edits
    deleted, ledger = {}, []
    for e in (W["edits"] if "edits_file_order" in flip else sorted(W["edits"], key=lambda x: x["seq"])):
        sid = resolve(e["tok"], e["t"])
        if sid is None or sid not in scope:
            continue
        key = (sid, e["sensor"], e["t"])
        st = "IGNORED"
        if not (ws <= e["t"] < we):
            pass
        elif e["op"] == "SET":
            if key in readings:
                readings[key] = {"val": e["value"], "unit": e["unit"], "q": "G", "file": readings[key]["file"]}
                st = "APPLIED"
        elif e["op"] == "DELETE":
            if key in readings:
                deleted[key] = readings.pop(key)
                st = "APPLIED"
        elif e["op"] == "RESTORE":
            if key in deleted:
                readings[key] = deleted.pop(key)
                st = "APPLIED"
        C["edits_applied" if st == "APPLIED" else "edits_ignored"] += 1
        ledger.append({"seq": e["seq"], "site": sid, "sensor": e["sensor"], "t": e["t"], "op": e["op"], "status": st})
    S["ledger"] = ledger
    for key, r in deleted.items():
        C["edit_deleted"] += 1
        excl.append((key, "EDIT_DELETED", r["file"]))
    # ---- H7 quality, H8 sensor selection
    for key in [k for k, r in readings.items() if r["q"] == "X"]:
        C["sensor_fault"] += 1
        excl.append((key, "SENSOR_FAULT", readings[key]["file"]))
        del readings[key]
    sel = {}
    for (sid, sen, t), r in readings.items():
        if sen == "P":
            sel[(sid, t)] = ("P", r)
    for (sid, sen, t), r in readings.items():
        if sen == "B":
            if (sid, t) in sel:
                C["backup_unused"] += 1
                excl.append(((sid, sen, t), "BACKUP_UNUSED", r["file"]))
            else:
                sel[(sid, t)] = ("B", r)
    C["kept"] = len(sel)
    S["C"], S["excl"] = C, excl
    # ---- H9 field visits and gage-height corrections
    dis = {v["vid"] for v in W["memo"]["disregard"]}
    vis = {}
    for v in W["visits"] + W["visits_other"]:
        vis[v["vid"]] = {"vid": v["vid"], "tok": v["tok"], "t": v["t"], "display": v["display"], "action": v["action"],
                         "refs": dict(v["refs"]), "void": False}
    for a in sorted(W["visit_amends"], key=lambda x: x["no"]):
        v = vis.get(a["visit"])
        if v is None or v["void"]:
            continue
        if a["field"] == "void":
            v["void"] = True
        elif a["field"] == "reference":
            v["refs"][a["method"].upper()] = a["value"]
        elif a["field"] == "action":
            v["action"] = a["value"]
        elif a["field"] == "time":
            v["t"] = _Glst_to_utc(a["value"], clock)
        elif a["field"] == "logger":
            v["display"] = a["value"]
    visit_rows, corr = [], {}
    for sid in sorted(scope):
        mine = sorted((v for v in vis.values() if resolve(v["tok"], v["t"]) == sid), key=lambda v: (v["t"], v["vid"]))
        tol = _Gfr(P["tol_site"][sid])
        used = []
        for v in mine:
            meth = next((m for m in ("TAPE", "WIRE", "STAFF") if m in v["refs"]), None)
            ref = _Gfr(v["refs"][meth])
            err = ref - _Gfr(v["display"])
            app = err if abs(err) >= tol else _GF(0)
            status = "VOID" if v["void"] else "DISREGARDED" if v["vid"] in dis else "USED"
            visit_rows.append({"site": sid, "vid": v["vid"], "t": v["t"], "method": meth, "ref": ref, "logger": _Gfr(v["display"]),
                               "err": err, "app": app if status == "USED" else None, "action": v["action"], "status": status})
            if status == "USED":
                used.append((v["t"], app, v["action"]))
        segs = []
        for k, (t, app, action) in enumerate(used):
            a = _GF(0) if action == "RESET" else app
            if k + 1 < len(used):
                segs.append((t, used[k + 1][0], a, used[k + 1][1]))
            else:
                segs.append((t, None, a, a))
        if "no_visit_corr" in flip:
            segs = []
        corr[sid] = segs
    S["visit_rows"], S["corr"] = visit_rows, corr

    def c_at(sid, t):
        val = _GF(0)
        for a, b, x, y in corr[sid]:
            if a <= t and (b is None or t < b):
                return x if b is None else x + (y - x) * _GF(t - a, b - a)
        return val

    dcache = {}

    def gh_of(sid, t):
        sen, r = sel[(sid, t)]
        k = (sid, sen)
        if k not in dcache:
            dcache[k] = sorted((x for x in W["datum_rows"] if x["site"] == sid and x["sensor"] == sen and x["status"] == "ACTIVE"),
                               key=lambda x: x["from"])
        off = _GF(0)
        for x in dcache[k]:
            if x["from"] <= t:
                off = _Gfr(x["offset"])
        return _Gq(_Gfr(r["val"]) / _GUNIT_DIV[r["unit"]] + off + c_at(sid, t), 2)
    times = {}
    for (sid, t) in sel:
        times.setdefault(sid, []).append(t)
    for sid in times:
        times[sid].sort()
    GH = {(sid, t): gh_of(sid, t) for sid in times for t in times[sid]}
    S["GH"], S["times"], S["sel"] = GH, times, sel
    # ---- H10 ratings
    RS = _G_rating_set(W, flip)
    S["RS"] = RS
    # ---- H11 measurements
    tolt = W["memo"]["tol_old"] if "tol_old" in flip else W["memo"]["tol"]
    ms = {}
    for src, lst in (("main", W["meas"] + W["meas_other"]), ("late", W["meas_late"])):
        for m in lst:
            if m["no"] not in ms or m["entered"] > ms[m["no"]][1]["entered"]:
                ms[m["no"]] = (src, m)
    meas = []
    for no, (src, m) in sorted(ms.items()):
        mid = m["start"] + (m["end"] - m["start"]) // 2
        mid -= mid % 60
        sid = resolve(m["tok"], mid)
        if sid is None or sid not in scope:
            continue
        verdict, grade = "ACCEPT", m["grade"]
        if no in W["review"]:
            vv, gg, _ = W["review"][no]
            verdict = vv
            if vv == "REGRADE":
                grade = gg
        xs = [GH[(sid, t)] for t in times.get(sid, []) if m["start"] <= t <= m["end"]]
        if "field_gh" in flip:
            gh = _Gfr(m["field_gh"])
        else:
            gh = _Gq(sum(xs, _GF(0)) / len(xs), 2) if xs else None
        meas.append({"no": no, "site": sid, "t": mid, "start": m["start"], "end": m["end"], "q": m["q"], "grade": grade, "verdict": verdict,
                     "cover": m["cover"], "gh": gh, "src": src})
    ents = []
    for e in W["icelog"]:
        if e["kind"] in ("ON", "OFF"):
            ents.append(dict(e, site=resolve(e["tok"], e["at"])))
        else:
            ents.append(e)
    ice = _G_ice_replay(ents)
    S["ice"] = {sid: ice.get(sid, []) for sid in sorted(scope)}

    def in_ice(sid, t):
        for a, b, _, _ in S["ice"][sid]:
            if a <= t and (b is None or t < b):
                return (a, b)
        return None
    cur, pts = {}, {}
    for m in sorted(meas, key=lambda x: (x["site"], x["t"], x["no"])):
        m.update({"rating": None, "s_use": None, "qr": None, "dev": None, "tol": None, "shift": None, "k": None})
        if m["verdict"] == "REJECT":
            m["decision"] = "REJECTED"
            continue
        if m["gh"] is None:
            m["decision"] = "NO_RECORD"
            continue
        v = _G_vat(RS[m["site"]], m["t"])
        m["rating"] = v["id"]
        if in_ice(m["site"], m["t"]):
            m["decision"] = "ICE"
            continue
        s_use = _GF(0) if "dev_base" in flip else cur.get(v["id"], _GF(0))
        qr, _ = _G_sig4_rating(v, m["gh"] + s_use)
        dev = _Gq((m["q"] - qr) / qr * 100, 1)
        tol = _Gfr(tolt[m["grade"]]) if m["grade"] in tolt else None
        m.update({"s_use": s_use, "qr": qr, "dev": dev, "tol": tol})
        if tol is not None and abs(dev) > tol:
            h_r = _Gq(_GF(_G_rinv(v["fpts"], float(m["q"]))), 2)
            m["shift"] = h_r - m["gh"]
            m["decision"] = "SHIFT"
            cur[v["id"]] = m["shift"]
            pts.setdefault(v["id"], []).append((m["t"], m["shift"], m["no"]))
        else:
            m["decision"] = "CHECK"
    curves = {}
    for sid in sorted(scope):
        for v in RS[sid]:
            curves[v["id"]] = [(v["eff_u"], _GF(0), None)] + pts.get(v["id"], [])
    S["curves"] = curves

    def s_at(v, t):
        cv = curves[v["id"]]
        for (a, x, _), (b, y, _) in zip(cv, cv[1:]):
            if a <= t < b:
                return _Gq(x + (y - x) * _GF(t - a, b - a), 2)
        return _Gq(cv[-1][1], 2)
    # ---- H13 ice factors
    W1 = W["memo"]["winter"]
    kp = {}
    for m in sorted(meas, key=lambda x: (x["site"], x["t"], x["no"])):
        if m["decision"] != "ICE":
            continue
        v = _G_vat(RS[m["site"]], m["t"])
        s = s_at(v, m["t"])
        qo, _ = _G_sig4_rating(v, m["gh"] + s)
        m["s_use"], m["qr"] = s, qo
        m["k"] = _Gq(m["q"] / qo, 3)
        per = in_ice(m["site"], m["t"])
        kp.setdefault((m["site"], per[0]), []).append((m["t"], m["k"], m["no"]))
    S["meas"] = sorted(meas, key=lambda x: x["no"])
    S["kp"] = kp

    def k_at(sid, per, t):
        ks = kp.get((sid, per[0]))
        if not ks:
            return _Gfr(W1[sid])
        if t <= ks[0][0]:
            return ks[0][1]
        for (a, x, _), (b, y, _) in zip(ks, ks[1:]):
            if a <= t < b:
                return _Gq(x + (y - x) * _GF(t - a, b - a), 3)
        return ks[-1][1]
    # ---- H14 unit values
    UV = {}
    for sid in sorted(times):
        for t in times[sid]:
            gh = GH[(sid, t)]
            v = _G_vat(RS[sid], t)
            s = s_at(v, t)
            h = gh + s
            qo, above = _G_sig4_rating(v, h)
            per = in_ice(sid, t)
            k = k_at(sid, per, t) if per else None
            q = _Gsig(k * qo, 4) if per else qo
            sen = sel[(sid, t)][0]
            UV[(sid, t)] = {"gh": gh, "s": s, "h": h, "qo": qo, "k": k, "q": q, "sensor": sen, "rating": v["id"],
                            "flags": ("B" if sen == "B" else "") + ("I" if per else "") + (">" if above else "")}
    S["UV"] = UV
    # ---- H15 daily values
    doff = 0 if "utc_days" in flip else std
    ndays = (W["pe"] - W["ps"]).days
    DV = {}
    dstart = _Gday_utc(W["ps"]) - doff * 60
    for sid in sorted(scope):
        ts = times.get(sid, [])
        gap = P["gap_site"][sid] * 60
        acc = [[_GF(0), 0, 0, set(), _GF(0)] for _ in range(ndays)]
        for t in ts:
            di = (t - dstart) // 86400
            if 0 <= di < ndays:
                acc[di][2] += 1
                fl = UV[(sid, t)]["flags"]
                if "I" in fl:
                    acc[di][3].add("ICE")
                if "B" in fl:
                    acc[di][3].add("B")
                if ">" in fl:
                    acc[di][3].add(">")
        for ta, tb in zip(ts, ts[1:]):
            if tb - ta > gap or tb <= dstart or ta >= dstart + ndays * 86400:
                continue
            ua, ub = UV[(sid, ta)], UV[(sid, tb)]
            qa, qb = ua["q"], ub["q"]
            for di in range(max(0, (ta - dstart) // 86400), min(ndays - 1, (tb - 1 - dstart) // 86400) + 1):
                d0 = dstart + di * 86400
                x, y = max(ta, d0), min(tb, d0 + 86400)
                if y <= x:
                    continue
                fx = qa + (qb - qa) * _GF(x - ta, tb - ta)
                fy = qa + (qb - qa) * _GF(y - ta, tb - ta)
                acc[di][0] += (fx + fy) / 2 * (y - x)
                acc[di][1] += y - x
                if "mean_stage" in flip:
                    ha, hb = ua["h"], ub["h"]
                    gx = ha + (hb - ha) * _GF(x - ta, tb - ta)
                    gy = ha + (hb - ha) * _GF(y - ta, tb - ta)
                    acc[di][4] += (gx + gy) / 2 * (y - x)
        for di in range(ndays):
            d = W["ps"] + _Gtd(days=di)
            integ, cov, nread, codes, hint = acc[di]
            inc = cov < P["min_cov"] * 86400
            mean = None
            if not inc:
                if "mean_stage" in flip:
                    v = _G_vat(RS[sid], dstart + di * 86400 + 43200)
                    mean = _Gdv(_G_sig4_rating(v, _Gq(hint / cov, 2))[0])
                else:
                    mean = _Gdv(integ / cov)
            cl = [c for c in ("INC", "ICE", "B", ">") if (c == "INC" and inc) or c in codes]
            DV[(sid, d)] = {"q": mean, "cov": cov, "n": nread, "codes": cl}
    S["DV"] = DV
    # ---- H16 monthly and period statistics
    MON, PST = [], []
    for sid in sorted(scope):
        area = _Gfr(W["station"][sid]["area_mi2"])
        months = {}
        for di in range(ndays):
            d = W["ps"] + _Gtd(days=di)
            months.setdefault((d.year, d.month), []).append(DV[(sid, d)])
        for (y, mo), rows in sorted(months.items()):
            comp = [r["q"] for r in rows if r["q"] is not None]
            rec = {"site": sid, "month": f"{y:04d}-{mo:02d}", "days": len(rows), "complete_days": len(comp)}
            if comp:
                vol = _Gq(sum(comp, _GF(0)) * _GAF, 1)
                rec.update({"mean": _Gdv(sum(comp, _GF(0)) / len(comp)), "min": min(comp), "max": max(comp), "volume": vol, "sum": sum(comp, _GF(0)),
                            "runoff": _Gq(vol * 12 / (area * 640), 2)})
            else:
                rec.update({"mean": None, "min": None, "max": None, "volume": None, "runoff": None, "sum": None})
            rec["complete"] = len(comp) == len(rows)
            MON.append(rec)
        days = [W["ps"] + _Gtd(days=di) for di in range(ndays)]
        peak = None
        for t in times.get(sid, []):
            if p0 <= t < p1:
                q = UV[(sid, t)]["q"]
                if peak is None or q > peak[0]:
                    peak = (q, t)
        best = None
        for i in range(ndays - 6):
            win = [DV[(sid, days[i + j])]["q"] for j in range(7)]
            if all(x is not None for x in win):
                mv = sum(win, _GF(0)) / 7
                if best is None or mv < best[0]:
                    best = (mv, days[i])
        comp = [DV[(sid, d)]["q"] for d in days if DV[(sid, d)]["q"] is not None]
        PST.append({"site": sid, "peak": peak, "min7": best, "mean": _Gdv(sum(comp, _GF(0)) / len(comp)) if comp else None,
                    "complete_days": len(comp), "inc_days": sum(1 for d in days if "INC" in DV[(sid, d)]["codes"]),
                    "ice_days": sum(1 for d in days if "ICE" in DV[(sid, d)]["codes"]),
                    "backup_days": sum(1 for d in days if "B" in DV[(sid, d)]["codes"]),
                    "above_rating_days": sum(1 for d in days if ">" in DV[(sid, d)]["codes"]),
                    "shift_points": sum(1 for m in meas if m["site"] == sid and m["decision"] == "SHIFT"),
                    "ice_measurements": sum(1 for m in meas if m["site"] == sid and m["decision"] == "ICE")})
    S["MON"], S["PST"] = MON, PST
    return S
# ---------------------------------------------------------------------------- tokens, registers, fixtures
def _G_assign_tokens(W, rng):
    def tok(sid, t, styles):
        return _G_pick_token(W, sid, rng.choice(styles), t)
    for v in W["visits"] + W["visits_other"]:
        v["tok"] = tok(v["site"], v["t"], ["canon", "canon", "short", "cb"])
    for m in W["meas"] + W["meas_late"] + W["meas_other"]:
        mid = m["start"] + (m["end"] - m["start"]) // 2
        m["tok"] = tok(m["site"], mid - mid % 60, ["canon", "canon", "short", "strip", "legacy", "cb"])
    for e in W["edits"]:
        e["tok"] = tok(e["site"], e["t"], ["canon", "short", "chain", "strip"])
    for e in W["icelog"]:
        if "site" in e:
            e["tok"] = tok(e["site"], e["at"], ["canon", "short", "cb"])


def _G_registers(W, rng):  # noqa: C901
    rows = []
    for s in W["sites"]:
        for sen in ("P", "B"):
            if sen == "B" and not s["backup"]:
                continue
            for k, (a, off) in enumerate(s["datum_tl"][sen]):
                rows.append({"site": s["id"], "sensor": sen, "from": a, "offset": off, "status": "ACTIVE",
                             "mark": f"RM-{rng.randint(1, 9)}", "note": "levelled" if k else "installed"})
            old = s["datum_tl"][sen][0][0] - rng.randint(200, 900) * 86400
            rows.append({"site": s["id"], "sensor": sen, "from": old, "offset": _Gtxt(_Gfr(s["datum_tl"][sen][0][1]) + _GF(rng.randint(-40, 40), 100), 2),
                         "status": "ACTIVE", "mark": "RM-1", "note": "original survey"})
    for s in rng.sample(W["sites"], 3):
        t = W["pstart"] + rng.randint(10, 80) * 86400
        rows.append({"site": s["id"], "sensor": "P", "from": t, "offset": _Gtxt(_Gfr(s["datum_tl"]["P"][-1][1]) + _GF(rng.choice([-25, 18, 31]), 100), 2),
                     "status": "WITHDRAWN", "mark": "RM-2", "note": "levelling rejected"})
    others = [x for x in W["stations"] if x["id"] not in W["site"]]
    for st in others:
        for _ in range(rng.choice([1, 1, 2])):
            rows.append({"site": st["id"], "sensor": "P", "from": W["ws"] - rng.randint(100, 3000) * 86400, "offset": f"{rng.uniform(-1, 2):.2f}",
                         "status": rng.choice(["ACTIVE", "ACTIVE", "WITHDRAWN"]), "mark": "RM-1", "note": "network survey"})
    W["datum_rows"] = rows
    eq = []
    for s in W["sites"]:
        for sen in ("P", "B"):
            if sen == "B" and not s["backup"]:
                continue
            tl = s["unit_tl"][sen]
            for k, (a, unit) in enumerate(tl):
                eq.append({"site": s["id"], "sensor": sen, "from": a, "event": "INSTALL" if k == 0 else "SWAP", "unit": unit,
                           "model": rng.choice(["PT-12", "BUB-4", "RAD-9", "SDI-55"]), "serial": f"SN{rng.randint(10000, 99999)}"})
            for _ in range(rng.randint(2, 5)):
                t = rng.randint(tl[0][0], W["we"])
                unit = _G_tl(tl, t)
                eq.append({"site": s["id"], "sensor": sen, "from": t, "event": rng.choice(["MAINT", "FIRMWARE", "BATTERY"]), "unit": unit,
                           "model": "", "serial": ""})
    for st in others:
        if rng.random() < 0.85:
            eq.append({"site": st["id"], "sensor": "P", "from": W["ws"] - rng.randint(50, 900) * 86400, "event": "INSTALL",
                       "unit": rng.choice(["FT", "M"]), "model": "PT-12", "serial": f"SN{rng.randint(10000, 99999)}"})
    W["equip_rows"] = eq


def _G_fix_ties(W, S, rng):
    """Move chosen measurements so that their rounded deviation equals the grade tolerance exactly."""
    cfg = W["cfg"]
    tol = W["memo"]["tol"]
    late = {m["no"] for m in W["meas_late"]}
    byno = {m["no"]: m for m in W["meas"]}
    first = {}
    for m in sorted(S["meas"], key=lambda x: (x["site"], x["t"])):
        if m["decision"] in ("SHIFT", "CHECK") and m["rating"] not in first:
            first[m["rating"]] = m
    cands = [m for m in first.values() if m["grade"] in tol and m["no"] not in late and m["no"] in byno and m["s_use"] == 0]
    cands.sort(key=lambda m: m["no"])
    done = []
    for m in rng.sample(cands, min(cfg["dev_tie"], len(cands))):
        qr, tv = m["qr"], _Gfr(tol[m["grade"]])
        sign = rng.choice([1, -1])
        target = qr * (1 + sign * tv / 100)
        k = _Gmag(target) - 3
        unit = _GF(10) ** k
        base = _Grnd(target, k)
        pick = None
        for j in sorted(range(-30, 31), key=abs):
            q = base + j * unit
            if q > 0 and _Gq((q - qr) / qr * 100, 1) == sign * tv:
                pick = q
                break
        if pick is not None:
            byno[m["no"]]["q"] = pick
            done.append(m["no"])
    W["tie_meas"] = done


def _G_decoy_data(W, S, SP, rng):  # noqa: C901
    """Published daily values, statistics and shifts, the dashboard and the unit-value cache."""
    pub = []
    for (sid, d), r in sorted(SP["DV"].items()):
        pub.append({"site": sid, "date": d, "q": r["q"], "codes": r["codes"]})
    W["published"] = pub
    W["pub_stats"] = SP["PST"]
    W["pub_mon"] = SP["MON"]
    sp = []
    for m in SP["meas"]:
        sp.append({"no": m["no"], "site": m["site"], "decision": m["decision"], "shift": m["shift"], "dev": m["dev"]})
    for k in range(160):
        sid = rng.choice(W["scope"])
        sp.append({"no": 3000 + k * 3 + rng.randint(0, 2), "site": sid, "decision": rng.choice(["SHIFT", "CHECK"]),
                   "shift": _GF(rng.randint(-20, 20), 100), "dev": _GF(rng.randint(-120, 120), 10), "prev": True})
    rng.shuffle(sp)
    W["shift_pub"] = sp
    raw_ice = {}
    for e in W["icelog"]:
        if e["kind"] in ("ON", "OFF") and e["site"] in W["site"]:
            raw_ice.setdefault(e["site"], []).append((e["at"], e["kind"]))
    def raw_in(sid, t):
        st = False
        for at, kind in sorted(raw_ice.get(sid, [])):
            if at > t:
                break
            st = kind == "ON"
        return st
    dash = []
    for (sid, d), r in sorted(S["DV"].items()):
        u = rng.random()
        if u < 0.08:
            q = r["q"]
        elif u < 0.88:
            q = SP["DV"][(sid, d)]["q"]
        else:
            q = _Gdv(r["q"] * _GF(rng.choice([97, 98, 102, 103]), 100)) if r["q"] is not None else None
        noon = _Gday_utc(d) - W["clock"]["std"] * 60 + 43200
        dash.append({"site": sid, "date": d, "q": q, "ice": "Y" if raw_in(sid, noon) else "N", "updated": noon + 86400 * rng.randint(1, 5)})
    W["dashboard"] = dash
    keys = sorted(S["UV"])
    cache = []
    for sid, t in rng.sample(keys, 640):
        u = rng.random()
        uv = S["UV"][(sid, t)]
        if u < 0.12:
            q = uv["q"]
        elif u < 0.88:
            q = SP["UV"].get((sid, t), uv)["q"]
        else:
            q = _Gsig(uv["q"] * _GF(rng.choice([96, 99, 101, 104]), 100), 4)
        cache.append({"site": sid, "t": t, "q": q})
    for k in range(25):
        sid = rng.choice(W["scope"])
        t = W["pstart"] + rng.randint(0, 80) * 86400 + 7 * 60
        cache.append({"site": sid, "t": t, "q": _GF(rng.randint(100, 9000), 10)})
    rng.shuffle(cache)
    W["uvcache"] = cache


# ---------------------------------------------------------------------------- rendering of the 21 reports
_GRUN = [("rating_sheet", "Ratings_2025"), ("tolerance_table", "T-1"), ("errata", "none"), ("measurement_gage_height", "field_sheet"),
         ("deviation_basis", "base_rating"), ("daily_method", "rating_of_mean_stage"), ("day_basis", "utc"),
         ("gage_height_corrections", "none"), ("edits_journal", "file_order")]


def _G_runsettings_in_force(P):
    return {"rating_sheet": P["rating_sheet"], "tolerance_table": "T-2", "errata": "R-2", "measurement_gage_height": "record_mean",
            "deviation_basis": "shift_in_use", "daily_method": "time_weighted_discharge", "day_basis": "local_standard_time",
            "gage_height_corrections": "prorated_visit_errors", "edits_journal": "seq_order"}


def _G_render(W, S) -> dict:  # noqa: C901
    clock = W["clock"]
    P = S["P"]
    L = lambda u: _Glst(u, clock)  # noqa: E731
    O = {}
    rows = []
    for (sid, t), u in sorted(S["UV"].items()):
        rows.append([sid, L(t), u["sensor"], _Gtxt(u["gh"], 2), _Gtxt(u["s"], 2), _Gtxt(u["h"], 2), _Gtxt(u["qo"]),
                     _Gtxt(u["k"], 3) if u["k"] is not None else "", _Gtxt(u["q"]), u["flags"]])
    O["unit_values.csv"] = _Gtab(["site", "time_lst", "sensor", "gh_ft", "shift_ft", "gh_eff_ft", "q_open_cfs", "k_factor", "q_cfs", "flags"], rows, ",")
    rows = []
    for sid in sorted(S["corr"]):
        for a, b, x, y in S["corr"][sid]:
            rows.append([sid, L(a), L(b) if b is not None else "", _Gtxt(x, 2), _Gtxt(y, 2)])
    O["gh_corrections.tsv"] = _Gtab(["site", "from_lst", "to_lst", "start_ft", "end_ft"], rows, "\t")
    rows = []
    for v in sorted(S["visit_rows"], key=lambda v: (v["site"], v["t"], v["vid"])):
        rows.append([v["site"], v["vid"], L(v["t"]), v["method"], _Gtxt(v["ref"], 2), _Gtxt(v["logger"], 2), _Gtxt(v["err"], 2),
                     _Gtxt(v["app"], 2) if v["app"] is not None else "", v["action"], v["status"]])
    O["visit_errors.psv"] = _Gtab(["site", "visit_id", "time_lst", "method", "reference_ft", "logger_ft", "error_ft", "applied_ft", "action", "status"], rows, "|")
    rows = []
    for m in S["meas"]:
        rows.append([m["no"], m["site"], L(m["t"]), m["grade"], m["verdict"], m["cover"], _Gtxt(m["gh"], 2) if m["gh"] is not None else "",
                     m["rating"] or "", _Gtxt(m["s_use"], 2) if m["s_use"] is not None else "", _Gtxt(m["qr"]) if m["qr"] is not None else "",
                     _Gtxt(m["q"], 2), _Gtxt(m["dev"], 1) if m["dev"] is not None else "", _Gtxt(m["tol"], 1) if m["tol"] is not None else "",
                     m["decision"], _Gtxt(m["shift"], 2) if m["shift"] is not None else "", _Gtxt(m["k"], 3) if m["k"] is not None else ""])
    O["measurement_eval.csv"] = _Gtab(["meas_no", "site", "instant_lst", "grade", "verdict", "cover", "gh_ft", "rating_id", "shift_in_use_ft",
                                       "rated_q_cfs", "measured_q_cfs", "deviation_pct", "tolerance_pct", "decision", "shift_ft", "k_factor"], rows, ",")
    curves = []
    for sid in sorted(S["RS"]):
        for v in S["RS"][sid]:
            pts = [{"time_lst": L(a), "shift_ft": _GN(x, 2), "source": "START" if no is None else str(no)} for a, x, no in S["curves"][v["id"]]]
            curves.append({"site": sid, "rating_id": v["id"], "effective_lst": L(v["eff_u"]), "points": pts})
    O["shift_curves.json"] = _Gjson_text({"curves": curves}) + "\n"
    lines = []
    for sid in sorted(S["ice"]):
        for a, b, ea, eb in S["ice"][sid]:
            ks = S["kp"].get((sid, a), [])
            nread = sum(1 for (s2, t) in S["UV"] if s2 == sid and a <= t and (b is None or t < b))
            lines.append(_Gjson_text({"site": sid, "on_lst": L(a), "off_lst": L(b) if b is not None else None, "on_entry": ea, "off_entry": eb,
                                      "k_points": [{"meas_no": no, "time_lst": L(t), "k": _GN(k, 3)} for t, k, no in ks],
                                      "default_k": None if ks else _GN(_Gfr(W["memo"]["winter"][sid]), 2), "unit_values": nread}))
    O["ice_periods.jsonl"] = "".join(x + "\n" for x in lines)
    rt = []
    for sid in sorted(S["RS"]):
        for v in S["RS"][sid]:
            rt.append({"rating_id": v["id"], "site": sid, "effective_lst": L(v["eff_u"]),
                       "points": [{"gh_ft": _GN(_Gfr(h), 2), "q_cfs": _GN(_Gfr(q)), "offset_ft": _GN(_Gfr(e), 2)} for h, q, e in v["points"]],
                       "errata_applied": [{"gh_ft": _GN(_Gfr(a["gh"]), 2), "from_q_cfs": _GN(_Gfr(a["from"])), "to_q_cfs": _GN(_Gfr(a["to"]))} for a in v["applied"]]})
    O["rating_tables_used.json"] = _Gjson_text({"ratings": rt}) + "\n"
    rows = []
    for (sid, d), r in sorted(S["DV"].items()):
        rows.append([sid, d.isoformat(), _Gtxt(r["q"]) if r["q"] is not None else "", _Gtxt(_GF(r["cov"], 3600), 2), r["n"], ";".join(r["codes"])])
    O["daily_values.csv"] = _Gtab(["site", "date", "q_mean_cfs", "coverage_h", "n_readings", "codes"], rows, ",")
    x = [f'<monthly_summary network="{P["network"]}" period_start="{P["period_start"]}" period_end="{P["period_end"]}">']
    for m in S["MON"]:
        f = lambda v: "" if v is None else _Gtxt(v)  # noqa: E731
        x.append(f'  <month site="{m["site"]}" month="{m["month"]}" days="{m["days"]}" complete_days="{m["complete_days"]}" '
                 f'mean_cfs="{f(m["mean"])}" min_cfs="{f(m["min"])}" max_cfs="{f(m["max"])}" '
                 f'volume_af="{"" if m["volume"] is None else _Gtxt(m["volume"], 1)}" runoff_in="{"" if m["runoff"] is None else _Gtxt(m["runoff"], 2)}" '
                 f'complete="{"true" if m["complete"] else "false"}"/>')
    x.append("</monthly_summary>")
    O["monthly_summary.xml"] = "\n".join(x) + "\n"
    st = []
    for p in S["PST"]:
        st.append({"site": p["site"], "peak_q_cfs": _GN(p["peak"][0]) if p["peak"] else None, "peak_time_lst": L(p["peak"][1]) if p["peak"] else None,
                   "min_7day_cfs": _GN(_Gdv(p["min7"][0])) if p["min7"] else None, "min_7day_start": p["min7"][1].isoformat() if p["min7"] else None,
                   "mean_cfs": _GN(p["mean"]) if p["mean"] is not None else None, "complete_days": p["complete_days"], "inc_days": p["inc_days"],
                   "ice_days": p["ice_days"], "backup_days": p["backup_days"], "above_rating_days": p["above_rating_days"],
                   "shift_points": p["shift_points"], "ice_measurements": p["ice_measurements"]})
    O["period_statistics.json"] = _Gjson_text({"sites": st}) + "\n"
    rows = [[t, sid, n] for (t, sid), n in sorted(S["toks"].items())]
    O["alias_resolution.csv"] = _Gtab(["token", "site", "records"], rows, ",")
    C = S["C"]
    O["dedup_report.json"] = _Gjson_text({k: C[k] for k in ["files_read", "records_read", "unknown_site", "out_of_scope", "unrouted",
                                                             "out_of_window", "admitted", "superseded", "duplicates", "voided", "edits_applied",
                                                             "edits_ignored", "edit_deleted", "sensor_fault", "backup_unused", "kept"]}) + "\n"
    O["source_lineage.json"] = _Gjson_text({"files": S["lineage"]}) + "\n"
    lines = []
    for (sid, sen, t), why, f in sorted(S["excl"], key=lambda e: (e[0][0], e[0][2], e[0][1])):
        lines.append(_Gjson_text({"site": sid, "sensor": sen, "time_lst": L(t), "reason": why, "file": f}))
    O["reading_exclusions.jsonl"] = "".join(x + "\n" for x in lines)
    rows = [[e["seq"], e["site"], e["sensor"], L(e["t"]), e["op"], e["status"]] for e in S["ledger"]]
    O["amendment_ledger.psv"] = _Gtab(["seq", "site", "sensor", "time_lst", "op", "status"], rows, "|")
    y = [("network", P["network"]), ("period_start", P["period_start"]), ("period_end", P["period_end"]), ("rating_sheet", P["rating_sheet"]),
         ("index_sheet", P["index_sheet"]), ("site_sheet", P["site_sheet"]), ("max_gap_minutes", str(P["max_gap"])),
         ("min_coverage_fraction", _Gtxt(P["min_cov"], 2)), ("record_margin_hours", str(P["margin_h"])), ("drift_tolerance_default_ft", P["drift_tol"]),
         ("tolerance_table", "T-2"), ("tolerance_E_pct", W["memo"]["tol"]["E"]), ("tolerance_G_pct", W["memo"]["tol"]["G"]),
         ("tolerance_F_pct", W["memo"]["tol"]["F"]), ("winter_table", "W-1"), ("errata_table", "R-2"),
         ("errata_applied", str(sum(len(v["applied"]) for vs in S["RS"].values() for v in vs))),
         ("date_system", "1904" if W["cfg"]["date1904"] else "1900"), ("clock_standard_offset_minutes", str(clock["std"])), ("dst_rule", clock["rule"])]
    for sid in sorted(P["tol_site"]):
        y.append((f"drift_tolerance_{sid}", P["tol_site"][sid]))
        y.append((f"max_gap_{sid}", str(P["gap_site"][sid])))
        y.append((f"winter_k_{sid}", W["memo"]["winter"][sid]))
    O["parameters_used.yaml"] = "".join(f"{k}: {v}\n" for k, v in y)
    pubd = {(r["site"], r["date"]): r for r in W["published"] if r["site"] in S["RS"]}
    rows = []
    for key in sorted(set(pubd) | set(S["DV"])):
        pr, rr = pubd.get(key), S["DV"].get(key)
        pq = pr["q"] if pr else None
        rq = rr["q"] if rr else None
        if pq is None and rq is None:
            continue
        diff = rq - pq if pq is not None and rq is not None else None
        stt = "ONLY_PUBLISHED" if rq is None else "ONLY_RECOMPUTED" if pq is None else "MATCH" if diff == 0 else "DIFF"
        rows.append([key[0], key[1].isoformat(), _Gtxt(pq) if pq is not None else "", _Gtxt(rq) if rq is not None else "",
                     _Gtxt(diff) if diff is not None else "", stt])
    O["variance_vs_published.csv"] = _Gtab(["site", "date", "published_cfs", "recomputed_cfs", "diff_cfs", "status"], rows, ",")
    bym = {m["no"]: m for m in S["meas"]}
    rows = []
    for r in sorted(W["shift_pub"], key=lambda r: r["no"]):
        m = bym.get(r["no"])
        if m is None:
            rows.append([r["no"], r["site"], r["decision"], _Gtxt(r["shift"], 2) if r["shift"] is not None else "", "", "", "NOT_FOUND"])
            continue
        agree = m["decision"] == r["decision"] and (m["decision"] != "SHIFT" or m["shift"] == r["shift"])
        rows.append([r["no"], m["site"], r["decision"], _Gtxt(r["shift"], 2) if r["shift"] is not None else "", m["decision"],
                     _Gtxt(m["shift"], 2) if m["shift"] is not None else "", "AGREE" if agree else "DIFFER"])
    O["shift_vs_published.csv"] = _Gtab(["meas_no", "site", "published_decision", "published_shift_ft", "recomputed_decision",
                                         "recomputed_shift_ft", "status"], rows, ",")
    rows = []
    for r in sorted(W["dashboard"], key=lambda r: (r["site"], r["date"])):
        rr = S["DV"].get((r["site"], r["date"]))
        if rr is None:
            continue
        rice = "Y" if "ICE" in rr["codes"] else "N"
        qok = r["q"] == rr["q"]
        if qok and rice == r["ice"]:
            continue
        rows.append([r["site"], r["date"].isoformat(), _Gtxt(r["q"]) if r["q"] is not None else "", _Gtxt(rr["q"]) if rr["q"] is not None else "",
                     r["ice"], rice, "Y" if qok else "N", "Y" if rice == r["ice"] else "N"])
    O["dashboard_disagreements.tsv"] = _Gtab(["site", "date", "dashboard_cfs", "recomputed_cfs", "dashboard_ice", "recomputed_ice", "q_agrees",
                                              "ice_agrees"], rows, "\t")
    lines = []
    for r in sorted(W["uvcache"], key=lambda r: (r["site"], r["t"])):
        uv = S["UV"].get((r["site"], r["t"]))
        stt = "MISSING" if uv is None else "CURRENT" if uv["q"] == r["q"] else "STALE"
        lines.append(_Gjson_text({"site": r["site"], "time_lst": L(r["t"]), "cached_cfs": _GN(r["q"]), "recomputed_cfs": _GN(uv["q"]) if uv else None,
                                  "status": stt}))
    O["cache_divergence.jsonl"] = "".join(x + "\n" for x in lines)
    md = ["# Streamflow reconciliation", "", "## Summary", "", "| site | published_days | recomputed_days | compared | diff_count | mean_diff_cfs |",
          "|---|---|---|---|---|---|"]
    for sid in sorted(S["RS"]):
        pdays = [k for k, r in pubd.items() if k[0] == sid and r["q"] is not None]
        rdays = [k for k, r in S["DV"].items() if k[0] == sid and r["q"] is not None]
        comp = [k for k in rdays if k in pubd and pubd[k]["q"] is not None]
        diffs = [S["DV"][k]["q"] - pubd[k]["q"] for k in comp]
        md.append(f"| {sid} | {len(pdays)} | {len(rdays)} | {len(comp)} | {sum(1 for d in diffs if d != 0)} | "
                  f"{_Gtxt(sum(diffs, _GF(0)) / len(diffs), 2) if diffs else ''} |")
    md += ["", "## Run settings", "", "| setting | published_run | in_force |", "|---|---|---|"]
    inf = _G_runsettings_in_force(P)
    for k, v in _GRUN:
        md.append(f"| {k} | {v} | {inf[k]} |")
    md += ["", "## Measurement decisions", "", "| site | measurements | shift | check | ice | rejected | no_record |", "|---|---|---|---|---|---|---|"]
    for sid in sorted(S["RS"]):
        ms = [m for m in S["meas"] if m["site"] == sid]
        md.append(f"| {sid} | {len(ms)} | " + " | ".join(str(sum(1 for m in ms if m["decision"] == d)) for d in ("SHIFT", "CHECK", "ICE", "REJECTED", "NO_RECORD")) + " |")
    O["reconciliation.md"] = "\n".join(md) + "\n"
    return O


def _G_derive(W, flip=frozenset()):
    S = W["S"] if not flip and "S" in W else _G_compute(W, frozenset(flip))
    return _G_render(W, S)
# ---------------------------------------------------------------------------- shard writers
def _G_write(path, text: str) -> None:
    _GPath(path).write_text(text, encoding="utf-8", newline="\n")


def _Gz(u):
    return _Gnaive(u).strftime("%Y-%m-%dT%H:%M:%SZ")


def _G_yq(s):
    return "'" + str(s).replace("'", "''") + "'"


def _G_group(recs, keyf):
    out, idx = [], {}
    for r in recs:
        k = keyf(r)
        if k not in idx:
            idx[k] = len(out)
            out.append((k, []))
        out[idx[k]][1].append(r)
    return out


def _G_write_shard(W, path, L, recs, rng):  # noqa: C901
    lid = L[0]
    clock = W["clock"]
    std = clock["std"]
    if lid == "L01":
        lines = ["# CBHS logger export, long format, stage in the logger unit of the equipment register", "station,sensor,obs_utc,stage,qual,rev,void"]
        for k, r in enumerate(recs):
            if k and k % 700 == 0:
                lines.append("")
                lines.append(f"# block {k // 700 + 1}")
            lines.append(f"{r['tok']},{r['sensor']},{_Gz(r['t'])},{r['val']},{r['q']},{r['rev']},{1 if r['void'] else 0}")
        _G_write(path, "\n".join(lines) + "\n")
    elif lid == "L02":
        lines = ["site_id,date_lst,hour,m00,m15,m30,m45,unit,rev"]
        groups = _G_group(recs, lambda r: (r["tok"], r["unit"], r["rev"], (r["t"] + std * 60) // 3600))
        last_day = None
        for (tok, unit, rev, hour), rs in groups:
            slot = {((r["t"] + std * 60) % 3600) // 900: r["val"] for r in rs}
            d = _Gnaive(hour * 3600).date()
            lines.append(f"{tok},{d.isoformat()},{_Gnaive(hour * 3600).hour},{slot.get(0, '')},{slot.get(1, '')},{slot.get(2, '')},{slot.get(3, '')},"
                         f"{unit.lower()},{rev}")
            if last_day is not None and d != last_day and rng.random() < 0.5:
                lines.append(f"{tok},{last_day.isoformat()},MEAN,{rs[0]['val']},,,,{unit.lower()},{rev}")
            last_day = d
        _G_write(path, "\n".join(lines) + "\n")
    elif lid == "L03":
        qm = {"G": "OK", "S": "SUS", "E": "EST", "X": "FLT"}
        lines = ["# exported by RF-telemetry gateway", "# decimal separator: comma", "gauge\tchan\tt_epoch\th\tunit\tflag\trevision\tstatus"]
        for r in recs:
            v = r["val"].replace(".", ",") if r["val"] else ""
            lines.append(f"{r['tok']}\t{1 if r['sensor'] == 'P' else 2}\t{r['t']}\t{v}\t{r['unit']}\t{qm[r['q']]}\t{r['rev']}\t{'VOID' if r['void'] else 'ACTIVE'}")
        _G_write(path, "\n".join(lines) + "\n")
    elif lid == "L04":
        qm = {"G": "A", "S": "S", "E": "E", "X": "F"}
        head = "STN\tSENSOR\tWALLCLOCK\tGH\tQ\tREV"
        lines = [head]
        for k, r in enumerate(recs):
            if k and k % 500 == 0:
                lines.append(head)
            w = _Gnaive(_Gwall_of(r["t"], clock)).strftime("%Y-%m-%d %H:%M")
            lines.append(f"{r['tok']}\t{'PRI' if r['sensor'] == 'P' else 'BAK'}\t{w}\t{r['val']}\t{qm[r['q']]}\t{r['rev']}")
        _G_write(path, "\n".join(lines) + "\n")
    elif lid == "L05":
        qm = {"G": "0", "S": "1", "E": "2", "X": "9"}
        lines = ["site|sens|ts_ms|value_cm|q|rv|vd"]
        for r in recs:
            lines.append(f"{r['tok']}|{1 if r['sensor'] == 'P' else 2}|{r['t'] * 1000}|{r['val']}|{qm[r['q']]}|{r['rev']}|{'Y' if r['void'] else 'N'}")
        _G_write(path, "\n".join(lines) + "\n")
    elif lid == "L06":
        lines = ["alias|when|stage|code|ver"]
        for r in recs:
            off = rng.choice([0, std, std + (60 if _Gis_dst(r["t"], clock) else 0)])
            sgn = "+" if off >= 0 else "-"
            ts = _Gnaive(r["t"] + off * 60).strftime("%Y-%m-%dT%H:%M:%S") + f"{sgn}{abs(off) // 60:02d}:{abs(off) % 60:02d}"
            suf = {"FT": rng.choice(["ft", "FT", " ft"]), "M": rng.choice(["m", " m", "M"])}[r["unit"]]
            lines.append(f"{r['tok']}|{ts}|{r['val']}{suf}|{r['q'].lower()}|{r['rev']}")
        _G_write(path, "\n".join(lines) + "\n")
    elif lid == "L07":
        out = []
        for k, r in enumerate(recs):
            if k % 400 == 0:
                out.append(_Gjson.dumps({"type": "hb", "gateway": "TQ-4", "seq": k}))
            out.append(_Gjson.dumps({"s": r["tok"], "k": r["sensor"], "t": _Gnaive(r["t"] + std * 60).strftime("%Y%m%dT%H%M"),
                                     "v": r["val"], "u": r["unit"].lower(), "q": r["q"], "r": r["rev"], "x": r["void"]}))
        _G_write(path, "\n".join(out) + "\n")
    elif lid == "L08":
        qm = {"G": "good", "S": "suspect", "E": "estimated", "X": "fault"}
        out = []
        for r in recs:
            val = None if r["void"] else _GNum(r["val"])
            o = {"station": {"id": r["tok"]}, "reading": {"time_utc": _Gnaive(r["t"]).strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                                                          "gh": {"value": val, "unit": r["unit"]}},
                 "meta": {"channel": "primary" if r["sensor"] == "P" else "backup", "rev": r["rev"], "void": r["void"], "quality": qm[r["q"]]}}
            out.append(_Gjson_text(o))
        _G_write(path, "\n".join(out) + "\n")
    elif lid == "L09":
        out = []
        groups = _G_group(recs, lambda r: (r["tok"], r["unit"], r["rev"], r["t"] // 3600))
        for (tok, unit, rev, hour), rs in groups:
            vals = [None, None, None, None]
            for r in rs:
                vals[(r["t"] % 3600) // 900] = _GNum(r["val"])
            out.append(_Gjson_text({"site": tok, "hour_utc": _Gnaive(hour * 3600).strftime("%Y-%m-%dT%H"), "vals": vals, "unit": unit.lower(), "rev": rev}))
        _G_write(path, "\n".join(out) + "\n")
    elif lid == "L10":
        out = []
        for r in recs:
            out.append(_Gjson_text({"id": r["tok"], "sensor": "backup", "epoch": r["t"], "stage_m": None if r["void"] else _GNum(r["val"]),
                                    "qa": r["q"], "rev": r["rev"], "deleted": 1 if r["void"] else 0}))
        _G_write(path, "\n".join(out) + "\n")
    elif lid == "L11":
        qm = {"G": "GOOD", "S": "SUSP", "E": "EST", "X": "FAULT"}
        x = ['<?xml version="1.0" encoding="UTF-8"?>', "<batch source=\"KD-hub\">", "  <!-- stage values are in the logger unit of the equipment register -->"]
        for tok, rs in _G_group(recs, lambda r: r["tok"]):
            x.append(f'  <site code="{tok}">')
            for r in rs:
                vd = ' void="1"' if r["void"] else ""
                x.append(f'    <r s="{r["sensor"]}" t="{_Gz(r["t"])}" v="{r["val"]}" q="{qm[r["q"]]}" rev="{r["rev"]}"{vd}/>')
            x.append("  </site>")
        x.append("</batch>")
        _G_write(path, "\n".join(x) + "\n")
    elif lid == "L12":
        qm = {"G": "10", "S": "30", "E": "40", "X": "90"}
        x = ['<?xml version="1.0" encoding="UTF-8"?>', "<export>"]
        for r in recs:
            zone = rng.choice(["UTC", "LST", "LOCAL"])
            u = r["t"] if zone == "UTC" else r["t"] + std * 60 if zone == "LST" else _Gwall_of(r["t"], clock)
            x.append(f'  <reading><station>{r["tok"]}</station><time zone="{zone}">{_Gnaive(u).strftime("%d/%m/%Y %H:%M")}</time>'
                     f'<value unit="{r["unit"].lower()}">{r["val"]}</value><qual>{qm[r["q"]]}</qual><rev>{r["rev"]}</rev></reading>')
        x.append("</export>")
        _G_write(path, "\n".join(x) + "\n")
    elif lid == "L13":
        lines = ["CBHS FIXED WIDTH STAGE REPORT", "STATION   DATE       TIME VALUE   UN Q RV", "-" * 40]
        for k, r in enumerate(recs):
            if k and k % 600 == 0:
                lines += [f"PAGE {k // 600}", "STATION   DATE       TIME VALUE   UN Q RV", "-" * 40]
            n = _Gnaive(r["t"] + std * 60)
            lines.append(f"{r['tok']:<10}{n.strftime('%Y-%m-%d')} {n.strftime('%H%M')} {r['val']:>7} {r['unit']:<2} {r['q']} {r['rev']:>2}")
        lines.append("END OF REPORT")
        _G_write(path, "\n".join(lines) + "\n")
    elif lid == "L14":
        lines = []
        for k, r in enumerate(recs):
            if k % 350 == 0:
                lines.append(f"NOTE gateway=PR-7 batch={k // 350 + 1}")
            ts = _Gnaive(r["t"]).strftime("%Y-%m-%d %H:%M:%S") + "Z"
            if r["void"]:
                lines.append(f"VOID stn={r['tok']} sensor={r['sensor']} t={ts.replace(' ', 'T')} rev={r['rev']}")
            else:
                lines.append(f"{ts} stn={r['tok']} sensor={r['sensor']} gh={r['val']}{r['unit'].lower()} q={r['q']} rev={r['rev']}")
        _G_write(path, "\n".join(lines) + "\n")
    elif lid == "L15":
        y = ["# YB gateway dump: one block per station, sensor and unit; rows are [epoch_s, value, quality, rev]", "blocks:"]
        for (tok, sen, unit), rs in _G_group(recs, lambda r: (r["tok"], r["sensor"], r["unit"])):
            y.append(f"  - station: {_G_yq(tok) if rng.random() < 0.6 else tok}")
            y.append(f"    sensor: {'primary' if sen == 'P' else 'backup'}")
            y.append(f"    unit: {unit.lower()}")
            y.append("    rows:")
            for r in rs:
                y.append(f"      - [{r['t']}, {r['val']}, {r['q'].lower()}, {r['rev']}]")
        _G_write(path, "\n".join(y) + "\n")
    elif lid == "L16":
        y = ["# QS export: station -> UTC minute -> reading", "stations:"]
        flow = W["cfg"]["yaml_flow"]
        for tok, rs in _G_group(recs, lambda r: r["tok"]):
            y.append(f"  {_G_yq(tok) if (tok.isdigit() or rng.random() < 0.5) else tok}:")
            for t, same in _G_group(rs, lambda r: r["t"]):
                key = _Gnaive(t).strftime("%Y-%m-%dT%H:%MZ")
                if len(same) > 1:
                    y.append(f"    '{key}': [" + ", ".join(f"{{v: {r['val']}, u: {r['unit'].lower()}, r: {r['rev']}}}" for r in same) + "]")
                    continue
                r = same[0]
                if flow or rng.random() < 0.5:
                    y.append(f"    '{key}': {{v: {r['val']}, u: {r['unit'].lower()}, r: {r['rev']}}}")
                else:
                    y.append(f"    '{key}':")
                    y.append(f"      v: {r['val']}")
                    y.append(f"      u: {r['unit'].lower()}")
                    y.append(f"      r: {r['rev']}")
        _G_write(path, "\n".join(y) + "\n")
    elif lid == "L17":
        series = []
        for (tok, sen, unit, rev, day), rs in _G_group(recs, lambda r: (r["tok"], r["sensor"], r["unit"], r["rev"], r["t"] // 86400)):
            step = W["site"][rs[0]["site"]]["interval"] if rs[0]["site"] in W["site"] else 900
            start = day * 86400
            vals = [None] * (86400 // step)
            for r in rs:
                vals[(r["t"] - start) // step] = _GNum(r["val"])
            while vals and vals[-1] is None:
                vals.pop()
            o = {"site": tok, "sensor": sen, "start": start, "step": step, "rev": rev, "values": vals}
            if unit != "FT":
                o["unit"] = unit.lower()
            series.append(o)
        _G_write(path, _Gjson_text({"meta": {"unit": "ft", "clock": "utc", "producer": "MA-archive"}, "series": series}) + "\n")
    elif lid == "L18":
        if _GPath(path).exists():
            _GPath(path).unlink()
        con = _Gsqlite3.connect(str(path))
        con.execute("CREATE TABLE sites (sid INTEGER PRIMARY KEY, token TEXT)")
        con.execute("CREATE TABLE readings (rid INTEGER PRIMARY KEY, sid INTEGER, sensor TEXT, t_serial REAL, value REAL, unit TEXT, q TEXT, rev INTEGER, void INTEGER)")
        sids = {}
        for r in recs:
            if r["tok"] not in sids:
                sids[r["tok"]] = len(sids) + 11
                con.execute("INSERT INTO sites VALUES (?, ?)", (sids[r["tok"]], r["tok"]))
        base = _Gday_utc(_Gdate(1899, 12, 30))
        for r in recs:
            ser = (r["t"] + std * 60 - base) / 86400.0
            con.execute("INSERT INTO readings (sid, sensor, t_serial, value, unit, q, rev, void) VALUES (?,?,?,?,?,?,?,?)",
                        (sids[r["tok"]], r["sensor"], ser, None if r["void"] else float(r["val"]), r["unit"], r["q"], r["rev"], 1 if r["void"] else 0))
        con.commit()
        con.close()
    elif lid == "L19":
        if _GPath(path).exists():
            _GPath(path).unlink()
        con = _Gsqlite3.connect(str(path))
        con.execute("CREATE TABLE obs (stn TEXT, ts INTEGER, gh_mm INTEGER, sensor TEXT, rev INTEGER, flag TEXT)")
        con.execute("CREATE TABLE voids (stn TEXT, ts INTEGER, sensor TEXT, rev INTEGER)")
        fm = {"G": "", "S": "S", "E": "E", "X": "X"}
        for r in recs:
            if r["void"]:
                con.execute("INSERT INTO voids VALUES (?,?,?,?)", (r["tok"], r["t"], r["sensor"], r["rev"]))
            else:
                con.execute("INSERT INTO obs VALUES (?,?,?,?,?,?)", (r["tok"], r["t"], int(r["val"]), r["sensor"], r["rev"], fm[r["q"]]))
        con.commit()
        con.close()
    elif lid == "L20":
        lines = ["site,time_lst,gh_ft,source"]
        for r in recs:
            lines.append(f"{r['tok']},{_Glst(r['t'], clock)},{r['val']},stage_cache")
        _G_write(path, "\n".join(lines) + "\n")
# ---------------------------------------------------------------------------- support registers
_GSUPPORT = {
    "catalog": "ingest_catalog.json", "stations": "stn_master.csv", "alias": "stn_xref.sqlite", "alias_add": "xref_addendum.yml",
    "visits": "fv_ledger_q2.db", "visit_am": "fv_amend.xml", "meas": "qm_main_26q2.csv", "meas_late": "qm_late.xml", "ice": "ice_obs_j2.ndjson",
    "datum": "dtm_hist.psv", "equip": "eqp_reg.tsv", "edits": "uv_edits.jsonl", "profile": "dv_profile.yml", "overlay": "site_overlay.yaml",
    "clock": "site_clock.yaml", "published": "dv_pub_26q2.csv", "pub_stats": "pub_stats_26q2.json", "dashboard": "hydro_dash_export.tsv",
    "uvcache": "uv_cache_r3.jsonl", "shift_pub": "shift_wksht_pub.csv", "bulletin": "ops_bulletin_feb.txt", "quickref": "field_quickref.txt",
    "draft": "hydrometry_handbook_r7_draft.md", "profile_draft": "dv_profile_draft.yml", "legacy_xml": "rating_export_2025.xml",
    "pack": "dv_compute_pack.md", "workbook": "cbhs_rt_26q2.xlsx", "memo": "hrb_26-04_minutes.pdf",
    "handbook": "hydrometry_handbook.md", "layouts": "feed_layouts.md", "contract": "output_contract.md",
}


def _G_write_support(W, data, rng):  # noqa: C901
    cfg = W["cfg"]
    clock = W["clock"]
    std = clock["std"]
    L = lambda u: _Glst(u, clock)  # noqa: E731
    # ingest catalog
    files = [{"file": f, "layout": W["lay"][f][0] if f in W["lay"] else rng.choice(["L01", "L11"]),
              "status": "ARCHIVED" if f in _GARCHIVED else "ACTIVE"} for f in W["catalog"]["order"]]
    routes = [{"route": r["route"], "file": r["file"], "site": r["site"], "sensor": r["sensor"], "from_utc": _Gz(r["from"]),
               "to_utc": _Gz(r["to"]), "status": r["status"]} for r in W["catalog"]["routes"]]
    _G_write(data / "ingest_catalog.json", _Gjson.dumps({"catalog": "CBHS ingest routing, revision 12",
                                                           "note": "file_order is the processing order; routes are half-open UTC windows",
                                                           "file_order": [x["file"] for x in files], "files": files, "routes": routes}, indent=1) + "\n")
    # station master
    rows = [[s["id"], s["name"], s["network"], s["status"], s["area_km2"], f"{rng.uniform(44, 49):.4f}", f"{rng.uniform(-97, -91):.4f}",
             str(rng.randint(1931, 2019))] for s in W["stations"]]
    rng.shuffle(rows)
    _G_write(data / "stn_master.csv", _Gtab(["station_id", "station_name", "network", "status", "area_km2_legacy", "lat", "lon", "established"], rows, ","))
    # alias register (sqlite) and addendum (yml)
    p = data / "stn_xref.sqlite"
    if p.exists():
        p.unlink()
    con = _Gsqlite3.connect(str(p))
    con.execute("CREATE TABLE xref (token TEXT, target TEXT, valid_from TEXT, valid_to TEXT, kind TEXT)")
    al = list(W["aliases"])
    rng.shuffle(al)
    for r in al:
        con.execute("INSERT INTO xref VALUES (?,?,?,?,?)", (r["token"], r["target"], r["from"], r["to"] or None, r["kind"]))
    con.commit()
    con.close()
    y = ["# cross-reference addendum; a row with the token and valid_from of a register row replaces that row", "rows:"]
    add = list(W["alias_add"])
    rng.shuffle(add)
    for r in add:
        y.append(f"  - token: {_G_yq(r['token'])}")
        y.append(f"    target: {_G_yq(r['target'])}")
        y.append(f"    valid_from: {r['from']}")
        y.append(f"    valid_to: {r['to'] or 'null'}")
        y.append(f"    note: {r['note']}")
    _G_write(data / "xref_addendum.yml", "\n".join(y) + "\n")
    # field visit ledger
    p = data / "fv_ledger_q2.db"
    if p.exists():
        p.unlink()
    con = _Gsqlite3.connect(str(p))
    con.execute("CREATE TABLE visit (vid INTEGER PRIMARY KEY, stn TEXT, vdate TEXT, vtime TEXT, logger_ft TEXT, action TEXT, party TEXT)")
    con.execute("CREATE TABLE vref (vid INTEGER, method TEXT, reading_ft TEXT, note TEXT)")
    vs = list(W["visits"] + W["visits_other"])
    rng.shuffle(vs)
    for v in vs:
        n = _Gnaive(v["t"] + std * 60)
        con.execute("INSERT INTO visit VALUES (?,?,?,?,?,?,?)", (v["vid"], v["tok"], n.strftime("%Y-%m-%d"), n.strftime("%H%M"), v["display"],
                                                                 v["action"] if rng.random() < 0.8 else v["action"].lower(), v["party"]))
        for m, x in v["refs"]:
            con.execute("INSERT INTO vref VALUES (?,?,?,?)", (v["vid"], m, x, rng.choice(["", "", "calm", "wind chop", "ice at staff"])))
    con.commit()
    con.close()
    x = ['<?xml version="1.0" encoding="UTF-8"?>', "<visit_amendments>"]
    am = list(W["visit_amends"])
    rng.shuffle(am)
    for a in am:
        attrs = f'no="{a["no"]}" visit="{a["visit"]}" field="{a["field"]}"'
        if "method" in a and a["field"] == "reference":
            attrs += f' method="{a["method"]}"'
        body = a.get("value", "")
        x.append(f"  <amend {attrs}>{body}</amend>")
    x.append("</visit_amendments>")
    _G_write(data / "fv_amend.xml", "\n".join(x) + "\n")
    # measurements
    rows = []
    for m in W["meas"] + W["meas_other"]:
        off = rng.choice([std, 0])
        sgn = "+" if off >= 0 else "-"
        z = f"{sgn}{abs(off) // 60:02d}:{abs(off) % 60:02d}"
        rows.append([m["no"], m["tok"], _Gnaive(m["start"] + off * 60).strftime("%Y-%m-%dT%H:%M") + z,
                     _Gnaive(m["end"] + off * 60).strftime("%Y-%m-%dT%H:%M") + z, _Gtxt(m["q"]), m["grade"], m["cover"], m["field_gh"],
                     m["method"], m["party"], _Gz(m["entered"])])
    rng.shuffle(rows)
    _G_write(data / "qm_main_26q2.csv", _Gtab(["meas_no", "station", "start", "end", "q_cfs", "grade", "cover", "field_gh_ft", "method", "party",
                                                  "entered_utc"], rows, ","))
    x = ['<?xml version="1.0" encoding="UTF-8"?>', '<late_measurements unit_note="discharge in cubic metres per second">']
    late = list(W["meas_late"]) + [dict(m, cms=True, q=m["q"], entered=m["entered"] + rng.choice([-1, 1]) * rng.randint(1, 9) * 3600)
                                   for m in rng.sample(W["meas_other"], 190)]
    rng.shuffle(late)
    for m in late:
        qc = _Gsig(m["q"] * _GCFS, 4)
        x.append(f'  <measurement no="{m["no"]}"><station>{m["tok"]}</station><start>{L(m["start"])}</start><end>{L(m["end"])}</end>'
                 f'<q unit="cms">{_Gtxt(qc)}</q><grade>{m["grade"]}</grade><cover>{m["cover"]}</cover><field_gh_ft>{m["field_gh"]}</field_gh_ft>'
                 f'<entered>{_Gz(m["entered"])}</entered></measurement>')
    x.append("</late_measurements>")
    _G_write(data / "qm_late.xml", "\n".join(x) + "\n")
    # ice observations
    out = []
    ents = list(W["icelog"])
    rng.shuffle(ents)
    for e in ents:
        o = {"entry": e["entry"], "kind": e["kind"]}
        if "tok" in e:
            o["station"] = e["tok"]
        if "target" in e:
            o["target"] = e["target"]
        if "at" in e:
            o["at_lst"] = L(e["at"])
        o["observer"] = rng.choice(["JKL", "MRV", "TSO", "AHB"])
        out.append(_Gjson.dumps(o))
    _G_write(data / "ice_obs_j2.ndjson", "\n".join(out) + "\n")
    # datum history, equipment register
    rows = [[r["site"], r["sensor"], _Gz(r["from"]), r["offset"], r["status"], r["mark"], r["note"]] for r in W["datum_rows"]]
    rng.shuffle(rows)
    _G_write(data / "dtm_hist.psv", _Gtab(["site", "sensor", "valid_from_utc", "offset_ft", "status", "ref_mark", "note"], rows, "|"))
    rows = [[r["site"], r["sensor"], L(r["from"]), r["event"], r["unit"], r["model"], r["serial"]] for r in W["equip_rows"]]
    rng.shuffle(rows)
    _G_write(data / "eqp_reg.tsv", _Gtab(["site", "sensor", "valid_from_lst", "event", "unit", "model", "serial"], rows, "\t"))
    # unit-value edits (file order is not seq order)
    out = []
    for e in W["edits"]:
        o = {"seq": e["seq"], "station": e["tok"], "sensor": e["sensor"], "time_lst": L(e["t"]), "op": e["op"]}
        if e["op"] == "SET":
            o["value"] = e["value"]
            o["unit"] = e["unit"].lower()
        o["by"] = rng.choice(["JKL", "MRV", "TSO"])
        out.append(_Gjson.dumps(o))
    _G_write(data / "uv_edits.jsonl", "\n".join(out) + "\n")
    # profile, overlay, clock
    y = ["# streamflow computation profile; settings of the network named by `network` apply", f"network: {cfg['network']}",
         f"period_start: {cfg['period_start']}", f"period_end: {cfg['period_end']}  # exclusive", "networks:"]
    for net in _GNETS:
        mine = net == cfg["network"]
        y.append(f"  {net}:")
        y.append(f"    rating_sheet: {cfg['rating_sheet'] if mine else rng.choice(['Ratings_2025', 'Ratings_S26', 'Ratings_2026_DRAFT'])}")
        y.append(f"    index_sheet: {cfg['index_sheet'] if mine else 'RatingIndex_25'}")
        y.append(f"    site_sheet: {cfg['site_sheet'] if mine else 'Sites_Legacy'}")
        y.append(f"    max_gap_minutes: {cfg['max_gap_min'] if mine else rng.choice([45, 90, 120])}")
        y.append(f"    min_coverage_fraction: {cfg['min_cov'] if mine else rng.choice(['0.80', '0.95'])}")
        y.append(f"    record_margin_hours: {cfg['margin_h'] if mine else 12}")
        y.append(f"    drift_tolerance_ft: {cfg['drift_tol'] if mine else rng.choice(['0.03', '0.05'])}")
        y.append(f"    publication_batch: {rng.choice(['B1', 'B2', 'B3'])}-{net[-1]}")
        y.append("    notify:")
        for k in range(rng.randint(3, 6)):
            y.append(f"      - {rng.choice(['ops', 'review', 'archive', 'web'])}-{net.lower()}-{k}@cbhs.example")
        y.append("    publication_stations:  # pages built by the web publisher; not the computation scope")
        for st in W["stations"]:
            if st["network"] == net:
                y.append(f"      - {_G_yq(st['id'])}")
        y.append("    calendar:")
        d = W["ps"]
        while d < W["pe"]:
            y.append(f"      - {{batch_date: {d.isoformat()}, cutoff_lst: '{rng.choice(['06:00', '12:00'])}'}}")
            d += _Gtd(days=rng.choice([7, 14]))
    _G_write(data / "dv_profile.yml", "\n".join(y) + "\n")
    y = ["# per-site settings; a setting named here wins over the workbook site sheet and the profile for that site", "sites:"]
    ov = dict(W["overlay_other"])
    ov.update(W["overlay"])
    for sid in sorted(ov):
        y.append(f"  {_G_yq(sid)}:")
        for k, v in sorted(ov[sid].items()):
            y.append(f"    {k}: {v}")
        y.append(f"    contact: {rng.choice(['north-desk', 'south-desk', 'east-desk', 'west-desk'])}")
        y.append(f"    reviewed: {(W['ps'] - _Gtd(days=rng.randint(5, 200))).isoformat()}")
    _G_write(data / "site_overlay.yaml", "\n".join(y) + "\n")
    y = ["# network clock: local standard time is UTC plus standard_offset_minutes; daylight time adds 60 minutes",
         f"standard_offset_minutes: {std}", f"dst_rule: {clock['rule']}",
         "rules:", "  us: second Sunday of March 02:00 local standard time until first Sunday of November 01:00 local standard time",
         "  eu: last Sunday of March 01:00 UTC until last Sunday of October 01:00 UTC", "  none: no daylight time", "transitions:"]
    for yr in range(1900, 2100):
        sp = _Gdst_span(clock["rule"], yr, std)
        if sp:
            y.append(f"  - {{year: {yr}, start_utc: '{_Gz(sp[0])}', end_utc: '{_Gz(sp[1])}'}}")
        else:
            y.append(f"  - {{year: {yr}, start_utc: null, end_utc: null}}")
    _G_write(data / "site_clock.yaml", "\n".join(y) + "\n")


def _G_write_decoys(W, data, rng):  # noqa: C901
    clock = W["clock"]
    L = lambda u: _Glst(u, clock)  # noqa: E731
    rows = [[r["site"], r["date"].isoformat(), _Gtxt(r["q"]) if r["q"] is not None else "", ";".join(r["codes"]), "P26Q2"] for r in W["published"]]
    _G_write(data / "dv_pub_26q2.csv", _Gtab(["site", "date", "q_mean_cfs", "codes", "batch"], rows, ","))
    recs = []
    for p in W["pub_stats"]:
        for k in ("peak", "min7", "mean", "complete_days", "inc_days", "ice_days", "backup_days", "above_rating_days", "shift_points", "ice_measurements"):
            v = p[k]
            if k == "peak":
                recs.append({"site": p["site"], "stat": "peak_q_cfs", "value": _Gtxt(v[0]) if v else None})
                recs.append({"site": p["site"], "stat": "peak_time_lst", "value": L(v[1]) if v else None})
            elif k == "min7":
                recs.append({"site": p["site"], "stat": "min_7day_cfs", "value": _Gtxt(_Gdv(v[0])) if v else None})
                recs.append({"site": p["site"], "stat": "min_7day_start", "value": v[1].isoformat() if v else None})
            elif k == "mean":
                recs.append({"site": p["site"], "stat": "mean_cfs", "value": _Gtxt(v) if v is not None else None})
            else:
                recs.append({"site": p["site"], "stat": k, "value": str(v)})
    for m in W["pub_mon"]:
        for k in ("mean", "min", "max"):
            recs.append({"site": m["site"], "stat": f"{k}_cfs_{m['month']}", "value": _Gtxt(m[k]) if m[k] is not None else None})
        recs.append({"site": m["site"], "stat": f"volume_af_{m['month']}", "value": _Gtxt(_Gq(m["sum"] * _GF(19835, 10000), 1), 1) if m["volume"] is not None else None})
    _G_write(data / "pub_stats_26q2.json", _Gjson.dumps({"batch": "P26Q2", "acre_feet_per_cfs_day": "1.9835", "stats": recs}, indent=1) + "\n")
    rows = []
    for r in W["dashboard"]:
        tok = W["station"][r["site"]]["short"]
        rows.append([tok, r["date"].isoformat(), _Gtxt(r["q"]) if r["q"] is not None else "", r["ice"], _Gz(r["updated"])])
    _G_write(data / "hydro_dash_export.tsv", _Gtab(["station", "date", "daily_cfs", "ice_flag", "updated_utc"], rows, "\t"))
    out = []
    for r in W["uvcache"]:
        out.append(_Gjson_text({"station": "CB" + r["site"], "t_lst": L(r["t"]), "q_cfs": _GN(r["q"]), "cache": "r3"}))
    _G_write(data / "uv_cache_r3.jsonl", "\n".join(out) + "\n")
    rows = []
    for r in W["shift_pub"]:
        rows.append([r["no"], r["site"], r["decision"], _Gtxt(r["shift"], 2) if r["shift"] is not None else "", _Gtxt(r["dev"], 1) if r["dev"] is not None else "",
                     "previous quarter" if r.get("prev") else "P26Q2"])
    _G_write(data / "shift_wksht_pub.csv", _Gtab(["meas_no", "site", "decision", "shift_ft", "deviation_pct", "batch"], rows, ","))
    # bulletin with stale notices
    lines = ["CBHS OPERATIONS BULLETIN - FEBRUARY", "Unofficial notices for field crews. Not a source for computation.", ""]
    for k in range(230):
        s = rng.choice(W["stations"])
        kind = rng.random()
        if kind < 0.25:
            lines.append(f"N{k + 1:03d} ice reported at {s['id']} {s['name']} on {(W['ps'] + _Gtd(days=rng.randint(0, 80))).isoformat()} (crew report)")
        elif kind < 0.45:
            g = rng.choice("EGF")
            lines.append(f"N{k + 1:03d} reminder: grade {g} measurements shift the rating beyond {W['memo']['tol_old'][g]} percent")
        elif kind < 0.6:
            lines.append(f"N{k + 1:03d} winter coefficient for {s['id']} is {W['memo']['winter_old'][s['id']]} until breakup")
        elif kind < 0.75:
            lines.append(f"N{k + 1:03d} logger at {s['short']} swapped; readings now in metres")
        else:
            lines.append(f"N{k + 1:03d} daily means are the rating of the day's mean stage for quick-look products")
    _G_write(data / "ops_bulletin_feb.txt", "\n".join(lines) + "\n")
    lines = ["FIELD QUICK REFERENCE (crew card, 2024 edition)", "", "conversions:", "  1 m = 3.2808 ft", "  1 m3/s = 35.31 cfs", "  1 cfs-day = 1.9835 acre-ft",
             "  round half up", "", "grade tolerances (percent):"]
    for g in "EGF":
        lines.append(f"  {g}: {W['memo']['tol_old'][g]}")
    lines += ["", "staff gage priority: STAFF, WIRE, TAPE", "", "station card:"]
    for s in W["stations"]:
        lines.append(f"  {s['id']} {s['short']:<10} area {s['area_km2']} km2 drift tol {rng.choice(['0.02', '0.05'])} ft")
    _G_write(data / "field_quickref.txt", "\n".join(lines) + "\n")
    y = ["# DRAFT profile for the next quarter; not in force", f"network: {W['cfg']['network']}", "networks:"]
    for net in _GNETS:
        y.append(f"  {net}:")
        y.append(f"    rating_sheet: Ratings_2026_DRAFT")
        y.append(f"    max_gap_minutes: {rng.choice([30, 120, 180])}")
        y.append(f"    min_coverage_fraction: {rng.choice(['0.75', '0.85'])}")
        y.append("    sites:")
        for s in rng.sample(W["stations"], 46):
            y.append(f"      {_G_yq(s['id'])}: {{drift_tolerance_ft: {rng.choice(['0.01', '0.05'])}}}")
    _G_write(data / "dv_profile_draft.yml", "\n".join(y) + "\n")
    x = ['<?xml version="1.0" encoding="UTF-8"?>', '<rating_export system="legacy" status="superseded 2025-12-01">']
    for s in W["sites"]:
        for v in s["versions"]:
            x.append(f'  <rating id="{v["id"]}" site="{s["id"]}">')
            for h, q, e in v["old_points"]:
                x.append(f'    <point gh="{h}" q="{q}" offset="{e}"/>')
            x.append("  </rating>")
    for st in rng.sample([x2 for x2 in W["stations"] if x2["id"] not in W["site"]], 12):
        x.append(f'  <rating id="{st["id"]}-R07" site="{st["id"]}">')
        h = rng.uniform(0.5, 2.0)
        q = rng.uniform(1, 20)
        for k in range(12):
            x.append(f'    <point gh="{h + 0.4 * k:.2f}" q="{_Gtxt(_Gsig(_GF(q * (1.6 ** k)), 3))}" offset="{h - 0.3:.2f}"/>')
        x.append("  </rating>")
    x.append("</rating_export>")
    _G_write(data / "rating_export_2025.xml", "\n".join(x) + "\n")
# ---------------------------------------------------------------------------- workbook and memo
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
        ct.append(f'<Override PartName="/xl/worksheets/sheet{file_order[k]}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
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
            info = _Gzipfile.ZipInfo(name, date_time=(2026, 4, 9, 9, 0, 0))
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


def _G_cell(rng, text, frac):
    """A decimal value written either as a number cell or as text (sometimes padded)."""
    u = rng.random()
    if u >= frac:
        return float(text)
    if u < frac / 3:
        return " " + text
    return text


def _G_write_workbook(W, data, rng):  # noqa: C901
    cfg = W["cfg"]
    d1904 = cfg["date1904"]
    nt = cfg["num_text"]
    std = W["clock"]["std"]

    def eff_cells(u):
        n = _Gnaive(u + std * 60)
        return _Gserial(n.date(), d1904), n.strftime("%H:%M")
    others = [x for x in W["stations"] if x["id"] not in W["site"]]
    idx = [["Rating version index"], ["effective_date is a workbook date serial; effective_time is local standard time"], [],
           ["rating_id", "site", "effective_date", "effective_time", "status", "note"]]
    allv = []
    for s in W["sites"]:
        for v in s["versions"]:
            allv.append((v, "ACTIVE", "in force"))
    for v in W["withdrawn_versions"]:
        allv.append((v, "WITHDRAWN", "withdrawn on review"))
    for v in W["draft_versions"]:
        allv.append((v, "DRAFT", "draft for next quarter"))
    fake = []
    for st in rng.sample(others, 40):
        n0 = rng.randint(3, 30)
        fv = {"id": f"{st['id']}-R{n0:02d}", "site": st["id"], "eff_u": W["ws"] - rng.randint(30, 900) * 86400 + 9 * 3600,
              "points": [(f"{1.0 + 0.5 * k:.2f}", _Gtxt(_Gsig(_GF(rng.uniform(2, 9)) * (k + 1) ** 2, 3)), "0.60") for k in range(6)]}
        fake.append(fv)
        allv.append((fv, rng.choice(["ACTIVE", "ACTIVE", "WITHDRAWN"]), "network"))
    rng.shuffle(allv)
    for v, stt, note in allv:
        dser, tt = eff_cells(v["eff_u"])
        idx.append([v["id"], v["site"], dser, tt, stt if rng.random() < 0.85 else stt.title(), note])
    old_idx = [["Rating version index, 2025 programme"], [], ["rating_id", "site", "effective_date", "effective_time", "status", "note"]]
    for s in W["sites"]:
        for v in s["versions"]:
            dser, tt = eff_cells(v["eff_u"] - rng.randint(5, 60) * 86400)
            old_idx.append([v["id"], s["id"], dser, tt, "ACTIVE", "2025 programme"])

    def pts_sheet(title, items):
        rows = [[title], ["gh_ft and offset_ft in feet; q_cfs in cubic feet per second"], [], ["rating_id", "gh_ft", "q_cfs", "offset_ft", "remark"]]
        for k, (rid, pts) in enumerate(items):
            if k == len(items) // 2:
                rows.append(["continued"])
            for h, q, e in pts:
                rows.append([rid, _G_cell(rng, h, nt), _G_cell(rng, q, nt), _G_cell(rng, e, nt), ""])
        return rows
    inforce = [(v["id"], v["points"]) for s in W["sites"] for v in s["versions"]] + [(v["id"], v["points"]) for v in W["withdrawn_versions"]]
    inforce += [(v["id"], v["points"]) for v in fake]
    rng.shuffle(inforce)
    old = [(v["id"], v["old_points"]) for s in W["sites"] for v in s["versions"]]
    draft = [(v["id"], v["points"]) for v in W["draft_versions"]]
    sites = [["Site constants"], [], ["site", "name", "drainage_area_mi2", "drift_tol_ft", "note"]]
    st_rows = list(W["stations"])
    rng.shuffle(st_rows)
    for st in st_rows:
        sites.append([st["id"], st["name"], _G_cell(rng, st["area_mi2"], nt), _G_cell(rng, st["drift_tol"], nt) if st["drift_tol"] else "", ""])
    legacy = [["Legacy site constants (2019)"], [], ["site", "drainage_area_mi2", "drift_tol_ft"]]
    for st in st_rows:
        legacy.append([st["id"], _G_cell(rng, _Gtxt(_Gq(_Gfr(st["area_mi2"]) * _GF(rng.randint(90, 110), 100), 1)), nt), "0.05"])
    sheets = [("Cover", [["Corvel Basin Hydrometric Service rating workbook"],
                         ["The profile names the rating sheet, the index sheet and the site sheet in force."],
                         ["Superseded and draft sheets are kept for audit only."]], False),
              (cfg["index_sheet"], idx, False), ("RatingIndex_25", old_idx, False),
              (cfg["rating_sheet"], pts_sheet("Rating points in force", inforce), False),
              ("Ratings_2025", pts_sheet("Rating points, 2025 programme (superseded)", old), False),
              ("Ratings_2026_DRAFT", pts_sheet("DRAFT rating points", draft), True),
              (cfg["site_sheet"], sites, False), ("Sites_Legacy", legacy, False)]
    order = list(range(1, len(sheets) + 1))
    rng.shuffle(order)
    _G_xlsx(data / "cbhs_rt_26q2.xlsx", sheets, order, rng, d1904, cfg["xlsx_runs"], cfg["xlsx_no_r"])


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
                ops.append(f"BT /F1 7 Tf 1 0 0 1 36 {y} Tm {shows[0]} " + " ".join(f"86 0 Td {sh}" for sh in shows[1:]) + " ET")
            else:
                for k, show in enumerate(shows):
                    ops.append(f"BT /F1 7 Tf 1 0 0 1 {36 + 86 * k} {y} Tm {show} ET")
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
    _GPath(path).write_bytes(bytes(out))


def _G_write_memo(W, data, rng):  # noqa: C901
    cfg = W["cfg"]
    M = W["memo"]
    blocks = []

    def table(tid, title, status, head, rows):
        blocks.append((tid, f"Table {tid}: {title} [{status}]", head, rows))
    prose = [["Hydrometric Review Board minutes HRB 26-04"],
             ["Tables marked IN FORCE govern the computation of the record. Other tables are kept for history."],
             ["Grades of measurements follow Table M-1 where a measurement is listed there."]]
    table("T-1", "Measurement grade tolerances", "WITHDRAWN 2025-09-30", ["grade", "tolerance_pct", "use"],
          [[g, M["tol_old"][g], "shift when exceeded"] for g in "EGF"] + [["P", "n/a", "check only"]])
    table("T-2", "Measurement grade tolerances", "IN FORCE", ["grade", "tolerance_pct", "use"],
          [[g, M["tol"][g], "shift when exceeded"] for g in "EGF"] + [["P", "n/a", "never a shift point"]])
    scope = set(W["scope"])
    wst = sorted(W["stations"], key=lambda s: s["id"])
    table("W-0", "Winter coefficients", "SUPERSEDED", ["station", "default_k"], [[s["id"], M["winter_old"][s["id"]]] for s in wst if s["id"] in scope])
    table("R-1", "Rating errata", "WITHDRAWN", ["rating_id", "gh_ft", "q_cfs", "was_q_cfs"], [[e["rating"], e["gh"], e["q"], e["was"]] for e in M["errata_old"]])
    table("W-1", "Winter coefficients", "IN FORCE", ["station", "default_k"], [[s["id"], M["winter"][s["id"]]] for s in wst])
    table("R-2", "Rating errata", "IN FORCE", ["rating_id", "gh_ft", "q_cfs", "was_q_cfs"], [[e["rating"], e["gh"], e["q"], e["was"]] for e in M["errata"]])
    table("V-1", "Field visits disregarded", "IN FORCE", ["visit_id", "station", "reason"],
          [[str(v["vid"]), v["tok"], rng.choice(["reference mark disturbed", "tape reading unverified", "logger clock fault"])] for v in M["disregard"]])
    rr = []
    toks = {m["no"]: m["tok"] for m in W["meas"] + W["meas_other"]}
    for no in sorted(W["review"]):
        vv, gg, note = W["review"][no]
        rr.append([str(no), toks.get(no, ""), vv, gg, note])
    table("M-1", "Measurement review", "IN FORCE", ["meas_no", "station", "verdict", "grade", "note"], rr)
    order = ["T-1", "T-2", "W-0", "R-1", "W-1", "R-2", "V-1", "M-1"]
    rng.shuffle(order)
    blocks.sort(key=lambda b: order.index(b[0]))
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
        cur.append(["Rows above apply as printed."] if rng.random() < 0.3 else [""])
    pages.append(cur)
    pages = [[c for c in pg if c != [""]] for pg in pages]
    _G_pdf(data / "hrb_26-04_minutes.pdf", pages, rng, "HRB 26-04", cfg["pdf_octal"], cfg["pdf_td"])
# ---------------------------------------------------------------------------- documents
_GHANDBOOK = """# CBHS streamflow computation handbook (revision 11)

This handbook fixes how the Corvel Basin Hydrometric Service computes the quarterly streamflow record of a network
from its logger shards, field visits, discharge measurements and ice observations. Sections are cited as H1 to H18.
Every computed figure follows these rules. A rule that names a memo table, a workbook sheet or a register takes its
values from that table, sheet or register at run time. File names below are the names used in the data directory.

## H1 Order of authority

1. Tables of the review board minutes `hrb_26-04_minutes.pdf` whose title ends with `[IN FORCE]`.
   The status of a table is the bracketed text at the end of its title line. A table whose status is anything else
   (WITHDRAWN, SUPERSEDED, DRAFT) is history and is never applied. A table may continue on later pages under a
   line `Table <id> (continued)` that repeats the column header. Text lines of a single cell (titles, notes, page
   footers) are not table rows. Cells of a row share one baseline and sit in columns 86 points apart.
2. The sheets of the rating workbook `cbhs_rt_26q2.xlsx` named by the profile: `rating_sheet` for rating points,
   `index_sheet` for rating versions and `site_sheet` for site constants. No other sheet is applied, whatever its title.
   Sheet names are the names in `xl/workbook.xml`; the part file of a sheet is found through its relationship id in
   `xl/_rels/workbook.xml.rels`. The workbook date system is the `date1904` flag of `xl/workbook.xml`. A sheet holds a
   title, notes and one header row; rows after the header that hold fewer than two cells (such as `continued`) are notes.
3. Settings: for each site, a setting present in its entry of `site_overlay.yaml` wins; otherwise the value of the
   workbook site sheet where H2 names one; otherwise the value of the profile block of the network; otherwise the
   default of this handbook.
4. The registers: station master `stn_master.csv`, cross-reference `stn_xref.sqlite` with `xref_addendum.yml`,
   equipment register `eqp_reg.tsv`, datum history `dtm_hist.psv`, field visit ledger `fv_ledger_q2.db` with
   `fv_amend.xml`, measurements `qm_main_26q2.csv` and `qm_late.xml`, ice observations `ice_obs_j2.ndjson`,
   unit-value edits `uv_edits.jsonl`, the ingest catalog `ingest_catalog.json` and the shards it lists.
5. Everything else is informational: the saved compute pack, the published daily values, statistics and shift
   worksheet, the dashboard export, the unit-value cache, bulletins, quick references, draft handbooks, draft
   profiles and the legacy rating export. None of it is an input to any computed figure. The comparison reports of
   H17 read some of it only to compare.

## H2 Scope, period and settings

- A station is in scope when its station master row has status ACTIVE and its network equals the profile `network`.
  Sites are reported in ascending station id.
- `dv_profile.yml` names the network, `period_start` and `period_end` (LST dates; the end date is excluded).
  The block `networks.<network>` holds the settings of that network: rating_sheet, index_sheet, site_sheet,
  max_gap_minutes, min_coverage_fraction, record_margin_hours and drift_tolerance_ft. Blocks of other networks
  do not apply.
- The record window runs from period_start 00:00 LST minus record_margin_hours to period_end 00:00 LST plus
  record_margin_hours, half open.
- Drift tolerance of a site: overlay `drift_tolerance_ft`, else the non-empty `drift_tol_ft` of the site sheet,
  else the profile drift_tolerance_ft.
- Maximum gap of a site: overlay `max_gap_minutes`, else the profile max_gap_minutes.
- Drainage area of a site: `drainage_area_mi2` of the site sheet. The station master area is a legacy figure in km2.

## H3 Time

- `site_clock.yaml` gives standard_offset_minutes and dst_rule. Local standard time (LST) is UTC plus the standard
  offset all year. Local wall-clock time is LST plus 60 minutes while daylight time is in effect; the UTC start and
  end of daylight time of each year follow the dst_rule and are listed under `transitions`.
- A wall-clock time maps to the UTC instant whose wall-clock reading it is. Times inside the skipped spring hour
  do not occur in the data.
- An ISO time with a numeric offset is converted with that offset; a trailing Z means UTC.
- Every time written in a report is LST as `YYYY-MM-DD HH:MM`. A day is an LST calendar day.
- Workbook date serials count days in the workbook date system: day 0 is 1899-12-30 in the 1900 system and
  1904-01-01 in the 1904 system.
- A serial time (layout L18) is a fraction of LST days in the 1900 system; its instant is serial times 86400
  seconds rounded to the nearest whole minute.

## H4 Ingest and routing

- `ingest_catalog.json` lists the shard files in `file_order`, which is the processing order. A listed file that is
  absent from the directory is skipped. A file that is not listed is never read as a shard, whatever its name.
- A listed file is read with the layout id the catalog gives for it; `feed_layouts.md` describes every layout.
- Every reading value of a file is one record; a wide row gives one record per non-empty value. Lines that a layout
  marks as non-data (comments, repeated headers, heartbeats, notes, summary rows, page lines) are not records.
- Each record meets four tests in this order, and the first test it fails names its counter:
  1. its station token resolves (H5) at the record instant, else `unknown_site`;
  2. the station is in scope, else `out_of_scope`;
  3. an ACTIVE route of the same file, station and sensor covers the record instant, else `unrouted`.
     Routes are half-open UTC windows `[from_utc, to_utc)`. RETIRED routes never cover anything;
  4. the instant lies inside the record window, else `out_of_window`.
- A record that passes all four is `admitted`. Only admitted records take part in H6.

## H5 Station tokens

- A token is normalized by trimming it and writing it in upper case; an all-digit token shorter than 8 characters is
  left-padded with zeros to 8 characters.
- A normalized token equal to the id of a station master row is that station.
- Otherwise the cross-reference applies: the rows of table `xref` of `stn_xref.sqlite` and the rows of
  `xref_addendum.yml`. An addendum row whose normalized token and valid_from equal those of a register row replaces
  that register row. A row applies at instant u when `valid_from <= u < valid_to`; an empty or null valid_to is open.
  The target of the applying row is resolved again in the same way at the same instant, following at most six
  rows in all. A token with no applying row, or one that would need a seventh row, is unresolved.
- Tokens of the registers resolve at the instant of their entry: visit time, measurement instant (H11), ice entry
  time, edit time. Dashboard tokens resolve at 12:00 LST of the row date and cache tokens at the cached instant.
- Worked example: token `ashby-wr` normalizes to `ASHBY-WR`; a CHAIN row `ASHBYWR -> ASHBY-WR` and a SHORT row
  `ASHBY-WR -> 04117250` mean `ashbywr` resolves in two steps to `04117250`.

## H6 Revisions, duplicates and voids

- Admitted records with the same station, sensor and UTC instant are copies of one reading.
- The copy with the highest revision wins. Among copies of that revision, the copy in the file that comes latest in
  file_order wins. Copies of lower revisions count as `superseded`; the other copies of the winning revision count
  as `duplicates`.
- When the winning copy is a void, the reading is removed and counts as `voided`. A void never falls back to a
  copy of a lower revision.

## H7 Unit-value edits

- `uv_edits.jsonl` is applied in ascending `seq`, which is not its line order, to the readings that survive H6.
- An edit names a station token, a sensor and an LST time. Edits of stations out of scope are skipped and not
  listed.
- SET replaces the value and the unit (a value as the logger records it, before the datum offset) and sets the
  quality to G. It acts only on a reading that exists and is not deleted.
- DELETE removes an existing reading. RESTORE reinstates a reading as it was at its last DELETE; a RESTORE with
  no deleted reading to reinstate does nothing.
- An edit that does nothing is IGNORED; every other edit is APPLIED. Readings still deleted when the journal ends
  count as `edit_deleted`.

## H8 Quality, units, datum and sensors

- Quality codes are G (good), S (suspect), E (estimated) and X (fault); feed_layouts.md maps each layout
  vocabulary to them. A layout without a quality field gives G. After H7, readings of quality X are removed and
  count as `sensor_fault`; S and E readings are kept.
- Unit: a record that carries its own unit (a unit column, a value suffix, a block, row or series unit, or a fixed
  layout unit) uses it. A record without one uses the unit of the equipment register row of its station and sensor
  with the latest valid_from_lst at or before the instant, whatever the event of that row.
- Feet: ft = m / 0.3048 = cm / 30.48 = mm / 304.8, exactly.
- Datum: the gage-datum stage is the value in feet plus `offset_ft` of the ACTIVE row of `dtm_hist.psv` of the
  station and sensor with the latest valid_from_utc at or before the instant. WITHDRAWN rows never apply.
- Sensor selection: at each station and instant the primary (P) reading is used when one survives; otherwise the
  backup (B) reading. A backup reading at an instant whose primary reading survives counts as `backup_unused`.
  `kept` counts the selected readings.

## H9 Field visits and gage-height corrections

- Visits are the rows of table `visit` of `fv_ledger_q2.db` (time in LST from vdate and vtime HHMM; `logger_ft` is
  the uncorrected gage-datum stage the logger showed) with their reference readings in table `vref`.
- `fv_amend.xml` is replayed in ascending `no`: field `reference` sets the reading of the named method, `action`
  sets the action, `time` sets the visit time (LST), `logger` sets logger_ft and `void` removes the visit.
  Amendments of a voided visit do nothing. Action and method words compare without regard to case.
- A visit listed in memo Table V-1 is disregarded. Voided and disregarded visits take no part in corrections.
- The reference reading of a visit is TAPE when present, else WIRE, else STAFF. CSG readings are never used.
- error = reference - logger_ft. applied = error when the absolute error is at least the drift tolerance (H2),
  otherwise 0.
- The used visits of a site in time order v0 .. vn define the correction c(t). For tk <= t < tk+1:
  c(t) = ak + (bk+1 - ak) x (t - tk) / (tk+1 - tk), where bk+1 is the applied value of vk+1 and ak is 0 when the
  action of vk is RESET and the applied value of vk otherwise. For t >= tn, c(t) = an.
- Corrected gage height = gage-datum stage + c(t), computed exactly and rounded to 2 decimals (H18). Backup
  readings take the same c(t).
- Worked example: a RESET visit at 2026-01-10 12:00 and a visit at 2026-01-24 12:00 with applied +0.06 give
  c = 0.06 x 13/28 at 2026-01-17 00:00. A reading of 1.312 m with offset -0.50 is 4.304461942 - 0.50 + 0.027857143
  = 3.832319085 ft, so the corrected gage height is 3.83.

## H10 Ratings

- Versions are the rows of the index sheet whose status is ACTIVE (any case). The effective instant of a version is
  its effective_date serial (H3) at its effective_time, in LST. The version in force at instant t is the ACTIVE
  version of the site with the latest effective instant at or before t.
- The points of a version are the rows of the rating sheet with its rating_id: gh_ft, q_cfs and offset_ft. Cells
  may hold numbers or text with surrounding spaces. Points are taken in ascending gh.
- Memo Table R-2 errata replace q_cfs of the point with the same rating_id and gh_ft.
- Evaluation R(h): when h equals the gh of a point, R is the q of that point. Otherwise take segment i with
  gh_i <= h < gh_i+1, segment 0 when h is below gh_0, and the last segment when h is above the last point:
  beta = ln(q_i+1 / q_i) / ln((gh_i+1 - e_i) / (gh_i - e_i)), with e_i the offset of point i, and
  R = q_i x ((h - e_i) / (gh_i - e_i)) ** beta. When h is below gh_0 and h <= e_0, R = 0.
- R is computed in IEEE binary64 with natural logarithms and the power operator, then rounded to 4 significant
  figures (H18) from the exact value of the binary64 result. A gage height above the last point is above rating.
- Inverse R^-1(Q): take segment i with q_i <= Q < q_i+1 (segment 0 below q_0, the last segment above the last point) and
  h = e_i + (gh_i - e_i) x (Q / q_i) ** (1 / beta), in binary64, rounded to 2 decimals (H18).
- Worked example: points (2.00, 15.0, offset 1.20) and (3.00, 61.0, offset 1.20) give beta = 1.7298944 and
  R(2.50) = 34.741240 -> 34.74; R(1.20) = 0; R^-1(34.2) = 2.4882536 -> 2.49.

## H11 Measurements

- Measurements come from `qm_main_26q2.csv` (q_cfs) and `qm_late.xml` (cubic metres per second; cfs = cms /
  0.028316846592 exactly, without rounding). When both files hold a meas_no, the entry with the later entered_utc
  wins.
- The instant of a measurement is the midpoint of start and end, truncated down to the whole minute. Its station
  token resolves at that instant; measurements of stations out of scope are not reported.
- Memo Table M-1: verdict REJECT makes the measurement REJECTED; verdict REGRADE replaces the field grade with the
  grade of the table; ACCEPT, or no row, keeps the field grade.
- Record gage height: the exact mean of the corrected gage heights (H9) of the selected readings (H8) whose instant
  lies in [start, end], both ends included, rounded to 2 decimals. When there is none the measurement is NO_RECORD.
  The field sheet gage height is informational.
- Decisions are taken in this order: REJECTED; NO_RECORD; ICE when the instant lies in an ice period (H13) of the
  site, whatever the cover field says; otherwise the open-water evaluation.
- Open-water evaluation, per site in instant order, under the version in force at the instant: shift_in_use is the
  shift of the latest SHIFT decision so far under the same version, 0.00 when there is none; rated Q =
  R(gh + shift_in_use); deviation = (measured - rated) / rated x 100, rounded to 1 decimal; the tolerance is the
  memo Table T-2 percentage of the grade, and grade P has none. The decision is SHIFT when the grade has a
  tolerance and the absolute deviation is strictly greater than it, with shift = R^-1(measured) - gh; otherwise CHECK.
- ICE measurements: shift_in_use is the curve shift s(t) of H12 at the instant, rated Q = R(gh + s(t)) and
  k = measured / rated, rounded to 3 decimals.
- Worked example (points of H10): gh 2.50 with shift_in_use 0.04 gives rated R(2.54) = 36.61; a grade G measurement
  of 41.6 cfs deviates by 13.6 percent; R^-1(41.6) = 2.64, so the shift is 0.14.

## H12 Shift curves

- Each ACTIVE version of a site has a curve: a START point at its effective instant with shift 0.00, followed by
  the SHIFT points of its measurements in instant order.
- The shift s(t) at an instant under a version varies linearly in time between consecutive points and stays at the
  last point after it; it is rounded to 2 decimals.

## H13 Ice periods and winter factors

- `ice_obs_j2.ndjson` is replayed in ascending `entry`. ON and OFF entries create events at at_lst for their station
  (resolved at that time). AMEND sets the time of its target event to its own at_lst. WITHDRAW removes its target
  event. An AMEND or WITHDRAW whose target does not exist, or was withdrawn, does nothing.
- Per site, events sorted by time and then entry: an ON opens a period when none is open, an OFF closes the open
  period, and any other event does nothing. A period still open at the end has no end. A period is [on, off).
- The K points of a period are its ICE measurements (H11) as (instant, k). In the period K(t) is the first k up to
  the first point, varies linearly in time between points (rounded to 3 decimals) and keeps the last k after the
  last point. A period without K points uses default_k of memo Table W-1 for the site.
- In a period, Q = K(t) x Q_open rounded to 4 significant figures.

## H14 Unit values

- For every selected reading in the record window: gh = corrected gage height (H9); shift = s(t) of the version in
  force (H12); gh_eff = gh + shift; Q_open = R(gh_eff) (H10); in an ice period K and Q follow H13, otherwise
  Q = Q_open.
- Flags, in this order and written together with no separator: B for a backup reading, I inside an ice period,
  > above rating. A backup reading inside an ice period carries `BI`.

## H15 Daily values

- Per site and LST day of the period, take the selected readings in instant order. Between two consecutive readings
  at most max_gap_minutes apart (H2) Q varies linearly; a longer interval is a gap and carries nothing.
- The integral of a day is the integral of that piecewise-linear Q over the parts of the segments inside the day,
  with the values at the day edges interpolated on their segment. The coverage is the total duration of those parts.
- A day whose coverage is below min_coverage_fraction x 24 hours is INC and has no value. Otherwise the daily mean
  is integral / coverage, exactly, rounded with the discharge table of H18.
- Codes: INC; ICE when a reading of the day is flagged I; B when one is flagged B; > when one is flagged >; joined by
  `;` in that order. n_readings counts the readings whose instant lies in the day.
- Worked example: readings at 23:30 (40.10) and 00:30 (40.70) give 40.40 at midnight, and the half hour after
  midnight contributes (40.40 + 40.70) / 2 x 1800 to the next day.

## H16 Monthly and period statistics

- Months are the LST calendar months of the period. complete_days counts days with a value. mean is the exact mean
  of the rounded daily values of those days, rounded with the discharge table; min and max are taken over the same
  values. volume_af = their sum x 86400 / 43560, rounded to 1 decimal; runoff_in = volume_af x 12 / (drainage area x
  640), rounded to 2 decimals. complete is true when every day of the month has a value. A month without a complete
  day has empty values.
- Period: peak is the largest unit-value Q with its instant in the period, the earliest on ties. min_7day is the
  smallest exact mean of seven consecutive period days that all have values (rounded daily values), rounded with the
  discharge table, the earliest start on ties. mean is the discharge-table rounding of the exact mean of the rounded
  daily values of the days with values. Day counts follow the daily codes; shift_points and ice_measurements count
  SHIFT and ICE decisions.

## H17 Comparisons

- Published daily values: a row compares with the recomputed value of the same site and date. Differences are
  recomputed minus published. Equal values MATCH.
- Published shift worksheet: a row agrees when the recomputed decision is the same and, for SHIFT, the shift too.
  A row whose meas_no has no recomputed measurement is NOT_FOUND.
- Dashboard: a row disagrees when its daily value differs from the recomputed one (empty equals empty) or its ice
  flag differs from Y for a recomputed day coded ICE and N otherwise.
- Unit-value cache: an entry is CURRENT when a unit value exists at its instant with the same Q, STALE when it
  differs, MISSING when there is no unit value.

## H18 Rounding

- Every rounding is half to even, at the named points only: corrected gage height 2 decimals; record gage height
  2 decimals; R and K x Q_open 4 significant figures; R^-1 2 decimals; shift curve values 2 decimals; deviation
  1 decimal; k and K(t) 3 decimals; daily, monthly, seven-day and period means by the discharge table; volume
  1 decimal; runoff 2 decimals; coverage hours 2 decimals.
- Discharge table, with the band chosen from the unrounded value: below 1, 2 decimals; from 1 to below 10,
  1 decimal; from 10 to below 1000, whole numbers; 1000 and above, 3 significant figures.
- Arithmetic between rounding points is exact decimal or rational arithmetic, except the binary64 evaluation of H10.
- Examples: 9.96 -> 10.0; 999.5 -> 1000; 1234.5 -> 1230; 0.125 -> 0.12.
"""


def _G_draft_md():
    t = _GHANDBOOK.replace("revision 11", "revision 7, DRAFT, not in force")
    t = t.replace("strictly greater than it", "at least it")
    t = t.replace("Every rounding is half to even", "Every rounding is half up")
    t = t.replace("The reference reading of a visit is TAPE when present, else WIRE, else STAFF.",
                  "The reference reading of a visit is STAFF when present, else WIRE, else TAPE.")
    t = t.replace("shift_in_use is the\n  shift of the latest SHIFT decision so far under the same version, 0.00 when there is none",
                  "shift_in_use is\n  0.00 for every measurement")
    return "> DRAFT revision 7. Superseded by revision 11 before publication; kept for the review record.\n\n" + t


_GLAYDOC = {
    "L01": ["csv with header `station,sensor,obs_utc,stage,qual,rev,void`; lines starting with # and blank lines are not records",
            "obs_utc: UTC ISO with Z", "stage: decimal in the equipment register unit of the station and sensor", "sensor: P or B",
            "qual: G, S, E, X", "rev: integer revision", "void: 1 marks a void copy (stage empty), 0 otherwise"],
    "L02": ["csv with header `site_id,date_lst,hour,m00,m15,m30,m45,unit,rev`; one row per station, unit, revision and LST hour",
            "m00..m45: values at minute 00, 15, 30 and 45 of the hour; an empty cell is no record", "date_lst and hour: LST date and hour 0 to 23",
            "a row whose hour is MEAN is a summary row and not a record", "unit: ft or m for the whole row", "sensor: always P; quality: none (G)",
            "rev: integer revision; no voids"],
    "L03": ["tsv with header `gauge chan t_epoch h unit flag revision status`; lines starting with # are not records",
            "t_epoch: UTC epoch seconds", "h: decimal with a decimal comma", "unit: FT or M", "chan: 1 is P, 2 is B",
            "flag: OK=G, SUS=S, EST=E, FLT=X", "status: VOID marks a void copy, ACTIVE otherwise"],
    "L04": ["tsv with header `STN SENSOR WALLCLOCK GH Q REV`; the header line repeats every 500 records and is not a record",
            "WALLCLOCK: local wall-clock time YYYY-MM-DD HH:MM (daylight time applies, H3)", "GH: decimal in the equipment register unit",
            "SENSOR: PRI is P, BAK is B", "Q: A=G, S=S, E=E, F=X", "REV: integer revision; no voids"],
    "L05": ["psv with header `site|sens|ts_ms|value_cm|q|rv|vd`", "ts_ms: UTC epoch milliseconds", "value_cm: centimetres",
            "sens: 1 is P, 2 is B", "q: 0=G, 1=S, 2=E, 9=X", "rv: revision", "vd: Y marks a void copy"],
    "L06": ["psv with header `alias|when|stage|code|ver`", "when: ISO time with a numeric offset (any offset)",
            "stage: decimal followed by its unit, ft or m, in any case and with or without a space", "code: g, s, e, x",
            "sensor: always P", "ver: revision; no voids"],
    "L07": ["JSON Lines; objects with `type` hb are heartbeats and not records", "keys: s station, k sensor P or B, t LST compact YYYYMMDDTHHMM,",
            "v value as a string, u unit ft or m, q G/S/E/X, r revision, x true for a void copy"],
    "L08": ["JSON Lines with nested objects", "station.id: token", "reading.time_utc: ISO with +00:00",
            "reading.gh.value: JSON number (null for a void copy); reading.gh.unit: FT or M",
            "meta.channel: primary is P, backup is B", "meta.quality: good=G, suspect=S, estimated=E, fault=X", "meta.rev, meta.void"],
    "L09": ["newline-delimited JSON, one object per station, unit, revision and UTC hour", "hour_utc: YYYY-MM-DDTHH (UTC)",
            "vals: four values at minutes 00, 15, 30, 45 of that UTC hour; null is no record", "unit: ft or m", "sensor: always P; quality: none (G)",
            "rev: revision; no voids"],
    "L10": ["newline-delimited JSON of backup sensors only (sensor B)", "keys: id token, epoch UTC seconds, stage_m metres (null for a void copy),",
            "qa G/S/E/X, rev revision, deleted 1 for a void copy"],
    "L11": ["XML: `<batch>` holds `<site code=token>` elements with `<r>` readings; comments are not records",
            "r@s: P or B", "r@t: UTC ISO with Z", "r@v: decimal in the equipment register unit", "r@q: GOOD=G, SUSP=S, EST=E, FAULT=X",
            "r@rev: revision; r@void=1 marks a void copy"],
    "L12": ["XML: `<export>` holds `<reading>` elements", "station: token", "time@zone: UTC, LST or LOCAL (wall clock, H3); text DD/MM/YYYY HH:MM",
            "value@unit: ft or m", "qual: 10=G, 30=S, 40=E, 90=X", "rev: revision; sensor always P; no voids"],
    "L13": ["fixed-width text; the title, the header, dashed rules, PAGE lines and END OF REPORT are not records",
            "columns by character position (0-based, end exclusive): station 0-10, LST date 10-20, LST time HHMM 21-25,",
            "value 26-33 (right aligned), unit 34-36 (FT or M), quality 37-38 (G/S/E/X), revision 39-41", "sensor: always P; no voids"],
    "L14": ["text log; lines starting with NOTE are not records", "reading lines: `YYYY-MM-DD HH:MM:SSZ stn=<token> sensor=<P|B> gh=<value><ft|m> q=<code> rev=<n>`",
            "time: UTC", "void lines: `VOID stn=<token> sensor=<P|B> t=<YYYY-MM-DDTHH:MM:SSZ> rev=<n>` are void copies"],
    "L15": ["YAML: `blocks` is a list; each block has station, sensor (primary or backup), unit (ft or m) and rows",
            "each row is a flow sequence [epoch_seconds_utc, value, quality g/s/e/x, revision]", "scalars are text as written, quoted or not; no voids"],
    "L16": ["YAML: `stations` maps a station token to a mapping of UTC minute keys `YYYY-MM-DDTHH:MMZ` to readings",
            "a reading is a mapping v (value), u (unit ft or m), r (revision), in flow or block style",
            "a key whose value is a flow list holds several readings of that minute (one per revision)", "sensor: always P; quality: none (G); no voids"],
    "L17": ["JSON document: `meta.unit` is the default unit; `series` is a list of runs",
            "a run has site, sensor, start (UTC epoch seconds), step (seconds), rev, values and an optional unit that overrides meta.unit",
            "value k is at start + k x step; null is no record", "quality: none (G); no voids"],
    "L18": ["SQLite: table sites (sid, token) and table readings (sid, sensor, t_serial, value, unit, q, rev, void)",
            "t_serial: LST serial days in the 1900 system (H3)", "value: REAL in the unit of the unit column (FT or M); its decimal is the shortest text that",
            "round-trips the REAL", "q: G/S/E/X; void 1 marks a void copy (value NULL); records in rid order"],
    "L19": ["SQLite: table obs (stn, ts, gh_mm, sensor, rev, flag) and table voids (stn, ts, sensor, rev)",
            "ts: UTC epoch seconds", "gh_mm: millimetres", "flag: empty=G, S, E, X", "every voids row is a void copy; obs rows come first in record order"],
    "L20": ["csv with header `site,time_lst,gh_ft,source`", "time_lst: LST YYYY-MM-DD HH:MM", "gh_ft: feet", "sensor: always P; quality: none (G); revision 1; no voids"],
}


_GLAYSUM = [("L01", "csv", "UTC ISO", "register", "P/B", "G S E X", "void column"), ("L02", "csv wide", "LST date + hour", "row", "P", "none", "none"),
            ("L03", "tsv", "UTC epoch s", "column", "P/B", "OK SUS EST FLT", "status"), ("L04", "tsv", "wall clock", "register", "P/B", "A S E F", "none"),
            ("L05", "psv", "UTC epoch ms", "cm", "P/B", "0 1 2 9", "vd"), ("L06", "psv", "ISO offset", "suffix", "P", "g s e x", "none"),
            ("L07", "jsonl", "LST compact", "field", "P/B", "G S E X", "x"), ("L08", "jsonl", "UTC ISO", "field", "P/B", "words", "meta.void"),
            ("L09", "ndjson wide", "UTC hour", "row", "P", "none", "none"), ("L10", "ndjson", "UTC epoch s", "m", "B", "G S E X", "deleted"),
            ("L11", "xml", "UTC ISO", "register", "P/B", "words", "void attribute"), ("L12", "xml", "zoned", "attribute", "P", "10 30 40 90", "none"),
            ("L13", "txt fixed", "LST date + HHMM", "column", "P", "G S E X", "none"), ("L14", "txt log", "UTC", "suffix", "P/B", "G S E X", "VOID lines"),
            ("L15", "yaml", "UTC epoch s", "block", "P/B", "g s e x", "none"), ("L16", "yml", "UTC minute key", "field", "P", "none", "none"),
            ("L17", "json series", "UTC epoch start + step", "meta or run", "P/B", "none", "none"),
            ("L18", "sqlite", "LST serial", "column", "P/B", "G S E X", "void column"), ("L19", "db", "UTC epoch s", "mm", "P/B", "flag", "voids table"),
            ("L20", "csv", "LST text", "ft", "P", "none", "none")]


def _G_layouts_md(W):
    out = ["# Shard layouts", "", "The ingest catalog gives the layout id of every listed shard. Every shard is UTF-8. Station tokens resolve under",
           "handbook H5 at the record instant. A record is one reading value; the fields below say where its station, sensor,",
           "instant, value, unit, quality, revision and void mark come from. Where a layout has no sensor field the sensor is P;",
           "where it has no quality field the quality is G; where it has no revision field the revision is 1. Values are decimals",
           "as written. JSON numbers are exact decimals as written.", ""]
    out += ["## Summary", "", "| layout | format | time | unit | sensor | quality | void |", "|---|---|---|---|---|---|---|"]
    for lid, fmt, tm, un, se, qu, vo in _GLAYSUM:
        out.append(f"| {lid} | {fmt} | {tm} | {un} | {se} | {qu} | {vo} |")
    out.append("")
    for lid in sorted(_GLAYDOC):
        out.append(f"## {lid}")
        out.append("")
        for line in _GLAYDOC[lid]:
            out.append(f"- {line}")
        out.append("")
    out += ["## Units and conversions", "", "- ft = m / 0.3048, ft = cm / 30.48, ft = mm / 304.8, exactly (handbook H8).",
            "- A record without its own unit takes the equipment register unit (handbook H8).", "",
            "## Catalog", "", "- file_order: processing order; files: file, layout, status (ARCHIVED files are absent).",
            "- routes: route, file, site (station id), sensor, from_utc, to_utc, status (ACTIVE or RETIRED).", ""]
    return "\n".join(out) + "\n"


_GCONTRACT = [
    ("unit_values.csv", "csv", "one row per selected reading in the record window; sorted by site, time_lst",
     [("site", "station id"), ("time_lst", "YYYY-MM-DD HH:MM"), ("sensor", "P or B"), ("gh_ft", "corrected gage height, 2 decimals"),
      ("shift_ft", "s(t), 2 decimals"), ("gh_eff_ft", "2 decimals"), ("q_open_cfs", "R(gh_eff), 4 significant figures"),
      ("k_factor", "K(t), 3 decimals, empty outside ice periods"), ("q_cfs", "4 significant figures"), ("flags", "B, I, > in that order with no separator (for example BI), or empty")]),
    ("gh_corrections.tsv", "tsv", "one row per correction segment of every site; sorted by site, from_lst",
     [("site", "station id"), ("from_lst", "time of the used visit that opens the segment"), ("to_lst", "time of the next used visit, empty for the last segment"),
      ("start_ft", "ak, 2 decimals"), ("end_ft", "bk+1, 2 decimals; the last segment repeats ak")]),
    ("visit_errors.psv", "psv", "one row per visit of an in-scope site after the amendments, voided ones included; sorted by site, time_lst, visit_id",
     [("site", "station id"), ("visit_id", "integer"), ("time_lst", "visit time"), ("method", "reference method used"),
      ("reference_ft", "2 decimals"), ("logger_ft", "2 decimals"), ("error_ft", "reference minus logger, 2 decimals"),
      ("applied_ft", "2 decimals, empty unless USED"), ("action", "RESET or NONE"), ("status", "USED, DISREGARDED or VOID")]),
    ("measurement_eval.csv", "csv", "one row per measurement of an in-scope site; sorted by meas_no",
     [("meas_no", "integer"), ("site", "station id"), ("instant_lst", "H11 instant"), ("grade", "final grade"), ("verdict", "ACCEPT, REJECT or REGRADE"),
      ("cover", "as recorded"), ("gh_ft", "record gage height, 2 decimals, empty when none"), ("rating_id", "version in force, empty for REJECTED and NO_RECORD"),
      ("shift_in_use_ft", "2 decimals, empty for REJECTED and NO_RECORD"), ("rated_q_cfs", "4 significant figures, empty for REJECTED and NO_RECORD"),
      ("measured_q_cfs", "cfs, 2 decimals"), ("deviation_pct", "1 decimal, open water only"), ("tolerance_pct", "1 decimal, open water grades E, G, F only"),
      ("decision", "SHIFT, CHECK, ICE, REJECTED or NO_RECORD"), ("shift_ft", "2 decimals, SHIFT only"), ("k_factor", "3 decimals, ICE only")]),
    ("shift_curves.json", "json", "object with key curves: one object per ACTIVE version of an in-scope site, sorted by site then effective instant",
     [("site", "station id"), ("rating_id", "id"), ("effective_lst", "effective instant"),
      ("points", "objects time_lst, shift_ft (JSON number, 2 decimals), source (START or the meas_no as a string) in curve order")]),
    ("ice_periods.jsonl", "jsonl", "one object per ice period of an in-scope site after the replay; sorted by site, on_lst",
     [("site", "station id"), ("on_lst", "time"), ("off_lst", "time or null"), ("on_entry", "entry of the ON event"), ("off_entry", "entry of the OFF event or null"),
      ("k_points", "objects meas_no, time_lst, k (JSON number, 3 decimals) in instant order"), ("default_k", "Table W-1 value when there is no K point, else null"),
      ("unit_values", "number of unit values inside the period")]),
    ("rating_tables_used.json", "json", "object with key ratings: one object per ACTIVE version of an in-scope site, sorted by site then effective instant",
     [("rating_id", "id"), ("site", "station id"), ("effective_lst", "effective instant"),
      ("points", "objects gh_ft, q_cfs, offset_ft (JSON numbers) after the errata, ascending gh"),
      ("errata_applied", "objects gh_ft, from_q_cfs, to_q_cfs for each R-2 erratum applied, ascending gh")]),
    ("daily_values.csv", "csv", "one row per in-scope site and period day; sorted by site, date",
     [("site", "station id"), ("date", "YYYY-MM-DD"), ("q_mean_cfs", "discharge table, empty for INC"), ("coverage_h", "coverage in hours, 2 decimals"),
      ("n_readings", "integer"), ("codes", "INC;ICE;B;> subset in that order, or empty")]),
    ("monthly_summary.xml", "xml", "root monthly_summary with attributes network, period_start, period_end; one month element per in-scope site and month",
     [("month@site", "station id"), ("month@month", "YYYY-MM"), ("month@days", "period days in the month"), ("month@complete_days", "integer"),
      ("month@mean_cfs", "discharge table or empty"), ("month@min_cfs", "or empty"), ("month@max_cfs", "or empty"), ("month@volume_af", "1 decimal or empty"),
      ("month@runoff_in", "2 decimals or empty"), ("month@complete", "true or false")]),
    ("period_statistics.json", "json", "object with key sites: one object per in-scope site in id order",
     [("site", "station id"), ("peak_q_cfs", "4 significant figures"), ("peak_time_lst", "time"), ("min_7day_cfs", "discharge table or null"),
      ("min_7day_start", "first date of the window or null"), ("mean_cfs", "discharge table or null"), ("complete_days", "integer"), ("inc_days", "integer"),
      ("ice_days", "integer"), ("backup_days", "integer"), ("above_rating_days", "integer"), ("shift_points", "integer"), ("ice_measurements", "integer")]),
    ("alias_resolution.csv", "csv", "one row per normalized token and in-scope station it resolved to on a shard record, when the token differs from the id; sorted by token, site",
     [("token", "normalized token"), ("site", "station id"), ("records", "records of read shards carrying the token that resolved to the site")]),
    ("dedup_report.json", "json", "one object with integer counters in this order",
     [("files_read", "listed files present"), ("records_read", "records"), ("unknown_site", "H4"), ("out_of_scope", "H4"), ("unrouted", "H4"),
      ("out_of_window", "H4"), ("admitted", "H4"), ("superseded", "H6"), ("duplicates", "H6"), ("voided", "H6"), ("edits_applied", "H7"),
      ("edits_ignored", "H7"), ("edit_deleted", "H7"), ("sensor_fault", "H8"), ("backup_unused", "H8"), ("kept", "H8")]),
    ("source_lineage.json", "json", "object with key files: one object per read file in processing order",
     [("file", "file name"), ("layout", "layout id"), ("records", "integer"), ("unknown_site", "integer"), ("out_of_scope", "integer"),
      ("unrouted", "integer"), ("out_of_window", "integer"), ("admitted", "integer")]),
    ("reading_exclusions.jsonl", "jsonl", "one object per reading removed after admission; sorted by site, time_lst, sensor",
     [("site", "station id"), ("sensor", "P or B"), ("time_lst", "time"), ("reason", "VOIDED, EDIT_DELETED, SENSOR_FAULT or BACKUP_UNUSED"),
      ("file", "file of the winning copy")]),
    ("amendment_ledger.psv", "psv", "one row per unit-value edit of an in-scope station; sorted by seq",
     [("seq", "integer"), ("site", "station id"), ("sensor", "P or B"), ("time_lst", "time"), ("op", "SET, DELETE or RESTORE"), ("status", "APPLIED or IGNORED")]),
    ("parameters_used.yaml", "yaml", "flat key: value lines in this order",
     [("network", "profile"), ("period_start", "profile"), ("period_end", "profile"), ("rating_sheet", "profile block"), ("index_sheet", "profile block"),
      ("site_sheet", "profile block"), ("max_gap_minutes", "profile block"), ("min_coverage_fraction", "2 decimals"), ("record_margin_hours", "profile block"),
      ("drift_tolerance_default_ft", "profile block"), ("tolerance_table", "id of the table applied"), ("tolerance_E_pct", "table value"),
      ("tolerance_G_pct", "table value"), ("tolerance_F_pct", "table value"), ("winter_table", "id"), ("errata_table", "id"),
      ("errata_applied", "number of errata applied"), ("date_system", "1900 or 1904"), ("clock_standard_offset_minutes", "site clock"),
      ("dst_rule", "site clock"), ("drift_tolerance_<site>", "per in-scope site in id order, followed by max_gap_<site> and winter_k_<site>")]),
    ("variance_vs_published.csv", "csv", "one row per site and date published or recomputed with a value; sorted by site, date",
     [("site", "station id"), ("date", "YYYY-MM-DD"), ("published_cfs", "or empty"), ("recomputed_cfs", "or empty"), ("diff_cfs", "recomputed minus published or empty"),
      ("status", "MATCH, DIFF, ONLY_PUBLISHED or ONLY_RECOMPUTED")]),
    ("shift_vs_published.csv", "csv", "one row per row of the published shift worksheet; sorted by meas_no",
     [("meas_no", "integer"), ("site", "station id"), ("published_decision", "as published"), ("published_shift_ft", "2 decimals or empty"),
      ("recomputed_decision", "or empty"), ("recomputed_shift_ft", "2 decimals or empty"), ("status", "AGREE, DIFFER or NOT_FOUND")]),
    ("dashboard_disagreements.tsv", "tsv", "one row per dashboard row of an in-scope site and period day that disagrees; sorted by site, date",
     [("site", "station id"), ("date", "YYYY-MM-DD"), ("dashboard_cfs", "or empty"), ("recomputed_cfs", "or empty"), ("dashboard_ice", "Y or N"),
      ("recomputed_ice", "Y or N"), ("q_agrees", "Y or N"), ("ice_agrees", "Y or N")]),
    ("cache_divergence.jsonl", "jsonl", "one object per cache entry of an in-scope station; sorted by site, time_lst",
     [("site", "station id"), ("time_lst", "time"), ("cached_cfs", "JSON number"), ("recomputed_cfs", "JSON number or null"), ("status", "CURRENT, STALE or MISSING")]),
    ("reconciliation.md", "md", "sections Summary, Run settings and Measurement decisions, each one Markdown table",
     [("Summary", "per in-scope site in id order: site, published_days (published rows with a value), recomputed_days (days with a value), compared (days with both), diff_count (compared days that differ), mean_diff_cfs (mean of recomputed minus published over compared days, 2 decimals)"),
      ("Run settings", "every setting of the compute pack Run settings table in its order: setting, published_run, in_force; in_force is the profile rating_sheet for rating_sheet, T-2 for tolerance_table, R-2 for errata, record_mean, shift_in_use, time_weighted_discharge, local_standard_time, prorated_visit_errors and seq_order for the other settings in the pack order"),
      ("Measurement decisions", "per in-scope site in id order: site, measurements, shift, check, ice, rejected, no_record")]),
]


def _G_contract_md() -> str:
    out = ["# Output contract", "",
           "Every report is UTF-8 with LF line endings and a final newline. Delimited reports carry exactly the header named here, in this order.",
           "Numbers carry the decimals stated here and are compared by value; negative numbers carry a leading minus sign and no number",
           "carries a plus sign. Significant-figure values are written as plain decimals without exponent. JSON reports are one document;",
           "JSON Lines reports hold one object per line. Empty cells and null stand for values that do not apply. Rows of delimited reports",
           "and JSON Lines objects compare as sets, as do the objects of JSON arrays, except the files array of source_lineage.json, whose",
           "order is the processing order, and the points arrays, whose order is stated. `manifest.json` lists the other reports in the",
           "order of this contract: one JSON object whose only key `files` holds an array of objects name, bytes, sha256.", "",
           "| report | format | column or key | content |", "|---|---|---|---|"]
    for name, fmt, rows_note, cols in _GCONTRACT:
        out.append(f"| {name} | {fmt} | (rows) | {rows_note} |")
        for c, note in cols:
            out.append(f"| {name} | {fmt} | {c} | {note} |")
    out += ["", "Times are LST (handbook H3). Station ids are canonical ids of the station master."]
    return "\n".join(out) + "\n"


def _G_pack_md(W, SP):
    out = ["# Saved daily-values compute pack (P26Q2)", "",
           "This pack produced the published daily values, statistics and shift worksheet of batch P26Q2. It is kept as the record",
           "of how the published batch was run.", "", "## Run settings", "", "| setting | value |", "|---|---|"]
    for k, v in _GRUN:
        out.append(f"| {k} | {v} |")
    out += ["", "## Steps", "",
            "1. Read every csv, tsv, psv, json, jsonl, ndjson, xml, txt and yaml file of the directory as a shard.",
            "2. Keep the newest revision of each reading.",
            "3. Convert metres with 3.2808 ft per metre.",
            "4. Evaluate the rating sheet Ratings_2025 for the daily mean gage height of each UTC day.",
            "5. Take the gage height of each measurement from the field sheet.",
            "6. Compare each measurement with the base rating and shift when it deviates beyond Table T-1.",
            "7. Apply the unit-value edits in file order.",
            "8. Report monthly volumes with 1.9835 acre-feet per cfs-day.", "", "## Run log", ""]
    rng = _G_rng(W["seed"], "pack")
    for k, m in enumerate(SP["meas"]):
        out.append(f"- {k + 1:03d} meas {m['no']} site {m['site']} decision {m['decision']} shift {_Gtxt(m['shift'], 2) if m['shift'] is not None else '-'}")
    for (sid, d), r in sorted(SP["DV"].items())[:: max(1, len(SP["DV"]) // 160)]:
        out.append(f"- day {sid} {d.isoformat()} mean {_Gtxt(r['q']) if r['q'] is not None else 'INC'} ({rng.choice(['ok', 'ok', 'late shard'])})")
    return "\n".join(out) + "\n"
# ============================================================================ entry point
def _Ggenerate(data, seed: int, over: dict | None = None) -> dict:
    cfg = _Gcfg(over, seed)
    W = _G_world(seed, cfg)
    _G_timeline(W, _G_rng(seed, "time"))
    _G_measurements(W, _G_rng(seed, "meas"))
    _G_icelog(W, _G_rng(seed, "ice"))
    _G_edits(W, _G_rng(seed, "edits"))
    _G_aliases(W, _G_rng(seed, "alias"))
    _G_shards(W, _G_rng(seed, "shards"))
    _G_memo_data(W, _G_rng(seed, "memo"))
    _G_other_visits(W, _G_rng(seed, "ovisits"))
    _G_visit_amends(W, _G_rng(seed, "vamend"))
    _G_review(W, _G_rng(seed, "review"))
    _G_assign_tokens(W, _G_rng(seed, "tokens"))
    _G_registers(W, _G_rng(seed, "registers"))
    _G_rng(seed, "editorder").shuffle(W["edits"])
    names = [L[1] for L in _GLAYOUTS]
    if cfg["rename"]:
        fn = {f: f"zq{i:02d}_{f.rsplit('.', 1)[0][::-1]}.{f.rsplit('.', 1)[1]}" for i, f in enumerate(sorted(names))}
    else:
        fn = {f: f for f in names}
    W["lay"] = {fn[L[1]]: L for L in _GLAYOUTS}
    W["files"] = {fn[f]: recs for f, recs in W["files"].items()}
    W["catalog"]["order"] = [fn.get(f, f) for f in W["catalog"]["order"]]
    for r in W["catalog"]["routes"]:
        r["file"] = fn.get(r["file"], r["file"])
    S = _G_compute(W)
    _G_fix_ties(W, S, _G_rng(seed, "ties"))
    if W["tie_meas"]:
        S = _G_compute(W)
    SP = _G_compute(W, _GPUB)
    _G_decoy_data(W, S, SP, _G_rng(seed, "decoys"))
    W["S"] = S
    data = _GPath(data)
    data.mkdir(parents=True, exist_ok=True)
    wr = _G_rng(seed, "write")
    for f, L in sorted(W["lay"].items()):
        _G_write_shard(W, data / f, L, W["files"][f], wr)
    _G_write_support(W, data, wr)
    _G_write_decoys(W, data, wr)
    _G_write_workbook(W, data, wr)
    _G_write_memo(W, data, wr)
    _G_write(data / "hydrometry_handbook.md", _GHANDBOOK)
    _G_write(data / "hydrometry_handbook_r7_draft.md", _G_draft_md())
    _G_write(data / "feed_layouts.md", _G_layouts_md(W))
    _G_write(data / "output_contract.md", _G_contract_md())
    _G_write(data / "dv_compute_pack.md", _G_pack_md(W, SP))
    return W



# ============================================================================ grading harness
import ast as _ast
import os as _os
import re as _re
import shutil as _shutil
import subprocess as _subprocess
import sys as _sys
import tempfile as _tempfile
import threading as _threading
import xml.etree.ElementTree as _ET
from decimal import InvalidOperation as _InvalidOperation

from rewardkit import criteria, criterion

SHIPPED_SEED = 6800948404603382707
OUT = _GPath("/app/out")
PROGRAM = OUT / "run_flowrecord.py"
NAMES = list(_GREPORTS)
CORE = list(_GCORE)
_LOCK = _threading.RLock()
_MEMO: dict = {}
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
HELD = {
    "h_reseed": (8823190451277310093, {"pdf_octal": True, "xlsx_runs": True}),
    "h_zone": (2871604438890512271, {"dst_rule": "eu", "std_offset": 60, "period_start": "2027-02-01", "period_end": "2027-05-01", "pdf_td": True}),
    "h_memo": (4419987305512338737, {"tol": {"E": "3.0", "G": "6.0", "F": "9.0"}, "tol_old": {"E": "2.0", "G": "5.0", "F": "8.0"}, "errata": 7,
                                     "rejects": 6, "regrades": 10, "disregard": 3, "dev_tie": 3, "pdf_octal": True, "pdf_td": True}),
    "h_profile": (5140337712096621873, {"rating_sheet": "Ratings_2026B", "index_sheet": "RatingIndex_26B", "site_sheet": "Sites_2026B", "max_gap_min": 45,
                                        "min_cov": "0.85", "margin_h": 12, "drift_tol": "0.03", "network": "CBHS-E",
                                        "dead_month": True}),
    "h_dense": (7307715526630918821, {"revision_rate": 0.09, "void_rate": 0.02, "conflicts": 40, "outages": 12, "fault_runs": 12, "edits": 160,
                                      "midnight_gaps": 10, "visit_amends": 14, "n_backup": 6, "yaml_flow": True,
                                      "long_chain": True, "order_fix": True}),
    "h_ice": (6109342237558170091, {"ice_sites": 8, "extra_ice_amend": 6, "meas_per_site": 9, "std_offset": -300, "open_ice": True}),
    "h_workbook": (3355718820456120917, {"date1904": True, "num_text": 0.8, "xlsx_runs": True, "xlsx_no_r": True}),
    "m_visits": (None, {"extra_visits": 10, "lower_method": True}),
    "m_measure": (None, {"extra_meas": 3}),
}


# ---------------------------------------------------------------------------- corpora
_FLIPS = ("field_gh", "mean_stage")


def _seal(root: _GPath) -> None:
    for p in root.iterdir():
        p.chmod(0o644)
    root.chmod(0o755)
    root.parent.chmod(0o755)


def _build_one(name: str, base: str) -> None:
    """Child-process entry: write one corpus and its expected reports under base."""
    base = _GPath(base)
    root = base / "data"
    if name in HELD:
        seed, over = HELD[name]
        W = _Ggenerate(root, seed or SHIPPED_SEED, over)
    elif name == "renamed":
        W = _Ggenerate(root, SHIPPED_SEED, {"rename": True})
    else:
        W = _Ggenerate(root, SHIPPED_SEED, None)
    exp = {"": _G_derive(W)}
    if name == "shipped":
        for f in _FLIPS:
            exp[f] = _G_derive(W, frozenset([f]))
    (base / "expected.json").write_text(_Gjson.dumps(exp), encoding="utf-8")
    _seal(root)


def _workers() -> int:
    return max(2, min(4, _os.cpu_count() or 2))


def _build_all() -> None:
    """Build every corpus once, in parallel child processes."""
    with _LOCK:
        if "built" in _MEMO:
            return
        names = ["shipped", "renamed", *HELD]
        pending = list(names)
        running = []
        while pending or running:
            while pending and len(running) < _workers():
                name = pending.pop(0)
                base = _GPath(_tempfile.mkdtemp(prefix=f"sf-{name}-"))
                base.chmod(0o755)
                proc = _subprocess.Popen([_sys.executable, str(_GPath(__file__).resolve()), "--build", name, str(base)],
                                         stdout=_subprocess.DEVNULL, stderr=_subprocess.DEVNULL)
                running.append((name, base, proc))
            name, base, proc = running.pop(0)
            proc.wait()
            if proc.returncode == 0 and (base / "expected.json").is_file():
                _MEMO["corpus:" + name] = base / "data"
                _MEMO["exp:" + name] = _Gjson.loads((base / "expected.json").read_text(encoding="utf-8"))
        _MEMO["built"] = True


def _corpus(name: str):
    _build_all()
    return _MEMO["corpus:" + name]


def _expected(name: str, flip: str = "") -> dict:
    _build_all()
    return _MEMO["exp:" + name][flip]


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
                stage = _GPath(_tempfile.mkdtemp(prefix="sf-prog-"))
                stage.chmod(0o755)
                staged = stage / "run_flowrecord.py"
                _shutil.copyfile(PROGRAM, staged)
                staged.chmod(0o755)
                _MEMO["staged"] = staged
        return _MEMO["staged"]


def _start(name: str, tag: str):
    prog = _staged_program()
    if prog is None:
        return None
    src = _corpus(name)
    work = _GPath(_tempfile.mkdtemp(prefix=f"sf-run-{name}-"))
    work.chmod(0o777)
    data = work / ("input" + tag) / "gauges"
    data.parent.mkdir()
    data.parent.chmod(0o755)
    _shutil.copytree(src, data)
    _seal(data)
    out = work / "result"
    out.mkdir(parents=True)
    out.chmod(0o777)
    try:
        proc = _subprocess.Popen(_untrusted([_sys.executable, str(prog), str(data), str(out)]), stdout=_subprocess.DEVNULL,
                                 stderr=_subprocess.DEVNULL, start_new_session=True)
    except (OSError, _subprocess.SubprocessError):
        return None
    return proc, out


def _finish(started):
    if started is None:
        return None
    proc, out = started
    try:
        code = proc.wait(timeout=600)
    except _subprocess.TimeoutExpired:
        code = -1
    finally:
        try:
            _os.killpg(proc.pid, 9)
        except OSError:
            pass
        proc.wait()
    return out if code == 0 and out.is_dir() else None


def _run_many(jobs) -> None:
    """Run the delivered program on several corpora, a few at a time."""
    with _LOCK:
        todo = [j for j in jobs if f"run:{j[0]}:{j[1]}" not in _MEMO]
        while todo:
            batch, todo = todo[:_workers()], todo[_workers():]
            started = [(j, _start(*j)) for j in batch]
            for (name, tag), st in started:
                _MEMO[f"run:{name}:{tag}"] = _finish(st)


def _run(name: str, tag: str = ""):
    """Run the delivered program on a fresh copy of a corpus; the output directory or None."""
    with _LOCK:
        _run_many([(name, tag)])
        return _MEMO[f"run:{name}:{tag}"]


# ---------------------------------------------------------------------------- comparison
_DECRE = _re.compile(r"^-?(\d+\.?\d*|\.\d+)$")


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
    """Canonical form: numbers by exact value; lists of objects as multisets except ordered arrays."""
    if isinstance(o, dict):
        return {k: _json_norm(v, k) for k, v in o.items()}
    if isinstance(o, list):
        items = [_json_norm(v) for v in o]
        if items and all(isinstance(v, dict) for v in items) and key not in ("files", "points", "k_points"):
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
        elif line.startswith("|") and not _re.fullmatch(r"\|(\s*-+\s*\|)+", line):
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
            if ok:
                _run_many([(name, "") for name in HELD] + [("shipped", "a"), ("shipped", "b"), ("renamed", "")])
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
@criterion(description="The program run_flowrecord.py, all twenty-one contract reports and manifest.json exist under /app/out")
def deliverables_present(workspace: _GPath) -> bool:
    return _safe(lambda: PROGRAM.is_file() and all((OUT / n).is_file() for n in _contract_files()))


@criterion(description="The program runs on a fresh copy of the shipped data at another path and writes exactly the twenty-two contract files there")
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
@criterion(description="The field visit errors are exact for the shipped data, with every core report exact")
def visit_errors_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("visit_errors.psv"))


@criterion(description="The rating tables used, errata included, are exact for the shipped data, with every core report exact")
def rating_tables_used_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("rating_tables_used.json"))


@criterion(description="The station token resolution table is exact for the shipped data, with every core report exact")
def alias_resolution_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("alias_resolution.csv"))


@criterion(description="The ingest counters are exact for the shipped data, with every core report exact")
def dedup_report_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("dedup_report.json"))


@criterion(description="The per-file source lineage is exact for the shipped data, with every core report exact")
def source_lineage_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("source_lineage.json"))


@criterion(description="The reading exclusions are exact for the shipped data, with every core report exact")
def reading_exclusions_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("reading_exclusions.jsonl"))


@criterion(description="The unit-value edit ledger is exact for the shipped data, with every core report exact")
def amendment_ledger_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("amendment_ledger.psv"))


@criterion(description="The governing settings applied are exact for the shipped data, with every core report exact")
def parameters_used_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("parameters_used.yaml"))


@criterion(description="The comparison with the published daily values is exact for the shipped data, with every core report exact")
def variance_vs_published_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("variance_vs_published.csv"))


@criterion(description="The comparison with the published shift worksheet is exact for the shipped data, with every core report exact")
def shift_vs_published_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("shift_vs_published.csv"))


@criterion(description="The dashboard comparison is exact for the shipped data, with every core report exact")
def dashboard_disagreements_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("dashboard_disagreements.tsv"))


@criterion(description="The unit-value cache comparison is exact for the shipped data, with every core report exact")
def cache_divergence_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("cache_divergence.jsonl"))


@criterion(description="The reconciliation summary is exact for the shipped data, with every core report exact")
def reconciliation_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _leaf("reconciliation.md"))


# ============================================================================ held-out re-execution
@criterion(description="Rerun on a reseeded network with other stations, ratings, visits, measurements and ice, every report is exact")
def heldout_reseed_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_reseed"))


@criterion(description="Rerun on a network under another clock rule, standard offset and period, every report is exact")
def heldout_zone_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_zone"))


@criterion(description="Rerun on data whose minutes change the tolerances, errata, reviews and disregarded visits, every report is exact")
def heldout_memo_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_memo"))


@criterion(description="Rerun on data whose profile names another network, sheets, gap, coverage, margin and tolerance, with one station silent for a whole month, every report is exact")
def heldout_profile_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_profile"))


@criterion(description="Rerun on denser data with more revisions, voids, conflicts, outages, faults, edits, gaps, long token chains and doubly failing records, every report is exact")
def heldout_dense_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_dense"))


@criterion(description="Rerun on a network with more ice stations, ice amendments and measurements under another offset, every report is exact")
def heldout_ice_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_ice"))


@criterion(description="Rerun on data whose workbook uses the 1904 date system, text numbers, rich text and cells without references, every report is exact")
def heldout_workbook_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("h_workbook"))


@criterion(description="Rerun on the shipped network with added field visit amendments in mixed case, every report is exact")
def metamorphic_visits_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("m_visits"))


@criterion(description="Rerun on the shipped network with added discharge measurements, every report is exact")
def metamorphic_measurements_exact(workspace: _GPath) -> bool:
    return _safe(lambda: _held_out_exact("m_measure"))


# ============================================================================ negative checks (True when the cheat or wrong reading is present)
def _echoes_shipped() -> bool:
    want_h = _expected("h_reseed")["daily_values.csv"]
    want_s = _expected("shipped")["daily_values.csv"]
    if _same("daily_values.csv", want_h, want_s):
        return False
    got = _text(_run("h_reseed"), "daily_values.csv")
    return got is not None and _same("daily_values.csv", got, want_s)


@criterion(description="The program ignores its input and replays the shipped daily values on a held-out network")
def negative_hardcoded_sample_answers(workspace: _GPath) -> bool:
    # inverted: True when the reseeded run reproduces the shipped daily values
    return _safe(_echoes_shipped)


@criterion(description="The program is exact on a copy of the shipped data and wrong once only the shard file names change")
def negative_filename_dependent_behaviour(workspace: _GPath) -> bool:
    # inverted: True when renaming the shards alone breaks an otherwise exact run (a replay is priced by the check above)
    def chk() -> bool:
        if _echoes_shipped():
            return False
        if not _all_exact(_run("shipped", "a"), "shipped", NAMES):
            return False
        return not _all_exact(_run("renamed"), "renamed", NAMES)
    return _safe(chk)


@criterion(description="Two runs of the program on copies of the same data write different report bytes")
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
                  "lxml", "pdfminer", "scipy", "statsmodels", "polars", "duckdb", "ruamel", "dateutil", "pytz"}
        for p in sorted(OUT.glob("*.py")):
            for node in _ast.walk(_ast.parse(p.read_text(encoding="utf-8"))):
                names = ({a.name.split(".")[0] for a in node.names} if isinstance(node, _ast.Import) else
                         {(node.module or "").split(".")[0]} if isinstance(node, _ast.ImportFrom) else set())
                if names & banned:
                    return True
        return False
    except Exception:
        return False


@criterion(description="daily_values.csv repeats the published daily value for at least half of the compared station days")
def negative_echoes_published(workspace: _GPath) -> bool:
    # inverted: True when half or more of the compared daily values equal the published numbers
    try:
        pub = {}
        for r in _Gcsv.DictReader(_Gio.StringIO((_corpus("shipped") / "dv_pub_26q2.csv").read_text(encoding="utf-8"))):
            if r["q_mean_cfs"].strip():
                pub[(r["site"].strip(), r["date"].strip())] = _GD(r["q_mean_cfs"].strip())
        hit = tot = 0
        for r in _Gcsv.DictReader(_Gio.StringIO(_text(OUT, "daily_values.csv") or "")):
            k = (str(r.get("site", "")).strip(), str(r.get("date", "")).strip())
            v = _dec(str(r.get("q_mean_cfs") or ""))
            if k in pub and v is not None:
                tot += 1
                hit += v == pub[k]
        return tot >= 100 and hit * 2 >= tot
    except Exception:
        return False


@criterion(description="measurement_eval.csv equals the evaluation that takes each measurement gage height from the field sheet")
def negative_field_sheet_gage_height(workspace: _GPath) -> bool:
    # inverted: True when the shipped measurement evaluation matches the field-sheet reading exactly
    return _safe(lambda: _matches_flip("field_gh", "measurement_eval.csv"))


@criterion(description="daily_values.csv equals the daily values computed as the rating of the mean daily gage height")
def negative_daily_from_mean_stage(workspace: _GPath) -> bool:
    # inverted: True when the shipped daily values match the rating-of-mean-stage reading exactly
    return _safe(lambda: _matches_flip("mean_stage", "daily_values.csv"))


criteria.deliverables_present(weight=1)
criteria.program_writes_contract_files(weight=1)
criteria.delimited_headers_exact(weight=1)
criteria.json_report_keys(weight=1)
criteria.manifest_consistent(weight=1)
criteria.text_serialization(weight=1)
criteria.visit_errors_exact(weight=3)
criteria.rating_tables_used_exact(weight=3)
criteria.alias_resolution_exact(weight=3)
criteria.dedup_report_exact(weight=3)
criteria.source_lineage_exact(weight=3)
criteria.reading_exclusions_exact(weight=3)
criteria.amendment_ledger_exact(weight=3)
criteria.parameters_used_exact(weight=1)
criteria.variance_vs_published_exact(weight=1)
criteria.shift_vs_published_exact(weight=1)
criteria.dashboard_disagreements_exact(weight=1)
criteria.cache_divergence_exact(weight=1)
criteria.reconciliation_exact(weight=1)
criteria.heldout_reseed_exact(weight=5)
criteria.heldout_zone_exact(weight=5)
criteria.heldout_memo_exact(weight=5)
criteria.heldout_profile_exact(weight=5)
criteria.heldout_dense_exact(weight=5)
criteria.heldout_ice_exact(weight=5)
criteria.heldout_workbook_exact(weight=5)
criteria.metamorphic_visits_exact(weight=5)
criteria.metamorphic_measurements_exact(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_third_party_import(weight=-3)
criteria.negative_echoes_published(weight=-3)
criteria.negative_field_sheet_gage_height(weight=-3)
criteria.negative_daily_from_mean_stage(weight=-3)


if __name__ == "__main__" and len(_sys.argv) == 4 and _sys.argv[1] == "--build":
    _build_one(_sys.argv[2], _sys.argv[3])
