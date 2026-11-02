"""Deterministic verifier for the array timing network task.

The verifier owns its corpus. It regenerates the whole input tree from a
named seed into a temporary directory, recomputes every expected artifact
from that regeneration, and grades the agent bytes under the output directory
against it. It never reads the agent corpus, which does not exist in this
container.

Most of the positive weight is spent on the delivered program rather than on
the delivered bytes. Three further intervals are minted here from seeds the
agent never sees, two under a strained acquisition profile and one under a
sparse profile the shipped interval does not use, and the delivered timescale
program is run against each of them as a subprocess. Its output is graded byte
for byte against the publication those papers entail.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path


# The agent corpus path is assembled rather than written as a literal,
# because this module also runs where no such directory exists.
INPUT_ROOT = "/app" + "/data"
OUTPUT_ROOT = "/app" + "/out"
PROGRAM_NAME = "timescale.py"

# Imports the corpus generator and the grading half need. The reference
# pipeline needs none of them, so the delivered program carries no import it
# does not use.
import io
import os
import random
import shutil
import sqlite3
import subprocess
import tempfile

from rewardkit import criteria, criterion


# --------------------------------------------------------------------------
# rewardkit adapter
#
# Required inversion/never-raise note (gate 03 TS-15, TS-29): _rk swallows
# every exception so a bad or missing agent output returns False rather than
# aborting the run. A negative wrapper returns True (fires its penalty) only
# when its detector completes without raising, which happens only when the
# cheat it rebuilds is present; an honest or empty delivery makes the detector
# raise, so the wrapper returns False. Polarity is the registered weight alone.
# --------------------------------------------------------------------------
def _rk(fn) -> bool:
    try:
        fn()
        return True
    except Exception:
        return False


@criterion(description="Every declared artifact is present under the output directory.")
def all_artifacts_exist(workspace: Path) -> bool:
    return _rk(test_all_artifacts_exist)


@criterion(description="The publication manifest, the link graph and the prediction book carry the shape the output schema reference fixes.")
def core_documents_parse(workspace: Path) -> bool:
    return _rk(test_core_documents_parse)


@criterion(description="The shipped interval core family matches byte for byte.")
def shipped_core_exact(workspace: Path) -> bool:
    return _rk(test_shipped_core_exact)


@criterion(description="The shipped interval graph family matches byte for byte.")
def shipped_graph_family_exact(workspace: Path) -> bool:
    return _rk(test_shipped_graph_family_exact)


@criterion(description="The shipped interval weight family matches byte for byte.")
def shipped_weight_family_exact(workspace: Path) -> bool:
    return _rk(test_shipped_weight_family_exact)


@criterion(description="The shipped interval publish family matches byte for byte.")
def shipped_publish_family_exact(workspace: Path) -> bool:
    return _rk(test_shipped_publish_family_exact)


@criterion(description="The delivered program reproduces the eval interval core family.")
def program_eval_core_exact(workspace: Path) -> bool:
    return _rk(test_program_eval_core_exact)


@criterion(description="The delivered program reproduces the challenge interval core family.")
def program_challenge_core_exact(workspace: Path) -> bool:
    return _rk(test_program_challenge_core_exact)


@criterion(description="The delivered program reproduces the probe interval core family.")
def program_probe_core_exact(workspace: Path) -> bool:
    return _rk(test_program_probe_core_exact)


@criterion(description="The delivered program reproduces the eval interval graph family.")
def program_eval_graph_exact(workspace: Path) -> bool:
    return _rk(test_program_eval_graph_exact)


@criterion(description="The delivered program reproduces the eval interval weight family.")
def program_eval_weight_exact(workspace: Path) -> bool:
    return _rk(test_program_eval_weight_exact)


@criterion(description="The delivered program reproduces the eval interval publish family.")
def program_eval_publish_exact(workspace: Path) -> bool:
    return _rk(test_program_eval_publish_exact)


@criterion(description="The delivered program reproduces the challenge interval graph family.")
def program_challenge_graph_exact(workspace: Path) -> bool:
    return _rk(test_program_challenge_graph_exact)


@criterion(description="The delivered program reproduces the challenge interval weight family.")
def program_challenge_weight_exact(workspace: Path) -> bool:
    return _rk(test_program_challenge_weight_exact)


@criterion(description="The delivered program reproduces the challenge interval publish family.")
def program_challenge_publish_exact(workspace: Path) -> bool:
    return _rk(test_program_challenge_publish_exact)


@criterion(description="The delivered program reproduces the probe interval graph family.")
def program_probe_graph_exact(workspace: Path) -> bool:
    return _rk(test_program_probe_graph_exact)


@criterion(description="The delivered program reproduces the probe interval weight family.")
def program_probe_weight_exact(workspace: Path) -> bool:
    return _rk(test_program_probe_weight_exact)


@criterion(description="The delivered program reproduces the probe interval publish family.")
def program_probe_publish_exact(workspace: Path) -> bool:
    return _rk(test_program_probe_publish_exact)


@criterion(description="The delivered bytes equal the reconstruction that keeps a lock-lost attempt as canonical.")
def negative_unlocked_attempt_selected(workspace: Path) -> bool:
    return _rk(test_negative_weight_unlocked_attempt_selected)


@criterion(description="The delivered bytes equal the reconstruction that selects the latest issued calibration report.")
def negative_latest_issued_calibration(workspace: Path) -> bool:
    return _rk(test_negative_weight_latest_issued_calibration)


@criterion(description="The delivered bytes equal the reconstruction that predicts by a least squares fit.")
def negative_least_squares_prediction(workspace: Path) -> bool:
    return _rk(test_negative_weight_least_squares_prediction)


@criterion(description="The delivered bytes equal the reconstruction that clamps the weight vector to the cap.")
def negative_clamped_weight_vector(workspace: Path) -> bool:
    return _rk(test_negative_weight_clamped_weight_vector)


@criterion(description="The delivered bytes equal the reconstruction that closes every placement residue onto one fixed holder.")
def negative_fixed_residue_carrier(workspace: Path) -> bool:
    return _rk(test_negative_weight_fixed_residue_carrier)


@criterion(description="The delivered bytes equal the reconstruction that rounds the residual before averaging.")
def negative_rounded_before_the_average(workspace: Path) -> bool:
    return _rk(test_negative_weight_rounded_before_the_average)


@criterion(description="The delivered bytes equal the reconstruction that reads the current node register.")
def negative_current_node_register(workspace: Path) -> bool:
    return _rk(test_negative_weight_current_node_register)


@criterion(description="The delivered bytes equal the reconstruction that steers from the decision epoch.")
def negative_steering_from_the_decision_epoch(workspace: Path) -> bool:
    return _rk(test_negative_weight_steering_from_the_decision_epoch)


@criterion(description="The delivered bytes equal the hardcoded shipped sample answers, with no program behind them or a program that produces nothing on every minted interval.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _rk(test_negative_weight_hardcoded_sample_answers)


@criterion(description="The manifest digest disagrees with the artifact bytes beside it.")
def negative_manifest_digest_mismatch(workspace: Path) -> bool:
    return _rk(test_negative_weight_manifest_digest_mismatch)


@criterion(description="The delivered program emits the same bytes regardless of its input directory.")
def negative_program_ignores_its_input(workspace: Path) -> bool:
    return _rk(test_negative_weight_program_ignores_its_input)


@criterion(description="The delivered program emits different bytes across two runs over one input.")
def negative_nondeterministic_output(workspace: Path) -> bool:
    return _rk(test_negative_weight_nondeterministic_output)


@criterion(description="The delivered program changes its output when its input directory is renamed.")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    return _rk(test_negative_weight_filename_dependent_behaviour)


@criterion(description="The delivered program mutates its input directory or writes an incomplete or extra set of outputs.")
def negative_program_dirties_its_directories(workspace: Path) -> bool:
    return _rk(test_negative_weight_program_dirties_its_directories)


@criterion(description="The delivered program reaches for the shipped training corpus at runtime.")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    return _rk(test_negative_weight_reads_training_corpus_at_runtime)


@criterion(description="A module dropped beside the artifacts shadows a name the verifier imports.")
def negative_rebinds_verifier_dependencies(workspace: Path) -> bool:
    return _rk(test_negative_weight_rebinds_verifier_dependencies)


criteria.all_artifacts_exist(weight=1)
criteria.core_documents_parse(weight=1)
criteria.shipped_core_exact(weight=3)
criteria.shipped_graph_family_exact(weight=3)
criteria.shipped_weight_family_exact(weight=3)
criteria.shipped_publish_family_exact(weight=3)
criteria.program_eval_core_exact(weight=5)
criteria.program_challenge_core_exact(weight=5)
criteria.program_probe_core_exact(weight=5)
criteria.program_eval_graph_exact(weight=5)
criteria.program_eval_weight_exact(weight=5)
criteria.program_eval_publish_exact(weight=5)
criteria.program_challenge_graph_exact(weight=5)
criteria.program_challenge_weight_exact(weight=5)
criteria.program_challenge_publish_exact(weight=5)
criteria.program_probe_graph_exact(weight=5)
criteria.program_probe_weight_exact(weight=5)
criteria.program_probe_publish_exact(weight=5)
criteria.negative_unlocked_attempt_selected(weight=-5)
criteria.negative_latest_issued_calibration(weight=-5)
criteria.negative_least_squares_prediction(weight=-5)
criteria.negative_clamped_weight_vector(weight=-5)
criteria.negative_fixed_residue_carrier(weight=-5)
criteria.negative_rounded_before_the_average(weight=-5)
criteria.negative_current_node_register(weight=-3)
criteria.negative_steering_from_the_decision_epoch(weight=-3)
criteria.negative_hardcoded_sample_answers(weight=-3)
criteria.negative_manifest_digest_mismatch(weight=-3)
criteria.negative_program_ignores_its_input(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_filename_dependent_behaviour(weight=-3)
criteria.negative_program_dirties_its_directories(weight=-3)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)
criteria.negative_rebinds_verifier_dependencies(weight=-3)


# --------------------------------------------------------------------------
# vocabularies and fixed structure
#
# Every closed vocabulary compared anywhere downstream is listed here, and the
# corpus is asserted to emit every member of every one of them, so no
# comparison is made against a token the agent never sees.
# --------------------------------------------------------------------------

# Published ratios carry this many decimal places. Every other published
# quantity is a whole number in the unit its stage names.
PLACES = 12

# Seconds in one grid step of the publication interval.
STEP_SECONDS = 86400

# Number of grid epochs in a publication interval.
INTERVAL_EPOCHS = 30

# Number of archived epochs in the preceding interval.
ARCHIVE_EPOCHS = 24

NODES = [
    "nd_arden",
    "nd_borrow",
    "nd_calder",
    "nd_dunmore",
    "nd_ellsmere",
    "nd_farrow",
    "nd_gantry",
    "nd_harlow",
    "nd_ingle",
    "nd_jarrow",
    "nd_kelvin",
    "nd_lyddon",
]

# The node the network configuration names as the transfer hub.
HUB_NODE = "nd_calder"

# Connected components as the link register lays them out. The hub sits in
# CORE_NODES; RIM_NODES form a second component with no path to the hub;
# nd_lyddon is registered with no usable link at all.
CORE_NODES = [
    "nd_arden",
    "nd_borrow",
    "nd_calder",
    "nd_dunmore",
    "nd_ellsmere",
    "nd_farrow",
    "nd_gantry",
    "nd_harlow",
    "nd_ingle",
]
RIM_NODES = ["nd_jarrow", "nd_kelvin"]
LONE_NODES = ["nd_lyddon"]

# Oscillator classes. The ceiling weight of each class is published only in
# the workbook, never in a plain text file.
OSC_CLASSES = [
    "OSC_CRYO_SAPPHIRE",
    "OSC_CS_BEAM",
    "OSC_HMASER",
    "OSC_OCXO",
    "OSC_RB_FOUNTAIN",
]

# Link techniques, with the measurement sense each one records and the rank
# used to break a tie between two candidate tree edges of equal uncertainty.
LINK_TECHNIQUES = ["LK_FIBRE_TWO_WAY", "LK_GNSS_CV", "LK_GNSS_PPP", "LK_TWSTFT"]

TECHNIQUE_SENSE = {
    "LK_FIBRE_TWO_WAY": "SENSE_A_MINUS_B",
    "LK_TWSTFT": "SENSE_A_MINUS_B",
    "LK_GNSS_PPP": "SENSE_B_MINUS_A",
    "LK_GNSS_CV": "SENSE_B_MINUS_A",
}

TECHNIQUE_RANK = {
    "LK_FIBRE_TWO_WAY": 1,
    "LK_TWSTFT": 2,
    "LK_GNSS_PPP": 3,
    "LK_GNSS_CV": 4,
}

MEASUREMENT_SENSES = ["SENSE_A_MINUS_B", "SENSE_B_MINUS_A"]

# Lock states an acquisition attempt can carry. Only LOCK_HELD makes an
# attempt eligible to be the canonical reading of its cluster.
LOCK_STATES = ["LOCK_HELD", "LOCK_LOST", "LOCK_SLIP", "LOCK_UNKNOWN"]

# Every reason a reading cluster can leave the ledger.
DROP_REASONS = [
    "DR_LINK_UNREGISTERED",
    "DR_NO_LOCKED_ATTEMPT",
    "DR_OUTSIDE_INTERVAL",
    "DR_SELF_LOOP",
    "DR_SESSION_WITHDRAWN",
]

# Every reason an oscillator can leave the ensemble.
EXCLUSION_REASONS = [
    "EX_DECOMMISSIONED",
    "EX_NO_ARCHIVE",
    "EX_SHORT_HISTORY",
    "EX_UNANCHORED_NODE",
]

# Quality flags on an archived deviation. Only ARC_VALID counts toward the
# history window.
ARCHIVE_FLAGS = ["ARC_ESTIMATED", "ARC_SUSPECT", "ARC_VALID", "ARC_VOID"]

# How a component of the link graph is rooted.
COMPONENT_ROLES = ["ROLE_ANCHORED", "ROLE_UNANCHORED"]

# How the capping sweep ended.
SWEEP_OUTCOMES = ["SW_BUDGET_EXHAUSTED", "SW_CAP_UNSATISFIABLE", "SW_SETTLED"]

# How the steering step resolved.
STEER_OUTCOMES = ["ST_APPLIED", "ST_NO_REALISATION", "ST_TRUNCATED_TO_ZERO"]

# Whether an epoch carries an ensemble value at all.
EPOCH_STATES = ["EP_ENSEMBLE_VOID", "EP_POPULATED"]

# The four nodes whose per node report is a declared artifact.
REPORT_NODES = ["nd_arden", "nd_calder", "nd_jarrow", "nd_lyddon"]

# Artifacts whose bytes enter the core digest, in the order the
# serialisation contract states.
CORE_FILES = [
    "reading_ledger.csv",
    "link_differences.psv",
    "oscillator_series.csv",
    "weight_book.json",
    "ensemble_scale.csv",
    "steered_scale.csv",
]

ARTIFACTS = [
    "reading_ledger.csv",
    "withdrawal_ledger.tsv",
    "calibration_selection.csv",
    "link_differences.psv",
    "link_graph.json",
    "epoch_grid.csv",
    "deadtime_ledger.jsonl",
    "oscillator_series.csv",
    "prediction_book.json",
    "dispersion_table.csv",
    "weight_book.json",
    "weight_sweep_trace.jsonl",
    "ensemble_scale.csv",
    "steering_plan.json",
    "steered_scale.csv",
    "node_offsets.csv",
    "uncertainty_budget.tsv",
    "dissemination_ledger.psv",
    "node_report_nd_arden.json",
    "node_report_nd_calder.json",
    "node_report_nd_jarrow.json",
    "node_report_nd_lyddon.json",
    "network_reconciliation.xml",
    "timescale_report.md",
    "ensemble_summary.md",
    "publication_manifest.json",
    "node_index.conf",
]

# Graded families. Every positive test above the existence floor grades a
# whole family at once.
# The core family is the six artifacts the core digest runs over plus the
# manifest that carries both digests. The publication digest inside the
# manifest runs over every other artifact, so the manifest moves when anything
# in the publication moves, and the core family carries the whole delivery.
FAM_CORE = list(CORE_FILES) + ["publication_manifest.json"]
FAM_GRAPH = [
    "withdrawal_ledger.tsv",
    "calibration_selection.csv",
    "link_graph.json",
    "epoch_grid.csv",
    "deadtime_ledger.jsonl",
]
FAM_WEIGHT = [
    "prediction_book.json",
    "dispersion_table.csv",
    "weight_sweep_trace.jsonl",
    "steering_plan.json",
]
FAM_PUBLISH = [
    "node_offsets.csv",
    "uncertainty_budget.tsv",
    "dissemination_ledger.psv",
    "node_report_nd_arden.json",
    "node_report_nd_calder.json",
    "node_report_nd_jarrow.json",
    "node_report_nd_lyddon.json",
    "network_reconciliation.xml",
    "timescale_report.md",
    "ensemble_summary.md",
    "node_index.conf",
]

# The rules the publication counts as its rule_count, in the order the stages
# apply them. Each identifier is a documented decision and a switch the author
# side mutation matrix reverts one at a time. The matrix carries three further
# switches that this list does not, R_TREE_PATH_COST, R_PLACEMENT_RESIDUE and
# R_RESIDUE_ROTATION, because rule_count is a published figure the output
# schema reference pins and it does not move when a decision is added.
RULE_IDS = [
    "R_WITHDRAWN_SESSIONS",
    "R_LOCK_STATE",
    "R_INTERVAL_BOUNDS",
    "R_CAL_APPLICABLE",
    "R_CAL_REVISION_TIE",
    "R_CAL_NANOSECOND",
    "R_SENSE_NORMALISE",
    "R_TREE_UNCERTAINTY",
    "R_TREE_TECHNIQUE_TIE",
    "R_UNANCHORED_ROOT",
    "R_UNANCHORED_EXCLUDE",
    "R_WINDOW_HALF_OPEN",
    "R_NEAREST_WINS",
    "R_NO_INTERPOLATION",
    "R_FROZEN_REGISTER",
    "R_TWO_POINT_SLOPE",
    "R_HISTORY_MINIMUM",
    "R_PUBLISHED_DISPERSION",
    "R_ZERO_DISPERSION_CEILING",
    "R_CAP_REDISTRIBUTE",
    "R_DAMPED_STEP",
    "R_PASS_QUANTISATION",
    "R_CAP_ORDER",
    "R_FINAL_OSC_SWEEP",
    "R_SWEEP_BUDGET",
    "R_EPOCH_DENOMINATOR",
    "R_ROUND_AT_WRITE",
    "R_STEER_NEXT_EPOCH",
    "R_STEER_TRUNCATE",
    "R_UNCERTAINTY_LINEAR",
    "R_ROW_ORDER",
    "R_DIGEST_ORDER",
]

# Stage T09 gives the total the two caps are taken from twice: its opening
# paragraph forms W from the raw weights, and its grid paragraph, with trap 47,
# takes the total of the weights placed on the grid. Both readings are graded
# as correct. This switch is not a rule and never counts toward rule_count; it
# selects the raw weight reading, and the default is the placed one.
READING_CAP_TOTAL_RAW = "READING_CAP_TOTAL_RAW"
GRADED_READINGS = [frozenset(), frozenset({READING_CAP_TOTAL_RAW})]

# --------------------------------------------------------------------------
# exact arithmetic and serialisation primitives
#
# Nothing in this module uses a float. Every quantity is an int or a
# Fraction until the moment it is written, and the write is the only place a
# rounding rule is applied.
# --------------------------------------------------------------------------


def half_even(value) -> int:
    """Round an exact Fraction to the nearest integer, ties to even."""
    frac = Fraction(value)
    floor_part = frac.numerator // frac.denominator
    remainder = frac - floor_part
    if remainder < Fraction(1, 2):
        return floor_part
    if remainder > Fraction(1, 2):
        return floor_part + 1
    return floor_part if floor_part % 2 == 0 else floor_part + 1


def trunc_zero(value) -> int:
    """Truncate an exact Fraction toward zero."""
    frac = Fraction(value)
    quotient = abs(frac.numerator) // frac.denominator
    return -quotient if frac < 0 else quotient


def ratio(value) -> str:
    """Render an exact Fraction with PLACES decimals, ties to even."""
    frac = Fraction(value)
    scale = 10 ** PLACES
    scaled = half_even(frac * scale)
    sign = "-" if scaled < 0 else ""
    scaled = abs(scaled)
    whole, part = divmod(scaled, scale)
    text = f"{sign}{whole}.{part:0{PLACES}d}"
    if text.startswith("-") and set(text[1:]) <= {"0", "."}:
        text = text[1:]
    return text


def signed(value: int) -> str:
    """Render a whole number, with negative zero collapsed to zero."""
    return str(int(value) + 0)


def mean_abs(values) -> Fraction:
    """Exact mean of the absolute values of a sequence of Fractions."""
    items = list(values)
    if not items:
        return Fraction(0)
    total = Fraction(0)
    for item in items:
        total += abs(Fraction(item))
    return total / len(items)


def phase_ps(femto_atto: Fraction, steps: int) -> Fraction:
    """Phase accumulated in picoseconds.

    femto_atto is a frequency offset in parts in ten to the eighteenth and
    steps is a whole number of grid steps of STEP_SECONDS seconds each. One
    grid step at one part in ten to the eighteenth is 864 / 10000 of a
    picosecond, which the expression below keeps exact.
    """
    return Fraction(864, 10000) * Fraction(femto_atto) * steps


def slope_atto(delta_ps: Fraction, delta_steps: int) -> Fraction:
    """Frequency in parts in ten to the eighteenth from a phase difference."""
    if delta_steps == 0:
        return Fraction(0)
    return Fraction(delta_ps) * Fraction(10000, 864) / delta_steps


# --------------------------------------------------------------------------
# canonical serialisation helpers
# --------------------------------------------------------------------------
def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=True) + "\n"


def compact_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


# --------------------------------------------------------------------------
# readers
# --------------------------------------------------------------------------
def read_delim(path: Path, delim: str = ",") -> list:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter=delim))


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_lines_json(path: Path) -> list:
    out = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def read_flat_yaml(path: Path) -> dict:
    """A deliberately small reader for the flat policy files this corpus
    ships: scalars, and one level of list under a key."""
    out: dict = {}
    key = None
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith("  - "):
            if key is not None:
                out.setdefault(key, [])
                if isinstance(out[key], list):
                    out[key].append(line[4:].strip().strip('"'))
            continue
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            key = k.strip()
            v = v.strip().strip('"')
            out[key] = v if v != "" else []
    return out


def read_flat_xml(path: Path) -> dict:
    root = ET.fromstring(Path(path).read_text(encoding="utf-8"))
    out: dict = {"_root": root}
    for child in root:
        out.setdefault(child.tag, []).append(child)
    return out


# --------------------------------------------------------------------------
# workbook reader (stdlib only: zipfile and xml, cached values)
# --------------------------------------------------------------------------
_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_RID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _col_to_idx(ref: str) -> int:
    letters = "".join(c for c in ref if c.isalpha())
    n = 0
    for c in letters:
        n = n * 26 + (ord(c) - 64)
    return n - 1


def read_xlsx_sheets(path: Path) -> dict:
    with zipfile.ZipFile(path) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", _NS):
                shared.append("".join(t.text or "" for t in si.iter("{%s}t" % _NS["m"])))
        wb = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rid_to_target = {r.get("Id"): r.get("Target") for r in rels}
        sheets = {}
        for sh in wb.find("m:sheets", _NS):
            name = sh.get("name")
            target = rid_to_target[sh.get(_RID)]
            if not target.startswith("xl/"):
                target = "xl/" + target
            data = ET.fromstring(zf.read(target))
            rows = []
            for row in data.iter("{%s}row" % _NS["m"]):
                cells = []
                for c in row.findall("m:c", _NS):
                    idx = _col_to_idx(c.get("r", "A1"))
                    while len(cells) <= idx:
                        cells.append("")
                    v = c.find("m:v", _NS)
                    val = v.text if v is not None else ""
                    if c.get("t") == "s" and val != "":
                        val = shared[int(val)]
                    cells[idx] = val or ""
                rows.append(cells)
            sheets[name] = rows
        return sheets


# --------------------------------------------------------------------------
# pdf text extraction (the memo is written by write_pdf below, so its
# content streams are plain uncompressed text operators)
# --------------------------------------------------------------------------
def read_pdf_lines(path: Path) -> list:
    raw = Path(path).read_bytes().decode("latin-1")
    out = []
    for m in re.finditer(r"\((.*?)\) Tj", raw):
        out.append(m.group(1).replace(r"\(", "(").replace(r"\)", ")").replace("\\\\", "\\"))
    return out


def pdf_scalar(lines: list, key: str) -> str:
    for line in lines:
        if line.startswith(key):
            return line.split("=", 1)[1].strip()
    raise KeyError(key)

# --------------------------------------------------------------------------
# corpus loaders
# --------------------------------------------------------------------------
def _as_int(text) -> int:
    text = str(text).strip()
    if text == "":
        return 0
    return int(text)


def load_config(root: Path) -> dict:
    return read_json(root / "network_config.json")


def load_nodes(root: Path, config: dict, off=frozenset()) -> dict:
    """Node metadata at the register revision the interval header freezes.

    The revision named in the interval header is the applicable one. The
    register carries later revisions too, and a snapshot of the latest one
    ships beside it under its own name.
    """
    if "R_FROZEN_REGISTER" in off:
        rows = read_delim(root / "node_register_current.csv")
        wanted = None
    else:
        rows = read_delim(root / "node_register_frozen.csv")
        wanted = config["frozen_register_revision"]
    out = {}
    for row in rows:
        if wanted is not None and row["register_revision"] != wanted:
            continue
        out[row["node_id"]] = {
            "node_id": row["node_id"],
            "register_revision": row["register_revision"],
            "site_class": row["site_class"],
            "reference_oscillator": row["reference_oscillator"],
            "declared_uncertainty_ps": _as_int(row["declared_uncertainty_ps"]),
        }
    return out


def load_oscillators(root: Path) -> list:
    rows = read_delim(root / "oscillator_catalogue.csv")
    out = []
    for row in rows:
        out.append({
            "osc_id": row["osc_id"],
            "node_id": row["node_id"],
            "osc_class": row["osc_class"],
            "status": row["status"],
        })
    return sorted(out, key=lambda r: r["osc_id"])


def load_links(root: Path) -> dict:
    out = {}
    for row in read_delim(root / "link_register.csv"):
        out[row["link_id"]] = {
            "link_id": row["link_id"],
            "node_a": row["node_a"],
            "node_b": row["node_b"],
            "technique": row["technique"],
            "published_uncertainty_ps": _as_int(row["published_uncertainty_ps"]),
        }
    return out


def load_reports(root: Path) -> dict:
    """The delay calibration ledger and the supplement that extends it.

    The supplement is not a replacement. Both files are reports of the same
    register and a link's report set is the union of the two.
    """
    out: dict = {}
    for row in read_delim(root / "delay_calibration_ledger.csv"):
        out.setdefault(row["link_id"], []).append({
            "report_id": row["report_id"],
            "link_id": row["link_id"],
            "effective_epoch_s": _as_int(row["effective_epoch_s"]),
            "issued_epoch_s": _as_int(row["issued_epoch_s"]),
            "revision": _as_int(row["revision"]),
            "delay_a_ns": _as_int(row["delay_a_ns"]),
            "delay_b_ns": _as_int(row["delay_b_ns"]),
            "status": row["status"],
        })
    for row in read_delim(root / "delay_calibration_supplement.psv", "|"):
        out.setdefault(row["link_id"], []).append({
            "report_id": row["report_id"],
            "link_id": row["link_id"],
            "effective_epoch_s": _as_int(row["effective_epoch_s"]),
            "issued_epoch_s": _as_int(row["issued_epoch_s"]),
            "revision": _as_int(row["revision"]),
            "delay_a_ns": _as_int(row["delay_a_ns"]),
            "delay_b_ns": _as_int(row["delay_b_ns"]),
            "status": row["status"],
        })
    for key in out:
        out[key].sort(key=lambda r: (r["effective_epoch_s"], r["revision"], r["report_id"]))
    return out


def load_sessions(root: Path) -> list:
    out = []
    for row in read_delim(root / "comparison_session_log.csv"):
        out.append({
            "session_id": row["session_id"],
            "link_id": row["link_id"],
            "receiver_id": row["receiver_id"],
            "attempt_no": _as_int(row["attempt_no"]),
            "acq_time_s": _as_int(row["acq_time_s"]),
            "raw_offset_ps": _as_int(row["raw_offset_ps"]),
            "lock_state": row["lock_state"],
        })
    return out


def load_withdrawn(root: Path) -> set:
    out = set()
    for row in read_delim(root / "session_withdrawal_journal.tsv", "\t"):
        out.add(row["session_id"])
    return out


def load_local(root: Path) -> dict:
    out = {}
    for row in read_delim(root / "local_comparison_log.psv", "|"):
        out[(row["osc_id"], _as_int(row["epoch_index"]))] = {
            "local_offset_ps": _as_int(row["local_offset_ps"]),
            "monitor_flag": row["monitor_flag"],
        }
    return out


def load_archive(root: Path) -> dict:
    out: dict = {}
    for row in read_delim(root / "prior_interval_deviations.psv", "|"):
        out.setdefault(row["osc_id"], {})[_as_int(row["archive_epoch"])] = {
            "deviation_ps": _as_int(row["deviation_ps"]),
            "quality_flag": row["quality_flag"],
        }
    return out


def load_realisation(root: Path) -> dict:
    out = {}
    for row in read_delim(root / "primary_standard_realisation.csv"):
        if row["realisation_ps"].strip() == "":
            continue
        out[_as_int(row["epoch_index"])] = _as_int(row["realisation_ps"])
    return out


def load_workbook(root: Path, config: dict) -> dict:
    """The live workbook sheet, chosen by matching its key cell.

    The workbook carries two sheets. The live one is the sheet whose cell B1
    holds the workbook sheet key the interval header names; the other is a
    superseded draft.
    """
    sheets = read_xlsx_sheets(root / "timing_network_workbook.xlsx")
    key = config["workbook_sheet_key"]
    live = None
    for name in sorted(sheets):
        rows = sheets[name]
        if rows and len(rows[0]) > 1 and rows[0][1] == key:
            live = rows
            break
    if live is None:
        raise KeyError("no workbook sheet carries the interval sheet key")
    ceilings: dict = {}
    components: dict = {}
    node_cap_num = 0
    node_cap_den = 1
    section = ""
    for row in live:
        cells = list(row) + ["", "", "", ""]
        head = cells[0].strip()
        if head.startswith("SECTION"):
            section = cells[1].strip()
            continue
        if section == "CLASS_CEILING" and head in OSC_CLASSES:
            ceilings[head] = int(cells[1])
        elif section == "NODE_CAP" and head == "NODE_WEIGHT_CAP":
            node_cap_num = int(cells[1])
            node_cap_den = int(cells[2])
        elif section == "UNCERTAINTY_COMPONENTS" and head.startswith("osc_"):
            components.setdefault(head, []).append(int(cells[2]))
    return {
        "class_ceiling": ceilings,
        "node_cap_num": node_cap_num,
        "node_cap_den": node_cap_den,
        "components": {k: list(v) for k, v in components.items()},
    }


def load_memo(root: Path) -> dict:
    """The signed calibration memo. Four control values live here and in no
    plain text file in the corpus."""
    lines = read_pdf_lines(root / "network_calibration_memo.pdf")
    return {
        "osc_cap_num": int(pdf_scalar(lines, "OSC_WEIGHT_CAP_NUMERATOR")),
        "osc_cap_den": int(pdf_scalar(lines, "OSC_WEIGHT_CAP_DENOMINATOR")),
        "sweep_budget": int(pdf_scalar(lines, "CAP_SWEEP_BUDGET")),
        "history_minimum": int(pdf_scalar(lines, "HISTORY_MINIMUM_EPOCHS")),
    }


def load_policies(root: Path) -> dict:
    grid = read_flat_yaml(root / "epoch_grid_policy.yaml")
    weighting = read_flat_yaml(root / "weighting_policy.yaml")
    steering = read_flat_yaml(root / "steering_policy.yaml")
    ordering = read_flat_yaml(root / "ordering_dependencies.yaml")
    return {
        "attribution_tolerance_s": int(grid["attribution_tolerance_s"]),
        "grid_instant_offset_s": int(grid["grid_instant_offset_s"]),
        "history_window_epochs": int(weighting["history_window_epochs"]),
        "weight_scale": int(weighting["weight_scale"]),
        "valid_archive_flag": weighting["valid_archive_flag"],
        "steer_decision_epoch": int(steering["decision_epoch"]),
        "steer_horizon_epochs": int(steering["horizon_epochs"]),
        "steer_grid_atto": int(steering["grid_atto"]),
        "damping_num": int(weighting["damping_numerator"]),
        "damping_den": int(weighting["damping_denominator"]),
        "weight_places": int(weighting["weight_places"]),
        "digest_order": ordering["digest_order"],
    }


def load_all(root: Path, off=frozenset()) -> dict:
    root = Path(root)
    config = load_config(root)
    return {
        "root": root,
        "config": config,
        # The interval header carries its own length. Nothing below assumes a
        # thirty epoch interval or a twenty four epoch archive.
        "epochs": int(config["interval_epochs"]),
        "archive_epochs": int(config["archive_epochs"]),
        "policies": load_policies(root),
        "nodes": load_nodes(root, config, off),
        "oscillators": load_oscillators(root),
        "links": load_links(root),
        "reports": load_reports(root),
        "sessions": load_sessions(root),
        "withdrawn": load_withdrawn(root),
        "local": load_local(root),
        "archive": load_archive(root),
        "realisation": load_realisation(root),
        "workbook": load_workbook(root, config),
        "memo": load_memo(root),
    }


# --------------------------------------------------------------------------
# T02 helper: the applicable delay calibration report
# --------------------------------------------------------------------------
def applicable_report(reports: list, at_s: int, off=frozenset()):
    """The report that governs a reading taken at at_s.

    The applicable report is the one with the greatest effective epoch on or
    before the reading. Two reports may share an effective epoch, and the
    smaller revision number wins, because a signed report is registered
    before the provisional restatement that carries the next revision.
    """
    if not reports:
        return None
    if "R_CAL_APPLICABLE" in off:
        return max(reports, key=lambda r: (r["issued_epoch_s"], r["report_id"]))
    eligible = [r for r in reports if r["effective_epoch_s"] <= at_s]
    if not eligible:
        return None
    best = max(r["effective_epoch_s"] for r in eligible)
    same = [r for r in eligible if r["effective_epoch_s"] == best]
    if "R_CAL_REVISION_TIE" in off:
        return max(same, key=lambda r: (r["revision"], r["report_id"]))
    return min(same, key=lambda r: (r["revision"], r["report_id"]))


def calibration_ps(report, off=frozenset()) -> int:
    """The delay correction in picoseconds.

    The ledger publishes both delays in nanoseconds; every reading is in
    picoseconds.
    """
    if report is None:
        return 0
    delta = report["delay_a_ns"] - report["delay_b_ns"]
    if "R_CAL_NANOSECOND" in off:
        return delta
    return delta * 1000


# --------------------------------------------------------------------------
# the thirteen stages
# --------------------------------------------------------------------------
def stage_grid(data: dict) -> list:
    """The publication grid: one instant per epoch."""
    start = data["config"]["interval_start_epoch_s"]
    offset = data["policies"]["grid_instant_offset_s"]
    return [start + (k - 1) * STEP_SECONDS + offset for k in range(1, data["epochs"] + 1)]


def stage_t01_readings(data: dict, off=frozenset()) -> dict:
    """T01 reading canonicalisation."""
    grid = stage_grid(data)
    tol = data["policies"]["attribution_tolerance_s"]
    links = data["links"]
    withdrawn = data["withdrawn"]

    attributed = []
    dropped = []
    for row in data["sessions"]:
        epoch = None
        for k, instant in enumerate(grid, start=1):
            lo = instant - tol
            hi = instant + tol
            if "R_WINDOW_HALF_OPEN" in off:
                inside = lo <= row["acq_time_s"] <= hi
            else:
                inside = lo <= row["acq_time_s"] < hi
            if inside:
                epoch = k
                break
        record = dict(row)
        record["epoch_index"] = epoch
        if epoch is None:
            if "R_INTERVAL_BOUNDS" in off:
                nearest = min(range(1, data["epochs"] + 1),
                              key=lambda k: (abs(row["acq_time_s"] - grid[k - 1]), k))
                record["epoch_index"] = nearest
                attributed.append(record)
                continue
            record["drop_reason"] = "DR_OUTSIDE_INTERVAL"
            dropped.append(record)
            continue
        if row["session_id"] in withdrawn and "R_WITHDRAWN_SESSIONS" not in off:
            record["drop_reason"] = "DR_SESSION_WITHDRAWN"
            dropped.append(record)
            continue
        link = links.get(row["link_id"])
        if link is None:
            record["drop_reason"] = "DR_LINK_UNREGISTERED"
            dropped.append(record)
            continue
        if link["node_a"] == link["node_b"]:
            record["drop_reason"] = "DR_SELF_LOOP"
            dropped.append(record)
            continue
        attributed.append(record)

    clusters: dict = {}
    for record in attributed:
        clusters.setdefault((record["link_id"], record["epoch_index"]), []).append(record)

    canonical = {}
    for key in sorted(clusters):
        rows = clusters[key]
        instant = grid[key[1] - 1]
        if "R_LOCK_STATE" in off:
            eligible = list(rows)
        else:
            eligible = [r for r in rows if r["lock_state"] == "LOCK_HELD"]
        if not eligible:
            for record in rows:
                marked = dict(record)
                marked["drop_reason"] = "DR_NO_LOCKED_ATTEMPT"
                dropped.append(marked)
            continue
        top = max(r["attempt_no"] for r in eligible)
        best = [r for r in eligible if r["attempt_no"] == top]
        if "R_NEAREST_WINS" in off:
            pick = min(best, key=lambda r: (r["acq_time_s"], r["session_id"]))
        else:
            pick = min(best, key=lambda r: (abs(r["acq_time_s"] - instant),
                                            r["acq_time_s"], r["session_id"]))
        canonical[key] = dict(pick)
        canonical[key]["cluster_rows"] = len(rows)
        canonical[key]["eligible_rows"] = len(eligible)
    return {"canonical": canonical, "dropped": dropped, "grid": grid}


def stage_t02_calibration(data: dict, t01: dict, off=frozenset()) -> dict:
    """T02 delay calibration application."""
    out = {}
    for key in sorted(t01["canonical"]):
        record = t01["canonical"][key]
        reports = data["reports"].get(record["link_id"], [])
        report = applicable_report(reports, record["acq_time_s"], off)
        correction = calibration_ps(report, off)
        out[key] = {
            "report_id": report["report_id"] if report else "REPORT_NONE",
            "revision": report["revision"] if report else 0,
            "status": report["status"] if report else "CAL_ABSENT",
            "effective_epoch_s": report["effective_epoch_s"] if report else 0,
            "correction_ps": correction,
            "corrected_ps": record["raw_offset_ps"] - correction,
        }
    return out


def stage_t03_sense(data: dict, t01: dict, t02: dict, off=frozenset()) -> dict:
    """T03 measurement sense normalisation."""
    out = {}
    for key in sorted(t01["canonical"]):
        link = data["links"][key[0]]
        sense = TECHNIQUE_SENSE[link["technique"]]
        value = t02[key]["corrected_ps"]
        if "R_SENSE_NORMALISE" in off:
            signed_value = value
        else:
            signed_value = value if sense == "SENSE_A_MINUS_B" else -value
        out[key] = {
            "sense": sense,
            "difference_ps": signed_value,
        }
    return out


def stage_t04_graph(data: dict, off=frozenset()) -> dict:
    """T04 link graph, component split, cycle break and spanning tree."""
    links = data["links"]
    nodes = data["nodes"]
    usable = []
    for link_id in sorted(links):
        link = links[link_id]
        if link["node_a"] == link["node_b"]:
            continue
        if link["node_a"] not in nodes or link["node_b"] not in nodes:
            continue
        usable.append(link)

    adjacency: dict = {node: [] for node in sorted(nodes)}
    for link in usable:
        adjacency[link["node_a"]].append(link)
        adjacency[link["node_b"]].append(link)

    seen = set()
    components = []
    for node in sorted(nodes):
        if node in seen:
            continue
        stack = [node]
        member = set()
        while stack:
            current = stack.pop()
            if current in member:
                continue
            member.add(current)
            for link in adjacency[current]:
                other = link["node_b"] if link["node_a"] == current else link["node_a"]
                if other not in member:
                    stack.append(other)
        seen |= member
        components.append(sorted(member))
    components.sort(key=lambda members: members[0])

    hub = data["config"]["hub_node"]
    result = []
    for index, members in enumerate(components, start=1):
        member_set = set(members)
        if hub in member_set:
            role = "ROLE_ANCHORED"
            root = hub
        else:
            role = "ROLE_UNANCHORED"
            if "R_UNANCHORED_ROOT" in off:
                root = members[-1]
            else:
                root = members[0]
        inside = [link for link in usable
                  if link["node_a"] in member_set and link["node_b"] in member_set]
        tree = []
        reached = {root}
        parent = {}
        path_cost = {root: 0}

        def admission_cost(link):
            """What the unreached end would carry back to the root.

            The uncertainty a node carries is the uncertainty of its whole path
            to the root, which is what T12 publishes as its path terms, so the
            admission works on the accumulated figure and not on the edge in
            front of it. The two readings admit different links."""
            anchor = link["node_a"] if link["node_a"] in reached else link["node_b"]
            if "R_TREE_PATH_COST" in off:
                return link["published_uncertainty_ps"]
            return path_cost[anchor] + link["published_uncertainty_ps"]

        while True:
            candidates = []
            for link in inside:
                a_in = link["node_a"] in reached
                b_in = link["node_b"] in reached
                if a_in == b_in:
                    continue
                candidates.append(link)
            if not candidates:
                break
            if "R_TREE_UNCERTAINTY" in off:
                pick = min(candidates, key=lambda l: l["link_id"])
            elif "R_TREE_TECHNIQUE_TIE" in off:
                pick = min(candidates, key=lambda l: (admission_cost(l), l["link_id"]))
            else:
                pick = min(candidates, key=lambda l: (admission_cost(l),
                                                      TECHNIQUE_RANK[l["technique"]],
                                                      l["link_id"]))
            if pick["node_a"] in reached:
                parent_node, child_node = pick["node_a"], pick["node_b"]
            else:
                parent_node, child_node = pick["node_b"], pick["node_a"]
            reached.add(child_node)
            path_cost[child_node] = (path_cost[parent_node]
                                     + pick["published_uncertainty_ps"])
            parent[child_node] = (parent_node, pick)
            tree.append({
                "link_id": pick["link_id"],
                "parent_node": parent_node,
                "child_node": child_node,
                "technique": pick["technique"],
                "published_uncertainty_ps": pick["published_uncertainty_ps"],
            })
        tree_ids = {edge["link_id"] for edge in tree}
        result.append({
            "component_id": "cmp_%02d" % index,
            "role": role,
            "root_node": root,
            "member_nodes": members,
            "tree_edges": tree,
            "excluded_link_ids": sorted(l["link_id"] for l in inside
                                        if l["link_id"] not in tree_ids),
            "parent": parent,
        })
    return {"components": result, "usable": usable}


def _node_path(components: list, node: str) -> list:
    for component in components:
        if node not in component["member_nodes"]:
            continue
        path = []
        current = node
        while current != component["root_node"]:
            parent_node, link = component["parent"][current]
            path.append((parent_node, current, link))
            current = parent_node
        return list(reversed(path))
    return []


def _component_of(components: list, node: str) -> dict:
    for component in components:
        if node in component["member_nodes"]:
            return component
    raise KeyError(node)


def stage_t05_offsets(data: dict, t01: dict, t03: dict, graph: dict, off=frozenset()) -> dict:
    """T05 epoch attribution carried into node offsets, with dead time."""
    components = graph["components"]
    node_offsets: dict = {}
    dead: list = []

    filled: dict = {}
    if "R_NO_INTERPOLATION" in off:
        # The reverted reading of the dead time rule: a link with no reading
        # at an epoch keeps the nearest reading it does have.
        by_link: dict = {}
        for link_id, epoch in t03:
            by_link.setdefault(link_id, {})[epoch] = t03[(link_id, epoch)]["difference_ps"]
        for link_id in sorted(by_link):
            known = sorted(by_link[link_id])
            for epoch in range(1, data["epochs"] + 1):
                if epoch in by_link[link_id]:
                    filled[(link_id, epoch)] = by_link[link_id][epoch]
                elif known:
                    near = min(known, key=lambda e: (abs(e - epoch), e))
                    filled[(link_id, epoch)] = by_link[link_id][near]

    for node in sorted(data["nodes"]):
        path = _node_path(components, node)
        for epoch in range(1, data["epochs"] + 1):
            total = 0
            missing = None
            for parent_node, child_node, link in path:
                key = (link["link_id"], epoch)
                if key in t03:
                    value = t03[key]["difference_ps"]
                elif key in filled:
                    value = filled[key]
                else:
                    missing = link["link_id"]
                    break
                if link["node_a"] == parent_node:
                    total += value
                else:
                    total -= value
                _ = child_node
            if missing is not None:
                node_offsets[(node, epoch)] = None
                dead.append({"epoch_index": epoch, "scope": "SCOPE_NODE",
                             "subject": node, "cause": missing})
                continue
            node_offsets[(node, epoch)] = -total
    for component in components:
        for edge in component["tree_edges"]:
            for epoch in range(1, data["epochs"] + 1):
                if (edge["link_id"], epoch) not in t03:
                    dead.append({"epoch_index": epoch, "scope": "SCOPE_LINK",
                                 "subject": edge["link_id"], "cause": "CAUSE_NO_READING"})
    return {"node_offsets": node_offsets, "dead": dead}


def stage_t06_series(data: dict, graph: dict, offsets: dict, off=frozenset()) -> dict:
    """T06 oscillator deviation series against the network reference."""
    components = graph["components"]
    nodes = data["nodes"]
    series: dict = {}
    dead: list = []
    for osc in data["oscillators"]:
        node = nodes.get(osc["node_id"])
        if node is None:
            continue
        component = _component_of(components, osc["node_id"])
        is_reference = node["reference_oscillator"] == osc["osc_id"]
        for epoch in range(1, data["epochs"] + 1):
            base = offsets["node_offsets"].get((osc["node_id"], epoch))
            if base is None:
                series[(osc["osc_id"], epoch)] = (None, "SER_ABSENT")
                continue
            if is_reference:
                value = base
            else:
                local = data["local"].get((osc["osc_id"], epoch))
                if local is None or local["monitor_flag"] != "MON_VALID":
                    series[(osc["osc_id"], epoch)] = (None, "SER_ABSENT")
                    dead.append({"epoch_index": epoch, "scope": "SCOPE_OSCILLATOR",
                                 "subject": osc["osc_id"], "cause": "CAUSE_NO_MONITOR"})
                    continue
                value = base + local["local_offset_ps"]
            flag = "SER_UNANCHORED" if component["role"] == "ROLE_UNANCHORED" else "SER_MEASURED"
            series[(osc["osc_id"], epoch)] = (value, flag)
    _ = off
    return {"series": series, "dead": dead}


def stage_t07_prediction(data: dict, graph: dict, off=frozenset()) -> dict:
    """T07 frequency prediction from the previous interval."""
    window = data["policies"]["history_window_epochs"]
    valid_flag = data["policies"]["valid_archive_flag"]
    minimum = data["memo"]["history_minimum"]
    first_epoch = data["archive_epochs"] - window + 1
    components = graph["components"]
    out = {}
    for osc in data["oscillators"]:
        entry = {
            "osc_id": osc["osc_id"],
            "node_id": osc["node_id"],
            "osc_class": osc["osc_class"],
            "window_first": first_epoch,
            "window_last": data["archive_epochs"],
            "valid_count": 0,
            "anchor_epoch": 0,
            "anchor_deviation_ps": 0,
            "frequency": Fraction(0),
            "included": False,
            "exclusion_reason": "",
            "residuals": [],
        }
        rows = data["archive"].get(osc["osc_id"], {})
        points = []
        for epoch in range(first_epoch, data["archive_epochs"] + 1):
            row = rows.get(epoch)
            if row is None or row["quality_flag"] != valid_flag:
                continue
            points.append((epoch, row["deviation_ps"]))
        entry["valid_count"] = len(points)
        if osc["status"] == "OS_DECOMMISSIONED":
            entry["exclusion_reason"] = "EX_DECOMMISSIONED"
            out[osc["osc_id"]] = entry
            continue
        if not rows:
            entry["exclusion_reason"] = "EX_NO_ARCHIVE"
            out[osc["osc_id"]] = entry
            continue
        if "R_HISTORY_MINIMUM" not in off and len(points) < minimum:
            entry["exclusion_reason"] = "EX_SHORT_HISTORY"
            out[osc["osc_id"]] = entry
            continue
        if len(points) < 2:
            entry["exclusion_reason"] = "EX_SHORT_HISTORY"
            out[osc["osc_id"]] = entry
            continue
        node = data["nodes"].get(osc["node_id"])
        if node is not None:
            component = _component_of(components, osc["node_id"])
            if component["role"] == "ROLE_UNANCHORED" and "R_UNANCHORED_EXCLUDE" not in off:
                entry["exclusion_reason"] = "EX_UNANCHORED_NODE"
                out[osc["osc_id"]] = entry
                continue
        first, last = points[0], points[-1]
        if "R_TWO_POINT_SLOPE" in off:
            count = len(points)
            mean_x = Fraction(sum(p[0] for p in points), count)
            mean_y = Fraction(sum(p[1] for p in points), count)
            num = sum((Fraction(p[0]) - mean_x) * (Fraction(p[1]) - mean_y) for p in points)
            den = sum((Fraction(p[0]) - mean_x) ** 2 for p in points)
            slope_ps = Fraction(0) if den == 0 else num / den
            frequency = slope_atto(slope_ps, 1)
        else:
            frequency = slope_atto(Fraction(last[1] - first[1]), last[0] - first[0])
        entry["anchor_epoch"] = last[0]
        entry["anchor_deviation_ps"] = last[1]
        entry["frequency"] = frequency
        entry["included"] = True
        residuals = []
        for epoch, value in points:
            predicted = Fraction(last[1]) + phase_ps(frequency, epoch - last[0])
            residuals.append(Fraction(value) - predicted)
        entry["residuals"] = residuals
        out[osc["osc_id"]] = entry
    return out


def stage_t08_weights(data: dict, prediction: dict, off=frozenset()) -> dict:
    """T08 residual dispersion and the raw weight of every oscillator."""
    scale = data["policies"]["weight_scale"]
    ceilings = data["workbook"]["class_ceiling"]
    out = {}
    for osc_id in sorted(prediction):
        entry = prediction[osc_id]
        if not entry["included"]:
            continue
        exact = mean_abs(entry["residuals"])
        published = half_even(exact)
        used = exact if "R_PUBLISHED_DISPERSION" in off else Fraction(published)
        if used == 0:
            if "R_ZERO_DISPERSION_CEILING" in off:
                continue
            weight = Fraction(ceilings[entry["osc_class"]])
            source = "WS_CLASS_CEILING"
        else:
            weight = Fraction(scale) / used
            source = "WS_DISPERSION"
        out[osc_id] = {
            "osc_id": osc_id,
            "node_id": entry["node_id"],
            "osc_class": entry["osc_class"],
            "valid_count": entry["valid_count"],
            "dispersion_ps": published,
            "raw_weight": weight,
            "weight_source": source,
        }
    return out


def quantise(value, places: int) -> Fraction:
    """Round an exact rational onto the published weight grid."""
    scale = 10 ** places
    return Fraction(half_even(Fraction(value) * scale), scale)


def _close_placement(stepped: dict, placed: dict, receivers: list,
                     carries: dict, off=frozenset()) -> dict:
    """Close the grid placement of one capping pass onto a single holder.

    Placing each weight on the grid on its own moves the total, because half
    to even sends some weights up and some down and the two do not cancel. The
    desk does not publish a weight vector whose total has drifted from the
    total the pass started with, so the whole of the difference is handed to
    one receiving holder. Both totals are whole numbers of grid units, so the
    residue is one too and the vector stays on the grid.

    The holder is not the same one every pass. Closing the residue onto the
    greatest receiver every time walks that one holder's published weight away
    from the vector the passes actually produced, so the desk hands the carry
    to the receiving holder that has carried it the fewest times so far in
    this interval, a tie going to the greatest weight after placement and then
    to the smallest oscillator identifier. The count runs across every pass of
    all three phases, so which holder closes a pass depends on what the passes
    before it did, and the vector cannot be recovered from the pass alone.
    """
    out = dict(placed)
    if "R_PLACEMENT_RESIDUE" in off or not receivers:
        return out
    residue = sum(stepped.values()) - sum(out.values())
    if residue == 0:
        return out
    if "R_RESIDUE_ROTATION" in off:
        carrier = sorted(receivers, key=lambda key: (-out[key], key))[0]
    else:
        carrier = sorted(
            receivers, key=lambda key: (carries.get(key, 0), -out[key], key))[0]
    out[carrier] = out[carrier] + residue
    carries[carrier] = carries.get(carrier, 0) + 1
    return out


def _cap_pass(weights: dict, cap: Fraction, lam: Fraction, places: int,
              carries: dict, off=frozenset()):
    """One damped, quantised pass of the capacity binding.

    The pass first works out where a full step would put the vector: every
    oscillator above the cap sits exactly on it, and the excess they give up
    goes to the oscillators still below the cap in proportion to the weight
    they already hold, so a full step preserves the mass.

    The desk does not take the full step. It moves the vector a fraction lam
    of the way toward that target, which is what keeps one noisy interval from
    throwing the whole weight vector, and then quantises the result onto the
    published grid. The next pass starts from the quantised vector, so the
    passes are not independent and the terminal vector is the k-th damped
    iterate rather than the fixed point of the map.
    """
    offenders = sorted(key for key in weights if weights[key] > cap)
    if not offenders:
        return dict(weights), offenders, Fraction(0), Fraction(0), "SW_SETTLED"
    holders = sorted(key for key in weights if weights[key] <= cap)
    if not holders:
        return dict(weights), offenders, Fraction(0), Fraction(0), "SW_CAP_UNSATISFIABLE"

    target = dict(weights)
    excess = Fraction(0)
    for key in offenders:
        excess += weights[key] - cap
        target[key] = cap
    base = sum(weights[key] for key in holders)
    if "R_CAP_REDISTRIBUTE" in off:
        excess = Fraction(0)
    if base == 0:
        share = Fraction(excess, len(holders))
        for key in holders:
            target[key] = weights[key] + share
    else:
        for key in holders:
            target[key] = weights[key] + excess * weights[key] / base

    stepped = {}
    for key in weights:
        if "R_DAMPED_STEP" in off:
            stepped[key] = target[key]
        else:
            stepped[key] = weights[key] + lam * (target[key] - weights[key])
    if "R_PASS_QUANTISATION" in off:
        out = dict(stepped)
    else:
        out = {key: quantise(value, places) for key, value in stepped.items()}
        out = _close_placement(stepped, out, holders, carries, off)
    residual = sum(abs(out[key] - weights[key]) for key in sorted(weights))
    return out, offenders, excess, residual, "SW_RUNNING"


def _cap_sweep(weights: dict, cap: Fraction, budget: int, lam: Fraction,
               places: int, phase: str, carries: dict, off=frozenset()):
    """Run the damped pass up to the budget the memo publishes."""
    current = dict(weights)
    trace = []
    outcome = "SW_SETTLED"
    sweeps = 0
    residual = Fraction(0)
    limit = budget
    if "R_SWEEP_BUDGET" in off:
        limit = 256
    while True:
        offenders = sorted(key for key in current if current[key] > cap)
        if not offenders:
            outcome = "SW_SETTLED"
            break
        if not [key for key in current if current[key] <= cap]:
            outcome = "SW_CAP_UNSATISFIABLE"
            break
        if sweeps >= limit:
            outcome = "SW_BUDGET_EXHAUSTED"
            break
        sweeps += 1
        current, offenders, excess, residual, state = _cap_pass(
            current, cap, lam, places, carries, off)
        if state == "SW_CAP_UNSATISFIABLE":
            outcome = state
            break
        trace.append({
            "phase": phase,
            "sweep": sweeps,
            "offenders": offenders,
            "excess_ratio": ratio(excess),
            "holders": len(current) - len(offenders),
            "residual_ratio": ratio(residual),
        })
    return current, trace, outcome, sweeps, residual


def stage_t09_capping(data: dict, raw: dict, off=frozenset()) -> dict:
    """T09 the two caps, in the order the capping policy states."""
    memo = data["memo"]
    book = data["workbook"]
    policies = data["policies"]
    lam = Fraction(policies["damping_num"], policies["damping_den"])
    places = policies["weight_places"]
    # The residue carry count is opened once for the interval and runs across
    # every pass of all three phases.
    carries: dict = {}
    weights = {k: quantise(raw[k]["raw_weight"], places) for k in raw}
    if READING_CAP_TOTAL_RAW in off:
        total = sum((raw[k]["raw_weight"] for k in raw), Fraction(0))
    else:
        total = sum(weights.values()) if weights else Fraction(0)
    osc_cap = Fraction(memo["osc_cap_num"], memo["osc_cap_den"]) * total
    node_cap = Fraction(book["node_cap_num"], book["node_cap_den"]) * total

    def node_pass(current):
        by_node: dict = {}
        for key in sorted(current):
            by_node.setdefault(raw[key]["node_id"], []).append(key)
        offending = sorted(n for n in by_node
                           if sum(current[k] for k in by_node[n]) > node_cap)
        if not offending:
            return dict(current), [], "SW_SETTLED"
        working = dict(current)
        excess = Fraction(0)
        offending_members = set()
        for node in offending:
            members = by_node[node]
            offending_members |= set(members)
            held = sum(working[k] for k in members)
            excess += held - node_cap
            for key in members:
                working[key] = working[key] * node_cap / held
        receivers = sorted(k for k in working if k not in offending_members)
        if not receivers:
            return dict(current), [], "SW_CAP_UNSATISFIABLE"
        base = sum(working[k] for k in receivers)
        if "R_CAP_REDISTRIBUTE" in off:
            excess = Fraction(0)
        if base == 0:
            share = Fraction(excess, len(receivers))
            for key in receivers:
                working[key] = working[key] + share
        else:
            for key in receivers:
                working[key] = working[key] + excess * working[key] / base
        if "R_PASS_QUANTISATION" not in off:
            placed = {key: quantise(value, places) for key, value in working.items()}
            working = _close_placement(working, placed, receivers, carries, off)
        moved = sum(abs(working[key] - current[key]) for key in sorted(current))
        note = [{"phase": "PH_NODE_CAP", "sweep": 1, "offenders": offending,
                 "excess_ratio": ratio(excess), "holders": len(receivers),
                 "residual_ratio": ratio(moved)}]
        return working, note, "SW_SETTLED"

    final_outcome = "SW_SETTLED"
    residual = Fraction(0)
    if "R_CAP_ORDER" in off:
        after_node, node_trace, node_outcome = node_pass(weights)
        after_osc, osc_trace, osc_outcome, sweeps, residual = _cap_sweep(
            after_node, osc_cap, memo["sweep_budget"], lam, places, "PH_OSC_CAP",
            carries, off)
        settled = after_osc
        final_trace = []
    else:
        after_osc, osc_trace, osc_outcome, sweeps, residual = _cap_sweep(
            weights, osc_cap, memo["sweep_budget"], lam, places, "PH_OSC_CAP",
            carries, off)
        after_node, node_trace, node_outcome = node_pass(after_osc)
        if "R_FINAL_OSC_SWEEP" in off:
            settled = after_node
            final_trace = []
        else:
            settled, final_trace, final_outcome, _, residual = _cap_sweep(
                after_node, osc_cap, 1, lam, places, "PH_FINAL_SWEEP",
                carries, off)
    return {
        "final_trace": final_trace,
        "final_outcome": final_outcome,
        "terminal_residual": residual,
        "damping_num": policies["damping_num"],
        "damping_den": policies["damping_den"],
        "weight_places": places,
        "total_weight": total,
        "osc_cap": osc_cap,
        "node_cap": node_cap,
        "after_osc": after_osc,
        "after_node": after_node,
        "final": settled,
        "osc_trace": osc_trace,
        "node_trace": node_trace,
        "osc_outcome": osc_outcome,
        "node_outcome": node_outcome,
        "sweeps": sweeps,
    }


def stage_t10_ensemble(data: dict, series: dict, prediction: dict, capping: dict,
                       off=frozenset()) -> dict:
    """T10 the free ensemble scale."""
    weights = capping["final"]
    out = {}
    for epoch in range(1, data["epochs"] + 1):
        numerator = Fraction(0)
        denominator = Fraction(0)
        members = []
        for osc_id in sorted(weights):
            entry = prediction[osc_id]
            value, flag = series["series"].get((osc_id, epoch), (None, "SER_ABSENT"))
            if value is None:
                continue
            predicted = Fraction(entry["anchor_deviation_ps"]) + phase_ps(
                entry["frequency"], data["archive_epochs"] + epoch - entry["anchor_epoch"])
            residual = Fraction(value) - predicted
            if "R_ROUND_AT_WRITE" in off:
                residual = Fraction(half_even(residual))
            numerator += weights[osc_id] * residual
            denominator += weights[osc_id]
            members.append(osc_id)
        if "R_EPOCH_DENOMINATOR" in off:
            denominator = sum(weights.values()) if weights else Fraction(0)
        if not members or denominator == 0:
            out[epoch] = {"state": "EP_ENSEMBLE_VOID", "value": None,
                          "members": [], "denominator": Fraction(0)}
        else:
            out[epoch] = {"state": "EP_POPULATED", "value": numerator / denominator,
                          "members": members, "denominator": denominator}
    return out


def stage_t11_steering(data: dict, ensemble: dict, off=frozenset()) -> dict:
    """T11 steering onto the primary realisation."""
    policies = data["policies"]
    decision = policies["steer_decision_epoch"]
    horizon = policies["steer_horizon_epochs"]
    grid_atto = policies["steer_grid_atto"]
    realisation = data["realisation"]
    entry = ensemble.get(decision)
    if entry is None or entry["state"] != "EP_POPULATED" or decision not in realisation:
        return {"decision_epoch": decision, "horizon_epochs": horizon,
                "grid_atto": grid_atto, "departure": Fraction(0),
                "raw_step": Fraction(0), "step_atto": 0,
                "outcome": "ST_NO_REALISATION"}
    departure = entry["value"] - Fraction(realisation[decision])
    raw_step = slope_atto(-departure, horizon)
    if "R_STEER_TRUNCATE" in off:
        steps = half_even(raw_step / grid_atto)
    else:
        steps = trunc_zero(raw_step / grid_atto)
    step_atto = steps * grid_atto
    outcome = "ST_APPLIED" if step_atto != 0 else "ST_TRUNCATED_TO_ZERO"
    return {"decision_epoch": decision, "horizon_epochs": horizon,
            "grid_atto": grid_atto, "departure": departure,
            "raw_step": raw_step, "step_atto": step_atto, "outcome": outcome}


def stage_t11b_steered(ensemble: dict, plan: dict, epochs: int, off=frozenset()) -> dict:
    """The steered scale. The correction starts at the epoch after the
    decision epoch and grows by one grid step each epoch."""
    decision = plan["decision_epoch"]
    step = plan["step_atto"]
    out = {}
    for epoch in range(1, epochs + 1):
        entry = ensemble[epoch]
        if "R_STEER_NEXT_EPOCH" in off:
            elapsed = max(0, epoch - decision + 1)
        else:
            elapsed = max(0, epoch - decision)
        correction = phase_ps(Fraction(step), elapsed)
        if entry["state"] != "EP_POPULATED":
            out[epoch] = {"state": entry["state"], "free": None,
                          "correction": correction, "steered": None}
        else:
            out[epoch] = {"state": entry["state"], "free": entry["value"],
                          "correction": correction,
                          "steered": entry["value"] + correction}
    return out


def stage_t12_dissemination(data: dict, graph: dict, offsets: dict, steered: dict,
                            off=frozenset()) -> dict:
    """T12 node offsets and the uncertainty budget."""
    components = graph["components"]
    nodes = data["nodes"]
    parts = data["workbook"]["components"]
    rows = []
    budget = []
    for node_id in sorted(nodes):
        node = nodes[node_id]
        component = _component_of(components, node_id)
        path = _node_path(components, node_id)
        available = 0
        total = Fraction(0)
        for epoch in range(1, data["epochs"] + 1):
            base = offsets["node_offsets"].get((node_id, epoch))
            entry = steered[epoch]
            if base is None or entry["steered"] is None:
                rows.append({"node_id": node_id, "epoch_index": epoch,
                             "offset": None, "flag": "OFF_ABSENT"})
                continue
            value = Fraction(base) - entry["steered"]
            available += 1
            total += value
            rows.append({"node_id": node_id, "epoch_index": epoch,
                         "offset": value, "flag": "OFF_PUBLISHED"})
        terms = list(parts.get(node["reference_oscillator"], []))
        terms.append(node["declared_uncertainty_ps"])
        for _, _, link in path:
            terms.append(link["published_uncertainty_ps"])
        combined = sum(term * term for term in terms)
        linear = sum(terms)
        if "R_UNCERTAINTY_LINEAR" in off:
            linear = combined
        if component["role"] == "ROLE_UNANCHORED":
            status = "DS_WITHHELD_UNANCHORED"
        elif available == 0:
            status = "DS_WITHHELD_NO_DATA"
        else:
            status = "DS_PUBLISHED"
        budget.append({
            "node_id": node_id,
            "component_id": component["component_id"],
            "role": component["role"],
            "path_length": len(path),
            "term_count": len(terms),
            "u_combined_ps2": combined,
            "u_linear_ps": linear,
            "epochs_available": available,
            "offset_mean": (total / available) if available else Fraction(0),
            "status": status,
        })
    return {"rows": rows, "budget": budget}


# --------------------------------------------------------------------------
# T13 rendering
#
# Rounding happens here and nowhere earlier. Every value above this line is
# an exact rational.
# --------------------------------------------------------------------------
def _delim(header: list, rows: list, sep: str) -> bytes:
    out = [sep.join(header)]
    for row in rows:
        out.append(sep.join(str(row[column]) for column in header))
    return ("\n".join(out) + "\n").encode("utf-8")


def _jsonl(records: list) -> bytes:
    if not records:
        return b""
    body = "\n".join(compact_json(record) for record in records)
    return (body + "\n").encode("utf-8")


def _json(obj) -> bytes:
    return canonical_json(obj).encode("utf-8")


def _text(lines: list) -> bytes:
    return ("\n".join(lines) + "\n").encode("utf-8")


def render(data: dict, state: dict, off=frozenset()) -> dict:
    config = data["config"]
    nodes = data["nodes"]
    links = data["links"]
    t01 = state["t01"]
    t02 = state["t02"]
    t03 = state["t03"]
    graph = state["graph"]
    offsets = state["offsets"]
    series = state["series"]
    prediction = state["prediction"]
    raw = state["raw"]
    capping = state["capping"]
    ensemble = state["ensemble"]
    plan = state["plan"]
    steered = state["steered"]
    dissemination = state["dissemination"]
    blobs: dict = {}

    # ---- reading ledger ---------------------------------------------------
    ledger_rows = []
    for key in sorted(t01["canonical"]):
        record = t01["canonical"][key]
        cal = t02[key]
        sense = t03[key]
        ledger_rows.append({
            "link_id": key[0],
            "epoch_index": key[1],
            "session_id": record["session_id"],
            "receiver_id": record["receiver_id"],
            "attempt_no": record["attempt_no"],
            "acq_time_s": record["acq_time_s"],
            "raw_offset_ps": record["raw_offset_ps"],
            "report_id": cal["report_id"],
            "correction_ps": signed(cal["correction_ps"]),
            "corrected_ps": signed(cal["corrected_ps"]),
            "sense": sense["sense"],
            "difference_ps": signed(sense["difference_ps"]),
            "cluster_rows": record["cluster_rows"],
        })
    blobs["reading_ledger.csv"] = _delim(
        ["link_id", "epoch_index", "session_id", "receiver_id", "attempt_no",
         "acq_time_s", "raw_offset_ps", "report_id", "correction_ps",
         "corrected_ps", "sense", "difference_ps", "cluster_rows"],
        ledger_rows, ",")

    # ---- withdrawal ledger ------------------------------------------------
    drop_rows = []
    for record in t01["dropped"]:
        drop_rows.append({
            "drop_reason": record["drop_reason"],
            "link_id": record["link_id"],
            "epoch_index": "NONE" if record["epoch_index"] is None else record["epoch_index"],
            "session_id": record["session_id"],
            "attempt_no": record["attempt_no"],
            "lock_state": record["lock_state"],
        })
    if "R_ROW_ORDER" in off:
        drop_rows.sort(key=lambda r: (r["link_id"], str(r["epoch_index"]),
                                      r["session_id"], r["attempt_no"]))
    else:
        drop_rows.sort(key=lambda r: (r["drop_reason"], r["link_id"],
                                      str(r["epoch_index"]), r["session_id"],
                                      r["attempt_no"]))
    blobs["withdrawal_ledger.tsv"] = _delim(
        ["drop_reason", "link_id", "epoch_index", "session_id", "attempt_no",
         "lock_state"], drop_rows, "\t")

    # ---- calibration selection -------------------------------------------
    cal_rows = []
    for key in sorted(t02):
        cal = t02[key]
        cal_rows.append({
            "link_id": key[0],
            "epoch_index": key[1],
            "report_id": cal["report_id"],
            "revision": cal["revision"],
            "status": cal["status"],
            "effective_epoch_s": cal["effective_epoch_s"],
            "delay_delta_ps": signed(cal["correction_ps"]),
        })
    blobs["calibration_selection.csv"] = _delim(
        ["link_id", "epoch_index", "report_id", "revision", "status",
         "effective_epoch_s", "delay_delta_ps"], cal_rows, ",")

    # ---- link differences -------------------------------------------------
    diff_rows = []
    for key in sorted(t03, key=lambda k: (k[1], k[0])):
        link = links[key[0]]
        diff_rows.append({
            "epoch_index": key[1],
            "link_id": key[0],
            "node_a": link["node_a"],
            "node_b": link["node_b"],
            "technique": link["technique"],
            "sense": t03[key]["sense"],
            "difference_ps": signed(t03[key]["difference_ps"]),
        })
    if "R_ROW_ORDER" in off:
        diff_rows.sort(key=lambda r: (r["link_id"], r["epoch_index"]))
    blobs["link_differences.psv"] = _delim(
        ["epoch_index", "link_id", "node_a", "node_b", "technique", "sense",
         "difference_ps"], diff_rows, "|")

    # ---- link graph -------------------------------------------------------
    graph_doc = {
        "hub_node": config["hub_node"],
        "component_count": len(graph["components"]),
        "components": [],
    }
    for component in graph["components"]:
        graph_doc["components"].append({
            "component_id": component["component_id"],
            "role": component["role"],
            "root_node": component["root_node"],
            "member_nodes": component["member_nodes"],
            "tree_edges": [{
                "link_id": edge["link_id"],
                "parent_node": edge["parent_node"],
                "child_node": edge["child_node"],
                "technique": edge["technique"],
                "published_uncertainty_ps": edge["published_uncertainty_ps"],
            } for edge in component["tree_edges"]],
            "excluded_link_ids": component["excluded_link_ids"],
        })
    blobs["link_graph.json"] = _json(graph_doc)

    # ---- epoch grid and dead time ----------------------------------------
    grid = t01["grid"]
    tree_link_ids = set()
    for component in graph["components"]:
        for edge in component["tree_edges"]:
            tree_link_ids.add(edge["link_id"])
    grid_rows = []
    for epoch in range(1, data["epochs"] + 1):
        canonical_here = sorted(k[0] for k in t01["canonical"] if k[1] == epoch)
        present = sorted(set(canonical_here) & tree_link_ids)
        grid_rows.append({
            "epoch_index": epoch,
            "epoch_instant_s": grid[epoch - 1],
            "canonical_readings": len(canonical_here),
            "tree_links_present": len(present),
            "contributing_oscillators": len(ensemble[epoch]["members"]),
            "epoch_state": ensemble[epoch]["state"],
        })
    blobs["epoch_grid.csv"] = _delim(
        ["epoch_index", "epoch_instant_s", "canonical_readings",
         "tree_links_present", "contributing_oscillators", "epoch_state"],
        grid_rows, ",")

    dead = offsets["dead"] + series["dead"]
    dead_records = sorted(
        ({"epoch_index": item["epoch_index"], "scope": item["scope"],
          "subject": item["subject"], "cause": item["cause"]} for item in dead),
        key=lambda r: (r["epoch_index"], r["scope"], r["subject"], r["cause"]))
    blobs["deadtime_ledger.jsonl"] = _jsonl(dead_records)

    # ---- oscillator series ------------------------------------------------
    series_rows = []
    for osc in data["oscillators"]:
        for epoch in range(1, data["epochs"] + 1):
            value, flag = series["series"].get((osc["osc_id"], epoch), (None, "SER_ABSENT"))
            series_rows.append({
                "osc_id": osc["osc_id"],
                "node_id": osc["node_id"],
                "epoch_index": epoch,
                "deviation_ps": "" if value is None else signed(value),
                "series_flag": flag,
            })
    blobs["oscillator_series.csv"] = _delim(
        ["osc_id", "node_id", "epoch_index", "deviation_ps", "series_flag"],
        series_rows, ",")

    # ---- prediction book --------------------------------------------------
    prediction_doc = {"window_epochs": data["policies"]["history_window_epochs"],
                      "history_minimum": data["memo"]["history_minimum"],
                      "oscillators": []}
    for osc_id in sorted(prediction):
        entry = prediction[osc_id]
        prediction_doc["oscillators"].append({
            "osc_id": osc_id,
            "node_id": entry["node_id"],
            "osc_class": entry["osc_class"],
            "window_first": entry["window_first"],
            "window_last": entry["window_last"],
            "valid_count": entry["valid_count"],
            "anchor_epoch": entry["anchor_epoch"],
            "anchor_deviation_ps": int(entry["anchor_deviation_ps"]),
            "frequency_atto": half_even(entry["frequency"]),
            "included": entry["included"],
            "exclusion_reason": entry["exclusion_reason"],
        })
    blobs["prediction_book.json"] = _json(prediction_doc)

    # ---- dispersion table -------------------------------------------------
    disp_rows = []
    for osc_id in sorted(raw):
        entry = raw[osc_id]
        disp_rows.append({
            "osc_id": osc_id,
            "node_id": entry["node_id"],
            "osc_class": entry["osc_class"],
            "valid_count": entry["valid_count"],
            "dispersion_ps": entry["dispersion_ps"],
            "weight_source": entry["weight_source"],
            "raw_weight": ratio(entry["raw_weight"]),
        })
    if "R_ROW_ORDER" in off:
        disp_rows.sort(key=lambda r: r["osc_id"])
    else:
        disp_rows.sort(key=lambda r: (r["dispersion_ps"], r["osc_id"]))
    blobs["dispersion_table.csv"] = _delim(
        ["osc_id", "node_id", "osc_class", "valid_count", "dispersion_ps",
         "weight_source", "raw_weight"], disp_rows, ",")

    # ---- weight book ------------------------------------------------------
    node_totals: dict = {}
    for osc_id in sorted(capping["final"]):
        node_id = raw[osc_id]["node_id"]
        node_totals[node_id] = node_totals.get(node_id, Fraction(0)) + capping["final"][osc_id]
    weight_doc = {
        "ensemble_size": len(capping["final"]),
        "total_weight": ratio(capping["total_weight"]),
        "oscillator_cap": ratio(capping["osc_cap"]),
        "node_cap": ratio(capping["node_cap"]),
        "oscillator_cap_outcome": capping["osc_outcome"],
        "node_cap_outcome": capping["node_outcome"],
        "final_sweep_outcome": capping["final_outcome"],
        "sweeps_used": capping["sweeps"],
        "damping_numerator": capping["damping_num"],
        "damping_denominator": capping["damping_den"],
        "weight_places": capping["weight_places"],
        "terminal_residual": ratio(capping["terminal_residual"]),
        "oscillators": [{
            "osc_id": osc_id,
            "node_id": raw[osc_id]["node_id"],
            "raw_weight": ratio(raw[osc_id]["raw_weight"]),
            "after_oscillator_cap": ratio(capping["after_osc"].get(osc_id, Fraction(0))),
            "after_node_cap": ratio(capping["after_node"].get(osc_id, Fraction(0))),
            "final_weight": ratio(capping["final"][osc_id]),
        } for osc_id in sorted(capping["final"])],
        "node_totals": [{"node_id": node_id, "weight": ratio(node_totals[node_id])}
                        for node_id in sorted(node_totals)],
    }
    blobs["weight_book.json"] = _json(weight_doc)
    blobs["weight_sweep_trace.jsonl"] = _jsonl(
        capping["osc_trace"] + capping["node_trace"] + capping["final_trace"])

    # ---- ensemble scale ---------------------------------------------------
    scale_rows = []
    for epoch in range(1, data["epochs"] + 1):
        entry = ensemble[epoch]
        scale_rows.append({
            "epoch_index": epoch,
            "epoch_state": entry["state"],
            "contributing_oscillators": len(entry["members"]),
            "denominator_weight": ratio(entry["denominator"]),
            "free_scale_ps": "" if entry["value"] is None else signed(half_even(entry["value"])),
        })
    blobs["ensemble_scale.csv"] = _delim(
        ["epoch_index", "epoch_state", "contributing_oscillators",
         "denominator_weight", "free_scale_ps"], scale_rows, ",")

    # ---- steering ---------------------------------------------------------
    blobs["steering_plan.json"] = _json({
        "decision_epoch": plan["decision_epoch"],
        "horizon_epochs": plan["horizon_epochs"],
        "grid_atto": plan["grid_atto"],
        "departure_ps": ratio(plan["departure"]),
        "raw_step_atto": ratio(plan["raw_step"]),
        "step_atto": int(plan["step_atto"]),
        "outcome": plan["outcome"],
    })
    steer_rows = []
    for epoch in range(1, data["epochs"] + 1):
        entry = steered[epoch]
        steer_rows.append({
            "epoch_index": epoch,
            "epoch_state": entry["state"],
            "free_scale_ps": "" if entry["free"] is None else signed(half_even(entry["free"])),
            "correction_ps": signed(half_even(entry["correction"])),
            "steered_scale_ps": "" if entry["steered"] is None else signed(half_even(entry["steered"])),
        })
    blobs["steered_scale.csv"] = _delim(
        ["epoch_index", "epoch_state", "free_scale_ps", "correction_ps",
         "steered_scale_ps"], steer_rows, ",")

    # ---- node offsets, budget, dissemination ------------------------------
    offset_rows = []
    for row in sorted(dissemination["rows"], key=lambda r: (r["node_id"], r["epoch_index"])):
        offset_rows.append({
            "node_id": row["node_id"],
            "epoch_index": row["epoch_index"],
            "offset_ps": "" if row["offset"] is None else signed(half_even(row["offset"])),
            "offset_flag": row["flag"],
        })
    blobs["node_offsets.csv"] = _delim(
        ["node_id", "epoch_index", "offset_ps", "offset_flag"], offset_rows, ",")

    budget_rows = []
    for entry in sorted(dissemination["budget"], key=lambda e: e["node_id"]):
        budget_rows.append({
            "node_id": entry["node_id"],
            "component_id": entry["component_id"],
            "role": entry["role"],
            "path_length": entry["path_length"],
            "term_count": entry["term_count"],
            "u_combined_ps2": entry["u_combined_ps2"],
            "u_linear_ps": entry["u_linear_ps"],
        })
    blobs["uncertainty_budget.tsv"] = _delim(
        ["node_id", "component_id", "role", "path_length", "term_count",
         "u_combined_ps2", "u_linear_ps"], budget_rows, "\t")

    diss_rows = []
    for entry in dissemination["budget"]:
        diss_rows.append({
            "node_id": entry["node_id"],
            "status": entry["status"],
            "epochs_available": entry["epochs_available"],
            "offset_mean_ps": ratio(entry["offset_mean"]),
            "u_combined_ps2": entry["u_combined_ps2"],
            "u_linear_ps": entry["u_linear_ps"],
        })
    if "R_ROW_ORDER" in off:
        diss_rows.sort(key=lambda r: r["node_id"])
    else:
        diss_rows.sort(key=lambda r: (-r["epochs_available"], r["node_id"]))
    blobs["dissemination_ledger.psv"] = _delim(
        ["node_id", "status", "epochs_available", "offset_mean_ps",
         "u_combined_ps2", "u_linear_ps"], diss_rows, "|")

    # ---- per node reports -------------------------------------------------
    budget_by_node = {entry["node_id"]: entry for entry in dissemination["budget"]}
    for node_id in REPORT_NODES:
        entry = budget_by_node[node_id]
        node = nodes[node_id]
        path = _node_path(graph["components"], node_id)
        members = []
        for osc in data["oscillators"]:
            if osc["node_id"] != node_id:
                continue
            pred = prediction.get(osc["osc_id"], {})
            members.append({
                "osc_id": osc["osc_id"],
                "osc_class": osc["osc_class"],
                "status": osc["status"],
                "included": bool(pred.get("included")),
                "exclusion_reason": pred.get("exclusion_reason", ""),
                "dispersion_ps": raw[osc["osc_id"]]["dispersion_ps"] if osc["osc_id"] in raw else 0,
                "final_weight": ratio(capping["final"].get(osc["osc_id"], Fraction(0))),
            })
        blobs["node_report_%s.json" % node_id] = _json({
            "node_id": node_id,
            "component_id": entry["component_id"],
            "role": entry["role"],
            "register_revision": node["register_revision"],
            "reference_oscillator": node["reference_oscillator"],
            "path_link_ids": [link["link_id"] for _, _, link in path],
            "path_length": entry["path_length"],
            "epochs_available": entry["epochs_available"],
            "offset_mean_ps": ratio(entry["offset_mean"]),
            "u_combined_ps2": entry["u_combined_ps2"],
            "u_linear_ps": entry["u_linear_ps"],
            "status": entry["status"],
            "oscillators": members,
        })

    # ---- reconciliation ---------------------------------------------------
    closures = []
    unreconciled = []
    for component in graph["components"]:
        for link_id in component["excluded_link_ids"]:
            link = links[link_id]
            seen = False
            for epoch in range(1, data["epochs"] + 1):
                key = (link_id, epoch)
                if key not in t03:
                    continue
                left = offsets["node_offsets"].get((link["node_a"], epoch))
                right = offsets["node_offsets"].get((link["node_b"], epoch))
                if left is None or right is None:
                    continue
                closures.append({
                    "link_id": link_id,
                    "epoch_index": epoch,
                    "closure_ps": t03[key]["difference_ps"] - (left - right),
                })
                seen = True
            if not seen:
                unreconciled.append(link_id)
    closures.sort(key=lambda c: (c["link_id"], c["epoch_index"]))
    unreconciled.sort()
    xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<network_reconciliation>"]
    xml_lines.append("  <interval>%s</interval>" % config["interval_label"])
    xml_lines.append('  <closures count="%d">' % len(closures))
    for item in closures:
        xml_lines.append("    <closure>")
        xml_lines.append("      <link_id>%s</link_id>" % item["link_id"])
        xml_lines.append("      <epoch_index>%d</epoch_index>" % item["epoch_index"])
        xml_lines.append("      <closure_ps>%s</closure_ps>" % signed(item["closure_ps"]))
        xml_lines.append("    </closure>")
    xml_lines.append("  </closures>")
    xml_lines.append('  <unreconciled count="%d">' % len(unreconciled))
    for link_id in unreconciled:
        xml_lines.append("    <link_id>%s</link_id>" % link_id)
    xml_lines.append("  </unreconciled>")
    xml_lines.append("</network_reconciliation>")
    blobs["network_reconciliation.xml"] = _text(xml_lines)

    # ---- markdown reports -------------------------------------------------
    published = [e for e in dissemination["budget"] if e["status"] == "DS_PUBLISHED"]
    void_epochs = [e for e in range(1, data["epochs"] + 1)
                   if ensemble[e]["state"] == "EP_ENSEMBLE_VOID"]
    report_lines = [
        "# Timescale report %s" % config["interval_label"],
        "",
        "## Network",
        "",
        "hub node: %s" % config["hub_node"],
        "register revision: %s" % config["frozen_register_revision"],
        "components: %d" % len(graph["components"]),
        "registered nodes: %d" % len(nodes),
        "published nodes: %d" % len(published),
        "",
        "## Readings",
        "",
        "canonical readings: %d" % len(t01["canonical"]),
        "set aside rows: %d" % len(t01["dropped"]),
        "dead time records: %d" % len(dead_records),
        "",
        "## Ensemble",
        "",
        "oscillators catalogued: %d" % len(data["oscillators"]),
        "oscillators weighted: %d" % len(capping["final"]),
        "oscillator cap outcome: %s" % capping["osc_outcome"],
        "node cap outcome: %s" % capping["node_outcome"],
        "void epochs: %d" % len(void_epochs),
        "",
        "## Steering",
        "",
        "decision epoch: %d" % plan["decision_epoch"],
        "step atto: %s" % signed(plan["step_atto"]),
        "outcome: %s" % plan["outcome"],
    ]
    blobs["timescale_report.md"] = _text(report_lines)

    summary_lines = [
        "# Ensemble summary %s" % config["interval_label"],
        "",
        "| node | status | epochs | offset mean ps | u linear ps |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in sorted(dissemination["budget"], key=lambda e: e["node_id"]):
        summary_lines.append("| %s | %s | %d | %s | %d |" % (
            entry["node_id"], entry["status"], entry["epochs_available"],
            ratio(entry["offset_mean"]), entry["u_linear_ps"]))
    blobs["ensemble_summary.md"] = _text(summary_lines)

    # ---- node index -------------------------------------------------------
    conf_lines = [
        "interval = %s" % config["interval_label"],
        "hub_node = %s" % config["hub_node"],
        "register_revision = %s" % config["frozen_register_revision"],
        "node_count = %d" % len(nodes),
        "published_node_count = %d" % len(published),
    ]
    for entry in sorted(dissemination["budget"], key=lambda e: e["node_id"]):
        conf_lines.append("%s.component = %s" % (entry["node_id"], entry["component_id"]))
        conf_lines.append("%s.status = %s" % (entry["node_id"], entry["status"]))
        conf_lines.append("%s.epochs_available = %d" % (entry["node_id"], entry["epochs_available"]))
    blobs["node_index.conf"] = _text(conf_lines)

    # ---- manifest ---------------------------------------------------------
    order = list(CORE_FILES)
    if "R_DIGEST_ORDER" in off:
        order = sorted(CORE_FILES)
    digest = hashlib.sha256()
    for name in order:
        digest.update(blobs[name])
    whole = hashlib.sha256()
    for name in ARTIFACTS:
        if name == "publication_manifest.json":
            continue
        whole.update(blobs[name])
    blobs["publication_manifest.json"] = _json({
        "interval": config["interval_label"],
        "document_count": len(ARTIFACTS),
        "core_order": order,
        "digest": digest.hexdigest(),
        "publication_digest": whole.hexdigest(),
        "rule_count": len(RULE_IDS),
        "ensemble_size": len(capping["final"]),
        "oscillator_cap_outcome": capping["osc_outcome"],
        "steering_outcome": plan["outcome"],
    })
    return blobs


def run_pipeline(root, off=frozenset()) -> dict:
    """Run the thirteen stages over one corpus and return the artifact bytes."""
    off = frozenset(off)
    data = load_all(Path(root), off)
    t01 = stage_t01_readings(data, off)
    t02 = stage_t02_calibration(data, t01, off)
    t03 = stage_t03_sense(data, t01, t02, off)
    graph = stage_t04_graph(data, off)
    offsets = stage_t05_offsets(data, t01, t03, graph, off)
    series = stage_t06_series(data, graph, offsets, off)
    prediction = stage_t07_prediction(data, graph, off)
    raw = stage_t08_weights(data, prediction, off)
    capping = stage_t09_capping(data, raw, off)
    ensemble = stage_t10_ensemble(data, series, prediction, capping, off)
    plan = stage_t11_steering(data, ensemble, off)
    steered = stage_t11b_steered(ensemble, plan, data["epochs"], off)
    dissemination = stage_t12_dissemination(data, graph, offsets, steered, off)
    state = {
        "t01": t01, "t02": t02, "t03": t03, "graph": graph, "offsets": offsets,
        "series": series, "prediction": prediction, "raw": raw,
        "capping": capping, "ensemble": ensemble, "plan": plan,
        "steered": steered, "dissemination": dissemination,
    }
    return render(data, state, off)

# --------------------------------------------------------------------------
# writers (stdlib only: real OOXML, real PDF 1.4, real sqlite)
# --------------------------------------------------------------------------
def _cell_ref(col: int, row: int) -> str:
    out = ""
    c = col
    while c > 0:
        c, r = divmod(c - 1, 26)
        out = chr(65 + r) + out
    return f"{out}{row}"


def _sheet_xml(rows: list, shared: list, shared_idx: dict) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    out.append('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">')
    out.append("<sheetData>")
    for ri, row in enumerate(rows, start=1):
        out.append(f'<row r="{ri}">')
        for ci, val in enumerate(row, start=1):
            ref = _cell_ref(ci, ri)
            if val is None or val == "":
                continue
            sval = str(val)
            try:
                float(sval)
                is_num = True
            except ValueError:
                is_num = False
            if is_num:
                out.append(f'<c r="{ref}"><v>{sval}</v></c>')
            else:
                if sval not in shared_idx:
                    shared_idx[sval] = len(shared)
                    shared.append(sval)
                out.append(f'<c r="{ref}" t="s"><v>{shared_idx[sval]}</v></c>')
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def write_xlsx(path: Path, sheets: dict) -> None:
    shared: list = []
    shared_idx: dict = {}
    sheet_xmls = {name: _sheet_xml(rows, shared, shared_idx) for name, rows in sheets.items()}

    ss = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    ss.append(
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(shared)}" uniqueCount="{len(shared)}">'
    )
    for item in shared:
        esc = item.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ss.append(f"<si><t>{esc}</t></si>")
    ss.append("</sst>")

    ctypes = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    ctypes.append('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">')
    ctypes.append('<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>')
    ctypes.append('<Default Extension="xml" ContentType="application/xml"/>')
    ctypes.append('<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>')
    ctypes.append('<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>')
    for i, _ in enumerate(sheets, start=1):
        ctypes.append(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
    ctypes.append("</Types>")

    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
        "</Relationships>"
    )

    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    wb.append('<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">')
    wb.append("<sheets>")
    for i, name in enumerate(sheets, start=1):
        wb.append(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>')
    wb.append("</sheets></workbook>")

    wb_rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    wb_rels.append('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">')
    for i, _ in enumerate(sheets, start=1):
        wb_rels.append(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')
    wb_rels.append(f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>')
    wb_rels.append("</Relationships>")

    entries = [
        ("[Content_Types].xml", "".join(ctypes)),
        ("_rels/.rels", root_rels),
        ("xl/workbook.xml", "".join(wb)),
        ("xl/_rels/workbook.xml.rels", "".join(wb_rels)),
        ("xl/sharedStrings.xml", "".join(ss)),
    ]
    for i, (_, xml) in enumerate(sheet_xmls.items(), start=1):
        entries.append((f"xl/worksheets/sheet{i}.xml", xml))

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            zf.writestr(info, payload)


# --------------------------------------------------------------------------
# pdf writer (minimal, stdlib-only, real PDF 1.4, no embedded timestamp)
# --------------------------------------------------------------------------
def write_pdf(path: Path, lines: list) -> None:
    def esc(t: str) -> str:
        return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    pages = [lines[i:i + 52] for i in range(0, len(lines), 52)] or [[""]]
    objects: list = []
    n_pages = len(pages)
    font_obj = 3 + 2 * n_pages
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(n_pages))
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {n_pages} >>")
    for i, page_lines in enumerate(pages):
        content = "BT /F1 9 Tf 40 750 Td 11 TL\n"
        for ln in page_lines:
            content += f"({esc(ln)}) Tj T*\n"
        content += "ET"
        cbytes = content.encode("latin-1", "replace")
        page_obj = 3 + 2 * i
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> "
            f"/Contents {page_obj + 1} 0 R >>"
        )
        objects.append((cbytes, f"<< /Length {len(cbytes)} >>"))
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        if isinstance(obj, tuple):
            cbytes, hdr = obj
            out.write(f"{i} 0 obj\n{hdr}\nstream\n".encode("latin-1"))
            out.write(cbytes)
            out.write(b"\nendstream\nendobj\n")
        else:
            out.write(f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1"))
    xref_pos = out.tell()
    n = len(objects) + 1
    out.write(f"xref\n0 {n}\n".encode("latin-1"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(f"{off:010d} 00000 n \n".encode("latin-1"))
    out.write(
        f"trailer\n<< /Size {n} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode("latin-1")
    )
    path.write_bytes(out.getvalue())


def write_sqlite(path: Path, tables: dict) -> None:
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    cur = con.cursor()
    for tname, (cols, rows) in tables.items():
        cur.execute("CREATE TABLE %s (%s)" % (tname, ", ".join(f"{c} TEXT" for c in cols)))
        ph = ", ".join("?" for _ in cols)
        cur.executemany(f"INSERT INTO {tname} VALUES ({ph})", rows)
    con.commit()
    con.close()


# --------------------------------------------------------------------------
# corpus generator
#
# One publication interval of the timing network is minted from a named seed.
# The verifier owns this generator, so it can regenerate the shipped interval
# and mint intervals the agent has never seen.
# --------------------------------------------------------------------------
SAMPLE_SEED = 20300317
EVAL_SEED = 20300421
CHALLENGE_SEED = 20300509
PROBE_SEED = 20300628

SEED_PROFILE = {
    SAMPLE_SEED: "settled",
    EVAL_SEED: "strained",
    CHALLENGE_SEED: "strained",
    PROBE_SEED: "sparse",
}

# The link register. The topology is a property of the network, not of the
# interval, so it does not move between intervals; the published
# uncertainties and the physical biases do.
LINK_LAYOUT = [
    ("lk_ca01", "nd_calder", "nd_arden", "LK_FIBRE_TWO_WAY", 260),
    ("lk_cb02", "nd_calder", "nd_borrow", "LK_FIBRE_TWO_WAY", 240),
    ("lk_cd03", "nd_calder", "nd_dunmore", "LK_TWSTFT", 380),
    ("lk_ab04", "nd_arden", "nd_borrow", "LK_GNSS_PPP", 900),
    ("lk_be05", "nd_borrow", "nd_ellsmere", "LK_FIBRE_TWO_WAY", 210),
    ("lk_de06", "nd_dunmore", "nd_ellsmere", "LK_GNSS_CV", 950),
    ("lk_ef07", "nd_ellsmere", "nd_farrow", "LK_TWSTFT", 350),
    ("lk_fg08", "nd_farrow", "nd_gantry", "LK_GNSS_PPP", 870),
    ("lk_gh09", "nd_gantry", "nd_harlow", "LK_FIBRE_TWO_WAY", 190),
    ("lk_ah10", "nd_arden", "nd_harlow", "LK_GNSS_CV", 930),
    ("lk_hi11", "nd_harlow", "nd_ingle", "LK_TWSTFT", 400),
    ("lk_df12", "nd_dunmore", "nd_farrow", "LK_GNSS_PPP", 880),
    ("lk_cg13", "nd_calder", "nd_gantry", "LK_TWSTFT", 150),
    ("lk_ce14", "nd_calder", "nd_ellsmere", "LK_GNSS_CV", 170),
    ("lk_ce15", "nd_calder", "nd_ellsmere", "LK_GNSS_PPP", 170),
    ("lk_jk16", "nd_jarrow", "nd_kelvin", "LK_TWSTFT", 420),
    ("lk_jk17", "nd_jarrow", "nd_kelvin", "LK_FIBRE_TWO_WAY", 420),
    ("lk_jk18", "nd_jarrow", "nd_kelvin", "LK_FIBRE_TWO_WAY", 420),
    ("lk_ff18", "nd_farrow", "nd_farrow", "LK_GNSS_CV", 500),
    ("lk_zz19", "nd_farrow", "nd_phantom", "LK_GNSS_PPP", 500),
]

# The oscillator population. The first oscillator listed at a node is the
# reference oscillator that node's clock is realised by at register revision
# REG-R14.
OSC_LAYOUT = [
    ("osc_ar01", "nd_arden", "OSC_HMASER"),
    ("osc_ar02", "nd_arden", "OSC_CS_BEAM"),
    ("osc_ar03", "nd_arden", "OSC_OCXO"),
    ("osc_bo01", "nd_borrow", "OSC_HMASER"),
    ("osc_bo02", "nd_borrow", "OSC_RB_FOUNTAIN"),
    ("osc_ca01", "nd_calder", "OSC_CRYO_SAPPHIRE"),
    ("osc_ca02", "nd_calder", "OSC_HMASER"),
    ("osc_ca03", "nd_calder", "OSC_HMASER"),
    ("osc_ca04", "nd_calder", "OSC_RB_FOUNTAIN"),
    ("osc_ca05", "nd_calder", "OSC_CS_BEAM"),
    ("osc_du01", "nd_dunmore", "OSC_HMASER"),
    ("osc_du02", "nd_dunmore", "OSC_CS_BEAM"),
    ("osc_du03", "nd_dunmore", "OSC_OCXO"),
    ("osc_el01", "nd_ellsmere", "OSC_RB_FOUNTAIN"),
    ("osc_el02", "nd_ellsmere", "OSC_HMASER"),
    ("osc_fa01", "nd_farrow", "OSC_HMASER"),
    ("osc_fa02", "nd_farrow", "OSC_CS_BEAM"),
    ("osc_fa03", "nd_farrow", "OSC_OCXO"),
    ("osc_ga01", "nd_gantry", "OSC_CS_BEAM"),
    ("osc_ga02", "nd_gantry", "OSC_RB_FOUNTAIN"),
    ("osc_ha01", "nd_harlow", "OSC_HMASER"),
    ("osc_ha02", "nd_harlow", "OSC_CS_BEAM"),
    ("osc_ha03", "nd_harlow", "OSC_OCXO"),
    ("osc_in01", "nd_ingle", "OSC_CS_BEAM"),
    ("osc_in02", "nd_ingle", "OSC_OCXO"),
    ("osc_ja01", "nd_jarrow", "OSC_HMASER"),
    ("osc_ja02", "nd_jarrow", "OSC_OCXO"),
    ("osc_ke01", "nd_kelvin", "OSC_RB_FOUNTAIN"),
    ("osc_ke02", "nd_kelvin", "OSC_CS_BEAM"),
    ("osc_ly01", "nd_lyddon", "OSC_OCXO"),
]

# Archive noise amplitude by oscillator class, in picoseconds. This is what
# the residual dispersion of the previous interval measures, and therefore
# what sets the raw weight.
CLASS_AMPLITUDE = {
    "OSC_CRYO_SAPPHIRE": 40,
    "OSC_HMASER": 120,
    "OSC_RB_FOUNTAIN": 260,
    "OSC_CS_BEAM": 700,
    "OSC_OCXO": 2400,
}

# Ceiling weight by class, published only in the workbook.
CLASS_CEILING = {
    "OSC_CRYO_SAPPHIRE": 60000,
    "OSC_HMASER": 25000,
    "OSC_RB_FOUNTAIN": 12000,
    "OSC_CS_BEAM": 5000,
    "OSC_OCXO": 1500,
}

UNCERTAINTY_TERMS = [
    "UC_CABLE",
    "UC_ELECTRONICS",
    "UC_ENVIRONMENT",
    "UC_MODEL",
    "UC_QUANTISATION",
    "UC_REFERENCE",
    "UC_TEMPERATURE",
]

REGISTER_REVISIONS = ["REG-R12", "REG-R13", "REG-R14", "REG-R15", "REG-R16"]
FROZEN_REVISION = "REG-R14"

# Oscillators the interval singles out. The corpus is minted so that every
# exclusion reason and every boundary the specification names is exercised.
DECOMMISSIONED_OSC = "osc_fa03"
NO_ARCHIVE_OSC = "osc_ha03"
SHORT_HISTORY_OSC = "osc_du03"
BOUNDARY_HISTORY_OSC = "osc_ga02"
ZERO_DISPERSION_OSC = "osc_ca01"
# The zero dispersion oscillator takes the ceiling of its own class only. The
# first minted interval also lays the history window of one included
# oscillator of every other class on a straight line, so each of the five
# ceilings the live sheet publishes is taken in some graded interval and a
# program holding any one of them is caught.
MINTED_FLAT_WINDOWS = {
    EVAL_SEED: ["osc_ar03", "osc_bo02", "osc_du01", "osc_fa02"],
}
DEAD_LINK = "lk_hi11"
# The tree edge of the unanchored pair. It carries no locked attempt at any
# epoch, so the far node of that component reaches no published offset.
RIM_TREE_LINK = "lk_jk17"
ABSENT_CAL_LINK = "lk_ah10"
SUPPLEMENT_LINKS = ["lk_ca01", "lk_cg13", "lk_ce15", "lk_be05", "lk_gh09"]

SPARSE_KEEP = ["osc_ar01", "osc_bo01", "osc_du01", "osc_el01", "osc_fa01", "osc_ga01"]


def _profile(seed: int) -> str:
    return SEED_PROFILE.get(seed, "settled")


def _interval_label(seed: int) -> str:
    year = 2030 + (seed // 100000) % 3
    month = 1 + (seed // 100) % 12
    return "PI-%04d-M%02d" % (year, month)


SWEEP_BUDGETS = [3, 4, 5, 6]


def _control_draws(seed: int) -> tuple:
    control = random.Random(seed * 29 + 17)
    controls = {
        "cap_den": control.choice([8, 10, 12]),
        "node_cap_num": control.choice([3, 4, 5]),
        "sweep_budget": control.choice(SWEEP_BUDGETS),
        "history_minimum": control.choice([5, 6, 7, 8]),
        "ceiling_scale": control.choice([1, 2, 3]),
    }
    return controls, control


def _mint_structure(seed: int, profile: str) -> dict:
    rng = random.Random(seed * 7 + 11)
    start = 1893456000 + (seed % 211) * STEP_SECONDS
    grid_offset = 43200
    grid = [start + (k - 1) * STEP_SECONDS + grid_offset for k in range(1, INTERVAL_EPOCHS + 1)]

    link_bias = {}
    for link_id, node_a, node_b, technique, uncertainty in LINK_LAYOUT:
        span = max(20, uncertainty // 3)
        link_bias[link_id] = rng.randrange(-span, span + 1)

    node_base = {}
    node_drift = {}
    node_noise = {}
    roots = {"nd_calder", "nd_jarrow", "nd_lyddon"}
    for node in NODES:
        if node in roots:
            node_base[node] = 0
            node_drift[node] = 0
            node_noise[node] = {}
            continue
        node_base[node] = rng.randrange(-3_000_000, 3_000_001)
        node_drift[node] = rng.randrange(-350_000, 350_001)
        node_noise[node] = {}
        for m in range(-ARCHIVE_EPOCHS, INTERVAL_EPOCHS + 1):
            node_noise[node][m] = rng.randrange(-600, 601)

    osc_base = {}
    osc_drift = {}
    osc_noise = {}
    reference = {}
    for node in NODES:
        members = [row for row in OSC_LAYOUT if row[1] == node]
        reference[node] = members[0][0]
    for osc_id, node, osc_class in OSC_LAYOUT:
        if reference[node] == osc_id:
            osc_base[osc_id] = 0
            osc_drift[osc_id] = 0
            osc_noise[osc_id] = {}
            continue
        osc_base[osc_id] = rng.randrange(-400_000, 400_001)
        osc_drift[osc_id] = rng.randrange(-180_000, 180_001)
        osc_noise[osc_id] = {}
        for m in range(-ARCHIVE_EPOCHS, INTERVAL_EPOCHS + 1):
            osc_noise[osc_id][m] = rng.randrange(-45, 46)

    # The zero dispersion oscillator carries a drift the grid represents
    # exactly, so its archived deviations sit on a straight line and the
    # residual dispersion of its window is exactly zero.
    class_noise = {}
    for osc_id, node, osc_class in OSC_LAYOUT:
        amplitude = CLASS_AMPLITUDE[osc_class]
        class_noise[osc_id] = {}
        for n in range(1, ARCHIVE_EPOCHS + 1):
            class_noise[osc_id][n] = rng.randrange(-amplitude, amplitude + 1)
    window_first = ARCHIVE_EPOCHS - 12 + 1
    for n in range(window_first, ARCHIVE_EPOCHS + 1):
        class_noise[ZERO_DISPERSION_OSC][n] = 0

    # Control values of this interval. The memo publishes the first four and
    # the live workbook sheet the last two, and no two intervals of the
    # network agree on all of them.
    controls, control = _control_draws(seed)
    cap_num, cap_den = 1, controls["cap_den"]
    # The node cap is drawn from three shares. A tighter share leaves the
    # node pass more excess to hand out, and a looser one hands out enough
    # to push a receiver back over the oscillator cap, which is the state
    # the third pass exists for. Both are reached across the four intervals.
    node_cap_num, node_cap_den = controls["node_cap_num"], 10
    sweep_budget = controls["sweep_budget"]
    history_minimum = controls["history_minimum"]
    ceiling_scale = controls["ceiling_scale"]
    if seed != SAMPLE_SEED:
        # A minted interval runs a sweep budget other than the shipped
        # interval's and writes its oscillator cap share over a numerator
        # other than one, so a program that holds either memo value instead
        # of reading it reproduces the shipped bytes and no minted ones. The
        # share itself is kept, so the capping each interval exercises is the
        # one its cap denominator was drawn for.
        shipped, _ = _control_draws(SAMPLE_SEED)
        if sweep_budget == shipped["sweep_budget"]:
            sweep_budget = control.choice(
                [b for b in SWEEP_BUDGETS if b != shipped["sweep_budget"]])
        share_scale = control.choice([2, 3])
        cap_num, cap_den = cap_num * share_scale, cap_den * share_scale
    ceilings = {name: value * ceiling_scale for name, value in CLASS_CEILING.items()}

    uncertainty_terms = {}
    for osc_id, node, osc_class in OSC_LAYOUT:
        uncertainty_terms[osc_id] = [rng.randrange(12, 260) for _ in UNCERTAINTY_TERMS]

    declared = {}
    for revision in REGISTER_REVISIONS:
        declared[revision] = {node: rng.randrange(40, 400) for node in NODES}

    return {
        "seed": seed,
        "profile": profile,
        "cap_num": cap_num,
        "cap_den": cap_den,
        "node_cap_num": node_cap_num,
        "node_cap_den": node_cap_den,
        "sweep_budget": sweep_budget,
        "history_minimum": history_minimum,
        "ceilings": ceilings,
        "ref_set": set(reference.values()),
        "start": start,
        "grid_offset": grid_offset,
        "grid": grid,
        "link_bias": link_bias,
        "node_base": node_base,
        "node_drift": node_drift,
        "node_noise": node_noise,
        "osc_base": osc_base,
        "osc_drift": osc_drift,
        "osc_noise": osc_noise,
        "class_noise": class_noise,
        "reference": reference,
        "uncertainty_terms": uncertainty_terms,
        "declared": declared,
        "rng": rng,
    }


def _node_dev(mint: dict, node: str, m: int) -> int:
    if node not in mint["node_base"]:
        return 0
    if node in ("nd_calder", "nd_jarrow", "nd_lyddon"):
        return 0
    return (mint["node_base"][node]
            + half_even(phase_ps(Fraction(mint["node_drift"][node]), m))
            + mint["node_noise"][node].get(m, 0))


def _local_dev(mint: dict, osc_id: str, m: int) -> int:
    if mint["osc_base"][osc_id] == 0 and mint["osc_drift"][osc_id] == 0 \
            and not mint["osc_noise"][osc_id]:
        return 0
    return (mint["osc_base"][osc_id]
            + half_even(phase_ps(Fraction(mint["osc_drift"][osc_id]), m))
            + mint["osc_noise"][osc_id].get(m, 0))


def _osc_dev(mint: dict, osc_id: str, node: str, m: int) -> int:
    return _node_dev(mint, node, m) + _local_dev(mint, osc_id, m)


def _mint_reports(mint: dict) -> dict:
    """The delay calibration ledger and the supplement that extends it."""
    rng = random.Random(mint["seed"] * 13 + 5)
    grid = mint["grid"]
    start = mint["start"]
    reports: dict = {}
    supplement: dict = {}
    for index, (link_id, node_a, node_b, technique, uncertainty) in enumerate(LINK_LAYOUT):
        rows = []
        base_issue = start - 500 * STEP_SECONDS
        if link_id == ABSENT_CAL_LINK:
            # Every report for this link takes effect after the interval
            # closes, so no report governs any reading on it.
            for revision in range(1, 4):
                rows.append({
                    "report_id": "cal_%s_r%d" % (link_id[3:], revision),
                    "link_id": link_id,
                    "effective_epoch_s": grid[-1] + (revision + 4) * STEP_SECONDS,
                    "issued_epoch_s": base_issue + revision * 3 * STEP_SECONDS,
                    "revision": revision,
                    "delay_a_ns": rng.randrange(120, 900),
                    "delay_b_ns": rng.randrange(120, 900),
                    "status": "CAL_SIGNED" if revision % 2 else "CAL_PROVISIONAL",
                })
            reports[link_id] = rows
            continue
        plan = [
            (start - 400 * STEP_SECONDS, base_issue + 1 * STEP_SECONDS, 1, "CAL_SIGNED"),
            (start - 10 * STEP_SECONDS, base_issue + 90 * STEP_SECONDS, 2, "CAL_SIGNED"),
            (grid[9], base_issue + 40 * STEP_SECONDS, 3, "CAL_SIGNED"),
            (grid[9], base_issue + 200 * STEP_SECONDS, 4, "CAL_PROVISIONAL"),
            (grid[19], base_issue + 30 * STEP_SECONDS, 5,
             "CAL_PROVISIONAL" if index % 3 == 1 else "CAL_SIGNED"),
            (grid[-1] + 30 * STEP_SECONDS, base_issue + 400 * STEP_SECONDS, 6, "CAL_PROVISIONAL"),
        ]
        for effective, issued, revision, status in plan:
            rows.append({
                "report_id": "cal_%s_r%d" % (link_id[3:], revision),
                "link_id": link_id,
                "effective_epoch_s": effective,
                "issued_epoch_s": issued,
                "revision": revision,
                "delay_a_ns": rng.randrange(120, 900) + index,
                "delay_b_ns": rng.randrange(120, 900) + index,
                "status": status,
            })
        reports[link_id] = rows
        if link_id in SUPPLEMENT_LINKS:
            supplement[link_id] = [{
                "report_id": "cal_%s_r7" % link_id[3:],
                "link_id": link_id,
                "effective_epoch_s": grid[14],
                "issued_epoch_s": base_issue + 120 * STEP_SECONDS,
                "revision": 7,
                "delay_a_ns": rng.randrange(120, 900) + index,
                "delay_b_ns": rng.randrange(120, 900) + index,
                "status": "CAL_SIGNED",
            }]
    return {"ledger": reports, "supplement": supplement}


def _all_reports(book: dict, link_id: str) -> list:
    rows = list(book["ledger"].get(link_id, [])) + list(book["supplement"].get(link_id, []))
    rows.sort(key=lambda r: (r["effective_epoch_s"], r["revision"], r["report_id"]))
    return rows


def _mint_sessions(mint: dict, book: dict) -> dict:
    """The raw acquisition log, the withdrawal journal and the local monitor
    log, minted together so every documented defeating condition appears."""
    rng = random.Random(mint["seed"] * 17 + 3)
    grid = mint["grid"]
    profile = mint["profile"]
    tolerance = 5400
    sessions = []
    withdrawn = []
    counter = 0

    link_by_id = {row[0]: row for row in LINK_LAYOUT}
    no_lock_targets = set()
    for epoch in range(1, INTERVAL_EPOCHS + 1):
        no_lock_targets.add((DEAD_LINK, epoch))
        no_lock_targets.add((RIM_TREE_LINK, epoch))
    for epoch in (4, 11, 23):
        no_lock_targets.add(("lk_ef07", epoch))
        no_lock_targets.add(("lk_be05", epoch))
    outage_epoch = 26 if profile == "sparse" else None

    for link_id, node_a, node_b, technique, uncertainty in LINK_LAYOUT:
        sense = TECHNIQUE_SENSE[technique]
        reports = _all_reports(book, link_id)
        for epoch in range(1, INTERVAL_EPOCHS + 1):
            instant = grid[epoch - 1]
            if outage_epoch is not None and epoch == outage_epoch:
                continue
            attempts = 1 + (rng.randrange(0, 100) < 55) + (rng.randrange(0, 100) < 20)
            offsets = []
            for attempt in range(attempts):
                offsets.append(rng.randrange(-tolerance + 200, tolerance - 200))
            if (link_id, epoch) == ("lk_cd03", 7):
                # Two receivers report the same attempt number at equal
                # distance from the epoch instant.
                offsets = [-1800, 1800]
                attempts = 2
            if (link_id, epoch) == ("lk_ca01", 13):
                # Two receivers report the same attempt number at different
                # distances from the epoch instant.
                offsets = [-2600, 400]
                attempts = 2
            for index in range(attempts):
                counter += 1
                acq = instant + offsets[index]
                if (link_id, epoch) in (("lk_cd03", 7), ("lk_ca01", 13)):
                    attempt_no = 2
                else:
                    attempt_no = index + 1
                if (link_id, epoch) in (("lk_cd03", 7), ("lk_ca01", 13)):
                    lock = "LOCK_HELD"
                elif (link_id, epoch) in no_lock_targets:
                    lock = ["LOCK_LOST", "LOCK_SLIP", "LOCK_UNKNOWN"][index % 3]
                elif index + 1 < attempts:
                    lock = ["LOCK_SLIP", "LOCK_LOST"][index % 2]
                else:
                    lock = "LOCK_HELD"
                m = epoch
                d_ab = (_node_dev(mint, node_a, m) - _node_dev(mint, node_b, m)
                        + mint["link_bias"][link_id])
                corrected = d_ab if sense == "SENSE_A_MINUS_B" else -d_ab
                report = applicable_report(reports, acq)
                raw = corrected + calibration_ps(report)
                if lock != "LOCK_HELD":
                    raw += rng.randrange(-90000, 90001)
                sessions.append({
                    "session_id": "ses_%06d" % counter,
                    "link_id": link_id,
                    "receiver_id": "rx_%s_%d" % (link_id[3:7], index + 1),
                    "attempt_no": attempt_no,
                    "acq_time_s": acq,
                    "raw_offset_ps": raw,
                    "lock_state": lock,
                })
        _ = link_by_id

    # Rows that land in no attribution window at all, including one that sits
    # exactly on the closing edge of a window and one exactly on its opening
    # edge.
    outside_ids = []
    for epoch, delta in ((5, tolerance), (9, tolerance + 600), (17, -tolerance),
                         (21, tolerance + 2400), (28, tolerance)):
        counter += 1
        instant = grid[epoch - 1]
        outside_ids.append("ses_%06d" % counter)
        sessions.append({
            "session_id": "ses_%06d" % counter,
            "link_id": "lk_cb02",
            "receiver_id": "rx_cb02_9",
            "attempt_no": 9,
            "acq_time_s": instant + delta,
            "raw_offset_ps": rng.randrange(-4_000_000, 4_000_001),
            "lock_state": "LOCK_HELD",
        })

    # Rows on a link the register does not carry, and rows on a link whose
    # two endpoints are the same node.
    unregistered_ids = []
    for epoch in range(1, 13):
        counter += 1
        unregistered_ids.append("ses_%06d" % counter)
        sessions.append({
            "session_id": "ses_%06d" % counter,
            "link_id": "lk_absent_99",
            "receiver_id": "rx_ab99_1",
            "attempt_no": 1,
            "acq_time_s": grid[epoch - 1] + 300,
            "raw_offset_ps": rng.randrange(-2_000_000, 2_000_001),
            "lock_state": "LOCK_HELD",
        })

    # Withdrawn sessions. The journal names the acquisition session, not the
    # cluster, so a cluster keeps its other attempts.
    held = [row for row in sessions if row["lock_state"] == "LOCK_HELD"
            and row["link_id"] in ("lk_cg13", "lk_ce15", "lk_gh09", "lk_cd03")]
    step = max(1, len(held) // 9)
    for row in held[::step][:9]:
        withdrawn.append({
            "session_id": row["session_id"],
            "withdrawn_at_s": row["acq_time_s"] + 3 * STEP_SECONDS,
            "reason_note": "receiver maintenance recorded after the fact",
            "authorised_by": "desk_%s" % row["link_id"][3:7],
        })

    # Two of the withdrawn sessions also satisfy an earlier predicate: one
    # falls in no attribution window and one names a link the register does
    # not carry. The predicates are ordered and the first match is the reason,
    # so these two are the rows that make that order decide something.
    by_id = {row["session_id"]: row for row in sessions}
    for session_id in (outside_ids[1], unregistered_ids[4]):
        row = by_id[session_id]
        withdrawn.append({
            "session_id": session_id,
            "withdrawn_at_s": row["acq_time_s"] + 3 * STEP_SECONDS,
            "reason_note": "acquisition withdrawn after the desk reviewed it",
            "authorised_by": "desk_%s" % row["link_id"][3:7],
        })

    sessions.sort(key=lambda r: (r["session_id"],))
    withdrawn.sort(key=lambda r: r["session_id"])
    return {"sessions": sessions, "withdrawn": withdrawn}


def _mint_local(mint: dict) -> list:
    rng = random.Random(mint["seed"] * 19 + 7)
    rows = []
    suspect = {("osc_ar02", 6), ("osc_ar02", 7), ("osc_ca03", 14),
               ("osc_du02", 19), ("osc_ha02", 3), ("osc_ke02", 22)}
    for osc_id, node, osc_class in OSC_LAYOUT:
        if mint["reference"][node] == osc_id:
            continue
        for epoch in range(1, INTERVAL_EPOCHS + 1):
            if (osc_id, epoch) in suspect:
                flag = "MON_SUSPECT"
            else:
                flag = "MON_VALID"
            rows.append({
                "monitor_id": "mon_%s" % osc_id[4:],
                "osc_id": osc_id,
                "epoch_index": epoch,
                "local_offset_ps": _local_dev(mint, osc_id, epoch),
                "monitor_flag": flag,
            })
    _ = rng
    return rows


def _mint_archive(mint: dict) -> list:
    rng = random.Random(mint["seed"] * 23 + 13)
    profile = mint["profile"]
    rows = []
    window_first = ARCHIVE_EPOCHS - 12 + 1
    for osc_id, node, osc_class in OSC_LAYOUT:
        if osc_id in (NO_ARCHIVE_OSC, DECOMMISSIONED_OSC):
            # The decommissioned oscillator carries no archive row either, so
            # it satisfies EX_DECOMMISSIONED and EX_NO_ARCHIVE at once and the
            # order stage T07 tests the two in decides which reason is
            # published for it.
            continue
        if profile == "sparse" and osc_id not in SPARSE_KEEP:
            invalid_window = set(range(window_first, ARCHIVE_EPOCHS + 1))
        elif osc_id == SHORT_HISTORY_OSC:
            # one valid deviation short of the minimum, so it is excluded
            keep = mint["history_minimum"] - 1
            invalid_window = set(sorted(range(window_first, ARCHIVE_EPOCHS + 1))[:12 - keep])
        elif osc_id == BOUNDARY_HISTORY_OSC:
            # exactly the minimum, so the strictness of the comparison shows
            keep = mint["history_minimum"]
            invalid_window = set(sorted(range(window_first, ARCHIVE_EPOCHS + 1))[:12 - keep])
        else:
            invalid_window = set()
        values = {n: _osc_dev(mint, osc_id, node, n - ARCHIVE_EPOCHS)
                  + mint["class_noise"][osc_id][n]
                  for n in range(1, ARCHIVE_EPOCHS + 1)}
        if osc_id in MINTED_FLAT_WINDOWS.get(mint["seed"], []):
            first = values[window_first]
            step = (values[ARCHIVE_EPOCHS] - first) // (ARCHIVE_EPOCHS - window_first)
            for n in range(window_first, ARCHIVE_EPOCHS + 1):
                values[n] = first + step * (n - window_first)
        for n in range(1, ARCHIVE_EPOCHS + 1):
            value = values[n]
            if n in invalid_window:
                flag = ["ARC_SUSPECT", "ARC_VOID", "ARC_ESTIMATED"][n % 3]
            elif n % 11 == 5 and n < window_first:
                flag = "ARC_ESTIMATED"
            elif n % 13 == 7 and n < window_first:
                flag = "ARC_VOID"
            elif n % 17 == 3 and n < window_first:
                flag = "ARC_SUSPECT"
            else:
                flag = "ARC_VALID"
            rows.append({
                "osc_id": osc_id,
                "archive_epoch": n,
                "deviation_ps": value,
                "quality_flag": flag,
            })
    _ = rng
    return rows


def _write_text(path: Path, text: str) -> None:
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def _write_table(path: Path, header: list, rows: list, sep: str) -> None:
    lines = [sep.join(header)]
    for row in rows:
        lines.append(sep.join(str(row[column]) for column in header))
    _write_text(path, "\n".join(lines))


def _write_jsonl(path: Path, records: list) -> None:
    _write_text(path, "\n".join(compact_json(record) for record in records))


def generate(seed: int, out_dir) -> dict:
    """Mint one publication interval of the timing network into out_dir."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    profile = _profile(seed)
    mint = _mint_structure(seed, profile)
    book = _mint_reports(mint)
    log = _mint_sessions(mint, book)
    local = _mint_local(mint)
    archive = _mint_archive(mint)
    grid = mint["grid"]
    label = _interval_label(seed)
    # The live workbook sheet is identified by its key cell and by nothing
    # else. Both sheets carry a revision label that says nothing about which
    # one is in force, both keys are minted in the same shape, and the order
    # the two sit in the workbook moves with the interval, so neither the name
    # of a sheet nor its position settles which one the desk works to.
    sheet_rng = random.Random(seed * 37 + 5)
    live_revision, draft_revision = sheet_rng.sample([3, 5, 7, 9], 2)
    sheet_key = "TN-R%d-%05d" % (live_revision, seed % 90000 + 10000)
    draft_key = "TN-R%d-%05d" % (draft_revision, seed % 90000 + 10000)
    sweep_budget = mint["sweep_budget"]
    history_minimum = mint["history_minimum"]
    cap_num, cap_den = mint["cap_num"], mint["cap_den"]
    node_cap_num, node_cap_den = mint["node_cap_num"], mint["node_cap_den"]
    ceilings = mint["ceilings"]

    # ---- configuration and policy ----------------------------------------
    _write_text(out / "network_config.json", canonical_json({
        "interval_label": label,
        "interval_start_epoch_s": mint["start"],
        "interval_epochs": INTERVAL_EPOCHS,
        "grid_step_seconds": STEP_SECONDS,
        "hub_node": HUB_NODE,
        "frozen_register_revision": FROZEN_REVISION,
        "workbook_sheet_key": sheet_key,
        "archive_epochs": ARCHIVE_EPOCHS,
        "profile_note": "acquisition profile %s" % profile,
    }).rstrip("\n"))

    _write_text(out / "epoch_grid_policy.yaml", "\n".join([
        "# Attribution of an acquisition row onto the publication grid.",
        "grid_instant_offset_s: 43200",
        "attribution_tolerance_s: 5400",
        "window_kind: half_open_low_inclusive",
        "cluster_key: link_id_and_epoch_index",
        "canonical_attempt: greatest_attempt_number_holding_lock",
        "attempt_tie_break: smallest_absolute_offset_then_earliest_acquisition",
    ]))
    _write_text(out / "weighting_policy.yaml", "\n".join([
        "# Prediction and weighting of the oscillator ensemble.",
        "history_window_epochs: 12",
        "valid_archive_flag: ARC_VALID",
        "weight_scale: 1000000",
        "slope_estimator: two_point_endpoint",
        "dispersion_statistic: mean_absolute_residual",
        "dispersion_use: published_whole_picosecond",
        "zero_dispersion_weight: class_ceiling_from_workbook",
        "weight_places: 6",
        "damping_numerator: 9",
        "damping_denominator: 20",
    ]))
    _write_text(out / "capping_policy.yaml", "\n".join([
        "# Capacity binding of the weight vector.",
        "first_pass: oscillator_cap",
        "second_pass: node_cap",
        "third_pass: single_oscillator_sweep",
        "redistribution: mass_preserving_proportional",
        "first_pass_step: damped_toward_the_capped_target",
        "damping_source: weighting_policy",
        "grid_placement: after_every_pass",
        "grid_residue: closed_onto_the_least_frequent_receiving_holder",
        "grid_residue_count: across_every_pass_of_all_three_phases",
        "oscillator_cap_source: signed_calibration_memo",
        "node_cap_source: workbook_live_sheet",
        "sweep_budget_source: signed_calibration_memo",
    ]))
    _write_text(out / "steering_policy.yaml", "\n".join([
        "# Steering of the free scale onto the primary realisation.",
        "decision_epoch: 12",
        "horizon_epochs: 10",
        "grid_atto: 500",
        "quantisation: truncate_toward_zero",
        "first_corrected_epoch: decision_epoch_plus_one",
    ]))
    _write_text(out / "rounding_policy.yaml", "\n".join([
        "# Rounding is applied at write time and at no earlier point.",
        "mode: round_half_even",
        "ratio_places: 12",
        "integer_unit_time: picosecond",
        "integer_unit_frequency: parts_in_ten_to_the_eighteenth",
        "negative_zero: written_as_zero",
        "empty_delimited_artifact: header_row_only",
        "empty_line_artifact: zero_bytes",
    ]))
    _write_text(out / "ordering_dependencies.yaml", "\n".join([
        "# What is frozen at which stage, and the order the digest runs in.",
        "frozen_at_t01: canonical_reading_per_cluster",
        "frozen_at_t04: spanning_tree_edge_set",
        "frozen_at_t07: prediction_frequency_and_anchor",
        "frozen_at_t09: final_weight_vector",
        "frozen_at_t11: steering_step",
        "digest_order:",
        "  - reading_ledger.csv",
        "  - link_differences.psv",
        "  - oscillator_series.csv",
        "  - weight_book.json",
        "  - ensemble_scale.csv",
        "  - steered_scale.csv",
    ]))
    _write_text(out / "uncertainty_budget_policy.yaml", "\n".join([
        "# The dissemination uncertainty budget.",
        "oscillator_terms: seven_named_terms_from_workbook",
        "register_term: declared_uncertainty_ps_at_frozen_revision",
        "path_terms: published_uncertainty_ps_of_every_tree_edge_on_the_path",
        "combined_statistic: sum_of_squares_in_square_picoseconds",
        "conservative_statistic: arithmetic_sum_in_picoseconds",
    ]))

    # ---- registers --------------------------------------------------------
    link_rows = []
    for link_id, node_a, node_b, technique, uncertainty in LINK_LAYOUT:
        link_rows.append({
            "link_id": link_id,
            "node_a": node_a,
            "node_b": node_b,
            "technique": technique,
            "published_uncertainty_ps": uncertainty,
            "commissioned_epoch_s": mint["start"] - 900 * STEP_SECONDS,
        })
    _write_table(out / "link_register.csv",
                 ["link_id", "node_a", "node_b", "technique",
                  "published_uncertainty_ps", "commissioned_epoch_s"],
                 link_rows, ",")

    frozen_rows = []
    current_rows = []
    for revision in REGISTER_REVISIONS:
        for node in NODES:
            members = [row for row in OSC_LAYOUT if row[1] == node]
            if revision in ("REG-R15", "REG-R16") and node in ("nd_arden", "nd_calder"):
                chosen = members[1][0]
            else:
                chosen = members[0][0]
            row = {
                "node_id": node,
                "register_revision": revision,
                "site_class": "SITE_CORE" if node in CORE_NODES else "SITE_RIM",
                "reference_oscillator": chosen,
                "declared_uncertainty_ps": mint["declared"][revision][node],
            }
            frozen_rows.append(row)
            if revision == REGISTER_REVISIONS[-1]:
                current_rows.append(dict(row))
    _write_table(out / "node_register_frozen.csv",
                 ["node_id", "register_revision", "site_class",
                  "reference_oscillator", "declared_uncertainty_ps"],
                 frozen_rows, ",")
    _write_table(out / "node_register_current.csv",
                 ["node_id", "register_revision", "site_class",
                  "reference_oscillator", "declared_uncertainty_ps"],
                 current_rows, ",")

    osc_rows = []
    for osc_id, node, osc_class in OSC_LAYOUT:
        osc_rows.append({
            "osc_id": osc_id,
            "node_id": node,
            "osc_class": osc_class,
            "status": "OS_DECOMMISSIONED" if osc_id == DECOMMISSIONED_OSC else "OS_ACTIVE",
            "serial": "sn-%s-%04d" % (osc_id[4:], (seed + len(osc_id)) % 9000 + 1000),
        })
    _write_table(out / "oscillator_catalogue.csv",
                 ["osc_id", "node_id", "osc_class", "status", "serial"],
                 osc_rows, ",")

    # ---- acquisition and monitor logs ------------------------------------
    _write_table(out / "comparison_session_log.csv",
                 ["session_id", "link_id", "receiver_id", "attempt_no",
                  "acq_time_s", "raw_offset_ps", "lock_state"],
                 log["sessions"], ",")
    _write_table(out / "session_withdrawal_journal.tsv",
                 ["session_id", "withdrawn_at_s", "reason_note", "authorised_by"],
                 log["withdrawn"], "\t")
    _write_table(out / "local_comparison_log.psv",
                 ["monitor_id", "osc_id", "epoch_index", "local_offset_ps",
                  "monitor_flag"], local, "|")
    _write_table(out / "prior_interval_deviations.psv",
                 ["osc_id", "archive_epoch", "deviation_ps", "quality_flag"],
                 archive, "|")

    ledger_rows = []
    supplement_rows = []
    for link_id, node_a, node_b, technique, uncertainty in LINK_LAYOUT:
        for row in book["ledger"].get(link_id, []):
            ledger_rows.append(row)
        for row in book["supplement"].get(link_id, []):
            supplement_rows.append(row)
    columns = ["report_id", "link_id", "effective_epoch_s", "issued_epoch_s",
               "revision", "delay_a_ns", "delay_b_ns", "status"]
    _write_table(out / "delay_calibration_ledger.csv", columns, ledger_rows, ",")
    _write_table(out / "delay_calibration_supplement.psv", columns, supplement_rows, "|")

    # ---- decoys -----------------------------------------------------------
    legacy_rows = []
    for osc_id, node, osc_class in OSC_LAYOUT:
        legacy_rows.append({
            "osc_id": osc_id,
            "legacy_weight": CLASS_CEILING[osc_class] // 7 + len(osc_id),
            "scheme": "LEGACY_FIXED_CLASS_WEIGHT",
            "retired_at_revision": "REG-R09",
        })
    _write_table(out / "legacy_weight_table.csv",
                 ["osc_id", "legacy_weight", "scheme", "retired_at_revision"],
                 legacy_rows, ",")

    topo = ['<?xml version="1.0" encoding="UTF-8"?>', "<topology>",
            "  <revision>%s</revision>" % FROZEN_REVISION]
    for link_id, node_a, node_b, technique, uncertainty in LINK_LAYOUT:
        topo.append("  <edge>")
        topo.append("    <link_id>%s</link_id>" % link_id)
        topo.append("    <node_a>%s</node_a>" % node_a)
        topo.append("    <node_b>%s</node_b>" % node_b)
        topo.append("    <technique>%s</technique>" % technique)
        topo.append("  </edge>")
    topo.append("</topology>")
    _write_text(out / "network_topology.xml", "\n".join(topo))

    draft = ['<?xml version="1.0" encoding="UTF-8"?>', "<topology_draft>",
             "  <revision>REG-R17</revision>",
             "  <note>proposed rerouting, not commissioned</note>"]
    for link_id, node_a, node_b, technique, uncertainty in LINK_LAYOUT[:8]:
        draft.append("  <edge>")
        draft.append("    <link_id>%s</link_id>" % (link_id + "x"))
        draft.append("    <node_a>%s</node_a>" % node_b)
        draft.append("    <node_b>%s</node_b>" % node_a)
        draft.append("    <technique>LK_FIBRE_TWO_WAY</technique>")
        draft.append("  </edge>")
    draft.append("</topology_draft>")
    _write_text(out / "topology_drafts.xml", "\n".join(draft))

    # ---- workbook ---------------------------------------------------------
    live_sheet = [["WORKBOOK_KEY", sheet_key, ""],
                  ["SECTION", "CLASS_CEILING", ""]]
    for osc_class in OSC_CLASSES:
        live_sheet.append([osc_class, str(ceilings[osc_class]), "ceiling weight"])
    live_sheet.append(["SECTION", "NODE_CAP", ""])
    live_sheet.append(["NODE_WEIGHT_CAP", str(node_cap_num), str(node_cap_den)])
    live_sheet.append(["SECTION", "UNCERTAINTY_COMPONENTS", ""])
    for osc_id, node, osc_class in OSC_LAYOUT:
        for index, term in enumerate(UNCERTAINTY_TERMS):
            live_sheet.append([osc_id, term, str(mint["uncertainty_terms"][osc_id][index])])
    draft_sheet = [["WORKBOOK_KEY", draft_key, ""],
                   ["SECTION", "CLASS_CEILING", ""]]
    for osc_class in OSC_CLASSES:
        draft_sheet.append([osc_class, str(ceilings[osc_class] * 2), "superseded"])
    draft_sheet.append(["SECTION", "NODE_CAP", ""])
    draft_sheet.append(["NODE_WEIGHT_CAP", "1", "2"])
    draft_sheet.append(["SECTION", "UNCERTAINTY_COMPONENTS", ""])
    for osc_id, node, osc_class in OSC_LAYOUT:
        for index, term in enumerate(UNCERTAINTY_TERMS):
            draft_sheet.append([osc_id, term,
                                str(mint["uncertainty_terms"][osc_id][index] + 90)])
    # The workbook lists its sheets in revision order, so which of the two the
    # interval works to lands in whichever position its revision falls in.
    pages = sorted([(live_revision, live_sheet), (draft_revision, draft_sheet)])
    write_xlsx(out / "timing_network_workbook.xlsx",
               {"REV_R%d" % revision: rows for revision, rows in pages})

    # ---- signed memo ------------------------------------------------------
    memo_lines = [
        "SIGNED CALIBRATION AND CONTROL MEMO",
        "interval %s" % label,
        "",
        "The four control values below are issued by the timing desk and are",
        "not restated in any plain text working paper.",
        "",
        "OSC_WEIGHT_CAP_NUMERATOR = %d" % cap_num,
        "OSC_WEIGHT_CAP_DENOMINATOR = %d" % cap_den,
        "CAP_SWEEP_BUDGET = %d" % sweep_budget,
        "HISTORY_MINIMUM_EPOCHS = %d" % history_minimum,
        "",
        "CABLE DELAY AUDIT REGISTER",
        "link report revision delay_a_ns delay_b_ns status",
    ]
    for row in ledger_rows:
        memo_lines.append("%s %s %d %d %d %s" % (
            row["link_id"], row["report_id"], row["revision"],
            row["delay_a_ns"], row["delay_b_ns"], row["status"]))
    for row in supplement_rows:
        memo_lines.append("%s %s %d %d %d %s" % (
            row["link_id"], row["report_id"], row["revision"],
            row["delay_a_ns"], row["delay_b_ns"], row["status"]))
    for link_id, node_a, node_b, technique, uncertainty in LINK_LAYOUT:
        memo_lines.append("%s path %s to %s technique %s uncertainty %d ps" % (
            link_id, node_a, node_b, technique, uncertainty))
    for osc_id, node, osc_class in OSC_LAYOUT:
        memo_lines.append("%s housed at %s class %s" % (osc_id, node, osc_class))
    for epoch in range(1, INTERVAL_EPOCHS + 1):
        memo_lines.append("grid epoch %d instant %d" % (epoch, grid[epoch - 1]))
    for revision in REGISTER_REVISIONS:
        for node in NODES:
            memo_lines.append("register %s node %s declared %d ps" % (
                revision, node, mint["declared"][revision][node]))
    write_pdf(out / "network_calibration_memo.pdf", memo_lines)

    # ---- redundant stores -------------------------------------------------
    write_sqlite(out / "reference_store.sqlite", {
        "link_register": (["link_id", "node_a", "node_b", "technique",
                           "published_uncertainty_ps"],
                          [(r["link_id"], r["node_a"], r["node_b"], r["technique"],
                            str(r["published_uncertainty_ps"])) for r in link_rows]),
        "oscillator_catalogue": (["osc_id", "node_id", "osc_class", "status"],
                                 [(r["osc_id"], r["node_id"], r["osc_class"], r["status"])
                                  for r in osc_rows]),
    })
    write_sqlite(out / "network_audit.db", {
        "session_audit": (["session_id", "link_id", "lock_state", "acq_time_s"],
                          [(r["session_id"], r["link_id"], r["lock_state"],
                            str(r["acq_time_s"])) for r in log["sessions"][:400]]),
        "withdrawal_audit": (["session_id", "withdrawn_at_s", "authorised_by"],
                             [(r["session_id"], str(r["withdrawn_at_s"]),
                               r["authorised_by"]) for r in log["withdrawn"]]),
    })

    # ---- maintenance and targets -----------------------------------------
    maintenance = []
    for index, node in enumerate(NODES):
        maintenance.append({
            "window_id": "mw_%02d" % (index + 1),
            "node_id": node,
            "opens_epoch_s": grid[(index * 2) % INTERVAL_EPOCHS] - 1800,
            "closes_epoch_s": grid[(index * 2) % INTERVAL_EPOCHS] + 1800,
            "activity": "receiver firmware refresh",
        })
    _write_jsonl(out / "maintenance_window_log.ndjson", maintenance)

    _write_text(out / "dissemination_targets.json", canonical_json({
        "interval": label,
        "targets": [{"node_id": node,
                     "target_label": "tg_%s" % node[3:],
                     "service": "array timing feed"} for node in NODES],
    }).rstrip("\n"))

    # ---- realisation, first pass -----------------------------------------
    realisation_rows = []
    for epoch in range(1, INTERVAL_EPOCHS + 1):
        realisation_rows.append({
            "epoch_index": epoch,
            "realisation_ps": 0,
            "source": "PS_CAESIUM_PRIMARY",
        })
    _write_table(out / "primary_standard_realisation.csv",
                 ["epoch_index", "realisation_ps", "source"], realisation_rows, ",")

    # ---- prose ------------------------------------------------------------
    _emit_documents(out, label, profile, sheet_key)

    # ---- realisation, second pass ----------------------------------------
    #
    # The steering outcome is a property of the interval, not a constant, so
    # the realisation the desk publishes is written once the free scale of
    # this interval is known.
    data = load_all(out)
    t01 = stage_t01_readings(data)
    t02 = stage_t02_calibration(data, t01)
    t03 = stage_t03_sense(data, t01, t02)
    graph = stage_t04_graph(data)
    offsets = stage_t05_offsets(data, t01, t03, graph)
    series = stage_t06_series(data, graph, offsets)
    prediction = stage_t07_prediction(data, graph)
    raw = stage_t08_weights(data, prediction)
    capping = stage_t09_capping(data, raw)
    ensemble = stage_t10_ensemble(data, series, prediction, capping)

    decision = data["policies"]["steer_decision_epoch"]
    if profile == "settled":
        departure = 260000
    elif profile == "strained":
        departure = 380 if seed == CHALLENGE_SEED else 175000
    else:
        departure = None
    realisation_rows = []
    for epoch in range(1, INTERVAL_EPOCHS + 1):
        entry = ensemble[epoch]
        if entry["state"] != "EP_POPULATED":
            value = ""
        else:
            value = signed(half_even(entry["value"]) - (epoch * 37))
        if epoch == decision:
            if departure is None:
                value = ""
            else:
                value = signed(half_even(ensemble[decision]["value"]) - departure)
        realisation_rows.append({
            "epoch_index": epoch,
            "realisation_ps": value,
            "source": "PS_CAESIUM_PRIMARY" if value != "" else "PS_UNAVAILABLE",
        })
    _write_table(out / "primary_standard_realisation.csv",
                 ["epoch_index", "realisation_ps", "source"], realisation_rows, ",")

    # ---- worked vectors ---------------------------------------------------
    vectors = {
        "note": "small worked values a solver can check an implementation against",
        "half_even_examples": [
            {"input": "5/2", "written": signed(half_even(Fraction(5, 2)))},
            {"input": "7/2", "written": signed(half_even(Fraction(7, 2)))},
            {"input": "-5/2", "written": signed(half_even(Fraction(-5, 2)))},
            {"input": "-1/2", "written": signed(half_even(Fraction(-1, 2)))},
        ],
        "truncate_toward_zero_examples": [
            {"input": "9/4", "written": signed(trunc_zero(Fraction(9, 4)))},
            {"input": "-9/4", "written": signed(trunc_zero(Fraction(-9, 4)))},
        ],
        "phase_examples": [
            {"frequency_atto": 10000, "steps": 1, "picoseconds": ratio(phase_ps(Fraction(10000), 1))},
            {"frequency_atto": 625, "steps": 4, "picoseconds": ratio(phase_ps(Fraction(625), 4))},
        ],
        "slope_examples": [
            {"delta_ps": 5400, "delta_steps": 6, "frequency_atto": ratio(slope_atto(Fraction(5400), 6))},
        ],
        "ratio_places": PLACES,
    }
    _write_text(out / "unit_test_vectors.json", canonical_json(vectors).rstrip("\n"))

    # Worked cases for stages T01 to T03. The values are invented for the
    # demonstration and belong to no link and no epoch of this interval, so a
    # reader can check an implementation against them without any of them
    # being a row of the publication.
    worked = [
        {"case": "WC_SENSE_A_MINUS_B",
         "note": "demonstration values, no row of this interval",
         "technique": "LK_FIBRE_TWO_WAY", "raw_offset_ps": 1250000,
         "delay_a_ns": 640, "delay_b_ns": 415, "correction_ps": 225000,
         "corrected_ps": 1025000, "sense": "SENSE_A_MINUS_B",
         "difference_ps": 1025000},
        {"case": "WC_SENSE_B_MINUS_A",
         "note": "demonstration values, no row of this interval",
         "technique": "LK_GNSS_PPP", "raw_offset_ps": -318400,
         "delay_a_ns": 208, "delay_b_ns": 331, "correction_ps": -123000,
         "corrected_ps": -195400, "sense": "SENSE_B_MINUS_A",
         "difference_ps": 195400},
        {"case": "WC_EFFECTIVE_EPOCH_TIE",
         "note": "two reports share an effective epoch; the smaller revision governs",
         "candidate_revisions": [3, 4], "applicable_revision": 3,
         "delay_a_ns": 500, "delay_b_ns": 500, "correction_ps": 0},
        {"case": "WC_NO_APPLICABLE_REPORT",
         "note": "every report of the link takes effect after the reading",
         "report_id": "REPORT_NONE", "status": "CAL_ABSENT",
         "correction_ps": 0, "corrected_ps": 4096},
        {"case": "WC_WINDOW_LOWER_EDGE",
         "note": "a reading exactly on the lower edge belongs to the epoch",
         "offset_from_instant_s": -5400, "attributed": True},
        {"case": "WC_WINDOW_UPPER_EDGE",
         "note": "a reading exactly on the upper edge belongs to no epoch",
         "offset_from_instant_s": 5400, "attributed": False,
         "drop_reason": "DR_OUTSIDE_INTERVAL"},
    ]
    _write_jsonl(out / "sample_worked_records.jsonl", worked)

    return {
        "profile": profile,
        "interval": label,
        "sheet_key": sheet_key,
        "sessions": len(log["sessions"]),
        "withdrawn": len(log["withdrawn"]),
        "archive_rows": len(archive),
        "local_rows": len(local),
        "reports": len(ledger_rows) + len(supplement_rows),
        "sweep_budget": sweep_budget,
        "history_minimum": history_minimum,
        "files": len(list(out.iterdir())),
    }


# --------------------------------------------------------------------------
# the working papers
#
# These are the normative documents the desk keeps. Every rule the graded
# artifacts depend on is written here, once in its own stage specification
# and once in the numbered footgun list.
# --------------------------------------------------------------------------
def _emit_documents(out: Path, label: str, profile: str, sheet_key: str) -> None:
    _write_text(out / "readme_first.txt", """
TIMING NETWORK WORKING PAPERS - READ THIS FIRST

This directory is one publication interval of the array timing network as the
desk left it. File names describe the role of a paper, not its contents, so
open a paper before assuming what is in it.

Start at network_contract_overview.md. It names the thirteen stages and the
specification paper for each one. The stage papers are normative; everything
else in this directory supports them.

Two control papers are not plain text and both are load bearing.
timing_network_workbook.xlsx is a real spreadsheet with two sheets, one live
and one superseded draft, and network_calibration_memo.pdf is the signed memo.
Four control values appear in the memo and nowhere else, and the class ceiling
weights, the node weight cap and the uncertainty component table appear in the
live workbook sheet and nowhere else. A reading of this interval taken from the
plain text papers alone will not converge.

Three papers in this directory are superseded and are kept only for audit.
data_lineage.md names them and says what each one is superseded by.

known_traps_and_footguns.md lists every reading of these papers that a careful
engineer plausibly takes and that this interval does not support, with the
condition in the corpus that defeats each one. unit_test_vectors.json and
sample_worked_records.jsonl carry worked arithmetic on invented values, so an
implementation can be checked against them; neither holds a value taken from
this interval. Nothing in this interval is
concealed. The work is in getting all of it right at once.
""".strip())

    _write_text(out / "corpus_sentinel_note.txt", """
SENTINEL NOTE ON THE COVERAGE OF THIS INTERVAL

This interval is an acquisition profile the desk calls %s. It does not
exercise every branch the stage papers define, and a reading of the network
that concludes a rule is absent because this interval never triggers it will
be wrong on the next interval.

Branches this profile is known to leave quiet:

  1. An epoch at which no oscillator carries a deviation. Stage T10 defines
     the void epoch state and this profile does not produce one.
  2. The unsatisfiable oscillator cap of stage T09, which arises when every
     weighted oscillator sits above the cap and there is nobody left to take
     the redistributed mass.
  3. The steering outcome for an interval whose decision epoch carries no
     primary realisation, defined in stage T11.
  4. A calibration report set in which the applicable report is the one the
     supplement carries rather than the one the ledger carries, at a link
     whose ledger reports all take effect after the interval closes.

The program the desk keeps has to handle all four. They are defined in the
stage papers whether or not this interval reaches them.
""".strip() % profile)

    _write_text(out / "network_contract_overview.md", """
# Publication contract for interval %s

The array is phase coherent only while every site works to one time scale.
Each publication interval the desk recomputes that scale from the oscillator
population, steers it onto the primary caesium realisation and publishes the
offset of every site from it. The previous publication of this interval was
withdrawn. This directory holds the working papers and the interval has to be
recomputed from them.

## The thirteen stages

| stage | subject | specification |
| --- | --- | --- |
| T01 | reading canonicalisation | spec_stage_t01_reading_canonicalisation.md |
| T02 | delay calibration | spec_stage_t02_delay_calibration.md |
| T03 | measurement sense | spec_stage_t03_measurement_sense.md |
| T04 | link graph and spanning tree | spec_stage_t04_link_graph.md |
| T05 | node offsets and dead time | spec_stage_t05_node_offsets.md |
| T06 | oscillator deviation series | spec_stage_t06_oscillator_series.md |
| T07 | frequency prediction | spec_stage_t07_frequency_prediction.md |
| T08 | dispersion and raw weight | spec_stage_t08_dispersion_and_weight.md |
| T09 | weight capping | spec_stage_t09_weight_capping.md |
| T10 | free ensemble scale | spec_stage_t10_ensemble_scale.md |
| T11 | steering | spec_stage_t11_steering.md |
| T12 | dissemination and uncertainty | spec_stage_t12_dissemination.md |
| T13 | reports and manifest | spec_stage_t13_reports_and_manifest.md |

Each stage freezes a value the next stage consumes. The canonical reading is
frozen at T01, the spanning tree edge set at T04, the prediction frequency and
its anchor at T07, the weight vector at T09 and the steering step at T11. A
stage never revisits a value an earlier stage froze.

## The pervasive rule

Every quantity in the chain is carried as an exact rational. No stage rounds,
truncates or converts to a binary floating point number. Rounding is applied
once, at the moment a value is written into an artifact, under the rule
rounding_policy.yaml states. Two stages carry a rounded value forward instead,
and each says so and why: the published dispersion of stage T08, and the weight
grid the capping passes of stage T09 place the vector on.

## Units

Every recorded and published time quantity is a whole number of picoseconds
unless a paper says otherwise. Delay calibration reports publish nanoseconds.
Frequency is carried and published in parts in ten to the eighteenth. One grid
step at one part in ten to the eighteenth is exactly 864 ten thousandths of a
picosecond.
""".strip() % label)

    _write_text(out / "spec_stage_t01_reading_canonicalisation.md", """
# T01 reading canonicalisation

## Input

comparison_session_log.csv holds every acquisition attempt the receivers made
during the interval. session_withdrawal_journal.tsv names the acquisition
sessions the desk has withdrawn. link_register.csv is the frozen register of
links. epoch_grid_policy.yaml holds the grid and attribution parameters.

## The publication grid

The interval carries thirty grid epochs, numbered 1 to 30. The instant of
epoch k is

    interval_start_epoch_s + (k - 1) * grid_step_seconds + grid_instant_offset_s

taking interval_start_epoch_s and grid_step_seconds from network_config.json
and grid_instant_offset_s from epoch_grid_policy.yaml.

## Attribution

A row is attributed to epoch k when its acq_time_s satisfies

    instant(k) - attribution_tolerance_s  <=  acq_time_s  <  instant(k) + attribution_tolerance_s

The window is half open. The lower edge belongs to the epoch and the upper
edge does not. The tolerance is smaller than half a grid step, so no row is
attributable to two epochs. A row attributable to no epoch is set aside; it is
never moved to the nearest epoch.

## Setting rows aside

The predicates below are ordered. A row is tested against them in this order
and the first one that matches is the reason recorded for it. A row is never
recorded twice.

    1. DR_OUTSIDE_INTERVAL   the row is attributable to no grid epoch
    2. DR_SESSION_WITHDRAWN  session_id appears in the withdrawal journal
    3. DR_LINK_UNREGISTERED  link_id is absent from link_register.csv
    4. DR_SELF_LOOP          the link register gives the link the same node
                             on both sides
    5. DR_NO_LOCKED_ATTEMPT  the cluster the row belongs to holds no attempt
                             in lock state LOCK_HELD

Predicates 1 to 4 are decided row by row. Predicate 5 is decided once the
surviving rows have been grouped, and when it fires it sets aside every
remaining row of that cluster.

## Clusters and the canonical reading

The surviving rows are grouped into clusters by the pair (link_id,
epoch_index). The canonical reading of a cluster is chosen from the rows of
that cluster whose lock_state is LOCK_HELD. Rows in any other lock state are
never eligible, whatever their attempt number.

Among the eligible rows the canonical reading is the one with the greatest
attempt_no. Two receivers can report the same attempt number for one cluster.
When the greatest attempt number is held by more than one row, the row with
the smallest absolute difference between acq_time_s and the instant of the
epoch wins, and if that is still equal the row with the earlier acq_time_s
wins.

## Output

The canonical reading of every surviving cluster, carrying its session, its
receiver, its attempt number, its acquisition time, its raw offset and the
number of rows the cluster held before selection. Every set aside row with the
reason recorded for it.
""".strip())

    _write_text(out / "spec_stage_t02_delay_calibration.md", """
# T02 delay calibration

## Input

delay_calibration_ledger.csv and delay_calibration_supplement.psv. The
supplement does not replace the ledger. Both are reports of the same
calibration register, and the report set of a link is the union of what the
two papers hold for it.

## Selecting the applicable report

A report governs a reading when its effective_epoch_s is on or before the
acq_time_s of that reading. Among the reports that govern a reading, the
applicable one is the one with the greatest effective_epoch_s.

Two reports can carry the same effective_epoch_s. When that happens the report
with the smaller revision number is the applicable one. The register issues a
signed report first and registers its provisional restatement afterwards under
the next revision, so the smaller revision is the settled reading and the
larger one is the restatement the desk has not adopted.

The status of a report records how far it has been through review. It takes no
part in selecting the applicable report; effective epoch and revision select
it, and a report is on the register because the desk put it there.

issued_epoch_s records when a report reached the desk. It orders nothing. A
report issued later can take effect earlier, and a report issued last can take
effect after the interval closes and govern no reading in it.

A link whose reports all take effect after the reading has no applicable
report. Its correction is zero, its report is recorded as REPORT_NONE and its
status is recorded as CAL_ABSENT.

## Applying the correction

The ledger publishes delay_a_ns and delay_b_ns in nanoseconds. Every reading
is in picoseconds. The correction is

    correction_ps = (delay_a_ns - delay_b_ns) * 1000

and the corrected reading is

    corrected_ps = raw_offset_ps - correction_ps

## Output

For every canonical reading, the applicable report, its revision, its status,
its effective epoch, the correction in picoseconds and the corrected reading.
""".strip())

    _write_text(out / "spec_stage_t03_measurement_sense.md", """
# T03 measurement sense

## Input

The corrected readings of T02 and link_register.csv.

## The rule

A link records its comparison in the sense its technique uses, and the two
senses are not interchangeable. link_technique_reference.txt gives the sense
of every technique. A reading on a link whose technique records
SENSE_A_MINUS_B already expresses the clock of node_a minus the clock of
node_b. A reading on a link whose technique records SENSE_B_MINUS_A expresses
the opposite and its sign is inverted to bring it to the A minus B convention.

    difference_ps = corrected_ps                    when SENSE_A_MINUS_B
    difference_ps = 0 - corrected_ps                when SENSE_B_MINUS_A

node_a and node_b are the columns of link_register.csv and are not reordered.

## Output

One signed difference per canonical reading, in the A minus B convention.
""".strip())

    _write_text(out / "spec_stage_t04_link_graph.md", """
# T04 link graph, components and the spanning tree

## Input

link_register.csv, node_register_frozen.csv at the frozen revision, and the
hub node network_config.json names.

## Usable links

A link is usable when both of its nodes are registered at the frozen register
revision and the two are different nodes. A link with the same node on both
sides and a link naming a node the register does not carry are both dropped
here and take no part in the graph.

## Components

The usable links partition the registered nodes into connected components. A
node with no usable link is a component of one node. Components are ordered by
the lexicographically smallest node each one holds and are identified cmp_01,
cmp_02 and so on in that order.

## Roots

The component that holds the hub node is anchored, its role is ROLE_ANCHORED
and its root is the hub node. Every other component is unanchored, its role is
ROLE_UNANCHORED and its root is the lexicographically smallest node in it.

## The spanning tree

The link graph carries cycles, and two links can join the same pair of nodes.
The offsets of a component are computed along one acyclic tree and not along
the whole graph.

The tree of a component is grown from its root. At each step the candidate
links are the usable links of that component with exactly one end already
reached.

**What the admission minimises.** The uncertainty a node carries is not the
uncertainty of the one link that reaches it. It is the uncertainty of the whole
path the tree gives it back to the root, which is the quantity stage T12
publishes as the path terms of that node's budget. The admission works on that
accumulated figure and not on the link in front of it.

The path cost of a node is the sum of published_uncertainty_ps over the tree
edges between the root of its component and that node. The root has a path cost
of zero. The admission cost of a candidate is

    admission cost = the path cost of its reached end
                     plus its own published_uncertainty_ps

which is the path cost the unreached end would take if that candidate were
admitted. The link admitted is

    the candidate with the smallest admission cost;
    ties on that go to the candidate whose technique has the smaller rank in
    link_technique_reference.txt;
    ties on that go to the candidate with the lexicographically smaller
    link_id.

The tree this grows is not in general the tree the smallest published
uncertainty at each step grows. A cheap link hanging off a distant node loses
to a dearer link hanging off a near one, and the two readings admit different
links on this network.

The admitted link makes the unreached end a child of the reached end, and the
path cost of that end is the admission cost of the link that reached it. Growth
stops when no candidate remains. Every usable link of the component that the
tree did not admit is recorded as an excluded link.

A link is admitted or excluded on the register alone. Whether it carries a
reading at any epoch plays no part in growing the tree.

## Output

Per component: its identifier, its role, its root, its member nodes, its tree
edges in the order they were admitted, and its excluded link identifiers in
ascending order.
""".strip())

    _write_text(out / "spec_stage_t05_node_offsets.md", """
# T05 node offsets and dead time

## Input

The signed differences of T03 and the spanning trees of T04.

## The path sum

The offset of a node is its clock minus the clock of the root of its
component, carried along the tree path from the root to that node. For a tree
edge whose parent is p and whose child is c, taken at epoch k,

    when the register gives node_a = p, that edge contributes  0 - difference_ps
    when the register gives node_a = c, that edge contributes  difference_ps

and the offset of the node is the sum of the contributions of the edges on its
path. The root of a component has an empty path and an offset of zero at every
epoch.

## Dead time

An edge on the path of a node can carry no canonical reading at an epoch,
because every attempt was set aside at T01. When that happens the node has no
offset at that epoch. The offset is not interpolated, not carried forward from
another epoch and not filled from another link. It is absent, and the absence
is recorded.

Two absences are recorded here. A tree edge with no canonical reading at an
epoch is recorded with scope SCOPE_LINK. A node whose path holds such an edge
at an epoch is recorded with scope SCOPE_NODE, naming the first edge on its
path, taken from the root outward, that is missing.

The node record stands for every oscillator at that node, so the oscillators
of a node that is out take no record of their own. Stage T06 records an
oscillator only for the local monitor case.

## Output

An offset or an absence for every registered node at every epoch, and the dead
time records.
""".strip())

    _write_text(out / "spec_stage_t06_oscillator_series.md", """
# T06 oscillator deviation series

## Input

The node offsets of T05, oscillator_catalogue.csv,
node_register_frozen.csv at the frozen revision and local_comparison_log.psv.

## The reference oscillator

Each node realises its clock with the oscillator the frozen register revision
names in reference_oscillator. The deviation of that oscillator at an epoch is
the offset of its node at that epoch.

The register carries several revisions and they do not agree. Two nodes change
their reference oscillator at a later revision. The revision that applies is
the one network_config.json freezes for this interval, and no other.

## Other oscillators

Every other oscillator at a node is measured against that node's reference
oscillator by the local monitor. Its deviation at an epoch is

    node offset at that epoch + local_offset_ps at that epoch

taken from the row of local_comparison_log.psv for that oscillator and epoch.
A row whose monitor_flag is not MON_VALID does not carry a measurement, and
neither does a missing row. In either case the oscillator has no deviation at
that epoch and the absence is recorded with scope SCOPE_OSCILLATOR.

That record covers the local monitor and nothing else. An oscillator whose node
carries no offset at an epoch also has no deviation there, and it takes no
SCOPE_OSCILLATOR record: the SCOPE_NODE record of stage T05 already says the
whole node is out at that epoch, and the ledger states each absence once. So a
SCOPE_OSCILLATOR record appears only where the node does carry an offset and
the oscillator's own monitor row is missing or is flagged other than
MON_VALID, which is why no reference oscillator ever takes one.

## Flags

A deviation carries SER_MEASURED when its node is in the anchored component,
and SER_UNANCHORED when its node is in an unanchored component, where the
deviation is against that component's own root and not against the hub. An
oscillator with no deviation at an epoch carries SER_ABSENT, and SER_ABSENT
takes precedence over SER_UNANCHORED.

## Output

A deviation or an absence for every catalogued oscillator at every epoch.
""".strip())

    _write_text(out / "spec_stage_t07_frequency_prediction.md", """
# T07 frequency prediction

## Input

prior_interval_deviations.psv, weighting_policy.yaml, the history minimum from
network_calibration_memo.pdf, oscillator_catalogue.csv and the components of
T04.

## The history window

The archive holds twenty four epochs of the previous interval, numbered 1 to
24. The history window is the last history_window_epochs of them, so it runs
from 24 - history_window_epochs + 1 to 24 inclusive.

An archived deviation counts as valid only when its quality_flag equals
valid_archive_flag. Any other flag is not a measurement and takes no part in
anything below.

## Exclusions

An oscillator is excluded from the ensemble for the first of these that
applies, in this order:

    EX_DECOMMISSIONED    oscillator_catalogue.csv gives it status
                         OS_DECOMMISSIONED
    EX_NO_ARCHIVE        the archive holds no row for it at all
    EX_SHORT_HISTORY     the number of valid deviations in its history window
                         is below the history minimum the memo publishes
    EX_UNANCHORED_NODE   its node is in an unanchored component

An oscillator carrying exactly the history minimum is not excluded. The
comparison is strict.

## The frequency

The prediction is a straight line through the first and the last valid
deviation of the history window. It is not a least squares fit, and no
intermediate point moves it.

    frequency = slope in parts in ten to the eighteenth of the line through
                (first valid window epoch, its deviation) and
                (last valid window epoch, its deviation)

with one grid step at one part in ten to the eighteenth being exactly 864 ten
thousandths of a picosecond. The anchor of the prediction is the last valid
deviation of the window and the epoch it was taken at.

The frequency is carried as an exact rational. The whole number written into
the prediction book is a rendering of it and is never the value the following
stages use.

## Predicted deviation

The prediction of an oscillator at an archived epoch n is

    anchor_deviation + phase(frequency, n - anchor_epoch)

and at grid epoch k of this interval it is

    anchor_deviation + phase(frequency, 24 + k - anchor_epoch)

## Output

For every catalogued oscillator: the window bounds, the number of valid
deviations in it, whether it is included, the exclusion reason when it is not,
and for an included oscillator the anchor and the frequency.
""".strip())

    _write_text(out / "spec_stage_t08_dispersion_and_weight.md", """
# T08 residual dispersion and raw weight

## Input

The predictions of T07, weighting_policy.yaml and the class ceiling weights
from the live sheet of timing_network_workbook.xlsx.

## Residuals

For an included oscillator, at every valid epoch of its history window,

    residual = archived deviation - predicted deviation at that epoch

using the exact frequency of T07. The residual at the anchor epoch is zero and
it counts.

## Dispersion

The dispersion of an oscillator is the mean of the absolute values of its
window residuals, rounded to a whole number of picoseconds by the rounding
rule. This is the first of the two places in the chain where a rounded value is
carried forward rather than only written, the other being the grid placement of
every capping pass of stage T09, and it is deliberate: the desk publishes the
dispersion as a whole picosecond and forms the weight from the number it
published, so a reader of the published table can reproduce the weight from
it.

## Raw weight

    raw weight = weight_scale / published dispersion

when the published dispersion is not zero, and the weight source is
WS_DISPERSION.

A prediction can reproduce a window exactly, and then the published dispersion
is zero. Such an oscillator is not dropped and its weight is not unbounded. It
takes the ceiling weight of its class from the live workbook sheet, and the
weight source is WS_CLASS_CEILING.

## Output

For every included oscillator: its valid count, its published dispersion, its
weight source and its raw weight.
""".strip())

    _write_text(out / "spec_stage_t09_weight_capping.md", """
# T09 weight capping

## Input

The raw weights of T08, capping_policy.yaml, the oscillator cap and the sweep
budget from network_calibration_memo.pdf, and the node weight cap from the
live workbook sheet.

## The two caps

Let W be the sum of the raw weights of the included oscillators. W is computed
once, from the raw weights, and does not move afterwards.

    oscillator cap = OSC_WEIGHT_CAP_NUMERATOR / OSC_WEIGHT_CAP_DENOMINATOR * W
    node cap       = NODE_WEIGHT_CAP numerator / denominator * W

Both caps are absolute weights, fixed for the interval by W.

## Redistribution

Capping is mass preserving. The weight a capped holder gives up is handed to
the holders that are still below the cap, in proportion to the weight each of
them already holds. It is never discarded. The sum of the weight vector after
a pass equals the sum before it, and it equals it exactly: the placement of the
vector on the published grid is closed onto one holder so that the grid costs
the vector none of its mass. The passes below say which holder.

## The three passes, in this order

The order of the passes changes the answer, and this is the order.

**The published weight grid.** Every weight the capping works on sits on the
grid weight_places decimal places give. The raw weight of stage T08 is placed
on that grid before the first pass, and every pass leaves the vector on it. The
raw weight the weight book publishes is the T08 formula as it stands; the value
the capping starts from is that weight placed on the grid.

**First pass, the oscillator cap. A damped fixed point, not a solve.** An
oscillator is an offender when its weight is strictly above the cap; one
sitting exactly on the cap is not an offender and takes a share of the excess
like any other holder. One pass works out where a full step would put the
vector: every offender sits exactly on the cap, the total excess is collected,
and it is handed to the oscillators at or below the cap in proportion to the
weight they hold. The desk does not take that step. It moves the whole vector a
fraction of the way toward that target,

    new weight = weight + damping * (target - weight)

with damping the ratio damping_numerator over damping_denominator that
weighting_policy.yaml publishes, applied to every oscillator and not only to
the offenders. The result is then placed back on the published grid, rounding half to even
at weight_places decimal places as the rounding policy states, and the next
pass starts from the placed vector. This is a carried rounding, the second and last
in the chain after the published dispersion of stage T08, and it is what makes
the passes depend on one another.

**Placement is mass preserving too.** Placing each weight on the grid on its
own moves the total: half to even sends some weights up and some down and the
two do not cancel. The desk does not publish a weight vector whose total has
drifted away from the total the pass started with, so the pass closes that
difference rather than leaving it. Take the total of the vector before the
pass, take the total of the placed vector, and hand the whole of the difference
to one holder,

    residue = the total before the pass minus the total of the placed vector

and that holder takes its placed weight plus the residue. The holder is not
the same one every pass. Closing the residue onto the greatest receiver every
time walks that one holder's published weight away from the vector the passes
produced, so the desk hands the carry to the receiving holder that has carried
it the fewest times so far in this interval, a tie going to the greatest weight
after placement and then to the lexicographically smallest oscillator
identifier. The count opens at zero for the interval and runs across every pass
of all three phases, so which holder closes a pass depends on what the passes
before it did, and a pass cannot be worked out from the vector it starts from
alone. An offender never carries the residue. Both totals are whole numbers
of grid units, so the residue is one too and the vector stays on the grid. The
pass therefore preserves the total exactly, which is what lets the sum of the
published weight vector be compared with the total the two caps were taken
from.

This matters, and it is why the pass is written out rather than solved. The map
this pass iterates has a fixed point with a closed form, in which every
over-cap oscillator sits at the cap and every other one is scaled by a single
common factor. That fixed point is not what the desk publishes. What it
publishes is the vector after the passes the budget allows, damped and placed
on the grid at the end of each one, which no closed form gives.

Pass again. Stop when no oscillator is above the cap, and record SW_SETTLED.
Stop when the number of passes already run equals CAP_SWEEP_BUDGET and an
oscillator is still above the cap, and record SW_BUDGET_EXHAUSTED, publishing
the vector as the budget left it. Stop when every oscillator is above the cap,
so that there is nobody to take the excess, and record SW_CAP_UNSATISFIABLE,
publishing the vector unchanged. Redistribution can push a holder over the cap
that was under it before, so the number of offenders can rise from pass to
pass; that is the mechanism working, not a fault.

The residual of a pass is the sum, over every oscillator, of the absolute
difference between its weight after the pass and its weight before it.

The terminal residual the weight book publishes is the residual of the third
pass, which is the last pass of the stage. A pass that finds no offender runs
no sweep and moves nothing, so its residual is zero and the terminal residual
is zero, whatever the passes before it moved.

**Second pass, the node cap.** One pass, not a sweep, and it is not damped: the
node cap is taken in full. Sum the weights of the oscillators at each node.
Every node whose sum is above the node cap has all of its oscillators scaled by
the ratio of the node cap to that sum, so the node sits exactly on its cap. The
excess collected from the offending nodes is handed to the oscillators at the
nodes that were not offending, in proportion to the weight each of them holds
after the first pass. The result is placed back on the published grid, as every
pass does, and the residue of that placement is closed onto one receiving
oscillator under the same carry count the first pass keeps, exactly as the
first pass closes it. The node pass is one of the passes the count runs over. When every node is above the node cap the pass records
SW_CAP_UNSATISFIABLE and changes nothing.

**Third pass, one further oscillator sweep.** Exactly one damped pass of the
oscillator cap, run over the vector the node cap produced, with the same cap
value, the same damping and the same grid. One pass, whatever the budget says,
and no node cap pass follows it.

## Output

The raw weight, the weight after the first pass, the weight after the second
pass and the final weight of every included oscillator, the two cap values, the
outcome of each pass, the terminal residual, the damping and the grid, and one
trace record per pass naming the phase PH_OSC_CAP, PH_NODE_CAP or
PH_FINAL_SWEEP, the offenders it acted on, the excess it moved, the number of
holders that took it and the residual of that pass.
""".strip())

    _write_text(out / "spec_stage_t10_ensemble_scale.md", """
# T10 the free ensemble scale

## Input

The deviation series of T06, the predictions of T07 and the final weights of
T09.

## The residual of an oscillator in this interval

At grid epoch k, for an oscillator that carries a deviation at k and holds a
final weight,

    residual(k) = deviation(k) - prediction(k)

with the prediction taken from T07 at the exact frequency. The residual is an
exact rational and is not rounded here.

## The free scale

    free scale(k) = sum over contributing oscillators of weight * residual(k)
                    divided by
                    sum over contributing oscillators of weight

An oscillator contributes at epoch k only when it carries a deviation at k.
The denominator is the sum of the weights of the oscillators that contribute
at that epoch. It is not the total weight of the ensemble, and it is
recomputed at every epoch.

The whole quotient is formed first and rounded once when it is written.
Rounding each term of the numerator to a picosecond before summing gives a
number that is right at every term and wrong in the total, and it is not what
this stage computes.

## The void epoch

An epoch at which no oscillator contributes has no free scale. Its state is
EP_ENSEMBLE_VOID, its free scale is written as an empty field and its
denominator is zero. Every other epoch has state EP_POPULATED.

## Output

For every epoch: its state, the number of contributing oscillators, the
denominator weight and the free scale.
""".strip())

    _write_text(out / "spec_stage_t11_steering.md", """
# T11 steering

## Input

The free scale of T10, steering_policy.yaml and
primary_standard_realisation.csv.

## The departure

At the decision epoch the policy names,

    departure = free scale at the decision epoch
                minus the primary realisation at the decision epoch

The realisation file leaves the value empty at an epoch the primary standard
did not cover. When the decision epoch itself is empty, or when the decision
epoch is void, there is no departure, the step is zero and the outcome is
ST_NO_REALISATION.

## The step

The step is the frequency that would remove the departure over the horizon the
policy names.

    raw step = the frequency, in parts in ten to the eighteenth, whose phase
               over horizon_epochs grid steps equals the negated departure

The step the desk applies sits on the grid the policy names. The raw step is
divided by grid_atto, truncated toward zero, and multiplied back by grid_atto.
Truncation toward zero, not rounding: a raw step whose magnitude is below one
grid unit becomes zero, and the outcome is ST_TRUNCATED_TO_ZERO. Otherwise the
outcome is ST_APPLIED.

## Applying the step

The step is a frequency and its phase accumulates. The first epoch it corrects
is the epoch after the decision epoch. At the decision epoch itself the
correction is zero.

    correction(k) = phase(step, k - decision_epoch)   for k greater than the
                                                      decision epoch
    correction(k) = 0                                 otherwise

    steered scale(k) = free scale(k) + correction(k)

Both terms are exact rationals and the sum is rounded once when it is written.
A void epoch carries its correction and leaves its free scale and its steered
scale empty.

## Output

The steering plan, holding the decision epoch, the horizon, the grid, the
departure, the raw step, the applied step and the outcome; and the steered
scale at every epoch beside the free scale and the correction.
""".strip())

    _write_text(out / "spec_stage_t12_dissemination.md", """
# T12 dissemination and the uncertainty budget

## Input

The node offsets of T05, the steered scale of T11, the spanning trees of T04,
node_register_frozen.csv at the frozen revision, the uncertainty component
table on the live workbook sheet and uncertainty_budget_policy.yaml.

## The published offset

At every epoch, for every registered node,

    offset(k) = node offset(k) - steered scale(k)

carried as an exact rational and rounded once when written. A node with no
offset at an epoch, and any epoch whose steered scale is empty, gives an
absent offset with flag OFF_ABSENT. Every other offset carries OFF_PUBLISHED.

## The budget terms

The terms of a node's budget are, in this order:

    the seven uncertainty components of that node's reference oscillator,
    taken from the live workbook sheet in the order the sheet lists them;

    the declared_uncertainty_ps of that node at the frozen register revision;

    the published_uncertainty_ps of every tree edge on the path from the root
    of its component to that node, taken from the root outward.

A node at the root of its component contributes no path term.

## The two statistics

    u_combined_ps2 = the sum of the squares of the terms, in square picoseconds
    u_linear_ps    = the arithmetic sum of the terms, in picoseconds

Both are published. The combined statistic is a variance and is not reduced to
a standard deviation, because a square root of an integer is not in general an
integer and this publication carries no irrational value.

## Status

    DS_WITHHELD_UNANCHORED   the node is in an unanchored component
    DS_WITHHELD_NO_DATA      the node carries no published offset at any epoch
    DS_PUBLISHED             otherwise

The three are tested in that order.

## The mean offset

The mean offset of a node is the exact mean of its published offsets, rounded
once when written, and is written as zero for a node with no published offset.

## Output

The per epoch offsets, the budget terms and the two statistics per node, and
the dissemination ledger.
""".strip())

    _write_text(out / "spec_stage_t13_reports_and_manifest.md", """
# T13 reports, reconciliation and the manifest

## Loop closures

Every link the tree excluded still carries readings, and the difference it
records disagrees with the difference the tree implies. At every epoch where
the excluded link carries a canonical reading and both of its nodes carry an
offset,

    closure_ps = difference_ps of the excluded link
                 minus (offset of node_a minus offset of node_b)

An excluded link that never reaches that condition carries no closure and is
listed as unreconciled instead.

## Per node reports

A report is published for each of the four nodes the output artifact contract
names. It carries the node's component, role, register revision, reference
oscillator, the link identifiers on its tree path in order from the root
outward, the length of that path, the count of epochs at which it carries a
published offset, its mean offset, the two uncertainty statistics, its status
and one entry for every oscillator catalogued at it.

## The two digests

The publication manifest carries two sha256 digests.

The core digest, published as digest, runs over the bytes of the six core
artifacts concatenated in the order ordering_dependencies.yaml lists under
digest_order. That order is the order of the chain and it is not alphabetical.

The publication digest, published as publication_digest, runs over the bytes of
every other artifact, concatenated in the order the table in
output_artifact_contract.md lists them, with the manifest itself left out
because it carries the digest. The manifest is the last document written, and
it moves whenever anything else in the publication moves.

## Output

The reconciliation document, the four node reports, the two markdown reports,
the node index and the publication manifest.
""".strip())

    _write_text(out / "data_lineage.md", """
# Data lineage

Which paper feeds which stage.

| paper | stages | note |
| --- | --- | --- |
| comparison_session_log.csv | T01 | every acquisition attempt of the interval |
| session_withdrawal_journal.tsv | T01 | withdrawn acquisition sessions |
| epoch_grid_policy.yaml | T01 | grid instant and attribution tolerance |
| link_register.csv | T01 T03 T04 T12 | frozen link register |
| link_technique_reference.txt | T03 T04 | measurement sense and technique rank |
| delay_calibration_ledger.csv | T02 | delay reports |
| delay_calibration_supplement.psv | T02 | further reports of the same register |
| network_config.json | T01 T04 T06 | interval header, hub, frozen revision, workbook key |
| node_register_frozen.csv | T04 T06 T12 | node register, several revisions |
| oscillator_catalogue.csv | T06 T07 | the oscillator population |
| local_comparison_log.psv | T06 | oscillator against its node reference |
| prior_interval_deviations.psv | T07 T08 | the previous interval archive |
| weighting_policy.yaml | T07 T08 | window, valid flag, weight scale |
| network_calibration_memo.pdf | T07 T09 | history minimum, oscillator cap, sweep budget |
| timing_network_workbook.xlsx | T08 T09 T12 | class ceilings, node cap, uncertainty components |
| capping_policy.yaml | T09 | pass order and redistribution |
| steering_policy.yaml | T11 | decision epoch, horizon, grid |
| primary_standard_realisation.csv | T11 | the realisation to steer onto |
| uncertainty_budget_policy.yaml | T12 | budget terms and statistics |
| rounding_policy.yaml | all | rounding mode and places |
| ordering_dependencies.yaml | T13 | what freezes where, and the digest order |
| dissemination_targets.json | none | service labels of the sites, kept for audit |
| network_topology.xml | none | a view of the register, kept for audit |
| reference_store.sqlite | none | a copy of two registers, kept for audit |
| network_audit.db | none | a copy of the session log, kept for audit |
| maintenance_window_log.ndjson | none | site activity, kept for audit |

## Superseded papers

Three papers in this directory are superseded and take no part in the
recompute. They are kept because the audit trail needs them.

  * node_register_current.csv holds the latest register revision only. The
    interval works at the revision network_config.json freezes, which is an
    earlier one, and the two disagree about the reference oscillator of two
    nodes and about the declared uncertainty of every node. Use the frozen
    register.

  * legacy_weight_table.csv holds a fixed weight per oscillator class from a
    scheme the network retired at REG-R09. Weights come from the residual
    dispersion of the previous interval, never from this table.

  * topology_drafts.xml holds a proposed rerouting that was never
    commissioned. The graph is built from link_register.csv.

The draft sheet of the workbook is superseded in the same way. The live sheet
is the one whose key cell matches the workbook sheet key in
network_config.json, and it is not selected by its name or by its position.
""".strip())

    _write_text(out / "known_traps_and_footguns.md", """
# Known traps and footguns

Every reading below is one a careful engineer plausibly takes, and every one of
them is wrong for this network. The right reading and the paper that states it
are named beside each. Nothing here is concealed; the work is in holding all of
it at once.

 1. Taking the highest attempt number of a cluster whatever its lock state.
    Only an attempt in lock state LOCK_HELD is eligible. (T01)
 2. Taking the last row of a cluster in file order. Order in the log means
    nothing; the rule is the greatest eligible attempt number. (T01)
 3. Breaking a tie on attempt number by acquisition time. The first tie break
    is the smallest absolute offset from the epoch instant; acquisition time
    only breaks a tie that survives that. (T01)
 4. Treating the attribution window as closed at both ends. It is closed below
    and open above. (T01)
 5. Moving a row that lands in no window to the nearest epoch. It is set aside
    with DR_OUTSIDE_INTERVAL. (T01)
 6. Setting a cluster aside because a session in it was withdrawn. The journal
    withdraws sessions, not clusters; the cluster keeps its other attempts and
    only loses everything when no LOCK_HELD attempt survives. (T01)
 7. Recording more than one reason for a set aside row. The five predicates are
    ordered and the first match is the reason. (T01)
 8. Choosing the calibration report with the greatest issued_epoch_s.
    issued_epoch_s orders nothing. The applicable report is the one with the
    greatest effective_epoch_s on or before the reading. (T02)
 9. Breaking a tie on effective_epoch_s toward the larger revision. The smaller
    revision is the signed report and it wins. (T02)
10. Reading only delay_calibration_ledger.csv. The supplement carries further
    reports of the same register and they can be the applicable ones. (T02)
11. Leaving the delays in nanoseconds. The reports are nanoseconds and the
    readings are picoseconds. (T02)
12. Assuming every link records A minus B. Two of the four techniques record
    the opposite sense. (T03)
13. Growing the spanning tree in register order, or by breadth first search.
    The admitted candidate is the one with the smallest admission cost, then
    the smaller technique rank, then the smaller link identifier. (T04)
14. Breaking a tie on admission cost by link identifier alone. Technique rank
    comes first, and two links of equal cost and different technique do
    exist. (T04)
15. Rooting an unanchored component anywhere but at its lexicographically
    smallest node. (T04)
16. Dropping a link from the tree because it carries no reading. The tree is
    built from the register; readings play no part. (T04)
17. Interpolating an offset across a dead epoch, or carrying the previous
    epoch forward. Dead time is absence and stays absent. (T05)
18. Taking the reference oscillator of a node from node_register_current.csv.
    The interval works at the frozen revision. (T06)
19. Treating a monitor row flagged other than MON_VALID as a measurement. (T06)
20. Fitting a least squares line to the history window. The prediction is the
    line through the first and last valid points of the window. (T07)
21. Using this interval's own deviations to predict this interval. The
    prediction comes from the previous interval's archive. (T07)
22. Counting an archived deviation whose quality flag is not ARC_VALID. (T07)
23. Excluding an oscillator that carries exactly the history minimum. The
    comparison is strict and exactly the minimum is enough. (T07)
24. Including an oscillator whose node is in an unanchored component. (T07)
25. Forming the weight from the exact rational dispersion. The desk publishes
    the dispersion as a whole picosecond and forms the weight from what it
    published. This is one of the two carried roundings in the chain, the other
    being the weight grid of stage T09. (T08)
26. Dropping an oscillator whose dispersion is zero, or giving it an unbounded
    weight. It takes the ceiling weight of its class from the workbook. (T08)
27. Clamping a weight to the cap and discarding the excess. Capping is mass
    preserving and the excess is redistributed in proportion. (T09)
28. Running the node cap before the oscillator cap. The order is oscillator
    cap, node cap, one further oscillator sweep. (T09)
29. Iterating the oscillator cap to convergence. It runs to the sweep budget
    the memo publishes and then stops and says so. (T09)
30. Skipping the third pass, or running it to convergence. It is exactly one
    sweep. (T09)
31. Dividing the ensemble by the total weight of the ensemble. The denominator
    is the weight of the oscillators contributing at that epoch. (T10)
32. Rounding each weighted residual to a picosecond before summing. The
    quotient is formed exactly and rounded once when written. (T10)
33. Rounding the steering step to the nearest grid unit. It is truncated toward
    zero, so a step below one grid unit becomes zero. (T11)
34. Applying the steering correction from the decision epoch. The first
    corrected epoch is the one after it. (T11)
35. Adding the written free scale to the written correction. Both are rounded
    renderings; the steered scale is the exact sum, rounded once. (T11)
36. Reducing the combined uncertainty to a standard deviation. It is published
    as a variance in square picoseconds. (T12)
37. Omitting the path terms from a node's budget, or including a path term for
    a node that is the root of its component. (T12)
38. Sorting a published artifact by its identifier when the schema reference
    states another order. (T13)
39. Taking the digest over the core artifacts in alphabetical order. The order
    is the one ordering_dependencies.yaml lists. (T13)
40. Reading the workbook sheet by name or by position. The live sheet is the
    one whose key cell matches the interval header. (T08 T09 T12)
41. Taking the publication digest over the core artifacts. It runs over every
    artifact except the manifest, in the order the output artifact contract
    lists them. (T13)
42. Writing the manifest before the rest of the publication. It digests the
    other twenty six documents, so it is written last. (T13)
43. Taking the full step toward the capped target. The pass moves the vector a
    fraction of the way, the damping the weighting policy publishes, and it
    damps every oscillator and not only the offenders. (T09)
44. Solving the cap in closed form, or iterating it to its fixed point. The
    published vector is the one the budget leaves, not the fixed point. (T09)
45. Carrying the exact rational between passes. Every pass places the vector
    back on the published weight grid and the next pass starts from the placed
    values. (T09)
46. Writing a SCOPE_OSCILLATOR dead time record for every oscillator of a node
    that is out. The node record already covers them; an oscillator record is
    the local monitor case alone. (T05 T06)
47. Starting the capping from the unplaced raw weight. The raw weight is
    published as stage T08 forms it, and the capping starts from that weight
    placed on the published grid, so the total the caps are taken from is the
    total of the placed weights. (T08 T09)
48. Growing the tree by the smallest published uncertainty in front of you, the
    minimum spanning tree of the component. The admission works on the
    accumulated path cost back to the root, and on this network the two
    readings admit different links. (T04)
49. Letting the grid placement of a capping pass move the total of the weight
    vector. The residue of the placement is closed onto one receiving holder,
    so every pass preserves the total exactly. (T09)
50. Closing that residue onto the same holder on every pass. Which holder
    carries it is decided by how often each receiving holder has already
    carried it in this interval, counted across all three phases, so the
    carrier moves from pass to pass. (T09)
""".strip())

    _write_text(out / "glossary_and_field_dictionary.md", """
# Glossary and field dictionary

**acq_time_s** absolute time of an acquisition attempt, in whole seconds.

**anchor** the last valid archived deviation of a history window, and the epoch
it was taken at. A prediction passes exactly through its anchor.

**archive epoch** an epoch of the previous interval, numbered 1 to 24.

**attribution window** the half open interval around a grid instant inside
which an acquisition row belongs to that epoch.

**cluster** the set of acquisition rows sharing one link and one grid epoch.

**component** a maximal set of nodes joined by usable links.

**dead time** an epoch at which a link, a node or an oscillator carries no
measurement.

**departure** the free scale at the decision epoch minus the primary
realisation there.

**dispersion** the mean absolute residual of an oscillator over its history
window, published as a whole picosecond.

**free scale** the weighted mean of the prediction residuals of the ensemble
at one epoch, before steering.

**grid epoch** an epoch of this interval, numbered 1 to 30.

**history window** the last history_window_epochs archived epochs.

**hub** the node the interval header names as the root of the anchored
component.

**link bias** the part of a link's reading that the calibration report does not
remove. It is why two spanning trees disagree and why the excluded links carry
non zero closures.

**loop closure** the disagreement between an excluded link's reading and the
difference the tree implies.

**mass preserving** a capping rule under which the sum of the weight vector is
unchanged by the pass, the placement residue included.

**node offset** a node's clock minus the clock of the root of its component.

**admission cost** the path cost of a candidate link's reached end plus its
own published uncertainty, which is the path cost its unreached end would take.
It is what stage T04 admits on.

**path cost** the sum of the published uncertainties of the tree edges between
the root of a component and one of its nodes. The root carries zero.

**placement residue** the amount by which placing a capping pass on the
published weight grid moves the total of the vector. Stage T09 hands the whole
of it to one holder, so a pass preserves the total exactly.

**published uncertainty** the uncertainty the register publishes for a link, in
picoseconds. It builds the admission cost that orders the spanning tree and it
is a term of the budget.

**raw weight** weight_scale divided by the published dispersion, or the class
ceiling weight when the published dispersion is zero.

**reference oscillator** the oscillator a node realises its clock with, at the
frozen register revision.

**residual** a measured deviation minus the deviation the prediction gives at
that epoch.

**sense** whether a technique records node_a minus node_b or the opposite.

**steered scale** the free scale plus the accumulated steering correction.

**sweep** one pass of the oscillator cap over the whole weight vector.

**usable link** a link both of whose nodes are registered and which does not
name the same node on both sides.
""".strip())

    _write_text(out / "output_artifact_contract.md", """
# Output artifact contract

Twenty eight files are published under the output directory. Twenty seven are
derived documents and the twenty eighth is the program that derives them.

| artifact | family | stage |
| --- | --- | --- |
| reading_ledger.csv | core | T01 T02 T03 |
| withdrawal_ledger.tsv | graph | T01 |
| calibration_selection.csv | graph | T02 |
| link_differences.psv | core | T03 |
| link_graph.json | graph | T04 |
| epoch_grid.csv | graph | T01 T10 |
| deadtime_ledger.jsonl | graph | T05 T06 |
| oscillator_series.csv | core | T06 |
| prediction_book.json | weight | T07 |
| dispersion_table.csv | weight | T08 |
| weight_book.json | core | T09 |
| weight_sweep_trace.jsonl | weight | T09 |
| ensemble_scale.csv | core | T10 |
| steering_plan.json | weight | T11 |
| steered_scale.csv | core | T11 |
| node_offsets.csv | publish | T12 |
| uncertainty_budget.tsv | publish | T12 |
| dissemination_ledger.psv | publish | T12 |
| node_report_nd_arden.json | publish | T13 |
| node_report_nd_calder.json | publish | T13 |
| node_report_nd_jarrow.json | publish | T13 |
| node_report_nd_lyddon.json | publish | T13 |
| network_reconciliation.xml | publish | T13 |
| timescale_report.md | publish | T13 |
| ensemble_summary.md | publish | T13 |
| publication_manifest.json | publish | T13 |
| node_index.conf | publish | T13 |

The core family is the family the core digest runs over, in the order
ordering_dependencies.yaml gives. The publication digest in the manifest runs
over every artifact in this table except the manifest, in the order this table
lists them, so the manifest moves when any document in the publication
moves.

Every artifact is a function of this directory alone. Nothing is read from
outside it and nothing carries a timestamp, a host name or a path.
""".strip())

    _write_text(out / "output_schema_reference.md", """
# Output schema reference

Column names, column order and row order are part of every artifact. Delimited
artifacts carry a header row. An artifact with no data rows carries its header
row and nothing else. A line oriented json artifact with no records is a file
of zero bytes.

## reading_ledger.csv

    link_id,epoch_index,session_id,receiver_id,attempt_no,acq_time_s,
    raw_offset_ps,report_id,correction_ps,corrected_ps,sense,difference_ps,
    cluster_rows

Ordered by link_id then epoch_index. cluster_rows is the number of rows the
cluster held after the row by row predicates and before selection.

## withdrawal_ledger.tsv

    drop_reason,link_id,epoch_index,session_id,attempt_no,lock_state

Ordered by drop_reason, then link_id, then epoch_index compared as text, then
session_id, then attempt_no. epoch_index is the whole number of the epoch the
row was attributed to, or the text NONE when it was attributed to none.

## calibration_selection.csv

    link_id,epoch_index,report_id,revision,status,effective_epoch_s,
    delay_delta_ps

Ordered by link_id then epoch_index. A reading with no applicable report
carries report_id REPORT_NONE, revision 0, status CAL_ABSENT,
effective_epoch_s 0 and delay_delta_ps 0.

## link_differences.psv

    epoch_index|link_id|node_a|node_b|technique|sense|difference_ps

Ordered by epoch_index then link_id. Epoch first, not link first.

## link_graph.json

    {"hub_node", "component_count", "components": [
       {"component_id", "role", "root_node", "member_nodes",
        "tree_edges": [{"link_id","parent_node","child_node","technique",
                        "published_uncertainty_ps"}],
        "excluded_link_ids"} ]}

Components in identifier order. tree_edges in the order the edges were
admitted. member_nodes and excluded_link_ids in ascending order.

## epoch_grid.csv

    epoch_index,epoch_instant_s,canonical_readings,tree_links_present,
    contributing_oscillators,epoch_state

One row per grid epoch, in epoch order. tree_links_present counts the links
that are tree edges of any component and carry a canonical reading at that
epoch.

## deadtime_ledger.jsonl

One compact object per line, keys epoch_index, scope, subject, cause. Ordered
by epoch_index, scope, subject, cause. scope is SCOPE_LINK, SCOPE_NODE or
SCOPE_OSCILLATOR. cause is the link identifier for SCOPE_NODE,
CAUSE_NO_READING for SCOPE_LINK and CAUSE_NO_MONITOR for SCOPE_OSCILLATOR.

Each absence is stated once. A node that is out at an epoch takes one
SCOPE_NODE record and its oscillators take none, so a SCOPE_OSCILLATOR record
only ever carries CAUSE_NO_MONITOR.

## oscillator_series.csv

    osc_id,node_id,epoch_index,deviation_ps,series_flag

One row per catalogued oscillator per grid epoch, ordered by osc_id then
epoch_index. deviation_ps is empty on an absent epoch.

## prediction_book.json

    {"window_epochs", "history_minimum", "oscillators": [
      {"osc_id","node_id","osc_class","window_first","window_last",
       "valid_count","anchor_epoch","anchor_deviation_ps","frequency_atto",
       "included","exclusion_reason"} ]}

anchor_deviation_ps and frequency_atto are whole numbers and are written as
json numbers.

valid_count is the number of valid deviations the oscillator holds in its
history window and is published for every oscillator, whether it was included
or excluded and whatever the reason. It is zero only when the window really
holds no valid deviation.

Oscillators in identifier order. An excluded oscillator carries anchor_epoch 0,
anchor_deviation_ps 0, frequency_atto 0 and its reason; an included one carries
an empty reason. frequency_atto is the exact frequency rendered as a whole
number.

## dispersion_table.csv

    osc_id,node_id,osc_class,valid_count,dispersion_ps,weight_source,raw_weight

One row per included oscillator, ordered by dispersion_ps ascending then
osc_id. raw_weight is a ratio.

## weight_book.json

    {"ensemble_size","total_weight","oscillator_cap","node_cap",
     "oscillator_cap_outcome","node_cap_outcome","final_sweep_outcome",
     "sweeps_used","damping_numerator","damping_denominator","weight_places",
     "terminal_residual",
     "oscillators":[{"osc_id","node_id","raw_weight","after_oscillator_cap",
                     "after_node_cap","final_weight"}],
     "node_totals":[{"node_id","weight"}]}

Oscillators in identifier order, node totals in node order. Every weight, the
two cap values and the total are ratios and are written as json strings.
ensemble_size, sweeps_used, damping_numerator, damping_denominator and
weight_places are whole numbers and are written as json numbers.
terminal_residual is a ratio and is written as a json string. sweeps_used
counts the passes of the first pass only.

## weight_sweep_trace.jsonl

One compact object per pass, keys phase, sweep, offenders, excess_ratio,
holders, residual_ratio. excess_ratio and residual_ratio are ratios and are
written as json strings. The records of the first pass come first, then the node cap pass, then
the third pass. offenders is an ascending list of identifiers, of oscillators
in an oscillator phase and of nodes in the node phase.

sweep counts within its own phase and starts at 1 in each of them, so the first
pass numbers its sweeps 1, 2 and upward, and the node cap pass and the third
pass each carry the single record sweep 1. A pass that moved nothing writes no
record at all. holders is the count of holders that took the redistributed
excess and excess_ratio is the mass that moved, written as a ratio.

## ensemble_scale.csv

    epoch_index,epoch_state,contributing_oscillators,denominator_weight,
    free_scale_ps

One row per grid epoch, in epoch order. free_scale_ps is empty on a void epoch
and denominator_weight is the ratio zero there.

## steering_plan.json

    {"decision_epoch","horizon_epochs","grid_atto","departure_ps",
     "raw_step_atto","step_atto","outcome"}

departure_ps and raw_step_atto are ratios and are written as json strings.
step_atto, decision_epoch, horizon_epochs and grid_atto are whole numbers and
are written as json numbers.

## steered_scale.csv

    epoch_index,epoch_state,free_scale_ps,correction_ps,steered_scale_ps

One row per grid epoch, in epoch order. correction_ps is written at every
epoch, including a void one.

## node_offsets.csv

    node_id,epoch_index,offset_ps,offset_flag

One row per registered node per grid epoch, ordered by node_id then
epoch_index.

## uncertainty_budget.tsv

    node_id,component_id,role,path_length,term_count,u_combined_ps2,
    u_linear_ps

One row per registered node, ordered by node_id.

## dissemination_ledger.psv

    node_id|status|epochs_available|offset_mean_ps|u_combined_ps2|u_linear_ps

One row per registered node, ordered by epochs_available descending then
node_id ascending. offset_mean_ps is a ratio.

## node_report_<node>.json

    {"node_id","component_id","role","register_revision","reference_oscillator",
     "path_link_ids","path_length","epochs_available","offset_mean_ps",
     "u_combined_ps2","u_linear_ps","status",
     "oscillators":[{"osc_id","osc_class","status","included",
                     "exclusion_reason","dispersion_ps","final_weight"}]}

Oscillators in catalogue order. An oscillator that holds no weight carries
dispersion_ps 0 and final_weight the ratio zero. offset_mean_ps and
final_weight are ratios and are written as json strings; path_length,
epochs_available, u_combined_ps2, u_linear_ps and dispersion_ps are whole
numbers and are written as json numbers.

## network_reconciliation.xml

The declaration is the first line and is written exactly as below.

    <?xml version="1.0" encoding="UTF-8"?>
    <network_reconciliation>
      <interval>...</interval>
      <closures count="N">
        <closure><link_id/><epoch_index/><closure_ps/></closure>
      </closures>
      <unreconciled count="M"><link_id/></unreconciled>
    </network_reconciliation>

Two space indent, closures ordered by link_id then epoch_index, unreconciled
link identifiers ascending. An element with no children is written as an
opening tag immediately followed by its closing tag, never self closed.

## timescale_report.md

An H1, then four H2 sections in this order, one blank line after every heading
and one blank line before the next heading. The interval label follows the H1
title. Each body line is a label, a colon, one space and the value.

    # Timescale report <interval label>

    ## Network

    hub node: <hub node>
    register revision: <frozen register revision>
    components: <number of components>
    registered nodes: <nodes at the frozen revision>
    published nodes: <nodes whose status is DS_PUBLISHED>

    ## Readings

    canonical readings: <rows in reading_ledger.csv>
    set aside rows: <rows in withdrawal_ledger.tsv>
    dead time records: <records in deadtime_ledger.jsonl>

    ## Ensemble

    oscillators catalogued: <rows in the oscillator catalogue>
    oscillators weighted: <oscillators holding a final weight>
    oscillator cap outcome: <outcome of the first capping pass>
    node cap outcome: <outcome of the second capping pass>
    void epochs: <epochs whose state is EP_ENSEMBLE_VOID>

    ## Steering

    decision epoch: <decision epoch>
    step atto: <applied step, a whole number>
    outcome: <steering outcome>

## ensemble_summary.md

An H1 carrying the interval label, one blank line, then a markdown table with
the header row and separator row exactly as below and one row per registered
node in node order. The pipe characters carry one space either side.

    # Ensemble summary <interval label>

    | node | status | epochs | offset mean ps | u linear ps |
    | --- | --- | --- | --- | --- |
    | <node_id> | <status> | <epochs_available> | <offset mean ratio> | <u_linear_ps> |

The offset mean is a ratio and carries its twelve decimal places. Every other
value in the table is a whole number or a status token, written as the
dissemination ledger writes it.

## publication_manifest.json

    {"interval","document_count","core_order","digest","publication_digest",
     "rule_count","ensemble_size","oscillator_cap_outcome","steering_outcome"}

document_count is 27 and rule_count is 32. digest is the core digest and
publication_digest is the digest over the other twenty six artifacts.

## node_index.conf

Lines of the form key = value with one space either side of the equals sign.
The header keys interval, hub_node, register_revision, node_count and
published_node_count come first, then three lines per node in node order, keyed
node.component, node.status and node.epochs_available.
""".strip())

    _write_text(out / "serialisation_and_digest_contract.md", """
# Serialisation and digest contract

## Bytes

UTF-8 without a byte order mark. Line feed line endings. Exactly one trailing
line feed at the end of every file that has content. No trailing spaces.

## Numbers

A whole number is written without a sign when it is not negative, without
padding and without a thousands separator. Negative zero is written as 0.

A ratio is written with exactly twelve decimal places, produced by rounding the
exact value half to even. A ratio that rounds to zero is written 0.000000000000
whatever its sign.

Rounding is applied at write time. Every value above the write is exact,
except at the two carried roundings the chain names, the published dispersion
of stage T08 and the grid placement of every capping pass of stage T09.

## Delimited files

A comma separated file uses a comma, a tab separated file a tab and a pipe
separated file a vertical bar. No field is quoted and no field contains its
delimiter. The header row carries the column names in the order the schema
reference gives. A file with no data rows carries its header row alone.

## json

Two space indent, keys sorted at every level, ASCII escaping, one trailing line
feed.

Inside a json document a ratio is written as a json string carrying its twelve
decimal places, and a whole number is written as a json number. A whole number
is never quoted and a ratio is never written as a json number, whatever its
value. The same rule holds inside a json lines record.

## json lines

One compact object per line, keys sorted, separators a comma and a colon with
no spaces, one trailing line feed. A file with no records is zero bytes long.

## xml

The xml declaration <?xml version="1.0" encoding="UTF-8"?> on its own first
line, then the document, two space indent, line feed endings. An element with
no children is written as an opening tag immediately followed by its closing
tag.

## markdown

Headings and lines exactly as the schema reference gives them, one blank line
between a heading and the block under it.

## conf

Lines of the form key = value, one space either side of the equals sign, in the
order the schema reference gives.

## The digests

The core digest is sha256 over the concatenated bytes of the six core
artifacts, taken in the order ordering_dependencies.yaml lists under
digest_order.

The publication digest is sha256 over the concatenated bytes of the other
twenty six artifacts, taken in the order the table in
output_artifact_contract.md lists them, with the manifest itself left out.

Both are written as lower case hexadecimal, and both are taken over the bytes
as published, after rounding.
""".strip())

    _write_text(out / "timescale_program_contract.md", """
# The program the desk keeps

The desk keeps one program that recomputes a publication interval from its
working papers. It is published as timescale.py beside the artifacts it
produces, and it is the artifact the desk reuses; the twenty seven documents are
this interval's run of it.

## Interface

    python3 timescale.py --data <input directory> --out <output directory>

Both options default to the directories this interval used. The program reads
nothing outside the directory it is given and writes nothing outside the
directory it is told to write to. It creates the output directory when it does
not exist and it does not remove files it did not write.

## Behaviour

The program holds nothing about this interval inside it. Every identifier,
every count, every threshold and every constant it uses comes from the papers
it is pointed at, including the four control values in the signed memo and the
class ceilings, the node cap and the uncertainty components on the live
workbook sheet. Pointed at a different interval of the same network, with a
different population, a different acquisition profile and different control
values, it produces that interval's twenty seven documents.

It is deterministic. Two runs over the same directory produce the same bytes,
and a run on another machine at another time produces those bytes again.
Everything it needs comes from the directory it is pointed at, so it reads no
clock, draws on no random source, takes nothing from an environment variable,
reaches for nothing outside that directory and uses nothing about the name of
the directory it is given.

That is a property of the delivered program and of nothing else. How the work
gets done is open: read what you like, run what you like, look up whatever
helps.

It reads the workbook and the memo itself. They are a real spreadsheet and a
real document and both are load bearing.

## Failure

An input the papers do not describe is a fault, and the program says which
paper and which field, rather than guessing a value.
""".strip())

    _write_text(out / "operations_handbook.md", """
# Operations handbook

## Why the tree matters

A link's reading is not the pure difference of two clocks. Each link carries a
bias its calibration report does not remove: the residual delay of the fibre or
the satellite path, the receiver electronics and the antenna cable. That bias
is why the graph does not close. Going from the hub to a node one way and back
another gives two different answers, and the closure of a cycle is the sum of
the biases around it.

The desk therefore fixes one tree and publishes along it. The tree is chosen by
published uncertainty because the least uncertain link is the one whose bias is
best characterised. What the desk minimises is the uncertainty a node ends up
carrying, which is the uncertainty of its whole path back to the root and not
of the last link on it, and it is the same figure the budget of stage T12
publishes for that node. A tree grown by the cheapest link in front of it can
hand a node a long cheap path that costs more than one short dear one. That
choice is a decision of the publication, not a property of the network, and it
is why the tree rule is stated exactly and why the links the tree leaves out
are published with their closures rather than quietly dropped.

## Why the caps exist

An ensemble dominated by one oscillator is not an ensemble. If the best clock
in the network holds a third of the weight then the scale is that clock, and
the scale inherits every one of its failures. The oscillator cap bounds any one
holder. The node cap bounds any one site, because oscillators at one site share
a room, a power feed and an environment, and their failures are not
independent.

The excess is redistributed rather than discarded because the weights are
relative. Discarding it would quietly reweight everything downstream by an
amount that depends on how many holders happened to be over the cap.

The sweep budget exists because the redistribution can push a holder over the
cap that was under it before, and the desk publishes a bounded computation
rather than an unbounded one. When the budget binds, the publication says so.

## Why the prediction is two points

The scale is a weighted mean of prediction residuals, and the prediction is a
model of where each oscillator was going. A least squares line through the
window is a better fit to the window and a worse predictor of the epoch after
it, because it is pulled by points a long way in the past. The endpoint slope
carries the recent behaviour of the oscillator and passes exactly through its
last measurement, which is where the interval starts.

## Why the dispersion is carried rounded

Every other rounding in the chain happens at write time. The dispersion does
not, because the desk publishes the dispersion table as whole picoseconds and a
reader has to be able to reproduce the weight from the number in front of them.
A weight formed from an unpublished exact value would not be reproducible from
the publication.
""".strip())

    _write_text(out / "governance_revision_notes.md", """
# Governance and revision notes

## The register

The node register is revised whenever a site changes what realises its clock or
restates its declared uncertainty. Every revision is kept. A publication
interval works at one revision, named in the interval header as
frozen_register_revision, and it does not move to a later one part way through.

Revisions REG-R15 and REG-R16 move the reference oscillator at two sites. This
interval is frozen at REG-R14 and both sites keep the oscillator REG-R14 names.
A recompute at the current revision would publish a different series for every
oscillator at those two sites and a different budget for every site.

node_register_current.csv is a snapshot of the latest revision, kept for the
audit trail. It is not the register this interval works at.

## Calibration revisions

A delay calibration report is registered under the next free revision number
of its link. When the register receives a restatement of a report that is
already on it, the restatement carries the same effective epoch and the next
revision number, and the register keeps both. The reading of that link at that
effective epoch stays the one the register took first, which is the smaller
revision. That is why two reports can share an effective epoch and why the
smaller revision is the one that governs.

The status of a report is a review state, not a selection key. A report on the
register governs the readings its effective epoch reaches whether its review
has finished or not.

The date a report reached the desk is recorded because the audit needs it. It
does not order anything. A report that reached the desk last can take effect
before every other report of its link, or after the interval closes.

## The workbook

The workbook holds a live sheet and a draft. The draft is a working copy of the
next revision and its numbers are not adopted. The interval header carries the
key of the live sheet and the live sheet carries that key in its own header
cell, so the live sheet is identified by matching, not by its name and not by
its position in the workbook.

## The retired weighting scheme

Before REG-R09 the network weighted by a fixed number per oscillator class.
legacy_weight_table.csv is what that scheme published. It is retired. Weights
come from the residual dispersion of the previous interval.
""".strip())

    _write_text(out / "operator_faq.md", """
# Operator questions

**A cluster has two rows with attempt number 2 and both hold lock. Which one?**
The one whose acquisition time is closest to the epoch instant. If they are
equally close, the earlier one.

**A row sits exactly on the upper edge of a window.** It is outside that
window. The window is closed below and open above. It may fall inside no window
at all, and then it is set aside.

**The withdrawal journal names a session that was the only locked attempt of
its cluster.** The session goes, and then the cluster has no locked attempt, so
the rest of the cluster is set aside as well. Two rules, applied in the order
stage T01 gives.

**A link's reports all take effect after the interval closes.** Then no report
governs it. Its correction is zero and the selection records CAL_ABSENT.

**Two links join the same pair of nodes.** Both are usable. The tree admits one
of them by the rule and the other is an excluded link with published closures.

**A node has no usable link.** It is a component of one node, it is unanchored,
it is its own root, its offset is zero at every epoch and its dissemination is
withheld as unanchored.

**A node's only link carries no reading at any epoch.** Its offsets are absent
throughout, and its dissemination is withheld for want of data. It is not
unanchored: it sits in the anchored component.

**An oscillator has exactly the history minimum of valid epochs.** It is
included. The comparison is strict.

**An oscillator's residuals are all zero.** Its published dispersion is zero
and it takes the ceiling weight of its class from the workbook.

**Every weighted oscillator is above the oscillator cap.** There is nobody to
take the excess. The pass records SW_CAP_UNSATISFIABLE and changes nothing.

**No oscillator carries a deviation at an epoch.** That epoch is void. It has
no free scale and no steered scale, but it still carries its steering
correction.

**The decision epoch has no primary realisation.** There is no departure, the
step is zero and the outcome is ST_NO_REALISATION. The correction is zero at
every epoch.

**Does the published free scale plus the published correction give the
published steered scale?** Not in general. All three are rounded renderings of
exact values, and the steered scale is the rounding of the exact sum.
""".strip())

    _write_text(out / "link_technique_reference.txt", """
LINK TECHNIQUE REFERENCE

technique              sense              rank   note
LK_FIBRE_TWO_WAY       SENSE_A_MINUS_B    1      two way optical fibre
LK_TWSTFT              SENSE_A_MINUS_B    2      two way satellite transfer
LK_GNSS_PPP            SENSE_B_MINUS_A    3      precise point positioning
LK_GNSS_CV             SENSE_B_MINUS_A    4      common view

The sense says which way round the technique records its comparison. A
technique of sense SENSE_A_MINUS_B records the clock of node_a minus the clock
of node_b, as the link register orders them. A technique of sense
SENSE_B_MINUS_A records the opposite and the sign is inverted at stage T03.

The rank orders two candidate tree edges of equal admission cost at stage
T04. The smaller rank is admitted. Rank is a property of the technique and has
nothing to do with the sense.
""".strip())

    _write_text(out / "lock_state_reference.txt", """
LOCK STATE REFERENCE

LOCK_HELD      the receiver held phase lock for the whole acquisition
LOCK_SLIP      lock was lost and reacquired inside the acquisition
LOCK_LOST      lock was not held at the end of the acquisition
LOCK_UNKNOWN   the receiver did not report a lock state

Only LOCK_HELD makes an attempt eligible to be the canonical reading of its
cluster, whatever the attempt number. An attempt in any other state is recorded
in the log because the audit needs it and is never selected.

ARCHIVE QUALITY FLAGS

ARC_VALID      a measurement
ARC_ESTIMATED  filled by the previous interval's own model
ARC_SUSPECT    kept but not trusted
ARC_VOID       no measurement

Only ARC_VALID counts toward a history window.

MONITOR FLAGS

MON_VALID      the local monitor measured the oscillator
MON_SUSPECT    the monitor reported, and the reading is not a measurement
""".strip())

    _write_text(out / "oscillator_class_reference.txt", """
OSCILLATOR CLASS REFERENCE

OSC_CRYO_SAPPHIRE   cryogenic sapphire oscillator
OSC_HMASER          active hydrogen maser
OSC_RB_FOUNTAIN     rubidium fountain
OSC_CS_BEAM         caesium beam standard
OSC_OCXO            oven controlled crystal oscillator

The class of an oscillator selects its ceiling weight, and the ceiling weight
applies only to an oscillator whose published dispersion is zero. The ceiling
weights are on the live sheet of the workbook and in no plain text paper.

Class does not otherwise weight an oscillator. Weight comes from the residual
dispersion of the previous interval.

OSCILLATOR STATUS

OS_ACTIVE           in service
OS_DECOMMISSIONED   withdrawn from service, excluded from the ensemble
""".strip())

    _write_text(out / "field_order_reference.txt", """
FIELD ORDER REFERENCE

Column order is part of an artifact. These are the orders the schema reference
gives, restated here so a writer can check itself.

reading_ledger.csv
  link_id, epoch_index, session_id, receiver_id, attempt_no, acq_time_s,
  raw_offset_ps, report_id, correction_ps, corrected_ps, sense,
  difference_ps, cluster_rows

withdrawal_ledger.tsv
  drop_reason, link_id, epoch_index, session_id, attempt_no, lock_state

calibration_selection.csv
  link_id, epoch_index, report_id, revision, status, effective_epoch_s,
  delay_delta_ps

link_differences.psv
  epoch_index, link_id, node_a, node_b, technique, sense, difference_ps

epoch_grid.csv
  epoch_index, epoch_instant_s, canonical_readings, tree_links_present,
  contributing_oscillators, epoch_state

oscillator_series.csv
  osc_id, node_id, epoch_index, deviation_ps, series_flag

dispersion_table.csv
  osc_id, node_id, osc_class, valid_count, dispersion_ps, weight_source,
  raw_weight

ensemble_scale.csv
  epoch_index, epoch_state, contributing_oscillators, denominator_weight,
  free_scale_ps

steered_scale.csv
  epoch_index, epoch_state, free_scale_ps, correction_ps, steered_scale_ps

node_offsets.csv
  node_id, epoch_index, offset_ps, offset_flag

uncertainty_budget.tsv
  node_id, component_id, role, path_length, term_count, u_combined_ps2,
  u_linear_ps

dissemination_ledger.psv
  node_id, status, epochs_available, offset_mean_ps, u_combined_ps2,
  u_linear_ps

Row order is stated per artifact in the schema reference and is not always the
identifier order.
""".strip())


# ==========================================================================
# grading
#
# Three tiers. A small existence floor, the shipped interval, and the
# delivered program run against three intervals minted here from seeds the
# agent never sees. Every interval is graded family by family, the core
# included, and each family is checked on its own documents only, so a stage
# read differently costs the families it moves and no others. A family passes
# when its documents match the reconstruction under one of the graded
# readings.
# ==========================================================================

OUT_DIR = Path(OUTPUT_ROOT)
PROGRAM = OUT_DIR / PROGRAM_NAME
PROGRAM_TIMEOUT_SEC = 420

MINTED_SEEDS = [EVAL_SEED, CHALLENGE_SEED, PROBE_SEED]

# The user the delivered program is dropped to before it runs. It owns
# nothing, and tests/test.sh takes the read bit off /tests for it.
UNPRIVILEGED_UID = "nobody"
UNPRIVILEGED_GID = "nogroup"

# File names that would shadow something this module imports if a grader ever
# ran with the delivery directory ahead of it on the import path.
REBINDING_NAMES = {
    "sitecustomize.py", "usercustomize.py", "conftest.py", "pytest.ini",
    "csv.py", "decimal.py", "fractions.py", "hashlib.py", "json.py",
    "pathlib.py", "random.py", "sqlite3.py", "subprocess.py", "zipfile.py",
}

_CORPUS_CACHE: dict = {}
_EXPECTED_CACHE: dict = {}
_NAIVE_CACHE: dict = {}
_PROGRAM_CACHE: dict = {}


def _corpus(seed: int) -> Path:
    if seed not in _CORPUS_CACHE:
        root = Path(tempfile.mkdtemp(prefix="ets-corpus-")) / "data"
        generate(seed, root)
        _CORPUS_CACHE[seed] = root
    return _CORPUS_CACHE[seed]


def _expected(seed: int = SAMPLE_SEED, reading=frozenset()) -> dict:
    key = (seed, reading)
    if key not in _EXPECTED_CACHE:
        _EXPECTED_CACHE[key] = run_pipeline(_corpus(seed), off=reading)
    return _EXPECTED_CACHE[key]


def _expected_readings(seed: int = SAMPLE_SEED) -> list:
    return [_expected(seed, reading) for reading in GRADED_READINGS]


def _naive(rule: str, seed: int = SAMPLE_SEED, reading=frozenset()) -> dict:
    key = (rule, seed, reading)
    if key not in _NAIVE_CACHE:
        _NAIVE_CACHE[key] = run_pipeline(_corpus(seed), off={rule} | reading)
    return _NAIVE_CACHE[key]


def _drop_privileges(argv: list) -> list:
    """Wrap a command so it runs as an unprivileged user.

    The delivered program is hostile input. Run as root it can read this
    module, which carries the generator and the whole reference chain, and a
    program that loads it and calls run_pipeline reproduces every graded byte
    on every interval without implementing anything. setpriv drops the run to
    nobody, and the verifier image makes /tests unreadable to that user, so
    the route is closed rather than merely discouraged. util-linux is
    installed by tests/Dockerfile for exactly this."""
    setpriv = shutil.which("setpriv")
    if setpriv is None:
        return list(argv)
    return [setpriv, "--reuid=" + UNPRIVILEGED_UID, "--regid=" + UNPRIVILEGED_GID,
            "--clear-groups", "--"] + list(argv)


def _open_to_unprivileged(root: Path) -> None:
    """Let the dropped user work under a directory this module made.

    tempfile.mkdtemp creates 0700, which nobody cannot even enter. The copied
    interval is left writable on purpose: the contract forbids the program to
    change its input directory, and the detector that grades that rule has to
    be able to observe the breach rather than have the kernel prevent it."""
    try:
        os.chmod(root, 0o777)
        for path in Path(root).rglob("*"):
            os.chmod(path, 0o777 if path.is_dir() else 0o666)
    except OSError:
        pass


def _readable_program() -> None:
    """The deliverable arrives owned by root. Make sure the dropped user can
    read it, so a restrictive umask on the agent side costs it nothing."""
    try:
        os.chmod(PROGRAM, 0o644)
    except OSError:
        pass


def _run_isolated(argv: list, cwd: str) -> tuple:
    """Run delivered agent code as an unprivileged subprocess in its own
    session, wait for it and then reap anything it left behind. The delivered
    program is hostile input in the grading container, so a child that
    detaches its stdio and outlives the run could rewrite the reward file
    after the grading phase has written it. Putting the run in a new process
    group and killing that group once the parent has exited closes that
    route, and dropping the user closes the read of this module."""
    proc = subprocess.Popen(_drop_privileges(argv),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, cwd=cwd,
                            start_new_session=hasattr(os, "killpg"))
    try:
        _, err = proc.communicate(timeout=PROGRAM_TIMEOUT_SEC)
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.communicate()
        raise
    finally:
        if hasattr(os, "killpg"):
            try:
                os.killpg(proc.pid, 9)
            except (ProcessLookupError, PermissionError, OSError):
                pass
    return rc, (err or "")[-4000:]


def _program_argv(data: Path, out: Path, flip: bool) -> list:
    """The command line the delivered program is run with.

    The contract says the two options are accepted in either order, so one of
    the graded intervals passes them the other way round and the promise is
    exercised rather than merely stated."""
    if flip:
        return [sys.executable, str(PROGRAM), "--out", str(out), "--data", str(data)]
    return [sys.executable, str(PROGRAM), "--data", str(data), "--out", str(out)]


def _tree_digest(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(Path(root).rglob("*")):
        if path.is_file():
            h.update(str(path.relative_to(root)).replace(os.sep, "/").encode("utf-8"))
            h.update(hashlib.sha256(path.read_bytes()).digest())
    return h.hexdigest()


def _program_case(seed: int, tag: str = "case") -> dict:
    """Run the delivered program against a private copy of an interval this
    module mints. The agent has never seen the interval and cannot have tuned
    to it."""
    key = (seed, tag)
    if key in _PROGRAM_CACHE:
        return _PROGRAM_CACHE[key]
    if not PROGRAM.is_file():
        raise AssertionError("required deliverable is absent: " + PROGRAM_NAME)
    root = Path(tempfile.mkdtemp(prefix="ets-run-"))
    data = root / tag
    out = root / (tag + "-out")
    shutil.copytree(_corpus(seed), data)
    _open_to_unprivileged(root)
    _readable_program()
    before = _tree_digest(data)
    try:
        rc, err = _run_isolated(
            _program_argv(data, out, seed == CHALLENGE_SEED), cwd=str(root))
    except subprocess.TimeoutExpired:
        rc, err = -1, "the program did not finish within the time allowed"
    _PROGRAM_CACHE[key] = {"rc": rc, "out": out, "stderr": err,
                           "before": before, "after": _tree_digest(data)}
    return _PROGRAM_CACHE[key]


def _program_repeat(seed: int) -> tuple:
    """Run the delivered program twice over ONE input directory, into two
    output directories. The input path is byte identical and name identical
    across the two runs, so a difference between them is nondeterminism and
    nothing else."""
    key = ("repeat-pair", seed)
    if key in _PROGRAM_CACHE:
        return _PROGRAM_CACHE[key]
    if not PROGRAM.is_file():
        raise AssertionError("required deliverable is absent: " + PROGRAM_NAME)
    root = Path(tempfile.mkdtemp(prefix="ets-repeat-"))
    data = root / "instance"
    shutil.copytree(_corpus(seed), data)
    _open_to_unprivileged(root)
    _readable_program()
    runs = []
    for index in (1, 2):
        out = root / ("out-%d" % index)
        try:
            rc, _ = _run_isolated(
                _program_argv(data, out, seed == CHALLENGE_SEED), cwd=str(root))
        except subprocess.TimeoutExpired:
            rc = -1
        runs.append((rc, out))
    _PROGRAM_CACHE[key] = tuple(runs)
    return _PROGRAM_CACHE[key]


def _repeat_got(seed: int, name: str) -> tuple:
    blobs = []
    for rc, out in _program_repeat(seed):
        if rc != 0:
            raise AssertionError("the program failed on the minted interval")
        path = out / name
        if not path.is_file():
            raise AssertionError(
                "the program wrote no %s for the minted interval" % name)
        blobs.append(path.read_bytes())
    return tuple(blobs)


def _got(name: str) -> bytes:
    path = OUT_DIR / name
    if not path.is_file():
        raise AssertionError("required artifact is absent: " + name)
    return path.read_bytes()


def _got_text(name: str) -> str:
    return _got(name).decode("utf-8")


def _case_got(seed: int, name: str, tag: str = "case") -> bytes:
    case = _program_case(seed, tag)
    if case["rc"] != 0:
        raise AssertionError(
            "the program failed on the minted interval: " + str(case["stderr"]))
    path = case["out"] / name
    if not path.is_file():
        raise AssertionError("the program wrote no %s for the minted interval" % name)
    return path.read_bytes()


def _matches_a_reading(got: dict, seed: int) -> bool:
    return any(all(got[name] == exp[name] for name in got)
               for exp in _expected_readings(seed))


def _assert_shipped_family(names) -> None:
    got = {name: _got(name) for name in names}
    assert _matches_a_reading(got, SAMPLE_SEED), (
        "the shipped family differs from every graded reading")


def _assert_case_family(seed: int, names) -> None:
    got = {name: _case_got(seed, name) for name in names}
    assert _matches_a_reading(got, seed), (
        "the program family differs from every graded reading on the minted interval")


# --------------------------------------------------------------------------
# tier one: the existence floor
# --------------------------------------------------------------------------
def test_all_artifacts_exist():
    """POSITIVE: every declared document and the timescale program are present
    under the output directory."""
    missing = [name for name in ARTIFACTS if not (OUT_DIR / name).is_file()]
    assert not missing, "missing artifacts: %s" % missing
    assert PROGRAM.is_file(), "missing deliverable: " + PROGRAM_NAME


def test_core_documents_parse():
    """POSITIVE: the manifest, the link graph and the prediction book carry
    the shape the output schema reference fixes."""
    manifest = json.loads(_got_text("publication_manifest.json"))
    assert manifest.get("core_order") == list(CORE_FILES)
    assert manifest.get("rule_count") == len(RULE_IDS)
    graph = json.loads(_got_text("link_graph.json"))
    assert graph.get("hub_node") == HUB_NODE
    roles = {component["role"] for component in graph["components"]}
    assert roles <= set(COMPONENT_ROLES)
    book = json.loads(_got_text("prediction_book.json"))
    assert book["history_minimum"] > 0
    reasons = {entry["exclusion_reason"] for entry in book["oscillators"]
               if not entry["included"]}
    assert reasons <= set(EXCLUSION_REASONS)


# --------------------------------------------------------------------------
# tier two: the shipped interval, byte exact, family by family
# --------------------------------------------------------------------------
def test_shipped_core_exact():
    """POSITIVE: the seven core artifacts of the shipped interval are byte
    exact. The core digest runs over six of them and the publication manifest
    carries it, so grading all seven here settles the digest by the byte
    comparison itself."""
    _assert_shipped_family(FAM_CORE)


def test_shipped_graph_family_exact():
    """POSITIVE: the withdrawal ledger, the calibration selection, the link
    graph, the epoch grid and the dead time ledger of the shipped interval are
    byte exact."""
    _assert_shipped_family(FAM_GRAPH)


def test_shipped_weight_family_exact():
    """POSITIVE: the prediction book, the dispersion table, the weight book,
    the sweep trace and the steering plan of the shipped interval are byte
    exact."""
    _assert_shipped_family(FAM_WEIGHT)


def test_shipped_publish_family_exact():
    """POSITIVE: the node offsets, the uncertainty budget, the dissemination
    ledger, the four node reports, the reconciliation, the two reports, the
    manifest and the node index of the shipped interval are byte exact."""
    _assert_shipped_family(FAM_PUBLISH)


# --------------------------------------------------------------------------
# tier three: the program, run against intervals the agent has never seen
#
# Two are minted under the strained acquisition profile and one under the
# sparse profile. The branches the shipped interval leaves quiet do most of
# the work here, so a program written only to reproduce the shipped bytes
# earns nothing across all three.
# --------------------------------------------------------------------------
def test_program_eval_core_exact():
    """POSITIVE: the program reproduces the seven core artifacts of the first
    minted interval."""
    _assert_case_family(EVAL_SEED, FAM_CORE)


def test_program_challenge_core_exact():
    """POSITIVE: the program reproduces the seven core artifacts of the second
    minted interval."""
    _assert_case_family(CHALLENGE_SEED, FAM_CORE)


def test_program_probe_core_exact():
    """POSITIVE: the program reproduces the seven core artifacts of the sparse
    minted interval."""
    _assert_case_family(PROBE_SEED, FAM_CORE)


def test_program_eval_graph_exact():
    """POSITIVE: the program reproduces the graph family of the first minted
    interval."""
    _assert_case_family(EVAL_SEED, FAM_GRAPH)


def test_program_eval_weight_exact():
    """POSITIVE: the program reproduces the weight family of the first minted
    interval."""
    _assert_case_family(EVAL_SEED, FAM_WEIGHT)


def test_program_eval_publish_exact():
    """POSITIVE: the program reproduces the publication family of the first
    minted interval."""
    _assert_case_family(EVAL_SEED, FAM_PUBLISH)


def test_program_challenge_graph_exact():
    """POSITIVE: the program reproduces the graph family of the second minted
    interval."""
    _assert_case_family(CHALLENGE_SEED, FAM_GRAPH)


def test_program_challenge_weight_exact():
    """POSITIVE: the program reproduces the weight family of the second minted
    interval."""
    _assert_case_family(CHALLENGE_SEED, FAM_WEIGHT)


def test_program_challenge_publish_exact():
    """POSITIVE: the program reproduces the publication family of the second
    minted interval."""
    _assert_case_family(CHALLENGE_SEED, FAM_PUBLISH)


def test_program_probe_graph_exact():
    """POSITIVE: the program reproduces the graph family of the sparse minted
    interval."""
    _assert_case_family(PROBE_SEED, FAM_GRAPH)


def test_program_probe_weight_exact():
    """POSITIVE: the program reproduces the weight family of the sparse minted
    interval."""
    _assert_case_family(PROBE_SEED, FAM_WEIGHT)


def test_program_probe_publish_exact():
    """POSITIVE: the program reproduces the publication family of the sparse
    minted interval, whose steering carries no primary realisation."""
    _assert_case_family(PROBE_SEED, FAM_PUBLISH)


# --------------------------------------------------------------------------
# negative detectors
#
# Each of the first eight rebuilds the whole pipeline under one named wrong
# reading and fires only when the delivered bytes match that reconstruction
# under one of the graded readings. Each short circuits on a delivery that is
# correct under any graded reading, so a correct submission trips none of
# them, and each raises rather than returning when an artifact is absent, so
# an empty container trips none of them either.
# --------------------------------------------------------------------------
def _assert_matches_naive(name: str, rule: str, correct: str) -> None:
    got = _got(name)
    if any(got == exp[name] for exp in _expected_readings()):
        raise AssertionError(correct)
    assert any(got == _naive(rule, SAMPLE_SEED, reading)[name]
               for reading in GRADED_READINGS)


def test_negative_weight_unlocked_attempt_selected():
    """NEGATIVE: the canonical reading of a cluster was taken as the greatest
    attempt number whatever its lock state."""
    _assert_matches_naive("reading_ledger.csv", "R_LOCK_STATE",
                          "the readings are correct; this detector must stay silent")


def test_negative_weight_latest_issued_calibration():
    """NEGATIVE: the delay report was chosen by the greatest issued epoch
    instead of the greatest effective epoch on or before the reading."""
    _assert_matches_naive("calibration_selection.csv", "R_CAL_APPLICABLE",
                          "the selection is correct; this detector must stay silent")


def test_negative_weight_least_squares_prediction():
    """NEGATIVE: the prediction frequency was fitted by least squares over the
    history window instead of taken through its first and last valid
    points."""
    _assert_matches_naive("prediction_book.json", "R_TWO_POINT_SLOPE",
                          "the predictions are correct; this detector must stay silent")


def test_negative_weight_clamped_weight_vector():
    """NEGATIVE: the caps clamped the offending weights and discarded the
    excess instead of redistributing it in proportion."""
    _assert_matches_naive("weight_book.json", "R_CAP_REDISTRIBUTE",
                          "the weights are correct; this detector must stay silent")


def test_negative_weight_fixed_residue_carrier():
    """NEGATIVE: every pass closed its grid placement residue onto the greatest
    receiving holder, instead of onto the receiver that has carried the residue
    the fewest times so far in the interval."""
    _assert_matches_naive("weight_book.json", "R_RESIDUE_ROTATION",
                          "the weights are correct; this detector must stay silent")


def test_negative_weight_rounded_before_the_average():
    """NEGATIVE: every residual was rounded to a whole picosecond before the
    weighted mean instead of the quotient being rounded once at write time."""
    _assert_matches_naive("ensemble_scale.csv", "R_ROUND_AT_WRITE",
                          "the free scale is correct; this detector must stay silent")


def test_negative_weight_current_node_register():
    """NEGATIVE: node metadata was read from the current register snapshot
    instead of the register revision the interval header freezes."""
    _assert_matches_naive("oscillator_series.csv", "R_FROZEN_REGISTER",
                          "the series are correct; this detector must stay silent")


def test_negative_weight_steering_from_the_decision_epoch():
    """NEGATIVE: the steering correction was applied from the decision epoch
    instead of the epoch after it."""
    _assert_matches_naive("steered_scale.csv", "R_STEER_NEXT_EPOCH",
                          "the steered scale is correct; this detector must stay silent")


def test_negative_weight_hardcoded_sample_answers():
    """NEGATIVE: the shipped bytes are right and nothing behind them produces
    a publication. Either no program was delivered at all, or the delivered
    one exits cleanly on every minted interval and writes no publication
    there, so there is no pipeline behind the delivery. The trigger is the
    ABSENCE of output rather than the wrongness of it, and a program that
    FAILS on a minted interval is a pipeline with a bug rather than a copy: it
    already forfeits the whole minted tier and this detector leaves it alone,
    which is why the failing case raises here instead of counting. The
    assertion holds when the defect is present, so a correct delivery fails it
    and escapes the penalty."""
    shipped_ok = _matches_a_reading({name: _got(name) for name in FAM_CORE}, SAMPLE_SEED)
    if not shipped_ok:
        raise AssertionError("the shipped core is wrong; this detector must stay silent")
    if not PROGRAM.is_file():
        # The shipped documents are exact and no program was delivered to
        # derive them, which is the copy this detector is for.
        return
    produced_nothing = 0
    for seed in MINTED_SEEDS:
        case = _program_case(seed)
        if case["rc"] != 0:
            raise AssertionError(
                "the program failed on a minted interval; that is a pipeline "
                "with a bug and this detector must stay silent")
        if not (case["out"] / "reading_ledger.csv").is_file():
            produced_nothing += 1
    assert produced_nothing == len(MINTED_SEEDS)


def test_negative_weight_manifest_digest_mismatch():
    """NEGATIVE: the published manifest digest disagrees with the bytes of the
    six core artifacts delivered beside it, taken in the published order. A
    fabricated digest trips it, and so does a digest taken over the right
    bytes in the wrong order, which is the reading the digest order rule
    names."""
    digest = hashlib.sha256()
    for name in CORE_FILES:
        digest.update(_got(name))
    published = json.loads(_got_text("publication_manifest.json")).get("digest")
    assert published != digest.hexdigest()


def test_negative_weight_program_ignores_its_input():
    """NEGATIVE: the program writes one constant core whatever interval it is
    pointed at, and that constant is not the shipped corpus. The shipped
    corpus case belongs to the detector below, so the two are disjoint and one
    delivery never fires both. The assertion holds when the defect is present,
    so a correct delivery fails it and escapes the penalty."""
    shipped = _expected()
    first = _case_got(EVAL_SEED, "reading_ledger.csv")
    second = _case_got(PROBE_SEED, "reading_ledger.csv")
    if first == shipped["reading_ledger.csv"]:
        raise AssertionError("the program emits the shipped corpus; the "
                             "training corpus detector owns that defect")
    assert first == second


def test_negative_weight_nondeterministic_output():
    """NEGATIVE: two runs of the program over ONE input directory, at one
    identical path, disagree, so the delivered figures are not reproducible.
    Holding the path fixed is what keeps this detector off the filename defect
    below. The assertion holds when the defect is present, so a correct
    delivery fails it and escapes the penalty."""
    first, second = _repeat_got(CHALLENGE_SEED, "ensemble_scale.csv")
    assert first != second


def test_negative_weight_filename_dependent_behaviour():
    """NEGATIVE: the program is reproducible at one path and still writes
    something else when the same interval is presented under a different
    directory name. The reproducibility clause keeps this detector disjoint
    from the one above, so one defect never fires both. The assertion holds
    when the defect is present, so a correct delivery fails it and escapes the
    penalty."""
    steady = _repeat_got(EVAL_SEED, "ensemble_scale.csv")
    if steady[0] != steady[1]:
        raise AssertionError("the program is not reproducible; the determinism "
                             "detector owns that defect")
    first = _case_got(EVAL_SEED, "ensemble_scale.csv", "case")
    second = _case_got(EVAL_SEED, "ensemble_scale.csv", "renamed")
    assert first != second


def test_negative_weight_program_dirties_its_directories():
    """NEGATIVE: the program changed the input directory it was pointed at, or
    left something other than the twenty seven derived documents in the output
    directory. Both rules are stated in the program contract and in the output
    artifact contract, and the input directory is digested before and after
    the run. The assertion holds when the defect is present, so a clean
    delivery fails it and escapes the penalty."""
    dirty = False
    for seed in MINTED_SEEDS:
        case = _program_case(seed)
        if case["rc"] != 0:
            raise AssertionError("the program failed on the minted interval; "
                                 "this detector must stay silent")
        if case["out"].is_dir() and {p.name for p in case["out"].iterdir()} & REBINDING_NAMES:
            raise AssertionError("the program wrote a shadowing module; the "
                                 "rebinding detector owns that defect")
        if case["before"] != case["after"]:
            dirty = True
        if not case["out"].is_dir():
            dirty = True
            continue
        written = sorted(p.name for p in case["out"].iterdir())
        if written != sorted(ARTIFACTS):
            dirty = True
    assert dirty


def test_negative_weight_reads_training_corpus_at_runtime():
    """NEGATIVE: the program reaches for the shipped corpus rather than the
    directory it was pointed at, so it writes the shipped answer for an
    interval it has never seen."""
    shipped = _expected()
    same = 0
    for seed in MINTED_SEEDS:
        try:
            got = _case_got(seed, "reading_ledger.csv")
        except AssertionError:
            raise AssertionError("the program produced nothing; the hardcoded "
                                 "answer detector owns that defect")
        if got == shipped["reading_ledger.csv"]:
            same += 1
    assert same == len(MINTED_SEEDS)


def test_negative_weight_rebinds_verifier_dependencies():
    """NEGATIVE: the delivered program dropped a module beside its artifacts
    during a minted run whose name shadows something the verifier imports, so
    a grader run from that directory would load the submission's code in place
    of the real module. The directory detector above short circuits on the
    same names, so one delivery never fires both. The assertion holds when the
    defect is present, so a clean delivery fails it and escapes the penalty."""
    if not PROGRAM.is_file():
        raise AssertionError("there is no program to inspect; this detector must stay silent")
    found = False
    for seed in MINTED_SEEDS:
        case = _program_case(seed)
        if case["rc"] != 0:
            continue
        if not case["out"].is_dir():
            continue
        if {p.name for p in case["out"].iterdir() if p.is_file()} & REBINDING_NAMES:
            found = True
    assert found


# --------------------------------------------------------------------------
# self check entry point
#
# Regenerating the shipped corpus from its seed and recomputing the whole
# publication is how this module is checked outside the harness.
# --------------------------------------------------------------------------
def _write_corpus(seed: int, out_dir) -> dict:
    """Mint one publication interval of the network into out_dir."""
    return generate(seed, Path(out_dir))


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="ets-selfcheck-")) / "data"
    info = _write_corpus(SAMPLE_SEED, root)
    blobs = run_pipeline(root)
    print("corpus files", info["files"])
    print("profile", info["profile"], "interval", info["interval"])
    print("artifacts", len(blobs))
    print("digest", json.loads(blobs["publication_manifest.json"].decode())["digest"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
