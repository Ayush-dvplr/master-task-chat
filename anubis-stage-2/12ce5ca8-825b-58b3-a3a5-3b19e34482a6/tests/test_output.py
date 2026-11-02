"""Verifier for the 12ce5ca8-825b-58b3-a3a5-3b19e34482a6 performance task.

The checker derives every graded value independently. It regenerates the
load-bearing corpus in a private temporary directory from a fixed canonical
seed, resolves the same fuzzy dependency chain the agent must resolve, and
computes the corrected rollup artifacts in-process. It never reads /app/data,
so it is safe under separate-mode grading where the data tree is absent.

Speed is gated only by stable relative repeated medians against a deliberately
slow stdlib baseline. No absolute host-speed threshold is used.

Test polarity for negative-weight tests: the assertion HOLDS when the cheat is
present. Honest agent -> assertion fails -> negative weight not added.
"""

# === CANON_MATH BLOCK START ===
# The verifier's own derivation of the contract's arithmetic. The oracle under
# solution/ implements the same contract independently, so agreement between the
# two is evidence rather than tautology. Stdlib only. No network, no test reads.
from __future__ import annotations

import csv
import json
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any

EVENT_FIELDS = ["id", "ts", "account", "region", "kind", "amount", "units", "latency_ms", "flag", "meter", "energy_wh"]


def half_up(numerator: int, denominator: int) -> int:
    """Round-half-up (away from zero on ties) integer division as a Decimal."""
    q = (Decimal(int(numerator)) / Decimal(int(denominator))).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    return int(q)


def _alias_map(rules: dict[str, Any], key: str, upper: bool) -> dict[str, str]:
    clean = (lambda value: str(value).strip().upper()) if upper else (lambda value: str(value).strip().lower())
    return {clean(source): clean(target) for source, target in (rules.get(key) or {}).items()}


def _normalise(raw: list[str], rules: dict[str, Any] | None = None) -> dict[str, str]:
    """Section 3a step 1: normalise fields, then apply one alias lookup."""
    rules = rules or {}
    row = {k: v.strip() for k, v in zip(EVENT_FIELDS, raw)}
    row["id"] = row["id"].lower()
    row["account"] = row["account"].upper()
    row["region"] = row["region"].lower()
    row["kind"] = row["kind"].lower()
    row["flag"] = row["flag"].lower()
    row["account"] = _alias_map(rules, "account_aliases", True).get(row["account"], row["account"])
    row["region"] = _alias_map(rules, "region_aliases", False).get(row["region"], row["region"])
    row["kind"] = _alias_map(rules, "kind_aliases", False).get(row["kind"], row["kind"])
    row["flag"] = _alias_map(rules, "flag_aliases", False).get(row["flag"], row["flag"])
    return row


def admit_rows(raw_rows, kind_weights, void_flag=None, rules=None) -> tuple[list[dict[str, str]], int, int, int]:
    """Section 3a admission, including forward and trailing void notices."""
    seen: set[str] = set()
    candidates: dict[str, tuple[int, dict[str, str]]] = {}
    void_ids: set[str] = set()
    replayed = 0
    for position, raw in enumerate(raw_rows):
        row = _normalise(raw, rules)
        first = row["id"] not in seen
        if first:
            seen.add(row["id"])
        else:
            replayed += 1
            if void_flag is not None and row["flag"] == void_flag:
                void_ids.add(row["id"])
            continue
        candidates.setdefault(row["id"], (position, row))
    admitted = []
    quarantined = withdrawn = 0
    for rid, (position, row) in candidates.items():
        if row["kind"] not in kind_weights:
            quarantined += 1
        elif rid in void_ids:
            withdrawn += 1
        else:
            admitted.append((position, row))
    admitted.sort(key=lambda item: item[0])
    return [row for _position, row in admitted], replayed, quarantined, withdrawn


def _raw_tiers(rules: dict[str, Any]) -> list[tuple[int, Any]]:
    tiers = rules.get("tariff_tiers")
    if tiers is None:
        return [(0, int(rules["tariff_bps"]))]
    return sorted(((int(start), None if bps is None else int(bps)) for start, bps in tiers), key=lambda x: x[0])


def tariff_tiers(rules: dict[str, Any]) -> list[tuple[int, int]]:
    """Section 4: tiers sorted by start; absent tiers mean one tier at tariff_bps.
    Section 4c: a tier rate given as null is the smallest bps >= 0 that makes
    every cost control come out exactly."""
    tiers = _raw_tiers(rules)
    missing = [i for i, (_s, b) in enumerate(tiers) if b is None]
    if not missing:
        return tiers
    controls = (rules.get("calibration") or {})["cost"]
    i = missing[0]
    def with_missing_rate(rate):
        rebuilt = []
        for position, (start, published_rate) in enumerate(tiers):
            rebuilt.append((start, rate if position == i else published_rate))
        return rebuilt

    calibration = controls[0]
    wanted = int(calibration["cost_cents"])

    def first_control_cost(rate):
        return tiered_cost(int(calibration["usage_wh"]), with_missing_rate(rate),
                           int(calibration["pre_wh"]))

    ceiling = 1
    while first_control_cost(ceiling) < wanted:
        ceiling <<= 1
    floor = 0
    while floor != ceiling:
        probe = (floor + ceiling) // 2
        if first_control_cost(probe) >= wanted:
            ceiling = probe
        else:
            floor = probe + 1
    while True:
        rebuilt = with_missing_rate(floor)
        outcomes = [tiered_cost(int(item["usage_wh"]), rebuilt, int(item["pre_wh"]))
                    for item in controls]
        if outcomes == [int(item["cost_cents"]) for item in controls]:
            return rebuilt
        floor += 1


def unit_divisor(rules: dict[str, Any]) -> int:
    """Section 4c: given, or the smallest D >= 1 reproducing every energy control."""
    if rules.get("unit_divisor") is not None:
        return int(rules["unit_divisor"])
    controls = (rules.get("calibration") or {})["energy"]
    d = 1
    while not all(half_up(int(c["usage_wh"]), d) == int(c["energy_kwh"]) for c in controls):
        d += 1
        if d > 10 ** 7:
            raise ValueError("no unit_divisor reproduces every energy control")
    return d


def tiered_cost(usage: int, tiers: list[tuple[int, int]], pre: int = 0) -> int:
    """Bill the cumulative range [pre, pre + usage) at the tiers it occupies."""
    lo, hi = pre, pre + usage
    numerator = 0
    for i, (start, bps) in enumerate(tiers):
        end = tiers[i + 1][0] if i + 1 < len(tiers) else None
        a = max(lo, start)
        b = hi if end is None else min(hi, end)
        if b > a:
            numerator += (b - a) * bps
    return half_up(numerator, 10000)


def seed_overrides(rules: dict[str, Any]) -> dict[str, int]:
    raw = rules.get("meter_seed_overrides") or {}
    return {str(k).strip().upper(): int(v) for k, v in raw.items()}


def _seed_for(account: str, rules: dict[str, Any]) -> int:
    overrides = seed_overrides(rules)
    if account in overrides:
        return overrides[account]
    matches = [(len(key) - 1, key, value) for key, value in overrides.items()
               if key.endswith("*") and account.startswith(key[:-1])]
    if matches:
        _length, _key, value = sorted(matches, key=lambda item: (-item[0], item[1]))[0]
        return value
    return int(rules["meter_seed"])


def _account_int_map(rules: dict[str, Any], key: str) -> dict[str, int]:
    return {str(account).strip().upper(): int(value)
            for account, value in (rules.get(key) or {}).items()}


def _account_tiers(rules: dict[str, Any], account: str) -> list[tuple[int, int]]:
    profiles = {str(key).strip().upper(): value
                for key, value in (rules.get("account_tariff_tiers") or {}).items()}
    if account not in profiles:
        return tariff_tiers(rules)
    return sorted((int(start), int(bps)) for start, bps in profiles[account])


def _id_number(value: str) -> int:
    import re
    match = re.search(r"([0-9]+)$", value)
    if match is None:
        raise ValueError("event id has no decimal suffix")
    return int(match.group(1))


def _score(row: dict[str, str], rules: dict[str, Any]) -> int:
    return (
        int(row["amount"]) * int(row["units"]) * int(rules["kind_weights"][row["kind"]])
        + int(rules["region_offsets"].get(row["region"], 0))
        - int(rules["flag_penalties"].get(row["flag"], 0))
        - int(row["latency_ms"]) // 10
    )


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _void_flag(rules: dict[str, Any]):
    flag = rules.get("void_flag")
    return None if flag is None else str(flag).strip().lower()


def _read_raw(events_path: Path) -> list[list[str]]:
    """Header-driven read (section 3): the extension picks the format (.csv
    comma, .psv pipe, .ndjson one JSON object per line); optional BOM, any column
    order, extra columns ignored, blank lines skipped. Returns rows in
    EVENT_FIELDS order."""
    path = Path(events_path)
    if path.suffix == ".ndjson":
        out = []
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            obj = {str(key).strip().lower(): value for key, value in json.loads(line).items()}
            out.append([str(obj[f]) for f in EVENT_FIELDS])
        return out
    delimiter = "|" if path.suffix == ".psv" else ","
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.reader(fh, delimiter=delimiter)
        header = [h.strip().lower() for h in next(reader)]
        index = [header.index(f) for f in EVENT_FIELDS]
        return [[r[i] for i in index] for r in reader if r and any(c.strip() for c in r)]


def aggregate(events_path: Any, rules_path: Any) -> dict[str, Any]:
    """Fast single-structural-pass corrected rollup engine."""
    rules = _load_json(Path(rules_path))
    ws = int(rules["window_start"])
    we = int(rules["window_end"])
    modulus = int(rules["meter_modulus"])
    seed = int(rules["meter_seed"])
    divisor = unit_divisor(rules)
    tiers = tariff_tiers(rules)
    overrides = seed_overrides(rules)
    admitted, _rep, _quar, _wd = admit_rows(
        _read_raw(Path(events_path)), rules["kind_weights"], _void_flag(rules), rules)
    account_totals: dict[str, int] = defaultdict(int)
    region_totals: dict[str, int] = defaultdict(int)
    kind_totals: dict[str, int] = defaultdict(int)
    flag_counts: dict[str, int] = defaultdict(int)
    per_account: dict[str, list[tuple[int, str]]] = defaultdict(list)
    prior: dict[str, int] = {}
    pre_rows: dict[str, list[tuple[int, str]]] = defaultdict(list)
    checksum = 0
    event_count = 0
    for row in admitted:
        ts = int(row["ts"])
        acc = row["account"]
        if ts >= we:
            continue
        score = _score(row, rules)
        if ts < ws:
            meter = int(row["meter"])
            pre_rows[acc].append((meter, row["flag"]))
            prior[acc] = meter
            continue
        event_count += 1
        account_totals[acc] += score
        region_totals[row["region"]] += score
        kind_totals[row["kind"]] += score
        flag_counts[row["flag"]] += 1
        per_account[acc].append((int(row["meter"]), row["flag"]))
        checksum = (checksum * 1315423911 + score * event_count + _id_number(row["id"])) & 0xFFFFFFFF
    usage_wh: dict[str, int] = {}
    energy_kwh: dict[str, int] = {}
    cost_cents: dict[str, int] = {}
    for acc, items in per_account.items():
        prev = prior.get(acc, _seed_for(acc, rules))
        modulus_for_account = _account_int_map(rules, "account_meter_modulus").get(acc, modulus)
        reset_flag = str(rules.get("meter_reset_flag") or "").strip().lower()
        usage = 0
        for meter, flag in items:
            if flag != reset_flag:
                usage += (meter - prev) % modulus_for_account
            prev = meter
        usage_wh[acc] = usage
        divisor_for_account = _account_int_map(rules, "account_unit_divisor").get(acc, divisor)
        energy_kwh[acc] = half_up(usage, divisor_for_account)
        walk_from = _seed_for(acc, rules)
        pre = 0
        for meter, flag in pre_rows[acc]:
            if flag != reset_flag:
                pre += (meter - walk_from) % modulus_for_account
            walk_from = meter
        credit = _account_int_map(rules, "account_tariff_credit_wh").get(acc, 0)
        cost_cents[acc] = tiered_cost(usage, _account_tiers(rules, acc), max(0, pre - credit))
    top = sorted(account_totals.items(), key=lambda kv: (-kv[1], kv[0]))[: int(rules.get("top_n", 5))]
    result = {
        "label": str(rules["label"]),
        "window": [ws, we],
        "event_count": event_count,
        "account_totals": dict(sorted(account_totals.items())),
        "region_totals": dict(sorted(region_totals.items())),
        "kind_totals": dict(sorted(kind_totals.items())),
        "flag_counts": dict(sorted(flag_counts.items())),
        "account_usage_wh": dict(sorted(usage_wh.items())),
        "account_energy_kwh": dict(sorted(energy_kwh.items())),
        "account_cost_cents": dict(sorted(cost_cents.items())),
        "top_accounts": [[k, v] for k, v in top],
        "checksum": checksum,
    }
    return result


def expected_report(events_path: Any, rules_path: Any) -> dict[str, Any]:
    """Slow, deliberately redundant twin. Logically identical to aggregate()."""
    rules = _load_json(Path(rules_path))
    admitted, _rep, _quar, _wd = admit_rows(
        _read_raw(Path(events_path)), rules["kind_weights"], _void_flag(rules), rules)
    ws = int(rules["window_start"])
    we = int(rules["window_end"])
    settled = []
    for row in admitted:
        if int(row["ts"]) >= we:
            continue
        score = _score(row, rules)
        if int(row["ts"]) >= ws:
            settled.append((row, score))
    rows = [row for row, _score_value in settled]
    accounts = sorted({r["account"] for r in rows})
    regions = sorted({r["region"] for r in rows})
    kinds = sorted({r["kind"] for r in rows})
    flags = sorted({r["flag"] for r in rows})
    account_totals = {k: sum(score for r, score in settled if r["account"] == k) for k in accounts}
    region_totals = {k: sum(score for r, score in settled if r["region"] == k) for k in regions}
    kind_totals = {k: sum(score for r, score in settled if r["kind"] == k) for k in kinds}
    flag_counts = {k: sum(1 for r in rows if r["flag"] == k) for k in flags}
    checksum = 0
    for idx, (row, score) in enumerate(settled, 1):
        checksum = (checksum * 1315423911 + score * idx + _id_number(row["id"])) & 0xFFFFFFFF
    divisor = unit_divisor(rules)
    modulus = int(rules["meter_modulus"])
    usage_wh = {}
    for k in accounts:
        before = [r for r in admitted if r["account"] == k and int(r["ts"]) < ws]
        prev = int(before[-1]["meter"]) if before else _seed_for(k, rules)
        account_modulus = _account_int_map(rules, "account_meter_modulus").get(k, modulus)
        reset_flag = str(rules.get("meter_reset_flag") or "").strip().lower()
        usage = 0
        for r in (r for r in rows if r["account"] == k):
            if r["flag"] != reset_flag:
                usage += (int(r["meter"]) - prev) % account_modulus
            prev = int(r["meter"])
        usage_wh[k] = usage
    account_divisors = _account_int_map(rules, "account_unit_divisor")
    energy_kwh = {k: half_up(usage_wh[k], account_divisors.get(k, divisor)) for k in accounts}
    cost_cents = {}
    for k in accounts:
        before = [r for r in admitted if r["account"] == k and int(r["ts"]) < ws]
        walk_from = _seed_for(k, rules)
        account_modulus = _account_int_map(rules, "account_meter_modulus").get(k, modulus)
        reset_flag = str(rules.get("meter_reset_flag") or "").strip().lower()
        pre = 0
        for r in before:
            if r["flag"] != reset_flag:
                pre += (int(r["meter"]) - walk_from) % account_modulus
            walk_from = int(r["meter"])
        credit = _account_int_map(rules, "account_tariff_credit_wh").get(k, 0)
        cost_cents[k] = tiered_cost(usage_wh[k], _account_tiers(rules, k), max(0, pre - credit))
    top = sorted(account_totals.items(), key=lambda kv: (-kv[1], kv[0]))[: int(rules.get("top_n", 5))]
    result = {
        "label": str(rules["label"]),
        "window": [int(rules["window_start"]), int(rules["window_end"])],
        "event_count": len(rows),
        "account_totals": account_totals,
        "region_totals": region_totals,
        "kind_totals": kind_totals,
        "flag_counts": flag_counts,
        "account_usage_wh": usage_wh,
        "account_energy_kwh": energy_kwh,
        "account_cost_cents": cost_cents,
        "top_accounts": [[k, v] for k, v in top],
        "checksum": checksum,
    }
    return result
# === CANON_MATH BLOCK END ===

import threading

from rewardkit import criteria, criterion

# rewardkit may run criteria on parallel threads. The checks share lazily built
# state (_EXPECTED_CACHE, _VISIBLE_INPUTS) and the speed check times the
# submission against a baseline, so concurrent checks would race on that state
# and skew the timing. One global lock makes every check run on its own.
_CHECK_LOCK = threading.Lock()


def _pass(thunk):
    with _CHECK_LOCK:
        try:
            thunk()
            return True
        except Exception:
            return False

# === CHAIN BLOCK START ===
# The verifier's own deterministic dependency-chain resolver + artifact builder,
# written independently of the oracle's. Stdlib only. Reads a data directory,
# resolves the fuzzy dependency chain to the authoritative corpus and active
# coefficient generation, then computes the corrected rollup artifacts.
import os
import sqlite3
import sys
import tempfile

SCENARIO_ORDER = ["visible", "peak", "steady", "burst", "latency"]
CONFIG_ROLES = ("baseline", "cost", "hardware", "queryplan", "indexcfg", "thresholds")


def _entrypoint_target(data_dir):
    text = (Path(data_dir) / "ingest_handoff_notes.txt").read_text(encoding="utf-8")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("catalog_ref:"):
            return stripped.split(":", 1)[1].strip()
    raise ValueError("no catalog_ref in entrypoint")


def _catalog_lookup(data_dir, catalog_name, key):
    con = sqlite3.connect(str(Path(data_dir) / catalog_name))
    try:
        cur = con.execute("SELECT target FROM catalog WHERE key = ?", (key,))
        row = cur.fetchone()
    finally:
        con.close()
    if row is None:
        raise ValueError("catalog key missing: " + key)
    return row[0]


def _read_ledger(data_dir, ledger_name):
    path = Path(data_dir) / ledger_name
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        return list(reader)


def _resolve_role(ledger_rows, role):
    """Active + highest integer generation wins. Draft and superseded are excluded."""
    candidates = [
        r for r in ledger_rows
        if r["role"] == role and r["state"] == "active"
    ]
    if not candidates:
        raise ValueError("no active binding for role: " + role)
    candidates.sort(key=lambda r: int(r["generation"]))
    return candidates[-1]["file"]


def _read_segment_shards(data_dir, manifest_name):
    entries = []
    with (Path(data_dir) / manifest_name).open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            if entry.get("superseded"):
                continue
            entries.append(entry)
    entries.sort(key=lambda e: int(e["sequence"]))
    rows = []
    for entry in entries:
        rows.extend(_read_raw(Path(data_dir) / entry["file"]))
    return rows


_XLSX_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
            "p": "http://schemas.openxmlformats.org/package/2006/relationships"}
_DOCX_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def _xlsx_sheets(path):
    """Return {sheet name: rows of cell strings} from an xlsx workbook (stdlib)."""
    import zipfile
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as zf:
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        target = {r.get("Id"): r.get("Target") for r in rels.findall("p:Relationship", _XLSX_NS)}
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            shared = ["".join(x.text or "" for x in si.iter("{%s}t" % _XLSX_NS["m"])) for si in sst.findall("m:si", _XLSX_NS)]
        out = {}
        for sheet in wb.find("m:sheets", _XLSX_NS).findall("m:sheet", _XLSX_NS):
            rid = sheet.get("{%s}id" % _XLSX_NS["r"])
            xml = ET.fromstring(zf.read("xl/" + target[rid].lstrip("/").replace("xl/", "", 1)))
            rows = []
            for row in xml.iter("{%s}row" % _XLSX_NS["m"]):
                cells = []
                for c in row.findall("m:c", _XLSX_NS):
                    kind = c.get("t")
                    if kind == "inlineStr":
                        cells.append("".join(x.text or "" for x in c.iter("{%s}t" % _XLSX_NS["m"])))
                    elif kind == "s":
                        cells.append(shared[int(c.find("m:v", _XLSX_NS).text)])
                    else:
                        v = c.find("m:v", _XLSX_NS)
                        cells.append("" if v is None else v.text)
                rows.append(cells)
            out[sheet.get("name")] = rows
        return out


def _select_tier_sheet(sheets):
    """Section 4: latest non-draft sheet named tiers_<year>Q<quarter>."""
    import re as _re
    best = None
    for name in sheets:
        m = _re.fullmatch(r"tiers_(\d{4})Q([1-4])", name)
        if m:
            key = (int(m.group(1)), int(m.group(2)))
            if best is None or key > best[0]:
                best = (key, name)
    rows = sheets[best[1]]
    return [[int(float(r[0])), None if r[1].strip().lower() == "calibrate" else int(float(r[1]))]
            for r in rows[1:] if len(r) >= 2 and r[0] != "" and r[1] != ""]


def _docx_table(path):
    import zipfile
    import xml.etree.ElementTree as ET
    with zipfile.ZipFile(path) as zf:
        doc = ET.fromstring(zf.read("word/document.xml"))
    table = doc.find(".//w:tbl", _DOCX_NS)
    rows = []
    for tr in table.findall("w:tr", _DOCX_NS):
        rows.append(["".join(t.text or "" for t in tc.iter("{%s}t" % _DOCX_NS["w"])) for tc in tr.findall("w:tc", _DOCX_NS)])
    return rows


def _amend_overrides(overrides, table):
    out = {str(k).strip().upper(): int(v) for k, v in overrides.items()}
    for account, seed in table[1:]:
        key = account.strip().upper()
        if seed.strip().lower() == "remove":
            out.pop(key, None)
        else:
            out[key] = int(seed.strip())
    return out


def _yaml_flat(path):
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        out[key.strip().strip("\"'")] = value.strip().strip("\"'")
    return out


def _region_table(path):
    con = sqlite3.connect(str(path))
    try:
        rows = con.execute("SELECT region, offset FROM region_offsets WHERE state = 'active' ORDER BY region").fetchall()
    finally:
        con.close()
    return {str(region).strip().lower(): int(offset) for region, offset in rows}


def resolve_chain(data_dir):
    data_dir = Path(data_dir)
    catalog_name = _entrypoint_target(data_dir)
    ledger_name = _catalog_lookup(data_dir, catalog_name, "binding_registry")
    ledger_rows = _read_ledger(data_dir, ledger_name)
    coeff_file = _resolve_role(ledger_rows, "coeff")
    coeffs = _load_json(data_dir / coeff_file)
    segments_manifest = _resolve_role(ledger_rows, "segments")
    events = _read_segment_shards(data_dir, segments_manifest)
    seeds_file = _resolve_role(ledger_rows, "meterseeds")
    overrides = _load_json(data_dir / seeds_file)["overrides"]
    overrides = _amend_overrides(overrides, _docx_table(data_dir / _resolve_role(ledger_rows, "seedaddendum")))
    # Source precedence: the dedicated roles win over the coefficient file's copies.
    coeffs = dict(
        coeffs,
        meter_seed_overrides=overrides,
        region_offsets=_region_table(data_dir / _resolve_role(ledger_rows, "regions")),
        tariff_tiers=_select_tier_sheet(_xlsx_sheets(data_dir / _resolve_role(ledger_rows, "tariff"))),
        void_flag=_yaml_flat(data_dir / _resolve_role(ledger_rows, "policy"))["void_flag"],
        calibration=_load_json(data_dir / _resolve_role(ledger_rows, "calibration")),
    )
    config = {}
    for role in CONFIG_ROLES:
        config_file = _resolve_role(ledger_rows, role)
        config[role] = _load_json(data_dir / config_file)
    return {
        "events": events,
        "coeffs": coeffs,
        "config": config,
        "source_label": coeff_file + "+" + segments_manifest,
    }


def _scenario_rules(coeffs, window):
    rules = {
        "label": coeffs["label"],
        "window_start": int(window[0]),
        "window_end": int(window[1]),
        "kind_weights": coeffs["kind_weights"],
        "region_offsets": coeffs["region_offsets"],
        "flag_penalties": coeffs["flag_penalties"],
        "top_n": int(coeffs["top_n"]),
        "meter_modulus": int(coeffs["meter_modulus"]),
        "meter_seed": int(coeffs["meter_seed"]),
        "tariff_bps": int(coeffs["tariff_bps"]),
        "tariff_tiers": coeffs["tariff_tiers"],
        "meter_seed_overrides": coeffs["meter_seed_overrides"],
        "calibration": coeffs["calibration"],
        "void_flag": coeffs["void_flag"],
    }
    for key in (
        "account_aliases", "region_aliases", "kind_aliases", "flag_aliases",
        "account_meter_modulus", "account_unit_divisor", "account_tariff_tiers",
        "account_tariff_credit_wh", "meter_reset_flag",
    ):
        if key in coeffs:
            rules[key] = coeffs[key]
    return rules


def _metrics(result):
    total_score = sum(result["account_totals"].values())
    event_count = result["event_count"]
    average = round(total_score / event_count, 3) if event_count else 0.0
    if result["top_accounts"]:
        top_account = result["top_accounts"][0][0]
        top_account_score = result["top_accounts"][0][1]
    else:
        top_account = ""
        top_account_score = 0
    return {
        "average_score": average,
        "top_account": top_account,
        "top_account_score": top_account_score,
        "total_score": total_score,
    }


def _compute_scenarios(resolved):
    coeffs = resolved["coeffs"]
    windows = coeffs["scenario_windows"]
    tmp = Path(tempfile.mkdtemp(prefix="rollup_"))
    corpus = tmp / "corpus.csv"
    with corpus.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(EVENT_FIELDS)
        for r in resolved["events"]:
            w.writerow(r)
    results = {}
    for name in SCENARIO_ORDER:
        rules_s = _scenario_rules(coeffs, windows[name])
        rules_path = tmp / ("rules_%s.json" % name)
        rules_path.write_text(json.dumps(rules_s, sort_keys=True), encoding="utf-8")
        results[name] = aggregate(str(corpus), str(rules_path))
    return results


def _scenario_payload(name, result, resolved):
    thresholds = resolved["config"]["thresholds"]
    return {
        "scenario": name,
        "source": resolved["source_label"],
        "result": result,
        "metrics": _metrics(result),
        "thresholds": {
            "max_relative_median": thresholds["max_relative_median"],
            "max_latency_warning_ms": thresholds["max_latency_warning_ms"],
        },
    }


def _perf_report(resolved, observed_relative_median):
    config = resolved["config"]
    return {
        "ok": True,
        "module": "/app/out/optimize.py",
        "benchmark_method": "repeated in-process median of aggregate vs baseline rescan engine",
        "observed_relative_median": observed_relative_median,
        "relative_target": config["thresholds"]["max_relative_median"],
        "scenario_count": 5,
        "artifact_count": 10,
        "scenarios": list(SCENARIO_ORDER),
        "baseline_name": config["baseline"]["baseline_name"],
        "hardware_profile": config["hardware"]["profile_name"],
    }


def _bottleneck(resolved):
    config = resolved["config"]
    qp = config["queryplan"]
    by_scenario = qp["baseline_median_ms_by_scenario"]
    highest = min(by_scenario.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return {
        "primary_bottleneck": "per_key_rescan",
        "baseline_complexities": qp["baseline_stages"],
        "optimized_complexities": qp["optimized_stages"],
        "baseline_median_ms_by_scenario": dict(sorted(by_scenario.items())),
        "highest_baseline_scenario": highest,
    }


def _recommendations(resolved):
    config = resolved["config"]
    idx = config["indexcfg"]
    return {
        "group_keys": idx["group_keys"],
        "top_accounts_order": idx["top_accounts_order"],
        "materialized_outputs": idx["materialized_outputs"],
        "estimated_rewrite_fixed_cost": config["cost"]["estimated_rewrite_fixed_cost"],
        "recommendations": [
            "resolve the active coefficient generation before scoring",
            "apply the half-open window and rollover-safe meter usage",
            "round energy and tariff once per account at the end",
        ],
    }


def _data_quality(input_files, scenario_results, resolved):
    admitted, replayed, quarantined, withdrawn = admit_rows(
        resolved["events"], resolved["coeffs"]["kind_weights"],
        str(resolved["coeffs"]["void_flag"]).strip().lower(), resolved["coeffs"])
    checks = []
    for name in SCENARIO_ORDER:
        r = scenario_results[name]
        checks.append({
            "scenario": name,
            "event_count": r["event_count"],
            "unique_accounts": len(r["account_totals"]),
            "checksum": r["checksum"],
        })
    return {
        "flat_input_file_count": len(input_files),
        "input_files": list(input_files),
        "corpus_row_count": len(resolved["events"]),
        "admitted_row_count": len(admitted),
        "replayed_row_count": replayed,
        "quarantined_row_count": quarantined,
        "withdrawn_row_count": withdrawn,
        "scenario_checks": checks,
    }
# === CHAIN BLOCK END ===

# === GEN BLOCK START ===
# Deterministic load-bearing corpus generator. It reproduces the shipped
# /app/data corpus from the canonical seed so grading never reads that tree.
# Never shipped inside the submission module. Stdlib only.
GEN_ACCOUNTS = 90
GEN_MODULUS = 20000
GEN_METER_SEED = 7
GEN_EVENTS = 2640
GEN_SHARDS = 12
GEN_KINDS = ["alpha", "beta", "gamma", "delta", "epsilon"]
GEN_REGIONS = ["north", "south", "east", "west", "central"]
GEN_FLAGS = ["ok", "review", "hold", "late"]

ENTRYPOINT_NAME = "ingest_handoff_notes.txt"
CATALOG_NAME = "rollup_catalog_idx.sqlite"
LEDGER_NAME = "binding_ledger_rev.tsv"
COEFF_ACTIVE = "coeff_rollup_g11.json"
SEGMENT_MANIFEST = "segment_manifest_v.jsonl"
SEEDS_ACTIVE = "meter_seed_overrides_g10.json"
REGIONS_ACTIVE = "region_registry.sqlite"
TARIFF_BOOK = "tariff_book.xlsx"
SEED_ADDENDUM = "meter_seed_addendum.docx"
POLICY_ACTIVE = "admission_policy.yaml"
CALIBRATION_ACTIVE = "calibration_controls.json"


def calibration_controls(divisor, tiers, energy_usages, cost_cases):
    """Controls with known outputs, computed from intended parameter values.
    The contract defines the recovered value as the smallest one reproducing
    every control, so the verifier always recovers by search, never by reading
    the intended value."""
    return {
        "energy": [{"usage_wh": u, "energy_kwh": half_up(u, divisor)} for u in energy_usages],
        "cost": [{"pre_wh": pre, "usage_wh": u, "cost_cents": tiered_cost(u, sorted(tiers), pre)}
                 for pre, u in cost_cases],
    }


CANON_CALIBRATION = calibration_controls(
    1024, [(0, 1500), (12000, 2230), (40000, 3050)],
    [374770, 52130, 98765, 15999], [(0, 30000), (5000, 20000), (11000, 3000), (0, 39999), (39000, 500)])
OLD_CALIBRATION = calibration_controls(
    1000, [(0, 1500), (12000, 2200), (40000, 3050)],
    [374770, 52130, 98765], [(0, 30000), (5000, 20000)])

_ZIP_DATE = (2026, 1, 14, 0, 0, 0)


def _zip_write(path, members):
    import zipfile
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in members:
            info = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, text)


def _xml_escape(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _write_xlsx(path, sheets, *, absolute_targets=False, cell_refs=True, shared_text=False):
    """Minimal stdlib xlsx: inline strings and numbers, one part per sheet.
    Options reproduce other valid writers: absolute relationship targets
    (/xl/worksheets/...), cells without an r attribute, and every value
    (numbers included) stored as text in a shared-strings part."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rns = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    members = [
        ("[Content_Types].xml",
         '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
         '<Default Extension="xml" ContentType="application/xml"/>'
         '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
         + "".join('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % (i + 1) for i in range(len(sheets)))
         + "</Types>"),
        ("_rels/.rels",
         '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>'),
        ("xl/workbook.xml",
         '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="%s" xmlns:r="%s"><sheets>' % (ns, rns)
         + "".join('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (_xml_escape(n), i + 1, i + 1) for i, (n, _r) in enumerate(sheets))
         + "</sheets></workbook>"),
        ("xl/_rels/workbook.xml.rels",
         '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         + "".join('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="%sworksheets/sheet%d.xml"/>' % (i + 1, "/xl/" if absolute_targets else "", i + 1) for i in range(len(sheets)))
         + "</Relationships>"),
    ]
    shared: list[str] = []
    for i, (_name, rows) in enumerate(sheets):
        body = []
        for r, row in enumerate(rows, 1):
            cells = []
            for c, value in enumerate(row):
                ref = (' r="%s%d"' % ("ABCDEFGH"[c], r)) if cell_refs else ""
                if shared_text:
                    shared.append(str(value))
                    cells.append('<c%s t="s"><v>%d</v></c>' % (ref, len(shared) - 1))
                elif isinstance(value, int):
                    cells.append('<c%s><v>%d</v></c>' % (ref, value))
                else:
                    cells.append('<c%s t="inlineStr"><is><t>%s</t></is></c>' % (ref, _xml_escape(value)))
            body.append(('<row r="%d">%s</row>' % (r, "".join(cells))) if cell_refs else ("<row>%s</row>" % "".join(cells)))
        members.append(("xl/worksheets/sheet%d.xml" % (i + 1),
                        '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="%s"><sheetData>%s</sheetData></worksheet>' % (ns, "".join(body))))
    if shared_text:
        members.append(("xl/sharedStrings.xml",
                        '<?xml version="1.0" encoding="UTF-8"?><sst xmlns="%s" count="%d" uniqueCount="%d">%s</sst>'
                        % (ns, len(shared), len(shared), "".join("<si><t>%s</t></si>" % _xml_escape(s) for s in shared))))
        members[0] = (members[0][0], members[0][1].replace(
            "</Types>", '<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/></Types>'))
    _zip_write(path, members)


def _write_docx(path, paragraphs, table):
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    para = "".join("<w:p><w:r><w:t xml:space=\"preserve\">%s</w:t></w:r></w:p>" % _xml_escape(p) for p in paragraphs)
    def cell(value):
        runs = value if isinstance(value, list) else [value]
        return "<w:tc><w:p>%s</w:p></w:tc>" % "".join(
            "<w:r><w:t xml:space=\"preserve\">%s</w:t></w:r>" % _xml_escape(run) for run in runs)
    rows = "".join("<w:tr>%s</w:tr>" % "".join(cell(c) for c in row) for row in table)
    _zip_write(path, [
        ("[Content_Types].xml",
         '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
         '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
         '<Default Extension="xml" ContentType="application/xml"/>'
         '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'),
        ("_rels/.rels",
         '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
         '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'),
        ("word/document.xml",
         '<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="%s"><w:body>%s<w:tbl>%s</w:tbl></w:body></w:document>' % (w, para, rows)),
    ])


def _write_heterogeneous_sources(root):
    """Region registry (sqlite), tariff book (xlsx), seed addendum (docx), the
    admission policy (yaml) and their decoys."""
    path = root / REGIONS_ACTIVE
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    try:
        con.execute("CREATE TABLE region_offsets (region TEXT NOT NULL, offset INTEGER NOT NULL, state TEXT NOT NULL)")
        con.executemany("INSERT INTO region_offsets VALUES (?, ?, ?)", [
            ("north", 11, "retired"), ("north", 12, "active"), ("south", 17, "active"),
            ("east", 21, "retired"), ("east", 23, "active"), ("west", 29, "active"),
            ("central", 33, "retired"), ("central", 31, "active"), ("midwest", 40, "draft"),
        ])
        con.commit()
    finally:
        con.close()
    _write_xlsx(root / TARIFF_BOOK, [
        ("readme", [["Tier sheets are named tiers_<year>Q<quarter>; draft sheets end in _draft."]]),
        ("tiers_2025Q3", [["start_wh", "bps"], [0, 1475], [15000, 2150], [45000, 2900]]),
        ("tiers_2025Q4", [["start_wh", "bps"], [40000, 3050], [0, 1500], [12000, "calibrate"]]),
        ("tiers_2026Q1_draft", [["start_wh", "bps"], [0, 1600], [10000, 2400]]),
    ])
    _write_docx(root / SEED_ADDENDUM, [
        "Meter seed addendum 2 (amends meter_seed_overrides_g10.json).",
        "Each row sets the account's seed; the word remove deletes its override.",
    ], [["account", "seed"], [" a011", "2500"], ["A005 ", "7777"], ["a072", "remove"], ["A040", "16500"]])
    (root / CALIBRATION_ACTIVE).write_text(json.dumps(dict(CANON_CALIBRATION, note=(
        "calibration controls generation 2: unit_divisor and the tariff rate marked calibrate are "
        "the smallest values reproducing every control")), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (root / "calibration_controls_old.json").write_text(json.dumps(dict(OLD_CALIBRATION, note=(
        "calibration controls generation 1 (superseded)")), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (root / POLICY_ACTIVE).write_text(
        "# admission policy, generation 3 (active)\nreplay_rule: first_occurrence_wins\nvoid_flag: revoke\n",
        encoding="utf-8")
    (root / "admission_policy_draft.yaml").write_text(
        "# admission policy, generation 4 (DRAFT, not adopted)\nreplay_rule: last_write_wins\nvoid_flag: void\n",
        encoding="utf-8")
    (root / "tariff_schedule_2025.md").write_text(
        "# Tariff schedule 2025 (superseded by the tariff book)\n\n| start_wh | bps |\n|---|---|\n| 0 | 1475 |\n| 15000 | 2150 |\n| 45000 | 2900 |\n",
        encoding="utf-8")


def authoritative_seed_overrides():
    """Generation-10 per-account meter seeds; keys deliberately unnormalised."""
    return {
        "generation": 10,
        "overrides": {
            "A003": 15000, " a011": 18750, "A017 ": 9000, "a024": 19990, "A031": 12345,
            "A038": 4000, " A042 ": 16000, "a047": 19000, "A055": 11111, "A061": 17500,
            "a066": 8888, "A072": 19999, "A079": 14000, " a083": 13000, "A088": 18000,
            "A08*": 4321,
        },
    }


class GenRng:
    __slots__ = ("state",)

    def __init__(self, seed):
        self.state = (seed & 0xFFFFFFFFFFFFFFFF) or 0x9E3779B97F4A7C15

    def _next(self):
        x = self.state
        x ^= (x >> 12) & 0xFFFFFFFFFFFFFFFF
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27) & 0xFFFFFFFFFFFFFFFF
        self.state = x
        return (x * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def rand_int(self, lo, hi):
        return lo + self._next() % (hi - lo + 1)

    def choice(self, seq):
        return seq[self._next() % len(seq)]


def _pad(rng, text):
    return rng.choice(["", " ", "  "]) + text + rng.choice(["", " ", "\t"])


def build_trap_rows(seed, n, *, padded=True, ts_lo=1000, ts_hi=9999, noise=0,
                    replays=0, quarantine=0, unknown_regions=0, ties=0,
                    accounts=GEN_ACCOUNTS, unknown_flags=0, voids=0,
                    id_prefix="e", casefold_replays=False, forward_voids=0,
                    reset_every=0, meter_moduli=None):
    """Seeded raw event rows (lists of strings in EVENT_FIELDS order).

    With every trap count at zero, padded ids and ts in [1000, 9999] this is the
    plain workload. The trap knobs inject, in this order: same-timestamp pairs
    whose ids order differently as strings and as integers (``ties``), rows with
    an unknown kind (``quarantine``), rows with an unknown region
    (``unknown_regions``), rows with an unknown flag (``unknown_flags``), case and
    whitespace noise (``noise``), replayed ids inserted later in the file
    (``replays``), and void notices for earlier ids inserted later still
    (``voids``). A knob left at zero draws nothing from the generator, so the
    canonical corpus does not depend on knobs it never sets."""
    rng = GenRng(seed)
    acct_names = ["A%03d" % i for i in range(accounts)]
    per = {a: GEN_METER_SEED for a in acct_names}
    rows = []
    for i in range(1, n + 1):
        acc = rng.choice(acct_names)
        inc = rng.rand_int(1500, 4000)
        region = rng.choice(GEN_REGIONS)
        kind = rng.choice(GEN_KINDS)
        amount = rng.rand_int(1, 999)
        units = rng.rand_int(1, 17)
        latency = rng.rand_int(0, 250)
        flag = rng.choice(GEN_FLAGS)
        ts = rng.rand_int(ts_lo, ts_hi)
        prev = per[acc]
        modulus = int((meter_moduli or {}).get(acc, GEN_MODULUS))
        meter = (prev + inc) % modulus
        per[acc] = meter
        rid = ((id_prefix + "%06d") % i) if padded else ((id_prefix + "%d") % i)
        rows.append([rid, str(ts), acc, region, kind, str(amount), str(units),
                     str(latency), flag, str(meter), str(meter - prev)])

    # Same-timestamp pairs for one account where string order != integer order.
    made = 0
    attempts = 0
    while made < ties and attempts < ties * 400:
        attempts += 1
        j = rng.rand_int(n // 3, n - 1)
        for i in range(j - 1, -1, -1):
            if rows[i][2] == rows[j][2] and rows[i][0] > rows[j][0]:
                rows[j][1] = rows[i][1]
                made += 1
                break

    quarantined_at = []
    for _ in range(quarantine):
        k = rng.rand_int(0, n - 2)
        rows[k][4] = rng.choice(["omega", "zeta", "Theta", "kappa"])
        quarantined_at.append(k)
    for _ in range(unknown_regions):
        k = rng.rand_int(0, n - 1)
        rows[k][3] = rng.choice(["northeast", "midwest"])
    for _ in range(unknown_flags):
        k = rng.rand_int(0, n - 1)
        rows[k][8] = rng.choice(["escalated", "disputed"])
    for _ in range(noise):
        k = rng.rand_int(0, n - 1)
        field = rng.choice([2, 3, 4, 8])
        value = rows[k][field]
        style = rng.rand_int(0, 2)
        if style == 0:
            value = value.lower() if field == 2 else value.upper()
        elif style == 1:
            value = value.lower() if field == 2 else value.title()
        rows[k][field] = _pad(rng, value)

    if replays:
        scheduled = {}
        for r in range(replays):
            variant = r % 4
            if variant == 3 and quarantined_at:
                src = rng.choice(quarantined_at)
            else:
                src = rng.rand_int(0, n - 2)
            copy = list(rows[src])
            if variant == 1:
                copy[5] = str(rng.rand_int(1, 999))
            elif variant == 2 or int(copy[1].strip()) >= 9000:
                copy[1] = str(rng.rand_int(max(ts_lo, 2000), 8999))
            elif variant == 3:
                copy[4] = "alpha"
                copy[9] = str(rng.rand_int(0, GEN_MODULUS - 1))
            if r % 5 == 0:
                copy[0] = " " + copy[0].strip() + " "
            after = rng.rand_int(src, n - 1)
            scheduled.setdefault(after, []).append(copy)
        merged = []
        for idx, row in enumerate(rows):
            merged.append(row)
            merged.extend(scheduled.get(idx, []))
        rows = merged
    if voids:
        scheduled = {}
        for _ in range(voids):
            src = rng.rand_int(0, len(rows) - 2)
            copy = list(rows[src])
            copy[8] = rng.choice(["revoke", " REVOKE", "Revoke "])
            after = rng.rand_int(src, len(rows) - 1)
            scheduled.setdefault(after, []).append(copy)
        merged = []
        for idx, row in enumerate(rows):
            merged.append(row)
            merged.extend(scheduled.get(idx, []))
        rows = merged
    if casefold_replays:
        seen_ids = set()
        for row in rows:
            key = row[0].strip().lower()
            if key in seen_ids:
                row[0] = row[0].upper()
            else:
                seen_ids.add(key)
    if forward_voids:
        moved = 0
        index = 0
        while index < len(rows) and moved < forward_voids:
            row = rows[index]
            if row[8].strip().lower() == "revoke":
                target = next((n for n, candidate in enumerate(rows)
                               if candidate[0].strip().lower() == row[0].strip().lower()
                               and candidate[8].strip().lower() != "revoke"), None)
                if target is not None and target < index:
                    notice = rows.pop(index)
                    rows.insert(target, notice)
                    moved += 1
                    index = target + 1
                    continue
            index += 1
    if reset_every:
        for index in range(reset_every - 1, len(rows), reset_every):
            rows[index][8] = "reset"
    return rows


def gen_event_rows(seed):
    rows = build_trap_rows(
        seed, GEN_EVENTS, padded=False, ts_lo=600, ts_hi=9999,
        noise=260, replays=72, quarantine=22, unknown_regions=9, ties=14,
        voids=40, id_prefix="event", casefold_replays=True, forward_voids=10,
        reset_every=97,
    )
    replacements = {
        2: {"A005": "legacy-a005", "A017": "legacy-a017"},
        3: {"north": "n-zone", "south": "s-zone"},
        4: {"alpha": "a-type", "beta": "b-type"},
        8: {"ok": "pass", "review": "inspect"},
    }
    for row in rows:
        for position, mapping in replacements.items():
            clean = row[position].strip()
            if clean in mapping:
                row[position] = mapping[clean]
    return rows


def authoritative_coeffs():
    return {
        "label": "ROLLUP-ACTIVE-G11",
        "generation": 11,
        "kind_weights": {"alpha": 3, "beta": 5, "gamma": 7, "delta": 9, "epsilon": 13},
        "region_offsets": {"north": 11, "south": 16, "east": 21, "west": 26, "central": 33},
        "flag_penalties": {"ok": 0, "review": 23, "hold": 41, "late": 17},
        "top_n": 7,
        "meter_modulus": GEN_MODULUS,
        "meter_seed": GEN_METER_SEED,
        "tariff_bps": 1475,
        "tariff_tiers": [[45000, 2900], [0, 1475], [15000, 2150]],
        "scenario_windows": {
            "visible": [1000, 9000],
            "peak": [2000, 4000],
            "steady": [4000, 7000],
            "burst": [7000, 9000],
            "latency": [1000, 5000],
        },
        "account_aliases": {"LEGACY-A005": "A005", "LEGACY-A017": "A017"},
        "region_aliases": {"n-zone": "north", "s-zone": "south"},
        "kind_aliases": {"a-type": "alpha", "b-type": "beta"},
        "flag_aliases": {"pass": "ok", "inspect": "review"},
        "account_unit_divisor": {"A005": 997, "A017": 1111},
        "account_tariff_tiers": {"A005": [[0, 1333], [8000, 2444]]},
        "account_tariff_credit_wh": {"A017": 5000},
        "meter_reset_flag": "reset",
    }


def _config_payloads():
    thresholds = {
        "max_relative_median": 0.70,
        "max_latency_warning_ms": 200,
        "required_fields": [
            "label", "window", "event_count", "account_totals", "region_totals",
            "kind_totals", "flag_counts", "account_usage_wh", "account_energy_kwh",
            "account_cost_cents", "top_accounts", "checksum",
        ],
    }
    baseline_metrics = {
        "baseline_name": "legacy_rollup_v1",
        "baseline_median_relative": 1.0,
        "reference_engine": "single_thread_stdlib",
    }
    cost_model = {
        "estimated_rewrite_fixed_cost": 4200,
        "per_scenario_unit_cost": 17,
        "currency_minor_units": "cents",
    }
    hardware_profile = {
        "cores": 4,
        "memory_gb": 8,
        "profile_name": "reference_node_a",
    }
    query_plan = {
        "baseline_stages": ["scan", "rescan_per_key", "sort", "materialize"],
        "optimized_stages": ["scan", "group", "finalize"],
        "baseline_median_ms_by_scenario": {
            "visible": 41,
            "peak": 22,
            "steady": 33,
            "burst": 19,
            "latency": 28,
        },
    }
    index_config = {
        "group_keys": ["account", "region", "kind", "flag"],
        "top_accounts_order": "score_desc_then_account_asc",
        "materialized_outputs": [
            "scenario_visible", "scenario_peak", "scenario_steady",
            "scenario_burst", "scenario_latency",
        ],
    }
    return {
        "baseline_metrics.json": baseline_metrics,
        "cost_model.json": cost_model,
        "hardware_profile.json": hardware_profile,
        "query_plan.json": query_plan,
        "index_config.json": index_config,
        "thresholds.json": thresholds,
    }


SHUFFLED_FIELDS = ["ts", "id", "meter", "account", "kind", "region", "flag",
                   "units", "amount", "energy_wh", "latency_ms"]


def write_events_file(path, rows, *, shuffled=False, extra=None, bom=False,
                      crlf=False, blank_every=0, padded_header=False,
                      mixed_case_header=False):
    """Write raw rows (EVENT_FIELDS order) as a CSV with optional format quirks:
    a different column order, an extra trailing column, a UTF-8 BOM, CRLF line
    endings, and blank lines."""
    fields = list(SHUFFLED_FIELDS if shuffled else EVENT_FIELDS)
    header = fields + ([extra[0]] if extra else [])
    if Path(path).suffix == ".ndjson":
        with Path(path).open("w", encoding="utf-8") as fh:
            for n, r in enumerate(rows, 1):
                by_name = dict(zip(EVENT_FIELDS, r))
                obj = {(f.upper() if mixed_case_header and n % 2 else f): by_name[f] for f in fields}
                for f in ("ts", "meter"):
                    if by_name[f].strip() == by_name[f]:
                        obj[f] = int(by_name[f])
                if extra:
                    obj[extra[0]] = extra[1](n)
                fh.write(json.dumps(obj) + "\n")
                if blank_every and n % blank_every == 0:
                    fh.write("\n")
        return
    with Path(path).open("w", newline="", encoding="utf-8-sig" if bom else "utf-8") as fh:
        w = csv.writer(fh, delimiter="|" if Path(path).suffix == ".psv" else ",",
                       lineterminator="\r\n" if crlf else "\n")
        if mixed_case_header:
            header = [h.upper() if i % 2 else h.title() for i, h in enumerate(header)]
        w.writerow([(" %s  " % h if i % 2 else " %s" % h) for i, h in enumerate(header)] if padded_header else header)
        for n, r in enumerate(rows, 1):
            by_name = dict(zip(EVENT_FIELDS, r))
            out = [by_name[f] for f in fields]
            if extra:
                out.append(extra[1](n))
            w.writerow(out)
            if blank_every and n % blank_every == 0:
                fh.write("\r\n" if crlf else "\n")


SHARD_FORMATS = {
    2: {"extra": ("note", lambda n: "re-sent, see journal" if n % 7 == 0 else "")},
    3: {"shuffled": True},
    5: {"shuffled": True, "extra": ("ingest_batch", lambda n: "b%02d" % (n % 13))},
    6: {"extra": ("ingest_batch", lambda n: "n%02d" % (n % 11))},
    8: {"bom": True, "mixed_case_header": True},
    10: {"blank_every": 45},
}
SHARD_SUFFIX = {3: ".psv", 6: ".ndjson", 7: ".psv", 11: ".ndjson"}


def _write_shards(root, rows):
    per_shard = (len(rows) + GEN_SHARDS - 1) // GEN_SHARDS
    shard_files = []
    for s in range(GEN_SHARDS):
        chunk = rows[s * per_shard:(s + 1) * per_shard]
        name = "seg_part_%02d%s" % (s, SHARD_SUFFIX.get(s, ".csv"))
        write_events_file(root / name, chunk, **SHARD_FORMATS.get(s, {}))
        shard_files.append(name)
    return shard_files


def _write_catalog(root):
    path = root / CATALOG_NAME
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    try:
        con.execute("CREATE TABLE catalog (key TEXT PRIMARY KEY, target TEXT NOT NULL, note TEXT)")
        con.executemany(
            "INSERT INTO catalog (key, target, note) VALUES (?, ?, ?)",
            [
                ("binding_registry", LEDGER_NAME, "authoritative role bindings"),
                ("stale_registry", "binding_ledger_old.tsv", "superseded do not use"),
                ("scratch", "scratch_notes.txt", "ignore"),
            ],
        )
        con.commit()
    finally:
        con.close()


def _write_ledger(root, shard_files):
    rows = [
        ("coeff", "1", "superseded", "coeff_prior_g1.json"),
        ("coeff", "2", "active", "coeff_hotfix_g2.json"),
        ("coeff", "3", "active", "coeff_active_g3.json"),
        ("coeff", "3", "draft", "coeff_draft_g3.json"),
        ("coeff", "11", "active", COEFF_ACTIVE),
        ("coeff", "12", "draft", "coeff_draft_g12.json"),
        ("segments", "3", "active", SEGMENT_MANIFEST),
        ("meterseeds", "9", "active", "meter_seed_overrides_g9.json"),
        ("meterseeds", "10", "active", SEEDS_ACTIVE),
        ("meterseeds", "11", "draft", "meter_seed_overrides_draft.json"),
        ("segments", "1", "superseded", "segment_manifest_old.jsonl"),
        ("baseline", "3", "active", "baseline_metrics.json"),
        ("cost", "3", "active", "cost_model.json"),
        ("hardware", "3", "active", "hardware_profile.json"),
        ("queryplan", "3", "active", "query_plan.json"),
        ("indexcfg", "3", "active", "index_config.json"),
        ("thresholds", "3", "active", "thresholds.json"),
        ("regions", "4", "active", REGIONS_ACTIVE),
        ("tariff", "6", "superseded", "tariff_schedule_2025.md"),
        ("tariff", "7", "active", TARIFF_BOOK),
        ("seedaddendum", "2", "active", SEED_ADDENDUM),
        ("policy", "3", "active", POLICY_ACTIVE),
        ("policy", "4", "draft", "admission_policy_draft.yaml"),
        ("calibration", "1", "superseded", "calibration_controls_old.json"),
        ("calibration", "2", "active", CALIBRATION_ACTIVE),
    ]
    with (root / LEDGER_NAME).open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(["role", "generation", "state", "file"])
        for r in rows:
            w.writerow(list(r))


def _write_segment_manifest(root, shard_files):
    with (root / SEGMENT_MANIFEST).open("w", encoding="utf-8") as fh:
        fh.write(json.dumps({"file": "seg_part_legacy.csv", "sequence": 99, "superseded": True}) + "\n")
        for i, name in reversed(list(enumerate(shard_files))):
            fh.write(json.dumps({"file": name, "sequence": i, "superseded": False}) + "\n")


def _write_entrypoint(root):
    text = (
        "handoff notes for the rollup recompute\n"
        "status: partial ingest, downstream rollup marked SUSPECT\n"
        "catalog_ref: %s\n"
        "do_not_trust: rollup_summary_prev.json\n"
        "hint_decoys: coeff_hotfix_g2.json, seg_part_legacy.csv\n"
    ) % CATALOG_NAME
    (root / ENTRYPOINT_NAME).write_text(text, encoding="utf-8")


def write_loadbearing_corpus(root, seed):
    """Write ONLY the load-bearing files the chain resolves. Used by the
    verifier to regenerate the corpus in a tempdir (never reads /app/data)."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    rows = gen_event_rows(seed)
    shard_files = _write_shards(root, rows)
    _write_catalog(root)
    _write_heterogeneous_sources(root)
    _write_ledger(root, shard_files)
    _write_segment_manifest(root, shard_files)
    (root / COEFF_ACTIVE).write_text(json.dumps(authoritative_coeffs(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (root / SEEDS_ACTIVE).write_text(json.dumps(authoritative_seed_overrides(), sort_keys=True, indent=2) + "\n", encoding="utf-8")
    for name, payload in _config_payloads().items():
        (root / name).write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    _write_entrypoint(root)
    return root
# === GEN BLOCK END ===

import ast
import importlib.util
import signal
import subprocess
import time
from typing import cast

CANON_SEED = 20260114

OUT_DIR = Path("/app/out")
SUBMISSION = OUT_DIR / "optimize.py"
ARTIFACTS = [
    OUT_DIR / "optimize.py",
    OUT_DIR / "scenario_visible.json",
    OUT_DIR / "scenario_peak.json",
    OUT_DIR / "scenario_steady.json",
    OUT_DIR / "scenario_burst.json",
    OUT_DIR / "scenario_latency.json",
    OUT_DIR / "perf_report.json",
    OUT_DIR / "bottleneck_analysis.json",
    OUT_DIR / "recommendations.json",
    OUT_DIR / "data_quality.json",
]

# Exact sorted census of the shipped /app/data tree. The data_quality artifact
# must report this list; deleting any input file breaks the census and the task.
FILE_MANIFEST = [
    "account_registry.csv",
    "admission_policy.yaml",
    "admission_policy_draft.yaml",
    "archive_index.db",
    "audit_trail.log",
    "baseline_metrics.json",
    "binding_ledger_old.tsv",
    "binding_ledger_rev.tsv",
    "calibration_controls.json",
    "calibration_controls_old.json",
    "checksum_cache.dat",
    "coeff_active_g3.json",
    "coeff_draft_g12.json",
    "coeff_draft_g3.json",
    "coeff_hotfix_g2.json",
    "coeff_prior_g1.json",
    "coeff_rollup_g11.json",
    "coldstore_snapshot.parquet",
    "cost_model.json",
    "energy_export_kwh.tsv",
    "flag_policy_v2.json",
    "hardware_profile.json",
    "index_config.json",
    "ingest_handoff_notes.txt",
    "kind_weights_backup.json",
    "legacy_catalog.db",
    "legacy_window_policy.txt",
    "meter_calibration.dat",
    "meter_readings_raw.csv",
    "meter_seed_addendum.docx",
    "meter_seed_overrides_draft.json",
    "meter_seed_overrides_g10.json",
    "meter_seed_overrides_g9.json",
    "notes_readme.md",
    "offsets_table.bin",
    "ops_bulletin.pdf",
    "pipeline_run.log",
    "quarterly_rollup.xlsx",
    "query_plan.json",
    "reconciliation_hint.md",
    "region_map_alt.tsv",
    "region_registry.sqlite",
    "replay_journal.log",
    "rollup_catalog_idx.sqlite",
    "rollup_summary_prev.json",
    "schema.md",
    "scratch_notes.txt",
    "seg_part_00.csv",
    "seg_part_01.csv",
    "seg_part_02.csv",
    "seg_part_03.psv",
    "seg_part_04.csv",
    "seg_part_05.csv",
    "seg_part_06.ndjson",
    "seg_part_07.psv",
    "seg_part_08.csv",
    "seg_part_09.csv",
    "seg_part_10.csv",
    "seg_part_11.ndjson",
    "seg_part_legacy.csv",
    "segment_manifest_old.jsonl",
    "segment_manifest_v.jsonl",
    "shard_offsets.bin",
    "superseded_expected_rollup.jsonl",
    "tariff_book.xlsx",
    "tariff_schedule_2025.md",
    "tariff_schedule_percent.json",
    "thresholds.json",
    "vendor_delta_dump.csv",
    "windowing_examples.txt",
]

_VISIBLE_EVENTS_TEXT = """id,ts,account,region,kind,amount,units,latency_ms,flag,meter,energy_wh
e0001,1100,A01,north,alpha,17,3,41,ok,2007,2000
e0002,1200,A02,south,beta,29,4,35,ok,2500,2493
e0003,1500,A01,north,alpha,11,2,55,review,4100,2093
e0004,1800,A03,west,gamma,43,1,73,ok,3000,2993
e0005,2100,A02,south,alpha,37,5,28,ok,5200,2700
e0006,2500,A04,east,beta,19,3,62,hold,3300,3293
e0007,3000,A03,west,alpha,23,7,47,ok,6100,3100
e0008,3500,A05,north,gamma,31,2,39,ok,2900,2893
e0009,4000,A04,east,alpha,13,4,88,review,7000,3700
e0010,4500,A05,north,beta,41,6,24,ok,6200,3300
"""
_VISIBLE_RULES = {
    # Opaque on purpose: this exact string is one of the tokens
    # negative_weight_hardcoded_sample_answers looks for in the submission.
    "label": "TASK-0000000001352512",
    "window_start": 1000,
    "window_end": 9000,
    "kind_weights": {"alpha": 3, "beta": 5, "gamma": 7},
    "region_offsets": {"north": 11, "south": 13, "east": 17, "west": 19},
    "flag_penalties": {"ok": 0, "review": 23, "hold": 41},
    "top_n": 4,
    "meter_modulus": 20000,
    "meter_seed": 7,
    "tariff_bps": 1450,
    "unit_divisor": 1000,
}
_VISIBLE_INPUTS: tuple[Path, Path] | None = None
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_RUNNER = r'''
import importlib.util, json, statistics, sys, time
module_path, events, rules, repeats = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
sys.path.insert(0, module_path.rsplit("/", 1)[0])
spec = importlib.util.spec_from_file_location("submitted_optimize", module_path)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load submission")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
samples = []
result = None
for _ in range(repeats):
    start = time.perf_counter_ns()
    current = module.aggregate(events, rules)
    samples.append(time.perf_counter_ns() - start)
    if result is None:
        result = current
    elif current != result:
        raise SystemExit("nondeterministic aggregate result")
print(json.dumps({"result": result, "median_ns": int(statistics.median(samples))}, sort_keys=True))
'''


def write_dataset(root: Path, seed: int, n: int = 1200, *, window: tuple[int, int] = (1000, 9000),
                  file_format: dict[str, Any] | None = None, tiers: Any = ((0, 1450),),
                  overrides: dict[str, int] | None = None, suffix: str = ".csv",
                  calibrate_divisor: int | None = None, calibrate_tier: tuple[int, int] | None = None,
                  rule_overlays: dict[str, Any] | None = None,
                  raw_aliases: dict[str, dict[str, str]] | None = None,
                  **traps: Any) -> tuple[Path, Path]:
    """Seeded flat workload with the extended meter schema for engine tests.

    With no trap keywords this is the plain workload (padded ids, clean fields,
    no replays, no unknown kinds, no rows before the window)."""
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o755)
    events = root / ("events" + suffix)
    rules = root / "rules.json"
    kinds = ["alpha", "beta", "gamma", "delta", "epsilon"]
    regions = ["north", "south", "east", "west", "central"]
    extra_rules: dict[str, Any] = {"tariff_tiers": [list(t) for t in tiers]}
    if overrides is not None:
        extra_rules["meter_seed_overrides"] = overrides
    if rule_overlays:
        extra_rules.update(rule_overlays)
    payload = {
        **extra_rules,
        "label": "ROLLUP-SEED",
        "void_flag": "revoke",
        "window_start": int(window[0]),
        "window_end": int(window[1]),
        "kind_weights": {k: i * 2 + 3 for i, k in enumerate(kinds)},
        "region_offsets": {r: i * 5 + 11 for i, r in enumerate(regions)},
        "flag_penalties": {"ok": 0, "review": 23, "hold": 41, "late": 17},
        "top_n": 7,
        "meter_modulus": GEN_MODULUS,
        "meter_seed": GEN_METER_SEED,
        "tariff_bps": 1450,
        "unit_divisor": 1000,
    }
    # Section 4c: hold a parameter back and publish it only through controls.
    calibration: dict[str, Any] = {}
    if calibrate_divisor is not None:
        del payload["unit_divisor"]
        calibration["energy"] = calibration_controls(
            calibrate_divisor, [(0, 1)], [123457, 80001, 45678, 9999, 987654, 555555, 2468013], [])["energy"]
    if calibrate_tier is not None:
        start, intended = calibrate_tier
        full = sorted([tuple(x) for x in tiers if x[0] != start] + [(start, intended)])
        payload["tariff_tiers"] = [[s, None if s == start else b] for s, b in reversed(full)]
        calibration["cost"] = calibration_controls(
            1000, full, [], [(0, start + 7000), (start - 2000, 9000), (start + 500, 4321), (0, start + 15001)])["cost"]
    if calibration:
        payload["calibration"] = calibration
    rules.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    rows = build_trap_rows(seed, n, **traps)
    if raw_aliases:
        positions = {"account": 2, "region": 3, "kind": 4, "flag": 8}
        for row in rows:
            for field, replacements in raw_aliases.items():
                position = positions[field]
                canonical = row[position].strip()
                replacement = replacements.get(canonical)
                if replacement is not None:
                    row[position] = replacement
    write_events_file(events, rows, **(file_format or {}))
    events.chmod(0o644)
    rules.chmod(0o644)
    return events, rules


def visible_inputs() -> tuple[Path, Path]:
    global _VISIBLE_INPUTS
    if _VISIBLE_INPUTS is None:
        root = Path(tempfile.mkdtemp(prefix="performance-visible-"))
        root.chmod(0o755)
        events = root / "events.csv"
        rules = root / "rules.json"
        events.write_text(_VISIBLE_EVENTS_TEXT, encoding="utf-8")
        rules.write_text(json.dumps(_VISIBLE_RULES, sort_keys=True), encoding="utf-8")
        events.chmod(0o644)
        rules.chmod(0o644)
        _VISIBLE_INPUTS = (events, rules)
    return _VISIBLE_INPUTS


_EXPECTED_CACHE: dict[str, Any] | None = None


def _verifier_expected() -> dict[str, Any]:
    """Regenerate the load-bearing corpus in a private tempdir and compute the
    expected artifacts in-process. Never reads /app/data."""
    global _EXPECTED_CACHE
    if _EXPECTED_CACHE is not None:
        return _EXPECTED_CACHE
    tmp = Path(tempfile.mkdtemp(prefix="verif_"))
    write_loadbearing_corpus(tmp, CANON_SEED)
    resolved = resolve_chain(tmp)
    scenario_results = _compute_scenarios(resolved)
    expected: dict[str, Any] = {}
    for name in SCENARIO_ORDER:
        expected["scenario_%s.json" % name] = _scenario_payload(name, scenario_results[name], resolved)
    # observed_relative_median is machine specific, so the reference carries a
    # placeholder and the comparison drops the key on both sides.
    expected["perf_report.json"] = _perf_report(resolved, None)
    expected["bottleneck_analysis.json"] = _bottleneck(resolved)
    expected["recommendations.json"] = _recommendations(resolved)
    expected["data_quality.json"] = _data_quality(FILE_MANIFEST, scenario_results, resolved)
    _EXPECTED_CACHE = expected
    return expected


def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except FileNotFoundError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _untrusted_command(command: list[str]) -> list[str]:
    if os.name == "posix" and os.geteuid() == 0:
        return [*_SETPRIV, *command]
    if os.name == "posix" and os.geteuid() != 0 and _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    return command


def _readable_submission() -> Path:
    """A copy of the submitted module (and every sibling .py it may import) that
    the unprivileged user can read. Agents often write their files 0600, and in
    the verifier those files are root-owned, so running the original as nobody
    would fail with Permission denied for reasons unrelated to the code."""
    if not SUBMISSION.is_file():
        return SUBMISSION
    copy_dir = Path(tempfile.mkdtemp(prefix="submission_"))
    for source in sorted(OUT_DIR.glob("*.py")):
        target = copy_dir / source.name
        target.write_bytes(source.read_bytes())
        target.chmod(0o644)
    copy_dir.chmod(0o755)
    return copy_dir / SUBMISSION.name


def _isolated_stdout(command: list[str], timeout: int) -> str:
    """Run untrusted code in its own process group and kill every survivor."""
    proc = subprocess.Popen(
        _untrusted_command(command), text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=True,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONHASHSEED": "0",
             "PYTHONDONTWRITEBYTECODE": "1", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
        if proc.returncode:
            raise subprocess.CalledProcessError(proc.returncode, command, stdout, stderr)
        return stdout
    finally:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if proc.poll() is None:
            proc.communicate()


def run_submission_timed(events: Path, rules: Path, repeats: int = 1) -> tuple[dict[str, Any], int]:
    stdout = _isolated_stdout(
        [sys.executable, "-I", "-B", "-c", _RUNNER, str(_readable_submission()),
         str(events), str(rules), str(repeats)], 120)
    payload = json.loads(stdout)
    return payload["result"], int(payload["median_ns"])


_RESOLVE_RUNNER = r'''
import importlib.util, json, sys
module_path, data_dir, scenario = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, module_path.rsplit("/", 1)[0])
spec = importlib.util.spec_from_file_location("submitted_optimize", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(json.dumps(module.resolve_rules(data_dir, scenario), sort_keys=True))
'''


def run_resolve(data_dir: Path, scenario: str) -> dict[str, Any]:
    return json.loads(_isolated_stdout(
        [sys.executable, "-I", "-B", "-c", _RESOLVE_RUNNER,
         str(_readable_submission()), str(data_dir), scenario], 120))


def expected_resolved_rules(data_dir: Path, scenario: str) -> dict[str, Any]:
    """Section 6b: the fully resolved rules object, from the verifier's resolver."""
    resolved = resolve_chain(data_dir)
    coeffs = resolved["coeffs"]
    rules = _scenario_rules(coeffs, coeffs["scenario_windows"][scenario])
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
        "meter_seed_overrides": seed_overrides(rules),
        "tariff_tiers": [[s, b] for s, b in tariff_tiers(rules)],
        "unit_divisor": unit_divisor(rules),
        "void_flag": _void_flag(rules),
    }
    for key in (
        "account_aliases", "region_aliases", "kind_aliases", "flag_aliases",
        "account_meter_modulus", "account_unit_divisor", "account_tariff_tiers",
        "account_tariff_credit_wh", "meter_reset_flag",
    ):
        if key in rules:
            result[key] = rules[key]
    return result


def _held_out_sources(mutate) -> Path:
    """A fresh copy of the load-bearing tree with one source rewritten."""
    root = Path(tempfile.mkdtemp(prefix="heldout_"))
    write_loadbearing_corpus(root, CANON_SEED)
    mutate(root)
    for path in [root, *root.rglob("*")]:
        path.chmod(0o755 if path.is_dir() else 0o644)
    return root


def _write_tier_book_and_controls(root, tiers_with_rate, held_start, divisor, **layout):
    """Tariff book whose winning sheet holds back one rate, plus matching controls."""
    sheet_rows = [["start_wh", "bps"]] + [[s, "calibrate" if s == held_start else b] for s, b in reversed(tiers_with_rate)]
    _write_xlsx(root / TARIFF_BOOK, [
        ("tiers_2026Q1_draft", [["start_wh", "bps"], [0, 1600], [10000, 2400]]),
        ("tiers_2025Q4", sheet_rows),
        ("readme", [["Tier sheets are named tiers_<year>Q<quarter>."]]),
        ("tiers_2025Q3", [["start_wh", "bps"], [0, 1475], [15000, 2150], [45000, 2900]]),
    ], **layout)
    controls = calibration_controls(divisor, sorted(tiers_with_rate), [374770, 52130, 98765, 15999, 2468013],
                                    [(0, 30000), (5000, 20000), (held_start - 1000, 3000), (0, 39999), (39000, 500)])
    (root / CALIBRATION_ACTIVE).write_text(json.dumps(controls, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def _assert_resolved(mutate, keys):
    root = _held_out_sources(mutate)
    try:
        produced = run_resolve(root, "peak")
        reference = expected_resolved_rules(root, "peak")
    finally:
        root.chmod(0o700)
    differing = [k for k in keys if not _strict_equal(produced.get(k), reference[k])]
    assert not differing, f"resolve_rules differs on {differing}"


def run_submission(events: Path, rules: Path) -> dict[str, Any]:
    return run_submission_timed(events, rules)[0]


def _cli_stdout(events: Path, rules: Path) -> str:
    return _isolated_stdout(
        [sys.executable, "-B", str(_readable_submission()), str(events), str(rules)], 60)


def _median(samples: list[int]) -> int:
    samples = sorted(samples)
    return samples[len(samples) // 2]


def _time_call(fn, events: Path, rules: Path, repeats: int) -> int:
    best_guard = None
    samples = []
    for _ in range(repeats):
        start = time.perf_counter_ns()
        result = fn(events, rules)
        samples.append(time.perf_counter_ns() - start)
        if best_guard is None:
            best_guard = result
        elif result != best_guard:
            raise RuntimeError("benchmark target is nondeterministic")
    return _median(samples)


def _source() -> str:
    return SUBMISSION.read_text(encoding="utf-8", errors="replace") if SUBMISSION.exists() else ""


def _source_tree():
    """Parse the submitted module, or None when there is nothing parsable there."""
    text = _source()
    if not text.strip():
        return None
    try:
        return ast.parse(text)
    except SyntaxError:
        return None


def _imported_roots(tree) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def _attribute_paths(tree) -> set[str]:
    paths: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            paths.add("%s.%s" % (node.value.id, node.attr))
    return paths


def _string_constants(tree) -> set[str]:
    return {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def _unsorted_key_paths(text: str) -> list[str]:
    """Return one entry per JSON object whose keys are out of sorted order."""
    offenders: list[str] = []

    def hook(pairs):
        keys = [k for k, _ in pairs]
        if keys != sorted(keys):
            offenders.append(",".join(keys))
        return dict(pairs)

    json.loads(text, object_pairs_hook=hook)
    return offenders


def _json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _strict_equal(left: Any, right: Any) -> bool:
    """JSON equality that does not accept booleans as integers."""
    return json.dumps(left, sort_keys=True, separators=(",", ":")) == json.dumps(
        right, sort_keys=True, separators=(",", ":"))


CHALLENGE_SEED = int("1363003703932080056")
EVAL_SEED = int("7692160586900466207")


def _assert_hidden_workload(seed: int, n: int, **kwargs: Any) -> None:
    with tempfile.TemporaryDirectory() as td:
        events, rules = write_dataset(Path(td), seed, n, **kwargs)
        produced = run_submission(events, rules)
        reference = expected_report(events, rules)
    differing = sorted(k for k in set(produced) | set(reference)
                       if not _strict_equal(produced.get(k), reference.get(k)))
    assert not differing, f"aggregate differs from the contract on keys {differing}"


def _assert_hand_workload(rows: list[list[str]], overlays: dict[str, Any] | None = None) -> None:
    """Run a compact adversarial ledger whose ordering facts are easy to miss."""
    payload: dict[str, Any] = {
        "label": "HAND-TRAP", "window_start": 1000, "window_end": 9000,
        "kind_weights": {"alpha": 3}, "region_offsets": {"north": 11},
        "flag_penalties": {"ok": 0}, "void_flag": "revoke", "top_n": 5,
        "meter_modulus": 1000, "meter_seed": 0, "tariff_bps": 100,
        "unit_divisor": 1000,
    }
    payload.update(overlays or {})
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        root.chmod(0o755)
        events = root / "events.csv"
        rules = root / "rules.json"
        write_events_file(events, rows)
        rules.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        produced = run_submission(events, rules)
        reference = expected_report(events, rules)
    assert _strict_equal(produced, reference), "hand trap differs from the contract"


def _impl_test_hidden_plain_workload_exact():
    """POSITIVE: a first void-looking row is ordinary, while a later replay is a notice."""
    _assert_hand_workload([
        ["e1", "1500", "A000", "north", "alpha", "2", "1", "0", "revoke", "100", "0"],
        ["e1", "1600", "A000", "north", "alpha", "99", "1", "0", "ok", "200", "0"],
        ["e2", "1700", "A000", "north", "alpha", "2", "1", "0", "ok", "250", "0"],
    ])


def _impl_test_hidden_normalisation_workload():
    """POSITIVE: alias lookup is one step, not a transitive chain."""
    _assert_hand_workload(
        [["e1", "1500", "legacy", "NORTH", "old", "2", "1", "0", "oldflag", "100", "0"]],
        {"account_aliases": {"legacy": "canonical", "canonical": "final"},
         "region_aliases": {"north": "NORTH"}, "kind_aliases": {"old": "alpha"},
         "flag_aliases": {"oldflag": "ok"}},
    )


def _impl_test_hidden_replay_workload():
    """POSITIVE: a void notice cannot withdraw a quarantined first occurrence."""
    _assert_hand_workload([
        ["e1", "1500", "A000", "north", "omega", "2", "1", "0", "ok", "100", "0"],
        ["e1", "1600", "A000", "north", "omega", "2", "1", "0", "revoke", "200", "0"],
        ["e2", "1700", "A000", "north", "alpha", "2", "1", "0", "ok", "250", "0"],
    ])


def _impl_test_hidden_quarantine_workload():
    """POSITIVE: an unknown flag remains admitted and receives zero penalty."""
    _assert_hand_workload([
        ["e1", "1500", "A000", "north", "alpha", "2", "1", "0", "mystery", "100", "0"],
    ])


def _impl_test_hidden_replay_void_notice_workload():
    """POSITIVE: a later replay carrying void_flag withdraws the first event."""
    _assert_hand_workload([
        ["e1", "1500", "A000", "north", "alpha", "2", "1", "0", "ok", "100", "0"],
        ["e1", "1600", "A000", "north", "alpha", "2", "1", "0", "revoke", "200", "0"],
        ["e2", "1700", "A000", "north", "alpha", "2", "1", "0", "ok", "250", "0"],
    ])


def _impl_test_hidden_tier_position_workload():
    """POSITIVE: tariff credit clamps pre-window position at zero."""
    _assert_hand_workload([
        ["e0", "500", "A000", "north", "alpha", "1", "1", "0", "ok", "500", "0"],
        ["e1", "1500", "A000", "north", "alpha", "1", "1", "0", "ok", "600", "0"],
    ], {"tariff_tiers": [[0, 1000], [100, 3000]], "account_tariff_credit_wh": {" a000 ": 9999}})


def _impl_test_hidden_calibrated_divisor_workload():
    """POSITIVE: a held-back global divisor is recovered even when the
    calibration output is zero and the smallest match exceeds usage_wh."""
    _assert_hand_workload([
        ["e1", "1500", "A000", "north", "alpha", "1", "1", "0", "ok", "10", "0"],
    ], {"unit_divisor": None,
        "calibration": {"energy": [{"usage_wh": 10, "energy_kwh": 0}], "cost": []}})


def _impl_test_hidden_calibrated_tier_workload():
    """POSITIVE: account-specific modulus overrides the global rollover."""
    _assert_hand_workload([
        ["e1", "1500", "A000", "north", "alpha", "1", "1", "0", "ok", "90", "0"],
        ["e2", "1600", "A000", "north", "alpha", "1", "1", "0", "ok", "10", "0"],
    ], {"meter_modulus": 1000, "account_meter_modulus": {" a000 ": 100}})


def _impl_test_hidden_large_tier_calibration_workload():
    """POSITIVE: held-back tier recovery has no arbitrary one-million-bps cap."""
    _assert_hand_workload([
        ["e1", "1500", "A000", "north", "alpha", "1", "1", "0", "ok", "1", "0"],
    ], {"tariff_tiers": [[0, None]],
        "calibration": {"energy": [],
                        "cost": [{"pre_wh": 0, "usage_wh": 1, "cost_cents": 101}]}})


def _impl_test_hidden_meter_corpus_order_workload():
    """POSITIVE: meter-reset rows establish a new baseline and contribute zero
    usage while remaining ordinary scored events."""
    _assert_hidden_workload(
        EVAL_SEED ^ 0x55, 1400, padded=False, reset_every=31,
        rule_overlays={"meter_reset_flag": "reset"},
    )


def _impl_test_hidden_file_format_workload():
    """POSITIVE: section 3 header-driven reading (different column order, an
    extra column, a UTF-8 BOM, CRLF line endings, blank lines, column names
    written with surrounding whitespace) on an unseen workload."""
    _assert_hidden_workload(EVAL_SEED ^ 0x66, 1400, file_format={
        "shuffled": True, "extra": ("ingest_batch", lambda n: "b%d" % (n % 5)),
        "bom": True, "crlf": True, "blank_every": 37, "padded_header": True,
        "mixed_case_header": True,
    })


def _impl_test_hidden_mixed_format_workload():
    """POSITIVE: section 3 events formats chosen by extension: a pipe-separated
    .psv file with a reordered, whitespace-padded header and an .ndjson file with
    integer-typed fields and an extra key, both on unseen workloads."""
    _assert_hidden_workload(EVAL_SEED ^ 0xE1, 1200, suffix=".psv", file_format={"shuffled": True, "padded_header": True})
    _assert_hidden_workload(EVAL_SEED ^ 0xE2, 1200, suffix=".ndjson",
                            file_format={"shuffled": True, "extra": ("src", lambda n: "v%d" % (n % 3)),
                                         "mixed_case_header": True})


def _impl_test_hidden_tiered_tariff_workload():
    """POSITIVE: account tariff profiles can carry independently unsorted tier
    lists and take precedence over the default tariff."""
    _assert_hidden_workload(
        EVAL_SEED ^ 0x77, 1400, tiers=((30000, 2600), (0, 1450), (9000, 1900)),
        rule_overlays={"account_tariff_tiers": {
            " a003 ": [[20000, 2700], [0, 1200], [6000, 1800]],
            " a004 ": [[10000, 2500], [0, 1550]],
        }},
    )


def _hidden_overrides() -> dict[str, int]:
    rng = GenRng(EVAL_SEED ^ 0x88)
    out = {}
    for i in range(0, 90, 3):
        name = "A%03d" % i
        name = name.lower() if i % 2 else name
        out[(" " if i % 9 == 0 else "") + name] = rng.rand_int(0, GEN_MODULUS - 1)
    return out


def _impl_test_hidden_meter_seed_override_workload():
    """POSITIVE: exact meter seeds beat wildcard seeds, and wildcard selection
    uses longest prefix before lexical order."""
    overrides = {"A*": 111, "A0*": 2222, "A00*": 3333, "A003": 4444}
    _assert_hidden_workload(EVAL_SEED ^ 0x88, 1400, window=(1000, 9000), overrides=overrides)


def _impl_test_hidden_interaction_workload():
    """POSITIVE: every rule at once on one unseen workload, so the multi-hop
    interactions show up: replays and quarantine decide which pre-window reading
    anchors each walk, overrides seed accounts without one, corpus order decides
    meter continuity, and the resulting usage decides tier crossings."""
    _assert_hidden_workload(
        EVAL_SEED ^ 0x99, 1600, padded=False, ts_lo=600, window=(2500, 8000), id_prefix="telemetry",
        noise=200, replays=120, quarantine=50, unknown_regions=20, unknown_flags=25,
        ties=50, voids=60,
        casefold_replays=True, forward_voids=30, reset_every=43,
        meter_moduli={"A000": 17011},
        tiers=((22000, 2400), (0, 1450), (8000, 1800)), overrides=_hidden_overrides(), calibrate_divisor=1013,
        rule_overlays={
            "account_aliases": {"legacy-a007": "A007"},
            "kind_aliases": {"a-type": "alpha"},
            "account_meter_modulus": {"A000": 17011},
            "account_unit_divisor": {"A001": 997},
            "account_tariff_credit_wh": {"A002": 6000},
            "meter_reset_flag": "reset",
        },
        raw_aliases={"account": {"A007": "legacy-a007"}, "kind": {"alpha": "a-type"}},
        file_format={"shuffled": True, "extra": ("src", lambda n: "v%d" % (n % 3)),
                     "bom": True, "crlf": True, "blank_every": 51, "mixed_case_header": True},
    )


def _impl_test_hidden_boundary_mix_workload():
    """POSITIVE: a fresh workload crosses the window boundary while combining
    reset baselines, per-account divisors, wildcard seeds and forward notices."""
    _assert_hidden_workload(
        EVAL_SEED ^ 0xB1, 1900, padded=True, ts_lo=900, window=(3200, 7600),
        id_prefix="boundary", noise=140, replays=90, quarantine=35,
        unknown_regions=15, unknown_flags=20, ties=35, voids=45,
        casefold_replays=True, forward_voids=22, reset_every=37,
        meter_moduli={"A000": 19007, "A001": 23011},
        tiers=((26000, 2550), (0, 1375), (9000, 1880)),
        overrides={"A*": 777, "A0*": 1777, "A00*": 2777, "A004": 4777},
        calibrate_divisor=1009,
        rule_overlays={
            "account_meter_modulus": {" a000 ": 19007, " a001 ": 23011},
            "account_unit_divisor": {" a001 ": 991},
            "meter_reset_flag": "reset",
            "void_flag": "revoke",
        },
    )


def _impl_test_hidden_alias_reset_workload():
    """POSITIVE: aliases, reset rows and unknown flags remain independent on a
    second unseen corpus rather than inheriting state from an earlier account."""
    _assert_hidden_workload(
        EVAL_SEED ^ 0xB2, 1700, padded=False, ts_lo=700, window=(2800, 8400),
        id_prefix="alias-reset", noise=110, replays=70, quarantine=28,
        unknown_regions=18, unknown_flags=30, ties=28, voids=35,
        casefold_replays=True, forward_voids=18, reset_every=29,
        meter_moduli={"A002": 17009},
        tiers=((18000, 2450), (0, 1425), (7000, 1760)),
        overrides={"A*": 555, "A00*": 1555, "A002": 2555},
        calibrate_divisor=1003,
        rule_overlays={
            "account_aliases": {" legacy-a002 ": "A002"},
            "account_meter_modulus": {" a002 ": 17009},
            "account_unit_divisor": {" a002 ": 1001},
            "meter_reset_flag": "reset",
            "void_flag": "cancel",
        },
    )


def _impl_test_cli_outputs_canonical_json():
    """POSITIVE: the script form prints the contract object as JSON with sorted
    object keys, nothing else on standard output, and the same bytes on a
    repeated run."""
    events, rules = visible_inputs()
    text = _cli_stdout(events, rules).strip()
    assert text, "the script printed nothing on standard output"
    assert _strict_equal(json.loads(text), expected_report(events, rules))
    unsorted_objects = _unsorted_key_paths(text)
    assert not unsorted_objects, f"printed JSON has unsorted keys: {unsorted_objects}"
    # The same input must print the same bytes on a second run.
    with tempfile.TemporaryDirectory() as td:
        events2, rules2 = write_dataset(Path(td), CHALLENGE_SEED, 400)
        first = _cli_stdout(events2, rules2)
        second = _cli_stdout(events2, rules2)
    assert first.strip() and first == second, "repeated runs on the same data printed different bytes"


def _scenario_pairs():
    expected = _verifier_expected()
    for name in SCENARIO_ORDER:
        key = "scenario_%s.json" % name
        yield name, _json(OUT_DIR / key), expected[key]


def _impl_test_scenario_envelope_matches_reference():
    """POSITIVE: every scenario artifact names the scenario, the resolved source,
    the resolved thresholds, and the active label and window."""
    for name, produced, reference in _scenario_pairs():
        assert produced.get("scenario") == reference["scenario"], name
        assert produced.get("source") == reference["source"], f"{name}: source"
        assert _strict_equal(produced.get("thresholds"), reference["thresholds"]), f"{name}: thresholds"
        result = produced.get("result", {})
        assert result.get("label") == reference["result"]["label"], f"{name}: label"
        assert result.get("window") == reference["result"]["window"], f"{name}: window"


def _impl_test_scenario_counts_and_checksums_match_reference():
    """POSITIVE: every scenario's event_count, flag_counts and checksum match the
    reference computed over the admitted rows of the resolved corpus."""
    for name, produced, reference in _scenario_pairs():
        result = produced.get("result", {})
        for key in ("event_count", "flag_counts", "checksum"):
            assert _strict_equal(result.get(key), reference["result"][key]), f"{name}: {key}"


def _impl_test_scenario_score_totals_match_reference():
    """POSITIVE: every scenario's account/region/kind totals, top accounts and
    metrics match the reference."""
    for name, produced, reference in _scenario_pairs():
        result = produced.get("result", {})
        for key in ("account_totals", "region_totals", "kind_totals", "top_accounts"):
            assert _strict_equal(result.get(key), reference["result"][key]), f"{name}: {key}"
        assert _strict_equal(produced.get("metrics"), reference["metrics"]), f"{name}: metrics"


def _impl_test_scenario_usage_and_energy_match_reference():
    """POSITIVE: every scenario's per-account usage and kWh match the reference
    meter walk and once-per-account rounding."""
    for name, produced, reference in _scenario_pairs():
        result = produced.get("result", {})
        for key in ("account_usage_wh", "account_energy_kwh"):
            assert _strict_equal(result.get(key), reference["result"][key]), f"{name}: {key}"


def _impl_test_scenario_cost_matches_reference():
    """POSITIVE: every scenario's per-account tiered cost matches the reference."""
    for name, produced, reference in _scenario_pairs():
        result = produced.get("result", {})
        assert _strict_equal(result.get("account_cost_cents"), reference["result"]["account_cost_cents"]), f"{name}: cost"


def _key_shape(value):
    """The nested key layout of a JSON value, ignoring every leaf value. Only the
    fixed-key objects of the contract are descended into; maps keyed by data
    (accounts, regions, kinds, flags) are compared by their values elsewhere."""
    if isinstance(value, dict):
        return sorted(value)
    return None


def _impl_test_artifacts_carry_exactly_the_contract_keys():
    """POSITIVE: every scenario artifact (top level, result, metrics, thresholds)
    and data_quality.json carry exactly the keys the contract lists, no extra and
    none missing. Values are graded by the other tests."""
    for name, produced, reference in _scenario_pairs():
        assert isinstance(produced, dict), name
        assert _key_shape(produced) == _key_shape(reference), f"{name}: top-level keys"
        for part in ("result", "metrics", "thresholds"):
            assert isinstance(produced.get(part), dict), f"{name}: {part}"
            assert _key_shape(produced[part]) == _key_shape(reference[part]), f"{name}: {part} keys"
    expected_quality = _verifier_expected()["data_quality.json"]
    produced_quality = _json(OUT_DIR / "data_quality.json")
    assert isinstance(produced_quality, dict), "data_quality.json"
    assert _key_shape(produced_quality) == _key_shape(expected_quality), "data_quality.json keys"
    checks = produced_quality.get("scenario_checks")
    assert isinstance(checks, list) and checks, "data_quality.scenario_checks"
    for entry in checks:
        assert isinstance(entry, dict), "scenario_checks entry"
        assert _key_shape(entry) == _key_shape(expected_quality["scenario_checks"][0]), "scenario_checks entry keys"


def _impl_test_config_reports_match_reference():
    """POSITIVE: perf_report (its measured ratio only as a float in (0, ceiling]),
    bottleneck_analysis and recommendations match the independently resolved
    reference."""
    expected = _verifier_expected()
    produced_perf = _json(OUT_DIR / "perf_report.json")
    assert produced_perf.get("ok") is True, "perf_report.ok must be the boolean true"
    observed = produced_perf.get("observed_relative_median")
    target = expected["perf_report.json"]["relative_target"]
    assert isinstance(observed, float) and 0.0 < observed <= target, \
        f"observed_relative_median must be a float above zero and at most {target}, got {observed!r}"
    produced_perf.pop("observed_relative_median", None)
    reference_perf = dict(expected["perf_report.json"])
    reference_perf.pop("observed_relative_median", None)
    assert _strict_equal(produced_perf, reference_perf), "perf_report.json differs from the reference"
    assert _strict_equal(_json(OUT_DIR / "bottleneck_analysis.json"), expected["bottleneck_analysis.json"])
    assert _strict_equal(_json(OUT_DIR / "recommendations.json"), expected["recommendations.json"])


def _impl_test_data_quality_file_census_matches_reference():
    """POSITIVE: data_quality carries the exact sorted file census of /app/data
    and its file count."""
    expected = _verifier_expected()["data_quality.json"]
    produced = _json(OUT_DIR / "data_quality.json")
    for key in ("flat_input_file_count", "input_files"):
        assert _strict_equal(produced.get(key), expected[key]), f"data_quality.{key} differs"


def _impl_test_data_quality_admission_counts_match_reference():
    """POSITIVE: data_quality carries the corpus-level section 3a outcome:
    corpus, admitted, replayed, quarantined and withdrawn row counts."""
    expected = _verifier_expected()["data_quality.json"]
    produced = _json(OUT_DIR / "data_quality.json")
    for key in ("corpus_row_count", "admitted_row_count", "replayed_row_count",
                "quarantined_row_count", "withdrawn_row_count"):
        assert _strict_equal(produced.get(key), expected[key]), f"data_quality.{key} differs"


def _impl_test_data_quality_scenario_checks_match_reference():
    """POSITIVE: data_quality.scenario_checks match the reference per scenario,
    in the canonical order."""
    expected = _verifier_expected()["data_quality.json"]
    produced = _json(OUT_DIR / "data_quality.json")
    assert _strict_equal(produced.get("scenario_checks"), expected["scenario_checks"])


def _impl_test_artifacts_are_written_with_sorted_keys():
    """POSITIVE: every JSON artifact is a populated JSON object that serialises its
    object keys in sorted order at every level."""
    offenders = []
    for path in ARTIFACTS:
        if path.suffix != ".json":
            continue
        if not path.is_file():
            offenders.append(f"{path}: missing")
            continue
        text = path.read_text(encoding="utf-8")
        unsorted_objects = _unsorted_key_paths(text)
        if unsorted_objects:
            offenders.append(f"{path}: unsorted keys {unsorted_objects[0]}")
            continue
        payload = json.loads(text)
        if not isinstance(payload, dict):
            offenders.append(f"{path}: top level is {type(payload).__name__}, not a JSON object")
        elif not payload:
            offenders.append(f"{path}: empty JSON object, nothing was serialised")
    assert not offenders, f"artifacts not written as populated sorted-key JSON: {offenders}"


def _impl_test_resolve_xlsx_absolute_parts():
    """POSITIVE: section 4b tariff book written like other spreadsheet tools:
    absolute relationship targets (/xl/worksheets/...), cells without an r
    attribute, sheets in another order; the held-back rate is recovered from the
    matching controls."""
    def mutate(root):
        _write_tier_book_and_controls(root, [(0, 1525), (11000, 2310), (42000, 3125)], 11000, 1001,
                                      absolute_targets=True, cell_refs=False)
    _assert_resolved(mutate, ["tariff_tiers"])


def _impl_test_resolve_xlsx_text_numbers():
    """POSITIVE: section 4b tier cells stored as text in a shared-strings part."""
    def mutate(root):
        _write_tier_book_and_controls(root, [(0, 1550), (13000, 2275), (41000, 2990)], 13000, 1024, shared_text=True)
    _assert_resolved(mutate, ["tariff_tiers"])


def _impl_test_resolve_region_registry_names():
    """POSITIVE: section 4b region names in the registry normalised like the
    region field, with a nullable extra column."""
    def mutate(root):
        path = root / REGIONS_ACTIVE
        path.unlink()
        con = sqlite3.connect(str(path))
        try:
            con.execute("CREATE TABLE region_offsets (region TEXT NOT NULL, offset INTEGER NOT NULL, state TEXT NOT NULL, note TEXT)")
            con.executemany("INSERT INTO region_offsets VALUES (?, ?, ?, ?)", [
                (" North", 13, "active", None), ("north", 11, "retired", "old"), ("EAST ", 24, "active", None),
                ("South", 18, "active", "moved"), ("west", 30, "active", None), (" Central ", 32, "active", None),
                ("midwest", 40, "draft", None),
            ])
            con.commit()
        finally:
            con.close()
    _assert_resolved(mutate, ["region_offsets"])


def _impl_test_resolve_docx_split_runs():
    """POSITIVE: section 4b addendum cells whose text is split across runs."""
    def mutate(root):
        _write_docx(root / SEED_ADDENDUM, ["Meter seed addendum 3 (amends meter_seed_overrides_g10.json)."], [
            [["acc", "ount"], ["se", "ed"]],
            [[" a0", "11"], ["26", "00"]],
            [["A0", "09 "], ["81", "11"]],
            [["a0", "24"], ["re", "move"]],
            [["A0", "17"], ["9", "500"]],
        ])
    _assert_resolved(mutate, ["meter_seed_overrides"])


def _impl_test_resolve_yaml_quoted_policy():
    """POSITIVE: section 4b policy YAML with quoted keys and values and trailing
    comments."""
    def mutate(root):
        (root / POLICY_ACTIVE).write_text(
            "# admission policy, generation 3 (active)\n"
            "'replay_rule': \"first_occurrence_wins\"  # unchanged\n"
            "\"void_flag\": 'Cancel'   # adopted 2026-01\n", encoding="utf-8")
    _assert_resolved(mutate, ["void_flag"])


def _impl_test_repeated_median_relative_speedup_is_stable():
    """POSITIVE: the submission stays under the contract's relative median ceiling
    across two independent measurement batches. The benchmark workload is the
    plain workload, so correctness there is only a precondition."""
    target = _verifier_expected()["perf_report.json"]["relative_target"]
    with tempfile.TemporaryDirectory() as td:
        events, rules = write_dataset(Path(td), EVAL_SEED ^ 0xA5A5, 2400)
        if run_submission(events, rules) != expected_report(events, rules):
            raise RuntimeError("precondition failed: submission is wrong on the benchmark workload")
        _time_call(expected_report, events, rules, 2)
        run_submission_timed(events, rules, 2)
        ratios = []
        for _ in range(2):
            base = _time_call(expected_report, events, rules, 9)
            _, optimized = run_submission_timed(events, rules, 9)
            ratios.append(optimized / base)
    assert max(ratios) <= target, f"relative medians {ratios} exceed the {target} ceiling"
    assert min(ratios) > 0.0, "measured a non-positive run time"


def _impl_negative_weight_hardcoded_sample_answers():
    """NEGATIVE (inverted polarity): this assertion HOLDS when the submission
    carries string literals lifted straight out of one particular sample input,
    which the instruction forbids."""
    tree = _source_tree()
    assert tree is not None, "no parsable submission to inspect"
    literals = _string_constants(tree)
    tokens = {"e0001", "e0010", "A05", "0000000001352512", "TASK-0000000001352512", "ROLLUP-ACTIVE-G11"}
    assert len(literals & tokens) >= 2


def _impl_negative_weight_reads_tests_or_hidden_paths():
    """NEGATIVE (inverted polarity): this assertion HOLDS when a string literal in
    the submission points at the checking machinery outside /app, which the
    instruction forbids."""
    tree = _source_tree()
    assert tree is not None, "no parsable submission to inspect"
    literals = {s.lower() for s in _string_constants(tree)}
    hidden_log = "/" + "logs" + "/" + "verifier"
    reward_txt = "reward" + ".txt"
    reward_json = "reward" + ".json"
    assert any(
        s.startswith("/tests")
        or hidden_log in s
        or "test_output" in s
        or s.endswith(reward_txt)
        or s.endswith(reward_json)
        for s in literals
    )


def _impl_negative_weight_nonstdlib_or_network_imports():
    """NEGATIVE (inverted polarity): this assertion HOLDS when the submission
    imports a third-party package or a network module, which the instruction
    forbids."""
    tree = _source_tree()
    assert tree is not None, "no parsable submission to inspect"
    banned = {
        "requests", "httpx", "aiohttp", "urllib", "urllib2", "urllib3", "http",
        "socket", "ssl", "ftplib", "smtplib", "telnetlib", "xmlrpc",
        "numpy", "pandas", "scipy", "polars", "pyarrow", "duckdb", "orjson",
    }
    assert _imported_roots(tree) & banned


def _impl_negative_weight_time_or_randomness_tricks():
    """NEGATIVE (inverted polarity): this assertion HOLDS when the aggregator
    module itself reaches for a clock or a random source, which the instruction
    forbids."""
    tree = _source_tree()
    assert tree is not None, "no parsable submission to inspect"
    roots = _imported_roots(tree)
    calls = _attribute_paths(tree)
    clocks = {
        "time.perf_counter", "time.perf_counter_ns", "time.monotonic",
        "time.monotonic_ns", "time.process_time", "time.process_time_ns",
        "time.time", "time.time_ns", "time.sleep",
    }
    assert bool(roots & {"random", "secrets", "timeit"}) or bool(calls & clocks)


@criterion(description="aggregate treats a first void-flag row as ordinary and a later replay as a notice")
def test_hidden_plain_workload_exact(workspace):
    return _pass(_impl_test_hidden_plain_workload_exact)


@criterion(description="aggregate applies each alias exactly once after normalisation")
def test_hidden_normalisation_workload(workspace):
    return _pass(_impl_test_hidden_normalisation_workload)


@criterion(description="aggregate does not withdraw a quarantined first occurrence")
def test_hidden_replay_workload(workspace):
    return _pass(_impl_test_hidden_replay_workload)


@criterion(description="aggregate admits unknown flags with zero penalty")
def test_hidden_quarantine_workload(workspace):
    return _pass(_impl_test_hidden_quarantine_workload)


@criterion(description="aggregate withdraws the first event when a later replay carries void_flag")
def test_hidden_replay_void_notice_workload(workspace):
    return _pass(_impl_test_hidden_replay_void_notice_workload)


@criterion(description="aggregate clamps an account tariff credit at zero pre-window position")
def test_hidden_tier_position_workload(workspace):
    return _pass(_impl_test_hidden_tier_position_workload)


@criterion(description="aggregate recovers a held-back divisor whose zero-output solution exceeds usage_wh")
def test_hidden_calibrated_divisor_workload(workspace):
    return _pass(_impl_test_hidden_calibrated_divisor_workload)


@criterion(description="aggregate normalises account keys for per-account meter moduli")
def test_hidden_calibrated_tier_workload(workspace):
    return _pass(_impl_test_hidden_calibrated_tier_workload)


@criterion(description="aggregate recovers a held-back tier rate above one million basis points")
def test_hidden_large_tier_calibration_workload(workspace):
    return _pass(_impl_test_hidden_large_tier_calibration_workload)


@criterion(description="aggregate treats meter-reset rows as zero-usage baselines while still scoring them")
def test_hidden_meter_corpus_order_workload(workspace):
    return _pass(_impl_test_hidden_meter_corpus_order_workload)


@criterion(description="aggregate reads CSV, PSV and NDJSON keys case-insensitively with the documented format variations")
def test_hidden_file_format_workload(workspace):
    return _pass(_impl_test_hidden_file_format_workload) and _pass(_impl_test_hidden_mixed_format_workload)


@criterion(description="aggregate sorts and applies independent per-account tariff profiles")
def test_hidden_tiered_tariff_workload(workspace):
    return _pass(_impl_test_hidden_tiered_tariff_workload)


@criterion(description="aggregate resolves exact and wildcard meter seeds by exactness then longest prefix")
def test_hidden_meter_seed_override_workload(workspace):
    return _pass(_impl_test_hidden_meter_seed_override_workload)


@criterion(description="aggregate applies every contract rule at once on an unseen multi-trap workload")
def test_hidden_interaction_workload(workspace):
    return _pass(_impl_test_hidden_interaction_workload)


@criterion(description="aggregate handles a fresh boundary workload with resets, notices, seeds and tier crossings")
def test_hidden_boundary_mix_workload(workspace):
    return _pass(_impl_test_hidden_boundary_mix_workload)


@criterion(description="aggregate keeps aliases, reset baselines and unknown flags independent on a fresh corpus")
def test_hidden_alias_reset_workload(workspace):
    return _pass(_impl_test_hidden_alias_reset_workload)


@criterion(description="the script form prints the contract object as sorted-key JSON, nothing else, identically on a rerun")
def test_cli_outputs_canonical_json(workspace):
    return _pass(_impl_test_cli_outputs_canonical_json)


@criterion(description="every scenario artifact carries the resolved scenario, source, thresholds, label and window")
def test_scenario_envelope_matches_reference(workspace):
    return _pass(_impl_test_scenario_envelope_matches_reference)


@criterion(description="every scenario event_count, flag_counts and checksum match the reference")
def test_scenario_counts_and_checksums_match_reference(workspace):
    return _pass(_impl_test_scenario_counts_and_checksums_match_reference)


@criterion(description="every scenario score total, top account list and metrics match the reference")
def test_scenario_score_totals_match_reference(workspace):
    return _pass(_impl_test_scenario_score_totals_match_reference)


@criterion(description="every scenario usage and kWh figure matches the reference")
def test_scenario_usage_and_energy_match_reference(workspace):
    return _pass(_impl_test_scenario_usage_and_energy_match_reference)


@criterion(description="every scenario tiered cost figure matches the reference")
def test_scenario_cost_matches_reference(workspace):
    return _pass(_impl_test_scenario_cost_matches_reference)


@criterion(description="every artifact carries exactly the contract keys and is written as populated sorted-key JSON")
def test_artifacts_carry_exactly_the_contract_keys(workspace):
    return _pass(_impl_test_artifacts_carry_exactly_the_contract_keys) and _pass(_impl_test_artifacts_are_written_with_sorted_keys)


@criterion(description="perf_report, bottleneck_analysis and recommendations match the reference, with the measured ratio a float within the ceiling")
def test_config_reports_match_reference(workspace):
    return _pass(_impl_test_config_reports_match_reference)


@criterion(description="data_quality carries the exact sorted file census of the input directory")
def test_data_quality_file_census_matches_reference(workspace):
    return _pass(_impl_test_data_quality_file_census_matches_reference)


@criterion(description="data_quality carries the corpus row, admitted, replayed, quarantined and withdrawn counts")
def test_data_quality_admission_counts_match_reference(workspace):
    return _pass(_impl_test_data_quality_admission_counts_match_reference)


@criterion(description="data_quality scenario_checks match the reference in canonical order")
def test_data_quality_scenario_checks_match_reference(workspace):
    return _pass(_impl_test_data_quality_scenario_checks_match_reference)


@criterion(description="the submission stays under the contract relative median ceiling across two independent measurement batches")
def test_repeated_median_relative_speedup_is_stable(workspace):
    return _pass(_impl_test_repeated_median_relative_speedup_is_stable)


@criterion(description="resolve_rules handles absolute xlsx relationship targets and cells without references")
def test_resolve_xlsx_absolute_parts(workspace):
    return _pass(_impl_test_resolve_xlsx_absolute_parts)


@criterion(description="resolve_rules reads xlsx tier cells stored as text in a shared-strings part")
def test_resolve_xlsx_text_numbers(workspace):
    return _pass(_impl_test_resolve_xlsx_text_numbers)


@criterion(description="resolve_rules normalises registry region names like the region field")
def test_resolve_region_registry_names(workspace):
    return _pass(_impl_test_resolve_region_registry_names)


@criterion(description="resolve_rules concatenates every text run in a docx addendum cell")
def test_resolve_docx_split_runs(workspace):
    return _pass(_impl_test_resolve_docx_split_runs)


@criterion(description="resolve_rules reads quoted yaml keys and values before trailing comments")
def test_resolve_yaml_quoted_policy(workspace):
    return _pass(_impl_test_resolve_yaml_quoted_policy)


@criterion(description="the submitted module embeds string literals lifted from one particular sample input")
def negative_weight_hardcoded_sample_answers(workspace):
    return _pass(_impl_negative_weight_hardcoded_sample_answers)


@criterion(description="the submitted module points at checking machinery outside /app")
def negative_weight_reads_tests_or_hidden_paths(workspace):
    return _pass(_impl_negative_weight_reads_tests_or_hidden_paths)


@criterion(description="the submitted module imports a third-party package or a network module")
def negative_weight_nonstdlib_or_network_imports(workspace):
    return _pass(_impl_negative_weight_nonstdlib_or_network_imports)


@criterion(description="the aggregator module itself reaches for a clock or a random source")
def negative_weight_time_or_randomness_tricks(workspace):
    return _pass(_impl_negative_weight_time_or_randomness_tricks)


criteria.test_hidden_plain_workload_exact(weight=5)
criteria.test_cli_outputs_canonical_json(weight=3)
criteria.test_scenario_envelope_matches_reference(weight=1)
criteria.test_config_reports_match_reference(weight=3)
criteria.test_repeated_median_relative_speedup_is_stable(weight=3)
criteria.test_hidden_normalisation_workload(weight=5)
criteria.test_hidden_replay_workload(weight=5)
criteria.test_hidden_quarantine_workload(weight=5)
criteria.test_hidden_calibrated_divisor_workload(weight=5)
criteria.test_hidden_calibrated_tier_workload(weight=5)
criteria.test_hidden_replay_void_notice_workload(weight=5)
criteria.test_hidden_tier_position_workload(weight=5)
criteria.test_hidden_large_tier_calibration_workload(weight=5)
criteria.test_hidden_meter_corpus_order_workload(weight=5)
criteria.test_hidden_file_format_workload(weight=5)
criteria.test_hidden_tiered_tariff_workload(weight=5)
criteria.test_hidden_meter_seed_override_workload(weight=5)
criteria.test_hidden_interaction_workload(weight=5)
criteria.test_scenario_counts_and_checksums_match_reference(weight=5)
criteria.test_scenario_score_totals_match_reference(weight=5)
criteria.test_scenario_usage_and_energy_match_reference(weight=5)
criteria.test_scenario_cost_matches_reference(weight=5)
criteria.test_artifacts_carry_exactly_the_contract_keys(weight=1)
criteria.test_data_quality_file_census_matches_reference(weight=1)
criteria.test_data_quality_admission_counts_match_reference(weight=5)
criteria.test_data_quality_scenario_checks_match_reference(weight=1)
criteria.test_resolve_xlsx_absolute_parts(weight=1)
criteria.test_hidden_boundary_mix_workload(weight=5)
criteria.test_hidden_alias_reset_workload(weight=5)
criteria.test_resolve_docx_split_runs(weight=1)
criteria.test_resolve_yaml_quoted_policy(weight=1)
criteria.test_resolve_xlsx_text_numbers(weight=1)
criteria.test_resolve_region_registry_names(weight=1)
criteria.negative_weight_hardcoded_sample_answers(weight=-5)
criteria.negative_weight_reads_tests_or_hidden_paths(weight=-5)
criteria.negative_weight_nonstdlib_or_network_imports(weight=-5)
criteria.negative_weight_time_or_randomness_tricks(weight=-3)
