#!/usr/bin/env python3
"""Recompute one operating shift of the Kestrel Point container terminal.

The fourteen stages of terminal_contract_overview.md appear below as fourteen
separately named steps, worked in that order.  Every identifier, control value,
threshold, boundary and rung code is read from the input directory.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from fractions import Fraction

# ---------------------------------------------------------------------------
# exact arithmetic and published forms
# ---------------------------------------------------------------------------


def half_up(value):
    """Round a Fraction to an integer, a half residue going away from zero."""
    if value >= 0:
        return (2 * value.numerator + value.denominator) // (2 * value.denominator)
    return -((-2 * value.numerator + value.denominator) // (2 * value.denominator))


def fmt_int(value):
    n = int(value)
    return "0" if n == 0 else str(n)


def fmt_ratio(value, places):
    scale = 10 ** places
    scaled = half_up(Fraction(value) * scale)
    sign = "-" if scaled < 0 else ""
    scaled = abs(scaled)
    whole, frac = divmod(scaled, scale)
    if whole == 0 and frac == 0:
        sign = ""
    return "%s%d.%0*d" % (sign, whole, places, frac)


# ---------------------------------------------------------------------------
# plain text papers
# ---------------------------------------------------------------------------


class Papers:
    """Everything the input directory carries, read once."""

    def __init__(self, data_dir):
        self.dir = data_dir

    def path(self, name):
        return os.path.join(self.dir, name)

    def text(self, name):
        with open(self.path(name), "r", encoding="utf-8") as handle:
            return handle.read()

    def delim(self, name, sep):
        with open(self.path(name), "r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle, delimiter=sep))

    def jsonl(self, name):
        rows = []
        for line in self.text(name).splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def scalars(self, name):
        """key/value pairs of a yaml, toml or conf paper, flat and unquoted."""
        found = {}
        for line in self.text(name).splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("["):
                continue
            match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*[:=]\s*(.+)$', line)
            if not match:
                continue
            value = match.group(2).strip()
            if value in ('>-', '|', '"""', '', '>'):
                continue
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            found.setdefault(match.group(1), value)
        return found


# ---------------------------------------------------------------------------
# the workbook
# ---------------------------------------------------------------------------

SSML = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
PKGREL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
DOCREL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
WORDML = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _column_of(ref):
    return re.match(r'^([A-Z]+)', ref).group(1)


def _row_of(ref):
    return int(re.match(r'^[A-Z]+(\d+)', ref).group(1))


def read_workbook(path):
    """Return [(sheet_name, {row_number: {column_letter: text}})] in book order."""
    with zipfile.ZipFile(path) as book:
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            for item in root.findall(SSML + "si"):
                shared.append("".join(t.text or "" for t in item.iter(SSML + "t")))
        rels = {}
        root = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        for rel in root.findall(PKGREL + "Relationship"):
            target = rel.get("Target")
            if not target.startswith("/"):
                target = "xl/" + target.lstrip("./")
            rels[rel.get("Id")] = target
        sheets = []
        root = ET.fromstring(book.read("xl/workbook.xml"))
        for sheet in root.find(SSML + "sheets").findall(SSML + "sheet"):
            sheets.append((sheet.get("name"), rels[sheet.get(DOCREL + "id")]))
        out = []
        for name, target in sheets:
            grid = {}
            root = ET.fromstring(book.read(target))
            for row in root.iter(SSML + "row"):
                cells = {}
                number = None
                for cell in row.findall(SSML + "c"):
                    kind = cell.get("t")
                    if kind == "inlineStr":
                        inline = cell.find(SSML + "is")
                        text = "".join(t.text or "" for t in inline.iter(SSML + "t"))
                    else:
                        value = cell.find(SSML + "v")
                        text = value.text if value is not None else ""
                        if kind == "s":
                            text = shared[int(text)]
                    cells[_column_of(cell.get("r"))] = text
                    if number is None:
                        number = _row_of(cell.get("r"))
                if cells:
                    if row.get("r") and row.get("r").isdigit():
                        number = int(row.get("r"))
                    grid[number] = cells
            out.append((name, grid))
    return out


def sheet_table(grid, labels):
    """Rows of the table whose header row carries every one of labels."""
    numbers = sorted(grid)
    for index, number in enumerate(numbers):
        header = grid[number]
        placed = {}
        for column, text in header.items():
            if text in labels:
                placed[text] = column
        if len(placed) != len(labels):
            continue
        first = placed[labels[0]]
        rows = []
        expected = number + 1
        for follower in numbers[index + 1:]:
            if follower != expected:
                break
            expected += 1
            cells = grid[follower]
            if not cells.get(first):
                break
            rows.append({label: cells.get(column, "") for label, column in placed.items()})
        return rows
    return []


# ---------------------------------------------------------------------------
# the memorandum
# ---------------------------------------------------------------------------


def read_pdf_lines(path):
    with open(path, "rb") as handle:
        raw = handle.read().decode("latin-1")
    lines = []
    for chunk in re.findall(r'\((.*?)\)\s*Tj', raw, re.S):
        text = chunk.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
        lines.append(text)
    return lines


def pdf_scalars(lines):
    found = {}
    for line in lines:
        tokens = line.split()
        if len(tokens) >= 2 and re.match(r'^[a-z][a-z0-9_]*$', tokens[0]):
            if re.match(r'^-?\d+$', tokens[1]):
                found.setdefault(tokens[0], int(tokens[1]))
    return found


def pdf_table(lines, labels):
    width = len(labels)
    for index, line in enumerate(lines):
        if [t for t in line.split()] != list(labels):
            continue
        rows = []
        for follower in lines[index + 1:]:
            tokens = follower.split()
            if len(tokens) != width:
                break
            rows.append(dict(zip(labels, tokens)))
        return rows
    return []


# ---------------------------------------------------------------------------
# the directive
# ---------------------------------------------------------------------------


def read_docx_tables(path):
    with zipfile.ZipFile(path) as doc:
        root = ET.fromstring(doc.read("word/document.xml"))
    tables = []
    for table in root.iter(WORDML + "tbl"):
        grid = []
        for row in table.findall(WORDML + "tr"):
            cells = []
            for cell in row.findall(WORDML + "tc"):
                cells.append("".join(t.text or "" for t in cell.iter(WORDML + "t")))
            grid.append(cells)
        if len(grid) > 1:
            head = grid[0]
            tables.append([dict(zip(head, body)) for body in grid[1:]])
    return tables


def docx_table(tables, labels):
    for table in tables:
        if table and all(label in table[0] for label in labels):
            return table
    return []


# ---------------------------------------------------------------------------
# the publication
# ---------------------------------------------------------------------------


class Publication:
    def __init__(self):
        self.docs = {}

    def delimited(self, name, sep, header, rows):
        lines = [sep.join(header)]
        for row in rows:
            lines.append(sep.join(str(cell) for cell in row))
        self.docs[name] = ("\n".join(lines) + "\n").encode("utf-8")

    def jsonlines(self, name, records):
        if not records:
            self.docs[name] = b""
            return
        out = []
        for record in records:
            out.append(json.dumps(record, separators=(",", ":")))
        self.docs[name] = ("\n".join(out) + "\n").encode("utf-8")

    def jsondoc(self, name, payload):
        self.docs[name] = (json.dumps(payload, indent=2) + "\n").encode("utf-8")

    def plain(self, name, text):
        self.docs[name] = text.encode("utf-8")


def xml_escape(text):
    text = str(text)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return text.replace('"', "&quot;").replace("'", "&apos;")


# ---------------------------------------------------------------------------
# shared reading of the registers
# ---------------------------------------------------------------------------


def applicable(rows, subject_keys, set_aside_flags, seq_key="revision_seq"):
    """revision_precedence.toml: highest surviving revision_seq per subject."""
    best = {}
    for row in rows:
        if any(row.get(flag, "no") == "yes" for flag in set_aside_flags):
            continue
        key = tuple(row[field] for field in subject_keys)
        seq = int(row[seq_key])
        if key not in best or seq > int(best[key][seq_key]):
            best[key] = row
    return best


class Shift:
    """The state the stages build up, in the order they build it."""

    def __init__(self, papers):
        self.papers = papers
        self.pub = Publication()


def load_context(papers):
    shift = Shift(papers)

    topology = ET.fromstring(papers.text("yard_topology.xml"))
    shift.shift_id = topology.find("shift").text.strip()
    shift.reference = topology.find("reference").text.strip()
    shift.blocks_in_force = []
    shift.block_zone_topology = {}
    for block in topology.find("blocks").findall("block"):
        if block.get("in_force") == "yes":
            shift.blocks_in_force.append(block.get("id"))
            shift.block_zone_topology[block.get("id")] = block.get("zone")
    shift.blocks_in_force.sort()

    boundaries = papers.scalars("boundary_conventions.yaml")
    shift.slot_length = int(boundaries["slot_length_minutes"])
    shift.slot_count = int(boundaries["slot_count"])
    shift.marker = papers.scalars("unit_register_dictionary.toml")["marker"]

    roster = papers.scalars("berth_reporting_roster.conf")
    shift.reporting_berths = sorted(
        part.strip() for part in roster["reporting_berths"].split(",") if part.strip()
    )

    grid = papers.delim("slot_grid_calendar.csv", ",")
    shift.slot_codes = sorted({row["slot_code"] for row in grid})
    shift.slot_ordinal = {code: n + 1 for n, code in enumerate(shift.slot_codes)}
    shift.slot_grid = {(row["slot_code"], row["block_id"]): row for row in grid}

    # the admission ladder, in the order the paper prints it
    shift.rungs = []
    for line in papers.text("move_admission_ladder.txt").splitlines():
        match = re.match(r'^rung\s+\d+\s+(\S+)\s*$', line.strip())
        if match:
            shift.rungs.append({"code": match.group(1), "words": ""})
            continue
        if shift.rungs and line.startswith(" ") and line.strip() and not line.startswith("rung"):
            if not shift.rungs[-1]["words"]:
                shift.rungs[-1]["words"] = line.strip()
    shift.rung_codes = [rung["code"] for rung in shift.rungs]
    shift.rung_tests = []
    for rung in shift.rungs:
        words = rung["words"].lower()
        if "master register" in words:
            kind = "unknown_box"
        elif "sealed" in words:
            kind = "sealed"
        elif "closed" in words:
            kind = "stale"
        elif "tier" in words:
            kind = "tier"
        elif "reserved" in words:
            kind = "reserved"
        else:
            kind = "duplicate"
        shift.rung_tests.append(kind)

    # the live workbook sheet, chosen by its key cell against the shift reference
    sheets = read_workbook(papers.path("quay_capacity_workbook.xlsx"))
    live = None
    for name, sheet in sheets:
        if not sheet:
            continue
        cells = sheet[min(sheet)]
        columns = sorted(cells)
        if len(columns) > 1 and cells[columns[1]] == shift.reference:
            live = (name, sheet)
            break
    shift.live_sheet_name, live_sheet = live

    controls = {}
    for row in sheet_table(live_sheet, ["control_name", "numerator", "denominator", "unit"]):
        controls[row["control_name"]] = Fraction(
            int(row["numerator"]), int(row["denominator"])
        )

    def control(fragment):
        for name, value in controls.items():
            if fragment in name:
                return value
        raise KeyError(fragment)

    shift.damping = control("damping")
    shift.decitonne_kg = control("decitonne")
    shift.centner_kg = control("centner")
    shift.base_move_charge = int(control("base_move_charge"))
    shift.teu_factors = {}
    for row in sheet_table(live_sheet, ["iso_length", "teu_factor"]):
        shift.teu_factors[row["iso_length"]] = int(row["teu_factor"])
    shift.vessel_slot_ceiling = {}
    for row in sheet_table(live_sheet, ["vessel_id", "slot_code", "admissible_minutes"]):
        shift.vessel_slot_ceiling[(row["vessel_id"], row["slot_code"])] = int(
            row["admissible_minutes"]
        )

    # the memorandum
    memo = read_pdf_lines(papers.path("berth_operations_memo.pdf"))
    memo_values = pdf_scalars(memo)

    def memo_value(fragment):
        for name, value in memo_values.items():
            if fragment in name:
                return value
        raise KeyError(fragment)

    shift.pass_budget = memo_value("pass_budget")
    shift.minimum_step = memo_value("minimum_step")
    shift.protection_depth = memo_value("protection_depth")
    shift.surcharge_ladder = []
    for row in pdf_table(memo, ["tier_depth", "surcharge_cents"]):
        shift.surcharge_ladder.append((int(row["tier_depth"]), int(row["surcharge_cents"])))
    shift.surcharge_ladder.sort()
    shift.gang_minutes = {}
    for row in pdf_table(memo, ["berth_id", "slot_code", "gang_code", "gang_minutes"]):
        key = (row["berth_id"], row["slot_code"])
        shift.gang_minutes[key] = shift.gang_minutes.get(key, 0) + int(row["gang_minutes"])

    # the directive
    tables = read_docx_tables(papers.path("stowage_ordering_directive.docx"))
    keys = docx_table(tables, ["key_position", "key_name"])
    shift.stowage_keys = [
        row["key_name"] for row in sorted(keys, key=lambda r: int(r["key_position"]))
    ]
    shift.class_rank = {}
    for row in docx_table(tables, ["box_class", "class_rank"]):
        shift.class_rank[row["box_class"]] = int(row["class_rank"])

    return shift


def surcharge_of(shift, depth):
    found = 0
    for rung_depth, cents in shift.surcharge_ladder:
        if rung_depth <= depth:
            found = cents
    return found


def last_rung_surcharge(shift):
    return shift.surcharge_ladder[-1][1] if shift.surcharge_ladder else 0


# ---------------------------------------------------------------------------
# Y01  Canonical event set
# ---------------------------------------------------------------------------


def step_y01_canonical_events(shift):
    papers = shift.papers
    withdrawn = set()
    for row in papers.delim("withdrawn_order_journal.tsv", "\t"):
        if row["shift_id"] == shift.shift_id and row["state"] == "withdrawn":
            withdrawn.add(row["order_id"])

    last_close = shift.slot_length * shift.slot_count
    events = []
    for row in papers.delim("move_order_journal.csv", ","):
        if row["order_id"] in withdrawn:
            continue
        raised = int(row["raised_min"])
        if raised > last_close:
            ordinal = None
        elif raised <= 0:
            ordinal = 1
        else:
            ordinal = -(-raised // shift.slot_length)
        event = {
            "order_id": row["order_id"],
            "box_id": row["box_id"],
            "source_system": row["source_system"],
            "event_seq": int(row["event_seq"]),
            "raised_min": raised,
            "to_block": row["to_block"],
            "to_row": row["to_row"],
            "to_tier": row["to_tier"],
            "cluster_tag": row["cluster_tag"],
            "slot_ordinal": ordinal,
            "slot_code": shift.slot_codes[ordinal - 1] if ordinal else shift.marker,
        }
        events.append(event)
    shift.events = events
    shift.withdrawn_orders = withdrawn


# ---------------------------------------------------------------------------
# Y02  Unit normalisation
# ---------------------------------------------------------------------------


def step_y02_unit_normalisation(shift):
    papers = shift.papers
    rows = [
        row
        for row in papers.delim("box_master_register.csv", ",")
        if row["shift_id"] == shift.shift_id
    ]
    master = applicable(rows, ["box_id"], ["retired"])
    shift.boxes = {key[0]: row for key, row in master.items()}

    filed = [
        row
        for row in papers.delim("mass_declaration_returns.psv", "|")
        if row["state"] == "filed"
    ]
    declarations = applicable(filed, ["box_id"], [], seq_key="declaration_seq")

    registers = {"kg": Fraction(1), "dt": shift.decitonne_kg, "ct": shift.centner_kg}

    shift.dimensions = {}
    for box_id, row in sorted(shift.boxes.items()):
        length_text = row["iso_length"]
        bare = re.sub(r'(?i)ft$', "", length_text).strip()
        teu = shift.teu_factors.get(bare, 0)
        declaration = declarations.get((box_id,))
        if declaration is None or declaration["mass_value"] == shift.marker:
            mass_state = "not_declared"
            mass_kg = 0
        else:
            mass_state = "declared"
            factor = registers[declaration["mass_unit"]]
            mass_kg = half_up(Fraction(int(declaration["mass_value"])) * factor)
        shift.dimensions[box_id] = {
            "box_id": box_id,
            "iso_length": int(bare),
            "teu_factor": teu,
            "box_class": row["box_class"],
            "vessel_id": row["vessel_id"],
            "mass_kg": mass_kg,
            "mass_state": mass_state,
        }

    shift.pub.delimited(
        "container_dimensions.csv",
        ",",
        ["box_id", "iso_length", "teu_factor", "box_class", "vessel_id", "mass_kg", "mass_state"],
        [
            [
                box["box_id"],
                fmt_int(box["iso_length"]),
                fmt_int(box["teu_factor"]),
                box["box_class"],
                box["vessel_id"],
                fmt_int(box["mass_kg"]),
                box["mass_state"],
            ]
            for box in (shift.dimensions[key] for key in sorted(shift.dimensions))
        ],
    )


# ---------------------------------------------------------------------------
# Y03  Vessel obligation state
# ---------------------------------------------------------------------------


def step_y03_vessel_obligation(shift):
    papers = shift.papers
    rows = [
        row
        for row in papers.delim("vessel_call_register.csv", ",")
        if row["shift_id"] == shift.shift_id
    ]
    calls = applicable(rows, ["vessel_id"], ["withdrawn"])
    shift.vessels = {key[0]: row for key, row in calls.items()}

    shift.pub.delimited(
        "vessel_obligation.csv",
        ",",
        [
            "vessel_id",
            "voyage",
            "berth_id",
            "service_group",
            "destination",
            "voyage_sequence",
            "applicable_revision",
        ],
        [
            [
                vessel_id,
                call["voyage"],
                call["berth_id"],
                call["service_group"],
                call["destination"],
                fmt_int(call["voyage_sequence"]),
                fmt_int(call["revision_seq"]),
            ]
            for vessel_id, call in sorted(shift.vessels.items())
        ],
    )

    def group_of(box_id):
        box = shift.dimensions.get(box_id)
        if box is None:
            return shift.marker
        call = shift.vessels.get(box["vessel_id"])
        return call["service_group"] if call else shift.marker

    shift.service_group_of_box = group_of


# ---------------------------------------------------------------------------
# Y04  The opening yard
# ---------------------------------------------------------------------------


def step_y04_opening_yard(shift):
    papers = shift.papers
    rows = [
        row
        for row in papers.delim("block_geometry_register.csv", ",")
        if row["shift_id"] == shift.shift_id and row["block_id"] in shift.block_zone_topology
    ]
    geometry = applicable(rows, ["block_id"], ["retired", "future"])

    shift.geometry = {}
    for block_id in shift.blocks_in_force:
        row = geometry.get((block_id,))
        if row is None:
            shift.geometry[block_id] = {
                "zone": shift.block_zone_topology[block_id],
                "rows": 0,
                "tiers_max": 0,
                "capacity": 0,
            }
        else:
            rows_n = int(row["rows"])
            tiers = int(row["tiers_max"])
            shift.geometry[block_id] = {
                "zone": row["zone"],
                "rows": rows_n,
                "tiers_max": tiers,
                "capacity": rows_n * tiers,
            }

    shift.opening_position = {}
    for row in papers.delim("stack_inventory_snapshot.csv", ","):
        if row["stack_state"] != "stacked":
            continue
        if row["block_id"] not in shift.geometry:
            continue
        if row["box_id"] not in shift.boxes:
            continue
        shift.opening_position[row["box_id"]] = {
            "block_id": row["block_id"],
            "row_no": int(row["row_no"]),
            "tier_no": int(row["tier_no"]),
        }

    shift.opening_boxes = {block_id: 0 for block_id in shift.blocks_in_force}
    for position in shift.opening_position.values():
        shift.opening_boxes[position["block_id"]] += 1

    shift.opening_free = {}
    for block_id in shift.blocks_in_force:
        capacity = shift.geometry[block_id]["capacity"]
        shift.opening_free[block_id] = capacity - shift.opening_boxes[block_id]

    shift.pub.delimited(
        "initial_occupancy.psv",
        "|",
        ["block_id", "zone", "rows", "tiers_max", "slot_capacity", "opening_boxes", "opening_free"],
        [
            [
                block_id,
                shift.geometry[block_id]["zone"],
                fmt_int(shift.geometry[block_id]["rows"]),
                fmt_int(shift.geometry[block_id]["tiers_max"]),
                fmt_int(shift.geometry[block_id]["capacity"]),
                fmt_int(shift.opening_boxes[block_id]),
                fmt_int(shift.opening_free[block_id]),
            ]
            for block_id in shift.blocks_in_force
        ],
    )


# ---------------------------------------------------------------------------
# Y05  Canonical event order
# ---------------------------------------------------------------------------


def step_y05_event_ordering(shift):
    papers = shift.papers
    rows = [
        row
        for row in papers.delim("source_priority_register.csv", ",")
        if row["shift_id"] == shift.shift_id
    ]
    ranks = applicable(rows, ["source_system"], ["retired"])
    shift.source_rank = {key[0]: int(row["priority_rank"]) for key, row in ranks.items()}

    beyond = shift.slot_count + 1
    for event in shift.events:
        event["source_priority"] = shift.source_rank[event["source_system"]]

    shift.events.sort(
        key=lambda event: (
            event["slot_ordinal"] if event["slot_ordinal"] else beyond,
            event["source_priority"],
            event["event_seq"],
            event["box_id"],
            event["order_id"],
        )
    )
    for index, event in enumerate(shift.events, start=1):
        event["event_key"] = index
    shift.event_of_order = {event["order_id"]: event for event in shift.events}

    # The Y01 document is written here: its row order and its event_key column
    # are the order this stage settles, so it cannot be written before it.
    shift.pub.delimited(
        "canonical_events.csv",
        ",",
        [
            "event_key",
            "order_id",
            "box_id",
            "source_system",
            "source_priority",
            "event_seq",
            "raised_min",
            "slot_code",
            "cluster_tag",
        ],
        [
            [
                fmt_int(event["event_key"]),
                event["order_id"],
                event["box_id"],
                event["source_system"],
                fmt_int(event["source_priority"]),
                fmt_int(event["event_seq"]),
                fmt_int(event["raised_min"]),
                event["slot_code"],
                event["cluster_tag"],
            ]
            for event in shift.events
        ],
    )
    shift.pub.delimited(
        "event_order.csv",
        ",",
        ["event_key", "order_id", "slot_code", "source_priority", "event_seq", "box_id"],
        [
            [
                fmt_int(event["event_key"]),
                event["order_id"],
                event["slot_code"],
                fmt_int(event["source_priority"]),
                fmt_int(event["event_seq"]),
                event["box_id"],
            ]
            for event in shift.events
        ],
    )


# ---------------------------------------------------------------------------
# Y06  Move dependencies and their cycles
# ---------------------------------------------------------------------------


def _components(edges):
    """Strongly connected components of two nodes or more."""
    outgoing = {}
    for edge in edges:
        outgoing.setdefault(edge["before_order"], set()).add(edge["after_order"])
    inside = set(outgoing)
    for followers in outgoing.values():
        inside |= followers

    reach = {}
    for start in sorted(inside):
        seen = set()
        frontier = list(outgoing.get(start, ()))
        while frontier:
            node = frontier.pop()
            if node in seen:
                continue
            seen.add(node)
            frontier.extend(outgoing.get(node, ()))
        reach[start] = seen

    found = []
    assigned = set()
    for node in sorted(inside):
        if node in assigned:
            continue
        group = sorted(
            other
            for other in reach[node]
            if other in reach and node in reach[other]
        )
        if node in group and len(group) > 1:
            found.append(group)
            assigned |= set(group)
    return found


def step_y06_dependency_cycles(shift):
    papers = shift.papers
    canonical = set(shift.event_of_order)
    edges = []
    for row in papers.jsonl("move_dependency_declarations.jsonl"):
        if row["state"] != "declared":
            continue
        if row["before_order"] not in canonical or row["after_order"] not in canonical:
            continue
        if row["before_order"] == row["after_order"]:
            continue
        edges.append(
            {
                "edge_id": row["edge_id"],
                "before_order": row["before_order"],
                "after_order": row["after_order"],
                "edge_weight": int(row["edge_weight"]),
            }
        )

    nodes = sorted(canonical)
    live = list(edges)
    entries = []
    while True:
        groups = _components(live)
        if not groups:
            break
        groups.sort(key=lambda group: group[0])
        group = groups[0]
        members = set(group)
        inside = [
            edge
            for edge in live
            if edge["before_order"] in members and edge["after_order"] in members
        ]
        ranked = sorted(inside, key=lambda edge: (-edge["edge_weight"], edge["edge_id"]))
        depth = min(shift.protection_depth, len(ranked))
        protected = {edge["edge_id"] for edge in ranked[:depth]}
        candidates = [edge for edge in inside if edge["edge_id"] not in protected]
        if not candidates:
            candidates = list(inside)
        removed = sorted(candidates, key=lambda edge: (edge["edge_weight"], edge["edge_id"]))[0]
        live = [edge for edge in live if edge["edge_id"] != removed["edge_id"]]
        entries.append(
            {
                "component_key": group[0],
                "member_count": len(group),
                "members": list(group),
                "edge_removed": removed["edge_id"],
                "edge_weight": removed["edge_weight"],
                "before_order": removed["before_order"],
                "after_order": removed["after_order"],
                "protected_count": depth,
            }
        )

    shift.dependency_edges = live
    shift.pub.jsondoc(
        "cycle_break_report.json",
        {
            "shift_id": shift.shift_id,
            "protection_depth": shift.protection_depth,
            "component_count": len(entries),
            "components": entries,
        },
    )

    predecessors = {order: set() for order in nodes}
    successors = {order: set() for order in nodes}
    for edge in live:
        predecessors[edge["after_order"]].add(edge["before_order"])
        successors[edge["before_order"]].add(edge["after_order"])
    placed = set()
    ready = sorted(
        (order for order in nodes if not predecessors[order]),
        key=lambda order: shift.event_of_order[order]["event_key"],
    )
    sequence = []
    while ready:
        order = ready.pop(0)
        placed.add(order)
        sequence.append(order)
        changed = False
        for follower in sorted(successors[order]):
            if follower in placed or follower in ready:
                continue
            if predecessors[follower] <= placed:
                ready.append(follower)
                changed = True
        if changed:
            ready.sort(key=lambda item: shift.event_of_order[item]["event_key"])
    shift.dependency_order = sequence

    shift.pub.delimited(
        "dependency_order.csv",
        ",",
        ["position", "order_id", "event_key"],
        [
            [fmt_int(position), order, fmt_int(shift.event_of_order[order]["event_key"])]
            for position, order in enumerate(sequence, start=1)
        ],
    )


# ---------------------------------------------------------------------------
# Y07  Move admission
# ---------------------------------------------------------------------------


def step_y07_move_admission(shift):
    papers = shift.papers

    waivers = {}
    exceptions = [
        row
        for row in papers.delim("operational_exception_notices.csv", ",")
        if row["shift_id"] == shift.shift_id
    ]
    shift.exceptions = exceptions
    for row in exceptions:
        if row["withdrawn"] == "yes" or row["target_kind"] != "order":
            continue
        kind = row["exception_kind"].lower()
        if "zone" in kind:
            lifted = "sealed"
        elif "tier" in kind:
            lifted = "tier"
        elif "reservation" in kind:
            lifted = "reserved"
        else:
            lifted = "cutoff"
        waivers.setdefault(row["target_id"], set()).add(lifted)
    shift.waivers = waivers

    reservations = []
    for row in papers.jsonl("hold_reservation_notices.jsonl"):
        if row["shift_id"] != shift.shift_id or row["state"] != "held":
            continue
        block_id = row["block_id"]
        opening_free = shift.opening_free.get(block_id, 0)
        if opening_free < 0:
            opening_free = 0
        quantity = row["quantity"]
        if quantity == shift.marker or quantity is None:
            asked = opening_free
        else:
            asked = int(quantity)
        credit = min(asked, opening_free)
        reservations.append(
            {
                "reservation_id": row["reservation_id"],
                "block_id": block_id,
                "service_group": row["service_group"],
                "first_slot": row["first_slot"],
                "last_slot": row["last_slot"],
                "asked": asked,
                "withheld": credit,
                "credit": credit,
                "consumed": 0,
                "unmet": asked - credit,
            }
        )
    reservations.sort(key=lambda item: item["reservation_id"])
    shift.reservations = reservations

    def covering(block_id, slot_code):
        ordinal = shift.slot_ordinal[slot_code]
        out = []
        for reservation in reservations:
            if reservation["block_id"] != block_id:
                continue
            first = shift.slot_ordinal[reservation["first_slot"]]
            last = shift.slot_ordinal[reservation["last_slot"]]
            if first <= ordinal <= last:
                out.append(reservation)
        return out

    shift.covering_reservations = covering

    standing = dict(shift.opening_boxes)
    position = {box: dict(place) for box, place in shift.opening_position.items()}
    canonical_of_cluster = {}
    history = []
    moves_of_box = {}
    rehandles_of_box = {}
    depths_of_box = {}

    occupancy_snapshots = {}
    credit_snapshots = {}

    def close_slot(slot_code):
        occupancy_snapshots[slot_code] = dict(standing)
        credit_snapshots[slot_code] = {
            reservation["reservation_id"]: reservation["credit"] for reservation in reservations
        }

    grouped = {code: [] for code in shift.slot_codes}
    grouped[shift.marker] = []
    for event in shift.events:
        grouped[event["slot_code"]].append(event)

    def admit(event):
        slot_code = event["slot_code"]
        lifted = shift.waivers.get(event["order_id"], set())
        box = shift.dimensions.get(event["box_id"])
        block_id = event["to_block"]
        in_force = block_id in shift.geometry
        capacity = shift.geometry[block_id]["capacity"] if in_force else 0
        tiers_max = shift.geometry[block_id]["tiers_max"] if in_force else 0
        reason = shift.marker
        outcome = "admitted"

        for test, code in zip(shift.rung_tests, shift.rung_codes):
            if test in lifted:
                continue
            caught = False
            if test == "unknown_box":
                caught = box is None
            elif test == "sealed":
                row = shift.slot_grid.get((slot_code, block_id))
                caught = row is not None and row["sealed"] == "yes"
            elif test == "stale":
                caught = event["slot_ordinal"] is None
            elif test == "tier":
                if not in_force or capacity == 0:
                    caught = True
                else:
                    caught = int(event["to_tier"]) > tiers_max
            elif test == "reserved":
                free = capacity - standing.get(block_id, 0)
                group = shift.service_group_of_box(event["box_id"])
                withheld = 0
                if in_force:
                    for reservation in covering(block_id, slot_code):
                        if reservation["service_group"] != group:
                            withheld += reservation["credit"]
                caught = (free - withheld) <= 0
            elif test == "duplicate":
                caught = event["cluster_tag"] in canonical_of_cluster
            if caught:
                outcome = "set_aside"
                reason = code
                break

        event["outcome"] = outcome
        event["reason_code"] = reason
        if outcome == "admitted":
            canonical_of_cluster.setdefault(event["cluster_tag"], event["order_id"])
            came = position.get(event["box_id"])
            was_stacked = came is not None
            if was_stacked:
                standing[came["block_id"]] -= 1
            standing[block_id] = standing.get(block_id, 0) + 1
            history.append(
                {
                    "box_id": event["box_id"],
                    "event_key": event["event_key"],
                    "from": came,
                    "to": {
                        "block_id": block_id,
                        "row_no": int(event["to_row"]),
                        "tier_no": int(event["to_tier"]),
                    },
                    "was_stacked": "yes" if was_stacked else "no",
                }
            )
            position[event["box_id"]] = {
                "block_id": block_id,
                "row_no": int(event["to_row"]),
                "tier_no": int(event["to_tier"]),
            }
            moves_of_box[event["box_id"]] = moves_of_box.get(event["box_id"], 0) + 1
            if was_stacked:
                rehandles_of_box[event["box_id"]] = rehandles_of_box.get(event["box_id"], 0) + 1
                depths_of_box.setdefault(event["box_id"], []).append(came["tier_no"])
            group = shift.service_group_of_box(event["box_id"])
            for reservation in covering(block_id, slot_code):
                if reservation["service_group"] == group and reservation["credit"] > 0:
                    reservation["credit"] -= 1
                    reservation["consumed"] += 1
                    break

    for code in shift.slot_codes:
        for event in grouped[code]:
            admit(event)
        close_slot(code)
    for event in grouped[shift.marker]:
        admit(event)
    shift.occupancy_snapshots = occupancy_snapshots
    shift.credit_snapshots = credit_snapshots
    shift.closing_standing = standing
    shift.closing_position = position
    shift.history = history
    shift.moves_of_box = moves_of_box
    shift.rehandles_of_box = rehandles_of_box
    shift.depths_of_box = depths_of_box
    shift.admitted = [event for event in shift.events if event["outcome"] == "admitted"]
    shift.set_aside = [event for event in shift.events if event["outcome"] == "set_aside"]

    shift.pub.delimited(
        "move_eligibility.csv",
        ",",
        [
            "event_key",
            "order_id",
            "box_id",
            "slot_code",
            "to_block",
            "to_row",
            "to_tier",
            "outcome",
            "reason_code",
        ],
        [
            [
                fmt_int(event["event_key"]),
                event["order_id"],
                event["box_id"],
                event["slot_code"],
                event["to_block"],
                fmt_int(event["to_row"]),
                fmt_int(event["to_tier"]),
                event["outcome"],
                event["reason_code"],
            ]
            for event in shift.events
        ],
    )
    shift.pub.delimited(
        "rejected_moves.tsv",
        "\t",
        ["event_key", "order_id", "box_id", "slot_code", "reason_code"],
        [
            [
                fmt_int(event["event_key"]),
                event["order_id"],
                event["box_id"],
                event["slot_code"],
                event["reason_code"],
            ]
            for event in shift.set_aside
        ],
    )
    counts = {code: 0 for code in shift.rung_codes}
    for event in shift.set_aside:
        counts[event["reason_code"]] += 1
    shift.rejection_counts = counts
    shift.pub.delimited(
        "rejection_reasons.csv",
        ",",
        ["reason_code", "order_count"],
        [[code, fmt_int(counts[code])] for code in shift.rung_codes],
    )
    shift.pub.delimited(
        "accepted_moves.csv",
        ",",
        ["event_key", "order_id", "box_id", "slot_code", "to_block", "to_row", "to_tier"],
        [
            [
                fmt_int(event["event_key"]),
                event["order_id"],
                event["box_id"],
                event["slot_code"],
                event["to_block"],
                fmt_int(event["to_row"]),
                fmt_int(event["to_tier"]),
            ]
            for event in shift.admitted
        ],
    )


# ---------------------------------------------------------------------------
# Y08  Yard state through the shift
# ---------------------------------------------------------------------------


def step_y08_yard_state(shift):
    shift.pub.delimited(
        "yard_occupancy.psv",
        "|",
        ["block_id", "zone", "slot_capacity", "opening_boxes", "closing_boxes", "closing_free"],
        [
            [
                block_id,
                shift.geometry[block_id]["zone"],
                fmt_int(shift.geometry[block_id]["capacity"]),
                fmt_int(shift.opening_boxes[block_id]),
                fmt_int(shift.closing_standing[block_id]),
                fmt_int(shift.geometry[block_id]["capacity"] - shift.closing_standing[block_id]),
            ]
            for block_id in shift.blocks_in_force
        ],
    )

    rows = []
    for record in sorted(shift.history, key=lambda item: item["event_key"]):
        came = record["from"]
        rows.append(
            [
                record["box_id"],
                fmt_int(record["event_key"]),
                came["block_id"] if came else shift.marker,
                fmt_int(came["row_no"]) if came else shift.marker,
                fmt_int(came["tier_no"]) if came else shift.marker,
                record["to"]["block_id"],
                fmt_int(record["to"]["row_no"]),
                fmt_int(record["to"]["tier_no"]),
                record["was_stacked"],
            ]
        )
    shift.pub.delimited(
        "container_state_history.psv",
        "|",
        [
            "box_id",
            "event_key",
            "from_block",
            "from_row",
            "from_tier",
            "to_block",
            "to_row",
            "to_tier",
            "was_stacked",
        ],
        rows,
    )

    rows = []
    for box_id in sorted(shift.boxes):
        place = shift.closing_position.get(box_id)
        rows.append(
            [
                box_id,
                place["block_id"] if place else shift.marker,
                fmt_int(place["row_no"]) if place else shift.marker,
                fmt_int(place["tier_no"]) if place else shift.marker,
                fmt_int(shift.moves_of_box.get(box_id, 0)),
                "stacked" if place else "off_yard",
            ]
        )
    shift.pub.delimited(
        "container_state_final.csv",
        ",",
        ["box_id", "block_id", "row_no", "tier_no", "moves_applied", "state"],
        rows,
    )


# ---------------------------------------------------------------------------
# Y09  Planned against physical
# ---------------------------------------------------------------------------


def step_y09_movement_reconciliation(shift):
    confirmations = shift.papers.jsonl("crane_confirmation_feed.ndjson")
    shift.confirmations = confirmations
    by_order = {}
    loose = []
    for record in confirmations:
        order_id = record.get("order_id") or ""
        if order_id in ("", shift.marker):
            loose.append(record)
            continue
        current = by_order.get(order_id)
        if current is None or (int(record["confirmed_min"]), record["confirm_id"]) < (
            int(current["confirmed_min"]),
            current["confirm_id"],
        ):
            by_order[order_id] = record
    shift.loose_confirmations = sorted(loose, key=lambda record: record["confirm_id"])
    shift.confirmation_of_order = by_order

    records = []
    for event in shift.events:
        confirmation = by_order.get(event["order_id"])
        if event["outcome"] == "admitted":
            if confirmation is None:
                state = "unconfirmed"
            elif confirmation["confirm_state"] == "landed":
                state = "confirmed"
            else:
                state = "aborted"
        else:
            if confirmation is not None and confirmation["confirm_state"] == "landed":
                state = "contradicted"
            else:
                state = "set_aside"
        event["movement_state"] = state
        records.append(
            {
                "event_key": event["event_key"],
                "order_id": event["order_id"],
                "box_id": event["box_id"],
                "planned_outcome": event["outcome"],
                "confirm_id": confirmation["confirm_id"] if confirmation else shift.marker,
                "confirmed_min": int(confirmation["confirmed_min"]) if confirmation else 0,
                "movement_state": state,
            }
        )
    shift.pub.jsonlines("movement_accounting.jsonl", records)


# ---------------------------------------------------------------------------
# Y10  Rehandles and equipment
# ---------------------------------------------------------------------------


def step_y10_rehandle_and_equipment(shift):
    papers = shift.papers
    records = []
    charge_of_box = {}
    for box_id in sorted(shift.moves_of_box):
        depths = shift.depths_of_box.get(box_id, [])
        surcharge = sum(surcharge_of(shift, depth) for depth in depths)
        charge = shift.moves_of_box[box_id] * shift.base_move_charge + surcharge
        charge_of_box[box_id] = charge
        records.append(
            {
                "box_id": box_id,
                "moves": shift.moves_of_box[box_id],
                "rehandles": shift.rehandles_of_box.get(box_id, 0),
                "tier_depths": list(depths),
                "surcharge_cents": surcharge,
                "charge_cents": charge,
            }
        )
    shift.charge_of_box = charge_of_box
    shift.assessed_cents = sum(charge_of_box.values())
    shift.pub.jsonlines("rehandle_ledger.jsonl", records)

    rows = [
        row
        for row in papers.delim("handling_equipment_register.csv", ",")
        if row["shift_id"] == shift.shift_id
    ]
    units = applicable(rows, ["equipment_id"], ["retired"])
    shift.equipment = {key[0]: row for key, row in units.items()}

    used = {unit: 0 for unit in shift.equipment}
    exceptions = []
    for event in sorted(shift.events, key=lambda item: item["event_key"]):
        if event["movement_state"] != "confirmed":
            continue
        confirmation = shift.confirmation_of_order[event["order_id"]]
        unit = confirmation["equipment_id"]
        if unit not in shift.equipment:
            exceptions.append(
                {
                    "event_key": event["event_key"],
                    "order_id": event["order_id"],
                    "equipment_id": unit,
                    "reason_code": "EQ_UNKNOWN_UNIT",
                }
            )
            continue
        allowance = int(shift.equipment[unit]["move_limit"])
        if used[unit] + 1 > allowance:
            exceptions.append(
                {
                    "event_key": event["event_key"],
                    "order_id": event["order_id"],
                    "equipment_id": unit,
                    "reason_code": "EQ_BEYOND_ALLOWANCE",
                }
            )
            continue
        used[unit] += 1
    shift.equipment_used = used
    shift.equipment_exceptions = exceptions

    shift.pub.delimited(
        "equipment_usage.csv",
        ",",
        ["equipment_id", "equipment_class", "allowance", "used", "minutes", "within_allowance"],
        [
            [
                unit,
                shift.equipment[unit]["equipment_class"],
                fmt_int(shift.equipment[unit]["move_limit"]),
                fmt_int(used[unit]),
                fmt_int(used[unit] * int(shift.equipment[unit]["base_minutes"])),
                "yes" if used[unit] <= int(shift.equipment[unit]["move_limit"]) else "no",
            ]
            for unit in sorted(shift.equipment)
        ],
    )
    shift.pub.delimited(
        "equipment_exceptions.tsv",
        "\t",
        ["event_key", "order_id", "equipment_id", "reason_code"],
        [
            [
                fmt_int(record["event_key"]),
                record["order_id"],
                record["equipment_id"],
                record["reason_code"],
            ]
            for record in exceptions
        ],
    )

    quay = sorted(
        unit
        for unit, row in shift.equipment.items()
        if row["equipment_class"] == "quay_crane"
    )
    shift.minutes_per_teu = int(shift.equipment[quay[0]]["base_minutes"]) if quay else 0


# ---------------------------------------------------------------------------
# Y11  Block capacity state
# ---------------------------------------------------------------------------


def step_y11_block_capacity(shift):
    rows = []
    for block_id in shift.blocks_in_force:
        capacity = shift.geometry[block_id]["capacity"]
        for slot_code in shift.slot_codes:
            occupied = shift.occupancy_snapshots[slot_code][block_id]
            grid = shift.slot_grid.get((slot_code, block_id))
            sealed = grid is not None and grid["sealed"] == "yes"
            out_of_service = grid is not None and grid["in_service"] == "no"
            if sealed or out_of_service or capacity == 0:
                rows.append(
                    [
                        block_id,
                        slot_code,
                        fmt_int(capacity),
                        fmt_int(occupied),
                        fmt_int(0),
                        fmt_int(capacity),
                        fmt_int(0),
                    ]
                )
                continue
            free = capacity - occupied
            if free < 0:
                free = 0
            standing = 0
            for reservation in shift.covering_reservations(block_id, slot_code):
                standing += shift.credit_snapshots[slot_code][reservation["reservation_id"]]
            reserved = min(standing, free)
            available = free - reserved
            if available < 0:
                available = 0
            rows.append(
                [
                    block_id,
                    slot_code,
                    fmt_int(capacity),
                    fmt_int(occupied),
                    fmt_int(reserved),
                    fmt_int(0),
                    fmt_int(available),
                ]
            )
    shift.pub.delimited(
        "yard_capacity.csv",
        ",",
        ["block_id", "slot_code", "slot_capacity", "occupied", "reserved", "unavailable", "available"],
        rows,
    )

    shift.pub.delimited(
        "yard_reservations.psv",
        "|",
        [
            "reservation_id",
            "block_id",
            "service_group",
            "first_slot",
            "last_slot",
            "asked",
            "withheld",
            "consumed",
            "unmet",
        ],
        [
            [
                reservation["reservation_id"],
                reservation["block_id"],
                reservation["service_group"],
                reservation["first_slot"],
                reservation["last_slot"],
                fmt_int(reservation["asked"]),
                fmt_int(reservation["withheld"]),
                fmt_int(reservation["consumed"]),
                fmt_int(reservation["unmet"]),
            ]
            for reservation in shift.reservations
        ],
    )

    shift.pub.delimited(
        "block_utilization.csv",
        ",",
        ["block_id", "slot_capacity", "closing_boxes", "utilisation_ratio"],
        [
            [
                block_id,
                fmt_int(shift.geometry[block_id]["capacity"]),
                fmt_int(shift.closing_standing[block_id]),
                fmt_ratio(
                    Fraction(
                        shift.closing_standing[block_id],
                        shift.geometry[block_id]["capacity"],
                    )
                    if shift.geometry[block_id]["capacity"]
                    else Fraction(0),
                    9,
                ),
            ]
            for block_id in shift.blocks_in_force
        ],
    )

    buckets = {code: [0, 0, 0, 0] for code in shift.slot_codes}
    buckets[shift.marker] = [0, 0, 0, 0]
    for event in shift.events:
        bucket = buckets[event["slot_code"]]
        bucket[0] += 1
        if event["outcome"] == "admitted":
            bucket[1] += 1
        else:
            bucket[2] += 1
        if event["movement_state"] == "confirmed":
            bucket[3] += 1
    shift.pub.delimited(
        "slot_accounting.csv",
        ",",
        ["slot_code", "events", "admitted", "set_aside", "confirmed"],
        [
            [code] + [fmt_int(value) for value in buckets[code]]
            for code in shift.slot_codes + [shift.marker]
        ],
    )


# ---------------------------------------------------------------------------
# Y12  Cutoff joined to yard state
# ---------------------------------------------------------------------------


def step_y12_load_eligibility(shift):
    papers = shift.papers
    notices = [
        row
        for row in papers.delim("cutoff_notice_board.tsv", "\t")
        if row["shift_id"] == shift.shift_id and row["superseded"] != "yes"
    ]
    in_force = {}
    for row in notices:
        key = row["vessel_id"]
        if key not in in_force or int(row["notice_seq"]) > int(in_force[key]["notice_seq"]):
            in_force[key] = row
    shift.cutoff_in_force = in_force

    obligations = {}
    for row in papers.delim("stowage_obligation_list.psv", "|"):
        obligations[(row["box_id"], row["vessel_id"])] = row
    shift.obligations = obligations

    ready_min = {}
    last_order = {}
    for event in shift.admitted:
        ready_min[event["box_id"]] = event["raised_min"]
        last_order[event["box_id"]] = event["order_id"]
    shift.ready_min = ready_min
    shift.last_admitted_order = last_order

    verdicts = {}
    for box_id in sorted(shift.boxes):
        box = shift.dimensions[box_id]
        vessel_id = box["vessel_id"]
        call = shift.vessels.get(vessel_id)
        obligation = obligations.get((box_id, vessel_id))
        ready = ready_min.get(box_id, 0)
        notice = in_force.get(vessel_id)
        order_id = last_order.get(box_id)
        waived = order_id is not None and "cutoff" in shift.waivers.get(order_id, set())
        if call is None:
            reason = "EL_NO_VESSEL"
        elif obligation is None:
            reason = "EL_NO_OBLIGATION"
        elif obligation["hold_flag"] == "yes":
            reason = "EL_HELD"
        elif box_id not in shift.closing_position:
            reason = "EL_OFF_YARD"
        elif notice is None:
            reason = "EL_NO_CUTOFF"
        elif not waived and ready > int(notice["cutoff_min"]):
            reason = "EL_AFTER_CUTOFF"
        else:
            reason = "EL_OK"
        verdicts[box_id] = {
            "box_id": box_id,
            "vessel_id": vessel_id,
            "eligible": "yes" if reason == "EL_OK" else "no",
            "reason_code": reason,
            "ready_min": ready,
        }
    shift.verdicts = verdicts

    shift.pub.delimited(
        "load_eligibility.csv",
        ",",
        ["box_id", "vessel_id", "eligible", "reason_code", "ready_min"],
        [
            [
                verdict["box_id"],
                verdict["vessel_id"],
                verdict["eligible"],
                verdict["reason_code"],
                fmt_int(verdict["ready_min"]),
            ]
            for verdict in (verdicts[key] for key in sorted(verdicts))
        ],
    )

    rows = []
    for vessel_id in sorted(shift.vessels):
        own = [verdict for verdict in verdicts.values() if verdict["vessel_id"] == vessel_id]
        outside = sum(1 for verdict in own if verdict["reason_code"] == "EL_AFTER_CUTOFF")
        notice = in_force.get(vessel_id)
        rows.append(
            [
                vessel_id,
                notice["notice_id"] if notice else shift.marker,
                fmt_int(int(notice["cutoff_min"]) if notice else 0),
                fmt_int(len(own)),
                fmt_int(len(own) - outside),
                fmt_int(outside),
            ]
        )
    shift.pub.delimited(
        "vessel_cutoff_status.csv",
        ",",
        ["vessel_id", "notice_id", "cutoff_min", "boxes_total", "boxes_inside", "boxes_outside"],
        rows,
    )

    manifest = {}
    for box_id in sorted(verdicts):
        verdict = verdicts[box_id]
        if verdict["reason_code"] != "EL_OK":
            continue
        box = shift.dimensions[box_id]
        obligation = obligations[(box_id, verdict["vessel_id"])]
        entry = {
            "vessel_id": verdict["vessel_id"],
            "box_id": box_id,
            "class_rank": shift.class_rank.get(box["box_class"], 0),
            "stow_sequence": int(obligation["stow_sequence"]),
            "bay_no": int(obligation["bay_no"]),
            "teu_factor": box["teu_factor"],
            "mass_kg": box["mass_kg"],
        }
        manifest.setdefault(verdict["vessel_id"], []).append(entry)
    shift.manifest = manifest

    rows = []
    for vessel_id in sorted(manifest):
        for entry in sorted(manifest[vessel_id], key=lambda item: item["box_id"]):
            rows.append(
                [
                    entry["vessel_id"],
                    entry["box_id"],
                    fmt_int(entry["class_rank"]),
                    fmt_int(entry["stow_sequence"]),
                    fmt_int(entry["bay_no"]),
                    fmt_int(entry["teu_factor"]),
                    fmt_int(entry["mass_kg"]),
                ]
            )
    shift.pub.delimited(
        "vessel_container_manifest.psv",
        "|",
        ["vessel_id", "box_id", "class_rank", "stow_sequence", "bay_no", "teu_factor", "mass_kg"],
        rows,
    )


# ---------------------------------------------------------------------------
# Y13  The quay ration and the load
# ---------------------------------------------------------------------------


def step_y13_quay_ration(shift):
    papers = shift.papers
    filed = [
        row
        for row in papers.delim("quay_demand_returns.csv", ",")
        if row["return_state"] == "filed"
    ]
    demands = applicable(filed, ["vessel_id", "slot_code"], [])
    shift.demands = {
        key: int(row["declared_minutes"]) for key, row in demands.items()
    }

    windows = applicable(
        [row for row in papers.delim("berth_window_register.csv", ",") if row["draft"] != "yes"],
        ["berth_id", "slot_code"],
        [],
    )
    shift.windows = {key: int(row["crane_minutes"]) for key, row in windows.items()}

    trace = []
    pairings = []
    share_of_vessel = {}
    for slot_code in shift.slot_codes:
        for berth_id in shift.reporting_berths:
            members = sorted(
                vessel_id
                for vessel_id, call in shift.vessels.items()
                if call["berth_id"] == berth_id and (vessel_id, slot_code) in shift.demands
            )
            crewed = shift.gang_minutes.get((berth_id, slot_code), 0)
            window = shift.windows.get((berth_id, slot_code), 0)
            pool = min(window, crewed)
            declared = {
                vessel_id: shift.demands[(vessel_id, slot_code)] for vessel_id in members
            }
            ceiling = {
                vessel_id: shift.vessel_slot_ceiling.get((vessel_id, slot_code), 0)
                for vessel_id in members
            }
            group = {
                vessel_id: shift.vessels[vessel_id]["service_group"] for vessel_id in members
            }
            share = {vessel_id: Fraction(0) for vessel_id in members}
            passes = 0
            for pass_no in range(1, shift.pass_budget + 1):
                need = {
                    vessel_id: max(Fraction(0), declared[vessel_id] - share[vessel_id])
                    for vessel_id in members
                }
                total_need = sum(need.values())
                unallocated = pool - sum(share.values())
                if total_need == 0 or unallocated <= 0:
                    break
                target = {}
                for vessel_id in members:
                    target[vessel_id] = share[vessel_id] + Fraction(
                        unallocated
                    ) * need[vessel_id] / total_need
                capped = {}
                freed = {}
                for vessel_id in members:
                    limit = Fraction(ceiling[vessel_id])
                    if target[vessel_id] > limit:
                        capped[vessel_id] = limit
                        freed[vessel_id] = target[vessel_id] - limit
                    else:
                        capped[vessel_id] = target[vessel_id]
                        freed[vessel_id] = Fraction(0)
                received = {vessel_id: Fraction(0) for vessel_id in members}
                unplaced = Fraction(0)
                cells = {}
                for vessel_id in members:
                    cells.setdefault((berth_id, group[vessel_id]), []).append(vessel_id)
                for cell in sorted(cells):
                    inside = cells[cell]
                    pot = sum(freed[vessel_id] for vessel_id in inside)
                    if pot == 0:
                        continue
                    takers = [vessel_id for vessel_id in inside if freed[vessel_id] == 0]
                    basis = sum(need[vessel_id] for vessel_id in takers)
                    if not takers or basis == 0:
                        unplaced += pot
                        continue
                    for vessel_id in takers:
                        received[vessel_id] = pot * need[vessel_id] / basis
                aim = {}
                for vessel_id in members:
                    value = capped[vessel_id] + received[vessel_id]
                    limit = Fraction(ceiling[vessel_id])
                    aim[vessel_id] = limit if value > limit else value
                for vessel_id in members:
                    standing = share[vessel_id]
                    moved = standing + shift.damping * (aim[vessel_id] - standing)
                    rounded = Fraction(half_up(moved))
                    goal = Fraction(half_up(aim[vessel_id]))
                    if rounded == standing and standing != goal:
                        step = Fraction(shift.minimum_step)
                        gap = goal - standing
                        if gap > 0:
                            rounded = standing + min(step, gap)
                        else:
                            rounded = standing - min(step, -gap)
                    share[vessel_id] = rounded
                passes = pass_no
                trace.append(
                    {
                        "slot_code": slot_code,
                        "berth_id": berth_id,
                        "pass_no": pass_no,
                        "pool_minutes": int(pool),
                        "unplaced_minutes": half_up(unplaced),
                        "shares": [
                            {
                                "vessel_id": vessel_id,
                                "share_minutes": int(share[vessel_id]),
                            }
                            for vessel_id in members
                        ],
                    }
                )
            rationed = sum(int(share[vessel_id]) for vessel_id in members)
            for vessel_id in members:
                share_of_vessel[vessel_id] = share_of_vessel.get(vessel_id, 0) + int(
                    share[vessel_id]
                )
            pairings.append(
                {
                    "slot_code": slot_code,
                    "berth_id": berth_id,
                    "pool_minutes": int(pool),
                    "declared_minutes": sum(declared.values()),
                    "crewed_minutes": crewed,
                    "vessel_count": len(members),
                    "rationed_minutes": rationed,
                    "passes": passes,
                }
            )
    shift.ration_trace = trace
    shift.pairings = pairings
    shift.share_of_vessel = {
        vessel_id: share_of_vessel.get(vessel_id, 0) for vessel_id in shift.vessels
    }
    shift.pub.jsonlines("ration_trace.jsonl", trace)

    def sort_key(entry):
        return tuple(entry[name] for name in shift.stowage_keys)

    loaded = {}
    deferred = {}
    loaded_minutes = {}
    for vessel_id in sorted(shift.vessels):
        entries = sorted(shift.manifest.get(vessel_id, []), key=sort_key)
        allowance = shift.share_of_vessel[vessel_id]
        running = 0
        taken = []
        left = []
        stopped = False
        for entry in entries:
            cost = entry["teu_factor"] * shift.minutes_per_teu
            if not stopped and running + cost <= allowance:
                running += cost
                taken.append({"box_id": entry["box_id"], "load_minutes": cost})
            else:
                stopped = True
                left.append({"box_id": entry["box_id"], "load_minutes": cost})
        loaded[vessel_id] = taken
        deferred[vessel_id] = left
        loaded_minutes[vessel_id] = running
    shift.loaded = loaded
    shift.deferred = deferred
    shift.loaded_minutes = loaded_minutes

    shift.pub.jsondoc(
        "load_sequence_ledger.json",
        {
            "shift_id": shift.shift_id,
            "minutes_per_teu": shift.minutes_per_teu,
            "stowage_keys": list(shift.stowage_keys),
            "vessels": [
                {
                    "vessel_id": vessel_id,
                    "share_minutes": shift.share_of_vessel[vessel_id],
                    "eligible_count": len(shift.manifest.get(vessel_id, [])),
                    "loaded_count": len(loaded[vessel_id]),
                    "deferred_count": len(deferred[vessel_id]),
                    "loaded_minutes": loaded_minutes[vessel_id],
                    "unused_minutes": shift.share_of_vessel[vessel_id]
                    - loaded_minutes[vessel_id],
                }
                for vessel_id in sorted(shift.vessels)
            ],
        },
    )

    shift.pub.jsondoc(
        "departure_ledger.json",
        {
            "shift_id": shift.shift_id,
            "vessels": [
                {
                    "vessel_id": vessel_id,
                    "berth_id": shift.vessels[vessel_id]["berth_id"],
                    "share_minutes": shift.share_of_vessel[vessel_id],
                    "loaded_minutes": loaded_minutes[vessel_id],
                    "unused_minutes": shift.share_of_vessel[vessel_id]
                    - loaded_minutes[vessel_id],
                    "boxes": [
                        {
                            "load_position": position,
                            "box_id": entry["box_id"],
                            "load_minutes": entry["load_minutes"],
                        }
                        for position, entry in enumerate(loaded[vessel_id], start=1)
                    ],
                }
                for vessel_id in sorted(shift.vessels)
            ],
        },
    )

    last_rung = last_rung_surcharge(shift)
    rows = []
    published = 0
    for vessel_id in sorted(deferred):
        for entry in sorted(deferred[vessel_id], key=lambda item: item["box_id"]):
            assessed = shift.charge_of_box.get(entry["box_id"], 0)
            republished = assessed + last_rung
            published += republished
            rows.append(
                [
                    vessel_id,
                    entry["box_id"],
                    fmt_int(entry["load_minutes"]),
                    fmt_int(assessed),
                    fmt_int(republished),
                ]
            )
    shift.published_cents = published
    shift.republished_boxes = [row[1] for row in rows]
    shift.pub.delimited(
        "deferred_containers.tsv",
        "\t",
        ["vessel_id", "box_id", "load_minutes", "assessed_cents", "published_cents"],
        rows,
    )


# ---------------------------------------------------------------------------
# Y14  Terminal accounts and publication
# ---------------------------------------------------------------------------


def step_y14_terminal_accounts(shift, out_dir):
    loaded_boxes = sorted(
        entry["box_id"] for entries in shift.loaded.values() for entry in entries
    )
    deferred_boxes = sorted(
        entry["box_id"] for entries in shift.deferred.values() for entry in entries
    )
    eligible_boxes = sorted(
        box_id for box_id, verdict in shift.verdicts.items() if verdict["reason_code"] == "EL_OK"
    )

    totals = {
        "admitted_moves": len(shift.admitted),
        "assessed_cents": shift.assessed_cents,
        "boxes_on_yard": sum(shift.closing_standing[block] for block in shift.blocks_in_force),
        "canonical_events": len(shift.events),
        "confirmed_moves": sum(
            1 for event in shift.events if event["movement_state"] == "confirmed"
        ),
        "contradicted_moves": sum(
            1 for event in shift.events if event["movement_state"] == "contradicted"
        ),
        "deferred_boxes": len(deferred_boxes),
        "eligible_boxes": len(eligible_boxes),
        "equipment_exceptions": len(shift.equipment_exceptions),
        "loaded_boxes": len(loaded_boxes),
        "loaded_minutes": sum(shift.loaded_minutes.values()),
        "loose_confirmations": len(shift.loose_confirmations),
        "published_cents": shift.published_cents,
        "rationed_minutes": sum(shift.share_of_vessel.values()),
        "rehandle_moves": sum(shift.rehandles_of_box.values()),
        "set_aside_moves": len(shift.set_aside),
    }
    shift.totals = totals

    moved_boxes = set(shift.moves_of_box)
    on_yard = set(shift.closing_position)
    decided = {event["order_id"] for event in shift.events if event["outcome"] in ("admitted", "set_aside")}
    identities = {
        "loaded_and_deferred_partition_eligible": "yes"
        if set(loaded_boxes).isdisjoint(deferred_boxes)
        and set(loaded_boxes) | set(deferred_boxes) == set(eligible_boxes)
        else "no",
        "moved_boxes_all_on_yard": "yes" if moved_boxes <= on_yard else "no",
        "decision_count_matches_events": "yes"
        if decided == {event["order_id"] for event in shift.events}
        else "no",
        "republished_covers_deferred": "yes"
        if set(shift.republished_boxes) == set(deferred_boxes)
        and len(shift.republished_boxes) == len(deferred_boxes)
        else "no",
    }
    shift.identities = identities

    shift.pub.delimited(
        "terminal_reconciliation.csv",
        ",",
        ["measure", "value"],
        [[measure, fmt_int(totals[measure])] for measure in sorted(totals)],
    )

    kinds = {}
    for row in shift.exceptions:
        bucket = kinds.setdefault(row["exception_kind"], [0, 0])
        if row["withdrawn"] == "yes":
            bucket[1] += 1
        else:
            bucket[0] += 1
    shift.pub.delimited(
        "exception_summary.tsv",
        "\t",
        ["exception_kind", "granted", "withdrawn"],
        [
            [kind, fmt_int(kinds[kind][0]), fmt_int(kinds[kind][1])]
            for kind in sorted(kinds)
        ],
    )

    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<vessel_reconciliation>"]
    lines.append("  <shift_id>%s</shift_id>" % xml_escape(shift.shift_id))
    lines.append("  <vessels>")
    for vessel_id in sorted(shift.vessels):
        lines.append('    <vessel id="%s">' % xml_escape(vessel_id))
        lines.append(
            "      <berth_id>%s</berth_id>" % xml_escape(shift.vessels[vessel_id]["berth_id"])
        )
        lines.append(
            "      <eligible_count>%s</eligible_count>"
            % fmt_int(len(shift.manifest.get(vessel_id, [])))
        )
        lines.append(
            "      <loaded_count>%s</loaded_count>" % fmt_int(len(shift.loaded[vessel_id]))
        )
        lines.append(
            "      <deferred_count>%s</deferred_count>" % fmt_int(len(shift.deferred[vessel_id]))
        )
        lines.append(
            "      <share_minutes>%s</share_minutes>"
            % fmt_int(shift.share_of_vessel[vessel_id])
        )
        lines.append("    </vessel>")
    lines.append("  </vessels>")
    for name, answer in identities.items():
        lines.append(
            '  <identity name="%s">%s</identity>' % (xml_escape(name), xml_escape(answer))
        )
    lines.append("</vessel_reconciliation>")
    shift.pub.plain("vessel_reconciliation.xml", "\n".join(lines) + "\n")

    states = {}
    for event in shift.events:
        states[event["movement_state"]] = states.get(event["movement_state"], 0) + 1
    conf = ["# The audit trail of one shift."]
    conf.append("[shift]")
    conf.append("shift_id = %s" % shift.shift_id)
    conf.append("live_sheet_name = %s" % shift.live_sheet_name)
    conf.append("reference = %s" % shift.reference)
    conf.append("")
    conf.append("[counts]")
    for measure in sorted(totals):
        conf.append("%s = %s" % (measure, fmt_int(totals[measure])))
    conf.append("")
    conf.append("[ladder]")
    for code in shift.rung_codes:
        conf.append("%s = %s" % (code, fmt_int(shift.rejection_counts[code])))
    conf.append("")
    conf.append("[movement]")
    for state in sorted(states):
        conf.append("%s = %s" % (state, fmt_int(states[state])))
    shift.pub.plain("audit_trail.conf", "\n".join(conf) + "\n")

    for berth_id in shift.reporting_berths:
        own = [pairing for pairing in shift.pairings if pairing["berth_id"] == berth_id]
        own.sort(key=lambda pairing: pairing["slot_code"])
        vessels = sorted(
            vessel_id
            for vessel_id, call in shift.vessels.items()
            if call["berth_id"] == berth_id
        )
        shift.pub.jsondoc(
            "berth_report_%s.json" % berth_id,
            {
                "shift_id": shift.shift_id,
                "berth_id": berth_id,
                "vessel_count": len(vessels),
                "vessels": vessels,
                "pool_minutes": sum(pairing["pool_minutes"] for pairing in own),
                "rationed_minutes": sum(pairing["rationed_minutes"] for pairing in own),
                "pairings": [
                    {
                        "slot_code": pairing["slot_code"],
                        "berth_id": pairing["berth_id"],
                        "pool_minutes": pairing["pool_minutes"],
                        "declared_minutes": pairing["declared_minutes"],
                        "crewed_minutes": pairing["crewed_minutes"],
                        "vessel_count": pairing["vessel_count"],
                        "rationed_minutes": pairing["rationed_minutes"],
                    }
                    for pairing in own
                ],
            },
        )

    summary = ["# Daily operational summary", ""]
    summary.append("shift %s at reference %s" % (shift.shift_id, shift.reference))
    summary.append("")
    for measure in sorted(totals):
        summary.append("- %s: %s" % (measure, fmt_int(totals[measure])))
    summary.append("")
    summary.append("## Ladder")
    summary.append("")
    for code in shift.rung_codes:
        summary.append("- %s: %s" % (code, fmt_int(shift.rejection_counts[code])))
    summary.append("")
    summary.append("## Identity checks")
    summary.append("")
    for name, answer in identities.items():
        summary.append("- %s: %s" % (name, answer))
    shift.pub.plain("daily_operational_summary.md", "\n".join(summary) + "\n")

    shift.pub.jsondoc(
        "final_control_totals.json",
        {
            "shift_id": shift.shift_id,
            "live_sheet_name": shift.live_sheet_name,
            "minutes_per_teu": shift.minutes_per_teu,
            "totals": {measure: totals[measure] for measure in sorted(totals)},
            "identities": dict(identities),
        },
    )

    artifacts = ARTIFACT_ORDER_HEAD + [
        "berth_report_%s.json" % berth_id for berth_id in shift.reporting_berths
    ] + ARTIFACT_ORDER_TAIL
    manifest_name = "publication_manifest.json"

    digests = {}
    sizes = {}
    for name in artifacts:
        if name == manifest_name:
            continue
        payload = shift.pub.docs[name]
        digests[name] = hashlib.sha256(payload).hexdigest()
        sizes[name] = len(payload)

    def block_digest(names):
        block = "".join("%s %s\n" % (name, digests[name]) for name in names)
        return hashlib.sha256(block.encode("utf-8")).hexdigest()

    core = block_digest(CORE_DOCUMENTS)
    rest = [name for name in artifacts if name != manifest_name and name not in CORE_DOCUMENTS]
    shift.pub.jsondoc(
        manifest_name,
        {
            "shift_id": shift.shift_id,
            "core_digest": core,
            "publication_digest": block_digest(rest),
            "document_count": len(artifacts),
            "documents": [
                {"name": name, "sha256": digests[name], "bytes": sizes[name]}
                for name in artifacts
                if name != manifest_name
            ],
        },
    )

    os.makedirs(out_dir, exist_ok=True)
    for name in artifacts:
        with open(os.path.join(out_dir, name), "wb") as handle:
            handle.write(shift.pub.docs[name])


ARTIFACT_ORDER_HEAD = [
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
    "rejected_moves.tsv",
    "rejection_reasons.csv",
    "accepted_moves.csv",
    "container_state_history.psv",
    "container_state_final.csv",
    "dependency_order.csv",
    "yard_reservations.psv",
    "block_utilization.csv",
    "equipment_usage.csv",
    "equipment_exceptions.tsv",
    "slot_accounting.csv",
    "vessel_cutoff_status.csv",
    "vessel_container_manifest.psv",
    "load_sequence_ledger.json",
    "deferred_containers.tsv",
    "departure_ledger.json",
    "vessel_reconciliation.xml",
    "exception_summary.tsv",
    "audit_trail.conf",
]

ARTIFACT_ORDER_TAIL = [
    "daily_operational_summary.md",
    "final_control_totals.json",
]

CORE_DOCUMENTS = [
    "canonical_events.csv",
    "move_eligibility.csv",
    "yard_occupancy.psv",
    "yard_capacity.csv",
    "load_eligibility.csv",
    "terminal_reconciliation.csv",
]


def main(argv=None):
    parser = argparse.ArgumentParser(description="recompute one terminal shift")
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    papers = Papers(args.data)
    shift = load_context(papers)

    step_y01_canonical_events(shift)
    step_y02_unit_normalisation(shift)
    step_y03_vessel_obligation(shift)
    step_y04_opening_yard(shift)
    step_y05_event_ordering(shift)
    step_y06_dependency_cycles(shift)
    step_y07_move_admission(shift)
    step_y08_yard_state(shift)
    step_y09_movement_reconciliation(shift)
    step_y10_rehandle_and_equipment(shift)
    step_y11_block_capacity(shift)
    step_y12_load_eligibility(shift)
    step_y13_quay_ration(shift)
    step_y14_terminal_accounts(shift, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
