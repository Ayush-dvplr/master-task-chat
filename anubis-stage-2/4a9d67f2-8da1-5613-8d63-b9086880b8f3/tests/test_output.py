import ast
import csv
import json
import os
import random
import shutil
import signal
import struct
import subprocess
import sys
import tempfile

from rewardkit import criteria, criterion

# Binary probe wire format "PRBE" (documented in environment/data/wire-format.md).
_PROBE_MAGIC = b"PRBE"
_PROBE_INT_FIELDS = ("seq", "meter", "rows", "spans", "replays")
_PROBE_STR_FIELDS = ("endpoint", "tag", "caller", "mode", "phase")


def encode_probes(rows):
    out = bytearray(_PROBE_MAGIC)
    out += struct.pack("<I", len(rows))
    for row in rows:
        out += struct.pack("<iiiii", *(int(row[f]) for f in _PROBE_INT_FIELDS))
        for f in _PROBE_STR_FIELDS:
            encoded = str(row[f]).encode("utf-8")
            out.append(len(encoded))
            out += encoded
    return bytes(out)


def decode_probes(data):
    if data[:4] != _PROBE_MAGIC:
        raise ValueError("not a PRBE probe file")
    count = struct.unpack_from("<I", data, 4)[0]
    pos = 8
    rows = []
    for _ in range(count):
        ints = struct.unpack_from("<iiiii", data, pos)
        pos += 20
        row = dict(zip(_PROBE_INT_FIELDS, ints))
        for f in _PROBE_STR_FIELDS:
            length = data[pos]
            pos += 1
            row[f] = data[pos:pos + length].decode("utf-8")
            pos += length
        rows.append(row)
    return rows


def _read_csv(path):
    with open(path, "r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_jsonl(path):
    rows = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_named(data_dir, prefix=""):
    runtimes = {}
    for row in _read_csv(os.path.join(data_dir, prefix + "runtimes.csv")):
        runtimes[row["runtime"]] = {
            "runtime": row["runtime"],
            "kernel": row["kernel"],
            "floor": int(row["floor"]),
        }
    variants = {}
    for row in _read_csv(os.path.join(data_dir, prefix + "variants.csv")):
        variants[row["variant"]] = {
            "variant": row["variant"],
            "precision": row["precision"],
            "base": row["base"],
        }
    callers = {}
    for row in _read_csv(os.path.join(data_dir, prefix + "callers.csv")):
        callers[row["caller"]] = {"caller": row["caller"], "plan": row["plan"]}
    endpoints = {}
    for row in _read_csv(os.path.join(data_dir, prefix + "endpoints.csv")):
        endpoints[row["endpoint"]] = {
            "endpoint": row["endpoint"],
            "runtime": row["runtime"],
            "variant": row["variant"],
            "accel": row["accel"],
            "tier": int(row["tier"]),
        }
    probes = []
    with open(os.path.join(data_dir, prefix + "probes.bin"), "rb") as handle:
        decoded = decode_probes(handle.read())
    for row in decoded:
        probes.append({
            "seq": int(row["seq"]),
            "endpoint": row["endpoint"],
            "tag": row["tag"],
            "caller": row["caller"],
            "mode": row["mode"],
            "phase": row["phase"],
            "meter": int(row["meter"]),
            "rows": int(row["rows"]),
            "spans": int(row["spans"]),
            "replays": int(row["replays"]),
        })
    return {"runtimes": runtimes, "variants": variants, "callers": callers,
            "endpoints": endpoints, "probes": probes}


def load_corpus(data_dir):
    return load_named(data_dir, "")


def charged_precision(variants, variant):
    entry = variants[variant]
    if entry["base"]:
        return variants[entry["base"]]["precision"]
    return entry["precision"]


def probe_width(probe):
    if probe["spans"] > 0:
        span = probe["spans"] * 4
    else:
        span = probe["rows"]
    return span * (probe["replays"] + 2)


def _adjust_precision(figure, precision):
    if precision == "fp16":
        return figure * 7 // 8
    if precision == "bf16":
        return figure + 11
    if precision == "int8":
        return figure * 3 // 2
    return figure


def _adjust_accel(figure, accel):
    if accel == "cuda":
        return figure * 6 // 5
    if accel == "rocm":
        return figure - 13
    if accel == "xla":
        return figure * 4 // 5
    if accel == "npu":
        return figure + 8
    if accel == "fpga":
        return figure - (figure % 7)
    if accel == "wasm":
        return figure // 3
    return figure


def _adjust_phase(figure, phase):
    if phase == "decode":
        return figure * 9 // 10
    if phase == "batch":
        return figure + 14
    return figure


def _adjust_kernel(figure, kernel):
    if kernel == "fused":
        return figure * 5 // 4
    if kernel == "eager":
        return figure - 9
    if kernel == "traced":
        return figure + 6
    return figure


def _band(score):
    if score >= 300:
        return "saturate"
    if score >= 150:
        return "high"
    if score >= 55:
        return "base"
    return "idle"


def _plan_limit(plan):
    if plan == "gold":
        return 60
    if plan == "silver":
        return 38
    if plan == "bronze":
        return 17
    return 0


def _verdict(mode, band, backlog_before, plan):
    if mode == "reset" or mode == "refund":
        return "setup"
    if mode == "abort":
        return "void"
    if band == "idle":
        return "rejected"
    if backlog_before > _plan_limit(plan):
        return "flagged"
    return "ok"


def _backlog_step(width, tier, run):
    step = width // 30
    if tier == 3:
        step = step * 2
    if run >= 1:
        step = step + 9
    return step


def resolve(corpus):
    runtimes = corpus["runtimes"]
    variants = corpus["variants"]
    callers = corpus["callers"]
    endpoints = corpus["endpoints"]

    state = {}
    for endpoint_id, endpoint in endpoints.items():
        state[endpoint_id] = {
            "budget": runtimes[endpoint["runtime"]]["floor"],
            "backlog": 0,
            "strikes": 0,
            "run": 0,
            "credit": 0,
            "recent": [],
            "meters": {},
        }

    verdicts = []
    running_total = 0
    for probe in sorted(corpus["probes"], key=lambda row: row["seq"]):
        endpoint = endpoints[probe["endpoint"]]
        slot = state[probe["endpoint"]]
        kernel = runtimes[endpoint["runtime"]]["kernel"]
        precision = charged_precision(variants, endpoint["variant"])
        plan = callers[probe["caller"]]["plan"]

        if probe["mode"] == "reset":
            slot["meters"] = {}
        track = slot["meters"].setdefault(probe["phase"], {"value": 0, "seen": 0})
        stored = probe["meter"]
        if stored == -1:
            meter = track["value"]
        elif track["seen"] == 0:
            meter = stored
            track["seen"] = 1
        else:
            meter = track["value"] + stored
        track["value"] = meter
        if endpoint["accel"] == "fpga":
            meter = meter * 5

        width = probe_width(probe)
        figure = meter - slot["budget"]
        if figure < 0:
            figure = 0
        figure = figure * 800 // width
        if figure < 0:
            figure = 0
        figure = _adjust_precision(figure, precision)
        if figure < 0:
            figure = 0
        figure = _adjust_accel(figure, endpoint["accel"])
        if figure < 0:
            figure = 0
        figure = _adjust_phase(figure, probe["phase"])
        if figure < 0:
            figure = 0
        figure = _adjust_kernel(figure, kernel)
        if figure < 0:
            figure = 0
        backlog_before = slot["backlog"]
        score = figure - backlog_before
        if score < 0:
            score = 0
        index = len(slot["recent"]) - 1
        while index >= 0:
            if slot["recent"][index][0] == probe["tag"]:
                score = slot["recent"][index][1]
                break
            index = index - 1
        if slot["credit"]:
            score = score // 3
            slot["credit"] = 0
        band = _band(score)
        verdict = _verdict(probe["mode"], band, backlog_before, plan)

        verdicts.append({
            "backlog_before": backlog_before,
            "band": band,
            "caller": probe["caller"],
            "endpoint": probe["endpoint"],
            "mode": probe["mode"],
            "phase": probe["phase"],
            "score": score,
            "seq": probe["seq"],
            "tag": probe["tag"],
            "verdict": verdict,
        })

        running_total = running_total + score
        if verdict == "rejected":
            slot["strikes"] = slot["strikes"] + 1
        if probe["mode"] == "reset":
            slot["budget"] = (runtimes[endpoint["runtime"]]["floor"]
                              + (running_total // 400) % 25)
            slot["run"] = 0
        elif probe["mode"] == "drain":
            slot["backlog"] = 0
            slot["run"] = 0
        elif probe["mode"] == "refund":
            slot["credit"] = 1
            slot["run"] = 0
        elif probe["mode"] == "serve":
            backlog = slot["backlog"] + _backlog_step(width, endpoint["tier"], slot["run"])
            if backlog > 120:
                backlog = 120
            slot["backlog"] = backlog
            slot["run"] = slot["run"] + 1
        else:
            slot["run"] = 0
        slot["recent"].append((probe["tag"], score))
        if len(slot["recent"]) > 4:
            del slot["recent"][0]

    endpoint_rows = []
    for endpoint_id in sorted(endpoints):
        rows = [row for row in verdicts if row["endpoint"] == endpoint_id]
        counted = [row for row in rows if row["verdict"] == "ok" or row["verdict"] == "flagged"]
        score_total = 0
        top_score = 0
        best = None
        for row in counted:
            score_total = score_total + row["score"]
            if row["score"] > top_score:
                top_score = row["score"]
            if best is None:
                best = row
            elif row["score"] > best["score"]:
                best = row
            elif row["score"] == best["score"] and row["seq"] > best["seq"]:
                best = row
        strikes = state[endpoint_id]["strikes"]
        backlog_end = state[endpoint_id]["backlog"]
        if strikes >= 3:
            disposition = "quarantine"
        elif backlog_end > 40:
            disposition = "throttle"
        else:
            disposition = "clear"
        bands = {"base": 0, "high": 0, "idle": 0, "saturate": 0}
        for row in rows:
            bands[row["band"]] = bands[row["band"]] + 1
        endpoint_rows.append({
            "backlog_end": backlog_end,
            "bands": bands,
            "budget_end": state[endpoint_id]["budget"],
            "counted": len(counted),
            "disposition": disposition,
            "endpoint": endpoint_id,
            "flagged": sum(1 for row in rows if row["verdict"] == "flagged"),
            "probes": len(rows),
            "score_total": score_total,
            "strikes": strikes,
            "top_score": top_score,
            "top_tag": best["tag"] if best is not None else None,
        })

    by_band = {"base": 0, "high": 0, "idle": 0, "saturate": 0}
    by_verdict = {"flagged": 0, "ok": 0, "rejected": 0, "setup": 0, "void": 0}
    for row in verdicts:
        by_band[row["band"]] = by_band[row["band"]] + 1
        by_verdict[row["verdict"]] = by_verdict[row["verdict"]] + 1

    top_endpoint = None
    top_total = None
    for row in endpoint_rows:
        if top_total is None or row["score_total"] > top_total:
            top_endpoint = row["endpoint"]
            top_total = row["score_total"]
        elif row["score_total"] == top_total and row["endpoint"] > top_endpoint:
            top_endpoint = row["endpoint"]

    classes = {}
    for row in endpoint_rows:
        precision = charged_precision(variants, endpoints[row["endpoint"]]["variant"])
        entry = classes.setdefault(precision, {"precision": precision, "endpoints": 0,
                                               "probes": 0, "score_total": 0, "flagged": 0})
        entry["endpoints"] = entry["endpoints"] + 1
        entry["probes"] = entry["probes"] + row["probes"]
        entry["score_total"] = entry["score_total"] + row["score_total"]
        entry["flagged"] = entry["flagged"] + row["flagged"]
    class_rows = [classes[key] for key in sorted(classes)]

    shift = {
        "by_band": by_band,
        "by_verdict": by_verdict,
        "endpoints": len(endpoint_rows),
        "probes": len(verdicts),
        "quarantined": sorted(row["endpoint"] for row in endpoint_rows
                              if row["disposition"] == "quarantine"),
        "score_total": sum(row["score_total"] for row in endpoint_rows),
        "top_endpoint": top_endpoint,
    }
    return verdicts, endpoint_rows, class_rows, shift


def derive(data_dir):
    return resolve(load_corpus(data_dir))


def render_verdicts(verdicts):
    parts = []
    for row in verdicts:
        parts.append(json.dumps(row, sort_keys=True, separators=(",", ":")))
        parts.append("\n")
    return "".join(parts)


def render_document(document):
    return json.dumps(document, sort_keys=True, indent=2) + "\n"


def render_classes(class_rows):
    lines = ["precision,endpoints,probes,score_total,flagged"]
    for row in class_rows:
        lines.append("%s,%d,%d,%d,%d" % (row["precision"], row["endpoints"], row["probes"],
                                         row["score_total"], row["flagged"]))
    return "\n".join(lines) + "\n"


def write_reports(out_dir, verdicts, endpoint_rows, class_rows, shift):
    with open(os.path.join(out_dir, "verdicts.jsonl"), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_verdicts(verdicts))
    with open(os.path.join(out_dir, "endpoints.json"), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_document({"endpoints": endpoint_rows}))
    with open(os.path.join(out_dir, "precision.csv"), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_classes(class_rows))
    with open(os.path.join(out_dir, "shift.json"), "w", encoding="utf-8", newline="") as handle:
        handle.write(render_document(shift))


class _Case:
    """Builds one shift corpus.  It mirrors the accumulator and the carried
    state so a probe can be aimed at a chosen score, and so absolute meters
    can be written as the first differences the meter column stores."""

    def __init__(self):
        self.runtimes = []
        self.variants = []
        self.callers = []
        self.endpoints = []
        self.probes = []
        self.seq = 0
        self.tag_no = 0
        self.state = {}

    def runtime(self, name, kernel, floor):
        self.runtimes.append((name, kernel, floor))
        return name

    def variant(self, name, precision, base):
        self.variants.append((name, precision, base))
        return name

    def caller(self, name, plan):
        self.callers.append((name, plan))
        return name

    def _runtime(self, name):
        for row in self.runtimes:
            if row[0] == name:
                return row
        raise KeyError(name)

    def _precision(self, variant):
        table = dict((name, (precision, base)) for name, precision, base in self.variants)
        precision, base = table[variant]
        if base:
            return table[base][0]
        return precision

    def endpoint(self, endpoint_id, runtime, variant, accel, tier):
        _name, kernel, floor = self._runtime(runtime)
        self.endpoints.append((endpoint_id, runtime, variant, accel, tier))
        self.state[endpoint_id] = {
            "budget": floor,
            "backlog": 0,
            "run": 0,
            "credit": 0,
            "recent": [],
            "meters": {},
            "tier": tier,
            "accel": accel,
            "precision": self._precision(variant),
            "kernel": kernel,
        }
        return endpoint_id

    def _next_tag(self):
        self.tag_no += 1
        return "TAG-%04d" % self.tag_no

    def neutral(self, endpoint_id):
        slot = self.state[endpoint_id]
        return (slot["accel"] == "none" and slot["precision"] == "fp32"
                and slot["kernel"] == "graph")

    def probe(self, endpoint_id, caller, mode, phase, meter, rows, spans, replays,
              tag=None, sentinel=False):
        """meter is the absolute counter the engine has to recover."""
        slot = self.state[endpoint_id]
        if mode == "reset":
            slot["meters"] = {}
        track = slot["meters"].setdefault(phase, {"value": 0, "seen": 0})
        if sentinel:
            stored = -1
            meter = track["value"]
        elif track["seen"] == 0:
            stored = meter
            track["seen"] = 1
        else:
            stored = meter - track["value"]
        if not sentinel and stored == -1:
            raise ValueError(
                "probe on %s encodes to the reserved meter value; the engine would "
                "read it as a repeat rather than as this level, so space the levels "
                "differently" % endpoint_id)
        track["value"] = meter
        self.seq += 1
        if tag is None:
            tag = self._next_tag()
        self.probes.append({
            "seq": self.seq, "endpoint": endpoint_id, "tag": tag, "caller": caller,
            "mode": mode, "phase": phase, "meter": stored,
            "rows": rows, "spans": spans, "replays": replays,
        })
        if slot["credit"]:
            slot["credit"] = 0
        width = (spans * 4 if spans > 0 else rows) * (replays + 2)
        if mode == "drain":
            slot["backlog"] = 0
            slot["run"] = 0
        elif mode == "refund":
            slot["credit"] = 1
            slot["run"] = 0
        elif mode == "serve":
            step = width // 30
            if slot["tier"] == 3:
                step = step * 2
            if slot["run"] >= 1:
                step = step + 9
            backlog = slot["backlog"] + step
            slot["backlog"] = 120 if backlog > 120 else backlog
            slot["run"] = slot["run"] + 1
        else:
            slot["run"] = 0
        slot["recent"].append(tag)
        if len(slot["recent"]) > 4:
            del slot["recent"][0]
        return self.seq

    def would_repeat(self, endpoint_id, phase, meter):
        """True when this absolute counter would encode to the reserved value,
        which the engine reads as a repeat rather than as the level asked for."""
        slot = self.state[endpoint_id]
        track = slot["meters"].get(phase)
        if track is None or track["seen"] == 0:
            return meter == -1
        return meter - track["value"] == -1

    def shape(self, width):
        if width % 2 != 0:
            raise ValueError("width %d must be even" % width)
        return width // 2, 0, 0

    def target(self, endpoint_id, caller, mode, score, width=800, tag=None):
        """Aim one probe at a chosen score.  Only meaningful on an endpoint that
        is neutral on every keyed axis and carries no credit."""
        slot = self.state[endpoint_id]
        if not self.neutral(endpoint_id):
            raise ValueError("aiming a score needs a neutral endpoint")
        figure = score + slot["backlog"]
        product = figure * width
        if product % 800 != 0:
            raise ValueError("width %d cannot express figure %d exactly" % (width, figure))
        meter = slot["budget"] + product // 800
        rows, spans, replays = self.shape(width)
        return self.probe(endpoint_id, caller, mode, "prefill", meter,
                          rows, spans, replays, tag)

    def flat(self, endpoint_id, caller, mode, width=800, tag=None):
        slot = self.state[endpoint_id]
        rows, spans, replays = self.shape(width)
        return self.probe(endpoint_id, caller, mode, "prefill", slot["budget"],
                          rows, spans, replays, tag)

    def spend(self, endpoint_id, caller, width, tag=None):
        """A serve at the budget: it scores zero and only moves the backlog."""
        slot = self.state[endpoint_id]
        rows, spans, replays = self.shape(width)
        return self.probe(endpoint_id, caller, "serve", "prefill", slot["budget"],
                          rows, spans, replays, tag)


def _neutral_case(tier=1, plan="gold", floor=140):
    case = _Case()
    case.runtime("PRT-1", "graph", floor)
    case.variant("PVR-1", "fp32", "")
    case.caller("PCL-1", plan)
    case.endpoint("PEP-1", "PRT-1", "PVR-1", "none", tier)
    return case


def _axis_case(accels, precisions, kernels, phases):
    """One endpoint per combination named, every other keyed axis left neutral."""
    case = _Case()
    for position, kernel in enumerate(kernels):
        case.runtime("ART-%d" % (position + 1), kernel, 140)
    for position, precision in enumerate(precisions):
        case.variant("AVR-%d" % (position + 1), precision, "")
    case.caller("ACL-1", "gold")
    index = 0
    for accel in accels:
        for precision_position, _precision in enumerate(precisions):
            for kernel_position, _kernel in enumerate(kernels):
                index += 1
                endpoint_id = case.endpoint("AEP-%02d" % index,
                                            "ART-%d" % (kernel_position + 1),
                                            "AVR-%d" % (precision_position + 1),
                                            accel, 1)
                for phase in phases:
                    for level in (900, 1400, 2100, 3200):
                        case.probe(endpoint_id, "ACL-1", "drain", phase,
                                   140 + level, 400, 0, 0)
    return case


def build_probe(name):
    if name == "gain":
        case = _neutral_case()
        for rows, spans, replays in ((400, 0, 0), (9999, 100, 0), (200, 0, 1),
                                     (150, 0, 2), (9999, 50, 1), (500, 0, 0)):
            case.probe("PEP-1", "PCL-1", "drain", "prefill", 140 + 2400,
                       rows, spans, replays)
        return case
    if name == "accel":
        return _axis_case(["cuda", "rocm", "xla", "npu", "fpga", "wasm", "none"],
                          ["fp32"], ["graph"], ["prefill"])
    if name == "precision":
        return _axis_case(["none"], ["fp32", "fp16", "bf16", "int8"], ["graph"], ["prefill"])
    if name == "phase":
        return _axis_case(["none"], ["fp32"], ["graph"], ["prefill", "decode", "batch"])
    if name == "kernel":
        return _axis_case(["none"], ["fp32"], ["graph", "eager", "fused", "traced"],
                          ["prefill"])
    raise KeyError(name)


def build_state_probe(name):
    if name == "first_difference":
        case = _neutral_case()
        for level in (600, 1100, 1700, 2400, 3200, 4100, 5100):
            case.probe("PEP-1", "PCL-1", "drain", "prefill", 140 + level, 400, 0, 0)
        case.endpoint("PEP-2", "PRT-1", "PVR-1", "none", 1)
        for level in (2600, 2200, 1900, 1700, 1700, 1900):
            case.probe("PEP-2", "PCL-1", "drain", "prefill", 140 + level, 400, 0, 0)
        return case
    if name == "phase_tracks":
        case = _neutral_case()
        for phase, levels in (("prefill", (800, 1500, 2300)),
                              ("decode", (2000, 2600)),
                              ("batch", (1200, 1900, 2700))):
            for level in levels:
                case.probe("PEP-1", "PCL-1", "drain", phase, 140 + level, 400, 0, 0)
        for phase in ("prefill", "decode", "batch"):
            case.probe("PEP-1", "PCL-1", "drain", phase, 140 + 3300, 400, 0, 0)
        return case
    if name == "segment_boundary":
        case = _neutral_case()
        for level in (600, 1100, 1700, 2400):
            case.probe("PEP-1", "PCL-1", "drain", "prefill", 140 + level, 400, 0, 0)
        case.probe("PEP-1", "PCL-1", "reset", "prefill", 140 + 900, 400, 0, 0)
        for level in (1300, 1800, 2500):
            case.probe("PEP-1", "PCL-1", "drain", "prefill", 140 + level, 400, 0, 0)
        return case
    if name == "sentinel":
        case = _neutral_case()
        for level in (800, 1500):
            case.probe("PEP-1", "PCL-1", "drain", "prefill", 140 + level, 400, 0, 0)
        case.probe("PEP-1", "PCL-1", "drain", "prefill", 0, 400, 0, 0, sentinel=True)
        case.probe("PEP-1", "PCL-1", "drain", "prefill", 140 + 2600, 400, 0, 0)
        case.probe("PEP-1", "PCL-1", "drain", "prefill", 0, 400, 0, 0, sentinel=True)
        case.probe("PEP-1", "PCL-1", "drain", "prefill", 140 + 3400, 400, 0, 0)
        return case
    if name == "backlog_step":
        case = _neutral_case()
        for width in (300, 600, 900, 120, 1500):
            case.spend("PEP-1", "PCL-1", width)
            case.target("PEP-1", "PCL-1", "drain", 500)
        return case
    if name == "tier_doubling":
        case = _neutral_case()
        case.endpoint("PEP-2", "PRT-1", "PVR-1", "none", 2)
        case.endpoint("PEP-3", "PRT-1", "PVR-1", "none", 3)
        for endpoint_id in ("PEP-1", "PEP-2", "PEP-3"):
            for width in (300, 600):
                case.spend(endpoint_id, "PCL-1", width)
                case.target(endpoint_id, "PCL-1", "drain", 500)
        return case
    if name == "back_to_back":
        case = _neutral_case()
        case.spend("PEP-1", "PCL-1", 300)
        case.spend("PEP-1", "PCL-1", 300)
        case.target("PEP-1", "PCL-1", "drain", 500)
        case.spend("PEP-1", "PCL-1", 300)
        case.flat("PEP-1", "PCL-1", "abort")
        case.spend("PEP-1", "PCL-1", 300)
        case.target("PEP-1", "PCL-1", "drain", 500)
        return case
    if name == "ceiling":
        case = _neutral_case()
        for _round in range(6):
            case.spend("PEP-1", "PCL-1", 750)
        case.target("PEP-1", "PCL-1", "drain", 500)
        for _round in range(4):
            case.spend("PEP-1", "PCL-1", 1200)
        case.target("PEP-1", "PCL-1", "drain", 500)
        return case
    if name == "replay_record":
        case = _neutral_case()
        case.target("PEP-1", "PCL-1", "drain", 1000, tag="RPL-X")
        case.target("PEP-1", "PCL-1", "drain", 800, tag="RPL-Y")
        case.target("PEP-1", "PCL-1", "drain", 600, tag="RPL-Z")
        case.target("PEP-1", "PCL-1", "drain", 400, tag="RPL-W")
        case.target("PEP-1", "PCL-1", "drain", 350, tag="RPL-X")
        case.target("PEP-1", "PCL-1", "drain", 700, tag="RPL-P")
        case.target("PEP-1", "PCL-1", "drain", 650, tag="RPL-Q")
        case.target("PEP-1", "PCL-1", "drain", 580, tag="RPL-R")
        case.target("PEP-1", "PCL-1", "drain", 520, tag="RPL-S")
        case.target("PEP-1", "PCL-1", "drain", 240, tag="RPL-X")
        # The refund is load-bearing: the credit divides the second RPL-T only,
        # so the record holds that tag at two different scores and the end the
        # lookup reads from becomes decidable (oldest 1000 vs most recent 333).
        case.target("PEP-1", "PCL-1", "drain", 1000, tag="RPL-T")
        case.flat("PEP-1", "PCL-1", "refund")
        case.target("PEP-1", "PCL-1", "drain", 900, tag="RPL-T")
        case.target("PEP-1", "PCL-1", "drain", 300, tag="RPL-T")
        return case
    if name == "credit":
        case = _neutral_case()
        case.target("PEP-1", "PCL-1", "drain", 900)
        case.flat("PEP-1", "PCL-1", "refund")
        case.target("PEP-1", "PCL-1", "drain", 900)
        case.target("PEP-1", "PCL-1", "drain", 900)
        case.flat("PEP-1", "PCL-1", "refund")
        case.target("PEP-1", "PCL-1", "drain", 902)
        return case
    if name == "shift_wide_budget":
        case = _neutral_case()
        case.endpoint("PEP-2", "PRT-1", "PVR-1", "none", 1)
        # The two endpoints interleave so the running figure each segment
        # boundary reads carries the other endpoint's scores too.  Probes after
        # a boundary are written as absolute meters because _Case does not
        # mirror the budget a boundary installs.
        case.target("PEP-2", "PCL-1", "drain", 900)
        case.target("PEP-2", "PCL-1", "drain", 800)
        case.target("PEP-1", "PCL-1", "drain", 700)
        case.probe("PEP-1", "PCL-1", "reset", "prefill", 140 + 1200, 400, 0, 0)
        case.probe("PEP-1", "PCL-1", "drain", "prefill", 140 + 2600, 400, 0, 0)
        case.target("PEP-2", "PCL-1", "drain", 600)
        case.probe("PEP-2", "PCL-1", "reset", "prefill", 140 + 1500, 400, 0, 0)
        case.probe("PEP-2", "PCL-1", "drain", "prefill", 140 + 3100, 400, 0, 0)
        case.probe("PEP-1", "PCL-1", "drain", "prefill", 140 + 3400, 400, 0, 0)
        return case
    if name == "ladder_order":
        case = _neutral_case(plan="trial")
        case.spend("PEP-1", "PCL-1", 600)
        case.target("PEP-1", "PCL-1", "abort", 20)
        case.target("PEP-1", "PCL-1", "reset", 20)
        case.endpoint("PEP-2", "PRT-1", "PVR-1", "none", 1)
        case.spend("PEP-2", "PCL-1", 600)
        case.target("PEP-2", "PCL-1", "drain", 20)
        case.endpoint("PEP-3", "PRT-1", "PVR-1", "none", 1)
        case.spend("PEP-3", "PCL-1", 600)
        case.target("PEP-3", "PCL-1", "drain", 500)
        case.endpoint("PEP-4", "PRT-1", "PVR-1", "none", 1)
        case.target("PEP-4", "PCL-1", "refund", 20)
        return case
    if name == "plan_tolerances":
        case = _Case()
        case.runtime("PRT-1", "graph", 140)
        case.variant("PVR-1", "fp32", "")
        for position, (caller, plan, limit) in enumerate(
                (("PCL-1", "gold", 60), ("PCL-2", "silver", 38),
                 ("PCL-3", "bronze", 17), ("PCL-4", "trial", 0))):
            case.caller(caller, plan)
            endpoint_id = case.endpoint("PEP-%d" % (position + 1), "PRT-1", "PVR-1", "none", 1)
            for level in (limit - 2, limit - 1, limit, limit + 1):
                if level < 0:
                    continue
                if level > 0:
                    case.spend(endpoint_id, caller, 30 * level)
                case.target(endpoint_id, caller, "drain", 500)
        return case
    if name == "counted_verdicts":
        case = _neutral_case()
        case.target("PEP-1", "PCL-1", "drain", 1000)
        case.target("PEP-1", "PCL-1", "drain", 30)
        case.target("PEP-1", "PCL-1", "reset", 900)
        case.probe("PEP-1", "PCL-1", "abort", "prefill", 140 + 1000, 400, 0, 0)
        case.endpoint("PEP-2", "PRT-1", "PVR-1", "none", 1)
        case.spend("PEP-2", "PCL-1", 600)
        case.target("PEP-2", "PCL-1", "drain", 800)
        return case
    if name == "dispositions":
        case = _Case()
        case.runtime("PRT-1", "graph", 140)
        case.variant("PVR-1", "fp32", "")
        case.caller("PCL-1", "gold")
        for position, rejects in enumerate((2, 3, 4)):
            endpoint_id = case.endpoint("PEP-%d" % (position + 1), "PRT-1", "PVR-1", "none", 1)
            for _round in range(rejects):
                case.target(endpoint_id, "PCL-1", "drain", 20)
            case.target(endpoint_id, "PCL-1", "drain", 700)
        for position, level in enumerate((38, 40, 41, 45)):
            endpoint_id = case.endpoint("PEP-%d" % (position + 4), "PRT-1", "PVR-1", "none", 1)
            case.target(endpoint_id, "PCL-1", "drain", 700)
            case.spend(endpoint_id, "PCL-1", 30 * level)
        return case
    raise KeyError(name)


ACCELS = ["cuda", "rocm", "xla", "npu", "fpga", "wasm", "none"]
PRECISIONS = ["fp32", "fp16", "bf16", "int8"]
KERNELS = ["graph", "eager", "fused", "traced"]
PLANS = ["gold", "silver", "bronze", "trial"]
MODES = ["serve", "reset", "drain", "refund", "abort"]
PHASES = ["prefill", "decode", "batch"]


def build_unseen(seed):
    """A shift the shipped directory has never seen.  Every rule the gate
    carries fires somewhere in it, so a single wrong constant fails the run."""
    rng = random.Random(seed)
    case = _Case()
    for position, kernel in enumerate(KERNELS):
        case.runtime("URT-%d" % (position + 1), kernel, rng.choice([80, 110, 140, 190]))
    for position, precision in enumerate(PRECISIONS):
        case.variant("UVR-%d" % (position + 1), precision, "")
    for position in range(3):
        case.variant("UVR-%d" % (position + 5), PRECISIONS[position],
                     "UVR-%d" % (((position + 2) % 4) + 1))
    for position, plan in enumerate(PLANS):
        case.caller("UCL-%d" % (position + 1), plan)
    index = [0]

    def fresh(runtime="URT-1", variant="UVR-1", accel="none", tier=1):
        index[0] += 1
        return case.endpoint("UEP-%02d" % index[0], runtime, variant, accel, tier)

    def climb(endpoint_id, caller, steps, start=None):
        levels = {}
        for _step in range(steps):
            phase = rng.choice(PHASES)
            level = levels.get(phase)
            if level is None:
                level = start if start is not None else rng.randint(400, 1100)
            level = level + rng.randint(80, 900)
            base = case.state[endpoint_id]["budget"]
            while case.would_repeat(endpoint_id, phase, base + level):
                level = level + 1
            levels[phase] = level
            spans = rng.choice([0, 0, 0, 50, 100])
            rows = 9999 if spans else rng.choice([200, 300, 400, 500, 800])
            case.probe(endpoint_id, caller, "drain", phase, base + level,
                       rows, spans, rng.randint(0, 3))

    # every accelerator, precision and kernel, crossed so no endpoint is a lone probe
    for position, accel in enumerate(ACCELS):
        endpoint_id = fresh("URT-%d" % ((position % 4) + 1),
                            "UVR-%d" % ((position % 7) + 1),
                            accel, (position % 3) + 1)
        climb(endpoint_id, "UCL-%d" % ((position % 4) + 1), rng.randint(4, 6))
    for position in range(4):
        endpoint_id = fresh("URT-%d" % (position + 1),
                            "UVR-%d" % (position + 5 if position < 3 else 2),
                            ACCELS[(position + 2) % 7], 1)
        climb(endpoint_id, "UCL-1", rng.randint(3, 5))

    # scores either side of every band edge.  The levels rise, because a fall of
    # exactly one encodes to the reserved meter value and would be resolved as a
    # repeat rather than as the level asked for.
    for edge in (300, 150, 55):
        endpoint_id = fresh()
        for score in (edge - 1, edge, edge + 1, edge + 50):
            case.target(endpoint_id, "UCL-1", "drain", score)

    # the four plan tolerances, met exactly and then passed by one
    for position, limit in enumerate((60, 38, 17, 0)):
        endpoint_id = fresh()
        caller = "UCL-%d" % (position + 1)
        for level in (limit, limit + 1):
            if level > 0:
                case.spend(endpoint_id, caller, 30 * level)
            case.target(endpoint_id, caller, "drain", rng.choice([400, 600, 800]))

    # the backlog arithmetic: the tier, the back to back extra, the ceiling
    for tier in (1, 2, 3):
        endpoint_id = fresh(tier=tier)
        case.spend(endpoint_id, "UCL-1", 300)
        case.target(endpoint_id, "UCL-1", "drain", 500)
        case.spend(endpoint_id, "UCL-1", 600)
        case.spend(endpoint_id, "UCL-1", 600)
        case.target(endpoint_id, "UCL-1", "drain", 600)
    endpoint_id = fresh()
    for _round in range(6):
        case.spend(endpoint_id, "UCL-1", 900)
    case.target(endpoint_id, "UCL-1", "drain", 700)

    # a mode that breaks the run of serves, so the extra is not charged after it
    endpoint_id = fresh()
    case.spend(endpoint_id, "UCL-1", 300)
    case.flat(endpoint_id, "UCL-1", "abort")
    case.spend(endpoint_id, "UCL-1", 300)
    case.target(endpoint_id, "UCL-1", "drain", 550)

    # the bounded trailing record: one tag comes back four probes later and one
    # comes back five probes later, so a record one entry short and a record one
    # entry long both report a different score here
    endpoint_id = fresh()
    scores = (1000, 800, 600, 400, 720, 660, 580, 520, 460, 410, 300, 240)
    for position, score in enumerate(scores):
        if position in (0, 4):
            tag = "URP-X"
        elif position in (5, 10):
            tag = "URP-Y"
        else:
            tag = "URP-%d" % position
        case.target(endpoint_id, "UCL-1", "drain", score, tag=tag)

    # the end of the record the lookup reads from: the refund is load-bearing,
    # because the credit divides the middle reading only, so the record holds
    # URP-Z at two different scores when the third one resolves
    endpoint_id = fresh()
    case.target(endpoint_id, "UCL-1", "drain", 1000, tag="URP-Z")
    case.flat(endpoint_id, "UCL-1", "refund")
    case.target(endpoint_id, "UCL-1", "drain", 900, tag="URP-Z")
    case.target(endpoint_id, "UCL-1", "drain", 300, tag="URP-Z")

    # the one shot credit
    endpoint_id = fresh()
    case.target(endpoint_id, "UCL-1", "drain", 900)
    case.flat(endpoint_id, "UCL-1", "refund")
    case.target(endpoint_id, "UCL-1", "drain", 900)
    case.target(endpoint_id, "UCL-1", "drain", 701)

    # segment boundaries, spread so the budget they install differs
    for _round in range(3):
        endpoint_id = fresh()
        climb(endpoint_id, "UCL-1", 3)
        case.probe(endpoint_id, "UCL-1", "reset", "prefill",
                   case.state[endpoint_id]["budget"] + rng.randint(500, 1100),
                   400, 0, 0)
        climb(endpoint_id, "UCL-1", 3)

    # the reserved meter value
    endpoint_id = fresh()
    climb(endpoint_id, "UCL-1", 3)
    case.probe(endpoint_id, "UCL-1", "drain", "prefill", 0, 400, 0, 0, sentinel=True)
    climb(endpoint_id, "UCL-1", 2)
    case.probe(endpoint_id, "UCL-1", "drain", "decode", 0, 400, 0, 0, sentinel=True)

    # the accumulation carried per phase as well as per endpoint: the same
    # endpoint climbing on all three phases at once, so a single accumulator
    # reports different meters
    for _round in range(2):
        endpoint_id = fresh()
        base = case.state[endpoint_id]["budget"]
        levels = {"prefill": 700, "decode": 1300, "batch": 2100}
        for _step in range(4):
            for phase in PHASES:
                levels[phase] = levels[phase] + rng.randint(90, 600)
                while case.would_repeat(endpoint_id, phase, base + levels[phase]):
                    levels[phase] = levels[phase] + 1
                case.probe(endpoint_id, "UCL-1", "drain", phase,
                           base + levels[phase], 400, 0, 0)

    # the coarse accelerator, which records its meter on a wider scale
    for _round in range(2):
        endpoint_id = fresh(runtime="URT-%d" % rng.randint(1, 4),
                            variant="UVR-%d" % rng.randint(1, 4),
                            accel="fpga")
        climb(endpoint_id, "UCL-1", 4, start=rng.randint(150, 500))

    # a subtracting stage followed by an adding one, which is the only place the
    # clamp between stages shows
    for accel in ("rocm", "wasm"):
        endpoint_id = fresh(runtime="URT-2", variant="UVR-2", accel=accel)
        base = case.state[endpoint_id]["budget"]
        for delta in (5, 8, 11, 15):
            case.probe(endpoint_id, "UCL-1", "drain", "batch", base + delta, 400, 0, 0)

    # strikes and both dispositions
    for rejects in (2, 3, 4):
        endpoint_id = fresh()
        for _round in range(rejects):
            case.target(endpoint_id, "UCL-1", "drain", 20)
        case.target(endpoint_id, "UCL-1", "drain", 700)
    # 40 sits exactly on the throttle figure, so a solver reading the comparison
    # as inclusive rather than strict is caught here
    for level in (38, 40, 41, 45):
        endpoint_id = fresh()
        case.target(endpoint_id, "UCL-1", "drain", 700)
        case.spend(endpoint_id, "UCL-1", 30 * level)

    # the two tie breaks
    top = rng.choice([70000, 80000, 90000])
    for _twin in range(2):
        endpoint_id = fresh()
        case.target(endpoint_id, "UCL-1", "drain", top, tag="UTI-%s-A" % endpoint_id)
        case.target(endpoint_id, "UCL-1", "drain", top, tag="UTI-%s-B" % endpoint_id)
        case.target(endpoint_id, "UCL-1", "drain", 500, tag="UTI-%s-C" % endpoint_id)

    # filler, so no two generated shifts look alike
    for _extra in range(rng.randint(3, 6)):
        endpoint_id = fresh("URT-%d" % rng.randint(1, 4),
                            "UVR-%d" % rng.randint(1, 7),
                            rng.choice(ACCELS), rng.randint(1, 3))
        climb(endpoint_id, "UCL-%d" % rng.randint(1, 4), rng.randint(3, 6))
    return case


def build_empty():
    case = _Case()
    case.runtime("ERT-1", "graph", 120)
    case.variant("EVR-1", "fp32", "")
    case.caller("ECL-1", "gold")
    return case


def write_case(data_dir, case, seed=17):
    os.makedirs(data_dir, exist_ok=True)
    rows = list(case.probes)
    random.Random(seed).shuffle(rows)
    # endpoints.csv ships in an arbitrary line order the way probes.bin does,
    # so a program that emits its rows in file order rather than sorted by
    # endpoint is caught rather than passed.
    endpoint_rows = list(case.endpoints)
    random.Random(seed + 1).shuffle(endpoint_rows)
    with open(os.path.join(data_dir, "runtimes.csv"), "w", encoding="utf-8", newline="") as handle:
        handle.write("runtime,kernel,floor\n")
        for name, kernel, floor in case.runtimes:
            handle.write("%s,%s,%d\n" % (name, kernel, floor))
    with open(os.path.join(data_dir, "variants.csv"), "w", encoding="utf-8", newline="") as handle:
        handle.write("variant,precision,base\n")
        for name, precision, base in case.variants:
            handle.write("%s,%s,%s\n" % (name, precision, base))
    with open(os.path.join(data_dir, "callers.csv"), "w", encoding="utf-8", newline="") as handle:
        handle.write("caller,plan\n")
        for name, plan in case.callers:
            handle.write("%s,%s\n" % (name, plan))
    with open(os.path.join(data_dir, "endpoints.csv"), "w", encoding="utf-8", newline="") as handle:
        handle.write("endpoint,runtime,variant,accel,tier\n")
        for endpoint_id, runtime, variant, accel, tier in endpoint_rows:
            handle.write("%s,%s,%s,%s,%d\n" % (endpoint_id, runtime, variant, accel, tier))
    with open(os.path.join(data_dir, "probes.bin"), "wb") as handle:
        handle.write(encode_probes(rows))


APP_ROOT = os.environ.get("APP_ROOT", "/app")
OUT_DIR = os.path.join(APP_ROOT, "out")
SCRIPT = os.path.join(OUT_DIR, "gate.py")

CLASS_HEADER = "precision,endpoints,probes,score_total,flagged"

VERDICT_KEYS = ["backlog_before", "band", "caller", "endpoint", "mode", "phase",
                "score", "seq", "tag", "verdict"]
ENDPOINT_KEYS = ["backlog_end", "bands", "budget_end", "counted", "disposition",
                 "endpoint", "flagged", "probes", "score_total", "strikes",
                 "top_score", "top_tag"]
SHIFT_KEYS = ["by_band", "by_verdict", "endpoints", "probes", "quarantined",
              "score_total", "top_endpoint"]

REPORT_NAMES = ("verdicts.jsonl", "endpoints.json", "precision.csv", "shift.json")

SHAPE_SEED = 5310001
FORM_SEED = 5310002
CORPUS_SEEDS = [8820011, 8820022, 8820033, 8820044,
                8820055, 8820066, 8820077, 8820088]

_TMP_ROOT = os.path.realpath(tempfile.gettempdir())
_RUNS = {}


def _inside_sandbox(path):
    resolved = os.path.realpath(path)
    return resolved != _TMP_ROOT and resolved.startswith(_TMP_ROOT + os.sep)


def _open_up(path):
    node = os.path.realpath(path)
    while _inside_sandbox(node):
        try:
            os.chmod(node, (os.stat(node).st_mode & 0o7777) | 0o111 | 0o044)
        except OSError:
            pass
        node = os.path.dirname(node)


def _grant_read(path):
    try:
        extra = 0o055 if os.path.isdir(path) else 0o044
        os.chmod(path, (os.stat(path).st_mode & 0o7777) | extra)
    except OSError:
        pass


def _demoted(argv):
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups", "--"] + argv
    return argv


def _terminate(proc):
    # The group id is proc.pid (start_new_session) and outlives the reaped leader.
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, AttributeError):
        pass
    try:
        proc.kill()
    except OSError:
        pass
    proc.wait()


def _launch(argv, scratch, budget=25):
    stdout_path = os.path.join(scratch, "stdout.txt")
    stderr_path = os.path.join(scratch, "stderr.txt")
    env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": scratch,
        "TMPDIR": scratch,
        "LC_ALL": "C",
    }
    with open(stdout_path, "wb") as sink, open(stderr_path, "wb") as errsink:
        proc = subprocess.Popen(
            _demoted(argv),
            stdout=sink,
            stderr=errsink,
            stdin=subprocess.DEVNULL,
            env=env,
            start_new_session=True,
        )
        try:
            code = proc.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            raise AssertionError("the delivered program ran past its time budget")
        finally:
            _terminate(proc)
    with open(stderr_path, "rb") as handle:
        return code, handle.read().decode("utf-8", "replace")


def _case_for(label, seed):
    if label.startswith("probe:"):
        return build_probe(label[6:])
    if label.startswith("state:"):
        return build_state_probe(label[6:])
    if label == "empty":
        return build_empty()
    return build_unseen(seed)


def _reference(data_dir):
    verdicts, endpoint_rows, class_rows, shift = derive(data_dir)
    return {
        "verdicts.jsonl": render_verdicts(verdicts),
        "endpoints.json": render_document({"endpoints": endpoint_rows}),
        "precision.csv": render_classes(class_rows),
        "shift.json": render_document(shift),
    }


def _materialise(label, seed):
    work = tempfile.mkdtemp(prefix="igr-")
    data = os.path.join(work, "data")
    out = os.path.join(work, "out")
    scratch = os.path.join(work, "scratch")
    write_case(data, _case_for(label, seed), seed)
    os.makedirs(out)
    os.makedirs(scratch)
    expected = _reference(data)
    for node in (work, data, out, scratch):
        os.chmod(node, 0o777)
    for name in os.listdir(data):
        os.chmod(os.path.join(data, name), 0o644)
    return work, data, out, scratch, expected


def _run(label, seed):
    if label in _RUNS:
        return _RUNS[label]
    assert os.path.isfile(SCRIPT), "no reusable program was delivered"
    _open_up(SCRIPT)
    _grant_read(APP_ROOT)
    _grant_read(OUT_DIR)
    _grant_read(SCRIPT)
    work, data, out, scratch, expected = _materialise(label, seed)
    code, err = _launch([sys.executable, SCRIPT, data, out], scratch)
    _RUNS[label] = (data, out, scratch, code, err, expected)
    return _RUNS[label]


def _artifact(out, name):
    path = os.path.join(out, name)
    assert os.path.isfile(path), "the program wrote no %s" % name
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8")


def _ledger(label, seed):
    _data, out, _scratch, code, err, expected = _run(label, seed)
    assert code == 0, "the program exited %s: %s" % (code, err[-400:])
    for name in REPORT_NAMES:
        assert _artifact(out, name) == expected[name], "%s disagrees with the reference" % name


def _probe(name):
    _data, out, _scratch, code, err, expected = _run("probe:" + name, 13)
    assert code == 0, "the program exited %s: %s" % (code, err[-400:])
    assert _artifact(out, "verdicts.jsonl") == expected["verdicts.jsonl"]


def _state(name):
    _data, out, _scratch, code, err, expected = _run("state:" + name, 13)
    assert code == 0, "the program exited %s: %s" % (code, err[-400:])
    assert _artifact(out, "verdicts.jsonl") == expected["verdicts.jsonl"]


def _state_rollup(name):
    _data, out, _scratch, code, err, expected = _run("state:" + name, 13)
    assert code == 0, "the program exited %s: %s" % (code, err[-400:])
    for report in REPORT_NAMES:
        assert _artifact(out, report) == expected[report], (
            "%s disagrees with the reference" % report)


def _delivered_source():
    assert os.path.isfile(SCRIPT), "no reusable program was delivered"
    _grant_read(SCRIPT)
    with open(SCRIPT, "rb") as handle:
        return handle.read().decode("utf-8", "replace")


def _bind(workspace):
    global APP_ROOT, OUT_DIR, SCRIPT
    APP_ROOT = os.environ.get("APP_ROOT", str(workspace))
    OUT_DIR = os.path.join(APP_ROOT, "out")
    SCRIPT = os.path.join(OUT_DIR, "gate.py")


def _holds(workspace, check):
    _bind(workspace)
    try:
        check()
    except Exception:
        return False
    return True


def _check_program_writes_the_four_reports_from_two_directory_arguments():
    """POSITIVE: driven with an input and an output directory the program writes the four documented reports."""
    _data, out, _scratch, code, err, _expected = _run("shape", SHAPE_SEED)
    assert code == 0, "the program exited %s: %s" % (code, err[-400:])
    rows = [line for line in _artifact(out, "verdicts.jsonl").splitlines() if line]
    assert rows
    for line in rows:
        assert sorted(json.loads(line)) == VERDICT_KEYS
    document = json.loads(_artifact(out, "endpoints.json"))
    assert sorted(document) == ["endpoints"]
    assert document["endpoints"]
    for row in document["endpoints"]:
        assert sorted(row) == ENDPOINT_KEYS
    body = _artifact(out, "precision.csv").splitlines()
    assert body[0] == CLASS_HEADER
    assert len(body) > 1
    for line in body[1:]:
        cells = line.split(",")
        assert len(cells) == 5
        for cell in cells[1:]:
            assert cell.isdigit()
    assert sorted(json.loads(_artifact(out, "shift.json"))) == SHIFT_KEYS


def _check_report_serialization_carries_the_documented_byte_form():
    """POSITIVE: each report file is the documented serialization of the content it carries."""
    _data, out, _scratch, code, err, _expected = _run("form", FORM_SEED)
    assert code == 0, "the program exited %s: %s" % (code, err[-400:])
    text = _artifact(out, "verdicts.jsonl")
    rows = [json.loads(line) for line in text.splitlines() if line]
    assert rows
    assert text == render_verdicts(rows)
    for name in ("endpoints.json", "shift.json"):
        body = _artifact(out, name)
        assert body == render_document(json.loads(body))


def _check_empty_shift_reports_are_written():
    """POSITIVE: driven over a shift holding no endpoint and no probe the program writes the four documented reports."""
    _ledger("empty", 0)


def _check_throughput_normalisation_gain():
    """POSITIVE: the batch width and the throughput normalisation match the reference across six probe shapes."""
    _probe("gain")


def _check_precision_responses_match_the_reference():
    """POSITIVE: every one of the four precision values reduces the way the reference reduces it."""
    _probe("precision")


def _check_accelerator_responses_match_the_reference():
    """POSITIVE: every one of the seven accelerator values reduces the way the reference reduces it."""
    _probe("accel")


def _check_phase_responses_match_the_reference():
    """POSITIVE: every one of the three phases reduces the way the reference reduces it."""
    _probe("phase")


def _check_kernel_responses_match_the_reference():
    """POSITIVE: every one of the four kernels reduces the way the reference reduces it."""
    _probe("kernel")


def _check_meter_accumulates_as_a_first_difference():
    """POSITIVE: the meter column is accumulated into the meter the way the reference accumulates it, on a rising and on a falling endpoint."""
    _state("first_difference")


def _check_meter_accumulates_per_phase():
    """POSITIVE: one endpoint serving all three phases carries a separate accumulation for each of them, the way the reference carries them."""
    _state("phase_tracks")


def _check_segment_boundary_resets_the_accumulator():
    """POSITIVE: the mode that opens a segment restarts the accumulation the way the reference restarts it."""
    _state("segment_boundary")


def _check_reserved_meter_repeats_the_previous_probe():
    """POSITIVE: a probe carrying the reserved meter takes the meter of the probe before it and leaves the accumulation alone."""
    _state("sentinel")


def _check_backlog_step_per_serve():
    """POSITIVE: the backlog a serve leaves behind matches the reference across five batch widths."""
    _state("backlog_step")


def _check_backlog_doubles_on_the_marked_tier():
    """POSITIVE: the same serves on a tier 1, a tier 2 and a tier 3 endpoint leave the reference backlogs."""
    _state("tier_doubling")


def _check_back_to_back_serve_carries_its_extra():
    """POSITIVE: a serve that directly follows another leaves the reference backlog and a broken run does not."""
    _state("back_to_back")


def _check_backlog_stops_at_its_ceiling():
    """POSITIVE: repeated serves leave the reference backlog once the ceiling is reached."""
    _state("ceiling")


def _check_repeated_tag_takes_the_recorded_score():
    """POSITIVE: a tag that comes back inside the trailing record takes its earlier score and one that has dropped out does not."""
    _state("replay_record")


def _check_credit_applies_once():
    """POSITIVE: the armed credit reduces one score and the probe after it is reduced in full."""
    _state("credit")


def _check_segment_budget_reads_the_whole_shift():
    """POSITIVE: the budget a segment boundary installs is derived from the scores resolved across the whole shift, not from the boundary's own endpoint."""
    _state("shift_wide_budget")


def _check_verdict_ladder_takes_the_first_condition():
    """POSITIVE: a probe meeting several ladder conditions at once takes the reference verdict."""
    _state("ladder_order")


def _check_plan_tolerances_separate_flagged_from_ok():
    """POSITIVE: each of the four caller plans flags at the reference backlog and stays ok below it."""
    _state("plan_tolerances")


def _check_endpoint_total_counts_the_reference_verdicts():
    """POSITIVE: the per endpoint rollup counts the reference set of verdicts into its totals."""
    _state_rollup("counted_verdicts")


def _check_endpoint_dispositions_follow_strikes_and_backlog():
    """POSITIVE: the per endpoint disposition matches the reference across the strike count and the backlog held at the end."""
    _state_rollup("dispositions")


def _check_full_ledger_on_unseen_shift_alpha():
    """POSITIVE: all four reports match the reference on an unseen shift."""
    _ledger("alpha", CORPUS_SEEDS[0])


def _check_full_ledger_on_unseen_shift_bravo():
    """POSITIVE: all four reports match the reference on an unseen shift."""
    _ledger("bravo", CORPUS_SEEDS[1])


def _check_full_ledger_on_unseen_shift_charlie():
    """POSITIVE: all four reports match the reference on an unseen shift."""
    _ledger("charlie", CORPUS_SEEDS[2])


def _check_full_ledger_on_unseen_shift_delta():
    """POSITIVE: all four reports match the reference on an unseen shift."""
    _ledger("delta", CORPUS_SEEDS[3])


def _check_full_ledger_on_unseen_shift_echo():
    """POSITIVE: all four reports match the reference on an unseen shift."""
    _ledger("echo", CORPUS_SEEDS[4])


def _check_full_ledger_on_unseen_shift_foxtrot():
    """POSITIVE: all four reports match the reference on an unseen shift."""
    _ledger("foxtrot", CORPUS_SEEDS[5])


def _check_full_ledger_on_unseen_shift_golf():
    """POSITIVE: all four reports match the reference on an unseen shift."""
    _ledger("golf", CORPUS_SEEDS[6])


def _check_full_ledger_on_unseen_shift_hotel():
    """POSITIVE: all four reports match the reference on an unseen shift."""
    _ledger("hotel", CORPUS_SEEDS[7])


def _check_negative_hardcoded_sample_answers():
    """NEGATIVE: the delivered program carries identifiers of the recorded shift as literal answers."""
    source = _delivered_source()
    marks = sum(1 for index in range(1, 60) if ("\"MEP-%02d\"" % index) in source
                or ("'MEP-%02d'" % index) in source)
    assert marks >= 5, "the program does not carry recorded endpoint identifiers"


def _check_negative_third_party_dependency():
    """NEGATIVE: the delivered program imports a module outside the standard library."""
    source = _delivered_source()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        raise AssertionError("the delivered program does not parse, so this stays unproven")
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                names.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            target = node.func
            if isinstance(target, ast.Name) and target.id == "__import__":
                if node.args and isinstance(node.args[0], ast.Constant):
                    if isinstance(node.args[0].value, str):
                        names.add(node.args[0].value.split(".")[0])
    outside = sorted(name for name in names if name and name not in sys.stdlib_module_names)
    assert outside, "the program imports only the standard library"


def _check_negative_filename_dependent_behaviour():
    """NEGATIVE: the delivered program changes what it reports when the input directory is renamed."""
    data, out, _scratch, code, _err, _expected = _run("alpha", CORPUS_SEEDS[0])
    assert code == 0, "the program left no output to compare, so this stays unproven"
    first = _artifact(out, "verdicts.jsonl")
    work = tempfile.mkdtemp(prefix="igr-rename-")
    other = os.path.join(work, "out")
    control = os.path.join(work, "control")
    scratch = os.path.join(work, "scratch")
    moved = os.path.join(work, "a-different-name")
    shutil.copytree(data, moved)
    os.makedirs(other)
    os.makedirs(control)
    os.makedirs(scratch)
    for node in (work, moved, other, control, scratch):
        os.chmod(node, 0o777)
    for name in os.listdir(moved):
        os.chmod(os.path.join(moved, name), 0o644)

    # A control run over the ORIGINAL directory first.  Only when the program
    # agrees with itself there can a later difference be blamed on the name of
    # the directory; a program that simply reports differently every run is
    # already penalised by negative_nondeterministic_output, and
    # charging it here as well would punish one act twice.
    steady, _err = _launch([sys.executable, SCRIPT, data, control], scratch)
    assert steady == 0, "the program left no output to compare, so this stays unproven"
    assert _artifact(control, "verdicts.jsonl") == first, (
        "the program reports differently run to run, so the directory name is unproven")

    again, _err = _launch([sys.executable, SCRIPT, moved, other], scratch)
    assert again == 0, "the program left no output to compare, so this stays unproven"
    assert _artifact(other, "verdicts.jsonl") != first, (
        "the program reports the same verdicts whatever the directory is called")


def _check_negative_nondeterministic_output():
    """NEGATIVE: five runs of the delivered program over one input directory disagree with each other."""
    data, out, scratch, code, _err, _expected = _run("bravo", CORPUS_SEEDS[1])
    assert code == 0, "the program left no output to compare, so this stays unproven"
    first = [_artifact(out, name) for name in REPORT_NAMES]
    work = tempfile.mkdtemp(prefix="igr-repeat-")
    os.chmod(work, 0o777)
    for attempt in range(5):
        again = os.path.join(work, "out-%d" % attempt)
        os.makedirs(again)
        os.chmod(again, 0o777)
        code, _err = _launch([sys.executable, SCRIPT, data, again], scratch)
        assert code == 0, "the program left no output to compare, so this stays unproven"
        if [_artifact(again, name) for name in REPORT_NAMES] != first:
            return
    assert False, "every run agreed with every other run"


@criterion(description="driven with an input and an output directory the program writes the four documented reports")
def program_writes_the_four_reports_from_two_directory_arguments(workspace):
    return _holds(workspace, _check_program_writes_the_four_reports_from_two_directory_arguments)


@criterion(description="each report file is the documented serialization of the content it carries")
def report_serialization_carries_the_documented_byte_form(workspace):
    return _holds(workspace, _check_report_serialization_carries_the_documented_byte_form)


@criterion(description="driven over a shift holding no endpoint and no probe the program writes the four documented reports")
def empty_shift_reports_are_written(workspace):
    return _holds(workspace, _check_empty_shift_reports_are_written)


@criterion(description="the batch width and the throughput normalisation match the reference across six probe shapes")
def throughput_normalisation_gain(workspace):
    return _holds(workspace, _check_throughput_normalisation_gain)


@criterion(description="every one of the four precision values reduces the way the reference reduces it")
def precision_responses_match_the_reference(workspace):
    return _holds(workspace, _check_precision_responses_match_the_reference)


@criterion(description="every one of the seven accelerator values reduces the way the reference reduces it")
def accelerator_responses_match_the_reference(workspace):
    return _holds(workspace, _check_accelerator_responses_match_the_reference)


@criterion(description="every one of the three phases reduces the way the reference reduces it")
def phase_responses_match_the_reference(workspace):
    return _holds(workspace, _check_phase_responses_match_the_reference)


@criterion(description="every one of the four kernels reduces the way the reference reduces it")
def kernel_responses_match_the_reference(workspace):
    return _holds(workspace, _check_kernel_responses_match_the_reference)


@criterion(description="the meter column is accumulated into the meter the way the reference accumulates it, on a rising and on a falling endpoint")
def meter_accumulates_as_a_first_difference(workspace):
    return _holds(workspace, _check_meter_accumulates_as_a_first_difference)


@criterion(description="one endpoint serving all three phases carries a separate accumulation for each of them, the way the reference carries them")
def meter_accumulates_per_phase(workspace):
    return _holds(workspace, _check_meter_accumulates_per_phase)


@criterion(description="the mode that opens a segment restarts the accumulation the way the reference restarts it")
def segment_boundary_resets_the_accumulator(workspace):
    return _holds(workspace, _check_segment_boundary_resets_the_accumulator)


@criterion(description="a probe carrying the reserved meter takes the meter of the probe before it and leaves the accumulation alone")
def reserved_meter_repeats_the_previous_probe(workspace):
    return _holds(workspace, _check_reserved_meter_repeats_the_previous_probe)


@criterion(description="the backlog a serve leaves behind matches the reference across five batch widths")
def backlog_step_per_serve(workspace):
    return _holds(workspace, _check_backlog_step_per_serve)


@criterion(description="the same serves on a tier 1, a tier 2 and a tier 3 endpoint leave the reference backlogs")
def backlog_doubles_on_the_marked_tier(workspace):
    return _holds(workspace, _check_backlog_doubles_on_the_marked_tier)


@criterion(description="a serve that directly follows another leaves the reference backlog and a broken run does not")
def back_to_back_serve_carries_its_extra(workspace):
    return _holds(workspace, _check_back_to_back_serve_carries_its_extra)


@criterion(description="repeated serves leave the reference backlog once the ceiling is reached")
def backlog_stops_at_its_ceiling(workspace):
    return _holds(workspace, _check_backlog_stops_at_its_ceiling)


@criterion(description="a tag that comes back inside the trailing record takes its earlier score and one that has dropped out does not")
def repeated_tag_takes_the_recorded_score(workspace):
    return _holds(workspace, _check_repeated_tag_takes_the_recorded_score)


@criterion(description="the armed credit reduces one score and the probe after it is reduced in full")
def credit_applies_once(workspace):
    return _holds(workspace, _check_credit_applies_once)


@criterion(description="the budget a segment boundary installs is derived from the scores resolved across the whole shift, not from the boundary's own endpoint")
def segment_budget_reads_the_whole_shift(workspace):
    return _holds(workspace, _check_segment_budget_reads_the_whole_shift)


@criterion(description="a probe meeting several ladder conditions at once takes the reference verdict")
def verdict_ladder_takes_the_first_condition(workspace):
    return _holds(workspace, _check_verdict_ladder_takes_the_first_condition)


@criterion(description="each of the four caller plans flags at the reference backlog and stays ok below it")
def plan_tolerances_separate_flagged_from_ok(workspace):
    return _holds(workspace, _check_plan_tolerances_separate_flagged_from_ok)


@criterion(description="the per endpoint rollup counts the reference set of verdicts into its totals")
def endpoint_total_counts_the_reference_verdicts(workspace):
    return _holds(workspace, _check_endpoint_total_counts_the_reference_verdicts)


@criterion(description="the per endpoint disposition matches the reference across the strike count and the backlog held at the end")
def endpoint_dispositions_follow_strikes_and_backlog(workspace):
    return _holds(workspace, _check_endpoint_dispositions_follow_strikes_and_backlog)


@criterion(description="all four reports match the reference on unseen shift alpha")
def full_ledger_on_unseen_shift_alpha(workspace):
    return _holds(workspace, _check_full_ledger_on_unseen_shift_alpha)


@criterion(description="all four reports match the reference on unseen shift bravo")
def full_ledger_on_unseen_shift_bravo(workspace):
    return _holds(workspace, _check_full_ledger_on_unseen_shift_bravo)


@criterion(description="all four reports match the reference on unseen shift charlie")
def full_ledger_on_unseen_shift_charlie(workspace):
    return _holds(workspace, _check_full_ledger_on_unseen_shift_charlie)


@criterion(description="all four reports match the reference on unseen shift delta")
def full_ledger_on_unseen_shift_delta(workspace):
    return _holds(workspace, _check_full_ledger_on_unseen_shift_delta)


@criterion(description="all four reports match the reference on unseen shift echo")
def full_ledger_on_unseen_shift_echo(workspace):
    return _holds(workspace, _check_full_ledger_on_unseen_shift_echo)


@criterion(description="all four reports match the reference on unseen shift foxtrot")
def full_ledger_on_unseen_shift_foxtrot(workspace):
    return _holds(workspace, _check_full_ledger_on_unseen_shift_foxtrot)


@criterion(description="all four reports match the reference on unseen shift golf")
def full_ledger_on_unseen_shift_golf(workspace):
    return _holds(workspace, _check_full_ledger_on_unseen_shift_golf)


@criterion(description="all four reports match the reference on unseen shift hotel")
def full_ledger_on_unseen_shift_hotel(workspace):
    return _holds(workspace, _check_full_ledger_on_unseen_shift_hotel)


@criterion(description="the delivered program carries identifiers of the recorded shift as literal answers")
def negative_hardcoded_sample_answers(workspace):
    # Holds when the cheat is present; the negative weight does the punishing.
    return _holds(workspace, _check_negative_hardcoded_sample_answers)


@criterion(description="the delivered program imports a module outside the standard library")
def negative_third_party_dependency(workspace):
    # Holds when the cheat is present; the negative weight does the punishing.
    return _holds(workspace, _check_negative_third_party_dependency)


@criterion(description="the delivered program changes what it reports when the input directory is renamed")
def negative_filename_dependent_behaviour(workspace):
    # Holds when the cheat is present; the negative weight does the punishing.
    return _holds(workspace, _check_negative_filename_dependent_behaviour)


@criterion(description="five runs of the delivered program over one input directory disagree with each other")
def negative_nondeterministic_output(workspace):
    # Holds when the cheat is present; the negative weight does the punishing.
    return _holds(workspace, _check_negative_nondeterministic_output)


criteria.program_writes_the_four_reports_from_two_directory_arguments(weight=1)
criteria.report_serialization_carries_the_documented_byte_form(weight=1)
criteria.empty_shift_reports_are_written(weight=1)
criteria.throughput_normalisation_gain(weight=1)
criteria.precision_responses_match_the_reference(weight=1)
criteria.accelerator_responses_match_the_reference(weight=1)
criteria.phase_responses_match_the_reference(weight=1)
criteria.kernel_responses_match_the_reference(weight=1)
criteria.meter_accumulates_as_a_first_difference(weight=3)
criteria.meter_accumulates_per_phase(weight=3)
criteria.segment_boundary_resets_the_accumulator(weight=3)
criteria.reserved_meter_repeats_the_previous_probe(weight=3)
criteria.backlog_step_per_serve(weight=3)
criteria.backlog_doubles_on_the_marked_tier(weight=3)
criteria.back_to_back_serve_carries_its_extra(weight=3)
criteria.backlog_stops_at_its_ceiling(weight=3)
criteria.repeated_tag_takes_the_recorded_score(weight=3)
criteria.credit_applies_once(weight=3)
criteria.segment_budget_reads_the_whole_shift(weight=3)
criteria.verdict_ladder_takes_the_first_condition(weight=3)
criteria.plan_tolerances_separate_flagged_from_ok(weight=3)
criteria.endpoint_total_counts_the_reference_verdicts(weight=3)
criteria.endpoint_dispositions_follow_strikes_and_backlog(weight=3)
criteria.full_ledger_on_unseen_shift_alpha(weight=5)
criteria.full_ledger_on_unseen_shift_bravo(weight=5)
criteria.full_ledger_on_unseen_shift_charlie(weight=5)
criteria.full_ledger_on_unseen_shift_delta(weight=5)
criteria.full_ledger_on_unseen_shift_echo(weight=5)
criteria.full_ledger_on_unseen_shift_foxtrot(weight=5)
criteria.full_ledger_on_unseen_shift_golf(weight=5)
criteria.full_ledger_on_unseen_shift_hotel(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_third_party_dependency(weight=-3)
criteria.negative_filename_dependent_behaviour(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
