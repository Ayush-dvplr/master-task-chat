#!/usr/bin/env python3
"""Rebuilt inference gate.

Reads a shift (runtimes.csv, variants.csv, callers.csv, endpoints.csv,
probes.jsonl) from the input directory and writes the four reports
(verdicts.jsonl, endpoints.json, precision.csv, shift.json) into the output
directory in the byte form reports.md describes.

usage: gate.py <input-dir> <output-dir>
"""

import csv
import json
import os
import sys

# ---------------------------------------------------------------- constants
# Recovered controller constants.  Everything below was reconstructed from the
# worked example shift; nothing here depends on a particular shift.

SPAN_FACTOR = 4          # stage 1: factor applied when `spans` governs
REPLAY_OFFSET = 2        # stage 2: offset stored in the `replays` column
GAIN = 1000              # stage 4: throughput normalisation gain

COARSE_ACCEL = "fpga"    # the accelerator metering on a coarser scale
COARSE_SCALE = 1000      # tokens per unit of that coarser scale

RESERVED_METER = -1      # meter value that never means a difference

PRECISION_RESPONSE = {"fp32": 86, "fp16": 76, "bf16": 86, "int8": 139}
ACCEL_RESPONSE = {"cuda": 140, "rocm": 103, "xla": 80, "npu": 108,
                  "fpga": 100, "wasm": 60, "none": 105}
PHASE_RESPONSE = {"prefill": 96, "decode": 80, "batch": 101}
KERNEL_RESPONSE = {"graph": 93, "eager": 79, "fused": 125, "traced": 84}

CHARGE_INHERITED_PRECISION = True   # a variant with a base is charged its base

SEGMENT_MODE = "reset"              # opens a segment, reinstalls the budget
BACKLOG_CLEAR_MODE = "drain"
CREDIT_MODE = "refund"
SERVE_MODE = "serve"
ABORT_MODE = "abort"
SETUP_MODES = ("reset", "refund")

RECORD_LEN = 4           # probes kept in an endpoint's trailing record
CREDIT_DIVISOR = 2       # stage 11: the one shot credit's division

BUDGET_DIVISOR = 100     # a segment installs running score total // this
SERVE_BACKLOG_DIVISOR = 10   # serve backlog amount = batch width // this
DOUBLING_TIER = 3        # tier whose serve backlog amount is doubled
SERVE_STREAK_BONUS = 25  # serve directly after a serve on the same endpoint
BACKLOG_CAP = 2000

BAND_SATURATE = 300
BAND_HIGH = 150
BAND_BASE = 75

PLAN_TOLERANCE = {"gold": 300, "silver": 200, "bronze": 100, "trial": 50}

COUNTED_VERDICTS = ("ok", "flagged")
QUARANTINE_STRIKES = 3
THROTTLE_BACKLOG = 300

BANDS = ("saturate", "high", "base", "idle")
VERDICTS = ("setup", "void", "rejected", "flagged", "ok")


# -------------------------------------------------------------------- input
def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as handle:
        return [row for row in csv.DictReader(handle)]


def read_probes(path):
    probes = []
    if not os.path.exists(path):
        return probes
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                probes.append(json.loads(line))
    probes.sort(key=lambda row: row["seq"])
    return probes


def load(indir):
    runtimes = {r["runtime"]: r for r in read_csv(os.path.join(indir, "runtimes.csv"))}
    variants = {r["variant"]: r for r in read_csv(os.path.join(indir, "variants.csv"))}
    callers = {r["caller"]: r for r in read_csv(os.path.join(indir, "callers.csv"))}
    endpoints = {r["endpoint"]: r for r in read_csv(os.path.join(indir, "endpoints.csv"))}
    probes = read_probes(os.path.join(indir, "probes.jsonl"))
    return runtimes, variants, callers, endpoints, probes


def charged_precision(variants, variant):
    row = variants[variant]
    base = (row.get("base") or "").strip()
    if CHARGE_INHERITED_PRECISION and base and base in variants:
        return variants[base]["precision"]
    return row["precision"]


# ------------------------------------------------------------------- engine
class EndpointState:
    __slots__ = ("budget", "backlog", "strikes", "prev_serve", "credit",
                 "record", "meters", "last")

    def __init__(self, budget):
        self.budget = budget
        self.backlog = 0
        self.strikes = 0
        self.prev_serve = False
        self.credit = False
        self.record = []          # trailing (tag, score) pairs, oldest first
        self.meters = {}          # phase -> running counter
        self.last = {}            # phase -> last recovered meter


def clamp(value):
    return value if value > 0 else 0


def scale(value, percent):
    return clamp(value * percent // 100)


def band_of(score):
    if score >= BAND_SATURATE:
        return "saturate"
    if score >= BAND_HIGH:
        return "high"
    if score >= BAND_BASE:
        return "base"
    return "idle"


def resolve(runtimes, variants, callers, endpoints, probes):
    states = {}
    for name, row in endpoints.items():
        floor = int(runtimes[row["runtime"]]["floor"])
        states[name] = EndpointState(floor)

    records = []
    running_total = 0

    for probe in probes:
        name = probe["endpoint"]
        endpoint = endpoints[name]
        runtime = runtimes[endpoint["runtime"]]
        state = states[name]
        mode = probe["mode"]
        phase = probe["phase"]

        # the meter column: accumulate to recover the counter
        if mode == SEGMENT_MODE:
            state.meters.clear()
            state.last.clear()
        if probe["meter"] == RESERVED_METER:
            recovered = state.last.get(phase, 0)
        else:
            recovered = state.meters.get(phase, 0) + probe["meter"]
            state.meters[phase] = recovered
        state.last[phase] = recovered
        if endpoint["accel"] == COARSE_ACCEL:
            recovered *= COARSE_SCALE

        # 1. batch width, 2. replay expansion
        if probe["spans"] == 0:
            width = probe["rows"]
        else:
            width = probe["spans"] * SPAN_FACTOR
        width = clamp(width * (probe["replays"] + REPLAY_OFFSET))

        # 3. warmup draw, 4. throughput normalisation
        figure = clamp(recovered - state.budget)
        figure = clamp(figure * GAIN // width) if width else 0

        # 5..8 the four responses
        figure = scale(figure, PRECISION_RESPONSE[charged_precision(variants, endpoint["variant"])])
        figure = scale(figure, ACCEL_RESPONSE[endpoint["accel"]])
        figure = scale(figure, PHASE_RESPONSE[phase])
        figure = scale(figure, KERNEL_RESPONSE[runtime["kernel"]])

        # 9. backlog relief
        backlog_before = state.backlog
        figure = clamp(figure - backlog_before)

        # 10. replay lookup
        for tag, score in reversed(state.record):
            if tag == probe["tag"]:
                figure = score
                break

        # 11. credit
        if state.credit:
            figure = clamp(figure // CREDIT_DIVISOR)
            state.credit = False
        score = figure

        # 12. banding
        band = band_of(score)

        # 13. verdict
        if mode in SETUP_MODES:
            verdict = "setup"
        elif mode == ABORT_MODE:
            verdict = "void"
        elif band == "idle":
            verdict = "rejected"
        elif backlog_before > PLAN_TOLERANCE[callers[probe["caller"]]["plan"]]:
            verdict = "flagged"
        else:
            verdict = "ok"

        records.append({
            "backlog_before": backlog_before,
            "band": band,
            "caller": probe["caller"],
            "endpoint": name,
            "mode": mode,
            "phase": phase,
            "score": score,
            "seq": probe["seq"],
            "tag": probe["tag"],
            "verdict": verdict,
        })
        running_total += score

        # 14. carry update
        if mode == SEGMENT_MODE:
            state.budget = clamp(running_total // BUDGET_DIVISOR)
        if mode == BACKLOG_CLEAR_MODE:
            state.backlog = 0
        if mode == CREDIT_MODE:
            state.credit = True
        if mode == SERVE_MODE:
            amount = width // SERVE_BACKLOG_DIVISOR
            if int(endpoint["tier"]) == DOUBLING_TIER:
                amount *= 2
            if state.prev_serve:
                amount += SERVE_STREAK_BONUS
            state.backlog = min(state.backlog + amount, BACKLOG_CAP)
        if verdict == "rejected":
            state.strikes += 1
        state.record.append((probe["tag"], score))
        if len(state.record) > RECORD_LEN:
            del state.record[0]
        state.prev_serve = (mode == SERVE_MODE)

    return records, states


# ------------------------------------------------------------------ reports
def endpoint_rows(endpoints, states, records):
    per = {name: [] for name in endpoints}
    for rec in records:
        per[rec["endpoint"]].append(rec)

    rows = []
    for name in sorted(endpoints):
        mine = per[name]
        state = states[name]
        bands = {band: 0 for band in BANDS}
        flagged = 0
        counted = 0
        score_total = 0
        top_score = 0
        top_tag = None
        for rec in mine:
            bands[rec["band"]] += 1
            if rec["verdict"] == "flagged":
                flagged += 1
            if rec["verdict"] in COUNTED_VERDICTS:
                counted += 1
                score_total += rec["score"]
                if rec["score"] > top_score or top_tag is None:
                    top_score = rec["score"]
                    top_tag = rec["tag"]
        if state.strikes >= QUARANTINE_STRIKES:
            disposition = "quarantine"
        elif state.backlog >= THROTTLE_BACKLOG:
            disposition = "throttle"
        else:
            disposition = "clear"
        rows.append({
            "backlog_end": state.backlog,
            "bands": bands,
            "budget_end": state.budget,
            "counted": counted,
            "disposition": disposition,
            "endpoint": name,
            "flagged": flagged,
            "probes": len(mine),
            "score_total": score_total,
            "strikes": state.strikes,
            "top_score": top_score,
            "top_tag": top_tag,
        })
    return rows


def precision_rows(endpoints, variants, rows):
    by = {}
    for row in rows:
        name = row["endpoint"]
        prec = charged_precision(variants, endpoints[name]["variant"])
        slot = by.setdefault(prec, [0, 0, 0, 0])
        slot[0] += 1
        slot[1] += row["probes"]
        slot[2] += row["score_total"]
        slot[3] += row["flagged"]
    return [(prec, by[prec]) for prec in sorted(by)]


def write_reports(outdir, records, rows, precision, endpoints):
    os.makedirs(outdir, exist_ok=True)

    with open(os.path.join(outdir, "verdicts.jsonl"), "w", encoding="utf-8") as handle:
        for rec in records:
            handle.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")

    with open(os.path.join(outdir, "endpoints.json"), "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"endpoints": rows}, sort_keys=True, indent=2) + "\n")

    with open(os.path.join(outdir, "precision.csv"), "w", encoding="utf-8") as handle:
        handle.write("precision,endpoints,probes,score_total,flagged\n")
        for prec, slot in precision:
            handle.write("%s,%d,%d,%d,%d\n" % (prec, slot[0], slot[1], slot[2], slot[3]))

    by_band = {band: 0 for band in BANDS}
    by_verdict = {verdict: 0 for verdict in VERDICTS}
    for rec in records:
        by_band[rec["band"]] += 1
        by_verdict[rec["verdict"]] += 1
    quarantined = sorted(r["endpoint"] for r in rows if r["disposition"] == "quarantine")
    top_endpoint = None
    best = None
    for row in rows:
        if best is None or row["score_total"] > best:
            best = row["score_total"]
            top_endpoint = row["endpoint"]
    shift = {
        "by_band": by_band,
        "by_verdict": by_verdict,
        "endpoints": len(endpoints),
        "probes": len(records),
        "quarantined": quarantined,
        "score_total": sum(r["score_total"] for r in rows),
        "top_endpoint": top_endpoint,
    }
    with open(os.path.join(outdir, "shift.json"), "w", encoding="utf-8") as handle:
        handle.write(json.dumps(shift, sort_keys=True, indent=2) + "\n")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: gate.py <input-dir> <output-dir>\n")
        return 2
    indir, outdir = argv[1], argv[2]
    runtimes, variants, callers, endpoints, probes = load(indir)
    records, states = resolve(runtimes, variants, callers, endpoints, probes)
    rows = endpoint_rows(endpoints, states, records)
    write_reports(outdir, records, rows, precision_rows(endpoints, variants, rows), endpoints)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
