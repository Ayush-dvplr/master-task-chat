#!/usr/bin/env python3
"""GROUNDLINK month end settlement.

Rebuilds the settlement of a satellite operator ground segment from the
working papers in the data directory and writes the thirty artifacts
into the output directory.

    python3 settle.py --data DIR --out DIR

Every figure is read from the papers of the month being settled.  The
standard library alone is used, no floating point is computed anywhere
and every division in the pipeline is a floor at the stage boundary the
precision contract names.
"""

import argparse
import collections
import csv
import hashlib
import json
import os
import re
import sqlite3
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib

CORE_ARTIFACTS = [
    "canonical_contact_ledger.csv",
    "admitted_contact_ledger.csv",
    "rejected_contact_ledger.psv",
    "normalized_contact_intervals.tsv",
    "antenna_capacity_ledger.csv",
    "capacity_cap_exceptions.psv",
    "contention_groups.jsonl",
    "winning_resource_assignments.csv",
    "displaced_contact_ledger.psv",
    "mission_entitlement_state.csv",
    "carry_forward_ledger.csv",
    "rationing_pass_trace.jsonl",
    "delivered_volume_ledger.csv",
    "deferred_volume_ledger.csv",
    "unused_capacity_ledger.tsv",
    "station_utilisation_ledger.csv",
    "antenna_utilisation_ledger.tsv",
    "mission_settlement_statements.csv",
    "station_settlement_statements.csv",
    "contract_compliance_ledger.csv",
    "credit_debit_ledger.csv",
    "outage_adjustment_ledger.psv",
    "exception_classification_report.jsonl",
    "tie_resolution_report.csv",
    "cross_source_discrepancy_report.psv",
    "invariant_check_report.json",
    "period_reconciliation_totals.json",
    "network_settlement_summary.xml",
    "per_mission_final_summary.md",
]

STAGE_COUNT = 14


# ---------------------------------------------------------------- intervals

def iv_normalise(ivs):
    """Sort, merge overlapping or abutting, drop zero length.  Half open."""
    out = []
    for s, e in sorted(ivs):
        if e <= s:
            continue
        if out and s <= out[-1][1]:
            if e > out[-1][1]:
                out[-1][1] = e
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def iv_subtract(ivs, b, c):
    if c <= b:
        return list(ivs)
    out = []
    for s, e in ivs:
        if c <= s or b >= e:
            out.append((s, e))
            continue
        if s < b:
            out.append((s, b))
        if c < e:
            out.append((c, e))
    return out


def iv_subtract_many(ivs, cuts):
    for b, c in cuts:
        ivs = iv_subtract(ivs, b, c)
    return ivs


def iv_intersect(ivs, a, b):
    out = []
    for s, e in ivs:
        lo = s if s > a else a
        hi = e if e < b else b
        if lo < hi:
            out.append((lo, hi))
    return out


def iv_len(ivs):
    return sum(e - s for s, e in ivs)


def iv_overlaps(ivs, other):
    """Total seconds of overlap between two disjoint sorted sets."""
    i = j = 0
    total = 0
    while i < len(ivs) and j < len(other):
        s = ivs[i][0] if ivs[i][0] > other[j][0] else other[j][0]
        e = ivs[i][1] if ivs[i][1] < other[j][1] else other[j][1]
        if s < e:
            total += e - s
        if ivs[i][1] < other[j][1]:
            i += 1
        else:
            j += 1
    return total


# ------------------------------------------------------------------- readers

def read_delim(path, delim):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=delim))


def read_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def read_ini(path):
    """Minimal ini reader: sections plus key = value pairs."""
    out = {}
    section = None
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith(";") or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip()
                out[section] = {}
                continue
            if "=" in line and section is not None:
                k, v = line.split("=", 1)
                out[section][k.strip()] = v.strip()
    return out


def pdf_text(path):
    """Extract the text strings of a pdf in document order."""
    data = open(path, "rb").read()
    chunks = []
    for m in re.finditer(rb"stream\r?\n", data):
        start = m.end()
        end = data.find(b"endstream", start)
        if end < 0:
            continue
        raw = data[start:end]
        head = data[max(0, m.start() - 400):m.start()]
        if b"FlateDecode" in head:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                pass
        chunks.append(raw)
    text = []
    for raw in chunks:
        i = 0
        while True:
            j = raw.find(b"(", i)
            if j < 0:
                break
            k = j + 1
            buf = []
            while k < len(raw):
                ch = raw[k]
                if ch == 0x5c:
                    nxt = raw[k + 1] if k + 1 < len(raw) else 0
                    if nxt == 0x6e or nxt == 0x72:
                        buf.append(0x0a)
                    elif nxt == 0x74:
                        buf.append(0x09)
                    elif nxt == 0x62:
                        buf.append(0x08)
                    elif nxt == 0x66:
                        buf.append(0x0c)
                    elif 0x30 <= nxt <= 0x37:
                        oct_digits = raw[k + 1:k + 4]
                        try:
                            buf.append(int(oct_digits, 8) & 0xff)
                        except ValueError:
                            buf.append(nxt)
                        k += 3
                    else:
                        buf.append(nxt)
                    k += 2
                    continue
                if ch == 0x29:
                    break
                buf.append(ch)
                k += 1
            text.append(bytes(buf).decode("latin-1"))
            i = k + 1
    return "\n".join(text)


def xlsx_sheets(path):
    """Parse a spreadsheetml package into {sheet_name: {row: {col: value}}}."""
    zf = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in zf.namelist():
        body = zf.read("xl/sharedStrings.xml").decode("utf-8")
        for m in re.finditer(r"<si>(.*?)</si>", body, re.S):
            txt = "".join(re.findall(r"<t[^>]*>(.*?)</t>", m.group(1), re.S))
            shared.append(txt)
    wb = zf.read("xl/workbook.xml").decode("utf-8")
    names = re.findall(r'<sheet[^>]*name="([^"]*)"', wb)
    rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
    targets = {}
    for m in re.finditer(r'<Relationship[^>]*Id="([^"]*)"[^>]*Target="([^"]*)"', rels):
        targets[m.group(1)] = m.group(2)
    rids = re.findall(r'<sheet[^>]*r:id="([^"]*)"', wb)
    sheets = {}
    for idx, name in enumerate(names):
        rid = rids[idx] if idx < len(rids) else None
        target = targets.get(rid, "worksheets/sheet%d.xml" % (idx + 1))
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        if target not in zf.namelist():
            target = "xl/worksheets/sheet%d.xml" % (idx + 1)
        body = zf.read(target).decode("utf-8")
        rows = {}
        for rm in re.finditer(r"<row[^>]*?>(.*?)</row>", body, re.S):
            row_xml = rm.group(1)
            cells = {}
            for cm in re.finditer(r'<c([^>]*)>(.*?)</c>', row_xml, re.S):
                attrs = cm.group(1)
                inner = cm.group(2)
                ref = re.search(r'r="([A-Z]+)\d+"', attrs)
                typ = re.search(r't="([^"]*)"', attrs)
                val = re.search(r"<v>(.*?)</v>", inner, re.S)
                if not ref or not val:
                    continue
                col = ref.group(1)
                v = val.group(1)
                if typ and typ.group(1) == "s":
                    v = shared[int(v)]
                cells[col] = v
            num = re.search(r'<row[^>]*?r="(\d+)"', rm.group(0))
            key = int(num.group(1)) if num else len(rows) + 1
            rows[key] = cells
        sheets[name] = rows
    return sheets


def sheet_row_values(cells):
    """Row as a list of values ordered by column letter."""
    if not cells:
        return []
    cols = sorted(cells.keys(), key=lambda c: (len(c), c))
    return [cells[c] for c in cols]


def parse_xlsx_blocks(path, selection):
    """Return (period_terms, credit_rates) from the binding sheet."""
    sheets = xlsx_sheets(path)
    binding_status = selection["binding_status"]
    status_cell = selection.get("status_header_cell", "sheet_status")
    revision_cell = selection.get("revision_header_cell", "sheet_revision")
    best = None
    for name, rows in sheets.items():
        status = None
        revision = None
        for key in sorted(rows):
            vals = sheet_row_values(rows[key])
            for i, v in enumerate(vals):
                if v == status_cell and i + 1 < len(vals):
                    status = vals[i + 1]
                if v == revision_cell and i + 1 < len(vals):
                    revision = vals[i + 1]
        if status != binding_status:
            continue
        try:
            rev = int(revision)
        except (TypeError, ValueError):
            rev = -1
        if best is None or rev > best[0]:
            best = (rev, name)
    if best is None:
        return [], {}
    rows = sheets[best[1]]
    markers = list(selection.get("block_markers", []))
    blocks = {}
    ordered_keys = sorted(rows)
    for key in ordered_keys:
        vals = sheet_row_values(rows[key])
        if vals and vals[0] in markers:
            blocks[vals[0]] = key
    period_terms = []
    credit_rates = {}
    for marker in markers:
        if marker not in blocks:
            continue
        start = blocks[marker]
        header = None
        for key in sorted(k for k in rows if k > start):
            vals = sheet_row_values(rows[key])
            if not vals:
                continue
            if vals[0] in markers:
                break
            if header is None:
                header = vals
                continue
            rec = {}
            for i, name in enumerate(header):
                if i < len(vals):
                    rec[name] = vals[i]
            if "rate_key" in header:
                credit_rates[rec.get("rate_key", "")] = rec.get("rate_value", "")
            else:
                period_terms.append(rec)
    return period_terms, credit_rates


def docx_text(path):
    """Flatten the paragraphs and table cells of a wordprocessingml body."""
    zf = zipfile.ZipFile(path)
    body = zf.read("word/document.xml").decode("utf-8")
    out = []
    for m in re.finditer(r"<w:t[^>]*>(.*?)</w:t>", body, re.S):
        out.append(re.sub(r"<[^>]*>", "", m.group(1)))
    return out


def directive_ranks(text):
    """The clause 1 precedence table: priority_class, rank_value, clause_ref."""
    tokens = text
    out = {}
    for i in range(len(tokens) - 2):
        name, value, ref = tokens[i], tokens[i + 1], tokens[i + 2]
        if (re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)
                and re.fullmatch(r"\d+", value)
                and re.fullmatch(r"\d+\.\d+", ref)):
            out.setdefault(name, int(value))
    return out


# ------------------------------------------------------------------ loading

def load(data_dir):
    d = {}
    j = lambda n: os.path.join(data_dir, n)

    d["missions"] = read_delim(j("mission_register.csv"), ",")
    d["crosswalk"] = read_delim(j("mission_alias_crosswalk.csv"), ",")
    d["ground"] = read_delim(j("ground_segment_register.tsv"), "\t")
    d["apertures"] = read_delim(j("aperture_register.csv"), ",")
    d["windows"] = read_delim(j("aperture_service_windows.csv"), ",")
    d["dockets"] = read_delim(j("maintenance_dockets.csv"), ",")
    d["blackouts"] = read_delim(j("blackout_advisories.psv"), "|")
    d["calendar"] = read_delim(j("station_accounting_calendar.csv"), ",")
    d["ini"] = read_ini(j("station_local_accounting.ini"))
    d["plan"] = read_delim(j("pass_plan_of_record.csv"), ",")
    d["cancellations"] = read_delim(j("cancellation_notices.csv"), ",")
    d["journal"] = read_jsonl(j("contact_event_journal.ndjson"))
    d["roster"] = read_delim(j("operator_roster.tsv"), "\t")
    d["overrides"] = read_jsonl(j("precedence_override_register.jsonl"))
    d["terms"] = read_delim(j("contract_terms_amendments.tsv"), "\t")
    d["rates"] = read_delim(j("rate_schedule_effective.psv"), "|")
    d["backlog"] = read_delim(j("onboard_backlog_reports.csv"), ",")
    d["claims"] = read_delim(j("outage_claims.psv"), "|")
    d["downlink"] = read_delim(j("downlink_reports.csv"), ",")
    d["legacy"] = read_delim(j("legacy_flat_rate_table.csv"), ",")
    d["prior"] = json.load(open(j("prior_period_settlement.json"), encoding="utf-8"))
    d["scaling"] = json.load(open(j("unit_scaling_rules.json"), encoding="utf-8"))
    d["selection"] = json.load(open(j("workbook_sheet_selection.json"), encoding="utf-8"))
    d["campaign"] = ET.parse(j("campaign_schedule.xml")).getroot()
    d["codes"] = ET.parse(j("exception_code_dictionary.xml")).getroot()

    ref = sqlite3.connect(j("reference_lookups.sqlite"))
    d["grade_authority"] = list(ref.execute("select authority_grade, commit_evidence from grade_authority"))
    d["priority_rank"] = list(ref.execute("select priority_class, rank_value from priority_rank"))
    d["station_scope"] = list(ref.execute("select contract_id, mission_id, station_id, scope_state from station_scope"))
    ref.close()

    aud = sqlite3.connect(j("settlement_audit_trace.db"))
    d["carry_state"] = list(aud.execute(
        "select contract_id, mission_id, period_id, bucket_class, valid_from_s, valid_to_s,"
        " carry_forward_enabled, trace_state from carry_state"))
    aud.close()

    d["memo_text"] = pdf_text(j("network_operations_memo.pdf"))
    d["directive_text"] = docx_text(j("precedence_directive.docx"))
    d["period_terms"], d["credit_rates"] = parse_xlsx_blocks(
        j("aperture_contract_workbook.xlsx"), d["selection"])
    return d


def memo_scalars(text):
    out = {}
    for m in re.finditer(r"commit-lead\s+([^\s:]+)\s*:\s*(\d+)\s*seconds", text):
        out.setdefault("commit_lead", {})[m.group(1)] = int(m.group(2))
    m = re.search(r"outage-qualifying-floor-seconds\s*:\s*(\d+)\s*seconds", text)
    if m:
        out["outage_floor"] = int(m.group(1))
    m = re.search(r"ration-pass-budget-base\s*:\s*(\d+)\s*passes", text)
    if m:
        out["ration_base"] = int(m.group(1))
    m = re.search(r"ration-pass-budget-ceiling\s*:\s*(\d+)\s*passes", text)
    if m:
        out["ration_ceiling"] = int(m.group(1))
    return out


# ----------------------------------------------------------------- S01..S14

def build(data_dir):
    d = load(data_dir)

    # ---------------------------------------------------------- S01 identity
    mission_class = {}
    missions = []
    for r in d["missions"]:
        if r.get("register_state") == "current":
            mission_class[r["mission_id"]] = r["priority_class"]
            missions.append(r["mission_id"])
    missions = sorted(set(missions))

    crosswalk = collections.defaultdict(list)
    for r in d["crosswalk"]:
        crosswalk[r["presentation_id"]].append(
            (int(r["valid_from_s"]), int(r["valid_to_s"]), r["mission_id"]))

    station_tz = {}
    stations = []
    for r in d["ground"]:
        if r.get("element_class") == "accounting_site":
            station_tz[r["station_id"]] = int(r["tz_offset_min"])
            stations.append(r["station_id"])
    stations = sorted(set(stations))

    aperture_station = {}
    aperture_label = {}
    label_to_aperture = {}
    apertures = []
    for r in d["apertures"]:
        if r.get("config_state") == "current":
            uid = r["antenna_uid"]
            aperture_station[uid] = r["station_id"]
            aperture_label[uid] = r["local_label"]
            label_to_aperture[(r["station_id"], r["local_label"])] = uid
            apertures.append(uid)
    apertures = sorted(set(apertures))

    contracts = {}
    for r in d["carry_state"]:
        cid = r[0]
        if cid not in contracts:
            contracts[cid] = {
                "contract_id": cid,
                "mission_id": r[1],
                "valid_from": int(r[4]),
                "valid_to": int(r[5]),
                "carry_forward": int(r[6]),
            }
    contracts_of_mission = collections.defaultdict(list)
    for cid in sorted(contracts):
        contracts_of_mission[contracts[cid]["mission_id"]].append(cid)

    scope = set()
    for cid, mid, sid, state in d["station_scope"]:
        if state == "in_scope" and contracts.get(cid, {}).get("mission_id") == mid:
            scope.add((cid, sid))

    settled = {}
    for r in d["terms"]:
        if r.get("amendment_status") != "executed":
            continue
        key = (r["contract_id"], r["period_id"])
        seq = int(r["revision_seq"])
        cur = settled.get(key)
        if cur is None or seq > cur[0]:
            settled[key] = (seq, r)
    terms = {k: v[1] for k, v in settled.items()}

    rank = {}
    for cls, val in d["priority_rank"]:
        try:
            rank[cls] = int(val)
        except (TypeError, ValueError):
            rank[cls] = 0
    for cls, val in directive_ranks(d["directive_text"]).items():
        rank.setdefault(cls, val)

    grade_evidence = {}
    for grade, ev in d["grade_authority"]:
        grade_evidence[grade] = str(ev).strip() in ("1", "true", "yes")

    operator_grade = {}
    for r in d["roster"]:
        operator_grade[r["operator_code"]] = r["authority_grade"]

    # -------------------------------------------------- S02 station calendar
    cal_rows = collections.defaultdict(list)
    for r in d["calendar"]:
        cal_rows[(r["station_id"], r["period_id"])].append(r)
    period_ids = sorted(set(r["period_id"] for r in d["calendar"]))
    period_open = {}
    for (st, p) in cal_rows:
        period_open.setdefault(p, []).append(min(int(x["local_open_s"]) for x in cal_rows[(st, p)]))
    period_order = sorted(period_ids, key=lambda p: (min(period_open[p]), p))
    period_index = {p: i for i, p in enumerate(period_order)}
    network_period_start = {}
    for p in period_order:
        network_period_start[p] = min(period_open[p])

    period_window = {}
    for (st, p) in cal_rows:
        rows = cal_rows[(st, p)]
        period_window[(st, p)] = (min(int(x["local_open_s"]) for x in rows),
                                  max(int(x["local_close_s"]) for x in rows))

    # ------------------------------------------------- S02 availability sets
    win_by_aperture = collections.defaultdict(list)
    for r in d["windows"]:
        if r.get("service_state") == "in_service":
            win_by_aperture[r["antenna_uid"]].append(
                (int(r["effective_from_s"]), int(r["effective_to_s"])))
    dockets = collections.defaultdict(list)
    for r in d["dockets"]:
        dockets[r["antenna_uid"]].append((int(r["start_s"]), int(r["end_s"])))
    blackouts = collections.defaultdict(list)
    for r in d["blackouts"]:
        blackouts[r["station_id"]].append((int(r["start_s"]), int(r["end_s"])))

    availability = {}
    for uid in apertures:
        ivs = iv_normalise(win_by_aperture.get(uid, []))
        ivs = iv_subtract_many(ivs, dockets.get(uid, []))
        ivs = iv_subtract_many(ivs, blackouts.get(aperture_station[uid], []))
        availability[uid] = ivs

    # ------------------------------------------------------- S05 rate tables
    rate_rows = collections.defaultdict(list)
    for r in d["rates"]:
        rate_rows[r["antenna_uid"]].append(
            (int(r["effective_from_s"]), int(r["effective_to_s"]), int(r["rate_mkib_per_s"])))
    for uid in rate_rows:
        rate_rows[uid].sort()
    rate_edges = {uid: sorted(set(x[0] for x in rate_rows[uid]) | set(x[1] for x in rate_rows[uid]))
                  for uid in rate_rows}

    def rate_at(uid, t):
        for a, b, r in rate_rows.get(uid, []):
            if a <= t < b:
                return r
        return 0

    # ------------------------------------------------- workbook parameters
    cap_by = {}
    budget_by = {}
    for rec in d["period_terms"]:
        key = (rec.get("antenna_uid"), rec.get("period_id"))
        try:
            cap_by[key] = int(rec.get("per_contact_cap_kib"))
        except (TypeError, ValueError):
            cap_by[key] = None
        try:
            budget_by[key] = int(rec.get("period_budget_kib"))
        except (TypeError, ValueError):
            budget_by[key] = 0
    cr = d["credit_rates"]
    credit_basis = int(d["scaling"]["credit_basis_kib_per_mib"])
    rate_scale = int(d["scaling"]["rate_scale_divisor"])
    theta_num = int(d["scaling"]["ration_damping_numerator"])
    theta_den = int(d["scaling"]["ration_damping_denominator"])
    outage_rate = int(cr.get("outage_credit_mcr_per_mib", 0))
    shortfall_rate = int(cr.get("shortfall_debit_mcr_per_mib", 0))
    unused_rate = int(cr.get("unused_reserved_credit_mcr_per_mib", 0))
    restore_num = int(cr.get("carry_restore_numerator", 0))
    restore_den = int(cr.get("carry_restore_denominator", 1))

    memo = memo_scalars(d["memo_text"])
    commit_lead = memo.get("commit_lead", {})
    outage_floor = memo.get("outage_floor", 0)
    ration_base = memo.get("ration_base", 0)
    ration_ceiling = memo.get("ration_ceiling", 0)

    # ----------------------------------------------------- S01 other lookups
    phases = collections.defaultdict(list)
    for el in d["campaign"]:
        phases[el.attrib["mission_id"]].append(
            (int(el.find("phase_from_s").text), int(el.find("phase_to_s").text),
             el.find("phase_class").text))

    notices = collections.defaultdict(list)
    for r in d["cancellations"]:
        notices[r["contact_id"]].append(r)

    journal = {}
    for r in d["journal"]:
        journal[r["contact_id"]] = r

    override_rows = collections.defaultdict(list)
    for r in d["overrides"]:
        override_rows[(r["mission_id"], r["antenna_uid"])].append(r)

    code_info = {}
    for el in d["codes"]:
        code_info[el.attrib["id"]] = {
            "reason": el.attrib.get("reason_slug", ""),
            "report_class": el.attrib.get("report_class", ""),
        }
    no_code = {"reason": "", "report_class": "admission"}

    backlog_by = {}
    for r in d["backlog"]:
        if r.get("report_state") != "current":
            continue
        key = (r["mission_id"], r["period_id"])
        seq = int(r["report_seq"])
        cur = backlog_by.get(key)
        if cur is None or seq > cur[0]:
            backlog_by[key] = (seq, int(r["backlog_kib"]))
    opening_backlog = {k: v[1] for k, v in backlog_by.items()}

    prior_carry = collections.defaultdict(int)
    for b in d["prior"].get("opening_buckets", []):
        if b.get("bucket_state") == "open":
            prior_carry[b["contract_id"]] += int(b["unsettled_kib"])

    claims = collections.defaultdict(list)
    for r in d["claims"]:
        claims[(r["mission_id"], r["period_id"])].append(r)

    downlink = collections.defaultdict(list)
    for r in d["downlink"]:
        downlink[r["contact_id"]].append(r)

    legacy_rows = collections.defaultdict(list)
    for r in d["legacy"]:
        legacy_rows[r["antenna_uid"]].append(r)

    # ------------------------------------------------------- S03 admission
    plan = sorted(d["plan"], key=lambda r: r["contact_id"])
    rejected = []
    admitted = []

    for p in plan:
        cid = p["contact_id"]
        start = int(p["scheduled_start_s"])
        end = int(p["scheduled_end_s"])
        station = p["station_id"]
        label = p["aperture_label"]
        pres = p["presentation_id"]
        boundary = start - commit_lead.get(station, 0)

        def fail(idx, code):
            rejected.append({
                "contact_id": cid, "station_id": station, "aperture_label": label,
                "presentation_id": pres, "scheduled_start_s": start,
                "scheduled_end_s": end, "predicate_index": idx,
                "reject_code": code, "reject_reason": code_info.get(code, no_code)["reason"],
                "_period": None,
            })

        # 1 alias resolution at the scheduled start
        mission = None
        for a, b, m in crosswalk.get(pres, []):
            if a <= start < b:
                mission = m
                break
        if mission is None:
            fail(1, "E01")
            continue

        # 2 aperture resolution against current configuration
        uid = label_to_aperture.get((station, label))
        if uid is None:
            fail(2, "E02")
            continue

        # 3 contract scope and validity
        pass_contracts = []
        for c in contracts_of_mission.get(mission, []):
            info = contracts[c]
            if info["valid_from"] <= start < info["valid_to"] and (c, station) in scope:
                pass_contracts.append(c)
        if not pass_contracts:
            fail(3, "E03")
            continue

        # 4 campaign phase
        standdown = False
        for a, b, cls in phases.get(mission, []):
            if a <= start < b:
                standdown = (cls == "standdown")
                break
        if standdown:
            fail(4, "E04")
            continue

        # 5 cancellation against the commit boundary
        eff = [n for n in notices.get(cid, []) if n.get("notice_state") == "effective"]
        binding_notice = None
        if eff:
            binding_notice = max(eff, key=lambda n: int(n["issued_seq"]))
        late_cancel = 0
        if binding_notice is not None and int(binding_notice["effective_s"]) < boundary:
            fail(5, "E05")
            continue
        if binding_notice is not None and int(binding_notice["effective_s"]) >= boundary:
            late_cancel = 1

        # 6 operational event
        ev = journal.get(cid)
        if ev is None:
            fail(6, "E06")
            continue

        # 7 admissible event class
        if ev.get("event_status") not in ("nominal", "partial"):
            fail(7, "E07")
            continue

        # 8 eligible interval
        avail = availability.get(uid, [])
        zero_length = (end == start)
        if zero_length:
            if not any(s <= start < e for s, e in avail):
                fail(8, "E08")
                continue
            elig = []
        else:
            base = [(start, end)]
            if ev.get("event_status") == "partial":
                base = iv_intersect(base, int(ev["actual_start_s"]),
                                    int(ev["actual_end_s"]))
            elig = []
            for s, e in iv_normalise(base):
                elig.extend(iv_intersect(avail, s, e))
            elig = iv_normalise(elig)
            if iv_len(elig) <= 0:
                fail(8, "E08")
                continue

        # -------------------------------------------------- S04 period split
        rows = []
        if zero_length:
            for p_ in period_order:
                w = period_window.get((station, p_))
                if w and w[0] <= start < w[1]:
                    rows.append((p_, [(start, start)]))
                    break
        else:
            for p_ in period_order:
                w = period_window.get((station, p_))
                if not w:
                    continue
                pieces = iv_intersect(elig, w[0], w[1])
                if pieces:
                    rows.append((p_, pieces))
        if not rows:
            continue

        # -------------------------------------------------- S06 precedence
        registered = mission_class.get(mission, "ordinary_priority")
        best_override = None
        for ov in override_rows.get((mission, uid), []):
            if int(ov["valid_from_s"]) <= start < int(ov["valid_to_s"]):
                if best_override is None:
                    best_override = ov
                else:
                    g = rank.get(ov["granted_class"], 99)
                    bg = rank.get(best_override["granted_class"], 99)
                    if g < bg or (g == bg and ov["override_id"] < best_override["override_id"]):
                        best_override = ov
        effective_class = registered
        if best_override is not None:
            g = rank.get(best_override["granted_class"], 99)
            r = rank.get(registered, 99)
            if g < r:
                effective_class = best_override["granted_class"]
        effective_rank = rank.get(effective_class, 99)

        protected = 0
        if int(ev.get("event_recorded_s", 0)) <= boundary:
            grade = operator_grade.get(ev.get("operator_code", ""), "")
            if grade_evidence.get(grade, False):
                protected = 1

        for p_, pieces in rows:
            admitted.append({
                "contact_id": cid, "period_id": p_, "station_id": station,
                "antenna_uid": uid, "mission_id": mission,
                "presentation_id": pres, "scheduled_start_s": start,
                "scheduled_end_s": end, "commit_boundary_s": boundary,
                "event_status": ev.get("event_status", ""),
                "operator_code": ev.get("operator_code", ""),
                "protected": protected, "late_cancel": late_cancel,
                "pieces": pieces, "eligible_seconds": iv_len(pieces),
                "effective_class": effective_class, "effective_rank": effective_rank,
                "pass_contracts": pass_contracts,
                "raw_capacity_kib": 0, "rate_piece_count": 0,
                "capacity_cap_kib": 0, "usable_capacity_kib": 0,
                "demand_kib": 0, "allocated_kib": 0, "accepted_kib": 0,
                "from_carry_kib": 0, "from_new_kib": 0,
                "deferred_kib": 0, "unused_capacity_kib": 0,
                "allocation_state": "won", "displaced_by": "",
                "contract_id": "", "remaining_obligation_kib": 0,
            })

    for r in rejected:
        st = r["station_id"]
        for p_ in period_order:
            w = period_window.get((st, p_))
            if w and w[0] <= r["scheduled_start_s"] < w[1]:
                r["_period"] = p_
                break

    # ------------------------------------------------------ S05 capacity
    cap_exceptions = []
    intervals_out = []
    for row in admitted:
        uid = row["antenna_uid"]
        cap = cap_by.get((uid, row["period_id"]))
        pieces = row["pieces"]
        rate_pieces = []
        for s, e in pieces:
            edges = [x for x in rate_edges.get(uid, []) if s < x < e]
            cuts = sorted(set(edges))
            prev = s
            for c in cuts:
                rate_pieces.append((prev, c))
                prev = c
            rate_pieces.append((prev, e))
        raw = 0
        for s, e in rate_pieces:
            seconds = e - s
            raw += (seconds * rate_at(uid, s)) // rate_scale
        row["rate_piece_count"] = len(rate_pieces)
        row["raw_capacity_kib"] = raw
        if cap is None:
            row["capacity_cap_kib"] = raw
            row["usable_capacity_kib"] = raw
        else:
            row["capacity_cap_kib"] = cap
            row["usable_capacity_kib"] = raw if raw < cap else cap
            if raw > cap:
                cap_exceptions.append({
                    "contact_id": row["contact_id"], "period_id": row["period_id"],
                    "antenna_uid": uid, "raw_capacity_kib": raw,
                    "capacity_cap_kib": cap, "clipped_kib": raw - cap,
                    "_period": row["period_id"],
                })
        for s, e in pieces:
            intervals_out.append({
                "contact_id": row["contact_id"], "period_id": row["period_id"],
                "antenna_uid": uid, "segment_start_s": s, "segment_end_s": e,
                "segment_seconds": e - s,
            })
        if not pieces:
            intervals_out.append({
                "contact_id": row["contact_id"], "period_id": row["period_id"],
                "antenna_uid": uid, "segment_start_s": row["scheduled_start_s"],
                "segment_end_s": row["scheduled_start_s"], "segment_seconds": 0,
            })

    # ------------------------------------------- S07 ordering and remaining
    for row in admitted:
        best = 0
        for c in row["pass_contracts"]:
            t = terms.get((c, row["period_id"]))
            if t is not None:
                v = int(t["obligation_kib"])
                if v > best:
                    best = v
        row["remaining_obligation_kib"] = best

    def order_key(row):
        return (0 if row["protected"] else 1, row["effective_rank"],
                row["commit_boundary_s"], -row["remaining_obligation_kib"],
                row["contact_id"])

    aperture_period_rows = collections.defaultdict(list)
    for row in admitted:
        aperture_period_rows[(row["antenna_uid"], row["period_id"])].append(row)

    contention_groups = []
    tie_rows = []
    displaced_rows = []
    won_rows = []
    aperture_order = {}

    for key in sorted(aperture_period_rows):
        rows = sorted(aperture_period_rows[key], key=order_key)
        aperture_order[key] = rows
        n = len(rows)
        # intersection graph
        inter = [[False] * n for _ in range(n)]
        for i in range(n):
            for jx in range(i + 1, n):
                if iv_overlaps(rows[i]["pieces"], rows[jx]["pieces"]) >= 1:
                    inter[i][jx] = inter[jx][i] = True
        # connected components
        seen = [False] * n
        comps = []
        for i in range(n):
            if seen[i]:
                continue
            stack = [i]
            comp = []
            seen[i] = True
            while stack:
                u = stack.pop()
                comp.append(u)
                for v in range(n):
                    if inter[u][v] and not seen[v]:
                        seen[v] = True
                        stack.append(v)
            comps.append(sorted(comp))
        comps.sort(key=lambda c: min(rows[i]["contact_id"] for i in c))
        for seq, comp in enumerate(comps, 1):
            contention_groups.append({
                "antenna_uid": key[0], "period_id": key[1], "group_seq": seq,
                "member_count": len(comp),
                "member_ids": ",".join(sorted(rows[i]["contact_id"] for i in comp)),
                "eligible_seconds_total": sum(rows[i]["eligible_seconds"] for i in comp),
                "_period": key[1],
            })
        # tie report
        for i in range(n):
            for jx in range(i + 1, n):
                if not inter[i][jx]:
                    continue
                a, b = rows[i], rows[jx]
                if a["protected"] != b["protected"]:
                    level = 1
                elif a["effective_rank"] != b["effective_rank"]:
                    level = 2
                elif a["commit_boundary_s"] != b["commit_boundary_s"]:
                    level = 3
                elif a["remaining_obligation_kib"] != b["remaining_obligation_kib"]:
                    level = 4
                else:
                    level = 5
                tie_rows.append({
                    "antenna_uid": key[0], "period_id": key[1],
                    "contact_id_kept": a["contact_id"],
                    "contact_id_yielded": b["contact_id"],
                    "decided_at_level": level,
                })
        # greedy walk over the whole aperture period
        accepted_idx = []
        for i, row in enumerate(rows):
            hit = None
            for jx in accepted_idx:
                if iv_overlaps(row["pieces"], rows[jx]["pieces"]) >= 1:
                    hit = jx
                    break
            if hit is None:
                accepted_idx.append(i)
                row["allocation_state"] = "won"
                won_rows.append(row)
            else:
                row["allocation_state"] = "displaced"
                row["displaced_by"] = rows[hit]["contact_id"]
                displaced_rows.append(row)

    # ------------------------------------------------------- S08..S10 by period
    entitlement = {}
    ration_trace = []
    won_rows = []
    backlog_running = {}
    allowance_state = {}
    carry_prev = dict(prior_carry)

    for p_ in period_order:
        # ---- S08 entitlement merge for this period
        for cid in sorted(contracts):
            key = (cid, p_)
            if key not in terms:
                continue
            if (cid, p_) in entitlement:
                continue
            src = carry_prev.get(cid, 0)
            t = terms[key]
            cap = int(t["carry_cap_kib"])
            enabled = (int(t["carry_forward_enabled"]) == 1
                       and contracts[cid]["carry_forward"] == 1)
            expired = 1 if contracts[cid]["valid_to"] <= network_period_start[p_] else 0
            if not enabled or expired:
                carry_in = 0
                forfeit = src
            else:
                carry_in = src if src < cap else cap
                forfeit = src - carry_in
            ent = int(t["entitlement_kib"])
            entitlement[key] = {
                "contract_id": cid, "period_id": p_, "carry_source_kib": src,
                "carry_cap_kib": cap, "carry_in_kib": carry_in,
                "carry_forfeit_kib": forfeit, "entitlement_kib": ent,
                "available_allowance_kib": carry_in + ent,
                "consumed_kib": 0, "unconsumed_kib": carry_in + ent,
                "contract_expired": expired,
                "carry_forward_enabled": 1 if enabled else 0,
                "obligation_kib": int(t["obligation_kib"]),
                "reserved_kib": int(t["reserved_kib"]),
                "_period": p_,
            }
            allowance_state[key] = [carry_in, ent]

        # ---- S09 deliverable volume for this period
        for key in sorted(k for k in aperture_order if k[1] == p_):
            rows = [r for r in aperture_order[key]
                    if r["allocation_state"] == "won"]
            if not rows:
                continue
            budget = budget_by.get(key, 0)
            for r in rows:
                bl = opening_backlog.get((r["mission_id"], p_), 0)
                r["demand_kib"] = (r["usable_capacity_kib"]
                                   if r["usable_capacity_kib"] < bl else bl)
            demands = [r["demand_kib"] for r in rows]
            total_demand = sum(demands)
            if total_demand <= budget:
                for r in rows:
                    r["allocated_kib"] = r["demand_kib"]
                continue
            n = len(rows)
            pass_budget = ration_base + n
            if pass_budget > ration_ceiling:
                pass_budget = ration_ceiling
            x = [0] * n
            pinned = [False] * n
            for pnum in range(1, pass_budget + 1):
                pinned_mass = sum(demands[i] for i in range(n) if pinned[i])
                active = [i for i in range(n) if not pinned[i]]
                if not active:
                    ration_trace.append({
                        "antenna_uid": key[0], "period_id": key[1],
                        "pass_seq": pnum, "active_count": 0, "share_kib": 0,
                        "allocated_kib": sum(x), "budget_kib": budget,
                        "demand_total_kib": total_demand,
                    })
                    continue
                room = budget - pinned_mass
                share = room // len(active) if room > 0 else 0
                for i in active:
                    target = demands[i] if demands[i] < share else share
                    step = target - x[i]
                    if step > 0:
                        delta = (step * theta_num) // theta_den
                        if delta < 1:
                            delta = 1
                        x[i] += delta
                for i in active:
                    if x[i] >= demands[i]:
                        x[i] = demands[i]
                        pinned[i] = True
                ration_trace.append({
                    "antenna_uid": key[0], "period_id": key[1],
                    "pass_seq": pnum, "active_count": len(active),
                    "share_kib": share, "allocated_kib": sum(x),
                    "budget_kib": budget, "demand_total_kib": total_demand,
                })
            residual = budget - sum(x)
            for i in range(n):
                if residual <= 0:
                    break
                take = demands[i] - x[i]
                if take > residual:
                    take = residual
                if take > 0:
                    x[i] += take
                    residual -= take
            for i, r in enumerate(rows):
                r["allocated_kib"] = x[i]

        # ---- S10 transmission accounting for this period
        for st in stations:
            for uid in apertures:
                if aperture_station.get(uid) != st:
                    continue
                if (uid, p_) not in aperture_order:
                    continue
                for r in aperture_order[(uid, p_)]:
                    if r["allocation_state"] != "won":
                        continue
                    bl_key = (r["mission_id"], p_)
                    if bl_key not in backlog_running:
                        backlog_running[bl_key] = opening_backlog.get(bl_key, 0)
                    bl = backlog_running[bl_key]
                    binding = None
                    best_ob = None
                    for c in r["pass_contracts"]:
                        t = terms.get((c, p_))
                        if t is None:
                            continue
                        ob = int(t["obligation_kib"])
                        if binding is None or ob > best_ob or (ob == best_ob and c < binding):
                            binding = c
                            best_ob = ob
                    if binding is None:
                        allow = 0
                        from_carry = 0
                        from_new = 0
                    else:
                        st_allow = allowance_state[(binding, p_)]
                        allow = st_allow[0] + st_allow[1]
                    acc = r["allocated_kib"]
                    if acc > bl:
                        acc = bl
                    if acc > allow:
                        acc = allow
                    if acc < 0:
                        acc = 0
                    if binding is not None:
                        st_allow = allowance_state[(binding, p_)]
                        from_carry = acc if acc < st_allow[0] else st_allow[0]
                        if from_carry < 0:
                            from_carry = 0
                        from_new = acc - from_carry
                        st_allow[0] -= from_carry
                        st_allow[1] -= from_new
                        ent = entitlement[(binding, p_)]
                        ent["consumed_kib"] += acc
                        ent["unconsumed_kib"] = (ent["available_allowance_kib"]
                                                - ent["consumed_kib"])
                    r["contract_id"] = binding or ""
                    r["accepted_kib"] = acc
                    r["from_carry_kib"] = from_carry
                    r["from_new_kib"] = from_new
                    r["deferred_kib"] = r["demand_kib"] - acc
                    r["unused_capacity_kib"] = r["usable_capacity_kib"] - acc
                    backlog_running[bl_key] = bl - acc
                    won_rows.append(r)

        # ---- close the period: carry out
        for cid in sorted(contracts):
            key = (cid, p_)
            e = entitlement.get(key)
            if e is None:
                continue
            e["unconsumed_kib"] = e["available_allowance_kib"] - e["consumed_kib"]
            carry_prev[cid] = e["unconsumed_kib"]

    # ---------------------------------------------------- S11 utilisation
    antenna_util = []
    antenna_util_by = {}
    for uid in apertures:
        for p_ in period_order:
            key = (uid, p_)
            w = period_window.get((aperture_station[uid], p_))
            avail = iv_len(iv_intersect(availability.get(uid, []), w[0], w[1])) if w else 0
            occ = sum(r["eligible_seconds"] for r in won_rows
                      if r["antenna_uid"] == uid and r["period_id"] == p_)
            bp = (occ * 10000) // avail if avail > 0 else 0
            rec = {"antenna_uid": uid, "period_id": p_, "occupied_seconds": occ,
                   "available_seconds": avail, "utilisation_bp": bp,
                   "denominator_state": "empty" if avail == 0 else "populated",
                   "_period": p_}
            antenna_util.append(rec)
            antenna_util_by[key] = rec
    station_util = []
    station_util_by = {}
    for st in stations:
        for p_ in period_order:
            occ = 0
            avail = 0
            for uid in apertures:
                if aperture_station.get(uid) != st:
                    continue
                rec = antenna_util_by[(uid, p_)]
                occ += rec["occupied_seconds"]
                avail += rec["available_seconds"]
            bp = (occ * 10000) // avail if avail > 0 else 0
            rec = {"station_id": st, "period_id": p_, "occupied_seconds": occ,
                   "available_seconds": avail, "utilisation_bp": bp,
                   "denominator_state": "empty" if avail == 0 else "populated",
                   "_period": p_}
            station_util.append(rec)
            station_util_by[(st, p_)] = rec

    # --------------------------------------------------------- S13 credits
    delivered = collections.defaultdict(int)
    for r in won_rows:
        if r["contract_id"]:
            delivered[(r["contract_id"], r["period_id"])] += r["accepted_kib"]

    credit_rows = []
    compliance_rows = []
    outage_rows = []
    credit_by_key = {}
    for key in sorted(entitlement, key=lambda k: (k[0], period_index[k[1]])):
        e = entitlement[key]
        cid, p_ = key
        ob = e["obligation_kib"]
        reserved = e["reserved_kib"]
        dlv = delivered.get(key, 0)
        shortfall = ob - dlv
        if shortfall < 0:
            shortfall = 0
        unused_reserved = reserved - dlv
        if unused_reserved < 0:
            unused_reserved = 0
        mission = contracts[cid]["mission_id"]
        acc_rows = [r for r in won_rows if r["contract_id"] == cid and r["period_id"] == p_]
        claim_list = [c for c in claims.get((mission, p_), []) if c.get("claim_status") == "accepted"]
        claim_overlap = []
        for c in claim_list:
            uid = c["antenna_uid"]
            secs = 0
            cf, ct = int(c["claim_from_s"]), int(c["claim_to_s"])
            for r in acc_rows:
                if r["antenna_uid"] != uid:
                    continue
                for s, e2 in r["pieces"]:
                    lo = s if s > cf else cf
                    hi = e2 if e2 < ct else ct
                    if lo < hi:
                        secs += hi - lo
            claim_overlap.append((c["claim_id"], c["antenna_uid"], secs))
        total_overlap = sum(x[2] for x in claim_overlap)
        qualified = 1 if total_overlap >= outage_floor else 0
        qualifying = [x for x in claim_overlap if x[2] >= 1]
        qualifying.sort(key=lambda x: x[0])
        pool = 0
        for claim_id, uid, _ in qualifying:
            for r in acc_rows:
                if r["antenna_uid"] == uid and r["late_cancel"] == 0:
                    pool += r["deferred_kib"]
        exempt = shortfall if shortfall < pool else pool
        if qualified:
            sdebit = 0
            ocredit = (exempt * outage_rate) // credit_basis
            restore = e["carry_forfeit_kib"]
            lim = (exempt * restore_num) // restore_den
            if restore > lim:
                restore = lim
        else:
            sdebit = (shortfall * shortfall_rate) // credit_basis
            ocredit = 0
            restore = 0
        ucredit = (unused_reserved * unused_rate) // credit_basis
        net = ucredit + ocredit - sdebit
        if shortfall == 0:
            state = "met"
        elif qualified:
            state = "exempt"
        else:
            state = "short"
        credit_rows.append({
            "contract_id": cid, "period_id": p_, "shortfall_kib": shortfall,
            "shortfall_debit_mcr": sdebit, "unused_reserved_kib": unused_reserved,
            "unused_credit_mcr": ucredit, "outage_credit_mcr": ocredit,
            "carry_restore_kib": restore, "net_mcr": net,
        })
        credit_by_key[key] = credit_rows[-1]
        compliance_rows.append({
            "contract_id": cid, "period_id": p_, "mission_id": mission,
            "obligation_kib": ob, "delivered_kib": dlv, "reserved_kib": reserved,
            "shortfall_kib": shortfall, "compliance_state": state,
        })
        outage_rows.append({
            "contract_id": cid, "period_id": p_, "mission_id": mission,
            "claim_overlap_seconds": total_overlap,
            "qualifying_floor_seconds": outage_floor,
            "outage_qualified": qualified, "exempt_kib": exempt,
            "carry_restore_kib": restore,
        })

    # --------------------------------------------------------- S12 statements
    mission_stmts = []
    for m in missions:
        for p_ in period_order:
            rs = [r for r in won_rows if r["mission_id"] == m and r["period_id"] == p_]
            net = 0
            for c in contracts_of_mission.get(m, []):
                cr = credit_by_key.get((c, p_))
                if cr:
                    net += cr["net_mcr"]
            mission_stmts.append({
                "mission_id": m, "period_id": p_, "won_pass_count": len(rs),
                "eligible_seconds": sum(r["eligible_seconds"] for r in rs),
                "usable_capacity_kib": sum(r["usable_capacity_kib"] for r in rs),
                "accepted_kib": sum(r["accepted_kib"] for r in rs),
                "deferred_kib": sum(r["deferred_kib"] for r in rs),
                "unused_capacity_kib": sum(r["unused_capacity_kib"] for r in rs),
                "net_mcr": net, "_period": p_,
            })
    station_stmts = []
    for st in stations:
        for p_ in period_order:
            rs = [r for r in won_rows if r["station_id"] == st and r["period_id"] == p_]
            station_stmts.append({
                "station_id": st, "period_id": p_, "won_pass_count": len(rs),
                "eligible_seconds": sum(r["eligible_seconds"] for r in rs),
                "accepted_kib": sum(r["accepted_kib"] for r in rs),
                "unused_capacity_kib": sum(r["unused_capacity_kib"] for r in rs),
                "utilisation_bp": station_util_by[(st, p_)]["utilisation_bp"],
                "_period": p_,
            })

    ctx = {
        "period_order": period_order,
        "period_index": period_index,
        "admitted": admitted,
        "won_rows": won_rows,
        "displaced_rows": displaced_rows,
        "rejected": rejected,
        "cap_exceptions": cap_exceptions,
        "intervals": intervals_out,
        "contention_groups": contention_groups,
        "tie_rows": tie_rows,
        "ration_trace": ration_trace,
        "entitlement": entitlement,
        "credit_rows": credit_rows,
        "compliance_rows": compliance_rows,
        "outage_rows": outage_rows,
        "mission_stmts": mission_stmts,
        "station_stmts": station_stmts,
        "antenna_util": antenna_util,
        "station_util": station_util,
        "missions": missions,
        "stations": stations,
        "apertures": apertures,
        "aperture_station": aperture_station,
        "contracts": contracts,
        "contracts_of_mission": contracts_of_mission,
        "budget_by": budget_by,
        "downlink": downlink,
        "legacy_rows": legacy_rows,
        "rate_rows": rate_rows,
        "code_info": code_info,
        "no_code": no_code,
        "opening_backlog": opening_backlog,
    }
    return ctx


# ---------------------------------------------------------------- artefacts

def row_of(row, columns):
    return [row[c] for c in columns]


def build_artifacts(ctx):
    out = {}
    admitted = ctx["admitted"]
    won = ctx["won_rows"]
    pidx = ctx["period_index"]

    def prow(r):
        return (r["contact_id"], pidx[r["period_id"]])

    adm_sorted = sorted(admitted, key=prow)

    out["canonical_contact_ledger.csv"] = ("csv", [
        "contact_id", "period_id", "station_id", "antenna_uid", "mission_id",
        "contract_id", "eligible_seconds", "raw_capacity_kib", "usable_capacity_kib",
        "effective_class", "protected", "late_cancel", "allocation_state",
        "demand_kib", "allocated_kib", "accepted_kib"],
        [[r["contact_id"], r["period_id"], r["station_id"], r["antenna_uid"],
          r["mission_id"], r["contract_id"], r["eligible_seconds"],
          r["raw_capacity_kib"], r["usable_capacity_kib"], r["effective_class"],
          r["protected"], r["late_cancel"], r["allocation_state"],
          r["demand_kib"], r["allocated_kib"], r["accepted_kib"]] for r in adm_sorted])

    out["admitted_contact_ledger.csv"] = ("csv", [
        "contact_id", "period_id", "station_id", "antenna_uid", "mission_id",
        "presentation_id", "scheduled_start_s", "scheduled_end_s",
        "commit_boundary_s", "event_status", "operator_code", "protected",
        "late_cancel", "eligible_seconds"],
        [[r["contact_id"], r["period_id"], r["station_id"], r["antenna_uid"],
          r["mission_id"], r["presentation_id"], r["scheduled_start_s"],
          r["scheduled_end_s"], r["commit_boundary_s"], r["event_status"],
          r["operator_code"], r["protected"], r["late_cancel"],
          r["eligible_seconds"]] for r in adm_sorted])

    rej = sorted(ctx["rejected"], key=lambda r: r["contact_id"])
    out["rejected_contact_ledger.psv"] = ("psv", [
        "contact_id", "station_id", "aperture_label", "presentation_id",
        "scheduled_start_s", "scheduled_end_s", "predicate_index",
        "reject_code", "reject_reason"],
        [[r["contact_id"], r["station_id"], r["aperture_label"],
          r["presentation_id"], r["scheduled_start_s"], r["scheduled_end_s"],
          r["predicate_index"], r["reject_code"], r["reject_reason"]] for r in rej])

    ivs = sorted(ctx["intervals"],
                 key=lambda r: (r["contact_id"], pidx[r["period_id"]], r["segment_start_s"]))
    out["normalized_contact_intervals.tsv"] = ("tsv", [
        "contact_id", "period_id", "antenna_uid", "segment_start_s",
        "segment_end_s", "segment_seconds"],
        [[r["contact_id"], r["period_id"], r["antenna_uid"], r["segment_start_s"],
          r["segment_end_s"], r["segment_seconds"]] for r in ivs])

    out["antenna_capacity_ledger.csv"] = ("csv", [
        "contact_id", "period_id", "antenna_uid", "eligible_seconds",
        "rate_piece_count", "raw_capacity_kib", "capacity_cap_kib",
        "usable_capacity_kib"],
        [[r["contact_id"], r["period_id"], r["antenna_uid"], r["eligible_seconds"],
          r["rate_piece_count"], r["raw_capacity_kib"], r["capacity_cap_kib"],
          r["usable_capacity_kib"]] for r in adm_sorted])

    caps = sorted(ctx["cap_exceptions"], key=lambda r: (r["contact_id"], pidx[r["period_id"]]))
    out["capacity_cap_exceptions.psv"] = ("psv", [
        "contact_id", "period_id", "antenna_uid", "raw_capacity_kib",
        "capacity_cap_kib", "clipped_kib"],
        [[r["contact_id"], r["period_id"], r["antenna_uid"], r["raw_capacity_kib"],
          r["capacity_cap_kib"], r["clipped_kib"]] for r in caps])

    groups = sorted(ctx["contention_groups"],
                    key=lambda r: (r["antenna_uid"], pidx[r["period_id"]], r["group_seq"]))
    out["contention_groups.jsonl"] = ("jsonl", None,
                                       [{"antenna_uid": g["antenna_uid"],
                                         "period_id": g["period_id"],
                                         "group_seq": g["group_seq"],
                                         "member_count": g["member_count"],
                                         "member_ids": g["member_ids"],
                                         "eligible_seconds_total": g["eligible_seconds_total"]}
                                        for g in groups])

    out["winning_resource_assignments.csv"] = ("csv", [
        "contact_id", "period_id", "antenna_uid", "mission_id", "effective_class",
        "effective_rank", "protected", "commit_boundary_s",
        "remaining_obligation_kib", "eligible_seconds", "usable_capacity_kib"],
        [[r["contact_id"], r["period_id"], r["antenna_uid"], r["mission_id"],
          r["effective_class"], r["effective_rank"], r["protected"],
          r["commit_boundary_s"], r["remaining_obligation_kib"],
          r["eligible_seconds"], r["usable_capacity_kib"]]
         for r in sorted(won, key=prow)])

    out["displaced_contact_ledger.psv"] = ("psv", [
        "contact_id", "period_id", "antenna_uid", "mission_id", "displaced_by",
        "displaced_seconds", "usable_capacity_kib"],
        [[r["contact_id"], r["period_id"], r["antenna_uid"], r["mission_id"],
          r["displaced_by"], r["eligible_seconds"], r["usable_capacity_kib"]]
         for r in sorted(ctx["displaced_rows"], key=prow)])

    ent = sorted(ctx["entitlement"].values(),
                 key=lambda r: (r["contract_id"], pidx[r["period_id"]]))
    out["mission_entitlement_state.csv"] = ("csv", [
        "contract_id", "period_id", "carry_source_kib", "carry_cap_kib",
        "carry_in_kib", "carry_forfeit_kib", "entitlement_kib",
        "available_allowance_kib", "consumed_kib", "unconsumed_kib",
        "contract_expired"],
        [[r["contract_id"], r["period_id"], r["carry_source_kib"], r["carry_cap_kib"],
          r["carry_in_kib"], r["carry_forfeit_kib"], r["entitlement_kib"],
          r["available_allowance_kib"], r["consumed_kib"], r["unconsumed_kib"],
          r["contract_expired"]] for r in ent])

    out["carry_forward_ledger.csv"] = ("csv", [
        "contract_id", "period_id", "carry_in_kib", "carry_forfeit_kib",
        "carry_out_kib", "carry_forward_enabled"],
        [[r["contract_id"], r["period_id"], r["carry_in_kib"], r["carry_forfeit_kib"],
          r["available_allowance_kib"] - r["consumed_kib"], r["carry_forward_enabled"]]
         for r in ent])

    trace = sorted(ctx["ration_trace"],
                   key=lambda r: (r["antenna_uid"], pidx[r["period_id"]], r["pass_seq"]))
    out["rationing_pass_trace.jsonl"] = ("jsonl", None, trace)

    out["delivered_volume_ledger.csv"] = ("csv", [
        "contact_id", "period_id", "mission_id", "contract_id", "antenna_uid",
        "demand_kib", "allocated_kib", "accepted_kib", "from_carry_kib",
        "from_new_kib"],
        [[r["contact_id"], r["period_id"], r["mission_id"], r["contract_id"],
          r["antenna_uid"], r["demand_kib"], r["allocated_kib"], r["accepted_kib"],
          r["from_carry_kib"], r["from_new_kib"]] for r in sorted(won, key=prow)])

    out["deferred_volume_ledger.csv"] = ("csv", [
        "contact_id", "period_id", "mission_id", "demand_kib", "accepted_kib",
        "deferred_kib", "late_cancel"],
        [[r["contact_id"], r["period_id"], r["mission_id"], r["demand_kib"],
          r["accepted_kib"], r["deferred_kib"], r["late_cancel"]]
         for r in sorted(won, key=prow)])

    out["unused_capacity_ledger.tsv"] = ("tsv", [
        "contact_id", "period_id", "antenna_uid", "usable_capacity_kib",
        "accepted_kib", "unused_capacity_kib"],
        [[r["contact_id"], r["period_id"], r["antenna_uid"], r["usable_capacity_kib"],
          r["accepted_kib"], r["unused_capacity_kib"]] for r in sorted(won, key=prow)])

    out["station_utilisation_ledger.csv"] = ("csv", [
        "station_id", "period_id", "occupied_seconds", "available_seconds",
        "utilisation_bp", "denominator_state"],
        [[r["station_id"], r["period_id"], r["occupied_seconds"],
          r["available_seconds"], r["utilisation_bp"], r["denominator_state"]]
         for r in ctx["station_util"]])

    out["antenna_utilisation_ledger.tsv"] = ("tsv", [
        "antenna_uid", "period_id", "occupied_seconds", "available_seconds",
        "utilisation_bp", "denominator_state"],
        [[r["antenna_uid"], r["period_id"], r["occupied_seconds"],
          r["available_seconds"], r["utilisation_bp"], r["denominator_state"]]
         for r in ctx["antenna_util"]])

    out["mission_settlement_statements.csv"] = ("csv", [
        "mission_id", "period_id", "won_pass_count", "eligible_seconds",
        "usable_capacity_kib", "accepted_kib", "deferred_kib",
        "unused_capacity_kib", "net_mcr"],
        [[r["mission_id"], r["period_id"], r["won_pass_count"], r["eligible_seconds"],
          r["usable_capacity_kib"], r["accepted_kib"], r["deferred_kib"],
          r["unused_capacity_kib"], r["net_mcr"]] for r in ctx["mission_stmts"]])

    out["station_settlement_statements.csv"] = ("csv", [
        "station_id", "period_id", "won_pass_count", "eligible_seconds",
        "accepted_kib", "unused_capacity_kib", "utilisation_bp"],
        [[r["station_id"], r["period_id"], r["won_pass_count"], r["eligible_seconds"],
          r["accepted_kib"], r["unused_capacity_kib"], r["utilisation_bp"]]
         for r in ctx["station_stmts"]])

    out["contract_compliance_ledger.csv"] = ("csv", [
        "contract_id", "period_id", "mission_id", "obligation_kib",
        "delivered_kib", "reserved_kib", "shortfall_kib", "compliance_state"],
        [[r["contract_id"], r["period_id"], r["mission_id"], r["obligation_kib"],
          r["delivered_kib"], r["reserved_kib"], r["shortfall_kib"],
          r["compliance_state"]] for r in ctx["compliance_rows"]])

    out["credit_debit_ledger.csv"] = ("csv", [
        "contract_id", "period_id", "shortfall_kib", "shortfall_debit_mcr",
        "unused_reserved_kib", "unused_credit_mcr", "outage_credit_mcr",
        "carry_restore_kib", "net_mcr"],
        [[r["contract_id"], r["period_id"], r["shortfall_kib"], r["shortfall_debit_mcr"],
          r["unused_reserved_kib"], r["unused_credit_mcr"], r["outage_credit_mcr"],
          r["carry_restore_kib"], r["net_mcr"]] for r in ctx["credit_rows"]])

    out["outage_adjustment_ledger.psv"] = ("psv", [
        "contract_id", "period_id", "mission_id", "claim_overlap_seconds",
        "qualifying_floor_seconds", "outage_qualified", "exempt_kib",
        "carry_restore_kib"],
        [[r["contract_id"], r["period_id"], r["mission_id"], r["claim_overlap_seconds"],
          r["qualifying_floor_seconds"], r["outage_qualified"], r["exempt_kib"],
          r["carry_restore_kib"]] for r in ctx["outage_rows"]])

    # exception report
    exc = []
    for r in rej:
        exc.append((ctx["code_info"].get(r["reject_code"], ctx["no_code"])["report_class"], r["contact_id"],
                    r["reject_code"], r["_period"] or "", r["predicate_index"]))
    for r in caps:
        exc.append(("capacity_cap", r["contact_id"], "X01", r["_period"], r["clipped_kib"]))
    for r in sorted(ctx["displaced_rows"], key=prow):
        exc.append(("displacement", r["contact_id"], "X02", r["period_id"], r["eligible_seconds"]))
    for r in ent:
        if r["carry_forfeit_kib"] > 0:
            exc.append(("carry_forfeit", r["contract_id"], "X03", r["period_id"],
                        r["carry_forfeit_kib"]))
    for r in ctx["antenna_util"]:
        if r["available_seconds"] == 0:
            exc.append(("empty_denominator", r["antenna_uid"], "X04", r["period_id"], 0))
    for r in adm_sorted:
        if r["late_cancel"] == 1:
            exc.append(("late_cancel", r["contact_id"], "X05", r["period_id"],
                        r["deferred_kib"]))
    exc.sort(key=lambda x: (x[0], x[1], x[2], pidx.get(x[3], -1)))
    out["exception_classification_report.jsonl"] = ("jsonl", None,
        [{"exception_class": c, "subject_id": s, "code": k, "detail_value": v}
         for c, s, k, _p, v in exc])

    ties = sorted(ctx["tie_rows"],
                  key=lambda r: (r["antenna_uid"], pidx[r["period_id"]],
                                 r["contact_id_kept"], r["contact_id_yielded"]))
    out["tie_resolution_report.csv"] = ("csv", [
        "antenna_uid", "period_id", "contact_id_kept", "contact_id_yielded",
        "decided_at_level"],
        [[r["antenna_uid"], r["period_id"], r["contact_id_kept"],
          r["contact_id_yielded"], r["decided_at_level"]] for r in ties])

    # discrepancy report
    disc = []
    acc_by_pass = collections.defaultdict(int)
    for r in won:
        acc_by_pass[r["contact_id"]] += r["accepted_kib"]
    for cid in sorted(acc_by_pass):
        reps = ctx["downlink"].get(cid, [])
        if not reps:
            continue
        rep = max(reps, key=lambda x: int(x["report_seq"]))
        left = acc_by_pass[cid]
        right = int(rep["reported_kib"])
        if left == right:
            continue
        cls = "over_report" if right > left else "under_report"
        disc.append(("canonical_ledger", "downlink_report", cid, "", left, right,
                     left - right, cls))
    for uid in sorted(ctx["apertures"]):
        rows = ctx["legacy_rows"].get(uid, [])
        if not rows:
            continue
        leg = max(rows, key=lambda x: int(x["table_rev"]))
        flat = int(leg["flat_rate_mkib_per_s"])
        rates = [x[2] for x in ctx["rate_rows"].get(uid, [])]
        if not rates:
            continue
        lo, hi = min(rates), max(rates)
        if lo <= flat <= hi:
            continue
        near = lo if abs(flat - lo) <= abs(flat - hi) else hi
        disc.append(("rate_schedule", "legacy_flat_table", uid, "", near, flat,
                     near - flat, "retired_rate_outside_band"))
    disc.sort(key=lambda r: (r[0], r[2]))
    out["cross_source_discrepancy_report.psv"] = ("psv", [
        "source_left", "source_right", "subject_id", "period_id", "left_value",
        "right_value", "delta_value", "discrepancy_class"],
        [[a, b, c, p_, l, r, dv, cl] for a, b, c, p_, l, r, dv, cl in disc])

    # invariants
    checks = []
    def add(name, left, right):
        checks.append({"check_name": name, "left_value": left, "right_value": right,
                       "balanced": 1 if left == right else 0})
    add("admitted_equals_won_plus_displaced", len(admitted),
        len(won) + len(ctx["displaced_rows"]))
    add("accepted_never_exceeds_allocated",
        sum(1 for r in won if r["accepted_kib"] > r["allocated_kib"]), 0)
    add("allocated_never_exceeds_demand",
        sum(1 for r in won if r["allocated_kib"] > r["demand_kib"]), 0)
    add("unused_matches_capacity_less_accepted",
        sum(r["unused_capacity_kib"] for r in won),
        sum(r["usable_capacity_kib"] - r["accepted_kib"] for r in won))
    add("carry_split_matches_accepted",
        sum(r["from_carry_kib"] + r["from_new_kib"] for r in won),
        sum(r["accepted_kib"] for r in won))
    overs = 0
    agg = collections.defaultdict(int)
    for r in won:
        agg[(r["antenna_uid"], r["period_id"])] += r["allocated_kib"]
    for key, total in agg.items():
        if total > ctx["budget_by"].get(key, 0):
            overs += 1
    add("allocation_within_aperture_budget", overs, 0)
    add("credit_rows_match_entitlement_rows", len(ctx["credit_rows"]), len(ent))
    traced = set()
    for t in ctx["ration_trace"]:
        traced.add((t["antenna_uid"], t["period_id"]))
    overs2 = 0
    for key in traced:
        tot = sum(r["demand_kib"] for r in won
                  if r["antenna_uid"] == key[0] and r["period_id"] == key[1])
        if tot <= ctx["budget_by"].get(key, 0):
            overs2 += 1
    add("ration_trace_groups_are_over_subscribed", overs2, 0)
    inv = {"check_count": len(checks), "checks": checks,
           "all_balanced": 1 if all(c["balanced"] == 1 for c in checks) else 0}
    out["invariant_check_report.json"] = ("json", None, inv)

    # period totals
    pt = {}
    for p_ in ctx["period_order"]:
        rs = [r for r in won if r["period_id"] == p_]
        ents = [e for e in ctx["entitlement"].values() if e["period_id"] == p_]
        crs = [c for c in ctx["credit_rows"] if c["period_id"] == p_]
        aus = [a for a in ctx["antenna_util"] if a["period_id"] == p_]
        pt[p_] = {
            "won_pass_count": len(rs),
            "eligible_seconds": sum(r["eligible_seconds"] for r in rs),
            "usable_capacity_kib": sum(r["usable_capacity_kib"] for r in rs),
            "accepted_kib": sum(r["accepted_kib"] for r in rs),
            "deferred_kib": sum(r["deferred_kib"] for r in rs),
            "unused_capacity_kib": sum(r["unused_capacity_kib"] for r in rs),
            "carry_in_kib": sum(e["carry_in_kib"] for e in ents),
            "carry_forfeit_kib": sum(e["carry_forfeit_kib"] for e in ents),
            "carry_out_kib": sum(e["available_allowance_kib"] - e["consumed_kib"] for e in ents),
            "shortfall_debit_mcr": sum(c["shortfall_debit_mcr"] for c in crs),
            "unused_credit_mcr": sum(c["unused_credit_mcr"] for c in crs),
            "outage_credit_mcr": sum(c["outage_credit_mcr"] for c in crs),
            "net_mcr": sum(c["net_mcr"] for c in crs),
            "occupied_seconds": sum(a["occupied_seconds"] for a in aus),
            "available_seconds": sum(a["available_seconds"] for a in aus),
        }
    network = {
        "net_mcr": sum(pt[p_]["net_mcr"] for p_ in ctx["period_order"]),
        "accepted_kib": sum(pt[p_]["accepted_kib"] for p_ in ctx["period_order"]),
        "won_pass_count": sum(pt[p_]["won_pass_count"] for p_ in ctx["period_order"]),
    }
    totals = dict(pt)
    totals["network"] = network
    out["period_reconciliation_totals.json"] = ("json", None, totals)

    # xml summary
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "<settlement>",
             "<missions>"]
    for r in ctx["mission_stmts"]:
        lines.append('<mission id="%s" period="%s"><accepted_kib>%d</accepted_kib>'
                     '<deferred_kib>%d</deferred_kib><net_mcr>%d</net_mcr></mission>'
                     % (r["mission_id"], r["period_id"], r["accepted_kib"],
                        r["deferred_kib"], r["net_mcr"]))
    lines.append("</missions>")
    lines.append("<stations>")
    for r in ctx["station_stmts"]:
        lines.append('<station id="%s" period="%s"><accepted_kib>%d</accepted_kib>'
                     '<utilisation_bp>%d</utilisation_bp></station>'
                     % (r["station_id"], r["period_id"], r["accepted_kib"],
                        r["utilisation_bp"]))
    lines.append("</stations>")
    lines.append("<network>")
    lines.append("<net_mcr>%d</net_mcr>" % network["net_mcr"])
    lines.append("<contract_period_count>%d</contract_period_count>" % len(ctx["credit_rows"]))
    lines.append("</network>")
    lines.append("</settlement>")
    out["network_settlement_summary.xml"] = ("xml", None, lines)

    # markdown
    agg_m = {}
    for r in ctx["mission_stmts"]:
        a = agg_m.setdefault(r["mission_id"], [r["mission_id"], 0, 0, 0, 0])
        a[1] += r["accepted_kib"]
        a[2] += r["deferred_kib"]
        a[3] += r["unused_capacity_kib"]
        a[4] += r["net_mcr"]
    md = ["# mission settlement summary", "",
          "| mission_id | accepted_kib | deferred_kib | unused_capacity_kib | net_mcr |",
          "| --- | --- | --- | --- | --- |"]
    for m in sorted(agg_m):
        a = agg_m[m]
        md.append("| %s | %d | %d | %d | %d |" % (a[0], a[1], a[2], a[3], a[4]))
    md.append("")
    md.append("network net_mcr %d" % network["net_mcr"])
    out["per_mission_final_summary.md"] = ("md", None, md)
    return out


def render(kind, header, rows):
    if kind in ("csv", "tsv", "psv"):
        sep = {"csv": ",", "tsv": "\t", "psv": "|"}[kind]
        lines = [sep.join(header)]
        for r in rows:
            lines.append(sep.join("" if v is None else str(v) for v in r))
        return ("\n".join(lines) + "\n").encode("ascii")
    if kind == "jsonl":
        buf = []
        for r in rows:
            buf.append(json.dumps(r, sort_keys=True, separators=(",", ":"),
                                  ensure_ascii=True))
        return ("".join(x + "\n" for x in buf)).encode("ascii")
    if kind == "json":
        return (json.dumps(rows, indent=2, sort_keys=True, ensure_ascii=True)
                + "\n").encode("ascii")
    if kind == "xml":
        return ("\n".join(rows) + "\n").encode("ascii")
    if kind == "md":
        return ("\n".join(rows) + "\n").encode("ascii")
    raise ValueError(kind)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    ctx = build(os.path.abspath(args.data))
    artifacts = build_artifacts(ctx)

    outdir = os.path.abspath(args.out)
    os.makedirs(outdir, exist_ok=True)

    blob = b""
    per = {}
    for name in CORE_ARTIFACTS:
        kind, header, rows = artifacts[name]
        data = render(kind, header, rows)
        with open(os.path.join(outdir, name), "wb") as fh:
            fh.write(data)
        blob += data
        per[name] = hashlib.sha256(data).hexdigest()

    manifest = {
        "artifact_count": len(CORE_ARTIFACTS),
        "core_digest": hashlib.sha256(blob).hexdigest(),
        "per_artifact_sha256": {k: per[k] for k in CORE_ARTIFACTS},
        "stage_count": STAGE_COUNT,
    }
    with open(os.path.join(outdir, "stage_digest_manifest.json"), "wb") as fh:
        fh.write((json.dumps(manifest, indent=2, sort_keys=True,
                             ensure_ascii=True) + "\n").encode("ascii"))
    return 0


if __name__ == "__main__":
    sys.exit(main())

