"""Recompute one publication interval of the array timing network.

The desk keeps this program and points it at the working papers of an
interval. It reads the thirteen stage specifications' inputs out of that
directory, runs the chain in exact rational arithmetic and writes the
publication beside them.

Nothing about any one interval is held here. Every identifier, count,
threshold, control value and vocabulary member is read from the directory the
program is pointed at, including the four control values in the signed memo
and the class ceilings, the node cap and the uncertainty components on the
live sheet of the workbook.

    python3 timescale.py --data <input directory> --out <output directory>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ElementTree
import zipfile
from fractions import Fraction

DEFAULT_DATA = "/app" + "/data"
DEFAULT_OUT = "/app" + "/out"

SPREADSHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
RELATION_ID = ("{http://schemas.openxmlformats.org/officeDocument/2006/"
               "relationships}id")


class PaperFault(Exception):
    """An input the papers do not describe.

    The program says which paper and which field rather than guessing a value.
    """


def fault(paper: str, field: str) -> "PaperFault":
    return PaperFault("%s: the paper does not describe %s" % (paper, field))


# ---------------------------------------------------------------------------
# arithmetic and rendering
#
# Every quantity is an int or a Fraction until it is written. The two carried
# roundings the chain names, the published dispersion of T08 and the grid
# placement of every capping pass of T09, are applied where those stages place
# them and nowhere else.
# ---------------------------------------------------------------------------

def to_int(text) -> int:
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        raise PaperFault("a whole number was expected and %r was found" % (text,))


def nearest_even(value: Fraction) -> int:
    """The rounding policy's round_half_even, on an exact rational."""
    value = Fraction(value)
    low = value.numerator // value.denominator
    rest = value - low
    if rest < Fraction(1, 2):
        return low
    if rest > Fraction(1, 2):
        return low + 1
    return low if low % 2 == 0 else low + 1


def toward_zero(value: Fraction) -> int:
    """The steering policy's truncate_toward_zero."""
    value = Fraction(value)
    magnitude = abs(value.numerator) // value.denominator
    return -magnitude if value < 0 else magnitude


def whole(value) -> str:
    """A whole number as the serialisation contract writes it."""
    number = int(value)
    return "0" if number == 0 else str(number)


def place(value: Fraction, places: int) -> Fraction:
    """Put an exact value on a decimal grid of the given width."""
    scale = 10 ** places
    return Fraction(nearest_even(Fraction(value) * scale), scale)


def ratio(value, places: int) -> str:
    """A ratio at the rounding policy's ratio_places, half to even.

    A ratio that rounds to zero is written as zero whatever its sign, so the
    publication carries no negative zero.
    """
    units = nearest_even(Fraction(value) * (10 ** places))
    if units == 0:
        return "0." + "0" * places
    sign = "-" if units < 0 else ""
    digits = str(abs(units)).rjust(places + 1, "0")
    return "%s%s.%s" % (sign, digits[:-places], digits[-places:])


class Units:
    """The grid the network carries frequency on.

    Frequency is held in parts in ten to the eighteenth and phase in
    picoseconds, so one unit of frequency held over one grid step of
    grid_step_seconds moves the phase by grid_step_seconds * 10**12 / 10**18
    picoseconds, 864 ten thousandths of a picosecond at a step of one day.
    """

    PICOSECONDS_PER_SECOND = 10 ** 12
    FREQUENCY_SCALE = 10 ** 18

    def __init__(self, step_s: int):
        self.step_ps = Fraction(step_s * self.PICOSECONDS_PER_SECOND, self.FREQUENCY_SCALE)

    def phase(self, frequency: Fraction, steps: int) -> Fraction:
        return Fraction(frequency) * steps * self.step_ps

    def slope(self, rise_ps: Fraction, run_steps: int) -> Fraction:
        if run_steps == 0:
            raise PaperFault("a slope over zero grid steps has no frequency")
        return Fraction(rise_ps) / (run_steps * self.step_ps)


# ---------------------------------------------------------------------------
# readers, written against the shipped formats
# ---------------------------------------------------------------------------

def read_text(path) -> str:
    """Read a paper, naming it when the directory does not carry one."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError:
        raise PaperFault("%s: the directory carries no such paper"
                         % os.path.basename(str(path)))


def read_rows(path, separator: str) -> list:
    """A delimited paper as a list of dictionaries.

    No field is quoted and no field carries its delimiter, which the
    serialisation contract states of every delimited artifact of this network,
    so the split is the whole of the parse.
    """
    lines = read_text(path).splitlines()
    if not lines:
        return []
    names = lines[0].split(separator)
    out = []
    for line in lines[1:]:
        if not line:
            continue
        cells = line.split(separator)
        if len(cells) < len(names):
            cells = cells + [""] * (len(names) - len(cells))
        out.append(dict(zip(names, cells)))
    return out


def read_json(path):
    return json.loads(read_text(path))


def read_settings(path) -> dict:
    """A policy paper: comment lines, `key: value` and `- item` list members."""
    settings = {}
    key_of_list = None
    for line in read_text(path).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.lstrip().startswith("- "):
            if key_of_list is None:
                continue
            settings[key_of_list].append(line.lstrip()[2:].strip())
            continue
        name, _, value = line.partition(":")
        name = name.strip()
        value = value.strip()
        if value == "":
            key_of_list = name
            settings[name] = []
        else:
            key_of_list = None
            settings[name] = value
    return settings


def setting_int(settings: dict, name: str, paper: str) -> int:
    if name not in settings:
        raise fault(paper, name)
    return to_int(settings[name])


def setting_text(settings: dict, name: str, paper: str) -> str:
    if name not in settings:
        raise fault(paper, name)
    return str(settings[name])


def read_sheets(path) -> dict:
    """Every sheet of an OOXML workbook, as a name to grid mapping.

    The sheet order and the sheet names carry no meaning for this network, so
    the reader keeps both and the caller picks by the key cell.
    """
    if not os.path.isfile(path):
        raise PaperFault("%s: the directory carries no such paper"
                         % os.path.basename(str(path)))
    with zipfile.ZipFile(path) as book:
        catalogue = ElementTree.fromstring(book.read("xl/workbook.xml"))
        links = ElementTree.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        target_of = {}
        for relation in links:
            target_of[relation.get("Id")] = relation.get("Target")
        strings = []
        if "xl/sharedStrings.xml" in book.namelist():
            table = ElementTree.fromstring(book.read("xl/sharedStrings.xml"))
            for item in table.findall(SPREADSHEET_NS + "si"):
                strings.append("".join(
                    node.text or "" for node in item.iter(SPREADSHEET_NS + "t")))
        sheets = {}
        holder = catalogue.find(SPREADSHEET_NS + "sheets")
        for leaf in (list(holder) if holder is not None else []):
            target = target_of.get(leaf.get(RELATION_ID), "")
            member = target if target.startswith("xl/") else "xl/" + target.lstrip("/")
            sheets[leaf.get("name")] = _sheet_grid(book.read(member), strings)
    return sheets


def _sheet_grid(payload: bytes, strings: list) -> list:
    grid = []
    page = ElementTree.fromstring(payload)
    for line in page.iter(SPREADSHEET_NS + "row"):
        cells = {}
        widest = -1
        for cell in line.iter(SPREADSHEET_NS + "c"):
            column = _column_index(cell.get("r") or "")
            slot = cell.find(SPREADSHEET_NS + "v")
            text = "" if slot is None else (slot.text or "")
            if cell.get("t") == "s" and text != "":
                text = strings[int(text)]
            cells[column] = text
            widest = max(widest, column)
        grid.append([cells.get(index, "") for index in range(widest + 1)])
    return grid


def _column_index(reference: str) -> int:
    index = 0
    for letter in reference:
        if not letter.isalpha():
            break
        index = index * 26 + (ord(letter.upper()) - 64)
    return index - 1


def read_memo_lines(path) -> list:
    """The signed memo, as the lines its text operators carry."""
    if not os.path.isfile(path):
        raise PaperFault("%s: the directory carries no such paper"
                         % os.path.basename(str(path)))
    with open(path, "rb") as handle:
        body = handle.read().decode("latin-1")
    return [_unescape_pdf(piece) for piece in re.findall(r"\((.*?)\)\s*Tj", body)]


def _unescape_pdf(text: str) -> str:
    for coded, plain in (("\\(", "("), ("\\)", ")"), ("\\\\", "\\")):
        text = text.replace(coded, plain)
    return text


def memo_value(lines: list, name: str) -> str:
    marker = name + " = "
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(marker):
            return stripped[len(marker):].strip()
    raise fault("network_calibration_memo.pdf", name)


# ---------------------------------------------------------------------------
# the working papers
# ---------------------------------------------------------------------------

class Papers:
    """Everything the thirteen stages read, taken from one directory."""

    def __init__(self, root):
        self.root = root
        self.header = read_json(self._at("network_config.json"))
        for field in ("interval_label", "interval_start_epoch_s", "interval_epochs",
                      "grid_step_seconds", "hub_node", "frozen_register_revision",
                      "workbook_sheet_key", "archive_epochs"):
            if field not in self.header:
                raise fault("network_config.json", field)
        self.label = str(self.header["interval_label"])
        self.start_s = to_int(self.header["interval_start_epoch_s"])
        self.epochs = to_int(self.header["interval_epochs"])
        self.step_s = to_int(self.header["grid_step_seconds"])
        self.units = Units(self.step_s)
        self.hub = str(self.header["hub_node"])
        self.revision = str(self.header["frozen_register_revision"])
        self.archive_epochs = to_int(self.header["archive_epochs"])

        self.grid_policy = read_settings(self._at("epoch_grid_policy.yaml"))
        self.rounding_policy = read_settings(self._at("rounding_policy.yaml"))
        if setting_text(self.rounding_policy, "mode", "rounding_policy.yaml") != "round_half_even":
            raise fault("rounding_policy.yaml", "mode")
        self.ratio_places = setting_int(
            self.rounding_policy, "ratio_places", "rounding_policy.yaml")
        self.weight_policy = read_settings(self._at("weighting_policy.yaml"))
        self.steer_policy = read_settings(self._at("steering_policy.yaml"))
        self.order_policy = read_settings(self._at("ordering_dependencies.yaml"))

        self.instant_offset_s = setting_int(
            self.grid_policy, "grid_instant_offset_s", "epoch_grid_policy.yaml")
        self.tolerance_s = setting_int(
            self.grid_policy, "attribution_tolerance_s", "epoch_grid_policy.yaml")
        self.window_epochs = setting_int(
            self.weight_policy, "history_window_epochs", "weighting_policy.yaml")
        self.archive_flag = setting_text(
            self.weight_policy, "valid_archive_flag", "weighting_policy.yaml")
        self.weight_scale = setting_int(
            self.weight_policy, "weight_scale", "weighting_policy.yaml")
        self.weight_places = setting_int(
            self.weight_policy, "weight_places", "weighting_policy.yaml")
        self.damping = Fraction(
            setting_int(self.weight_policy, "damping_numerator", "weighting_policy.yaml"),
            setting_int(self.weight_policy, "damping_denominator", "weighting_policy.yaml"))
        self.decision_epoch = setting_int(
            self.steer_policy, "decision_epoch", "steering_policy.yaml")
        self.horizon_epochs = setting_int(
            self.steer_policy, "horizon_epochs", "steering_policy.yaml")
        self.grid_atto = setting_int(
            self.steer_policy, "grid_atto", "steering_policy.yaml")
        self.digest_order = list(self.order_policy.get("digest_order") or [])
        if not self.digest_order:
            raise fault("ordering_dependencies.yaml", "digest_order")

        self._read_registers()
        self._read_vocabularies()
        self._read_acquisition()
        self._read_calibration()
        self._read_measurement()
        self._read_control_papers()
        self._read_contract()

    def _at(self, name: str):
        return os.path.join(self.root, name)

    # -- registers ---------------------------------------------------------
    def _read_registers(self):
        self.nodes = {}
        for row in read_rows(self._at("node_register_frozen.csv"), ","):
            if row["register_revision"] != self.revision:
                continue
            self.nodes[row["node_id"]] = {
                "node_id": row["node_id"],
                "register_revision": row["register_revision"],
                "site_class": row["site_class"],
                "reference_oscillator": row["reference_oscillator"],
                "declared_uncertainty_ps": to_int(row["declared_uncertainty_ps"]),
            }
        if self.hub not in self.nodes:
            raise fault("node_register_frozen.csv", "the hub node at " + self.revision)
        self.node_ids = sorted(self.nodes)

        self.links = {}
        for row in read_rows(self._at("link_register.csv"), ","):
            self.links[row["link_id"]] = {
                "link_id": row["link_id"],
                "node_a": row["node_a"],
                "node_b": row["node_b"],
                "technique": row["technique"],
                "uncertainty_ps": to_int(row["published_uncertainty_ps"]),
            }

        self.oscillators = []
        for row in read_rows(self._at("oscillator_catalogue.csv"), ","):
            self.oscillators.append({
                "osc_id": row["osc_id"],
                "node_id": row["node_id"],
                "osc_class": row["osc_class"],
                "status": row["status"],
            })
        self.oscillator_ids = [entry["osc_id"] for entry in self.oscillators]
        self.oscillator_of = {entry["osc_id"]: entry for entry in self.oscillators}

    # -- closed vocabularies ----------------------------------------------
    def _read_vocabularies(self):
        self.sense_of = {}
        self.rank_of = {}
        for line in read_text(self._at("link_technique_reference.txt")).splitlines():
            cells = line.split()
            if len(cells) < 3 or not cells[0].startswith("LK_"):
                continue
            self.sense_of[cells[0]] = cells[1]
            self.rank_of[cells[0]] = to_int(cells[2])
        if not self.sense_of:
            raise fault("link_technique_reference.txt", "the technique table")

    # -- acquisition -------------------------------------------------------
    def _read_acquisition(self):
        self.attempts = []
        for row in read_rows(self._at("comparison_session_log.csv"), ","):
            self.attempts.append({
                "session_id": row["session_id"],
                "receiver_id": row["receiver_id"],
                "link_id": row["link_id"],
                "attempt_no": to_int(row["attempt_no"]),
                "acq_time_s": to_int(row["acq_time_s"]),
                "raw_offset_ps": to_int(row["raw_offset_ps"]),
                "lock_state": row["lock_state"],
            })
        self.withdrawn = {row["session_id"] for row
                          in read_rows(self._at("session_withdrawal_journal.tsv"), "\t")}

    # -- calibration -------------------------------------------------------
    def _read_calibration(self):
        self.reports = {}
        papers = (("delay_calibration_ledger.csv", ","),
                  ("delay_calibration_supplement.psv", "|"))
        for name, separator in papers:
            path = self._at(name)
            if not os.path.isfile(path):
                raise SystemExit("%s: the directory carries no such paper" % name)
            for row in read_rows(path, separator):
                self.reports.setdefault(row["link_id"], []).append({
                    "report_id": row["report_id"],
                    "link_id": row["link_id"],
                    "effective_epoch_s": to_int(row["effective_epoch_s"]),
                    "revision": to_int(row["revision"]),
                    "delay_a_ns": to_int(row["delay_a_ns"]),
                    "delay_b_ns": to_int(row["delay_b_ns"]),
                    "status": row["status"],
                })

    # -- monitor and archive ----------------------------------------------
    def _read_measurement(self):
        self.monitor = {}
        for row in read_rows(self._at("local_comparison_log.psv"), "|"):
            self.monitor[(row["osc_id"], to_int(row["epoch_index"]))] = {
                "local_offset_ps": to_int(row["local_offset_ps"]),
                "monitor_flag": row["monitor_flag"],
            }
        self.archive = {}
        for row in read_rows(self._at("prior_interval_deviations.psv"), "|"):
            self.archive.setdefault(row["osc_id"], {})[to_int(row["archive_epoch"])] = {
                "deviation_ps": to_int(row["deviation_ps"]),
                "quality_flag": row["quality_flag"],
            }
        self.realisation = {}
        for row in read_rows(self._at("primary_standard_realisation.csv"), ","):
            if row["realisation_ps"].strip() == "":
                continue
            self.realisation[to_int(row["epoch_index"])] = to_int(row["realisation_ps"])

    # -- the two control papers -------------------------------------------
    def _read_control_papers(self):
        sheets = read_sheets(self._at("timing_network_workbook.xlsx"))
        wanted = str(self.header["workbook_sheet_key"])
        live = None
        for name in sorted(sheets):
            grid = sheets[name]
            if grid and len(grid[0]) > 1 and grid[0][1] == wanted:
                live = grid
                self.live_sheet_name = name
                break
        if live is None:
            raise fault("timing_network_workbook.xlsx",
                        "a sheet whose key cell holds " + wanted)

        self.class_ceiling = {}
        self.uncertainty_terms = {}
        self.node_cap_share = None
        section = ""
        for line in live:
            cells = list(line) + ["", "", ""]
            head = cells[0].strip()
            if head == "SECTION":
                section = cells[1].strip()
                continue
            if section == "CLASS_CEILING" and head.startswith("OSC_"):
                self.class_ceiling[head] = to_int(cells[1])
            elif section == "NODE_CAP" and head == "NODE_WEIGHT_CAP":
                self.node_cap_share = Fraction(to_int(cells[1]), to_int(cells[2]))
            elif section == "UNCERTAINTY_COMPONENTS" and head.startswith("osc_"):
                self.uncertainty_terms.setdefault(head, []).append(to_int(cells[2]))
        if self.node_cap_share is None:
            raise fault("timing_network_workbook.xlsx", "NODE_WEIGHT_CAP")

        memo = read_memo_lines(self._at("network_calibration_memo.pdf"))
        self.osc_cap_share = Fraction(
            to_int(memo_value(memo, "OSC_WEIGHT_CAP_NUMERATOR")),
            to_int(memo_value(memo, "OSC_WEIGHT_CAP_DENOMINATOR")))
        self.sweep_budget = to_int(memo_value(memo, "CAP_SWEEP_BUDGET"))
        self.history_minimum = to_int(memo_value(memo, "HISTORY_MINIMUM_EPOCHS"))

    # -- the output contract ----------------------------------------------
    def _read_contract(self):
        self.documents = []
        for line in read_text(self._at("output_artifact_contract.md")).splitlines():
            match = re.match(r"\|\s*([A-Za-z0-9_]+\.[A-Za-z0-9]+)\s*\|", line)
            if match:
                self.documents.append(match.group(1))
        if not self.documents:
            raise fault("output_artifact_contract.md", "the artifact table")
        self.rule_count = None
        for line in read_text(self._at("output_schema_reference.md")).splitlines():
            match = re.search(r"rule_count is (\d+)", line)
            if match:
                self.rule_count = int(match.group(1))
        if self.rule_count is None:
            raise fault("output_schema_reference.md", "rule_count")
        self.report_nodes = [name[len("node_report_"):-len(".json")]
                             for name in self.documents
                             if name.startswith("node_report_")]

    # -- the publication grid ---------------------------------------------
    def instant(self, epoch: int) -> int:
        return self.start_s + (epoch - 1) * self.step_s + self.instant_offset_s

    def epoch_range(self):
        return range(1, self.epochs + 1)


# ---------------------------------------------------------------------------
# the interval: thirteen stages, each freezing what the next one consumes
# ---------------------------------------------------------------------------

class Interval:
    def __init__(self, papers: Papers):
        self.papers = papers
        self.stage_t01_canonical_readings()
        self.stage_t02_delay_calibration()
        self.stage_t03_measurement_sense()
        self.stage_t04_link_graph()
        self.stage_t05_node_offsets()
        self.stage_t06_oscillator_series()
        self.stage_t07_frequency_prediction()
        self.stage_t08_dispersion_and_weight()
        self.stage_t09_weight_capping()
        self.stage_t10_ensemble_scale()
        self.stage_t11_steering()
        self.stage_t12_dissemination()
        self.stage_t13_reconciliation()

    # -- T01 ---------------------------------------------------------------
    def stage_t01_canonical_readings(self):
        papers = self.papers
        tolerance = papers.tolerance_s
        instants = {k: papers.instant(k) for k in papers.epoch_range()}

        attributed = []
        set_aside = []
        for row in papers.attempts:
            epoch = None
            for k, moment in instants.items():
                if moment - tolerance <= row["acq_time_s"] < moment + tolerance:
                    epoch = k
                    break
            entry = dict(row)
            entry["epoch_index"] = epoch
            link = papers.links.get(row["link_id"])
            if epoch is None:
                reason = "DR_OUTSIDE_INTERVAL"
            elif row["session_id"] in papers.withdrawn:
                reason = "DR_SESSION_WITHDRAWN"
            elif link is None:
                reason = "DR_LINK_UNREGISTERED"
            elif link["node_a"] == link["node_b"]:
                reason = "DR_SELF_LOOP"
            else:
                reason = None
            if reason is None:
                attributed.append(entry)
            else:
                entry["drop_reason"] = reason
                set_aside.append(entry)

        clusters = {}
        for entry in attributed:
            clusters.setdefault((entry["link_id"], entry["epoch_index"]), []).append(entry)

        self.readings = {}
        self.cluster_size = {}
        for key in sorted(clusters):
            members = clusters[key]
            eligible = [row for row in members if row["lock_state"] == "LOCK_HELD"]
            if not eligible:
                for row in members:
                    row["drop_reason"] = "DR_NO_LOCKED_ATTEMPT"
                    set_aside.append(row)
                continue
            moment = instants[key[1]]
            best = min(eligible, key=lambda row: (
                -row["attempt_no"], abs(row["acq_time_s"] - moment), row["acq_time_s"]))
            self.readings[key] = dict(best)
            self.cluster_size[key] = len(members)
        self.set_aside = set_aside

    # -- T02 ---------------------------------------------------------------
    def stage_t02_delay_calibration(self):
        papers = self.papers
        self.calibration = {}
        for key in sorted(self.readings):
            reading = self.readings[key]
            governing = [report for report in papers.reports.get(key[0], [])
                         if report["effective_epoch_s"] <= reading["acq_time_s"]]
            if governing:
                applicable = min(governing, key=lambda report: (
                    -report["effective_epoch_s"], report["revision"]))
                correction = (applicable["delay_a_ns"] - applicable["delay_b_ns"]) * 1000
                record = {
                    "report_id": applicable["report_id"],
                    "revision": applicable["revision"],
                    "status": applicable["status"],
                    "effective_epoch_s": applicable["effective_epoch_s"],
                    "correction_ps": correction,
                }
            else:
                record = {
                    "report_id": "REPORT_NONE",
                    "revision": 0,
                    "status": "CAL_ABSENT",
                    "effective_epoch_s": 0,
                    "correction_ps": 0,
                }
            record["corrected_ps"] = reading["raw_offset_ps"] - record["correction_ps"]
            self.calibration[key] = record

    # -- T03 ---------------------------------------------------------------
    def stage_t03_measurement_sense(self):
        papers = self.papers
        self.difference = {}
        for key in sorted(self.readings):
            technique = papers.links[key[0]]["technique"]
            sense = papers.sense_of.get(technique)
            if sense is None:
                raise fault("link_technique_reference.txt", technique)
            corrected = self.calibration[key]["corrected_ps"]
            self.difference[key] = {
                "sense": sense,
                "difference_ps": corrected if sense == "SENSE_A_MINUS_B" else -corrected,
            }

    # -- T04 ---------------------------------------------------------------
    def stage_t04_link_graph(self):
        papers = self.papers
        usable = [papers.links[link_id] for link_id in sorted(papers.links)
                  if papers.links[link_id]["node_a"] in papers.nodes
                  and papers.links[link_id]["node_b"] in papers.nodes
                  and papers.links[link_id]["node_a"] != papers.links[link_id]["node_b"]]
        neighbours = {node: [] for node in papers.node_ids}
        for link in usable:
            neighbours[link["node_a"]].append(link)
            neighbours[link["node_b"]].append(link)

        assigned = set()
        groups = []
        for node in papers.node_ids:
            if node in assigned:
                continue
            members = set()
            frontier = [node]
            while frontier:
                here = frontier.pop()
                if here in members:
                    continue
                members.add(here)
                for link in neighbours[here]:
                    other = link["node_b"] if link["node_a"] == here else link["node_a"]
                    if other not in members:
                        frontier.append(other)
            assigned |= members
            groups.append(sorted(members))
        groups.sort(key=lambda members: members[0])

        self.components = []
        self.component_of = {}
        self.tree_path = {}
        for position, members in enumerate(groups, start=1):
            inside = set(members)
            anchored = papers.hub in inside
            root = papers.hub if anchored else members[0]
            edges = self._grow_tree(
                [link for link in usable
                 if link["node_a"] in inside and link["node_b"] in inside], root)
            admitted = {edge["link_id"] for edge in edges}
            component = {
                "component_id": "cmp_%02d" % position,
                "role": "ROLE_ANCHORED" if anchored else "ROLE_UNANCHORED",
                "root_node": root,
                "member_nodes": members,
                "tree_edges": edges,
                "excluded_link_ids": sorted(
                    link["link_id"] for link in usable
                    if link["node_a"] in inside and link["node_b"] in inside
                    and link["link_id"] not in admitted),
            }
            self.components.append(component)
            for node in members:
                self.component_of[node] = component
            self._chart_paths(component)

    def _grow_tree(self, inside: list, root: str) -> list:
        papers = self.papers
        reached = {root}
        cost = {root: 0}
        edges = []
        while True:
            candidates = [link for link in inside
                          if (link["node_a"] in reached) != (link["node_b"] in reached)]
            if not candidates:
                break
            chosen = min(candidates, key=lambda link: (
                self._admission_cost(link, reached, cost),
                papers.rank_of.get(link["technique"], 0),
                link["link_id"]))
            if chosen["node_a"] in reached:
                parent, child = chosen["node_a"], chosen["node_b"]
            else:
                parent, child = chosen["node_b"], chosen["node_a"]
            cost[child] = self._admission_cost(chosen, reached, cost)
            reached.add(child)
            edges.append({
                "link_id": chosen["link_id"],
                "parent_node": parent,
                "child_node": child,
                "technique": chosen["technique"],
                "published_uncertainty_ps": chosen["uncertainty_ps"],
            })
        return edges

    @staticmethod
    def _admission_cost(link: dict, reached: set, cost: dict) -> int:
        end = link["node_a"] if link["node_a"] in reached else link["node_b"]
        return cost[end] + link["uncertainty_ps"]

    def _chart_paths(self, component: dict):
        parent_of = {}
        for edge in component["tree_edges"]:
            parent_of[edge["child_node"]] = edge
        for node in component["member_nodes"]:
            chain = []
            here = node
            while here in parent_of:
                edge = parent_of[here]
                chain.append(edge)
                here = edge["parent_node"]
            chain.reverse()
            self.tree_path[node] = chain

    # -- T05 ---------------------------------------------------------------
    def stage_t05_node_offsets(self):
        papers = self.papers
        self.tree_link_ids = set()
        for component in self.components:
            for edge in component["tree_edges"]:
                self.tree_link_ids.add(edge["link_id"])

        self.node_offset = {}
        self.dead_time = []
        for epoch in papers.epoch_range():
            for link_id in sorted(self.tree_link_ids):
                if (link_id, epoch) not in self.readings:
                    self.dead_time.append({
                        "epoch_index": epoch, "scope": "SCOPE_LINK",
                        "subject": link_id, "cause": "CAUSE_NO_READING"})
            for node in papers.node_ids:
                chain = self.tree_path[node]
                missing = None
                total = 0
                for edge in chain:
                    key = (edge["link_id"], epoch)
                    if key not in self.difference:
                        missing = edge["link_id"]
                        break
                    signed = self.difference[key]["difference_ps"]
                    register = papers.links[edge["link_id"]]
                    if register["node_a"] == edge["parent_node"]:
                        total -= signed
                    else:
                        total += signed
                if missing is None:
                    self.node_offset[(node, epoch)] = Fraction(total)
                else:
                    self.dead_time.append({
                        "epoch_index": epoch, "scope": "SCOPE_NODE",
                        "subject": node, "cause": missing})

    # -- T06 ---------------------------------------------------------------
    def stage_t06_oscillator_series(self):
        papers = self.papers
        reference_of = {node: papers.nodes[node]["reference_oscillator"]
                        for node in papers.node_ids}
        self.series = {}
        for entry in papers.oscillators:
            node = entry["node_id"]
            component = self.component_of.get(node)
            anchored = component is not None and component["role"] == "ROLE_ANCHORED"
            for epoch in papers.epoch_range():
                offset = self.node_offset.get((node, epoch))
                if offset is None:
                    self.series[(entry["osc_id"], epoch)] = (None, "SER_ABSENT")
                    continue
                if reference_of.get(node) == entry["osc_id"]:
                    value = offset
                else:
                    row = papers.monitor.get((entry["osc_id"], epoch))
                    if row is None or row["monitor_flag"] != "MON_VALID":
                        self.series[(entry["osc_id"], epoch)] = (None, "SER_ABSENT")
                        self.dead_time.append({
                            "epoch_index": epoch, "scope": "SCOPE_OSCILLATOR",
                            "subject": entry["osc_id"], "cause": "CAUSE_NO_MONITOR"})
                        continue
                    value = offset + row["local_offset_ps"]
                self.series[(entry["osc_id"], epoch)] = (
                    value, "SER_MEASURED" if anchored else "SER_UNANCHORED")

    # -- T07 ---------------------------------------------------------------
    def stage_t07_frequency_prediction(self):
        papers = self.papers
        self.window_first = papers.archive_epochs - papers.window_epochs + 1
        self.window_last = papers.archive_epochs
        self.prediction = {}
        for entry in papers.oscillators:
            osc_id = entry["osc_id"]
            rows = papers.archive.get(osc_id, {})
            points = []
            for epoch in range(self.window_first, self.window_last + 1):
                row = rows.get(epoch)
                if row is not None and row["quality_flag"] == papers.archive_flag:
                    points.append((epoch, row["deviation_ps"]))
            record = {
                "osc_id": osc_id,
                "node_id": entry["node_id"],
                "osc_class": entry["osc_class"],
                "valid_count": len(points),
                "anchor_epoch": 0,
                "anchor_deviation_ps": 0,
                "frequency": Fraction(0),
                "included": False,
                "exclusion_reason": "",
                "points": points,
            }
            component = self.component_of.get(entry["node_id"])
            if entry["status"] == "OS_DECOMMISSIONED":
                record["exclusion_reason"] = "EX_DECOMMISSIONED"
            elif not rows:
                record["exclusion_reason"] = "EX_NO_ARCHIVE"
            elif len(points) < papers.history_minimum:
                record["exclusion_reason"] = "EX_SHORT_HISTORY"
            elif component is None or component["role"] != "ROLE_ANCHORED":
                record["exclusion_reason"] = "EX_UNANCHORED_NODE"
            else:
                first_epoch, first_value = points[0]
                last_epoch, last_value = points[-1]
                record["anchor_epoch"] = last_epoch
                record["anchor_deviation_ps"] = last_value
                if last_epoch != first_epoch:
                    record["frequency"] = papers.units.slope(
                        Fraction(last_value - first_value), last_epoch - first_epoch)
                record["included"] = True
            self.prediction[osc_id] = record

    def predicted_at_archive(self, osc_id: str, epoch: int) -> Fraction:
        record = self.prediction[osc_id]
        return Fraction(record["anchor_deviation_ps"]) + self.papers.units.phase(
            record["frequency"], epoch - record["anchor_epoch"])

    def predicted_at_grid(self, osc_id: str, epoch: int) -> Fraction:
        return self.predicted_at_archive(
            osc_id, self.papers.archive_epochs + epoch)

    # -- T08 ---------------------------------------------------------------
    def stage_t08_dispersion_and_weight(self):
        papers = self.papers
        self.weighted = {}
        for osc_id in papers.oscillator_ids:
            record = self.prediction[osc_id]
            if not record["included"]:
                continue
            residuals = [Fraction(value) - self.predicted_at_archive(osc_id, epoch)
                         for epoch, value in record["points"]]
            mean = sum((abs(item) for item in residuals), Fraction(0)) / len(residuals)
            dispersion = nearest_even(mean)
            if dispersion == 0:
                osc_class = record["osc_class"]
                if osc_class not in papers.class_ceiling:
                    raise fault("timing_network_workbook.xlsx",
                                "a ceiling weight for " + osc_class)
                raw = Fraction(papers.class_ceiling[osc_class])
                source = "WS_CLASS_CEILING"
            else:
                raw = Fraction(papers.weight_scale, dispersion)
                source = "WS_DISPERSION"
            self.weighted[osc_id] = {
                "osc_id": osc_id,
                "node_id": record["node_id"],
                "osc_class": record["osc_class"],
                "valid_count": record["valid_count"],
                "dispersion_ps": dispersion,
                "weight_source": source,
                "raw_weight": raw,
            }

    # -- T09 ---------------------------------------------------------------
    def stage_t09_weight_capping(self):
        papers = self.papers
        places = papers.weight_places
        self.carried = {}
        self.trace = []

        vector = {osc_id: place(entry["raw_weight"], places)
                  for osc_id, entry in self.weighted.items()}
        self.total_weight = sum(vector.values(), Fraction(0))
        self.osc_cap = papers.osc_cap_share * self.total_weight
        self.node_cap = papers.node_cap_share * self.total_weight

        vector, self.osc_outcome, self.sweeps_used, _ = self._oscillator_sweeps(
            vector, papers.sweep_budget, "PH_OSC_CAP")
        self.after_osc = dict(vector)
        vector, self.node_outcome = self._node_pass(vector)
        self.after_node = dict(vector)
        vector, self.final_outcome, _, self.terminal_residual = self._oscillator_sweeps(
            vector, 1, "PH_FINAL_SWEEP")
        self.final_weight = vector

        self.node_totals = {}
        for osc_id, value in self.final_weight.items():
            node = self.weighted[osc_id]["node_id"]
            self.node_totals[node] = self.node_totals.get(node, Fraction(0)) + value

    def _oscillator_sweeps(self, vector: dict, budget: int, phase: str):
        """The damped cap and redistribute map, run to the budget it is given."""
        current = dict(vector)
        outcome = "SW_SETTLED"
        passes = 0
        residual = Fraction(0)
        while True:
            offenders = sorted(key for key in current if current[key] > self.osc_cap)
            if not offenders:
                outcome = "SW_SETTLED"
                break
            holders = sorted(key for key in current if current[key] <= self.osc_cap)
            if not holders:
                outcome = "SW_CAP_UNSATISFIABLE"
                break
            if passes >= budget:
                outcome = "SW_BUDGET_EXHAUSTED"
                break
            passes += 1

            excess = sum((current[key] - self.osc_cap for key in offenders), Fraction(0))
            target = dict(current)
            for key in offenders:
                target[key] = self.osc_cap
            base = sum((current[key] for key in holders), Fraction(0))
            for key in holders:
                if base == 0:
                    target[key] = current[key] + Fraction(excess, len(holders))
                else:
                    target[key] = current[key] + excess * current[key] / base
            stepped = {key: current[key] + self.papers.damping * (target[key] - current[key])
                       for key in current}
            placed = self._close_on_grid(stepped, holders)
            residual = sum((abs(placed[key] - current[key]) for key in sorted(current)),
                           Fraction(0))
            self.trace.append({
                "phase": phase,
                "sweep": passes,
                "offenders": offenders,
                "excess_ratio": ratio(excess, self.papers.ratio_places),
                "holders": len(holders),
                "residual_ratio": ratio(residual, self.papers.ratio_places),
            })
            current = placed
        return current, outcome, passes, residual

    def _node_pass(self, vector: dict):
        """One undamped pass of the node cap, taken in full."""
        by_node = {}
        for osc_id in sorted(vector):
            by_node.setdefault(self.weighted[osc_id]["node_id"], []).append(osc_id)
        offending = sorted(node for node in by_node
                           if sum((vector[key] for key in by_node[node]), Fraction(0))
                           > self.node_cap)
        if not offending:
            return dict(vector), "SW_SETTLED"
        working = dict(vector)
        excess = Fraction(0)
        capped = set()
        for node in offending:
            members = by_node[node]
            capped |= set(members)
            held = sum((working[key] for key in members), Fraction(0))
            excess += held - self.node_cap
            for key in members:
                working[key] = working[key] * self.node_cap / held
        receivers = sorted(key for key in working if key not in capped)
        if not receivers:
            return dict(vector), "SW_CAP_UNSATISFIABLE"
        base = sum((working[key] for key in receivers), Fraction(0))
        for key in receivers:
            if base == 0:
                working[key] = working[key] + Fraction(excess, len(receivers))
            else:
                working[key] = working[key] + excess * working[key] / base
        placed = self._close_on_grid(working, receivers)
        moved = sum((abs(placed[key] - vector[key]) for key in sorted(vector)),
                    Fraction(0))
        self.trace.append({
            "phase": "PH_NODE_CAP",
            "sweep": 1,
            "offenders": offending,
            "excess_ratio": ratio(excess, self.papers.ratio_places),
            "holders": len(receivers),
            "residual_ratio": ratio(moved, self.papers.ratio_places),
        })
        return placed, "SW_SETTLED"

    def _close_on_grid(self, stepped: dict, receivers: list) -> dict:
        """Place a pass on the published grid without costing it any mass.

        Placing each weight on its own moves the total, so the whole of the
        difference goes to one receiving holder: the one that has carried it
        the fewest times so far in this interval, a tie going to the greatest
        weight after placement and then to the smallest identifier. The count
        runs across every pass of all three phases.
        """
        places = self.papers.weight_places
        placed = {key: place(value, places) for key, value in stepped.items()}
        if not receivers:
            return placed
        residue = (sum(stepped.values(), Fraction(0))
                   - sum(placed.values(), Fraction(0)))
        if residue == 0:
            return placed
        carrier = min(receivers, key=lambda key: (
            self.carried.get(key, 0), -placed[key], key))
        placed[carrier] = placed[carrier] + residue
        self.carried[carrier] = self.carried.get(carrier, 0) + 1
        return placed

    # -- T10 ---------------------------------------------------------------
    def stage_t10_ensemble_scale(self):
        papers = self.papers
        self.epoch_state = {}
        self.contributors = {}
        self.denominator = {}
        self.free_scale = {}
        for epoch in papers.epoch_range():
            numerator = Fraction(0)
            weight_sum = Fraction(0)
            count = 0
            for osc_id in sorted(self.final_weight):
                value, _flag = self.series.get((osc_id, epoch), (None, "SER_ABSENT"))
                if value is None:
                    continue
                weight = self.final_weight[osc_id]
                numerator += weight * (value - self.predicted_at_grid(osc_id, epoch))
                weight_sum += weight
                count += 1
            self.contributors[epoch] = count
            self.denominator[epoch] = weight_sum
            if count == 0:
                self.epoch_state[epoch] = "EP_ENSEMBLE_VOID"
                self.free_scale[epoch] = None
            else:
                self.epoch_state[epoch] = "EP_POPULATED"
                self.free_scale[epoch] = numerator / weight_sum

    # -- T11 ---------------------------------------------------------------
    def stage_t11_steering(self):
        papers = self.papers
        decision = papers.decision_epoch
        free = self.free_scale.get(decision)
        realisation = papers.realisation.get(decision)
        if free is None or realisation is None:
            self.departure = Fraction(0)
            self.raw_step = Fraction(0)
            self.step_atto = 0
            self.steer_outcome = "ST_NO_REALISATION"
        else:
            self.departure = free - realisation
            self.raw_step = papers.units.slope(-self.departure, papers.horizon_epochs)
            self.step_atto = toward_zero(self.raw_step / papers.grid_atto) * papers.grid_atto
            self.steer_outcome = ("ST_TRUNCATED_TO_ZERO" if self.step_atto == 0
                                  else "ST_APPLIED")
        self.correction = {}
        self.steered_scale = {}
        for epoch in papers.epoch_range():
            if epoch > decision:
                shift = papers.units.phase(Fraction(self.step_atto), epoch - decision)
            else:
                shift = Fraction(0)
            self.correction[epoch] = shift
            free_here = self.free_scale[epoch]
            self.steered_scale[epoch] = None if free_here is None else free_here + shift

    # -- T12 ---------------------------------------------------------------
    def stage_t12_dissemination(self):
        papers = self.papers
        self.published_offset = {}
        for node in papers.node_ids:
            for epoch in papers.epoch_range():
                base = self.node_offset.get((node, epoch))
                steered = self.steered_scale[epoch]
                if base is None or steered is None:
                    self.published_offset[(node, epoch)] = None
                else:
                    self.published_offset[(node, epoch)] = base - steered

        self.budget = {}
        for node in papers.node_ids:
            reference = papers.nodes[node]["reference_oscillator"]
            terms = list(papers.uncertainty_terms.get(reference, []))
            if not terms:
                raise fault("timing_network_workbook.xlsx",
                            "uncertainty components for " + reference)
            terms.append(papers.nodes[node]["declared_uncertainty_ps"])
            for edge in self.tree_path[node]:
                terms.append(edge["published_uncertainty_ps"])
            component = self.component_of[node]
            available = [self.published_offset[(node, epoch)]
                         for epoch in papers.epoch_range()
                         if self.published_offset[(node, epoch)] is not None]
            if component["role"] != "ROLE_ANCHORED":
                status = "DS_WITHHELD_UNANCHORED"
            elif not available:
                status = "DS_WITHHELD_NO_DATA"
            else:
                status = "DS_PUBLISHED"
            mean = (sum(available, Fraction(0)) / len(available)) if available else Fraction(0)
            self.budget[node] = {
                "component_id": component["component_id"],
                "role": component["role"],
                "path_length": len(self.tree_path[node]),
                "term_count": len(terms),
                "u_combined_ps2": sum(term * term for term in terms),
                "u_linear_ps": sum(terms),
                "status": status,
                "epochs_available": len(available),
                "offset_mean_ps": mean,
            }

    # -- T13 ---------------------------------------------------------------
    def stage_t13_reconciliation(self):
        papers = self.papers
        self.closures = []
        self.unreconciled = []
        excluded = []
        for component in self.components:
            excluded.extend(component["excluded_link_ids"])
        for link_id in sorted(excluded):
            register = papers.links[link_id]
            found = False
            for epoch in papers.epoch_range():
                key = (link_id, epoch)
                if key not in self.difference:
                    continue
                offset_a = self.node_offset.get((register["node_a"], epoch))
                offset_b = self.node_offset.get((register["node_b"], epoch))
                if offset_a is None or offset_b is None:
                    continue
                found = True
                self.closures.append({
                    "link_id": link_id,
                    "epoch_index": epoch,
                    "closure_ps": self.difference[key]["difference_ps"] - (offset_a - offset_b),
                })
            if not found:
                self.unreconciled.append(link_id)
        self.closures.sort(key=lambda item: (item["link_id"], item["epoch_index"]))


# ---------------------------------------------------------------------------
# the publication
# ---------------------------------------------------------------------------

class Publication:
    """Every document the output artifact contract names, as bytes."""

    def __init__(self, interval: Interval):
        self.interval = interval
        self.papers = interval.papers
        self.places = interval.papers.ratio_places
        self.blobs = {}
        self._readings()
        self._graph_family()
        self._ensemble_family()
        self._publish_family()
        self._reports()
        self._manifest()

    def _ratio(self, value) -> str:
        return ratio(value, self.places)

    # -- byte shapes -------------------------------------------------------
    @staticmethod
    def _delimited(header: list, rows: list, separator: str) -> bytes:
        lines = [separator.join(header)]
        for row in rows:
            lines.append(separator.join(str(row[name]) for name in header))
        return ("\n".join(lines) + "\n").encode("utf-8")

    @staticmethod
    def _document(payload) -> bytes:
        text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True)
        return (text + "\n").encode("utf-8")

    @staticmethod
    def _records(payload: list) -> bytes:
        if not payload:
            return b""
        lines = [json.dumps(item, sort_keys=True, ensure_ascii=True,
                            separators=(",", ":")) for item in payload]
        return ("\n".join(lines) + "\n").encode("utf-8")

    @staticmethod
    def _lines(payload: list) -> bytes:
        return ("\n".join(payload) + "\n").encode("utf-8")

    # -- core and graph ----------------------------------------------------
    def _readings(self):
        interval = self.interval
        papers = self.papers
        ledger = []
        differences = []
        selection = []
        for key in sorted(interval.readings):
            reading = interval.readings[key]
            calibration = interval.calibration[key]
            sense = interval.difference[key]
            register = papers.links[key[0]]
            ledger.append({
                "link_id": key[0], "epoch_index": key[1],
                "session_id": reading["session_id"],
                "receiver_id": reading["receiver_id"],
                "attempt_no": reading["attempt_no"],
                "acq_time_s": reading["acq_time_s"],
                "raw_offset_ps": whole(reading["raw_offset_ps"]),
                "report_id": calibration["report_id"],
                "correction_ps": whole(calibration["correction_ps"]),
                "corrected_ps": whole(calibration["corrected_ps"]),
                "sense": sense["sense"],
                "difference_ps": whole(sense["difference_ps"]),
                "cluster_rows": interval.cluster_size[key],
            })
            selection.append({
                "link_id": key[0], "epoch_index": key[1],
                "report_id": calibration["report_id"],
                "revision": calibration["revision"],
                "status": calibration["status"],
                "effective_epoch_s": calibration["effective_epoch_s"],
                "delay_delta_ps": whole(calibration["correction_ps"]),
            })
            differences.append({
                "epoch_index": key[1], "link_id": key[0],
                "node_a": register["node_a"], "node_b": register["node_b"],
                "technique": register["technique"], "sense": sense["sense"],
                "difference_ps": whole(sense["difference_ps"]),
            })
        differences.sort(key=lambda row: (row["epoch_index"], row["link_id"]))
        self.blobs["reading_ledger.csv"] = self._delimited(
            ["link_id", "epoch_index", "session_id", "receiver_id", "attempt_no",
             "acq_time_s", "raw_offset_ps", "report_id", "correction_ps",
             "corrected_ps", "sense", "difference_ps", "cluster_rows"], ledger, ",")
        self.blobs["calibration_selection.csv"] = self._delimited(
            ["link_id", "epoch_index", "report_id", "revision", "status",
             "effective_epoch_s", "delay_delta_ps"], selection, ",")
        self.blobs["link_differences.psv"] = self._delimited(
            ["epoch_index", "link_id", "node_a", "node_b", "technique", "sense",
             "difference_ps"], differences, "|")

        withdrawal = []
        for row in interval.set_aside:
            withdrawal.append({
                "drop_reason": row["drop_reason"], "link_id": row["link_id"],
                "epoch_index": "NONE" if row["epoch_index"] is None else row["epoch_index"],
                "session_id": row["session_id"], "attempt_no": row["attempt_no"],
                "lock_state": row["lock_state"],
            })
        withdrawal.sort(key=lambda row: (row["drop_reason"], row["link_id"],
                                         str(row["epoch_index"]), row["session_id"],
                                         row["attempt_no"]))
        self.blobs["withdrawal_ledger.tsv"] = self._delimited(
            ["drop_reason", "link_id", "epoch_index", "session_id", "attempt_no",
             "lock_state"], withdrawal, "\t")

    def _graph_family(self):
        interval = self.interval
        papers = self.papers
        self.blobs["link_graph.json"] = self._document({
            "hub_node": papers.hub,
            "component_count": len(interval.components),
            "components": [{
                "component_id": component["component_id"],
                "role": component["role"],
                "root_node": component["root_node"],
                "member_nodes": component["member_nodes"],
                "tree_edges": [dict(edge) for edge in component["tree_edges"]],
                "excluded_link_ids": component["excluded_link_ids"],
            } for component in interval.components],
        })

        grid_rows = []
        for epoch in papers.epoch_range():
            present = sum(1 for link_id in interval.tree_link_ids
                          if (link_id, epoch) in interval.readings)
            grid_rows.append({
                "epoch_index": epoch,
                "epoch_instant_s": papers.instant(epoch),
                "canonical_readings": sum(1 for key in interval.readings
                                          if key[1] == epoch),
                "tree_links_present": present,
                "contributing_oscillators": interval.contributors[epoch],
                "epoch_state": interval.epoch_state[epoch],
            })
        self.blobs["epoch_grid.csv"] = self._delimited(
            ["epoch_index", "epoch_instant_s", "canonical_readings",
             "tree_links_present", "contributing_oscillators", "epoch_state"],
            grid_rows, ",")

        dead = sorted(interval.dead_time,
                      key=lambda row: (row["epoch_index"], row["scope"],
                                       row["subject"], row["cause"]))
        self.blobs["deadtime_ledger.jsonl"] = self._records(dead)

    def _ensemble_family(self):
        interval = self.interval
        papers = self.papers

        series_rows = []
        for osc_id in sorted(papers.oscillator_ids):
            node = papers.oscillator_of[osc_id]["node_id"]
            for epoch in papers.epoch_range():
                value, flag = interval.series.get((osc_id, epoch), (None, "SER_ABSENT"))
                series_rows.append({
                    "osc_id": osc_id, "node_id": node, "epoch_index": epoch,
                    "deviation_ps": "" if value is None else whole(nearest_even(value)),
                    "series_flag": flag,
                })
        self.blobs["oscillator_series.csv"] = self._delimited(
            ["osc_id", "node_id", "epoch_index", "deviation_ps", "series_flag"],
            series_rows, ",")

        self.blobs["prediction_book.json"] = self._document({
            "window_epochs": papers.window_epochs,
            "history_minimum": papers.history_minimum,
            "oscillators": [{
                "osc_id": osc_id,
                "node_id": interval.prediction[osc_id]["node_id"],
                "osc_class": interval.prediction[osc_id]["osc_class"],
                "window_first": interval.window_first,
                "window_last": interval.window_last,
                "valid_count": interval.prediction[osc_id]["valid_count"],
                "anchor_epoch": interval.prediction[osc_id]["anchor_epoch"],
                "anchor_deviation_ps": interval.prediction[osc_id]["anchor_deviation_ps"],
                "frequency_atto": nearest_even(interval.prediction[osc_id]["frequency"]),
                "included": interval.prediction[osc_id]["included"],
                "exclusion_reason": interval.prediction[osc_id]["exclusion_reason"],
            } for osc_id in sorted(papers.oscillator_ids)],
        })

        dispersion_rows = [{
            "osc_id": entry["osc_id"], "node_id": entry["node_id"],
            "osc_class": entry["osc_class"], "valid_count": entry["valid_count"],
            "dispersion_ps": whole(entry["dispersion_ps"]),
            "weight_source": entry["weight_source"],
            "raw_weight": self._ratio(entry["raw_weight"]),
        } for entry in interval.weighted.values()]
        dispersion_rows.sort(key=lambda row: (int(row["dispersion_ps"]), row["osc_id"]))
        self.blobs["dispersion_table.csv"] = self._delimited(
            ["osc_id", "node_id", "osc_class", "valid_count", "dispersion_ps",
             "weight_source", "raw_weight"], dispersion_rows, ",")

        self.blobs["weight_book.json"] = self._document({
            "ensemble_size": len(interval.final_weight),
            "total_weight": self._ratio(interval.total_weight),
            "oscillator_cap": self._ratio(interval.osc_cap),
            "node_cap": self._ratio(interval.node_cap),
            "oscillator_cap_outcome": interval.osc_outcome,
            "node_cap_outcome": interval.node_outcome,
            "final_sweep_outcome": interval.final_outcome,
            "sweeps_used": interval.sweeps_used,
            "damping_numerator": papers.damping.numerator,
            "damping_denominator": papers.damping.denominator,
            "weight_places": papers.weight_places,
            "terminal_residual": self._ratio(interval.terminal_residual),
            "oscillators": [{
                "osc_id": osc_id,
                "node_id": interval.weighted[osc_id]["node_id"],
                "raw_weight": self._ratio(interval.weighted[osc_id]["raw_weight"]),
                "after_oscillator_cap": self._ratio(interval.after_osc[osc_id]),
                "after_node_cap": self._ratio(interval.after_node[osc_id]),
                "final_weight": self._ratio(interval.final_weight[osc_id]),
            } for osc_id in sorted(interval.final_weight)],
            "node_totals": [{"node_id": node, "weight": self._ratio(interval.node_totals[node])}
                            for node in sorted(interval.node_totals)],
        })
        self.blobs["weight_sweep_trace.jsonl"] = self._records(interval.trace)

        scale_rows = []
        steered_rows = []
        for epoch in papers.epoch_range():
            free = interval.free_scale[epoch]
            steered = interval.steered_scale[epoch]
            scale_rows.append({
                "epoch_index": epoch,
                "epoch_state": interval.epoch_state[epoch],
                "contributing_oscillators": interval.contributors[epoch],
                "denominator_weight": self._ratio(interval.denominator[epoch]),
                "free_scale_ps": "" if free is None else whole(nearest_even(free)),
            })
            steered_rows.append({
                "epoch_index": epoch,
                "epoch_state": interval.epoch_state[epoch],
                "free_scale_ps": "" if free is None else whole(nearest_even(free)),
                "correction_ps": whole(nearest_even(interval.correction[epoch])),
                "steered_scale_ps": ("" if steered is None
                                     else whole(nearest_even(steered))),
            })
        self.blobs["ensemble_scale.csv"] = self._delimited(
            ["epoch_index", "epoch_state", "contributing_oscillators",
             "denominator_weight", "free_scale_ps"], scale_rows, ",")
        self.blobs["steered_scale.csv"] = self._delimited(
            ["epoch_index", "epoch_state", "free_scale_ps", "correction_ps",
             "steered_scale_ps"], steered_rows, ",")

        self.blobs["steering_plan.json"] = self._document({
            "decision_epoch": papers.decision_epoch,
            "horizon_epochs": papers.horizon_epochs,
            "grid_atto": papers.grid_atto,
            "departure_ps": self._ratio(interval.departure),
            "raw_step_atto": self._ratio(interval.raw_step),
            "step_atto": interval.step_atto,
            "outcome": interval.steer_outcome,
        })

    def _publish_family(self):
        interval = self.interval
        papers = self.papers

        offset_rows = []
        for node in papers.node_ids:
            for epoch in papers.epoch_range():
                value = interval.published_offset[(node, epoch)]
                offset_rows.append({
                    "node_id": node, "epoch_index": epoch,
                    "offset_ps": "" if value is None else whole(nearest_even(value)),
                    "offset_flag": "OFF_ABSENT" if value is None else "OFF_PUBLISHED",
                })
        self.blobs["node_offsets.csv"] = self._delimited(
            ["node_id", "epoch_index", "offset_ps", "offset_flag"], offset_rows, ",")

        budget_rows = [{
            "node_id": node,
            "component_id": interval.budget[node]["component_id"],
            "role": interval.budget[node]["role"],
            "path_length": interval.budget[node]["path_length"],
            "term_count": interval.budget[node]["term_count"],
            "u_combined_ps2": interval.budget[node]["u_combined_ps2"],
            "u_linear_ps": interval.budget[node]["u_linear_ps"],
        } for node in papers.node_ids]
        self.blobs["uncertainty_budget.tsv"] = self._delimited(
            ["node_id", "component_id", "role", "path_length", "term_count",
             "u_combined_ps2", "u_linear_ps"], budget_rows, "\t")

        ledger_rows = [{
            "node_id": node,
            "status": interval.budget[node]["status"],
            "epochs_available": interval.budget[node]["epochs_available"],
            "offset_mean_ps": self._ratio(interval.budget[node]["offset_mean_ps"]),
            "u_combined_ps2": interval.budget[node]["u_combined_ps2"],
            "u_linear_ps": interval.budget[node]["u_linear_ps"],
        } for node in papers.node_ids]
        ledger_rows.sort(key=lambda row: (-row["epochs_available"], row["node_id"]))
        self.blobs["dissemination_ledger.psv"] = self._delimited(
            ["node_id", "status", "epochs_available", "offset_mean_ps",
             "u_combined_ps2", "u_linear_ps"], ledger_rows, "|")

    def _reports(self):
        interval = self.interval
        papers = self.papers

        for node in papers.report_nodes:
            budget = interval.budget[node]
            self.blobs["node_report_%s.json" % node] = self._document({
                "node_id": node,
                "component_id": budget["component_id"],
                "role": budget["role"],
                "register_revision": papers.revision,
                "reference_oscillator": papers.nodes[node]["reference_oscillator"],
                "path_link_ids": [edge["link_id"] for edge in interval.tree_path[node]],
                "path_length": budget["path_length"],
                "epochs_available": budget["epochs_available"],
                "offset_mean_ps": self._ratio(budget["offset_mean_ps"]),
                "u_combined_ps2": budget["u_combined_ps2"],
                "u_linear_ps": budget["u_linear_ps"],
                "status": budget["status"],
                "oscillators": [{
                    "osc_id": entry["osc_id"],
                    "osc_class": entry["osc_class"],
                    "status": entry["status"],
                    "included": interval.prediction[entry["osc_id"]]["included"],
                    "exclusion_reason": interval.prediction[entry["osc_id"]]["exclusion_reason"],
                    "dispersion_ps": (interval.weighted[entry["osc_id"]]["dispersion_ps"]
                                      if entry["osc_id"] in interval.weighted else 0),
                    "final_weight": self._ratio(interval.final_weight.get(
                        entry["osc_id"], Fraction(0))),
                } for entry in papers.oscillators if entry["node_id"] == node],
            })

        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 "<network_reconciliation>",
                 "  <interval>%s</interval>" % papers.label,
                 '  <closures count="%d">' % len(interval.closures)]
        for closure in interval.closures:
            lines.append("    <closure>")
            lines.append("      <link_id>%s</link_id>" % closure["link_id"])
            lines.append("      <epoch_index>%d</epoch_index>" % closure["epoch_index"])
            lines.append("      <closure_ps>%s</closure_ps>"
                         % whole(nearest_even(closure["closure_ps"])))
            lines.append("    </closure>")
        lines.append("  </closures>")
        lines.append('  <unreconciled count="%d">' % len(interval.unreconciled))
        for link_id in interval.unreconciled:
            lines.append("    <link_id>%s</link_id>" % link_id)
        lines.append("  </unreconciled>")
        lines.append("</network_reconciliation>")
        self.blobs["network_reconciliation.xml"] = self._lines(lines)

        published = [node for node in papers.node_ids
                     if interval.budget[node]["status"] == "DS_PUBLISHED"]
        report = [
            "# Timescale report %s" % papers.label, "",
            "## Network", "",
            "hub node: %s" % papers.hub,
            "register revision: %s" % papers.revision,
            "components: %d" % len(interval.components),
            "registered nodes: %d" % len(papers.node_ids),
            "published nodes: %d" % len(published), "",
            "## Readings", "",
            "canonical readings: %d" % len(interval.readings),
            "set aside rows: %d" % len(interval.set_aside),
            "dead time records: %d" % len(interval.dead_time), "",
            "## Ensemble", "",
            "oscillators catalogued: %d" % len(papers.oscillators),
            "oscillators weighted: %d" % len(interval.final_weight),
            "oscillator cap outcome: %s" % interval.osc_outcome,
            "node cap outcome: %s" % interval.node_outcome,
            "void epochs: %d" % sum(1 for epoch in papers.epoch_range()
                                    if interval.epoch_state[epoch] == "EP_ENSEMBLE_VOID"),
            "",
            "## Steering", "",
            "decision epoch: %d" % papers.decision_epoch,
            "step atto: %s" % whole(interval.step_atto),
            "outcome: %s" % interval.steer_outcome,
        ]
        self.blobs["timescale_report.md"] = self._lines(report)

        summary = ["# Ensemble summary %s" % papers.label, "",
                   "| node | status | epochs | offset mean ps | u linear ps |",
                   "| --- | --- | --- | --- | --- |"]
        for node in papers.node_ids:
            budget = interval.budget[node]
            summary.append("| %s | %s | %d | %s | %d |" % (
                node, budget["status"], budget["epochs_available"],
                self._ratio(budget["offset_mean_ps"]), budget["u_linear_ps"]))
        self.blobs["ensemble_summary.md"] = self._lines(summary)

        index = ["interval = %s" % papers.label,
                 "hub_node = %s" % papers.hub,
                 "register_revision = %s" % papers.revision,
                 "node_count = %d" % len(papers.node_ids),
                 "published_node_count = %d" % len(published)]
        for node in papers.node_ids:
            budget = interval.budget[node]
            index.append("%s.component = %s" % (node, budget["component_id"]))
            index.append("%s.status = %s" % (node, budget["status"]))
            index.append("%s.epochs_available = %d" % (node, budget["epochs_available"]))
        self.blobs["node_index.conf"] = self._lines(index)

    def _manifest(self):
        interval = self.interval
        papers = self.papers
        core = hashlib.sha256()
        for name in papers.digest_order:
            core.update(self.blobs[name])
        publication = hashlib.sha256()
        for name in papers.documents:
            if name == "publication_manifest.json":
                continue
            publication.update(self.blobs[name])
        self.blobs["publication_manifest.json"] = self._document({
            "interval": papers.label,
            "document_count": len(papers.documents),
            "core_order": list(papers.digest_order),
            "digest": core.hexdigest(),
            "publication_digest": publication.hexdigest(),
            "rule_count": papers.rule_count,
            "ensemble_size": len(interval.final_weight),
            "oscillator_cap_outcome": interval.osc_outcome,
            "steering_outcome": interval.steer_outcome,
        })


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def publish(data_dir: str, out_dir: str) -> int:
    papers = Papers(data_dir)
    blobs = Publication(Interval(papers)).blobs
    os.makedirs(out_dir, exist_ok=True)
    for name in papers.documents:
        with open(os.path.join(out_dir, name), "wb") as handle:
            handle.write(blobs[name])
    return len(papers.documents)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Recompute one publication interval of the timing network.")
    parser.add_argument("--data", default=DEFAULT_DATA)
    parser.add_argument("--out", default=DEFAULT_OUT)
    options = parser.parse_args(argv)
    try:
        written = publish(options.data, options.out)
    except PaperFault as trouble:
        sys.stderr.write("%s\n" % trouble)
        return 2
    sys.stdout.write("wrote %d documents to %s\n" % (written, options.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
