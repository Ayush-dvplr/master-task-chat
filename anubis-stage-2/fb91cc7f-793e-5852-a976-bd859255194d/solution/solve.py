"""Restoration cadence settlement.

Reads a restoration catalogue directory and writes the settlement reports for
the cycle that catalogue declares. Standard library only. Deterministic.

An independent settlement engine authored against the shipped rulebooks, the
invariants and the published calibration cycle. The three standing house
conventions (frame quantisation, operator composition order, repair ceiling
carry fraction) are constants; they hold for every cycle this lab settles and
were recovered once from the calibration slice.
"""

from __future__ import annotations

import csv
import json
import os
import sys

# --------------------------------------------------------------------------- #
# standing house conventions (recovered from the published calibration cycle)
# --------------------------------------------------------------------------- #

QUANTISER = "half_even"                       # ties to even, banker's rounding
OPERATOR_ORDER = ("impair", "cadence", "credit")
CEILING_CARRY = (3, 5)                         # three fifths carries per pass

BAND_FLOORS = (("A", 95), ("B", 85), ("C", 70), ("D", 0))
CREDIT_RATE = {"A": (1, 1), "B": (3, 4), "C": (1, 2), "D": (1, 4)}

PHOTOCHEMICAL = frozenset({"negative", "interpositive", "print"})

SOURCE_FILES = {
    "reels": ("reel_scans.csv", False),
    "lineage": ("lineage_events.csv", False),
    "cuts": ("cut_list.csv", False),
    "programmes": ("programmes.csv", False),
    "defects": ("defect_log.csv", False),
    "repairs": ("repair_log.csv", False),
    "holders": ("holders.csv", False),
    "vaults": ("vault_charter.json", True),
    "lanes": ("lane_charter.json", True),
}

# report field orders (projected out of the working records)
SHOT_FIELDS = (
    "canonical_id", "element_after_last_frame", "element_first_frame", "frames",
    "shot_ordinal", "source_reel_id", "timeline_start", "timeline_stop", "transition",
)
REEL_FIELDS = (
    "canonical_id", "element_class", "registration_shift", "reel_id",
    "scan_cadence_mhz", "scanned_frames", "state",
)
FINDING_FIELDS = (
    "clipped_frames", "defect_class", "defect_id", "detected_stage", "programme_id",
    "recovered_frames", "severity", "shot_ordinal", "timeline_start", "timeline_stop",
)
REPAIR_FIELDS = (
    "claimed_frames", "defect_id", "pass_index", "programme_id",
    "recovered_frames", "repair_id", "state",
)
CADENCE_FIELDS = (
    "cadence_frames", "condition_grade", "delivery_cadence_mhz", "element_cadence_mhz",
    "governing_element", "impaired_frames", "programme_id", "recovered_frames",
    "settled_frames", "source_frames", "unrecovered_frames",
)
DRAW_FIELDS = ("holder_id", "programme_id", "settled_frames", "settlement_group", "state")
STORED_FIELDS = (
    "condition_grade", "deliverable_class", "holder_id", "programme_id",
    "settled_frames", "settlement_group", "title_key",
)


def project(record: dict, fields) -> dict:
    """Copy exactly the named fields out of a working record."""
    return {name: record[name] for name in fields}


def to_whole(top: int, bottom: int, mode: str = QUANTISER) -> int:
    """Reduce top/bottom to a whole frame under the named convention.

    Rounds the magnitude and re-attaches the sign, so negative inputs round
    symmetrically.
    """
    if bottom <= 0:
        raise ValueError("bottom must be above zero")
    flip = top < 0
    amount = -top if flip else top
    quot, rem = divmod(amount, bottom)
    if mode == "floor":
        stepped = quot + (1 if (rem and flip) else 0)
    elif mode == "ceil":
        stepped = quot + (1 if (rem and not flip) else 0)
    else:
        twice = rem + rem
        bump = twice > bottom or (twice == bottom and (mode == "half_up" or quot & 1))
        stepped = quot + (1 if bump else 0)
    return -stepped if flip else stepped


def _rows(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return [dict(entry) for entry in csv.DictReader(fh)]


def _doc(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_catalogue(root: str) -> dict:
    book = {}
    for key, (filename, is_json) in SOURCE_FILES.items():
        where = os.path.join(root, filename)
        book[key] = _doc(where) if is_json else _rows(where)
    return book


def coalesce(pieces):
    """Collapse half-open [a, b) intervals into a minimal disjoint cover."""
    stack = []
    for lo, hi in sorted(pieces):
        if stack and lo <= stack[-1][1]:
            prev = stack[-1]
            stack[-1] = (prev[0], max(prev[1], hi))
        else:
            stack.append((lo, hi))
    return stack


def spanned(pieces) -> int:
    return sum(hi - lo for lo, hi in coalesce(pieces))


# --------------------------------------------------------------------------- #
# stage 1 - identity resolution
# --------------------------------------------------------------------------- #


def resolve_identity(reels, lineage, cycle) -> dict:
    labels = sorted(scan["reel_id"] for scan in reels)
    upstream = {name: name for name in labels}
    hop = {name: 0 for name in labels}
    gone = set()
    folded_ids = []

    for event in sorted(lineage, key=lambda e: (int(e["effective_cycle"]), e["event_id"])):
        when = int(event["effective_cycle"])
        act = event["kind"]
        subject = event["from_reel"]
        toward = event["to_reel"]
        if act == "retire":
            if when <= cycle:
                gone.add(subject)
            continue
        if when > cycle:
            continue
        if subject not in upstream or (toward and toward not in upstream):
            raise ValueError("lineage points at an unknown reel: " + subject)
        if act not in ("alias", "merge", "supersede"):
            raise ValueError("unrecognised lineage kind: " + act)
        upstream[subject] = toward
        hop[subject] = int(event["registration_offset"] or 0)
        folded_ids.append(subject)

    def chase(name):
        trail = set()
        drift = 0
        node = name
        while upstream[node] != node:
            if node in trail:
                raise ValueError("identity loop at " + node)
            trail.add(node)
            drift += hop[node]
            node = upstream[node]
        return node, drift

    home = {}
    offset = {}
    for name in labels:
        settle_to, drift = chase(name)
        home[name] = settle_to
        offset[name] = drift

    absorbed = {}
    for name in sorted(folded_ids):
        absorbed.setdefault(home[name], []).append(name)

    standing = sorted({home[n] for n in labels if home[n] not in gone})
    return {
        "canonical": home,
        "shift": offset,
        "retired": sorted(gone),
        "folded": absorbed,
        "live": standing,
    }


# --------------------------------------------------------------------------- #
# stage 2 - usable span per canonical element
# --------------------------------------------------------------------------- #


def measure_spans(reels, identity) -> dict:
    catalogue = {scan["reel_id"]: scan for scan in reels}
    per_reel = {}
    for name in sorted(catalogue):
        scan = catalogue[name]
        total = int(scan["scanned_frames"])
        if scan["element_class"] in PHOTOCHEMICAL:
            opening = int(scan["head_leader"])
            closing = total - int(scan["tail_leader"])
        else:
            opening, closing = 0, total
        if closing <= opening:
            raise ValueError("reel " + name + " carries no usable picture")
        per_reel[name] = (opening, closing)

    pooled = {}
    for name in sorted(catalogue):
        target = identity["canonical"][name]
        if target in identity["retired"]:
            continue
        drift = identity["shift"][name]
        opening, closing = per_reel[name]
        pooled.setdefault(target, []).append((opening + drift, closing + drift))

    unioned = {target: coalesce(pieces) for target, pieces in sorted(pooled.items())}
    return {"raw": per_reel, "canonical": unioned}


# --------------------------------------------------------------------------- #
# stages 3 and 4 - conform and void
# --------------------------------------------------------------------------- #


def build_timelines(cuts, programmes, identity, spans) -> dict:
    bucket = {}
    for cut in cuts:
        bucket.setdefault(cut["programme_id"], []).append(cut)

    laid = {}
    voided = {}
    for prog in sorted(p["programme_id"] for p in programmes):
        ordered = sorted(bucket.get(prog, []), key=lambda c: int(c["shot_ordinal"]))
        faults = []
        strip = []
        head_pos = 0
        for cut in ordered:
            reel = cut["reel_id"]
            target = identity["canonical"].get(reel)
            if target is None:
                faults.append("unknown element")
                continue
            if target in identity["retired"]:
                faults.append("retired element")
                continue
            drift = identity["shift"][reel]
            opening = int(cut["in_frame"]) + drift
            closing = int(cut["out_frame"]) + drift
            if closing <= opening:
                faults.append("empty shot")
                continue
            within = any(a <= opening and closing <= b for a, b in spans["canonical"].get(target, []))
            if not within:
                faults.append("shot leaves the usable span")
                continue
            reach = closing - opening
            strip.append(
                {
                    "shot_ordinal": int(cut["shot_ordinal"]),
                    "canonical_id": target,
                    "source_reel_id": reel,
                    "element_first_frame": opening,
                    "element_after_last_frame": closing,
                    "frames": reach,
                    "timeline_start": head_pos,
                    "timeline_stop": head_pos + reach,
                    "transition": cut["transition"],
                }
            )
            head_pos += reach

        marks = [int(c["shot_ordinal"]) for c in ordered]
        if marks != list(range(1, len(marks) + 1)):
            faults.append("shot ordinals do not tile")
        if not ordered:
            faults.append("no shots")

        laid[prog] = strip
        if faults:
            voided[prog] = sorted(set(faults))

    return {"shots": laid, "voids": voided}


# --------------------------------------------------------------------------- #
# stage 5 - governing element
# --------------------------------------------------------------------------- #


def elect_governor(strip, reels) -> str:
    catalogue = {scan["reel_id"]: scan for scan in reels}
    weight = {}
    for shot in strip:
        weight[shot["canonical_id"]] = weight.get(shot["canonical_id"], 0) + shot["frames"]
    if not weight:
        raise ValueError("programme carries no shots")
    ladder = sorted(weight.items(), key=lambda kv: (-kv[1], kv[0]))
    for candidate, _reach in ladder:
        scan = catalogue.get(candidate)
        if scan is not None and scan["element_class"] != "print":
            return candidate
    return ladder[0][0]


# --------------------------------------------------------------------------- #
# stage 7 - impairment as a union
# --------------------------------------------------------------------------- #


def accrue_impairment(defects, programmes, plan) -> dict:
    intact = {p["programme_id"] for p in programmes if p["programme_id"] not in plan["voids"]}
    stacked = {}
    clipped = {}
    for flaw in sorted(defects, key=lambda d: d["defect_id"]):
        prog = flaw["programme_id"]
        if prog not in intact:
            continue
        mark = int(flaw["shot_ordinal"])
        host = next((s for s in plan["shots"][prog] if s["shot_ordinal"] == mark), None)
        if host is None:
            continue
        opens = int(flaw["span_start"])
        shuts = max(opens, int(flaw["span_end"]))
        first = host["timeline_start"]
        after_last = host["timeline_stop"]
        # Both ends move into the host shot, so a defect that misses it clips to zero length and keeps its row.
        low = min(max(opens, first), after_last)
        high = min(max(shuts, first), after_last)
        clipped[flaw["defect_id"]] = {
            "defect_id": flaw["defect_id"],
            "programme_id": prog,
            "shot_ordinal": mark,
            "defect_class": flaw["defect_class"],
            "severity": int(flaw["severity"]),
            "detected_stage": flaw["detected_stage"],
            "timeline_start": low,
            "timeline_stop": high,
            "clipped_frames": high - low,
        }
        if high > low:
            stacked.setdefault(prog, []).append((low, high))

    hurt = {prog: spanned(pieces) for prog, pieces in stacked.items()}
    for prog in intact:
        hurt.setdefault(prog, 0)
    return {"per_defect": clipped, "impaired": hurt}


# --------------------------------------------------------------------------- #
# stage 8 - repair adjudication under the decaying ceiling
# --------------------------------------------------------------------------- #


def adjudicate_repairs(fixes, per_defect, programmes, carry, impaired) -> dict:
    deadline = {p["programme_id"]: int(p["window_close_cycle"]) for p in programmes}
    grouped = {}
    for fix in fixes:
        seen = per_defect.get(fix["defect_id"])
        if seen is None:
            continue
        grouped.setdefault(seen["programme_id"], []).append(fix)

    ledger = []
    won_by_defect = {flaw_id: 0 for flaw_id in per_defect}
    won_by_prog = {}
    top, bot = carry

    for prog in sorted(grouped):
        queue = sorted(grouped[prog], key=lambda f: (int(f["pass_index"]), f["repair_id"]))
        limit = {}
        remaining = {}
        depth = {}
        for flaw_id, seen in per_defect.items():
            if seen["programme_id"] == prog:
                limit[flaw_id] = seen["clipped_frames"]
                remaining[flaw_id] = seen["clipped_frames"]
                depth[flaw_id] = 0
        purse = impaired.get(prog, 0)

        for fix in queue:
            flaw_id = fix["defect_id"]
            seen = per_defect[flaw_id]
            depth[flaw_id] += 1
            if depth[flaw_id] > 1:
                limit[flaw_id] = limit[flaw_id] * top // bot
            asked = int(fix["claimed_frames"])
            grade_class = int(fix["node_class"])
            if int(fix["submitted_cycle"]) > deadline.get(prog, -1):
                outcome = "outside the repair window"
                given = 0
            elif grade_class < seen["severity"]:
                outcome = "node class below defect severity"
                given = 0
            else:
                given = min(asked, limit[flaw_id], remaining[flaw_id], purse)
                outcome = "accepted" if given == asked else "clamped"
            remaining[flaw_id] -= given
            purse -= given
            won_by_defect[flaw_id] += given
            won_by_prog[prog] = won_by_prog.get(prog, 0) + given
            ledger.append(
                {
                    "repair_id": fix["repair_id"],
                    "defect_id": flaw_id,
                    "programme_id": prog,
                    "pass_index": int(fix["pass_index"]),
                    "claimed_frames": asked,
                    "recovered_frames": given,
                    "state": outcome,
                }
            )

    ledger.sort(key=lambda e: (e["programme_id"], e["defect_id"], e["pass_index"], e["repair_id"]))
    return {"ledger": ledger, "by_defect": won_by_defect, "by_programme": won_by_prog}


# --------------------------------------------------------------------------- #
# stages 6 and 9 - cadence conversion and the condition grade fixpoint
# --------------------------------------------------------------------------- #


def grade_for(count, reference) -> str:
    if reference <= 0:
        return "D"
    for band, floor in BAND_FLOORS:
        if count * 100 >= reference * floor:
            return band
    return "D"


def fold_operators(base, missing, mended, band, ratio) -> int:
    up, down = ratio
    cnum, cden = CREDIT_RATE[band]
    tally = base
    scaled = False
    for step in OPERATOR_ORDER:
        if step == "cadence":
            tally = to_whole(tally * up, down)
            scaled = True
        elif step == "impair":
            loss = to_whole(missing * up, down) if scaled else missing
            tally -= loss
        else:
            gain = to_whole(mended * cnum, cden)
            if scaled:
                gain = to_whole(gain * up, down)
            tally += gain
    return tally


def settle_cadence(programmes, reels, plan, imp, rep, group_of) -> dict:
    catalogue = {scan["reel_id"]: scan for scan in reels}
    ruled = {}
    for entry in sorted(programmes, key=lambda p: p["programme_id"]):
        prog = entry["programme_id"]
        if prog in plan["voids"]:
            continue
        strip = plan["shots"][prog]
        governor = elect_governor(strip, reels)
        governor_mhz = int(catalogue[governor]["scan_cadence_mhz"])
        contract_mhz = int(entry["delivery_cadence_mhz"])
        ratio = (contract_mhz, governor_mhz)
        base = sum(shot["frames"] for shot in strip)
        hurt = imp["impaired"].get(prog, 0)
        mended = rep["by_programme"].get(prog, 0)
        missing = hurt - mended
        reference = to_whole(base * contract_mhz, governor_mhz)

        winner = None
        for band, _floor in BAND_FLOORS:
            trial = fold_operators(base, missing, mended, band, ratio)
            if grade_for(trial, reference) == band:
                if winner is None:
                    winner = (band, trial)
                    break
        if winner is None:
            raise ValueError("no stable grade for " + prog)
        band, count = winner

        ruled[prog] = {
            "programme_id": prog,
            "title_key": entry["title_key"],
            "holder_id": entry["holder_id"],
            "settlement_group": group_of[entry["holder_id"]],
            "deliverable_class": entry["deliverable_class"],
            "governing_element": governor,
            "element_cadence_mhz": governor_mhz,
            "delivery_cadence_mhz": contract_mhz,
            "source_frames": base,
            "cadence_frames": reference,
            "impaired_frames": hurt,
            "recovered_frames": mended,
            "unrecovered_frames": missing,
            "condition_grade": band,
            "settled_frames": count,
        }
    return ruled


# --------------------------------------------------------------------------- #
# stage 10 - admission draw with the drawing-set fixpoint
# --------------------------------------------------------------------------- #


def run_admission(ruled, holders, charter) -> dict:
    account = {h["holder_id"]: h for h in holders}
    rebate = int(charter["group_draw_factor"])
    queue = sorted(ruled, key=lambda p: (-ruled[p]["settled_frames"], p))

    roster = {}
    for hid, acct in account.items():
        roster.setdefault(acct["settlement_group"], []).append(hid)

    def sweep(drawing):
        allowance = {}
        for band, members in roster.items():
            active = sorted(h for h in members if h in drawing)
            pot = sum(int(account[h]["base_quota_frames"]) for h in active)
            if active:
                pot -= rebate * (len(active) - 1)
            allowance[band] = max(pot, 0)
        spent = {band: 0 for band in allowance}
        shut = set()
        taken = {}
        for prog in queue:
            band = account[ruled[prog]["holder_id"]]["settlement_group"]
            if band in shut:
                continue
            if spent[band] + ruled[prog]["settled_frames"] <= allowance[band]:
                spent[band] += ruled[prog]["settled_frames"]
                taken[prog] = band
            else:
                shut.add(band)
        return {"quota": allowance, "used": spent, "admitted": taken}, frozenset(
            ruled[p]["holder_id"] for p in taken
        )

    current = frozenset(ruled[p]["holder_id"] for p in ruled)
    for _ in range(64):
        result, following = sweep(current)
        if following == current:
            return {
                "quota": result["quota"],
                "used": result["used"],
                "admitted": sorted(result["admitted"]),
                "held": sorted(p for p in ruled if p not in result["admitted"]),
                "drawing": sorted(current),
                "order": queue,
            }
        current = following
    raise ValueError("the drawing set never settled")


# --------------------------------------------------------------------------- #
# stages 11 and 12 - vault seating and lane cascade
# --------------------------------------------------------------------------- #


def allocate(admitted, ruled, charter, lanes) -> dict:
    bins = sorted(charter["vaults"], key=lambda v: (int(v["seat_rank"]), v["vault_id"]))
    queue = sorted(admitted, key=lambda p: (-ruled[p]["settled_frames"], p))

    def fits(bin_, prog):
        return (
            ruled[prog]["deliverable_class"] in bin_["accepts_classes"]
            and ruled[prog]["settlement_group"] in bin_["settlement_groups"]
        )

    fill = {v["vault_id"]: 0 for v in bins}
    trial = {}
    answer = [None]
    completions = [0]
    cap_out = 4096

    def descend(at):
        if completions[0] >= cap_out:
            return
        if at == len(queue):
            completions[0] += 1
            if answer[0] is None:
                answer[0] = dict(trial)
            return
        prog = queue[at]
        weight = ruled[prog]["settled_frames"]
        for bin_ in bins:
            vid = bin_["vault_id"]
            if not fits(bin_, prog):
                continue
            if fill[vid] + weight > int(bin_["capacity_frames"]):
                continue
            fill[vid] += weight
            trial[prog] = vid
            descend(at + 1)
            del trial[prog]
            fill[vid] -= weight

    descend(0)
    if answer[0] is None:
        raise ValueError("no feasible seating exists")

    seated = answer[0]
    vault_fill = {v["vault_id"]: 0 for v in bins}
    for prog, vid in seated.items():
        vault_fill[vid] += ruled[prog]["settled_frames"]
    spare = sum(int(v["capacity_frames"]) - vault_fill[v["vault_id"]] for v in bins)

    waiting = sorted(p for p in ruled if p not in admitted)
    tracks = sorted(lanes["lanes"], key=lambda t: (int(t["lane_rank"]), t["lane_id"]))
    reservoir = spare
    lane_of = {}
    lane_cap = {}
    for track in tracks:
        room = reservoir * int(track["residual_share_num"]) // int(track["residual_share_den"])
        lane_cap[track["lane_id"]] = room
        drawn = 0
        for prog in sorted(waiting, key=lambda p: (-ruled[p]["settled_frames"], p)):
            if prog in lane_of:
                continue
            if ruled[prog]["deliverable_class"] not in track["accepts_classes"]:
                continue
            if ruled[prog]["settlement_group"] not in track["settlement_groups"]:
                continue
            if drawn + ruled[prog]["settled_frames"] > room:
                continue
            lane_of[prog] = track["lane_id"]
            drawn += ruled[prog]["settled_frames"]
        reservoir -= drawn

    return {
        "seating": seated,
        "vault_load": vault_fill,
        "vault_residual": spare,
        "lane_seating": lane_of,
        "lane_capacity": lane_cap,
        "shed": sorted(p for p in waiting if p not in lane_of),
    }


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #


def settle_cycle(book) -> dict:
    charter = book["vaults"]
    cycle = int(charter["settlement_cycle"])
    group_of = {h["holder_id"]: h["settlement_group"] for h in book["holders"]}
    identity = resolve_identity(book["reels"], book["lineage"], cycle)
    spans = measure_spans(book["reels"], identity)
    plan = build_timelines(book["cuts"], book["programmes"], identity, spans)
    imp = accrue_impairment(book["defects"], book["programmes"], plan)
    rep = adjudicate_repairs(book["repairs"], imp["per_defect"], book["programmes"], CEILING_CARRY, imp["impaired"])
    ruled = settle_cadence(book["programmes"], book["reels"], plan, imp, rep, group_of)
    adm = run_admission(ruled, book["holders"], charter)
    place = allocate(adm["admitted"], ruled, charter, book["lanes"])
    return {
        "cycle": cycle,
        "identity": identity,
        "spans": spans,
        "plan": plan,
        "impairment": imp,
        "repairs": rep,
        "ruled": ruled,
        "admission": adm,
        "placement": place,
        "book": book,
    }


# --------------------------------------------------------------------------- #
# report assembly
# --------------------------------------------------------------------------- #


def assemble_reports(state) -> dict:
    identity = state["identity"]
    plan = state["plan"]
    imp = state["impairment"]
    rep = state["repairs"]
    ruled = state["ruled"]
    adm = state["admission"]
    place = state["placement"]
    book = state["book"]
    charter = book["vaults"]
    tracks = book["lanes"]["lanes"]
    out = {}

    def by_size(names):
        return sorted(names, key=lambda p: (-ruled[p]["settled_frames"], p))

    # reel_audit -------------------------------------------------------------
    fleet = []
    for scan in sorted(book["reels"], key=lambda r: r["reel_id"]):
        name = scan["reel_id"]
        target = identity["canonical"][name]
        if target in identity["retired"] or name in identity["retired"]:
            status = "retired"
        elif name == target:
            status = "live"
        else:
            status = "folded"
        fleet.append(
            {
                "canonical_id": target,
                "element_class": scan["element_class"],
                "registration_shift": identity["shift"][name],
                "reel_id": name,
                "scan_cadence_mhz": int(scan["scan_cadence_mhz"]),
                "scanned_frames": int(scan["scanned_frames"]),
                "state": status,
            }
        )
    out["reel_audit.json"] = {
        "canonical_elements": sorted(identity["live"]),
        "folded_elements": {home: sorted(kids) for home, kids in sorted(identity["folded"].items())},
        "reels": [project(entry, REEL_FIELDS) for entry in fleet],
        "retired_elements": sorted(identity["retired"]),
        "settlement_cycle": state["cycle"],
        "usable_frames": {home: spanned(pieces) for home, pieces in sorted(state["spans"]["canonical"].items())},
    }

    # conform_report ---------------------------------------------------------
    intact = [p for p in sorted(plan["shots"]) if p not in plan["voids"]]
    lines = []
    for prog in intact:
        strip = plan["shots"][prog]
        lines.append(
            {
                "conformed_frames": sum(shot["frames"] for shot in strip),
                "programme_id": prog,
                "shot_count": len(strip),
                "shots": [project(shot, SHOT_FIELDS) for shot in strip],
                "state": "conformed",
            }
        )
    for prog in sorted(plan["voids"]):
        lines.append(
            {
                "conformed_frames": 0,
                "programme_id": prog,
                "reason": plan["voids"][prog],
                "shot_count": 0,
                "shots": [],
                "state": "void",
            }
        )
    lines.sort(key=lambda entry: entry["programme_id"])
    out["conform_report.json"] = {
        "conformed_programmes": intact,
        "programmes": lines,
        "void_programmes": sorted(plan["voids"]),
    }

    # defect_findings --------------------------------------------------------
    findings = []
    for flaw_id in sorted(imp["per_defect"]):
        clip = dict(imp["per_defect"][flaw_id])
        clip["recovered_frames"] = rep["by_defect"].get(flaw_id, 0)
        findings.append(project(clip, FINDING_FIELDS))
    out["defect_findings.json"] = {
        "defects": findings,
        "impaired_frames": {p: imp["impaired"][p] for p in sorted(imp["impaired"])},
        "impaired_total": sum(imp["impaired"].values()),
    }

    # repair_ledger ----------------------------------------------------------
    entries = sorted(
        (project(e, REPAIR_FIELDS) for e in rep["ledger"]),
        key=lambda e: (e["pass_index"], e["repair_id"]),
    )
    tally = {}
    for e in entries:
        tally[e["state"]] = tally.get(e["state"], 0) + 1
    mended = {p: ruled[p]["recovered_frames"] for p in sorted(ruled)}
    out["repair_ledger.json"] = {
        "recovered_frames": mended,
        "recovered_total": sum(mended.values()),
        "repairs": entries,
        "state_counts": {k: tally[k] for k in sorted(tally)},
    }

    # cadence_ledger ---------------------------------------------------------
    ledger = [project(ruled[p], CADENCE_FIELDS) for p in sorted(ruled)]
    out["cadence_ledger.json"] = {
        "cadence_total": sum(e["cadence_frames"] for e in ledger),
        "programmes": ledger,
        "settled_total": sum(e["settled_frames"] for e in ledger),
        "source_total": sum(e["source_frames"] for e in ledger),
    }

    # allocation_ledger ------------------------------------------------------
    picks = []
    for prog in adm["order"]:
        record = dict(ruled[prog])
        record["state"] = "admitted" if prog in adm["admitted"] else "held"
        picks.append(project(record, DRAW_FIELDS))
    out["allocation_ledger.json"] = {
        "admitted": list(adm["admitted"]),
        "draw_order": picks,
        "drawing_holders": list(adm["drawing"]),
        "group_quota": {g: adm["quota"][g] for g in sorted(adm["quota"])},
        "group_used": {g: adm["used"].get(g, 0) for g in sorted(adm["quota"])},
        "held": list(adm["held"]),
    }

    def stored(names):
        return [project(ruled[p], STORED_FIELDS) for p in names]

    # vault_index and per vault ---------------------------------------------
    roll = []
    for bin_ in sorted(charter["vaults"], key=lambda v: int(v["seat_rank"])):
        vid = bin_["vault_id"]
        residents = by_size([p for p, where in place["seating"].items() if where == vid])
        ceiling = int(bin_["capacity_frames"])
        used = place["vault_load"].get(vid, 0)
        roll.append(
            {
                "capacity_frames": ceiling,
                "headroom_frames": ceiling - used,
                "load_frames": used,
                "programme_count": len(residents),
                "seat_rank": int(bin_["seat_rank"]),
                "vault_id": vid,
            }
        )
        out["vault_%s.json" % vid] = {
            "accepts_classes": sorted(bin_["accepts_classes"]),
            "capacity_frames": ceiling,
            "headroom_frames": ceiling - used,
            "load_frames": used,
            "programmes": stored(residents),
            "seat_rank": int(bin_["seat_rank"]),
            "settlement_groups": sorted(bin_["settlement_groups"]),
            "vault_id": vid,
        }
    out["vault_index.json"] = {
        "residual_pool_frames": place["vault_residual"],
        "seated_total_frames": sum(place["vault_load"].values()),
        "vaults": roll,
    }

    # per lane ---------------------------------------------------------------
    for track in sorted(tracks, key=lambda t: int(t["lane_rank"])):
        lid = track["lane_id"]
        residents = by_size([p for p, where in place["lane_seating"].items() if where == lid])
        ceiling = place["lane_capacity"].get(lid, 0)
        used = sum(ruled[p]["settled_frames"] for p in residents)
        out["lane_%s.json" % lid] = {
            "accepts_classes": sorted(track["accepts_classes"]),
            "capacity_frames": ceiling,
            "headroom_frames": ceiling - used,
            "lane_id": lid,
            "lane_rank": int(track["lane_rank"]),
            "load_frames": used,
            "programmes": stored(residents),
            "settlement_groups": sorted(track["settlement_groups"]),
        }

    # summary ----------------------------------------------------------------
    def total(names):
        return sum(ruled[p]["settled_frames"] for p in names)

    admitted_load = total(adm["admitted"])
    held_load = total(adm["held"])
    lane_load = total(place["lane_seating"])
    shed_load = total(place["shed"])
    grand = sum(rec["settled_frames"] for rec in ruled.values())
    out["summary.json"] = {
        "admitted_count": len(adm["admitted"]),
        "admitted_frames": admitted_load,
        "conformed_programme_count": len(ruled),
        "held_count": len(adm["held"]),
        "held_frames": held_load,
        "impaired_total": sum(imp["impaired"].values()),
        "lane_frames": lane_load,
        "lane_seated_count": len(place["lane_seating"]),
        "recovered_total": sum(ruled[p]["recovered_frames"] for p in ruled),
        "settled_total": grand,
        "settlement_cycle": state["cycle"],
        "shed_count": len(place["shed"]),
        "shed_frames": shed_load,
        "void_programme_count": len(plan["voids"]),
    }

    # reconciliation ---------------------------------------------------------
    steps = [
        ("conform", len(book["programmes"]), len(ruled) + len(plan["voids"])),
        (
            "impairment",
            sum(imp["impaired"].values()),
            sum(ruled[p]["recovered_frames"] + ruled[p]["unrecovered_frames"] for p in ruled),
        ),
        ("admission", grand, admitted_load + held_load),
        ("seating", admitted_load, sum(place["vault_load"].values())),
        ("cascade", held_load, lane_load + shed_load),
    ]
    stages = []
    for label, left, right in steps:
        stages.append(
            {
                "closes": left - right == 0,
                "left": left,
                "residual": left - right,
                "right": right,
                "stage": label,
            }
        )
    out["reconciliation.json"] = {
        "residual": sum(abs(row["residual"]) for row in stages),
        "settled_total": grand,
        "stages": stages,
        "vault_and_lane_total": sum(place["vault_load"].values()) + lane_load + shed_load,
    }

    return out


def serialise(payload) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main(argv) -> int:
    if len(argv) != 3:
        sys.stderr.write("usage: cadence_settle.py <catalogue_dir> <output_dir>\n")
        return 2
    catalogue_dir, output_dir = argv[1], argv[2]
    book = load_catalogue(catalogue_dir)
    reports = assemble_reports(settle_cycle(book))
    os.makedirs(output_dir, exist_ok=True)
    for name in sorted(reports):
        with open(os.path.join(output_dir, name), "w", encoding="utf-8", newline="") as fh:
            fh.write(serialise(reports[name]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
