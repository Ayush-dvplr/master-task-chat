#!/usr/bin/env python3
"""HAS-7 Regional Household Activity Survey derivation.

Usage: python3 derive_survey.py DATA_DIR OUT_DIR

Reads one collection round of the survey from DATA_DIR and writes the complete
HAS-7 report set into OUT_DIR in a single run.  Every rule applied here comes
from the HAS-7 standard revision 7 that ships with the extract, including the
margin order and the raking rounding point, which the pilot record settles.
"""

import configparser
import csv
import json
import math
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from fractions import Fraction
from itertools import permutations

REFERENCE_PERIOD = "2026-H1"
REFERENCE_WAVE = 3
MARGIN_DIMENSIONS = ("region_tenure", "activity", "band")


# ---------------------------------------------------------------------------
# arithmetic and text
# ---------------------------------------------------------------------------

def rhd(num, den):
    """num/den rounded to the nearest whole number, halves away from zero."""
    if den == 0:
        return 0
    if den < 0:
        num, den = -num, -den
    if num >= 0:
        return (2 * num + den) // (2 * den)
    return -((-2 * num + den) // (2 * den))


def sqrt_nearest(value):
    """Square root of a non negative integer, rounded to the nearest whole."""
    if value <= 0:
        return 0
    root = math.isqrt(value)
    if (root + 1) * (root + 1) - value < value - root * root:
        return root + 1
    return root


def nfc(text):
    return unicodedata.normalize("NFC", text)


def is_active(value):
    return str(value).strip().upper() in ("Y", "YES", "TRUE")


def yn(flag):
    return "Y" if flag else "N"


UNIT_ID_RE = re.compile(r"^RH[-_.]([A-Z0-9]+)[-_.](\d+)$")


def canon_unit(value):
    """Fold any shipped spelling of a unit identifier onto its canonical form."""
    text = nfc(str(value)).strip().upper().replace("_", "-").replace(".", "-")
    match = UNIT_ID_RE.match(text)
    if not match:
        return None
    return "RH-%s-%s" % (match.group(1), match.group(2).zfill(6))


def parse_instant(value):
    """Canonical UTC instant of a shipped timestamp, fraction truncated."""
    text = nfc(str(value)).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    moment = moment.astimezone(timezone.utc).replace(microsecond=0)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def median_lower(values):
    """Median, with the lower of the two central values for an even count."""
    ordered = sorted(values)
    count = len(ordered)
    if count == 0:
        return 0
    if count % 2 == 1:
        return ordered[count // 2]
    return ordered[count // 2 - 1]


# ---------------------------------------------------------------------------
# file readers
# ---------------------------------------------------------------------------

def read_delimited(path, delimiter):
    """Delimited file.  Values are kept exactly as written: repairs in the
    standard, such as the whitespace repair on a frame serial, must see them."""
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle, delimiter=delimiter))
    if not rows:
        return []
    header = [name.strip() for name in rows[0]]
    out = []
    for row in rows[1:]:
        if not row:
            continue
        record = {}
        for index, name in enumerate(header):
            record[name] = row[index] if index < len(row) else ""
        out.append(record)
    return out


def read_csv(path):
    return read_delimited(path, ",")


def read_tsv(path):
    return read_delimited(path, "\t")


def read_psv(path):
    return read_delimited(path, "|")


def read_fwf(path):
    """Fixed width file, its header line gives the column starts."""
    with open(path, encoding="utf-8") as handle:
        lines = handle.read().split("\n")
    if not lines:
        return []
    header = lines[0]
    tokens = [(m.group(0), m.start()) for m in re.finditer(r"\S+", header)]
    columns = []
    for index, (name, start) in enumerate(tokens):
        end = tokens[index + 1][1] if index + 1 < len(tokens) else len(header)
        columns.append((name.strip(), start, end))
    out = []
    for line in lines[1:]:
        if not line.strip():
            continue
        record = {}
        for name, start, end in columns:
            record[name] = line[start:end].strip()
        out.append(record)
    return out


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                out.append(json.loads(line))
    return out


def read_keyed(path):
    """`key = value` file, blank lines and `#` comments ignored."""
    out = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


def read_ini(path):
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.read(path, encoding="utf-8")
    return parser


def _toml_split(text):
    parts = []
    depth = 0
    quote = False
    start = 0
    for index, char in enumerate(text):
        if char == '"':
            quote = not quote
        elif char == "[" and not quote:
            depth += 1
        elif char == "]" and not quote:
            depth -= 1
        elif char == "," and depth == 0 and not quote:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return parts


def _toml_value(text):
    if text.startswith("[") and text.endswith("]"):
        inner = text[1:-1].strip()
        if not inner:
            return []
        return [_toml_value(part.strip()) for part in _toml_split(inner)]
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        return text[1:-1]
    if text in ("true", "false"):
        return text == "true"
    if re.match(r"^-?\d+$", text):
        return int(text)
    return text


def read_toml(path):
    """The subset of TOML the extract uses: tables, arrays of tables, values."""
    root = {}
    current = root
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[["):
                current = {}
                root.setdefault(line[2:-2].strip(), []).append(current)
                continue
            if line.startswith("["):
                current = root.setdefault(line[1:-1].strip(), {})
                continue
            key, _, value = line.partition("=")
            current[key.strip()] = _toml_value(value.strip())
    return root


def read_sexp(path):
    """One s-expression per line, parsed into nested lists."""
    out = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith(";"):
                continue
            stack = [[]]
            for token in re.findall(r"\(|\)|[^\s()]+", line):
                if token == "(":
                    node = []
                    stack[-1].append(node)
                    stack.append(node)
                elif token == ")":
                    if len(stack) > 1:
                        stack.pop()
                else:
                    stack[-1].append(token)
            if stack[0]:
                out.append(stack[0][0])
    return out


def read_rfc822(path):
    """Message style records, one per block of header lines."""
    records = []
    current = {}
    with open(path, encoding="utf-8") as handle:
        for raw in handle:
            line = raw.rstrip("\n")
            if not line.strip():
                if current:
                    records.append(current)
                    current = {}
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                current[key.strip().lower()] = value.strip()
            elif current:
                last = list(current)[-1]
                current[last] = (current[last] + " " + line.strip()).strip()
        if current:
            records.append(current)
    return records


RFC5424_RE = re.compile(r"^<\d+>\d+\s+(\S+)\s+\S+\s+\S+\s+\S+\s+\S+\s+\[(.*)\]\s*$")
SD_PAIR_RE = re.compile(r'(\w+)="([^"]*)"')


def read_rfc5424(path):
    out = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            match = RFC5424_RE.match(line)
            if not match:
                continue
            record = dict(SD_PAIR_RE.findall(match.group(2)))
            record["timestamp"] = match.group(1)
            out.append(record)
    return out


LOGFMT_RE = re.compile(r'(\w+)=(?:"([^"]*)"|(\S*))')


def read_logfmt(path):
    out = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            record = {}
            for match in LOGFMT_RE.finditer(line):
                record[match.group(1)] = (match.group(2) if match.group(2) is not None
                                         else match.group(3))
            out.append(record)
    return out


def write_json(path, payload):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False))
        handle.write("\n")


def write_delimited(path, header, rows, delimiter):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(delimiter.join(header) + "\n")
        for row in rows:
            handle.write(delimiter.join(str(value) for value in row) + "\n")


# ---------------------------------------------------------------------------
# the round
# ---------------------------------------------------------------------------

class Round(object):
    """One collection round: every register read once and resolved."""

    def __init__(self, data_dir):
        self.dir = data_dir
        self.corrections = []
        self._read_reference()
        self._read_rules()
        self._read_frame()
        self._read_contact()
        self._read_interviews()
        self._read_benchmarks()
        self._resolve_units()

    def path(self, name):
        return os.path.join(self.dir, name)

    # ----------------------------------------------------------- references
    def _read_reference(self):
        self.regions = {}
        for row in read_csv(self.path("ref__region-codes.csv")):
            if not is_active(row.get("active")):
                continue
            code = nfc(row["region_code"]).strip().upper()
            self.regions[code] = {
                "name": nfc(row["region_name"]).strip(),
                "rank_order": int(row["rank_order"]),
            }

        self.strata = {}
        for row in read_tsv(self.path("ref__stratum-params.tsv")):
            if not is_active(row.get("active")):
                continue
            code = nfc(row["stratum_code"]).strip()
            self.strata[code] = {
                "region": row["region_code"].strip().upper(),
                "group": nfc(row["stratum_group"]).strip(),
                "population_units": int(row["population_units"]),
                "collapse_partner": nfc(row["collapse_partner"]).strip(),
            }
        self.stratum_by_name = {}
        for code, info in self.strata.items():
            region_name = self.regions[info["region"]]["name"]
            self.stratum_by_name[nfc(region_name + " " + info["group"])] = code

        fields = {}
        for key, value in read_keyed(self.path("ref__band-definitions.properties")).items():
            parts = key.split(".")
            if len(parts) == 3 and parts[0] == "band":
                fields.setdefault(parts[1], {})[parts[2]] = value
        self.band_defs = {}
        for code, values in fields.items():
            self.band_defs[code] = {
                "lower": int(values["lower_hours_inclusive"]),
                "upper": int(values["upper_hours_inclusive"]),
                "sort_rank": int(values["sort_rank"]),
            }
        self.band_order = [code for code, _ in sorted(
            self.band_defs.items(), key=lambda item: (item[1]["sort_rank"], item[0]))]

        self.contact_bands = []
        for form in read_sexp(self.path("ref__contact-bands.sexp")):
            if not form or form[0] != "contact-band":
                continue
            pairs = {item[0]: item[1] for item in form[1:]
                     if isinstance(item, list) and len(item) == 2}
            if not is_active(pairs.get("active", "yes")):
                continue
            self.contact_bands.append({
                "code": nfc(pairs["code"]).strip(),
                "min": int(pairs["min-attempts"]),
                "max": int(pairs["max-attempts"]),
                "sort_rank": int(pairs["sort-rank"]),
            })
        self.contact_bands.sort(key=lambda band: (band["sort_rank"], band["code"]))

        self.precedence = {}
        for row in read_csv(self.path("rules__disposition-precedence.csv")):
            if not is_active(row.get("active")):
                continue
            self.precedence[nfc(row["disposition_code"]).strip()] = {
                "severity_rank": int(row["severity_rank"]),
                "eligible": is_active(row["eligible"]),
                "responding": is_active(row["responding"]),
                "superseded": is_active(row["superseded"]),
            }

    # ---------------------------------------------------------------- rules
    def _read_rules(self):
        raking = read_ini(self.path("rules__margin-order.ini"))
        self.tolerance_uw = int(raking["raking"]["tolerance_uw"])
        self.max_iterations = int(raking["raking"]["max_iterations"])
        self.rule_margin_order = []
        for section in raking.sections():
            if not section.startswith("margin."):
                continue
            if not is_active(raking[section].get("active", "yes")):
                continue
            dimension = raking[section].get("control_dimension", "").strip()
            if dimension in MARGIN_DIMENSIONS and dimension not in self.rule_margin_order:
                self.rule_margin_order.append(dimension)

        trimming = read_keyed(self.path("rules__trimming.conf"))
        self.trim_ratio_bp = int(trimming["trim_ratio_bp"])
        self.trim_trigger_deff_bp = int(trimming["trim_trigger_deff_bp"])

        cells = read_toml(self.path("rules__adjustment-cells.toml"))
        self.min_response_rate_bp = int(cells["min_response_rate_bp"])
        self.min_cell_count = int(cells["min_cell_count"])
        self.max_collapse_rounds = int(cells["max_collapse_rounds"])

        disclosure = read_toml(self.path("disclosure__parameters.toml"))
        self.min_publish_count = int(disclosure["min_publish_count"])
        self.max_publish_cv_bp = int(disclosure["max_publish_cv_bp"])
        self.dominance_bp = int(disclosure["dominance_bp"])
        self.max_cascade_rounds = int(disclosure["max_cascade_rounds"])

        registry = {}
        for row in read_csv(self.path("disclosure__cell-registry.csv")):
            if not is_active(row.get("active")):
                continue
            table = row["table_name"].strip()
            axis = row["axis"].strip()
            if axis not in ("row", "column"):
                continue
            registry.setdefault(table, {"row": [], "column": []})[axis].append({
                "level": nfc(row["level_key"]).strip(),
                "sort_rank": int(row["sort_rank"]),
            })
        self.tables = {}
        for table in sorted(registry):
            entry = registry[table]
            entry["row"].sort(key=lambda level: (level["sort_rank"], level["level"]))
            entry["column"].sort(key=lambda level: (level["sort_rank"], level["level"]))
            self.tables[table] = entry

    # ---------------------------------------------------------------- frame
    def _read_frame(self):
        self.repair_counts = {code: 0 for code in
                              ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8")}
        in_frame = []
        records = []
        records.extend(read_csv(self.path("frame__register-a.csv")))
        records.extend(read_tsv(self.path("frame__register-b.tsv")))
        for row in read_fwf(self.path("frame__register-c.fwf")):
            records.append({
                "record_id": row["record_id"],
                "region_code": row["reg"],
                "serial": row["serial"],
                "stratum": row["strat"],
                "psu_code": nfc(row["psu"]).strip(),
                "vintage_rank": row["vr"],
                "edit_timestamp": row["edit_timestamp"],
                "tenure": row["tenure"],
            })
        for row in records:
            serial = row["serial"]
            m1 = serial != serial.strip()
            if m1:
                serial = serial.strip()
            m2 = len(serial) < 6
            if m2:
                serial = serial.zfill(6)
            region = row["region_code"]
            m3 = region != region.upper()
            if m3:
                region = region.upper()
            stratum = nfc(row["stratum"]).strip()
            m7 = False
            if stratum not in self.strata:
                if stratum in self.stratum_by_name:
                    stratum = self.stratum_by_name[stratum]
                    m7 = True
                else:
                    continue
            if m1:
                self.repair_counts["M1"] += 1
            if m2:
                self.repair_counts["M2"] += 1
            if m3:
                self.repair_counts["M3"] += 1
            if m7:
                self.repair_counts["M7"] += 1
            in_frame.append({
                "record_id": row["record_id"].strip(),
                "region": region,
                "serial": serial,
                "stratum": stratum,
                "psu_code": nfc(row["psu_code"]).strip(),
                "vintage_rank": int(row["vintage_rank"]),
                "edit_timestamp": parse_instant(row["edit_timestamp"]),
                "tenure": nfc(row["tenure"]).strip(),
            })

        identities = {}
        for record in in_frame:
            identities.setdefault((record["region"], record["serial"]), []).append(record)
        self.discarded_record_ids = []
        survivors = []
        for key in sorted(identities):
            group = identities[key]
            best = max(group, key=lambda r: (r["vintage_rank"], r["edit_timestamp"],
                                             r["record_id"]))
            for record in group:
                if record is not best:
                    self.discarded_record_ids.append(record["record_id"])
            survivors.append(best)
        self.discarded_record_ids.sort()
        self.repair_counts["M8"] = len(self.discarded_record_ids)

        reissue = {}
        for row in read_jsonl(self.path("frame__register-d.jsonl")):
            unit = canon_unit(row.get("unit_id"))
            psu = str(row.get("psu_code", "")).strip()
            if unit is None or psu == "":
                continue
            record_id = str(row.get("record_id", "")).strip()
            if unit not in reissue or record_id > reissue[unit][0]:
                reissue[unit] = (record_id, psu)

        addresses = {}
        for block in read_rfc822(self.path("frame__addresses.rfc822")):
            if not is_active(block.get("active", "yes")):
                continue
            unit = canon_unit(block.get("unit-id", ""))
            if unit is not None and unit not in addresses:
                addresses[unit] = block

        subsample = read_keyed(self.path("frame__subsample.conf"))
        self.subsample_factor_bp = int(subsample.get("subsample_factor_bp", 10000))
        subsampled = {}
        for key, value in subsample.items():
            parts = key.split(".")
            if len(parts) == 3 and parts[0] == "unit" and parts[2] == "subsampled":
                unit = canon_unit(parts[1])
                if unit is not None:
                    subsampled[unit] = is_active(value)

        self.units = {}
        for record in survivors:
            unit = "RH-%s-%s" % (record["region"], record["serial"])
            address = addresses.get(unit, {})
            dwelling = address.get("dwelling-units", "").strip()
            if dwelling == "":
                dwelling_units = 1
                self.repair_counts["M4"] += 1
            else:
                dwelling_units = int(dwelling)
            psu = record["psu_code"]
            if psu == "" and unit in reissue:
                psu = reissue[unit][1]
            self.units[unit] = {
                "unit_id": unit,
                "region": record["region"],
                "serial": record["serial"],
                "stratum": record["stratum"],
                "psu": psu,
                "tenure": record["tenure"],
                "dwelling_units": dwelling_units,
                "subsampled": bool(subsampled.get(unit, False)),
                "parent": None,
            }

        self.self_referencing_units = []
        self.dangling_parent_units = []
        for unit in sorted(self.units):
            address = addresses.get(unit, {})
            parent_raw = address.get("parent-unit", "").strip()
            parent = canon_unit(parent_raw) if parent_raw else None
            if parent is None:
                continue
            if parent == unit:
                self.repair_counts["M5"] += 1
                self.self_referencing_units.append(unit)
            elif parent not in self.units:
                self.repair_counts["M6"] += 1
                self.dangling_parent_units.append(unit)
            else:
                self.units[unit]["parent"] = parent
        self.self_referencing_units.sort()
        self.dangling_parent_units.sort()
        self.resolved_unit_count = len(self.units)

    # -------------------------------------------------------------- contact
    def _read_contact(self):
        self.attempts = []

        def add(unit, wave, attempt_no, instant, outcome):
            if unit is None:
                return
            self.attempts.append((unit, wave, attempt_no, instant, outcome))

        for row in read_rfc5424(self.path("contact__log-w1.rfc5424")):
            if not is_active(row.get("active", "yes")):
                continue
            add(canon_unit(row.get("unit")), int(row["wave"]), int(row["attempt"]),
                parse_instant(row["timestamp"]), row.get("outcome", "").strip())

        for name in ("contact__log-w2.logfmt", "contact__log-w3.logfmt"):
            for row in read_logfmt(self.path(name)):
                if not is_active(row.get("active", "yes")):
                    continue
                unit = canon_unit(row.get("unit"))
                wave = int(row["wave"])
                attempt_no = int(row["attempt"])
                instant = parse_instant(row["ts"])
                if "correction" in row:
                    self.corrections.append((unit, wave, attempt_no, instant,
                                             row["correction"].strip()))
                else:
                    add(unit, wave, attempt_no, instant, row.get("outcome", "").strip())

        for row in read_csv(self.path("contact__outcomes.csv")):
            if not is_active(row.get("active")):
                continue
            add(canon_unit(row["unit_id"]), int(row["wave"]), int(row["attempt_no"]),
                parse_instant(row["contact_datetime"]), row["outcome_code"].strip())

        for row in read_jsonl(self.path("contact__reissues.jsonl")):
            if not is_active(row.get("active")):
                continue
            add(canon_unit(row["unit_id"]), int(row["wave"]), int(row["attempt_no"]),
                parse_instant(row["contact_datetime"]), row["outcome_code"].strip())

    # ----------------------------------------------------------- interviews
    def _read_interviews(self):
        specs = [
            ("interview__w1-q1.csv", "csv"),
            ("interview__w1-q2.psv", "psv"),
            ("interview__w1-q3.jsonl", "jsonl"),
            ("interview__w1-q4.tsv", "tsv"),
            ("interview__w2-q1.csv", "csv"),
            ("interview__w2-q2.fwf", "fwf"),
            ("interview__w2-q3.jsonl", "jsonl"),
            ("interview__w2-q4.psv", "psv"),
            ("interview__w3-q1.csv", "csv"),
            ("interview__w3-q2.tsv", "tsv"),
            ("interview__w3-q3.fwf", "fwf"),
            ("interview__w3-q4.psv", "psv"),
        ]
        interviews = {}
        for name, kind in specs:
            if kind == "csv":
                rows = read_csv(self.path(name))
            elif kind == "tsv":
                rows = read_tsv(self.path(name))
            elif kind == "psv":
                rows = read_psv(self.path(name))
            elif kind == "fwf":
                rows = read_fwf(self.path(name))
            else:
                rows = read_jsonl(self.path(name))
            for row in rows:
                if not is_active(row.get("active")):
                    continue
                unit = canon_unit(row.get("unit_id"))
                if unit is None:
                    continue
                hours = str(row.get("hours_worked", "")).strip()
                interviews[(unit, int(row["wave"]))] = {
                    "activity": nfc(row.get("activity_code", "")).strip(),
                    "sector": nfc(row.get("sector_code", "")).strip(),
                    "hours": int(hours) if hours != "" else None,
                }
        self.interviews = interviews

        self.prior_bands = {1: {}, 2: {}}
        for row in read_csv(self.path("prior__wave1-bands.csv")):
            if not is_active(row.get("active")):
                continue
            unit = canon_unit(row["unit_id"])
            if unit is not None:
                self.prior_bands[1][unit] = nfc(row["prior_band"]).strip()
        for row in read_jsonl(self.path("prior__wave2-bands.jsonl")):
            if not is_active(row.get("active")):
                continue
            unit = canon_unit(row["unit_id"])
            if unit is not None:
                self.prior_bands[2][unit] = nfc(row["prior_band"]).strip()

    # ----------------------------------------------------------- benchmarks
    def _read_benchmarks(self):
        conversions = {}
        for row in read_csv(self.path("bench__unit-conversions.csv")):
            if not is_active(row.get("active")):
                continue
            conversions[row["unit_name"].strip()] = int(row["persons_per_unit"])

        offers = {}

        def offer(dimension, level, rank, date, source, value, unit):
            unit = unit.strip()
            if unit not in conversions or dimension not in MARGIN_DIMENSIONS:
                return
            offers.setdefault((dimension, level), []).append({
                "rank": int(rank),
                "published_date": nfc(date).strip(),
                "source_id": nfc(source).strip(),
                "value": Fraction(value.strip()) * conversions[unit] * 1000000,
            })

        for row in read_csv(self.path("bench__activity-v1.csv")):
            if row["reference_period"].strip() != REFERENCE_PERIOD:
                continue
            offer("activity", nfc(row["level_key"]).strip(), row["rank"], row["published_date"],
                  row["source_id"], row["value"], row["unit"])

        for name in ("bench__activity-v2.json", "bench__region-tenure-v1.json"):
            data = read_json(self.path(name))
            for entry in data.get("series", []):
                if str(entry.get("reference_period", "")).strip() != REFERENCE_PERIOD:
                    continue
                offer(nfc(data["dimension"]).strip(), nfc(entry["key"]).strip(), entry["rank"],
                      nfc(data["published_date"]).strip(), nfc(data["source_id"]).strip(),
                      entry["value"], data["unit"])

        properties = read_keyed(self.path("bench__band-v1.properties"))
        series = {}
        for key, value in properties.items():
            parts = key.split(".")
            if len(parts) == 3 and parts[0] == "series":
                series.setdefault(parts[1], {})[parts[2]] = value
        for fields in series.values():
            if fields.get("reference_period", "").strip() != REFERENCE_PERIOD:
                continue
            offer(nfc(properties["dimension"]).strip(), nfc(fields["key"]).strip(), fields["rank"],
                  nfc(properties["published_date"]).strip(), nfc(properties["source_id"]).strip(),
                  fields["value"], properties["unit"])

        for name in ("bench__band-v2.toml", "bench__region-tenure-v2.toml"):
            data = read_toml(self.path(name))
            for entry in data.get("series", []):
                if str(entry.get("reference_period", "")).strip() != REFERENCE_PERIOD:
                    continue
                offer(nfc(data["dimension"]).strip(), nfc(entry["key"]).strip(), entry["rank"],
                      nfc(data["published_date"]).strip(), nfc(data["source_id"]).strip(),
                      entry["value"], data["unit"])

        data = read_ini(self.path("bench__region-tenure-v3.ini"))
        meta = data["meta"]
        for section in data.sections():
            if not section.startswith("series"):
                continue
            row = data[section]
            if row["reference_period"].strip() != REFERENCE_PERIOD:
                continue
            offer(nfc(meta["dimension"]).strip(), nfc(row["key"]).strip(), row["rank"],
                  nfc(meta["published_date"]).strip(), nfc(meta["source_id"]).strip(),
                  row["value"], meta["unit"])

        self.control_totals = {}
        self.control_source = {}
        for (dimension, level), choices in offers.items():
            best = max(choices, key=lambda o: (o["rank"], o["published_date"], o["source_id"]))
            self.control_totals.setdefault(dimension, {})[level] = rhd(
                best["value"].numerator, best["value"].denominator)
            self.control_source[(dimension, level)] = (best["rank"], best["source_id"])
        for dimension in MARGIN_DIMENSIONS:
            self.control_totals.setdefault(dimension, {})

    # ---------------------------------------------------------- unit level
    def _resolve_units(self):
        counts = {}
        for info in self.units.values():
            counts[info["stratum"]] = counts.get(info["stratum"], 0) + 1
        for unit, info in self.units.items():
            stratum = self.strata[info["stratum"]]
            weight = rhd(stratum["population_units"] * 1000000, counts[info["stratum"]])
            if info["subsampled"]:
                weight = rhd(weight * 10000, self.subsample_factor_bp)
            info["design_weight"] = weight

        net = {}
        for unit, wave, attempt_no, instant, kind in self.corrections:
            key = (unit, wave, attempt_no)
            previous = net.get(key)
            if previous is None or instant > previous[0] or (instant == previous[0]
                                                            and kind == "reinstate"):
                net[key] = (instant, kind)
        voided = set(key for key, value in net.items() if value[1] == "void")

        self.attempt_counts = {}
        for unit, wave, attempt_no, instant, outcome in self.attempts:
            key = (unit, wave)
            self.attempt_counts[key] = self.attempt_counts.get(key, 0) + 1

        best = {}
        for unit, wave, attempt_no, instant, outcome in self.attempts:
            if (unit, wave, attempt_no) in voided:
                continue
            flags = self.precedence.get(outcome)
            if flags is None:
                continue
            key = (unit, wave)
            rank = (flags["severity_rank"], instant, attempt_no)
            if key not in best or rank > best[key][0]:
                best[key] = (rank, outcome, attempt_no, instant)
        self.disposition = {}
        for key in best:
            _, outcome, attempt_no, instant = best[key]
            self.disposition[key] = {"disposition": outcome, "attempt_no": attempt_no,
                                     "resolved_utc": instant}

        self.eligible = set()
        self.responding = set()
        self.superseded_units = []
        for unit in sorted(self.units):
            resolved = self.disposition.get((unit, REFERENCE_WAVE))
            if resolved is None:
                continue
            flags = self.precedence.get(resolved["disposition"], {})
            info = self.units[unit]
            if flags.get("eligible") and info["dwelling_units"] != 0:
                self.eligible.add(unit)
            if flags.get("superseded"):
                self.superseded_units.append(unit)
            if (unit in self.eligible and flags.get("responding") and not flags.get("superseded")
                    and (unit, REFERENCE_WAVE) in self.interviews):
                self.responding.add(unit)

        def contact_band(unit):
            count = (self.attempt_counts.get((unit, 1), 0)
                     + self.attempt_counts.get((unit, 2), 0))
            for band in self.contact_bands:
                if band["min"] <= count <= band["max"]:
                    return band["code"]
            return self.contact_bands[-1]["code"] if self.contact_bands else ""

        def band_of_hours(hours):
            for code in self.band_order:
                limits = self.band_defs[code]
                if limits["lower"] <= hours <= limits["upper"]:
                    return code
            return self.band_order[0] if self.band_order else ""

        zero_band = band_of_hours(0)
        for unit, info in self.units.items():
            info["contact_band"] = contact_band(unit)
            wave1 = self.interviews.get((unit, 1))
            if wave1 is None:
                info["band_wave1"] = None
            elif wave1["hours"] is None:
                info["band_wave1"] = self.prior_bands[1].get(unit) or zero_band
            else:
                info["band_wave1"] = band_of_hours(wave1["hours"])
            wave2 = self.interviews.get((unit, 2))
            if wave2 is not None and wave2["hours"] is not None:
                info["band_ref"] = band_of_hours(wave2["hours"])
            else:
                info["band_ref"] = (self.prior_bands[2].get(unit)
                                    or self.prior_bands[1].get(unit) or zero_band)
            reference = self.interviews.get((unit, REFERENCE_WAVE))
            info["activity_ref"] = reference["activity"] if reference else ""
            info["sector_ref"] = reference["sector"] if reference else ""
            info["region_tenure"] = "%s|%s" % (info["region"], info["tenure"])

        self.margin_order, self.round_each_margin = self._calibrate_pilot()

    def margin_level(self, unit, dimension):
        info = self.units[unit]
        if dimension == "region_tenure":
            return info["region_tenure"]
        if dimension == "activity":
            return info["activity_ref"]
        return info["band_ref"]

    # --------------------------------------------------------------- pilot
    def _calibrate_pilot(self):
        """The pilot round settles the margin order and the rounding point."""
        pilot = read_json(self.path("calib__pilot-round.json"))
        published = pilot.get("published", {})
        target_iterations = published.get("iterations_used")
        target_totals = published.get("raked_totals_uw", {})
        units = [unit for unit in pilot.get("units", []) if is_active(unit.get("active", "yes"))]
        if not units or not pilot.get("controls_uw"):
            return list(MARGIN_DIMENSIONS), False
        controls = pilot["controls_uw"]
        weights = [int(unit["adjusted_weight_uw"]) for unit in units]
        levels = {}
        for index, unit in enumerate(units):
            for dimension in MARGIN_DIMENSIONS:
                levels.setdefault(dimension, {}).setdefault(
                    str(unit.get(dimension, "")), []).append(index)
        best = None
        for order in permutations(MARGIN_DIMENSIONS):
            for round_each in (False, True):
                iterations, _, _, final = rake(weights, controls, levels, order,
                                               round_each, self.tolerance_uw,
                                               self.max_iterations)
                figures = 1 if iterations == target_iterations else 0
                for dimension in target_totals:
                    for level, expected in target_totals[dimension].items():
                        indices = levels.get(dimension, {}).get(level, [])
                        if sum(final[index] for index in indices) == expected:
                            figures += 1
                key = (figures, 0 if round_each else 1)
                if best is None or key > best[0]:
                    best = (key, list(order), round_each)
        return best[1], best[2]


# ---------------------------------------------------------------------------
# raking, nonresponse adjustment and trimming
# ---------------------------------------------------------------------------

def rake(weights, controls, levels, order, round_each_margin, tolerance, max_iterations):
    """Rake integer micro unit weights onto control totals.

    `levels` maps dimension -> level -> indices into `weights`.  Returns the
    iterations used, whether it converged, the deviation after every iteration
    and the raked weights.
    """
    count = len(weights)
    current = [Fraction(value) for value in weights]
    deviations = []
    converged = False
    iterations = 0
    for iteration in range(1, max_iterations + 1):
        for dimension in order:
            members = levels.get(dimension, {})
            totals = controls.get(dimension, {})
            for level, indices in members.items():
                control = totals.get(level)
                if control is None or not indices:
                    continue
                level_sum = Fraction(0)
                for index in indices:
                    level_sum += current[index]
                if level_sum == 0:
                    continue
                factor = Fraction(control) / level_sum
                for index in indices:
                    current[index] = current[index] * factor
                if round_each_margin:
                    for index in indices:
                        current[index] = Fraction(rhd(current[index].numerator,
                                                      current[index].denominator))
        if not round_each_margin:
            for index in range(count):
                current[index] = Fraction(rhd(current[index].numerator,
                                              current[index].denominator))
        deviation = 0
        for dimension in order:
            members = levels.get(dimension, {})
            totals = controls.get(dimension, {})
            for level, control in totals.items():
                indices = members.get(level, [])
                level_sum = 0
                for index in indices:
                    level_sum += int(current[index])
                gap = abs(level_sum - control)
                if gap > deviation:
                    deviation = gap
        deviations.append(deviation)
        iterations = iteration
        if deviation <= tolerance:
            converged = True
            break
    return iterations, converged, deviations, [int(value) for value in current]


def build_cells(round_, design_weights):
    """Form the adjustment cells of the eligible units and collapse failures."""
    members = {}
    for unit in sorted(round_.eligible):
        if design_weights.get(unit, 0) == 0:
            continue
        info = round_.units[unit]
        key = "%s|%s|%s" % (info["stratum"], info["tenure"], info["contact_band"])
        members.setdefault(key, []).append(unit)

    def stats(group):
        eligible_weight = sum(design_weights[unit] for unit in group)
        responding_weight = sum(design_weights[unit] for unit in group
                                if unit in round_.responding)
        responding_count = sum(1 for unit in group if unit in round_.responding)
        rate = 0 if eligible_weight == 0 else rhd(responding_weight * 10000, eligible_weight)
        return eligible_weight, responding_weight, responding_count, rate

    rounds = 0
    while True:
        rounds += 1
        snapshot = {key: list(group) for key, group in members.items()}
        moves = []
        for key in sorted(snapshot):
            depth = key.count("|")
            if depth == 0:
                continue
            eligible_weight, _, responding_count, rate = stats(snapshot[key])
            if (rate >= round_.min_response_rate_bp
                    and responding_count >= round_.min_cell_count):
                continue
            moves.append((key, "|".join(key.split("|")[:depth])))
        for key, parent_key in moves:
            members.setdefault(parent_key, []).extend(members.pop(key))
        if not moves or rounds >= round_.max_collapse_rounds:
            break

    assignment = {}
    for key, group in members.items():
        for unit in group:
            assignment[unit] = key
    cells = {}
    for key in sorted(members):
        eligible_weight, responding_weight, responding_count, rate = stats(members[key])
        factor = 0 if responding_weight == 0 else rhd(eligible_weight * 1000000,
                                                      responding_weight)
        cells[key] = {
            "cell_key": key,
            "depth": key.count("|"),
            "eligible_weight_uw": eligible_weight,
            "responding_weight_uw": responding_weight,
            "responding_count": responding_count,
            "response_rate_bp": rate,
            "adjustment_factor_uw": factor,
        }
    return rounds, assignment, cells


def trim(round_, raked):
    """Trim raked weights per stratum and hand the removed weight back."""
    by_stratum = {}
    for unit in sorted(raked):
        by_stratum.setdefault(round_.units[unit]["stratum"], []).append(unit)

    ceilings = {}
    applies = {}
    for stratum, group in by_stratum.items():
        weights = [raked[unit] for unit in group]
        ceilings[stratum] = rhd(median_lower(weights) * round_.trim_ratio_bp, 10000)
        total = sum(weights)
        if total == 0:
            applies[stratum] = False
        else:
            deff = rhd(10000 * len(weights) * sum(w * w for w in weights), total * total)
            applies[stratum] = deff > round_.trim_trigger_deff_bp

    final = dict(raked)
    trimmed_units = []
    for stratum in sorted(by_stratum):
        if not applies[stratum]:
            continue
        group = by_stratum[stratum]
        ceiling = ceilings[stratum]
        over = [unit for unit in group if raked[unit] > ceiling]
        if not over:
            continue
        below = [unit for unit in group if raked[unit] <= ceiling]
        removed = sum(raked[unit] - ceiling for unit in over)
        for unit in over:
            final[unit] = ceiling
            trimmed_units.append(unit)
        if not below:
            continue
        base = sum(raked[unit] for unit in below)
        if base == 0:
            for unit in below:
                final[unit] = rhd(removed, len(below))
        else:
            for unit in below:
                final[unit] = raked[unit] + rhd(removed * raked[unit], base)
        handed = sum(final[unit] for unit in below) - sum(raked[unit] for unit in below)
        difference = removed - handed
        if difference != 0:
            target = min(below, key=lambda unit: (-final[unit], unit))
            final[target] += difference
    trimmed_units.sort()
    return final, ceilings, applies, trimmed_units


def weight_pipeline(round_, design_weights):
    """Design weights -> final weights, with the artifacts of every stage."""
    collapse_rounds, assignment, cells = build_cells(round_, design_weights)
    adjusted = {}
    for unit in sorted(round_.responding):
        if design_weights.get(unit, 0) == 0:
            continue
        factor = cells[assignment[unit]]["adjustment_factor_uw"]
        adjusted[unit] = rhd(design_weights[unit] * factor, 1000000)

    active = sorted(adjusted)
    levels = {}
    for index, unit in enumerate(active):
        for dimension in MARGIN_DIMENSIONS:
            level = round_.margin_level(unit, dimension)
            if level:
                levels.setdefault(dimension, {}).setdefault(level, []).append(index)
    iterations, converged, deviations, raked_list = rake(
        [adjusted[unit] for unit in active], round_.control_totals, levels,
        round_.margin_order, round_.round_each_margin, round_.tolerance_uw,
        round_.max_iterations)
    raked = {unit: raked_list[index] for index, unit in enumerate(active)}
    final, ceilings, applies, trimmed_units = trim(round_, raked)
    return {
        "collapse_rounds": collapse_rounds,
        "assignment": assignment,
        "cells": cells,
        "adjusted": adjusted,
        "iterations": iterations,
        "converged": converged,
        "deviations": deviations,
        "raked": raked,
        "final": final,
        "ceilings": ceilings,
        "trim_applies": applies,
        "trimmed_units": trimmed_units,
        "active": active,
    }


# ---------------------------------------------------------------------------
# reports
# ---------------------------------------------------------------------------

def compute(round_):
    """Run the whole derivation and return everything the reports need."""
    units = round_.units
    results = {}

    design_weights = {unit: info["design_weight"] for unit, info in units.items()}
    full = weight_pipeline(round_, design_weights)
    results["full"] = full
    responding = sorted(round_.responding)
    results["responding"] = responding

    psus = {}
    for unit in sorted(units):
        psus.setdefault(units[unit]["stratum"], set()).add(units[unit]["psu"])

    def group_target(stratum, seen=None):
        if len(psus.get(stratum, ())) >= 2 or stratum not in round_.strata:
            return stratum
        seen = set() if seen is None else seen
        if stratum in seen:
            return stratum
        seen.add(stratum)
        return group_target(round_.strata[stratum]["collapse_partner"], seen)

    groups = {}
    for stratum in sorted(psus):
        code = group_target(stratum)
        entry = groups.setdefault(code, {"strata": set(), "psus": set()})
        entry["strata"].add(stratum)
        entry["psus"] |= psus[stratum]
    results["groups"] = groups

    final_weights = full["final"]
    ordered = sorted(responding, key=lambda unit: (final_weights[unit], unit))
    quintile = {}
    for index, unit in enumerate(ordered):
        quintile[unit] = "Q%d" % (1 + (5 * index) // len(ordered))
    results["quintile"] = quintile

    def placement_of(unit):
        info = units[unit]
        placed = {}
        if info["activity_ref"]:
            placed["activity_by_region"] = "%s|%s" % (info["activity_ref"], info["region"])
        placed["tenure_by_wquintile"] = "%s|%s" % (info["tenure"], quintile[unit])
        if info["sector_ref"]:
            placed["hours_by_sector"] = "%s|%s" % (info["sector_ref"], info["band_ref"])
        if info["band_wave1"]:
            placed["band_transition"] = "%s|%s" % (info["band_wave1"], info["band_ref"])
        return placed

    placement = {unit: placement_of(unit) for unit in responding}
    results["placement"] = placement

    keys = {}
    for table in round_.tables:
        keys[table] = ["%s|%s" % (row_level["level"], column_level["level"])
                       for row_level in round_.tables[table]["row"]
                       for column_level in round_.tables[table]["column"]]
    results["keys"] = keys

    def cell_totals(weights, active):
        totals = {table: {key: 0 for key in keys[table]} for table in round_.tables}
        counts = {table: {key: 0 for key in keys[table]} for table in round_.tables}
        greatest = {table: {key: 0 for key in keys[table]} for table in round_.tables}
        for unit in active:
            weight = weights[unit]
            for table, key in placement[unit].items():
                if key not in totals[table]:
                    continue
                totals[table][key] += weight
                counts[table][key] += 1
                if weight > greatest[table][key]:
                    greatest[table][key] = weight
        return totals, counts, greatest

    full_totals, full_counts, full_greatest = cell_totals(final_weights, responding)
    results["full_totals"] = full_totals
    results["full_counts"] = full_counts
    results["full_greatest"] = full_greatest

    replicate_rows = []
    variance = {table: {key: 0 for key in keys[table]} for table in round_.tables}
    variance_by_group = {table: {code: 0 for code in groups} for table in round_.tables}
    for code in sorted(groups):
        entry = groups[code]
        size = len(entry["psus"])
        for psu in sorted(entry["psus"]):
            rep_weights = {}
            for unit, weight in design_weights.items():
                stratum = units[unit]["stratum"]
                if stratum in entry["strata"]:
                    if units[unit]["psu"] == psu:
                        continue
                    rep_weights[unit] = rhd(weight * size, size - 1)
                else:
                    rep_weights[unit] = weight
            result = weight_pipeline(round_, rep_weights)
            replicate_rows.append((
                "%s::%s" % (code, psu), code, psu, size, result["iterations"],
                yn(result["converged"]), len(result["trimmed_units"]),
                sum(result["final"].values())))
            totals, _, _ = cell_totals(result["final"], result["active"])
            for table in round_.tables:
                for key in keys[table]:
                    diff = totals[table][key] - full_totals[table][key]
                    term = (size - 1) * diff * diff
                    variance[table][key] += term // size
                    variance_by_group[table][code] += term // size
    replicate_rows.sort(key=lambda row: row[0])
    results["replicate_rows"] = replicate_rows
    results["variance"] = variance
    results["variance_by_group"] = variance_by_group

    estimates = {}
    for table in round_.tables:
        table_estimates = {}
        for key in keys[table]:
            row_level, column_level = key.split("|", 1)
            total = full_totals[table][key]
            count = full_counts[table][key]
            error = sqrt_nearest(variance[table][key])
            if total == 0:
                cv = 0
                dominance = 0
            else:
                cv = rhd(10000 * error, total)
                dominance = rhd(10000 * full_greatest[table][key], total)
            table_estimates[key] = {
                "row_level": row_level,
                "column_level": column_level,
                "point_estimate_uw": total,
                "unweighted_count": count,
                "standard_error_uw": error,
                "cv_bp": cv,
                "dominance_bp": dominance,
            }
        estimates[table] = table_estimates
    results["estimates"] = estimates
    return results


def disclosure(round_, results, min_publish_count=None, max_publish_cv_bp=None,
               dominance_bp=None, max_cascade_rounds=None):
    """Screening rank, primary and secondary suppression."""
    min_publish_count = round_.min_publish_count if min_publish_count is None else min_publish_count
    max_publish_cv_bp = round_.max_publish_cv_bp if max_publish_cv_bp is None else max_publish_cv_bp
    dominance_bp = round_.dominance_bp if dominance_bp is None else dominance_bp
    max_cascade_rounds = round_.max_cascade_rounds if max_cascade_rounds is None else max_cascade_rounds

    estimates = results["estimates"]
    screening = []
    for table in sorted(round_.tables):
        for key in estimates[table]:
            screening.append((table, key, estimates[table][key]["cv_bp"]))
    screening.sort(key=lambda item: (-item[2], item[0], item[1]))
    ranks = {(table, key): rank for rank, (table, key, _) in enumerate(screening, start=1)}

    primary = {}
    primary_counts = {}
    cv_tables = {table: [] for table in round_.tables}
    for table, key, _ in screening:
        entry = estimates[table][key]
        reasons = []
        if entry["unweighted_count"] < min_publish_count:
            reasons.append("count")
        if entry["cv_bp"] > max_publish_cv_bp:
            reasons.append("cv")
        if entry["dominance_bp"] > dominance_bp:
            reasons.append("dominance")
        cv_tables.setdefault(table, []).append({
            "cell_key": key,
            "screening_rank": ranks[(table, key)],
            "cv_bp": entry["cv_bp"],
            "dominance_bp": entry["dominance_bp"],
            "unweighted_count": entry["unweighted_count"],
            "reasons": reasons,
        })
        if reasons:
            primary.setdefault(table, []).append({"cell_key": key, "reasons": reasons})
            primary_counts[table] = primary_counts.get(table, 0) + 1
    for table in primary:
        primary[table].sort(key=lambda entry: entry["cell_key"])

    secondary = {}
    cascade_rounds = {}
    secondary_counts = {}
    for table in sorted(round_.tables):
        suppressed = set(entry["cell_key"] for entry in primary.get(table, []))
        entries = []
        rounds = 0
        while rounds < max_cascade_rounds:
            rounds += 1
            changed = False
            for axis in ("row", "column"):
                for axis_level in round_.tables[table][axis]:
                    level = axis_level["level"]
                    cells = [key for key in results["keys"][table]
                             if (axis == "row" and key.split("|", 1)[0] == level)
                             or (axis == "column" and key.split("|", 1)[1] == level)]
                    held = [key for key in cells if key in suppressed]
                    if len(held) != 1:
                        continue
                    candidates = [key for key in cells if key not in suppressed]
                    if not candidates:
                        continue
                    chosen = min(candidates, key=lambda key: (
                        estimates[table][key]["unweighted_count"], key))
                    suppressed.add(chosen)
                    entries.append({
                        "cell_key": chosen,
                        "axis": axis,
                        "axis_level": level,
                        "round": rounds,
                    })
                    changed = True
            if not changed:
                break
        entries.sort(key=lambda entry: entry["cell_key"])
        secondary[table] = entries
        cascade_rounds[table] = rounds
        secondary_counts[table] = len(entries)

    return {
        "ranks": ranks,
        "screening": screening,
        "cv_tables": cv_tables,
        "primary": primary,
        "primary_counts": primary_counts,
        "secondary": secondary,
        "secondary_counts": secondary_counts,
        "cascade_rounds": cascade_rounds,
    }


def suppressed_sets(round_, screen):
    return {table: set(entry["cell_key"] for entry in screen["primary"].get(table, []))
            | set(entry["cell_key"] for entry in screen["secondary"][table])
            for table in round_.tables}


def write_reports(round_, results, screen, out_dir):
    units = round_.units
    full = results["full"]
    responding = results["responding"]
    final_weights = full["final"]

    write_json(os.path.join(out_dir, "frame_audit.json"), {
        "repair_counts": round_.repair_counts,
        "self_referencing_units": round_.self_referencing_units,
        "dangling_parent_units": round_.dangling_parent_units,
        "discarded_record_ids": round_.discarded_record_ids,
        "resolved_unit_count": round_.resolved_unit_count,
        "subsample_factor_bp": round_.subsample_factor_bp,
    })

    dimensions = {}
    level_counts = {}
    for dimension in sorted(round_.control_totals):
        dimensions[dimension] = dict(sorted(round_.control_totals[dimension].items()))
        level_counts[dimension] = len(round_.control_totals[dimension])
    write_json(os.path.join(out_dir, "control_totals.json"), {
        "reference_period": REFERENCE_PERIOD,
        "grand_total_uw": sum(round_.control_totals["region_tenure"].values()),
        "dimensions": dimensions,
        "level_counts": level_counts,
    })
    margin_rows = []
    for dimension in sorted(round_.control_totals):
        for level in sorted(round_.control_totals[dimension]):
            rank, source = round_.control_source[(dimension, level)]
            margin_rows.append((dimension, level, round_.control_totals[dimension][level],
                                rank, source))
    write_delimited(os.path.join(out_dir, "control_margins.tsv"),
                    ["dimension", "level_key", "control_total_uw", "chosen_rank",
                     "chosen_source"], margin_rows, "\t")

    disposition_counts = {}
    status_units = {}
    for (unit, wave), resolved in round_.disposition.items():
        if wave != REFERENCE_WAVE or unit not in units:
            continue
        code = resolved["disposition"]
        disposition_counts[code] = disposition_counts.get(code, 0) + 1
        status_units[unit] = {
            "disposition": code,
            "attempt_no": resolved["attempt_no"],
            "resolved_utc": resolved["resolved_utc"],
            "attempts": round_.attempt_counts.get((unit, wave), 0),
        }
    write_json(os.path.join(out_dir, "response_status.json"), {
        "reference_wave": REFERENCE_WAVE,
        "disposition_counts": dict(sorted(disposition_counts.items())),
        "eligible_count": len(round_.eligible),
        "responding_count": len(responding),
        "superseded_units": sorted(round_.superseded_units),
        "units": status_units,
    })

    write_delimited(os.path.join(out_dir, "design_weights.csv"),
                    ["unit_id", "stratum", "psu_code", "subsampled", "design_weight_uw"],
                    [(unit, units[unit]["stratum"], units[unit]["psu"],
                      yn(units[unit]["subsampled"]), units[unit]["design_weight"])
                     for unit in sorted(units)], ",")

    cells_payload = [full["cells"][key] for key in sorted(full["cells"])]
    depth_counts = {"0": 0, "1": 0, "2": 0}
    for cell in cells_payload:
        depth_counts[str(cell["depth"])] = depth_counts.get(str(cell["depth"]), 0) + 1
    write_json(os.path.join(out_dir, "adjustment_cells.json"), {
        "collapse_rounds": full["collapse_rounds"],
        "cell_count": len(cells_payload),
        "cells": cells_payload,
        "depth_counts": depth_counts,
    })

    write_delimited(os.path.join(out_dir, "adjusted_weights.csv"),
                    ["unit_id", "cell_key", "adjustment_factor_uw", "adjusted_weight_uw"],
                    [(unit, full["assignment"][unit],
                      full["cells"][full["assignment"][unit]]["adjustment_factor_uw"],
                      full["adjusted"][unit]) for unit in responding], ",")

    write_json(os.path.join(out_dir, "raking_trace.json"), {
        "margin_order": list(round_.margin_order),
        "tolerance_uw": round_.tolerance_uw,
        "max_iterations": round_.max_iterations,
        "iterations_used": full["iterations"],
        "converged": full["converged"],
        "final_max_deviation_uw": full["deviations"][-1] if full["deviations"] else 0,
        "per_iteration": [{"iteration": index + 1, "max_deviation_uw": deviation}
                          for index, deviation in enumerate(full["deviations"])],
    })

    write_delimited(os.path.join(out_dir, "final_weights.csv"),
                    ["unit_id", "stratum", "raked_weight_uw", "trimmed", "final_weight_uw"],
                    [(unit, units[unit]["stratum"], full["raked"][unit],
                      yn(unit in full["trimmed_units"]), final_weights[unit])
                     for unit in responding], ",")

    total = sum(final_weights.values())
    if total == 0:
        deff = 0
    else:
        deff = rhd(10000 * len(responding) * sum(w * w for w in final_weights.values()),
                   total * total)
    stratum_totals = {}
    for unit in responding:
        stratum = units[unit]["stratum"]
        stratum_totals[stratum] = stratum_totals.get(stratum, 0) + final_weights[unit]
    write_json(os.path.join(out_dir, "weight_diagnostics.json"), {
        "responding_count": len(responding),
        "final_weight_total_uw": total,
        "design_effect_bp": deff,
        "median_weight_uw": median_lower([final_weights[unit] for unit in responding]),
        "maximum_weight_uw": max(final_weights.values()) if final_weights else 0,
        "minimum_weight_uw": min(final_weights.values()) if final_weights else 0,
        "trimmed_count": len(full["trimmed_units"]),
        "trimmed_units": full["trimmed_units"],
        "stratum_totals_uw": dict(sorted(stratum_totals.items())),
        "stratum_ceilings_uw": dict(sorted(full["ceilings"].items())),
    })

    groups_payload = {}
    merged_groups = {}
    for code in sorted(results["groups"]):
        entry = results["groups"][code]
        groups_payload[code] = {
            "psus": sorted(entry["psus"]),
            "size": len(entry["psus"]),
            "strata": sorted(entry["strata"]),
        }
        if len(entry["strata"]) > 1:
            merged_groups[code] = sorted(entry["strata"])
    replicate_count = sum(entry["size"] for entry in groups_payload.values())
    write_json(os.path.join(out_dir, "replicate_design.json"), {
        "replicate_count": replicate_count,
        "group_count": len(groups_payload),
        "groups": groups_payload,
        "merged_groups": merged_groups,
    })
    write_delimited(os.path.join(out_dir, "replicate_summary.csv"),
                    ["replicate_id", "group", "dropped_psu", "group_size",
                     "iterations_used", "converged", "trimmed_count", "final_total_uw"],
                    results["replicate_rows"], ",")

    for table in sorted(round_.tables):
        rows = []
        for key in results["keys"][table]:
            entry = results["estimates"][table][key]
            rows.append((key, entry["row_level"], entry["column_level"],
                         entry["point_estimate_uw"], entry["unweighted_count"],
                         entry["standard_error_uw"], entry["cv_bp"], entry["dominance_bp"]))
        write_delimited(os.path.join(out_dir, "estimates_%s.csv" % table),
                        ["cell_key", "row_level", "column_level", "point_estimate_uw",
                         "unweighted_count", "standard_error_uw", "cv_bp", "dominance_bp"],
                        rows, ",")
    write_json(os.path.join(out_dir, "variance_components.json"), {
        "replicate_count": replicate_count,
        "tables": {table: {
            "summed_cell_variance_uw2": sum(results["variance"][table].values()),
            "by_group": dict(sorted(results["variance_by_group"][table].items())),
        } for table in sorted(round_.tables)},
    })

    write_json(os.path.join(out_dir, "cv_screening.json"), {
        "min_publish_count": round_.min_publish_count,
        "max_publish_cv_bp": round_.max_publish_cv_bp,
        "dominance_bp": round_.dominance_bp,
        "tables": screen["cv_tables"],
    })
    primary_payload = {
        "tables": {table: screen["primary"].get(table, [])
                   for table in sorted(round_.tables)},
        "counts": {table: screen["primary_counts"].get(table, 0)
                   for table in sorted(round_.tables)},
        "total": sum(screen["primary_counts"].values()),
    }
    write_json(os.path.join(out_dir, "primary_suppression.json"), primary_payload)

    write_json(os.path.join(out_dir, "secondary_suppression.json"), {
        "tables": {table: screen["secondary"][table] for table in sorted(round_.tables)},
        "cascade_rounds": {table: screen["cascade_rounds"][table]
                           for table in sorted(round_.tables)},
        "counts": {table: screen["secondary_counts"][table]
                   for table in sorted(round_.tables)},
        "total": sum(screen["secondary_counts"].values()),
    })

    suppressed = suppressed_sets(round_, screen)
    audit_rows = []
    for table, key, _ in screen["screening"]:
        entry = results["estimates"][table][key]
        if key in suppressed[table]:
            status = "suppressed"
            reason = ("primary" if key in set(entry["cell_key"] for entry in
                                             screen["primary"].get(table, [])) else "secondary")
        else:
            status = "published"
            reason = "none"
        audit_rows.append((screen["ranks"][(table, key)], table, key, status, reason,
                           entry["point_estimate_uw"], entry["unweighted_count"],
                           entry["cv_bp"]))
    write_delimited(os.path.join(out_dir, "disclosure_audit.tsv"),
                    ["screening_rank", "table_name", "cell_key", "status", "reason",
                     "point_estimate_uw", "unweighted_count", "cv_bp"],
                    audit_rows, "\t")

    table_payload = {}
    conservation = 0
    for table in sorted(round_.tables):
        entries = results["estimates"][table]
        total_uw = sum(entry["point_estimate_uw"] for entry in entries.values())
        published_uw = sum(entries[key]["point_estimate_uw"] for key in entries
                           if key not in suppressed[table])
        suppressed_uw = sum(entries[key]["point_estimate_uw"] for key in entries
                            if key in suppressed[table])
        residual = published_uw + suppressed_uw - total_uw
        conservation += residual
        table_payload[table] = {
            "total_uw": total_uw,
            "published_uw": published_uw,
            "suppressed_uw": suppressed_uw,
            "residual_uw": residual,
            "coverage_gap_uw": total - total_uw,
        }

    level_sums = {}
    for unit in responding:
        for dimension in MARGIN_DIMENSIONS:
            level = round_.margin_level(unit, dimension)
            level_sums[(dimension, level)] = (level_sums.get((dimension, level), 0)
                                             + final_weights[unit])
    deviation = 0
    for dimension in MARGIN_DIMENSIONS:
        for level, control in round_.control_totals[dimension].items():
            gap = abs(level_sums.get((dimension, level), 0) - control)
            if gap > deviation:
                deviation = gap

    grand_total = sum(round_.control_totals["region_tenure"].values())
    checks = [
        ("raking_converged", 1 if full["converged"] else 0),
        ("final_total_within_tolerance",
         1 if abs(total - grand_total) <= round_.tolerance_uw else 0),
        ("trimming_preserves_total",
         1 if sum(final_weights.values()) == sum(full["raked"].values()) else 0),
        ("suppression_conservation",
         1 if all(payload["residual_uw"] == 0 for payload in table_payload.values()) else 0),
    ]
    write_json(os.path.join(out_dir, "closure_report.json"), {
        "post_trim_margin_deviation_uw": deviation,
        "final_weight_total_uw": total,
        "control_grand_total_uw": grand_total,
        "conservation_residual_uw": conservation,
        "final_total_gap_uw": total - grand_total,
        "responding_count": len(responding),
        "replicate_count": replicate_count,
        "primary_suppression_total": primary_payload["total"],
        "secondary_suppression_total": sum(screen["secondary_counts"].values()),
        "tables": table_payload,
        "checks": [{"name": name, "expected": 1, "observed": observed,
                    "verdict": "pass" if observed == 1 else "fail"}
                   for name, observed in checks],
        "all_checks_pass": all(observed == 1 for _, observed in checks),
    })


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_survey.py DATA_DIR OUT_DIR\n")
        return 2
    data_dir, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)
    round_ = Round(data_dir)
    results = compute(round_)
    screen = disclosure(round_, results)
    write_reports(round_, results, screen, out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
