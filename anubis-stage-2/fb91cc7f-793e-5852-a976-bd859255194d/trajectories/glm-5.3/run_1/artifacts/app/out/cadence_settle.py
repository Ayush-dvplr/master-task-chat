#!/usr/bin/env python3
"""Cadence settlement for the film and tape restoration lab.

Settles a cycle from its catalogue: identity resolution, conform, impairment,
repair, cadence settlement, allocation, vault seating and overflow lanes.

Usage:  cadence_settle.py <catalogue directory> <output directory>

Standard library only. Every figure comes from the catalogue.
"""
import csv
import json
import os
import sys
from fractions import Fraction
from itertools import combinations

# ---------------------------------------------------------------- conventions

PHOTOCHEMICAL = {"negative", "interpositive", "print"}

# Standing house conventions, recovered from the published calibration cycle.
#   quantisation: a converted frame count is rounded to the nearest whole
#     frame, a half going to the even neighbour
#   composition: the impairment deduction acts first, then the cadence
#     conversion, then the restoration credit
#   repair ceiling: each repair after the first worked on a defect may recover
#     three fifths of the ceiling the repair before it could have recovered
CARRY = Fraction(3, 5)
CREDIT_RATE = {"A": Fraction(1), "B": Fraction(3, 4),
               "C": Fraction(1, 2), "D": Fraction(1, 4)}
BANDS = (("A", Fraction(95, 100)), ("B", Fraction(85, 100)),
         ("C", Fraction(70, 100)))


def quantise(x):
    """The lab's standing quantisation: nearest whole frame, halves to even."""
    f = Fraction(x)
    low = f.numerator // f.denominator
    rem = f.numerator - low * f.denominator
    twice = rem * 2
    if twice < f.denominator:
        return low
    if twice > f.denominator:
        return low + 1
    return low if low % 2 == 0 else low + 1


# --------------------------------------------------------------------- reading

def read_csv(path):
    with open(path, newline="") as fh:
        return [{k: v for k, v in row.items() if k is not None}
                for row in csv.DictReader(fh)]


def read_json(path):
    with open(path) as fh:
        return json.load(fh)


def as_int(value):
    if isinstance(value, int):
        return value
    return int(str(value).strip())


class Catalogue:
    """The scanned elements and everything filed against them."""

    FILENAMES = {
        "reel_scans": "reel_scans.csv",
        "lineage": "lineage_events.csv",
        "cut_list": "cut_list.csv",
        "programmes": "programmes.csv",
        "holders": "holders.csv",
        "defects": "defect_log.csv",
        "repairs": "repair_log.csv",
    }

    def __init__(self, directory):
        for attr, name in self.FILENAMES.items():
            setattr(self, attr, read_csv(os.path.join(directory, name)))
        self.vault_charter = read_json(os.path.join(directory, "vault_charter.json"))
        self.lane_charter = read_json(os.path.join(directory, "lane_charter.json"))
        self.cycle = self.vault_charter["settlement_cycle"]

    @property
    def scans(self):
        return {row["reel_id"]: row for row in self.reel_scans}

    @property
    def programme_rows(self):
        return {row["programme_id"]: row for row in self.programmes}

    @property
    def holder_rows(self):
        return {row["holder_id"]: row for row in self.holders}


# -------------------------------------------------------------------- identity

def apply_events(catalogue):
    """Only lineage events whose effective cycle has arrived act."""
    acting = {}
    for event in catalogue.lineage:
        if as_int(event["effective_cycle"]) <= catalogue.cycle:
            acting[event["from_reel"]] = event
    return acting


def resolve_identity(catalogue):
    """reel id -> the live element it resolves to, its shift and its state."""
    acting = apply_events(catalogue)
    resolved = {}

    def walk(reel_id, seen):
        if reel_id in resolved:
            return resolved[reel_id]
        if reel_id in seen:
            raise RuntimeError("lineage chain closes on itself at %s" % reel_id)
        event = acting.get(reel_id)
        if event is None:
            entry = (reel_id, 0, "live")
        elif event["kind"] == "retire":
            entry = (reel_id, 0, "retired")
        else:
            target, shift, state = walk(event["to_reel"], seen | {reel_id})
            entry = (target, shift + as_int(event["registration_offset"]), state)
        resolved[reel_id] = entry
        return entry

    for row in catalogue.reel_scans:
        walk(row["reel_id"], frozenset())
    return resolved


def element_usable_spans(catalogue, identity):
    """canonical element id -> (first frame, first frame past the end)."""
    scans = catalogue.scans
    parts = {}
    for reel_id, (canonical, shift, state) in identity.items():
        if state == "retired":
            continue
        scan = scans[reel_id]
        frames = as_int(scan["scanned_frames"])
        if scan["element_class"] in PHOTOCHEMICAL:
            first = as_int(scan["head_leader"])
            past = frames - as_int(scan["tail_leader"])
        else:
            first, past = 0, frames
        parts.setdefault(canonical, []).append((first + shift, past + shift))
    spans = {}
    for canonical, pieces in parts.items():
        spans[canonical] = (min(p[0] for p in pieces), max(p[1] for p in pieces))
    return spans


# --------------------------------------------------------------------- conform

VOID_UNKNOWN = "unknown element"
VOID_RETIRED = "retired element"
VOID_EMPTY = "empty shot"
VOID_SPAN = "shot leaves the usable span"
VOID_TILE = "shot ordinals do not tile"
VOID_NOSHOT = "no shots"


def conform_programmes(catalogue, identity, spans):
    shots_by_programme = {}
    for row in catalogue.cut_list:
        shots_by_programme.setdefault(row["programme_id"], []).append(row)

    reports = {}
    for programme in sorted(catalogue.programmes, key=lambda r: r["programme_id"]):
        programme_id = programme["programme_id"]
        rows = sorted(shots_by_programme.get(programme_id, []),
                      key=lambda r: as_int(r["shot_ordinal"]))
        reasons = set()
        shots = []
        for row in rows:
            reel_id = row["reel_id"]
            ordinal = as_int(row["shot_ordinal"])
            first = as_int(row["in_frame"])
            past = as_int(row["out_frame"])
            length = past - first
            entry = identity.get(reel_id)
            if entry is None:
                reasons.add(VOID_UNKNOWN)
                shots.append({"source_reel_id": reel_id, "shot_ordinal": ordinal,
                              "canonical_id": None, "element_first_frame": None,
                              "element_after_last_frame": None, "frames": 0,
                              "timeline_start": 0, "timeline_stop": 0,
                              "transition": row["transition"]})
                continue
            canonical, shift, state = entry
            element_first = first + shift
            element_past = past + shift
            if state == "retired":
                reasons.add(VOID_RETIRED)
            if length <= 0:
                reasons.add(VOID_EMPTY)
            # a retired element supplies no picture, so it has no usable span
            span_first, span_past = spans.get(canonical, (0, 0))
            if not (span_first <= element_first and element_past <= span_past):
                reasons.add(VOID_SPAN)
            shots.append({"source_reel_id": reel_id, "shot_ordinal": ordinal,
                          "canonical_id": canonical,
                          "element_first_frame": element_first,
                          "element_after_last_frame": element_past,
                          "frames": max(length, 0), "timeline_start": 0,
                          "timeline_stop": 0, "transition": row["transition"]})
        if not rows:
            reasons.add(VOID_NOSHOT)
        else:
            ordinals = sorted(as_int(r["shot_ordinal"]) for r in rows)
            if ordinals != list(range(1, len(ordinals) + 1)):
                reasons.add(VOID_TILE)
        voided = bool(reasons)
        timeline = 0
        for shot in shots:
            shot["timeline_start"] = timeline
            timeline += shot["frames"]
            shot["timeline_stop"] = timeline
        reports[programme_id] = {
            "programme_id": programme_id,
            "state": "void" if voided else "conformed",
            "reason": sorted(reasons),
            "shots": [] if voided else shots,
            "shot_count": 0 if voided else len(shots),
            "conformed_frames": 0 if voided else timeline,
        }
    return reports


def governing_element(programme, scans):
    """The element that supplies the most frames, prints never governing
    while any other class supplies the programme."""
    tally = {}
    for shot in programme["shots"]:
        if shot["canonical_id"]:
            tally[shot["canonical_id"]] = tally.get(shot["canonical_id"], 0) + shot["frames"]
    if not tally:
        return None
    classes = {element: scans[element]["element_class"] for element in tally}
    pool = tally if all(c == "print" for c in classes.values()) else \
        {e: n for e, n in tally.items() if classes[e] != "print"}
    return sorted(pool.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


# ------------------------------------------------------------------ impairment

def clip_defects(catalogue, conformed):
    """Every defect raised against a conformed programme and one of its shots."""
    by_shot = {}
    for programme_id, report in conformed.items():
        if report["state"] == "conformed":
            by_shot[programme_id] = {s["shot_ordinal"]: s for s in report["shots"]}
    findings = []
    for row in sorted(catalogue.defects, key=lambda r: r["defect_id"]):
        programme_id = row["programme_id"]
        report = conformed.get(programme_id)
        if report is None or report["state"] != "conformed":
            continue
        shot = by_shot[programme_id].get(as_int(row["shot_ordinal"]))
        if shot is None:
            continue
        start = max(as_int(row["span_start"]), shot["timeline_start"])
        stop = min(as_int(row["span_end"]), shot["timeline_stop"])
        if stop < start:
            stop = start
        findings.append({
            "defect_id": row["defect_id"], "programme_id": programme_id,
            "shot_ordinal": as_int(row["shot_ordinal"]),
            "defect_class": row["defect_class"],
            "severity": as_int(row["severity"]),
            "detected_stage": row["detected_stage"],
            "timeline_start": start, "timeline_stop": stop,
            "clipped_frames": stop - start,
        })
    return findings


def impaired_frames(findings, conformed):
    """Frames of a timeline at least one defect covers; a frame counts once."""
    impaired = {}
    for programme_id, report in conformed.items():
        if report["state"] != "conformed":
            continue
        spans = sorted((f["timeline_start"], f["timeline_stop"])
                       for f in findings if f["programme_id"] == programme_id)
        total = 0
        current = None
        for start, stop in spans:
            if current is None:
                current = [start, stop]
            elif start <= current[1]:
                current[1] = max(current[1], stop)
            else:
                total += current[1] - current[0]
                current = [start, stop]
        if current is not None:
            total += current[1] - current[0]
        impaired[programme_id] = total
    return impaired


# ---------------------------------------------------------------------- repair

def work_repairs(catalogue, findings, impaired, windows):
    """Repairs worked in pass order then repair id, ceiling falling as it goes."""
    coverage = {f["defect_id"]: f["clipped_frames"] for f in findings}
    programme_of = {f["defect_id"]: f["programme_id"] for f in findings}

    sequence = {}
    for row in catalogue.repairs:
        defect_id = row["defect_id"]
        if defect_id not in coverage:
            continue
        sequence.setdefault(programme_of[defect_id], []).append(row)
    for programme_id in sequence:
        sequence[programme_id].sort(
            key=lambda r: (as_int(r["pass_index"]), r["repair_id"]))

    severities = {f["defect_id"]: f["severity"] for f in findings}
    recovered_by_defect = {defect_id: 0 for defect_id in coverage}
    recovered_by_programme = {p: 0 for p in impaired}
    repairs = []
    for programme_id in sorted(sequence):
        programme_left = impaired[programme_id]
        ceiling = {}
        for row in sequence[programme_id]:
            defect_id = row["defect_id"]
            claim = as_int(row["claimed_frames"])
            # the ceiling falls at every step of the order, standing or not
            if defect_id in ceiling:
                ceiling[defect_id] = ceiling[defect_id] * CARRY
            else:
                ceiling[defect_id] = Fraction(coverage[defect_id])
            if as_int(row["submitted_cycle"]) > windows[programme_id]:
                state, recovered = "outside the repair window", 0
            elif as_int(row["node_class"]) < severities[defect_id]:
                state, recovered = "node class below defect severity", 0
            else:
                bound = min(ceiling[defect_id],
                            Fraction(coverage[defect_id] - recovered_by_defect[defect_id]),
                            Fraction(programme_left))
                recovered = min(Fraction(claim), bound).__floor__()
                programme_left -= recovered
                recovered_by_defect[defect_id] += recovered
                state = "accepted" if recovered == claim else "clamped"
            repairs.append({
                "repair_id": row["repair_id"], "defect_id": defect_id,
                "programme_id": programme_id, "pass_index": as_int(row["pass_index"]),
                "claimed_frames": claim, "recovered_frames": recovered,
                "state": state,
            })
            recovered_by_programme[programme_id] += recovered
    repairs.sort(key=lambda r: (r["pass_index"], r["repair_id"]))
    return repairs, recovered_by_programme


# --------------------------------------------------------------------- cadence

def convert(count, source_cadence, delivery_cadence):
    return quantise(Fraction(count) * Fraction(delivery_cadence) / Fraction(source_cadence))


def condition_grade(settled, base):
    for grade, floor in BANDS:
        if settled >= floor * base:
            return grade
    return "D"


def settle_programme(source_frames, element_cadence, delivery_cadence,
                     impaired, recovered):
    """Deduction, then cadence conversion, then restoration credit.

    The deduction is taken from the element cadence count, the conversion moves
    the figure to the delivery cadence, and the credit is earned by the
    recovered frames at the delivery cadence under the settled grade.
    """
    rate = Fraction(delivery_cadence) / Fraction(element_cadence)
    unrecovered = impaired - recovered
    base = convert(source_frames, element_cadence, delivery_cadence)
    converted = convert(source_frames - unrecovered, element_cadence,
                        delivery_cadence)
    settled = converted
    grade = "D"
    for candidate in ("A", "B", "C", "D"):
        figure = converted + quantise(Fraction(recovered) * rate * CREDIT_RATE[candidate])
        if condition_grade(figure, base) == candidate:
            settled, grade = figure, candidate
            break
    return {
        "source_frames": source_frames,
        "cadence_frames": base,
        "unrecovered_frames": unrecovered,
        "settled_frames": settled,
        "condition_grade": grade,
    }


def settle_cycle(catalogue, conformed, impaired, recovered_by_programme):
    scans = catalogue.scans
    programmes = catalogue.programme_rows
    ledger = {}
    for programme_id, report in conformed.items():
        if report["state"] != "conformed":
            continue
        governing = governing_element(report, scans)
        element_cadence = as_int(scans[governing]["scan_cadence_mhz"])
        delivery_cadence = as_int(programmes[programme_id]["delivery_cadence_mhz"])
        result = settle_programme(report["conformed_frames"], element_cadence,
                                 delivery_cadence, impaired[programme_id],
                                 recovered_by_programme[programme_id])
        result.update({
            "programme_id": programme_id,
            "governing_element": governing,
            "element_cadence_mhz": element_cadence,
            "delivery_cadence_mhz": delivery_cadence,
            "impaired_frames": impaired[programme_id],
            "recovered_frames": recovered_by_programme[programme_id],
        })
        ledger[programme_id] = result
    return ledger


# ------------------------------------------------------------------ allocation

def group_quota(holders, groups, factor, drawing):
    """A group's quota is its drawing holders' base quotas, less the charter's
    group draw factor once for each drawing holder beyond the first."""
    quota = {group: 0 for group in groups}
    for group in groups:
        members = sorted(h for h in drawing
                         if holders[h]["settlement_group"] == group)
        if not members:
            continue
        total = sum(as_int(holders[h]["base_quota_frames"]) for h in members)
        quota[group] = total - factor * (len(members) - 1)
    return quota


def drawing_holders(admitted, programmes):
    return sorted({programmes[p]["holder_id"] for p in admitted})


def find_stable_drawing(catalogue, settled):
    """The drawing set that is stable under the quota it produces."""
    holders = catalogue.holder_rows
    programmes = catalogue.programme_rows
    factor = as_int(catalogue.vault_charter["group_draw_factor"])
    groups = sorted({row["settlement_group"] for row in catalogue.holders})
    universe = sorted(holders)

    def admitted_under(drawing):
        quota = group_quota(holders, groups, factor, drawing)
        admitted, _, _ = draw(catalogue, settled, quota)
        return admitted

    def is_stable(drawing):
        admitted = admitted_under(drawing)
        if drawing_holders(admitted, programmes) != sorted(drawing):
            return False
        for holder in universe:
            if holder in drawing:
                continue
            gained = admitted_under(set(drawing) | {holder})
            if holder in drawing_holders(gained, programmes):
                return False
        return True

    drawing = set(universe)
    seen = set()
    while True:
        key = frozenset(drawing)
        if key in seen:
            break
        seen.add(key)
        admitted = admitted_under(drawing)
        drawing = set(drawing_holders(admitted, programmes))
        if not drawing:
            break
    if is_stable(drawing):
        return drawing
    if len(universe) > 20:
        raise RuntimeError("no stable drawing set found by iteration")
    for size in range(len(universe), -1, -1):
        for combo in combinations(universe, size):
            if is_stable(set(combo)):
                return set(combo)
    raise RuntimeError("no stable drawing set settles this cycle")


def draw(catalogue, settled, quota):
    """Each group's programmes draw in descending settled frames; the draw
    closes at the first programme that would take the group past its quota."""
    programmes = catalogue.programme_rows
    holders = catalogue.holder_rows
    admitted, held, order = [], [], []
    for group in sorted(quota):
        members = [p for p in settled
                   if holders[programmes[p]["holder_id"]]["settlement_group"] == group]
        members.sort(key=lambda p: (-settled[p]["settled_frames"], p))
        used = 0
        closed = False
        for programme_id in members:
            frames = settled[programme_id]["settled_frames"]
            if closed:
                state = "held"
            elif used + frames > quota[group]:
                closed = True
                state = "held"
            else:
                used += frames
                state = "admitted"
            (admitted if state == "admitted" else held).append(programme_id)
            order.append({"programme_id": programme_id,
                          "holder_id": programmes[programme_id]["holder_id"],
                          "settlement_group": group,
                          "settled_frames": frames, "state": state})
    return admitted, held, order


# --------------------------------------------------------------------- seating

def seat_vaults(vaults, admitted, programmes, catalogue, settled):
    """Backtracking seating: the first complete placement this search reaches."""
    order = sorted(admitted, key=lambda p: (-settled[p]["settled_frames"], p))
    classes = {p: programmes[p]["deliverable_class"] for p in order}
    groups = {p: catalogue.holder_rows[programmes[p]["holder_id"]]["settlement_group"]
              for p in order}
    frames = {p: settled[p]["settled_frames"] for p in order}
    vault_order = sorted(vaults, key=lambda v: (as_int(v["seat_rank"]), v["vault_id"]))
    loads = {v["vault_id"]: 0 for v in vault_order}
    seated = {}

    def place(index, used):
        if index == len(order):
            return True
        programme_id = order[index]
        for vault in vault_order:
            vault_id = vault["vault_id"]
            if classes[programme_id] not in vault["accepts_classes"]:
                continue
            if groups[programme_id] not in vault["settlement_groups"]:
                continue
            if used[vault_id] + frames[programme_id] > as_int(vault["capacity_frames"]):
                continue
            used[vault_id] += frames[programme_id]
            seated[programme_id] = vault_id
            if place(index + 1, used):
                return True
            used[vault_id] -= frames[programme_id]
            del seated[programme_id]
        return False

    if not place(0, dict(loads)):
        raise RuntimeError("no complete vault seating exists for this cycle")
    return seated


def seat_lanes(lanes, held, catalogue, programmes, settled, residual_pool):
    """Lanes draw on the residual pool in ascending rank and take what fits."""
    order = sorted(held, key=lambda p: (-settled[p]["settled_frames"], p))
    remaining = list(order)
    pool = residual_pool
    lane_reports = {}
    for lane in sorted(lanes, key=lambda l: (as_int(l["lane_rank"]), l["lane_id"])):
        capacity = (pool * as_int(lane["residual_share_num"])) // as_int(lane["residual_share_den"])
        load = 0
        taken = []
        for programme_id in remaining:
            frames = settled[programme_id]["settled_frames"]
            cls = programmes[programme_id]["deliverable_class"]
            group = catalogue.holder_rows[programmes[programme_id]["holder_id"]]["settlement_group"]
            if cls not in lane["accepts_classes"] or group not in lane["settlement_groups"]:
                continue
            if load + frames > capacity:
                continue
            load += frames
            taken.append(programme_id)
        for programme_id in taken:
            remaining.remove(programme_id)
        pool -= load
        lane_reports[lane["lane_id"]] = {"load": load, "programmes": taken,
                                         "capacity": capacity}
    return lane_reports, remaining


# ------------------------------------------------------------------- documents

def write_json(path, document):
    with open(path, "w") as handle:
        handle.write(json.dumps(document, sort_keys=True, indent=2))
        handle.write("\n")


def build_documents(catalogue, out_directory):
    identity = resolve_identity(catalogue)
    spans = element_usable_spans(catalogue, identity)
    conformed = conform_programmes(catalogue, identity, spans)
    programmes = catalogue.programme_rows
    holders = catalogue.holder_rows

    conformed_ids = sorted(p for p, r in conformed.items() if r["state"] == "conformed")
    voided_ids = sorted(p for p, r in conformed.items() if r["state"] == "void")

    findings = clip_defects(catalogue, conformed)
    impaired = impaired_frames(findings, conformed)
    windows = {p: as_int(row["window_close_cycle"]) for p, row in programmes.items()}
    repairs, recovered = work_repairs(catalogue, findings, impaired, windows)
    settled = settle_cycle(catalogue, conformed, impaired, recovered)

    # allocation -----------------------------------------------------------
    factor = as_int(catalogue.vault_charter["group_draw_factor"])
    groups = sorted({row["settlement_group"] for row in catalogue.holders})
    drawing = find_stable_drawing(catalogue, settled)
    quota = group_quota(holders, groups, factor, drawing)
    admitted, held, draw_order = draw(catalogue, settled, quota)
    used = {group: 0 for group in groups}
    for row in draw_order:
        if row["state"] == "admitted":
            used[row["settlement_group"]] += row["settled_frames"]

    # seating --------------------------------------------------------------
    vaults = catalogue.vault_charter["vaults"]
    lanes = catalogue.lane_charter["lanes"]
    vault_of = seat_vaults(vaults, admitted, programmes, catalogue, settled)
    vault_load = {v["vault_id"]: 0 for v in vaults}
    for programme_id, vault_id in vault_of.items():
        vault_load[vault_id] += settled[programme_id]["settled_frames"]
    residual_pool = sum(as_int(v["capacity_frames"]) - vault_load[v["vault_id"]]
                        for v in vaults)
    lane_reports, shed = seat_lanes(lanes, held, catalogue, programmes,
                                    settled, residual_pool)

    documents = {}

    # summary --------------------------------------------------------------
    admitted_frames = sum(settled[p]["settled_frames"] for p in admitted)
    held_frames = sum(settled[p]["settled_frames"] for p in held)
    shed_frames = sum(settled[p]["settled_frames"] for p in shed)
    lane_frames = sum(report["load"] for report in lane_reports.values())
    documents["summary.json"] = {
        "admitted_count": len(admitted),
        "admitted_frames": admitted_frames,
        "conformed_programme_count": len(conformed_ids),
        "held_count": len(held),
        "held_frames": held_frames,
        "impaired_total": sum(impaired.values()),
        "lane_frames": lane_frames,
        "lane_seated_count": sum(len(r["programmes"]) for r in lane_reports.values()),
        "recovered_total": sum(recovered.values()),
        "settled_total": admitted_frames + held_frames,
        "settlement_cycle": catalogue.cycle,
        "shed_count": len(shed),
        "shed_frames": shed_frames,
        "void_programme_count": len(voided_ids),
    }

    # reconciliation --------------------------------------------------------
    stage_names = ["conform", "impairment", "admission", "seating", "cascade"]
    left = {
        "conform": len(conformed),
        "impairment": sum(impaired.values()),
        "admission": admitted_frames + held_frames,
        "seating": admitted_frames,
        "cascade": held_frames,
    }
    right = {
        "conform": len(conformed_ids) + len(voided_ids),
        "impairment": sum(recovered.values()) + sum(
            impaired[p] - recovered[p] for p in impaired),
        "admission": admitted_frames + held_frames,
        "seating": sum(vault_load.values()),
        "cascade": lane_frames + shed_frames,
    }
    stages = []
    for name in stage_names:
        residual = left[name] - right[name]
        stages.append({"stage": name, "left": left[name], "right": right[name],
                       "residual": residual, "closes": residual == 0})
    documents["reconciliation.json"] = {
        "settled_total": admitted_frames + held_frames,
        "stages": stages,
        "residual": sum(abs(s["residual"]) for s in stages),
        "vault_and_lane_total": sum(vault_load.values()) + lane_frames,
    }

    # reel audit -----------------------------------------------------------
    scans = catalogue.scans
    reels = []
    for reel_id in sorted(scans):
        canonical, shift, state = identity[reel_id]
        if state == "retired":
            row_state = "retired"
        elif canonical == reel_id:
            row_state = "live"
        else:
            row_state = "folded"
        reels.append({
            "reel_id": reel_id, "canonical_id": canonical, "state": row_state,
            "element_class": scans[reel_id]["element_class"],
            "registration_shift": shift,
            "scan_cadence_mhz": as_int(scans[reel_id]["scan_cadence_mhz"]),
            "scanned_frames": as_int(scans[reel_id]["scanned_frames"]),
        })
    canonical_elements = sorted(r["reel_id"] for r in reels if r["state"] == "live")
    retired_elements = sorted({r["canonical_id"] for r in reels if r["state"] == "retired"})
    folded_elements = {}
    for row in reels:
        if row["state"] == "folded":
            folded_elements.setdefault(row["canonical_id"], []).append(row["reel_id"])
    folded_elements = {k: sorted(v) for k, v in sorted(folded_elements.items())}
    usable_frames = {element: spans[element][1] - spans[element][0]
                     for element in sorted(spans)}
    documents["reel_audit.json"] = {
        "settlement_cycle": catalogue.cycle,
        "reels": reels,
        "canonical_elements": canonical_elements,
        "retired_elements": retired_elements,
        "folded_elements": folded_elements,
        "usable_frames": usable_frames,
    }

    # conform report -------------------------------------------------------
    programme_rows = []
    for programme_id in sorted(conformed):
        report = conformed[programme_id]
        row = {"programme_id": programme_id, "state": report["state"],
               "conformed_frames": report["conformed_frames"],
               "shot_count": report["shot_count"], "shots": []}
        if report["state"] == "void":
            row["reason"] = report["reason"]
        for shot in report["shots"]:
            row["shots"].append({
                "shot_ordinal": shot["shot_ordinal"],
                "source_reel_id": shot["source_reel_id"],
                "canonical_id": shot["canonical_id"],
                "element_first_frame": shot["element_first_frame"],
                "element_after_last_frame": shot["element_after_last_frame"],
                "frames": shot["frames"],
                "timeline_start": shot["timeline_start"],
                "timeline_stop": shot["timeline_stop"],
                "transition": shot["transition"],
            })
        programme_rows.append(row)
    documents["conform_report.json"] = {
        "conformed_programmes": conformed_ids,
        "void_programmes": voided_ids,
        "programmes": programme_rows,
    }

    # defect findings ------------------------------------------------------
    documents["defect_findings.json"] = {
        "defects": [{
            "defect_id": f["defect_id"], "programme_id": f["programme_id"],
            "shot_ordinal": f["shot_ordinal"], "defect_class": f["defect_class"],
            "severity": f["severity"], "detected_stage": f["detected_stage"],
            "timeline_start": f["timeline_start"], "timeline_stop": f["timeline_stop"],
            "clipped_frames": f["clipped_frames"],
            "recovered_frames": sum(r["recovered_frames"] for r in repairs
                                    if r["defect_id"] == f["defect_id"]),
        } for f in findings],
        "impaired_frames": {p: impaired[p] for p in conformed_ids},
        "impaired_total": sum(impaired.values()),
    }

    # repair ledger --------------------------------------------------------
    state_counts = {}
    for repair in repairs:
        state_counts[repair["state"]] = state_counts.get(repair["state"], 0) + 1
    documents["repair_ledger.json"] = {
        "repairs": repairs,
        "state_counts": {k: state_counts[k] for k in sorted(state_counts)},
        "recovered_frames": {p: recovered[p] for p in conformed_ids},
        "recovered_total": sum(recovered.values()),
    }

    # cadence ledger -------------------------------------------------------
    cadence_rows = []
    for programme_id in conformed_ids:
        entry = settled[programme_id]
        cadence_rows.append({
            "programme_id": programme_id,
            "governing_element": entry["governing_element"],
            "element_cadence_mhz": entry["element_cadence_mhz"],
            "delivery_cadence_mhz": entry["delivery_cadence_mhz"],
            "source_frames": entry["source_frames"],
            "cadence_frames": entry["cadence_frames"],
            "impaired_frames": entry["impaired_frames"],
            "recovered_frames": entry["recovered_frames"],
            "unrecovered_frames": entry["unrecovered_frames"],
            "settled_frames": entry["settled_frames"],
            "condition_grade": entry["condition_grade"],
        })
    documents["cadence_ledger.json"] = {
        "programmes": cadence_rows,
        "source_total": sum(r["source_frames"] for r in cadence_rows),
        "cadence_total": sum(r["cadence_frames"] for r in cadence_rows),
        "settled_total": sum(r["settled_frames"] for r in cadence_rows),
    }

    # allocation ledger ----------------------------------------------------
    documents["allocation_ledger.json"] = {
        "draw_order": draw_order,
        "admitted": sorted(admitted),
        "held": sorted(held),
        "drawing_holders": sorted(drawing),
        "group_quota": {g: quota[g] for g in sorted(quota)},
        "group_used": {g: used.get(g, 0) for g in sorted(quota)},
    }

    # vault index ----------------------------------------------------------
    vault_rows = []
    for vault in sorted(vaults, key=lambda v: (as_int(v["seat_rank"]), v["vault_id"])):
        capacity = as_int(vault["capacity_frames"])
        load = vault_load[vault["vault_id"]]
        vault_rows.append({
            "vault_id": vault["vault_id"], "seat_rank": as_int(vault["seat_rank"]),
            "capacity_frames": capacity, "load_frames": load,
            "headroom_frames": capacity - load,
            "programme_count": sum(1 for p in vault_of if vault_of[p] == vault["vault_id"]),
        })
    documents["vault_index.json"] = {
        "vaults": vault_rows,
        "seated_total_frames": sum(vault_load.values()),
        "residual_pool_frames": residual_pool,
    }

    # one document per vault, one per lane ---------------------------------
    for vault in sorted(vaults, key=lambda v: (as_int(v["seat_rank"]), v["vault_id"])):
        vault_id = vault["vault_id"]
        capacity = as_int(vault["capacity_frames"])
        members = sorted((p for p in admitted if vault_of.get(p) == vault_id),
                         key=lambda p: (-settled[p]["settled_frames"], p))
        documents["vault_%s.json" % vault_id] = {
            "vault_id": vault_id,
            "seat_rank": as_int(vault["seat_rank"]),
            "accepts_classes": sorted(vault["accepts_classes"]),
            "settlement_groups": sorted(vault["settlement_groups"]),
            "capacity_frames": capacity,
            "load_frames": sum(settled[p]["settled_frames"] for p in members),
            "headroom_frames": capacity - sum(settled[p]["settled_frames"] for p in members),
            "programmes": [{
                "programme_id": p,
                "title_key": programmes[p]["title_key"],
                "holder_id": programmes[p]["holder_id"],
                "settlement_group": holders[programmes[p]["holder_id"]]["settlement_group"],
                "deliverable_class": programmes[p]["deliverable_class"],
                "condition_grade": settled[p]["condition_grade"],
                "settled_frames": settled[p]["settled_frames"],
            } for p in members],
        }
    for lane in sorted(lanes, key=lambda l: (as_int(l["lane_rank"]), l["lane_id"])):
        lane_id = lane["lane_id"]
        report = lane_reports[lane_id]
        members = sorted(report["programmes"],
                         key=lambda p: (-settled[p]["settled_frames"], p))
        documents["lane_%s.json" % lane_id] = {
            "lane_id": lane_id,
            "lane_rank": as_int(lane["lane_rank"]),
            "accepts_classes": sorted(lane["accepts_classes"]),
            "settlement_groups": sorted(lane["settlement_groups"]),
            "capacity_frames": report["capacity"],
            "load_frames": report["load"],
            "headroom_frames": report["capacity"] - report["load"],
            "programmes": [{
                "programme_id": p,
                "title_key": programmes[p]["title_key"],
                "holder_id": programmes[p]["holder_id"],
                "settlement_group": holders[programmes[p]["holder_id"]]["settlement_group"],
                "deliverable_class": programmes[p]["deliverable_class"],
                "condition_grade": settled[p]["condition_grade"],
                "settled_frames": settled[p]["settled_frames"],
            } for p in members],
        }

    os.makedirs(out_directory, exist_ok=True)
    for name, document in sorted(documents.items()):
        write_json(os.path.join(out_directory, name), document)
    return documents


def main(argv):
    if len(argv) != 3:
        sys.stderr.write("usage: cadence_settle.py <catalogue dir> <output dir>\n")
        return 2
    catalogue = Catalogue(argv[1])
    build_documents(catalogue, argv[2])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
