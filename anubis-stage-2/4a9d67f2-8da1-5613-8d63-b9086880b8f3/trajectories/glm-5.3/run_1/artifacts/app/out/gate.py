#!/usr/bin/env python3
"""Inference gate: scores metered inference probes and rolls a shift up.

Usage:  python3 gate.py <input_dir> <output_dir>

Reads  runtimes.csv, variants.csv, callers.csv, endpoints.csv and probes.bin
from the input directory and writes verdicts.jsonl, endpoints.json,
precision.csv and shift.json into the output directory.

Every figure the stages apply is a recovered controller constant; nothing is
precomputed from any particular shift.  The recovered constants are grouped
below, with the ones the worked example pins exactly marked as such.
"""

import json
import os
import struct
import sys
from collections import OrderedDict

# ---------------------------------------------------------------- constants

GAIN = 1000                       # throughput normalisation gain (worked example)
SPAN_FACTOR = 4                   # spans governs -> width = spans * 4
REPLAY_OFFSET = 2                  # width *= (replays + 2)
BAND_SATURATE = 300                # score >= 300 -> saturate  (worked example)
BAND_HIGH = 150                   # score >= 150 -> high
BAND_BASE = 100                   # score >= 100 -> base, else idle
RESERVED_METER = -1                # meter value that never means a difference
SEGMENT_MODES = {"reset"}          # mode that opens a segment (restarts counters)
BUDGET_MODES = {"reset"}          # mode that reinstalls the budget
CLEAR_BACKLOG_MODES = {"drain"}    # mode that clears the backlog
CREDIT_MODES = {"refund"}          # mode that arms the one shot credit
CREDIT_DIVISOR = 2                 # armed credit halves the score
BACKLOG_CEILING = 1000             # backlog never passes this
SERVE_BACKLOG_DIV = 10             # serve backlog amount = width // 10
SERVE_STREAK_BONUS = 25            # a serve directly after a serve adds this
TRAILING_RECORD = 8                # how many recent probes the record keeps
SETUP_MODES = {"reset", "refund"}  # bookkeeping modes -> setup
VOID_MODES = {"abort"}             # abandoned probe -> void
COUNTED_VERDICTS = {"ok", "flagged", "rejected"}
QUARANTINE_STRIKES = 3             # strikes needed to quarantine
THROTTLE_BACKLOG = 500             # backlog_end above this throttles
PLAN_TOLERANCE = {"gold": 1000, "silver": 500, "bronze": 250, "trial": 100}
PRECISION_INHERITS_BASE = False    # charge the variant's own precision

# multiplicative response factors, as (numerator, denominator)
PREC_MULT = {"fp32": (1, 1), "fp16": (7, 8), "bf16": (1, 1), "int8": (3, 2)}
ACCEL_MULT = {"none": (1, 1), "cuda": (6, 5), "rocm": (1, 1), "npu": (1, 1),
              "xla": (4, 5), "wasm": (1, 3), "fpga": (1, 1)}
KERNEL_MULT = {"graph": (4, 5), "eager": (4, 5), "fused": (1, 1), "traced": (4, 5)}
PHASE_MULT = {"prefill": (1, 1), "decode": (9, 10), "batch": (1, 1)}

# additive response adjustments, keyed like the factors above
PREC_ADD = {"fp32": -3, "fp16": -3, "bf16": 9, "int8": 0}
ACCEL_ADD = {"none": 7, "cuda": 8, "rocm": -5, "npu": 15, "xla": 5,
             "wasm": 5, "fpga": 0}
KERNEL_ADD = {"graph": -4, "eager": -14, "fused": -3, "traced": 0}
PHASE_ADD = {"prefill": 0, "decode": -1, "batch": 15}

BANDS = ("saturate", "high", "base", "idle")


# ---------------------------------------------------------------- helpers

def trunc_div(a, b):
    """Integer division truncating towards zero."""
    q = abs(a) // abs(b)
    return -q if (a < 0) != (b < 0) else q


def clamp0(x):
    return x if x > 0 else 0


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return [dict(row) for row in __import__("csv").DictReader(fh)]


def decode_probes(path):
    """Decode probes.bin per wire-format.md."""
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) < 8 or data[:4] != b"PRBE":
        return []
    (count,) = struct.unpack_from("<I", data, 4)
    off = 8
    out = []
    for _ in range(count):
        seq, meter, rows, spans, replays = struct.unpack_from("<iiiii", data, off)
        off += 20
        vals = []
        for _ in range(5):
            n = data[off]
            off += 1
            vals.append(data[off:off + n].decode("utf-8"))
            off += n
        out.append({
            "seq": seq, "endpoint": vals[0], "tag": vals[1], "caller": vals[2],
            "mode": vals[3], "phase": vals[4],
            "meter": meter, "rows": rows, "spans": spans, "replays": replays,
        })
    return out


# ---------------------------------------------------------------- the gate

class Endpoint:
    def __init__(self, name, runtime, variant, accel, tier, floor, kernel, precision):
        self.name = name
        self.runtime = runtime
        self.variant = variant
        self.accel = accel
        self.tier = tier
        self.floor = floor
        self.kernel = kernel
        self.precision = precision
        self.budget = floor
        self.backlog = 0
        self.strikes = 0
        self.prev_was_serve = False
        self.credit = False
        self.trail = []          # most recent [tag, score] entries, oldest first
        self.counters = {}       # phase -> cumulative token counter
        self.last_meter = {}     # phase -> recovered meter of previous probe
        self.probes = 0
        self.flagged = 0
        self.strikes_total = 0
        self.bands = {b: 0 for b in BANDS}
        self.counted = 0
        self.score_total = 0
        self.top_score = 0
        self.top_tag = None
        self.backlog_end = 0
        self.budget_end = floor

    def charge_precision(self):
        return self.precision


def run_gate(in_dir):
    runtimes = {r["runtime"]: r for r in read_csv(os.path.join(in_dir, "runtimes.csv"))}
    variants = {v["variant"]: v for v in read_csv(os.path.join(in_dir, "variants.csv"))}
    callers = {c["caller"]: c for c in read_csv(os.path.join(in_dir, "callers.csv"))}
    endpoint_rows = read_csv(os.path.join(in_dir, "endpoints.csv"))
    probes = decode_probes(os.path.join(in_dir, "probes.bin"))

    def runtime_kernel(rt):
        row = runtimes.get(rt)
        return row["kernel"] if row else "graph"

    def runtime_floor(rt):
        row = runtimes.get(rt)
        try:
            return int(row["floor"]) if row else 0
        except (TypeError, ValueError):
            return 0

    def variant_precision(vr):
        row = variants.get(vr)
        if not row:
            return "fp32"
        prec = row["precision"] or ""
        if PRECISION_INHERITS_BASE and row.get("base"):
            base = variants.get(row["base"])
            if base:
                prec = base["precision"] or prec
        return prec

    endpoints = {}
    for row in endpoint_rows:
        name = row["endpoint"]
        endpoints[name] = Endpoint(
            name, row.get("runtime", ""), row.get("variant", ""),
            row.get("accel", "none"), row.get("tier", "1"),
            runtime_floor(row.get("runtime", "")),
            runtime_kernel(row.get("runtime", "")),
            variant_precision(row.get("variant", "")))

    order = sorted(probes, key=lambda p: p["seq"])
    verdicts = []
    running_score_sum = 0
    running_count = 0

    for probe in order:
        ep = endpoints.get(probe["endpoint"])
        if ep is None:
            ep = Endpoint(probe["endpoint"], "", "", "none", "1", 0, "graph", "fp32")
            endpoints[ep.name] = ep
        phase = probe["phase"]
        mode = probe["mode"]

        # ---- meter recovery -------------------------------------------
        if mode in SEGMENT_MODES:
            ep.counters = {}
            ep.last_meter = {}
        if probe["meter"] == RESERVED_METER:
            meter = ep.last_meter.get(phase, 0)
        else:
            if phase in ep.counters:
                ep.counters[phase] += probe["meter"]
            else:
                ep.counters[phase] = probe["meter"]
            meter = ep.counters[phase]
            ep.last_meter[phase] = meter

        # ---- 1/2. batch width and replay expansion -------------------
        if probe["spans"] != 0:
            width = probe["spans"] * SPAN_FACTOR
        else:
            width = probe["rows"]
        width *= probe["replays"] + REPLAY_OFFSET

        # ---- 3. warmup draw ------------------------------------------
        figure = clamp0(meter - ep.budget)

        # ---- 4. throughput normalisation ------------------------------
        figure = clamp0(trunc_div(figure * GAIN, width)) if width > 0 else 0

        # ---- 5-8. precision / accelerator / phase / kernel response --
        for mult, add, key in ((PREC_MULT, PREC_ADD, ep.charge_precision()),
                               (ACCEL_MULT, ACCEL_ADD, ep.accel),
                               (PHASE_MULT, PHASE_ADD, phase),
                               (KERNEL_MULT, KERNEL_ADD, ep.kernel)):
            n, d = mult.get(key, (1, 1))
            if n != d:
                figure = clamp0(trunc_div(figure * n, d))
            figure = clamp0(figure + add.get(key, 0))

        # ---- 9. backlog relief ----------------------------------------
        backlog_before = ep.backlog
        figure = clamp0(figure - backlog_before)

        # ---- 10. replay lookup ----------------------------------------
        for tag, score in reversed(ep.trail):
            if tag == probe["tag"]:
                figure = score
                break

        # ---- 11. credit ------------------------------------------------
        if ep.credit:
            figure = trunc_div(figure, CREDIT_DIVISOR)
            ep.credit = False

        score = figure

        # ---- 12. banding -----------------------------------------------
        if score >= BAND_SATURATE:
            band = "saturate"
        elif score >= BAND_HIGH:
            band = "high"
        elif score >= BAND_BASE:
            band = "base"
        else:
            band = "idle"

        # ---- 13. verdict -----------------------------------------------
        if mode in SETUP_MODES:
            verdict = "setup"
        elif mode in VOID_MODES:
            verdict = "void"
        elif band == "idle":
            verdict = "rejected"
        else:
            plan = "trial"
            crow = callers.get(probe["caller"])
            if crow:
                plan = crow["plan"]
            tolerance = PLAN_TOLERANCE.get(plan, 0)
            verdict = "flagged" if backlog_before > tolerance else "ok"

        # ---- 14. carry update -------------------------------------------
        if mode in BUDGET_MODES:
            ep.budget = (running_score_sum // running_count) // 10 if running_count else ep.floor
        if mode in CLEAR_BACKLOG_MODES:
            ep.backlog = 0
        if mode in CREDIT_MODES:
            ep.credit = True
        if mode == "serve":
            amount = width // SERVE_BACKLOG_DIV
            if ep.tier not in ("1", ""):
                amount *= 2
            if ep.prev_was_serve:
                amount += SERVE_STREAK_BONUS
            ep.backlog = min(ep.backlog + amount, BACKLOG_CEILING)
        ep.prev_was_serve = (mode == "serve")
        if verdict == "rejected":
            ep.strikes += 1
        ep.trail.append([probe["tag"], score])
        if len(ep.trail) > TRAILING_RECORD:
            ep.trail.pop(0)

        # ---- endpoint bookkeeping ---------------------------------------
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
        ep.strikes_total = ep.strikes
        ep.backlog_end = ep.backlog
        ep.budget_end = ep.budget

        running_score_sum += score
        running_count += 1

        verdicts.append(OrderedDict([
            ("backlog_before", backlog_before),
            ("band", band),
            ("caller", probe["caller"]),
            ("endpoint", probe["endpoint"]),
            ("mode", mode),
            ("phase", phase),
            ("score", score),
            ("seq", probe["seq"]),
            ("tag", probe["tag"]),
            ("verdict", verdict),
        ]))

    # ------------------------------------------------------------ rollups
    ep_rows = []
    for name in sorted(endpoints):
        ep = endpoints[name]
        if verdict["verdict"] if False else False:
            pass
        disposition = "clear"
        if ep.strikes >= QUARANTINE_STRIKES:
            disposition = "quarantine"
        elif ep.backlog_end > THROTTLE_BACKLOG:
            disposition = "throttle"
        ep_rows.append(OrderedDict([
            ("backlog_end", ep.backlog_end),
            ("bands", {b: ep.bands[b] for b in BANDS}),
            ("budget_end", ep.budget_end),
            ("counted", ep.counted),
            ("disposition", disposition),
            ("endpoint", name),
            ("flagged", ep.flagged),
            ("probes", ep.probes),
            ("score_total", ep.score_total),
            ("strikes", ep.strikes),
            ("top_score", ep.top_score),
            ("top_tag", ep.top_tag),
        ]))

    prec_rows = {}
    for name in sorted(endpoints):
        ep = endpoints[name]
        row = prec_rows.setdefault(ep.charge_precision(), [0, 0, 0, 0])
        row[0] += 1
        row[1] += ep.probes
        row[2] += ep.score_total
        row[3] += ep.flagged

    quarantined = [r["endpoint"] for r in ep_rows if r["disposition"] == "quarantine"]
    top_endpoint = None
    best = None
    for r in ep_rows:
        if best is None or r["score_total"] > best:
            best = r["score_total"]
            top_endpoint = r["endpoint"]

    by_band = {b: 0 for b in BANDS}
    by_verdict = {v: 0 for v in ("setup", "void", "rejected", "flagged", "ok")}
    for v in verdicts:
        by_band[v["band"]] += 1
        by_verdict[v["verdict"]] += 1

    shift = OrderedDict([
        ("by_band", by_band),
        ("by_verdict", by_verdict),
        ("endpoints", len(endpoints)),
        ("probes", len(verdicts)),
        ("quarantined", quarantined),
        ("score_total", sum(r["score_total"] for r in ep_rows)),
        ("top_endpoint", top_endpoint),
    ])

    return verdicts, ep_rows, prec_rows, shift


# ---------------------------------------------------------------- reports

def write_reports(out_dir, verdicts, ep_rows, prec_rows, shift):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "verdicts.jsonl"), "w", encoding="utf-8") as fh:
        for record in verdicts:
            fh.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            fh.write("\n")
    with open(os.path.join(out_dir, "endpoints.json"), "w", encoding="utf-8") as fh:
        doc = {"endpoints": [dict(r) for r in ep_rows]}
        fh.write(json.dumps(doc, sort_keys=True, indent=2))
        fh.write("\n")
    with open(os.path.join(out_dir, "precision.csv"), "w", encoding="utf-8") as fh:
        fh.write("precision,endpoints,probes,score_total,flagged\n")
        for prec in sorted(prec_rows):
            row = prec_rows[prec]
            fh.write("%s,%d,%d,%d,%d\n" % (prec, row[0], row[1], row[2], row[3]))
    with open(os.path.join(out_dir, "shift.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(shift), sort_keys=True, indent=2))
        fh.write("\n")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: gate.py <input_dir> <output_dir>\n")
        return 2
    verdicts, ep_rows, prec_rows, shift = run_gate(argv[1])
    write_reports(argv[2], verdicts, ep_rows, prec_rows, shift)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
