#!/usr/bin/env python3
"""GROUNDLINK month end contact settlement.

Rebuilds the settlement of a satellite operator ground segment from the
working papers of one month and writes the thirty artifacts of the output
contract. The same file is the reusable settlement program: it takes
"--data DIR --out DIR", reads every operating constant out of the papers it
is handed, and carries no figure of any particular month.

Stage order follows ordering_dependencies.yaml, S01 through S14, with the
single backward edge from the settled obligation of S08 into the contention
ladder of S07. Every quantity is an integer and every division is a floor.
"""

import argparse
import configparser
import csv
import hashlib
import json
import re
import sqlite3
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import OrderedDict, defaultdict
from pathlib import Path

LF = chr(10)
DQ = chr(34)
LT = chr(60)
GT = chr(62)
XML_HEAD = (LT + '?xml version=' + DQ + '1.0' + DQ + ' encoding=' + DQ
            + 'UTF-8' + DQ + ' standalone=' + DQ + 'yes' + DQ + '?' + GT)

SPREAD = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
DOCBODY = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
RELID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


# ===========================================================================
# paper readers
#
# Seventeen shipped formats, all of them opened with the standard library
# alone so that the settlement program runs wherever python3 does.
# ===========================================================================
def sheet_rows(path, sep=","):
    """Delimited paper as a list of dicts keyed by the header line."""
    with open(str(path), "r", encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter=sep)]


def doc_json(path):
    with open(str(path), "r", encoding="utf-8") as handle:
        return json.load(handle)


def doc_jsonl(path):
    out = []
    with open(str(path), "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def doc_ini(path):
    """Section keyed mapping. Comment markers are semicolon and hash."""
    parser = configparser.ConfigParser(
        interpolation=None, comment_prefixes=(";", "#"))
    parser.optionxform = str
    with open(str(path), "r", encoding="utf-8") as handle:
        parser.read_file(handle)
    return dict((name, dict(parser.items(name))) for name in parser.sections())


def doc_elements(path, tag):
    """Every element of one tag, its attributes merged with its child text."""
    out = []
    for node in ET.parse(str(path)).getroot().iter(tag):
        record = dict(node.attrib)
        for child in node:
            record[child.tag] = child.text if child.text is not None else ""
        out.append(record)
    return out


def _letters_to_ordinal(letters):
    total = 0
    for char in letters:
        total = total * 26 + (ord(char.upper()) - 64)
    return total - 1


def book_pages(path):
    """Workbook as an ordered mapping of sheet name to a grid of strings."""
    pages = OrderedDict()
    with zipfile.ZipFile(str(path)) as archive:
        names = archive.namelist()
        pool = []
        if "xl/sharedStrings.xml" in names:
            for entry in ET.fromstring(archive.read("xl/sharedStrings.xml")):
                pool.append("".join(
                    part.text or "" for part in entry.iter(SPREAD + "t")))
        wiring = {}
        for link in ET.fromstring(archive.read("xl/_rels/workbook.xml.rels")):
            wiring[link.get("Id")] = link.get("Target")
        for tab in ET.fromstring(archive.read("xl/workbook.xml")).iter(
                SPREAD + "sheet"):
            target = wiring.get(tab.get(RELID), "")
            if not target.startswith("xl/"):
                target = "xl/" + target.lstrip("/")
            grid = []
            for line in ET.fromstring(archive.read(target)).iter(SPREAD + "row"):
                slots = {}
                for box in line.iter(SPREAD + "c"):
                    where = box.get("r") or ""
                    column = "".join(ch for ch in where if ch.isalpha())
                    holder = box.find(SPREAD + "v")
                    text = "" if holder is None else (holder.text or "")
                    if box.get("t") == "s" and text != "":
                        text = pool[int(text)]
                    slots[_letters_to_ordinal(column) if column else len(slots)] = text
                span = max(slots) + 1 if slots else 0
                grid.append([slots.get(i, "") for i in range(span)])
            pages[tab.get("name")] = grid
    return pages


def memo_text(path):
    """Every shown line of an uncompressed text pdf, in page order."""
    blob = Path(str(path)).read_bytes().decode("latin-1")
    return [piece for piece in re.findall(r"\(([^()]*)\)\s*Tj", blob)]


def directive_text(path):
    with zipfile.ZipFile(str(path)) as archive:
        body = ET.fromstring(archive.read("word/document.xml"))
    return ["".join(part.text or "" for part in block.iter(DOCBODY + "t"))
            for block in body.iter(DOCBODY + "p")]


def db_table(path, table):
    link = sqlite3.connect(str(path))
    try:
        cursor = link.execute("select * from " + table)
        heads = [spec[0] for spec in cursor.description]
        return [dict(zip(heads, row)) for row in cursor.fetchall()]
    finally:
        link.close()


def whole(value, fallback=0):
    """Integer from a paper cell, tolerating an empty or absent field."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return fallback


# ===========================================================================
# half open interval arithmetic on integer seconds
#
# Every span in every paper is [start, end). Two spans that share only an
# endpoint do not overlap, and a span of zero length contains no instant.
# ===========================================================================
def fuse(spans):
    """Sorted disjoint form. Overlapping or abutting spans merge, empty go."""
    ordered = sorted((lo, hi) for lo, hi in spans if hi > lo)
    stack = []
    for lo, hi in ordered:
        if stack and lo <= stack[-1][1]:
            if hi > stack[-1][1]:
                stack[-1][1] = hi
        else:
            stack.append([lo, hi])
    return [(lo, hi) for lo, hi in stack]


def carve(spans, holes):
    """spans less holes, exactly, on integer seconds."""
    live = list(spans)
    for cut_lo, cut_hi in holes:
        if cut_hi <= cut_lo:
            continue
        rest = []
        for lo, hi in live:
            if cut_hi <= lo or cut_lo >= hi:
                rest.append((lo, hi))
                continue
            if lo < cut_lo:
                rest.append((lo, cut_lo))
            if cut_hi < hi:
                rest.append((cut_hi, hi))
        live = rest
    return live


def meet(left, right):
    """Intersection of two sorted disjoint span lists."""
    out = []
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        lo = max(left[i][0], right[j][0])
        hi = min(left[i][1], right[j][1])
        if hi > lo:
            out.append((lo, hi))
        if left[i][1] < right[j][1]:
            i += 1
        else:
            j += 1
    return out


def extent(spans):
    return sum(hi - lo for lo, hi in spans)


def collides(left, right):
    """True when the two span lists share at least one second."""
    return extent(meet(left, right)) > 0


def covers(spans, instant):
    for lo, hi in spans:
        if lo <= instant < hi:
            return True
    return False


def window_at(rows, instant, low="valid_from_s", high="valid_to_s"):
    """The row whose half open window contains the instant, or None."""
    for row in rows:
        if whole(row[low]) <= instant < whole(row[high]):
            return row
    return None


# ===========================================================================
# the papers of one month
# ===========================================================================
PERIOD_ORDER = ("P1", "P2", "P3")
ADMISSIBLE = ("nominal", "partial")


class Papers(object):
    """Everything under the data directory, read once, nothing settled yet."""

    def __init__(self, data_dir):
        here = Path(str(data_dir))
        self.root = here
        self.missions = sheet_rows(here / "mission_register.csv")
        self.aliases = sheet_rows(here / "mission_alias_crosswalk.csv")
        self.facilities = sheet_rows(here / "ground_segment_register.tsv", chr(9))
        self.apertures = sheet_rows(here / "aperture_register.csv")
        self.service = sheet_rows(here / "aperture_service_windows.csv")
        self.dockets = sheet_rows(here / "maintenance_dockets.csv")
        self.blackouts = sheet_rows(here / "blackout_advisories.psv", "|")
        self.calendar = sheet_rows(here / "station_accounting_calendar.csv")
        self.local = doc_ini(here / "station_local_accounting.ini")
        self.plan = sheet_rows(here / "pass_plan_of_record.csv")
        self.phases = doc_elements(here / "campaign_schedule.xml", "phase")
        self.notices = sheet_rows(here / "cancellation_notices.csv")
        self.journal = doc_jsonl(here / "contact_event_journal.ndjson")
        self.roster = sheet_rows(here / "operator_roster.tsv", chr(9))
        self.rates = sheet_rows(here / "rate_schedule_effective.psv", "|")
        self.legacy = sheet_rows(here / "legacy_flat_rate_table.csv")
        self.overrides = doc_jsonl(here / "precedence_override_register.jsonl")
        self.amendments = sheet_rows(here / "contract_terms_amendments.tsv", chr(9))
        self.opening = doc_json(here / "prior_period_settlement.json")
        self.backlogs = sheet_rows(here / "onboard_backlog_reports.csv")
        self.claims = sheet_rows(here / "outage_claims.psv", "|")
        self.reports = sheet_rows(here / "downlink_reports.csv")
        self.scaling = doc_json(here / "unit_scaling_rules.json")
        self.selection = doc_json(here / "workbook_sheet_selection.json")
        self.codes = doc_elements(here / "exception_code_dictionary.xml", "code")
        self.workbook = book_pages(here / "aperture_contract_workbook.xlsx")
        self.memo = memo_text(here / "network_operations_memo.pdf")
        self.directive = directive_text(here / "precedence_directive.docx")
        self.scope = db_table(here / "reference_lookups.sqlite", "station_scope")
        self.ranks = db_table(here / "reference_lookups.sqlite", "priority_rank")
        self.grades = db_table(here / "reference_lookups.sqlite", "grade_authority")
        self.trace = db_table(here / "settlement_audit_trace.db", "carry_state")

    # -- scalars that live only in the harder documents --------------------
    def commit_leads(self):
        """Per station commit lead, published in the memo and nowhere else."""
        leads = {}
        for line in self.memo:
            hit = re.match(r"commit-lead\s+(\S+):\s*(-?\d+)", line.strip())
            if hit:
                leads[hit.group(1)] = int(hit.group(2))
        return leads

    def memo_scalar(self, label):
        for line in self.memo:
            hit = re.match(re.escape(label) + r":\s*(-?\d+)", line.strip())
            if hit:
                return int(hit.group(1))
        return 0

    def binding_page(self):
        """The workbook sheet whose status matches, highest revision on a tie."""
        wanted = self.selection.get("binding_status")
        status_key = self.selection.get("status_header_cell", "sheet_status")
        revision_key = self.selection.get("revision_header_cell", "sheet_revision")
        best = None
        for name, grid in self.workbook.items():
            header = {}
            for line in grid:
                if len(line) >= 2 and line[0] and not line[0].startswith("#"):
                    header.setdefault(line[0], line[1])
                if line and line[0].startswith("#"):
                    break
            if header.get(status_key) != wanted:
                continue
            revision = whole(header.get(revision_key))
            if best is None or revision > best[0]:
                best = (revision, name, grid)
        if best is None:
            return []
        return best[2]

    def page_blocks(self):
        """The binding sheet split at its block markers into header keyed rows."""
        markers = list(self.selection.get("block_markers") or [])
        blocks = {}
        current = None
        heads = None
        for line in self.binding_page():
            head = line[0] if line else ""
            if head in markers:
                current = head
                heads = None
                blocks[current] = []
                continue
            if current is None:
                continue
            if heads is None:
                heads = list(line)
                continue
            if not head:
                continue
            blocks[current].append(dict(zip(heads, line)))
        return blocks

    def aperture_terms(self):
        """(antenna_uid, period_id) to the per contact cap and period budget."""
        blocks = self.page_blocks()
        rows = blocks.get("#aperture_period_terms", [])
        terms = {}
        for row in rows:
            key = (row.get("antenna_uid"), row.get("period_id"))
            terms[key] = (whole(row.get("per_contact_cap_kib")),
                          whole(row.get("period_budget_kib")))
        return terms

    def credit_terms(self):
        blocks = self.page_blocks()
        out = {}
        for row in blocks.get("#credit_rates", []):
            out[row.get("rate_key")] = whole(row.get("rate_value"))
        return out

    def class_ranks(self):
        """Rank per priority class. The lookup table binds; the directive
        clause one table is the same ladder written out in prose."""
        table = dict((row["priority_class"], whole(row["rank_value"]))
                     for row in self.ranks)
        if table:
            return table
        text = self.directive
        for index, line in enumerate(text):
            if line in table:
                continue
            if index + 1 < len(text) and re.match(r"^\d+$", text[index + 1] or ""):
                table[line] = int(text[index + 1])
        return table

    def committing_grades(self):
        return set(row["authority_grade"] for row in self.grades
                   if whole(row["commit_evidence"]) == 1)

    def code_index(self):
        return dict((row["id"], row) for row in self.codes)


# ===========================================================================
# S01 identity resolution
# ===========================================================================
class Register(object):
    """The binding identity of every mission, station, aperture and contract."""

    def __init__(self, papers):
        self.papers = papers
        self.mission_of = {}
        for row in papers.missions:
            if row["register_state"] == "current":
                self.mission_of[row["mission_id"]] = row
        self.mission_ids = sorted(self.mission_of)

        self.alias_windows = defaultdict(list)
        for row in papers.aliases:
            self.alias_windows[row["presentation_id"]].append(row)

        self.station_of = {}
        for row in papers.facilities:
            if row["element_class"] == "accounting_site":
                self.station_of[row["station_id"]] = row
        self.station_ids = sorted(self.station_of)

        self.aperture_of = {}
        self.label_index = {}
        for row in papers.apertures:
            if row["config_state"] != "current":
                continue
            self.aperture_of[row["antenna_uid"]] = row
            self.label_index[(row["station_id"], row["local_label"])] = row["antenna_uid"]
        self.aperture_ids = sorted(self.aperture_of)

        self.contract_of = {}
        for row in papers.trace:
            cid = row["contract_id"]
            if cid not in self.contract_of:
                self.contract_of[cid] = {
                    "contract_id": cid,
                    "mission_id": row["mission_id"],
                    "valid_from_s": whole(row["valid_from_s"]),
                    "valid_to_s": whole(row["valid_to_s"]),
                    "carry_forward_enabled": whole(row["carry_forward_enabled"]),
                }
        self.contract_ids = sorted(self.contract_of)

        self.scope_index = defaultdict(set)
        for row in papers.scope:
            self.scope_index[row["contract_id"]].add(row["station_id"])

        self.by_mission = defaultdict(list)
        for cid in self.contract_ids:
            self.by_mission[self.contract_of[cid]["mission_id"]].append(cid)

        self.phase_index = defaultdict(list)
        for row in papers.phases:
            self.phase_index[row["mission_id"]].append(row)

        self.terms = {}
        for row in papers.amendments:
            if row["amendment_status"] != "executed":
                continue
            key = (row["contract_id"], row["period_id"])
            seat = self.terms.get(key)
            if seat is None or whole(row["revision_seq"]) > whole(seat["revision_seq"]):
                self.terms[key] = row

    def mission_at(self, presentation_id, instant):
        hit = window_at(self.alias_windows.get(presentation_id, []), instant)
        return hit["mission_id"] if hit is not None else None

    def phase_at(self, mission_id, instant):
        return window_at(self.phase_index.get(mission_id, []), instant,
                         "phase_from_s", "phase_to_s")

    def contracts_at(self, mission_id, station_id, instant):
        """Every contract of the mission valid at the instant whose scope
        holds the station."""
        out = []
        for cid in self.by_mission.get(mission_id, []):
            deed = self.contract_of[cid]
            if not (deed["valid_from_s"] <= instant < deed["valid_to_s"]):
                continue
            if station_id not in self.scope_index.get(cid, ()):
                continue
            out.append(cid)
        return out

    def settled(self, contract_id, period_id):
        return self.terms.get((contract_id, period_id))


# ===========================================================================
# S02 availability construction
# ===========================================================================
def build_availability(papers, register):
    """Declared operating windows less aperture dockets less station
    blackouts, per aperture, as a sorted disjoint span list."""
    declared = defaultdict(list)
    for row in papers.service:
        if row["service_state"] != "in_service":
            continue
        declared[row["antenna_uid"]].append(
            (whole(row["effective_from_s"]), whole(row["effective_to_s"])))

    aperture_cuts = defaultdict(list)
    for row in papers.dockets:
        aperture_cuts[row["antenna_uid"]].append(
            (whole(row["start_s"]), whole(row["end_s"])))

    station_cuts = defaultdict(list)
    for row in papers.blackouts:
        station_cuts[row["station_id"]].append(
            (whole(row["start_s"]), whole(row["end_s"])))

    free = {}
    for uid in register.aperture_ids:
        station = register.aperture_of[uid]["station_id"]
        live = fuse(declared.get(uid, []))
        live = carve(live, aperture_cuts.get(uid, []))
        live = carve(live, station_cuts.get(station, []))
        free[uid] = fuse(live)
    return free


def build_period_windows(papers, register):
    """Station local accounting period, the smallest open to the largest
    close of the calendar rows of that station and period."""
    edges = defaultdict(lambda: [None, None])
    for row in papers.calendar:
        slot = edges[(row["station_id"], row["period_id"])]
        low = whole(row["local_open_s"])
        high = whole(row["local_close_s"])
        slot[0] = low if slot[0] is None else min(slot[0], low)
        slot[1] = high if slot[1] is None else max(slot[1], high)
    windows = {}
    for (station, period), (low, high) in edges.items():
        windows[(station, period)] = (low, high)
    return windows


def period_ids_of(windows):
    seen = set(period for _, period in windows)
    ordered = [p for p in PERIOD_ORDER if p in seen]
    ordered += sorted(p for p in seen if p not in PERIOD_ORDER)
    return ordered


# ===========================================================================
# S03 pass admission and S04 interval clipping
# ===========================================================================
REJECTIONS = (
    (1, "E01"), (2, "E02"), (3, "E03"), (4, "E04"),
    (5, "E05"), (6, "E06"), (7, "E07"), (8, "E08"),
)


def effective_notice(rows):
    """Last notice by issued_seq whose state is effective. A rescinded notice
    binds nothing however late it sits."""
    bound = None
    for row in rows:
        if row["notice_state"] != "effective":
            continue
        if bound is None or whole(row["issued_seq"]) > whole(bound["issued_seq"]):
            bound = row
    return bound


def split_on(spans, edges):
    """Cut every span at the edges that fall strictly inside it."""
    out = []
    for lo, hi in spans:
        marks = [lo] + [e for e in edges if lo < e < hi] + [hi]
        marks = sorted(set(marks))
        for i in range(len(marks) - 1):
            if marks[i + 1] > marks[i]:
                out.append((marks[i], marks[i + 1]))
    return out


class Admission(object):
    """Runs the eight predicates in the published order and clips whatever
    survives into canonical rows, one per pass per settlement period."""

    def __init__(self, papers, register, free, windows, periods):
        self.papers = papers
        self.register = register
        self.free = free
        self.windows = windows
        self.periods = periods
        self.leads = papers.commit_leads()
        self.grades_with_commit = papers.committing_grades()
        self.grade_of = dict((row["operator_code"], row["authority_grade"])
                             for row in papers.roster)
        self.event_of = dict((row["contact_id"], row) for row in papers.journal)
        self.notice_of = defaultdict(list)
        for row in papers.notices:
            self.notice_of[row["contact_id"]].append(row)
        self.rows = []
        self.rejected = []
        self.segments = []
        self._run()

    def _station_periods(self, station):
        return [(pid, self.windows[(station, pid)]) for pid in self.periods
                if (station, pid) in self.windows]

    def _run(self):
        for pass_row in sorted(self.papers.plan, key=lambda r: r["contact_id"]):
            self._one(pass_row)

    def _reject(self, pass_row, index, code):
        slug = self.papers.code_index().get(code, {}).get("reason_slug", "")
        self.rejected.append({
            "contact_id": pass_row["contact_id"],
            "station_id": pass_row["station_id"],
            "aperture_label": pass_row["aperture_label"],
            "presentation_id": pass_row["presentation_id"],
            "scheduled_start_s": whole(pass_row["scheduled_start_s"]),
            "scheduled_end_s": whole(pass_row["scheduled_end_s"]),
            "predicate_index": index,
            "reject_code": code,
            "reject_reason": slug,
        })

    def _one(self, pass_row):
        reg = self.register
        contact = pass_row["contact_id"]
        station = pass_row["station_id"]
        start = whole(pass_row["scheduled_start_s"])
        end = whole(pass_row["scheduled_end_s"])
        boundary = start - self.leads.get(station, 0)

        mission = reg.mission_at(pass_row["presentation_id"], start)
        if mission is None:
            return self._reject(pass_row, 1, "E01")

        uid = reg.label_index.get((station, pass_row["aperture_label"]))
        if uid is None:
            return self._reject(pass_row, 2, "E02")

        contracts = reg.contracts_at(mission, station, start)
        if not contracts:
            return self._reject(pass_row, 3, "E03")

        phase = reg.phase_at(mission, start)
        if phase is not None and phase.get("phase_class") == "standdown":
            return self._reject(pass_row, 4, "E04")

        notice = effective_notice(self.notice_of.get(contact, []))
        late_cancel = 0
        if notice is not None:
            if whole(notice["effective_s"]) < boundary:
                return self._reject(pass_row, 5, "E05")
            late_cancel = 1

        event = self.event_of.get(contact)
        if event is None:
            return self._reject(pass_row, 6, "E06")
        if event.get("event_status") not in ADMISSIBLE:
            return self._reject(pass_row, 7, "E07")

        base = [(start, end)]
        if event.get("event_status") == "partial":
            base = meet(base, [(whole(event.get("actual_start_s")),
                                whole(event.get("actual_end_s")))])
        eligible = meet(fuse(base), self.free.get(uid, []))

        zero_length = end == start
        if zero_length:
            if not covers(self.free.get(uid, []), start):
                return self._reject(pass_row, 8, "E08")
        elif extent(eligible) <= 0:
            return self._reject(pass_row, 8, "E08")

        grade = self.grade_of.get(event.get("operator_code"), "")
        protected = int(whole(event.get("event_recorded_s")) <= boundary
                        and grade in self.grades_with_commit)

        shared = {
            "contact_id": contact,
            "station_id": station,
            "antenna_uid": uid,
            "mission_id": mission,
            "presentation_id": pass_row["presentation_id"],
            "scheduled_start_s": start,
            "scheduled_end_s": end,
            "commit_boundary_s": boundary,
            "event_status": event.get("event_status"),
            "operator_code": event.get("operator_code"),
            "protected": protected,
            "late_cancel": late_cancel,
            "contracts": contracts,
        }

        if zero_length:
            for period, (low, high) in self._station_periods(station):
                if low <= start < high:
                    row = dict(shared)
                    row["period_id"] = period
                    row["spans"] = []
                    row["eligible_seconds"] = 0
                    self.rows.append(row)
                    self.segments.append((contact, period, uid, start, start, 0))
                    break
            return

        for period, (low, high) in self._station_periods(station):
            slice_ = meet(eligible, [(low, high)])
            if not slice_:
                continue
            row = dict(shared)
            row["period_id"] = period
            row["spans"] = slice_
            row["eligible_seconds"] = extent(slice_)
            self.rows.append(row)
            for lo, hi in slice_:
                self.segments.append((contact, period, uid, lo, hi, hi - lo))


# ===========================================================================
# S05 capacity derivation
# ===========================================================================
def derive_capacity(papers, register, rows):
    """Rate pieces floored one by one, then the per contact cap applied to
    the canonical row before any aggregation of any kind."""
    divisor = whole(papers.scaling.get("rate_scale_divisor"), 1) or 1
    schedule = defaultdict(list)
    for row in papers.rates:
        schedule[row["antenna_uid"]].append(
            (whole(row["effective_from_s"]), whole(row["effective_to_s"]),
             whole(row["rate_mkib_per_s"])))
    edges = {}
    for uid, pieces in schedule.items():
        marks = set()
        for lo, hi, _ in pieces:
            marks.add(lo)
            marks.add(hi)
        edges[uid] = sorted(marks)

    terms = papers.aperture_terms()
    for row in rows:
        uid = row["antenna_uid"]
        chunks = split_on(row["spans"], edges.get(uid, []))
        raw = 0
        for lo, hi in chunks:
            rate = 0
            for from_s, to_s, value in schedule.get(uid, []):
                if from_s <= lo < to_s:
                    rate = value
                    break
            raw += ((hi - lo) * rate) // divisor
        cap = terms.get((uid, row["period_id"]), (0, 0))[0]
        row["rate_piece_count"] = len(chunks)
        row["raw_capacity_kib"] = raw
        row["capacity_cap_kib"] = cap
        row["usable_capacity_kib"] = min(raw, cap)


# ===========================================================================
# S06 precedence and commit
# ===========================================================================
def apply_precedence(papers, register, rows):
    """Registered class, raised by a narrow override that names the same
    mission, the same aperture and a window holding the scheduled start."""
    ranks = papers.class_ranks()
    grants = defaultdict(list)
    for row in papers.overrides:
        grants[(row.get("mission_id"), row.get("antenna_uid"))].append(row)

    for row in rows:
        registered = register.mission_of[row["mission_id"]]["priority_class"]
        best_class = registered
        best_rank = ranks.get(registered, 0)
        winner = None
        for grant in grants.get((row["mission_id"], row["antenna_uid"]), []):
            low = whole(grant.get("valid_from_s"))
            high = whole(grant.get("valid_to_s"))
            if not (low <= row["scheduled_start_s"] < high):
                continue
            granted = grant.get("granted_class")
            rank = ranks.get(granted, 0)
            if winner is None:
                winner = (rank, str(grant.get("override_id")), granted)
            else:
                here = (rank, str(grant.get("override_id")), granted)
                if here[0] < winner[0] or (here[0] == winner[0] and here[1] < winner[1]):
                    winner = here
        if winner is not None and winner[0] < best_rank:
            best_class = winner[2]
            best_rank = winner[0]
        row["effective_class"] = best_class
        row["effective_rank"] = best_rank


def opening_obligation(register, row, period):
    """The largest settled obligation across the contracts of the pass, read
    once at the opening of the period. This is the backward edge S08 to S07."""
    best = 0
    for cid in row["contracts"]:
        terms = register.settled(cid, period)
        if terms is None:
            continue
        best = max(best, whole(terms["obligation_kib"]))
    return best


def ladder(row):
    """The five key ordering of S07. Protection first, contact_id last."""
    return (0 if row["protected"] else 1,
            row["effective_rank"],
            row["commit_boundary_s"],
            -row["obligation_open"],
            row["contact_id"])


def decided_level(left, right):
    one = ladder(left)
    two = ladder(right)
    for index in range(len(one)):
        if one[index] != two[index]:
            return index + 1
    return len(one)


# ===========================================================================
# S07 contention resolution
# ===========================================================================
def resolve_contention(rows):
    """One greedy walk over the whole aperture period in the published
    order. Displacement is whole; a displaced row keeps none of its span."""
    buckets = defaultdict(list)
    for row in rows:
        buckets[(row["antenna_uid"], row["period_id"])].append(row)

    groups = []
    ties = []
    for key in sorted(buckets):
        uid, period = key
        members = sorted(buckets[key], key=ladder)
        held = []
        for row in members:
            blocker = None
            for taken in held:
                if collides(row["spans"], taken["spans"]):
                    blocker = taken
                    break
            if blocker is None:
                row["allocation_state"] = "won"
                row["displaced_by"] = ""
                held.append(row)
            else:
                row["allocation_state"] = "displaced"
                row["displaced_by"] = blocker["contact_id"]

        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                if collides(members[i]["spans"], members[j]["spans"]):
                    ties.append({
                        "antenna_uid": uid,
                        "period_id": period,
                        "contact_id_kept": members[i]["contact_id"],
                        "contact_id_yielded": members[j]["contact_id"],
                        "decided_at_level": decided_level(members[i], members[j]),
                    })

        for seq, part in enumerate(components(members), start=1):
            groups.append({
                "antenna_uid": uid,
                "period_id": period,
                "group_seq": seq,
                "member_count": len(part),
                "member_ids": ",".join(sorted(x["contact_id"] for x in part)),
                "eligible_seconds_total": sum(x["eligible_seconds"] for x in part),
            })
    return groups, ties


def components(members):
    """Connected components of the intersection graph, ordered by their
    smallest contact_id. A row that intersects nothing is a group of one."""
    size = len(members)
    parent = list(range(size))

    def find(node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    for i in range(size):
        for j in range(i + 1, size):
            if collides(members[i]["spans"], members[j]["spans"]):
                a, b = find(i), find(j)
                if a != b:
                    parent[a] = b

    pools = defaultdict(list)
    for i in range(size):
        pools[find(i)].append(members[i])
    ordered = sorted(pools.values(),
                     key=lambda part: min(x["contact_id"] for x in part))
    return ordered


# ===========================================================================
# S08 entitlement merge
# ===========================================================================
def opening_carry(papers, register):
    """Only the open buckets of prior_period_settlement.json carry."""
    source = defaultdict(int)
    for bucket in papers.opening.get("opening_buckets", []):
        if bucket.get("bucket_state") != "open":
            continue
        source[bucket.get("contract_id")] += whole(bucket.get("unsettled_kib"))
    return source


def earliest_open(windows, period):
    """The earliest station local period open across the network, so that a
    contract expires on the same instant everywhere."""
    stamps = [low for (station, pid), (low, high) in windows.items() if pid == period]
    return min(stamps) if stamps else 0


# ===========================================================================
# S09 deliverable volume, the damped ration
# ===========================================================================
def ration(demands, budget, rounds, theta_num, theta_den):
    """The published procedure: a fixed number of offer rounds, integer at
    the end of each, a minimum movement of one unit on a positive step, and
    a residual walk afterwards. Returns the allocations and the trace."""
    size = len(demands)
    holding = [0] * size
    pinned = [False] * size
    trace = []
    for step in range(1, rounds + 1):
        pinned_mass = sum(demands[i] for i in range(size) if pinned[i])
        active = [i for i in range(size) if not pinned[i]]
        if not active:
            trace.append((step, 0, 0, sum(holding)))
            continue
        room = budget - pinned_mass
        share = room // len(active) if room > 0 else 0
        for i in active:
            target = min(demands[i], share)
            gap = target - holding[i]
            move = (gap * theta_num) // theta_den
            if gap > 0 and move < 1:
                move = 1
            holding[i] += move
        for i in active:
            if holding[i] >= demands[i]:
                holding[i] = demands[i]
                pinned[i] = True
        trace.append((step, len(active), share, sum(holding)))

    residual = budget - sum(holding)
    if residual > 0:
        for i in range(size):
            if residual <= 0:
                break
            take = min(residual, demands[i] - holding[i])
            if take > 0:
                holding[i] += take
                residual -= take
    return holding, trace


def traced_groups_within_budget(traces):
    """Aperture periods that carry a ration trace while their demand total sat
    at or below their budget. The ration runs only past the budget, so the S14
    invariant holds when this count is zero."""
    return len(set((trace["antenna_uid"], trace["period_id"]) for trace in traces
                   if trace["demand_total_kib"] <= trace["budget_kib"]))


def allocate_volume(papers, rows, backlog_open):
    """Demand against the opening backlog, then the aperture period budget."""
    terms = papers.aperture_terms()
    base = papers.memo_scalar("ration-pass-budget-base")
    ceiling = papers.memo_scalar("ration-pass-budget-ceiling")
    theta_num = whole(papers.scaling.get("ration_damping_numerator"), 1)
    theta_den = whole(papers.scaling.get("ration_damping_denominator"), 1) or 1

    buckets = defaultdict(list)
    for row in rows:
        if row["allocation_state"] == "won":
            buckets[(row["antenna_uid"], row["period_id"])].append(row)

    traces = []
    overspend = 0
    for key in sorted(buckets):
        uid, period = key
        members = sorted(buckets[key], key=ladder)
        for row in members:
            row["demand_kib"] = min(
                row["usable_capacity_kib"],
                backlog_open.get((row["mission_id"], period), 0))
        demands = [row["demand_kib"] for row in members]
        budget = terms.get(key, (0, 0))[1]
        total = sum(demands)
        if total <= budget:
            for row in members:
                row["allocated_kib"] = row["demand_kib"]
        else:
            rounds = min(ceiling, base + len(members))
            shares, trace = ration(demands, budget, rounds, theta_num, theta_den)
            for row, value in zip(members, shares):
                row["allocated_kib"] = value
            for step, active, share, running in trace:
                traces.append({
                    "antenna_uid": uid,
                    "period_id": period,
                    "pass_seq": step,
                    "active_count": active,
                    "share_kib": share,
                    "allocated_kib": running,
                    "budget_kib": budget,
                    "demand_total_kib": total,
                })
        if sum(row["allocated_kib"] for row in members) > budget:
            overspend += 1
    return traces, overspend, traced_groups_within_budget(traces)


# ===========================================================================
# S10 transmission accounting
# ===========================================================================
def bind_contract(register, row, period):
    """Among the contracts of the pass with settled terms in the period, the
    largest obligation, the lower contract_id on a tie. A mission holding two
    contracts competes against itself here."""
    best = None
    for cid in sorted(row["contracts"]):
        terms = register.settled(cid, period)
        if terms is None:
            continue
        weight = whole(terms["obligation_kib"])
        if best is None or weight > best[0]:
            best = (weight, cid)
    return best[1] if best is not None else ""


def settle_accounts(register, rows, periods, carry_source, backlog_open,
                    windows, contract_ids):
    """Walks each period in order, carry first, and carries the unconsumed
    allowance of one period into the next."""
    entitlement = []
    live_source = dict(carry_source)

    won_by_period = defaultdict(list)
    for row in rows:
        if row["allocation_state"] == "won":
            won_by_period[row["period_id"]].append(row)

    for period in periods:
        opening_instant = earliest_open(windows, period)
        state = {}
        for cid in contract_ids:
            terms = register.settled(cid, period)
            if terms is None:
                continue
            deed = register.contract_of[cid]
            source = live_source.get(cid, 0)
            cap = whole(terms["carry_cap_kib"])
            enabled = int(whole(terms["carry_forward_enabled"]) == 1
                          and deed["carry_forward_enabled"] == 1)
            expired = int(deed["valid_to_s"] <= opening_instant)
            if enabled == 0 or expired == 1:
                carry_in = 0
                forfeit = source
            else:
                carry_in = min(source, cap)
                forfeit = source - carry_in
            allowance = carry_in + whole(terms["entitlement_kib"])
            state[cid] = {
                "contract_id": cid,
                "period_id": period,
                "mission_id": deed["mission_id"],
                "carry_source_kib": source,
                "carry_cap_kib": cap,
                "carry_in_kib": carry_in,
                "carry_forfeit_kib": forfeit,
                "entitlement_kib": whole(terms["entitlement_kib"]),
                "available_allowance_kib": allowance,
                "carry_left": carry_in,
                "new_left": whole(terms["entitlement_kib"]),
                "contract_expired": expired,
                "carry_forward_enabled": enabled,
                "obligation_kib": whole(terms["obligation_kib"]),
                "reserved_kib": whole(terms["reserved_kib"]),
                "delivered_kib": 0,
            }

        backlog_left = {}
        order = sorted(won_by_period.get(period, []),
                       key=lambda r: (r["station_id"], r["antenna_uid"]) + ladder(r))
        for row in order:
            cid = bind_contract(register, row, period)
            row["contract_id"] = cid
            mission_key = (row["mission_id"], period)
            if mission_key not in backlog_left:
                backlog_left[mission_key] = backlog_open.get(mission_key, 0)
            purse = state.get(cid)
            room = (purse["carry_left"] + purse["new_left"]) if purse else 0
            taken = min(row["allocated_kib"], backlog_left[mission_key], room)
            if taken < 0:
                taken = 0
            from_carry = min(taken, purse["carry_left"]) if purse else 0
            from_new = taken - from_carry
            if purse is not None:
                purse["carry_left"] -= from_carry
                purse["new_left"] -= from_new
                purse["delivered_kib"] += taken
            backlog_left[mission_key] -= taken
            row["accepted_kib"] = taken
            row["from_carry_kib"] = from_carry
            row["from_new_kib"] = from_new
            row["deferred_kib"] = row["demand_kib"] - taken
            row["unused_capacity_kib"] = row["usable_capacity_kib"] - taken

        for cid in sorted(state):
            purse = state[cid]
            unconsumed = purse["carry_left"] + purse["new_left"]
            purse["consumed_kib"] = purse["available_allowance_kib"] - unconsumed
            purse["unconsumed_kib"] = unconsumed
            purse["carry_out_kib"] = unconsumed
            live_source[cid] = unconsumed
            entitlement.append(purse)
    return entitlement


# ===========================================================================
# S11 utilisation basis
# ===========================================================================
def measure_utilisation(register, rows, free, windows, periods):
    """Numerator from the resolved ledger, denominator from S02 availability
    intersected with the station local period. Nothing at S13 touches it."""
    occupied = defaultdict(int)
    for row in rows:
        if row["allocation_state"] == "won":
            occupied[(row["antenna_uid"], row["period_id"])] += row["eligible_seconds"]

    per_aperture = []
    for uid in register.aperture_ids:
        station = register.aperture_of[uid]["station_id"]
        for period in periods:
            window = windows.get((station, period))
            available = extent(meet(free.get(uid, []), [window])) if window else 0
            numerator = occupied.get((uid, period), 0)
            per_aperture.append({
                "antenna_uid": uid,
                "station_id": station,
                "period_id": period,
                "occupied_seconds": numerator,
                "available_seconds": available,
                "utilisation_bp": (numerator * 10000) // available if available else 0,
                "denominator_state": "populated" if available else "empty",
            })

    totals = defaultdict(lambda: [0, 0])
    for entry in per_aperture:
        slot = totals[(entry["station_id"], entry["period_id"])]
        slot[0] += entry["occupied_seconds"]
        slot[1] += entry["available_seconds"]

    per_station = []
    for station in register.station_ids:
        for period in periods:
            numerator, available = totals.get((station, period), [0, 0])
            per_station.append({
                "station_id": station,
                "period_id": period,
                "occupied_seconds": numerator,
                "available_seconds": available,
                "utilisation_bp": (numerator * 10000) // available if available else 0,
                "denominator_state": "populated" if available else "empty",
            })
    return per_aperture, per_station


# ===========================================================================
# S13 credit and debit
# ===========================================================================
def price_settlement(papers, register, rows, entitlement, periods):
    """The outage test runs before the shortfall. A qualifying outage waives
    the debit outright and restores part of a forfeited carry."""
    rates = papers.credit_terms()
    basis = whole(papers.scaling.get("credit_basis_kib_per_mib"), 1) or 1
    floor_seconds = papers.memo_scalar("outage-qualifying-floor-seconds")

    claims = defaultdict(list)
    for claim in papers.claims:
        if claim["claim_status"] != "accepted":
            continue
        claims[(claim["mission_id"], claim["period_id"])].append(claim)

    won_by_contract = defaultdict(list)
    for row in rows:
        if row["allocation_state"] == "won":
            won_by_contract[(row.get("contract_id", ""), row["period_id"])].append(row)

    credits = []
    compliance = []
    outages = []
    for purse in entitlement:
        cid = purse["contract_id"]
        period = purse["period_id"]
        mission = purse["mission_id"]
        served = won_by_contract.get((cid, period), [])
        delivered = purse["delivered_kib"]
        shortfall = max(0, purse["obligation_kib"] - delivered)
        unused_reserved = max(0, purse["reserved_kib"] - delivered)

        overlap = 0
        qualifying = []
        for claim in sorted(claims.get((mission, period), []),
                            key=lambda c: c["claim_id"]):
            window = [(whole(claim["claim_from_s"]), whole(claim["claim_to_s"]))]
            on_aperture = [r for r in served
                           if r["antenna_uid"] == claim["antenna_uid"]]
            reach = sum(extent(meet(row["spans"], window)) for row in on_aperture)
            overlap += reach
            if reach > 0:
                qualifying.append(on_aperture)

        pool = 0
        for on_aperture in qualifying:
            for row in on_aperture:
                if row["late_cancel"] != 1:
                    pool += row["deferred_kib"]

        qualified = int(overlap >= floor_seconds)
        exempt = min(shortfall, pool) if qualified else 0
        if qualified:
            debit = 0
            outage_credit = (exempt * rates.get("outage_credit_mcr_per_mib", 0)) // basis
            restore = min(purse["carry_forfeit_kib"],
                          (exempt * rates.get("carry_restore_numerator", 0))
                          // (rates.get("carry_restore_denominator", 1) or 1))
        else:
            debit = (shortfall * rates.get("shortfall_debit_mcr_per_mib", 0)) // basis
            outage_credit = 0
            restore = 0
        unused_credit = (unused_reserved
                         * rates.get("unused_reserved_credit_mcr_per_mib", 0)) // basis
        net = unused_credit + outage_credit - debit

        if shortfall == 0:
            verdict = "met"
        elif qualified:
            verdict = "exempt"
        else:
            verdict = "short"

        purse["net_mcr"] = net
        credits.append({
            "contract_id": cid, "period_id": period,
            "shortfall_kib": shortfall, "shortfall_debit_mcr": debit,
            "unused_reserved_kib": unused_reserved,
            "unused_credit_mcr": unused_credit,
            "outage_credit_mcr": outage_credit,
            "carry_restore_kib": restore, "net_mcr": net,
        })
        compliance.append({
            "contract_id": cid, "period_id": period, "mission_id": mission,
            "obligation_kib": purse["obligation_kib"],
            "delivered_kib": delivered,
            "reserved_kib": purse["reserved_kib"],
            "shortfall_kib": shortfall, "compliance_state": verdict,
        })
        outages.append({
            "contract_id": cid, "period_id": period, "mission_id": mission,
            "claim_overlap_seconds": overlap,
            "qualifying_floor_seconds": floor_seconds,
            "outage_qualified": qualified,
            "exempt_kib": exempt, "carry_restore_kib": restore,
        })
    return credits, compliance, outages


# ===========================================================================
# S14 emission
# ===========================================================================
CORE_ARTIFACTS = [
    "canonical_contact_ledger.csv",
    "admitted_contact_ledger.csv",
    "rejected_contact_ledger.psv",
    "normalized_contact_intervals.tsv",
    "antenna_capacity_ledger.csv",
    "capacity_cap_exceptions.psv",
    "contention_groups.jsonl",
    "winning_resource_assignments.csv",
    "displaced_contact_ledger.psv",
    "mission_entitlement_state.csv",
    "carry_forward_ledger.csv",
    "rationing_pass_trace.jsonl",
    "delivered_volume_ledger.csv",
    "deferred_volume_ledger.csv",
    "unused_capacity_ledger.tsv",
    "station_utilisation_ledger.csv",
    "antenna_utilisation_ledger.tsv",
    "mission_settlement_statements.csv",
    "station_settlement_statements.csv",
    "contract_compliance_ledger.csv",
    "credit_debit_ledger.csv",
    "outage_adjustment_ledger.psv",
    "exception_classification_report.jsonl",
    "tie_resolution_report.csv",
    "cross_source_discrepancy_report.psv",
    "invariant_check_report.json",
    "period_reconciliation_totals.json",
    "network_settlement_summary.xml",
    "per_mission_final_summary.md",
]
MANIFEST_NAME = "stage_digest_manifest.json"
ALL_ARTIFACTS = CORE_ARTIFACTS + [MANIFEST_NAME]
PROGRAM_NAME = "settle.py"


def as_cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(int(value))
    return str(value)


def emit_table(columns, records, sep):
    lines = [sep.join(columns)]
    for record in records:
        lines.append(sep.join(as_cell(record.get(name)) for name in columns))
    return (LF.join(lines) + LF).encode("utf-8")


def emit_jsonl(records):
    if not records:
        return b""
    body = []
    for record in records:
        body.append(json.dumps(record, sort_keys=True, ensure_ascii=True,
                               separators=(",", ":")))
    return (LF.join(body) + LF).encode("utf-8")


def emit_json(document):
    return (json.dumps(document, sort_keys=True, ensure_ascii=True, indent=2)
            + LF).encode("utf-8")


def emit_text(text):
    return (text + LF).encode("utf-8")


def xml_escape(value):
    return (str(value).replace("&", "&amp;").replace(LT, "&lt;")
            .replace(GT, "&gt;").replace(DQ, "&quot;"))


def tagged(name, value):
    return LT + name + GT + xml_escape(value) + LT + "/" + name + GT


# ===========================================================================
# the run
# ===========================================================================
def settle(data_dir):
    """Runs the fourteen stages over one data directory and returns the
    artifact bytes, keyed by artifact name."""
    papers = Papers(data_dir)
    register = Register(papers)
    free = build_availability(papers, register)
    windows = build_period_windows(papers, register)
    periods = period_ids_of(windows)

    gate = Admission(papers, register, free, windows, periods)
    rows = gate.rows
    derive_capacity(papers, register, rows)
    apply_precedence(papers, register, rows)
    for row in rows:
        row["obligation_open"] = opening_obligation(register, row, row["period_id"])
        row["contract_id"] = ""
        row["demand_kib"] = 0
        row["allocated_kib"] = 0
        row["accepted_kib"] = 0
        row["from_carry_kib"] = 0
        row["from_new_kib"] = 0
        row["deferred_kib"] = 0
        row["unused_capacity_kib"] = 0
    groups, ties = resolve_contention(rows)

    backlog_open = {}
    for report in papers.backlogs:
        if report["report_state"] != "current":
            continue
        key = (report["mission_id"], report["period_id"])
        seat = backlog_open.get(key)
        if seat is None or whole(report["report_seq"]) > seat[0]:
            backlog_open[key] = (whole(report["report_seq"]),
                                 whole(report["backlog_kib"]))
    backlog_open = dict((key, value[1]) for key, value in backlog_open.items())

    traces, overspend, quiet = allocate_volume(papers, rows, backlog_open)
    entitlement = settle_accounts(
        register, rows, periods, opening_carry(papers, register), backlog_open,
        windows, register.contract_ids)
    per_aperture, per_station = measure_utilisation(
        register, rows, free, windows, periods)
    credits, compliance, outages = price_settlement(
        papers, register, rows, entitlement, periods)

    return assemble(papers, register, rows, gate, groups, ties, traces,
                    entitlement, credits, compliance, outages, per_aperture,
                    per_station, periods, overspend, quiet)


def assemble(papers, register, rows, gate, groups, ties, traces, entitlement,
             credits, compliance, outages, per_aperture, per_station, periods,
             overspend, quiet):
    """S14. Projection and emission only, over values the stages froze."""
    order = sorted(rows, key=lambda r: (r["contact_id"], r["period_id"]))
    won = [r for r in order if r["allocation_state"] == "won"]
    lost = [r for r in order if r["allocation_state"] == "displaced"]
    art = OrderedDict()

    art["canonical_contact_ledger.csv"] = emit_table([
        "contact_id", "period_id", "station_id", "antenna_uid", "mission_id",
        "contract_id", "eligible_seconds", "raw_capacity_kib",
        "usable_capacity_kib", "effective_class", "protected", "late_cancel",
        "allocation_state", "demand_kib", "allocated_kib", "accepted_kib",
    ], order, ",")

    art["admitted_contact_ledger.csv"] = emit_table([
        "contact_id", "period_id", "station_id", "antenna_uid", "mission_id",
        "presentation_id", "scheduled_start_s", "scheduled_end_s",
        "commit_boundary_s", "event_status", "operator_code", "protected",
        "late_cancel", "eligible_seconds",
    ], order, ",")

    art["rejected_contact_ledger.psv"] = emit_table([
        "contact_id", "station_id", "aperture_label", "presentation_id",
        "scheduled_start_s", "scheduled_end_s", "predicate_index",
        "reject_code", "reject_reason",
    ], sorted(gate.rejected, key=lambda r: r["contact_id"]), "|")

    segments = sorted(gate.segments, key=lambda s: (s[0], s[1], s[3]))
    art["normalized_contact_intervals.tsv"] = emit_table([
        "contact_id", "period_id", "antenna_uid", "segment_start_s",
        "segment_end_s", "segment_seconds",
    ], [dict(zip(("contact_id", "period_id", "antenna_uid", "segment_start_s",
                  "segment_end_s", "segment_seconds"), s)) for s in segments],
        chr(9))

    art["antenna_capacity_ledger.csv"] = emit_table([
        "contact_id", "period_id", "antenna_uid", "eligible_seconds",
        "rate_piece_count", "raw_capacity_kib", "capacity_cap_kib",
        "usable_capacity_kib",
    ], order, ",")

    clipped = []
    for row in order:
        if row["raw_capacity_kib"] > row["capacity_cap_kib"]:
            clipped.append(dict(row, clipped_kib=(row["raw_capacity_kib"]
                                                  - row["capacity_cap_kib"])))
    art["capacity_cap_exceptions.psv"] = emit_table([
        "contact_id", "period_id", "antenna_uid", "raw_capacity_kib",
        "capacity_cap_kib", "clipped_kib",
    ], clipped, "|")

    art["contention_groups.jsonl"] = emit_jsonl(sorted(
        groups, key=lambda g: (g["antenna_uid"], g["period_id"], g["group_seq"])))

    art["winning_resource_assignments.csv"] = emit_table([
        "contact_id", "period_id", "antenna_uid", "mission_id",
        "effective_class", "effective_rank", "protected", "commit_boundary_s",
        "remaining_obligation_kib", "eligible_seconds", "usable_capacity_kib",
    ], [dict(r, remaining_obligation_kib=r["obligation_open"]) for r in won], ",")

    art["displaced_contact_ledger.psv"] = emit_table([
        "contact_id", "period_id", "antenna_uid", "mission_id", "displaced_by",
        "displaced_seconds", "usable_capacity_kib",
    ], [dict(r, displaced_seconds=r["eligible_seconds"]) for r in lost], "|")

    purses = sorted(entitlement, key=lambda p: (p["contract_id"], p["period_id"]))
    art["mission_entitlement_state.csv"] = emit_table([
        "contract_id", "period_id", "carry_source_kib", "carry_cap_kib",
        "carry_in_kib", "carry_forfeit_kib", "entitlement_kib",
        "available_allowance_kib", "consumed_kib", "unconsumed_kib",
        "contract_expired",
    ], purses, ",")

    art["carry_forward_ledger.csv"] = emit_table([
        "contract_id", "period_id", "carry_in_kib", "carry_forfeit_kib",
        "carry_out_kib", "carry_forward_enabled",
    ], purses, ",")

    art["rationing_pass_trace.jsonl"] = emit_jsonl(sorted(
        traces, key=lambda t: (t["antenna_uid"], t["period_id"], t["pass_seq"])))

    art["delivered_volume_ledger.csv"] = emit_table([
        "contact_id", "period_id", "mission_id", "contract_id", "antenna_uid",
        "demand_kib", "allocated_kib", "accepted_kib", "from_carry_kib",
        "from_new_kib",
    ], won, ",")

    art["deferred_volume_ledger.csv"] = emit_table([
        "contact_id", "period_id", "mission_id", "demand_kib", "accepted_kib",
        "deferred_kib", "late_cancel",
    ], won, ",")

    art["unused_capacity_ledger.tsv"] = emit_table([
        "contact_id", "period_id", "antenna_uid", "usable_capacity_kib",
        "accepted_kib", "unused_capacity_kib",
    ], won, chr(9))

    art["station_utilisation_ledger.csv"] = emit_table([
        "station_id", "period_id", "occupied_seconds", "available_seconds",
        "utilisation_bp", "denominator_state",
    ], per_station, ",")

    art["antenna_utilisation_ledger.tsv"] = emit_table([
        "antenna_uid", "period_id", "occupied_seconds", "available_seconds",
        "utilisation_bp", "denominator_state",
    ], per_aperture, chr(9))

    net_by_contract = dict(((c["contract_id"], c["period_id"]), c["net_mcr"])
                           for c in credits)
    mission_net = defaultdict(int)
    for purse in entitlement:
        mission_net[(purse["mission_id"], purse["period_id"])] += net_by_contract.get(
            (purse["contract_id"], purse["period_id"]), 0)

    mission_rows = []
    for mission in register.mission_ids:
        for period in periods:
            share = [r for r in won
                     if r["mission_id"] == mission and r["period_id"] == period]
            mission_rows.append({
                "mission_id": mission, "period_id": period,
                "won_pass_count": len(share),
                "eligible_seconds": sum(r["eligible_seconds"] for r in share),
                "usable_capacity_kib": sum(r["usable_capacity_kib"] for r in share),
                "accepted_kib": sum(r["accepted_kib"] for r in share),
                "deferred_kib": sum(r["deferred_kib"] for r in share),
                "unused_capacity_kib": sum(r["unused_capacity_kib"] for r in share),
                "net_mcr": mission_net.get((mission, period), 0),
            })
    art["mission_settlement_statements.csv"] = emit_table([
        "mission_id", "period_id", "won_pass_count", "eligible_seconds",
        "usable_capacity_kib", "accepted_kib", "deferred_kib",
        "unused_capacity_kib", "net_mcr",
    ], mission_rows, ",")

    station_bp = dict(((s["station_id"], s["period_id"]), s["utilisation_bp"])
                      for s in per_station)
    station_rows = []
    for station in register.station_ids:
        for period in periods:
            share = [r for r in won
                     if r["station_id"] == station and r["period_id"] == period]
            station_rows.append({
                "station_id": station, "period_id": period,
                "won_pass_count": len(share),
                "eligible_seconds": sum(r["eligible_seconds"] for r in share),
                "accepted_kib": sum(r["accepted_kib"] for r in share),
                "unused_capacity_kib": sum(r["unused_capacity_kib"] for r in share),
                "utilisation_bp": station_bp.get((station, period), 0),
            })
    art["station_settlement_statements.csv"] = emit_table([
        "station_id", "period_id", "won_pass_count", "eligible_seconds",
        "accepted_kib", "unused_capacity_kib", "utilisation_bp",
    ], station_rows, ",")

    art["contract_compliance_ledger.csv"] = emit_table([
        "contract_id", "period_id", "mission_id", "obligation_kib",
        "delivered_kib", "reserved_kib", "shortfall_kib", "compliance_state",
    ], sorted(compliance, key=lambda c: (c["contract_id"], c["period_id"])), ",")

    art["credit_debit_ledger.csv"] = emit_table([
        "contract_id", "period_id", "shortfall_kib", "shortfall_debit_mcr",
        "unused_reserved_kib", "unused_credit_mcr", "outage_credit_mcr",
        "carry_restore_kib", "net_mcr",
    ], sorted(credits, key=lambda c: (c["contract_id"], c["period_id"])), ",")

    art["outage_adjustment_ledger.psv"] = emit_table([
        "contract_id", "period_id", "mission_id", "claim_overlap_seconds",
        "qualifying_floor_seconds", "outage_qualified", "exempt_kib",
        "carry_restore_kib",
    ], sorted(outages, key=lambda o: (o["contract_id"], o["period_id"])), "|")

    art["exception_classification_report.jsonl"] = emit_jsonl(
        exception_records(papers, gate, order, won, lost, purses, per_aperture))

    art["tie_resolution_report.csv"] = emit_table([
        "antenna_uid", "period_id", "contact_id_kept", "contact_id_yielded",
        "decided_at_level",
    ], sorted(ties, key=lambda t: (t["antenna_uid"], t["period_id"],
                                  t["contact_id_kept"], t["contact_id_yielded"])),
        ",")

    art["cross_source_discrepancy_report.psv"] = emit_table([
        "source_left", "source_right", "subject_id", "period_id", "left_value",
        "right_value", "delta_value", "discrepancy_class",
    ], discrepancies(papers, register, won), "|")

    checks = invariants(order, won, lost, purses, credits, traces, overspend,
                        quiet)
    art["invariant_check_report.json"] = emit_json({
        "check_count": len(checks),
        "checks": checks,
        "all_balanced": int(all(c["balanced"] == 1 for c in checks)),
    })

    art["period_reconciliation_totals.json"] = emit_json(period_totals(
        won, purses, credits, per_aperture, periods))

    art["network_settlement_summary.xml"] = emit_text(summary_xml(
        mission_rows, station_rows, credits))

    art["per_mission_final_summary.md"] = emit_text(summary_md(
        register, won, mission_net, periods))

    digest = hashlib.sha256()
    per_artifact = {}
    for name in CORE_ARTIFACTS:
        digest.update(art[name])
        per_artifact[name] = hashlib.sha256(art[name]).hexdigest()
    art[MANIFEST_NAME] = emit_json({
        "artifact_count": len(CORE_ARTIFACTS),
        "stage_count": 14,
        "core_digest": digest.hexdigest(),
        "per_artifact_sha256": per_artifact,
    })
    return art


def exception_records(papers, gate, order, won, lost, purses, per_aperture):
    """Admission rejections, cap clippings, displacements, carry forfeits,
    empty denominators and late cancellations, in one report."""
    book = papers.code_index()

    def klass(code):
        return book.get(code, {}).get("report_class", "")

    records = []
    # _period is the fourth sort key the schema publishes. It is stripped
    # before return, because the period orders the record without being a
    # field of it.
    for row in sorted(gate.rejected, key=lambda r: r["contact_id"]):
        records.append({
            "exception_class": klass(row["reject_code"]),
            "subject_id": row["contact_id"],
            "code": row["reject_code"],
            "detail_value": row["predicate_index"],
            "_period": row.get("period_id", ""),
        })
    for row in order:
        if row["raw_capacity_kib"] > row["capacity_cap_kib"]:
            records.append({
                "exception_class": klass("X01"), "subject_id": row["contact_id"],
                "code": "X01",
                "detail_value": row["raw_capacity_kib"] - row["capacity_cap_kib"],
                "_period": row.get("period_id", ""),
            })
    for row in lost:
        records.append({
            "exception_class": klass("X02"), "subject_id": row["contact_id"],
            "code": "X02", "detail_value": row["eligible_seconds"],
            "_period": row.get("period_id", ""),
        })
    for purse in purses:
        if purse["carry_forfeit_kib"] > 0:
            records.append({
                "exception_class": klass("X03"),
                "subject_id": purse["contract_id"], "code": "X03",
                "detail_value": purse["carry_forfeit_kib"],
                "_period": purse.get("period_id", ""),
            })
    for entry in per_aperture:
        if entry["denominator_state"] == "empty":
            records.append({
                "exception_class": klass("X04"),
                "subject_id": entry["antenna_uid"], "code": "X04",
                "detail_value": 0,
                "_period": entry.get("period_id", ""),
            })
    for row in won:
        if row["late_cancel"] == 1:
            records.append({
                "exception_class": klass("X05"), "subject_id": row["contact_id"],
                "code": "X05", "detail_value": row["deferred_kib"],
                "_period": row.get("period_id", ""),
            })
    records.sort(key=lambda r: (r["exception_class"], r["subject_id"],
                                r["code"], r["_period"]))
    for row in records:
        del row["_period"]
    return records


def discrepancies(papers, register, won):
    """Two families: the canonical ledger against the reported downlink, and
    the effective schedule against the retired flat table."""
    out = []
    accepted_by_pass = defaultdict(int)
    for row in won:
        accepted_by_pass[row["contact_id"]] += row["accepted_kib"]
    binding_report = {}
    for report in papers.reports:
        contact = report["contact_id"]
        seat = binding_report.get(contact)
        if seat is None or whole(report["report_seq"]) > whole(seat["report_seq"]):
            binding_report[contact] = report
    for contact in sorted(accepted_by_pass):
        report = binding_report.get(contact)
        if report is None:
            continue
        left = accepted_by_pass[contact]
        right = whole(report["reported_kib"])
        if left == right:
            continue
        out.append({
            "source_left": "canonical_ledger", "source_right": "downlink_report",
            "subject_id": contact, "period_id": "", "left_value": left,
            "right_value": right, "delta_value": left - right,
            "discrepancy_class": "over_report" if right > left else "under_report",
        })

    band = defaultdict(list)
    for row in papers.rates:
        band[row["antenna_uid"]].append(whole(row["rate_mkib_per_s"]))
    binding_legacy = {}
    for row in papers.legacy:
        uid = row["antenna_uid"]
        seat = binding_legacy.get(uid)
        if seat is None or whole(row["table_rev"]) > whole(seat["table_rev"]):
            binding_legacy[uid] = row
    for uid in sorted(binding_legacy):
        rates = band.get(uid)
        if not rates:
            continue
        low = min(rates)
        high = max(rates)
        flat = whole(binding_legacy[uid]["flat_rate_mkib_per_s"])
        if low <= flat <= high:
            continue
        left = low if flat < low else high
        out.append({
            "source_left": "rate_schedule", "source_right": "legacy_flat_table",
            "subject_id": uid, "period_id": "", "left_value": left,
            "right_value": flat, "delta_value": left - flat,
            "discrepancy_class": "retired_rate_outside_band",
        })
    out.sort(key=lambda r: (r["source_left"], r["subject_id"]))
    return out


def invariants(order, won, lost, purses, credits, traces, overspend, quiet):
    """The fixed balance checks of output_schema_reference.md, in order."""
    pairs = [
        ("admitted_equals_won_plus_displaced", len(order), len(won) + len(lost)),
        ("accepted_never_exceeds_allocated",
         sum(1 for r in won if r["accepted_kib"] > r["allocated_kib"]), 0),
        ("allocated_never_exceeds_demand",
         sum(1 for r in won if r["allocated_kib"] > r["demand_kib"]), 0),
        ("unused_matches_capacity_less_accepted",
         sum(r["unused_capacity_kib"] for r in won),
         sum(r["usable_capacity_kib"] - r["accepted_kib"] for r in won)),
        ("carry_split_matches_accepted",
         sum(r["accepted_kib"] for r in won),
         sum(r["from_carry_kib"] + r["from_new_kib"] for r in won)),
        ("allocation_within_aperture_budget", overspend, 0),
        ("credit_rows_match_entitlement_rows", len(credits), len(purses)),
        ("ration_trace_groups_are_over_subscribed", quiet, 0),
    ]
    return [{"check_name": name, "left_value": left, "right_value": right,
             "balanced": int(left == right)} for name, left, right in pairs]


def period_totals(won, purses, credits, per_aperture, periods):
    """One block per settlement period plus the network roll up."""
    document = {}
    for period in periods:
        share = [r for r in won if r["period_id"] == period]
        seats = [p for p in purses if p["period_id"] == period]
        money = [c for c in credits if c["period_id"] == period]
        dishes = [a for a in per_aperture if a["period_id"] == period]
        document[period] = {
            "won_pass_count": len(share),
            "eligible_seconds": sum(r["eligible_seconds"] for r in share),
            "usable_capacity_kib": sum(r["usable_capacity_kib"] for r in share),
            "accepted_kib": sum(r["accepted_kib"] for r in share),
            "deferred_kib": sum(r["deferred_kib"] for r in share),
            "unused_capacity_kib": sum(r["unused_capacity_kib"] for r in share),
            "carry_in_kib": sum(p["carry_in_kib"] for p in seats),
            "carry_forfeit_kib": sum(p["carry_forfeit_kib"] for p in seats),
            "carry_out_kib": sum(p["carry_out_kib"] for p in seats),
            "shortfall_debit_mcr": sum(c["shortfall_debit_mcr"] for c in money),
            "unused_credit_mcr": sum(c["unused_credit_mcr"] for c in money),
            "outage_credit_mcr": sum(c["outage_credit_mcr"] for c in money),
            "net_mcr": sum(c["net_mcr"] for c in money),
            "occupied_seconds": sum(a["occupied_seconds"] for a in dishes),
            "available_seconds": sum(a["available_seconds"] for a in dishes),
        }
    document["network"] = {
        "net_mcr": sum(c["net_mcr"] for c in credits),
        "accepted_kib": sum(r["accepted_kib"] for r in won),
        "won_pass_count": len(won),
    }
    return document


def summary_xml(mission_rows, station_rows, credits):
    lines = [XML_HEAD, LT + "settlement" + GT, LT + "missions" + GT]
    for row in mission_rows:
        lines.append(
            LT + 'mission id=' + DQ + xml_escape(row["mission_id"]) + DQ
            + ' period=' + DQ + xml_escape(row["period_id"]) + DQ + GT
            + tagged("accepted_kib", row["accepted_kib"])
            + tagged("deferred_kib", row["deferred_kib"])
            + tagged("net_mcr", row["net_mcr"])
            + LT + "/mission" + GT)
    lines.append(LT + "/missions" + GT)
    lines.append(LT + "stations" + GT)
    for row in station_rows:
        lines.append(
            LT + 'station id=' + DQ + xml_escape(row["station_id"]) + DQ
            + ' period=' + DQ + xml_escape(row["period_id"]) + DQ + GT
            + tagged("accepted_kib", row["accepted_kib"])
            + tagged("utilisation_bp", row["utilisation_bp"])
            + LT + "/station" + GT)
    lines.append(LT + "/stations" + GT)
    lines.append(LT + "network" + GT)
    lines.append(tagged("net_mcr", sum(c["net_mcr"] for c in credits)))
    lines.append(tagged("contract_period_count", len(credits)))
    lines.append(LT + "/network" + GT)
    lines.append(LT + "/settlement" + GT)
    return LF.join(lines)


def summary_md(register, won, mission_net, periods):
    lines = ["# mission settlement summary", "",
             "| mission_id | accepted_kib | deferred_kib | unused_capacity_kib"
             " | net_mcr |",
             "| --- | --- | --- | --- | --- |"]
    total = 0
    for mission in register.mission_ids:
        share = [r for r in won if r["mission_id"] == mission]
        money = sum(mission_net.get((mission, period), 0) for period in periods)
        total += money
        lines.append("| " + " | ".join([
            mission,
            str(sum(r["accepted_kib"] for r in share)),
            str(sum(r["deferred_kib"] for r in share)),
            str(sum(r["unused_capacity_kib"] for r in share)),
            str(money),
        ]) + " |")
    lines.append("")
    lines.append("network net_mcr " + str(total))
    return LF.join(lines)


def main(argv):
    parser = argparse.ArgumentParser(prog=PROGRAM_NAME)
    parser.add_argument("--data", required=True)
    parser.add_argument("--out", required=True)
    known = parser.parse_args(argv[1:])
    target = Path(known.out)
    target.mkdir(parents=True, exist_ok=True)
    artifacts = settle(known.data)
    for name in ALL_ARTIFACTS:
        (target / name).write_bytes(artifacts[name])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
