#!/usr/bin/env python3
"""Rebuilt inference gate.

Usage: gate.py <input-dir> <output-dir>
"""
import csv
import json
import os
import sys

# ---------------------------------------------------------------- constants
SPAN_FACTOR = 4
REPLAY_OFFSET = 2
GAIN = 1000

COARSE_ACCEL = None
COARSE_SCALE = 1

# each adjustment is affine: y -> y * num // den + off
IDENTITY = (1, 1, 0)
PREC_ADJ = {"fp32": (1, 1, 0), "fp16": (7, 8, -1), "bf16": (1, 1, 13),
            "int8": (3, 2, 0)}
ACCEL_ADJ = {"cuda": (6, 5, 0), "rocm": (1, 1, -7), "xla": (4, 5, 0),
             "npu": (1, 1, 19), "fpga": IDENTITY, "wasm": (1, 3, 8),
             "none": IDENTITY}
PHASE_ADJ = {"prefill": IDENTITY, "decode": (9, 10, 0), "batch": (1, 1, 17)}
KERNEL_ADJ = {"graph": (4, 5, 0), "eager": (4, 5, -15),
              "fused": IDENTITY, "traced": (4, 5, 0)}

SEGMENT_MODE = "reset"
RESERVED_METER = 0
CLEAR_MODE = "drain"
CREDIT_MODE = "refund"
CREDIT_DIV = 2
SETUP_MODES = ("reset", "refund")
VOID_MODE = "abort"

RECORD_LEN = 3
BACKLOG_DIV = 10
BACKLOG_TIER = 3
BACKLOG_STREAK = 5
BACKLOG_CAP = 500

PLAN_TOLERANCE = {"gold": 400, "silver": 300, "bronze": 200, "trial": 100}
BANDS = (("saturate", 300), ("high", 150), ("base", 100))
COUNTED_VERDICTS = ("ok", "flagged")
QUARANTINE_STRIKES = 3
THROTTLE_BACKLOG = 200
BUDGET_DIV = 10

BAND_NAMES = ("saturate", "high", "base", "idle")
VERDICT_NAMES = ("setup", "void", "rejected", "flagged", "ok")


def apply_adj(y, adj):
    num, den, off = adj
    y = y * num // den + off
    return 0 if y < 0 else y


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def load(indir):
    runtimes = {r["runtime"]: r for r in read_csv(os.path.join(indir, "runtimes.csv"))}
    variants = {r["variant"]: r for r in read_csv(os.path.join(indir, "variants.csv"))}
    callers = {r["caller"]: r for r in read_csv(os.path.join(indir, "callers.csv"))}
    endpoints = {r["endpoint"]: r for r in read_csv(os.path.join(indir, "endpoints.csv"))}
    probes = []
    ppath = os.path.join(indir, "probes.jsonl")
    if os.path.exists(ppath):
        with open(ppath, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    probes.append(json.loads(line))
    probes.sort(key=lambda p: p["seq"])
    return runtimes, variants, callers, endpoints, probes


def charged_precision(variants, vname):
    v = variants[vname]
    base = v.get("base") or ""
    if base:
        return variants[base]["precision"]
    return v["precision"]


def run(indir):
    runtimes, variants, callers, endpoints, probes = load(indir)

    state = {}
    for name, e in endpoints.items():
        rt = runtimes[e["runtime"]]
        state[name] = {
            "budget": int(rt["floor"]),
            "backlog": 0,
            "strikes": 0,
            "prev_serve": False,
            "credit": False,
            "record": [],
            "meters": {},
            "last_meter": {},
            "probes": 0,
            "counted": 0,
            "score_total": 0,
            "top_score": 0,
            "top_tag": None,
            "flagged": 0,
            "bands": {b: 0 for b in BAND_NAMES},
        }

    verdicts = []
    score_sum = 0
    score_count = 0

    for p in probes:
        name = p["endpoint"]
        st = state[name]
        e = endpoints[name]
        rt = runtimes[e["runtime"]]
        prec = charged_precision(variants, e["variant"])
        phase = p["phase"]
        mode = p["mode"]

        key = phase
        if mode == SEGMENT_MODE:
            st["meters"] = {}
            running = score_sum // score_count // BUDGET_DIV if score_count else int(rt["floor"])
            st["budget"] = running

        raw = p["meter"]
        if raw == RESERVED_METER:
            meter = st["last_meter"].get(key, 0)
        else:
            meter = st["meters"].get(key, 0) + raw
            st["meters"][key] = meter
        st["last_meter"][key] = meter

        m = meter
        if COARSE_ACCEL is not None and e["accel"] == COARSE_ACCEL:
            m = m * COARSE_SCALE

        # 1 batch width
        if p["spans"] == 0:
            width = p["rows"]
        else:
            width = p["spans"] * SPAN_FACTOR
        if width < 0:
            width = 0
        # 2 replay expansion
        width = width * (p["replays"] + REPLAY_OFFSET)
        if width < 0:
            width = 0
        # 3 warmup draw
        y = m - st["budget"]
        if y < 0:
            y = 0
        # 4 throughput normalisation
        y = y * GAIN // width if width > 0 else 0
        if y < 0:
            y = 0
        # 5-8 responses
        y = apply_adj(y, PREC_ADJ.get(prec, IDENTITY))
        y = apply_adj(y, ACCEL_ADJ.get(e["accel"], IDENTITY))
        y = apply_adj(y, PHASE_ADJ.get(phase, IDENTITY))
        y = apply_adj(y, KERNEL_ADJ.get(rt["kernel"], IDENTITY))
        # 9 backlog relief
        backlog_before = st["backlog"]
        y = y - backlog_before
        if y < 0:
            y = 0
        # 10 replay lookup
        for tag, sc in reversed(st["record"]):
            if tag == p["tag"]:
                y = sc
                break
        # 11 credit
        if st["credit"]:
            y = y // CREDIT_DIV
            st["credit"] = False
        if y < 0:
            y = 0
        score = y
        # 12 banding
        band = "idle"
        for bname, thresh in BANDS:
            if score >= thresh:
                band = bname
                break
        # 13 verdict
        if mode in SETUP_MODES:
            verdict = "setup"
        elif mode == VOID_MODE:
            verdict = "void"
        elif band == "idle":
            verdict = "rejected"
        elif backlog_before > PLAN_TOLERANCE[callers[p["caller"]]["plan"]]:
            verdict = "flagged"
        else:
            verdict = "ok"

        verdicts.append({
            "backlog_before": backlog_before,
            "band": band,
            "caller": p["caller"],
            "endpoint": name,
            "mode": mode,
            "phase": phase,
            "score": score,
            "seq": p["seq"],
            "tag": p["tag"],
            "verdict": verdict,
        })

        score_sum += score
        score_count += 1

        # 14 carry update
        if mode == CLEAR_MODE:
            st["backlog"] = 0
        if mode == CREDIT_MODE:
            st["credit"] = True
        if mode == "serve":
            add = width // BACKLOG_DIV
            if int(e["tier"]) == BACKLOG_TIER:
                add *= 2
            if st["prev_serve"]:
                add += BACKLOG_STREAK
            st["backlog"] += add
            if st["backlog"] > BACKLOG_CAP:
                st["backlog"] = BACKLOG_CAP
        st["prev_serve"] = (mode == "serve")
        if verdict == "rejected":
            st["strikes"] += 1
        st["record"].append((p["tag"], score))
        if len(st["record"]) > RECORD_LEN:
            st["record"].pop(0)

        st["probes"] += 1
        st["bands"][band] += 1
        if verdict == "flagged":
            st["flagged"] += 1
        if verdict in COUNTED_VERDICTS:
            st["counted"] += 1
            st["score_total"] += score
            if score > st["top_score"]:
                st["top_score"] = score
                st["top_tag"] = p["tag"]
            elif score == st["top_score"] and st["top_tag"] is not None:
                if p["tag"] < st["top_tag"]:
                    st["top_tag"] = p["tag"]

    ep_rows = []
    for name in sorted(endpoints):
        st = state[name]
        if st["strikes"] >= QUARANTINE_STRIKES:
            disp = "quarantine"
        elif st["backlog"] >= THROTTLE_BACKLOG:
            disp = "throttle"
        else:
            disp = "clear"
        ep_rows.append({
            "backlog_end": st["backlog"],
            "bands": {b: st["bands"][b] for b in BAND_NAMES},
            "budget_end": st["budget"],
            "counted": st["counted"],
            "disposition": disp,
            "endpoint": name,
            "flagged": st["flagged"],
            "probes": st["probes"],
            "score_total": st["score_total"],
            "strikes": st["strikes"],
            "top_score": st["top_score"],
            "top_tag": st["top_tag"],
        })

    prec_rows = {}
    for name in sorted(endpoints):
        prec = charged_precision(variants, endpoints[name]["variant"])
        row = prec_rows.setdefault(prec, [0, 0, 0, 0])
        st = state[name]
        row[0] += 1
        row[1] += st["probes"]
        row[2] += st["score_total"]
        row[3] += st["flagged"]

    by_band = {b: 0 for b in BAND_NAMES}
    by_verdict = {v: 0 for v in VERDICT_NAMES}
    for v in verdicts:
        by_band[v["band"]] += 1
        by_verdict[v["verdict"]] += 1
    quarantined = sorted(r["endpoint"] for r in ep_rows if r["disposition"] == "quarantine")
    top_endpoint = None
    best = None
    for r in ep_rows:
        if best is None or r["score_total"] > best:
            best = r["score_total"]
            top_endpoint = r["endpoint"]
    if not ep_rows:
        top_endpoint = None
    shift = {
        "by_band": by_band,
        "by_verdict": by_verdict,
        "endpoints": len(ep_rows),
        "probes": len(verdicts),
        "quarantined": quarantined,
        "score_total": sum(r["score_total"] for r in ep_rows),
        "top_endpoint": top_endpoint,
    }
    return verdicts, ep_rows, prec_rows, shift


def write_reports(outdir, verdicts, ep_rows, prec_rows, shift):
    os.makedirs(outdir, exist_ok=True)
    vtxt = "".join(json.dumps(v, sort_keys=True, separators=(",", ":")) + "\n"
                   for v in verdicts)
    etxt = json.dumps({"endpoints": ep_rows}, sort_keys=True, indent=2) + "\n"
    lines = ["precision,endpoints,probes,score_total,flagged"]
    for prec in sorted(prec_rows):
        a, b, c, d = prec_rows[prec]
        lines.append("%s,%d,%d,%d,%d" % (prec, a, b, c, d))
    ptxt = "\n".join(lines) + "\n"
    stxt = json.dumps(shift, sort_keys=True, indent=2) + "\n"
    for fname, text in (("verdicts.jsonl", vtxt), ("endpoints.json", etxt),
                        ("precision.csv", ptxt), ("shift.json", stxt)):
        with open(os.path.join(outdir, fname), "w", encoding="utf-8", newline="") as fh:
            fh.write(text)


def main(argv):
    indir, outdir = argv[1], argv[2]
    verdicts, ep_rows, prec_rows, shift = run(indir)
    write_reports(outdir, verdicts, ep_rows, prec_rows, shift)


if __name__ == "__main__":
    main(sys.argv)
