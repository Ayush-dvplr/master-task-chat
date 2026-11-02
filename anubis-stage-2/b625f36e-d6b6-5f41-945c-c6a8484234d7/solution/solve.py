#!/usr/bin/env python3
"""Materialize the Marrowgate settlement ledger.

    python3 materialize.py --data <corpus dir> --out <destination dir>

Reads only the directory --data names and writes every deliverable other than
itself into the directory --out names. Standard library only.

The program follows the shipped specification directly: settlement-protocol.md
governs membership, disposition, selection, arithmetic and outcome;
settlement-calendar.md supplies the eight settlement windows; entity-model.md
supplies the join normalization, the merge walk and the effective dated
lookups; record-layouts.md supplies the six serializations and their units;
reason-codes.md supplies the closed vocabularies; ledger-output-contract.md
supplies the bytes of every deliverable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from pathlib import Path

LF = "\n"

# reason-codes.md, "Revision classes", and the class rank in protocol section 3
RANK = {"ORIGINAL": 0, "AMENDMENT": 1, "CORRECTION": 2,
        "REVERSAL": 3, "RESTATEMENT": 4}
CLASSES = frozenset(RANK)

# record-layouts.md: the ten logical fields, the family each file name belongs
# to, the serialization it uses and the unit its quantity field carries.
LOGICAL_FIELDS = ("event_key", "revision_no", "revision_class", "site_ref",
                  "meter_id", "occurred_at", "ingested_at", "quantity",
                  "delta_flag", "supersedes_revision")

FIXED_WIDTH_COLUMNS = (("event_key", 12), ("revision_no", 4),
                       ("revision_class", 12), ("site_ref", 16),
                       ("meter_id", 10), ("occurred_at", 22),
                       ("ingested_at", 22), ("quantity", 14),
                       ("delta_flag", 2), ("supersedes_revision", 4))

FAMILY_PATTERNS = (
    (re.compile(r"^readings_desk_\d+\.csv$"), "desk", "delimited,", "kwh"),
    (re.compile(r"^readings_import_\d+\.jsonl$"), "import", "json", "kwh"),
    (re.compile(r"^readings_relay_\d+\.tsv$"), "relay", "delimited\t", "kwh"),
    (re.compile(r"^readings_partner_\d+\.psv$"), "partner", "delimited|", "kwh"),
    (re.compile(r"^readings_legacy_\d+\.fixed$"), "legacy", "fixed", "kwh"),
    (re.compile(r"^adjustments_\d+\.jsonl$"), "adjustment", "json", "wh"),
)

HYPHEN_PADDING = re.compile(r"\s*-\s*")
# record-layouts.md: the numeral grammar of each unit, ASCII characters only.
KWH_NUMERAL = re.compile(r"[+-]?[0-9]+(?:\.[0-9]+)?")
WH_NUMERAL = re.compile(r"[+-]?[0-9]+")
# protocol check 2: ASCII digits only, leading zeros carry no meaning.
REVISION_NUMBER = re.compile(r"[0-9]+")
LINE_BREAK = re.compile(r"\r?\n")
CALENDAR_LINE = re.compile(r"^(\d{8})\s+opens\s+(\S+)\s*$", re.MULTILINE)
SETTINGS_LINE = re.compile(r"^([A-Za-z0-9_.]+)\s*[=:]\s*(.*?)$")

CONFIG_LAYERS = ("settlement_defaults.ini", "network_policy.conf",
                 "site_overrides.properties")


# ---------------------------------------------------------------------------
# instants and the settlement calendar
# ---------------------------------------------------------------------------

def read_instant(text):
    """An instant in Z form, or in the fixed offset form carrying a trailing
    +HH:MM or -HH:MM that names the shift between the reading as written and
    UTC. None when the text does not parse as either."""
    if not isinstance(text, str):
        return None
    if len(text) == 25 and text[19] in "+-" and text[22] == ":":
        try:
            stamp = datetime.strptime(text, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            return None
        return stamp.astimezone(timezone.utc)
    if len(text) != 20:
        return None
    if text[10] != "T" or text[19] != "Z":
        return None
    try:
        stamp = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return stamp.replace(tzinfo=timezone.utc)


class Calendar:
    """The settlement days, taken from settlement-calendar.md rather than
    assumed. Each window is half open and runs for twenty four hours."""

    def __init__(self, text):
        self.windows = []
        for key, opens in CALENDAR_LINE.findall(text):
            start = read_instant(opens)
            if start is not None:
                self.windows.append((key, start, start + timedelta(days=1)))
        self.windows.sort(key=lambda window: window[1])
        self.keys = [window[0] for window in self.windows]

    def day_of(self, moment):
        if moment is None:
            return None
        for key, start, stop in self.windows:
            if start <= moment < stop:
                return key
        return None


# ---------------------------------------------------------------------------
# entity-model.md: join normalization
# ---------------------------------------------------------------------------

def join_form(raw):
    """NFC composition, tabs to spaces, whitespace runs collapsed, hyphen
    padding removed, stripped, case folded to upper case."""
    if not isinstance(raw, str):
        return ""
    text = unicodedata.normalize("NFC", raw).replace("\t", " ")
    text = " ".join(text.split())
    text = HYPHEN_PADDING.sub("-", text)
    return text.strip().casefold().upper()


# ---------------------------------------------------------------------------
# quantities
# ---------------------------------------------------------------------------

def numeral_value(text, unit):
    """The exact decimal a quantity field denotes when it is a numeral of the
    grammar its unit has, otherwise None."""
    grammar = WH_NUMERAL if unit == "wh" else KWH_NUMERAL
    if not isinstance(text, str) or grammar.fullmatch(text) is None:
        return None
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError, ArithmeticError):
        return None


def ascii_whole(text):
    """A whole number written in the ten ASCII digits, or None. A digit drawn
    from another script is not a decimal digit of this grammar."""
    if not isinstance(text, str) or REVISION_NUMBER.fullmatch(text) is None:
        return None
    return int(text)


def revision_number(text):
    """A revision number written in ASCII digits, or None."""
    return ascii_whole(text)


def to_watt_hours(text, unit, pulse=1):
    """The quantity field read in the unit its batch family declares, as
    integer watt-hours. The pulse multiplier reaches the exact decimal the
    numeral denotes, so the product is quantized once here and the integer
    this returns is never scaled again."""
    value = numeral_value(text, unit)
    if value is None:
        return None
    exact = value * pulse * (1 if unit == "wh" else 1000)
    return int(exact.to_integral_value(rounding=ROUND_HALF_EVEN))


def kwh_presentation(watt_hours, places):
    scaled = Decimal(watt_hours) / Decimal(1000)
    return str(scaled.quantize(Decimal(1).scaleb(-places),
                               rounding=ROUND_HALF_EVEN))


# ---------------------------------------------------------------------------
# reading the corpus
# ---------------------------------------------------------------------------

def classify_file(name):
    """(family, serialization, unit) for a registered batch file name."""
    for pattern, family, serialization, unit in FAMILY_PATTERNS:
        if pattern.match(name):
            return family, serialization, unit
    return None


def read_table(path, separator=","):
    """A delimited reference table, skipping any line whose field count
    disagrees with the header."""
    with open(path, encoding="utf-8") as handle:
        lines = [line for line in handle.read().split(LF) if line != ""]
    if not lines:
        return []
    header = lines[0].split(separator)
    table = []
    for line in lines[1:]:
        cells = line.split(separator)
        if len(cells) == len(header):
            table.append(dict(zip(header, cells)))
    return table


def read_body(path, serialization):
    """Every body line of one batch as ten logical string fields. A line the
    serialization cannot yield ten fields for is still a body line and is
    handed on empty, so validation rejects it rather than the reader losing
    it."""
    blank = dict((field, "") for field in LOGICAL_FIELDS)
    # utf-8-sig drops a byte order mark ahead of the first line, and a line
    # ends at LF or CR LF, so no carriage return reaches the last field.
    with open(path, encoding="utf-8-sig", newline="") as handle:
        lines = [line for line in LINE_BREAK.split(handle.read()) if line != ""]
    body = []
    if serialization == "fixed":
        for line in lines:
            record = {}
            at = 0
            for field, width in FIXED_WIDTH_COLUMNS:
                record[field] = line[at:at + width].strip()
                at += width
            body.append(record)
        return body
    if serialization == "json":
        for line in lines:
            try:
                obj = json.loads(line)
            except ValueError:
                body.append(dict(blank))
                continue
            body.append(dict((f, str(obj.get(f, ""))) for f in LOGICAL_FIELDS))
        return body
    if not lines:
        return body
    separator = serialization[-1]
    header = lines[0].split(separator)
    for line in lines[1:]:
        cells = line.split(separator)
        if len(cells) != len(header):
            body.append(dict(blank))
            continue
        named = dict(zip(header, cells))
        body.append(dict((f, named.get(f, "")) for f in LOGICAL_FIELDS))
    return body


class Reference:
    """The effective dated reference tables, the merge history, and the
    registered sites and meters."""

    def __init__(self, datadir):
        def at(name):
            return os.path.join(datadir, name)

        self.attributes = defaultdict(list)
        for row in read_table(at("sites_effective.csv")):
            self.attributes[row["site_id"]].append(
                (read_instant(row["valid_from"]), read_instant(row["valid_to"]),
                 (row["tariff_class"], row["zone"])))
        self.operational = defaultdict(list)
        for row in read_table(at("operational_state.csv")):
            self.operational[row["site_id"]].append(
                (read_instant(row["valid_from"]), read_instant(row["valid_to"]),
                 row["state"]))
        self.ceilings = defaultdict(list)
        for row in read_table(at("max_interval_limits.csv")):
            self.ceilings[row["site_id"]].append(
                (read_instant(row["valid_from"]), read_instant(row["valid_to"]),
                 int(row["max_interval_wh"])))
        self.bands = defaultdict(list)
        for row in read_table(at("tariff_classes.csv")):
            self.bands[row["tariff_class"]].append(
                (int(row["threshold_wh"]), row["band"]))
        for tariff_class in self.bands:
            self.bands[tariff_class].sort()
        self.absorbed = {}
        for row in read_table(at("site_merges.csv")):
            self.absorbed[row["absorbed_site"]] = (
                row["survivor_site"], read_instant(row["merge_instant"]))
        self.meters = {}
        self.sites = set()
        self.unreadable_registrations = 0
        for row in read_table(at("meter_registry.csv")):
            # entity-model.md: a row whose pulse_multiplier is absent, or is
            # not a positive whole number in the ten ASCII digits, is no
            # registration at all. It covers no instant, it governs nothing,
            # and it registers no site.
            pulse = ascii_whole(row.get("pulse_multiplier", ""))
            if pulse is None or pulse < 1:
                self.unreadable_registrations += 1
                continue
            self.meters.setdefault(row["meter_id"], []).append(
                (read_instant(row["valid_from"]),
                 read_instant(row["valid_to"]), (row["site_id"], pulse)))
            self.sites.add(row["site_id"])
        self.sites.update(self.attributes)

    @staticmethod
    def _effective(rows, moment):
        """Half open [valid_from, valid_to) pick at one instant. These files
        are corrected in place rather than rewritten, so more than one row of
        one key can cover one instant: the row that opens latest governs, and
        where two covering rows open together the one that closes earliest
        does, because the narrower row is the later correction. The order the
        rows sit in the file decides nothing."""
        if moment is None:
            return None
        governing = None
        for start, stop, payload in rows:
            if start is None or stop is None or not start <= moment < stop:
                continue
            if (governing is None or start > governing[0]
                    or (start == governing[0] and stop < governing[1])):
                governing = (start, stop, payload)
        return None if governing is None else governing[2]

    def survivor_of(self, site, moment):
        """The site the merge chain reaches, taking each hop only from its own
        instant forward and stopping at the first hop the instant precedes."""
        here = site
        walked = set()
        while here in self.absorbed and here not in walked:
            walked.add(here)
            survivor, when = self.absorbed[here]
            if when is None or moment is None or moment < when:
                break
            here = survivor
        return here

    def attributes_at(self, site, moment):
        return self._effective(self.attributes.get(site, []), moment)

    def state_at(self, site, moment):
        found = self._effective(self.operational.get(site, []), moment)
        return found if found is not None else "ACTIVE"

    def ceiling_at(self, site, moment):
        """The interval ceiling governing the site at one instant, or None
        where no row of the file covers it. A hole is not a ceiling of zero
        and no ceiling is ever assumed in its place."""
        return self._effective(self.ceilings.get(site, []), moment)

    def registration_at(self, meter, moment):
        """The site a meter was registered to at one instant paired with the
        pulse multiplier that registration carries, or None when the meter
        held no registration then."""
        return self._effective(self.meters.get(meter, []), moment)

    def band_for(self, tariff_class, watt_hours):
        """The band whose threshold is the greatest threshold at or below the
        quantity; below every threshold of the class, the literal UNBANDED."""
        chosen = "UNBANDED"
        for threshold, name in self.bands.get(tariff_class, []):
            if threshold > watt_hours:
                break
            chosen = name
        return chosen


def resolve_settings(datadir):
    """Three layers in the order the protocol names. Last wins everywhere
    except the rounding namespace, where the numerically smallest value set by
    any layer governs, whichever layer set it."""
    values = {}
    source = {}
    for layer in CONFIG_LAYERS:
        path = os.path.join(datadir, layer)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line[0] in "#;[":
                continue
            found = SETTINGS_LINE.match(line)
            if not found:
                continue
            key, value = found.group(1), found.group(2).strip()
            if key.startswith("rounding."):
                try:
                    number = int(value)
                except ValueError:
                    continue
                if key in values and number >= int(values[key]):
                    continue
                values[key] = str(number)
                source[key] = layer
            else:
                values[key] = value
                source[key] = layer
    return values, source


# ---------------------------------------------------------------------------
# ingestion: every body line receives exactly one disposition
# ---------------------------------------------------------------------------

def load_manifest(datadir):
    registered = []
    for row in read_table(os.path.join(datadir, "batch_manifest.csv")):
        try:
            sequence = int(row["batch_seq"])
            declared = int(row["expected_rows"])
        except (KeyError, ValueError):
            continue
        registered.append({"batch_id": row["batch_id"],
                           "filename": row["filename"],
                           "batch_seq": sequence,
                           "status": row["status"],
                           "expected_rows": declared})
    registered.sort(key=lambda entry: entry["batch_seq"])
    return registered


def reason_for(record, reference, unit, calendar):
    """The validation precedence of protocol section 2, stopping at the first
    failure, so a row failing two checks carries the code of the earlier
    one."""
    if record.get("revision_class", "") not in CLASSES:
        return "MALFORMED_ROW"
    number = revision_number(record.get("revision_no", ""))
    if number is None or number < 1:
        return "MALFORMED_ROW"
    moment = read_instant(record.get("occurred_at", ""))
    if moment is None:
        return "BAD_TIMESTAMP"
    if calendar.day_of(moment) is None:
        return "OUT_OF_CALENDAR"
    quantity = record.get("quantity", "")
    if quantity != "" and to_watt_hours(quantity, unit) is None:
        return "BAD_QUANTITY"
    if join_form(record.get("site_ref", "")) not in reference.sites:
        return "UNKNOWN_SITE"
    registration = reference.registration_at(
        record.get("meter_id", "").strip(), moment)
    if registration is None:
        return "UNKNOWN_METER"
    # check 8: the covering registration names the site the normalized
    # reference denotes, which is the site before any merge hop is taken.
    if registration[0] != join_form(record.get("site_ref", "")):
        return "METER_SITE_MISMATCH"
    return None


class Ingestion:
    """Walks the in scope batches in ascending batch_seq and gives every body
    line exactly one of ADMITTED, DUPLICATE, CONFLICT or REJECTED."""

    def __init__(self, datadir, reference, calendar):
        self.manifest = load_manifest(datadir)
        self.admitted = []
        self.rejected = []
        self.duplicates = []
        self.conflicts = []
        self.absent_batches = []
        self.row_exceptions = []
        self.body_lines = 0
        self.ingested_ids = []
        self.withdrawn_ids = []
        claimed = {}

        for entry in self.manifest:
            if entry["status"] != "ACTIVE":
                self.withdrawn_ids.append(entry["batch_id"])
                continue
            path = os.path.join(datadir, entry["filename"])
            if not os.path.exists(path):
                self.absent_batches.append(entry)
                continue
            self.ingested_ids.append(entry["batch_id"])
            shape = classify_file(entry["filename"])
            if shape is None:
                continue
            family, serialization, unit = shape
            body = read_body(path, serialization)
            if len(body) != entry["expected_rows"]:
                self.row_exceptions.append({
                    "batch_id": entry["batch_id"],
                    "declared_rows": entry["expected_rows"],
                    "filename": entry["filename"],
                    "observed_rows": len(body)})
            for line_no, record in enumerate(body, 1):
                self.body_lines += 1
                where = {"batch_id": entry["batch_id"],
                         "batch_seq": entry["batch_seq"],
                         "filename": entry["filename"],
                         "line_no": line_no}
                code = reason_for(record, reference, unit, calendar)
                if code is not None:
                    marked = dict(where)
                    marked["event_key"] = record.get("event_key", "")
                    marked["reason_code"] = code
                    self.rejected.append(marked)
                    continue
                identity = (record["event_key"],
                            revision_number(record["revision_no"]),
                            record["revision_class"], family)
                names = record["supersedes_revision"].strip()
                named = revision_number(names)
                names = names if named is None else str(named)
                # protocol section 2: the payload compares by value, so the
                # instant in UTC, the exact quantity and the named number
                payload = (join_form(record["site_ref"]),
                           record["meter_id"].strip(),
                           read_instant(record["occurred_at"]),
                           numeral_value(record["quantity"], unit)
                           if record["quantity"] != "" else None,
                           names)
                if identity in claimed:
                    marked = dict(where)
                    marked["event_key"] = identity[0]
                    marked["revision_no"] = identity[1]
                    marked["revision_class"] = identity[2]
                    marked["family"] = identity[3]
                    if claimed[identity] == payload:
                        self.duplicates.append(marked)
                    else:
                        self.conflicts.append(marked)
                    continue
                claimed[identity] = payload
                text = record["quantity"]
                # protocol 4: a delivered count stands for a whole number of
                # metered units, and the multiplier that says how many is read
                # at the row's own occurred_at, because a row is read as
                # delivered. Every admitted row cleared check 7, so exactly
                # one registration covers it.
                delivered = reference.registration_at(
                    payload[1], read_instant(record["occurred_at"]))
                pulse = 1 if delivered is None else delivered[1]
                self.admitted.append({
                    "event_key": identity[0],
                    "revision_no": identity[1],
                    "revision_class": identity[2],
                    "family": family,
                    "batch_id": entry["batch_id"],
                    "batch_seq": entry["batch_seq"],
                    "site_id": payload[0],
                    "meter_id": payload[1],
                    "occurred_at": record["occurred_at"],
                    "ingested_at": record["ingested_at"],
                    "supersedes_revision": names,
                    "quantity_wh": (to_watt_hours(text, unit, pulse)
                                    if text else None)})


# ---------------------------------------------------------------------------
# canonical state
# ---------------------------------------------------------------------------

def highest_ranked(revisions):
    """Highest class rank, then highest revision number, then the lowest batch
    sequence."""
    return min(revisions, key=lambda r: (-RANK[r["revision_class"]],
                                         -r["revision_no"], r["batch_seq"]))


class Materialization:
    """Everything the run computes, in the order the protocol builds it."""

    def __init__(self, datadir):
        with open(os.path.join(datadir, "settlement-calendar.md"),
                  encoding="utf-8") as handle:
            self.calendar = Calendar(handle.read())
        self.reference = Reference(datadir)
        self.settings, self.setting_source = resolve_settings(datadir)
        self.ingestion = Ingestion(datadir, self.reference, self.calendar)
        self.quantity_dp = int(self.settings.get("rounding.quantity_dp", "3"))
        self.total_dp = int(self.settings.get("rounding.total_dp", "2"))
        self.place_excluded = (
            self.settings.get("settlement.exclusion_policy", "omit")
            == "include")

        self.by_event = defaultdict(list)
        for revision in self.ingestion.admitted:
            self.by_event[revision["event_key"]].append(revision)

        self.events = [self._settle(key) for key in sorted(self.by_event)]
        self.events.sort(key=lambda event: (event["settlement_day"],
                                            event["canonical_site"],
                                            event["event_key"]))

        self.partitions = dict((day, []) for day in self.calendar.keys)
        for event in self.events:
            if event["outcome"] == "EXCLUDED" and not self.place_excluded:
                continue
            self.partitions[event["settlement_day"]].append(event)

        self.cells = {}
        for event in self.events:
            if event["outcome"] != "SETTLED":
                continue
            cell = self.cells.setdefault(
                (event["settlement_day"], event["zone"]),
                {"settled_wh": 0, "event_count": 0})
            cell["settled_wh"] += event["quantity_wh"]
            cell["event_count"] += 1

    def _settle(self, key):
        revisions = self.by_event[key]
        canonical = highest_ranked(revisions)
        moment = read_instant(canonical["occurred_at"])
        day = self.calendar.day_of(moment)

        source_site = canonical["site_id"]
        canonical_site = self.reference.survivor_of(source_site, moment)
        attributes = self.reference.attributes_at(canonical_site, moment)
        tariff_class, zone = attributes if attributes else ("", "")
        state = self.reference.state_at(canonical_site, moment)
        ceiling = self.reference.ceiling_at(canonical_site, moment)

        grounded = [r for r in revisions if r["revision_class"] != "RESTATEMENT"]
        base = highest_ranked(grounded) if grounded else None
        base_identity = None
        if base is not None:
            base_identity = (base["revision_no"], base["revision_class"],
                             base["family"])

        # T24: build displacement set (RESTATEMENT displaces RESTATEMENT)
        full_stack = sorted(
            (r for r in revisions if r["revision_class"] == "RESTATEMENT"),
            key=lambda r: (r["revision_no"], r["batch_seq"]))
        stack_nos = set(r["revision_no"] for r in full_stack)
        displaced = set()
        for _r in full_stack:
            named = revision_number(_r["supersedes_revision"])
            if named is not None and named in stack_nos:
                displaced.add(named)

        numbers = set(r["revision_no"] for r in revisions)
        outcome = None
        reason = ""
        if canonical["revision_class"] in ("CORRECTION", "RESTATEMENT"):
            names = canonical["supersedes_revision"]
            if revision_number(names) not in numbers:
                outcome, reason = "UNRESOLVABLE", "ORPHAN_SUPERSEDE"
        if outcome is None and base is None:
            outcome, reason = "UNRESOLVABLE", "MISSING_BASE"
        if outcome is None and ceiling is None:
            # protocol 5 test 3: a canonical site with no ceiling at the
            # effective instant leaves the event undecided, and that test is
            # weighed before the one that defers a base carrying no reading.
            outcome, reason = "UNRESOLVABLE", "MISSING_CEILING"

        quantity = 0
        clamp = None
        if outcome is None:
            if base["quantity_wh"] is None:
                outcome = "DEFERRED"
            else:
                raw = base["quantity_wh"]
                clamped = max(0, min(ceiling, raw))
                stack = sorted(
                    (r for r in full_stack
                     if r["revision_no"] not in displaced),
                    key=lambda r: (r["revision_no"], r["batch_seq"]))
                summed = clamped
                for delta in stack:
                    if delta["quantity_wh"] is not None:
                        summed += delta["quantity_wh"]
                final = max(0, min(ceiling, summed))
                stage = ""
                if clamped != raw and final != summed:
                    stage = "BOTH"
                elif clamped != raw:
                    stage = "BASE"
                elif final != summed:
                    stage = "SUM"
                if stage:
                    clamp = {"event_key": key,
                             "canonical_site": canonical_site,
                             "max_interval_wh": ceiling,
                             "base_wh": raw,
                             "base_clamped_wh": clamped,
                             "stack_delta_wh": summed - clamped,
                             "final_wh": final,
                             "clamp_stage": stage}
                quantity = final
                reversals = sum(1 for r in revisions
                                if r["revision_class"] == "REVERSAL")
                if (canonical["revision_class"] == "REVERSAL"
                        and reversals % 2 == 1):
                    outcome, quantity = "VOIDED", 0
                elif state == "SUSPENDED":
                    outcome = "EXCLUDED"
                else:
                    outcome = "SETTLED"

        return {"event_key": key,
                "settlement_day": day,
                "source_site": source_site,
                "canonical_site": canonical_site,
                "zone": zone,
                "tariff_class": tariff_class,
                "tariff_band": self.reference.band_for(tariff_class, quantity),
                "outcome": outcome,
                "reason_code": reason,
                "quantity_wh": quantity,
                "revision_no": canonical["revision_no"],
                "revision_class": canonical["revision_class"],
                "canonical_family": canonical["family"],
                "base_identity": base_identity,
                "clamp": clamp,
                "full_stack": full_stack,
                "displaced": displaced}


# ---------------------------------------------------------------------------
# the deliverables
# ---------------------------------------------------------------------------

def compact(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def document(obj):
    return json.dumps(obj, sort_keys=True, indent=2) + LF


def sheet(columns, rows):
    out = [",".join(columns)]
    out.extend(",".join(str(row[column]) for column in columns)
               for row in rows)
    return LF.join(out) + LF


def read_publication(datadir):
    with open(os.path.join(datadir, "published_baseline.json"),
              encoding="utf-8") as handle:
        published = json.load(handle)
    stated = {}
    for cell in published.get("cells", []):
        stated[(cell["settlement_day"], cell["zone"])] = (
            int(cell["settled_wh"]), int(cell["event_count"]))
    return stated


def build_deliverables(datadir):
    """Every deliverable other than the program itself, as exact bytes."""
    run = Materialization(datadir)
    published = read_publication(datadir)
    files = {}

    files["canonical_ledger.jsonl"] = "".join(
        compact({"canonical_site": event["canonical_site"],
                 "event_key": event["event_key"],
                 "outcome": event["outcome"],
                 "quantity_kwh": kwh_presentation(event["quantity_wh"],
                                                  run.quantity_dp),
                 "quantity_wh": event["quantity_wh"],
                 "revision_class": event["revision_class"],
                 "revision_no": event["revision_no"],
                 "settlement_day": event["settlement_day"],
                 "source_site": event["source_site"],
                 "tariff_band": event["tariff_band"],
                 "tariff_class": event["tariff_class"],
                 "zone": event["zone"]}) + LF
        for event in run.events)

    canonical_of = {}
    base_of = {}
    disp_of = {}
    for event in run.events:
        canonical_of[event["event_key"]] = (event["revision_no"],
                                            event["revision_class"],
                                            event["canonical_family"])
        base_of[event["event_key"]] = event["base_identity"]
        disp_of[event["event_key"]] = event["displaced"]
    staged = []
    for key in sorted(run.by_event):
        for revision in sorted(run.by_event[key],
                               key=lambda r: (r["revision_no"],
                                              r["revision_class"],
                                              r["family"])):
            identity = (revision["revision_no"], revision["revision_class"],
                        revision["family"])
            canonical = canonical_of.get(key) == identity
            if canonical:
                role = "CANONICAL"
            elif base_of.get(key) == identity:
                role = "BASE"
            elif revision["revision_class"] == "RESTATEMENT":
                if revision["revision_no"] in disp_of.get(key, ()):
                    role = "DISPLACED"
                else:
                    role = "RESTATEMENT_STACK"
            else:
                role = "SUPERSEDED"
            staged.append({"batch_id": revision["batch_id"],
                           "event_key": key,
                           "family": revision["family"],
                           "is_canonical": canonical,
                           "quantity_wh": revision["quantity_wh"],
                           "revision_class": revision["revision_class"],
                           "revision_no": revision["revision_no"],
                           "role": role})
    files["revision_index.jsonl"] = "".join(compact(obj) + LF for obj in staged)

    partition_columns = ["sequence_no", "event_key", "canonical_site", "zone",
                         "tariff_band", "outcome", "quantity_wh"]
    summary = []
    for day in run.calendar.keys:
        rows = run.partitions[day]
        numbered = []
        for position, event in enumerate(rows, 1):
            entry = dict((column, event[column])
                         for column in partition_columns[1:])
            entry["sequence_no"] = position
            numbered.append(entry)
        files["partition_%s.csv" % day] = sheet(partition_columns, numbered)
        settled_wh = sum(event["quantity_wh"] for event in rows
                         if event["outcome"] == "SETTLED")
        summary.append({"settlement_day": day,
                        "row_count": len(rows),
                        "settled_event_count": sum(
                            1 for event in rows
                            if event["outcome"] == "SETTLED"),
                        "settled_wh": settled_wh,
                        "settled_kwh": kwh_presentation(settled_wh,
                                                        run.total_dp)})
    files["partition_manifest.json"] = document({"partitions": summary})

    ingestion = run.ingestion

    def by_batch_then_line(rows):
        return sorted(rows, key=lambda row: (row["batch_id"], row["line_no"]))

    files["rejects.csv"] = sheet(
        ["batch_id", "filename", "line_no", "event_key", "reason_code"],
        by_batch_then_line(ingestion.rejected))
    files["quarantine.jsonl"] = "".join(
        compact({"batch_id": row["batch_id"], "event_key": row["event_key"],
                 "line_no": row["line_no"],
                 "revision_class": row["revision_class"],
                 "revision_no": row["revision_no"]}) + LF
        for row in by_batch_then_line(ingestion.conflicts))
    files["dedup_ledger.csv"] = sheet(
        ["batch_id", "line_no", "event_key", "revision_no", "revision_class"],
        by_batch_then_line(ingestion.duplicates))

    deferred = sorted((event for event in run.events
                       if event["outcome"] == "DEFERRED"),
                      key=lambda event: event["event_key"])
    files["deferred.jsonl"] = "".join(
        compact({"canonical_site": event["canonical_site"],
                 "event_key": event["event_key"],
                 "revision_no": event["revision_no"],
                 "settlement_day": event["settlement_day"]}) + LF
        for event in deferred)

    unresolved = sorted((event for event in run.events
                         if event["outcome"] == "UNRESOLVABLE"),
                        key=lambda event: event["event_key"])
    files["unresolvable.json"] = document({
        "events": [{"canonical_site": event["canonical_site"],
                    "event_key": event["event_key"],
                    "reason_code": event["reason_code"],
                    "settlement_day": event["settlement_day"]}
                   for event in unresolved],
        "missing_batches": [{"batch_id": batch["batch_id"],
                             "filename": batch["filename"],
                             "reason_code": "MISSING_BATCH"}
                            for batch in sorted(
                                ingestion.absent_batches,
                                key=lambda batch: batch["batch_id"])]})

    resolutions = [{"canonical_site": event["canonical_site"],
                    "event_key": event["event_key"],
                    "merge_applied": (event["canonical_site"]
                                      != event["source_site"]),
                    "source_site": event["source_site"]}
                   for event in run.events
                   if event["source_site"] in run.reference.absorbed]
    resolutions.sort(key=lambda entry: entry["event_key"])
    files["entity_resolution.json"] = document({"resolutions": resolutions})

    clamp_columns = ["event_key", "canonical_site", "max_interval_wh",
                     "base_wh", "base_clamped_wh", "stack_delta_wh",
                     "final_wh", "clamp_stage"]
    clamped = sorted((event["clamp"] for event in run.events
                      if event["clamp"]),
                     key=lambda record: record["event_key"])
    files["clamp_register.csv"] = sheet(clamp_columns, clamped)

    # T24: build stack_register.csv
    stack_columns = ["event_key", "revision_no", "family", "delta_wh",
                     "stack_state"]
    srows = []
    for event in run.events:
        for a in event["full_stack"]:
            # stack state priority: DISPLACED > WITHHELD > ABSENT > APPLIED
            if a["revision_no"] in event["displaced"]:
                state = "DISPLACED"
            elif event["outcome"] in ("DEFERRED", "UNRESOLVABLE"):
                state = "WITHHELD"
            elif a["quantity_wh"] is None:
                state = "ABSENT"
            else:
                state = "APPLIED"
            srows.append({"event_key": a["event_key"],
                          "revision_no": a["revision_no"],
                          "family": a["family"],
                          "delta_wh": (0 if a["quantity_wh"] is None
                                       else a["quantity_wh"]),
                          "stack_state": state})
    srows.sort(key=lambda s: (s["event_key"], s["revision_no"],
                              s["family"]))
    files["stack_register.csv"] = sheet(stack_columns, srows)

    adjustment_columns = ["settlement_day", "zone", "adjustment_kind",
                          "baseline_settled_wh", "restated_settled_wh",
                          "delta_wh", "baseline_event_count",
                          "restated_event_count", "delta_events"]
    adjustments = []
    published_total = 0
    delta_total = 0
    for cell in sorted(set(published) | set(run.cells)):
        was_wh, was_count = published.get(cell, (0, 0))
        now = run.cells.get(cell, {"settled_wh": 0, "event_count": 0})
        moved_wh = now["settled_wh"] - was_wh
        moved_count = now["event_count"] - was_count
        published_total += was_wh
        delta_total += moved_wh
        if moved_wh == 0 and moved_count == 0:
            continue
        adjustments.append({
            "settlement_day": cell[0], "zone": cell[1],
            "adjustment_kind": ("INCREASE" if moved_wh > 0
                                else "DECREASE" if moved_wh < 0
                                else "COUNT_ONLY"),
            "baseline_settled_wh": was_wh,
            "restated_settled_wh": now["settled_wh"],
            "delta_wh": moved_wh,
            "baseline_event_count": was_count,
            "restated_event_count": now["event_count"],
            "delta_events": moved_count})
    files["restatement_adjustments.csv"] = sheet(adjustment_columns,
                                                 adjustments)

    ledger_wh = sum(event["quantity_wh"] for event in run.events
                    if event["outcome"] == "SETTLED")
    partition_wh = sum(day["settled_wh"] for day in summary)
    admitted = len(ingestion.admitted)
    duplicate = len(ingestion.duplicates)
    conflict = len(ingestion.conflicts)
    rejected = len(ingestion.rejected)
    identities = {
        "identity_class_partition": {
            "admitted": admitted, "conflict": conflict,
            "duplicate": duplicate, "rejected": rejected,
            "residual": (admitted + duplicate + conflict + rejected
                         - ingestion.body_lines),
            "total_rows": ingestion.body_lines},
        "identity_partition_rollup": {
            "ledger_settled_wh": ledger_wh,
            "partition_settled_wh": partition_wh,
            "residual": partition_wh - ledger_wh},
        "identity_restatement": {
            "adjustment_delta_wh": delta_total,
            "baseline_settled_wh": published_total,
            "residual": published_total + delta_total - ledger_wh,
            "restated_settled_wh": ledger_wh},
    }
    files["reconciliation.json"] = document(identities)

    files["validation_report.txt"] = LF.join([
        "CLASS_PARTITION residual=%d"
        % identities["identity_class_partition"]["residual"],
        "PARTITION_ROLLUP residual=%d"
        % identities["identity_partition_rollup"]["residual"],
        "RESTATEMENT residual=%d"
        % identities["identity_restatement"]["residual"],
        "ROUNDING quantity_dp=%d total_dp=%d" % (run.quantity_dp, run.total_dp),
        "EXCLUSION policy=%s" % ("include" if run.place_excluded else "omit"),
        "CLAMPED events=%d" % len(clamped),
        "UNRESOLVED events=%d" % len(unresolved),
        "DISPLACED revisions=%d" % sum(1 for s in srows if s["stack_state"] == "DISPLACED"),
    ]) + LF

    files["run_manifest.json"] = document({
        "batches_ingested": sorted(ingestion.ingested_ids),
        "batches_withdrawn": sorted(ingestion.withdrawn_ids),
        "config_resolved": run.settings,
        "config_winner": run.setting_source,
        "row_exceptions": sorted(ingestion.row_exceptions,
                                 key=lambda record: record["batch_id"])})

    return files


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialize the Marrowgate settlement ledger.")
    parser.add_argument("--data",
                        default=os.environ.get("MG_DATA", "/app/data"))
    parser.add_argument("--out", default=os.environ.get("MG_OUT", "/app/out"))
    chosen = parser.parse_args()

    destination = Path(chosen.out)
    destination.mkdir(parents=True, exist_ok=True)

    for name, body in sorted(build_deliverables(chosen.data).items()):
        with open(os.path.join(chosen.out, name), "w", encoding="utf-8",
                  newline=LF) as handle:
            handle.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
