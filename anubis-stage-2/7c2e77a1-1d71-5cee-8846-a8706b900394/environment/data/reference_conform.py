"""Legacy conform engine, kept for continuity.

This module predates `conform_contract.md`. It was written when the house ran a single
delivery family out of one machine room and it has never been revised. Two things in here
carry house sign off and nothing else does:

* `STAGES`, the ordered stage list the house uses when it talks about conform cost.
* `profile(data_dir, scenario)`, the stage visit counter. The counts it returns are the
  agreed measure of where legacy conform work goes.

`legacy_run(data_dir, scenario)` still executes, and operators still read it when they want a
rough shape of a scenario. Its frame numbers, phases, reason codes and totals carry no
authority. Where this module and the contract disagree about a value, the contract holds.
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

STAGES = [
    "admission",
    "corrections",
    "overrides",
    "identity",
    "rate_lookup",
    "span",
    "handles",
    "speed",
    "cadence",
    "state",
]

_NEG = re.compile(r"^\((\d+)\)$")
_CACHE: dict[str, dict] = {}


def _parse_iso(text: str) -> datetime:
    return datetime.strptime(text.strip(), "%Y-%m-%dT%H:%M:%SZ")


def _window_pick(rows, when):
    """Return the row whose window covers `when`."""
    for start, stop, payload in rows:
        if not (when < start or when >= stop):
            return payload
    return None


def _to_int(text: str) -> int:
    body = text.strip()
    if not body:
        return 0
    hit = _NEG.match(body)
    if hit:
        return -int(hit.group(1))
    return int(body)


def _ppm_from_percent(text: str) -> int:
    body = text.strip().strip('"')
    if not body:
        return 1000000
    try:
        return int(round(float(body.replace(",", ".")) * 10000.0))
    except ValueError:
        return 1000000


def _tc_to_frames(tc: str, nominal: int, drop: bool) -> int:
    parts = tc.strip().split(":")
    if len(parts) != 4:
        return 0
    hh, mm, ss, ff = (int(p) for p in parts)
    minutes = hh * 60 + mm
    total = (minutes * 60 + ss) * nominal + ff
    if drop:
        total -= 2 * (minutes - minutes // 10)
    return total


def _rows(path: Path, delim: str = ","):
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=delim)
        head = next(reader, None)
        if head is None:
            return []
        return list(reader)


def _load(data_dir: str) -> dict:
    cached = _CACHE.get(data_dir)
    if cached is not None:
        return cached
    root = Path(data_dir)

    vendor: dict[str, list] = {}
    for key, house, start, stop in _rows(root / "alias_hops_vendor.tsv", "\t"):
        vendor.setdefault(key, []).append((_parse_iso(start), _parse_iso(stop), house))
    house_map: dict[str, list] = {}
    for key, target, start, stop in _rows(root / "alias_hops_house.tsv", "\t"):
        house_map.setdefault(key, []).append((_parse_iso(start), _parse_iso(stop), target))

    assets: dict[tuple[str, str], str] = {}
    for name in ("assets_gen_a.csv", "assets_gen_b.csv", "assets_gen_c.csv"):
        for code, gen, family, _retired in _rows(root / name):
            assets[(code, gen)] = family

    rates: dict[str, list] = {}
    for row in _rows(root / "rate_families.csv"):
        code, start, stop, family, _num, _den, nominal, drop = row
        rates.setdefault(code, []).append(
            (_parse_iso(start), _parse_iso(stop), (family, int(nominal), drop == "true"))
        )

    cadence = []
    for site, src, dlv, num, den in _rows(root / "cadence_map.tsv", "\t"):
        cadence.append((site, src, dlv, int(num), int(den)))

    handles: dict[tuple[str, str], list] = {}
    for cls, site, start, stop, handling in _rows(root / "handle_policy.tsv", "\t"):
        handles.setdefault((cls, site), []).append(
            (_parse_iso(start), _parse_iso(stop), handling)
        )

    transitions: dict[tuple[str, str, str], str] = {}
    for cls, src, dst, legality in _rows(root / "transition_matrix.csv"):
        transitions[(cls, src, dst)] = legality

    cutoffs = json.loads((root / "scenario_cutoffs.json").read_text(encoding="utf-8"))

    delivery = "F2997D"
    bundle = {
        "vendor": vendor,
        "house": house_map,
        "assets": assets,
        "rates": rates,
        "cadence": cadence,
        "handles": handles,
        "transitions": transitions,
        "cutoffs": cutoffs,
        "delivery": delivery,
        "root": root,
    }
    _CACHE[data_dir] = bundle
    return bundle


def _cadence_house(tables, source_family, delivery_family, counts):
    num = den = None
    for site, src, dlv, a, b in tables["cadence"]:
        if counts is not None:
            counts["cadence"] += 1
        if site == "HOUSE" and src == source_family and dlv == delivery_family:
            num, den = a, b
    return num, den


def _resolve_identity(tables, raw, generation, when, counts):
    key = re.sub(r"[ \-]", "", raw).upper()
    digits = re.search(r"\d+", key)
    if digits:
        key = key[: digits.start()] + digits.group(0).zfill(6) + key[digits.end():]
    if counts is not None:
        counts["identity"] += 1
    house = _window_pick(tables["vendor"].get(key, ()), when)
    if house is None:
        return None
    code = house
    for _hop in range(4):
        if counts is not None:
            counts["identity"] += 1
        nxt = _window_pick(tables["house"].get(code, ()), when)
        if nxt is None:
            break
        code = nxt
    if (code, generation) not in tables["assets"]:
        return None
    return code


def _walk(data_dir: str, scenario: str, counts):
    tables = _load(data_dir)
    root = tables["root"]
    cutoff = _parse_iso(tables["cutoffs"]["scenarios"][scenario]["cutoff_utc"])

    rows = []
    for shard in ("a", "b"):
        path = root / ("events_%s_%s.csv" % (scenario, shard))
        if path.exists():
            rows.extend(_rows(path))

    amended: dict[str, dict] = {}
    for part in ("p1", "p2"):
        path = root / ("corrections_%s_%s.jsonl" % (scenario, part))
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if counts is not None:
                    counts["corrections"] += 1
                record = json.loads(line)
                if record["op"] == "delete":
                    amended[record["event_uid"]] = {"__gone__": True}
                else:
                    slot = amended.setdefault(record["event_uid"], {})
                    slot.pop("__gone__", None)
                    slot.update(record["fields"])

    patches: dict[str, dict] = {}
    for half in ("2025h1", "2025h2", "2026h1", "2026h2"):
        path = root / ("overrides_%s.jsonl" % half)
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                if counts is not None:
                    counts["overrides"] += 1
                record = json.loads(line)
                patches.setdefault(record["event_uid"], {})[record["field"]] = record["value"]

    timelines: dict[str, list] = {}
    for row in rows:
        if counts is not None:
            counts["admission"] += 1
        if _parse_iso(row[14]) > cutoff:
            continue
        timelines.setdefault(row[1], []).append(row)

    out = {"scenario": scenario, "timelines": [], "record_frames": 0}
    for timeline_id in sorted(timelines):
        bucket = sorted(timelines[timeline_id], key=lambda r: int(r[2]))
        cursor = 0
        applied = 0
        state = None
        for row in bucket:
            uid = row[0]
            patch = dict(amended.get(uid, {}))
            if patch.get("__gone__"):
                continue
            patch.update(patches.get(uid, {}))
            effective = _parse_iso(row[13])
            site = str(patch.get("site_code", row[21]))
            cls = row[10]
            state_from = state if state is not None else row[11]
            state_to = str(patch.get("state_to", row[12]))
            if counts is not None:
                counts["state"] += 1
            legality = tables["transitions"].get((cls, state_from, state_to))
            if legality != "apply":
                continue
            code = _resolve_identity(tables, row[3], row[4], effective, counts)
            if code is None:
                continue
            family_code = tables["assets"].get((code, row[4]))
            if counts is not None:
                counts["rate_lookup"] += 1
            rate = _window_pick(tables["rates"].get(family_code, ()), effective)
            if rate is None:
                continue
            family, nominal, drop = rate
            in_tc = str(patch.get("source_in_tc", row[5]))
            out_tc = str(patch.get("source_out_tc", row[6]))
            offset = int(patch.get("offset_frames", _to_int(row[16])))
            if counts is not None:
                counts["span"] += 1
            span = (_tc_to_frames(out_tc, nominal, drop) + offset
                    - _tc_to_frames(in_tc, nominal, drop))
            if span <= 0:
                continue
            if counts is not None:
                counts["handles"] += 1
            handling = _window_pick(tables["handles"].get((cls, site), ()), effective)
            if handling == "excluded":
                net = span - int(patch.get("head_handle", row[7])) - int(
                    patch.get("tail_handle", row[8]))
            else:
                net = span
            if net <= 0:
                continue
            ppm = int(patch.get("rate_adjust_ppm", _ppm_from_percent(row[18])))
            if ppm <= 0:
                continue
            if counts is not None:
                counts["speed"] += 1
            adjusted = (net * 1000000 + (ppm - ppm // 2) - 1) // ppm
            num, den = _cadence_house(tables, family, tables["delivery"], counts)
            if num is None:
                continue
            record_span = -(-(adjusted * num) // den)
            cursor += record_span
            applied += 1
            state = state_to
        out["timelines"].append(
            {"timeline_id": timeline_id, "record_frames": cursor, "applied_events": applied}
        )
        out["record_frames"] += cursor
    return out


def legacy_run(data_dir: str, scenario: str) -> dict:
    """Run the legacy conform walk. Frame values carry no authority."""
    return _walk(data_dir, scenario, None)


def profile(data_dir: str, scenario: str) -> dict:
    """Return the house stage visit counts for one scenario."""
    counts = {stage: 0 for stage in STAGES}
    _walk(data_dir, scenario, counts)
    return counts


def clock_window(host_offsets, host, when):
    """Legacy helper retained for the ingest tooling."""
    return _window_pick(host_offsets.get(host, ()), when)


def shift(when: datetime, minutes: int) -> datetime:
    return when - timedelta(minutes=minutes)
