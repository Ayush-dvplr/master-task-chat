#!/usr/bin/env python3
"""The inference gate: scores a shift of metered inference probes."""
import csv
import json
import os
import sys
from collections import deque

SPAN_FACTOR = 4
REPLAY_OFFSET = 2
GAIN = 800
RESERVED_METER = -1
COARSE_ACCEL = "fpga"
COARSE_SCALE = 10
CHARGE_INHERITED_PRECISION = False

PRECISION_ADJ = {"bf16": ("add", 7), "fp16": ("mul", 5, 6), "int8": ("mul", 4, 3)}
ACCEL_ADJ = {
    "rocm": ("add", -17),
    "npu": ("add", 12),
    "cuda": ("mul", 5, 4),
    "xla": ("mul", 3, 4),
    "wasm": ("mul", 1, 4),
}
PHASE_ADJ = {"decode": ("mul", 4, 5), "batch": ("add", 9)}
KERNEL_ADJ = {"eager": ("add", -7), "fused": ("mul", 6, 5), "traced": ("add", 11)}

BAND_SATURATE = 300
BAND_HIGH = 150
BAND_BASE = 55

SEGMENT_MODE = "reset"
BACKLOG_CLEAR_MODE = "drain"
CREDIT_MODE = "refund"
VOID_MODE = "abort"
SETUP_MODES = ("reset", "refund")
CREDIT_DIVISOR = 2

TRAIL_SIZE = 4
BACKLOG_DIVISOR = 30
DOUBLE_TIER = 3
CONSECUTIVE_SERVE = 9
BACKLOG_CEILING = 200
PLAN_TOLERANCE = {"gold": 60, "silver": 38, "bronze": 17, "trial": 0}

QUARANTINE_STRIKES = 3
THROTTLE_BACKLOG = 40
COUNTED_VERDICTS = ("ok", "flagged")

BANDS = ("saturate", "high", "base", "idle")
VERDICTS = ("setup", "void", "rejected", "flagged", "ok")


def read_table(path, key):
    if not os.path.exists(path):
        return {}
    with open(path, newline="", encoding="utf-8") as fh:
        return {row[key]: row for row in csv.DictReader(fh)}


def read_probes(path):
    probes = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    probes.append(json.loads(line))
    probes.sort(key=lambda p: p["seq"])
    return probes


def apply_adj(adj, value):
    if adj is None:
        return value
    if adj[0] == "add":
        value = value + adj[1]
    else:
        value = value * adj[1] // adj[2]
    return value if value > 0 else 0


def band_of(score):
    if score >= BAND_SATURATE:
        return "saturate"
    if score >= BAND_HIGH:
        return "high"
    if score >= BAND_BASE:
        return "base"
    return "idle"


class Endpoint:
    def __init__(self, row, runtime, variant):
        self.name = row["endpoint"]
        self.tier = int(row["tier"])
        self.accel = row["accel"]
        self.kernel = runtime["kernel"]
        self.precision = variant["precision"]
        self.budget = int(runtime["floor"])
        self.backlog = 0
        self.strikes = 0
        self.prev_serve = False
        self.credit = False
        self.trail = deque(maxlen=TRAIL_SIZE)
        self.meters = {}
        self.last = {}
        self.probes = 0
        self.counted = 0
        self.flagged = 0
        self.score_total = 0
        self.top_score = 0
        self.top_tag = None
        self.bands = {b: 0 for b in BANDS}


def resolve(indir):
    runtimes = read_table(os.path.join(indir, "runtimes.csv"), "runtime")
    variants = read_table(os.path.join(indir, "variants.csv"), "variant")
    callers = read_table(os.path.join(indir, "callers.csv"), "caller")
    rows = read_table(os.path.join(indir, "endpoints.csv"), "endpoint")
    probes = read_probes(os.path.join(indir, "probes.jsonl"))

    state = {}
    for name, row in rows.items():
        variant = variants[row["variant"]]
        if CHARGE_INHERITED_PRECISION and variant.get("base"):
            variant = variants[variant["base"]]
        state[name] = Endpoint(row, runtimes[row["runtime"]], variant)

    verdicts = []
    running_total = 0
    running_count = 0

    for probe in probes:
        ep = state[probe["endpoint"]]
        phase = probe["phase"]
        mode = probe["mode"]

        if mode == SEGMENT_MODE:
            ep.meters.clear()

        meter = probe["meter"]
        if meter == RESERVED_METER:
            recovered = ep.last.get(phase, 0)
        else:
            recovered = ep.meters.get(phase, 0) + meter
            ep.meters[phase] = recovered
        ep.last[phase] = recovered
        if ep.accel == COARSE_ACCEL:
            recovered *= COARSE_SCALE

        width = probe["rows"] if probe["spans"] == 0 else probe["spans"] * SPAN_FACTOR
        width *= probe["replays"] + REPLAY_OFFSET

        figure = recovered - ep.budget
        if figure < 0:
            figure = 0
        figure = figure * GAIN // width if width else 0
        if figure < 0:
            figure = 0
        figure = apply_adj(PRECISION_ADJ.get(ep.precision), figure)
        figure = apply_adj(ACCEL_ADJ.get(ep.accel), figure)
        figure = apply_adj(PHASE_ADJ.get(phase), figure)
        figure = apply_adj(KERNEL_ADJ.get(ep.kernel), figure)

        backlog_before = ep.backlog
        figure -= backlog_before
        if figure < 0:
            figure = 0

        tag = probe["tag"]
        for old_tag, old_score in reversed(ep.trail):
            if old_tag == tag:
                figure = old_score
                break

        if ep.credit:
            figure //= CREDIT_DIVISOR
            ep.credit = False

        score = figure
        band = band_of(score)

        if mode in SETUP_MODES:
            verdict = "setup"
        elif mode == VOID_MODE:
            verdict = "void"
        elif band == "idle":
            verdict = "rejected"
        elif backlog_before > PLAN_TOLERANCE[callers[probe["caller"]]["plan"]]:
            verdict = "flagged"
        else:
            verdict = "ok"

        verdicts.append(
            {
                "backlog_before": backlog_before,
                "band": band,
                "caller": probe["caller"],
                "endpoint": probe["endpoint"],
                "mode": mode,
                "phase": phase,
                "score": score,
                "seq": probe["seq"],
                "tag": tag,
                "verdict": verdict,
            }
        )

        running_total += score
        running_count += 1

        if mode == SEGMENT_MODE:
            ep.budget = running_total // running_count
        if mode == BACKLOG_CLEAR_MODE:
            ep.backlog = 0
        if mode == CREDIT_MODE:
            ep.credit = True
        if mode == "serve":
            amount = width // BACKLOG_DIVISOR
            if ep.tier == DOUBLE_TIER:
                amount *= 2
            if ep.prev_serve:
                amount += CONSECUTIVE_SERVE
            ep.backlog = min(ep.backlog + amount, BACKLOG_CEILING)
        ep.prev_serve = mode == "serve"
        if verdict == "rejected":
            ep.strikes += 1
        ep.trail.append((tag, score))

        ep.probes += 1
        ep.bands[band] += 1
        if verdict == "flagged":
            ep.flagged += 1
        if verdict in COUNTED_VERDICTS:
            ep.counted += 1
            ep.score_total += score
            if ep.top_tag is None or score > ep.top_score or (score == ep.top_score and tag < ep.top_tag):
                ep.top_score = score
                ep.top_tag = tag

    return state, verdicts


def disposition(ep):
    if ep.strikes >= QUARANTINE_STRIKES:
        return "quarantine"
    if ep.backlog > THROTTLE_BACKLOG:
        return "throttle"
    return "clear"


def write_reports(outdir, state, verdicts):
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "verdicts.jsonl"), "w", encoding="utf-8") as fh:
        for record in verdicts:
            fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")

    rows = []
    for name in sorted(state):
        ep = state[name]
        rows.append(
            {
                "backlog_end": ep.backlog,
                "bands": dict(ep.bands),
                "budget_end": ep.budget,
                "counted": ep.counted,
                "disposition": disposition(ep),
                "endpoint": ep.name,
                "flagged": ep.flagged,
                "probes": ep.probes,
                "score_total": ep.score_total,
                "strikes": ep.strikes,
                "top_score": ep.top_score,
                "top_tag": ep.top_tag,
            }
        )
    with open(os.path.join(outdir, "endpoints.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"endpoints": rows}, sort_keys=True, indent=2) + "\n")

    per = {}
    for name in sorted(state):
        ep = state[name]
        acc = per.setdefault(ep.precision, [0, 0, 0, 0])
        acc[0] += 1
        acc[1] += ep.probes
        acc[2] += ep.score_total
        acc[3] += ep.flagged
    with open(os.path.join(outdir, "precision.csv"), "w", encoding="utf-8") as fh:
        fh.write("precision,endpoints,probes,score_total,flagged\n")
        for precision in sorted(per):
            acc = per[precision]
            fh.write("%s,%d,%d,%d,%d\n" % (precision, acc[0], acc[1], acc[2], acc[3]))

    by_band = {b: 0 for b in BANDS}
    by_verdict = {v: 0 for v in VERDICTS}
    for record in verdicts:
        by_band[record["band"]] += 1
        by_verdict[record["verdict"]] += 1
    top_endpoint = None
    best = None
    for name in sorted(state):
        total = state[name].score_total
        if best is None or total > best:
            best = total
            top_endpoint = name
    shift = {
        "by_band": by_band,
        "by_verdict": by_verdict,
        "endpoints": len(state),
        "probes": len(verdicts),
        "quarantined": sorted(n for n in state if disposition(state[n]) == "quarantine"),
        "score_total": sum(state[n].score_total for n in state),
        "top_endpoint": top_endpoint,
    }
    with open(os.path.join(outdir, "shift.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(shift, sort_keys=True, indent=2) + "\n")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: gate.py INPUT_DIR OUTPUT_DIR\n")
        return 2
    state, verdicts = resolve(argv[1])
    write_reports(argv[2], state, verdicts)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
