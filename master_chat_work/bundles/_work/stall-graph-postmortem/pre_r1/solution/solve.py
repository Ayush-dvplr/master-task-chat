#!/usr/bin/env python3
"""derive_report - stall journal post mortem writer.

Called as::

    python3 derive_report.py [<data_dir> [<out_dir>]]

Both arguments fall back to /app/data and /app/out when omitted. Everything is
computed from the shipped rule documents; nothing is hardcoded from the shipped
window.
"""
from __future__ import annotations

import json
import pathlib
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

DEFAULT_DATA = pathlib.Path("/app/data")
DEFAULT_OUT = pathlib.Path("/app/out")

WIRE_INPUTS: tuple[str, ...] = (
    "stall_journal.psv",
    "thread_probe.csv",
    "park_reports.jsonl",
    "thread_registry.csv",
    "lock_ladder.csv",
    "pool_windows.csv",
    "host_cells.csv",
    "tenant_classes.csv",
)

CALIBRATION_INPUTS: tuple[str, ...] = (
    "calibration_stall_journal.psv",
    "calibration_thread_probe.csv",
    "calibration_park_reports.jsonl",
    "control-slice-figures.json",
)

SPIN_BYTES = 24
MAX_ALIAS_HOPS = 6
TOKEN_HEX_CHARS = 16
LRC_MOD = 0x10000
TOKEN_MOD = 1_000_000_007

BIT_ZIGZAG_WAIT = 1 << 0
BIT_MASKED_HOLD = 1 << 1
BIT_STRIDE_LAYOUT = 1 << 2
BIT_PADDED_COUNT = 1 << 3
BIT_LE_HEX_ORIGIN = 1 << 4
BIT_CHAINED_ORIGIN = 1 << 5
BIT_SENTINEL = 1 << 6
BIT_RING_OWNER = 1 << 7
BIT_COARSE_SPIN = 1 << 8
BIT_ROTATED_TOKEN = 1 << 9
BIT_ALIAS_WORKER = 1 << 10
BIT_DECOY_SLOT = 1 << 11

CANDIDATES: dict[str, tuple[int, ...]] = {
    "count_window": (2, 3, 4, 5, 6),
    "stride": (3, 5, 7, 9, 11, 13),
    "chain_width": (6, 7, 8, 9, 10, 11),
    "depth_width": (5, 6, 7, 8, 9, 10),
    "ring_width": (4, 6, 8, 12, 16),
    "coarse_unit": (32, 64, 128, 256, 512),
    "token_offset": tuple(range(8)),
    "hold_scale": (1, 2, 4, 5, 8, 10, 16),
    "epoch_span": tuple(1 << k for k in range(20, 32)),
}

STAGE_ORDER: tuple[tuple[str, str], ...] = (
    ("count_window", "CTRL-A"),
    ("stride", "CTRL-B"),
    ("chain_width", "CTRL-C"),
    ("depth_width", "CTRL-D"),
    ("ring_width", "CTRL-E"),
    ("coarse_unit", "CTRL-F"),
    ("token_offset", "CTRL-G"),
    ("hold_scale", "CTRL-H"),
    ("epoch_span", "CTRL-I"),
)

PRESET_CONSTANTS: dict[str, int] = {
    "count_window": 5,
    "stride": 7,
    "chain_width": 9,
    "depth_width": 8,
    "ring_width": 6,
    "coarse_unit": 128,
    "token_offset": 3,
    "hold_scale": 5,
    "epoch_span": 1 << 24,
}

PARAM_LABEL: dict[str, str] = {
    "count_window": "count bias window",
    "stride": "interleave stride",
    "chain_width": "chain mask width",
    "depth_width": "depth complement width",
    "ring_width": "owner ring width",
    "coarse_unit": "coarse spin unit",
    "token_offset": "token rotation offset",
    "hold_scale": "hold scale",
    "epoch_span": "epoch span",
}

CONTROLS: tuple[str, ...] = tuple(
    f"CTRL-{ch}" for ch in "ABCDEFGHIJK"
)

REGION_NAMES: tuple[str, ...] = ("East", "North", "South", "West")
SEGMENT_NAMES: tuple[str, ...] = ("commercial", "public")

REJECT_KINDS: tuple[str, ...] = (
    "outside_window",
    "retired_worker",
    "unprobed_slot",
    "unreported_park",
    "unresolved_worker",
)

OUTPUT_ORDER: tuple[str, ...] = (
    ("summary.json", "policy_audit.json", "data_quality.json")
    + tuple(f"region_{r}.json" for r in ("North", "South", "West", "East"))
    + tuple(f"segment_{s}.json" for s in SEGMENT_NAMES)
)


def wire_lrc(payload: str) -> str:
    total = 0
    for ch in payload:
        total += ord(ch)
    return format(total & (LRC_MOD - 1), "04x")


def spin_left(chars: str, shift: int) -> str:
    if not chars:
        return chars
    step = shift % len(chars)
    return chars[step:] + chars[:step]


def spin_right(chars: str, shift: int) -> str:
    if not chars:
        return chars
    step = shift % len(chars)
    if step == 0:
        return chars
    return chars[-step:] + chars[:-step]


def to_zigzag(number: int) -> int:
    if number < 0:
        return (number << 1) ^ (number >> 63)
    return number << 1


def from_zigzag(value: int) -> int:
    return (value >> 1) ^ -(value & 1)


def pair_swap(hex_text: str) -> str:
    padded = hex_text if len(hex_text) % 2 == 0 else "0" + hex_text
    pairs = [padded[k:k + 2] for k in range(0, len(padded), 2)]
    pairs.reverse()
    return "".join(pairs)


def stride_layout(count: int, step: int) -> list[int]:
    seats: list[bool] = [False] * count
    picked: list[int] = []
    at = 0
    left = count
    while left > 0:
        while seats[at]:
            at = (at + 1) % count
        picked.append(at)
        seats[at] = True
        left -= 1
        at = (at + step) % count
    return picked


@dataclass(frozen=True)
class Constants:
    count_window: int
    stride: int
    chain_width: int
    depth_width: int
    ring_width: int
    coarse_unit: int
    token_offset: int
    hold_scale: int
    epoch_span: int

    @classmethod
    def from_map(cls, table: Mapping[str, int]) -> "Constants":
        return cls(
            count_window=table["count_window"],
            stride=table["stride"],
            chain_width=table["chain_width"],
            depth_width=table["depth_width"],
            ring_width=table["ring_width"],
            coarse_unit=table["coarse_unit"],
            token_offset=table["token_offset"],
            hold_scale=table["hold_scale"],
            epoch_span=table["epoch_span"],
        )

    def as_map(self) -> dict[str, int]:
        return {
            "count_window": self.count_window,
            "stride": self.stride,
            "chain_width": self.chain_width,
            "depth_width": self.depth_width,
            "ring_width": self.ring_width,
            "coarse_unit": self.coarse_unit,
            "token_offset": self.token_offset,
            "hold_scale": self.hold_scale,
            "epoch_span": self.epoch_span,
        }


@dataclass
class DecodedEvent:
    slot: int
    wait_ns: int
    hold_ns: int
    spins: int
    depth: int
    blocked_class: str
    owner_tag: str
    symbol: str
    token: str
    tick: int


@dataclass
class Segment:
    segment_id: str
    worker_field: str
    origin: int
    sflags: int
    events: list[DecodedEvent]


def _group_journal(text: str) -> list[tuple[str, list[str]]]:
    groups: list[tuple[str, list[str]]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if line == "" or line.startswith("#"):
            continue
        if line.startswith("@|"):
            groups.append((line, []))
            continue
        if not groups:
            raise ValueError("event line before any segment header")
        groups[-1][1].append(line)
    return groups


def _decode_segment(
    header_line: str,
    body_lines: list[str],
    constants: Constants,
    ring: list[str],
    ring_position: int,
    previous_origin: int,
    verify: bool,
) -> tuple[Segment, list[str], int, int]:
    header = header_line.split("|")
    if len(header) != 8:
        raise ValueError("malformed segment header")
    segment_id = header[1]
    worker_field = header[2]
    count_field = header[3]
    origin_field = header[4]
    sflags = int(header[5], 16)
    segment_key = int(header[6])
    header_check = int(header[7], 16)

    if sflags & BIT_PADDED_COUNT:
        padding_bias = segment_key % constants.count_window
    else:
        padding_bias = 0

    real_count = int(count_field) - padding_bias
    if real_count < 1 or real_count > len(body_lines):
        raise ValueError("declared count outside the segment")

    if verify:
        checksum_accumulator = 0
        for body_line in body_lines:
            trailing_hex = body_line.rsplit("|", 1)[1]
            checksum_accumulator += int(trailing_hex, 16)
        if (checksum_accumulator & (LRC_MOD - 1)) != header_check:
            raise ValueError("segment check total mismatch")

    wire_rows = body_lines[:real_count]
    if sflags & BIT_STRIDE_LAYOUT:
        layout = stride_layout(real_count, constants.stride)
        wire_rows = [wire_rows[layout[k]] for k in range(real_count)]

    origin_text = pair_swap(origin_field) if sflags & BIT_LE_HEX_ORIGIN else origin_field
    origin_number = int(origin_text, 16)
    if sflags & BIT_CHAINED_ORIGIN:
        origin_number = previous_origin + origin_number

    parsed_rows: list[list[str]] = []
    for row_line in wire_rows:
        fields = row_line.split("|")
        if len(fields) != 10:
            raise ValueError("malformed event line")
        if verify:
            expected = wire_lrc("|".join(fields[:9]))
            if expected != fields[9]:
                raise ValueError("event check total mismatch")
        parsed_rows.append(fields)

    mask = (1 << constants.chain_width) - 1
    depth_mask = (1 << constants.depth_width) - 1

    events: list[DecodedEvent] = []
    prior_wait = 0
    prior_raw_symbol = ""
    running_hold = 0

    for fields in parsed_rows:
        raw_symbol = fields[7]
        if sflags & BIT_DECOY_SLOT:
            head, _sep, tail = raw_symbol.rpartition(":")
            authoritative_slot = int(tail)
            symbol_text = head
        else:
            authoritative_slot = int(fields[0])
            symbol_text = raw_symbol
        if sflags & BIT_SENTINEL and symbol_text.startswith("!"):
            symbol_text = symbol_text[1:]

        raw_wait = int(fields[1])
        if sflags & BIT_ZIGZAG_WAIT:
            wait_value = raw_wait if not events else prior_wait + from_zigzag(raw_wait)
        else:
            wait_value = raw_wait

        hold_value = int(fields[2])
        if sflags & BIT_MASKED_HOLD:
            hold_value ^= prior_wait & mask

        spins_text = fields[3]
        if spins_text.startswith("~"):
            spin_count = int(spins_text[1:]) * constants.coarse_unit
        else:
            spin_count = int(spins_text)

        depth_value = int(fields[4])
        if (sflags & BIT_SENTINEL) and prior_raw_symbol.startswith("!"):
            depth_value ^= depth_mask

        owner_field = fields[6]
        if owner_field.startswith("^"):
            back_index = int(owner_field[1:]) % constants.ring_width
            owner_value = ring[back_index]
        else:
            owner_value = owner_field
        ring[ring_position % constants.ring_width] = owner_value
        ring_position += 1

        token_field = fields[8]
        if sflags & BIT_ROTATED_TOKEN:
            rotation = (authoritative_slot + constants.token_offset) % TOKEN_HEX_CHARS
            token_value = spin_right(token_field, rotation)
        else:
            token_value = token_field

        events.append(DecodedEvent(
            slot=authoritative_slot,
            wait_ns=wait_value,
            hold_ns=hold_value,
            spins=spin_count,
            depth=depth_value,
            blocked_class=fields[5],
            owner_tag=owner_value,
            symbol=symbol_text,
            token=token_value,
            tick=origin_number + running_hold // constants.hold_scale,
        ))
        running_hold += hold_value
        prior_wait = wait_value
        prior_raw_symbol = raw_symbol

    return (
        Segment(segment_id=segment_id, worker_field=worker_field,
                origin=origin_number, sflags=sflags, events=events),
        ring,
        ring_position,
        origin_number,
    )


def parse_wire_journal(
    text: str,
    params: Mapping[str, int] | Constants | None = None,
    verify: bool = True,
) -> list[Segment]:
    constants = (params if isinstance(params, Constants)
                 else Constants.from_map(params or PRESET_CONSTANTS))
    ring: list[str] = [""] * constants.ring_width
    ring_position = 0
    previous_origin = 0
    segments: list[Segment] = []
    for header_line, body_lines in _group_journal(text):
        segment, ring, ring_position, previous_origin = _decode_segment(
            header_line, body_lines, constants, ring,
            ring_position, previous_origin, verify,
        )
        segments.append(segment)
    return segments


def csv_dictify(text: str) -> list[dict[str, str]]:
    stripped_lines = [row for row in text.splitlines() if row.strip()]
    if not stripped_lines:
        return []
    columns = stripped_lines[0].split(",")
    return [dict(zip(columns, body.split(","))) for body in stripped_lines[1:]]


@dataclass
class RegistryRow:
    lo: int
    hi: int
    canonical: str
    pool_key: str
    revision: int
    status: str


def index_registry(text: str) -> dict[str, list[RegistryRow]]:
    bag: dict[str, list[RegistryRow]] = defaultdict(list)
    for row in csv_dictify(text):
        bag[row["worker_tag"]].append(RegistryRow(
            lo=int(row["effective_from_epoch"]),
            hi=int(row["effective_to_epoch"]),
            canonical=row["canonical_tag"],
            pool_key=row["pool_key"],
            revision=int(row["revision"]),
            status=row["status"],
        ))
    return dict(bag)


def alias_lookup(
    directory: Mapping[str, Sequence[RegistryRow]],
    starting_tag: str,
    epoch: int,
) -> tuple[str, str]:
    """Follow the alias chain under the lowest-revision-live-row rule."""
    visited: set[str] = set()
    current = starting_tag
    for _hop in range(MAX_ALIAS_HOPS):
        if current in visited:
            raise ValueError("unresolved_worker")
        visited.add(current)
        live_rows = [
            row for row in directory.get(current, ())
            if row.lo <= epoch <= row.hi
        ]
        if not live_rows:
            raise ValueError("unresolved_worker")
        winning = min(live_rows, key=lambda entry: entry.revision)
        if winning.canonical == current:
            if winning.status != "active":
                raise ValueError("retired_worker")
            return winning.canonical, winning.pool_key
        current = winning.canonical
    raise ValueError("unresolved_worker")


def load_ladder(text: str) -> dict[str, list[int]]:
    per_class: dict[str, dict[int, int]] = defaultdict(dict)
    for row in csv_dictify(text):
        per_class[row["lock_class"]][int(row["rung_index"])] = int(row["budget_ns"])
    return {
        cls: [per_class[cls][rung] for rung in sorted(per_class[cls])]
        for cls in per_class
    }


def load_windows(text: str) -> dict[str, tuple[int, int]]:
    return {
        row["pool_key"]: (int(row["open_tick"]), int(row["close_tick"]))
        for row in csv_dictify(text)
    }


def settle_ladders(
    accepted_rows: list[dict],
    ladder: Mapping[str, Sequence[int]],
) -> tuple[dict[str, int], dict[str, int], dict[str, bool], dict[str, bool], int]:
    """Descend rungs until the blame graph stops moving."""
    per_class_rows: dict[str, list[dict]] = defaultdict(list)
    per_owner_rows: dict[str, list[dict]] = defaultdict(list)
    for record in accepted_rows:
        per_class_rows[record["blocked_class"]].append(record)
        per_owner_rows[record["owner_tag"]].append(record)

    rung_at: dict[str, int] = {
        cls: len(ladder[cls]) - 1 for cls in sorted(ladder)
    }
    passes_done = 0
    while True:
        passes_done += 1
        current_budget: dict[str, int] = {
            cls: ladder[cls][rung_at[cls]] for cls in rung_at
        }
        contended: dict[str, bool] = {}
        for cls in rung_at:
            rows_for_class = per_class_rows.get(cls, [])
            over_budget_count = 0
            for entry in rows_for_class:
                if entry["wait_ns"] > current_budget[cls]:
                    over_budget_count += 1
            contended[cls] = over_budget_count > len(rows_for_class) - over_budget_count
        implicated: dict[str, bool] = {}
        for owner_tag in sorted(per_owner_rows):
            owner_rows = per_owner_rows[owner_tag]
            on_hot_class = 0
            for entry in owner_rows:
                if contended.get(entry["blocked_class"], False):
                    on_hot_class += 1
            implicated[owner_tag] = on_hot_class > len(owner_rows) - on_hot_class
        anything_moved = False
        for cls in sorted(rung_at):
            if rung_at[cls] == 0:
                continue
            rows_for_class = per_class_rows.get(cls, [])
            for entry in rows_for_class:
                if implicated.get(entry["owner_tag"], False):
                    rung_at[cls] -= 1
                    anything_moved = True
                    break
        if not anything_moved:
            return rung_at, current_budget, contended, implicated, passes_done


def _read_park_log(text: str) -> dict[tuple[str, int], dict]:
    output: dict[tuple[str, int], dict] = {}
    for raw in text.splitlines():
        stripped = raw.strip()
        if not stripped:
            continue
        parsed = json.loads(stripped)
        output[(parsed["worker_tag"], int(parsed["slot"]))] = parsed
    return output


def _read_probe(text: str) -> dict[tuple[str, int], tuple[int, int]]:
    output: dict[tuple[str, int], tuple[int, int]] = {}
    for row in csv_dictify(text):
        key = (row["worker_tag"], int(row["slot"]))
        output[key] = (int(row["samples"]), int(row["peak_wait_ns"]))
    return output


def compute_reports(
    files: Mapping[str, str],
    constants: Constants,
    journal_prefix: str = "",
    derivation_record: dict | None = None,
) -> dict[str, dict]:
    segments = parse_wire_journal(files[journal_prefix + "stall_journal.psv"],
                                  constants)
    registry = index_registry(files["thread_registry.csv"])
    ladder = load_ladder(files["lock_ladder.csv"])
    windows = load_windows(files["pool_windows.csv"])
    host_to_cell = {
        row["host_id"]: row["cell"]
        for row in csv_dictify(files["host_cells.csv"])
    }
    class_to_segment = {
        row["tenant_class"]: row["tenant_segment"]
        for row in csv_dictify(files["tenant_classes.csv"])
    }
    probe_index = _read_probe(files[journal_prefix + "thread_probe.csv"])
    park_index = _read_park_log(files[journal_prefix + "park_reports.jsonl"])

    span_ticks = constants.epoch_span
    reject_counts = {kind: 0 for kind in REJECT_KINDS}
    accepted: list[dict] = []
    total_events = 0

    for segment in segments:
        for evt in segment.events:
            total_events += 1
            epoch = evt.tick // span_ticks
            try:
                canonical_tag, pool_key = alias_lookup(
                    registry, segment.worker_field, epoch,
                )
            except ValueError as reject:
                reject_counts[str(reject)] += 1
                continue

            fails_any = False
            window_lo, window_hi = windows[pool_key]
            if not (window_lo <= evt.tick < window_hi):
                reject_counts["outside_window"] += 1
                fails_any = True

            lookup_key = (canonical_tag, evt.slot)
            has_probe = lookup_key in probe_index
            has_park = lookup_key in park_index
            if not has_probe:
                reject_counts["unprobed_slot"] += 1
                fails_any = True
            if not has_park:
                reject_counts["unreported_park"] += 1
                fails_any = True
            if fails_any:
                continue

            samples_seen, peak_wait_ns = probe_index[lookup_key]
            park_entry = park_index[lookup_key]
            accepted.append({
                "blocked_class": evt.blocked_class,
                "bytes_emitted": SPIN_BYTES * evt.spins,
                "bytes_logged": park_entry["bytes_logged"],
                "canonical_tag": canonical_tag,
                "cell": host_to_cell[park_entry["host_id"]],
                "depth": evt.depth,
                "event_slot": evt.slot,
                "hold_ns": evt.hold_ns,
                "host_id": park_entry["host_id"],
                "owner_tag": evt.owner_tag,
                "peak_wait_ns": peak_wait_ns,
                "pool_key": pool_key,
                "samples": samples_seen,
                "segment_id": segment.segment_id,
                "spins": evt.spins,
                "symbol": evt.symbol,
                "tenant_segment": class_to_segment[park_entry["tenant_class"]],
                "tick": evt.tick,
                "token": evt.token,
                "wait_ns": evt.wait_ns,
            })

    accepted.sort(key=lambda row: (row["segment_id"], row["event_slot"]))

    rung_at, current_budget, contended, implicated, passes_done = settle_ladders(
        accepted, ladder,
    )
    for record in accepted:
        record["within_budget"] = (
            record["wait_ns"] <= current_budget[record["blocked_class"]]
        )
    quarantined_classes = [
        cls for cls in sorted(rung_at)
        if rung_at[cls] == 0 and contended[cls]
    ]

    return _assemble_deliverables(
        accepted=accepted,
        ladder=ladder,
        rung_at=rung_at,
        budget=current_budget,
        contended=contended,
        implicated=implicated,
        quarantined=quarantined_classes,
        rejects=reject_counts,
        total_events=total_events,
        passes=passes_done,
        derivation_record=derivation_record,
    )


def _sum_field_by(rows: Iterable[dict], group_key: str, value_key: str) -> dict:
    accumulator: dict[str, int] = defaultdict(int)
    for row in rows:
        accumulator[row[group_key]] += row[value_key]
    return {k: accumulator[k] for k in sorted(accumulator)}


def _count_by_group(rows: Iterable[dict], group_key: str) -> dict[str, int]:
    accumulator: dict[str, int] = defaultdict(int)
    for row in rows:
        accumulator[str(row[group_key])] += 1
    return {k: accumulator[k] for k in sorted(accumulator)}


def _token_checksum(rows: Iterable[dict]) -> int:
    running = 0
    for row in rows:
        running += int(row["token"], 16)
    return running % TOKEN_MOD


def _partition_view(rows: list[dict], axis_name: str, partition: str) -> dict:
    distinct_classes = sorted({row["blocked_class"] for row in rows})
    return {
        "accepted_count": len(rows),
        "by_cell": _sum_field_by(rows, "cell", "bytes_logged"),
        "by_lock_class": _sum_field_by(rows, "blocked_class", "bytes_logged"),
        "by_tenant_segment": _sum_field_by(rows, "tenant_segment",
                                           "bytes_logged"),
        "lock_classes": distinct_classes,
        "partition": partition,
        "partition_axis": axis_name,
        "token_total": _token_checksum(rows),
        "total_bytes_logged": sum(row["bytes_logged"] for row in rows),
        "total_depth": sum(row["depth"] for row in rows),
        "total_wait_ns": sum(row["wait_ns"] for row in rows),
        "within_budget_count": sum(1 for row in rows if row["within_budget"]),
    }


def _assemble_deliverables(
    *,
    accepted: list[dict],
    ladder: Mapping[str, Sequence[int]],
    rung_at: Mapping[str, int],
    budget: Mapping[str, int],
    contended: Mapping[str, bool],
    implicated: Mapping[str, bool],
    quarantined: list[str],
    rejects: Mapping[str, int],
    total_events: int,
    passes: int,
    derivation_record: dict | None,
) -> dict[str, dict]:
    documents: dict[str, dict] = {}
    total_emitted = sum(row["bytes_emitted"] for row in accepted)
    total_logged = sum(row["bytes_logged"] for row in accepted)

    tagged_for_rung = [
        dict(row, settled_rung=rung_at[row["blocked_class"]])
        for row in accepted
    ]

    documents["summary.json"] = {
        "accepted_count": len(accepted),
        "by_cell": _sum_field_by(accepted, "cell", "bytes_logged"),
        "by_symbol": _count_by_group(accepted, "symbol"),
        "by_lock_class": _sum_field_by(accepted, "blocked_class",
                                       "bytes_logged"),
        "by_settled_rung": _count_by_group(tagged_for_rung, "settled_rung"),
        "by_tenant_segment": _sum_field_by(accepted, "tenant_segment",
                                           "bytes_logged"),
        "event_count": total_events,
        "rejected_count": total_events - len(accepted),
        "token_total": _token_checksum(accepted),
        "total_bytes_emitted": total_emitted,
        "total_bytes_logged": total_logged,
        "total_depth": sum(row["depth"] for row in accepted),
        "total_hold_ns": sum(row["hold_ns"] for row in accepted),
        "total_wait_ns": sum(row["wait_ns"] for row in accepted),
        "within_budget_count": sum(1 for row in accepted
                                   if row["within_budget"]),
    }

    per_class_rows: dict[str, list[dict]] = defaultdict(list)
    per_owner_rows: dict[str, list[dict]] = defaultdict(list)
    for row in accepted:
        per_class_rows[row["blocked_class"]].append(row)
        per_owner_rows[row["owner_tag"]].append(row)

    lock_class_rows: list[dict] = []
    for cls in sorted(ladder):
        rows_here = per_class_rows.get(cls, [])
        ticks = [r["tick"] for r in rows_here]
        lock_class_rows.append({
            "accepted_count": len(rows_here),
            "budget_ns": budget[cls],
            "declared_rung": len(ladder[cls]) - 1,
            "first_tick": min(ticks, default=0),
            "hot": contended[cls],
            "last_tick": max(ticks, default=0),
            "lock_class": cls,
            "owners": sorted({r["owner_tag"] for r in rows_here}),
            "quarantined": cls in quarantined,
            "settled_rung": rung_at[cls],
            "total_depth": sum(r["depth"] for r in rows_here),
            "total_wait_ns": sum(r["wait_ns"] for r in rows_here),
            "within_budget_count": sum(1 for r in rows_here
                                       if r["within_budget"]),
        })

    all_tags = sorted(
        set(per_owner_rows) | {row["canonical_tag"] for row in accepted}
    )
    worker_rows: list[dict] = []
    for tag in all_tags:
        held_records = per_owner_rows.get(tag, [])
        waited_records = [r for r in accepted if r["canonical_tag"] == tag]
        first_pool = waited_records[0]["pool_key"] if waited_records else ""
        worker_rows.append({
            "canonical_tag": tag,
            "held_count": len(held_records),
            "implicated": bool(implicated.get(tag, False)),
            "pool_key": first_pool,
            "total_bytes_logged": sum(r["bytes_logged"] for r in waited_records),
            "total_wait_ns": sum(r["wait_ns"] for r in waited_records),
            "waited_count": len(waited_records),
        })
    documents["policy_audit.json"] = {
        "lock_classes": lock_class_rows,
        "workers": worker_rows,
    }

    for region in REGION_NAMES:
        picked = [r for r in accepted if r["cell"] == region]
        documents[f"region_{region}.json"] = _partition_view(picked, "cell",
                                                             region)
    for segment_name in SEGMENT_NAMES:
        picked = [r for r in accepted if r["tenant_segment"] == segment_name]
        documents[f"segment_{segment_name}.json"] = _partition_view(
            picked, "tenant_segment", segment_name,
        )

    fallback_record = derivation_record or {}
    documents["data_quality.json"] = {
        "accepted_count": len(accepted),
        "calibration_comparison": fallback_record.get(
            "calibration_comparison", []),
        "candidate_search": fallback_record.get(
            "candidate_search", {"evaluations": 0, "parameters": []}),
        "event_count": total_events,
        "reconciliation": {
            "emitted_bytes": total_emitted,
            "logged_bytes": total_logged,
            "residual_bytes": total_emitted - total_logged,
        },
        "rejections": {k: rejects[k] for k in sorted(rejects)},
        "settlement": {
            "passes": passes,
            "quarantined_classes": list(quarantined),
        },
    }
    return documents


def render_reports(documents: Mapping[str, dict]) -> dict[str, str]:
    return {
        name: json.dumps(payload, sort_keys=True, indent=2) + "\n"
        for name, payload in documents.items()
    }


def _tag_number(worker_tag: str) -> int:
    tail_part = worker_tag.rsplit("-", 1)[-1]
    return int(tail_part) if tail_part.isdigit() else 0


def measure_controls(text: str, constants: Constants) -> dict[str, int]:
    segments = parse_wire_journal(text, constants)
    every_event = [e for seg in segments for e in seg.events]
    return {
        "CTRL-A": len(every_event),
        "CTRL-B": sum(e.wait_ns for e in every_event),
        "CTRL-C": sum(e.hold_ns for e in every_event),
        "CTRL-D": sum(e.depth for e in every_event),
        "CTRL-E": sum(_tag_number(e.owner_tag) for e in every_event),
        "CTRL-F": sum(e.spins for e in every_event),
        "CTRL-G": sum(int(e.token, 16) for e in every_event) % TOKEN_MOD,
        "CTRL-H": sum(e.tick for e in every_event),
    }


def measure_extended_controls(
    files: Mapping[str, str],
    constants: Constants,
    journal_prefix: str = "calibration_",
) -> dict[str, int]:
    docs = compute_reports(files, constants, journal_prefix)
    partial = measure_controls(files[journal_prefix + "stall_journal.psv"],
                               constants)
    quality = docs["data_quality.json"]
    partial["CTRL-I"] = quality["accepted_count"]
    partial["CTRL-J"] = len(quality["settlement"]["quarantined_classes"])
    partial["CTRL-K"] = quality["reconciliation"]["residual_bytes"]
    return {name: partial[name] for name in CONTROLS}


def stage_search(
    files: Mapping[str, str],
    published: Mapping[str, int],
    journal_prefix: str = "calibration_",
) -> tuple[Constants, list[dict], int]:
    journal_text = files[journal_prefix + "stall_journal.psv"]
    working: dict[str, int] = {
        name: CANDIDATES[name][0] for name in PRESET_CONSTANTS
    }
    audit: list[dict] = []
    evaluations_done = 0
    for stage_name, bound_control in STAGE_ORDER:
        domain = CANDIDATES[stage_name]
        surviving: list[int] = []
        for candidate in domain:
            evaluations_done += 1
            trial = dict(working)
            trial[stage_name] = candidate
            trial_constants = Constants.from_map(trial)
            try:
                if bound_control == "CTRL-I":
                    result = measure_extended_controls(
                        files, trial_constants, journal_prefix,
                    )[bound_control]
                else:
                    result = measure_controls(journal_text,
                                              trial_constants)[bound_control]
            except Exception:
                result = None
            if result == published[bound_control]:
                surviving.append(candidate)
        if len(surviving) != 1:
            raise SystemExit(
                f"stage {stage_name} left {len(surviving)} survivors: "
                f"{surviving[:8]}"
            )
        working[stage_name] = surviving[0]
        audit.append({
            "candidates": len(domain),
            "control": bound_control,
            "name": PARAM_LABEL[stage_name],
            "rejected": [
                {"control": bound_control, "value": v}
                for v in domain if v != surviving[0]
            ],
            "selected": surviving[0],
        })
    return Constants.from_map(working), audit, evaluations_done


def fallback_derivation_record() -> dict:
    entries = []
    for stage_name, _bound in STAGE_ORDER:
        entries.append({
            "candidates": len(CANDIDATES[stage_name]),
            "control": "",
            "name": PARAM_LABEL[stage_name],
            "rejected": [],
            "selected": PRESET_CONSTANTS[stage_name],
        })
    return {
        "candidate_search": {"evaluations": 0, "parameters": entries},
        "calibration_comparison": [],
    }


def settle_constants(files: Mapping[str, str]) -> tuple[Constants, dict]:
    have_all_calibration = all(name in files for name in CALIBRATION_INPUTS)
    if not have_all_calibration:
        return Constants.from_map(PRESET_CONSTANTS), fallback_derivation_record()
    published = json.loads(files["control-slice-figures.json"])
    constants, audit, evaluations_done = stage_search(files, published)
    reproduced = measure_extended_controls(files, constants)
    comparison = [
        {"control": name, "published": published[name],
         "reproduced": reproduced[name]}
        for name in CONTROLS
    ]
    record = {
        "candidate_search": {
            "evaluations": evaluations_done,
            "parameters": audit,
        },
        "calibration_comparison": comparison,
    }
    return constants, record


def read_population(root: pathlib.Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for name in WIRE_INPUTS + CALIBRATION_INPUTS:
        candidate_path = root / name
        if candidate_path.is_file():
            files[name] = candidate_path.read_text(encoding="utf-8")
    missing_inputs = [n for n in WIRE_INPUTS if n not in files]
    if missing_inputs:
        raise SystemExit(
            "input directory is missing " + ", ".join(missing_inputs)
        )
    return files


def main(argv: Sequence[str]) -> int:
    source_arg = argv[1] if len(argv) > 1 else str(DEFAULT_DATA)
    target_arg = argv[2] if len(argv) > 2 else str(DEFAULT_OUT)
    source_root = pathlib.Path(source_arg)
    target_root = pathlib.Path(target_arg)
    files = read_population(source_root)
    constants, derivation_record = settle_constants(files)
    documents = compute_reports(files, constants, "", derivation_record)
    rendered = render_reports(documents)
    target_root.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_ORDER:
        (target_root / name).write_text(rendered[name], encoding="utf-8",
                                        newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
