#!/usr/bin/env python3
"""HAS-7 round derivation: python3 derive_survey.py DATA_DIR OUT_DIR.

Reads one Regional Household Activity Survey extract and writes the twenty two
reports the HAS-7 standard defines. Standard library only; every graded figure
is an integer, so no value passes through binary floating point.
"""
from __future__ import annotations

import configparser
import csv
import io
import itertools
import json
import math
import re
import sys
import tomllib
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

MICRO = 1_000_000
BASIS = 10_000
REFERENCE_PERIOD = "2026-H1"
REFERENCE_WAVE = 3
TABLE_NAMES = ["activity_by_region", "band_transition", "hours_by_sector",
               "tenure_by_wquintile"]
IN_SCOPE_MARKERS = {"Y", "yes", "true"}
UNIT_PATTERN = re.compile(r"RH-([A-Z]{2})-([0-9]+)")
STAMP_PATTERN = re.compile(
    r"(\d{4})-(\d\d)-(\d\d)T(\d\d):(\d\d):(\d\d)(\.\d+)?(Z|([+-])(\d\d):(\d\d))")


# --------------------------------------------------------------- arithmetic
def divide(numerator: int, denominator: int) -> int:
    """Integer division rounded to nearest, halves away from zero."""
    if denominator == 0:
        return 0
    if denominator < 0:
        numerator, denominator = -numerator, -denominator
    magnitude = (2 * abs(numerator) + denominator) // (2 * denominator)
    return magnitude if numerator >= 0 else -magnitude


def rounded_root(value: int) -> int:
    if value <= 0:
        return 0
    base = math.isqrt(value)
    # (base + 1/2)^2 = base^2 + base + 1/4, so round up past base^2 + base
    return base + 1 if value > base * base + base else base


def in_scope(marker) -> bool:
    if isinstance(marker, bool):
        return marker
    return str(marker).strip() in IN_SCOPE_MARKERS


def nfc(text) -> str:
    return unicodedata.normalize("NFC", str(text))


def canonical_unit(raw) -> str | None:
    text = nfc(raw).strip().upper().replace("_", "-").replace(".", "-")
    match = UNIT_PATTERN.fullmatch(text)
    if not match:
        return None
    return "RH-%s-%06d" % (match.group(1), int(match.group(2)))


def utc_instant(raw: str) -> tuple[int, str]:
    """Seconds since the epoch (fraction truncated) and the canonical text."""
    match = STAMP_PATTERN.fullmatch(raw.strip())
    if not match:
        raise ValueError("unreadable timestamp %r" % raw)
    year, month, day, hour, minute, second = (int(match.group(i)) for i in range(1, 7))
    local = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    seconds = int(local.timestamp())
    if match.group(8) != "Z":
        shift = int(match.group(10)) * 3600 + int(match.group(11)) * 60
        seconds -= shift if match.group(9) == "+" else -shift
    text = datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return seconds, text


# --------------------------------------------------------------- readers
class Extract:
    """Typed access to the files of one extract directory."""

    def __init__(self, folder: Path):
        self.folder = folder

    def text(self, name: str) -> str:
        return (self.folder / name).read_text(encoding="utf-8")

    def table(self, name: str) -> list[dict]:
        delimiter = {".csv": ",", ".tsv": "\t", ".psv": "|"}[Path(name).suffix]
        reader = csv.DictReader(io.StringIO(self.text(name)), delimiter=delimiter)
        return [dict(row) for row in reader]

    def json_lines(self, name: str) -> list[dict]:
        return [json.loads(line) for line in self.text(name).splitlines() if line.strip()]

    def document(self, name: str):
        return json.loads(self.text(name))

    def toml(self, name: str) -> dict:
        return tomllib.loads(self.text(name))

    def ini(self, name: str) -> configparser.ConfigParser:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(self.text(name))
        return parser

    def pairs(self, name: str) -> dict:
        found = {}
        for line in self.text(name).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            found[key.strip()] = value.strip()
        return found

    def fixed_width(self, name: str) -> list[dict]:
        lines = [line for line in self.text(name).splitlines() if line.strip()]
        header = lines[0]
        starts = [m.start() for m in re.finditer(r"\S+", header)]
        names = header.split()
        bounds = list(zip(starts, starts[1:] + [None]))
        rows = []
        for line in lines[1:]:
            rows.append({key: line[a:b].strip() if b else line[a:].strip()
                         for key, (a, b) in zip(names, bounds)})
        return rows

    def records(self, name: str) -> list[dict]:
        suffix = Path(name).suffix
        if suffix in (".csv", ".tsv", ".psv"):
            return self.table(name)
        if suffix == ".jsonl":
            return self.json_lines(name)
        if suffix == ".fwf":
            return self.fixed_width(name)
        raise ValueError("no reader for %s" % name)

    def names(self, prefix: str) -> list[str]:
        return sorted(p.name for p in self.folder.iterdir() if p.name.startswith(prefix))


# --------------------------------------------------------------- reference data
def load_registers(ex: Extract) -> dict:
    strata = {nfc(r["stratum_code"]): r for r in ex.table("ref__stratum-params.tsv")
              if in_scope(r["active"])}
    regions = {nfc(r["region_code"]): nfc(r["region_name"])
               for r in ex.table("ref__region-codes.csv") if in_scope(r["active"])}
    stratum_by_name = {}
    for code, row in strata.items():
        if nfc(row["region_code"]) in regions:
            stratum_by_name[nfc("%s %s" % (regions[nfc(row["region_code"])],
                                           row["stratum_group"]))] = code
    tenure_doc = ex.document("ref__tenure-classes.json")
    tenure_class = {nfc(k): nfc(v["tenure_class"]) for k, v in tenure_doc["classes"].items()
                    if in_scope(v.get("active", True))}
    band_fields = {}
    for key, value in ex.pairs("ref__band-definitions.properties").items():
        parts = key.split(".")
        if len(parts) == 3 and parts[0] == "band":
            band_fields.setdefault(nfc(parts[1]), {})[parts[2]] = value
    bands = sorted(((int(f["sort_rank"]), code, int(f["lower_hours_inclusive"]),
                     int(f["upper_hours_inclusive"])) for code, f in band_fields.items()))
    precedence = {nfc(r["disposition_code"]): r
                  for r in ex.table("rules__disposition-precedence.csv") if in_scope(r["active"])}
    registry = {}
    for row in ex.table("disclosure__cell-registry.csv"):
        if in_scope(row["active"]):
            registry.setdefault((nfc(row["table_name"]), nfc(row["axis"])), []).append(
                (int(row["sort_rank"]), nfc(row["level_key"])))
    levels = {k: [lv for _, lv in sorted(v)] for k, v in registry.items()}
    contact_bands = []
    for line in ex.text("ref__contact-bands.sexp").splitlines():
        if not line.startswith("(contact-band"):
            continue
        fields = dict(re.findall(r"\(([\w-]+) ([^()\s]+)\)", line))
        if in_scope(fields.get("active", "")):
            contact_bands.append((int(fields["min-attempts"]), int(fields["max-attempts"]),
                                  nfc(fields["code"])))
    return {"strata": strata, "stratum_by_name": stratum_by_name,
            "tenure_class": tenure_class, "bands": bands, "precedence": precedence,
            "levels": levels, "contact_bands": sorted(contact_bands)}


def band_for_hours(bands, hours: int) -> str:
    for _, code, low, high in bands:
        if low <= hours <= high:
            return code
    return bands[-1][1]


def load_settings(ex: Extract) -> dict:
    cells = ex.toml("rules__adjustment-cells.toml")
    raking = ex.ini("rules__margin-order.ini")
    margins = sorted(section.split(".", 1)[1] for section in raking.sections()
                     if section.startswith("margin.") and in_scope(raking[section]["active"]))
    trim = ex.pairs("rules__trimming.conf")
    disclosure = ex.toml("disclosure__parameters.toml")
    return {
        "min_rate": int(cells["min_response_rate_bp"]),
        "min_count": int(cells["min_cell_count"]),
        "collapse_limit": int(cells["max_collapse_rounds"]),
        "margins": margins,
        "tolerance": int(raking["raking"]["tolerance_uw"]),
        "iteration_limit": int(raking["raking"]["max_iterations"]),
        "trim_ratio": int(trim["trim_ratio_bp"]),
        "trim_trigger": int(trim["trim_trigger_deff_bp"]),
        "min_publish": int(disclosure["min_publish_count"]),
        "max_cv": int(disclosure["max_publish_cv_bp"]),
        "max_dominance": int(disclosure["dominance_bp"]),
        "cascade_limit": int(disclosure["max_cascade_rounds"]),
    }


# --------------------------------------------------------------- benchmarks
def benchmark_offers(ex: Extract):
    """Yield (dimension, level, rank, published, source, value text, unit, period)."""
    for name in ex.names("bench__"):
        if name == "bench__unit-conversions.csv":
            continue
        suffix = Path(name).suffix
        if suffix == ".csv":
            for row in ex.table(name):
                yield (row["dimension"], row["level_key"], row["rank"], row["published_date"],
                       row["source_id"], row["value"], row["unit"], row["reference_period"])
            continue
        if suffix == ".json":
            head = ex.document(name)
            series = head["series"]
        elif suffix == ".toml":
            head = ex.toml(name)
            series = head["series"]
        elif suffix == ".ini":
            parser = ex.ini(name)
            head = dict(parser["meta"])
            series = [dict(parser[s]) for s in parser.sections() if s.startswith("series.")]
        elif suffix == ".properties":
            flat = ex.pairs(name)
            head = flat
            grouped = {}
            for key, value in flat.items():
                if key.startswith("series."):
                    _, index, field = key.split(".", 2)
                    grouped.setdefault(index, {})[field] = value
            series = list(grouped.values())
        else:
            continue
        for entry in series:
            yield (head["dimension"], entry["key"], entry["rank"], head["published_date"],
                   head["source_id"], entry["value"], head["unit"], entry["reference_period"])


def resolve_controls(ex: Extract) -> tuple[dict, dict]:
    scale = {nfc(r["unit_name"]): Decimal(r["persons_per_unit"])
             for r in ex.table("bench__unit-conversions.csv") if in_scope(r["active"])}
    best = {}
    for dimension, level, rank, published, source, value, unit, period in benchmark_offers(ex):
        if str(period) != REFERENCE_PERIOD:
            continue
        micro = Decimal(str(value)) * scale[nfc(unit)] * MICRO
        candidate = ((int(rank), str(published), str(source)), int(micro), int(rank), source)
        key = (nfc(dimension), nfc(level))
        if key not in best or candidate[0] > best[key][0]:
            best[key] = candidate
    controls, provenance = {}, {}
    for (dimension, level), (_, micro, rank, source) in best.items():
        controls.setdefault(dimension, {})[level] = micro
        provenance[(dimension, level)] = (rank, source)
    return controls, provenance


# --------------------------------------------------------------- frame
REPAIRS = ["M%d" % i for i in range(1, 9)]


def resolve_frame(ex: Extract, reg: dict) -> dict:
    repairs = dict.fromkeys(REPAIRS, 0)
    raw_rows = []
    for row in ex.table("frame__register-a.csv") + ex.table("frame__register-b.tsv"):
        raw_rows.append((row["record_id"], row["region_code"], row["serial"], row["stratum"],
                         row["psu_code"], row["vintage_rank"], row["edit_timestamp"],
                         row["tenure"]))
    for row in ex.fixed_width("frame__register-c.fwf"):
        raw_rows.append((row["record_id"], row["reg"], row["serial"], row["strat"],
                         row["psu"], row["vr"], row["edit_timestamp"], row["tenure"]))

    candidates = {}
    for record_id, region, serial, stratum, psu, vintage, stamp, tenure in raw_rows:
        stratum_text = nfc(stratum)
        if stratum_text in reg["strata"]:
            code = stratum_text
        elif stratum_text in reg["stratum_by_name"]:
            code = reg["stratum_by_name"][stratum_text]
        else:
            continue  # outside the frame, no repair counted
        if code != stratum_text:
            repairs["M7"] += 1
        trimmed = serial.strip()
        if trimmed != serial:
            repairs["M1"] += 1
        if len(trimmed) < 6:
            repairs["M2"] += 1
        if region != region.upper():
            repairs["M3"] += 1
        identity = "RH-%s-%s" % (nfc(region).upper(), trimmed.zfill(6))
        candidates.setdefault(identity, []).append(
            {"rank": int(vintage), "stamp": stamp, "record_id": record_id,
             "stratum": code, "psu": nfc(psu).strip(), "tenure": nfc(tenure)})
    reissued_psu = {}
    for row in ex.json_lines("frame__register-d.jsonl"):
        unit = canonical_unit(row.get("unit_id", ""))
        if unit is not None:
            reissued_psu[unit] = nfc(row.get("psu_code", "")).strip()

    units, discarded = {}, []
    for identity, rows in candidates.items():
        ordered = sorted(rows, key=lambda r: (r["rank"], r["stamp"], r["record_id"]),
                         reverse=True)
        winner = ordered[0]
        for loser in ordered[1:]:
            repairs["M8"] += 1
            discarded.append(loser["record_id"])
        units[identity] = {"stratum": winner["stratum"],
                           "psu": winner["psu"] or reissued_psu.get(identity, ""),
                           "tenure": winner["tenure"], "region": identity[3:5],
                           "dwellings": 1, "band": None}

    self_links, dangling = [], []
    blocks = ex.text("frame__addresses.rfc822").split("\n\n")
    for block in blocks:
        fields = {}
        for line in block.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key.strip()] = value.strip()
        if not in_scope(fields.get("Active", "Y")):
            continue
        unit = canonical_unit(fields.get("Unit-Id", ""))
        if unit not in units:
            continue
        record = units[unit]
        dwellings = fields.get("Dwelling-Units", "")
        if dwellings == "":
            repairs["M4"] += 1
            record["dwellings"] = 1
        else:
            record["dwellings"] = int(dwellings)
        parent = fields.get("Parent-Unit", "")
        if parent:
            target = canonical_unit(parent)
            if target == unit:
                repairs["M5"] += 1
                self_links.append(unit)
            elif target not in units:
                repairs["M6"] += 1
                dangling.append(unit)

    subsample = ex.pairs("frame__subsample.conf")
    for unit, record in units.items():
        record["subsampled"] = in_scope(subsample.get("unit.%s.subsampled" % unit, "no"))
    return {"units": units, "repairs": repairs, "self_links": sorted(self_links),
            "dangling": sorted(dangling), "discarded": sorted(discarded),
            "subsample_bp": int(subsample["subsample_factor_bp"])}


# --------------------------------------------------------------- contacts
def contact_history(ex: Extract, units: dict, precedence: dict) -> dict:
    attempts, corrections = {}, {}

    def attempt(raw_unit, wave, number, stamp, code):
        unit, code = canonical_unit(raw_unit), nfc(code)
        if unit not in units or code not in precedence:
            return
        seconds, text = utc_instant(stamp)
        attempts.setdefault((unit, int(wave)), []).append(
            {"severity": int(precedence[code]["severity_rank"]), "seconds": seconds,
             "number": int(number), "code": code, "utc": text})

    structured = re.compile(r'(\w+)="([^"]*)"')
    for line in ex.text("contact__log-w1.rfc5424").splitlines():
        if not line.strip():
            continue
        stamp = line.split(" ")[1]
        fields = dict(structured.findall(line))
        attempt(fields["unit"], fields["wave"], fields["attempt"], stamp, fields["outcome"])
    for name in ex.names("contact__log-w"):
        if not name.endswith(".logfmt"):
            continue
        for line in ex.text(name).splitlines():
            fields = dict(token.split("=", 1) for token in line.split() if "=" in token)
            if not fields or not in_scope(fields.get("active", "")):
                continue
            if "correction" in fields:
                unit = canonical_unit(fields["unit"])
                key = (unit, int(fields["wave"]), int(fields["attempt"]))
                corrections.setdefault(key, []).append(
                    (utc_instant(fields["ts"])[0], nfc(fields["correction"]) == "reinstate"))
                continue
            attempt(fields["unit"], fields["wave"], fields["attempt"], fields["ts"],
                    fields["outcome"])
    for row in ex.table("contact__outcomes.csv"):
        if in_scope(row["active"]):
            attempt(row["unit_id"], row["wave"], row["attempt_no"], row["contact_datetime"],
                    row["outcome_code"])
    for row in ex.json_lines("contact__reissues.jsonl"):
        if in_scope(row["active"]):
            attempt(row["unit_id"], row["wave"], row["attempt_no"], row["contact_datetime"],
                    row["outcome_code"])

    void = {key for key, marks in corrections.items() if not max(marks)[1]}
    settled = {}
    for (unit, wave), tries in attempts.items():
        standing = [t for t in tries if (unit, wave, t["number"]) not in void]
        if not standing:
            continue
        top = max(standing, key=lambda t: (t["severity"], t["seconds"], t["number"]))
        flags = precedence[top["code"]]
        settled[(unit, wave)] = {"disposition": top["code"], "attempt_no": top["number"],
                                 "resolved_utc": top["utc"], "attempts": len(tries),
                                 "eligible": in_scope(flags["eligible"]),
                                 "responding": in_scope(flags["responding"]),
                                 "superseded": in_scope(flags["superseded"])}
    counts = {key: len(tries) for key, tries in attempts.items()}
    return settled, counts


# --------------------------------------------------------------- interviews
def interviews(ex: Extract, units: dict) -> dict:
    found = {}
    for name in ex.names("interview__w"):
        for row in ex.records(name):
            if not in_scope(row.get("active", "")):
                continue
            unit = canonical_unit(row["unit_id"])
            if unit not in units:
                continue
            hours = str(row["hours_worked"]).strip()
            found[(unit, int(row["wave"]))] = {
                "activity": nfc(row["activity_code"]), "sector": nfc(row["sector_code"]),
                "hours": int(hours) if hours else None}
    return found


def prior_bands(ex: Extract) -> tuple[dict, dict]:
    first = {canonical_unit(r["unit_id"]): nfc(r["prior_band"])
             for r in ex.table("prior__wave1-bands.csv") if in_scope(r["active"])}
    second = {canonical_unit(r["unit_id"]): nfc(r["prior_band"])
              for r in ex.json_lines("prior__wave2-bands.jsonl") if in_scope(r["active"])}
    return first, second


def band_at(unit, wave, sheet, bands, first, second):
    record = sheet.get((unit, wave))
    if record is None:
        return None
    if record["hours"] is not None:
        return band_for_hours(bands, record["hours"])
    if wave == REFERENCE_WAVE:
        earlier = sheet.get((unit, 2))
        if earlier is not None and earlier["hours"] is not None:
            return band_for_hours(bands, earlier["hours"])
        if unit in second:
            return second[unit]
    if unit in first:
        return first[unit]
    return band_for_hours(bands, 0)


# --------------------------------------------------------------- weighting chain
def rake(weights: dict, memberships: dict, controls: dict, order, tolerance, limit,
         rounding: str):
    """Iterative proportional fitting.

    rounding "margin" rounds every weight each time a margin rescales it;
    rounding "iteration" keeps exact ratios through one iteration's margins and
    rounds once at its end. Between iterations weights are whole micro-units.
    """
    current = dict(weights)
    groups = {}
    for dimension in order:
        buckets = {}
        for unit in sorted(current):
            buckets.setdefault(memberships[dimension][unit], []).append(unit)
        groups[dimension] = buckets
    history, used, converged = [], 0, False
    while used < limit:
        used += 1
        exact = {u: Fraction(w) for u, w in current.items()}
        for dimension in order:
            for level, members in groups[dimension].items():
                target = controls.get(dimension, {}).get(level)
                total = sum(exact[u] for u in members)
                if target is None or total <= 0:
                    continue
                for u in members:
                    value = exact[u] * target / total
                    if rounding == "margin":
                        value = Fraction(divide(value.numerator, value.denominator))
                    exact[u] = value
        current = {u: divide(v.numerator, v.denominator) for u, v in exact.items()}
        worst = 0
        for dimension in order:
            for level, target in controls.get(dimension, {}).items():
                total = sum(current[u] for u in groups[dimension].get(level, []))
                worst = max(worst, abs(total - target))
        history.append(worst)
        if worst <= tolerance:
            converged = True
            break
    return current, history, used, converged


def pilot_settings(ex: Extract, settings: dict):
    """The one (margin order, rounding point) that reproduces the pilot's figures."""
    pilot = ex.document("calib__pilot-round.json")
    rows = [r for r in pilot["units"] if in_scope(r.get("active", ""))]
    start = {r["pilot_id"]: int(r["adjusted_weight_uw"]) for r in rows}
    dims = settings["margins"]
    members = {d: {r["pilot_id"]: nfc(r[d]) for r in rows} for d in dims}
    targets = {d: {nfc(k): int(v) for k, v in pilot["controls_uw"].get(d, {}).items()}
               for d in dims}
    published = pilot["published"]
    wanted_totals = {d: {nfc(k): int(v) for k, v in levels.items()}
                     for d, levels in published["raked_totals_uw"].items()}
    matching = []
    for order in itertools.permutations(dims):
        for rounding in ("margin", "iteration"):
            result, _, used, _ = rake(start, members, targets, order, settings["tolerance"],
                                      settings["iteration_limit"], rounding)
            totals = {}
            for d in dims:
                for pid, level in members[d].items():
                    totals.setdefault(d, {})
                    totals[d][level] = totals[d].get(level, 0) + result[pid]
            if used == int(published["iterations_used"]) and totals == wanted_totals:
                matching.append((list(order), rounding))
    if len(matching) != 1:
        raise SystemExit("the pilot record does not single out one setting combination")
    return matching[0]


def adjustment_key(record: dict, tenure_class: dict, depth: int) -> str:
    parts = [record["stratum"], tenure_class.get(record["tenure"], "owner"), record["band"]]
    return "|".join(parts[:3 - depth])


def weighting_chain(design: dict, eligible: set, responding: set, ctx: dict) -> dict:
    """Nonresponse adjustment, raking and gated trimming over one weight set."""
    settings, units = ctx["settings"], ctx["units"]
    depth = {u: 0 for u in eligible}

    def tally():
        cells = {}
        for u in eligible:
            key = adjustment_key(units[u], ctx["tenure_class"], depth[u])
            cell = cells.setdefault(key, [0, 0, 0])
            cell[0] += design[u]
            if u in responding:
                cell[1] += design[u]
                cell[2] += 1
        return cells

    rounds = 0
    while rounds < settings["collapse_limit"]:
        rounds += 1
        cells = tally()
        failing = set()
        for key, (wide, narrow, heads) in cells.items():
            rate = divide(BASIS * narrow, wide) if wide else 0
            if rate < settings["min_rate"] or heads < settings["min_count"]:
                failing.add(key)
        movers = [u for u in eligible if depth[u] < 2 and
                  adjustment_key(units[u], ctx["tenure_class"], depth[u]) in failing]
        for u in movers:
            depth[u] += 1
        if not movers:
            break
    cells = tally()
    factors = {key: divide(MICRO * wide, narrow) if narrow else 0
               for key, (wide, narrow, _) in cells.items()}
    cell_of = {u: adjustment_key(units[u], ctx["tenure_class"], depth[u]) for u in responding}
    adjusted = {u: divide(design[u] * factors[cell_of[u]], MICRO) for u in responding}

    memberships = {d: {u: ctx["margin_key"][d][u] for u in responding} for d in ctx["order"]}
    raked, history, used, converged = rake(adjusted, memberships, ctx["controls"], ctx["order"],
                                           settings["tolerance"], settings["iteration_limit"],
                                           ctx["rounding"])

    final = dict(raked)
    by_stratum = {}
    for u in responding:
        by_stratum.setdefault(units[u]["stratum"], []).append(u)
    ceilings, capped, spared = {}, [], 0
    for stratum, members in sorted(by_stratum.items()):
        values = sorted(raked[u] for u in members)
        ceiling = divide(values[(len(values) - 1) // 2] * settings["trim_ratio"], BASIS)
        ceilings[stratum] = ceiling
        total = sum(values)
        effect = divide(BASIS * len(values) * sum(v * v for v in values), total * total)
        if effect <= settings["trim_trigger"]:
            spared += sum(1 for v in values if v > ceiling)
            continue
        over = [u for u in members if raked[u] > ceiling]
        if not over:
            continue
        removed = sum(raked[u] - ceiling for u in over)
        for u in over:
            final[u] = ceiling
        capped.extend(over)
        keepers = [u for u in members if raked[u] <= ceiling]
        base = sum(raked[u] for u in keepers)
        if base <= 0:
            continue
        handed = 0
        for u in keepers:
            share = divide(removed * raked[u], base)
            final[u] = raked[u] + share
            handed += share
        if removed != handed:
            receiver = min(keepers, key=lambda u: (-final[u], u))
            final[receiver] += removed - handed
    return {"rounds": rounds, "cells": cells, "factors": factors, "cell_of": cell_of,
            "adjusted": adjusted, "raked": raked, "history": history, "used": used,
            "converged": converged, "final": final, "ceilings": ceilings,
            "capped": sorted(capped), "spared": spared}


# --------------------------------------------------------------- replication
def replication_groups(units: dict, strata: dict):
    psus_of = {}
    for record in units.values():
        psus_of.setdefault(record["stratum"], set()).add(record["psu"])
    owner = {s: s for s in psus_of}
    for stratum in sorted(psus_of):
        if len(psus_of[stratum]) < 2:
            partner = strata[stratum]["collapse_partner"]
            if partner in psus_of:
                owner[stratum] = owner.get(partner, partner)
    members, psus = {}, {}
    for stratum, group in owner.items():
        members.setdefault(group, []).append(stratum)
        psus.setdefault(group, set()).update(psus_of[stratum])
    live = {g: sorted(p) for g, p in psus.items() if len(p) >= 2}
    return live, {g: sorted(s) for g, s in members.items()}, owner


# --------------------------------------------------------------- output helpers
def write_json(folder: Path, name: str, payload) -> None:
    (folder / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                               encoding="utf-8", newline="\n")


def write_rows(folder: Path, name: str, header: list[str], rows, sep: str) -> None:
    lines = [sep.join(header)] + [sep.join(str(v) for v in row) for row in rows]
    (folder / name).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def flag(value: bool) -> str:
    return "Y" if value else "N"


# --------------------------------------------------------------- main derivation
def derive(data_dir: Path, out_dir: Path) -> None:
    ex = Extract(data_dir)
    reg = load_registers(ex)
    settings = load_settings(ex)
    controls, provenance = resolve_controls(ex)
    frame = resolve_frame(ex, reg)
    units = frame["units"]
    settled, counts = contact_history(ex, units, reg["precedence"])
    for unit, record in units.items():
        prior_attempts = counts.get((unit, 1), 0) + counts.get((unit, 2), 0)
        record["band"] = next((code for low, high, code in reg["contact_bands"]
                               if low <= prior_attempts <= high), "")
    sheet = interviews(ex, units)
    first, second = prior_bands(ex)

    eligible, responding = set(), set()
    for unit, record in units.items():
        verdict = settled.get((unit, REFERENCE_WAVE))
        if verdict and verdict["eligible"] and record["dwellings"] != 0:
            eligible.add(unit)
            if (verdict["responding"] and not verdict["superseded"]
                    and (unit, REFERENCE_WAVE) in sheet):
                responding.add(unit)

    counts = {}
    for record in units.values():
        counts[record["stratum"]] = counts.get(record["stratum"], 0) + 1
    design = {}
    for unit, record in units.items():
        base = divide(MICRO * int(reg["strata"][record["stratum"]]["population_units"]),
                      counts[record["stratum"]])
        design[unit] = divide(base * BASIS, frame["subsample_bp"]) if record["subsampled"] else base

    band_now = {u: band_at(u, REFERENCE_WAVE, sheet, reg["bands"], first, second)
                for u in responding}
    margin_key = {
        "region_tenure": {u: "%s|%s" % (units[u]["region"], units[u]["tenure"]) for u in responding},
        "activity": {u: sheet[(u, REFERENCE_WAVE)]["activity"] for u in responding},
        "band": band_now,
    }
    order, rounding = pilot_settings(ex, settings)
    ctx = {"settings": settings, "units": units, "tenure_class": reg["tenure_class"],
           "rounding": rounding,
           "margin_key": margin_key, "controls": controls, "order": order}
    round_chain = weighting_chain(design, eligible, responding, ctx)
    final = round_chain["final"]

    groups, group_strata, owner = replication_groups(units, reg["strata"])
    replicates = []
    for group in sorted(groups):
        size = len(groups[group])
        for dropped in groups[group]:
            weights = {}
            for unit, value in design.items():
                if owner[units[unit]["stratum"]] != group:
                    weights[unit] = value
                elif units[unit]["psu"] == dropped:
                    weights[unit] = 0
                else:
                    weights[unit] = divide(value * size, size - 1)
            alive_eligible = {u for u in eligible if weights[u] > 0}
            alive = {u for u in responding if weights[u] > 0}
            chain = weighting_chain(weights, alive_eligible, alive, ctx)
            replicates.append({"id": "%s::%s" % (group, dropped), "group": group,
                               "dropped": dropped, "size": size, "chain": chain,
                               "alive": alive})

    ranked = sorted(responding, key=lambda u: (final[u], u))
    quintile = {u: "Q%d" % (1 + (5 * i) // len(ranked)) for i, u in enumerate(ranked)}
    classifiers = {
        "activity_by_region": (lambda u: sheet[(u, REFERENCE_WAVE)]["activity"],
                               lambda u: units[u]["region"]),
        "tenure_by_wquintile": (lambda u: units[u]["tenure"], lambda u: quintile[u]),
        "hours_by_sector": (lambda u: sheet[(u, REFERENCE_WAVE)]["sector"],
                            lambda u: band_now[u]),
        "band_transition": (lambda u: band_at(u, 1, sheet, reg["bands"], first, second),
                            lambda u: band_now[u]),
    }

    def tabulate(table, members, weights):
        row_of, col_of = classifiers[table]
        rows = reg["levels"][(table, "row")]
        cols = reg["levels"][(table, "column")]
        grid = {(r, c): [0, 0, 0] for r in rows for c in cols}
        for u in members:
            slot = grid.get((row_of(u), col_of(u)))
            if slot is not None:
                slot[0] += weights[u]
                slot[1] += 1
                slot[2] = max(slot[2], weights[u])
        return rows, cols, grid

    tables, variance, by_group = {}, {}, {}
    for table in TABLE_NAMES:
        rows, cols, grid = tabulate(table, responding, final)
        spread = {key: 0 for key in grid}
        parts = {}
        for rep in replicates:
            _, _, rep_grid = tabulate(table, rep["alive"], rep["chain"]["final"])
            k = rep["size"]
            gained = 0
            for key, slot in grid.items():
                gap = rep_grid[key][0] - slot[0]
                term = (k - 1) * gap * gap // k
                spread[key] += term
                gained += term
            parts[rep["group"]] = parts.get(rep["group"], 0) + gained
        listing = []
        for r in rows:
            for c in cols:
                total, heads, biggest = grid[(r, c)]
                error = rounded_root(spread[(r, c)])
                listing.append({"cell_key": "%s|%s" % (r, c), "row": r, "col": c,
                                "total": total, "heads": heads, "error": error,
                                "cv": divide(BASIS * error, total) if total > 0 else 0,
                                "dominance": divide(BASIS * biggest, total) if total > 0 else 0})
        tables[table] = {"rows": rows, "cols": cols, "cells": listing}
        variance[table] = sum(spread.values())
        by_group[table] = parts

    everything = [(cell["cv"], table, cell["cell_key"]) for table in TABLE_NAMES
                  for cell in tables[table]["cells"]]
    everything.sort(key=lambda item: (-item[0], item[1], item[2]))
    rank_of = {(table, key): position for position, (_, table, key)
               in enumerate(everything, start=1)}

    primary, secondary, rounds_used = {}, {}, {}
    for table in TABLE_NAMES:
        info = tables[table]
        by_key = {cell["cell_key"]: cell for cell in info["cells"]}
        hits = []
        for cell in info["cells"]:
            reasons = []
            if cell["heads"] < settings["min_publish"]:
                reasons.append("count")
            if cell["cv"] > settings["max_cv"]:
                reasons.append("cv")
            if cell["dominance"] > settings["max_dominance"]:
                reasons.append("dominance")
            cell["reasons"] = reasons
            if reasons:
                hits.append(cell["cell_key"])
        hidden = set(hits)
        protective, passes = [], 0
        lines = ([("row", r, ["%s|%s" % (r, c) for c in info["cols"]]) for r in info["rows"]]
                 + [("column", c, ["%s|%s" % (r, c) for r in info["rows"]])
                    for c in info["cols"]])
        while passes < settings["cascade_limit"]:
            passes += 1
            added = False
            for axis, level, keys in lines:
                if sum(1 for k in keys if k in hidden) != 1:
                    continue
                open_cells = [k for k in keys if k not in hidden]
                if not open_cells:
                    continue
                pick = min(open_cells, key=lambda k: (by_key[k]["heads"], k))
                hidden.add(pick)
                protective.append({"cell_key": pick, "axis": axis, "axis_level": level,
                                   "round": passes})
                added = True
            if not added:
                break
        primary[table] = sorted(hits)
        secondary[table] = sorted(protective, key=lambda e: e["cell_key"])
        rounds_used[table] = passes

    out = out_dir
    out.mkdir(parents=True, exist_ok=True)

    write_json(out, "frame_audit.json", {
        "repair_counts": frame["repairs"], "self_referencing_units": frame["self_links"],
        "dangling_parent_units": frame["dangling"],
        "discarded_record_ids": frame["discarded"], "resolved_unit_count": len(units),
        "subsample_factor_bp": frame["subsample_bp"]})

    grand_total = sum(controls.get("region_tenure", {}).values())
    write_json(out, "control_totals.json", {
        "reference_period": REFERENCE_PERIOD, "grand_total_uw": grand_total,
        "dimensions": controls, "level_counts": {d: len(v) for d, v in controls.items()}})
    write_rows(out, "control_margins.tsv",
               ["dimension", "level_key", "control_total_uw", "chosen_rank", "chosen_source"],
               [[d, lv, controls[d][lv], provenance[(d, lv)][0], provenance[(d, lv)][1]]
                for d in sorted(controls) for lv in sorted(controls[d])], "\t")

    at_wave = {u: v for (u, w), v in settled.items() if w == REFERENCE_WAVE}
    tallies = {}
    for verdict in at_wave.values():
        tallies[verdict["disposition"]] = tallies.get(verdict["disposition"], 0) + 1
    write_json(out, "response_status.json", {
        "reference_wave": REFERENCE_WAVE, "disposition_counts": tallies,
        "eligible_count": len(eligible), "responding_count": len(responding),
        "superseded_units": sorted(u for u, v in at_wave.items() if v["superseded"]),
        "units": {u: {"disposition": v["disposition"], "attempt_no": v["attempt_no"],
                      "resolved_utc": v["resolved_utc"], "attempts": v["attempts"]}
                  for u, v in at_wave.items()}})

    write_rows(out, "design_weights.csv",
               ["unit_id", "stratum", "psu_code", "subsampled", "design_weight_uw"],
               [[u, units[u]["stratum"], units[u]["psu"], flag(units[u]["subsampled"]),
                 design[u]] for u in sorted(units)], ",")

    cells_out = []
    for key in sorted(round_chain["cells"]):
        wide, narrow, heads = round_chain["cells"][key]
        cells_out.append({"cell_key": key, "depth": key.count("|"),
                          "eligible_weight_uw": wide, "responding_weight_uw": narrow,
                          "responding_count": heads,
                          "response_rate_bp": divide(BASIS * narrow, wide) if wide else 0,
                          "adjustment_factor_uw": round_chain["factors"][key]})
    write_json(out, "adjustment_cells.json", {
        "collapse_rounds": round_chain["rounds"], "cell_count": len(cells_out),
        "cells": cells_out,
        "depth_counts": {str(d): sum(1 for c in cells_out if c["depth"] == d)
                         for d in range(3)}})
    write_rows(out, "adjusted_weights.csv",
               ["unit_id", "cell_key", "adjustment_factor_uw", "adjusted_weight_uw"],
               [[u, round_chain["cell_of"][u], round_chain["factors"][round_chain["cell_of"][u]],
                 round_chain["adjusted"][u]] for u in sorted(responding)], ",")

    write_json(out, "raking_trace.json", {
        "margin_order": order, "tolerance_uw": settings["tolerance"],
        "max_iterations": settings["iteration_limit"],
        "iterations_used": round_chain["used"], "converged": round_chain["converged"],
        "final_max_deviation_uw": round_chain["history"][-1] if round_chain["history"] else 0,
        "per_iteration": [{"iteration": i, "max_deviation_uw": d}
                          for i, d in enumerate(round_chain["history"], start=1)]})

    capped = set(round_chain["capped"])
    write_rows(out, "final_weights.csv",
               ["unit_id", "stratum", "raked_weight_uw", "trimmed", "final_weight_uw"],
               [[u, units[u]["stratum"], round_chain["raked"][u], flag(u in capped), final[u]]
                for u in sorted(responding)], ",")

    final_total = sum(final.values())
    ordered_weights = sorted(final.values())
    count = len(ordered_weights)
    stratum_totals = {}
    for u in responding:
        stratum_totals[units[u]["stratum"]] = stratum_totals.get(units[u]["stratum"], 0) + final[u]
    write_json(out, "weight_diagnostics.json", {
        "responding_count": count, "final_weight_total_uw": final_total,
        "design_effect_bp": divide(BASIS * count * sum(w * w for w in ordered_weights),
                                   final_total * final_total) if final_total else 0,
        "median_weight_uw": ordered_weights[(count - 1) // 2] if count else 0,
        "maximum_weight_uw": ordered_weights[-1] if count else 0,
        "minimum_weight_uw": ordered_weights[0] if count else 0,
        "trimmed_count": len(capped), "trimmed_units": sorted(capped),
        "stratum_totals_uw": stratum_totals, "stratum_ceilings_uw": round_chain["ceilings"]})

    write_json(out, "replicate_design.json", {
        "replicate_count": len(replicates), "group_count": len(groups),
        "groups": {g: {"psus": groups[g], "size": len(groups[g]), "strata": group_strata[g]}
                   for g in groups},
        "merged_groups": {g: group_strata[g] for g in groups if len(group_strata[g]) > 1}})
    write_rows(out, "replicate_summary.csv",
               ["replicate_id", "group", "dropped_psu", "group_size", "iterations_used",
                "converged", "trimmed_count", "final_total_uw"],
               [[r["id"], r["group"], r["dropped"], r["size"], r["chain"]["used"],
                 flag(r["chain"]["converged"]), len(r["chain"]["capped"]),
                 sum(r["chain"]["final"].values())]
                for r in sorted(replicates, key=lambda r: r["id"])], ",")

    for table in TABLE_NAMES:
        write_rows(out, "estimates_%s.csv" % table,
                   ["cell_key", "row_level", "column_level", "point_estimate_uw",
                    "unweighted_count", "standard_error_uw", "cv_bp", "dominance_bp"],
                   [[c["cell_key"], c["row"], c["col"], c["total"], c["heads"], c["error"],
                     c["cv"], c["dominance"]] for c in tables[table]["cells"]], ",")
    write_json(out, "variance_components.json", {
        "replicate_count": len(replicates),
        "tables": {t: {"summed_cell_variance_uw2": variance[t], "by_group": by_group[t]}
                   for t in TABLE_NAMES}})

    write_json(out, "cv_screening.json", {
        "min_publish_count": settings["min_publish"], "max_publish_cv_bp": settings["max_cv"],
        "dominance_bp": settings["max_dominance"],
        "tables": {t: [{"cell_key": c["cell_key"], "screening_rank": rank_of[(t, c["cell_key"])],
                        "cv_bp": c["cv"], "dominance_bp": c["dominance"],
                        "unweighted_count": c["heads"], "reasons": c["reasons"]}
                       for c in sorted(tables[t]["cells"],
                                       key=lambda c: rank_of[(t, c["cell_key"])])]
                   for t in TABLE_NAMES}})
    reasons_of = {(t, c["cell_key"]): c["reasons"] for t in TABLE_NAMES
                  for c in tables[t]["cells"]}
    write_json(out, "primary_suppression.json", {
        "tables": {t: [{"cell_key": k, "reasons": reasons_of[(t, k)]} for k in primary[t]]
                   for t in TABLE_NAMES},
        "counts": {t: len(primary[t]) for t in TABLE_NAMES},
        "total": sum(len(v) for v in primary.values())})
    write_json(out, "secondary_suppression.json", {
        "tables": secondary, "cascade_rounds": rounds_used,
        "counts": {t: len(secondary[t]) for t in TABLE_NAMES},
        "total": sum(len(v) for v in secondary.values())})

    audit, board, residual = [], {}, 0
    for table in TABLE_NAMES:
        first_set = set(primary[table])
        second_set = {e["cell_key"] for e in secondary[table]}
        total = shown = hidden_total = 0
        for c in tables[table]["cells"]:
            if c["cell_key"] in first_set:
                status, reason = "suppressed", "primary"
            elif c["cell_key"] in second_set:
                status, reason = "suppressed", "secondary"
            else:
                status, reason = "published", "none"
            total += c["total"]
            if status == "published":
                shown += c["total"]
            else:
                hidden_total += c["total"]
            audit.append([rank_of[(table, c["cell_key"])], table, c["cell_key"], status,
                          reason, c["total"], c["heads"], c["cv"]])
        board[table] = {"total_uw": total, "published_uw": shown,
                        "suppressed_uw": hidden_total,
                        "residual_uw": total - shown - hidden_total,
                        "coverage_gap_uw": final_total - total}
        residual += abs(total - shown - hidden_total)
    audit.sort(key=lambda r: (r[0], r[1], r[2]))
    write_rows(out, "disclosure_audit.tsv",
               ["screening_rank", "table_name", "cell_key", "status", "reason",
                "point_estimate_uw", "unweighted_count", "cv_bp"], audit, "\t")

    deviation = 0
    for dimension, levels in controls.items():
        for level, target in levels.items():
            held = sum(final[u] for u in responding if margin_key[dimension][u] == level)
            deviation = max(deviation, abs(held - target))
    observed = [int(round_chain["converged"]),
                int(abs(final_total - grand_total) <= settings["tolerance"]),
                int(sum(round_chain["raked"].values()) == final_total),
                int(residual == 0)]
    checks = [{"name": name, "expected": 1, "observed": seen,
               "verdict": "pass" if seen == 1 else "fail"}
              for name, seen in zip(["raking_converged", "final_total_within_tolerance",
                                     "trimming_preserves_total", "suppression_conservation"],
                                    observed)]
    write_json(out, "closure_report.json", {
        "post_trim_margin_deviation_uw": deviation, "final_weight_total_uw": final_total,
        "control_grand_total_uw": grand_total, "conservation_residual_uw": residual,
        "final_total_gap_uw": final_total - grand_total,
        "responding_count": len(responding), "replicate_count": len(replicates),
        "primary_suppression_total": sum(len(v) for v in primary.values()),
        "secondary_suppression_total": sum(len(v) for v in secondary.values()),
        "tables": board, "checks": checks,
        "all_checks_pass": all(c["verdict"] == "pass" for c in checks)})


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: derive_survey.py DATA_DIR OUT_DIR", file=sys.stderr)
        return 2
    derive(Path(argv[1]), Path(argv[2]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
