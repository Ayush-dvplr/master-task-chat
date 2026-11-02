#!/usr/bin/env python3
"""Point-in-time backtest of the Halvard champion lease scorecard.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
Reads one backtest extract and writes the nine reports. Standard library only.
"""
import configparser
import json
import re
import sys
import tomllib
from bisect import bisect_right
from datetime import date, datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path

UTC = timezone.utc
REGIONS = ("North", "South", "West", "East")
SEGMENTS = ("commercial", "public")
REPORTS = ("summary.json", "policy_audit.json", "data_quality.json", "region_North.json", "region_South.json",
           "region_West.json", "region_East.json", "segment_commercial.json", "segment_public.json")
REQUIRED = ("backtest_run.toml", "region_clock.ini", "branches.ini", "holiday_calendar.ics", "scorecard_registry.json",
            "feature_lineage.yaml", "data_incidents.json", "return_codes.ini", "servicing_policy.ini",
            "exclusion_policy.yaml", "bureau_vendors.ini", "sector_reference.json", "bureau_disputes.json",
            "score_bands.yaml", "leases.csv", "lease_branch_history.csv", "obligors.csv", "obligor_events.jsonl",
            "public_entity_register.csv", "lease_events.jsonl", "relief_approvals.csv", "lockbox_north.csv",
            "lockbox_south.csv", "lockbox_west.csv", "lockbox_east.csv", "card_settlements.csv", "ach_returns.log",
            "bureau_kr.jsonl", "bureau_nd.csv", "credit_limits.csv", "invoice_notices.csv", "snapshot_runs.log")


def ts(s):
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    t = datetime.fromisoformat(s.replace(" ", "T"))
    if t.tzinfo is None:
        t = t.replace(tzinfo=UTC)
    return t.astimezone(UTC)


def iso(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_csv(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    head = lines[0].split(",")
    out = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        out.append((ln, dict(zip(head, ln.split(",")))))
    return out


def read_jsonl(path):
    out = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            out.append((ln, json.loads(ln)))
    return out


def mini_yaml_lists(text):
    """Parse the small yaml files: 'key: [a, b]' maps and '- {k: v}' / '- reason: x' lists."""
    sections = {}
    cur = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if not line.startswith(" ") and line.endswith(":"):
            cur = line[:-1].strip()
            sections[cur] = []
            continue
        sections.setdefault(cur, []).append(line.strip())
    return sections


def month_add(y, m, k):
    i = y * 12 + (m - 1) + k
    return i // 12, i % 12 + 1


def dim(y, m):
    return 31 if m == 12 else (date(y, m + 1, 1) - date(y, m, 1)).days


def ppm(fr):
    return None if fr is None else round(fr * 1000000)


class Extract:
    def __init__(self, data, variant=None):
        self.data = Path(data)
        self.v = variant or {}
        for name in REQUIRED:
            if not (self.data / name).is_file():
                raise SystemExit("missing input file: %s" % name)
        self.ledger_files = sorted(p for p in self.data.glob("servicing_ledger_*.jsonl"))
        years = set(int(p.stem.rsplit("_", 1)[1]) for p in self.ledger_files)
        run = tomllib.loads((self.data / "backtest_run.toml").read_text(encoding="utf-8"))["run"]
        first = min(date.fromisoformat(r["start_date"]).year for _raw, r in read_csv(self.data / "leases.csv"))
        need = set(range(first, date.fromisoformat(run["data_cutoff"]).year + 1))
        if not need <= years:
            raise SystemExit("missing servicing ledger year: %s" % sorted(need - years))
        self.late = {}
        self.dups = {}
        self._sched = {}
        self._state = {}
        self._groups = {}
        self._final = {}
        self.rejects = []
        self.load_config()
        self.load_identity()
        self.load_leases()
        self.load_cash()
        self.load_bureau_limits()

    # ------------------------------------------------------------------ helpers
    def admit(self, fname, t):
        if t > self.watermark:
            self.late[fname] = self.late.get(fname, 0) + 1
            return False
        return True

    def dedupe(self, fname, rows):
        seen = set()
        out = []
        for raw, rec in rows:
            if raw in seen:
                self.dups[fname] = self.dups.get(fname, 0) + 1
                continue
            seen.add(raw)
            out.append(rec)
        return out

    def known(self, t, K):
        if self.v.get("exclusive_cut"):
            return t < K
        return t <= K

    # ------------------------------------------------------------------ config
    def load_config(self):
        d = self.data
        run = tomllib.loads((d / "backtest_run.toml").read_text(encoding="utf-8"))["run"]
        self.run_id = run["run_id"]
        fs = date.fromisoformat(run["first_snapshot"])
        self.snapshots = []
        for i in range(int(run["snapshot_count"])):
            y, m = month_add(fs.year, fs.month, i * int(run["snapshot_step_months"]))
            self.snapshots.append(date(y, m, min(fs.day, dim(y, m))))
        self.perf = int(run["performance_days"])
        self.bad_dpd = int(run["bad_dpd"])
        self.cutoff = date.fromisoformat(run["data_cutoff"])
        self.watermark = ts(run["watermark_utc"])
        hh, mm, ss = (int(x) for x in run["cut_local_time"].split(":"))
        cp = configparser.ConfigParser()
        cp.read_string((d / "region_clock.ini").read_text(encoding="utf-8"))
        self.clock = {}
        for r in REGIONS:
            sec = cp[r.lower()]
            periods = []
            for part in sec.get("daylight_periods", "").split(","):
                part = part.strip()
                if part:
                    a, b = part.split("/")
                    periods.append((ts(a), ts(b)))
            self.clock[r] = (int(sec["standard_offset"]), int(sec["daylight_offset"]), periods)
        self.cuts = {}
        for s in self.snapshots:
            for r in REGIONS:
                if self.v.get("cut_utc"):
                    self.cuts[(s, r)] = datetime(s.year, s.month, s.day, hh, mm, ss, tzinfo=UTC)
                else:
                    self.cuts[(s, r)] = self.local_to_utc(r, datetime(s.year, s.month, s.day, hh, mm, ss))
        bp = configparser.ConfigParser()
        bp.optionxform = str
        bp.read_string((d / "branches.ini").read_text(encoding="utf-8"))
        self.branch_region = {k.upper(): v for k, v in bp["branches"].items()}
        self.branch_alias = {k.upper(): v.upper() for k, v in bp["aliases"].items()}
        # holidays
        self.holidays = {r: set() for r in REGIONS}
        for block in (d / "holiday_calendar.ics").read_text(encoding="utf-8").split("BEGIN:VEVENT")[1:]:
            props = {}
            for ln in block.splitlines():
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    props[k.split(";")[0].strip()] = v.strip()
            if props.get("STATUS", "CONFIRMED") != "CONFIRMED":
                continue
            ds = props["DTSTART"]
            de = props.get("DTEND")
            day = date(int(ds[:4]), int(ds[4:6]), int(ds[6:8]))
            end = date(int(de[:4]), int(de[4:6]), int(de[6:8])) if de else day + timedelta(days=1)
            for reg in props.get("CATEGORIES", "").split(","):
                reg = reg.strip()
                if reg in self.holidays:
                    x = day
                    while x < end:
                        self.holidays[reg].add(x)
                        x += timedelta(days=1)
        sp = configparser.ConfigParser()
        sp.read_string((d / "servicing_policy.ini").read_text(encoding="utf-8"))
        self.tol = {"commercial": int(sp["tolerance"]["commercial_cents"]), "public": int(sp["tolerance"]["public_cents"])}
        if self.v.get("tol_zero"):
            self.tol = {"commercial": 0, "public": 0}
        self.surcharge = int(sp["card"]["surcharge_cents"])
        self.max_holidays = int(sp["relief"]["max_holidays_per_lease"])
        rc = configparser.ConfigParser()
        rc.optionxform = str
        rc.read_string((d / "return_codes.ini").read_text(encoding="utf-8"))
        self.reverses = {k.upper(): v.strip().lower() == "yes" for k, v in rc["codes"].items()}
        if self.v.get("all_returns"):
            self.reverses = {k: True for k in self.reverses}
        bv = configparser.ConfigParser()
        bv.read_string((d / "bureau_vendors.ini").read_text(encoding="utf-8"))
        self.bureau_age = int(bv["general"]["max_age_days"])
        self.vendor_order = {s: [x.strip() for x in bv["precedence"][s].split(",")] for s in SEGMENTS}
        if self.v.get("bureau_reversed"):
            self.vendor_order = {s: list(reversed(o)) for s, o in self.vendor_order.items()}
        self.nd_num = int(bv["ND"]["to_kr_numerator"])
        self.nd_den = int(bv["ND"]["to_kr_denominator"])
        self.sector_class = json.loads((d / "sector_reference.json").read_text(encoding="utf-8"))["sectors"]
        ex = mini_yaml_lists((d / "exclusion_policy.yaml").read_text(encoding="utf-8"))
        self.exclusion_order = [ln.split(":", 1)[1].strip() for ln in ex.get("exclusions", []) if ln.startswith("- reason:")]
        lin = mini_yaml_lists((d / "feature_lineage.yaml").read_text(encoding="utf-8"))
        self.nodes = {}
        for sec in ("nodes", "characteristics"):
            for ln in lin.get(sec, []):
                k, v = ln.split(":", 1)
                self.nodes[k.strip()] = [x.strip() for x in v.strip().strip("[]").split(",") if x.strip()]
        self.bands = []
        for ln in mini_yaml_lists((d / "score_bands.yaml").read_text(encoding="utf-8")).get("bands", []):
            body = ln.lstrip("- ").strip().strip("{}")
            kv = dict((p.split(":", 1)[0].strip(), p.split(":", 1)[1].strip()) for p in body.split(","))
            self.bands.append((kv["band"], int(kv["lo"]), int(kv["hi"])))
        reg = json.loads((d / "scorecard_registry.json").read_text(encoding="utf-8"))["versions"]
        for x in reg:
            if not (d / x["file"]).is_file():
                raise SystemExit("missing input file: %s" % x["file"])
        self.versions = []
        for x in reg:
            if x["status"] != "released" and not self.v.get("honor_withdrawn"):
                continue
            card = json.loads((d / x["file"]).read_text(encoding="utf-8"))
            self.versions.append((date.fromisoformat(x["effective_from"]), x["version"], card))
        self.versions.sort(key=lambda t: (t[0], t[1]))
        inc = json.loads((d / "data_incidents.json").read_text(encoding="utf-8"))["incidents"]
        self.incidents = [] if self.v.get("no_incidents") else [
            (ts(x["from_utc"]), ts(x["to_utc"]), x["source"], set(x["regions"])) for x in inc if x["status"] == "confirmed"]
        self.disputes = [(x["pull_id"], ts(x["recorded_at"])) for x in
                         json.loads((d / "bureau_disputes.json").read_text(encoding="utf-8"))["disputes"]]

    def offset(self, r, t):
        std, dst, periods = self.clock[r]
        for a, b in periods:
            if a <= t < b:
                return dst
        return std

    def local_to_utc(self, r, naive):
        base = naive.replace(tzinfo=UTC)
        std = self.clock[r][0]
        t = base - timedelta(minutes=std)
        off = self.offset(r, t)
        t = base - timedelta(minutes=off)
        if self.offset(r, t) != off:
            t = base - timedelta(minutes=self.offset(r, t))
        return t

    def local_date(self, r, t):
        if self.v.get("utc_value_date"):
            return t.date()
        return (t + timedelta(minutes=self.offset(r, t))).date()

    def is_bd(self, r, d):
        return d.weekday() < 5 and d not in self.holidays[r]

    # ------------------------------------------------------------------ identity
    @staticmethod
    def norm_lease(ref):
        x = re.sub(r"[\s\-_]", "", ref).upper()
        m = re.fullmatch(r"HL0*(\d+)", x)
        return "HL-%06d" % int(m.group(1)) if m else None

    @staticmethod
    def norm_obl(ref):
        x = re.sub(r"[\s\-_]", "", ref).upper()
        m = re.fullmatch(r"OB0*(\d+)", x)
        return "OB-%05d" % int(m.group(1)) if m else None

    @staticmethod
    def norm_tax(t):
        x = re.sub(r"\D", "", t)
        return x if len(x) == 9 else None

    def norm_branch(self, code):
        x = re.sub(r"[\s\-_]", "", code).upper()
        if x in self.branch_region:
            return self.branch_region[x]
        if x in self.branch_alias:
            return self.branch_region[self.branch_alias[x]]
        return None

    def load_identity(self):
        d = self.data
        self.obligors = {}
        for raw, r in read_csv(d / "obligors.csv"):
            t = ts(r["created_at"])
            if not self.admit("obligors.csv", t):
                continue
            self.obligors[self.norm_obl(r["obligor_id"])] = {"tax": self.norm_tax(r["tax_id"]), "created": t}
        self.oev = {}
        self.merges = {}
        for rec in self.dedupe("obligor_events.jsonl", read_jsonl(d / "obligor_events.jsonl")):
            t = ts(rec["recorded_at"])
            if not self.admit("obligor_events.jsonl", t):
                continue
            ob = self.norm_obl(rec["obligor_ref"])
            e = (date.fromisoformat(rec["effective_date"]), t, rec["event_seq"], rec)
            if rec["type"] == "MERGE":
                if not self.v.get("no_merges"):
                    self.merges.setdefault(ob, []).append((e[0], t, rec["event_seq"], self.norm_obl(rec["into"])))
            else:
                self.oev.setdefault(ob, []).append(e)
        self.register = {}
        for raw, r in read_csv(d / "public_entity_register.csv"):
            tax = self.norm_tax(r["fein"])
            lo = date.fromisoformat(r["listed_on"])
            hi = date.fromisoformat(r["delisted_on"]) if r["delisted_on"].strip() else None
            self.register.setdefault(tax, []).append((lo, hi))

    def obligor_known(self, ob, K):
        o = self.obligors.get(ob)
        return o is not None and self.known(o["created"], K)

    def resolve(self, ob, A, K):
        seen = set()
        while True:
            cands = [m for m in self.merges.get(ob, []) if m[0] <= A and self.known(m[1], K)]
            if not cands or ob in seen:
                return ob
            seen.add(ob)
            ob = max(cands)[3]

    def tax_of(self, ob, K):
        best = None
        for eff, t, seq, rec in self.oev.get(ob, []):
            if rec["type"] == "TAXID_CORRECTION" and self.known(t, K) and not self.v.get("no_taxfix"):
                if best is None or (t, seq) > best[0]:
                    best = ((t, seq), self.norm_tax(rec["tax_id"]))
        return best[1] if best else self.obligors[ob]["tax"]

    def sector_of(self, ob, A, K):
        best = None
        for eff, t, seq, rec in self.oev.get(ob, []):
            if rec["type"] in ("SECTOR_SET", "SECTOR_CHANGE") and eff <= A and self.known(t, K):
                key = (eff, t, seq)
                if best is None or key > best[0]:
                    best = (key, rec["sector_code"])
        return best[1] if best else None

    def public(self, tax, day):
        for lo, hi in self.register.get(tax, []):
            if lo <= day and (hi is None or day < hi):
                return True
        return False

    # ------------------------------------------------------------------ leases
    def load_leases(self):
        d = self.data
        self.leases = {}
        for raw, r in read_csv(d / "leases.csv"):
            lid = self.norm_lease(r["lease_id"])
            dollars, cents = r["instalment"].split(".")
            self.leases[lid] = {"id": lid, "ob": self.norm_obl(r["obligor_ref"]), "start": date.fromisoformat(r["start_date"]),
                                "term": int(r["term_months"]), "inst": int(dollars) * 100 + int(cents),
                                "anchor": int(r["anchor_day"]), "branches": [], "events": {}, "relief": {}}
        for raw, r in read_csv(d / "lease_branch_history.csv"):
            t = ts(r["recorded_at"])
            if not self.admit("lease_branch_history.csv", t):
                continue
            lid = self.norm_lease(r["lease_ref"])
            if lid in self.leases:
                self.leases[lid]["branches"].append((date.fromisoformat(r["effective_from"]), t, r["row_id"], self.norm_branch(r["branch_code"])))
        for l in self.leases.values():
            b = sorted(l["branches"], key=lambda x: (x[0], x[1], x[2]))
            l["booking"] = b[0][3] if b else None
            o = self.obligors.get(l["ob"])
            seg = "commercial"
            if o is not None:
                seg = "public" if self.public(self.tax_of(l["ob"], self.watermark), l["start"]) else "commercial"
            l["contract_seg"] = seg
        # lease events
        for rec in self.dedupe("lease_events.jsonl", read_jsonl(d / "lease_events.jsonl")):
            t = ts(rec["recorded_at"])
            if not self.admit("lease_events.jsonl", t):
                continue
            lid = self.norm_lease(rec["lease_ref"])
            if lid not in self.leases:
                self.rejects.append(("lease_events.jsonl", rec["event_id"], "unknown_lease"))
                continue
            self.leases[lid]["events"].setdefault(rec["event_id"], []).append(
                (int(rec["version"]), t, rec["type"], date.fromisoformat(rec["effective_date"])))
        for lid, l in self.leases.items():
            _st, _clo, _co, bad = self.replay(l, date.max, self.watermark)
            for eid in sorted(bad):
                self.rejects.append(("lease_events.jsonl", eid, "invalid_transition"))
        # relief
        for raw, r in read_csv(d / "relief_approvals.csv"):
            t = ts(r["status_at"])
            if not self.admit("relief_approvals.csv", t):
                continue
            lid = self.norm_lease(r["lease_ref"])
            if lid not in self.leases:
                self.rejects.append(("relief_approvals.csv", r["status_id"], "unknown_lease"))
                continue
            self.leases[lid]["relief"].setdefault(r["request_id"], []).append(
                (t, r["status_id"], r["status"], int(r["months"]), int(r["first_deferred_instalment"])))
        self.final_holidays = []
        for lid, l in self.leases.items():
            hol, invalid, over = self.holiday_at(l, self.watermark, collect=True)
            for sid in invalid:
                self.rejects.append(("relief_approvals.csv", sid, "invalid_transition"))
            for rq in over:
                self.rejects.append(("relief_approvals.csv", rq, "holiday_limit"))
            if hol:
                self.final_holidays.append({"request_id": hol[3], "lease_id": lid, "months": hol[0], "first_deferred_instalment": hol[1]})
        self.invoices = {}
        for raw, r in read_csv(d / "invoice_notices.csv"):
            self.invoices[r["invoice_no"].strip().upper()] = self.norm_lease(r["lease_id"])

    def replay(self, l, A, K):
        key = (l["id"], A, K)
        if key in self._state:
            return self._state[key]
        evs = []
        for eid, vers in l["events"].items():
            kv = [x for x in vers if self.known(x[1], K)]
            if not kv:
                continue
            g = max(kv, key=lambda x: (x[0], x[1]))
            if g[2] == "VOID":
                continue
            evs.append((g[3], eid, g[2]))
        evs.sort()
        state, close, co, bad = "PENDING", None, None, []
        for eff, eid, typ in evs:
            if eff > A:
                break
            if state == "PENDING" and typ == "ACTIVATE":
                state = "ACTIVE"
            elif state == "ACTIVE" and typ in ("BUYOUT", "PAYOFF"):
                state, close = "CLOSED", eff
            elif state == "ACTIVE" and typ == "CHARGE_OFF":
                state, co = "CHARGED_OFF", eff
            else:
                bad.append(eid)
        res = (state, close, co, bad)
        self._state[key] = res
        return res

    def holiday_at(self, l, K, collect=False):
        inforce = []
        invalid = []
        for rq, rows in l["relief"].items():
            st = None
            appr = None
            for t, sid, status, months, k in sorted(rows):
                if not self.known(t, K):
                    continue
                ok = (st is None and status == "REQUESTED") or (st == "REQUESTED" and status in ("APPROVED", "DECLINED")) \
                    or (st == "APPROVED" and status == "WITHDRAWN")
                if not ok:
                    invalid.append(sid)
                    continue
                st = status
                if status == "APPROVED":
                    appr = (t, months, k)
            if st == "APPROVED":
                inforce.append((appr[0], rq, appr[1], appr[2]))
        inforce.sort()
        over = [x[1] for x in inforce[self.max_holidays:]]
        hol = (inforce[0][2], inforce[0][3], inforce[0][0], inforce[0][1]) if inforce else None
        if collect:
            return hol, invalid, over
        return hol

    def roll(self, r, d, modified):
        f = d
        while not self.is_bd(r, f):
            f += timedelta(days=1)
        if modified and f.month != d.month:
            f = d
            while not self.is_bd(r, f):
                f -= timedelta(days=1)
        return f

    def schedule(self, l, hol):
        key = (l["id"], hol[:2] if hol else None)
        if key in self._sched:
            return self._sched[key]
        modified = l["contract_seg"] == "public" and not self.v.get("following_all")
        if self.v.get("modified_all"):
            modified = True
        y, m = l["start"].year, l["start"].month
        due = [None]
        for k in range(1, l["term"] + 1):
            shift = hol[0] if hol and k >= hol[1] else 0
            yy, mm = month_add(y, m, k + shift)
            nominal = date(yy, mm, min(l["anchor"], dim(yy, mm)))
            if shift and self.v.get("shift_clamped"):
                y0, m0 = month_add(y, m, k)
                c0 = date(y0, m0, min(l["anchor"], dim(y0, m0)))
                nominal = date(yy, mm, min(c0.day, dim(yy, mm)))
            due.append(self.roll(l["booking"], nominal, modified))
        self._sched[key] = due
        return due

    # ------------------------------------------------------------------ cash
    def parse_amount(self, s):
        m = re.fullmatch(r"(\d+)\.(\d\d)", s.strip())
        if not m:
            return None
        v = int(m.group(1)) * 100 + int(m.group(2))
        return v if v > 0 else None

    def resolve_remit(self, ref):
        lid = self.norm_lease(ref)
        if lid in self.leases:
            return lid
        inv = self.invoices.get(ref.strip().upper())
        if inv in self.leases:
            return inv
        return None

    def load_cash(self):
        d = self.data
        pays = {}

        def slot(key, ch):
            if key not in pays:
                pays[key] = {"ch": ch, "ledger": [], "bank": [], "returns": []}
            return pays[key]
        for r in REGIONS:
            fname = "lockbox_%s.csv" % r.lower()
            for row in self.dedupe(fname, read_csv(d / fname)):
                t = ts(row["received_at"])
                if not self.admit(fname, t):
                    continue
                lid = self.resolve_remit(row["remit_ref"])
                cents = self.parse_amount(row["amount"])
                if lid is None:
                    self.rejects.append((fname, row["item_id"], "unknown_lease"))
                    continue
                if cents is None:
                    self.rejects.append((fname, row["item_id"], "bad_amount"))
                    continue
                key = ("LOCKBOX", row["item_id"].replace("-", "").upper())
                slot(key, "LOCKBOX")["bank"].append((t, date.fromisoformat(row["value_date"]), cents, lid))
        for row in self.dedupe("card_settlements.csv", read_csv(d / "card_settlements.csv")):
            t = ts(row["batch_at"])
            if not self.admit("card_settlements.csv", t):
                continue
            lid = self.resolve_remit(row["lease_ref"])
            cents = self.parse_amount(row["amount"])
            if lid is None:
                self.rejects.append(("card_settlements.csv", row["auth_code"], "unknown_lease"))
                continue
            if cents is None:
                self.rejects.append(("card_settlements.csv", row["auth_code"], "bad_amount"))
                continue
            key = ("CARD", row["auth_code"].upper())
            slot(key, "CARD")["bank"].append((t, date.fromisoformat(row["settlement_date"]), cents - self.surcharge, lid))
        posting_key = {}
        for f in self.ledger_files:
            for rec in self.dedupe(f.name, read_jsonl(f)):
                t = ts(rec["posted_at"])
                if not self.admit(f.name, t):
                    continue
                ch = rec["channel"]
                if ch == "ACH":
                    key = ("ACH", rec["posting_id"])
                else:
                    key = (ch, rec["source_ref"].replace("-", "").upper())
                lid = self.norm_lease(rec["lease_id"])
                slot(key, ch)["ledger"].append((t, int(rec["amount"]), lid, rec["posting_id"]))
                posting_key[rec["posting_id"]] = key
        rlines = []
        for ln in (d / "ach_returns.log").read_text(encoding="utf-8").splitlines():
            if not ln.strip() or ln.startswith("#"):
                continue
            parts = ln.split()
            kv = dict(p.split("=", 1) for p in parts[2:])
            rlines.append((ln, (ts(parts[0]), kv)))
        for t, kv in self.dedupe("ach_returns.log", rlines):
            if not self.admit("ach_returns.log", t):
                continue
            key = posting_key.get(kv["posting"])
            if key is None:
                self.rejects.append(("ach_returns.log", kv["id"], "unknown_posting"))
                continue
            if self.reverses.get(kv["code"].upper(), False):
                pays[key]["returns"].append((t, kv["posting"]))
        self.by_lease = {}
        self.pay_counts = {"lockbox": 0, "card": 0, "ach": 0, "reversed": 0}
        for key in sorted(pays):
            p = pays[key]
            lid = p["ledger"][0][2] if p["ledger"] else p["bank"][0][3]
            if lid not in self.leases:
                continue
            self.by_lease.setdefault(lid, []).append(p)
            self.pay_counts[p["ch"].lower()] += 1
            if p["returns"]:
                self.pay_counts["reversed"] += 1

    def cash_at(self, l, K):
        out = []
        reg = l["booking"]
        for p in self.by_lease.get(l["id"], []):
            led = [x for x in p["ledger"] if self.known(x[0], K)]
            bank = [x for x in p["bank"] if self.known(x[0], K)]
            if not led and not bank:
                continue
            if led and any(self.known(t, K) and any(pid == x[3] for x in led) for t, pid in p["returns"]):
                continue
            g = max(bank) if bank else None
            lg = min(led) if led else None
            if p["ch"] == "LOCKBOX":
                v, c = (g[1], g[2]) if g else (self.local_date(reg, lg[0]), lg[1])
            elif p["ch"] == "CARD":
                v = g[1] if g else self.local_date(reg, lg[0])
                c = lg[1] if lg else g[2]
            else:
                v, c = self.local_date(reg, lg[0]), lg[1]
            out.append((v, c))
        out.sort()
        vals = [x[0] for x in out]
        cum = []
        s = 0
        for x in out:
            s += x[1]
            cum.append(s)
        return vals, cum

    def dpd_fn(self, l, due, cash):
        vals, cum = cash
        inst = l["inst"]
        tol = self.tol[l["contract_seg"]]
        n = l["term"]

        def dpd(day):
            i = bisect_right(vals, day)
            paid = cum[i - 1] if i else 0
            k = (paid + tol) // inst + 1
            if k <= n and due[k] < day:
                return (day - due[k]).days
            return 0

        def worst(a, b):
            if b < a:
                return 0
            best = dpd(b)
            for v in vals[bisect_right(vals, a):bisect_right(vals, b)]:
                best = max(best, dpd(v - timedelta(days=1)))
            return best
        return dpd, worst

    # ------------------------------------------------------------------ bureau and limits
    def load_bureau_limits(self):
        d = self.data
        self.pulls = {}
        for rec in self.dedupe("bureau_kr.jsonl", read_jsonl(d / "bureau_kr.jsonl")):
            t = ts(rec["recorded_at"])
            if not self.admit("bureau_kr.jsonl", t):
                continue
            st = rec["status"]
            val = ("score", int(rec["score"])) if st == "OK" else (("no_hit", None) if st == "NOHIT" else ("thin", None))
            self.pulls.setdefault(self.norm_tax(rec["tax_id"]), []).append(
                (date.fromisoformat(rec["pulled_on"]), "KR", t, rec["pull_id"], val))
        for r in self.dedupe("bureau_nd.csv", read_csv(d / "bureau_nd.csv")):
            t = ts(r["loaded_at"])
            if not self.admit("bureau_nd.csv", t):
                continue
            if r["result"] == "NOHIT":
                val = ("no_hit", None)
            elif not r["score"].strip() or (self.v.get("nd_zero_thin") and r["score"].strip() == "0.0"):
                val = ("thin", None)
            else:
                w, f = r["score"].split(".")
                tenths = int(w) * 10 + int(f)
                val = ("score", 300 + tenths * self.nd_num // self.nd_den)
            self.pulls.setdefault(self.norm_tax(r["fein"]), []).append(
                (date.fromisoformat(r["pull_date"]), "ND", t, r["pull_ref"], val))
        self.dispute_at = {}
        for pid, t in self.disputes:
            if t <= self.watermark:
                self.dispute_at[pid] = min(t, self.dispute_at.get(pid, t))
        self.limits = {}
        for r in self.dedupe("credit_limits.csv", read_csv(d / "credit_limits.csv")):
            t = ts(r["recorded_at"])
            if not self.admit("credit_limits.csv", t):
                continue
            v = r["limit_k"].strip()
            if v == "" and self.v.get("blank_limit_zero"):
                v = "0"
            self.limits.setdefault(self.norm_obl(r["obligor_ref"]), []).append(
                (date.fromisoformat(r["effective_from"]), t, r["limit_id"], None if v == "" else int(v) * 100000))

    def bureau_value(self, tax, A, K, seg):
        cands = []
        order = self.vendor_order[seg]
        for pulled, vnd, t, pid, val in self.pulls.get(tax, []):
            if pulled > A or (A - pulled).days > self.bureau_age or not self.known(t, K):
                continue
            if pid in self.dispute_at and self.known(self.dispute_at[pid], K):
                continue
            cands.append((pulled, -order.index(vnd), t, pid, val))
        if not cands:
            return ("missing", None)
        return max(cands)[4]

    def limit_value(self, ob, A, K):
        rows = [x for x in self.limits.get(ob, []) if x[0] <= A and self.known(x[1], K) and x[3] is not None]
        if not rows:
            return None
        return max(rows)[3]

    # ------------------------------------------------------------------ backtest
    def lineage_closure(self, srcs):
        bad = set(srcs)
        changed = True
        while changed:
            changed = False
            for n, ups in self.nodes.items():
                if n not in bad and any(u in bad for u in ups):
                    bad.add(n)
                    changed = True
        return bad

    def version_for(self, s):
        cur = None
        for eff, ver, card in self.versions:
            if eff <= s:
                cur = (ver, card)
        return cur

    def run(self):
        obs = []
        unresolved = []
        candidates = 0
        excl_rows = []
        quar_rows = []
        usage = {}
        final_K = self.watermark
        for s in self.snapshots:
            A = s - timedelta(days=1)
            ver = self.version_for(s)
            for lid in sorted(self.leases):
                l = self.leases[lid]
                if l["booking"] is None:
                    continue
                K = final_K if self.v.get("full_knowledge") else self.cuts[(s, l["booking"])]
                state = self.replay(l, A, K)[0]
                if state != "ACTIVE":
                    continue
                candidates += 1
                rows = [b for b in l["branches"] if b[0] <= A and self.known(b[1], K)]
                if not rows:
                    unresolved.append({"lease_id": lid, "snapshot": s.isoformat(), "reason": "no_branch"})
                    continue
                region = max(rows, key=lambda b: (b[0], b[1], b[2]))[3]
                if l["ob"] is None or not self.obligor_known(l["ob"], K):
                    unresolved.append({"lease_id": lid, "snapshot": s.isoformat(), "reason": "unknown_obligor"})
                    continue
                cutK = self.cuts[(s, l["booking"])]
                o = self.resolve(l["ob"], A, K)
                tax = self.tax_of(o, K)
                seg = "public" if self.public(tax, A) else "commercial"
                hol = self.holiday_at(l, K)
                due = self.schedule(l, hol)
                dpd, worst = self.dpd_fn(l, due, self.cash_at(l, K))
                feats = {"dpd_now": dpd(A), "max_dpd_12m": worst(A - timedelta(days=364), A),
                         "recent_worst": worst(A - timedelta(days=89), A)}
                mob = (A.year - l["start"].year) * 12 + (A.month - l["start"].month) - (1 if A.day < l["start"].day else 0)
                feats["months_on_book"] = mob
                # obligor level
                group = [(lid2, l2, self.replay(l2, A, K)[0]) for lid2, l2 in self.groups(A, K).get(o, [])]
                active = [(lid2, l2) for lid2, l2, st in group if st == "ACTIVE"]
                feats["active_leases"] = len(active)
                exposure = 0
                for lid2, l2 in active:
                    d2 = self.schedule(l2, self.holiday_at(l2, K))
                    exposure += l2["inst"] * sum(1 for k in range(1, l2["term"] + 1) if d2[k] > A)
                lim = self.limit_value(o, A, K)
                if lim is None:
                    util = ("missing", None)
                elif lim == 0:
                    util = ("zero_limit", None)
                else:
                    util = ("value", exposure * 1000 // lim)
                bureau = self.bureau_value(tax, A, K, seg)
                sector = self.sector_of(o, A, K)
                q_src = set()
                for a, b, src, regs in self.incidents:
                    if region in regs and a <= cutK < b:
                        q_src.add(src)
                qnodes = self.lineage_closure(q_src) if q_src else set()
                name, card = ver
                bins = {}
                score = card["base_points"][seg]
                qchars = []
                for ch in card["characteristics"]:
                    cn = ch["name"]
                    if cn in qnodes:
                        lab, pts = "quarantined", ch["special"]["quarantined"]
                        qchars.append(cn)
                    elif cn == "sector_class":
                        lab = self.sector_class.get(sector)
                        if lab is None:
                            lab, pts = "missing", ch["special"]["missing"]
                        else:
                            pts = ch["categories"][lab]
                    else:
                        if cn == "utilisation":
                            kind, x = util
                        elif cn == "bureau":
                            kind, x = bureau if bureau[0] != "score" else ("value", bureau[1])
                        else:
                            kind, x = "value", feats[cn]
                        if kind != "value":
                            lab, pts = kind, ch["special"][kind]
                        else:
                            lab = pts = None
                            for b in ch["bins"]:
                                if b["lo"] <= x and (b["hi"] is None or x < b["hi"]):
                                    lab, pts = b["label"], b["points"]
                                    break
                    bins[cn] = lab
                    score += pts
                if qchars:
                    quar_rows.append({"lease_id": lid, "snapshot": s.isoformat(), "characteristics": sorted(qchars)})
                approved = score >= card["cutoff"][seg]
                # exclusions
                reasons = []
                for reason in self.exclusion_order:
                    if reason == "prior_charge_off":
                        if any(st == "CHARGED_OFF" and lid2 != lid for lid2, l2, st in group):
                            reasons.append(reason)
                    elif reason == "holiday_active" and hol:
                        k = hol[1]
                        orig = self.schedule(l, None)[k]
                        if orig <= A < due[k]:
                            reasons.append(reason)
                exclusion = reasons[0] if reasons and not self.v.get("no_exclusions") else None
                if exclusion:
                    excl_rows.append({"lease_id": lid, "snapshot": s.isoformat(), "reason": exclusion})
                label = self.label(l, A)
                usage[(s, name)] = usage.get((s, name), 0) + 1
                obs.append({"lease_id": lid, "snapshot": s.isoformat(), "obligor_id": o, "segment": seg, "region": region,
                            "scorecard": name, "bins": bins, "score": score, "approved": approved,
                            "exclusion": exclusion, "label": label})
        self.result = (obs, unresolved, candidates, excl_rows, quar_rows, usage)
        return self.result

    def groups(self, A, K):
        key = (A, K)
        if key not in self._groups:
            g = {}
            for lid2 in sorted(self.leases):
                l2 = self.leases[lid2]
                if l2["ob"] is None or l2["booking"] is None or not self.obligor_known(l2["ob"], K):
                    continue
                g.setdefault(self.resolve(l2["ob"], A, K), []).append((lid2, l2))
            self._groups[key] = g
        return self._groups[key]

    def final_path(self, l):
        if l["id"] not in self._final:
            K = self.watermark
            due = self.schedule(l, self.holiday_at(l, K))
            self._final[l["id"]] = (self.replay(l, date.max, K), self.dpd_fn(l, due, self.cash_at(l, K)))
        return self._final[l["id"]]

    def label(self, l, A):
        end = A + timedelta(days=self.perf)
        if end > self.cutoff:
            return "immature"
        (_st, close, co, _bad), (_dpd, worst) = self.final_path(l)
        if co is not None and co <= end:
            return "bad"
        wend = min(end, close) if close is not None else end
        if worst(A + timedelta(days=1), wend) >= self.bad_dpd:
            return "bad"
        if close is not None and close <= end:
            return "indeterminate"
        return "good"


# ---------------------------------------------------------------------- metrics and reports
def totals(rows):
    t = {"observations": len(rows), "excluded": 0, "bad": 0, "good": 0, "indeterminate": 0, "immature": 0, "approved": 0}
    for r in rows:
        t[r["label"]] += 1
        t["excluded"] += r["exclusion"] is not None
        t["approved"] += r["approved"]
    return t


def metrics(rows):
    pop = [r for r in rows if r["exclusion"] is None and r["label"] in ("bad", "good")]
    bads = sorted(r["score"] for r in pop if r["label"] == "bad")
    goods = sorted(r["score"] for r in pop if r["label"] == "good")
    nb, ng = len(bads), len(goods)
    auc = ks = None
    if nb and ng:
        num = 0
        for b in bads:
            lo = bisect_right(goods, b - 1)
            hi = bisect_right(goods, b)
            num += 2 * (ng - hi) + (hi - lo)
        auc = Fraction(num, 2 * nb * ng)
        best = Fraction(0)
        for c in sorted(set(bads + goods)):
            diff = abs(Fraction(bisect_right(bads, c), nb) - Fraction(bisect_right(goods, c), ng))
            best = max(best, diff)
        ks = best
    return {"population": len(pop), "bad": nb, "good": ng, "auc_ppm": ppm(auc), "ks_ppm": ppm(ks),
            "bad_rate_ppm": ppm(Fraction(nb, nb + ng)) if nb + ng else None,
            "approved": sum(1 for r in pop if r["approved"]),
            "approved_bad": sum(1 for r in pop if r["approved"] and r["label"] == "bad")}


def public_row(r):
    return {k: r[k] for k in ("lease_id", "snapshot", "obligor_id", "segment", "scorecard", "bins", "score",
                              "approved", "exclusion", "label")}


def build_reports(ex):
    obs, unresolved, candidates, excl_rows, quar_rows, usage = ex.result
    order = lambda r: (r["snapshot"], r["lease_id"])
    obs = sorted(obs, key=order)
    snaps = [s.isoformat() for s in ex.snapshots]
    rep = {}
    for reg in REGIONS:
        rows = [r for r in obs if r["region"] == reg]
        rep["region_%s.json" % reg] = {"region": reg, "totals": totals(rows), "metrics": metrics(rows),
                                       "observations": [public_row(r) for r in rows]}
    for seg in SEGMENTS:
        rows = [r for r in obs if r["segment"] == seg]
        by_card = {}
        for r in rows:
            by_card[r["scorecard"]] = by_card.get(r["scorecard"], 0) + 1
        rep["segment_%s.json" % seg] = {"segment": seg, "totals": totals(rows), "metrics": metrics(rows),
                                        "by_snapshot": [{"snapshot": s, "totals": totals([r for r in rows if r["snapshot"] == s]),
                                                         "metrics": metrics([r for r in rows if r["snapshot"] == s])} for s in snaps],
                                        "by_scorecard": by_card}
    bands = []
    for name, lo, hi in ex.bands:
        rows = [r for r in obs if lo <= r["score"] < hi]
        bands.append({"band": name, "observations": len(rows), "bad": sum(r["label"] == "bad" for r in rows),
                      "good": sum(r["label"] == "good" for r in rows)})
    rep["summary.json"] = {"run_id": ex.run_id, "snapshots": snaps, "totals": totals(obs), "metrics": metrics(obs),
                           "by_region": {reg: totals([r for r in obs if r["region"] == reg]) for reg in REGIONS},
                           "by_segment": {seg: totals([r for r in obs if r["segment"] == seg]) for seg in SEGMENTS},
                           "by_snapshot": [{"snapshot": s, "totals": totals([r for r in obs if r["snapshot"] == s]),
                                            "auc_ppm": metrics([r for r in obs if r["snapshot"] == s])["auc_ppm"]} for s in snaps],
                           "score_bands": bands}
    merges = []
    for ob in sorted(ex.merges):
        tgt = ex.resolve(ob, date.max, ex.watermark)
        if tgt != ob:
            merges.append({"obligor_id": ob, "resolved_to": tgt})
    rep["policy_audit.json"] = {
        "cut_instants": {s.isoformat(): {r: iso(ex.cuts[(s, r)]) for r in REGIONS} for s in ex.snapshots},
        "scorecard_usage": [{"snapshot": s.isoformat(), "version": v, "observations": n} for (s, v), n in sorted(usage.items())],
        "exclusions": sorted(excl_rows, key=order),
        "quarantined": sorted(quar_rows, key=order),
        "holidays": sorted(ex.final_holidays, key=lambda x: x["request_id"]),
        "merges": merges}
    sv = rep["summary.json"]["totals"]["observations"]
    rep["data_quality.json"] = {
        "rejects": [{"source": a, "record_id": b, "reason": c} for a, b, c in sorted(set(ex.rejects))],
        "duplicates": dict(sorted(ex.dups.items())),
        "late_records": dict(sorted(ex.late.items())),
        "unresolved": sorted(unresolved, key=order),
        "partition": {"candidates": candidates, "scored": len(obs), "unresolved": len(unresolved)},
        "payments": ex.pay_counts,
        "identity_check": {
            "regions_minus_summary": sum(rep["region_%s.json" % r]["totals"]["observations"] for r in REGIONS) - sv,
            "segments_minus_summary": sum(rep["segment_%s.json" % g]["totals"]["observations"] for g in SEGMENTS) - sv,
            "snapshots_minus_summary": sum(x["totals"]["observations"] for x in rep["summary.json"]["by_snapshot"]) - sv}}
    return rep


def main(data, out, variant=None):
    ex = Extract(data, variant)
    ex.run()
    rep = build_reports(ex)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    for name in REPORTS:
        (out / name).write_text(json.dumps(rep[name], sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return ex, rep


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: derive_report.py DATA_DIR OUT_DIR")
    main(sys.argv[1], sys.argv[2])
