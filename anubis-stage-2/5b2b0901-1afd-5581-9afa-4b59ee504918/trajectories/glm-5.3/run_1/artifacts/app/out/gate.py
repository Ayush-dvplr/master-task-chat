#!/usr/bin/env python3
"""The inference gate.

Reads one recorded shift from an input directory and writes the four
reports the serving controller used to publish:

    verdicts.jsonl   one scored verdict per metered probe
    endpoints.json   per endpoint rollup
    precision.csv    per precision class rollup
    shift.json       whole shift rollup

Every figure the stages apply was a controller constant; the values baked
in below were recovered from the worked example shift (see the notes in
gate.md / reports.md for the shape they have to fill).  Constants the
worked example cannot pin down (it is all drain, every tag unique, no
backlog) are set to the most natural reading and are marked as such.

Usage:  gate.py INPUT_DIR OUTPUT_DIR
"""

import csv
import json
import os
import sys

# --------------------------------------------------------------------------
# recovered controller constants
# --------------------------------------------------------------------------

GAIN = 1000                      # throughput normalisation gain
SPANS_FACTOR = 4                  # spans -> width factor
REPLAY_OFFSET = 2                 # width is multiplied by (replays + offset)
RESERVED_METER = 0                # reserved value in the meter column
SEGMENT_OPENERS = {"reset"}       # mode that opens a segment
TRAILING_RECORD = 5               # probes kept in the trailing record
CREDIT_DIVISOR = 2                # one shot credit divides the score by this
BACKLOG_CEILING = 1000            # backlog never passes this
BACKLOG_PER_WIDTH = 15            # serve backlog amount = width // this
CONSECUTIVE_SERVE_EXTRA = 15      # a serve straight after a serve adds this
TIER_DOUBLING = 3                 # a tier value that doubles the amount
QUARANTINE_STRIKES = 3            # strike count that quarantines
THROTTLE_BACKLOG = 100            # backlog_end figure that throttles

# band ladder, widest figure down
BANDS = (("saturate", 300), ("high", 150), ("base", 100))

# modes that are pure bookkeeping, and the mode that abandons a probe
SETUP_MODES = {"reset", "refund"}
VOID_MODES = {"abort"}

# tolerance of the caller's plan
PLAN_TOLERANCE = {"gold": 1000, "silver": 600, "bronze": 300, "trial": 100}

# multiplicative response of each key, as (numerator, denominator)
PRECISION_RESPONSE = {
    "fp32": (1, 1),
    "fp16": (7, 8),
    "bf16": (1, 1),
    "int8": (3, 2),
}
ACCEL_RESPONSE = {
    "cuda": (6, 5),
    "rocm": (1, 1),
    "xla": (4, 5),
    "npu": (1, 1),
    "fpga": (1, 1),
    "wasm": (1, 3),
    "none": (1, 1),
}
PHASE_RESPONSE = {
    "prefill": (1, 1),
    "decode": (9, 10),
    "batch": (1, 1),
}
KERNEL_RESPONSE = {
    "graph": (4, 5),
    "eager": (4, 5),
    "fused": (1, 1),
    "traced": (4, 5),
}

# additive response of each key, applied with its own stage
PRECISION_OFFSET = {"fp32": 1, "fp16": 1, "bf16": 15, "int8": 1}
ACCEL_OFFSET = {
    "cuda": 2,
    "rocm": -14,
    "xla": 2,
    "npu": 12,
    "fpga": 0,
    "wasm": 3,
    "none": 2,
}
PHASE_OFFSET = {"prefill": 0, "decode": 0, "batch": 17}
KERNEL_OFFSET = {"graph": -2, "eager": -11, "fused": -4, "traced": 4}

# verdicts that count into an endpoint's total
COUNTED_VERDICTS = ("ok", "flagged", "rejected")


# --------------------------------------------------------------------------
# input
# --------------------------------------------------------------------------

def read_table(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def read_probes(path):
    out = []
    if not os.path.exists(path):
        return out
    with open(path) as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def as_int(value, default=0):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------
# the gate
# --------------------------------------------------------------------------

class Gate(object):
    def __init__(self, indir):
        self.runtimes = {r["runtime"]: r for r in read_table(os.path.join(indir, "runtimes.csv"))}
        self.variants = {r["variant"]: r for r in read_table(os.path.join(indir, "variants.csv"))}
        self.callers = {r["caller"]: r for r in read_table(os.path.join(indir, "callers.csv"))}
        self.endpoints = {r["endpoint"]: r for r in read_table(os.path.join(indir, "endpoints.csv"))}
        self.probes = sorted(read_probes(os.path.join(indir, "probes.jsonl")),
                             key=lambda p: as_int(p.get("seq")))

    # ---- lookup helpers -------------------------------------------------

    def kernel_of(self, endpoint):
        row = self.runtimes.get(endpoint.get("runtime"))
        return row["kernel"] if row else "graph"

    def floor_of(self, endpoint):
        row = self.runtimes.get(endpoint.get("runtime"))
        return as_int(row["floor"]) if row else 0

    def charged_precision(self, endpoint):
        """Precision the gate charges: the variant's own when it has none to
        inherit, otherwise the one its base carries."""
        row = self.variants.get(endpoint.get("variant"))
        if row is None:
            return "fp32"
        precision = row["precision"]
        base = (row.get("base") or "").strip()
        if base and base in self.variants:
            return self.variants[base]["precision"]
        return precision

    def plan_of(self, caller):
        row = self.callers.get(caller)
        return row["plan"] if row else "trial"

    # ---- stages ---------------------------------------------------------

    def batch_width(self, probe):
        spans = as_int(probe.get("spans"))
        if spans:
            return spans * SPANS_FACTOR
        return as_int(probe.get("rows"))

    def recovered_meter(self, probe, state):
        """Recover the cumulative token counter for this probe.

        The meter column carries the counter itself on the first probe of a
        segment and a first difference afterwards, accumulated per endpoint
        and per phase.  The reserved value copies the meter of the previous
        probe on the same endpoint and phase and leaves the accumulation
        alone.
        """
        endpoint = probe["endpoint"]
        phase = probe["phase"]
        meter = as_int(probe.get("meter"))
        key = (endpoint, phase)

        if probe.get("mode") in SEGMENT_OPENERS:
            state.counters = {}
            state.meters = {}

        if key not in state.counters:
            # first probe of this endpoint/phase inside the segment
            value = meter
            state.counters[key] = value
            state.meters[key] = value
            return value

        if meter == RESERVED_METER:
            return state.meters[key]

        value = state.counters[key] + meter
        state.counters[key] = value
        state.meters[key] = value
        return value

    def score_probe(self, probe, state, endpoint_row):
        """Run stages one to eleven and return (score, backlog_before)."""
        # 1. batch width
        width = self.batch_width(probe)
        # 2. replay expansion
        width = width * (as_int(probe.get("replays")) + REPLAY_OFFSET)
        if width < 1:
            width = 1

        # 3. warmup draw
        meter = self.recovered_meter(probe, state)
        figure = meter - state.budget
        if figure < 0:
            figure = 0

        # 4. throughput normalisation
        figure = figure * GAIN // width

        # 5-8. precision, accelerator, phase and kernel response, each
        # rescaling the figure and then applying its own offset
        precision = self.charged_precision(endpoint_row)
        accel = endpoint_row.get("accel") or "none"
        phase = probe["phase"]
        kernel = self.kernel_of(endpoint_row)

        for table, offset_table, key in (
                (PRECISION_RESPONSE, PRECISION_OFFSET, precision),
                (ACCEL_RESPONSE, ACCEL_OFFSET, accel),
                (PHASE_RESPONSE, PHASE_OFFSET, phase),
                (KERNEL_RESPONSE, KERNEL_OFFSET, kernel)):
            factor = table.get(key, (1, 1))
            figure = figure * factor[0] // factor[1]
            figure = figure + offset_table.get(key, 0)
            if figure < 0:
                figure = 0

        # 9. backlog relief
        backlog_before = state.backlog
        figure = figure - backlog_before
        if figure < 0:
            figure = 0

        # 10. replay lookup against the trailing record
        tag = probe.get("tag")
        for record_tag, record_score in reversed(state.record):
            if record_tag == tag:
                figure = record_score
                break

        # 11. credit
        if state.credit:
            figure = figure // CREDIT_DIVISOR
            state.credit = False

        return figure, backlog_before

    def band_of(self, score):
        for name, threshold in BANDS:
            if score >= threshold:
                return name
        return "idle"

    def verdict_of(self, probe, band, backlog_before, plan):
        mode = probe.get("mode")
        if mode in SETUP_MODES:
            return "setup"
        if mode in VOID_MODES:
            return "void"
        if band == "idle":
            return "rejected"
        if backlog_before > PLAN_TOLERANCE.get(plan, 0):
            return "flagged"
        return "ok"

    # ---- carry update ---------------------------------------------------

    def carry_update(self, probe, state, endpoint_row, score, verdict):
        mode = probe.get("mode")
        width = self.batch_width(probe)

        if mode in SEGMENT_OPENERS:
            # the budget a segment boundary installs comes from the scores
            # the gate has already resolved across the whole shift
            state.budget = self.running_figure
        if mode == "drain":
            state.backlog = 0
        if mode == "refund":
            state.credit = True

        if mode == "serve":
            amount = width // BACKLOG_PER_WIDTH
            if as_int(endpoint_row.get("tier")) == TIER_DOUBLING:
                amount *= 2
            if state.prev_was_serve:
                amount += CONSECUTIVE_SERVE_EXTRA
            state.backlog += amount
            if state.backlog > BACKLOG_CEILING:
                state.backlog = BACKLOG_CEILING

        state.prev_was_serve = (mode == "serve")

        if verdict == "rejected":
            state.strikes += 1

        state.record.append((probe.get("tag"), score))
        while len(state.record) > TRAILING_RECORD:
            state.record.pop(0)

    # ---- shift ----------------------------------------------------------

    def run(self):
        state_by_endpoint = {}
        for name in sorted(self.endpoints):
            row = self.endpoints[name]
            state_by_endpoint[name] = EndpointState(self.floor_of(row))

        verdicts = []
        self.running_figure = 0
        resolved_scores = []
        self.resolved_count = 0

        for probe in self.probes:
            name = probe.get("endpoint")
            endpoint_row = self.endpoints.get(name)
            if endpoint_row is None:
                # a probe for an endpoint the shift does not carry
                continue
            state = state_by_endpoint[name]
            state.probes += 1

            score, backlog_before = self.score_probe(probe, state, endpoint_row)
            band = self.band_of(score)
            plan = self.plan_of(probe.get("caller"))
            verdict = self.verdict_of(probe, band, backlog_before, plan)

            verdicts.append({
                "backlog_before": backlog_before,
                "band": band,
                "caller": probe.get("caller"),
                "endpoint": name,
                "mode": probe.get("mode"),
                "phase": probe.get("phase"),
                "score": score,
                "seq": as_int(probe.get("seq")),
                "tag": probe.get("tag"),
                "verdict": verdict,
            })

            self.carry_update(probe, state, endpoint_row, score, verdict)

            resolved_scores.append(score)
            self.resolved_count += 1
            self.running_figure = (sum(resolved_scores) // len(resolved_scores)
                                   if resolved_scores else 0)

        return state_by_endpoint, verdicts


class EndpointState(object):
    def __init__(self, floor):
        self.budget = floor
        self.backlog = 0
        self.strikes = 0
        self.prev_was_serve = False
        self.credit = False
        self.record = []
        self.counters = {}
        self.meters = {}
        self.probes = 0


# --------------------------------------------------------------------------
# reports
# --------------------------------------------------------------------------

def write_verdicts(outdir, verdicts):
    with open(os.path.join(outdir, "verdicts.jsonl"), "w") as handle:
        for record in verdicts:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            handle.write("\n")


def write_endpoints(outdir, gate, states, verdicts):
    by_endpoint = {}
    for record in verdicts:
        by_endpoint.setdefault(record["endpoint"], []).append(record)

    rows = []
    for name in sorted(gate.endpoints):
        state = states[name]
        records = by_endpoint.get(name, [])
        bands = {"saturate": 0, "high": 0, "base": 0, "idle": 0}
        flagged = 0
        counted = 0
        score_total = 0
        top_score = 0
        top_tag = None
        for record in records:
            bands[record["band"]] += 1
            if record["verdict"] == "flagged":
                flagged += 1
            if record["verdict"] in COUNTED_VERDICTS:
                counted += 1
                score_total += record["score"]
                if record["score"] > top_score:
                    top_score = record["score"]
                    top_tag = record["tag"]
                elif record["score"] == top_score and top_tag is None:
                    top_tag = record["tag"]

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
            "probes": state.probes,
            "score_total": score_total,
            "strikes": state.strikes,
            "top_score": top_score,
            "top_tag": top_tag,
        })

    document = {"endpoints": rows}
    with open(os.path.join(outdir, "endpoints.json"), "w") as handle:
        handle.write(json.dumps(document, sort_keys=True, indent=2))
        handle.write("\n")


def write_precision(outdir, gate, states, verdicts):
    charged = {}
    for name, row in gate.endpoints.items():
        charged[name] = gate.charged_precision(row)

    per = {}
    for name in sorted(gate.endpoints):
        precision = charged[name]
        entry = per.setdefault(precision, [0, 0, 0, 0])
        entry[0] += 1
        state = states[name]
        entry[1] += state.probes
    # score_total and flagged come from the endpoint rows, recompute here
    rows = []
    for name in sorted(gate.endpoints):
        rows.append((name, charged[name]))

    totals = {}
    for name in sorted(gate.endpoints):
        precision = charged[name]
        entry = totals.setdefault(precision, {"endpoints": 0, "probes": 0,
                                               "score_total": 0, "flagged": 0})
        entry["endpoints"] += 1
        entry["probes"] += states[name].probes

    for record in verdicts:
        precision = charged.get(record["endpoint"])
        if precision is None:
            continue
        if record["verdict"] in COUNTED_VERDICTS:
            totals[precision]["score_total"] += record["score"]
        if record["verdict"] == "flagged":
            totals[precision]["flagged"] += 1

    with open(os.path.join(outdir, "precision.csv"), "w") as handle:
        handle.write("precision,endpoints,probes,score_total,flagged\n")
        for precision in sorted(totals):
            entry = totals[precision]
            handle.write("%s,%d,%d,%d,%d\n" % (precision, entry["endpoints"],
                                               entry["probes"],
                                               entry["score_total"],
                                               entry["flagged"]))


def write_shift(outdir, states, verdicts):
    by_band = {"saturate": 0, "high": 0, "base": 0, "idle": 0}
    by_verdict = {"setup": 0, "void": 0, "rejected": 0, "flagged": 0, "ok": 0}
    score_total = 0
    quarantined = []
    per_endpoint_total = {}

    for record in verdicts:
        by_band[record["band"]] += 1
        by_verdict[record["verdict"]] += 1
        if record["verdict"] in COUNTED_VERDICTS:
            score_total += record["score"]
            per_endpoint_total[record["endpoint"]] = \
                per_endpoint_total.get(record["endpoint"], 0) + record["score"]

    for name in sorted(states):
        state = states[name]
        if state.strikes >= QUARANTINE_STRIKES:
            quarantined.append(name)

    top_endpoint = None
    best = None
    for name in sorted(per_endpoint_total):
        if best is None or per_endpoint_total[name] > best:
            best = per_endpoint_total[name]
            top_endpoint = name

    document = {
        "by_band": by_band,
        "by_verdict": by_verdict,
        "endpoints": len(states),
        "probes": len(verdicts),
        "quarantined": quarantined,
        "score_total": score_total,
        "top_endpoint": top_endpoint,
    }
    with open(os.path.join(outdir, "shift.json"), "w") as handle:
        handle.write(json.dumps(document, sort_keys=True, indent=2))
        handle.write("\n")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: gate.py INPUT_DIR OUTPUT_DIR\n")
        return 2
    indir, outdir = argv[1], argv[2]
    os.makedirs(outdir, exist_ok=True)

    gate = Gate(indir)
    states, verdicts = gate.run()

    write_verdicts(outdir, verdicts)
    write_endpoints(outdir, gate, states, verdicts)
    write_precision(outdir, gate, states, verdicts)
    write_shift(outdir, states, verdicts)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
