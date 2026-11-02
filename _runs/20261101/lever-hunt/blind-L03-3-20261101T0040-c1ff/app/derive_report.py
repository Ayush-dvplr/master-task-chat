#!/usr/bin/env python3
"""Cold-Storage Contaminant Panel CSP-2026.

Usage:
    python3 /app/derive_report.py <corpus_dir> <out_dir>

Reads one extract of laboratory transmissions from
``<corpus_dir>/transmissions/*.csv`` and writes the panel files into
``<out_dir>`` as declared by ``panel_contract.md`` / ``output_schema.json``.

Python 3 standard library only.
"""

import csv
import glob
import json
import os
import sys
from decimal import Decimal
from fractions import Fraction

PANEL = "CSP-2026"

# ---------------------------------------------------------------- declared universe

DEPOTS = ["KES", "MAR", "OSS", "TAL"]

# (quarter, first day, last day) -- both ends inclusive, assigned by collected_on
QUARTERS = [
    ("2026-Q1", "2026-01-01", "2026-03-31"),
    ("2026-Q2", "2026-04-01", "2026-06-30"),
    ("2026-Q3", "2026-07-01", "2026-09-30"),
]
QUARTER_CODES = [q for q, _, _ in QUARTERS]

# (assay, limit in mg/kg)
ASSAYS = [
    ("PB", "0.300"),
    ("CD", "0.100"),
    ("HG", "0.500"),
    ("AS", "0.200"),
    ("HIS", "100.000"),
]
ASSAY_CODES = [a for a, _ in ASSAYS]
LIMIT = {a: Decimal(lim) for a, lim in ASSAYS}
ASSAY_ORDER = {a: i for i, a in enumerate(ASSAY_CODES)}

# lab priority tier, 1 = highest. A lab outside the table ranks below all of them.
LAB_TIER = {"NRL": 1, "ACM": 2, "BLX": 2, "FSK": 3}
UNKNOWN_TIER = 10 ** 6

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

NO_SUMMARY = -1  # mean / max / worst_ratio with nothing to summarise

# ---------------------------------------------------------------- numeric helpers


def round3(value):
    """Round a Fraction/Decimal exactly to three decimals, half away from zero."""
    frac = value if isinstance(value, Fraction) else Fraction(Decimal(value))
    scaled = frac * 1000
    num, den = scaled.numerator, scaled.denominator
    if num >= 0:
        q = (2 * num + den) // (2 * den)
    else:
        q = -((-2 * num + den) // (2 * den))
    return Decimal(q).scaleb(-3)


def jnum(dec):
    """Decimal -> JSON number (shortest float repr round-trips 3-decimal values)."""
    return float(str(dec))


# ---------------------------------------------------------------- input


def quarter_of(collected_on):
    for code, first, last in QUARTERS:
        if first <= collected_on <= last:
            return code
    return None


def read_transmissions(corpus_dir):
    """Every .csv in <corpus_dir>/transmissions; file names carry no meaning."""
    pattern = os.path.join(corpus_dir, "transmissions", "*.csv")
    rows = []
    for path in sorted(glob.glob(pattern)):
        with open(path, "r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for raw in reader:
                row = {key: (raw.get(key) or "").strip() for key in FIELDS}
                row["_source"] = os.path.basename(path)
                rows.append(row)
    return rows


def validate(row):
    """Return rejection reason, or None when the transmission is valid."""
    if row["depot"] not in DEPOTS:
        return "UNKNOWN_DEPOT"
    if row["assay"] not in ASSAY_CODES:
        return "UNKNOWN_ASSAY"
    if quarter_of(row["collected_on"]) is None:
        return "OUT_OF_PERIOD"
    return None


def resolve(valid_rows):
    """One accepted transmission per (sample_id, assay); the rest are superseded."""
    groups = {}
    for row in valid_rows:
        groups.setdefault((row["sample_id"], row["assay"]), []).append(row)

    accepted, superseded = [], []
    for key in groups:
        candidates = groups[key]
        best = min(
            candidates,
            key=lambda r: (
                LAB_TIER.get(r["lab"], UNKNOWN_TIER),   # highest tier wins
                _desc(r["reported_at"]),                 # then latest reported_at
                _desc(r["transmission_id"]),             # stable last resort
            ),
        )
        accepted.append(best)
        superseded.extend(r for r in candidates if r is not best)
    return accepted, superseded


class _desc(object):
    """Sort key wrapper that reverses the ordering of a string."""

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return self.value > other.value

    def __eq__(self, other):
        return self.value == other.value


# ---------------------------------------------------------------- aggregation


def build(rows):
    rejected = []
    valid = []
    for row in rows:
        reason = validate(row)
        if reason is None:
            valid.append(row)
        else:
            rejected.append((row["transmission_id"], reason))

    accepted, superseded = resolve(valid)

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
                "result": Decimal(row["result"]),
            }
        )

    ledger = {
        "rows_read": len(rows),
        "accepted": len(accepted),
        "superseded": len(superseded),
        "rejected": len(rejected),
    }
    return measurements, ledger, rejected


def stats_block(values, limit):
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "max": None, "exceedances": 0}
    total = Fraction(0)
    for value in values:
        total += Fraction(value)
    return {
        "n": n,
        "mean": round3(total / n),
        "max": max(values),
        "exceedances": sum(1 for value in values if value > limit),
    }


def emit(measurements, ledger, rejected, out_dir):
    # index accepted measurements -------------------------------------------------
    by_cell = {}      # (depot, quarter, assay) -> [Decimal]
    row_samples = {}  # (depot, quarter) -> set(sample_id)
    depot_samples = {d: set() for d in DEPOTS}
    for m in measurements:
        by_cell.setdefault((m["depot"], m["quarter"], m["assay"]), []).append(m["result"])
        row_samples.setdefault((m["depot"], m["quarter"]), set()).add(m["sample_id"])
        depot_samples[m["depot"]].add(m["sample_id"])

    # panel rows ------------------------------------------------------------------
    panel_rows = []
    row_index = {}
    for depot in DEPOTS:
        for quarter in QUARTER_CODES:
            samples = len(row_samples.get((depot, quarter), ()))
            cells = {}
            breach = False
            worst_ratio = None
            for assay in ASSAY_CODES:
                values = by_cell.get((depot, quarter, assay), [])
                block = stats_block(values, LIMIT[assay])
                if block["n"] == 0:
                    cells[assay] = {
                        "status": "NO_SAMPLE",
                        "n": 0,
                        "mean": None,
                        "max": None,
                        "exceedances": 0,
                    }
                    continue
                if block["exceedances"] > 0:
                    breach = True
                ratio = Fraction(block["max"]) / Fraction(LIMIT[assay])
                if worst_ratio is None or ratio > worst_ratio:
                    worst_ratio = ratio
                cells[assay] = {
                    "status": "MEASURED",
                    "n": block["n"],
                    "mean": jnum(block["mean"]),
                    "max": jnum(block["max"]),
                    "exceedances": block["exceedances"],
                }
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
                "assays": cells,
            }
            panel_rows.append(row)
            row_index[(depot, quarter)] = {
                "samples": samples,
                "status": status,
                "worst_ratio": worst_ratio,
            }

    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(out_dir, "depots"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "assays"), exist_ok=True)

    write_json(
        os.path.join(out_dir, "panel.json"),
        {"panel": PANEL, "ledger": ledger, "rows": panel_rows},
    )

    # depot reports ---------------------------------------------------------------
    for depot in DEPOTS:
        entries = []
        breach_quarters = 0
        for quarter in QUARTER_CODES:
            info = row_index[(depot, quarter)]
            if info["status"] == "BREACH":
                breach_quarters += 1
            ratio = info["worst_ratio"]
            entries.append(
                {
                    "quarter": quarter,
                    "samples": info["samples"],
                    "worst_ratio": NO_SUMMARY if ratio is None else jnum(round3(ratio)),
                    "status": info["status"],
                }
            )
        total_samples = len(depot_samples[depot])
        if total_samples == 0:
            status = "NO_DATA"
        elif breach_quarters > 0:
            status = "BREACH"
        else:
            status = "COMPLIANT"
        write_json(
            os.path.join(out_dir, "depots", depot + ".json"),
            {
                "depot": depot,
                "total_samples": total_samples,
                "breach_quarters": breach_quarters,
                "status": status,
                "quarters": entries,
            },
        )

    # assay reports ---------------------------------------------------------------
    for assay in ASSAY_CODES:
        limit = LIMIT[assay]
        all_values = [m["result"] for m in measurements if m["assay"] == assay]
        overall = stats_block(all_values, limit)
        if overall["n"] == 0:
            status = "NO_SAMPLE"
        elif overall["exceedances"] > 0:
            status = "EXCEEDED"
        else:
            status = "WITHIN"
        by_quarter = []
        for quarter in QUARTER_CODES:
            values = []
            depots_sampled = 0
            for depot in DEPOTS:
                cell = by_cell.get((depot, quarter, assay), [])
                if cell:
                    depots_sampled += 1
                    values.extend(cell)
            block = stats_block(values, limit)
            by_quarter.append(
                {
                    "quarter": quarter,
                    "n": block["n"],
                    "mean": NO_SUMMARY if block["n"] == 0 else jnum(block["mean"]),
                    "max": NO_SUMMARY if block["n"] == 0 else jnum(block["max"]),
                    "exceedances": block["exceedances"],
                    "depots_sampled": depots_sampled,
                }
            )
        write_json(
            os.path.join(out_dir, "assays", assay + ".json"),
            {
                "assay": assay,
                "limit": jnum(limit),
                "n": overall["n"],
                "mean": NO_SUMMARY if overall["n"] == 0 else jnum(overall["mean"]),
                "max": NO_SUMMARY if overall["n"] == 0 else jnum(overall["max"]),
                "exceedances": overall["exceedances"],
                "status": status,
                "by_quarter": by_quarter,
            },
        )

    # quarters.csv ----------------------------------------------------------------
    quarter_lines = []
    for quarter in QUARTER_CODES:
        depots_reporting = 0
        samples = 0
        breach_rows = 0
        no_data_rows = 0
        for depot in DEPOTS:
            info = row_index[(depot, quarter)]
            if info["samples"] > 0:
                depots_reporting += 1
                samples += info["samples"]
            if info["status"] == "BREACH":
                breach_rows += 1
            elif info["status"] == "NO_DATA":
                no_data_rows += 1
        if samples == 0:
            status = "NO_DATA"
        elif breach_rows > 0:
            status = "BREACH"
        else:
            status = "COMPLIANT"
        quarter_lines.append(
            [quarter, depots_reporting, samples, breach_rows, no_data_rows, status]
        )
    write_csv(
        os.path.join(out_dir, "quarters.csv"),
        ["quarter", "depots_reporting", "samples", "breach_rows", "no_data_rows", "status"],
        quarter_lines,
    )

    # measurements.csv ------------------------------------------------------------
    ordered = sorted(
        measurements, key=lambda m: (m["sample_id"], ASSAY_ORDER[m["assay"]])
    )
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

    # rejected.csv ----------------------------------------------------------------
    write_csv(
        os.path.join(out_dir, "rejected.csv"),
        ["transmission_id", "reason"],
        sorted(rejected, key=lambda pair: pair[0]),
    )


def write_json(path, payload):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def write_csv(path, header, rows):
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
    rows = read_transmissions(corpus_dir)
    measurements, ledger, rejected = build(rows)
    emit(measurements, ledger, rejected, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
