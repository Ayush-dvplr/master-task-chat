#!/usr/bin/env python3
"""Telemetry rollup optimizer.

Recomputes the telemetry rollup described by /app/data/schema.md.

Public API:
    aggregate(events_path, rules_path) -> result object
    resolve_rules(data_dir, scenario)  -> resolved rules object

Command line:
    python3 /app/out/optimize.py EVENTS_FILE RULES_JSON

prints the aggregate result object to stdout as canonical JSON with sorted keys.

Standard library only.  No clock reads, no randomness, no process timing: the
aggregator is a pure function of (events file, rules file).
"""

from operator import itemgetter as _itemgetter
import csv
import io
import json
import os
import re
import sqlite3
import sys
import zipfile
from decimal import Decimal, ROUND_HALF_UP

MASK = 0xFFFFFFFF
CHECKSUM_BASE = 1315423911
COST_DIVISOR = 10000
FIELD_COLUMNS = ("id", "ts", "account", "region", "kind", "amount",
                 "units", "latency_ms", "flag", "meter", "energy_wh")
INT_FIELDS = ("ts", "amount", "units", "latency_ms", "meter", "energy_wh")
SCENARIO_ORDER = ("visible", "peak", "steady", "burst", "latency")
RULE_KEYS = ("label", "window_start", "window_end", "kind_weights",
             "region_offsets", "flag_penalties", "top_n", "meter_modulus",
             "meter_seed", "meter_seed_overrides", "tariff_tiers",
             "unit_divisor", "void_flag")
OPTIONAL_RULE_KEYS = ("account_aliases", "region_aliases", "kind_aliases",
                      "flag_aliases", "account_meter_modulus",
                      "account_unit_divisor", "account_tariff_tiers",
                      "account_tariff_credit_wh", "meter_reset_flag")
CONFIG_ROLES = ("baseline", "cost", "hardware", "queryplan", "indexcfg",
                "thresholds")
SOURCE_ROLES = ("coeff", "segments", "meterseeds", "seedaddendum", "regions",
                "tariff", "policy", "calibration") + CONFIG_ROLES
_ID_TAIL_RE = re.compile(r"[0-9]+$")


def half_up(numerator, denominator):
    """Exact decimal division rounded half up to an integer."""
    if denominator == 0:
        raise ZeroDivisionError("denominator is zero")
    if numerator < 0:
        # ROUND_HALF_UP rounds away from zero; the contract only ever applies
        # half_up to non-negative numerators, but keep it exact anyway.
        return -int((-Decimal(numerator) / Decimal(denominator)).quantize(
            Decimal(1), rounding=ROUND_HALF_UP))
    return int((Decimal(numerator) / Decimal(denominator)).quantize(
        Decimal(1), rounding=ROUND_HALF_UP))


def round3(numerator, denominator):
    return (Decimal(numerator) / Decimal(denominator)).quantize(
        Decimal("0.001"), rounding=ROUND_HALF_UP)


def id_number(norm_id):
    m = _ID_TAIL_RE.search(norm_id)
    return int(m.group()) if m else 0


# --------------------------------------------------------------------------
# Row readers (section 3)
# --------------------------------------------------------------------------

def _text(value):
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _split_row(line, delim):
    """Split one delimited row, honouring standard CSV quoting."""
    if '"' not in line:
        return line.split(delim)
    return next(csv.reader([line], delimiter=delim, quotechar='"'))


def _canon_names(names):
    """Column names of a header or key set, stripped and lower-cased."""
    out = []
    for name in names:
        if isinstance(name, str):
            out.append(name.strip().lower())
        else:
            out.append(str(name).strip().lower())
    return out


def _records(events_path):
    """Yield one tuple per data row, in FIELD_COLUMNS order.

    Values keep their file text (a `.ndjson` value may still be an integer;
    callers convert on use).  Missing columns yield "".  This is the hot read
    path of the aggregator: it never builds a per-row mapping.
    """
    ext = os.path.splitext(events_path)[1].lower()
    with open(events_path, "rb") as handle:
        data = handle.read()
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    text = data.decode("utf-8")
    width = len(FIELD_COLUMNS)

    if ext == ".ndjson":
        getter = None
        for line in text.splitlines():
            if not line or line.isspace():
                continue
            obj = json.loads(line)
            if getter is None:
                names = _canon_names(obj.keys())
                index = {}
                for i, name in enumerate(names):
                    if name not in index:
                        index[name] = i
                if all(name in index for name in FIELD_COLUMNS):
                    keys = tuple(tuple(obj)[index[name]]
                                 for name in FIELD_COLUMNS)
                    getter = _itemgetter(*keys)
                else:
                    getter = _partial_getter(index, obj.keys())
            try:
                yield getter(obj)
            except (KeyError, IndexError):
                yield _slow_record(obj, width)
        return

    if ext == ".psv":
        delim = "|"
    elif ext == ".csv":
        delim = ","
    else:
        delim = ","
    getter = None
    for line in text.splitlines():
        if not line or line.isspace():
            continue
        if getter is None:
            header = _split_row(line, delim)
            index = {}
            for i, name in enumerate(_canon_names(header)):
                if name not in index:
                    index[name] = i
            if all(name in index for name in FIELD_COLUMNS):
                getter = _itemgetter(*[index[name] for name in FIELD_COLUMNS])
            else:
                getter = _partial_getter(index, header)
            continue
        cells = _split_row(line, delim)
        try:
            yield getter(cells)
        except IndexError:
            yield _slow_record(dict(zip(_canon_names(cells), cells)), width)


def _partial_getter(index, source_names):
    """Getter for a file that does not carry every event column."""
    positions = [index.get(name) for name in FIELD_COLUMNS]

    def getter(row):
        if isinstance(row, dict):
            return tuple(row.get(name, "") if name in row else
                         (row[source_names[i]] if positions[i] is not None
                          else "") for i, name in enumerate(FIELD_COLUMNS))
        return tuple(row[positions[i]] if positions[i] is not None else ""
                     for i in range(len(FIELD_COLUMNS)))
    return getter


def _slow_record(obj, width):
    names = _canon_names(obj.keys())
    index = {}
    for i, name in enumerate(names):
        if name not in index:
            index[name] = i
    return tuple(obj[list(obj)[index[name]]] if name in index else ""
                 for name in FIELD_COLUMNS)


def read_rows(events_path):
    """Yield the data rows of an events file as dicts of raw field text."""
    for record in _records(events_path):
        row = {}
        for i, name in enumerate(FIELD_COLUMNS):
            value = record[i]
            if value is None:
                value = ""
            elif not isinstance(value, str):
                value = _text(value)
            row[name] = value
        yield row


# --------------------------------------------------------------------------
# Normalisation (section 3a step 1) and admission
# --------------------------------------------------------------------------

def _norm_aliases(aliases):
    """Alias map whose keys and values are normalised like a lower-cased field."""
    out = {}
    if aliases:
        for key, value in aliases.items():
            out[str(key).strip().lower()] = str(value).strip().lower()
    return out


def _norm_account_aliases(aliases):
    """Alias map whose keys and values are normalised like the account field."""
    out = {}
    if aliases:
        for key, value in aliases.items():
            out[str(key).strip().upper()] = str(value).strip().upper()
    return out


def admit_rows(rows, kind_weights, void_flag, aliases):
    """Apply section 3a to an iterable of raw row mappings.

    Returns (admitted, outcomes) where admitted is the list of normalised
    admitted rows in file order and outcomes classifies every raw row as one
    of "admitted", "replayed", "quarantined" or "withdrawn".

    This is the same admission the aggregate loop applies; it is exposed so a
    caller can report the row-by-row outcome counts of section 3a.
    """
    account_alias, region_alias, kind_alias, flag_alias = aliases
    seen = set()
    void_ids = set()
    candidates = []
    outcomes = []
    for row in rows:
        rid = row.get("id", "").strip().lower()
        kind = row.get("kind", "").strip().lower()
        kind = kind_alias.get(kind, kind)
        flag = row.get("flag", "").strip().lower()
        flag = flag_alias.get(flag, flag)
        if rid in seen:
            if void_flag is not None and flag == void_flag:
                void_ids.add(rid)
            outcomes.append("replayed")
            continue
        seen.add(rid)
        if kind not in kind_weights:
            outcomes.append("quarantined")
            continue
        # a first occurrence carrying the void flag is an ordinary event
        candidates.append((len(outcomes), rid, flag, row, kind))
        outcomes.append("admitted")
    withdrawn_ids = set()
    if void_ids:
        for _, rid, flag, _, _ in candidates:
            if rid in void_ids and rid not in withdrawn_ids:
                if void_flag is None or flag != void_flag:
                    withdrawn_ids.add(rid)
    if withdrawn_ids:
        for entry in candidates:
            if entry[1] in withdrawn_ids:
                outcomes[entry[0]] = "withdrawn"
    admitted = []
    for index, rid, flag, row, kind in candidates:
        if outcomes[index] != "admitted":
            continue
        account = row.get("account", "").strip().upper()
        account = account_alias.get(account, account)
        region = row.get("region", "").strip().lower()
        region = region_alias.get(region, region)
        admitted.append({
            "id": rid,
            "ts": int(row.get("ts", "0").strip() or 0),
            "account": account,
            "region": region,
            "kind": kind,
            "amount": int(row.get("amount", "0").strip() or 0),
            "units": int(row.get("units", "0").strip() or 0),
            "latency_ms": int(row.get("latency_ms", "0").strip() or 0),
            "flag": flag,
            "meter": int(row.get("meter", "0").strip() or 0),
        })
    return admitted, outcomes


# --------------------------------------------------------------------------
# Tariff helpers (section 5)
# --------------------------------------------------------------------------

def sort_tiers(tiers):
    return sorted(((int(s), b) for s, b in tiers), key=lambda p: p[0])


def tier_sum(tiers, lo, hi):
    """Sum of bps * watt-hours of [lo, hi) inside each tier."""
    total = 0
    n = len(tiers)
    for i in range(n):
        start, bps = tiers[i]
        end = tiers[i + 1][0] if i + 1 < n else None
        a = lo if lo > start else start
        b = hi if end is None or end > hi else end
        if b > a:
            total += (b - a) * bps
    return total


def _tier_rate_missing(bps):
    return bps is None or (isinstance(bps, str) and
                           bps.strip().lower() == "calibrate")


def _tier_rate_int(bps):
    if isinstance(bps, str):
        return int(bps.strip())
    return int(bps)


# --------------------------------------------------------------------------
# Calibration (section 4c)
# --------------------------------------------------------------------------

def calibrate_unit_divisor(controls, given=None):
    if given is not None:
        return int(given)
    best = None
    for d in range(1, 1000001):
        if all(half_up(c["usage_wh"], d) == c["energy_kwh"]
               for c in controls):
            best = d
            break
    if best is None:
        raise ValueError("no unit_divisor reproduces every energy control")
    return best


def calibrate_tier_rate(tiers, missing_index, controls):
    """Smallest integer bps >= 0 making every cost control reproduce."""
    for rate in range(0, 200001):
        trial = list(tiers)
        trial[missing_index] = (tiers[missing_index][0], rate)
        if all(half_up(tier_sum(trial, c["pre_wh"],
                                c["pre_wh"] + c["usage_wh"]),
                       COST_DIVISOR) == c["cost_cents"] for c in controls):
            return rate
    raise ValueError("no tier rate reproduces every cost control")


# --------------------------------------------------------------------------
# Rules resolution (sections 1, 2, 4, 4b, 4c)
# --------------------------------------------------------------------------

def _read_catalog_target(data_dir, catalog_name):
    path = os.path.join(data_dir, catalog_name)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute("SELECT target FROM catalog WHERE key = ?",
                           ("binding_registry",))
        row = cur.fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError("no binding_registry row in catalog %r" % catalog_name)
    return row[0]


def _read_ledger(data_dir, ledger_name):
    path = os.path.join(data_dir, ledger_name)
    with open(path, "r", encoding="utf-8", newline="") as handle:
        text = handle.read()
    lines = [l for l in text.splitlines() if l.strip()]
    delim = "\t" if "\t" in lines[0] else None
    rows = []
    header = None
    for line in lines:
        cells = line.split(delim) if delim else line.split()
        cells = [c.strip() for c in cells]
        if header is None:
            header = [c.strip().lower() for c in cells]
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def _resolve_ledger(data_dir, ledger_name):
    rows = _read_ledger(data_dir, ledger_name)
    best = {}
    for row in rows:
        if row.get("state") != "active":
            continue
        try:
            gen = int(row.get("generation"))
        except (TypeError, ValueError):
            continue
        role = row.get("role")
        cur = best.get(role)
        if cur is None or gen > cur[0]:
            best[role] = (gen, row.get("file"))
    return {role: name for role, (gen, name) in best.items()}


def _load_regions(data_dir, name):
    path = os.path.join(data_dir, name)
    conn = sqlite3.connect(path)
    try:
        cur = conn.execute(
            "SELECT region, offset, state FROM region_offsets")
        out = {}
        for region, offset, state in cur.fetchall():
            if state is not None and str(state).strip().lower() == "active":
                out[str(region).strip().lower()] = int(offset)
        return out
    finally:
        conn.close()


def _xlsx_sheets(path):
    """Return {sheet_name: [[cell text, ...], ...]} for an xlsx package."""
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            shared = _xlsx_shared_strings(zf.read("xl/sharedStrings.xml"))
        workbook = zf.read("xl/workbook.xml").decode("utf-8")
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            rels = _xlsx_rels(zf.read("xl/_rels/workbook.xml.rels").decode())
        sheets = _xlsx_sheet_targets(workbook, rels)
        out = {}
        for sheet_name, target in sheets.items():
            part = target if target.startswith("xl/") else "xl/" + target
            if part not in names:
                continue
            out[sheet_name] = _xlsx_rows(zf.read(part), shared)
        return out


def _xlsx_shared_strings(xml_bytes):
    text = xml_bytes.decode("utf-8")
    strings = []
    for item in re.findall(r"<si>(.*?)</si>", text, re.S):
        runs = re.findall(r"<t[^>]*>(.*?)</t>", item, re.S)
        strings.append(_xml_unescape("".join(runs)))
    return strings


def _xlsx_rels(rels_text):
    out = {}
    for rel in re.findall(r"<Relationship\b[^>]*/?>", rels_text):
        rid = re.search(r'Id="([^"]+)"', rel)
        target = re.search(r'Target="([^"]+)"', rel)
        if rid and target:
            out[rid.group(1)] = target.group(1)
    return out


def _xlsx_sheet_targets(workbook, rels):
    out = {}
    for tag in re.findall(r"<sheet\b[^>]*/?>", workbook):
        name = re.search(r'\bname="([^"]+)"', tag)
        rid = re.search(r'\br:id="([^"]+)"', tag)
        if name and rid and rid.group(1) in rels:
            out[name.group(1)] = rels[rid.group(1)]
    return out


def _xml_unescape(text):
    return (text.replace("&lt;", "<").replace("&gt;", ">")
            .replace("&quot;", '"').replace("&apos;", "'")
            .replace("&#10;", "\n").replace("&#13;", "\r").replace("&amp;", "&"))


def _xlsx_rows(xml_bytes, shared):
    text = xml_bytes.decode("utf-8")
    rows = []
    for row_xml in re.findall(r"<row\b[^>]*>(.*?)</row>", text, re.S):
        cells = {}
        for cell_xml in re.findall(r"<c\b[^>]*/?>.*?(?:</c>|$)", row_xml, re.S):
            ref = re.search(r'\br="([A-Z]+)([0-9]+)"', cell_xml)
            if not ref:
                continue
            col = _column_index(ref.group(1))
            value = _xlsx_cell_value(cell_xml, shared)
            cells[col] = value
        if cells:
            width = max(cells) + 1
            rows.append([cells.get(i, "") for i in range(width)])
    return rows


def _column_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _xlsx_cell_value(cell_xml, shared):
    inline = re.search(r"<is>(.*?)</is>", cell_xml, re.S)
    if inline:
        runs = re.findall(r"<t[^>]*>(.*?)</t>", inline.group(1), re.S)
        return _xml_unescape("".join(runs))
    shared_index = re.search(r'\bt="s"', cell_xml)
    value = re.search(r"<v>(.*?)</v>", cell_xml, re.S)
    if value:
        if shared_index:
            i = int(value.group(1))
            return shared[i] if i < len(shared) else ""
        return _xml_unescape(value.group(1))
    return ""


_TIER_SHEET_RE = re.compile(r"^tiers_(\d{4})Q([1-4])$")


def _load_tariff(data_dir, name):
    sheets = _xlsx_sheets(os.path.join(data_dir, name))
    best = None
    for sheet_name, rows in sheets.items():
        m = _TIER_SHEET_RE.match(sheet_name.strip())
        if not m:
            continue
        key = (int(m.group(1)), int(m.group(2)))
        if best is None or key > best[0]:
            best = (key, sheet_name, rows)
    if best is None:
        raise ValueError("no tier sheet in tariff book %r" % name)
    rows = best[2]
    if not rows:
        return []
    header = [str(c).strip().lower() for c in rows[0]]
    try:
        start_i = header.index("start_wh")
        bps_i = header.index("bps")
    except ValueError:
        start_i, bps_i = 0, 1
    tiers = []
    for row in rows[1:]:
        if len(row) <= max(start_i, bps_i):
            continue
        start = row[start_i]
        bps = row[bps_i]
        if str(start).strip() == "" or str(bps).strip() == "":
            continue
        start_val = int(float(str(start).strip()))
        bps_text = str(bps).strip()
        if bps_text.lower() == "calibrate":
            tiers.append((start_val, None))
        else:
            try:
                tiers.append((start_val, int(float(bps_text))))
            except ValueError:
                continue
    return tiers


def _load_policy(data_dir, name):
    path = os.path.join(data_dir, name)
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    out = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "#" in stripped:
            quote = None
            cut = None
            for i, ch in enumerate(stripped):
                if quote:
                    if ch == quote:
                        quote = None
                elif ch in "\"'":
                    quote = ch
                elif ch == "#":
                    cut = i
                    break
            if cut is not None:
                stripped = stripped[:cut].strip()
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        key = _unquote(key.strip())
        value = _unquote(value.strip())
        out[key] = value
    return out


def _unquote(text):
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def _load_addendum(data_dir, name):
    """Rows of the docx table: [(account text, seed text), ...]."""
    with zipfile.ZipFile(os.path.join(data_dir, name)) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    tables = re.findall(r"<w:tbl>(.*?)</w:tbl>", xml, re.S)
    rows = []
    for table in tables:
        for row_xml in re.findall(r"<w:tr\b[^>]*>(.*?)</w:tr>", table, re.S):
            cells = []
            for cell_xml in re.findall(r"<w:tc\b[^>]*>(.*?)</w:tc>",
                                       row_xml, re.S):
                runs = re.findall(r"<w:t[^>]*>(.*?)</w:t>", cell_xml, re.S)
                cells.append(_xml_unescape("".join(runs)))
            if cells:
                rows.append(cells)
    if rows:
        return rows[1:]
    return []


def _resolve_seed_overrides(base_overrides, addendum_rows):
    overrides = {}
    for key, value in (base_overrides or {}).items():
        k = str(key).strip().upper()
        overrides[k] = int(value)
    for cells in addendum_rows:
        if len(cells) < 2:
            continue
        account = cells[0].strip().upper()
        seed_text = cells[1].strip()
        if seed_text.lower() == "remove":
            overrides.pop(account, None)
        else:
            overrides[account] = int(seed_text)
    return overrides


def _exact_override(overrides, account):
    if account in overrides:
        return overrides[account]
    best = None
    best_len = -1
    for key, value in overrides.items():
        if key.endswith("*") and account.startswith(key[:-1]):
            if len(key) > best_len or (len(key) == best_len and key < best):
                best = key
                best_len = len(key)
    if best is None:
        return None
    return overrides[best]


def resolve_rules(data_dir, scenario):
    """Resolve the rules object for `scenario` from `data_dir`."""
    data_dir = str(data_dir)
    with open(os.path.join(data_dir, "ingest_handoff_notes.txt"),
              "r", encoding="utf-8") as handle:
        notes = handle.read()
    catalog_name = None
    for line in notes.splitlines():
        if line.startswith("catalog_ref:"):
            catalog_name = line.split(":", 1)[1].strip()
            break
    if not catalog_name:
        raise ValueError("no catalog_ref line in ingest_handoff_notes.txt")
    ledger_name = _read_catalog_target(data_dir, catalog_name)
    resolved = _resolve_ledger(data_dir, ledger_name)
    for role in SOURCE_ROLES:
        if role not in resolved:
            raise ValueError("ledger has no active row for role %r" % role)

    with open(os.path.join(data_dir, resolved["coeff"]),
              "r", encoding="utf-8") as handle:
        coeff = json.load(handle)

    with open(os.path.join(data_dir, resolved["meterseeds"]),
              "r", encoding="utf-8") as handle:
        meterseeds = json.load(handle)
    addendum_rows = _load_addendum(data_dir, resolved["seedaddendum"])
    overrides = _resolve_seed_overrides(meterseeds.get("overrides"),
                                        addendum_rows)

    region_offsets = _load_regions(data_dir, resolved["regions"])
    tariff_tiers = _load_tariff(data_dir, resolved["tariff"])
    policy = _load_policy(data_dir, resolved["policy"])
    with open(os.path.join(data_dir, resolved["calibration"]),
              "r", encoding="utf-8") as handle:
        calibration = json.load(handle)

    void_flag = policy.get("void_flag")
    void_flag = str(void_flag).strip().lower() if void_flag is not None else None

    rules = {}
    windows = coeff.get("scenario_windows") or {}
    if scenario in windows:
        window = windows[scenario]
    elif "window_start" in coeff and "window_end" in coeff:
        window = [coeff["window_start"], coeff["window_end"]]
    else:
        raise ValueError("no window for scenario %r" % scenario)
    rules["label"] = coeff.get("label")
    rules["window_start"] = int(window[0])
    rules["window_end"] = int(window[1])
    rules["kind_weights"] = dict(coeff.get("kind_weights") or {})
    rules["region_offsets"] = region_offsets or dict(
        coeff.get("region_offsets") or {})
    rules["flag_penalties"] = dict(coeff.get("flag_penalties") or {})
    rules["top_n"] = int(coeff.get("top_n", 0))
    rules["meter_modulus"] = int(coeff.get("meter_modulus", 1))
    rules["meter_seed"] = int(coeff.get("meter_seed", 0))
    rules["meter_seed_overrides"] = overrides

    tiers = sort_tiers(tariff_tiers) if tariff_tiers else sort_tiers(
        coeff.get("tariff_tiers") or [])
    if not tiers:
        bps = coeff.get("tariff_bps")
        if bps is None:
            raise ValueError("no tariff tiers available")
        tiers = [(0, int(bps))]
    missing = [i for i, (s, b) in enumerate(tiers) if _tier_rate_missing(b)]
    if len(missing) > 1:
        raise ValueError("more than one held-back tier rate")
    if missing:
        rate = calibrate_tier_rate(
            tiers, missing[0], calibration.get("cost") or [])
        tiers = list(tiers)
        tiers[missing[0]] = (tiers[missing[0]][0], rate)
    rules["tariff_tiers"] = [[s, b] for s, b in tiers]

    unit_divisor = coeff.get("unit_divisor")
    if unit_divisor is None:
        energy_controls = calibration.get("energy") or []
        if energy_controls:
            unit_divisor = calibrate_unit_divisor(energy_controls)
        else:
            unit_divisor = 1000
    rules["unit_divisor"] = int(unit_divisor)

    if void_flag is not None:
        rules["void_flag"] = void_flag

    for key in OPTIONAL_RULE_KEYS:
        if key in coeff and coeff[key] is not None:
            rules[key] = coeff[key]

    if "meter_reset_flag" in rules and rules["meter_reset_flag"] is not None:
        rules["meter_reset_flag"] = str(rules["meter_reset_flag"]).strip().lower()

    for key in ("kind_weights", "region_offsets", "flag_penalties"):
        rules[key] = {str(k).strip().lower(): int(v)
                      for k, v in rules[key].items()}
    if "account_aliases" in rules:
        rules["account_aliases"] = _norm_account_aliases(rules["account_aliases"])
    for key in ("region_aliases", "kind_aliases", "flag_aliases"):
        if key in rules:
            rules[key] = _norm_aliases(rules[key])
    if "account_meter_modulus" in rules:
        rules["account_meter_modulus"] = {
            str(k).strip().upper(): int(v)
            for k, v in rules["account_meter_modulus"].items()}
    if "account_unit_divisor" in rules:
        rules["account_unit_divisor"] = {
            str(k).strip().upper(): int(v)
            for k, v in rules["account_unit_divisor"].items()}
    if "account_tariff_tiers" in rules:
        rules["account_tariff_tiers"] = {
            str(k).strip().upper(): [[int(s), b] for s, b in tiers_]
            for k, tiers_ in rules["account_tariff_tiers"].items()}
    if "account_tariff_credit_wh" in rules:
        rules["account_tariff_credit_wh"] = {
            str(k).strip().upper(): int(v)
            for k, v in rules["account_tariff_credit_wh"].items()}

    return rules


def resolve_all(data_dir):
    """Resolve the raw sources once (used by the artifact builders)."""
    data_dir = str(data_dir)
    with open(os.path.join(data_dir, "ingest_handoff_notes.txt"),
              "r", encoding="utf-8") as handle:
        notes = handle.read()
    catalog_name = None
    for line in notes.splitlines():
        if line.startswith("catalog_ref:"):
            catalog_name = line.split(":", 1)[1].strip()
            break
    ledger_name = _read_catalog_target(data_dir, catalog_name)
    resolved = _resolve_ledger(data_dir, ledger_name)
    out = {"resolved": resolved,
           "catalog": catalog_name,
           "ledger": ledger_name}
    for role in CONFIG_ROLES:
        name = resolved.get(role)
        if name is None:
            continue
        with open(os.path.join(data_dir, name), "r", encoding="utf-8") as fh:
            out[role] = json.load(fh)
    return out


def corpus_files(data_dir):
    """The ordered list of authoritative shard files of the corpus."""
    resolved = resolve_all(data_dir)["resolved"]
    manifest = resolved["segments"]
    entries = []
    with open(os.path.join(data_dir, manifest), "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            entries.append(json.loads(line))
    live = [e for e in entries if not e.get("superseded")]
    live.sort(key=lambda e: int(e["sequence"]))
    return [e["file"] for e in live]


# --------------------------------------------------------------------------
# Aggregation (sections 3a, 5)
# --------------------------------------------------------------------------

def aggregate(events_path, rules_path):
    """Aggregate one events file against one resolved rules JSON file."""
    if isinstance(rules_path, dict):
        rules = rules_path
    else:
        with open(rules_path, "r", encoding="utf-8") as handle:
            rules = json.load(handle)

    kind_weights = {str(k).strip().lower(): int(v)
                    for k, v in (rules.get("kind_weights") or {}).items()}
    region_offsets = {str(k).strip().lower(): int(v)
                      for k, v in (rules.get("region_offsets") or {}).items()}
    flag_penalties = {str(k).strip().lower(): int(v)
                      for k, v in (rules.get("flag_penalties") or {}).items()}
    account_aliases = _norm_account_aliases(rules.get("account_aliases"))
    region_aliases = _norm_aliases(rules.get("region_aliases"))
    kind_aliases = _norm_aliases(rules.get("kind_aliases"))
    flag_aliases = _norm_aliases(rules.get("flag_aliases"))

    void_flag = rules.get("void_flag")
    if isinstance(void_flag, str):
        void_flag = void_flag.strip().lower()

    window_start = int(rules["window_start"])
    window_end = int(rules["window_end"])
    top_n = int(rules.get("top_n", 0))
    modulus = int(rules.get("meter_modulus", 1))
    seed = int(rules.get("meter_seed", 0))
    overrides = rules.get("meter_seed_overrides") or {}
    per_modulus = rules.get("account_meter_modulus") or {}
    per_divisor = rules.get("account_unit_divisor") or {}
    credit = rules.get("account_tariff_credit_wh") or {}
    reset_flag = rules.get("meter_reset_flag")
    if isinstance(reset_flag, str):
        reset_flag = reset_flag.strip().lower()

    base_tiers = rules.get("tariff_tiers")
    if base_tiers:
        base_tiers = [(int(s), (None if _tier_rate_missing(b) else b))
                      for s, b in base_tiers]
        base_tiers = sort_tiers([(s, b) for s, b in base_tiers])
    else:
        base_tiers = [(0, int(rules.get("tariff_bps", 0)))]
    per_tiers = {}
    for account, tiers_ in (rules.get("account_tariff_tiers") or {}).items():
        per_tiers[str(account).strip().upper()] = sort_tiers(tiers_)
    calibration = rules.get("calibration") or {}

    unit_divisor = rules.get("unit_divisor")
    if unit_divisor is None:
        energy_controls = calibration.get("energy") or []
        if energy_controls:
            unit_divisor = calibrate_unit_divisor(energy_controls)
        else:
            unit_divisor = 1000
    else:
        unit_divisor = int(unit_divisor)
    for account, tiers_ in per_tiers.items():
        missing = [i for i, (s, b) in enumerate(tiers_)
                   if _tier_rate_missing(b)]
        if len(missing) > 1:
            raise ValueError("more than one held-back tier rate for %r"
                             % account)
        if missing:
            rate = calibrate_tier_rate(
                tiers_, missing[0], calibration.get("cost") or [])
            tiers_ = list(tiers_)
            tiers_[missing[0]] = (tiers_[missing[0]][0], rate)
            per_tiers[account] = tiers_
    missing = [i for i, (s, b) in enumerate(base_tiers)
               if _tier_rate_missing(b)]
    if len(missing) > 1:
        raise ValueError("more than one held-back tier rate")
    if missing:
        rate = calibrate_tier_rate(
            base_tiers, missing[0], calibration.get("cost") or [])
        base_tiers = list(base_tiers)
        base_tiers[missing[0]] = (base_tiers[missing[0]][0], rate)

    # ---- pass 1: admission, replay and void (section 3a) --------------
    # Records are read in FIELD_COLUMNS order; positions are fixed there.
    ID, TS, ACCOUNT, REGION, KIND, AMOUNT, UNITS, LATENCY, FLAG, METER, _ = \
        range(len(FIELD_COLUMNS))
    admitted = []
    seen = set()
    void_ids = set()
    # Normalisation is a pure function of the field text, so each field's
    # canonical value is memoised: the corpus repeats a few dozen distinct
    # region, kind, flag and account spellings over thousands of rows.
    canon_kind = {}
    canon_flag = {}
    canon_account = {}
    canon_region = {}
    seen_add = seen.add
    void_add = void_ids.add
    admitted_append = admitted.append
    for record in _records(events_path):
        rid = record[ID]
        if not isinstance(rid, str):
            rid = _text(rid)
        rid = rid.strip().lower()
        raw_kind = record[KIND]
        kind = canon_kind.get(raw_kind)
        if kind is None:
            kind = raw_kind
            if not isinstance(kind, str):
                kind = _text(kind)
            kind = kind.strip().lower()
            kind = kind_aliases.get(kind, kind)
            canon_kind[raw_kind] = kind
        if rid in seen:
            if void_flag is not None:
                raw_flag = record[FLAG]
                flag = canon_flag.get(raw_flag)
                if flag is None:
                    if not isinstance(raw_flag, str):
                        raw_flag = _text(raw_flag)
                    flag = raw_flag.strip().lower()
                    flag = flag_aliases.get(flag, flag)
                    canon_flag[record[FLAG]] = flag
                if flag == void_flag:
                    void_add(rid)
            continue
        seen_add(rid)
        if kind not in kind_weights:
            continue
        raw_flag = record[FLAG]
        flag = canon_flag.get(raw_flag)
        if flag is None:
            if not isinstance(raw_flag, str):
                raw_flag = _text(raw_flag)
            flag = raw_flag.strip().lower()
            flag = flag_aliases.get(flag, flag)
            canon_flag[record[FLAG]] = flag
        raw_account = record[ACCOUNT]
        account = canon_account.get(raw_account)
        if account is None:
            if not isinstance(raw_account, str):
                raw_account = _text(raw_account)
            account = raw_account.strip().upper()
            account = account_aliases.get(account, account)
            canon_account[record[ACCOUNT]] = account
        raw_region = record[REGION]
        region = canon_region.get(raw_region)
        if region is None:
            if not isinstance(raw_region, str):
                raw_region = _text(raw_region)
            region = raw_region.strip().lower()
            region = region_aliases.get(region, region)
            canon_region[record[REGION]] = region
        admitted_append((
            rid,
            int(record[TS]),
            account,
            region,
            kind,
            int(record[AMOUNT]),
            int(record[UNITS]),
            int(record[LATENCY]),
            flag,
            int(record[METER]),
        ))
    if void_ids:
        # A notice withdraws the earlier non-void occurrence of the same id.
        # A void-flagged first occurrence is an ordinary event, and a notice
        # for an id whose only admitted occurrence is that void-flagged row
        # withdraws nothing.
        withdrawn_ids = set()
        for row in admitted:
            rid = row[0]
            if rid in void_ids and rid not in withdrawn_ids:
                flag = row[8]
                if void_flag is None or flag != void_flag:
                    withdrawn_ids.add(rid)
        if withdrawn_ids:
            keep = []
            for row in admitted:
                if row[0] in withdrawn_ids:
                    continue
                keep.append(row)
            admitted = keep

    # ---- pass 2: pre-window meter walk (also gives the window's start) --
    last_pre_meter = {}
    pre_wh = {}
    pre_prev = {}
    for (rid, ts, account, region, kind, amount, units, latency, flag,
         meter) in admitted:
        if ts >= window_start:
            continue
        acct_mod = per_modulus.get(account, modulus)
        prev = pre_prev.get(account)
        if prev is None:
            prev = _exact_override(overrides, account)
            if prev is None:
                prev = seed
        if reset_flag is not None and flag == reset_flag:
            delta = 0
        else:
            delta = (meter - prev) % acct_mod
        pre_prev[account] = meter
        pre_wh[account] = pre_wh.get(account, 0) + delta
        last_pre_meter[account] = meter

    # ---- pass 3: one pass over the windowed rows fills every group ----
    account_totals = {}
    region_totals = {}
    kind_totals = {}
    flag_counts = {}
    usage_wh = {}
    win_prev = {}
    checksum = 0
    event_count = 0

    for (rid, ts, account, region, kind, amount, units, latency, flag,
         meter) in admitted:
        if ts < window_start or ts >= window_end:
            continue
        acct_mod = per_modulus.get(account, modulus)
        prev = win_prev.get(account)
        if prev is None:
            if account in last_pre_meter:
                prev = last_pre_meter[account]
            else:
                prev = _exact_override(overrides, account)
                if prev is None:
                    prev = seed
        if reset_flag is not None and flag == reset_flag:
            delta = 0
        else:
            delta = (meter - prev) % acct_mod
        win_prev[account] = meter
        usage_wh[account] = usage_wh.get(account, 0) + delta
        event_count += 1
        score = (amount * units * kind_weights[kind]
                 + region_offsets.get(region, 0)
                 - flag_penalties.get(flag, 0) - latency // 10)
        account_totals[account] = account_totals.get(account, 0) + score
        region_totals[region] = region_totals.get(region, 0) + score
        kind_totals[kind] = kind_totals.get(kind, 0) + score
        flag_counts[flag] = flag_counts.get(flag, 0) + 1
        checksum = (checksum * CHECKSUM_BASE + score * event_count
                    + id_number(rid)) & MASK

    # ---- finalize ---------------------------------------------------
    account_totals = {k: account_totals[k] for k in sorted(account_totals)}
    region_totals = {k: region_totals[k] for k in sorted(region_totals)}
    kind_totals = {k: kind_totals[k] for k in sorted(kind_totals)}
    flag_counts = {k: flag_counts[k] for k in sorted(flag_counts)}

    top = sorted(account_totals.items(), key=lambda kv: (-kv[1], kv[0]))
    if top_n:
        top = top[:top_n]

    account_usage = {}
    account_energy = {}
    account_cost = {}
    for account in sorted(usage_wh):
        used = usage_wh[account]
        account_usage[account] = used
        divisor = per_divisor.get(account, unit_divisor)
        account_energy[account] = half_up(used, divisor)
        base = pre_wh.get(account, 0)
        credit_wh = credit.get(account, 0)
        if credit_wh:
            base = base - credit_wh
            if base < 0:
                base = 0
        tiers = per_tiers.get(account, base_tiers)
        account_cost[account] = half_up(tier_sum(tiers, base, base + used),
                                        COST_DIVISOR)

    return {
        "label": rules.get("label"),
        "window": [window_start, window_end],
        "event_count": event_count,
        "account_totals": account_totals,
        "region_totals": region_totals,
        "kind_totals": kind_totals,
        "flag_counts": flag_counts,
        "account_usage_wh": account_usage,
        "account_energy_kwh": account_energy,
        "account_cost_cents": account_cost,
        "top_accounts": [[k, v] for k, v in top],
        "checksum": checksum,
    }


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------

def main(argv):
    if len(argv) != 3:
        sys.stderr.write(
            "usage: python3 optimize.py EVENTS_FILE RULES_JSON\n")
        return 2
    result = aggregate(argv[1], argv[2])
    sys.stdout.write(json.dumps(result, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
