#!/usr/bin/env python3
"""Monthly SLA service-credit close for Corvid Cloud Platform.

Usage: python3 transform.py [DATA_DIR] [OUT_DIR] [--prior PRIOR_OUT_DIR]
Defaults: /app/data -> /app/out.  Reads only DATA_DIR (and PRIOR_OUT_DIR when given).
"""
import csv
import datetime as dt
import email
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import tempfile
import tomllib
import zipfile
from email import policy
from email.utils import parsedate_to_datetime
from fractions import Fraction
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

UTC = dt.timezone.utc
EPOCH = dt.datetime(1970, 1, 1, tzinfo=UTC)
DAY = 86400
WIN = 300


class _Place:
    def __repr__(self):
        return "PLACE"


PLACE = _Place()

# --------------------------------------------------------------------------- time helpers


def ts_of(text):
    s = str(text).strip()
    if len(s) == 10:
        s += "T00:00:00"
    s = s.replace("Z", "+00:00")
    d = dt.datetime.fromisoformat(s)
    if d.tzinfo is None:
        d = d.replace(tzinfo=UTC)
    return int((d - EPOCH).total_seconds())


def iso(sec):
    return (EPOCH + dt.timedelta(seconds=sec)).strftime("%Y-%m-%dT%H:%M:%SZ")


def day_of(sec):
    return (EPOCH + dt.timedelta(seconds=sec)).strftime("%Y-%m-%d")


def date_ts(d):
    return ts_of(d[:10])


def add_days(d, n):
    return (dt.date.fromisoformat(d) + dt.timedelta(days=n)).isoformat()


def last_sunday_utc(year, month):
    if month == 12:
        nxt = dt.date(year + 1, 1, 1)
    else:
        nxt = dt.date(year, month + 1, 1)
    d = nxt - dt.timedelta(days=1)
    while d.weekday() != 6:
        d -= dt.timedelta(days=1)
    return date_ts(d.isoformat()) + 3600


class Zone:
    """Standard offset in minutes plus an optional EU summer-time rule."""

    def __init__(self, std, rule):
        self.std = std
        self.rule = rule

    def offset(self, utc):
        if self.rule != "EU":
            return self.std
        y = int(day_of(utc)[:4])
        if last_sunday_utc(y, 3) <= utc < last_sunday_utc(y, 10):
            return self.std + 60
        return self.std

    def to_utc(self, naive):
        cands = []
        for off in sorted({self.std, self.std + 60}, reverse=True):
            u = naive - off * 60
            if self.offset(u) == off:
                cands.append(u)
        if cands:
            return min(cands)
        return naive - self.offset(naive - 6 * 3600) * 60

    def naive(self, utc):
        return utc + self.offset(utc) * 60


def half_even(fr):
    fr = Fraction(fr)
    q, r = divmod(fr.numerator, fr.denominator)
    r2 = 2 * r
    if r2 > fr.denominator or (r2 == fr.denominator and q % 2 == 1):
        q += 1
    return q


def fixed(fr, dp):
    fr = Fraction(fr)
    n = half_even(fr * 10 ** dp)
    sign = "-" if n < 0 else ""
    n = abs(n)
    if dp == 0:
        return f"{sign}{n}"
    return f"{sign}{n // 10 ** dp}.{n % 10 ** dp:0{dp}d}"


def sha16(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- value normalisation

INVIS = re.compile("[\u200b\ufeff\u00a0\u202f\u2060\\s]")
GROUP = re.compile("[\u00a0\u202f '\u2009]")
ID_WIDTH = {"SUB": 6, "ACC": 5, "INS": 7}


def n_id(v):
    if v is None:
        return None
    s = INVIS.sub("", str(v))
    if not s or not s.isascii():
        return None
    s = s.upper().replace("_", "-")
    m = re.fullmatch(r"([A-Z]+)-?(\d+)", s)
    if not m:
        return None
    p, d = m.groups()
    w = ID_WIDTH.get(p)
    if w is not None and len(d) != w:
        return None
    return f"{p}-{d}"


def n_host(v):
    if v is None:
        return None
    s = INVIS.sub("", str(v)).lower()
    return s if re.fullmatch(r"[a-z0-9-]+", s) else None


def n_cnt(v):
    if v is None or isinstance(v, bool):
        return PLACE
    if isinstance(v, int):
        return PLACE if v < 0 else v
    if isinstance(v, float):
        if v < 0 or v != int(v):
            return PLACE
        return int(v)
    s = str(v).strip()
    if s == "" or s.upper() == "N/A":
        return PLACE
    s = GROUP.sub("", s)
    if s.lower().endswith("k"):
        f = Fraction(s[:-1]) * 1000
        if f.denominator != 1:
            raise ValueError(f"bad count {v!r}")
        return int(f)
    n = int(s)
    return PLACE if n < 0 else n


def n_kcnt(v):
    if v is None:
        return PLACE
    f = Fraction(str(v).strip())
    if f < 0:
        return PLACE
    return half_even(f * 1000)


def n_int(v):
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, (int, float)):
        return int(v)
    return int(GROUP.sub("", str(v).strip()))


def n_dec(v):
    if v is None:
        return PLACE
    if isinstance(v, (int, float)):
        return Fraction(str(v))
    s = str(v).strip().replace(" ", "")
    if s == "" or s.upper() == "N/A":
        return PLACE
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    return Fraction(s)


def n_money(v, exp):
    if v is None:
        return PLACE
    if isinstance(v, bool):
        raise ValueError("bool money")
    if isinstance(v, int):
        return PLACE if v < 0 else v
    if isinstance(v, float):
        return int(v)
    s = str(v).strip()
    if s.upper() == "LIST":
        return "LIST"
    if s == "" or s.upper() == "N/A":
        return PLACE
    m = re.fullmatch(r"(-?[0-9][0-9.]*)\s*([A-Z]{3})", s)
    if m:
        return half_even(Fraction(m.group(1)) * 10 ** exp[m.group(2)])
    n = int(GROUP.sub("", s))
    return PLACE if n < 0 else n


def _serial(v, e1904):
    base = dt.datetime(1904, 1, 1, tzinfo=UTC) if e1904 else dt.datetime(1899, 12, 30, tzinfo=UTC)
    secs = half_even(Fraction(str(v)) * DAY)
    return int((base - EPOCH).total_seconds()) + secs


def n_ts(v, e1904=False):
    if v is None or v == "":
        return None
    if isinstance(v, dt.datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=UTC)
        return int((v - EPOCH).total_seconds())
    if isinstance(v, dt.date):
        return date_ts(v.isoformat())
    if isinstance(v, bool):
        raise ValueError("bool ts")
    if isinstance(v, int):
        return v // 1000 if v >= 10 ** 11 else v
    if isinstance(v, float):
        return _serial(v, e1904)
    s = str(v).strip()
    if s.isdigit():
        if len(s) == 8:
            return date_ts(f"{s[:4]}-{s[4:6]}-{s[6:]}")
        n = int(s)
        return n // 1000 if len(s) >= 12 else n
    m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", s)
    if m:
        return date_ts(f"{m.group(3)}-{m.group(2)}-{m.group(1)}")
    return ts_of(s)


def n_lts(v, e1904=False):
    """Local wall-clock reading -> naive seconds (as if UTC)."""
    if v is None or v == "":
        return None
    if isinstance(v, dt.datetime):
        return int((v.replace(tzinfo=UTC) - EPOCH).total_seconds())
    if isinstance(v, float):
        return _serial(v, e1904)
    s = str(v).strip()
    if re.fullmatch(r"\d{14}", s):
        s = f"{s[:4]}-{s[4:6]}-{s[6:8]}T{s[8:10]}:{s[10:12]}:{s[12:]}"
    d = dt.datetime.fromisoformat(s)
    return int((d.replace(tzinfo=UTC) - EPOCH).total_seconds())


def n_date(v, e1904=False):
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        v = v.date()
    if isinstance(v, dt.date):
        s = v.isoformat()
    elif isinstance(v, float):
        s = day_of(_serial(v, e1904))
    else:
        s = str(v).strip()
        if s == "":
            return None
        m = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", s)
        if m:
            s = f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        elif re.fullmatch(r"\d{8}", s):
            s = f"{s[:4]}-{s[4:6]}-{s[6:]}"
        s = s[:10]
        dt.date.fromisoformat(s)
    return None if s == "9999-12-31" else s


def n_bool(v):
    if isinstance(v, bool):
        return v
    if v is None:
        return False
    return str(v).strip().upper() in ("Y", "YES", "TRUE", "1")


def n_enum(v):
    return None if v is None else INVIS.sub("", str(v)).upper()


def n_str(v):
    return None if v is None else str(v).strip()


def n_reg(v):
    return None if v is None else INVIS.sub("", str(v)).lower()


# --------------------------------------------------------------------------- schema
# file -> {table: [(column, type)]}; the first column of every table is its control field.

TEL = [("requests", "cnt"), ("err_5xx", "cnt"), ("err_429", "cnt"), ("err_4xx", "cnt")]
LB = [("record_id", "id"), ("host", "host"), ("subscription", "id"), ("window_start", "ts")] + TEL + [
    ("seq", "int"), ("batch_id", "id"), ("agent", "str")]
SVC = [("record_id", "id"), ("node", "host"), ("subscription", "id"), ("window_start_ms", "ts")] + TEL + [
    ("seq", "int"), ("batch_id", "id")]
SVC3 = [("record_id", "id"), ("node", "host"), ("subscription", "id"), ("window_start_ms", "ts"),
        ("requests_k", "kcnt")] + TEL[1:] + [("seq", "int"), ("batch_id", "id")]
EDGE = [("record_id", "id"), ("host", "host"), ("subscription", "id"), ("reading", "lts")] + TEL + [
    ("seq", "int"), ("batch_id", "id")]
CDNX = [("record_id", "id"), ("host", "host"), ("subscription", "id"), ("window_epoch", "ts")] + TEL + [
    ("seq", "int"), ("batch_id", "id"), ("note", "str")]
CDNA = [("record_id", "id"), ("host", "host"), ("subscription", "id"), ("window_start", "ts")] + TEL + [
    ("seq", "int"), ("batch_id", "id")]
SDK = [("event_id", "id"), ("install_id", "id"), ("build", "str"), ("ts", "ts"), ("requests", "cnt"),
       ("errors_5xx", "cnt"), ("errors_429", "cnt"), ("errors_4xx", "cnt"), ("seq", "int"), ("batch_id", "id")]
QUOTA = [("subscription", "id"), ("quota_per_window", "int"), ("as_of", "date")]
PROBE = [("probe_id", "id"), ("observed_at", "ts"), ("vantage", "enum"), ("target", "id"), ("status", "enum"),
         ("latency_ms", "int")]
SUBS = [("subscription_id", "id"), ("account_ref", "id"), ("product", "enum"), ("region", "reg"),
        ("start_date", "date"), ("end_date", "date"), ("plan_code", "enum"), ("monthly_fee", "money"),
        ("currency", "enum")]
PLANC = [("change_id", "id"), ("subscription_id", "id"), ("effective", "ts"), ("action", "enum"),
         ("plan_code", "enum"), ("reverts", "id")]
ENROL = [("enrollment_id", "id"), ("subscription_id", "id"), ("effective", "date"), ("action", "enum"),
         ("sla_class", "enum")]
LINK = [("link_id", "id"), ("downstream", "id"), ("upstream", "id"), ("action", "enum"), ("registered_at", "ts")]
LOGH = [("ts", "ts"), ("level", "enum"), ("component", "str")]
CTRL = [("control_id", "id"), ("file", "str"), ("block", "int"), ("records", "int"), ("control_sum", "int")]

SCHEMA = {
    **{f"lb_errors_{g}.csv": {"records": LB} for g in ("central", "east", "north", "south", "west")},
    "svc_metrics_part1.parquet": {"records": SVC},
    "svc_metrics_part2.parquet": {"records": SVC},
    "svc_metrics_part3.parquet": {"records": SVC3},
    **{f"edge_legacy_{x}.txt": {"records": EDGE} for x in "abc"},
    "cdn_logs_fastedge.xml": {"Window": CDNX},
    "cdn_logs_akamoto.xml": {"Window": CDNX},
    "cdn_attestations.xlsx": {"Fastedge": CDNA, "Akamoto": CDNA},
    **{f"sdk_events_{i}.jsonl": {"records": SDK} for i in (1, 2, 3)},
    "sdk_server_receipts.csv": {"records": [("event_id", "id"), ("received_at", "ts"), ("collector_node", "str")]},
    "sdk_builds.json": {"builds": [("build", "str"), ("platform", "str"), ("clock", "enum"), ("status", "enum"),
                                   ("released", "date")]},
    "telemetry_voids.jsonl": {"records": [("void_id", "id"), ("target", "id"), ("action", "enum"), ("at", "ts"),
                                          ("reason", "str")]},
    "ingest_batches.jsonl": {"records": [("batch_id", "id"), ("collector", "enum"), ("status", "enum"),
                                         ("loaded_at", "ts"), ("rows", "int")]},
    "telemetry_quarantine.json": {"quarantine": [("quarantine_id", "id"), ("host", "host"), ("from", "ts"),
                                                 ("to", "ts"), ("status", "enum")]},
    "host_inventory.csv": {"records": [("host", "host"), ("region", "reg"), ("product", "enum"), ("lane", "enum"),
                                       ("rack", "str"), ("commissioned", "date")]},
    "lb_sampling.parquet": {"records": [("sampling_id", "id"), ("host", "host"), ("effective_from", "ts"),
                                        ("one_in", "int")]},
    "deploy_events.log": {"records": [("event_id", "id")] + LOGH + [("event", "enum"), ("schema", "str"),
                                                                     ("wave", "id"), ("seq", "int")]},
    "deploy_manifests.xml": {"Member": [("member_id", "id"), ("wave", "id"), ("revision", "int"), ("host", "host")]},
    "schema_registry.yaml": {"versions": [("version", "str"), ("err_5xx_includes_429", "bool"), ("notes", "str")],
                             "baseline": [("host", "host"), ("schema", "str"), ("as_of", "date")]},
    "quotas_central.yaml": {"quotas": QUOTA},
    "quotas_east.toml": {"quota": QUOTA},
    "quotas_north.sqlite": {"quotas": QUOTA},
    "quotas_south.md": {"Quotas": QUOTA},
    "quotas_west.html": {"Quotas": QUOTA},
    "quota_changes.tsv": {"records": [("change_id", "id"), ("subscription", "id"), ("effective", "ts"),
                                      ("quota", "int")]},
    "probes_core.tsv": {"records": PROBE},
    "probes_data.tsv": {"records": PROBE},
    "probes_compute.tsv": {"records": PROBE},
    "probe_targets.json": {"targets": [("target_id", "id"), ("product", "enum"), ("region", "reg"),
                                       ("endpoint", "str"), ("status", "enum")]},
    "noc_outage_declarations.pdf": {"Declarations": [("noc_id", "id"), ("product", "enum"), ("region", "reg"),
                                                     ("start", "ts"), ("end", "ts"), ("status", "enum"),
                                                     ("prelim_ref", "id")]},
    "incident_register.xml": {"Incident": [("incident_id", "id"), ("product", "enum"), ("region", "reg"),
                                           ("opened", "ts"), ("closed", "ts")],
                              "Update": [("update_id", "id"), ("ref", "id"), ("action", "enum"), ("at", "ts"),
                                         ("until", "ts")]},
    "dependency_links.tsv": {"records": LINK},
    "incident_attribution_policy.docx": {"Dependency declarations": LINK,
                                         "Service dependencies": [("product", "enum"), ("upstream", "enum")]},
    "maintenance_changes.xlsx": {"Changes": [("change_id", "id"), ("region", "reg"), ("product", "enum"),
                                             ("type", "enum"), ("start_local", "lts"), ("end_local", "lts")],
                                 "Approvals": [("approval_id", "id"), ("change_id", "id"), ("seq", "int"),
                                               ("decision", "enum"), ("decided_at", "ts")]},
    "change_calendar.ics": {"records": [("uid", "id"), ("sequence", "int"), ("dtstart", "str"), ("dtend", "str"),
                                        ("status", "enum"), ("summary", "str")]},
    "maintenance_notices.mbox": {"records": [("message_id", "id"), ("change_id", "id"), ("sent", "ts"),
                                             ("subject", "str")]},
    "maintenance_policy.docx": {"Site calendars": [("site", "enum"), ("date", "date"), ("business", "bool")]},
    "lifecycle_events.log": {"records": [("event_id", "id")] + LOGH + [("event", "enum"), ("subscription", "id"),
                                                                        ("reason", "str")]},
    "suspension_orders.pdf": {"Orders": [("order_id", "id"), ("subscription", "id"), ("from", "ts"), ("to", "ts"),
                                         ("status", "enum")]},
    "accounts_master.csv": {"records": [("account_id", "id"), ("name", "str"), ("home_region", "reg"),
                                        ("currency", "enum"), ("created", "date"), ("status", "enum")]},
    "account_aliases.tsv": {"records": [("alias_id", "id"), ("account_id", "id"), ("registered", "date")]},
    "governance_charter.docx": {
        "Account decisions": [("decision_id", "id"), ("from_account", "id"), ("to_account", "id"),
                              ("decided_on", "date"), ("kind", "enum")],
        "Plan segments": [("plan_code", "enum"), ("segment", "str")],
        "Region regroupings": [("region", "reg"), ("region_group", "str"), ("effective", "date")]},
    "subscriptions_central.csv": {"records": SUBS},
    "subscriptions_east.parquet": {"records": SUBS},
    "subscriptions_north.sqlite": {"subscriptions": SUBS},
    "subscriptions_south.jsonl": {"records": SUBS},
    "subscriptions_west.xlsx": {"Subscriptions": SUBS,
                                "Contract discounts": [("discount_id", "id"), ("account_ref", "id"),
                                                       ("discount_bp", "int"), ("effective", "date")]},
    "source_register.md": {
        "Close parameters": [("key", "str"), ("value", "str")],
        "Regions": [("region", "reg"), ("city", "str"), ("region_group", "str"), ("tzid", "str"),
                    ("std_offset_min", "int"), ("dst_rule", "enum")],
        "Currencies": [("currency", "enum"), ("minor_exponent", "int")],
        "Source catalog": [("file", "str"), ("format", "str"), ("role", "str"), ("control_field", "str"),
                           ("record_definition", "str")],
        "Legacy order references": [("order_ref", "id"), ("subscription_id", "id")]},
    "plan_changes_central.tsv": {"records": PLANC},
    "plan_changes_east.json": {"changes": PLANC},
    "plan_changes_north.xml": {"Change": PLANC},
    "plan_changes_south.yaml": {"changes": PLANC},
    "plan_changes_west.log": {"records": [("change_id", "id")] + LOGH + PLANC[1:]},
    "sla_enrollment_central.md": {"Enrollments": ENROL},
    "sla_enrollment_east.html": {"Enrollments": ENROL},
    "sla_enrollment_north.pdf": {"Enrollments": ENROL},
    "sla_enrollment_south.pdf": {"Enrollments": ENROL},
    "sla_enrollment_west.csv": {"records": ENROL},
    "contracts_register.xlsx": {"Contracts": [("contract_id", "id"), ("account_id", "id"), ("signed_on", "date")],
                                "Amendments": [("amendment_id", "id"), ("contract_id", "id"),
                                               ("signed_on", "date")]},
    "sla_policy_2026.docx": {
        "Version cutovers": [("version", "str"), ("signed_from", "date")],
        "Service targets": [("version", "str"), ("sla_class", "enum"), ("target_pct", "dec")],
        "Credit tiers": [("version", "str"), ("tier", "int"), ("kind", "str"), ("threshold", "dec"),
                         ("credit_pct", "int")],
        "Bad window thresholds": [("version", "str"), ("permille", "int")],
        "Subscription pins": [("pin_id", "id"), ("subscription_id", "id"), ("version", "str"),
                              ("pinned_on", "date")]},
    "enterprise_sla_schedules.pdf": {"Schedules": [("schedule_id", "id"), ("subscription_id", "id"),
                                                   ("effective", "date"), ("target_pct", "dec"),
                                                   ("credit_pct", "int")]},
    "price_book.toml": {"price": [("price_id", "id"), ("plan", "enum"), ("product", "enum"), ("currency", "enum"),
                                  ("effective", "date"), ("amount", "money")]},
    "fee_overrides.xlsx": {s: [("override_id", "id"), ("subscription_id", "id"), ("revision", "int"),
                               ("fee_minor", "money"), ("status", "enum"), ("approved_on", "date")]
                           for s in ("Overrides A", "Overrides B")},
    "account_caps.xlsx": {s: [("cap_id", "id"), ("account_ref", "id"), ("quarterly_cap_usd", "money"),
                              ("effective", "date")] for s in ("Caps", "Caps continued")},
    "credit_ledger.sqlite": {"postings": [("posting_id", "id"), ("account_ref", "id"), ("amount_usd_cents", "money"),
                                          ("posted_at", "ts"), ("kind", "enum")],
                             "goodwill": [("grant_id", "id"), ("account_ref", "id"), ("amount_usd_cents", "money"),
                                          ("granted_at", "ts")]},
    "credit_preferences.json": {"preferences": [("account_id", "id"), ("auto_credit", "bool"), ("channel", "str")]},
    "credit_operations_manual.docx": {"Account calendar sites": [("account_id", "id"), ("calendar_site", "enum")]},
    "claims_portal.csv": {"records": [("claim_id", "id"), ("subscription_id", "id"), ("filed_at", "ts"),
                                      ("channel", "str"), ("note", "str")]},
    "support_tickets.jsonl": {"records": [("ticket_id", "id"), ("crm_case", "id"), ("order_ref", "id"),
                                          ("opened_at", "ts"), ("category", "enum"), ("subject", "str")]},
    "claims_backoffice.xlsx": {"Received": [("receipt_id", "id"), ("ban", "str"), ("subscription_id", "id"),
                                            ("received", "ts")],
                               "Decisions": [("decision_id", "id"), ("receipt_id", "id"), ("decision", "enum"),
                                             ("decided_on", "date")]},
    "claims_workflow.log": {"records": [("event_id", "id")] + LOGH + [("event", "enum"), ("ref", "id"),
                                                                       ("actor", "str")]},
    "fx_hourly_treasury.csv": {"records": [("fixing_id", "id"), ("currency", "enum"), ("hour", "ts"),
                                           ("usd_per_unit", "dec"), ("revision", "int")]},
    "telemetry_collection_standard.docx": {
        "Collector precedence": [("collector", "enum"), ("precedence", "int"), ("lane", "enum")],
        "Edge record layout V6": [("field", "str"), ("width", "int")],
        "Collector gap windows": [("gap_id", "id"), ("region", "reg"), ("collector", "enum"), ("from", "ts"),
                                  ("to", "ts")],
        "Host lane assignments": [("host", "host"), ("lane", "enum"), ("assigned_on", "date")]},
    "audit_control_register.pdf": {"Control blocks": CTRL + [("revision", "int")]},
    **{f"host_clock_edge_{x}.ini": {"measure": [("measurement_id", "id"), ("host", "host"),
                                                 ("measured_at", "ts"), ("skew_s", "int")]} for x in "abc"},
    # ---- supplementary exports
    "lb_errors_east_replay.csv": {"records": LB + [("marker", "enum")]},
    "svc_metrics_compacted.parquet": {"records": [("record_id", "id"), ("kind", "enum"), ("target", "id"),
                                                  ("node", "host"), ("host", "host"), ("subscription", "id"),
                                                  ("window_start_ms", "ts"), ("requests", "int"),
                                                  ("err_5xx", "int"), ("err_429", "int"), ("err_4xx", "int")]},
    "client_sdk_dedup.jsonl": {"records": [("record_id", "id"), ("kind", "enum"), ("install_id", "id"),
                                           ("subscription", "id"), ("build", "str"), ("event_ref", "id"),
                                           ("ts", "ts"), ("requests", "int"), ("errors_5xx", "int"),
                                           ("errors_429", "int"), ("errors_4xx", "int")]},
    "sla_policy_v4_draft.docx": {
        "Draft credit tiers v4": [("version", "str"), ("tier", "int"), ("kind", "str"), ("threshold", "dec"),
                                  ("credit_pct", "int")],
        "Legacy schedule v2 targets": [("version", "str"), ("sla_class", "enum"), ("target_pct", "dec")],
        "Legacy schedule v2 tiers": [("version", "str"), ("tier", "int"), ("kind", "str"), ("threshold", "dec"),
                                     ("credit_pct", "int")],
        "Legacy schedule v2 thresholds": [("version", "str"), ("permille", "int")],
        "Legacy plan codes": [("legacy_code", "enum"), ("plan_code", "enum")],
        "Draft subscription pins": [("pin_id", "id"), ("subscription_id", "id"), ("version", "str"),
                                    ("pinned_on", "date")]},
    "credit_tiers_2026.xlsx": {
        "Draft": [("target_id", "id"), ("product", "enum"), ("region", "reg"), ("sla_class", "enum"),
                  ("target_pct", "dec"), ("effective", "date")],
        "Ratified": [("target_id", "id"), ("product", "enum"), ("region", "reg"), ("sla_class", "enum"),
                     ("target_pct", "dec"), ("effective", "date")],
        "Revocations": [("revocation_id", "id"), ("schedule_id", "id"), ("revoked_on", "date"),
                        ("status", "enum")]},
    "incident_register_preliminary.xml": {
        "Preliminary": [("prelim_id", "id"), ("final_id", "id"), ("product", "enum"), ("region", "reg"),
                        ("opened", "ts"), ("closed", "ts")],
        "Retraction": [("retraction_id", "id"), ("noc_id", "id"), ("at", "ts")]},
    "account_snapshot_legacy.sqlite": {"accounts": [("account_id", "id"), ("ban", "str"), ("name", "str"),
                                                    ("segment", "str"), ("region", "reg"),
                                                    ("internal_flag", "bool"), ("currency", "enum")]},
    "fx_rates_unofficial.json": {"rates": [("fixing_id", "id"), ("currency", "enum"), ("hour", "ts"),
                                           ("usd_per_unit", "dec")],
                                 "recalls": [("recall_id", "id"), ("fixing_id", "id"), ("at", "ts")]},
    "uptime_dashboard_snapshot.html": {
        "Daily uptime": [("row_id", "id"), ("product", "enum"), ("region", "reg"), ("day", "date"),
                         ("uptime_pct", "dec")],
        "Retired probe targets": [("retired_id", "id"), ("target_id", "id")],
        "Beta product-regions": [("beta_id", "id"), ("product", "enum"), ("region", "reg"), ("beta_from", "date"),
                                 ("beta_to", "date")]},
    "sla_report_draft.pdf": {
        "Draft subscription results": [("row_id", "id"), ("subscription_id", "id"), ("uptime_pct", "dec"),
                                       ("credit_pct", "int"), ("status", "enum")],
        "Voided July postings": [("void_ref", "id"), ("posting_id", "id")],
        "Claim references": [("ref", "id"), ("claim_id", "id")]},
    "collector_schema_proposed.yaml": {
        "proposed_host_schema": [("host", "host"), ("schema", "str"), ("as_of", "date")],
        "edge_layout_v7": [("field", "str"), ("width", "int")],
        "aborted_rollouts": [("event_id", "id"), ("reason", "str")]},
    "probe_results_mirror.tsv": {"records": [("row_id", "id"), ("kind", "enum"), ("probe_id", "id"),
                                             ("observed_at", "ts"), ("vantage", "enum"), ("vantage_id", "enum"),
                                             ("target", "id"), ("status", "enum")]},
    "ingest_reprocess.log": {"records": [("event_id", "id")] + LOGH + [("event", "enum"), ("batch", "id"),
                                                                        ("file", "str"), ("block", "int"),
                                                                        ("records", "int"),
                                                                        ("control_sum", "int")]},
    "claims_crm_legacy.csv": {"records": [("case_id", "id"), ("subscription_id", "id"), ("filed_at", "ts"),
                                          ("origin", "str"), ("state", "enum")]},
    "region_groups_2025.toml": {
        "host_group": [("host", "host"), ("region_group", "str"), ("as_of", "date")],
        "region_alias": [("alias", "reg"), ("region", "reg")],
        "region_site": [("region", "reg"), ("site", "enum")],
        "control": CTRL},
}

assert len(SCHEMA) == 100, len(SCHEMA)
FILES = sorted(SCHEMA)
REGISTER = "audit_control_register.pdf"


def snake(k):
    return re.sub(r"(?<=[a-z0-9])([A-Z])", lambda m: "_" + m.group(1).lower(), str(k))


# --------------------------------------------------------------------------- readers


def decode_lines(data):
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    out = []
    for raw in data.split(b"\n"):
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        try:
            out.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            out.append(raw.decode("latin-1"))
    while out and out[-1] == "":
        out.pop()
    return out


def read_delimited(data, delim):
    keep = [ln for ln in decode_lines(data) if not ln.startswith("#")]
    header, out = None, []
    for r in csv.reader(io.StringIO("\n".join(keep)), delimiter=delim):
        cells = [c.strip() for c in r]
        if not cells or all(c == "" for c in cells):
            continue
        if header is None:
            header = cells
            continue
        if len(cells) == len(header) and set(cells) == set(header):
            header = cells
            continue
        if len(r) < len(header):
            r = r + [""] * (len(header) - len(r))
        out.append(dict(zip(header, r)))
    return {"records": out}


def _snake_keys(d):
    return {snake(k): v for k, v in d.items()}


def read_jsonl(data):
    out = []
    for ln in decode_lines(data):
        if not ln.strip():
            continue
        o = json.loads(ln)
        if "_meta" in o:
            continue
        out.append(_snake_keys(o))
    return {"records": out}


def read_json(data):
    o = json.loads(data.decode("utf-8-sig"))
    return {k: [_snake_keys(r) for r in v] for k, v in o.items() if isinstance(v, list)}


def read_xml(data):
    root = ET.fromstring(data)
    out = {}
    for el in root:
        rec = {snake(k): v for k, v in el.attrib.items()}
        for c in el:
            rec[snake(c.tag)] = c.text or ""
        out.setdefault(el.tag, []).append(rec)
    return out


def read_parquet(data):
    import pyarrow.parquet as pq
    return {"records": pq.read_table(io.BytesIO(data)).to_pylist()}


def read_xlsx(data):
    import openpyxl
    from openpyxl.utils.datetime import CALENDAR_MAC_1904
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    e1904 = wb.epoch == CALENDAR_MAC_1904
    out = {}
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        header = None
        recs = []
        for r in rows:
            if header is None:
                header = [str(c).strip() if c is not None else "" for c in r]
                continue
            if all(c is None or c == "" for c in r):
                continue
            recs.append(dict(zip(header, r)))
        out[ws.title] = recs
    wb.close()
    return out, e1904


def read_sqlite(data):
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        con = sqlite3.connect(path)
        out = {}
        names = [r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY rowid")]
        for n in names:
            cur = con.execute(f'SELECT * FROM "{n}" ORDER BY rowid')
            cols = [c[0] for c in cur.description]
            out[n] = [dict(zip(cols, r)) for r in cur]
        con.close()
    finally:
        os.unlink(path)
    return out


def read_yaml(data):
    import yaml
    o = yaml.safe_load(data.decode("utf-8-sig"))
    return {k: [_snake_keys(r) for r in v] for k, v in o.items() if isinstance(v, list)}


def read_toml(data):
    o = tomllib.loads(data.decode("utf-8-sig"))
    return {k: [_snake_keys(r) for r in v] for k, v in o.items() if isinstance(v, list)}


def read_ini(data, schema):
    import configparser
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    cp.read_string("\n".join(decode_lines(data)))
    out = {}
    for sec in cp.sections():
        name = sec.strip()
        table, _, suffix = name.partition(".")
        first = schema[table][0][0] if table in schema else "id"
        rec = {first: suffix.strip()}
        rec.update({snake(k): v for k, v in cp[sec].items()})
        out.setdefault(table, []).append(rec)
    return out


LOG_RE = re.compile(r"(\S+) (\S+) (\S+) ?(.*)$")
KV_RE = re.compile(r'(\w+)=("(?:[^"\\]|\\.)*"|\S*)')


def read_log(data):
    out = []
    for ln in decode_lines(data):
        if not ln.strip() or ln.startswith("#"):
            continue
        m = LOG_RE.match(ln)
        rec = {"ts": m.group(1), "level": m.group(2), "component": m.group(3)}
        for k, v in KV_RE.findall(m.group(4)):
            if v.startswith('"'):
                v = re.sub(r"\\(.)", r"\1", v[1:-1])
            rec[k] = v
        out.append(rec)
    return {"records": out}


def read_fwf(data, layouts):
    out = []
    layout = None
    for ln in decode_lines(data):
        if ln.startswith("H"):
            layout = ln[1:5].strip()
        elif ln.startswith("D"):
            pos, rec = 1, {}
            for col, width in layouts[layout]:
                rec[col] = ln[pos:pos + width].strip()
                pos += width
            out.append(rec)
    return {"records": out}


def read_mbox(data):
    text = data.decode("utf-8", "replace")
    chunks = re.split(r"(?m)^From \S+ .*\n", text)
    out = []
    for ch in chunks:
        if not ch.strip():
            continue
        msg = email.message_from_bytes(ch.encode("utf-8"), policy=policy.default)
        mid = str(msg["Message-ID"] or "").strip().strip("<>").split("@")[0]
        body = msg.get_content()
        rec = {"message_id": mid, "sent": int((parsedate_to_datetime(str(msg["Date"])) - EPOCH).total_seconds()),
               "subject": str(msg["Subject"] or "")}
        for ln in body.splitlines():
            ln = ln[1:] if ln.startswith(">From ") else ln
            m = re.match(r"([A-Za-z_][\w-]*): (.*)$", ln)
            if m:
                rec[snake(m.group(1)).lower().replace("-", "_")] = m.group(2).strip()
        out.append(rec)
    return {"records": out}


def read_ics(data):
    lines = []
    for ln in decode_lines(data):
        if ln.startswith((" ", "\t")) and lines:
            lines[-1] += ln[1:]
        else:
            lines.append(ln)
    out, cur = [], None
    for ln in lines:
        if ln == "BEGIN:VEVENT":
            cur = {}
        elif ln == "END:VEVENT":
            out.append(cur)
            cur = None
        elif cur is not None and ":" in ln:
            head, _, val = ln.partition(":")
            name, *params = head.split(";")
            name = name.upper()
            if name in ("DTSTART", "DTEND"):
                tz = ""
                for p in params:
                    if p.upper().startswith("TZID="):
                        tz = p[5:]
                val = f"{tz}|{val}"
            cur[name.lower().replace("-", "_")] = val
    return {"records": out}


def split_md(line):
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|") and not s.endswith("\\|"):
        s = s[:-1]
    cells, buf, i = [], "", 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s) and s[i + 1] == "|":
            buf += "|"
            i += 2
            continue
        if s[i] == "|":
            cells.append(buf.strip())
            buf = ""
        else:
            buf += s[i]
        i += 1
    cells.append(buf.strip())
    return cells


def md_tables(data):
    lines = decode_lines(data)
    out, i = {}, 0
    while i < len(lines):
        m = re.fullmatch(r"\*\*Table: (.+)\*\*", lines[i].strip())
        if not m:
            i += 1
            continue
        name = m.group(1)
        i += 1
        while i < len(lines) and not lines[i].strip():
            i += 1
        header = split_md(lines[i])
        i += 2
        rows = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            rows.append(dict(zip(header, split_md(lines[i]))))
            i += 1
        out[name] = rows
    return out


class _HT(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.cap, self.rows, self.row, self.cell, self.mode = {}, None, None, None, None, None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.rows, self.cap = [], ""
        elif tag == "caption":
            self.mode = "cap"
        elif tag == "tr" and self.rows is not None:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = ""

    def handle_endtag(self, tag):
        if tag == "caption":
            self.mode = None
        elif tag in ("td", "th") and self.cell is not None:
            self.row.append(self.cell.strip())
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "table" and self.rows is not None:
            header = self.rows[0] if self.rows else []
            self.tables[self.cap.strip()] = [dict(zip(header, r)) for r in self.rows[1:]]
            self.rows = None

    def handle_data(self, d):
        if self.mode == "cap":
            self.cap += d
        elif self.cell is not None:
            self.cell += d


def html_tables(data):
    p = _HT()
    p.feed(data.decode("utf-8-sig"))
    return p.tables


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def docx_tables(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(W + "body")
    out, cap = {}, None
    for el in body:
        if el.tag == W + "p":
            t = "".join(x.text or "" for x in el.iter(W + "t"))
            if t.startswith("Table: "):
                cap = t[7:].strip()
        elif el.tag == W + "tbl":
            rows = []
            for tr in el.iter(W + "tr"):
                rows.append(["".join(x.text or "" for x in tc.iter(W + "t")).strip() for tc in tr.iter(W + "tc")])
            header = rows[0]
            out[cap] = [dict(zip(header, r)) for r in rows[1:]]
            cap = None
    return out


def pdf_tables(data):
    from pypdf import PdfReader
    rd = PdfReader(io.BytesIO(data))
    lines = []
    for pg in rd.pages:
        lines.extend((pg.extract_text() or "").split("\n"))
    out, name, header, expect = {}, None, None, False
    for ln in lines:
        s = ln.strip()
        m = re.fullmatch(r"Table: (.+?)( \(continued\))?", s)
        if m:
            name = m.group(1)
            expect = True
            out.setdefault(name, [])
            continue
        if expect:
            header = [c.strip() for c in s.split("|")]
            expect = False
            continue
        if re.fullmatch(r"Page \d+", s):
            continue
        if name is not None and header and s.count("|") == len(header) - 1 and s:
            out[name].append(dict(zip(header, [c.strip() for c in s.split("|")])))
        else:
            name, header = None, None
    return out


# ---------------------------------------------------------------------------
# close engine: loading, normalisation, controls, parameters, accounts
# ---------------------------------------------------------------------------

NORM = {"id": n_id, "host": n_host, "cnt": n_cnt, "kcnt": n_kcnt, "int": n_int, "dec": n_dec,
        "str": n_str, "enum": n_enum, "reg": n_reg, "bool": n_bool}
BAD = (ValueError, TypeError, ArithmeticError, KeyError, OverflowError, IndexError, AttributeError)
STRIPPED = {"ts", "lts", "date", "int", "dec", "money", "cnt", "kcnt"}


def ceil_div(a, b):
    return -((-a) // b)


def weekday(d):
    return dt.date.fromisoformat(d).weekday()


class Close:
    def __init__(self, data, out, prior=None):
        self.data = Path(data)
        self.out = Path(out)
        self.prior = Path(prior) if prior else None
        self.raw = {}
        self.e1904 = {}
        self.missing = []
        self.unreadable = []
        self.held_period_error = None
        self._norm = {}
        self.EXP = {}
        self.RALIAS = {}
        self.layouts = {}

    # ---------------- reading
    def _read(self, name, data):
        ext = name.rsplit(".", 1)[1]
        if ext == "csv":
            return read_delimited(data, ",")
        if ext == "tsv":
            return read_delimited(data, "\t")
        if ext == "jsonl":
            return read_jsonl(data)
        if ext == "json":
            return read_json(data)
        if ext == "xml":
            return read_xml(data)
        if ext == "parquet":
            return read_parquet(data)
        if ext == "xlsx":
            tabs, e = read_xlsx(data)
            self.e1904[name] = e
            return tabs
        if ext == "sqlite":
            return read_sqlite(data)
        if ext == "yaml":
            return read_yaml(data)
        if ext == "toml":
            return read_toml(data)
        if ext == "ini":
            return read_ini(data, SCHEMA[name])
        if ext == "log":
            return read_log(data)
        if ext == "txt":
            return read_fwf(data, self.layouts)
        if ext == "mbox":
            return read_mbox(data)
        if ext == "ics":
            return read_ics(data)
        if ext == "md":
            return md_tables(data)
        if ext == "html":
            return html_tables(data)
        if ext == "docx":
            return docx_tables(data)
        if ext == "pdf":
            return pdf_tables(data)
        raise ValueError(name)

    def _load_one(self, name):
        p = self.data / name
        self.raw[name] = {t: [] for t in SCHEMA[name]}
        if not p.is_file():
            self.missing.append(name)
            return
        try:
            tabs = self._read(name, p.read_bytes())
        except Exception:  # an unreadable export is reported, never guessed at
            self.unreadable.append(name)
            return
        self.raw[name] = {t: list(tabs.get(t, [])) for t in SCHEMA[name]}

    def load(self):
        for name in FILES:
            if not name.endswith(".txt"):
                self._load_one(name)
        self.RALIAS = {r["alias"]: r["region"] for r in self.T("region_groups_2025.toml", "region_alias")
                       if r["alias"] and r["region"]}
        self.EXP = {r["currency"]: r["minor_exponent"] for r in self.T("source_register.md", "Currencies")
                    if r["currency"] and r["minor_exponent"] is not None}
        self.layouts = {
            "V6": [(r["field"], r["width"]) for r in self.T("telemetry_collection_standard.docx",
                                                             "Edge record layout V6")],
            "V7": [(r["field"], r["width"]) for r in self.T("collector_schema_proposed.yaml", "edge_layout_v7")],
        }
        for name in FILES:
            if name.endswith(".txt"):
                self._load_one(name)

    def T(self, name, table):
        key = (name, table)
        if key in self._norm:
            return self._norm[key]
        cols = SCHEMA[name][table]
        e = self.e1904.get(name, False)
        alias = {} if name == "region_groups_2025.toml" else self.RALIAS
        out = []
        for i, raw in enumerate(self.raw.get(name, {}).get(table, [])):
            rec = {"_i": i}
            ok = True
            try:
                for c, t in cols:
                    v = raw.get(c)
                    if isinstance(v, str) and t in STRIPPED:
                        v = v.strip()
                    if t == "money":
                        x = n_money(v, self.EXP)
                    elif t == "ts":
                        x = n_ts(v, e)
                    elif t == "lts":
                        x = n_lts(v, e)
                    elif t == "date":
                        x = n_date(v, e)
                    else:
                        x = NORM[t](v)
                    if x is PLACE:
                        ok = False
                        break
                    if (t == "id" and x is None and v is not None
                            and str(v).strip() != ""):
                        ok = False
                        break
                    if t == "reg" and x:
                        x = alias.get(x, x)
                    rec[c] = x
            except BAD:
                ok = False
            if ok:
                out.append(rec)
        self._norm[key] = out
        return out

    # ---------------- controls
    def control_blocks(self, name):
        vals = []
        for t, cols in SCHEMA[name].items():
            first = cols[0][0]
            for raw in self.raw.get(name, {}).get(t, []):
                v = raw.get(first)
                d = "".join(ch for ch in ("" if v is None else str(v)) if "0" <= ch <= "9")
                vals.append(int(d) if d else 0)
        blocks = {}
        for j in range(0, len(vals), 100):
            part = vals[j:j + 100]
            blocks[j // 100 + 1] = (len(part), sum(part))
        return len(vals), blocks

    def register(self):
        best = {}
        for r in self.T(REGISTER, "Control blocks"):
            if not r["file"] or r["block"] is None:
                continue
            k = (r["revision"] or 0, r["control_id"] or "")
            fb = (r["file"], r["block"])
            if fb not in best or k > best[fb][0]:
                best[fb] = (k, (r["records"], r["control_sum"]))
        reg = {}
        for (f, b), (_, v) in best.items():
            reg.setdefault(f, {})[b] = v
        extra = {}
        for r in self.T("ingest_reprocess.log", "records"):
            if r["event"] == "CONTROL" and r["file"] and r["block"] is not None:
                extra.setdefault(r["file"], {})[r["block"]] = (r["records"], r["control_sum"])
        for r in self.T("region_groups_2025.toml", "control"):
            if r["file"] and r["block"] is not None:
                extra.setdefault(r["file"], {})[r["block"]] = (r["records"], r["control_sum"])
        for f, v in extra.items():
            if f not in reg:
                reg[f] = v
        return reg

    def check(self):
        reg = self.register()
        self.sources = []
        self.held = []
        self.control_total = 0
        self.record_total = 0
        for f in FILES:
            if f in self.missing or f in self.unreadable:
                self.sources.append({"file": f, "records": 0, "control_blocks": 0, "control_ok": False})
                self.held.append(("MISSING:" if f in self.missing else "UNREADABLE:") + f)
                continue
            n, blocks = self.control_blocks(f)
            if f == REGISTER:
                ok, nb = True, 0
            else:
                ok, nb = (reg.get(f) == blocks), len(blocks)
                if not ok:
                    self.held.append("CONTROL_MISMATCH:" + f)
            self.record_total += n
            self.control_total += nb
            self.sources.append({"file": f, "records": n, "control_blocks": nb, "control_ok": ok})

    # ---------------- parameters and reference tables
    def params(self):
        P = {r["key"]: r["value"] for r in self.T("source_register.md", "Close parameters") if r["key"]}
        self.PERIOD = P["period"]
        y, m = map(int, self.PERIOD.split("-"))
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        self.S = ts_of(f"{y:04d}-{m:02d}-01")
        self.E = ts_of(f"{ny:04d}-{nm:02d}-01")
        self.FIRST = day_of(self.S)
        self.L = day_of(self.E - DAY)
        self.DAYS = (self.E - self.S) // DAY
        self.NW = (self.E - self.S) // WIN
        self.Q = ts_of(P["quarter_start"])
        self.CUT = ts_of(P["crm_cutover"])
        self.RZ, self.TZ, self.RGROUP = {}, {}, {}
        for r in self.T("source_register.md", "Regions"):
            if not r["region"]:
                continue
            z = Zone(r["std_offset_min"] or 0, r["dst_rule"] or "")
            self.RZ[r["region"]] = z
            if r["tzid"]:
                self.TZ[r["tzid"]] = z
            self.RGROUP[r["region"]] = (r["region_group"] or "").lower()
        regroup = {}
        for r in self.T("governance_charter.docx", "Region regroupings"):
            if r["region"] and r["effective"] and r["effective"] <= self.L:
                k = (r["effective"], r["_i"])
                if r["region"] not in regroup or k > regroup[r["region"]][0]:
                    regroup[r["region"]] = (k, (r["region_group"] or "").lower())
        for reg, (_, g) in regroup.items():
            self.RGROUP[reg] = g
        self.RSITE = {r["region"]: r["site"] for r in self.T("region_groups_2025.toml", "region_site")
                      if r["region"] and r["site"]}
        self.SITE_REG = {s: reg for reg, s in self.RSITE.items()}
        self.CAL = {(r["site"], r["date"]): r["business"] for r in self.T("maintenance_policy.docx", "Site calendars")
                    if r["site"] and r["date"]}
        self.SEG = {r["plan_code"]: (r["segment"] or "").lower() for r in self.T("governance_charter.docx",
                                                                                   "Plan segments") if r["plan_code"]}
        self.LEGACY = {r["legacy_code"]: r["plan_code"] for r in self.T("sla_policy_v4_draft.docx",
                                                                          "Legacy plan codes") if r["legacy_code"]}

    def is_bd(self, site, d):
        b = self.CAL.get((site, d))
        return (weekday(d) < 5) if b is None else b

    def bd_back(self, site, d, n):
        x, c = d, 0
        while c < n:
            x = add_days(x, -1)
            if self.is_bd(site, x):
                c += 1
        return x

    def bd_fwd(self, site, d, n):
        x, c = d, 0
        while c < n:
            x = add_days(x, 1)
            if self.is_bd(site, x):
                c += 1
        return x

    def zone_of_site(self, site):
        return self.RZ.get(self.SITE_REG.get(site), Zone(0, ""))

    # ---------------- accounts
    def accounts(self):
        self.MASTER = {}
        for r in self.T("accounts_master.csv", "records"):
            if r["account_id"] and r["account_id"] not in self.MASTER:
                self.MASTER[r["account_id"]] = r
        amap = {}
        for r in sorted(self.T("account_aliases.tsv", "records"),
                        key=lambda r: (r["registered"] or "", r["alias_id"] or "")):
            if r["alias_id"] and r["account_id"]:
                amap[r["alias_id"]] = r["account_id"]
        for r in sorted(self.T("governance_charter.docx", "Account decisions"),
                        key=lambda r: (r["decided_on"] or "", r["decision_id"] or "")):
            if r["from_account"] and r["to_account"] and r["decided_on"] and r["decided_on"] <= self.L:
                amap[r["from_account"]] = r["to_account"]
        self.AMAP = amap
        self._acct = {}
        self.INTERNAL = set()
        self.BAN = {}
        for r in self.T("account_snapshot_legacy.sqlite", "accounts"):
            a = self.acct(r["account_id"])
            if a is None:
                continue
            if r["internal_flag"]:
                self.INTERNAL.add(a)
            if r["ban"]:
                self.BAN[r["ban"]] = a
        signs = {}
        cmap = {}
        for r in self.T("contracts_register.xlsx", "Contracts"):
            a = self.acct(r["account_id"])
            if a is None or not r["contract_id"]:
                continue
            cmap[r["contract_id"]] = a
            if r["signed_on"] and r["signed_on"] <= self.L:
                signs[a] = max(signs.get(a, ""), r["signed_on"])
        for r in self.T("contracts_register.xlsx", "Amendments"):
            a = cmap.get(r["contract_id"])
            if a and r["signed_on"] and r["signed_on"] <= self.L:
                signs[a] = max(signs.get(a, ""), r["signed_on"])
        self.SIGN = signs

    def acct(self, ref):
        if ref is None:
            return None
        if ref in self._acct:
            return self._acct[ref]
        x, seen = ref, set()
        while x in self.AMAP and x not in seen and len(seen) < 25:
            seen.add(x)
            x = self.AMAP[x]
        res = x if (x not in seen and x in self.MASTER) else None
        self._acct[ref] = res
        return res

    # ---------------- subscriptions, plans, enrollment
    SUB_SOURCES = (("subscriptions_central.csv", "records"), ("subscriptions_east.parquet", "records"),
                   ("subscriptions_north.sqlite", "subscriptions"), ("subscriptions_south.jsonl", "records"),
                   ("subscriptions_west.xlsx", "Subscriptions"))
    PLAN_SOURCES = (("plan_changes_central.tsv", "records"), ("plan_changes_east.json", "changes"),
                    ("plan_changes_north.xml", "Change"), ("plan_changes_south.yaml", "changes"),
                    ("plan_changes_west.log", "records"))
    ENROL_SOURCES = (("sla_enrollment_central.md", "Enrollments"), ("sla_enrollment_east.html", "Enrollments"),
                     ("sla_enrollment_north.pdf", "Enrollments"), ("sla_enrollment_south.pdf", "Enrollments"),
                     ("sla_enrollment_west.csv", "records"))

    def subs(self):
        self.SUBS = {}
        for name, table in self.SUB_SOURCES:
            for r in self.T(name, table):
                sid = r["subscription_id"]
                if not sid or sid in self.SUBS or not r["start_date"] or not r["product"] or not r["region"]:
                    continue
                a0 = max(r["start_date"], self.FIRST)
                a1 = min(r["end_date"] or self.L, self.L)
                s = {"id": sid, "account_ref": r["account_ref"], "account": self.acct(r["account_ref"]),
                     "product": r["product"], "region": r["region"], "plan0": r["plan_code"],
                     "fee": r["monthly_fee"], "currency": r["currency"], "active": a0 <= a1}
                if a0 <= a1:
                    s["a0"], s["a1"] = a0, a1
                    s["days"] = (date_ts(a1) - date_ts(a0)) // DAY + 1
                    s["w0"] = (date_ts(a0) - self.S) // WIN
                    s["w1"] = (date_ts(a1) + DAY - self.S) // WIN
                self.SUBS[sid] = s
        self.BY_ACC_REGION = {}
        for s in self.SUBS.values():
            if s["active"] and s["account"]:
                self.BY_ACC_REGION.setdefault((s["account"], s["region"]), []).append(s)

    def plans(self):
        events = []
        for name, table in self.PLAN_SOURCES:
            for r in self.T(name, table):
                if r["change_id"] and r["subscription_id"] and r["effective"] is not None and r["effective"] < self.E:
                    events.append(r)
        voided = {r["reverts"] for r in events if r["action"] == "REVERT" and r["reverts"]}
        best = {}
        for r in events:
            if r["action"] != "APPLY" or r["change_id"] in voided or not r["plan_code"]:
                continue
            k = (r["effective"], r["change_id"])
            if r["subscription_id"] not in best or k > best[r["subscription_id"]][0]:
                best[r["subscription_id"]] = (k, r["plan_code"])
        for sid, s in self.SUBS.items():
            p = best[sid][1] if sid in best else s["plan0"]
            p = self.LEGACY.get(p, p)
            s["plan"] = p
            s["segment"] = self.SEG.get(p)

    def enrollment(self):
        best = {}
        for name, table in self.ENROL_SOURCES:
            for r in self.T(name, table):
                if r["subscription_id"] and r["effective"] and r["effective"] <= self.L:
                    k = (r["effective"], r["enrollment_id"] or "")
                    if r["subscription_id"] not in best or k > best[r["subscription_id"]][0]:
                        best[r["subscription_id"]] = (k, r)
        for sid, s in self.SUBS.items():
            r = best.get(sid, (None, None))[1]
            s["sla_class"] = r["sla_class"] if (r and r["action"] == "ENROLLED" and r["sla_class"]) else None

    # ---------------- service level terms
    @staticmethod
    def _v(x):
        return (x or "").strip().lower()

    def sla_terms(self):
        pins = {}
        for r in self.T("sla_policy_2026.docx", "Subscription pins"):
            if r["subscription_id"] and r["pinned_on"] and r["pinned_on"] <= self.L and r["version"]:
                k = (r["pinned_on"], r["pin_id"] or "")
                if r["subscription_id"] not in pins or k > pins[r["subscription_id"]][0]:
                    pins[r["subscription_id"]] = (k, self._v(r["version"]))
        cut = sorted((r["signed_from"], self._v(r["version"])) for r in self.T("sla_policy_2026.docx",
                                                                             "Version cutovers")
                     if r["signed_from"] and r["version"])
        self.TARGET, self.TIER, self.PERMILLE = {}, {}, {}
        for name, tt, ti, th in (("sla_policy_2026.docx", "Service targets", "Credit tiers", "Bad window thresholds"),
                                 ("sla_policy_v4_draft.docx", "Legacy schedule v2 targets",
                                  "Legacy schedule v2 tiers", "Legacy schedule v2 thresholds")):
            legacy = name == "sla_policy_v4_draft.docx"
            for r in self.T(name, tt):
                v = self._v(r["version"])
                if r["sla_class"] and (v == "v2") == legacy:
                    self.TARGET[(v, r["sla_class"])] = r["target_pct"]
            for r in self.T(name, ti):
                v = self._v(r["version"])
                if (v == "v2") == legacy and r["credit_pct"] is not None:
                    self.TIER.setdefault(v, []).append((self._v(r["kind"]), r["threshold"], r["credit_pct"]))
            for r in self.T(name, th):
                v = self._v(r["version"])
                if (v == "v2") == legacy and r["permille"] is not None:
                    self.PERMILLE[v] = r["permille"]
        v5 = {}
        for r in self.T("credit_tiers_2026.xlsx", "Ratified"):
            if r["product"] and r["region"] and r["sla_class"] and r["effective"] and r["effective"] <= self.L:
                key = (r["product"], r["region"], r["sla_class"])
                k = (r["effective"], r["target_id"] or "")
                if key not in v5 or k > v5[key][0]:
                    v5[key] = (k, r["target_pct"])
        revoked = {r["schedule_id"] for r in self.T("credit_tiers_2026.xlsx", "Revocations")
                   if r["status"] == "RATIFIED" and r["revoked_on"] and r["revoked_on"] <= self.L}
        sched = {}
        for r in self.T("enterprise_sla_schedules.pdf", "Schedules"):
            if (r["subscription_id"] and r["effective"] and r["effective"] <= self.L
                    and r["schedule_id"] not in revoked and r["target_pct"] is not None):
                k = (r["effective"], r["schedule_id"] or "")
                if r["subscription_id"] not in sched or k > sched[r["subscription_id"]][0]:
                    sched[r["subscription_id"]] = (k, r)
        self.BETA = set()
        for r in self.T("uptime_dashboard_snapshot.html", "Beta product-regions"):
            if r["product"] and r["region"] and r["beta_from"] and r["beta_from"] <= self.L and (
                    r["beta_to"] is None or r["beta_to"] > self.L):
                self.BETA.add((r["product"], r["region"]))
        for sid, s in self.SUBS.items():
            a = s["account"]
            s["schedule"] = None
            if s.get("segment") == "enterprise" and sid in sched:
                sc = sched[sid][1]
                s["schedule"] = sc
                s["version"] = "custom"
                s["target"] = sc["target_pct"]
                s["permille"] = self.PERMILLE.get("v5")
                continue
            if sid in pins:
                v = pins[sid][1]
            else:
                sign = self.SIGN.get(a) or (self.MASTER[a]["created"] if a in self.MASTER else None) or ""
                v = None
                for frm, ver in cut:
                    if frm <= sign:
                        v = ver
            s["version"] = v
            if v == "v5":
                s["target"] = v5.get((s["product"], s["region"], s["sla_class"]), (None, None))[1]
            else:
                s["target"] = self.TARGET.get((v, s["sla_class"]))
            s["permille"] = self.PERMILLE.get(v)

    def credit_pct(self, s, uptime):
        if s["target"] is None:
            return 0
        if s["schedule"] is not None:
            return s["schedule"]["credit_pct"] if uptime < s["target"] else 0
        pct = 0
        for kind, thr, p in self.TIER.get(s["version"], []):
            if thr is None:
                continue
            hit = uptime < (s["target"] - thr) if kind == "rel" else uptime < thr
            if hit and p > pct:
                pct = p
        return pct

    # ---------------- fees
    def fees(self):
        ov = {}
        for t in ("Overrides A", "Overrides B"):
            for r in self.T("fee_overrides.xlsx", t):
                if (r["subscription_id"] and r["status"] == "APPROVED" and r["approved_on"]
                        and r["approved_on"] <= self.L and isinstance(r["fee_minor"], int)):
                    k = (r["revision"] or 0, r["override_id"] or "")
                    if r["subscription_id"] not in ov or k > ov[r["subscription_id"]][0]:
                        ov[r["subscription_id"]] = (k, r["fee_minor"])
        price = {}
        for r in self.T("price_book.toml", "price"):
            if r["plan"] and r["product"] and r["currency"] and r["effective"] and r["effective"] <= self.L \
                    and isinstance(r["amount"], int):
                key = (r["plan"], r["product"], r["currency"])
                k = (r["effective"], r["price_id"] or "")
                if key not in price or k > price[key][0]:
                    price[key] = (k, r["amount"])
        disc = {}
        for r in self.T("subscriptions_west.xlsx", "Contract discounts"):
            a = self.acct(r["account_ref"])
            if a and r["effective"] and r["effective"] <= self.L and r["discount_bp"] is not None:
                k = (r["effective"], r["discount_id"] or "")
                if a not in disc or k > disc[a][0]:
                    disc[a] = (k, r["discount_bp"])
        for sid, s in self.SUBS.items():
            if sid in ov:
                fee = ov[sid][1]
            elif isinstance(s["fee"], int):
                fee = s["fee"]
            else:
                lst = price.get((s.get("plan"), s["product"], s["currency"]), (None, 0))[1]
                bp = disc.get(s["account"], (None, 0))[1]
                fee = half_even(Fraction(lst * (10000 - bp), 10000))
            s["fee_minor"] = fee

    # ---------------- claims
    def claims(self):
        site_of = {}
        for r in self.T("credit_operations_manual.docx", "Account calendar sites"):
            a = self.acct(r["account_id"])
            if a and r["calendar_site"]:
                site_of[a] = r["calendar_site"]
        withdrawn_refs = {r["ref"] for r in self.T("claims_workflow.log", "records")
                          if r["event"] == "WITHDRAWN" and r["ref"]}
        crossref = {r["ref"]: r["claim_id"] for r in self.T("sla_report_draft.pdf", "Claim references")
                    if r["ref"] and r["claim_id"]}
        withdrawn = {crossref[x] for x in withdrawn_refs if x in crossref}
        cases = {r["case_id"]: r for r in self.T("claims_crm_legacy.csv", "records") if r["case_id"]}
        orders = {r["order_ref"]: r["subscription_id"] for r in self.T("source_register.md",
                                                                      "Legacy order references")
                  if r["order_ref"] and r["subscription_id"]}
        cand = []
        for r in self.T("claims_portal.csv", "records"):
            cand.append((r["claim_id"], r["subscription_id"], r["filed_at"]))
        for r in self.T("support_tickets.jsonl", "records"):
            if r["category"] != "SLA_CLAIM":
                continue
            sid = None
            if r["crm_case"] and r["crm_case"] in cases:
                sid = cases[r["crm_case"]]["subscription_id"]
            elif r["order_ref"]:
                sid = orders.get(r["order_ref"])
            cand.append((r["ticket_id"], sid, r["opened_at"]))
        dec = {}
        for r in self.T("claims_backoffice.xlsx", "Decisions"):
            if r["receipt_id"] and r["decided_on"]:
                k = (r["decided_on"], r["decision_id"] or "")
                if r["receipt_id"] not in dec or k > dec[r["receipt_id"]][0]:
                    dec[r["receipt_id"]] = (k, r["decision"])
        for r in self.T("claims_backoffice.xlsx", "Received"):
            if dec.get(r["receipt_id"], (None, None))[1] == "REJECTED":
                continue
            s = self.SUBS.get(r["subscription_id"])
            if s is None or not s["account"] or self.BAN.get(r["ban"]) != s["account"]:
                continue
            cand.append((r["receipt_id"], r["subscription_id"], r["received"]))
        for r in cases.values():
            s = self.SUBS.get(r["subscription_id"])
            if s is not None and s.get("segment") == "smb" and r["filed_at"] is not None and r["filed_at"] < self.CUT:
                cand.append((r["case_id"], r["subscription_id"], r["filed_at"]))
        best = {}
        for cid, sid, filed in cand:
            if not cid or not sid or filed is None or cid in withdrawn or filed < self.S:
                continue
            s = self.SUBS.get(sid)
            if s is None:
                continue
            site = site_of.get(s["account"], self.RSITE.get(s["region"]))
            local = day_of(self.zone_of_site(site).naive(filed))
            if local > self.bd_fwd(site, self.L, 10):
                continue
            k = (filed, cid)
            if sid not in best or k < best[sid]:
                best[sid] = k
        self.CLAIM = best
        self.AUTO = {r["account_id"] for r in self.T("credit_preferences.json", "preferences")
                     if r["account_id"] and r["auto_credit"]}
        self.AUTO = {self.acct(a) for a in self.AUTO} - {None}

    # ---------------- currency conversion
    def fx(self):
        recalled = {r["fixing_id"] for r in self.T("fx_rates_unofficial.json", "recalls") if r["fixing_id"]}
        best = {}
        for r in self.T("fx_hourly_treasury.csv", "records"):
            if r["currency"] and r["hour"] is not None and r["fixing_id"] not in recalled:
                key = (r["currency"], r["hour"])
                k = (r["revision"] or 0, r["fixing_id"] or "")
                if key not in best or k > best[key][0]:
                    best[key] = (k, r["usd_per_unit"])
        have = {c for c, _ in best}
        for r in self.T("fx_rates_unofficial.json", "rates"):
            if r["currency"] and r["currency"] not in have and r["hour"] is not None and r["fixing_id"] not in recalled:
                key = (r["currency"], r["hour"])
                k = (0, r["fixing_id"] or "")
                if key not in best or k > best[key][0]:
                    best[key] = (k, r["usd_per_unit"])
        series = {}
        for (c, h), (_, v) in best.items():
            series.setdefault(c, []).append((h, v))
        self.FX = {c: sorted(v) for c, v in series.items()}
        self.FXH = {c: [h for h, _ in v] for c, v in self.FX.items()}

    def rate(self, ccy, t):
        if ccy == "USD":
            return Fraction(1)
        if ccy not in self.FX:
            return None
        import bisect
        h = (t // 3600) * 3600
        j = bisect.bisect_right(self.FXH[ccy], h) - 1
        return self.FX[ccy][j][1] if j >= 0 else None

    # ---------------- caps and quarter-to-date
    def caps(self):
        cap = {}
        for t in ("Caps", "Caps continued"):
            for r in self.T("account_caps.xlsx", t):
                a = self.acct(r["account_ref"])
                if a and r["effective"] and r["effective"] <= self.L and isinstance(r["quarterly_cap_usd"], int):
                    k = (r["effective"], r["cap_id"] or "")
                    if a not in cap or k > cap[a][0]:
                        cap[a] = (k, r["quarterly_cap_usd"])
        self.CAP = {a: v for a, (_, v) in cap.items()}
        voided = {r["posting_id"] for r in self.T("sla_report_draft.pdf", "Voided July postings") if r["posting_id"]}
        qtd = {}
        for r in self.T("credit_ledger.sqlite", "postings"):
            a = self.acct(r["account_ref"])
            if (a and r["posted_at"] is not None and self.Q <= r["posted_at"] < self.S
                    and r["posting_id"] not in voided and isinstance(r["amount_usd_cents"], int)):
                sign = 1 if r["kind"] == "CREDIT" else -1 if r["kind"] == "REVERSAL" else 0
                qtd[a] = qtd.get(a, 0) + sign * r["amount_usd_cents"]
        for r in self.T("credit_ledger.sqlite", "goodwill"):
            a = self.acct(r["account_ref"])
            if a and r["granted_at"] is not None and self.Q <= r["granted_at"] < self.E \
                    and isinstance(r["amount_usd_cents"], int):
                qtd[a] = qtd.get(a, 0) + r["amount_usd_cents"]
        if self.prior is not None:
            p = self.prior / "normalized.jsonl"
            if p.is_file():
                for ln in p.read_text(encoding="utf-8").splitlines():
                    if not ln.strip():
                        continue
                    o = json.loads(ln)
                    if o.get("status") == "CREDITED" and o.get("account_id"):
                        qtd[o["account_id"]] = qtd.get(o["account_id"], 0) + int(o.get("credit_usd_cents") or 0)
        self.QTD = qtd

    # ---------------- window ranges
    def wr(self, t0, t1):
        if t0 is None or t1 is None:
            return None
        a = max(0, ceil_div(t0 - self.S, WIN))
        b = min(self.NW, ceil_div(t1 - self.S, WIN))
        return (a, b) if a < b else None

    @staticmethod
    def merge(rs):
        out = []
        for a, b in sorted(r for r in rs if r):
            if out and a <= out[-1][1]:
                if b > out[-1][1]:
                    out[-1] = (out[-1][0], b)
            else:
                out.append((a, b))
        return out

    @staticmethod
    def rcount(rs):
        return sum(b - a for a, b in rs)

    @staticmethod
    def rinter(A, B):
        out, i, j = [], 0, 0
        while i < len(A) and j < len(B):
            a, b = max(A[i][0], B[j][0]), min(A[i][1], B[j][1])
            if a < b:
                out.append((a, b))
            if A[i][1] < B[j][1]:
                i += 1
            else:
                j += 1
        return out

    @staticmethod
    def rin(rs, w):
        from bisect import bisect_right
        k = bisect_right(rs, (w, float("inf"))) - 1
        return k >= 0 and rs[k][0] <= w < rs[k][1]

    def widx(self, t):
        if t is None or t < self.S or t >= self.E:
            return None
        return (t - self.S) // WIN

    # ---------------- telemetry
    def telemetry(self):
        self.PREC = {}
        for r in self.T("telemetry_collection_standard.docx", "Collector precedence"):
            if r["collector"] and r["precedence"] is not None:
                self.PREC[r["collector"]] = (r["precedence"], r["lane"])
        lane = {}
        for r in self.T("telemetry_collection_standard.docx", "Host lane assignments"):
            if r["host"] and r["assigned_on"] and r["assigned_on"] <= self.L:
                k = (r["assigned_on"], r["_i"])
                if r["host"] not in lane or k > lane[r["host"]][0]:
                    lane[r["host"]] = (k, r["lane"])
        self.LANE = {h: v[1] for h, v in lane.items()}
        self.INV = {}
        for r in self.T("host_inventory.csv", "records"):
            if r["host"] and r["host"] not in self.INV:
                self.INV[r["host"]] = (r["region"], r["product"])
        bst = {}
        for r in self.T("ingest_batches.jsonl", "records"):
            if r["batch_id"]:
                k = (r["loaded_at"] or 0, r["batch_id"])
                if r["batch_id"] not in bst or k > bst[r["batch_id"]][0]:
                    bst[r["batch_id"]] = (k, r["status"])
        replay = {r["batch"] for r in self.T("ingest_reprocess.log", "records") if r["event"] == "REPLAY" and r["batch"]}
        self.BATCH_OK = {b for b, v in bst.items() if v[1] == "LOADED" and b not in replay}
        vs = {}
        for r in sorted((r for r in self.T("telemetry_voids.jsonl", "records") if r["target"] and r["at"] is not None),
                        key=lambda r: (r["at"], r["void_id"] or "")):
            vs[r["target"]] = r["action"]
        self.VOIDED = {k for k, v in vs.items() if v == "VOID"}
        for r in self.T("lb_errors_east_replay.csv", "records"):
            if r["marker"] == "VOID" and r["record_id"]:
                self.VOIDED.add(r["record_id"])
        self.NODE = {}
        for r in self.T("svc_metrics_compacted.parquet", "records"):
            if r["kind"] == "TOMBSTONE" and r["target"]:
                self.VOIDED.add(r["target"])
            elif r["kind"] == "ALIAS" and r["node"] and r["host"]:
                self.NODE[r["node"]] = r["host"]
        self.QUAR = {}
        for r in self.T("telemetry_quarantine.json", "quarantine"):
            if r["host"] and r["status"] == "ACTIVE" and r["from"] is not None:
                self.QUAR.setdefault(r["host"], []).append((r["from"], r["to"] if r["to"] is not None else float("inf")))
        samp = {}
        for r in self.T("lb_sampling.parquet", "records"):
            if r["host"] and r["effective_from"] is not None and r["one_in"]:
                samp.setdefault(r["host"], []).append((r["effective_from"], r["sampling_id"] or "", r["one_in"]))
        self.SAMP = {h: sorted(v) for h, v in samp.items()}
        # LB schema state
        self.VINC = {self._v(r["version"]): bool(r["err_5xx_includes_429"])
                     for r in self.T("schema_registry.yaml", "versions") if r["version"]}
        base = {}
        for r in self.T("schema_registry.yaml", "baseline"):
            if r["host"] and r["schema"] and (r["as_of"] is None or r["as_of"] <= self.L):
                k = (r["as_of"] or "", r["_i"])
                if r["host"] not in base or k > base[r["host"]][0]:
                    base[r["host"]] = (k, self._v(r["schema"]))
        self.BASE = {h: v[1] for h, v in base.items()}
        aborted = {r["event_id"] for r in self.T("collector_schema_proposed.yaml", "aborted_rollouts") if r["event_id"]}
        mem = {}
        for r in self.T("deploy_manifests.xml", "Member"):
            if r["wave"] and r["host"] and r["revision"] is not None:
                mem.setdefault(r["wave"], {}).setdefault(r["revision"], set()).add(r["host"])
        members = {w: v[max(v)] for w, v in mem.items()}
        self.SCH_EV = {}
        for r in self.T("deploy_events.log", "records"):
            if r["event"] in ("ROLLOUT", "ROLLBACK") and r["event_id"] not in aborted and r["ts"] is not None \
                    and r["schema"] and r["wave"]:
                for h in members.get(r["wave"], ()):
                    self.SCH_EV.setdefault(h, []).append((r["ts"], r["seq"] or 0, self._v(r["schema"])))
        gaps = []
        for r in self.T("telemetry_collection_standard.docx", "Collector gap windows"):
            if r["region"] and r["from"] is not None and r["to"] is not None:
                gaps.append((r["region"], r["collector"], r["from"], r["to"]))
        self.GAPS = gaps
        self.BEST = {}
        self._lb()
        self._svc()
        self._edge()
        self._cdn()
        self._sdk()
        self._judge()

    def quarantined(self, host, t):
        return any(a <= t < b for a, b in self.QUAR.get(host, ()))

    def one_in(self, host, t):
        n = 1
        for eff, _, k in self.SAMP.get(host, ()):
            if eff <= t:
                n = k
            else:
                break
        return n

    def schema_at(self, host, t):
        best = None
        for ts_, seq, sch in self.SCH_EV.get(host, ()):
            if ts_ <= t and (best is None or seq > best[0]):
                best = (seq, sch)
        return best[1] if best else self.BASE.get(host)

    def valid(self, coll, rid, batch, sid, host, t):
        s = self.SUBS.get(sid)
        if not s or not rid or not s["active"] or self.widx(t) is None:
            return False
        if batch not in self.BATCH_OK or rid in self.VOIDED:
            return False
        if coll != "SDK":
            inv = self.INV.get(host)
            if not inv or inv != (s["region"], s["product"]):
                return False
            if coll not in self.PREC or self.LANE.get(host) != self.PREC[coll][1]:
                return False
            if self.quarantined(host, t):
                return False
        return True

    def offer(self, coll, rid, seq, sid, t, R, e5, e429):
        if coll not in self.PREC or e5 < 0 or e429 < 0:
            return
        w = self.widx(t)
        key = (-self.PREC[coll][0], seq or 0, rid)
        cur = self.BEST.get((sid, w))
        if cur is None or key > cur[0]:
            self.BEST[(sid, w)] = (key, R, e5, e429)

    def _lb_row(self, r):
        sid, host, t = r["subscription"], r["host"], r["window_start"]
        if not self.valid("LB", r["record_id"], r["batch_id"], sid, host, t):
            return
        e5, e429 = r["err_5xx"], r["err_429"]
        if self.VINC.get(self.schema_at(host, t), False):
            e5 = e5 - e429
        n = self.one_in(host, t)
        self.offer("LB", r["record_id"], r["seq"], sid, t, r["requests"] * n, e5 * n, e429 * n)

    def _lb(self):
        for g in ("central", "east", "north", "south", "west"):
            for r in self.T("lb_errors_%s.csv" % g, "records"):
                self._lb_row(r)
        for r in self.T("lb_errors_east_replay.csv", "records"):
            if r["marker"] != "GAPFILL" or r["window_start"] is None:
                continue
            inv = self.INV.get(r["host"])
            t = r["window_start"]
            if inv and any(g[0] == inv[0] and g[1] == "LB" and g[2] <= t < g[3] for g in self.GAPS):
                self._lb_row(r)

    def _svc(self):
        for name in ("svc_metrics_part1.parquet", "svc_metrics_part2.parquet", "svc_metrics_part3.parquet"):
            for r in self.T(name, "records"):
                host = self.NODE.get(r["node"])
                sid, t = r["subscription"], r["window_start_ms"]
                if not host or not self.valid("SVC", r["record_id"], r["batch_id"], sid, host, t):
                    continue
                R = r["requests_k"] if "requests_k" in r else r["requests"]
                self.offer("SVC", r["record_id"], r["seq"], sid, t, R, r["err_5xx"], r["err_429"])

    def _edge(self):
        meas = {}
        for name in ("host_clock_edge_a.ini", "host_clock_edge_b.ini", "host_clock_edge_c.ini"):
            for r in self.T(name, "measure"):
                if r["host"] and r["measured_at"] is not None and r["skew_s"] is not None:
                    meas.setdefault(r["host"], []).append((r["measured_at"], r["measurement_id"] or "", r["skew_s"]))
        meas = {h: sorted(v) for h, v in meas.items()}
        for name in ("edge_legacy_a.txt", "edge_legacy_b.txt", "edge_legacy_c.txt"):
            for r in self.T(name, "records"):
                host, rd = r["host"], r["reading"]
                inv = self.INV.get(host)
                if not inv or rd is None or inv[0] not in self.RZ:
                    continue
                u = self.RZ[inv[0]].to_utc(rd)
                skew = 0
                for m_at, _, sk in meas.get(host, ()):
                    if m_at <= u:
                        skew = sk
                    else:
                        break
                t = u - skew
                sid = r["subscription"]
                if self.valid("EDGE", r["record_id"], r["batch_id"], sid, host, t):
                    self.offer("EDGE", r["record_id"], r["seq"], sid, t, r["requests"], r["err_5xx"], r["err_429"])

    def _cdn(self):
        for name in ("cdn_logs_fastedge.xml", "cdn_logs_akamoto.xml"):
            for r in self.T(name, "Window"):
                sid, t = r["subscription"], r["window_epoch"]
                if self.valid("CDN-XML", r["record_id"], r["batch_id"], sid, r["host"], t):
                    self.offer("CDN-XML", r["record_id"], r["seq"], sid, t, r["requests"], r["err_5xx"], r["err_429"])
        for sheet in ("Fastedge", "Akamoto"):
            for r in self.T("cdn_attestations.xlsx", sheet):
                sid, t = r["subscription"], r["window_start"]
                if self.valid("CDN-ATT", r["record_id"], r["batch_id"], sid, r["host"], t):
                    self.offer("CDN-ATT", r["record_id"], r["seq"], sid, t, r["requests"], r["err_5xx"], r["err_429"])

    def _sdk(self):
        install, withdrawn = {}, set()
        for r in self.T("client_sdk_dedup.jsonl", "records"):
            if r["kind"] == "INSTALL" and r["install_id"] and r["subscription"]:
                install[r["install_id"]] = r["subscription"]
            elif r["kind"] == "WITHDRAWN_BUILD" and r["build"]:
                withdrawn.add(r["build"])
        builds = {}
        for r in self.T("sdk_builds.json", "builds"):
            if r["build"]:
                builds[r["build"]] = r
        rec = {}
        for r in self.T("sdk_server_receipts.csv", "records"):
            if r["event_id"] and r["received_at"] is not None:
                rec[r["event_id"]] = r["received_at"]
        for name in ("sdk_events_1.jsonl", "sdk_events_2.jsonl", "sdk_events_3.jsonl"):
            for r in self.T(name, "records"):
                b = builds.get(r["build"])
                if not b or b["status"] == "RECALLED" or r["build"] in withdrawn:
                    continue
                sid = install.get(r["install_id"])
                t = rec.get(r["event_id"]) if b["clock"] == "DEVICE" else r["ts"]
                if t is None or not self.valid("SDK", r["event_id"], r["batch_id"], sid, None, t):
                    continue
                self.offer("SDK", r["event_id"], r["seq"], sid, t, r["requests"], r["errors_5xx"], r["errors_429"])

    def _judge(self):
        base = {}
        files = (("quotas_central.yaml", "quotas"), ("quotas_east.toml", "quota"), ("quotas_north.sqlite", "quotas"),
                 ("quotas_south.md", "Quotas"), ("quotas_west.html", "Quotas"))
        for fi, (name, table) in enumerate(files):
            for r in self.T(name, table):
                if r["subscription"] and r["quota_per_window"] is not None and r["as_of"] and r["as_of"] <= self.L:
                    k = (r["as_of"], fi, r["_i"])
                    if r["subscription"] not in base or k > base[r["subscription"]][0]:
                        base[r["subscription"]] = (k, r["quota_per_window"])
        qc = {}
        for r in self.T("quota_changes.tsv", "records"):
            if r["subscription"] and r["effective"] is not None and r["quota"] is not None:
                qc.setdefault(r["subscription"], []).append((r["effective"], r["change_id"] or "", r["quota"]))
        qc = {k: sorted(v) for k, v in qc.items()}
        self.TELW, self.TELBAD = {}, {}
        for (sid, w), (_, R, e5, e429) in self.BEST.items():
            s = self.SUBS[sid]
            self.TELW.setdefault(sid, set()).add(w)
            pm = s.get("permille")
            if pm is None or R <= 0:
                continue
            ws = self.S + w * WIN
            q = base[sid][1] if sid in base else 0
            for eff, _, v in qc.get(sid, ()):
                if eff <= ws:
                    q = v
                else:
                    break
            c429 = e429 if (q == 0 or R <= q) else 0
            if (e5 + c429) * 1000 >= pm * R:
                self.TELBAD.setdefault(sid, set()).add(w)

    # ---------------- probes and declared outages
    def probes(self):
        vmap, flap = {}, set()
        for r in self.T("probe_results_mirror.tsv", "records"):
            if r["kind"] == "VANTAGE" and r["vantage"] and r["vantage_id"]:
                vmap[r["vantage"]] = r["vantage_id"]
            elif r["kind"] == "FLAPVOID" and r["probe_id"]:
                flap.add(r["probe_id"])
        retired = {r["retired_id"]: r["target_id"] for r in self.T("uptime_dashboard_snapshot.html", "Retired probe targets")
                   if r["retired_id"] and r["target_id"]}
        targets = {r["target_id"]: (r["product"], r["region"]) for r in self.T("probe_targets.json", "targets")
                   if r["target_id"] and r["product"] and r["region"]}
        down = {}
        for name in ("probes_core.tsv", "probes_data.tsv", "probes_compute.tsv"):
            for r in self.T(name, "records"):
                if r["status"] != "DOWN" or r["probe_id"] in flap or not r["probe_id"]:
                    continue
                v = vmap.get(r["vantage"])
                tg = targets.get(retired.get(r["target"], r["target"]))
                w = self.widx(r["observed_at"])
                if v is None or tg is None or w is None:
                    continue
                down.setdefault((tg, w), set()).add(v)
        self.OUTAGE = {}
        for (pr, w), vs in down.items():
            if len(vs) >= 2:
                self.OUTAGE.setdefault(pr, set()).add(w)
        retracted = {r["noc_id"] for r in self.T("incident_register_preliminary.xml", "Retraction") if r["noc_id"]}
        for r in self.T("noc_outage_declarations.pdf", "Declarations"):
            if r["status"] != "CONFIRMED" or r["noc_id"] in retracted or not r["product"] or not r["region"]:
                continue
            rg = self.wr(r["start"], r["end"])
            if rg:
                self.OUTAGE.setdefault((r["product"], r["region"]), set()).update(range(rg[0], rg[1]))

    # ---------------- incidents and dependency links
    def incidents(self):
        final = {r["prelim_id"]: r["final_id"] for r in self.T("incident_register_preliminary.xml", "Preliminary")
                 if r["prelim_id"] and r["final_id"]}
        inc = {}
        for r in self.T("incident_register.xml", "Incident"):
            if r["incident_id"] and r["opened"] is not None and r["product"] and r["region"] \
                    and r["incident_id"] not in inc:
                inc[r["incident_id"]] = {"pr": (r["product"], r["region"]),
                                         "iv": [[r["opened"], r["closed"] if r["closed"] is not None else self.E]]}
        ups = [r for r in self.T("incident_register.xml", "Update") if r["ref"] and r["at"] is not None]
        for r in sorted(ups, key=lambda r: (r["at"], r["update_id"] or "")):
            i = inc.get(final.get(r["ref"], r["ref"]))
            if not i:
                continue
            last = i["iv"][-1]
            if r["action"] == "EXTEND" and r["until"] is not None:
                last[1] = max(last[1], r["until"])
            elif r["action"] == "CLOSE" and r["until"] is not None:
                last[1] = r["until"]
            elif r["action"] == "REOPEN":
                i["iv"].append([r["at"], r["until"] if r["until"] is not None else self.E])
        incw = {}
        for i in inc.values():
            for a, b in i["iv"]:
                incw.setdefault(i["pr"], []).append(self.wr(a, b))
        self.INCW = {k: self.merge(v) for k, v in incw.items()}
        links = {}
        rows = list(self.T("dependency_links.tsv", "records")) + \
            list(self.T("incident_attribution_policy.docx", "Dependency declarations"))
        for r in rows:
            if r["downstream"] and r["upstream"] and r["registered_at"] is not None and r["action"] in ("ADD", "REMOVE"):
                links.setdefault((r["downstream"], r["upstream"]), []).append(
                    (r["registered_at"], r["link_id"] or "", r["action"]))
        self.LINKS = {k: sorted(v) for k, v in links.items()}
        self.UPS = {}
        for r in self.T("incident_attribution_policy.docx", "Service dependencies"):
            if r["product"] and r["upstream"]:
                self.UPS.setdefault(r["product"], set()).add(r["upstream"])

    def link_active(self, d, u, t):
        st = None
        for at, _, act in self.LINKS.get((d, u), ()):
            if at <= t:
                st = act
            else:
                break
        return st == "ADD"

    def attributed(self, s, w):
        ups = self.UPS.get(s["product"])
        if not ups or not s["account"]:
            return False
        t = self.S + w * WIN
        for u in self.BY_ACC_REGION.get((s["account"], s["region"]), ()):
            if u["product"] in ups and u["w0"] <= w < u["w1"] and self.link_active(s["id"], u["id"], t) \
                    and self.rin(self.INCW.get((u["product"], s["region"]), []), w):
                return True
        return False

    # ---------------- maintenance and suspensions
    def _ics_time(self, v):
        if not v or "|" not in v:
            return None
        tz, val = v.split("|", 1)
        val = val.strip()
        m = re.fullmatch(r"(\d{8})T(\d{6})(Z?)", val)
        if not m:
            return None
        d, hms = m.group(1), m.group(2)
        naive = ts_of("%s-%s-%sT%s:%s:%s" % (d[:4], d[4:6], d[6:], hms[:2], hms[2:4], hms[4:]))
        if m.group(3) or not tz:
            return naive
        z = self.TZ.get(tz.strip())
        return z.to_utc(naive) if z else None

    def maintenance(self):
        appr = {}
        for r in self.T("maintenance_changes.xlsx", "Approvals"):
            if r["change_id"] and r["seq"] is not None:
                k = (r["seq"], r["approval_id"] or "")
                if r["change_id"] not in appr or k > appr[r["change_id"]][0]:
                    appr[r["change_id"]] = (k, r["decision"])
        ics = {}
        for r in self.T("change_calendar.ics", "records"):
            if r["uid"]:
                k = (r["sequence"] or 0, r["_i"])
                if r["uid"] not in ics or k > ics[r["uid"]][0]:
                    ics[r["uid"]] = (k, r)
        notice = {}
        for r in self.T("maintenance_notices.mbox", "records"):
            if r["change_id"] and r["sent"] is not None:
                if r["change_id"] not in notice or r["sent"] < notice[r["change_id"]]:
                    notice[r["change_id"]] = r["sent"]
        maint, seen = {}, set()
        for r in self.T("maintenance_changes.xlsx", "Changes"):
            cid = r["change_id"]
            if not cid or cid in seen or r["type"] != "PLANNED" or not r["region"] or not r["product"]:
                continue
            seen.add(cid)
            if appr.get(cid, (None, None))[1] != "APPROVED" or r["region"] not in self.RZ:
                continue
            z = self.RZ[r["region"]]
            if r["start_local"] is None or r["end_local"] is None:
                continue
            st, en = z.to_utc(r["start_local"]), z.to_utc(r["end_local"])
            if cid in ics:
                ev = ics[cid][1]
                if ev["status"] == "CANCELLED":
                    continue
                a, b = self._ics_time(ev["dtstart"]), self._ics_time(ev["dtend"])
                if a is not None and b is not None:
                    st, en = a, b
            if cid not in notice:
                continue
            site = self.RSITE.get(r["region"])
            start_day = day_of(z.naive(st))
            if day_of(z.naive(notice[cid])) > self.bd_back(site, start_day, 5):
                continue
            maint.setdefault((r["product"], r["region"]), []).append(self.wr(st, en))
        self.MAINT = {k: self.merge(v) for k, v in maint.items()}

    def suspensions(self):
        ev = {}
        for r in self.T("lifecycle_events.log", "records"):
            if r["subscription"] and r["ts"] is not None and r["event"] in ("SUSPEND", "RESUME"):
                ev.setdefault(r["subscription"], []).append((r["ts"], r["event_id"] or "", r["event"]))
        susp = {}
        for sid, lst in ev.items():
            op = None
            for t, _, e in sorted(lst):
                if e == "SUSPEND" and op is None:
                    op = t
                elif e == "RESUME" and op is not None:
                    susp.setdefault(sid, []).append(self.wr(op, t))
                    op = None
            if op is not None:
                susp.setdefault(sid, []).append(self.wr(op, self.E))
        for r in self.T("suspension_orders.pdf", "Orders"):
            if r["subscription"] and r["status"] == "ACTIVE" and r["from"] is not None:
                susp.setdefault(r["subscription"], []).append(
                    self.wr(r["from"], r["to"] if r["to"] is not None else self.E))
        self.SUSP = {k: self.merge(v) for k, v in susp.items()}

    # ---------------- per-subscription window accounting
    def windows(self, s):
        sid, pr = s["id"], (s["product"], s["region"])
        A = [(s["w0"], s["w1"])]
        SU = self.SUSP.get(sid, [])
        SM = self.merge(SU + self.MAINT.get(pr, []))
        susp = self.rcount(self.rinter(A, SU))
        asm = self.rcount(self.rinter(A, SM))
        res = {"active_windows": s["w1"] - s["w0"], "suspended_windows": susp,
               "maintenance_windows": asm - susp, "eligible_windows": s["w1"] - s["w0"] - asm}

        def elig(w):
            return s["w0"] <= w < s["w1"] and not self.rin(SM, w)
        tel = {w for w in self.TELW.get(sid, ()) if elig(w)}
        tbad = {w for w in self.TELBAD.get(sid, ()) if elig(w)}
        out = {w for w in self.OUTAGE.get(pr, ()) if elig(w)}
        bad0 = tbad | out
        attr = {w for w in bad0 if self.attributed(s, w)}
        bad = bad0 - attr
        res.update({"telemetry_windows": len(tel), "outage_windows": len(out), "bad_windows": len(bad),
                    "attributed_windows": len(attr),
                    "bad_window_digest": sha16(",".join(str(w) for w in sorted(bad)))})
        return res

    # ---------------- record assembly
    EXCLUSION_ORDER = ("UNKNOWN_ACCOUNT", "INTERNAL_ACCOUNT", "BETA_PRODUCT_REGION", "NO_SLA_ENROLLMENT")

    def exclusion(self, s):
        if s["account"] is None:
            return "UNKNOWN_ACCOUNT"
        if s["account"] in self.INTERNAL:
            return "INTERNAL_ACCOUNT"
        if (s["product"], s["region"]) in self.BETA:
            return "BETA_PRODUCT_REGION"
        if s.get("sla_class") is None:
            return "NO_SLA_ENROLLMENT"
        return None

    def assemble(self):
        self.records, self.exclusions = [], []
        running = {}
        for sid in sorted(self.SUBS):
            s = self.SUBS[sid]
            if not s["active"]:
                continue
            why = self.exclusion(s)
            if why:
                self.exclusions.append({"subscription_id": sid, "reason": why})
                continue
            a = s["account"]
            w = self.windows(s)
            el, bad = w["eligible_windows"], w["bad_windows"]
            uptime = Fraction(100 * (el - bad), el) if el else Fraction(100)
            pct = self.credit_pct(s, uptime)
            fee = s["fee_minor"]
            credit = half_even(Fraction(fee * s["days"] * pct, self.DAYS * 100))
            seg = s.get("segment")
            if seg == "enterprise" or (seg == "corporate" and a in self.AUTO):
                claim_id, filed, t = "AUTO", None, self.E - 3600
            elif sid in self.CLAIM:
                filed, claim_id = self.CLAIM[sid]
                t = filed
            else:
                claim_id, filed, t = None, None, None
            run = running.get(a, self.QTD.get(a, 0))
            cap = self.CAP.get(a)
            fx, usd = None, 0
            if pct == 0:
                status = "MET"
            elif claim_id is None:
                status = "UNCLAIMED"
            else:
                rate = self.rate(s["currency"], t)
                exp = self.EXP.get(s["currency"], 2)
                if rate is not None:
                    fx = fixed(rate, 6)
                    usd = half_even(Fraction(credit) * rate * 100 / (10 ** exp))
                if cap is None or run + usd <= cap:
                    status = "CREDITED"
                else:
                    status = "CAP_EXHAUSTED"
            rec = {
                "subscription_id": sid, "account_id": a, "product": s["product"], "region": s["region"],
                "region_group": self.RGROUP.get(s["region"]), "segment": seg, "plan": s.get("plan"),
                "sla_class": s["sla_class"], "sla_version": s.get("version"),
                "target_pct": fixed(s["target"], 3) if s.get("target") is not None else None,
                "currency": s["currency"], "fee_minor": fee, "active_days": s["days"],
            }
            rec.update(w)
            rec.update({
                "uptime_pct": fixed(uptime, 3), "credit_pct": pct, "credit_minor": credit,
                "claim_id": claim_id, "claim_filed_utc": iso(filed) if filed is not None else None,
                "fx_rate": fx, "credit_usd_cents": usd, "qtd_before_usd_cents": run,
                "cap_usd_cents": cap, "status": status,
            })
            if status == "CREDITED":
                run += usd
            running[a] = run
            self.records.append(rec)

    # ---------------- outputs
    STATUSES = ("CAP_EXHAUSTED", "CREDITED", "MET", "UNCLAIMED")
    GROUPS = ("central", "east", "north", "south", "west")
    SEGMENTS = ("consumer", "corporate", "enterprise", "smb")

    def _counts(self, recs):
        c = {k: 0 for k in self.STATUSES}
        for r in recs:
            c[r["status"]] += 1
        return c

    @staticmethod
    def _credited(recs):
        return sum(r["credit_usd_cents"] for r in recs if r["status"] == "CREDITED")

    def _dump(self, name, obj):
        (self.out / name).write_text(json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False) + "\n",
                                     encoding="utf-8")

    def write(self):
        self.out.mkdir(parents=True, exist_ok=True)
        recs = self.records
        with open(self.out / "normalized.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            for r in recs:
                fh.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
        by_ccy = {}
        for r in recs:
            if r["status"] == "CREDITED":
                by_ccy[r["currency"]] = by_ccy.get(r["currency"], 0) + r["credit_minor"]
        fails = sum(1 for x in self.sources if not x["control_ok"])
        self._dump("summary.json", {
            "status": "PUBLISHED", "period": self.PERIOD, "records": len(recs), "excluded": len(self.exclusions),
            "status_counts": self._counts(recs), "credited_usd_cents": self._credited(recs),
            "credit_minor_by_currency": by_ccy,
            "eligible_windows": sum(r["eligible_windows"] for r in recs),
            "bad_windows": sum(r["bad_windows"] for r in recs),
            "attributed_windows": sum(r["attributed_windows"] for r in recs),
            "reconciliation": {"files": len(self.sources), "records": self.record_total,
                               "control_blocks": self.control_total, "control_failures": fails},
        })
        self._dump("data_quality.json", {"sources": self.sources, "exclusions": self.exclusions})
        prods = {}
        for r in recs:
            prods.setdefault(r["product"], []).append(r)
        self._dump("product_summary.json", {"products": {p: {
            "records": len(v), "eligible_windows": sum(r["eligible_windows"] for r in v),
            "bad_windows": sum(r["bad_windows"] for r in v),
            "attributed_windows": sum(r["attributed_windows"] for r in v),
            "credited_usd_cents": self._credited(v), "status_counts": self._counts(v)} for p, v in prods.items()}})
        for g in self.GROUPS:
            v = [r for r in recs if r["region_group"] == g]
            regs = {}
            for r in v:
                regs.setdefault(r["region"], []).append(r)
            self._dump("region_%s.json" % g, {
                "region_group": g, "records": len(v), "status_counts": self._counts(v),
                "credited_usd_cents": self._credited(v),
                "regions": {k: {"records": len(x), "eligible_windows": sum(r["eligible_windows"] for r in x),
                                "bad_windows": sum(r["bad_windows"] for r in x),
                                "credited_usd_cents": self._credited(x)} for k, x in regs.items()}})
        for sg in self.SEGMENTS:
            v = [r for r in recs if r["segment"] == sg]
            plans = {}
            for r in v:
                plans.setdefault(r["plan"], []).append(r)
            self._dump("segment_%s.json" % sg, {
                "segment": sg, "records": len(v), "status_counts": self._counts(v),
                "credited_usd_cents": self._credited(v),
                "plans": {k: {"records": len(x), "credited_usd_cents": self._credited(x)} for k, x in plans.items()}})

    def write_held(self):
        self.out.mkdir(parents=True, exist_ok=True)
        (self.out / "normalized.jsonl").write_text("", encoding="utf-8")
        self._dump("summary.json", {"status": "HELD", "period": getattr(self, "PERIOD", None),
                                    "held_reasons": sorted(self.held)})
        self._dump("data_quality.json", {"sources": self.sources, "exclusions": []})
        for name in (["product_summary.json"] + ["region_%s.json" % g for g in self.GROUPS]
                     + ["segment_%s.json" % s for s in self.SEGMENTS]):
            self._dump(name, {"status": "HELD"})

    STEPS = ("params", "accounts", "subs", "plans", "enrollment", "sla_terms", "fees", "claims", "fx", "caps",
             "telemetry", "probes", "incidents", "maintenance", "suspensions", "assemble")

    def run(self):
        self.load()
        self.check()
        if self.held:
            # held_reasons names only files, so the cause is kept here instead.
            try:
                self.params()
            except Exception as exc:
                self.held_period_error = exc
            self.write_held()
            return "HELD"
        for step in self.STEPS:
            getattr(self, step)()
        self.write()
        return "PUBLISHED"


def main(argv):
    args, prior = [], None
    i = 0
    while i < len(argv):
        if argv[i] == "--prior":
            prior = argv[i + 1]
            i += 2
            continue
        args.append(argv[i])
        i += 1
    data = Path(args[0]) if len(args) > 0 else Path("/app/data")
    out = Path(args[1]) if len(args) > 1 else Path("/app/out")
    Close(data, out, prior).run()


if __name__ == "__main__":
    main(sys.argv[1:])
