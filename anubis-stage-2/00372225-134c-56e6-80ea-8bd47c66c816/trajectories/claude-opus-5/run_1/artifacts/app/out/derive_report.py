#!/usr/bin/env python3
"""Derive the reconciled clinical-assay QC recalibration report for a run.

Usage: python3 derive_report.py DATA_DIR OUT_DIR
"""
import csv
import hashlib
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
import zlib

FP_SHIFT = 16
ONE = 1 << FP_SHIFT
HALF = ONE // 2

CORE_FILES = ["summary.json", "policy_audit.json", "panel_analyte_glucose.json"]
REUSABLE_PROGRAM = "/app/out/derive_report.py"
MAX_ROUNDS = 64


# --------------------------------------------------------------------------
# Q16.16 fixed point
# --------------------------------------------------------------------------
def div_half_up(num, den):
    """Divide, rounding halves away from zero. den > 0."""
    if num >= 0:
        return (2 * num + den) // (2 * den)
    return -((-2 * num + den) // (2 * den))


def fp_from_int(n):
    return n * ONE


def fp_from_bp(bp):
    return div_half_up(bp * ONE, 10000)


def fp_from_milli(m):
    return div_half_up(m * ONE, 1000)


def fp_mul(a, b):
    p = a * b
    if p < 0:
        return -((-p) >> FP_SHIFT)
    return p >> FP_SHIFT


def fp_sqrt(v):
    if v <= 0:
        return 0
    return math.isqrt(v * ONE)


def fp_round_whole(v):
    """Round to a whole fixed-point value, halves away from zero."""
    if v >= 0:
        return ((v + HALF) // ONE) * ONE
    return -(((-v) + HALF) // ONE) * ONE


def fp_trunc(v):
    """Fixed-point value to whole result, truncating toward zero."""
    if v >= 0:
        return v // ONE
    return -((-v) // ONE)


# --------------------------------------------------------------------------
# Input readers
# --------------------------------------------------------------------------
def read_csv_rows(path, delim=","):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=delim))


def read_run_profile(data_dir):
    with open(os.path.join(data_dir, "run_profile.json"), encoding="utf-8") as fh:
        return json.load(fh)


NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
NS_PKGREL = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _col_letters(ref):
    return "".join(ch for ch in ref if ch.isalpha())


def _xlsx_sheets(path):
    """Yield (sheet_name, rows) where rows maps column letter -> value."""
    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst.findall(NS_MAIN + "si"):
                shared.append("".join(t.text or "" for t in si.iter(NS_MAIN + "t")))
        rels = {}
        rel_root = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        for rel in rel_root.findall(NS_PKGREL + "Relationship"):
            rels[rel.get("Id")] = rel.get("Target")
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        for sheet in wb.find(NS_MAIN + "sheets").findall(NS_MAIN + "sheet"):
            name = sheet.get("name")
            target = rels[sheet.get(NS_REL + "id")]
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            ws = ET.fromstring(zf.read(target))
            rows = []
            for row in ws.iter(NS_MAIN + "row"):
                cells = {}
                for cell in row.findall(NS_MAIN + "c"):
                    vnode = cell.find(NS_MAIN + "v")
                    if vnode is None or vnode.text is None:
                        continue
                    raw = vnode.text
                    if cell.get("t") == "s":
                        raw = shared[int(raw)]
                    cells[_col_letters(cell.get("r"))] = raw
                rows.append(cells)
            yield name, rows


def read_grid(data_dir, calibration_tag):
    """Read method and recal coefficients from the LIVE grid sheet."""
    path = os.path.join(data_dir, "recalibration_grid.xlsx")
    for _name, rows in _xlsx_sheets(path):
        if not rows:
            continue
        tag = None
        for col, val in rows[0].items():
            if val == calibration_tag:
                tag = val
        if tag is None:
            continue
        header = None
        methods = {}
        recal = {}
        for cells in rows[1:]:
            vals = set(cells.values())
            if header is None:
                if "row_kind" in vals and "key" in vals:
                    header = {col: v for col, v in cells.items()}
                continue
            rec = {}
            for col, v in cells.items():
                field = header.get(col)
                if field:
                    rec[field] = v
            kind = rec.get("row_kind")
            key = rec.get("key")
            if kind == "method":
                methods[key] = {
                    "exponent_milli": int(rec["exponent_milli"]),
                    "gain_bp": int(rec["gain_bp"]),
                }
            elif kind == "recal":
                recal[key] = {
                    "a_milli": int(rec["a_milli"]),
                    "b_milli": int(rec["b_milli"]),
                }
        return methods, recal
    raise ValueError("no grid sheet matches calibration tag %r" % calibration_tag)


GOV_KEYS = (
    "RECOVERY_FLOOR_BP",
    "FLOOR_RESULT",
    "DAMPING_SEED",
    "BATCH_CAP",
    "CARRYOVER_CEILING",
)


def read_governance(data_dir):
    """Read the five governance constants from the envelope PDF."""
    blob = open(os.path.join(data_dir, "governance_envelope.pdf"), "rb").read()
    text_parts = []
    for m in re.finditer(rb"stream\r?\n(.*?)endstream", blob, re.S):
        chunk = m.group(1)
        try:
            chunk = zlib.decompressobj().decompress(chunk)
        except zlib.error:
            pass
        text_parts.append(chunk.decode("latin-1"))
    text = "\n".join(text_parts)
    out = {}
    for lit in re.findall(r"\((.*?)\)\s*Tj", text, re.S):
        parts = lit.split()
        if len(parts) >= 2 and parts[0] in GOV_KEYS:
            out[parts[0]] = int(parts[1])
    missing = [k for k in GOV_KEYS if k not in out]
    if missing:
        raise ValueError("governance envelope missing %s" % missing)
    return out


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------
def build_batches(data_dir, effective_lot):
    rows = read_csv_rows(os.path.join(data_dir, "batch_calendar.csv"))
    out = []
    for r in rows:
        if int(r["min_lot"]) <= effective_lot:
            out.append((r["batch"], int(r["from_slot"]), int(r["to_slot"])))
    return out


def batch_for_slot(batches, slot):
    found = None
    for name, lo, hi in batches:
        if lo <= slot < hi:
            found = name
    return found


def transform_basis(scaled_basis, exponent_milli, gain_bp):
    if exponent_milli == 1000:
        powered = scaled_basis
    elif exponent_milli == 1500:
        powered = fp_mul(scaled_basis, fp_sqrt(scaled_basis))
    elif exponent_milli == 2000:
        powered = fp_mul(scaled_basis, scaled_basis)
    else:
        raise ValueError("unsupported exponent_milli %r" % exponent_milli)
    return fp_round_whole(fp_mul(powered, fp_from_bp(gain_bp)))


def fair_share(masses, order, cap):
    total = sum(masses[a] for a in order)
    if total == 0:
        return {a: 0 for a in order}
    target = total if total <= cap else cap
    base = {}
    rem = {}
    for a in order:
        n = masses[a] * target
        base[a] = n // total
        rem[a] = n - base[a] * total
    leftover = target - sum(base.values())
    if leftover > 0:
        ranked = sorted(order, key=lambda a: (-rem[a], a))
        for a in ranked[:leftover]:
            base[a] += 1
    return base


def settle_batch(masses_in, cap, damping_seed):
    """Damped proportional rebalance. Returns (masses, round_count)."""
    order = sorted(masses_in)
    masses = dict(masses_in)
    damping = damping_seed
    prev_residual = None
    nonimproving = 0
    seen = {}
    states = []
    rnd = 0
    while rnd < MAX_ROUNDS:
        state = tuple(masses[a] for a in order)
        if state in seen:
            cycle = states[seen[state]:]
            best = min(cycle)
            return dict(zip(order, best)), -1
        seen[state] = len(states)
        states.append(state)

        fair = fair_share(masses, order, cap)
        residual = sum(abs(masses[a] - fair[a]) for a in order)
        if residual == 0:
            return masses, rnd
        if prev_residual is not None and residual >= prev_residual:
            nonimproving += 1
            if nonimproving == 2:
                damping //= 2
                nonimproving = 0
        prev_residual = residual

        flows = {}
        for a in order:
            flows[a] = div_half_up((fair[a] - masses[a]) * damping, 10000)
        drift = sum(flows.values())
        if drift != 0:
            pick = min(order, key=lambda a: (-abs(fair[a] - masses[a]), a))
            flows[pick] -= drift
        if all(v == 0 for v in flows.values()):
            return masses, rnd
        for a in order:
            masses[a] += flows[a]
        rnd += 1
    return masses, MAX_ROUNDS


def reproject(masses, ceiling, batch):
    """Claw back excess over the ceiling, largest analyte first."""
    ledger = []
    total = sum(masses.values())
    excess = total - ceiling
    while excess > 0:
        pick = min(masses, key=lambda a: (-masses[a], a))
        avail = masses[pick]
        if avail <= 0:
            break
        take = avail if avail < excess else excess
        masses[pick] = avail - take
        excess -= take
        ledger.append({"analyte": pick, "batch": batch, "clawed_units": take})
    return ledger


def derive(data_dir):
    profile = read_run_profile(data_dir)
    effective_lot = min(int(profile["lot_a"]), int(profile["lot_b"]))
    methods, recal = read_grid(data_dir, profile["calibration_tag"])
    gov = read_governance(data_dir)

    panel = {}
    panel_order = []
    for r in read_csv_rows(os.path.join(data_dir, "panel_topology.csv")):
        panel[r["analyte"]] = {
            "matrix": r["matrix_class"],
            "tier": r["tier"],
            "shift": int(r["matrix_shift_units"]),
        }
        panel_order.append(r["analyte"])
    crosswalk = [r["analyte"] for r in
                 read_csv_rows(os.path.join(data_dir, "analyte_crosswalk.csv"))]
    scales = {r["spec_unit"]: int(r["scale_bp"]) for r in
              read_csv_rows(os.path.join(data_dir, "unit_scale_book.csv"))}
    with open(os.path.join(data_dir, "tier_weight_book.json"), encoding="utf-8") as fh:
        tier_weights = json.load(fh)

    readings = read_csv_rows(os.path.join(data_dir, "assay_capture_run.csv"))
    excluded = sorted(r["reading_id"] for r in readings if int(r["is_qc_fail"]))
    live = [r for r in readings if not int(r["is_qc_fail"])]

    # settle_slot asc, draw_slot asc, reading_id desc
    live.sort(key=lambda r: r["reading_id"], reverse=True)
    live.sort(key=lambda r: (int(r["settle_slot"]), int(r["draw_slot"])))
    ordered_ids = [r["reading_id"] for r in live]

    batches = build_batches(data_dir, effective_lot)
    cap = gov["BATCH_CAP"]

    admitted_mass = {}
    committed = {}
    members = {}
    carry = {}
    channel_first = {}

    for r in live:
        batch = batch_for_slot(batches, int(r["settle_slot"]))
        if batch is None:
            continue
        analyte = r["analyte"]
        channel = r["channel"]
        members.setdefault(batch, set()).add(analyte)
        committed.setdefault((batch, analyte), 0)
        channel_first.setdefault(channel, (batch, analyte))

        scale = fp_from_bp(scales[r["spec_unit"]])
        scaled_raw = fp_mul(fp_from_int(int(r["raw_signal"])), scale)
        scaled_basis = fp_mul(fp_from_int(int(r["basis_signal"])), scale)

        method = methods[r["method"]]
        transformed = transform_basis(
            scaled_basis, method["exponent_milli"], method["gain_bp"])

        coeff = recal[analyte]
        recal_in = scaled_raw + transformed
        value = fp_round_whole(
            fp_mul(fp_from_milli(coeff["a_milli"]), recal_in)
            + fp_from_milli(coeff["b_milli"]))

        recovery = max(int(r["recovery_bp"]), gov["RECOVERY_FLOOR_BP"])
        value = fp_round_whole(fp_mul(value, fp_from_bp(recovery)))

        whole = fp_trunc(value) + carry.get(channel, 0)
        mass = admitted_mass.get(batch, 0)
        if whole < 0:
            admit = whole
            carry[channel] = 0
        else:
            headroom = cap - mass
            if headroom < 0:
                headroom = 0
            admit = whole if whole < headroom else headroom
            carry[channel] = whole - admit
        admitted_mass[batch] = mass + admit

        seated = admit if admit > gov["FLOOR_RESULT"] else gov["FLOOR_RESULT"]
        seated += panel[analyte]["shift"]
        if seated < 0:
            seated = 0
        committed[(batch, analyte)] += seated

    for channel in sorted(carry):
        left = carry[channel]
        if left and channel in channel_first:
            committed[channel_first[channel]] += left

    convergence_rounds = {}
    ledger = []
    for batch in sorted(members):
        order = sorted(members[batch])
        masses = {a: committed[(batch, a)] for a in order}
        masses, rounds = settle_batch(masses, cap, gov["DAMPING_SEED"])
        convergence_rounds[batch] = rounds
        ledger.extend(reproject(masses, gov["CARRYOVER_CEILING"], batch))
        for a in order:
            committed[(batch, a)] = masses[a]

    ledger.sort(key=lambda e: (e["batch"], e["analyte"]))

    batch_keys = sorted(members)
    allocations = {b: {a: committed[(b, a)] for a in sorted(members[b])}
                   for b in batch_keys}
    batch_totals = {b: sum(allocations[b].values()) for b in batch_keys}

    analyte_totals = {}
    for b in batch_keys:
        for a, v in allocations[b].items():
            analyte_totals[a] = analyte_totals.get(a, 0) + v

    matrix_totals = {}
    tier_totals = {}
    for a, v in analyte_totals.items():
        matrix_totals[panel[a]["matrix"]] = matrix_totals.get(panel[a]["matrix"], 0) + v
        tier_totals[panel[a]["tier"]] = tier_totals.get(panel[a]["tier"], 0) + v

    objective = sum(tier_totals[t] * int(tier_weights[t]) for t in tier_totals)

    unsettled = sorted(b for b in batch_keys if convergence_rounds[b] == -1)

    return {
        "profile": profile,
        "effective_lot": effective_lot,
        "panel": panel,
        "panel_order": panel_order,
        "crosswalk": crosswalk,
        "tier_weights": tier_weights,
        "excluded": excluded,
        "ordered_ids": ordered_ids,
        "batch_keys": batch_keys,
        "allocations": allocations,
        "batch_totals": batch_totals,
        "analyte_totals": analyte_totals,
        "matrix_totals": matrix_totals,
        "tier_totals": tier_totals,
        "objective": objective,
        "convergence_rounds": convergence_rounds,
        "unsettled": unsettled,
        "ledger": ledger,
        "grand_total": sum(analyte_totals.values()),
        "carryover_total": sum(e["clawed_units"] for e in ledger),
    }


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
def jdump(obj):
    return (json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n").encode()


def xml_attr(value):
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def build_artifacts(res):
    arts = {}
    arts["summary.json"] = jdump({
        "batch_totals": res["batch_totals"],
        "analyte_allocations": res["allocations"],
        "convergence_rounds": res["convergence_rounds"],
        "unsettled_batches": res["unsettled"],
    })
    arts["policy_audit.json"] = jdump({
        "tier_totals": res["tier_totals"],
        "carryover_ledger": res["ledger"],
        "excluded_reading_ids": res["excluded"],
        "excluded_count": len(res["excluded"]),
        "effective_lot": res["effective_lot"],
        "ordered_reading_ids": res["ordered_ids"],
    })
    for analyte in res["crosswalk"]:
        info = res["panel"][analyte]
        per_batch = {b: res["allocations"][b][analyte] for b in res["batch_keys"]
                     if analyte in res["allocations"][b]}
        arts["panel_analyte_%s.json" % analyte] = jdump({
            "analyte": analyte,
            "matrix": info["matrix"],
            "tier": info["tier"],
            "committed_total": res["analyte_totals"].get(analyte, 0),
            "per_batch": per_batch,
        })

    core_blob = b"".join(arts[name] for name in CORE_FILES)
    digest = hashlib.sha256(core_blob).hexdigest()

    arts["data_quality.json"] = jdump({
        "objective_value": res["objective"],
        "tier_totals": res["tier_totals"],
        "committed_grand_total": res["grand_total"],
        "carryover_total_units": res["carryover_total"],
        "core_files": CORE_FILES,
        "core_sha256": digest,
    })
    arts["matrix_rollup.json"] = jdump({
        "axis": "matrix",
        "class_totals": res["matrix_totals"],
        "analyte_membership": {a: res["panel"][a]["matrix"]
                               for a in res["analyte_totals"]},
    })
    arts["tier_rollup.json"] = jdump({
        "axis": "tier",
        "class_totals": res["tier_totals"],
        "weighted_objective": res["objective"],
        "analyte_membership": {a: res["panel"][a]["tier"]
                               for a in res["analyte_totals"]},
    })
    arts["analyte_totals.json"] = jdump(res["analyte_totals"])
    arts["tier_analyte_membership.json"] = jdump(
        {a: res["panel"][a]["tier"] for a in res["analyte_totals"]})
    arts["ordered_reading_index.json"] = jdump(res["ordered_ids"])
    arts["excluded_readings.json"] = jdump(res["excluded"])

    lines = ["analyte,matrix,tier,committed_total"]
    for a in sorted(res["crosswalk"]):
        info = res["panel"][a]
        lines.append("%s,%s,%s,%d" % (a, info["matrix"], info["tier"],
                                      res["analyte_totals"].get(a, 0)))
    arts["analyte_committed.csv"] = ("\n".join(lines) + "\n").encode()

    lines = ["batch\tcommitted_total\tconvergence_rounds"]
    for b in res["batch_keys"]:
        lines.append("%s\t%d\t%d" % (b, res["batch_totals"][b],
                                     res["convergence_rounds"][b]))
    arts["batch_committed.tsv"] = ("\n".join(lines) + "\n").encode()

    lines = ["tier|committed_total|tier_weight|weighted_contribution"]
    for t in sorted(res["tier_weights"]):
        total = res["tier_totals"].get(t, 0)
        weight = int(res["tier_weights"][t])
        lines.append("%s|%d|%d|%d" % (t, total, weight, total * weight))
    arts["matrix_weighted.psv"] = ("\n".join(lines) + "\n").encode()

    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<carryover_ledger>"]
    for e in res["ledger"]:
        lines.append('  <entry batch="%s" analyte="%s" clawed_units="%s"/>' % (
            xml_attr(e["batch"]), xml_attr(e["analyte"]),
            xml_attr(e["clawed_units"])))
    lines.append('  <total clawed_units="%s"/>' % xml_attr(res["carryover_total"]))
    lines.append("</carryover_ledger>")
    arts["carryover_ledger.xml"] = ("\n".join(lines) + "\n").encode()

    lines = [
        "objective_value: %d" % res["objective"],
        "committed_grand_total: %d" % res["grand_total"],
        "excluded_count: %d" % len(res["excluded"]),
        "carryover_total_units: %d" % res["carryover_total"],
        "effective_lot: %d" % res["effective_lot"],
        "core_sha256: %s" % digest,
        "tier_totals:",
    ]
    for t in sorted(res["tier_totals"]):
        lines.append("  %s: %d" % (t, res["tier_totals"][t]))
    arts["objective_summary.yaml"] = ("\n".join(lines) + "\n").encode()

    lines = [
        "# Assay QC Reconciliation Report",
        "",
        "objective_value %d" % res["objective"],
        "committed_grand_total %d" % res["grand_total"],
        "effective_lot %d" % res["effective_lot"],
        "excluded_count %d" % len(res["excluded"]),
        "",
        "## Batch totals",
        "",
    ]
    for b in res["batch_keys"]:
        lines.append("- %s %d" % (b, res["batch_totals"][b]))
    arts["reconciliation_report.md"] = ("\n".join(lines) + "\n").encode()

    lines = [
        "status %s" % ("UNSETTLED" if res["unsettled"] else "SETTLED"),
        "objective_value %d" % res["objective"],
        "core_sha256 %s" % digest,
        "unsettled_batches %s" % (",".join(res["unsettled"])
                                  if res["unsettled"] else "none"),
    ]
    arts["run_status.txt"] = ("\n".join(lines) + "\n").encode()

    names = sorted(list(arts) + ["provenance_manifest.json"])
    arts["provenance_manifest.json"] = jdump({
        "artifact_names": names,
        "core_files": CORE_FILES,
        "core_sha256": digest,
        "reusable_program": REUSABLE_PROGRAM,
    })
    return arts, digest


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: %s DATA_DIR OUT_DIR\n" % argv[0])
        return 2
    data_dir, out_dir = argv[1], argv[2]
    res = derive(data_dir)
    arts, digest = build_artifacts(res)
    os.makedirs(out_dir, exist_ok=True)
    for name, blob in arts.items():
        with open(os.path.join(out_dir, name), "wb") as fh:
            fh.write(blob)
    print("objective_value %d" % res["objective"])
    print("core_sha256 %s" % digest)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
