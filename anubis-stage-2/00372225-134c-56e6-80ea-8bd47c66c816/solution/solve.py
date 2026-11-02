#!/usr/bin/env python3
"""Reference solver for 00372225-134c-56e6-80ea-8bd47c66c816.

Standard-library only. Usage:

    python3 derive_report.py DATA_DIR OUT_DIR

Reads one clinical-assay QC recalibration run laid out in the shipped schema and
writes the reconciled report. Every rule below is taken from the pipeline
contract, the per-stage notes, precision_and_rounding.md and
output_artifact_contract.md shipped in the data directory.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path

GOVERNANCE_KEYS = ("RECOVERY_FLOOR_BP", "FLOOR_RESULT", "DAMPING_SEED", "BATCH_CAP",
                   "CARRYOVER_CEILING")
READING_FIELDS = ("reading_id", "analyte", "channel", "method", "spec_unit", "raw_signal",
                  "basis_signal", "recovery_bp", "is_qc_fail", "draw_slot", "settle_slot")
CORE_FILES = ["summary.json", "policy_audit.json", "panel_analyte_glucose.json"]
PANEL = ("glucose", "calcium", "lactate", "creatinine")
SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


class InputError(Exception):
    """A required input is missing or does not carry what the contract requires."""


# --------------------------------------------------------------------------
# Q16.16 fixed point, as precision_and_rounding.md defines it.
# --------------------------------------------------------------------------
SHIFT = 16
SCALE = 1 << SHIFT


def div_half_away(numerator: int, denominator: int) -> int:
    """numerator / denominator rounded half up away from zero (denominator > 0)."""
    magnitude, remainder = divmod(abs(numerator), denominator)
    if 2 * remainder >= denominator:
        magnitude += 1
    return -magnitude if numerator < 0 else magnitude


def fx_whole(n: int) -> int:
    return n * SCALE


def fx_bp(bp: int) -> int:
    return div_half_away(bp * SCALE, 10000)


def fx_milli(milli: int) -> int:
    return div_half_away(milli * SCALE, 1000)


def fx_mul(a: int, b: int) -> int:
    product = a * b
    magnitude = abs(product) >> SHIFT
    return -magnitude if product < 0 else magnitude


def fx_sqrt(x: int) -> int:
    return math.isqrt(x * SCALE) if x > 0 else 0


def fx_round(x: int) -> int:
    return div_half_away(x, SCALE) * SCALE


def fx_truncate(x: int) -> int:
    magnitude = abs(x) >> SHIFT
    return -magnitude if x < 0 else magnitude


# --------------------------------------------------------------------------
# Input readers.
# --------------------------------------------------------------------------
def require_file(path: Path) -> Path:
    if not path.is_file():
        raise InputError(f"required input is missing: {path}")
    return path


def read_table(path: Path, fields: tuple[str, ...]) -> list[dict[str, str]]:
    with require_file(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        absent = [f for f in fields if f not in (reader.fieldnames or [])]
        if absent:
            raise InputError(f"{path.name} lacks the columns {', '.join(absent)}")
        return list(reader)


def read_json(path: Path):
    try:
        return json.loads(require_file(path).read_text(encoding="utf-8"))
    except ValueError as err:
        raise InputError(f"{path.name} is not valid JSON: {err}") from err


def column_index(ref: str) -> int:
    letters = "".join(ch for ch in ref if ch.isalpha())
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return index - 1


def read_workbook_sheets(path: Path) -> list[list[list[str]]]:
    """Every worksheet of the workbook as a dense grid of cell strings."""
    with zipfile.ZipFile(require_file(path)) as book:
        names = set(book.namelist())
        strings: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            for item in root.iter(SHEET_NS + "si"):
                strings.append("".join(t.text or "" for t in item.iter(SHEET_NS + "t")))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        target_of = {rel.get("Id"): rel.get("Target") for rel in rels.iter(PKG_REL_NS + "Relationship")}
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        grids = []
        for sheet in workbook.iter(SHEET_NS + "sheet"):
            target = target_of[sheet.get(REL_NS + "id")].lstrip("/")
            member = target if target.startswith("xl/") else "xl/" + target
            cells: dict[tuple[int, int], str] = {}
            for cell in ET.fromstring(book.read(member)).iter(SHEET_NS + "c"):
                ref = cell.get("r")
                row = int("".join(ch for ch in ref if ch.isdigit()))
                value_node = cell.find(SHEET_NS + "v")
                value = value_node.text if value_node is not None and value_node.text else ""
                if cell.get("t") == "s" and value:
                    value = strings[int(value)]
                cells[(row, column_index(ref))] = value
            if not cells:
                grids.append([])
                continue
            height = max(r for r, _ in cells)
            width = max(c for _, c in cells) + 1
            grids.append([[cells.get((r, c), "") for c in range(width)] for r in range(1, height + 1)])
    return grids


def read_live_sheet(path: Path, tag: str):
    """Method and recalibration coefficients from the sheet whose first-row tag matches."""
    for grid in read_workbook_sheets(path):
        if len(grid) < 2 or len(grid[0]) < 2 or grid[0][1] != tag:
            continue
        header = {name: idx for idx, name in enumerate(grid[1])}
        methods: dict[str, tuple[int, int]] = {}
        recal: dict[str, tuple[int, int]] = {}
        for row in grid[2:]:
            kind = row[header["row_kind"]]
            key = row[header["key"]]
            if kind == "method":
                methods[key] = (int(row[header["exponent_milli"]]), int(row[header["gain_bp"]]))
            elif kind == "recal":
                recal[key] = (int(row[header["a_milli"]]), int(row[header["b_milli"]]))
        return methods, recal
    raise InputError(f"{path.name} has no sheet tagged {tag}")


def read_governance(path: Path) -> dict[str, int]:
    """The five constants shown as text in the envelope's content streams."""
    data = require_file(path).read_bytes()
    text = []
    for header in re.finditer(rb"<<([^<>]*)>>\s*stream\r?\n", data):
        fields = header.group(1)
        length = re.search(rb"/Length (\d+)", fields)
        if length is None:
            raise InputError(f"{path.name} has a content stream with no /Length")
        payload = data[header.end():header.end() + int(length.group(1))]
        if b"/FlateDecode" in fields:
            try:
                payload = zlib.decompress(payload)
            except zlib.error as err:
                raise InputError(f"{path.name} has a content stream that does not inflate: {err}") from err
        text.append(payload.decode("latin-1"))
    found: dict[str, int] = {}
    for name, value in re.findall(r"\((\w+) (-?\d+)\) Tj", "\n".join(text)):
        if name in GOVERNANCE_KEYS:
            found[name] = int(value)
    missing = [k for k in GOVERNANCE_KEYS if k not in found]
    if missing:
        raise InputError(f"{path.name} does not carry {', '.join(missing)}")
    return found


def load_run(data_dir: Path) -> dict:
    profile = read_json(data_dir / "run_profile.json")
    for key in ("calibration_tag", "lot_a", "lot_b"):
        if key not in profile:
            raise InputError(f"run_profile.json lacks {key}")
    methods, recal = read_live_sheet(data_dir / "recalibration_grid.xlsx", profile["calibration_tag"])
    weights = read_json(data_dir / "tier_weight_book.json")
    if not isinstance(weights, dict) or not weights:
        raise InputError("tier_weight_book.json must map each tier to an integer weight")
    return {
        "profile": profile,
        "methods": methods,
        "recal": recal,
        "governance": read_governance(data_dir / "governance_envelope.pdf"),
        "readings": read_table(data_dir / "assay_capture_run.csv", READING_FIELDS),
        "crosswalk": read_table(data_dir / "analyte_crosswalk.csv", ("analyte", "matrix")),
        "topology": {row["analyte"]: row for row in read_table(
            data_dir / "panel_topology.csv", ("analyte", "matrix_class", "tier", "matrix_shift_units"))},
        "unit_scale": {row["spec_unit"]: int(row["scale_bp"]) for row in read_table(
            data_dir / "unit_scale_book.csv", ("spec_unit", "scale_bp"))},
        "calendar": read_table(data_dir / "batch_calendar.csv", ("batch", "from_slot", "to_slot", "min_lot")),
        "tier_weight": {str(k): int(v) for k, v in weights.items()},
    }


# --------------------------------------------------------------------------
# Stages, in the order the pipeline contract fixes.
# --------------------------------------------------------------------------
def flagged(reading: dict[str, str]) -> bool:
    return reading["is_qc_fail"].strip() not in ("", "0", "false", "False")


def order_live_readings(readings):
    """Exclude flagged readings, then settle asc, draw asc, reading id desc."""
    live = [r for r in readings if not flagged(r)]
    live.sort(key=lambda r: r["reading_id"], reverse=True)
    live.sort(key=lambda r: (int(r["settle_slot"]), int(r["draw_slot"])))
    return live


def place_in_batch(slot: int, calendar, effective_lot: int):
    """The last eligible calendar entry whose half-open window covers the slot."""
    for entry in reversed(calendar):
        if int(entry["min_lot"]) <= effective_lot and int(entry["from_slot"]) <= slot < int(entry["to_slot"]):
            return entry["batch"]
    return None


def method_transform(basis: int, exponent_milli: int, gain_bp: int) -> int:
    if exponent_milli == 1000:
        powered = basis
    elif exponent_milli == 1500:
        powered = fx_mul(basis, fx_sqrt(basis))
    elif exponent_milli == 2000:
        powered = fx_mul(basis, basis)
    else:
        raise InputError(f"unsupported exponent_milli {exponent_milli}")
    return fx_round(fx_mul(powered, fx_bp(gain_bp)))


def recalibrate(value: int, a_milli: int, b_milli: int) -> int:
    return fx_round(fx_mul(value, fx_milli(a_milli)) + fx_milli(b_milli))


def reweight(value: int, recovery_bp: int, floor_bp: int) -> int:
    return fx_round(fx_mul(value, fx_bp(max(recovery_bp, floor_bp))))


def fair_share(masses: dict[str, int], cap: int) -> dict[str, int]:
    names = sorted(masses)
    mass = sum(masses.values())
    if mass <= 0:
        return {name: 0 for name in names}
    target = mass if mass <= cap else cap
    share = {}
    remainders = []
    for name in names:
        quotient, remainder = divmod(masses[name] * target, mass)
        share[name] = quotient
        remainders.append((-remainder, name))
    for _, name in sorted(remainders)[: target - sum(share.values())]:
        share[name] += 1
    return share


def converge(masses: dict[str, int], damping_seed: int, cap: int):
    """Damped rebalance of one batch: (settled masses, round count or -1)."""
    names = sorted(masses)
    fair = fair_share(masses, cap)
    state = dict(masses)
    damping = damping_seed
    previous = None
    stalls = 0
    first_seen: dict[tuple[int, ...], int] = {}
    states: list[tuple[int, ...]] = []
    for round_index in range(64):
        snapshot = tuple(state[n] for n in names)
        if snapshot in first_seen:
            smallest = min(states[first_seen[snapshot]:])
            return dict(zip(names, smallest)), -1
        first_seen[snapshot] = round_index
        states.append(snapshot)
        residual = sum(abs(state[n] - fair[n]) for n in names)
        if residual == 0:
            return state, round_index
        if previous is not None and residual >= previous:
            stalls += 1
            if stalls == 2:
                damping //= 2
                stalls = 0
        previous = residual
        flow = {n: div_half_away((fair[n] - state[n]) * damping, 10000) for n in names}
        drift = sum(flow.values())
        if drift:
            furthest = sorted(names, key=lambda n: (-abs(fair[n] - state[n]), n))[0]
            flow[furthest] -= drift
        if all(v == 0 for v in flow.values()):
            return state, round_index
        for n in names:
            state[n] += flow[n]
    return state, 64


def claw_back(settled: dict[str, dict[str, int]], ceiling: int):
    final = {batch: dict(masses) for batch, masses in settled.items()}
    ledger = []
    for batch in sorted(final):
        masses = final[batch]
        excess = sum(masses.values()) - ceiling
        for name in sorted(masses, key=lambda n: (-masses[n], n)):
            if excess <= 0:
                break
            taken = min(masses[name], excess)
            masses[name] -= taken
            excess -= taken
            ledger.append({"analyte": name, "batch": batch, "clawed_units": taken})
    ledger.sort(key=lambda e: (e["batch"], e["analyte"]))
    return final, ledger


def reconcile(run: dict) -> dict:
    gov = run["governance"]
    effective_lot = min(int(run["profile"]["lot_a"]), int(run["profile"]["lot_b"]))
    ordered = order_live_readings(run["readings"])
    committed: dict[tuple[str, str], int] = {}
    carry: dict[str, int] = {}
    admitted: dict[str, int] = {}
    channel_first_seat: dict[str, tuple[str, str]] = {}
    for reading in ordered:
        batch = place_in_batch(int(reading["settle_slot"]), run["calendar"], effective_lot)
        if batch is None:
            continue
        analyte, channel = reading["analyte"], reading["channel"]
        unit = run["unit_scale"][reading["spec_unit"]]
        raw = fx_mul(fx_whole(int(reading["raw_signal"])), fx_bp(unit))
        basis = fx_mul(fx_whole(int(reading["basis_signal"])), fx_bp(unit))
        transformed = method_transform(basis, *run["methods"][reading["method"]])
        calibrated = recalibrate(raw + transformed, *run["recal"][analyte])
        weighted = reweight(calibrated, int(reading["recovery_bp"]), gov["RECOVERY_FLOOR_BP"])
        wanted = fx_truncate(weighted) + carry.pop(channel, 0)
        room = max(0, gov["BATCH_CAP"] - admitted.get(batch, 0))
        granted = min(wanted, room)
        if wanted > granted:
            carry[channel] = wanted - granted
        admitted[batch] = admitted.get(batch, 0) + granted
        seated = max(0, max(granted, gov["FLOOR_RESULT"]) + int(run["topology"][analyte]["matrix_shift_units"]))
        committed[(analyte, batch)] = committed.get((analyte, batch), 0) + seated
        channel_first_seat.setdefault(channel, (analyte, batch))
    for channel in sorted(carry):
        if carry[channel] > 0 and channel in channel_first_seat:
            seat = channel_first_seat[channel]
            committed[seat] += carry[channel]

    per_batch: dict[str, dict[str, int]] = {}
    for (analyte, batch), units in committed.items():
        per_batch.setdefault(batch, {})[analyte] = units
    settled, rounds = {}, {}
    for batch in sorted(per_batch):
        settled[batch], rounds[batch] = converge(per_batch[batch], gov["DAMPING_SEED"], gov["BATCH_CAP"])
    final, ledger = claw_back(settled, gov["CARRYOVER_CEILING"])
    return {
        "effective_lot": effective_lot,
        "ordered_ids": [r["reading_id"] for r in ordered],
        "excluded_ids": sorted(r["reading_id"] for r in run["readings"] if flagged(r)),
        "final": final,
        "rounds": rounds,
        "ledger": ledger,
    }


# --------------------------------------------------------------------------
# Artifacts, in the shapes output_artifact_contract.md fixes.
# --------------------------------------------------------------------------
def compact(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"


def xml_escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def lines(rows) -> str:
    return "".join(row + "\n" for row in rows)


def build_artifacts(run: dict, result: dict) -> dict[str, str]:
    topology, weights = run["topology"], run["tier_weight"]
    final, rounds, ledger = result["final"], result["rounds"], result["ledger"]
    batches = sorted(final)
    totals: dict[str, int] = {}
    for masses in final.values():
        for analyte, units in masses.items():
            totals[analyte] = totals.get(analyte, 0) + units
    by_matrix: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    for analyte, units in totals.items():
        by_matrix[topology[analyte]["matrix_class"]] = by_matrix.get(topology[analyte]["matrix_class"], 0) + units
        by_tier[topology[analyte]["tier"]] = by_tier.get(topology[analyte]["tier"], 0) + units
    objective = sum(by_tier.get(tier, 0) * weight for tier, weight in weights.items())
    grand_total = sum(totals.values())
    clawed = sum(e["clawed_units"] for e in ledger)
    excluded = result["excluded_ids"]
    crosswalk = {row["analyte"] for row in run["crosswalk"]}
    members = sorted(a for a in totals if a in crosswalk)
    unsettled = [b for b in batches if rounds[b] == -1]

    summary = {
        "batch_totals": {b: sum(final[b].values()) for b in batches},
        "analyte_allocations": {b: final[b] for b in batches},
        "convergence_rounds": {b: rounds[b] for b in batches},
        "unsettled_batches": unsettled,
    }
    audit = {
        "tier_totals": by_tier,
        "carryover_ledger": ledger,
        "excluded_reading_ids": excluded,
        "excluded_count": len(excluded),
        "effective_lot": result["effective_lot"],
        "ordered_reading_ids": result["ordered_ids"],
    }

    def panel_doc(analyte: str) -> dict:
        row = topology.get(analyte, {})
        return {"analyte": analyte, "matrix": row.get("matrix_class", ""), "tier": row.get("tier", ""),
                "committed_total": totals.get(analyte, 0),
                "per_batch": {b: final[b][analyte] for b in batches if analyte in final[b]}}

    out = {"summary.json": compact(summary), "policy_audit.json": compact(audit)}
    for analyte in PANEL:
        out[f"panel_analyte_{analyte}.json"] = compact(panel_doc(analyte))
    digest = hashlib.sha256("".join(out[name] for name in CORE_FILES).encode("utf-8")).hexdigest()
    out["data_quality.json"] = compact({
        "objective_value": objective, "tier_totals": by_tier, "committed_grand_total": grand_total,
        "carryover_total_units": clawed, "core_files": CORE_FILES, "core_sha256": digest})
    out["matrix_rollup.json"] = compact({
        "axis": "matrix", "class_totals": by_matrix,
        "analyte_membership": {a: topology[a]["matrix_class"] for a in members}})
    out["tier_rollup.json"] = compact({
        "axis": "tier", "class_totals": by_tier, "weighted_objective": objective,
        "analyte_membership": {a: topology[a]["tier"] for a in members}})
    out["analyte_totals.json"] = compact(totals)
    out["tier_analyte_membership.json"] = compact({a: topology[a]["tier"] for a in members})
    out["ordered_reading_index.json"] = compact(result["ordered_ids"])
    out["excluded_readings.json"] = compact(excluded)
    out["analyte_committed.csv"] = lines(
        ["analyte,matrix,tier,committed_total"]
        + [f"{a},{topology.get(a, {}).get('matrix_class', '')},{topology.get(a, {}).get('tier', '')},{totals.get(a, 0)}"
           for a in sorted(crosswalk)])
    out["batch_committed.tsv"] = lines(
        ["batch\tcommitted_total\tconvergence_rounds"]
        + [f"{b}\t{sum(final[b].values())}\t{rounds[b]}" for b in batches])
    out["matrix_weighted.psv"] = lines(
        ["tier|committed_total|tier_weight|weighted_contribution"]
        + [f"{t}|{by_tier.get(t, 0)}|{weights[t]}|{by_tier.get(t, 0) * weights[t]}" for t in sorted(weights)])
    out["carryover_ledger.xml"] = lines(
        ['<?xml version="1.0" encoding="UTF-8"?>', "<carryover_ledger>"]
        + [f'  <entry batch="{xml_escape(e["batch"])}" analyte="{xml_escape(e["analyte"])}" '
           f'clawed_units="{e["clawed_units"]}"/>' for e in ledger]
        + [f'  <total clawed_units="{clawed}"/>', "</carryover_ledger>"])
    out["objective_summary.yaml"] = lines(
        [f"objective_value: {objective}", f"committed_grand_total: {grand_total}",
         f"excluded_count: {len(excluded)}", f"carryover_total_units: {clawed}",
         f"effective_lot: {result['effective_lot']}", f"core_sha256: {digest}", "tier_totals:"]
        + [f"  {t}: {by_tier[t]}" for t in sorted(by_tier)])
    out["reconciliation_report.md"] = lines(
        ["# Assay QC Reconciliation Report", "", f"objective_value {objective}",
         f"committed_grand_total {grand_total}", f"effective_lot {result['effective_lot']}",
         f"excluded_count {len(excluded)}", "", "## Batch totals", ""]
        + [f"- {b} {sum(final[b].values())}" for b in batches])
    out["run_status.txt"] = lines(
        [f"status {'UNSETTLED' if unsettled else 'SETTLED'}", f"objective_value {objective}",
         f"core_sha256 {digest}", f"unsettled_batches {','.join(unsettled) if unsettled else 'none'}"])
    out["provenance_manifest.json"] = compact({
        "artifact_names": sorted([*out, "provenance_manifest.json"]), "core_files": CORE_FILES,
        "core_sha256": digest, "reusable_program": "/app/out/derive_report.py"})
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    try:
        run = load_run(Path(argv[1]))
    except InputError as err:
        sys.stderr.write(f"derive_report.py: {err}\n")
        return 1
    artifacts = build_artifacts(run, reconcile(run))
    out_dir = Path(argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, text in artifacts.items():
        (out_dir / name).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
