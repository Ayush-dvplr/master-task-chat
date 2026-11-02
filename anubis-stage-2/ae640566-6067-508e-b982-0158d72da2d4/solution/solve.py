"""Reference derivation for the Helios gravimeter array reconciliation.

Usage: derive_report.py DATA_DIR OUT_DIR
"""

from __future__ import annotations

import csv
import json
import os
import sys
from collections import Counter
from pathlib import Path

MICRO = 1000000
REASONS = (
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
TABLES = (
    "units",
    "channel_registry",
    "channel_aliases",
    "stations",
    "deployments",
    "agencies",
    "custody",
    "certificates",
    "standards",
    "observations",
)
SAMPLE_FIELDS = ("channel_token", "epoch", "raw_count", "unit_token", "standing_basis")
# A structural label is this prefix plus digits; it names the prefix, a hyphen and four digits.
STRUCTURAL_PREFIX = "HLS"
# parameter, certificate column, station column, policy key
PARAMETERS = (
    ("gain", "gain_micro", "station_gain_micro", "network_gain_micro"),
    ("offset", "offset_nano", "station_offset_nano", "network_offset_nano"),
    (
        "drift",
        "drift_nano_per_sample",
        "station_drift_nano_per_sample",
        "network_drift_nano_per_sample",
    ),
)
ORDINARY_SOURCES = ("certificate", "station", "network")
PROVISIONAL_SOURCES = ("station", "certificate", "network")
FIGURES = (
    ("canonical_nano", "canonical"),
    ("traced_nano", "traced"),
    ("drift_nano", "drift"),
    ("reported_nano", "reported"),
)


def read_csv(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        stripped = [[part.strip() for part in line] for line in csv.reader(handle)]
    records = [line for line in stripped if any(line)]
    if not records:
        return []
    columns, width = records[0], len(records[0])
    return [
        dict(zip(columns, line[:width] + [""] * (width - len(line))))
        for line in records[1:]
    ]


def read_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def read_ledger(path):
    """Return the well formed ledger entries and the number of malformed lines."""
    rows = []
    malformed = 0
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not well_formed_entry(entry):
                malformed += 1
                continue
            rows.append(entry)
    return rows, malformed


def well_formed_entry(entry):
    if not isinstance(entry, dict):
        return False
    entry_id = entry.get("entry_id")
    sequence = entry.get("sequence")
    if not isinstance(entry_id, str) or entry_id == "":
        return False
    return isinstance(sequence, int) and not isinstance(sequence, bool)


def is_json_integer(value):
    return isinstance(value, int) and not isinstance(value, bool)


def keep_alnum(text):
    return "".join(filter(str.isalnum, text))


def norm_label(text):
    # Case is folded first: folding can emit marks that the letter-and-digit filter drops.
    return keep_alnum(str(text).upper())


def norm_unit(text):
    return keep_alnum(str(text).lower())


def half_up(num, den):
    """Round num/den (den > 0) to the nearest integer, halves away from zero."""
    whole, rest = divmod(abs(num), den)
    if 2 * rest >= den:
        whole += 1
    return -whole if num < 0 else whole


def ascii_digits(text):
    return text != "" and text.isascii() and text.isdigit()


def read_instant(text):
    """Turn `Y-M-D[T| ]h:m:s` with or without zero padding into a sortable tuple, else None."""
    text = text.strip()
    for sep in ("T", " "):
        day, found, clock = text.partition(sep)
        if found:
            break
    else:
        return None
    parts = day.split("-") + clock.split(":")
    if len(day.split("-")) != 3 or len(clock.split(":")) != 3:
        return None
    if not all(ascii_digits(part) for part in parts):
        return None
    return tuple(int(part) for part in parts)


def parse_epoch(text):
    """Read a table timestamp: blank means an open interval end, anything else must parse."""
    text = text.strip()
    if text == "":
        return None
    moment = read_instant(text)
    if moment is None:
        raise ValueError("unreadable timestamp: %r" % text)
    return moment


def parse_count(text):
    """Read a raw count written as an optional sign and ASCII digits, else None."""
    if text is None:
        return None
    text = text.strip()
    digits = text[1:] if text[:1] in ("+", "-") else text
    if not ascii_digits(digits):
        return None
    return int(text)


def parse_factor(text):
    """Return (numerator, denominator) for `N` or `N/D` with positive integers, else None."""
    numerator, slash, denominator = text.strip().partition("/")
    if not slash:
        denominator = "1"
    numerator, denominator = numerator.strip(), denominator.strip()
    if not (numerator.isdigit() and denominator.isdigit()):
        return None
    if not (numerator.isascii() and denominator.isascii()):
        return None
    top, bottom = int(numerator), int(denominator)
    if top == 0 or bottom == 0:
        return None
    return top, bottom


def is_true(text, blank):
    text = text.strip()
    if text == "":
        return blank
    return text.lower() == "true"


def cell(row, key):
    value = row.get(key)
    if value is None:
        return ""
    return value.strip()


def opt_int(row, key):
    text = cell(row, key)
    if text == "":
        return None
    return int(text)


def covers(start, end, epoch):
    if epoch < start:
        return False
    if end is not None and epoch > end:
        return False
    return True


def pick_interval(rows, epoch, start_key, end_key, id_key):
    chosen = None
    chosen_start = None
    for row in rows:
        start = parse_epoch(cell(row, start_key))
        if not covers(start, parse_epoch(cell(row, end_key)), epoch):
            continue
        if chosen is None or start > chosen_start:
            chosen, chosen_start = row, start
        elif start == chosen_start and cell(row, id_key) < cell(chosen, id_key):
            chosen = row
    return chosen


def ladder_ppm(standards, standard_id):
    total = 0
    seen = set()
    current = standard_id
    while True:
        if current not in standards or current in seen:
            return None
        seen.add(current)
        row = standards[current]
        parent = cell(row, "parent_standard_id")
        if parent == "":
            return total
        total += int(cell(row, "ratio_ppm"))
        current = parent


def apportion(budget, counts, names):
    """Largest-remainder shares of the budget over names, weighted by their counts."""
    weights = [(name, counts.get(name, 0)) for name in names]
    population = sum(weight for _, weight in weights)
    if population <= 0:
        return {name: 0 for name in names}
    shares = {}
    ranking = []
    for name, weight in weights:
        whole, rest = divmod(budget * weight, population)
        shares[name] = whole
        ranking.append((-rest, name))
    ranking.sort()
    spare = budget - sum(shares.values())
    for _, name in ranking[:spare]:
        shares[name] += 1
    return shares


def group_rows(rows, key):
    grouped = {}
    for row in rows:
        grouped.setdefault(cell(row, key), []).append(row)
    return grouped


def index_rows(rows, key):
    return {cell(row, key): row for row in rows}


class LedgerReplay:
    """Lifecycle state of every sample after the well formed ledger entries are posted."""

    def __init__(self, observations, certificate_ids, standards, malformed_lines):
        self.status = {}
        self.values = {}
        self.duplicates = 0
        for row in observations:
            sid = cell(row, "sample_id")
            if sid in self.status:
                self.duplicates += 1
                continue
            self.status[sid] = cell(row, "status")
            self.values[sid] = {key: cell(row, key) for key in SAMPLE_FIELDS}
        self.certificate_ids = certificate_ids
        self.standards = standards
        self.revoked = set()
        self.ignored = 0
        self.unmatched = malformed_lines
        self.handlers = {
            "revoke_certificate": self.revoke,
            "restore_certificate": self.restore,
            "revise_standard": self.revise_standard,
            "revise": self.revise,
            "void": self.void,
            "reinstate": self.reinstate,
            "certify": self.certify,
        }

    def post_all(self, entries):
        posted = set()
        for entry in sorted(entries, key=lambda item: (item["sequence"], item["entry_id"])):
            if entry["entry_id"] in posted:
                self.ignored += 1
                continue
            posted.add(entry["entry_id"])
            op = entry.get("op")
            handler = self.handlers.get(op) if isinstance(op, str) else None
            if handler is None:
                self.unmatched += 1
            else:
                handler(entry)

    def known_certificate(self, entry):
        cert_id = entry.get("certificate_id")
        if isinstance(cert_id, str) and cert_id in self.certificate_ids:
            return cert_id
        self.unmatched += 1
        return None

    def revoke(self, entry):
        cert_id = self.known_certificate(entry)
        if cert_id is None:
            return
        if cert_id in self.revoked:
            self.ignored += 1
        else:
            self.revoked.add(cert_id)

    def restore(self, entry):
        cert_id = self.known_certificate(entry)
        if cert_id is None:
            return
        if cert_id in self.revoked:
            self.revoked.discard(cert_id)
        else:
            self.ignored += 1

    def revise_standard(self, entry):
        std_id = entry.get("standard_id")
        if not isinstance(std_id, str) or std_id not in self.standards:
            self.unmatched += 1
            return
        names_parent = "parent_standard_id" in entry
        names_ratio = "ratio_ppm" in entry
        parent_ok = not names_parent or isinstance(entry["parent_standard_id"], str)
        ratio_ok = not names_ratio or is_json_integer(entry["ratio_ppm"])
        if not (names_parent or names_ratio) or not (parent_ok and ratio_ok):
            self.ignored += 1
            return
        row = self.standards[std_id]
        if names_parent:
            row["parent_standard_id"] = entry["parent_standard_id"]
        if names_ratio:
            row["ratio_ppm"] = str(entry["ratio_ppm"])

    def sample_of(self, entry):
        sid = entry.get("sample_id")
        if isinstance(sid, str) and sid in self.status:
            return sid
        self.unmatched += 1
        return None

    def revise(self, entry):
        sid = self.sample_of(entry)
        if sid is None:
            return
        if self.status[sid] == "void":
            self.ignored += 1
            return
        values = self.values[sid]
        for key in ("channel_token", "unit_token", "standing_basis"):
            if key in entry:
                given = entry[key]
                if isinstance(given, bool):
                    given = "true" if given else "false"
                values[key] = str(given)
        if "epoch" in entry:
            # A revised epoch must itself be text naming an instant.
            values["epoch"] = entry["epoch"] if isinstance(entry["epoch"], str) else None
        if "raw_count" in entry:
            # Only a JSON integer is a whole count; text, fractions and booleans are not.
            given = entry["raw_count"]
            values["raw_count"] = str(given) if is_json_integer(given) else None

    def move(self, entry, allowed_from, target, refuse_from):
        sid = self.sample_of(entry)
        if sid is None:
            return
        current = self.status[sid]
        if allowed_from is not None and current != allowed_from:
            self.ignored += 1
        elif refuse_from is not None and current == refuse_from:
            self.ignored += 1
        else:
            self.status[sid] = target

    def void(self, entry):
        self.move(entry, None, "void", "void")

    def reinstate(self, entry):
        self.move(entry, "void", "observed", None)

    def certify(self, entry):
        self.move(entry, "suspect", "observed", None)


class Archive:
    """The tables of one archive, indexed the way the classification rules look them up."""

    def __init__(self, data_dir):
        self.root = Path(data_dir)
        self.policy = read_json(self.root / "policy.json")
        self.thresholds = read_json(self.root / "thresholds.json")
        self.area_roster = list(self.thresholds["reported_arrays"])
        self.class_roster = list(self.thresholds["reported_segments"])
        tables = {name: read_csv(self.root / (name + ".csv")) for name in TABLES}
        self.registry_rows = tables["channel_registry"]
        self.alias_rows = tables["channel_aliases"]
        self.observations = tables["observations"]
        self.registry = index_rows(self.registry_rows, "channel_id")
        self.alias_target = {
            norm_label(cell(row, "alias_token")): cell(row, "channel_id")
            for row in self.alias_rows
        }
        self.factors = {}
        for row in tables["units"]:
            factor = parse_factor(cell(row, "factor_nano"))
            if factor is not None:
                self.factors[norm_unit(cell(row, "unit_token"))] = factor
        self.stations = index_rows(tables["stations"], "station_id")
        self.agencies = index_rows(tables["agencies"], "agency_id")
        self.standards = index_rows(tables["standards"], "standard_id")
        self.certificates = index_rows(tables["certificates"], "certificate_id")
        self.certificates_of = group_rows(tables["certificates"], "channel_id")
        self.deployments_of = group_rows(tables["deployments"], "channel_id")
        self.custody_of = group_rows(tables["custody"], "station_id")
        self.custodian = {
            cell(row, "array_channel_id"): cell(row, "custodian_channel_id")
            for row in tables["custody"]
            if cell(row, "array_channel_id")
        }
        entries, malformed = read_ledger(self.root / "amendments.jsonl")
        self.ledger = LedgerReplay(
            self.observations, self.certificates, self.standards, malformed
        )
        self.ledger.post_all(entries)

    def file_count(self):
        return sum(1 for item in self.root.iterdir() if item.is_file())


# Classification rules, in the order the calibration control shows they apply.
# Each returns the quarantine reason when it holds the record, else fills the draft.


def check_values(archive, draft):
    values = draft["values"]
    draft["raw"] = parse_count(values["raw_count"])
    draft["epoch"] = None if values["epoch"] is None else read_instant(values["epoch"])
    if draft["raw"] is None or draft["epoch"] is None:
        return "malformed_sample"
    return None


def resolve_channel(archive, draft):
    label = norm_label(draft["values"]["channel_token"])
    digits = label[len(STRUCTURAL_PREFIX):]
    if label in archive.alias_target:
        channel_id = archive.alias_target[label]
    elif label.startswith(STRUCTURAL_PREFIX) and digits.isdigit():
        channel_id = "%s-%s" % (STRUCTURAL_PREFIX, digits.zfill(4))
    else:
        return "unknown_channel"
    if channel_id not in archive.registry:
        return "unknown_channel"
    draft["channel_id"] = channel_id
    return None


def resolve_deployment(archive, draft):
    row = pick_interval(
        archive.deployments_of.get(draft["channel_id"], []),
        draft["epoch"], "valid_from", "valid_to", "deployment_id",
    )
    if row is None or cell(row, "station_id") not in archive.stations:
        return "no_deployment"
    draft["station"] = archive.stations[cell(row, "station_id")]
    return None


def resolve_custody(archive, draft):
    row = pick_interval(
        archive.custody_of.get(cell(draft["station"], "station_id"), []),
        draft["epoch"], "effective_from", "effective_to", "custody_id",
    )
    if row is None or cell(row, "agency_id") not in archive.agencies:
        return "no_custody"
    draft["agency"] = archive.agencies[cell(row, "agency_id")]
    return None


def resolve_certificate(archive, draft):
    best = None
    for row in archive.certificates_of.get(draft["channel_id"], []):
        if cell(row, "certificate_id") in archive.ledger.revoked:
            continue
        start = parse_epoch(cell(row, "valid_from"))
        if not covers(start, parse_epoch(cell(row, "valid_to")), draft["epoch"]):
            continue
        rank = (start, cell(row, "certificate_id"))
        if best is None or rank > best[0]:
            best = (rank, row)
    if best is None:
        return "no_certificate"
    draft["certificate"] = best[1]
    return None


def resolve_unit(archive, draft):
    factor = archive.factors.get(norm_unit(draft["values"]["unit_token"]))
    if factor is None:
        return "unknown_unit"
    draft["factor"] = factor
    return None


def resolve_ladder(archive, draft):
    ppm = ladder_ppm(archive.standards, cell(draft["certificate"], "standard_id"))
    if ppm is None:
        return "broken_ladder"
    draft["ladder_ppm"] = ppm
    return None


RULES = (
    check_values,
    resolve_channel,
    resolve_deployment,
    resolve_custody,
    resolve_certificate,
    resolve_unit,
    resolve_ladder,
)


class Sample:
    """An observation that survived every non-standing rule."""

    def __init__(self, sample_id, draft, registry):
        self.sample_id = sample_id
        self.channel_id = draft["channel_id"]
        self.epoch = draft["epoch"]
        numerator, denominator = draft["factor"]
        self.canonical = half_up(draft["raw"] * numerator, denominator)
        self.station = draft["station"]
        self.station_id = cell(self.station, "station_id")
        self.area = cell(self.station, "array_name")
        self.agency_id = cell(draft["agency"], "agency_id")
        self.operator_class = cell(draft["agency"], "operator_class")
        self.certificate = draft["certificate"]
        self.certificate_id = cell(self.certificate, "certificate_id")
        self.ladder_ppm = draft["ladder_ppm"]
        self.basis = is_true(draft["values"]["standing_basis"], True)
        self.provisional = is_true(cell(registry[self.channel_id], "provisional"), False)
        self.parameters = {}
        self.position = 0
        self.traced = 0
        self.drift = 0
        self.reported = 0


def classify(archive):
    """Split the observed samples into held reasons and surviving samples."""
    holds = {
        sid: "unresolved_suspect"
        for sid, status in archive.ledger.status.items()
        if status == "suspect"
    }
    survivors = []
    for sid, status in archive.ledger.status.items():
        if status != "observed":
            continue
        draft = {"values": archive.ledger.values[sid]}
        reason = None
        for rule in RULES:
            reason = rule(archive, draft)
            if reason:
                break
        if reason:
            holds[sid] = reason
        else:
            survivors.append(Sample(sid, draft, archive.registry))
    return holds, survivors


def settle_standing(archive, survivors):
    """Return qualifying counts and the round in which each reporting channel joined."""
    area_of = {
        channel_id: cell(row, "reporting_area") for channel_id, row in archive.registry.items()
    }
    qualifying = dict.fromkeys(archive.registry, 0)
    for sample in survivors:
        if sample.basis:
            qualifying[sample.channel_id] += 1
    bands = [
        (band["reporting_arrays_at_least"], band["minimum_qualifying_observations"])
        for band in archive.thresholds["reporting_floor_bands"]
    ]
    secondary = archive.thresholds["custody_secondary_band"]

    def applicable_floor(reporting_in_area):
        chosen = None
        for at_least, minimum in bands:
            if at_least <= reporting_in_area and (chosen is None or at_least >= chosen[0]):
                chosen = (at_least, minimum)
        return None if chosen is None else chosen[1]

    def qualifies(channel_id, members, reporting_by_area):
        floor = applicable_floor(reporting_by_area[area_of[channel_id]])
        if floor is not None and qualifying[channel_id] >= floor:
            return True
        holder = archive.custodian.get(channel_id)
        return holder in members and qualifying[channel_id] >= secondary

    def entrants(members):
        reporting_by_area = Counter(area_of[channel_id] for channel_id in members)
        return {
            channel_id
            for channel_id in archive.registry
            if channel_id not in members and qualifies(channel_id, members, reporting_by_area)
        }

    joined = {}
    members = frozenset()
    round_number = 1
    newcomers = entrants(members)
    while newcomers:
        for channel_id in newcomers:
            joined[channel_id] = round_number
        members = members | newcomers
        round_number += 1
        newcomers = entrants(members)
    return qualifying, joined


def choose_parameters(archive, samples):
    """Pick gain, offset and drift for each sample and count where each value came from."""
    sources = {
        parameter: {"certificate": 0, "network": 0, "station": 0}
        for parameter, _, _, _ in PARAMETERS
    }
    for sample in samples:
        order = PROVISIONAL_SOURCES if sample.provisional else ORDINARY_SOURCES
        for parameter, cert_key, station_key, policy_key in PARAMETERS:
            offered = {
                "certificate": opt_int(sample.certificate, cert_key),
                "station": opt_int(sample.station, station_key),
                "network": archive.policy[policy_key],
            }
            source = next(name for name in order if offered[name] is not None)
            sample.parameters[parameter] = offered[source]
            sources[parameter][source] += 1
    return sources


def assign_drift_positions(samples):
    previous = None
    position = 0
    ordered = sorted(
        samples, key=lambda s: (s.channel_id, s.certificate_id, s.epoch, s.sample_id)
    )
    for sample in ordered:
        group = (sample.channel_id, sample.certificate_id)
        position = position + 1 if group == previous else 0
        sample.position = position
        previous = group


def compute_figures(samples, floor):
    for sample in samples:
        gained = half_up(sample.canonical * sample.parameters["gain"], MICRO)
        sample.traced = half_up(gained * (MICRO + sample.ladder_ppm), MICRO)
        sample.drift = sample.position * sample.parameters["drift"]
        sample.reported = max(floor, sample.traced - sample.drift + sample.parameters["offset"])


def reported_by(samples, key):
    totals = {}
    for sample in samples:
        name = key(sample)
        totals[name] = totals.get(name, 0) + sample.reported
    return totals


def counted_by(samples, key):
    return dict(Counter(key(sample) for sample in samples))


def figure_sums(samples):
    return {
        field: sum(getattr(sample, attribute) for sample in samples)
        for field, attribute in FIGURES
    }


def bucket_report(name, members, allocation, gate, breakdowns):
    report = figure_sums(members)
    report["name"] = name
    report["accepted_count"] = len(members)
    report["allocation_nano"] = allocation
    report["channel_totals"] = reported_by(members, lambda s: s.channel_id)
    for field, (summarise, key) in breakdowns.items():
        report[field] = summarise(members, key)
    gap = report["reported_nano"] - report["canonical_nano"]
    report["alerts"] = [{"delta_nano": gap, "name": name}] if abs(gap) >= gate else []
    return report


AREA_BREAKDOWNS = {
    "station_totals": (reported_by, lambda s: s.station_id),
    "segment_counts": (counted_by, lambda s: s.operator_class),
}
CLASS_BREAKDOWNS = {
    "agency_totals": (reported_by, lambda s: s.agency_id),
    "array_counts": (counted_by, lambda s: s.area),
}


def derive(data_dir):
    archive = Archive(data_dir)
    policy, thresholds, ledger = archive.policy, archive.thresholds, archive.ledger

    holds, survivors = classify(archive)
    qualifying, joined = settle_standing(archive, survivors)
    excluded = {
        sample.sample_id: sample.certificate_id
        for sample in survivors
        if not sample.basis and sample.channel_id not in joined
    }
    for sid in excluded:
        holds[sid] = "unreported_array"
    accepted = sorted(
        (sample for sample in survivors if sample.sample_id not in excluded),
        key=lambda s: s.sample_id,
    )
    sources = choose_parameters(archive, accepted)
    assign_drift_positions(accepted)
    compute_figures(accepted, policy["minimum_reported_nano"])

    area_roster, class_roster = archive.area_roster, archive.class_roster
    budget, gate = policy["uncertainty_budget_nano"], thresholds["variance_alert_nano"]
    area_counts = counted_by(accepted, lambda s: s.area)
    class_counts = counted_by(accepted, lambda s: s.operator_class)
    area_shares = apportion(budget, area_counts, area_roster)
    class_shares = apportion(budget, class_counts, class_roster)

    areas = {
        name: bucket_report(
            name, [s for s in accepted if s.area == name], area_shares[name], gate,
            AREA_BREAKDOWNS,
        )
        for name in area_roster
    }
    classes = {
        name: bucket_report(
            name, [s for s in accepted if s.operator_class == name], class_shares[name], gate,
            CLASS_BREAKDOWNS,
        )
        for name in class_roster
    }
    top = min(accepted, key=lambda s: (-s.reported, s.sample_id), default=None)
    observed = len(archive.observations)
    voided = sum(1 for status in ledger.status.values() if status == "void")
    quarantined = len(holds) + ledger.duplicates

    summary = figure_sums(accepted)
    summary.update(
        report_id=policy["report_id"],
        observed_count=observed,
        accepted_count=len(accepted),
        voided_count=voided,
        quarantined_count=quarantined,
        array_counts=area_counts,
        array_totals=reported_by(accepted, lambda s: s.area),
        segment_counts=class_counts,
        station_totals=reported_by(accepted, lambda s: s.station_id),
        channel_totals=reported_by(accepted, lambda s: s.channel_id),
        largest_sample={
            "reported_nano": top.reported if top else 0,
            "sample_id": top.sample_id if top else None,
        },
        budget_nano=budget,
        array_allocation_nano=area_shares,
        segment_allocation_nano=class_shares,
        alerts=[alert for name in sorted(area_roster) for alert in areas[name]["alerts"]],
    )

    applied = {sample.certificate_id for sample in accepted}
    reporting = set(joined)
    registry_areas = {cell(row, "reporting_area") for row in archive.registry_rows}
    audit = {
        "budget_nano": budget,
        "certificates_applied": sorted(applied),
        "certificates_revoked": sorted(ledger.revoked),
        "certificates_unused": sorted(
            set(archive.certificates) - ledger.revoked - applied
        ),
        "ladder_ppm_by_certificate": {s.certificate_id: s.ladder_ppm for s in accepted},
        "minimum_reported_nano": policy["minimum_reported_nano"],
        "parameter_sources": sources,
        "provisional_channels": sorted(
            cell(row, "channel_id")
            for row in archive.registry_rows
            if is_true(cell(row, "provisional"), False)
        ),
        "qualifying_observations_by_array": qualifying,
        "report_id": policy["report_id"],
        "reporting_array_count_by_area": {
            area: sum(
                1 for channel_id in reporting
                if cell(archive.registry[channel_id], "reporting_area") == area
            )
            for area in registry_areas
        },
        "reporting_arrays": sorted(reporting),
        "reporting_round_by_array": joined,
        "standing_exclusions_by_certificate": excluded,
        "unreported_arrays": sorted(set(archive.registry) - reporting),
        "variance_alert_nano": gate,
    }

    reasons = Counter(holds.values())
    reasons["duplicate_sample"] += ledger.duplicates
    ratio = half_up(quarantined * MICRO, observed) if observed else 0
    quality = {
        "accepted_count": len(accepted),
        "conservation_ok": len(accepted) + voided + quarantined == observed,
        "ignored_amendments": ledger.ignored,
        "input_file_count": archive.file_count(),
        "observed_count": observed,
        "orphan_alias_tokens": sorted(
            cell(row, "alias_token")
            for row in archive.alias_rows
            if cell(row, "channel_id") not in archive.registry
        ),
        "quarantine_alert": ratio >= thresholds["quarantine_alert_ratio_ppm"],
        "quarantine_ratio_ppm": ratio,
        "quarantine_reasons": {name: reasons[name] for name in REASONS if reasons[name]},
        "quarantined_count": quarantined,
        "unmatched_amendments": ledger.unmatched,
        "unreported_array_counts": {
            name: count for name, count in area_counts.items() if name not in area_roster
        },
        "voided_count": voided,
    }

    named = [("summary.json", summary), ("policy_audit.json", audit), ("data_quality.json", quality)]
    named += [("region_%s.json" % name, areas[name]) for name in area_roster]
    named += [("segment_%s.json" % name, classes[name]) for name in class_roster]
    return dict(named)


def reconcile(out_dir, expected):
    """Re-read the written reports and confirm they describe one consistent state."""
    reports = {}
    for name in sorted(expected):
        target = out_dir / name
        if not target.is_file():
            return "missing report %s" % name
        reports[name] = json.loads(target.read_text(encoding="utf-8"))
        if reports[name] != expected[name]:
            return "report %s disagrees with the archive it came from" % name

    summary = reports["summary.json"]
    quality = reports["data_quality.json"]
    areas = [reports[n] for n in sorted(expected) if n.startswith("region_")]
    classes = [reports[n] for n in sorted(expected) if n.startswith("segment_")]

    lifecycle = (
        summary["accepted_count"] + summary["voided_count"] + summary["quarantined_count"]
    )
    if lifecycle != summary["observed_count"]:
        return "lifecycle counts do not conserve the observed total"
    if quality["conservation_ok"] is not True:
        return "data quality report denies conservation"
    for key in ("observed_count", "accepted_count", "voided_count", "quarantined_count"):
        if quality[key] != summary[key]:
            return "count %s disagrees between summary and data quality" % key

    unreported = sum(quality["unreported_array_counts"].values())
    if sum(a["accepted_count"] for a in areas) + unreported != summary["accepted_count"]:
        return "area reports plus unreported areas do not cover the accepted samples"
    covered = set(entry["name"] for entry in classes)
    outside = sum(
        count for name, count in summary["segment_counts"].items() if name not in covered
    )
    if sum(c["accepted_count"] for c in classes) + outside != summary["accepted_count"]:
        return "class reports plus unreported classes do not cover the accepted samples"
    if outside == 0:
        for key in ("canonical_nano", "traced_nano", "drift_nano", "reported_nano"):
            if sum(c[key] for c in classes) != summary[key]:
                return "class totals disagree with the network total for %s" % key

    envelope = summary["budget_nano"]
    shares = (
        ("array_allocation_nano", sum(a["accepted_count"] for a in areas)),
        ("segment_allocation_nano", sum(c["accepted_count"] for c in classes)),
    )
    for share, weighted in shares:
        wanted = envelope if weighted else 0
        if sum(summary[share].values()) != wanted:
            return "%s does not reconcile to the budget" % share
    for area in areas:
        if area["allocation_nano"] != summary["array_allocation_nano"][area["name"]]:
            return "area %s carries a different share than the summary" % area["name"]
        if area["reported_nano"] != summary["array_totals"].get(area["name"], 0):
            return "area %s total disagrees with the summary" % area["name"]
    for entry in classes:
        if entry["allocation_nano"] != summary["segment_allocation_nano"][entry["name"]]:
            return "class %s carries a different share than the summary" % entry["name"]

    if outside == 0:
        merged = {}
        for entry in classes:
            for channel, value in entry["channel_totals"].items():
                merged[channel] = merged.get(channel, 0) + value
        if merged != summary["channel_totals"]:
            return "per instrument totals disagree between the class reports and the summary"
    return ""


def main(argv):
    if len(argv) == 1:
        root = Path(os.environ.get("APP_ROOT", "/app"))
        out_dir = root / "out"
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "derive_report.py"
        target.write_text(Path(__file__).read_text(encoding="utf-8"), encoding="utf-8")
        argv = [str(target), str(root / "data"), str(out_dir)]
    if len(argv) != 3:
        sys.stderr.write("usage: derive_report.py DATA_DIR OUT_DIR\n")
        return 2
    out_dir = Path(argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = derive(Path(argv[1]))
    for name, blob in outputs.items():
        (out_dir / name).write_text(
            json.dumps(blob, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    problem = reconcile(out_dir, outputs)
    if problem:
        sys.stderr.write("reconciliation failed: %s\n" % problem)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
