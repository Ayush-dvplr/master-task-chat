#!/usr/bin/env python3
"""Recompute a publication interval of the array timing network from its working papers.

Every identifier, count, threshold, control value and vocabulary member is read
from the input directory.  Arithmetic is exact rational throughout; rounding
happens where a stage specification places it and nowhere else.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import zipfile
import zlib
import xml.etree.ElementTree as ET
from fractions import Fraction


class PaperFault(Exception):
    """An input the papers do not describe."""


def fault(paper, field, detail):
    raise PaperFault("%s: field %s: %s" % (paper, field, detail))


# --------------------------------------------------------------------------
# numbers
# --------------------------------------------------------------------------

def half_even(value):
    """Round an exact Fraction to a whole number, half to even."""
    num, den = value.numerator, value.denominator
    quo, rem = divmod(num, den)
    twice = 2 * rem
    if twice > den:
        return quo + 1
    if twice < den:
        return quo
    return quo if quo % 2 == 0 else quo + 1


def whole(value):
    """Render an exact quantity as a whole number; never negative zero."""
    if isinstance(value, Fraction):
        value = half_even(value)
    value = int(value)
    return "0" if value == 0 else str(value)


def ratio(value, places):
    """Render an exact quantity at exactly `places` decimals, half to even."""
    if not isinstance(value, Fraction):
        value = Fraction(value)
    scaled = half_even(value * (10 ** places))
    if scaled == 0:
        return "0." + "0" * places
    sign = "-" if scaled < 0 else ""
    mag = abs(scaled)
    unit = 10 ** places
    return "%s%d.%0*d" % (sign, mag // unit, places, mag % unit)


def trunc_toward_zero(value):
    num, den = value.numerator, value.denominator
    quo = abs(num) // den
    return -quo if num < 0 else quo


# --------------------------------------------------------------------------
# plain text papers
# --------------------------------------------------------------------------

def read_text(root, name):
    path = os.path.join(root, name)
    if not os.path.exists(path):
        raise PaperFault("%s: paper absent from the input directory" % name)
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def read_rows(root, name, delimiter):
    path = os.path.join(root, name)
    if not os.path.exists(path):
        raise PaperFault("%s: paper absent from the input directory" % name)
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if reader.fieldnames is None:
            raise PaperFault("%s: no header row" % name)
        return [dict(row) for row in reader]


def read_yaml(root, name):
    """Minimal reader for the flat mappings and single lists these papers use."""
    out = {}
    key = None
    for line in read_text(root, name).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"^\s+-\s+(.*)$", line)
        if item is not None:
            if key is None:
                fault(name, "-", "list item before any key")
            out.setdefault(key, [])
            if not isinstance(out[key], list):
                out[key] = []
            out[key].append(item.group(1).strip())
            continue
        pair = re.match(r"^([A-Za-z_][\w]*):\s*(.*)$", line)
        if pair is None:
            fault(name, line.strip(), "not a key and value")
        key = pair.group(1)
        value = pair.group(2).strip()
        out[key] = value if value else None
    return out


def need(mapping, paper, field):
    if field not in mapping or mapping[field] is None:
        fault(paper, field, "absent")
    return mapping[field]


def need_int(mapping, paper, field):
    text = str(need(mapping, paper, field))
    if not re.fullmatch(r"-?\d+", text):
        fault(paper, field, "not a whole number: %r" % text)
    return int(text)


def flatten(text):
    """Collapse the line wrapping of a prose paper so a phrase can be matched."""
    return re.sub(r"\s+", " ", text)


def grab(text, pattern, paper, field, group=1):
    found = re.search(pattern, text)
    if found is None:
        fault(paper, field, "not stated")
    return found.group(group)


# --------------------------------------------------------------------------
# the workbook
# --------------------------------------------------------------------------

SSML = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _cell_text(cell, shared):
    kind = cell.get("t")
    if kind == "inlineStr":
        node = cell.find(SSML + "is")
        if node is None:
            return ""
        return "".join(t.text or "" for t in node.iter(SSML + "t"))
    node = cell.find(SSML + "v")
    if node is None:
        return ""
    raw = node.text or ""
    if kind == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError):
            fault("timing_network_workbook.xlsx", cell.get("r"), "bad shared string")
    return raw


def read_workbook(root, name):
    """Return [(sheet_name, {cell_ref: text})] in workbook order."""
    path = os.path.join(root, name)
    if not os.path.exists(path):
        raise PaperFault("%s: paper absent from the input directory" % name)
    with zipfile.ZipFile(path) as archive:
        shared = []
        if "xl/sharedStrings.xml" in archive.namelist():
            sst = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in sst.findall(SSML + "si"):
                shared.append("".join(t.text or "" for t in item.iter(SSML + "t")))
        rels = {}
        rel_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        for rel in rel_root:
            target = rel.get("Target")
            if target.startswith("/"):
                target = target[1:]
            elif not target.startswith("xl/"):
                target = "xl/" + target
            rels[rel.get("Id")] = target
        book = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets = []
        rid_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        for sheet in book.find(SSML + "sheets"):
            part = rels.get(sheet.get(rid_attr))
            if part is None:
                fault(name, sheet.get("name"), "no relationship for the sheet")
            data = ET.fromstring(archive.read(part))
            cells = {}
            for row in data.iter(SSML + "row"):
                for cell in row.iter(SSML + "c"):
                    cells[cell.get("r")] = _cell_text(cell, shared)
            sheets.append((sheet.get("name"), cells))
        return sheets


def sheet_grid(cells):
    """Group a cell map into rows ordered by row number, columns by letter."""
    rows = {}
    for ref, text in cells.items():
        parsed = re.fullmatch(r"([A-Z]+)(\d+)", ref)
        if parsed is None:
            continue
        rows.setdefault(int(parsed.group(2)), {})[parsed.group(1)] = text
    return [rows[n] for n in sorted(rows)]


# --------------------------------------------------------------------------
# the signed memo
# --------------------------------------------------------------------------

def pdf_text(root, name):
    path = os.path.join(root, name)
    if not os.path.exists(path):
        raise PaperFault("%s: paper absent from the input directory" % name)
    with open(path, "rb") as handle:
        blob = handle.read()
    chunks = []
    for match in re.finditer(rb"stream\r?\n", blob):
        start = match.end()
        stop = blob.find(b"endstream", start)
        if stop < 0:
            continue
        body = blob[start:stop]
        try:
            body = zlib.decompress(body)
        except zlib.error:
            pass
        chunks.append(body)
    lines = []
    for chunk in chunks:
        for literal in re.finditer(rb"\((?:[^()\\]|\\.)*\)", chunk):
            text = literal.group(0)[1:-1]
            text = re.sub(rb"\\([()\\])", rb"\1", text)
            lines.append(text.decode("latin-1"))
    if not lines:
        raise PaperFault("%s: no text content found" % name)
    return lines


# --------------------------------------------------------------------------
# control papers
# --------------------------------------------------------------------------

class Papers(object):
    def __init__(self, root):
        self.root = root
        self.config = json.loads(read_text(root, "network_config.json"))
        cfg = "network_config.json"
        for key in ("archive_epochs", "frozen_register_revision", "grid_step_seconds",
                    "hub_node", "interval_epochs", "interval_label",
                    "interval_start_epoch_s", "workbook_sheet_key"):
            if key not in self.config:
                fault(cfg, key, "absent")
        self.interval = self.config["interval_label"]
        self.hub = self.config["hub_node"]
        self.revision = self.config["frozen_register_revision"]
        self.epochs = int(self.config["interval_epochs"])
        self.archive_epochs = int(self.config["archive_epochs"])
        self.grid_step = int(self.config["grid_step_seconds"])
        self.start = int(self.config["interval_start_epoch_s"])

        self.grid_policy = read_yaml(root, "epoch_grid_policy.yaml")
        self.instant_offset = need_int(self.grid_policy, "epoch_grid_policy.yaml",
                                       "grid_instant_offset_s")
        self.tolerance = need_int(self.grid_policy, "epoch_grid_policy.yaml",
                                  "attribution_tolerance_s")

        self.rounding = read_yaml(root, "rounding_policy.yaml")
        self.places = need_int(self.rounding, "rounding_policy.yaml", "ratio_places")

        self.weighting = read_yaml(root, "weighting_policy.yaml")
        wp = "weighting_policy.yaml"
        self.window_epochs = need_int(self.weighting, wp, "history_window_epochs")
        self.archive_valid = need(self.weighting, wp, "valid_archive_flag")
        self.weight_scale = Fraction(need_int(self.weighting, wp, "weight_scale"))
        self.weight_places = need_int(self.weighting, wp, "weight_places")
        self.damp_num = need_int(self.weighting, wp, "damping_numerator")
        self.damp_den = need_int(self.weighting, wp, "damping_denominator")
        self.damping = Fraction(self.damp_num, self.damp_den)

        self.capping = read_yaml(root, "capping_policy.yaml")
        for field in ("first_pass", "second_pass", "third_pass", "redistribution",
                      "grid_placement", "grid_residue"):
            need(self.capping, "capping_policy.yaml", field)

        self.steering = read_yaml(root, "steering_policy.yaml")
        sp = "steering_policy.yaml"
        self.decision_epoch = need_int(self.steering, sp, "decision_epoch")
        self.horizon = need_int(self.steering, sp, "horizon_epochs")
        self.grid_atto = need_int(self.steering, sp, "grid_atto")

        self.ordering = read_yaml(root, "ordering_dependencies.yaml")
        order = need(self.ordering, "ordering_dependencies.yaml", "digest_order")
        if not isinstance(order, list):
            fault("ordering_dependencies.yaml", "digest_order", "not a list")
        self.digest_order = order

        contract = read_text(root, "output_artifact_contract.md")
        self.artifact_order = []
        for line in contract.splitlines():
            row = re.fullmatch(r"\|\s*([\w.]+\.\w+)\s*\|\s*(\w+)\s*\|([^|]*)\|", line.strip())
            if row is None:
                continue
            self.artifact_order.append(row.group(1))
        if not self.artifact_order:
            fault("output_artifact_contract.md", "artifact table", "no rows")
        self.node_report_nodes = [
            re.fullmatch(r"node_report_(.+)\.json", name).group(1)
            for name in self.artifact_order
            if re.fullmatch(r"node_report_(.+)\.json", name)
        ]

        schema = read_text(root, "output_schema_reference.md")
        counts = re.search(r"document_count is (\d+) and rule_count is (\d+)", schema)
        if counts is None:
            fault("output_schema_reference.md", "document_count", "not stated")
        self.document_count = int(counts.group(1))
        self.rule_count = int(counts.group(2))
        self.cause_no_reading = grab(flatten(schema), r"(CAUSE_NO_READING)",
                                     "output_schema_reference.md", "cause for SCOPE_LINK")
        self.cause_no_monitor = grab(flatten(schema), r"(CAUSE_NO_MONITOR)",
                                     "output_schema_reference.md", "cause for SCOPE_OSCILLATOR")

        overview = flatten(read_text(root, "network_contract_overview.md"))
        self.phase_ten_thousandths = int(grab(
            overview, r"exactly (\d+) ten thousandths of a picosecond",
            "network_contract_overview.md", "grid step of one part in ten to the eighteenth"))
        self.phase_unit = Fraction(self.phase_ten_thousandths, 10000)

        # vocabularies
        t01 = read_text(root, "spec_stage_t01_reading_canonicalisation.md")
        self.drop_reasons = re.findall(r"^\s+\d+\.\s+(DR_[A-Z_]+)", t01, re.M)
        if len(self.drop_reasons) != 5:
            fault("spec_stage_t01_reading_canonicalisation.md", "setting rows aside",
                  "expected five ordered predicates, found %d" % len(self.drop_reasons))
        (self.dr_outside, self.dr_withdrawn, self.dr_unregistered,
         self.dr_self_loop, self.dr_no_lock) = self.drop_reasons

        locks = read_text(root, "lock_state_reference.txt")
        self.lock_held = grab(flatten(locks), r"Only (LOCK_[A-Z_]+) makes an attempt eligible",
                              "lock_state_reference.txt", "eligible lock state")
        self.monitor_valid = grab(locks, r"(?m)^(MON_[A-Z_]+)\s+the local monitor measured",
                                  "lock_state_reference.txt", "valid monitor flag")

        t02 = flatten(read_text(root, "spec_stage_t02_delay_calibration.md"))
        self.report_none = grab(t02, r"recorded as (REPORT_[A-Z_]+)",
                                "spec_stage_t02_delay_calibration.md", "absent report id")
        self.cal_absent = grab(t02, r"recorded as (CAL_[A-Z_]+)",
                               "spec_stage_t02_delay_calibration.md", "absent report status")
        self.ns_to_ps = int(grab(t02, r"delay_b_ns\) \* (\d+)",
                                 "spec_stage_t02_delay_calibration.md", "nanosecond scale"))

        techs = read_text(root, "link_technique_reference.txt")
        self.techniques = {}
        for line in techs.splitlines():
            row = re.match(r"^(LK_[A-Z_]+)\s+(SENSE_[A-Z_]+)\s+(\d+)", line)
            if row:
                self.techniques[row.group(1)] = (row.group(2), int(row.group(3)))
        if not self.techniques:
            fault("link_technique_reference.txt", "technique table", "no rows")
        self.sense_a_minus_b = grab(flatten(techs), r"of sense (SENSE_[A-Z_]+) records the clock of node_a",
                                    "link_technique_reference.txt", "A minus B sense")

        t04 = flatten(read_text(root, "spec_stage_t04_link_graph.md"))
        self.role_anchored = grab(t04, r"its role is (ROLE_[A-Z_]+) and its root is the hub",
                                  "spec_stage_t04_link_graph.md", "anchored role")
        self.role_unanchored = grab(t04, r"its role is (ROLE_[A-Z_]+) and its root is the lexicographically",
                                    "spec_stage_t04_link_graph.md", "unanchored role")

        t05 = flatten(read_text(root, "spec_stage_t05_node_offsets.md"))
        self.scope_link = grab(t05, r"recorded with scope (SCOPE_[A-Z_]+)\. A node",
                               "spec_stage_t05_node_offsets.md", "link scope")
        self.scope_node = grab(t05, r"is recorded with scope (SCOPE_[A-Z_]+), naming",
                               "spec_stage_t05_node_offsets.md", "node scope")

        t06 = flatten(read_text(root, "spec_stage_t06_oscillator_series.md"))
        self.scope_osc = grab(t06, r"the absence is recorded with scope (SCOPE_[A-Z_]+)",
                              "spec_stage_t06_oscillator_series.md", "oscillator scope")
        self.ser_measured = grab(t06, r"carries (SER_[A-Z_]+) when its node is in the anchored",
                                 "spec_stage_t06_oscillator_series.md", "measured flag")
        self.ser_unanchored = grab(t06, r"and (SER_[A-Z_]+) when its node is in an unanchored",
                                   "spec_stage_t06_oscillator_series.md", "unanchored flag")
        self.ser_absent = grab(t06, r"at an epoch carries (SER_[A-Z_]+)",
                               "spec_stage_t06_oscillator_series.md", "absent flag")

        t07 = read_text(root, "spec_stage_t07_frequency_prediction.md")
        self.exclusions = re.findall(r"^\s+(EX_[A-Z_]+)\s", t07, re.M)
        if len(self.exclusions) != 4:
            fault("spec_stage_t07_frequency_prediction.md", "exclusions",
                  "expected four ordered reasons, found %d" % len(self.exclusions))
        (self.ex_decommissioned, self.ex_no_archive,
         self.ex_short_history, self.ex_unanchored) = self.exclusions

        classes = read_text(root, "oscillator_class_reference.txt")
        self.os_decommissioned = grab(classes, r"(?m)^(OS_[A-Z_]+)\s+withdrawn from service",
                                      "oscillator_class_reference.txt", "decommissioned status")
        self.osc_classes = re.findall(r"^(OSC_[A-Z_]+)\s{2,}\w", classes, re.M)
        if not self.osc_classes:
            fault("oscillator_class_reference.txt", "class table", "no classes")

        t08 = flatten(read_text(root, "spec_stage_t08_dispersion_and_weight.md"))
        self.ws_dispersion = grab(t08, r"the weight source is (WS_[A-Z_]+)",
                                  "spec_stage_t08_dispersion_and_weight.md", "dispersion source")
        self.ws_ceiling = grab(t08, r"the weight source is\s+(WS_CLASS_[A-Z_]+)",
                               "spec_stage_t08_dispersion_and_weight.md", "ceiling source")

        t09 = flatten(read_text(root, "spec_stage_t09_weight_capping.md"))
        self.osc_cap_num_key = grab(t09, r"oscillator cap = ([A-Z_]+) / ([A-Z_]+)",
                                    "spec_stage_t09_weight_capping.md", "oscillator cap numerator", 1)
        self.osc_cap_den_key = grab(t09, r"oscillator cap = ([A-Z_]+) / ([A-Z_]+)",
                                    "spec_stage_t09_weight_capping.md", "oscillator cap denominator", 2)
        self.node_cap_key = grab(t09, r"node cap\s+= ([A-Z_]+) numerator",
                                 "spec_stage_t09_weight_capping.md", "node cap name")
        self.sweep_budget_key = grab(t09, r"passes already run equals ([A-Z_]+)",
                                     "spec_stage_t09_weight_capping.md", "sweep budget name")
        self.sw_settled = grab(t09, r"above the cap, and record (SW_[A-Z_]+)",
                               "spec_stage_t09_weight_capping.md", "settled outcome")
        self.sw_exhausted = grab(t09, r"still above the cap, and record (SW_[A-Z_]+)",
                                 "spec_stage_t09_weight_capping.md", "budget outcome")
        self.sw_unsatisfiable = grab(t09, r"take the excess, and record (SW_[A-Z_]+)",
                                     "spec_stage_t09_weight_capping.md", "unsatisfiable outcome")
        phases = re.findall(r"(PH_[A-Z_]+)", t09)
        if len(phases) < 3:
            fault("spec_stage_t09_weight_capping.md", "phase names", "fewer than three")
        self.ph_osc, self.ph_node, self.ph_final = phases[0], phases[1], phases[2]

        t10 = flatten(read_text(root, "spec_stage_t10_ensemble_scale.md"))
        self.ep_void = grab(t10, r"Its state is\s+(EP_[A-Z_]+)",
                            "spec_stage_t10_ensemble_scale.md", "void state")
        self.ep_populated = grab(t10, r"Every other epoch has state (EP_[A-Z_]+)",
                                 "spec_stage_t10_ensemble_scale.md", "populated state")

        t11 = flatten(read_text(root, "spec_stage_t11_steering.md"))
        self.st_none = grab(t11, r"the outcome is (ST_[A-Z_]+)",
                            "spec_stage_t11_steering.md", "no realisation outcome")
        self.st_zero = grab(t11, r"becomes zero, and the outcome is (ST_[A-Z_]+)",
                            "spec_stage_t11_steering.md", "truncated outcome")
        self.st_applied = grab(t11, r"Otherwise the\s+outcome is (ST_[A-Z_]+)",
                               "spec_stage_t11_steering.md", "applied outcome")

        t12_raw = read_text(root, "spec_stage_t12_dissemination.md")
        t12 = flatten(t12_raw)
        self.off_absent = grab(t12, r"absent offset with flag (OFF_[A-Z_]+)",
                               "spec_stage_t12_dissemination.md", "absent offset flag")
        self.off_published = grab(t12, r"offset carries (OFF_[A-Z_]+)",
                                  "spec_stage_t12_dissemination.md", "published offset flag")
        statuses = re.findall(r"^\s+(DS_[A-Z_]+)\s", t12_raw, re.M)
        if len(statuses) != 3:
            fault("spec_stage_t12_dissemination.md", "status", "expected three tokens")
        self.ds_unanchored, self.ds_no_data, self.ds_published = statuses

        # the signed memo
        memo_lines = pdf_text(root, "network_calibration_memo.pdf")
        memo = {}
        for line in memo_lines:
            pair = re.fullmatch(r"([A-Z][A-Z0-9_]*)\s*=\s*(-?\d+)", line.strip())
            if pair:
                memo[pair.group(1)] = int(pair.group(2))
        for key in (self.osc_cap_num_key, self.osc_cap_den_key, self.sweep_budget_key):
            if key not in memo:
                fault("network_calibration_memo.pdf", key, "absent")
        self.osc_cap_fraction = Fraction(memo[self.osc_cap_num_key], memo[self.osc_cap_den_key])
        self.sweep_budget = memo[self.sweep_budget_key]
        remaining = [k for k in memo
                     if k not in (self.osc_cap_num_key, self.osc_cap_den_key,
                                  self.sweep_budget_key)]
        if len(remaining) != 1:
            fault("network_calibration_memo.pdf", "history minimum",
                  "could not single out the history minimum among %r" % sorted(memo))
        self.history_min_key = remaining[0]
        self.history_min = memo[self.history_min_key]

        # the live workbook sheet
        wb_name = "timing_network_workbook.xlsx"
        key_wanted = self.config["workbook_sheet_key"]
        live = None
        for sheet_name, cells in read_workbook(root, wb_name):
            if any(text == key_wanted for text in cells.values()):
                if live is not None:
                    fault(wb_name, "workbook key", "more than one sheet carries %r" % key_wanted)
                live = (sheet_name, cells)
        if live is None:
            fault(wb_name, "workbook key", "no sheet carries %r" % key_wanted)
        self.live_sheet_name, live_cells = live
        self.live_sheet_key = key_wanted
        self._load_live_sheet(wb_name, live_cells)

    def _load_live_sheet(self, wb_name, cells):
        grid = sheet_grid(cells)
        self.class_ceiling = {}
        self.node_cap_fraction = None
        self.uncertainty_terms = {}
        order = []
        for row in grid:
            a = row.get("A", "")
            b = row.get("B", "")
            c = row.get("C", "")
            if a in self.osc_classes:
                if not re.fullmatch(r"-?\d+", b):
                    fault(wb_name, a, "ceiling weight is not a whole number: %r" % b)
                self.class_ceiling[a] = Fraction(int(b))
            elif a == self.node_cap_key:
                if not (re.fullmatch(r"-?\d+", b) and re.fullmatch(r"-?\d+", c)):
                    fault(wb_name, a, "node cap is not a pair of whole numbers")
                self.node_cap_fraction = Fraction(int(b), int(c))
            elif re.fullmatch(r"UC_[A-Z_]+", b):
                if not re.fullmatch(r"-?\d+", c):
                    fault(wb_name, a, "uncertainty component is not a whole number: %r" % c)
                self.uncertainty_terms.setdefault(a, [])
                self.uncertainty_terms[a].append((b, int(c)))
                if b not in order:
                    order.append(b)
        if not self.class_ceiling:
            fault(wb_name, "CLASS_CEILING", "no class ceiling weights on the live sheet")
        if self.node_cap_fraction is None:
            fault(wb_name, self.node_cap_key, "absent from the live sheet")
        if not self.uncertainty_terms:
            fault(wb_name, "UNCERTAINTY_COMPONENTS", "no components on the live sheet")
        self.uncertainty_order = order

    def instant(self, k):
        return self.start + (k - 1) * self.grid_step + self.instant_offset

    def phase(self, frequency, steps):
        return Fraction(frequency) * self.phase_unit * steps


# --------------------------------------------------------------------------
# T01 reading canonicalisation
# --------------------------------------------------------------------------

def stage_t01(p, links, sessions, withdrawn):
    instants = {k: p.instant(k) for k in range(1, p.epochs + 1)}
    set_aside = []
    survivors = []
    for row in sessions:
        acq = int(row["acq_time_s"])
        epoch = None
        for k, inst in instants.items():
            if inst - p.tolerance <= acq < inst + p.tolerance:
                epoch = k
                break
        record = {
            "link_id": row["link_id"],
            "epoch_index": epoch,
            "session_id": row["session_id"],
            "receiver_id": row["receiver_id"],
            "attempt_no": int(row["attempt_no"]),
            "acq_time_s": acq,
            "raw_offset_ps": int(row["raw_offset_ps"]),
            "lock_state": row["lock_state"],
        }
        if epoch is None:
            record["drop_reason"] = p.dr_outside
            set_aside.append(record)
            continue
        if row["session_id"] in withdrawn:
            record["drop_reason"] = p.dr_withdrawn
            set_aside.append(record)
            continue
        link = links.get(row["link_id"])
        if link is None:
            record["drop_reason"] = p.dr_unregistered
            set_aside.append(record)
            continue
        if link["node_a"] == link["node_b"]:
            record["drop_reason"] = p.dr_self_loop
            set_aside.append(record)
            continue
        survivors.append(record)

    clusters = {}
    for record in survivors:
        clusters.setdefault((record["link_id"], record["epoch_index"]), []).append(record)

    canonical = {}
    for key, members in clusters.items():
        eligible = [r for r in members if r["lock_state"] == p.lock_held]
        if not eligible:
            for record in members:
                record["drop_reason"] = p.dr_no_lock
                set_aside.append(record)
            continue
        instant = instants[key[1]]
        pick = min(eligible, key=lambda r: (-r["attempt_no"],
                                            abs(r["acq_time_s"] - instant),
                                            r["acq_time_s"]))
        chosen = dict(pick)
        chosen["cluster_rows"] = len(members)
        canonical[key] = chosen
    return canonical, set_aside


# --------------------------------------------------------------------------
# T02 delay calibration
# --------------------------------------------------------------------------

def stage_t02(p, reports, canonical):
    selection = {}
    for key, reading in sorted(canonical.items()):
        link_reports = reports.get(key[0], [])
        governing = [r for r in link_reports if r["effective_epoch_s"] <= reading["acq_time_s"]]
        if governing:
            best = min(governing, key=lambda r: (-r["effective_epoch_s"], r["revision"]))
            correction = (best["delay_a_ns"] - best["delay_b_ns"]) * p.ns_to_ps
            selection[key] = {
                "report_id": best["report_id"],
                "revision": best["revision"],
                "status": best["status"],
                "effective_epoch_s": best["effective_epoch_s"],
                "correction_ps": correction,
                "corrected_ps": reading["raw_offset_ps"] - correction,
            }
        else:
            selection[key] = {
                "report_id": p.report_none,
                "revision": 0,
                "status": p.cal_absent,
                "effective_epoch_s": 0,
                "correction_ps": 0,
                "corrected_ps": reading["raw_offset_ps"],
            }
    return selection


# --------------------------------------------------------------------------
# T03 measurement sense
# --------------------------------------------------------------------------

def stage_t03(p, links, canonical, selection):
    senses = {}
    for key in canonical:
        link = links[key[0]]
        technique = link["technique"]
        if technique not in p.techniques:
            fault("link_register.csv", "technique", "%s is not in the technique reference" % technique)
        sense, _rank = p.techniques[technique]
        corrected = selection[key]["corrected_ps"]
        difference = corrected if sense == p.sense_a_minus_b else -corrected
        senses[key] = {"sense": sense, "difference_ps": difference}
    return senses


# --------------------------------------------------------------------------
# T04 link graph
# --------------------------------------------------------------------------

def stage_t04(p, links, registered):
    usable = {
        lid: link for lid, link in links.items()
        if link["node_a"] in registered and link["node_b"] in registered
        and link["node_a"] != link["node_b"]
    }
    parent = {node: node for node in registered}

    def find(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for link in usable.values():
        a, b = find(link["node_a"]), find(link["node_b"])
        if a != b:
            parent[max(a, b)] = min(a, b)
    groups = {}
    for node in registered:
        groups.setdefault(find(node), []).append(node)
    ordered = sorted(groups.values(), key=lambda members: min(members))

    components = []
    for index, members in enumerate(ordered, start=1):
        members = sorted(members)
        cid = "cmp_%02d" % index
        if p.hub in members:
            role, root = p.role_anchored, p.hub
        else:
            role, root = p.role_unanchored, members[0]
        member_set = set(members)
        own = {lid: link for lid, link in usable.items() if link["node_a"] in member_set}
        reached = {root: Fraction(0)}
        tree_edges = []
        admitted = set()
        while True:
            candidates = []
            for lid, link in sorted(own.items()):
                if lid in admitted:
                    continue
                a, b = link["node_a"], link["node_b"]
                if (a in reached) == (b in reached):
                    continue
                near, far = (a, b) if a in reached else (b, a)
                cost = reached[near] + link["published_uncertainty_ps"]
                rank = p.techniques[link["technique"]][1]
                candidates.append((cost, rank, lid, near, far))
            if not candidates:
                break
            cost, _rank, lid, near, far = min(candidates)
            link = own[lid]
            admitted.add(lid)
            reached[far] = cost
            tree_edges.append({
                "link_id": lid,
                "parent_node": near,
                "child_node": far,
                "technique": link["technique"],
                "published_uncertainty_ps": link["published_uncertainty_ps"],
            })
        excluded = sorted(lid for lid in own if lid not in admitted)
        components.append({
            "component_id": cid,
            "role": role,
            "root_node": root,
            "member_nodes": members,
            "tree_edges": tree_edges,
            "excluded_link_ids": excluded,
        })

    node_component = {}
    node_path = {}
    for comp in components:
        for node in comp["member_nodes"]:
            node_component[node] = comp
        children = {}
        for edge in comp["tree_edges"]:
            children[edge["child_node"]] = edge
        for node in comp["member_nodes"]:
            path = []
            walk = node
            while walk in children:
                edge = children[walk]
                path.append(edge)
                walk = edge["parent_node"]
            node_path[node] = list(reversed(path))
    return components, node_component, node_path


# --------------------------------------------------------------------------
# T05 node offsets and dead time
# --------------------------------------------------------------------------

def stage_t05(p, links, senses, components, node_component, node_path, registered):
    epochs = list(range(1, p.epochs + 1))
    tree_links = set()
    for comp in components:
        for edge in comp["tree_edges"]:
            tree_links.add(edge["link_id"])

    offsets = {}
    deadtime = []
    for epoch in epochs:
        for lid in sorted(tree_links):
            if (lid, epoch) not in senses:
                deadtime.append({"epoch_index": epoch, "scope": p.scope_link,
                                 "subject": lid, "cause": p.cause_no_reading})
    for node in sorted(registered):
        path = node_path[node]
        for epoch in epochs:
            missing = None
            total = Fraction(0)
            for edge in path:
                key = (edge["link_id"], epoch)
                if key not in senses:
                    missing = edge["link_id"]
                    break
                link = links[edge["link_id"]]
                diff = senses[key]["difference_ps"]
                if link["node_a"] == edge["parent_node"]:
                    total += -diff
                else:
                    total += diff
            if missing is None:
                offsets[(node, epoch)] = total
            else:
                offsets[(node, epoch)] = None
                deadtime.append({"epoch_index": epoch, "scope": p.scope_node,
                                 "subject": node, "cause": missing})
    return offsets, deadtime, tree_links


# --------------------------------------------------------------------------
# T06 oscillator deviation series
# --------------------------------------------------------------------------

def stage_t06(p, oscillators, reference, offsets, monitor, node_component, deadtime):
    epochs = list(range(1, p.epochs + 1))
    deviations = {}
    for osc in oscillators:
        oid, node = osc["osc_id"], osc["node_id"]
        comp = node_component.get(node)
        if comp is None:
            fault("oscillator_catalogue.csv", "node_id",
                  "%s is housed at %s, which the frozen register does not carry" % (oid, node))
        anchored = comp["role"] == p.role_anchored
        is_reference = reference.get(node) == oid
        for epoch in epochs:
            base = offsets.get((node, epoch))
            if base is None:
                deviations[(oid, epoch)] = None
                continue
            if is_reference:
                deviations[(oid, epoch)] = (base, p.ser_measured if anchored else p.ser_unanchored)
                continue
            row = monitor.get((oid, epoch))
            if row is None or row["monitor_flag"] != p.monitor_valid:
                deviations[(oid, epoch)] = None
                deadtime.append({"epoch_index": epoch, "scope": p.scope_osc,
                                 "subject": oid, "cause": p.cause_no_monitor})
                continue
            deviations[(oid, epoch)] = (base + row["local_offset_ps"],
                                        p.ser_measured if anchored else p.ser_unanchored)
    return deviations


# --------------------------------------------------------------------------
# T07 frequency prediction
# --------------------------------------------------------------------------

def stage_t07(p, oscillators, archive, node_component):
    first = p.archive_epochs - p.window_epochs + 1
    last = p.archive_epochs
    book = []
    included = {}
    for osc in oscillators:
        oid = osc["osc_id"]
        rows = archive.get(oid, {})
        window = [(n, rows[n]["deviation_ps"]) for n in range(first, last + 1)
                  if n in rows and rows[n]["quality_flag"] == p.archive_valid]
        valid_count = len(window)
        reason = ""
        if osc["status"] == p.os_decommissioned:
            reason = p.ex_decommissioned
        elif not rows:
            reason = p.ex_no_archive
        elif valid_count < p.history_min:
            reason = p.ex_short_history
        elif node_component[osc["node_id"]]["role"] != p.role_anchored:
            reason = p.ex_unanchored
        entry = {
            "osc_id": oid,
            "node_id": osc["node_id"],
            "osc_class": osc["osc_class"],
            "window_first": first,
            "window_last": last,
            "valid_count": valid_count,
            "anchor_epoch": 0,
            "anchor_deviation_ps": 0,
            "frequency": Fraction(0),
            "included": not reason,
            "exclusion_reason": reason,
        }
        if not reason:
            (e0, d0), (e1, d1) = window[0], window[-1]
            if e1 == e0:
                fault("prior_interval_deviations.psv", "archive_epoch",
                      "%s has one valid window epoch and no slope" % oid)
            slope_ps = Fraction(d1 - d0, e1 - e0)
            entry["frequency"] = slope_ps / p.phase_unit
            entry["anchor_epoch"] = e1
            entry["anchor_deviation_ps"] = d1
            entry["window"] = window
            included[oid] = entry
        book.append(entry)
    return book, included, first, last


def prediction_at(p, entry, archive_epoch):
    return (Fraction(entry["anchor_deviation_ps"])
            + p.phase(entry["frequency"], archive_epoch - entry["anchor_epoch"]))


# --------------------------------------------------------------------------
# T08 dispersion and raw weight
# --------------------------------------------------------------------------

def stage_t08(p, included):
    table = []
    for oid in sorted(included):
        entry = included[oid]
        residuals = [Fraction(dev) - prediction_at(p, entry, epoch)
                     for epoch, dev in entry["window"]]
        mean_abs = sum((abs(r) for r in residuals), Fraction(0)) / len(residuals)
        dispersion = half_even(mean_abs)
        if dispersion != 0:
            raw = p.weight_scale / dispersion
            source = p.ws_dispersion
        else:
            ceiling = p.class_ceiling.get(entry["osc_class"])
            if ceiling is None:
                fault("timing_network_workbook.xlsx", entry["osc_class"],
                      "no ceiling weight for the class of %s" % oid)
            raw = ceiling
            source = p.ws_ceiling
        table.append({
            "osc_id": oid,
            "node_id": entry["node_id"],
            "osc_class": entry["osc_class"],
            "valid_count": entry["valid_count"],
            "dispersion_ps": dispersion,
            "weight_source": source,
            "raw_weight": raw,
        })
    return table


# --------------------------------------------------------------------------
# T09 weight capping
# --------------------------------------------------------------------------

def stage_t09(p, dispersion_table):
    unit = Fraction(1, 10 ** p.weight_places)

    def place(value):
        return half_even(value / unit) * unit

    ids = [row["osc_id"] for row in dispersion_table]
    node_of = {row["osc_id"]: row["node_id"] for row in dispersion_table}
    raw = {row["osc_id"]: row["raw_weight"] for row in dispersion_table}
    weights = {oid: place(raw[oid]) for oid in ids}
    total = sum(weights.values(), Fraction(0))
    osc_cap = p.osc_cap_fraction * total
    node_cap = p.node_cap_fraction * total
    carries = {oid: 0 for oid in ids}
    trace = []

    def close_pass(before, target_values, receivers):
        """Place a target vector on the grid and close the residue onto one receiver."""
        placed = {oid: place(target_values[oid]) for oid in ids}
        residue = before - sum(placed.values(), Fraction(0))
        holder = None
        if residue != 0:
            if not receivers:
                fault("spec_stage_t09_weight_capping.md", "grid_residue",
                      "a placement residue with no receiving holder to close it onto")
            holder = min(receivers, key=lambda oid: (carries[oid], -placed[oid], oid))
            placed[holder] = placed[holder] + residue
            carries[holder] += 1
        return placed, holder

    def oscillator_sweep(phase_name, sweep_no):
        before_total = sum(weights.values(), Fraction(0))
        offenders = sorted(oid for oid in ids if weights[oid] > osc_cap)
        receivers = sorted(oid for oid in ids if weights[oid] <= osc_cap)
        offending = set(offenders)
        excess = sum((weights[oid] - osc_cap for oid in offenders), Fraction(0))
        pool = sum((weights[oid] for oid in receivers), Fraction(0))
        target = {}
        for oid in ids:
            if oid in offending:
                target[oid] = osc_cap
            elif pool != 0:
                target[oid] = weights[oid] + excess * weights[oid] / pool
            else:
                target[oid] = weights[oid]
        damped = {oid: weights[oid] + p.damping * (target[oid] - weights[oid]) for oid in ids}
        placed, _holder = close_pass(before_total, damped, receivers)
        residual = sum((abs(placed[oid] - weights[oid]) for oid in ids), Fraction(0))
        for oid in ids:
            weights[oid] = placed[oid]
        trace.append({
            "phase": phase_name,
            "sweep": sweep_no,
            "offenders": offenders,
            "excess_ratio": excess,
            "holders": len(receivers),
            "residual_ratio": residual,
        })
        return residual

    # first pass: damped oscillator cap, run to the sweep budget
    sweeps_used = 0
    while True:
        offenders = [oid for oid in ids if weights[oid] > osc_cap]
        if not offenders:
            osc_outcome = p.sw_settled
            break
        if sweeps_used >= p.sweep_budget:
            osc_outcome = p.sw_exhausted
            break
        if len(offenders) == len(ids):
            osc_outcome = p.sw_unsatisfiable
            break
        sweeps_used += 1
        oscillator_sweep(p.ph_osc, sweeps_used)
    after_osc = dict(weights)

    # second pass: the node cap, taken in full, one pass
    node_weights = {}
    for oid in ids:
        node_weights.setdefault(node_of[oid], Fraction(0))
        node_weights[node_of[oid]] += weights[oid]
    offending_nodes = sorted(n for n, w in node_weights.items() if w > node_cap)
    if not offending_nodes:
        node_outcome = p.sw_settled
    elif len(offending_nodes) == len(node_weights):
        node_outcome = p.sw_unsatisfiable
    else:
        node_outcome = p.sw_settled
        before_total = sum(weights.values(), Fraction(0))
        offending = set(offending_nodes)
        receivers = sorted(oid for oid in ids if node_of[oid] not in offending)
        excess = sum((node_weights[n] - node_cap for n in offending_nodes), Fraction(0))
        pool = sum((weights[oid] for oid in receivers), Fraction(0))
        target = {}
        for oid in ids:
            node = node_of[oid]
            if node in offending:
                target[oid] = weights[oid] * node_cap / node_weights[node]
            elif pool != 0:
                target[oid] = weights[oid] + excess * weights[oid] / pool
            else:
                target[oid] = weights[oid]
        placed, _holder = close_pass(before_total, target, receivers)
        residual = sum((abs(placed[oid] - weights[oid]) for oid in ids), Fraction(0))
        for oid in ids:
            weights[oid] = placed[oid]
        trace.append({
            "phase": p.ph_node,
            "sweep": 1,
            "offenders": offending_nodes,
            "excess_ratio": excess,
            "holders": len(receivers),
            "residual_ratio": residual,
        })
    after_node = dict(weights)

    # third pass: exactly one further damped oscillator sweep
    offenders = [oid for oid in ids if weights[oid] > osc_cap]
    terminal = Fraction(0)
    if not offenders:
        final_outcome = p.sw_settled
    elif len(offenders) == len(ids):
        final_outcome = p.sw_unsatisfiable
    else:
        terminal = oscillator_sweep(p.ph_final, 1)
        still = [oid for oid in ids if weights[oid] > osc_cap]
        final_outcome = p.sw_exhausted if still else p.sw_settled

    node_totals = {}
    for oid in ids:
        node_totals.setdefault(node_of[oid], Fraction(0))
        node_totals[node_of[oid]] += weights[oid]

    return {
        "ids": ids,
        "node_of": node_of,
        "raw": raw,
        "total": total,
        "oscillator_cap": osc_cap,
        "node_cap": node_cap,
        "after_oscillator_cap": after_osc,
        "after_node_cap": after_node,
        "final": dict(weights),
        "oscillator_cap_outcome": osc_outcome,
        "node_cap_outcome": node_outcome,
        "final_sweep_outcome": final_outcome,
        "sweeps_used": sweeps_used,
        "terminal_residual": terminal,
        "trace": trace,
        "node_totals": node_totals,
    }


# --------------------------------------------------------------------------
# T10 the free ensemble scale
# --------------------------------------------------------------------------

def stage_t10(p, included, weights, deviations):
    series = []
    for epoch in range(1, p.epochs + 1):
        numerator = Fraction(0)
        denominator = Fraction(0)
        count = 0
        for oid in sorted(included):
            weight = weights.get(oid)
            if weight is None:
                continue
            entry = deviations.get((oid, epoch))
            if entry is None:
                continue
            residual = entry[0] - prediction_at(p, included[oid], p.archive_epochs + epoch)
            numerator += weight * residual
            denominator += weight
            count += 1
        if count == 0 or denominator == 0:
            series.append({"epoch_index": epoch, "epoch_state": p.ep_void,
                           "contributing": count, "denominator": Fraction(0),
                           "free_scale": None})
        else:
            series.append({"epoch_index": epoch, "epoch_state": p.ep_populated,
                           "contributing": count, "denominator": denominator,
                           "free_scale": numerator / denominator})
    return series


# --------------------------------------------------------------------------
# T11 steering
# --------------------------------------------------------------------------

def stage_t11(p, free_series, realisation):
    by_epoch = {row["epoch_index"]: row for row in free_series}
    decision = by_epoch.get(p.decision_epoch)
    primary = realisation.get(p.decision_epoch)
    departure = Fraction(0)
    raw_step = Fraction(0)
    step = 0
    if decision is None or decision["free_scale"] is None or primary is None:
        outcome = p.st_none
    else:
        departure = decision["free_scale"] - primary
        raw_step = -departure / (p.phase_unit * p.horizon)
        step = trunc_toward_zero(raw_step / p.grid_atto) * p.grid_atto
        outcome = p.st_zero if step == 0 else p.st_applied
    plan = {
        "decision_epoch": p.decision_epoch,
        "horizon_epochs": p.horizon,
        "grid_atto": p.grid_atto,
        "departure_ps": departure,
        "raw_step_atto": raw_step,
        "step_atto": step,
        "outcome": outcome,
    }
    steered = []
    for row in free_series:
        epoch = row["epoch_index"]
        correction = p.phase(step, epoch - p.decision_epoch) if epoch > p.decision_epoch else Fraction(0)
        total = None if row["free_scale"] is None else row["free_scale"] + correction
        steered.append({"epoch_index": epoch, "epoch_state": row["epoch_state"],
                        "free_scale": row["free_scale"], "correction": correction,
                        "steered": total})
    return plan, steered


# --------------------------------------------------------------------------
# T12 dissemination and the uncertainty budget
# --------------------------------------------------------------------------

def stage_t12(p, registered, register_rows, reference, offsets, steered,
              node_component, node_path):
    steered_by_epoch = {row["epoch_index"]: row["steered"] for row in steered}
    published = {}
    for node in sorted(registered):
        for epoch in range(1, p.epochs + 1):
            base = offsets.get((node, epoch))
            scale = steered_by_epoch.get(epoch)
            if base is None or scale is None:
                published[(node, epoch)] = None
            else:
                published[(node, epoch)] = base - scale
    budget = {}
    for node in sorted(registered):
        comp = node_component[node]
        ref = reference[node]
        terms = []
        components = p.uncertainty_terms.get(ref)
        if components is None:
            fault("timing_network_workbook.xlsx", ref,
                  "no uncertainty components for the reference oscillator of %s" % node)
        for name in p.uncertainty_order:
            matching = [value for term, value in components if term == name]
            if not matching:
                fault("timing_network_workbook.xlsx", name,
                      "component absent for oscillator %s" % ref)
            terms.extend(matching)
        terms.append(register_rows[node]["declared_uncertainty_ps"])
        for edge in node_path[node]:
            terms.append(edge["published_uncertainty_ps"])
        available = sum(1 for epoch in range(1, p.epochs + 1)
                        if published[(node, epoch)] is not None)
        values = [published[(node, epoch)] for epoch in range(1, p.epochs + 1)
                  if published[(node, epoch)] is not None]
        mean = sum(values, Fraction(0)) / len(values) if values else Fraction(0)
        if comp["role"] != p.role_anchored:
            status = p.ds_unanchored
        elif available == 0:
            status = p.ds_no_data
        else:
            status = p.ds_published
        budget[node] = {
            "component_id": comp["component_id"],
            "role": comp["role"],
            "path_length": len(node_path[node]),
            "term_count": len(terms),
            "u_combined_ps2": sum(t * t for t in terms),
            "u_linear_ps": sum(terms),
            "epochs_available": available,
            "offset_mean_ps": mean,
            "status": status,
        }
    return published, budget


# --------------------------------------------------------------------------
# T13 loop closures
# --------------------------------------------------------------------------

def stage_t13_closures(p, links, components, senses, offsets):
    closures = []
    unreconciled = []
    excluded = []
    for comp in components:
        excluded.extend(comp["excluded_link_ids"])
    for lid in sorted(excluded):
        link = links[lid]
        found = False
        for epoch in range(1, p.epochs + 1):
            key = (lid, epoch)
            if key not in senses:
                continue
            a = offsets.get((link["node_a"], epoch))
            b = offsets.get((link["node_b"], epoch))
            if a is None or b is None:
                continue
            closures.append({"link_id": lid, "epoch_index": epoch,
                             "closure_ps": senses[key]["difference_ps"] - (a - b)})
            found = True
        if not found:
            unreconciled.append(lid)
    closures.sort(key=lambda c: (c["link_id"], c["epoch_index"]))
    return closures, sorted(unreconciled)


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------

class Publication(object):
    def __init__(self, out_dir):
        self.out_dir = out_dir
        self.bytes = {}

    def write(self, name, text):
        data = text.encode("utf-8")
        self.bytes[name] = data
        with open(os.path.join(self.out_dir, name), "wb") as handle:
            handle.write(data)

    def delimited(self, name, header, rows, delimiter):
        lines = [delimiter.join(header)]
        lines.extend(delimiter.join(row) for row in rows)
        self.write(name, "\n".join(lines) + "\n")

    def json_doc(self, name, obj):
        self.write(name, json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n")

    def json_lines(self, name, records):
        if not records:
            self.write(name, "")
            return
        lines = [json.dumps(r, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
                 for r in records]
        self.write(name, "\n".join(lines) + "\n")


def run(data_dir, out_dir):
    p = Papers(data_dir)
    places = p.places
    ratio_zero = ratio(Fraction(0), places)

    # registers and logs
    link_rows = read_rows(data_dir, "link_register.csv", ",")
    links = {}
    for row in link_rows:
        links[row["link_id"]] = {
            "link_id": row["link_id"],
            "node_a": row["node_a"],
            "node_b": row["node_b"],
            "technique": row["technique"],
            "published_uncertainty_ps": int(row["published_uncertainty_ps"]),
        }

    register_all = read_rows(data_dir, "node_register_frozen.csv", ",")
    register_rows = {}
    for row in register_all:
        if row["register_revision"] == p.revision:
            register_rows[row["node_id"]] = {
                "site_class": row["site_class"],
                "reference_oscillator": row["reference_oscillator"],
                "declared_uncertainty_ps": int(row["declared_uncertainty_ps"]),
            }
    if not register_rows:
        fault("node_register_frozen.csv", "register_revision",
              "no rows at the frozen revision %s" % p.revision)
    registered = sorted(register_rows)
    reference = {n: register_rows[n]["reference_oscillator"] for n in registered}

    sessions = read_rows(data_dir, "comparison_session_log.csv", ",")
    journal = read_rows(data_dir, "session_withdrawal_journal.tsv", "\t")
    withdrawn = set(row["session_id"] for row in journal)

    reports = {}
    ledger = read_rows(data_dir, "delay_calibration_ledger.csv", ",")
    supplement = read_rows(data_dir, "delay_calibration_supplement.psv", "|")
    for row in ledger + supplement:
        reports.setdefault(row["link_id"], []).append({
            "report_id": row["report_id"],
            "effective_epoch_s": int(row["effective_epoch_s"]),
            "issued_epoch_s": int(row["issued_epoch_s"]),
            "revision": int(row["revision"]),
            "delay_a_ns": int(row["delay_a_ns"]),
            "delay_b_ns": int(row["delay_b_ns"]),
            "status": row["status"],
        })

    catalogue_rows = read_rows(data_dir, "oscillator_catalogue.csv", ",")
    oscillators = [{"osc_id": r["osc_id"], "node_id": r["node_id"],
                    "osc_class": r["osc_class"], "status": r["status"]}
                   for r in catalogue_rows]

    monitor_rows = read_rows(data_dir, "local_comparison_log.psv", "|")
    monitor = {}
    for row in monitor_rows:
        monitor[(row["osc_id"], int(row["epoch_index"]))] = {
            "local_offset_ps": int(row["local_offset_ps"]),
            "monitor_flag": row["monitor_flag"],
        }

    archive_rows = read_rows(data_dir, "prior_interval_deviations.psv", "|")
    archive = {}
    for row in archive_rows:
        archive.setdefault(row["osc_id"], {})[int(row["archive_epoch"])] = {
            "deviation_ps": int(row["deviation_ps"]),
            "quality_flag": row["quality_flag"],
        }

    realisation_rows = read_rows(data_dir, "primary_standard_realisation.csv", ",")
    realisation = {}
    for row in realisation_rows:
        text = row["realisation_ps"].strip()
        realisation[int(row["epoch_index"])] = Fraction(int(text)) if text else None
    realisation = {k: v for k, v in realisation.items() if v is not None}

    # the chain
    canonical, set_aside = stage_t01(p, links, sessions, withdrawn)
    selection = stage_t02(p, reports, canonical)
    senses = stage_t03(p, links, canonical, selection)
    components, node_component, node_path = stage_t04(p, links, set(registered))
    offsets, deadtime, tree_links = stage_t05(p, links, senses, components,
                                              node_component, node_path, registered)
    deviations = stage_t06(p, oscillators, reference, offsets, monitor,
                           node_component, deadtime)
    book, included, window_first, window_last = stage_t07(p, oscillators, archive,
                                                          node_component)
    dispersion_table = stage_t08(p, included)
    caps = stage_t09(p, dispersion_table)
    free_series = stage_t10(p, included, caps["final"], deviations)
    plan, steered = stage_t11(p, free_series, realisation)
    published, budget = stage_t12(p, registered, register_rows, reference, offsets,
                                  steered, node_component, node_path)
    closures, unreconciled = stage_t13_closures(p, links, components, senses, offsets)

    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    pub = Publication(out_dir)

    # reading_ledger.csv
    rows = []
    for key in sorted(canonical, key=lambda k: (k[0], k[1])):
        reading = canonical[key]
        cal = selection[key]
        sense = senses[key]
        rows.append([
            key[0], whole(key[1]), reading["session_id"], reading["receiver_id"],
            whole(reading["attempt_no"]), whole(reading["acq_time_s"]),
            whole(reading["raw_offset_ps"]), cal["report_id"],
            whole(cal["correction_ps"]), whole(cal["corrected_ps"]),
            sense["sense"], whole(sense["difference_ps"]), whole(reading["cluster_rows"]),
        ])
    pub.delimited("reading_ledger.csv",
                  ["link_id", "epoch_index", "session_id", "receiver_id", "attempt_no",
                   "acq_time_s", "raw_offset_ps", "report_id", "correction_ps",
                   "corrected_ps", "sense", "difference_ps", "cluster_rows"], rows, ",")

    # withdrawal_ledger.tsv
    rows = []
    for record in set_aside:
        epoch = "NONE" if record["epoch_index"] is None else whole(record["epoch_index"])
        rows.append([record["drop_reason"], record["link_id"], epoch,
                     record["session_id"], whole(record["attempt_no"]),
                     record["lock_state"]])
    rows.sort(key=lambda r: (r[0], r[1], r[2], r[3], int(r[4])))
    pub.delimited("withdrawal_ledger.tsv",
                  ["drop_reason", "link_id", "epoch_index", "session_id", "attempt_no",
                   "lock_state"], rows, "\t")

    # calibration_selection.csv
    rows = []
    for key in sorted(canonical, key=lambda k: (k[0], k[1])):
        cal = selection[key]
        rows.append([key[0], whole(key[1]), cal["report_id"], whole(cal["revision"]),
                     cal["status"], whole(cal["effective_epoch_s"]),
                     whole(cal["correction_ps"])])
    pub.delimited("calibration_selection.csv",
                  ["link_id", "epoch_index", "report_id", "revision", "status",
                   "effective_epoch_s", "delay_delta_ps"], rows, ",")

    # link_differences.psv
    rows = []
    for key in sorted(canonical, key=lambda k: (k[1], k[0])):
        link = links[key[0]]
        sense = senses[key]
        rows.append([whole(key[1]), key[0], link["node_a"], link["node_b"],
                     link["technique"], sense["sense"], whole(sense["difference_ps"])])
    pub.delimited("link_differences.psv",
                  ["epoch_index", "link_id", "node_a", "node_b", "technique", "sense",
                   "difference_ps"], rows, "|")

    # link_graph.json
    pub.json_doc("link_graph.json", {
        "hub_node": p.hub,
        "component_count": len(components),
        "components": [{
            "component_id": c["component_id"],
            "role": c["role"],
            "root_node": c["root_node"],
            "member_nodes": c["member_nodes"],
            "tree_edges": [{
                "link_id": e["link_id"],
                "parent_node": e["parent_node"],
                "child_node": e["child_node"],
                "technique": e["technique"],
                "published_uncertainty_ps": e["published_uncertainty_ps"],
            } for e in c["tree_edges"]],
            "excluded_link_ids": c["excluded_link_ids"],
        } for c in components],
    })

    # epoch_grid.csv
    free_by_epoch = {row["epoch_index"]: row for row in free_series}
    rows = []
    for epoch in range(1, p.epochs + 1):
        readings = sum(1 for key in canonical if key[1] == epoch)
        present = sum(1 for lid in tree_links if (lid, epoch) in senses)
        state = free_by_epoch[epoch]
        rows.append([whole(epoch), whole(p.instant(epoch)), whole(readings),
                     whole(present), whole(state["contributing"]), state["epoch_state"]])
    pub.delimited("epoch_grid.csv",
                  ["epoch_index", "epoch_instant_s", "canonical_readings",
                   "tree_links_present", "contributing_oscillators", "epoch_state"],
                  rows, ",")

    # deadtime_ledger.jsonl
    records = sorted(deadtime, key=lambda r: (r["epoch_index"], r["scope"],
                                              r["subject"], r["cause"]))
    pub.json_lines("deadtime_ledger.jsonl", [
        {"epoch_index": r["epoch_index"], "scope": r["scope"],
         "subject": r["subject"], "cause": r["cause"]} for r in records])

    # oscillator_series.csv
    rows = []
    for osc in sorted(oscillators, key=lambda o: o["osc_id"]):
        for epoch in range(1, p.epochs + 1):
            entry = deviations.get((osc["osc_id"], epoch))
            if entry is None:
                rows.append([osc["osc_id"], osc["node_id"], whole(epoch), "", p.ser_absent])
            else:
                rows.append([osc["osc_id"], osc["node_id"], whole(epoch),
                             whole(entry[0]), entry[1]])
    pub.delimited("oscillator_series.csv",
                  ["osc_id", "node_id", "epoch_index", "deviation_ps", "series_flag"],
                  rows, ",")

    # prediction_book.json
    pub.json_doc("prediction_book.json", {
        "window_epochs": p.window_epochs,
        "history_minimum": p.history_min,
        "oscillators": [{
            "osc_id": e["osc_id"],
            "node_id": e["node_id"],
            "osc_class": e["osc_class"],
            "window_first": e["window_first"],
            "window_last": e["window_last"],
            "valid_count": e["valid_count"],
            "anchor_epoch": e["anchor_epoch"],
            "anchor_deviation_ps": e["anchor_deviation_ps"],
            "frequency_atto": half_even(e["frequency"]),
            "included": e["included"],
            "exclusion_reason": e["exclusion_reason"],
        } for e in sorted(book, key=lambda e: e["osc_id"])],
    })

    # dispersion_table.csv
    rows = []
    for row in sorted(dispersion_table, key=lambda r: (r["dispersion_ps"], r["osc_id"])):
        rows.append([row["osc_id"], row["node_id"], row["osc_class"],
                     whole(row["valid_count"]), whole(row["dispersion_ps"]),
                     row["weight_source"], ratio(row["raw_weight"], places)])
    pub.delimited("dispersion_table.csv",
                  ["osc_id", "node_id", "osc_class", "valid_count", "dispersion_ps",
                   "weight_source", "raw_weight"], rows, ",")

    # weight_book.json
    pub.json_doc("weight_book.json", {
        "ensemble_size": len(caps["ids"]),
        "total_weight": ratio(caps["total"], places),
        "oscillator_cap": ratio(caps["oscillator_cap"], places),
        "node_cap": ratio(caps["node_cap"], places),
        "oscillator_cap_outcome": caps["oscillator_cap_outcome"],
        "node_cap_outcome": caps["node_cap_outcome"],
        "final_sweep_outcome": caps["final_sweep_outcome"],
        "sweeps_used": caps["sweeps_used"],
        "damping_numerator": p.damp_num,
        "damping_denominator": p.damp_den,
        "weight_places": p.weight_places,
        "terminal_residual": ratio(caps["terminal_residual"], places),
        "oscillators": [{
            "osc_id": oid,
            "node_id": caps["node_of"][oid],
            "raw_weight": ratio(caps["raw"][oid], places),
            "after_oscillator_cap": ratio(caps["after_oscillator_cap"][oid], places),
            "after_node_cap": ratio(caps["after_node_cap"][oid], places),
            "final_weight": ratio(caps["final"][oid], places),
        } for oid in sorted(caps["ids"])],
        "node_totals": [{"node_id": node, "weight": ratio(caps["node_totals"][node], places)}
                        for node in sorted(caps["node_totals"])],
    })

    # weight_sweep_trace.jsonl
    pub.json_lines("weight_sweep_trace.jsonl", [{
        "phase": t["phase"],
        "sweep": t["sweep"],
        "offenders": t["offenders"],
        "excess_ratio": ratio(t["excess_ratio"], places),
        "holders": t["holders"],
        "residual_ratio": ratio(t["residual_ratio"], places),
    } for t in caps["trace"]])

    # ensemble_scale.csv
    rows = []
    for row in free_series:
        rows.append([whole(row["epoch_index"]), row["epoch_state"],
                     whole(row["contributing"]), ratio(row["denominator"], places),
                     "" if row["free_scale"] is None else whole(row["free_scale"])])
    pub.delimited("ensemble_scale.csv",
                  ["epoch_index", "epoch_state", "contributing_oscillators",
                   "denominator_weight", "free_scale_ps"], rows, ",")

    # steering_plan.json
    pub.json_doc("steering_plan.json", {
        "decision_epoch": plan["decision_epoch"],
        "horizon_epochs": plan["horizon_epochs"],
        "grid_atto": plan["grid_atto"],
        "departure_ps": ratio(plan["departure_ps"], places),
        "raw_step_atto": ratio(plan["raw_step_atto"], places),
        "step_atto": plan["step_atto"],
        "outcome": plan["outcome"],
    })

    # steered_scale.csv
    rows = []
    for row in steered:
        rows.append([whole(row["epoch_index"]), row["epoch_state"],
                     "" if row["free_scale"] is None else whole(row["free_scale"]),
                     whole(row["correction"]),
                     "" if row["steered"] is None else whole(row["steered"])])
    pub.delimited("steered_scale.csv",
                  ["epoch_index", "epoch_state", "free_scale_ps", "correction_ps",
                   "steered_scale_ps"], rows, ",")

    # node_offsets.csv
    rows = []
    for node in registered:
        for epoch in range(1, p.epochs + 1):
            value = published[(node, epoch)]
            if value is None:
                rows.append([node, whole(epoch), "", p.off_absent])
            else:
                rows.append([node, whole(epoch), whole(value), p.off_published])
    pub.delimited("node_offsets.csv",
                  ["node_id", "epoch_index", "offset_ps", "offset_flag"], rows, ",")

    # uncertainty_budget.tsv
    rows = []
    for node in registered:
        b = budget[node]
        rows.append([node, b["component_id"], b["role"], whole(b["path_length"]),
                     whole(b["term_count"]), whole(b["u_combined_ps2"]),
                     whole(b["u_linear_ps"])])
    pub.delimited("uncertainty_budget.tsv",
                  ["node_id", "component_id", "role", "path_length", "term_count",
                   "u_combined_ps2", "u_linear_ps"], rows, "\t")

    # dissemination_ledger.psv
    rows = []
    for node in sorted(registered, key=lambda n: (-budget[n]["epochs_available"], n)):
        b = budget[node]
        rows.append([node, b["status"], whole(b["epochs_available"]),
                     ratio(b["offset_mean_ps"], places), whole(b["u_combined_ps2"]),
                     whole(b["u_linear_ps"])])
    pub.delimited("dissemination_ledger.psv",
                  ["node_id", "status", "epochs_available", "offset_mean_ps",
                   "u_combined_ps2", "u_linear_ps"], rows, "|")

    # node reports
    dispersion_by_osc = {row["osc_id"]: row for row in dispersion_table}
    book_by_osc = {e["osc_id"]: e for e in book}
    for node in p.node_report_nodes:
        if node not in budget:
            fault("output_artifact_contract.md", "node_report_%s.json" % node,
                  "the frozen register does not carry %s" % node)
        b = budget[node]
        entries = []
        for osc in oscillators:
            if osc["node_id"] != node:
                continue
            entry = book_by_osc[osc["osc_id"]]
            disp = dispersion_by_osc.get(osc["osc_id"])
            weight = caps["final"].get(osc["osc_id"])
            entries.append({
                "osc_id": osc["osc_id"],
                "osc_class": osc["osc_class"],
                "status": osc["status"],
                "included": entry["included"],
                "exclusion_reason": entry["exclusion_reason"],
                "dispersion_ps": disp["dispersion_ps"] if disp else 0,
                "final_weight": ratio(weight if weight is not None else Fraction(0), places),
            })
        pub.json_doc("node_report_%s.json" % node, {
            "node_id": node,
            "component_id": b["component_id"],
            "role": b["role"],
            "register_revision": p.revision,
            "reference_oscillator": reference[node],
            "path_link_ids": [e["link_id"] for e in node_path[node]],
            "path_length": b["path_length"],
            "epochs_available": b["epochs_available"],
            "offset_mean_ps": ratio(b["offset_mean_ps"], places),
            "u_combined_ps2": b["u_combined_ps2"],
            "u_linear_ps": b["u_linear_ps"],
            "status": b["status"],
            "oscillators": entries,
        })

    # network_reconciliation.xml
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<network_reconciliation>",
             "  <interval>%s</interval>" % p.interval]
    if closures:
        lines.append('  <closures count="%d">' % len(closures))
        for c in closures:
            lines.append("    <closure><link_id>%s</link_id><epoch_index>%s</epoch_index>"
                         "<closure_ps>%s</closure_ps></closure>"
                         % (c["link_id"], whole(c["epoch_index"]), whole(c["closure_ps"])))
        lines.append("  </closures>")
    else:
        lines.append('  <closures count="0"></closures>')
    inner = "".join("<link_id>%s</link_id>" % lid for lid in unreconciled)
    lines.append('  <unreconciled count="%d">%s</unreconciled>' % (len(unreconciled), inner))
    lines.append("</network_reconciliation>")
    pub.write("network_reconciliation.xml", "\n".join(lines) + "\n")

    # timescale_report.md
    published_nodes = [n for n in registered if budget[n]["status"] == p.ds_published]
    void_epochs = sum(1 for row in free_series if row["epoch_state"] == p.ep_void)
    weighted = sum(1 for oid in caps["ids"] if oid in caps["final"])
    report = [
        "# Timescale report %s" % p.interval, "",
        "## Network", "",
        "hub node: %s" % p.hub,
        "register revision: %s" % p.revision,
        "components: %d" % len(components),
        "registered nodes: %d" % len(registered),
        "published nodes: %d" % len(published_nodes), "",
        "## Readings", "",
        "canonical readings: %d" % len(canonical),
        "set aside rows: %d" % len(set_aside),
        "dead time records: %d" % len(deadtime), "",
        "## Ensemble", "",
        "oscillators catalogued: %d" % len(oscillators),
        "oscillators weighted: %d" % weighted,
        "oscillator cap outcome: %s" % caps["oscillator_cap_outcome"],
        "node cap outcome: %s" % caps["node_cap_outcome"],
        "void epochs: %d" % void_epochs, "",
        "## Steering", "",
        "decision epoch: %d" % plan["decision_epoch"],
        "step atto: %s" % whole(plan["step_atto"]),
        "outcome: %s" % plan["outcome"],
    ]
    pub.write("timescale_report.md", "\n".join(report) + "\n")

    # ensemble_summary.md
    lines = ["# Ensemble summary %s" % p.interval, "",
             "| node | status | epochs | offset mean ps | u linear ps |",
             "| --- | --- | --- | --- | --- |"]
    for node in registered:
        b = budget[node]
        lines.append("| %s | %s | %s | %s | %s |" % (
            node, b["status"], whole(b["epochs_available"]),
            ratio(b["offset_mean_ps"], places), whole(b["u_linear_ps"])))
    pub.write("ensemble_summary.md", "\n".join(lines) + "\n")

    # node_index.conf
    lines = ["interval = %s" % p.interval,
             "hub_node = %s" % p.hub,
             "register_revision = %s" % p.revision,
             "node_count = %d" % len(registered),
             "published_node_count = %d" % len(published_nodes)]
    for node in registered:
        b = budget[node]
        lines.append("%s.component = %s" % (node, b["component_id"]))
        lines.append("%s.status = %s" % (node, b["status"]))
        lines.append("%s.epochs_available = %s" % (node, whole(b["epochs_available"])))
    pub.write("node_index.conf", "\n".join(lines) + "\n")

    # publication_manifest.json, written last
    manifest_name = "publication_manifest.json"
    core = hashlib.sha256()
    for name in p.digest_order:
        if name not in pub.bytes:
            fault("ordering_dependencies.yaml", "digest_order", "%s was not written" % name)
        core.update(pub.bytes[name])
    whole_pub = hashlib.sha256()
    for name in p.artifact_order:
        if name == manifest_name:
            continue
        if name not in pub.bytes:
            fault("output_artifact_contract.md", name, "artifact was not written")
        whole_pub.update(pub.bytes[name])
    pub.json_doc(manifest_name, {
        "interval": p.interval,
        "document_count": p.document_count,
        "core_order": list(p.digest_order),
        "digest": core.hexdigest(),
        "publication_digest": whole_pub.hexdigest(),
        "rule_count": p.rule_count,
        "ensemble_size": len(caps["ids"]),
        "oscillator_cap_outcome": caps["oscillator_cap_outcome"],
        "steering_outcome": plan["outcome"],
    })
    return pub


def main(argv=None):
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--data", default=os.path.join(os.path.dirname(here), "data"))
    parser.add_argument("--out", default=here)
    args = parser.parse_args(argv)
    try:
        run(os.path.abspath(args.data), os.path.abspath(args.out))
    except PaperFault as problem:
        sys.stderr.write("fault: %s\n" % problem)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
