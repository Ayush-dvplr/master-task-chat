#!/usr/bin/env python3
"""Cold-Storage Contaminant Panel CSP-2026.

Usage:
    python3 derive_report.py <corpus_dir> <out_dir>

Reads every ``*.csv`` under ``<corpus_dir>/transmissions/`` and writes the
panel files described in ``panel_contract.md`` / ``output_schema.json`` into
``<out_dir>``.  Python 3 standard library only.
"""

import csv
import glob
import json
import os
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, getcontext

getcontext().prec = 60

PANEL = "CSP-2026"

# ---------------------------------------------------------------- declared universe

DEPOTS = ["KES", "MAR", "OSS", "TAL"]

QUARTERS = [
    ("2026-Q1", "2026-01-01", "2026-03-31"),
    ("2026-Q2", "2026-04-01", "2026-06-30"),
    ("2026-Q3", "2026-07-01", "2026-09-30"),
]
QUARTER_CODES = [q[0] for q in QUARTERS]

ASSAYS = ["PB", "CD", "HG", "AS", "HIS"]
LIMITS = {
    "PB": Decimal("0.300"),
    "CD": Decimal("0.100"),
    "HG": Decimal("0.500"),
    "AS": Decimal("0.200"),
    "HIS": Decimal("100.000"),
}
ASSAY_INDEX = {a: i for i, a in enumerate(ASSAYS)}

# Lab priority tiers (lower number wins).  Labs outside the table rank last.
LAB_TIER = {"NRL": 1, "ACM": 2, "BLX": 2, "FSK": 3}
UNKNOWN_LAB_TIER = 99

FIELDS = [
    "transmission_id",
    "lab",
    "sample_id",
    "depot",
    "collected_on",
    "assay",
    "result",
    "reported_at",
]

THREE = Decimal("0.001")


# ---------------------------------------------------------------- helpers


def round3(value):
    """Round a Decimal half-up to three decimals."""
    return value.quantize(THREE, rounding=ROUND_HALF_UP)


def num(value):
    """Render a Decimal as a JSON number."""
    return float(value)


def quarter_of(collected_on):
    """Declared quarter containing ``collected_on``, or None."""
    for code, first, last in QUARTERS:
        if first <= collected_on <= last:
            return code
    return None


def read_transmissions(corpus_dir):
    """Every row of every csv in <corpus_dir>/transmissions, in a stable order."""
    pattern = os.path.join(corpus_dir, "transmissions", "*.csv")
    rows = []
    for path in sorted(glob.glob(pattern)):
        with open(path, "r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                row = {}
                for field in FIELDS:
                    value = raw.get(field)
                    row[field] = "" if value is None else value.strip()
                rows.append(row)
    return rows


def validate(row):
    """Rejection reason for a transmission, or None when it is valid.

    Checks run in contract order and stop at the first failure.
    """
    if row["depot"] not in DEPOTS:
        return "UNKNOWN_DEPOT"
    if row["assay"] not in ASSAYS:
        return "UNKNOWN_ASSAY"
    if quarter_of(row["collected_on"]) is None:
        return "OUT_OF_PERIOD"
    return None


def parse_result(text):
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return Decimal(0)


# ---------------------------------------------------------------- core


def build(corpus_dir):
    rows = read_transmissions(corpus_dir)
    rows_read = len(rows)

    rejected = []          # (transmission_id, reason)
    candidates = {}        # (sample_id, assay) -> list of rows

    for row in rows:
        reason = validate(row)
        if reason is not None:
            rejected.append((row["transmission_id"], reason))
            continue
        candidates.setdefault((row["sample_id"], row["assay"]), []).append(row)

    # Source rules: best tier wins, then latest reported_at.
    accepted = []
    superseded = 0
    for key in sorted(candidates):
        group = candidates[key]
        best_tier = min(LAB_TIER.get(r["lab"], UNKNOWN_LAB_TIER) for r in group)
        in_tier = [r for r in group if LAB_TIER.get(r["lab"], UNKNOWN_LAB_TIER) == best_tier]
        winner = max(in_tier, key=lambda r: (r["reported_at"], r["transmission_id"]))
        accepted.append(winner)
        superseded += len(group) - 1

    # measurements: one per accepted transmission
    measurements = []
    for row in accepted:
        measurements.append(
            {
                "sample_id": row["sample_id"],
                "depot": row["depot"],
                "quarter": quarter_of(row["collected_on"]),
                "assay": row["assay"],
                "lab": row["lab"],
                "transmission_id": row["transmission_id"],
                "result_text": row["result"],
                "result": parse_result(row["result"]),
            }
        )

    ledger = {
        "rows_read": rows_read,
        "accepted": len(accepted),
        "superseded": superseded,
        "rejected": len(rejected),
    }
    return measurements, rejected, ledger


def cell_stats(values, assay):
    """n / mean / max / exceedances for a list of Decimal results."""
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "max": None, "exceedances": 0}
    total = sum(values, Decimal(0))
    mean = round3(total / Decimal(n))
    biggest = max(values)
    limit = LIMITS[assay]
    exceedances = sum(1 for v in values if v > limit)
    return {"n": n, "mean": mean, "max": biggest, "exceedances": exceedances}


def aggregate(measurements):
    # (depot, quarter, assay) -> [results]
    cells = {}
    # (depot, quarter) -> set of sample ids
    row_samples = {}
    for m in measurements:
        cells.setdefault((m["depot"], m["quarter"], m["assay"]), []).append(m["result"])
        row_samples.setdefault((m["depot"], m["quarter"]), set()).add(m["sample_id"])

    panel_rows = []
    row_index = {}
    for depot in DEPOTS:
        for quarter in QUARTER_CODES:
            assays = {}
            breach = False
            for assay in ASSAYS:
                stats = cell_stats(cells.get((depot, quarter, assay), []), assay)
                if stats["n"] == 0:
                    assays[assay] = {
                        "status": "NO_SAMPLE",
                        "n": 0,
                        "mean": None,
                        "max": None,
                        "exceedances": 0,
                    }
                else:
                    assays[assay] = {
                        "status": "MEASURED",
                        "n": stats["n"],
                        "mean": num(stats["mean"]),
                        "max": num(stats["max"]),
                        "exceedances": stats["exceedances"],
                    }
                    if stats["exceedances"] > 0:
                        breach = True
            samples = len(row_samples.get((depot, quarter), ()))
            if samples == 0:
                status = "NO_DATA"
            elif breach:
                status = "BREACH"
            else:
                status = "COMPLIANT"
            row = {
                "depot": depot,
                "quarter": quarter,
                "samples": samples,
                "status": status,
                "assays": assays,
            }
            panel_rows.append(row)
            row_index[(depot, quarter)] = row
    return cells, row_samples, panel_rows, row_index


def build_depot_reports(cells, row_samples, row_index):
    reports = {}
    for depot in DEPOTS:
        quarters = []
        breach_quarters = 0
        all_samples = set()
        for quarter in QUARTER_CODES:
            row = row_index[(depot, quarter)]
            worst = None
            for assay in ASSAYS:
                values = cells.get((depot, quarter, assay))
                if not values:
                    continue
                ratio = round3(max(values) / LIMITS[assay])
                if worst is None or ratio > worst:
                    worst = ratio
            if row["status"] == "BREACH":
                breach_quarters += 1
            all_samples |= row_samples.get((depot, quarter), set())
            quarters.append(
                {
                    "quarter": quarter,
                    "samples": row["samples"],
                    "worst_ratio": -1 if worst is None else num(worst),
                    "status": row["status"],
                }
            )
        total_samples = len(all_samples)
        if total_samples == 0:
            status = "NO_DATA"
        elif breach_quarters > 0:
            status = "BREACH"
        else:
            status = "COMPLIANT"
        reports[depot] = {
            "depot": depot,
            "total_samples": total_samples,
            "breach_quarters": breach_quarters,
            "status": status,
            "quarters": quarters,
        }
    return reports


def build_assay_reports(measurements):
    by_assay = {a: [] for a in ASSAYS}
    by_assay_quarter = {}
    depots_seen = {}
    for m in measurements:
        by_assay[m["assay"]].append(m["result"])
        by_assay_quarter.setdefault((m["assay"], m["quarter"]), []).append(m["result"])
        depots_seen.setdefault((m["assay"], m["quarter"]), set()).add(m["depot"])

    reports = {}
    for assay in ASSAYS:
        overall = cell_stats(by_assay[assay], assay)
        if overall["n"] == 0:
            status = "NO_SAMPLE"
        elif overall["exceedances"] > 0:
            status = "EXCEEDED"
        else:
            status = "WITHIN"
        by_quarter = []
        for quarter in QUARTER_CODES:
            stats = cell_stats(by_assay_quarter.get((assay, quarter), []), assay)
            if stats["n"] == 0:
                by_quarter.append(
                    {
                        "quarter": quarter,
                        "n": 0,
                        "mean": -1,
                        "max": -1,
                        "exceedances": 0,
                        "depots_sampled": 0,
                    }
                )
            else:
                by_quarter.append(
                    {
                        "quarter": quarter,
                        "n": stats["n"],
                        "mean": num(stats["mean"]),
                        "max": num(stats["max"]),
                        "exceedances": stats["exceedances"],
                        "depots_sampled": len(depots_seen.get((assay, quarter), ())),
                    }
                )
        reports[assay] = {
            "assay": assay,
            "limit": num(LIMITS[assay]),
            "n": overall["n"],
            "mean": -1 if overall["n"] == 0 else num(overall["mean"]),
            "max": -1 if overall["n"] == 0 else num(overall["max"]),
            "exceedances": overall["exceedances"],
            "status": status,
            "by_quarter": by_quarter,
        }
    return reports


def build_quarter_lines(row_index):
    lines = []
    for quarter in QUARTER_CODES:
        depots_reporting = 0
        samples = 0
        breach_rows = 0
        no_data_rows = 0
        for depot in DEPOTS:
            row = row_index[(depot, quarter)]
            if row["samples"] > 0:
                depots_reporting += 1
                samples += row["samples"]
            if row["status"] == "BREACH":
                breach_rows += 1
            if row["status"] == "NO_DATA":
                no_data_rows += 1
        if samples == 0:
            status = "NO_DATA"
        elif breach_rows > 0:
            status = "BREACH"
        else:
            status = "COMPLIANT"
        lines.append([quarter, depots_reporting, samples, breach_rows, no_data_rows, status])
    return lines


# ---------------------------------------------------------------- writing


def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def write_csv(path, header, rows):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py <corpus_dir> <out_dir>\n")
        return 2
    corpus_dir, out_dir = argv[1], argv[2]

    measurements, rejected, ledger = build(corpus_dir)
    cells, row_samples, panel_rows, row_index = aggregate(measurements)
    depot_reports = build_depot_reports(cells, row_samples, row_index)
    assay_reports = build_assay_reports(measurements)
    quarter_lines = build_quarter_lines(row_index)

    os.makedirs(out_dir, exist_ok=True)

    write_json(
        os.path.join(out_dir, "panel.json"),
        {"panel": PANEL, "ledger": ledger, "rows": panel_rows},
    )
    for depot in DEPOTS:
        write_json(os.path.join(out_dir, "depots", depot + ".json"), depot_reports[depot])
    for assay in ASSAYS:
        write_json(os.path.join(out_dir, "assays", assay + ".json"), assay_reports[assay])

    write_csv(
        os.path.join(out_dir, "quarters.csv"),
        ["quarter", "depots_reporting", "samples", "breach_rows", "no_data_rows", "status"],
        quarter_lines,
    )

    ordered = sorted(measurements, key=lambda m: (m["sample_id"], ASSAY_INDEX[m["assay"]]))
    write_csv(
        os.path.join(out_dir, "measurements.csv"),
        ["sample_id", "depot", "quarter", "assay", "lab", "transmission_id", "result"],
        [
            [
                m["sample_id"],
                m["depot"],
                m["quarter"],
                m["assay"],
                m["lab"],
                m["transmission_id"],
                m["result_text"],
            ]
            for m in ordered
        ],
    )

    write_csv(
        os.path.join(out_dir, "rejected.csv"),
        ["transmission_id", "reason"],
        sorted(rejected, key=lambda r: r[0]),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
