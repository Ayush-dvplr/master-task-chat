#!/usr/bin/env python3
"""Recompute one operating day of the Ashgrove Point reefer power yard.

Usage:
    python3 reeferdispatch.py --data <input directory> --out <output directory>

Both options may be given in either order. When neither is given the program
works on /app/data and /app/out. Standard library only, exact rational
arithmetic throughout, no binary floating point anywhere in the derivation.

The work is organised as a Papers reader, a Day holding the fourteen stages as
separately named steps, and a Publication writer.
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
import xml.etree.ElementTree as ET
from fractions import Fraction
from pathlib import Path

SLOT_MINUTES = 15
SLOTS = 96
APPLICABLE = ("current", "filed", "booked", "landed")
SENTINEL_SLACK = 999
SENTINEL_URGENCY = 9

SPREADSHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
RELATION_ID = ("{http://schemas.openxmlformats.org/officeDocument/2006/"
               "relationships}id")


# ==========================================================================
# rounding, as rounding_and_arithmetic_policy.yaml places it
# ==========================================================================


def half_up(value):
    """A remainder of exactly one half is carried away from zero."""
    value = Fraction(value)
    if value < 0:
        return -((-value * 2 + 1) // 2)
    return (value * 2 + 1) // 2


def down(value):
    return Fraction(value).__floor__()


def up(value):
    return -((-Fraction(value)).__floor__())


def whole(text, fallback=0):
    try:
        return int(str(text).strip())
    except (TypeError, ValueError):
        return fallback


def blank(text):
    return text is None or str(text).strip() in ("", "-")


def nine_places(numerator, denominator):
    if denominator == 0:
        return "0.000000000"
    units = half_up(Fraction(numerator * 1000000000, denominator))
    mark = "-" if units < 0 else ""
    units = abs(units)
    left, right = divmod(units, 1000000000)
    if left == 0 and right == 0:
        mark = ""
    return "%s%d.%09d" % (mark, left, right)


# ==========================================================================
# Papers: every shipped format, read the way its own paper is written
# ==========================================================================


class Papers:

    def __init__(self, root):
        self.root = Path(root)
        self._cache = {}

    def _text(self, name):
        return (self.root / name).read_text(encoding="utf-8")

    def table(self, name, sep=","):
        key = ("table", name)
        if key in self._cache:
            return self._cache[key]
        body = [ln for ln in self._text(name).split("\n") if ln != ""]
        columns = body[0].split(sep) if body else []
        out = []
        for ln in body[1:]:
            cells = ln.split(sep)
            cells += [""] * (len(columns) - len(cells))
            out.append(dict(zip(columns, cells)))
        self._cache[key] = out
        return out

    def records(self, name):
        out = []
        for ln in self._text(name).split("\n"):
            if ln.strip():
                out.append(json.loads(ln))
        return out

    def roster(self, name):
        """The substations the reporting roster publishes, in the order it
        prints them. RULE P14.e of spec_stage_p14_publication.md and the
        serialisation contract both make this paper the authority for which
        reports are published and in what order."""
        out = []
        current = None
        for raw in self._text(name).split("\n"):
            line = raw.strip()
            if not line or line[0] == "#":
                continue
            if line[0] == "[" and line[-1] == "]":
                current = line[1:-1]
            elif current is not None and "=" in line:
                key, _, value = line.partition("=")
                if key.strip() == "published":
                    if value.strip() == "yes" and current not in out:
                        out.append(current)
                    current = None
        return out

    def document(self, name):
        return json.loads(self._text(name))

    def tree(self, name):
        return ET.fromstring(self._text(name))

    def settings(self, name):
        """The declarative papers: sections, scalars, lists, inline tables."""
        block = {}
        where = block
        for raw in self._text(name).split("\n"):
            line = raw.strip()
            if not line or line[0] == "#":
                continue
            if line[0] == "[" and line[-1] == "]":
                where = block.setdefault(line[1:-1], {})
                continue
            if "=" not in line:
                continue
            left, right = line.split("=", 1)
            where[left.strip()] = self._scalar(right.strip())
        return block

    @staticmethod
    def _scalar(text):
        if text[:1] == "{" and text[-1:] == "}":
            inner = {}
            for chunk in text[1:-1].split(","):
                if "=" in chunk:
                    a, b = chunk.split("=", 1)
                    inner[a.strip()] = Papers._scalar(b.strip())
            return inner
        if text[:1] == "[" and text[-1:] == "]":
            body = text[1:-1].strip()
            return [Papers._scalar(c.strip()) for c in body.split(",")] if body else []
        if len(text) > 1 and text[0] == text[-1] == '"':
            return text[1:-1]
        if text in ("true", "false"):
            return text == "true"
        try:
            return int(text)
        except ValueError:
            return text

    def sheets(self, name):
        """Every worksheet of the spreadsheet package, in package order."""
        found = []
        with zipfile.ZipFile(str(self.root / name)) as pack:
            pool = []
            if "xl/sharedStrings.xml" in pack.namelist():
                for item in ET.fromstring(
                        pack.read("xl/sharedStrings.xml")).findall(
                            SPREADSHEET_NS + "si"):
                    pool.append("".join(
                        node.text or "" for node in item.iter(SPREADSHEET_NS + "t")))
            book = ET.fromstring(pack.read("xl/workbook.xml"))
            links = {}
            for link in ET.fromstring(pack.read("xl/_rels/workbook.xml.rels")):
                links[link.get("Id")] = link.get("Target")
            for entry in book.find(SPREADSHEET_NS + "sheets"):
                part = links.get(entry.get(RELATION_ID), "")
                if not part.startswith("xl/"):
                    part = "xl/" + part
                grid = []
                for line in ET.fromstring(pack.read(part)).iter(
                        SPREADSHEET_NS + "row"):
                    cells = []
                    for cell in line.findall(SPREADSHEET_NS + "c"):
                        holder = cell.find(SPREADSHEET_NS + "v")
                        text = holder.text if holder is not None else ""
                        if cell.get("t") == "s" and text:
                            text = pool[int(text)]
                        cells.append(text or "")
                    grid.append(cells)
                found.append((entry.get("name"), grid))
        return found

    def memo(self, name):
        """The text lines of the portable document, in page order."""
        blob = (self.root / name).read_bytes()
        opener = ("stream" + chr(10)).encode("ascii")
        closer = (chr(10) + "end" + "stream").encode("ascii")
        lines = []
        cursor = 0
        while True:
            head = blob.find(opener, cursor)
            if head < 0:
                break
            tail = blob.find(closer, head)
            if tail < 0:
                break
            page = blob[head + len(opener):tail].decode("latin-1", "replace")
            cursor = tail + 1
            for piece in page.split(chr(10)):
                piece = piece.strip()
                if piece[:1] != "(" or ") Tj" not in piece:
                    continue
                shown = piece[1:piece.rfind(") Tj")]
                shown = shown.replace("\\(", "(").replace("\\)", ")")
                lines.append(shown.replace("\\\\", "\\"))
        return lines

    def directive(self, name):
        """The paragraphs and tables of the word processing package."""
        with zipfile.ZipFile(str(self.root / name)) as pack:
            body = ET.fromstring(pack.read("word/document.xml")).find(
                WORD_NS + "body")
        out = []
        for node in body:
            if node.tag == WORD_NS + "p":
                out.append(("text", "".join(
                    t.text or "" for t in node.iter(WORD_NS + "t"))))
            elif node.tag == WORD_NS + "tbl":
                grid = []
                for line in node.findall(WORD_NS + "tr"):
                    grid.append(["".join(t.text or "" for t in cell.iter(
                        WORD_NS + "t")) for cell in line.findall(WORD_NS + "tc")])
                out.append(("grid", grid))
        return out

    def ladder(self, name):
        """The rung codes in the order the ladder paper prints them."""
        out = []
        for line in self._text(name).split("\n"):
            words = line.strip().split()
            if len(words) == 3 and words[0] == "rung" and words[2][:3] == "DR_":
                out.append(words[2])
        return out


# ==========================================================================
# Controls: the three office papers resolved into the values they carry
# ==========================================================================


class Controls:

    def __init__(self, papers, reference):
        self.sheet_name, grid = self._governing(papers, reference)
        self.damping = None
        self.service_charge = 0
        for line in self._block(grid, "control"):
            if line[0] == "reconciliation damping fraction":
                self.damping = Fraction(whole(line[1]), whole(line[2]))
            elif line[0] == "base service charge cents":
                self.service_charge = whole(line[1])
        self.coefficient = dict(
            (line[0], Fraction(whole(line[1]), whole(line[2])))
            for line in self._block(grid, "temperature class"))
        self.share_ceiling = dict(
            (line[0], whole(line[1])) for line in self._block(grid, "vessel"))
        self.substation_ceiling = dict(
            (line[0], whole(line[1])) for line in self._block(grid, "substation"))

        self.budget = 0
        self.minimum_step = 0
        self.protection = 0
        rungs = []
        for line in papers.memo("dispatch_operations_memo.pdf"):
            words = line.strip().split()
            if line.strip().startswith("pass budget "):
                self.budget = whole(words[-1])
            elif line.strip().startswith("minimum step watt hours"):
                self.minimum_step = whole(words[-1])
            elif line.strip().startswith("dependency protection depth"):
                self.protection = whole(words[-1])
            elif len(words) == 2 and words[0].isdigit() and words[1].isdigit():
                rungs.append((int(words[0]), int(words[1])))
        self.surcharge = sorted(set(rungs))

        self.keys = []
        self.class_rank = {}
        for kind, payload in papers.directive("priority_ordering_directive.docx"):
            if kind != "grid" or not payload:
                continue
            head = payload[0]
            if head[:1] == ["key position"]:
                self.keys = [line[1] for line in payload[1:]]
            elif head == ["temperature class", "class rank"]:
                for line in payload[1:]:
                    self.class_rank[line[0]] = whole(line[1])

    @staticmethod
    def _governing(papers, reference):
        """The sheet whose key cell carries this day reference."""
        for name, grid in papers.sheets("substation_capacity_workbook.xlsx"):
            for line in grid[:6]:
                if len(line) > 1 and line[0] == "day reference" \
                        and line[1] == reference:
                    return name, grid
        raise ValueError("no workbook sheet carries the day reference")

    @staticmethod
    def _block(grid, heading):
        collected = []
        started = False
        for line in grid:
            if not started:
                started = bool(line) and line[0] == heading
                continue
            if not line or not line[0]:
                break
            collected.append(line)
        return collected

    def rung_charge(self, short_slots):
        charge = 0
        for edge, cents in self.surcharge:
            if short_slots >= edge:
                charge = cents
        return charge


# ==========================================================================
# precedence, as revision_precedence.toml states it
# ==========================================================================


def governing(rows, keys, day, sequence):
    """This day, an applicable record state, then the highest sequence."""
    kept = {}
    for row in rows:
        if row.get("day_id") != day:
            continue
        if row.get("record_state", "current") not in APPLICABLE:
            continue
        mark = tuple(row.get(k, "") for k in keys)
        seq = whole(row.get(sequence))
        if mark not in kept or seq > kept[mark][0]:
            kept[mark] = (seq, row)
    return dict((k, v[1]) for k, v in kept.items())


def slot_holding(minute):
    return minute // SLOT_MINUTES + 1


def window_slots(opened, closed):
    """Closed at the connect minute, open at the disconnect minute."""
    if closed <= opened:
        return []
    first = max(1, slot_holding(opened))
    last = min(SLOTS, slot_holding(closed - 1))
    return list(range(first, last + 1)) if last >= first else []


# ==========================================================================
# Day: the fourteen stages, one named step each
# ==========================================================================


class Day:

    def __init__(self, papers):
        self.papers = papers
        topology = papers.tree("substation_topology.xml")
        self.day = topology.get("day")
        self.reference = topology.get("reference")
        self.topology = topology
        self.controls = Controls(papers, self.reference)

    # -- p01 ---------------------------------------------------------------
    def stage_p01_unit_normalisation(self):
        p = self.papers
        day = self.day
        self.plug_of = governing(p.table("plug_assignment_register.csv"),
                                 ["plug_id"], day, "revision_seq")
        self.feeder_of = governing(p.table("feeder_capacity_register.csv"),
                                   ["feeder_id"], day, "revision_seq")
        self.call_of = governing(p.table("vessel_call_register.csv"),
                                 ["vessel_id"], day, "revision_seq")
        returns = governing(p.table("energy_declaration_returns.psv", "|"),
                            ["reefer_id"], day, "declaration_seq")
        presented = governing(p.table("reefer_service_register.csv"),
                              ["reefer_id"], day, "revision_seq")

        self.live_feeders = set()
        for node in self.topology.iter("feeder"):
            self.live_feeders.add(node.get("id"))

        units = p.settings("unit_register_dictionary.toml")
        power = units.get("power", {})
        energy = units.get("energy", {})

        self.reefers = []
        for mark in sorted(presented):
            row = presented[mark]
            name = row["reefer_id"]
            plug = row["plug_id"]
            seat = self.plug_of.get((plug,))
            feeder = seat["feeder_id"] if seat else ""
            station = ""
            if feeder and (feeder,) in self.feeder_of:
                station = self.feeder_of[(feeder,)]["substation_id"]
            scale = self._factor(power, row["nameplate_unit"])
            if scale is None:
                watts, unit_state = 0, "unknown_unit"
            else:
                watts = half_up(Fraction(whole(row["nameplate_value"])) * scale)
                unit_state = "converted"
            filed = returns.get((name,))
            asked = "not_declared"
            if filed is not None and not blank(filed.get("declared_value")):
                other = self._factor(energy, filed.get("energy_unit"))
                if other is not None:
                    asked = half_up(
                        Fraction(whole(filed.get("declared_value"))) * other)
            self.reefers.append({
                "reefer_id": name,
                "plug_id": plug,
                "feeder_id": feeder,
                "substation_id": station,
                "vessel_id": row["vessel_id"],
                "temperature_class": row["temperature_class"],
                "nameplate_w": watts,
                "unit_state": unit_state,
                "connect_minute": whole(row["connect_minute"]),
                "disconnect_minute": whole(row["disconnect_minute"]),
                "declared_energy_wh": asked,
                "source_system": row["source_system"],
            })
        self.by_name = dict((r["reefer_id"], r) for r in self.reefers)

    @staticmethod
    def _factor(table, unit):
        entry = table.get(unit)
        if not isinstance(entry, dict):
            return None
        return Fraction(whole(entry.get("numerator")),
                        whole(entry.get("denominator"), 1))

    # -- p02 ---------------------------------------------------------------
    def stage_p02_availability_lattice(self):
        p = self.papers
        self.calendar = dict(
            (whole(row["interval"]), row)
            for row in p.table("interval_grid_calendar.csv")
            if row.get("day_id") == self.day)

        self.shut = {"feeder": {}, "plug": {}, "crane": {}, "battery": set()}
        for row in p.table("maintenance_window_register.csv"):
            if row.get("day_id") != self.day or row.get("window_state") != "booked":
                continue
            span = set(range(max(1, whole(row["first_interval"])),
                             min(SLOTS, whole(row["last_interval"])) + 1))
            kind = row["resource_kind"]
            if kind == "battery":
                self.shut["battery"] |= span
            elif kind in self.shut:
                self.shut[kind].setdefault(row["resource_id"], set()).update(span)

        self.slots = {}
        self.lattice_rows = []
        for r in self.reefers:
            name = r["reefer_id"]
            held = [n for n in window_slots(r["connect_minute"],
                                            r["disconnect_minute"])
                    if n not in self.shut["feeder"].get(r["feeder_id"], ())
                    and n not in self.shut["plug"].get(r["plug_id"], ())]
            self.slots[name] = held
            shape = "empty" if not held else (
                "single_slot" if len(held) == 1 else "open")
            self.lattice_rows.append([name, held[0] if held else 0,
                                      held[-1] if held else 0, len(held), shape])

        self.demand = {}
        for r in self.reefers:
            for n in self.slots[r["reefer_id"]]:
                seen = self.demand.setdefault((n, r["feeder_id"]), [0, 0])
                seen[0] += 1
                seen[1] += r["nameplate_w"]

    # -- p03 ---------------------------------------------------------------
    def stage_p03_energy_floor(self):
        readings = self.papers.document("ambient_condition_returns.json")
        self.multiplier = {}
        for line in readings["multiplier_table"]:
            self.multiplier[(line["temperature_class"], line["ambient_class"])] = \
                Fraction(whole(line["multiplier_numerator"]),
                         whole(line["multiplier_denominator"], 1))
        fallback = readings["class_default_multiplier"]
        self.default_multiplier = Fraction(
            whole(fallback["multiplier_numerator"]),
            whole(fallback["multiplier_denominator"], 1))
        self.air = dict((whole(line["interval"]), line["ambient_class"])
                        for line in readings["interval_readings"]
                        if line.get("day_id") == self.day)

        self.floor = {}
        self.pull = {}
        self.floor_rows = []
        for r in self.reefers:
            name = r["reefer_id"]
            coefficient = self.controls.coefficient.get(
                r["temperature_class"], Fraction(1))
            per_slot = {}
            per_pull = {}
            mandatory = 0
            for n in self.slots[name]:
                air = self.air.get(n, "temperate")
                lift = self.multiplier.get((r["temperature_class"], air),
                                           self.default_multiplier)
                exact = Fraction(r["nameplate_w"]) * lift * coefficient
                per_slot[n] = half_up(exact / 4)
                per_pull[n] = half_up(exact)
                mandatory += per_slot[n]
            self.floor[name] = per_slot
            self.pull[name] = per_pull
            if r["declared_energy_wh"] == "not_declared":
                asked, shape = mandatory, "defaulted"
            else:
                asked, shape = r["declared_energy_wh"], "declared"
            r["mandatory_wh"] = mandatory
            r["requested_wh"] = asked
            r["discretionary_wh"] = max(0, asked - mandatory)
            self.floor_rows.append([name, len(per_slot), mandatory, asked,
                                    r["discretionary_wh"], shape])

    # -- p04 ---------------------------------------------------------------
    def stage_p04_priority_queue(self):
        p = self.papers
        admits = {}
        for mark, row in governing(p.table("plug_zone_admission_matrix.csv"),
                                   ["plug_zone", "temperature_class"], self.day,
                                   "revision_seq").items():
            admits[mark] = row["admission"]

        self.waived = set()
        self.critical = set()
        for note in p.records("exception_notices.jsonl"):
            if note.get("day_id") != self.day:
                continue
            if note.get("kind") == "zone_waiver":
                self.waived.add(note.get("subject_id"))
            elif note.get("kind") == "priority_override":
                self.critical.add(note.get("subject_id"))

        order = p.ladder("dispatch_admission_ladder.txt")
        self.caught = {}
        standing = []
        for r in self.reefers:
            name = r["reefer_id"]
            hit = ""
            for rung in order:
                if rung == "DR_UNKNOWN_PLUG":
                    seat = self.plug_of.get((r["plug_id"],))
                    if seat is None or seat.get("plug_state") != "live":
                        hit = rung
                elif rung == "DR_FEEDER_OUT_OF_FORCE":
                    if r["feeder_id"] not in self.live_feeders:
                        hit = rung
                elif rung == "DR_WINDOW_EMPTY":
                    if not self.slots[name]:
                        hit = rung
                elif rung == "DR_UNKNOWN_POWER_UNIT":
                    if r["unit_state"] == "unknown_unit":
                        hit = rung
                elif rung == "DR_PLUG_ZONE_REFUSED":
                    seat = self.plug_of.get((r["plug_id"],))
                    zone = seat.get("plug_zone") if seat else ""
                    if admits.get((zone, r["temperature_class"])) == "refused" \
                            and name not in self.waived:
                        hit = rung
                if hit:
                    break
            self.caught[name] = hit
            if not hit:
                standing.append(r)

        clusters = {}
        for r in standing:
            clusters.setdefault(r["plug_id"], []).append(r["reefer_id"])
        for members in clusters.values():
            for name in sorted(members)[1:]:
                self.caught[name] = "DR_DUPLICATE_CONNECTION"

        self.queue = []
        for r in self.reefers:
            name = r["reefer_id"]
            if self.caught[name]:
                continue
            call = self.call_of.get((r["vessel_id"],))
            if call is None:
                r["cutoff"] = SLOTS
                r["slack"] = SENTINEL_SLACK
                r["urgency"] = SENTINEL_URGENCY
                r["group"] = "sg_none"
            else:
                r["cutoff"] = whole(call["cutoff_interval"])
                r["slack"] = r["cutoff"] - self.slots[name][-1]
                r["urgency"] = whole(call["urgency_rank"])
                r["group"] = call["service_group"]
            r["class_rank"] = self.controls.class_rank.get(
                r["temperature_class"], 9)
            self.queue.append(r)

        field = {"deadline_slack": "slack", "class_rank": "class_rank",
                 "urgency_rank": "urgency", "reefer_id": "reefer_id"}
        picked = [field[k] for k in self.controls.keys]
        self.queue.sort(key=lambda r: tuple(r[k] for k in picked))
        self.queue_rows = []
        for place, r in enumerate(self.queue, start=1):
            r["rank"] = place
            self.queue_rows.append([place, r["reefer_id"], r["slack"],
                                    r["class_rank"], r["urgency"], "queued"])
        for r in self.reefers:
            if self.caught[r["reefer_id"]]:
                r["rank"] = 0
                self.queue_rows.append(
                    [0, r["reefer_id"], 0, 0, 0, self.caught[r["reefer_id"]]])

    # -- p05 ---------------------------------------------------------------
    def stage_p05_provisional_allocation(self):
        self.derate = {}
        for mark, row in governing(
                self.papers.table("feeder_derating_notices.csv"),
                ["feeder_id"], self.day, "notice_seq").items():
            self.derate[mark[0]] = (whole(row["first_interval"]),
                                    whole(row["last_interval"]),
                                    whole(row["derate_permille"]))
        self.feeders = sorted(self.live_feeders)
        self.nominal = {}
        for f in self.feeders:
            record = self.feeder_of.get((f,))
            base = whole(record["nominal_capacity_w"]) if record else 0
            note = self.derate.get(f)
            for n in range(1, SLOTS + 1):
                if record is None or n in self.shut["feeder"].get(f, ()):
                    self.nominal[(f, n)] = 0
                elif note and note[0] <= n <= note[1]:
                    self.nominal[(f, n)] = down(Fraction(base * note[2], 1000))
                else:
                    self.nominal[(f, n)] = base

        self.draw = {}
        for r in self.queue:
            for n, watts in self.pull[r["reefer_id"]].items():
                self.draw[(r["reefer_id"], n)] = watts

        self.on = {}
        self.provisional_rows = []
        for n in range(1, SLOTS + 1):
            running = {}
            for r in self.queue:
                name = r["reefer_id"]
                if (name, n) not in self.draw:
                    continue
                f = r["feeder_id"]
                want = self.draw[(name, n)]
                if running.get(f, 0) + want <= self.nominal.get((f, n), 0):
                    running[f] = running.get(f, 0) + want
                    self.on[(name, n)] = True
                else:
                    self.on[(name, n)] = False
            for r in self.queue:
                name = r["reefer_id"]
                if (name, n) in self.draw:
                    self.provisional_rows.append(
                        [n, r["feeder_id"], name, self.draw[(name, n)],
                         "powered" if self.on[(name, n)] else "held"])
        self.provisional_rows.sort(key=lambda row: (row[0], row[1], row[2]))

    # -- p06 ---------------------------------------------------------------
    def stage_p06_feeder_reconciliation(self):
        self.reserve = {}
        self.reserved = {}
        for f in self.feeders:
            record = self.feeder_of.get((f,))
            keep = whole(record["standing_reserve_w"]) if record else 0
            self.reserve[f] = keep
            for n in range(1, SLOTS + 1):
                self.reserved[(f, n)] = max(0, self.nominal[(f, n)] - keep)

        self.present = {}
        for r in self.queue:
            for n in self.slots[r["reefer_id"]]:
                self.present.setdefault(n, []).append(r)

        self.load = dict(((f, n), 0) for f in self.feeders
                         for n in range(1, SLOTS + 1))
        self.violation_rows = []
        self.spill_rows = []
        for n in range(1, SLOTS + 1):
            for r in self.present.get(n, []):
                if self.on.get((r["reefer_id"], n)):
                    self.load[(r["feeder_id"], n)] += self.draw[(r["reefer_id"], n)]
            for f in self.feeders:
                ceiling = self.reserved[(f, n)]
                opening = self.load[(f, n)]
                pulled = 0
                while self.load[(f, n)] > ceiling:
                    here = [r for r in self.present.get(n, [])
                            if r["feeder_id"] == f
                            and self.on.get((r["reefer_id"], n))]
                    if not here:
                        break
                    here.sort(key=lambda r: (-r["rank"], r["reefer_id"]))
                    loser = here[0]["reefer_id"]
                    self.on[(loser, n)] = False
                    self.load[(f, n)] -= self.draw[(loser, n)]
                    pulled += 1
                    landed = 0
                    for m in self.slots[loser]:
                        if m <= n or self.on.get((loser, m)):
                            continue
                        if self.load[(f, m)] + self.draw[(loser, m)] \
                                <= self.reserved[(f, m)]:
                            self.on[(loser, m)] = True
                            self.load[(f, m)] += self.draw[(loser, m)]
                            landed = m
                            break
                    self.spill_rows.append(
                        [loser, n, landed, f, self.draw[(loser, n)],
                         "spilled" if landed else "unspilled"])
                if pulled:
                    self.violation_rows.append(
                        [n, f, opening, ceiling, opening - ceiling, pulled])
        self.spill_rows.sort(key=lambda row: (row[1], row[3], row[0]))

    # -- p07 ---------------------------------------------------------------
    def stage_p07_crane_interaction(self):
        first_word = {}
        for row in self.papers.records("crane_confirmation_journal.jsonl"):
            if row.get("day_id") != self.day:
                continue
            mark = (row["crane_id"], whole(row["interval"]))
            seq = whole(row["confirm_seq"])
            if mark not in first_word or seq < first_word[mark][0]:
                first_word[mark] = (seq, row["confirmation_state"])

        self.crane = {}
        for row in self.papers.records("crane_duty_feed.ndjson"):
            if row.get("day_id") != self.day:
                continue
            crane = row["crane_id"]
            n = whole(row["interval"])
            if n in self.shut["crane"].get(crane, ()):
                continue
            word = first_word.get((crane, n))
            if word is None or word[1] != "landed":
                continue
            mark = (row["feeder_id"], n)
            self.crane[mark] = self.crane.get(mark, 0) + whole(row["demand_kw"]) * 1000

        self.adjusted = {}
        self.adjusted_rows = []
        for n in range(1, SLOTS + 1):
            for f in self.feeders:
                ceiling = self.reserved[(f, n)]
                taken = self.crane.get((f, n), 0)
                left = ceiling - taken
                mark = "clear"
                if left < 0:
                    left, mark = 0, "clamped"
                self.adjusted[(f, n)] = left
                self.adjusted_rows.append([n, f, ceiling, taken, left, mark])

    # -- p08 ---------------------------------------------------------------
    def stage_p08_battery_intervention(self):
        policy = self.papers.settings("battery_operating_policy.toml")
        station = policy["substation_id"]
        room = whole(policy["capacity_wh"])
        floor_wh = whole(policy["reserve_wh"])
        charge_rate = whole(policy["max_charge_w"])
        drain_rate = whole(policy["max_discharge_w"])
        charge_eff = whole(policy["charge_efficiency_permille"])
        drain_eff = whole(policy["discharge_efficiency_permille"])
        bands = policy["charge_eligible_bands"]
        charge = whole(policy["initial_state_of_charge_wh"])

        awake = set(whole(row["interval"])
                    for row in self.papers.table("battery_telemetry_returns.csv")
                    if row.get("day_id") == self.day
                    and row.get("availability_state") == "online")
        mine = [f for f in self.feeders
                if self.feeder_of.get((f,), {}).get("substation_id") == station]

        self.support = dict(((f, n), 0) for f in self.feeders
                            for n in range(1, SLOTS + 1))
        self.battery_rows = []
        self.charge_rows = []
        self.cycled = 0
        for n in range(1, SLOTS + 1):
            opening = charge
            usable = n in awake and n not in self.shut["battery"]
            short = sum(max(0, self.load[(f, n)] - self.adjusted[(f, n)])
                        for f in mine)
            out_wh = 0
            in_wh = 0
            if not usable:
                move, why = "offline", "none"
            elif short > 0:
                move = "discharge"
                by_rate = down(Fraction(drain_rate, 4))
                by_charge = down(Fraction((charge - floor_wh) * drain_eff, 1000))
                wanted = down(Fraction(short, 4))
                out_wh = min(wanted, by_rate, by_charge)
                if out_wh <= 0:
                    out_wh, why = 0, "state_of_charge_on_reserve"
                elif out_wh == by_rate:
                    why = "discharge_limit"
                elif out_wh == by_charge:
                    why = "state_of_charge_limit"
                else:
                    why = "deficit_met"
                charge -= up(Fraction(out_wh * 1000, drain_eff))
                self.cycled += out_wh
            elif self.calendar[n]["tariff_band"] in bands:
                move = "charge"
                spare = sum(max(0, self.adjusted[(f, n)] - self.load[(f, n)])
                            for f in mine)
                by_rate = down(Fraction(charge_rate, 4))
                by_spare = down(Fraction(spare, 4))
                by_room = room - charge
                in_wh = min(by_rate, by_spare, by_room)
                if in_wh <= 0:
                    in_wh, why = 0, "no_room"
                elif in_wh == by_room:
                    why = "capacity_limit"
                elif in_wh == by_rate:
                    why = "charge_limit"
                else:
                    why = "headroom_limit"
                charge += down(Fraction(in_wh * charge_eff, 1000))
                self.cycled += in_wh
            else:
                move, why = "idle", "band_ineligible"
            self.battery_rows.append(
                [n, move, down(Fraction(short, 4)), out_wh, in_wh, why])
            if charge == floor_wh:
                mark = "at_reserve"
            elif charge < floor_wh:
                mark = "below_reserve"
            else:
                mark = "above_reserve"
            self.charge_rows.append([n, opening, charge, floor_wh, mark])
            left = out_wh * 4
            for f in mine:
                need = max(0, self.load[(f, n)] - self.adjusted[(f, n)])
                give = min(need, left)
                self.support[(f, n)] = give
                left -= give

    # -- p09 ---------------------------------------------------------------
    def stage_p09_load_reconciliation(self):
        spare_w = {}
        pool = {}
        for f in self.feeders:
            running = 0
            for n in range(1, SLOTS + 1):
                value = max(0, self.adjusted[(f, n)] + self.support[(f, n)]
                            - self.load[(f, n)])
                spare_w[(f, n)] = value
                running += value
            pool[f] = down(Fraction(running, 4))

        crowd = {}
        for r in self.queue:
            if r["discretionary_wh"] > 0:
                crowd.setdefault(r["feeder_id"], []).append(r)
        for f in crowd:
            crowd[f].sort(key=lambda r: r["rank"])

        self.share = {}
        cap = {}
        for f, band in crowd.items():
            for r in band:
                self.share[r["reefer_id"]] = 0
                cap[r["reefer_id"]] = min(
                    r["discretionary_wh"],
                    self.controls.share_ceiling.get(r["vessel_id"],
                                                    r["discretionary_wh"]))

        self.pass_rows = []
        for turn in range(1, self.controls.budget + 1):
            for f in sorted(crowd):
                band = crowd[f]
                before = dict((r["reefer_id"], self.share[r["reefer_id"]])
                              for r in band)
                gap = dict((r["reefer_id"],
                            max(0, r["discretionary_wh"] - self.share[r["reefer_id"]]))
                           for r in band)
                gap_total = sum(gap.values())
                free = pool[f] - sum(self.share[r["reefer_id"]] for r in band)
                aim = {}
                for r in band:
                    name = r["reefer_id"]
                    if gap_total > 0 and free > 0:
                        aim[name] = Fraction(self.share[name]) + Fraction(
                            free * gap[name], gap_total)
                    else:
                        aim[name] = Fraction(self.share[name])
                spilled = {}
                for r in band:
                    name = r["reefer_id"]
                    if aim[name] > cap[name]:
                        cell = (r["substation_id"], r["group"])
                        spilled[cell] = spilled.get(cell, Fraction(0)) \
                            + aim[name] - cap[name]
                        aim[name] = Fraction(cap[name])
                for cell, mass in spilled.items():
                    open_room = {}
                    for r in band:
                        name = r["reefer_id"]
                        if (r["substation_id"], r["group"]) != cell:
                            continue
                        slack = Fraction(cap[name]) - aim[name]
                        if slack > 0:
                            open_room[name] = slack
                    whole_room = sum(open_room.values())
                    if whole_room <= 0:
                        continue
                    for name, slack in open_room.items():
                        aim[name] += mass * slack / whole_room
                for r in band:
                    name = r["reefer_id"]
                    now = Fraction(self.share[name])
                    stepped = now + self.controls.damping * (aim[name] - now)
                    if stepped != now:
                        delta = stepped - now
                        if 0 < delta < self.controls.minimum_step:
                            stepped = now + self.controls.minimum_step
                        elif 0 < -delta < self.controls.minimum_step:
                            stepped = now - self.controls.minimum_step
                    self.share[name] = max(0, min(half_up(stepped), cap[name]))
                for r in band:
                    name = r["reefer_id"]
                    self.pass_rows.append(
                        [turn, f, name, before[name], gap[name],
                         half_up(aim[name]), self.share[name],
                         "moving" if self.share[name] != before[name] else "settled"])
        self.pass_rows.sort(key=lambda row: (row[0], row[1], row[2]))

        spare_wh = dict((k, down(Fraction(v, 4))) for k, v in spare_w.items())
        self.placed = {}
        self.left_over = {}
        for r in self.queue:
            name = r["reefer_id"]
            owing = self.share.get(name, 0)
            if owing <= 0:
                self.left_over[name] = 0
                continue
            f = r["feeder_id"]
            for n in self.slots[name]:
                if owing <= 0:
                    break
                room = spare_wh.get((f, n), 0)
                if room <= 0:
                    continue
                take = min(owing, room)
                self.placed[(name, n)] = take
                spare_wh[(f, n)] = room - take
                owing -= take
            self.left_over[name] = owing

        self.final = dict(self.load)
        for (name, n), wh in self.placed.items():
            self.final[(self.by_name[name]["feeder_id"], n)] += wh * 4

    # -- p10 ---------------------------------------------------------------
    def stage_p10_tariff_and_demand(self):
        price = {}
        for mark, row in governing(
                self.papers.table("tariff_interval_schedule.csv"),
                ["interval"], self.day, "schedule_seq").items():
            price[whole(mark[0])] = whole(row["price_tenth_cents_per_kwh"])

        self.tariff_rows = []
        self.energy_cents = 0
        self.yard = {}
        for n in range(1, SLOTS + 1):
            watts = sum(self.final[(f, n)] for f in self.feeders)
            self.yard[n] = watts
            stored = half_up(Fraction(watts, 4))
            rate = price.get(n, 0)
            cents = half_up(Fraction(stored * rate, 10000))
            self.energy_cents += cents
            self.tariff_rows.append(
                [n, self.calendar[n]["tariff_band"], rate, watts, stored, cents])

        ladder = {}
        for mark, row in governing(
                self.papers.table("demand_charge_bands.tsv", "\t"),
                ["substation_id", "band_code"], self.day, "revision_seq").items():
            ladder.setdefault(mark[0], []).append(row)
        for station in ladder:
            ladder[station].sort(key=lambda row: whole(row["floor_w"]))

        self.station_load = {}
        for station in self.stations:
            for n in range(1, SLOTS + 1):
                self.station_load[(station, n)] = 0
        for f in self.feeders:
            record = self.feeder_of.get((f,))
            if record is None:
                continue
            station = record["substation_id"]
            for n in range(1, SLOTS + 1):
                self.station_load[(station, n)] = \
                    self.station_load.get((station, n), 0) + self.final[(f, n)]

        self.station_peaks = []
        self.demand_cents = 0
        for station in self.stations:
            top, when = 0, 0
            for n in range(1, SLOTS + 1):
                if self.station_load.get((station, n), 0) > top:
                    top = self.station_load[(station, n)]
                    when = n
            when = when or 1
            code, cents = "", 0
            for row in ladder.get(station, []):
                if whole(row["floor_w"]) <= top < whole(row["ceiling_w"]):
                    code, cents = row["band_code"], whole(row["charge_cents"])
                    break
            self.demand_cents += cents
            self.station_peaks.append(
                {"substation_id": station, "peak_w": top, "peak_interval": when,
                 "band_code": code, "charge_cents": cents})

        self.yard_peak, self.yard_peak_at = 0, 1
        for n in range(1, SLOTS + 1):
            if self.yard[n] > self.yard_peak:
                self.yard_peak, self.yard_peak_at = self.yard[n], n

    # -- p11 and p12 --------------------------------------------------------
    def _standing(self, on):
        book = {}
        for r in self.queue:
            name = r["reefer_id"]
            need = 0
            got = 0
            missed = 0
            for n in self.slots[name]:
                if n > r["cutoff"]:
                    continue
                need += self.floor[name][n]
                if on.get((name, n)):
                    got += self.floor[name][n]
                else:
                    missed += 1
            book[name] = (need, got, max(0, need - got), missed)
        return book

    @staticmethod
    def _fingerprint(on):
        live = sorted(k for k, v in on.items() if v)
        joined = ";".join("%s@%d" % (name, n) for name, n in live)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()

    def stage_p11_deadline_correction(self):
        depth = self.controls.protection
        on = dict(self.on)
        load = dict(self.final)
        headroom = dict(((f, n), self.adjusted[(f, n)] + self.support[(f, n)])
                        for f in self.feeders for n in range(1, SLOTS + 1))
        ranked = sorted(self.queue, key=lambda r: r["rank"])
        frozen = set()
        seen = set()
        loops = []
        self.correction_rows = []
        prints = [self._fingerprint(on)]
        close = "budget_spent"
        settled_at = 0
        allowed = depth + 2
        turns = 0
        for sweep in range(1, allowed + 1):
            turns = sweep
            book = self._standing(on)
            short = [r for r in ranked if book[r["reefer_id"]][2] > 0]
            short.sort(key=lambda r: (0 if r["reefer_id"] in self.critical else 1,
                                      r["rank"]))
            moves = []
            for r in short:
                name = r["reefer_id"]
                if name in frozen:
                    continue
                f = r["feeder_id"]
                for n in self.slots[name]:
                    if n > r["cutoff"] or on.get((name, n)):
                        continue
                    options = []
                    for other in self.present.get(n, []):
                        mate = other["reefer_id"]
                        if mate == name or other["feeder_id"] != f:
                            continue
                        if not on.get((mate, n)) or mate in self.critical \
                                or mate in frozen:
                            continue
                        kept = sum(1 for m in self.slots[mate]
                                   if m <= other["cutoff"] and on.get((mate, m)))
                        if kept > depth:
                            options.append(other)
                    if not options:
                        self.correction_rows.append(
                            [name, n, "", f, "refused_protected"])
                        continue
                    options.sort(key=lambda o: (-o["rank"], o["reefer_id"]))
                    mate = options[0]["reefer_id"]
                    rise = self.draw[(name, n)] - self.draw[(mate, n)]
                    if rise > 0 and load[(f, n)] + rise > headroom[(f, n)]:
                        self.correction_rows.append(
                            [name, n, mate, f, "refused_no_headroom"])
                        continue
                    on[(mate, n)] = False
                    on[(name, n)] = True
                    load[(f, n)] += rise
                    self.correction_rows.append([name, n, mate, f, "corrected"])
                    moves.append((name, mate, n))
                    break
            prints.append(self._fingerprint(on))
            back = [m for m in moves if (m[1], m[0], m[2]) in seen]
            if back:
                best = min(back, key=lambda m: (self.draw[(m[1], m[2])], m[2],
                                                m[1], m[0]))
                for name, mate, n in sorted(back):
                    loops.append({"sweep": sweep, "short_reefer": name,
                                  "displaced_reefer": mate, "interval": n,
                                  "broken": (name, mate, n) == best})
                frozen.add(best[0])
                frozen.add(best[1])
            seen |= set(moves)
            if not moves:
                close = "settled"
                settled_at = sweep
                break
        self.correction_rows.sort(key=lambda row: (row[1], row[3], row[0]))
        self.on_final = on
        self.load_final = load
        self.headroom = headroom
        self.book = self._standing(on)
        self.sweep_record = (turns, allowed, close, settled_at, loops,
                             frozen, prints)

    def stage_p12_cycle_break(self):
        turns, allowed, close, settled_at, loops, frozen, prints = \
            self.sweep_record
        self.cycle_report = {
            "day_id": self.day,
            "sweeps_run": turns,
            "sweep_budget": allowed,
            "closing_state": close,
            "settled_at_sweep": settled_at,
            "correction_count": len([row for row in self.correction_rows
                                     if row[4] == "corrected"]),
            "cycle_count": len(loops),
            "cycles": loops,
            "frozen_reefers": sorted(frozen),
            "state_signatures": [mark[:16] for mark in prints],
        }

    # -- p13 ---------------------------------------------------------------
    def stage_p13_objective(self):
        breaches = 0
        for f in self.feeders:
            for n in range(1, SLOTS + 1):
                if self.load_final[(f, n)] > self.headroom[(f, n)]:
                    breaches += 1
        under = sum(1 for row in self.charge_rows if row[4] == "below_reserve")

        unmet = 0
        fine = 0
        self.certificate_rows = []
        for r in sorted(self.queue, key=lambda r: r["reefer_id"]):
            name = r["reefer_id"]
            need, got, gap, missed = self.book[name]
            unmet += gap
            cents = self.controls.rung_charge(missed) if gap > 0 else 0
            fine += cents
            self.certificate_rows.append(
                [name, r["feeder_id"], r["vessel_id"], need, got, gap, missed,
                 self.share.get(name, 0), self.left_over.get(name, 0), cents,
                 "unmet" if gap > 0 else "met"])

        live = sorted(set(name for name, n in self.on_final
                          if self.on_final[(name, n)]))
        self.objective = {
            "day_id": self.day,
            "lexicographic_order": [
                "hard_violations", "unmet_mandatory_wh", "deadline_penalty_cents",
                "peak_demand_w", "energy_cost_cents", "battery_cycle_wh",
                "tie_key",
            ],
            "hard_violations": breaches + under,
            "unmet_mandatory_wh": unmet,
            "deadline_penalty_cents": fine,
            "peak_demand_w": self.yard_peak,
            "energy_cost_cents": self.energy_cents + self.demand_cents
            + self.controls.service_charge,
            "battery_cycle_wh": self.cycled,
            "tie_key": hashlib.sha256(
                ";".join(live).encode("utf-8")).hexdigest()[:16],
        }
        at_cap = 0
        for r in self.queue:
            name = r["reefer_id"]
            got = self.share.get(name, 0)
            top = min(r["discretionary_wh"],
                      self.controls.share_ceiling.get(r["vessel_id"],
                                                      r["discretionary_wh"]))
            if got > 0 and got == top:
                at_cap += 1
        self.constraints = {
            "day_id": self.day,
            "feeder_intervals_over_capacity": breaches,
            "state_of_charge_below_reserve": under,
            "reefers_at_share_ceiling": at_cap,
            "unplaced_allowance_wh": sum(self.left_over.values()),
            "reefers_refused": len([r for r in self.reefers
                                    if self.caught[r["reefer_id"]]]),
            "reefers_queued": len(self.queue),
            "spill_count": len(self.spill_rows),
            "unspilled_count": len([row for row in self.spill_rows
                                    if row[5] == "unspilled"]),
        }

    def work(self):
        self.rostered = self.papers.roster("reporting_feeder_roster.conf")
        # peak_demand_certificate.json follows the substation order the
        # topology prints, which is a different paper from the roster above.
        self.stations = [node.get("id") for node
                         in self.papers.tree("substation_topology.xml")
                         .findall("substation")]
        self.stage_p01_unit_normalisation()
        self.stage_p02_availability_lattice()
        self.stage_p03_energy_floor()
        self.stage_p04_priority_queue()
        self.stage_p05_provisional_allocation()
        self.stage_p06_feeder_reconciliation()
        self.stage_p07_crane_interaction()
        self.stage_p08_battery_intervention()
        self.stage_p09_load_reconciliation()
        self.stage_p10_tariff_and_demand()
        self.stage_p11_deadline_correction()
        self.stage_p12_cycle_break()
        self.stage_p13_objective()
        return self

    def stage_p14_publication(self, target):
        Publication(self, target).write()


# ==========================================================================
# Publication: stage p14, under the serialisation contract
# ==========================================================================


CORE = ["normalised_reefers.jsonl", "energy_floor_ledger.csv",
        "provisional_allocation.psv", "reconciliation_iterations.csv",
        "objective_vector.json", "final_schedule.csv"]

SPINE = ["normalised_reefers.jsonl", "availability_lattice.csv",
         "energy_floor_ledger.csv", "dispatch_priority_queue.csv",
         "provisional_allocation.psv", "feeder_violation_ledger.csv",
         "crane_adjusted_capacity.csv", "battery_schedule.csv",
         "reconciliation_iterations.csv", "tariff_charge_ledger.csv",
         "deadline_correction.csv", "cycle_break_report.json",
         "objective_vector.json", "final_schedule.csv",
         "publication_manifest.json"]

LOAD_SET = ["interval_demand.csv", "feeder_load_ledger.csv",
            "spill_decisions.tsv", "soc_ledger.psv",
            "constraint_certificate.json"]

TARIFF_SET = ["peak_demand_certificate.json", "unmet_requirement_report.tsv",
              "reefer_service_certificate.csv", "audit_trace.jsonl",
              "dispatch_control_totals.conf"]

PUBLIC_SET = ["final_schedule_by_feeder.psv", "final_schedule_by_vessel.xml",
              "substation_report_sb_alder.json",
              "substation_report_sb_bourne.json",
              "substation_report_sb_calloway.json",
              "daily_dispatch_summary.md"]

EVERY = SPINE + LOAD_SET + TARIFF_SET + PUBLIC_SET


class Publication:

    def __init__(self, day, out):
        self.d = day
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)

    def _sequence(self):
        """EVERY with the substation reports taken in the order the reporting
        roster prints them, which is the order the serialisation contract
        fixes for the documents list and the publication digest."""
        reports = ["substation_report_%s.json" % s for s in self.d.rostered]
        out = []
        for name in EVERY:
            if name.startswith("substation_report_"):
                if reports:
                    out.extend(reports)
                    reports = []
                continue
            out.append(name)
        return out

    def _put(self, name, text):
        (self.out / name).write_text(text, encoding="utf-8", newline="\n")

    def _grid(self, name, head, rows, sep):
        body = [sep.join(head)]
        for row in rows:
            body.append(sep.join("" if c is None else str(c) for c in row))
        self._put(name, "\n".join(body) + "\n")

    def _object(self, name, payload):
        self._put(name, json.dumps(payload, indent=2, sort_keys=False) + "\n")

    def _stream(self, name, payload):
        self._put(name, "\n".join(
            json.dumps(item, separators=(",", ":"), sort_keys=False)
            for item in payload) + "\n")

    @staticmethod
    def _guard(value):
        return (str(value).replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))

    def write(self):
        d = self.d
        self._stream("normalised_reefers.jsonl", [
            {"reefer_id": r["reefer_id"], "plug_id": r["plug_id"],
             "feeder_id": r["feeder_id"], "substation_id": r["substation_id"],
             "vessel_id": r["vessel_id"],
             "temperature_class": r["temperature_class"],
             "nameplate_w": r["nameplate_w"], "unit_state": r["unit_state"],
             "connect_minute": r["connect_minute"],
             "disconnect_minute": r["disconnect_minute"],
             "declared_energy_wh": r["declared_energy_wh"],
             "source_system": r["source_system"]} for r in d.reefers])

        self._grid("availability_lattice.csv",
                   ["reefer_id", "first_interval", "last_interval",
                    "slot_count", "window_state"], d.lattice_rows, ",")

        demand = []
        for n in range(1, SLOTS + 1):
            for f in d.feeders:
                count, watts = d.demand.get((n, f), (0, 0))
                demand.append([n, f, count, watts])
        self._grid("interval_demand.csv",
                   ["interval", "feeder_id", "connected_count",
                    "nominal_demand_w"], demand, ",")

        self._grid("energy_floor_ledger.csv",
                   ["reefer_id", "slot_count", "mandatory_wh", "requested_wh",
                    "discretionary_wh", "floor_state"], d.floor_rows, ",")

        self._grid("dispatch_priority_queue.csv",
                   ["rank", "reefer_id", "deadline_slack", "class_rank",
                    "urgency_rank", "queue_state"], d.queue_rows, ",")

        self._grid("provisional_allocation.psv",
                   ["interval", "feeder_id", "reefer_id", "draw_w",
                    "allocation_state"], d.provisional_rows, "|")

        ledger = []
        for n in range(1, SLOTS + 1):
            for f in d.feeders:
                held = d.reserved[(f, n)]
                value = d.load[(f, n)]
                mark = ("over_capacity" if value > held else
                        ("at_capacity" if value == held else "clear"))
                ledger.append([n, f, d.nominal[(f, n)], d.reserve[f], held,
                               value, held - value, mark])
        self._grid("feeder_load_ledger.csv",
                   ["interval", "feeder_id", "capacity_w", "reserve_w",
                    "reserved_capacity_w", "load_w", "headroom_w",
                    "load_state"], ledger, ",")

        self._grid("feeder_violation_ledger.csv",
                   ["interval", "feeder_id", "provisional_load_w",
                    "reserved_capacity_w", "excess_w", "removed_count"],
                   d.violation_rows, ",")

        self._grid("spill_decisions.tsv",
                   ["reefer_id", "from_interval", "to_interval", "feeder_id",
                    "draw_w", "spill_state"], d.spill_rows, "\t")

        self._grid("crane_adjusted_capacity.csv",
                   ["interval", "feeder_id", "reserved_capacity_w",
                    "crane_draw_w", "adjusted_capacity_w", "clamp_state"],
                   d.adjusted_rows, ",")

        self._grid("battery_schedule.csv",
                   ["interval", "action", "deficit_wh", "discharge_wh",
                    "charge_wh", "limit_reason"], d.battery_rows, ",")

        self._grid("soc_ledger.psv",
                   ["interval", "opening_soc_wh", "closing_soc_wh",
                    "reserve_wh", "soc_state"], d.charge_rows, "|")

        self._grid("reconciliation_iterations.csv",
                   ["pass", "feeder_id", "reefer_id", "opening_share_wh",
                    "need_wh", "target_wh", "closing_share_wh", "pass_state"],
                   d.pass_rows, ",")

        self._grid("tariff_charge_ledger.csv",
                   ["interval", "tariff_band", "price_tenth_cents_per_kwh",
                    "load_w", "energy_wh", "charge_cents"], d.tariff_rows, ",")

        self._object("peak_demand_certificate.json", {
            "day_id": d.day, "yard_peak_w": d.yard_peak,
            "yard_peak_interval": d.yard_peak_at,
            "substations": d.station_peaks,
            "demand_charge_cents": d.demand_cents})

        self._grid("deadline_correction.csv",
                   ["reefer_id", "interval", "displaced_reefer_id",
                    "feeder_id", "correction_state"], d.correction_rows, ",")

        self._object("cycle_break_report.json", d.cycle_report)
        self._object("objective_vector.json", d.objective)
        self._object("constraint_certificate.json", d.constraints)

        plan = []
        for n in range(1, SLOTS + 1):
            for r in d.present.get(n, []):
                name = r["reefer_id"]
                base = d.draw[(name, n)] if d.on_final.get((name, n)) else 0
                extra = d.placed.get((name, n), 0)
                if base and extra:
                    mark = "powered_with_allowance"
                elif base:
                    mark = "powered"
                elif extra:
                    mark = "allowance_only"
                else:
                    mark = "held"
                plan.append([n, r["feeder_id"], name, base, extra,
                             half_up(Fraction(base, 4)) + extra, mark])
        plan.sort(key=lambda row: (row[0], row[1], row[2]))
        self._grid("final_schedule.csv",
                   ["interval", "feeder_id", "reefer_id", "base_draw_w",
                    "allowance_wh", "energy_wh", "schedule_state"], plan, ",")

        by_feeder = []
        for n in range(1, SLOTS + 1):
            for f in d.feeders:
                top = d.adjusted[(f, n)]
                lift = d.support[(f, n)]
                value = d.load_final[(f, n)]
                mark = ("over_capacity" if value > top + lift else
                        ("at_capacity" if value == top + lift else "clear"))
                by_feeder.append([f, n, value, top, lift, mark])
        self._grid("final_schedule_by_feeder.psv",
                   ["feeder_id", "interval", "load_w", "adjusted_capacity_w",
                    "battery_support_w", "feeder_state"], by_feeder, "|")

        fleets = {}
        for r in d.queue:
            fleets.setdefault(r["vessel_id"], []).append(r)
        lines = ['<?xml version="1.0" encoding="utf-8"?>',
                 '<dispatch day="%s" reference="%s">'
                 % (self._guard(d.day), self._guard(d.reference))]
        for vessel in sorted(fleets):
            crew = sorted(fleets[vessel], key=lambda r: r["reefer_id"])
            call = d.call_of.get((vessel,))
            cutoff = whole(call["cutoff_interval"]) if call else SLOTS
            lines.append('  <vessel id="%s" cutoff="%d" members="%d">'
                         % (self._guard(vessel), cutoff, len(crew)))
            for r in crew:
                need, got, gap, _ = d.book[r["reefer_id"]]
                lines.append('    <reefer id="%s" required_wh="%d" '
                             'served_wh="%d" shortfall_wh="%d" '
                             'allowance_wh="%d"/>'
                             % (self._guard(r["reefer_id"]), need, got, gap,
                                d.share.get(r["reefer_id"], 0)))
            lines.append("  </vessel>")
        lines.append("</dispatch>")
        self._put("final_schedule_by_vessel.xml", "\n".join(lines) + "\n")

        for station in d.rostered:
            entry = None
            for item in d.station_peaks:
                if item["substation_id"] == station:
                    entry = item
            owned = [f for f in d.feeders
                     if d.feeder_of.get((f,), {}).get("substation_id") == station]
            served = 0
            for f in owned:
                for n in range(1, SLOTS + 1):
                    served += half_up(Fraction(d.load_final[(f, n)], 4))
            self._object("substation_report_%s.json" % station, {
                "day_id": d.day, "substation_id": station,
                "feeder_count": len(owned), "feeders": owned,
                "ceiling_w": d.controls.substation_ceiling.get(station, 0),
                "peak_w": entry["peak_w"] if entry else 0,
                "peak_interval": entry["peak_interval"] if entry else 0,
                "band_code": entry["band_code"] if entry else "",
                "demand_charge_cents": entry["charge_cents"] if entry else 0,
                "served_energy_wh": served})

        unmet = [[row[0], row[1], row[2], row[5], row[6], row[8], row[9]]
                 for row in d.certificate_rows
                 if row[10] == "unmet" or row[8] > 0]
        self._grid("unmet_requirement_report.tsv",
                   ["reefer_id", "feeder_id", "vessel_id", "shortfall_wh",
                    "shortfall_intervals", "unplaced_allowance_wh",
                    "surcharge_cents"], unmet, "\t")

        self._grid("reefer_service_certificate.csv",
                   ["reefer_id", "feeder_id", "vessel_id", "required_wh",
                    "served_wh", "shortfall_wh", "shortfall_intervals",
                    "allowance_wh", "unplaced_allowance_wh", "surcharge_cents",
                    "service_state"], d.certificate_rows, ",")

        self._stream("audit_trace.jsonl", [
            {"stage": code, "note": note, "measure": measure}
            for code, note, measure in [
                ("p01", "unit normalisation", len(d.reefers)),
                ("p02", "availability lattice", len(d.lattice_rows)),
                ("p03", "mandatory energy floor", len(d.floor_rows)),
                ("p04", "dispatch priority queue", len(d.queue_rows)),
                ("p05", "provisional allocation", len(d.provisional_rows)),
                ("p06", "feeder reconciliation", len(d.violation_rows)),
                ("p07", "crane adjusted capacity", len(d.adjusted_rows)),
                ("p08", "battery intervention", d.cycled),
                ("p09", "load reconciliation passes", len(d.pass_rows)),
                ("p10", "tariff and demand charge", d.energy_cents),
                ("p11", "deadline correction", len(d.correction_rows)),
                ("p12", "cycle detection and break",
                 d.cycle_report["sweeps_run"]),
                ("p13", "objective reconciliation",
                 d.objective["unmet_mandatory_wh"]),
                ("p14", "publication", len(EVERY)),
            ]])

        o = d.objective
        needed = max(1, sum(v[0] for v in d.book.values()))
        self._put("dispatch_control_totals.conf", "\n".join([
            "# control totals for %s" % d.day,
            "day_id = %s" % d.day,
            "day_reference = %s" % d.reference,
            "live_sheet = %s" % d.controls.sheet_name,
            "reefers_normalised = %d" % len(d.reefers),
            "reefers_queued = %d" % len(d.queue),
            "reefers_refused = %d" % d.constraints["reefers_refused"],
            "spill_count = %d" % len(d.spill_rows),
            "hard_violations = %d" % o["hard_violations"],
            "unmet_mandatory_wh = %d" % o["unmet_mandatory_wh"],
            "deadline_penalty_cents = %d" % o["deadline_penalty_cents"],
            "peak_demand_w = %d" % o["peak_demand_w"],
            "energy_cost_cents = %d" % o["energy_cost_cents"],
            "battery_cycle_wh = %d" % o["battery_cycle_wh"],
            "unmet_share_of_mandatory = %s"
            % nine_places(o["unmet_mandatory_wh"], needed),
        ]) + "\n")

        self._put("daily_dispatch_summary.md", "\n".join([
            "# Ashgrove Point reefer yard dispatch summary",
            "",
            "Operating day %s was recomputed from the working papers under the "
            "input directory. The governing workbook sheet was %s."
            % (d.day, d.controls.sheet_name),
            "",
            "## Admission",
            "",
            "%d reefers were normalised and %d of them reached the dispatch "
            "priority queue. %d were set aside by the admission ladder."
            % (len(d.reefers), len(d.queue),
               d.constraints["reefers_refused"]),
            "",
            "## Reconciliation",
            "",
            "The feeder reconciliation removed %d placements and spilled %d of "
            "them into a later interval. The reconciliation ran %d passes "
            "against the pass budget."
            % (len(d.spill_rows),
               len([row for row in d.spill_rows if row[5] == "spilled"]),
               d.controls.budget),
            "",
            "## Objective",
            "",
            "hard violations %d, unmet mandatory energy %d watt hours, "
            "deadline penalty %d cents, peak demand %d watts, energy cost %d "
            "cents, battery cycle %d watt hours."
            % (o["hard_violations"], o["unmet_mandatory_wh"],
               o["deadline_penalty_cents"], o["peak_demand_w"],
               o["energy_cost_cents"], o["battery_cycle_wh"]),
            "",
        ]) + "\n")

        sequence = self._sequence()
        listed = []
        for name in sequence:
            if name == "publication_manifest.json":
                continue
            blob = (self.out / name).read_bytes()
            listed.append({"name": name, "bytes": len(blob),
                           "sha256": hashlib.sha256(blob).hexdigest()})
        core = hashlib.sha256()
        for name in CORE:
            core.update((self.out / name).read_bytes())
        rest = hashlib.sha256()
        for name in sequence:
            if name in CORE or name == "publication_manifest.json":
                continue
            rest.update((self.out / name).read_bytes())
        self._object("publication_manifest.json", {
            "day_id": d.day, "day_reference": d.reference,
            "document_count": len(listed),
            "core_digest": core.hexdigest(),
            "publication_digest": rest.hexdigest(),
            "documents": listed})


def main(argv):
    source = "/app" + "/data"
    target = "/app" + "/out"
    i = 0
    while i < len(argv):
        if argv[i] == "--data" and i + 1 < len(argv):
            source, i = argv[i + 1], i + 2
        elif argv[i] == "--out" and i + 1 < len(argv):
            target, i = argv[i + 1], i + 2
        else:
            i += 1
    Day(Papers(source)).work().stage_p14_publication(target)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
