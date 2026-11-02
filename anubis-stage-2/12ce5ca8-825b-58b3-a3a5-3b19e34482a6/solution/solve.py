"""Reference aggregator for the 12ce5ca8-825b-58b3-a3a5-3b19e34482a6 task.

Written against the written contract at /app/data/schema.md. It resolves the
dependency chain to the one authoritative event corpus and the one active
coefficient set, recomputes every scenario rollup with integer and exact-decimal
arithmetic, and writes the ten artifacts the contract describes.

Standard library only. This module reads no clock and draws no randomness: the
relative median that perf_report.json carries is measured by the caller and
handed to build_artifacts, so that timing never leaks into the aggregator itself.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ElementTree
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

# Section 3: the corpus column order.
EVENT_COLUMNS = [
    "id",
    "ts",
    "account",
    "region",
    "kind",
    "amount",
    "units",
    "latency_ms",
    "flag",
    "meter",
    "energy_wh",
]

# Section 7: the order every artifact lists the scenarios in.
SCENARIOS_IN_REPORT_ORDER = ["visible", "peak", "steady", "burst", "latency"]

# Section 1 step 4: the six configuration roles resolved from the ledger.
CONFIG_ROLES = ["baseline", "cost", "hardware", "queryplan", "indexcfg", "thresholds"]

ENTRYPOINT_FILE = "ingest_handoff_notes.txt"
CATALOG_POINTER_PREFIX = "catalog_ref:"
LEDGER_CATALOG_KEY = "binding_registry"

AGGREGATOR_PATH = "/app/out/optimize.py"
BENCHMARK_METHOD = "repeated in-process median of aggregate vs baseline rescan engine"
PRIMARY_BOTTLENECK = "per_key_rescan"
RECOMMENDATION_LINES = [
    "resolve the active coefficient generation before scoring",
    "apply the half-open window and rollover-safe meter usage",
    "round energy and tariff once per account at the end",
]

def round_half_up(numerator: int, denominator: int) -> int:
    """Divide exactly and round half away from zero, per the contract's half_up.

    Decimal keeps this off binary floating point, which the contract requires.
    """
    quotient = Decimal(int(numerator)) / Decimal(int(denominator))
    return int(quotient.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def read_json_file(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Section 1 and 2: resolving the dependency chain
# --------------------------------------------------------------------------


def read_catalog_pointer(data_dir: Path) -> str:
    """Return the catalog filename named on the entrypoint's catalog_ref line."""
    entrypoint = Path(data_dir) / ENTRYPOINT_FILE
    for raw_line in entrypoint.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith(CATALOG_POINTER_PREFIX):
            return line[len(CATALOG_POINTER_PREFIX):].strip()
    raise ValueError(f"{ENTRYPOINT_FILE} carries no {CATALOG_POINTER_PREFIX} line")


def read_ledger_pointer(data_dir: Path, catalog_file: str) -> str:
    """Return the binding ledger filename the catalog's binding_registry row names."""
    connection = sqlite3.connect(str(Path(data_dir) / catalog_file))
    try:
        row = connection.execute(
            "SELECT target FROM catalog WHERE key = ?", (LEDGER_CATALOG_KEY,)
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise ValueError(f"{catalog_file} has no {LEDGER_CATALOG_KEY} row")
    return row[0]


def read_binding_ledger(data_dir: Path, ledger_file: str) -> list[dict[str, str]]:
    with (Path(data_dir) / ledger_file).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def pick_active_generation(ledger: list[dict[str, str]], role: str) -> str:
    """Apply section 2: among active rows for the role, the highest generation wins.

    Draft and superseded rows are never eligible, whatever generation they carry.
    """
    active = [row for row in ledger if row["role"] == role and row["state"] == "active"]
    if not active:
        raise ValueError(f"the ledger binds no active row for role {role}")
    winner = max(active, key=lambda row: int(row["generation"]))
    return winner["file"]


def load_event_corpus(data_dir: Path, manifest_file: str) -> list[dict[str, str]]:
    """Concatenate the non-superseded shards in ascending sequence order.

    The resulting row order is itself load-bearing: the checksum folds over it.
    """
    manifest_path = Path(data_dir) / manifest_file
    entries = []
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        entry = json.loads(line)
        if not entry.get("superseded"):
            entries.append(entry)
    entries.sort(key=lambda entry: int(entry["sequence"]))

    corpus: list[dict[str, str]] = []
    for entry in entries:
        corpus.extend(read_events(Path(data_dir) / entry["file"]))
    return corpus


def read_events(path: Path | str) -> list[dict[str, str]]:
    """Section 3: read one events file by column name; the extension picks the
    format (.csv, .psv or .ndjson). A BOM, CRLF line endings, extra columns and
    blank lines are all tolerated; NDJSON integers become their text."""
    path = Path(path)
    if path.suffix == ".ndjson":
        rows = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                rows.append({str(key).strip().lower(): str(value)
                             for key, value in json.loads(line).items()})
        return rows
    delimiter = "|" if path.suffix == ".psv" else ","
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        # Whitespace around a header name is not part of the name.
        reader.fieldnames = [name.strip().lower() for name in (reader.fieldnames or [])]
        return list(reader)


# Section 4b: the dedicated sources.
SPREADSHEET = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
OFFICE_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PACKAGE_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
WORD = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
TIER_SHEET = re.compile(r"tiers_(\d{4})Q([1-4])")


def read_region_offsets(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(str(path))
    try:
        rows = connection.execute(
            "SELECT region, offset FROM region_offsets WHERE state = 'active'"
        ).fetchall()
    finally:
        connection.close()
    # Region names are normalised like the region field.
    return {str(region).strip().lower(): int(offset) for region, offset in rows}


def read_tariff_tiers(path: Path) -> list[list[int]]:
    """Pick the latest non-draft tiers_<year>Q<quarter> sheet and read its pairs."""
    with zipfile.ZipFile(path) as book:
        workbook = ElementTree.fromstring(book.read("xl/workbook.xml"))
        relations = ElementTree.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {rel.get("Id"): rel.get("Target") for rel in relations.iter(PACKAGE_REL + "Relationship")}
        shared: list[str] = []
        if "xl/sharedStrings.xml" in book.namelist():
            strings = ElementTree.fromstring(book.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in item.iter(SPREADSHEET + "t"))
                      for item in strings.iter(SPREADSHEET + "si")]
        candidates = []
        for sheet in workbook.iter(SPREADSHEET + "sheet"):
            match = TIER_SHEET.fullmatch(sheet.get("name"))
            if match:
                candidates.append(((int(match.group(1)), int(match.group(2))), sheet.get(OFFICE_REL + "id")))
        _quarter, relation_id = max(candidates)
        part = "xl/" + targets[relation_id].lstrip("/").removeprefix("xl/")
        sheet_xml = ElementTree.fromstring(book.read(part))
    table = []
    for row in sheet_xml.iter(SPREADSHEET + "row"):
        values = []
        for cell in row.iter(SPREADSHEET + "c"):
            if cell.get("t") == "inlineStr":
                values.append("".join(t.text or "" for t in cell.iter(SPREADSHEET + "t")))
            elif cell.get("t") == "s":
                values.append(shared[int(cell.find(SPREADSHEET + "v").text)])
            else:
                value = cell.find(SPREADSHEET + "v")
                values.append("" if value is None else value.text)
        table.append(values)
    # Section 4c: a rate cell reading "calibrate" is held back (None here).
    return [[int(float(start)), None if bps.strip().lower() == "calibrate" else int(float(bps))]
            for start, bps, *_rest in table[1:] if start != "" and bps != ""]


def amend_seed_overrides(overrides: dict[str, int], addendum: Path) -> dict[str, int]:
    """Apply the addendum table rows in order: a number sets, 'remove' deletes."""
    with zipfile.ZipFile(addendum) as document:
        body = ElementTree.fromstring(document.read("word/document.xml"))
    table = next(body.iter(WORD + "tbl"))
    rows = [["".join(t.text or "" for t in cell.iter(WORD + "t")) for cell in row.iter(WORD + "tc")]
            for row in table.iter(WORD + "tr")]
    amended = {str(account).strip().upper(): int(seed) for account, seed in overrides.items()}
    for account, seed in rows[1:]:
        key = account.strip().upper()
        if seed.strip().lower() == "remove":
            amended.pop(key, None)
        else:
            amended[key] = int(seed.strip())
    return amended


def read_policy(path: Path) -> dict[str, str]:
    """Flat key: value YAML lines; '#' starts a comment."""
    policy = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if ":" in line:
            key, value = line.split(":", 1)
            policy[key.strip().strip("\"'")] = value.strip().strip("\"'")
    return policy


def resolve_inputs(data_dir: Path | str) -> dict[str, Any]:
    """Walk the whole chain and return the authoritative inputs it reaches."""
    data_dir = Path(data_dir)
    catalog_file = read_catalog_pointer(data_dir)
    ledger_file = read_ledger_pointer(data_dir, catalog_file)
    ledger = read_binding_ledger(data_dir, ledger_file)

    coefficient_file = pick_active_generation(ledger, "coeff")
    manifest_file = pick_active_generation(ledger, "segments")
    seeds_file = pick_active_generation(ledger, "meterseeds")
    configs = {
        role: read_json_file(data_dir / pick_active_generation(ledger, role))
        for role in CONFIG_ROLES
    }
    overrides = amend_seed_overrides(
        read_json_file(data_dir / seeds_file)["overrides"],
        data_dir / pick_active_generation(ledger, "seedaddendum"),
    )
    # Section 4b precedence: the dedicated roles replace the coefficient file's copies.
    coefficients = dict(read_json_file(data_dir / coefficient_file))
    coefficients["region_offsets"] = read_region_offsets(data_dir / pick_active_generation(ledger, "regions"))
    coefficients["tariff_tiers"] = read_tariff_tiers(data_dir / pick_active_generation(ledger, "tariff"))
    coefficients["void_flag"] = read_policy(data_dir / pick_active_generation(ledger, "policy"))["void_flag"].lower()
    # Section 4c: recover the held-back parameters once from the calibration controls.
    coefficients["calibration"] = read_json_file(data_dir / pick_active_generation(ledger, "calibration"))
    coefficients["unit_divisor"] = recover_unit_divisor(coefficients)
    coefficients["tariff_tiers"] = [list(tier) for tier in sorted_tariff_tiers(coefficients)]

    return {
        "coefficients": coefficients,
        "meter_seed_overrides": overrides,
        "events": load_event_corpus(data_dir, manifest_file),
        "configs": configs,
        "provenance": f"{coefficient_file}+{manifest_file}",
    }


# --------------------------------------------------------------------------
# Section 5 and 6: the corrected computation
# --------------------------------------------------------------------------


def scenario_rules(coefficients: dict[str, Any], window: list[int],
                   meter_seed_overrides: dict[str, int]) -> dict[str, Any]:
    """Flatten the coefficient set plus one scenario window into a rules object."""
    rules = {
        "label": coefficients["label"],
        "window_start": int(window[0]),
        "window_end": int(window[1]),
        "kind_weights": coefficients["kind_weights"],
        "region_offsets": coefficients["region_offsets"],
        "flag_penalties": coefficients["flag_penalties"],
        "top_n": int(coefficients["top_n"]),
        "meter_modulus": int(coefficients["meter_modulus"]),
        "meter_seed": int(coefficients["meter_seed"]),
        "tariff_bps": int(coefficients["tariff_bps"]),
        "tariff_tiers": coefficients["tariff_tiers"],
        "meter_seed_overrides": meter_seed_overrides,
        "unit_divisor": int(coefficients["unit_divisor"]),
        "void_flag": coefficients["void_flag"],
    }
    for key in (
        "account_aliases", "region_aliases", "kind_aliases", "flag_aliases",
        "account_meter_modulus", "account_unit_divisor", "account_tariff_tiers",
        "account_tariff_credit_wh", "meter_reset_flag",
    ):
        if key in coefficients:
            rules[key] = coefficients[key]
    return rules


def resolve_rules(data_dir: Path | str, scenario: str) -> dict[str, Any]:
    """Section 6b: the fully resolved rules object for one scenario of a data tree."""
    resolved = resolve_inputs(data_dir)
    coefficients = resolved["coefficients"]
    rules = scenario_rules(coefficients, coefficients["scenario_windows"][scenario],
                           resolved["meter_seed_overrides"])
    result = {
        "label": rules["label"],
        "window_start": rules["window_start"],
        "window_end": rules["window_end"],
        "kind_weights": rules["kind_weights"],
        "region_offsets": rules["region_offsets"],
        "flag_penalties": rules["flag_penalties"],
        "top_n": rules["top_n"],
        "meter_modulus": rules["meter_modulus"],
        "meter_seed": rules["meter_seed"],
        "meter_seed_overrides": normalised_seed_overrides(rules),
        "tariff_tiers": [list(tier) for tier in sorted_tariff_tiers(rules)],
        "unit_divisor": int(rules["unit_divisor"]),
        "void_flag": rules["void_flag"],
    }
    for key in (
        "account_aliases", "region_aliases", "kind_aliases", "flag_aliases",
        "account_meter_modulus", "account_unit_divisor", "account_tariff_tiers",
        "account_tariff_credit_wh", "meter_reset_flag",
    ):
        if key in rules:
            result[key] = rules[key]
    return result


def _normalised_aliases(rules: dict[str, Any], key: str, upper: bool) -> dict[str, str]:
    clean = (lambda value: str(value).strip().upper()) if upper else (lambda value: str(value).strip().lower())
    return {clean(source): clean(target) for source, target in (rules.get(key) or {}).items()}


def normalise_row(row: dict[str, str], rules: dict[str, Any] | None = None) -> dict[str, str]:
    """Section 3a step 1: normalise fields, then apply one alias lookup."""
    rules = rules or {}
    clean = {column: str(row.get(column) or "").strip() for column in EVENT_COLUMNS}
    clean["id"] = clean["id"].lower()
    clean["account"] = clean["account"].upper()
    for column in ("region", "kind", "flag"):
        clean[column] = clean[column].lower()
    clean["account"] = _normalised_aliases(rules, "account_aliases", True).get(clean["account"], clean["account"])
    clean["region"] = _normalised_aliases(rules, "region_aliases", False).get(clean["region"], clean["region"])
    clean["kind"] = _normalised_aliases(rules, "kind_aliases", False).get(clean["kind"], clean["kind"])
    clean["flag"] = _normalised_aliases(rules, "flag_aliases", False).get(clean["flag"], clean["flag"])
    return clean


def admit_rows(raw_rows, kind_weights: dict[str, int], void_flag: str | None = None,
               rules: dict[str, Any] | None = None) -> dict[str, Any]:
    """Section 3a admission, including forward and trailing void notices."""
    ids_seen: set[str] = set()
    candidates: dict[str, tuple[int, dict[str, str]]] = {}
    void_ids: set[str] = set()
    replayed = 0
    for position, raw_row in enumerate(raw_rows):
        row = normalise_row(raw_row, rules)
        first = row["id"] not in ids_seen
        if first:
            ids_seen.add(row["id"])
            candidates.setdefault(row["id"], (position, row))
            continue
        replayed += 1
        if void_flag is not None and row["flag"] == void_flag:
            void_ids.add(row["id"])
    admitted = []
    quarantined = withdrawn = 0
    for row_id, (position, row) in candidates.items():
        if row["kind"] not in kind_weights:
            quarantined += 1
        elif row_id in void_ids:
            withdrawn += 1
        else:
            admitted.append((position, row))
    admitted.sort(key=lambda item: item[0])
    return {"admitted": [row for _position, row in admitted],
            "replayed": replayed, "quarantined": quarantined,
            "withdrawn": withdrawn}


def normalised_seed_overrides(rules: dict[str, Any]) -> dict[str, int]:
    """Section 4: override keys are normalised like the account field."""
    overrides = rules.get("meter_seed_overrides") or {}
    return {str(account).strip().upper(): int(value) for account, value in overrides.items()}


def seed_for_account(account: str, rules: dict[str, Any]) -> int:
    overrides = normalised_seed_overrides(rules)
    if account in overrides:
        return overrides[account]
    matches = [(len(key) - 1, key, value) for key, value in overrides.items()
               if key.endswith("*") and account.startswith(key[:-1])]
    if matches:
        return sorted(matches, key=lambda item: (-item[0], item[1]))[0][2]
    return int(rules["meter_seed"])


def account_integer_map(rules: dict[str, Any], key: str) -> dict[str, int]:
    return {str(account).strip().upper(): int(value)
            for account, value in (rules.get(key) or {}).items()}


def account_tariff_tiers(rules: dict[str, Any], account: str) -> list[tuple[int, int]]:
    profiles = {str(key).strip().upper(): value
                for key, value in (rules.get("account_tariff_tiers") or {}).items()}
    if account not in profiles:
        return sorted_tariff_tiers(rules)
    return sorted((int(start), int(bps)) for start, bps in profiles[account])


def id_number(event_id: str) -> int:
    match = re.search(r"([0-9]+)$", event_id)
    if match is None:
        raise ValueError("event id has no decimal suffix")
    return int(match.group(1))


def validate_rules(rules: dict[str, Any]) -> None:
    """Reject malformed reusable-rule extensions before touching event data."""
    required = (
        "label", "window_start", "window_end", "kind_weights",
        "region_offsets", "flag_penalties", "top_n", "meter_modulus",
        "meter_seed",
    )
    missing = [key for key in required if key not in rules]
    if missing:
        raise ValueError("rules missing required keys: " + ", ".join(missing))
    if int(rules["window_start"]) > int(rules["window_end"]):
        raise ValueError("window_start exceeds window_end")
    if int(rules["top_n"]) < 0:
        raise ValueError("top_n must be non-negative")
    if int(rules["meter_modulus"]) <= 0:
        raise ValueError("meter_modulus must be positive")
    for key in ("account_meter_modulus", "account_unit_divisor"):
        for account, value in (rules.get(key) or {}).items():
            if not str(account).strip() or int(value) <= 0:
                raise ValueError(key + " entries need an account and positive value")
    for account, value in (rules.get("account_tariff_credit_wh") or {}).items():
        if not str(account).strip() or int(value) < 0:
            raise ValueError("account tariff credits must be non-negative")
    for key in ("account_aliases", "region_aliases", "kind_aliases", "flag_aliases"):
        for source, target in (rules.get(key) or {}).items():
            if not str(source).strip() or not str(target).strip():
                raise ValueError(key + " cannot carry an empty alias")
    for account, tiers in (rules.get("account_tariff_tiers") or {}).items():
        if not str(account).strip() or not tiers:
            raise ValueError("each account tariff profile needs at least one tier")
        starts = [int(pair[0]) for pair in tiers]
        if min(starts) != 0 or len(starts) != len(set(starts)):
            raise ValueError("account tariff tier starts must be unique and include zero")


def sorted_tariff_tiers(rules: dict[str, Any]) -> list[tuple[int, int]]:
    """Section 4: tiers sorted by start; no tiers means one tier at tariff_bps.
    A rate given as null is recovered from the cost controls (section 4c)."""
    if "tariff_tiers" not in rules:
        return [(0, int(rules["tariff_bps"]))]
    tiers = sorted(((int(start), bps) for start, bps in rules["tariff_tiers"]), key=lambda tier: tier[0])
    held_back = [index for index, (_start, bps) in enumerate(tiers) if bps is None]
    if held_back:
        controls = (rules.get("calibration") or {}).get("cost", [])
        return recover_tier_rate(tiers, held_back[0], controls)
    return [(start, int(bps)) for start, bps in tiers]


def recover_tier_rate(tiers: list[tuple[int, Any]], index: int,
                      controls: list[dict[str, int]]) -> list[tuple[int, int]]:
    """Smallest bps >= 0 for the held-back tier that reproduces every cost control.

    Cost never falls as the rate rises, so a binary search on the first control
    finds the lowest candidate; from there candidates are checked upward.
    """
    def with_rate(bps):
        return [(start, bps if position == index else int(rate)) for position, (start, rate) in enumerate(tiers)]

    def matches(bps, control):
        return tiered_cost_cents(int(control["usage_wh"]), with_rate(bps), int(control["pre_wh"])) == int(control["cost_cents"])

    first = controls[0]
    low, high = 0, 1
    while tiered_cost_cents(int(first["usage_wh"]), with_rate(high), int(first["pre_wh"])) < int(first["cost_cents"]):
        high *= 2
    while low < high:
        middle = (low + high) // 2
        if tiered_cost_cents(int(first["usage_wh"]), with_rate(middle), int(first["pre_wh"])) < int(first["cost_cents"]):
            low = middle + 1
        else:
            high = middle
    candidate = low
    while not all(matches(candidate, control) for control in controls):
        candidate += 1
    return with_rate(candidate)


def recover_unit_divisor(rules: dict[str, Any]) -> int:
    """Section 4c: a given unit_divisor, else the smallest D >= 1 for which
    half_up(U, D) == K on every energy control. Each control confines D to an
    interval (U / (K + 1/2), U / (K - 1/2)]; the answer is the smallest integer
    in their intersection, confirmed against the controls."""
    if rules.get("unit_divisor") is not None:
        return int(rules["unit_divisor"])
    controls = (rules.get("calibration") or {}).get("energy", [])
    lowest = 1
    for control in controls:
        usage, kwh = Decimal(int(control["usage_wh"])), Decimal(int(control["energy_kwh"]))
        bound = usage / (kwh + Decimal("0.5"))
        lowest = max(lowest, int(bound) + 1 if bound == int(bound) else int(bound.to_integral_value(rounding="ROUND_CEILING")))
    candidate = max(1, lowest - 2)
    while not all(round_half_up(int(c["usage_wh"]), candidate) == int(c["energy_kwh"]) for c in controls):
        candidate += 1
    return candidate


def tiered_cost_cents(usage_wh: int, tiers: list[tuple[int, int]], pre_wh: int = 0) -> int:
    """Bill the cumulative range [pre_wh, pre_wh + usage_wh) watt-hour by tier,
    then round once for the account."""
    low, high = pre_wh, pre_wh + usage_wh
    tier_sum = 0
    for index, (start, bps) in enumerate(tiers):
        upper = tiers[index + 1][0] if index + 1 < len(tiers) else high
        billed = min(high, upper) - max(low, start)
        if billed > 0:
            tier_sum += billed * bps
    return round_half_up(tier_sum, 10000)


def aggregate(events_path: Any, rules_path: Any) -> dict[str, Any]:
    """Recompute one scenario rollup from an events CSV and a rules JSON.

    One structural pass over the admitted rows fills every output group at once,
    so no group is paid for with a second walk over the rows. Per-account meter
    series are ordered afterwards, which is the only place ordering is needed.
    """
    rules = read_json_file(rules_path)
    validate_rules(rules)
    window_start = int(rules["window_start"])
    window_end = int(rules["window_end"])
    kind_weights = rules["kind_weights"]
    region_offsets = rules["region_offsets"]
    flag_penalties = rules["flag_penalties"]
    modulus = int(rules["meter_modulus"])
    seed = int(rules["meter_seed"])
    divisor = recover_unit_divisor(rules)

    void_flag = rules.get("void_flag")
    if void_flag is not None:
        void_flag = str(void_flag).strip().lower()
    admitted = admit_rows(read_events(events_path), kind_weights, void_flag, rules)["admitted"]

    by_account: dict[str, int] = {}
    by_region: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    by_flag: dict[str, int] = {}
    meter_series: dict[str, list[tuple[int, str]]] = {}
    pre_window_series: dict[str, list[tuple[int, str]]] = {}
    last_before_window: dict[str, int] = {}
    checksum = 0
    windowed_rows = 0

    for row in admitted:
        timestamp = int(row["ts"])
        account = row["account"]
        if timestamp >= window_end:
            continue
        score = (
            int(row["amount"]) * int(row["units"]) * int(kind_weights[row["kind"]])
            + int(region_offsets.get(row["region"], 0))
            - int(flag_penalties.get(row["flag"], 0))
            - int(row["latency_ms"]) // 10
        )
        if timestamp < window_start:
            # Corpus order is the meter sequence, so the last encountered
            # pre-window reading anchors this account's window walk.
            meter = int(row["meter"])
            pre_window_series.setdefault(account, []).append((meter, row["flag"]))
            last_before_window[account] = meter
            continue
        windowed_rows += 1

        by_account[account] = by_account.get(account, 0) + score
        by_region[row["region"]] = by_region.get(row["region"], 0) + score
        by_kind[row["kind"]] = by_kind.get(row["kind"], 0) + score
        by_flag[row["flag"]] = by_flag.get(row["flag"], 0) + 1
        meter_series.setdefault(account, []).append((int(row["meter"]), row["flag"]))

        # position is the 1-based index among the windowed rows, in file order.
        checksum = (
            checksum * 1315423911 + score * windowed_rows + id_number(row["id"])
        ) & 0xFFFFFFFF

    usage_wh: dict[str, int] = {}
    energy_kwh: dict[str, int] = {}
    cost_cents: dict[str, int] = {}
    for account, readings in meter_series.items():
        prior = last_before_window.get(account)
        # A pre-window reading anchors the walk; otherwise the override, then the seed.
        previous = prior if prior is not None else seed_for_account(account, rules)
        modulus_for_account = account_integer_map(rules, "account_meter_modulus").get(account, modulus)
        reset_flag = str(rules.get("meter_reset_flag") or "").strip().lower()
        usage = 0
        for meter, flag in readings:
            # Modular difference recovers the true increment across a rollover.
            if flag != reset_flag:
                usage += (meter - previous) % modulus_for_account
            previous = meter
        usage_wh[account] = usage
        # Each rounding happens once, on the summed usage, never per row.
        divisor_for_account = account_integer_map(rules, "account_unit_divisor").get(account, divisor)
        energy_kwh[account] = round_half_up(usage, divisor_for_account)
        # Tier position: the usage walked before the window, from the override or seed.
        pre_usage = 0
        walk_from = seed_for_account(account, rules)
        for meter, flag in pre_window_series.get(account, []):
            if flag != reset_flag:
                pre_usage += (meter - walk_from) % modulus_for_account
            walk_from = meter
        credit = account_integer_map(rules, "account_tariff_credit_wh").get(account, 0)
        cost_cents[account] = tiered_cost_cents(
            usage, account_tariff_tiers(rules, account), max(0, pre_usage - credit))

    ranked = sorted(by_account.items(), key=lambda pair: (-pair[1], pair[0]))

    return {
        "label": str(rules["label"]),
        "window": [window_start, window_end],
        "event_count": windowed_rows,
        "account_totals": dict(sorted(by_account.items())),
        "region_totals": dict(sorted(by_region.items())),
        "kind_totals": dict(sorted(by_kind.items())),
        "flag_counts": dict(sorted(by_flag.items())),
        "account_usage_wh": dict(sorted(usage_wh.items())),
        "account_energy_kwh": dict(sorted(energy_kwh.items())),
        "account_cost_cents": dict(sorted(cost_cents.items())),
        "top_accounts": [[account, total] for account, total in ranked[: int(rules["top_n"])]],
        "checksum": checksum,
    }


def compute_all_scenarios(resolved: dict[str, Any]) -> dict[str, Any]:
    """Run aggregate once per scenario window over the resolved corpus.

    aggregate() takes file paths, so the concatenated corpus and one rules object
    per scenario are staged in a scratch directory this function owns.
    """
    scratch_dir = Path(tempfile.mkdtemp(prefix="rollup_scratch_"))
    corpus_csv = scratch_dir / "resolved_corpus.csv"
    with corpus_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(EVENT_COLUMNS)
        for row in resolved["events"]:
            writer.writerow([row[column] for column in EVENT_COLUMNS])

    windows = resolved["coefficients"]["scenario_windows"]
    results = {}
    for scenario in SCENARIOS_IN_REPORT_ORDER:
        rules_json = scratch_dir / f"rules_{scenario}.json"
        rules_json.write_text(
            json.dumps(scenario_rules(resolved["coefficients"], windows[scenario], resolved["meter_seed_overrides"]), sort_keys=True),
            encoding="utf-8",
        )
        results[scenario] = aggregate(str(corpus_csv), str(rules_json))
    return results


# --------------------------------------------------------------------------
# Section 7: the artifacts
# --------------------------------------------------------------------------


def write_sorted_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def scenario_metrics(result: dict[str, Any]) -> dict[str, Any]:
    total_score = sum(result["account_totals"].values())
    event_count = result["event_count"]
    leader = result["top_accounts"][0] if result["top_accounts"] else ["", 0]
    return {
        "average_score": round(total_score / event_count, 3) if event_count else 0.0,
        "top_account": leader[0],
        "top_account_score": leader[1],
        "total_score": total_score,
    }


def scenario_artifact(scenario: str, result: dict[str, Any], resolved: dict[str, Any]) -> dict[str, Any]:
    thresholds = resolved["configs"]["thresholds"]
    return {
        "scenario": scenario,
        "source": resolved["provenance"],
        "result": result,
        "metrics": scenario_metrics(result),
        "thresholds": {
            "max_relative_median": thresholds["max_relative_median"],
            "max_latency_warning_ms": thresholds["max_latency_warning_ms"],
        },
    }


def performance_artifact(resolved: dict[str, Any], observed_relative_median: float) -> dict[str, Any]:
    configs = resolved["configs"]
    return {
        "ok": True,
        "module": AGGREGATOR_PATH,
        "benchmark_method": BENCHMARK_METHOD,
        "observed_relative_median": observed_relative_median,
        "relative_target": configs["thresholds"]["max_relative_median"],
        "scenario_count": len(SCENARIOS_IN_REPORT_ORDER),
        "artifact_count": 10,
        "scenarios": list(SCENARIOS_IN_REPORT_ORDER),
        "baseline_name": configs["baseline"]["baseline_name"],
        "hardware_profile": configs["hardware"]["profile_name"],
    }


def bottleneck_artifact(resolved: dict[str, Any]) -> dict[str, Any]:
    query_plan = resolved["configs"]["queryplan"]
    medians = query_plan["baseline_median_ms_by_scenario"]
    # Greatest baseline median wins; an alphabetically earlier name breaks a tie.
    slowest = sorted(medians.items(), key=lambda pair: (-pair[1], pair[0]))[0][0]
    return {
        "primary_bottleneck": PRIMARY_BOTTLENECK,
        "baseline_complexities": query_plan["baseline_stages"],
        "optimized_complexities": query_plan["optimized_stages"],
        "baseline_median_ms_by_scenario": dict(sorted(medians.items())),
        "highest_baseline_scenario": slowest,
    }


def recommendations_artifact(resolved: dict[str, Any]) -> dict[str, Any]:
    index_config = resolved["configs"]["indexcfg"]
    return {
        "group_keys": index_config["group_keys"],
        "top_accounts_order": index_config["top_accounts_order"],
        "materialized_outputs": index_config["materialized_outputs"],
        "estimated_rewrite_fixed_cost": resolved["configs"]["cost"]["estimated_rewrite_fixed_cost"],
        "recommendations": list(RECOMMENDATION_LINES),
    }


def data_quality_artifact(input_files: list[str], results: dict[str, Any], resolved: dict[str, Any]) -> dict[str, Any]:
    admission = admit_rows(resolved["events"], resolved["coefficients"]["kind_weights"],
                           resolved["coefficients"]["void_flag"], resolved["coefficients"])
    return {
        "flat_input_file_count": len(input_files),
        "input_files": list(input_files),
        "corpus_row_count": len(resolved["events"]),
        "admitted_row_count": len(admission["admitted"]),
        "replayed_row_count": admission["replayed"],
        "quarantined_row_count": admission["quarantined"],
        "withdrawn_row_count": admission["withdrawn"],
        "scenario_checks": [
            {
                "scenario": scenario,
                "event_count": results[scenario]["event_count"],
                "unique_accounts": len(results[scenario]["account_totals"]),
                "checksum": results[scenario]["checksum"],
            }
            for scenario in SCENARIOS_IN_REPORT_ORDER
        ],
    }


def build_artifacts(data_dir: str, out_dir: str, observed_relative_median: float) -> dict[str, Any]:
    """Resolve the chain, recompute every scenario, and write all ten artifacts.

    The measured ratio arrives as an argument so this module never reads a clock.
    """
    data_path = Path(data_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    resolved = resolve_inputs(data_path)
    results = compute_all_scenarios(resolved)

    for scenario in SCENARIOS_IN_REPORT_ORDER:
        write_sorted_json(
            out_path / f"scenario_{scenario}.json",
            scenario_artifact(scenario, results[scenario], resolved),
        )
    write_sorted_json(out_path / "perf_report.json", performance_artifact(resolved, observed_relative_median))
    write_sorted_json(out_path / "bottleneck_analysis.json", bottleneck_artifact(resolved))
    write_sorted_json(out_path / "recommendations.json", recommendations_artifact(resolved))
    write_sorted_json(
        out_path / "data_quality.json",
        data_quality_artifact(sorted(os.listdir(str(data_path))), results, resolved),
    )

    return results


def main(argv: list[str]) -> int:
    arguments = argv[1:]
    if len(arguments) != 2:
        sys.stderr.write("usage: optimize.py EVENTS_FILE RULES_JSON\n")
        return 2
    print(json.dumps(aggregate(arguments[0], arguments[1]), sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
