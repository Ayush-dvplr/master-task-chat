#!/usr/bin/env python3
"""Playout as-run reconciliation and make-good settlement.

Usage:
    python3 optimize.py DATA_DIR WORKLOAD        print the scenario object for one workload
    python3 optimize.py --rollup DATA_DIR NAME   print one roll-up (perf_report, bottleneck_analysis,
                                                 recommendations or data_quality) for DATA_DIR

The program reads only DATA_DIR and prints to standard output; it never writes a file.
"""

from __future__ import annotations

import bisect
import configparser
import csv
import datetime as dt
import json
import re
import sys
from pathlib import Path

TICKS_PER_SECOND = 30000
DAY_TICKS = 86400 * TICKS_PER_SECOND
EPOCH = dt.date(1970, 1, 1)
WEEKDAY_CODES = ("MO", "TU", "WE", "TH", "FR", "SA", "SU")
DISPOSITIONS = ("AIRED", "OUT_OF_WINDOW", "WRONG_COPY", "PARTIAL", "PREEMPTED", "MISSED", "UNRESOLVED")
REASONS = ("BAD_TIMECODE", "DROPPED_LABEL", "MISSING_FIELD")
OCCUPYING = {"AIRED", "OUT_OF_WINDOW", "WRONG_COPY", "UNRESOLVED"}
CHAIN_SOURCES = ("A", "B")
NOTHING_ON_AIR = "NONE"
REQUIRED_ASRUN_FIELDS = ("seq", "date", "tc", "evt", "spot", "house", "frames", "status")
# output_contract.md fixes the roll-up workloads and their order.
CONTRACT_WORKLOADS = ("visible", "peak", "steady", "burst", "latency")
ROLLUP_NAMES = ("perf_report", "bottleneck_analysis", "recommendations", "data_quality")
SUPPORTED_COMMISSION_ROUNDING = "half_up_per_order_line"
TC_RE = re.compile(r"^(\d\d):(\d\d):(\d\d)([:;])(\d\d)$")
HOUSE_RE = re.compile(r"^([A-Z]{3})(\d{1,5})$")


def day_number(text: str) -> int:
    return (dt.date.fromisoformat(text) - EPOCH).days


def day_text(day: int) -> str:
    return (EPOCH + dt.timedelta(days=day)).isoformat()


def utc_seconds(text: str) -> int:
    stamp = dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
    return int((stamp - dt.datetime(1970, 1, 1)).total_seconds())


def utc_ticks_ms(text: str) -> int:
    stamp = dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ")
    delta = stamp - dt.datetime(1970, 1, 1)
    millis = (delta.days * 86400 + delta.seconds) * 1000 + delta.microseconds // 1000
    return millis * (TICKS_PER_SECOND // 1000)


class Timebase:
    """Frame arithmetic for one channel (timecode_and_clock.md)."""

    def __init__(self, rate: str, mode: str):
        self.drop = mode == "drop"
        self.nominal = 30 if rate == "30000/1001" else 25
        self.frame_ticks = 1001 if rate == "30000/1001" else 1200

    def frames(self, hours: int, minutes: int, seconds: int, frame: int) -> int:
        if self.drop:
            total_minutes = 60 * hours + minutes
            return (3600 * hours + 60 * minutes + seconds) * 30 + frame - 2 * (total_minutes - total_minutes // 10)
        return (3600 * hours + 60 * minutes + seconds) * self.nominal + frame

    def parse(self, label: str):
        """Return (clock count, None) for a valid label, or (None, reason code)."""
        match = TC_RE.match(label)
        if not match:
            return None, "BAD_TIMECODE"
        hours, minutes, seconds = int(match.group(1)), int(match.group(2)), int(match.group(3))
        separator, frame = match.group(4), int(match.group(5))
        if (separator == ";") != self.drop or hours > 23 or minutes > 59 or seconds > 59 or frame >= self.nominal:
            return None, "BAD_TIMECODE"
        if self.drop and seconds == 0 and frame < 2 and minutes % 10 != 0:
            return None, "DROPPED_LABEL"
        return self.frames(hours, minutes, seconds, frame), None

    def clock(self, text: str) -> int:
        """Clock count of an HH:MM or HH:MM:SS bound; hours may run past 23."""
        fields = [int(part) for part in text.split(":")]
        while len(fields) < 3:
            fields.append(0)
        return self.frames(fields[0], fields[1], fields[2], 0)


class Zone:
    """UTC offset transitions of one zone (utc_offsets.json)."""

    def __init__(self, transitions):
        self.change_ticks = [utc_seconds(transition["from_utc"]) * TICKS_PER_SECOND for transition in transitions]
        self.offsets = [int(transition["offset_minutes"]) for transition in transitions]

    def offset_at(self, utc_ticks: int) -> int:
        position = bisect.bisect_right(self.change_ticks, utc_ticks) - 1
        return self.offsets[max(position, 0)]

    def to_utc(self, local_ticks: int) -> int:
        """The UTC instant whose offset in force maps it onto local_ticks."""
        for offset in sorted(set(self.offsets)):
            utc_ticks = local_ticks - offset * 60 * TICKS_PER_SECOND
            if self.offset_at(utc_ticks) == offset:
                return utc_ticks
        raise ValueError("no UTC offset of the zone fits local instant %d" % local_ticks)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_csv(path: Path, delimiter=","):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle, delimiter=delimiter))


def read_jsonl(path: Path):
    return [json.loads(line) for line in read_text(path).splitlines() if line.strip()]


def normalise_house(raw: str):
    """Canonical LLL-NNNNN form of a house id, or None when it does not normalise."""
    text = raw.strip().upper().replace(" ", "").replace("-", "")
    match = HOUSE_RE.match(text)
    if not match:
        return None
    return "%s-%05d" % (match.group(1), int(match.group(2)))


# ---------------------------------------------------------------------------
# readings of the three points the rules leave to the prior close
# ---------------------------------------------------------------------------
STRADDLE_READINGS = tuple((outcome, inclusive) for outcome in ("aired", "partial") for inclusive in (True, False))
WINDOW_READINGS = ("whole_spot", "start_only", "end_only")
TIE_READINGS = ("traffic_first", "mcr_first", "latest_recorded", "earliest_recorded")


def straddle_airs(reading, partner_complete: bool, sync_offset: int, tolerance: int) -> bool:
    """Whether a span that puts the other chain on air goes on past step 4 under one reading."""
    outcome, inclusive = reading
    within = sync_offset <= tolerance if inclusive else sync_offset < tolerance
    return outcome == "aired" and partner_complete and within


def window_contains(reading, spot_start: int, spot_end: int, window_start: int, window_end: int) -> bool:
    """Window membership of a spot covering [spot_start, spot_end) under one reading."""
    if reading == "whole_spot":
        return window_start <= spot_start and spot_end <= window_end
    if reading == "start_only":
        return window_start <= spot_start < window_end
    return window_start < spot_end <= window_end


def tie_rank(reading, desk: str, recorded_at: str):
    """Rank among corrections sharing the highest rev; the highest rank governs."""
    desk_rank = {"traffic_first": desk == "traffic", "mcr_first": desk == "mcr"}.get(reading, False)
    recorded_rank = -utc_seconds(recorded_at) if reading == "earliest_recorded" else utc_seconds(recorded_at)
    return int(desk_rank), recorded_rank


def label_frames(timebase: Timebase, label: str) -> int:
    """Clock count of a prior close label, which may use ':' or ';' before the frames."""
    hours, minutes, rest = label.split(":", 2)
    seconds, frame = re.split("[:;]", rest)
    return timebase.frames(int(hours), int(minutes), int(seconds), int(frame))


def settle_readings(records):
    """Keep, for each point, the one reading that reproduces every prior close record."""
    timebases = {"30000/1001": Timebase("30000/1001", "drop"), "25": Timebase("25", "nondrop")}
    straddle = dict.fromkeys(STRADDLE_READINGS, True)
    window = dict.fromkeys(WINDOW_READINGS, True)
    tie = dict.fromkeys(TIE_READINGS, True)
    for record in records:
        kind = record.get("kind")
        if kind == "failover_straddle":
            timebase = timebases[record["rate"]]
            sync_offset = abs(label_frames(timebase, record["other_start_tc"]) - label_frames(timebase, record["on_air_start_tc"]))
            tolerance = int(record["tolerance_frames"])
            for reading in straddle:
                aired = straddle_airs(reading, record["other_complete"], sync_offset, tolerance)
                if ("aired" if aired else "partial") != record["outcome"]:
                    straddle[reading] = False
        elif kind == "window_edge":
            timebase = timebases[record["rate"]]
            spot_start = label_frames(timebase, record["start_tc"])
            if record["after_local_midnight"]:
                spot_start += timebase.frames(24, 0, 0, 0)
            spot_end = spot_start + int(record["frames"])
            first_bound, last_bound = record["window"].split("-")
            window_start, window_end = timebase.clock(first_bound), timebase.clock(last_bound)
            for reading in window:
                inside = window_contains(reading, spot_start, spot_end, window_start, window_end)
                if ("in_window" if inside else "out_of_window") != record["outcome"]:
                    window[reading] = False
        elif kind == "correction_tie":
            top_rev = max(version["rev"] for version in record["versions"])
            tied = [version for version in record["versions"] if version["rev"] == top_rev]
            for reading in tie:
                governing = max(tied, key=lambda version: tie_rank(reading, version["desk"], version["recorded_at"]))
                if governing["order_line"] != record["outcome_order_line"]:
                    tie[reading] = False
    chosen = {}
    for point, table in (("straddle", straddle), ("window", window), ("tie", tie)):
        surviving = [reading for reading, holds in table.items() if holds]
        if len(surviving) != 1:
            raise ValueError("prior close records do not settle the %s point: %r" % (point, surviving))
        chosen[point] = surviving[0]
    return chosen


# ---------------------------------------------------------------------------
# reconciliation of one workload
# ---------------------------------------------------------------------------
class Workload:
    def __init__(self, data_dir: Path, name: str):
        self.dir = Path(data_dir)
        self.name = name
        channels = configparser.ConfigParser()
        channels.read_string(read_text(self.dir / "channels.ini"))
        if name not in channels:
            raise ValueError("workload %s is not a section of channels.ini" % name)
        section = channels[name]
        self.channel = section["channel"]
        self.timebase = Timebase(section["frame_rate"].strip(), section["timecode"].strip())
        zones = json.loads(read_text(self.dir / "utc_offsets.json"))["zones"]
        self.zone = Zone(zones[section["zone"].strip()])
        first_day = day_number(section["week_start"].strip())
        self.dates = [first_day + offset for offset in range(int(section["broadcast_days"]))]
        self.day_start = self.timebase.clock(section["broadcast_day_start"].strip())
        self.day_frames = self.timebase.frames(24, 0, 0, 0)
        self.tolerance = int(section["sync_tolerance_frames"])
        daypart_sets = json.loads(read_text(self.dir / "dayparts.json"))["sets"]
        self.dayparts = [(part["daypart"], self.timebase.clock(part["start"]), self.timebase.clock(part["end"]))
                         for part in daypart_sets[section["daypart_set"].strip()]]
        self.daypart_window = {daypart: (start, end) for daypart, start, end in self.dayparts}
        blackouts = json.loads(read_text(self.dir / "holidays.json"))["blackout_broadcast_dates"]
        self.blackout = {day_number(date) for date in blackouts.get(self.channel, [])}
        policy = json.loads(read_text(self.dir / "close_policy.json"))
        if policy["commission_rounding"] != SUPPORTED_COMMISSION_ROUNDING:
            raise ValueError("unsupported commission_rounding %r" % policy["commission_rounding"])
        self.cutoff = policy["cutoff_utc"][name]
        self.grace_days = int(policy["makegood_grace_days"])
        self.readings = settle_readings(read_jsonl(self.dir / "prior_close_decisions.jsonl"))
        advertisers = json.loads(read_text(self.dir / "advertisers.json"))["advertisers"]
        self.commission_bps = {advertiser: int(terms["commission_bps"]) for advertiser, terms in advertisers.items()}
        self._load_copies()
        self._load_orders()

    # -- reference data --------------------------------------------------
    def _load_copies(self):
        self.registry = {}
        for row in read_csv(self.dir / "copy_registry.csv"):
            self.registry[normalise_house(row["house_id"])] = (int(row["master_rate"]), int(row["frames"]))
        self.aliases = {}
        for row in read_csv(self.dir / "house_aliases.csv"):
            self.aliases.setdefault(normalise_house(row["old_house_id"]), []).append(
                (day_number(row["effective_from"]), normalise_house(row["new_house_id"])))

    def resolve(self, raw: str, on_day: int):
        """Return (canonical registered id or None, alias links followed) as of on_day."""
        current = normalise_house(raw)
        links = 0
        visited = set()
        while current is not None and current not in visited:
            visited.add(current)
            successors = [new_id for effective_from, new_id in self.aliases.get(current, []) if effective_from <= on_day]
            if not successors:
                break
            current = successors[-1]
            links += 1
        if current is None or current not in self.registry:
            return None, links
        return current, links

    def expected_frames(self, house: str) -> int:
        master_rate, master_frames = self.registry[house]
        return -(-master_frames * self.timebase.nominal // master_rate)

    def _load_orders(self):
        self.orders = {}
        for row in read_csv(self.dir / "orders.csv"):
            if row["workload"] != self.name:
                continue
            self.orders[row["order_line"]] = {
                "advertiser": row["advertiser"], "daypart": row["daypart"], "weekdays": set(row["weekdays"].split()),
                "spots_per_day": int(row["spots_per_day"]), "flight_start": day_number(row["flight_start"]),
                "flight_end": day_number(row["flight_end"]), "unit_rate": int(row["unit_rate_cents"]),
                "priority": int(row["priority"]), "house_id": row["house_id"]}
        self.amendments_admitted = 0
        self.amendments_late = 0
        self.amendments = {}
        for amendment in read_jsonl(self.dir / "order_amendments.jsonl"):
            if amendment["order_line"] not in self.orders:
                continue
            if amendment["recorded_at"] >= self.cutoff:
                self.amendments_late += 1
                continue
            self.amendments_admitted += 1
            self.amendments.setdefault(amendment["order_line"], []).append(
                (day_number(amendment["effective_from"]), amendment["recorded_at"], int(amendment["spots_per_day"])))

    def committed(self, line: str, day: int) -> int:
        order = self.orders[line]
        if not (order["flight_start"] <= day < order["flight_end"]) or day in self.blackout:
            return 0
        if WEEKDAY_CODES[(EPOCH + dt.timedelta(days=day)).weekday()] not in order["weekdays"]:
            return 0
        in_force = [amendment for amendment in self.amendments.get(line, []) if amendment[0] <= day]
        if not in_force:
            return order["spots_per_day"]
        # greatest effective_from governs, then the later recorded_at, then the larger spots_per_day
        return max(in_force)[2]

    # -- time helpers ------------------------------------------------------
    def broadcast(self, index: int):
        """(broadcast date, broadcast clock count) of an absolute frame index."""
        day, clock_count = divmod(index, self.day_frames)
        if clock_count < self.day_start:
            return day - 1, clock_count + self.day_frames
        return day, clock_count

    def utc_of(self, day: int, clock_count: int) -> int:
        return self.zone.to_utc(day * DAY_TICKS + clock_count * self.timebase.frame_ticks)

    # -- logs ----------------------------------------------------------------
    def _load_probes(self):
        """Chain B offsets in UTC order: OK sets the offset, RELOCK zeroes it, STALE governs nothing."""
        self.relock_probes = 0
        self.stale_probes = 0
        probes = []
        for line in read_text(self.dir / ("%s_sync_probes.log" % self.name)).splitlines():
            parts = line.split()
            if not parts:
                continue
            fields = dict(part.split("=", 1) for part in parts[2:] if "=" in part)
            if fields.get("chain") != "B":
                continue
            lock = fields.get("lock")
            if lock == "STALE":
                self.stale_probes += 1
                continue
            if lock == "RELOCK":
                self.relock_probes += 1
                offset = 0
            else:
                offset = int(fields["offset_frames"])
            probes.append((utc_ticks_ms(parts[0]), offset))
        probes.sort(key=lambda probe: probe[0])
        self.probe_times = [probe_time for probe_time, _ in probes]
        self.probe_offsets = [offset for _, offset in probes]

    def b_offset(self, utc_ticks: int) -> int:
        position = bisect.bisect_right(self.probe_times, utc_ticks) - 1
        return self.probe_offsets[position] if position >= 0 else 0

    def _load_switcher(self):
        """PGM takes in UTC order; PST lines never put anything on air."""
        takes = []
        for line_number, line in enumerate(read_text(self.dir / ("%s_switcher.log" % self.name)).splitlines()):
            parts = line.split()
            if not parts:
                continue
            fields = dict(part.split("=", 1) for part in parts[1:] if "=" in part)
            if fields.get("BUS") != "PGM":
                continue
            takes.append((utc_ticks_ms(parts[0]), line_number, fields["SRC"]))
        takes.sort()
        self.take_times = [take_time for take_time, _, _ in takes]
        self.take_sources = [source for _, _, source in takes]

    def source_at(self, utc_ticks: int) -> str:
        position = bisect.bisect_right(self.take_times, utc_ticks) - 1
        return self.take_sources[position] if position >= 0 else NOTHING_ON_AIR

    def sources_over(self, start: int, end: int):
        """Every source on air at some instant of [start, end)."""
        position = max(bisect.bisect_right(self.take_times, start) - 1, 0)
        sources = []
        while position < len(self.take_times) and self.take_times[position] < end:
            if position + 1 >= len(self.take_times) or self.take_times[position + 1] > start:
                sources.append(self.take_sources[position])
            position += 1
        return sources

    def _load_corrections(self):
        self.retracted_events = set()
        self.corrections_admitted = 0
        self.corrections_late = 0
        governing = {}
        tie_reading = self.readings["tie"]
        for correction in read_jsonl(self.dir / ("%s_corrections.jsonl" % self.name)):
            if correction["recorded_at"] >= self.cutoff:
                self.corrections_late += 1
                continue
            self.corrections_admitted += 1
            if correction["kind"] == "retract":
                self.retracted_events.add(correction["target"])
                continue
            if int(correction["rev"]) < 1:
                continue
            rank = (int(correction["rev"]),) + tie_rank(tie_reading, correction["desk"], correction["recorded_at"]) + (correction["correction_id"],)
            current = governing.get(correction["target"])
            if current is None or rank > current[0]:
                governing[correction["target"]] = (rank, correction)
        self.attribution = {}
        for target, (_, correction) in governing.items():
            self.attribution[target] = correction["payload"].get("order_line") if correction["kind"] == "reattribute" else None

    def _governing_plays(self, chain: str):
        """Governing play per spot on one chain; counts duplicates, retracted lines, rejects and re-airs."""
        text = read_text(self.dir / ("%s_asrun_%s.log" % (self.name, chain.lower())))
        lines = [line for line in text.splitlines() if line.strip()]
        self.asrun_lines[chain] = len(lines)
        distinct = list(dict.fromkeys(lines))
        self.duplicate_lines += len(lines) - len(distinct)
        plays = {}
        for line in distinct:
            fields = {}
            for part in line.split("|"):
                if "=" in part:
                    key, value = part.split("=", 1)
                    fields[key] = value
            if fields.get("type") != "SPOT":
                continue
            if "%s:%s" % (chain, fields.get("evt", "")) in self.retracted_events:
                self.retracted_lines += 1
                continue
            if any(not fields.get(key, "").strip() for key in REQUIRED_ASRUN_FIELDS):
                self.rejects.append((chain, fields.get("seq", ""), "MISSING_FIELD"))
                continue
            clock_count, reason = self.timebase.parse(fields["tc"])
            if reason:
                self.rejects.append((chain, fields["seq"], reason))
                continue
            if fields["status"] != "PLAYED":
                continue
            day = day_number(fields["date"])
            index = day * self.day_frames + clock_count
            utc_ticks = self.utc_of(day, clock_count)
            if chain == "B":
                skew = self.b_offset(utc_ticks)
                utc_ticks -= skew * self.timebase.frame_ticks
                index -= skew
            plays.setdefault(fields["spot"], []).append(
                {"chain": chain, "utc": utc_ticks, "index": index, "frames": int(fields["frames"]),
                 "house": fields["house"], "seq": fields["seq"]})
        governing = {}
        for spot_id, spot_plays in plays.items():
            spot_plays.sort(key=lambda play: (play["utc"], play["seq"]))
            governing[spot_id] = spot_plays[0]
            self.reairs += len(spot_plays) - 1
        return governing

    # -- main pass -------------------------------------------------------------
    def run(self):
        self.asrun_lines = {}
        self.duplicate_lines = 0
        self.rejects = []
        self.reairs = 0
        self.retracted_lines = 0
        self._load_probes()
        self._load_switcher()
        self._load_corrections()
        plays_a = self._governing_plays("A")
        plays_b = self._governing_plays("B")
        self.spots = []
        self.alias_spots = 0
        self.reattributed_spots = 0
        for row in read_csv(self.dir / ("%s_schedule.csv" % self.name)):
            self.spots.append(self._dispose(row, plays_a.get(row["spot_id"]), plays_b.get(row["spot_id"])))
        self._settle()
        return self

    def _dispose(self, row, play_a, play_b):
        """Disposition of one scheduled spot through the seven steps of reconciliation_rules.md."""
        scheduled_day = day_number(row["broadcast_date"])
        reattributed_to = self.attribution.get(row["spot_id"])
        line = reattributed_to if reattributed_to is not None else row["order_line"]
        if line != row["order_line"]:
            self.reattributed_spots += 1
        scheduled_house, schedule_links = self.resolve(row["house_id"], scheduled_day)
        reference = None
        if play_a is not None and self.source_at(play_a["utc"]) == "A":
            reference = play_a
        elif play_b is not None and self.source_at(play_b["utc"]) == "B":
            reference = play_b
        reference_links = self.resolve(reference["house"], scheduled_day)[1] if reference is not None else 0
        if schedule_links or reference_links:
            self.alias_spots += 1
        chain = None
        broadcast_day = scheduled_day
        if scheduled_house is None:
            disposition = "UNRESOLVED"
            if reference is not None:
                chain = reference["chain"]
                broadcast_day = self.broadcast(reference["index"])[0]
        elif reference is None:
            disposition = "MISSED"
            for play in (play_a, play_b):
                if play is not None and self.source_at(play["utc"]) not in CHAIN_SOURCES + (NOTHING_ON_AIR,):
                    disposition = "PREEMPTED"
                    chain = play["chain"]
                    broadcast_day = self.broadcast(play["index"])[0]
                    break
        else:
            chain = reference["chain"]
            broadcast_day, clock_count = self.broadcast(reference["index"])
            expected = self.expected_frames(scheduled_house)
            span_end = reference["utc"] + expected * self.timebase.frame_ticks
            partner = play_b if reference["chain"] == "A" else play_a
            preempted = False
            partial = reference["frames"] < expected
            for source in self.sources_over(reference["utc"], span_end):
                if source not in CHAIN_SOURCES:
                    preempted = True
                elif source != reference["chain"]:
                    if partner is None or not straddle_airs(self.readings["straddle"], partner["frames"] >= expected,
                                                             abs(partner["index"] - reference["index"]), self.tolerance):
                        partial = True
            if preempted:
                disposition = "PREEMPTED"
            elif partial:
                disposition = "PARTIAL"
            else:
                aired_house = self.resolve(reference["house"], scheduled_day)[0]
                if aired_house is None:
                    disposition = "UNRESOLVED"
                elif aired_house != scheduled_house:
                    disposition = "WRONG_COPY"
                else:
                    window_start, window_end = self.daypart_window[self.orders[line]["daypart"]]
                    inside = window_contains(self.readings["window"], clock_count, clock_count + expected, window_start, window_end)
                    disposition = "AIRED" if inside else "OUT_OF_WINDOW"
        occupancy = reference["frames"] if (reference is not None and disposition in OCCUPYING) else 0
        return {"spot_id": row["spot_id"], "order_line": line, "broadcast_date": broadcast_day, "chain": chain,
                "disposition": disposition, "break_id": row["break_id"], "occupancy": occupancy}

    # -- settlement ----------------------------------------------------------
    def _settle(self):
        self._build_deliveries()
        self._load_breaks()
        self._allocate_makegoods()
        self._bill()

    def _build_deliveries(self):
        delivered, held = {}, {}
        for spot in self.spots:
            key = (spot["order_line"], spot["broadcast_date"])
            if spot["disposition"] == "AIRED":
                delivered[key] = delivered.get(key, 0) + 1
            elif spot["disposition"] == "UNRESOLVED":
                held[key] = held.get(key, 0) + 1
        self.deliveries = []
        for line in sorted(self.orders):
            for day in self.dates:
                committed = self.committed(line, day)
                delivered_spots = delivered.get((line, day), 0)
                held_spots = held.get((line, day), 0)
                if committed == 0 and delivered_spots == 0 and held_spots == 0:
                    continue
                effective = max(committed - held_spots, 0)
                billable = min(delivered_spots, effective)
                self.deliveries.append({"order_line": line, "broadcast_date": day, "committed": committed,
                                        "held": held_spots, "delivered": delivered_spots, "billable": billable,
                                        "shortfall": effective - billable, "bonus": delivered_spots - billable})

    def _load_breaks(self):
        self.breaks = []
        for row in read_csv(self.dir / ("%s_breaks.tsv" % self.name), delimiter="\t"):
            clock_count, reason = self.timebase.parse(row["open_tc"])
            if reason:
                raise ValueError("break %s opens on an invalid label %s (%s)" % (row["break_id"], row["open_tc"], reason))
            if row["local_date"] != row["broadcast_date"]:
                clock_count += self.day_frames
            daypart = self.dayparts[-1][0]
            for name, start, end in self.dayparts:
                if start <= clock_count < end:
                    daypart = name
                    break
            self.breaks.append({"break_id": row["break_id"], "broadcast_day": day_number(row["broadcast_date"]),
                                "clock_count": clock_count, "daypart": daypart,
                                "capacity": int(row["capacity_frames"]), "occupied": 0, "makegood_frames": 0})
        breaks_by_id = {brk["break_id"]: brk for brk in self.breaks}
        for spot in self.spots:
            if spot["occupancy"]:
                breaks_by_id[spot["break_id"]]["occupied"] += spot["occupancy"]
        for brk in self.breaks:
            brk["spare"] = max(brk["capacity"] - brk["occupied"], 0)

    def _allocate_makegoods(self):
        lanes = {}
        for brk in sorted(self.breaks, key=lambda brk: (brk["broadcast_day"], brk["clock_count"], brk["break_id"])):
            lanes.setdefault(brk["daypart"], []).append(brk)
        trees = {daypart: SpareTree(lane) for daypart, lane in lanes.items()}
        units = []
        for row in self.deliveries:
            order = self.orders[row["order_line"]]
            for unit in range(1, row["shortfall"] + 1):
                units.append((order["priority"], row["broadcast_date"], -order["unit_rate"], row["order_line"], unit))
        units.sort()
        last_day = self.dates[-1]
        self.makegoods = []
        for _, from_day, _, line, unit in units:
            order = self.orders[line]
            need = self.expected_frames(normalise_house(order["house_id"]))
            last_open_day = min(last_day, order["flight_end"] - 1 + self.grace_days)
            lane = lanes.get(order["daypart"], [])
            placed = None
            if lane and last_open_day > from_day:
                tree = trees[order["daypart"]]
                position = tree.find(tree.first_day(from_day + 1), tree.first_day(last_open_day + 1), need)
                if position is not None:
                    placed = lane[position]
                    tree.take(position, need)
                    placed["makegood_frames"] += need
            self.makegoods.append({"order_line": line, "from_date": from_day, "unit": unit,
                                   "status": "placed" if placed else "credited",
                                   "break_id": placed["break_id"] if placed else None,
                                   "broadcast_day": placed["broadcast_day"] if placed else None,
                                   "clock_count": placed["clock_count"] if placed else None,
                                   "daypart": order["daypart"], "unit_rate": order["unit_rate"]})
        for daypart, tree in trees.items():
            for position, brk in enumerate(lanes[daypart]):
                brk["spare"] = tree.value(position)

    def _bill(self):
        credits = {}
        for makegood in self.makegoods:
            if makegood["status"] == "credited":
                credits[makegood["order_line"]] = credits.get(makegood["order_line"], 0) + makegood["unit_rate"]
        billable_spots = {}
        for row in self.deliveries:
            billable_spots[row["order_line"]] = billable_spots.get(row["order_line"], 0) + row["billable"]
        self.billing = []
        for line in sorted(billable_spots):
            order = self.orders[line]
            gross = billable_spots[line] * order["unit_rate"]
            # commission rounds half up once per order line
            commission = (gross * self.commission_bps[order["advertiser"]] + 5000) // 10000
            credit = credits.get(line, 0)
            self.billing.append({"order_line": line, "advertiser": order["advertiser"], "gross_cents": gross,
                                 "commission_cents": commission, "credit_cents": credit,
                                 "net_cents": gross - commission - credit})

    # -- output ----------------------------------------------------------------
    def scenario(self):
        spots = [{"spot_id": spot["spot_id"], "order_line": spot["order_line"],
                  "broadcast_date": day_text(spot["broadcast_date"]), "chain": spot["chain"],
                  "disposition": spot["disposition"]}
                 for spot in sorted(self.spots, key=lambda spot: spot["spot_id"])]
        deliveries = [dict(row, broadcast_date=day_text(row["broadcast_date"])) for row in self.deliveries]
        makegoods = [{"order_line": makegood["order_line"], "from_date": day_text(makegood["from_date"]),
                      "unit": makegood["unit"], "status": makegood["status"], "break_id": makegood["break_id"],
                      "broadcast_date": day_text(makegood["broadcast_day"]) if makegood["broadcast_day"] is not None else None}
                     for makegood in sorted(self.makegoods, key=lambda makegood: (makegood["order_line"], makegood["from_date"], makegood["unit"]))]
        rejects = [{"chain": chain, "seq": seq, "reason": reason} for chain, seq, reason in sorted(set(self.rejects))]
        totals = {
            "scheduled_spots": len(self.spots),
            "aired": sum(1 for spot in self.spots if spot["disposition"] == "AIRED"),
            "committed": sum(row["committed"] for row in self.deliveries),
            "held": sum(row["held"] for row in self.deliveries),
            "delivered": sum(row["delivered"] for row in self.deliveries),
            "billable": sum(row["billable"] for row in self.deliveries),
            "shortfall": sum(row["shortfall"] for row in self.deliveries),
            "bonus": sum(row["bonus"] for row in self.deliveries),
            "placed_units": sum(1 for makegood in self.makegoods if makegood["status"] == "placed"),
            "credited_units": sum(1 for makegood in self.makegoods if makegood["status"] == "credited"),
            "gross_cents": sum(bill["gross_cents"] for bill in self.billing),
            "commission_cents": sum(bill["commission_cents"] for bill in self.billing),
            "credit_cents": sum(bill["credit_cents"] for bill in self.billing),
            "net_cents": sum(bill["net_cents"] for bill in self.billing),
        }
        return {"workload": self.name, "channel": self.channel, "spots": spots, "deliveries": deliveries,
                "makegoods": makegoods, "billing": self.billing, "rejects": rejects, "totals": totals}


class SpareTree:
    """Max segment tree over the spare frames of one daypart's breaks, in placement order."""

    def __init__(self, lane):
        self.days = [brk["broadcast_day"] for brk in lane]
        leaves = 1
        while leaves < max(len(lane), 1):
            leaves *= 2
        self.leaves = leaves
        self.best = [-1] * (2 * leaves)
        for position, brk in enumerate(lane):
            self.best[leaves + position] = brk["spare"]
        for node in range(leaves - 1, 0, -1):
            self.best[node] = max(self.best[2 * node], self.best[2 * node + 1])

    def first_day(self, day: int) -> int:
        """Position of the first break on or after day."""
        return bisect.bisect_left(self.days, day)

    def value(self, position: int) -> int:
        return self.best[self.leaves + position]

    def take(self, position: int, frames: int):
        node = position + self.leaves
        self.best[node] -= frames
        node //= 2
        while node:
            self.best[node] = max(self.best[2 * node], self.best[2 * node + 1])
            node //= 2

    def find(self, first: int, end: int, need: int):
        """Smallest position in [first, end) whose spare is at least need."""
        if first >= end:
            return None
        return self._find(1, 0, self.leaves, first, end, need)

    def _find(self, node, node_start, node_end, first, end, need):
        if node_end <= first or end <= node_start or self.best[node] < need:
            return None
        if node_end - node_start == 1:
            return node_start
        middle = (node_start + node_end) // 2
        left = self._find(2 * node, node_start, middle, first, end, need)
        if left is not None:
            return left
        return self._find(2 * node + 1, middle, node_end, first, end, need)


def reconcile(data_dir, workload):
    """The scenario object output_contract.md defines for one workload of data_dir."""
    return Workload(Path(data_dir), workload).run().scenario()


# ---------------------------------------------------------------------------
# roll-ups over the contract's workloads
# ---------------------------------------------------------------------------
SUM_FIELDS = ("committed", "held", "delivered", "billable", "shortfall", "bonus")
MONEY_FIELDS = ("gross_cents", "commission_cents", "credit_cents", "net_cents")


def delivery_bps(row) -> int:
    owed = row["billable"] + row["shortfall"]
    return row["billable"] * 10000 // owed if owed else 0


def perf_report(workloads):
    workload_rows, by_advertiser = [], {}
    totals = dict.fromkeys(SUM_FIELDS + MONEY_FIELDS, 0)
    for workload in workloads:
        row = {"workload": workload.name}
        for field in SUM_FIELDS:
            row[field] = sum(delivery[field] for delivery in workload.deliveries)
        for field in MONEY_FIELDS:
            row[field] = sum(bill[field] for bill in workload.billing)
        workload_rows.append(row)
        for delivery in workload.deliveries:
            advertiser = workload.orders[delivery["order_line"]]["advertiser"]
            account = by_advertiser.setdefault(advertiser, dict.fromkeys(SUM_FIELDS + MONEY_FIELDS, 0))
            for field in SUM_FIELDS:
                account[field] += delivery[field]
        for bill in workload.billing:
            account = by_advertiser[bill["advertiser"]]
            for field in MONEY_FIELDS:
                account[field] += bill[field]
        for field in totals:
            totals[field] += row[field]
    advertiser_rows = []
    for advertiser in sorted(by_advertiser):
        row = dict(advertiser=advertiser, **by_advertiser[advertiser])
        row["delivery_bps"] = delivery_bps(row)
        advertiser_rows.append(row)
    totals["delivery_bps"] = delivery_bps(totals)
    return {"workloads": workload_rows, "advertisers": advertiser_rows, "totals": totals}


def bottleneck_analysis(workloads):
    rows = []
    for workload in workloads:
        for daypart, _, _ in workload.dayparts:
            breaks = [brk for brk in workload.breaks if brk["daypart"] == daypart]
            rows.append({"workload": workload.name, "daypart": daypart, "breaks": len(breaks),
                         "capacity_frames": sum(brk["capacity"] for brk in breaks),
                         "occupied_frames": sum(brk["occupied"] for brk in breaks),
                         "overbooked_breaks": sum(1 for brk in breaks if brk["occupied"] > brk["capacity"]),
                         "makegood_frames": sum(brk["makegood_frames"] for brk in breaks),
                         "spare_frames_after": sum(brk["spare"] for brk in breaks),
                         "zero_spare_breaks": sum(1 for brk in breaks if brk["spare"] == 0),
                         "unplaced_units": sum(1 for makegood in workload.makegoods
                                               if makegood["status"] == "credited" and makegood["daypart"] == daypart)})
    _, worst = min(enumerate(rows), key=lambda item: (-item[1]["unplaced_units"], item[1]["spare_frames_after"], item[0]))
    return {"dayparts": rows, "worst": {"workload": worst["workload"], "daypart": worst["daypart"]}}


def recommendations(workloads):
    rows = []
    for workload in workloads:
        units_by_line = {}
        for makegood in workload.makegoods:
            units_by_line.setdefault(makegood["order_line"], []).append(makegood)
        for line in sorted(units_by_line):
            units = units_by_line[line]
            placed = sorted((unit for unit in units if unit["status"] == "placed"),
                            key=lambda unit: (unit["broadcast_day"], unit["clock_count"], unit["break_id"]))
            credited = [unit for unit in units if unit["status"] == "credited"]
            rows.append({"workload": workload.name, "order_line": line, "advertiser": workload.orders[line]["advertiser"],
                         "shortfall_units": len(units), "placed_units": len(placed), "credited_units": len(credited),
                         "credit_cents": sum(unit["unit_rate"] for unit in credited),
                         "first_break_id": placed[0]["break_id"] if placed else None,
                         "last_break_id": placed[-1]["break_id"] if placed else None})
    totals = {field: sum(row[field] for row in rows) for field in ("shortfall_units", "placed_units", "credited_units", "credit_cents")}
    return {"order_lines": rows, "totals": totals}


def data_quality(workloads, perf, bottleneck, recs):
    rows = []
    for workload in workloads:
        dispositions = dict.fromkeys(DISPOSITIONS, 0)
        for spot in workload.spots:
            dispositions[spot["disposition"]] += 1
        rejects = dict.fromkeys(REASONS, 0)
        for _, _, reason in set(workload.rejects):
            rejects[reason] += 1
        rows.append({"workload": workload.name, "asrun_lines": dict(workload.asrun_lines),
                     "duplicate_lines": workload.duplicate_lines, "rejects": rejects, "reairs": workload.reairs,
                     "retracted_lines": workload.retracted_lines,
                     "corrections": {"admitted": workload.corrections_admitted, "late": workload.corrections_late,
                                     "reattributed_spots": workload.reattributed_spots},
                     "amendments": {"admitted": workload.amendments_admitted, "late": workload.amendments_late},
                     "alias_spots": workload.alias_spots, "relock_probes": workload.relock_probes,
                     "stale_probes": workload.stale_probes, "dispositions": dispositions,
                     "partition_residual": len(workload.spots) - sum(dispositions.values())})
    scenario_totals = [workload.scenario()["totals"] for workload in workloads]
    identities = {
        "billing_net_vs_perf_report": sum(totals["net_cents"] for totals in scenario_totals) - perf["totals"]["net_cents"],
        "credits_vs_recommendations": sum(totals["credit_cents"] for totals in scenario_totals) - recs["totals"]["credit_cents"],
        "unplaced_vs_bottleneck": sum(totals["credited_units"] for totals in scenario_totals)
        - sum(row["unplaced_units"] for row in bottleneck["dayparts"]),
    }
    return {"workloads": rows, "identities": identities}


def rollups(data_dir):
    """The four roll-ups for data_dir, keyed by name."""
    workloads = [Workload(Path(data_dir), name).run() for name in CONTRACT_WORKLOADS]
    perf = perf_report(workloads)
    bottleneck = bottleneck_analysis(workloads)
    recs = recommendations(workloads)
    return {"perf_report": perf, "bottleneck_analysis": bottleneck, "recommendations": recs,
            "data_quality": data_quality(workloads, perf, bottleneck, recs)}


def main(argv):
    try:
        if len(argv) == 4 and argv[1] == "--rollup" and argv[3] in ROLLUP_NAMES:
            document = rollups(argv[2])[argv[3]]
        elif len(argv) == 3:
            document = reconcile(argv[1], argv[2])
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except (OSError, ValueError, KeyError) as error:
        print("optimize.py: cannot reconcile: %s: %s" % (type(error).__name__, error), file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
