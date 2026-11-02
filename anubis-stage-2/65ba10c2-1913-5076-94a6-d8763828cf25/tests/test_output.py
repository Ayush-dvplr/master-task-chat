"""Deterministic verifier for the container yard rehandling ledger task.

The verifier owns its corpus. It regenerates the whole working paper tree from
a named seed into a temporary directory, recomputes every published document
from that regeneration, and grades the agent bytes under the output directory
against it. It never reads the agent corpus, which does not exist in this
container.

Most of the positive weight is spent on the delivered program rather than on
the delivered bytes. Three further operating shifts are minted here from seeds
the agent never sees, one under a strained quay profile, one under a wide
profile and one under a sparse profile the shipped shift does not use, and the
delivered ledger program is run against each of them as a subprocess. Its
output is graded byte for byte against the publication those papers entail.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

# Imports the corpus generator and the grading half need. The reference
# pipeline needs none of them, so the delivered program carries no import it
# does not use.
import base64
import os
import shutil
import signal
import sqlite3
import subprocess
import tempfile
import threading

from rewardkit import criteria, criterion

# The agent output path is assembled rather than written as a literal,
# because this module also runs where no such directory exists.
OUTPUT_ROOT = "/app" + "/out"
PROGRAM_NAME = "yardledger.py"

SAMPLE_SEED = 3140829677
EVAL_SEED = 5271933811
CHALLENGE_SEED = 6382044922
PROBE_SEED = 7493155033

SEED_PROFILE = {
    SAMPLE_SEED: "shipped",
    EVAL_SEED: "strained",
    CHALLENGE_SEED: "wide",
    PROBE_SEED: "sparse",
}

MINTED_SEEDS = [EVAL_SEED, CHALLENGE_SEED, PROBE_SEED]

# One published observable per stage, plus the manifest that digests the whole
# publication. The order of this list, and of ALL_DOCUMENTS below, is the order
# the manifest lists its documents in, so it is part of the published bytes and
# is fixed by SECTION 7 of the serialisation contract.
FAMILY_CORE = [
    "canonical_events.csv",
    "container_dimensions.csv",
    "vessel_obligation.csv",
    "initial_occupancy.psv",
    "event_order.csv",
    "cycle_break_report.json",
    "move_eligibility.csv",
    "yard_occupancy.psv",
    "movement_accounting.jsonl",
    "rehandle_ledger.jsonl",
    "yard_capacity.csv",
    "load_eligibility.csv",
    "ration_trace.jsonl",
    "terminal_reconciliation.csv",
    "publication_manifest.json",
]

MANIFEST = "publication_manifest.json"

SPINE = [name for name in FAMILY_CORE if name != MANIFEST]

FAMILY_STATE = [
    "rejected_moves.tsv",
    "rejection_reasons.csv",
    "accepted_moves.csv",
    "container_state_history.psv",
    "container_state_final.csv",
    "dependency_order.csv",
]

FAMILY_YARD = [
    "yard_reservations.psv",
    "block_utilization.csv",
    "equipment_usage.csv",
    "equipment_exceptions.tsv",
    "slot_accounting.csv",
]

FAMILY_VESSEL = [
    "vessel_cutoff_status.csv",
    "vessel_container_manifest.psv",
    "load_sequence_ledger.json",
    "deferred_containers.tsv",
    "departure_ledger.json",
    "vessel_reconciliation.xml",
    "exception_summary.tsv",
    "audit_trail.conf",
    "berth_report_bt_alder.json",
    "berth_report_bt_calder.json",
    "berth_report_bt_marlow.json",
    "daily_operational_summary.md",
    "final_control_totals.json",
]

# The six documents the manifest carries a joint digest over. The other
# thirty three are digested by the publication digest.
CORE_DOCUMENTS = [
    "canonical_events.csv",
    "move_eligibility.csv",
    "yard_occupancy.psv",
    "yard_capacity.csv",
    "load_eligibility.csv",
    "terminal_reconciliation.csv",
]

ALL_DOCUMENTS = FAMILY_CORE + FAMILY_STATE + FAMILY_YARD + FAMILY_VESSEL

BERTHS = ["bt_alder", "bt_calder", "bt_marlow"]

"""Instance minting for 65ba10c2-1913-5076-94a6-d8763828cf25.

This module is source text: it is concatenated verbatim into
tests/test_output.py, where the verifier uses it to mint operating shifts the
agent has never seen. It holds no reference to any grading decision; it only
lays out the terminal's working papers.
"""

# --------------------------------------------------------------------------
# deterministic rng
#
# CPython's random module is not contractually stable across releases, so the
# corpus is minted from a xorshift64 the module owns.
# --------------------------------------------------------------------------


class Rng:
    """xorshift64star, fully specified so a regeneration reproduces bytes."""

    def __init__(self, seed):
        s = seed & 0xFFFFFFFFFFFFFFFF
        self.state = s if s else 0x9E3779B97F4A7C15

    def _next(self):
        x = self.state
        x ^= (x >> 12) & 0xFFFFFFFFFFFFFFFF
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27) & 0xFFFFFFFFFFFFFFFF
        self.state = x & 0xFFFFFFFFFFFFFFFF
        return (self.state * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def below(self, n):
        if n <= 0:
            raise ValueError("bound must be positive")
        return self._next() % n

    def between(self, lo, hi):
        return lo + self.below(hi - lo + 1)

    def pick(self, items):
        return items[self.below(len(items))]

    def chance(self, num, den):
        return self.below(den) < num

    def shuffled(self, items):
        out = list(items)
        for i in range(len(out) - 1, 0, -1):
            j = self.below(i + 1)
            out[i], out[j] = out[j], out[i]
        return out


# --------------------------------------------------------------------------
# closed vocabularies
# --------------------------------------------------------------------------

ISO_LENGTHS = [20, 40, 45]
BOX_CLASSES = ["dry", "reefer", "hazard", "oog", "tank"]
ZONES = ["standard", "reefer", "hazard"]
SERVICE_GROUPS = ["sg_north", "sg_levant", "sg_gulf", "sg_baltic"]
MASS_UNITS = ["kg", "dt", "ct"]
MOVE_SOURCES = ["planning_desk", "gate_terminal", "crane_console", "yard_radio"]
EQUIP_CLASSES = ["rtg", "reachstacker", "straddle", "quay_crane"]
DESTINATIONS = ["PT_ALKENA", "PT_BRESHOR", "PT_CIRVAL", "PT_DUNMARK",
                "PT_ESKHOLM", "PT_FARNWAY"]

# The order the admission ladder is read in. The first rung that catches a
# move order settles it, and this order is not the alphabetical order of the
# rung codes.
LADDER_RUNGS = [
    "LR_UNKNOWN_BOX",
    "LR_SEALED_ZONE",
    "LR_STALE_SLOT",
    "LR_TIER_BEYOND_MAX",
    "LR_RESERVED_BOUND",
    "LR_DUPLICATE_ORDER",
]

REJECTION_TEXT = {
    "LR_UNKNOWN_BOX": "the order names a box the master register does not carry",
    "LR_SEALED_ZONE": "the destination block was sealed for the slot the order lands in",
    "LR_STALE_SLOT": "the order was raised against a slot that had already closed",
    "LR_TIER_BEYOND_MAX": "the destination tier lies beyond the block legal maximum",
    "LR_RESERVED_BOUND": "reserved capacity in the destination block bound the placement",
    "LR_DUPLICATE_ORDER": "an earlier order in the same cluster was already made canonical",
}

PROFILES = {
    "shipped": {
        "boxes": 224, "blocks": 14, "slots": 12, "vessels": 7,
        "moves": 306, "pool_scale": 100, "reserve_scale": 100,
        "sheet_index": 2, "equipment": 11, "names": 0,
        "orphan_cutoff": 0, "unknown_unit": 0, "orphan_obligation": 0,
    },
    "strained": {
        "boxes": 198, "blocks": 13, "slots": 12, "vessels": 6,
        "moves": 268, "pool_scale": 58, "reserve_scale": 145,
        "sheet_index": 3, "equipment": 10, "names": 1,
        "orphan_cutoff": 1, "unknown_unit": 1, "orphan_obligation": 1,
    },
    "wide": {
        "boxes": 271, "blocks": 17, "slots": 14, "vessels": 9,
        "moves": 352, "pool_scale": 147, "reserve_scale": 78,
        "sheet_index": 1, "equipment": 13, "names": 2,
        "orphan_cutoff": 1, "unknown_unit": 1, "orphan_obligation": 1,
    },
    "sparse": {
        "boxes": 154, "blocks": 11, "slots": 10, "vessels": 5,
        "moves": 214, "pool_scale": 121, "reserve_scale": 62,
        "sheet_index": 4, "equipment": 9, "names": 3,
        "orphan_cutoff": 1, "unknown_unit": 1, "orphan_obligation": 1,
    },
}

# Four sheet name pools, one per profile, drawn from one pool of six names so
# that a sheet name carries no information about which sheet is live. Across
# the four profiles the live sheet has four pairwise distinct file positions,
# four pairwise distinct sorted ranks and four distinct names, and it is never
# the first or the last sheet under either ordering. So no fixed reading of
# position, position from the end, sorted rank or name is right more than
# once, and every one of them is wrong on at least three profiles. The build
# asserts that property rather than trusting it.
SHEET_WORDS = ["Allocation", "Berthing", "Clearance", "Dispatch", "Equipment", "Forecast"]

SHEET_NAME_POOL = [
    ["Clearance", "Dispatch", "Berthing", "Allocation", "Equipment", "Forecast"],
    ["Equipment", "Allocation", "Forecast", "Clearance", "Berthing", "Dispatch"],
    ["Forecast", "Dispatch", "Allocation", "Equipment", "Berthing", "Clearance"],
    ["Berthing", "Forecast", "Clearance", "Allocation", "Equipment", "Dispatch"],
]

PROFILE_ORDER = ["shipped", "strained", "wide", "sparse"]


def _shift_id(seed):
    return "KP-%d-S%02d" % (2040 + (seed % 9), 3 + (seed % 21))


def _shift_reference(seed):
    return "QCR-%06d" % (seed % 1000000)


def mint_instance(seed, profile):
    """Build the whole shift as data. Nothing here decides an answer; the
    reference pipeline derives every published quantity from these papers."""
    cfg = PROFILES[profile]
    rng = Rng(seed)
    inst = {
        "seed": seed,
        "profile": profile,
        "shift_id": _shift_id(seed),
        "shift_reference": _shift_reference(seed),
        "cfg": cfg,
    }
    _mint_slots(inst, rng, cfg)
    _mint_blocks(inst, rng, cfg)
    _mint_vessels(inst, rng, cfg)
    _mint_boxes(inst, rng, cfg)
    _mint_reservations(inst, rng, cfg)
    _mint_moves(inst, rng, cfg)
    _mint_confirmations(inst, rng, cfg)
    _mint_equipment(inst, rng, cfg)
    _mint_cutoffs(inst, rng, cfg)
    _mint_stowage(inst, rng, cfg)
    _mint_exceptions(inst, rng, cfg)
    _mint_demand(inst, rng, cfg)
    _mint_controls(inst, rng, cfg)
    return inst


# --------------------------------------------------------------------------
# the shift grid
# --------------------------------------------------------------------------


def _mint_slots(inst, rng, cfg):
    slots = []
    for i in range(cfg["slots"]):
        slots.append({
            "slot_code": "SL%02d" % (i + 1),
            "ordinal": i + 1,
            "opens_min": i * 120,
            "closes_min": (i + 1) * 120,
            "shift_half": "first" if i < cfg["slots"] // 2 else "second",
        })
    inst["slots"] = slots
    inst["slot_index"] = dict((s["slot_code"], s) for s in slots)


# --------------------------------------------------------------------------
# yard geometry
#
# Every block carries a revision history. A revision is retired when the
# register says so, and a revision raised after the assessment slot has not
# taken effect. The applicable revision is the highest revision sequence that
# is neither retired nor raised after the assessment slot.
# --------------------------------------------------------------------------


def _mint_blocks(inst, rng, cfg):
    blocks = []
    rows = []
    for i in range(cfg["blocks"]):
        block_id = "BLK-%s%02d" % ("ABCDEFGHJKLMNPQRST"[i % 18], i + 1)
        zone = ZONES[i % 3] if i % 5 else rng.pick(ZONES)
        n_rows = rng.between(4, 9)
        tiers_max = rng.between(3, 5)
        # One block in every shift has no capacity at all. Zero capacity is a
        # published state distinct from a block the papers never mention.
        if i == cfg["blocks"] - 2:
            n_rows, tiers_max = 0, 0
        blocks.append({
            "block_id": block_id,
            "zone": zone,
            "rows": n_rows,
            "tiers_max": tiers_max,
            "slot_capacity": n_rows * tiers_max,
            "sealed_slots": [],
        })
    seal_target = blocks[3 % len(blocks)]
    first = rng.between(2, max(2, cfg["slots"] - 4))
    seal_target["sealed_slots"] = ["SL%02d" % s for s in range(first, first + 2)]

    for b in blocks:
        base = rng.between(3, 6)
        for r in range(base):
            retired = (r == base - 2 and base >= 4)
            future = (r == base - 1 and rng.chance(1, 3))
            live = (not retired) and (not future)
            rows.append({
                "block_id": b["block_id"],
                "revision_seq": r + 1,
                "zone": b["zone"] if live else rng.pick(ZONES),
                "rows": b["rows"] if live else max(0, b["rows"] + rng.between(-2, 2)),
                "tiers_max": b["tiers_max"] if live else max(0, b["tiers_max"] + rng.between(-1, 1)),
                "retired": retired,
                "future": future,
                "raised_slot": "SL%02d" % rng.between(1, cfg["slots"]),
            })
        applicable = [r for r in rows if r["block_id"] == b["block_id"]
                      and not r["retired"] and not r["future"]]
        keep = applicable[-1]
        keep["zone"] = b["zone"]
        keep["rows"] = b["rows"]
        keep["tiers_max"] = b["tiers_max"]
        b["applicable_revision"] = keep["revision_seq"]
    inst["blocks"] = blocks
    inst["block_index"] = dict((b["block_id"], b) for b in blocks)
    inst["block_revisions"] = rows


# --------------------------------------------------------------------------
# vessels, voyages and berths
# --------------------------------------------------------------------------


def _mint_vessels(inst, rng, cfg):
    vessels = []
    revisions = []
    for i in range(cfg["vessels"]):
        vid = "VS-%03d" % (101 + i * 7)
        berth = BERTHS[i % len(BERTHS)]
        # Service groups are laid out so that a pairing carries both shapes
        # the redistribution rule turns on. A berth working three vessels or
        # more gives its first two one service group and every later one a
        # group of its own, so the pairing holds a cross classification cell
        # of two and a cell of one: what a slot ceiling frees is placed on the
        # other member of the two, and the cell of one has nobody to give it
        # to, so those minutes stay unplaced. A berth working two vessels
        # gives each its own group, so both cells hold one member and
        # redistributing across the whole pairing is a different answer from
        # redistributing inside the cell. With a group per vessel everywhere
        # nothing could ever be placed; with one group per berth the cell
        # boundary itself would stop deciding anything.
        seat = i // len(BERTHS)
        at_berth = len(range(i % len(BERTHS), cfg["vessels"], len(BERTHS)))
        cell_seat = 0 if (at_berth >= 3 and seat <= 1) else seat
        vessels.append({
            "vessel_id": vid,
            "voyage": "V%04d%s" % (2200 + i * 13, "NESW"[i % 4]),
            "berth": berth,
            "service_group": SERVICE_GROUPS[cell_seat % len(SERVICE_GROUPS)],
            "destination": DESTINATIONS[i % len(DESTINATIONS)],
            "window_open": rng.between(0, 3) * 120,
            "window_close": rng.between(7, cfg["slots"]) * 120,
            "voyage_sequence": i + 1,
        })
        base = rng.between(3, 5)
        for r in range(base):
            withdrawn = (r == base - 2 and base >= 4)
            revisions.append({
                "vessel_id": vid,
                "revision_seq": r + 1,
                "withdrawn": withdrawn,
                "destination": vessels[-1]["destination"] if not withdrawn else rng.pick(DESTINATIONS),
                "service_group": vessels[-1]["service_group"] if not withdrawn else rng.pick(SERVICE_GROUPS),
                "berth": berth if not withdrawn else rng.pick(BERTHS),
                "raised_slot": "SL%02d" % rng.between(1, cfg["slots"]),
            })
        live = [r for r in revisions if r["vessel_id"] == vid and not r["withdrawn"]][-1]
        live["destination"] = vessels[-1]["destination"]
        live["service_group"] = vessels[-1]["service_group"]
        live["berth"] = berth
        vessels[-1]["applicable_revision"] = live["revision_seq"]
        # One call in every shift is revised and then the revision is
        # withdrawn, so the highest revision sequence is a withdrawn one and
        # the applicable revision is the one below it.
        if i == 1:
            revisions.append({
                "vessel_id": vid,
                "revision_seq": base + 1,
                "withdrawn": True,
                "destination": rng.pick(DESTINATIONS),
                "service_group": rng.pick(SERVICE_GROUPS),
                "berth": rng.pick(BERTHS),
                "raised_slot": "SL%02d" % rng.between(1, cfg["slots"]),
            })
    # The last call of the shift is cancelled outright: every one of its
    # revisions is withdrawn, so it has no applicable call at all and the
    # boxes booked on it carry no service group.
    doomed = vessels[-1]["vessel_id"]
    for r in revisions:
        if r["vessel_id"] == doomed:
            r["withdrawn"] = True
    inst["cancelled_vessel"] = doomed
    inst["vessels"] = vessels
    inst["vessel_index"] = dict((v["vessel_id"], v) for v in vessels)
    inst["vessel_revisions"] = revisions


# --------------------------------------------------------------------------
# the boxes
# --------------------------------------------------------------------------


def _mint_boxes(inst, rng, cfg):
    boxes = []
    placeable = [b for b in inst["blocks"] if b["slot_capacity"] > 0]
    for i in range(cfg["boxes"]):
        box_id = "CTR-%07d" % (1840000 + i * 37 + (inst["seed"] % 900))
        iso = rng.pick(ISO_LENGTHS)
        klass = BOX_CLASSES[i % len(BOX_CLASSES)] if i % 7 else rng.pick(BOX_CLASSES)
        vessel = rng.pick(inst["vessels"])
        unit = MASS_UNITS[i % 3]
        kg = rng.between(2400, 31800)
        if unit == "dt":
            value = kg // 100
            kg = value * 100
        elif unit == "ct":
            value = kg // 50
            kg = value * 50
        else:
            value = kg
        blk = placeable[i % len(placeable)]
        boxes.append({
            "box_id": box_id,
            "iso_length": iso,
            "box_class": klass,
            "vessel_id": vessel["vessel_id"],
            "service_group": vessel["service_group"],
            "destination": vessel["destination"],
            "mass_value": value,
            "mass_unit": unit,
            "mass_kg": kg,
            "home_block": blk["block_id"],
            "declared_seq": i + 1,
        })
    inst["boxes"] = boxes
    inst["box_index"] = dict((b["box_id"], b) for b in boxes)
    _mint_initial_stacks(inst, rng, cfg)


def _mint_initial_stacks(inst, rng, cfg):
    """Lay the boxes into the yard. One block is held back empty, so the
    published occupancy has to carry a block with no boxes in it."""
    occupancy = {}
    placements = []
    blocks = [b for b in inst["blocks"] if b["slot_capacity"] > 0]
    free = []
    for b in blocks:
        for row in range(1, b["rows"] + 1):
            for tier in range(1, b["tiers_max"] + 1):
                free.append((b["block_id"], row, tier))
    empty_block = blocks[-1]["block_id"] if blocks else None
    free = [f for f in free if f[0] != empty_block]
    order = rng.shuffled(free)
    yard_boxes = inst["boxes"][: (len(order) * 3) // 5]
    for i, box in enumerate(yard_boxes):
        if i >= len(order):
            break
        block_id, row, tier = order[i]
        placements.append({
            "box_id": box["box_id"],
            "block_id": block_id,
            "row_no": row,
            "tier_no": tier,
            "placed_slot": "SL%02d" % rng.between(1, cfg["slots"]),
        })
        occupancy[box["box_id"]] = (block_id, row, tier)
    inst["initial_placements"] = placements
    inst["initial_occupancy"] = occupancy
    inst["empty_block"] = empty_block


# --------------------------------------------------------------------------
# reserved capacity
#
# A reservation withholds slots in one block for one service group over a run
# of shift slots. Reserved slots are not free capacity, and a reservation
# whose quantity is absent withholds the whole remaining free capacity of the
# block, which is a different thing from withholding none of it.
# --------------------------------------------------------------------------


def _mint_reservations(inst, rng, cfg):
    out = []
    blocks = inst["blocks"]
    n = max(24, cfg["blocks"] * 3)
    for i in range(n):
        b = blocks[i % len(blocks)]
        first = rng.between(1, max(1, cfg["slots"] - 2))
        span = rng.between(1, 3)
        absent = (i % 11 == 5)
        free_now = max(0, b["slot_capacity"] - sum(
            1 for v in inst["initial_occupancy"].values() if v[0] == b["block_id"]))
        if i % 13 == 7:
            qty = free_now
        elif i % 17 == 9:
            qty = free_now + rng.between(1, 4)
        else:
            qty = rng.between(0, max(1, free_now // 2 + 1))
        out.append({
            "reservation_id": "RSV-%04d" % (2100 + i * 3),
            "block_id": b["block_id"],
            "service_group": SERVICE_GROUPS[i % len(SERVICE_GROUPS)],
            "first_slot": "SL%02d" % first,
            "last_slot": "SL%02d" % min(cfg["slots"], first + span),
            "quantity": None if absent else qty,
        })
    inst["reservations"] = out


# --------------------------------------------------------------------------
# move orders
#
# An order carries the minute it was raised, not the slot it belongs to. The
# slot is derived, and a minute that falls exactly on a slot boundary belongs
# to the slot that is closing rather than to the one that is opening.
# --------------------------------------------------------------------------


def _mint_moves(inst, rng, cfg):
    orders = []
    boxes = inst["boxes"]
    blocks = [b for b in inst["blocks"] if b["slot_capacity"] > 0]
    sealed = [b for b in inst["blocks"] if b["sealed_slots"]]
    last_min = cfg["slots"] * 120
    for i in range(cfg["moves"]):
        box = boxes[i % len(boxes)]
        source = MOVE_SOURCES[i % len(MOVE_SOURCES)]
        dest = blocks[(i * 5 + 3) % len(blocks)]
        # Every twenty first order lands exactly on a slot boundary.
        if i % 21 == 0:
            raised = ((i % cfg["slots"]) + 1) * 120
        else:
            raised = rng.between(1, last_min - 1)
        tier = rng.between(1, max(1, dest["tiers_max"]))
        row = rng.between(1, max(1, dest["rows"]))
        order = {
            "order_id": "MO-%05d" % (41000 + i * 7),
            "box_id": box["box_id"],
            "source_system": source,
            "event_seq": (i * 13) % 997,
            "raised_min": raised,
            "to_block": dest["block_id"],
            "to_row": row,
            "to_tier": tier,
            "priority_band": rng.between(1, 5),
            "depends_on": "",
            "cluster_tag": "",
        }
        # Deliberate boundary and rejection fixtures, laid down by index so
        # every profile carries the same shapes at different densities.
        if i % 29 == 4:
            order["box_id"] = "CTR-9%06d" % (i * 3)          # unknown box
        if i % 31 == 6 and sealed:
            order["to_block"] = sealed[0]["block_id"]
            order["raised_min"] = (int(sealed[0]["sealed_slots"][0][2:]) - 1) * 120 + 45
        if i % 37 == 11:
            order["raised_min"] = last_min + rng.between(30, 400)  # stale slot
        if i % 23 == 8:
            order["to_tier"] = dest["tiers_max"] + 1               # one beyond max
        if i % 19 == 3:
            order["to_tier"] = max(1, dest["tiers_max"])           # exactly at max
        # Orders two rungs catch at once. The printed rung order only decides
        # anything on an order more than one rung would settle, so without
        # these the relative order of rungs one and two, and of rungs three
        # and four, would change nothing anywhere and would grade nothing.
        if i % 41 == 9 and sealed:
            order["box_id"] = "CTR-8%06d" % (i * 5)                # unknown box
            order["to_block"] = sealed[0]["block_id"]              # and sealed
            order["raised_min"] = (int(sealed[0]["sealed_slots"][0][2:]) - 1) * 120 + 45
        if i % 43 == 12:
            order["raised_min"] = last_min + 60 + (i % 90)         # stale slot
            order["to_tier"] = dest["tiers_max"] + 2               # and beyond max
        orders.append(order)

    # Clusters: an order repeated across sources inside one slot. The cluster
    # tag is published by the papers, so the clustering itself is given and
    # only the canonical pick inside a cluster is derived.
    for i in range(0, len(orders) - 3, 17):
        tag = "CL-%04d" % (700 + i)
        base = orders[i]
        for k in range(3):
            twin = orders[i + k]
            twin["cluster_tag"] = tag
            twin["box_id"] = base["box_id"]
            twin["raised_min"] = base["raised_min"]
            twin["source_system"] = MOVE_SOURCES[k % len(MOVE_SOURCES)]
            twin["event_seq"] = base["event_seq"] + k
        # One cluster in every shift is tied on every published key except the
        # order identifier itself.
        if i == 17:
            orders[i + 1]["source_system"] = orders[i]["source_system"]
            orders[i + 1]["event_seq"] = orders[i]["event_seq"]
        if i % 51 == 34:
            # Some clusters are repeated inside one source system rather than
            # across several. Their members are then ordered by event
            # sequence alone, so the last member is the one the duplicate
            # rung reaches, and that member carries a box the master register
            # does not know. Both the unknown box rung and the duplicate rung
            # catch it, and RULE Y07.7 decides which code it is published
            # under. Without this the two rungs never meet on one order and
            # the sentence that orders them would grade nothing.
            for k in range(3):
                orders[i + k]["source_system"] = MOVE_SOURCES[0]
                orders[i + k]["event_seq"] = base["event_seq"] + k
            orders[i + 2]["box_id"] = "CTR-6%06d" % (i * 11)
    for o in orders:
        if not o["cluster_tag"]:
            o["cluster_tag"] = "CL-%s" % o["order_id"][3:]

    _mint_dependencies(inst, rng, cfg, orders)
    inst["orders"] = orders
    inst["order_index"] = dict((o["order_id"], o) for o in orders)


def _mint_dependencies(inst, rng, cfg, orders):
    """A shuffle chain: one order may have to run after another. The graph
    carries deliberate cycles, one of which contains the highest priority edge
    in its component."""
    edges = []
    n = len(orders)
    for i in range(0, n - 6, 11):
        a, b = orders[i], orders[i + 3]
        edges.append({
            "edge_id": "DE-%05d" % (60000 + i * 3),
            "before_order": a["order_id"],
            "after_order": b["order_id"],
            "edge_weight": rng.between(1, 9),
        })
    # Explicit cycles, laid out differently on every profile so the component
    # count, the member counts and the removed edges all move between shifts
    # and no shift's cycle report can be carried inside the program. The
    # second cycle of each layout carries the heaviest edge in its component,
    # so a rule that protects heavy edges and a rule that removes the lowest
    # weight edge disagree there.
    cycle_specs = [
        [(5, 3), (41, 4), (83, 3), (119, 2)],
        [(7, 2), (39, 4), (81, 5), (117, 3)],
        [(9, 4), (43, 4), (85, 2), (121, 3), (163, 3)],
        [(3, 5), (37, 4), (79, 3)],
    ][PROFILE_ORDER.index(inst["profile"])]
    cycles = []
    for spec_position, (start, size) in enumerate(cycle_specs):
        if start + size + 1 >= n:
            continue
        members = [orders[start + k] for k in range(size)]
        ring = []
        for k in range(size):
            a = members[k]
            b = members[(k + 1) % size]
            weight = rng.between(2, 8)
            ring.append({
                "edge_id": "DE-%05d" % (70000 + start * 5 + k),
                "before_order": a["order_id"],
                "after_order": b["order_id"],
                "edge_weight": weight,
            })
        if spec_position == 1:
            # A chord across the four order ring, closing a shorter cycle over
            # the first three orders. The two edges the two cycles share are
            # the heaviest in the component, so the protection holds them and
            # the edge that goes is one the shorter cycle does not use. That
            # leaves the component cyclic, and the components have to be found
            # again before the next removal.
            ring[0]["edge_weight"] = 9
            ring[1]["edge_weight"] = 9
            ring[2]["edge_weight"] = 2
            ring[3]["edge_weight"] = 8
            ring.append({
                "edge_id": "DE-%05d" % (70000 + start * 5 + size),
                "before_order": members[2]["order_id"],
                "after_order": members[0]["order_id"],
                "edge_weight": 7,
            })
        # The removable edge is the one with the lowest weight; ties inside a
        # ring are broken by the edge identifier, so make one ring tie.
        if spec_position == 2:
            ring[0]["edge_weight"] = 2
            ring[1]["edge_weight"] = 2
        edges.extend(ring)
        cycles.append([m["order_id"] for m in members])
    inst["dependency_edges"] = edges
    inst["planted_cycles"] = cycles


# --------------------------------------------------------------------------
# physical confirmations
#
# The crane console confirms what the yard actually did. A confirmation is
# evidence about a movement, not an instruction: it never resurrects an order
# the ladder set aside, and it may arrive before the order it confirms.
# --------------------------------------------------------------------------


def _mint_confirmations(inst, rng, cfg):
    out = []
    orders = inst["orders"]
    for i, o in enumerate(orders):
        if i % 9 == 4:
            continue                      # a planned move with no confirmation
        drift = rng.between(-40, 40)
        rec = {
            "confirm_id": "CF-%05d" % (52000 + i * 3),
            "order_id": o["order_id"],
            "box_id": o["box_id"],
            "confirmed_min": max(0, o["raised_min"] + drift),
            "equipment_id": "EQ-%03d" % (200 + (i % max(1, cfg["equipment"]))),
            "landed_block": o["to_block"],
            "landed_row": o["to_row"],
            "landed_tier": o["to_tier"],
            "confirm_state": "landed",
        }
        if i % 26 == 7:
            rec["confirmed_min"] = max(0, o["raised_min"] - rng.between(60, 200))
        if i % 34 == 12:
            rec["confirm_state"] = "aborted"
        if i % 47 == 15:
            rec["order_id"] = ""          # a confirmation with no order behind it
            rec["confirm_id"] = "CF-%05d" % (58000 + i * 3)
        # A unit outside the handling register, so it has no applicable
        # revision and stage Y10 records EQ_UNKNOWN_UNIT against the movement.
        if cfg.get("unknown_unit") and i % 53 == 11 and rec["order_id"]:
            rec["equipment_id"] = "EQ-%03d" % (200 + cfg["equipment"] + 4)
        out.append(rec)
        # Every nineteenth order is confirmed twice. The later confirmation
        # says the lift was aborted, so which of the two counts decides the
        # movement state.
        if i % 19 == 9:
            twin = dict(rec)
            twin["confirm_id"] = "CF-6%04d" % (1000 + i)
            twin["confirmed_min"] = rec["confirmed_min"] + rng.between(20, 90)
            twin["confirm_state"] = "aborted"
            out.append(twin)
    inst["confirmations"] = out


# --------------------------------------------------------------------------
# handling equipment
# --------------------------------------------------------------------------


def _mint_equipment(inst, rng, cfg):
    units = []
    revisions = []
    for i in range(cfg["equipment"]):
        eid = "EQ-%03d" % (200 + i)
        klass = EQUIP_CLASSES[i % len(EQUIP_CLASSES)]
        limit = rng.between(6, 26)
        if i == 2:
            limit = 0                     # an equipment unit with no allowance
        if i == 3:
            limit = 1                     # a unit that may carry exactly one
        if i == 4:
            limit = 2                     # and one that may carry exactly two
        units.append({
            "equipment_id": eid,
            "equipment_class": klass,
            "move_limit": limit,
            "base_minutes": 4 + (i % 5),
        })
        base = rng.between(3, 5)
        for r in range(base):
            retired = (r == base - 2 and base >= 4)
            revisions.append({
                "equipment_id": eid,
                "revision_seq": r + 1,
                "equipment_class": klass if not retired else rng.pick(EQUIP_CLASSES),
                "move_limit": limit if not retired else max(0, limit + rng.between(-8, 8)),
                "base_minutes": units[-1]["base_minutes"] if not retired else rng.between(2, 9),
                "retired": retired,
            })
        live = [r for r in revisions if r["equipment_id"] == eid and not r["retired"]][-1]
        live["equipment_class"] = klass
        live["move_limit"] = limit
        live["base_minutes"] = units[-1]["base_minutes"]
        units[-1]["applicable_revision"] = live["revision_seq"]
    inst["equipment"] = units
    inst["equipment_index"] = dict((u["equipment_id"], u) for u in units)
    inst["equipment_revisions"] = revisions



# --------------------------------------------------------------------------
# vessel cutoffs
#
# A cutoff is a minute on the shift grid. An event that lands exactly on the
# cutoff minute is inside the cutoff, not outside it.
# --------------------------------------------------------------------------


def _mint_cutoffs(inst, rng, cfg):
    out = []
    orphan = len(inst["vessels"]) - 2 if cfg.get("orphan_cutoff") else -1
    for i, v in enumerate(inst["vessels"]):
        base = rng.between(3, cfg["slots"] - 1) * 120
        # Every notice this vessel carries is superseded, so no notice is in
        # force for it and stage Y12 settles its boxes at EL_NO_CUTOFF.
        all_superseded = (i == orphan)
        for r in range(rng.between(2, 4)):
            superseded = all_superseded or (r > 0 and rng.chance(1, 2))
            out.append({
                "notice_id": "CO-%05d" % (80000 + i * 17 + r),
                "vessel_id": v["vessel_id"],
                "notice_seq": r + 1,
                "cutoff_min": base + (0 if not superseded else rng.between(-240, 240)),
                "superseded": superseded,
            })
        standing = [c for c in out
                    if c["vessel_id"] == v["vessel_id"] and not c["superseded"]]
        if not standing:
            v["cutoff_min"] = None
            v["cutoff_notice"] = None
            continue
        live = standing[-1]
        live["cutoff_min"] = base
        v["cutoff_min"] = base
        v["cutoff_notice"] = live["notice_id"]
    inst["cutoffs"] = out


# --------------------------------------------------------------------------
# stowage obligations
# --------------------------------------------------------------------------


def _mint_stowage(inst, rng, cfg):
    out = []
    cancelled = inst.get("cancelled_vessel")
    # One box of a vessel that still holds an applicable call is struck off the
    # stowage list, so the eligibility chain of stage Y12 passes the vessel rung
    # and settles that box at EL_NO_OBLIGATION. Without it the rung the sentinel
    # note names as unreached is reached by no graded shift. The pick draws no
    # randomness, so a profile that leaves the flag clear mints byte for byte
    # what it minted before.
    standing = [b["box_id"] for b in inst["boxes"] if b["vessel_id"] != cancelled]
    orphaned = standing[len(standing) // 3] if (cfg.get("orphan_obligation") and standing) else None
    inst["orphan_obligation_box"] = orphaned
    for i, box in enumerate(inst["boxes"]):
        # The cancelled call was struck off the stowage list as well, so its
        # boxes have neither an applicable call nor an obligation and the
        # order the eligibility reasons are put in decides what they carry.
        if box["vessel_id"] == cancelled:
            continue
        if box["box_id"] == orphaned:
            continue
        out.append({
            "obligation_id": "SO-%05d" % (90000 + i * 3),
            "box_id": box["box_id"],
            "vessel_id": box["vessel_id"],
            "bay_no": rng.between(1, 48),
            "stow_sequence": (i * 7) % 401,
            "hold_flag": "yes" if i % 23 == 5 else "no",
            "box_class": box["box_class"],
        })

    # Deliberate ties on the ordering keys. A vessel's boxes are ordered by
    # class rank first, so a tie only reaches the second key inside one class
    # of one vessel, and only reaches the third and fourth keys when the
    # second ties as well. Inside every class of every vessel the second
    # obligation repeats the stow sequence of the first, and the third
    # repeats its bay number too, so the ordering has to fall through to the
    # bay number and then to the box identifier. Without these the third and
    # fourth keys the directive names would settle nothing on any shift.
    groups = {}
    for r in out:
        groups.setdefault((r["vessel_id"], r["box_class"]), []).append(r)
    for key in sorted(groups):
        rows = groups[key]
        if len(rows) > 1:
            rows[1]["stow_sequence"] = rows[0]["stow_sequence"]
        if len(rows) > 2:
            rows[2]["stow_sequence"] = rows[0]["stow_sequence"]
            rows[2]["bay_no"] = rows[0]["bay_no"]
        if len(rows) > 3:
            rows[3]["bay_no"] = rows[0]["bay_no"]
    for r in out:
        del r["box_class"]

    inst["stowage"] = out


# --------------------------------------------------------------------------
# operational exceptions
# --------------------------------------------------------------------------


def _mint_exceptions(inst, rng, cfg):
    out = []
    kinds = ["zone_waiver", "tier_waiver", "cutoff_waiver", "reservation_release"]
    n = max(24, cfg["blocks"] * 2)
    for i in range(n):
        target = inst["orders"][(i * 11) % len(inst["orders"])]
        out.append({
            "exception_id": "EX-%04d" % (4400 + i * 3),
            "exception_kind": kinds[i % len(kinds)],
            "target_kind": "order" if i % 3 else "block",
            "target_id": target["order_id"] if i % 3 else inst["blocks"][i % len(inst["blocks"])]["block_id"],
            "granted_slot": "SL%02d" % rng.between(1, cfg["slots"]),
            "withdrawn": (i % 8 == 3),
        })
    inst["exceptions"] = out


# --------------------------------------------------------------------------
# quay demand and berth windows
# --------------------------------------------------------------------------


def _mint_demand(inst, rng, cfg):
    windows = []
    for i, b in enumerate(BERTHS):
        for s in inst["slots"]:
            base = rng.between(40, 90) * cfg["pool_scale"] // 100
            windows.append({
                "berth_id": b,
                "slot_code": s["slot_code"],
                "crane_minutes": max(0, base),
                "crane_count": rng.between(1, 3),
            })
    inst["berth_windows"] = windows

    returns = []
    for i, v in enumerate(inst["vessels"]):
        for s in inst["slots"]:
            returns.append({
                "return_id": "QD-%05d" % (10000 + i * 40 + s["ordinal"]),
                "vessel_id": v["vessel_id"],
                "slot_code": s["slot_code"],
                "declared_minutes": rng.between(10, 70),
                "return_state": "filed" if (i + s["ordinal"]) % 13 else "void",
            })
    inst["demand_returns"] = returns


# --------------------------------------------------------------------------
# the control values
#
# These are the numbers that live only in the workbook, the memo and the
# directive. Nothing else in the corpus carries them.
# --------------------------------------------------------------------------


def _mint_controls(inst, rng, cfg):
    profile = inst["profile"]
    idx = PROFILE_ORDER.index(profile)
    damp_num = [7, 5, 9, 11][idx]
    damp_den = [16, 12, 20, 24][idx]
    controls = {
        "sheet_names": SHEET_NAME_POOL[cfg["names"]],
        "live_sheet_index": cfg["sheet_index"],
        "damping_num": damp_num,
        "damping_den": damp_den,
        "decitonne_kilograms": 100,
        "centner_kilograms": 50,
        "teu_factor": {20: 1, 40: 2, 45: 2},
        "plug_ceiling": {"standard": 0, "reefer": 6 + idx, "hazard": 3 + idx},
        "pass_budget": [5, 4, 7, 6][idx],
        "minimum_step": [3, 2, 4, 3][idx],
        "protection_depth": [2, 3, 2, 4][idx],
        "surcharge_ladder": [
            {"tier_depth": 1, "surcharge_cents": 0},
            {"tier_depth": 2, "surcharge_cents": 450 + idx * 25},
            {"tier_depth": 3, "surcharge_cents": 900 + idx * 40},
            {"tier_depth": 4, "surcharge_cents": 1600 + idx * 55},
        ],
        # The class rank register and the stowage key order are terminal
        # policy, not physics, and the program contract forbids holding
        # either inside the program. Both therefore move between profiles:
        # every class takes a different rank on every shift, and the two
        # middle ordering keys change places, so a program that carries
        # either one is right on one shift and wrong on the other three.
        "class_rank": [
            {"reefer": 1, "hazard": 2, "oog": 3, "tank": 4, "dry": 5},
            {"hazard": 1, "reefer": 2, "tank": 3, "dry": 4, "oog": 5},
            {"oog": 1, "tank": 2, "dry": 3, "reefer": 4, "hazard": 5},
            {"dry": 1, "oog": 2, "hazard": 3, "tank": 4, "reefer": 5},
        ][idx],
        "stowage_keys": ["class_rank"] + [
            ["stow_sequence", "bay_no", "box_id"],
            ["bay_no", "stow_sequence", "box_id"],
            ["stow_sequence", "bay_no", "box_id"],
            ["bay_no", "stow_sequence", "box_id"],
        ][idx],
        "base_move_cents": 2750 + idx * 30,
    }
    inst["controls"] = controls

"""Working paper writers: delimited, spreadsheet, document and database."""

# --------------------------------------------------------------------------
# delimited and structured writers
# --------------------------------------------------------------------------


def _join(sep: str, values) -> str:
    return sep.join("" if v is None else str(v) for v in values)


def write_rows(path, header, rows, sep):
    lines = [_join(sep, header)]
    for row in rows:
        lines.append(_join(sep, row))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_lines(path, lines):
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path, records):
    out = []
    for rec in records:
        out.append(json.dumps(rec, separators=(",", ":"), sort_keys=False))
    path.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")


# --------------------------------------------------------------------------
# spreadsheet writer (minimal, stdlib only, real OOXML)
# --------------------------------------------------------------------------


def _cell_ref(col: int, row: int) -> str:
    name = ""
    while col > 0:
        col, rem = divmod(col - 1, 26)
        name = chr(65 + rem) + name
    return "%s%d" % (name, row)


def _xml_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace('"', "&quot;"))


def _sheet_xml(rows: list, shared: list, shared_idx: dict) -> str:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    out.append('<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">')
    out.append("<sheetData>")
    for ri, row in enumerate(rows, start=1):
        out.append('<row r="%d">' % ri)
        for ci, val in enumerate(row, start=1):
            if val is None or val == "":
                continue
            ref = _cell_ref(ci, ri)
            sval = str(val)
            is_num = True
            try:
                int(sval)
            except ValueError:
                is_num = False
            if is_num:
                out.append('<c r="%s"><v>%s</v></c>' % (ref, sval))
            else:
                if sval not in shared_idx:
                    shared_idx[sval] = len(shared)
                    shared.append(sval)
                out.append('<c r="%s" t="s"><v>%d</v></c>' % (ref, shared_idx[sval]))
        out.append("</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out)


def write_xlsx(path, sheets: dict) -> None:
    shared: list = []
    shared_idx: dict = {}
    sheet_xmls = [(name, _sheet_xml(rows, shared, shared_idx)) for name, rows in sheets.items()]

    ss = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    ss.append('<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
              'count="%d" uniqueCount="%d">' % (len(shared), len(shared)))
    for item in shared:
        ss.append("<si><t xml:space=\"preserve\">%s</t></si>" % _xml_escape(item))
    ss.append("</sst>")

    ctypes = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    ctypes.append('<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">')
    ctypes.append('<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>')
    ctypes.append('<Default Extension="xml" ContentType="application/xml"/>')
    ctypes.append('<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>')
    ctypes.append('<Override PartName="/xl/sharedStrings.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml"/>')
    for i, _ in enumerate(sheet_xmls, start=1):
        ctypes.append('<Override PartName="/xl/worksheets/sheet%d.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' % i)
    ctypes.append("</Types>")

    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                 "</Relationships>")

    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    wb.append('<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
              'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">')
    wb.append("<sheets>")
    for i, (name, _) in enumerate(sheet_xmls, start=1):
        wb.append('<sheet name="%s" sheetId="%d" r:id="rId%d"/>' % (_xml_escape(name), i, i))
    wb.append("</sheets></workbook>")

    wb_rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>']
    wb_rels.append('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">')
    for i, _ in enumerate(sheet_xmls, start=1):
        wb_rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet%d.xml"/>' % (i, i))
    wb_rels.append('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings" Target="sharedStrings.xml"/>' % (len(sheet_xmls) + 1))
    wb_rels.append("</Relationships>")

    entries = [
        ("[Content_Types].xml", "".join(ctypes)),
        ("_rels/.rels", root_rels),
        ("xl/workbook.xml", "".join(wb)),
        ("xl/_rels/workbook.xml.rels", "".join(wb_rels)),
        ("xl/sharedStrings.xml", "".join(ss)),
    ]
    for i, (_, xml) in enumerate(sheet_xmls, start=1):
        entries.append(("xl/worksheets/sheet%d.xml" % i, xml))

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            zf.writestr(info, payload)


# --------------------------------------------------------------------------
# word processing writer (minimal, stdlib only, real OOXML)
# --------------------------------------------------------------------------


def _docx_paragraph(text: str) -> str:
    return ('<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>'
            % _xml_escape(text))


def _docx_table(rows: list) -> str:
    out = ['<w:tbl><w:tblPr><w:tblW w:w="0" w:type="auto"/></w:tblPr>']
    for row in rows:
        out.append("<w:tr>")
        for cell in row:
            out.append('<w:tc><w:tcPr><w:tcW w:w="1800" w:type="dxa"/></w:tcPr>'
                       '<w:p><w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p></w:tc>'
                       % _xml_escape(str(cell)))
        out.append("</w:tr>")
    out.append("</w:tbl>")
    return "".join(out)


def write_docx(path, blocks: list) -> None:
    """blocks is a list of ('p', text) and ('table', rows) pairs."""
    body = []
    for kind, payload in blocks:
        if kind == "p":
            body.append(_docx_paragraph(payload))
        else:
            body.append(_docx_table(payload))
            body.append(_docx_paragraph(""))
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body>" + "".join(body) +
                '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/></w:sectPr>'
                "</w:body></w:document>")

    ctypes = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
              '<Default Extension="xml" ContentType="application/xml"/>'
              '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
              "</Types>")
    root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                 "</Relationships>")
    doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')

    entries = [
        ("[Content_Types].xml", ctypes),
        ("_rels/.rels", root_rels),
        ("word/document.xml", document),
        ("word/_rels/document.xml.rels", doc_rels),
    ]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries:
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            zf.writestr(info, payload)


# --------------------------------------------------------------------------
# pdf writer (minimal, stdlib only, real PDF 1.4, no embedded timestamp)
# --------------------------------------------------------------------------


def write_pdf(path, lines: list) -> None:
    def esc(t: str) -> str:
        return t.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    pages = [lines[i:i + 52] for i in range(0, len(lines), 52)] or [[""]]
    objects: list = []
    n_pages = len(pages)
    font_obj = 3 + 2 * n_pages
    kids = " ".join("%d 0 R" % (3 + 2 * i) for i in range(n_pages))
    objects.append("<< /Type /Catalog /Pages 2 0 R >>")
    objects.append("<< /Type /Pages /Kids [%s] /Count %d >>" % (kids, n_pages))
    for i, page_lines in enumerate(pages):
        content = "BT /F1 9 Tf 34 754 Td 11 TL\n"
        for ln in page_lines:
            content += "(%s) Tj T*\n" % esc(ln)
        content += "ET"
        cbytes = content.encode("latin-1", "replace")
        page_obj = 3 + 2 * i
        objects.append("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       "/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>"
                       % (font_obj, page_obj + 1))
        objects.append((cbytes, "<< /Length %d >>" % len(cbytes)))
    objects.append("<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(out.tell())
        if isinstance(obj, tuple):
            cbytes, hdr = obj
            out.write(("%d 0 obj\n%s\nstream\n" % (i, hdr)).encode("latin-1"))
            out.write(cbytes)
            out.write(b"\nendstream\nendobj\n")
        else:
            out.write(("%d 0 obj\n%s\nendobj\n" % (i, obj)).encode("latin-1"))
    xref_pos = out.tell()
    n = len(objects) + 1
    out.write(("xref\n0 %d\n" % n).encode("latin-1"))
    out.write(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.write(("%010d 00000 n \n" % off).encode("latin-1"))
    out.write(("trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
               % (n, xref_pos)).encode("latin-1"))
    path.write_bytes(out.getvalue())


def write_sqlite(path, tables: dict) -> None:
    if path.exists():
        path.unlink()
    con = sqlite3.connect(str(path))
    cur = con.cursor()
    for tname, (cols, rows) in tables.items():
        cur.execute("CREATE TABLE %s (%s)" % (tname, ", ".join("%s TEXT" % c for c in cols)))
        ph = ", ".join("?" for _ in cols)
        cur.executemany("INSERT INTO %s VALUES (%s)" % (tname, ph), rows)
    con.commit()
    con.close()

"""The terminal's registers, journals and feeds."""

NOT_SUPPLIED = "-"


def _pad_rng(inst, salt):
    """A second stream for padding rows, so decoy material never disturbs the
    minting of the shift itself."""
    return Rng((inst["seed"] * 1000003 + salt) & 0xFFFFFFFFFFFFFFFF)


def _prior_shifts(inst, n):
    return ["KP-%d-S%02d" % (2039, 1 + (i % 24)) for i in range(n)]


def _iso_text(rng, length):
    """Three spellings of one length. The register is not normalised."""
    return rng.pick(["%d" % length, "%dFT" % length, "%dft" % length])


# --------------------------------------------------------------------------
# the boxes
# --------------------------------------------------------------------------


def write_box_papers(inst, root):
    rng = _pad_rng(inst, 11)
    rows = []
    for b in inst["boxes"]:
        rows.append([b["box_id"], 1, _iso_text(rng, b["iso_length"]), b["box_class"],
                     b["vessel_id"], b["declared_seq"], inst["shift_id"], "no"])
    # Retired statements from earlier shifts. They name this terminal's boxes
    # but carry an earlier shift identifier, so they are set aside.
    # Every twenty ninth box was restated after its live row and the
    # restatement was retired. Its revision sequence is the highest the box
    # has, so a reader that takes the highest sequence without setting retired
    # rows aside takes the restatement.
    for i, b in enumerate(inst["boxes"]):
        if i % 29 == 13:
            rows.append([b["box_id"], 2, _iso_text(rng, rng.pick(ISO_LENGTHS)),
                         rng.pick(BOX_CLASSES),
                         rng.pick(inst["vessels"])["vessel_id"],
                         b["declared_seq"], inst["shift_id"], "yes"])
    priors = _prior_shifts(inst, 24)
    i = 0
    while len(rows) < 248:
        b = inst["boxes"][i % len(inst["boxes"])]
        rows.append([b["box_id"], 0, _iso_text(rng, rng.pick(ISO_LENGTHS)),
                     rng.pick(BOX_CLASSES), rng.pick(inst["vessels"])["vessel_id"],
                     b["declared_seq"], priors[i % len(priors)], "yes"])
        i += 1
    write_rows(root / "box_master_register.csv",
               ["box_id", "revision_seq", "iso_length", "box_class", "vessel_id",
                "declared_seq", "shift_id", "retired"], rows, ",")

    # Mass declarations. Three unit registers live side by side and the unit
    # column is the only thing that says which one a row is written in. A
    # superseded declaration carries a later declaration sequence for the same
    # box, and an absent value is written as the not supplied marker.
    rng = _pad_rng(inst, 12)
    rows = []
    for i, b in enumerate(inst["boxes"]):
        # Every seventeenth box filed its declaration with the mass left out.
        # An absent mass is not a mass of zero.
        value = NOT_SUPPLIED if i % 17 == 8 else b["mass_value"]
        rows.append([b["box_id"], 2, value, b["mass_unit"], "filed"])
    # Every twenty third box was reweighed after its declaration was filed
    # and the reweigh was itself superseded. That row carries a higher
    # declaration sequence than the filed one, so a reader that takes the
    # highest sequence without first setting the superseded rows aside takes
    # the wrong mass.
    for i, b in enumerate(inst["boxes"]):
        if i % 23 == 11:
            rows.append([b["box_id"], 3, rng.between(1000, 30000),
                         rng.pick(MASS_UNITS), "superseded"])
    i = 0
    while len(rows) < 284:
        b = inst["boxes"][i % len(inst["boxes"])]
        if i % 9 == 4:
            rows.append([b["box_id"], 1, NOT_SUPPLIED, b["mass_unit"], "superseded"])
        else:
            rows.append([b["box_id"], 1, rng.between(1000, 30000),
                         rng.pick(MASS_UNITS), "superseded"])
        i += 1
    write_rows(root / "mass_declaration_returns.psv",
               ["box_id", "declaration_seq", "mass_value", "mass_unit", "state"],
               rows, "|")

    # The opening stack. A box the snapshot does not place is on the quay or
    # on a truck and has no yard position at the opening instant.
    rows = []
    for p in inst["initial_placements"]:
        rows.append([p["box_id"], p["block_id"], p["row_no"], p["tier_no"],
                     p["placed_slot"], "stacked"])
    rng = _pad_rng(inst, 13)
    # A box that left the yard before the shift opened keeps the address it
    # was lifted from on its row. The stack state is the only thing that says
    # the box is no longer standing there.
    placeable = [b for b in inst["blocks"] if b["slot_capacity"] > 0]
    i = 0
    while len(rows) < 232:
        b = inst["boxes"][(i * 3) % len(inst["boxes"])]
        if i % 5 == 2 and placeable:
            blk = placeable[i % len(placeable)]
            rows.append([b["box_id"], blk["block_id"], 1 + (i % max(1, blk["rows"])),
                         1 + (i % max(1, blk["tiers_max"])),
                         "SL%02d" % rng.between(1, inst["cfg"]["slots"]), "off_yard"])
        else:
            rows.append([b["box_id"], NOT_SUPPLIED, NOT_SUPPLIED, NOT_SUPPLIED,
                         "SL%02d" % rng.between(1, inst["cfg"]["slots"]), "off_yard"])
        i += 1
    write_rows(root / "stack_inventory_snapshot.csv",
               ["box_id", "block_id", "row_no", "tier_no", "placed_slot", "stack_state"],
               rows, ",")

    # A supplement that restates some box classes. It is a working note and
    # the master register outranks it wherever the two disagree.
    rng = _pad_rng(inst, 14)
    rows = []
    for i, b in enumerate(inst["boxes"]):
        klass = b["box_class"] if i % 6 else rng.pick(BOX_CLASSES)
        rows.append([b["box_id"], klass, rng.between(1, 9), "supplement"])
    while len(rows) < 228:
        b = inst["boxes"][len(rows) % len(inst["boxes"])]
        rows.append([b["box_id"], rng.pick(BOX_CLASSES), rng.between(1, 9), "supplement"])
    write_rows(root / "box_class_supplement.csv",
               ["box_id", "box_class", "handling_grade", "origin"], rows, ",")


# --------------------------------------------------------------------------
# the yard
# --------------------------------------------------------------------------


def write_yard_papers(inst, root):
    rng = _pad_rng(inst, 21)
    rows = []
    for r in inst["block_revisions"]:
        rows.append([r["block_id"], r["revision_seq"], r["zone"], r["rows"],
                     r["tiers_max"], r["raised_slot"],
                     "yes" if r["retired"] else "no",
                     "yes" if r["future"] else "no", inst["shift_id"]])
    # Blocks that were decommissioned before this shift. They are carried so
    # the register reads back over several shifts, and the topology paper is
    # what says which blocks are in force now.
    # A block that was surveyed for this shift and then left out of the
    # topology. It is not in force, so nothing may be placed in it and it is
    # published nowhere, however current its geometry row looks.
    rows.append(["BLK-Y01", 2, rng.pick(ZONES), rng.between(4, 8),
                 rng.between(3, 5), "SL01", "no", "no", inst["shift_id"]])
    priors = _prior_shifts(inst, 24)
    i = 0
    while len(rows) < 208:
        bid = "BLK-Z%02d" % (10 + (i % 37))
        rows.append([bid, 1 + (i % 3), rng.pick(ZONES), rng.between(3, 8),
                     rng.between(2, 5), "SL%02d" % rng.between(1, inst["cfg"]["slots"]),
                     "yes", "no", priors[i % len(priors)]])
        i += 1
    write_rows(root / "block_geometry_register.csv",
               ["block_id", "revision_seq", "zone", "rows", "tiers_max",
                "raised_slot", "retired", "future", "shift_id"], rows, ",")

    # Per slot availability. A block is sealed for a slot when this paper says
    # so; a block with no capacity at all is a different state from a block
    # that is sealed, and both are published.
    rows = []
    for b in inst["blocks"]:
        for s in inst["slots"]:
            sealed = "yes" if s["slot_code"] in b["sealed_slots"] else "no"
            rows.append([s["slot_code"], b["block_id"], sealed,
                         "yes" if b["slot_capacity"] else "no"])
    i = 0
    while len(rows) < 208:
        rows.append(["SL%02d" % (1 + (i % inst["cfg"]["slots"])),
                     "BLK-Z%02d" % (10 + (i % 37)), "no", "no"])
        i += 1
    write_rows(root / "slot_grid_calendar.csv",
               ["slot_code", "block_id", "sealed", "in_service"], rows, ",")

    # Reservations. The quantity column may be absent, and an absent quantity
    # is not a quantity of zero.
    rng = _pad_rng(inst, 22)
    records = []
    for r in inst["reservations"]:
        records.append({
            "reservation_id": r["reservation_id"],
            "block_id": r["block_id"],
            "service_group": r["service_group"],
            "first_slot": r["first_slot"],
            "last_slot": r["last_slot"],
            "quantity": NOT_SUPPLIED if r["quantity"] is None else r["quantity"],
            "shift_id": inst["shift_id"],
            "state": "held",
        })
    priors = _prior_shifts(inst, 24)
    i = 0
    while len(records) < 212:
        records.append({
            "reservation_id": "RSV-9%03d" % (100 + i),
            "block_id": inst["blocks"][i % len(inst["blocks"])]["block_id"],
            "service_group": rng.pick(SERVICE_GROUPS),
            "first_slot": "SL%02d" % rng.between(1, inst["cfg"]["slots"]),
            "last_slot": "SL%02d" % rng.between(1, inst["cfg"]["slots"]),
            "quantity": rng.between(0, 9),
            "shift_id": priors[i % len(priors)],
            "state": "released",
        })
        i += 1
    write_jsonl(root / "hold_reservation_notices.jsonl", records)

    # The topology names the blocks that are in force for this shift. Nothing
    # else does.
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<terminal>",
             "  <shift>%s</shift>" % inst["shift_id"],
             "  <reference>%s</reference>" % inst["shift_reference"], "  <blocks>"]
    for b in inst["blocks"]:
        lines.append('    <block id="%s" zone="%s" in_force="yes"/>' % (b["block_id"], b["zone"]))
    lines.append("  </blocks>")
    lines.append("  <berths>")
    for bt in BERTHS:
        lines.append('    <berth id="%s" reporting="yes"/>' % bt)
    lines.append("  </berths>")
    lines.append("</terminal>")
    write_lines(root / "yard_topology.xml", lines)


# --------------------------------------------------------------------------
# the move stream
# --------------------------------------------------------------------------


def write_move_papers(inst, root):
    rows = []
    for o in inst["orders"]:
        rows.append([o["order_id"], o["box_id"], o["source_system"], o["event_seq"],
                     o["raised_min"], o["to_block"], o["to_row"], o["to_tier"],
                     o["priority_band"], o["cluster_tag"]])
    write_rows(root / "move_order_journal.csv",
               ["order_id", "box_id", "source_system", "event_seq", "raised_min",
                "to_block", "to_row", "to_tier", "priority_band", "cluster_tag"],
               rows, ",")

    records = []
    for c in inst["confirmations"]:
        records.append({
            "confirm_id": c["confirm_id"],
            "order_id": c["order_id"],
            "box_id": c["box_id"],
            "confirmed_min": c["confirmed_min"],
            "equipment_id": c["equipment_id"],
            "landed_block": c["landed_block"],
            "landed_row": c["landed_row"],
            "landed_tier": c["landed_tier"],
            "confirm_state": c["confirm_state"],
        })
    rng = _pad_rng(inst, 31)
    i = 0
    while len(records) < 236:
        records.append({
            "confirm_id": "CF-7%04d" % (1000 + i),
            "order_id": "",
            "box_id": inst["boxes"][i % len(inst["boxes"])]["box_id"],
            "confirmed_min": rng.between(0, inst["cfg"]["slots"] * 120),
            "equipment_id": "EQ-%03d" % (200 + (i % max(1, inst["cfg"]["equipment"]))),
            "landed_block": NOT_SUPPLIED,
            "landed_row": NOT_SUPPLIED,
            "landed_tier": NOT_SUPPLIED,
            "confirm_state": "survey",
        })
        i += 1
    write_jsonl(root / "crane_confirmation_feed.ndjson", records)

    # Dependency declarations. An edge whose state is lifted was stood down
    # before the shift opened and is no part of the graph.
    records = []
    for e in inst["dependency_edges"]:
        records.append({
            "edge_id": e["edge_id"],
            "before_order": e["before_order"],
            "after_order": e["after_order"],
            "edge_weight": e["edge_weight"],
            "state": "declared",
        })
    rng = _pad_rng(inst, 32)
    i = 0
    while len(records) < 214:
        a = inst["orders"][(i * 5) % len(inst["orders"])]
        b = inst["orders"][(i * 5 + 2) % len(inst["orders"])]
        records.append({
            "edge_id": "DE-9%04d" % (1000 + i),
            "before_order": a["order_id"],
            "after_order": b["order_id"],
            "edge_weight": rng.between(1, 9),
            "state": "lifted",
        })
        i += 1
    write_jsonl(root / "move_dependency_declarations.jsonl", records)

    # Orders stood down at the desk. A withdrawn order never reaches the
    # ladder at all.
    rng = _pad_rng(inst, 33)
    ringed = set()
    for ring in inst["planted_cycles"]:
        ringed.update(ring)
    rows = []
    i = 0
    while len(rows) < 209:
        o = inst["orders"][(i * 7) % len(inst["orders"])]
        # An order that carries a dependency ring is never withdrawn at the
        # desk, so every ring reaches the graph stage intact.
        withdrawn = (i % 23 == 6) and o["order_id"] not in ringed
        stale = (i % 29 == 12)
        # A withdrawal raised in an earlier shift against an order this shift
        # reissued. It names a live order and withdraws nothing, because it
        # does not name this shift.
        rows.append([o["order_id"], "SL%02d" % rng.between(1, inst["cfg"]["slots"]),
                     "withdrawn" if (withdrawn or stale) else "carried",
                     inst["shift_id"] if withdrawn else _prior_shifts(inst, 9)[i % 9]])
        i += 1
    write_rows(root / "withdrawn_order_journal.tsv",
               ["order_id", "raised_slot", "state", "shift_id"], rows, "\t")

    # Which source system outranks which, when two orders of one cluster land
    # in the same slot with nothing else to separate them. The rank is a
    # register like any other and carries retired revisions.
    rng = _pad_rng(inst, 34)
    ranks = {"planning_desk": 2, "gate_terminal": 4, "crane_console": 1, "yard_radio": 3}
    rows = []
    for src in MOVE_SOURCES:
        rows.append([src, 2, ranks[src], "no", inst["shift_id"]])
        rows.append([src, 1, rng.between(1, 4), "yes", inst["shift_id"]])
        # A rank raised after the live one and then retired. Its sequence is
        # the highest of the three, so a reader that takes the highest
        # sequence without setting retired rows aside takes this one.
        rows.append([src, 3, 1 + ((ranks[src] + 1) % 4), "yes", inst["shift_id"]])
    priors = _prior_shifts(inst, 24)
    i = 0
    while len(rows) < 202:
        rows.append([MOVE_SOURCES[i % len(MOVE_SOURCES)], 1 + (i % 3),
                     rng.between(1, 4), "yes", priors[i % len(priors)]])
        i += 1
    write_rows(root / "source_priority_register.csv",
               ["source_system", "revision_seq", "priority_rank", "retired",
                "shift_id"], rows, ",")


# --------------------------------------------------------------------------
# equipment
# --------------------------------------------------------------------------


def write_equipment_papers(inst, root):
    rng = _pad_rng(inst, 41)
    rows = []
    for r in inst["equipment_revisions"]:
        rows.append([r["equipment_id"], r["revision_seq"], r["equipment_class"],
                     r["move_limit"], r["base_minutes"],
                     "yes" if r["retired"] else "no", inst["shift_id"]])
    priors = _prior_shifts(inst, 24)
    i = 0
    while len(rows) < 204:
        rows.append(["EQ-8%02d" % (10 + (i % 41)), 1 + (i % 3), rng.pick(EQUIP_CLASSES),
                     rng.between(10, 50), rng.between(2, 9), "yes",
                     priors[i % len(priors)]])
        i += 1
    write_rows(root / "handling_equipment_register.csv",
               ["equipment_id", "revision_seq", "equipment_class", "move_limit",
                "base_minutes", "retired", "shift_id"], rows, ",")



# --------------------------------------------------------------------------
# vessels
# --------------------------------------------------------------------------


def write_vessel_papers(inst, root):
    rng = _pad_rng(inst, 51)
    rows = []
    for r in inst["vessel_revisions"]:
        v = inst["vessel_index"][r["vessel_id"]]
        rows.append([r["vessel_id"], v["voyage"], r["revision_seq"], r["berth"],
                     r["service_group"], r["destination"], v["voyage_sequence"],
                     "yes" if r["withdrawn"] else "no", inst["shift_id"]])
    priors = _prior_shifts(inst, 24)
    i = 0
    while len(rows) < 210:
        rows.append(["VS-9%02d" % (10 + (i % 47)), "V9%03d%s" % (100 + i, "NESW"[i % 4]),
                     1 + (i % 3), rng.pick(BERTHS), rng.pick(SERVICE_GROUPS),
                     rng.pick(DESTINATIONS), 90 + i, "yes", priors[i % len(priors)]])
        i += 1
    write_rows(root / "vessel_call_register.csv",
               ["vessel_id", "voyage", "revision_seq", "berth_id", "service_group",
                "destination", "voyage_sequence", "withdrawn", "shift_id"], rows, ",")

    rows = []
    for c in inst["cutoffs"]:
        rows.append([c["notice_id"], c["vessel_id"], c["notice_seq"], c["cutoff_min"],
                     "yes" if c["superseded"] else "no", inst["shift_id"]])
    rng = _pad_rng(inst, 52)
    i = 0
    while len(rows) < 205:
        rows.append(["CO-9%04d" % (1000 + i), "VS-9%02d" % (10 + (i % 47)),
                     1 + (i % 3), rng.between(0, 1600), "yes",
                     priors[i % len(priors)]])
        i += 1
    write_rows(root / "cutoff_notice_board.tsv",
               ["notice_id", "vessel_id", "notice_seq", "cutoff_min", "superseded",
                "shift_id"], rows, "\t")

    rows = []
    for s in inst["stowage"]:
        rows.append([s["obligation_id"], s["box_id"], s["vessel_id"], s["bay_no"],
                     s["stow_sequence"], s["hold_flag"]])
    # Obligations left over from calls that closed before this shift. They
    # name vessels the call register carries only under an earlier shift, so
    # no box of this shift is ever matched to one.
    rng = _pad_rng(inst, 55)
    i = 0
    while len(rows) < 212:
        b = inst["boxes"][(i * 5) % len(inst["boxes"])]
        rows.append(["SO-8%04d" % (1000 + i), b["box_id"],
                     "VS-9%02d" % (10 + (i % 47)), rng.between(1, 48),
                     (i * 11) % 401, "no"])
        i += 1
    write_rows(root / "stowage_obligation_list.psv",
               ["obligation_id", "box_id", "vessel_id", "bay_no", "stow_sequence",
                "hold_flag"], rows, "|")

    # Berth windows, carried per revision. The applicable revision is the last
    # one that is not marked draft.
    rng = _pad_rng(inst, 53)
    rows = []
    for rev in range(1, 7):
        for w in inst["berth_windows"]:
            draft = (rev != 4)
            rows.append([w["berth_id"], w["slot_code"], rev,
                         w["crane_minutes"] if not draft else rng.between(10, 140),
                         w["crane_count"] if not draft else rng.between(1, 4),
                         "yes" if draft else "no"])
    write_rows(root / "berth_window_register.csv",
               ["berth_id", "slot_code", "revision_seq", "crane_minutes",
                "crane_count", "draft"], rows, ",")

    rng = _pad_rng(inst, 54)
    rows = []
    for rev in range(1, 4):
        for d in inst["demand_returns"]:
            live = (rev == 2)
            rows.append([d["return_id"], d["vessel_id"], d["slot_code"], rev,
                         d["declared_minutes"] if live else rng.between(5, 80),
                         d["return_state"] if live else "void"])
    write_rows(root / "quay_demand_returns.csv",
               ["return_id", "vessel_id", "slot_code", "revision_seq",
                "declared_minutes", "return_state"], rows, ",")


# --------------------------------------------------------------------------
# exceptions, history and decoys
# --------------------------------------------------------------------------


def write_history_papers(inst, root):
    rng = _pad_rng(inst, 61)
    rows = []
    for e in inst["exceptions"]:
        rows.append([e["exception_id"], e["exception_kind"], e["target_kind"],
                     e["target_id"], e["granted_slot"],
                     "yes" if e["withdrawn"] else "no", inst["shift_id"]])
    priors = _prior_shifts(inst, 24)
    i = 0
    while len(rows) < 208:
        rows.append(["EX-9%03d" % (100 + i),
                     rng.pick(["zone_waiver", "tier_waiver", "cutoff_waiver",
                               "reservation_release"]),
                     "order", "MO-9%04d" % (1000 + i),
                     "SL%02d" % rng.between(1, inst["cfg"]["slots"]), "yes",
                     priors[i % len(priors)]])
        i += 1
    write_rows(root / "operational_exception_notices.csv",
               ["exception_id", "exception_kind", "target_kind", "target_id",
                "granted_slot", "withdrawn", "shift_id"], rows, ",")

    # The tariff this terminal stopped using. It is kept for audit and the
    # published move charge is not taken from it.
    rng = _pad_rng(inst, 63)
    rows = []
    i = 0
    while len(rows) < 211:
        rows.append(["LT-%04d" % (3000 + i), BOX_CLASSES[i % len(BOX_CLASSES)],
                     ISO_LENGTHS[i % len(ISO_LENGTHS)], rng.between(1800, 4200),
                     "withdrawn"])
        i += 1
    write_rows(root / "legacy_tariff_extract.csv",
               ["tariff_id", "box_class", "iso_length", "flat_cents", "state"],
               rows, ",")

    # An operational database kept by the shift office.
    audit_moves = []
    for o in inst["orders"]:
        audit_moves.append((o["order_id"], o["box_id"], o["source_system"],
                            str(o["raised_min"]), o["cluster_tag"]))
    audit_boxes = []
    for b in inst["boxes"]:
        audit_boxes.append((b["box_id"], b["box_class"], str(b["iso_length"]),
                            b["vessel_id"], b["destination"]))
    write_sqlite(root / "shift_office_audit.db", {
        "move_orders": (["order_id", "box_id", "source_system", "raised_min",
                         "cluster_tag"], audit_moves),
        "boxes": (["box_id", "box_class", "iso_length", "vessel_id", "destination"],
                  audit_boxes),
    })

"""The three papers that are not plain text.

Each carries control values that appear nowhere else in the corpus. The
workbook holds one live sheet among six and the live one is the sheet whose
key cell carries this shift's reference; sheet name and sheet position carry
no information about which one that is.
"""


def _sheet_reference(inst, position):
    """Every sheet declares a shift reference in cell B1. Exactly one of them
    is this shift's."""
    if position == inst["controls"]["live_sheet_index"]:
        return inst["shift_reference"]
    return "QCR-%06d" % ((inst["seed"] + 7919 * (position + 1)) % 1000000)


def _workbook_sheet(inst, position):
    c = inst["controls"]
    live = (position == c["live_sheet_index"])
    rng = Rng((inst["seed"] * 31 + position * 7717) & 0xFFFFFFFFFFFFFFFF)

    def val(x, spread):
        return x if live else max(1, x + rng.between(-spread, spread))

    rows = [
        ["shift_reference", _sheet_reference(inst, position)],
        ["sheet_state", "live" if live else "prior"],
        [],
        ["control_name", "numerator", "denominator", "unit"],
        ["ration_damping_fraction", val(c["damping_num"], 3), val(c["damping_den"], 5), "fraction"],
        ["decitonne_kilograms", val(c["decitonne_kilograms"], 20), 1, "kilogram"],
        ["centner_kilograms", val(c["centner_kilograms"], 12), 1, "kilogram"],
        ["base_move_charge_cents", val(c["base_move_cents"], 400), 1, "cent"],
        [],
        ["teu_factor_table", "iso_length", "teu_factor"],
    ]
    for iso in ISO_LENGTHS:
        rows.append(["teu_factor", iso, c["teu_factor"][iso] if live else rng.between(1, 3)])
    rows.append([])
    rows.append(["plug_ceiling_table", "zone", "plug_ceiling"])
    for zone in ZONES:
        rows.append(["plug_ceiling", zone,
                     c["plug_ceiling"][zone] if live else rng.between(0, 9)])
    rows.append([])
    rows.append(["block_class_ceiling_register", "block_id", "box_class",
                 "shift_half", "class_ceiling"])
    for b in inst["blocks"]:
        for klass in BOX_CLASSES:
            for half in ("first", "second"):
                ceiling = (b["slot_capacity"] // 2) + len(klass)
                rows.append(["block_class_ceiling", b["block_id"], klass, half,
                             ceiling if live else rng.between(0, 40)])
    rows.append([])
    rows.append(["vessel_slot_ceiling_register", "vessel_id", "slot_code",
                 "admissible_minutes"])
    for v in inst["vessels"]:
        for s in inst["slots"]:
            base = 18 + ((v["voyage_sequence"] * 5 + s["ordinal"] * 3) % 47)
            rows.append(["vessel_slot_ceiling", v["vessel_id"], s["slot_code"],
                         base if live else rng.between(5, 90)])
    return rows


def write_workbook(inst, path):
    names = inst["controls"]["sheet_names"]
    sheets = {}
    for i, name in enumerate(names):
        sheets[name] = _workbook_sheet(inst, i)
    write_xlsx(path, sheets)


def write_memo(inst, path):
    c = inst["controls"]
    lines = [
        "KESTREL POINT CONTAINER TERMINAL",
        "BERTH OPERATIONS MEMORANDUM",
        "shift %s    reference %s" % (inst["shift_id"], inst["shift_reference"]),
        "",
        "SECTION 1  CONTROL VALUES ISSUED HERE",
        "",
        "These three values are issued here and are carried in no other paper",
        "of this shift. The first two govern the quay ration; the third",
        "governs the dependency stage. The fourth value the quay ration needs,",
        "the damping fraction, is issued by the capacity workbook.",
        "",
        "  ration_pass_budget          %d" % c["pass_budget"],
        "  ration_minimum_step         %d crane minutes" % c["minimum_step"],
        "  dependency_protection_depth %d" % c["protection_depth"],
        "",
        "The pass budget is a count of passes, not a convergence test. The",
        "ration stops when the budget is spent whether or not the shares have",
        "settled, and the shares as they stand at that point are the shares",
        "that get published.",
        "",
        "The minimum step is the smallest move a share may make in one pass.",
        "A share whose damped move rounds to nothing still moves by the",
        "minimum step toward its target, so a share that has not reached its",
        "target never sits still while passes remain.",
        "",
        "SECTION 2  REHANDLE SURCHARGE LADDER",
        "",
        "  tier_depth   surcharge_cents",
    ]
    for entry in c["surcharge_ladder"]:
        lines.append("  %-12d %d" % (entry["tier_depth"], entry["surcharge_cents"]))
    lines += [
        "",
        "A tier depth beyond the last rung of the ladder carries the surcharge",
        "of the last rung. A tier depth of one carries no surcharge.",
        "",
        "SECTION 3  QUAY GANG ROSTER",
        "",
        "The gang roster is the minute allowance the quay can actually crew in",
        "each slot. The berth window register declares what the berth asked",
        "for. The pool a berth rations in a slot is the smaller of the two.",
        "",
        "  berth_id     slot_code  gang_code  gang_minutes",
    ]
    rng = Rng((inst["seed"] * 8191 + 13) & 0xFFFFFFFFFFFFFFFF)
    for berth in BERTHS:
        for s in inst["slots"]:
            for g in range(6):
                minutes = rng.between(3, 18)
                lines.append("  %-12s %-10s %-10s %d"
                             % (berth, s["slot_code"], "GNG-%d" % (g + 1), minutes))
    lines += [
        "",
        "SECTION 4  STANDING NOTES",
        "",
        "Reserved capacity is withheld capacity. A block may show free slots",
        "and still refuse a placement, because the reservation standing over",
        "that block for that slot is settled before free capacity is counted.",
        "",
        "end of memorandum",
    ]
    write_pdf(path, lines)


def write_directive(inst, path):
    c = inst["controls"]
    blocks = [
        ("p", "KESTREL POINT CONTAINER TERMINAL"),
        ("p", "STOWAGE ORDERING DIRECTIVE"),
        ("p", "shift %s    reference %s" % (inst["shift_id"], inst["shift_reference"])),
        ("p", ""),
        ("p", "SECTION 1. The order in which a vessel is loaded."),
        ("p", "The loadable set of a vessel is put in order by the keys below, "
              "read left to right, each ascending. The last key settles every "
              "remaining tie by itself, so the order is total."),
        ("table", [["key_position", "key_name"]] +
                  [[str(i + 1), k] for i, k in enumerate(c["stowage_keys"])]),
        ("p", "SECTION 2. The class rank register."),
        ("p", "The class rank is the first ordering key. It is issued here and "
              "is carried in no other paper of this shift."),
        ("table", [["box_class", "class_rank"]] +
                  [[k, str(c["class_rank"][k])] for k in BOX_CLASSES]),
        ("p", "SECTION 3. The bay assignment register."),
        ("p", "Every bay a vessel declares is listed with the tier band the "
              "bay accepts. A bay the register does not carry takes the band "
              "of the highest numbered bay below it."),
    ]
    rng = Rng((inst["seed"] * 5779 + 29) & 0xFFFFFFFFFFFFFFFF)
    bay_rows = [["vessel_id", "bay_no", "tier_band", "state"]]
    for v in inst["vessels"]:
        for bay in range(1, 49):
            bay_rows.append([v["vessel_id"], str(bay), str(rng.between(1, 5)),
                             "open" if bay % 7 else "shut"])
    blocks.append(("table", bay_rows))
    blocks.append(("p", "end of directive"))
    write_docx(path, blocks)

"""Policy and vocabulary papers: the rules that cut across the stages."""


def write_policy_papers(inst, root):
    c = inst["controls"]
    slots = inst["cfg"]["slots"]

    write_lines(root / "rounding_and_arithmetic_policy.yaml", [
        "# How this terminal rounds. Every stage that names a rounding step",
        "# means this rule and no other.",
        "policy: kestrel_point_rounding",
        "shift_id: %s" % inst["shift_id"],
        "arithmetic:",
        "  domain: exact_rational",
        "  binary_floating_point: forbidden",
        "  statement: >-",
        "    Every derivation is carried in exact rational arithmetic. A value",
        "    is rounded only where a stage specification places a rounding",
        "    step, and the rounded value is what the next stage reads.",
        "rounding_rule:",
        "  name: half_up_away_from_zero",
        "  statement: >-",
        "    A residue of exactly one half rounds away from zero. A residue",
        "    below one half rounds toward zero. This applies to every rounding",
        "    step in every stage.",
        "placement:",
        "  statement: >-",
        "    Rounding is placed where the stage says and nowhere else. A",
        "    quantity rounded at each of three stages is not the same quantity",
        "    as one carried exactly and rounded once at the end, and this",
        "    terminal publishes the first.",
        "negative_zero:",
        "  statement: a published integer is never written with a leading minus when its value is zero",
        "published_forms:",
        "  whole_quantities: integer, no thousands separator, no sign when zero",
        "  crane_minutes: integer crane minutes",
        "  money: integer cents",
        "  ratios: exactly nine decimal places, half up away from zero",
        "  mass: integer kilograms",
    ])

    write_lines(root / "revision_precedence.toml", [
        "# Which revision of a register row is in force at the assessment",
        "# instant. Every register that carries a revision_seq column is read",
        "# through this paper.",
        'policy = "revision_precedence"',
        'shift_id = "%s"' % inst["shift_id"],
        "",
        "[scope]",
        'statement = """',
        "A register row belongs to this shift only when its shift_id column",
        "names this shift. Rows carrying any other shift identifier are",
        "earlier material and take no part in this shift's derivation.",
        '"""',
        "",
        "[selection]",
        'statement = """',
        "Among the rows of one register that belong to this shift and name one",
        "subject, set aside every row marked retired and every row marked",
        "future, then take the row with the highest revision_seq. That row is",
        "the applicable revision. A subject whose rows are all set aside has",
        "no applicable revision and the stage that reads it says what happens",
        "then.",
        '"""',
        "",
        "[withdrawal]",
        'statement = """',
        "A vessel call revision marked withdrawn is set aside the same way a",
        "retired row is. A withdrawn revision never becomes applicable, not",
        "even when it is the only revision that remains.",
        '"""',
        "",
        "[supersession]",
        'statement = """',
        "A notice marked superseded is set aside. Among the notices for one",
        "subject that are not superseded, the one with the highest notice_seq",
        "is in force.",
        '"""',
    ])

    # The ladder. Rung order is stated here and it is not the alphabetical
    # order of the rung codes.
    ladder = [
        "KESTREL POINT CONTAINER TERMINAL",
        "MOVE ORDER ADMISSION LADDER",
        "",
        "A move order is put to the rungs below in the order printed here.",
        "The first rung that catches an order settles it, the order is set",
        "aside with that rung's code as its reason, and the remaining rungs",
        "are not put to it. The printed order is the order in force. It is",
        "not the alphabetical order of the rung codes and it is not the order",
        "the codes happen to take in any other paper.",
        "",
    ]
    for i, rung in enumerate(LADDER_RUNGS, start=1):
        ladder.append("rung %d  %s" % (i, rung))
        ladder.append("        %s" % REJECTION_TEXT[rung])
        ladder.append("")
    ladder += [
        "An order that no rung catches is admitted and goes on to the",
        "eligibility stage.",
        "",
        "An order withdrawn at the desk never reaches rung one. Withdrawal is",
        "recorded in the withdrawn order journal and a withdrawn order is",
        "absent from the canonical event set rather than set aside by a rung.",
    ]
    write_lines(root / "move_admission_ladder.txt", ladder)

    write_lines(root / "reserved_capacity_policy.toml", [
        "# Reserved capacity, and how it settles against free capacity.",
        'policy = "reserved_capacity"',
        'shift_id = "%s"' % inst["shift_id"],
        "",
        "[precedence]",
        'statement = """',
        "Reserved capacity is settled before free capacity is counted. A",
        "block may carry free slots and still refuse a placement, because the",
        "slots a reservation withholds were never free to begin with. A stage",
        "that counts free slots and admits a placement against them without",
        "first withholding the reserved slots has read this backwards.",
        '"""',
        "",
        "[absent_quantity]",
        'statement = """',
        "A reservation whose quantity column carries the not supplied marker",
        "withholds the whole of the block free capacity for the slots it",
        "spans. An absent quantity is not a quantity of zero, and the two",
        "give different answers wherever a block has free capacity at all.",
        '"""',
        "",
        "[qualifying]",
        'statement = """',
        "A reservation is consumed only by a move whose box belongs to the",
        "service group the reservation names. A move belonging to any other",
        "service group is bound by the reservation and consumes none of it.",
        '"""',
        "",
        "[span]",
        'statement = """',
        "A reservation stands over every slot from its first_slot to its",
        "last_slot, both included.",
        '"""',
        "",
        "[over_reservation]",
        'statement = """',
        "A reservation quantity larger than the free capacity of its block",
        "withholds the free capacity and no more. The excess is recorded as",
        "unmet reservation and withholds nothing further.",
        '"""',
    ])

    write_lines(root / "equipment_allowance_policy.toml", [
        "# Handling allowances.",
        'policy = "equipment_allowance"',
        'shift_id = "%s"' % inst["shift_id"],
        "",
        "[limit]",
        'statement = """',
        "The move limit of an equipment unit is the count of confirmed moves",
        "it may carry across the whole shift. A unit that has carried exactly",
        "its limit is inside its allowance. A unit that would carry one move",
        "beyond its limit is outside it, and the move that would take it past",
        "the limit is recorded as an equipment exception.",
        '"""',
        "",
        "[zero_allowance]",
        'statement = """',
        "A unit whose move limit is zero carries no move at all. It is still",
        "published, with a used count of zero and an allowance of zero, and it",
        "is not the same as a unit the register does not carry.",
        '"""',
        "",
        "[ordering]",
        'statement = """',
        "Moves are charged to a unit in canonical event order. The allowance",
        "is spent in that order, so which move falls outside the allowance",
        "depends on the order and not on the order the duty log happens to",
        "list.",
        '"""',
    ])

    write_lines(root / "boundary_conventions.yaml", [
        "# Where a value that lands exactly on a boundary belongs.",
        "policy: kestrel_point_boundaries",
        "shift_id: %s" % inst["shift_id"],
        "slot_length_minutes: 120",
        "slot_count: %d" % slots,
        "slot_boundary:",
        "  statement: >-",
        "    A minute that falls exactly on the boundary between two slots",
        "    belongs to the slot that is closing, not to the slot that is",
        "    opening. Minute zero belongs to the first slot. A minute beyond",
        "    the close of the last slot belongs to no slot and the order that",
        "    carries it was raised against a slot that had already closed.",
        "  worked: >-",
        "    With slots of one hundred and twenty minutes, minute 240 belongs",
        "    to slot SL02 and minute 241 belongs to slot SL03.",
        "cutoff_boundary:",
        "  statement: >-",
        "    A box whose last accepted movement lands exactly on a vessel",
        "    cutoff minute is inside that cutoff. Strictly after the cutoff",
        "    minute is outside it.",
        "tier_boundary:",
        "  statement: >-",
        "    A placement at exactly the legal maximum tier of a block is",
        "    lawful. A placement one tier beyond it is not.",
        "capacity_boundary:",
        "  statement: >-",
        "    A block whose free capacity is zero is published with a free",
        "    capacity of zero. That is a different published state from a",
        "    block the topology does not carry, which is published not at all.",
    ])

    write_lines(root / "quay_ration_policy.toml", [
        "# The shape of the quay ration. The four control values it needs are",
        "# issued by the berth operations memorandum and the capacity",
        "# workbook, and are carried in no other paper.",
        'policy = "quay_ration"',
        'shift_id = "%s"' % inst["shift_id"],
        "",
        "[pairing]",
        'statement = """',
        "The ration is run once for every pairing of a slot with a berth. The",
        "vessels in a pairing are the vessels whose applicable berth is that",
        "berth and which carry a filed demand return for that slot.",
        '"""',
        "",
        "[pool]",
        'statement = """',
        "The pool a pairing rations is the smaller of the crane minutes the",
        "applicable berth window revision declares for that slot and the sum",
        "of the gang minutes the quay gang roster crews for that pairing.",
        '"""',
        "",
        "[iterate]",
        'statement = """',
        "The ration is a damped iterate under a hard pass budget. It is not",
        "run to convergence and it is not solved in closed form. Every share",
        "starts at zero. Each pass computes a target from the demands, caps",
        "the target, redistributes what the caps freed, damps the move from",
        "the standing share toward the target, and rounds the result to whole",
        "crane minutes before the next pass begins. The passes stop when the",
        "budget is spent, and the shares standing at that moment are",
        "published whether or not they have settled.",
        '"""',
        "",
        "[quantisation]",
        'statement = """',
        "The rounding happens at the end of every pass, not once at the end",
        "of the ration. Each pass therefore begins from whole crane minutes",
        "and the residues do not accumulate.",
        '"""',
        "",
        "[redistribution]",
        'statement = """',
        "What a cap frees is redistributed inside the cross classification of",
        "berth and service group. A vessel receives a portion of freed",
        "minutes only from vessels sharing both its berth and its service",
        "group, in proportion to its own demand. Freed minutes with no",
        "uncapped vessel in the cell stay unassigned and are published as",
        "unplaced minutes for that pairing.",
        '"""',
        "",
        "[minimum_step]",
        'statement = """',
        "A share that has not reached its target moves by at least the",
        "minimum step the memorandum issues, in the direction of the target,",
        "even when the damped move would round to nothing. A share already",
        "at its target does not move. The step never carries a share past its",
        "target.",
        '"""',
        "",
        "[order]",
        'statement = """',
        "Inside one pass the vessels are worked in ascending vessel_id. The",
        "pairings are worked in ascending slot_code and then ascending",
        "berth_id.",
        '"""',
    ])

    write_lines(root / "berth_reporting_roster.conf", [
        "# Berths that publish a report of their own.",
        "[roster]",
        "shift_id = %s" % inst["shift_id"],
        "reporting_berths = %s" % ", ".join(BERTHS),
        "",
        "[form]",
        "one_report_per_reporting_berth = yes",
        "empty_berth_still_reports = yes",
        "statement = A reporting berth that rationed nothing still publishes its report, carrying zero counts and an empty vessel list.",
    ])

    write_lines(root / "unit_register_dictionary.toml", [
        "# The unit registers this terminal writes mass and size in.",
        'dictionary = "unit_registers"',
        'shift_id = "%s"' % inst["shift_id"],
        "",
        "[mass]",
        'base_unit = "kilogram"',
        'statement = """',
        "A mass declaration carries the register it is written in. The kg",
        "register is already in kilograms. The dt register is in decitonnes",
        "and the ct register is in centners. The kilograms in one decitonne",
        "and the kilograms in one centner are issued by the capacity workbook",
        "and are carried in no other paper. A declaration read without its",
        "register is wrong by a factor this dictionary will not name.",
        '"""',
        "",
        "[size]",
        'statement = """',
        "An iso_length column is written as a bare number, or with the suffix",
        "FT, or with the suffix ft. The three spellings are one length. The",
        "teu factor of a length is issued by the capacity workbook.",
        '"""',
        "",
        "[absence]",
        'marker = "-"',
        'statement = """',
        "The not supplied marker means the field was not supplied. What that",
        "means for a derivation is settled by the stage that reads the field,",
        "and it is never silently a zero.",
        '"""',
    ])

    write_lines(root / "publication_form_rules.toml", [
        "# How a published document is laid out.",
        'policy = "publication_form"',
        'shift_id = "%s"' % inst["shift_id"],
        "",
        "[ordering]",
        'statement = """',
        "Every published document is written in the row order its schema",
        "names. Where a schema names no order, rows ascend by their first",
        "column and ties by the column after it.",
        '"""',
        "",
        "[empty_groups]",
        'statement = """',
        "A group with no members is published as a row of its own carrying",
        "zero counts, never left out. A group with exactly one member is",
        "published by the same rule as a group with many, with no special",
        "case for the single member.",
        '"""',
        "",
        "[zero_denominator]",
        'statement = """',
        "A ratio whose denominator is zero is published as 0.000000000. It is",
        "not left blank and it is not left out.",
        '"""',
    ])

"""One specification per stage."""

STAGE_TITLES = [
    ("y01", "canonical_events", "Canonical event set"),
    ("y02", "unit_normalisation", "Unit normalisation"),
    ("y03", "vessel_obligation", "Vessel obligation state"),
    ("y04", "opening_yard", "The opening yard"),
    ("y05", "event_ordering", "Canonical event order"),
    ("y06", "dependency_cycles", "Move dependencies and their cycles"),
    ("y07", "move_admission", "Move admission"),
    ("y08", "yard_state", "Yard state through the shift"),
    ("y09", "movement_reconciliation", "Planned against physical"),
    ("y10", "rehandle_and_equipment", "Rehandles and equipment"),
    ("y11", "block_capacity", "Block capacity state"),
    ("y12", "load_eligibility", "Cutoff joined to yard state"),
    ("y13", "quay_ration", "The quay ration and the load"),
    ("y14", "terminal_accounts", "Terminal accounts and publication"),
]


def _stage_body(tag, inst):
    c = inst["controls"]
    if tag == "y01":
        return [
            "This stage turns the move order journal into the canonical event",
            "set of the shift. Nothing is decided about a move here beyond",
            "which slot it belongs to and whether it exists at all.",
            "",
            "RULE Y01.1  Withdrawal.",
            "An order named in the withdrawn order journal with state",
            "withdrawn and this shift's identifier is absent from the",
            "canonical event set. It is not set aside by a rung of the",
            "admission ladder, it is not published in the rejection journal,",
            "and it takes no part in any later stage. A withdrawal row",
            "carrying any other shift identifier is earlier material and",
            "withdraws nothing here.",
            "",
            "RULE Y01.2  The slot a minute belongs to.",
            "Every order carries the minute it was raised and no slot. The",
            "slot is derived from the minute using the boundary convention in",
            "boundary_conventions.yaml. A minute that falls exactly on the",
            "boundary between two slots belongs to the slot that is closing.",
            "Minute zero belongs to the first slot.",
            "",
            "RULE Y01.3  Beyond the last slot.",
            "A minute strictly greater than the close of the last slot belongs",
            "to no slot. The order is still a canonical event, its published",
            "slot_code is the not supplied marker, and the admission ladder",
            "settles it at the rung that catches a stale slot.",
            "",
            "RULE Y01.4  Clusters are given.",
            "The cluster tag on an order is read from the journal. This stage",
            "forms no clusters of its own and picks no canonical member; the",
            "pick happens at the admission stage, because it depends on which",
            "members survive the earlier rungs.",
            "",
            "PUBLISHES  canonical_events.csv",
        ]
    if tag == "y02":
        return [
            "This stage puts every box in the terminal's base units.",
            "",
            "RULE Y02.1  The applicable box record.",
            "Read box_master_register.csv through revision_precedence.toml.",
            "Rows of another shift, and rows marked retired, are set aside.",
            "The applicable row of a box is the surviving row with the",
            "highest revision_seq.",
            "",
            "RULE Y02.2  The applicable mass declaration.",
            "In mass_declaration_returns.psv a declaration counts only when",
            "its state is filed. Among the filed declarations of one box the",
            "one with the highest declaration_seq is applicable. Superseded",
            "declarations are set aside whatever they carry.",
            "",
            "RULE Y02.3  The unit register.",
            "A declaration is written in the register its mass_unit column",
            "names. A kg declaration is already in kilograms. A dt",
            "declaration is multiplied by the kilograms in one decitonne and a",
            "ct declaration by the kilograms in one centner. Both factors are",
            "issued by the live sheet of quay_capacity_workbook.xlsx and are",
            "carried in no other paper of this shift.",
            "",
            "RULE Y02.4  An absent mass.",
            "A box whose applicable declaration carries the not supplied",
            "marker, and a box with no filed declaration at all, is published",
            "with mass_state of not_declared and a published mass_kg of 0.",
            "The published zero is a form, not a measurement: such a box is",
            "excluded from every mass total this publication carries. Reading",
            "an absent mass as a declared zero puts it into those totals and",
            "is wrong.",
            "",
            "RULE Y02.5  The length spellings.",
            "The iso_length column is written as a bare number, or with the",
            "suffix FT, or with the suffix ft. The three are one length. The",
            "published iso_length is the bare number.",
            "",
            "RULE Y02.6  The teu factor.",
            "The teu factor of a length is issued by the live workbook sheet.",
            "A length the sheet does not carry has a teu factor of 0.",
            "",
            "PUBLISHES  container_dimensions.csv",
        ]
    if tag == "y03":
        return [
            "This stage settles which call each vessel is making.",
            "",
            "RULE Y03.1  The applicable call revision.",
            "In vessel_call_register.csv set aside rows of another shift and",
            "rows marked withdrawn. The applicable revision of a vessel is the",
            "surviving row with the highest revision_seq. A withdrawn revision",
            "never becomes applicable, not even when it is the only revision a",
            "vessel has; such a vessel has no applicable call and is absent",
            "from the published obligation.",
            "",
            "RULE Y03.2  What the call settles.",
            "The applicable revision settles the vessel's berth, its service",
            "group and its destination. Every later stage reads those three",
            "from here and from nowhere else. A box takes its service group",
            "and its destination from its vessel, not from its own papers.",
            "",
            "RULE Y03.3  A box whose vessel has no applicable call.",
            "Such a box carries the not supplied marker for service group and",
            "destination, and the eligibility stage settles what happens to",
            "it.",
            "",
            "PUBLISHES  vessel_obligation.csv",
        ]
    if tag == "y04":
        return [
            "This stage materialises the yard as it stood when the shift",
            "opened.",
            "",
            "RULE Y04.1  Which blocks are in force.",
            "yard_topology.xml names the blocks in force for this shift. A",
            "block the topology does not name takes no part in this shift",
            "however many rows the geometry register carries for it.",
            "",
            "RULE Y04.2  The applicable geometry.",
            "In block_geometry_register.csv set aside rows of another shift,",
            "rows marked retired and rows marked future. The applicable",
            "revision of a block is the surviving row with the highest",
            "revision_seq. A block in force with no surviving revision has",
            "zero rows, zero tiers and zero capacity.",
            "",
            "RULE Y04.3  Capacity.",
            "The slot capacity of a block is its rows multiplied by its",
            "maximum tier. A block whose capacity is zero is published with a",
            "capacity of zero. That is a different published state from a",
            "block the topology does not carry, which is published not at",
            "all.",
            "",
            "RULE Y04.4  The opening stack.",
            "A row of stack_inventory_snapshot.csv places a box only when its",
            "stack_state is stacked, its block is in force and its box has an",
            "applicable master record. Every other row places nothing; a box",
            "it names is off the yard at the opening instant and has no yard",
            "position.",
            "",
            "RULE Y04.5  An empty block.",
            "A block in force that the opening stack places nothing into is",
            "published with an opening count of zero and its whole capacity",
            "free. It is never left out of the published occupancy.",
            "",
            "PUBLISHES  initial_occupancy.psv",
        ]
    if tag == "y05":
        return [
            "This stage puts the canonical events in the one order every later",
            "stage walks them in.",
            "",
            "RULE Y05.1  The source rank.",
            "source_priority_register.csv gives every source system a priority",
            "rank. Read it through revision_precedence.toml: rows of another",
            "shift and rows marked retired are set aside, and the surviving",
            "row with the highest revision_seq is applicable. A lower rank",
            "number outranks a higher one. The rank order is not the order the",
            "sources appear in any paper and it is not their alphabetical",
            "order.",
            "",
            "RULE Y05.2  The order.",
            "Events ascend by slot ordinal, then by source priority rank, then",
            "by event_seq, then by box_id, then by order_id. An event with no",
            "slot sorts after every event that has one. The last key settles",
            "every remaining tie by itself, so the order is total and does not",
            "depend on the order the journal happens to list.",
            "",
            "RULE Y05.3  The event key.",
            "The event key is the position of the event in that order,",
            "counting from one. Every later stage names events by this key.",
            "",
            "PUBLISHES  event_order.csv",
        ]
    if tag == "y06":
        return [
            "This stage builds the move dependency graph and breaks its",
            "cycles. A cycle is broken, never rejected.",
            "",
            "RULE Y06.1  Which edges are in the graph.",
            "An edge of move_dependency_declarations.jsonl is in the graph",
            "only when its state is declared and both of its orders are",
            "canonical events. An edge marked lifted was stood down before the",
            "shift opened. An edge from an order to itself is no edge.",
            "",
            "RULE Y06.2  Finding the cycles.",
            "A cycle is a strongly connected component of two orders or more.",
            "Components are settled on the graph as it stands, and are found",
            "again after every removal, because removing one edge can leave a",
            "component that is still cyclic.",
            "",
            "RULE Y06.3  Protected edges.",
            "Inside one cyclic component rank its edges by weight descending",
            "and then by edge_id ascending. The edges at the head of that",
            "ranking are protected, as many of them as the protection depth",
            "names. The protection depth is issued by",
            "berth_operations_memo.pdf and is carried in no other paper.",
            "",
            "RULE Y06.4  The edge that is removed.",
            "The edge removed from a cyclic component is the edge of lowest",
            "weight among its unprotected edges, and ties on weight are",
            "settled by ascending edge_id. When every edge of the component is",
            "protected the protection is lifted for that component alone and",
            "the same rule is applied to all of its edges. The protected_count",
            "the report carries is the number of edges the protection marked",
            "at the head of the ranking, which is the protection depth or the",
            "edge count of the component when that is smaller. It is published",
            "as that number whether or not the protection then had to be",
            "lifted, so it never reads zero for a component that carries an",
            "edge.",
            "",
            "RULE Y06.5  The component key and the order they are worked in.",
            "The component key of a cyclic component is the lowest order",
            "identifier the component carries. Components are worked in",
            "ascending component key, one edge removed from one component at a",
            "time, and a component that is still cyclic after its removal is",
            "worked again straight away, before any component with a higher",
            "key. The report carries one entry per removal, in that order, so",
            "a component that lost two edges appears twice under one key.",
            "",
            "RULE Y06.6  The dependency order.",
            "After the cycles are broken the orders are placed one at a time.",
            "At each step the placeable orders are those whose remaining",
            "predecessors are all placed, and the one placed is the placeable",
            "order with the lowest event key. This is a total order and it is",
            "not the order any generic traversal happens to produce.",
            "",
            "PUBLISHES  cycle_break_report.json, dependency_order.csv",
        ]
    if tag == "y07":
        return [
            "This stage settles every canonical event against the yard as it",
            "stood immediately before that event. It is walked in canonical",
            "event order and it is stateful: an event is judged against the",
            "state its predecessors left, and never against the state a later",
            "event will produce.",
            "",
            "RULE Y07.1  The ladder.",
            "The rungs of move_admission_ladder.txt are put to an order in the",
            "order that paper prints them. The first rung that catches an",
            "order settles it and the remaining rungs are not put to it. The",
            "printed order is not the alphabetical order of the rung codes.",
            "",
            "RULE Y07.2  Waivers.",
            "An exception of operational_exception_notices.csv that names this",
            "shift and is not withdrawn lifts one rung for the order it",
            "targets. A zone_waiver lifts the sealed zone rung, a tier_waiver",
            "lifts the tier rung and a reservation_release lifts the reserved",
            "capacity rung. A lifted rung is skipped for that order and the",
            "rungs below it are still put to it. A cutoff_waiver lifts nothing",
            "here and is read at the eligibility stage. A waiver never revives",
            "a destination the topology does not carry: when the tier rung is",
            "lifted for an order whose destination block is not in force, the",
            "rungs below it read that block as holding no capacity at all, so",
            "the reserved capacity rung catches the order.",
            "",
            "RULE Y07.3  Reserved capacity is settled before free capacity.",
            "At the reserved capacity rung, take the block's capacity less the",
            "boxes standing in it at that instant. That is the free capacity.",
            "Then withhold, from that free capacity, the standing credit of",
            "every reservation that covers this block and this slot and names",
            "a service group other than the service group of this order's box.",
            "What remains is what this order may be placed against. When what",
            "remains is zero or less the rung catches the order. A stage that",
            "counts free capacity and admits the order against it, without",
            "first withholding the reserved credit, has read this backwards",
            "and will admit orders this terminal refuses.",
            "",
            "RULE Y07.4  What a reservation withholds.",
            "A reservation of hold_reservation_notices.jsonl counts when it",
            "names this shift and its state is held. Its opening credit is the",
            "quantity it asks for, and a quantity written as the not supplied",
            "marker asks for the whole opening free capacity of its block. The",
            "credit is then capped at that opening free capacity, and whatever",
            "was asked beyond it is published as unmet and withholds nothing.",
            "A reservation stands over every slot from its first slot to its",
            "last slot, both included.",
            "",
            "RULE Y07.5  What consumes a reservation.",
            "An admitted order whose box belongs to the service group a",
            "standing reservation names consumes one unit of that",
            "reservation's remaining credit. Where more than one such",
            "reservation stands, the one with the lowest reservation_id is",
            "consumed. An order of any other service group consumes nothing,",
            "which is why the credit it was bound by is still standing for the",
            "orders that follow it.",
            "",
            "RULE Y07.6  The tier rung.",
            "A placement at exactly the maximum legal tier of the applicable",
            "geometry is lawful. A placement one tier beyond it is not. A",
            "destination block that is not in force, or whose capacity is",
            "zero, is caught by this rung as well.",
            "",
            "RULE Y07.7  The duplicate rung.",
            "The duplicate rung is the last rung. Among the orders of one",
            "cluster, the canonical one is the first in canonical event order",
            "that no earlier rung caught, and every later member of that",
            "cluster is caught here. So an order that carries an unknown box",
            "and is also a duplicate is set aside as an unknown box, and a",
            "cluster whose first member is caught by an earlier rung has its",
            "second member as its canonical one.",
            "",
            "RULE Y07.8  A set aside order changes nothing.",
            "An order the ladder catches moves no box, occupies no slot,",
            "consumes no reservation and frees no capacity. It stays in the",
            "published record, and the capacity a set aside order would have",
            "released is never counted as released.",
            "",
            "PUBLISHES  move_eligibility.csv, rejected_moves.tsv,",
            "rejection_reasons.csv, accepted_moves.csv",
        ]
    if tag == "y08":
        return [
            "This stage carries the yard state forward through the shift.",
            "",
            "RULE Y08.1  What an admitted order does.",
            "An admitted order takes its box out of the cell it stood in, if",
            "it stood in one, and puts it in the block, row and tier the order",
            "names. The count of the block it left falls by one and the count",
            "of the block it enters rises by one.",
            "",
            "RULE Y08.2  The history.",
            "One row is published per admitted order, in ascending event key,",
            "carrying where the box came from and where it went. A box that",
            "had no yard position carries the not supplied marker in the three",
            "from columns and a was_stacked of no.",
            "",
            "RULE Y08.3  The closing state.",
            "The closing position of a box is where its last admitted order",
            "put it, or its opening position when no order moved it, or no",
            "position at all when it was off the yard and stayed there.",
            "",
            "RULE Y08.4  The per slot occupancy.",
            "The occupancy of a block at the close of a slot is the occupancy",
            "after every admitted order of that slot and of every earlier slot",
            "has been carried out, and before any order of a later slot. The",
            "capacity stage reads these snapshots.",
            "",
            "RULE Y08.5  Every block is published.",
            "Every block in force appears in the published occupancy, an empty",
            "one included, with its opening count, its closing count and its",
            "closing free capacity.",
            "",
            "PUBLISHES  yard_occupancy.psv, container_state_history.psv,",
            "container_state_final.csv",
        ]
    if tag == "y09":
        return [
            "This stage sets the planned stream against the physical stream.",
            "The two are separate sources of evidence about one movement and",
            "neither is a copy of the other.",
            "",
            "RULE Y09.1  Which confirmation belongs to an order.",
            "A confirmation belongs to an order when it names that order. When",
            "more than one confirmation names one order the one with the",
            "lowest confirmed minute is the one that counts. A confirmation",
            "may carry a minute earlier than the minute its order was raised;",
            "that is ordinary and changes nothing about which confirmation",
            "counts.",
            "",
            "RULE Y09.2  The movement state.",
            "An admitted order with a landed confirmation is confirmed. An",
            "admitted order with a confirmation in any other state is aborted.",
            "An admitted order with no confirmation is unconfirmed. An order",
            "the ladder set aside is contradicted when a landed confirmation",
            "names it, and set_aside otherwise.",
            "",
            "RULE Y09.3  A confirmation does not overturn the ladder.",
            "A contradicted order stays set aside. Its box does not move, no",
            "capacity is taken and no reservation is consumed. The",
            "contradiction is recorded and nothing else about the shift",
            "changes because of it. Treating a landed confirmation as evidence",
            "that the move happened, and moving the box, is wrong.",
            "",
            "RULE Y09.4  A confirmation with no order.",
            "A confirmation whose order_id is empty belongs to no order. It is",
            "counted as a loose confirmation, in ascending confirm_id, and it",
            "moves nothing.",
            "",
            "PUBLISHES  movement_accounting.jsonl",
        ]
    if tag == "y10":
        return [
            "This stage derives the rehandles and charges the equipment. Both",
            "are read off the state this shift produced, not counted off the",
            "source journals.",
            "",
            "RULE Y10.1  What a rehandle is.",
            "An admitted order is a rehandle when the box it moves was",
            "standing in a yard cell immediately before that order. An order",
            "that puts a box on the yard for the first time is a placement and",
            "not a rehandle. The rehandle count of a box is the number of its",
            "admitted orders that were rehandles, and it is derived from the",
            "state history and not from any count the source papers carry.",
            "The rehandle ledger carries one record per box that the state",
            "history holds at least one admitted order for. A box no admitted",
            "order moved has no record in it at all.",
            "",
            "RULE Y10.2  The charge.",
            "Every admitted order carries the base move charge issued by the",
            "live workbook sheet. A rehandle carries, on top of that, the",
            "surcharge its tier depth attracts.",
            "",
            "RULE Y10.3  The tier depth.",
            "The tier depth of a rehandle is the tier the box was standing at",
            "before the order, not the tier it moves to.",
            "",
            "RULE Y10.4  The surcharge ladder.",
            "The ladder is issued by berth_operations_memo.pdf and is carried",
            "in no other paper. The surcharge of a depth is the surcharge of",
            "the highest rung at or below that depth. A depth beyond the last",
            "rung carries the surcharge of the last rung. A depth of one",
            "carries no surcharge.",
            "",
            "RULE Y10.5  The equipment allowance.",
            "The applicable revision of an equipment unit is settled through",
            "revision_precedence.toml. Confirmed movements are charged to the",
            "unit their confirmation names, in ascending event key. A unit",
            "that has carried exactly its allowance is inside it. The movement",
            "that would take a unit one past its allowance is recorded as an",
            "equipment exception and is charged to nothing, and so are the",
            "movements after it. A confirmation naming a unit with no",
            "applicable revision is an exception of its own kind.",
            "",
            "RULE Y10.6  A unit that carries nothing.",
            "A unit whose allowance is zero is published with a used count of",
            "zero, and so is a unit no movement was charged to. Both are",
            "published; a unit the register does not carry is not.",
            "",
            "RULE Y10.7  What the equipment usage document publishes.",
            "The used figure of a unit is the count of movements charged to",
            "it. The minutes figure is that used count multiplied by the base",
            "minutes its applicable revision declares, so a unit charged no",
            "movement publishes zero minutes whatever its base minutes say.",
            "The within_allowance figure reads yes whenever the used count is",
            "at or below the allowance. A unit that turned a movement away at",
            "RULE Y10.5 still reads yes, because the movement it turned away",
            "was never charged to it and its used count never passed the",
            "allowance.",
            "",
            "PUBLISHES  rehandle_ledger.jsonl, equipment_usage.csv,",
            "equipment_exceptions.tsv",
        ]
    if tag == "y11":
        return [
            "This stage publishes what each block held and what was withheld",
            "from it, slot by slot.",
            "",
            "RULE Y11.1  One row per block and slot.",
            "Every block in force is published against every slot of the",
            "shift, whatever happened in it.",
            "",
            "RULE Y11.2  A block that is out of use.",
            "When slot_grid_calendar.csv seals a block for a slot, or says it",
            "is not in service, or the block has no capacity at all, the whole",
            "capacity is published as unavailable, the reserved figure is zero",
            "and the available figure is zero. The occupied figure is still",
            "the boxes that stood there.",
            "",
            "RULE Y11.3  A block that is in use.",
            "The free capacity is the capacity less the boxes standing there",
            "at the close of that slot. The reserved figure is the standing",
            "credit, at the close of that slot, of every reservation covering",
            "that block and slot, capped at the free capacity. The available",
            "figure is the free capacity less the reserved figure, and never",
            "below zero.",
            "",
            "RULE Y11.4  Utilisation.",
            "The utilisation of a block is its closing count over its",
            "capacity, published at exactly nine decimal places. A block with",
            "no capacity has a utilisation of 0.000000000 and is published",
            "with it.",
            "",
            "RULE Y11.5  Slot accounting.",
            "Every slot of the shift is published with its event count, its",
            "admitted count, its set aside count and its confirmed count, a",
            "slot in which nothing happened included. Events belonging to no",
            "slot are published on a row of their own under the not supplied",
            "marker, after every slot.",
            "",
            "PUBLISHES  yard_capacity.csv, yard_reservations.psv,",
            "block_utilization.csv, slot_accounting.csv",
        ]
    if tag == "y12":
        return [
            "This stage joins the yard state this shift produced to the cutoff",
            "notices, which come from a different source. A box can be",
            "standing in the yard and still be ineligible, and the two facts",
            "are settled by different papers.",
            "",
            "RULE Y12.1  The cutoff in force.",
            "Among the notices of cutoff_notice_board.tsv that name this shift",
            "and are not superseded, the one with the highest notice_seq is in",
            "force for its vessel. A vessel with no such notice has no cutoff",
            "in force.",
            "",
            "RULE Y12.2  The ready minute.",
            "The ready minute of a box is the raised minute of the last",
            "admitted order that moved it. A box no order moved has a ready",
            "minute of zero.",
            "",
            "RULE Y12.3  The cutoff boundary.",
            "A box whose ready minute is less than or equal to the cutoff",
            "minute is inside the cutoff. Strictly greater is outside it. A",
            "ready minute exactly equal to the cutoff minute is inside.",
            "",
            "RULE Y12.4  The order the reasons are put in.",
            "A box is settled by the first of these that holds, and the",
            "published reason is that one: its vessel has no applicable call,",
            "EL_NO_VESSEL; its vessel carries no stowage obligation for it,",
            "EL_NO_OBLIGATION; that obligation holds it, EL_HELD; it has no",
            "closing yard position, EL_OFF_YARD; its vessel has no cutoff in",
            "force, EL_NO_CUTOFF; it is outside the cutoff, EL_AFTER_CUTOFF.",
            "A box none of these catches is eligible and carries EL_OK.",
            "",
            "RULE Y12.5  The cutoff waiver.",
            "A cutoff_waiver naming the last admitted order of a box lifts the",
            "cutoff test for that box alone. It lifts nothing else.",
            "",
            "RULE Y12.6  Every box is published.",
            "Every box with an applicable master record is published with its",
            "verdict, eligible or not, and a vessel with no eligible box at",
            "all is still published in the cutoff status with counts of zero.",
            "",
            "RULE Y12.7  What the cutoff status counts.",
            "The boxes_outside figure of vessel_cutoff_status.csv is the count",
            "of the vessel's boxes this stage settled at EL_AFTER_CUTOFF, and",
            "boxes_inside is the rest of boxes_total. The two figures are read",
            "off the published verdict and not off a fresh comparison of ready",
            "minute against cutoff minute, so a box a cutoff waiver lifted the",
            "test for counts as inside, and so does a box an earlier reason",
            "settled before the cutoff was ever reached.",
            "",
            "PUBLISHES  load_eligibility.csv, vessel_cutoff_status.csv,",
            "vessel_container_manifest.psv",
        ]
    if tag == "y13":
        return [
            "This stage rations the quay and settles what each vessel loads.",
            "The ration is the one derivation of this shift that is not a",
            "lookup: it is a damped iterate run a fixed number of times, and",
            "the number of times is part of the answer.",
            "",
            "RULE Y13.1  The pairings.",
            "The ration is run once for each pairing of a slot with a",
            "reporting berth, slots ascending and berths ascending inside a",
            "slot. The vessels of a pairing are those whose applicable berth",
            "is that berth and which carry an applicable demand return for",
            "that slot, in ascending vessel_id.",
            "",
            "RULE Y13.2  The applicable demand return.",
            "In quay_demand_returns.csv a return counts only when its",
            "return_state is filed. Among the filed returns of one vessel and",
            "slot the one with the highest revision_seq is applicable. A",
            "vessel with no filed return for a slot is not in that pairing at",
            "all.",
            "",
            "RULE Y13.3  The pool.",
            "The applicable berth window is the row of berth_window_register",
            ".csv with the highest revision_seq that is not marked draft. The",
            "pool a pairing rations is the smaller of the crane minutes that",
            "window declares and the sum of the gang minutes the quay gang",
            "roster of berth_operations_memo.pdf crews for that berth and",
            "slot. The roster is carried in no other paper.",
            "",
            "RULE Y13.4  The ceiling.",
            "The admissible minutes of a vessel in a slot are issued by the",
            "vessel slot ceiling register of the live workbook sheet. A",
            "pairing member the register does not carry has a ceiling of zero.",
            "",
            "RULE Y13.5  The iterate.",
            "Every share starts at zero. The ration runs exactly the number of",
            "passes the pass budget of berth_operations_memo.pdf allows, and",
            "each pass does the following in this order.",
            "",
            "  a  The need of a vessel is its applicable declared minutes less",
            "     its standing share, and never below zero. The unallocated",
            "     pool is the pool less the sum of the standing shares. When",
            "     the total need is zero, or the unallocated pool is zero or",
            "     less, the ration stops early and the standing shares are the",
            "     shares.",
            "",
            "  b  The target of a vessel is its standing share plus the",
            "     unallocated pool apportioned across the needs.",
            "",
            "  c  The target is capped at the vessel's ceiling.",
            "",
            "  d  What the caps freed is redistributed inside the cross",
            "     classification of berth and service group. A vessel receives",
            "     freed minutes only from vessels sharing both its berth and",
            "     its service group, apportioned across the needs of the",
            "     members of that cell whose target the cap did not bind.",
            "     Freed minutes in a cell with no such member stay unassigned",
            "     and are published as the unplaced minutes of that pass.",
            "     Redistributing across the whole pairing rather than inside",
            "     the cell is wrong and gives different shares.",
            "",
            "  e  The aim of a vessel is its capped target plus what it",
            "     received, capped at its ceiling again.",
            "",
            "  f  The share moves from where it stands toward the aim by the",
            "     damping fraction of the live workbook sheet.",
            "",
            "  g  The result is rounded to whole crane minutes. This rounding",
            "     happens at the end of every pass. The next pass begins from",
            "     the rounded share, so the residues do not accumulate, and a",
            "     ration that carries exact shares through every pass and",
            "     rounds once at the end is a different ration and gives",
            "     different numbers.",
            "",
            "  h  A share that has not reached its rounded aim, and whose",
            "     damped move rounded to no movement at all, moves instead by",
            "     the minimum step of berth_operations_memo.pdf toward the",
            "     aim, and never past it.",
            "",
            "RULE Y13.6  The budget is a count, not a test.",
            "The passes stop when the budget is spent. The ration is not run",
            "to convergence, it is not iterated until the shares stop moving,",
            "and it is not solved in closed form. The shares standing when the",
            "budget is spent are the published shares whether or not they have",
            "settled, and on this shift most of them have not.",
            "",
            "RULE Y13.7  The share of a vessel.",
            "The share of a vessel over the shift is the sum of its shares",
            "across the pairings it belonged to.",
            "",
            "RULE Y13.8  The load order.",
            "The eligible boxes of a vessel are put in order by the keys",
            "stowage_ordering_directive.docx names, read left to right, each",
            "ascending. The class rank register of that directive is carried",
            "in no other paper.",
            "",
            "RULE Y13.9  What a box costs.",
            "A box costs its teu factor multiplied by the base minutes of the",
            "quay crane unit, which is the applicable unit of class quay_crane",
            "with the lowest equipment_id.",
            "",
            "RULE Y13.10  Where the load stops.",
            "The boxes are taken in load order while the running total stays",
            "within the vessel's share. The first box that would take the",
            "total past the share is deferred, and so is every box after it.",
            "The load is a sequence and not a selection: a later box that",
            "would have fitted is deferred all the same.",
            "",
            "RULE Y13.11  The republished charge.",
            "A deferred box has its charge republished as the charge it was",
            "assessed plus the surcharge of the last rung of the surcharge",
            "ladder. A box that was never moved was assessed nothing and is",
            "republished at the last rung alone.",
            "",
            "PUBLISHES  ration_trace.jsonl, load_sequence_ledger.json,",
            "departure_ledger.json, deferred_containers.tsv",
        ]
    if tag == "y14":
        return [
            "This stage closes the accounts. Every figure here is read off the",
            "ledgers the earlier stages published and none of it is derived a",
            "second time from the source papers.",
            "",
            "RULE Y14.1  The control totals.",
            "The measures published in terminal_reconciliation.csv are the ones",
            "output_schema_reference.md names, in ascending measure name.",
            "",
            "RULE Y14.2  The identity checks.",
            "Totals that agree by category can still disagree by identity, so",
            "each check compares the identity sets and not the counts. The",
            "checks are the four output_schema_reference.md names, and each",
            "publishes yes or no.",
            "",
            "RULE Y14.3  The reports.",
            "One report is published for each berth of",
            "berth_reporting_roster.conf, whatever it rationed, a berth that",
            "rationed nothing included.",
            "",
            "RULE Y14.4  The digests.",
            "publication_manifest.json carries a digest of every document",
            "beside it. The core digest covers the six core documents",
            "output_schema_reference.md names and the publication digest",
            "covers every other document of the publication. Both are taken",
            "over lines of document name, one space and the document digest, in",
            "the artifact order the schema reference lists, each line ending",
            "in one line feed. The digests are taken last, after every other",
            "document is written.",
            "",
            "PUBLISHES  terminal_reconciliation.csv, exception_summary.tsv,",
            "vessel_reconciliation.xml, audit_trail.conf, the berth reports,",
            "daily_operational_summary.md, final_control_totals.json,",
            "publication_manifest.json",
        ]
    return []


def write_stage_specs(inst, root):
    for tag, slug, title in STAGE_TITLES:
        body = _stage_body(tag, inst)
        if tag == "y06":
            body = [line % inst["controls"]["protection_depth"] if "%d" in line else line
                    for line in body]
        lines = ["STAGE %s  %s" % (tag.upper(), title),
                 "shift %s" % inst["shift_id"], ""] + body
        write_lines(root / ("spec_stage_%s_%s.md" % (tag, slug)), lines)

"""Navigation papers, the schema reference and the two contracts."""

DELIMITED_LAYOUT = [
    ("canonical_events.csv", ",", ["event_key", "order_id", "box_id", "source_system",
                                   "source_priority", "event_seq", "raised_min",
                                   "slot_code", "cluster_tag"],
     "ascending event_key"),
    ("container_dimensions.csv", ",", ["box_id", "iso_length", "teu_factor", "box_class",
                                       "vessel_id", "mass_kg", "mass_state"],
     "ascending box_id"),
    ("vessel_obligation.csv", ",", ["vessel_id", "voyage", "berth_id", "service_group",
                                    "destination", "voyage_sequence",
                                    "applicable_revision"], "ascending vessel_id"),
    ("initial_occupancy.psv", "|", ["block_id", "zone", "rows", "tiers_max",
                                    "slot_capacity", "opening_boxes", "opening_free"],
     "ascending block_id"),
    ("event_order.csv", ",", ["event_key", "order_id", "slot_code", "source_priority",
                              "event_seq", "box_id"], "ascending event_key"),
    ("move_eligibility.csv", ",", ["event_key", "order_id", "box_id", "slot_code",
                                   "to_block", "to_row", "to_tier", "outcome",
                                   "reason_code"], "ascending event_key"),
    ("yard_occupancy.psv", "|", ["block_id", "zone", "slot_capacity", "opening_boxes",
                                 "closing_boxes", "closing_free"], "ascending block_id"),
    ("yard_capacity.csv", ",", ["block_id", "slot_code", "slot_capacity", "occupied",
                                "reserved", "unavailable", "available"],
     "ascending block_id then ascending slot_code"),
    ("load_eligibility.csv", ",", ["box_id", "vessel_id", "eligible", "reason_code",
                                   "ready_min"], "ascending box_id"),
    ("terminal_reconciliation.csv", ",", ["measure", "value"], "ascending measure"),
    ("rejected_moves.tsv", "\t", ["event_key", "order_id", "box_id", "slot_code",
                                  "reason_code"], "ascending event_key"),
    ("rejection_reasons.csv", ",", ["reason_code", "order_count"],
     "the rung order the admission ladder prints"),
    ("accepted_moves.csv", ",", ["event_key", "order_id", "box_id", "slot_code",
                                 "to_block", "to_row", "to_tier"], "ascending event_key"),
    ("container_state_history.psv", "|", ["box_id", "event_key", "from_block", "from_row",
                                          "from_tier", "to_block", "to_row", "to_tier",
                                          "was_stacked"], "ascending event_key"),
    ("container_state_final.csv", ",", ["box_id", "block_id", "row_no", "tier_no",
                                        "moves_applied", "state"], "ascending box_id"),
    ("dependency_order.csv", ",", ["position", "order_id", "event_key"],
     "ascending position"),
    ("yard_reservations.psv", "|", ["reservation_id", "block_id", "service_group",
                                    "first_slot", "last_slot", "asked", "withheld",
                                    "consumed", "unmet"], "ascending reservation_id"),
    ("block_utilization.csv", ",", ["block_id", "slot_capacity", "closing_boxes",
                                    "utilisation_ratio"], "ascending block_id"),
    ("equipment_usage.csv", ",", ["equipment_id", "equipment_class", "allowance", "used",
                                  "minutes", "within_allowance"], "ascending equipment_id"),
    ("equipment_exceptions.tsv", "\t", ["event_key", "order_id", "equipment_id",
                                        "reason_code"], "ascending event_key"),
    ("slot_accounting.csv", ",", ["slot_code", "events", "admitted", "set_aside",
                                  "confirmed"],
     "ascending slot_code, with the not supplied row last"),
    ("vessel_cutoff_status.csv", ",", ["vessel_id", "notice_id", "cutoff_min",
                                       "boxes_total", "boxes_inside", "boxes_outside"],
     "ascending vessel_id"),
    ("vessel_container_manifest.psv", "|", ["vessel_id", "box_id", "class_rank",
                                            "stow_sequence", "bay_no", "teu_factor",
                                            "mass_kg"],
     "ascending vessel_id then ascending box_id"),
    ("deferred_containers.tsv", "\t", ["vessel_id", "box_id", "load_minutes",
                                       "assessed_cents", "published_cents"],
     "ascending vessel_id then ascending box_id"),
    ("exception_summary.tsv", "\t", ["exception_kind", "granted", "withdrawn"],
     "ascending exception_kind"),
]

JSONL_LAYOUT = [
    ("movement_accounting.jsonl",
     ["event_key", "order_id", "box_id", "planned_outcome", "confirm_id",
      "confirmed_min", "movement_state"], "ascending event_key"),
    ("rehandle_ledger.jsonl",
     ["box_id", "moves", "rehandles", "tier_depths", "surcharge_cents",
      "charge_cents"], "ascending box_id"),
    ("ration_trace.jsonl",
     ["slot_code", "berth_id", "pass_no", "pool_minutes", "unplaced_minutes",
      "shares"],
     "ascending slot_code, then ascending berth_id, then ascending pass_no"),
]

MEASURES = ["admitted_moves", "assessed_cents", "boxes_on_yard", "canonical_events",
            "confirmed_moves", "contradicted_moves", "deferred_boxes", "eligible_boxes",
            "equipment_exceptions", "loaded_boxes", "loaded_minutes",
            "loose_confirmations", "published_cents", "rationed_minutes",
            "rehandle_moves", "set_aside_moves"]

IDENTITIES = ["loaded_and_deferred_partition_eligible", "moved_boxes_all_on_yard",
              "decision_count_matches_events", "republished_covers_deferred"]

ELIGIBILITY_CODES = ["EL_OK", "EL_NO_VESSEL", "EL_NO_OBLIGATION", "EL_HELD",
                     "EL_OFF_YARD", "EL_NO_CUTOFF", "EL_AFTER_CUTOFF"]

MOVEMENT_STATES = ["confirmed", "aborted", "unconfirmed", "contradicted", "set_aside"]

EQUIPMENT_CODES = ["EQ_UNKNOWN_UNIT", "EQ_BEYOND_ALLOWANCE"]


def write_schema_reference(inst, root):
    lines = [
        "OUTPUT SCHEMA REFERENCE",
        "shift %s" % inst["shift_id"],
        "",
        "Every published document is listed here with its exact header line,",
        "its column order and its row order. A document that disagrees with",
        "this paper in a header, a column order, a row order, a key name or a",
        "value type is wrong however right its numbers are.",
        "",
        "SECTION 1  ARTIFACT ORDER",
        "",
        "This is the order the manifest digests the publication in.",
        "",
    ]
    for name in ALL_DOCUMENTS:
        lines.append("  %s" % name)
    lines += ["", "SECTION 2  THE SIX CORE DOCUMENTS", "",
              "The core digest covers exactly these, in this order.", ""]
    for name in CORE_DOCUMENTS:
        lines.append("  %s" % name)
    lines += ["",
              "The publication digest covers every other document of the",
              "publication except the manifest itself, in the artifact order of",
              "section 1.",
              "", "SECTION 3  DELIMITED DOCUMENTS", ""]
    for name, sep, header, order in DELIMITED_LAYOUT:
        shown = {",": "comma", "|": "pipe", "\t": "tab"}[sep]
        lines.append("  %s" % name)
        lines.append("    separator  %s" % shown)
        lines.append("    header     %s" % sep.join(header))
        lines.append("    row order  %s" % order)
        lines.append("")
    lines += ["SECTION 4  LINE DELIMITED JSON DOCUMENTS", "",
              "One object per line, keys in the order listed, no space after a",
              "separator.", ""]
    for name, keys, order in JSONL_LAYOUT:
        lines.append("  %s" % name)
        lines.append("    keys       %s" % ", ".join(keys))
        lines.append("    row order  %s" % order)
        lines.append("")
    lines += [
        "  The shares value of ration_trace.jsonl is an array of objects",
        "  carrying vessel_id and share_minutes, in ascending vessel_id.",
        "  The tier_depths value of rehandle_ledger.jsonl is an array of",
        "  integers in the order the rehandles happened.",
        "",
        "  An order that no confirmation belongs to publishes confirm_id as",
        "  the not supplied marker and confirmed_min as the whole number 0.",
        "  The two absent fields take different forms on purpose: confirm_id",
        "  is an identifier and carries the marker, confirmed_min is a whole",
        "  quantity and carries a zero, the same form an absent mass takes at",
        "  stage Y02.",
        "",
        "SECTION 5  JSON DOCUMENTS",
        "",
        "  cycle_break_report.json",
        "    keys       shift_id, protection_depth, component_count, components",
        "    component  component_key, member_count, members, edge_removed,",
        "               edge_weight, before_order, after_order, protected_count",
        "    order      the order the components were worked in",
        "",
        "  load_sequence_ledger.json",
        "    keys       shift_id, minutes_per_teu, stowage_keys, vessels",
        "    stowage_keys  an array of the ordering key names the stowage",
        "               directive issues, in its key position order",
        "    vessel     vessel_id, share_minutes, eligible_count, loaded_count,",
        "               deferred_count, loaded_minutes, unused_minutes",
        "    order      ascending vessel_id",
        "",
        "  departure_ledger.json",
        "    keys       shift_id, vessels",
        "    vessel     vessel_id, berth_id, share_minutes, loaded_minutes,",
        "               unused_minutes, boxes",
        "    box        load_position, box_id, load_minutes",
        "    order      ascending vessel_id, boxes in ascending load_position",
        "",
        "  berth_report_<berth_id>.json, one per reporting berth",
        "    keys       shift_id, berth_id, vessel_count, vessels, pool_minutes,",
        "               rationed_minutes, pairings",
        "    pairing    slot_code, berth_id, pool_minutes, declared_minutes,",
        "               crewed_minutes, vessel_count, rationed_minutes",
        "    order      pairings in ascending slot_code",
        "    vessels    an array of vessel_id strings, ascending, carrying",
        "               every vessel whose applicable berth is this one",
        "               whatever it rationed; vessel_count is its length",
        "    minutes    pool_minutes and rationed_minutes at the head of the",
        "               document are the sums of those figures over the",
        "               pairings listed below them",
        "",
        "  final_control_totals.json",
        "    keys       shift_id, live_sheet_name, minutes_per_teu, totals,",
        "               identities",
        "",
        "  publication_manifest.json",
        "    keys       shift_id, core_digest, publication_digest,",
        "               document_count, documents",
        "    document   name, sha256, bytes",
        "    order      the artifact order of section 1",
        "",
        "  document_count is the number of documents the publication carries,",
        "  which is every name in the artifact order of section 1 and so",
        "  counts the manifest itself. The documents array carries an entry",
        "  for each of the others and never one for the manifest, so it holds",
        "  one entry fewer than document_count.",
        "",
        "SECTION 6  THE CONTROL MEASURES",
        "",
        "terminal_reconciliation.csv publishes exactly these measures, and",
        "final_control_totals.json carries the same set under totals.",
        "",
    ]
    for name in MEASURES:
        lines.append("  %s" % name)
    lines += ["", "SECTION 7  THE IDENTITY CHECKS", "",
              "vessel_reconciliation.xml and final_control_totals.json carry",
              "exactly these four, each answering yes or no.", ""]
    for name in IDENTITIES:
        lines.append("  %s" % name)
    lines += ["", "SECTION 8  CLOSED VOCABULARIES", "",
              "move_eligibility.csv outcome takes admitted or set_aside.",
              "move_eligibility.csv reason_code takes the not supplied marker",
              "or one of the rung codes the admission ladder prints.",
              "", "load_eligibility.csv reason_code takes one of:", ""]
    for code in ELIGIBILITY_CODES:
        lines.append("  %s" % code)
    lines += ["", "movement_accounting.jsonl movement_state takes one of:", ""]
    for code in MOVEMENT_STATES:
        lines.append("  %s" % code)
    lines += ["", "equipment_exceptions.tsv reason_code takes one of:", ""]
    for code in EQUIPMENT_CODES:
        lines.append("  %s" % code)
    lines += ["",
              "container_state_final.csv state takes stacked or off_yard.",
              "container_dimensions.csv mass_state takes declared or",
              "not_declared.",
              "container_state_history.psv was_stacked takes yes or no.",
              "equipment_usage.csv within_allowance takes yes or no.",
              "load_eligibility.csv eligible takes yes or no.",
              "",
              "SECTION 9  THE TWO FREE FORM DOCUMENTS",
              "",
              "audit_trail.conf carries, in this order, a shift section with",
              "shift_id, live_sheet_name and reference; a counts section with",
              "the control measures of section 6 in ascending measure name; a",
              "ladder section with the rung codes in the order the admission",
              "ladder prints them; and a movement section with the movement",
              "states present, in ascending state name. A key line is written",
              "as the key, one space, an equals sign, one space and the value.",
              "A section header is written in square brackets and is preceded",
              "by one empty line except at the head of the file, which opens",
              "with one comment line.",
              "",
              "daily_operational_summary.md opens with a level one heading, a",
              "blank line, one line naming the shift and the reference and a",
              "blank line. Then one bullet per control measure in ascending",
              "measure name, written as a hyphen, one space, the measure name,",
              "a colon, one space and the value. Then a blank line, a level two",
              "heading reading Ladder, a blank line and one bullet per rung in",
              "the printed rung order. Then a blank line, a level two heading",
              "reading Identity checks, a blank line and one bullet per",
              "identity check in the order of section 7.",
              ""]
    write_lines(root / "output_schema_reference.md", lines)


def write_serialisation_contract(inst, root):
    write_lines(root / "serialisation_and_digest_contract.md", [
        "SERIALISATION AND DIGEST CONTRACT",
        "shift %s" % inst["shift_id"],
        "",
        "SECTION 1  BYTES",
        "",
        "Every published document is written in UTF-8 with no byte order",
        "mark. Every line ends in one line feed and no carriage return",
        "appears anywhere. Every document ends in exactly one line feed, and",
        "no document ends in a blank line.",
        "",
        "SECTION 2  DELIMITED DOCUMENTS",
        "",
        "The header line is written first, then one line per row. A field is",
        "written as it stands with no quoting, no padding and no thousands",
        "separator. A field that has no value carries the not supplied marker,",
        "which is one hyphen. An empty document is its header line and",
        "nothing else, followed by one line feed.",
        "",
        "SECTION 3  LINE DELIMITED JSON",
        "",
        "One object per line, written with a comma between members and a",
        "colon between a key and its value, with no space after either. Keys",
        "appear in the order the schema reference lists and are never sorted.",
        "An empty document is a file of zero bytes.",
        "",
        "SECTION 4  JSON",
        "",
        "Written with an indent of two spaces, keys in the order the schema",
        "reference lists and never sorted, and one line feed after the closing",
        "brace. An empty array is written as a pair of square brackets on one",
        "line and an empty object as a pair of braces on one line.",
        "",
        "SECTION 5  XML",
        "",
        "The document opens with the declaration",
        "",
        '    <?xml version="1.0" encoding="utf-8"?>',
        "",
        "Every element is written with an opening tag and a closing tag, and",
        "the self closing form is never used, not even for an element with no",
        "content. Nesting is indented by two spaces per level. The five",
        "characters that XML reserves are escaped and nothing else is.",
        "",
        "SECTION 6  NUMBERS",
        "",
        "A whole quantity is written as a plain integer with no sign when it",
        "is zero and no leading zero. A ratio is written at exactly nine",
        "decimal places. Money is written as a whole number of cents. Crane",
        "minutes are written as whole minutes. Binary floating point appears",
        "nowhere in the derivation and no value is published as a floating",
        "point literal.",
        "",
        "SECTION 7  DIGESTS",
        "",
        "A digest is the SHA-256 of the bytes of a document, written in lower",
        "case hexadecimal. The core digest and the publication digest are",
        "each taken over a block built by writing, for every document the",
        "digest covers and in the artifact order of the schema reference, the",
        "document name, one space, the document digest and one line feed. The",
        "manifest digests every document beside it and never itself.",
    ])


def write_program_contract(inst, root):
    write_lines(root / "yardledger_program_contract.md", [
        "PROGRAM CONTRACT",
        "shift %s" % inst["shift_id"],
        "",
        "The program published beside the documents is yardledger.py.",
        "",
        "SECTION 1  HOW IT IS CALLED",
        "",
        "    python3 yardledger.py --data <input directory> --out <output directory>",
        "",
        "The two options may be given in either order. The program creates",
        "the output directory when it is absent, writes the whole publication",
        "there and exits with status zero. It writes nothing else into that",
        "directory and it leaves the input directory byte for byte as it",
        "found it.",
        "",
        "SECTION 2  WHAT IT MAY DEPEND ON",
        "",
        "The Python standard library and nothing else. No package is",
        "installed for it and none may be imported. The workbook, the",
        "memorandum and the directive are read with the standard library.",
        "",
        "SECTION 3  WHAT IT MAY HOLD",
        "",
        "Nothing about this shift. Every identifier, control value,",
        "threshold, boundary, rung code and vocabulary member is read from",
        "the directory the program is pointed at. A block identifier, a berth",
        "identifier, a damping fraction, a pass budget, a slot length, a",
        "class rank or a rung order written into the program is a defect,",
        "because the same program is run against other shifts whose papers",
        "carry different ones.",
        "",
        "SECTION 4  DETERMINISM",
        "",
        "Two runs over one input directory produce identical bytes. The same",
        "shift placed under a different directory name produces those bytes",
        "again, so no behaviour may depend on a path, a file modification",
        "time, a clock, a locale, an environment variable or a random source.",
        "",
        "SECTION 5  WHAT IT MAY READ",
        "",
        "Only the directory it is pointed at. It does not reach for any other",
        "path on the machine, and it does not read the directory the",
        "publication is graded from.",
        "",
        "SECTION 6  WHAT SHAPE IT TAKES",
        "",
        "The fourteen stages appear in the program as fourteen separately",
        "named steps, in the order terminal_contract_overview.md lists them,",
        "so a reader can put a published figure back to the stage that",
        "derived it. A program that folds the stages into one step meets none",
        "of this section however right its numbers are.",
    ])


def write_navigation(inst, root):
    write_lines(root / "readme_first.txt", [
        "KESTREL POINT CONTAINER TERMINAL",
        "WORKING PAPERS OF ONE OPERATING SHIFT",
        "",
        "Shift %s, reference %s." % (inst["shift_id"], inst["shift_reference"]),
        "",
        "The shift closed, its operational ledgers were published, the",
        "publication was withdrawn after the vessel agents disputed it, and",
        "the superintendent who ran the shift has left. What survives is this",
        "directory. Every value in it was minted for this shift alone, so no",
        "source outside this directory settles anything.",
        "",
        "Read terminal_contract_overview.md next. It names the fourteen",
        "stages and the specification governing each of them.",
        "",
        "data_lineage.md maps every paper to the stage that reads it, and",
        "names the papers that govern nothing.",
        "",
        "The file names describe a role and not a content. Open them.",
        "",
        "Three papers are not plain text. quay_capacity_workbook.xlsx,",
        "berth_operations_memo.pdf and stowage_ordering_directive.docx carry",
        "control values that appear in no other paper of this shift. The",
        "workbook holds six sheets and only one of them is live.",
    ])

    write_lines(root / "terminal_contract_overview.md", [
        "TERMINAL CONTRACT OVERVIEW",
        "shift %s" % inst["shift_id"],
        "",
        "One shift is recomputed in fourteen stages, worked in the order",
        "below. Each stage reads the state the stages before it left and",
        "publishes the documents named in its specification.",
        "",
    ] + ["  %s  %-28s  spec_stage_%s_%s.md" % (tag.upper(), title, tag, slug)
         for tag, slug, title in STAGE_TITLES] + [
        "",
        "The cross cutting papers are rounding_and_arithmetic_policy.yaml,",
        "revision_precedence.toml, boundary_conventions.yaml,",
        "reserved_capacity_policy.toml, equipment_allowance_policy.toml,",
        "quay_ration_policy.toml, unit_register_dictionary.toml,",
        "publication_form_rules.toml and berth_reporting_roster.conf. A stage",
        "specification that names one of them is governed by it.",
        "",
        "The publication is described by output_schema_reference.md and",
        "serialisation_and_digest_contract.md. The program is described by",
        "yardledger_program_contract.md.",
        "",
        "Two stages take evidence from two sources at once. Stage Y09 sets",
        "the planned move stream against the physical confirmation stream.",
        "Stage Y12 joins the yard state this shift produced to the cutoff",
        "notices, which come from the vessel side and know nothing about the",
        "yard.",
        "",
        "Stage Y13 is the only stage of the shift that is not a lookup.",
    ])

    write_lines(root / "data_lineage.md", [
        "DATA LINEAGE",
        "shift %s" % inst["shift_id"],
        "",
        "Which paper feeds which stage.",
        "",
        "  box_master_register.csv               Y02",
        "  mass_declaration_returns.psv          Y02",
        "  stack_inventory_snapshot.csv          Y04",
        "  block_geometry_register.csv           Y04",
        "  slot_grid_calendar.csv                Y07 Y11",
        "  hold_reservation_notices.jsonl        Y07 Y11",
        "  yard_topology.xml                     Y04",
        "  move_order_journal.csv                Y01",
        "  withdrawn_order_journal.tsv           Y01",
        "  source_priority_register.csv          Y05",
        "  move_dependency_declarations.jsonl    Y06",
        "  crane_confirmation_feed.ndjson        Y09 Y10",
        "  handling_equipment_register.csv       Y10 Y13",
        "  vessel_call_register.csv              Y03",
        "  cutoff_notice_board.tsv               Y12",
        "  stowage_obligation_list.psv           Y12 Y13",
        "  berth_window_register.csv             Y13",
        "  quay_demand_returns.csv               Y13",
        "  operational_exception_notices.csv     Y07 Y12 Y14",
        "  quay_capacity_workbook.xlsx           Y02 Y10 Y13",
        "  berth_operations_memo.pdf             Y06 Y10 Y13",
        "  stowage_ordering_directive.docx       Y13",
        "",
        "These papers govern nothing. They are kept because the shift office",
        "keeps them, and no published quantity is taken from any of them.",
        "",
        "  box_class_supplement.csv              a working note. Where it",
        "                                        disagrees with the master",
        "                                        register the master register",
        "                                        stands.",
        "  legacy_tariff_extract.csv             the tariff this terminal",
        "                                        stopped using. The base move",
        "                                        charge comes from the live",
        "                                        workbook sheet.",
        "  shift_office_audit.db                 a copy of the move journal",
        "                                        and the box register.",
        "  quay_gang_roster inside the memo      feeds the pool at Y13, so the",
        "                                        memo is not a decoy.",
    ])

    # The note is written from what this shift actually contains, so it stays
    # true on every shift the corpus mints rather than only on the first one.
    cfg = inst["cfg"]
    unreached = []
    reached_here = []
    for present, block, short in (
        (cfg.get("orphan_obligation"),
         ["  EL_NO_OBLIGATION    a box whose vessel carries no stowage",
          "                      obligation for it, stage Y12"],
         ["  a box whose vessel carries no stowage obligation for it,",
          "  stage Y12"]),
        (cfg.get("orphan_cutoff"),
         ["  EL_NO_CUTOFF        a vessel with no cutoff notice in force,",
          "                      stage Y12"],
         ["  a vessel with no cutoff notice in force, stage Y12"]),
        (cfg.get("unknown_unit"),
         ["  EQ_UNKNOWN_UNIT     a confirmation naming an equipment unit with",
          "                      no applicable revision, stage Y10"],
         ["  a confirmation naming an equipment unit with no applicable",
          "  revision, stage Y10"]),
    ):
        if present:
            reached_here.append(short)
        else:
            unreached.append(block)
    sentinel = [
        "COVERAGE SENTINEL",
        "shift %s" % inst["shift_id"],
        "",
    ]
    if unreached:
        sentinel += [
            "This shift does not reach every branch the specifications",
            "describe. Read this before deciding a branch is absent because",
            "it does not apply.",
            "",
            "These outcomes are described by the specifications and this",
            "shift produces none of them. Implement them from the",
            "specification that names them, because other shifts reach them.",
            "",
        ]
        for block in unreached:
            sentinel += block
        sentinel.append("")
    else:
        sentinel += [
            "This shift reaches every branch the specifications describe.",
            "Read this before deciding a branch is absent because it does",
            "not apply.",
            "",
        ]
    sentinel.append("These branches are reached and are easy to miss:")
    sentinel.append("")
    for block in reached_here:
        sentinel += block
    write_lines(root / "corpus_sentinel_note.txt", sentinel + [
        "  a block of zero capacity, stage Y04",
        "  a block the opening stack leaves empty, stage Y04",
        "  a placement at exactly the maximum legal tier, stage Y07",
        "  a reservation asking for more than the free capacity, stage Y07",
        "  a reservation with no quantity supplied, stage Y07",
        "  an order raised exactly on a slot boundary, stage Y01",
        "  a cluster tied on every key except the order identifier, stage Y05",
        "  a confirmation naming no order, stage Y09",
        "  a confirmation earlier than the order it confirms, stage Y09",
        "  a box whose mass was never declared, stage Y02",
        "  a ration pairing whose pool runs out before the budget, stage Y13",
    ])

    write_lines(root / "glossary_and_field_dictionary.md", [
        "GLOSSARY AND FIELD DICTIONARY",
        "shift %s" % inst["shift_id"],
        "",
        "block          a stack of ground slots, addressed by row and tier.",
        "row_no         the row within a block, counting from one.",
        "tier_no        the height within a row, counting from one. Tier one",
        "               is the ground.",
        "slot           a two hour window of the shift, addressed SL01 upward.",
        "slot_capacity  rows multiplied by maximum tier.",
        "free capacity  slot capacity less the boxes standing in the block.",
        "reserved       free capacity a reservation withholds. Reserved",
        "               capacity is not free capacity.",
        "available      free capacity less what is reserved against this",
        "               order, never below zero.",
        "unavailable    the whole capacity of a block that is sealed, out of",
        "               service, or has no capacity at all.",
        "rehandle       an admitted move of a box that was already standing in",
        "               a yard cell.",
        "tier depth     the tier a box stood at before the move that lifted",
        "               it.",
        "canonical      the one member of a cluster the shift acts on.",
        "cluster        orders the journal groups under one cluster tag.",
        "ready minute   the raised minute of the last admitted move of a box.",
        "cutoff         the minute after which a box may no longer be loaded.",
        "pairing        one slot with one berth, the unit the quay ration runs",
        "               over.",
        "pool           the crane minutes a pairing has to give out.",
        "share          the crane minutes the ration gives a vessel.",
        "aim            the value a share is moving toward inside one pass.",
        "pass           one round of the ration.",
        "teu factor     the twenty foot equivalent of a length.",
        "dt             decitonne, a mass register.",
        "ct             centner, a mass register.",
        "not supplied   one hyphen, meaning the field was not supplied.",
    ])

    write_lines(root / "known_traps_and_footguns.md", [
        "KNOWN TRAPS AND FOOTGUNS",
        "shift %s" % inst["shift_id"],
        "",
        "Readings this terminal does not support. Each entry names a decision",
        "and the stage that owns it. The specification of that stage says",
        "which reading is in force; this paper does not repeat it.",
        "",
        "  the order the admission ladder rungs are put in            Y07",
        "  whether reserved capacity is settled before free capacity   Y07",
        "  what a reservation with no quantity supplied withholds      Y07",
        "  which member of a cluster is the canonical one              Y07",
        "  whether a placement at the maximum tier is lawful           Y07",
        "  which slot a minute on a boundary belongs to                Y01",
        "  which revision of a register is applicable                  Y02 Y03 Y04",
        "  which mass register a declaration is written in             Y02",
        "  what an absent mass means                                   Y02",
        "  which source system outranks which                          Y05",
        "  which edge a cyclic component loses                         Y06",
        "  whether a landed confirmation overturns the ladder          Y09",
        "  where a rehandle count comes from                           Y10",
        "  which tier the surcharge is read against                    Y10",
        "  whether a unit at exactly its allowance is inside it        Y10",
        "  which side of a cutoff an equal minute falls on             Y12",
        "  which sheet of the workbook is live                         Y02 Y13",
        "  how many passes the quay ration runs                        Y13",
        "  where the ration rounds                                     Y13",
        "  which vessels share in what a cap frees                     Y13",
        "  where a load stops                                          Y13",
    ])

"""Worked examples of the two free form documents and of one ration pass.

Every figure below belongs to a made up two berth shift that is not this one.
The examples fix the FORM of a document, never a value of this shift.
"""


def write_worked_examples(inst, root):
    write_lines(root / "worked_examples.md", [
        "WORKED EXAMPLES",
        "",
        "The shift used below, KP-0000-S00, is invented. It has two blocks,",
        "one berth, two measures and two rungs, so the shape of each document",
        "is visible in a few lines. None of its figures belong to this shift.",
        "Use these to settle the form of a document, and the schema reference",
        "and the serialisation contract to settle everything else.",
        "",
        "SECTION 1  audit_trail.conf",
        "",
        "```",
        "# The audit trail of one shift.",
        "[shift]",
        "shift_id = KP-0000-S00",
        "live_sheet_name = Example",
        "reference = QCR-000000",
        "",
        "[counts]",
        "admitted_moves = 2",
        "canonical_events = 3",
        "",
        "[ladder]",
        "LR_UNKNOWN_BOX = 1",
        "LR_SEALED_ZONE = 0",
        "",
        "[movement]",
        "confirmed = 2",
        "set_aside = 1",
        "```",
        "",
        "The file opens with the comment line exactly as printed. A section",
        "header is preceded by one empty line except the first. A key line is",
        "the key, one space, an equals sign, one space, the value.",
        "",
        "SECTION 2  daily_operational_summary.md",
        "",
        "```",
        "# Daily operational summary",
        "",
        "shift KP-0000-S00 at reference QCR-000000",
        "",
        "- admitted_moves: 2",
        "- canonical_events: 3",
        "",
        "## Ladder",
        "",
        "- LR_UNKNOWN_BOX: 1",
        "- LR_SEALED_ZONE: 0",
        "",
        "## Identity checks",
        "",
        "- loaded_and_deferred_partition_eligible: yes",
        "- moved_boxes_all_on_yard: yes",
        "```",
        "",
        "SECTION 3  vessel_reconciliation.xml",
        "",
        "```",
        '<?xml version="1.0" encoding="utf-8"?>',
        "<vessel_reconciliation>",
        "  <shift_id>KP-0000-S00</shift_id>",
        "  <vessels>",
        '    <vessel id="VS-000">',
        "      <berth_id>bt_example</berth_id>",
        "      <eligible_count>2</eligible_count>",
        "      <loaded_count>1</loaded_count>",
        "      <deferred_count>1</deferred_count>",
        "      <share_minutes>7</share_minutes>",
        "    </vessel>",
        "  </vessels>",
        '  <identity name="moved_boxes_all_on_yard">yes</identity>',
        "</vessel_reconciliation>",
        "```",
        "",
        "A vessel with no eligible box still carries its element with counts",
        "of zero. No element is ever written in the self closing form.",
        "",
        "SECTION 4  one pass of the quay ration",
        "",
        "Two vessels of one service group share a pool of 20 crane minutes.",
        "VS-A declares 14 minutes and VS-B declares 6. Neither ceiling binds.",
        "The damping fraction is one half and the minimum step is 2. Both",
        "shares stand at zero when the pass opens.",
        "",
        "  need     VS-A 14, VS-B 6, total 20",
        "  unallocated pool  20 less 0 equals 20",
        "  target   VS-A 0 + 20 times 14 over 20 equals 14",
        "           VS-B 0 + 20 times 6 over 20 equals 6",
        "  no cap binds, so nothing is freed and nothing is redistributed",
        "  aim      VS-A 14, VS-B 6",
        "  damped   VS-A 0 + one half of 14 equals 7",
        "           VS-B 0 + one half of 6 equals 3",
        "  rounded  VS-A 7, VS-B 3",
        "",
        "The second pass opens from 7 and 3, not from 14 and 6, and not from",
        "the unrounded values. Its needs are 7 and 3 and its unallocated pool",
        "is 10.",
        "",
        "Now suppose instead the damped move of VS-B had been three eighths of",
        "a minute. That rounds to zero, VS-B has not reached its aim, and so",
        "VS-B moves by the minimum step to 2 rather than standing still. Had",
        "its aim been 1, the step would have carried it to 1 and no further,",
        "because a step never carries a share past its aim.",
        "",
        "SECTION 5  an empty delimited document",
        "",
        "A delimited document with no rows is its header line and one line",
        "feed, like this three column example.",
        "",
        "```",
        "event_key,order_id,reason_code",
        "```",
        "",
        "A line delimited json document with no records is a file of zero",
        "bytes.",
    ])



def mint_corpus(seed, profile, root):
    """Write the whole working paper tree for one shift."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    inst = mint_instance(seed, profile)
    write_box_papers(inst, root)
    write_yard_papers(inst, root)
    write_move_papers(inst, root)
    write_equipment_papers(inst, root)
    write_vessel_papers(inst, root)
    write_history_papers(inst, root)
    write_policy_papers(inst, root)
    write_stage_specs(inst, root)
    write_schema_reference(inst, root)
    write_serialisation_contract(inst, root)
    write_program_contract(inst, root)
    write_navigation(inst, root)
    write_worked_examples(inst, root)
    write_workbook(inst, root / "quay_capacity_workbook.xlsx")
    write_memo(inst, root / "berth_operations_memo.pdf")
    write_directive(inst, root / "stowage_ordering_directive.docx")
    return inst

"""Readers for the terminal's working papers. Standard library only."""

ABSENT = "-"

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_S_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_R_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"


def _read_delimited(path, sep):
    text = Path(path).read_text(encoding="utf-8")
    lines = text.split("\n")
    while lines and lines[-1] == "":
        lines.pop()
    if not lines:
        return []
    header = lines[0].split(sep)
    out = []
    for line in lines[1:]:
        parts = line.split(sep)
        if len(parts) < len(header):
            parts = parts + [""] * (len(header) - len(parts))
        out.append(dict(zip(header, parts)))
    return out


def read_csv(path):
    return _read_delimited(path, ",")


def read_tsv(path):
    return _read_delimited(path, "\t")


def read_psv(path):
    return _read_delimited(path, "|")


def read_jsonl(path):
    out = []
    for line in Path(path).read_text(encoding="utf-8").split("\n"):
        if line.strip():
            out.append(json.loads(line))
    return out


def read_conf(path):
    """A flat sectioned configuration file: section name to key to value."""
    out = {}
    section = ""
    for raw in Path(path).read_text(encoding="utf-8").split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            out.setdefault(section, {})
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            out.setdefault(section, {})[key.strip()] = value.strip()
    return out


def read_scalar_yaml(path):
    """Top level scalar keys of a small yaml paper. Nested blocks are prose
    and are left alone."""
    out = {}
    for raw in Path(path).read_text(encoding="utf-8").split("\n"):
        if raw.startswith(" ") or raw.startswith("#") or ":" not in raw:
            continue
        key, _, value = raw.partition(":")
        value = value.strip()
        if value and not value.startswith(">"):
            out[key.strip()] = value
    return out


def read_ladder(path):
    """The admission ladder in the order the paper prints it."""
    out = []
    for raw in Path(path).read_text(encoding="utf-8").split("\n"):
        line = raw.strip()
        if line.startswith("rung "):
            parts = line.split()
            if len(parts) >= 3:
                out.append(parts[2])
    return out


def read_xml_blocks(path):
    root = ET.fromstring(Path(path).read_text(encoding="utf-8"))
    blocks = []
    for node in root.iter("block"):
        if node.get("in_force") == "yes":
            blocks.append({"block_id": node.get("id"), "zone": node.get("zone")})
    berths = []
    for node in root.iter("berth"):
        if node.get("reporting") == "yes":
            berths.append(node.get("id"))
    reference = ""
    for node in root.iter("reference"):
        reference = (node.text or "").strip()
    return blocks, berths, reference


# --------------------------------------------------------------------------
# spreadsheet
# --------------------------------------------------------------------------


def _column_of(ref):
    letters = ""
    for ch in ref:
        if ch.isalpha():
            letters += ch
        else:
            break
    col = 0
    for ch in letters:
        col = col * 26 + (ord(ch) - 64)
    return col


def read_xlsx(path):
    """Every sheet of a workbook, in workbook order, as a list of rows of
    strings."""
    with zipfile.ZipFile(str(path)) as zf:
        shared = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst.findall(_S_NS + "si"):
                text = ""
                for t in si.iter(_S_NS + "t"):
                    text += t.text or ""
                shared.append(text)
        book = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        target = {}
        for rel in rels:
            target[rel.get("Id")] = rel.get("Target")
        sheets = []
        for node in book.iter(_S_NS + "sheet"):
            name = node.get("name")
            rid = node.get(_R_NS + "id")
            part = target.get(rid, "")
            if not part.startswith("xl/"):
                part = "xl/" + part.lstrip("/")
            sheets.append((name, part))
        out = []
        for name, part in sheets:
            grid = []
            sheet = ET.fromstring(zf.read(part))
            for row in sheet.iter(_S_NS + "row"):
                cells = {}
                width = 0
                for c in row.findall(_S_NS + "c"):
                    ref = c.get("r") or ""
                    col = _column_of(ref)
                    v = c.find(_S_NS + "v")
                    value = "" if v is None else (v.text or "")
                    if c.get("t") == "s":
                        value = shared[int(value)] if value.isdigit() else ""
                    cells[col] = value
                    width = max(width, col)
                grid.append([cells.get(i + 1, "") for i in range(width)])
            out.append((name, grid))
    return out


# --------------------------------------------------------------------------
# portable document
# --------------------------------------------------------------------------


def read_pdf_lines(path):
    """The text lines of a document written with one show operator per line."""
    payload = Path(path).read_bytes()
    opener = ("stream" + "\n").encode("latin-1")
    closer = ("\n" + "endstream").encode("latin-1")
    out = []
    pos = 0
    while True:
        start = payload.find(opener, pos)
        if start < 0:
            break
        end = payload.find(closer, start)
        if end < 0:
            break
        body = payload[start + len(opener):end].decode("latin-1")
        for raw in body.split("\n"):
            raw = raw.strip()
            show_at = raw.find(") Tj")
            if show_at < 0:
                continue
            open_at = raw.find("(")
            close_at = show_at
            if open_at < 0 or close_at <= open_at:
                continue
            text = raw[open_at + 1:close_at]
            out.append(text.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\"))
        pos = end + 1
    return out


# --------------------------------------------------------------------------
# word processing document
# --------------------------------------------------------------------------


def read_docx(path):
    """Paragraphs and tables in document order. A paragraph is a string and a
    table is a list of rows of strings."""
    with zipfile.ZipFile(str(path)) as zf:
        document = ET.fromstring(zf.read("word/document.xml"))
    body = document.find(_W_NS + "body")
    out = []
    for node in list(body):
        if node.tag == _W_NS + "p":
            text = ""
            for t in node.iter(_W_NS + "t"):
                text += t.text or ""
            out.append(("p", text))
        elif node.tag == _W_NS + "tbl":
            rows = []
            for tr in node.findall(_W_NS + "tr"):
                cells = []
                for tc in tr.findall(_W_NS + "tc"):
                    text = ""
                    for t in tc.iter(_W_NS + "t"):
                        text += t.text or ""
                    cells.append(text)
                rows.append(cells)
            out.append(("table", rows))
    return out


# --------------------------------------------------------------------------
# small helpers the stages share
# --------------------------------------------------------------------------


def as_int(value, default=0):
    text = str(value).strip()
    if text in ("", ABSENT):
        return default
    try:
        return int(text)
    except ValueError:
        return default


def is_absent(value):
    return str(value).strip() in ("", ABSENT)


def yes(value):
    return str(value).strip().lower() == "yes"


def iso_length_of(text):
    digits = ""
    for ch in str(text):
        if ch.isdigit():
            digits += ch
        else:
            break
    return int(digits) if digits else 0


def round_half_up(value):
    """Exact rational to integer, half away from zero."""
    if value >= 0:
        return int((value * 2 + 1) // 2)
    return -int(((-value) * 2 + 1) // 2)


def ratio_text(num, den):
    """A ratio at exactly nine decimal places, half up away from zero."""
    if den == 0:
        return "0.000000000"
    scaled = round_half_up(Fraction(num, den) * 1000000000)
    sign = "-" if scaled < 0 else ""
    scaled = abs(scaled)
    whole, frac = divmod(scaled, 1000000000)
    return "%s%d.%09d" % (sign, whole, frac)

"""The fourteen stages of one operating shift, and the documents they publish."""


# --------------------------------------------------------------------------
# loading the working papers
# --------------------------------------------------------------------------


def load_shift(data_dir):
    root = Path(data_dir)
    data = {"root": root}
    blocks_in_force, reporting_berths, reference = read_xml_blocks(root / "yard_topology.xml")
    data["reference"] = reference
    data["blocks_in_force"] = blocks_in_force
    roster = read_conf(root / "berth_reporting_roster.conf")
    data["shift_id"] = roster.get("roster", {}).get("shift_id", "")
    listed = roster.get("roster", {}).get("reporting_berths", "")
    data["berths"] = [b.strip() for b in listed.split(",") if b.strip()] or reporting_berths
    bounds = read_scalar_yaml(root / "boundary_conventions.yaml")
    data["slot_length"] = as_int(bounds.get("slot_length_minutes"), 120)
    data["slot_count"] = as_int(bounds.get("slot_count"), 0)
    data["ladder"] = read_ladder(root / "move_admission_ladder.txt")

    data["box_master"] = read_csv(root / "box_master_register.csv")
    data["mass_returns"] = read_psv(root / "mass_declaration_returns.psv")
    data["stack_snapshot"] = read_csv(root / "stack_inventory_snapshot.csv")
    data["block_geometry"] = read_csv(root / "block_geometry_register.csv")
    data["slot_grid"] = read_csv(root / "slot_grid_calendar.csv")
    data["reservations"] = read_jsonl(root / "hold_reservation_notices.jsonl")
    data["orders"] = read_csv(root / "move_order_journal.csv")
    data["confirmations"] = read_jsonl(root / "crane_confirmation_feed.ndjson")
    data["dep_edges"] = read_jsonl(root / "move_dependency_declarations.jsonl")
    data["withdrawals"] = read_tsv(root / "withdrawn_order_journal.tsv")
    data["source_priority"] = read_csv(root / "source_priority_register.csv")
    data["equipment_register"] = read_csv(root / "handling_equipment_register.csv")
    data["vessel_register"] = read_csv(root / "vessel_call_register.csv")
    data["cutoffs"] = read_tsv(root / "cutoff_notice_board.tsv")
    data["stowage"] = read_psv(root / "stowage_obligation_list.psv")
    data["berth_windows"] = read_csv(root / "berth_window_register.csv")
    data["demand_returns"] = read_csv(root / "quay_demand_returns.csv")
    data["exceptions"] = read_csv(root / "operational_exception_notices.csv")

    data["workbook"] = read_xlsx(root / "quay_capacity_workbook.xlsx")
    data["memo"] = read_pdf_lines(root / "berth_operations_memo.pdf")
    data["directive"] = read_docx(root / "stowage_ordering_directive.docx")
    return data


def _live_sheet(data):
    """The live sheet is the one whose key cell carries this shift's
    reference. Sheet name and sheet position say nothing about which."""
    for name, grid in data["workbook"]:
        for row in grid:
            if len(row) >= 2 and row[0] == "shift_reference":
                if row[1] == data["reference"]:
                    return name, grid
            break
    raise ValueError("no workbook sheet carries the shift reference")


def prepare(data):
    name, grid = _live_sheet(data)
    data["live_sheet_name"] = name
    controls = {"teu_factor": {}, "plug_ceiling": {}, "block_class_ceiling": {},
                "vessel_slot_ceiling": {}}
    for row in grid:
        if not row:
            continue
        tag = row[0]
        if tag == "ration_damping_fraction":
            controls["damping"] = Fraction(as_int(row[1]), as_int(row[2]))
        elif tag == "decitonne_kilograms":
            controls["decitonne_kilograms"] = as_int(row[1])
        elif tag == "centner_kilograms":
            controls["centner_kilograms"] = as_int(row[1])
        elif tag == "base_move_charge_cents":
            controls["base_move_cents"] = as_int(row[1])
        elif tag == "teu_factor":
            controls["teu_factor"][as_int(row[1])] = as_int(row[2])
        elif tag == "plug_ceiling":
            controls["plug_ceiling"][row[1]] = as_int(row[2])
        elif tag == "block_class_ceiling":
            controls["block_class_ceiling"][(row[1], row[2], row[3])] = as_int(row[4])
        elif tag == "vessel_slot_ceiling":
            controls["vessel_slot_ceiling"][(row[1], row[2])] = as_int(row[3])

    ladder_rungs = []
    gang = {}
    for line in data["memo"]:
        text = line.strip()
        if text.startswith("ration_pass_budget"):
            controls["pass_budget"] = as_int(text.split()[-1])
        elif text.startswith("ration_minimum_step"):
            controls["minimum_step"] = as_int(text.split()[1])
        elif text.startswith("dependency_protection_depth"):
            controls["protection_depth"] = as_int(text.split()[-1])
        parts = text.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            ladder_rungs.append((int(parts[0]), int(parts[1])))
        if len(parts) == 4 and parts[0].startswith("bt_") and parts[2].startswith("GNG-"):
            key = (parts[0], parts[1])
            gang[key] = gang.get(key, 0) + int(parts[3])
    controls["surcharge_ladder"] = sorted(ladder_rungs)
    controls["gang_minutes"] = gang

    keys = []
    class_rank = {}
    seen_tables = 0
    for kind, payload in data["directive"]:
        if kind != "table":
            continue
        seen_tables += 1
        header = payload[0]
        if header[:2] == ["key_position", "key_name"]:
            for row in payload[1:]:
                keys.append((int(row[0]), row[1]))
        elif header[:2] == ["box_class", "class_rank"]:
            for row in payload[1:]:
                class_rank[row[0]] = int(row[1])
    controls["stowage_keys"] = [k for _, k in sorted(keys)]
    controls["class_rank"] = class_rank
    data["controls"] = controls


# --------------------------------------------------------------------------
# helpers shared by the stages
# --------------------------------------------------------------------------


def _mine(rows, shift_id):
    return [r for r in rows if r.get("shift_id") == shift_id]


def _applicable(rows, key_fields, shift_id, aside_fields):
    """The applicable revision of every subject in a register."""
    best = {}
    for r in _mine(rows, shift_id):
        if any(yes(r.get(f)) for f in aside_fields):
            continue
        key = tuple(r.get(f) for f in key_fields)
        seq = as_int(r.get("revision_seq"))
        if key not in best or seq > as_int(best[key].get("revision_seq")):
            best[key] = r
    return best


def slot_of(minute, slot_length, slot_count):
    """A minute on the shift grid. A minute exactly on a boundary belongs to
    the slot that is closing."""
    if minute < 0:
        return 0
    if minute > slot_length * slot_count:
        return 0
    if minute == 0:
        return 1
    ordinal = (minute + slot_length - 1) // slot_length
    return ordinal if 1 <= ordinal <= slot_count else 0


def slot_code(ordinal):
    return "SL%02d" % ordinal


# --------------------------------------------------------------------------
# Y01  canonical events
# --------------------------------------------------------------------------


def stage_y01(data):
    shift = data["shift_id"]
    withdrawn = set()
    for r in data["withdrawals"]:
        if r.get("shift_id") == shift and r.get("state") == "withdrawn":
            withdrawn.add(r.get("order_id"))
    data["withdrawn_orders"] = withdrawn

    events = []
    for row in data["orders"]:
        oid = row["order_id"]
        if oid in withdrawn:
            continue
        raised = as_int(row["raised_min"])
        ordinal = slot_of(raised, data["slot_length"], data["slot_count"])
        events.append({
            "order_id": oid,
            "box_id": row["box_id"],
            "source_system": row["source_system"],
            "event_seq": as_int(row["event_seq"]),
            "raised_min": raised,
            "slot_ordinal": ordinal,
            "slot_code": slot_code(ordinal) if ordinal else ABSENT,
            "to_block": row["to_block"],
            "to_row": as_int(row["to_row"]),
            "to_tier": as_int(row["to_tier"]),
            "priority_band": as_int(row["priority_band"]),
            "cluster_tag": row["cluster_tag"],
        })
    data["events"] = events


# --------------------------------------------------------------------------
# Y02  unit normalisation
# --------------------------------------------------------------------------


def _mass_reading(rec, factor):
    """RULE Y02.4. An absent mass is not a declared zero."""
    if rec is None or is_absent(rec.get("mass_value")):
        return 0, "not_declared"
    unit = rec.get("mass_unit", "kg")
    return as_int(rec["mass_value"]) * factor.get(unit, 1), "declared"


def stage_y02(data):
    shift = data["shift_id"]
    master = _applicable(data["box_master"], ["box_id"], shift, ["retired"])
    controls = data["controls"]
    factor = {"kg": 1,
              "dt": controls["decitonne_kilograms"],
              "ct": controls["centner_kilograms"]}

    declared = {}
    for r in data["mass_returns"]:
        if r.get("state") != "filed":
            continue
        box = r["box_id"]
        seq = as_int(r.get("declaration_seq"))
        if box not in declared or seq > as_int(declared[box].get("declaration_seq")):
            declared[box] = r

    boxes = {}
    for (box_id,), row in sorted(master.items()):
        iso = iso_length_of(row["iso_length"])
        mass_kg, mass_state = _mass_reading(declared.get(box_id), factor)
        boxes[box_id] = {
            "box_id": box_id,
            "iso_length": iso,
            "teu_factor": controls["teu_factor"].get(iso, 0),
            "box_class": row["box_class"],
            "vessel_id": row["vessel_id"],
            "mass_kg": mass_kg,
            "mass_state": mass_state,
        }
    data["boxes"] = boxes


# --------------------------------------------------------------------------
# Y03  vessel obligation state
# --------------------------------------------------------------------------


def stage_y03(data):
    shift = data["shift_id"]
    live = _applicable(data["vessel_register"], ["vessel_id"], shift, ["withdrawn"])
    vessels = {}
    for (vid,), row in sorted(live.items()):
        vessels[vid] = {
            "vessel_id": vid,
            "voyage": row["voyage"],
            "berth_id": row["berth_id"],
            "service_group": row["service_group"],
            "destination": row["destination"],
            "voyage_sequence": as_int(row["voyage_sequence"]),
            "applicable_revision": as_int(row["revision_seq"]),
        }
    data["vessels"] = vessels
    for box in data["boxes"].values():
        vessel = vessels.get(box["vessel_id"])
        box["service_group"] = vessel["service_group"] if vessel else ABSENT
        box["destination"] = vessel["destination"] if vessel else ABSENT


# --------------------------------------------------------------------------
# Y04  the opening yard
# --------------------------------------------------------------------------


def stage_y04(data):
    shift = data["shift_id"]
    in_force = [b["block_id"] for b in data["blocks_in_force"]]
    geometry = _applicable(data["block_geometry"], ["block_id"], shift,
                           ["retired", "future"])
    blocks = {}
    for block_id in in_force:
        row = geometry.get((block_id,))
        rows_n = as_int(row["rows"]) if row else 0
        tiers = as_int(row["tiers_max"]) if row else 0
        blocks[block_id] = {
            "block_id": block_id,
            "zone": row["zone"] if row else ABSENT,
            "rows": rows_n,
            "tiers_max": tiers,
            "slot_capacity": rows_n * tiers,
            "applicable_revision": as_int(row["revision_seq"]) if row else 0,
        }
    data["blocks"] = blocks

    sealed = {}
    in_service = {}
    for r in data["slot_grid"]:
        key = (r["block_id"], r["slot_code"])
        sealed[key] = yes(r.get("sealed"))
        in_service[key] = yes(r.get("in_service"))
    data["sealed"] = sealed
    data["in_service"] = in_service

    placed = {}
    opening = {}
    for r in data["stack_snapshot"]:
        if r.get("stack_state") != "stacked":
            continue
        block_id = r["block_id"]
        if block_id not in blocks:
            continue
        box_id = r["box_id"]
        if box_id not in data["boxes"]:
            continue
        placed[box_id] = (block_id, as_int(r["row_no"]), as_int(r["tier_no"]))
        opening[block_id] = opening.get(block_id, 0) + 1
    data["placement"] = placed
    data["opening_counts"] = opening


# --------------------------------------------------------------------------
# Y05  canonical event order
# --------------------------------------------------------------------------


def stage_y05(data):
    shift = data["shift_id"]
    ranks = _applicable(data["source_priority"], ["source_system"], shift, ["retired"])
    priority = {}
    for (src,), row in ranks.items():
        priority[src] = as_int(row["priority_rank"])
    data["source_rank"] = priority

    def key(ev):
        return (ev["slot_ordinal"] if ev["slot_ordinal"] else 10 ** 6,
                priority.get(ev["source_system"], 10 ** 6),
                ev["event_seq"], ev["box_id"], ev["order_id"])

    ordered = sorted(data["events"], key=key)
    for i, ev in enumerate(ordered, start=1):
        ev["event_key"] = i
    data["ordered_events"] = ordered
    data["event_by_order"] = dict((ev["order_id"], ev) for ev in ordered)


# --------------------------------------------------------------------------
# Y06  the dependency graph and its cycles
# --------------------------------------------------------------------------


def _components(nodes, edges):
    """Tarjan strongly connected components, iterative, deterministic."""
    index = {}
    low = {}
    on_stack = {}
    stack = []
    result = []
    counter = [0]
    adjacency = {}
    for e in edges:
        adjacency.setdefault(e["before"], []).append(e["after"])
    for node in nodes:
        adjacency.setdefault(node, [])
        adjacency[node] = sorted(adjacency[node])

    for start in nodes:
        if start in index:
            continue
        work = [(start, 0)]
        while work:
            node, pointer = work[-1]
            if pointer == 0:
                index[node] = low[node] = counter[0]
                counter[0] += 1
                stack.append(node)
                on_stack[node] = True
            recursed = False
            neighbours = adjacency[node]
            while pointer < len(neighbours):
                nxt = neighbours[pointer]
                pointer += 1
                if nxt not in index:
                    work[-1] = (node, pointer)
                    work.append((nxt, 0))
                    recursed = True
                    break
                if on_stack.get(nxt):
                    low[node] = min(low[node], index[nxt])
            if recursed:
                continue
            work[-1] = (node, pointer)
            if pointer >= len(neighbours):
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])
                if low[node] == index[node]:
                    group = []
                    while True:
                        member = stack.pop()
                        on_stack[member] = False
                        group.append(member)
                        if member == node:
                            break
                    result.append(sorted(group))
    return result


def stage_y06(data):
    known = set(ev["order_id"] for ev in data["ordered_events"])
    edges = []
    for r in data["dep_edges"]:
        if r.get("state") != "declared":
            continue
        before, after = r["before_order"], r["after_order"]
        if before not in known or after not in known or before == after:
            continue
        edges.append({"edge_id": r["edge_id"], "before": before, "after": after,
                      "weight": as_int(r["edge_weight"])})
    edges.sort(key=lambda e: e["edge_id"])
    nodes = sorted(known)
    depth = data["controls"]["protection_depth"]

    removed = []
    report = []
    live = list(edges)
    while True:
        groups = [g for g in _components(nodes, live) if len(g) > 1]
        if not groups:
            break
        groups.sort(key=lambda g: (g[0], len(g)))
        group = groups[0]
        member = set(group)
        inside = [e for e in live if e["before"] in member and e["after"] in member]
        protected = set()
        for e in sorted(inside, key=lambda e: (-e["weight"], e["edge_id"]))[:depth]:
            protected.add(e["edge_id"])
        candidates = [e for e in inside if e["edge_id"] not in protected] or inside
        drop = sorted(candidates, key=lambda e: (e["weight"], e["edge_id"]))[0]
        live = [e for e in live if e["edge_id"] != drop["edge_id"]]
        removed.append(drop)
        report.append({
            "component_key": group[0],
            "member_count": len(group),
            "members": group,
            "edge_removed": drop["edge_id"],
            "edge_weight": drop["weight"],
            "before_order": drop["before"],
            "after_order": drop["after"],
            "protected_count": len(protected),
        })
    data["dep_edges_live"] = live
    data["cycle_report"] = report
    data["edges_removed"] = removed

    # Dependency order: repeatedly take the admitted event with the lowest
    # event key whose predecessors are all placed.
    keys = dict((ev["order_id"], ev["event_key"]) for ev in data["ordered_events"])
    incoming = dict((n, 0) for n in nodes)
    outgoing = dict((n, []) for n in nodes)
    for e in live:
        incoming[e["after"]] += 1
        outgoing[e["before"]].append(e["after"])
    ready = sorted([n for n in nodes if incoming[n] == 0], key=lambda n: keys[n])
    order = []
    while ready:
        node = ready.pop(0)
        order.append(node)
        for nxt in sorted(outgoing[node], key=lambda n: keys[n]):
            incoming[nxt] -= 1
            if incoming[nxt] == 0:
                ready.append(nxt)
                ready.sort(key=lambda n: keys[n])
    data["dependency_order"] = order


# --------------------------------------------------------------------------
# Y07  admission, with reserved capacity settled before free capacity
# --------------------------------------------------------------------------


def _waivers(data):
    shift = data["shift_id"]
    out = {}
    for r in data["exceptions"]:
        if r.get("shift_id") != shift or yes(r.get("withdrawn")):
            continue
        out.setdefault(r["target_id"], set()).add(r["exception_kind"])
    return out


def _withheld_against(credits, block_id, ordinal, group):
    """RULE Y07.3. Reserved capacity is settled before free capacity is
    counted, and a reservation of the order's own service group withholds
    nothing from it."""
    total = 0
    for c in credits:
        if c["block_id"] != block_id or c["remaining"] <= 0:
            continue
        if not (c["first"] <= ordinal <= c["last"]):
            continue
        if c["service_group"] == group:
            continue
        total += c["remaining"]
    return total


def stage_y07(data):
    shift = data["shift_id"]
    blocks = data["blocks"]
    waiver = _waivers(data)
    data["waivers"] = waiver

    # Reservation credits. An absent quantity withholds the whole opening free
    # capacity of the block; a quantity larger than that withholds the free
    # capacity and no more.
    credits = []
    for r in data["reservations"]:
        if r.get("shift_id") != shift or r.get("state") != "held":
            continue
        block_id = r["block_id"]
        block = blocks.get(block_id)
        if block is None:
            continue
        opening_free = max(0, block["slot_capacity"] - data["opening_counts"].get(block_id, 0))
        if is_absent(r.get("quantity")):
            asked = opening_free
        else:
            asked = as_int(r["quantity"])
        withheld = min(asked, opening_free)
        credits.append({
            "reservation_id": r["reservation_id"],
            "block_id": block_id,
            "service_group": r["service_group"],
            "first": as_int(r["first_slot"][2:]),
            "last": as_int(r["last_slot"][2:]),
            "asked": asked,
            "withheld": withheld,
            "remaining": withheld,
            "consumed": 0,
            "unmet": max(0, asked - withheld),
        })
    credits.sort(key=lambda c: c["reservation_id"])
    data["credits"] = credits

    occupied = {}
    for block_id, count in data["opening_counts"].items():
        occupied[block_id] = count
    where = dict(data["placement"])

    rung_order = data["ladder"]
    lifts = {"LR_SEALED_ZONE": "zone_waiver",
             "LR_TIER_BEYOND_MAX": "tier_waiver",
             "LR_RESERVED_BOUND": "reservation_release"}
    canonical_taken = set()
    decisions = []
    history = []
    accepted = []

    for ev in data["ordered_events"]:
        block_id = ev["to_block"]
        block = blocks.get(block_id)
        granted = waiver.get(ev["order_id"], set())
        reason = ""
        for rung in rung_order:
            if rung in lifts and lifts[rung] in granted:
                continue
            if rung == "LR_UNKNOWN_BOX":
                if ev["box_id"] not in data["boxes"]:
                    reason = rung
                    break
            elif rung == "LR_SEALED_ZONE":
                if ev["slot_ordinal"] and data["sealed"].get((block_id, ev["slot_code"])):
                    reason = rung
                    break
            elif rung == "LR_STALE_SLOT":
                if not ev["slot_ordinal"]:
                    reason = rung
                    break
            elif rung == "LR_TIER_BEYOND_MAX":
                if block is None or block["slot_capacity"] == 0 or ev["to_tier"] > block["tiers_max"]:
                    reason = rung
                    break
            elif rung == "LR_RESERVED_BOUND":
                # A waiver can lift the tier rung off an order whose block the
                # topology does not carry. Such a block holds no capacity at
                # all, so this rung catches the order.
                if block is None:
                    reason = rung
                    break
                free_now = block["slot_capacity"] - occupied.get(block_id, 0)
                group = data["boxes"].get(ev["box_id"], {}).get("service_group", ABSENT)
                withheld_now = _withheld_against(credits, block_id,
                                                 ev["slot_ordinal"], group)
                if free_now - withheld_now <= 0:
                    reason = rung
                    break
            elif rung == "LR_DUPLICATE_ORDER":
                if ev["cluster_tag"] in canonical_taken:
                    reason = rung
                    break
        decision = {
            "event_key": ev["event_key"],
            "order_id": ev["order_id"],
            "box_id": ev["box_id"],
            "slot_code": ev["slot_code"],
            "to_block": block_id,
            "to_row": ev["to_row"],
            "to_tier": ev["to_tier"],
            "outcome": "set_aside" if reason else "admitted",
            "reason_code": reason if reason else ABSENT,
            "slot_ordinal": ev["slot_ordinal"],
            "consumed_reservation": ABSENT,
        }
        decisions.append(decision)
        if reason:
            continue
        canonical_taken.add(ev["cluster_tag"])
        group = data["boxes"][ev["box_id"]]["service_group"]
        for c in credits:
            if (c["block_id"] == block_id and c["service_group"] == group
                    and c["remaining"] > 0
                    and c["first"] <= ev["slot_ordinal"] <= c["last"]):
                c["remaining"] -= 1
                c["consumed"] += 1
                decision["consumed_reservation"] = c["reservation_id"]
                break
        prior = where.get(ev["box_id"])
        if prior is not None:
            occupied[prior[0]] = occupied.get(prior[0], 0) - 1
        occupied[block_id] = occupied.get(block_id, 0) + 1
        where[ev["box_id"]] = (block_id, ev["to_row"], ev["to_tier"])
        history.append({
            "box_id": ev["box_id"],
            "event_key": ev["event_key"],
            "from_block": prior[0] if prior else ABSENT,
            "from_row": prior[1] if prior else ABSENT,
            "from_tier": prior[2] if prior else ABSENT,
            "to_block": block_id,
            "to_row": ev["to_row"],
            "to_tier": ev["to_tier"],
            "was_stacked": "yes" if prior else "no",
        })
        accepted.append(decision)
    data["decisions"] = decisions
    data["accepted"] = accepted
    data["history"] = history
    data["closing_where"] = where
    data["closing_counts"] = occupied


# --------------------------------------------------------------------------
# Y08  the yard state through the shift
# --------------------------------------------------------------------------


def stage_y08(data):
    slots = [slot_code(i) for i in range(1, data["slot_count"] + 1)]
    data["slot_codes"] = slots
    occupied = dict((b, data["opening_counts"].get(b, 0)) for b in data["blocks"])
    where = dict(data["placement"])
    credit_left = dict((c["reservation_id"], c["withheld"]) for c in data["credits"])
    accepted = sorted(data["accepted"], key=lambda d: d["event_key"])
    pointer = 0
    per_slot = {}
    credit_slot = {}
    for ordinal in range(1, data["slot_count"] + 1):
        while pointer < len(accepted) and accepted[pointer]["slot_ordinal"] <= ordinal:
            d = accepted[pointer]
            prior = where.get(d["box_id"])
            if prior is not None:
                occupied[prior[0]] = occupied.get(prior[0], 0) - 1
            occupied[d["to_block"]] = occupied.get(d["to_block"], 0) + 1
            where[d["box_id"]] = (d["to_block"], d["to_row"], d["to_tier"])
            if d["consumed_reservation"] != ABSENT:
                credit_left[d["consumed_reservation"]] -= 1
            pointer += 1
        per_slot[slot_code(ordinal)] = dict(occupied)
        credit_slot[slot_code(ordinal)] = dict(credit_left)
    data["occupancy_by_slot"] = per_slot
    data["credit_by_slot"] = credit_slot
    data["closing_occupied"] = occupied


# --------------------------------------------------------------------------
# Y09  the planned stream against the physical stream
# --------------------------------------------------------------------------


def _movement_state_for(planned_outcome, confirm_state):
    """RULE Y09.2 and Y09.3. A landed confirmation never overturns the
    ladder: an order the ladder set aside stays set aside and is recorded as
    contradicted."""
    if planned_outcome == "admitted":
        if confirm_state is None:
            return "unconfirmed"
        return "confirmed" if confirm_state == "landed" else "aborted"
    return "contradicted" if confirm_state == "landed" else "set_aside"


def stage_y09(data):
    by_order = {}
    loose = []
    for c in data["confirmations"]:
        oid = str(c.get("order_id") or "")
        if not oid:
            loose.append(c)
            continue
        seen = by_order.get(oid)
        if seen is None or as_int(c.get("confirmed_min")) < as_int(seen.get("confirmed_min")):
            by_order[oid] = c
    records = []
    for d in sorted(data["decisions"], key=lambda x: x["event_key"]):
        c = by_order.get(d["order_id"])
        state = _movement_state_for(d["outcome"],
                                    None if c is None else c.get("confirm_state"))
        records.append({
            "event_key": d["event_key"],
            "order_id": d["order_id"],
            "box_id": d["box_id"],
            "planned_outcome": d["outcome"],
            "confirm_id": (c or {}).get("confirm_id", ABSENT),
            "confirmed_min": as_int((c or {}).get("confirmed_min"), 0) if c else 0,
            "movement_state": state,
        })
    data["movement"] = records
    data["loose_confirmations"] = sorted(loose, key=lambda c: str(c.get("confirm_id")))
    data["confirm_by_order"] = by_order


# --------------------------------------------------------------------------
# Y10  rehandles and the equipment that carried them
# --------------------------------------------------------------------------


def stage_y10(data):
    ladder = data["controls"]["surcharge_ladder"]
    base_cents = data["controls"]["base_move_cents"]

    def surcharge(depth):
        chosen = 0
        for tier, cents in ladder:
            if depth >= tier:
                chosen = cents
        return chosen

    per_box = {}
    for h in data["history"]:
        rec = per_box.setdefault(h["box_id"], {
            "box_id": h["box_id"], "moves": 0, "rehandles": 0,
            "surcharge_cents": 0, "charge_cents": 0, "depths": []})
        rec["moves"] += 1
        rec["charge_cents"] += base_cents
        if h["was_stacked"] == "yes":
            rec["rehandles"] += 1
            depth = as_int(h["from_tier"])
            rec["depths"].append(depth)
            add = surcharge(depth)
            rec["surcharge_cents"] += add
            rec["charge_cents"] += add
    data["rehandles"] = per_box

    state = _applicable(data["equipment_register"], ["equipment_id"],
                        data["shift_id"], ["retired"])
    units = {}
    for (eid,), row in sorted(state.items()):
        units[eid] = {
            "equipment_id": eid,
            "equipment_class": row["equipment_class"],
            "allowance": as_int(row["move_limit"]),
            "base_minutes": as_int(row["base_minutes"]),
            "used": 0,
            "minutes": 0,
        }
    data["equipment"] = units

    exceptions = []
    for r in data["movement"]:
        if r["movement_state"] != "confirmed":
            continue
        c = data["confirm_by_order"].get(r["order_id"])
        eid = (c or {}).get("equipment_id")
        unit = units.get(eid)
        if unit is None:
            exceptions.append({"event_key": r["event_key"], "order_id": r["order_id"],
                               "equipment_id": eid or ABSENT,
                               "reason_code": "EQ_UNKNOWN_UNIT"})
            continue
        if unit["used"] + 1 > unit["allowance"]:
            exceptions.append({"event_key": r["event_key"], "order_id": r["order_id"],
                               "equipment_id": eid, "reason_code": "EQ_BEYOND_ALLOWANCE"})
            continue
        unit["used"] += 1
        unit["minutes"] += unit["base_minutes"]
    data["equipment_exceptions"] = exceptions


# --------------------------------------------------------------------------
# Y11  what each block had, and what was withheld
# --------------------------------------------------------------------------


def stage_y11(data):
    rows = []
    for block_id in sorted(data["blocks"]):
        block = data["blocks"][block_id]
        for code in data["slot_codes"]:
            capacity = block["slot_capacity"]
            occupied = data["occupancy_by_slot"][code].get(block_id, 0)
            sealed = data["sealed"].get((block_id, code), False)
            served = data["in_service"].get((block_id, code), capacity > 0)
            if sealed or not served or capacity == 0:
                unavailable = capacity
                reserved = 0
                available = 0
            else:
                unavailable = 0
                free = max(0, capacity - occupied)
                reserved = 0
                for c in data["credits"]:
                    if c["block_id"] != block_id:
                        continue
                    if not (c["first"] <= as_int(code[2:]) <= c["last"]):
                        continue
                    reserved += data["credit_by_slot"][code].get(c["reservation_id"], 0)
                reserved = min(reserved, free)
                available = max(0, free - reserved)
            rows.append({
                "block_id": block_id, "slot_code": code, "slot_capacity": capacity,
                "occupied": occupied, "reserved": reserved,
                "unavailable": unavailable, "available": available,
            })
    data["capacity_rows"] = rows


# --------------------------------------------------------------------------
# Y12  the cutoff joined to the yard state
# --------------------------------------------------------------------------


def stage_y12(data):
    shift = data["shift_id"]
    in_force = {}
    for r in data["cutoffs"]:
        if r.get("shift_id") != shift or yes(r.get("superseded")):
            continue
        vid = r["vessel_id"]
        seq = as_int(r["notice_seq"])
        if vid not in in_force or seq > as_int(in_force[vid]["notice_seq"]):
            in_force[vid] = r
    data["cutoff_in_force"] = in_force

    obligation = {}
    for r in data["stowage"]:
        obligation[(r["vessel_id"], r["box_id"])] = r

    ready = {}
    last_order = {}
    for d in sorted(data["accepted"], key=lambda x: x["event_key"]):
        ev = data["event_by_order"][d["order_id"]]
        ready[d["box_id"]] = ev["raised_min"]
        last_order[d["box_id"]] = d["order_id"]
    data["ready_min"] = ready

    rows = []
    for box_id in sorted(data["boxes"]):
        box = data["boxes"][box_id]
        vid = box["vessel_id"]
        vessel = data["vessels"].get(vid)
        ob = obligation.get((vid, box_id))
        reason = "EL_OK"
        if vessel is None:
            reason = "EL_NO_VESSEL"
        elif ob is None:
            reason = "EL_NO_OBLIGATION"
        elif yes(ob.get("hold_flag")):
            reason = "EL_HELD"
        elif box_id not in data["closing_where"]:
            reason = "EL_OFF_YARD"
        else:
            notice = in_force.get(vid)
            if notice is None:
                reason = "EL_NO_CUTOFF"
            else:
                waived = "cutoff_waiver" in data["waivers"].get(last_order.get(box_id, ""), set())
                if not waived and ready.get(box_id, 0) > as_int(notice["cutoff_min"]):
                    reason = "EL_AFTER_CUTOFF"
        rows.append({
            "box_id": box_id, "vessel_id": vid,
            "eligible": "yes" if reason == "EL_OK" else "no",
            "reason_code": reason,
            "ready_min": ready.get(box_id, 0),
            "bay_no": as_int((ob or {}).get("bay_no"), 0),
            "stow_sequence": as_int((ob or {}).get("stow_sequence"), 0),
        })
    data["eligibility"] = rows
    data["eligible_by_vessel"] = {}
    for r in rows:
        if r["eligible"] == "yes":
            data["eligible_by_vessel"].setdefault(r["vessel_id"], []).append(r)


# --------------------------------------------------------------------------
# Y13  the quay ration, and the load it settles
# --------------------------------------------------------------------------


def _demand_applicable(data):
    """The applicable demand return for a vessel and slot: the highest
    revision whose return_state is filed."""
    best = {}
    for r in data["demand_returns"]:
        if r.get("return_state") != "filed":
            continue
        key = (r["vessel_id"], r["slot_code"])
        seq = as_int(r["revision_seq"])
        if key not in best or seq > as_int(best[key]["revision_seq"]):
            best[key] = r
    return best


def _window_applicable(data):
    best = {}
    for r in data["berth_windows"]:
        if yes(r.get("draft")):
            continue
        key = (r["berth_id"], r["slot_code"])
        seq = as_int(r["revision_seq"])
        if key not in best or seq > as_int(best[key]["revision_seq"]):
            best[key] = r
    return best


def _ration_budget(controls):
    """RULE Y13.6. The budget is a count of passes, not a convergence test."""
    return controls["pass_budget"]


def _ration_quantise(value):
    """RULE Y13.5 g. The share is rounded at the end of every pass, so the
    next pass opens from whole crane minutes."""
    return round_half_up(value)


def _ration_cell_key(data, vessel_id):
    """RULE Y13.5 d. What a cap frees is redistributed inside the cross
    classification of berth and service group. Inside one pairing the berth
    is fixed, so the cell is the service group."""
    return data["vessels"][vessel_id]["service_group"]


def _ration_pairing(data, code, berth, members, pool):
    """One damped, capped, redistributed iterate under a hard pass budget."""
    controls = data["controls"]
    damping = controls["damping"]
    budget = _ration_budget(controls)
    step = controls["minimum_step"]
    ceiling = {}
    demand = {}
    group = {}
    for m in members:
        ceiling[m] = Fraction(controls["vessel_slot_ceiling"].get((m, code), 0))
        demand[m] = Fraction(data["demand"][(m, code)])
        group[m] = _ration_cell_key(data, m)
    share = dict((m, 0) for m in members)
    passes = []
    for pass_no in range(1, budget + 1):
        need = dict((m, max(Fraction(0), demand[m] - Fraction(share[m]))) for m in members)
        total_need = sum(need.values())
        unallocated = Fraction(pool) - sum(Fraction(share[m]) for m in members)
        if total_need == 0 or unallocated <= 0:
            break
        target = {}
        for m in members:
            target[m] = Fraction(share[m]) + unallocated * need[m] / total_need
        capped = dict((m, min(target[m], ceiling[m])) for m in members)
        received = dict((m, Fraction(0)) for m in members)
        unplaced = Fraction(0)
        cells = {}
        for m in members:
            cells.setdefault(group[m], []).append(m)
        for cell_key in sorted(cells):
            cell = cells[cell_key]
            freed = sum(target[m] - capped[m] for m in cell)
            if freed <= 0:
                continue
            open_members = [m for m in cell if capped[m] < ceiling[m]]
            weight = sum(need[m] for m in open_members)
            if not open_members or weight == 0:
                unplaced += freed
                continue
            for m in open_members:
                received[m] = freed * need[m] / weight
        aim = {}
        for m in members:
            aim[m] = min(capped[m] + received[m], ceiling[m])
        for m in sorted(members):
            moved = Fraction(share[m]) + damping * (aim[m] - Fraction(share[m]))
            landed = _ration_quantise(moved)
            goal = _ration_quantise(aim[m])
            if landed == share[m] and share[m] != goal:
                direction = 1 if goal > share[m] else -1
                landed = share[m] + direction * step
                if direction > 0:
                    landed = min(landed, goal)
                else:
                    landed = max(landed, goal)
            share[m] = landed
        passes.append({
            "slot_code": code,
            "berth_id": berth,
            "pass_no": pass_no,
            "pool_minutes": pool,
            "unplaced_minutes": round_half_up(unplaced),
            "shares": [{"vessel_id": m,
                        "share_minutes": round_half_up(Fraction(share[m]))}
                       for m in sorted(members)],
        })
    return dict((m, round_half_up(Fraction(share[m]))) for m in members), passes


def stage_y13(data):
    demand_rows = _demand_applicable(data)
    windows = _window_applicable(data)
    gang = data["controls"]["gang_minutes"]
    data["demand"] = {}
    for (vid, code), row in demand_rows.items():
        data["demand"][(vid, code)] = as_int(row["declared_minutes"])

    trace = []
    total_share = dict((v, 0) for v in data["vessels"])
    pairings = []
    for code in data["slot_codes"]:
        for berth in sorted(data["berths"]):
            members = sorted(v for v, rec in data["vessels"].items()
                             if rec["berth_id"] == berth and (v, code) in data["demand"])
            window = windows.get((berth, code))
            declared = as_int(window["crane_minutes"]) if window else 0
            crewed = gang.get((berth, code), 0)
            pool = min(declared, crewed)
            share, passes = _ration_pairing(data, code, berth, members, pool)
            trace.extend(passes)
            for m in members:
                total_share[m] += share[m]
            pairings.append({
                "slot_code": code, "berth_id": berth, "pool_minutes": pool,
                "declared_minutes": declared, "crewed_minutes": crewed,
                "vessel_count": len(members),
                "rationed_minutes": sum(share.values()),
            })
    data["ration_trace"] = trace
    data["pairings"] = pairings
    data["vessel_share"] = total_share

    quay = [u for u in data["equipment"].values() if u["equipment_class"] == "quay_crane"]
    quay.sort(key=lambda u: u["equipment_id"])
    per_teu = quay[0]["base_minutes"] if quay else 0
    data["minutes_per_teu"] = per_teu

    rank = data["controls"]["class_rank"]
    loaded, deferred, ledger = [], [], []
    for vid in sorted(data["vessels"]):
        members = data["eligible_by_vessel"].get(vid, [])
        rows = []
        for r in members:
            box = data["boxes"][r["box_id"]]
            rows.append({
                "box_id": r["box_id"],
                "class_rank": rank.get(box["box_class"], 0),
                "stow_sequence": r["stow_sequence"],
                "bay_no": r["bay_no"],
                "load_minutes": box["teu_factor"] * per_teu,
                "teu_factor": box["teu_factor"],
                "mass_kg": box["mass_kg"],
            })
        # The ordering keys and the order they are read in come from the
        # directive, not from this module: the directive names them by key
        # position and other shifts print them in another order.
        stow_keys = data["controls"]["stowage_keys"]
        rows.sort(key=lambda x: tuple(x[k] for k in stow_keys))
        budget = total_share[vid]
        spent = 0
        stopped = False
        for position, row in enumerate(rows, start=1):
            if stopped or spent + row["load_minutes"] > budget:
                stopped = True
                deferred.append({"vessel_id": vid, "box_id": row["box_id"],
                                 "load_minutes": row["load_minutes"]})
                continue
            spent += row["load_minutes"]
            loaded.append({"vessel_id": vid, "box_id": row["box_id"],
                           "load_position": position, "load_minutes": row["load_minutes"]})
        ledger.append({
            "vessel_id": vid,
            "share_minutes": budget,
            "eligible_count": len(rows),
            "loaded_count": sum(1 for x in loaded if x["vessel_id"] == vid),
            "deferred_count": sum(1 for x in deferred if x["vessel_id"] == vid),
            "loaded_minutes": spent,
            "unused_minutes": budget - spent,
        })
    data["loaded"] = loaded
    data["deferred"] = deferred
    data["load_ledger"] = ledger

    last_rung = data["controls"]["surcharge_ladder"][-1][1] if data["controls"]["surcharge_ladder"] else 0
    republished = []
    for d in sorted(deferred, key=lambda x: (x["vessel_id"], x["box_id"])):
        rec = data["rehandles"].get(d["box_id"])
        assessed = rec["charge_cents"] if rec else 0
        republished.append({
            "box_id": d["box_id"], "vessel_id": d["vessel_id"],
            "load_minutes": d["load_minutes"],
            "assessed_cents": assessed,
            "published_cents": assessed + last_rung,
        })
    data["republished"] = republished


# --------------------------------------------------------------------------
# Y14  the terminal accounts
# --------------------------------------------------------------------------


def stage_y14(data):
    counts = {}
    for d in data["decisions"]:
        counts[d["reason_code"]] = counts.get(d["reason_code"], 0) + 1
    data["reason_counts"] = counts

    states = {}
    for r in data["movement"]:
        states[r["movement_state"]] = states.get(r["movement_state"], 0) + 1
    data["movement_counts"] = states

    totals = {
        "canonical_events": len(data["ordered_events"]),
        "admitted_moves": len(data["accepted"]),
        "set_aside_moves": len(data["decisions"]) - len(data["accepted"]),
        "confirmed_moves": states.get("confirmed", 0),
        "contradicted_moves": states.get("contradicted", 0),
        "loose_confirmations": len(data["loose_confirmations"]),
        "rehandle_moves": sum(r["rehandles"] for r in data["rehandles"].values()),
        "assessed_cents": sum(r["charge_cents"] for r in data["rehandles"].values()),
        "published_cents": sum(r["published_cents"] for r in data["republished"]),
        "rationed_minutes": sum(data["vessel_share"].values()),
        "loaded_minutes": sum(r["loaded_minutes"] for r in data["load_ledger"]),
        "loaded_boxes": len(data["loaded"]),
        "deferred_boxes": len(data["deferred"]),
        "eligible_boxes": sum(1 for r in data["eligibility"] if r["eligible"] == "yes"),
        "boxes_on_yard": len(data["closing_where"]),
        "equipment_exceptions": len(data["equipment_exceptions"]),
    }
    data["totals"] = totals

    # The identity checks. Totals that agree by category can still disagree by
    # identity, so each check names the identity set it compares.
    identities = []
    loaded_ids = set(x["box_id"] for x in data["loaded"])
    deferred_ids = set(x["box_id"] for x in data["deferred"])
    eligible_ids = set(r["box_id"] for r in data["eligibility"] if r["eligible"] == "yes")
    identities.append(("loaded_and_deferred_partition_eligible",
                       "yes" if (loaded_ids | deferred_ids) == eligible_ids
                       and not (loaded_ids & deferred_ids) else "no"))
    moved_ids = set(h["box_id"] for h in data["history"])
    identities.append(("moved_boxes_all_on_yard",
                       "yes" if moved_ids <= set(data["closing_where"]) else "no"))
    identities.append(("decision_count_matches_events",
                       "yes" if len(data["decisions"]) == len(data["ordered_events"]) else "no"))
    identities.append(("republished_covers_deferred",
                       "yes" if set(r["box_id"] for r in data["republished"]) == deferred_ids
                       else "no"))
    data["identities"] = identities


# --------------------------------------------------------------------------
# publication
# --------------------------------------------------------------------------


def _write_text(path, text):
    Path(path).write_text(text, encoding="utf-8", newline="\n")


def _write_lines(path, lines):
    _write_text(path, "\n".join(lines) + "\n")


def _write_rows(path, header, rows, sep):
    out = [sep.join(header)]
    for row in rows:
        out.append(sep.join("" if v is None else str(v) for v in row))
    _write_text(path, "\n".join(out) + "\n")


def _write_json(path, payload):
    _write_text(path, json.dumps(payload, indent=2, sort_keys=False,
                                 ensure_ascii=False) + "\n")


def _write_jsonl(path, records):
    out = [json.dumps(r, separators=(",", ":"), sort_keys=False, ensure_ascii=False)
           for r in records]
    _write_text(path, "\n".join(out) + "\n" if out else "")


def _xml_text(value):
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def publish(data, out_dir):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    shift = data["shift_id"]
    rank = data["controls"]["class_rank"]

    # Y01
    rows = []
    for ev in data["ordered_events"]:
        rows.append([ev["event_key"], ev["order_id"], ev["box_id"], ev["source_system"],
                     data["source_rank"].get(ev["source_system"], 0), ev["event_seq"],
                     ev["raised_min"], ev["slot_code"], ev["cluster_tag"]])
    _write_rows(out / "canonical_events.csv",
                ["event_key", "order_id", "box_id", "source_system", "source_priority",
                 "event_seq", "raised_min", "slot_code", "cluster_tag"], rows, ",")

    # Y02
    rows = []
    for box_id in sorted(data["boxes"]):
        b = data["boxes"][box_id]
        rows.append([box_id, b["iso_length"], b["teu_factor"], b["box_class"],
                     b["vessel_id"], b["mass_kg"], b["mass_state"]])
    _write_rows(out / "container_dimensions.csv",
                ["box_id", "iso_length", "teu_factor", "box_class", "vessel_id",
                 "mass_kg", "mass_state"], rows, ",")

    # Y03
    rows = []
    for vid in sorted(data["vessels"]):
        v = data["vessels"][vid]
        rows.append([vid, v["voyage"], v["berth_id"], v["service_group"],
                     v["destination"], v["voyage_sequence"], v["applicable_revision"]])
    _write_rows(out / "vessel_obligation.csv",
                ["vessel_id", "voyage", "berth_id", "service_group", "destination",
                 "voyage_sequence", "applicable_revision"], rows, ",")

    # Y04
    rows = []
    for block_id in sorted(data["blocks"]):
        b = data["blocks"][block_id]
        opening = data["opening_counts"].get(block_id, 0)
        rows.append([block_id, b["zone"], b["rows"], b["tiers_max"], b["slot_capacity"],
                     opening, max(0, b["slot_capacity"] - opening)])
    _write_rows(out / "initial_occupancy.psv",
                ["block_id", "zone", "rows", "tiers_max", "slot_capacity",
                 "opening_boxes", "opening_free"], rows, "|")

    # Y05
    rows = []
    for ev in data["ordered_events"]:
        rows.append([ev["event_key"], ev["order_id"], ev["slot_code"],
                     data["source_rank"].get(ev["source_system"], 0),
                     ev["event_seq"], ev["box_id"]])
    _write_rows(out / "event_order.csv",
                ["event_key", "order_id", "slot_code", "source_priority",
                 "event_seq", "box_id"], rows, ",")

    # Y06
    _write_json(out / "cycle_break_report.json", {
        "shift_id": shift,
        "protection_depth": data["controls"]["protection_depth"],
        "component_count": len(data["cycle_report"]),
        "components": data["cycle_report"],
    })
    rows = []
    keys = dict((ev["order_id"], ev["event_key"]) for ev in data["ordered_events"])
    for position, oid in enumerate(data["dependency_order"], start=1):
        rows.append([position, oid, keys[oid]])
    _write_rows(out / "dependency_order.csv",
                ["position", "order_id", "event_key"], rows, ",")

    # Y07
    rows = []
    for d in data["decisions"]:
        rows.append([d["event_key"], d["order_id"], d["box_id"], d["slot_code"],
                     d["to_block"], d["to_row"], d["to_tier"], d["outcome"],
                     d["reason_code"]])
    _write_rows(out / "move_eligibility.csv",
                ["event_key", "order_id", "box_id", "slot_code", "to_block",
                 "to_row", "to_tier", "outcome", "reason_code"], rows, ",")
    rows = [[d["event_key"], d["order_id"], d["box_id"], d["slot_code"], d["reason_code"]]
            for d in data["decisions"] if d["outcome"] == "set_aside"]
    _write_rows(out / "rejected_moves.tsv",
                ["event_key", "order_id", "box_id", "slot_code", "reason_code"], rows, "\t")
    rows = [[rung, data["reason_counts"].get(rung, 0)] for rung in data["ladder"]]
    _write_rows(out / "rejection_reasons.csv", ["reason_code", "order_count"], rows, ",")
    rows = [[d["event_key"], d["order_id"], d["box_id"], d["slot_code"], d["to_block"],
             d["to_row"], d["to_tier"]] for d in data["accepted"]]
    _write_rows(out / "accepted_moves.csv",
                ["event_key", "order_id", "box_id", "slot_code", "to_block", "to_row",
                 "to_tier"], rows, ",")

    # Y08
    rows = []
    for h in sorted(data["history"], key=lambda x: x["event_key"]):
        rows.append([h["box_id"], h["event_key"], h["from_block"], h["from_row"],
                     h["from_tier"], h["to_block"], h["to_row"], h["to_tier"],
                     h["was_stacked"]])
    _write_rows(out / "container_state_history.psv",
                ["box_id", "event_key", "from_block", "from_row", "from_tier",
                 "to_block", "to_row", "to_tier", "was_stacked"], rows, "|")
    moves_by_box = {}
    for h in data["history"]:
        moves_by_box[h["box_id"]] = moves_by_box.get(h["box_id"], 0) + 1
    rows = []
    for box_id in sorted(data["boxes"]):
        spot = data["closing_where"].get(box_id)
        rows.append([box_id,
                     spot[0] if spot else ABSENT,
                     spot[1] if spot else ABSENT,
                     spot[2] if spot else ABSENT,
                     moves_by_box.get(box_id, 0),
                     "stacked" if spot else "off_yard"])
    _write_rows(out / "container_state_final.csv",
                ["box_id", "block_id", "row_no", "tier_no", "moves_applied", "state"],
                rows, ",")
    rows = []
    for block_id in sorted(data["blocks"]):
        b = data["blocks"][block_id]
        closing = data["closing_occupied"].get(block_id, 0)
        rows.append([block_id, b["zone"], b["slot_capacity"],
                     data["opening_counts"].get(block_id, 0), closing,
                     max(0, b["slot_capacity"] - closing)])
    _write_rows(out / "yard_occupancy.psv",
                ["block_id", "zone", "slot_capacity", "opening_boxes",
                 "closing_boxes", "closing_free"], rows, "|")

    # Y09
    _write_jsonl(out / "movement_accounting.jsonl", data["movement"])

    # Y10
    records = []
    for box_id in sorted(data["rehandles"]):
        r = data["rehandles"][box_id]
        records.append({
            "box_id": box_id,
            "moves": r["moves"],
            "rehandles": r["rehandles"],
            "tier_depths": r["depths"],
            "surcharge_cents": r["surcharge_cents"],
            "charge_cents": r["charge_cents"],
        })
    _write_jsonl(out / "rehandle_ledger.jsonl", records)
    rows = []
    for eid in sorted(data["equipment"]):
        u = data["equipment"][eid]
        rows.append([eid, u["equipment_class"], u["allowance"], u["used"],
                     u["minutes"], "yes" if u["used"] <= u["allowance"] else "no"])
    _write_rows(out / "equipment_usage.csv",
                ["equipment_id", "equipment_class", "allowance", "used", "minutes",
                 "within_allowance"], rows, ",")
    rows = [[e["event_key"], e["order_id"], e["equipment_id"], e["reason_code"]]
            for e in sorted(data["equipment_exceptions"], key=lambda x: x["event_key"])]
    _write_rows(out / "equipment_exceptions.tsv",
                ["event_key", "order_id", "equipment_id", "reason_code"], rows, "\t")

    # Y11
    rows = [[r["block_id"], r["slot_code"], r["slot_capacity"], r["occupied"],
             r["reserved"], r["unavailable"], r["available"]]
            for r in data["capacity_rows"]]
    _write_rows(out / "yard_capacity.csv",
                ["block_id", "slot_code", "slot_capacity", "occupied", "reserved",
                 "unavailable", "available"], rows, ",")
    rows = []
    for c in data["credits"]:
        rows.append([c["reservation_id"], c["block_id"], c["service_group"],
                     "SL%02d" % c["first"], "SL%02d" % c["last"], c["asked"],
                     c["withheld"], c["consumed"], c["unmet"]])
    _write_rows(out / "yard_reservations.psv",
                ["reservation_id", "block_id", "service_group", "first_slot",
                 "last_slot", "asked", "withheld", "consumed", "unmet"], rows, "|")
    rows = []
    for block_id in sorted(data["blocks"]):
        b = data["blocks"][block_id]
        closing = data["closing_occupied"].get(block_id, 0)
        rows.append([block_id, b["slot_capacity"], closing,
                     ratio_text(closing, b["slot_capacity"])])
    _write_rows(out / "block_utilization.csv",
                ["block_id", "slot_capacity", "closing_boxes", "utilisation_ratio"],
                rows, ",")
    by_slot = {}
    for d in data["decisions"]:
        entry = by_slot.setdefault(d["slot_code"], [0, 0, 0, 0])
        entry[0] += 1
        if d["outcome"] == "admitted":
            entry[1] += 1
        else:
            entry[2] += 1
    for r in data["movement"]:
        if r["movement_state"] == "confirmed":
            code = data["event_by_order"][r["order_id"]]["slot_code"]
            by_slot.setdefault(code, [0, 0, 0, 0])[3] += 1
    rows = []
    for code in data["slot_codes"] + [ABSENT]:
        entry = by_slot.get(code, [0, 0, 0, 0])
        rows.append([code, entry[0], entry[1], entry[2], entry[3]])
    _write_rows(out / "slot_accounting.csv",
                ["slot_code", "events", "admitted", "set_aside", "confirmed"],
                rows, ",")

    # Y12
    rows = []
    for vid in sorted(data["vessels"]):
        notice = data["cutoff_in_force"].get(vid)
        mine = [r for r in data["eligibility"] if r["vessel_id"] == vid]
        inside = sum(1 for r in mine if r["reason_code"] != "EL_AFTER_CUTOFF")
        rows.append([vid, (notice or {}).get("notice_id", ABSENT),
                     as_int((notice or {}).get("cutoff_min"), 0) if notice else 0,
                     len(mine), inside, len(mine) - inside])
    _write_rows(out / "vessel_cutoff_status.csv",
                ["vessel_id", "notice_id", "cutoff_min", "boxes_total", "boxes_inside",
                 "boxes_outside"], rows, ",")
    rows = [[r["box_id"], r["vessel_id"], r["eligible"], r["reason_code"], r["ready_min"]]
            for r in data["eligibility"]]
    _write_rows(out / "load_eligibility.csv",
                ["box_id", "vessel_id", "eligible", "reason_code", "ready_min"], rows, ",")
    rows = []
    for vid in sorted(data["vessels"]):
        for r in sorted(data["eligible_by_vessel"].get(vid, []), key=lambda x: x["box_id"]):
            box = data["boxes"][r["box_id"]]
            rows.append([vid, r["box_id"], rank.get(box["box_class"], 0),
                         r["stow_sequence"], r["bay_no"], box["teu_factor"], box["mass_kg"]])
    _write_rows(out / "vessel_container_manifest.psv",
                ["vessel_id", "box_id", "class_rank", "stow_sequence", "bay_no",
                 "teu_factor", "mass_kg"], rows, "|")

    # Y13
    _write_jsonl(out / "ration_trace.jsonl", data["ration_trace"])
    _write_json(out / "load_sequence_ledger.json", {
        "shift_id": shift,
        "minutes_per_teu": data["minutes_per_teu"],
        "stowage_keys": data["controls"]["stowage_keys"],
        "vessels": data["load_ledger"],
    })
    rows = [[r["vessel_id"], r["box_id"], r["load_minutes"], r["assessed_cents"],
             r["published_cents"]] for r in data["republished"]]
    _write_rows(out / "deferred_containers.tsv",
                ["vessel_id", "box_id", "load_minutes", "assessed_cents",
                 "published_cents"], rows, "\t")
    vessels = []
    for entry in data["load_ledger"]:
        vid = entry["vessel_id"]
        boxes = [x for x in data["loaded"] if x["vessel_id"] == vid]
        boxes.sort(key=lambda x: x["load_position"])
        vessels.append({
            "vessel_id": vid,
            "berth_id": data["vessels"][vid]["berth_id"],
            "share_minutes": entry["share_minutes"],
            "loaded_minutes": entry["loaded_minutes"],
            "unused_minutes": entry["unused_minutes"],
            "boxes": [{"load_position": b["load_position"], "box_id": b["box_id"],
                       "load_minutes": b["load_minutes"]} for b in boxes],
        })
    _write_json(out / "departure_ledger.json",
                {"shift_id": shift, "vessels": vessels})

    # Y14
    rows = [[name, value] for name, value in sorted(data["totals"].items())]
    _write_rows(out / "terminal_reconciliation.csv", ["measure", "value"], rows, ",")

    granted, withdrawn = {}, {}
    for r in data["exceptions"]:
        if r.get("shift_id") != shift:
            continue
        target = withdrawn if yes(r.get("withdrawn")) else granted
        target[r["exception_kind"]] = target.get(r["exception_kind"], 0) + 1
    kinds = sorted(set(list(granted) + list(withdrawn)))
    rows = [[k, granted.get(k, 0), withdrawn.get(k, 0)] for k in kinds]
    _write_rows(out / "exception_summary.tsv",
                ["exception_kind", "granted", "withdrawn"], rows, "\t")

    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<vessel_reconciliation>",
             "  <shift_id>%s</shift_id>" % _xml_text(shift), "  <vessels>"]
    for entry in data["load_ledger"]:
        vid = entry["vessel_id"]
        lines.append('    <vessel id="%s">' % _xml_text(vid))
        lines.append("      <berth_id>%s</berth_id>" % _xml_text(data["vessels"][vid]["berth_id"]))
        lines.append("      <eligible_count>%d</eligible_count>" % entry["eligible_count"])
        lines.append("      <loaded_count>%d</loaded_count>" % entry["loaded_count"])
        lines.append("      <deferred_count>%d</deferred_count>" % entry["deferred_count"])
        lines.append("      <share_minutes>%d</share_minutes>" % entry["share_minutes"])
        lines.append("    </vessel>")
    lines.append("  </vessels>")
    for name, verdict in data["identities"]:
        lines.append("  <identity name=\"%s\">%s</identity>" % (_xml_text(name), verdict))
    lines.append("</vessel_reconciliation>")
    _write_lines(out / "vessel_reconciliation.xml", lines)

    lines = ["# The audit trail of one shift.", "[shift]",
             "shift_id = %s" % shift,
             "live_sheet_name = %s" % data["live_sheet_name"],
             "reference = %s" % data["reference"],
             "", "[counts]"]
    for name in sorted(data["totals"]):
        lines.append("%s = %d" % (name, data["totals"][name]))
    lines += ["", "[ladder]"]
    for rung in data["ladder"]:
        lines.append("%s = %d" % (rung, data["reason_counts"].get(rung, 0)))
    lines += ["", "[movement]"]
    for state in sorted(data["movement_counts"]):
        lines.append("%s = %d" % (state, data["movement_counts"][state]))
    _write_lines(out / "audit_trail.conf", lines)

    for berth in sorted(data["berths"]):
        pairings = [p for p in data["pairings"] if p["berth_id"] == berth]
        vessels_here = sorted(v for v, rec in data["vessels"].items()
                              if rec["berth_id"] == berth)
        _write_json(out / ("berth_report_%s.json" % berth), {
            "shift_id": shift,
            "berth_id": berth,
            "vessel_count": len(vessels_here),
            "vessels": vessels_here,
            "pool_minutes": sum(p["pool_minutes"] for p in pairings),
            "rationed_minutes": sum(p["rationed_minutes"] for p in pairings),
            "pairings": pairings,
        })

    lines = ["# Daily operational summary", "",
             "shift %s at reference %s" % (shift, data["reference"]), ""]
    for name in sorted(data["totals"]):
        lines.append("- %s: %d" % (name, data["totals"][name]))
    lines += ["", "## Ladder", ""]
    for rung in data["ladder"]:
        lines.append("- %s: %d" % (rung, data["reason_counts"].get(rung, 0)))
    lines += ["", "## Identity checks", ""]
    for name, verdict in data["identities"]:
        lines.append("- %s: %s" % (name, verdict))
    _write_lines(out / "daily_operational_summary.md", lines)

    _write_json(out / "final_control_totals.json", {
        "shift_id": shift,
        "live_sheet_name": data["live_sheet_name"],
        "minutes_per_teu": data["minutes_per_teu"],
        "totals": dict((k, data["totals"][k]) for k in sorted(data["totals"])),
        "identities": dict((name, verdict) for name, verdict in data["identities"]),
    })

    digests = []
    for name in ALL_DOCUMENTS:
        if name == "publication_manifest.json":
            continue
        payload = (out / name).read_bytes()
        digests.append({"name": name,
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "bytes": len(payload)})
    core_blob = b""
    publication_blob = b""
    for entry in digests:
        line = ("%s %s\n" % (entry["name"], entry["sha256"])).encode("utf-8")
        if entry["name"] in CORE_DOCUMENTS:
            core_blob += line
        else:
            publication_blob += line
    _write_json(out / "publication_manifest.json", {
        "shift_id": shift,
        "core_digest": hashlib.sha256(core_blob).hexdigest(),
        "publication_digest": hashlib.sha256(publication_blob).hexdigest(),
        "document_count": len(digests) + 1,
        "documents": digests,
    })


def run_pipeline(data_dir, out_dir):
    data = load_shift(data_dir)
    prepare(data)
    stage_y01(data)
    stage_y02(data)
    stage_y03(data)
    stage_y04(data)
    stage_y05(data)
    stage_y06(data)
    stage_y07(data)
    stage_y08(data)
    stage_y09(data)
    stage_y10(data)
    stage_y11(data)
    stage_y12(data)
    stage_y13(data)
    stage_y14(data)
    publish(data, out_dir)
    return data


# --------------------------------------------------------------------------
# grading scaffolding
# --------------------------------------------------------------------------

_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_STATE = {}

# rewardkit runs the criteria of one file in up to eight threads
# (reward.py: asyncio.to_thread per criterion), so everything below that
# builds shared state holds this lock: the minted corpora and their
# recomputed references, the runs of the delivered program, and the variant
# pipelines. The variants in particular rebind module globals while they run,
# which is only safe while no other thread is inside a pipeline. Comparisons
# read that state once it is built and need no lock.
_LOCK = threading.RLock()


def _drops_privileges():
    return os.name == "posix" and hasattr(os, "geteuid") and os.geteuid() == 0


def _untrusted(command):
    """Submitted code runs as nobody so it cannot read this module, which
    holds the reference pipeline and the seeds."""
    if not _drops_privileges():
        return command
    if shutil.which("setpriv") is None:
        raise RuntimeError("setpriv is required to isolate submitted code from /tests")
    return [*_SETPRIV, *command]


def _workroot():
    with _LOCK:
        root = _STATE.get("workroot")
        if root is None:
            root = Path(tempfile.mkdtemp(prefix="yardledger-grade-"))
            # mkdtemp is 0700 and root owned. The dropped child has to traverse
            # this far to reach the public tree, and no further.
            os.chmod(root, 0o755)
            _STATE["workroot"] = root
        return root


def _publicroot():
    """The only part of the work tree the dropped child may read and write:
    the minted working papers and the output directories it creates."""
    with _LOCK:
        root = _workroot() / "public"
        root.mkdir(exist_ok=True)
        os.chmod(root, 0o777)
        return root


def _refroot():
    """Root owned and 0700. The recomputed reference publication of every
    graded shift lives here rather than beside the papers it was derived
    from, so submitted code cannot read the answer it is being graded
    against out of its own working tree."""
    with _LOCK:
        root = _workroot() / "reference"
        root.mkdir(exist_ok=True)
        os.chmod(root, 0o700)
        return root


def _rundir():
    """The working directory the submitted program is run from. It is its own
    empty directory, so the program cannot enumerate the grading tree by
    listing the directory it happens to start in."""
    with _LOCK:
        root = _publicroot() / "cwd"
        root.mkdir(exist_ok=True)
        os.chmod(root, 0o777)
        return root


def _relax(path):
    for item in Path(path).rglob("*"):
        try:
            os.chmod(item, 0o777 if item.is_dir() else 0o666)
        except OSError:
            pass
    try:
        os.chmod(path, 0o777)
    except OSError:
        pass


def _case(seed):
    """Mint one shift and recompute its publication. Cached."""
    key = "case-%d" % seed
    with _LOCK:
        cached = _STATE.get(key)
        if cached is not None:
            return cached
        root = _publicroot() / ("shift_%d" % seed)
        data_dir = root / "papers"
        ref_dir = _refroot() / ("shift_%d" % seed)
        if not data_dir.is_dir():
            mint_corpus(seed, SEED_PROFILE[seed], data_dir)
            run_pipeline(data_dir, ref_dir)
            # Only the papers are opened up. The reference publication stays
            # under the root owned reference tree.
            _relax(root)
        _STATE[key] = (data_dir, ref_dir)
        return _STATE[key]


def _program():
    path = _delivered() / PROGRAM_NAME
    if not path.is_file():
        raise AssertionError("no %s was delivered at %s" % (PROGRAM_NAME, path))
    return path


def _grant_read(program):
    """Let the unprivileged run user open an agent-written program.

    An agent editor writes through a temp file and renames it into place, so the
    delivered program arrives at mode 0600 owned by the agent's uid. The run
    below drops to an unprivileged user, which cannot open that file, so without
    this grant every check that executes the program returns False on a
    submission that is completely correct. The verifier is root, so it grants
    read on the program and traverse on the directories above it. The grant on
    the parents is additive, because the output parent must keep the write bit
    the dropped user needs to create the leaf directory itself. The privilege
    drop is unchanged: the program still runs with no privileges of its own.
    """
    program = Path(program)
    try:
        os.chmod(program, 0o755)
    except OSError:
        pass
    for parent in (program.parent, program.parent.parent):
        try:
            os.chmod(parent, (os.stat(parent).st_mode & 0o777) | 0o055)
        except OSError:
            pass


def _program_present():
    """A detector never fires on an empty container: with nothing delivered
    there is no wrong reading to report."""
    return (_delivered() / PROGRAM_NAME).is_file()


_WORKSPACE = {}


def _delivered():
    return _WORKSPACE.get("out") or Path(OUTPUT_ROOT)


def _guard(workspace, body):
    """Run one check body and turn every failure into a False verdict.

    An exception raised inside a check aborts the whole rewardkit run and no
    reward is written at all, so a body that cannot reach a verdict reports
    False instead. For a positive check that reads as a failure; for a
    detector it reads as silence, which is what the "must stay silent" guards
    inside the detector bodies already mean.
    """
    _WORKSPACE["out"] = Path(workspace) / "out"
    try:
        return bool(body())
    except Exception:
        return False


def _digest_tree(root):
    root = Path(root)
    out = {}
    for item in sorted(root.rglob("*")):
        if item.is_file():
            out[str(item.relative_to(root))] = hashlib.sha256(item.read_bytes()).hexdigest()
    return out


def _run_program(data_dir, out_dir, cwd=None, options_reversed=False):
    """Run the delivered program the way its contract says it is called.

    The contract has the program create the output directory when it is
    absent and accept the two options in either order, so the directory is
    deliberately not created here and the order is deliberately varied. Only
    the parent is prepared, and opened up, because the run is dropped to an
    unprivileged user that has to create the leaf itself.
    """
    out_dir = Path(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(out_dir.parent, 0o777)
    if out_dir.is_dir():
        os.chmod(out_dir, 0o777)
    work = Path(cwd) if cwd is not None else _rundir()
    if options_reversed:
        options = ["--out", str(out_dir), "--data", str(data_dir)]
    else:
        options = ["--data", str(data_dir), "--out", str(out_dir)]
    _grant_read(_program())
    command = [sys.executable, str(_program()), *options]
    proc = subprocess.Popen(_untrusted(command), cwd=str(work),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    timed_out = False
    try:
        _, stderr = proc.communicate(timeout=900)
    except subprocess.TimeoutExpired:
        timed_out = True
        stderr = ""
        proc.kill()
        proc.communicate()
    finally:
        # start_new_session makes the run its own process group leader, so one
        # signal reaches every grandchild the delivered program daemonised. A
        # child that outlived its check could rewrite the reward after grading
        # finished.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
    if timed_out:
        raise AssertionError("%s did not finish inside 900 seconds" % PROGRAM_NAME)
    if proc.returncode != 0:
        raise AssertionError("%s exited %d: %s"
                             % (PROGRAM_NAME, proc.returncode,
                                (stderr or "")[-600:]))


def _case_output(seed, tag="case"):
    """Run the delivered program once per minted shift, and remember what the
    run did to both directories. Shared with the cheat detectors."""
    key = "output-%s-%d" % (tag, seed)
    with _LOCK:
        cached = _STATE.get(key)
        if cached is not None:
            return cached
        if not _program_present():
            return None
        data_dir, _ = _case(seed)
        out_dir = _publicroot() / ("%s_out_%d" % (tag, seed)) / "publication"
        before = _digest_tree(data_dir)
        failed = ""
        try:
            # The graded run gives the two options the other way round from the
            # repeat run, and neither run creates the output directory, so both
            # halves of the calling convention the contract states are exercised
            # by every program test rather than by none of them.
            _run_program(data_dir, out_dir, options_reversed=(tag == "case"))
        except Exception as exc:
            failed = str(exc)
        after = _digest_tree(data_dir)
        record = {"out": out_dir, "before": before, "after": after, "failed": failed}
        _STATE[key] = record
        return record


def _compare(ref_dir, got_dir, names, label):
    ref_dir = Path(ref_dir)
    got_dir = Path(got_dir)
    for name in names:
        want = (ref_dir / name).read_bytes()
        target = got_dir / name
        if not target.is_file():
            raise AssertionError("%s wrote no %s" % (label, name))
        got = target.read_bytes()
        if got != want:
            raise AssertionError("%s: %s differs, %d bytes against %d"
                                 % (label, name, len(got), len(want)))


def _minted_outputs():
    outputs = {}
    for seed in MINTED_SEEDS:
        record = _case_output(seed)
        if record is None:
            raise AssertionError("no %s was delivered" % PROGRAM_NAME)
        if record["failed"]:
            raise AssertionError(record["failed"])
        outputs[seed] = record["out"]
    return outputs


def _shipped_family(family, label):
    """Compare one family of the shipped delivery against the publication the
    shipped papers entail.

    Each family stands on its own. A document read the wrong way costs the
    family it sits in and nothing else, so partial credit tracks how much of
    the shift was recomputed rather than turning on one comparison.
    """
    _, ref_dir = _case(SAMPLE_SEED)
    _compare(ref_dir, _delivered(), family, label)
    return True


ALL_ARTIFACTS = sorted(set(ALL_DOCUMENTS))

# Module names a planted file could shadow inside the verifier. The reference
# pipeline imports every one of them.
REBINDING_NAMES = {
    "fractions.py", "hashlib.py", "io.py", "json.py", "os.py", "pathlib.py",
    "re.py", "shutil.py", "sitecustomize.py", "sqlite3.py", "subprocess.py",
    "sys.py", "tempfile.py", "usercustomize.py", "zipfile.py",
}


# --------------------------------------------------------------------------
# positive tests
# --------------------------------------------------------------------------


def _body_all_artifacts_exist():
    out = _delivered()
    missing = [name for name in ALL_ARTIFACTS if not (out / name).is_file()]
    if missing:
        raise AssertionError("missing published documents: %s" % ", ".join(missing))
    if not (out / PROGRAM_NAME).is_file():
        raise AssertionError("no %s was delivered" % PROGRAM_NAME)
    return True


DELIMITED_HEADERS = (
    ("canonical_events.csv", ",", "event_key"),
    ("container_dimensions.csv", ",", "box_id"),
    ("vessel_obligation.csv", ",", "vessel_id"),
    ("initial_occupancy.psv", "|", "block_id"),
    ("event_order.csv", ",", "event_key"),
    ("move_eligibility.csv", ",", "event_key"),
    ("yard_occupancy.psv", "|", "block_id"),
    ("yard_capacity.csv", ",", "block_id"),
    ("load_eligibility.csv", ",", "box_id"),
    ("terminal_reconciliation.csv", ",", "measure"),
)


def _body_core_documents_parse():
    out = _delivered()
    for name in ("cycle_break_report.json", "publication_manifest.json"):
        json.loads((out / name).read_text(encoding="utf-8"))
    for name, sep, header in DELIMITED_HEADERS:
        text = (out / name).read_text(encoding="utf-8")
        first = text.split("\n")[0]
        if first.split(sep)[0] != header:
            raise AssertionError("%s header starts %r" % (name, first[:60]))
    return True


def _body_core_documents_line_endings():
    out = _delivered()
    for name, _sep, _header in DELIMITED_HEADERS:
        text = (out / name).read_text(encoding="utf-8")
        if not text.endswith("\n"):
            raise AssertionError("%s does not end with one line feed" % name)
        if "\r" in text:
            raise AssertionError("%s carries a carriage return" % name)
    return True


def _body_shipped_spine_exact():
    return _shipped_family(SPINE, "shipped shift spine")


def _body_shipped_state_family_exact():
    return _shipped_family(FAMILY_STATE, "shipped state family")


def _body_shipped_yard_family_exact():
    return _shipped_family(FAMILY_YARD, "shipped yard family")


def _body_shipped_vessel_family_exact():
    return _shipped_family(FAMILY_VESSEL, "shipped vessel family")


def _body_shipped_manifest_exact():
    """The manifest digests the thirty nine documents beside it, so it owns a
    weight of its own rather than riding along inside the spine set.

    The minted shifts need no manifest check: their manifests are a pure
    function of bytes the family checks already compare, and a manifest
    written from anything other than the delivery is caught by the digest
    mismatch detector.
    """
    return _shipped_family([MANIFEST], "shipped publication manifest")


def _body_program_minted_spines_exact():
    outputs = _minted_outputs()
    for seed in MINTED_SEEDS:
        _, ref_dir = _case(seed)
        _compare(ref_dir, outputs[seed], SPINE, "minted shift %d spine" % seed)
    return True


def _program_family(seed, family, label):
    """Compare one family of one minted shift against what its own papers
    entail.

    The only precondition is that the delivered program ran and exited zero on
    every minted shift. No family is gated on another family, and no shift is
    gated on another shift.
    """
    outputs = _minted_outputs()
    _, ref_dir = _case(seed)
    _compare(ref_dir, outputs[seed], family, label)
    return True


def _body_program_strained_state_exact():
    return _program_family(EVAL_SEED, FAMILY_STATE, "strained state family")


def _body_program_strained_yard_exact():
    return _program_family(EVAL_SEED, FAMILY_YARD, "strained yard family")


def _body_program_strained_vessel_exact():
    return _program_family(EVAL_SEED, FAMILY_VESSEL, "strained vessel family")


def _body_program_wide_state_exact():
    return _program_family(CHALLENGE_SEED, FAMILY_STATE, "wide state family")


def _body_program_wide_yard_exact():
    return _program_family(CHALLENGE_SEED, FAMILY_YARD, "wide yard family")


def _body_program_wide_vessel_exact():
    return _program_family(CHALLENGE_SEED, FAMILY_VESSEL, "wide vessel family")


def _body_program_sparse_state_exact():
    return _program_family(PROBE_SEED, FAMILY_STATE, "sparse state family")


def _body_program_sparse_yard_exact():
    return _program_family(PROBE_SEED, FAMILY_YARD, "sparse yard family")


def _body_program_sparse_vessel_exact():
    return _program_family(PROBE_SEED, FAMILY_VESSEL, "sparse vessel family")


# --------------------------------------------------------------------------
# named wrong readings
#
# Each variant below is one documented decision read the other way. A detector
# asserts that the delivered bytes MATCH the wrong reading, so a delivery that
# read the decision correctly fails the assertion and escapes the penalty, and
# a delivery that produced nothing fails it too.
# --------------------------------------------------------------------------

_ORIG = {
    "read_ladder": read_ladder,
    "slot_of": slot_of,
    "_mass_reading": _mass_reading,
    "_withheld_against": _withheld_against,
    "_movement_state_for": _movement_state_for,
    "_ration_budget": _ration_budget,
    "_ration_quantise": _ration_quantise,
    "_ration_cell_key": _ration_cell_key,
}


def _variant(tag, patches):
    """Recompute the shipped shift with one decision read the other way."""
    key = "variant-" + tag
    with _LOCK:
        cached = _STATE.get(key)
        if cached is not None:
            return cached
        data_dir, _ = _case(SAMPLE_SEED)
        out = _workroot() / ("variant_" + tag)
        if not out.is_dir():
            for name, fn in patches.items():
                globals()[name] = fn
            try:
                run_pipeline(data_dir, out)
            finally:
                for name in patches:
                    globals()[name] = _ORIG[name]
        _STATE[key] = out
        return out


def _matches_variant(tag, patches, witnesses):
    out = _delivered()
    for name in witnesses:
        if not (out / name).is_file():
            raise AssertionError("no %s was delivered; this detector must stay "
                                 "silent" % name)
    ref_dir = _case(SAMPLE_SEED)[1]
    variant = _variant(tag, patches)
    differs = False
    for name in witnesses:
        if (variant / name).read_bytes() != (ref_dir / name).read_bytes():
            differs = True
    if not differs:
        raise AssertionError("the wrong reading of %s changes none of its "
                             "witnesses; this detector grades nothing" % tag)
    for name in witnesses:
        if (out / name).read_bytes() != (variant / name).read_bytes():
            return False
    return True


def _body_negative_alphabetical_ladder_order():
    """NEGATIVE: the admission ladder was applied in the alphabetical order of
    its rung codes rather than the order move_admission_ladder.txt prints. The
    assertion holds when the defect is present, so a delivery that read the
    printed order fails it and escapes the penalty."""
    return _matches_variant(
        "alpha_ladder",
        {"read_ladder": lambda path: sorted(_ORIG["read_ladder"](path))},
        ["move_eligibility.csv", "rejection_reasons.csv", "rejected_moves.tsv"])


def _body_negative_free_capacity_before_reserved():
    """NEGATIVE: free capacity was counted and the placement admitted against
    it without first withholding the standing reserved credit. The assertion
    holds when the defect is present, so a delivery that settled reserved
    capacity first fails it and escapes the penalty."""
    return _matches_variant(
        "free_first",
        {"_withheld_against": lambda credits, block_id, ordinal, group: 0},
        ["move_eligibility.csv", "yard_occupancy.psv", "yard_capacity.csv"])


def _body_negative_ration_run_to_convergence():
    """NEGATIVE: the quay ration was iterated until the shares stopped moving
    rather than for the number of passes the pass budget of
    berth_operations_memo.pdf allows. The assertion holds when the defect is
    present, so a delivery that stopped at the budget fails it and escapes the
    penalty."""
    return _matches_variant(
        "convergence",
        {"_ration_budget": lambda controls: 400},
        ["ration_trace.jsonl", "departure_ledger.json", "deferred_containers.tsv"])


def _body_negative_ration_rounds_once_at_end():
    """NEGATIVE: the ration carried exact shares through every pass and
    rounded once at the end instead of rounding at the end of every pass. The
    assertion holds when the defect is present, so a delivery that rounded per
    pass fails it and escapes the penalty."""
    return _matches_variant(
        "round_last",
        {"_ration_quantise": lambda value: value},
        ["ration_trace.jsonl", "departure_ledger.json", "load_sequence_ledger.json"])


def _body_negative_redistribution_across_the_pairing():
    """NEGATIVE: what the caps freed was spread across the whole pairing
    rather than inside the cross classification of berth and service group.
    The assertion holds when the defect is present, so a delivery that
    redistributed inside the cell fails it and escapes the penalty."""
    return _matches_variant(
        "flat_cell",
        {"_ration_cell_key": lambda data, vessel_id: "one_cell"},
        ["ration_trace.jsonl", "departure_ledger.json"])


def _body_negative_confirmation_overturns_the_ladder():
    """NEGATIVE: a landed confirmation was treated as evidence that a set
    aside move happened, so the movement was accounted as confirmed. The
    assertion holds when the defect is present, so a delivery that kept the
    order set aside fails it and escapes the penalty."""
    def wrong(planned_outcome, confirm_state):
        if confirm_state == "landed":
            return "confirmed"
        return _ORIG["_movement_state_for"](planned_outcome, confirm_state)
    return _matches_variant(
        "confirm_wins",
        {"_movement_state_for": wrong},
        ["movement_accounting.jsonl", "terminal_reconciliation.csv",
         "audit_trail.conf"])


def _body_negative_absent_mass_read_as_zero():
    """NEGATIVE: a mass declaration carrying the not supplied marker was read
    as a declared mass of zero. The assertion holds when the defect is
    present, so a delivery that published not_declared fails it and escapes
    the penalty."""
    return _matches_variant(
        "zero_mass",
        {"_mass_reading": lambda rec, factor: (0, "declared") if (
            rec is None or is_absent(rec.get("mass_value")))
            else _ORIG["_mass_reading"](rec, factor)},
        ["container_dimensions.csv"])


def _body_negative_slot_boundary_opens_the_slot():
    """NEGATIVE: a minute falling exactly on a slot boundary was placed in the
    slot that opens rather than the slot that closes. The assertion holds when
    the defect is present, so a delivery that used the closing convention
    fails it and escapes the penalty."""
    def wrong(minute, slot_length, slot_count):
        if minute < 0 or minute >= slot_length * slot_count:
            return 0
        return (minute // slot_length) + 1
    return _matches_variant(
        "opening_slot",
        {"slot_of": wrong},
        ["canonical_events.csv", "event_order.csv", "move_eligibility.csv"])


# --------------------------------------------------------------------------
# cheat detectors
#
# The detectors below are disjoint by construction: each one raises, and so
# stays silent, on the defect another one owns, so a single wrong decision
# never charges more than one penalty. The carrying-answers detector is the
# owner of last resort, and the two that could otherwise fire alongside it
# defer to it explicitly.
# --------------------------------------------------------------------------


def _carries_answers():
    """True when the delivery reproduces the shipped shift exactly, the
    program fails every shift it has never seen, and at least one of those
    runs handed back the shipped shift's own spine instead of the one its
    input entails.

    That last condition is what separates carried answers from a derivation
    with a gap. A program that crashes on an unseen shift, and a program that
    derives from its input and gets the answer wrong, are both honest and
    already forfeit the whole program tier; neither of them ever emits the
    bytes of a shift it was not pointed at.
    """
    if not _program_present():
        return False
    try:
        _, shipped_ref = _case(SAMPLE_SEED)
        _compare(shipped_ref, _delivered(), FAMILY_CORE, "shipped")
    except AssertionError:
        return False
    broken = 0
    memorised = 0
    for seed in MINTED_SEEDS:
        record = _case_output(seed)
        if record is None or record["failed"]:
            broken += 1
            continue
        try:
            _, ref_dir = _case(seed)
            _compare(ref_dir, record["out"], FAMILY_CORE, "minted")
        except AssertionError:
            broken += 1
            try:
                _compare(shipped_ref, record["out"], FAMILY_CORE, "memorised")
                memorised += 1
            except AssertionError:
                pass
    return broken == len(MINTED_SEEDS) and memorised > 0


def _body_negative_hardcoded_sample_answers():
    """NEGATIVE: the delivered program reproduces the shipped shift and fails
    on shifts it has never seen, so it carries answers rather than a
    derivation. The assertion holds when the defect is present."""
    if not _program_present():
        raise AssertionError("no program was delivered; this detector must stay silent")
    return _carries_answers()


def _body_negative_reads_training_corpus_at_runtime():
    """NEGATIVE: the delivered program carries the shipped shift inside it.
    Its source names this shift's identifier, its reference or one of its
    block identifiers, all of which the program contract requires it to read
    from the directory it is pointed at, so on another shift it would be
    reading the training corpus rather than its input. The assertion holds
    when the defect is present, so a program that reads those values fails it
    and escapes the penalty."""
    if not _program_present():
        raise AssertionError("no program was delivered; this detector must stay silent")
    if _carries_answers():
        raise AssertionError("the program carries the shipped answers; the "
                             "hardcoded answer detector owns that defect")
    source = _program().read_text(encoding="utf-8", errors="replace")
    data_dir, _ = _case(SAMPLE_SEED)
    planted = [_shift_id(SAMPLE_SEED), _shift_reference(SAMPLE_SEED)]
    for line in (data_dir / "yard_topology.xml").read_text(encoding="utf-8").split("\n"):
        if 'block id="' in line:
            planted.append(line.split('block id="')[1].split('"')[0])
    # A token stays a planted shift value when it is written base64 rather
    # than as a literal, so the encoded renderings are looked for as well.
    encoded = []
    for token in planted:
        raw = token.encode("utf-8")
        for pad in (b"", b" ", b"  "):
            encoded.append(base64.b64encode(pad + raw).decode("ascii").rstrip("="))
    return any(token in source for token in planted + encoded)


def _body_negative_program_ignores_its_input():
    """NEGATIVE: the delivered program writes the same bytes whatever
    directory it is pointed at, so it is not reading its input. The assertion
    holds when the defect is present."""
    if not _program_present():
        raise AssertionError("no program was delivered; this detector must stay silent")
    if _carries_answers():
        raise AssertionError("the program carries the shipped answers; the "
                             "hardcoded answer detector owns that defect")
    trees = []
    for seed in MINTED_SEEDS:
        record = _case_output(seed)
        if record is None or record["failed"]:
            raise AssertionError("the program produced nothing; the hardcoded "
                                 "answer detector owns that defect")
        trees.append(_digest_tree(record["out"]))
    return all(tree == trees[0] for tree in trees)


def _body_negative_nondeterministic_output():
    """NEGATIVE: two runs of the delivered program over one input directory
    disagree. The assertion holds when the defect is present."""
    if not _program_present():
        raise AssertionError("no program was delivered; this detector must stay silent")
    seed = MINTED_SEEDS[0]
    first = _case_output(seed)
    second = _case_output(seed, tag="repeat")
    if first is None or second is None or first["failed"] or second["failed"]:
        raise AssertionError("the program produced nothing; the hardcoded "
                             "answer detector owns that defect")
    return _digest_tree(first["out"]) != _digest_tree(second["out"])


def _body_negative_filename_dependent_behaviour():
    """NEGATIVE: the delivered program writes different bytes when the same
    shift is placed under another directory name. The assertion holds when the
    defect is present."""
    if not _program_present():
        raise AssertionError("no program was delivered; this detector must stay silent")
    seed = MINTED_SEEDS[0]
    record = _case_output(seed)
    if record is None or record["failed"]:
        raise AssertionError("the program produced nothing; the hardcoded "
                             "answer detector owns that defect")
    # This detector takes its own run under the original directory name rather
    # than reading only the cached graded run, so the single variable between
    # the two trees it compares below is the name of the input directory. A
    # program whose two same path runs already disagree is nondeterministic,
    # which the nondeterminism detector prices on its own, so this one returns
    # False rather than charging one defect in two places.
    baseline = _case_output(seed, tag="samepath")
    if baseline is None or baseline["failed"]:
        raise AssertionError("the program produced nothing; the hardcoded "
                             "answer detector owns that defect")
    same_path = _digest_tree(baseline["out"])
    if same_path != _digest_tree(record["out"]):
        return False
    data_dir, _ = _case(seed)
    renamed = _publicroot() / "a_differently_named_berth"
    if not renamed.is_dir():
        shutil.copytree(str(data_dir), str(renamed))
        _relax(renamed)
    other = _publicroot() / "renamed_out"
    # A renamed run that cannot complete, because it timed out or exited non
    # zero, is no evidence of filename dependence, so the failure is raised and
    # this detector stays silent. The hardcoded answer detector and the
    # forfeited program tier own a program that does not finish.
    _run_program(renamed, other)
    return same_path != _digest_tree(other)


def _body_negative_program_dirties_its_directories():
    """NEGATIVE: the delivered program changed the directory it was pointed
    at, or wrote something into the output directory that is no declared
    document. The assertion holds when the defect is present."""
    if not _program_present():
        raise AssertionError("no program was delivered; this detector must stay silent")
    dirty = False
    for seed in MINTED_SEEDS:
        record = _case_output(seed)
        if record is None or record["failed"]:
            raise AssertionError("the program produced nothing; the hardcoded "
                                 "answer detector owns that defect")
        if not record["out"].is_dir():
            raise AssertionError("the program produced nothing; the hardcoded "
                                 "answer detector owns that defect")
        written = sorted(p.name for p in record["out"].iterdir())
        if set(written) & REBINDING_NAMES:
            raise AssertionError("the program planted a shadowing module; the "
                                 "rebinding detector owns that defect")
        if record["before"] != record["after"]:
            dirty = True
        if written != sorted(ALL_ARTIFACTS):
            dirty = True
    return dirty


def _body_negative_rebinds_verifier_dependencies():
    """NEGATIVE: the delivered program plants a file that would shadow a
    module the verifier imports, so a later import inside the grading
    container would load agent code. The assertion holds when the defect is
    present."""
    planted = set()
    for seed in MINTED_SEEDS:
        record = _case_output(seed)
        if record is None or record["failed"]:
            raise AssertionError("the program produced nothing; the hardcoded "
                                 "answer detector owns that defect")
        if not record["out"].is_dir():
            raise AssertionError("the program produced nothing; the hardcoded "
                                 "answer detector owns that defect")
        planted |= {p.name for p in record["out"].iterdir()} & REBINDING_NAMES
    planted |= {p.name for p in _rundir().iterdir() if p.is_file()} & REBINDING_NAMES
    planted |= {p.name for p in _delivered().iterdir() if p.is_file()} & REBINDING_NAMES
    return bool(planted)


def _body_negative_manifest_digest_mismatch():
    """NEGATIVE: the publication manifest disagrees with the bytes of every
    document delivered beside it, so the manifest was written from something
    other than the delivery. The assertion holds when the defect is present."""
    out = _delivered()
    target = out / "publication_manifest.json"
    if not target.is_file():
        raise AssertionError("no manifest was delivered; this detector must stay silent")
    try:
        manifest = json.loads(target.read_text(encoding="utf-8"))
    except ValueError:
        raise AssertionError("the manifest does not parse; this detector must stay silent")
    documents = manifest.get("documents")
    if not isinstance(documents, list) or not documents:
        raise AssertionError("the manifest lists no document; this detector "
                             "must stay silent")
    checked = 0
    mismatched = 0
    for entry in documents:
        if not isinstance(entry, dict):
            continue
        beside = out / str(entry.get("name"))
        if not beside.is_file():
            continue
        checked += 1
        if hashlib.sha256(beside.read_bytes()).hexdigest() != entry.get("sha256"):
            mismatched += 1
    return checked > 0 and mismatched == checked


# --------------------------------------------------------------------------
# rewardkit criteria
#
# Each criterion hands its workspace to the body above and reports a bool.
# The weights live on the registrations at the foot of this file and nowhere
# else.
# --------------------------------------------------------------------------


@criterion(description="every declared document and the ledger program are present")
def all_artifacts_exist(workspace: Path) -> bool:
    return _guard(workspace, _body_all_artifacts_exist)


@criterion(description="the spine documents parse as the shapes the contract names")
def core_documents_parse(workspace: Path) -> bool:
    return _guard(workspace, _body_core_documents_parse)


@criterion(description="the delimited spine documents carry the line endings the serialisation contract names")
def core_documents_line_endings(workspace: Path) -> bool:
    return _guard(workspace, _body_core_documents_line_endings)


@criterion(description="the stage spine of the shipped shift is byte exact")
def shipped_spine_exact(workspace: Path) -> bool:
    return _guard(workspace, _body_shipped_spine_exact)


@criterion(description="the state family of the shipped shift is byte exact")
def shipped_state_family_exact(workspace: Path) -> bool:
    return _guard(workspace, _body_shipped_state_family_exact)


@criterion(description="the yard and equipment family of the shipped shift is byte exact")
def shipped_yard_family_exact(workspace: Path) -> bool:
    return _guard(workspace, _body_shipped_yard_family_exact)


@criterion(description="the vessel and publication family of the shipped shift is byte exact")
def shipped_vessel_family_exact(workspace: Path) -> bool:
    return _guard(workspace, _body_shipped_vessel_family_exact)


@criterion(description="the publication manifest of the shipped shift is byte exact")
def shipped_manifest_exact(workspace: Path) -> bool:
    return _guard(workspace, _body_shipped_manifest_exact)


@criterion(description="the delivered program reproduces the stage spine of all three shifts it has never seen")
def program_minted_spines_exact(workspace: Path) -> bool:
    return _guard(workspace, _body_program_minted_spines_exact)


@criterion(description="the state family of the strained shift is byte exact")
def program_strained_state_exact(workspace: Path) -> bool:
    return _guard(workspace, _body_program_strained_state_exact)


@criterion(description="the yard family of the strained shift is byte exact")
def program_strained_yard_exact(workspace: Path) -> bool:
    return _guard(workspace, _body_program_strained_yard_exact)


@criterion(description="the vessel family of the strained shift is byte exact")
def program_strained_vessel_exact(workspace: Path) -> bool:
    return _guard(workspace, _body_program_strained_vessel_exact)


@criterion(description="the state family of the wide shift is byte exact")
def program_wide_state_exact(workspace: Path) -> bool:
    return _guard(workspace, _body_program_wide_state_exact)


@criterion(description="the yard family of the wide shift is byte exact")
def program_wide_yard_exact(workspace: Path) -> bool:
    return _guard(workspace, _body_program_wide_yard_exact)


@criterion(description="the vessel family of the wide shift is byte exact")
def program_wide_vessel_exact(workspace: Path) -> bool:
    return _guard(workspace, _body_program_wide_vessel_exact)


@criterion(description="the state family of the sparse shift is byte exact")
def program_sparse_state_exact(workspace: Path) -> bool:
    return _guard(workspace, _body_program_sparse_state_exact)


@criterion(description="the yard family of the sparse shift is byte exact")
def program_sparse_yard_exact(workspace: Path) -> bool:
    return _guard(workspace, _body_program_sparse_yard_exact)


@criterion(description="the vessel family of the sparse shift is byte exact")
def program_sparse_vessel_exact(workspace: Path) -> bool:
    return _guard(workspace, _body_program_sparse_vessel_exact)


@criterion(description="the admission ladder was applied in the alphabetical order of its rung codes")
def negative_alphabetical_ladder_order(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_alphabetical_ladder_order)


@criterion(description="free capacity was counted before the standing reserved credit was withheld")
def negative_free_capacity_before_reserved(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_free_capacity_before_reserved)


@criterion(description="the quay ration was iterated past the pass budget until the shares stopped moving")
def negative_ration_run_to_convergence(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_ration_run_to_convergence)


@criterion(description="the ration rounded once at the end rather than at the end of every pass")
def negative_ration_rounds_once_at_end(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_ration_rounds_once_at_end)


@criterion(description="what the ceilings freed was spread across the whole pairing rather than inside the service group cell")
def negative_redistribution_across_the_pairing(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_redistribution_across_the_pairing)


@criterion(description="a landed confirmation was taken as evidence that a set aside move happened")
def negative_confirmation_overturns_the_ladder(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_confirmation_overturns_the_ladder)


@criterion(description="a mass declaration carrying the not supplied marker was read as a declared mass of zero")
def negative_absent_mass_read_as_zero(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_absent_mass_read_as_zero)


@criterion(description="a minute falling on a slot boundary was placed in the slot that opens")
def negative_slot_boundary_opens_the_slot(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_slot_boundary_opens_the_slot)


@criterion(description="the delivered program carries the shipped answers rather than a derivation")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_hardcoded_sample_answers)


@criterion(description="the delivered program carries this shift's own identifiers in its source")
def negative_reads_training_corpus_at_runtime(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_reads_training_corpus_at_runtime)


@criterion(description="the delivered program writes the same bytes whatever directory it is pointed at")
def negative_program_ignores_its_input(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_program_ignores_its_input)


@criterion(description="two runs of the delivered program over one input directory disagree")
def negative_nondeterministic_output(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_nondeterministic_output)


@criterion(description="the delivered program writes different bytes when the shift is placed under another directory name")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_filename_dependent_behaviour)


@criterion(description="the delivered program changed its input directory or wrote an undeclared file into its output directory")
def negative_program_dirties_its_directories(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_program_dirties_its_directories)


@criterion(description="the delivered program plants a file that would shadow a module the verifier imports")
def negative_rebinds_verifier_dependencies(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_rebinds_verifier_dependencies)


@criterion(description="the publication manifest disagrees with the bytes of every document delivered beside it")
def negative_manifest_digest_mismatch(workspace: Path) -> bool:
    return _guard(workspace, _body_negative_manifest_digest_mismatch)



criteria.all_artifacts_exist(weight=1)
criteria.core_documents_parse(weight=1)
criteria.core_documents_line_endings(weight=1)
criteria.shipped_spine_exact(weight=3)
criteria.shipped_state_family_exact(weight=3)
criteria.shipped_yard_family_exact(weight=3)
criteria.shipped_vessel_family_exact(weight=3)
criteria.shipped_manifest_exact(weight=3)
criteria.program_minted_spines_exact(weight=5)
criteria.program_strained_state_exact(weight=5)
criteria.program_strained_yard_exact(weight=5)
criteria.program_strained_vessel_exact(weight=5)
criteria.program_wide_state_exact(weight=5)
criteria.program_wide_yard_exact(weight=5)
criteria.program_wide_vessel_exact(weight=5)
criteria.program_sparse_state_exact(weight=5)
criteria.program_sparse_yard_exact(weight=5)
criteria.program_sparse_vessel_exact(weight=5)
criteria.negative_alphabetical_ladder_order(weight=-5)
criteria.negative_free_capacity_before_reserved(weight=-5)
criteria.negative_ration_run_to_convergence(weight=-5)
criteria.negative_ration_rounds_once_at_end(weight=-5)
criteria.negative_redistribution_across_the_pairing(weight=-3)
criteria.negative_confirmation_overturns_the_ladder(weight=-5)
criteria.negative_absent_mass_read_as_zero(weight=-3)
criteria.negative_slot_boundary_opens_the_slot(weight=-3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_reads_training_corpus_at_runtime(weight=-5)
criteria.negative_program_ignores_its_input(weight=-3)
criteria.negative_nondeterministic_output(weight=-3)
criteria.negative_filename_dependent_behaviour(weight=-3)
criteria.negative_program_dirties_its_directories(weight=-3)
criteria.negative_rebinds_verifier_dependencies(weight=-3)
criteria.negative_manifest_digest_mismatch(weight=-3)


# --------------------------------------------------------------------------
# corpus regeneration entry point
# --------------------------------------------------------------------------


def _write_corpus(root):
    """Regenerate the shipped working papers under <root>/data.

    The contents are cleared rather than the directory itself, so a shell
    sitting inside it does not block the regeneration.
    """
    target = Path(root) / "data"
    if target.exists():
        for item in target.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
    mint_corpus(SAMPLE_SEED, SEED_PROFILE[SAMPLE_SEED], target)


if __name__ == "__main__":
    _write_corpus(Path(sys.argv[1]))
