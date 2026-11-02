#!/usr/bin/env python3
"""Settle a film and tape restoration cycle from a catalogue directory.

Usage: cadence_settle.py <catalogue dir> <output dir>

The three unwritten house conventions this implements were recovered from the
published calibration cycle carried in the catalogue:

  * quantisation: a converted frame count is quantised toward the count it was
    converted from, i.e. the frames a conversion adds or removes are truncated
    to whole frames (floor when converting up, ceiling when converting down).
  * composition: the impairment deduction and the restoration credit are
    applied to the conformed count first, and the cadence conversion last.
  * pass ceiling: three fifths of the ceiling carries to the next repair worked
    on the same defect.
"""

import csv
import json
import os
import sys
from fractions import Fraction

CEILING_CARRY = Fraction(3, 5)
GRADE_BANDS = (
    ("A", Fraction(95, 100), Fraction(1, 1)),
    ("B", Fraction(85, 100), Fraction(3, 4)),
    ("C", Fraction(70, 100), Fraction(1, 2)),
    ("D", Fraction(0, 1), Fraction(1, 4)),
)
PHOTOCHEMICAL = ("negative", "interpositive", "print")

VOID_UNKNOWN = "unknown element"
VOID_RETIRED = "retired element"
VOID_EMPTY = "empty shot"
VOID_SPAN = "shot leaves the usable span"
VOID_TILE = "shot ordinals do not tile"
VOID_NO_SHOTS = "no shots"

REPAIR_ACCEPTED = "accepted"
REPAIR_CLAMPED = "clamped"
REPAIR_CLASS = "node class below defect severity"
REPAIR_WINDOW = "outside the repair window"


def quantise(value, source):
    """Quantise a rational frame count toward the whole count it came from."""
    value = Fraction(value)
    if value >= source:
        return value.numerator // value.denominator
    return -((-value.numerator) // value.denominator)


def floor_div(value):
    value = Fraction(value)
    return value.numerator // value.denominator


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_json(path):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_report(out_dir, name, payload):
    path = os.path.join(out_dir, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, sort_keys=True, indent=2)
        handle.write("\n")


def union_length(intervals):
    total = 0
    start = stop = None
    for lo, hi in sorted(intervals):
        if hi <= lo:
            continue
        if start is None:
            start, stop = lo, hi
        elif lo <= stop:
            stop = max(stop, hi)
        else:
            total += stop - start
            start, stop = lo, hi
    if start is not None:
        total += stop - start
    return total


def union_intervals(intervals):
    merged = []
    for lo, hi in sorted(intervals):
        if hi <= lo:
            continue
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return [tuple(span) for span in merged]


def inside(spans, lo, hi):
    return any(span[0] <= lo and hi <= span[1] for span in spans)


# --------------------------------------------------------------------------
# identity


def resolve_identity(scans, events, cycle):
    applying = [e for e in events if int(e["effective_cycle"]) <= cycle]
    retired_at_source = set()
    pointer = {}
    for event in applying:
        kind = event["kind"]
        if kind == "retire":
            retired_at_source.add(event["from_reel"])
        else:
            pointer[event["from_reel"]] = (
                event["to_reel"],
                int(event["registration_offset"]),
            )

    def resolve(reel_id):
        shift = 0
        current = reel_id
        seen = {current}
        while current in pointer:
            current, offset = pointer[current]
            shift += offset
            if current in seen:
                raise ValueError("lineage chain revisits %s" % current)
            seen.add(current)
        return current, shift

    identifiers = set(scans) | set(pointer) | retired_at_source
    for event in applying:
        if event["kind"] != "retire":
            identifiers.add(event["to_reel"])

    resolution = {}
    for reel_id in identifiers:
        canonical, shift = resolve(reel_id)
        retired = canonical in retired_at_source
        resolution[reel_id] = {
            "canonical_id": canonical,
            "registration_shift": shift,
            "retired": retired,
        }
    return resolution


def usable_spans(scans, resolution):
    spans = {}
    for reel_id, scan in scans.items():
        info = resolution[reel_id]
        if info["retired"]:
            continue
        frames = int(scan["scanned_frames"])
        if scan["element_class"] in PHOTOCHEMICAL:
            lo = int(scan["head_leader"])
            hi = frames - int(scan["tail_leader"])
        else:
            lo, hi = 0, frames
        shift = info["registration_shift"]
        spans.setdefault(info["canonical_id"], []).append((lo + shift, hi + shift))
    return {reel: union_intervals(parts) for reel, parts in spans.items()}


# --------------------------------------------------------------------------
# conform


def conform(programmes, cuts, resolution, spans):
    by_programme = {}
    for row in cuts:
        by_programme.setdefault(row["programme_id"], []).append(row)

    report = {}
    for programme_id in sorted(programmes):
        rows = sorted(by_programme.get(programme_id, []), key=lambda r: int(r["shot_ordinal"]))
        reasons = set()
        shots = []
        if not rows:
            reasons.add(VOID_NO_SHOTS)
        ordinals = [int(row["shot_ordinal"]) for row in rows]
        if rows and sorted(ordinals) != list(range(1, len(ordinals) + 1)):
            reasons.add(VOID_TILE)
        for row in rows:
            reel_id = row["reel_id"]
            info = resolution.get(reel_id)
            canonical = info["canonical_id"] if info else reel_id
            shift = info["registration_shift"] if info else 0
            first = int(row["in_frame"]) + shift
            after = int(row["out_frame"]) + shift
            if after <= first:
                reasons.add(VOID_EMPTY)
            if info is not None and info["retired"]:
                reasons.add(VOID_RETIRED)
            elif canonical not in spans:
                reasons.add(VOID_UNKNOWN)
            elif after > first and not inside(spans[canonical], first, after):
                reasons.add(VOID_SPAN)
            shots.append(
                {
                    "canonical_id": canonical,
                    "element_after_last_frame": after,
                    "element_first_frame": first,
                    "frames": after - first,
                    "shot_ordinal": int(row["shot_ordinal"]),
                    "source_reel_id": reel_id,
                    "transition": row["transition"],
                }
            )
        if reasons:
            report[programme_id] = {
                "state": "void",
                "reason": sorted(reasons),
                "conformed_frames": 0,
                "shots": [],
            }
            continue
        timeline = 0
        for shot in shots:
            shot["timeline_start"] = timeline
            timeline += shot["frames"]
            shot["timeline_stop"] = timeline
        report[programme_id] = {
            "state": "conformed",
            "conformed_frames": timeline,
            "shots": shots,
        }
    return report


def governing_element(shots, scans):
    supplied = {}
    for shot in shots:
        supplied[shot["canonical_id"]] = supplied.get(shot["canonical_id"], 0) + shot["frames"]
    pool = {
        reel: frames
        for reel, frames in supplied.items()
        if scans[reel]["element_class"] != "print"
    }
    if not pool:
        pool = supplied
    return sorted(pool.items(), key=lambda item: (-item[1], item[0]))[0][0]


# --------------------------------------------------------------------------
# defects and repairs


def find_defects(defect_log, conformed):
    findings = []
    for row in sorted(defect_log, key=lambda r: r["defect_id"]):
        programme_id = row["programme_id"]
        programme = conformed.get(programme_id)
        if programme is None:
            continue
        ordinal = int(row["shot_ordinal"])
        host = next((s for s in programme["shots"] if s["shot_ordinal"] == ordinal), None)
        if host is None:
            continue
        lo, hi = host["timeline_start"], host["timeline_stop"]
        start = min(max(int(row["span_start"]), lo), hi)
        stop = min(max(int(row["span_end"]), lo), hi)
        if stop < start:
            stop = start
        findings.append(
            {
                "clipped_frames": stop - start,
                "defect_class": row["defect_class"],
                "defect_id": row["defect_id"],
                "detected_stage": row["detected_stage"],
                "programme_id": programme_id,
                "severity": int(row["severity"]),
                "shot_ordinal": ordinal,
                "timeline_start": start,
                "timeline_stop": stop,
            }
        )
    return findings


def impaired_frames(findings, conformed):
    impaired = {programme_id: 0 for programme_id in conformed}
    spans = {}
    for defect in findings:
        spans.setdefault(defect["programme_id"], []).append(
            (defect["timeline_start"], defect["timeline_stop"])
        )
    for programme_id, parts in spans.items():
        impaired[programme_id] = union_length(parts)
    return impaired


def work_repairs(repair_log, findings, programmes, impaired):
    by_id = {defect["defect_id"]: defect for defect in findings}
    rows = [row for row in repair_log if row["defect_id"] in by_id]
    rows.sort(key=lambda r: (int(r["pass_index"]), r["repair_id"]))

    by_programme = {}
    for row in rows:
        by_programme.setdefault(by_id[row["defect_id"]]["programme_id"], []).append(row)

    outcome = {}
    recovered_by_defect = {defect["defect_id"]: 0 for defect in findings}
    recovered = {programme_id: 0 for programme_id in impaired}

    for programme_id, sequence in by_programme.items():
        window_close = int(programmes[programme_id]["window_close_cycle"])
        defect_left = {
            defect["defect_id"]: defect["clipped_frames"]
            for defect in findings
            if defect["programme_id"] == programme_id
        }
        programme_left = impaired[programme_id]
        step = {}
        for row in sequence:
            defect = by_id[row["defect_id"]]
            index = step.get(defect["defect_id"], 0)
            step[defect["defect_id"]] = index + 1
            ceiling = defect["clipped_frames"] * CEILING_CARRY ** index
            claimed = int(row["claimed_frames"])
            if int(row["submitted_cycle"]) > window_close:
                state, frames = REPAIR_WINDOW, 0
            elif int(row["node_class"]) < defect["severity"]:
                state, frames = REPAIR_CLASS, 0
            else:
                allowed = min(
                    Fraction(claimed),
                    ceiling,
                    Fraction(defect_left[defect["defect_id"]]),
                    Fraction(programme_left),
                )
                frames = max(0, floor_div(allowed))
                state = REPAIR_ACCEPTED if frames == claimed else REPAIR_CLAMPED
            defect_left[defect["defect_id"]] -= frames
            programme_left -= frames
            recovered_by_defect[defect["defect_id"]] += frames
            recovered[programme_id] += frames
            outcome[row["repair_id"]] = {
                "claimed_frames": claimed,
                "defect_id": defect["defect_id"],
                "pass_index": int(row["pass_index"]),
                "programme_id": programme_id,
                "recovered_frames": frames,
                "repair_id": row["repair_id"],
                "state": state,
            }
    ledger = [outcome[row["repair_id"]] for row in rows]
    return ledger, recovered, recovered_by_defect


# --------------------------------------------------------------------------
# cadence


def band_of(settled, cadence):
    for band, share, _ in GRADE_BANDS:
        if Fraction(settled) >= share * cadence:
            return band
    return GRADE_BANDS[-1][0]


def settle_programme(source, impaired, recovered, ratio):
    """Settle a programme at its delivery cadence, highest self consistent grade."""
    cadence = quantise(source * ratio, source)
    unrecovered = impaired - recovered
    for name, _, credit_share in GRADE_BANDS:
        credit = quantise(credit_share * recovered, recovered)
        base = source - unrecovered + credit
        settled = quantise(base * ratio, base)
        if band_of(settled, cadence) == name:
            return name, cadence, settled
    raise ValueError("no stable condition grade")


# --------------------------------------------------------------------------
# allocation


def group_quota(holders, drawing, factor):
    quota = {}
    for holder in holders.values():
        quota[holder["settlement_group"]] = 0
    for group in quota:
        members = [h for h in drawing if holders[h]["settlement_group"] == group]
        if members:
            total = sum(int(holders[h]["base_quota_frames"]) for h in members)
            quota[group] = total - factor * (len(members) - 1)
    return quota


def run_draw(settled, holders, drawing, factor):
    quota = group_quota(holders, drawing, factor)
    by_group = {}
    for programme_id, row in settled.items():
        by_group.setdefault(row["settlement_group"], []).append(programme_id)
    admitted = set()
    used = {group: 0 for group in quota}
    for group, members in by_group.items():
        members.sort(key=lambda p: (-settled[p]["settled_frames"], p))
        consumed = 0
        closed = False
        for programme_id in members:
            frames = settled[programme_id]["settled_frames"]
            if closed or consumed + frames > quota[group]:
                closed = True
                continue
            consumed += frames
            admitted.add(programme_id)
        used[group] = consumed
    return admitted, quota, used


def drawn_by(settled, holders, drawing, factor):
    admitted, _, _ = run_draw(settled, holders, drawing, factor)
    return {settled[p]["holder_id"] for p in admitted}


def stable_drawing_set(settled, holders, factor):
    """The one drawing set under which exactly the drawing holders are admitted."""
    candidates = sorted({row["holder_id"] for row in settled.values()})
    drawing = set(candidates)
    for _ in range(len(candidates) + 1):
        holding = drawn_by(settled, holders, drawing, factor)
        if holding == drawing:
            return drawing
        drawing = holding
    for mask in range(1 << len(candidates)):
        subset = {candidates[i] for i in range(len(candidates)) if mask >> i & 1}
        if drawn_by(settled, holders, subset, factor) == subset:
            return subset
    raise ValueError("no stable drawing set")


def seat_vaults(admitted, settled, vaults):
    order = sorted(admitted, key=lambda p: (-settled[p]["settled_frames"], p))
    ranked = sorted(vaults, key=lambda v: (int(v["seat_rank"]), v["vault_id"]))
    load = {vault["vault_id"]: 0 for vault in ranked}
    seating = {}

    def place(index):
        if index == len(order):
            return True
        programme_id = order[index]
        row = settled[programme_id]
        for vault in ranked:
            if row["deliverable_class"] not in vault["accepts_classes"]:
                continue
            if row["settlement_group"] not in vault["settlement_groups"]:
                continue
            if load[vault["vault_id"]] + row["settled_frames"] > int(vault["capacity_frames"]):
                continue
            load[vault["vault_id"]] += row["settled_frames"]
            seating[programme_id] = vault["vault_id"]
            if place(index + 1):
                return True
            load[vault["vault_id"]] -= row["settled_frames"]
            del seating[programme_id]
        return False

    if not place(0):
        raise ValueError("no complete seating")
    return seating, load


def cascade_lanes(held, settled, lanes, pool):
    ranked = sorted(lanes, key=lambda l: (int(l["lane_rank"]), l["lane_id"]))
    offer = sorted(held, key=lambda p: (-settled[p]["settled_frames"], p))
    seating = {}
    capacity = {}
    load = {}
    remaining = pool
    for lane in ranked:
        cap = floor_div(
            Fraction(remaining * int(lane["residual_share_num"]), int(lane["residual_share_den"]))
        )
        capacity[lane["lane_id"]] = cap
        room = cap
        taken = 0
        for programme_id in offer:
            if programme_id in seating:
                continue
            row = settled[programme_id]
            if row["deliverable_class"] not in lane["accepts_classes"]:
                continue
            if row["settlement_group"] not in lane["settlement_groups"]:
                continue
            if row["settled_frames"] > room:
                continue
            room -= row["settled_frames"]
            taken += row["settled_frames"]
            seating[programme_id] = lane["lane_id"]
        load[lane["lane_id"]] = taken
        remaining -= taken
    return seating, capacity, load


# --------------------------------------------------------------------------


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: cadence_settle.py <catalogue dir> <output dir>\n")
        return 2
    catalogue, out_dir = argv[1], argv[2]
    os.makedirs(out_dir, exist_ok=True)

    scans = {row["reel_id"]: row for row in read_csv(os.path.join(catalogue, "reel_scans.csv"))}
    events = read_csv(os.path.join(catalogue, "lineage_events.csv"))
    cuts = read_csv(os.path.join(catalogue, "cut_list.csv"))
    programmes = {
        row["programme_id"]: row
        for row in read_csv(os.path.join(catalogue, "programmes.csv"))
    }
    defect_log = read_csv(os.path.join(catalogue, "defect_log.csv"))
    repair_log = read_csv(os.path.join(catalogue, "repair_log.csv"))
    holders = {row["holder_id"]: row for row in read_csv(os.path.join(catalogue, "holders.csv"))}
    vault_charter = read_json(os.path.join(catalogue, "vault_charter.json"))
    lane_charter = read_json(os.path.join(catalogue, "lane_charter.json"))

    cycle = int(vault_charter["settlement_cycle"])
    factor = int(vault_charter["group_draw_factor"])
    vaults = vault_charter["vaults"]
    lanes = lane_charter["lanes"]

    resolution = resolve_identity(scans, events, cycle)
    spans = usable_spans(scans, resolution)

    # ---- reel audit
    live = sorted(
        reel
        for reel in scans
        if resolution[reel]["canonical_id"] == reel and not resolution[reel]["retired"]
    )
    retired = sorted(reel for reel in scans if resolution[reel]["retired"])
    folded = {}
    reel_rows = []
    for reel in sorted(scans):
        info = resolution[reel]
        if info["retired"]:
            state = "retired"
        elif info["canonical_id"] == reel:
            state = "live"
        else:
            state = "folded"
            folded.setdefault(info["canonical_id"], []).append(reel)
        reel_rows.append(
            {
                "canonical_id": info["canonical_id"],
                "element_class": scans[reel]["element_class"],
                "reel_id": reel,
                "registration_shift": info["registration_shift"],
                "scan_cadence_mhz": int(scans[reel]["scan_cadence_mhz"]),
                "scanned_frames": int(scans[reel]["scanned_frames"]),
                "state": state,
            }
        )
    reel_audit = {
        "canonical_elements": live,
        "folded_elements": {reel: sorted(parts) for reel, parts in sorted(folded.items())},
        "reels": reel_rows,
        "retired_elements": retired,
        "settlement_cycle": cycle,
        "usable_frames": {
            reel: union_length(spans.get(reel, [])) for reel in live
        },
    }

    # ---- conform
    conform_rows = conform(programmes, cuts, resolution, spans)
    conformed = {p: row for p, row in conform_rows.items() if row["state"] == "conformed"}
    voided = sorted(p for p, row in conform_rows.items() if row["state"] == "void")

    conform_report = {
        "conformed_programmes": sorted(conformed),
        "programmes": [],
        "void_programmes": voided,
    }
    for programme_id in sorted(conform_rows):
        row = conform_rows[programme_id]
        entry = {
            "conformed_frames": row["conformed_frames"],
            "programme_id": programme_id,
            "shot_count": len(row["shots"]),
            "shots": [
                {
                    "canonical_id": shot["canonical_id"],
                    "element_after_last_frame": shot["element_after_last_frame"],
                    "element_first_frame": shot["element_first_frame"],
                    "frames": shot["frames"],
                    "shot_ordinal": shot["shot_ordinal"],
                    "source_reel_id": shot["source_reel_id"],
                    "timeline_start": shot["timeline_start"],
                    "timeline_stop": shot["timeline_stop"],
                    "transition": shot["transition"],
                }
                for shot in row["shots"]
            ],
            "state": row["state"],
        }
        if row["state"] == "void":
            entry["reason"] = row["reason"]
        conform_report["programmes"].append(entry)

    # ---- defects and repairs
    findings = find_defects(defect_log, conformed)
    impaired = impaired_frames(findings, conformed)
    ledger, recovered, recovered_by_defect = work_repairs(
        repair_log, findings, programmes, impaired
    )

    defect_findings = {
        "defects": [
            {
                "clipped_frames": defect["clipped_frames"],
                "defect_class": defect["defect_class"],
                "defect_id": defect["defect_id"],
                "detected_stage": defect["detected_stage"],
                "programme_id": defect["programme_id"],
                "recovered_frames": recovered_by_defect[defect["defect_id"]],
                "severity": defect["severity"],
                "shot_ordinal": defect["shot_ordinal"],
                "timeline_start": defect["timeline_start"],
                "timeline_stop": defect["timeline_stop"],
            }
            for defect in findings
        ],
        "impaired_frames": {p: impaired[p] for p in sorted(impaired)},
        "impaired_total": sum(impaired.values()),
    }

    state_counts = {}
    for row in ledger:
        state_counts[row["state"]] = state_counts.get(row["state"], 0) + 1
    repair_ledger = {
        "recovered_frames": {p: recovered[p] for p in sorted(recovered)},
        "recovered_total": sum(recovered.values()),
        "repairs": ledger,
        "state_counts": dict(sorted(state_counts.items())),
    }

    # ---- cadence
    cadence_rows = []
    settled = {}
    for programme_id in sorted(conformed):
        row = conformed[programme_id]
        programme = programmes[programme_id]
        element = governing_element(row["shots"], scans)
        element_cadence = int(scans[element]["scan_cadence_mhz"])
        delivery = int(programme["delivery_cadence_mhz"])
        ratio = Fraction(delivery, element_cadence)
        source = row["conformed_frames"]
        grade, cadence_frames, settled_frames = settle_programme(
            source, impaired[programme_id], recovered[programme_id], ratio
        )
        cadence_rows.append(
            {
                "cadence_frames": cadence_frames,
                "condition_grade": grade,
                "delivery_cadence_mhz": delivery,
                "element_cadence_mhz": element_cadence,
                "governing_element": element,
                "impaired_frames": impaired[programme_id],
                "programme_id": programme_id,
                "recovered_frames": recovered[programme_id],
                "settled_frames": settled_frames,
                "source_frames": source,
                "unrecovered_frames": impaired[programme_id] - recovered[programme_id],
            }
        )
        settled[programme_id] = {
            "condition_grade": grade,
            "deliverable_class": programme["deliverable_class"],
            "holder_id": programme["holder_id"],
            "programme_id": programme_id,
            "settled_frames": settled_frames,
            "settlement_group": holders[programme["holder_id"]]["settlement_group"],
            "title_key": programme["title_key"],
        }
    cadence_ledger = {
        "cadence_total": sum(row["cadence_frames"] for row in cadence_rows),
        "programmes": cadence_rows,
        "settled_total": sum(row["settled_frames"] for row in cadence_rows),
        "source_total": sum(row["source_frames"] for row in cadence_rows),
    }

    # ---- allocation
    drawing = stable_drawing_set(settled, holders, factor)
    admitted_set, quota, used = run_draw(settled, holders, drawing, factor)
    held_set = set(settled) - admitted_set
    draw_order = sorted(settled, key=lambda p: (-settled[p]["settled_frames"], p))
    allocation_ledger = {
        "admitted": sorted(admitted_set),
        "draw_order": [
            {
                "holder_id": settled[p]["holder_id"],
                "programme_id": p,
                "settled_frames": settled[p]["settled_frames"],
                "settlement_group": settled[p]["settlement_group"],
                "state": "admitted" if p in admitted_set else "held",
            }
            for p in draw_order
        ],
        "drawing_holders": sorted(drawing),
        "group_quota": {group: quota[group] for group in sorted(quota)},
        "group_used": {group: used[group] for group in sorted(used)},
        "held": sorted(held_set),
    }

    # ---- seating
    seating, vault_load = seat_vaults(admitted_set, settled, vaults)
    vault_rows = []
    for vault in sorted(vaults, key=lambda v: (int(v["seat_rank"]), v["vault_id"])):
        vault_id = vault["vault_id"]
        capacity = int(vault["capacity_frames"])
        load = vault_load[vault_id]
        members = sorted(
            (p for p, v in seating.items() if v == vault_id),
            key=lambda p: (-settled[p]["settled_frames"], p),
        )
        vault_rows.append(
            {
                "capacity_frames": capacity,
                "headroom_frames": capacity - load,
                "load_frames": load,
                "programme_count": len(members),
                "seat_rank": int(vault["seat_rank"]),
                "vault_id": vault_id,
            }
        )
        write_report(
            out_dir,
            "vault_%s.json" % vault_id,
            {
                "accepts_classes": sorted(vault["accepts_classes"]),
                "capacity_frames": capacity,
                "headroom_frames": capacity - load,
                "load_frames": load,
                "programmes": [dict(settled[p]) for p in members],
                "seat_rank": int(vault["seat_rank"]),
                "settlement_groups": sorted(vault["settlement_groups"]),
                "vault_id": vault_id,
            },
        )
    residual_pool = sum(row["headroom_frames"] for row in vault_rows)
    vault_index = {
        "residual_pool_frames": residual_pool,
        "seated_total_frames": sum(row["load_frames"] for row in vault_rows),
        "vaults": vault_rows,
    }

    # ---- cascade
    lane_seating, lane_capacity, lane_load = cascade_lanes(
        held_set, settled, lanes, residual_pool
    )
    for lane in sorted(lanes, key=lambda l: (int(l["lane_rank"]), l["lane_id"])):
        lane_id = lane["lane_id"]
        capacity = lane_capacity[lane_id]
        load = lane_load[lane_id]
        members = sorted(
            (p for p, l in lane_seating.items() if l == lane_id),
            key=lambda p: (-settled[p]["settled_frames"], p),
        )
        write_report(
            out_dir,
            "lane_%s.json" % lane_id,
            {
                "accepts_classes": sorted(lane["accepts_classes"]),
                "capacity_frames": capacity,
                "headroom_frames": capacity - load,
                "lane_id": lane_id,
                "lane_rank": int(lane["lane_rank"]),
                "load_frames": load,
                "programmes": [dict(settled[p]) for p in members],
                "settlement_groups": sorted(lane["settlement_groups"]),
            },
        )

    shed_set = held_set - set(lane_seating)
    admitted_frames = sum(settled[p]["settled_frames"] for p in admitted_set)
    held_frames = sum(settled[p]["settled_frames"] for p in held_set)
    lane_frames = sum(lane_load.values())
    shed_frames = sum(settled[p]["settled_frames"] for p in shed_set)
    settled_total = admitted_frames + held_frames
    impaired_total = sum(impaired.values())
    recovered_total = sum(recovered.values())

    summary = {
        "admitted_count": len(admitted_set),
        "admitted_frames": admitted_frames,
        "conformed_programme_count": len(conformed),
        "held_count": len(held_set),
        "held_frames": held_frames,
        "impaired_total": impaired_total,
        "lane_frames": lane_frames,
        "lane_seated_count": len(lane_seating),
        "recovered_total": recovered_total,
        "settled_total": settled_total,
        "settlement_cycle": cycle,
        "shed_count": len(shed_set),
        "shed_frames": shed_frames,
        "void_programme_count": len(voided),
    }

    stages = [
        ("conform", len(programmes), len(conformed) + len(voided)),
        ("impairment", impaired_total, recovered_total + (impaired_total - recovered_total)),
        ("admission", settled_total, admitted_frames + held_frames),
        ("seating", admitted_frames, sum(vault_load.values())),
        ("cascade", held_frames, lane_frames + shed_frames),
    ]
    stage_rows = []
    for name, left, right in stages:
        stage_rows.append(
            {
                "closes": left - right == 0,
                "left": left,
                "residual": left - right,
                "right": right,
                "stage": name,
            }
        )
    reconciliation = {
        "residual": sum(abs(row["residual"]) for row in stage_rows),
        "settled_total": settled_total,
        "stages": stage_rows,
        "vault_and_lane_total": sum(vault_load.values()) + lane_frames + shed_frames,
    }

    write_report(out_dir, "summary.json", summary)
    write_report(out_dir, "reconciliation.json", reconciliation)
    write_report(out_dir, "reel_audit.json", reel_audit)
    write_report(out_dir, "conform_report.json", conform_report)
    write_report(out_dir, "defect_findings.json", defect_findings)
    write_report(out_dir, "repair_ledger.json", repair_ledger)
    write_report(out_dir, "cadence_ledger.json", cadence_ledger)
    write_report(out_dir, "allocation_ledger.json", allocation_ledger)
    write_report(out_dir, "vault_index.json", vault_index)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
