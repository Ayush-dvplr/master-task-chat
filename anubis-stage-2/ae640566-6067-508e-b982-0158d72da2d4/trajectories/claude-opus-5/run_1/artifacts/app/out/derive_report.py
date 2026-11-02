#!/usr/bin/env python3
"""Helios gravimeter array reconciliation transform.

Usage: derive_report.py <archive_dir> <output_dir>

Rebuilds the full report set for any archive obeying the Helios derivation
contract.  Every figure is carried in exact integer arithmetic.
"""

import csv
import json
import os
import re
import sys
from collections import defaultdict

REPORT_FILES = ("summary.json", "policy_audit.json", "data_quality.json")

NANO = 1000000
PPM = 1000000

# Quarantine precedence, as demonstrated by the calibration control.
QUARANTINE_ORDER = (
    "duplicate_sample",
    "unresolved_suspect",
    "malformed_sample",
    "unknown_channel",
    "no_deployment",
    "no_custody",
    "no_certificate",
    "unknown_unit",
    "broken_ladder",
    "unreported_array",
)

WHOLE_NUMBER_RE = re.compile(r"[+-]?[0-9]+\Z")
DIGITS_RE = re.compile(r"[0-9]+\Z")
INSTANT_RE = re.compile(
    r"([0-9]+)-([0-9]+)-([0-9]+)[T ]([0-9]+):([0-9]+):([0-9]+)\Z")
STRUCTURAL_RE = re.compile(r"HLS([0-9]+)\Z")


class Fault(Exception):
    """Raised when the written reports fail to reconcile."""


# ---------------------------------------------------------------- primitives

def round_ratio(numerator, denominator):
    """Exact integer division rounding halves away from zero."""
    if denominator < 0:
        numerator, denominator = -numerator, -denominator
    sign = -1 if numerator < 0 else 1
    magnitude = abs(numerator)
    quotient, remainder = divmod(magnitude, denominator)
    if 2 * remainder >= denominator:
        quotient += 1
    return sign * quotient


def parse_instant(text):
    """Return a comparable instant tuple, or None when unreadable."""
    if text is None:
        return None
    match = INSTANT_RE.match(text.strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


def is_whole_number(text):
    return text is not None and WHOLE_NUMBER_RE.match(text.strip()) is not None


def is_json_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def parse_factor(text):
    """Positive integer or ratio of positive integers, else None."""
    body = (text or "").strip()
    if "/" in body:
        parts = body.split("/")
        if len(parts) != 2:
            return None
        head, tail = parts[0].strip(), parts[1].strip()
        if DIGITS_RE.match(head) is None or DIGITS_RE.match(tail) is None:
            return None
        num, den = int(head), int(tail)
        if num <= 0 or den <= 0:
            return None
        return (num, den)
    if DIGITS_RE.match(body) is None:
        return None
    num = int(body)
    if num <= 0:
        return None
    return (num, 1)


def normalise_label(text):
    return re.sub(r"[^A-Z0-9]", "", (text or "").strip().upper())


def normalise_unit(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").strip().lower())


def read_bool(text, default):
    body = (text or "").strip().lower()
    if body == "":
        return default
    if body == "true":
        return True
    if body == "false":
        return False
    return default


def optional_int(text):
    """An empty override is absent; zero is supplied."""
    body = (text or "").strip()
    if body == "":
        return None
    return int(body)


def read_table(path):
    """Read the usual quoted CSV dialect, dropping wholly blank lines."""
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        rows = []
        reader = csv.reader(handle)
        header = None
        for raw in reader:
            if not any(cell.strip() for cell in raw):
                continue
            cells = [cell.strip() for cell in raw]
            if header is None:
                header = cells
                continue
            record = {}
            for index, name in enumerate(header):
                record[name] = cells[index] if index < len(cells) else ""
            rows.append(record)
        return rows


def read_json(path, default):
    if not os.path.isfile(path):
        return default
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_jsonl(path):
    """Yield (line_number, parsed_or_None) for every non-blank line."""
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                out.append((number, json.loads(line)))
            except ValueError:
                out.append((number, None))
    return out


# ------------------------------------------------------------------- archive

class Interval(object):
    __slots__ = ("start", "end")

    def __init__(self, start_text, end_text):
        self.start = parse_instant(start_text)
        self.end = parse_instant(end_text)

    def covers(self, instant):
        if self.start is not None and instant < self.start:
            return False
        if self.end is not None and instant > self.end:
            return False
        return True


class Archive(object):
    def __init__(self, directory):
        self.directory = directory
        self.policy = read_json(os.path.join(directory, "policy.json"), {})
        self.thresholds = read_json(
            os.path.join(directory, "thresholds.json"), {})
        self.units = {}
        for row in read_table(os.path.join(directory, "units.csv")):
            token = normalise_unit(row.get("unit_token"))
            if token:
                self.units[token] = parse_factor(row.get("factor_nano"))
        self.channels = {}
        self.channel_area = {}
        self.provisional = set()
        for row in read_table(os.path.join(directory, "channel_registry.csv")):
            cid = row.get("channel_id", "")
            if not cid:
                continue
            self.channels[cid] = row
            self.channel_area[cid] = row.get("reporting_area", "")
            if read_bool(row.get("provisional"), False):
                self.provisional.add(cid)
        self.aliases = {}
        self.alias_rows = []
        for row in read_table(os.path.join(directory, "channel_aliases.csv")):
            token = normalise_label(row.get("alias_token"))
            if not token:
                continue
            self.alias_rows.append(row)
            self.aliases[token] = row.get("channel_id", "")
        self.normalised_channels = {}
        for cid in self.channels:
            self.normalised_channels.setdefault(normalise_label(cid), cid)
        self.stations = {}
        for row in read_table(os.path.join(directory, "stations.csv")):
            sid = row.get("station_id", "")
            if sid:
                self.stations[sid] = row
        self.agencies = {}
        for row in read_table(os.path.join(directory, "agencies.csv")):
            aid = row.get("agency_id", "")
            if aid:
                self.agencies[aid] = row
        self.deployments = defaultdict(list)
        for row in read_table(os.path.join(directory, "deployments.csv")):
            self.deployments[row.get("channel_id", "")].append(
                (row.get("deployment_id", ""),
                 Interval(row.get("valid_from"), row.get("valid_to")),
                 row.get("station_id", "")))
        self.station_custody = defaultdict(list)
        self.standing_custodian = {}
        for row in read_table(os.path.join(directory, "custody.csv")):
            held = row.get("array_channel_id", "")
            if held:
                self.standing_custodian[held] = row.get(
                    "custodian_channel_id", "")
                continue
            self.station_custody[row.get("station_id", "")].append(
                (row.get("custody_id", ""),
                 Interval(row.get("effective_from"), row.get("effective_to")),
                 row.get("agency_id", "")))
        self.certificates = {}
        self.channel_certificates = defaultdict(list)
        for row in read_table(os.path.join(directory, "certificates.csv")):
            cert = row.get("certificate_id", "")
            if not cert:
                continue
            entry = {
                "certificate_id": cert,
                "channel_id": row.get("channel_id", ""),
                "interval": Interval(row.get("valid_from"),
                                     row.get("valid_to")),
                "gain_micro": optional_int(row.get("gain_micro")),
                "offset_nano": optional_int(row.get("offset_nano")),
                "drift": optional_int(row.get("drift_nano_per_sample")),
                "standard_id": row.get("standard_id", ""),
            }
            self.certificates[cert] = entry
            self.channel_certificates[entry["channel_id"]].append(entry)
        self.standards = {}
        for row in read_table(os.path.join(directory, "standards.csv")):
            sid = row.get("standard_id", "")
            if sid:
                ratio = optional_int(row.get("ratio_ppm"))
                self.standards[sid] = {
                    "parent": row.get("parent_standard_id", ""),
                    "ratio_ppm": 0 if ratio is None else ratio,
                }
        self.observation_rows = read_table(
            os.path.join(directory, "observations.csv"))
        self.ledger_lines = read_jsonl(
            os.path.join(directory, "amendments.jsonl"))
        self.input_file_count = 0
        if os.path.isdir(directory):
            for entry in os.scandir(directory):
                if entry.is_file():
                    self.input_file_count += 1

    def resolve_label(self, token):
        """Alias rules outrank structural rules (calibration boundary C-09)."""
        key = normalise_label(token)
        if key in self.aliases:
            return self.aliases[key]
        match = STRUCTURAL_RE.match(key)
        if match is not None:
            return "HLS-%04d" % int(match.group(1))
        return self.normalised_channels.get(key, "")

    def pick_deployment(self, channel_id, instant):
        best = None
        for dep_id, interval, station_id in self.deployments.get(
                channel_id, ()):
            if not interval.covers(instant):
                continue
            start = interval.start or ()
            # Later start wins; a tied start uses the lower identifier.
            key = (start, tuple(-ord(ch) for ch in dep_id))
            if best is None or key > best[0]:
                best = (key, station_id)
        return None if best is None else best[1]

    def pick_custody(self, station_id, instant):
        best = None
        for cus_id, interval, agency_id in self.station_custody.get(
                station_id, ()):
            if not interval.covers(instant):
                continue
            start = interval.start or ()
            key = (start, tuple(-ord(ch) for ch in cus_id))
            if best is None or key > best[0]:
                best = (key, agency_id)
        return None if best is None else best[1]

    def pick_certificate(self, channel_id, instant, revoked):
        best = None
        for entry in self.channel_certificates.get(channel_id, ()):
            if entry["certificate_id"] in revoked:
                continue
            if not entry["interval"].covers(instant):
                continue
            start = entry["interval"].start or ()
            # Later start wins; a tied start uses the higher identifier.
            key = (start, entry["certificate_id"])
            if best is None or key > best[0]:
                best = (key, entry)
        return None if best is None else best[1]

    def ladder_ppm(self, standard_id):
        """Sum of ratios toward the parentless primary, primary excluded."""
        total = 0
        seen = set()
        current = standard_id
        while True:
            if current not in self.standards:
                return None
            if current in seen:
                return None
            seen.add(current)
            node = self.standards[current]
            parent = node["parent"]
            if not parent:
                return total
            total += node["ratio_ppm"]
            current = parent


# -------------------------------------------------------------- ledger stage

class Sample(object):
    __slots__ = ("sample_id", "row_index", "channel_token", "epoch_text",
                 "raw_text", "unit_token", "status", "standing_basis",
                 "duplicate", "raw_broken", "epoch_broken", "raw_value")

    def __init__(self, row, index):
        self.sample_id = row.get("sample_id", "")
        self.row_index = index
        self.channel_token = row.get("channel_token", "")
        self.epoch_text = row.get("epoch", "")
        self.raw_text = row.get("raw_count", "")
        self.unit_token = row.get("unit_token", "")
        self.status = (row.get("status", "") or "").strip().lower()
        self.standing_basis = read_bool(row.get("standing_basis"), True)
        self.duplicate = False
        self.raw_broken = not is_whole_number(self.raw_text)
        self.epoch_broken = parse_instant(self.epoch_text) is None
        self.raw_value = (None if self.raw_broken
                          else int(self.raw_text.strip()))


def build_samples(archive):
    samples = []
    first_by_id = {}
    for index, row in enumerate(archive.observation_rows):
        sample = Sample(row, index)
        if sample.sample_id in first_by_id:
            sample.duplicate = True
        else:
            first_by_id[sample.sample_id] = sample
        samples.append(sample)
    return samples, first_by_id


def ledger_order(archive):
    """Well-formed entries in ledger order, plus the malformed line count."""
    well_formed = []
    malformed = 0
    for line_number, obj in archive.ledger_lines:
        if not isinstance(obj, dict):
            malformed += 1
            continue
        entry_id = obj.get("entry_id")
        sequence = obj.get("sequence")
        if not isinstance(entry_id, str) or entry_id == "":
            malformed += 1
            continue
        if not is_json_int(sequence):
            malformed += 1
            continue
        well_formed.append((sequence, entry_id, line_number, obj))
    well_formed.sort(key=lambda item: (
        item[0], tuple(ord(ch) for ch in item[1])))
    return well_formed, malformed


def apply_ledger(archive, samples, first_by_id):
    """Post the ledger; return (revoked_certs, ignored, unmatched)."""
    entries, unmatched = ledger_order(archive)
    ignored = 0
    posted_ids = set()
    revoked = set()

    for _sequence, entry_id, _line, obj in entries:
        # A malformed line claims no entry_id; every other line claims its
        # own on first appearance, so later appearances never act.
        if entry_id in posted_ids:
            ignored += 1
            continue
        posted_ids.add(entry_id)
        outcome = post_entry(archive, obj, obj.get("op"), first_by_id, revoked)
        if outcome == "unmatched":
            unmatched += 1
        elif outcome == "ignored":
            ignored += 1
    return revoked, ignored, unmatched


def post_entry(archive, obj, op, first_by_id, revoked):
    if op in ("revise", "void", "reinstate", "certify"):
        sample = first_by_id.get(obj.get("sample_id"))
        if sample is None:
            return "unmatched"
        return post_sample_op(obj, op, sample)
    if op == "revoke_certificate":
        cert = obj.get("certificate_id")
        if not isinstance(cert, str) or cert not in archive.certificates:
            return "unmatched"
        if cert in revoked:
            return "ignored"
        revoked.add(cert)
        return "posted"
    if op == "restore_certificate":
        cert = obj.get("certificate_id")
        if not isinstance(cert, str) or cert not in archive.certificates:
            return "unmatched"
        if cert not in revoked:
            return "ignored"
        revoked.discard(cert)
        return "posted"
    if op == "revise_standard":
        return post_standard_op(archive, obj)
    return "unmatched"


def post_sample_op(obj, op, sample):
    if op == "void":
        if sample.status == "void":
            return "ignored"
        sample.status = "void"
        return "posted"
    if op == "reinstate":
        if sample.status != "void":
            return "ignored"
        sample.status = "observed"
        return "posted"
    if op == "certify":
        if sample.status != "suspect":
            return "ignored"
        sample.status = "observed"
        return "posted"
    # revise
    if sample.status == "void":
        return "ignored"
    if "channel_token" in obj:
        value = obj["channel_token"]
        if isinstance(value, str):
            sample.channel_token = value
    if "unit_token" in obj:
        value = obj["unit_token"]
        if isinstance(value, str):
            sample.unit_token = value
    if "standing_basis" in obj:
        value = obj["standing_basis"]
        if isinstance(value, bool):
            sample.standing_basis = value
    if "raw_count" in obj:
        value = obj["raw_count"]
        if is_json_int(value):
            sample.raw_value = value
            sample.raw_text = str(value)
            sample.raw_broken = False
        else:
            sample.raw_value = None
            sample.raw_broken = True
    if "epoch" in obj:
        value = obj["epoch"]
        if isinstance(value, str) and parse_instant(value) is not None:
            sample.epoch_text = value
            sample.epoch_broken = False
        else:
            sample.epoch_broken = True
    return "posted"


def post_standard_op(archive, obj):
    standard_id = obj.get("standard_id")
    if (not isinstance(standard_id, str)
            or standard_id not in archive.standards):
        return "unmatched"
    has_parent = "parent_standard_id" in obj
    has_ratio = "ratio_ppm" in obj
    if not has_parent and not has_ratio:
        return "ignored"
    parent = obj.get("parent_standard_id")
    ratio = obj.get("ratio_ppm")
    if has_parent and not isinstance(parent, str):
        return "ignored"
    if has_ratio and not is_json_int(ratio):
        return "ignored"
    node = archive.standards[standard_id]
    if has_parent:
        node["parent"] = parent
    if has_ratio:
        node["ratio_ppm"] = ratio
    return "posted"


# ------------------------------------------------------------ sample staging

class Staged(object):
    __slots__ = ("sample", "reason", "lifecycle", "channel_id", "station_id",
                 "agency_id", "certificate", "ladder", "factor", "instant",
                 "canonical", "traced", "reported", "drift_amount",
                 "drift_position", "sources")

    def __init__(self, sample):
        self.sample = sample
        self.reason = None
        self.lifecycle = None
        self.channel_id = ""
        self.station_id = ""
        self.agency_id = ""
        self.certificate = None
        self.ladder = None
        self.factor = None
        self.instant = None
        self.canonical = 0
        self.traced = 0
        self.reported = 0
        self.drift_amount = 0
        self.drift_position = 0
        self.sources = {}


def stage_samples(archive, samples, revoked):
    """Classify every observation under the non-standing rules."""
    staged = []
    for sample in samples:
        item = Staged(sample)
        staged.append(item)

        if sample.duplicate:
            item.lifecycle = "quarantined"
            item.reason = "duplicate_sample"
            continue
        if sample.status == "void":
            item.lifecycle = "voided"
            continue
        if sample.status == "suspect":
            item.lifecycle = "quarantined"
            item.reason = "unresolved_suspect"
            continue
        if sample.raw_broken or sample.epoch_broken:
            item.lifecycle = "quarantined"
            item.reason = "malformed_sample"
            continue

        item.instant = parse_instant(sample.epoch_text)
        channel_id = archive.resolve_label(sample.channel_token)
        conditions = set()
        if channel_id not in archive.channels:
            conditions.add("unknown_channel")
        else:
            item.channel_id = channel_id

        factor = archive.units.get(normalise_unit(sample.unit_token))
        if factor is None:
            conditions.add("unknown_unit")
        else:
            item.factor = factor

        if item.channel_id:
            station_id = archive.pick_deployment(item.channel_id, item.instant)
            if not station_id or station_id not in archive.stations:
                conditions.add("no_deployment")
            else:
                item.station_id = station_id
                agency_id = archive.pick_custody(station_id, item.instant)
                if not agency_id or agency_id not in archive.agencies:
                    conditions.add("no_custody")
                else:
                    item.agency_id = agency_id
            certificate = archive.pick_certificate(
                item.channel_id, item.instant, revoked)
            if certificate is None:
                conditions.add("no_certificate")
            else:
                item.certificate = certificate
                ladder = archive.ladder_ppm(certificate["standard_id"])
                if ladder is None:
                    conditions.add("broken_ladder")
                else:
                    item.ladder = ladder

        for reason in QUARANTINE_ORDER:
            if reason in conditions:
                item.lifecycle = "quarantined"
                item.reason = reason
                break
        else:
            item.lifecycle = "survivor"
    return staged


def pick_parameter(archive, item, cert_key, station_key, policy_key):
    """Ordinary channels read certificate, station, network in that order;
    provisional channels exchange the first two sources."""
    certificate = item.certificate
    cert_value = None if certificate is None else certificate[cert_key]
    station = archive.stations.get(item.station_id, {})
    station_value = optional_int(station.get(station_key))
    policy_value = archive.policy.get(policy_key)
    chain = [("certificate", cert_value), ("station", station_value)]
    if item.channel_id in archive.provisional:
        chain.reverse()
    chain.append(("network", policy_value))
    for source, value in chain:
        if value is not None:
            return source, value
    return "network", 0


def value_samples(archive, staged):
    """Assign drift positions and compute figures for every survivor."""
    survivors = [item for item in staged if item.lifecycle == "survivor"]
    runs = defaultdict(list)
    for item in survivors:
        runs[(item.channel_id, item.certificate["certificate_id"])].append(
            item)
    for key in runs:
        ordered = sorted(
            runs[key],
            key=lambda it: (it.instant,
                            tuple(ord(ch) for ch in it.sample.sample_id)))
        for position, item in enumerate(ordered):
            item.drift_position = position

    floor = archive.policy.get("minimum_reported_nano", 0)
    for item in survivors:
        gain_source, gain = pick_parameter(
            archive, item, "gain_micro", "station_gain_micro",
            "network_gain_micro")
        offset_source, offset = pick_parameter(
            archive, item, "offset_nano", "station_offset_nano",
            "network_offset_nano")
        drift_source, drift_rate = pick_parameter(
            archive, item, "drift", "station_drift_nano_per_sample",
            "network_drift_nano_per_sample")
        item.sources = {"gain": gain_source, "offset": offset_source,
                        "drift": drift_source}
        num, den = item.factor
        item.canonical = round_ratio(item.sample.raw_value * num, den)
        gained = round_ratio(item.canonical * gain, NANO)
        item.traced = round_ratio(gained * (PPM + item.ladder), PPM)
        item.drift_amount = item.drift_position * drift_rate
        reported = item.traced - item.drift_amount + offset
        item.reported = reported if reported >= floor else floor
    return survivors


# ------------------------------------------------------------------ standing

def reporting_floor(thresholds, reporting_count):
    best = None
    for band in thresholds.get("reporting_floor_bands", ()):
        at_least = band.get("reporting_arrays_at_least")
        if at_least is None or at_least > reporting_count:
            continue
        if best is None or at_least > best[0]:
            best = (at_least, band.get("minimum_qualifying_observations"))
    if best is None or best[1] is None:
        return None
    return best[1]


def earn_standing(archive, survivors):
    """Least set of reporting channels consistent with the standing facts."""
    qualifying = {cid: 0 for cid in archive.channels}
    for item in survivors:
        if item.sample.standing_basis:
            qualifying[item.channel_id] = qualifying.get(
                item.channel_id, 0) + 1

    secondary = archive.thresholds.get("custody_secondary_band")
    reporting = set()
    rounds = {}
    round_number = 0
    while True:
        round_number += 1
        area_counts = defaultdict(int)
        for cid in reporting:
            area_counts[archive.channel_area.get(cid, "")] += 1
        added = []
        for cid in sorted(archive.channels):
            if cid in reporting:
                continue
            count = qualifying.get(cid, 0)
            floor = reporting_floor(
                archive.thresholds,
                area_counts[archive.channel_area.get(cid, "")])
            if floor is not None and count >= floor:
                added.append(cid)
                continue
            custodian = archive.standing_custodian.get(cid)
            if (custodian in reporting and secondary is not None
                    and count >= secondary):
                added.append(cid)
        if not added:
            break
        for cid in added:
            reporting.add(cid)
            rounds[cid] = round_number

    area_counts = {}
    for cid, area in archive.channel_area.items():
        area_counts.setdefault(area, 0)
        if cid in reporting:
            area_counts[area] += 1
    return qualifying, reporting, rounds, area_counts


# ----------------------------------------------------------------- allocation

def apportion(budget, weights, names):
    """Largest remainders; equal remainders break on ascending bucket name."""
    shares = {name: 0 for name in names}
    total = sum(weights.get(name, 0) for name in names)
    if total <= 0 or budget == 0:
        return shares
    remainders = []
    assigned = 0
    for name in names:
        weight = weights.get(name, 0)
        product = budget * weight
        base = product // total
        shares[name] = base
        assigned += base
        remainders.append((product - base * total, name))
    left = budget - assigned
    remainders.sort(key=lambda item: (-item[0],
                                      tuple(ord(ch) for ch in item[1])))
    for index in range(left):
        shares[remainders[index][1]] += 1
    return shares


# -------------------------------------------------------------------- bucket

class Bucket(object):
    def __init__(self, name):
        self.name = name
        self.accepted = 0
        self.canonical = 0
        self.traced = 0
        self.reported = 0
        self.drift = 0
        self.channel_totals = defaultdict(int)
        self.station_totals = defaultdict(int)
        self.agency_totals = defaultdict(int)
        self.area_counts = defaultdict(int)
        self.class_counts = defaultdict(int)

    def add(self, item, area, operator_class):
        self.accepted += 1
        self.canonical += item.canonical
        self.traced += item.traced
        self.reported += item.reported
        self.drift += item.drift_amount
        self.channel_totals[item.channel_id] += item.reported
        self.station_totals[item.station_id] += item.reported
        self.agency_totals[item.agency_id] += item.reported
        self.area_counts[area] += 1
        self.class_counts[operator_class] += 1


def sorted_map(mapping):
    return {key: mapping[key]
            for key in sorted(mapping, key=lambda k: tuple(ord(c) for c in k))}


def alert_for(name, bucket, gate):
    if gate is None:
        return []
    delta = bucket.reported - bucket.canonical
    if abs(delta) >= gate:
        return [{"name": name, "delta_nano": delta}]
    return []


# -------------------------------------------------------------------- derive

def derive(archive):
    samples, first_by_id = build_samples(archive)
    revoked, ignored, unmatched = apply_ledger(archive, samples, first_by_id)
    staged = stage_samples(archive, samples, revoked)
    survivors = value_samples(archive, staged)
    qualifying, reporting, rounds, area_reporting = earn_standing(
        archive, survivors)

    accepted = []
    for item in survivors:
        if item.sample.standing_basis or item.channel_id in reporting:
            item.lifecycle = "accepted"
            accepted.append(item)
        else:
            item.lifecycle = "quarantined"
            item.reason = "unreported_array"

    observed_count = len(staged)
    voided_count = sum(1 for it in staged if it.lifecycle == "voided")
    quarantined = [it for it in staged if it.lifecycle == "quarantined"]
    reasons = defaultdict(int)
    for item in quarantined:
        reasons[item.reason] += 1

    roster_areas = list(archive.thresholds.get("reported_arrays", ()))
    roster_classes = list(archive.thresholds.get("reported_segments", ()))

    network = Bucket("network")
    area_buckets = {}
    class_buckets = {}
    for item in accepted:
        area = archive.stations.get(item.station_id, {}).get("array_name", "")
        operator_class = archive.agencies.get(
            item.agency_id, {}).get("operator_class", "")
        network.add(item, area, operator_class)
        area_buckets.setdefault(area, Bucket(area)).add(
            item, area, operator_class)
        class_buckets.setdefault(operator_class, Bucket(operator_class)).add(
            item, area, operator_class)

    area_weights = {name: (area_buckets[name].accepted
                           if name in area_buckets else 0)
                    for name in roster_areas}
    class_weights = {name: (class_buckets[name].accepted
                            if name in class_buckets else 0)
                     for name in roster_classes}
    budget = archive.policy.get("uncertainty_budget_nano", 0)
    area_allocation = apportion(budget, area_weights, roster_areas)
    class_allocation = apportion(budget, class_weights, roster_classes)

    gate = archive.thresholds.get("variance_alert_nano")
    area_reports = {}
    area_alerts = []
    for name in roster_areas:
        bucket = area_buckets.get(name) or Bucket(name)
        alerts = alert_for(name, bucket, gate)
        area_alerts.extend(alerts)
        area_reports[name] = {
            "name": name,
            "accepted_count": bucket.accepted,
            "canonical_nano": bucket.canonical,
            "traced_nano": bucket.traced,
            "reported_nano": bucket.reported,
            "drift_nano": bucket.drift,
            "channel_totals": sorted_map(bucket.channel_totals),
            "station_totals": sorted_map(bucket.station_totals),
            "segment_counts": sorted_map(bucket.class_counts),
            "allocation_nano": area_allocation[name],
            "alerts": alerts,
        }
    area_alerts.sort(key=lambda a: tuple(ord(c) for c in a["name"]))

    class_reports = {}
    for name in roster_classes:
        bucket = class_buckets.get(name) or Bucket(name)
        class_reports[name] = {
            "name": name,
            "accepted_count": bucket.accepted,
            "canonical_nano": bucket.canonical,
            "traced_nano": bucket.traced,
            "reported_nano": bucket.reported,
            "drift_nano": bucket.drift,
            "channel_totals": sorted_map(bucket.channel_totals),
            "agency_totals": sorted_map(bucket.agency_totals),
            "array_counts": sorted_map(bucket.area_counts),
            "allocation_nano": class_allocation[name],
            "alerts": alert_for(name, bucket, gate),
        }

    largest = {"reported_nano": 0, "sample_id": None}
    best_key = None
    for item in accepted:
        key = (-item.reported, tuple(ord(c) for c in item.sample.sample_id))
        if best_key is None or key < best_key:
            best_key = key
            largest = {"reported_nano": item.reported,
                       "sample_id": item.sample.sample_id}

    summary = {
        "report_id": archive.policy.get("report_id"),
        "observed_count": observed_count,
        "accepted_count": network.accepted,
        "quarantined_count": len(quarantined),
        "voided_count": voided_count,
        "canonical_nano": network.canonical,
        "traced_nano": network.traced,
        "reported_nano": network.reported,
        "drift_nano": network.drift,
        "budget_nano": budget,
        "array_counts": sorted_map(network.area_counts),
        "array_totals": sorted_map(
            {name: bucket.reported for name, bucket in area_buckets.items()}),
        "segment_counts": sorted_map(network.class_counts),
        "channel_totals": sorted_map(network.channel_totals),
        "station_totals": sorted_map(network.station_totals),
        "array_allocation_nano": sorted_map(area_allocation),
        "segment_allocation_nano": sorted_map(class_allocation),
        "largest_sample": largest,
        "alerts": area_alerts,
    }

    applied = sorted({it.certificate["certificate_id"] for it in accepted},
                     key=lambda k: tuple(ord(c) for c in k))
    exclusions = defaultdict(int)
    for item in quarantined:
        if item.reason == "unreported_array":
            exclusions[item.certificate["certificate_id"]] += 1
    sources = {kind: {"certificate": 0, "station": 0, "network": 0}
               for kind in ("gain", "offset", "drift")}
    for item in accepted:
        for kind, source in item.sources.items():
            sources[kind][source] += 1
    unused = sorted(
        set(archive.certificates) - set(applied) - revoked,
        key=lambda k: tuple(ord(c) for c in k))
    policy_audit = {
        "report_id": archive.policy.get("report_id"),
        "budget_nano": budget,
        "minimum_reported_nano": archive.policy.get("minimum_reported_nano"),
        "variance_alert_nano": gate,
        "certificates_applied": applied,
        "certificates_revoked": sorted(
            revoked, key=lambda k: tuple(ord(c) for c in k)),
        "certificates_unused": unused,
        "ladder_ppm_by_certificate": sorted_map(
            {cert: archive.ladder_ppm(
                archive.certificates[cert]["standard_id"])
             for cert in applied}),
        "parameter_sources": {kind: dict(sorted(value.items()))
                              for kind, value in sources.items()},
        "provisional_channels": sorted(
            archive.provisional, key=lambda k: tuple(ord(c) for c in k)),
        "qualifying_observations_by_array": sorted_map(qualifying),
        "reporting_arrays": sorted(
            reporting, key=lambda k: tuple(ord(c) for c in k)),
        "unreported_arrays": sorted(
            set(archive.channels) - reporting,
            key=lambda k: tuple(ord(c) for c in k)),
        "reporting_round_by_array": sorted_map(rounds),
        "reporting_array_count_by_area": sorted_map(area_reporting),
        "standing_exclusions_by_certificate": sorted_map(exclusions),
    }

    unrostered = defaultdict(int)
    for name, bucket in area_buckets.items():
        if name not in roster_areas:
            unrostered[name] += bucket.accepted
    ratio = (0 if observed_count == 0
             else round_ratio(len(quarantined) * PPM, observed_count))
    ratio_gate = archive.thresholds.get("quarantine_alert_ratio_ppm")
    orphans = sorted(
        {row.get("alias_token", "") for row in archive.alias_rows
         if row.get("channel_id", "") not in archive.channels},
        key=lambda k: tuple(ord(c) for c in k))
    data_quality = {
        "observed_count": observed_count,
        "accepted_count": network.accepted,
        "quarantined_count": len(quarantined),
        "voided_count": voided_count,
        "conservation_ok": (observed_count ==
                            network.accepted + len(quarantined)
                            + voided_count),
        "quarantine_reasons": sorted_map(reasons),
        "ignored_amendments": ignored,
        "unmatched_amendments": unmatched,
        "orphan_alias_tokens": orphans,
        "unreported_array_counts": sorted_map(unrostered),
        "quarantine_ratio_ppm": ratio,
        "quarantine_alert": (ratio_gate is not None and ratio >= ratio_gate),
        "input_file_count": archive.input_file_count,
    }

    reports = {
        "summary.json": summary,
        "policy_audit.json": policy_audit,
        "data_quality.json": data_quality,
    }
    for name in roster_areas:
        reports["region_%s.json" % name] = area_reports[name]
    for name in roster_classes:
        reports["segment_%s.json" % name] = class_reports[name]
    return reports, roster_areas, roster_classes


# ------------------------------------------------------------------ emission

def write_reports(outdir, reports):
    os.makedirs(outdir, exist_ok=True)
    for name in sorted(reports):
        path = os.path.join(outdir, name)
        if os.path.exists(path):
            os.remove(path)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(reports[name], indent=2, sort_keys=True))
            handle.write("\n")


# -------------------------------------------------------------- verification

def check(condition, message):
    if not condition:
        raise Fault(message)


def reconcile(outdir, roster_areas, roster_classes):
    """Re-read the written reports and check that they agree."""
    loaded = {}
    names = (list(REPORT_FILES)
             + ["region_%s.json" % name for name in roster_areas]
             + ["segment_%s.json" % name for name in roster_classes])
    for name in names:
        path = os.path.join(outdir, name)
        check(os.path.isfile(path), "missing report %s" % name)
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
        check(text.endswith("\n"), "report %s lacks terminal newline" % name)
        loaded[name] = json.loads(text)

    summary = loaded["summary.json"]
    audit = loaded["policy_audit.json"]
    quality = loaded["data_quality.json"]

    check(summary["observed_count"] == summary["accepted_count"]
          + summary["quarantined_count"] + summary["voided_count"],
          "lifecycle counts do not conserve")
    check(quality["conservation_ok"] is True, "conservation flag is false")
    for key in ("observed_count", "accepted_count", "quarantined_count",
                "voided_count"):
        check(summary[key] == quality[key],
              "summary and data quality disagree on %s" % key)
    check(sum(quality["quarantine_reasons"].values())
          == quality["quarantined_count"],
          "quarantine reasons do not sum to the quarantined count")
    check(sum(summary["array_counts"].values()) == summary["accepted_count"],
          "area counts do not sum to the accepted count")
    check(sum(summary["channel_totals"].values()) == summary["reported_nano"],
          "channel totals do not sum to the reported total")
    check(sum(summary["station_totals"].values()) == summary["reported_nano"],
          "station totals do not sum to the reported total")
    check(sum(summary["array_totals"].values()) == summary["reported_nano"],
          "area totals do not sum to the reported total")
    check(sum(summary["segment_counts"].values()) <= summary["accepted_count"],
          "class counts exceed the accepted count")

    budget = summary["budget_nano"]
    check(audit["budget_nano"] == budget, "budget disagrees with the audit")
    for allocation, weights in (
            (summary["array_allocation_nano"], summary["array_counts"]),
            (summary["segment_allocation_nano"], summary["segment_counts"])):
        population = sum(weights.get(name, 0) for name in allocation)
        total = sum(allocation.values())
        check(total == (budget if population > 0 else 0),
              "apportionment does not sum to the budget")

    area_alerts = []
    accepted_sum = 0
    for name in roster_areas:
        report = loaded["region_%s.json" % name]
        check(report["name"] == name, "area report carries the wrong name")
        check(sum(report["channel_totals"].values())
              == report["reported_nano"],
              "area channel totals do not reconcile")
        check(sum(report["station_totals"].values())
              == report["reported_nano"],
              "area station totals do not reconcile")
        check(sum(report["segment_counts"].values())
              == report["accepted_count"],
              "area class counts do not reconcile")
        check(report["accepted_count"]
              == summary["array_counts"].get(name, 0),
              "area accepted count disagrees with the summary")
        check(report["reported_nano"] == summary["array_totals"].get(name, 0),
              "area reported total disagrees with the summary")
        check(report["allocation_nano"]
              == summary["array_allocation_nano"][name],
              "area allocation disagrees with the summary")
        accepted_sum += report["accepted_count"]
        area_alerts.extend(report["alerts"])
    unrostered = sum(quality["unreported_array_counts"].values())
    check(accepted_sum + unrostered == summary["accepted_count"],
          "area partition does not account for every accepted sample")
    check(area_alerts == summary["alerts"],
          "network alert list disagrees with the area reports")

    class_accepted = 0
    for name in roster_classes:
        report = loaded["segment_%s.json" % name]
        check(report["name"] == name, "class report carries the wrong name")
        check(sum(report["channel_totals"].values())
              == report["reported_nano"],
              "class channel totals do not reconcile")
        check(sum(report["agency_totals"].values())
              == report["reported_nano"],
              "class agency totals do not reconcile")
        check(sum(report["array_counts"].values())
              == report["accepted_count"],
              "class area counts do not reconcile")
        check(report["accepted_count"]
              == summary["segment_counts"].get(name, 0),
              "class accepted count disagrees with the summary")
        check(report["allocation_nano"]
              == summary["segment_allocation_nano"][name],
              "class allocation disagrees with the summary")
        class_accepted += report["accepted_count"]
    check(class_accepted <= summary["accepted_count"],
          "class partition exceeds the accepted total")

    channels = set(audit["reporting_arrays"]) | set(audit["unreported_arrays"])
    check(not (set(audit["reporting_arrays"])
               & set(audit["unreported_arrays"])),
          "a channel is both reporting and non reporting")
    check(set(audit["qualifying_observations_by_array"]) == channels,
          "qualifying counts do not cover every channel")
    check(set(audit["reporting_round_by_array"])
          == set(audit["reporting_arrays"]),
          "reporting rounds do not cover the reporting set")
    check(sum(audit["reporting_array_count_by_area"].values())
          == len(audit["reporting_arrays"]),
          "area reporting counts do not sum to the reporting set")
    check(set(audit["ladder_ppm_by_certificate"])
          == set(audit["certificates_applied"]),
          "ladder values do not cover the applied certificates")
    check(not (set(audit["certificates_applied"])
               & set(audit["certificates_revoked"])),
          "a revoked certificate was applied")
    for kind, counts in audit["parameter_sources"].items():
        check(sum(counts.values()) == summary["accepted_count"],
              "%s parameter sources do not cover every accepted sample" % kind)
    check(set(summary["channel_totals"]) <= channels,
          "an accepted sample names an unregistered channel")

    if summary["accepted_count"] == 0:
        check(summary["largest_sample"] == {"reported_nano": 0,
                                           "sample_id": None},
              "an empty network must carry a null largest sample")
        check(quality["quarantine_ratio_ppm"] == 0
              or summary["observed_count"] > 0,
              "an empty archive must carry a zero quarantine ratio")
    else:
        check(summary["largest_sample"]["sample_id"] is not None,
              "a nonempty network must name a largest sample")


def main(argv):
    if len(argv) != 3:
        sys.stderr.write(
            "usage: %s <archive_dir> <output_dir>\n"
            % os.path.basename(argv[0] or "derive_report.py"))
        return 2
    archive_dir, outdir = argv[1], argv[2]
    if not os.path.isdir(archive_dir):
        sys.stderr.write("archive directory not found: %s\n" % archive_dir)
        return 2
    archive = Archive(archive_dir)
    reports, roster_areas, roster_classes = derive(archive)
    write_reports(outdir, reports)
    try:
        reconcile(outdir, roster_areas, roster_classes)
    except Fault as fault:
        sys.stderr.write("reconciliation failed: %s\n" % fault)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
