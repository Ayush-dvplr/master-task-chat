#!/usr/bin/env python3
"""GROUNDLINK month end settlement.

Rebuilds the thirty settlement artifacts from a directory of working
papers.  Every operating constant is read from the papers on each run.

    python3 settle.py --data DIR --out DIR
"""

import argparse
import csv
import hashlib
import io
import json
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
import zipfile
import zlib

# ---------------------------------------------------------------- intervals

def normalise(ivs):
    out = []
    for a, b in sorted(i for i in ivs if i[1] > i[0]):
        if out and a <= out[-1][1]:
            if b > out[-1][1]:
                out[-1][1] = b
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def subtract(base, cuts):
    cur = list(base)
    for ca, cb in cuts:
        if cb <= ca:
            continue
        nxt = []
        for a, b in cur:
            if cb <= a or ca >= b:
                nxt.append((a, b))
                continue
            if a < ca:
                nxt.append((a, ca))
            if cb < b:
                nxt.append((cb, b))
        cur = nxt
    return cur


def intersect(xs, ys):
    out = []
    i = j = 0
    while i < len(xs) and j < len(ys):
        a = max(xs[i][0], ys[j][0])
        b = min(xs[i][1], ys[j][1])
        if b > a:
            out.append((a, b))
        if xs[i][1] < ys[j][1]:
            i += 1
        else:
            j += 1
    return out


def total(ivs):
    return sum(b - a for a, b in ivs)


def overlap_len(xs, ys):
    return total(intersect(xs, ys))


# ------------------------------------------------------------------ readers

def read_delim(path, sep):
    with open(path, "r", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh, delimiter=sep))


def read_jsonl(path):
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def read_ini(path):
    sections = {}
    cur = None
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith(";") or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                cur = line[1:-1]
                sections[cur] = {}
            elif "=" in line and cur is not None:
                k, v = line.split("=", 1)
                sections[cur][k.strip()] = v.strip()
    return sections


def pdf_text(path):
    raw = open(path, "rb").read()
    chunks = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.S):
        body = m.group(1)
        try:
            body = zlib.decompress(body)
        except zlib.error:
            pass
        chunks.append(body)
    if not chunks:
        chunks = [raw]
    text = []
    for body in chunks:
        for t in re.finditer(rb"\((.*?)\)\s*Tj", body, re.S):
            text.append(t.group(1).decode("latin-1"))
    return "\n".join(text)


def docx_text(path):
    with zipfile.ZipFile(path) as z:
        doc = z.read("word/document.xml").decode("utf-8")
    doc = re.sub(r"</w:p>", "\n", doc)
    doc = re.sub(r"<[^>]+>", "", doc)
    return doc


XLNS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RELNS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
RNS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def read_xlsx(path):
    """Return {sheet_name: [ {col_letter: value}, ... ]} in sheet order."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.findall(XLNS + "si"):
                shared.append("".join(t.text or "" for t in si.iter(XLNS + "t")))
        rels = {}
        rroot = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        for rel in rroot.findall(RELNS + "Relationship"):
            tgt = rel.get("Target")
            if not tgt.startswith("/"):
                tgt = "xl/" + tgt.lstrip("./")
            rels[rel.get("Id")] = tgt
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        sheets = {}
        for sh in wb.find(XLNS + "sheets").findall(XLNS + "sheet"):
            target = rels[sh.get(RNS + "id")]
            sroot = ET.fromstring(z.read(target))
            rows = []
            for row in sroot.iter(XLNS + "row"):
                cells = {}
                for c in row.findall(XLNS + "c"):
                    ref = c.get("r")
                    col = "".join(ch for ch in ref if ch.isalpha())
                    v = c.find(XLNS + "v")
                    val = v.text if v is not None else ""
                    if c.get("t") == "s" and val != "":
                        val = shared[int(val)]
                    elif c.get("t") == "inlineStr":
                        node = c.find(XLNS + "is")
                        val = "".join(t.text or "" for t in node.iter(XLNS + "t")) if node is not None else ""
                    cells[col] = val
                rows.append(cells)
            sheets[sh.get("name")] = rows
    return sheets


# ------------------------------------------------------------------ writers

def ser_delim(header, rows, sep):
    buf = io.StringIO()
    buf.write(sep.join(header))
    buf.write("\n")
    for r in rows:
        buf.write(sep.join("" if v is None else str(v) for v in r))
        buf.write("\n")
    return buf.getvalue().encode("utf-8")


def ser_jsonl(objs):
    buf = io.StringIO()
    for o in objs:
        buf.write(json.dumps(o, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
        buf.write("\n")
    return buf.getvalue().encode("utf-8")


def ser_json(obj):
    return (json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode("utf-8")


# ------------------------------------------------------------------ pipeline

def run(data_dir, out_dir):
    D = lambda n: os.path.join(data_dir, n)

    # ---------------- scalars from the harder papers ----------------------
    memo = pdf_text(D("network_operations_memo.pdf"))
    commit_lead = {}
    for m in re.finditer(r"commit-lead\s+(\S+):\s*(-?\d+)\s*seconds", memo):
        commit_lead[m.group(1)] = int(m.group(2))
    outage_floor = int(re.search(r"outage-qualifying-floor-seconds:\s*(-?\d+)", memo).group(1))
    ration_base = int(re.search(r"ration-pass-budget-base:\s*(-?\d+)", memo).group(1))
    ration_ceiling = int(re.search(r"ration-pass-budget-ceiling:\s*(-?\d+)", memo).group(1))

    units = read_json(D("unit_scaling_rules.json"))
    rate_div = int(units["rate_scale_divisor"])
    credit_basis = int(units["credit_basis_kib_per_mib"])
    theta_num = int(units["ration_damping_numerator"])
    theta_den = int(units["ration_damping_denominator"])

    sel = read_json(D("workbook_sheet_selection.json"))
    sheets = read_xlsx(D("aperture_contract_workbook.xlsx"))
    rev_cell = sel["revision_header_cell"]
    sta_cell = sel["status_header_cell"]
    markers = list(sel["block_markers"])
    binding_status = sel["binding_status"]

    def sheet_meta(rows):
        meta = {}
        for cells in rows:
            a = cells.get("A", "")
            if a in (rev_cell, sta_cell):
                meta[a] = cells.get("B", "")
        return meta

    candidates = []
    for name, rows in sheets.items():
        meta = sheet_meta(rows)
        if meta.get(sta_cell) == binding_status:
            candidates.append((int(meta.get(rev_cell, "0")), name))
    candidates.sort()
    binding_sheet_name = candidates[-1][1]
    binding_rows = sheets[binding_sheet_name]

    def block(rows, marker):
        out = []
        i = 0
        while i < len(rows) and rows[i].get("A", "") != marker:
            i += 1
        i += 1
        if i >= len(rows):
            return out
        header = [rows[i].get(c, "") for c in sorted(rows[i].keys())]
        cols = sorted(rows[i].keys())
        i += 1
        while i < len(rows):
            a = rows[i].get("A", "")
            if a == "" or a.startswith("#"):
                break
            out.append({header[k]: rows[i].get(cols[k], "") for k in range(len(cols))})
            i += 1
        return out

    cap_rows = block(binding_rows, markers[0])
    rate_rows_wb = block(binding_rows, markers[1])
    per_contact_cap = {}
    period_budget = {}
    for r in cap_rows:
        key = (r["antenna_uid"], r["period_id"])
        per_contact_cap[key] = int(r["per_contact_cap_kib"])
        period_budget[key] = int(r["period_budget_kib"])
    credit_rates = {r["rate_key"]: int(r["rate_value"]) for r in rate_rows_wb}
    outage_rate = credit_rates["outage_credit_mcr_per_mib"]
    shortfall_rate = credit_rates["shortfall_debit_mcr_per_mib"]
    unused_rate = credit_rates["unused_reserved_credit_mcr_per_mib"]
    restore_num = credit_rates["carry_restore_numerator"]
    restore_den = credit_rates["carry_restore_denominator"]

    directive = docx_text(D("precedence_directive.docx"))
    directive_rank = {}
    dlines = [l.strip() for l in directive.split("\n")]
    for i in range(len(dlines) - 2):
        if re.fullmatch(r"\d+", dlines[i + 1]) and re.fullmatch(r"\d+\.\d+", dlines[i + 2]) \
                and re.fullmatch(r"[a-z_]+", dlines[i]) and dlines[i] not in ("priority_class", "rank_value", "clause_ref"):
            directive_rank.setdefault(dlines[i], int(dlines[i + 1]))

    # ---------------- S01 identity resolution -----------------------------
    mission_rows = read_delim(D("mission_register.csv"), ",")
    missions = {}
    for r in mission_rows:
        if r["register_state"] == "current":
            missions[r["mission_id"]] = r
    mission_ids = sorted(missions)

    crosswalk = {}
    for r in read_delim(D("mission_alias_crosswalk.csv"), ","):
        crosswalk.setdefault(r["presentation_id"], []).append(
            (int(r["valid_from_s"]), int(r["valid_to_s"]), r["mission_id"]))
    for v in crosswalk.values():
        v.sort()

    def resolve_mission(pid, t):
        for a, b, mid in crosswalk.get(pid, ()):
            if a <= t < b:
                return mid
        return None

    gsr = read_delim(D("ground_segment_register.tsv"), "\t")
    station_tz = {}
    for r in gsr:
        if r["element_class"] == "accounting_site":
            station_tz[r["station_id"]] = int(r["tz_offset_min"])
    station_ids = sorted(station_tz)

    ap_rows = read_delim(D("aperture_register.csv"), ",")
    apertures = {}
    for r in ap_rows:
        if r["config_state"] == "current":
            apertures[r["antenna_uid"]] = r
    antenna_ids = sorted(apertures)
    label_to_uid = {}
    ap_station = {}
    for uid, r in apertures.items():
        label_to_uid[(r["station_id"], r["local_label"])] = uid
        ap_station[uid] = r["station_id"]
    station_apertures = {s: [] for s in station_ids}
    for uid in antenna_ids:
        station_apertures.setdefault(ap_station[uid], []).append(uid)

    ref = sqlite3.connect(D("reference_lookups.sqlite"))
    rank_of = {}
    for cls, rv in ref.execute("select priority_class, rank_value from priority_rank"):
        rank_of[cls] = int(rv)
    for cls, rv in directive_rank.items():
        rank_of.setdefault(cls, rv)
    grade_commit = {}
    for g, ce in ref.execute("select authority_grade, commit_evidence from grade_authority"):
        grade_commit[g] = str(ce).strip() in ("1", "yes", "true")
    scope = {}
    for cid, mid, sid, st in ref.execute(
            "select contract_id, mission_id, station_id, scope_state from station_scope"):
        if st == "in_scope":
            scope.setdefault(cid, set()).add(sid)
    ref.close()

    aud = sqlite3.connect(D("settlement_audit_trace.db"))
    contracts = {}
    for cid, mid, vf, vt, cfe in aud.execute(
            "select contract_id, mission_id, valid_from_s, valid_to_s, carry_forward_enabled from carry_state"):
        contracts[cid] = {
            "contract_id": cid, "mission_id": mid,
            "valid_from_s": int(vf), "valid_to_s": int(vt),
            "carry_forward_enabled": str(cfe).strip() in ("1", "yes", "true"),
        }
    aud.close()
    contract_ids = sorted(contracts)
    mission_contracts = {}
    for cid in contract_ids:
        mission_contracts.setdefault(contracts[cid]["mission_id"], []).append(cid)

    terms = {}
    for r in read_delim(D("contract_terms_amendments.tsv"), "\t"):
        if r["amendment_status"] != "executed":
            continue
        key = (r["contract_id"], r["period_id"])
        seq = int(r["revision_seq"])
        if key not in terms or seq > terms[key]["revision_seq"]:
            terms[key] = {
                "revision_seq": seq,
                "obligation_kib": int(r["obligation_kib"]),
                "entitlement_kib": int(r["entitlement_kib"]),
                "reserved_kib": int(r["reserved_kib"]),
                "carry_cap_kib": int(r["carry_cap_kib"]),
                "carry_forward_enabled": str(r["carry_forward_enabled"]).strip() in ("1", "yes", "true"),
            }

    # ---------------- S02 availability ------------------------------------
    site_cfg = read_ini(D("station_local_accounting.ini"))

    cal = read_delim(D("station_accounting_calendar.csv"), ",")
    PERIOD_ORDER = sorted({r["period_id"] for r in cal})
    declared = {int(v["period_count"]) for v in site_cfg.values() if "period_count" in v}
    if len(declared) == 1 and declared != {len(PERIOD_ORDER)}:
        raise SystemExit("calendar periods disagree with station_local_accounting.ini")
    period_index = {p: i for i, p in enumerate(PERIOD_ORDER)}
    pidx = period_index.__getitem__

    period_window = {}
    for r in cal:
        key = (r["station_id"], r["period_id"])
        o, c = int(r["local_open_s"]), int(r["local_close_s"])
        if key not in period_window:
            period_window[key] = [o, c]
        else:
            w = period_window[key]
            w[0] = min(w[0], o)
            w[1] = max(w[1], c)
    period_window = {k: (v[0], v[1]) for k, v in period_window.items()}
    network_period_open = {}
    for p in PERIOD_ORDER:
        opens = [period_window[(s, p)][0] for s in station_ids if (s, p) in period_window]
        network_period_open[p] = min(opens) if opens else 0

    svc = {}
    for r in read_delim(D("aperture_service_windows.csv"), ","):
        if r["service_state"] == "in_service":
            svc.setdefault(r["antenna_uid"], []).append(
                (int(r["effective_from_s"]), int(r["effective_to_s"])))
    dockets = {}
    for r in read_delim(D("maintenance_dockets.csv"), ","):
        dockets.setdefault(r["antenna_uid"], []).append((int(r["start_s"]), int(r["end_s"])))
    blackouts = {}
    for r in read_delim(D("blackout_advisories.psv"), "|"):
        blackouts.setdefault(r["station_id"], []).append((int(r["start_s"]), int(r["end_s"])))

    availability = {}
    for uid in antenna_ids:
        base = normalise(svc.get(uid, []))
        base = subtract(base, dockets.get(uid, []))
        base = subtract(base, blackouts.get(ap_station[uid], []))
        availability[uid] = normalise(base)

    # ---------------- rates ------------------------------------------------
    rate_sched = {}
    for r in read_delim(D("rate_schedule_effective.psv"), "|"):
        rate_sched.setdefault(r["antenna_uid"], []).append(
            (int(r["effective_from_s"]), int(r["effective_to_s"]), int(r["rate_mkib_per_s"])))
    for v in rate_sched.values():
        v.sort()
    rate_edges = {uid: sorted({e for a, b, _ in v for e in (a, b)})
                  for uid, v in rate_sched.items()}

    def rate_at(uid, t):
        for a, b, rt in rate_sched.get(uid, ()):
            if a <= t < b:
                return rt
        return 0

    # ---------------- campaign, cancellations, journal ---------------------
    phases = {}
    croot = ET.parse(D("campaign_schedule.xml")).getroot()
    for ph in croot.iter("phase"):
        phases.setdefault(ph.get("mission_id"), []).append(
            (int(ph.findtext("phase_from_s")), int(ph.findtext("phase_to_s")), ph.findtext("phase_class")))
    for v in phases.values():
        v.sort()

    notices = {}
    for r in read_delim(D("cancellation_notices.csv"), ","):
        notices.setdefault(r["contact_id"], []).append(r)
    binding_notice = {}
    for cid, rows in notices.items():
        eff = [r for r in rows if r["notice_state"] == "effective"]
        if eff:
            binding_notice[cid] = max(eff, key=lambda r: int(r["issued_seq"]))

    journal = {}
    for ev in read_jsonl(D("contact_event_journal.ndjson")):
        journal[ev["contact_id"]] = ev

    roster = {}
    for r in read_delim(D("operator_roster.tsv"), "\t"):
        roster[r["operator_code"]] = r["authority_grade"]

    overrides = read_jsonl(D("precedence_override_register.jsonl"))

    backlog = {}
    for r in read_delim(D("onboard_backlog_reports.csv"), ","):
        if r["report_state"] != "current":
            continue
        key = (r["mission_id"], r["period_id"])
        seq = int(r["report_seq"])
        if key not in backlog or seq > backlog[key][0]:
            backlog[key] = (seq, int(r["backlog_kib"]))
    opening_backlog = {k: v[1] for k, v in backlog.items()}

    codes = {}
    xroot = ET.parse(D("exception_code_dictionary.xml")).getroot()
    for c in xroot.iter("code"):
        codes[c.get("id")] = {"reason_slug": c.get("reason_slug"),
                              "report_class": c.get("report_class")}

    # ---------------- S03 admission ----------------------------------------
    plan = read_delim(D("pass_plan_of_record.csv"), ",")
    plan.sort(key=lambda r: r["contact_id"])

    admitted = []
    rejected = []

    for r in plan:
        cid = r["contact_id"]
        sid = r["station_id"]
        label = r["aperture_label"]
        pres = r["presentation_id"]
        ss = int(r["scheduled_start_s"])
        se = int(r["scheduled_end_s"])
        lead = commit_lead.get(sid, 0)
        cb = ss - lead

        def reject(idx, code):
            rejected.append({
                "contact_id": cid, "station_id": sid, "aperture_label": label,
                "presentation_id": pres, "scheduled_start_s": ss, "scheduled_end_s": se,
                "predicate_index": idx, "reject_code": code,
                "reject_reason": codes[code]["reason_slug"],
            })

        mid = resolve_mission(pres, ss)
        if mid is None:
            reject(1, "E01")
            continue
        uid = label_to_uid.get((sid, label))
        if uid is None:
            reject(2, "E02")
            continue
        pass_contracts = []
        for cc in mission_contracts.get(mid, ()):
            c = contracts[cc]
            if c["valid_from_s"] <= ss < c["valid_to_s"] and sid in scope.get(cc, ()):
                pass_contracts.append(cc)
        if not pass_contracts:
            reject(3, "E03")
            continue
        phase_class = None
        for a, b, pc in phases.get(mid, ()):
            if a <= ss < b:
                phase_class = pc
                break
        if phase_class == "standdown":
            reject(4, "E04")
            continue
        late_cancel = 0
        bn = binding_notice.get(cid)
        if bn is not None:
            eff = int(bn["effective_s"])
            if eff < cb:
                reject(5, "E05")
                continue
            late_cancel = 1
        ev = journal.get(cid)
        if ev is None:
            reject(6, "E06")
            continue
        if ev["event_status"] not in ("nominal", "partial"):
            reject(7, "E07")
            continue

        base = [(ss, se)] if se > ss else []
        if ev["event_status"] == "partial":
            base = intersect(base, [(int(ev["actual_start_s"]), int(ev["actual_end_s"]))])
        avail = availability[uid]
        eligible = intersect(base, avail)
        zero_len = (se == ss)
        if zero_len:
            inside = any(a <= ss < b for a, b in avail)
            if not inside:
                reject(8, "E08")
                continue
        elif total(eligible) <= 0:
            reject(8, "E08")
            continue

        grade = roster.get(ev.get("operator_code", ""), "")
        protected = 1 if (int(ev["event_recorded_s"]) <= cb and grade_commit.get(grade, False)) else 0

        reg_class = missions[mid]["priority_class"]
        eff_class = reg_class
        best = None
        for ov in overrides:
            if ov["mission_id"] != mid or ov["antenna_uid"] != uid:
                continue
            if not (int(ov["valid_from_s"]) <= ss < int(ov["valid_to_s"])):
                continue
            key = (rank_of.get(ov["granted_class"], 1 << 30), ov["override_id"],
                   ov["granted_class"])
            if best is None or key < best:
                best = key
        if best is not None and best[0] < rank_of.get(reg_class, 1 << 30):
            eff_class = best[2]

        admitted.append({
            "contact_id": cid, "station_id": sid, "aperture_label": label,
            "antenna_uid": uid, "presentation_id": pres, "mission_id": mid,
            "scheduled_start_s": ss, "scheduled_end_s": se, "commit_boundary_s": cb,
            "event_status": ev["event_status"], "operator_code": ev.get("operator_code", ""),
            "protected": protected, "late_cancel": late_cancel,
            "effective_class": eff_class, "effective_rank": rank_of.get(eff_class, 1 << 30),
            "contracts": pass_contracts, "eligible": eligible, "zero_len": zero_len,
        })

    rejected.sort(key=lambda r: r["contact_id"])

    # ---------------- S04 clipping -----------------------------------------
    canon = []
    for p in admitted:
        sid = p["station_id"]
        if p["zero_len"]:
            ss = p["scheduled_start_s"]
            per = None
            for q in PERIOD_ORDER:
                w = period_window.get((sid, q))
                if w and w[0] <= ss < w[1]:
                    per = q
                    break
            if per is None:
                continue
            canon.append({"pass": p, "period_id": per, "pieces": [], "eligible_seconds": 0})
            continue
        for q in PERIOD_ORDER:
            w = period_window.get((sid, q))
            if not w:
                continue
            pieces = intersect(p["eligible"], [w])
            if not pieces:
                continue
            canon.append({"pass": p, "period_id": q, "pieces": pieces,
                          "eligible_seconds": total(pieces)})

    canon.sort(key=lambda c: (c["pass"]["contact_id"], pidx(c["period_id"])))

    # ---------------- S05 capacity -----------------------------------------
    for c in canon:
        uid = c["pass"]["antenna_uid"]
        edges = rate_edges.get(uid, [])
        raw = 0
        npieces = 0
        for a, b in c["pieces"]:
            cuts = [a] + [e for e in edges if a < e < b] + [b]
            for k in range(len(cuts) - 1):
                x, y = cuts[k], cuts[k + 1]
                if y <= x:
                    continue
                raw += ((y - x) * rate_at(uid, x)) // rate_div
                npieces += 1
        cap = per_contact_cap.get((uid, c["period_id"]), 0)
        c["rate_piece_count"] = npieces
        c["raw_capacity_kib"] = raw
        c["capacity_cap_kib"] = cap
        c["usable_capacity_kib"] = min(raw, cap)

    # ---------------- S07 contention ----------------------------------------
    def obligation_of(pass_contracts, period):
        vals = [terms[(cc, period)]["obligation_kib"] for cc in pass_contracts
                if (cc, period) in terms]
        return max(vals) if vals else 0

    for c in canon:
        c["remaining_obligation_kib"] = obligation_of(c["pass"]["contracts"], c["period_id"])

    def order_key(c):
        p = c["pass"]
        return (0 if p["protected"] else 1, p["effective_rank"], p["commit_boundary_s"],
                -c["remaining_obligation_kib"], p["contact_id"])

    groups = {}
    for c in canon:
        groups.setdefault((c["pass"]["antenna_uid"], c["period_id"]), []).append(c)

    contention_rows = []
    tie_rows = []
    for key in sorted(groups, key=lambda k: (k[0], pidx(k[1]))):
        uid, per = key
        rows = sorted(groups[key], key=order_key)
        # greedy walk
        accepted_list = []
        for c in rows:
            hit = None
            for acc in accepted_list:
                if overlap_len(c["pieces"], acc["pieces"]) >= 1:
                    hit = acc
                    break
            if hit is None:
                c["allocation_state"] = "won"
                accepted_list.append(c)
            else:
                c["allocation_state"] = "displaced"
                c["displaced_by"] = hit["pass"]["contact_id"]
        # intersection graph for groups and ties
        n = len(rows)
        adj = [[] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                if overlap_len(rows[i]["pieces"], rows[j]["pieces"]) >= 1:
                    adj[i].append(j)
                    adj[j].append(i)
                    ki, kj = order_key(rows[i]), order_key(rows[j])
                    level = 5
                    for lv in range(5):
                        if ki[lv] != kj[lv]:
                            level = lv + 1
                            break
                    first, second = (rows[i], rows[j]) if ki < kj else (rows[j], rows[i])
                    tie_rows.append((uid, per, first["pass"]["contact_id"],
                                     second["pass"]["contact_id"], level))
        seen = [False] * n
        comps = []
        for i in range(n):
            if seen[i]:
                continue
            stack = [i]
            seen[i] = True
            comp = []
            while stack:
                v = stack.pop()
                comp.append(v)
                for w in adj[v]:
                    if not seen[w]:
                        seen[w] = True
                        stack.append(w)
            comps.append(sorted(rows[v]["pass"]["contact_id"] for v in comp))
        comps.sort(key=lambda m: m[0])
        by_cid = {r["pass"]["contact_id"]: r for r in rows}
        for gs, members in enumerate(comps, start=1):
            contention_rows.append({
                "antenna_uid": uid, "period_id": per, "group_seq": gs,
                "member_count": len(members), "member_ids": ",".join(members),
                "eligible_seconds_total": sum(by_cid[m]["eligible_seconds"] for m in members),
            })
        groups[key] = rows

    won = [c for c in canon if c["allocation_state"] == "won"]
    displaced = [c for c in canon if c["allocation_state"] == "displaced"]

    # ---------------- S09 demand and ration ---------------------------------
    for c in won:
        ob = opening_backlog.get((c["pass"]["mission_id"], c["period_id"]), 0)
        c["demand_kib"] = min(c["usable_capacity_kib"], ob)
    for c in displaced:
        c["demand_kib"] = 0
        c["allocated_kib"] = 0
        c["accepted_kib"] = 0
        c["from_carry_kib"] = 0
        c["from_new_kib"] = 0

    ration_trace = []
    ration_groups = []
    for key in sorted(groups, key=lambda k: (k[0], pidx(k[1]))):
        uid, per = key
        rows = [c for c in groups[key] if c["allocation_state"] == "won"]
        if not rows:
            continue
        rows = sorted(rows, key=order_key)
        budget = period_budget.get((uid, per), 0)
        demands = [c["demand_kib"] for c in rows]
        dtotal = sum(demands)
        if dtotal <= budget:
            for c in rows:
                c["allocated_kib"] = c["demand_kib"]
            continue
        ration_groups.append((uid, per, dtotal, budget))
        n = len(rows)
        x = [0] * n
        pinned = [False] * n
        passes = min(ration_ceiling, ration_base + n)
        for seq in range(1, passes + 1):
            pinned_mass = sum(demands[i] for i in range(n) if pinned[i])
            active = [i for i in range(n) if not pinned[i]]
            if not active:
                ration_trace.append({
                    "antenna_uid": uid, "period_id": per, "pass_seq": seq,
                    "active_count": 0, "share_kib": 0, "allocated_kib": sum(x),
                    "budget_kib": budget, "demand_total_kib": dtotal})
                continue
            room = budget - pinned_mass
            share = room // len(active) if room > 0 else 0
            for i in active:
                target = min(demands[i], share)
                step = target - x[i]
                delta = (step * theta_num) // theta_den
                if step > 0 and delta < 1:
                    delta = 1
                x[i] += delta
            for i in active:
                if x[i] >= demands[i]:
                    x[i] = demands[i]
                    pinned[i] = True
            ration_trace.append({
                "antenna_uid": uid, "period_id": per, "pass_seq": seq,
                "active_count": len(active), "share_kib": share,
                "allocated_kib": sum(x), "budget_kib": budget,
                "demand_total_kib": dtotal})
        residual = budget - sum(x)
        if residual > 0:
            for i in range(n):
                if residual <= 0:
                    break
                give = min(residual, demands[i] - x[i])
                if give > 0:
                    x[i] += give
                    residual -= give
        for i, c in enumerate(rows):
            c["allocated_kib"] = x[i]

    # ---------------- S08 + S10 per period ----------------------------------
    carry_source = {cid: 0 for cid in contract_ids}
    for b in read_json(D("prior_period_settlement.json"))["opening_buckets"]:
        if b["bucket_state"] == "open":
            carry_source[b["contract_id"]] = carry_source.get(b["contract_id"], 0) + int(b["unsettled_kib"])

    entitlement_state = {}
    for per in PERIOD_ORDER:
        pstart = network_period_open[per]
        state = {}
        for cid in contract_ids:
            key = (cid, per)
            if key not in terms:
                continue
            t = terms[key]
            src = carry_source.get(cid, 0)
            expired = contracts[cid]["valid_to_s"] <= pstart
            enabled = t["carry_forward_enabled"] and contracts[cid]["carry_forward_enabled"]
            if not enabled or expired:
                carry_in = 0
            else:
                carry_in = min(src, t["carry_cap_kib"])
            forfeit = src - carry_in
            state[cid] = {
                "contract_id": cid, "period_id": per,
                "carry_source_kib": src, "carry_cap_kib": t["carry_cap_kib"],
                "carry_in_kib": carry_in, "carry_forfeit_kib": forfeit,
                "entitlement_kib": t["entitlement_kib"],
                "available_allowance_kib": carry_in + t["entitlement_kib"],
                "carry_rem": carry_in, "new_rem": t["entitlement_kib"],
                "contract_expired": 1 if expired else 0,
                "carry_forward_enabled": 1 if enabled else 0,
            }
        entitlement_state[per] = state

        running_backlog = {}
        rows = [c for c in won if c["period_id"] == per]
        rows.sort(key=lambda c: (c["pass"]["station_id"], c["pass"]["antenna_uid"]) + order_key(c))
        for c in rows:
            p = c["pass"]
            cands = [cc for cc in p["contracts"] if (cc, per) in terms]
            cands.sort(key=lambda cc: (-terms[(cc, per)]["obligation_kib"], cc))
            bc = cands[0] if cands else ""
            c["contract_id"] = bc
            mk = (p["mission_id"], per)
            if mk not in running_backlog:
                running_backlog[mk] = opening_backlog.get(mk, 0)
            st = state.get(bc)
            allow = (st["carry_rem"] + st["new_rem"]) if st else 0
            acc = min(c["allocated_kib"], running_backlog[mk], allow)
            if acc < 0:
                acc = 0
            fc = min(acc, st["carry_rem"]) if st else 0
            fn = acc - fc
            if st:
                st["carry_rem"] -= fc
                st["new_rem"] -= fn
            running_backlog[mk] -= acc
            c["accepted_kib"] = acc
            c["from_carry_kib"] = fc
            c["from_new_kib"] = fn
            c["deferred_kib"] = c["demand_kib"] - acc
            c["unused_capacity_kib"] = c["usable_capacity_kib"] - acc

        for cid, st in state.items():
            st["consumed_kib"] = st["available_allowance_kib"] - (st["carry_rem"] + st["new_rem"])
            st["unconsumed_kib"] = st["carry_rem"] + st["new_rem"]
            st["carry_out_kib"] = st["unconsumed_kib"]
        nxt = {}
        for cid in contract_ids:
            nxt[cid] = state[cid]["carry_out_kib"] if cid in state else carry_source.get(cid, 0)
        carry_source = nxt

    for c in displaced:
        c["contract_id"] = ""
        c["deferred_kib"] = 0
        c["unused_capacity_kib"] = 0

    # ---------------- S11 utilisation ---------------------------------------
    ap_util = {}
    for uid in antenna_ids:
        sid = ap_station[uid]
        for per in PERIOD_ORDER:
            w = period_window.get((sid, per))
            avail = intersect(availability[uid], [w]) if w else []
            occ = sum(c["eligible_seconds"] for c in groups.get((uid, per), [])
                      if c["allocation_state"] == "won")
            den = total(avail)
            bp = (occ * 10000) // den if den > 0 else 0
            ap_util[(uid, per)] = {"occupied_seconds": occ, "available_seconds": den,
                                   "utilisation_bp": bp,
                                   "denominator_state": "empty" if den == 0 else "populated"}
    st_util = {}
    for sid in station_ids:
        for per in PERIOD_ORDER:
            occ = sum(ap_util[(u, per)]["occupied_seconds"] for u in station_apertures.get(sid, ()))
            den = sum(ap_util[(u, per)]["available_seconds"] for u in station_apertures.get(sid, ()))
            bp = (occ * 10000) // den if den > 0 else 0
            st_util[(sid, per)] = {"occupied_seconds": occ, "available_seconds": den,
                                   "utilisation_bp": bp,
                                   "denominator_state": "empty" if den == 0 else "populated"}

    # ---------------- S13 credit and debit ----------------------------------
    claims = read_delim(D("outage_claims.psv"), "|")
    claims = [c for c in claims if c["claim_status"] == "accepted"]
    claims.sort(key=lambda c: c["claim_id"])

    delivered = {}
    for c in won:
        key = (c["contract_id"], c["period_id"])
        delivered[key] = delivered.get(key, 0) + c["accepted_kib"]

    rows_by_contract_period = {}
    for c in won:
        rows_by_contract_period.setdefault((c["contract_id"], c["period_id"]), []).append(c)

    credit_rows = []
    compliance_rows = []
    outage_rows = []
    net_by_contract_period = {}
    for cid in contract_ids:
        for per in PERIOD_ORDER:
            key = (cid, per)
            if key not in terms:
                continue
            t = terms[key]
            mid = contracts[cid]["mission_id"]
            dlv = delivered.get(key, 0)
            shortfall = max(0, t["obligation_kib"] - dlv)
            unused_res = max(0, t["reserved_kib"] - dlv)
            crows = rows_by_contract_period.get(key, [])
            overlap_total = 0
            qualifying = []
            for cl in claims:
                if cl["mission_id"] != mid or cl["period_id"] != per:
                    continue
                win = [(int(cl["claim_from_s"]), int(cl["claim_to_s"]))]
                sec = 0
                for c in crows:
                    if c["pass"]["antenna_uid"] != cl["antenna_uid"]:
                        continue
                    sec += overlap_len(c["pieces"], win)
                overlap_total += sec
                if sec >= 1:
                    qualifying.append(cl)
            qualified = overlap_total >= outage_floor
            pool = 0
            for cl in qualifying:
                for c in crows:
                    if c["pass"]["antenna_uid"] != cl["antenna_uid"]:
                        continue
                    if c["pass"]["late_cancel"] == 1:
                        continue
                    pool += c["deferred_kib"]
            exempt = min(shortfall, pool) if qualified else 0
            st = entitlement_state[per][cid]
            if qualified:
                shortfall_debit = 0
                outage_credit = (exempt * outage_rate) // credit_basis
                carry_restore = min(st["carry_forfeit_kib"], (exempt * restore_num) // restore_den)
            else:
                shortfall_debit = (shortfall * shortfall_rate) // credit_basis
                outage_credit = 0
                carry_restore = 0
            unused_credit = (unused_res * unused_rate) // credit_basis
            net = unused_credit + outage_credit - shortfall_debit
            net_by_contract_period[key] = net
            if shortfall == 0:
                cstate = "met"
            elif qualified:
                cstate = "exempt"
            else:
                cstate = "short"
            compliance_rows.append((cid, per, mid, t["obligation_kib"], dlv,
                                    t["reserved_kib"], shortfall, cstate))
            credit_rows.append((cid, per, shortfall, shortfall_debit, unused_res,
                                unused_credit, outage_credit, carry_restore, net))
            outage_rows.append((cid, per, mid, overlap_total, outage_floor,
                                1 if qualified else 0, exempt, carry_restore))

    # ---------------- S12 aggregation ---------------------------------------
    mission_stmt = []
    for mid in mission_ids:
        for per in PERIOD_ORDER:
            rows = [c for c in won if c["pass"]["mission_id"] == mid and c["period_id"] == per]
            net = sum(net_by_contract_period.get((cc, per), 0)
                      for cc in mission_contracts.get(mid, ()))
            mission_stmt.append((mid, per, len(rows),
                                 sum(c["eligible_seconds"] for c in rows),
                                 sum(c["usable_capacity_kib"] for c in rows),
                                 sum(c["accepted_kib"] for c in rows),
                                 sum(c["deferred_kib"] for c in rows),
                                 sum(c["unused_capacity_kib"] for c in rows),
                                 net))
    station_stmt = []
    for sid in station_ids:
        for per in PERIOD_ORDER:
            rows = [c for c in won if c["pass"]["station_id"] == sid and c["period_id"] == per]
            station_stmt.append((sid, per, len(rows),
                                 sum(c["eligible_seconds"] for c in rows),
                                 sum(c["accepted_kib"] for c in rows),
                                 sum(c["unused_capacity_kib"] for c in rows),
                                 st_util[(sid, per)]["utilisation_bp"]))

    # ---------------- artifacts ---------------------------------------------
    os.makedirs(out_dir, exist_ok=True)
    artifacts = []

    def emit(name, data):
        artifacts.append((name, data))

    emit("canonical_contact_ledger.csv", ser_delim(
        ["contact_id", "period_id", "station_id", "antenna_uid", "mission_id", "contract_id",
         "eligible_seconds", "raw_capacity_kib", "usable_capacity_kib", "effective_class",
         "protected", "late_cancel", "allocation_state", "demand_kib", "allocated_kib",
         "accepted_kib"],
        [[c["pass"]["contact_id"], c["period_id"], c["pass"]["station_id"],
          c["pass"]["antenna_uid"], c["pass"]["mission_id"], c["contract_id"],
          c["eligible_seconds"], c["raw_capacity_kib"], c["usable_capacity_kib"],
          c["pass"]["effective_class"], c["pass"]["protected"], c["pass"]["late_cancel"],
          c["allocation_state"], c["demand_kib"], c["allocated_kib"], c["accepted_kib"]]
         for c in canon], ","))

    emit("admitted_contact_ledger.csv", ser_delim(
        ["contact_id", "period_id", "station_id", "antenna_uid", "mission_id", "presentation_id",
         "scheduled_start_s", "scheduled_end_s", "commit_boundary_s", "event_status",
         "operator_code", "protected", "late_cancel", "eligible_seconds"],
        [[c["pass"]["contact_id"], c["period_id"], c["pass"]["station_id"],
          c["pass"]["antenna_uid"], c["pass"]["mission_id"], c["pass"]["presentation_id"],
          c["pass"]["scheduled_start_s"], c["pass"]["scheduled_end_s"],
          c["pass"]["commit_boundary_s"], c["pass"]["event_status"], c["pass"]["operator_code"],
          c["pass"]["protected"], c["pass"]["late_cancel"], c["eligible_seconds"]]
         for c in canon], ","))

    emit("rejected_contact_ledger.psv", ser_delim(
        ["contact_id", "station_id", "aperture_label", "presentation_id", "scheduled_start_s",
         "scheduled_end_s", "predicate_index", "reject_code", "reject_reason"],
        [[r["contact_id"], r["station_id"], r["aperture_label"], r["presentation_id"],
          r["scheduled_start_s"], r["scheduled_end_s"], r["predicate_index"],
          r["reject_code"], r["reject_reason"]] for r in rejected], "|"))

    interval_rows = []
    for c in canon:
        if c["pieces"]:
            for a, b in c["pieces"]:
                interval_rows.append([c["pass"]["contact_id"], c["period_id"],
                                      c["pass"]["antenna_uid"], a, b, b - a])
        else:
            s = c["pass"]["scheduled_start_s"]
            interval_rows.append([c["pass"]["contact_id"], c["period_id"],
                                  c["pass"]["antenna_uid"], s, s, 0])
    emit("normalized_contact_intervals.tsv", ser_delim(
        ["contact_id", "period_id", "antenna_uid", "segment_start_s", "segment_end_s",
         "segment_seconds"], interval_rows, "\t"))

    emit("antenna_capacity_ledger.csv", ser_delim(
        ["contact_id", "period_id", "antenna_uid", "eligible_seconds", "rate_piece_count",
         "raw_capacity_kib", "capacity_cap_kib", "usable_capacity_kib"],
        [[c["pass"]["contact_id"], c["period_id"], c["pass"]["antenna_uid"],
          c["eligible_seconds"], c["rate_piece_count"], c["raw_capacity_kib"],
          c["capacity_cap_kib"], c["usable_capacity_kib"]] for c in canon], ","))

    cap_exc = [c for c in canon if c["raw_capacity_kib"] > c["capacity_cap_kib"]]
    emit("capacity_cap_exceptions.psv", ser_delim(
        ["contact_id", "period_id", "antenna_uid", "raw_capacity_kib", "capacity_cap_kib",
         "clipped_kib"],
        [[c["pass"]["contact_id"], c["period_id"], c["pass"]["antenna_uid"],
          c["raw_capacity_kib"], c["capacity_cap_kib"],
          c["raw_capacity_kib"] - c["capacity_cap_kib"]] for c in cap_exc], "|"))

    emit("contention_groups.jsonl", ser_jsonl(contention_rows))

    won_sorted = sorted(won, key=lambda c: (c["pass"]["contact_id"], pidx(c["period_id"])))
    disp_sorted = sorted(displaced, key=lambda c: (c["pass"]["contact_id"], pidx(c["period_id"])))

    emit("winning_resource_assignments.csv", ser_delim(
        ["contact_id", "period_id", "antenna_uid", "mission_id", "effective_class",
         "effective_rank", "protected", "commit_boundary_s", "remaining_obligation_kib",
         "eligible_seconds", "usable_capacity_kib"],
        [[c["pass"]["contact_id"], c["period_id"], c["pass"]["antenna_uid"],
          c["pass"]["mission_id"], c["pass"]["effective_class"], c["pass"]["effective_rank"],
          c["pass"]["protected"], c["pass"]["commit_boundary_s"],
          c["remaining_obligation_kib"], c["eligible_seconds"], c["usable_capacity_kib"]]
         for c in won_sorted], ","))

    emit("displaced_contact_ledger.psv", ser_delim(
        ["contact_id", "period_id", "antenna_uid", "mission_id", "displaced_by",
         "displaced_seconds", "usable_capacity_kib"],
        [[c["pass"]["contact_id"], c["period_id"], c["pass"]["antenna_uid"],
          c["pass"]["mission_id"], c["displaced_by"], c["eligible_seconds"],
          c["usable_capacity_kib"]] for c in disp_sorted], "|"))

    ent_rows = []
    carry_rows = []
    for cid in contract_ids:
        for per in PERIOD_ORDER:
            st = entitlement_state[per].get(cid)
            if st is None:
                continue
            ent_rows.append([cid, per, st["carry_source_kib"], st["carry_cap_kib"],
                             st["carry_in_kib"], st["carry_forfeit_kib"], st["entitlement_kib"],
                             st["available_allowance_kib"], st["consumed_kib"],
                             st["unconsumed_kib"], st["contract_expired"]])
            carry_rows.append([cid, per, st["carry_in_kib"], st["carry_forfeit_kib"],
                               st["carry_out_kib"], st["carry_forward_enabled"]])
    emit("mission_entitlement_state.csv", ser_delim(
        ["contract_id", "period_id", "carry_source_kib", "carry_cap_kib", "carry_in_kib",
         "carry_forfeit_kib", "entitlement_kib", "available_allowance_kib", "consumed_kib",
         "unconsumed_kib", "contract_expired"], ent_rows, ","))
    emit("carry_forward_ledger.csv", ser_delim(
        ["contract_id", "period_id", "carry_in_kib", "carry_forfeit_kib", "carry_out_kib",
         "carry_forward_enabled"], carry_rows, ","))

    emit("rationing_pass_trace.jsonl", ser_jsonl(sorted(
        ration_trace, key=lambda r: (r["antenna_uid"], pidx(r["period_id"]), r["pass_seq"]))))

    emit("delivered_volume_ledger.csv", ser_delim(
        ["contact_id", "period_id", "mission_id", "contract_id", "antenna_uid", "demand_kib",
         "allocated_kib", "accepted_kib", "from_carry_kib", "from_new_kib"],
        [[c["pass"]["contact_id"], c["period_id"], c["pass"]["mission_id"], c["contract_id"],
          c["pass"]["antenna_uid"], c["demand_kib"], c["allocated_kib"], c["accepted_kib"],
          c["from_carry_kib"], c["from_new_kib"]] for c in won_sorted], ","))

    emit("deferred_volume_ledger.csv", ser_delim(
        ["contact_id", "period_id", "mission_id", "demand_kib", "accepted_kib", "deferred_kib",
         "late_cancel"],
        [[c["pass"]["contact_id"], c["period_id"], c["pass"]["mission_id"], c["demand_kib"],
          c["accepted_kib"], c["deferred_kib"], c["pass"]["late_cancel"]]
         for c in won_sorted], ","))

    emit("unused_capacity_ledger.tsv", ser_delim(
        ["contact_id", "period_id", "antenna_uid", "usable_capacity_kib", "accepted_kib",
         "unused_capacity_kib"],
        [[c["pass"]["contact_id"], c["period_id"], c["pass"]["antenna_uid"],
          c["usable_capacity_kib"], c["accepted_kib"], c["unused_capacity_kib"]]
         for c in won_sorted], "\t"))

    emit("station_utilisation_ledger.csv", ser_delim(
        ["station_id", "period_id", "occupied_seconds", "available_seconds", "utilisation_bp",
         "denominator_state"],
        [[sid, per, st_util[(sid, per)]["occupied_seconds"],
          st_util[(sid, per)]["available_seconds"], st_util[(sid, per)]["utilisation_bp"],
          st_util[(sid, per)]["denominator_state"]]
         for sid in station_ids for per in PERIOD_ORDER], ","))

    emit("antenna_utilisation_ledger.tsv", ser_delim(
        ["antenna_uid", "period_id", "occupied_seconds", "available_seconds", "utilisation_bp",
         "denominator_state"],
        [[uid, per, ap_util[(uid, per)]["occupied_seconds"],
          ap_util[(uid, per)]["available_seconds"], ap_util[(uid, per)]["utilisation_bp"],
          ap_util[(uid, per)]["denominator_state"]]
         for uid in antenna_ids for per in PERIOD_ORDER], "\t"))

    emit("mission_settlement_statements.csv", ser_delim(
        ["mission_id", "period_id", "won_pass_count", "eligible_seconds", "usable_capacity_kib",
         "accepted_kib", "deferred_kib", "unused_capacity_kib", "net_mcr"],
        [list(r) for r in mission_stmt], ","))

    emit("station_settlement_statements.csv", ser_delim(
        ["station_id", "period_id", "won_pass_count", "eligible_seconds", "accepted_kib",
         "unused_capacity_kib", "utilisation_bp"],
        [list(r) for r in station_stmt], ","))

    emit("contract_compliance_ledger.csv", ser_delim(
        ["contract_id", "period_id", "mission_id", "obligation_kib", "delivered_kib",
         "reserved_kib", "shortfall_kib", "compliance_state"],
        [list(r) for r in compliance_rows], ","))

    emit("credit_debit_ledger.csv", ser_delim(
        ["contract_id", "period_id", "shortfall_kib", "shortfall_debit_mcr",
         "unused_reserved_kib", "unused_credit_mcr", "outage_credit_mcr", "carry_restore_kib",
         "net_mcr"], [list(r) for r in credit_rows], ","))

    emit("outage_adjustment_ledger.psv", ser_delim(
        ["contract_id", "period_id", "mission_id", "claim_overlap_seconds",
         "qualifying_floor_seconds", "outage_qualified", "exempt_kib", "carry_restore_kib"],
        [list(r) for r in outage_rows], "|"))

    # exception report
    exc = []
    for r in rejected:
        exc.append(("", {"exception_class": codes[r["reject_code"]]["report_class"],
                         "subject_id": r["contact_id"], "code": r["reject_code"],
                         "detail_value": r["predicate_index"]}))
    for c in cap_exc:
        exc.append((c["period_id"], {"exception_class": codes["X01"]["report_class"],
                                     "subject_id": c["pass"]["contact_id"], "code": "X01",
                                     "detail_value": c["raw_capacity_kib"] - c["capacity_cap_kib"]}))
    for c in disp_sorted:
        exc.append((c["period_id"], {"exception_class": codes["X02"]["report_class"],
                                     "subject_id": c["pass"]["contact_id"], "code": "X02",
                                     "detail_value": c["eligible_seconds"]}))
    for cid in contract_ids:
        for per in PERIOD_ORDER:
            st = entitlement_state[per].get(cid)
            if st and st["carry_forfeit_kib"] > 0:
                exc.append((per, {"exception_class": codes["X03"]["report_class"],
                                  "subject_id": cid, "code": "X03",
                                  "detail_value": st["carry_forfeit_kib"]}))
    for uid in antenna_ids:
        for per in PERIOD_ORDER:
            if ap_util[(uid, per)]["denominator_state"] == "empty":
                exc.append((per, {"exception_class": codes["X04"]["report_class"],
                                  "subject_id": uid, "code": "X04", "detail_value": 0}))
    for c in canon:
        if c["pass"]["late_cancel"] == 1:
            exc.append((c["period_id"], {"exception_class": codes["X05"]["report_class"],
                                         "subject_id": c["pass"]["contact_id"], "code": "X05",
                                         "detail_value": c["deferred_kib"]}))
    exc.sort(key=lambda e: (e[1]["exception_class"], e[1]["subject_id"], e[1]["code"],
                            pidx(e[0]) if e[0] else -1))
    emit("exception_classification_report.jsonl", ser_jsonl([e[1] for e in exc]))

    tie_rows.sort(key=lambda t: (t[0], pidx(t[1]), t[2], t[3]))
    emit("tie_resolution_report.csv", ser_delim(
        ["antenna_uid", "period_id", "contact_id_kept", "contact_id_yielded", "decided_at_level"],
        [list(t) for t in tie_rows], ","))

    # discrepancy report
    reports = {}
    for r in read_delim(D("downlink_reports.csv"), ","):
        cid = r["contact_id"]
        seq = int(r["report_seq"])
        if cid not in reports or seq > reports[cid][0]:
            reports[cid] = (seq, int(r["reported_kib"]))
    accepted_by_pass = {}
    for c in won:
        accepted_by_pass[c["pass"]["contact_id"]] = \
            accepted_by_pass.get(c["pass"]["contact_id"], 0) + c["accepted_kib"]
    disc = []
    for cid in sorted(accepted_by_pass):
        if cid not in reports:
            continue
        left = accepted_by_pass[cid]
        right = reports[cid][1]
        if left == right:
            continue
        disc.append(["canonical_ledger", "downlink_report", cid, "", left, right,
                     left - right, "over_report" if right > left else "under_report"])
    legacy = {}
    for r in read_delim(D("legacy_flat_rate_table.csv"), ","):
        uid = r["antenna_uid"]
        rev = int(r["table_rev"])
        if uid not in legacy or rev > legacy[uid][0]:
            legacy[uid] = (rev, int(r["flat_rate_mkib_per_s"]))
    for uid in antenna_ids:
        if uid not in legacy or uid not in rate_sched:
            continue
        flat = legacy[uid][1]
        lo = min(x[2] for x in rate_sched[uid])
        hi = max(x[2] for x in rate_sched[uid])
        if lo <= flat <= hi:
            continue
        near = lo if flat < lo else hi
        disc.append(["rate_schedule", "legacy_flat_table", uid, "", near, flat,
                     near - flat, "retired_rate_outside_band"])
    disc.sort(key=lambda d: (d[0], d[2]))
    emit("cross_source_discrepancy_report.psv", ser_delim(
        ["source_left", "source_right", "subject_id", "period_id", "left_value", "right_value",
         "delta_value", "discrepancy_class"], disc, "|"))

    # invariants
    v2 = sum(1 for c in won if c["accepted_kib"] > c["allocated_kib"])
    v3 = sum(1 for c in won if c["allocated_kib"] > c["demand_kib"])
    alloc_by_ap = {}
    for c in won:
        k = (c["pass"]["antenna_uid"], c["period_id"])
        alloc_by_ap[k] = alloc_by_ap.get(k, 0) + c["allocated_kib"]
    v6 = sum(1 for k, v in alloc_by_ap.items() if v > period_budget.get(k, 0))
    traced = {(r["antenna_uid"], r["period_id"]) for r in ration_trace}
    v8 = 0
    for uid, per in traced:
        rows = [c for c in groups.get((uid, per), []) if c["allocation_state"] == "won"]
        if sum(c["demand_kib"] for c in rows) <= period_budget.get((uid, per), 0):
            v8 += 1
    checks = [
        ("admitted_equals_won_plus_displaced", len(canon), len(won) + len(displaced)),
        ("accepted_never_exceeds_allocated", v2, 0),
        ("allocated_never_exceeds_demand", v3, 0),
        ("unused_matches_capacity_less_accepted",
         sum(c["unused_capacity_kib"] for c in won),
         sum(c["usable_capacity_kib"] for c in won) - sum(c["accepted_kib"] for c in won)),
        ("carry_split_matches_accepted",
         sum(c["from_carry_kib"] + c["from_new_kib"] for c in won),
         sum(c["accepted_kib"] for c in won)),
        ("allocation_within_aperture_budget", v6, 0),
        ("credit_rows_match_entitlement_rows", len(credit_rows), len(ent_rows)),
        ("ration_trace_groups_are_over_subscribed", v8, 0),
    ]
    check_objs = [{"check_name": n, "left_value": l, "right_value": r,
                   "balanced": 1 if l == r else 0} for n, l, r in checks]
    emit("invariant_check_report.json", ser_json({
        "check_count": len(check_objs), "checks": check_objs,
        "all_balanced": 1 if all(c["balanced"] == 1 for c in check_objs) else 0}))

    # period reconciliation
    recon = {}
    for per in PERIOD_ORDER:
        rows = [c for c in won if c["period_id"] == per]
        ents = [entitlement_state[per][cid] for cid in contract_ids
                if cid in entitlement_state[per]]
        cr = [r for r in credit_rows if r[1] == per]
        recon[per] = {
            "won_pass_count": len(rows),
            "eligible_seconds": sum(c["eligible_seconds"] for c in rows),
            "usable_capacity_kib": sum(c["usable_capacity_kib"] for c in rows),
            "accepted_kib": sum(c["accepted_kib"] for c in rows),
            "deferred_kib": sum(c["deferred_kib"] for c in rows),
            "unused_capacity_kib": sum(c["unused_capacity_kib"] for c in rows),
            "carry_in_kib": sum(e["carry_in_kib"] for e in ents),
            "carry_forfeit_kib": sum(e["carry_forfeit_kib"] for e in ents),
            "carry_out_kib": sum(e["carry_out_kib"] for e in ents),
            "shortfall_debit_mcr": sum(r[3] for r in cr),
            "unused_credit_mcr": sum(r[5] for r in cr),
            "outage_credit_mcr": sum(r[6] for r in cr),
            "net_mcr": sum(r[8] for r in cr),
            "occupied_seconds": sum(st_util[(s, per)]["occupied_seconds"] for s in station_ids),
            "available_seconds": sum(st_util[(s, per)]["available_seconds"] for s in station_ids),
        }
    recon["network"] = {
        "net_mcr": sum(recon[p]["net_mcr"] for p in PERIOD_ORDER),
        "accepted_kib": sum(recon[p]["accepted_kib"] for p in PERIOD_ORDER),
        "won_pass_count": sum(recon[p]["won_pass_count"] for p in PERIOD_ORDER),
    }
    emit("period_reconciliation_totals.json", ser_json(recon))

    # xml summary
    lines = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', "<settlement>", "<missions>"]
    for mid, per, _wc, _es, _uc, acc, dfr, _un, net in mission_stmt:
        lines.append('<mission id="%s" period="%s"><accepted_kib>%d</accepted_kib>'
                     '<deferred_kib>%d</deferred_kib><net_mcr>%d</net_mcr></mission>'
                     % (mid, per, acc, dfr, net))
    lines.append("</missions>")
    lines.append("<stations>")
    for sid, per, _wc, _es, acc, _un, bp in station_stmt:
        lines.append('<station id="%s" period="%s"><accepted_kib>%d</accepted_kib>'
                     '<utilisation_bp>%d</utilisation_bp></station>' % (sid, per, acc, bp))
    lines.append("</stations>")
    lines.append("<network>")
    lines.append("<net_mcr>%d</net_mcr>" % recon["network"]["net_mcr"])
    lines.append("<contract_period_count>%d</contract_period_count>" % len(credit_rows))
    lines.append("</network>")
    lines.append("</settlement>")
    emit("network_settlement_summary.xml", ("\n".join(lines) + "\n").encode("utf-8"))

    md = ["# mission settlement summary", "",
          "| mission_id | accepted_kib | deferred_kib | unused_capacity_kib | net_mcr |",
          "| --- | --- | --- | --- | --- |"]
    for mid in mission_ids:
        rows = [r for r in mission_stmt if r[0] == mid]
        md.append("| %s | %d | %d | %d | %d |" % (
            mid, sum(r[5] for r in rows), sum(r[6] for r in rows),
            sum(r[7] for r in rows), sum(r[8] for r in rows)))
    md.append("")
    md.append("network net_mcr %d" % recon["network"]["net_mcr"])
    emit("per_mission_final_summary.md", ("\n".join(md) + "\n").encode("utf-8"))

    for name, blob in artifacts:
        with open(os.path.join(out_dir, name), "wb") as fh:
            fh.write(blob)

    per_sha = {}
    cat = hashlib.sha256()
    for name, _ in artifacts:
        blob = open(os.path.join(out_dir, name), "rb").read()
        per_sha[name] = hashlib.sha256(blob).hexdigest()
        cat.update(blob)
    manifest = ser_json({
        "artifact_count": len(artifacts),
        "core_digest": cat.hexdigest(),
        "per_artifact_sha256": per_sha,
        "stage_count": 14,
    })
    with open(os.path.join(out_dir, "stage_digest_manifest.json"), "wb") as fh:
        fh.write(manifest)

    return {
        "binding_sheet": binding_sheet_name,
        "commit_lead": commit_lead,
        "outage_floor": outage_floor,
        "ration_base": ration_base,
        "ration_ceiling": ration_ceiling,
        "admitted_rows": len(canon),
        "won": len(won),
        "displaced": len(displaced),
        "rejected": len(rejected),
        "ration_groups": ration_groups,
        "core_digest": cat.hexdigest(),
        "compliance_rows": compliance_rows,
        "outage_rows": outage_rows,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    run(args.data, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
