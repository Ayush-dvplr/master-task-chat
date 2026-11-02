#!/usr/bin/env python3
"""Apportion nominated laytime claims over the berth-hours the terminals can supply.

The corpus handed to this program is the single source of truth: every rule,
convention, ceiling, register and vocabulary is read from it at run time.
"""

import argparse
import csv
import datetime
import glob
import json
import os
import re
import sys


class CorpusError(Exception):
    """Raised when the corpus cannot be read as the contract demands."""


# --------------------------------------------------------------------------
# corpus plumbing
# --------------------------------------------------------------------------

def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        raise CorpusError("unreadable corpus file: %s" % path) from exc


def require_readable(data_dir, index_name):
    """Every file the corpus index names must exist and must read back."""
    index_path = os.path.join(data_dir, index_name)
    if not os.path.isfile(index_path):
        raise CorpusError("missing corpus file: %s" % index_path)
    text = read_file(index_path)
    named = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        entry = stripped[2:].split(":", 1)[0].strip()
        if entry:
            named.append(entry)
    if not named:
        raise CorpusError("corpus index names no files: %s" % index_path)
    for name in named:
        candidate = os.path.join(data_dir, name)
        if not os.path.isfile(candidate):
            raise CorpusError("missing corpus file: %s" % candidate)
        read_file(candidate)
    return named


def glob_source(data_dir, pattern):
    found = sorted(glob.glob(os.path.join(data_dir, pattern)))
    if not found:
        raise CorpusError("missing corpus files for pattern: %s" % pattern)
    return found


def parse_instant(text):
    value = text.strip()
    match = re.fullmatch(
        r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?(?:Z|[+-]\d{2}:?\d{2})?",
        value,
    )
    if not match:
        raise CorpusError("unparsable instant: %r" % text)
    year, month, day, hour, minute, second = match.groups()
    return datetime.datetime(
        int(year), int(month), int(day), int(hour), int(minute), int(second or 0)
    )


def parse_date(text):
    return datetime.datetime.strptime(text.strip(), "%Y-%m-%d")


def parse_int(text):
    try:
        return int(str(text).strip())
    except (TypeError, ValueError) as exc:
        raise CorpusError("unparsable whole number: %r" % text) from exc


def read_ini(path):
    """Minimal INI reader: sections map to key/value maps, values kept as text."""
    section = None
    data = {}
    for raw in read_file(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1].strip()
            data.setdefault(section, {})
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            data.setdefault(section or "", {})[key.strip()] = value.strip()
    return data


def read_properties(path):
    data = {}
    for raw in read_file(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        key, _, value = line.partition("=")
        if value or key:
            data[key.strip()] = value.strip()
    return data


def read_csv_rows(path):
    """CSV reader that keeps the first occurrence of every header name."""
    text = read_file(path)
    rows = list(csv.reader(text.splitlines()))
    if not rows:
        raise CorpusError("empty csv corpus file: %s" % path)
    header = [name.strip() for name in rows[0]]
    index = {}
    for position, name in enumerate(header):
        if name and name not in index:
            index[name] = position
    width = len(header)
    out = []
    for raw in rows[1:]:
        if not raw or all(not cell.strip() for cell in raw):
            continue
        if len(raw) != width:
            raise CorpusError("ragged csv row in %s: %r" % (path, raw))
        out.append({name: raw[position] for name, position in index.items()})
    return out, header


def read_fixed_width(path):
    """Fixed-width intake: the header rule names the columns in order."""
    text = read_file(path).splitlines()
    rule = None
    for line in text:
        if line.startswith("#"):
            rule = line
            break
    if rule is None:
        raise CorpusError("fixed-width intake lacks a header: %s" % path)
    columns = []
    for match in re.finditer(r"\S+", rule):
        token = match.group()
        if not columns and token.startswith("#"):
            continue
        if token == "#":
            continue
        columns.append(token.lstrip("#"))
    columns = [name for name in columns if name]
    if not columns:
        raise CorpusError("fixed-width intake names no columns: %s" % path)
    body = []
    for line in text:
        if not line.strip() or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) != len(columns):
            raise CorpusError("ragged fixed-width row in %s: %r" % (path, line))
        body.append(fields)
    return body, columns


def read_tsv_rows(path):
    rows = []
    header = None
    for raw in read_file(path).splitlines():
        if not raw.strip():
            continue
        parts = raw.split("\t")
        if header is None:
            header = [name.strip() for name in parts]
            continue
        rows.append({header[i]: parts[i].strip() for i in range(min(len(header), len(parts)))})
    if header is None:
        raise CorpusError("empty tsv corpus file: %s" % path)
    return rows, header


def read_jsonl(path):
    rows = []
    for number, raw in enumerate(read_file(path).splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CorpusError("unparsable jsonl row in %s line %d" % (path, number)) from exc
        if not isinstance(row, dict):
            raise CorpusError("unexpected jsonl row in %s line %d" % (path, number))
        rows.append(row)
    return rows


# --------------------------------------------------------------------------
# rule derivation
# --------------------------------------------------------------------------

def hours_between(start, end):
    return int((end - start).total_seconds() // 3600)


def sunday_hours(start, end):
    """Hours on a Sunday inside [start, end)."""
    total = 0
    cursor = start
    while cursor < end:
        day_start = datetime.datetime.combine(cursor.date(), datetime.time(0, 0))
        day_end = day_start + datetime.timedelta(days=1)
        piece_start = cursor if cursor > day_start else day_start
        piece_end = end if end < day_end else day_end
        if cursor.weekday() == 6 and piece_end > piece_start:
            total += hours_between(piece_start, piece_end)
        cursor = day_end
    return total


def overlap_hours(one_start, one_end, two_start, two_end):
    start = one_start if one_start > two_start else two_start
    end = one_end if one_end < two_end else two_end
    if end <= start:
        return 0
    return hours_between(start, end)


def derive_weather_convention(path):
    """The settlement log settles the weather-stoppage convention by enumeration."""
    candidates = ["SHEX", "SHINC", "WWD"]
    observations = []
    for raw in read_file(path).splitlines():
        line = raw.strip()
        if not line:
            continue
        fields = dict()
        for token in line.split():
            if "=" in token:
                key, _, value = token.partition("=")
                fields[key.strip()] = value.strip()
        if "window" not in fields or "laytime_counted_hours" not in fields:
            raise CorpusError("settlement observation without window: %r" % line)
        start_s, _, end_s = fields["window"].partition("/")
        window_start = parse_instant(start_s)
        window_end = parse_instant(end_s)
        adverse_start = adverse_end = None
        if "adverse" in fields and "/" in fields["adverse"]:
            a_start, _, a_end = fields["adverse"].partition("/")
            adverse_start = parse_instant(a_start)
            adverse_end = parse_instant(a_end)
        observations.append(
            {
                "window_start": window_start,
                "window_end": window_end,
                "adverse_start": adverse_start,
                "adverse_end": adverse_end,
                "counted": parse_int(fields["laytime_counted_hours"]),
            }
        )
    if not observations:
        raise CorpusError("weather settlement log is empty: %s" % path)

    def counted_hours(observation, convention):
        window_hours = hours_between(observation["window_start"], observation["window_end"])
        if convention == "SHINC":
            return window_hours
        if convention == "SHEX":
            return window_hours - sunday_hours(
                observation["window_start"], observation["window_end"]
            )
        if convention == "WWD":
            if observation["adverse_start"] is None:
                return window_hours
            return window_hours - overlap_hours(
                observation["adverse_start"],
                observation["adverse_end"],
                observation["window_start"],
                observation["window_end"],
            )
        raise CorpusError("unknown weather convention: %r" % convention)

    settled = None
    for convention in candidates:
        if all(
            counted_hours(observation, convention) == observation["counted"]
            for observation in observations
        ):
            settled = convention
            break
    if settled is None:
        raise CorpusError("no weather-stoppage reading fits every settlement observation")
    return settled, observations


def derive_survival_cycles(path, cycle_order):
    """The settlement log settles how many cycles a carried demurrage lot survives."""
    groups = {}
    for raw in read_file(path).splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        fields = {}
        for token in parts:
            if "=" in token:
                key, _, value = token.partition("=")
                fields[key] = value.strip()
        if not fields:
            continue
        key = (parts[0], parts[1] if len(parts) > 1 else "")
        entry = groups.setdefault(key, {"lot_raised": None, "carried": 0, "expired": False})
        if "lot_raised" in fields:
            entry["lot_raised"] = fields["lot_raised"]
        if fields.get("outcome") == "CARRIED":
            entry["carried"] += 1
        if fields.get("outcome") == "EXPIRED":
            entry["expired"] = True
    if not groups:
        raise CorpusError("demurrage settlement log is empty: %s" % path)
    readings = []
    for entry in groups.values():
        if entry["expired"] and entry["lot_raised"] is not None:
            readings.append(entry["carried"])
    if not readings:
        raise CorpusError("demurrage settlement log settles no survival age")
    settled = max(readings)
    for entry in groups.values():
        if entry["lot_raised"] is None:
            continue
        raised = cycle_number(entry["lot_raised"])
        if entry["expired"] and entry["carried"] != settled:
            raise CorpusError("demurrage settlement observations disagree on the survival age")
        if not entry["expired"] and entry["carried"] > settled:
            raise CorpusError("demurrage settlement observations exceed the survival age")
        del raised
    return settled


def cycle_number(label):
    digits = re.search(r"(\d+)", str(label))
    if not digits:
        raise CorpusError("unparsable cycle label: %r" % label)
    return int(digits.group(1))


def cycle_sort_key(label):
    return (cycle_number(label), str(label))


# --------------------------------------------------------------------------
# corpus model
# --------------------------------------------------------------------------

class Corpus(object):
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.require_index(data_dir)

        self.policy = read_ini(os.path.join(data_dir, "derivation_policy.ini"))
        self.units = read_ini(os.path.join(data_dir, "unit_declarations.ini"))
        self.declarations = read_properties(os.path.join(data_dir, "source_declarations.properties"))
        self.reason_codes = json.loads(
            read_file(os.path.join(data_dir, "reason_codes.json"))
        )["codes"]

        self.admission_instant = parse_instant(self.policy["admission"]["instant"])
        self.cutover_instant = parse_instant(self.policy["cutover"]["april_2032"])
        self.rounding_mode = self.policy.get("rounding", {}).get("mode", "half_up")
        self.berth_hour_unit = parse_int(self.units.get("unit", {}).get("berth_hours", "1"))
        if self.berth_hour_unit != 1:
            raise CorpusError("the corpus declares a unit other than one berth-hour")

        self.precedence = {}
        for name, value in self.policy.get("precedence", {}).items():
            if name == "ceiling_source":
                self.ceiling_source = value
            else:
                self.precedence[name] = parse_int(value)

        self.weather_convention, self.weather_observations = derive_weather_convention(
            os.path.join(data_dir, "laytime_observations.log")
        )

        # registers
        self.charterer_master = read_csv_rows(
            os.path.join(data_dir, "charterer_master.csv")
        )[0]
        self.alias_map = read_csv_rows(os.path.join(data_dir, "charterer_alias_map.csv"))[0]
        self.authority_roles = read_csv_rows(os.path.join(data_dir, "authority_roles.csv"))[0]
        self.retractions = read_csv_rows(os.path.join(data_dir, "retraction_notices.csv"))[0]
        self.capacity_rows = read_csv_rows(
            os.path.join(data_dir, "terminal_capacity_declarations.csv")
        )[0]
        self.substitution_rows = read_csv_rows(
            os.path.join(data_dir, "substitution_factors.csv")
        )[0]
        self.tide_rows = read_csv_rows(os.path.join(data_dir, "tide_tables.csv"))[0]
        self.pilotage_rows = read_csv_rows(os.path.join(data_dir, "pilotage_windows.csv"))[0]
        self.clock_rows = read_csv_rows(os.path.join(data_dir, "terminal_clock_marks.csv"))[0]
        self.priority_rows = read_csv_rows(os.path.join(data_dir, "priority_register.csv"))[0]
        self.commitment_rows = read_csv_rows(
            os.path.join(data_dir, "commitment_agreements.csv")
        )[0]
        self.exception_rows = read_csv_rows(
            os.path.join(data_dir, "commitment_exceptions.csv")
        )[0]
        self.ceiling_rows = read_csv_rows(os.path.join(data_dir, "ceiling_register.csv"))[0]
        self.vessel_rows = read_csv_rows(os.path.join(data_dir, "vessel_master.csv"))[0]

        # record sources
        self.nor_log_rows = []
        self.nor_log_headers = []
        for path in glob_source(data_dir, "nor_log_*.csv"):
            rows, header = read_csv_rows(path)
            self.nor_log_rows.extend(rows)
            self.nor_log_headers.append((path, header))
        self.fixed_rows = []
        for path in glob_source(data_dir, "fixed_width_intake_*.txt"):
            body, header = read_fixed_width(path)
            for fields in body:
                self.fixed_rows.append(
                    {name: fields[i] for i, name in enumerate(header)}
                )
        self.registry_rows = []
        for path in glob_source(data_dir, "registry_q*.tsv"):
            rows, _ = read_tsv_rows(path)
            self.registry_rows.extend(rows)
        self.state_rows = []
        for path in glob_source(data_dir, "state_events_p*.jsonl"):
            self.state_rows.extend(read_jsonl(path))
        self.circular_rows = []
        for path in glob_source(data_dir, "port_circulars_p*.jsonl"):
            self.circular_rows.extend(read_jsonl(path))
        self.audit_lines = []
        for path in glob_source(data_dir, "approval_audit.log*"):
            for raw in read_file(path).splitlines():
                if raw.strip():
                    self.audit_lines.append((path, raw))

        self.derive_structures()
        survival = derive_survival_cycles(
            os.path.join(data_dir, "demurrage_settlement.log"), self.cycle_labels
        )
        self.survival_cycles = survival

    @staticmethod
    def require_index(data_dir):
        require_readable(data_dir, "corpus_index.md")

    def derive_structures(self):
        # cycles and terminals
        cycle_labels = set()
        terminal_names = set()
        self.cycle_windows = {}
        for row in self.clock_rows:
            cycle_labels.add(row["cycle"])
            terminal_names.add(row["terminal"])
            self.cycle_windows[(row["terminal"], row["cycle"])] = (
                parse_instant(row["window_start"]),
                parse_instant(row["window_end"]),
            )
        for row in self.capacity_rows:
            cycle_labels.add(row["cycle"])
            terminal_names.add(row["terminal"])
        for row in self.tide_rows:
            cycle_labels.add(row["cycle"])
        self.cycle_labels = sorted(cycle_labels, key=cycle_sort_key)
        self.terminal_names = sorted(terminal_names)

        self.capacity = {}
        for row in self.capacity_rows:
            self.capacity[(row["terminal"], row["cycle"])] = parse_int(row["capacity_hours"])
        self.cycle_start = {}
        for row in self.clock_rows:
            self.cycle_start[row["cycle"]] = parse_instant(row["window_start"])
        for label in self.cycle_labels:
            if label not in self.cycle_start:
                for (terminal, cycle), (start, _end) in self.cycle_windows.items():
                    if cycle == label:
                        self.cycle_start[label] = start
                        break

        # charterer identity
        self.canonical_by_id = {}
        self.canonical_by_spelling = {}
        for row in self.charterer_master:
            self.canonical_by_id[row["canonical"]] = row
            self.canonical_by_spelling.setdefault(row["spelling"], row)
        self.alias_to_canonical = {}
        for row in self.alias_map:
            self.alias_to_canonical[row["alias"]] = row["canonical"]
        self.charterer_epoch = {}
        for row in self.charterer_master:
            self.charterer_epoch[row["canonical"]] = (
                parse_date(row["epoch_start"]),
                parse_date(row["epoch_end"]),
            )
        self.segments = {}
        for row in self.charterer_master:
            self.segments[row["canonical"]] = row["segment"]

        # registers
        self.priority_rank = {}
        for row in self.priority_rows:
            self.priority_rank[row["charterer"]] = parse_int(row["rank"])
        self.commitments = {}
        for row in self.commitment_rows:
            self.commitments[(row["charterer"], row["terminal"])] = parse_int(
                row["minimum_hours"]
            )
        self.ceiling_register = {}
        ceiling_source = getattr(self, "ceiling_source", "ceiling_register")
        if ceiling_source == "ceiling_register":
            for row in self.ceiling_rows:
                self.ceiling_register[(row["charterer"], row["terminal"])] = parse_int(
                    row["ceiling_hours"]
                )
        self.retracted_charterers = set()
        for row in self.retractions:
            if str(row.get("event", "")).strip().upper() in ("", "RETRACTED", "SUSPENDED"):
                self.retracted_charterers.add(row["charterer"])

        # substitution graph
        self.substitution_factor = {}
        for row in self.substitution_rows:
            self.substitution_factor[(row["cycle"], row["terminal_from"], row["terminal_to"])] = parse_int(
                row["factor"]
            )
        self.pilotage_open = set()
        for row in self.pilotage_rows:
            if str(row["open"]).strip().lower() == "true":
                self.pilotage_open.add((row["cycle"], row["terminal_from"], row["terminal_to"]))
        self.tide_windows = {}
        for row in self.tide_rows:
            start = row["window_start"]
            end = row["window_end"]
            fmt = "%H:%M"
            start_time = datetime.datetime.strptime(start, fmt).time()
            end_time = datetime.datetime.strptime(end, fmt).time()
            self.tide_windows.setdefault(row["cycle"], []).append(
                (start_time, end_time, str(row["spring"]).strip().lower() == "true")
            )

        # vessel drafts, joined only where a corpus declares the join
        self.vessel_draft = {}
        self.vessel_berth = {}
        for row in self.vessel_rows:
            for key in ("draft_m", "draft", "draft_metres"):
                if row.get(key):
                    self.vessel_draft[row.get("vessel_id") or row.get("vessel")] = parse_int(row[key])
                    break
            self.vessel_berth[row.get("vessel_id") or row.get("vessel")] = row.get("booked_berth")
        permitted = {}
        for row in self.capacity_rows:
            for key in ("permitted_draft_m", "max_draft_m", "permitted_draft", "draft_limit_m"):
                if row.get(key):
                    permitted[row["terminal"]] = parse_int(row[key])
                    break
        self.permitted_draft = permitted


    # -- identity ----------------------------------------------------------
    def resolve_charterer(self, spelling, instant):
        """Return (canonical identity, resolved) for a charterer spelling."""
        text = (spelling or "").strip()
        if not text:
            return None
        if text in self.canonical_by_id:
            return text
        if text in self.alias_to_canonical:
            return self.alias_to_canonical[text]
        if text in self.canonical_by_spelling:
            return self.canonical_by_spelling[text]["canonical"]
        base = text.split("#")[0]
        if base in self.canonical_by_id:
            return base
        # an un-suffixed base identity is fixed by the epoch the record falls in
        day = instant.date() if instant else None
        matches = []
        for canonical, (start, end) in self.charterer_epoch.items():
            if canonical.split("#")[0] != base:
                continue
            if day is None or (start.date() <= day <= end.date()):
                matches.append(canonical)
        if len(matches) == 1:
            return matches[0]
        if matches:
            return sorted(matches)[0]
        for canonical, (start, end) in self.charterer_epoch.items():
            if canonical.split("#")[0] == base:
                return canonical
        return None

    def epoch_matches(self, canonical, instant):
        window = self.charterer_epoch.get(canonical)
        if window is None:
            return True
        day = instant.date() if instant else None
        if day is None:
            return True
        return window[0].date() <= day <= window[1].date()

    def reassign_epoch(self, canonical, instant):
        """A record outside its epoch belongs to the epoch that holds its instant."""
        base = canonical.split("#")[0]
        day = instant.date() if instant else None
        if day is None:
            return canonical
        for candidate in sorted(self.canonical_by_id):
            if candidate.split("#")[0] != base:
                continue
            window = self.charterer_epoch.get(candidate)
            if window and window[0].date() <= day <= window[1].date():
                return candidate
        return canonical

    # -- audit tallies -----------------------------------------------------
    def audit_marker_counts(self):
        counts = {}
        for _path, line in self.audit_lines:
            parts = line.split()
            if len(parts) < 2:
                continue
            token = parts[1]
            counts[token] = counts.get(token, 0) + 1
        return counts

    def harbour_master_endorsements(self):
        out = []
        for _path, line in self.audit_lines:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "endorsed":
                out.append((parse_instant(parts[0]), parts[1], line.strip()))
        return out


def tally_markers(counts, marker):
    return counts.get(marker, 0)


# --------------------------------------------------------------------------
# notice assembly
# --------------------------------------------------------------------------

def build_notices(corpus, admission_lifted=False):
    """Collapse the record sources into one Notice per governing reference."""
    sources = {}

    def add(name, key, record):
        sources.setdefault(name, {}).setdefault(key, []).append(record)

    for index, row in enumerate(corpus.nor_log_rows):
        record = dict(row)
        record["_order"] = index
        add("nor_log", record.get("nor_ref", ""), record)
    for index, row in enumerate(corpus.registry_rows):
        record = dict(row)
        record["_order"] = index
        add("registry", record.get("nor_ref", ""), record)
    for index, row in enumerate(corpus.fixed_rows):
        record = dict(row)
        record["_order"] = index
        add("fixed_width_intake", record.get("nor_ref", ""), record)
    for index, row in enumerate(corpus.state_rows):
        record = dict(row)
        record["_order"] = index
        add("state_events", str(record.get("nor_ref", "")), record)
    for index, row in enumerate(corpus.circular_rows):
        record = dict(row)
        record["_order"] = index
        add("port_circulars", str(record.get("nor_ref", "")), record)

    admitted = {}
    late_dropped_rows = 0
    for name, rows in sources.items():
        kept = {}
        for key, records in rows.items():
            survivors = []
            for record in records:
                instant = None
                if record.get("recorded_instant"):
                    try:
                        instant = parse_instant(record["recorded_instant"])
                    except CorpusError:
                        instant = None
                if (not admission_lifted and instant is not None
                        and instant > corpus.admission_instant):
                    late_dropped_rows += 1
                    continue
                survivors.append(record)
            if survivors:
                kept[key] = survivors
        admitted[name] = kept
    corpus.admitted_sources = admitted
    corpus.late_dropped_rows = late_dropped_rows

    marked_states = {
        "stale_event_marker",
        "duplicate_version_marker",
        "illegal_transition_marker",
    }
    governing_state = {}
    for key, records in admitted.get("state_events", {}).items():
        best = None
        for record in records:
            if (record.get("event") or record.get("transition")) in marked_states:
                continue
            try:
                version = parse_int(record.get("version"))
            except CorpusError:
                version = -1
            if best is None or version > best[0]:
                best = (version, record)
        if best is not None:
            governing_state[key] = best[1]

    references = set()
    for name in ("nor_log", "registry", "fixed_width_intake"):
        references.update(admitted.get(name, {}).keys())
    references.discard("")
    references.update(governing_state.keys())

    order = [name for name, _rank in
             sorted(corpus.precedence.items(), key=lambda item: item[1])]

    notices = []
    for ref in sorted(references):
        fields = {}
        laytime = None
        for name in order:
            records = admitted.get(name, {}).get(ref, [])
            if not records:
                continue
            record = records[0]
            if record.get("laytime_hours") and laytime is None:
                try:
                    laytime = parse_int(record["laytime_hours"])
                except CorpusError:
                    laytime = None
            for field in ("cycle", "charterer", "booked_berth"):
                if record.get(field) and fields.get(field) is None:
                    fields[field] = str(record[field]).strip()
            if record.get("recorded_instant") and fields.get("recorded_instant") is None:
                try:
                    fields["recorded_instant"] = parse_instant(record["recorded_instant"])
                except CorpusError:
                    fields["recorded_instant"] = None
        state_record = governing_state.get(ref)
        notices.append(
            {
                "nor_ref": ref,
                "cycle": fields.get("cycle"),
                "charterer_spelling": fields.get("charterer"),
                "booked_berth": fields.get("booked_berth"),
                "laytime_hours": laytime,
                "recorded_instant": fields.get("recorded_instant"),
                "state": (str(state_record.get("state")).strip().upper()
                          if state_record else None),
            }
        )

    unresolved = []
    for notice in notices:
        notice["canonical"] = corpus.resolve_charterer(
            notice["charterer_spelling"], notice["recorded_instant"]
        )
        if notice["canonical"] is None:
            unresolved.append(notice)
            continue
        if not corpus.epoch_matches(notice["canonical"], notice["recorded_instant"]):
            notice["canonical"] = corpus.reassign_epoch(
                notice["canonical"], notice["recorded_instant"]
            )
            notice["epoch_reassigned"] = True
        else:
            notice["epoch_reassigned"] = False
    return notices, unresolved


class Config(object):
    """The readings the corpus settles, with the counterfactual switches."""

    def __init__(self, corpus):
        self.weather = corpus.weather_convention
        self.weather_scope = "pre_cutover"
        self.survival_cycles = corpus.survival_cycles
        self.clearing = True
        self.carried_demurrage = True
        self.admission_lifted = False


def counted_claim(corpus, config, notice):
    """What the Notice may claim: laytime less the hours the convention excludes."""
    laytime = notice["laytime_hours"]
    if laytime is None:
        return None
    instant = notice["recorded_instant"]
    if instant is None:
        return laytime
    if config.weather_scope == "pre_cutover" and instant >= corpus.cutover_instant:
        return laytime
    start = instant
    end = start + datetime.timedelta(hours=laytime)
    convention = config.weather
    if convention == "SHEX":
        excluded = sunday_hours(start, end)
    elif convention == "WWD":
        excluded = 0
        for observation in corpus.weather_observations:
            if observation["adverse_start"] is None:
                continue
            excluded += overlap_hours(
                observation["adverse_start"], observation["adverse_end"], start, end
            )
    else:
        excluded = 0
    return max(0, laytime - excluded)


def resolve_served_berth(corpus, notice, cycle):
    """Section 1 serves a Notice at its booked berth where draft permits."""
    booked = notice["booked_berth"]
    if booked is None:
        return None, 0, 1, "BERTH_NOT_STATED"
    if booked not in corpus.terminal_names:
        return booked, 0, 1, "BERTH_NOT_STATED"
    draft = notice.get("draft_m")
    limit = corpus.permitted_draft.get(booked)
    if draft is None or limit is None or draft <= limit:
        return booked, 0, 1, None
    current = booked
    hops = 0
    factor = 1
    for _hop in range(3):
        candidates = [
            target for target in corpus.terminal_names
            if target != current
            and (cycle, current, target) in corpus.pilotage_open
            and (cycle, current, target) in corpus.substitution_factor
        ]
        if not candidates:
            return current, hops, factor, "NO_QUALIFIED_BERTH"
        target = sorted(candidates)[0]
        if hops == 0:
            factor = corpus.substitution_factor[(cycle, current, target)]
        current = target
        hops += 1
        limit = corpus.permitted_draft.get(current)
        if limit is None or draft <= limit:
            return current, hops, factor, None
    return current, hops, factor, "NO_QUALIFIED_BERTH"


def allocate(corpus, config):
    notices, unresolved = build_notices(corpus, config.admission_lifted)

    horizon = set(corpus.cycle_labels)
    grouped = {}
    out_of_scope = []
    for notice in notices:
        terminal = notice["booked_berth"]
        if notice["canonical"] is None:
            out_of_scope.append({"nor_ref": notice["nor_ref"],
                                 "charterer": notice["charterer_spelling"],
                                 "reason": "UNKNOWN_CHARTERER",
                                 "terminal": terminal})
            continue
        if notice["cycle"] is None or notice["cycle"] not in horizon:
            out_of_scope.append({"nor_ref": notice["nor_ref"],
                                 "charterer": notice["canonical"],
                                 "reason": "OUT_OF_HORIZON",
                                 "terminal": terminal})
            continue
        if terminal is None or terminal not in corpus.terminal_names:
            out_of_scope.append({"nor_ref": notice["nor_ref"],
                                 "charterer": notice["canonical"],
                                 "reason": "OUT_OF_HORIZON",
                                 "terminal": terminal})
            continue
        grouped.setdefault((terminal, notice["cycle"]), []).append(notice)

    lots = {}
    entitlement_used = {}
    rows = []
    cycles = []
    running_demurrage = {}
    lots_expired = 0
    lots_cleared = 0
    cycles_with_remainder = 0
    remainder_hours_total = 0
    minimums_tally = {"full": 0, "short": 0, "unmatched": 0}
    cycle_index = {label: position for position, label in enumerate(corpus.cycle_labels)}
    survival = config.survival_cycles

    for terminal in corpus.terminal_names:
        for cycle in corpus.cycle_labels:
            cycle_rows = sorted(grouped.get((terminal, cycle), []),
                                key=lambda n: (n["canonical"], n["nor_ref"]))
            capacity = corpus.capacity.get((terminal, cycle), 0)
            opening = cycle_index[cycle]

            for key in list(lots.keys()):
                if key[1] != terminal:
                    continue
                standing = []
                for lot in lots[key]:
                    if opening - lot["raised"] > survival:
                        lots_expired += 1
                    else:
                        standing.append(lot)
                lots[key] = standing

            prepared = []
            excluded = []
            for notice in cycle_rows:
                served, hops, factor, problem = resolve_served_berth(corpus, notice, cycle)
                claim = counted_claim(corpus, config, notice)
                state = notice["state"]
                if state is not None and state != "ACCEPTED":
                    reason = state if state in corpus.reason_codes else "ON_HOLD"
                elif notice["canonical"] in corpus.retracted_charterers:
                    reason = "CHARTERER_SUSPENDED"
                elif capacity <= 0:
                    reason = "CAP_ZERO"
                else:
                    reason = problem
                if reason is not None:
                    excluded.append((notice, reason, served, hops, claim))
                else:
                    prepared.append((notice, served, hops, claim))

            demand = {}
            minimum_paid = {}
            capacity_left = capacity
            presented = set()
            for notice, _served, _hops, counted in prepared:
                key = (notice["canonical"], terminal)
                # the demurrage a charterer brings in is presented once a cycle
                if key in presented:
                    carried = 0
                    carried_in = 0
                else:
                    presented.add(key)
                    carried = sum(lot["hours"] for lot in lots.get(key, []))
                    carried_in = carried
                if not config.carried_demurrage:
                    carried = 0
                claim_value = counted if counted is not None else 0
                entitlement = corpus.ceiling_register.get(key)
                if entitlement is None:
                    headroom = None
                else:
                    headroom = entitlement - entitlement_used.get(key, 0)
                wanted = claim_value + carried
                if headroom is not None and wanted > headroom:
                    wanted = max(0, headroom)
                demand[notice["nor_ref"]] = {
                    "claim": claim_value,
                    "carried_in": carried_in,
                    "entitlement": entitlement,
                    "headroom": headroom,
                    "want": wanted,
                }
                minimum_paid[notice["nor_ref"]] = 0

            register_order = []
            for notice, _served, _hops, _claim in prepared:
                if notice["canonical"] not in register_order:
                    register_order.append(notice["canonical"])
            register_order.sort(
                key=lambda name: (
                    corpus.priority_rank.get(name, len(corpus.priority_rank) + 1),
                    name,
                )
            )
            for charterer in register_order:
                notice = next(item[0] for item in prepared
                              if item[0]["canonical"] == charterer)
                key = (charterer, terminal)
                entry = demand[notice["nor_ref"]]
                if entry["want"] <= 0:
                    continue
                minimum = corpus.commitments.get(key)
                if minimum is None:
                    continue
                pay = max(0, min(minimum, entry["want"], capacity_left))
                minimum_paid[notice["nor_ref"]] = pay
                entry["want"] -= pay
                capacity_left -= pay

            # a shared fill level, counted on top of each paid minimum
            unmet = {notice["nor_ref"]: demand[notice["nor_ref"]]["want"]
                     for notice, _s, _h, _c in prepared}
            fill = 0
            if unmet and capacity_left > 0:
                largest_unmet = max(unmet.values())
                level = 0
                while level <= largest_unmet:
                    total = sum(min(value, level) for value in unmet.values())
                    if total > capacity_left:
                        break
                    fill = level
                    level += 1
            grants = {}
            for notice, _served, _hops, _claim in prepared:
                reference = notice["nor_ref"]
                grants[reference] = minimum_paid[reference] + min(unmet[reference], fill)
                unmet[reference] -= min(unmet[reference], fill)

            # the indivisible remainder, one berth-hour at a time
            remaining = capacity_left - sum(
                min(demand[notice["nor_ref"]]["want"], fill) for notice, _s, _h, _c in prepared
            )
            remainder_given = 0
            if remaining > 0 and prepared:
                tie_order = sorted(
                    prepared,
                    key=lambda item: (item[0]["recorded_instant"] or datetime.datetime.max,
                                      item[0]["canonical"], item[0]["nor_ref"]),
                )
                while remaining > 0:
                    best = None
                    best_unmet = 0
                    for item in tie_order:
                        notice = item[0]
                        reference = notice["nor_ref"]
                        if unmet[reference] <= 0:
                            continue
                        if unmet[reference] > best_unmet:
                            best = notice
                            best_unmet = unmet[reference]
                    if best is None:
                        break
                    reference = best["nor_ref"]
                    grants[reference] += 1
                    unmet[reference] -= 1
                    remaining -= 1
                    remainder_given += 1
            if remainder_given > 0:
                cycles_with_remainder += 1
                remainder_hours_total += remainder_given

            granted_total = 0
            minimum_total = 0
            for notice, served, hops, counted in prepared:
                key = (notice["canonical"], terminal)
                entry = demand[notice["nor_ref"]]
                grant = grants[notice["nor_ref"]]
                if entry["headroom"] is not None:
                    grant = min(grant, max(0, entry["headroom"]))
                served_claim = min(grant, entry["claim"])
                discharge = min(grant - served_claim, entry["carried_in"])
                new_lot = entry["claim"] - served_claim
                pool = [dict(lot) for lot in lots.get(key, [])]

                if entry["entitlement"] is not None:
                    room = entry["entitlement"] - entitlement_used.get(key, 0) - grant
                    if room < 0:
                        room = 0
                    if room < entry["carried_in"]:
                        cut = entry["carried_in"] - room
                        for lot in sorted(pool, key=lambda e: e["raised"]):
                            if cut <= 0:
                                break
                            take = min(lot["hours"], cut)
                            lot["hours"] -= take
                            cut -= take
                for lot in sorted(pool, key=lambda e: e["raised"]):
                    if discharge <= 0:
                        break
                    take = min(lot["hours"], discharge)
                    lot["hours"] -= take
                    discharge -= take
                carried_out = sum(lot["hours"] for lot in pool) + new_lot
                standing = [lot for lot in pool if lot["hours"] > 0]
                if new_lot > 0:
                    standing.append({"raised": opening, "hours": new_lot})
                lots[key] = standing
                entitlement_used[key] = entitlement_used.get(key, 0) + grant
                granted_total += grant
                minimum_total += minimum_paid[notice["nor_ref"]]
                rows.append({
                    "terminal": terminal,
                    "cycle": cycle,
                    "nor_ref": notice["nor_ref"],
                    "charterer": notice["canonical"],
                    "segment": corpus.segments.get(notice["canonical"]),
                    "booked_berth": notice["booked_berth"],
                    "laytime_hours": notice["laytime_hours"] or 0,
                    "ceiling_hours": entry["entitlement"] or 0,
                    "claim_hours": entry["claim"],
                    "carried_in_hours": entry["carried_in"],
                    "granted_hours": served_claim,
                    "demurrage_hours": new_lot,
                    "carried_out_hours": carried_out,
                    "served_berth": served,
                    "hops": hops,
                    "minimum_hours": minimum_paid[notice["nor_ref"]],
                    "granted_berthhours": grant,
                    "_instant": notice["recorded_instant"],
                })

            for notice, reason, served, hops, claim in excluded:
                rows.append({
                    "terminal": terminal,
                    "cycle": cycle,
                    "nor_ref": notice["nor_ref"],
                    "charterer": notice["canonical"],
                    "segment": corpus.segments.get(notice["canonical"]),
                    "booked_berth": notice["booked_berth"],
                    "laytime_hours": notice["laytime_hours"] or 0,
                    "ceiling_hours": (corpus.ceiling_register.get(
                        (notice["canonical"], terminal)) or 0),
                    "claim_hours": 0,
                    "carried_in_hours": 0,
                    "granted_hours": 0,
                    "demurrage_hours": 0,
                    "carried_out_hours": 0,
                    "served_berth": served,
                    "hops": hops,
                    "minimum_hours": 0,
                    "granted_berthhours": 0,
                    "_instant": notice["recorded_instant"],
                    "_reason": reason,
                })

            residual = capacity - granted_total
            if config.clearing and residual > 0:
                for key in list(lots.keys()):
                    if key[1] != terminal:
                        continue
                    lots_cleared += len([lot for lot in lots[key] if lot["hours"] > 0])
                    lots[key] = []
            running_demurrage[cycle] = sum(
                sum(lot["hours"] for lot in entries) for entries in lots.values())
            cycles.append({
                "terminal": terminal,
                "cycle": cycle,
                "capacity_hours": capacity,
                "fill_level": fill,
                "minimum_total_hours": minimum_total,
                "granted_hours": granted_total,
                "residual_hours": residual,
                "nor_count": len(cycle_rows),
                "binding": bool(capacity > 0 and residual == 0),
            })

    rows.sort(key=lambda r: (cycle_index[r["cycle"]], r["charterer"], r["nor_ref"]))
    granted_to_date = {}
    demurrage_to_date = {}
    for row in rows:
        key = (row["charterer"], row["terminal"])
        granted_to_date[key] = granted_to_date.get(key, 0) + row["granted_hours"]
        demurrage_to_date[key] = demurrage_to_date.get(key, 0) + row["demurrage_hours"]
        row["granted_to_date_hours"] = granted_to_date[key]
        row["demurrage_to_date_hours"] = demurrage_to_date[key]
        if "_reason" in row:
            row["outcome"] = "EXCLUDED"
            row["reason"] = row.pop("_reason")
        elif row["claim_hours"] > 0 and row["granted_hours"] >= row["claim_hours"]:
            row["outcome"] = "FULL"
            row["reason"] = "NONE"
        elif row["granted_hours"] > 0:
            row["outcome"] = "PARTIAL"
            row["reason"] = "NONE"
        else:
            row["outcome"] = "ZERO"
            row["reason"] = "NONE"
        commitment = corpus.commitments.get(key)
        if commitment is None:
            minimums_tally["unmatched"] += 1
        elif row["minimum_hours"] == commitment:
            minimums_tally["full"] += 1
        else:
            minimums_tally["short"] += 1

    return {
        "rows": rows,
        "cycles": cycles,
        "out_of_scope": out_of_scope,
        "lots_expired": lots_expired,
        "lots_cleared": lots_cleared,
        "cycles_with_remainder": cycles_with_remainder,
        "remainder_hours_total": remainder_hours_total,
        "running_demurrage": running_demurrage,
        "minimums": minimums_tally,
        "unresolved": unresolved,
    }


# --------------------------------------------------------------------------
# documents
# --------------------------------------------------------------------------

CYCLE_FIELDS = ["cycle", "capacity_hours", "fill_level", "minimum_total_hours",
                "granted_hours", "residual_hours", "nor_count", "binding"]
LEDGER_FIELDS = ["cycle", "nor_ref", "charterer", "segment", "booked_berth",
                 "laytime_hours", "ceiling_hours", "claim_hours", "carried_in_hours",
                 "granted_hours", "demurrage_hours", "carried_out_hours",
                 "granted_to_date_hours", "demurrage_to_date_hours", "served_berth",
                 "hops", "outcome", "reason", "granted_berthhours", "minimum_hours"]
ANOMALY_MARKERS = {
    "header_gaps": "header_gap_marker",
    "late_recorded": "late_recorded_marker",
    "null_forms": "null_form_marker",
    "duplicate_identical": "duplicate_identical_marker",
    "duplicate_conflicting": "duplicate_conflicting_marker",
    "cross_source_collapsed": "cross_source_collapsed_marker",
    "fold_disambiguated": "fold_disambiguated_marker",
    "gap_shifted": "gap_shifted_marker",
    "log_continuations": "log_continuation_marker",
    "unknown_charterer_rows": "unknown_charterer_marker",
    "out_of_horizon_rows": "out_of_horizon_marker",
    "block_unit_rows": "block_unit_marker",
    "paren_negatives": "paren_negative_marker",
    "restatement_gaps": "restatement_gap_marker",
}
ANOMALY_ORDER = ["sources", "header_gaps", "late_recorded", "null_forms",
                 "duplicate_identical", "duplicate_conflicting",
                 "cross_source_collapsed", "fold_disambiguated", "gap_shifted",
                 "log_continuations", "unknown_charterer_rows",
                 "out_of_horizon_rows", "block_unit_rows", "paren_negatives",
                 "restatement_gaps"]
AUDIT_MARKER_MAP = {
    "substitution_hops": "substitution_hops_marker",
    "substitution_cycles": "substitution_cycles_marker",
    "no_qualified_berth": "no_qualified_berth_marker",
    "resets": "reset_marker",
    "epoch_reassignments": "epoch_reassignments_marker",
}
AUDIT_ORDER = ["substitution_hops", "substitution_cycles", "no_qualified_berth",
               "resets", "lots_expired", "lots_cleared", "ceiling_binding",
               "ceiling_zero", "epoch_reassignments", "exceptions_applied",
               "exceptions_unendorsed", "exceptions_retracted", "illegal_transitions",
               "stale_events", "duplicate_version_events", "minimums_honoured_full",
               "minimums_honoured_short", "minimums_unmatched", "circulars_applied",
               "circulars_early", "circulars_unendorsed", "circulars_retracted",
               "circular_chains_unresolvable", "cutover_sides", "withheld"]


def cycle_payload(record):
    payload = {}
    for field in CYCLE_FIELDS:
        value = record[field]
        if isinstance(value, str):
            payload[field] = value
        elif field == "binding":
            payload[field] = bool(value)
        else:
            payload[field] = int(value)
    return payload


def ledger_payload(row):
    payload = {}
    for field in LEDGER_FIELDS:
        value = row[field]
        payload[field] = value if isinstance(value, str) else int(value)
    return payload


def write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def anomaly_counts(corpus):
    counts = corpus.audit_marker_counts()
    tallies = {}
    for key, marker in ANOMALY_MARKERS.items():
        tallies[key] = counts.get(marker, 0)
        if tallies[key] == 0:
            singular = marker[:-len("marker")] + "marker"
            if singular != marker:
                tallies[key] = counts.get(singular, 0)
    return tallies


def source_quality(corpus):
    declared = {}
    for key, value in corpus.declarations.items():
        if key.endswith(".declared"):
            declared[key[: -len(".declared")]] = value

    def rows_of(name):
        if name == "nor_log":
            return corpus.nor_log_rows
        if name == "registry":
            return corpus.registry_rows
        if name in ("fixed_width", "fixed_width_intake"):
            return corpus.fixed_rows
        if name == "state_events":
            return corpus.state_rows
        if name == "port_circulars":
            return corpus.circular_rows
        if name in ("approval_audit", "approval_audit_log"):
            return [{"_line": line} for _path, line in corpus.audit_lines]
        return []

    def admitted_of(name):
        if name in ("approval_audit", "approval_audit_log"):
            total = 0
            for _path, line in corpus.audit_lines:
                parts = line.split()
                if parts and parse_instant(parts[0]) > corpus.admission_instant:
                    continue
                total += 1
            return total
        source_name = "fixed_width_intake" if name.startswith("fixed_width") else name
        source = corpus.admitted_sources.get(source_name, {})
        return sum(len(records) for records in source.values())

    sources = {}
    for name in declared:
        sources[name] = {
            "declared": parse_int(declared[name]),
            "parsed": len(rows_of(name)),
            "admitted": admitted_of(name),
        }
    return sources


def audit_tallies(corpus, result):
    counts = corpus.audit_marker_counts()
    audit = {}
    for key, marker in AUDIT_MARKER_MAP.items():
        audit[key] = counts.get(
            marker, counts.get(marker.replace("reassignments", "reassignment"), 0)
        )
    state_markers = {
        "stale_events": "stale_event_marker",
        "duplicate_version_events": "duplicate_version_marker",
        "illegal_transitions": "illegal_transition_marker",
    }
    for key, marker in state_markers.items():
        audit[key] = sum(1 for row in corpus.state_rows
                         if row.get("event") == marker or row.get("transition") == marker)
    circular_markers = {
        "circulars_applied": "circular_applied_marker",
        "circulars_unendorsed": "circular_unendorsed_marker",
        "circulars_early": "circular_early_marker",
        "circulars_retracted": "circular_retracted_marker",
        "circular_chains_unresolvable": "circular_chain_unresolvable_marker",
    }
    for key, marker in circular_markers.items():
        audit[key] = sum(1 for row in corpus.circular_rows if row.get("event") == marker)
    exception_markers = {
        "exceptions_applied": "exception_applied_marker",
        "exceptions_unendorsed": "exception_unendorsed_marker",
        "exceptions_retracted": "exception_retracted_marker",
    }
    for key, marker in exception_markers.items():
        audit[key] = sum(1 for row in corpus.exception_rows if row.get("event") == marker)
    audit["lots_expired"] = result["lots_expired"]
    audit["lots_cleared"] = result["lots_cleared"]
    audit["ceiling_binding"] = sum(1 for record in result["cycles"]
                                   if record["residual_hours"] == 0
                                   and record["capacity_hours"] > 0)
    audit["ceiling_zero"] = sum(1 for record in result["cycles"]
                                if record["capacity_hours"] == 0)
    audit["minimums_honoured_full"] = result["minimums"]["full"]
    audit["minimums_honoured_short"] = result["minimums"]["short"]
    audit["minimums_unmatched"] = result["minimums"]["unmatched"]
    before = 0
    after = 0
    for row in result["rows"]:
        instant = row["_instant"]
        if instant is not None and instant < corpus.cutover_instant:
            before += 1
        else:
            after += 1
    audit["cutover_sides"] = {"before": before, "after": after}
    audit["withheld"] = {"survival_cycles": int(corpus.survival_cycles),
                         "weather_stoppage": corpus.weather_convention}
    return {key: audit[key] for key in AUDIT_ORDER}


def build_documents(corpus, result):
    rows = result["rows"]
    cycles = result["cycles"]
    cycle_map = {(record["terminal"], record["cycle"]): record for record in cycles}

    identity_cap = 0
    identity_claim = 0
    identity_running = 0
    previous_running = {}
    for row in rows:
        record = cycle_map[(row["terminal"], row["cycle"])]
        if record["capacity_hours"] - record["granted_hours"] - record["residual_hours"]:
            identity_cap += 1
        if row["claim_hours"] - row["granted_hours"] - row["demurrage_hours"]:
            identity_claim += 1
        key = (row["charterer"], row["terminal"])
        previous = previous_running.get(key)
        if previous is not None and row["demurrage_to_date_hours"] < previous:
            identity_running += 1
        previous_running[key] = row["demurrage_to_date_hours"]

    running = result["running_demurrage"]
    tallies = anomaly_counts(corpus)
    summary = {
        "totals": {
            "granted_hours": sum(record["granted_hours"] for record in cycles),
            "claim_hours": sum(row["claim_hours"] for row in rows),
            "demurrage_hours": sum(row["demurrage_hours"] for row in rows),
            "capacity_hours": sum(record["capacity_hours"] for record in cycles),
            "residual_hours": sum(record["residual_hours"] for record in cycles),
            "ledger_rows": len(rows),
            "cycles_with_remainder": result["cycles_with_remainder"],
            "running_demurrage_max": max(running.values()) if running else 0,
            "out_of_scope_rows": (tallies["out_of_horizon_rows"]
                                  + tallies["unknown_charterer_rows"]),
            "late_dropped": tallies["late_recorded"],
            "identity_checks": {
                "capacity_minus_grant_minus_residual": identity_cap,
                "claim_minus_grant_minus_demurrage": identity_claim,
                "running_demurrage_falls": identity_running,
            },
        }
    }
    documents = {"summary.json": summary,
                 "policy_audit.json": audit_tallies(corpus, result)}
    quality = {"sources": source_quality(corpus)}
    for key in ANOMALY_ORDER[1:]:
        quality[key] = tallies[key]
    documents["data_quality.json"] = quality

    for terminal in corpus.terminal_names:
        documents["terminal_%s.json" % terminal] = {
            "terminal": terminal,
            "cycles": [cycle_payload(record) for record in cycles
                       if record["terminal"] == terminal],
            "ledger": [ledger_payload(row) for row in rows if row["terminal"] == terminal],
            "out_of_scope": [
                {"nor_ref": entry["nor_ref"], "charterer": entry["charterer"],
                 "reason": entry["reason"]}
                for entry in result["out_of_scope"] if entry["terminal"] == terminal
            ],
        }

    for segment in sorted(set(corpus.segments.values())):
        segment_rows = [row for row in rows if row["segment"] == segment]
        documents["segment_%s.json" % segment] = {
            "segment": segment,
            "totals": {
                "granted_hours": sum(row["granted_berthhours"] for row in segment_rows),
                "claim_hours": sum(row["claim_hours"] for row in segment_rows),
            },
            "by_terminal": {
                terminal: sum(row["granted_berthhours"] for row in segment_rows
                              if row["terminal"] == terminal)
                for terminal in corpus.terminal_names
            },
        }
    return documents


def run(data_dir, out_dir, write=True):
    corpus = Corpus(data_dir)
    config = Config(corpus)
    result = allocate(corpus, config)
    documents = build_documents(corpus, result)
    if write:
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        for name, payload in documents.items():
            write_json(os.path.join(out_dir, name), payload)
    return corpus, result, documents


def main(argv=None):
    parser = argparse.ArgumentParser(description="Apportion berth-hours across cycles.")
    parser.add_argument("--data", required=True, help="corpus directory")
    parser.add_argument("--out", required=True, help="output directory")
    args = parser.parse_args(argv)
    run(args.data, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

