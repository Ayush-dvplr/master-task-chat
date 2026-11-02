#!/usr/bin/env python3
"""Out of time backtest of the Halvard Equipment Finance champion lease scorecard.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""

import json
import os
import re
import sys
import tomllib
from bisect import bisect_right, bisect_left
from collections import defaultdict

EPOCH_ORD = 719163  # date(1970, 1, 1).toordinal()

MONTH_DAYS = (31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def fail(msg):
    sys.stderr.write("error: %s\n" % msg)
    raise SystemExit(2)


# ---------------------------------------------------------------- date helpers

def is_leap(y):
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def days_in_month(y, m):
    if m == 2 and is_leap(y):
        return 29
    return MONTH_DAYS[m - 1]


def ymd_to_ord(y, m, d):
    # proleptic Gregorian ordinal, same as date.toordinal()
    y -= 1
    n = y * 365 + y // 4 - y // 100 + y // 400
    cum = (0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334)[m - 1]
    if m > 2 and is_leap(y + 1):
        cum += 1
    return n + cum + d


def ord_to_ymd(o):
    y = (o * 400) // 146097
    if y < 1:
        y = 1
    while ymd_to_ord(y, 1, 1) > o:
        y -= 1
    while ymd_to_ord(y + 1, 1, 1) <= o:
        y += 1
    rem = o - ymd_to_ord(y, 1, 1) + 1
    m = 1
    while True:
        dim = days_in_month(y, m)
        if rem <= dim:
            break
        rem -= dim
        m += 1
    return y, m, rem


_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_INST_RE = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?"
    r"(Z|z|[+-]\d{2}:?\d{2})?$"
)


def parse_date(s):
    s = s.strip()
    m = _DATE_RE.match(s)
    if not m:
        fail("bad date %r" % s)
    return ymd_to_ord(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def parse_instant(s):
    s = s.strip()
    m = _INST_RE.match(s)
    if not m:
        fail("bad instant %r" % s)
    y, mo, d, h, mi, se, tz = m.groups()
    v = (ymd_to_ord(int(y), int(mo), int(d)) - EPOCH_ORD) * 86400
    v += int(h) * 3600 + int(mi) * 60 + int(se)
    if tz and tz not in ("Z", "z"):
        sign = 1 if tz[0] == "+" else -1
        off = int(tz[1:3]) * 3600 + int(tz[-2:]) * 60
        v -= sign * off
    return v


def parse_clock(s):
    s = s.strip()
    parts = s.split(":")
    if len(parts) == 2:
        parts.append("0")
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])


def fmt_date(o):
    y, m, d = ord_to_ymd(o)
    return "%04d-%02d-%02d" % (y, m, d)


def fmt_instant(secs):
    o = secs // 86400 + EPOCH_ORD
    rem = secs % 86400
    y, m, d = ord_to_ymd(o)
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (
        y, m, d, rem // 3600, (rem // 60) % 60, rem % 60)


def add_months_day(y, m, k, day):
    """Ordinal of the date `k` months after (y, m), on `day` clamped."""
    t = m - 1 + k
    y2 = y + t // 12
    m2 = t % 12 + 1
    dim = days_in_month(y2, m2)
    return ymd_to_ord(y2, m2, day if day < dim else dim)


def money_to_cents(s):
    s = s.strip()
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    if "." in s:
        a, b = s.split(".", 1)
        b = (b + "00")[:2]
    else:
        a, b = s, "00"
    v = int(a or "0") * 100 + int(b)
    return -v if neg else v


_AMOUNT_RE = re.compile(r"^\d+\.\d\d$")


def strict_cents(s):
    """Positive dollars with exactly two decimals, else None."""
    s = s.strip()
    if not _AMOUNT_RE.match(s):
        return None
    v = int(s[:-3]) * 100 + int(s[-2:])
    return v if v > 0 else None


# -------------------------------------------------------------- reference text

def norm_ref(s):
    return s.replace(" ", "").replace("-", "").replace("_", "").upper()


_DIGITS_RE = re.compile(r"\D")


def only_digits(s):
    return _DIGITS_RE.sub("", s)


def read_text(path):
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def read_lines(path):
    return read_text(path).splitlines()


def read_csv(path):
    lines = read_lines(path)
    if not lines:
        fail("empty csv %s" % path)
    head = lines[0].split(",")
    out = []
    for raw in lines[1:]:
        if not raw:
            continue
        out.append((dict(zip(head, raw.split(","))), raw))
    return out


def read_jsonl(path):
    out = []
    for raw in read_lines(path):
        if not raw.strip():
            continue
        out.append((json.loads(raw), raw))
    return out


def read_ini(path):
    """Minimal ini reader: section -> list of (key, value) in file order."""
    sections = {}
    order = []
    cur = None
    for raw in read_lines(path):
        line = raw.strip()
        if not line or line[0] in ";#":
            continue
        if line.startswith("[") and line.endswith("]"):
            cur = line[1:-1].strip()
            if cur not in sections:
                sections[cur] = []
                order.append(cur)
            continue
        if "=" not in line or cur is None:
            continue
        k, v = line.split("=", 1)
        sections[cur].append((k.strip(), v.strip()))
    return sections, order


def _scalar(v):
    v = v.strip()
    if v.startswith('"') and v.endswith('"') and len(v) >= 2:
        return v[1:-1]
    if v.startswith("'") and v.endswith("'") and len(v) >= 2:
        return v[1:-1]
    if re.match(r"^-?\d+$", v):
        return int(v)
    return v


def _inline_map(s):
    out = {}
    for part in s[1:-1].split(","):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        out[k.strip()] = _scalar(v.strip())
    return out


def read_yaml_list(path, key):
    """Read a yaml file holding `key:` followed by a list of mappings."""
    items = []
    seen_key = False
    cur = None
    for raw in read_lines(path):
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        line = raw.strip()
        if not seen_key:
            if line.rstrip(":") == key and line.endswith(":"):
                seen_key = True
            continue
        if line.startswith("- "):
            item = line[2:].strip()
            if item.startswith("{") and item.endswith("}"):
                cur = _inline_map(item)
                items.append(cur)
            else:
                cur = {}
                items.append(cur)
                if ":" in item:
                    k, v = item.split(":", 1)
                    cur[k.strip()] = _scalar(v.strip())
        elif ":" in line and cur is not None:
            k, v = line.split(":", 1)
            cur[k.strip()] = _scalar(v.strip())
    return items


def read_yaml_nodes(path):
    """Read feature_lineage.yaml: two top level mappings of name -> list."""
    out = {}
    cur = None
    for raw in read_lines(path):
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        line = raw.strip()
        if indent == 0:
            k = line.split(":", 1)[0].strip()
            cur = {}
            out[k] = cur
            continue
        if ":" not in line or cur is None:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            cur[k.strip()] = [x.strip() for x in inner.split(",") if x.strip()]
        else:
            cur[k.strip()] = []
    return out


# ------------------------------------------------------------------- loading

FIXED_INPUTS = [
    "backtest_run.toml",
    "region_clock.ini",
    "branches.ini",
    "holiday_calendar.ics",
    "servicing_policy.ini",
    "return_codes.ini",
    "bureau_vendors.ini",
    "bureau_disputes.json",
    "sector_reference.json",
    "feature_lineage.yaml",
    "data_incidents.json",
    "exclusion_policy.yaml",
    "score_bands.yaml",
    "scorecard_registry.json",
    "leases.csv",
    "lease_branch_history.csv",
    "lease_events.jsonl",
    "relief_approvals.csv",
    "obligors.csv",
    "obligor_events.jsonl",
    "public_entity_register.csv",
    "lockbox_north.csv",
    "lockbox_south.csv",
    "lockbox_west.csv",
    "lockbox_east.csv",
    "card_settlements.csv",
    "ach_returns.log",
    "bureau_kr.jsonl",
    "bureau_nd.csv",
    "credit_limits.csv",
    "invoice_notices.csv",
    "snapshot_runs.log",
]

LOCKBOX_FILES = [
    ("lockbox_north.csv", "North"),
    ("lockbox_south.csv", "South"),
    ("lockbox_west.csv", "West"),
    ("lockbox_east.csv", "East"),
]

DUP_COUNTED = ["lease_events.jsonl", "card_settlements.csv"] + \
    [f for f, _ in LOCKBOX_FILES]


class Extract(object):
    """Everything the extract says, read once."""

    def __init__(self, data_dir):
        self.dir = data_dir
        self.duplicates = {}
        self.late = {}
        self.rejects = set()
        self._check_and_load()

    # -- plumbing ---------------------------------------------------------
    def path(self, name):
        return os.path.join(self.dir, name)

    def need(self, name):
        p = self.path(name)
        if not os.path.isfile(p):
            fail("required input file missing: %s" % name)
        return p

    def dedupe(self, raws):
        """Byte identical lines are one record: distinct lines and their counts."""
        counts = {}
        order = []
        for raw in raws:
            if raw in counts:
                counts[raw] += 1
            else:
                counts[raw] = 1
                order.append(raw)
        return order, counts

    def count_dup(self, name, n):
        """Duplicates are counted for the files whose lines the rules call
        records: the lease events and the three payment sources."""
        if n and (name in DUP_COUNTED or
                  re.fullmatch(r"servicing_ledger_\d{4}\.jsonl", name)):
            self.duplicates[name] = self.duplicates.get(name, 0) + n

    def note_late(self, name, n=1):
        if n:
            self.late[name] = self.late.get(name, 0) + n

    def reject(self, source, record_id, reason):
        self.rejects.add((source, record_id, reason))

    # -- main load --------------------------------------------------------
    def _check_and_load(self):
        for name in FIXED_INPUTS:
            self.need(name)
        with open(self.need("backtest_run.toml"), "rb") as fh:
            run = tomllib.load(fh)["run"]
        self.run_id = run["run_id"]
        self.first_snapshot = parse_date(str(run["first_snapshot"]))
        self.snapshot_count = int(run["snapshot_count"])
        self.step_months = int(run["snapshot_step_months"])
        self.performance_days = int(run["performance_days"])
        self.bad_dpd = int(run["bad_dpd"])
        self.data_cutoff = parse_date(str(run["data_cutoff"]))
        self.watermark = parse_instant(str(run["watermark_utc"]))
        self.cut_secs = parse_clock(str(run["cut_local_time"]))
        self.notices_through = parse_date(str(run["notices_through"]))

        reg = json.load(open(self.need("scorecard_registry.json")))
        self.versions = []
        for v in reg["versions"]:
            self.need(v["file"])
            self.versions.append({
                "version": v["version"],
                "file": v["file"],
                "effective_from": parse_date(str(v["effective_from"])),
                "status": v["status"],
            })

        self._load_clocks()
        self._load_branches()
        self._load_holidays()
        self._load_policy()
        self._load_bureau_config()
        self._load_feature_config()
        self._load_scorecards()
        self._load_boundary()
        self._load_leases()
        self._load_branch_history()
        self._booking_regions()
        self._load_lease_events()
        self._load_relief()
        self._load_obligors()
        self._load_register()
        self._load_notices()
        self._load_payments()
        self._load_bureau()
        self._load_limits()
        self._build_calendar_tables()
        self._contract_segments()
        self._fit_conventions()

    # -- configuration ----------------------------------------------------
    def _load_clocks(self):
        sections, order = read_ini(self.need("region_clock.ini"))
        self.clock = {}
        for sec in order:
            vals = dict(sections[sec])
            periods = []
            for span in vals.get("daylight_periods", "").split(","):
                span = span.strip()
                if not span:
                    continue
                a, b = span.split("/")
                periods.append((parse_instant(a), parse_instant(b)))
            periods.sort()
            self.clock[sec.lower()] = (
                int(vals["standard_offset"]) * 60,
                int(vals["daylight_offset"]) * 60,
                periods,
            )

    def _load_branches(self):
        sections, _ = read_ini(self.need("branches.ini"))
        self.branch_region = {}
        for k, v in sections.get("branches", []):
            self.branch_region[norm_ref(k)] = v
        for k, v in sections.get("aliases", []):
            tgt = norm_ref(v)
            if tgt in self.branch_region:
                self.branch_region[norm_ref(k)] = self.branch_region[tgt]
        self.regions = sorted(set(self.branch_region.values()))

    def _load_holidays(self):
        self.holidays = dict((r, set()) for r in self.regions)
        cur = None
        for raw in read_lines(self.need("holiday_calendar.ics")):
            line = raw.strip()
            if line == "BEGIN:VEVENT":
                cur = {}
                continue
            if line == "END:VEVENT":
                if cur is not None and cur.get("STATUS") == "CONFIRMED" \
                        and "DTSTART" in cur and "DTEND" in cur:
                    names = [x.strip() for x in cur.get("CATEGORIES", "").split(",")]
                    for d in range(cur["DTSTART"], cur["DTEND"]):
                        for nm in names:
                            if nm in self.holidays:
                                self.holidays[nm].add(d)
                cur = None
                continue
            if cur is None or ":" not in line:
                continue
            key, val = line.split(":", 1)
            key = key.split(";")[0].strip()
            if key in ("DTSTART", "DTEND"):
                v = val.strip()
                if len(v) >= 8 and v[:8].isdigit():
                    cur[key] = ymd_to_ord(int(v[0:4]), int(v[4:6]), int(v[6:8]))
            elif key in ("STATUS", "CATEGORIES", "SUMMARY"):
                cur[key] = val.strip()

    def _load_policy(self):
        sections, _ = read_ini(self.need("servicing_policy.ini"))
        self.tolerance = {}
        for k, v in sections.get("tolerance", []):
            if k.endswith("_cents"):
                self.tolerance[k[:-6]] = int(v)
        self.surcharge = int(dict(sections.get("card", []))["surcharge_cents"])
        self.max_holidays = int(
            dict(sections.get("relief", []))["max_holidays_per_lease"])
        sections, _ = read_ini(self.need("return_codes.ini"))
        self.return_reverses = {}
        for k, v in sections.get("codes", []):
            self.return_reverses[k.strip().upper()] = (v.strip().lower() == "yes")

    def _load_bureau_config(self):
        sections, _ = read_ini(self.need("bureau_vendors.ini"))
        gen = dict(sections.get("general", []))
        self.max_age_days = int(gen["max_age_days"])
        self.precedence = {}
        for k, v in sections.get("precedence", []):
            self.precedence[k.strip().lower()] = [
                x.strip() for x in v.split(",") if x.strip()]
        nd = dict(sections.get("ND", []))
        self.nd_num = int(nd["to_kr_numerator"])
        self.nd_den = int(nd["to_kr_denominator"])
        scale = dict(sections.get("KR", [])).get("scale", "300-850")
        self.kr_floor = int(scale.split("-")[0])
        disputes = json.load(open(self.need("bureau_disputes.json")))["disputes"]
        self.disputes = {}
        nlate = 0
        for d in disputes:
            rec = parse_instant(str(d["recorded_at"]))
            if rec > self.watermark:
                nlate += 1
                continue
            key = (d["vendor"], d["pull_id"])
            if key not in self.disputes or rec < self.disputes[key]:
                self.disputes[key] = rec
        self.note_late("bureau_disputes.json", nlate)

    def _load_feature_config(self):
        self.sector_class = json.load(
            open(self.need("sector_reference.json")))["sectors"]
        lineage = read_yaml_nodes(self.need("feature_lineage.yaml"))
        nodes = lineage.get("nodes", {})
        chars = lineage.get("characteristics", {})
        memo = {}

        def leaves(name):
            if name in memo:
                return memo[name]
            memo[name] = set()
            parents = nodes.get(name)
            if not parents:
                out = set([name])
            else:
                out = set()
                for p in parents:
                    out |= leaves(p)
            memo[name] = out
            return out

        self.char_sources = {}
        for cname, parents in chars.items():
            acc = set()
            for p in parents:
                acc |= leaves(p)
            self.char_sources[cname] = acc
        inc = json.load(open(self.need("data_incidents.json")))["incidents"]
        self.incidents = []
        for i in inc:
            if str(i.get("status", "")).lower() != "confirmed":
                continue
            self.incidents.append((
                i["source"],
                frozenset(i["regions"]),
                parse_instant(str(i["from_utc"])),
                parse_instant(str(i["to_utc"])),
            ))
        self.exclusion_order = [
            str(e["reason"]) for e in
            read_yaml_list(self.need("exclusion_policy.yaml"), "exclusions")]
        self.bands = []
        for b in read_yaml_list(self.need("score_bands.yaml"), "bands"):
            self.bands.append((str(b["band"]), int(b["lo"]), int(b["hi"])))

    def _load_scorecards(self):
        self.cards = {}
        for v in self.versions:
            data = json.load(open(self.path(v["file"])))
            chars = []
            for c in data["characteristics"]:
                entry = {
                    "name": c["name"],
                    "special": dict((k, int(x)) for k, x in
                                    c.get("special", {}).items()),
                    "bins": None,
                    "categories": None,
                }
                if "bins" in c:
                    entry["bins"] = [
                        (int(b["lo"]),
                         None if b["hi"] is None else int(b["hi"]),
                         b["label"], int(b["points"]))
                        for b in c["bins"]]
                if "categories" in c:
                    entry["categories"] = dict(
                        (k, int(x)) for k, x in c["categories"].items())
                chars.append(entry)
            self.cards[v["version"]] = {
                "version": data["version"],
                "base": dict((k, int(x)) for k, x in data["base_points"].items()),
                "cutoff": dict((k, int(x)) for k, x in data["cutoff"].items()),
                "chars": chars,
                "names": [c["name"] for c in chars],
            }

    def _load_boundary(self):
        """Does a record recorded exactly at the cut count as known?"""
        admit_eq = 0
        defer_eq = 0
        cut = None
        for raw in read_lines(self.need("snapshot_runs.log")):
            if not raw or raw.startswith("#"):
                continue
            if " RUN " in raw:
                m = re.search(r"cut=(\S+)", raw)
                if m:
                    cut = parse_instant(m.group(1))
                continue
            if " BOUNDARY " in raw and cut is not None:
                m = re.search(r"recorded_at=(\S+)\s+decision=(\S+)", raw)
                if not m:
                    continue
                if parse_instant(m.group(1)) != cut:
                    continue
                if m.group(2).strip().upper() == "ADMIT":
                    admit_eq += 1
                else:
                    defer_eq += 1
        self.boundary_inclusive = admit_eq >= defer_eq

    # -- records ----------------------------------------------------------
    def _load_leases(self):
        self.leases = {}
        self.lease_by_num = {}
        for row, _raw in read_csv(self.need("leases.csv")):
            lid = row["lease_id"]
            m = re.fullmatch(r"HL(\d+)", norm_ref(lid))
            if m:
                self.lease_by_num[int(m.group(1))] = lid
            self.leases[lid] = {
                "lease_id": lid,
                "obligor_ref": row["obligor_ref"],
                "start": parse_date(row["start_date"]),
                "term": int(row["term_months"]),
                "instalment": money_to_cents(row["instalment"]),
                "anchor": int(row["anchor_day"]),
                "product": row["product"],
            }
        self.lease_ids = sorted(self.leases)
        years = set()
        for L in self.leases.values():
            years.add(ord_to_ymd(L["start"])[0])
        first_year = min(years) if years else ord_to_ymd(self.data_cutoff)[0]
        last_year = ord_to_ymd(self.data_cutoff)[0]
        names = set()
        for y in range(first_year, last_year + 1):
            name = "servicing_ledger_%04d.jsonl" % y
            self.need(name)
            names.add(name)
        for name in os.listdir(self.dir):
            if re.fullmatch(r"servicing_ledger_\d{4}\.jsonl", name):
                names.add(name)
        self.ledger_files = sorted(names)

    def resolve_lease(self, ref):
        m = re.fullmatch(r"HL(\d+)", norm_ref(ref))
        if not m:
            return None
        return self.lease_by_num.get(int(m.group(1)))

    def resolve_obligor(self, ref):
        m = re.fullmatch(r"OB(\d+)", norm_ref(ref))
        if not m:
            return None
        return self.obligor_by_num.get(int(m.group(1)))

    def _load_branch_history(self):
        self.branch_rows = defaultdict(list)
        nlate = 0
        name = "lease_branch_history.csv"
        for row, _raw in read_csv(self.need(name)):
            rec = parse_instant(row["recorded_at"])
            if rec > self.watermark:
                nlate += 1
                continue
            lid = self.resolve_lease(row["lease_ref"])
            if lid is None:
                continue
            region = self.branch_region.get(norm_ref(row["branch_code"]))
            if region is None:
                continue
            self.branch_rows[lid].append(
                (parse_date(row["effective_from"]), rec, row["row_id"], region))
        for rows in self.branch_rows.values():
            rows.sort()
        self.note_late(name, nlate)

    def _load_lease_events(self):
        name = "lease_events.jsonl"
        raws, counts = self.dedupe(
            [raw for _o, raw in read_jsonl(self.need(name))])
        self.lease_events = defaultdict(list)
        nlate = 0
        ndup = 0
        for raw in raws:
            o = json.loads(raw)
            rec = parse_instant(o["recorded_at"])
            if rec > self.watermark:
                nlate += 1
                continue
            ndup += counts[raw] - 1
            lid = self.resolve_lease(o["lease_ref"])
            if lid is None:
                self.reject(name, o["event_id"], "unknown_lease")
                continue
            self.lease_events[lid].append(
                (o["event_id"], int(o["version"]), rec, o["type"],
                 parse_date(o["effective_date"])))
        self.note_late(name, nlate)
        self.count_dup(name, ndup)
        for rows in self.lease_events.values():
            rows.sort(key=lambda t: (t[0], t[1], t[2]))

    def _load_relief(self):
        name = "relief_approvals.csv"
        self.relief = {}
        nlate = 0
        for row, _raw in read_csv(self.need(name)):
            rec = parse_instant(row["status_at"])
            if rec > self.watermark:
                nlate += 1
                continue
            lid = self.resolve_lease(row["lease_ref"])
            if lid is None:
                self.reject(name, row["status_id"], "unknown_lease")
                continue
            req = self.relief.get(row["request_id"])
            if req is None:
                req = {
                    "request_id": row["request_id"],
                    "lease_id": lid,
                    "months": int(row["months"]),
                    "first": int(row["first_deferred_instalment"]),
                    "rows": [],
                }
                self.relief[row["request_id"]] = req
            req["rows"].append((rec, row["status_id"], row["status"]))
        for req in self.relief.values():
            req["rows"].sort()
        self.note_late(name, nlate)
        self.relief_by_lease = defaultdict(list)
        for rid in sorted(self.relief):
            self.relief_by_lease[self.relief[rid]["lease_id"]].append(rid)

    def _load_obligors(self):
        name = "obligors.csv"
        self.obligors = {}
        self.obligor_by_num = {}
        nlate = 0
        for row, _raw in read_csv(self.need(name)):
            rec = parse_instant(row["created_at"])
            if rec > self.watermark:
                nlate += 1
                continue
            oid = row["obligor_id"]
            m = re.fullmatch(r"OB(\d+)", norm_ref(oid))
            if m:
                self.obligor_by_num[int(m.group(1))] = oid
            self.obligors[oid] = {
                "obligor_id": oid,
                "tax_id": only_digits(row["tax_id"]),
                "created": rec,
            }
        self.note_late(name, nlate)
        name = "obligor_events.jsonl"
        self.taxid_fixes = defaultdict(list)
        self.merges = defaultdict(list)
        self.sectors = defaultdict(list)
        nlate = 0
        for o, _raw in read_jsonl(self.need(name)):
            rec = parse_instant(o["recorded_at"])
            if rec > self.watermark:
                nlate += 1
                continue
            oid = self.resolve_obligor(o["obligor_ref"])
            if oid is None:
                continue
            seq = int(o["event_seq"])
            eff = parse_date(o["effective_date"])
            t = o["type"]
            if t == "TAXID_CORRECTION":
                self.taxid_fixes[oid].append((rec, seq, only_digits(o["tax_id"])))
            elif t == "MERGE":
                self.merges[oid].append((eff, rec, seq, o["into"]))
            elif t in ("SECTOR_SET", "SECTOR_CHANGE"):
                self.sectors[oid].append((eff, rec, seq, str(o["sector_code"])))
        self.note_late(name, nlate)
        for d in (self.taxid_fixes, self.merges, self.sectors):
            for v in d.values():
                v.sort()

    def _load_register(self):
        self.register = defaultdict(list)
        for row, _raw in read_csv(self.need("public_entity_register.csv")):
            lo = parse_date(row["listed_on"])
            hi = parse_date(row["delisted_on"]) \
                if row["delisted_on"].strip() else None
            self.register[only_digits(row["fein"])].append((lo, hi))

    def _load_notices(self):
        self.invoice_lease = {}
        self.notices = []
        for row, _raw in read_csv(self.need("invoice_notices.csv")):
            lid = row["lease_id"] if row["lease_id"] in self.leases else \
                self.resolve_lease(row["lease_id"])
            self.invoice_lease[norm_ref(row["invoice_no"])] = lid
            if lid is None:
                continue
            self.notices.append((lid, int(row["instalment_no"]),
                                 parse_date(row["printed_due_date"]),
                                 parse_date(row["issued_on"])))

    def resolve_payment_ref(self, ref):
        lid = self.resolve_lease(ref)
        if lid is not None:
            return lid
        return self.invoice_lease.get(norm_ref(ref))

    def local_ord(self, region, secs):
        std, dst, periods = self.clock[region.lower()]
        off = std
        for a, b in periods:
            if a <= secs < b:
                off = dst
                break
        return (secs + off) // 86400 + EPOCH_ORD

    def local_to_utc(self, region, day, secs_of_day):
        std, dst, periods = self.clock[region.lower()]
        naive = (day - EPOCH_ORD) * 86400 + secs_of_day
        found = []
        for off in (std, dst):
            cand = naive - off
            cur = std
            for a, b in periods:
                if a <= cand < b:
                    cur = dst
                    break
            if cur == off:
                found.append(cand)
        if found:
            return min(found)
        return naive - std

    def _load_payments(self):
        self.payments = {}
        self.posting_by_id = {}

        def get_payment(key, kind):
            p = self.payments.get(key)
            if p is None:
                p = {
                    "key": key,
                    "kind": kind,
                    "lines": [],
                    "post": None,
                    "post_lease": None,
                    "post_lord": None,
                    "post_cents": 0,
                    "returns": [],
                }
                self.payments[key] = p
            return p

        for name in self.ledger_files:
            raws, counts = self.dedupe(
                [raw for _o, raw in read_jsonl(self.need(name))])
            nlate = 0
            ndup = 0
            for raw in raws:
                o = json.loads(raw)
                rec = parse_instant(o["posted_at"])
                if rec > self.watermark:
                    nlate += 1
                    continue
                ndup += counts[raw] - 1
                channel = str(o["channel"]).upper()
                lid = o["lease_id"] if o["lease_id"] in self.leases else \
                    self.resolve_lease(o["lease_id"])
                if channel == "LOCKBOX":
                    kind = "lockbox"
                    key = norm_ref(str(o["source_ref"]))
                elif channel == "CARD":
                    kind = "card"
                    key = norm_ref(str(o["source_ref"]))
                else:
                    kind = "ach"
                    key = o["posting_id"]
                p = get_payment(key, kind)
                p["post"] = rec
                p["post_lease"] = lid
                p["post_cents"] = int(o["amount"])
                region = self.booking.get(lid)
                p["post_lord"] = self.local_ord(region, rec) if region \
                    else rec // 86400 + EPOCH_ORD
                self.posting_by_id[o["posting_id"]] = p
            self.note_late(name, nlate)
            self.count_dup(name, ndup)

        for name, _region in LOCKBOX_FILES:
            self._load_bank_file(name, "item_id", "remit_ref", "value_date",
                                 "received_at", "lockbox", get_payment)
        self._load_bank_file("card_settlements.csv", "auth_code", "lease_ref",
                             "settlement_date", "batch_at", "card", get_payment)

        name = "ach_returns.log"
        nlate = 0
        for raw in read_lines(self.need(name)):
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            parts = raw.split()
            if len(parts) < 2 or parts[1] != "RETURN":
                continue
            rec = parse_instant(parts[0])
            fields = {}
            for tok in parts[2:]:
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    fields[k] = v
            rid = fields.get("id", "")
            if rec > self.watermark:
                nlate += 1
                continue
            p = self.posting_by_id.get(fields.get("posting", ""))
            if p is None:
                self.reject(name, rid, "unknown_posting")
                continue
            code = fields.get("code", "").upper()
            p["returns"].append((rec, bool(self.return_reverses.get(code)), code))
        self.note_late(name, nlate)

        self.pay_by_lease = defaultdict(list)
        for key in sorted(self.payments):
            p = self.payments[key]
            p["lines"].sort(key=lambda t: t[0])
            p["returns"].sort()
            cands = set()
            if p["post_lease"] is not None:
                cands.add(p["post_lease"])
            for line in p["lines"]:
                cands.add(line[3])
            for lid in sorted(cands):
                self.pay_by_lease[lid].append(p)

    def _load_bank_file(self, name, idfield, reffield, datefield, recfield,
                        kind, get_payment):
        raws, counts = self.dedupe(
            [raw for _row, raw in read_csv(self.need(name))])
        head = read_lines(self.path(name))[0].split(",")
        nlate = 0
        ndup = 0
        for raw in raws:
            row = dict(zip(head, raw.split(",")))
            rec = parse_instant(row[recfield])
            if rec > self.watermark:
                nlate += 1
                continue
            ndup += counts[raw] - 1
            rid = row[idfield]
            lid = self.resolve_payment_ref(row[reffield])
            if lid is None:
                self.reject(name, rid, "unknown_lease")
                continue
            cents = strict_cents(row["amount"])
            if cents is None:
                self.reject(name, rid, "bad_amount")
                continue
            p = get_payment(norm_ref(rid), kind)
            p["lines"].append((rec, parse_date(row[datefield]), cents, lid))
        self.note_late(name, nlate)
        self.count_dup(name, ndup)

    def _load_bureau(self):
        self.pulls = defaultdict(list)
        name = "bureau_kr.jsonl"
        nlate = 0
        for o, _raw in read_jsonl(self.need(name)):
            rec = parse_instant(o["recorded_at"])
            if rec > self.watermark:
                nlate += 1
                continue
            status = str(o["status"]).upper()
            if status == "OK":
                kind, value = "score", int(o["score"])
            elif status == "NOHIT":
                kind, value = "no_hit", None
            else:
                kind, value = "thin", None
            self.pulls[only_digits(o["tax_id"])].append(
                (parse_date(o["pulled_on"]), "KR", rec, o["pull_id"], kind, value))
        self.note_late(name, nlate)
        name = "bureau_nd.csv"
        nlate = 0
        for row, _raw in read_csv(self.need(name)):
            rec = parse_instant(row["loaded_at"])
            if rec > self.watermark:
                nlate += 1
                continue
            result = row["result"].strip().upper()
            score = row["score"].strip()
            if result == "NOHIT":
                kind, value = "no_hit", None
            elif not score:
                kind, value = "thin", None
            else:
                tenths = money_to_cents(score) // 10
                kind = "score"
                value = self.kr_floor + tenths * self.nd_num // self.nd_den
            self.pulls[only_digits(row["fein"])].append(
                (parse_date(row["pull_date"]), "ND", rec, row["pull_ref"],
                 kind, value))
        self.note_late(name, nlate)
        for v in self.pulls.values():
            v.sort()

    def _load_limits(self):
        self.limits = defaultdict(list)
        name = "credit_limits.csv"
        nlate = 0
        for row, _raw in read_csv(self.need(name)):
            rec = parse_instant(row["recorded_at"])
            if rec > self.watermark:
                nlate += 1
                continue
            oid = self.resolve_obligor(row["obligor_ref"])
            if oid is None:
                continue
            raw_k = row["limit_k"].strip()
            if not raw_k:
                continue
            self.limits[oid].append(
                (parse_date(row["effective_from"]), rec, row["limit_id"],
                 int(raw_k)))
        self.note_late(name, nlate)
        for v in self.limits.values():
            v.sort()

    # -- calendar ---------------------------------------------------------
    def _build_calendar_tables(self):
        max_months = 0
        for req in self.relief.values():
            if req["months"] > max_months:
                max_months = req["months"]
        slack = self.max_holidays * max_months + 2
        lo = min([L["start"] for L in self.leases.values()] +
                 [self.first_snapshot]) - 400
        hi = self.first_snapshot + 32 * self.step_months * self.snapshot_count \
            + self.performance_days
        for L in self.leases.values():
            y, m, _d = ord_to_ymd(L["start"])
            end = add_months_day(y, m, L["term"] + slack, 28)
            if end > hi:
                hi = end
        hi += 400
        self.cal_lo = lo
        n = hi - lo + 1
        self.cal_n = n
        self.cal_month = [0] * n
        for i in range(n):
            y, m, _d = ord_to_ymd(lo + i)
            self.cal_month[i] = y * 12 + m
        self.next_bd = {}
        self.prev_bd = {}
        for rg in self.regions:
            hol = self.holidays[rg]
            bus = bytearray(n)
            for i in range(n):
                o = lo + i
                if (o + 6) % 7 < 5 and o not in hol:
                    bus[i] = 1
            nb = [0] * n
            nxt = n - 1
            for i in range(n - 1, -1, -1):
                if bus[i]:
                    nxt = i
                nb[i] = nxt
            pb = [0] * n
            prv = 0
            for i in range(n):
                if bus[i]:
                    prv = i
                pb[i] = prv
            self.next_bd[rg] = nb
            self.prev_bd[rg] = pb

    def roll(self, o, region, conv):
        if conv == 4:
            return o
        i = o - self.cal_lo
        if conv == 0:
            return self.cal_lo + self.next_bd[region][i]
        if conv == 1:
            return self.cal_lo + self.prev_bd[region][i]
        if conv == 2:
            j = self.next_bd[region][i]
            if self.cal_month[j] != self.cal_month[i]:
                j = self.prev_bd[region][i]
            return self.cal_lo + j
        j = self.prev_bd[region][i]
        if self.cal_month[j] != self.cal_month[i]:
            j = self.next_bd[region][i]
        return self.cal_lo + j

    # -- identity ---------------------------------------------------------
    def _booking_regions(self):
        self.booking = {}
        for lid in self.lease_ids:
            rows = self.branch_rows.get(lid)
            if rows:
                self.booking[lid] = rows[0][3]

    def eff(self, inst):
        return inst if self.boundary_inclusive else inst - 1

    def tax_id_at(self, oid, inst_eff):
        fixes = self.taxid_fixes.get(oid)
        if fixes:
            best = None
            for rec, _seq, tid in fixes:
                if rec <= inst_eff:
                    best = tid
            if best is not None:
                return best
        return self.obligors[oid]["tax_id"]

    def is_public(self, tax_id, day):
        for lo, hi in self.register.get(tax_id, ()):
            if lo <= day and (hi is None or hi > day):
                return True
        return False

    def _contract_segments(self):
        wm = self.eff(self.watermark)
        self.contract_seg = {}
        for lid in self.lease_ids:
            L = self.leases[lid]
            oid = self.resolve_obligor(L["obligor_ref"])
            seg = "commercial"
            if oid is not None and self.obligors[oid]["created"] <= wm:
                if self.is_public(self.tax_id_at(oid, wm), L["start"]):
                    seg = "public"
            self.contract_seg[lid] = seg

    # -- payment holidays -------------------------------------------------
    def relief_replay(self, rid, inst_eff):
        """Return (last valid status, approved key, ignored status ids)."""
        state = None
        approved = None
        ignored = []
        for rec, sid, status in self.relief[rid]["rows"]:
            if rec > inst_eff:
                continue
            ok = False
            if state is None:
                if status == "REQUESTED":
                    state = "REQUESTED"
                    ok = True
            elif state == "REQUESTED":
                if status in ("APPROVED", "DECLINED"):
                    state = status
                    ok = True
                    if status == "APPROVED":
                        approved = (rec, sid)
            elif state == "APPROVED":
                if status == "WITHDRAWN":
                    state = status
                    ok = True
            if not ok:
                ignored.append(sid)
        return state, approved, ignored

    def governing_requests(self, lid, inst_eff):
        """Request ids governing the lease at the instant, and the rejected ones."""
        inforce = []
        for rid in self.relief_by_lease.get(lid, ()):
            state, approved, _ig = self.relief_replay(rid, inst_eff)
            if state == "APPROVED":
                inforce.append((approved[0], self.relief[rid]["request_id"], rid))
        inforce.sort()
        govern = [t[2] for t in inforce[:self.max_holidays]]
        extra = [t[2] for t in inforce[self.max_holidays:]]
        return govern, extra

    def holiday_key(self, lid, inst_eff):
        govern, _extra = self.governing_requests(lid, inst_eff)
        if not govern:
            return ()
        out = []
        for rid in govern:
            req = self.relief[rid]
            out.append((req["months"], req["first"]))
        out.sort()
        return tuple(out)

    # -- schedules --------------------------------------------------------
    def nominal(self, lid, k, shift):
        L = self.leases[lid]
        y, m, _d = ord_to_ymd(L["start"])
        if self.anchor_rule == 0 or shift == 0:
            return add_months_day(y, m, k + shift, L["anchor"])
        base = add_months_day(y, m, k, L["anchor"])
        by, bm, bd = ord_to_ymd(base)
        return add_months_day(by, bm, shift, bd)

    def schedule(self, lid, hol_key, conv=None):
        if conv is None:
            conv = self.conv[self.contract_seg[lid]]
        ck = (lid, hol_key, conv)
        got = self._sched_cache.get(ck)
        if got is not None:
            return got
        L = self.leases[lid]
        rg = self.booking[lid]
        dues = []
        for k in range(1, L["term"] + 1):
            shift = 0
            for months, first in hol_key:
                if first <= k:
                    shift += months
            if self.anchor_rule == 2 and shift:
                base = self.roll(self.nominal(lid, k, 0), rg, conv)
                by, bm, bd = ord_to_ymd(base)
                dues.append(self.roll(add_months_day(by, bm, shift, bd), rg, conv))
            else:
                dues.append(self.roll(self.nominal(lid, k, shift), rg, conv))
        dues = tuple(dues)
        self._sched_cache[ck] = dues
        return dues

    # -- conventions left to the evidence ---------------------------------
    def _fit_conventions(self):
        self._sched_cache = {}
        wm = self.eff(self.watermark)
        keys = {}
        for lid in self.lease_ids:
            keys[lid] = self.holiday_key(lid, wm)
        notices = [t for t in self.notices if t[3] <= self.notices_through]
        by_seg = defaultdict(list)
        for lid, k, printed, _issued in notices:
            by_seg[self.contract_seg[lid]].append((lid, k, printed))
        best = None
        for anchor in (0, 1, 2):
            self.anchor_rule = anchor
            self._sched_cache = {}
            total = 0
            choice = {}
            for seg in ("commercial", "public"):
                rows = by_seg.get(seg, [])
                hits = []
                for conv in (0, 2, 1, 3, 4):
                    n = 0
                    for lid, k, printed in rows:
                        dues = self.schedule(lid, keys[lid], conv)
                        if k - 1 < len(dues) and dues[k - 1] == printed:
                            n += 1
                    hits.append((n, conv))
                top = max(h[0] for h in hits)
                conv = [c for n, c in hits if n == top][0]
                choice[seg] = conv
                total += top
            if best is None or total > best[0]:
                best = (total, anchor, choice)
        self.anchor_rule = best[1]
        self.conv = dict(best[2])
        self._sched_cache = {}


# -------------------------------------------------------------------- engine

DEFAULT_FLAGS = {
    "cut_utc": False,
    "knowledge_watermark": False,
    "ignore_merges": False,
    "include_withdrawn": False,
    "zero_tolerance": False,
    "all_returns_reverse": False,
    "ignore_incidents": False,
    "public_conv_as_commercial": False,
    "no_exclusions": False,
    "swap_precedence": False,
}

STATE_PENDING = "pending"
STATE_ACTIVE = "active"
STATE_CLOSED = "closed"
STATE_CHARGED = "charged_off"

BIG_DAY = 4000000


def round_ppm(num, den):
    """num/den in parts per million, half to even."""
    num *= 1000000
    neg = (num < 0) != (den < 0)
    num = abs(num)
    den = abs(den)
    q, r = divmod(num, den)
    r2 = r * 2
    if r2 > den or (r2 == den and q % 2):
        q += 1
    return -q if neg else q


class Engine(object):
    def __init__(self, ex, flags=None):
        self.ex = ex
        f = dict(DEFAULT_FLAGS)
        if flags:
            f.update(flags)
        self.f = f
        self.wm_eff = ex.eff(ex.watermark)
        self.tol = {}
        for seg, v in ex.tolerance.items():
            self.tol[seg] = 0 if f["zero_tolerance"] else v
        self.conv = dict(ex.conv)
        if f["public_conv_as_commercial"]:
            self.conv["public"] = ex.conv["commercial"]
        self.prec = dict(ex.precedence)
        if f["swap_precedence"]:
            segs = sorted(self.prec)
            if len(segs) == 2:
                self.prec = {segs[0]: ex.precedence[segs[1]],
                             segs[1]: ex.precedence[segs[0]]}
        self.base_oid = {}
        for lid in ex.lease_ids:
            self.base_oid[lid] = ex.resolve_obligor(ex.leases[lid]["obligor_ref"])
        self._hk = {}
        self._world = {}
        self._pay = {}
        self._wm_state = {}

    # -- schedules --------------------------------------------------------
    def holiday_key(self, lid, inst_eff):
        key = (lid, inst_eff)
        v = self._hk.get(key)
        if v is None:
            v = self.ex.holiday_key(lid, inst_eff)
            self._hk[key] = v
        return v

    def dues(self, lid, inst_eff):
        ex = self.ex
        conv = self.conv[ex.contract_seg[lid]]
        return ex.schedule(lid, self.holiday_key(lid, inst_eff), conv)

    def plain_dues(self, lid):
        ex = self.ex
        return ex.schedule(lid, (), self.conv[ex.contract_seg[lid]])

    # -- lease state ------------------------------------------------------
    def replay(self, lid, day, inst_eff, invalid=None):
        evs = self.ex.lease_events.get(lid)
        if not evs:
            return STATE_PENDING, None, None
        gov = {}
        for eid, ver, rec, typ, eff in evs:
            if rec > inst_eff:
                continue
            cur = gov.get(eid)
            if cur is None or (ver, rec) > (cur[0], cur[1]):
                gov[eid] = (ver, rec, typ, eff)
        items = []
        for eid, (ver, rec, typ, eff) in gov.items():
            if typ == "VOID":
                continue
            if eff <= day:
                items.append((eff, eid, typ))
        items.sort()
        state = STATE_PENDING
        closed_on = None
        charged_on = None
        for eff, eid, typ in items:
            if typ == "ACTIVATE":
                if state == STATE_PENDING:
                    state = STATE_ACTIVE
                    continue
            elif typ in ("BUYOUT", "PAYOFF"):
                if state == STATE_ACTIVE:
                    state = STATE_CLOSED
                    closed_on = eff
                    continue
            elif typ == "CHARGE_OFF":
                if state == STATE_ACTIVE:
                    state = STATE_CHARGED
                    charged_on = eff
                    continue
            if invalid is not None:
                invalid.append(eid)
        return state, closed_on, charged_on

    def wm_state(self, lid):
        got = self._wm_state.get(lid)
        if got is None:
            got = self.replay(lid, BIG_DAY, self.wm_eff)
            self._wm_state[lid] = got
        return got

    # -- obligors ---------------------------------------------------------
    def survivor(self, oid, day, inst_eff, cache):
        if self.f["ignore_merges"]:
            return oid
        got = cache.get(oid)
        if got is not None:
            return got
        ex = self.ex
        seen = set()
        cur = oid
        while True:
            events = ex.merges.get(cur)
            if not events:
                break
            best = None
            for eff, rec, seq, into in events:
                if eff <= day and rec <= inst_eff:
                    key = (eff, rec, seq)
                    if best is None or key > best[0]:
                        best = (key, into)
            if best is None:
                break
            nxt = ex.resolve_obligor(best[1])
            if nxt is None or nxt == cur or nxt in seen:
                break
            seen.add(cur)
            cur = nxt
        cache[oid] = cur
        return cur

    def world(self, asof, inst_eff):
        key = (asof, inst_eff)
        got = self._world.get(key)
        if got is not None:
            return got
        ex = self.ex
        states = {}
        surv = {}
        groups = {}
        cache = {}
        for lid in ex.lease_ids:
            state, _c, _o = self.replay(lid, asof, inst_eff)
            states[lid] = state
            oid = self.base_oid[lid]
            if oid is not None and ex.obligors[oid]["created"] <= inst_eff:
                s = self.survivor(oid, asof, inst_eff, cache)
            else:
                oid = None
                s = None
            surv[lid] = (oid, s)
            if s is not None:
                g = groups.get(s)
                if g is None:
                    g = groups[s] = [0, 0, []]
                g[2].append(lid)
                if state == STATE_ACTIVE:
                    g[0] += 1
                elif state == STATE_CHARGED:
                    g[1] += 1
        got = (states, surv, groups)
        self._world[key] = got
        return got

    # -- payments ---------------------------------------------------------
    def payment_state(self, p, inst_eff, apply_returns=True):
        gl = None
        for t in p["lines"]:
            if t[0] <= inst_eff:
                gl = t
            else:
                break
        post = p["post"]
        post_known = post is not None and post <= inst_eff
        if gl is None and not post_known:
            return None
        if apply_returns and post_known and p["returns"]:
            every = self.f["all_returns_reverse"]
            for rrec, rev, _code in p["returns"]:
                if rrec <= inst_eff and (rev or every):
                    return None
        lease = p["post_lease"] if post_known else gl[3]
        kind = p["kind"]
        if kind == "lockbox":
            if gl is not None:
                return (lease, gl[1], gl[2])
            return (lease, p["post_lord"], p["post_cents"])
        if kind == "card":
            vord = gl[1] if gl is not None else p["post_lord"]
            cents = p["post_cents"] if post_known else gl[2] - self.ex.surcharge
            return (lease, vord, cents)
        return (lease, p["post_lord"], p["post_cents"])

    def pay_series(self, lid, inst_eff):
        key = (lid, inst_eff)
        got = self._pay.get(key)
        if got is not None:
            return got
        items = []
        for p in self.ex.pay_by_lease.get(lid, ()):
            st = self.payment_state(p, inst_eff)
            if st is None or st[0] != lid:
                continue
            items.append((st[1], st[2]))
        items.sort()
        ords = []
        cum = []
        total = 0
        for vord, cents in items:
            total += cents
            ords.append(vord)
            cum.append(total)
        got = (ords, cum)
        self._pay[key] = got
        return got

    # -- days past due ----------------------------------------------------
    @staticmethod
    def dpd_on(day, dues, ords, cum, inst_cents, tol, term):
        i = bisect_right(ords, day)
        paid = cum[i - 1] if i else 0
        k0 = (paid + tol) // inst_cents + 1
        if k0 > term:
            return 0
        due = dues[k0 - 1]
        return day - due if due < day else 0

    def worst_dpd(self, lo, hi, dues, ords, cum, inst_cents, tol, term):
        if hi < lo:
            return 0
        best = self.dpd_on(hi, dues, ords, cum, inst_cents, tol, term)
        for v in ords:
            d = v - 1
            if lo <= d < hi:
                x = self.dpd_on(d, dues, ords, cum, inst_cents, tol, term)
                if x > best:
                    best = x
        return best

    # -- characteristics --------------------------------------------------
    def bureau_value(self, tax_id, asof, inst_eff, seg):
        ex = self.ex
        pulls = ex.pulls.get(tax_id)
        if not pulls:
            return None
        prec = self.prec.get(seg, [])
        nprec = len(prec)
        oldest = asof - ex.max_age_days
        best = None
        for pord, vendor, rec, pid, kind, value in pulls:
            if pord < oldest:
                continue
            if pord > asof or rec > inst_eff:
                continue
            seen = ex.disputes.get((vendor, pid))
            if seen is not None and seen <= inst_eff:
                continue
            rank = prec.index(vendor) if vendor in prec else nprec
            key = (pord, -rank, rec, pid)
            if best is None or key > best[0]:
                best = (key, kind, value)
        if best is None:
            return None
        return (best[1], best[2])

    def sector_of(self, oid, asof, inst_eff):
        best = None
        for eff, rec, seq, code in self.ex.sectors.get(oid, ()):
            if eff <= asof and rec <= inst_eff:
                key = (eff, rec, seq)
                if best is None or key > best[0]:
                    best = (key, code)
        return best[1] if best else None

    def limit_of(self, oid, asof, inst_eff):
        best = None
        for eff, rec, rid, k in self.ex.limits.get(oid, ()):
            if eff <= asof and rec <= inst_eff:
                key = (eff, rec, rid)
                if best is None or key > best[0]:
                    best = (key, k)
        return best[1] if best else None

    @staticmethod
    def pick_bin(bins, value):
        for lo, hi, label, pts in bins:
            if lo <= value and (hi is None or value < hi):
                return label, pts
        lowest = min(bins, key=lambda b: b[0])
        if value < lowest[0]:
            return lowest[2], lowest[3]
        highest = max(bins, key=lambda b: b[0])
        return highest[2], highest[3]

    # -- audit at the watermark -------------------------------------------
    def all_rejects(self):
        ex = self.ex
        out = set(ex.rejects)
        for lid in ex.lease_ids:
            invalid = []
            self.replay(lid, BIG_DAY, self.wm_eff, invalid)
            for eid in invalid:
                out.add(("lease_events.jsonl", eid, "invalid_transition"))
        for rid in sorted(ex.relief):
            _state, _appr, ignored = ex.relief_replay(rid, self.wm_eff)
            for sid in ignored:
                out.add(("relief_approvals.csv", sid, "invalid_transition"))
        for lid in sorted(ex.relief_by_lease):
            _gov, extra = ex.governing_requests(lid, self.wm_eff)
            for rid in extra:
                out.add(("relief_approvals.csv", ex.relief[rid]["request_id"],
                         "holiday_limit"))
        return out

    def holiday_entries(self):
        ex = self.ex
        rows = []
        for lid in sorted(ex.relief_by_lease):
            gov, _extra = ex.governing_requests(lid, self.wm_eff)
            for rid in gov:
                req = ex.relief[rid]
                rows.append({
                    "request_id": req["request_id"],
                    "lease_id": req["lease_id"],
                    "months": req["months"],
                    "first_deferred_instalment": req["first"],
                })
        rows.sort(key=lambda r: r["request_id"])
        return rows

    def merge_entries(self):
        ex = self.ex
        out = []
        for oid in sorted(ex.merges):
            cur = oid
            seen = set()
            while True:
                events = ex.merges.get(cur)
                if not events:
                    break
                best = None
                for eff, rec, seq, into in events:
                    key = (eff, rec, seq)
                    if best is None or key > best[0]:
                        best = (key, into)
                nxt = ex.resolve_obligor(best[1])
                if nxt is None or nxt == cur or nxt in seen:
                    break
                seen.add(cur)
                cur = nxt
            out.append({"obligor_id": oid, "resolved_to": cur})
        return out

    def payment_counts(self):
        ex = self.ex
        counts = {"lockbox": 0, "card": 0, "ach": 0, "reversed": 0}
        every = self.f["all_returns_reverse"]
        for key in sorted(ex.payments):
            p = ex.payments[key]
            st = self.payment_state(p, self.wm_eff, apply_returns=False)
            if st is None or st[0] is None:
                continue
            counts[p["kind"]] = counts.get(p["kind"], 0) + 1
            post = p["post"]
            if post is not None and post <= self.wm_eff:
                for rrec, rev, _code in p["returns"]:
                    if rrec <= self.wm_eff and (rev or every):
                        counts["reversed"] += 1
                        break
        return counts

    # -- the backtest -----------------------------------------------------
    def snapshot_dates(self):
        ex = self.ex
        y, m, d = ord_to_ymd(ex.first_snapshot)
        return [add_months_day(y, m, i * ex.step_months, d)
                for i in range(ex.snapshot_count)]

    def cut_instant(self, snap, region):
        if self.f["cut_utc"]:
            return (snap - EPOCH_ORD) * 86400 + self.ex.cut_secs
        return self.ex.local_to_utc(region, snap, self.ex.cut_secs)

    def version_for(self, snap):
        best = None
        for v in self.ex.versions:
            ok = v["status"] == "released" or (
                self.f["include_withdrawn"] and v["status"] == "withdrawn")
            if not ok or v["effective_from"] > snap:
                continue
            if best is None or v["effective_from"] >= best["effective_from"]:
                best = v
        if best is None:
            fail("no scorecard version is effective at %s" % fmt_date(snap))
        return best["version"]

    def branch_region(self, lid, asof, inst_eff):
        best = None
        for eff, rec, rid, region in self.ex.branch_rows.get(lid, ()):
            if eff <= asof and rec <= inst_eff:
                key = (eff, rec, rid)
                if best is None or key > best[0]:
                    best = (key, region)
        return best[1] if best else None

    def exposure(self, group, states, asof, inst_eff):
        total = 0
        for lid in group[2]:
            if states[lid] != STATE_ACTIVE:
                continue
            dues = self.dues(lid, inst_eff)
            total += self.ex.leases[lid]["instalment"] * (
                len(dues) - bisect_right(dues, asof))
        return total

    def deferral_span(self, lid, inst_eff):
        hol = self.holiday_key(lid, inst_eff)
        if not hol:
            return None
        first = min(f for _m, f in hol)
        dues = self.dues(lid, inst_eff)
        if first < 1 or first > len(dues):
            return None
        plain = self.plain_dues(lid)
        return (plain[first - 1], dues[first - 1])

    def observe(self):
        ex = self.ex
        snaps = self.snapshot_dates()
        by_booking = defaultdict(list)
        for lid in ex.lease_ids:
            region = ex.booking.get(lid)
            if region is not None:
                by_booking[region].append(lid)
        obs = []
        unresolved = []
        candidates = 0
        cut_instants = {}
        expo_cache = {}
        for snap in snaps:
            asof = snap - 1
            window_end = asof + ex.performance_days
            mature = window_end <= ex.data_cutoff
            version = self.version_for(snap)
            card = ex.cards[version]
            chars = card["chars"]
            cuts = {}
            for region in ex.regions:
                cuts[region] = self.cut_instant(snap, region)
            cut_instants[snap] = cuts
            for region in ex.regions:
                inst = cuts[region]
                inst_eval = ex.watermark if self.f["knowledge_watermark"] else inst
                eff = ex.eff(inst_eval)
                states, surv, groups = self.world(asof, eff)
                qbase = []
                if not self.f["ignore_incidents"]:
                    for src, regions, a, b in ex.incidents:
                        if a <= inst < b:
                            qbase.append((src, regions))
                for lid in by_booking[region]:
                    if states[lid] != STATE_ACTIVE:
                        continue
                    candidates += 1
                    rg = self.branch_region(lid, asof, eff)
                    if rg is None:
                        unresolved.append((snap, lid, "no_branch"))
                        continue
                    base, s = surv[lid]
                    if base is None:
                        unresolved.append((snap, lid, "unknown_obligor"))
                        continue
                    L = ex.leases[lid]
                    tax = ex.tax_id_at(s, eff)
                    seg = "public" if ex.is_public(tax, asof) else "commercial"
                    qsrc = set()
                    for src, regions in qbase:
                        if rg in regions:
                            qsrc.add(src)
                    group = groups[s]
                    tolv = self.tol[ex.contract_seg[lid]]
                    cents = L["instalment"]
                    term = L["term"]
                    dues = None
                    ords = None
                    cum = None
                    bins = {}
                    score = card["base"][seg]
                    for c in chars:
                        name = c["name"]
                        if qsrc and (ex.char_sources.get(name) or ()) and \
                                qsrc & ex.char_sources[name]:
                            label = "quarantined"
                            pts = c["special"]["quarantined"]
                        elif name == "dpd_now" or name == "max_dpd_12m" or \
                                name == "recent_worst":
                            if dues is None:
                                dues = self.dues(lid, eff)
                                ords, cum = self.pay_series(lid, eff)
                            if name == "dpd_now":
                                value = self.dpd_on(asof, dues, ords, cum,
                                                    cents, tolv, term)
                            elif name == "max_dpd_12m":
                                value = self.worst_dpd(asof - 364, asof, dues,
                                                       ords, cum, cents, tolv,
                                                       term)
                            else:
                                value = self.worst_dpd(asof - 89, asof, dues,
                                                       ords, cum, cents, tolv,
                                                       term)
                            label, pts = self.pick_bin(c["bins"], value)
                        elif name == "months_on_book":
                            y1, m1, d1 = ord_to_ymd(L["start"])
                            y2, m2, d2 = ord_to_ymd(asof)
                            value = (y2 - y1) * 12 + (m2 - m1)
                            if d2 < d1:
                                value -= 1
                            label, pts = self.pick_bin(c["bins"], value)
                        elif name == "active_leases":
                            label, pts = self.pick_bin(c["bins"], group[0])
                        elif name == "utilisation":
                            limit_k = self.limit_of(s, asof, eff)
                            if limit_k is None:
                                label = "missing"
                                pts = c["special"]["missing"]
                            elif limit_k == 0:
                                label = "zero_limit"
                                pts = c["special"]["zero_limit"]
                            else:
                                ck = (asof, eff, s)
                                total = expo_cache.get(ck)
                                if total is None:
                                    total = self.exposure(group, states, asof, eff)
                                    expo_cache[ck] = total
                                value = total * 1000 // (limit_k * 100000)
                                label, pts = self.pick_bin(c["bins"], value)
                        elif name == "bureau":
                            got = self.bureau_value(tax, asof, eff, seg)
                            if got is None:
                                label = "missing"
                                pts = c["special"]["missing"]
                            elif got[0] == "score":
                                label, pts = self.pick_bin(c["bins"], got[1])
                            else:
                                label = got[0]
                                pts = c["special"][got[0]]
                        elif name == "sector_class":
                            code = self.sector_of(s, asof, eff)
                            cls = ex.sector_class.get(code) if code else None
                            if cls is None:
                                label = "missing"
                                pts = c["special"]["missing"]
                            else:
                                label = cls
                                pts = c["categories"][cls]
                        else:
                            fail("unknown characteristic %s" % name)
                        bins[name] = label
                        score += pts
                    exclusion = None
                    if not self.f["no_exclusions"]:
                        for reason in ex.exclusion_order:
                            if reason == "prior_charge_off":
                                if group[1] > 0:
                                    exclusion = reason
                                    break
                            elif reason == "holiday_active":
                                span = self.deferral_span(lid, eff)
                                if span and span[0] <= asof < span[1]:
                                    exclusion = reason
                                    break
                    if not mature:
                        label_out = "immature"
                    else:
                        _st, closed, charged = self.wm_state(lid)
                        if charged is not None and charged <= window_end:
                            label_out = "bad"
                        else:
                            last = closed if (closed is not None and
                                              closed <= window_end) else window_end
                            wd = self.dues(lid, self.wm_eff)
                            wo, wc = self.pay_series(lid, self.wm_eff)
                            worst = self.worst_dpd(asof + 1, last, wd, wo, wc,
                                                   cents, tolv, term)
                            if worst >= ex.bad_dpd:
                                label_out = "bad"
                            elif closed is not None and closed <= window_end:
                                label_out = "indeterminate"
                            else:
                                label_out = "good"
                    obs.append({
                        "lease_id": lid,
                        "snapshot": fmt_date(snap),
                        "obligor_id": s,
                        "segment": seg,
                        "scorecard": version,
                        "bins": bins,
                        "score": score,
                        "approved": score >= card["cutoff"][seg],
                        "exclusion": exclusion,
                        "label": label_out,
                        "_region": rg,
                        "_snap": snap,
                    })
        obs.sort(key=lambda o: (o["_snap"], o["lease_id"]))
        unresolved.sort()
        return {
            "snapshots": snaps,
            "observations": obs,
            "unresolved": unresolved,
            "candidates": candidates,
            "cut_instants": cut_instants,
        }


# ------------------------------------------------------------------- reports

SEGMENTS = ("commercial", "public")
OBS_KEYS = ("approved", "bins", "exclusion", "label", "lease_id", "obligor_id",
            "score", "scorecard", "segment", "snapshot")


def totals_of(items):
    t = {"observations": len(items), "excluded": 0, "bad": 0, "good": 0,
         "indeterminate": 0, "immature": 0, "approved": 0}
    for o in items:
        if o["exclusion"] is not None:
            t["excluded"] += 1
        t[o["label"]] += 1
        if o["approved"]:
            t["approved"] += 1
    return t


def metrics_of(items):
    gc = {}
    bc = {}
    nb = 0
    ng = 0
    appr = 0
    appr_bad = 0
    for o in items:
        if o["exclusion"] is not None:
            continue
        lab = o["label"]
        if lab != "bad" and lab != "good":
            continue
        s = o["score"]
        if lab == "bad":
            bc[s] = bc.get(s, 0) + 1
            nb += 1
            if o["approved"]:
                appr_bad += 1
        else:
            gc[s] = gc.get(s, 0) + 1
            ng += 1
        if o["approved"]:
            appr += 1
    n = nb + ng
    out = {"population": n, "bad": nb, "good": ng, "approved": appr,
           "approved_bad": appr_bad, "auc_ppm": None, "ks_ppm": None,
           "bad_rate_ppm": None}
    if n:
        out["bad_rate_ppm"] = round_ppm(nb, n)
    if nb and ng:
        scores = sorted(set(gc) | set(bc))
        below = 0
        num2 = 0
        for s in scores:
            g = gc.get(s, 0)
            b = bc.get(s, 0)
            if g:
                num2 += g * (2 * below + b)
            below += b
        out["auc_ppm"] = round_ppm(num2, 2 * ng * nb)
        cb = 0
        cg = 0
        best = 0
        for s in scores:
            cb += bc.get(s, 0)
            cg += gc.get(s, 0)
            d = cb * ng - cg * nb
            if d < 0:
                d = -d
            if d > best:
                best = d
        out["ks_ppm"] = round_ppm(best, nb * ng)
    return out


def public_obs(o):
    return dict((k, o[k]) for k in OBS_KEYS)


def build_reports(ex, eng, res):
    obs = res["observations"]
    snaps = res["snapshots"]
    snap_strs = [fmt_date(s) for s in snaps]
    by_region = defaultdict(list)
    by_segment = defaultdict(list)
    by_snap = defaultdict(list)
    by_seg_snap = defaultdict(list)
    by_seg_card = {}
    usage = {}
    for sg in SEGMENTS:
        by_seg_card[sg] = {}
    for o in obs:
        by_region[o["_region"]].append(o)
        by_segment[o["segment"]].append(o)
        by_snap[o["snapshot"]].append(o)
        by_seg_snap[(o["segment"], o["snapshot"])].append(o)
        d = by_seg_card.setdefault(o["segment"], {})
        d[o["scorecard"]] = d.get(o["scorecard"], 0) + 1
        key = (o["snapshot"], o["scorecard"])
        usage[key] = usage.get(key, 0) + 1

    reports = {}
    bands = []
    for band, lo, hi in ex.bands:
        n = 0
        nb = 0
        ng = 0
        for o in obs:
            if lo <= o["score"] < hi:
                n += 1
                if o["label"] == "bad":
                    nb += 1
                elif o["label"] == "good":
                    ng += 1
        bands.append({"band": band, "observations": n, "bad": nb, "good": ng})
    summary = {
        "run_id": ex.run_id,
        "snapshots": snap_strs,
        "totals": totals_of(obs),
        "metrics": metrics_of(obs),
        "by_region": dict((rg, totals_of(by_region.get(rg, [])))
                          for rg in ex.regions),
        "by_segment": dict((sg, totals_of(by_segment.get(sg, [])))
                           for sg in SEGMENTS),
        "by_snapshot": [
            {"snapshot": s,
             "totals": totals_of(by_snap.get(s, [])),
             "auc_ppm": metrics_of(by_snap.get(s, []))["auc_ppm"]}
            for s in snap_strs],
        "score_bands": bands,
    }
    reports["summary.json"] = summary

    for rg in ex.regions:
        items = by_region.get(rg, [])
        reports["region_%s.json" % rg] = {
            "region": rg,
            "totals": totals_of(items),
            "metrics": metrics_of(items),
            "observations": [public_obs(o) for o in items],
        }
    for sg in SEGMENTS:
        items = by_segment.get(sg, [])
        reports["segment_%s.json" % sg] = {
            "segment": sg,
            "totals": totals_of(items),
            "metrics": metrics_of(items),
            "by_snapshot": [
                {"snapshot": s,
                 "totals": totals_of(by_seg_snap.get((sg, s), [])),
                 "metrics": metrics_of(by_seg_snap.get((sg, s), []))}
                for s in snap_strs],
            "by_scorecard": dict(
                (v, n) for v, n in sorted(by_seg_card.get(sg, {}).items()) if n),
        }

    cut = {}
    for snap in snaps:
        cut[fmt_date(snap)] = dict(
            (rg, fmt_instant(res["cut_instants"][snap][rg])) for rg in ex.regions)
    quarantined = []
    exclusions = []
    for o in obs:
        if o["exclusion"] is not None:
            exclusions.append({"lease_id": o["lease_id"],
                               "snapshot": o["snapshot"],
                               "reason": o["exclusion"]})
        names = sorted(k for k, v in o["bins"].items() if v == "quarantined")
        if names:
            quarantined.append({"lease_id": o["lease_id"],
                                "snapshot": o["snapshot"],
                                "characteristics": names})
    policy = {
        "cut_instants": cut,
        "scorecard_usage": [
            {"snapshot": s, "version": v, "observations": usage[(s, v)]}
            for s, v in sorted(usage)],
        "exclusions": exclusions,
        "quarantined": quarantined,
        "holidays": eng.holiday_entries(),
        "merges": eng.merge_entries(),
    }
    reports["policy_audit.json"] = policy

    rejects = [{"source": a, "record_id": b, "reason": c}
               for a, b, c in sorted(eng.all_rejects())]
    unresolved = [{"lease_id": lid, "snapshot": fmt_date(snap), "reason": why}
                  for snap, lid, why in res["unresolved"]]
    regions_sum = sum(len(by_region.get(rg, [])) for rg in ex.regions)
    segments_sum = sum(len(by_segment.get(sg, [])) for sg in SEGMENTS)
    snaps_sum = sum(len(by_snap.get(s, [])) for s in snap_strs)
    quality = {
        "rejects": rejects,
        "duplicates": dict(sorted(ex.duplicates.items())),
        "late_records": dict(sorted(ex.late.items())),
        "unresolved": unresolved,
        "partition": {"candidates": res["candidates"],
                      "scored": len(obs),
                      "unresolved": len(res["unresolved"])},
        "payments": eng.payment_counts(),
        "identity_check": {
            "regions_minus_summary": regions_sum - len(obs),
            "segments_minus_summary": segments_sum - len(obs),
            "snapshots_minus_summary": snaps_sum - len(obs),
        },
    }
    reports["data_quality.json"] = quality
    return reports


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    if not os.path.isdir(data_dir):
        fail("no such data directory: %s" % data_dir)
    ex = Extract(data_dir)
    eng = Engine(ex)
    res = eng.observe()
    reports = build_reports(ex, eng, res)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    for name in sorted(reports):
        text = json.dumps(reports[name], sort_keys=True, indent=2) + "\n"
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
