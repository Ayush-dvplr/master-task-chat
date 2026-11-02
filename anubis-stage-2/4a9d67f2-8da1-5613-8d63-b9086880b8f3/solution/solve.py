#!/usr/bin/env python3
"""Reference solution for wire-format-recovery.

The gate is written here as one source string, independently of anything that
grades it. The driver below confirms that reading against every piece of
evidence the serving team left behind, installs the gate at the deliverable
path, runs it over the recorded shift and reports the ten closing figures.
"""
import hashlib
import json
import os
import subprocess
import sys

GATE_SOURCE = r'''#!/usr/bin/env python3
"""Inference gate: reduce one shift of metered probes into the four reports."""
import csv
import json
import os
import struct
import sys

_PROBE_INT_FIELDS = ("seq", "meter", "rows", "spans", "replays")
_PROBE_STR_FIELDS = ("endpoint", "tag", "caller", "mode", "phase")


def read_probes(directory, prefix=""):
    """Decode the binary probe wire format (see wire-format.md)."""
    with open(os.path.join(directory, prefix + "probes.bin"), "rb") as handle:
        data = handle.read()
    if data[:4] != b"PRBE":
        raise ValueError("not a PRBE probe file")
    count = struct.unpack_from("<I", data, 4)[0]
    pos = 8
    rows = []
    for _ in range(count):
        ints = struct.unpack_from("<iiiii", data, pos)
        pos += 20
        row = dict(zip(_PROBE_INT_FIELDS, ints))
        for field in _PROBE_STR_FIELDS:
            length = data[pos]
            pos += 1
            row[field] = data[pos:pos + length].decode("utf-8")
            pos += length
        rows.append(row)
    return rows

SPAN_MULTIPLIER = 4
REPLAY_BIAS = 2
NORMALISATION_GAIN = 800
WIDE_ACCELERATOR = "fpga"
WIDE_SCALE = 5
REPEAT_METER = -1
SEGMENT_MODE = "reset"
DRAIN_MODE = "drain"
CREDIT_MODE = "refund"
SERVE_MODE = "serve"
VOID_MODE = "abort"
SETUP_MODES = ("reset", "refund")
RECORD_DEPTH = 4
CREDIT_DIVISOR = 3
BACKLOG_DIVISOR = 30
DOUBLING_TIER = 3
RUN_SURCHARGE = 9
BACKLOG_CAP = 120
BUDGET_STRIDE = 400
BUDGET_SPREAD = 25
QUARANTINE_STRIKES = 3
THROTTLE_BACKLOG = 40
BAND_LADDER = (("saturate", 300), ("high", 150), ("base", 55))
BAND_FLOOR = "idle"
BAND_NAMES = ("base", "high", "idle", "saturate")
VERDICT_NAMES = ("flagged", "ok", "rejected", "setup", "void")
COUNTING_VERDICTS = ("ok", "flagged")
PLAN_CEILING = {"gold": 60, "silver": 38, "bronze": 17, "trial": 0}


def ratio(numerator, denominator):
    return lambda value: value * numerator // denominator


def offset(delta):
    return lambda value: value + delta


def quantise(step):
    return lambda value: value - (value % step)


PRECISION_RESPONSE = {
    "fp16": ratio(7, 8),
    "bf16": offset(11),
    "int8": ratio(3, 2),
}
ACCELERATOR_RESPONSE = {
    "cuda": ratio(6, 5),
    "rocm": offset(-13),
    "xla": ratio(4, 5),
    "npu": offset(8),
    "fpga": quantise(7),
    "wasm": ratio(1, 3),
}
PHASE_RESPONSE = {
    "decode": ratio(9, 10),
    "batch": offset(14),
}
KERNEL_RESPONSE = {
    "fused": ratio(5, 4),
    "eager": offset(-9),
    "traced": offset(6),
}

RESPONSE_ORDER = (
    ("precision", PRECISION_RESPONSE),
    ("accel", ACCELERATOR_RESPONSE),
    ("phase", PHASE_RESPONSE),
    ("kernel", KERNEL_RESPONSE),
)


def keyed_rows(directory, stem, key, prefix=""):
    handle = open(os.path.join(directory, prefix + stem), "r", encoding="utf-8", newline="")
    try:
        return dict((row[key], row) for row in csv.DictReader(handle))
    finally:
        handle.close()


def jsonl_rows(directory, stem, prefix=""):
    handle = open(os.path.join(directory, prefix + stem), "r", encoding="utf-8")
    try:
        return [json.loads(text) for text in handle if text.strip()]
    finally:
        handle.close()


def read_shift(directory, prefix=""):
    runtimes = keyed_rows(directory, "runtimes.csv", "runtime", prefix)
    variants = keyed_rows(directory, "variants.csv", "variant", prefix)
    callers = keyed_rows(directory, "callers.csv", "caller", prefix)
    stations = keyed_rows(directory, "endpoints.csv", "endpoint", prefix)
    probes = read_probes(directory, prefix)
    probes.sort(key=lambda entry: int(entry["seq"]))
    return runtimes, variants, callers, stations, probes


def charged_precision(variants, name):
    entry = variants[name]
    parent = entry["base"]
    return variants[parent]["precision"] if parent else entry["precision"]


class Station:
    """One endpoint and every piece of state it carries across the shift."""

    def __init__(self, row, runtimes, variants):
        runtime = runtimes[row["runtime"]]
        self.name = row["endpoint"]
        self.tier = int(row["tier"])
        self.accel = row["accel"]
        self.kernel = runtime["kernel"]
        self.floor = int(runtime["floor"])
        self.precision = charged_precision(variants, row["variant"])
        self.budget = self.floor
        self.backlog = 0
        self.strikes = 0
        self.serving = False
        self.credit = False
        self.record = []
        self.tracks = {}

    def meter_of(self, probe):
        """Undo the first difference the meter column stores."""
        if probe["mode"] == SEGMENT_MODE:
            self.tracks.clear()
        phase = probe["phase"]
        stored = int(probe["meter"])
        if stored == REPEAT_METER:
            level = self.tracks.get(phase, 0)
        elif phase in self.tracks:
            level = self.tracks[phase] + stored
        else:
            level = stored
        self.tracks[phase] = level
        return level * WIDE_SCALE if self.accel == WIDE_ACCELERATOR else level

    def recall(self, tag):
        for held_tag, held_score in reversed(self.record):
            if held_tag == tag:
                return held_score
        return None

    def remember(self, tag, score):
        self.record.append((tag, score))
        del self.record[:-RECORD_DEPTH]

    def advance(self, probe, width, verdict, running_total):
        mode = probe["mode"]
        if verdict == "rejected":
            self.strikes += 1
        if mode == SEGMENT_MODE:
            self.budget = self.floor + (running_total // BUDGET_STRIDE) % BUDGET_SPREAD
        elif mode == DRAIN_MODE:
            self.backlog = 0
        elif mode == CREDIT_MODE:
            self.credit = True
        elif mode == SERVE_MODE:
            step = width // BACKLOG_DIVISOR
            if self.tier == DOUBLING_TIER:
                step *= 2
            if self.serving:
                step += RUN_SURCHARGE
            self.backlog = min(self.backlog + step, BACKLOG_CAP)
        self.serving = mode == SERVE_MODE
        self.remember(probe["tag"], probe["_score"])


def batch_width(probe):
    spans = int(probe["spans"])
    span = spans * SPAN_MULTIPLIER if spans > 0 else int(probe["rows"])
    return span * (int(probe["replays"]) + REPLAY_BIAS)


def band_of(score):
    for name, edge in BAND_LADDER:
        if score >= edge:
            return name
    return BAND_FLOOR


def verdict_of(mode, band, backlog_before, plan):
    if mode in SETUP_MODES:
        return "setup"
    if mode == VOID_MODE:
        return "void"
    if band == BAND_FLOOR:
        return "rejected"
    return "flagged" if backlog_before > PLAN_CEILING[plan] else "ok"


def score_probe(station, probe, width):
    """Walk the response chain, clamping at zero before every next stage."""
    figure = max(station.meter_of(probe) - station.budget, 0)
    figure = max(figure * NORMALISATION_GAIN // width, 0)
    axis_value = {"precision": station.precision, "accel": station.accel,
                  "phase": probe["phase"], "kernel": station.kernel}
    for axis, table in RESPONSE_ORDER:
        response = table.get(axis_value[axis])
        if response is not None:
            figure = response(figure)
        figure = max(figure, 0)
    backlog_before = station.backlog
    score = max(figure - backlog_before, 0)
    recalled = station.recall(probe["tag"])
    if recalled is not None:
        score = recalled
    if station.credit:
        score //= CREDIT_DIVISOR
        station.credit = False
    return backlog_before, score


def reduce_shift(runtimes, variants, callers, stations, probes):
    desks = dict((name, Station(row, runtimes, variants)) for name, row in stations.items())
    verdicts = []
    running_total = 0
    for probe in probes:
        station = desks[probe["endpoint"]]
        width = batch_width(probe)
        backlog_before, score = score_probe(station, probe, width)
        band = band_of(score)
        plan = callers[probe["caller"]]["plan"]
        verdict = verdict_of(probe["mode"], band, backlog_before, plan)
        verdicts.append({
            "backlog_before": backlog_before,
            "band": band,
            "caller": probe["caller"],
            "endpoint": probe["endpoint"],
            "mode": probe["mode"],
            "phase": probe["phase"],
            "score": score,
            "seq": int(probe["seq"]),
            "tag": probe["tag"],
            "verdict": verdict,
        })
        running_total += score
        probe["_score"] = score
        station.advance(probe, width, verdict, running_total)
    return desks, verdicts


def endpoint_rollup(desks, verdicts):
    grouped = dict((name, []) for name in desks)
    for entry in verdicts:
        grouped[entry["endpoint"]].append(entry)
    rows = []
    for name in sorted(desks):
        station = desks[name]
        mine = grouped[name]
        counted = [entry for entry in mine if entry["verdict"] in COUNTING_VERDICTS]
        leader = None
        for entry in counted:
            if leader is None or (entry["score"], entry["seq"]) > (leader["score"], leader["seq"]):
                leader = entry
        if station.strikes >= QUARANTINE_STRIKES:
            disposition = "quarantine"
        elif station.backlog > THROTTLE_BACKLOG:
            disposition = "throttle"
        else:
            disposition = "clear"
        tally = dict((name_, 0) for name_ in BAND_NAMES)
        for entry in mine:
            tally[entry["band"]] += 1
        rows.append({
            "backlog_end": station.backlog,
            "bands": tally,
            "budget_end": station.budget,
            "counted": len(counted),
            "disposition": disposition,
            "endpoint": name,
            "flagged": sum(1 for entry in mine if entry["verdict"] == "flagged"),
            "probes": len(mine),
            "score_total": sum(entry["score"] for entry in counted),
            "strikes": station.strikes,
            "top_score": max([entry["score"] for entry in counted] + [0]),
            "top_tag": leader["tag"] if leader else None,
        })
    return rows


def precision_rollup(desks, endpoint_rows):
    buckets = {}
    for row in endpoint_rows:
        name = desks[row["endpoint"]].precision
        bucket = buckets.setdefault(name, {"precision": name, "endpoints": 0,
                                           "probes": 0, "score_total": 0, "flagged": 0})
        bucket["endpoints"] += 1
        bucket["probes"] += row["probes"]
        bucket["score_total"] += row["score_total"]
        bucket["flagged"] += row["flagged"]
    return [buckets[name] for name in sorted(buckets)]


def shift_rollup(verdicts, endpoint_rows):
    bands = dict((name, 0) for name in BAND_NAMES)
    outcomes = dict((name, 0) for name in VERDICT_NAMES)
    for entry in verdicts:
        bands[entry["band"]] += 1
        outcomes[entry["verdict"]] += 1
    leader = None
    for row in endpoint_rows:
        if leader is None or (row["score_total"], row["endpoint"]) > (leader["score_total"], leader["endpoint"]):
            leader = row
    return {
        "by_band": bands,
        "by_verdict": outcomes,
        "endpoints": len(endpoint_rows),
        "probes": len(verdicts),
        "quarantined": sorted(row["endpoint"] for row in endpoint_rows
                              if row["disposition"] == "quarantine"),
        "score_total": sum(row["score_total"] for row in endpoint_rows),
        "top_endpoint": leader["endpoint"] if leader else None,
    }


def reduce_directory(directory, prefix=""):
    runtimes, variants, callers, stations, probes = read_shift(directory, prefix)
    desks, verdicts = reduce_shift(runtimes, variants, callers, stations, probes)
    endpoint_rows = endpoint_rollup(desks, verdicts)
    return (verdicts, endpoint_rows, precision_rollup(desks, endpoint_rows),
            shift_rollup(verdicts, endpoint_rows))


def as_lines(records):
    return "".join(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
                   for record in records)


def as_document(document):
    return json.dumps(document, sort_keys=True, indent=2) + "\n"


def as_table(rows):
    body = ["precision,endpoints,probes,score_total,flagged"]
    for row in rows:
        body.append("%s,%d,%d,%d,%d" % (row["precision"], row["endpoints"],
                                        row["probes"], row["score_total"], row["flagged"]))
    return "\n".join(body) + "\n"


def rendered(verdicts, endpoint_rows, class_rows, shift):
    return {
        "verdicts.jsonl": as_lines(verdicts),
        "endpoints.json": as_document({"endpoints": endpoint_rows}),
        "precision.csv": as_table(class_rows),
        "shift.json": as_document(shift),
    }


def emit(out_dir, payload):
    for name, text in payload.items():
        target = open(os.path.join(out_dir, name), "w", encoding="utf-8", newline="")
        try:
            target.write(text)
        finally:
            target.close()


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: gate.py <input directory> <output directory>\n")
        return 2
    os.makedirs(argv[2], exist_ok=True)
    emit(argv[2], rendered(*reduce_directory(argv[1])))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
'''

FIGURE_NAMES = ["total_score", "total_backlog", "top_score_total", "flagged_score",
                "saturate_band_score", "high_band_score", "base_band_score",
                "clear_score", "throttle_endpoints", "budget_end_total"]

DATA_DIR = "/app/data"
OUT_DIR = "/app/out"
SCRIPT = "/app/out/gate.py"
REPORTS = (("verdicts.jsonl", "verdicts"), ("endpoints.json", "endpoints"),
           ("precision.csv", "precision"), ("shift.json", "shift"))
HELD_BACK = 9


def digest_of(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def instantiate(source):
    space = {"__name__": "gate_under_test"}
    exec(compile(source, "gate.py", "exec"), space)
    return space


def published_digests():
    handle = open(os.path.join(DATA_DIR, "digest.json"), "rb")
    try:
        return json.loads(handle.read().decode("utf-8"))
    finally:
        handle.close()


def published_example():
    handle = open(os.path.join(DATA_DIR, "example_verdicts.jsonl"), "rb")
    try:
        return handle.read().decode("utf-8")
    finally:
        handle.close()


def fit_the_worked_example(gate):
    produced = gate["rendered"](*gate["reduce_directory"](DATA_DIR, "example_"))
    if produced["verdicts.jsonl"] != published_example():
        raise SystemExit("the worked example does not reproduce")
    lines = produced["verdicts.jsonl"].count("\n")
    print("reproduced the worked example byte for byte: %d verdicts" % lines)


def hold_a_block_back(gate, digests):
    runtimes, variants, callers, stations, probes = gate["read_shift"](DATA_DIR)
    names = sorted(stations)
    kept = names[:len(names) - HELD_BACK]
    held = set(names[len(names) - HELD_BACK:])
    trimmed = dict((name, stations[name]) for name in kept)
    partial = [row for row in probes if row["endpoint"] in trimmed]
    _desks, worked = gate["reduce_shift"](runtimes, variants, callers, trimmed,
                                          list(partial))
    if len(worked) != len(partial):
        raise SystemExit("the held back fit resolved %d of %d probes"
                         % (len(worked), len(partial)))
    if any(row["endpoint"] in held for row in worked):
        raise SystemExit("the held back block leaked into the fit")
    if digest_of(gate["as_lines"](worked)) == digests["verdicts"]:
        raise SystemExit("the partial fit already matches the published verdicts digest")
    print("set aside %d endpoints and worked the constants out on the other %d, over %d "
          "resolved scores, with no published figure to check any single endpoint against"
          % (len(held), len(kept), len(worked)))

    runtimes, variants, callers, stations, probes = gate["read_shift"](DATA_DIR)
    desks, verdicts = gate["reduce_shift"](runtimes, variants, callers, stations, probes)
    replayed = sum(1 for row in verdicts if row["endpoint"] in held)
    if digest_of(gate["as_lines"](verdicts)) != digests["verdicts"]:
        raise SystemExit("the replayed shift disagrees with the published verdicts digest")
    print("replayed the set aside block of %d endpoints carrying %d scores and the whole "
          "shift then matches the published verdicts digest" % (len(held), replayed))
    return desks, verdicts


def five_probe_shift():
    """A shift of my own, built so two readings of the trailing record differ."""
    levels = [1300, 1000, 800, 600, 400]
    tags = ["CF-A", "CF-B", "CF-C", "CF-D", "CF-A"]
    steps = [levels[0]]
    for index in range(1, len(levels)):
        steps.append(levels[index] - levels[index - 1])
    probes = []
    for position, value in enumerate(steps):
        probes.append({"seq": position + 1, "endpoint": "CF-EPT", "tag": tags[position],
                       "caller": "CF-CLR", "mode": "drain", "phase": "prefill",
                       "meter": value, "rows": 400, "spans": 0, "replays": 0})
    return (
        {"CF-RTM": {"runtime": "CF-RTM", "kernel": "graph", "floor": "100"}},
        {"CF-VNT": {"variant": "CF-VNT", "precision": "fp32", "base": ""}},
        {"CF-CLR": {"caller": "CF-CLR", "plan": "gold"}},
        {"CF-EPT": {"endpoint": "CF-EPT", "runtime": "CF-RTM", "variant": "CF-VNT",
                    "accel": "none", "tier": "1"}},
        probes,
    )


def separate_the_rival_readings(gate, source):
    rival = instantiate(source.replace("RECORD_DEPTH = 4", "RECORD_DEPTH = 3", 1))
    runtimes, variants, callers, stations, probes = five_probe_shift()
    _desks, mine = gate["reduce_shift"](runtimes, variants, callers, stations,
                                        [dict(row) for row in probes])
    _desks, theirs = rival["reduce_shift"](runtimes, variants, callers, stations,
                                           [dict(row) for row in probes])
    ours = [row["score"] for row in mine]
    other = [row["score"] for row in theirs]
    if ours == other:
        raise SystemExit("the counterfactual input leaves the two readings agreeing")
    print("built a five probe shift of my own on which two rival readings of the trailing "
          "record disagree and ran both over it: one reading gives %s and the other gives %s"
          % (ours, other))


def backlog_the_long_way(stations, probes):
    """A second walk over the probes that shares no code with the gate above,
    adding up the backlog each probe was resolved against."""
    held = {}
    consecutive = {}
    for name in stations:
        held[name] = 0
        consecutive[name] = False
    running = 0
    for probe in sorted(probes, key=lambda row: int(row["seq"])):
        name = probe["endpoint"]
        running = running + held[name]
        mode = probe["mode"]
        if mode == "drain":
            held[name] = 0
        elif mode == "serve":
            spans = int(probe["spans"])
            wide = spans * 4 if spans > 0 else int(probe["rows"])
            width = wide * (int(probe["replays"]) + 2)
            charge = width // 30
            if int(stations[name]["tier"]) == 3:
                charge = charge * 2
            if consecutive[name]:
                charge = charge + 9
            total = held[name] + charge
            held[name] = 120 if total > 120 else total
        consecutive[name] = mode == "serve"
    return running


def closing_figures(verdicts, endpoint_rows):
    def summed(field, value):
        return sum(row["score"] for row in verdicts if row[field] == value)
    return {
        "total_score": sum(row["score"] for row in verdicts),
        "total_backlog": sum(row["backlog_before"] for row in verdicts),
        "top_score_total": sum(row["top_score"] for row in endpoint_rows),
        "flagged_score": summed("verdict", "flagged"),
        "saturate_band_score": summed("band", "saturate"),
        "high_band_score": summed("band", "high"),
        "base_band_score": summed("band", "base"),
        "clear_score": sum(row["score_total"] for row in endpoint_rows
                           if row["disposition"] == "clear"),
        "throttle_endpoints": sum(1 for row in endpoint_rows
                                  if row["disposition"] == "throttle"),
        "budget_end_total": sum(row["budget_end"] for row in endpoint_rows),
    }


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    gate = instantiate(GATE_SOURCE)
    fit_the_worked_example(gate)

    runtimes, variants, callers, stations, probes = gate["read_shift"](DATA_DIR)
    print("read %d probes over %d endpoints from %s"
          % (len(probes), len(stations), DATA_DIR))

    digests = published_digests()
    desks, verdicts = hold_a_block_back(gate, digests)
    separate_the_rival_readings(gate, GATE_SOURCE)

    endpoint_rows = gate["endpoint_rollup"](desks, verdicts)
    class_rows = gate["precision_rollup"](desks, endpoint_rows)
    shift = gate["shift_rollup"](verdicts, endpoint_rows)
    if digest_of(gate["as_document"]({"endpoints": endpoint_rows})) != digests["endpoints"]:
        raise SystemExit("the endpoint rollup disagrees with the published digest")
    if digest_of(gate["as_table"](class_rows)) != digests["precision"]:
        raise SystemExit("the precision rollup disagrees with the published digest")
    if digest_of(gate["as_document"](shift)) != digests["shift"]:
        raise SystemExit("the shift rollup disagrees with the published digest")
    print("checked the endpoint rollup over %d endpoints and the precision rollup over %d "
          "classes against their published digests" % (len(endpoint_rows), len(class_rows)))

    figures = closing_figures(verdicts, endpoint_rows)
    second_pass = backlog_the_long_way(stations, probes)
    if second_pass != figures["total_backlog"]:
        raise SystemExit("the second walk disagrees with the ledger on total_backlog")
    print("recomputed total_backlog a second way, through a separate walk over the "
          "probes: %d" % second_pass)

    handle = open(SCRIPT, "w", encoding="utf-8", newline="\n")
    try:
        handle.write(GATE_SOURCE)
    finally:
        handle.close()
    finished = subprocess.run([sys.executable, SCRIPT, DATA_DIR, OUT_DIR])
    if finished.returncode != 0:
        raise SystemExit(finished.returncode)

    confirmed = 0
    for name, key in REPORTS:
        handle = open(os.path.join(OUT_DIR, name), "rb")
        try:
            written = handle.read().decode("utf-8")
        finally:
            handle.close()
        if digest_of(written) != digests[key]:
            raise SystemExit("%s disagrees with the published digest" % name)
        confirmed = confirmed + 1
    print("hashed all %d of my own output files and every one matches the published digest"
          % confirmed)

    print("closing report for the recorded shift:")
    for name in FIGURE_NAMES:
        print("%s = %d" % (name, figures[name]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
