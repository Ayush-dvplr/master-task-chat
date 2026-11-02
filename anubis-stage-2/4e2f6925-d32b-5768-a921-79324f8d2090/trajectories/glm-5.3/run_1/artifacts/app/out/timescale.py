#!/usr/bin/env python3
"""Recompute one publication interval of the array timing network from its working papers.

    python3 timescale.py [--data <input directory>] [--out <output directory>]

Every identifier, count, control value, threshold and vocabulary member the
publication uses is read from the directory the program is pointed at.  All
arithmetic is exact rational arithmetic; rounding happens once, when a value is
written, at the two points the stage papers name as carried roundings.  The
program writes the derived documents of the interval into the output
directory and nothing else, and it never writes to the input directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import zipfile
import zlib
from fractions import Fraction
from pathlib import Path
import xml.etree.ElementTree as ET

READING_LEDGER = "reading_ledger.csv"
WITHDRAWAL_LEDGER = "withdrawal_ledger.tsv"
CALIBRATION_SELECTION = "calibration_selection.csv"
LINK_DIFFERENCES = "link_differences.psv"
LINK_GRAPH = "link_graph.json"
EPOCH_GRID = "epoch_grid.csv"
DEADTIME_LEDGER = "deadtime_ledger.jsonl"
OSCILLATOR_SERIES = "oscillator_series.csv"
PREDICTION_BOOK = "prediction_book.json"
DISPERSION_TABLE = "dispersion_table.csv"
WEIGHT_BOOK = "weight_book.json"
WEIGHT_SWEEP_TRACE = "weight_sweep_trace.jsonl"
ENSEMBLE_SCALE = "ensemble_scale.csv"
STEERING_PLAN = "steering_plan.json"
STEERED_SCALE = "steered_scale.csv"
NODE_OFFSETS = "node_offsets.csv"
UNCERTAINTY_BUDGET = "uncertainty_budget.tsv"
DISSEMINATION_LEDGER = "dissemination_ledger.psv"
NODE_REPORT_PREFIX = "node_report_"
NODE_REPORT_SUFFIX = ".json"
RECONCILIATION = "network_reconciliation.xml"
TIMESCALE_REPORT = "timescale_report.md"
ENSEMBLE_SUMMARY = "ensemble_summary.md"
MANIFEST = "publication_manifest.json"
NODE_INDEX = "node_index.conf"

DELIMITERS = {".csv": ",", ".tsv": "\t", ".psv": "|"}


class Fault(Exception):
    """An input the papers do not describe."""


def fault(paper, field):
    raise Fault("input not described by the papers: %s: %s" % (paper, field))


# --------------------------------------------------------------- exact numbers

def round_half_even(value):
    n, d = value.numerator, value.denominator
    q, r = divmod(n, d)
    if 2 * r > d:
        return q + 1
    if 2 * r < d:
        return q
    return q if q % 2 == 0 else q + 1


def as_fraction(value):
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise Fault("boolean is not a rational")
    if isinstance(value, int):
        return Fraction(value)
    if isinstance(value, str):
        return Fraction(value)
    raise Fault("not a rational: %r" % (value,))


def fmt_whole(value):
    return str(round_half_even(as_fraction(value)))


def fmt_ratio(value, places):
    scaled = round_half_even(as_fraction(value) * 10 ** places)
    if scaled == 0:
        return "0." + "0" * places
    sign = "-" if scaled < 0 else ""
    whole, frac = divmod(abs(scaled), 10 ** places)
    return "%s%d.%0*d" % (sign, whole, places, frac)


def truncate_toward_zero(value):
    """Truncate toward zero, not floor: -9/4 truncates to -2."""
    value = as_fraction(value)
    if value >= 0:
        return value.numerator // value.denominator
    return -((-value.numerator) // value.denominator)


# --------------------------------------------------------------- file readers

def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        fault(path.name, "missing paper")


def read_json(path):
    try:
        return json.loads(read_text(path))
    except ValueError:
        fault(path.name, "not well formed json")


def read_table(path):
    delimiter = DELIMITERS.get(path.suffix.lower())
    if delimiter is None:
        fault(path.name, "unknown table format")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [row for row in csv.reader(handle, delimiter=delimiter) if row]
    if not rows:
        fault(path.name, "empty table")
    header = rows[0]
    table = []
    for row in rows[1:]:
        record = {}
        for i, name in enumerate(header):
            record[name] = row[i] if i < len(row) else ""
        table.append(record)
    return table


def read_settings(path):
    settings = {}
    key = None
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if line.startswith("  - ") and key is not None:
            if not isinstance(settings.get(key), list):
                settings[key] = []
            settings[key].append(line[4:].strip())
            continue
        if ":" not in line:
            fault(path.name, "unreadable line")
        key, value = (part.strip() for part in line.split(":", 1))
        settings[key] = value if value else []
    return settings


def find_one(pattern, text, paper, field):
    match = re.search(pattern, text, re.MULTILINE)
    if not match:
        fault(paper, field)
    return match.group(1)


def find_all(pattern, text, paper, field):
    found = re.findall(pattern, text, re.MULTILINE)
    if not found:
        fault(paper, field)
    return found


def need_int(container, key, paper, field):
    try:
        return int(container[key])
    except (KeyError, TypeError, ValueError):
        fault(paper, "%s (%s)" % (field, key))


# --------------------------------------------------------------- the workbook

NS_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
NS_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def column_index(letters):
    index = 0
    for char in letters:
        index = index * 26 + (ord(char) - 64)
    return index - 1


def parse_shared_strings(blob):
    strings = []
    for item in ET.fromstring(blob).findall(NS_MAIN + "si"):
        strings.append("".join(node.text or "" for node in item.iter(NS_MAIN + "t")))
    return strings


def parse_sheet(blob, shared):
    rows = []
    for row in ET.fromstring(blob).iter(NS_MAIN + "row"):
        cells = {}
        for cell in row.findall(NS_MAIN + "c"):
            letters = re.match(r"([A-Z]+)", cell.get("r") or "")
            index = column_index(letters.group(1)) if letters else len(cells)
            value_node = cell.find(NS_MAIN + "v")
            inline = cell.find(NS_MAIN + "is")
            if inline is not None:
                text = "".join(node.text or "" for node in inline.iter(NS_MAIN + "t"))
            elif cell.get("t") == "s":
                text = shared[int(value_node.text)] if value_node is not None else ""
            else:
                text = value_node.text if value_node is not None else ""
            cells[index] = text
        rows.append(cells)
    return rows


def read_workbook(path):
    try:
        handle = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile, KeyError):
        fault(path.name, "not a readable spreadsheet")
    with handle:
        names = handle.namelist()
        if "xl/workbook.xml" not in names or "xl/_rels/workbook.xml.rels" not in names:
            fault(path.name, "workbook structure")
        shared = parse_shared_strings(handle.read("xl/sharedStrings.xml")) if "xl/sharedStrings.xml" in names else []
        rels = {}
        for rel in ET.fromstring(handle.read("xl/_rels/workbook.xml.rels")):
            rels[rel.get("Id")] = rel.get("Target")
        sheets = []
        for sheet in ET.fromstring(handle.read("xl/workbook.xml")).find(NS_MAIN + "sheets"):
            target = rels.get(sheet.get(NS_REL + "id"))
            if target is None:
                fault(path.name, "sheet relationship")
            target = target.lstrip("/")
            if not target.startswith("xl/"):
                target = "xl/" + target
            if target not in names:
                fault(path.name, "sheet part %s" % target)
            sheets.append((sheet.get("name") or "", parse_sheet(handle.read(target), shared)))
    return sheets


def live_sheet(path, key):
    """The live sheet is identified by its key cell, not by its name or position."""
    for name, rows in read_workbook(path):
        for cells in rows:
            if key in cells.values():
                return rows
    fault(path.name, "no sheet carries the workbook sheet key %s" % key)


# --------------------------------------------------------------- the memo

def unescape_pdf_string(raw):
    out = bytearray()
    i = 0
    while i < len(raw):
        byte = raw[i]
        if byte == 0x5C and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt in b"nrtbf()\\":
                out.append({ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}.get(nxt, nxt))
                i += 2
                continue
            if 0x30 <= nxt <= 0x37:
                j = i + 1
                digits = b""
                while j < len(raw) and 0x30 <= raw[j] <= 0x37 and len(digits) < 3:
                    digits += raw[j : j + 1]
                    j += 1
                out.append(int(digits, 8) & 0xFF)
                i = j
                continue
            out.append(nxt)
            i += 2
            continue
        out.append(byte)
        i += 1
    return out.decode("latin-1")


def read_pdf_text(path):
    blob = path.read_bytes()
    lines = []
    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", blob, re.S):
        raw = match.group(1)
        head = blob[max(0, match.start() - 400) : match.start()]
        if b"FlateDecode" in head:
            try:
                raw = zlib.decompress(raw)
            except zlib.error:
                fault(path.name, "compressed stream")
        for item in re.finditer(rb"\(((?:\\.|[^()\\])*)\)\s*Tj", raw, re.S):
            lines.append(unescape_pdf_string(item.group(1)))
    if not lines:
        fault(path.name, "no readable text")
    return "\n".join(lines)


# --------------------------------------------------------------- the papers

class Papers:
    """Every control value, threshold and vocabulary member the interval uses."""

    def __init__(self, data):
        self.data = data
        overview = read_text(data / "network_contract_overview.md")
        self.stage_spec = {}
        for line in overview.splitlines():
            if "|" not in line:
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) == 3 and re.fullmatch(r"T\d+", cells[0]) and cells[2].endswith(".md"):
                self.stage_spec[cells[0]] = cells[2]
        self.config = read_json(data / "network_config.json")
        for field in ("interval_label", "interval_epochs", "interval_start_epoch_s",
                      "grid_step_seconds", "hub_node", "frozen_register_revision",
                      "workbook_sheet_key", "archive_epochs"):
            if field not in self.config:
                fault("network_config.json", field)
        self.overview = overview
        self.specs = {}
        self.grid_policy = read_settings(data / "epoch_grid_policy.yaml")
        self.weighting = read_settings(data / "weighting_policy.yaml")
        self.capping = read_settings(data / "capping_policy.yaml")
        self.steering = read_settings(data / "steering_policy.yaml")
        self.rounding = read_settings(data / "rounding_policy.yaml")
        self.ordering = read_settings(data / "ordering_dependencies.yaml")
        self.artifact_contract = read_text(data / "output_artifact_contract.md")
        self.schema_reference = read_text(data / "output_schema_reference.md")
        self.load_vocabularies()
        self.load_control_values()

    def spec(self, stage):
        name = self.stage_spec.get(stage)
        if name is None:
            fault("network_contract_overview.md", "specification of stage %s" % stage)
        if stage not in self.specs:
            self.specs[stage] = read_text(self.data / name)
        return self.specs[stage]

    def load_vocabularies(self):
        data = self.data
        self.ps_per_step = Fraction(int(find_one(
            r"exactly (\d+) ten thousandths of a", self.overview,
            "network_contract_overview.md", "picoseconds per grid step at one part in ten to the eighteenth")), 10000)
        self.ratio_places = need_int(self.rounding, "ratio_places", "rounding_policy.yaml", "ratio places")
        t01 = self.spec("T01")
        self.drop_reasons = find_all(r"^\s*\d+\.\s+(DR_[A-Z_]+)", t01, self.stage_spec["T01"], "the ordered set aside predicates")
        t02 = self.spec("T02")
        self.report_none = find_one(r"recorded as (REPORT_[A-Z_]+)", t02, self.stage_spec["T02"], "the absent report token")
        self.cal_absent = find_one(r"status is recorded as (CAL_[A-Z_]+)", t02, self.stage_spec["T02"], "the absent calibration status")
        self.ns_to_ps = int(find_one(r"delay_b_ns\)\s*\*\s*(\d+)", t02, self.stage_spec["T02"], "the nanoseconds to picoseconds factor"))
        self.no_epoch_token = find_one(r"or the text (\S+) when it was attributed to none", self.schema_reference, "output_schema_reference.md", "the token for an unattributed row")
        t03 = self.spec("T03")
        self.sense_a_minus_b = find_one(r"(SENSE_A_MINUS_B)\s+already expresses", t03, self.stage_spec["T03"], "the a minus b sense")
        self.sense_b_minus_a = find_one(r"technique records (SENSE_B_MINUS_A)\s+expresses", t03, self.stage_spec["T03"], "the b minus a sense")
        self.techniques = {}
        for line in read_text(data / "link_technique_reference.txt").splitlines():
            match = re.match(r"^(LK_\S+)\s+(SENSE_[A-Z_]+)\s+(\d+)\s+", line)
            if match:
                self.techniques[match.group(1)] = {"sense": match.group(2), "rank": int(match.group(3))}
        if not self.techniques:
            fault("link_technique_reference.txt", "the technique table")
        t04 = self.spec("T04")
        roles = find_all(r"(ROLE_ANCHORED|ROLE_UNANCHORED)", t04, self.stage_spec["T04"], "the component roles")
        seen = []
        for role in roles:
            if role not in seen:
                seen.append(role)
        if len(seen) != 2:
            fault(self.stage_spec["T04"], "the two component roles")
        self.role_anchored, self.role_unanchored = seen
        template = find_one(r"identified\s+([A-Za-z]+_\d+)", t04, self.stage_spec["T04"], "the component identifiers")
        self.component_prefix, digits = template.rsplit("_", 1)
        self.component_width = len(digits)
        t05 = self.spec("T05")
        t06 = self.spec("T06")
        self.lock_held = find_one(r"Only\s+(\S+)\s+makes an attempt eligible",
                                  read_text(data / "lock_state_reference.txt"),
                                  "lock_state_reference.txt", "the lock state that makes an attempt eligible")
        self.monitor_valid = find_one(r"monitor_flag is not (MON_[A-Z_]+)", t06, self.stage_spec["T06"], "the valid monitor flag")
        self.series_measured = find_one(r"carries (SER_[A-Z_]+) when its node is in the anchored", t06, self.stage_spec["T06"], "the measured series flag")
        self.series_unanchored = find_one(r"and (SER_[A-Z_]+) when its node is in an unanchored", t06, self.stage_spec["T06"], "the unanchored series flag")
        self.series_absent = find_one(r"no deviation at an epoch carries (SER_[A-Z_]+)", t06, self.stage_spec["T06"], "the absent series flag")
        scope_text = t05 + t06 + self.schema_reference
        scopes = find_all(r"scope (SCOPE_[A-Z_]+)", scope_text, "the stage papers", "the absence scopes")
        scope_seen = []
        for scope in scopes:
            if scope not in scope_seen:
                scope_seen.append(scope)
        if len(scope_seen) != 3:
            fault("the stage papers", "the three absence scopes")
        self.scope_link, self.scope_node, self.scope_oscillator = scope_seen
        self.cause_link = find_one(r"cause is the link identifier for SCOPE_NODE,\s*(CAUSE_[A-Z_]+) for SCOPE_LINK", scope_text, "the stage papers", "the link absence cause")
        self.cause_oscillator = find_one(r"(CAUSE_[A-Z_]+) for SCOPE_OSCILLATOR", scope_text, "the stage papers", "the oscillator absence cause")
        t07 = self.spec("T07")
        self.exclusions = find_all(r"^\s+(EX_[A-Z_]+)\s", t07, self.stage_spec["T07"], "the ordered ensemble exclusions")
        class_reference = read_text(data / "oscillator_class_reference.txt")
        self.decommissioned = find_one(r"^(OS_[A-Z_]+)\s+withdrawn from service", class_reference, "oscillator_class_reference.txt", "the decommissioned status")
        t08 = self.spec("T08")
        sources = find_all(r"(WS_[A-Z_]+)", t08, self.stage_spec["T08"], "the weight sources")
        if len(sources) != 2:
            fault(self.stage_spec["T08"], "the two weight sources")
        self.weight_dispersion, self.weight_ceiling = sources
        t09 = self.spec("T09")
        phases = find_all(r"(PH_[A-Z_]+)", t09, self.stage_spec["T09"], "the capping phases")
        phase_seen = []
        for phase in phases:
            if phase not in phase_seen:
                phase_seen.append(phase)
        if len(phase_seen) != 3:
            fault(self.stage_spec["T09"], "the capping phases")
        self.phase_osc, self.phase_node, self.phase_final = phase_seen
        self.sw_settled = find_one(r"above the cap, and record (SW_[A-Z_]+)", t09, self.stage_spec["T09"], "the settled outcome")
        self.sw_budget_exhausted = find_one(r"still above the cap, and record (SW_[A-Z_]+)", t09, self.stage_spec["T09"], "the budget exhausted outcome")
        self.sw_unsat = find_one(r"take the excess, and record (SW_[A-Z_]+)", t09, self.stage_spec["T09"], "the unsatisfiable outcome")
        t10 = self.spec("T10")
        self.epoch_void = find_one(r"^\s*(EP_[A-Z_]+),", t10, self.stage_spec["T10"], "the void epoch state")
        self.epoch_populated = find_one(r"state (EP_[A-Z_]+)", t10, self.stage_spec["T10"], "the populated epoch state")
        t11 = self.spec("T11")
        outcomes = find_all(r"(ST_[A-Z_]+)", t11, self.stage_spec["T11"], "the steering outcomes")
        outcome_seen = []
        for outcome in outcomes:
            if outcome not in outcome_seen:
                outcome_seen.append(outcome)
        if len(outcome_seen) != 3:
            fault(self.stage_spec["T11"], "the three steering outcomes")
        self.st_no_realisation, self.st_truncated, self.st_applied = outcome_seen
        t12 = self.spec("T12")
        self.offset_absent = find_one(r"absent offset with flag (OFF_[A-Z_]+)", t12, self.stage_spec["T12"], "the absent offset flag")
        self.offset_published = find_one(r"other offset carries (OFF_[A-Z_]+)", t12, self.stage_spec["T12"], "the published offset flag")
        statuses = find_all(r"^\s+(DS_[A-Z_]+)\s", t12, self.stage_spec["T12"], "the ordered dissemination statuses")
        if len(statuses) != 3:
            fault(self.stage_spec["T12"], "the three dissemination statuses")
        self.withheld_unanchored, self.withheld_no_data, self.dissemination_published = statuses
        self.node_cap_key = find_one(r"node cap\s*=\s*([A-Z0-9_]+)\s*numerator", t09, self.stage_spec["T09"], "the node weight cap key")
        keys = find_all(r"oscillator cap\s*=\s*([A-Z0-9_]+)\s*/\s*([A-Z0-9_]+)\s*\*\s*W", t09, self.stage_spec["T09"], "the oscillator cap keys")
        self.cap_numerator_key, self.cap_denominator_key = keys[0]
        self.sweep_budget_key = find_one(r"passes already run equals\s+([A-Z0-9_]+)", t09, self.stage_spec["T09"], "the sweep budget key")

    def load_control_values(self):
        memo_text = read_pdf_text(self.data / "network_calibration_memo.pdf")
        memo_values = {}
        for match in re.finditer(r"^([A-Z][A-Z0-9_]*)\s*=\s*(-?\d+)\s*$", memo_text, re.MULTILINE):
            memo_values[match.group(1)] = int(match.group(2))
        if self.cap_numerator_key not in memo_values or self.cap_denominator_key not in memo_values:
            fault("network_calibration_memo.pdf", "the oscillator cap control values")
        self.osc_cap = Fraction(memo_values[self.cap_numerator_key], memo_values[self.cap_denominator_key])
        self.sweep_budget = need_int(memo_values, self.sweep_budget_key, "network_calibration_memo.pdf", "the cap sweep budget")
        named = {self.cap_numerator_key, self.cap_denominator_key, self.sweep_budget_key}
        remaining = [name for name in memo_values if name not in named]
        if len(remaining) != 1:
            fault("network_calibration_memo.pdf", "the history minimum control value")
        self.history_minimum = memo_values[remaining[0]]

        rows = live_sheet(self.data / "timing_network_workbook.xlsx", self.config["workbook_sheet_key"])
        classes = set(re.findall(r"^(OSC_[A-Z_]+)\s", read_text(self.data / "oscillator_class_reference.txt"), re.MULTILINE))
        catalogue = read_table(self.data / "oscillator_catalogue.csv")
        osc_ids = {row["osc_id"] for row in catalogue}
        self.class_ceilings = {}
        self.node_cap = None
        self.uncertainty_components = {}
        for cells in rows:
            if not cells:
                continue
            columns = sorted(cells)
            first = cells[columns[0]]
            if first in classes:
                if len(columns) < 2:
                    fault("timing_network_workbook.xlsx", "the class ceiling weight of %s" % first)
                self.class_ceilings[first] = as_fraction(cells[columns[1]])
            elif first == self.node_cap_key:
                if len(columns) < 3:
                    fault("timing_network_workbook.xlsx", "the node weight cap")
                self.node_cap = Fraction(as_fraction(cells[columns[1]]), as_fraction(cells[columns[2]]))
            elif first in osc_ids:
                if len(columns) < 3:
                    fault("timing_network_workbook.xlsx", "the uncertainty component of %s" % first)
                self.uncertainty_components.setdefault(first, []).append((cells[columns[1]], as_fraction(cells[columns[2]])))
        if self.node_cap is None:
            fault("timing_network_workbook.xlsx", "the node weight cap")
        if not self.class_ceilings:
            fault("timing_network_workbook.xlsx", "the class ceiling weights")
        if not self.uncertainty_components:
            fault("timing_network_workbook.xlsx", "the uncertainty component table")

    def artifact_order(self):
        order = []
        for line in self.artifact_contract.splitlines():
            if not line.strip().startswith("|"):
                continue
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if len(cells) < 2 or cells[0] == "artifact" or set(cells[0]) <= {"-"}:
                continue
            order.append(cells[0])
        if MANIFEST not in order:
            fault("output_artifact_contract.md", "the publication manifest")
        return order

    def node_report_nodes(self):
        nodes = []
        for name in self.artifact_order():
            match = re.fullmatch(re.escape(NODE_REPORT_PREFIX) + r"(\S+)" + re.escape(NODE_REPORT_SUFFIX), name)
            if match:
                nodes.append(match.group(1))
        if not nodes:
            fault("output_artifact_contract.md", "the per node reports")
        return nodes

    def manifest_counts(self):
        match = re.search(r"document_count is (\d+) and rule_count is (\d+)", self.schema_reference)
        if not match:
            fault("output_schema_reference.md", "document_count and rule_count")
        return int(match.group(1)), int(match.group(2))

    def digest_order(self):
        order = self.ordering.get("digest_order")
        if not isinstance(order, list) or not order:
            fault("ordering_dependencies.yaml", "digest_order")
        return list(order)


# --------------------------------------------------------------- stage T01

def stage_t01(papers):
    """Attribute every acquisition row onto the grid, set aside and select."""
    data = papers.data
    config = papers.config
    instant_offset = need_int(papers.grid_policy, "grid_instant_offset_s", "epoch_grid_policy.yaml", "grid instant offset")
    tolerance = need_int(papers.grid_policy, "attribution_tolerance_s", "epoch_grid_policy.yaml", "attribution tolerance")
    epochs = need_int(config, "interval_epochs", "network_config.json", "interval epochs")
    start = need_int(config, "interval_start_epoch_s", "network_config.json", "interval start")
    step = need_int(config, "grid_step_seconds", "network_config.json", "grid step")
    instants = {k: start + (k - 1) * step + instant_offset for k in range(1, epochs + 1)}

    links = {}
    for row in read_table(data / "link_register.csv"):
        if not row.get("link_id"):
            fault("link_register.csv", "link_id")
        links[row["link_id"]] = row
    withdrawn = set()
    for row in read_table(data / "session_withdrawal_journal.tsv"):
        if not row.get("session_id"):
            fault("session_withdrawal_journal.tsv", "session_id")
        withdrawn.add(row["session_id"])
    log = read_table(data / "comparison_session_log.csv")

    set_aside = []
    survivors = []
    for row in log:
        acquired = need_int(row, "acq_time_s", "comparison_session_log.csv", "acquisition time")
        epoch = None
        for index, instant in instants.items():
            if instant - tolerance <= acquired < instant + tolerance:
                epoch = index
                break
        if epoch is None:
            set_aside.append((papers.drop_reasons[0], row, None))
            continue
        if row.get("session_id") in withdrawn:
            set_aside.append((papers.drop_reasons[1], row, epoch))
            continue
        link = links.get(row.get("link_id"))
        if link is None:
            set_aside.append((papers.drop_reasons[2], row, epoch))
            continue
        if link.get("node_a") == link.get("node_b"):
            set_aside.append((papers.drop_reasons[3], row, epoch))
            continue
        survivors.append((row, epoch))

    clusters = {}
    for row, epoch in survivors:
        clusters.setdefault((row["link_id"], epoch), []).append(row)

    canonical = []
    for (link_id, epoch), rows in clusters.items():
        eligible = [row for row in rows if row.get("lock_state") == papers.lock_held]
        if not eligible:
            for row in rows:
                set_aside.append((papers.drop_reasons[4], row, epoch))
            continue
        best = max(need_int(row, "attempt_no", "comparison_session_log.csv", "attempt number") for row in eligible)
        candidates = [row for row in eligible if int(row["attempt_no"]) == best]
        if len(candidates) > 1:
            candidates.sort(key=lambda row: (abs(int(row["acq_time_s"]) - instants[epoch]), int(row["acq_time_s"])))
        canonical.append({"link_id": link_id, "epoch_index": epoch, "row": candidates[0], "cluster_rows": len(rows)})
    return canonical, set_aside, instants, links, epochs


# --------------------------------------------------------------- stage T02

def stage_t02(papers, canonical, links):
    """Select the applicable delay report for every canonical reading."""
    reports = {}
    for name in ("delay_calibration_ledger.csv", "delay_calibration_supplement.psv"):
        for row in read_table(papers.data / name):
            if not row.get("link_id"):
                fault(name, "link_id")
            parsed = dict(row)
            for source, target in (("effective_epoch_s", "_effective"), ("revision", "_revision"),
                                   ("delay_a_ns", "_a"), ("delay_b_ns", "_b")):
                try:
                    parsed[target] = int(row[source])
                except (KeyError, ValueError):
                    fault(name, source)
            reports.setdefault(row["link_id"], []).append(parsed)

    for reading in canonical:
        acquired = int(reading["row"]["acq_time_s"])
        governing = [row for row in reports.get(reading["link_id"], []) if row["_effective"] <= acquired]
        applicable = None
        if governing:
            latest = max(row["_effective"] for row in governing)
            applicable = min((row for row in governing if row["_effective"] == latest), key=lambda row: row["_revision"])
        if applicable is None:
            reading["report_id"] = papers.report_none
            reading["revision"] = 0
            reading["status"] = papers.cal_absent
            reading["effective_epoch_s"] = 0
            reading["correction_ps"] = Fraction(0)
        else:
            reading["report_id"] = applicable["report_id"]
            reading["revision"] = applicable["_revision"]
            reading["status"] = applicable["status"]
            reading["effective_epoch_s"] = applicable["_effective"]
            reading["correction_ps"] = Fraction((applicable["_a"] - applicable["_b"]) * papers.ns_to_ps)
        reading["corrected_ps"] = Fraction(int(reading["row"]["raw_offset_ps"])) - reading["correction_ps"]
        technique = links[reading["link_id"]].get("technique")
        if technique not in papers.techniques:
            fault("link_technique_reference.txt", "technique %s" % technique)
        reading["technique"] = technique
        reading["sense"] = papers.techniques[technique]["sense"]
    return canonical


# --------------------------------------------------------------- stage T03

def stage_t03(papers, canonical):
    """Bring every reading to the A minus B convention."""
    for reading in canonical:
        if reading["sense"] == papers.sense_a_minus_b:
            reading["difference_ps"] = reading["corrected_ps"]
        elif reading["sense"] == papers.sense_b_minus_a:
            reading["difference_ps"] = -reading["corrected_ps"]
        else:
            fault("link_technique_reference.txt", "the sense of %s" % reading["sense"])
    return canonical


# --------------------------------------------------------------- stage T04

def stage_t04(papers):
    """Build the components and grow the spanning tree of each one."""
    data = papers.data
    config = papers.config
    revision = config["frozen_register_revision"]
    nodes = {}
    for row in read_table(data / "node_register_frozen.csv"):
        if row.get("register_revision") == revision:
            if not row.get("node_id"):
                fault("node_register_frozen.csv", "node_id")
            nodes[row["node_id"]] = row
    if not nodes:
        fault("node_register_frozen.csv", "no nodes at revision %s" % revision)
    usable = {}
    for row in read_table(data / "link_register.csv"):
        a, b = row.get("node_a"), row.get("node_b")
        if a in nodes and b in nodes and a != b:
            usable[row["link_id"]] = row

    adjacency = {node: [] for node in nodes}
    for row in usable.values():
        adjacency[row["node_a"]].append(row["node_b"])
        adjacency[row["node_b"]].append(row["node_a"])

    seen = set()
    groups = []
    for node in sorted(nodes):
        if node in seen:
            continue
        stack = [node]
        seen.add(node)
        group = {node}
        while stack:
            current = stack.pop()
            for neighbour in adjacency[current]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    group.add(neighbour)
                    stack.append(neighbour)
        groups.append(group)
    groups.sort(key=min)

    hub = config["hub_node"]
    components = []
    for position, group in enumerate(groups, 1):
        anchored = hub in group
        role = papers.role_anchored if anchored else papers.role_unanchored
        root = hub if anchored else min(group)
        path_cost = {root: 0}
        reached = {root}
        edges = []
        while True:
            best = None
            for link_id in sorted(usable):
                row = usable[link_id]
                a, b = row["node_a"], row["node_b"]
                if a in reached and b not in reached:
                    parent, child = a, b
                elif b in reached and a not in reached:
                    parent, child = b, a
                else:
                    continue
                if row["technique"] not in papers.techniques:
                    fault("link_technique_reference.txt", "technique %s" % row["technique"])
                cost = path_cost[parent] + as_fraction(row["published_uncertainty_ps"])
                key = (cost, papers.techniques[row["technique"]]["rank"], link_id)
                if best is None or key < best[0]:
                    best = (key, link_id, parent, child, row)
            if best is None:
                break
            _, link_id, parent, child, row = best
            edges.append({"link_id": link_id, "parent_node": parent, "child_node": child,
                          "technique": row["technique"],
                          "published_uncertainty_ps": int(row["published_uncertainty_ps"]),
                          "node_a": row["node_a"], "node_b": row["node_b"]})
            reached.add(child)
            path_cost[child] = path_cost[parent] + int(row["published_uncertainty_ps"])
        admitted = {edge["link_id"] for edge in edges}
        members = set(group)
        excluded = sorted(link_id for link_id, row in usable.items()
                           if link_id not in admitted
                           and row["node_a"] in members and row["node_b"] in members)
        component = {
            "component_id": "%s_%0*d" % (papers.component_prefix, papers.component_width, position),
            "role": role, "root_node": root, "member_nodes": sorted(group),
            "tree_edges": edges, "excluded_link_ids": excluded,
        }
        components.append(component)
    return components, nodes, usable


# --------------------------------------------------------------- stage T05

def build_tree(papers, components):
    """Index the trees: parent, children and the root outward path of each node."""
    tree_link = {}
    children = {}
    parent = {}
    node_component = {}
    for component in components:
        for node in component["member_nodes"]:
            node_component[node] = component
        for edge in component["tree_edges"]:
            tree_link[edge["link_id"]] = edge
            children.setdefault(edge["parent_node"], []).append(edge["child_node"])
            parent[edge["child_node"]] = (edge["parent_node"], edge["link_id"])

    def path_links(node):
        chain = []
        while node in parent:
            node, link_id = parent[node]
            chain.append(link_id)
        chain.reverse()
        return chain

    return tree_link, children, parent, node_component, path_links


def stage_t05(papers, canonical, components, epochs):
    """Carry the tree paths into node offsets and record dead time."""
    difference = {}
    for reading in canonical:
        difference[(reading["link_id"], reading["epoch_index"])] = reading["difference_ps"]

    tree_link, children, parent, node_component, path_links = build_tree(papers, components)
    offsets = {}
    dead = set()
    for component in components:
        root = component["root_node"]
        order = [root]
        position = 0
        while position < len(order):
            node = order[position]
            position += 1
            for child in children.get(node, []):
                order.append(child)
        for epoch in range(1, epochs + 1):
            for node in order:
                if node == root:
                    offsets[(root, epoch)] = Fraction(0)
                    continue
                node_parent, link_id = parent[node]
                edge = tree_link[link_id]
                value = difference.get((link_id, epoch))
                if value is None:
                    dead.add((epoch, papers.scope_link, link_id, papers.cause_link))
                    continue
                # A tree edge whose node_a is the parent contributes the negated difference.
                if edge["node_a"] == node_parent:
                    contribution = -value
                else:
                    contribution = value
                if (node_parent, epoch) in offsets:
                    offsets[(node, epoch)] = offsets[(node_parent, epoch)] + contribution
        for epoch in range(1, epochs + 1):
            for node in order[1:]:
                if (node, epoch) in offsets:
                    continue
                for link_id in path_links(node):
                    if (link_id, epoch) not in difference:
                        dead.add((epoch, papers.scope_node, node, link_id))
                        break
    return offsets, dead, tree_link, node_component, path_links


# --------------------------------------------------------------- stage T06

def stage_t06(papers, catalogue, components, node_component, offsets, dead, epochs):
    """Turn the node offsets and the local monitor into a deviation series."""
    data = papers.data
    revision = papers.config["frozen_register_revision"]
    reference = {}
    for row in read_table(data / "node_register_frozen.csv"):
        if row.get("register_revision") == revision and row.get("node_id"):
            reference[row["node_id"]] = row.get("reference_oscillator")
    monitor = {}
    for row in read_table(data / "local_comparison_log.psv"):
        key = (row.get("osc_id"), need_int(row, "epoch_index", "local_comparison_log.psv", "epoch index"))
        monitor[key] = row

    series = {}
    for osc in catalogue:
        osc_id, node_id = osc.get("osc_id"), osc.get("node_id")
        if not osc_id or not node_id:
            fault("oscillator_catalogue.csv", "osc_id and node_id")
        for epoch in range(1, epochs + 1):
            node_offset = offsets.get((node_id, epoch))
            if node_offset is None:
                series[(osc_id, epoch)] = (None, papers.series_absent)
                continue
            if reference.get(node_id) == osc_id:
                series[(osc_id, epoch)] = (node_offset, None)
                continue
            row = monitor.get((osc_id, epoch))
            if row is None or row.get("monitor_flag") != papers.monitor_valid:
                series[(osc_id, epoch)] = (None, papers.series_absent)
                dead.add((epoch, papers.scope_oscillator, osc_id, papers.cause_oscillator))
                continue
            series[(osc_id, epoch)] = (node_offset + as_fraction(row["local_offset_ps"]), None)

    anchored = set()
    for component in components:
        if component["role"] == papers.role_anchored:
            anchored.update(component["member_nodes"])
    node_of = {osc["osc_id"]: osc["node_id"] for osc in catalogue}
    for key, (value, flag) in list(series.items()):
        if flag is not None:
            continue
        series[key] = (value, papers.series_measured if node_of[key[0]] in anchored else papers.series_unanchored)
    return series


# --------------------------------------------------------------- stage T07

def stage_t07(papers, catalogue, components):
    """Predict every oscillator from the previous interval's archive."""
    archive = read_table(papers.data / "prior_interval_deviations.psv")
    archive_epochs = need_int(papers.config, "archive_epochs", "network_config.json", "archive epochs")
    window_epochs = need_int(papers.weighting, "history_window_epochs", "weighting_policy.yaml", "history window")
    window_first = archive_epochs - window_epochs + 1
    window_last = archive_epochs
    valid_flag = papers.weighting["valid_archive_flag"]

    deviation = {}
    archived_ids = set()
    for row in archive:
        osc_id = row.get("osc_id")
        archived_ids.add(osc_id)
        if row.get("quality_flag") == valid_flag:
            deviation[(osc_id, need_int(row, "archive_epoch", "prior_interval_deviations.psv", "archive epoch"))] = as_fraction(row["deviation_ps"])

    anchored = set()
    for component in components:
        if component["role"] == papers.role_anchored:
            anchored.update(component["member_nodes"])
    predictions = {}
    for osc in catalogue:
        osc_id, node_id = osc.get("osc_id"), osc.get("node_id")
        valid = [epoch for epoch in range(window_first, window_last + 1) if (osc_id, epoch) in deviation]
        if osc.get("status") == papers.decommissioned:
            reason = papers.exclusions[0]
        elif osc_id not in archived_ids:
            reason = papers.exclusions[1]
        elif len(valid) < papers.history_minimum:
            reason = papers.exclusions[2]
        elif node_id not in anchored:
            reason = papers.exclusions[3]
        else:
            reason = ""
        record = {"window_first": window_first, "window_last": window_last, "valid": len(valid)}
        if reason:
            record.update({"included": False, "reason": reason, "anchor_epoch": 0,
                           "anchor_deviation": Fraction(0), "frequency": Fraction(0)})
        else:
            anchor_epoch = valid[-1]
            anchor_deviation = deviation[(osc_id, anchor_epoch)]
            first_epoch = valid[0]
            steps = anchor_epoch - first_epoch
            delta = anchor_deviation - deviation[(osc_id, first_epoch)]
            record.update({"included": True, "reason": "", "anchor_epoch": anchor_epoch,
                           "anchor_deviation": anchor_deviation,
                           "frequency": delta / (steps * papers.ps_per_step) if steps else Fraction(0)})
        predictions[osc_id] = record
    return predictions


def prediction_step(papers, prediction, steps):
    """The predicted deviation of an oscillator, steps epochs after its anchor."""
    return prediction["anchor_deviation"] + prediction["frequency"] * steps * papers.ps_per_step


# --------------------------------------------------------------- stage T08

def stage_t08(papers, catalogue, predictions):
    """Take the residual dispersion and form the raw weights."""
    archive = read_table(papers.data / "prior_interval_deviations.psv")
    valid_flag = papers.weighting["valid_archive_flag"]
    deviation = {}
    for row in archive:
        if row.get("quality_flag") == valid_flag:
            deviation[(row["osc_id"], int(row["archive_epoch"]))] = as_fraction(row["deviation_ps"])

    weight_scale = as_fraction(papers.weighting["weight_scale"])
    dispersion = {}
    raw_weights = {}
    weight_sources = {}
    for osc in catalogue:
        osc_id = osc["osc_id"]
        prediction = predictions.get(osc_id)
        if not prediction or not prediction["included"]:
            continue
        residuals = []
        for epoch in range(prediction["window_first"], prediction["window_last"] + 1):
            archived = deviation.get((osc_id, epoch))
            if archived is None:
                continue
            predicted = prediction_step(papers, prediction, epoch - prediction["anchor_epoch"])
            residuals.append(abs(archived - predicted))
        published = round_half_even(sum(residuals) / len(residuals)) if residuals else 0
        dispersion[osc_id] = published
        if published == 0:
            ceiling = papers.class_ceilings.get(osc.get("osc_class"))
            if ceiling is None:
                fault("timing_network_workbook.xlsx", "the class ceiling weight of %s" % osc.get("osc_class"))
            raw_weights[osc_id] = ceiling
            weight_sources[osc_id] = papers.weight_ceiling
        else:
            raw_weights[osc_id] = weight_scale / published
            weight_sources[osc_id] = papers.weight_dispersion
    return dispersion, raw_weights, weight_sources


# --------------------------------------------------------------- stage T09

def close_residue(before, placed, receivers, carry_count, offenders):
    """Hand the placement residue to the receiving holder that has carried it least."""
    residue = before - sum(placed.values())
    if residue == 0:
        return placed
    candidates = [osc for osc in receivers if osc not in offenders]
    if not candidates:
        candidates = list(receivers)
    chosen = min(candidates, key=lambda osc: (carry_count.get(osc, 0), -placed[osc], osc))
    placed[chosen] = placed[chosen] + residue
    carry_count[chosen] = carry_count.get(chosen, 0) + 1
    return placed


def osc_cap_pass(papers, weights, cap, damping, unit, carry_count, trace, sweep):
    """One damped step of the oscillator cap, placed back on the published grid."""
    offenders = sorted(osc for osc, weight in weights.items() if weight > cap)
    if not offenders:
        return weights, offenders, papers.sw_settled, Fraction(0)
    if all(weight > cap for weight in weights.values()):
        return weights, offenders, papers.sw_unsat, Fraction(0)
    target = dict(weights)
    excess = Fraction(0)
    for osc in offenders:
        excess += target[osc] - cap
        target[osc] = cap
    receivers = [osc for osc in weights if osc not in offenders]
    held = sum(weights[osc] for osc in receivers)
    for osc in receivers:
        target[osc] = weights[osc] + excess * weights[osc] / held if held else weights[osc]
    stepped = {osc: weights[osc] + damping * (target[osc] - weights[osc]) for osc in weights}
    before = sum(stepped.values())
    placed = {osc: Fraction(round_half_even(stepped[osc] * unit), unit) for osc in stepped}
    placed = close_residue(before, placed, receivers, carry_count, set(offenders))
    residual = sum(abs(placed[osc] - weights[osc]) for osc in weights)
    moved = sum(weights[osc] for osc in offenders) - sum(placed[osc] for osc in offenders)
    trace.append({"phase": papers.phase_osc, "sweep": sweep, "offenders": offenders,
                  "excess": moved, "holders": len(receivers), "residual": residual})
    return placed, offenders, None, residual


def node_cap_pass(papers, weights, cap, unit, carry_count, trace, nodes_of_osc):
    """One full pass of the node cap, placed back on the published grid."""
    totals = {}
    for osc, weight in weights.items():
        totals[nodes_of_osc[osc]] = totals.get(nodes_of_osc[osc], Fraction(0)) + weight
    offenders = sorted(node for node, total in totals.items() if total > cap)
    if not offenders:
        return weights, offenders, papers.sw_settled, Fraction(0)
    if all(total > cap for total in totals.values()):
        return weights, offenders, papers.sw_unsat, Fraction(0)
    excess = Fraction(0)
    target = dict(weights)
    offender_set = set(offenders)
    for node in offenders:
        excess += totals[node] - cap
        scale = cap / totals[node]
        for osc in weights:
            if nodes_of_osc[osc] == node:
                target[osc] = weights[osc] * scale
    receivers = [osc for osc in weights if nodes_of_osc[osc] not in offender_set]
    held = sum(weights[osc] for osc in receivers)
    for osc in receivers:
        target[osc] = weights[osc] + excess * weights[osc] / held if held else weights[osc]
    before = sum(target.values())
    placed = {osc: Fraction(round_half_even(target[osc] * unit), unit) for osc in target}
    placed = close_residue(before, placed, receivers, carry_count,
                           {osc for osc in weights if nodes_of_osc[osc] in offender_set})
    residual = sum(abs(placed[osc] - weights[osc]) for osc in weights)
    moved = sum(weights[osc] for osc in weights if nodes_of_osc[osc] in offender_set) \
        - sum(placed[osc] for osc in placed if nodes_of_osc[osc] in offender_set)
    trace.append({"phase": papers.phase_node, "sweep": 1, "offenders": offenders,
                  "excess": moved, "holders": len(receivers), "residual": residual})
    return placed, offenders, None, residual


def stage_t09(papers, catalogue, raw_weights):
    """Run the caps in the order the capping policy states."""
    places = need_int(papers.weighting, "weight_places", "weighting_policy.yaml", "weight places")
    damping = Fraction(need_int(papers.weighting, "damping_numerator", "weighting_policy.yaml", "damping numerator"),
                       need_int(papers.weighting, "damping_denominator", "weighting_policy.yaml", "damping denominator"))
    unit = 10 ** places
    total = sum(raw_weights.values())
    osc_cap = papers.osc_cap * total
    node_cap = papers.node_cap * total
    nodes_of_osc = {osc["osc_id"]: osc["node_id"] for osc in catalogue}

    # The capping starts from the raw weights placed on the published grid.
    weights = {osc: Fraction(round_half_even(weight * unit), unit) for osc, weight in raw_weights.items()}
    carry_count = {}

    trace = []
    sweeps = 0
    outcome = papers.sw_settled
    while True:
        weights, offenders, pass_outcome, _ = osc_cap_pass(
            papers, weights, osc_cap, damping, unit, carry_count, trace, sweeps + 1)
        sweeps += 1
        if pass_outcome == papers.sw_unsat:
            outcome = papers.sw_unsat
            break
        if not offenders:
            outcome = papers.sw_settled
            break
        if sweeps >= papers.sweep_budget:
            outcome = papers.sw_budget_exhausted
            break
    after_osc = dict(weights)

    weights, offenders, node_outcome, _ = node_cap_pass(
        papers, weights, node_cap, unit, carry_count, trace, nodes_of_osc)
    if node_outcome is None:
        # The node cap is taken in full, so no offending node remains above it.
        node_outcome = papers.sw_settled
    after_node = dict(weights)

    weights, offenders, final_outcome, terminal_residual = osc_cap_pass(
        papers, weights, osc_cap, damping, unit, carry_count, trace, 1)
    if final_outcome is None:
        final_outcome = papers.sw_budget_exhausted if offenders else papers.sw_settled
    return {
        "weights": weights, "after_osc": after_osc, "after_node": after_node,
        "osc_cap": osc_cap, "node_cap": node_cap, "osc_outcome": outcome,
        "node_outcome": node_outcome, "final_outcome": final_outcome,
        "sweeps_used": sweeps, "damping": damping, "places": places,
        "terminal_residual": terminal_residual, "trace": trace, "total_weight": total,
    }


# --------------------------------------------------------------- stage T10

def stage_t10(papers, series, predictions, final_weights, epochs):
    """Form the free ensemble scale at every epoch."""
    free = {}
    archive_epochs = need_int(papers.config, "archive_epochs", "network_config.json", "archive epochs")
    for epoch in range(1, epochs + 1):
        numerator = Fraction(0)
        denominator = Fraction(0)
        contributing = 0
        for osc_id, weight in final_weights.items():
            entry = series.get((osc_id, epoch))
            if entry is None or entry[0] is None:
                continue
            prediction = predictions.get(osc_id)
            if not prediction or not prediction["included"]:
                continue
            steps = archive_epochs + epoch - prediction["anchor_epoch"]
            numerator += weight * (entry[0] - prediction_step(papers, prediction, steps))
            denominator += weight
            contributing += 1
        if denominator == 0:
            free[epoch] = {"state": papers.epoch_void, "count": 0, "denominator": Fraction(0), "value": None}
        else:
            free[epoch] = {"state": papers.epoch_populated, "count": contributing,
                           "denominator": denominator, "value": numerator / denominator}
    return free


# --------------------------------------------------------------- stage T11

def stage_t11(papers, free, epochs):
    """Steer the free scale onto the primary realisation."""
    decision = need_int(papers.steering, "decision_epoch", "steering_policy.yaml", "the decision epoch")
    horizon = need_int(papers.steering, "horizon_epochs", "steering_policy.yaml", "the horizon")
    grid_atto = need_int(papers.steering, "grid_atto", "steering_policy.yaml", "the steering grid")
    realisation = {}
    for row in read_table(papers.data / "primary_standard_realisation.csv"):
        epoch = need_int(row, "epoch_index", "primary_standard_realisation.csv", "epoch index")
        text = row.get("realisation_ps", "")
        realisation[epoch] = as_fraction(text) if text.strip() else None

    plan = {"decision_epoch": decision, "horizon_epochs": horizon, "grid_atto": grid_atto}
    entry = free.get(decision)
    realisation_value = realisation.get(decision)
    if entry is None or entry["value"] is None or realisation_value is None:
        plan.update({"departure": None, "raw_step": Fraction(0), "step": Fraction(0),
                     "outcome": papers.st_no_realisation})
    else:
        departure = entry["value"] - realisation_value
        raw_step = -departure / (horizon * papers.ps_per_step)
        step = Fraction(truncate_toward_zero(raw_step / grid_atto) * grid_atto)
        outcome = papers.st_truncated if step == 0 else papers.st_applied
        plan.update({"departure": departure, "raw_step": raw_step, "step": step, "outcome": outcome})

    steered = {}
    for epoch in range(1, epochs + 1):
        entry = free.get(epoch)
        value = entry["value"] if entry else None
        correction = plan["step"] * (epoch - decision) * papers.ps_per_step if epoch > decision else Fraction(0)
        steered[epoch] = (value, correction, value + correction if value is not None else None)
    return plan, steered


# --------------------------------------------------------------- stage T12

def stage_t12(papers, nodes, node_component, offsets, steered, tree_link, path_links, epochs):
    """Publish the node offsets and the uncertainty budget."""
    published = {}
    for node in nodes:
        for epoch in range(1, epochs + 1):
            node_offset = offsets.get((node, epoch))
            entry = steered.get(epoch)
            steered_value = entry[2] if entry else None
            if node_offset is None or steered_value is None:
                published[(node, epoch)] = (None, papers.offset_absent)
            else:
                published[(node, epoch)] = (node_offset - steered_value, papers.offset_published)

    budgets = {}
    for node in nodes:
        reference = nodes[node].get("reference_oscillator")
        components_table = papers.uncertainty_components.get(reference)
        if not components_table:
            fault("timing_network_workbook.xlsx", "the uncertainty components of %s" % reference)
        terms = [value for name, value in components_table]
        terms.append(as_fraction(nodes[node]["declared_uncertainty_ps"]))
        chain = path_links(node)
        for link_id in chain:
            terms.append(as_fraction(tree_link[link_id]["published_uncertainty_ps"]))
        component = node_component[node]
        budgets[node] = {
            "component_id": component["component_id"], "role": component["role"],
            "path_link_ids": chain, "path_length": len(chain), "term_count": len(terms),
            "u_combined": sum(term * term for term in terms), "u_linear": sum(terms),
        }
    return published, budgets


def stage_t12_status(papers, nodes, node_component, published, epochs):
    """Withheld nodes, the count of published epochs and the mean offset."""
    statuses = {}
    counts = {}
    means = {}
    for node in nodes:
        values = [published[(node, epoch)][0] for epoch in range(1, epochs + 1)
                  if published.get((node, epoch), (None, None))[1] == papers.offset_published]
        counts[node] = len(values)
        if node_component[node]["role"] != papers.role_anchored:
            statuses[node] = papers.withheld_unanchored
        elif not values:
            statuses[node] = papers.withheld_no_data
        else:
            statuses[node] = papers.dissemination_published
        means[node] = sum(values) / len(values) if values else Fraction(0)
    return statuses, counts, means


# --------------------------------------------------------------- the publication

def write_text(path, payload):
    """Every artifact is UTF-8 text with exactly one trailing line feed."""
    path.write_bytes(payload.encode("utf-8"))


def join_delimited(header, rows, delimiter):
    lines = [delimiter.join(header)] + [delimiter.join(row) for row in rows]
    return "\n".join(lines) + "\n"


def json_document(payload, places):
    return json.dumps(render_json(payload, places), indent=2, sort_keys=True,
                      ensure_ascii=True, separators=(",", ": ")) + "\n"


def render_json(value, places):
    if isinstance(value, Whole):
        return round_half_even(as_fraction(value.value))
    if isinstance(value, Ratio):
        return fmt_ratio(value.value, places)
    if isinstance(value, dict):
        return {key: render_json(item, places) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [render_json(item, places) for item in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int):
        return value
    raise Fault("cannot render %r as json" % (value,))


def json_line(payload, places):
    return json.dumps(render_json(payload, places), sort_keys=True,
                      ensure_ascii=True, separators=(",", ":")) + "\n"


class Whole:
    def __init__(self, value):
        self.value = value


class Ratio:
    def __init__(self, value):
        self.value = value


def publish(papers, out):
    """Recompute the interval and write its derived documents."""
    data = papers.data
    places = papers.ratio_places
    canonical, set_aside, instants, links, epochs = stage_t01(papers)
    canonical = stage_t02(papers, canonical, links)
    canonical = stage_t03(papers, canonical)
    components, nodes, usable = stage_t04(papers)
    offsets, dead, tree_link, node_component, path_links = stage_t05(
        papers, canonical, components, epochs)
    catalogue = read_table(data / "oscillator_catalogue.csv")
    series = stage_t06(papers, catalogue, components, node_component, offsets, dead, epochs)
    predictions = stage_t07(papers, catalogue, components)
    dispersion, raw_weights, weight_sources = stage_t08(papers, catalogue, predictions)
    caps = stage_t09(papers, catalogue, raw_weights)
    free = stage_t10(papers, series, predictions, caps["weights"], epochs)
    plan, steered = stage_t11(papers, free, epochs)
    published_offsets, budgets = stage_t12(
        papers, nodes, node_component, offsets, steered, tree_link, path_links, epochs)
    statuses, counts, means = stage_t12_status(papers, nodes, node_component, published_offsets, epochs)

    interval = papers.config["interval_label"]
    revision = papers.config["frozen_register_revision"]
    hub = papers.config["hub_node"]
    order = papers.artifact_order()
    node_report_nodes = papers.node_report_nodes()
    report_nodes = [node for node in node_report_nodes if node in nodes]
    missing = [node for node in node_report_nodes if node not in nodes]
    if missing:
        fault("output_artifact_contract.md", "a named node the register does not carry: %s" % ", ".join(missing))

    payloads = {}

    # reading_ledger.csv
    rows = []
    for reading in sorted(canonical, key=lambda r: (r["link_id"], r["epoch_index"])):
        rows.append([
            reading["link_id"], str(reading["epoch_index"]), reading["row"]["session_id"],
            reading["row"]["receiver_id"], reading["row"]["attempt_no"], reading["row"]["acq_time_s"],
            reading["row"]["raw_offset_ps"], reading["report_id"], fmt_whole(reading["correction_ps"]),
            fmt_whole(reading["corrected_ps"]), reading["sense"], fmt_whole(reading["difference_ps"]),
            str(reading["cluster_rows"]),
        ])
    payloads[READING_LEDGER] = join_delimited(
        ["link_id", "epoch_index", "session_id", "receiver_id", "attempt_no", "acq_time_s",
         "raw_offset_ps", "report_id", "correction_ps", "corrected_ps", "sense", "difference_ps",
         "cluster_rows"], rows, ",")

    # withdrawal_ledger.tsv
    rows = []
    for reason, row, epoch in sorted(
            set_aside, key=lambda item: (item[0], item[1]["link_id"],
                                        papers.no_epoch_token if item[2] is None else str(item[2]),
                                        item[1]["session_id"], int(item[1]["attempt_no"]))):
        rows.append([reason, row["link_id"], papers.no_epoch_token if epoch is None else str(epoch),
                     row["session_id"], row["attempt_no"], row["lock_state"]])
    payloads[WITHDRAWAL_LEDGER] = join_delimited(
        ["drop_reason", "link_id", "epoch_index", "session_id", "attempt_no", "lock_state"], rows, "\t")

    # calibration_selection.csv
    rows = []
    for reading in sorted(canonical, key=lambda r: (r["link_id"], r["epoch_index"])):
        rows.append([
            reading["link_id"], str(reading["epoch_index"]), reading["report_id"], str(reading["revision"]),
            reading["status"], str(reading["effective_epoch_s"]), fmt_whole(reading["correction_ps"]),
        ])
    payloads[CALIBRATION_SELECTION] = join_delimited(
        ["link_id", "epoch_index", "report_id", "revision", "status", "effective_epoch_s",
         "delay_delta_ps"], rows, ",")

    # link_differences.psv
    rows = []
    for reading in sorted(canonical, key=lambda r: (r["epoch_index"], r["link_id"])):
        link = links[reading["link_id"]]
        rows.append([
            str(reading["epoch_index"]), reading["link_id"], link["node_a"], link["node_b"],
            link["technique"], reading["sense"], fmt_whole(reading["difference_ps"]),
        ])
    payloads[LINK_DIFFERENCES] = join_delimited(
        ["epoch_index", "link_id", "node_a", "node_b", "technique", "sense", "difference_ps"], rows, "|")

    # link_graph.json
    graph = {
        "hub_node": hub,
        "component_count": len(components),
        "components": [
            {
                "component_id": component["component_id"],
                "role": component["role"],
                "root_node": component["root_node"],
                "member_nodes": component["member_nodes"],
                "tree_edges": [
                    {"link_id": edge["link_id"], "parent_node": edge["parent_node"],
                     "child_node": edge["child_node"], "technique": edge["technique"],
                     "published_uncertainty_ps": int(edge["published_uncertainty_ps"])}
                    for edge in component["tree_edges"]
                ],
                "excluded_link_ids": component["excluded_link_ids"],
            }
            for component in components
        ],
    }
    payloads[LINK_GRAPH] = json_document(graph, places)

    # deadtime_ledger.jsonl
    records = []
    for epoch, scope, subject, cause in sorted(dead):
        records.append({"epoch_index": epoch, "scope": scope, "subject": subject, "cause": cause})
    payloads[DEADTIME_LEDGER] = "".join(json_line(record, places) for record in records)

    # epoch_grid.csv
    tree_edges = {edge["link_id"] for component in components for edge in component["tree_edges"]}
    epochs_with_reading = {}
    for reading in canonical:
        epochs_with_reading.setdefault(reading["epoch_index"], set()).add(reading["link_id"])
    rows = []
    for epoch in range(1, epochs + 1):
        state = free[epoch]["state"]
        rows.append([
            str(epoch), str(instants[epoch]), str(len(epochs_with_reading.get(epoch, ()))),
            str(len(tree_edges & epochs_with_reading.get(epoch, set()))),
            str(free[epoch]["count"]), state,
        ])
    payloads[EPOCH_GRID] = join_delimited(
        ["epoch_index", "epoch_instant_s", "canonical_readings", "tree_links_present",
         "contributing_oscillators", "epoch_state"], rows, ",")

    # oscillator_series.csv
    rows = []
    for osc in sorted(catalogue, key=lambda o: o["osc_id"]):
        for epoch in range(1, epochs + 1):
            value, flag = series[(osc["osc_id"], epoch)]
            rows.append([
                osc["osc_id"], osc["node_id"], str(epoch),
                "" if value is None else fmt_whole(value), flag,
            ])
    payloads[OSCILLATOR_SERIES] = join_delimited(
        ["osc_id", "node_id", "epoch_index", "deviation_ps", "series_flag"], rows, ",")

    # prediction_book.json
    book = {"window_epochs": int(papers.weighting["history_window_epochs"]),
            "history_minimum": papers.history_minimum,
            "oscillators": []}
    for osc in sorted(catalogue, key=lambda o: o["osc_id"]):
        prediction = predictions[osc["osc_id"]]
        book["oscillators"].append({
            "osc_id": osc["osc_id"], "node_id": osc["node_id"], "osc_class": osc["osc_class"],
            "window_first": prediction["window_first"], "window_last": prediction["window_last"],
            "valid_count": prediction["valid"],
            "anchor_epoch": Whole(prediction["anchor_epoch"]),
            "anchor_deviation_ps": Whole(prediction["anchor_deviation"]),
            "frequency_atto": Whole(round_half_even(prediction["frequency"])),
            "included": prediction["included"], "exclusion_reason": prediction["reason"],
        })
    payloads[PREDICTION_BOOK] = json_document(book, places)

    # dispersion_table.csv
    rows = []
    for osc_id in sorted(dispersion, key=lambda osc: (dispersion[osc], osc)):
        row = next(o for o in catalogue if o["osc_id"] == osc_id)
        rows.append([
            osc_id, row["node_id"], row["osc_class"], str(predictions[osc_id]["valid"]),
            str(dispersion[osc_id]), weight_sources[osc_id], fmt_ratio(raw_weights[osc_id], places),
        ])
    payloads[DISPERSION_TABLE] = join_delimited(
        ["osc_id", "node_id", "osc_class", "valid_count", "dispersion_ps", "weight_source",
         "raw_weight"], rows, ",")

    # weight_book.json
    node_totals = {}
    for osc_id, weight in caps["weights"].items():
        node = next(o["node_id"] for o in catalogue if o["osc_id"] == osc_id)
        node_totals[node] = node_totals.get(node, Fraction(0)) + weight
    weight_book = {
        "ensemble_size": len(caps["weights"]),
        "total_weight": Ratio(caps["total_weight"]),
        "oscillator_cap": Ratio(caps["osc_cap"]),
        "node_cap": Ratio(caps["node_cap"]),
        "oscillator_cap_outcome": caps["osc_outcome"],
        "node_cap_outcome": caps["node_outcome"],
        "final_sweep_outcome": caps["final_outcome"],
        "sweeps_used": caps["sweeps_used"],
        "damping_numerator": caps["damping"].numerator,
        "damping_denominator": caps["damping"].denominator,
        "weight_places": caps["places"],
        "terminal_residual": Ratio(caps["terminal_residual"]),
        "oscillators": [
            {"osc_id": osc_id, "node_id": next(o["node_id"] for o in catalogue if o["osc_id"] == osc_id),
             "raw_weight": Ratio(raw_weights[osc_id]),
             "after_oscillator_cap": Ratio(caps["after_osc"][osc_id]),
             "after_node_cap": Ratio(caps["after_node"][osc_id]),
             "final_weight": Ratio(caps["weights"][osc_id])}
            for osc_id in sorted(caps["weights"])
        ],
        "node_totals": [{"node_id": node, "weight": Ratio(node_totals[node])} for node in sorted(node_totals)],
    }
    payloads[WEIGHT_BOOK] = json_document(weight_book, places)

    # weight_sweep_trace.jsonl
    lines = []
    for record in caps["trace"]:
        lines.append(json_line({
            "phase": record["phase"], "sweep": record["sweep"], "offenders": record["offenders"],
            "excess_ratio": Ratio(record["excess"]), "holders": record["holders"],
            "residual_ratio": Ratio(record["residual"]),
        }, places))
    payloads[WEIGHT_SWEEP_TRACE] = "".join(lines)

    # ensemble_scale.csv
    rows = []
    for epoch in range(1, epochs + 1):
        entry = free[epoch]
        rows.append([
            str(epoch), entry["state"], str(entry["count"]),
            fmt_ratio(entry["denominator"], places),
            "" if entry["value"] is None else fmt_ratio(entry["value"], places),
        ])
    payloads[ENSEMBLE_SCALE] = join_delimited(
        ["epoch_index", "epoch_state", "contributing_oscillators", "denominator_weight",
         "free_scale_ps"], rows, ",")

    # steering_plan.json
    payload = {
        "decision_epoch": plan["decision_epoch"], "horizon_epochs": plan["horizon_epochs"],
        "grid_atto": plan["grid_atto"],
        "departure_ps": Ratio(plan["departure"] if plan["departure"] is not None else Fraction(0)),
        "raw_step_atto": Ratio(plan["raw_step"]),
        "step_atto": Whole(plan["step"]), "outcome": plan["outcome"],
    }
    payloads[STEERING_PLAN] = json_document(payload, places)

    # steered_scale.csv
    rows = []
    for epoch in range(1, epochs + 1):
        value, correction, steered_value = steered[epoch]
        state = free[epoch]["state"]
        rows.append([
            str(epoch), state, "" if value is None else fmt_ratio(value, places),
            fmt_ratio(correction, places),
            "" if steered_value is None else fmt_ratio(steered_value, places),
        ])
    payloads[STEERED_SCALE] = join_delimited(
        ["epoch_index", "epoch_state", "free_scale_ps", "correction_ps", "steered_scale_ps"], rows, ",")

    # node_offsets.csv
    rows = []
    for node in sorted(nodes):
        for epoch in range(1, epochs + 1):
            value, flag = published_offsets[(node, epoch)]
            rows.append([node, str(epoch), "" if value is None else fmt_ratio(value, places), flag])
    payloads[NODE_OFFSETS] = join_delimited(
        ["node_id", "epoch_index", "offset_ps", "offset_flag"], rows, ",")

    # uncertainty_budget.tsv
    rows = []
    for node in sorted(nodes):
        budget = budgets[node]
        rows.append([
            node, budget["component_id"], budget["role"], str(budget["path_length"]),
            str(budget["term_count"]), fmt_whole(budget["u_combined"]), fmt_whole(budget["u_linear"]),
        ])
    payloads[UNCERTAINTY_BUDGET] = join_delimited(
        ["node_id", "component_id", "role", "path_length", "term_count", "u_combined_ps2",
         "u_linear_ps"], rows, "\t")

    # dissemination_ledger.psv
    rows = []
    for node in sorted(nodes, key=lambda n: (-counts[n], n)):
        rows.append([
            node, statuses[node], str(counts[node]), fmt_ratio(means[node], places),
            fmt_whole(budgets[node]["u_combined"]), fmt_whole(budgets[node]["u_linear"]),
        ])
    payloads[DISSEMINATION_LEDGER] = join_delimited(
        ["node_id", "status", "epochs_available", "offset_mean_ps", "u_combined_ps2", "u_linear_ps"],
        rows, "|")

    # loop closures and reconciliation
    closures = []
    unreconciled = []
    excluded_links = {}
    for component in components:
        members = set(component["member_nodes"])
        for link_id in component["excluded_link_ids"]:
            row = usable[link_id]
            if row["node_a"] in members and row["node_b"] in members:
                excluded_links[link_id] = row
    difference = {}
    epochs_of = {}
    for reading in canonical:
        difference[(reading["link_id"], reading["epoch_index"])] = reading["difference_ps"]
        epochs_of.setdefault(reading["link_id"], set()).add(reading["epoch_index"])
    for link_id in sorted(excluded_links):
        row = excluded_links[link_id]
        reached = False
        for epoch in sorted(epochs_of.get(link_id, ())):
            offset_a = offsets.get((row["node_a"], epoch))
            offset_b = offsets.get((row["node_b"], epoch))
            if offset_a is None or offset_b is None:
                continue
            closures.append((link_id, epoch, difference[(link_id, epoch)] - (offset_a - offset_b)))
            reached = True
        if not reached:
            unreconciled.append(link_id)
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', "<network_reconciliation>"]
    xml.append("  <interval>%s</interval>" % interval)
    xml.append('  <closures count="%d">' % len(closures))
    for link_id, epoch, value in sorted(closures, key=lambda item: (item[0], item[1])):
        xml.append("    <closure>")
        xml.append("      <link_id>%s</link_id>" % link_id)
        xml.append("      <epoch_index>%d</epoch_index>" % epoch)
        xml.append("      <closure_ps>%s</closure_ps>" % fmt_whole(value))
        xml.append("    </closure>")
    xml.append("  </closures>")
    xml.append('  <unreconciled count="%d">' % len(unreconciled))
    for link_id in unreconciled:
        xml.append("    <link_id>%s</link_id>" % link_id)
    xml.append("  </unreconciled>")
    xml.append("</network_reconciliation>")
    payloads[RECONCILIATION] = "\n".join(xml) + "\n"

    # per node reports
    for node in report_nodes:
        budget = budgets[node]
        oscillators = []
        for osc in catalogue:
            if osc["node_id"] != node:
                continue
            osc_id = osc["osc_id"]
            prediction = predictions.get(osc_id)
            included = bool(prediction and prediction["included"])
            oscillators.append({
                "osc_id": osc_id, "osc_class": osc["osc_class"], "status": osc["status"],
                "included": included,
                "exclusion_reason": prediction["reason"] if prediction else "",
                "dispersion_ps": Whole(Fraction(dispersion.get(osc_id, 0))),
                "final_weight": Ratio(caps["weights"].get(osc_id, Fraction(0))),
            })
        report = {
            "node_id": node, "component_id": budget["component_id"], "role": budget["role"],
            "register_revision": revision, "reference_oscillator": nodes[node]["reference_oscillator"],
            "path_link_ids": budget["path_link_ids"], "path_length": budget["path_length"],
            "epochs_available": counts[node], "offset_mean_ps": Ratio(means[node]),
            "u_combined_ps2": Whole(budget["u_combined"]), "u_linear_ps": Whole(budget["u_linear"]),
            "status": statuses[node], "oscillators": oscillators,
        }
        payloads[NODE_REPORT_PREFIX + node + NODE_REPORT_SUFFIX] = json_document(report, places)

    # timescale_report.md
    published_nodes = [node for node in sorted(nodes) if statuses[node] == papers.dissemination_published]
    void_epochs = [epoch for epoch in range(1, epochs + 1) if free[epoch]["state"] == papers.epoch_void]
    lines = ["# Timescale report %s" % interval, ""]
    lines += ["## Network", ""]
    lines += ["hub node: %s" % hub, "register revision: %s" % revision,
              "components: %d" % len(components), "registered nodes: %d" % len(nodes),
              "published nodes: %d" % len(published_nodes), ""]
    lines += ["## Readings", ""]
    lines += ["canonical readings: %d" % len(canonical),
              "set aside rows: %d" % len(set_aside),
              "dead time records: %d" % len(dead), ""]
    lines += ["## Ensemble", ""]
    lines += ["oscillators catalogued: %d" % len(catalogue),
              "oscillators weighted: %d" % len(caps["weights"]),
              "oscillator cap outcome: %s" % caps["osc_outcome"],
              "node cap outcome: %s" % caps["node_outcome"],
              "void epochs: %d" % len(void_epochs), ""]
    lines += ["## Steering", ""]
    lines += ["decision epoch: %d" % plan["decision_epoch"],
              "step atto: %d" % round_half_even(plan["step"]),
              "outcome: %s" % plan["outcome"], ""]
    payloads[TIMESCALE_REPORT] = "\n".join(lines)

    # ensemble_summary.md
    lines = ["# Ensemble summary %s" % interval, ""]
    lines += ["| node | status | epochs | offset mean ps | u linear ps |",
              "| --- | --- | --- | --- | --- |"]
    for node in sorted(nodes):
        lines.append("| %s | %s | %d | %s | %d |" % (
            node, statuses[node], counts[node], fmt_ratio(means[node], places),
            round_half_even(budgets[node]["u_linear"])))
    payloads[ENSEMBLE_SUMMARY] = "\n".join(lines) + "\n"

    # node_index.conf
    lines = ["interval = %s" % interval, "hub_node = %s" % hub,
             "register_revision = %s" % revision, "node_count = %d" % len(nodes),
             "published_node_count = %d" % len(published_nodes)]
    for node in sorted(nodes):
        lines.append("node.%s.component = %s" % (node, budgets[node]["component_id"]))
        lines.append("node.%s.status = %s" % (node, statuses[node]))
        lines.append("node.%s.epochs_available = %d" % (node, counts[node]))
    payloads[NODE_INDEX] = "\n".join(lines) + "\n"

    # write every artifact except the manifest, then the manifest
    for name in order:
        if name == MANIFEST:
            continue
        if name not in payloads:
            fault("output_artifact_contract.md", "the artifact %s" % name)
        write_text(out / name, payloads[name])

    core = hashlib.sha256()
    for name in papers.digest_order():
        if name not in payloads:
            fault("ordering_dependencies.yaml", "the core artifact %s" % name)
        core.update((out / name).read_bytes())
    publication = hashlib.sha256()
    for name in order:
        if name != MANIFEST:
            publication.update((out / name).read_bytes())
    document_count, rule_count = papers.manifest_counts()
    manifest = {
        "interval": interval, "document_count": document_count,
        "core_order": papers.digest_order(), "digest": core.hexdigest(),
        "publication_digest": publication.hexdigest(), "rule_count": rule_count,
        "ensemble_size": len(caps["weights"]),
        "oscillator_cap_outcome": caps["osc_outcome"],
        "steering_outcome": plan["outcome"],
    }
    write_text(out / MANIFEST, json_document(manifest, places))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Recompute one publication interval of the array timing network.")
    parser.add_argument("--data", default="/app/data", help="the working papers of the interval")
    parser.add_argument("--out", default="/app/out", help="the directory the publication is written to")
    args = parser.parse_args(argv)
    data = Path(args.data)
    out = Path(args.out)
    if not data.is_dir():
        print("no input directory: %s" % data, file=sys.stderr)
        return 2
    try:
        papers = Papers(data)
        out.mkdir(parents=True, exist_ok=True)
        publish(papers, out)
    except Fault as error:
        print(str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
