#!/usr/bin/env python3
"""Derive the coexistence occupancy measure from a register corpus.

Usage: python3 derive_report.py <corpus_dir> <output_dir>
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
ZONES = ["North", "South", "West", "East"]
GROUPS = ["identity", "time", "frequency"]
LAYERS = ["core", "office", "coord"]


# ------------------------------------------------------------------ stamps

def ts(text):
    text = (text or "").strip()
    if not text:
        return None
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?"
                 r"(Z|[+-]\d{2}:\d{2})?$", text)
    if m:
        y, mo, d, hh, mm = (int(m.group(i)) for i in range(1, 6))
        ss = int(m.group(6) or 0)
        base = int((datetime(y, mo, d, hh, mm, ss, tzinfo=timezone.utc) - EPOCH).total_seconds())
        tzs = m.group(7)
        if tzs and tzs != "Z":
            sign = 1 if tzs[0] == "+" else -1
            base -= sign * (int(tzs[1:3]) * 3600 + int(tzs[4:6]) * 60)
        return base
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", text)
    if m:
        y, mo, d = (int(m.group(i)) for i in range(1, 4))
        return int((datetime(y, mo, d, tzinfo=timezone.utc) - EPOCH).total_seconds())
    raise ValueError("unparsable stamp %r" % text)


def iso(n):
    return (EPOCH + timedelta(seconds=int(n))).strftime("%Y-%m-%dT%H:%M:%SZ")


def civil(n):
    d = EPOCH + timedelta(seconds=int(n))
    return d.year, d.month, d.day


def mstart(y, m):
    return int((datetime(y, m, 1, tzinfo=timezone.utc) - EPOCH).total_seconds())


def nextm(y, m):
    return (y + 1, 1) if m == 12 else (y, m + 1)


def isoweek(n):
    return (EPOCH + timedelta(seconds=int(n))).isoweekday()


# ------------------------------------------------------------------ parsing

def read_text(root, name):
    with open(os.path.join(root, name), "r", encoding="utf-8") as fh:
        return fh.read()


def md_tables(text):
    out = []
    cur = None
    for raw in text.splitlines():
        s = raw.strip()
        if s.startswith("|") and s.endswith("|") and len(s) > 1:
            cells = [c.strip() for c in s[1:-1].split("|")]
            if cells and all(c and set(c) <= set("-: ") for c in cells):
                continue
            if cur is None:
                cur = {"head": cells, "rows": []}
            else:
                cur["rows"].append(cells)
        elif cur is not None:
            out.append(cur)
            cur = None
    if cur is not None:
        out.append(cur)
    return out


def table_by_head(text, first_col):
    for t in md_tables(text):
        if t["head"] and t["head"][0] == first_col:
            return t
    raise ValueError("table starting with %r not found" % first_col)


def read_ini(root, name):
    out = {}
    sec = None
    for raw in read_text(root, name).splitlines():
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("[") and s.endswith("]"):
            sec = s[1:-1]
            out[sec] = {}
        elif "=" in s and sec is not None:
            k, v = s.split("=", 1)
            out[sec][k.strip()] = v.strip()
    return out


def read_csv(root, name, sep=","):
    rows = []
    with open(os.path.join(root, name), "r", encoding="utf-8") as fh:
        head = fh.readline().rstrip("\n").split(sep)
        for raw in fh:
            raw = raw.rstrip("\n")
            if not raw:
                continue
            parts = raw.split(sep)
            if len(parts) < len(head):
                parts += [""] * (len(head) - len(parts))
            rows.append(dict(zip(head, parts)))
    return rows


def read_jsonl(root, name):
    rows = []
    with open(os.path.join(root, name), "r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if raw:
                rows.append(json.loads(raw))
    return rows


def count_rows(root, name):
    with open(os.path.join(root, name), "r", encoding="utf-8") as fh:
        n = sum(1 for _ in fh)
    return n if name.endswith(".jsonl") else n - 1


# ------------------------------------------------------------------ specs

class Specs(object):
    def __init__(self, root):
        self.root = root
        cfg = read_ini(root, "measure_config.ini")
        self.h0_text = cfg["horizon"]["start"]
        self.h1_text = cfg["horizon"]["end"]
        self.as_of_text = cfg["horizon"]["as_of"]
        self.h0 = ts(self.h0_text)
        self.h1 = ts(self.h1_text)
        self.as_of = ts(self.as_of_text)
        self.share_bp = int(cfg["measure"]["share_total_bp"])
        self.ppm = int(cfg["measure"]["ppm_scale"])
        self.rounding = cfg["measure"]["rounding"]
        self.shared_min = int(cfg["measure"]["shared_multiplicity_min"])
        self.top_holders = int(cfg["limits"]["top_holders"])
        self.top_excess = int(cfg["limits"]["top_excess"])
        self.top_deficit = int(cfg["limits"]["top_deficit"])
        self.units = read_ini(root, "unit_declarations.ini")

        bp = table_by_head(read_text(root, "band_plan.md"), "band")
        self.bands = [(r[0], int(r[1]), int(r[2]), int(r[3])) for r in bp["rows"]]

        zt = table_by_head(read_text(root, "zone_time_rules.md"), "zone")
        self.zone_clock = {}
        for r in zt["rows"]:
            a = "" if r[3] == "none" else r[3]
            b = "" if r[4] == "none" else r[4]
            self.zone_clock[r[0]] = (int(r[1]), int(r[2]), a, b)

        pp = read_text(root, "precedence_policy.md")
        self.rank = [r[1] for r in sorted(table_by_head(pp, "rank")["rows"],
                                          key=lambda r: int(r[0]))]
        self.reg_steps = [r[1] for r in sorted(table_by_head(pp, "step")["rows"],
                                               key=lambda r: int(r[0]))]

        nr = read_text(root, "normalisation_rules.md")
        self.norm_steps = [r[1] for r in sorted(table_by_head(nr, "step")["rows"],
                                                key=lambda r: int(r[0]))]
        self.norm_prefix = re.search(r"leading ([A-Z]{2,4}) prefix", nr).group(1)
        if "last six" not in nr:
            raise ValueError("canonical length not stated")
        self.norm_len = 6
        self.term_enc = dict((r[0], r[1]) for r in
                             table_by_head(nr, "encoding of effective_to")["rows"])

        sm = table_by_head(read_text(root, "state_machine.md"), "state")
        self.trans = dict(((r[0], r[1]), (r[2], r[3] == "yes")) for r in sm["rows"])

        rc = read_text(root, "reason_codes.md")
        self.reject_order = [r[1] for r in sorted(table_by_head(rc, "order")["rows"],
                                                  key=lambda r: int(r[0]))]
        self.note_codes = sorted(r[0] for r in table_by_head(rc, "note")["rows"])

        gp = read_text(root, "guard_policy.md")
        self.recur_tokens = [r[0] for r in table_by_head(gp, "recurrence token")["rows"]]

        dp = read_text(root, "duty_policy.md")
        self.duty_quant = [r[0] for r in table_by_head(dp, "quantity")["rows"]]
        self.duty_minute_token = re.search(r"`unit=([a-z_]+)`", dp).group(1)

        oc = read_text(root, "output_contract.md")
        self.artifacts = re.findall(r"^## ([A-Za-z_<>.]+\.(?:json|py))", oc, re.M)

        self.index = [(r[0], r[1]) for r in
                      table_by_head(read_text(root, "corpus_index.md"), "file")["rows"]]
        self.declared = dict((r[0], int(r[1])) for r in
                             table_by_head(read_text(root, "source_manifest.md"),
                                           "file")["rows"])

        self.channels = [(c["band"], int(c["f_low_khz"]), int(c["f_high_khz"]), c["status"])
                         for c in read_csv(root, "channel_raster.csv")]
        self.edge_lo = set(c[1] for c in self.channels)
        self.edge_hi = set(c[2] for c in self.channels)
        runs = []
        for b, lo, hi, st in sorted(self.channels, key=lambda c: c[1]):
            if st != "usable":
                continue
            if runs and runs[-1][1] == lo and runs[-1][2] == b:
                runs[-1] = (runs[-1][0], hi, b)
            else:
                runs.append([lo, hi, b])
        self.runs = [tuple(r) for r in runs]
        if len(self.duty_quant) != 4 or len(self.norm_steps) != 5:
            raise ValueError("spec tables incomplete")
        if len(self.artifacts) < 4 or not self.recur_tokens or not self.reg_steps:
            raise ValueError("spec tables incomplete")

    def set_keying(self, keying):
        self.keying = keying
        self.tr = {}
        for z in ZONES:
            std, smr, a, b = self.zone_clock[z]
            if not a:
                self.tr[z] = (std, smr, None, None)
                continue
            ta, tb = ts(a), ts(b)
            if keying == "local_standard":
                ta -= std
                tb -= std
            self.tr[z] = (std, smr, ta, tb)

    def off_at(self, z, utc):
        std, smr, a, b = self.tr[z]
        if a is None:
            return std
        if a <= b:
            return smr if a <= utc < b else std
        return smr if (utc >= a or utc < b) else std

    def to_utc(self, z, local):
        std, smr, a, b = self.tr[z]
        if a is None:
            return local - std
        c = local - std
        if self.off_at(z, c) == std:
            return c
        c = local - smr
        if self.off_at(z, c) == smr:
            return c
        return local - std

    def month_cells(self, z):
        out = []
        y, m, _ = civil(self.h0 + self.off_at(z, self.h0))
        while True:
            a = self.to_utc(z, mstart(y, m))
            ny, nm = nextm(y, m)
            b = self.to_utc(z, mstart(ny, nm))
            if a >= self.h1:
                break
            if b > self.h0:
                out.append(("%04d-%02d" % (y, m), max(a, self.h0), min(b, self.h1)))
            y, m = ny, nm
        return out


# ------------------------------------------------------------------ holders

def canonical(sp, ref):
    s = ref or ""
    for rule in sp.norm_steps:
        low = rule.lower()
        if "upper case" in low:
            s = s.upper()
        elif "not a letter or a digit" in low:
            s = "".join(c for c in s if c.isalnum())
        elif "prefix" in low:
            if s.startswith(sp.norm_prefix):
                s = s[len(sp.norm_prefix):]
        elif "last six" in low:
            if len(s) > sp.norm_len:
                s = s[-sp.norm_len:]
        elif "pad on the left" in low:
            if len(s) < sp.norm_len:
                s = "0" * (sp.norm_len - len(s)) + s
    return s


def alias_fixpoint(alias):
    resolved = {}
    depth = {}
    cycles = []
    for start in sorted(alias):
        if start in resolved:
            continue
        path = []
        pos = {}
        cur = start
        while cur in alias and alias[cur] != cur and cur not in pos:
            pos[cur] = len(path)
            path.append(cur)
            cur = alias[cur]
        if cur in pos:
            ring = sorted(path[pos[cur]:])
            if len(ring) > 1 and ring not in cycles:
                cycles.append(ring)
            target = ring[0]
        else:
            target = cur
        walk = list(path)
        if cur not in pos:
            walk.append(cur)
        for node in walk:
            n = node
            steps = 0
            while n != target and steps <= len(path) + 1:
                n = alias.get(n, n)
                steps += 1
            resolved[node] = target
            depth[node] = steps
        if start not in resolved:
            resolved[start] = start
            depth[start] = 0
    return resolved, depth, cycles


def resolve_ref(sp, alias_res, alias_depth, ref):
    base = canonical(sp, ref)
    hops = 0
    if base in alias_res:
        hops = alias_depth.get(base, 1)
        base = alias_res[base]
    return base, hops


# ------------------------------------------------------------------ geometry

def free_spans(lo, hi, blocks):
    spans = []
    cur = lo
    for a, b in sorted(blocks):
        if b <= cur:
            continue
        if a > cur:
            spans.append((cur, min(a, hi)))
        cur = max(cur, b)
        if cur >= hi:
            break
    if cur < hi:
        spans.append((cur, hi))
    return [(a, b) for a, b in spans if b > a]


def subtract_rect(rect, occs):
    flo, fhi, tlo, thi, aid = rect
    rel = [o for o in occs if o[0] < fhi and o[1] > flo and o[2] < thi and o[3] > tlo]
    if not rel:
        return [rect]
    cuts = set([flo, fhi])
    for o in rel:
        if flo < o[0] < fhi:
            cuts.add(o[0])
        if flo < o[1] < fhi:
            cuts.add(o[1])
    xs = sorted(cuts)
    out = []
    for i in range(len(xs) - 1):
        a, b = xs[i], xs[i + 1]
        blocks = [(max(tlo, o[2]), min(thi, o[3])) for o in rel if o[0] <= a and o[1] >= b]
        for s, e in free_spans(tlo, thi, blocks):
            out.append((a, b, s, e, aid))
    return out


def intersect_sets(a, b):
    out = []
    for r in a:
        for q in b:
            flo = max(r[0], q[0])
            fhi = min(r[1], q[1])
            if fhi <= flo:
                continue
            tlo = max(r[2], q[2])
            thi = min(r[3], q[3])
            if thi <= tlo:
                continue
            out.append((flo, fhi, tlo, thi, r[4]))
    return out


def reduce_rects(rects):
    cur = list(rects)
    while True:
        merged = False
        groups = {}
        for r in cur:
            groups.setdefault((r[4], r[2], r[3]), []).append(r)
        nxt = []
        for key in sorted(groups):
            run = sorted(groups[key], key=lambda r: r[0])
            acc = list(run[0])
            for r in run[1:]:
                if r[0] == acc[1]:
                    acc[1] = r[1]
                    merged = True
                else:
                    nxt.append(tuple(acc))
                    acc = list(r)
            nxt.append(tuple(acc))
        cur = nxt
        groups = {}
        for r in cur:
            groups.setdefault((r[4], r[0], r[1]), []).append(r)
        nxt = []
        for key in sorted(groups):
            run = sorted(groups[key], key=lambda r: r[2])
            acc = list(run[0])
            for r in run[1:]:
                if r[2] == acc[3]:
                    acc[3] = r[3]
                    merged = True
                else:
                    nxt.append(tuple(acc))
                    acc = list(r)
            nxt.append(tuple(acc))
        cur = nxt
        if not merged:
            return sorted(cur)


def sweep(rects, own=None, tcuts=None, bands=None, shared_min=2):
    """Union, exclusive, shared, per cut bucket, per band, and charges."""
    res = {"union": 0, "excl": 0, "shared": 0, "charge": {}, "months": {}, "bands": {}}
    if not rects:
        return res
    xs = sorted(set([r[0] for r in rects] + [r[1] for r in rects]))
    pos = dict((x, i) for i, x in enumerate(xs))
    buckets = [[] for _ in range(len(xs) - 1)]
    for r in rects:
        for i in range(pos[r[0]], pos[r[1]]):
            buckets[i].append(r)
    cutlist = sorted(tcuts.keys()) if tcuts else []
    for i, bucket in enumerate(buckets):
        if not bucket:
            continue
        width = xs[i + 1] - xs[i]
        bname = None
        if bands is not None:
            for nm, lo, hi, _w in bands:
                if lo <= xs[i] < hi:
                    bname = nm
                    break
        evs = []
        for r in bucket:
            evs.append((r[2], 1, r[4]))
            evs.append((r[3], -1, r[4]))
        for c in cutlist:
            evs.append((c, 0, None))
        evs.sort(key=lambda e: (e[0], e[1]))
        active = {}
        prev = None
        for t, d, aid in evs:
            if prev is not None and t > prev and active:
                span = (t - prev) * width
                k = len(active)
                res["union"] += span
                if k >= shared_min:
                    res["shared"] += span
                    if own is not None:
                        order = sorted(active, key=lambda a: (-own.get(a, 0), a))
                        for a in order[1:]:
                            res["charge"][a] = res["charge"].get(a, 0) + span
                else:
                    res["excl"] += span
                if bname is not None:
                    res["bands"][bname] = res["bands"].get(bname, 0) + span
                if tcuts:
                    key = tcuts.get(prev)
                    if key is None:
                        key = _bucket_of(cutlist, tcuts, prev)
                    if key is not None:
                        res["months"][key] = res["months"].get(key, 0) + span
            prev = t
            if d == 1:
                active[aid] = active.get(aid, 0) + 1
            elif d == -1:
                active[aid] -= 1
                if active[aid] == 0:
                    del active[aid]
    return res


def _bucket_of(cutlist, tcuts, t):
    lo, hi = 0, len(cutlist) - 1
    best = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if cutlist[mid] <= t:
            best = cutlist[mid]
            lo = mid + 1
        else:
            hi = mid - 1
    return tcuts.get(best) if best is not None else None


def union_only(rects):
    return sweep(rects)["union"]


# ------------------------------------------------------------------ rounding

def half_even(num, den):
    q, r = divmod(num, den)
    twice = 2 * r
    if twice > den or (twice == den and q % 2 == 1):
        q += 1
    return q


def largest_remainder(values, total):
    keys = sorted(values)
    base = sum(values[k] for k in keys)
    if base <= 0:
        return dict((k, 0) for k in keys)
    out = {}
    rem = []
    used = 0
    for k in keys:
        q, r = divmod(values[k] * total, base)
        out[k] = q
        used += q
        rem.append((-r, k))
    rem.sort()
    left = total - used
    for i in range(left):
        out[rem[i % len(rem)][1]] += 1
    return out


# ------------------------------------------------------------------ sources

def load_sources(sp):
    root = sp.root
    files = dict(sp.index)
    counts = {}
    for name in files:
        counts[name] = {"rows_read": count_rows(root, name), "rows_visible": 0,
                        "rows_governing": 0}
    marks = []
    for r in read_csv(root, "zone_clock_marks.csv"):
        if r["jurisdiction"] == sp.units["zone_clock_marks"]["authoritative_jurisdiction"]:
            marks.append((r["zone"], ts(r["local_stamp"]), ts(r["utc_stamp"])))
    best = None
    for keying in ("local_standard", "utc"):
        sp.set_keying(keying)
        bad = 0
        for z, loc, utc in marks:
            if sp.off_at(z, utc) != loc - utc:
                bad += 1
        if best is None or bad < best[1]:
            best = (keying, bad)
    sp.set_keying(best[0])
    sp.keying_misses = best[1]

    recs = []
    for name, layer in sp.index:
        if layer == "core":
            for r in read_csv(root, name):
                flo = int(r["f_low_khz"])
                width = int(r["bandwidth_khz"])
                exp = r["f_high_khz"].strip()
                fhi = int(exp) if exp else flo + width
                et = r["effective_to"].strip()
                recs.append({
                    "aid": r["assignment_id"], "layer": "core", "rev": int(r["revision"]),
                    "rec": ts(r["recorded_at"]), "action": r["action"], "file": name,
                    "identity": {"holder_ref": r["holder_ref"], "zone": r["zone"],
                                 "parent_id": r["parent_id"].strip()},
                    "time": {"ef": ts(r["effective_from"]), "et": ts(et) if et else None,
                             "open": not et, "nulled": False},
                    "freq": {"flo": flo, "fhi": fhi, "bad": False,
                             "mismatch": bool(exp) and fhi != flo + width},
                })
        elif layer == "office":
            z = None
            for cand in ZONES:
                if "_%s_" % cand.lower() in name:
                    z = cand
            for r in read_csv(root, name, "\t"):
                rec = sp.to_utc(z, ts(r["recorded_at_local"]))
                et = r["effective_to_local"].strip()
                fq = None
                lo_hz = r["f_low_hz"].strip()
                if lo_hz:
                    bw_hz = int(r["bandwidth_hz"])
                    lo = int(lo_hz)
                    bad = (lo % 1000 != 0) or (bw_hz % 1000 != 0)
                    fq = {"flo": lo // 1000, "fhi": (lo + bw_hz) // 1000, "bad": bad,
                          "mismatch": False}
                recs.append({
                    "aid": r["assignment_id"], "layer": "office", "rev": int(r["revision"]),
                    "rec": rec, "action": r["action"], "file": name, "identity": None,
                    "time": {"ef": sp.to_utc(z, ts(r["effective_from_local"])),
                             "et": sp.to_utc(z, ts(et)) if et else None,
                             "open": not et, "nulled": False},
                    "freq": fq,
                })
        elif layer == "coord":
            acc = [t.strip() for t in
                   sp.units["coordination_decisions"]["accepted_unit_tokens"].split(",")]
            for r in read_jsonl(root, name):
                fq = None
                if "f_low_khz" in r:
                    flo = int(r["f_low_khz"])
                    unit = r.get("bandwidth_unit")
                    raw = r.get("bandwidth")
                    bad = False
                    width = 0
                    if unit not in acc or raw is None:
                        bad = True
                    elif unit == "kHz":
                        width = int(raw)
                    elif int(raw) % 1000 != 0:
                        bad = True
                    else:
                        width = int(raw) // 1000
                    exp = r.get("f_high_khz")
                    fhi = int(exp) if exp is not None else flo + width
                    fq = {"flo": flo, "fhi": fhi, "bad": bad,
                          "mismatch": exp is not None and fhi != flo + width}
                tm = None
                if "effective_from" in r:
                    raw = r.get("effective_to", "")
                    tm = {"ef": ts(r["effective_from"]),
                          "et": None if raw in (None, "") else ts(raw),
                          "open": raw == "", "nulled": raw is None}
                idn = None
                if "holder_ref" in r:
                    idn = {"holder_ref": r["holder_ref"], "zone": r.get("zone", ""),
                           "parent_id": (r.get("parent_id") or "").strip()}
                recs.append({
                    "aid": r["assignment_id"], "layer": "coord", "rev": int(r["revision"]),
                    "rec": ts(r["recorded_at"]), "action": r["action"], "file": name,
                    "identity": idn, "time": tm, "freq": fq,
                })
    for i, r in enumerate(recs):
        r["idx"] = i
        if r["rec"] < sp.as_of:
            counts[r["file"]]["rows_visible"] += 1
    return recs, counts


def derive_tiebreak(sp):
    rows = read_csv(sp.root, "register_governing_flags.csv")
    groups = {}
    for r in rows:
        groups.setdefault((r["assignment_id"], r["layer"]), []).append(
            (int(r["revision"]), ts(r["recorded_at"]), r["governing"].strip().lower()))
    votes = {"earliest": 0, "latest": 0}
    for key in sorted(groups):
        pool = groups[key]
        top = max(p[0] for p in pool)
        tied = [p for p in pool if p[0] == top]
        if len(tied) < 2:
            continue
        gov = [p for p in tied if p[2] == "true"]
        if len(gov) != 1:
            continue
        stamps = sorted(p[1] for p in tied)
        if gov[0][1] == stamps[0]:
            votes["earliest"] += 1
        if gov[0][1] == stamps[-1]:
            votes["latest"] += 1
    return "earliest" if votes["earliest"] >= votes["latest"] else "latest"


def governing(sp, recs, tiebreak):
    best = {}
    for r in recs:
        if r["rec"] >= sp.as_of:
            continue
        key = (r["aid"], r["layer"])
        cur = best.get(key)
        if cur is None or r["rev"] > cur["rev"]:
            best[key] = r
        elif r["rev"] == cur["rev"]:
            if tiebreak == "earliest":
                if (r["rec"], r["idx"]) < (cur["rec"], cur["idx"]):
                    best[key] = r
            else:
                if (r["rec"], -r["idx"]) > (cur["rec"], -cur["idx"]):
                    best[key] = r
    return best


def supply_map(best):
    out = {}
    for (aid, layer), r in best.items():
        slot = out.setdefault(aid, {})
        slot[layer] = {"identity": r["identity"] is not None,
                       "time": r["time"] is not None,
                       "frequency": r["freq"] is not None}
    return out


def pick_layer(order, supply, aid, group):
    for layer in order:
        s = supply.get(aid, {}).get(layer)
        if s and s[group]:
            return layer
    return None


def derive_exception(sp, best, supply, segment):
    tally = {}
    for r in read_csv(sp.root, "precedence_observations.csv"):
        aid = r["assignment_id"]
        grp = r["field_group"]
        got = r["layer_followed"]
        if aid not in supply or grp not in GROUPS or grp == "identity":
            continue
        want = pick_layer(sp.rank, supply, aid, grp)
        if want is None or got == want:
            continue
        seg = segment.get(aid)
        if seg is None:
            continue
        tally.setdefault((seg, grp), {})
        tally[(seg, grp)][got] = tally[(seg, grp)].get(got, 0) + 1
    if not tally:
        return None
    cell = sorted(tally, key=lambda k: (-sum(tally[k].values()), k))[0]
    layer = sorted(tally[cell], key=lambda k: (-tally[cell][k], k))[0]
    return {"segment": cell[0], "field_group": cell[1], "layer": layer}


# ------------------------------------------------------------------ registry

def load_registry(sp):
    reg = {}
    for z in ZONES:
        for r in read_csv(sp.root, "holder_registry_%s.csv" % z.lower()):
            reg.setdefault(r["canonical_id"], []).append(
                (ts(r["as_of"]), r["holder_class"], r["zone_of_record"]))
    hist = {}
    for r in read_csv(sp.root, "holder_status_history.csv"):
        hist.setdefault(r["canonical_id"], []).append((ts(r["status_from"]), r["status"]))
    for k in hist:
        hist[k].sort()
    return reg, hist


def pick_reg(rows, grant_zone):
    best = None
    for as_of, cls, zor in rows:
        key = (-as_of, 0 if zor == grant_zone else 1, zor)
        if best is None or key < best[0]:
            best = (key, cls, zor)
    return best[1], best[2]


def status_at(hist, hid, when):
    out = None
    for sfrom, st in hist.get(hid) or []:
        if sfrom > when:
            break
        out = st
    return out or "provisional"


def load_notices(sp):
    live = {}
    groups = {}
    for i, r in enumerate(read_csv(sp.root, "retraction_notices.csv")):
        if ts(r["recorded_at"]) >= sp.as_of:
            continue
        groups.setdefault((r["assignment_id"], r["notice_date"]), []).append(
            (ts(r["recorded_at"]), i, r["scope"]))
    for key in groups:
        rows = sorted(groups[key])
        if rows[-1][2] == "full":
            live[key[0]] = True
    return live


# ------------------------------------------------------------------ state

PRIO = {"terminate": 0, "suspend": 1, "restore": 2, "activate": 3}


def load_events(sp):
    ev = {}
    susp = {}
    for z in ZONES:
        for r in read_csv(sp.root, "state_events_%s.csv" % z.lower()):
            if ts(r["recorded_at"]) >= sp.as_of:
                continue
            aid = r["assignment_id"]
            stamp = ts(r["event_ts"])
            ev.setdefault(aid, []).append((stamp, PRIO.get(r["event"], 9), r["event"]))
            if r["event"] == "suspend":
                susp.setdefault(aid, []).append(stamp)
    for k in ev:
        ev[k].sort()
    return ev, susp


def active_spans(sp, events, ef, et):
    spans = []
    anomaly = 0
    state = "active"
    cur = ef
    for stamp, _p, kind in events:
        t = stamp
        if t < ef:
            t = ef
        if t >= et:
            continue
        if state == "terminated":
            continue
        if kind == "restore" and state == "active":
            anomaly += 1
            continue
        nxt = sp.trans.get((state, kind))
        if nxt is None:
            continue
        new = nxt[0]
        if new == state:
            continue
        if state == "active":
            if t > cur:
                spans.append((cur, t))
        if new == "active":
            cur = t
        state = new
    if state == "active" and et > cur:
        spans.append((cur, et))
    return [(a, b) for a, b in spans if b > a], anomaly


# ------------------------------------------------------------------ guards

def build_occurrences(sp, zone, exc_rows):
    cancels = set()
    adds = []
    for r in exc_rows:
        if r["zone"] != zone:
            continue
        if r["kind"] == "cancel":
            cancels.add((r["rule_id"], r["occurrence_date"]))
        elif r["kind"] == "add":
            adds.append(r)
    rules = {}
    occ = []
    cancelled = 0
    added = 0
    for r in read_csv(sp.root, "guard_windows_%s.csv" % zone.lower()):
        rules[r["rule_id"]] = r
        if r["status"] != "active":
            continue
        vf = ts(r["valid_from"])
        vt = ts(r["valid_to"])
        dur = int(r["duration_min"]) * 60
        hh, mm = r["local_start"].split(":")
        start = int(hh) * 3600 + int(mm) * 60
        if sp.to_utc(zone, vt + 86400 + start) + dur <= sp.h0:
            continue
        if sp.to_utc(zone, vf - 86400 + start) >= sp.h1:
            continue
        flo, fhi = int(r["f_lo_khz"]), int(r["f_hi_khz"])
        token = r["recurrence"]
        d = vf
        while d < vt:
            keep = True
            if token == "daily":
                pass
            elif token.startswith("weekly:"):
                keep = isoweek(d) == int(token.split(":")[1])
            elif token.startswith("monthly:"):
                keep = civil(d)[2] == int(token.split(":")[1])
            else:
                keep = False
            if keep:
                date = iso(d)[:10]
                if (r["rule_id"], date) in cancels:
                    cancelled += 1
                else:
                    u = sp.to_utc(zone, d + start)
                    a, b = max(u, sp.h0), min(u + dur, sp.h1)
                    if b > a:
                        occ.append((flo, fhi, a, b))
            d += 86400
    for r in adds:
        rule = rules.get(r["rule_id"])
        if rule is None or rule["status"] != "active":
            continue
        hh, mm = r["local_start"].split(":")
        start = int(hh) * 3600 + int(mm) * 60
        dur = int(r["duration_min"]) * 60
        u = sp.to_utc(zone, ts(r["occurrence_date"]) + start)
        a, b = max(u, sp.h0), min(u + dur, sp.h1)
        if b > a:
            occ.append((int(rule["f_lo_khz"]), int(rule["f_hi_khz"]), a, b))
            added += 1
    index = {}
    for o in occ:
        index.setdefault((o[0], o[1]), []).append((o[2], o[3]))
    for k in index:
        index[k].sort()
    return occ, index, cancelled, added


def relevant(index, flo, fhi, tlo, thi):
    out = []
    for (a, b), spans in index.items():
        if a >= fhi or b <= flo:
            continue
        for s, e in spans:
            if s >= thi:
                break
            if e > tlo:
                out.append((a, b, s, e))
    return out


# ------------------------------------------------------------------ pipeline

def derive(corpus, outdir):
    sp = Specs(corpus)
    recs, counts = load_sources(sp)
    tiebreak = derive_tiebreak(sp)
    best = governing(sp, recs, tiebreak)
    for r in best.values():
        counts[r["file"]]["rows_governing"] += 1
    supply = supply_map(best)
    reg, hist = load_registry(sp)
    alias_raw = {}
    for r in read_csv(sp.root, "holder_alias_map.csv"):
        alias_raw[r["alias_id"]] = r["canonical_id"]
    alias_res, alias_depth, cycles = alias_fixpoint(alias_raw)
    notices = load_notices(sp)
    events, suspends = load_events(sp)

    aids = sorted(supply)
    ident = {}
    holder = {}
    segment = {}
    zone_of = {}
    hops_seen = 0
    for aid in aids:
        lay = pick_layer(sp.rank, supply, aid, "identity")
        row = best[(aid, lay)]["identity"] if lay else None
        ident[aid] = row
        if row is None:
            continue
        hid, hops = resolve_ref(sp, alias_res, alias_depth, row["holder_ref"])
        hops_seen = max(hops_seen, hops)
        holder[aid] = (hid, hops)
        zone_of[aid] = row["zone"]
        if hid in reg:
            cls, _zor = pick_reg(reg[hid], row["zone"])
            segment[aid] = cls

    exception = derive_exception(sp, best, supply, segment)
    order_cache = {}

    def order_for(seg, grp):
        key = (seg, grp)
        if key not in order_cache:
            base = list(sp.rank)
            if exception and seg == exception["segment"] and grp == exception["field_group"]:
                base = [exception["layer"]] + [x for x in base if x != exception["layer"]]
            order_cache[key] = base
        return order_cache[key]

    retracted = set()
    for aid in aids:
        lay = pick_layer(sp.rank, supply, aid, "identity")
        if lay and best[(aid, lay)]["action"] == "retract":
            retracted.add(aid)
        elif notices.get(aid):
            retracted.add(aid)

    layer_wins = {"core": 0, "office": 0, "coord": 0}
    rejects = dict((c, 0) for c in sp.reject_order)
    notes = dict((c, 0) for c in sp.note_codes)
    zero_span = 0
    anomalies = 0
    draft = {}
    parent_of = {}
    for aid in aids:
        if aid in retracted:
            continue
        seg = segment.get(aid)
        chosen = {}
        for grp in GROUPS:
            lay = pick_layer(order_for(seg, grp), supply, aid, grp)
            chosen[grp] = lay
            if lay:
                layer_wins[lay] += 1
        idn = best[(aid, chosen["identity"])]["identity"] if chosen["identity"] else None
        tm = best[(aid, chosen["time"])]["time"] if chosen["time"] else None
        fq = best[(aid, chosen["frequency"])]["freq"] if chosen["frequency"] else None
        rec = {"aid": aid, "idn": idn, "tm": tm, "fq": fq, "seg": seg, "fault": None,
               "notes": set()}
        draft[aid] = rec
        if idn is not None:
            parent_of[aid] = idn["parent_id"]
        if tm is None or tm["nulled"] or tm["ef"] is None:
            rec["fault"] = "TERM_MISSING"
            continue
        ef = tm["ef"]
        et = sp.h1 if tm["open"] else tm["et"]
        if et is None:
            rec["fault"] = "TERM_MISSING"
            continue
        if et < ef:
            rec["fault"] = "SPAN_INVERTED"
            continue
        rec["ef"], rec["et"] = ef, et
        if fq is None or fq["bad"]:
            rec["fault"] = "UNIT_AMBIGUOUS"
            continue
        flo, fhi = fq["flo"], fq["fhi"]
        if fhi <= flo:
            rec["fault"] = "BAND_OUTSIDE"
            continue
        runs = []
        for a, b, _bn in sp.runs:
            lo, hi = max(a, flo), min(b, fhi)
            if hi > lo:
                runs.append((lo, hi))
        if not runs:
            rec["fault"] = "BAND_OUTSIDE"
            continue
        if flo not in sp.edge_lo or fhi not in sp.edge_hi:
            rec["fault"] = "RASTER_MISALIGNED"
            continue
        rec["runs"] = runs
        hid = holder.get(aid)
        if hid is None or hid[0] not in reg:
            rec["fault"] = "HOLDER_UNKNOWN"
            continue
        cls, zor = pick_reg(reg[hid[0]], idn["zone"])
        rec["holder"] = hid[0]
        rec["seg"] = cls
        st = status_at(hist, hid[0], ef)
        if zor != idn["zone"] and st == "provisional":
            rec["fault"] = "ZONE_MISMATCH"
            continue
        if zor != idn["zone"]:
            rec["notes"].add("ZONE_OF_RECORD_DIFFERS")
        if hid[1] > 0:
            rec["notes"].add("ALIAS_RESOLVED")
        if fq["mismatch"]:
            rec["notes"].add("WIDTH_MISMATCH")
        if tm["open"]:
            rec["notes"].add("OPEN_ENDED")
        if ef < sp.h0 or (not tm["open"] and et > sp.h1):
            rec["notes"].add("CLIPPED_TO_HORIZON")
        if sum(b - a for a, b in runs) < fhi - flo:
            rec["notes"].add("CLIPPED_TO_BAND")
        if len(runs) > 1:
            rec["notes"].add("SPLIT_BY_RASTER")
        if et == ef:
            rec["notes"].add("ZERO_SPAN")

    # parent resolution, independent of iteration order
    known = set(aids)
    local_bad = {}
    for aid in aids:
        rec = draft.get(aid)
        if rec is None:
            local_bad[aid] = True
            continue
        if aid in retracted or rec["fault"] is not None:
            local_bad[aid] = True
            continue
        par = (parent_of.get(aid) or "").strip()
        if par and (par not in known or zone_of.get(par) != zone_of.get(aid)):
            rec["fault"] = "PARENT_UNKNOWN"
            local_bad[aid] = True
            continue
        local_bad[aid] = False
    for aid in aids:
        rec = draft.get(aid)
        if rec is None or local_bad.get(aid):
            continue
        seen = set([aid])
        cur = aid
        while True:
            par = (parent_of.get(cur) or "").strip()
            if not par or par not in known:
                break
            if par == aid:
                rec["fault"] = "PARENT_CYCLE"
                local_bad[aid] = True
                break
            if par in seen:
                break
            seen.add(par)
            cur = par
    depth_of = {}
    for aid in aids:
        rec = draft.get(aid)
        if rec is None or local_bad.get(aid):
            continue
        chain = [aid]
        seen = set([aid])
        cur = aid
        tainted = False
        while True:
            par = (parent_of.get(cur) or "").strip()
            if not par or par not in known or par in seen:
                break
            if local_bad.get(par, True):
                tainted = True
                break
            seen.add(par)
            chain.append(par)
            cur = par
        if tainted:
            rec["fault"] = "PARENT_RETRACTED"
            continue
        rec["chain"] = chain
        depth_of[aid] = len(chain)

    for aid in aids:
        rec = draft.get(aid)
        if rec is None:
            continue
        if rec["fault"] is not None:
            rejects[rec["fault"]] = rejects.get(rec["fault"], 0) + 1
            continue
        for n in rec["notes"]:
            notes[n] = notes.get(n, 0) + 1
        if rec.get("et") == rec.get("ef"):
            zero_span += 1

    # extents
    exc_rows = read_csv(sp.root, "guard_exceptions.csv")
    zone_rects = {}
    zone_pre = {}
    zone_guard = {}
    guard_tot = {"occurrences": 0, "cancelled": 0, "added": 0, "subtracted_area": 0}
    stage = {}
    for aid in aids:
        rec = draft.get(aid)
        if rec is None or rec["fault"] is not None:
            continue
        spans, anom = active_spans(sp, events.get(aid) or [], rec["ef"], rec["et"])
        anomalies += anom
        out = []
        for a, b in spans:
            lo, hi = max(a, sp.h0), min(b, sp.h1)
            if hi <= lo:
                continue
            for flo, fhi in rec["runs"]:
                out.append((flo, fhi, lo, hi, aid))
        stage[aid] = out
    if anomalies:
        notes["STATE_ANOMALY"] = anomalies

    for z in ZONES:
        occ, index, canc, added = build_occurrences(sp, z, exc_rows)
        guard_tot["occurrences"] += len(occ)
        guard_tot["cancelled"] += canc
        guard_tot["added"] += added
        pre = []
        for aid in aids:
            if zone_of.get(aid) == z and aid in stage:
                pre.extend(stage[aid])
        post = []
        for r in pre:
            rel = relevant(index, r[0], r[1], r[2], r[3])
            post.extend(subtract_rect(r, rel) if rel else [r])
        pre_u = union_only(pre)
        post_u = union_only(post)
        zone_pre[z] = (len(occ), canc, added)
        zone_guard[z] = pre_u - post_u
        guard_tot["subtracted_area"] += pre_u - post_u
        zone_rects[z] = post

    # parent clipping in dependency order
    final = {}
    for z in ZONES:
        byaid = {}
        for r in zone_rects[z]:
            byaid.setdefault(r[4], []).append(r)
        order = sorted(byaid, key=lambda a: (depth_of.get(a, 1), a))
        for aid in order:
            own = byaid[aid]
            chain = (draft[aid].get("chain") or [aid])[1:]
            for par in chain:
                own = intersect_sets(own, final.get(par, []))
                if not own:
                    break
            final[aid] = reduce_rects(own) if own else []
    return sp, {
        "aids": aids, "draft": draft, "retracted": retracted, "rejects": rejects,
        "notes": notes, "zero_span": zero_span, "counts": counts, "final": final,
        "zone_of": zone_of, "segment": dict((a, draft[a]["seg"]) for a in draft),
        "holder": holder, "layer_wins": layer_wins, "tiebreak": tiebreak,
        "exception": exception, "cycles": cycles, "hops": hops_seen,
        "depth_of": depth_of, "guard": guard_tot, "zone_guard": zone_guard,
        "zone_pre": zone_pre, "suspends": suspends, "events": events,
        "reg": reg, "outdir": outdir,
    }


# ------------------------------------------------------------------ measures

def dump(outdir, name, obj):
    with open(os.path.join(outdir, name), "w", encoding="utf-8") as fh:
        json.dump(obj, fh, sort_keys=True, indent=2)
        fh.write("\n")


def write_artifacts(sp, st):
    outdir = st["outdir"]
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    final = st["final"]
    zone_of = st["zone_of"]
    seg_of = st["segment"]
    holder = st["holder"]
    own = {}
    for aid, rects in final.items():
        own[aid] = sum((r[1] - r[0]) * (r[3] - r[2]) for r in rects)
    measurable = sorted(a for a in final if own.get(a, 0) > 0)

    zone_rects = dict((z, []) for z in ZONES)
    for aid in measurable:
        zone_rects[zone_of[aid]].extend(final[aid])

    cells = dict((z, sp.month_cells(z)) for z in ZONES)
    zone_out = {}
    charges = {}
    for z in ZONES:
        rects = zone_rects[z]
        tcuts = dict((a, k) for k, a, _b in cells[z])
        res = sweep(rects, own=own, tcuts=tcuts, bands=sp.bands, shared_min=sp.shared_min)
        total = sum((r[1] - r[0]) * (r[3] - r[2]) for r in rects)
        months = dict((k, res["months"].get(k, 0)) for k, _a, _b in cells[z])
        bands = dict((b[0], res["bands"].get(b[0], 0)) for b in sp.bands)
        top = sorted(res["charge"].items(), key=lambda kv: (-kv[1], kv[0]))[:sp.top_excess]
        for k, v in res["charge"].items():
            charges[k] = charges.get(k, 0) + v
        std, smr, a, b = sp.tr[z]
        zone_out[z] = {
            "zone": z,
            "utc_offset_standard_sec": std,
            "utc_offset_summer_sec": smr,
            "summer_window_utc": None if a is None else [iso(a), iso(b)],
            "assignments_measurable": sum(1 for x in measurable if zone_of[x] == z),
            "rectangles": len(rects),
            "area_total_assigned": total,
            "area_union": res["union"],
            "area_exclusive": res["excl"],
            "area_shared": res["shared"],
            "area_excess": total - res["union"],
            "guard_occurrences": st["zone_pre"][z][0],
            "guard_subtracted_area": st["zone_guard"][z],
            "excess_charge_top": [[k, v] for k, v in top],
            "band_area_union": bands,
            "month_area_union": months,
        }

    area_union = sum(zone_out[z]["area_union"] for z in ZONES)
    area_excl = sum(zone_out[z]["area_exclusive"] for z in ZONES)
    area_shared = sum(zone_out[z]["area_shared"] for z in ZONES)
    area_total = sum(zone_out[z]["area_total_assigned"] for z in ZONES)
    rect_count = sum(zone_out[z]["rectangles"] for z in ZONES)

    seg_out = {}
    seg_union = {}
    for seg in ("commercial", "public"):
        per_zone = {}
        u = e = sh = 0
        for z in ZONES:
            rects = [r for aid in measurable if zone_of[aid] == z and seg_of.get(aid) == seg
                     for r in final[aid]]
            res = sweep(rects, shared_min=sp.shared_min)
            per_zone[z] = res["union"]
            u += res["union"]
            e += res["excl"]
            sh += res["shared"]
        seg_union[seg] = u
        seg_out[seg] = {"segment": seg, "area_union": u, "area_exclusive": e,
                        "area_shared": sh, "zone_area_union": per_zone,
                        "assignments_measurable": sum(1 for a in measurable
                                                      if seg_of.get(a) == seg)}

    hold_rects = {}
    for aid in measurable:
        key = (holder[aid][0], zone_of[aid])
        hold_rects.setdefault(key, []).extend(final[aid])
    hold_union = {}
    for (hid, z), rects in hold_rects.items():
        hold_union[hid] = hold_union.get(hid, 0) + union_only(rects)
    hold_seg = {}
    for aid in measurable:
        hold_seg[holder[aid][0]] = seg_of.get(aid)

    duty = run_duty(sp, st, hold_rects, cells)
    for seg in ("commercial", "public"):
        tops = sorted(((h, v) for h, v in hold_union.items() if hold_seg.get(h) == seg),
                      key=lambda kv: (-kv[1], kv[0]))[:sp.top_holders]
        seg_out[seg]["top_holders"] = [[h, v] for h, v in tops]
        seg_out[seg]["holders"] = sum(1 for h in hold_seg if hold_seg[h] == seg)
        seg_out[seg]["duty_deficit_months"] = duty["seg_deficit"][seg]
        seg_out[seg]["duty_carry_end"] = duty["seg_carry"][seg]

    zone_bp = largest_remainder(dict((z, zone_out[z]["area_union"]) for z in ZONES),
                                sp.share_bp)
    seg_bp = largest_remainder(dict(seg_union), sp.share_bp)
    summary = {
        "horizon": {"start": sp.h0_text, "end": sp.h1_text, "as_of": sp.as_of_text},
        "assignments_total": len(st["aids"]),
        "assignments_measurable": len(measurable),
        "rectangles": rect_count,
        "area_total_assigned": area_total,
        "area_union": area_union,
        "area_exclusive": area_excl,
        "area_shared": area_shared,
        "area_excess": area_total - area_union,
        "excess_charge_total": sum(charges.values()),
        "shared_ratio_ppm": half_even(area_shared * sp.ppm, area_union) if area_union else 0,
        "zone_area_union": dict((z, zone_out[z]["area_union"]) for z in ZONES),
        "zone_share_bp": zone_bp,
        "segment_area_union": dict(seg_union),
        "segment_share_bp": seg_bp,
        "cross_segment_shared_area": seg_union["commercial"] + seg_union["public"] - area_union,
        "guard_subtracted_area": st["guard"]["subtracted_area"],
    }

    audit = {
        "as_of": sp.as_of_text,
        "precedence_exception": st["exception"],
        "duplicate_tiebreak": st["tiebreak"] + "_recorded_at",
        "clock_keying": sp.keying,
        "layer_governing_counts": st["layer_wins"],
        "alias_fixpoint_depth": st["hops"],
        "alias_cycles": len(st["cycles"]),
        "parent_chain_max_depth": max([st["depth_of"].get(a, 1) for a in measurable] or [0]),
        "parent_rejects": dict((c, st["rejects"].get(c, 0))
                               for c in ("PARENT_UNKNOWN", "PARENT_CYCLE", "PARENT_RETRACTED")),
        "duty": duty["audit"],
        "guard": st["guard"],
    }

    counts = st["counts"]
    quality = {
        "assignments_total": len(st["aids"]),
        "rows_read_total": sum(c["rows_read"] for c in counts.values()),
        "rejects": st["rejects"],
        "notes": st["notes"],
        "retracted": len(st["retracted"]),
        "zero_span": st["zero_span"],
        "manifest_mismatches": sorted(n for n in counts
                                      if sp.declared.get(n) != counts[n]["rows_read"]),
        "source_counts": counts,
    }

    dump(outdir, "summary.json", summary)
    dump(outdir, "policy_audit.json", audit)
    dump(outdir, "data_quality.json", quality)
    for z in ZONES:
        dump(outdir, "region_%s.json" % z, zone_out[z])
    for seg in ("commercial", "public"):
        dump(outdir, "segment_%s.json" % seg, seg_out[seg])


def run_duty(sp, st, hold_rects, cells):
    reg = st["reg"]
    seg_deficit = {"commercial": 0, "public": 0}
    seg_carry = {"commercial": 0, "public": 0}
    audit = {"holders_audited": 0, "months_in_deficit": 0, "total_allowance": 0,
             "total_consumed": 0, "carry_forward_end": 0, "carry_resets": 0,
             "top_deficit": []}
    deficits = []
    susp_by_holder = {}
    for aid, info in st["holder"].items():
        for stamp in st["suspends"].get(aid) or []:
            susp_by_holder.setdefault(info[0], []).append(stamp)
    for seg in ("commercial", "public"):
        plan = {}
        for r in read_csv(sp.root, "duty_budget_%s.csv" % seg):
            allow = int(r["allowance_khz_s"])
            if r["notes"].strip() == "unit=" + sp.duty_minute_token:
                allow *= 60
            plan.setdefault(r["canonical_id"], {})[r["month"]] = allow
        for hid in sorted(plan):
            rows = reg.get(hid)
            if not rows:
                continue
            _cls, zor = pick_reg(rows, None)
            audit["holders_audited"] += 1
            month_list = [(k, a, b) for k, a, b in cells[zor] if k in plan[hid]]
            occ = {}
            for (h, z), rects in hold_rects.items():
                if h != hid:
                    continue
                tcuts = dict((a, k) for k, a, _b in cells[zor])
                res = sweep(rects, tcuts=tcuts, shared_min=sp.shared_min)
                for k, v in res["months"].items():
                    occ[k] = occ.get(k, 0) + v
            carry = 0
            for key, a, b in month_list:
                allow = plan[hid][key]
                audit["total_allowance"] += allow
                use = occ.get(key, 0)
                avail = allow + carry
                consumed = min(avail, use)
                audit["total_consumed"] += consumed
                deficit = use - avail if use > avail else 0
                carry_out = avail - use if avail > use else 0
                hit = any(a <= s < b for s in susp_by_holder.get(hid) or [])
                if hit and carry_out > 0:
                    audit["carry_resets"] += 1
                if hit:
                    carry_out = 0
                if deficit > 0:
                    audit["months_in_deficit"] += 1
                    seg_deficit[seg] += 1
                    deficits.append((deficit, hid, key))
                carry = carry_out
            audit["carry_forward_end"] += carry
            seg_carry[seg] += carry
    deficits.sort(key=lambda t: (-t[0], t[1], t[2]))
    audit["top_deficit"] = [[h, k, d] for d, h, k in deficits[:sp.top_deficit]]
    return {"audit": audit, "seg_deficit": seg_deficit, "seg_carry": seg_carry}


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py <corpus_dir> <output_dir>\n")
        return 2
    sp, st = derive(argv[1], argv[2])
    write_artifacts(sp, st)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
