#!/usr/bin/env python3
"""Cold-Storage Contaminant Panel CSP-2026.

Usage:
    python3 derive_report.py <corpus_dir> <out_dir>

Reads every ``*.csv`` under ``<corpus_dir>/transmissions/`` and writes the
panel files described in panel_contract.md / output_schema.json into
``<out_dir>``.  Python 3 standard library only.
"""

import csv
import glob
import json
import os
import sys
from decimal import Decimal, ROUND_HALF_UP

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

# lab priority tier: lower wins
LAB_TIER = {"NRL": 1, "ACM": 2, "BLX": 2, "FSK": 3}
UNKNOWN_TIER = 99

THREE = Decimal("0.001")


def q3(value):
    """Round a Decimal half-up to three decimals and return it as a JSON number."""
    return float(Decimal(value).quantize(THREE, rounding=ROUND_HALF_UP))


def quarter_of(collected_on):
    for code, first, last in QUARTERS:
        if first <= collected_on <= last:
            return code
    return None


# ---------------------------------------------------------------- input
def read_transmissions(corpus_dir):
    pattern = os.path.join(corpus_dir, "transmissions", "*.csv")
    rows = []
    for path in sorted(glob.glob(pattern)):
        with open(path, newline="", encoding="utf-8") as fh:
            for rec in csv.DictReader(fh):
                if rec.get("transmission_id") is None:
                    continue
                if not any((v or "").strip() for v in rec.values()):
                    continue
                rows.append({k: (rec.get(k) or "").strip() for k in
                             ("transmission_id", "lab", "sample_id", "depot",
                              "collected_on", "assay", "result", "reported_at")})
    return rows


def validate(rows):
    """Split into (valid, rejected) where rejected is a list of (tid, reason)."""
    valid, rejected = [], []
    for rec in rows:
        if rec["depot"] not in DEPOTS:
            rejected.append((rec["transmission_id"], "UNKNOWN_DEPOT"))
            continue
        if rec["assay"] not in ASSAYS:
            rejected.append((rec["transmission_id"], "UNKNOWN_ASSAY"))
            continue
        quarter = quarter_of(rec["collected_on"])
        if quarter is None:
            rejected.append((rec["transmission_id"], "OUT_OF_PERIOD"))
            continue
        rec = dict(rec)
        rec["quarter"] = quarter
        valid.append(rec)
    return valid, rejected


def resolve(valid):
    """Keep one transmission per (sample_id, assay); return (accepted, superseded_count)."""
    best = {}
    for rec in valid:
        key = (rec["sample_id"], rec["assay"])
        current = best.get(key)
        if current is None or sort_key(rec) < sort_key(current):
            best[key] = rec
    accepted = list(best.values())
    return accepted, len(valid) - len(accepted)


def sort_key(rec):
    # lowest tier wins; inside a tier the latest reported_at wins;
    # transmission_id only as a last-resort determinism guard.
    return (LAB_TIER.get(rec["lab"], UNKNOWN_TIER),
            _invert(rec["reported_at"]),
            rec["transmission_id"])


def _invert(text):
    # descending string order expressed as an ascending key
    return tuple(-ord(ch) for ch in text)


# ---------------------------------------------------------------- aggregation
def build(accepted):
    """Return (cells, row_samples) keyed for every declared combination."""
    cells = {}
    for depot in DEPOTS:
        for quarter in QUARTER_CODES:
            for assay in ASSAYS:
                cells[(depot, quarter, assay)] = []
    row_samples = {(d, q): set() for d in DEPOTS for q in QUARTER_CODES}

    for rec in accepted:
        key = (rec["depot"], rec["quarter"], rec["assay"])
        cells[key].append(rec)
        row_samples[(rec["depot"], rec["quarter"])].add(rec["sample_id"])
    return cells, row_samples


def cell_stats(records, assay):
    n = len(records)
    if n == 0:
        return {"status": "NO_SAMPLE", "n": 0, "mean": None, "max": None,
                "exceedances": 0}
    values = [Decimal(r["result"]) for r in records]
    limit = LIMITS[assay]
    biggest = max(values)
    return {
        "status": "MEASURED",
        "n": n,
        "mean": q3(sum(values) / Decimal(n)),
        "max": float(biggest),
        "exceedances": sum(1 for v in values if v > limit),
        "_max_dec": biggest,
    }


def flat_stats(records, assay):
    """Stats block used by the assay reports (-1 instead of null)."""
    n = len(records)
    limit = LIMITS[assay]
    if n == 0:
        return {"n": 0, "mean": -1, "max": -1, "exceedances": 0}
    values = [Decimal(r["result"]) for r in records]
    return {
        "n": n,
        "mean": q3(sum(values) / Decimal(n)),
        "max": float(max(values)),
        "exceedances": sum(1 for v in values if v > limit),
    }


# ---------------------------------------------------------------- output
def write_json(path, payload):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        json.dump(payload, fh, indent=2)
        fh.write("\n")


def write_csv(path, header, lines):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(header) + "\n")
        for line in lines:
            fh.write(",".join(str(c) for c in line) + "\n")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py <corpus_dir> <out_dir>\n")
        return 2
    corpus_dir, out_dir = argv[1], argv[2]

    rows = read_transmissions(corpus_dir)
    valid, rejected = validate(rows)
    accepted, superseded = resolve(valid)

    cells, row_samples = build(accepted)

    # ---- panel rows
    panel_rows = []
    row_index = {}
    for depot in DEPOTS:
        for quarter in QUARTER_CODES:
            assay_blocks = {}
            measured_ratios = []
            breach = False
            for assay in ASSAYS:
                stats = cell_stats(cells[(depot, quarter, assay)], assay)
                if stats["status"] == "MEASURED":
                    measured_ratios.append(stats.pop("_max_dec") / LIMITS[assay])
                    if stats["exceedances"] > 0:
                        breach = True
                assay_blocks[assay] = stats
            samples = len(row_samples[(depot, quarter)])
            if samples == 0:
                status = "NO_DATA"
            elif breach:
                status = "BREACH"
            else:
                status = "COMPLIANT"
            row = {"depot": depot, "quarter": quarter, "samples": samples,
                   "status": status, "assays": assay_blocks}
            panel_rows.append(row)
            row_index[(depot, quarter)] = {
                "samples": samples,
                "status": status,
                "worst_ratio": q3(max(measured_ratios)) if measured_ratios else -1,
            }

    ledger = {"rows_read": len(rows), "accepted": len(accepted),
              "superseded": superseded, "rejected": len(rejected)}
    write_json(os.path.join(out_dir, "panel.json"),
               {"panel": PANEL, "ledger": ledger, "rows": panel_rows})

    # ---- depot reports
    for depot in DEPOTS:
        entries = []
        total_samples = set()
        breach_quarters = 0
        for quarter in QUARTER_CODES:
            info = row_index[(depot, quarter)]
            entries.append({"quarter": quarter, "samples": info["samples"],
                            "worst_ratio": info["worst_ratio"],
                            "status": info["status"]})
            if info["status"] == "BREACH":
                breach_quarters += 1
            total_samples |= row_samples[(depot, quarter)]
        if not total_samples:
            status = "NO_DATA"
        elif breach_quarters > 0:
            status = "BREACH"
        else:
            status = "COMPLIANT"
        write_json(os.path.join(out_dir, "depots", depot + ".json"),
                   {"depot": depot, "total_samples": len(total_samples),
                    "breach_quarters": breach_quarters, "status": status,
                    "quarters": entries})

    # ---- assay reports
    for assay in ASSAYS:
        all_records = [r for r in accepted if r["assay"] == assay]
        overall = flat_stats(all_records, assay)
        if overall["n"] == 0:
            status = "NO_SAMPLE"
        elif overall["exceedances"] > 0:
            status = "EXCEEDED"
        else:
            status = "WITHIN"
        by_quarter = []
        for quarter in QUARTER_CODES:
            records = [r for r in all_records if r["quarter"] == quarter]
            stats = flat_stats(records, assay)
            depots_sampled = sum(
                1 for depot in DEPOTS if cells[(depot, quarter, assay)])
            entry = {"quarter": quarter}
            entry.update(stats)
            entry["depots_sampled"] = depots_sampled
            by_quarter.append(entry)
        payload = {"assay": assay, "limit": float(LIMITS[assay])}
        payload.update(overall)
        payload["status"] = status
        payload["by_quarter"] = by_quarter
        write_json(os.path.join(out_dir, "assays", assay + ".json"), payload)

    # ---- quarters.csv
    quarter_lines = []
    for quarter in QUARTER_CODES:
        infos = [row_index[(depot, quarter)] for depot in DEPOTS]
        depots_reporting = sum(1 for i in infos if i["samples"] > 0)
        samples = sum(i["samples"] for i in infos if i["samples"] > 0)
        breach_rows = sum(1 for i in infos if i["status"] == "BREACH")
        no_data_rows = sum(1 for i in infos if i["status"] == "NO_DATA")
        if samples == 0:
            status = "NO_DATA"
        elif breach_rows > 0:
            status = "BREACH"
        else:
            status = "COMPLIANT"
        quarter_lines.append([quarter, depots_reporting, samples, breach_rows,
                              no_data_rows, status])
    write_csv(os.path.join(out_dir, "quarters.csv"),
              ["quarter", "depots_reporting", "samples", "breach_rows",
               "no_data_rows", "status"], quarter_lines)

    # ---- measurements.csv
    assay_rank = {a: i for i, a in enumerate(ASSAYS)}
    ordered = sorted(accepted, key=lambda r: (r["sample_id"],
                                              assay_rank[r["assay"]]))
    write_csv(os.path.join(out_dir, "measurements.csv"),
              ["sample_id", "depot", "quarter", "assay", "lab",
               "transmission_id", "result"],
              [[r["sample_id"], r["depot"], r["quarter"], r["assay"], r["lab"],
                r["transmission_id"], r["result"]] for r in ordered])

    # ---- rejected.csv
    write_csv(os.path.join(out_dir, "rejected.csv"),
              ["transmission_id", "reason"],
              sorted(rejected, key=lambda x: x[0]))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
