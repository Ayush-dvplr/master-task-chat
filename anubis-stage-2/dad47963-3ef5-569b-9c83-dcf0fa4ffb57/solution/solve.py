#!/usr/bin/env python3
"""Reference monitoring engine: reads an estate directory, writes the cycle artifacts."""
from __future__ import annotations

import configparser
import csv
import io
import json
import mailbox
import quopri
import re
import sqlite3
import sys
import tomllib
import zipfile
import xml.etree.ElementTree as ET
from decimal import Decimal
from fractions import Fraction
from html.parser import HTMLParser
from pathlib import Path


# =============================================================================
# Value readers (specification 3.1 and 4): every documented field notation is
# turned into one canonical Python value here.
# =============================================================================
import calendar
import datetime as dtm
import math
from decimal import ROUND_HALF_UP

UNIX0 = dtm.datetime(1970, 1, 1)
EXCEL0 = dtm.date(1899, 12, 30)
LOOKALIKE = str.maketrans({"\u0410": "A", "\u0421": "C"})
HIDDEN_CHARS = frozenset("\u00a0\u200b\ufeff")
OPEN_ENDS = frozenset({"", "open", "none", "9999-12-31", "31.12.9999", "99991231"})


def squeeze(value):
    """Drop every whitespace and invisible character (spec 3.1)."""
    return "".join(c for c in str(value) if not (c.isspace() or c in HIDDEN_CHARS))


def digit_value(value):
    """Integer spelt by the decimal digits of a hash key, read left to right (spec 2.2)."""
    found = [c for c in str(value) if c.isdigit()]
    return int("".join(found)) if found else 0


def _canonical(value, prefix):
    text = squeeze(value).upper().translate(LOOKALIKE).replace("-", "")
    tail = text[len(prefix):]
    if text.startswith(prefix) and tail.isdigit():
        return prefix + str(int(tail)).zfill(7)
    return text


def as_acct(value):
    return _canonical(value, "AC")


def as_acctref(value):
    text = squeeze(value).upper()
    return text if text.startswith("L-") else as_acct(value)


def as_cust(value):
    text = squeeze(value).upper()
    return text if text.startswith("LCU") else _canonical(value, "CU")


def as_upper(value):
    return squeeze(value).upper()


as_id = as_upper
as_code = as_upper


def as_text(value):
    return "" if value is None else str(value)


def as_date(value):
    if isinstance(value, dtm.datetime):
        return value.date()
    if isinstance(value, dtm.date):
        return value
    text = squeeze(value)
    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso:
        y, m, d = iso.groups()
    elif re.fullmatch(r"\d{8}", text):
        y, m, d = text[:4], text[4:6], text[6:]
    else:
        euro = re.fullmatch(r"(\d{2})[./-](\d{2})[./-](\d{4})", text)
        if not euro:
            raise ValueError(f"unrecognised date {value!r}")
        d, m, y = euro.groups()
    return dtm.date(int(y), int(m), int(d))


def as_end(value):
    if value is None or squeeze(value).lower() in OPEN_ENDS:
        return None
    return as_date(value)


def as_month(value):
    """Month as a running index year * 12 + (month - 1)."""
    text = squeeze(value)
    slash = re.fullmatch(r"(\d{2})/(\d{4})", text)
    if slash:
        return int(slash.group(2)) * 12 + int(slash.group(1)) - 1
    compact = text.replace("-", "")
    return int(compact[:4]) * 12 + int(compact[4:6]) - 1


def as_dec(value):
    if isinstance(value, bool):
        raise ValueError("boolean is not a number")
    if isinstance(value, (int, Decimal)):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(repr(value))
    text = squeeze(value)
    negative = len(text) > 1 and text[0] == "(" and text[-1] == ")"
    text = text.strip("()")
    if "," in text:
        # a comma is a thousands separator next to a point, otherwise the decimal mark
        text = text.replace(",", "") if "." in text else text.replace(",", ".")
    number = Decimal(text)
    return -number if negative else number


def as_money(value):
    return as_dec(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def as_int(value):
    return value if isinstance(value, int) else int(squeeze(value))


def as_pi(value):
    text = squeeze(value).strip("'\"")
    if text.endswith("%"):
        return Fraction(as_dec(text[:-1])) / 100
    if "/" in text:
        num, den = text.split("/")
        return Fraction(int(num), int(den))
    return Fraction(as_dec(text))


def as_instant(value):
    """Epoch seconds of an ISO-8601 instant; no designator means UTC."""
    if isinstance(value, int):
        return value
    text = re.sub(r"\.\d+(?=Z$|[+-]\d{2}:\d{2}$|$)", "", str(value).strip())
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    stamp = dtm.datetime.fromisoformat(text)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dtm.timezone.utc)
    return int(stamp.timestamp())


def as_local(value, layout="%Y-%m-%d %H:%M:%S"):
    """Wall-clock reading as seconds on the epoch scale, without any offset applied."""
    return int((dtm.datetime.strptime(value.strip(), layout) - UNIX0).total_seconds())


def as_serial_date(value):
    return EXCEL0 + dtm.timedelta(days=int(as_dec(value)))


def as_serial_instant(value):
    """Excel 1900 serial day count in UTC, rounded to the nearest second."""
    seconds = (Fraction(as_dec(value)) - 25569) * 86400
    return math.floor(seconds + Fraction(1, 2))


def parse_control_text(text):
    pairs = (part.split("=", 1) for part in re.split(r"[\s;]+", text.strip()) if "=" in part)
    return {k: v for k, v in pairs}


def control_tuple(c):
    acks = [(c["ack_rows_of"], "rows", int(c["ack_rows"])), (c["ack_hash_of"], "hash", int(c["ack_hash"]))]
    return c["control_id"], acks


KIND = {"acct": as_acct, "acctref": as_acctref, "cust": as_cust, "id": as_id, "code": as_code,
        "status": as_upper, "date": as_date, "enddate": as_end, "month": as_month, "money": as_money,
        "dec": as_dec, "int": as_int, "pi": as_pi, "isoutc": as_instant, "text": as_text,
        "serial": as_serial_date}


# =============================================================================
# Rule layer. Each block implements one section of monitoring_spec_v4.md or of
# a policy document it names, reading the facts the loaders below collect.
# =============================================================================
from bisect import bisect_right
from collections import defaultdict
from decimal import localcontext

SEGMENTS = ("CARD", "PLOAN", "AUTO", "MORT", "OVDR", "BNPL")
MARKET_CURRENCY = {"GB": "GBP", "PL": "PLN", "SE": "SEK", "CZ": "CZK",
                   "HU": "HUF", "CH": "CHF", "DK": "DKK", "NO": "NOK"}
CURRENT_CYCLE = "2026-Q2-MON"
WINDOW_REASONS = ("CENSORED", "INSUFFICIENT", "INDETERMINATE")
OUTPUT_NAMES = ["cohort.csv", "exclusions.csv", "score_selection.csv", "performance_windows.csv",
                "population_summary.json", "discrimination.json", "psi.json", "calibration.csv",
                "reconciliation.json"]
HEADERS = {
    "cohort.csv": "acct,segment,market,cohort_month,decision_utc,score,score_band,bad,weight,exposure_eur",
    "exclusions.csv": "acct,reason",
    "score_selection.csv": "acct,event_id,run_id,model_version,score_ts_utc,score",
    "performance_windows.csv": "acct,window_start,window_end,months_observed,max_dpd,bad_month,outcome",
    "calibration.csv": "segment,band,accounts,weighted_accounts,weighted_bads,expected_bads,actual_rate,expected_rate",
}
EPOCH_DAY = dtm.date(1970, 1, 1)
PSI_FLOOR = Fraction(1, 10000)


# ---- calendar helpers: months are counted as year * 12 + (month - 1) -------
def month_no(year, month):
    return year * 12 + month - 1


def month_name(n):
    year, rest = divmod(n, 12)
    return f"{year:04d}-{rest + 1:02d}"


def month_start(n):
    year, rest = divmod(n, 12)
    return dtm.date(year, rest + 1, 1)


def month_end(n):
    year, rest = divmod(n, 12)
    return dtm.date(year, rest + 1, calendar.monthrange(year, rest + 1)[1])


def month_of_day(day):
    return month_no(day.year, day.month)


def day_of(instant):
    return EPOCH_DAY + dtm.timedelta(days=instant // 86400)


def instant_name(instant):
    return dtm.datetime.fromtimestamp(instant, dtm.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---- spec 3.3: market wall clocks ---------------------------------------------
def _summer_edge(year, month):
    """01:00 UTC on the last Sunday of the month, in epoch seconds."""
    last = dtm.date(year, month, calendar.monthrange(year, month)[1])
    sunday = last - dtm.timedelta(days=last.isoweekday() % 7)
    return (sunday - EPOCH_DAY).days * 86400 + 3600


def clock_offset(market, instant):
    year = day_of(instant).year
    summer = _summer_edge(year, 3) <= instant < _summer_edge(year, 10)
    return (0 if market == "GB" else 3600) + (3600 if summer else 0)


def wall_clock_to_utc(market, wall):
    """A wall time that occurs twice is its summer occurrence; one in the spring gap takes the standard offset."""
    standard = 0 if market == "GB" else 3600
    for offset in (standard + 3600, standard):
        if clock_offset(market, wall - offset) == offset:
            return wall - offset
    return wall - standard


# ---- spec 8.6: reporting precision ----------------------------------------------
def decimals(value, places, half_up=False):
    """Exact rational rounded to a fixed number of decimals, half to even unless half_up."""
    scaled = Fraction(value) * 10 ** places
    if half_up:
        units = math.floor(abs(scaled) + Fraction(1, 2))
        units = -units if scaled < 0 else units
    else:
        units = round(scaled)
    sign = "-" if units < 0 else ""
    whole, part = divmod(abs(units), 10 ** places)
    return f"{sign}{whole}.{part:0{places}d}" if places else f"{sign}{whole}"


def rate(num, den):
    return decimals(Fraction(num, 1) / den, 6) if den else None


# ---- governance precedence policy 3.1-3.3, errata register, merge decisions -----
class Governance:
    def __init__(self, facts):
        latest = {}
        for row_no, (cr, status, decided) in enumerate(facts["change_requests"]):
            stamp = (decided, row_no)
            if cr not in latest or stamp > latest[cr][0]:
                latest[cr] = (stamp, status)
        self.cr_status = {cr: status for cr, (_stamp, status) in latest.items()}
        self.dpd_threshold = dict.fromkeys(SEGMENTS, 90)
        self.cuts = {seg: list(points) for seg, points in facts["documented_cuts"].items()}
        self.hold_end_inclusive = False
        for _eid, _doc, change, cr in facts["rule_errata"]:
            if not self.in_force(cr):
                continue
            threshold = re.search(r"DPD threshold for (\w+) is (\d+)", change, re.I)
            if threshold:
                self.dpd_threshold[threshold.group(1).upper()] = int(threshold.group(2))
            cut = re.search(r"(\w+) cut point c(\d) reads \d+; the correct value is (\d+)", change)
            if cut and cut.group(1) in self.cuts:
                self.cuts[cut.group(1)][int(cut.group(2)) - 1] = int(cut.group(3))
            if re.search(r"to date of a litigation hold is inclusive", change, re.I):
                self.hold_end_inclusive = True
        self.withdrawn = [(model, start) for model, start, cr in facts["registry_withdrawals"] if self.in_force(cr)]
        self.approvals = facts["version_approvals"]

    def in_force(self, cr):
        return self.cr_status.get(as_id(cr)) == "APPROVED"

    def version_ok(self, version, segment, day):
        granted = any(model == version and segment in segments and start <= day and (end is None or day <= end)
                      for model, segments, start, end in self.approvals)
        return granted and not any(model == version and day >= start for model, start in self.withdrawn)


class Customers:
    """Customer resolution: alias table first, then approved merges followed to the survivor."""

    def __init__(self, facts):
        self.aliases = facts["customer_aliases"]
        legacy = facts["legacy_customers"]
        chosen = {}
        for merged, survivor, decision, decided in facts["merge_rows"]:
            if decision != "APPROVED":
                continue
            merged, survivor = as_cust(legacy.get(merged, merged)), as_cust(legacy.get(survivor, survivor))
            if merged not in chosen or (decided, survivor) > chosen[merged]:
                chosen[merged] = (decided, survivor)
        self.merges = {merged: survivor for merged, (_d, survivor) in chosen.items()}
        self._memo = {}

    def resolve(self, customer):
        if customer not in self._memo:
            current, seen = self.aliases.get(customer, customer), set()
            while current in self.merges and current not in seen:
                seen.add(current)
                current = self.merges[current]
            self._memo[customer] = current
        return self._memo[customer]


# ---- spec 2: delivery controls --------------------------------------------------
def delivery_controls(facts):
    cycle_rows = [row for row in facts["manifest_rows"] if row[2] == CURRENT_CYCLE]
    expected = sorted(delivery for delivery, _file, _cycle, _at in cycle_rows)
    ring = facts["control_ring"]
    measured = {f["control_id"]: (f["rows"], f["hash"]) for f in ring}
    acknowledged = defaultdict(list)
    for f in ring:
        for target, kind, value in f["acks"]:
            acknowledged[(target, kind)].append(value)
    failed = []
    for cid in expected:
        rows_ack, hash_ack = acknowledged[(cid, "rows")], acknowledged[(cid, "hash")]
        ok = (cid in measured and rows_ack and hash_ack
              and set(rows_ack) == {measured[cid][0]} and set(hash_ack) == {measured[cid][1]})
        if not ok:
            failed.append(cid)
    return {"status": "RECONCILED" if not failed and len(ring) == len(expected) else "UNRECONCILED",
            "files_checked": len(ring), "failed_controls": failed,
            "estate_record_total": sum(f["rows"] for f in ring),
            "estate_hash_total": sum(f["hash"] for f in ring)}


class Review:
    """One cycle of the monitoring review: population, scores, exclusions, outcomes, weights."""

    def __init__(self, facts):
        self.facts = facts
        self.gov = Governance(facts)
        self.people = Customers(facts)
        self.excluded = {}
        self.picked = {}
        self.window = {}
        self.cohort = []
        self.april_app = {acct: app for app, acct in facts["april_app_ids"].items()}

    def exclude(self, account, reason):
        self.excluded[account["acct"]] = reason

    # ---- spec 3.2-3.4: one decision per account ----------------------------
    def decisions(self):
        f = self.facts
        order = {}
        cycle_rows = sorted((row for row in f["manifest_rows"] if row[2] == CURRENT_CYCLE), key=lambda r: (r[3], r[0]))
        for position, (_delivery, file_name, _cycle, _at) in enumerate(cycle_rows):
            order[file_name] = position
        best = {}
        for rec in f["application_rows"]:
            if (rec["file"], rec["recno"]) in f["quarantined"]:
                continue
            rank = (rec["revision"], rec["received_utc"], order.get(rec["file"], 0), rec["recno"])
            if rec["acct"] not in best or rank > best[rec["acct"]][0]:
                best[rec["acct"]] = (rank, rec)
        out = []
        for acct in sorted(best):
            out.append(self.decision_of(best[acct][1]))
        return out

    def decision_of(self, rec):
        f = self.facts
        branch = f["branch_recode"].get(rec["branch"], rec["branch"])
        has_utc = rec["decision_utc"] is not None
        lookup_day = day_of(rec["decision_utc"] if has_utc else rec["decision_local"])
        markets = [m for m, start, end in f["branch_rows"].get(branch, ())
                   if start <= lookup_day and (end is None or lookup_day <= end)]
        if not markets:
            raise ValueError(f"branch {branch} has no market on {lookup_day}")
        market = markets[-1]
        decided = rec["decision_utc"] if has_utc else wall_clock_to_utc(market, rec["decision_local"])
        local_day = day_of(decided + clock_offset(market, decided))
        code = rec["product_code"]
        if rec["product_basis"] == "current":
            later = sorted((m for m in f["product_moves"].get(rec["acct"], ()) if m[2] > local_day),
                           key=lambda m: (m[2], m[3]))
            if later:
                code = later[0][0]
        app_id = rec["app_id"] or self.april_app.get(rec["acct"])
        return {"acct": rec["acct"], "customer": self.people.resolve(rec["cust"]), "app_id": app_id,
                "market": market, "segment": f["product_segment"][code], "decided": decided,
                "day": local_day, "cohort": month_of_day(local_day), "limit": rec["limit"]}

    # ---- spec 3.3, 3.5, 3.6 ------------------------------------------------
    def in_scope(self, decisions):
        f = self.facts
        first, last = month_no(2025, 1), month_no(2025, 6)
        survivors = []
        for a in decisions:
            if not first <= a["cohort"] <= last:
                self.exclude(a, "WINDOW")
                continue
            early = [w for w in f["withdrawal_dates"].get(a["acct"], ()) if 0 <= (w - a["day"]).days <= 14]
            if early and a["acct"] not in f["reversed_withdrawals"]:
                self.exclude(a, "WITHDRAWN")
                continue
            survivors.append(a)
        groups = defaultdict(list)
        for a in survivors:
            groups[(a["customer"], a["segment"])].append(a)
        kept = []
        for members in groups.values():
            members.sort(key=lambda a: (a["decided"], a["acct"]))
            last_kept_day = None
            for a in members:
                if last_kept_day is not None and (a["day"] - last_kept_day).days <= 30:
                    self.exclude(a, "DUPLICATE")
                else:
                    last_kept_day = a["day"]
                    kept.append(a)
        kept.sort(key=lambda a: a["acct"])
        return kept

    # ---- spec 6: point-in-time score ----------------------------------------
    def scored(self, accounts):
        f = self.facts
        usable_runs = {run for run, (node, _model, status) in f["run_register"].items()
                       if status == "OK" and node != "9" and run not in f["voided_runs"]}
        by_account = defaultdict(list)
        for ev in f["score_events"]:
            if ev["run_id"] in usable_runs and (ev["file"], ev["recno"]) not in f["quarantined"]:
                by_account[ev["acct"]].append(ev)
        out = []
        for a in accounts:
            candidates = []
            for ev in by_account.get(a["acct"], ()):
                version = f["run_register"][ev["run_id"]][1]
                at = ev["score_ts"] + f["clock_offsets"].get(ev["run_id"], 0)
                if at <= a["decided"] and self.gov.version_ok(version, a["segment"], a["day"]):
                    candidates.append(((at, ev["event_num"]), ev, version))
            if not candidates:
                self.exclude(a, "NO_SCORE")
                self.picked[a["acct"]] = None
                continue
            (at, _n), ev, version = max(candidates, key=lambda c: c[0])
            a["score"] = ev["score"]
            self.picked[a["acct"]] = (ev["event_id"], ev["run_id"], version, instant_name(at), ev["score"])
            out.append(a)
        return out

    # ---- exclusion policy section 2 ------------------------------------------
    def employment_spans(self):
        f = self.facts
        spans = defaultdict(list)
        for employee, starts in f["employee_starts"].items():
            leaves = sorted(f["employee_leaves"].get(employee, ()))
            nxt = 0
            for customer, started in sorted(starts, key=lambda s: s[1]):
                nxt = max(nxt, bisect_right(leaves, started))
                ended = leaves[nxt] if nxt < len(leaves) else None
                if ended is not None:
                    nxt += 1
                spans[self.people.resolve(customer)].append((started, ended))
        return spans

    def policy_exclusions(self, accounts):
        f, gov = self.facts, self.gov
        spans = self.employment_spans()
        first_death = {}
        for customer, day in f["death_notices"]:
            who = self.people.resolve(customer)
            first_death[who] = min(day, first_death.get(who, day))
        first_fraud = {}
        for case, acct, day in f["fraud_alert_rows"]:
            if f["case_disposition"].get(case) == "CONFIRMED":
                first_fraud[acct] = min(day, first_fraud.get(acct, day))

        def staff(a):
            return any(s <= a["day"] and (e is None or a["day"] < e) for s, e in spans.get(a["customer"], ()))

        def legal_hold(a):
            return any(s <= a["day"] and (e is None or a["day"] < e or (gov.hold_end_inclusive and a["day"] == e))
                       for s, e in f["hold_spans"].get(a["acct"], ()))

        def insolvency(a):
            return a["acct"] in f["insolvency_notices"] and f["insolvency_notices"][a["acct"]] <= a["window_end"]

        def redress(a):
            return a["acct"] in f["redress_members"]

        def deceased(a):
            return a["customer"] in first_death and first_death[a["customer"]] <= a["window_end"]

        def fraud(a):
            return a["acct"] in first_fraud and first_fraud[a["acct"]] <= a["window_end"]

        screens = (("STAFF", staff), ("LEGAL_HOLD", legal_hold), ("INSOLVENCY", insolvency),
                   ("REDRESS", redress), ("DECEASED", deceased), ("FRAUD", fraud))
        out = []
        for a in accounts:
            a["window_end"] = month_end(a["cohort"] + 12)
            reason = next((name for name, test in screens if test(a)), None)
            if reason:
                self.exclude(a, reason)
            else:
                out.append(a)
        return out

    # ---- bad definition standard v4 ----------------------------------------------
    def outcomes(self, accounts):
        f, gov = self.facts, self.gov
        latest_record = {}
        for rec in f["snapshot_rows"]:
            if (rec["file"], rec["recno"]) in f["quarantined"]:
                continue
            key = (rec["acct"], rec["month"], rec["file"])
            if key not in latest_record or rec["recno"] > latest_record[key]["recno"]:
                latest_record[key] = rec
        forborne = defaultdict(set)
        for grant, (acct, start, end) in f["forbearance_grants"].items():
            if grant in f["forbearance_revoked"]:
                continue
            end = max([end, *f["forbearance_extensions"].get(grant, ())])
            forborne[acct].update(range(start, end + 1))
        legacy = f["legacy_accounts"]
        charge_offs = defaultdict(list)
        for event, ref, day in f["chargeoff_rows"]:
            reversal = f["reversal_dates"].get(event)
            if reversal is not None and (reversal - day).days <= 60:
                continue
            key = squeeze(ref).upper()
            charge_offs[legacy[key] if key in legacy else as_acct(ref)].append(day)
        first_closure = {}
        for acct, day in f["closure_rows"]:
            first_closure[acct] = min(day, first_closure.get(acct, day))
        corrections = (f["row_errata"], f["feed_corrections"], f["mail_corrections"])
        kept = []
        for a in accounts:
            acct, c = a["acct"], a["cohort"]
            observed = {}
            bad_month = None
            for month in range(c + 1, c + 13):
                rec = latest_record.get((acct, month, f["certified_source"].get((month, a["market"]))))
                if rec is None:
                    continue
                dpd = rec["dpd"]
                fix = [layer[(acct, month)] for layer in corrections if (acct, month) in layer]
                if fix:
                    dpd = fix[0]
                elif (acct, month) in f["system_error_months"]:
                    dpd = 0
                if dpd is None:
                    continue
                effective = 0 if month in forborne[acct] else dpd
                observed[month] = effective
                if bad_month is None and (effective >= gov.dpd_threshold[a["segment"]] or rec["status"] == "CO"):
                    bad_month = month
            hits = [month_of_day(d) for d in charge_offs.get(acct, ()) if a["day"] < d <= a["window_end"]]
            if hits:
                bad_month = min(hits + ([] if bad_month is None else [bad_month]))
            worst = max(observed.values(), default=0)
            closed = first_closure.get(acct)
            required_to = c + 12 if closed is None else min(c + 12, month_of_day(closed))
            if bad_month is not None:
                outcome = "BAD"
            elif not all(m in observed for m in range(c + 1, required_to + 1)):
                outcome = "CENSORED"
            elif closed is not None and closed < month_start(c + 6):
                outcome = "INSUFFICIENT"
            elif worst >= 30:
                outcome = "INDETERMINATE"
            else:
                outcome = "GOOD"
            self.window[acct] = (month_name(c + 1), month_name(c + 12), len(observed), worst,
                                 "" if bad_month is None else month_name(bad_month), outcome)
            if outcome in WINDOW_REASONS:
                self.exclude(a, outcome)
                continue
            label = f["audited_labels"].get(acct)
            a["bad"] = int(label == "BAD") if label is not None else int(outcome == "BAD")
            kept.append(a)
        return kept

    # ---- sampling methodology and limit management policy 4 ---------------------
    def weigh(self, accounts):
        f = self.facts
        iso = {int(numeric): alpha for numeric, alpha in f["iso_numeric"].items()}
        currency_of = {acct: iso.get(int(numeric), numeric) for acct, numeric in f["redenominated_numeric"].items()}
        for a in accounts:
            acct = a["acct"]
            pi = next((p for p in (f["inclusion_overrides"].get(acct), f["inclusion_by_account"].get(acct),
                                   f["inclusion_by_app"].get(a["app_id"]) if a["app_id"] is not None else None)
                       if p is not None), None)
            if pi is None:
                raise ValueError(f"no inclusion probability for {acct}")
            weight = 1 / Fraction(pi)
            if weight.denominator != 1:
                raise ValueError(f"design weight of {acct} is not an integer")
            a["weight"] = weight.numerator
            close = month_end(a["cohort"])
            changes = sorted((x for x in f["limit_changes"].get(acct, ()) if a["day"] <= x[0] <= close),
                             key=lambda x: (x[0], x[2]))
            limit = changes[-1][1] if changes else a["limit"]
            currency = currency_of.get(acct, MARKET_CURRENCY[a["market"]])
            fixing_day = close
            closures = f["market_closures"].get(a["market"], ())
            while fixing_day.weekday() >= 5 or fixing_day in closures:
                fixing_day -= dtm.timedelta(days=1)
            series = f["treasury_rates"].get(currency, ())
            at_or_before = [fx for fx in series if fx[0] <= fixing_day]
            if not at_or_before:
                raise ValueError(f"no {currency} fixing on or before {fixing_day}")
            _day, value, per = max(at_or_before, key=lambda fx: fx[0])
            a["exposure_text"] = decimals(Fraction(limit) * Fraction(value) / per, 2, half_up=True)
            a["band"] = 1 + sum(cut < a["score"] for cut in self.gov.cuts[a["segment"]])
        return accounts

    def run(self):
        population = self.in_scope(self.decisions())
        self.cohort = self.weigh(self.outcomes(self.policy_exclusions(self.scored(population))))
        return self


# ---- spec 8: metrics ------------------------------------------------------------
def population_block(members):
    w = sum(a["weight"] for a in members)
    wb = sum(a["weight"] for a in members if a["bad"])
    exposure = sum((a["weight"] * Fraction(Decimal(a["exposure_text"])) for a in members), Fraction(0))
    bad_exposure = sum((a["weight"] * Fraction(Decimal(a["exposure_text"])) for a in members if a["bad"]), Fraction(0))
    return {"accounts": len(members), "bads": sum(a["bad"] for a in members), "weighted_accounts": w,
            "weighted_bads": wb, "bad_rate": rate(wb, w), "exposure_eur": decimals(exposure, 2),
            "exposure_bad_rate": rate(bad_exposure, exposure)}


def discrimination_block(members):
    cells = defaultdict(lambda: [0, 0])
    for a in members:
        cells[a["score"]][a["bad"]] += a["weight"]
    scores = sorted(cells)
    goods = sum(cells[s][0] for s in scores)
    bads = sum(cells[s][1] for s in scores)
    auc = None
    if goods and bads:
        pairs, goods_up_to = Fraction(0), 0
        for s in scores:
            g, b = cells[s]
            pairs += b * (goods - goods_up_to - g + Fraction(g, 2))
            goods_up_to += g
        auc = pairs / (goods * bads)
    ks = ks_score = None
    cum_g = cum_b = 0
    for s in scores:
        cum_g += cells[s][0]
        cum_b += cells[s][1]
        gap = abs(Fraction(cum_b, bads) - Fraction(cum_g, goods)) if goods and bads else Fraction(0)
        if ks is None or gap > ks:
            ks, ks_score = gap, s
    return {"auc": None if auc is None else decimals(auc, 6), "gini": None if auc is None else decimals(2 * auc - 1, 6),
            "ks": None if ks is None else decimals(ks, 6), "ks_score": ks_score}


def stability_block(facts, cuts, segment, members):
    expected, actual = [0] * 10, [0] * 10
    for (seg, score), count in facts["dev_counts"].items():
        if seg == segment:
            expected[sum(cut < score for cut in cuts)] += count
    for a in members:
        actual[a["band"] - 1] += a["weight"]
    e_total, a_total = sum(expected), sum(actual)
    bins, terms = [], []
    with localcontext() as ctx:
        ctx.prec = 60
        for i in range(10):
            e = Fraction(expected[i], e_total) if e_total else Fraction(0)
            a = Fraction(actual[i], a_total) if a_total else Fraction(0)
            ef, af = (Decimal(x.numerator) / Decimal(x.denominator) for x in (max(e, PSI_FLOOR), max(a, PSI_FLOOR)))
            terms.append((af - ef) * (af / ef).ln())
            bins.append({"band": i + 1, "expected": decimals(e, 6), "actual": decimals(a, 6)})
        psi = sum(terms, Decimal(0))
    return {"psi": decimals(Fraction(psi), 6), "bins": bins}


def calibration_lines(facts, segment, members):
    grid = dict(facts["pd_grid"])
    grid.update((k, v) for k, v in facts["retro_pd"].items() if k in grid)
    lines = []
    for band in range(1, 11):
        inside = [a for a in members if a["band"] == band]
        w = sum(a["weight"] for a in inside)
        wb = sum(a["weight"] for a in inside if a["bad"])
        expected = sum((a["weight"] * Fraction(grid[(segment, a["score"])]) for a in inside), Fraction(0))
        lines.append(",".join(str(v) for v in (segment, band, len(inside), w, wb, decimals(expected, 6),
                                               rate(wb, w) or "", (decimals(expected / w, 6) if w else ""))))
    return lines


def as_json(obj):
    return (json.dumps(obj, indent=2, sort_keys=True) + "\n").encode("utf-8")


def as_csv(name, lines):
    return "".join(line + "\n" for line in [HEADERS[name], *lines]).encode("utf-8")


def artifacts(facts):
    recon = delivery_controls(facts)
    status = recon["status"]
    out = {"reconciliation.json": as_json(recon)}
    if status != "RECONCILED":
        out.update({name: as_csv(name, []) for name in HEADERS})
        out.update({name: as_json({"segments": {}, "status": status})
                    for name in ("population_summary.json", "discrimination.json", "psi.json")})
        return out
    review = Review(facts).run()
    cohort = sorted(review.cohort, key=lambda a: a["acct"])
    out["cohort.csv"] = as_csv("cohort.csv", [
        f"{a['acct']},{a['segment']},{a['market']},{month_name(a['cohort'])},{instant_name(a['decided'])},"
        f"{a['score']},{a['band']},{a['bad']},{a['weight']},{a['exposure_text']}" for a in cohort])
    out["exclusions.csv"] = as_csv("exclusions.csv", [f"{k},{v}" for k, v in sorted(review.excluded.items())])
    out["score_selection.csv"] = as_csv("score_selection.csv", [
        k + ",,,,," if v is None else ",".join([k, *map(str, v)]) for k, v in sorted(review.picked.items())])
    out["performance_windows.csv"] = as_csv("performance_windows.csv", [
        ",".join([k, *map(str, v)]) for k, v in sorted(review.window.items())])
    groups = {seg: [a for a in cohort if a["segment"] == seg] for seg in SEGMENTS}
    groups["ALL"] = cohort
    out["population_summary.json"] = as_json({"status": status, "segments": {
        seg: population_block(m) for seg, m in groups.items()}})
    out["discrimination.json"] = as_json({"status": status, "segments": {
        seg: discrimination_block(m) for seg, m in groups.items()}})
    out["psi.json"] = as_json({"status": status, "segments": {
        seg: stability_block(facts, review.gov.cuts[seg], seg, groups[seg]) for seg in SEGMENTS}})
    out["calibration.csv"] = as_csv("calibration.csv", [
        line for seg in SEGMENTS for line in calibration_lines(facts, seg, groups[seg])])
    return out


# Register deliveries: where the rows live, which column carries the hash key, and
# each documented column as 'column field kind' (catalogue, spec section 9).
REGISTERS = {
    "status_events_chargeoff_2025.csv": ("csv", "account_ref",
        "event_id eid id ; account_ref ref acctref ; chargeoff_date date date ; amount amount money"),
    "account_closures_2026h1.csv": ("csv", "account",
        "account acct acct ; closed_on date date ; reason reason text"),
    "applications_2025_04_reextract.csv": ("csv", "account",
        "app_id app_id id ; account acct acct ; branch branch code ; product_code code code ; decision_utc decision_utc isoutc ; limit limit money"),
    "customer_merges_2026.tsv": ("tsv", "merged_customer",
        "merged_customer merged cust ; surviving_customer survivor cust ; decision status status ; decided_on date date"),
    "employee_leavers.tsv": ("tsv", "employee_id",
        "employee_id emp id ; leave_date date date"),
    "fraud_alerts_2025.jsonl": ("jsonl", "case",
        "case case id ; account acct acct ; alert_date date date"),
    "account_closures_2025.json": ("json:closures", "account",
        "account acct acct ; closed date date"),
    "fraud_case_dispositions.json": ("json:cases", "case_id",
        "case_id case id ; disposition status status"),
    "application_withdrawals.json": ("json:withdrawals", "account",
        "account acct acct ; withdrawn_on date date"),
    "score_clock_skew_corrections.json": ("json:runs", "run",
        "run run_id id ; offset_seconds offset int"),
    "status_events_consolidated.json": ("json:events", "ref|subject",
        "type type status ; subject subject cust ; date date date ; ref ref id ; source source status"),
    "delivery_manifest.json": ("json:deliveries", "delivery_id",
        "delivery_id delivery id ; file file text ; cycle cycle text ; delivered_at delivered isoutc ; status status status"),
    "snapshot_corrections_feed.xml": ("xml:correction", "account",
        "seq seq int ; account acct acct ; period month month ; dpd dpd int"),
    "deceased_notifications_feed.xml": ("xml:notification", "customer",
        "customer cust cust ; notified date date"),
    "fraud_alerts_2026.xml": ("xml:alert", "case",
        "case case id ; account acct acct ; raised date date"),
    "limit_amendments_2025.xlsx": ("xlsx:H1,H2", "account",
        "amendment_id id id ; account acct acct ; effective_serial date serial ; new_limit limit money"),
    "product_migrations_2025.xlsx": ("xlsx:migrations", "account",
        "migration_id id id ; account acct acct ; from_code from code ; to_code to code ; effective date date"),
    "governance_precedence_policy.docx": ("docx", "cr",
        "cr cr id ; subject subject text ; status status status ; decided_on date date"),
    "exclusion_policy.docx": ("docx", "employee",
        "employee emp id ; customer cust cust ; start_date date date"),
    "customer_merge_decisions.docx": ("docx", "merged_customer",
        "merged_customer merged cust ; surviving_customer survivor cust ; decision status status ; decided_on date date"),
    "sampling_methodology.docx": ("docx", "account",
        "account acct acct ; inclusion_probability pi pi ; status status status"),
    "bad_definition_standard.docx": ("docx", "grant",
        "grant gid id ; account acct acct ; from_month start month ; to_month end month"),
    "limit_management_policy.docx": ("docx", "account",
        "amendment_id id id ; account acct acct ; effective date date ; new_limit limit money"),
    "bad_definition_standard_v5.docx": ("docx", "grant",
        "grant gid id ; revoked_on date date ; account acct acct ; status status status"),
    "consumer_redress_programme.pdf": ("pdf", "account",
        "account acct acct ; programme programme code"),
    "deceased_notifications_register.pdf": ("pdf", "customer",
        "customer cust cust ; notified date date"),
    "audit_label_confirmations.pdf": ("pdf", "account",
        "account acct acct ; audited_label label status"),
    "regulatory_exclusion_letter_2026.pdf": ("pdf", "account",
        "account acct acct ; notice_date date date"),
    "forbearance_extensions_register.pdf": ("pdf", "grant",
        "grant gid id ; new_to_month end month"),
    "litigation_hold_register.html": ("html", "account",
        "hold_id hold id ; account acct acct ; from from date ; to to enddate"),
    "branch_directory.html": ("html", "branch",
        "market market status ; branch code id ; valid_from from date ; valid_to to enddate"),
    "branch_directory_2026.html": ("html", "branch_2026",
        "branch_2026 new id ; branch_2025 old id ; booking_market market status ; branch_name bname text ; opened_2026 opened date ; status_2026 bstatus status"),
}


def register_columns(name):
    return [tuple(part.split()) for part in REGISTERS[name][2].split(" ; ")]


# ---------------------------------------------------------------- readers ---
def read_text(path, encoding="utf-8"):
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode(encoding)


def read_delimited(path, delim, encoding="utf-8"):
    """Rows as dicts keyed by header names; honours comments, controls and re-emitted headers."""
    text = read_text(path, encoding)
    control = None
    body = []
    for line in io.StringIO(text, newline=""):
        if line.startswith("# CONTROL "):
            control = parse_control_text(line[len("# CONTROL "):])
            continue
        body.append(line)
    rows = []
    header = None
    for raw in csv.reader(io.StringIO("".join(ln for ln in body if not ln.startswith("#")), newline=""), delimiter=delim):
        if not raw or all(c == "" for c in raw):
            continue
        if header is None:
            header = raw
            names = set(header)
            continue
        if set(raw) == names and len(raw) == len(header):
            header = raw
            continue
        while len(raw) > len(header) and raw[-1] == "":
            raw = raw[:-1]
        rows.append(dict(zip(header, raw)))
    return rows, control


def read_jsonl(path):
    rows, control = [], None
    for line in read_text(path).splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        if "_control" in obj:
            control = obj["_control"]
        elif "_header" in obj:
            continue
        else:
            rows.append(obj)
    return rows, control


def read_fixed(path, encoding="latin-1"):
    rows, control = [], None
    for line in read_text(path, encoding).splitlines():
        if line.startswith("10"):
            rows.append(line)
        elif line.startswith("99"):
            control = parse_control_text(line[2:])
    return rows, control


NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def office_control(zf):
    root = ET.fromstring(zf.read("docProps/custom.xml"))
    out = {}
    for prop in root:
        out[prop.get("name")] = "".join(prop.itertext())
    return out


def read_xlsx(path):
    with zipfile.ZipFile(path) as zf:
        strings = []
        if "xl/sharedStrings.xml" in zf.namelist():
            for si in ET.fromstring(zf.read("xl/sharedStrings.xml")):
                strings.append("".join(t.text or "" for t in si.iter(NS_MAIN + "t")))
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        names = [s.get("name") for s in wb.iter(NS_MAIN + "sheet")]
        sheets = {}
        for i, nm in enumerate(names, start=1):
            root = ET.fromstring(zf.read(f"xl/worksheets/sheet{i}.xml"))
            rows = []
            for row in root.iter(NS_MAIN + "row"):
                cells = {}
                for c in row.iter(NS_MAIN + "c"):
                    ref = c.get("r")
                    col = re.match(r"[A-Z]+", ref).group(0)
                    idx = 0
                    for ch in col:
                        idx = idx * 26 + ord(ch) - 64
                    v = c.find(NS_MAIN + "v")
                    val = v.text if v is not None else ""
                    if c.get("t") == "s":
                        val = strings[int(val)]
                    cells[idx - 1] = val
                width = max(cells) + 1 if cells else 0
                rows.append([cells.get(j, "") for j in range(width)])
            header = rows[0]
            sheets[nm] = [dict(zip(header, r + [""] * (len(header) - len(r)))) for r in rows[1:] if any(x != "" for x in r)]
        control = office_control(zf)
    return sheets, control


NS_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def read_docx_tables(path):
    with zipfile.ZipFile(path) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))
        control = office_control(zf)
    tables = []
    for tbl in root.iter(NS_W + "tbl"):
        rows = []
        for tr in tbl.iter(NS_W + "tr"):
            cells = []
            for tc in tr.iter(NS_W + "tc"):
                parts = []
                for node in tc.iter():
                    if node.tag == NS_W + "t":
                        parts.append(node.text or "")
                    elif node.tag == NS_W + "br":
                        parts.append("\n")
                cells.append("".join(parts))
            rows.append(cells)
        tables.append(rows)
    records = []
    header = None
    for t in tables:
        if header is None:
            header = t[0]
        for r in t[1:]:
            if r == header:
                continue
            records.append(dict(zip(header, r)))
    return records, control


PDF_TJ = re.compile(r"\(((?:\\.|[^\\)])*)\) Tj".encode())


def pdf_lines(path):
    data = path.read_bytes()
    lines = []
    for m in re.finditer("stream\n(.*?)\nendstream".encode(), data, re.S):
        for tm in re.finditer(PDF_TJ, m.group(1)):
            raw = tm.group(1)
            raw = re.sub(rb"\\(.)", lambda x: x.group(1), raw)
            lines.append(raw.decode("latin-1"))
    return lines


def read_pdf_table(path, header):
    lines = pdf_lines(path)
    hdr = " | ".join(header)
    rows, control, active = [], None, False
    for ln in lines:
        if ln.startswith("Delivery control: "):
            control = parse_control_text(ln[len("Delivery control: "):])
            continue
        if ln == hdr:
            active = True
            continue
        if active and " | " in ln:
            parts = ln.split(" | ")
            if len(parts) == len(header):
                rows.append(dict(zip(header, parts)))
    return rows, control, lines


class _Tables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.rows, self.cur, self.cell, self.meta, self.in_reg, self.is_th = [], None, None, {}, False, False
        self.span = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("name") == "delivery-control":
            self.meta = parse_control_text(a.get("content", ""))
        if tag == "table" and a.get("id") == "register":
            self.in_reg = True
        if self.in_reg and tag == "tr":
            self.cur, self.is_th = [], False
        if self.in_reg and tag in ("td", "th"):
            self.cell = []
            self.span = int(a.get("rowspan", "1"))
            self.is_th = self.is_th or tag == "th"

    def handle_endtag(self, tag):
        if self.in_reg and tag in ("td", "th") and self.cell is not None:
            self.cur.append(("".join(self.cell), self.span))
            self.cell = None
        if self.in_reg and tag == "tr" and self.cur is not None:
            self.rows.append((self.is_th, self.cur))
            self.cur = None
        if tag == "table":
            self.in_reg = False

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)


def read_html_table(path):
    p = _Tables()
    p.feed(read_text(path))
    header, out, pending = None, [], {}
    for is_th, cells in p.rows:
        if is_th:
            header = [c for c, _ in cells]
            continue
        vals, it = [], iter(cells)
        for col in range(len(header)):
            if col in pending:
                text, left = pending[col]
                vals.append(text)
                pending[col] = (text, left - 1)
                if left - 1 == 0:
                    del pending[col]
                continue
            text, span = next(it)
            vals.append(text)
            if span > 1:
                pending[col] = (text, span - 1)
        out.append(dict(zip(header, [v.replace("\u00a0", " ").strip() for v in vals])))
    return out, p.meta


def read_sqlite(path):
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    tables = {}
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid"):
        cur = con.execute(f"SELECT * FROM {name} ORDER BY rowid")
        cols = [d[0] for d in cur.description]
        tables[name] = [dict(zip(cols, r)) for r in cur]
    cur = con.execute("SELECT * FROM delivery_control")
    control = dict(zip([d[0] for d in cur.description], cur.fetchone()))
    con.close()
    return tables, control


def read_parquet(path):
    import pyarrow.parquet as pq
    t = pq.read_table(path)
    meta = json.loads(t.schema.metadata["delivery_control".encode()])
    return t.to_pylist(), meta


def _yaml_strip_comment(line):
    out, quote = [], None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1].isspace()):
            break
        out.append(ch)
    return "".join(out).rstrip()


def _yaml_scalar(text):
    t = text.strip()
    if len(t) >= 2 and t[0] == t[-1] and t[0] in "'\"":
        return t[1:-1]
    return t


def _yaml_flow(text):
    body = text.strip()[1:-1]
    parts, cur, quote = [], [], None
    for ch in body:
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == ",":
            parts.append("".join(cur))
            cur = []
            continue
        cur.append(ch)
    parts.append("".join(cur))
    out = {}
    for part in parts:
        k, _, v = part.partition(":")
        out[k.strip()] = _yaml_scalar(v)
    return out


def read_yaml_inclusion(path):
    """Entries of the inclusion list and the delivery_control mapping; every scalar stays a string."""
    entries, control, cur, section = [], {}, None, None
    for raw in read_text(path).splitlines():
        line = _yaml_strip_comment(raw)
        if not line.strip() or line.strip() == "---":
            continue
        if not line.startswith(" "):
            section = line.split(":")[0].strip()
            continue
        s = line.strip()
        if section == "inclusion":
            if s.startswith("- {"):
                entries.append(_yaml_flow(s[2:]))
                cur = None
                continue
            if s.startswith("- "):
                cur = {}
                entries.append(cur)
                s = s[2:]
            k, _, v = s.partition(":")
            cur[k.strip()] = _yaml_scalar(v)
        elif section == "delivery_control":
            k, _, v = s.partition(":")
            control[k.strip()] = _yaml_scalar(v)
    return entries, control


def read_ini(path):
    cp = configparser.ConfigParser(interpolation=None, default_section="DEFAULT", inline_comment_prefixes=None)
    cp.optionxform = str
    cp.read_string(read_text(path))
    defaults = set(cp.defaults())
    sections = {}
    for sec in cp.sections():
        sections[sec] = {k: v for k, v in cp.items(sec, raw=True) if k not in defaults}
    return sections


def read_mbox(path):
    import email.utils as eu
    box = mailbox.mbox(str(path), create=False)
    msgs, control = [], None
    for m in box:
        subject = (m["Subject"] or "").strip()
        payload = m.get_payload(decode=False)
        payload = "\n".join(ln[1:] if ln.startswith(">From ") else ln for ln in payload.split("\n"))
        if (m["Content-Transfer-Encoding"] or "").lower() == "quoted-printable":
            payload = quopri.decodestring(payload.encode("ascii")).decode("utf-8")
        if subject.upper() == "DELIVERY CONTROL":
            control = parse_control_text(payload)
            continue
        msgs.append({"subject": subject, "msgid": (m["Message-ID"] or "").strip(),
                     "ts": int(eu.parsedate_to_datetime(m["Date"]).timestamp()), "body": payload})
    return msgs, control


def read_ics(path):
    raw = read_text(path).replace("\r\n", "\n")
    unfolded = re.sub(r"\n[ \t]", "", raw)
    events, cur, control = [], None, None
    for line in unfolded.split("\n"):
        if line.startswith("X-DELIVERY-CONTROL:"):
            control = parse_control_text(line.split(":", 1)[1])
        elif line == "BEGIN:VEVENT":
            cur = {}
        elif line == "END:VEVENT":
            events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            k, v = line.split(":", 1)
            cur[k.split(";")[0]] = (k, v)
    return events, control


def _strip_ns(tag):
    return tag.split("}", 1)[1] if "}" in tag else tag


def read_register(path, name):
    """Typed rows, raw hash keys and the control block of a register delivery (layouts in REGISTERS)."""
    container, cols = REGISTERS[name][0], register_columns(name)
    base = container.split(":")[0]
    header = [c for c, _f, _k in cols]
    if base in ("csv", "tsv"):
        raw, control = read_delimited(path, "\t" if base == "tsv" else ",")
    elif base == "jsonl":
        raw, control = read_jsonl(path)
    elif base == "json":
        data = json.loads(read_text(path))
        raw, control = data[container.split(":")[1]], data["control"]
    elif base == "xml":
        root = ET.parse(path).getroot()
        tag = container.split(":")[1]
        raw, control = [], None
        for el in root:
            t = _strip_ns(el.tag)
            if t == tag:
                raw.append({_strip_ns(ch.tag): (ch.text or "") for ch in el})
            elif t == "control":
                control = dict(el.attrib)
    elif base == "xlsx":
        sheets, control = read_xlsx(path)
        raw = [r for sh in container.split(":")[1].split(",") for r in sheets[sh]]
    elif base == "docx":
        raw, control = read_docx_tables(path)
    elif base == "pdf":
        raw, control, _lines = read_pdf_table(path, header)
    else:
        raw, control = read_html_table(path)
    typed = []
    for r in raw:
        rec = {}
        for col, field, kind in cols:
            v = r.get(col)
            rec[field] = KIND[kind]("" if v is None else v)
        typed.append(rec)
    hc = REGISTERS[name][1].split("|")
    keys = [next((r.get(c) for c in hc if r.get(c)), "") or "" for r in raw]
    return typed, keys, control


# ------------------------------------------------------------ estate model ---
APP_PARTS = ["applications_2025_01.csv", "applications_2025_02.tsv", "applications_2025_03.txt",
             "applications_2025_04.csv", "applications_2025_05.xlsx", "applications_2025_06.jsonl"]
SNAP_CSV = {
    "snapshots_2025_02.csv": (",", ("account", "period", "dpd", "status"), {"OPEN": "OPEN", "CLOSED": "CLOSED", "CO": "CO"}),
    "snapshots_2025_03.tsv": ("\t", ("acct", "period_yyyymm", "days_past_due", "status_cd"), {"O": "OPEN", "C": "CLOSED", "W": "CO"}),
    "snapshots_2025_06_a.csv": (";", ("konto", "okres", "dpd", "status"), {"A": "OPEN", "Z": "CLOSED", "S": "CO"}),
    "snapshots_2025_08_a.csv": (",", ("account", "period", "dpd", "status"), {"OPEN": "OPEN", "CLOSED": "CLOSED", "CO": "CO"}),
    "snapshots_2025_08_b.tsv": ("\t", ("acct", "period_yyyymm", "days_past_due", "status_cd"), {"O": "OPEN", "C": "CLOSED", "W": "CO"}),
    "snapshots_2025_10_a.csv": (",", ("account", "period", "dpd", "status"), {"OPEN": "OPEN", "CLOSED": "CLOSED", "CO": "CO"}),
    "snapshots_2025_10_b.tsv": ("\t", ("acct", "period_yyyymm", "days_past_due", "status_cd"), {"O": "OPEN", "C": "CLOSED", "W": "CO"}),
    "snapshots_2025_10_b_restated.tsv": ("\t", ("acct", "period_yyyymm", "days_past_due", "status_cd"), {"O": "OPEN", "C": "CLOSED", "W": "CO"}),
    "snapshots_2025_11_a.csv": (",", ("account", "period", "dpd", "status"), {"OPEN": "OPEN", "CLOSED": "CLOSED", "CO": "CO"}),
    "snapshots_2025_11_a_rev2.csv": (",", ("account", "period", "dpd", "status"), {"OPEN": "OPEN", "CLOSED": "CLOSED", "CO": "CO"}),
    "snapshots_2026_02_a.csv": (",", ("account", "period", "dpd", "status"), {"OPEN": "OPEN", "CLOSED": "CLOSED", "CO": "CO"}),
    "snapshots_2026_06.csv": (",", ("account", "period", "dpd", "status"), {"OPEN": "OPEN", "CLOSED": "CLOSED", "CO": "CO"}),
}
SNAP_JSONL = ["snapshots_2025_06_b.jsonl", "snapshots_2026_02_b.jsonl"]
SNAP_PARQUET = ["snapshots_2025_04.parquet", "snapshots_2025_11_b.parquet", "snapshots_2026_05_a.parquet"]
SNAP_XLSX = ["snapshots_2025_05.xlsx", "snapshots_2025_09.xlsx", "snapshots_2025_12.xlsx", "snapshots_2026_03.xlsx"]
SNAP_DB = ["servicing_snapshots_2025q3.db", "servicing_snapshots_2026q1.db"]
SNAP_FW = ["snapshots_2026_04.txt", "snapshots_2026_05_b.txt"]
SCORE_LOGS = ["scoring_engine_node1.log", "scoring_engine_node2.log", "scoring_engine_node3.log", "scoring_engine_node4.log"]
SCORE_JSONL = ["score_batches_2025_q1.jsonl", "score_batches_2025_q2_a.jsonl", "score_batches_2025_q2_b.jsonl",
               "score_batches_2025_q2_c.jsonl"]
SCORE_LINE = re.compile(r"^(\S+) +\S+ +\S+ +(SCORE|VOID) (.*)$")


def snap_dpd(raw):
    if raw is None:
        return None
    t = squeeze(raw)
    if t in ("", "-1", "N/A", "null", "9999"):
        return None
    return int(t)


class Estate:
    def __init__(self, root):
        self.root = Path(root)
        self.ring_files = {}
        self.L = {}
        self.missing = []

    def path(self, name):
        return self.root / name

    def ctl(self, name, records, keys, control):
        self.ring_files[name] = {"control_id": None, "rows": len(records), "hash": sum(digit_value(k) for k in keys), "acks": []}
        if control:
            cid, acks = control_tuple(control)
            self.ring_files[name]["control_id"] = cid
            self.ring_files[name]["acks"] = acks


def load(root):
    E = Estate(root)
    L = E.L
    loaders = [_registers, _apps, _snapshots, _scores, _runs, _others, _model, _corrections, _manifest]
    for fn in loaders:
        fn(E)
    L["control_ring"] = [v for v in E.ring_files.values() if v["control_id"]]
    return L


def guarded(fn):
    def run(E, *names):
        for name in names:
            p = E.path(name)
            if not p.is_file():
                E.missing.append(name)
                continue
            try:
                fn(E, name, p)
            except (OSError, ValueError, KeyError, IndexError, zipfile.BadZipFile, ET.ParseError, sqlite3.Error,
                    tomllib.TOMLDecodeError, configparser.Error) as exc:
                E.missing.append(name)
                print(f"monitor: cannot read {name}: {exc}", file=sys.stderr)
    return run


def _app_rec(E, name, recno, acct, cust, app_id, branch, code, utc, local, limit, rev, received):
    E.L.setdefault("application_rows", []).append({
        "acct": as_acct(acct), "cust": as_cust(cust), "app_id": as_id(app_id) if app_id else None, "branch": as_id(branch),
        "product_code": as_code(code),
        "product_basis": "current" if name == "applications_2025_05.xlsx" else "decision", "decision_utc": utc,
        "decision_local": local, "limit": as_money(limit), "revision": as_int(rev), "received_utc": received, "file": name, "recno": recno,
        "order": recno})


@guarded
def read_app(E, name, p):
    if name == "applications_2025_01.csv":
        rows, c = read_delimited(p, ",")
        for i, r in enumerate(rows, 1):
            _app_rec(E, name, i, r["account_ref"], r["customer_ref"], r["app_id"], r["branch_code"], r["product_code"], None,
                     as_local(r["decided_at_local"]), r["limit_amount"], r["revision"], as_instant(r["received_at_utc"]))
        E.ctl(name, rows, [r["account_ref"] for r in rows], c)
    elif name == "applications_2025_02.tsv":
        rows, c = read_delimited(p, "\t")
        for i, r in enumerate(rows, 1):
            _app_rec(E, name, i, r["acct"], r["cust"], r["app_id"], r["branch"], r["product"], as_instant(r["decision_utc"]), None,
                     r["limit"], r["rev"], as_instant(r["received_utc"]))
        E.ctl(name, rows, [r["acct"] for r in rows], c)
    elif name == "applications_2025_03.txt":
        rows, c = read_fixed(p)
        keys = []
        for i, ln in enumerate(rows, 1):
            acct = ln[13:25]
            keys.append(acct)
            _app_rec(E, name, i, acct, ln[25:37], ln[2:13], ln[37:43], ln[43:51], None,
                     as_local(ln[51:65], "%Y%m%d%H%M%S"), Decimal(int(ln[65:78])) / 100, ln[78:80],
                     as_local(ln[80:94], "%Y%m%d%H%M%S"))
        E.ctl(name, rows, keys, c)
    elif name == "applications_2025_04.csv":
        rows, c = read_delimited(p, ";")
        for i, r in enumerate(rows, 1):
            _app_rec(E, name, i, r["konto"], r["kunde"], None, r["filial"], r["produkt"], as_instant(r["entscheidung"]), None,
                     r["limit"], r["revision"], as_instant(r["eingang_utc"]))
        E.ctl(name, rows, [r["konto"] for r in rows], c)
    elif name == "applications_2025_05.xlsx":
        sheets, c = read_xlsx(p)
        rows = sheets["applications"]
        for i, r in enumerate(rows, 1):
            _app_rec(E, name, i, r["account"], r["customer"], r["app_id"], r["branch"], r["product_code_current"], None,
                     as_serial_instant(r["decided_local"]), r["limit"], r["revision"], as_instant(r["received_utc"]))
        E.ctl(name, rows, [r["account"] for r in rows], c)
    else:
        rows, c = read_jsonl(p)
        for i, r in enumerate(rows, 1):
            _app_rec(E, name, i, r["acct"], r["cust"], r["app"], r["branch"], r["product"], int(r["decided_ms"]) // 1000, None,
                     r["limit"], r["rev"], int(r["received_ms"]) // 1000)
        E.ctl(name, rows, [r["acct"] for r in rows], c)


def _apps(E):
    E.L.setdefault("application_rows", [])
    read_app(E, *APP_PARTS)


def _snap(E, name, recno, acct, period, dpd, status):
    dpd = snap_dpd(dpd)
    if dpd == 999:
        dpd, status = 180, "CO"
    E.L.setdefault("snapshot_rows", []).append({"acct": as_acct(acct), "month": as_month(period), "dpd": dpd, "status": as_upper(status),
                                        "file": name, "recno": recno})


@guarded
def read_snap(E, name, p):
    if name in SNAP_CSV:
        delim, (ka, kp, kd, ks), smap = SNAP_CSV[name]
        rows, c = read_delimited(p, delim)
        for i, r in enumerate(rows, 1):
            _snap(E, name, i, r[ka], r[kp], r[kd], smap[as_upper(r[ks])])
            if name == "snapshots_2025_10_b_restated.tsv" and as_upper(r.get("dpd_reason", "")) == "SYSTEM_ERROR":
                E.L.setdefault("system_error_months", set()).add((as_acct(r[ka]), as_month(r[kp])))
        E.ctl(name, rows, [r[ka] for r in rows], c)
    elif name in SNAP_JSONL:
        rows, c = read_jsonl(p)
        for i, r in enumerate(rows, 1):
            _snap(E, name, i, r["a"], r["p"], r["dpd"], r["s"])
        E.ctl(name, rows, [r["a"] for r in rows], c)
    elif name in SNAP_PARQUET:
        rows, c = read_parquet(p)
        for i, r in enumerate(rows, 1):
            _snap(E, name, i, r["account"], str(r["period"]), r["dpd"], r["status"])
        E.ctl(name, rows, [r["account"] for r in rows], c)
    elif name in SNAP_XLSX:
        sheets, c = read_xlsx(p)
        rows = sheets["A"] + sheets["B"]
        for i, r in enumerate(rows, 1):
            d = as_serial_date(r["period"])
            _snap(E, name, i, r["account"], f"{d.year:04d}{d.month:02d}", r["dpd"], r["status"])
        E.ctl(name, rows, [r["account"] for r in rows], c)
    elif name in SNAP_DB:
        tables, c = read_sqlite(p)
        rows = [r for t in sorted(tables) for r in tables[t]]
        for i, r in enumerate(rows, 1):
            _snap(E, name, i, r["account"], r["period"], r["dpd"], r["status"])
        E.ctl(name, rows, [r["account"] for r in rows], c)
    else:
        rows, c = read_fixed(p)
        for i, ln in enumerate(rows, 1):
            _snap(E, name, i, ln[2:14], ln[14:20], ln[20:24], {"O": "OPEN", "C": "CLOSED", "W": "CO"}[ln[24]])
        E.ctl(name, rows, [ln[2:14] for ln in rows], c)


@guarded
def read_replica(E, name, p):
    tables, c = read_sqlite(p)
    keys = []
    count = 0
    for t in sorted(tables):
        for r in tables[t]:
            count += 1
            if t == "cycle_controls":
                keys.append(int(r["value"]) % 10000000)
            else:
                keys.append(r["account"])
                _snap(E, name, count, r["account"], r["period"], r["dpd"], r["status"])
    E.ctl(name, keys, keys, c)


def _snapshots(E):
    E.L.setdefault("snapshot_rows", [])
    E.L.setdefault("system_error_months", set())
    read_snap(E, *(list(SNAP_CSV) + SNAP_JSONL + SNAP_PARQUET + SNAP_XLSX + SNAP_DB + SNAP_FW))
    read_replica(E, "snapshots_servicing_replica.db")


def _score(E, name, recno, eid, acct, run, ts, score):
    E.L.setdefault("score_events", []).append({"event_id": as_id(eid), "event_num": digit_value(eid), "acct": as_acct(acct), "run_id": as_id(run),
                                         "score_ts": ts, "score": as_int(score), "file": name, "recno": recno})


@guarded
def read_score(E, name, p):
    if name.endswith(".log"):
        recs = []
        for line in read_text(p).splitlines():
            m = SCORE_LINE.match(line)
            if not m:
                continue
            kv = dict(part.split("=", 1) for part in m.group(3).split(" ") if "=" in part)
            recs.append((m.group(1), m.group(2), kv))
        keys = []
        for i, (ts, kind, kv) in enumerate(recs, 1):
            if kind == "VOID":
                E.L.setdefault("voided_runs", set()).add(as_id(kv["run"]))
                keys.append(kv["run"])
                continue
            keys.append(kv["acct"])
            stamp = as_instant(kv["orig_ts"]) if "orig_ts" in kv else as_instant(ts)
            _score(E, name, i, kv["event"], kv["acct"], kv["run"], stamp, kv["score"])
        lines = read_text(p).splitlines()
        c = next((parse_control_text(ln[len("# CONTROL "):]) for ln in lines if ln.startswith("# CONTROL ")), None)
        E.ctl(name, recs, keys, c)
    elif name in SCORE_JSONL:
        rows, c = read_jsonl(p)
        for i, r in enumerate(rows, 1):
            _score(E, name, i, r["event"], r["acct"] or "", r["run"], int(float(r["ts_ms"])) // 1000, r["score"])
        E.ctl(name, rows, [r["acct"] for r in rows], c)
    elif name == "score_events_node5.parquet":
        rows, c = read_parquet(p)
        for i, r in enumerate(rows, 1):
            _score(E, name, i, r["event_id"], r["account"], r["run_id"], int(r["scored_at_s"]), r["score"])
        E.ctl(name, rows, [r["account"] for r in rows], c)
    elif name == "score_events_node6.xml":
        root = ET.parse(p).getroot()
        ns = "{urn:example-bank:scoring:v4}"
        rows = root.findall(ns + "event")
        for i, ev in enumerate(rows, 1):
            _score(E, name, i, ev.get("id"), ev.find(ns + "account").text, ev.get("run"), as_instant(ev.find(ns + "scoredAt").text),
                   ev.find(ns + "score").text)
        c = root.find(ns + "control")
        E.ctl(name, rows, [ev.find(ns + "account").text for ev in rows], dict(c.attrib) if c is not None else None)
    elif name == "score_events_node7.tsv":
        rows, c = read_delimited(p, "\t")
        for i, r in enumerate(rows, 1):
            _score(E, name, i, r["event_id"], r["account"], r["run_id"], as_serial_instant(r["scored_at_serial_utc"]), r["score"])
        E.ctl(name, rows, [r["account"] for r in rows], c)
    else:
        rows, c = read_delimited(p, ",")
        for i, r in enumerate(rows, 1):
            _score(E, name, i, r["event_id"], r["account"], r["run_id"], as_instant(r["scored_at"]), r["score"])
        E.ctl(name, rows, [r["account"] for r in rows], c)


def _scores(E):
    E.L.setdefault("score_events", [])
    E.L.setdefault("voided_runs", set())
    read_score(E, *(SCORE_LOGS + ["scoring_engine_node9.log"] + SCORE_JSONL +
                    ["score_events_node5.parquet", "score_events_node6.xml", "score_events_node7.tsv", "score_events_backfill.csv"]))


@guarded
def read_toml_file(E, name, p):
    data = tomllib.loads(read_text(p))
    c = {k: str(v) for k, v in data["delivery_control"].items()}
    if name == "model_registry_v4_1.toml":
        pts = data.get("calibration_point", [])
        E.L["registry_withdrawals"] = [(w["model"].strip(), as_date(w["withdrawn_from"]), as_id(w.get("change_request", "")))
                                   for w in data.get("withdrawal", [])]
        E.ctl(name, pts, [pt["score"] for pt in pts], c)
        return
    runs = data.get("run", [])
    for r in runs:
        E.L.setdefault("run_register", {})[as_id(r["run_id"])] = (str(r["node"]).strip(), r["model"].strip(), as_upper(r["status"]))
    if name == "model_registry_v4.toml":
        E.L["version_approvals"] = [(a["model"].strip(), {x.strip().upper() for x in a["segments"]}, as_date(a["effective_from"]),
                             as_date(a["effective_to"]) if a.get("effective_to") else None) for a in data.get("approval", [])]
    E.ctl(name, runs, [r["run_id"] for r in runs], c)


def _runs(E):
    E.L.setdefault("run_register", {})
    E.L.setdefault("version_approvals", [])
    read_toml_file(E, "model_registry_v4.toml", "scoring_runs_2025q2.toml", "model_registry_v4_1.toml")


@guarded
def read_reg(E, name, p):
    rows, keys, control = read_register(p, name)
    E.ctl(name, rows, keys, control)
    E.reg[name] = rows


def reg(E, name):
    return E.reg.get(name, [])


def _registers(E):
    E.reg = {}
    read_reg(E, *REGISTERS)
    L = E.L
    L["chargeoff_rows"] = [(r["eid"], r["ref"], r["date"]) for f in ("status_events_chargeoff_2025.csv",) for r in reg(E, f)]
    L["april_app_ids"] = {r["app_id"]: r["acct"] for r in reg(E, "applications_2025_04_reextract.csv")}
    L["reversal_dates"] = {r["ref"]: r["date"] for r in reg(E, "status_events_consolidated.json") if r["type"] == "CO_REVERSAL"}
    dec_ = [(r["subject"], r["date"]) for r in reg(E, "status_events_consolidated.json")
            if r["type"] == "DECEASED" and r["source"] == "CIVIL_REGISTRY"]
    dec_ += [(r["cust"], r["date"]) for f in ("deceased_notifications_feed.xml", "deceased_notifications_register.pdf") for r in reg(E, f)]
    L["death_notices"] = [(as_cust(c), d) for c, d in dec_]
    L["closure_rows"] = [(r["acct"], r["date"]) for f in ("account_closures_2025.json", "account_closures_2026h1.csv") for r in reg(E, f)]
    L["fraud_alert_rows"] = [(r["case"], r["acct"], r["date"]) for f in ("fraud_alerts_2025.jsonl", "fraud_alerts_2026.xml") for r in reg(E, f)]
    L["case_disposition"] = {r["case"]: r["status"] for r in reg(E, "fraud_case_dispositions.json")}
    wd = {}
    for r in reg(E, "application_withdrawals.json"):
        wd.setdefault(r["acct"], []).append(r["date"])
    L["withdrawal_dates"] = wd
    L["clock_offsets"] = {r["run_id"]: r["offset"] for r in reg(E, "score_clock_skew_corrections.json")}
    ss, sl = {}, {}
    for r in reg(E, "exclusion_policy.docx"):
        ss.setdefault(r["emp"], []).append((r["cust"], r["date"]))
    for r in reg(E, "employee_leavers.tsv"):
        sl.setdefault(r["emp"], []).append(r["date"])
    L["employee_starts"], L["employee_leaves"] = ss, sl
    holds = {}
    for r in reg(E, "litigation_hold_register.html"):
        holds.setdefault(r["acct"], []).append((r["from"], r["to"]))
    L["hold_spans"] = holds
    L["insolvency_notices"] = {r["acct"]: r["date"] for r in reg(E, "regulatory_exclusion_letter_2026.pdf")}
    L["redress_members"] = {r["acct"] for r in reg(E, "consumer_redress_programme.pdf")}
    L["audited_labels"] = {r["acct"]: r["label"] for r in reg(E, "audit_label_confirmations.pdf")}
    L["merge_rows"] = [(r["merged"], r["survivor"], r["status"], r["date"])
                    for f in ("customer_merge_decisions.docx", "customer_merges_2026.tsv") for r in reg(E, f)]
    L["forbearance_grants"] = {r["gid"]: (r["acct"], r["start"], r["end"]) for r in reg(E, "bad_definition_standard.docx")}
    ext = {}
    for r in reg(E, "forbearance_extensions_register.pdf"):
        ext.setdefault(r["gid"], []).append(r["end"])
    L["forbearance_extensions"] = ext
    L["forbearance_revoked"] = {r["gid"] for r in reg(E, "bad_definition_standard_v5.docx")}
    L["inclusion_overrides"] = {r["acct"]: r["pi"] for r in reg(E, "sampling_methodology.docx") if r["status"] == "APPROVED"}
    la = {}
    for f in ("limit_amendments_2025.xlsx", "limit_management_policy.docx"):
        for r in reg(E, f):
            la.setdefault(r["acct"], []).append((r["date"], r["limit"], r["id"]))
    L["limit_changes"] = la
    mig = {}
    for r in reg(E, "product_migrations_2025.xlsx"):
        mig.setdefault(r["acct"], []).append((r["from"], r["to"], r["date"], r["id"]))
    L["product_moves"] = mig
    xc = {}
    for r in sorted(reg(E, "snapshot_corrections_feed.xml"), key=lambda r: r["seq"]):
        xc[(r["acct"], r["month"])] = r["dpd"]
    L["feed_corrections"] = xc
    br = {}
    for r in reg(E, "branch_directory.html"):
        br.setdefault(r["code"], []).append((r["market"], r["from"], r["to"]))
    L["branch_rows"] = br
    L["branch_recode"] = {r["new"]: r["old"] for r in reg(E, "branch_directory_2026.html")}
    L["change_requests"] = [(r["cr"], r["status"], r["date"]) for r in reg(E, "governance_precedence_policy.docx")]
    L["manifest_rows"] = [(r["delivery"], r["file"], r["cycle"], r["delivered"]) for r in reg(E, "delivery_manifest.json")]


@guarded
def read_other(E, name, p):
    L = E.L
    if name == "status_events_chargeoff_2025.csv":
        return
    if name == "chargeoff_events_2026.parquet":
        rows, c = read_parquet(p)
        for r in rows:
            L.setdefault("chargeoff_rows", []).append((as_id(r["event_id"]), r["account"], r["chargeoff_date"]))
        E.ctl(name, rows, [r["account"] for r in rows], c)
    elif name == "applications_master_2025h1.parquet":
        rows, c = read_parquet(p)
        L["reversed_withdrawals"] = {as_acct(r["account"]) for r in rows if r["withdrawal_reversed"]}
        E.ctl(name, rows, [r["account"] for r in rows], c)
    elif name == "customer_master.db":
        tables, c = read_sqlite(p)
        L["customer_aliases"] = {as_cust(r["alias"]): as_cust(r["master"]) for r in tables["customer_alias"]}
        E.ctl(name, tables["customer_alias"] + tables["customers"],
              [r["alias"] for r in tables["customer_alias"]] + [r["customer"] for r in tables["customers"]], c)
    elif name == "merge_candidates_ml.xlsx":
        sheets, c = read_xlsx(p)
        L["legacy_customers"] = {as_id(r["legacy_customer"]): as_cust(r["customer"]) for r in sheets["legacy_refs"]}
        E.ctl(name, sheets["candidates"] + sheets["legacy_refs"],
              [r["customer_a"] for r in sheets["candidates"]] + [r["legacy_customer"] for r in sheets["legacy_refs"]], c)
    elif name.endswith(".yaml"):
        entries, c = read_yaml_inclusion(p)
        for e in entries:
            key = e["key"].strip()
            if name == "sampling_design_v2.yaml" and as_month(e["cohort"]) != 2025 * 12 + 5:
                continue
            if key.upper().startswith("APP"):
                L.setdefault("inclusion_by_app", {})[key.upper()] = as_pi(e["pi"])
            else:
                L.setdefault("inclusion_by_account", {})[as_acct(key)] = as_pi(e["pi"])
        E.ctl(name, entries, [e["key"] for e in entries], c)
    elif name == "currency_redenomination.ini":
        secs_ = read_ini(p)
        rows = secs_["redenominated"]
        L["redenominated_numeric"] = {as_acct(k): v.split(";")[0].strip() for k, v in rows.items()}
        E.ctl(name, list(rows), list(rows), secs_["delivery_control"])
    elif name == "treasury_fixings_2024_2026.xml":
        root = ET.parse(p).getroot()
        rows = root.findall("fixing")
        best = {}
        for f in rows:
            k = (f.get("ccy").strip().upper(), as_date(f.get("date")))
            rev = int(f.get("rev", "1"))
            if k not in best or rev > best[k][0]:
                best[k] = (rev, as_dec(f.text), int(f.get("per", "1")))
        fx = {}
        for (ccy, d), (_r, eur, per) in best.items():
            fx.setdefault(ccy, []).append((d, eur, per))
        L["treasury_rates"] = {k: sorted(v) for k, v in fx.items()}
        E.ctl(name, rows, [f.get("date") for f in rows], dict(root.find("control").attrib))
    elif name == "fx_rates_ecb_mirror.xml":
        root = ET.parse(p).getroot()
        rows = [el for el in root if _strip_ns(el.tag) == "rate"]
        L["iso_numeric"] = {c_.get("numeric"): c_.get("alpha") for c_ in root.iter() if _strip_ns(c_.tag) == "currency"}
        ctl_el = next(el for el in root if _strip_ns(el.tag) == "control")
        E.ctl(name, rows, [r.get("date") for r in rows], dict(ctl_el.attrib))
    elif name == "market_holidays.ics":
        import datetime as dt
        events, c = read_ics(p)
        hol = {}
        for ev in events:
            cat = ev["CATEGORIES"][1].strip().upper()
            ev["X-MARKET"] = (ev["X-MARKET"][0], ev["X-MARKET"][1].strip().upper())
            if cat not in ("PUBLIC-HOLIDAY", "BANK-CLOSURE"):
                continue
            start = as_date(ev["DTSTART"][1][:8])
            end = as_date(ev["DTEND"][1][:8]) if "DTEND" in ev else start + dt.timedelta(days=1)
            d = start
            while d < end:
                hol.setdefault(ev["X-MARKET"][1].strip(), set()).add(d)
                d += dt.timedelta(days=1)
        L["market_closures"] = hol
        E.ctl(name, events, [ev["DTSTART"][1][:8] for ev in events], c)
    elif name == "product_code_crosswalk.ini":
        secs_ = read_ini(p)
        keys = []
        for sec, items in secs_.items():
            if sec == "delivery_control":
                continue
            for k in items:
                L.setdefault("product_segment", {})[as_code(k)] = sec.strip().upper()
                keys.append(k)
        E.ctl(name, keys, keys, secs_["delivery_control"])
    elif name == "legacy_account_map.ini":
        secs_ = read_ini(p)
        rows = secs_["legacy_accounts"]
        L["legacy_accounts"] = {k.strip().upper(): as_acct(v.split(";")[0]) for k, v in rows.items()}
        E.ctl(name, list(rows), list(rows), secs_["delivery_control"])


def _others(E):
    for k, v in (("reversed_withdrawals", set()), ("customer_aliases", {}), ("legacy_customers", {}), ("inclusion_by_account", {}), ("inclusion_by_app", {}),
                 ("redenominated_numeric", {}), ("treasury_rates", {}), ("iso_numeric", {}), ("market_closures", {}), ("product_segment", {}), ("legacy_accounts", {})):
        E.L.setdefault(k, v)
    read_other(E, "chargeoff_events_2026.parquet", "applications_master_2025h1.parquet", "customer_master.db",
               "merge_candidates_ml.xlsx", "sampling_inclusion_gb_pl_se.yaml", "sampling_inclusion_cz_hu_ch.yaml",
               "sampling_inclusion_dk_no.yaml", "sampling_design_v2.yaml", "currency_redenomination.ini",
               "treasury_fixings_2024_2026.xml", "fx_rates_ecb_mirror.xml", "market_holidays.ics",
               "product_code_crosswalk.ini", "legacy_account_map.ini")


@guarded
def read_model(E, name, p):
    L = E.L
    if name == "model_documentation_v4.pdf":
        rows, c, lines = read_pdf_table(p, ["segment", "score", "pd"])
        L["pd_grid"] = {(as_upper(r["segment"]), as_int(r["score"])): str(as_dec(r["pd"])) for r in rows}
        cuts, on = {}, False
        for ln in lines:
            if ln.startswith("segment | c1"):
                on = True
                continue
            if on:
                parts = ln.split(" | ")
                if len(parts) != 10:
                    break
                cuts[parts[0].strip()] = [int(x) for x in parts[1:]]
        L["documented_cuts"] = cuts
        E.ctl(name, rows, [r["score"] for r in rows], c)
    elif name == "calibration_reissue_2026.pdf":
        lines = pdf_lines(p)
        rows, retro, part, control = [], [], "reissue", None
        for ln in lines:
            if ln.startswith("Delivery control: "):
                control = parse_control_text(ln[len("Delivery control: "):])
            elif ln == "Appendix B - retrospective corrections":
                part = "retro"
            elif ln == "segment | score | pd":
                continue
            elif ln.count(" | ") == 2:
                seg, sc, pd = ln.split(" | ")
                rows.append(sc)
                if part == "retro":
                    retro.append(((as_upper(seg), as_int(sc)), str(as_dec(pd))))
        L["retro_pd"] = dict(retro)
        E.ctl(name, rows, rows, control)
    elif name == "monitoring_spec_v4.md":
        text = read_text(p)
        dev, keys = {}, []
        appendix = text.split("## Appendix A.")[1].split("## Delivery control")[0]
        for ln in appendix.splitlines():
            parts = [x.strip() for x in ln.strip().strip("|").split("|")]
            if len(parts) == 3 and parts[1].isdigit():
                dev[(as_upper(parts[0]), as_int(parts[1]))] = int(squeeze(parts[2]).replace(",", ""))
                keys.append(parts[1])
        L["dev_counts"] = dev
        E.ctl(name, keys, keys, md_control(text))


def md_control(text):
    block = text.split("## Delivery control")[-1]
    out = {}
    for ln in block.splitlines():
        parts = [x.strip() for x in ln.strip().strip("|").split("|")]
        if len(parts) == 2 and parts[0] not in ("field", "---"):
            out[parts[0]] = parts[1]
    return out


def md_rows(text, section, ncols):
    body = text.split(section)[1]
    for stop in ("\n## ",):
        body = body.split(stop)[0]
    rows = []
    for ln in body.splitlines():
        if not ln.startswith("|") or ln.startswith("|---"):
            continue
        parts = [x.strip().replace("\\|", "|") for x in re.split(r"(?<!\\)\|", ln.strip())[1:-1]]
        if len(parts) == ncols:
            rows.append(parts)
    return rows[1:] if rows else rows


def _model(E):
    for k, v in (("pd_grid", {}), ("documented_cuts", {}), ("retro_pd", {}), ("dev_counts", {})):
        E.L.setdefault(k, v)
    read_model(E, "model_documentation_v4.pdf", "calibration_reissue_2026.pdf", "monitoring_spec_v4.md")


@guarded
def read_corrections(E, name, p):
    L = E.L
    if name == "errata_register.md":
        text = read_text(p)
        L["rule_errata"] = md_rows(text, "## Rule errata", 4)
        rows = md_rows(text, "## Row errata", 6)
        best = {}
        for eid, acct, period, dpd, status, raised in rows:
            if as_upper(status) != "APPLIED":
                continue
            key = (as_acct(acct), as_month(period))
            stamp = (as_date(raised), as_id(eid))
            if key not in best or stamp > best[key][0]:
                best[key] = (stamp, as_int(dpd))
        L["row_errata"] = {k: v[1] for k, v in best.items()}
        E.ctl(name, rows, [r[0] for r in rows], md_control(text))
    elif name == "ops_corrections.mbox":
        msgs, c = read_mbox(p)
        retracted = {m["subject"].split(" ", 1)[1].strip() for m in msgs if m["subject"].upper().startswith("RETRACT ")}
        best = {}
        for m in msgs:
            if not m["subject"].upper().startswith("CORRECTION:") or m["msgid"] in retracted:
                continue
            fields = {k.lower(): v for k, v in re.findall(r"^(account|period|dpd): *(.+?) *$", m["body"], re.M | re.I)}
            key = (as_acct(fields["account"]), as_month(fields["period"]))
            stamp = (m["ts"], m["msgid"])
            if key not in best or stamp > best[key][0]:
                best[key] = (stamp, as_int(fields["dpd"]))
        L["mail_corrections"] = {k: v[1] for k, v in best.items()}
        E.ctl(name, msgs, [m["msgid"] for m in msgs], c)
    elif name == "data_quality_issue_log.md":
        text = read_text(p)
        rows = md_rows(text, "# Data quality issue log", 5)
        names = {q.name.lower(): q.name for q in E.root.iterdir()}
        L["quarantined"] = {(names.get(r[1].strip().lower(), r[1].strip()), as_int(r[2])) for r in rows if as_upper(r[3]) == "QUARANTINE"}
        E.ctl(name, rows, [r[0] for r in rows], md_control(text))


def _corrections(E):
    for k, v in (("rule_errata", []), ("row_errata", {}), ("mail_corrections", {}), ("quarantined", set())):
        E.L.setdefault(k, v)
    read_corrections(E, "errata_register.md", "ops_corrections.mbox", "data_quality_issue_log.md")


def _manifest(E):
    cert = {}
    p = E.path("delivery_manifest.json")
    if p.is_file():
        try:
            data = json.loads(read_text(p))
            for part in data["certified_snapshot_partitions"]:
                mi = as_month(part["period"])
                for m in part["markets"]:
                    cert[(mi, m)] = part["file"]
        except (ValueError, KeyError) as exc:
            print(f"monitor: cannot read certified partitions: {exc}", file=sys.stderr)
    E.L["certified_source"] = cert


def main(argv):
    if len(argv) != 3:
        print("usage: monitor.py ESTATE_DIR OUT_DIR", file=sys.stderr)
        return 2
    estate, out = Path(argv[1]), Path(argv[2])
    outputs = artifacts(load(estate))
    out.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_NAMES:
        (out / name).write_bytes(outputs[name])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
