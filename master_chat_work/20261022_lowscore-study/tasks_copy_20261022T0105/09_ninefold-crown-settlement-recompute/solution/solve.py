#!/usr/bin/env python3
"""Settle one Ninefold Crown event from a directory of working papers.

    python3 crownsettle.py --data <directory> --out <directory>

The two options may come in either order. Without them the program reads
/app/data and writes /app/out. Every value the event carries is read from the
papers: the stage specifications fix the rules, the schema reference fixes the
column and key order of every document, and the settlement specification fixes
the order the manifest lists them in. Arithmetic is exact throughout.
"""

from __future__ import annotations

import csv
import functools
import hashlib
import json
import re
import sys
import tomllib
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path

DEFAULT_DATA = Path("/app/data")
DEFAULT_OUT = Path("/app/out")

REQUIRED_PAPERS = (
    "division_topology.xml", "entry_roster_register.csv", "entry_alias_register.csv",
    "rating_return_sheet.psv", "membership_standing_register.csv",
    "status_change_journal.tsv", "penalty_notice_register.psv",
    "recorded_pairing_table.csv", "match_result_sheets.ndjson", "game_records.csv",
    "round_configuration_register.csv", "division_admission_matrix.csv",
    "source_priority_register.csv", "unit_register_dictionary.toml",
    "revision_precedence.toml", "settlement_form_rules.toml",
    "boundary_conventions.yaml", "tiebreak_rules.json", "prize_rules.json",
    "round_modifier_rules.json", "reporting_division_roster.conf",
    "pairing_precedence_policy.toml", "panel_capacity_workbook.xlsx",
    "appeals_procedure_memo.pdf", "standings_precedence_directive.docx",
    "output_schema_reference.md", "spec_stage_p14_settlement_publication.md",
)

SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DOC_REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PKG_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# The violation level of each screening check, as the P08 table prints it.
VIOLATION_LEVEL = {
    "ineligible_player": 4,
    "holds_bye": 4,
    "cross_division": 3,
    "repeat_opponent": 2,
    "score_band": 1,
}


class PapersError(Exception):
    """The input directory cannot be settled."""


# --------------------------------------------------------------------------
# exact arithmetic
# --------------------------------------------------------------------------


def half_even(value: Fraction) -> int:
    """Round an exact value to an integer, a tie going to the even integer."""
    whole, rest = divmod(value.numerator, value.denominator)
    doubled = 2 * rest
    if doubled > value.denominator or (doubled == value.denominator and whole % 2):
        whole += 1
    return whole


def nine_place_ratio(top: int, bottom: int) -> str:
    if bottom == 0:
        return "0.000000000"
    scaled = half_even(Fraction(top * 10 ** 9, bottom))
    sign = "-" if scaled < 0 else ""
    units, decimals = divmod(abs(scaled), 10 ** 9)
    return "%s%d.%09d" % (sign, units, decimals)


# --------------------------------------------------------------------------
# readers, one per format the papers use
# --------------------------------------------------------------------------


def read_rows(path: Path, delimiter: str) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter, restval=""))


def read_json_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def read_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def read_ticks_per_round(path: Path) -> int:
    match = re.search(r"^\s*ticks_per_round:\s*(\d+)\s*$",
                      path.read_text(encoding="utf-8"), re.MULTILINE)
    if match is None:
        raise PapersError("boundary_conventions.yaml names no ticks_per_round")
    return int(match.group(1))


def read_conf_sections(path: Path) -> list[tuple[str, dict]]:
    """Sections in file order; a section name may repeat."""
    sections: list[tuple[str, dict]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            sections.append((line[1:-1], {}))
        elif "=" in line and sections:
            key, value = line.split("=", 1)
            sections[-1][1][key.strip()] = value.strip()
    return sections


def column_number(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference).group(0)
    number = 0
    for letter in letters:
        number = number * 26 + ord(letter) - ord("A") + 1
    return number - 1


def read_workbook(path: Path) -> dict[str, list[list[str]]]:
    """Every worksheet as a grid of cell texts, keyed by sheet name."""
    with zipfile.ZipFile(path) as archive:
        names = set(archive.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            for item in ET.fromstring(archive.read("xl/sharedStrings.xml")):
                shared.append("".join(node.text or "" for node in item.iter(SHEET_NS + "t")))
        targets = {}
        for rel in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels")).iter(
                PKG_REL_NS + "Relationship"):
            target = rel.get("Target").lstrip("/")
            targets[rel.get("Id")] = target if target.startswith("xl/") else "xl/" + target
        grids = {}
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        for sheet in workbook.iter(SHEET_NS + "sheet"):
            part = ET.fromstring(archive.read(targets[sheet.get(DOC_REL_NS + "id")]))
            grid = []
            for row in part.iter(SHEET_NS + "row"):
                cells: dict[int, str] = {}
                for cell in row.iter(SHEET_NS + "c"):
                    value = cell.find(SHEET_NS + "v")
                    text = value.text if value is not None and value.text else ""
                    if cell.get("t") == "s" and text:
                        text = shared[int(text)]
                    cells[column_number(cell.get("r"))] = text
                width = max(cells) + 1 if cells else 0
                grid.append([cells.get(i, "") for i in range(width)])
            grids[sheet.get("name")] = grid
    return grids


PDF_SHOWN_TEXT = re.compile(rb"\(((?:\\.|[^\\)])*)\)\s*Tj")


def read_pdf_lines(path: Path) -> list[str]:
    """The text shown by every Tj operator of the uncompressed content streams."""
    lines = []
    for match in PDF_SHOWN_TEXT.finditer(path.read_bytes()):
        text = re.sub(rb"\\(.)", rb"\1", match.group(1))
        lines.append(text.decode("latin-1"))
    return lines


def read_word_tables(path: Path) -> list[list[list[str]]]:
    with zipfile.ZipFile(path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
    tables = []
    for table in document.iter(WORD_NS + "tbl"):
        rows = []
        for row in table.iter(WORD_NS + "tr"):
            rows.append(["".join(node.text or "" for node in cell.iter(WORD_NS + "t"))
                         for cell in row.iter(WORD_NS + "tc")])
        tables.append(rows)
    return tables


def read_schema(path: Path) -> dict[str, list[str]]:
    """The header or key list of every document the schema reference describes."""
    columns: dict[str, list[str]] = {}
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^## (\S+)$", line)
        if heading:
            current = heading.group(1)
            continue
        listing = re.match(r"^- (?:header|keys|structure): (.+)$", line)
        if listing and current:
            columns[current] = [name.strip() for name in listing.group(1).split(",")]
    return columns


def read_contract_order(path: Path) -> list[str]:
    """The artifact contract order the settlement specification prints."""
    text = path.read_text(encoding="utf-8")
    section = text.split("## The artifact contract order", 1)
    if len(section) != 2:
        raise PapersError("the settlement specification prints no artifact contract order")
    return re.findall(r"^\s*\d+\.\s+(\S+)\s*$", section[1], re.MULTILINE)


# --------------------------------------------------------------------------
# the event as the papers state it
# --------------------------------------------------------------------------


@dataclass
class Event:
    folder: Path
    event_id: str = ""
    reference: str = ""
    rounds: int = 0
    divisions: list[str] = field(default_factory=list)
    absent: str = ""
    precedence: dict = field(default_factory=dict)
    capacity: dict = field(default_factory=dict)
    clauses: dict = field(default_factory=dict)
    families: dict = field(default_factory=dict)
    division_rank: dict = field(default_factory=dict)
    report_order: dict = field(default_factory=dict)

    def rows(self, name: str, delimiter: str) -> list[dict]:
        return [row for row in read_rows(self.folder / name, delimiter)
                if row.get("event_reference") == self.reference]

    def admits(self, section: str, status: str) -> bool:
        rule = self.precedence[section]
        if status in rule.get("excluded_status", []):
            return False
        allowed = rule.get("applicable_status")
        return allowed is None or status in allowed

    def clause_int(self, key: str) -> int:
        return int(self.clauses[key])


def open_event(folder: Path) -> Event:
    missing = [name for name in REQUIRED_PAPERS if not (folder / name).is_file()]
    if missing:
        raise PapersError("required papers missing: " + ", ".join(missing))
    event = Event(folder)
    topology = ET.parse(folder / "division_topology.xml").getroot()
    event.event_id = topology.findtext("identity/event_id")
    event.reference = topology.findtext("identity/event_reference")
    event.rounds = int(topology.findtext("identity/round_count"))
    event.divisions = [node.get("id") for node in topology.iter("division")
                       if node.get("in_force") == "yes"]
    event.absent = read_toml(folder / "settlement_form_rules.toml")["markers"]["absent"]
    event.precedence = read_toml(folder / "revision_precedence.toml")
    event.capacity = live_capacity(read_workbook(folder / "panel_capacity_workbook.xlsx"),
                                   event.reference)
    event.clauses = operative_clauses(read_pdf_lines(folder / "appeals_procedure_memo.pdf"),
                                      event.reference)
    event.families, event.division_rank = directive_registers(
        read_word_tables(folder / "standings_precedence_directive.docx"), event.reference)
    for name, values in read_conf_sections(folder / "reporting_division_roster.conf"):
        if not name.startswith("division:"):
            continue
        if values.get("event_reference") != event.reference:
            continue
        if not event.admits("reporting_roster", values.get("record_status", "")):
            continue
        event.report_order[name.split(":", 1)[1]] = int(values["report_order"])
    return event


def live_capacity(grids: dict, reference: str) -> dict[str, dict]:
    """The operative parameter rows of the sheet whose key cell names this event."""
    for grid in grids.values():
        key_rows = [row for row in grid if row[:1] == ["sheet_reference"]]
        if not key_rows or len(key_rows[0]) < 2 or key_rows[0][1] != reference:
            continue
        parameters: dict[str, dict] = {}
        header = None
        for row in grid:
            if row[:1] == ["parameter"]:
                header = row
            elif header and row and row[0]:
                record = dict(zip(header, row))
                if record.get("status") == "operative" and "value" in record:
                    parameters.setdefault(record["parameter"], record)
        return parameters
    raise PapersError("no capacity sheet carries the event reference " + reference)


def operative_clauses(lines: list[str], reference: str) -> dict[str, str]:
    clauses = {}
    for line in lines:
        parts = line.split()
        if len(parts) >= 5 and parts[0].startswith("CL-") and parts[1] == "operative" \
                and parts[2] == reference:
            clauses[parts[3]] = parts[4]
    return clauses


def directive_registers(tables: list, reference: str) -> tuple[dict, dict]:
    families: dict[str, list[tuple[int, str]]] = {}
    ranks: dict[str, int] = {}
    for table in tables:
        if not table:
            continue
        header = table[0]
        for row in table[1:]:
            record = dict(zip(header, row))
            if record.get("status") != "operative" or record.get("event_reference") != reference:
                continue
            if "key_family" in record:
                families.setdefault(record["key_family"], []).append(
                    (int(record["key_position"]), record["key_name"]))
            elif "division_rank" in record:
                ranks[record["division_id"]] = int(record["division_rank"])
    return {name: [key for _pos, key in sorted(keys)] for name, keys in families.items()}, ranks


# --------------------------------------------------------------------------
# P01 entry normalisation
# --------------------------------------------------------------------------


@dataclass
class Entrant:
    player_id: str
    division_id: str
    rating_mr: int
    rating_source: str
    entry_seq: int
    membership_ref: str
    folded_ids: list[str]
    seed_number: int = 0


class IdentifierClosure:
    def __init__(self, alias_rows: list[dict]):
        self.next_id = {row["alias_id"]: row["canonical_id"] for row in alias_rows}
        self.memo: dict[str, str] = {}

    def resolve(self, identifier: str) -> str:
        if identifier in self.memo:
            return self.memo[identifier]
        walk = [identifier]
        while walk[-1] in self.next_id:
            step = self.next_id[walk[-1]]
            if step in walk:
                answer = min(walk[walk.index(step):])
                break
            walk.append(step)
        else:
            answer = walk[-1]
        for member in walk:
            self.memo[member] = answer
        return answer


def normalise_entries(event: Event, closure: IdentifierClosure) -> dict[str, Entrant]:
    units = read_toml(event.folder / "unit_register_dictionary.toml")["unit"]
    filings: dict[str, list[dict]] = {}
    for row in event.rows("entry_roster_register.csv", ","):
        if event.admits("entry_roster", row["entry_status"]):
            filings.setdefault(closure.resolve(row["entry_id"]), []).append(row)

    latest_return: dict[str, dict] = {}
    for row in event.rows("rating_return_sheet.psv", "|"):
        if not event.admits("rating_return", row["return_status"]):
            continue
        who = closure.resolve(row["player_ref"])
        if who not in latest_return or int(row["return_seq"]) > int(latest_return[who]["return_seq"]):
            latest_return[who] = row

    defaults = {row["division_id"]: int(row["value"])
                for row in event.rows("division_admission_matrix.csv", ",")
                if row["parameter"] == "default_rating_mr" and int(row["round_no"]) == 1}

    entrants = {}
    for who, rows in filings.items():
        governing = max(rows, key=lambda row: (int(row["revision_seq"]), int(row["entry_seq"])))
        division = governing["division_id"]
        if division not in event.divisions:
            continue
        if who in latest_return:
            value, unit, source = (latest_return[who]["quoted_value"],
                                   latest_return[who]["quoted_unit"], "return")
        else:
            value, unit, source = governing["quoted_rating"], governing["rating_unit"], "roster"
        if value.strip() == event.absent:
            rating, source = defaults[division], "default"
        else:
            entry = units[unit]
            rating = half_even(Fraction(int(value) * entry["numerator"], entry["denominator"]))
        entrants[who] = Entrant(
            player_id=who, division_id=division, rating_mr=rating, rating_source=source,
            entry_seq=int(governing["entry_seq"]), membership_ref=governing["membership_ref"],
            folded_ids=sorted({row["entry_id"] for row in rows} - {who}))

    seat_order = sorted(entrants.values(), key=lambda e: (-e.rating_mr, e.player_id))
    for number, entrant in enumerate(seat_order, start=1):
        entrant.seed_number = number
    return dict(sorted(entrants.items()))


# --------------------------------------------------------------------------
# P02 participation state
# --------------------------------------------------------------------------


def participation_states(event, closure, entrants) -> dict[tuple[str, int], tuple[str, str, int]]:
    ticks = read_ticks_per_round(event.folder / "boundary_conventions.yaml")
    journal: dict[str, list[tuple[int, int, str]]] = {}
    for row in event.rows("status_change_journal.tsv", "\t"):
        who = closure.resolve(row["player_ref"])
        if who in entrants:
            journal.setdefault(who, []).append(
                (int(row["tick"]) // ticks + 1, int(row["note_seq"]), row["change_code"]))

    standings: dict[str, list[tuple[int, int, str]]] = {}
    for row in event.rows("membership_standing_register.csv", ","):
        if event.admits("membership_standing", row["standing_code"]):
            standings.setdefault(row["membership_ref"], []).append(
                (int(row["effective_round"]), int(row["notice_seq"]), row["standing_code"]))

    expulsion: dict[str, tuple[int, int]] = {}
    for row in event.rows("penalty_notice_register.psv", "|"):
        if row["penalty_class"] != "expulsion" or not event.admits("penalty_notice", row["notice_status"]):
            continue
        who = closure.resolve(row["player_ref"])
        if who in entrants:
            mark = (int(row["effective_round"]), int(row["notice_seq"]))
            expulsion[who] = min(expulsion.get(who, mark), mark)

    states = {}
    for who, entrant in entrants.items():
        changes = sorted(journal.get(who, []))
        cards = sorted(standings.get(entrant.membership_ref, []))
        for round_no in range(1, event.rounds + 1):
            state, code, seq = "seated", "none", 0
            for change_round, note_seq, change in changes:
                if change_round > round_no:
                    break
                if change == "drop":
                    state, code, seq = "dropped", change, note_seq
                elif change in ("reentry", "reinstate"):
                    state, code, seq = "seated", change, note_seq
                elif change == "absence" and change_round == round_no:
                    state, code, seq = "absent", change, note_seq
            reached = [card for card in cards if card[0] <= round_no]
            if reached and reached[-1][2] == "lapsed":
                state, code, seq = "barred", "lapsed", reached[-1][1]
            if who in expulsion and expulsion[who][0] <= round_no:
                state, code, seq = "barred", "expulsion", expulsion[who][1]
            states[(who, round_no)] = (state, code, seq)
    return states


# --------------------------------------------------------------------------
# P03 candidate boards and P04 evidence
# --------------------------------------------------------------------------


@dataclass
class Board:
    round_no: int
    table_no: int
    player_a: str
    player_b: str
    sheet_revision: int
    source_seq: int
    result_code: str = ""
    basis: str = ""
    games_a: int = 0
    games_b: int = 0
    void: tuple | None = None

    @property
    def delta_a(self) -> int:
        return self.games_a - self.games_b

    def holds(self, who: str) -> bool:
        return who in (self.player_a, self.player_b)


def candidate_boards(event, closure, entrants) -> list[Board]:
    governing: dict[tuple[int, int], dict] = {}
    for row in event.rows("recorded_pairing_table.csv", ","):
        if not event.admits("recorded_pairing", row["pairing_status"]):
            continue
        slot = (int(row["round_no"]), int(row["table_no"]))
        rank = (int(row["sheet_revision"]), int(row["source_seq"]))
        held = governing.get(slot)
        if held is None or rank > (int(held["sheet_revision"]), int(held["source_seq"])):
            governing[slot] = row
    boards = []
    for (round_no, table_no), row in sorted(governing.items()):
        first, second = closure.resolve(row["player_a"]), closure.resolve(row["player_b"])
        if first in entrants and second in entrants and first != second:
            boards.append(Board(round_no, table_no, first, second,
                                int(row["sheet_revision"]), int(row["source_seq"])))
    return boards


def resolve_evidence(event: Event, boards: list[Board]) -> None:
    sheets: dict[tuple[int, int], dict] = {}
    for record in read_json_lines(event.folder / "match_result_sheets.ndjson"):
        if record.get("event_reference") != event.reference:
            continue
        if not event.admits("result_sheet", record.get("sheet_status")):
            continue
        slot = (int(record["round_no"]), int(record["table_no"]))
        if slot not in sheets or int(record["sheet_seq"]) > int(sheets[slot]["sheet_seq"]):
            sheets[slot] = record
    games: dict[tuple[int, int], list[dict]] = {}
    for row in event.rows("game_records.csv", ","):
        games.setdefault((int(row["round_no"]), int(row["table_no"])), []).append(row)
    ranked = sorted((row for row in event.rows("source_priority_register.csv", ",")
                     if row["record_status"] == "operative"),
                    key=lambda row: int(row["priority_rank"]))
    levels = [row["source_code"] for row in ranked]

    def present(value) -> bool:
        return str(value) != event.absent

    def count_result(first: int, second: int) -> str:
        return "win_a" if first > second else "win_b" if second > first else "draw"

    for board in boards:
        sheet = sheets.get((board.round_no, board.table_no), {})
        played = games.get((board.round_no, board.table_no), [])
        board.games_a = sum(1 for g in played if g["outcome"] == "won_a" and g["completed"] == "yes")
        board.games_b = sum(1 for g in played if g["outcome"] == "won_b" and g["completed"] == "yes")
        concessions = {g["outcome"] for g in played if g["outcome"].startswith("conceded_")}
        adjudicated = sheet.get("adjudicated_result", event.absent)
        declared = (sheet.get("declared_games_a", event.absent),
                    sheet.get("declared_games_b", event.absent))
        deciders = {
            "sheet_adjudication": lambda: adjudicated if present(adjudicated) else None,
            "game_concession": lambda: (
                None if not concessions else "double_loss" if len(concessions) == 2
                else "win_b" if "conceded_a" in concessions else "win_a"),
            "completed_game": lambda: (count_result(board.games_a, board.games_b)
                                       if board.games_a or board.games_b else None),
            "declared_count": lambda: (count_result(int(declared[0]), int(declared[1]))
                                       if all(present(v) for v in declared) else None),
            "no_evidence": lambda: "double_loss",
        }
        for level in levels:
            outcome = deciders[level]()
            if outcome is not None:
                board.result_code, board.basis = outcome, level
                break


# --------------------------------------------------------------------------
# P05 to P11, one round at a time
# --------------------------------------------------------------------------


@dataclass
class Standing:
    """The closed figures an entrant carries into the round that opens."""
    points: int = 0
    delta: int = 0
    byes: int = 0
    opponents: set = field(default_factory=set)


def key_order(family: list[str], value_of):
    """A sort key applying the named keys in turn, each with its direction."""
    parsed = []
    for name in family:
        subject, direction = name.rsplit("_", 1)
        parsed.append((subject, direction == "descending"))

    def compare(left: str, right: str) -> int:
        for subject, descending in parsed:
            a, b = value_of(subject, left), value_of(subject, right)
            if a != b:
                return (-1 if a < b else 1) * (-1 if descending else 1)
        return 0

    return functools.cmp_to_key(compare)


class RoundLoop:
    def __init__(self, event, closure, entrants, states, boards):
        self.event = event
        self.entrants = entrants
        self.states = states
        self.boards_by_round: dict[int, list[Board]] = {}
        for board in boards:
            self.boards_by_round.setdefault(board.round_no, []).append(board)
        self.standing = {who: Standing() for who in entrants}

        matrix = event.rows("division_admission_matrix.csv", ",")
        self.matrix = {(r["division_id"], int(r["round_no"]), r["parameter"]): r["value"]
                       for r in matrix}
        config = event.rows("round_configuration_register.csv", ",")
        self.config = {(int(r["round_no"]), r["division_id"], r["parameter"]): r["value"]
                       for r in config}
        modifiers = json.loads((event.folder / "round_modifier_rules.json").read_text(encoding="utf-8"))
        self.modifier = {code["code"]: Fraction(code["numerator"], code["denominator"])
                         for code in modifiers["codes"]}
        policy = read_toml(event.folder / "pairing_precedence_policy.toml")
        self.levels = int(policy["admission"]["levels"])
        self.tolerance = policy["tolerance"]
        self.rungs = [event.clauses["relaxation_rung_%d" % i] for i in range(1, self.levels)]
        self.score_band = int(event.capacity["score_band"]["value"])
        self.max_byes = int(event.capacity["max_byes"]["value"])

        self.notices: dict[tuple[str, int, str], list[tuple[int, int]]] = {}
        self.tournament: dict[str, list[tuple[int, int]]] = {}
        applied = {event.clauses["penalty_order_%d" % i] for i in range(1, 5)}
        for row in event.rows("penalty_notice_register.psv", "|"):
            cls = row["penalty_class"]
            if cls not in applied or not event.admits("penalty_notice", row["notice_status"]):
                continue
            who = closure.resolve(row["player_ref"])
            if who not in entrants:
                continue
            notice = (int(row["notice_seq"]), int(row["magnitude"]))
            if cls == "tournament":
                self.tournament.setdefault(who, []).append(notice)
            else:
                self.notices.setdefault((who, int(row["effective_round"]), cls), []).append(notice)

        self.eligibility_rows, self.bye_rows, self.pairing_rows = [], [], []
        self.fallback_rows, self.unpaired_rows, self.void_rows = [], [], []
        self.score_rows, self.penalty_rows, self.history_rows = [], [], []
        self.round_reports = []
        self.round_score: dict[tuple[str, int], tuple[str, int, int]] = {}
        self.raw_delta = {who: 0 for who in entrants}
        self.game_units = {who: 0 for who in entrants}
        self.rounds_counted = {who: 0 for who in entrants}

    # -- keys -----------------------------------------------------------

    def value_of(self, subject: str, who: str):
        standing = self.standing[who]
        return {
            "running_points": lambda: standing.points,
            "running_differential": lambda: standing.delta,
            "byes_received": lambda: standing.byes,
            "seat_order": lambda: self.entrants[who].seed_number,
            "division_rank": lambda: self.event.division_rank[self.entrants[who].division_id],
            "player_id": lambda: who,
        }[subject]()

    def ordered(self, family: str, members: list[str]) -> list[str]:
        return sorted(members, key=key_order(self.event.families[family], self.value_of))

    def effective_band(self, division: str, round_no: int) -> int:
        widening = self.matrix.get((division, round_no, "band_widening"), "0")
        return self.score_band + int(widening)

    def cross_admitted(self, division: str, round_no: int) -> bool:
        return self.matrix.get((division, round_no, "cross_admitted")) == "yes"

    # -- the loop -------------------------------------------------------

    def run(self) -> None:
        for round_no in range(1, self.event.rounds + 1):
            eligible = self.open_round(round_no)
            bye_holders = self.award_byes(round_no, eligible)
            levels, unpaired = self.pair(round_no, eligible, bye_holders)
            voids = self.screen(round_no, eligible, bye_holders, levels)
            self.score(round_no, eligible, bye_holders, voids, unpaired)
            self.record_encounters(round_no, eligible, voids)
            self.close(round_no, bye_holders)

    def open_round(self, round_no: int) -> set[str]:
        eligible = set()
        for who, entrant in self.entrants.items():
            state = self.states[(who, round_no)][0]
            if state == "seated":
                eligible.add(who)
            standing = self.standing[who]
            self.eligibility_rows.append([round_no, who, entrant.division_id,
                                          "yes" if state == "seated" else "no", state,
                                          standing.points, standing.delta])
        self.report = {"round_no": round_no}
        return eligible

    def award_byes(self, round_no: int, eligible: set[str]) -> dict[str, str]:
        holders = {}
        for division in self.event.divisions:
            members = sorted(w for w in eligible if self.entrants[w].division_id == division)
            if len(members) % 2 == 0:
                continue
            candidates = [w for w in members if self.standing[w].byes < self.max_byes]
            basis = "normal"
            if not candidates:
                if self.matrix.get((division, round_no, "bye_override")) != "yes":
                    continue
                candidates, basis = members, "cap_override"
            chosen = self.ordered("bye_order", candidates)[0]
            holders[chosen] = division
            self.bye_rows.append([round_no, division, chosen, self.standing[chosen].byes, basis])
        self.report["byes"] = len(holders)
        return holders

    def admissible(self, round_no: int, first: str, partner: str, level: int) -> bool:
        set_aside = set(self.rungs[:level])
        div_first = self.entrants[first].division_id
        div_partner = self.entrants[partner].division_id
        if div_first != div_partner:
            if "division" not in set_aside:
                return False
            if not (self.cross_admitted(div_first, round_no)
                    and self.cross_admitted(div_partner, round_no)):
                return False
        if "score_band" not in set_aside:
            gap = abs(self.standing[first].points - self.standing[partner].points)
            if gap > self.effective_band(div_first, round_no):
                return False
        if "repeat_opponent" not in set_aside and partner in self.standing[first].opponents:
            return False
        return True

    def pair(self, round_no, eligible, bye_holders) -> tuple[dict[str, int], set[str]]:
        levels = {who: int(self.tolerance["bye_holder"]) for who in bye_holders}
        waiting = self.ordered("pairing_order", [w for w in eligible if w not in bye_holders])
        unpaired: set[str] = set()
        counts = {level: 0 for level in range(self.levels)}
        board_no = cross = repeats = 0
        while waiting:
            first = waiting.pop(0)
            match = next(((level, partner) for level in range(self.levels)
                          for partner in waiting
                          if self.admissible(round_no, first, partner, level)), None)
            if match is None:
                unpaired.add(first)
                levels[first] = int(self.tolerance["unpaired"])
                self.unpaired_rows.append([round_no, self.entrants[first].division_id, first,
                                           self.standing[first].points, "no_admissible_partner"])
                continue
            level, partner = match
            waiting.remove(partner)
            board_no += 1
            levels[first] = levels[partner] = level
            counts[level] += 1
            div_a, div_b = self.entrants[first].division_id, self.entrants[partner].division_id
            cross += div_a != div_b
            repeats += partner in self.standing[first].opponents
            self.pairing_rows.append([round_no, board_no, first, partner, div_a, div_b, level,
                                      self.standing[first].points, self.standing[partner].points])
            if level:
                self.fallback_rows.append([round_no, board_no, first, partner, level,
                                           "+".join(self.rungs[:level])])
        self.report.update({
            "boards": board_no, "unpaired": len(unpaired),
            "level_counts": {"level_%d" % level: counts[level] for level in range(self.levels)},
            "cross_division_boards": cross, "repeat_boards": repeats})
        return levels, unpaired

    def screen(self, round_no, eligible, bye_holders, levels) -> dict[int, Board]:
        outside = int(self.tolerance["ineligible"])
        reason_order = self.event.families["void_reason"]
        voids = {}
        for board in self.boards_by_round.get(round_no, []):
            a, b = board.player_a, board.player_b
            breached = set()
            if a not in eligible or b not in eligible:
                breached.add("ineligible_player")
            if a in bye_holders or b in bye_holders:
                breached.add("holds_bye")
            if self.entrants[a].division_id != self.entrants[b].division_id:
                breached.add("cross_division")
            if b in self.standing[a].opponents:
                breached.add("repeat_opponent")
            gap = abs(self.standing[a].points - self.standing[b].points)
            if gap > self.effective_band(self.entrants[a].division_id, round_no):
                breached.add("score_band")
            tolerance = min(levels.get(a, outside), levels.get(b, outside))
            voiding = [name for name in reason_order
                       if name in breached and VIOLATION_LEVEL[name] > tolerance]
            if voiding:
                voids[board.table_no] = board
                board.void = (voiding[0], VIOLATION_LEVEL[voiding[0]], tolerance)
        self.report["voided_boards"] = len(voids)
        return voids

    def notice_total(self, who, round_no, cls):
        found = self.notices.get((who, round_no, cls), [])
        if not found:
            return None
        return sum(m for _s, m in found), min(s for s, _m in found)

    def score(self, round_no, eligible, bye_holders, voids, unpaired) -> None:
        clause = self.event.clause_int
        boards = sorted(self.boards_by_round.get(round_no, []), key=lambda b: b.table_no)
        for who in sorted(eligible):
            division = self.entrants[who].division_id
            points = {name: int(self.config.get((round_no, division, name + "_points"), 0))
                      for name in ("win", "draw", "loss")}
            board = next((b for b in boards if b.holds(who)), None)
            if who in bye_holders:
                basis, base, delta = "bye", clause("bye_points"), clause("bye_game_delta")
            elif board is not None and board.table_no in voids:
                basis, base, delta = "void", clause("void_points"), 0
            elif board is not None:
                basis = "match"
                on_a = board.player_a == who
                code = board.result_code
                if code == "draw":
                    base = points["draw"]
                elif code == "double_loss":
                    base = points["loss"]
                else:
                    winner_is_a = code == "win_a"
                    base = points["win"] if winner_is_a == on_a else points["loss"]
                delta = board.delta_a if on_a else -board.delta_a
            elif who in unpaired:
                basis, base, delta = "unpaired", clause("unpaired_points"), 0
            else:
                basis, base, delta = "no_record", clause("no_record_points"), 0

            self.raw_delta[who] += delta
            game = self.notice_total(who, round_no, "game")
            if game:
                self.penalty_rows.append([round_no, who, "game", game[0], game[1],
                                          delta, delta - game[0], 0])
                delta -= game[0]
                self.game_units[who] += game[0]
            match = self.notice_total(who, round_no, "match")
            if match:
                self.penalty_rows.append([round_no, who, "match", match[0], match[1],
                                          base, points["loss"], 0])
                base = points["loss"]
            code = self.config[(round_no, division, "modifier_code")]
            modified = half_even(base * self.modifier[code])
            final = modified
            penalty = self.notice_total(who, round_no, "round")
            if penalty:
                final = max(clause("round_points_floor"), modified - penalty[0])
                shortfall = penalty[0] - modified if penalty[0] > modified else 0
                self.penalty_rows.append([round_no, who, "round", penalty[0], penalty[1],
                                          modified, final, shortfall])
            self.score_rows.append([round_no, who, division, basis, base, code, modified,
                                    final, delta])
            self.round_score[(who, round_no)] = (basis, final, delta, base)
            self.rounds_counted[who] += 1

        for table_no in sorted(voids):
            board = voids[table_no]
            reason, level, tolerance = board.void
            credited = [self.round_score[(w, round_no)][3] if (w, round_no) in self.round_score
                        else self.event.absent for w in (board.player_a, board.player_b)]
            self.void_rows.append([round_no, table_no, board.player_a, board.player_b,
                                   reason, level, tolerance, *credited])

    def record_encounters(self, round_no, eligible, voids) -> None:
        for board in self.boards_by_round.get(round_no, []):
            a, b = board.player_a, board.player_b
            if a not in eligible or b not in eligible:
                continue
            counts = "no" if board.table_no in voids else "yes"
            self.history_rows.append([round_no, a, b, counts, "board"])
            self.history_rows.append([round_no, b, a, counts, "board"])
            self.standing[a].opponents.add(b)
            self.standing[b].opponents.add(a)

    def close(self, round_no, bye_holders) -> None:
        for (who, closed_round), (_basis, final, delta, _base) in self.round_score.items():
            if closed_round == round_no:
                self.standing[who].points += final
                self.standing[who].delta += delta
        for who in bye_holders:
            self.standing[who].byes += 1
        report = self.report
        self.round_reports.append({key: report[key] for key in (
            "round_no", "boards", "byes", "unpaired", "level_counts",
            "cross_division_boards", "repeat_boards", "voided_boards")})


# --------------------------------------------------------------------------
# P10 to P14, over the closed event
# --------------------------------------------------------------------------


@dataclass
class Closing:
    event_points: dict
    penalty_units: dict
    rate: dict
    strength_rows: dict
    strength: dict
    adjusted_strength: dict
    adjusted_delta: dict
    ranking: list
    rank_of: dict
    eligible: dict


def close_event(event: Event, loop: RoundLoop) -> Closing:
    rules = json.loads((event.folder / "tiebreak_rules.json").read_text(encoding="utf-8"))
    debit = int(event.capacity["strength_debit"]["value"])
    scale = int(rules["rate_scale"])
    zero = int(rules["zero_strength_value"])
    floor = int(rules["penalty_adjusted_strength"]["floor"])

    event_points, units = {}, {}
    for who in loop.entrants:
        closed = loop.standing[who].points
        notices = loop.tournament.get(who, [])
        units[who] = sum(m for _s, m in notices)
        event_points[who] = max(0, closed - units[who])
        if notices:
            shortfall = units[who] - closed if units[who] > closed else 0
            loop.penalty_rows.append([0, who, "tournament", units[who],
                                      min(s for s, _m in notices), closed,
                                      event_points[who], shortfall])

    rate = {who: half_even(Fraction(event_points[who] * scale, max(1, loop.rounds_counted[who])))
            for who in loop.entrants}
    population: dict[str, set] = {who: set() for who in loop.entrants}
    for _r, who, opponent, counts, _source in loop.history_rows:
        if counts == "yes":
            population[who].add(opponent)
    strength, adjusted, rows = {}, {}, {}
    for who, members in population.items():
        total = sum(rate[m] for m in members)
        strength[who] = half_even(Fraction(total, len(members))) if members else zero
        adjusted[who] = max(floor, strength[who] - debit * units[who])
        rows[who] = [who, len(members), total, strength[who], units[who], adjusted[who]]
    adjusted_delta = {who: loop.raw_delta[who] - loop.game_units[who] for who in loop.entrants}

    values = {
        "event_points": event_points,
        "adjusted_game_differential": adjusted_delta,
        "opponent_strength": strength,
        "penalty_adjusted_strength": adjusted,
    }
    directions = {item["key"]: item["direction"] for item in rules["ordering"]}
    family = event.families["tiebreak"]
    named = [name + "_" + directions[name] for name in family]
    ranking = sorted(loop.entrants, key=key_order(
        named, lambda subject, who: who if subject == "player_id" else values[subject][who]))
    disqualify = event.clause_int("prize_disqualify_units")
    return Closing(event_points, units, rate, rows, strength, adjusted, adjusted_delta, ranking,
                   {who: i for i, who in enumerate(ranking, start=1)},
                   {who: units[who] < disqualify for who in loop.entrants})


def tiebreak_value(closing: Closing, key: str, who: str):
    return {
        "event_points": closing.event_points,
        "adjusted_game_differential": closing.adjusted_delta,
        "opponent_strength": closing.strength,
        "penalty_adjusted_strength": closing.adjusted_strength,
    }[key][who] if key != "player_id" else who


@dataclass
class Prize:
    pool: int
    allocation: list
    splits: list
    awarded: dict
    awarded_total: int


def settle_prizes(event: Event, closing: Closing) -> Prize:
    rules = json.loads((event.folder / "prize_rules.json").read_text(encoding="utf-8"))
    share = {int(row["rank"]): int(row["basis_points"]) for row in rules["share_table"]}
    pool = int(event.capacity["pool_cents"]["value"])
    keys = event.families["tiebreak"][:event.clause_int("tie_group_depth")]

    groups: list[list[str]] = []
    for who in closing.ranking:
        if groups and all(tiebreak_value(closing, k, groups[-1][-1]) == tiebreak_value(closing, k, who)
                          for k in keys):
            groups[-1].append(who)
        else:
            groups.append([who])

    allocation, splits, awarded = [], [], {}
    for group_id, members in enumerate(groups, start=1):
        ranks = [closing.rank_of[w] for w in members]
        basis_points = sum(share.get(r, 0) for r in ranks)
        if basis_points == 0:
            continue
        amount = half_even(Fraction(pool * basis_points, 10000))
        base_share, remainder = divmod(amount, len(members))
        cent = {w: int(i < remainder) for i, w in enumerate(sorted(members))}
        for who in members:
            paid = base_share + cent[who] if closing.eligible[who] else 0
            awarded[who] = paid
            allocation.append([closing.rank_of[who], who, group_id, basis_points, amount,
                               len(members), base_share, cent[who],
                               "yes" if closing.eligible[who] else "no", paid])
        if len(members) > 1:
            splits.append([group_id, "%d+%d" % (min(ranks), max(ranks)), len(members),
                           basis_points, amount, base_share, remainder,
                           "+".join(sorted(members))])
    return Prize(pool, allocation, splits, awarded, sum(awarded.values()))


# --------------------------------------------------------------------------
# publication
# --------------------------------------------------------------------------


class Publisher:
    def __init__(self, event, out: Path):
        self.event = event
        self.out = out
        self.schema = read_schema(event.folder / "output_schema_reference.md")
        self.contract = read_contract_order(
            event.folder / "spec_stage_p14_settlement_publication.md")
        self.documents: dict[str, bytes] = {}

    def text(self, name: str, lines: list[str]) -> None:
        self.documents[name] = ("\n".join(lines) + "\n").encode("utf-8")

    def delimited(self, name: str, rows: list[list], delimiter: str) -> None:
        lines = [delimiter.join(self.schema[name])]
        lines += [delimiter.join("" if v is None else str(v) for v in row) for row in rows]
        self.text(name, lines)

    def json_document(self, name: str, payload: dict) -> None:
        self.documents[name] = (json.dumps(payload, indent=1) + "\n").encode("utf-8")

    def json_lines(self, name: str, records: list[dict]) -> None:
        self.text(name, [json.dumps(r, separators=(",", ":")) for r in records])

    def keyed(self, name: str, values: dict) -> dict:
        return {key: values[key] for key in self.schema[name]}

    def manifest(self, core: list[str]) -> None:
        listed = [name for name in self.contract]
        core_bytes = b"".join(self.documents[name] for name in listed if name in core)
        rest_bytes = b"".join(self.documents[name] for name in listed if name not in core)
        self.json_document("settlement_manifest.json", self.keyed("settlement_manifest.json", {
            "event_id": self.event.event_id,
            "event_reference": self.event.reference,
            "round_count": self.event.rounds,
            "player_count": self.player_count,
            "core_digest": hashlib.sha256(core_bytes).hexdigest(),
            "publication_digest": hashlib.sha256(rest_bytes).hexdigest(),
            "documents": [{"name": name, "sha256": hashlib.sha256(self.documents[name]).hexdigest(),
                           "bytes": len(self.documents[name])} for name in listed],
        }))

    def write(self) -> None:
        self.out.mkdir(parents=True, exist_ok=True)
        for name, payload in self.documents.items():
            (self.out / name).write_bytes(payload)


def publish(event, entrants, states, boards, loop, closing, prize, out: Path) -> None:
    pub = Publisher(event, out)
    pub.player_count = len(entrants)
    ranked = closing.ranking

    pub.json_lines("normalised_entries.jsonl", [
        pub.keyed("normalised_entries.jsonl", vars(e)) for e in entrants.values()])
    pub.delimited("participation_ledger.csv", [
        [who, r, *states[(who, r)]] for who in entrants for r in range(1, event.rounds + 1)], ",")
    pub.delimited("round_match_candidates.csv", [
        [b.round_no, b.table_no, b.player_a, b.player_b, b.sheet_revision, b.source_seq]
        for b in boards], ",")
    pub.delimited("match_result_ledger.csv", [
        [b.round_no, b.table_no, b.player_a, b.player_b, b.result_code, b.basis,
         b.games_a, b.games_b, b.delta_a] for b in boards], ",")
    pub.delimited("round_eligibility_ledger.csv", loop.eligibility_rows, ",")
    pub.delimited("bye_ledger.csv", sorted(loop.bye_rows, key=lambda r: (r[0], r[1])), ",")
    pub.delimited("authoritative_pairing_ledger.csv", loop.pairing_rows, ",")
    pub.delimited("void_adjudication_ledger.csv", loop.void_rows, ",")
    pub.delimited("round_score_ledger.csv", loop.score_rows, ",")
    class_rank = {event.clauses["penalty_order_%d" % i]: i for i in range(1, 5)}
    pub.delimited("penalty_application_ledger.psv", sorted(
        loop.penalty_rows, key=lambda r: (r[0], r[1], class_rank[r[2]])), "|")
    pub.delimited("opponent_history_ledger.csv",
                  sorted(loop.history_rows, key=lambda r: (r[0], r[1], r[2])), ",")
    pub.delimited("opponent_strength_ledger.csv",
                  [closing.strength_rows[w] for w in entrants], ",")
    pub.delimited("standings_ledger.csv", [
        [closing.rank_of[w], w, entrants[w].division_id, closing.event_points[w],
         closing.adjusted_delta[w], closing.strength[w], closing.adjusted_strength[w],
         closing.penalty_units[w], "yes" if closing.eligible[w] else "no"] for w in ranked], ",")

    pub.delimited("pairing_fallback_ledger.csv", loop.fallback_rows, ",")
    meetings: dict[tuple[str, str], list[int]] = {}
    for r, who, opponent, _c, _s in loop.history_rows:
        meetings.setdefault((who, opponent), []).append(r)
    pub.delimited("repeat_opponent_audit.tsv", [
        [who, opp, len(rs), "+".join(str(r) for r in sorted(rs))]
        for (who, opp), rs in sorted(meetings.items()) if len(rs) > 1], "\t")
    pub.delimited("unpaired_ledger.tsv",
                  sorted(loop.unpaired_rows, key=lambda r: (r[0], r[2])), "\t")
    pub.json_document("pairing_constraint_report.json", pub.keyed(
        "pairing_constraint_report.json",
        {"event_reference": event.reference, "rounds": loop.round_reports}))

    pub.delimited("game_differential_ledger.psv", [
        [w, loop.rounds_counted[w], loop.raw_delta[w], loop.game_units[w],
         closing.adjusted_delta[w]] for w in entrants], "|")
    family = event.families["tiebreak"]
    separations = []
    for spot in range(len(ranked) - 1):
        here, there = ranked[spot], ranked[spot + 1]
        position = next((i for i, key in enumerate(family, start=1)
                         if tiebreak_value(closing, key, here) != tiebreak_value(closing, key, there)),
                        len(family))
        separations.append([spot + 1, here, there, position, family[position - 1]])
    pub.delimited("tiebreak_resolution_ledger.csv", separations, ",")
    pub.json_document("final_ranking.json", pub.keyed("final_ranking.json", {
        "event_id": event.event_id, "event_reference": event.reference,
        "round_count": event.rounds, "player_count": len(entrants),
        "ranking": [{"rank": closing.rank_of[w], "player_id": w,
                     "event_points": closing.event_points[w],
                     "adjusted_delta": closing.adjusted_delta[w],
                     "opponent_strength": closing.strength[w],
                     "penalty_adjusted_strength": closing.adjusted_strength[w]} for w in ranked]}))

    def round_trace(who, r):
        if (who, r) in loop.round_score:
            basis, final, delta, _base = loop.round_score[(who, r)]
        else:
            basis, final, delta = "none", 0, 0
        return {"round_no": r, "state": states[(who, r)][0], "basis": basis,
                "round_points": final, "game_delta": delta}

    pub.json_lines("player_audit_trace.jsonl", [pub.keyed("player_audit_trace.jsonl", {
        "player_id": w, "division_id": e.division_id, "seed_number": e.seed_number,
        "rounds": [round_trace(w, r) for r in range(1, event.rounds + 1)],
        "event_points": closing.event_points[w], "adjusted_delta": closing.adjusted_delta[w],
        "opponent_strength": closing.strength[w], "rank": closing.rank_of[w],
        "awarded_cents": prize.awarded.get(w, 0)}) for w, e in entrants.items()])

    pub.delimited("prize_allocation_ledger.csv", sorted(prize.allocation, key=lambda r: r[0]), ",")
    pub.delimited("prize_tie_split.tsv", prize.splits, "\t")

    def members_of(division, order):
        return [w for w in order if entrants[w].division_id == division]

    for division in event.divisions:
        people = members_of(division, ranked)
        paid = sum(prize.awarded.get(w, 0) for w in people)
        name = "division_report_%s.json" % division
        pub.json_document(name, pub.keyed(name, {
            "division_id": division, "in_force": True,
            "report_order": event.report_order[division],
            "seated_players": len(people),
            "paired_boards": sum(1 for row in loop.pairing_rows
                                 if entrants[row[2]].division_id == division),
            "byes_awarded": sum(1 for row in loop.bye_rows if row[1] == division),
            "voided_boards": sum(1 for row in loop.void_rows
                                 if entrants[row[2]].division_id == division),
            "points_total": sum(closing.event_points[w] for w in people),
            "game_delta_total": sum(closing.adjusted_delta[w] for w in people),
            "awarded_cents": paid,
            "award_share_ratio": nine_place_ratio(paid, prize.pool),
            "top_player": people[0] if people else event.absent}))

    def attr(value) -> str:
        return (str(value).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))

    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<settlement event_id="%s" event_reference="%s">' % (attr(event.event_id),
                                                               attr(event.reference))]
    for division in sorted(event.divisions, key=lambda d: event.report_order[d]):
        people = members_of(division, ranked)
        opening = ' <division id="%s" report_order="%d" entrants="%d"' % (
            attr(division), event.report_order[division], len(people))
        if not people:
            xml.append(opening + " />")
            continue
        xml.append(opening + ">")
        for w in people:
            xml.append('  <entrant rank="%d" player_id="%s" event_points="%d" adjusted_delta="%d"'
                       ' opponent_strength="%d" awarded_cents="%d" />' % (
                           closing.rank_of[w], attr(w), closing.event_points[w],
                           closing.adjusted_delta[w], closing.strength[w],
                           prize.awarded.get(w, 0)))
        xml.append(" </division>")
    xml.append("</settlement>")
    pub.text("standings_by_division.xml", xml)

    round_points_total = sum(row[7] for row in loop.score_rows)
    levels = {key: sum(report["level_counts"][key] for report in loop.round_reports)
              for key in loop.round_reports[0]["level_counts"]} if loop.round_reports else {}
    level = lambda n: levels.get("level_%d" % n, 0)
    residue = prize.pool - prize.awarded_total
    pub.text("settlement_control_totals.conf", [
        "[event]",
        "event_id = %s" % event.event_id,
        "event_reference = %s" % event.reference,
        "round_count = %d" % event.rounds,
        "player_count = %d" % len(entrants),
        "",
        "[totals]",
        "round_points_total = %d" % round_points_total,
        "game_delta_total = %d" % sum(closing.adjusted_delta.values()),
        "penalty_units_total = %d" % sum(closing.penalty_units.values()),
        "points_per_round_ratio = %s" % nine_place_ratio(round_points_total, event.rounds),
        "",
        "[pairing]",
        "boards_total = %d" % len(loop.pairing_rows),
        "byes_total = %d" % len(loop.bye_rows),
        "voided_total = %d" % len(loop.void_rows),
        "unpaired_total = %d" % len(loop.unpaired_rows),
        "level_1_boards = %d" % level(1),
        "level_2_boards = %d" % level(2),
        "level_3_boards = %d" % level(3),
        "",
        "[prize]",
        "pool_cents = %d" % prize.pool,
        "awarded_cents = %d" % prize.awarded_total,
        "residue_cents = %d" % residue,
        "tie_groups = %d" % len(prize.splits),
        "award_share_ratio = %s" % nine_place_ratio(prize.awarded_total, prize.pool),
    ])

    summary = ["# Settlement summary %s" % event.reference, "",
               "Event %s settled over %d rounds with %d entrants seated."
               % (event.event_id, event.rounds, len(entrants)), "",
               "## Standings", "",
               "| rank | player_id | division_id | event_points | adjusted_delta |",
               "|---|---|---|---|---|"]
    for w in ranked[:10]:
        summary.append("| %d | %s | %s | %d | %d |" % (
            closing.rank_of[w], w, entrants[w].division_id, closing.event_points[w],
            closing.adjusted_delta[w]))
    summary += ["", "## Pairing", "",
                "Boards admitted at level 0: %d. Level 1: %d. Level 2: %d. Level 3: %d."
                % (level(0), level(1), level(2), level(3)),
                "Byes awarded: %d. Boards voided: %d. Entrants left unpaired: %d."
                % (len(loop.bye_rows), len(loop.void_rows), len(loop.unpaired_rows)),
                "", "## Settlement", "",
                "Pool %d cents. Awarded %d cents. Residue %d cents."
                % (prize.pool, prize.awarded_total, residue),
                "Tie groups holding more than one member: %d." % len(prize.splits)]
    pub.text("event_settlement_summary.md", summary)

    pub.manifest(core=pub.contract[:6])
    pub.write()


# --------------------------------------------------------------------------
# entry point
# --------------------------------------------------------------------------


def parse_arguments(argv: list[str]) -> tuple[Path, Path]:
    chosen = {"--data": DEFAULT_DATA, "--out": DEFAULT_OUT}
    queue = list(argv)
    while queue:
        option = queue.pop(0)
        if "=" in option and option.split("=", 1)[0] in chosen:
            option, value = option.split("=", 1)
        elif option in chosen and queue:
            value = queue.pop(0)
        else:
            raise PapersError("unrecognised argument: " + option)
        chosen[option] = Path(value)
    return chosen["--data"], chosen["--out"]


def settle(data: Path, out: Path) -> None:
    event = open_event(data)
    closure = IdentifierClosure(event.rows("entry_alias_register.csv", ","))
    entrants = normalise_entries(event, closure)
    states = participation_states(event, closure, entrants)
    boards = candidate_boards(event, closure, entrants)
    resolve_evidence(event, boards)
    loop = RoundLoop(event, closure, entrants, states, boards)
    loop.run()
    closing = close_event(event, loop)
    prize = settle_prizes(event, closing)
    publish(event, entrants, states, boards, loop, closing, prize, out)


def main(argv: list[str]) -> int:
    try:
        data, out = parse_arguments(argv)
        settle(data, out)
    except (PapersError, KeyError, ValueError, OSError, ET.ParseError,
            zipfile.BadZipFile, tomllib.TOMLDecodeError) as problem:
        print("crownsettle: %s" % problem, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
