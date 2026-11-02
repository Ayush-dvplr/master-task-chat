#!/usr/bin/env python3
"""The inference gate: scores metered inference probes and rolls a shift up.

Usage: gate.py <input_dir> <output_dir>

Every figure the stages apply was a controller constant that was never written
down. The constants below were recovered from the worked example shift.

Recovered with confidence from the worked example:
  - the batch width rule, the replay offset and the throughput gain
  - the within-stage multiplier ratios of stages 5-8
  - the band thresholds (example base max 109, high 155..281, saturate min 307)

Marked UNRESOLVED below: constants the worked example cannot observe, because
every one of its 130 probes is a `drain` probe resolving to `ok` with
backlog_before == 0, and because it never uses the fpga accelerator or a
variant that names a base. Those values are reasoned guesses.
"""
import csv
import json
import os
import sys
from collections import deque

BANDS = ("saturate", "high", "base", "idle")
VERDICTS = ("setup", "void", "rejected", "flagged", "ok")

# ---------------------------------------------------------------- stages 1-4
SPAN_IDLE = 0            # the spans value that hands control back to rows
SPAN_FACTOR = 4          # factor applied when spans governs the width
REPLAY_OFFSET = 2        # offset stored in the replays column
GAIN = 1000              # throughput gain; the division truncates

# ---------------------------------------------------------------- stages 5-8
# Each key carries (numerator, denominator, offset) applied as
#     u = max(0, u * num // den + off)
# in the order precision, accelerator, phase, kernel. The multiplier ratios are
# forced by the example groups that fit exactly; the offsets are the best fit
# found for the example and are not exact.
PRECISION_ADJ = {
    "fp32": (1, 1, -40),
    "bf16": (1, 1, -26),
    "fp16": (7, 8, -40),
    "int8": (3, 2, -39),
}
ACCEL_ADJ = {
    "none": (1, 1, 28),
    "rocm": (1, 1, 12),
    "npu": (1, 1, 38),
    "cuda": (6, 5, 36),
    "xla": (4, 5, 20),
    "wasm": (1, 3, 1),
    "fpga": (1, 1, 0),   # UNRESOLVED: absent from the worked example
}
PHASE_ADJ = {
    "batch": (1, 1, 4),
    "prefill": (1, 1, -14),
    "decode": (9, 10, -15),
}
KERNEL_ADJ = {
    "fused": (1, 1, 25),
    "graph": (4, 5, 21),
    "eager": (4, 5, 12),
    "traced": (4, 5, 27),
}

# ------------------------------------------------------------------ the meter
# UNRESOLVED: fpga is the only accelerator the worked example never uses, so it
# is the coarse one by elimination, but its scale is observable nowhere.
COARSE_ACCEL = "fpga"
COARSE_SCALE = 1
# UNRESOLVED: -1 is the only sentinel-looking meter value in the recorded shift
# too small to be a plausible first difference.
RESERVED_METER = -1
SEGMENT_MODE = "reset"

# --------------------------------------------------------------- stages 11-13
CREDIT_DIVISOR = 2
BAND_SATURATE = 300
BAND_HIGH = 150
BAND_BASE = 100
SETUP_MODES = ("reset", "refund")
VOID_MODES = ("abort",)
# UNRESOLVED: every example probe carries backlog_before == 0, so the ladder's
# tolerances are never exercised.
PLAN_TOLERANCE = {"gold": 0, "silver": 20, "bronze": 40, "trial": 60}

# -------------------------------------------------- stage 14 and the rollups
# UNRESOLVED: the example holds only drain probes with an empty backlog, so
# none of the carry update or the dispositions are observable there.
BACKLOG_MODE = "drain"
CREDIT_MODE = "refund"
BACKLOG_DIVISOR = 10
DOUBLE_TIER = "3"
REPEAT_SERVE_ADD = 5
BACKLOG_CEILING = 500
TRAIL_LEN = 3
QUARANTINE_STRIKES = 3
THROTTLE_BACKLOG = 200
COUNTED_VERDICTS = ("ok", "flagged")
# UNRESOLVED: no example variant names a base.
CHARGE_INHERITED_PRECISION = False


def read_table(path, key):
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        return {row[key]: row for row in csv.DictReader(fh)}


def read_probes(path):
    probes = []
    if not os.path.exists(path):
        return probes
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                probes.append(json.loads(line))
    probes.sort(key=lambda p: p["seq"])
    return probes


def clamp(value):
    return value if value > 0 else 0


def apply_adj(value, table, key):
    adj = table.get(key)
    if adj is None:
        return value
    num, den, off = adj
    return clamp(value * num // den + off)


def charged_precision(variant, variants):
    row = variants.get(variant)
    if row is None:
        return None
    if CHARGE_INHERITED_PRECISION and row.get("base"):
        parent = variants.get(row["base"])
        if parent is not None:
            return parent["precision"]
    return row["precision"]


class Endpoint:
    def __init__(self, row, runtimes):
        runtime = runtimes.get(row.get("runtime", ""), {})
        self.row = row
        self.kernel = runtime.get("kernel", "")
        self.budget = int(runtime.get("floor", 0) or 0)
        self.backlog = 0
        self.strikes = 0
        self.prev_serve = False
        self.credit = False
        self.trail = deque(maxlen=TRAIL_LEN)
        self.meters = {}
        self.last_meter = {}
        self.probes = 0
        self.flagged = 0
        self.counted = 0
        self.score_total = 0
        self.top_score = 0
        self.top_tag = None
        self.bands = {b: 0 for b in BANDS}


def resolve(indir):
    runtimes = read_table(os.path.join(indir, "runtimes.csv"), "runtime")
    variants = read_table(os.path.join(indir, "variants.csv"), "variant")
    callers = read_table(os.path.join(indir, "callers.csv"), "caller")
    ep_rows = read_table(os.path.join(indir, "endpoints.csv"), "endpoint")
    probes = read_probes(os.path.join(indir, "probes.jsonl"))

    state = {name: Endpoint(row, runtimes) for name, row in ep_rows.items()}
    records = []
    running = 0

    for probe in probes:
        name = probe["endpoint"]
        if name not in state:
            state[name] = Endpoint(
                {"endpoint": name, "runtime": "", "variant": "",
                 "accel": "none", "tier": "1"}, runtimes)
        ep = state[name]
        phase = probe["phase"]
        mode = probe["mode"]
        accel = ep.row.get("accel", "none")
        precision = charged_precision(ep.row.get("variant", ""), variants)

        if mode == SEGMENT_MODE:
            ep.meters.clear()

        raw = probe["meter"]
        if raw == RESERVED_METER:
            meter = ep.last_meter.get(phase, 0)
        else:
            meter = ep.meters.get(phase, 0) + raw
            ep.meters[phase] = meter
        ep.last_meter[phase] = meter
        if accel == COARSE_ACCEL:
            meter *= COARSE_SCALE

        spans = probe["spans"]
        width = probe["rows"] if spans == SPAN_IDLE else spans * SPAN_FACTOR
        width = clamp(clamp(width) * (probe["replays"] + REPLAY_OFFSET))

        value = clamp(meter - ep.budget)
        value = clamp(value * GAIN // width) if width else 0
        value = apply_adj(value, PRECISION_ADJ, precision)
        value = apply_adj(value, ACCEL_ADJ, accel)
        value = apply_adj(value, PHASE_ADJ, phase)
        value = apply_adj(value, KERNEL_ADJ, ep.kernel)

        backlog_before = ep.backlog
        value = clamp(value - backlog_before)

        for tag, prior in reversed(ep.trail):
            if tag == probe["tag"]:
                value = prior
                break

        if ep.credit:
            value = clamp(value // CREDIT_DIVISOR)
            ep.credit = False
        score = value

        if score >= BAND_SATURATE:
            band = "saturate"
        elif score >= BAND_HIGH:
            band = "high"
        elif score >= BAND_BASE:
            band = "base"
        else:
            band = "idle"

        if mode in SETUP_MODES:
            verdict = "setup"
        elif mode in VOID_MODES:
            verdict = "void"
        elif band == "idle":
            verdict = "rejected"
        elif backlog_before > PLAN_TOLERANCE.get(
                callers.get(probe["caller"], {}).get("plan", ""), 0):
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

        running += score
        if mode == SEGMENT_MODE:
            ep.budget = running
        if mode == BACKLOG_MODE:
            ep.backlog = 0
        if mode == CREDIT_MODE:
            ep.credit = True
        if mode == "serve":
            add = width // BACKLOG_DIVISOR
            if ep.row.get("tier") == DOUBLE_TIER:
                add *= 2
            if ep.prev_serve:
                add += REPEAT_SERVE_ADD
            ep.backlog = min(ep.backlog + add, BACKLOG_CEILING)
        ep.prev_serve = mode == "serve"
        if verdict == "rejected":
            ep.strikes += 1
        ep.trail.append((probe["tag"], score))

        ep.probes += 1
        ep.bands[band] += 1
        if verdict == "flagged":
            ep.flagged += 1
        if verdict in COUNTED_VERDICTS:
            ep.counted += 1
            ep.score_total += score
            if score > ep.top_score:
                ep.top_score = score
                ep.top_tag = probe["tag"]

    return state, records, variants


def endpoint_rows(state):
    rows = []
    for name in sorted(state):
        ep = state[name]
        if ep.strikes >= QUARANTINE_STRIKES:
            disposition = "quarantine"
        elif ep.backlog >= THROTTLE_BACKLOG:
            disposition = "throttle"
        else:
            disposition = "clear"
        rows.append({
            "backlog_end": ep.backlog,
            "bands": dict(ep.bands),
            "budget_end": ep.budget,
            "counted": ep.counted,
            "disposition": disposition,
            "endpoint": name,
            "flagged": ep.flagged,
            "probes": ep.probes,
            "score_total": ep.score_total,
            "strikes": ep.strikes,
            "top_score": ep.top_score,
            "top_tag": ep.top_tag,
        })
    return rows


def write_reports(outdir, state, records, variants):
    os.makedirs(outdir, exist_ok=True)
    rows = endpoint_rows(state)

    with open(os.path.join(outdir, "verdicts.jsonl"), "w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, sort_keys=True, separators=(",", ":")) + "\n")

    with open(os.path.join(outdir, "endpoints.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"endpoints": rows}, sort_keys=True, indent=2) + "\n")

    buckets = {}
    for row in rows:
        ep = state[row["endpoint"]]
        precision = charged_precision(ep.row.get("variant", ""), variants)
        if precision is None:
            continue
        acc = buckets.setdefault(precision, [0, 0, 0, 0])
        acc[0] += 1
        acc[1] += row["probes"]
        acc[2] += row["score_total"]
        acc[3] += row["flagged"]
    with open(os.path.join(outdir, "precision.csv"), "w", encoding="utf-8") as fh:
        fh.write("precision,endpoints,probes,score_total,flagged\n")
        for precision in sorted(buckets):
            acc = buckets[precision]
            fh.write("%s,%d,%d,%d,%d\n" % (precision, acc[0], acc[1], acc[2], acc[3]))

    by_band = {b: 0 for b in BANDS}
    by_verdict = {v: 0 for v in VERDICTS}
    for rec in records:
        by_band[rec["band"]] += 1
        by_verdict[rec["verdict"]] += 1

    top_endpoint = None
    best = None
    for row in rows:
        if best is None or row["score_total"] > best:
            best = row["score_total"]
            top_endpoint = row["endpoint"]

    shift = {
        "by_band": by_band,
        "by_verdict": by_verdict,
        "endpoints": len(rows),
        "probes": len(records),
        "quarantined": sorted(r["endpoint"] for r in rows
                              if r["disposition"] == "quarantine"),
        "score_total": sum(r["score_total"] for r in rows),
        "top_endpoint": top_endpoint,
    }
    with open(os.path.join(outdir, "shift.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(shift, sort_keys=True, indent=2) + "\n")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: gate.py <input_dir> <output_dir>\n")
        return 2
    state, records, variants = resolve(argv[1])
    write_reports(argv[2], state, records, variants)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
