#!/usr/bin/env python3
"""Derive the gravimeter array report set from an archive directory.

Usage:
    python3 derive_report.py <archive_dir> <output_dir>

The archive directory holds the material described by the derivation
contract: comma-separated tables in the usual quoted dialect, a JSON
network policy and reporting-threshold table, a JSON-lines amendment
ledger and the observations.  The transform is deterministic, uses exact
integer arithmetic only, and rebuilds the complete report set, replacing
in full any report an earlier run left in the output location.  After
writing, the reports are re-read and reconciled with one another; the
program exits nonzero when they disagree.
"""

import csv
import json
import os
import re
import sys
from collections import defaultdict

POLICY_FILE = "policy.json"
THRESHOLDS_FILE = "thresholds.json"
UNITS_FILE = "units.csv"
REGISTRY_FILE = "channel_registry.csv"
ALIASES_FILE = "channel_aliases.csv"
STATIONS_FILE = "stations.csv"
AGENCIES_FILE = "agencies.csv"
CUSTODY_FILE = "custody.csv"
DEPLOYMENTS_FILE = "deployments.csv"
CERTIFICATES_FILE = "certificates.csv"
STANDARDS_FILE = "standards.csv"
OBSERVATIONS_FILE = "observations.csv"
AMENDMENTS_FILE = "amendments.jsonl"

MAIN_REPORTS = ("summary.json", "policy_audit.json", "data_quality.json")
AREA_REPORT_FMT = "region_{}.json"
CLASS_REPORT_FMT = "segment_{}.json"
STALE_AREA_RE = re.compile(r"\Aregion_.+\.json\Z")
STALE_CLASS_RE = re.compile(r"\Asegment_.+\.json\Z")

# An epoch is a year, month and day joined by "-", then "T" or a single
# space, then hours, minutes and seconds joined by ":", every component
# being one or more ASCII digits, so leading zeros are optional.
INSTANT_RE = re.compile(r"([0-9]+)-([0-9]+)-([0-9]+)[T ]([0-9]+):([0-9]+):([0-9]+)\Z")
WHOLE_RE = re.compile(r"[+-]?[0-9]+\Z")
DIGITS_RE = re.compile(r"[0-9]+\Z")
SIGNED_RE = re.compile(r"[+-]?[0-9]+\Z")
STRUCTURAL_RE = re.compile(r"\AHLS([0-9]+)\Z")

# The order in which an observed sample's quarantine outcomes apply.  A
# duplicate row is held before every other rule; lifecycle state precedes
# malformation; malformation precedes every outcome in this list.  The
# calibration control fixes this composition, not the order the
# contract's bullet list happens to use.
REASON_ORDER = (
    "unknown_channel",
    "no_deployment",
    "no_custody",
    "no_certificate",
    "unknown_unit",
    "broken_ladder",
    "unreported_array",
)
KNOWN_REASONS = set(REASON_ORDER) | {
    "duplicate_sample",
    "malformed_sample",
    "unresolved_suspect",
    "voided",
}
REVISE_FIELDS = ("channel_token", "epoch", "raw_count", "unit_token", "standing_basis")
PARAMETERS = ("gain", "offset", "drift")
PARAMETER_KEYS = {
    "certificate": {
        "gain": "gain_micro",
        "offset": "offset_nano",
        "drift": "drift_nano_per_sample",
    },
    "station": {"gain": "gain", "offset": "offset", "drift": "drift"},
    "network": {
        "gain": "network_gain_micro",
        "offset": "network_offset_nano",
        "drift": "network_drift_nano_per_sample",
    },
}
SOURCE_ORDER = ("certificate", "station", "network")
AGGREGATE_FIELDS = (
    "accepted_count",
    "canonical_nano",
    "traced_nano",
    "drift_nano",
    "reported_nano",
)


# ---------------------------------------------------------------- primitives


def round_half_away(num, den):
    """Round num/den to an integer, exact halves away from zero (den > 0)."""
    if num >= 0:
        quot, rem = divmod(num, den)
        if 2 * rem >= den:
            quot += 1
        return quot
    return -round_half_away(-num, den)


def parse_instant(value):
    """Read an ISO-8601 local instant; return a comparable tuple or None."""
    if not isinstance(value, str):
        return None
    match = INSTANT_RE.match(value.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def as_int(value):
    """Read an integer parameter from a table cell or a JSON object."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and SIGNED_RE.match(value.strip()):
        return int(value.strip())
    return None


def whole_number(value):
    """Return (is_whole, integer_value) for an observation raw count."""
    if isinstance(value, bool):
        return False, None
    if isinstance(value, int):
        return True, value
    if isinstance(value, str) and WHOLE_RE.match(value.strip()):
        return True, int(value.strip())
    return False, None


def parse_flag(value, blank):
    """Read a true/false flag in any letter case; a blank takes the default."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text == "":
            return blank
        return text == "true"
    return False


def normalize_label(value):
    """Upper-case a label and strip it to letters and digits."""
    if not isinstance(value, str):
        return ""
    return "".join(ch for ch in value.upper() if ch.isalnum())


def normalize_unit(value):
    """Lower-case a unit token and strip it to letters and digits."""
    if not isinstance(value, str):
        return ""
    return "".join(ch for ch in value.lower() if ch.isalnum())


def parse_factor(value):
    """Read a unit factor as a (numerator, denominator) pair, or None."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if "/" in text:
        head, _, tail = text.partition("/")
        head, tail = head.strip(), tail.strip()
        if DIGITS_RE.match(head) and DIGITS_RE.match(tail):
            num, den = int(head), int(tail)
            if num > 0 and den > 0:
                return (num, den)
        return None
    if DIGITS_RE.match(text):
        num = int(text)
        if num > 0:
            return (num, 1)
    return None


def read_table(path):
    """Read a comma-separated table in the usual quoted dialect."""
    if not os.path.isfile(path):
        return []
    rows = []
    with open(path, "r", encoding="utf-8", newline="") as handle:
        for row in csv.reader(handle):
            cells = [(cell or "").strip() for cell in row]
            if not any(cells):
                continue
            rows.append(cells)
    if not rows:
        return []
    header = rows[0]
    records = []
    for cells in rows[1:]:
        record = {}
        for index, name in enumerate(header):
            if name != "" and name not in record:
                record[name] = cells[index] if index < len(cells) else ""
        records.append(record)
    return records


def read_json(path, default):
    if not os.path.isfile(path):
        return default
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def read_lines(path):
    if not os.path.isfile(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().splitlines()


def unique_names(names):
    """Ordered, trimmed, de-duplicated roster of bucket names."""
    out = []
    for name in names:
        if not isinstance(name, str):
            continue
        name = name.strip()
        if name != "" and name not in out:
            out.append(name)
    return sorted(out)


def apportion(budget, names, weights):
    """Largest-remainder apportionment of a budget over named buckets."""
    if budget < 0:
        shares = apportion(-budget, names, weights)
        return dict((name, -shares[name]) for name in names)
    total = sum(weights.get(name, 0) for name in names)
    if total <= 0 or budget == 0:
        return dict((name, 0) for name in names)
    bases = {}
    remainders = []
    for name in names:
        base, rem = divmod(budget * weights.get(name, 0), total)
        bases[name] = base
        remainders.append((rem, name))
    leftover = budget - sum(bases.values())
    remainders.sort(key=lambda item: (-item[0], item[1]))
    for index in range(leftover):
        bases[remainders[index % len(remainders)][1]] += 1
    return bases


def count_by(rows, key):
    out = defaultdict(int)
    for row in rows:
        out[key(row)] += 1
    return out


def total_by(rows, key, value):
    out = defaultdict(int)
    for row in rows:
        out[key(row)] += value(row)
    return out


def ordered(mapping):
    """A mapping with its keys in identifier order."""
    return dict(sorted(mapping.items()))


# ------------------------------------------------------------------- archive


class Archive(object):
    """The archive material, parsed once."""

    def __init__(self, root):
        self.root = root
        self.policy = read_json(os.path.join(root, POLICY_FILE), {})
        self.thresholds = read_json(os.path.join(root, THRESHOLDS_FILE), {})
        self.units = self._units(os.path.join(root, UNITS_FILE))
        self.channels = self._channels(os.path.join(root, REGISTRY_FILE))
        self.aliases = self._aliases(os.path.join(root, ALIASES_FILE))
        self.alias_cells = self._alias_cells(os.path.join(root, ALIASES_FILE))
        self.stations = self._stations(os.path.join(root, STATIONS_FILE))
        self.agencies = self._agencies(os.path.join(root, AGENCIES_FILE))
        self.custody, self.standing_custody = self._custody(
            os.path.join(root, CUSTODY_FILE)
        )
        self.deployments = self._deployments(os.path.join(root, DEPLOYMENTS_FILE))
        self.certificates = self._certificates(os.path.join(root, CERTIFICATES_FILE))
        self.standards = self._standards(os.path.join(root, STANDARDS_FILE))
        self.observations = self._observations(os.path.join(root, OBSERVATIONS_FILE))
        self.amendment_lines = read_lines(os.path.join(root, AMENDMENTS_FILE))
        self.input_file_count = self._file_count(root)

    @staticmethod
    def _file_count(root):
        if not os.path.isdir(root):
            return 0
        return sum(
            1 for name in os.listdir(root) if os.path.isfile(os.path.join(root, name))
        )

    def _units(self, path):
        units = {}
        for record in read_table(path):
            token = normalize_unit(record.get("unit_token", ""))
            if token == "" or token in units:
                continue
            units[token] = parse_factor(record.get("factor_nano", ""))
        return units

    def _channels(self, path):
        channels = {}
        for record in read_table(path):
            channel_id = record.get("channel_id", "")
            if channel_id == "" or channel_id in channels:
                continue
            channels[channel_id] = {
                "provisional": parse_flag(record.get("provisional", ""), False),
                "area": record.get("reporting_area", ""),
            }
        return channels

    def _aliases(self, path):
        aliases = {}
        for record in read_table(path):
            token = normalize_label(record.get("alias_token", ""))
            if token == "" or token in aliases:
                continue
            aliases[token] = record.get("channel_id", "")
        return aliases

    @staticmethod
    def _alias_cells(path):
        cells = []
        for record in read_table(path):
            token = record.get("alias_token", "").strip()
            if token != "":
                cells.append((token, record.get("channel_id", "").strip()))
        return cells

    def _stations(self, path):
        stations = {}
        for record in read_table(path):
            station_id = record.get("station_id", "")
            if station_id == "" or station_id in stations:
                continue
            stations[station_id] = {
                "array_name": record.get("array_name", ""),
                "gain": as_int(record.get("station_gain_micro", "")),
                "offset": as_int(record.get("station_offset_nano", "")),
                "drift": as_int(record.get("station_drift_nano_per_sample", "")),
            }
        return stations

    def _agencies(self, path):
        agencies = {}
        for record in read_table(path):
            agency_id = record.get("agency_id", "")
            if agency_id == "" or agency_id in agencies:
                continue
            agencies[agency_id] = record.get("operator_class", "")
        return agencies

    def _custody(self, path):
        rows = []
        standing = {}
        for record in read_table(path):
            held = record.get("array_channel_id", "")
            if held != "":
                if held not in standing:
                    standing[held] = record.get("custodian_channel_id", "")
                continue
            rows.append(
                {
                    "id": record.get("custody_id", ""),
                    "station_id": record.get("station_id", ""),
                    "agency_id": record.get("agency_id", ""),
                    "from": parse_instant(record.get("effective_from", "")),
                    "to": parse_instant(record.get("effective_to", "")),
                }
            )
        return rows, standing

    def _deployments(self, path):
        rows = []
        for record in read_table(path):
            rows.append(
                {
                    "id": record.get("deployment_id", ""),
                    "channel_id": record.get("channel_id", ""),
                    "station_id": record.get("station_id", ""),
                    "from": parse_instant(record.get("valid_from", "")),
                    "to": parse_instant(record.get("valid_to", "")),
                }
            )
        return rows

    def _certificates(self, path):
        certificates = {}
        for record in read_table(path):
            cert_id = record.get("certificate_id", "")
            if cert_id == "" or cert_id in certificates:
                continue
            certificates[cert_id] = {
                "id": cert_id,
                "channel_id": record.get("channel_id", ""),
                "from": parse_instant(record.get("valid_from", "")),
                "to": parse_instant(record.get("valid_to", "")),
                "gain_micro": as_int(record.get("gain_micro", "")),
                "offset_nano": as_int(record.get("offset_nano", "")),
                "drift_nano_per_sample": as_int(record.get("drift_nano_per_sample", "")),
                "standard_id": record.get("standard_id", ""),
            }
        return certificates

    def _standards(self, path):
        standards = {}
        for record in read_table(path):
            standard_id = record.get("standard_id", "")
            if standard_id == "" or standard_id in standards:
                continue
            ratio = as_int(record.get("ratio_ppm", ""))
            standards[standard_id] = {
                "parent": record.get("parent_standard_id", ""),
                "ratio": 0 if ratio is None else ratio,
            }
        return standards

    def _observations(self, path):
        rows = []
        for record in read_table(path):
            rows.append(
                {
                    "sample_id": record.get("sample_id", ""),
                    "channel_token": record.get("channel_token", ""),
                    "epoch": record.get("epoch", ""),
                    "raw_count": record.get("raw_count", ""),
                    "unit_token": record.get("unit_token", ""),
                    "status": record.get("status", "").strip().lower(),
                    "standing_basis": parse_flag(record.get("standing_basis", ""), True),
                }
            )
        return rows

    # -- resolution helpers ---------------------------------------------

    def resolve_channel(self, token):
        """Resolve an observation label to an owned channel, or None."""
        label = normalize_label(token)
        if label == "":
            return None
        named = self.aliases.get(label)
        if named is not None:
            return named if named in self.channels else None
        match = STRUCTURAL_RE.match(label)
        if match is not None:
            channel_id = "HLS-" + match.group(1).zfill(4)
            if channel_id in self.channels:
                return channel_id
        for channel_id in self.channels:
            if normalize_label(channel_id) == label:
                return channel_id
        return None

    def unit_factor(self, token):
        return self.units.get(normalize_unit(token))

    def covering(self, rows, key, value, instant):
        """Latest-start covering row; ties on the lower row identifier."""
        best = None
        for row in rows:
            if row[key] != value:
                continue
            start = row["from"]
            if start is None or start > instant:
                continue
            end = row["to"]
            if end is not None and end < instant:
                continue
            if best is None or start > best["from"] or (
                start == best["from"] and row["id"] < best["id"]
            ):
                best = row
        return best

    def select_certificate(self, channel_id, instant, revoked):
        """Effective unrevoked certificate; later start, ties on the higher id."""
        best = None
        for cert_id in sorted(self.certificates):
            cert = self.certificates[cert_id]
            if cert["channel_id"] != channel_id or cert_id in revoked:
                continue
            start = cert["from"]
            if start is None or start > instant:
                continue
            end = cert["to"]
            if end is not None and end < instant:
                continue
            if best is None or start > best["from"] or (
                start == best["from"] and cert_id > best["id"]
            ):
                best = cert
        return best

    def ladder(self, standard_id):
        """Ladder correction of a standard, or None when the ladder is broken."""
        if standard_id not in self.standards:
            return None
        node = standard_id
        seen = set()
        primary = None
        while True:
            if node not in self.standards or node in seen:
                return None
            seen.add(node)
            parent = self.standards[node]["parent"]
            if parent == "":
                primary = node
                break
            node = parent
        total = 0
        node = standard_id
        while node != primary:
            total += self.standards[node]["ratio"]
            node = self.standards[node]["parent"]
        return total


# ------------------------------------------------------------------- ledger


def apply_ledger(archive, samples_by_id):
    """Post the amendment ledger; return (revoked, ignored, unmatched)."""
    revoked = set()
    ignored = 0
    unmatched = 0
    entries = []
    for line in archive.amendment_lines:
        if line.strip() == "":
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            unmatched += 1
            continue
        if not isinstance(entry, dict):
            unmatched += 1
            continue
        entry_id = entry.get("entry_id")
        sequence = entry.get("sequence")
        if not isinstance(entry_id, str) or entry_id == "":
            unmatched += 1
            continue
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            unmatched += 1
            continue
        entries.append((sequence, entry_id, entry))
    # Ascending sequence, a tied sequence by ascending entry_id in
    # code-point order; the file's own line order carries no meaning.
    entries.sort(key=lambda item: (item[0], item[1]))

    seen = set()
    for _sequence, entry_id, entry in entries:
        if entry_id in seen:
            ignored += 1
            continue
        seen.add(entry_id)
        op = entry.get("op")
        if op in ("void", "reinstate", "certify"):
            target = entry.get("sample_id")
            sample = samples_by_id.get(target) if isinstance(target, str) else None
            if sample is None:
                unmatched += 1
            elif op == "void":
                if sample["status"] == "void":
                    ignored += 1
                else:
                    sample["status"] = "void"
            elif op == "reinstate":
                if sample["status"] == "void":
                    sample["status"] = "observed"
                else:
                    ignored += 1
            elif sample["status"] == "suspect":
                sample["status"] = "observed"
            else:
                ignored += 1
        elif op == "revise":
            target = entry.get("sample_id")
            sample = samples_by_id.get(target) if isinstance(target, str) else None
            if sample is None:
                unmatched += 1
            elif sample["status"] == "void":
                ignored += 1
            else:
                written = False
                for field in REVISE_FIELDS:
                    if field not in entry:
                        continue
                    value = entry[field]
                    if field in ("channel_token", "epoch", "unit_token"):
                        if not isinstance(value, str):
                            continue
                    elif field == "standing_basis":
                        if not isinstance(value, bool):
                            continue
                    sample[field] = value
                    written = True
                if not written:
                    ignored += 1
        elif op in ("revoke_certificate", "restore_certificate"):
            cert_id = entry.get("certificate_id")
            if not isinstance(cert_id, str) or cert_id not in archive.certificates:
                unmatched += 1
            elif op == "revoke_certificate":
                if cert_id in revoked:
                    ignored += 1
                else:
                    revoked.add(cert_id)
            elif cert_id in revoked:
                revoked.discard(cert_id)
            else:
                ignored += 1
        elif op == "revise_standard":
            standard_id = entry.get("standard_id")
            if not isinstance(standard_id, str) or standard_id not in archive.standards:
                unmatched += 1
                continue
            parent = entry.get("parent_standard_id")
            ratio = entry.get("ratio_ppm")
            has_parent = "parent_standard_id" in entry
            has_ratio = "ratio_ppm" in entry
            if not has_parent and not has_ratio:
                ignored += 1
                continue
            if has_parent and not isinstance(parent, str):
                ignored += 1
                continue
            if has_ratio and (isinstance(ratio, bool) or not isinstance(ratio, int)):
                ignored += 1
                continue
            if has_parent:
                archive.standards[standard_id]["parent"] = parent
            if has_ratio:
                archive.standards[standard_id]["ratio"] = ratio
        else:
            unmatched += 1
    return revoked, ignored, unmatched


# ------------------------------------------------------------------ samples


def classify(archive):
    """Give every observation row a lifecycle outcome or quarantine reason."""
    samples_by_id = {}
    order = []
    for row in archive.observations:
        record = dict(row)
        # A sample_id on more than one row is carried by its first row
        # alone; later rows are held before any other rule is considered.
        record["duplicate"] = record["sample_id"] in samples_by_id
        if record["duplicate"]:
            record["reason"] = "duplicate_sample"
        else:
            record["reason"] = None
            samples_by_id[record["sample_id"]] = record
        order.append(record)

    revoked, ignored, unmatched = apply_ledger(archive, samples_by_id)

    for record in order:
        if record["duplicate"]:
            continue
        if record["status"] == "void":
            record["reason"] = "voided"
            continue
        if record["status"] == "suspect":
            record["reason"] = "unresolved_suspect"
            continue
        is_whole, raw_value = whole_number(record["raw_count"])
        instant = parse_instant(record["epoch"])
        record["instant"] = instant
        if not is_whole or instant is None:
            record["reason"] = "malformed_sample"
            continue
        record["raw_value"] = raw_value
        channel_id = archive.resolve_channel(record["channel_token"])
        record["channel_id"] = channel_id
        if channel_id is None:
            record["reason"] = "unknown_channel"
            continue
        factor = archive.unit_factor(record["unit_token"])
        record["factor"] = factor
        if factor is None:
            record["reason"] = "unknown_unit"
            continue
        deployment = archive.covering(
            archive.deployments, "channel_id", channel_id, instant
        )
        if deployment is None or deployment["station_id"] == "":
            record["reason"] = "no_deployment"
            continue
        record["station_id"] = deployment["station_id"]
        custody = archive.covering(
            archive.custody, "station_id", deployment["station_id"], instant
        )
        if custody is None or custody["agency_id"] == "":
            record["reason"] = "no_custody"
            continue
        record["agency_id"] = custody["agency_id"]
        certificate = archive.select_certificate(channel_id, instant, revoked)
        if certificate is None:
            record["reason"] = "no_certificate"
            continue
        record["certificate_id"] = certificate["id"]
        ladder = archive.ladder(certificate["standard_id"])
        if ladder is None:
            record["reason"] = "broken_ladder"
            continue
        record["ladder"] = ladder
    return order, revoked, ignored, unmatched


def parameter_sources(archive, record):
    """Resolve gain, offset and drift for an accepted sample."""
    channel = archive.channels[record["channel_id"]]
    tables = {
        "certificate": archive.certificates[record["certificate_id"]],
        "station": archive.stations.get(record["station_id"], {}),
        "network": archive.policy,
    }
    order = list(SOURCE_ORDER)
    if channel["provisional"]:
        order[0], order[1] = order[1], order[0]
    chosen = {}
    for parameter in PARAMETERS:
        value = None
        source = "network"
        for name in order:
            candidate = as_int(tables[name].get(PARAMETER_KEYS[name][parameter]))
            if candidate is not None:
                value = candidate
                source = name
                break
        chosen[parameter] = (value, source)
    return chosen


def settle_standing(archive, qualifying):
    """The least reporting set consistent with the standing statements."""
    bands = []
    for band in archive.thresholds.get("reporting_floor_bands", []):
        if not isinstance(band, dict):
            continue
        at_least = as_int(band.get("reporting_arrays_at_least"))
        minimum = as_int(band.get("minimum_qualifying_observations"))
        if at_least is None or minimum is None:
            continue
        bands.append((at_least, minimum))
    bands.sort()
    custody_band = as_int(archive.thresholds.get("custody_secondary_band"))

    def floor_for(count):
        applicable = None
        for at_least, minimum in bands:
            if at_least <= count:
                applicable = minimum
        return applicable

    reporting = set()
    rounds = {}
    number = 0
    while True:
        number += 1
        reporting_count = defaultdict(int)
        for channel_id in reporting:
            reporting_count[archive.channels[channel_id]["area"]] += 1
        joined = []
        for channel_id in archive.channels:
            if channel_id in reporting:
                continue
            area = archive.channels[channel_id]["area"]
            count = qualifying.get(channel_id, 0)
            floor = floor_for(reporting_count[area])
            if floor is not None and count >= floor:
                joined.append(channel_id)
                continue
            if custody_band is None:
                continue
            custodian = archive.standing_custody.get(channel_id)
            if (
                custodian is not None
                and custodian in reporting
                and count >= custody_band
            ):
                joined.append(channel_id)
        if not joined:
            break
        for channel_id in joined:
            reporting.add(channel_id)
            rounds[channel_id] = number
    return reporting, rounds


# ------------------------------------------------------------------ reports


def largest_sample(accepted):
    if not accepted:
        return {"reported_nano": 0, "sample_id": None}
    best = min(accepted, key=lambda row: (-row["figure"], row["sample_id"]))
    return {"reported_nano": best["figure"], "sample_id": best["sample_id"]}


def alert_for(name, reported, canonical, gate):
    delta = reported - canonical
    if abs(delta) >= gate:
        return {"name": name, "delta_nano": delta}
    return None


def figures(rows):
    return {
        "canonical_nano": sum(row["canonical"] for row in rows),
        "traced_nano": sum(row["traced"] for row in rows),
        "drift_nano": sum(row["drifted"] for row in rows),
        "reported_nano": sum(row["figure"] for row in rows),
    }


def area_report(rows, name, allocation, gate):
    values = figures(rows)
    alert = alert_for(name, values["reported_nano"], values["canonical_nano"], gate)
    return {
        "name": name,
        "accepted_count": len(rows),
        "canonical_nano": values["canonical_nano"],
        "traced_nano": values["traced_nano"],
        "drift_nano": values["drift_nano"],
        "reported_nano": values["reported_nano"],
        "allocation_nano": allocation,
        "channel_totals": ordered(
            total_by(rows, lambda r: r["channel_id"], lambda r: r["figure"])
        ),
        "station_totals": ordered(
            total_by(rows, lambda r: r["station_id"], lambda r: r["figure"])
        ),
        "segment_counts": ordered(count_by(rows, lambda r: r["operator_class"])),
        "alerts": [] if alert is None else [alert],
    }


def class_report(rows, name, allocation, gate):
    values = figures(rows)
    alert = alert_for(name, values["reported_nano"], values["canonical_nano"], gate)
    return {
        "name": name,
        "accepted_count": len(rows),
        "canonical_nano": values["canonical_nano"],
        "traced_nano": values["traced_nano"],
        "drift_nano": values["drift_nano"],
        "reported_nano": values["reported_nano"],
        "allocation_nano": allocation,
        "channel_totals": ordered(
            total_by(rows, lambda r: r["channel_id"], lambda r: r["figure"])
        ),
        "agency_totals": ordered(
            total_by(rows, lambda r: r["agency_id"], lambda r: r["figure"])
        ),
        "array_counts": ordered(count_by(rows, lambda r: r["area"])),
        "alerts": [] if alert is None else [alert],
    }


def derive(root):
    """Derive every report object from the archive at root."""
    archive = Archive(root)
    order, revoked, ignored, unmatched = classify(archive)

    survived = [row for row in order if row["reason"] is None]
    qualifying = dict(
        count_by(
            [row for row in survived if row["standing_basis"]],
            lambda row: row["channel_id"],
        )
    )
    reporting, rounds = settle_standing(archive, qualifying)

    accepted = []
    for row in survived:
        if row["standing_basis"] or row["channel_id"] in reporting:
            accepted.append(row)
        else:
            row["reason"] = "unreported_array"

    # Drift positions run over accepted samples only, ordered by epoch
    # then sample identifier within each channel and certificate.
    groups = defaultdict(list)
    for row in accepted:
        groups[(row["channel_id"], row["certificate_id"])].append(row)
    for group in groups.values():
        group.sort(key=lambda row: (row["instant"], row["sample_id"]))
        for index, row in enumerate(group):
            row["position"] = index

    floor_value = as_int(archive.policy.get("minimum_reported_nano"))
    source_counts = dict(
        (parameter, dict((name, 0) for name in SOURCE_ORDER))
        for parameter in PARAMETERS
    )
    for row in accepted:
        chosen = parameter_sources(archive, row)
        for parameter in PARAMETERS:
            value, source = chosen[parameter]
            row[parameter] = 0 if value is None else value
            source_counts[parameter][source] += 1
        num, den = row["factor"]
        canonical = round_half_away(row["raw_value"] * num, den)
        gained = round_half_away(canonical * row["gain"], 1000000)
        traced = round_half_away(gained * 1000000 + row["ladder"], 1000000)
        drifted = row["position"] * row["drift"]
        value = traced - drifted + row["offset"]
        if floor_value is not None and value < floor_value:
            value = floor_value
        row["canonical"] = canonical
        row["traced"] = traced
        row["drifted"] = drifted
        row["figure"] = value
        row["area"] = archive.stations.get(row["station_id"], {}).get("array_name", "")
        row["operator_class"] = archive.agencies.get(row["agency_id"], "")

    area_roster = unique_names(archive.thresholds.get("reported_arrays", []))
    class_roster = unique_names(archive.thresholds.get("reported_segments", []))
    registry_areas = unique_names(
        [channel["area"] for channel in archive.channels.values()]
    )

    reasons = count_by(
        [row for row in order if row["reason"] not in (None, "voided")],
        lambda row: row["reason"],
    )
    voided = sum(1 for row in order if row["reason"] == "voided")
    quarantined = sum(reasons.values())
    observed = len(order)

    accepted_in_area = count_by(accepted, lambda r: r["area"])
    accepted_in_class = count_by(accepted, lambda r: r["operator_class"])
    arealess = accepted_in_area.get("", 0)
    classless = accepted_in_class.get("", 0)
    unrostered = dict(
        (name, accepted_in_area[name])
        for name in sorted(accepted_in_area)
        if name != "" and name not in area_roster
    )

    budget = as_int(archive.policy.get("uncertainty_budget_nano"))
    budget = 0 if budget is None else budget
    gate = as_int(archive.thresholds.get("variance_alert_nano"))
    gate = 0 if gate is None else gate
    alert_ratio = as_int(archive.thresholds.get("quarantine_alert_ratio_ppm"))
    alert_ratio = 0 if alert_ratio is None else alert_ratio

    area_allocation = apportion(
        budget,
        area_roster,
        dict((name, accepted_in_area.get(name, 0)) for name in area_roster),
    )
    class_allocation = apportion(
        budget,
        class_roster,
        dict((name, accepted_in_class.get(name, 0)) for name in class_roster),
    )

    report_id = archive.policy.get("report_id")
    if not isinstance(report_id, str):
        report_id = ""

    applied = sorted({row["certificate_id"] for row in accepted})
    ladder_by_certificate = dict(
        (cert_id, archive.ladder(archive.certificates[cert_id]["standard_id"]))
        for cert_id in applied
    )
    standing_excluded = ordered(
        dict(
            (
                (row["sample_id"], row["certificate_id"])
                for row in order
                if row["reason"] == "unreported_array"
            )
        )
    )
    reporting_by_area = dict(
        (
            name,
            sum(
                1
                for channel_id, channel in archive.channels.items()
                if channel["area"] == name and channel_id in reporting
            ),
        )
        for name in registry_areas
    )

    summary = {
        "report_id": report_id,
        "observed_count": observed,
        "accepted_count": len(accepted),
        "quarantined_count": quarantined,
        "voided_count": voided,
        "budget_nano": budget,
        "canonical_nano": sum(row["canonical"] for row in accepted),
        "traced_nano": sum(row["traced"] for row in accepted),
        "drift_nano": sum(row["drifted"] for row in accepted),
        "reported_nano": sum(row["figure"] for row in accepted),
        "largest_sample": largest_sample(accepted),
        "array_counts": ordered(
            dict((name, accepted_in_area[name]) for name in area_roster if name in accepted_in_area)
        ),
        "array_totals": ordered(
            dict(
                (name, total)
                for name, total in total_by(
                    accepted, lambda r: r["area"], lambda r: r["figure"]
                ).items()
                if name in area_roster
            )
        ),
        "array_allocation_nano": area_allocation,
        "segment_counts": ordered(
            dict(
                (name, accepted_in_class[name])
                for name in class_roster
                if name in accepted_in_class
            )
        ),
        "segment_allocation_nano": class_allocation,
        "channel_totals": ordered(
            total_by(accepted, lambda r: r["channel_id"], lambda r: r["figure"])
        ),
        "station_totals": ordered(
            total_by(accepted, lambda r: r["station_id"], lambda r: r["figure"])
        ),
        "alerts": [
            alert
            for name in area_roster
            for alert in (
                alert_for(
                    name,
                    sum(row["figure"] for row in accepted if row["area"] == name),
                    sum(row["canonical"] for row in accepted if row["area"] == name),
                    gate,
                ),
            )
            if alert is not None
        ],
    }

    policy_audit = {
        "report_id": report_id,
        "budget_nano": budget,
        "minimum_reported_nano": 0 if floor_value is None else floor_value,
        "variance_alert_nano": gate,
        "certificates_applied": applied,
        "certificates_revoked": sorted(revoked),
        "certificates_unused": sorted(
            cert_id
            for cert_id in archive.certificates
            if cert_id not in applied and cert_id not in revoked
        ),
        "ladder_ppm_by_certificate": ladder_by_certificate,
        "parameter_sources": source_counts,
        "provisional_channels": sorted(
            channel_id
            for channel_id, channel in archive.channels.items()
            if channel["provisional"]
        ),
        "qualifying_observations_by_array": dict(
            (channel_id, qualifying.get(channel_id, 0))
            for channel_id in sorted(archive.channels)
        ),
        "reporting_arrays": sorted(reporting),
        "unreported_arrays": sorted(
            channel_id for channel_id in archive.channels if channel_id not in reporting
        ),
        "reporting_round_by_array": dict(
            (channel_id, rounds[channel_id]) for channel_id in sorted(rounds)
        ),
        "reporting_array_count_by_area": reporting_by_area,
        "standing_exclusions_by_certificate": standing_excluded,
    }

    ratio = round_half_away(quarantined * 1000000, observed) if observed > 0 else 0
    data_quality = {
        "observed_count": observed,
        "accepted_count": len(accepted),
        "quarantined_count": quarantined,
        "voided_count": voided,
        "quarantine_reasons": dict((reason, reasons[reason]) for reason in sorted(reasons)),
        "quarantine_ratio_ppm": ratio,
        "quarantine_alert": ratio >= alert_ratio,
        "ignored_amendments": ignored,
        "unmatched_amendments": unmatched,
        "orphan_alias_tokens": sorted(
            {
                token
                for token, channel_id in archive.alias_cells
                if channel_id not in archive.channels
            }
        ),
        "unreported_array_counts": unrostered,
        "input_file_count": archive.input_file_count,
        "conservation_ok": True,
    }

    reports = {
        "summary.json": summary,
        "policy_audit.json": policy_audit,
        "data_quality.json": data_quality,
    }
    for name in area_roster:
        reports[AREA_REPORT_FMT.format(name)] = area_report(
            [row for row in accepted if row["area"] == name],
            name,
            area_allocation[name],
            gate,
        )
    for name in class_roster:
        reports[CLASS_REPORT_FMT.format(name)] = class_report(
            [row for row in accepted if row["operator_class"] == name],
            name,
            class_allocation[name],
            gate,
        )

    context = {
        "area_roster": area_roster,
        "class_roster": class_roster,
        "arealess": arealess,
        "classless": classless,
        "gate": gate,
        "budget": budget,
        "alert_ratio": alert_ratio,
        "revoked": sorted(revoked),
        "applied": applied,
    }
    checks = internal_checks(reports, summary, data_quality, context)
    data_quality["conservation_ok"] = not checks
    reports["data_quality.json"] = data_quality
    context["checks"] = checks
    return reports, context


def internal_checks(reports, summary, data_quality, context):
    """Conservation and partition checks run before serialisation."""
    problems = []
    if (
        data_quality["accepted_count"]
        + data_quality["quarantined_count"]
        + data_quality["voided_count"]
        != data_quality["observed_count"]
    ):
        problems.append("lifecycle counts do not conserve")
    if sum(data_quality["quarantine_reasons"].values()) != data_quality["quarantined_count"]:
        problems.append("quarantine reasons do not sum to the quarantined count")
    if any(reason not in KNOWN_REASONS for reason in data_quality["quarantine_reasons"]):
        problems.append("quarantine reasons hold an unknown reason")
    if sorted(data_quality["quarantine_reasons"]) != list(data_quality["quarantine_reasons"]):
        problems.append("quarantine reasons are not ordered")
    area_keys = [AREA_REPORT_FMT.format(name) for name in context["area_roster"]]
    class_keys = [CLASS_REPORT_FMT.format(name) for name in context["class_roster"]]
    for key in area_keys + class_keys:
        if key not in reports:
            problems.append("missing report %s" % key)
    unrostered = sum(data_quality["unreported_array_counts"].values())
    if (
        sum(reports[key]["accepted_count"] for key in area_keys if key in reports)
        + unrostered
        + context["arealess"]
        != summary["accepted_count"]
    ):
        problems.append("area partitions do not sum to the network count")
    for field in AGGREGATE_FIELDS:
        total = sum(reports[key][field] for key in class_keys if key in reports)
        if total + context["classless"] != summary[field]:
            problems.append("class partitions do not sum to the network %s" % field)
    budget_total = context["budget"] if summary["accepted_count"] > 0 else 0
    if sum(summary["array_allocation_nano"].values()) != budget_total:
        problems.append("area allocations do not sum to the budget")
    if sum(summary["segment_allocation_nano"].values()) != budget_total:
        problems.append("class allocations do not sum to the budget")
    for key, name in zip(area_keys, context["area_roster"]):
        if key in reports and reports[key]["allocation_nano"] != summary[
            "array_allocation_nano"
        ].get(name):
            problems.append("area allocation disagrees with the summary for %s" % name)
    for key, name in zip(class_keys, context["class_roster"]):
        if key in reports and reports[key]["allocation_nano"] != summary[
            "segment_allocation_nano"
        ].get(name):
            problems.append("class allocation disagrees with the summary for %s" % name)
    if summary["accepted_count"] == 0 and summary["largest_sample"] != {
        "reported_nano": 0,
        "sample_id": None,
    }:
        problems.append("largest sample is not empty for an empty population")
    return problems


# ------------------------------------------------------------------ writing


def write_reports(outdir, reports):
    """Replace the report set in outdir, creating the directory if needed."""
    if not os.path.isdir(outdir):
        os.makedirs(outdir, exist_ok=True)
    for name in sorted(os.listdir(outdir)):
        path = os.path.join(outdir, name)
        if not os.path.isfile(path):
            continue
        if name in MAIN_REPORTS or STALE_AREA_RE.match(name) or STALE_CLASS_RE.match(name):
            os.remove(path)
    for name in sorted(reports):
        text = json.dumps(reports[name], indent=2, sort_keys=True) + "\n"
        with open(os.path.join(outdir, name), "w", encoding="utf-8") as handle:
            handle.write(text)


def load_written(outdir, names):
    written = {}
    for name in names:
        with open(os.path.join(outdir, name), "r", encoding="utf-8") as handle:
            written[name] = json.load(handle)
    return written


def verify(outdir, reports, context):
    """Re-read the written reports and check that they agree with one another."""
    problems = list(context.get("checks", []))
    written = load_written(outdir, sorted(reports))
    for name in sorted(reports):
        if written[name] != reports[name]:
            problems.append("%s does not round-trip" % name)
    summary = written["summary.json"]
    audit = written["policy_audit.json"]
    quality = written["data_quality.json"]
    gate = audit["variance_alert_nano"]

    if quality["conservation_ok"] is not True:
        problems.append("conservation flag is false")
    for field in ("observed_count", "accepted_count", "quarantined_count", "voided_count"):
        if summary[field] != quality[field]:
            problems.append("%s disagrees between summary and data quality" % field)
    if (
        quality["accepted_count"]
        + quality["quarantined_count"]
        + quality["voided_count"]
        != quality["observed_count"]
    ):
        problems.append("lifecycle counts do not conserve")
    if sum(quality["quarantine_reasons"].values()) != quality["quarantined_count"]:
        problems.append("quarantine reasons do not sum to the quarantined count")
    observed = quality["observed_count"]
    expected = (
        round_half_away(quality["quarantined_count"] * 1000000, observed)
        if observed
        else 0
    )
    if expected != quality["quarantine_ratio_ppm"]:
        problems.append("quarantine ratio is not the rounded ratio")
    if quality["quarantine_alert"] != (
        quality["quarantine_ratio_ppm"] >= context["alert_ratio"]
    ):
        problems.append("quarantine alert disagrees with the ratio and the gate")
    if quality["input_file_count"] < 0:
        problems.append("input file count is negative")
    orphans = quality["orphan_alias_tokens"]
    if orphans != sorted(set(orphans)):
        problems.append("orphan alias tokens are not an ordered set")
    if quality["observed_count"] == 0 and quality["quarantine_ratio_ppm"] != 0:
        problems.append("an archive holding no observation has a nonzero quarantine ratio")

    area_names = list(context["area_roster"])
    class_names = list(context["class_roster"])
    area_keys = [AREA_REPORT_FMT.format(name) for name in area_names]
    class_keys = [CLASS_REPORT_FMT.format(name) for name in class_names]
    for key in area_keys:
        if key not in written:
            problems.append("missing area report %s" % key)
    for key in class_keys:
        if key not in written:
            problems.append("missing class report %s" % key)

    area_alerts = []
    area_accepted = 0
    area_reported = 0
    for key, name in zip(area_keys, area_names):
        report = written.get(key)
        if report is None:
            continue
        area_accepted += report["accepted_count"]
        area_reported += report["reported_nano"]
        if report["name"] != name:
            problems.append("%s names the wrong area" % key)
        if sum(report["segment_counts"].values()) != report["accepted_count"]:
            problems.append("%s segment counts do not sum" % key)
        if sum(report["channel_totals"].values()) != report["reported_nano"]:
            problems.append("%s channel totals do not sum" % key)
        if sum(report["station_totals"].values()) != report["reported_nano"]:
            problems.append("%s station totals do not sum" % key)
        if report["allocation_nano"] != summary["array_allocation_nano"].get(name):
            problems.append("%s allocation disagrees with the summary" % key)
        if report["reported_nano"] != summary["array_totals"].get(name, 0):
            problems.append("%s reported total disagrees with the summary" % key)
        if report["accepted_count"] != summary["array_counts"].get(name, 0):
            problems.append("%s accepted count disagrees with the summary" % key)
        delta = report["reported_nano"] - report["canonical_nano"]
        expected = [] if abs(delta) < gate else [{"name": name, "delta_nano": delta}]
        if report["alerts"] != expected:
            problems.append("%s alert disagrees with its figures" % key)
        if expected:
            area_alerts.append(expected[0])
    unrostered = sum(quality["unreported_array_counts"].values())
    if area_accepted + unrostered + context["arealess"] != summary["accepted_count"]:
        problems.append("area partitions do not sum to the network count")
    if (
        context["arealess"] == 0
        and unrostered == 0
        and area_reported != summary["reported_nano"]
    ):
        problems.append("area totals do not sum to the network total")

    class_accepted = 0
    for key, name in zip(class_keys, class_names):
        report = written.get(key)
        if report is None:
            continue
        class_accepted += report["accepted_count"]
        if report["name"] != name:
            problems.append("%s names the wrong class" % key)
        if sum(report["array_counts"].values()) != report["accepted_count"]:
            problems.append("%s array counts do not sum" % key)
        if sum(report["channel_totals"].values()) != report["reported_nano"]:
            problems.append("%s channel totals do not sum" % key)
        if sum(report["agency_totals"].values()) != report["reported_nano"]:
            problems.append("%s agency totals do not sum" % key)
        if report["allocation_nano"] != summary["segment_allocation_nano"].get(name):
            problems.append("%s allocation disagrees with the summary" % key)
        if report["accepted_count"] != summary["segment_counts"].get(name, 0):
            problems.append("%s accepted count disagrees with the summary" % key)
        delta = report["reported_nano"] - report["canonical_nano"]
        expected = [] if abs(delta) < gate else [{"name": name, "delta_nano": delta}]
        if report["alerts"] != expected:
            problems.append("%s alert disagrees with its figures" % key)
    if class_accepted + context["classless"] != summary["accepted_count"]:
        problems.append("class partitions do not sum to the network count")
    for field in AGGREGATE_FIELDS:
        total = sum(written[key][field] for key in class_keys if key in written)
        if total + context["classless"] != summary[field]:
            problems.append("class partitions do not sum to the network %s" % field)

    budget_total = summary["budget_nano"] if summary["accepted_count"] else 0
    if sum(summary["array_allocation_nano"].values()) != budget_total:
        problems.append("area allocations do not sum to the budget")
    if sum(summary["segment_allocation_nano"].values()) != budget_total:
        problems.append("class allocations do not sum to the budget")
    if summary["budget_nano"] != audit["budget_nano"]:
        problems.append("budget disagrees between summary and policy audit")
    if summary["alerts"] != area_alerts:
        problems.append("summary alert list does not match the area alerts")
    if sum(summary["channel_totals"].values()) != summary["reported_nano"]:
        problems.append("channel totals do not sum to the network total")
    if sum(summary["station_totals"].values()) != summary["reported_nano"]:
        problems.append("station totals do not sum to the network total")

    reporting = audit["reporting_arrays"]
    unreported = audit["unreported_arrays"]
    if reporting != sorted(reporting):
        problems.append("reporting channel list is not ordered")
    if unreported != sorted(unreported):
        problems.append("non-reporting channel list is not ordered")
    if set(reporting) & set(unreported):
        problems.append("reporting and non-reporting channel lists overlap")
    if sum(audit["reporting_array_count_by_area"].values()) != len(reporting):
        problems.append("area reporting counts do not sum to the reporting set")
    qualifying = audit["qualifying_observations_by_array"]
    if list(qualifying) != sorted(qualifying):
        problems.append("qualifying counts are not ordered")
    if sum(qualifying.values()) > summary["accepted_count"]:
        problems.append("qualifying counts exceed the accepted count")
    for parameter, sources in audit["parameter_sources"].items():
        if sorted(sources) != sorted(SOURCE_ORDER):
            problems.append("parameter sources for %s are not complete" % parameter)
        elif sum(sources.values()) != summary["accepted_count"]:
            problems.append("parameter-source counts do not sum to the accepted count")
    exclusions = audit["standing_exclusions_by_certificate"]
    if list(exclusions) != sorted(exclusions):
        problems.append("standing exclusions are not ordered")
    if quality["quarantine_reasons"].get("unreported_array", 0) != len(exclusions):
        problems.append("standing exclusions disagree with the quarantine count")
    for sample_id, cert_id in exclusions.items():
        if not isinstance(cert_id, str) or cert_id == "":
            problems.append("standing exclusion for %s carries no certificate" % sample_id)
    if audit["certificates_revoked"] != context["revoked"]:
        problems.append("revoked certificate list disagrees with the ledger")
    if audit["certificates_applied"] != context["applied"]:
        problems.append("applied certificate list disagrees with the derivation")
    if set(audit["certificates_applied"]) & set(audit["certificates_revoked"]):
        problems.append("a certificate is both applied and revoked")
    if set(audit["certificates_unused"]) & (
        set(audit["certificates_applied"]) | set(audit["certificates_revoked"])
    ):
        problems.append("an unused certificate is also applied or revoked")
    for cert_id, ladder in audit["ladder_ppm_by_certificate"].items():
        if not isinstance(ladder, int):
            problems.append("ladder for %s is not an integer" % cert_id)
    rounds = audit["reporting_round_by_array"]
    if sorted(rounds) != reporting:
        problems.append("reporting rounds do not cover the reporting set")
    for channel_id, number in rounds.items():
        if number < 1 or number > len(reporting):
            problems.append("reporting round for %s is out of range" % channel_id)
    if summary["accepted_count"] == 0:
        if summary["largest_sample"] != {"reported_nano": 0, "sample_id": None}:
            problems.append("largest sample is not empty for an empty population")
    elif not isinstance(summary["largest_sample"]["sample_id"], str):
        problems.append("largest sample carries no identifier")
    return problems


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py <archive_dir> <output_dir>\n")
        return 2
    archive_dir, output_dir = argv[1], argv[2]
    if not os.path.isdir(archive_dir):
        sys.stderr.write("archive directory not found: %s\n" % archive_dir)
        return 2
    reports, context = derive(archive_dir)
    write_reports(output_dir, reports)
    problems = verify(output_dir, reports, context)
    if problems:
        for problem in problems:
            sys.stderr.write("reconciliation failure: %s\n" % problem)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
