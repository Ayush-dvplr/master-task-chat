#!/usr/bin/env python3
"""Inference gate.

Usage:  gate.py INPUT_DIR OUTPUT_DIR

Reads runtimes.csv, variants.csv, callers.csv, endpoints.csv, probes.jsonl from
INPUT_DIR and writes verdicts.jsonl, endpoints.json, precision.csv, shift.json
into OUTPUT_DIR.

Only the Python standard library is used.  All figures are worked out from the
input files at run time; nothing about any particular shift is precomputed.

CONSTANTS
---------
The constants below were recovered from the worked example
(example_probes.jsonl + example_verdicts.jsonl).  Those marked [example] are
pinned by that evidence; those marked [guess] could not be pinned by it (the
example does not exercise them) and are best estimates.
"""

import csv
import json
import os
import sys
from collections import defaultdict, deque
from fractions import Fraction

# ---------------------------------------------------------------- constants

# Stage 1/2: batch width and replay expansion.  [example]
SPAN_FACTOR = 4          # spans governs when non-zero and is multiplied by this
REPLAY_OFFSET = 2         # the width is multiplied by (replays + this)

# Stage 3: warmup draw.  The budget starts at the runtime floor.  [example]
SEGMENT_MODE = "serve"    # the mode that opens a segment [example: not drain]
RESERVED_METER = 0        # reserved meter value: carry the previous meter
COARSE_ACCEL = None       # accelerator recording on a coarser scale [guess]
COARSE_SCALE = 1          # tokens per recorded unit for that accelerator

# Stage 4: throughput normalisation.  [example]
GAIN = Fraction(800)      # the one fixed gain

# Stages 5-8: response adjustments.  Each is a multiplier; a value absent from
# the table leaves the figure alone.  [example]
PRECISION_FACTOR = {"int8": Fraction(8, 5)}
ACCEL_FACTOR = {"cuda": Fraction(5), "xla": Fraction(3)}
PHASE_FACTOR = {"decode": Fraction(4, 5)}
KERNEL_FACTOR = {"eager": Fraction(1, 4), "traced": Fraction(5, 24)}

# Stages 5-8: the additive part of each response.  [example: approximate; the
# worked example pins these only up to about +/-2]
PRECISION_ADJ = {"bf16": 7, "fp32": 0, "fp16": 0, "int8": 0}
ACCEL_ADJ = {"none": 0, "npu": 12, "rocm": -17, "cuda": 0, "xla": 0,
             "wasm": 0, "fpga": 0}
PHASE_ADJ = {"prefill": 0, "decode": -1, "batch": 9}
KERNEL_ADJ = {"graph": 0, "eager": -7, "fused": 0, "traced": 11}

# Stage 12: banding.  [example: thresholds lie in (52,80], (146,163], (297,302]]
IDLE_BELOW = 60
BASE_BELOW = 150
HIGH_BELOW = 300

# Stage 13: verdict ladder.  [guess: the example never flags a probe]
PLAN_TOLERANCE = {"gold": 300, "silver": 200, "bronze": 100, "trial": 50}
VOID_MODE = "abort"                     # the abandoned probe [example]
SETUP_MODES = ("reset", "refund")       # the two bookkeeping modes [guess]

# Stage 11: the one shot credit.  [guess]
CREDIT_DIVISOR = 2

# Stage 10: the trailing record.  [guess]
TRAILING_SIZE = 4

# Stage 14: carry update.  [guess]
BACKLOG_PER_WIDTH = Fraction(1, 4)   # a serve adds width/4 to the backlog
BACKLOG_TIER_DOUBLE = True           # a tier value doubles that amount
BACKLOG_REPEAT_BONUS = 50            # a serve following a serve adds this
BACKLOG_CEILING = 100000
CREDIT_ARM_MODE = "refund"           # the mode that arms the credit
BACKLOG_CLEAR_MODE = "drain"         # the mode that clears the backlog
BUDGET_MODE = "reset"                # the mode that reinstalls the budget

# Rollups.  [guess]
COUNTED_VERDICTS = ("ok",)           # verdicts counted into the endpoint totals
QUARANTINE_STRIKES = 3               # strikes that quarantine an endpoint
THROTTLE_BACKLOG = 500               # backlog that throttles an endpoint

BAND_ORDER = ("saturate", "high", "base", "idle")
VERDICT_ORDER = ("setup", "void", "rejected", "flagged", "ok")


# ---------------------------------------------------------------- input

def read_csv_rows(path):
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def read_probes(path):
    probes = []
    with open(path) as handle:
        for line in handle:
            line = line.strip()
            if line:
                probes.append(json.loads(line))
    probes.sort(key=lambda rec: rec["seq"])
    return probes


# ---------------------------------------------------------------- gate

class Gate:
    def __init__(self, indir):
        self.runtimes = {row["runtime"]: row for row in read_csv_rows(os.path.join(indir, "runtimes.csv"))}
        self.variants = {row["variant"]: row for row in read_csv_rows(os.path.join(indir, "variants.csv"))}
        self.callers = {row["caller"]: row for row in read_csv_rows(os.path.join(indir, "callers.csv"))}
        self.endpoints = {row["endpoint"]: row for row in read_csv_rows(os.path.join(indir, "endpoints.csv"))}
        self.probes = read_probes(os.path.join(indir, "probes.jsonl"))

    # -- precision the gate charges a variant at --------------------------
    def charged_precision(self, variant):
        row = self.variants[variant]
        return row["precision"] if not row["base"] else self.variants[row["base"]]["precision"]

    # -- stage 1/2 --------------------------------------------------------
    @staticmethod
    def width_and_replays(probe):
        if probe["spans"] == 0:
            width = probe["rows"]
        else:
            width = probe["spans"] * SPAN_FACTOR
        return width, probe["replays"] + REPLAY_OFFSET

    # -- multiplier and additive response for a probe ---------------------
    def response(self, probe, endpoint):
        precision = self.charged_precision(endpoint["variant"])
        kernel = self.runtimes[endpoint["runtime"]]["kernel"]
        accel = endpoint["accel"]
        phase = probe["phase"]
        factor = (GAIN
                  * KERNEL_FACTOR.get(kernel, Fraction(1))
                  * ACCEL_FACTOR.get(accel, Fraction(1))
                  * PRECISION_FACTOR.get(precision, Fraction(1))
                  * PHASE_FACTOR.get(phase, Fraction(1)))
        additive = (KERNEL_ADJ.get(kernel, 0)
                    + ACCEL_ADJ.get(accel, 0)
                    + PRECISION_ADJ.get(precision, 0)
                    + PHASE_ADJ.get(phase, 0))
        return factor, additive

    # -- the whole shift --------------------------------------------------
    def run(self):
        verdicts = []
        state = {}
        counters = {}
        resolved_scores = []          # every score resolved so far, shift wide

        for probe in self.probes:
            endpoint_id = probe["endpoint"]
            endpoint = self.endpoints[endpoint_id]
            floor = int(self.runtimes[endpoint["runtime"]]["floor"])

            if endpoint_id not in state:
                state[endpoint_id] = {
                    "budget": floor,
                    "backlog": 0,
                    "strikes": 0,
                    "prev_serve": False,
                    "credit": False,
                    "trail": deque(),
                    "counted": 0,
                    "score_total": 0,
                    "top_score": 0,
                    "top_tag": None,
                    "flagged": 0,
                    "probes": 0,
                    "bands": {band: 0 for band in BAND_ORDER},
                    "backlog_end": 0,
                    "budget_end": floor,
                }
            st = state[endpoint_id]

            # ---- meter recovery ----------------------------------------
            phase = probe["phase"]
            key = (endpoint_id, phase)
            if probe["mode"] == SEGMENT_MODE:
                # a boundary restarts every counter the endpoint holds and the
                # boundary probe itself carries the counter
                for held in [k for k in counters if k[0] == endpoint_id]:
                    del counters[held]
                if probe["meter"] == RESERVED_METER:
                    recovered = counters.get(key, probe["meter"])
                else:
                    counters[key] = probe["meter"]
                    recovered = probe["meter"]
            elif probe["meter"] == RESERVED_METER:
                recovered = counters.get(key, probe["meter"])
            else:
                counters[key] = counters.get(key, 0) + probe["meter"]
                recovered = counters[key]

            if COARSE_ACCEL is not None and endpoint["accel"] == COARSE_ACCEL:
                recovered = recovered * COARSE_SCALE

            # ---- the ordered stages ------------------------------------
            width, replays = self.width_and_replays(probe)
            figure = recovered - st["budget"]
            if figure < 0:
                figure = 0
            factor, additive = self.response(probe, endpoint)
            divisor = width * replays * factor.denominator
            figure = (figure * factor.numerator) // divisor if divisor else 0
            if figure < 0:
                figure = 0

            backlog_before = st["backlog"]
            figure -= backlog_before
            if figure < 0:
                figure = 0
            score_so_far = figure

            # ---- replay lookup -----------------------------------------
            tag = probe["tag"]
            replaced = None
            for held_tag, held_score in reversed(st["trail"]):
                if held_tag == tag:
                    replaced = held_score
                    break
            if replaced is not None:
                score_so_far = replaced

            # ---- credit -------------------------------------------------
            if st["credit"]:
                score_so_far = score_so_far // CREDIT_DIVISOR
                st["credit"] = False
            score = score_so_far

            # ---- banding -----------------------------------------------
            if score < IDLE_BELOW:
                band = "idle"
            elif score < BASE_BELOW:
                band = "base"
            elif score < HIGH_BELOW:
                band = "high"
            else:
                band = "saturate"

            # ---- verdict ------------------------------------------------
            mode = probe["mode"]
            if mode in SETUP_MODES:
                verdict = "setup"
            elif mode == VOID_MODE:
                verdict = "void"
            elif band == "idle":
                verdict = "rejected"
            else:
                plan = self.callers[probe["caller"]]["plan"]
                if backlog_before > PLAN_TOLERANCE[plan]:
                    verdict = "flagged"
                else:
                    verdict = "ok"

            verdicts.append({
                "backlog_before": backlog_before,
                "band": band,
                "caller": probe["caller"],
                "endpoint": endpoint_id,
                "mode": mode,
                "phase": phase,
                "score": score,
                "seq": probe["seq"],
                "tag": tag,
                "verdict": verdict,
            })

            # ---- carry update -------------------------------------------
            resolved_scores.append(score)
            if mode == BUDGET_MODE and resolved_scores:
                st["budget"] = sum(resolved_scores) // len(resolved_scores)
            if mode == BACKLOG_CLEAR_MODE:
                st["backlog"] = 0
            if mode == CREDIT_ARM_MODE:
                st["credit"] = True
            if mode == "serve":
                amount = width * BACKLOG_PER_WIDTH
                if BACKLOG_TIER_DOUBLE:
                    amount = amount * int(endpoint["tier"])
                if st["prev_serve"]:
                    amount = amount + BACKLOG_REPEAT_BONUS
                st["backlog"] = min(int(st["backlog"] + amount), BACKLOG_CEILING)
            st["prev_serve"] = (mode == "serve")
            if verdict == "rejected":
                st["strikes"] += 1

            st["trail"].append((tag, score))
            while len(st["trail"]) > TRAILING_SIZE:
                st["trail"].popleft()

            st["probes"] += 1
            st["bands"][band] += 1
            if verdict == "flagged":
                st["flagged"] += 1
            if verdict in COUNTED_VERDICTS:
                st["counted"] += 1
                st["score_total"] += score
                if score > st["top_score"]:
                    st["top_score"] = score
                    st["top_tag"] = tag
            st["backlog_end"] = st["backlog"]
            st["budget_end"] = st["budget"]

        return verdicts, state

    # -- the four reports --------------------------------------------------
    def reports(self, verdicts, state):
        lines = []
        for record in sorted(verdicts, key=lambda rec: rec["seq"]):
            lines.append(json.dumps(record, sort_keys=True, separators=(",", ":")))
        verdicts_text = "".join(line + "\n" for line in lines)

        # every endpoint the shift holds appears, whether or not it carried a
        # probe; an endpoint that carried none reports zero throughout
        rows = []
        for endpoint_id in sorted(self.endpoints):
            st = state.get(endpoint_id)
            if st is None:
                st = {"backlog_end": 0, "bands": {band: 0 for band in BAND_ORDER},
                      "budget_end": int(self.runtimes[self.endpoints[endpoint_id]["runtime"]]["floor"]),
                      "counted": 0, "flagged": 0, "probes": 0, "score_total": 0,
                      "strikes": 0, "top_score": 0, "top_tag": None}
            rows.append({
                "backlog_end": st["backlog_end"],
                "bands": {band: st["bands"][band] for band in BAND_ORDER},
                "budget_end": st["budget_end"],
                "counted": st["counted"],
                "disposition": ("quarantine" if st["strikes"] >= QUARANTINE_STRIKES
                                else "throttle" if st["backlog_end"] >= THROTTLE_BACKLOG
                                else "clear"),
                "endpoint": endpoint_id,
                "flagged": st["flagged"],
                "probes": st["probes"],
                "score_total": st["score_total"],
                "strikes": st["strikes"],
                "top_score": st["top_score"],
                "top_tag": st["top_tag"],
            })
        endpoints_doc = {"endpoints": rows}
        endpoints_text = json.dumps(endpoints_doc, sort_keys=True, indent=2) + "\n"

        per_precision = defaultdict(lambda: {"endpoints": 0, "probes": 0,
                                            "score_total": 0, "flagged": 0})
        for endpoint_id, row in zip(sorted(self.endpoints), rows):
            endpoint = self.endpoints[endpoint_id]
            precision = self.charged_precision(endpoint["variant"])
            bucket = per_precision[precision]
            bucket["endpoints"] += 1
            bucket["probes"] += row["probes"]
            bucket["score_total"] += row["score_total"]
            bucket["flagged"] += row["flagged"]
        precision_text = "precision,endpoints,probes,score_total,flagged\n"
        for precision in sorted(per_precision):
            bucket = per_precision[precision]
            precision_text += ("%s,%d,%d,%d,%d\n"
                               % (precision, bucket["endpoints"], bucket["probes"],
                                  bucket["score_total"], bucket["flagged"]))

        by_band = {band: 0 for band in BAND_ORDER}
        by_verdict = {verdict: 0 for verdict in VERDICT_ORDER}
        for record in verdicts:
            by_band[record["band"]] += 1
            by_verdict[record["verdict"]] += 1
        quarantined = sorted(row["endpoint"] for row in rows
                            if row["disposition"] == "quarantine")
        top_endpoint = None
        best = None
        for row in rows:
            if best is None or row["score_total"] > best:
                best = row["score_total"]
                top_endpoint = row["endpoint"]
        shift_doc = {
            "by_band": by_band,
            "by_verdict": by_verdict,
            "endpoints": len(rows),
            "probes": len(verdicts),
            "quarantined": quarantined,
            "score_total": sum(row["score_total"] for row in rows),
            "top_endpoint": top_endpoint,
        }
        shift_text = json.dumps(shift_doc, sort_keys=True, indent=2) + "\n"

        return verdicts_text, endpoints_text, precision_text, shift_text


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: gate.py INPUT_DIR OUTPUT_DIR\n")
        return 2
    indir, outdir = argv[1], argv[2]
    os.makedirs(outdir, exist_ok=True)
    gate = Gate(indir)
    verdicts, state = gate.run()
    texts = gate.reports(verdicts, state)
    for name, text in zip(("verdicts.jsonl", "endpoints.json",
                           "precision.csv", "shift.json"), texts):
        with open(os.path.join(outdir, name), "w") as handle:
            handle.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
