#!/usr/bin/env python3
"""Inference gate: score a shift of metered inference probes and roll it up.

Usage: gate.py INPUT_DIR OUTPUT_DIR
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

# ---- controller constants -------------------------------------------------
SPAN_FACTOR = 4          # spans is multiplied by this when it governs the batch width
REPLAY_OFFSET = 2        # the stored replay count plus this is the real count
GAIN = 800               # throughput normalisation gain
BAND_SATURATE = 300
BAND_HIGH = 150
BAND_BASE = 55
RESERVED_METER = 3       # meter value meaning "same meter as the previous probe"
COARSE_ACCEL = "fpga"
COARSE_SCALE = 1000      # the fpga meter is recorded a thousandth-scale coarse
COARSE_DIV = False       # True => divide, False => multiply
SEGMENT_MODE = "reset"    # opens a segment and reinstalls the budget
CLEAR_MODE = "drain"     # clears the backlog
CREDIT_MODE = "refund"   # arms the one shot credit
CREDIT_DIVISOR = 2
SETUP_MODES = ("reset", "refund")
VOID_MODE = "abort"
BACKLOG_DIVISOR = 15     # serve adds batch width // this
TIER_DOUBLE = 2          # this tier value doubles the backlog amount
BACKLOG_BONUS = 49       # a serve directly after a serve adds this
BACKLOG_CAP = 420
TRAILING = 4
PLAN_TOLERANCE = {"gold": 60, "silver": 38, "bronze": 17, "trial": 0}
COUNTED_VERDICTS = ("ok", "flagged", "rejected")
QUARANTINE_STRIKES = 3
THROTTLE_BACKLOG = 40
INHERIT_PRECISION = True  # charge the precision of the variant's base when it has one

PRECISION_RESPONSE = {
    "fp32": (1, 1, 0), "fp16": (9, 10, 0), "bf16": (1, 1, 5), "int8": (5, 3, 0),
}
ACCEL_RESPONSE = {
    "none": (1, 1, 0), "cuda": (7, 6, 0), "rocm": (1, 1, -11), "wasm": (1, 2, 0),
    "xla": (2, 3, 0), "npu": (1, 1, 15), "fpga": (1, 1, 0),
}
PHASE_RESPONSE = {"prefill": (1, 1, 0), "decode": (5, 6, 0), "batch": (1, 1, 19)}
KERNEL_RESPONSE = {"graph": (1, 1, 0), "eager": (1, 1, -12), "fused": (4, 3, 0), "traced": (1, 1, 4)}


def apply_op(figure, op):
    num, den, add = op
    value = figure * num // den + add
    return value if value > 0 else 0


def read_csv(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def load_shift(indir):
    runtimes = {r["runtime"]: r for r in read_csv(os.path.join(indir, "runtimes.csv"))}
    variants = {r["variant"]: r for r in read_csv(os.path.join(indir, "variants.csv"))}
    callers = {r["caller"]: r for r in read_csv(os.path.join(indir, "callers.csv"))}
    endpoints = {r["endpoint"]: r for r in read_csv(os.path.join(indir, "endpoints.csv"))}
    probes = []
    with open(os.path.join(indir, "probes.jsonl")) as fh:
        for line in fh:
            line = line.strip()
            if line:
                probes.append(json.loads(line))
    probes.sort(key=lambda p: p["seq"])
    return runtimes, variants, callers, endpoints, probes


def charged_precision(variant, variants):
    base = variants[variant]["base"]
    if base and INHERIT_PRECISION:
        return variants[base]["precision"]
    return variants[variant]["precision"]


def resolve_shift(runtimes, variants, callers, endpoints, probes):
    state = {}
    for eid, ep in endpoints.items():
        state[eid] = {
            "budget": int(runtimes[ep["runtime"]]["floor"]),
            "backlog": 0,
            "strikes": 0,
            "prev_serve": False,
            "credit": False,
            "record": [],
            "counters": {},
            "last_meter": {},
        }
    running_total = 0
    resolved = 0
    records = []
    for probe in probes:
        eid = probe["endpoint"]
        ep = endpoints[eid]
        st = state[eid]
        phase = probe["phase"]
        key = (eid, phase)
        mode = probe["mode"]
        meter = probe["meter"]
        if key not in st["counters"] or mode == SEGMENT_MODE:
            st["counters"][key] = meter
            recovered = meter
        elif meter == RESERVED_METER:
            recovered = st["last_meter"].get(key, meter)
        else:
            st["counters"][key] += meter
            recovered = st["counters"][key]
        st["last_meter"][key] = recovered
        if ep["accel"] == COARSE_ACCEL:
            if COARSE_DIV:
                recovered = recovered // COARSE_SCALE
            elif COARSE_SCALE != 1:
                recovered = recovered * COARSE_SCALE
        width = probe["spans"] * SPAN_FACTOR if probe["spans"] > 0 else probe["rows"]
        full_width = width * (probe["replays"] + REPLAY_OFFSET)
        figure = recovered - st["budget"]
        if figure < 0:
            figure = 0
        figure = figure * GAIN // full_width
        if figure < 0:
            figure = 0
        figure = apply_op(figure, PRECISION_RESPONSE[charged_precision(ep["variant"], variants)])
        figure = apply_op(figure, ACCEL_RESPONSE.get(ep["accel"], (1, 1, 0)))
        figure = apply_op(figure, PHASE_RESPONSE.get(phase, (1, 1, 0)))
        figure = apply_op(figure, KERNEL_RESPONSE.get(runtimes[ep["runtime"]]["kernel"], (1, 1, 0)))
        backlog_before = st["backlog"]
        figure -= backlog_before
        if figure < 0:
            figure = 0
        record = st["record"]
        for tag, score in reversed(record):
            if tag == probe["tag"]:
                figure = score
                break
        if st["credit"]:
            figure //= CREDIT_DIVISOR
            if figure < 0:
                figure = 0
            st["credit"] = False
        if figure >= BAND_SATURATE:
            band = "saturate"
        elif figure >= BAND_HIGH:
            band = "high"
        elif figure >= BAND_BASE:
            band = "base"
        else:
            band = "idle"
        if mode in SETUP_MODES:
            verdict = "setup"
        elif mode == VOID_MODE:
            verdict = "void"
        elif band == "idle":
            verdict = "rejected"
        elif backlog_before > PLAN_TOLERANCE.get(callers[probe["caller"]]["plan"], 0):
            verdict = "flagged"
        else:
            verdict = "ok"
        records.append({
            "backlog_before": backlog_before,
            "band": band,
            "caller": probe["caller"],
            "endpoint": eid,
            "mode": mode,
            "phase": phase,
            "score": figure,
            "seq": probe["seq"],
            "tag": probe["tag"],
            "verdict": verdict,
        })
        running_total += figure
        resolved += 1
        if mode == SEGMENT_MODE:
            st["budget"] = running_total // resolved
        if mode == CLEAR_MODE:
            st["backlog"] = 0
        if mode == CREDIT_MODE:
            st["credit"] = True
        if mode == "serve":
            amount = width // BACKLOG_DIVISOR
            if int(ep["tier"]) == TIER_DOUBLE:
                amount *= 2
            st["backlog"] += amount
            if st["prev_serve"]:
                st["backlog"] += BACKLOG_BONUS
            if st["backlog"] > BACKLOG_CAP:
                st["backlog"] = BACKLOG_CAP
        if verdict == "rejected":
            st["strikes"] += 1
        record.append((probe["tag"], figure))
        if len(record) > TRAILING:
            del record[0]
        st["prev_serve"] = mode == "serve"
    return records, state


def write_reports(records, state, endpoints, variants, outdir):
    per = defaultdict(lambda: {
        "probes": 0, "flagged": 0, "bands": Counter(), "scored": []})
    by_band = Counter()
    by_verdict = Counter()
    for rec in records:
        entry = per[rec["endpoint"]]
        entry["probes"] += 1
        entry["bands"][rec["band"]] += 1
        by_band[rec["band"]] += 1
        by_verdict[rec["verdict"]] += 1
        if rec["verdict"] == "flagged":
            entry["flagged"] += 1
        if rec["verdict"] in COUNTED_VERDICTS:
            entry["scored"].append((rec["seq"], rec["score"], rec["tag"]))
    rows = []
    for eid in sorted(endpoints):
        entry = per.get(eid) or {"probes": 0, "flagged": 0, "bands": Counter(), "scored": []}
        st = state[eid]
        scored = entry["scored"]
        if scored:
            best = scored[0]
            for item in scored:
                if item[1] > best[1]:
                    best = item
            top_score, top_tag = best[1], best[2]
        else:
            top_score, top_tag = 0, None
        strikes = st["strikes"]
        backlog_end = st["backlog"]
        if strikes >= QUARANTINE_STRIKES:
            disposition = "quarantine"
        elif backlog_end > THROTTLE_BACKLOG:
            disposition = "throttle"
        else:
            disposition = "clear"
        rows.append({
            "backlog_end": backlog_end,
            "bands": {b: entry["bands"].get(b, 0) for b in ("base", "high", "idle", "saturate")},
            "budget_end": st["budget"],
            "counted": len(scored),
            "disposition": disposition,
            "endpoint": eid,
            "flagged": entry["flagged"],
            "probes": entry["probes"],
            "score_total": sum(item[1] for item in scored),
            "strikes": strikes,
            "top_score": top_score,
            "top_tag": top_tag,
        })
    with open(os.path.join(outdir, "verdicts.jsonl"), "w") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")
    with open(os.path.join(outdir, "endpoints.json"), "w") as fh:
        fh.write(json.dumps({"endpoints": rows}, sort_keys=True, indent=2) + "\n")
    per_precision = defaultdict(lambda: {"endpoints": 0, "probes": 0, "score_total": 0, "flagged": 0})
    prec_of = {eid: charged_precision(ep["variant"], variants) for eid, ep in endpoints.items()}
    for eid in sorted(endpoints):
        per_precision[prec_of[eid]]["endpoints"] += 1
    total_by_ep = {r["endpoint"]: r["score_total"] for r in rows}
    for rec in records:
        bucket = per_precision[prec_of[rec["endpoint"]]]
        bucket["probes"] += 1
        if rec["verdict"] == "flagged":
            bucket["flagged"] += 1
    for prec, bucket in per_precision.items():
        bucket["score_total"] = sum(
            total_by_ep[eid] for eid in endpoints if prec_of[eid] == prec)
    with open(os.path.join(outdir, "precision.csv"), "w") as fh:
        fh.write("precision,endpoints,probes,score_total,flagged\n")
        for prec in sorted(per_precision):
            b = per_precision[prec]
            fh.write("%s,%d,%d,%d,%d\n" % (prec, b["endpoints"], b["probes"], b["score_total"], b["flagged"]))
    top_endpoint = None
    for row in rows:
        if top_endpoint is None or row["score_total"] > top_endpoint[1]:
            top_endpoint = (row["endpoint"], row["score_total"])
    shift = {
        "by_band": {b: by_band.get(b, 0) for b in ("base", "high", "idle", "saturate")},
        "by_verdict": {v: by_verdict.get(v, 0) for v in ("flagged", "ok", "rejected", "setup", "void")},
        "endpoints": len(endpoints),
        "probes": len(records),
        "quarantined": sorted(r["endpoint"] for r in rows if r["disposition"] == "quarantine"),
        "score_total": sum(r["score_total"] for r in rows),
        "top_endpoint": top_endpoint[0] if top_endpoint else None,
    }
    with open(os.path.join(outdir, "shift.json"), "w") as fh:
        fh.write(json.dumps(shift, sort_keys=True, indent=2) + "\n")


def main():
    if len(sys.argv) != 3:
        sys.stderr.write("usage: gate.py INPUT_DIR OUTPUT_DIR\n")
        return 2
    indir, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    runtimes, variants, callers, endpoints, probes = load_shift(indir)
    records, state = resolve_shift(runtimes, variants, callers, endpoints, probes)
    write_reports(records, state, endpoints, variants, outdir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
