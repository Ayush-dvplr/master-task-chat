#!/usr/bin/env python3
"""PACR-1.0 pension accrual / COLA / rebase engine (standard library only).

Usage: python3 calculate_pension.py DATA_DIR OUT_DIR
"""
import datetime as dt
import hashlib
import json
import os
import re
import sys
from decimal import ROUND_HALF_UP, Decimal, getcontext

getcontext().prec = 80

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
KIND_ORDER = {"ACCRUAL": 0, "COLA": 1, "REBASE": 2}


def rhu(num, den):
    """ROUND_HALF_UP(num / den) for integers, returned as int."""
    return int((Decimal(num) / Decimal(den)).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def parse_date(v):
    if not isinstance(v, str) or not DATE_RE.match(v):
        return None
    try:
        return dt.date.fromisoformat(v)
    except ValueError:
        return None


def parse_ts(v):
    if not isinstance(v, str):
        return None
    s = v.strip()
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"
    try:
        t = dt.datetime.fromisoformat(s)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc)


def is_str(v):
    return isinstance(v, str) and v != ""


def read_json(path, default):
    if not os.path.isfile(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def read_jsonl(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    # row order is irrelevant: canonicalise
    rows.sort(key=lambda r: json.dumps(r, sort_keys=True, separators=(",", ":")))
    return rows


def write_report(out_dir, name, obj):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False))
        fh.write("\n")


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def rid(row, key):
    v = row.get(key) if isinstance(row, dict) else None
    return v if isinstance(v, str) else ("" if v is None else str(v))


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: calculate_pension.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)

    issues = []

    def issue(code, record_id):
        issues.append({"code": code, "record_id": record_id})

    # ---------------- inputs ----------------
    policy = read_json(os.path.join(data_dir, "policy.json"), {})
    engine_version = policy.get("engine_version")
    valuation = parse_date(policy.get("valuation_date"))
    days_per_year = policy.get("days_per_year")
    material_cents = policy.get("material_cents")
    if valuation is None or not is_int(days_per_year) or days_per_year <= 0:
        raise SystemExit("invalid policy.json")
    if not is_int(material_cents) or material_cents < 0:
        raise SystemExit("invalid policy.json material_cents")

    plans_raw = read_json(os.path.join(data_dir, "plans.json"), [])
    if isinstance(plans_raw, dict) and "plans" in plans_raw:
        plans_raw = plans_raw["plans"]
    plans = {}
    for p in sorted(plans_raw, key=canon):
        pid = p.get("plan_id")
        if is_str(pid) and pid not in plans:
            plans[pid] = p

    members_rows = read_jsonl(os.path.join(data_dir, "members.jsonl"))
    service_rows = read_jsonl(os.path.join(data_dir, "service_revisions.jsonl"))
    salary_rows = read_jsonl(os.path.join(data_dir, "salary_history.jsonl"))
    leave_rows = read_jsonl(os.path.join(data_dir, "leave_intervals.jsonl"))
    cola_rows = read_jsonl(os.path.join(data_dir, "cola_rules.jsonl"))
    rebase_rows = read_jsonl(os.path.join(data_dir, "rebase_events.jsonl"))
    election_rows = read_jsonl(os.path.join(data_dir, "elections.jsonl"))

    # ---------------- members ----------------
    members = {}
    for m in members_rows:
        mid = m.get("member_id")
        birth = parse_date(m.get("birth_date"))
        if not is_str(mid) or m.get("plan_id") not in plans or birth is None or mid in members:
            issue("INVALID_MEMBER", rid(m, "member_id"))
            continue
        members[mid] = {"member_id": mid, "plan_id": m["plan_id"], "birth": birth}

    # ---------------- service revisions ----------------
    by_service = {}
    for r in service_rows:
        sid = r.get("service_id")
        ts = parse_ts(r.get("recorded_at"))
        if not is_str(sid) or not is_int(r.get("revision")) or ts is None or not is_str(r.get("record_id")):
            issue("INVALID_SERVICE", rid(r, "record_id"))
            continue
        by_service.setdefault(sid, []).append((r["revision"], ts, r["record_id"], r))

    decisions = []
    effective = []
    for sid in sorted(by_service):
        cands = sorted(by_service[sid], key=lambda c: (c[0], c[1], c[2]))
        win = cands[-1]
        winner = win[3]
        peers = [c[3] for c in cands if c[0] == win[0] and c[1] == win[1]]
        conflict = False
        if len(peers) > 1:
            strip = lambda d: {k: v for k, v in d.items() if k != "record_id"}
            base = canon(strip(winner))
            conflict = any(canon(strip(p)) != base for p in peers)
        if conflict:
            issue("REVISION_TIE_CONFLICT", sid)
        status = winner.get("status")
        is_effective = False
        if status == "active":
            start = parse_date(winner.get("start"))
            end = parse_date(winner.get("end"))
            if winner.get("member_id") not in members or start is None or end is None or start >= end:
                issue("INVALID_SERVICE", winner["record_id"])
            else:
                is_effective = True
                effective.append({"service_id": sid, "member_id": winner["member_id"],
                                  "start": start.isoformat(), "end": end.isoformat()})
        decisions.append({
            "service_id": sid,
            "record_id": winner["record_id"],
            "revision": winner["revision"],
            "recorded_at": winner.get("recorded_at"),
            "status": status,
            "candidate_count": len(cands),
            "tie_conflict": conflict,
            "effective": is_effective,
        })
    effective.sort(key=lambda e: (e["member_id"], e["start"], e["end"], e["service_id"]))

    # ---------------- salary / leave ----------------
    salaries = {}
    for s in salary_rows:
        st, en = parse_date(s.get("start")), parse_date(s.get("end"))
        amt = s.get("annual_salary_cents")
        if (not is_str(s.get("salary_id")) or s.get("member_id") not in members or st is None
                or en is None or st >= en or not is_int(amt) or amt < 0):
            issue("INVALID_SALARY", rid(s, "salary_id"))
            continue
        salaries.setdefault(s["member_id"], []).append((st, en, s["salary_id"], amt))

    leaves = {}
    for lv in leave_rows:
        st, en = parse_date(lv.get("start")), parse_date(lv.get("end"))
        cb = lv.get("credit_bps")
        if (not is_str(lv.get("leave_id")) or lv.get("member_id") not in members or st is None
                or en is None or st >= en or not is_int(cb) or cb < 0 or cb > 10000):
            issue("INVALID_LEAVE", rid(lv, "leave_id"))
            continue
        leaves.setdefault(lv["member_id"], []).append((st, en, lv["leave_id"], cb))

    # ---------------- COLA / rebase / elections ----------------
    colas = {}
    for c in cola_rows:
        d = parse_date(c.get("effective_date"))
        f = c.get("factor_bps")
        if not is_str(c.get("cola_id")) or c.get("plan_id") not in plans or d is None or not is_int(f) or f < 0:
            issue("INVALID_COLA", rid(c, "cola_id"))
            continue
        colas.setdefault(c["plan_id"], []).append((d, c["cola_id"], f))

    rebases = {}
    for r in rebase_rows:
        d = parse_date(r.get("effective_date"))
        f = r.get("factor_bps")
        if not is_str(r.get("rebase_id")) or r.get("member_id") not in members or d is None or not is_int(f) or f < 0:
            issue("INVALID_REBASE", rid(r, "rebase_id"))
            continue
        rebases.setdefault(r["member_id"], []).append((d, r["rebase_id"], f))

    elections = {}
    for e in election_rows:
        d = parse_date(e.get("retirement_date"))
        f = e.get("option_factor_bps")
        if (not is_str(e.get("election_id")) or e.get("member_id") not in members or d is None
                or not is_int(f) or f < 0 or f > 10000):
            issue("INVALID_ELECTION", rid(e, "election_id"))
            continue
        cur = elections.get(e["member_id"])
        cand = (d, e["election_id"], f)
        if cur is None or (cand[0], cand[1]) > (cur[0], cur[1]):
            elections[e["member_id"]] = cand

    # ---------------- accrual atoms ----------------
    atoms = []
    for svc in effective:
        mid = svc["member_id"]
        plan = plans[members[mid]["plan_id"]]
        s0, s1 = dt.date.fromisoformat(svc["start"]), dt.date.fromisoformat(svc["end"])
        cuts = {s0, s1}
        for (a, b, _i, _v) in salaries.get(mid, []):
            if a < s1 and b > s0:
                cuts.update(x for x in (a, b) if s0 < x < s1)
        for (a, b, _i, _v) in leaves.get(mid, []):
            if a < s1 and b > s0:
                cuts.update(x for x in (a, b) if s0 < x < s1)
        for y in range(s0.year + 1, s1.year + 1):
            j = dt.date(y, 1, 1)
            if s0 < j < s1:
                cuts.add(j)
        if s0 < valuation < s1:
            cuts.add(valuation)
        pts = sorted(cuts)
        for a, b in zip(pts, pts[1:]):
            if b > valuation or a >= b:
                continue
            cover = [s for s in salaries.get(mid, []) if s[0] <= a and b <= s[1]]
            if not cover:
                issue("MISSING_SALARY", "%s:%s" % (svc["service_id"], a.isoformat()))
                continue
            sal = max(cover, key=lambda s: (s[0], s[2]))
            capped = min(sal[3], plan["annual_cap_cents"])
            lcov = [l[3] for l in leaves.get(mid, []) if l[0] <= a and b <= l[1]]
            lf = min(lcov) if lcov else 10000
            cal = (b - a).days
            credited = rhu(cal * lf, 10000)
            accrual = rhu(capped * plan["accrual_bps"] * credited, 10000 * days_per_year)
            atoms.append({
                "member_id": mid,
                "plan_id": plan["plan_id"],
                "service_id": svc["service_id"],
                "salary_id": sal[2],
                "start": a.isoformat(),
                "end": b.isoformat(),
                "calendar_days": cal,
                "leave_factor_bps": lf,
                "credited_days": credited,
                "capped_salary_cents": capped,
                "accrual_bps": plan["accrual_bps"],
                "accrual_cents": accrual,
            })
    atoms.sort(key=lambda x: (x["member_id"], x["start"], x["end"], x["service_id"], x["salary_id"]))

    # ---------------- event revaluation ----------------
    events_out = []
    benefits = []
    for mid in sorted(members):
        m = members[mid]
        plan = plans[m["plan_id"]]
        stream = []
        for at in atoms:
            if at["member_id"] == mid:
                stream.append((at["end"], "ACCRUAL", "%s:%s" % (at["service_id"], at["start"]), None, at["accrual_cents"]))
        for (d, cid, f) in colas.get(m["plan_id"], []):
            stream.append((d.isoformat(), "COLA", cid, f, None))
        for (d, rbid, f) in rebases.get(mid, []):
            stream.append((d.isoformat(), "REBASE", rbid, f, None))
        stream = [e for e in stream if e[0] <= valuation.isoformat()]
        stream.sort(key=lambda e: (e[0], KIND_ORDER[e[1]], e[2]))
        bal = 0
        base = 0
        reval = 0
        for (d, kind, eid, f, amt) in stream:
            before = bal
            if kind == "ACCRUAL":
                bal = bal + amt
                base += amt
            else:
                bal = rhu(bal * f, 10000)
                reval += bal - before
            events_out.append({
                "member_id": mid, "event_date": d, "event_kind": kind, "event_id": eid,
                "factor_bps": f, "balance_before_cents": before, "balance_after_cents": bal,
                "delta_cents": bal - before,
            })
        accrued = bal
        el = elections.get(mid)
        if el is not None:
            rd, eid, of = el
            b = m["birth"]
            age = (rd.year - b.year) * 12 + rd.month - b.month - (1 if rd.day < b.day else 0)
            early = max(0, plan["normal_age_months"] - age)
            red = min(10000, early * plan["early_reduction_bps_per_month"])
            el_id, ret_date = eid, rd.isoformat()
        else:
            age, early, red, of, el_id, ret_date = None, 0, 0, plan["option_factor_bps"], None, None
        reduced = rhu(accrued * (10000 - red), 10000)
        payable = rhu(reduced * of, 10000)
        benefits.append({
            "member_id": mid,
            "plan_id": m["plan_id"],
            "credited_days": sum(a["credited_days"] for a in atoms if a["member_id"] == mid),
            "base_accrual_cents": base,
            "revaluation_delta_cents": reval,
            "accrued_cents": accrued,
            "election_id": el_id,
            "retirement_date": ret_date,
            "age_months": age,
            "early_months": early,
            "reduction_bps": red,
            "option_factor_bps": of,
            "payable_cents": payable,
        })
    events_out.sort(key=lambda e: (e["member_id"], e["event_date"], KIND_ORDER[e["event_kind"]], e["event_id"]))

    # ---------------- rollups ----------------
    rollups = []
    for pid in sorted(plans):
        rows = [b for b in benefits if b["plan_id"] == pid]
        rollups.append({
            "plan_id": pid,
            "member_count": len(rows),
            "credited_days": sum(b["credited_days"] for b in rows),
            "base_accrual_cents": sum(b["base_accrual_cents"] for b in rows),
            "revaluation_delta_cents": sum(b["revaluation_delta_cents"] for b in rows),
            "accrued_cents": sum(b["accrued_cents"] for b in rows),
            "payable_cents": sum(b["payable_cents"] for b in rows),
        })

    issues.sort(key=lambda i: (i["code"], i["record_id"]))
    exceptions = [dict(i) for i in issues]
    for b in benefits:
        if abs(b["payable_cents"]) >= material_cents:
            exceptions.append({"code": "MATERIAL_BENEFIT", "record_id": b["member_id"], "amount_cents": b["payable_cents"]})
    exceptions.sort(key=lambda i: (i["code"], i["record_id"]))

    # ---------------- audit ----------------
    prev = "0" * 64
    trace = []
    for b in benefits:
        h = hashlib.sha256((prev + canon(b)).encode("utf-8")).hexdigest()
        trace.append({"member_id": b["member_id"], "previous_hash": prev, "row_hash": h})
        prev = h

    # ---------------- manifest / quality ----------------
    input_files = []
    record_counts = {}
    for name in sorted(os.listdir(data_dir)):
        path = os.path.join(data_dir, name)
        if not os.path.isfile(path) or os.path.islink(path):
            continue
        with open(path, "rb") as fh:
            blob = fh.read()
        input_files.append({"name": name, "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)})
        if name.endswith(".jsonl"):
            record_counts[name] = sum(1 for ln in blob.decode("utf-8").splitlines() if ln.strip())
        elif name == "plans.json":
            record_counts[name] = len(plans_raw)

    write_report(out_dir, "manifest.json", {
        "engine_version": engine_version,
        "input_files": input_files,
        "valid_member_count": len(members),
        "effective_service_count": len(effective),
        "accrual_atom_count": len(atoms),
    })
    write_report(out_dir, "data_quality.json", {
        "input_file_count": len(input_files),
        "record_counts": record_counts,
        "issue_count": len(issues),
        "issues": issues,
    })
    write_report(out_dir, "service_ledger.json", {"revision_decisions": decisions, "effective_services": effective})
    write_report(out_dir, "accrual_ledger.json", {"atoms": atoms})
    write_report(out_dir, "cola_ledger.json", {"events": events_out})
    write_report(out_dir, "member_benefits.json", {"members": benefits})
    write_report(out_dir, "plan_rollups.json", {"plans": rollups})
    write_report(out_dir, "exception_register.json", {"exceptions": exceptions})
    write_report(out_dir, "audit_trace.json", {"rows": trace, "final_hash": prev})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
