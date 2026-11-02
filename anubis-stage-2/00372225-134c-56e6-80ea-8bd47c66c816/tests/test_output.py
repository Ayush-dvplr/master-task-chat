"""Deterministic rewardkit channel for 00372225-134c-56e6-80ea-8bd47c66c816.

This module is an INDEPENDENT re-derivation of the clinical-assay QC
recalibration pipeline. It does not import solution/solve.py. It regenerates its
own sample, challenge and eval corpora from three seeds, derives the expected
artifacts itself with a separate code path, runs the agent's delivered
derive_report.py against fresh corpora, and compares byte-exact.

rewardkit calls each check with the workspace root, which the harness sets to
/app, so the agent's declared artifacts are read under `workspace / "out"`.
Every check returns a bool and never raises: an exception inside a check aborts
the whole run and no reward is written, so each body is wrapped by _guard().

Polarity for the negative checks: the check returns True when the cheat is
present and its negative weight is subtracted. An honest agent leaves every
negative check returning False, so nop scores exactly 0.000.

Every figure graded on the shipped run is read from the agent's declared
artifact AND must be reproduced byte for byte by running the delivered program
on a freshly regenerated copy of that run, so a hand-written artifact set with no
working program earns nothing beyond the shape checks. Each of those checks also
grades the same figure on an unseen run in the same layout, so a program that
replays the shipped outputs without computing them earns nothing more. The checks that compare
every artifact of a whole run (the held-out corpora and the carry, round-control
and sparse probes) call _full_core_matches() first; every other probe check
grades its own probe output on its own, so one wrong stage costs the checks that
exercise it rather than the whole positive suite.
"""
# pyright: reportUndefinedVariable=false, reportUnhashable=false, reportArgumentType=false
from __future__ import annotations

import ast
import csv
import hashlib
import json
import os
import re
import shutil
import signal
import sqlite3
import subprocess
import sys
import tempfile
import threading
import zipfile
import zlib
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

SAMPLE_SEED = 5731904428170553611
CHALLENGE_SEED = 8419273650118824407
EVAL_SEED = 3082756194023881190

SCRIPT_NAME = "derive_report.py"
CORE_NAMES = ["summary.json", "policy_audit.json", "panel_analyte_glucose.json"]
ARTIFACT_NAMES = [
    "summary.json", "policy_audit.json", "data_quality.json",
    "panel_analyte_glucose.json", "panel_analyte_calcium.json",
    "panel_analyte_lactate.json", "panel_analyte_creatinine.json",
    "matrix_rollup.json", "tier_rollup.json",
    "analyte_totals.json", "tier_analyte_membership.json",
    "ordered_reading_index.json", "excluded_readings.json",
    "analyte_committed.csv", "batch_committed.tsv",
    "matrix_weighted.psv", "carryover_ledger.xml", "objective_summary.yaml",
    "reconciliation_report.md", "run_status.txt", "provenance_manifest.json",
]

_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]

Q = 16
ONE = 1 << Q

# Structural vocabulary (independent copy of the documented spec).
ANALYTES = ["glucose", "calcium", "lactate", "creatinine"]
# Each panel analyte belongs to a matrix (serum/whole_blood) and a decision
# tier (routine/stat), and carries an after-clamp matrix shift in whole units.
ANALYTE_DEF = {
    "glucose": ("serum", "routine", 30),
    "calcium": ("serum", "stat", -20),
    "lactate": ("whole_blood", "stat", 15),
    "creatinine": ("whole_blood", "routine", 0),
}
# Instrument channels are the carry lanes; batches are the accumulation windows.
CHANNELS = ["ch0", "ch1", "ch2", "ch3"]
# The assay method selects the non-linearity regime applied to the basis signal.
METHODS = ["photometric", "enzymatic", "potentiometric"]
# The specimen unit selects the fixed-point scale (basis points) of the signal.
SPEC_UNITS = ["mg_dl", "mmol_l", "mabs"]
UNIT_SCALE_BP = {"mg_dl": 10000, "mmol_l": 10850, "mabs": 12600}
# The LIVE method coefficients: exponent regime (milli) and gain (basis points).
METHOD_COEFFS_LIVE = {
    "photometric": {"exponent_milli": 1000, "gain_bp": 10000},
    "enzymatic": {"exponent_milli": 1500, "gain_bp": 9200},
    "potentiometric": {"exponent_milli": 2000, "gain_bp": 300},
}
METHOD_COEFFS_DRAFT = {
    "photometric": {"exponent_milli": 1000, "gain_bp": 10000},
    "enzymatic": {"exponent_milli": 1000, "gain_bp": 9200},
    "potentiometric": {"exponent_milli": 1000, "gain_bp": 300},
}
# Per-analyte linear recalibration (slope a_milli over 1000, intercept b_milli).
RECAL_LIVE = {
    "glucose": {"a_milli": 1200, "b_milli": -300},
    "calcium": {"a_milli": 900, "b_milli": 150},
    "lactate": {"a_milli": 1100, "b_milli": -80},
    "creatinine": {"a_milli": 1000, "b_milli": 0},
}
RECAL_DRAFT = {
    "glucose": {"a_milli": 1000, "b_milli": 0},
    "calcium": {"a_milli": 1000, "b_milli": 0},
    "lactate": {"a_milli": 1000, "b_milli": 0},
    "creatinine": {"a_milli": 1000, "b_milli": 0},
}
# Governance constants that live ONLY in the pdf content stream.
PDF_CONSTS = {
    "RECOVERY_FLOOR_BP": 350, "FLOOR_RESULT": 5, "DAMPING_SEED": 14000,
    "BATCH_CAP": 900, "CARRYOVER_CEILING": 1200,
}
CALIBRATION_TAG = "ASSAYCAL-L7"
# Decision-tier objective weights (stat weighted higher than routine).
TIER_WEIGHT = {"stat": 5, "routine": 2}
BATCHES = [
    {"batch": "b_open", "from_slot": 0, "to_slot": 15, "min_lot": 0},
    {"batch": "b_ramp", "from_slot": 15, "to_slot": 30, "min_lot": 0},
    {"batch": "b_plateau", "from_slot": 30, "to_slot": 60, "min_lot": 0},
    {"batch": "b_recheck", "from_slot": 29, "to_slot": 31, "min_lot": 5},
]
# Each panel analyte maps to a matrix class and a decision tier for rollups.
ANALYTE_MATRIX = {a: ANALYTE_DEF[a][0] for a in ANALYTES}
ANALYTE_TIER = {a: ANALYTE_DEF[a][1] for a in ANALYTES}


# ---------------------------------------------------------------------------
# Deterministic RNG (xorshift64*) - contractually stable across CPython.
# ---------------------------------------------------------------------------
class Rng:
    __slots__ = ("state",)

    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFFFFFFFFFF or 0xA0761D6478BD642F

    def _next(self) -> int:
        x = self.state
        x ^= (x >> 12) & 0xFFFFFFFFFFFFFFFF
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27) & 0xFFFFFFFFFFFFFFFF
        self.state = x
        return (x * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def rand_int(self, lo: int, hi: int) -> int:
        return lo + self._next() % (hi - lo + 1)

    def choice(self, seq):
        return seq[self._next() % len(seq)]


# ---------------------------------------------------------------------------
# Fixed-point + reference math (independent of solve.py).
# ---------------------------------------------------------------------------
def _half_up_div(num: int, den: int) -> int:
    if den < 0:
        num, den = -num, -den
    if num >= 0:
        return (num * 2 + den) // (2 * den)
    return -(((-num) * 2 + den) // (2 * den))


def q_mul(a: int, b: int) -> int:
    p = a * b
    return -((-p) >> Q) if p < 0 else p >> Q


def q_from_bp(bp: int) -> int:
    return _half_up_div(bp * ONE, 10000)


def q_from_milli(m: int) -> int:
    return _half_up_div(m * ONE, 1000)


def q_round_half_up(v: int) -> int:
    return _half_up_div(v, ONE) << Q


def q_to_whole(v: int) -> int:
    return v >> Q if v >= 0 else -((-v) >> Q)


def q_from_int(n: int) -> int:
    return n << Q


def q_sqrt(x: int) -> int:
    if x <= 0:
        return 0
    n = x * ONE
    r = 0
    bit = 1 << ((n.bit_length() + 1) // 2 * 2)
    while bit > n:
        bit >>= 2
    while bit:
        if n >= r + bit:
            n -= r + bit
            r = (r >> 1) + bit
        else:
            r >>= 1
        bit >>= 2
    return r


def _neg_str(s: str) -> tuple:
    return tuple(-ord(ch) for ch in s) + (1,)


def _method_transform(basis_q: int, method: dict[str, int]) -> int:
    em = method["exponent_milli"]
    if em == 1000:
        powered = basis_q
    elif em == 2000:
        powered = q_mul(basis_q, basis_q)
    elif em == 1500:
        powered = q_mul(basis_q, q_sqrt(basis_q))
    else:
        raise AssertionError(f"unsupported exponent_milli {em}")
    return q_round_half_up(q_mul(powered, q_from_bp(method["gain_bp"])))


def _recal(transformed_q: int, recal: dict[str, int]) -> int:
    a_q = q_from_milli(recal["a_milli"])
    b_q = q_from_milli(recal["b_milli"])
    return q_round_half_up(q_mul(transformed_q, a_q) + b_q)


def _effective_lot(profile: dict[str, Any]) -> int:
    return min(int(profile["lot_a"]), int(profile["lot_b"]))


def _batch_of(slot: int, batches: list[dict[str, str]], eff_lot: int) -> str | None:
    chosen = None
    for b in batches:
        if int(b["min_lot"]) > eff_lot:
            continue
        if int(b["from_slot"]) <= slot < int(b["to_slot"]):
            chosen = b["batch"]
    return chosen


def _converge_batch(state: dict[str, int], damping_seed: int, batch_cap: int):
    keys = sorted(state.keys())
    n = len(keys)
    mass = sum(state.values())
    target_mass = min(mass, batch_cap)
    if mass > 0:
        raw = [state[k] * target_mass for k in keys]
        fairl = [r // mass for r in raw]
        rem = target_mass - sum(fairl)
        order = sorted(range(n), key=lambda i: (-(raw[i] - fairl[i] * mass), keys[i]))
        for i in range(rem):
            fairl[order[i]] += 1
        fair = {k: fairl[i] for i, k in enumerate(keys)}
    else:
        fair = {k: 0 for k in keys}
    damping = damping_seed
    prev_resid = None
    non_improving = 0
    seen: dict[tuple, int] = {}
    history: list[dict[str, int]] = []
    r = 0
    budget = 64
    while r < budget:
        sig = tuple(state[k] for k in keys)
        if sig in seen:
            start = seen[sig]
            cyc = history[start:] + [dict(state)]
            smallest = min(cyc, key=lambda s: tuple(s[k] for k in keys))
            return smallest, -1
        seen[sig] = r
        history.append(dict(state))
        resid = sum(abs(state[k] - fair[k]) for k in keys)
        if resid == 0:
            return dict(state), r
        if prev_resid is not None and resid >= prev_resid:
            non_improving += 1
            if non_improving >= 2:
                damping = damping // 2
                non_improving = 0
        prev_resid = resid
        flow = {k: _half_up_div((fair[k] - state[k]) * damping, 10000) for k in keys}
        imbalance = sum(flow.values())
        if imbalance != 0:
            tk = min(keys, key=lambda k: (-abs(fair[k] - state[k]), k))
            flow[tk] -= imbalance
        moved = any(flow[k] != 0 for k in keys)
        for k in keys:
            state[k] += flow[k]
        if not moved:
            return dict(state), r
        r += 1
    return dict(state), budget


def _carryover(settled: dict[str, dict[str, int]], ceiling: int):
    final = {b: dict(analytes) for b, analytes in settled.items()}
    ledger: list[dict[str, Any]] = []
    for batch in sorted(final):
        analytes = final[batch]
        excess = sum(analytes.values()) - ceiling
        if excess <= 0:
            continue
        remaining = excess
        for a in sorted(analytes.keys(), key=lambda a: (-analytes[a], a)):
            if remaining <= 0:
                break
            take = min(analytes[a], remaining)
            analytes[a] -= take
            remaining -= take
            ledger.append({"analyte": a, "clawed_units": take, "batch": batch})
    ledger.sort(key=lambda d: (d["batch"], d["analyte"]))
    return final, ledger


# ---------------------------------------------------------------------------
# Independent xlsx / pdf readers (different code path than solve.py).
# ---------------------------------------------------------------------------
def _read_csv(path: Path, delim: str = ",") -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=delim))


def _grid(xml: str, shared: list[str]) -> list[list[str]]:
    cells: dict[int, dict[int, str]] = {}
    for cm in re.finditer(r'<c r="([A-Z]+)(\d+)"([^>]*)>(.*?)</c>', xml, re.S):
        col = 0
        for ch in cm.group(1):
            col = col * 26 + (ord(ch) - 64)
        col -= 1
        row = int(cm.group(2))
        vm = re.search(r"<v>(.*?)</v>", cm.group(4), re.S)
        val = vm.group(1) if vm else ""
        if 't="s"' in cm.group(3) and val != "":
            val = shared[int(val)]
        cells.setdefault(row, {})[col] = val
    if not cells:
        return []
    mr = max(cells)
    mc = max(max(c) for c in cells.values())
    return [[cells.get(r, {}).get(c, "") for c in range(mc + 1)] for r in range(1, mr + 1)]


def _read_calibration_xlsx(path: Path, tag: str):
    with zipfile.ZipFile(path) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sx = zf.read("xl/sharedStrings.xml").decode("utf-8")
            for m in re.finditer(r"<si>(.*?)</si>", sx, re.S):
                shared.append("".join(re.findall(r"<t[^>]*>(.*?)</t>", m.group(1), re.S)))
        wb = zf.read("xl/workbook.xml").decode("utf-8")
        rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        rid = {m.group(1): m.group(2) for m in re.finditer(
            r'<Relationship[^>]*Id="([^"]+)"[^>]*Target="([^"]+)"', rels)}
        grids: dict[str, list[list[str]]] = {}
        for m in re.finditer(r'<sheet[^>]*name="([^"]+)"[^>]*r:id="([^"]+)"', wb):
            tgt = rid[m.group(2)]
            if not tgt.startswith("xl/"):
                tgt = "xl/" + tgt.lstrip("/")
            grids[m.group(1)] = _grid(zf.read(tgt).decode("utf-8"), shared)
    for grid in grids.values():
        if len(grid) >= 1 and len(grid[0]) >= 2 and grid[0][1] == tag:
            header = grid[1]
            ci = {header[i]: i for i in range(len(header))}
            methods: dict[str, dict[str, int]] = {}
            recal: dict[str, dict[str, int]] = {}
            for row in grid[2:]:
                if not row or row[ci["row_kind"]] == "":
                    continue
                kind = row[ci["row_kind"]]
                key = row[ci["key"]]
                if kind == "method":
                    methods[key] = {"exponent_milli": int(row[ci["exponent_milli"]]),
                                    "gain_bp": int(row[ci["gain_bp"]])}
                elif kind == "recal":
                    recal[key] = {"a_milli": int(row[ci["a_milli"]]),
                                  "b_milli": int(row[ci["b_milli"]])}
            return methods, recal
    raise AssertionError("no LIVE calibration sheet matches calibration_tag")


def _read_governance_pdf(path: Path) -> dict[str, int]:
    raw = path.read_bytes().decode("latin-1")
    text = []
    for m in re.finditer(r"stream\r?\n(.*?)\r?\nendstream", raw, re.S):
        blob = m.group(1).encode("latin-1")
        try:
            blob = zlib.decompress(blob).decode("latin-1", errors="replace")
        except zlib.error:
            blob = m.group(1)
        text.append(blob)
    joined = "\n".join(text)
    found: dict[str, int] = {}
    for m in re.finditer(r"\(([A-Z_]+)\s+(-?\d+)\)\s*Tj", joined):
        found[m.group(1)] = int(m.group(2))
    return found


# ---------------------------------------------------------------------------
# The reference re-derivation (independent second code path).
# ---------------------------------------------------------------------------
def reference(data_dir: Path) -> dict[str, str]:
    profile = json.loads((data_dir / "run_profile.json").read_text(encoding="utf-8"))
    methods, recal = _read_calibration_xlsx(data_dir / "recalibration_grid.xlsx", profile["calibration_tag"])
    consts = _read_governance_pdf(data_dir / "governance_envelope.pdf")
    readings = _read_csv(data_dir / "assay_capture_run.csv")
    analytes = {r["analyte"]: r for r in _read_csv(data_dir / "analyte_crosswalk.csv")}
    topology = {r["analyte"]: r for r in _read_csv(data_dir / "panel_topology.csv")}
    units = {r["spec_unit"]: int(r["scale_bp"]) for r in _read_csv(data_dir / "unit_scale_book.csv")}
    batches = _read_csv(data_dir / "batch_calendar.csv")
    tier_weight = {k: int(v) for k, v in json.loads(
        (data_dir / "tier_weight_book.json").read_text(encoding="utf-8")).items()}

    eff_lot = _effective_lot(profile)
    rec_floor = consts["RECOVERY_FLOOR_BP"]
    floor_result = consts["FLOOR_RESULT"]
    batch_cap = consts["BATCH_CAP"]
    ceiling = consts["CARRYOVER_CEILING"]
    damping_seed = consts["DAMPING_SEED"]

    live_readings = [o for o in readings if o.get("is_qc_fail", "0") not in ("1", "true", "True")]
    ordered = sorted(live_readings, key=lambda o: (int(o["settle_slot"]), int(o["draw_slot"]), _neg_str(o["reading_id"])))

    committed: dict[tuple[str, str], int] = {}
    per_reading: list[dict[str, Any]] = []
    channel_carry: dict[str, int] = {}
    batch_running: dict[str, int] = {}

    for o in ordered:
        analyte = o["analyte"]
        mat = topology[analyte]
        method = methods[o["method"]]
        batch = _batch_of(int(o["settle_slot"]), batches, eff_lot)
        if batch is None:
            per_reading.append({"reading_id": o["reading_id"], "dropped": True, "analyte": analyte})
            continue
        scale = units[o["spec_unit"]]
        raw_q = q_mul(q_from_int(int(o["raw_signal"])), q_from_bp(scale))
        basis_q = q_mul(q_from_int(int(o["basis_signal"])), q_from_bp(scale))
        transformed = _method_transform(basis_q, method)
        calibrated = _recal(raw_q + transformed, recal[analyte])
        rec_bp = max(rec_floor, int(o["recovery_bp"]))
        reweighted = q_round_half_up(q_mul(calibrated, q_from_bp(rec_bp)))
        want_whole = q_to_whole(reweighted) + channel_carry.get(o["channel"], 0)
        channel_carry[o["channel"]] = 0
        running = batch_running.get(batch, 0)
        headroom = max(0, batch_cap - running)
        admit = want_whole if want_whole <= headroom else headroom
        spill = want_whole - admit
        if spill > 0:
            channel_carry[o["channel"]] = channel_carry.get(o["channel"], 0) + spill
        batch_running[batch] = running + admit
        clamped = admit if admit >= floor_result else floor_result
        placed = max(0, clamped + int(mat["matrix_shift_units"]))
        committed[(analyte, batch)] = committed.get((analyte, batch), 0) + placed
        per_reading.append({"reading_id": o["reading_id"], "dropped": False, "analyte": analyte,
                            "batch": batch, "channel": o["channel"]})

    channel_home: dict[str, tuple[str, str]] = {}
    for rec in per_reading:
        if not rec.get("dropped"):
            channel_home.setdefault(rec["channel"], (rec["analyte"], rec["batch"]))
    for channel, carry in sorted(channel_carry.items()):
        if carry > 0 and channel in channel_home:
            key = channel_home[channel]
            committed[key] = committed.get(key, 0) + carry

    by_batch: dict[str, dict[str, int]] = {}
    for (analyte, batch), u in committed.items():
        by_batch.setdefault(batch, {})[analyte] = u
    settled: dict[str, dict[str, int]] = {}
    rounds: dict[str, int] = {}
    for batch in sorted(by_batch):
        st, rd = _converge_batch(dict(by_batch[batch]), damping_seed, batch_cap)
        settled[batch] = st
        rounds[batch] = rd
    final, ledger = _carryover(settled, ceiling)

    batches_sorted = sorted(final)
    analyte_totals: dict[str, int] = {}
    for b in final:
        for a, u in final[b].items():
            analyte_totals[a] = analyte_totals.get(a, 0) + u
    matrix_totals: dict[str, int] = {}
    tier_totals: dict[str, int] = {}
    for a, total in analyte_totals.items():
        mat = topology[a]
        matrix_totals[mat["matrix_class"]] = matrix_totals.get(mat["matrix_class"], 0) + total
        tier_totals[mat["tier"]] = tier_totals.get(mat["tier"], 0) + total
    objective_val = sum(tier_totals.get(t, 0) * tier_weight[t] for t in sorted(tier_weight))
    excluded_ids = sorted(o["reading_id"] for o in readings
                          if o.get("is_qc_fail", "0") in ("1", "true", "True"))

    summary = {
        "batch_totals": {b: sum(final[b].values()) for b in batches_sorted},
        "analyte_allocations": {b: dict(sorted(final[b].items())) for b in batches_sorted},
        "convergence_rounds": {b: rounds[b] for b in batches_sorted},
        "unsettled_batches": sorted([b for b in batches_sorted if rounds[b] == -1]),
    }
    policy_audit = {
        "tier_totals": dict(sorted(tier_totals.items())),
        "carryover_ledger": ledger,
        "excluded_reading_ids": excluded_ids,
        "excluded_count": len(excluded_ids),
        "effective_lot": eff_lot,
        "ordered_reading_ids": [o["reading_id"] for o in ordered],
    }

    def _mat_of(a_name: str) -> dict[str, str]:
        return topology.get(a_name, {})

    def analyte_doc(a_name: str) -> dict[str, Any]:
        return {"analyte": a_name, "matrix": _mat_of(a_name).get("matrix_class", ""),
                "tier": _mat_of(a_name).get("tier", ""),
                "committed_total": analyte_totals.get(a_name, 0),
                "per_batch": {b: final[b].get(a_name, 0) for b in batches_sorted if a_name in final[b]}}

    matrix_doc = {
        "axis": "matrix",
        "class_totals": dict(sorted(matrix_totals.items())),
        "analyte_membership": {a: _mat_of(a).get("matrix_class", "") for a in sorted(analyte_totals) if a in analytes},
    }
    tier_doc = {
        "axis": "tier",
        "class_totals": dict(sorted(tier_totals.items())),
        "weighted_objective": objective_val,
        "analyte_membership": {a: _mat_of(a).get("tier", "") for a in sorted(analyte_totals) if a in analytes},
    }

    def dumps(obj: Any) -> str:
        return json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"

    def xesc(s: str) -> str:
        return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))

    core = {"summary.json": summary, "policy_audit.json": policy_audit,
            "panel_analyte_glucose.json": analyte_doc("glucose")}
    core_text = "".join(dumps(core[n]) for n in CORE_NAMES)
    digest = hashlib.sha256(core_text.encode("utf-8")).hexdigest()

    out: dict[str, str] = {}
    out["summary.json"] = dumps(summary)
    out["policy_audit.json"] = dumps(policy_audit)
    dq = {"objective_value": objective_val, "tier_totals": dict(sorted(tier_totals.items())),
          "committed_grand_total": sum(analyte_totals.values()),
          "carryover_total_units": sum(d["clawed_units"] for d in ledger),
          "core_files": list(CORE_NAMES), "core_sha256": digest}
    out["data_quality.json"] = dumps(dq)
    out["panel_analyte_glucose.json"] = dumps(analyte_doc("glucose"))
    out["panel_analyte_calcium.json"] = dumps(analyte_doc("calcium"))
    out["panel_analyte_lactate.json"] = dumps(analyte_doc("lactate"))
    out["panel_analyte_creatinine.json"] = dumps(analyte_doc("creatinine"))
    out["matrix_rollup.json"] = dumps(matrix_doc)
    out["tier_rollup.json"] = dumps(tier_doc)
    out["analyte_totals.json"] = dumps(dict(sorted(analyte_totals.items())))
    out["tier_analyte_membership.json"] = dumps({a: _mat_of(a).get("tier", "") for a in sorted(analyte_totals) if a in analytes})
    out["ordered_reading_index.json"] = dumps([o["reading_id"] for o in ordered])
    out["excluded_readings.json"] = dumps(excluded_ids)

    csv_lines = ["analyte,matrix,tier,committed_total"]
    for a in sorted(analytes):
        mat = _mat_of(a)
        csv_lines.append(f"{a},{mat.get('matrix_class','')},{mat.get('tier','')},{analyte_totals.get(a,0)}")
    out["analyte_committed.csv"] = "\n".join(csv_lines) + "\n"
    tsv_lines = ["batch\tcommitted_total\tconvergence_rounds"]
    for b in batches_sorted:
        tsv_lines.append(f"{b}\t{sum(final[b].values())}\t{rounds[b]}")
    out["batch_committed.tsv"] = "\n".join(tsv_lines) + "\n"
    psv_lines = ["tier|committed_total|tier_weight|weighted_contribution"]
    for t in sorted(tier_weight):
        tt = tier_totals.get(t, 0)
        psv_lines.append(f"{t}|{tt}|{tier_weight[t]}|{tt*tier_weight[t]}")
    out["matrix_weighted.psv"] = "\n".join(psv_lines) + "\n"
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', "<carryover_ledger>"]
    for d in ledger:
        xml.append(f'  <entry batch="{xesc(d["batch"])}" analyte="{xesc(d["analyte"])}" clawed_units="{d["clawed_units"]}"/>')
    xml.append(f'  <total clawed_units="{sum(d["clawed_units"] for d in ledger)}"/>')
    xml.append("</carryover_ledger>")
    out["carryover_ledger.xml"] = "\n".join(xml) + "\n"
    yaml_lines = [f"objective_value: {objective_val}",
                  f"committed_grand_total: {sum(analyte_totals.values())}",
                  f"excluded_count: {len(excluded_ids)}",
                  f"carryover_total_units: {sum(d['clawed_units'] for d in ledger)}",
                  f"effective_lot: {eff_lot}", f"core_sha256: {digest}", "tier_totals:"]
    for t in sorted(tier_totals):
        yaml_lines.append(f"  {t}: {tier_totals[t]}")
    out["objective_summary.yaml"] = "\n".join(yaml_lines) + "\n"
    md_lines = ["# Assay QC Reconciliation Report", "",
                f"objective_value {objective_val}",
                f"committed_grand_total {sum(analyte_totals.values())}",
                f"effective_lot {eff_lot}", f"excluded_count {len(excluded_ids)}",
                "", "## Batch totals", ""]
    for b in batches_sorted:
        md_lines.append(f"- {b} {sum(final[b].values())}")
    out["reconciliation_report.md"] = "\n".join(md_lines) + "\n"
    status = "SETTLED" if not summary["unsettled_batches"] else "UNSETTLED"
    out["run_status.txt"] = "\n".join([
        f"status {status}", f"objective_value {objective_val}", f"core_sha256 {digest}",
        f"unsettled_batches {','.join(summary['unsettled_batches']) or 'none'}"]) + "\n"
    art_names = sorted(out.keys()) + ["provenance_manifest.json"]
    out["provenance_manifest.json"] = dumps({
        "artifact_names": sorted(art_names), "core_files": list(CORE_NAMES),
        "core_sha256": digest, "reusable_program": "/app/out/derive_report.py"})
    return out


# ---------------------------------------------------------------------------
# Corpus writers (independent). Sample tier ships; challenge/eval regenerate.
# ---------------------------------------------------------------------------
def _idx_to_col(idx: int) -> str:
    idx += 1
    s = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        s = chr(65 + rem) + s
    return s


def _make_calibration_xlsx(path: Path) -> None:
    shared: list[str] = []
    sidx: dict[str, int] = {}

    def si(s: str) -> int:
        if s not in sidx:
            sidx[s] = len(shared)
            shared.append(s)
        return sidx[s]

    def sheet(rows):
        out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
               '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
        for ri, row in enumerate(rows, 1):
            out.append(f'<row r="{ri}">')
            for ci, (val, is_str) in enumerate(row):
                if val == "" or val is None:
                    continue
                ref = f"{_idx_to_col(ci)}{ri}"
                if is_str:
                    out.append(f'<c r="{ref}" t="s"><v>{si(str(val))}</v></c>')
                else:
                    out.append(f'<c r="{ref}"><v>{val}</v></c>')
            out.append("</row>")
        out.append("</sheetData></worksheet>")
        return "".join(out)

    def rows_for(tag, methods, recal):
        rows = [[("calibration_tag", True), (tag, True)],
                [("row_kind", True), ("key", True), ("exponent_milli", True),
                 ("gain_bp", True), ("a_milli", True), ("b_milli", True)]]
        for m in METHODS:
            rows.append([("method", True), (m, True), (methods[m]["exponent_milli"], False),
                         (methods[m]["gain_bp"], False), ("", True), ("", True)])
        for a in ANALYTES:
            rows.append([("recal", True), (a, True), ("", True), ("", True),
                         (recal[a]["a_milli"], False), (recal[a]["b_milli"], False)])
        for i in range(24):
            rows.append([("note", True), (f"ctrl_lot_{i:03d}", True),
                         ((i * 7) % 900, False), (10000, False),
                         (1000, False), (0, False)])
        return rows

    live = sheet(rows_for(CALIBRATION_TAG, METHOD_COEFFS_LIVE, RECAL_LIVE))
    draft = sheet(rows_for("ASSAYCAL-DRAFT", METHOD_COEFFS_DRAFT, RECAL_DRAFT))
    sst = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" count="{len(shared)}" uniqueCount="{len(shared)}">']
    sst += [f"<si><t>{s}</t></si>" for s in shared]
    sst.append("</sst>")
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
          '<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
          '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>')
    rr = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
          '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    wbxml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
             'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
             '<sheet name="LIVE_L7" sheetId="1" r:id="rId1"/><sheet name="DRAFT_v2" sheetId="2" r:id="rId2"/></sheets></workbook>')
    wbrels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
              '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
              '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>'
              '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", ct)
        zf.writestr("_rels/.rels", rr)
        zf.writestr("xl/workbook.xml", wbxml)
        zf.writestr("xl/_rels/workbook.xml.rels", wbrels)
        zf.writestr("xl/sharedStrings.xml", "".join(sst))
        zf.writestr("xl/worksheets/sheet1.xml", live)
        zf.writestr("xl/worksheets/sheet2.xml", draft)


def _make_governance_pdf(path: Path, consts: dict[str, int]) -> None:
    lines = [f"{k} {v}" for k, v in consts.items()]
    filler = []
    for i in range(12):
        filler.append(f"AUDIT_NOTE_{i:03d} superseded control limit {1200 + i} retired")
    ops = ["BT", "/F1 12 Tf", "72 720 Td"]
    for ln in lines:
        ops.append(f"({ln}) Tj")
        ops.append("0 -14 Td")
    for ln in filler:
        ops.append(f"({ln}) Tj")
        ops.append("0 -12 Td")
    ops.append("ET")
    comp = zlib.compress("\n".join(ops).encode("latin-1"))
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
            b"<< /Length " + str(len(comp)).encode() + b" /Filter /FlateDecode >>\nstream\n" + comp + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out = bytearray(b"%PDF-1.4\n")
    offs = [0]
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs)+1}\n".encode() + b"0000000000 65535 f \n"
    for off in offs[1:]:
        out += f"{off:010d} 00000 n \n".encode()
    out += b"trailer\n" + f"<< /Size {len(objs)+1} /Root 1 0 R >>\n".encode()
    out += b"startxref\n" + f"{xref}\n".encode() + b"%%EOF\n"
    path.write_bytes(bytes(out))


def _make_docx(path: Path) -> None:
    paras = [
        "Assay governance appendix (informational restatement).",
        "The authoritative recovery floor lives in the governance envelope document.",
        "The authoritative floor result lives in the governance envelope document.",
        "The authoritative damping seed lives in the governance envelope document.",
        "The authoritative batch cap lives in the governance envelope document.",
        "The authoritative carryover ceiling lives in the governance envelope document.",
        "SUPERSEDED legacy note: an older brief listed the batch cap as 1200; that value is retired.",
        "SUPERSEDED legacy note: an older brief listed the carryover ceiling as 1500; that value is retired.",
        "The calibration LIVE sheet is selected by the run profile calibration tag.",
        "The recalibration slope a_milli and intercept b_milli live only in the calibration matrix LIVE sheet.",
    ]
    body = "".join(f'<w:p><w:r><w:t xml:space="preserve">{p}</w:t></w:r></w:p>' for p in paras)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f'<w:body>{body}</w:body></w:document>')
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", ct)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", doc)


def _sqlite_dims(path: Path, tables: list[str]) -> None:
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    cur = con.cursor()
    if "analyte" in tables:
        cur.execute("CREATE TABLE analyte_dim (analyte TEXT PRIMARY KEY, matrix TEXT)")
        cur.executemany("INSERT INTO analyte_dim VALUES (?,?)", [(a, ANALYTE_MATRIX[a]) for a in ANALYTES])
    if "panel" in tables:
        cur.execute("CREATE TABLE panel_dim (analyte TEXT PRIMARY KEY, matrix_class TEXT, tier TEXT, matrix_shift_units INTEGER)")
        cur.executemany("INSERT INTO panel_dim VALUES (?,?,?,?)",
                        [(a, ANALYTE_DEF[a][0], ANALYTE_DEF[a][1], ANALYTE_DEF[a][2]) for a in ANALYTES])
    if "unit" in tables:
        cur.execute("CREATE TABLE unit_dim (spec_unit TEXT PRIMARY KEY, scale_bp INTEGER)")
        cur.executemany("INSERT INTO unit_dim VALUES (?,?)", [(u, UNIT_SCALE_BP[u]) for u in SPEC_UNITS])
    con.commit()
    con.close()


def _readings_csv(rng: Rng, n: int) -> str:
    header = ("reading_id,analyte,channel,method,spec_unit,raw_signal,basis_signal,recovery_bp,"
              "is_qc_fail,draw_slot,settle_slot")
    body = []
    for i in range(1, n + 1):
        raw = rng.rand_int(-40, 300)
        basis = max(0, raw - rng.rand_int(0, 30)) if raw > 0 else rng.rand_int(0, 20)
        draw = rng.rand_int(0, 40)
        settle = draw + rng.rand_int(0, 6)
        rec = rng.rand_int(100, 9000)
        qc_fail = 1 if rng.rand_int(0, 9) == 0 else 0
        body.append(f"r{i:04d},{rng.choice(ANALYTES)},{rng.choice(CHANNELS)},{rng.choice(METHODS)},"
                    f"{rng.choice(SPEC_UNITS)},{raw},{basis},{rec},{qc_fail},{draw},{settle}")
    perm = list(range(len(body)))
    for i in range(len(perm) - 1, 0, -1):
        j = rng.rand_int(0, i)
        perm[i], perm[j] = perm[j], perm[i]
    return "\n".join([header] + [body[k] for k in perm]) + "\n"


def _pad(header: str, n: int, cols_fn, delim: str = ",") -> str:
    lines = [header]
    for i in range(n):
        lines.append(delim.join(str(x) for x in cols_fn(i)))
    return "\n".join(lines) + "\n"


_CONVERGENCE_NOTE_TEXT = (
    '# Convergence\n'
    '\n'
    'For each batch, settle the admitted analyte masses by damped proportional rebalance toward the fair share, halving the damping after two non-improving rounds, and reporting the round count. The damping seed is a governance constant.\n'
    '\n'
    'The fair share splits a target mass across the analytes in proportion to what they already hold. The target is the batch mass when that mass sits at or below the batch cap, and the batch cap otherwise. Give each analyte its own mass times the target divided by the batch mass, keeping the floor of that division, then hand out the units still unassigned one each by largest remainder, ordering the analytes by the remainder of that same division from largest to smallest and breaking ties by analyte name ascending. A batch holding no mass has a fair share of zero for every analyte.\n'
    '\n'
    'Settle in rounds, counting the rounds from zero and running at most sixty four of them. The residual of a round is the sum over analytes of the absolute difference between the mass an analyte holds and its fair share. A round counts as non-improving when its residual is greater than or equal to the previous residual, and the damping halves by floor division once two non-improving rounds have accumulated, after which that count starts again from zero. The halved damping already applies to the flow of the round in which the second non-improving round is counted. The flow for each analyte is its fair share minus the mass it holds, multiplied by the damping, divided by ten thousand and rounded half up away from zero, so the damping seed reads as basis points like the other scaled governance figures. When the flows across a batch do not sum to zero, subtract the difference from the analyte standing furthest from its fair share, measured by the absolute difference from largest to smallest and breaking ties by analyte name ascending, which keeps the batch mass whole.\n'
    '\n'
    'Stop and report the current round index when the residual reaches zero, and report it the same way when a round yields a flow of zero for every analyte. When the round budget runs out with the batch still moving, report sixty four, the number of rounds run. A batch that cycles is reported unsettled with the lexicographically smallest state in the cycle and a round count of negative one, where the cycle begins at the first sighting of the repeated state and states compare as their masses read in analyte name order.\n'
)


_OUTPUT_CONTRACT_TEXT = (
    "# Output artifact contract\n"
    "\n"
    "This file fixes the exact shape of every report so a solver can produce byte-exact\n"
    "output. Every JSON artifact is serialized with sorted keys, compact separators\n"
    "(comma and colon, no spaces), and a single trailing newline. Integers are bare\n"
    "integers. The analyte keys are glucose, calcium, lactate and creatinine, the matrix\n"
    "keys are serum and whole_blood, and the tier keys are routine and stat. The batch\n"
    "keys are whatever batches the run admits, sorted as strings.\n"
    "\n"
    "summary.json is an object with exactly these keys: batch_totals, an object mapping\n"
    "each batch to its committed integer total; analyte_allocations, an object mapping\n"
    "each batch to an object mapping each analyte that seated at least one reading in that\n"
    "batch to its committed integer, a zero included; \n"
    "convergence_rounds, an object mapping each batch to its integer round count where a\n"
    "cycling batch is negative one; and unsettled_batches, the sorted list of batches\n"
    "whose round count is negative one.\n"
    "\n"
    "policy_audit.json is an object with exactly these keys: tier_totals, an object\n"
    "mapping each tier to its integer total, listing only the tiers that at least one\n"
    "analyte of analyte_totals belongs to, so a tier holding no such analyte is left out\n"
    "rather than written as zero; carryover_ledger, a list of objects each\n"
    "with keys analyte, clawed_units and batch, sorted by batch then analyte; \n"
    "excluded_reading_ids, the sorted list of the reading ids the qc-fail exclusion\n"
    "removed; excluded_count, its\n"
    "integer length; effective_lot, the integer effective lot; and ordered_reading_ids,\n"
    "the reading ids in processing order, which are the readings that survived that\n"
    "exclusion.\n"
    "\n"
    "data_quality.json is an object with exactly these keys: objective_value, the integer\n"
    "weighted objective; tier_totals, the same tier totals object; committed_grand_total,\n"
    "the integer sum of all analyte totals; carryover_total_units, the integer sum of\n"
    "clawed units; core_files, the list summary.json, policy_audit.json and\n"
    "panel_analyte_glucose.json in that order; and core_sha256, the digest defined below.\n"
    "\n"
    "Each of panel_analyte_glucose.json, panel_analyte_calcium.json,\n"
    "panel_analyte_lactate.json and panel_analyte_creatinine.json is an object with keys\n"
    "analyte, the analyte name; matrix, its matrix class; tier, its decision tier; \n"
    "committed_total, the integer analyte total; and per_batch, an object mapping each\n"
    "batch whose analyte_allocations entry lists that analyte to its integer, a zero included.\n"
    "\n"
    "matrix_rollup.json is an object with keys axis set to the string matrix; class_totals,\n"
    "the matrix totals object; and analyte_membership, an object mapping each analyte to\n"
    "its matrix. tier_rollup.json has keys axis set to the string tier; class_totals, the\n"
    "tier totals object; weighted_objective, the integer objective; and analyte_membership,\n"
    "an object mapping each analyte to its tier.\n"
    "\n"
    "analyte_totals.json is an object mapping each analyte that appears in\n"
    "analyte_allocations to its integer total, and the analyte_membership objects and\n"
    "tier_analyte_membership.json cover those same analytes. Both class_totals objects,\n"
    "like tier_totals, hold only the matrices or tiers those same analytes belong to.\n"
    "tier_analyte_membership.json is an object mapping each analyte to its tier.\n"
    "ordered_reading_index.json is the list of reading ids in processing order.\n"
    "excluded_readings.json is the same sorted list of qc-fail excluded reading ids.\n"
    "\n"
    "analyte_committed.csv is comma separated with the header line\n"
    "analyte,matrix,tier,committed_total and one row per analyte of the crosswalk sorted by\n"
    "analyte. batch_committed.tsv is tab separated, its header line included, with the\n"
    "columns batch, committed_total and convergence_rounds and one row per batch sorted by\n"
    "batch. matrix_weighted.psv is pipe separated, its header line included, with the\n"
    "columns tier, committed_total, tier_weight and weighted_contribution and one row per\n"
    "tier of the tier weight book sorted by tier.\n"
    "\n"
    "carryover_ledger.xml is written line by line. The first line is the declaration\n"
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    "and the second line opens the carryover_ledger root element. Then comes one line per\n"
    "clawback, in carryover_ledger order, holding two spaces and a self-closing entry element\n"
    "whose attributes are batch, analyte and clawed_units in that order. Then comes a line\n"
    "holding two spaces and a self-closing total element whose one clawed_units attribute is\n"
    "the summed clawback, and the last line closes the root element. Attribute values are\n"
    "double quoted and XML escaped, with one space between attributes and none before the\n"
    "closing slash.\n"
    "\n"
    "objective_summary.yaml has one key per line, written as the key, a colon, a space and the\n"
    "value: objective_value, committed_grand_total, excluded_count, carryover_total_units,\n"
    "effective_lot and core_sha256 in that order, then the line tier_totals: and one line per\n"
    "tier of the tier_totals object sorted by tier, indented by two spaces.\n"
    "\n"
    "reconciliation_report.md opens with this exact title line:\n"
    "# Assay QC Reconciliation Report\n"
    "then a blank line, then the objective_value, committed_grand_total,\n"
    "effective_lot and excluded_count lines, then a blank line, then this exact heading:\n"
    "## Batch totals\n"
    "then a blank line, then one bullet per batch sorted by batch written\n"
    "as a hyphen, a space, the batch key, a space and the committed total. run_status.txt\n"
    "lists status, objective_value, core_sha256 and unsettled_batches in that order, where\n"
    "status is the word SETTLED when no batch is unsettled and the word UNSETTLED\n"
    "otherwise, and unsettled_batches is the word none when no batch is unsettled and the\n"
    "unsettled batch keys joined by a comma otherwise. In both of these two files a line\n"
    "pairs its key and value with a single space and no colon, unlike objective_summary.yaml\n"
    "which pairs them with a colon and a space. Every line in both files ends with a single\n"
    "newline, and so does every line of the csv, tsv, psv, xml and yaml artifacts, the last\n"
    "line included, with no blank line after it.\n"
    "\n"
    "provenance_manifest.json is an object with keys artifact_names, the sorted list of\n"
    "every report filename the program writes into the output directory, including\n"
    "provenance_manifest.json itself and leaving out the program derive_report.py; core_files, the\n"
    "three core files in order; core_sha256, the digest; and reusable_program, the string\n"
    "/app/out/derive_report.py.\n"
    "\n"
    "The digest core_sha256 is the sha256 hex of the concatenation, in the core_files\n"
    "order, of the exact serialized bytes of summary.json, then policy_audit.json, then\n"
    "panel_analyte_glucose.json, each serialized as sorted-key compact JSON with its\n"
    "trailing newline, with no separator between them.\n"
)


def _write_specs(root: Path) -> None:
    specs = {
        "readme_pointer.md": "# Schema pointer\n\nThe run materials live beside this file. The assay capture is the spine; the crosswalk tables join analytes to matrices and matrices to tiers; the recalibration grid and the governance envelope carry the load-bearing constants. The written contract is split across the pipeline contract and the per-stage notes. Read them all and decide which inputs feed which figure.\n",
        "pipeline_contract.md": "# Pipeline contract\n\nStages run in order. First order the live readings. Then place each reading in its batch from the batch calendar. Then scale raw and basis signals by the specimen unit scale in basis points. Then apply the method exponent transform and gain. Then apply per-analyte linear recalibration from the LIVE grid sheet. Then apply the recovery reweight with the governance recovery floor. Then admit against the per-batch cap with channel carry. Then clamp the admitted result to the governance floor result and add the matrix shift. Then settle each batch by damped convergence. Then reproject each batch against the carryover ceiling. Every figure in the report is a projection of the committed per-analyte per-batch result.\n",
        "stage_note_batching.md": "# Batching\n\nEvery surviving reading belongs to one batch, chosen by its settle_slot. A batch in the calendar covers the slots from its from_slot up to but not including its to_slot. A batch is eligible only when its min_lot is less than or equal to the effective lot, so a batch asking for a higher lot than the run carries is skipped. When more than one eligible batch covers the same slot, the one appearing last in the calendar wins. A reading that no eligible batch covers takes no part in admission and adds nothing to any total, but it keeps its place in the processing order.\n",
        "stage_note_ordering.md": "# Ordering\n\nExclude every reading whose is_qc_fail is set before doing anything else. Order the surviving readings by settle_slot ascending, then draw_slot ascending, then by reading_id descending. The descending id tiebreak decides channel carry order and admission order.\n",
        "stage_note_scaling.md": "# Scaling\n\nConvert raw_signal and basis_signal to the fixed-point basis by multiplying by the specimen unit scale in basis points over ten thousand. The unit scale comes from the current unit scale table, not from any file marked superseded.\n",
        "stage_note_transform.md": "# Method transform\n\nThe method exponent selects the power: one thousand is identity, one thousand five hundred is value times its square root, two thousand is value squared. Multiply the powered basis by the method gain in basis points, then round half up at this stage. The exponent and gain come only from the LIVE grid sheet selected by the run profile tag.\n",
        "stage_note_recalibration.md": "# Recalibration\n\nApply linear recalibration to the sum of the scaled raw signal and the transformed basis. The recalibrated value is a_milli over one thousand times the input plus b_milli over one thousand, rounded half up at this stage. The a_milli and b_milli per analyte live only in the LIVE grid sheet.\n",
        "stage_note_recovery.md": "# Recovery reweight\n\nTake the reading recovery in basis points and raise it to at least the governance recovery floor. Multiply the recalibrated value by that recovery over ten thousand and round half up. The floor is a governance constant in the envelope document.\n",
        "stage_note_admission.md": "# Admission\n\nConvert the reweighted value to a whole result and add any carry standing on the channel. Admit up to the remaining per-batch cap headroom. Any excess spills forward as carry on the same channel to the next admitted reading. A whole result that comes out below zero is admitted as it stands: it spills nothing and lowers the running admitted mass of its batch. The batch cap is a governance constant.\n\nRaise the admitted whole result to at least the governance floor result, then add the matrix shift that the panel topology gives for that analyte, then hold the seated figure at zero whenever it would come out below zero. The shift is a whole-unit offset and is never scaled. Add the seated figure to the committed total for that analyte and batch.\n\nCarry can still be standing on a channel once every reading has been admitted. Take the channels in name order and add what is left on each one to the analyte and batch of the first reading that channel admitted, where a reading counts as admitted once a batch covers it, even when the cap left it no units. This late addition is not bounded by the batch cap.\n",
        "stage_note_convergence.md": _CONVERGENCE_NOTE_TEXT,
        "stage_note_carryover.md": "# Carryover reprojection\n\nFor each batch whose settled mass exceeds the carryover ceiling, claw back the excess from the largest analyte first, ties broken by analyte name, recording each clawback. The ceiling is a governance constant.\n",
        "precision_and_rounding.md": "# Rounding and precision\n\nAll arithmetic is exact integer or fixed point. The fixed-point form is signed Q16.16: a value is held as an integer equal to that value times 65536. A whole number enters the form shifted left by sixteen bits. A basis-point figure enters it as the figure times 65536 divided by ten thousand, and a milli figure as the figure times 65536 divided by one thousand, each rounded half up away from zero. The product of two fixed-point values is their integer product shifted right by sixteen bits, truncating toward zero when the product is negative. The square root of a fixed-point value is the floored integer square root of that value times 65536, and zero for a value at or below zero. Round half up away from zero to a whole fixed-point value at the method stage, the recalibration stage, and the reweight stage. A fixed-point value becomes a whole result by truncating toward zero. Carrying full precision and rounding once at the end is wrong and will disagree with the reference.\n",
        "ordering_dependencies.md": "# Ordering dependencies\n\nQC-fail exclusion happens before ordering. Ordering happens before admission. Admission carry is per channel and flows in admission order. Convergence happens after all admission. Carryover reprojection happens after convergence.\n",
        "output_artifact_contract.md": _OUTPUT_CONTRACT_TEXT,
        "field_glossary.md": "# Glossary\n\nAnalyte: a measured quantity. Matrix: a grouping of analytes carrying a matrix class, a tier, and a shift. Tier: routine or stat, each with an objective weight read from the current tier weight book. Matrix class: serum or whole_blood. Channel: the carry lane for spilled admission. Batch: a run window bounded by settle slots. Method: photometric, enzymatic, or potentiometric, selecting the exponent regime.\n",
        "footguns_and_gotchas.md": "# Known traps and footguns\n\nThe DRAFT grid sheet is not authoritative; select the LIVE sheet by the run profile tag. The flat coefficient archive and the prior recalibration shim are superseded. The scale scratch book is superseded. The prior tier weights file is superseded, so the tier objective weights come from the current tier weight book. The relaxation notes and the docx appendix restate retired governance values; the envelope is authoritative. The effective lot is the smaller of the two declared lots, not the larger, and it decides which batches are eligible. The recovery floor applies before reweighting. Rounding is staged, not once. QC-fail rows are excluded before ordering, and those excluded ids are what the excluded reading list reports. The matrix shift is added after the floor clamp and is a whole-unit offset.\n",
        "sheet_selection_rule.md": "# Sheet selection\n\nThe recalibration grid workbook holds a LIVE sheet and a DRAFT sheet. Each sheet names its calibration tag in the first row. Select the sheet whose tag equals the run profile tag. The method coefficients and the recalibration parameters both live in the selected sheet.\n",
        "governance_source_notes.md": "# Governance constants\n\nThe governance envelope document carries the recovery floor, the floor result, the damping seed, the batch cap, and the carryover ceiling. These five constants are read from that document and nowhere else is authoritative.\n",
        "exclusion_policy.md": "# QC-fail exclusion\n\nA reading whose is_qc_fail column is set is excluded from the run entirely before ordering, admission, and every rollup. Excluded readings are not out-of-batch drops; they never enter the pipeline.\n",
        "admission_cap_notes.md": "# Admission cap\n\nThe per-batch cap bounds the running admitted mass. Spill flows forward as channel carry. The batch cap is the governance batch constant.\n",
        "convergence_notes.md": "# Convergence\n\nThe damped proportional rebalance uses the governance damping seed, halving after two non-improving residual rounds. A detected cycle reports the smallest state and a round count of negative one.\n",
        "relaxation_notes.txt": "SUPERSEDED relaxation notes. An older run applied no recovery floor, used a batch cap of 1200, and rounded once at the end. None of that is current; the governance envelope and the LIVE grid sheet are authoritative.\n",
        "legacy_readme.txt": "Legacy readme. This directory once shipped flat coefficient files and a single-sheet calibration csv. Those are retained only as superseded references; the current run reads the recalibration grid workbook and the governance envelope document.\n",
    }
    for name, text in specs.items():
        (root / name).write_text(text, encoding="utf-8")


def write_corpus(root: Path, seed: int, n_readings: int) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    rng = Rng(seed)
    # ---- load-bearing files ----
    (root / "assay_capture_run.csv").write_text(_readings_csv(rng, n_readings), encoding="utf-8")
    (root / "analyte_crosswalk.csv").write_text(
        "analyte,matrix\n" + "".join(f"{a},{ANALYTE_MATRIX[a]}\n" for a in ANALYTES), encoding="utf-8")
    # panel_topology is keyed per analyte and carries its matrix_class, decision
    # tier, and after-clamp matrix shift; analyte_crosswalk resolves analyte -> matrix.
    (root / "panel_topology.csv").write_text(
        "analyte,matrix_class,tier,matrix_shift_units\n" +
        "".join(f"{a},{ANALYTE_DEF[a][0]},{ANALYTE_DEF[a][1]},{ANALYTE_DEF[a][2]}\n" for a in ANALYTES),
        encoding="utf-8")
    (root / "unit_scale_book.csv").write_text(
        "spec_unit,scale_bp\n" + "".join(f"{u},{UNIT_SCALE_BP[u]}\n" for u in SPEC_UNITS), encoding="utf-8")
    (root / "batch_calendar.csv").write_text(
        "batch,from_slot,to_slot,min_lot\n" +
        "".join(f"{b['batch']},{b['from_slot']},{b['to_slot']},{b['min_lot']}\n" for b in BATCHES),
        encoding="utf-8")
    (root / "run_profile.json").write_text(
        json.dumps({"calibration_tag": CALIBRATION_TAG, "lot_a": 6, "lot_b": 4, "mode": "settle"},
                   sort_keys=True, indent=2) + "\n", encoding="utf-8")
    _make_calibration_xlsx(root / "recalibration_grid.xlsx")
    _make_governance_pdf(root / "governance_envelope.pdf", PDF_CONSTS)

    # ---- required-format supporting / decoy files ----
    echo_rows = _readings_csv(Rng(seed ^ 0x55), 60).splitlines()[1:]
    jl = []
    for i, ln in enumerate(echo_rows):
        p = ln.split(",")
        jl.append(json.dumps({"echo_id": f"e{i:04d}", "reading_ref": p[0], "channel": p[2], "method": p[3]}))
    (root / "capture_echo_stream.jsonl").write_text("\n".join(jl) + "\n", encoding="utf-8")
    (root / "capture_shadow_ledger.ndjson").write_text("\n".join(jl) + "\n", encoding="utf-8")
    (root / "qc_flag_hint_index.jsonl").write_text(
        "\n".join(json.dumps({"qc_ref": f"h{i:04d}", "flagged": (i % 7 == 0)}) for i in range(60)) + "\n",
        encoding="utf-8")
    (root / "specimen_membership_wide.tsv").write_text(
        _pad("specimen_id\tanalyte\tmatrix\tactive", 60,
             lambda i: [f"s{i:04d}", ANALYTES[i % len(ANALYTES)], ANALYTE_MATRIX[ANALYTES[i % len(ANALYTES)]], 1 if i % 3 else 0], "\t"),
        encoding="utf-8")
    (root / "numeric_edge_notes.tsv").write_text(
        _pad("case_id\traw_signal\tbasis_signal\tnote", 48,
             lambda i: [f"edge{i:04d}", (i * 7) % 320 - 40, (i * 5) % 300, "boundary" if i % 11 == 0 else "nominal"], "\t"),
        encoding="utf-8")
    (root / "prior_recal_shim.tsv").write_text(
        "analyte\ta_milli\tb_milli\tstatus\n" + "".join(f"{a}\t1000\t0\tSUPERSEDED\n" for a in ANALYTES),
        encoding="utf-8")
    (root / "shift_scratch_table.tsv").write_text(
        "matrix_class\tmatrix_shift_units\tstatus\nserum\t0\tSUPERSEDED\nwhole_blood\t0\tSUPERSEDED\n",
        encoding="utf-8")
    (root / "reading_audit_ledger.psv").write_text(
        _pad("audit_id|reading_ref|batch_guess|note", 60,
             lambda i: [f"a{i:04d}", f"r{(i % n_readings) + 1:04d}", BATCHES[i % len(BATCHES)]["batch"], "review"], "|"),
        encoding="utf-8")
    (root / "scale_scratch_book.psv").write_text(
        "spec_unit|scale_bp|status\n" + "".join(f"{u}|10000|SUPERSEDED\n" for u in SPEC_UNITS), encoding="utf-8")
    (root / "flat_coeff_archive.csv").write_text(
        "method,exponent_milli,gain_bp,status\n" +
        "".join(f"{m},1000,{METHOD_COEFFS_LIVE[m]['gain_bp']},SUPERSEDED\n" for m in METHODS), encoding="utf-8")
    (root / "drift_qc_reference.csv").write_text(
        _pad("qc_id,analyte,bias_milli,cv_milli", 60,
             lambda i: [f"d{i:04d}", ANALYTES[i % len(ANALYTES)], (i * 13) % 900, (i * 17) % 800]),
        encoding="utf-8")
    (root / "calibration_tag_history.csv").write_text(
        "tag,status,issued_slot\nASSAYCAL-L5,retired,10\nASSAYCAL-L6,retired,20\n"
        f"{CALIBRATION_TAG},live,30\nASSAYCAL-DRAFT,draft,31\n", encoding="utf-8")
    (root / "lot_ledger.csv").write_text(
        "lot_axis,value,note\nlot_a,6,current\nlot_b,4,current\n", encoding="utf-8")
    (root / "supersession_index.csv").write_text(
        "file,status,superseded_by\n"
        "flat_coeff_archive.csv,SUPERSEDED,recalibration_grid.xlsx\n"
        "prior_recal_shim.tsv,SUPERSEDED,recalibration_grid.xlsx\n"
        "scale_scratch_book.psv,SUPERSEDED,unit_scale_book.csv\n"
        "shift_scratch_table.tsv,SUPERSEDED,panel_topology.csv\n"
        "prior_tier_weights.yaml,SUPERSEDED,tier_weight_book.json\n"
        "relaxation_notes.txt,SUPERSEDED,governance_envelope.pdf\n", encoding="utf-8")
    (root / "tier_weight_book.json").write_text(
        json.dumps(TIER_WEIGHT, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (root / "matrix_membership_echo.json").write_text(
        json.dumps({a: ANALYTE_DEF[a][0] for a in ANALYTES}, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (root / "prior_tier_weights.yaml").write_text(
        "status: SUPERSEDED\nstat: 4\nroutine: 1\n", encoding="utf-8")
    (root / "recovery_handling.yml").write_text(
        "status: current\nrecovery_floor_source: governance_envelope.pdf\n"
        "note: apply floor before reweighting; reweight numerator is basis points over 10000\n", encoding="utf-8")
    (root / "regime_catalog.yaml").write_text(
        "status: current\nexponent_milli:\n  identity: 1000\n  sqrt_boost: 1500\n  square: 2000\n"
        "authoritative_source: recalibration_grid.xlsx LIVE sheet\n", encoding="utf-8")
    (root / "carryover_handling.yaml").write_text(
        "status: current\nceiling_source: governance_envelope.pdf\n"
        "note: reproject per batch against ceiling; claw largest analyte first\n", encoding="utf-8")
    (root / "batch_catalog.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<batches>\n' +
        "".join(f'  <batch name="{b["batch"]}" from_slot="{b["from_slot"]}" to_slot="{b["to_slot"]}" min_lot="{b["min_lot"]}"/>\n' for b in BATCHES) +
        "</batches>\n", encoding="utf-8")
    (root / "source_lineage.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<lineage>\n'
        '  <authoritative name="recalibration_grid.xlsx" kind="xlsx"/>\n'
        '  <authoritative name="governance_envelope.pdf" kind="pdf"/>\n'
        '  <authoritative name="assay_capture_run.csv" kind="csv"/>\n'
        '</lineage>\n', encoding="utf-8")
    _sqlite_dims(root / "analyte_index.sqlite", ["analyte"])
    _sqlite_dims(root / "reference_lookups.db", ["panel", "unit"])
    _make_docx(root / "governance_appendix.docx")
    _write_specs(root)
    return root


# ---------------------------------------------------------------------------
# Probe corpora for dedicated numerical traps (small, hand-built).
# ---------------------------------------------------------------------------
PROBE_SEED = 6287431905514772283


def _write_calendar(root: Path, batches: list[dict[str, Any]]) -> None:
    def attr(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    (root / "batch_calendar.csv").write_text(
        "batch,from_slot,to_slot,min_lot\n" +
        "".join(f"{b['batch']},{b['from_slot']},{b['to_slot']},{b['min_lot']}\n" for b in batches),
        encoding="utf-8")
    (root / "batch_catalog.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<batches>\n' +
        "".join(f'  <batch name="{attr(b["batch"])}" from_slot="{b["from_slot"]}" to_slot="{b["to_slot"]}" '
                f'min_lot="{b["min_lot"]}"/>\n' for b in batches) +
        "</batches>\n", encoding="utf-8")


def _probe_corpus(root: Path, rows: list[str], consts: dict[str, int] | None = None,
                  profile: dict[str, Any] | None = None,
                  calendar: list[dict[str, Any]] | None = None) -> Path:
    """Build a probe as a COMPLETE corpus and then substitute the readings, and
    the governance constants, the run profile or the batch calendar when the
    probe needs different ones. Every file the shipped run carries is present, so
    a program that reads any documented input (the tier weight book, a spec note,
    a crosswalk) finds it here too. Writing only the handful of files the
    reference happens to touch would punish an honest program for reading a file
    the contract points it at."""
    write_corpus(root, PROBE_SEED, max(2, len(rows)))
    if consts is not None:
        _make_governance_pdf(root / "governance_envelope.pdf", consts)
    if profile is not None:
        (root / "run_profile.json").write_text(
            json.dumps(profile, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    if calendar is not None:
        _write_calendar(root, calendar)
    hdr = ("reading_id,analyte,channel,method,spec_unit,raw_signal,basis_signal,recovery_bp,"
           "is_qc_fail,draw_slot,settle_slot")
    (root / "assay_capture_run.csv").write_text("\n".join([hdr] + rows) + "\n", encoding="utf-8")
    return root


def _staged_probe(root: Path) -> Path:
    rows = [
        "r0001,lactate,ch2,potentiometric,mmol_l,123,102,3895,0,11,16",
        "r0002,lactate,ch0,potentiometric,mg_dl,74,72,6415,0,34,39",
        "r0003,creatinine,ch2,enzymatic,mmol_l,135,111,3219,0,34,40",
        "r0004,glucose,ch3,potentiometric,mabs,212,202,1251,0,19,19",
        "r0005,creatinine,ch0,photometric,mg_dl,179,160,4711,0,32,32",
        "r0006,calcium,ch1,potentiometric,mabs,154,142,3508,0,8,9",
        "r0007,creatinine,ch1,enzymatic,mg_dl,160,137,3400,0,28,30",
        "r0008,glucose,ch1,enzymatic,mg_dl,77,56,4573,0,5,9",
        "r0009,glucose,ch0,potentiometric,mmol_l,41,20,5385,0,27,33",
        "r0010,calcium,ch3,photometric,mmol_l,54,37,6297,0,40,40",
    ]
    return _probe_corpus(root, rows)


# Load-bearing: this seed and cap are the pair under which b_open and b_ramp both
# cycle. Change either and the cycles vanish, so the -1 round count and the
# UNSETTLED branch stop being exercised while the test still passes. They also
# differ from the shipped run, so hardcoding the five constants rather than reading
# the pdf fails here. The two cycles place the lexicographically smallest state at
# opposite ends: in b_open it is the last state before the repeat, in b_ramp it is
# the repeated state itself, so reporting either end instead of the smallest state
# changes the reported spine.
_CYCLING_CONSTS = {"RECOVERY_FLOOR_BP": 350, "FLOOR_RESULT": 5, "DAMPING_SEED": 18000,
                   "BATCH_CAP": 70, "CARRYOVER_CEILING": 900}

# 480 deliberately differs from the shipped 350: only a program that reads the floor
# from the envelope document can raise recovery to it on an unseen run.
_FLOOR_PROBE_CONSTS = {"RECOVERY_FLOOR_BP": 480, "FLOOR_RESULT": 5, "DAMPING_SEED": 14000,
                       "BATCH_CAP": 900, "CARRYOVER_CEILING": 1200}


def _cycling_probe(root: Path) -> Path:
    rows = ["r0001,calcium,ch0,photometric,mabs,20,13,2035,0,1,14",
            "r0002,creatinine,ch1,photometric,mmol_l,14,14,2699,0,2,9",
            "r0003,lactate,ch0,enzymatic,mmol_l,5,17,3991,0,3,1",
            "r0004,creatinine,ch1,potentiometric,mg_dl,16,40,2848,0,4,14",
            "r0005,creatinine,ch3,enzymatic,mmol_l,11,6,1047,0,19,19",
            "r0006,glucose,ch3,enzymatic,mg_dl,36,48,4398,0,16,19"]
    return _probe_corpus(root, rows, _CYCLING_CONSTS)


# Load-bearing: glucose and calcium seat on exactly equal committed mass here and
# the cap sits below their total, so both analytes stand the same distance from
# their fair share. That equal distance is the only situation in which the
# convergence note's "breaking ties by analyte name ascending" anchor rule decides
# anything. Retune any of these numbers and the rule silently stops being graded.
_CONVERGENCE_TIE_CONSTS = {"RECOVERY_FLOOR_BP": 350, "FLOOR_RESULT": 5, "DAMPING_SEED": 9000,
                           "BATCH_CAP": 60, "CARRYOVER_CEILING": 172}


def _convergence_tie_probe(root: Path) -> Path:
    rows = ["r0001,glucose,ch0,photometric,mg_dl,13,13,10000,0,1,1",
            "r0002,calcium,ch1,photometric,mg_dl,45,45,10000,0,2,2"]
    return _probe_corpus(root, rows, _CONVERGENCE_TIE_CONSTS)


# Load-bearing: glucose and lactate seat on exactly equal committed mass here, and
# the ceiling leaves an excess smaller than one of them, so the carryover note's
# "ties broken by analyte name" rule decides which analyte is clawed.
_CLAWBACK_TIE_CONSTS = {"RECOVERY_FLOOR_BP": 350, "FLOOR_RESULT": 5, "DAMPING_SEED": 14000,
                        "BATCH_CAP": 900, "CARRYOVER_CEILING": 300}


def _clawback_tie_probe(root: Path) -> Path:
    rows = ["r0001,glucose,ch0,photometric,mg_dl,71,71,10000,0,1,1",
            "r0002,lactate,ch1,photometric,mg_dl,84,84,10000,0,2,2"]
    return _probe_corpus(root, rows, _CLAWBACK_TIE_CONSTS)


# Load-bearing: the two declared lots are swapped in magnitude against the
# shipped run and straddle b_recheck's min_lot of 5, so the smaller lot (3) and
# the larger lot (9) disagree twice over. They disagree on the reported
# effective lot, and they disagree on batch eligibility, because the readings
# below settle in slots 29 and 30 where b_recheck is the last calendar entry
# covering the slot and therefore wins whenever it is eligible. A program that
# takes the maximum, or that transcribes the shipped run's lot of 4, produces a
# different effective lot AND a different batch set here. Retune these lots or
# the settle slots and the smaller-lot rule stops being graded on unseen data.
_LOT_PROBE_PROFILE = {"calibration_tag": CALIBRATION_TAG, "lot_a": 9, "lot_b": 3,
                      "mode": "settle"}


def _lot_probe(root: Path) -> Path:
    rows = ["r0001,glucose,ch0,photometric,mg_dl,64,61,10000,0,20,29",
            "r0002,calcium,ch1,enzymatic,mmol_l,88,80,7200,0,22,30",
            "r0003,lactate,ch2,potentiometric,mabs,45,41,6100,0,4,8",
            "r0004,creatinine,ch3,photometric,mg_dl,120,117,5300,0,31,35"]
    return _probe_corpus(root, rows, profile=_LOT_PROBE_PROFILE)


# Load-bearing: both declared lots reach b_recheck's min_lot of 5, so b_recheck is
# eligible and overlaps b_ramp at slot 29 and b_plateau at slot 30. Only the
# batching note's "the one appearing last in the calendar wins" rule seats r0001
# and r0002 in b_recheck. r0003 settles at slot 61, which no batch covers, so it
# must add nothing to any total yet keep its place in the processing order. The
# "up to but not including its to_slot" rule decides r0006 and r0007: slot 31 is
# b_recheck's to_slot, so r0006 belongs to b_plateau, and slot 60 is b_plateau's
# to_slot, so r0007 is uncovered. An inclusive upper bound seats r0006 in
# b_recheck and r0007 in b_plateau. Every batch stays far below the carryover
# ceiling, so its total is never a constant that can be copied out of the
# envelope document.
_PLACEMENT_PROBE_PROFILE = {"calibration_tag": CALIBRATION_TAG, "lot_a": 8, "lot_b": 5,
                            "mode": "settle"}


def _placement_probe(root: Path) -> Path:
    rows = ["r0001,glucose,ch0,photometric,mg_dl,60,55,6000,0,22,29",
            "r0002,calcium,ch1,photometric,mg_dl,70,64,7000,0,24,30",
            "r0003,lactate,ch2,photometric,mg_dl,50,45,8000,0,55,61",
            "r0004,creatinine,ch3,photometric,mg_dl,40,38,9000,0,3,10",
            "r0005,glucose,ch0,photometric,mg_dl,45,40,5000,0,35,40",
            "r0006,lactate,ch2,photometric,mg_dl,30,28,6000,0,26,31",
            "r0007,creatinine,ch3,photometric,mg_dl,35,30,7000,0,50,60"]
    return _probe_corpus(root, rows, profile=_PLACEMENT_PROBE_PROFILE)


# Load-bearing: the two flagged glucose readings settle first, on ch0, and
# together would overrun the batch cap and leave carry on ch0. Admitting them at
# any stage changes the committed spine; only excluding them before the pipeline
# reproduces the reference.
def _qc_probe(root: Path) -> Path:
    rows = ["r0001,glucose,ch0,photometric,mg_dl,300,290,9000,1,1,1",
            "r0002,glucose,ch0,photometric,mg_dl,300,290,9000,1,1,2",
            "r0003,calcium,ch0,photometric,mg_dl,120,110,8000,0,2,3",
            "r0004,lactate,ch1,photometric,mg_dl,90,80,7000,0,3,4",
            "r0005,creatinine,ch0,photometric,mg_dl,60,55,6000,0,4,5"]
    return _probe_corpus(root, rows)


# Load-bearing: r0001 and r0002 overrun the batch cap on ch0, so carry is still
# standing on ch0 when r0004 is processed. r0004 settles at slot 61, which no
# batch covers, so it takes no part in admission: the carry must stay on the
# channel and be seated at the end of the run on ch0's first seat. A program that
# lets the uncovered reading consume or clear the carry loses those units.
def _carry_probe(root: Path) -> Path:
    rows = ["r0001,glucose,ch0,photometric,mg_dl,300,290,9000,0,1,1",
            "r0002,glucose,ch0,photometric,mg_dl,300,290,9000,0,1,2",
            "r0003,calcium,ch1,photometric,mg_dl,80,75,8000,0,2,3",
            "r0004,lactate,ch0,photometric,mg_dl,50,45,8000,0,55,61"]
    return _probe_corpus(root, rows)


# Load-bearing: with this damping seed and cap, b_open is still moving when the
# sixty-four round budget runs out, so its round count is 64 and its masses are
# the state after the last round; and b_plateau meets two consecutive rounds of
# equal residual, which count as non-improving and halve the damping. A program
# that drops the budget, reports 63, or treats only a larger residual as
# non-improving settles to a different spine or round count. Retune any value
# and either rule silently stops being graded.
_ROUND_CONTROL_CONSTS = {"RECOVERY_FLOOR_BP": 350, "FLOOR_RESULT": 5, "DAMPING_SEED": 79025,
                         "BATCH_CAP": 379, "CARRYOVER_CEILING": 5000}


def _round_control_probe(root: Path) -> Path:
    rows = ["r0001,calcium,ch2,enzymatic,mabs,13,58,8185,0,4,4",
            "r0002,creatinine,ch0,enzymatic,mg_dl,26,118,9592,0,2,2",
            "r0003,calcium,ch3,potentiometric,mmol_l,106,35,7326,0,9,9",
            "r0004,creatinine,ch1,enzymatic,mmol_l,52,71,6440,0,41,41",
            "r0005,calcium,ch1,enzymatic,mg_dl,23,26,2756,0,19,19",
            "r0006,lactate,ch1,potentiometric,mg_dl,82,6,4246,0,42,42",
            "r0007,glucose,ch1,photometric,mabs,65,27,1203,0,41,41"]
    return _probe_corpus(root, rows, _ROUND_CONTROL_CONSTS)


# Load-bearing: only glucose and creatinine read here, both routine, so calcium
# and lactate are absent from analyte_totals and the stat tier is absent from
# tier_totals. analyte_committed.csv must still carry a row for every crosswalk
# analyte and matrix_weighted.psv a row for every tier of the tier weight book.
# The second batch is named b_r&d and the low ceiling claws from it, so the
# ledger entry's batch attribute must be XML escaped.
_SPARSE_CONSTS = {"RECOVERY_FLOOR_BP": 350, "FLOOR_RESULT": 5, "DAMPING_SEED": 14000,
                  "BATCH_CAP": 900, "CARRYOVER_CEILING": 200}
_SPARSE_CALENDAR = [
    {"batch": "b_open", "from_slot": 0, "to_slot": 15, "min_lot": 0},
    {"batch": "b_r&d", "from_slot": 15, "to_slot": 30, "min_lot": 0},
    {"batch": "b_plateau", "from_slot": 30, "to_slot": 60, "min_lot": 0},
    {"batch": "b_recheck", "from_slot": 29, "to_slot": 31, "min_lot": 5},
]


def _sparse_probe(root: Path) -> Path:
    rows = ["r0001,glucose,ch0,photometric,mg_dl,90,85,9000,0,2,3",
            "r0002,creatinine,ch1,photometric,mg_dl,60,55,8000,0,4,6",
            "r0003,glucose,ch2,photometric,mg_dl,120,110,9000,0,16,18",
            "r0004,creatinine,ch3,photometric,mg_dl,70,66,7000,0,20,24",
            "r0005,glucose,ch0,photometric,mg_dl,40,35,6000,0,33,41"]
    return _probe_corpus(root, rows, _SPARSE_CONSTS, calendar=_SPARSE_CALENDAR)


def _perturb_superseded(root: Path) -> None:
    """Rewrite every file supersession_index.csv lists with different values in
    the same layout. A program that derives nothing from retired files writes
    the same artifacts before and after."""
    (root / "flat_coeff_archive.csv").write_text(
        "method,exponent_milli,gain_bp,status\n"
        "photometric,1500,11111,SUPERSEDED\nenzymatic,2000,10311,SUPERSEDED\n"
        "potentiometric,1500,1411,SUPERSEDED\n", encoding="utf-8")
    (root / "prior_recal_shim.tsv").write_text(
        "analyte\ta_milli\tb_milli\tstatus\n" + "".join(f"{a}\t1333\t77\tSUPERSEDED\n" for a in ANALYTES),
        encoding="utf-8")
    (root / "scale_scratch_book.psv").write_text(
        "spec_unit|scale_bp|status\n" + "".join(f"{u}|11111|SUPERSEDED\n" for u in SPEC_UNITS), encoding="utf-8")
    (root / "shift_scratch_table.tsv").write_text(
        "matrix_class\tmatrix_shift_units\tstatus\nserum\t7\tSUPERSEDED\nwhole_blood\t-9\tSUPERSEDED\n",
        encoding="utf-8")
    (root / "prior_tier_weights.yaml").write_text("status: SUPERSEDED\nstat: 9\nroutine: 3\n", encoding="utf-8")
    (root / "relaxation_notes.txt").write_text(
        "SUPERSEDED relaxation notes. An older run applied no recovery floor, used a batch cap of 1350, "
        "and rounded once at the end. None of that is current; the governance envelope and the LIVE grid "
        "sheet are authoritative.\n", encoding="utf-8")


def _probe_run(workspace: Path, build) -> tuple[Path, dict[str, str]]:
    """Run the delivered program on a freshly built probe; return its output
    directory and the reference artifacts for the same probe. The caller reads
    the output inside the same temporary tree, which is kept for the process."""
    tp = Path(tempfile.mkdtemp(prefix="assay-probe-"))
    data = build(tp / "data")
    out = tp / "out"
    _run_agent(script_of(workspace), data, out, tp)
    return out, reference(data)


# Unseen regenerations of the shipped run: the same generator and size under
# seeds the agent never sees. The shipped answers are in the agent's hands, so
# every check that grades a figure of the shipped run also grades that figure
# here, and a program that only replays the shipped outputs earns nothing for it.
# Load-bearing: these two seeds exercise exactly the rules the shipped run
# exercises, so a program right or wrong on any single rule scores what the
# shipped run alone would give it. Retune either seed and a rule the shipped run
# never triggers, such as the descending id tiebreak or the recovery floor,
# starts costing points here as well.
_SHADOW_SEED = SAMPLE_SEED ^ 0xAAAA
# The four per-analyte docs restate the spine, so they are graded on a run of
# their own rather than the one analyte_allocations_match_reference reads.
_DOCS_SEED = SAMPLE_SEED ^ 0x4444
PANEL_DOC_NAMES = ("panel_analyte_glucose.json", "panel_analyte_calcium.json",
                   "panel_analyte_lactate.json", "panel_analyte_creatinine.json")


def _shadow_corpus(root: Path) -> Path:
    return write_corpus(root, _SHADOW_SEED, 90)


def _docs_corpus(root: Path) -> Path:
    return write_corpus(root, _DOCS_SEED, 90)


def _unseen_matches(workspace: Path, build, name: str, keys: tuple[str, ...]) -> bool:
    """Run the delivered program on an unseen corpus and compare the named keys
    of one JSON artifact, or the whole parsed artifact when no key is named,
    with the reference for that corpus."""
    out, exp = _probe_run(workspace, build)
    got = json.loads((out / name).read_text(encoding="utf-8"))
    want = json.loads(exp[name])
    if not keys:
        return got == want
    return all(got[key] == want[key] for key in keys)


# ---------------------------------------------------------------------------
# Corpus caches + run helpers.
# ---------------------------------------------------------------------------
_VISIBLE: Path | None = None
_VISIBLE_LOCK = threading.Lock()
# rewardkit runs the checks concurrently in worker threads, so every cache below
# is filled under a lock and then only read.
_VISIBLE_RUNS: dict[tuple[str, int, int], Path | None] = {}
_VISIBLE_RUN_LOCK = threading.Lock()


def visible_inputs() -> Path:
    global _VISIBLE
    with _VISIBLE_LOCK:
        if _VISIBLE is None:
            _VISIBLE = write_corpus(Path(tempfile.mkdtemp(prefix="assay-visible-")), SAMPLE_SEED, 90)
        return _VISIBLE


def out_of(workspace: Path) -> Path:
    """The agent's declared output directory. The harness sets the rewardkit
    workspace to /app and every declared artifact path is /app/out/<name>."""
    return workspace / "out"


def script_of(workspace: Path) -> Path:
    return out_of(workspace) / SCRIPT_NAME


def _guard(fn, *args) -> bool:
    """Run a check body and convert any failure into a plain False.

    rewardkit aborts the whole run when a check raises, and an aborted run
    writes no reward at all, so missing, truncated or garbage agent output has
    to come back as False rather than as an exception."""
    try:
        return bool(fn(*args))
    except Exception:
        return False


def actual(out_dir: Path, name: str) -> Any:
    return json.loads((out_dir / name).read_text(encoding="utf-8"))


def _untrusted(command: list[str]) -> list[str]:
    if os.name == "posix" and os.geteuid() == 0:
        return [*_SETPRIV, *command]
    return command


def _run_agent(script: Path, data_dir: Path, out_dir: Path, td: Path) -> None:
    """Run the delivered program as an unprivileged subprocess in its own process
    group. Its output is drained, and the whole group is killed before this
    returns, so nothing the program spawned outlives the check.

    The program runs from a copy made readable to every user. The declared
    artifact keeps whatever mode the agent's editor gave it, and an editor that
    saves owner-only (0600) would otherwise leave the unprivileged user unable
    to open the file at all, failing every check that runs the program for a
    reason that has nothing to do with the program."""
    td.chmod(0o777)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_dir.chmod(0o777)
    runnable = td / SCRIPT_NAME
    shutil.copyfile(script, runnable)
    runnable.chmod(0o644)
    proc = subprocess.Popen(_untrusted([sys.executable, str(runnable), str(data_dir), str(out_dir)]),
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, start_new_session=True)
    try:
        proc.communicate(timeout=60)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"delivered program exited with {proc.returncode}")


def _visible_run(workspace: Path) -> Path:
    """Output directory of the delivered program run on a freshly regenerated copy
    of the shipped run. Computed once per delivered program and cached."""
    script = script_of(workspace)
    st = script.stat()
    key = (str(script), st.st_mtime_ns, st.st_size)
    with _VISIBLE_RUN_LOCK:
        if key not in _VISIBLE_RUNS:
            tp = Path(tempfile.mkdtemp(prefix="assay-visible-run-"))
            data = write_corpus(tp / "data", SAMPLE_SEED, 90)
            out = tp / "out"
            try:
                _run_agent(script, data, out, tp)
                _VISIBLE_RUNS[key] = out
            except Exception:
                _VISIBLE_RUNS[key] = None
        out = _VISIBLE_RUNS[key]
    if out is None:
        raise RuntimeError("the delivered program did not run on the shipped run")
    return out


def delivered_text(workspace: Path, name: str) -> str:
    """The declared artifact's text, accepted only when the delivered program
    writes exactly the same bytes when run on the shipped run. A hand-written
    artifact with no working program behind it is rejected here."""
    text = (out_of(workspace) / name).read_text(encoding="utf-8")
    if (_visible_run(workspace) / name).read_text(encoding="utf-8") != text:
        raise ValueError(f"{name} is not what the delivered program writes")
    return text


def delivered(workspace: Path, name: str) -> Any:
    return json.loads(delivered_text(workspace, name))


def _fold_str_concat(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _fold_str_concat(node.left)
        right = _fold_str_concat(node.right)
        if left is not None and right is not None:
            return left + right
    return None


_DOC_KEYWORDS = frozenset({"help", "description", "epilog", "usage"})


def _runtime_string_literals(out_dir: Path) -> str:
    """Every string literal in the delivered program that the program can use.
    Comments, docstrings and any other bare string statement are excluded, and
    so is any literal inside a help, description, epilog or usage keyword
    argument: a docstring is a no-op and help text is only ever printed, so
    naming a sample reading or a path there is honest documentation rather than
    a hardwired value. Adjacent concatenations are folded so that splitting a
    value across two literals does not evade the scan."""
    found: list[str] = []
    for path in sorted(out_dir.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        documentation: set[int] = set()
        for node in ast.walk(tree):
            if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)):
                documentation.add(id(node.value))
            elif isinstance(node, ast.keyword) and node.arg in _DOC_KEYWORDS:
                documentation.update(id(inner) for inner in ast.walk(node.value))
        for node in ast.walk(tree):
            if id(node) in documentation:
                continue
            if isinstance(node, ast.BinOp):
                folded = _fold_str_concat(node)
                if folded is not None:
                    found.append(folded)
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                found.append(node.value)
    return "\n".join(found)


# ---------------------------------------------------------------------------
# The full-core gate.
# ---------------------------------------------------------------------------
def _program_present(workspace: Path) -> bool:
    """Precondition for the mid-derivation checks: the reusable program was
    delivered. Those checks then grade one observable each on its own, so a
    single wrong figure costs that figure rather than the whole positive suite."""
    return script_of(workspace).is_file()


def _full_core_matches(workspace: Path) -> bool:
    """True only when the entire three-file core matches the reference on the
    visible corpus, byte for byte. Gate for the whole-document and digest
    checks only, never for the mid-derivation checks, so partial credit stays
    partial."""
    if not _program_present(workspace):
        return False
    expected = reference(visible_inputs())
    return all(delivered_text(workspace, name) == expected[name] for name in CORE_NAMES)


# ---------------------------------------------------------------------------
# Check bodies. Each is plain logic returning a bool; the @criterion wrappers
# below run them through _guard so a crash becomes False instead of aborting
# the run.
# ---------------------------------------------------------------------------
def _artifact_set_exists_and_parses(workspace: Path) -> bool:
    out_dir = out_of(workspace)
    if not _program_present(workspace):
        return False
    for name in ARTIFACT_NAMES:
        if not (out_dir / name).is_file():
            return False
    for name in ARTIFACT_NAMES:
        if name.endswith(".json") and not isinstance(actual(out_dir, name), (dict, list)):
            return False
    return True


def _summary_schema_shape(workspace: Path) -> bool:
    return set(actual(out_of(workspace), "summary.json")) == {
        "batch_totals", "analyte_allocations", "convergence_rounds", "unsettled_batches"}


def _policy_audit_schema_shape(workspace: Path) -> bool:
    return set(actual(out_of(workspace), "policy_audit.json")) == {
        "tier_totals", "carryover_ledger", "excluded_reading_ids", "excluded_count",
        "effective_lot", "ordered_reading_ids"}


def _data_quality_schema_shape(workspace: Path) -> bool:
    return set(actual(out_of(workspace), "data_quality.json")) == {
        "objective_value", "tier_totals", "committed_grand_total", "carryover_total_units",
        "core_files", "core_sha256"}


def _manifest_declares_core_order_and_names(workspace: Path) -> bool:
    man = actual(out_of(workspace), "provenance_manifest.json")
    return man["core_files"] == CORE_NAMES and man["artifact_names"] == sorted(ARTIFACT_NAMES)


def _canonical_serialization_sorted_compact(workspace: Path) -> bool:
    out_dir = out_of(workspace)
    for name in ARTIFACT_NAMES:
        if not name.endswith(".json"):
            continue
        text = (out_dir / name).read_text(encoding="utf-8")
        if not text.endswith("\n"):
            return False
        if text != json.dumps(json.loads(text), sort_keys=True, separators=(",", ":")) + "\n":
            return False
    return True


def _effective_lot_is_smaller_of_two(workspace: Path) -> bool:
    """The smaller-lot rule, graded on the shipped run and again on a probe
    whose two lots differ from it. The probe run is what makes this check
    about the rule rather than about the integer: the effective lot is visible
    in run_profile.json, so comparing only the shipped figure pays out to a
    hand-written artifact that transcribes it without doing any work."""
    if not _program_present(workspace):
        return False
    want = json.loads(reference(visible_inputs())["policy_audit.json"])["effective_lot"]
    if delivered(workspace, "policy_audit.json")["effective_lot"] != want:
        return False
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        data = _lot_probe(tp / "data")
        out = tp / "out"
        _run_agent(script_of(workspace), data, out, tp)
        exp = reference(data)
        got_lot = json.loads((out / "policy_audit.json").read_text(encoding="utf-8"))["effective_lot"]
        if got_lot != json.loads(exp["policy_audit.json"])["effective_lot"]:
            return False
        got_batches = json.loads((out / "summary.json").read_text(encoding="utf-8"))["batch_totals"]
        want_batches = json.loads(exp["summary.json"])["batch_totals"]
        return sorted(got_batches) == sorted(want_batches)


def _ordered_reading_ids_match_tiebreak(workspace: Path) -> bool:
    """Shipped run (thirteen settle/draw ties) plus the placement probe, where a
    reading no batch covers must still keep its place in the order."""
    if not _program_present(workspace):
        return False
    if (delivered(workspace, "policy_audit.json")["ordered_reading_ids"]
            != json.loads(reference(visible_inputs())["policy_audit.json"])["ordered_reading_ids"]):
        return False
    out, exp = _probe_run(workspace, _placement_probe)
    got = json.loads((out / "policy_audit.json").read_text(encoding="utf-8"))
    return got["ordered_reading_ids"] == json.loads(exp["policy_audit.json"])["ordered_reading_ids"]


def _qc_fail_rows_excluded_before_ordering(workspace: Path) -> bool:
    if not _program_present(workspace):
        return False
    out, exp = _probe_run(workspace, _qc_probe)
    got = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    return got["analyte_allocations"] == json.loads(exp["summary.json"])["analyte_allocations"]


def _batch_totals_match_reference(workspace: Path) -> bool:
    """Shipped run plus the placement probe, whose totals sit below the ceiling
    and depend on the last-entry-wins and uncovered-slot batching rules."""
    if not _program_present(workspace):
        return False
    if (delivered(workspace, "summary.json")["batch_totals"]
            != json.loads(reference(visible_inputs())["summary.json"])["batch_totals"]):
        return False
    out, exp = _probe_run(workspace, _placement_probe)
    got = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    return got["batch_totals"] == json.loads(exp["summary.json"])["batch_totals"]


def _analyte_allocations_match_reference(workspace: Path) -> bool:
    if not _program_present(workspace):
        return False
    if (delivered(workspace, "summary.json")["analyte_allocations"]
            != json.loads(reference(visible_inputs())["summary.json"])["analyte_allocations"]):
        return False
    return _unseen_matches(workspace, _shadow_corpus, "summary.json", ("analyte_allocations",))


def _convergence_rounds_match_reference(workspace: Path) -> bool:
    if not _program_present(workspace):
        return False
    if (delivered(workspace, "summary.json")["convergence_rounds"]
            != json.loads(reference(visible_inputs())["summary.json"])["convergence_rounds"]):
        return False
    return _unseen_matches(workspace, _shadow_corpus, "summary.json", ("convergence_rounds",))


def _tier_totals_partition_match(workspace: Path) -> bool:
    if not _program_present(workspace):
        return False
    if (delivered(workspace, "policy_audit.json")["tier_totals"]
            != json.loads(reference(visible_inputs())["policy_audit.json"])["tier_totals"]):
        return False
    return _unseen_matches(workspace, _shadow_corpus, "policy_audit.json", ("tier_totals",))


def _analyte_totals_match_reference(workspace: Path) -> bool:
    if not _program_present(workspace):
        return False
    if (delivered(workspace, "analyte_totals.json")
            != json.loads(reference(visible_inputs())["analyte_totals.json"])):
        return False
    return _unseen_matches(workspace, _shadow_corpus, "analyte_totals.json", ())


def _four_analyte_docs_match_reference(workspace: Path) -> bool:
    """Graded on its own unseen run only. On the shipped run the docs carry the
    per_batch and committed_total figures that analyte_allocations_match_reference
    and analyte_totals_match_reference already grade, and the shipped docs are
    still compared byte for byte by all_artifacts_exact_on_visible."""
    if not _program_present(workspace):
        return False
    out, exp = _probe_run(workspace, _docs_corpus)
    return all(json.loads((out / name).read_text(encoding="utf-8")) == json.loads(exp[name])
               for name in PANEL_DOC_NAMES)


def _carryover_ledger_matches_reference(workspace: Path) -> bool:
    if not _program_present(workspace):
        return False
    if (delivered(workspace, "policy_audit.json")["carryover_ledger"]
            != json.loads(reference(visible_inputs())["policy_audit.json"])["carryover_ledger"]):
        return False
    return _unseen_matches(workspace, _shadow_corpus, "policy_audit.json", ("carryover_ledger",))


def _excluded_readings_match_reference(workspace: Path) -> bool:
    if not _program_present(workspace):
        return False
    exp = json.loads(reference(visible_inputs())["policy_audit.json"])
    got = delivered(workspace, "policy_audit.json")
    if (got["excluded_reading_ids"] != exp["excluded_reading_ids"]
            or got["excluded_count"] != exp["excluded_count"]):
        return False
    return _unseen_matches(workspace, _shadow_corpus, "policy_audit.json",
                           ("excluded_reading_ids", "excluded_count"))


def _convergence_anchor_tie_break_applied(workspace: Path) -> bool:
    if not _program_present(workspace):
        return False
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        data = _convergence_tie_probe(tp / "data")
        out = tp / "out"
        _run_agent(script_of(workspace), data, out, tp)
        return (out / "summary.json").read_text(encoding="utf-8") == reference(data)["summary.json"]


def _carryover_clawback_tie_break_applied(workspace: Path) -> bool:
    if not _program_present(workspace):
        return False
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        data = _clawback_tie_probe(tp / "data")
        out = tp / "out"
        _run_agent(script_of(workspace), data, out, tp)
        exp = json.loads(reference(data)["policy_audit.json"])
        got = json.loads((out / "policy_audit.json").read_text(encoding="utf-8"))
        return got["carryover_ledger"] == exp["carryover_ledger"]


def _core_three_files_all_exact_on_challenge(workspace: Path) -> bool:
    if not _full_core_matches(workspace):
        return False
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        data = write_corpus(tp / "data", CHALLENGE_SEED ^ 0x2B2B, 96)
        out = tp / "out"
        _run_agent(script_of(workspace), data, out, tp)
        expected = reference(data)
        return all((out / name).read_text(encoding="utf-8") == expected[name]
                   for name in CORE_NAMES)


def _cycling_batch_reports_unsettled(workspace: Path) -> bool:
    if not _program_present(workspace):
        return False
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        data = _cycling_probe(tp / "data")
        out = tp / "out"
        _run_agent(script_of(workspace), data, out, tp)
        exp = reference(data)
        got = json.loads((out / "summary.json").read_text(encoding="utf-8"))
        want = json.loads(exp["summary.json"])
        return (got["convergence_rounds"] == want["convergence_rounds"]
                and got["unsettled_batches"] == want["unsettled_batches"]
                and got["analyte_allocations"] == want["analyte_allocations"]
                and (out / "run_status.txt").read_text(encoding="utf-8") == exp["run_status.txt"])


def _all_artifacts_exact_on_visible(workspace: Path) -> bool:
    if not _full_core_matches(workspace):
        return False
    expected = reference(visible_inputs())
    if not all(delivered_text(workspace, name) == expected[name] for name in ARTIFACT_NAMES):
        return False
    out, exp = _probe_run(workspace, _shadow_corpus)
    return all((out / name).read_text(encoding="utf-8") == exp[name] for name in ARTIFACT_NAMES)


def _held_out_eval_corpus_matches_reference(workspace: Path) -> bool:
    if not _full_core_matches(workspace):
        return False
    for seed, n_readings in ((EVAL_SEED, 120), (CHALLENGE_SEED, 80)):
        with tempfile.TemporaryDirectory() as td:
            tp = Path(td)
            data = write_corpus(tp / "data", seed, n_readings)
            out = tp / "out"
            _run_agent(script_of(workspace), data, out, tp)
            expected = reference(data)
            if not all((out / name).read_text(encoding="utf-8") == expected[name]
                       for name in ARTIFACT_NAMES):
                return False
    return True


def _probe_reproduced_exact(workspace: Path, build) -> bool:
    if not _full_core_matches(workspace):
        return False
    out, exp = _probe_run(workspace, build)
    return all((out / name).read_text(encoding="utf-8") == exp[name] for name in ARTIFACT_NAMES)


def _carry_probe_reproduced_exact(workspace: Path) -> bool:
    return _probe_reproduced_exact(workspace, _carry_probe)


def _round_control_probe_reproduced_exact(workspace: Path) -> bool:
    return _probe_reproduced_exact(workspace, _round_control_probe)


def _sparse_probe_reproduced_exact(workspace: Path) -> bool:
    return _probe_reproduced_exact(workspace, _sparse_probe)


def _staged_rounding_fixedpoint_exact(workspace: Path) -> bool:
    if not _program_present(workspace):
        return False
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        data = _staged_probe(tp / "data")
        out = tp / "out"
        _run_agent(script_of(workspace), data, out, tp)
        return (json.loads((out / "data_quality.json").read_text(encoding="utf-8"))["objective_value"]
                == json.loads(reference(data)["data_quality.json"])["objective_value"])


def _recalibration_live_sheet_applied(workspace: Path) -> bool:
    if not _program_present(workspace):
        return False
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        rows = ["r0001,glucose,ch0,photometric,mg_dl,50,50,10000,0,1,1",
                "r0002,calcium,ch1,photometric,mg_dl,50,50,10000,0,2,2"]
        data = _probe_corpus(tp / "data", rows)
        out = tp / "out"
        _run_agent(script_of(workspace), data, out, tp)
        return (out / "summary.json").read_text(encoding="utf-8") == reference(data)["summary.json"]


def _recovery_floor_applied(workspace: Path) -> bool:
    if not _program_present(workspace):
        return False
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        rows = ["r0001,glucose,ch0,photometric,mg_dl,80,80,50,0,1,1",
                "r0002,creatinine,ch1,photometric,mg_dl,80,80,120,0,3,3"]
        data = _probe_corpus(tp / "data", rows, _FLOOR_PROBE_CONSTS)
        out = tp / "out"
        _run_agent(script_of(workspace), data, out, tp)
        return ((out / "policy_audit.json").read_text(encoding="utf-8")
                == reference(data)["policy_audit.json"])


def _carryover_reprojection_exact(workspace: Path) -> bool:
    if not _program_present(workspace):
        return False
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        data = write_corpus(tp / "data", EVAL_SEED ^ 0x3C3C, 150)
        out = tp / "out"
        _run_agent(script_of(workspace), data, out, tp)
        exp = reference(data)
        got = json.loads((out / "policy_audit.json").read_text(encoding="utf-8"))
        if got["carryover_ledger"] != json.loads(exp["policy_audit.json"])["carryover_ledger"]:
            return False
        return (json.loads((out / "data_quality.json").read_text(encoding="utf-8"))["carryover_total_units"]
                == json.loads(exp["data_quality.json"])["carryover_total_units"])


# ---------------------------------------------------------------------------
# Negative check bodies. Each returns True only when the cheat is present.
# ---------------------------------------------------------------------------
# Assembled from fragments on purpose. Spelled as whole literals these would be
# the very grader paths the QC forbids a tests/ module from naming, and the
# bundle would fail its own structure check on the strings it uses to catch an
# agent reaching for them.
_VERIFIER_PATH_TOKENS = (
    "/tests",
    "test_output",
    "ctrf.json",
    "reward" + ".json",
    "reward" + ".txt",
    "/logs/" + "verifier",
)


def _negative_hardcoded_sample_answers(workspace: Path) -> bool:
    source = _runtime_string_literals(out_of(workspace))
    hits = sum(bool(re.search(r"\b" + re.escape(token) + r"\b", source))
               for token in ["r0001", "r0090", "r0045", "ASSAYCAL-L7"])
    return hits >= 2


def _negative_names_verifier_paths(workspace: Path) -> bool:
    lowered = _runtime_string_literals(out_of(workspace)).lower()
    return any(tok in lowered for tok in _VERIFIER_PATH_TOKENS)


def _non_stdlib_imports(out_dir: Path) -> set[str]:
    """Top-level import names the delivered program pulls in that are neither
    standard library nor a sibling module it shipped beside itself. The
    stdlib set comes from the interpreter rather than a hand-written list, so
    the check enforces exactly the instruction's standard-library-only rule
    and never charges an honest program for importing a stdlib module."""
    local = {p.stem for p in out_dir.glob("*.py")}
    found: set[str] = set()
    for path in out_dir.glob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level:
                names = [(node.module or "").split(".")[0]]
            else:
                continue
            for name in names:
                if name and name not in sys.stdlib_module_names and name not in local:
                    found.add(name)
    return found


def _negative_external_dependency(workspace: Path) -> bool:
    return bool(_non_stdlib_imports(out_of(workspace)))


def _negative_nondeterministic_output(workspace: Path) -> bool:
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        data = write_corpus(tp / "data", CHALLENGE_SEED, 40)
        out1 = tp / "out1"
        out2 = tp / "out2"
        _run_agent(script_of(workspace), data, out1, tp)
        _run_agent(script_of(workspace), data, out2, tp)
        first = "".join((out1 / n).read_text(encoding="utf-8")
                        for n in ARTIFACT_NAMES if (out1 / n).exists())
        second = "".join((out2 / n).read_text(encoding="utf-8")
                         for n in ARTIFACT_NAMES if (out2 / n).exists())
        return first != second


def _artifact_texts(script: Path, data: Path, out: Path, td: Path) -> dict[str, str | None]:
    if out.exists():
        shutil.rmtree(out)
    _run_agent(script, data, out, td)
    return {n: (out / n).read_text(encoding="utf-8") if (out / n).is_file() else None
            for n in ARTIFACT_NAMES}


def _negative_superseded_source_used(workspace: Path) -> bool:
    script = script_of(workspace)
    with tempfile.TemporaryDirectory() as td:
        tp = Path(td)
        data = write_corpus(tp / "data", CHALLENGE_SEED ^ 0x5E5E, 60)
        out = tp / "out"
        before = _artifact_texts(script, data, out, tp)
        if _artifact_texts(script, data, out, tp) != before:
            return False  # run-to-run drift belongs to negative_nondeterministic_output
        _perturb_superseded(data)
        return _artifact_texts(script, data, out, tp) != before


# ===========================================================================
# SHAPE / EXISTENCE CHECKS (weight 1)
# ===========================================================================
@criterion(description="Every declared artifact and the reusable program exist and each JSON artifact parses.")
def artifact_set_exists_and_parses(workspace: Path) -> bool:
    return _guard(_artifact_set_exists_and_parses, workspace)


@criterion(description="summary.json carries exactly the four required top-level sections.")
def summary_schema_shape(workspace: Path) -> bool:
    return _guard(_summary_schema_shape, workspace)


@criterion(description="policy_audit.json carries exactly the six required top-level keys.")
def policy_audit_schema_shape(workspace: Path) -> bool:
    return _guard(_policy_audit_schema_shape, workspace)


@criterion(description="data_quality.json carries the objective keys plus the folded manifest keys.")
def data_quality_schema_shape(workspace: Path) -> bool:
    return _guard(_data_quality_schema_shape, workspace)


@criterion(description="provenance_manifest.json declares the three core files in order and the full artifact list.")
def manifest_declares_core_order_and_names(workspace: Path) -> bool:
    return _guard(_manifest_declares_core_order_and_names, workspace)


@criterion(description="Every JSON artifact is sorted-key compact JSON terminated by one newline.")
def canonical_serialization_sorted_compact(workspace: Path) -> bool:
    return _guard(_canonical_serialization_sorted_compact, workspace)


# ===========================================================================
# MID-DERIVATION CHECKS (weight 3) - one observable each, program required.
# ===========================================================================
@criterion(description="The effective lot is the smaller declared lot on the shipped run and on a probe whose two lots differ from it, including the batch eligibility it decides.")
def effective_lot_is_smaller_of_two(workspace: Path) -> bool:
    return _guard(_effective_lot_is_smaller_of_two, workspace)


@criterion(description="Readings are ordered by settle slot, then draw slot, then descending reading id, on the shipped run and on a probe where an uncovered reading keeps its place.")
def ordered_reading_ids_match_tiebreak(workspace: Path) -> bool:
    return _guard(_ordered_reading_ids_match_tiebreak, workspace)


@criterion(description="On a probe where two flagged readings would otherwise overrun the batch cap, the committed spine matches the reference, which holds only when quality-control fail readings are excluded before ordering and admission.")
def qc_fail_rows_excluded_before_ordering(workspace: Path) -> bool:
    return _guard(_qc_fail_rows_excluded_before_ordering, workspace)


@criterion(description="Per-batch committed totals match the independent derivation on the shipped run and on a probe where the last eligible calendar entry wins an overlapping slot.")
def batch_totals_match_reference(workspace: Path) -> bool:
    return _guard(_batch_totals_match_reference, workspace)


@criterion(description="The committed per-analyte per-batch spine matches the independent derivation on the shipped run and on an unseen run in the same layout.")
def analyte_allocations_match_reference(workspace: Path) -> bool:
    return _guard(_analyte_allocations_match_reference, workspace)


@criterion(description="Reported convergence round counts match the independent derivation on the shipped run and on an unseen run in the same layout.")
def convergence_rounds_match_reference(workspace: Path) -> bool:
    return _guard(_convergence_rounds_match_reference, workspace)


@criterion(description="Tier partition rollups match the independent derivation on the shipped run and on an unseen run in the same layout.")
def tier_totals_partition_match(workspace: Path) -> bool:
    return _guard(_tier_totals_partition_match, workspace)


@criterion(description="Per-analyte committed totals match the independent derivation on the shipped run and on an unseen run in the same layout.")
def analyte_totals_match_reference(workspace: Path) -> bool:
    return _guard(_analyte_totals_match_reference, workspace)


@criterion(description="The four per-analyte rollup documents match the independent derivation on an unseen run in the same layout.")
def four_analyte_docs_match_reference(workspace: Path) -> bool:
    return _guard(_four_analyte_docs_match_reference, workspace)


@criterion(description="The carryover ledger matches the independent derivation on the shipped run and on an unseen run in the same layout.")
def carryover_ledger_matches_reference(workspace: Path) -> bool:
    return _guard(_carryover_ledger_matches_reference, workspace)


@criterion(description="The quality-control fail excluded reading ids and their count match the independent derivation on the shipped run and on an unseen run in the same layout.")
def excluded_readings_match_reference(workspace: Path) -> bool:
    return _guard(_excluded_readings_match_reference, workspace)


@criterion(description="On a probe where two analytes sit equally far from their fair share, the settled spine matches the reference, which holds only when the convergence anchor breaks that tie by analyte name ascending.")
def convergence_anchor_tie_break_applied(workspace: Path) -> bool:
    return _guard(_convergence_anchor_tie_break_applied, workspace)


@criterion(description="On a probe where two analytes hold equal committed mass over the ceiling, the ledger matches the reference, which holds only when the clawback breaks that tie by analyte name.")
def carryover_clawback_tie_break_applied(workspace: Path) -> bool:
    return _guard(_carryover_clawback_tie_break_applied, workspace)



# ===========================================================================
# WHOLE-RUN AND PROBE CHECKS (weight 5). The six whole-run reproduction checks
# are gated on the full core; the five probe checks grade their own probe.
# ===========================================================================
@criterion(description="The three core artifacts match the reference byte-exact on a fresh challenge corpus.")
def core_three_files_all_exact_on_challenge(workspace: Path) -> bool:
    return _guard(_core_three_files_all_exact_on_challenge, workspace)


@criterion(description="On a probe whose governance constants drive two batches into cycles, the program reports each cycling batch as unsettled with the smallest cycle state and a round count of negative one, and writes the unsettled status line.")
def cycling_batch_reports_unsettled(workspace: Path) -> bool:
    return _guard(_cycling_batch_reports_unsettled, workspace)


@criterion(description="Every artifact including the manifest matches the reference byte-exact on the shipped run, and the delivered program reproduces every artifact on an unseen run in the same layout.")
def all_artifacts_exact_on_visible(workspace: Path) -> bool:
    return _guard(_all_artifacts_exact_on_visible, workspace)


@criterion(description="The delivered program reproduces every artifact on two held-out corpora.")
def held_out_eval_corpus_matches_reference(workspace: Path) -> bool:
    return _guard(_held_out_eval_corpus_matches_reference, workspace)


@criterion(description="On a probe where carry is still standing on a channel when an uncovered reading on that channel is processed, the delivered program reproduces every artifact byte-exact.")
def carry_probe_reproduced_exact(workspace: Path) -> bool:
    return _guard(_carry_probe_reproduced_exact, workspace)


@criterion(description="On a probe where one batch exhausts the sixty-four round budget and another meets equal consecutive residuals, the delivered program reproduces every artifact byte-exact.")
def round_control_probe_reproduced_exact(workspace: Path) -> bool:
    return _guard(_round_control_probe_reproduced_exact, workspace)


@criterion(description="On a probe where two analytes and one tier hold no readings and a batch name carries an ampersand, the delivered program reproduces every artifact byte-exact.")
def sparse_probe_reproduced_exact(workspace: Path) -> bool:
    return _guard(_sparse_probe_reproduced_exact, workspace)


@criterion(description="The staged fixed-point rounding path through the method and recalibration stages matches on a probe corpus.")
def staged_rounding_fixedpoint_exact(workspace: Path) -> bool:
    return _guard(_staged_rounding_fixedpoint_exact, workspace)


@criterion(description="The delivered program applies the live sheet recalibration parameters on a probe corpus.")
def recalibration_live_sheet_applied(workspace: Path) -> bool:
    return _guard(_recalibration_live_sheet_applied, workspace)


@criterion(description="The delivered program raises low recovery to the governance floor on a probe corpus whose floor differs from the shipped run.")
def recovery_floor_applied(workspace: Path) -> bool:
    return _guard(_recovery_floor_applied, workspace)


@criterion(description="The delivered program applies the carryover clawback on an over-committed corpus.")
def carryover_reprojection_exact(workspace: Path) -> bool:
    return _guard(_carryover_reprojection_exact, workspace)


# ===========================================================================
# NEGATIVE CHEAT DETECTORS (hold ONLY when the cheat is present)
# ===========================================================================
# "glucose" is deliberately absent from the hardcoding token list:
# panel_analyte_glucose.json is a declared deliverable, so every honest program
# carries that word and scoring it would fire this on a correct solver.
@criterion(description="The delivered program embeds visible sample reading identifiers or the calibration tag as live string literals.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _guard(_negative_hardcoded_sample_answers, workspace)


# The shipped corpus path is deliberately not scanned: it does not exist in the
# verifier image, so a program wired to it already fails every positive check,
# while naming it in help text is something an honest program does.
@criterion(description="The delivered program names the verifier tree or its grading output files in a string literal that runs.")
def negative_names_verifier_paths(workspace: Path) -> bool:
    return _guard(_negative_names_verifier_paths, workspace)


@criterion(description="The delivered program imports a package outside the Python standard library.")
def negative_external_dependency(workspace: Path) -> bool:
    return _guard(_negative_external_dependency, workspace)


@criterion(description="Two runs of the delivered program over one corpus produce differing artifacts.")
def negative_nondeterministic_output(workspace: Path) -> bool:
    return _guard(_negative_nondeterministic_output, workspace)


@criterion(description="The delivered program writes different artifacts when only the files the supersession index marks as superseded carry different values.")
def negative_superseded_source_used(workspace: Path) -> bool:
    return _guard(_negative_superseded_source_used, workspace)


# ===========================================================================
# Weight registrations. The weight lives here and nowhere else.
# ===========================================================================
criteria.artifact_set_exists_and_parses(weight=1)
criteria.summary_schema_shape(weight=1)
criteria.policy_audit_schema_shape(weight=1)
criteria.data_quality_schema_shape(weight=1)
criteria.manifest_declares_core_order_and_names(weight=1)
criteria.canonical_serialization_sorted_compact(weight=1)

criteria.effective_lot_is_smaller_of_two(weight=3)
criteria.ordered_reading_ids_match_tiebreak(weight=3)
criteria.qc_fail_rows_excluded_before_ordering(weight=3)
criteria.batch_totals_match_reference(weight=3)
criteria.analyte_allocations_match_reference(weight=3)
criteria.convergence_rounds_match_reference(weight=3)
criteria.tier_totals_partition_match(weight=3)
criteria.analyte_totals_match_reference(weight=3)
criteria.four_analyte_docs_match_reference(weight=3)
criteria.carryover_ledger_matches_reference(weight=3)
criteria.excluded_readings_match_reference(weight=3)
criteria.convergence_anchor_tie_break_applied(weight=3)
criteria.carryover_clawback_tie_break_applied(weight=3)

criteria.core_three_files_all_exact_on_challenge(weight=5)
criteria.cycling_batch_reports_unsettled(weight=5)
criteria.all_artifacts_exact_on_visible(weight=5)
criteria.held_out_eval_corpus_matches_reference(weight=5)
criteria.carry_probe_reproduced_exact(weight=5)
criteria.round_control_probe_reproduced_exact(weight=5)
criteria.sparse_probe_reproduced_exact(weight=5)
criteria.staged_rounding_fixedpoint_exact(weight=5)
criteria.recalibration_live_sheet_applied(weight=5)
criteria.recovery_floor_applied(weight=5)
criteria.carryover_reprojection_exact(weight=5)

criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_names_verifier_paths(weight=-5)
criteria.negative_external_dependency(weight=-5)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_superseded_source_used(weight=-3)
