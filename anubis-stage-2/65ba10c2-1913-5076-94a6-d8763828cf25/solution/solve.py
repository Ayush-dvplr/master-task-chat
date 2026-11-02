#!/usr/bin/env python3
"""Recompute one operating shift of the Kestrel Point container terminal.

Usage:
    python3 yardledger.py --data <input directory> --out <output directory>

The two options may be given in either order. The program creates the output
directory when it is absent, writes the whole publication there and exits with
status zero.

Written to the working papers of the shift it is pointed at. Nothing about any
particular shift is held here: every identifier, control value, threshold,
boundary and rung code is read from the input directory at run time. Standard
library only, exact rational arithmetic throughout.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from fractions import Fraction
from pathlib import Path

ABSENT = "-"


# ==========================================================================
# small helpers
# ==========================================================================


def absent(value) -> bool:
    return value is None or str(value).strip() == ABSENT or str(value).strip() == ""


def whole(value, fallback=0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return fallback


def affirmative(value) -> bool:
    return str(value).strip().lower() in ("yes", "true", "1")


def quantise(value) -> int:
    """The rounding rule of rounding_and_arithmetic_policy.yaml: a residue of
    exactly one half rounds away from zero."""
    value = Fraction(value)
    if value >= 0:
        return int((value * 2 + 1) // 2)
    return -int(((-value) * 2 + 1) // 2)


def ratio_at_nine(numerator, denominator) -> str:
    """A ratio is published at exactly nine decimal places. A ratio whose
    denominator is zero is published as 0.000000000."""
    if denominator == 0:
        return "0.000000000"
    scaled = quantise(Fraction(numerator, denominator) * 1000000000)
    sign = "-" if scaled < 0 else ""
    scaled = abs(scaled)
    text = "%s%d.%09d" % (sign, scaled // 1000000000, scaled % 1000000000)
    return "0.000000000" if text == "-0.000000000" else text


def length_number(text) -> str:
    """The iso_length column is written bare, or with the suffix FT, or with
    the suffix ft. The three are one length and the bare number is published."""
    digits = re.match(r"\s*(\d+)", str(text))
    return digits.group(1) if digits else str(text).strip()


# ==========================================================================
# readers
# ==========================================================================


def read_table(path: Path, sep: str) -> list:
    text = path.read_text(encoding="utf-8")
    rows = [line for line in text.split("\n") if line != ""]
    if not rows:
        return []
    head = rows[0].split(sep)
    return [dict(zip(head, line.split(sep))) for line in rows[1:]]


def read_records(path: Path) -> list:
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").split("\n") if line.strip()]


def read_conf_pairs(path: Path) -> dict:
    """A key line is the key, one space, an equals sign, one space, a value.
    Section headers are square bracketed and are not needed by any reader
    here, so the pairs collapse into one mapping."""
    out = {}
    for line in path.read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            out[key.strip()] = value.strip()
    return out


def read_flat_yaml(path: Path) -> dict:
    """Only the scalar keys are wanted; the block statements are prose."""
    out = {}
    for line in path.read_text(encoding="utf-8").split("\n"):
        if not line or line.startswith("#") or line.startswith(" "):
            continue
        key, _, value = line.partition(":")
        value = value.strip()
        if value and not value.startswith(">") and not value.startswith("|"):
            out[key.strip()] = value
    return out


def read_rungs(path: Path) -> list:
    """The rungs in the order the paper prints them, which is the order they
    are applied in."""
    found = []
    for line in path.read_text(encoding="utf-8").split("\n"):
        hit = re.match(r"\s*rung\s+\d+\s+(\S+)", line)
        if hit:
            found.append(hit.group(1))
    return found


def read_rung_texts(path: Path) -> dict:
    """The line under each rung is that rung's reason text."""
    out = {}
    lines = path.read_text(encoding="utf-8").split("\n")
    for index, line in enumerate(lines):
        hit = re.match(r"\s*rung\s+\d+\s+(\S+)", line)
        if hit and index + 1 < len(lines):
            out[hit.group(1)] = lines[index + 1].strip()
    return out


def read_blocks_in_force(path: Path) -> list:
    """yard_topology.xml names the blocks in force for this shift."""
    text = path.read_text(encoding="utf-8")
    out = []
    for chunk in re.findall(r"<block\s([^>]*?)/?>", text):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', chunk))
        if affirmative(attrs.get("in_force", "yes")):
            out.append(attrs)
    return out


def read_topology_scalars(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    out = {}
    for tag in ("shift", "reference"):
        hit = re.search(r"<%s>(.*?)</%s>" % (tag, tag), text)
        if hit:
            out[tag] = hit.group(1)
    return out


# --- the three office papers ----------------------------------------------


def _sheet_cells(archive: zipfile.ZipFile, member: str, strings: list) -> dict:
    """Cell reference to text for one worksheet part."""
    body = archive.read(member).decode("utf-8")
    cells = {}
    for ref, attrs, value in re.findall(
            r'<c r="([A-Z]+\d+)"([^>]*)>(?:<v>(.*?)</v>)?</c>', body):
        if value is None or value == "":
            continue
        if 't="s"' in attrs:
            cells[ref] = strings[int(value)]
        else:
            cells[ref] = value
    return cells


def read_workbook(path: Path) -> list:
    """Every sheet of the workbook as (name, cells), in file order."""
    archive = zipfile.ZipFile(str(path))
    strings = re.findall(r"<t[^>]*>(.*?)</t>",
                         archive.read("xl/sharedStrings.xml").decode("utf-8"),
                         re.S)
    strings = [_unescape(s) for s in strings]
    names = re.findall(r'<sheet name="([^"]+)"',
                       archive.read("xl/workbook.xml").decode("utf-8"))
    sheets = []
    for position, name in enumerate(names, start=1):
        member = "xl/worksheets/sheet%d.xml" % position
        sheets.append((_unescape(name), _sheet_cells(archive, member, strings)))
    archive.close()
    return sheets


def _unescape(text: str) -> str:
    return (text.replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&apos;", "'")
                .replace("&amp;", "&"))


def read_memo_lines(path: Path) -> list:
    """The memorandum is a PDF whose page content streams are uncompressed, so
    the text showing operators carry the lines."""
    raw = path.read_bytes()
    out = []
    for chunk in re.findall(rb"\((.*?)\)\s*Tj", raw, re.S):
        text = chunk.decode("latin-1")
        text = text.replace(r"\(", "(").replace(r"\)", ")")
        out.append(text.replace("\\\\", "\\"))
    return out


def read_directive_blocks(path: Path) -> list:
    """word/document.xml as a flat list of the text of each paragraph and each
    table row, a table row carrying its cells in order."""
    archive = zipfile.ZipFile(str(path))
    body = archive.read("word/document.xml").decode("utf-8")
    archive.close()
    out = []
    for kind, chunk in re.findall(r"<w:(tbl|p)[ >](.*?)</w:\1>", body, re.S):
        if kind == "p":
            out.append([_unescape("".join(
                re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", chunk, re.S)))])
        else:
            for row in re.findall(r"<w:tr[ >](.*?)</w:tr>", chunk, re.S):
                cells = []
                for cell in re.findall(r"<w:tc[ >](.*?)</w:tc>", row, re.S):
                    cells.append(_unescape("".join(
                        re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", cell, re.S))))
                out.append(cells)
    return out


# ==========================================================================
# the working papers
# ==========================================================================


class Papers:
    """Everything the shift office kept, indexed the way the stages read it."""

    def __init__(self, root: Path):
        self.root = Path(root)
        topology = read_topology_scalars(self.root / "yard_topology.xml")
        self.shift_id = topology["shift"]
        self.reference = topology["reference"]
        self.topology_blocks = read_blocks_in_force(self.root / "yard_topology.xml")

        self.orders = read_table(self.root / "move_order_journal.csv", ",")
        self.withdrawals = read_table(self.root / "withdrawn_order_journal.tsv", "\t")
        self.box_rows = read_table(self.root / "box_master_register.csv", ",")
        self.mass_rows = read_table(self.root / "mass_declaration_returns.psv", "|")
        self.vessel_rows = read_table(self.root / "vessel_call_register.csv", ",")
        self.geometry_rows = read_table(self.root / "block_geometry_register.csv", ",")
        self.stack_rows = read_table(self.root / "stack_inventory_snapshot.csv", ",")
        self.calendar = read_table(self.root / "slot_grid_calendar.csv", ",")
        self.source_rows = read_table(self.root / "source_priority_register.csv", ",")
        self.equipment_rows = read_table(self.root / "handling_equipment_register.csv", ",")
        self.cutoff_rows = read_table(self.root / "cutoff_notice_board.tsv", "\t")
        self.stowage = read_table(self.root / "stowage_obligation_list.psv", "|")
        self.window_rows = read_table(self.root / "berth_window_register.csv", ",")
        self.demand_rows = read_table(self.root / "quay_demand_returns.csv", ",")
        self.exception_rows = read_table(self.root / "operational_exception_notices.csv", ",")
        self.reservations = read_records(self.root / "hold_reservation_notices.jsonl")
        self.edges = read_records(self.root / "move_dependency_declarations.jsonl")
        self.confirmations = read_records(self.root / "crane_confirmation_feed.ndjson")

        self.rungs = read_rungs(self.root / "move_admission_ladder.txt")
        self.rung_text = read_rung_texts(self.root / "move_admission_ladder.txt")
        self.roster = read_conf_pairs(self.root / "berth_reporting_roster.conf")
        self.berths = [b.strip() for b in
                       self.roster["reporting_berths"].split(",") if b.strip()]

        boundaries = read_flat_yaml(self.root / "boundary_conventions.yaml")
        self.slot_length = whole(boundaries["slot_length_minutes"])
        self.slot_count = whole(boundaries["slot_count"])
        # SECTION 3 of the program contract: the slot code vocabulary is read
        # from the papers rather than spelled here. The calendar carries one
        # row per block and slot, so its distinct slot codes in ascending
        # order are the slots of the shift, and a code's position in that
        # list is its ordinal.
        self.slot_codes = sorted(set(row["slot_code"] for row in self.calendar))
        self.slot_ordinal_of = dict((code, n) for n, code
                                    in enumerate(self.slot_codes, start=1))

        self._read_office_papers()

    # -- the three office papers -------------------------------------------

    def _read_office_papers(self):
        sheets = read_workbook(self.root / "quay_capacity_workbook.xlsx")
        live = None
        for name, cells in sheets:
            if cells.get("B1") == self.reference:
                live = (name, cells)
                break
        if live is None:
            raise SystemExit("no workbook sheet carries the shift reference")
        self.live_sheet_name, cells = live

        rows = {}
        for ref, value in cells.items():
            hit = re.match(r"([A-Z]+)(\d+)", ref)
            rows.setdefault(int(hit.group(2)), {})[hit.group(1)] = value
        labelled = {}
        for number in sorted(rows):
            row = rows[number]
            labelled.setdefault(row.get("A"), []).append(row)

        def scalar(name):
            row = labelled[name][0]
            return Fraction(whole(row["B"]), whole(row["C"], 1))

        self.damping = scalar("ration_damping_fraction")
        self.decitonne_kg = scalar("decitonne_kilograms")
        self.centner_kg = scalar("centner_kilograms")
        self.base_move_charge = scalar("base_move_charge_cents")
        self.teu_factor = dict(
            (length_number(row["B"]), whole(row["C"]))
            for row in labelled.get("teu_factor", []))
        self.vessel_ceiling = dict(
            ((row["B"], row["C"]), whole(row["D"]))
            for row in labelled.get("vessel_slot_ceiling", []))

        memo = read_memo_lines(self.root / "berth_operations_memo.pdf")
        self.surcharge_ladder = []
        self.gang_minutes = {}
        for line in memo:
            stripped = line.strip()
            hit = re.match(r"(\w+)\s+(-?\d+)", stripped)
            if hit and hit.group(1) == "ration_pass_budget":
                self.pass_budget = whole(hit.group(2))
            elif hit and hit.group(1) == "ration_minimum_step":
                self.minimum_step = whole(hit.group(2))
            elif hit and hit.group(1) == "dependency_protection_depth":
                self.protection_depth = whole(hit.group(2))
            roster = re.match(r"(\S+)\s+(SL\d+)\s+(\S+)\s+(\d+)\s*$", stripped)
            if roster:
                key = (roster.group(1), roster.group(2))
                self.gang_minutes[key] = self.gang_minutes.get(key, 0) + whole(roster.group(4))
                continue
            rung = re.match(r"(\d+)\s+(\d+)\s*$", stripped)
            if rung:
                self.surcharge_ladder.append((whole(rung.group(1)), whole(rung.group(2))))
        self.surcharge_ladder.sort()

        blocks = read_directive_blocks(self.root / "stowage_ordering_directive.docx")
        keys = {}
        self.class_rank = {}
        for cells in blocks:
            if len(cells) == 2 and cells[0].isdigit():
                keys[whole(cells[0])] = cells[1]
            elif len(cells) == 2 and cells[1].isdigit() and cells[0] != "key_position":
                self.class_rank[cells[0]] = whole(cells[1])
        self.stowage_keys = [keys[position] for position in sorted(keys)]

    # -- revision precedence -----------------------------------------------

    def mine(self, rows):
        """Rows belong to this shift only when their shift_id names it. A
        register with no shift_id column is wholly this shift's."""
        return [r for r in rows
                if "shift_id" not in r or r["shift_id"] == self.shift_id]

    def applicable(self, rows, subject, aside=("retired", "future")):
        """The surviving row with the highest revision_seq, per subject."""
        best = {}
        for row in self.mine(rows):
            if any(affirmative(row.get(flag)) for flag in aside):
                continue
            key = row[subject]
            if key not in best or whole(row["revision_seq"]) > whole(best[key]["revision_seq"]):
                best[key] = row
        return best

    # -- shared derivations -------------------------------------------------

    def slot_ordinal(self, minute):
        """A minute exactly on the boundary between two slots belongs to the
        slot that is closing. Minute zero belongs to the first slot. A minute
        beyond the close of the last slot belongs to no slot."""
        if minute > self.slot_length * self.slot_count:
            return None
        if minute <= 0:
            return 1
        return -(-minute // self.slot_length)

    def slot_code(self, ordinal):
        if ordinal is None or not 1 <= ordinal <= len(self.slot_codes):
            return ABSENT
        return self.slot_codes[ordinal - 1]

    def surcharge_of(self, depth):
        """The surcharge of the highest rung at or below that depth; a depth
        beyond the last rung carries the surcharge of the last rung."""
        found = 0
        for rung, cents in self.surcharge_ladder:
            if rung <= depth:
                found = cents
        return found


# ==========================================================================
# the shift
# ==========================================================================


def redistribute_within_cell(cell, offers):
    """RULE Y13.5 d on one cross classification cell of stage Y13.

    offers carries, per vessel of the pairing, the minutes its ceiling
    surrendered, whether that ceiling left it any headroom, and its appetite.
    Returns what each member of the cell takes from the minutes the ceilings of
    that cell gave back, apportioned across the appetites of the members the
    cap left headroom, and the minutes no member of the cell could take, which
    the pass publishes as its unplaced minutes.
    """
    freed = sum(offers[vessel_id]["surrendered"] for vessel_id in cell)
    if freed <= 0:
        return {}, Fraction(0)
    takers = [vessel_id for vessel_id in cell if offers[vessel_id]["headroom"]]
    claim = sum(offers[vessel_id]["appetite"] for vessel_id in takers)
    if not takers or claim == 0:
        return {}, freed
    return dict((vessel_id, freed * offers[vessel_id]["appetite"] / claim)
                for vessel_id in takers), Fraction(0)


class Shift:
    """The fourteen stages, in the order terminal_contract_overview.md lists
    them. Each stage reads the state the stages before it left."""

    def __init__(self, papers: Papers):
        self.p = papers

    # -- Y01 ---------------------------------------------------------------

    def stage_y01_canonical_events(self):
        p = self.p
        withdrawn = set(row["order_id"] for row in p.mine(p.withdrawals)
                        if row.get("state") == "withdrawn")
        self.events = []
        for row in p.orders:
            if row["order_id"] in withdrawn:
                continue
            ordinal = p.slot_ordinal(whole(row["raised_min"]))
            event = dict(row)
            event["slot_ordinal"] = ordinal
            event["slot_code"] = p.slot_code(ordinal)
            self.events.append(event)

    # -- Y02 ---------------------------------------------------------------

    def stage_y02_unit_normalisation(self):
        p = self.p
        self.box_record = p.applicable(p.box_rows, "box_id", aside=("retired",))
        filed = {}
        for row in p.mass_rows:
            if row.get("state") != "filed":
                continue
            key = row["box_id"]
            if key not in filed or whole(row["declaration_seq"]) > whole(filed[key]["declaration_seq"]):
                filed[key] = row
        self.dimensions = {}
        for box_id in sorted(self.box_record):
            record = self.box_record[box_id]
            declaration = filed.get(box_id)
            if declaration is None or absent(declaration.get("mass_value")):
                mass_kg, state = 0, "not_declared"
            else:
                unit = declaration["mass_unit"]
                value = Fraction(whole(declaration["mass_value"]))
                if unit == "dt":
                    value = value * p.decitonne_kg
                elif unit == "ct":
                    value = value * p.centner_kg
                mass_kg, state = quantise(value), "declared"
            length = length_number(record["iso_length"])
            self.dimensions[box_id] = {
                "box_id": box_id,
                "iso_length": length,
                "teu_factor": p.teu_factor.get(length, 0),
                "box_class": record["box_class"],
                "vessel_id": record["vessel_id"],
                "mass_kg": mass_kg,
                "mass_state": state,
            }

    # -- Y03 ---------------------------------------------------------------

    def stage_y03_vessel_obligation(self):
        p = self.p
        self.vessel_call = p.applicable(p.vessel_rows, "vessel_id", aside=("withdrawn",))
        self.obligation = {}
        for vessel_id in sorted(self.vessel_call):
            row = self.vessel_call[vessel_id]
            self.obligation[vessel_id] = {
                "vessel_id": vessel_id,
                "voyage": row["voyage"],
                "berth_id": row["berth_id"],
                "service_group": row["service_group"],
                "destination": row["destination"],
                "voyage_sequence": whole(row["voyage_sequence"]),
                "applicable_revision": whole(row["revision_seq"]),
            }

    def service_group_of(self, box_id):
        record = self.dimensions.get(box_id)
        if record is None:
            return ABSENT
        call = self.obligation.get(record["vessel_id"])
        return call["service_group"] if call else ABSENT

    # -- Y04 ---------------------------------------------------------------

    def stage_y04_opening_yard(self):
        p = self.p
        geometry = p.applicable(p.geometry_rows, "block_id")
        self.blocks = {}
        for entry in p.topology_blocks:
            block_id = entry["id"]
            revision = geometry.get(block_id)
            rows_n = whole(revision["rows"]) if revision else 0
            tiers = whole(revision["tiers_max"]) if revision else 0
            self.blocks[block_id] = {
                "block_id": block_id,
                "zone": entry.get("zone", ABSENT),
                "rows": rows_n,
                "tiers_max": tiers,
                "slot_capacity": rows_n * tiers,
            }
        self.opening_cell = {}
        for row in p.stack_rows:
            if row.get("stack_state") != "stacked":
                continue
            if row["block_id"] not in self.blocks:
                continue
            if row["box_id"] not in self.box_record:
                continue
            self.opening_cell[row["box_id"]] = {
                "block_id": row["block_id"],
                "row_no": whole(row["row_no"]),
                "tier_no": whole(row["tier_no"]),
            }
        self.opening_count = {}
        for cell in self.opening_cell.values():
            self.opening_count[cell["block_id"]] = self.opening_count.get(cell["block_id"], 0) + 1

    # -- Y05 ---------------------------------------------------------------

    def stage_y05_event_ordering(self):
        p = self.p
        ranks = p.applicable(p.source_rows, "source_system", aside=("retired",))
        self.source_rank = dict((name, whole(row["priority_rank"]))
                                for name, row in ranks.items())

        def key(event):
            ordinal = event["slot_ordinal"]
            return (0 if ordinal is not None else 1,
                    ordinal if ordinal is not None else 0,
                    self.source_rank.get(event["source_system"], 0),
                    whole(event["event_seq"]),
                    event["box_id"],
                    event["order_id"])

        self.events.sort(key=key)
        for position, event in enumerate(self.events, start=1):
            event["event_key"] = position
        self.event_of = dict((e["order_id"], e) for e in self.events)

    # -- Y06 ---------------------------------------------------------------

    def stage_y06_dependency_cycles(self):
        p = self.p
        canonical = set(self.event_of)
        live = []
        for edge in p.edges:
            if edge.get("state") != "declared":
                continue
            if edge["before_order"] not in canonical or edge["after_order"] not in canonical:
                continue
            if edge["before_order"] == edge["after_order"]:
                continue
            live.append(edge)

        self.cycle_entries = []
        while True:
            components = self._cyclic_components(canonical, live)
            if not components:
                break
            components.sort(key=lambda members: min(members))
            members = components[0]
            inside = [e for e in live
                      if e["before_order"] in members and e["after_order"] in members]
            ranked = sorted(inside, key=lambda e: (-whole(e["edge_weight"]), e["edge_id"]))
            protected = set(e["edge_id"] for e in ranked[:p.protection_depth])
            candidates = [e for e in inside if e["edge_id"] not in protected] or inside
            chosen = sorted(candidates,
                            key=lambda e: (whole(e["edge_weight"]), e["edge_id"]))[0]
            self.cycle_entries.append({
                "component_key": min(members),
                "member_count": len(members),
                "members": sorted(members),
                "edge_removed": chosen["edge_id"],
                "edge_weight": whole(chosen["edge_weight"]),
                "before_order": chosen["before_order"],
                "after_order": chosen["after_order"],
                "protected_count": len(protected),
            })
            live = [e for e in live if e["edge_id"] != chosen["edge_id"]]

        self.graph_edges = live
        self._dependency_order()

    def _cyclic_components(self, nodes, edges):
        """Strongly connected components of two orders or more."""
        successors = {}
        for edge in edges:
            successors.setdefault(edge["before_order"], []).append(edge["after_order"])
        index = {}
        low = {}
        on_stack = {}
        stack = []
        counter = [0]
        found = []

        def strongconnect(root):
            work = [(root, 0)]
            while work:
                node, child = work[-1]
                if child == 0:
                    index[node] = low[node] = counter[0]
                    counter[0] += 1
                    stack.append(node)
                    on_stack[node] = True
                recursed = False
                children = sorted(successors.get(node, []))
                for position in range(child, len(children)):
                    peer = children[position]
                    if peer not in index:
                        work[-1] = (node, position + 1)
                        work.append((peer, 0))
                        recursed = True
                        break
                    if on_stack.get(peer):
                        low[node] = min(low[node], index[peer])
                if recursed:
                    continue
                if low[node] == index[node]:
                    group = []
                    while True:
                        peer = stack.pop()
                        on_stack[peer] = False
                        group.append(peer)
                        if peer == node:
                            break
                    if len(group) >= 2:
                        found.append(set(group))
                work.pop()
                if work:
                    parent = work[-1][0]
                    low[parent] = min(low[parent], low[node])

        for node in sorted(nodes):
            if node not in index:
                strongconnect(node)
        return found

    def _dependency_order(self):
        """Orders are placed one at a time; the placeable order with the
        lowest event key is the one placed."""
        predecessors = {}
        successors = {}
        for order_id in self.event_of:
            predecessors[order_id] = set()
            successors[order_id] = []
        for edge in self.graph_edges:
            predecessors[edge["after_order"]].add(edge["before_order"])
            successors[edge["before_order"]].append(edge["after_order"])
        ready = sorted((self.event_of[o]["event_key"], o)
                       for o in predecessors if not predecessors[o])
        placed = []
        remaining = dict((o, set(v)) for o, v in predecessors.items())
        while ready:
            ready.sort()
            _, order_id = ready.pop(0)
            placed.append(order_id)
            for peer in successors[order_id]:
                remaining[peer].discard(order_id)
                if not remaining[peer]:
                    ready.append((self.event_of[peer]["event_key"], peer))
        self.dependency_order = placed

    # -- Y07 ---------------------------------------------------------------

    WAIVED_RUNG = {
        "zone_waiver": "LR_SEALED_ZONE",
        "tier_waiver": "LR_TIER_BEYOND_MAX",
        "reservation_release": "LR_RESERVED_BOUND",
    }

    def stage_y07_move_admission(self):
        p = self.p
        self.waivers = {}
        self.cutoff_waivers = set()
        for row in p.mine(p.exception_rows):
            if affirmative(row.get("withdrawn")):
                continue
            if row.get("target_kind") != "order":
                continue
            if row["exception_kind"] == "cutoff_waiver":
                self.cutoff_waivers.add(row["target_id"])
                continue
            rung = self.WAIVED_RUNG.get(row["exception_kind"])
            if rung:
                self.waivers.setdefault(row["target_id"], set()).add(rung)

        self.sealed = set()
        self.out_of_service = set()
        for row in p.calendar:
            if affirmative(row.get("sealed")):
                self.sealed.add((row["block_id"], row["slot_code"]))
            if not affirmative(row.get("in_service")):
                self.out_of_service.add((row["block_id"], row["slot_code"]))

        # RULE Y07.4. The opening credit of a reservation is what it asks for,
        # an absent quantity asking for the whole opening free capacity of its
        # block, capped at that opening free capacity.
        self.credits = []
        for notice in p.reservations:
            if notice.get("shift_id") != p.shift_id or notice.get("state") != "held":
                continue
            block = self.blocks.get(notice["block_id"])
            if block is None:
                opening_free = 0
            else:
                opening_free = max(0, block["slot_capacity"]
                                   - self.opening_count.get(notice["block_id"], 0))
            if absent(notice.get("quantity")):
                asked = opening_free
            else:
                asked = whole(notice["quantity"])
            withheld = min(asked, opening_free)
            self.credits.append({
                "reservation_id": notice["reservation_id"],
                "block_id": notice["block_id"],
                "service_group": notice["service_group"],
                "first_slot": notice["first_slot"],
                "last_slot": notice["last_slot"],
                "asked": asked,
                "withheld": withheld,
                "consumed": 0,
                "unmet": max(0, asked - withheld),
                "standing": withheld,
            })
        self.credits.sort(key=lambda c: c["reservation_id"])

        standing_count = dict(self.opening_count)
        self.cell = dict((box, dict(cell)) for box, cell in self.opening_cell.items())
        self.history = []
        self.moves_applied = {}
        self.slot_snapshot = {}
        self.reason_counts = dict((rung, 0) for rung in p.rungs)
        cluster_taken = set()
        self.decisions = []

        for event in self.events:
            reason = self._ladder(event, standing_count, cluster_taken)
            outcome = "set_aside" if reason else "admitted"
            event["outcome"] = outcome
            event["reason_code"] = reason or ABSENT
            if reason:
                self.reason_counts[reason] += 1
            else:
                cluster_taken.add(event["cluster_tag"])
                self._apply(event, standing_count)
            self.decisions.append(event)

        self._close_slots(standing_count)

    def _covering(self, block_id, ordinal):
        for credit in self.credits:
            if credit["block_id"] != block_id:
                continue
            first = self.p.slot_ordinal_of.get(credit["first_slot"], 0)
            last = self.p.slot_ordinal_of.get(credit["last_slot"], 0)
            if first <= ordinal <= last:
                yield credit

    def _ladder(self, event, standing_count, cluster_taken):
        """The rungs in the order move_admission_ladder.txt prints them. The
        first rung that catches an order settles it."""
        p = self.p
        lifted = self.waivers.get(event["order_id"], set())
        block_id = event["to_block"]
        block = self.blocks.get(block_id)
        ordinal = event["slot_ordinal"]
        for rung in p.rungs:
            if rung in lifted:
                continue
            if rung == "LR_UNKNOWN_BOX":
                if event["box_id"] not in self.box_record:
                    return rung
            elif rung == "LR_SEALED_ZONE":
                if ordinal is not None and (block_id, p.slot_code(ordinal)) in self.sealed:
                    return rung
            elif rung == "LR_STALE_SLOT":
                if ordinal is None:
                    return rung
            elif rung == "LR_TIER_BEYOND_MAX":
                if block is None or block["slot_capacity"] == 0:
                    return rung
                if whole(event["to_tier"]) > block["tiers_max"]:
                    return rung
            elif rung == "LR_RESERVED_BOUND":
                # RULE Y07.3. Reserved capacity is settled before free
                # capacity is counted.
                if block is None or block["slot_capacity"] == 0:
                    return rung
                free = block["slot_capacity"] - standing_count.get(block_id, 0)
                group = self.service_group_of(event["box_id"])
                withheld = 0
                for credit in self._covering(block_id, ordinal):
                    if credit["service_group"] != group:
                        withheld += credit["standing"]
                if free - withheld <= 0:
                    return rung
            elif rung == "LR_DUPLICATE_ORDER":
                if event["cluster_tag"] in cluster_taken:
                    return rung
        return None

    def _apply(self, event, standing_count):
        """RULE Y08.1. An admitted order takes its box out of the cell it
        stood in and puts it where the order names."""
        box_id = event["box_id"]
        was = self.cell.get(box_id)
        if was is not None:
            standing_count[was["block_id"]] = standing_count.get(was["block_id"], 0) - 1
        block_id = event["to_block"]
        standing_count[block_id] = standing_count.get(block_id, 0) + 1
        self.history.append({
            "box_id": box_id,
            "event_key": event["event_key"],
            "from_block": was["block_id"] if was else ABSENT,
            "from_row": was["row_no"] if was else ABSENT,
            "from_tier": was["tier_no"] if was else ABSENT,
            "to_block": block_id,
            "to_row": whole(event["to_row"]),
            "to_tier": whole(event["to_tier"]),
            "was_stacked": "yes" if was else "no",
        })
        event["tier_depth"] = was["tier_no"] if was else None
        self.cell[box_id] = {
            "block_id": block_id,
            "row_no": whole(event["to_row"]),
            "tier_no": whole(event["to_tier"]),
        }
        self.moves_applied[box_id] = self.moves_applied.get(box_id, 0) + 1
        # RULE Y07.5. An admitted order whose box belongs to the service group
        # a standing reservation names consumes one unit of its credit.
        group = self.service_group_of(box_id)
        for credit in self._covering(block_id, event["slot_ordinal"]):
            if credit["service_group"] == group and credit["standing"] > 0:
                credit["standing"] -= 1
                credit["consumed"] += 1
                break

    def _close_slots(self, standing_count):
        """RULE Y08.4. The occupancy of a block at the close of a slot is the
        occupancy after every admitted order of that slot and every earlier
        slot has been carried out."""
        p = self.p
        counts = dict(self.opening_count)
        credit_standing = dict((c["reservation_id"], c["withheld"]) for c in self.credits)
        cursor = 0
        admitted = [e for e in self.events if e["outcome"] == "admitted"]
        for ordinal in range(1, p.slot_count + 1):
            while cursor < len(admitted) and admitted[cursor]["slot_ordinal"] is not None \
                    and admitted[cursor]["slot_ordinal"] <= ordinal:
                event = admitted[cursor]
                was = self._cell_before(event)
                if was is not None:
                    counts[was] = counts.get(was, 0) - 1
                counts[event["to_block"]] = counts.get(event["to_block"], 0) + 1
                group = self.service_group_of(event["box_id"])
                for credit in self._covering(event["to_block"], event["slot_ordinal"]):
                    if credit["service_group"] == group and credit_standing[credit["reservation_id"]] > 0:
                        credit_standing[credit["reservation_id"]] -= 1
                        break
                cursor += 1
            self.slot_snapshot[ordinal] = (dict(counts), dict(credit_standing))
        self.closing_count = standing_count

    def _cell_before(self, event):
        for row in self.history:
            if row["event_key"] == event["event_key"]:
                return None if row["was_stacked"] == "no" else row["from_block"]
        return None

    # -- Y08 ---------------------------------------------------------------

    def stage_y08_yard_state(self):
        self.final_state = {}
        for box_id in sorted(self.box_record):
            cell = self.cell.get(box_id)
            if cell is None:
                self.final_state[box_id] = {
                    "box_id": box_id, "block_id": ABSENT, "row_no": ABSENT,
                    "tier_no": ABSENT, "moves_applied": self.moves_applied.get(box_id, 0),
                    "state": "off_yard",
                }
            else:
                self.final_state[box_id] = {
                    "box_id": box_id, "block_id": cell["block_id"],
                    "row_no": cell["row_no"], "tier_no": cell["tier_no"],
                    "moves_applied": self.moves_applied.get(box_id, 0),
                    "state": "stacked",
                }
        self.closing_boxes = {}
        for cell in self.cell.values():
            self.closing_boxes[cell["block_id"]] = self.closing_boxes.get(cell["block_id"], 0) + 1

    # -- Y09 ---------------------------------------------------------------

    def stage_y09_movement_reconciliation(self):
        """RULE Y09.1. When more than one confirmation names one order the one
        with the lowest confirmed minute counts."""
        p = self.p
        self.confirmation_of = {}
        self.loose = []
        for record in p.confirmations:
            order_id = record.get("order_id") or ""
            if not order_id:
                self.loose.append(record)
                continue
            held = self.confirmation_of.get(order_id)
            if held is None or whole(record["confirmed_min"]) < whole(held["confirmed_min"]):
                self.confirmation_of[order_id] = record
        self.loose.sort(key=lambda r: r["confirm_id"])

        self.movements = []
        for event in self.events:
            confirmation = self.confirmation_of.get(event["order_id"])
            state = confirmation.get("confirm_state") if confirmation else None
            if event["outcome"] == "admitted":
                if state == "landed":
                    movement = "confirmed"
                elif confirmation is None:
                    movement = "unconfirmed"
                else:
                    movement = "aborted"
            else:
                # RULE Y09.3. A contradicted order stays set aside.
                movement = "contradicted" if state == "landed" else "set_aside"
            event["movement_state"] = movement
            self.movements.append({
                "event_key": event["event_key"],
                "order_id": event["order_id"],
                "box_id": event["box_id"],
                "planned_outcome": event["outcome"],
                "confirm_id": confirmation["confirm_id"] if confirmation else ABSENT,
                "confirmed_min": whole(confirmation["confirmed_min"]) if confirmation else 0,
                "movement_state": movement,
            })

    # -- Y10 ---------------------------------------------------------------

    def stage_y10_rehandle_and_equipment(self):
        """RULE Y10.1. A rehandle is an admitted order whose box was standing
        in a yard cell immediately before that order, read off the state
        history rather than off any count the source papers carry."""
        p = self.p
        per_box = {}
        for row in self.history:
            entry = per_box.setdefault(row["box_id"], {
                "box_id": row["box_id"], "moves": 0, "rehandles": 0,
                "tier_depths": [], "surcharge_cents": 0, "charge_cents": 0,
            })
            entry["moves"] += 1
            entry["charge_cents"] += quantise(p.base_move_charge)
            if row["was_stacked"] == "yes":
                depth = row["from_tier"]
                entry["rehandles"] += 1
                entry["tier_depths"].append(depth)
                surcharge = p.surcharge_of(depth)
                entry["surcharge_cents"] += surcharge
                entry["charge_cents"] += surcharge
        self.rehandles = per_box
        self.assessed = dict((box, entry["charge_cents"]) for box, entry in per_box.items())

        units = p.applicable(p.equipment_rows, "equipment_id", aside=("retired",))
        self.equipment = {}
        for equipment_id in sorted(units):
            row = units[equipment_id]
            self.equipment[equipment_id] = {
                "equipment_id": equipment_id,
                "equipment_class": row["equipment_class"],
                "allowance": whole(row["move_limit"]),
                "base_minutes": whole(row["base_minutes"]),
                "used": 0,
                "closed": False,
            }
        self.equipment_exceptions = []
        for event in self.events:
            if event.get("movement_state") != "confirmed":
                continue
            confirmation = self.confirmation_of[event["order_id"]]
            equipment_id = confirmation.get("equipment_id")
            unit = self.equipment.get(equipment_id)
            if unit is None:
                self.equipment_exceptions.append({
                    "event_key": event["event_key"],
                    "order_id": event["order_id"],
                    "equipment_id": equipment_id,
                    "reason_code": "EQ_UNKNOWN_UNIT",
                })
                continue
            # RULE Y10.5. A unit that has carried exactly its allowance is
            # inside it; the movement that would take it one past is an
            # exception, and so are the movements after it.
            if unit["closed"] or unit["used"] + 1 > unit["allowance"]:
                unit["closed"] = True
                self.equipment_exceptions.append({
                    "event_key": event["event_key"],
                    "order_id": event["order_id"],
                    "equipment_id": equipment_id,
                    "reason_code": "EQ_BEYOND_ALLOWANCE",
                })
                continue
            unit["used"] += 1
        self.equipment_exceptions.sort(key=lambda r: r["event_key"])

    # -- Y11 ---------------------------------------------------------------

    def stage_y11_block_capacity(self):
        p = self.p
        self.capacity_rows = []
        for block_id in sorted(self.blocks):
            block = self.blocks[block_id]
            for ordinal in range(1, p.slot_count + 1):
                code = p.slot_code(ordinal)
                counts, credit_standing = self.slot_snapshot[ordinal]
                occupied = counts.get(block_id, 0)
                unusable = ((block_id, code) in self.sealed
                            or (block_id, code) in self.out_of_service
                            or block["slot_capacity"] == 0)
                if unusable:
                    self.capacity_rows.append({
                        "block_id": block_id, "slot_code": code,
                        "slot_capacity": block["slot_capacity"],
                        "occupied": occupied, "reserved": 0,
                        "unavailable": block["slot_capacity"], "available": 0,
                    })
                    continue
                free = max(0, block["slot_capacity"] - occupied)
                reserved = 0
                for credit in self._covering(block_id, ordinal):
                    reserved += credit_standing[credit["reservation_id"]]
                reserved = min(reserved, free)
                self.capacity_rows.append({
                    "block_id": block_id, "slot_code": code,
                    "slot_capacity": block["slot_capacity"],
                    "occupied": occupied, "reserved": reserved,
                    "unavailable": 0, "available": max(0, free - reserved),
                })

        self.slot_rows = []
        for ordinal in range(1, p.slot_count + 1):
            code = p.slot_code(ordinal)
            here = [e for e in self.events if e["slot_ordinal"] == ordinal]
            self.slot_rows.append({
                "slot_code": code,
                "events": len(here),
                "admitted": sum(1 for e in here if e["outcome"] == "admitted"),
                "set_aside": sum(1 for e in here if e["outcome"] == "set_aside"),
                "confirmed": sum(1 for e in here if e.get("movement_state") == "confirmed"),
            })
        stale = [e for e in self.events if e["slot_ordinal"] is None]
        self.slot_rows.append({
            "slot_code": ABSENT,
            "events": len(stale),
            "admitted": sum(1 for e in stale if e["outcome"] == "admitted"),
            "set_aside": sum(1 for e in stale if e["outcome"] == "set_aside"),
            "confirmed": sum(1 for e in stale if e.get("movement_state") == "confirmed"),
        })

    # -- Y12 ---------------------------------------------------------------

    ELIGIBILITY_ORDER = ["EL_NO_VESSEL", "EL_NO_OBLIGATION", "EL_HELD",
                         "EL_OFF_YARD", "EL_NO_CUTOFF", "EL_AFTER_CUTOFF"]

    def stage_y12_load_eligibility(self):
        p = self.p
        notices = {}
        for row in p.mine(p.cutoff_rows):
            if affirmative(row.get("superseded")):
                continue
            key = row["vessel_id"]
            if key not in notices or whole(row["notice_seq"]) > whole(notices[key]["notice_seq"]):
                notices[key] = row
        self.cutoff_notice = notices

        obligations = {}
        for row in p.stowage:
            obligations[(row["vessel_id"], row["box_id"])] = row

        self.ready_min = {}
        self.last_order = {}
        for event in self.events:
            if event["outcome"] == "admitted":
                self.ready_min[event["box_id"]] = whole(event["raised_min"])
                self.last_order[event["box_id"]] = event["order_id"]

        self.eligibility = []
        self.eligible_by_vessel = {}
        for box_id in sorted(self.box_record):
            record = self.dimensions[box_id]
            vessel_id = record["vessel_id"]
            call = self.obligation.get(vessel_id)
            obligation = obligations.get((vessel_id, box_id))
            notice = notices.get(vessel_id)
            ready = self.ready_min.get(box_id, 0)
            waived = self.last_order.get(box_id) in self.cutoff_waivers
            reason = "EL_OK"
            if call is None:
                reason = "EL_NO_VESSEL"
            elif obligation is None:
                reason = "EL_NO_OBLIGATION"
            elif affirmative(obligation.get("hold_flag")):
                reason = "EL_HELD"
            elif self.final_state[box_id]["state"] != "stacked":
                reason = "EL_OFF_YARD"
            elif notice is None:
                reason = "EL_NO_CUTOFF"
            elif not waived and ready > whole(notice["cutoff_min"]):
                reason = "EL_AFTER_CUTOFF"
            row = {
                "box_id": box_id,
                "vessel_id": vessel_id,
                "eligible": "yes" if reason == "EL_OK" else "no",
                "reason_code": reason,
                "ready_min": ready,
            }
            self.eligibility.append(row)
            if reason == "EL_OK":
                self.eligible_by_vessel.setdefault(vessel_id, []).append(obligation)

        self.cutoff_status = []
        for vessel_id in sorted(self.obligation):
            notice = notices.get(vessel_id)
            mine = [r for r in self.eligibility if r["vessel_id"] == vessel_id]
            outside = sum(1 for r in mine if r["reason_code"] == "EL_AFTER_CUTOFF")
            inside = len(mine) - outside
            self.cutoff_status.append({
                "vessel_id": vessel_id,
                "notice_id": notice["notice_id"] if notice else ABSENT,
                "cutoff_min": whole(notice["cutoff_min"]) if notice else 0,
                "boxes_total": len(mine),
                "boxes_inside": inside,
                "boxes_outside": outside,
            })

        self.manifest_rows = []
        for vessel_id in sorted(self.eligible_by_vessel):
            for obligation in sorted(self.eligible_by_vessel[vessel_id],
                                     key=lambda o: o["box_id"]):
                record = self.dimensions[obligation["box_id"]]
                self.manifest_rows.append({
                    "vessel_id": vessel_id,
                    "box_id": obligation["box_id"],
                    "class_rank": p.class_rank.get(record["box_class"], 0),
                    "stow_sequence": whole(obligation["stow_sequence"]),
                    "bay_no": whole(obligation["bay_no"]),
                    "teu_factor": record["teu_factor"],
                    "mass_kg": record["mass_kg"],
                })

    # -- Y13 ---------------------------------------------------------------

    def stage_y13_quay_ration(self):
        p = self.p
        demand = {}
        for row in p.demand_rows:
            if row.get("return_state") != "filed":
                continue
            key = (row["vessel_id"], row["slot_code"])
            if key not in demand or whole(row["revision_seq"]) > whole(demand[key]["revision_seq"]):
                demand[key] = row
        self.demand = dict((key, whole(row["declared_minutes"]))
                           for key, row in demand.items())

        windows = {}
        for row in p.window_rows:
            if affirmative(row.get("draft")):
                continue
            key = (row["berth_id"], row["slot_code"])
            if key not in windows or whole(row["revision_seq"]) > whole(windows[key]["revision_seq"]):
                windows[key] = row

        self.trace = []
        self.pairings = []
        self.vessel_share = dict((v, 0) for v in self.obligation)
        for code in p.slot_codes:
            for berth in sorted(p.berths):
                members = sorted(v for v, call in self.obligation.items()
                                 if call["berth_id"] == berth and (v, code) in self.demand)
                window = windows.get((berth, code))
                declared = whole(window["crane_minutes"]) if window else 0
                crewed = p.gang_minutes.get((berth, code), 0)
                pool = min(declared, crewed)
                share, passes = self._ration(code, berth, members, pool)
                self.trace.extend(passes)
                for member in members:
                    self.vessel_share[member] += share[member]
                self.pairings.append({
                    "slot_code": code, "berth_id": berth, "pool_minutes": pool,
                    "declared_minutes": declared, "crewed_minutes": crewed,
                    "vessel_count": len(members),
                    "rationed_minutes": sum(share.values()),
                })
        self._settle_load()

    def _ration_cells(self, members):
        """RULE Y13.5 d. Inside one pairing the berth is already fixed, so the
        cross classification of berth and service group reduces to the service
        group. The cells are walked in ascending key order."""
        grouped = {}
        for vessel_id in members:
            grouped.setdefault(self.obligation[vessel_id]["service_group"], []).append(vessel_id)
        return [grouped[key] for key in sorted(grouped)]

    def _ration_registers(self, code, members):
        """The two per vessel registers a pairing is rationed against: the
        admissible minutes of RULE Y13.4 and the applicable declared minutes of
        RULE Y13.2."""
        return (dict((v, Fraction(self.p.vessel_ceiling.get((v, code), 0))) for v in members),
                dict((v, Fraction(self.demand[(v, code)])) for v in members))

    def _ration_nudge(self, held, aim_whole):
        """RULE Y13.5 h. A damped move that rounded to no movement at all moves
        by the minimum step instead, and never past the aim."""
        if aim_whole > held:
            return min(held + self.p.minimum_step, aim_whole)
        return max(held - self.p.minimum_step, aim_whole)

    def _ration(self, code, berth, members, pool):
        """RULE Y13.5. The damped iterate, run for exactly the number of passes
        the memorandum budgets and rounded to whole crane minutes at the end of
        every one of them."""
        p = self.p
        admissible, wanted = self._ration_registers(code, members)
        cells = self._ration_cells(members)
        standing = dict((v, 0) for v in members)
        trace = []
        for pass_no in range(1, p.pass_budget + 1):
            offers = {}
            for vessel_id in members:
                outstanding = wanted[vessel_id] - Fraction(standing[vessel_id])
                offers[vessel_id] = {"appetite": outstanding if outstanding > 0 else Fraction(0)}
            hunger = sum(offer["appetite"] for offer in offers.values())
            spare = Fraction(pool) - sum(Fraction(standing[v]) for v in members)
            if hunger == 0 or spare <= 0:
                break
            for vessel_id, offer in offers.items():
                raw = Fraction(standing[vessel_id]) + spare * offer["appetite"] / hunger
                limit = admissible[vessel_id]
                trimmed = raw if raw < limit else limit
                offer["allowed"] = trimmed
                offer["surrendered"] = raw - trimmed
                offer["headroom"] = trimmed < limit
            gained = dict((v, Fraction(0)) for v in members)
            stranded = Fraction(0)
            for cell in cells:
                taken, unplaceable = redistribute_within_cell(cell, offers)
                gained.update(taken)
                stranded += unplaceable
            for vessel_id in sorted(members):
                reached = offers[vessel_id]["allowed"] + gained[vessel_id]
                limit = admissible[vessel_id]
                aim = reached if reached < limit else limit
                held = standing[vessel_id]
                damped = Fraction(held) + p.damping * (aim - Fraction(held))
                settled = quantise(damped)
                aim_whole = quantise(aim)
                if settled == held and held != aim_whole:
                    settled = self._ration_nudge(held, aim_whole)
                standing[vessel_id] = settled
            trace.append({
                "slot_code": code, "berth_id": berth, "pass_no": pass_no,
                "pool_minutes": pool, "unplaced_minutes": quantise(stranded),
                "shares": [{"vessel_id": v, "share_minutes": standing[v]}
                           for v in sorted(members)],
            })
        return dict(standing), trace

    def _settle_load(self):
        """RULE Y13.9 and Y13.10. A box costs its teu factor times the base
        minutes of the quay crane unit, and the load stops at the first box
        that would take the running total past the share."""
        p = self.p
        cranes = sorted((u for u in self.equipment.values()
                         if u["equipment_class"] == "quay_crane"),
                        key=lambda u: u["equipment_id"])
        self.minutes_per_teu = cranes[0]["base_minutes"] if cranes else 0

        self.load_ledger = []
        self.departures = []
        self.deferred = []
        self.loaded_boxes = 0
        for vessel_id in sorted(self.obligation):
            rows = [r for r in self.manifest_rows if r["vessel_id"] == vessel_id]
            ordered = sorted(rows, key=lambda r: tuple(
                r[key] if key != "box_id" else r["box_id"] for key in p.stowage_keys))
            share = self.vessel_share.get(vessel_id, 0)
            running = 0
            stopped = False
            boxes = []
            deferred_here = []
            for row in ordered:
                cost = row["teu_factor"] * self.minutes_per_teu
                if stopped or running + cost > share:
                    stopped = True
                    deferred_here.append((row, cost))
                    continue
                running += cost
                boxes.append({"load_position": len(boxes) + 1,
                              "box_id": row["box_id"], "load_minutes": cost})
            self.loaded_boxes += len(boxes)
            for row, cost in sorted(deferred_here, key=lambda pair: pair[0]["box_id"]):
                assessed = self.assessed.get(row["box_id"], 0)
                last_rung = self.p.surcharge_ladder[-1][1] if self.p.surcharge_ladder else 0
                self.deferred.append({
                    "vessel_id": vessel_id, "box_id": row["box_id"],
                    "load_minutes": cost, "assessed_cents": assessed,
                    "published_cents": assessed + last_rung,
                })
            self.load_ledger.append({
                "vessel_id": vessel_id, "share_minutes": share,
                "eligible_count": len(ordered), "loaded_count": len(boxes),
                "deferred_count": len(deferred_here), "loaded_minutes": running,
                "unused_minutes": share - running,
            })
            self.departures.append({
                "vessel_id": vessel_id,
                "berth_id": self.obligation[vessel_id]["berth_id"],
                "share_minutes": share, "loaded_minutes": running,
                "unused_minutes": share - running, "boxes": boxes,
            })

    # -- Y14 ---------------------------------------------------------------

    def stage_y14_terminal_accounts(self):
        """Every figure here is read off the ledgers the earlier stages
        published and none of it is derived a second time."""
        p = self.p
        admitted = [e for e in self.events if e["outcome"] == "admitted"]
        eligible = [r for r in self.eligibility if r["reason_code"] == "EL_OK"]
        self.totals = {
            "admitted_moves": len(admitted),
            "assessed_cents": sum(self.assessed.values()),
            "boxes_on_yard": sum(1 for s in self.final_state.values()
                                 if s["state"] == "stacked"),
            "canonical_events": len(self.events),
            "confirmed_moves": sum(1 for e in self.events
                                   if e.get("movement_state") == "confirmed"),
            "contradicted_moves": sum(1 for e in self.events
                                      if e.get("movement_state") == "contradicted"),
            "deferred_boxes": len(self.deferred),
            "eligible_boxes": len(eligible),
            "equipment_exceptions": len(self.equipment_exceptions),
            "loaded_boxes": self.loaded_boxes,
            "loaded_minutes": sum(r["loaded_minutes"] for r in self.load_ledger),
            "loose_confirmations": len(self.loose),
            "published_cents": sum(r["published_cents"] for r in self.deferred),
            "rationed_minutes": sum(r["rationed_minutes"] for r in self.pairings),
            "rehandle_moves": sum(e["rehandles"] for e in self.rehandles.values()),
            "set_aside_moves": sum(1 for e in self.events if e["outcome"] == "set_aside"),
        }

        loaded_ids = set()
        for departure in self.departures:
            loaded_ids |= set(b["box_id"] for b in departure["boxes"])
        deferred_ids = set(r["box_id"] for r in self.deferred)
        eligible_ids = set(r["box_id"] for r in eligible)
        moved_ids = set(row["box_id"] for row in self.history)
        on_yard_ids = set(box for box, state in self.final_state.items()
                          if state["state"] == "stacked")
        republished_ids = set(r["box_id"] for r in self.deferred)
        self.identities = [
            ("loaded_and_deferred_partition_eligible",
             "yes" if (loaded_ids | deferred_ids) == eligible_ids
                      and not (loaded_ids & deferred_ids) else "no"),
            ("moved_boxes_all_on_yard",
             "yes" if moved_ids <= on_yard_ids else "no"),
            ("decision_count_matches_events",
             "yes" if len(self.decisions) == len(self.events) else "no"),
            ("republished_covers_deferred",
             "yes" if republished_ids == deferred_ids else "no"),
        ]

        self.exception_summary = {}
        for row in p.mine(p.exception_rows):
            entry = self.exception_summary.setdefault(
                row["exception_kind"], {"granted": 0, "withdrawn": 0})
            if affirmative(row.get("withdrawn")):
                entry["withdrawn"] += 1
            else:
                entry["granted"] += 1

    def run(self):
        self.stage_y01_canonical_events()
        self.stage_y02_unit_normalisation()
        self.stage_y03_vessel_obligation()
        self.stage_y04_opening_yard()
        self.stage_y05_event_ordering()
        self.stage_y06_dependency_cycles()
        self.stage_y07_move_admission()
        self.stage_y08_yard_state()
        self.stage_y09_movement_reconciliation()
        self.stage_y10_rehandle_and_equipment()
        self.stage_y11_block_capacity()
        self.stage_y12_load_eligibility()
        self.stage_y13_quay_ration()
        self.stage_y14_terminal_accounts()
        return self


# ==========================================================================
# the publication
# ==========================================================================

CORE_DOCUMENTS = [
    "canonical_events.csv",
    "move_eligibility.csv",
    "yard_occupancy.psv",
    "yard_capacity.csv",
    "load_eligibility.csv",
    "terminal_reconciliation.csv",
]


def artifact_order(berths):
    spine = [
        "canonical_events.csv", "container_dimensions.csv", "vessel_obligation.csv",
        "initial_occupancy.psv", "event_order.csv", "cycle_break_report.json",
        "move_eligibility.csv", "yard_occupancy.psv", "movement_accounting.jsonl",
        "rehandle_ledger.jsonl", "yard_capacity.csv", "load_eligibility.csv",
        "ration_trace.jsonl", "terminal_reconciliation.csv",
        "publication_manifest.json",
    ]
    state = ["rejected_moves.tsv", "rejection_reasons.csv", "accepted_moves.csv",
             "container_state_history.psv", "container_state_final.csv",
             "dependency_order.csv"]
    yard = ["yard_reservations.psv", "block_utilization.csv", "equipment_usage.csv",
            "equipment_exceptions.tsv", "slot_accounting.csv"]
    vessel = ["vessel_cutoff_status.csv", "vessel_container_manifest.psv",
              "load_sequence_ledger.json", "deferred_containers.tsv",
              "departure_ledger.json", "vessel_reconciliation.xml",
              "exception_summary.tsv", "audit_trail.conf"]
    vessel += ["berth_report_%s.json" % berth for berth in sorted(berths)]
    vessel += ["daily_operational_summary.md", "final_control_totals.json"]
    return spine + state + yard + vessel


class Publication:
    """Every published document, written to the serialisation contract."""

    def __init__(self, shift: "Shift", out: Path):
        self.s = shift
        self.p = shift.p
        self.out = Path(out)

    # -- byte level ---------------------------------------------------------

    def _text(self, name, text):
        (self.out / name).write_bytes(text.encode("utf-8"))

    def _lines(self, name, lines):
        self._text(name, "".join(line + "\n" for line in lines))

    def _rows(self, name, header, rows, sep):
        body = [sep.join(header)]
        for row in rows:
            body.append(sep.join(ABSENT if value is None else str(value)
                                 for value in row))
        self._lines(name, body)

    def _json(self, name, payload):
        self._text(name, json.dumps(payload, indent=2) + "\n")

    def _jsonl(self, name, records):
        self._text(name, "".join(
            json.dumps(record, separators=(",", ":")) + "\n" for record in records))

    # -- the thirty nine ----------------------------------------------------

    def write_all(self):
        s, p = self.s, self.p
        self.out.mkdir(parents=True, exist_ok=True)

        self._rows("canonical_events.csv",
                   ["event_key", "order_id", "box_id", "source_system",
                    "source_priority", "event_seq", "raised_min", "slot_code",
                    "cluster_tag"],
                   [[e["event_key"], e["order_id"], e["box_id"], e["source_system"],
                     s.source_rank.get(e["source_system"], 0), whole(e["event_seq"]),
                     whole(e["raised_min"]), e["slot_code"], e["cluster_tag"]]
                    for e in s.events], ",")

        self._rows("container_dimensions.csv",
                   ["box_id", "iso_length", "teu_factor", "box_class", "vessel_id",
                    "mass_kg", "mass_state"],
                   [[d["box_id"], d["iso_length"], d["teu_factor"], d["box_class"],
                     d["vessel_id"], d["mass_kg"], d["mass_state"]]
                    for d in (s.dimensions[b] for b in sorted(s.dimensions))], ",")

        self._rows("vessel_obligation.csv",
                   ["vessel_id", "voyage", "berth_id", "service_group",
                    "destination", "voyage_sequence", "applicable_revision"],
                   [[o["vessel_id"], o["voyage"], o["berth_id"], o["service_group"],
                     o["destination"], o["voyage_sequence"], o["applicable_revision"]]
                    for o in (s.obligation[v] for v in sorted(s.obligation))], ",")

        self._rows("initial_occupancy.psv",
                   ["block_id", "zone", "rows", "tiers_max", "slot_capacity",
                    "opening_boxes", "opening_free"],
                   [[b["block_id"], b["zone"], b["rows"], b["tiers_max"],
                     b["slot_capacity"], s.opening_count.get(b["block_id"], 0),
                     max(0, b["slot_capacity"] - s.opening_count.get(b["block_id"], 0))]
                    for b in (s.blocks[k] for k in sorted(s.blocks))], "|")

        self._rows("event_order.csv",
                   ["event_key", "order_id", "slot_code", "source_priority",
                    "event_seq", "box_id"],
                   [[e["event_key"], e["order_id"], e["slot_code"],
                     s.source_rank.get(e["source_system"], 0), whole(e["event_seq"]),
                     e["box_id"]] for e in s.events], ",")

        self._json("cycle_break_report.json", {
            "shift_id": p.shift_id,
            "protection_depth": p.protection_depth,
            "component_count": len(s.cycle_entries),
            "components": s.cycle_entries,
        })

        self._rows("move_eligibility.csv",
                   ["event_key", "order_id", "box_id", "slot_code", "to_block",
                    "to_row", "to_tier", "outcome", "reason_code"],
                   [[e["event_key"], e["order_id"], e["box_id"], e["slot_code"],
                     e["to_block"], whole(e["to_row"]), whole(e["to_tier"]),
                     e["outcome"], e["reason_code"]] for e in s.events], ",")

        self._rows("yard_occupancy.psv",
                   ["block_id", "zone", "slot_capacity", "opening_boxes",
                    "closing_boxes", "closing_free"],
                   [[b["block_id"], b["zone"], b["slot_capacity"],
                     s.opening_count.get(b["block_id"], 0),
                     s.closing_boxes.get(b["block_id"], 0),
                     max(0, b["slot_capacity"] - s.closing_boxes.get(b["block_id"], 0))]
                    for b in (s.blocks[k] for k in sorted(s.blocks))], "|")

        self._jsonl("movement_accounting.jsonl", s.movements)

        self._jsonl("rehandle_ledger.jsonl",
                    [s.rehandles[b] for b in sorted(s.rehandles)])

        self._rows("yard_capacity.csv",
                   ["block_id", "slot_code", "slot_capacity", "occupied",
                    "reserved", "unavailable", "available"],
                   [[r["block_id"], r["slot_code"], r["slot_capacity"], r["occupied"],
                     r["reserved"], r["unavailable"], r["available"]]
                    for r in s.capacity_rows], ",")

        self._rows("load_eligibility.csv",
                   ["box_id", "vessel_id", "eligible", "reason_code", "ready_min"],
                   [[r["box_id"], r["vessel_id"], r["eligible"], r["reason_code"],
                     r["ready_min"]] for r in s.eligibility], ",")

        self._jsonl("ration_trace.jsonl", s.trace)

        self._rows("terminal_reconciliation.csv", ["measure", "value"],
                   [[name, s.totals[name]] for name in sorted(s.totals)], ",")

        # --- state family --------------------------------------------------

        self._rows("rejected_moves.tsv",
                   ["event_key", "order_id", "box_id", "slot_code", "reason_code"],
                   [[e["event_key"], e["order_id"], e["box_id"], e["slot_code"],
                     e["reason_code"]] for e in s.events
                    if e["outcome"] == "set_aside"], "\t")

        self._rows("rejection_reasons.csv", ["reason_code", "order_count"],
                   [[rung, s.reason_counts.get(rung, 0)] for rung in p.rungs], ",")

        self._rows("accepted_moves.csv",
                   ["event_key", "order_id", "box_id", "slot_code", "to_block",
                    "to_row", "to_tier"],
                   [[e["event_key"], e["order_id"], e["box_id"], e["slot_code"],
                     e["to_block"], whole(e["to_row"]), whole(e["to_tier"])]
                    for e in s.events if e["outcome"] == "admitted"], ",")

        self._rows("container_state_history.psv",
                   ["box_id", "event_key", "from_block", "from_row", "from_tier",
                    "to_block", "to_row", "to_tier", "was_stacked"],
                   [[r["box_id"], r["event_key"], r["from_block"], r["from_row"],
                     r["from_tier"], r["to_block"], r["to_row"], r["to_tier"],
                     r["was_stacked"]]
                    for r in sorted(s.history, key=lambda r: r["event_key"])], "|")

        self._rows("container_state_final.csv",
                   ["box_id", "block_id", "row_no", "tier_no", "moves_applied",
                    "state"],
                   [[f["box_id"], f["block_id"], f["row_no"], f["tier_no"],
                     f["moves_applied"], f["state"]]
                    for f in (s.final_state[b] for b in sorted(s.final_state))], ",")

        self._rows("dependency_order.csv", ["position", "order_id", "event_key"],
                   [[position, order_id, s.event_of[order_id]["event_key"]]
                    for position, order_id in enumerate(s.dependency_order, start=1)],
                   ",")

        # --- yard family ---------------------------------------------------

        self._rows("yard_reservations.psv",
                   ["reservation_id", "block_id", "service_group", "first_slot",
                    "last_slot", "asked", "withheld", "consumed", "unmet"],
                   [[c["reservation_id"], c["block_id"], c["service_group"],
                     c["first_slot"], c["last_slot"], c["asked"], c["withheld"],
                     c["consumed"], c["unmet"]] for c in s.credits], "|")

        self._rows("block_utilization.csv",
                   ["block_id", "slot_capacity", "closing_boxes", "utilisation_ratio"],
                   [[b["block_id"], b["slot_capacity"],
                     s.closing_boxes.get(b["block_id"], 0),
                     ratio_at_nine(s.closing_boxes.get(b["block_id"], 0),
                                   b["slot_capacity"])]
                    for b in (s.blocks[k] for k in sorted(s.blocks))], ",")

        self._rows("equipment_usage.csv",
                   ["equipment_id", "equipment_class", "allowance", "used",
                    "minutes", "within_allowance"],
                   [[u["equipment_id"], u["equipment_class"], u["allowance"],
                     u["used"], u["used"] * u["base_minutes"],
                     "yes" if u["used"] <= u["allowance"] else "no"]
                    for u in (s.equipment[k] for k in sorted(s.equipment))], ",")

        self._rows("equipment_exceptions.tsv",
                   ["event_key", "order_id", "equipment_id", "reason_code"],
                   [[r["event_key"], r["order_id"], r["equipment_id"],
                     r["reason_code"]] for r in s.equipment_exceptions], "\t")

        self._rows("slot_accounting.csv",
                   ["slot_code", "events", "admitted", "set_aside", "confirmed"],
                   [[r["slot_code"], r["events"], r["admitted"], r["set_aside"],
                     r["confirmed"]] for r in s.slot_rows], ",")

        # --- vessel family --------------------------------------------------

        self._rows("vessel_cutoff_status.csv",
                   ["vessel_id", "notice_id", "cutoff_min", "boxes_total",
                    "boxes_inside", "boxes_outside"],
                   [[r["vessel_id"], r["notice_id"], r["cutoff_min"],
                     r["boxes_total"], r["boxes_inside"], r["boxes_outside"]]
                    for r in s.cutoff_status], ",")

        self._rows("vessel_container_manifest.psv",
                   ["vessel_id", "box_id", "class_rank", "stow_sequence", "bay_no",
                    "teu_factor", "mass_kg"],
                   [[r["vessel_id"], r["box_id"], r["class_rank"], r["stow_sequence"],
                     r["bay_no"], r["teu_factor"], r["mass_kg"]]
                    for r in s.manifest_rows], "|")

        self._json("load_sequence_ledger.json", {
            "shift_id": p.shift_id,
            "minutes_per_teu": s.minutes_per_teu,
            "stowage_keys": p.stowage_keys,
            "vessels": s.load_ledger,
        })

        self._rows("deferred_containers.tsv",
                   ["vessel_id", "box_id", "load_minutes", "assessed_cents",
                    "published_cents"],
                   [[r["vessel_id"], r["box_id"], r["load_minutes"],
                     r["assessed_cents"], r["published_cents"]] for r in s.deferred],
                   "\t")

        self._json("departure_ledger.json", {
            "shift_id": p.shift_id,
            "vessels": s.departures,
        })

        self._write_reconciliation_xml()

        self._rows("exception_summary.tsv", ["exception_kind", "granted", "withdrawn"],
                   [[kind, s.exception_summary[kind]["granted"],
                     s.exception_summary[kind]["withdrawn"]]
                    for kind in sorted(s.exception_summary)], "\t")

        self._write_audit_trail()
        self._write_berth_reports()
        self._write_summary()

        self._json("final_control_totals.json", {
            "shift_id": p.shift_id,
            "live_sheet_name": p.live_sheet_name,
            "minutes_per_teu": s.minutes_per_teu,
            "totals": dict((name, s.totals[name]) for name in sorted(s.totals)),
            "identities": dict(s.identities),
        })

        self._write_manifest()

    # -- the shaped documents ------------------------------------------------

    def _write_reconciliation_xml(self):
        s, p = self.s, self.p
        lines = ['<?xml version="1.0" encoding="utf-8"?>',
                 "<vessel_reconciliation>",
                 "  <shift_id>%s</shift_id>" % xml_text(p.shift_id),
                 "  <vessels>"]
        ledger = dict((r["vessel_id"], r) for r in s.load_ledger)
        for vessel_id in sorted(s.obligation):
            row = ledger[vessel_id]
            lines.append('    <vessel id="%s">' % xml_text(vessel_id))
            lines.append("      <berth_id>%s</berth_id>"
                         % xml_text(s.obligation[vessel_id]["berth_id"]))
            lines.append("      <eligible_count>%d</eligible_count>" % row["eligible_count"])
            lines.append("      <loaded_count>%d</loaded_count>" % row["loaded_count"])
            lines.append("      <deferred_count>%d</deferred_count>" % row["deferred_count"])
            lines.append("      <share_minutes>%d</share_minutes>" % row["share_minutes"])
            lines.append("    </vessel>")
        lines.append("  </vessels>")
        for name, verdict in s.identities:
            lines.append('  <identity name="%s">%s</identity>'
                         % (xml_text(name), xml_text(verdict)))
        lines.append("</vessel_reconciliation>")
        self._lines("vessel_reconciliation.xml", lines)

    def _write_audit_trail(self):
        s, p = self.s, self.p
        lines = ["# The audit trail of one shift.", "[shift]",
                 "shift_id = %s" % p.shift_id,
                 "live_sheet_name = %s" % p.live_sheet_name,
                 "reference = %s" % p.reference,
                 "", "[counts]"]
        for name in sorted(s.totals):
            lines.append("%s = %d" % (name, s.totals[name]))
        lines += ["", "[ladder]"]
        for rung in p.rungs:
            lines.append("%s = %d" % (rung, s.reason_counts.get(rung, 0)))
        lines += ["", "[movement]"]
        present = {}
        for event in s.events:
            state = event.get("movement_state")
            if state:
                present[state] = present.get(state, 0) + 1
        for state in sorted(present):
            lines.append("%s = %d" % (state, present[state]))
        self._lines("audit_trail.conf", lines)

    def _write_berth_reports(self):
        s, p = self.s, self.p
        for berth in sorted(p.berths):
            pairings = [r for r in s.pairings if r["berth_id"] == berth]
            here = sorted(v for v, call in s.obligation.items()
                          if call["berth_id"] == berth)
            self._json("berth_report_%s.json" % berth, {
                "shift_id": p.shift_id,
                "berth_id": berth,
                "vessel_count": len(here),
                "vessels": here,
                "pool_minutes": sum(r["pool_minutes"] for r in pairings),
                "rationed_minutes": sum(r["rationed_minutes"] for r in pairings),
                "pairings": pairings,
            })

    def _write_summary(self):
        s, p = self.s, self.p
        lines = ["# Daily operational summary", "",
                 "shift %s at reference %s" % (p.shift_id, p.reference), ""]
        for name in sorted(s.totals):
            lines.append("- %s: %d" % (name, s.totals[name]))
        lines += ["", "## Ladder", ""]
        for rung in p.rungs:
            lines.append("- %s: %d" % (rung, s.reason_counts.get(rung, 0)))
        lines += ["", "## Identity checks", ""]
        for name, verdict in s.identities:
            lines.append("- %s: %s" % (name, verdict))
        self._lines("daily_operational_summary.md", lines)

    def _write_manifest(self):
        """RULE Y14.4. The digests are taken last, over lines of document name,
        one space and the document digest, in the artifact order."""
        p = self.p
        names = artifact_order(p.berths)
        entries = []
        for name in names:
            if name == "publication_manifest.json":
                continue
            payload = (self.out / name).read_bytes()
            entries.append({"name": name,
                            "sha256": hashlib.sha256(payload).hexdigest(),
                            "bytes": len(payload)})
        core = b""
        rest = b""
        for entry in entries:
            line = ("%s %s\n" % (entry["name"], entry["sha256"])).encode("utf-8")
            if entry["name"] in CORE_DOCUMENTS:
                core += line
            else:
                rest += line
        self._json("publication_manifest.json", {
            "shift_id": p.shift_id,
            "core_digest": hashlib.sha256(core).hexdigest(),
            "publication_digest": hashlib.sha256(rest).hexdigest(),
            "document_count": len(entries) + 1,
            "documents": entries,
        })


def xml_text(value) -> str:
    return (str(value).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;"))


# ==========================================================================
# entry point
# ==========================================================================


def main(argv):
    data_dir = None
    out_dir = None
    position = 0
    while position < len(argv):
        token = argv[position]
        if token == "--data" and position + 1 < len(argv):
            data_dir = argv[position + 1]
            position += 2
        elif token == "--out" and position + 1 < len(argv):
            out_dir = argv[position + 1]
            position += 2
        else:
            position += 1
    if data_dir is None or out_dir is None:
        raise SystemExit("--data and --out are both required")

    papers = Papers(Path(data_dir))
    shift = Shift(papers).run()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    Publication(shift, out).write_all()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
