#!/usr/bin/env python3
"""Wafer start apportionment derivation.

Reads the flat corpus named by ``corpus_index.md`` and writes the nine
artifacts fixed by ``output_contract.md``.  Every rule is read from the
corpus at run time.
"""

import argparse
import bisect
import csv
import json
import os
import re
from collections import defaultdict, Counter
from datetime import datetime, timedelta

UTC_FMT = "%Y-%m-%dT%H:%M:%SZ"
FAR_FUTURE = datetime(9999, 1, 1)


# ---------------------------------------------------------------- helpers

def parse_utc(s):
    if s is None:
        return None
    s = s.strip()
    if not s:
        return None
    if s.endswith("Z"):
        return datetime.strptime(s, UTC_FMT)
    m = re.match(r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})([+-])(\d{2}):?(\d{2})$", s)
    if m:
        base = datetime.strptime(m.group(1) + "T" + m.group(2), "%Y-%m-%dT%H:%M:%S")
        off = int(m.group(4)) * 60 + int(m.group(5))
        if m.group(3) == "-":
            off = -off
        return base - timedelta(minutes=off)
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")


def parse_naive(s):
    return datetime.strptime(s.strip(), "%Y-%m-%dT%H:%M:%S")


def parse_compact(s):
    return datetime.strptime(s.strip(), "%Y%m%d%H%M%S")


def rhu(num, den):
    """round-half-up of num/den with den > 0."""
    if num >= 0:
        return (2 * num + den) // (2 * den)
    return -((2 * (-num) + den) // (2 * den))


def trunc_div(num, den):
    q = abs(num) // den
    return q if num >= 0 else -q


# ---------------------------------------------------------------- policy

def parse_ini(path):
    sections = {}
    cur = None
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            s = raw.strip()
            if not s or s[0] in ";#":
                continue
            if s.startswith("[") and s.endswith("]"):
                cur = s[1:-1]
                sections.setdefault(cur, {})
                continue
            if "=" in s:
                k, v = s.split("=", 1)
                sections.setdefault(cur, {})[k.strip()] = v.strip()
    return sections


def ini_lookup(sections, start, key):
    seen = set()
    name = start
    while name and name not in seen:
        seen.add(name)
        sec = sections.get(name)
        if sec is None:
            break
        if key in sec:
            return sec[key]
        name = sec.get("inherits")
    return sections.get("defaults", {}).get(key)


def parse_properties(path):
    joined = []
    cur = None
    with open(path, encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            if cur is None:
                if not line.strip() or line.strip().startswith("#"):
                    continue
                cur = line.strip()
            else:
                cur = cur + " " + line.strip()
            if cur.endswith("\\"):
                cur = cur[:-1].rstrip()
                continue
            joined.append(cur)
            cur = None
    out = {}
    for line in joined:
        m = re.match(r"^([A-Za-z0-9_.]+)\s*[=:]\s*(.*)$", line)
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


# ---------------------------------------------------------------- clocks

class Clocks(object):
    def __init__(self, path):
        self.marks = defaultdict(dict)
        self.dates = {}
        with open(path, encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                self.marks[row["site"]].setdefault(row["local_date"], []).append(
                    (row["from_local_time"], int(row["utc_offset_minutes"]), row["mark_kind"]))
        for site in self.marks:
            for d in self.marks[site]:
                self.marks[site][d].sort(key=lambda x: x[0])
            self.dates[site] = sorted(self.marks[site])
        self.fold_hits = 0
        self.gap_hits = 0

    def _day(self, site, dstr):
        day = self.marks[site].get(dstr)
        if day is not None:
            return day
        lst = self.dates[site]
        i = bisect.bisect_left(lst, dstr)
        if i == 0:
            return self.marks[site][lst[0]]
        return self.marks[site][lst[i - 1]]

    def to_utc(self, site, naive, fold=0, count=False):
        day = self._day(site, naive.strftime("%Y-%m-%d"))
        tstr = naive.strftime("%H:%M:%S")
        off = day[0][1]
        for ent in day:
            if ent[0] <= tstr:
                off = ent[1]
            else:
                break
        shifted = naive
        for j in range(1, len(day)):
            kind = day[j][2]
            if kind == "standing":
                continue
            prev_off = day[j - 1][1]
            new_off = day[j][1]
            mark_dt = datetime.combine(
                naive.date(), datetime.strptime(day[j][0], "%H:%M:%S").time())
            if kind == "clocks_back":
                delta = prev_off - new_off
                if delta > 0 and mark_dt - timedelta(minutes=delta) <= naive < mark_dt:
                    off = prev_off if int(fold) == 0 else new_off
                    if count:
                        self.fold_hits += 1
            elif kind == "clocks_forward":
                delta = new_off - prev_off
                if delta > 0 and mark_dt <= naive < mark_dt + timedelta(minutes=delta):
                    shifted = naive + timedelta(minutes=delta)
                    off = new_off
                    if count:
                        self.gap_hits += 1
        return shifted - timedelta(minutes=off)


# ---------------------------------------------------------------- corpus

class Corpus(object):
    def __init__(self, data_dir):
        self.dir = data_dir
        self.late = Counter()

    def path(self, name):
        return os.path.join(self.dir, name)

    def _lines(self, name):
        with open(self.path(name), encoding="utf-8") as fh:
            return fh.read().split("\n")

    def declared(self, name):
        lines = self._lines(name)
        if lines and lines[0].startswith("#"):
            m = re.search(r"declared_rows=(\d+)", lines[0])
            if m:
                return int(m.group(1))
        return None

    def rows(self, name, delim=","):
        lines = self._lines(name)
        i = 1 if (lines and lines[0].startswith("#")) else 0
        i += 1  # header
        body = [l for l in lines[i:] if l.strip()]
        if delim == "\t":
            return [l.split("\t") for l in body]
        return list(csv.reader(body))

    def dicts(self, name, delim=","):
        lines = self._lines(name)
        i = 1 if (lines and lines[0].startswith("#")) else 0
        header = lines[i].split("\t") if delim == "\t" else next(csv.reader([lines[i]]))
        out = []
        for r in self.rows(name, delim):
            out.append(dict(zip(header, r)))
        return out


# ------------------------------------------------------- settled readings

def settle_quantity(corpus, props):
    fname = props.get("precedence.prior_period_settlements",
                      "governance_observations.log").strip()
    norm = {"registry": "contract_registry", "order_book": "order_book",
            "contract_registry": "contract_registry"}
    alive = {"order_book", "contract_registry", "later_recorded"}
    with open(corpus.path(fname), encoding="utf-8") as fh:
        for line in fh:
            d = dict(p.split("=", 1) for p in line.split() if "=" in p)
            if "governed_by" not in d:
                continue
            gov = norm.get(d["governed_by"], d["governed_by"])
            later = norm.get(d.get("later_recorded"), d.get("later_recorded"))
            if gov != "order_book":
                alive.discard("order_book")
            if gov != "contract_registry":
                alive.discard("contract_registry")
            if gov != later:
                alive.discard("later_recorded")
    for r in ("order_book", "contract_registry", "later_recorded"):
        if r in alive:
            return r
    return "order_book"


WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6}


def settle_carry_age(corpus):
    txt = open(corpus.path("carry_forward_rules.md"), encoding="utf-8").read()
    cands = []
    m = re.search(r"readings under consideration are ([^.]+)\.", txt)
    if m:
        for tok in re.split(r",|\band\b", m.group(1)):
            tok = tok.strip()
            if tok in WORDS:
                cands.append(WORDS[tok])
            elif tok.isdigit():
                cands.append(int(tok))
            elif tok == "unbounded":
                cands.append("unbounded")
    if not cands:
        cands = [1, 2, 3, "unbounded"]
    alive = list(cands)
    with open(corpus.path("deficit_observations.log"), encoding="utf-8") as fh:
        for line in fh:
            d = dict(p.split("=", 1) for p in line.split() if "=" in p)
            if "lot_age" not in d:
                continue
            age = int(d["lot_age"])
            carried = d.get("deficit_state") == "carried"
            alive = [k for k in alive
                     if (True if k == "unbounded" else age <= k) == carried]
    return alive[0] if alive else "unbounded"


def infer_year(corpus):
    txt = open(corpus.path("temporal_rules.md"), encoding="utf-8").read()
    m = re.search(r"calendar year (\d{4})", txt)
    return int(m.group(1)) if m else 2031


# ---------------------------------------------------------------- engine

def run(data_dir, out_dir, opts=None, write_files=True):
    opts = opts or {}
    C = Corpus(data_dir)

    pol = parse_ini(C.path("derivation_policy.ini"))
    props = parse_properties(C.path("source_declarations.properties"))
    units = parse_ini(C.path("unit_declarations.ini"))
    reasons = json.load(open(C.path("reason_codes.json"), encoding="utf-8"))
    prec_list = reasons["reason_precedence"]

    as_of_s = ini_lookup(pol, "defaults", "as_of_instant")
    as_of = FAR_FUTURE if opts.get("no_as_of") else parse_utc(as_of_s)
    real_as_of = parse_utc(as_of_s)

    n_first = int(ini_lookup(pol, "defaults", "horizon_first_cycle")[1:])
    n_last = int(ini_lookup(pol, "defaults", "horizon_last_cycle")[1:])
    cycle_names = ["C%02d" % i for i in range(n_first, n_last + 1)]
    cyc_idx = {c: i for i, c in enumerate(cycle_names)}
    hh, mm, ss = [int(x) for x in ini_lookup(pol, "defaults", "cycle_start_local_time").split(":")]
    start_days = [int(x) for x in ini_lookup(pol, "defaults", "cycle_start_days").split(",")]
    per_year_month = len(start_days)
    collapse = timedelta(minutes=int(ini_lookup(pol, "defaults", "collapse_window_minutes")))
    max_hops = int(ini_lookup(pol, "defaults", "max_substitution_hops"))
    unranked_rank = int(ini_lookup(pol, "defaults", "unranked_commitment_rank"))
    year = infer_year(C)

    clocks = Clocks(C.path("site_clock_marks.csv"))
    sites = sorted(clocks.marks)
    skew = {}
    for s in sites:
        v = ini_lookup(pol, "site:" + s, "recorder_skew_seconds")
        skew[s] = int(v) if v is not None else 0

    def cycle_local_start(n):
        month = (n - 1) // per_year_month + 1
        return datetime(year, month, start_days[(n - 1) % per_year_month], hh, mm, ss)

    cstart = {}
    for s in sites:
        for i, c in enumerate(cycle_names):
            cstart[(s, c)] = clocks.to_utc(s, cycle_local_start(n_first + i), 0)
        cstart[(s, "END")] = clocks.to_utc(s, datetime(year + 1, 1, 1, hh, mm, ss), 0)
    cyc_bounds = {s: [cstart[(s, c)] for c in cycle_names] for s in sites}

    def cycle_of(site, inst):
        b = cyc_bounds[site]
        if inst < b[0] or inst >= cstart[(site, "END")]:
            return None
        return cycle_names[bisect.bisect_right(b, inst) - 1]

    # ------------------------------------------------ source declarations
    src_name, src_files = {}, {}
    for k, v in props.items():
        m = re.match(r"^source\.([A-Za-z0-9]+)\.name$", k)
        if m:
            src_name[m.group(1)] = v
        m = re.match(r"^source\.([A-Za-z0-9]+)\.files$", k)
        if m:
            src_files[m.group(1)] = [x.strip() for x in v.split(",") if x.strip()]
    name_code = {v: k for k, v in src_name.items()}
    audit_files = [x.strip() for x in props.get("source.AUT.audit", "").split(",") if x.strip()]
    cutover_cycle = props.get("precedence.cutover_cycle")

    OBK, REG, LGI = name_code["order_book"], name_code["contract_registry"], \
        name_code["legacy_intake"]
    SRC_ORDER = [OBK, REG, LGI]
    rank_of = {c: i for i, c in enumerate(SRC_ORDER)}

    prec = {"before": {}, "from": {}}
    for k, v in props.items():
        m = re.match(r"^precedence\.before_cutover\.(\w+)$", k)
        if m:
            prec["before"][m.group(1)] = name_code[v]
        m = re.match(r"^precedence\.from_cutover\.(\w+)$", k)
        if m:
            prec["from"][m.group(1)] = name_code[v]

    withheld_qty = opts.get("force_qty_rule") or settle_quantity(C, props)
    carry_age = settle_carry_age(C)
    if opts.get("force_carry_age") is not None:
        carry_age = opts["force_carry_age"]
    carry_age_n = 10 ** 9 if carry_age == "unbounded" else int(carry_age)
    prec["before"]["quantity"] = {"order_book": OBK, "contract_registry": REG,
                                  "later_recorded": "LATER"}[withheld_qty]

    def lot_size(section, key, default=25):
        v = units.get(section, {}).get(key)
        return int(v) if v else default

    obk_lot = lot_size("order_book", "lot_size_wafers")
    reg_lot = lot_size("contract_registry", "lot_size_wafers")
    ceil_lot = lot_size("ceilings", "lot_size_wafers")
    cmt_lot = lot_size("commitments", "lot_size_wafers")
    cap_lot = lot_size("capacity", "lot_equivalent_wafers")
    intake_hundredths = units.get("intake", {}).get("quantity_scale") == "hundredths"

    dq = Counter()
    parsed, admitted, declared = Counter(), Counter(), Counter()
    header_gaps = {}

    def note_file(code, fname, nparsed):
        d = C.declared(fname)
        parsed[code] += nparsed
        if d is None:
            declared[code] += nparsed
        else:
            declared[code] += d
            if d != nparsed:
                header_gaps[fname] = d - nparsed

    # ---------------------------------------------------- request rows
    rows = []
    for fname in src_files[OBK]:
        raw = C.rows(fname)
        note_file(OBK, fname, len(raw))
        for r in raw:
            if r[4] != r[5]:
                dq["restatement_gaps"] += 1
            if r[6] == "lots":
                dq["lot_unit_rows"] += 1
            rec = parse_utc(r[9])
            if rec > as_of:
                C.late[OBK] += 1
                continue
            admitted[OBK] += 1
            qh = int(r[4]) * 100 * (obk_lot if r[6] == "lots" else 1)
            rows.append({"src": OBK, "ref": r[0], "cust": r[1], "site": r[2],
                         "node": r[3].strip() or None, "qh": qh,
                         "eff": clocks.to_utc(r[2], parse_naive(r[7]), r[8], count=True),
                         "rec": rec, "key": tuple(r)})

    for fname in src_files[REG]:
        raw = C.rows(fname, "\t")
        note_file(REG, fname, len(raw))
        for r in raw:
            if len(r) < 10:
                dq["row_truncated"] += 1
            node = r[3].strip()
            if node == "":
                dq["node_empty"] += 1
            elif node == "\\N":
                dq["node_backslash_n"] += 1
            if r[5] == "lots":
                dq["lot_unit_rows"] += 1
            rec = parse_utc(r[7])
            if rec > as_of:
                C.late[REG] += 1
                continue
            admitted[REG] += 1
            qh = int(r[4]) * 100 * (reg_lot if r[5] == "lots" else 1)
            rows.append({"src": REG, "ref": r[0], "cust": r[1], "site": r[2],
                         "node": node if node not in ("", "\\N") else None,
                         "qh": qh, "eff": parse_utc(r[6]), "rec": rec, "key": tuple(r)})

    for fname in src_files[LGI]:
        with open(C.path(fname), encoding="utf-8") as fh:
            raw = [l.rstrip("\n") for l in fh if l.strip()]
        note_file(LGI, fname, len(raw))
        for line in raw:
            rec = parse_compact(line[64:78])
            if rec > as_of:
                C.late[LGI] += 1
                continue
            admitted[LGI] += 1
            site = line[26:34].strip()
            qh = int(line[40:50]) * (1 if intake_hundredths else 100)
            rows.append({"src": LGI, "ref": line[0:12].strip(), "cust": line[12:26].strip(),
                         "site": site, "node": line[34:40].strip() or None, "qh": qh,
                         "eff": clocks.to_utc(site, parse_compact(line[50:64]), 0, count=True),
                         "rec": rec, "key": (line,)})

    # ---------------------------------------------------- dedup per source
    bysrcref = defaultdict(list)
    for r in rows:
        bysrcref[(r["src"], r["ref"])].append(r)
    dup_ident = dup_conf = 0
    deduped = []
    for k in sorted(bysrcref):
        grp = bysrcref[k]
        if len(grp) == 1:
            deduped.append(grp[0])
            continue
        if all(g["key"] == grp[0]["key"] for g in grp):
            dup_ident += len(grp) - 1
            deduped.append(grp[0])
        else:
            dup_conf += len(grp) - 1
            grp.sort(key=lambda g: (g["rec"], g["ref"]))
            deduped.append(grp[-1])
    rows = deduped

    # ---------------------------------------------------- registers
    def admit(code, fname, delim=","):
        allrows = C.dicts(fname, delim)
        note_file(code, fname, len(allrows))
        keep = []
        for r in allrows:
            rec = parse_utc(r.get("recorded_utc"))
            if rec is not None and rec > as_of:
                continue
            r["_rec"] = rec
            keep.append(r)
        C.late[code] += len(allrows) - len(keep)
        admitted[code] += len(keep)
        return allrows, keep

    _, alias_rows = admit("ALS", "customer_alias_map.csv")
    alias_by = defaultdict(list)
    for r in alias_rows:
        alias_by[r["alias_code"]].append(r)

    _, mst = admit("MST", "customer_master.csv")
    epochs = defaultdict(dict)
    master_rows = defaultdict(list)
    for r in mst:
        es = int(r["epoch_seq"])
        epochs[r["customer_id"]][es] = (parse_utc(r["epoch_from_utc"]),
                                        parse_utc(r["epoch_to_utc"]), r["segment"])
        master_rows[(r["customer_id"], es)].append(r)

    def resolve_ref(raw, eff):
        code = raw.strip()
        m = re.match(r"^([A-Za-z])-(\d+)$", code)
        if m:
            return "CUS-%04d" % int(m.group(2))
        for _ in range(4):
            m = re.match(r"^CUS-(\d+)$", code)
            if m:
                return "CUS-%04d" % int(m.group(1))
            cands = [a for a in alias_by.get(code, ())
                     if parse_utc(a["effective_utc"]) <= eff < parse_utc(a["expires_utc"])]
            if not cands:
                return None
            cands.sort(key=lambda a: (int(a["revision_seq"]), a["_rec"]))
            code = cands[-1]["target_code"]
        return None

    def epoch_of(cid, inst):
        d = epochs.get(cid)
        if not d:
            return None
        for es in sorted(d):
            fr, to, _ = d[es]
            if fr <= inst < to:
                return es
        return None

    unknown_rows, good = [], []
    for r in rows:
        cid = resolve_ref(r["cust"], r["eff"])
        es = epoch_of(cid, r["eff"]) if cid else None
        if cid is None or es is None:
            unknown_rows.append(r)
            continue
        r["cid"] = cid
        r["ident"] = "%s#%d" % (cid, es)
        good.append(r)

    # ---------------------------------------------------- collapse
    groups = []
    bykey = defaultdict(list)
    for r in good:
        bykey[(r["ident"], r["site"])].append(r)
    cross_collapsed = 0
    for k in sorted(bykey):
        lst = sorted(bykey[k], key=lambda r: (r["eff"], rank_of[r["src"]], r["ref"]))
        i = 0
        while i < len(lst):
            base = lst[i]["eff"]
            j = i
            while j < len(lst) and lst[j]["eff"] - base <= collapse:
                j += 1
            groups.append(lst[i:j])
            cross_collapsed += j - i - 1
            i = j

    # ---------------------------------------------------- audit, authority
    audit, by_ref_audit = {}, {}
    for fname in audit_files:
        with open(C.path(fname), encoding="utf-8") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if not line.strip():
                    continue
                if line.startswith("  "):
                    dq["log_continuations"] += 1
                    continue
                parts = line.split()
                d = dict(p.split("=", 1) for p in parts[1:] if "=" in p)
                site = d.get("site")
                inst = clocks.to_utc(site, parse_naive(parts[0]), 0, count=True) \
                    - timedelta(seconds=skew.get(site, 0))
                ent = {"apl": d.get("apl"), "approver": d.get("approver"),
                       "scope": d.get("scope"), "ref": d.get("ref"), "inst": inst}
                if ent["apl"] and ent["apl"] != "none":
                    audit[ent["apl"]] = ent
                    if ent["ref"]:
                        by_ref_audit[ent["ref"]] = ent

    _, aut = admit("AUT", "authority_roles.csv")
    grants = defaultdict(list)
    for r in aut:
        grants[(r["approver_id"], r["role"], r["scope"])].append(r)
    scopes_by_approver = defaultdict(list)
    for k, lst in grants.items():
        lst.sort(key=lambda r: (parse_utc(r["effective_utc"]), int(r["revision_seq"])))
        g = lst[-1]
        scopes_by_approver[k[0]].append((k[2], parse_utc(g["effective_utc"]),
                                         parse_utc(g["expires_utc"])))

    def has_scope(approver, scope, inst):
        for sc, fr, to in scopes_by_approver.get(approver, ()):
            if (sc == scope or sc == "any") and fr <= inst < to:
                return True
        return False

    def endorsed(apl, scope):
        if not apl or apl == "none":
            return False
        ent = audit.get(apl)
        return bool(ent) and has_scope(ent["approver"], scope, ent["inst"])

    # ---------------------------------------------------- retractions
    _, rtr = admit("RTR", "retraction_notices.csv")
    targets = defaultdict(list)
    for r in rtr:
        targets[r["target_id"]].append(r)
    _live = {}

    def retraction_live(rid, stack=()):
        if rid in _live:
            return _live[rid]
        if rid in stack:
            return True
        live = True
        for t in targets.get(rid, ()):
            if retraction_live(t["retraction_id"], stack + (rid,)):
                live = False
                break
        _live[rid] = live
        return live

    def is_retracted(tid):
        for t in targets.get(tid, ()):
            if retraction_live(t["retraction_id"]):
                return True
        return False

    # ---------------------------------------------------- capacity
    cap_all, cap = admit("CAP", "site_capacity_declarations.csv")
    for r in cap_all:
        if r["value"].startswith("("):
            dq["paren_negatives"] += 1
        if r["unit"] == "lot_equivalents":
            dq["lot_unit_rows"] += 1
    for r in cap:
        r["_eff"] = clocks.to_utc(r["site"], parse_naive(r["effective_local"]),
                                  r["fold"], count=True)
        v = r["value"].strip()
        neg = v.startswith("(")
        n = int(v.strip("()")) * (-1 if neg else 1)
        if r["unit"] == "lot_equivalents":
            n *= cap_lot
        r["_v"] = n
    cap_groups = defaultdict(list)
    for r in cap:
        cap_groups[(r["site"], r["cycle"], r["tool_group"])].append(r)
    capacity, qualified = {}, {}
    for s in sites:
        for c in cycle_names:
            capacity[(s, c)] = 0
            qualified[(s, c)] = set()
    for (s, c, tg), lst in cap_groups.items():
        if (s, c) not in capacity:
            continue
        start = cstart[(s, c)]
        bases = [r for r in lst if r["basis"] == "absolute" and r["_eff"] <= start]
        if not bases:
            continue
        bases.sort(key=lambda r: (r["_eff"], int(r["revision_seq"])))
        base = bases[-1]
        if base["status"] != "online":
            continue
        val = base["_v"]
        deltas = [r for r in lst if r["basis"] == "delta"
                  and base["_eff"] <= r["_eff"] <= start]
        deltas.sort(key=lambda r: (r["_eff"], int(r["revision_seq"])))
        for d in deltas:
            val += d["_v"]
        capacity[(s, c)] += max(0, val)
        for nd in base["nodes"].split("|"):
            if nd.strip():
                qualified[(s, c)].add(nd.strip())

    # ---------------------------------------------------- substitution
    _, sub = admit("SUB", "node_substitution_factors.csv")
    for r in sub:
        r["_eff"] = clocks.to_utc(r["site"], parse_naive(r["effective_local"]),
                                  r["fold"], count=True)
    sub_groups = defaultdict(list)
    for r in sub:
        sub_groups[(r["site"], r["cycle"], r["from_node"], r["to_node"])].append(r)
    edge_map = defaultdict(lambda: defaultdict(list))
    for (s, c, fn, tn), lst in sub_groups.items():
        start = cstart.get((s, c))
        if start is None:
            continue
        cands = [r for r in lst if r["_eff"] <= start]
        if not cands:
            continue
        cands.sort(key=lambda r: (r["_eff"], int(r["revision_seq"])))
        if cands[-1]["status"] == "in_force":
            edge_map[(s, c)][fn].append((int(cands[-1]["factor_per_100"]), tn))
    for k in edge_map:
        for fn in edge_map[k]:
            edge_map[k][fn].sort()

    def walk(site, cycle, node):
        qs = qualified[(site, cycle)]
        if node in qs:
            return ("OK", node, 0, 1, 1)
        visited = {node}
        cur, numer, steps = node, 1, 0
        em = edge_map.get((site, cycle), {})
        while steps < max_hops:
            cands = em.get(cur)
            if not cands:
                return ("NO_QUALIFIED_NODE", "", 0, 1, 1)
            f, tn = cands[0]
            numer *= f
            steps += 1
            cur = tn
            if cur in qs:
                return ("OK", cur, steps, numer, 100 ** steps)
            if cur in visited:
                return ("UNRESOLVABLE_SUB_CYCLE", "", 0, 1, 1)
            visited.add(cur)
        return ("NO_QUALIFIED_NODE", "", 0, 1, 1)

    # ---------------------------------------------------- ceilings
    ceils = []
    for fname in src_files["CEIL"]:
        allr, keep = admit("CEIL", fname)
        for r in allr:
            if r["unit"] == "lots":
                dq["lot_unit_rows"] += 1
        ceils.extend(keep)
    ceil_by = defaultdict(list)
    for r in ceils:
        r["_eff"] = clocks.to_utc(r["declaring_site"], parse_naive(r["effective_local"]),
                                  r["fold"], count=True)
        r["_h"] = int(r["ceiling"]) * 100 * (ceil_lot if r["unit"] == "lots" else 1)
        ceil_by[(r["customer_id"], int(r["epoch_seq"]))].append(r)
    for k in ceil_by:
        ceil_by[k].sort(key=lambda r: (r["_eff"], int(r["revision_seq"])))

    def ceiling_h(cid, es, start):
        best = None
        for r in ceil_by.get((cid, es), ()):
            if r["_eff"] <= start:
                best = r
            else:
                break
        return None if best is None else best["_h"]

    # ---------------------------------------------------- commitments
    agr_all, agr = admit("AGR", "commitment_agreements.csv")
    for r in agr_all:
        if r["unit"] == "lots":
            dq["lot_unit_rows"] += 1
    agr_by = defaultdict(list)
    for r in agr:
        r["_eff"] = clocks.to_utc(r["site"], parse_naive(r["effective_local"]), 0, count=True)
        r["_h"] = int(r["floor"]) * 100 * (cmt_lot if r["unit"] == "lots" else 1)
        agr_by[r["agreement_id"]].append(r)
    for k in agr_by:
        agr_by[k].sort(key=lambda r: (r["_eff"], int(r["revision_seq"])))

    _, pri = admit("PRI", "priority_register.csv")
    pri_by = defaultdict(list)
    for r in pri:
        aid = r["agreement_id"]
        site = agr_by[aid][0]["site"] if agr_by.get(aid) else sites[0]
        r["_eff"] = clocks.to_utc(site, parse_naive(r["effective_local"]), 0, count=True)
        pri_by[aid].append(r)
    for k in pri_by:
        pri_by[k].sort(key=lambda r: (r["_eff"], int(r["revision_seq"])))

    _, exc = admit("EXC", "commitment_exceptions.csv")

    # ---------------------------------------------------- events, notices
    evts = []
    for fname in src_files["EVT"]:
        with open(C.path(fname), encoding="utf-8") as fh:
            part = [json.loads(l) for l in fh if l.strip()]
        note_file("EVT", fname, len(part))
        for e in part:
            rec = parse_utc(e["recorded_utc"])
            if rec > as_of:
                C.late["EVT"] += 1
                continue
            e["_rec"] = rec
            evts.append(e)
    admitted["EVT"] = len(evts)
    evt_by_ref = defaultdict(list)
    for e in evts:
        evt_by_ref[e["request_ref"]].append(e)

    amds = []
    for fname in src_files["AMD"]:
        with open(C.path(fname), encoding="utf-8") as fh:
            part = [json.loads(l) for l in fh if l.strip()]
        note_file("AMD", fname, len(part))
        for a in part:
            rec = parse_utc(a["recorded_utc"])
            if rec > as_of:
                C.late["AMD"] += 1
                continue
            a["_rec"] = rec
            amds.append(a)
    admitted["AMD"] = len(amds)
    amd_by_ref = defaultdict(list)
    for a in amds:
        amd_by_ref[a["request_ref"]].append(a)

    clk_rows = len(C.dicts("site_clock_marks.csv"))
    parsed["CLK"] = declared["CLK"] = admitted["CLK"] = clk_rows
    obs_rows = 0
    for fname in src_files.get("OBS", ()):
        with open(C.path(fname), encoding="utf-8") as fh:
            obs_rows += sum(1 for l in fh if l.strip())
    parsed["OBS"] = declared["OBS"] = admitted["OBS"] = obs_rows

    # ================================================== build the requests
    tally = Counter()
    requests = []
    out_of_scope = defaultdict(list)
    for r in unknown_rows:
        out_of_scope[r["site"]].append({"request_ref": r["ref"],
                                        "customer": r["cust"].strip(),
                                        "site": r["site"], "reason": "UNKNOWN_CUSTOMER"})
    dq["unknown_customer_rows"] = len(unknown_rows)
    apply_unendorsed = opts.get("apply_unendorsed", False)

    for grp in groups:
        site = grp[0]["site"]
        earliest = min(g["eff"] for g in grp)
        side = "before" if earliest < cstart[(site, cutover_cycle)] else "from"
        bysrc = {}
        for g in grp:
            cur = bysrc.get(g["src"])
            if cur is None or (g["rec"], g["ref"]) > (cur["rec"], cur["ref"]):
                bysrc[g["src"]] = g

        def pick(field):
            want = prec[side].get(field)
            if want == "LATER":
                cands = sorted((bysrc[s] for s in SRC_ORDER if s in bysrc),
                               key=lambda g: (g["rec"], -rank_of[g["src"]]))
                return cands[-1]
            if want in bysrc:
                return bysrc[want]
            for s in SRC_ORDER:
                if s in bysrc:
                    return bysrc[s]
            return None

        qh = pick("quantity")["qh"]
        eff = pick("effective")["eff"]
        node = None
        want = prec[side].get("node")
        if want in bysrc and bysrc[want]["node"]:
            node = bysrc[want]["node"]
        else:
            for s in SRC_ORDER:
                if s in bysrc and bysrc[s]["node"]:
                    node = bysrc[s]["node"]
                    break
        ref = None
        for s in SRC_ORDER:
            if s in bysrc:
                ref = bysrc[s]["ref"]
                break

        refs = set(g["ref"] for g in grp)
        latest_rec = max(g["rec"] for g in grp)
        earliest_rec = min(g["rec"] for g in grp)

        notices = []
        for rf in sorted(refs):
            notices.extend(amd_by_ref.get(rf, ()))
        chain_bad = False
        if notices:
            byid = {n["notice_id"]: n for n in notices}
            for n in notices:
                seen, cur = set(), n
                while cur is not None:
                    if cur["notice_id"] in seen:
                        chain_bad = True
                        break
                    seen.add(cur["notice_id"])
                    cur = byid.get(cur["supersedes"])
                if chain_bad:
                    break
        if chain_bad:
            tally["amendment_chains_unresolvable"] += 1
        cands = []
        if not chain_bad:
            for n in notices:
                if n["_rec"] <= latest_rec:
                    tally["amendments_early"] += 1
                    continue
                if is_retracted(n["notice_id"]):
                    tally["amendments_retracted"] += 1
                    continue
                if not endorsed(n.get("approval_ref"), n["field"]):
                    tally["amendments_unendorsed"] += 1
                    if not apply_unendorsed:
                        continue
                cands.append(n)
        cand_ids = set(n["notice_id"] for n in cands)
        memo = {}

        def survives(nid, stack=()):
            if nid in memo:
                return memo[nid]
            if nid not in cand_ids:
                return False
            if nid in stack:
                return True
            res = True
            for m in cands:
                if m["supersedes"] == nid and m["notice_id"] != nid \
                        and survives(m["notice_id"], stack + (nid,)):
                    res = False
                    break
            memo[nid] = res
            return res

        applied = {}
        for n in cands:
            if not survives(n["notice_id"]):
                continue
            cur = applied.get(n["field"])
            if cur is None or (n["_rec"], n["notice_id"]) > (cur["_rec"], cur["notice_id"]):
                applied[n["field"]] = n
        for f in sorted(applied):
            n = applied[f]
            tally["amendments_applied"] += 1
            if f == "quantity":
                qh = int(n["value"]) * 100
            elif f == "node":
                node = n["value"]
            elif f == "effective":
                eff = parse_utc(n["value"])

        cyc = cycle_of(site, eff)
        cid = grp[0]["cid"]
        es = epoch_of(cid, eff)
        if es is None:
            es = int(grp[0]["ident"].split("#")[1])
        ident = "%s#%d" % (cid, es)

        if cyc is None:
            dq["out_of_horizon_rows"] += len(grp)
            out_of_scope[site].append({"request_ref": ref, "customer": ident,
                                       "site": site, "reason": "OUT_OF_HORIZON"})
            continue

        events = []
        for rf in sorted(refs):
            events.extend(evt_by_ref.get(rf, ()))
        state = "approved"
        if events:
            events.sort(key=lambda e: (e["_rec"], e["version"], e["event_id"]))
            highest = None
            seen_v = set()
            for e in events:
                v = e["version"]
                if v in seen_v:
                    tally["duplicate_version_events"] += 1
                seen_v.add(v)
                if highest is not None and v <= highest:
                    tally["stale_events"] += 1
                    continue
                highest = v
                act = e["action"]
                ns = None
                if act == "hold" and state == "approved":
                    ns = "held"
                elif act == "release" and state == "held":
                    ns = "approved"
                elif act == "withdraw" and state in ("approved", "held"):
                    ns = "withdrawn"
                elif act == "reject" and state == "approved":
                    ns = "rejected"
                elif act == "reinstate" and state == "withdrawn":
                    if "authority_ref" in e:
                        ar = e["authority_ref"]
                        ok = endorsed(ar, "state") if ar else False
                    else:
                        ent = by_ref_audit.get(e["event_id"])
                        ok = bool(ent) and has_scope(ent["approver"], "state", ent["inst"])
                    if ok:
                        ns = "approved"
                if ns is None:
                    tally["illegal_transitions"] += 1
                else:
                    state = ns

        requests.append({"site": site, "cycle": cyc, "ident": ident, "cid": cid,
                         "epoch": es, "ref": ref, "node": node, "qh": qh, "eff": eff,
                         "side": side, "state": state, "chain_bad": chain_bad,
                         "all_late": earliest_rec > real_as_of})

    # ---------------------------------------- per request derivation
    first_epoch = {cid: min(d) for cid, d in epochs.items()}
    for q in requests:
        s, c = q["site"], q["cycle"]
        start = cstart[(s, c)]
        fail = None
        if q["node"] is None:
            fail = "NODE_NOT_STATED"
            served, hops, numer, denom = "", 0, 1, 1
        else:
            st, served, hops, numer, denom = walk(s, c, q["node"])
            if st != "OK":
                fail = st
        q["served"], q["hops"], q["numer"], q["denom"] = served, hops, numer, denom
        q["quantity_equiv"] = rhu(q["qh"] * numer, denom * 100)
        ch = ceiling_h(q["cid"], q["epoch"], start)
        q["ceiling_h"] = ch
        q["ceiling_equiv"] = 0 if ch is None else rhu(ch * numer, denom * 100)
        q["segment"] = epochs[q["cid"]][q["epoch"]][2]
        mr = master_rows[(q["cid"], q["epoch"])]
        eligible = [r for r in mr if parse_utc(r["effective_utc"]) <= start]
        eligible.sort(key=lambda r: (parse_utc(r["effective_utc"]), int(r["revision_seq"])))
        q["status"] = eligible[-1]["status"] if eligible else (mr[0]["status"] if mr else "active")
        if q["epoch"] != first_epoch[q["cid"]]:
            tally["epoch_reassignments"] += 1

        applicable = []
        if fail:
            applicable.append(fail)
        if q["chain_bad"]:
            applicable.append("UNRESOLVABLE_CHAIN")
        if q["status"] == "suspended":
            applicable.append("CUSTOMER_SUSPENDED")
        if q["state"] == "rejected":
            applicable.append("REJECTED")
        elif q["state"] == "withdrawn":
            applicable.append("WITHDRAWN")
        elif q["state"] == "held":
            applicable.append("ON_HOLD")
        if ch is not None and q["ceiling_equiv"] == 0:
            applicable.append("CAP_ZERO")
            tally["ceiling_zero"] += 1
        applicable.sort(key=prec_list.index)
        q["gate_reason"] = applicable[0] if applicable else None
        q["claims"] = not applicable
        q["granted_wafers"] = 0
        for f in ("carried_in_equiv", "claim_equiv", "floor_equiv", "granted_equiv",
                  "deficit_equiv", "carried_out_equiv"):
            q[f] = 0

    # ---------------------------------------- obligations
    obligations = defaultdict(list)
    live_exc = defaultdict(list)
    for e in sorted(exc, key=lambda e: e["exception_id"]):
        if is_retracted(e["exception_id"]):
            tally["exceptions_retracted"] += 1
            continue
        if not endorsed(e["approval_ref"], "commitment"):
            tally["exceptions_unendorsed"] += 1
            continue
        tally["exceptions_applied"] += 1
        live_exc[(e["agreement_id"], e["cycle"])].append(e)

    for aid in sorted(agr_by):
        lst = agr_by[aid]
        site = lst[0]["site"]
        cid = lst[0]["customer_id"]
        for c in cycle_names:
            start = cstart[(site, c)]
            cands = [r for r in lst if r["_eff"] <= start]
            if not cands:
                continue
            g = cands[-1]
            fi, ui, ci = cyc_idx.get(g["first_cycle"]), cyc_idx.get(g["until_cycle"]), cyc_idx[c]
            if fi is None or ui is None or not (fi <= ci <= ui):
                continue
            rec = g["recurrence"]
            if rec == "every_cycle":
                due = True
            elif rec == "alternate_from_first":
                due = (ci - fi) % 2 == 0
            elif rec == "first_cycle_of_month":
                due = int(c[1:]) % 2 == 1
            else:
                due = False
            if not due:
                continue
            tgt, drop = c, False
            for e in live_exc.get((aid, c), ()):
                if e["action"] == "skip":
                    drop = True
                elif e["action"] == "move_to":
                    tgt = e["target_cycle"]
            if drop or tgt not in cyc_idx:
                continue
            pl = [r for r in pri_by.get(aid, ()) if r["_eff"] <= cstart[(site, tgt)]]
            rank = int(pl[-1]["priority_rank"]) if pl else unranked_rank
            obligations[(site, tgt)].append({"aid": aid, "cid": cid, "rank": rank,
                                             "floor_h": g["_h"]})

    # ---------------------------------------- apportionment
    by_cell = defaultdict(list)
    for q in requests:
        by_cell[(q["site"], q["cycle"])].append(q)

    lots = defaultdict(list)
    deficit_to_date, granted_to_date = Counter(), Counter()
    cell_report = {}
    ignore_carry = opts.get("ignore_carry", False)
    no_clearing = opts.get("no_clearing", False)
    pro_rata = opts.get("pro_rata", False)
    remainder_units = remainder_cells = 0

    for s in sites:
        for ci, c in enumerate(cycle_names):
            cap_v = capacity[(s, c)]
            here = by_cell.get((s, c), [])
            here.sort(key=lambda q: (q["ident"], q["ref"]))
            claimers = [q for q in here if q["claims"]]
            attach = {}
            for q in sorted(claimers, key=lambda q: (q["eff"], q["ref"])):
                attach.setdefault(q["ident"], q)

            for q in claimers:
                cin = 0
                if not ignore_carry and attach[q["ident"]] is q:
                    cin = sum(a for _, a in lots[(q["ident"], s)])
                q["carried_in_equiv"] = cin
                total = q["quantity_equiv"] + cin
                if q["ceiling_h"] is None:
                    q["claim_equiv"] = total
                else:
                    ce = q["ceiling_equiv"]
                    if ce < total:
                        tally["ceiling_binding"] += 1
                    q["claim_equiv"] = min(total, ce)

            obs = sorted(obligations.get((s, c), ()), key=lambda o: (o["rank"], o["aid"]))
            used = floor_total = 0
            for o in obs:
                cands = sorted((q for q in claimers if q["cid"] == o["cid"]),
                               key=lambda q: (q["eff"], q["ref"]))
                if not cands:
                    tally["floors_unmatched"] += 1
                    continue
                tgt = cands[0]
                fl = rhu(o["floor_h"] * tgt["numer"], tgt["denom"] * 100)
                amount = max(0, min(fl, tgt["claim_equiv"] - tgt["floor_equiv"], cap_v - used))
                tgt["floor_equiv"] += amount
                used += amount
                floor_total += amount
                if amount >= fl:
                    tally["floors_honoured_full"] += 1
                else:
                    tally["floors_honoured_short"] += 1

            if pro_rata:
                apportion_pro_rata(claimers, cap_v)
                level = 0
            else:
                level, handed = apportion(claimers, cap_v)
                remainder_units += handed
                if handed > 0:
                    remainder_cells += 1

            granted = sum(q["granted_equiv"] for q in claimers)
            residual = cap_v - granted
            cell_report[(s, c)] = {
                "cycle": c, "capacity_equiv": cap_v, "fill_level": level,
                "floor_total_equiv": floor_total, "granted_equiv": granted,
                "residual_equiv": residual, "request_count": len(here),
                "binding": residual == 0}

            for q in here:
                if q["claims"]:
                    q["deficit_equiv"] = q["claim_equiv"] - q["granted_equiv"]
                key = (q["ident"], s)
                deficit_to_date[key] += q["deficit_equiv"]
                granted_to_date[key] += q["granted_equiv"]
                q["granted_to_date_equiv"] = granted_to_date[key]
                q["deficit_to_date_equiv"] = deficit_to_date[key]
                q["granted_wafers"] = trunc_div(q["granted_equiv"] * q["denom"], q["numer"])

            if not ignore_carry:
                for q in claimers:
                    key = (q["ident"], s)
                    carried_part = max(0, q["claim_equiv"] - q["quantity_equiv"])
                    g_carried = min(q["granted_equiv"], carried_part)
                    rem = g_carried
                    lst = lots[key]
                    i = 0
                    while rem > 0 and i < len(lst):
                        take = min(rem, lst[i][1])
                        lst[i][1] -= take
                        rem -= take
                        i += 1
                    lots[key] = [x for x in lst if x[1] > 0]
                    newlot = q["quantity_equiv"] - (q["granted_equiv"] - g_carried)
                    if newlot > 0:
                        lots[key].append([ci, newlot])
                for key in list(lots):
                    if key[1] != s:
                        continue
                    keep = []
                    for origin, amt in lots[key]:
                        if (ci + 1) - origin <= carry_age_n:
                            keep.append([origin, amt])
                        else:
                            tally["lots_expired"] += 1
                    lots[key] = keep
                if residual > 0 and not no_clearing:
                    tally["resets"] += 1
                    for key in list(lots):
                        if key[1] == s and lots[key]:
                            tally["lots_cleared"] += len(lots[key])
                            lots[key] = []

            for q in here:
                if q["claims"] and attach[q["ident"]] is q:
                    q["carried_out_equiv"] = sum(a for _, a in lots[(q["ident"], s)])
                else:
                    q["carried_out_equiv"] = 0
                if q["claims"]:
                    cl, g = q["claim_equiv"], q["granted_equiv"]
                    if cl > 0 and g == cl:
                        q["outcome"] = "FULL"
                    elif 0 < g < cl:
                        q["outcome"] = "PARTIAL"
                    elif cl > 0:
                        q["outcome"] = "ZERO"
                    else:
                        q["outcome"] = "EXCLUDED"
                    q["reason"] = "NONE"
                else:
                    q["outcome"] = "EXCLUDED"
                    q["reason"] = q["gate_reason"] or "NONE"

    for q in requests:
        tally["hops_%d" % q["hops"]] += 1
        tally["cutover_" + q["side"]] += 1
        if q["reason"] == "NO_QUALIFIED_NODE":
            tally["no_qualified_node"] += 1
        elif q["reason"] == "UNRESOLVABLE_SUB_CYCLE":
            tally["substitution_cycles"] += 1

    # ================================================== artifacts
    region = {}
    for s in sites:
        led = sorted((q for q in requests if q["site"] == s),
                     key=lambda q: (cyc_idx[q["cycle"]], q["ident"], q["ref"]))
        rows_out = [{
            "cycle": q["cycle"], "request_ref": q["ref"], "customer": q["ident"],
            "segment": q["segment"], "requested_node": q["node"] or "",
            "served_node": q["served"], "hops": q["hops"],
            "quantity_equiv": q["quantity_equiv"], "carried_in_equiv": q["carried_in_equiv"],
            "ceiling_equiv": q["ceiling_equiv"], "claim_equiv": q["claim_equiv"],
            "floor_equiv": q["floor_equiv"], "granted_equiv": q["granted_equiv"],
            "granted_wafers": q["granted_wafers"], "deficit_equiv": q["deficit_equiv"],
            "carried_out_equiv": q["carried_out_equiv"],
            "granted_to_date_equiv": q["granted_to_date_equiv"],
            "deficit_to_date_equiv": q["deficit_to_date_equiv"],
            "outcome": q["outcome"], "reason": q["reason"]} for q in led]
        cyc_out = [cell_report[(s, c)] for c in cycle_names]
        region[s] = {
            "site": s, "as_of": as_of_s, "cycles": cyc_out, "ledger": rows_out,
            "out_of_scope": sorted(out_of_scope.get(s, []),
                                   key=lambda o: (o["request_ref"], o["customer"], o["reason"])),
            "totals": {
                "ledger_rows": len(rows_out),
                "granted_equiv": sum(r["granted_equiv"] for r in rows_out),
                "claim_equiv": sum(r["claim_equiv"] for r in rows_out),
                "deficit_equiv": sum(r["deficit_equiv"] for r in rows_out),
                "capacity_equiv": sum(x["capacity_equiv"] for x in cyc_out),
                "residual_equiv": sum(x["residual_equiv"] for x in cyc_out)}}

    preferred = ["North", "South", "West", "East"]
    site_order = [s for s in preferred if s in sites] + \
                 [s for s in sites if s not in preferred]
    segments = ["commercial", "public"]

    seg_docs = {}
    for seg in segments:
        qs = [q for q in requests if q["segment"] == seg]
        sites_out = []
        for s in site_order:
            sub = [q for q in qs if q["site"] == s]
            sites_out.append({"site": s,
                              "granted_equiv": sum(q["granted_equiv"] for q in sub),
                              "claim_equiv": sum(q["claim_equiv"] for q in sub),
                              "deficit_equiv": sum(q["deficit_equiv"] for q in sub),
                              "ledger_rows": len(sub)})
        cyc_out = []
        for c in cycle_names:
            sub = [q for q in qs if q["cycle"] == c]
            cyc_out.append({"cycle": c,
                            "granted_equiv": sum(q["granted_equiv"] for q in sub),
                            "claim_equiv": sum(q["claim_equiv"] for q in sub),
                            "deficit_equiv": sum(q["deficit_equiv"] for q in sub),
                            "ledger_rows": len(sub)})
        oc = {k: 0 for k in reasons["outcomes"]}
        rc = {}
        for q in qs:
            oc[q["outcome"]] += 1
            rc[q["reason"]] = rc.get(q["reason"], 0) + 1
        seg_docs[seg] = {
            "segment": seg, "as_of": as_of_s, "sites": sites_out, "cycles": cyc_out,
            "outcome_counts": oc, "reason_counts": rc,
            "totals": {"granted_equiv": sum(q["granted_equiv"] for q in qs),
                       "claim_equiv": sum(q["claim_equiv"] for q in qs),
                       "deficit_equiv": sum(q["deficit_equiv"] for q in qs),
                       "ledger_rows": len(qs),
                       "customers": len(set(q["ident"] for q in qs))}}

    sites_sum = []
    for s in site_order:
        t = region[s]["totals"]
        sites_sum.append({"site": s, "capacity_equiv": t["capacity_equiv"],
                          "granted_equiv": t["granted_equiv"],
                          "claim_equiv": t["claim_equiv"],
                          "deficit_equiv": t["deficit_equiv"],
                          "residual_equiv": t["residual_equiv"],
                          "ledger_rows": t["ledger_rows"]})
    segs_sum = [{"segment": seg,
                 "granted_equiv": seg_docs[seg]["totals"]["granted_equiv"],
                 "claim_equiv": seg_docs[seg]["totals"]["claim_equiv"],
                 "deficit_equiv": seg_docs[seg]["totals"]["deficit_equiv"],
                 "ledger_rows": seg_docs[seg]["totals"]["ledger_rows"]} for seg in segments]
    cyc_sum = []
    for c in cycle_names:
        sub = [q for q in requests if q["cycle"] == c]
        cyc_sum.append({"cycle": c,
                        "capacity_equiv": sum(capacity[(s, c)] for s in sites),
                        "granted_equiv": sum(q["granted_equiv"] for q in sub),
                        "claim_equiv": sum(q["claim_equiv"] for q in sub),
                        "deficit_equiv": sum(q["deficit_equiv"] for q in sub),
                        "residual_equiv": sum(cell_report[(s, c)]["residual_equiv"]
                                              for s in sites),
                        "ledger_rows": len(sub)})

    tot_granted = sum(q["granted_equiv"] for q in requests)
    tot_claim = sum(q["claim_equiv"] for q in requests)
    tot_def = sum(q["deficit_equiv"] for q in requests)
    tot_cap = sum(capacity[(s, c)] for s in sites for c in cycle_names)
    tot_res = sum(cell_report[(s, c)]["residual_equiv"] for s in sites for c in cycle_names)
    best = {"customer": "", "site": "", "value": 0}
    bkey = None
    for (ident, s), v in deficit_to_date.items():
        k = (-v, ident, s)
        if bkey is None or k < bkey:
            bkey, best = k, {"customer": ident, "site": s, "value": v}
    binding_cells = sum(1 for s in sites for c in cycle_names
                        if cell_report[(s, c)]["binding"])

    summary = {
        "as_of": as_of_s, "sites": sites_sum, "segments": segs_sum, "cycles": cyc_sum,
        "totals": {
            "ledger_rows": len(requests), "granted_equiv": tot_granted,
            "claim_equiv": tot_claim, "deficit_equiv": tot_def,
            "capacity_equiv": tot_cap, "residual_equiv": tot_res,
            "out_of_scope_rows": sum(len(v) for v in out_of_scope.values()),
            "customers_served": len(set(q["ident"] for q in requests)),
            "identity_checks": {
                "region_minus_segment_granted":
                    sum(region[s]["totals"]["granted_equiv"] for s in sites)
                    - sum(seg_docs[g]["totals"]["granted_equiv"] for g in segments),
                "capacity_minus_granted_minus_residual": tot_cap - tot_granted - tot_res,
                "claim_minus_granted_minus_deficit": tot_claim - tot_granted - tot_def},
            "spine": {"binding_cells": binding_cells,
                      "non_binding_cells": len(sites) * len(cycle_names) - binding_cells,
                      "largest_deficit_to_date": best}}}

    audit_doc = {k: tally[k] for k in [
        "floors_honoured_full", "floors_honoured_short", "floors_unmatched",
        "exceptions_applied", "exceptions_unendorsed", "exceptions_retracted",
        "illegal_transitions", "stale_events", "duplicate_version_events",
        "amendments_applied", "amendments_unendorsed", "amendments_early",
        "amendments_retracted", "amendment_chains_unresolvable", "no_qualified_node",
        "substitution_cycles", "resets", "lots_expired", "lots_cleared",
        "ceiling_binding", "ceiling_zero", "epoch_reassignments"]}
    audit_doc["substitution_hops"] = {str(h): tally["hops_%d" % h]
                                      for h in range(0, max_hops + 1)}
    audit_doc["cutover_sides"] = {"before": tally["cutover_before"],
                                  "from": tally["cutover_from"]}
    audit_doc["withheld"] = {"quantity_governed_before_cutover": withheld_qty,
                             "carry_forward_age": carry_age}

    src_codes = sorted(src_name)
    dq_doc = {
        "sources": {code: {"declared_rows": declared.get(code, 0),
                           "parsed_rows": parsed.get(code, 0),
                           "admitted_rows": admitted.get(code, 0)} for code in src_codes},
        "header_gaps": header_gaps,
        "null_forms": {"node_empty": dq["node_empty"],
                       "node_backslash_n": dq["node_backslash_n"],
                       "row_truncated": dq["row_truncated"]},
        "late_recorded": {code: C.late.get(code, 0) for code in src_codes},
        "duplicate_identical": dup_ident,
        "duplicate_conflicting": dup_conf,
        "cross_source_collapsed": cross_collapsed,
        "fold_disambiguated": clocks.fold_hits,
        "gap_shifted": clocks.gap_hits,
        "log_continuations": dq["log_continuations"],
        "unknown_customer_rows": dq["unknown_customer_rows"],
        "out_of_horizon_rows": dq["out_of_horizon_rows"],
        "lot_unit_rows": dq["lot_unit_rows"],
        "paren_negatives": dq["paren_negatives"],
        "restatement_gaps": dq["restatement_gaps"]}

    if write_files:
        os.makedirs(out_dir, exist_ok=True)

        def write(name, obj):
            with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
                json.dump(obj, fh, indent=1, sort_keys=True)

        for s in sites:
            write("region_%s.json" % s, region[s])
        for seg in segments:
            write("segment_%s.json" % seg, seg_docs[seg])
        write("summary.json", summary)
        write("policy_audit.json", audit_doc)
        write("data_quality.json", dq_doc)

    return {"requests": requests, "summary": summary, "audit": audit_doc, "dq": dq_doc,
            "cells": cell_report, "deficit_to_date": deficit_to_date,
            "remainder_units": remainder_units, "remainder_cells": remainder_cells,
            "capacity": capacity, "cycles": cycle_names, "sites": sites}


def apportion(claimers, cap_v):
    if not claimers:
        return 0, 0
    floors = [q["floor_equiv"] for q in claimers]
    claims = [q["claim_equiv"] for q in claimers]

    def total(L):
        return sum(max(f, c if c < L else L) for f, c in zip(floors, claims))

    maxc = max(claims)
    if total(maxc) <= cap_v:
        level = maxc
    else:
        lo, hi = 0, maxc
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if total(mid) <= cap_v:
                lo = mid
            else:
                hi = mid - 1
        level = lo
    for q in claimers:
        q["granted_equiv"] = max(q["floor_equiv"], min(q["claim_equiv"], level))
    left = cap_v - sum(q["granted_equiv"] for q in claimers)
    handed = 0
    while left > 0:
        unmet = [q for q in claimers if q["granted_equiv"] < q["claim_equiv"]]
        if not unmet:
            break
        unmet.sort(key=lambda q: (-(q["claim_equiv"] - q["granted_equiv"]), q["eff"],
                                  q["ident"], q["ref"]))
        for q in unmet:
            if left == 0:
                break
            q["granted_equiv"] += 1
            left -= 1
            handed += 1
    return level, handed


def apportion_pro_rata(claimers, cap_v):
    for q in claimers:
        q["granted_equiv"] = 0
    tot = sum(q["quantity_equiv"] for q in claimers)
    if not claimers or tot <= 0:
        return
    used = 0
    for q in claimers:
        share = min((cap_v * q["quantity_equiv"]) // tot, q["claim_equiv"])
        q["granted_equiv"] = share
        used += share
    left = cap_v - used
    if left > 0:
        cands = sorted((q for q in claimers if q["granted_equiv"] < q["claim_equiv"]),
                       key=lambda q: (-q["quantity_equiv"], q["ref"]))
        if cands:
            t = cands[0]
            t["granted_equiv"] += min(left, t["claim_equiv"] - t["granted_equiv"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    run(a.data, a.out)


if __name__ == "__main__":
    main()
