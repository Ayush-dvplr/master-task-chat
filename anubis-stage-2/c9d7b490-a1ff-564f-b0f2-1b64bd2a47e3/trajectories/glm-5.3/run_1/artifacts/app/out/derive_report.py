#!/usr/bin/env python3
"""Out-of-time backtest of the Halvard Equipment Finance champion lease scorecard.

Usage: python3 derive_report.py DATA_DIR OUT_DIR

Reads an extract laid out like the Halvard backtest extract (the documents
inside the extract state the rules) and writes the nine reports of
output_contract.md.  Every parameter comes from the extract; the servicing
conventions the rule documents leave to the evidence (the knowledge-time
boundary and the business day roll of each contract segment) are recovered
from snapshot_runs.log and invoice_notices.csv.
"""

import bisect
import calendar
import configparser
import datetime
import glob
import json
import os
import re
import sys
import tomllib
from collections import Counter, defaultdict
from fractions import Fraction

UTC = datetime.timezone.utc
EPOCH = datetime.datetime(1970, 1, 1, tzinfo=UTC)

ROLLS = ("following", "modified_following", "modified_preceding", "preceding")


def die(msg):
    sys.stderr.write("error: %s\n" % msg)
    raise SystemExit(1)


# ---------------------------------------------------------------- helpers ---

def parse_date(s):
    return datetime.date.fromisoformat(s.strip())


def parse_ts(s):
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def ikey(dt):
    return int((dt - EPOCH).total_seconds())


def ts_key(s):
    return ikey(parse_ts(s))


def add_months(y, m, day, n):
    m = m - 1 + n
    y2 = y + m // 12
    m2 = m % 12 + 1
    return datetime.date(y2, m2, min(day, calendar.monthrange(y2, m2)[1]))


def norm_code(s):
    return re.sub(r"[ \-_]", "", (s or "")).upper()


def canon_ref(s, prefix, width):
    if s is None:
        return None
    n = re.sub(r"[ \-_]", "", s).upper()
    tail = n[len(prefix):]
    if n.startswith(prefix) and tail and tail.isdigit():
        return "%s-%0*d" % (prefix, width, int(tail))
    return None


def lease_ref(s):
    return canon_ref(s, "HL", 6)


def obligor_ref(s):
    return canon_ref(s, "OB", 5)


def tax_digits(s):
    return re.sub(r"\D", "", s or "")


MONEY_RE = re.compile(r"^\d+\.\d{2}$")


def money_cents(s):
    """Dollars written with exactly two decimals -> positive cents, else None."""
    if s is None:
        return None
    t = s.strip()
    if not MONEY_RE.match(t):
        return None
    whole, frac = t.split(".")
    cents = int(whole) * 100 + int(frac)
    return cents if cents > 0 else None


def to_int(s, default=0):
    t = (s if s is not None else "").strip()
    return int(t) if t else default


def half_even_ppm(num, den):
    """Exact fraction num/den in parts per million, rounded half to even."""
    if den == 0:
        return None
    return round(Fraction(num * 1000000, den))


# ----------------------------------------------------------- mini parsers ---

def split_flow(inner):
    out, depth, cur = [], 0, ""
    for ch in inner:
        if ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def parse_scalar(tok):
    tok = tok.strip()
    if tok.startswith("[") and tok.endswith("]"):
        inner = tok[1:-1].strip()
        return [parse_scalar(p) for p in split_flow(inner)] if inner else []
    if tok.startswith("{") and tok.endswith("}"):
        res = {}
        inner = tok[1:-1].strip()
        if inner:
            for part in split_flow(inner):
                k, _, v = part.partition(":")
                res[k.strip()] = parse_scalar(v)
        return res
    if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "'\"":
        return tok[1:-1]
    if re.match(r"^-?\d+$", tok):
        return int(tok)
    if tok in ("null", "~", ""):
        return None
    return tok


def parse_simple_yaml(path):
    """Parse the small YAML subset used by the extract's reference files."""
    root = {}
    top = None
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.rstrip("\n")
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            if indent == 0:
                if stripped.endswith(":"):
                    top = stripped[:-1]
                    root[top] = None
                else:
                    k, _, v = stripped.partition(":")
                    root[k.strip()] = parse_scalar(v)
                    top = None
                continue
            if top is None:
                continue
            if root[top] is None:
                root[top] = [] if stripped.startswith("- ") else {}
            cont = root[top]
            if stripped.startswith("- "):
                cont.append(parse_scalar(stripped[2:]) if not _bare_kv(stripped[2:])
                           else _bare_kv(stripped[2:]))
            elif isinstance(cont, list):
                if not cont or not isinstance(cont[-1], dict):
                    cont.append({})
                k, _, v = stripped.partition(":")
                cont[-1][k.strip()] = parse_scalar(v)
            elif isinstance(cont, dict):
                k, _, v = stripped.partition(":")
                cont[k.strip()] = parse_scalar(v)
    return root


def _bare_kv(text):
    m = re.match(r"^([A-Za-z_][\w ]*?):\s*(.*)$", text)
    if not m:
        return None
    return {m.group(1): parse_scalar(m.group(2))}


def parse_ics(path):
    spans = []
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    for block in text.split("BEGIN:VEVENT")[1:]:
        block = block.split("END:VEVENT")[0]
        fields = {}
        for line in block.splitlines():
            line = line.strip()
            if not line or ":" not in line:
                continue
            name, _, value = line.partition(":")
            fields[name.split(";")[0].upper()] = value.strip()
        if "DTSTART" not in fields or "DTEND" not in fields:
            continue
        ds, de = fields["DTSTART"], fields["DTEND"]
        try:
            d0 = datetime.date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))
            d1 = datetime.date(int(de[:4]), int(de[4:6]), int(de[6:8]))
        except ValueError:
            continue
        cats = [c.strip() for c in fields.get("CATEGORIES", "").split(",") if c.strip()]
        spans.append((cats, d0, d1, fields.get("STATUS", "").upper()))
    return spans


def read_ini(path):
    cp = configparser.ConfigParser()
    cp.optionxform = str
    cp.read(path)
    return cp


# --------------------------------------------------------------- calendar ---

class Clock:
    """The regional clock of an extract region."""

    def __init__(self, section):
        self.standard = int(section["standard_offset"])
        self.daylight = int(section["daylight_offset"])
        self.periods = []
        raw = (section.get("daylight_periods") or "").strip()
        if raw:
            for span in raw.split(","):
                span = span.strip()
                if not span:
                    continue
                a, _, b = span.partition("/")
                self.periods.append((ts_key(a), ts_key(b)))

    def offset_at(self, t):
        for a, b in self.periods:
            if a <= t < b:
                return self.daylight
        return self.standard

    def local_to_utc(self, day, hh, mm, ss):
        base = datetime.datetime(day.year, day.month, day.day, hh, mm, ss, tzinfo=UTC)
        for off in {self.standard, self.daylight}:
            t = ikey(base) - off * 60
            if self.offset_at(t) == off:
                return t
        return ikey(base) - self.standard * 60

    def local_date(self, t):
        loc = EPOCH + datetime.timedelta(seconds=t + self.offset_at(t) * 60)
        return loc.date()


# ------------------------------------------------------------- the extract ---

class Extract:
    """Reads an extract; drops late records and counts duplicates."""

    def __init__(self, data_dir, watermark_key):
        self.dir = data_dir
        self.wm = watermark_key
        self.late = Counter()
        self._seen = {}

    def path(self, name):
        return os.path.join(self.dir, name)

    def require(self, name):
        p = self.path(name)
        if not os.path.isfile(p):
            die("missing required input file: %s" % name)
        return p

    def lines(self, name):
        with open(self.require(name), "r", encoding="utf-8") as fh:
            return [l.rstrip("\n") for l in fh]

    def csv(self, name, time_field=None, drop_late=True):
        lines = self.lines(name)
        header = lines[0].split(",") if lines else []
        body = [l for l in lines[1:] if l.strip()]
        rows, kept = [], []
        nlate = 0
        for l in body:
            vals = l.split(",")
            row = dict(zip(header, vals))
            if time_field is not None and ts_key(row[time_field]) > self.wm:
                nlate += 1
                continue
            row["\x00line"] = l
            rows.append(row)
            kept.append(l)
        if drop_late:
            self.late[name] = nlate
        self._dups(name, kept)
        return header, rows

    def jsonl(self, name, time_field, drop_late=True):
        body = [l for l in self.lines(name) if l.strip()]
        rows, kept, nlate = [], [], 0
        for l in body:
            row = json.loads(l)
            if ts_key(row[time_field]) > self.wm:
                nlate += 1
                continue
            row["\x00line"] = l
            rows.append(row)
            kept.append(l)
        if drop_late:
            self.late[name] = nlate
        self._dups(name, kept)
        return rows

    def counted_lines(self, name, is_late=None):
        """For line oriented files whose lines are not parsed as records."""
        body = [l for l in self.lines(name) if l.strip()]
        kept, nlate = [], 0
        for l in body:
            late = bool(is_late and is_late(l))
            if late:
                nlate += 1
                continue
            kept.append(l)
        if is_late:
            self.late[name] = nlate
        self._dups(name, kept)
        return kept

    def _dups(self, name, kept):
        seen = self._seen.setdefault(name, Counter())
        for l in kept:
            seen[l] += 1

    def duplicates(self):
        out = {}
        for name, seen in self._seen.items():
            n = sum(v - 1 for v in seen.values() if v > 1)
            if n:
                out[name] = n
        return out


# ------------------------------------------------------------------ model ---

class Model:
    def __init__(self, data_dir):
        self.dir = data_dir

    # -- configuration -----------------------------------------------------

    def load_config(self):
        d = self.dir
        p = os.path.join(d, "backtest_run.toml")
        if not os.path.isfile(p):
            die("missing required input file: backtest_run.toml")
        with open(p, "rb") as fh:
            run = tomllib.load(fh)["run"]
        self.run_id = run["run_id"]
        self.first_snapshot = parse_date(run["first_snapshot"])
        self.snapshot_count = int(run["snapshot_count"])
        self.step_months = int(run["snapshot_step_months"])
        self.performance_days = int(run["performance_days"])
        self.bad_dpd = int(run["bad_dpd"])
        self.data_cutoff = parse_date(run["data_cutoff"])
        self.watermark_raw = ts_key(run["watermark_utc"])
        self.watermark_dt = parse_ts(run["watermark_utc"])
        self.cut_local_time = run["cut_local_time"]
        self.notices_through = parse_date(run["notices_through"])
        h, m, s = (to_int(x) for x in self.cut_local_time.split(":"))
        self.cut_hms = (h, m, s)

        cp = read_ini(self._req("region_clock.ini"))
        self.regions = []
        self.clocks = {}
        for sec in cp.sections():
            self.clocks[sec] = Clock(cp[sec])
        # regions come from branches.ini; clocks must exist for each
        br = read_ini(self._req("branches.ini"))
        self.branch_region = {}
        for code, reg in br["branches"].items():
            self.branch_region[norm_code(code)] = reg
        self.alias = {}
        for a, code in br["aliases"].items():
            self.alias[norm_code(a)] = norm_code(code)
        self.regions = []
        for reg in self.branch_region.values():
            if reg not in self.regions:
                self.regions.append(reg)
        for reg in self.regions:
            rl = reg.lower()
            clock = None
            for sec, clock in self.clocks.items():
                if sec.lower() == rl:
                    clock = self.clocks[sec]
                    break
            if clock is None:
                die("region_clock.ini has no clock for region %s" % reg)
            self.clocks[reg] = clock

        pol = read_ini(self._req("servicing_policy.ini"))
        self.tolerance = {
            "commercial": int(pol["tolerance"]["commercial_cents"]),
            "public": int(pol["tolerance"]["public_cents"]),
        }
        self.surcharge_cents = int(pol["card"]["surcharge_cents"])
        self.max_holidays = int(pol["relief"]["max_holidays_per_lease"])

        rc = read_ini(self._req("return_codes.ini"))
        self.reverse_code = {}
        for code, yes in rc["codes"].items():
            self.reverse_code[norm_code(code)] = (str(yes).strip().lower() == "yes")

        bv = read_ini(self._req("bureau_vendors.ini"))
        self.max_age_days = int(bv["general"]["max_age_days"])
        self.precedence = {}
        for seg, lst in bv["precedence"].items():
            self.precedence[seg] = [v.strip() for v in lst.split(",") if v.strip()]
        self.nd_num = int(bv["ND"]["to_kr_numerator"])
        self.nd_den = int(bv["ND"]["to_kr_denominator"])

        self.sectors = json.load(open(self._req("sector_reference.json"), encoding="utf-8"))["sectors"]

        lin = parse_simple_yaml(self._req("feature_lineage.yaml"))
        self.lineage_nodes = {k: list(v or []) for k, v in (lin.get("nodes") or {}).items()}
        self.lineage_chars = {k: list(v or []) for k, v in (lin.get("characteristics") or {}).items()}

        self.incidents = json.load(open(self._req("data_incidents.json"), encoding="utf-8"))["incidents"]

        ex = parse_simple_yaml(self._req("exclusion_policy.yaml"))
        self.exclusion_reasons = [e["reason"] for e in (ex.get("exclusions") or [])]

        bands = parse_simple_yaml(self._req("score_bands.yaml"))
        self.bands = [(b["band"], b["lo"], b["hi"]) for b in (bands.get("bands") or [])]

        reg = json.load(open(self._req("scorecard_registry.json"), encoding="utf-8"))
        self.registry = reg["versions"]
        self.scorecards = {}
        for entry in self.registry:
            path = self._req(entry["file"])
            self.scorecards[entry["version"]] = json.load(open(path, encoding="utf-8"))

        self.holidays = {}
        for cats, d0, d1, status in parse_ics(self._req("holiday_calendar.ics")):
            if status != "CONFIRMED":
                continue
            span = [d0 + datetime.timedelta(days=i) for i in range((d1 - d0).days)]
            for cat in cats:
                for reg_name in self.regions:
                    if cat.upper() == reg_name.upper():
                        self.holidays.setdefault(reg_name, set()).update(span)

    def _req(self, name):
        p = os.path.join(self.dir, name)
        if not os.path.isfile(p):
            die("missing required input file: %s" % name)
        return p

    def region_of_branch(self, code):
        c = self.alias.get(norm_code(code), norm_code(code))
        return self.branch_region.get(c)

    def is_business_day(self, day, region):
        return day.weekday() < 5 and day not in self.holidays.get(region, ())

    def roll(self, day, region, conv):
        if self.is_business_day(day, region):
            return day
        if conv in ("following", "modified_following"):
            d = day
            while not self.is_business_day(d, region):
                d += datetime.timedelta(days=1)
            if conv == "modified_following" and (d.year, d.month) != (day.year, day.month):
                d = day
                while not self.is_business_day(d, region):
                    d -= datetime.timedelta(days=1)
            return d
        d = day
        while not self.is_business_day(d, region):
            d -= datetime.timedelta(days=1)
        if conv == "modified_preceding" and (d.year, d.month) != (day.year, day.month):
            d = day
            while not self.is_business_day(d, region):
                d += datetime.timedelta(days=1)
        return d

    def cut_instant(self, region, day):
        h, m, s = self.cut_hms
        return self.clocks[region].local_to_utc(day, h, m, s)

    # -- identity ----------------------------------------------------------

    def load_identity(self, ex):
        header, rows = ex.csv("leases.csv")
        self.leases = {}
        for r in rows:
            lid = r["lease_id"]
            if lid in self.leases:
                continue
            self.leases[lid] = {
                "obligor": obligor_ref(r["obligor_ref"]),
                "start": parse_date(r["start_date"]),
                "term": to_int(r["term_months"]),
                "inst": money_cents(r["instalment"]) or 0,
                "anchor": to_int(r["anchor_day"]),
                "product": r["product"],
            }
        self.lease_ids = sorted(self.leases)

        # branch history
        _, rows = ex.csv("lease_branch_history.csv", "recorded_at")
        bh = defaultdict(list)
        for r in rows:
            lid = lease_ref(r["lease_ref"])
            reg = self.region_of_branch(r["branch_code"])
            if reg is None:
                continue
            bh[lid].append((r["effective_from"], r["recorded_at"], r["row_id"], reg))
        self.branch_rows = {}
        for lid, lst in bh.items():
            lst.sort(key=lambda t: (parse_date(t[0]), ts_key(t[1]), t[2]))
            self.branch_rows[lid] = lst
        self.booking_region = {}
        for lid, lst in self.branch_rows.items():
            self.booking_region[lid] = lst[0][3]

        # obligors
        _, rows = ex.csv("obligors.csv", "created_at")
        self.obligors = {}
        for r in rows:
            oid = r["obligor_id"]
            if oid in self.obligors:
                continue
            self.obligors[oid] = {"created": ts_key(r["created_at"]), "tax": tax_digits(r["tax_id"])}

        events = ex.jsonl("obligor_events.jsonl", "recorded_at")
        self.ob_events = defaultdict(list)
        for e in events:
            oid = obligor_ref(e["obligor_ref"])
            if oid is None:
                continue
            self.ob_events[oid].append(e)
        for oid in self.ob_events:
            self.ob_events[oid].sort(key=lambda e: (ts_key(e["recorded_at"]), e["event_seq"]))

        _, rows = ex.csv("public_entity_register.csv")
        self.public = defaultdict(list)
        for r in rows:
            self.public[tax_digits(r["fein"])].append(
                (parse_date(r["listed_on"]), parse_date(r["delisted_on"]) if r["delisted_on"].strip() else None))

    # -- tax ids, sectors, merges ------------------------------------------

    def tax_id_at(self, oid, t):
        best = None
        for e in self.ob_events.get(oid, ()):
            if e["type"] != "TAXID_CORRECTION" or ts_key(e["recorded_at"]) > t:
                continue
            key = (ts_key(e["recorded_at"]), e["event_seq"])
            if best is None or key > best[0]:
                best = (key, tax_digits(e["tax_id"]))
        if best:
            return best[1]
        ob = self.obligors.get(oid)
        return ob["tax"] if ob else ""

    def obligor_known(self, oid, t):
        ob = self.obligors.get(oid)
        return ob is not None and ob["created"] <= t

    def sector_at(self, oid, day, t):
        best = None
        for e in self.ob_events.get(oid, ()):
            if e["type"] not in ("SECTOR_SET", "SECTOR_CHANGE"):
                continue
            if ts_key(e["recorded_at"]) > t or parse_date(e["effective_date"]) > day:
                continue
            key = (parse_date(e["effective_date"]), ts_key(e["recorded_at"]), e["event_seq"])
            if best is None or key > best[0]:
                best = (key, str(e["sector_code"]))
        return best[1] if best else None

    def merge_step(self, oid, day, t):
        best = None
        for e in self.ob_events.get(oid, ()):
            if e["type"] != "MERGE":
                continue
            if ts_key(e["recorded_at"]) > t or parse_date(e["effective_date"]) > day:
                continue
            key = (parse_date(e["effective_date"]), ts_key(e["recorded_at"]), e["event_seq"])
            if best is None or key > best[0]:
                best = (key, obligor_ref(e["into"]))
        return best[1] if best else None

    def surviving(self, oid, day, t):
        seen = set()
        cur = oid
        while cur is not None and cur not in seen and len(seen) < 32:
            seen.add(cur)
            nxt = self.merge_step(cur, day, t)
            if nxt is None:
                return cur
            cur = nxt
        return cur

    def is_public(self, tax, day):
        for listed, delisted in self.public.get(tax, ()):
            if listed <= day and (delisted is None or delisted > day):
                return True
        return False

    def contract_segment(self, lid):
        seg = self._contract_seg.get(lid)
        if seg is not None:
            return seg
        lease = self.leases[lid]
        seg = "commercial"
        if lease["obligor"] is not None:
            tax = self.tax_id_at(lease["obligor"], self.watermark)
            if tax and self.is_public(tax, lease["start"]):
                seg = "public"
        self._contract_seg[lid] = seg
        return seg

    # -- lifecycle ---------------------------------------------------------

    def load_lifecycle(self, ex, events):
        by_event = {}
        self.event_rejects = []
        for e in events:
            eid = e["event_id"]
            lid = lease_ref(e["lease_ref"])
            if lid is None or lid not in self.leases:
                self.event_rejects.append(("lease_events.jsonl", eid, "unknown_lease"))
                continue
            cur = by_event.get(eid)
            if cur is None or (int(e["version"]), ts_key(e["recorded_at"]), e["\x00line"]) > \
                    (int(cur["version"]), ts_key(cur["recorded_at"]), cur["\x00line"]):
                by_event[eid] = e
        self.le_events = defaultdict(list)
        for eid, e in by_event.items():
            if e["type"] == "VOID":
                continue
            lid = lease_ref(e["lease_ref"])
            self.le_events[lid].append((parse_date(e["effective_date"]), eid, e["type"]))
        for lid in self.le_events:
            self.le_events[lid].sort()

        invalid = set()
        for lid in sorted(self.le_events):
            state = "pending"
            for _, eid, typ in self.le_events[lid]:
                if state == "pending" and typ == "ACTIVATE":
                    state = "active"
                elif state == "active" and typ in ("BUYOUT", "PAYOFF"):
                    state = "closed"
                elif state == "active" and typ == "CHARGE_OFF":
                    state = "charged_off"
                else:
                    invalid.add(eid)
        for eid in sorted(invalid):
            self.event_rejects.append(("lease_events.jsonl", eid, "invalid_transition"))

        _, rows = ex.csv("relief_approvals.csv", "status_at")
        self.relief_rejects = []
        by_req = defaultdict(list)
        for r in rows:
            lid = lease_ref(r["lease_ref"])
            if lid is None or lid not in self.leases:
                self.relief_rejects.append(("relief_approvals.csv", r["status_id"], "unknown_lease"))
                continue
            by_req[r["request_id"]].append(r)
        self.requests = {}
        for rid, lst in by_req.items():
            lst.sort(key=lambda r: (ts_key(r["status_at"]), r["status_id"]))
            valid = []
            state = None
            for r in lst:
                st = r["status"]
                ok = (state is None and st == "REQUESTED") or \
                     (state == "REQUESTED" and st in ("APPROVED", "DECLINED")) or \
                     (state == "APPROVED" and st == "WITHDRAWN")
                if not ok:
                    self.relief_rejects.append(
                        ("relief_approvals.csv", r["status_id"], "invalid_transition"))
                    continue
                state = st
                valid.append(r)
            self.requests[rid] = {
                "lease": lease_ref(lst[0]["lease_ref"]),
                "rows": lst,
                "valid": valid,
                "months": to_int(lst[0]["months"]),
                "fdi": to_int(lst[0]["first_deferred_instalment"]),
            }
        self.relief_by_lease = defaultdict(list)
        for rid in sorted(self.requests):
            self.relief_by_lease[self.requests[rid]["lease"]].append(rid)

        _, rows = ex.csv("invoice_notices.csv")
        notices = []
        invoice_lease = {}
        for r in rows:
            lid = lease_ref(r["lease_id"])
            if lid is not None:
                invoice_lease.setdefault(r["invoice_no"], lid)
            if lid is None or lid not in self.leases:
                continue
            notices.append((lid, to_int(r["instalment_no"]),
                            parse_date(r["printed_due_date"]), parse_date(r["issued_on"])))
        return notices, invoice_lease

    def governing_holidays(self, lid, t):
        """Request ids of the holidays in force for a lease at an instant."""
        in_force = []
        for rid in self.relief_by_lease.get(lid, ()):
            valid = self.requests[rid]["valid"]
            if not valid:
                continue
            last = valid[0]
            for r in valid:
                if ts_key(r["status_at"]) <= t:
                    last = r
                else:
                    break
            if last["status"] == "APPROVED" and ts_key(last["status_at"]) <= t:
                in_force.append((ts_key(last["status_at"]), rid))
        in_force.sort()
        return [rid for _, rid in in_force[:self.max_holidays]]

    def holiday_limits(self):
        """Requests rejected at the watermark for exceeding the holiday limit."""
        out = []
        for lid, rids in self.relief_by_lease.items():
            in_force = []
            for rid in rids:
                valid = self.requests[rid]["valid"]
                if not valid:
                    continue
                last = valid[0]
                for r in valid:
                    if ts_key(r["status_at"]) <= self.watermark:
                        last = r
                    else:
                        break
                if last["status"] == "APPROVED":
                    in_force.append((ts_key(last["status_at"]), rid))
            in_force.sort()
            for _, rid in in_force[self.max_holidays:]:
                out.append(("relief_approvals.csv", rid, "holiday_limit"))
        return out

    def events_at(self, lid, t):
        """Governing non-VOID events of a lease, as known at t."""
        key = (lid, t)
        got = self._events_cache.get(key)
        if got is not None:
            return got
        versions = self._event_versions.get(lid, {})
        eff = []
        for eid, lst in versions.items():
            gov = None
            for e in lst:
                if ts_key(e["recorded_at"]) <= t:
                    if gov is None or (int(e["version"]), ts_key(e["recorded_at"]), e["\x00line"]) > \
                            (int(gov["version"]), ts_key(gov["recorded_at"]), gov["\x00line"]):
                        gov = e
                else:
                    break
            if gov is None or gov["type"] == "VOID":
                continue
            eff.append((parse_date(gov["effective_date"]), eid, gov["type"]))
        eff.sort()
        self._events_cache[key] = eff
        return eff

    def state_at(self, lid, day, t):
        """State of a lease on a date as known at t."""
        eff = self.events_at(lid, t)
        state = "pending"
        for eff_date, _, typ in eff:
            if eff_date > day:
                break
            if state == "pending" and typ == "ACTIVATE":
                state = "active"
            elif state == "active" and typ in ("BUYOUT", "PAYOFF"):
                state = "closed"
            elif state == "active" and typ == "CHARGE_OFF":
                state = "charged_off"
        return state

    def branch_at(self, lid, day, t):
        """Region of the lease's branch on a date, as known at t."""
        rows = [r for r in self.branch_rows.get(lid, ()) if ts_key(r[1]) <= t]
        best = None
        for r in rows:
            if parse_date(r[0]) > day:
                continue
            key = (parse_date(r[0]), ts_key(r[1]), r[2])
            if best is None or key > best[0]:
                best = (key, r[3])
        return best[1] if best else None

    # -- schedule ----------------------------------------------------------

    def schedule(self, lid, holidays):
        """Due dates of the instalments of a lease under the given holidays."""
        key = (lid, holidays)
        got = self._sched_cache.get(key)
        if got is not None:
            return got
        lease = self.leases[lid]
        region = self.booking_region.get(lid)
        conv = self.roll_conv[self.contract_segment(lid)]
        n = lease["term"]
        anchor = lease["anchor"]
        sy, sm = lease["start"].year, lease["start"].month
        dues = []
        for k in range(1, n + 1):
            shift = 0
            for fdi, months in holidays:
                if k >= fdi:
                    shift += months
            if self.anchor_variant == "anchor":
                nom = add_months(sy, sm + k, anchor, shift) if shift else \
                    add_months(sy, sm + k, anchor, 0)
            else:
                nom = add_months(sy, sm + k, anchor, 0)
                if shift:
                    nom = add_months(nom.year, nom.month, nom.day, shift)
            due = self.roll(nom, region, conv) if region else nom
            dues.append(due.toordinal())
        self._sched_cache[key] = dues
        return dues

    def holiday_state(self, lid, t):
        """Governing (fdi, months) tuples in force for a lease at t."""
        rids = self.governing_holidays(lid, t)
        return tuple(sorted((self.requests[r]["fdi"], self.requests[r]["months"]) for r in rids))

    # -- cash ---------------------------------------------------------------

    def resolve_ref(self, ref):
        lid = lease_ref(ref)
        if lid is None:
            lid = self.invoice_lease.get(ref)
        if lid is not None and lid not in self.leases:
            return None
        return lid

    def load_cash(self, ex, invoice_lease):
        self.invoice_lease = invoice_lease

        self.cash_rejects = []
        self.line_index = defaultdict(list)
        self.posting_index = defaultdict(list)
        self.posting_by_id = defaultdict(list)

        lb_files = sorted(glob.glob(os.path.join(self.dir, "lockbox_*.csv")))
        for region in self.regions:
            want = os.path.join(self.dir, "lockbox_%s.csv" % region.lower())
            if want not in lb_files:
                die("missing required input file: lockbox_%s.csv" % region.lower())
        self.lockbox_files = []
        for path in lb_files:
            name = os.path.basename(path)
            self.lockbox_files.append(name)
            _, rows = ex.csv(name, "received_at")
            for r in rows:
                pid = norm_code(r["item_id"])
                lease = self.resolve_ref(r["remit_ref"])
                if lease is None:
                    self.cash_rejects.append((name, r["item_id"], "unknown_lease"))
                    continue
                amount = money_cents(r["amount"])
                if amount is None:
                    self.cash_rejects.append((name, r["item_id"], "bad_amount"))
                    continue
                self.line_index[("lockbox", pid)].append({
                    "at": ts_key(r["received_at"]), "lease": lease,
                    "value": parse_date(r["value_date"]), "amount": amount,
                    "line": r["\x00line"],
                })

        _, rows = ex.csv("card_settlements.csv", "batch_at")
        for r in rows:
            pid = norm_code(r["auth_code"])
            lease = self.resolve_ref(r["lease_ref"])
            if lease is None:
                self.cash_rejects.append(("card_settlements.csv", r["auth_code"], "unknown_lease"))
                continue
            amount = money_cents(r["amount"])
            if amount is None:
                self.cash_rejects.append(("card_settlements.csv", r["auth_code"], "bad_amount"))
                continue
            self.line_index[("card", pid)].append({
                "at": ts_key(r["batch_at"]), "lease": lease,
                "value": parse_date(r["settlement_date"]), "amount": amount,
                "line": r["\x00line"],
            })

        names = sorted(glob.glob(os.path.join(self.dir, "servicing_ledger_*.jsonl")))
        if not names:
            die("missing required input file: servicing_ledger_*.jsonl")
        by_name = {os.path.basename(n): n for n in names}
        first_year = min(l["start"].year for l in self.leases.values()) if self.leases else None
        for year in range(first_year, self.data_cutoff.year + 1):
            if "servicing_ledger_%d.jsonl" % year not in by_name:
                die("missing required input file: servicing_ledger_%d.jsonl" % year)
        for name in sorted(by_name):
            rows = ex.jsonl(name, "posted_at")
            for r in rows:
                lid = lease_ref(r["lease_id"])
                if lid is not None and lid not in self.leases:
                    lid = None
                ch = r["channel"].upper()
                if ch == "ACH":
                    key = ("ach", norm_code(r["posting_id"]))
                elif ch == "LOCKBOX":
                    key = ("lockbox", norm_code(r["source_ref"]))
                elif ch == "CARD":
                    key = ("card", norm_code(r["source_ref"]))
                else:
                    continue
                post = {
                    "at": ts_key(r["posted_at"]), "lease": lid, "amount": int(r["amount"]),
                    "id": r["posting_id"], "line": r["\x00line"],
                }
                self.posting_index[key].append(post)
                self.posting_by_id[r["posting_id"]].append(post)
        for key in self.posting_index:
            self.posting_index[key].sort(key=lambda p: (p["at"], p["id"]))
        for key in self.line_index:
            self.line_index[key].sort(key=lambda l: (l["at"], l["line"]))

        raw = ex.counted_lines("ach_returns.log", is_late=self._log_line_is_late)
        self.returns = []
        for l in raw:
            s = l.strip()
            if not s or s.startswith("#"):
                continue
            m = re.match(r"^(\S+)\s+RETURN\s+id=(\S+)\s+posting=(\S+)\s+code=(\S+)", s)
            if not m:
                continue
            self.returns.append({
                "at": ts_key(m.group(1)), "id": m.group(2),
                "posting": m.group(3), "code": norm_code(m.group(4)),
            })
        self.return_rejects = []
        for r in self.returns:
            posts = self.posting_by_id.get(r["posting"])
            if not posts:
                self.return_rejects.append(("ach_returns.log", r["id"], "unknown_posting"))
                r["reverses"] = False
                continue
            r["reverses"] = self.reverse_code.get(r["code"], False)

        self.payments = sorted(set(self.line_index) | set(self.posting_index))
        self._return_by_posting = defaultdict(list)
        for r in self.returns:
            self._return_by_posting[r["posting"]].append(r)
        self._pay_segments = {}
        self._pay_keys = {}
        for key in self.payments:
            self._pay_segments[key] = self._build_payment(key)
        self._lease_pay = defaultdict(list)
        for key, segs in self._pay_segments.items():
            for _, state in segs:
                if state is not None:
                    if key not in self._lease_pay[state[0]]:
                        self._lease_pay[state[0]].append(key)
        for lid in self._lease_pay:
            self._lease_pay[lid].sort()

    def _log_line_is_late(self, line):
        s = line.strip()
        if not s or s.startswith("#"):
            return False
        try:
            return ts_key(s.split(" ")[0]) > self.watermark
        except Exception:
            return False

    def _build_payment(self, key):
        lines = self.line_index.get(key, ())
        posts = self.posting_index.get(key, ())
        times = {l["at"] for l in lines} | {p["at"] for p in posts}
        for p in posts:
            for r in self._return_by_posting.get(p["id"], ()):
                times.add(r["at"])
        segs = []
        for t in sorted(times):
            segs.append((t, self._payment_at(key, lines, posts, t)))
        return segs

    def _payment_at(self, key, lines, posts, t):
        line = None
        for l in lines:
            if l["at"] <= t:
                line = l
            else:
                break
        post = None
        for p in posts:
            if p["at"] <= t:
                post = p
            else:
                break
        if post is not None:
            reversed_now = any(r["at"] <= t and r["reverses"]
                              for r in self._return_by_posting.get(post["id"], ()))
        else:
            reversed_now = False
        if post is not None:
            lease = post["lease"]
        elif line is not None:
            lease = line["lease"]
        else:
            return None
        if lease is None:
            return None
        region = self.booking_region.get(lease)
        post_value = self.clocks[region].local_date(post["at"]) \
            if (post is not None and region is not None) else None
        if key[0] == "lockbox":
            if line is not None:
                value, amount = line["value"], line["amount"]
            elif post_value is not None:
                value, amount = post_value, post["amount"]
            else:
                return None
        elif key[0] == "card":
            value = line["value"] if line is not None else post_value
            amount = post["amount"] if post is not None else None
            if value is None:
                return None
        else:
            if post is None or post_value is None:
                return None
            value, amount = post_value, post["amount"]
        if reversed_now:
            return None
        return (lease, value.toordinal(), amount)

    def payment_state(self, key, t):
        segs = self._pay_segments.get(key)
        if not segs:
            return None
        keys = self._pay_keys.get(key)
        if keys is None:
            keys = [s[0] for s in segs]
            self._pay_keys[key] = keys
        i = bisect.bisect_right(keys, t)
        if i == 0:
            return None
        return segs[i - 1][1]

    def cash_at(self, lid, t):
        """(value dates, cumulative cents) of the payments of a lease at t."""
        key = (lid, t)
        got = self._cash_cache.get(key)
        if got is not None:
            return got
        amounts = defaultdict(int)
        for pkey in self._lease_pay.get(lid, ()):
            state = self.payment_state(pkey, t)
            if state is None or state[0] != lid or state[2] is None:
                continue
            amounts[state[1]] += state[2]
        if not amounts:
            self._cash_cache[key] = None
            return None
        vdates = sorted(amounts)
        cums = []
        total = 0
        for v in vdates:
            total += amounts[v]
            cums.append(total)
        res = (vdates, cums)
        self._cash_cache[key] = res
        return res

    # -- bureau -------------------------------------------------------------

    def load_bureau(self, ex):
        rows = ex.jsonl("bureau_kr.jsonl", "recorded_at")
        self.kr = defaultdict(list)
        for r in rows:
            self.kr[tax_digits(r["tax_id"])].append({
                "vendor": "KR", "id": r["pull_id"], "day": parse_date(r["pulled_on"]),
                "at": ts_key(r["recorded_at"]), "status": r["status"], "score": r["score"],
            })
        _, rows = ex.csv("bureau_nd.csv", "loaded_at")
        self.nd = defaultdict(list)
        for r in rows:
            self.nd[tax_digits(r["fein"])].append({
                "vendor": "ND", "id": r["pull_ref"], "day": parse_date(r["pull_date"]),
                "at": ts_key(r["loaded_at"]), "status": r["result"], "score": r["score"],
            })
        for index in (self.kr, self.nd):
            for tax in index:
                index[tax].sort(key=lambda p: (p["day"], p["at"], p["id"]))
        disputes = json.load(open(self._req("bureau_disputes.json"), encoding="utf-8"))["disputes"]
        self.disputes = defaultdict(list)
        for d in disputes:
            if ts_key(d["recorded_at"]) > self.watermark:
                ex.late["bureau_disputes.json"] += 1
                continue
            self.disputes[(d["vendor"], d["pull_id"])].append(ts_key(d["recorded_at"]))
        _, rows = ex.csv("credit_limits.csv", "recorded_at")
        self.limits = defaultdict(list)
        for r in rows:
            oid = obligor_ref(r["obligor_ref"])
            if oid is None:
                continue
            self.limits[oid].append((parse_date(r["effective_from"]), ts_key(r["recorded_at"]),
                                     r["limit_id"], r["limit_k"]))

    def bureau_at(self, tax, day, t, segment):
        """(kind, value) of the bureau characteristic, or None when no candidate."""
        if not tax:
            return None
        prec = self.precedence.get(segment, [])
        best = None
        for vendor, index in (("KR", self.kr), ("ND", self.nd)):
            for pull in index.get(tax, ()):
                if pull["day"] > day or (day - pull["day"]).days > self.max_age_days:
                    continue
                if pull["at"] > t:
                    continue
                disputed = False
                for at in self.disputes.get((vendor, pull["id"]), ()):
                    if at <= t:
                        disputed = True
                        break
                if disputed:
                    continue
                rank = prec.index(vendor) if vendor in prec else len(prec)
                key = (pull["day"], rank, pull["at"], pull["id"])
                if best is None or key > best[0]:
                    best = (key, pull)
        if best is None:
            return None
        pull = best[1]
        if pull["vendor"] == "KR":
            st = pull["status"]
            if st == "OK":
                return ("score", int(pull["score"]))
            if st == "NOHIT":
                return ("no_hit", None)
            if st == "THIN":
                return ("thin", None)
            return None
        st = pull["status"]
        if st == "NOHIT":
            return ("no_hit", None)
        if pull["score"] is None or str(pull["score"]).strip() == "":
            return ("thin", None)
        tenths = round(float(pull["score"]) * 10)
        return ("score", 300 + (tenths * self.nd_num) // self.nd_den)

    def limit_at(self, oid, day, t):
        best = None
        for eff, at, lid, limit_k in self.limits.get(oid, ()):
            if at > t or eff > day:
                continue
            if limit_k is None or str(limit_k).strip() == "":
                continue
            key = (eff, at, lid)
            if best is None or key > best[0]:
                best = (key, limit_k)
        return None if best is None else to_int(best[1])

    # -- quarantine ---------------------------------------------------------

    def load_incidents(self, ex):
        self.incident_list = []
        for inc in self.incidents:
            if str(inc.get("status", "")).lower() != "confirmed":
                continue
            self.incident_list.append({
                "source": inc["source"],
                "regions": {str(r).upper() for r in inc.get("regions", [])},
                "from": ts_key(inc["from_utc"]),
                "to": ts_key(inc["to_utc"]),
                "declared": ts_key(inc["declared_at"]),
            })
        self.incident_list = [i for i in self.incident_list if i["declared"] <= self.watermark]

    def char_closure(self):
        """characteristic -> the nodes it is computed from, itself included."""
        out = {}

        def close(name):
            if name in out:
                return out[name]
            out[name] = {name}
            for dep in self.lineage_nodes.get(name, ()):
                out[name] |= close(dep)
            return out[name]

        chars = {}
        for ch, deps in self.lineage_chars.items():
            nodes = set()
            for dep in deps:
                nodes |= close(dep)
            chars[ch] = nodes
        return chars

    def quarantined_sources(self, region, t):
        """Sources quarantined for an observation of a region with knowledge instant t."""
        regs = {region.upper()}
        out = set()
        for inc in self.incident_list:
            if not (regs & inc["regions"]):
                continue
            if inc["from"] <= t < inc["to"]:
                out.add(inc["source"])
        return out

    def compute_boundary(self):
        """Recover the knowledge-time boundary from the production run log."""
        path = os.path.join(self.dir, "snapshot_runs.log")
        if not os.path.isfile(path):
            die("missing required input file: snapshot_runs.log")
        admits, defers = [], []
        cut = None
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                s = raw.strip()
                if not s or s.startswith("#"):
                    continue
                m = re.match(r"^(\S+)\s+RUN\s+snapshot=(\S+)\s+region=(\S+)\s+cut=(\S+)", s)
                if m:
                    cut = ts_key(m.group(4))
                    continue
                m = re.match(r"^(\S+)\s+BOUNDARY\s+source=(\S+)\s+record=(\S+)\s+recorded_at=(\S+)\s+decision=(\S+)", s)
                if m and cut is not None:
                    delta = ts_key(m.group(4)) - cut
                    if m.group(5) == "ADMIT":
                        admits.append(delta)
                    elif m.group(5) == "DEFER":
                        defers.append(delta)
        lo = max(admits) if admits else None
        hi = (min(defers) - 1) if defers else None
        if lo is None and hi is None:
            return 0
        if lo is None:
            return hi
        if hi is None:
            return lo
        return lo if lo <= hi else hi

    # -- conventions left to the evidence -----------------------------------

    def load_evidence(self, notices):
        best = None
        for conv_c in ROLLS:
            for conv_p in ROLLS:
                for variant in ("anchor", "shift"):
                    fails = self._notice_fails(notices, conv_c, conv_p, variant)
                    cand = (fails, ROLLS.index(conv_c), ROLLS.index(conv_p), variant == "shift")
                    if best is None or cand < best:
                        best = cand
        self.roll_conv = {"commercial": ROLLS[best[1]], "public": ROLLS[best[2]]}
        self.anchor_variant = "shift" if best[3] else "anchor"
        self.notice_fails = best[0]

    def _notice_fails(self, notices, conv_c, conv_p, variant):
        fails = 0
        for lid, k, printed, issued in notices:
            region = self.booking_region.get(lid)
            if region is None:
                continue
            conv = conv_c if self.contract_segment(lid) == "commercial" else conv_p
            t = ikey(datetime.datetime(issued.year, issued.month, issued.day, tzinfo=UTC)) + 86400
            shift = 0
            for fdi, months in self.holiday_state(lid, t):
                if k >= fdi:
                    shift += months
            lease = self.leases[lid]
            if variant == "shift" and shift:
                base = add_months(lease["start"].year, lease["start"].month + k, lease["anchor"], 0)
                nom = add_months(base.year, base.month, base.day, shift)
            else:
                nom = add_months(lease["start"].year, lease["start"].month + k, lease["anchor"], shift)
            if self.roll(nom, region, conv) != printed:
                fails += 1
        return fails


    # -- knowledge instants --------------------------------------------------

    def knowledge_instant(self, lid, day):
        """The knowledge instant of a lease at a snapshot (already boundary adjusted)."""
        region = self.booking_region.get(lid)
        if region is None:
            return None
        return self.cut_instant(region, day)

    def snapshot_dates(self):
        out = []
        for i in range(self.snapshot_count):
            out.append(add_months(self.first_snapshot.year, self.first_snapshot.month,
                                   self.first_snapshot.day, i * self.step_months))
        return out

    # -- scorecard ----------------------------------------------------------

    def version_for(self, day):
        best = None
        for entry in self.registry:
            if str(entry.get("status", "")).lower() != "released":
                continue
            eff = parse_date(entry["effective_from"])
            if eff > day:
                continue
            key = (eff, entry["version"])
            if best is None or key > best[0]:
                best = (key, entry["version"])
        return best[1] if best else None

    # -- dpd ----------------------------------------------------------------

    def dpd_scan(self, dues, cash, inst, tol, a, b):
        """(max dpd over [a, b], dpd on b) for a lease, in day ordinals."""
        if not dues or inst <= 0:
            return 0, 0
        n = len(dues)
        vdates, cums = cash if cash else ([], [])

        def paid(day):
            if not vdates:
                return 0
            i = bisect.bisect_right(vdates, day)
            return cums[i - 1] if i else 0

        def dpd(day):
            kmin = (paid(day) + tol) // inst + 1
            if kmin > n:
                return 0
            kmax = bisect.bisect_left(dues, day)
            if kmin > kmax:
                return 0
            return day - dues[kmin - 1]

        events = []
        if cash:
            events.extend(v for v in vdates if a < v <= b)
        events.extend(u + 1 for u in dues if a <= u < b)
        events = sorted(set(events))
        best = 0
        cur = a
        for e in events:
            end = min(e - 1, b)
            if end >= cur:
                d = dpd(end)
                if d > best:
                    best = d
            cur = e
            if e > b:
                break
        if cur <= b:
            d = dpd(b)
            if d > best:
                best = d
        else:
            d = dpd(b)
        return best, d

    # -- characteristics -----------------------------------------------------

    def compute_observation(self, lid, snapshot, asof, t, pool, cut=None):
        """Return (region, segment, obligor, version, bins) or None."""
        region = pool["branch"][lid]
        oref = self.leases[lid]["obligor"]
        if oref is None or not self.obligor_known(oref, t):
            return None
        surv = self.surviving(oref, asof, t)
        tax = self.tax_id_at(surv, t)
        segment = "public" if (tax and self.is_public(tax, asof)) else "commercial"
        version = self.version_for(snapshot)
        card = self.scorecards[version]
        listed = [c["name"] for c in card["characteristics"]]
        quar = set()
        if self.incident_list:
            quar = self.quarantined_sources(region, cut if cut is not None else t)
        conv_seg = self.contract_segment(lid)
        tol = self.tolerance[conv_seg]
        inst = self.leases[lid]["inst"]
        holidays = self.holiday_state(lid, t)
        dues = self.schedule(lid, holidays)
        cash = self.cash_at(lid, t)
        values = {}

        if "dpd_now" in listed:
            values["dpd_now"] = self.dpd_scan(dues, cash, inst, tol, asof.toordinal(),
                                             asof.toordinal())[1]
        if "max_dpd_12m" in listed:
            lo = asof.toordinal() - 364
            values["max_dpd_12m"] = self.dpd_scan(dues, cash, inst, tol, lo, asof.toordinal())[0]
        if "recent_worst" in listed:
            lo = asof.toordinal() - 89
            values["recent_worst"] = self.dpd_scan(dues, cash, inst, tol, lo, asof.toordinal())[0]
        if "months_on_book" in listed:
            start = self.leases[lid]["start"]
            months = (asof.year - start.year) * 12 + (asof.month - start.month)
            if asof.day < start.day:
                months -= 1
            values["months_on_book"] = months
        if "active_leases" in listed:
            values["active_leases"] = pool["active"].get(surv, 0)
        if "utilisation" in listed:
            limit = self.limit_at(surv, asof, t)
            if limit is None:
                values["utilisation"] = "missing"
            elif limit == 0:
                values["utilisation"] = "zero_limit"
            else:
                exposure = pool["exposure"].get(surv, 0)
                values["utilisation"] = (exposure * 1000) // (limit * 100000)
        if "bureau" in listed:
            res = self.bureau_at(tax, asof, t, segment)
            if res is None:
                values["bureau"] = "missing"
            elif res[0] == "score":
                values["bureau"] = res[1]
            else:
                values["bureau"] = res[0]
        if "sector_class" in listed:
            sector = self.sector_at(surv, asof, t)
            values["sector_class"] = self.sectors.get(str(sector)) if sector is not None else None

        bins = {}
        for ch in listed:
            spec = self._char_spec(card, ch)
            if spec is None:
                continue
            val = values.get(ch)
            label = None
            if quar and (self.char_nodes.get(ch, set()) & quar):
                label = "quarantined"
            elif isinstance(val, str) and val in ("missing", "zero_limit", "no_hit", "thin"):
                label = val
            elif ch == "sector_class":
                label = val if val is not None else "missing"
                if label is not None and label not in spec.get("categories", {}):
                    label = "missing"
            if label is None and ch != "sector_class":
                label = self._bin_label(spec, val)
            bins[ch] = label
        return region, segment, surv, version, bins

    def _char_spec(self, card, name):
        specs = card.get("\x00specs")
        if specs is None:
            specs = {c["name"]: c for c in card["characteristics"]}
            card["\x00specs"] = specs
        return specs.get(name)

    def _bin_label(self, spec, value):
        if value is None:
            return "missing"
        for b in spec.get("bins", ()):
            lo = b.get("lo")
            hi = b.get("hi")
            if (lo is None or value >= lo) and (hi is None or value < hi):
                return b["label"]
        bins = spec.get("bins", ())
        if bins:
            return bins[-1]["label"]
        return "missing"

    def points_of(self, card, segment, bins):
        score = card["base_points"][segment]
        for ch, label in bins.items():
            spec = self._char_spec(card, ch)
            if spec is None:
                continue
            special = spec.get("special", {})
            if label in special:
                score += special[label]
                continue
            if "categories" in spec:
                score += spec["categories"].get(label, 0)
                continue
            for b in spec.get("bins", ()):
                if b["label"] == label:
                    score += b["points"]
                    break
        return score

    # -- labels --------------------------------------------------------------

    def closing_dates(self, lid, horizon):
        """(charge off date, closing date) on or before horizon, at the watermark."""
        eff = self.events_at(lid, self.watermark)
        state = "pending"
        charge = None
        close = None
        for eff_date, _, typ in eff:
            if eff_date > horizon:
                break
            if state == "pending" and typ == "ACTIVATE":
                state = "active"
            elif state == "active" and typ in ("BUYOUT", "PAYOFF"):
                state = "closed"
                if close is None:
                    close = eff_date
            elif state == "active" and typ == "CHARGE_OFF":
                state = "charged_off"
                if charge is None:
                    charge = eff_date
        return charge, close

    def deferral_span_ord(self, lid, t):
        """Ordinal span [without, with) of the first deferred instalment at t."""
        holidays = self.holiday_state(lid, t)
        if not holidays:
            return None
        fdi = min(h[0] for h in holidays)
        shift = sum(h[1] for h in holidays if h[0] <= fdi)
        if shift <= 0:
            return None
        base = self.schedule(lid, ())
        moved = self.schedule(lid, holidays)
        if fdi < 1 or fdi > len(base) or fdi > len(moved):
            return None
        return (base[fdi - 1], moved[fdi - 1])

    def label_of(self, lid, asof):
        window_end = asof + datetime.timedelta(days=self.performance_days)
        if window_end > self.data_cutoff:
            return "immature"
        charge, close = self.closing_dates(lid, window_end)
        if charge is not None:
            return "bad"
        conv_seg = self.contract_segment(lid)
        tol = self.tolerance[conv_seg]
        inst = self.leases[lid]["inst"]
        holidays = self.holiday_state(lid, self.watermark)
        dues = self.schedule(lid, holidays)
        cash = self.cash_at(lid, self.watermark)
        a = asof.toordinal() + 1
        b = window_end.toordinal()
        if close is not None:
            b = min(b, close.toordinal())
        if b >= a:
            worst = self.dpd_scan(dues, cash, inst, tol, a, b)[0]
            if worst >= self.bad_dpd:
                return "bad"
        if close is not None:
            return "indeterminate"
        return "good"

    # -- exclusions -----------------------------------------------------------

    def exclusion_of(self, lid, asof, t, surv, pool):
        for reason in self.exclusion_reasons:
            if reason == "prior_charge_off":
                if pool["charged"].get(surv, 0) > 0:
                    return "prior_charge_off"
            elif reason == "holiday_active":
                span = self.deferral_span_ord(lid, t)
                if span is not None and span[0] <= asof.toordinal() < span[1]:
                    return "holiday_active"
        return None

    # -- audit -------------------------------------------------------------

    def merge_report(self):
        """Obligors folded by a MERGE event known at the watermark, and their survivor."""
        folded = set()
        horizon = self.watermark_dt.date()
        for oid, events in self.ob_events.items():
            for e in events:
                if e["type"] != "MERGE" or ts_key(e["recorded_at"]) > self.watermark:
                    continue
                folded.add(oid)
                d = parse_date(e["effective_date"])
                if d > horizon:
                    horizon = d
        out = []
        for oid in sorted(folded):
            out.append({"obligor_id": oid,
                        "resolved_to": self.surviving(oid, horizon, self.watermark)})
        return out

    def payment_belongs(self, key, t):
        """The lease a payment belongs to at t, ignoring any reversal."""
        line = None
        for l in self.line_index.get(key, ()):
            if l["at"] <= t:
                line = l
            else:
                break
        post = None
        for p in self.posting_index.get(key, ()):
            if p["at"] <= t:
                post = p
            else:
                break
        if post is not None:
            return post["lease"]
        if line is not None:
            return line["lease"]
        return None

    def payment_counts(self):
        counts = {"lockbox": 0, "card": 0, "ach": 0, "reversed": 0}
        for key in self.payments:
            if self.payment_belongs(key, self.watermark) is None:
                continue
            counts[key[0]] += 1
            if self._reversed_at(key, self.watermark):
                counts["reversed"] += 1
        return counts

    def _reversed_at(self, key, t):
        for post in self.posting_index.get(key, ()):
            if post["at"] > t:
                continue
            for r in self._return_by_posting.get(post["id"], ()):
                if r["reverses"] and r["at"] <= t:
                    return True
        return False



# --------------------------------------------------------------- population ---

def totals_of(obs):
    return {
        "observations": len(obs),
        "excluded": sum(1 for o in obs if o["exclusion"]),
        "bad": sum(1 for o in obs if o["label"] == "bad"),
        "good": sum(1 for o in obs if o["label"] == "good"),
        "indeterminate": sum(1 for o in obs if o["label"] == "indeterminate"),
        "immature": sum(1 for o in obs if o["label"] == "immature"),
        "approved": sum(1 for o in obs if o["approved"]),
    }


def metrics_of(obs):
    pop = [o for o in obs if not o["exclusion"] and o["label"] in ("bad", "good")]
    bad = [o for o in pop if o["label"] == "bad"]
    good = [o for o in pop if o["label"] == "good"]
    auc = None
    ks = None
    nb, ng = len(bad), len(good)
    if nb and ng:
        bad_scores = sorted(o["score"] for o in bad)
        good_scores = sorted(o["score"] for o in good)
        num = 0
        for s in bad_scores:
            gt = ng - bisect.bisect_right(good_scores, s)
            eq = bisect.bisect_right(good_scores, s) - bisect.bisect_left(good_scores, s)
            num += 2 * gt + eq
        auc = half_even_ppm(num, 2 * nb * ng)
        best = 0
        for c in sorted({o["score"] for o in pop}):
            b_le = bisect.bisect_right(bad_scores, c)
            g_le = bisect.bisect_right(good_scores, c)
            diff = abs(b_le * ng - g_le * nb)
            if diff > best:
                best = diff
        ks = half_even_ppm(best, nb * ng)
    return {
        "population": len(pop),
        "bad": len(bad),
        "good": len(good),
        "auc_ppm": auc,
        "ks_ppm": ks,
        "bad_rate_ppm": None if not pop else half_even_ppm(len(bad), len(pop)),
        "approved": sum(1 for o in pop if o["approved"]),
        "approved_bad": sum(1 for o in pop if o["approved"] and o["label"] == "bad"),
    }


# ------------------------------------------------------------------- runner ---

class Backtest:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.model = Model(data_dir)

    def load(self):
        m = self.model
        m._contract_seg = {}
        m._events_cache = {}
        m._sched_cache = {}
        m._cash_cache = {}
        m._spec_cache = {}
        m._event_versions = defaultdict(lambda: defaultdict(list))
        m.load_config()
        m.boundary = m.compute_boundary()
        m.watermark = m.watermark_raw + m.boundary
        ex = Extract(self.data_dir, m.watermark)
        m.load_identity(ex)
        events = ex.jsonl("lease_events.jsonl", "recorded_at")
        for e in events:
            lid = lease_ref(e["lease_ref"])
            if lid is None or lid not in m.leases:
                continue
            m._event_versions[lid][e["event_id"]].append(e)
        for lid in m._event_versions:
            for eid in m._event_versions[lid]:
                m._event_versions[lid][eid].sort(
                    key=lambda e: (ts_key(e["recorded_at"]), e["\x00line"]))
        notices, invoice_lease = m.load_lifecycle(ex, events)
        m.load_cash(ex, invoice_lease)
        m.load_bureau(ex)
        m.load_incidents(ex)
        m.char_nodes = m.char_closure()
        ex.counted_lines("snapshot_runs.log", is_late=m._log_line_is_late)
        m.load_evidence(notices)
        self.ex = ex
        return self

    def pool_for(self, snapshot, asof, t):
        m = self.model
        active = defaultdict(int)
        exposure = defaultdict(int)
        charged = defaultdict(int)
        branch = {}
        for lid in m.lease_ids:
            reg = m.branch_at(lid, asof, t)
            if reg is not None:
                branch[lid] = reg
            oref = m.leases[lid]["obligor"]
            if oref is None or not m.obligor_known(oref, t):
                continue
            surv = m.surviving(oref, asof, t)
            if surv is None:
                continue
            state = m.state_at(lid, asof, t)
            if state == "active":
                active[surv] += 1
                dues = m.schedule(lid, m.holiday_state(lid, t))
                due_after = len(dues) - bisect.bisect_right(dues, asof.toordinal())
                exposure[surv] += m.leases[lid]["inst"] * due_after
            elif state == "charged_off":
                charged[surv] += 1
        return {"active": active, "exposure": exposure, "charged": charged, "branch": branch}

    def run(self):
        m = self.model
        snapshots = m.snapshot_dates()
        observations = []
        unresolved = []
        candidates = 0
        cut_instants = {region: {} for region in m.regions}
        for snapshot in snapshots:
            asof = snapshot - datetime.timedelta(days=1)
            pools = {}
            for lid in m.lease_ids:
                cut = m.knowledge_instant(lid, snapshot)
                if cut is None:
                    continue
                t = cut + m.boundary
                if t not in pools:
                    pools[t] = self.pool_for(snapshot, asof, t)
                if m.state_at(lid, asof, t) != "active":
                    continue
                candidates += 1
                pool = pools[t]
                if lid not in pool["branch"]:
                    unresolved.append({"lease_id": lid, "snapshot": snapshot.isoformat(),
                                       "reason": "no_branch"})
                    continue
                got = m.compute_observation(lid, snapshot, asof, t, pool, cut)
                if got is None:
                    unresolved.append({"lease_id": lid, "snapshot": snapshot.isoformat(),
                                       "reason": "unknown_obligor"})
                    continue
                region, segment, surv, version, bins = got
                card = m.scorecards[version]
                score = m.points_of(card, segment, bins)
                approved = score >= card["cutoff"][segment]
                exclusion = m.exclusion_of(lid, asof, t, surv, pool)
                label = m.label_of(lid, asof)
                observations.append({
                    "lease_id": lid,
                    "snapshot": snapshot.isoformat(),
                    "obligor_id": surv,
                    "segment": segment,
                    "scorecard": version,
                    "bins": bins,
                    "score": score,
                    "approved": approved,
                    "exclusion": exclusion,
                    "label": label,
                    "region": region,
                })
            for region in m.regions:
                cut_instants[region][snapshot.isoformat()] = \
                    format_instant(m.cut_instant(region, snapshot))
        observations.sort(key=lambda o: (o["snapshot"], o["lease_id"]))
        unresolved.sort(key=lambda o: (o["snapshot"], o["lease_id"]))
        self.observations = observations
        self.unresolved = unresolved
        self.candidates = candidates
        self.snapshots = snapshots
        self.cut_instants = cut_instants
        return self


def format_instant(t):
    return (EPOCH + datetime.timedelta(seconds=t)).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------ reports ---

def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, sort_keys=True, separators=(",", ":"))
        fh.write("\n")


def observation_out(o):
    return {
        "lease_id": o["lease_id"],
        "snapshot": o["snapshot"],
        "obligor_id": o["obligor_id"],
        "segment": o["segment"],
        "scorecard": o["scorecard"],
        "bins": o["bins"],
        "score": o["score"],
        "approved": o["approved"],
        "exclusion": o["exclusion"],
        "label": o["label"],
    }


def build_reports(bt, out_dir):
    m = bt.model
    obs = bt.observations
    regions = sorted(m.regions)
    os.makedirs(out_dir, exist_ok=True)

    for region in regions:
        rows = [o for o in obs if o["region"] == region]
        write_json(os.path.join(out_dir, "region_%s.json" % region), {
            "region": region,
            "totals": totals_of(rows),
            "metrics": metrics_of(rows),
            "observations": [observation_out(o) for o in rows],
        })

    for segment in ("commercial", "public"):
        rows = [o for o in obs if o["segment"] == segment]
        by_snapshot = []
        for snap in bt.snapshots:
            sub = [o for o in rows if o["snapshot"] == snap.isoformat()]
            by_snapshot.append({
                "snapshot": snap.isoformat(),
                "totals": totals_of(sub),
                "metrics": metrics_of(sub),
            })
        cards = Counter(o["scorecard"] for o in rows)
        write_json(os.path.join(out_dir, "segment_%s.json" % segment), {
            "segment": segment,
            "totals": totals_of(rows),
            "metrics": metrics_of(rows),
            "by_snapshot": by_snapshot,
            "by_scorecard": dict(sorted(cards.items())),
        })

    by_region = {region: totals_of([o for o in obs if o["region"] == region]) for region in regions}
    by_segment = {seg: totals_of([o for o in obs if o["segment"] == seg])
                  for seg in ("commercial", "public")}
    by_snapshot = []
    for snap in bt.snapshots:
        sub = [o for o in obs if o["snapshot"] == snap.isoformat()]
        by_snapshot.append({
            "snapshot": snap.isoformat(),
            "totals": totals_of(sub),
            "auc_ppm": metrics_of(sub)["auc_ppm"],
        })
    bands = []
    for name, lo, hi in m.bands:
        rows = [o for o in obs if (lo is None or o["score"] >= lo) and (hi is None or o["score"] < hi)]
        bands.append({
            "band": name,
            "observations": len(rows),
            "bad": sum(1 for o in rows if o["label"] == "bad"),
            "good": sum(1 for o in rows if o["label"] == "good"),
        })
    write_json(os.path.join(out_dir, "summary.json"), {
        "run_id": m.run_id,
        "snapshots": [s.isoformat() for s in bt.snapshots],
        "totals": totals_of(obs),
        "metrics": metrics_of(obs),
        "by_region": by_region,
        "by_segment": by_segment,
        "by_snapshot": by_snapshot,
        "score_bands": bands,
    })

    usage = []
    for snap in bt.snapshots:
        counts = Counter(o["scorecard"] for o in obs if o["snapshot"] == snap.isoformat())
        for version in sorted(counts):
            usage.append({"snapshot": snap.isoformat(), "version": version,
                          "observations": counts[version]})
    exclusions = [{"lease_id": o["lease_id"], "snapshot": o["snapshot"], "reason": o["exclusion"]}
                  for o in obs if o["exclusion"]]
    quarantined = []
    for o in obs:
        names = sorted(ch for ch, lab in o["bins"].items() if lab == "quarantined")
        if names:
            quarantined.append({"lease_id": o["lease_id"], "snapshot": o["snapshot"],
                                "characteristics": names})
    holidays = []
    for rid in sorted(m.requests):
        req = m.requests[rid]
        if rid in m.governing_holidays(req["lease"], m.watermark):
            holidays.append({
                "request_id": rid,
                "lease_id": req["lease"],
                "months": req["months"],
                "first_deferred_instalment": req["fdi"],
            })
    write_json(os.path.join(out_dir, "policy_audit.json"), {
        "cut_instants": {s: {r: bt.cut_instants[r][s] for r in regions} for s in bt.snapshots_iso},
        "scorecard_usage": usage,
        "exclusions": exclusions,
        "quarantined": quarantined,
        "holidays": holidays,
        "merges": m.merge_report(),
    })

    rejects = sorted(set(m.event_rejects + m.relief_rejects + m.cash_rejects + m.return_rejects +
                        m.holiday_limits()))
    late = {k: v for k, v in sorted(bt.ex.late.items()) if v}
    write_json(os.path.join(out_dir, "data_quality.json"), {
        "rejects": [{"source": s, "record_id": r, "reason": reason} for s, r, reason in rejects],
        "duplicates": dict(sorted(bt.ex.duplicates().items())),
        "late_records": late,
        "unresolved": bt.unresolved,
        "partition": {"candidates": bt.candidates, "scored": len(obs),
                      "unresolved": len(bt.unresolved)},
        "payments": m.payment_counts(),
        "identity_check": {
            "regions_minus_summary": sum(by_region[r]["observations"] for r in by_region)
            - totals_of(obs)["observations"],
            "segments_minus_summary": sum(by_segment[s]["observations"] for s in by_segment)
            - totals_of(obs)["observations"],
            "snapshots_minus_summary": sum(e["totals"]["observations"] for e in by_snapshot)
            - totals_of(obs)["observations"],
        },
    })


def main(argv):
    if len(argv) != 3:
        die("usage: derive_report.py DATA_DIR OUT_DIR")
    data_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(data_dir):
        die("data directory not found: %s" % data_dir)
    bt = Backtest(data_dir).load()
    bt.run()
    bt.snapshots_iso = [s.isoformat() for s in bt.snapshots]
    build_reports(bt, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))








