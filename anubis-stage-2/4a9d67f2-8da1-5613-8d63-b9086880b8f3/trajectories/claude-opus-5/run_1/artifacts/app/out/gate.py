#!/usr/bin/env python3
"""The inference gate: scores metered inference probes and rolls a shift up.

Usage: gate.py <input-dir> <output-dir>
"""
import csv
import json
import os
import struct
import sys

# ---------------------------------------------------------------- constants
GAIN = 800
SPAN_FACTOR = 4
REPLAY_OFFSET = 2

PRECISION_ADJ = {
    "fp32": ("mul", 1, 1),
    "bf16": ("add", 11),
    "fp16": ("mul", 7, 8),
    "int8": ("mul", 3, 2),
}
ACCEL_ADJ = {
    "none": ("mul", 1, 1),
    "cuda": ("mul", 6, 5),
    "rocm": ("add", -13),
    "xla": ("mul", 4, 5),
    "npu": ("add", 8),
    "fpga": ("mul", 1, 1),
    "wasm": ("mul", 1, 3),
}
PHASE_ADJ = {
    "prefill": ("mul", 1, 1),
    "decode": ("mul", 9, 10),
    "batch": ("add", 14),
}
KERNEL_ADJ = {
    "graph": ("mul", 1, 1),
    "eager": ("add", -9),
    "fused": ("mul", 5, 4),
    "traced": ("add", 6),
}

COARSE_ACCEL = "fpga"
COARSE_SCALE = 10
RESERVED_METER = -1
SEGMENT_MODE = "reset"
CHARGE_BASE_PRECISION = True

TRAIL_LEN = 4
CREDIT_DIVISOR = 2

BAND_SATURATE = 300
BAND_HIGH = 150
BAND_BASE = 55
BANDS = ("saturate", "high", "base", "idle")
VERDICTS = ("setup", "void", "rejected", "flagged", "ok")

PLAN_TOLERANCE = {"gold": 60, "silver": 38, "bronze": 17, "trial": 0}

BACKLOG_DIVISOR = 30
BACKLOG_DOUBLE_TIER = 3
SERVE_STREAK_BONUS = 9
BACKLOG_CEILING = 120

COUNTED_VERDICTS = ("ok", "flagged")
QUARANTINE_STRIKES = 3
THROTTLE_BACKLOG = 41


def adjust(value, spec):
    if spec[0] == "mul":
        value = value * spec[1] // spec[2]
    else:
        value = value + spec[1]
    return value if value > 0 else 0


# ------------------------------------------------------------------- inputs
def read_table(path, key):
    with open(path, newline="", encoding="utf-8") as fh:
        return {row[key]: row for row in csv.DictReader(fh)}


def read_probes(path):
    with open(path, "rb") as fh:
        blob = fh.read()
    if blob[:4] != b"PRBE":
        raise ValueError("not a probe file")
    (count,) = struct.unpack_from("<I", blob, 4)
    off = 8
    out = []
    for _ in range(count):
        ints = struct.unpack_from("<5i", blob, off)
        off += 20
        text = []
        for _ in range(5):
            size = blob[off]
            off += 1
            text.append(blob[off:off + size].decode("utf-8"))
            off += size
        out.append({
            "seq": ints[0], "meter": ints[1], "rows": ints[2],
            "spans": ints[3], "replays": ints[4],
            "endpoint": text[0], "tag": text[1], "caller": text[2],
            "mode": text[3], "phase": text[4],
        })
    return out


class Endpoint:
    __slots__ = ("name", "floor", "kernel", "accel", "tier", "precision",
                 "budget", "backlog", "strikes", "prev_serve", "credit",
                 "trail", "counter", "last_meter", "probes", "flagged",
                 "counted", "score_total", "top_score", "top_tag", "bands")

    def __init__(self, name, floor, kernel, accel, tier, precision):
        self.name = name
        self.floor = floor
        self.kernel = kernel
        self.accel = accel
        self.tier = tier
        self.precision = precision
        self.budget = floor
        self.backlog = 0
        self.strikes = 0
        self.prev_serve = False
        self.credit = False
        self.trail = []
        self.counter = {}
        self.last_meter = {}
        self.probes = 0
        self.flagged = 0
        self.counted = 0
        self.score_total = 0
        self.top_score = 0
        self.top_tag = None
        self.bands = {b: 0 for b in BANDS}


def run(indir):
    runtimes = read_table(os.path.join(indir, "runtimes.csv"), "runtime")
    variants = read_table(os.path.join(indir, "variants.csv"), "variant")
    callers = read_table(os.path.join(indir, "callers.csv"), "caller")
    rows = read_table(os.path.join(indir, "endpoints.csv"), "endpoint")
    probes = read_probes(os.path.join(indir, "probes.bin"))

    state = {}
    for name, row in rows.items():
        rt = runtimes[row["runtime"]]
        var = variants[row["variant"]]
        if CHARGE_BASE_PRECISION and var["base"]:
            precision = variants[var["base"]]["precision"]
        else:
            precision = var["precision"]
        state[name] = Endpoint(name, int(rt["floor"]), rt["kernel"],
                               row["accel"], int(row["tier"]), precision)

    verdicts = []
    running_total = 0
    running_count = 0

    for probe in sorted(probes, key=lambda p: p["seq"]):
        ep = state[probe["endpoint"]]
        phase = probe["phase"]
        mode = probe["mode"]

        # recover the meter
        if mode == SEGMENT_MODE:
            ep.counter = {}
            ep.last_meter = {}
        raw = probe["meter"]
        if raw == RESERVED_METER and phase in ep.last_meter:
            meter = ep.last_meter[phase]
        else:
            meter = ep.counter.get(phase, 0) + raw
            ep.counter[phase] = meter
        ep.last_meter[phase] = meter
        if ep.accel == COARSE_ACCEL:
            meter *= COARSE_SCALE

        # 1 batch width
        if probe["spans"] != 0:
            width = probe["spans"] * SPAN_FACTOR
        else:
            width = probe["rows"]
        if width < 0:
            width = 0
        # 2 replay expansion
        width = width * (probe["replays"] + REPLAY_OFFSET)
        if width < 0:
            width = 0
        # 3 warmup draw
        value = meter - ep.budget
        if value < 0:
            value = 0
        # 4 throughput normalisation
        value = value * GAIN // width if width else 0
        if value < 0:
            value = 0
        # 5-8 responses
        value = adjust(value, PRECISION_ADJ[ep.precision])
        value = adjust(value, ACCEL_ADJ[ep.accel])
        value = adjust(value, PHASE_ADJ[phase])
        value = adjust(value, KERNEL_ADJ[ep.kernel])
        # 9 backlog relief
        backlog_before = ep.backlog
        value -= backlog_before
        if value < 0:
            value = 0
        # 10 replay lookup
        for tag, score in reversed(ep.trail):
            if tag == probe["tag"]:
                value = score
                break
        # 11 credit
        if ep.credit:
            value = value // CREDIT_DIVISOR
            if value < 0:
                value = 0
            ep.credit = False
        score = value

        # 12 banding
        if score >= BAND_SATURATE:
            band = "saturate"
        elif score >= BAND_HIGH:
            band = "high"
        elif score >= BAND_BASE:
            band = "base"
        else:
            band = "idle"

        # 13 verdict
        if mode in ("reset", "refund"):
            verdict = "setup"
        elif mode == "abort":
            verdict = "void"
        elif band == "idle":
            verdict = "rejected"
        elif backlog_before > PLAN_TOLERANCE[callers[probe["caller"]]["plan"]]:
            verdict = "flagged"
        else:
            verdict = "ok"

        verdicts.append({
            "backlog_before": backlog_before,
            "band": band,
            "caller": probe["caller"],
            "endpoint": probe["endpoint"],
            "mode": mode,
            "phase": phase,
            "score": score,
            "seq": probe["seq"],
            "tag": probe["tag"],
            "verdict": verdict,
        })

        # 14 carry update
        running_total += score
        running_count += 1
        if mode == "reset":
            ep.budget = running_total // running_count
        elif mode == "drain":
            ep.backlog = 0
        elif mode == "refund":
            ep.credit = True
        if mode == "serve":
            amount = width // BACKLOG_DIVISOR
            if ep.tier == BACKLOG_DOUBLE_TIER:
                amount *= 2
            if ep.prev_serve:
                amount += SERVE_STREAK_BONUS
            ep.backlog += amount
            if ep.backlog > BACKLOG_CEILING:
                ep.backlog = BACKLOG_CEILING
        ep.prev_serve = (mode == "serve")
        if verdict == "rejected":
            ep.strikes += 1
        ep.trail.append((probe["tag"], score))
        if len(ep.trail) > TRAIL_LEN:
            del ep.trail[0]

        # rollup
        ep.probes += 1
        ep.bands[band] += 1
        if verdict == "flagged":
            ep.flagged += 1
        if verdict in COUNTED_VERDICTS:
            ep.counted += 1
            ep.score_total += score
            if score > ep.top_score or (score == ep.top_score and ep.top_tag is None):
                ep.top_score = score
                ep.top_tag = probe["tag"]

    return state, verdicts


def build_reports(state, verdicts):
    ep_rows = []
    for name in sorted(state):
        ep = state[name]
        if ep.strikes >= QUARANTINE_STRIKES:
            disposition = "quarantine"
        elif ep.backlog >= THROTTLE_BACKLOG:
            disposition = "throttle"
        else:
            disposition = "clear"
        ep_rows.append({
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

    prec = {}
    for name in sorted(state):
        ep = state[name]
        row = prec.setdefault(ep.precision,
                              {"endpoints": 0, "probes": 0, "score_total": 0,
                               "flagged": 0})
        row["endpoints"] += 1
        row["probes"] += ep.probes
        row["score_total"] += ep.score_total
        row["flagged"] += ep.flagged

    by_band = {b: 0 for b in BANDS}
    by_verdict = {v: 0 for v in VERDICTS}
    for rec in verdicts:
        by_band[rec["band"]] += 1
        by_verdict[rec["verdict"]] += 1
    top_endpoint = None
    best = None
    for row in ep_rows:
        if best is None or row["score_total"] > best:
            best = row["score_total"]
            top_endpoint = row["endpoint"]
    shift = {
        "by_band": by_band,
        "by_verdict": by_verdict,
        "endpoints": len(ep_rows),
        "probes": len(verdicts),
        "quarantined": sorted(r["endpoint"] for r in ep_rows
                              if r["disposition"] == "quarantine"),
        "score_total": sum(r["score_total"] for r in ep_rows),
        "top_endpoint": top_endpoint,
    }
    return ep_rows, prec, shift


def write_reports(outdir, verdicts, ep_rows, prec, shift):
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "verdicts.jsonl"), "w", encoding="utf-8",
              newline="") as fh:
        for rec in verdicts:
            fh.write(json.dumps(rec, sort_keys=True, separators=(",", ":")))
            fh.write("\n")
    with open(os.path.join(outdir, "endpoints.json"), "w", encoding="utf-8",
              newline="") as fh:
        fh.write(json.dumps({"endpoints": ep_rows}, sort_keys=True, indent=2))
        fh.write("\n")
    with open(os.path.join(outdir, "precision.csv"), "w", encoding="utf-8",
              newline="") as fh:
        fh.write("precision,endpoints,probes,score_total,flagged\n")
        for name in sorted(prec):
            row = prec[name]
            fh.write("%s,%d,%d,%d,%d\n" % (name, row["endpoints"],
                                           row["probes"], row["score_total"],
                                           row["flagged"]))
    with open(os.path.join(outdir, "shift.json"), "w", encoding="utf-8",
              newline="") as fh:
        fh.write(json.dumps(shift, sort_keys=True, indent=2))
        fh.write("\n")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: gate.py <input-dir> <output-dir>\n")
        return 2
    state, verdicts = run(argv[1])
    ep_rows, prec, shift = build_reports(state, verdicts)
    write_reports(argv[2], verdicts, ep_rows, prec, shift)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
