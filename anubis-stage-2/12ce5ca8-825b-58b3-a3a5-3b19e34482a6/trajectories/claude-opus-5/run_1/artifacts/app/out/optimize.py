#!/usr/bin/env python3
"""Single-pass telemetry rollup aggregator (standard library only).

Implements the data contract in /app/data/schema.md:

* ``resolve_rules(data_dir, scenario)`` walks the dependency chain
  (entrypoint -> catalog -> binding ledger -> roles) and returns the resolved
  rules object for one scenario.
* ``aggregate(events_path, rules_path)`` applies row admission and the
  corrected computation to one events file, in a single pass over the rows.
"""

import csv
import json
import os
import re
import sqlite3
import sys
import zipfile
from decimal import Decimal, ROUND_HALF_UP

EVENT_FIELDS = (
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
)

USED_FIELDS = (
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
)

SCENARIO_ORDER = ("visible", "peak", "steady", "burst", "latency")

CONFIG_ROLES = ("baseline", "cost", "hardware", "queryplan", "indexcfg", "thresholds")

_TIER_SHEET_RE = re.compile(r"^tiers_(\d{4})Q(\d+)$")
_CELL_REF_RE = re.compile(r"^([A-Z]+)(\d+)$")


# --------------------------------------------------------------------------
# exact arithmetic helpers
# --------------------------------------------------------------------------


def half_up(numerator, denominator):
    """Exact decimal division rounded half up to an integer."""
    return int(
        (Decimal(numerator) / Decimal(denominator)).quantize(
            Decimal(1), rounding=ROUND_HALF_UP
        )
    )


def tier_sum(tiers, pre_wh, usage_wh):
    """Block-tariff sum over the cumulative range [pre_wh, pre_wh + usage_wh)."""
    if usage_wh <= 0:
        return 0
    lo_range = pre_wh
    hi_range = pre_wh + usage_wh
    total = 0
    last = len(tiers) - 1
    for i, (start, bps) in enumerate(tiers):
        lo = start if start > lo_range else lo_range
        hi = hi_range if i == last else min(hi_range, tiers[i + 1][0])
        if hi > lo:
            total += (hi - lo) * bps
    return total


def _id_number(text):
    i = len(text)
    while i and "0" <= text[i - 1] <= "9":
        i -= 1
    return int(text[i:])


# --------------------------------------------------------------------------
# events file reading (section 3)
# --------------------------------------------------------------------------


def _iter_event_rows(events_path):
    """Yield one list of raw field texts per data row, in file order."""
    ext = events_path.rsplit(".", 1)[-1].lower() if "." in events_path else ""
    if ext == "ndjson":
        with open(events_path, "r", encoding="utf-8-sig", newline="") as fh:
            for line in fh:
                if not line.strip():
                    continue
                obj = json.loads(line)
                row = {}
                for key, value in obj.items():
                    row[key.strip().lower()] = value
                yield [str(row[name]) for name in USED_FIELDS]
        return

    delimiter = "|" if ext == "psv" else ","
    with open(events_path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh, delimiter=delimiter)
        index = None
        for row in reader:
            if index is None:
                header = [cell.strip().lower() for cell in row]
                index = [header.index(name) for name in USED_FIELDS]
                continue
            if not row:
                continue
            if len(row) == 1 and not row[0].strip():
                continue
            yield [row[i] for i in index]


# --------------------------------------------------------------------------
# row admission (section 3a)
# --------------------------------------------------------------------------


def _admit(events_path, rules):
    """Return (admitted_records, stats) for one events file.

    A record is ``(id_number, ts, account, region, kind, amount, units,
    latency_ms, flag, meter)`` with every text field already canonical.
    """
    kind_weights = rules["kind_weights"]
    account_aliases = rules.get("account_aliases") or {}
    region_aliases = rules.get("region_aliases") or {}
    kind_aliases = rules.get("kind_aliases") or {}
    flag_aliases = rules.get("flag_aliases") or {}
    void_flag = rules.get("void_flag")

    seen = set()
    first_slot = {}
    voided = set()
    records = []
    row_count = 0
    replayed = 0
    quarantined = 0

    for raw in _iter_event_rows(events_path):
        row_count += 1
        rid = raw[0].strip().lower()
        flag = raw[8].strip().lower()
        flag = flag_aliases.get(flag, flag)
        if rid in seen:
            replayed += 1
            if void_flag is not None and flag == void_flag:
                voided.add(rid)
            continue
        seen.add(rid)
        kind = raw[4].strip().lower()
        kind = kind_aliases.get(kind, kind)
        if kind not in kind_weights:
            quarantined += 1
            continue
        account = raw[2].strip().upper()
        account = account_aliases.get(account, account)
        region = raw[3].strip().lower()
        region = region_aliases.get(region, region)
        first_slot[rid] = len(records)
        records.append(
            (
                _id_number(rid),
                int(raw[1]),
                account,
                region,
                kind,
                int(raw[5]),
                int(raw[6]),
                int(raw[7]),
                flag,
                int(raw[9]),
            )
        )

    withdrawn_slots = set()
    for rid in voided:
        slot = first_slot.get(rid)
        if slot is not None:
            withdrawn_slots.add(slot)

    if withdrawn_slots:
        admitted = [r for i, r in enumerate(records) if i not in withdrawn_slots]
    else:
        admitted = records

    stats = {
        "corpus_row_count": row_count,
        "admitted_row_count": len(admitted),
        "replayed_row_count": replayed,
        "quarantined_row_count": quarantined,
        "withdrawn_row_count": len(withdrawn_slots),
    }
    return admitted, stats


def admission_report(events_path, rules_path):
    """Section 3a outcome counts over a whole events file, window independent."""
    rules = _load_rules(rules_path)
    _, stats = _admit(events_path, rules)
    return stats


# --------------------------------------------------------------------------
# calibration (section 4c)
# --------------------------------------------------------------------------


def calibrate_unit_divisor(controls):
    divisor = 1
    while True:
        if all(
            half_up(c["usage_wh"], divisor) == c["energy_kwh"]
            for c in controls
        ):
            return divisor
        divisor += 1


def calibrate_tier_bps(tiers, slot, controls):
    """Smallest bps >= 0 filling ``tiers[slot]`` that reproduces every control."""
    candidate = [list(t) for t in tiers]
    bps = 0
    while True:
        candidate[slot][1] = bps
        if all(
            half_up(tier_sum(candidate, c["pre_wh"], c["usage_wh"]), 10000)
            == c["cost_cents"]
            for c in controls
        ):
            return bps
        bps += 1


def _fill_calibrated(rules):
    """Resolve held-back ``unit_divisor`` / tier rate inside a rules object."""
    tiers = rules.get("tariff_tiers")
    if tiers is None:
        tiers = [[0, rules["tariff_bps"]]]
    tiers = sorted(([int(t[0]), t[1]] for t in tiers), key=lambda t: t[0])

    controls = rules.get("calibration") or {}
    divisor = rules.get("unit_divisor")
    if divisor is None:
        divisor = calibrate_unit_divisor(controls["energy"])

    held = [i for i, t in enumerate(tiers) if t[1] is None]
    if held:
        tiers[held[0]][1] = calibrate_tier_bps(tiers, held[0], controls["cost"])
    tiers = [[int(a), int(b)] for a, b in tiers]
    return tiers, int(divisor)


# --------------------------------------------------------------------------
# aggregate (sections 5 and 6)
# --------------------------------------------------------------------------


def _load_rules(rules_path):
    if isinstance(rules_path, dict):
        return rules_path
    with open(rules_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def aggregate(events_path, rules_path):
    rules = _load_rules(rules_path)
    admitted, _ = _admit(events_path, rules)

    window_start = int(rules["window_start"])
    window_end = int(rules["window_end"])
    kind_weights = rules["kind_weights"]
    region_offsets = rules.get("region_offsets") or {}
    flag_penalties = rules.get("flag_penalties") or {}
    reset_flag = rules.get("meter_reset_flag")

    account_totals = {}
    region_totals = {}
    kind_totals = {}
    flag_counts = {}
    pre_rows = {}
    win_rows = {}
    checksum = 0
    position = 0

    for rec in admitted:
        ts = rec[1]
        if ts < window_start:
            account = rec[2]
            entry = (rec[9], rec[8] == reset_flag)
            bucket = pre_rows.get(account)
            if bucket is None:
                pre_rows[account] = [entry]
            else:
                bucket.append(entry)
            continue
        if ts >= window_end:
            continue

        account = rec[2]
        region = rec[3]
        kind = rec[4]
        flag = rec[8]
        score = (
            rec[5] * rec[6] * kind_weights[kind]
            + region_offsets.get(region, 0)
            - flag_penalties.get(flag, 0)
            - rec[7] // 10
        )
        account_totals[account] = account_totals.get(account, 0) + score
        region_totals[region] = region_totals.get(region, 0) + score
        kind_totals[kind] = kind_totals.get(kind, 0) + score
        flag_counts[flag] = flag_counts.get(flag, 0) + 1

        position += 1
        checksum = (checksum * 1315423911 + score * position + rec[0]) & 0xFFFFFFFF

        entry = (rec[9], flag == reset_flag)
        bucket = win_rows.get(account)
        if bucket is None:
            win_rows[account] = [entry]
        else:
            bucket.append(entry)

    overrides = rules.get("meter_seed_overrides") or {}
    exact_seeds, wildcard_seeds = _split_overrides(overrides)
    default_seed = int(rules["meter_seed"])
    default_modulus = int(rules["meter_modulus"])
    account_modulus = rules.get("account_meter_modulus") or {}
    account_divisor = rules.get("account_unit_divisor") or {}
    account_tiers = rules.get("account_tariff_tiers") or {}
    account_credit = rules.get("account_tariff_credit_wh") or {}
    default_tiers, default_divisor = _fill_calibrated(rules)

    usage_wh = {}
    energy_kwh = {}
    cost_cents = {}

    for account in win_rows:
        modulus = int(account_modulus.get(account, default_modulus))
        seed = _seed_for(account, exact_seeds, wildcard_seeds, default_seed)

        previous = seed
        pre_usage = 0
        for meter, is_reset in pre_rows.get(account, ()):
            if not is_reset:
                pre_usage += (meter - previous) % modulus
            previous = meter

        total = 0
        for meter, is_reset in win_rows[account]:
            if not is_reset:
                total += (meter - previous) % modulus
            previous = meter

        divisor = int(account_divisor.get(account, default_divisor))
        tiers = account_tiers.get(account)
        tiers = default_tiers if tiers is None else sorted(
            ([int(t[0]), int(t[1])] for t in tiers), key=lambda t: t[0]
        )
        credit = int(account_credit.get(account, 0))
        pre_wh = pre_usage - credit
        if pre_wh < 0:
            pre_wh = 0

        usage_wh[account] = total
        energy_kwh[account] = half_up(total, divisor)
        cost_cents[account] = half_up(tier_sum(tiers, pre_wh, total), 10000)

    top_n = int(rules["top_n"])
    top_accounts = [
        [account, total]
        for account, total in sorted(
            account_totals.items(), key=lambda kv: (-kv[1], kv[0])
        )[:top_n]
    ]

    return {
        "label": rules["label"],
        "window": [window_start, window_end],
        "event_count": position,
        "account_totals": dict(sorted(account_totals.items())),
        "region_totals": dict(sorted(region_totals.items())),
        "kind_totals": dict(sorted(kind_totals.items())),
        "flag_counts": dict(sorted(flag_counts.items())),
        "account_usage_wh": dict(sorted(usage_wh.items())),
        "account_energy_kwh": dict(sorted(energy_kwh.items())),
        "account_cost_cents": dict(sorted(cost_cents.items())),
        "top_accounts": top_accounts,
        "checksum": checksum,
    }


def _split_overrides(overrides):
    exact = {}
    wildcard = []
    for key, value in overrides.items():
        name = key.strip().upper()
        if name.endswith("*"):
            wildcard.append((name[:-1], int(value)))
        else:
            exact[name] = int(value)
    wildcard.sort(key=lambda kv: (-len(kv[0]), kv[0]))
    return exact, wildcard


def _seed_for(account, exact, wildcard, default):
    seed = exact.get(account)
    if seed is not None:
        return seed
    for prefix, value in wildcard:
        if account.startswith(prefix):
            return value
    return default


# --------------------------------------------------------------------------
# dependency chain resolution (sections 1, 2, 4, 4b, 4c)
# --------------------------------------------------------------------------


def _read_catalog_ref(data_dir):
    path = os.path.join(data_dir, "ingest_handoff_notes.txt")
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.strip().startswith("catalog_ref:"):
                return line.split(":", 1)[1].strip()
    raise ValueError("no catalog_ref line in ingest_handoff_notes.txt")


def _catalog_target(catalog_path, key):
    conn = sqlite3.connect(catalog_path)
    try:
        row = conn.execute(
            "SELECT target FROM catalog WHERE key = ?", (key,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError("catalog has no key %r" % key)
    return row[0].strip()


def _read_ledger(ledger_path):
    roles = {}
    with open(ledger_path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh, delimiter="\t")
        header = None
        for row in reader:
            if not row or not any(c.strip() for c in row):
                continue
            if header is None:
                header = [c.strip().lower() for c in row]
                continue
            entry = dict(zip(header, (c.strip() for c in row)))
            if entry.get("state", "").lower() != "active":
                continue
            role = entry["role"].lower()
            generation = int(entry["generation"])
            current = roles.get(role)
            if current is None or generation > current[0]:
                roles[role] = (generation, entry["file"])
    return {role: value[1] for role, value in roles.items()}


def resolve_sources(data_dir):
    """Resolve every ledger role to a file name under ``data_dir``."""
    catalog = _read_catalog_ref(data_dir)
    ledger = _catalog_target(os.path.join(data_dir, catalog), "binding_registry")
    roles = _read_ledger(os.path.join(data_dir, ledger))
    roles["catalog"] = catalog
    roles["ledger"] = ledger
    return roles


def _load_region_offsets(path):
    conn = sqlite3.connect(path)
    try:
        rows = conn.execute("SELECT region, offset, state FROM region_offsets").fetchall()
    finally:
        conn.close()
    offsets = {}
    for region, offset, state in rows:
        if str(state).strip().lower() != "active":
            continue
        offsets[str(region).strip().lower()] = int(offset)
    return offsets


def _xlsx_cell_values(zf, sheet_name_to_part, sheet_name):
    shared = []
    try:
        shared_xml = zf.read("xl/sharedStrings.xml").decode("utf-8")
    except KeyError:
        shared_xml = None
    if shared_xml is not None:
        for si in re.findall(r"<si>(.*?)</si>", shared_xml, re.S):
            shared.append("".join(re.findall(r"<t[^>]*>(.*?)</t>", si, re.S)))

    xml = zf.read(sheet_name_to_part[sheet_name]).decode("utf-8")
    cells = {}
    for match in re.finditer(r"<c\s([^>]*?)/>|<c\s([^>]*?)>(.*?)</c>", xml, re.S):
        attrs = match.group(1) or match.group(2)
        body = match.group(3) or ""
        ref = re.search(r'r="([A-Z]+\d+)"', attrs)
        if ref is None:
            continue
        ctype = re.search(r't="([^"]+)"', attrs)
        ctype = ctype.group(1) if ctype else "n"
        if ctype == "inlineStr":
            text = "".join(re.findall(r"<t[^>]*>(.*?)</t>", body, re.S))
        elif ctype == "s":
            raw = re.search(r"<v[^>]*>(.*?)</v>", body, re.S)
            text = shared[int(raw.group(1))] if raw else ""
        elif ctype == "str":
            raw = re.search(r"<v[^>]*>(.*?)</v>", body, re.S)
            text = raw.group(1) if raw else ""
        else:
            raw = re.search(r"<v[^>]*>(.*?)</v>", body, re.S)
            text = raw.group(1) if raw else ""
        cells[ref.group(1)] = text.strip()
    return cells


def _load_tariff_tiers(path):
    with zipfile.ZipFile(path) as zf:
        workbook = zf.read("xl/workbook.xml").decode("utf-8")
        rels = zf.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        rel_target = dict(
            re.findall(r'Id="([^"]+)"[^>]*?Target="([^"]+)"', rels)
        )
        name_to_part = {}
        for attrs in re.findall(r"<sheet\s([^>]*?)/>", workbook):
            name = re.search(r'name="([^"]*)"', attrs).group(1)
            rid = re.search(r'r:id="([^"]*)"', attrs).group(1)
            target = rel_target[rid]
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            name_to_part[name] = target

        best = None
        for name in name_to_part:
            match = _TIER_SHEET_RE.match(name)
            if match is None:
                continue
            key = (int(match.group(1)), int(match.group(2)))
            if best is None or key > best[0]:
                best = (key, name)
        if best is None:
            raise ValueError("no tier sheet in %s" % path)

        cells = _xlsx_cell_values(zf, name_to_part, best[1])

    columns = {}
    rows = {}
    for ref, text in cells.items():
        match = _CELL_REF_RE.match(ref)
        column, rownum = match.group(1), int(match.group(2))
        if rownum == 1:
            columns[text.strip().lower()] = column
        else:
            rows.setdefault(rownum, {})[column] = text

    start_col = columns["start_wh"]
    bps_col = columns["bps"]
    tiers = []
    for rownum in sorted(rows):
        row = rows[rownum]
        start = row.get(start_col, "").strip()
        bps = row.get(bps_col, "").strip()
        if not start or not bps:
            continue
        tiers.append([int(Decimal(start)), None if bps.lower() == "calibrate" else int(Decimal(bps))])
    tiers.sort(key=lambda t: t[0])
    return tiers


def _docx_table_rows(path):
    with zipfile.ZipFile(path) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    table = re.search(r"<w:tbl>(.*?)</w:tbl>", xml, re.S)
    if table is None:
        return []
    rows = []
    for tr in re.findall(r"<w:tr>(.*?)</w:tr>", table.group(1), re.S):
        cells = []
        for tc in re.findall(r"<w:tc>(.*?)</w:tc>", tr, re.S):
            cells.append("".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", tc, re.S)))
        rows.append(cells)
    return rows


def _apply_seed_addendum(overrides, path):
    rows = _docx_table_rows(path)
    if not rows:
        return overrides
    header = [c.strip().lower() for c in rows[0]]
    account_at = header.index("account")
    seed_at = header.index("seed")
    for cells in rows[1:]:
        if len(cells) <= max(account_at, seed_at):
            continue
        account = cells[account_at].strip().upper()
        value = cells[seed_at].strip()
        if not account:
            continue
        if value.lower() == "remove":
            overrides.pop(account, None)
        else:
            overrides[account] = int(value)
    return overrides


def _load_policy(path):
    policy = {}
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().strip("'\"").strip()
            value = value.strip().strip("'\"").strip()
            policy[key] = value
    return policy


def _load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


OPTIONAL_RULE_KEYS = (
    "account_aliases",
    "region_aliases",
    "kind_aliases",
    "flag_aliases",
    "account_meter_modulus",
    "account_unit_divisor",
    "account_tariff_tiers",
    "account_tariff_credit_wh",
    "meter_reset_flag",
)


def resolve_rules(data_dir, scenario):
    roles = resolve_sources(data_dir)
    path = lambda role: os.path.join(data_dir, roles[role])

    coeff = _load_json(path("coeff"))
    window = coeff["scenario_windows"][scenario]

    overrides = {}
    for key, value in (_load_json(path("meterseeds")).get("overrides") or {}).items():
        overrides[key.strip().upper()] = int(value)
    overrides = _apply_seed_addendum(overrides, path("seedaddendum"))

    tiers = _load_tariff_tiers(path("tariff"))
    calibration = _load_json(path("calibration"))
    policy = _load_policy(path("policy"))

    staged = {
        "label": coeff["label"],
        "kind_weights": dict(coeff["kind_weights"]),
        "region_offsets": _load_region_offsets(path("regions")),
        "flag_penalties": dict(coeff["flag_penalties"]),
        "top_n": int(coeff["top_n"]),
        "meter_modulus": int(coeff["meter_modulus"]),
        "meter_seed": int(coeff["meter_seed"]),
        "tariff_tiers": tiers,
        "calibration": calibration,
    }
    if "unit_divisor" in coeff:
        staged["unit_divisor"] = int(coeff["unit_divisor"])
    if "tariff_bps" in coeff:
        staged["tariff_bps"] = int(coeff["tariff_bps"])

    filled_tiers, divisor = _fill_calibrated(staged)

    rules = {
        "label": coeff["label"],
        "window_start": int(window[0]),
        "window_end": int(window[1]),
        "kind_weights": staged["kind_weights"],
        "region_offsets": staged["region_offsets"],
        "flag_penalties": staged["flag_penalties"],
        "top_n": staged["top_n"],
        "meter_modulus": staged["meter_modulus"],
        "meter_seed": staged["meter_seed"],
        "meter_seed_overrides": overrides,
        "tariff_tiers": filled_tiers,
        "unit_divisor": divisor,
        "void_flag": policy["void_flag"].strip().lower(),
    }

    for key in OPTIONAL_RULE_KEYS:
        if key not in coeff:
            continue
        value = coeff[key]
        if key == "meter_reset_flag":
            rules[key] = str(value).strip().lower()
        elif key == "account_aliases":
            rules[key] = {
                k.strip().upper(): v.strip().upper() for k, v in value.items()
            }
        elif key in ("region_aliases", "kind_aliases", "flag_aliases"):
            rules[key] = {
                k.strip().lower(): v.strip().lower() for k, v in value.items()
            }
        elif key == "account_tariff_tiers":
            rules[key] = {
                k.strip().upper(): sorted(
                    ([int(t[0]), int(t[1])] for t in tier_list), key=lambda t: t[0]
                )
                for k, tier_list in value.items()
            }
        else:
            rules[key] = {k.strip().upper(): int(v) for k, v in value.items()}

    return dict(sorted(rules.items()))


# --------------------------------------------------------------------------
# authoritative corpus (section 1 step 6)
# --------------------------------------------------------------------------


def resolve_corpus_shards(data_dir):
    roles = resolve_sources(data_dir)
    entries = []
    with open(
        os.path.join(data_dir, roles["segments"]), "r", encoding="utf-8-sig"
    ) as fh:
        for line in fh:
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("superseded"):
                continue
            entries.append((int(entry["sequence"]), entry["file"]))
    entries.sort(key=lambda e: e[0])
    return [os.path.join(data_dir, name) for name in (e[1] for e in entries)]


def materialize_corpus(data_dir, dest_path):
    """Concatenate the authoritative shards into one CSV in corpus row order."""
    with open(dest_path, "w", encoding="utf-8", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(EVENT_FIELDS)
        for shard in resolve_corpus_shards(data_dir):
            for row in _iter_corpus_rows(shard):
                writer.writerow(row)
    return dest_path


def _iter_corpus_rows(events_path):
    ext = events_path.rsplit(".", 1)[-1].lower()
    if ext == "ndjson":
        with open(events_path, "r", encoding="utf-8-sig", newline="") as fh:
            for line in fh:
                if not line.strip():
                    continue
                obj = json.loads(line)
                row = {}
                for key, value in obj.items():
                    row[key.strip().lower()] = value
                yield [str(row[name]) for name in EVENT_FIELDS]
        return
    delimiter = "|" if ext == "psv" else ","
    with open(events_path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh, delimiter=delimiter)
        index = None
        for row in reader:
            if index is None:
                header = [cell.strip().lower() for cell in row]
                index = [header.index(name) for name in EVENT_FIELDS]
                continue
            if not row:
                continue
            if len(row) == 1 and not row[0].strip():
                continue
            yield [row[i] for i in index]


# --------------------------------------------------------------------------
# script entry point
# --------------------------------------------------------------------------


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: optimize.py EVENTS_FILE RULES_JSON\n")
        return 2
    sys.stdout.write(json.dumps(aggregate(argv[1], argv[2]), sort_keys=True))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
