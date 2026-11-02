"""Verifier for the fb91cc7f-793e-5852-a976-bd859255194d.

Carries the reference settlement so delivered reports can be graded
against a catalogue the solver has never seen.
"""

from __future__ import annotations

import hashlib

import csv
import json
import os
import signal
import sys

from rewardkit import criteria, criterion

# ---------------------------------------------------------------------------
# house conventions (withheld from the shipped catalogue)
# ---------------------------------------------------------------------------

TRUE_ROUNDING = "half_even"
TRUE_ORDER = ("impair", "cadence", "credit")
TRUE_DECAY = (3, 5)

ROUNDINGS = ("floor", "ceil", "half_up", "half_even")
ORDERS = (
    ("cadence", "impair", "credit"),
    ("cadence", "credit", "impair"),
    ("impair", "cadence", "credit"),
    ("impair", "credit", "cadence"),
    ("credit", "cadence", "impair"),
    ("credit", "impair", "cadence"),
)
DECAYS = ((1, 2), (1, 3), (2, 3), (1, 4), (3, 4), (2, 5), (3, 5), (4, 5))

GRADE_BANDS = (
    ("A", 95, 100),
    ("B", 85, 100),
    ("C", 70, 100),
    ("D", 0, 100),
)
GRADE_CREDIT = {"A": (1, 1), "B": (3, 4), "C": (1, 2), "D": (1, 4)}
GRADE_ORDER = ("A", "B", "C", "D")

PHOTOCHEMICAL = ("negative", "interpositive", "print")

MAIN_FILES = {
    "reels": "reel_scans.csv",
    "lineage": "lineage_events.csv",
    "cuts": "cut_list.csv",
    "programmes": "programmes.csv",
    "defects": "defect_log.csv",
    "repairs": "repair_log.csv",
    "holders": "holders.csv",
    "vaults": "vault_charter.json",
    "lanes": "lane_charter.json",
}


def quantise(numerator: int, denominator: int, mode: str) -> int:
    """Divide numerator by denominator under the named convention."""
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    negative = numerator < 0
    value = -numerator if negative else numerator
    whole, rest = divmod(value, denominator)
    if mode == "floor":
        out = whole if not negative else whole + (1 if rest else 0)
        return -out if negative else out
    if mode == "ceil":
        out = whole + (1 if rest else 0) if not negative else whole
        return -out if negative else out
    twice = rest * 2
    if twice > denominator:
        whole += 1
    elif twice == denominator:
        if mode == "half_up":
            whole += 1
        elif whole % 2 == 1:
            whole += 1
    return -whole if negative else whole


def read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def read_json(path: str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def load_corpus(root: str, prefix: str = "") -> dict:
    data = {}
    for key, name in MAIN_FILES.items():
        path = os.path.join(root, prefix + name)
        data[key] = read_json(path) if name.endswith(".json") else read_csv(path)
    return data


# ---------------------------------------------------------------------------
# stage 1 - canonical identity
# ---------------------------------------------------------------------------


def canonicalise(reels: list[dict], lineage: list[dict], cycle: int) -> dict:
    ids = sorted(r["reel_id"] for r in reels)
    events = sorted(
        lineage,
        key=lambda e: (int(e["effective_cycle"]), e["event_id"]),
    )
    parent = {rid: rid for rid in ids}
    offset = {rid: 0 for rid in ids}
    retired = set()
    merges = []

    def resolve(rid: str) -> tuple[str, int]:
        seen = set()
        shift = 0
        cur = rid
        while parent.get(cur, cur) != cur:
            if cur in seen:
                raise ValueError("identity cycle at " + cur)
            seen.add(cur)
            shift += offset.get(cur, 0)
            cur = parent[cur]
        return cur, shift

    for event in events:
        kind = event["kind"]
        effective = int(event["effective_cycle"])
        src = event["from_reel"]
        dst = event["to_reel"]
        shift = int(event["registration_offset"] or 0)
        if kind == "retire":
            if effective <= cycle:
                retired.add(src)
            continue
        if effective > cycle:
            continue
        if src not in parent or (dst and dst not in parent):
            raise ValueError("lineage references an unknown element")
        if kind in ("alias", "supersede", "merge"):
            parent[src] = dst
            offset[src] = shift
            merges.append(src)
        else:
            raise ValueError("unknown lineage kind " + kind)

    canon = {}
    shift_of = {}
    for rid in ids:
        target, shift = resolve(rid)
        canon[rid] = target
        shift_of[rid] = shift
    folded = {}
    for src in sorted(merges):
        folded.setdefault(canon[src], []).append(src)
    live = sorted({canon[r] for r in ids if canon[r] not in retired})
    return {
        "canonical": canon,
        "shift": shift_of,
        "retired": sorted(retired),
        "folded": folded,
        "live": live,
    }


# ---------------------------------------------------------------------------
# stage 2 - usable span per canonical element
# ---------------------------------------------------------------------------


def usable_spans(reels: list[dict], identity: dict) -> dict:
    by_id = {r["reel_id"]: r for r in reels}
    spans = {}
    for rid in sorted(by_id):
        row = by_id[rid]
        scanned = int(row["scanned_frames"])
        head = int(row["head_leader"])
        tail = int(row["tail_leader"])
        if row["element_class"] in PHOTOCHEMICAL:
            first = head
            last = scanned - tail
        else:
            first = 0
            last = scanned
        if last <= first:
            raise ValueError("element " + rid + " has no usable span")
        spans[rid] = (first, last)

    target = {}
    for rid in sorted(by_id):
        canon = identity["canonical"][rid]
        if canon in identity["retired"]:
            continue
        shift = identity["shift"][rid]
        first, last = spans[rid]
        moved = (first + shift, last + shift)
        if canon not in target:
            target[canon] = [moved]
        else:
            target[canon].append(moved)

    merged = {}
    for canon in sorted(target):
        pieces = sorted(target[canon])
        out = []
        for piece in pieces:
            if out and piece[0] <= out[-1][1]:
                out[-1] = (out[-1][0], max(out[-1][1], piece[1]))
            else:
                out.append(piece)
        merged[canon] = [tuple(p) for p in out]
    return {"raw": spans, "canonical": merged}


# ---------------------------------------------------------------------------
# stage 3 and 4 - conform
# ---------------------------------------------------------------------------


def conform(cuts: list[dict], programmes: list[dict], identity: dict, spans: dict) -> dict:
    by_programme = {}
    for row in cuts:
        by_programme.setdefault(row["programme_id"], []).append(row)

    shots = {}
    voids = {}
    for pid in sorted(p["programme_id"] for p in programmes):
        rows = sorted(
            by_programme.get(pid, []),
            key=lambda r: int(r["shot_ordinal"]),
        )
        reasons = []
        placed = []
        cursor = 0
        for row in rows:
            reel = row["reel_id"]
            canon = identity["canonical"].get(reel)
            if canon is None:
                reasons.append("unknown element")
                continue
            if canon in identity["retired"]:
                reasons.append("retired element")
                continue
            shift = identity["shift"][reel]
            start = int(row["in_frame"]) + shift
            stop = int(row["out_frame"]) + shift
            if stop <= start:
                reasons.append("empty shot")
                continue
            covered = any(
                piece[0] <= start and stop <= piece[1]
                for piece in spans["canonical"].get(canon, [])
            )
            if not covered:
                reasons.append("shot leaves the usable span")
                continue
            length = stop - start
            placed.append(
                {
                    "shot_ordinal": int(row["shot_ordinal"]),
                    "element": canon,
                    "source_element": reel,
                    "first_frame": start,
                    "after_last_frame": stop,
                    "frames": length,
                    "timeline_start": cursor,
                    "timeline_stop": cursor + length,
                    "transition": row["transition"],
                }
            )
            cursor += length
        ordinals = [int(r["shot_ordinal"]) for r in rows]
        if ordinals != list(range(1, len(ordinals) + 1)):
            reasons.append("shot ordinals do not tile")
        if not rows:
            reasons.append("no shots")
        shots[pid] = placed
        if reasons:
            voids[pid] = sorted(set(reasons))
    return {"shots": shots, "voids": voids}


# ---------------------------------------------------------------------------
# stage 5 - governing element and source frames
# ---------------------------------------------------------------------------


def governing(shots: list[dict], reels: list[dict]) -> str:
    by_id = {r["reel_id"]: r for r in reels}
    tally = {}
    for shot in shots:
        tally[shot["element"]] = tally.get(shot["element"], 0) + shot["frames"]
    if not tally:
        raise ValueError("programme has no shots")
    ranked = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))
    for element, _frames in ranked:
        row = by_id.get(element)
        if row is not None and row["element_class"] != "print":
            return element
    return ranked[0][0]


# ---------------------------------------------------------------------------
# stage 7 - impairment
# ---------------------------------------------------------------------------


def union_length(spans: list[tuple[int, int]]) -> int:
    ordered = sorted(spans)
    total = 0
    cur_start = None
    cur_stop = None
    for start, stop in ordered:
        if cur_stop is None or start > cur_stop:
            if cur_stop is not None:
                total += cur_stop - cur_start
            cur_start, cur_stop = start, stop
        else:
            cur_stop = max(cur_stop, stop)
    if cur_stop is not None:
        total += cur_stop - cur_start
    return total


def impairment(defects: list[dict], programmes: list[dict], plan: dict) -> dict:
    live = {p["programme_id"] for p in programmes if p["programme_id"] not in plan["voids"]}
    per_programme = {}
    per_defect = {}
    for row in sorted(defects, key=lambda r: r["defect_id"]):
        pid = row["programme_id"]
        if pid not in live:
            continue
        shots = plan["shots"][pid]
        ordinal = int(row["shot_ordinal"])
        host = next((s for s in shots if s["shot_ordinal"] == ordinal), None)
        if host is None:
            continue
        start = int(row["span_start"])
        stop = max(start, int(row["span_end"]))
        first = host["timeline_start"]
        after_last = host["timeline_stop"]
        # Both ends move into the host shot, so a defect that misses it clips to zero length and keeps its row.
        lo = min(max(start, first), after_last)
        hi = min(max(stop, first), after_last)
        per_defect[row["defect_id"]] = {
            "defect_id": row["defect_id"],
            "programme_id": pid,
            "shot_ordinal": ordinal,
            "defect_class": row["defect_class"],
            "severity": int(row["severity"]),
            "detected_stage": row["detected_stage"],
            "span": (lo, hi),
            "frames": hi - lo,
        }
        if hi > lo:
            per_programme.setdefault(pid, []).append((lo, hi))
    impaired = {pid: union_length(v) for pid, v in per_programme.items()}
    for pid in live:
        impaired.setdefault(pid, 0)
    return {"per_defect": per_defect, "impaired": impaired}


# ---------------------------------------------------------------------------
# stage 8 - repair passes
# ---------------------------------------------------------------------------


def repairs_applied(
    repairs: list[dict],
    defects: dict,
    programmes: list[dict],
    decay: tuple[int, int],
    impaired: dict,
) -> dict:
    window = {p["programme_id"]: int(p["window_close_cycle"]) for p in programmes}
    by_programme_rows = {}
    for row in repairs:
        record = defects.get(row["defect_id"])
        if record is None:
            continue
        by_programme_rows.setdefault(record["programme_id"], []).append(row)

    ledger = []
    recovered_by_defect = {did: 0 for did in defects}
    per_programme = {}
    for pid in sorted(by_programme_rows):
        rows = sorted(
            by_programme_rows[pid],
            key=lambda r: (int(r["pass_index"]), r["repair_id"]),
        )
        ceiling = {}
        remaining = {}
        rank = {}
        for did, record in defects.items():
            if record["programme_id"] == pid:
                ceiling[did] = record["frames"]
                remaining[did] = record["frames"]
                rank[did] = 0
        budget = impaired.get(pid, 0)
        for row in rows:
            did = row["defect_id"]
            record = defects[did]
            rank[did] += 1
            if rank[did] > 1:
                ceiling[did] = ceiling[did] * decay[0] // decay[1]
            claimed = int(row["claimed_frames"])
            node = int(row["node_class"])
            state = "counted"
            if int(row["submitted_cycle"]) > window.get(pid, -1):
                state = "outside the repair window"
                allowed = 0
            elif node < record["severity"]:
                state = "node class below defect severity"
                allowed = 0
            else:
                allowed = min(claimed, ceiling[did], remaining[did], budget)
                state = "accepted" if allowed == claimed else "clamped"
            remaining[did] -= allowed
            budget -= allowed
            recovered_by_defect[did] += allowed
            per_programme[pid] = per_programme.get(pid, 0) + allowed
            ledger.append(
                {
                    "repair_id": row["repair_id"],
                    "defect_id": did,
                    "programme_id": pid,
                    "pass_index": int(row["pass_index"]),
                    "claimed_frames": claimed,
                    "recovered_frames": allowed,
                    "state": state,
                }
            )
    return {
        "ledger": sorted(ledger, key=lambda r: (r["programme_id"], r["defect_id"], r["pass_index"], r["repair_id"])),
        "by_defect": recovered_by_defect,
        "by_programme": per_programme,
    }


# ---------------------------------------------------------------------------
# stage 6 and 9 - cadence and the grade fixpoint
# ---------------------------------------------------------------------------


def band_of(settled: int, cadence_frames: int) -> str:
    if cadence_frames <= 0:
        return "D"
    pct = settled * 100
    if pct >= cadence_frames * 95:
        return "A"
    if pct >= cadence_frames * 85:
        return "B"
    if pct >= cadence_frames * 70:
        return "C"
    return "D"


def compose(src: int, unrecovered: int, recovered: int, grade: str, ratio: tuple[int, int], params: dict) -> int:
    num, den = ratio
    mode = params["rounding"]
    value = src
    converted = False
    credit_num, credit_den = GRADE_CREDIT[grade]
    for op in params["order"]:
        if op == "cadence":
            value = quantise(value * num, den, mode)
            converted = True
        elif op == "impair":
            amount = unrecovered
            if converted:
                amount = quantise(amount * num, den, mode)
            value -= amount
        elif op == "credit":
            amount = quantise(recovered * credit_num, credit_den, mode)
            if converted:
                amount = quantise(amount * num, den, mode)
            value += amount
    return value


def settle_programmes(programmes, reels, plan, imp, rep, params) -> dict:
    by_reel = {r["reel_id"]: r for r in reels}
    out = {}
    for row in sorted(programmes, key=lambda p: p["programme_id"]):
        pid = row["programme_id"]
        if pid in plan["voids"]:
            continue
        shots = plan["shots"][pid]
        element = governing(shots, reels)
        element_mhz = int(by_reel[element]["scan_cadence_mhz"])
        delivery_mhz = int(row["delivery_cadence_mhz"])
        ratio = (delivery_mhz, element_mhz)
        src = sum(s["frames"] for s in shots)
        impaired = imp["impaired"].get(pid, 0)
        recovered = rep["by_programme"].get(pid, 0)
        unrecovered = impaired - recovered
        cadence_frames = quantise(src * ratio[0], ratio[1], params["rounding"])
        stable = []
        for grade in GRADE_ORDER:
            settled = compose(src, unrecovered, recovered, grade, ratio, params)
            if band_of(settled, cadence_frames) == grade:
                stable.append((grade, settled))
        if not stable:
            raise ValueError("no stable grade for " + pid)
        grade, settled = stable[0]
        out[pid] = {
            "programme_id": pid,
            "title_key": row["title_key"],
            "holder_id": row["holder_id"],
            "deliverable_class": row["deliverable_class"],
            "governing_element": element,
            "element_cadence_mhz": element_mhz,
            "delivery_cadence_mhz": delivery_mhz,
            "source_frames": src,
            "cadence_frames": cadence_frames,
            "impaired_frames": impaired,
            "recovered_frames": recovered,
            "unrecovered_frames": unrecovered,
            "condition_grade": grade,
            "settled_frames": settled,
            "stable_grades": [g for g, _ in stable],
        }
    return out


# ---------------------------------------------------------------------------
# stage 10 - admission under the shared group quota
# ---------------------------------------------------------------------------


def admit(settled: dict, holders: list[dict], charter: dict) -> dict:
    holder_row = {h["holder_id"]: h for h in holders}
    factor = int(charter["group_draw_factor"])
    order = sorted(settled, key=lambda pid: (-settled[pid]["settled_frames"], pid))

    def run(drawing: frozenset) -> tuple[dict, frozenset]:
        quota = {}
        groups = {}
        for hid, row in holder_row.items():
            groups.setdefault(row["settlement_group"], []).append(hid)
        for group, members in groups.items():
            drawn = sorted(h for h in members if h in drawing)
            base = sum(int(holder_row[h]["base_quota_frames"]) for h in drawn)
            if drawn:
                base -= factor * (len(drawn) - 1)
            quota[group] = max(base, 0)
        used = {g: 0 for g in quota}
        closed = set()
        admitted = {}
        for pid in order:
            row = settled[pid]
            hid = row["holder_id"]
            group = holder_row[hid]["settlement_group"]
            if group in closed:
                continue
            if used[group] + row["settled_frames"] <= quota[group]:
                used[group] += row["settled_frames"]
                admitted[pid] = group
            else:
                closed.add(group)
        nxt = frozenset(settled[p]["holder_id"] for p in admitted)
        return {"quota": quota, "used": used, "admitted": admitted}, nxt

    everyone = frozenset(settled[p]["holder_id"] for p in settled)
    state = everyone
    seen = []
    for _ in range(64):
        result, nxt = run(state)
        if nxt == state:
            return {
                "quota": result["quota"],
                "used": result["used"],
                "admitted": sorted(result["admitted"]),
                "held": sorted(p for p in settled if p not in result["admitted"]),
                "drawing": sorted(state),
                "order": order,
            }
        seen.append(state)
        state = nxt
    raise ValueError("admission did not settle")


# ---------------------------------------------------------------------------
# stage 11 and 12 - vault seating and lane cascade
# ---------------------------------------------------------------------------


def seat(admitted: list[str], settled: dict, holders: list[dict], charter: dict, lanes: dict) -> dict:
    holder_row = {h["holder_id"]: h for h in holders}
    vaults = sorted(charter["vaults"], key=lambda v: (int(v["seat_rank"]), v["vault_id"]))
    order = sorted(admitted, key=lambda pid: (-settled[pid]["settled_frames"], pid))

    def eligible(pid: str, vault: dict) -> bool:
        row = settled[pid]
        group = holder_row[row["holder_id"]]["settlement_group"]
        return (
            row["deliverable_class"] in vault["accepts_classes"]
            and group in vault["settlement_groups"]
        )

    best = None
    tally = [0]
    load = {v["vault_id"]: 0 for v in vaults}
    seating: dict[str, str] = {}
    limit = 4096

    def search(index: int) -> None:
        nonlocal best
        if tally[0] >= limit:
            return
        if index == len(order):
            tally[0] += 1
            if best is None:
                best = dict(seating)
            return
        pid = order[index]
        frames = settled[pid]["settled_frames"]
        for vault in vaults:
            if not eligible(pid, vault):
                continue
            if load[vault["vault_id"]] + frames > int(vault["capacity_frames"]):
                continue
            load[vault["vault_id"]] += frames
            seating[pid] = vault["vault_id"]
            search(index + 1)
            del seating[pid]
            load[vault["vault_id"]] -= frames

    search(0)
    if best is None:
        raise ValueError("no feasible seating")

    seated_load = {v["vault_id"]: 0 for v in vaults}
    for pid, vid in best.items():
        seated_load[vid] += settled[pid]["settled_frames"]
    residual = sum(
        int(v["capacity_frames"]) - seated_load[v["vault_id"]] for v in vaults
    )

    held = sorted(p for p in settled if p not in admitted)
    lane_rows = sorted(lanes["lanes"], key=lambda ln: (int(ln["lane_rank"]), ln["lane_id"]))
    pool = residual
    lane_seat: dict[str, str] = {}
    lane_capacity = {}
    for lane in lane_rows:
        cap = pool * int(lane["residual_share_num"]) // int(lane["residual_share_den"])
        lane_capacity[lane["lane_id"]] = cap
        used = 0
        for pid in sorted(held, key=lambda p: (-settled[p]["settled_frames"], p)):
            if pid in lane_seat:
                continue
            row = settled[pid]
            group = holder_row[row["holder_id"]]["settlement_group"]
            if row["deliverable_class"] not in lane["accepts_classes"]:
                continue
            if group not in lane["settlement_groups"]:
                continue
            if used + row["settled_frames"] > cap:
                continue
            lane_seat[pid] = lane["lane_id"]
            used += row["settled_frames"]
        pool -= used
    return {
        "seating": best,
        "feasible_count": tally[0],
        "vault_load": seated_load,
        "vault_residual": residual,
        "lane_seating": lane_seat,
        "lane_capacity": lane_capacity,
        "shed": sorted(p for p in held if p not in lane_seat),
    }


# ---------------------------------------------------------------------------
# full settlement
# ---------------------------------------------------------------------------


def settle(corpus: dict, params: dict | None = None) -> dict:
    params = params or {
        "rounding": TRUE_ROUNDING,
        "order": TRUE_ORDER,
        "decay": TRUE_DECAY,
    }
    charter = corpus["vaults"]
    cycle = int(charter["settlement_cycle"])
    identity = canonicalise(corpus["reels"], corpus["lineage"], cycle)
    spans = usable_spans(corpus["reels"], identity)
    plan = conform(corpus["cuts"], corpus["programmes"], identity, spans)
    imp = impairment(corpus["defects"], corpus["programmes"], plan)
    rep = repairs_applied(
        corpus["repairs"], imp["per_defect"], corpus["programmes"], params["decay"], imp["impaired"]
    )
    settled = settle_programmes(corpus["programmes"], corpus["reels"], plan, imp, rep, params)
    adm = admit(settled, corpus["holders"], charter)
    placement = seat(adm["admitted"], settled, corpus["holders"], charter, corpus["lanes"])
    return {
        "cycle": cycle,
        "identity": identity,
        "spans": spans,
        "plan": plan,
        "impairment": imp,
        "repairs": rep,
        "settled": settled,
        "admission": adm,
        "placement": placement,
        "params": params,
        "corpus": corpus,
    }

# ---------------------------------------------------------------- reports


def span_length(pairs):
    return sum(b - a for a, b in pairs)


def build_reports(res):
    ident = res["identity"]
    plan = res["plan"]
    imp = res["impairment"]
    rep = res["repairs"]
    settled = res["settled"]
    adm = res["admission"]
    place = res["placement"]
    corpus = res["corpus"]
    charter = corpus["vaults"]
    lanes = corpus["lanes"]["lanes"]
    group_of = {h["holder_id"]: h["settlement_group"] for h in corpus["holders"]}
    out = {}

    # -- reel audit ---------------------------------------------------
    reel_rows = []
    for row in sorted(corpus["reels"], key=lambda r: r["reel_id"]):
        rid = row["reel_id"]
        canon = ident["canonical"][rid]
        if canon in ident["retired"] or rid in ident["retired"]:
            state = "retired"
        elif rid == canon:
            state = "live"
        else:
            state = "folded"
        reel_rows.append(
            {
                "canonical_id": canon,
                "element_class": row["element_class"],
                "registration_shift": ident["shift"][rid],
                "reel_id": rid,
                "scan_cadence_mhz": int(row["scan_cadence_mhz"]),
                "scanned_frames": int(row["scanned_frames"]),
                "state": state,
            }
        )
    out["reel_audit.json"] = {
        "canonical_elements": sorted(ident["live"]),
        "folded_elements": {k: sorted(v) for k, v in sorted(ident["folded"].items())},
        "reels": reel_rows,
        "retired_elements": sorted(ident["retired"]),
        "settlement_cycle": res["cycle"],
        "usable_frames": {
            k: span_length(v) for k, v in sorted(res["spans"]["canonical"].items())
        },
    }

    # -- conform report -----------------------------------------------
    conf = []
    conformed = [p for p in sorted(plan["shots"]) if p not in plan["voids"]]
    for pid in conformed:
        shots = plan["shots"][pid]
        conf.append(
            {
                "conformed_frames": sum(s["frames"] for s in shots),
                "programme_id": pid,
                "shot_count": len(shots),
                "shots": [
                    {
                        "canonical_id": s["element"],
                        "element_first_frame": s["first_frame"],
                        "element_after_last_frame": s["after_last_frame"],
                        "frames": s["frames"],
                        "shot_ordinal": s["shot_ordinal"],
                        "source_reel_id": s["source_element"],
                        "timeline_start": s["timeline_start"],
                        "timeline_stop": s["timeline_stop"],
                        "transition": s["transition"],
                    }
                    for s in shots
                ],
                "state": "conformed",
            }
        )
    for pid in sorted(plan["voids"]):
        conf.append(
            {
                "conformed_frames": 0,
                "programme_id": pid,
                "reason": plan["voids"][pid],
                "shot_count": 0,
                "shots": [],
                "state": "void",
            }
        )
    conf.sort(key=lambda r: r["programme_id"])
    out["conform_report.json"] = {
        "conformed_programmes": conformed,
        "programmes": conf,
        "void_programmes": sorted(plan["voids"]),
    }

    # -- defect findings ----------------------------------------------
    findings = []
    for did in sorted(imp["per_defect"]):
        d = imp["per_defect"][did]
        findings.append(
            {
                "clipped_frames": d["frames"],
                "defect_class": d["defect_class"],
                "defect_id": did,
                "detected_stage": d["detected_stage"],
                "programme_id": d["programme_id"],
                "recovered_frames": rep["by_defect"].get(did, 0),
                "severity": d["severity"],
                "shot_ordinal": d["shot_ordinal"],
                "timeline_start": d["span"][0],
                "timeline_stop": d["span"][1],
            }
        )
    out["defect_findings.json"] = {
        "defects": findings,
        "impaired_frames": {k: imp["impaired"][k] for k in sorted(imp["impaired"])},
        "impaired_total": sum(imp["impaired"].values()),
    }

    # -- repair ledger -------------------------------------------------
    rl = [
        {
            "claimed_frames": r["claimed_frames"],
            "defect_id": r["defect_id"],
            "pass_index": r["pass_index"],
            "programme_id": r["programme_id"],
            "recovered_frames": r["recovered_frames"],
            "repair_id": r["repair_id"],
            "state": r["state"],
        }
        for r in rep["ledger"]
    ]
    rl.sort(key=lambda r: (r["pass_index"], r["repair_id"]))
    counts = {}
    for r in rl:
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    recovered_map = {pid: settled[pid]["recovered_frames"] for pid in sorted(settled)}
    out["repair_ledger.json"] = {
        "recovered_frames": recovered_map,
        "recovered_total": sum(recovered_map.values()),
        "repairs": rl,
        "state_counts": {k: counts[k] for k in sorted(counts)},
    }

    # -- cadence ledger ------------------------------------------------
    rows = []
    for pid in sorted(settled):
        s = settled[pid]
        rows.append(
            {
                "cadence_frames": s["cadence_frames"],
                "condition_grade": s["condition_grade"],
                "delivery_cadence_mhz": s["delivery_cadence_mhz"],
                "element_cadence_mhz": s["element_cadence_mhz"],
                "governing_element": s["governing_element"],
                "impaired_frames": s["impaired_frames"],
                "programme_id": pid,
                "recovered_frames": s["recovered_frames"],
                "settled_frames": s["settled_frames"],
                "source_frames": s["source_frames"],
                "unrecovered_frames": s["unrecovered_frames"],
            }
        )
    out["cadence_ledger.json"] = {
        "cadence_total": sum(r["cadence_frames"] for r in rows),
        "programmes": rows,
        "settled_total": sum(r["settled_frames"] for r in rows),
        "source_total": sum(r["source_frames"] for r in rows),
    }

    # -- allocation ledger ----------------------------------------------
    draws = []
    for pid in adm["order"]:
        s = settled[pid]
        draws.append(
            {
                "holder_id": s["holder_id"],
                "programme_id": pid,
                "settled_frames": s["settled_frames"],
                "settlement_group": group_of[s["holder_id"]],
                "state": "admitted" if pid in adm["admitted"] else "held",
            }
        )
    out["allocation_ledger.json"] = {
        "admitted": list(adm["admitted"]),
        "draw_order": draws,
        "drawing_holders": list(adm["drawing"]),
        "group_quota": {k: adm["quota"][k] for k in sorted(adm["quota"])},
        "group_used": {k: adm["used"].get(k, 0) for k in sorted(adm["quota"])},
        "held": list(adm["held"]),
    }

    def entries(ids):
        return [
            {
                "condition_grade": settled[p]["condition_grade"],
                "deliverable_class": settled[p]["deliverable_class"],
                "holder_id": settled[p]["holder_id"],
                "programme_id": p,
                "settled_frames": settled[p]["settled_frames"],
                "settlement_group": group_of[settled[p]["holder_id"]],
                "title_key": settled[p]["title_key"],
            }
            for p in ids
        ]

    # -- vault index and per vault reports --------------------------------
    index = []
    for v in sorted(charter["vaults"], key=lambda x: int(x["seat_rank"])):
        vid = v["vault_id"]
        seated = sorted(
            [p for p, s in place["seating"].items() if s == vid],
            key=lambda p: (-settled[p]["settled_frames"], p),
        )
        cap = int(v["capacity_frames"])
        load = place["vault_load"].get(vid, 0)
        index.append(
            {
                "capacity_frames": cap,
                "headroom_frames": cap - load,
                "load_frames": load,
                "programme_count": len(seated),
                "seat_rank": int(v["seat_rank"]),
                "vault_id": vid,
            }
        )
        out["vault_%s.json" % vid] = {
            "accepts_classes": sorted(v["accepts_classes"]),
            "capacity_frames": cap,
            "headroom_frames": cap - load,
            "load_frames": load,
            "programmes": entries(seated),
            "seat_rank": int(v["seat_rank"]),
            "settlement_groups": sorted(v["settlement_groups"]),
            "vault_id": vid,
        }
    out["vault_index.json"] = {
        "residual_pool_frames": place["vault_residual"],
        "seated_total_frames": sum(place["vault_load"].values()),
        "vaults": index,
    }

    # -- per lane reports ---------------------------------------------------
    for ln in sorted(lanes, key=lambda x: int(x["lane_rank"])):
        lid = ln["lane_id"]
        seated = sorted(
            [p for p, s in place["lane_seating"].items() if s == lid],
            key=lambda p: (-settled[p]["settled_frames"], p),
        )
        cap = place["lane_capacity"].get(lid, 0)
        load = sum(settled[p]["settled_frames"] for p in seated)
        out["lane_%s.json" % lid] = {
            "accepts_classes": sorted(ln["accepts_classes"]),
            "capacity_frames": cap,
            "headroom_frames": cap - load,
            "lane_id": lid,
            "lane_rank": int(ln["lane_rank"]),
            "load_frames": load,
            "programmes": entries(seated),
            "settlement_groups": sorted(ln["settlement_groups"]),
        }

    # -- summary ------------------------------------------------------------
    admitted_frames = sum(settled[p]["settled_frames"] for p in adm["admitted"])
    held_frames = sum(settled[p]["settled_frames"] for p in adm["held"])
    lane_frames = sum(settled[p]["settled_frames"] for p in place["lane_seating"])
    shed_frames = sum(settled[p]["settled_frames"] for p in place["shed"])
    settled_total = sum(s["settled_frames"] for s in settled.values())
    out["summary.json"] = {
        "admitted_count": len(adm["admitted"]),
        "admitted_frames": admitted_frames,
        "conformed_programme_count": len(settled),
        "held_count": len(adm["held"]),
        "held_frames": held_frames,
        "impaired_total": sum(imp["impaired"].values()),
        "lane_frames": lane_frames,
        "lane_seated_count": len(place["lane_seating"]),
        "recovered_total": sum(settled[p]["recovered_frames"] for p in settled),
        "settled_total": settled_total,
        "settlement_cycle": res["cycle"],
        "shed_count": len(place["shed"]),
        "shed_frames": shed_frames,
        "void_programme_count": len(plan["voids"]),
    }

    # -- reconciliation -----------------------------------------------------
    stages = [
        {
            "left": len(corpus["programmes"]),
            "right": len(settled) + len(plan["voids"]),
            "stage": "conform",
        },
        {
            "left": sum(imp["impaired"].values()),
            "right": sum(settled[p]["recovered_frames"] for p in settled)
            + sum(settled[p]["unrecovered_frames"] for p in settled),
            "stage": "impairment",
        },
        {
            "left": settled_total,
            "right": admitted_frames + held_frames,
            "stage": "admission",
        },
        {
            "left": admitted_frames,
            "right": sum(place["vault_load"].values()),
            "stage": "seating",
        },
        {
            "left": held_frames,
            "right": lane_frames + shed_frames,
            "stage": "cascade",
        },
    ]
    for st in stages:
        st["residual"] = st["left"] - st["right"]
        st["closes"] = st["residual"] == 0
    out["reconciliation.json"] = {
        "residual": sum(abs(s["residual"]) for s in stages),
        "settled_total": settled_total,
        "stages": stages,
        "vault_and_lane_total": sum(place["vault_load"].values())
        + lane_frames
        + shed_frames,
    }

    return out


def dump(obj):
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# verifier harness
# ---------------------------------------------------------------------------

import base64
import copy
import io
import shutil
import subprocess
import tarfile
import tempfile
import zlib

from pathlib import Path


CATALOGUE_ARCHIVE = (
    "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"
)


def _materialise_catalogue():
    root = Path(tempfile.mkdtemp(prefix="restoration-catalogue-")) / "data"
    root.mkdir(parents=True, exist_ok=True)
    blob = zlib.decompress(base64.b64decode(CATALOGUE_ARCHIVE))
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            if "/" in member.name or member.name.startswith("."):
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            (root / member.name).write_bytes(handle.read())
    return root


_CACHE = {}


def _data_root() -> Path:
    """The verifier's private reference catalogue, unpacked on first use.

    Nothing at module level does this work. rewardkit imports this module, and
    an import that base64 decoded and untarred a 28 file corpus would pay that
    cost even when no check runs.
    """
    if "data" not in _CACHE:
        _CACHE["data"] = _materialise_catalogue()
    return _CACHE["data"]


def _out(workspace) -> Path:
    return Path(workspace) / "out"


def _agent_data(workspace) -> Path:
    return Path(workspace) / "data"


def _program(workspace) -> Path:
    return _out(workspace) / "cadence_settle.py"


CORE_REPORTS = (
    "reel_audit.json",
    "conform_report.json",
    "defect_findings.json",
    "repair_ledger.json",
    "cadence_ledger.json",
    "allocation_ledger.json",
    "vault_index.json",
    "summary.json",
    "reconciliation.json",
)

HEADERS = {
    "reels": [
        "reel_id",
        "element_class",
        "scanned_frames",
        "scan_cadence_mhz",
        "head_leader",
        "tail_leader",
    ],
    "lineage": [
        "event_id",
        "effective_cycle",
        "kind",
        "from_reel",
        "to_reel",
        "registration_offset",
    ],
    "cuts": [
        "programme_id",
        "shot_ordinal",
        "reel_id",
        "in_frame",
        "out_frame",
        "transition",
    ],
    "programmes": [
        "programme_id",
        "title_key",
        "delivery_cadence_mhz",
        "deliverable_class",
        "holder_id",
        "greenlit_cycle",
        "window_close_cycle",
    ],
    "defects": [
        "defect_id",
        "programme_id",
        "shot_ordinal",
        "defect_class",
        "severity",
        "span_start",
        "span_end",
        "detected_stage",
    ],
    "repairs": [
        "repair_id",
        "defect_id",
        "pass_index",
        "node_class",
        "claimed_frames",
        "submitted_cycle",
    ],
    "holders": ["holder_id", "account_tier", "settlement_group", "base_quota_frames"],
}


def _base_corpus():
    if "base" not in _CACHE:
        _CACHE["base"] = load_corpus(str(_data_root()))
    return copy.deepcopy(_CACHE["base"])


def _reference():
    if "ref" not in _CACHE:
        _CACHE["ref"] = build_reports(settle(load_corpus(str(_data_root()))))
    return _CACHE["ref"]


def _delivered(workspace):
    key = "got:" + str(workspace)
    if key in _CACHE:
        return _CACHE[key]
    got = {}
    out = _out(workspace)
    if out.is_dir():
        for entry in sorted(os.listdir(str(out))):
            if not entry.endswith(".json"):
                continue
            try:
                got[entry] = json.loads((out / entry).read_text(encoding="utf-8"))
            except Exception:
                got[entry] = None
    _CACHE[key] = got
    return got


def _got(workspace, name):
    return _delivered(workspace).get(name)


def _agrees(workspace, name, *keys):
    ref = _reference().get(name)
    got = _got(workspace, name)
    if not isinstance(got, dict) or not isinstance(ref, dict):
        return False
    if not keys:
        return got == ref
    for key in keys:
        if key not in got or got[key] != ref[key]:
            return False
    return True


def _write_corpus(corpus, root):
    """Write a mutated catalogue that is still a complete catalogue.

    The instruction points the agent at the published calibration cycle and at
    the subsystem rulebooks, and tells it to recover the three standing
    conventions from that cycle rather than guess them. A graded catalogue
    carrying only the mutated data files would therefore punish a program for
    reading exactly the files it was told to read. Every file in the reference
    catalogue is copied in first, and the mutated ones are written over those
    copies; the calibration cycle is deliberately not mutated, because the
    conventions it publishes hold across every cycle.
    """
    os.makedirs(root, exist_ok=True)
    for source in sorted(_data_root().iterdir()):
        if source.is_file():
            shutil.copy2(str(source), os.path.join(root, source.name))
    names = {
        "reels": "reel_scans.csv",
        "lineage": "lineage_events.csv",
        "cuts": "cut_list.csv",
        "programmes": "programmes.csv",
        "defects": "defect_log.csv",
        "repairs": "repair_log.csv",
        "holders": "holders.csv",
    }
    for key, filename in names.items():
        path = os.path.join(root, filename)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=HEADERS[key], lineterminator="\n")
            writer.writeheader()
            for row in corpus[key]:
                writer.writerow({k: row.get(k, "") for k in HEADERS[key]})
    Path(os.path.join(root, "vault_charter.json")).write_text(
        json.dumps(corpus["vaults"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    Path(os.path.join(root, "lane_charter.json")).write_text(
        json.dumps(corpus["lanes"], indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _privilege_drop_prefix():
    """Command prefix that runs the agent's program as an unprivileged user.

    Grading runs as root and the delivered program is hostile input. Running it
    under setpriv as nobody means a process it daemonises cannot write into the
    root-owned verifier log directory and cannot read the answer key under
    /tests, so the reward it earns cannot be forged after the run.

    Returns [] when we are not root, where there is no privilege to drop, and
    None when we are root but setpriv is missing. None means refuse: running
    hostile code as root is not a degraded mode worth having, and the verifier
    image installs util-linux precisely so this cannot happen.
    """
    if os.name != "posix" or os.geteuid() != 0:
        return []
    if shutil.which("setpriv") is None:
        return None
    return ["setpriv", "--reuid", "65534", "--regid", "65534", "--clear-groups"]


def _grant_access(target, executable=False, writable=True):
    """Let the unprivileged agent user reach a temp path without exposing /tests.

    Opens the target subtree and grants traverse on its ancestors only; nothing
    under /tests or /logs is touched.

    writable=False grants read and traverse but no write. That is what an input
    catalogue needs, because the program only reads its input, and it keeps the
    verifier's own reference catalogue out of reach of the program it is about
    to run. The output directory still needs write, so it keeps the default.
    """
    target = os.path.abspath(target)
    if os.path.isdir(target):
        dir_mode = 0o777 if writable else 0o555
        file_mode = 0o666 if writable else 0o444
        try:
            os.chmod(target, dir_mode)
        except OSError:
            pass
        for root, dirs, files in os.walk(target):
            for name in dirs:
                try:
                    os.chmod(os.path.join(root, name), dir_mode)
                except OSError:
                    pass
            for name in files:
                try:
                    os.chmod(os.path.join(root, name), file_mode)
                except OSError:
                    pass
    else:
        try:
            os.chmod(target, 0o755 if executable else 0o644)
        except OSError:
            pass
    parent = os.path.dirname(target)
    while parent and parent not in ("/", "/tmp"):
        try:
            mode = os.stat(parent).st_mode & 0o777
            os.chmod(parent, mode | 0o011)
        except OSError:
            pass
        parent = os.path.dirname(parent)


def _run_program(workspace, catalogue_dir, output_dir):
    """Run the delivered program once, then kill everything it left behind.

    start_new_session puts the program in its own process group so the whole
    group can be killed on every exit path, including a timeout. Without the
    kill a child the program daemonises would outlive the check and could still
    be running when rewardkit writes the reward.
    """
    program = _program(workspace)
    if not program.is_file():
        return False
    prefix = _privilege_drop_prefix()
    if prefix is None:
        return False
    os.makedirs(output_dir, exist_ok=True)
    if prefix:
        _grant_access(catalogue_dir, writable=False)
        _grant_access(output_dir)
        _grant_access(str(program), executable=True)
    proc = None
    try:
        proc = subprocess.Popen(
            prefix + [sys.executable, str(program), str(catalogue_dir), str(output_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            proc.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            return False
        return proc.returncode == 0
    except Exception:
        return False
    finally:
        if proc is not None:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except Exception:
                pass
            try:
                proc.kill()
            except Exception:
                pass
            try:
                proc.wait(timeout=10)
            except Exception:
                pass


def _collect(output_dir):
    got = {}
    if not os.path.isdir(output_dir):
        return got
    for entry in sorted(os.listdir(output_dir)):
        if not entry.endswith(".json"):
            continue
        try:
            got[entry] = json.loads(
                Path(os.path.join(output_dir, entry)).read_text(encoding="utf-8")
            )
        except Exception:
            got[entry] = None
    return got


def _generalises(workspace, mutator, names=CORE_REPORTS):
    """Run the delivered program over a mutated catalogue and compare."""
    corpus = mutator(_base_corpus())
    try:
        want = build_reports(settle(corpus))
    except Exception:
        return False
    work = tempfile.mkdtemp(prefix="cadence-")
    try:
        catalogue = os.path.join(work, "catalogue")
        produced = os.path.join(work, "out")
        _write_corpus(corpus, catalogue)
        if not _run_program(workspace, catalogue, produced):
            return False
        got = _collect(produced)
        for name in names:
            if name not in got or got[name] != want[name]:
                return False
        wanted_parts = {k for k in want if k.startswith(("vault_", "lane_"))}
        wanted_parts.discard("vault_index.json")
        got_parts = {k for k in got if k.startswith(("vault_", "lane_"))}
        got_parts.discard("vault_index.json")
        if wanted_parts != got_parts:
            return False
        for name in sorted(wanted_parts):
            if got[name] != want[name]:
                return False
        return True
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _row(rows, key, value):
    for row in rows:
        if row[key] == value:
            return row
    raise KeyError(value)


# ---------------------------------------------------------------------------
# mutation families
# ---------------------------------------------------------------------------


def _mutate_tie_configuration(corpus):
    """The two elements supplying pg09 most are levelled so the governing tie-break decides."""
    cycle = int(corpus["vaults"]["settlement_cycle"])
    canon = canonicalise(corpus["reels"], corpus["lineage"], cycle)["canonical"]
    rows = [r for r in corpus["cuts"] if r["programme_id"] == "pg09"]
    rows.sort(key=lambda r: int(r["shot_ordinal"]))
    tally = {}
    for row in rows:
        length = int(row["out_frame"]) - int(row["in_frame"])
        if length <= 0:
            continue
        element = canon.get(row["reel_id"], row["reel_id"])
        tally[element] = tally.get(element, 0) + length
    ranked = sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))
    if len(ranked) < 2:
        return corpus
    gap = ranked[0][1] - ranked[1][1]
    for row in rows:
        if gap <= 0:
            break
        if canon.get(row["reel_id"], row["reel_id"]) != ranked[0][0]:
            continue
        length = int(row["out_frame"]) - int(row["in_frame"])
        take = min(gap, length - 1)
        if take <= 0:
            continue
        row["out_frame"] = str(int(row["out_frame"]) - take)
        gap -= take
    return corpus


def _mutate_value_across_a_cap(corpus):
    """The smallest vault loses just enough capacity to change the seating."""
    vaults = sorted(corpus["vaults"]["vaults"], key=lambda v: v["capacity_frames"])
    vaults[0]["capacity_frames"] = int(vaults[0]["capacity_frames"]) - 900
    vaults[-1]["capacity_frames"] = int(vaults[-1]["capacity_frames"]) + 900
    return corpus


def _mutate_rule_precedence_inverted(corpus):
    """A late pass becomes the earliest pass on its defect."""
    by_defect = {}
    for row in corpus["repairs"]:
        by_defect.setdefault(row["defect_id"], []).append(row)
    for defect_id in sorted(by_defect):
        group = by_defect[defect_id]
        if len(group) < 3:
            continue
        group.sort(key=lambda r: (int(r["pass_index"]), r["repair_id"]))
        first, last = group[0], group[-1]
        first["pass_index"], last["pass_index"] = last["pass_index"], first["pass_index"]
    return corpus


def _mutate_group_emptied(corpus):
    """Every holder in one settlement group loses its quota.

    The group emptied has to be one that actually draws in the base cycle.
    Taking the alphabetically first group emptied a group that already draws
    nothing, so the mutated catalogue settled identically to the base one and
    this fixture graded nothing the base cycle checks did not already grade.
    """
    drawn = {}
    for row in build_reports(settle(_base_corpus()))["allocation_ledger.json"]["draw_order"]:
        if row["state"] == "admitted":
            group = row["settlement_group"]
            drawn[group] = drawn.get(group, 0) + row["settled_frames"]
    if drawn:
        victim = max(sorted(drawn), key=lambda group: drawn[group])
    else:
        victim = sorted({r["settlement_group"] for r in corpus["holders"]})[0]
    for row in corpus["holders"]:
        if row["settlement_group"] == victim:
            row["base_quota_frames"] = "0"
    return corpus


def _mutate_cycle_introduced(corpus):
    """A lineage cycle is written into the book but dated beyond this cycle."""
    events = corpus["lineage"]
    alias = next(r for r in events if r["kind"] == "alias")
    events.append(
        {
            "event_id": "lv99",
            "effective_cycle": str(int(corpus["vaults"]["settlement_cycle"]) + 6),
            "kind": "alias",
            "from_reel": alias["to_reel"],
            "to_reel": alias["from_reel"],
            "registration_offset": "0",
        }
    )
    return corpus


def _mutate_temporal_boundary(corpus):
    """Every repair window closes one cycle earlier."""
    for row in corpus["programmes"]:
        row["window_close_cycle"] = str(int(row["window_close_cycle"]) - 1)
    return corpus


def _mutate_entity_added(corpus):
    """A fresh holder joins a group and moves the drawing fixpoint."""
    holders = corpus["holders"]
    donor = _row(holders, "holder_id", sorted(r["holder_id"] for r in holders)[0])
    holders.append(
        {
            "holder_id": "h07",
            "account_tier": "deferred",
            "settlement_group": donor["settlement_group"],
            "base_quota_frames": str(int(donor["base_quota_frames"]) // 3),
        }
    )
    moved = sorted(
        (r for r in corpus["programmes"] if r["holder_id"] == donor["holder_id"]),
        key=lambda r: r["programme_id"],
    )
    if moved:
        moved[-1]["holder_id"] = "h07"
    for vault in corpus["vaults"]["vaults"]:
        vault["capacity_frames"] = int(vault["capacity_frames"]) * 6 // 5
    return corpus


def _mutate_non_applying_rule(corpus):
    """A programme is cut entirely from print stock, so the exclusion lifts."""
    prints = sorted(
        r["reel_id"] for r in corpus["reels"] if r["element_class"] == "print"
    )
    live = prints[0]
    for row in corpus["lineage"]:
        if row["kind"] == "retire" and row["from_reel"] == live:
            row["effective_cycle"] = str(int(corpus["vaults"]["settlement_cycle"]) + 9)
    scan = _row(corpus["reels"], "reel_id", live)
    scan["scanned_frames"] = "42000"
    scan["head_leader"] = "48"
    scan["tail_leader"] = "48"
    shots = sorted(
        (r for r in corpus["cuts"] if r["programme_id"] == "pg05"),
        key=lambda r: int(r["shot_ordinal"]),
    )
    cursor = 200
    for row in shots:
        length = int(row["out_frame"]) - int(row["in_frame"])
        row["reel_id"] = live
        row["in_frame"] = str(cursor)
        row["out_frame"] = str(cursor + length)
        cursor += length + 40
    return corpus


def _mutate_print_governs(corpus):
    """Print stock supplies the most frames of a programme that also has a negative."""
    prints = sorted(
        r["reel_id"] for r in corpus["reels"] if r["element_class"] == "print"
    )
    live = prints[0]
    for row in corpus["lineage"]:
        if row["kind"] == "retire" and row["from_reel"] == live:
            row["effective_cycle"] = str(int(corpus["vaults"]["settlement_cycle"]) + 9)
    scan = _row(corpus["reels"], "reel_id", live)
    scan["scanned_frames"] = "60000"
    scan["head_leader"] = "48"
    scan["tail_leader"] = "48"
    shots = sorted(
        (r for r in corpus["cuts"] if r["programme_id"] == "pg09"),
        key=lambda r: int(r["shot_ordinal"]),
    )
    cursor = 200
    for row in shots[:-1]:
        length = int(row["out_frame"]) - int(row["in_frame"]) + 900
        row["reel_id"] = live
        row["in_frame"] = str(cursor)
        row["out_frame"] = str(cursor + length)
        cursor += length + 40
    return corpus


def _mutate_prefix_binding(corpus):
    """Quotas tighten and two programmes in one group settle level, so the draw closes on a tie."""
    for row in corpus["holders"]:
        row["base_quota_frames"] = str(max(1, int(row["base_quota_frames"]) * 9 // 10))
    donor, twin = "pg08", "pg09"
    shots = [r for r in corpus["cuts"] if r["programme_id"] == donor]
    shots.sort(key=lambda r: int(r["shot_ordinal"]))
    kept = [r for r in corpus["cuts"] if r["programme_id"] != twin]
    for index, row in enumerate(shots, start=1):
        clone = dict(row)
        clone["programme_id"] = twin
        clone["shot_ordinal"] = str(index)
        kept.append(clone)
    corpus["cuts"] = kept
    by_id = {r["programme_id"]: r for r in corpus["programmes"]}
    by_id[twin]["delivery_cadence_mhz"] = by_id[donor]["delivery_cadence_mhz"]
    corpus["defects"] = [r for r in corpus["defects"] if r["programme_id"] not in (donor, twin)]
    live = {r["defect_id"] for r in corpus["defects"]}
    corpus["repairs"] = [r for r in corpus["repairs"] if r["defect_id"] in live]
    return corpus


def _mutate_counterfactual_boundary(corpus):
    """Programmes swap their delivery cadence across the conversion boundary."""
    order = sorted(corpus["programmes"], key=lambda r: r["programme_id"])
    swap = {"23976": "29970", "24000": "29970", "25000": "23976", "29970": "24000"}
    for row in order:
        row["delivery_cadence_mhz"] = swap[row["delivery_cadence_mhz"]]
    for vault in corpus["vaults"]["vaults"]:
        vault["capacity_frames"] = int(vault["capacity_frames"]) * 9 // 5
    return corpus


def _mutate_partition_count(corpus):
    """One vault is retired from the charter and a new lane opens."""
    vaults = sorted(corpus["vaults"]["vaults"], key=lambda v: v["seat_rank"])
    dropped = vaults.pop()
    survivors = vaults
    for vault in survivors:
        vault["capacity_frames"] = int(vault["capacity_frames"]) + int(
            dropped["capacity_frames"]
        )
        classes = set(vault["accepts_classes"]) | set(dropped["accepts_classes"])
        groups = set(vault["settlement_groups"]) | set(dropped["settlement_groups"])
        vault["accepts_classes"] = sorted(classes)
        vault["settlement_groups"] = sorted(groups)
    corpus["vaults"]["vaults"] = survivors
    lanes = sorted(corpus["lanes"]["lanes"], key=lambda ln: ln["lane_rank"])
    corpus["lanes"]["lanes"] = lanes + [
        {
            "lane_id": "trestle",
            "lane_rank": max(int(ln["lane_rank"]) for ln in lanes) + 1,
            "residual_share_num": 1,
            "residual_share_den": 1,
            "accepts_classes": sorted(
                {r["deliverable_class"] for r in corpus["programmes"]}
            ),
            "settlement_groups": sorted(
                {r["settlement_group"] for r in corpus["holders"]}
            ),
        }
    ]
    return corpus


# ---------------------------------------------------------------------------
# catalogue fingerprint (the shipped catalogue must survive the run untouched)
# ---------------------------------------------------------------------------

def _mutate_every_void_reason(corpus):
    """Exercise the four void conditions the shipped cycle never reaches.

    The conform rulebook states six conditions that void a programme, and the
    shipped cycle only reaches two of them, so a solver could omit the other
    four and lose nothing. This corpus names an element no identity resolves
    to, names a retired element, carries a shot with no picture, and strips one
    programme of its shots, which puts all six reasons in play at once.
    """
    retired = sorted(
        row["from_reel"] for row in corpus["lineage"] if row["kind"] == "retire"
    )
    retired_reel = retired[0] if retired else "el110"
    for row in corpus["cuts"]:
        if row["programme_id"] == "pg01" and int(row["shot_ordinal"]) == 1:
            row["reel_id"] = "el999"
        elif row["programme_id"] == "pg02" and int(row["shot_ordinal"]) == 1:
            row["reel_id"] = retired_reel
        elif row["programme_id"] == "pg03" and int(row["shot_ordinal"]) == 1:
            row["out_frame"] = row["in_frame"]
    corpus["cuts"] = [r for r in corpus["cuts"] if r["programme_id"] != "pg04"]
    return corpus


DATA_SHA256 = {
    "calibration_cut_list.csv": "ad7a82197575246aa2685afdd9ef7b26b1a4b59ab3643064672d62c84aaee1ac",
    "calibration_defect_log.csv": "67b855a30cba78f46dab9123d6eac7baf0aba9e19faf186d89894d4c7fd648a3",
    "calibration_holders.csv": "fe985007b03728b7807aff30e3cdade8d879466030fb2b8bf7d1c838928cf723",
    "calibration_lane_charter.json": "9d47228cc1452a2ef8d380d8272197413b23fceabc99b08278ac73b3281ebe85",
    "calibration_lineage_events.csv": "7275f41652087bcec341f88b3e8e7db2e0c4b5e5c03afae2eacdca47b6458d5c",
    "calibration_programmes.csv": "f80213d80a369a411e6cef7ef94d388935150e4e1ab07787736398edc2f44575",
    "calibration_reel_scans.csv": "9723b447635759f00145437521ac6f56bad27b0177452f5ec9d74c4f88ddbc11",
    "calibration_repair_log.csv": "d866bbcd94a4fc2bbd4c71c5e6e4d453d28942de5801eb0aee7c630e7415486a",
    "calibration_slice.md": "6204f5b043575931ad3afb7e181449fc47fa4328fc076ffc8c719196a8618e48",
    "calibration_vault_charter.json": "9df6642c391ac94695f412c0c4b5189c30185a9bc46c982776b51e9e3be0e338",
    "cut_list.csv": "3ce6e4b680da5dd06a724bc2e56243dcdb48d565f3555db441223157b8e15f03",
    "defect_log.csv": "1d283fcd94e2b507607cc192e5292bcb6e25dade278207830235cb2e042fd561",
    "delivery_schedule.md": "1bb6ad413c2c4dc46083ae681a6a13cf160bb9db2fbd4b59b8096aa458d5e341",
    "example_vault_report.json": "dcbf50a9d398817c1d35318f1b2699772bbb32bb69f55f5ac54980f6d6c10220",
    "holders.csv": "37b36768b51cafd3e3e281840caa4b0599228fcc092976d034eb0987bbe2db8d",
    "invariants.md": "7567b2efb2c502d09fb6b8368cc26edf0e76f9dbeff82f64a374a71a3a82cd0a",
    "lane_charter.json": "1fab5e52a2015a63bff0c77cc448bb0d9cc1b33365b8cb98c026708ca9b40164",
    "lineage_events.csv": "56eabe018e60200f9d9c346a9d0407072f5bc3264354bed99512ed8dad55355f",
    "programmes.csv": "ad349ae21250e77d95a9b8c094aae0c2b7b300cbde6d0a4674d453870109d046",
    "reel_scans.csv": "750e7e5938cd1bee2532c5fa9d2c741f378dc2725e1aab69e4fc66c8d7b50964",
    "repair_log.csv": "2e765f0841fd788943c12df85b21bcabcdde7fbbb9b5806f9b712111e434b2a6",
    "rulebook_allocation.md": "7ef140a204023159e5fd20c7c267d17bb76627c696414c2c1b2ebbc352565f56",
    "rulebook_cadence.md": "19e40a4ac3dd44960dbe87f77b8af59d9c24498754ad21c0924f38721b44d0f0",
    "rulebook_conform.md": "fae82310dda3e5aba6fcb949fc36561309882c3fad5bddab1905911babfec9bd",
    "rulebook_defect.md": "d6db01cd820761c9f46ece15f91dfb153e0fe32aa4fac954403c4311a34b3d7f",
    "rulebook_identity.md": "8db8df25e17267c2fb5a1345f08732f87c11302cc836d2d74545d23de10164cf",
    "rulebook_repair.md": "e87aaad72f6a75ca391703bb6134bd61c2bae6f5a1db11337abc91d23f6c49b7",
    "vault_charter.json": "74f9f1e890e2a73566cb4ec0a45ce3f0fbfec3ec8b7642b0a54ce78e4459cf39",
}


def _catalogue_intact(workspace):
    agent_data = _agent_data(workspace)
    if not agent_data.is_dir():
        return False
    present = sorted(p.name for p in agent_data.iterdir() if p.is_file())
    if present != sorted(DATA_SHA256):
        return False
    for name, digest in DATA_SHA256.items():
        try:
            blob = (agent_data / name).read_bytes()
        except OSError:
            return False
        if hashlib.sha256(blob).hexdigest() != digest:
            return False
    return True


def _partition_names(reports):
    names = {k for k in reports if k.startswith(("vault_", "lane_"))}
    names.discard("vault_index.json")
    return names


def _naive_impairment():
    """Per-programme impairment if overlapping defects were added rather than merged."""
    ref = _reference()
    tally = {}
    for record in ref["defect_findings.json"]["defects"]:
        pid = record["programme_id"]
        tally[pid] = tally.get(pid, 0) + record["clipped_frames"]
    return tally


# ---------------------------------------------------------------------------
# graded checks
#
# One checker per observable. Each check is a top-level @criterion function of
# workspace, returns a bool, and never raises: an exception inside a check
# aborts the whole rewardkit run and leaves no reward behind.
# ---------------------------------------------------------------------------


@criterion(description="a reusable settlement program was delivered")
def settlement_program_present(workspace: Path) -> bool:
    try:
        program = _program(workspace)
        return program.is_file() and program.stat().st_size > 0
    except Exception:
        return False


@criterion(description="every core report is present and parses as a JSON object")
def core_reports_parse(workspace: Path) -> bool:
    try:
        got = _delivered(workspace)
        return all(isinstance(got.get(name), dict) for name in CORE_REPORTS)
    except Exception:
        return False


@criterion(description="at least one vault report and one lane report were delivered")
def partition_reports_present(workspace: Path) -> bool:
    try:
        names = _partition_names(_delivered(workspace))
        return any(n.startswith("vault_") for n in names) and any(
            n.startswith("lane_") for n in names
        )
    except Exception:
        return False


@criterion(description="the reel audit settles canonical identity, folding and retirement")
def identity_resolved(workspace: Path) -> bool:
    try:
        return _agrees(
            workspace,
            "reel_audit.json",
            "canonical_elements",
            "folded_elements",
            "retired_elements",
            "settlement_cycle",
        )
    except Exception:
        return False


@criterion(
    description="every reel carries its accumulated registration shift and state, "
    "and each survivor supplies the union of what folded into it"
)
def usable_spans_measured(workspace: Path) -> bool:
    try:
        if not _agrees(workspace, "reel_audit.json", "usable_frames", "reels"):
            return False
        ref = _reference()["reel_audit.json"]
        got = _got(workspace, "reel_audit.json")
        if not isinstance(got, dict):
            return False
        folded = ref["folded_elements"]
        if not folded:
            return False
        for survivor in folded:
            if ref["usable_frames"].get(survivor, 0) < 1:
                return False
            if got["usable_frames"].get(survivor) != ref["usable_frames"][survivor]:
                return False
        return True
    except Exception:
        return False


@criterion(
    description="every shot is placed on its programme timeline, the voids carry "
    "their reasons, and the kept shot ordinals tile from one without a gap"
)
def shots_conformed(workspace: Path) -> bool:
    try:
        ref = _reference()["conform_report.json"]
        got = _got(workspace, "conform_report.json")
        if not isinstance(got, dict) or not isinstance(got.get("programmes"), list):
            return False
        if got.get("programmes") != ref["programmes"]:
            return False
        if got.get("void_programmes") != ref["void_programmes"]:
            return False
        if got.get("conformed_programmes") != ref["conformed_programmes"]:
            return False
        for record in got["programmes"]:
            shots = record.get("shots") or []
            if not shots:
                continue
            ordinals = [s.get("shot_ordinal") for s in shots]
            if ordinals != list(range(1, len(shots) + 1)):
                return False
            cursor = 0
            for shot in shots:
                if shot.get("timeline_start") != cursor:
                    return False
                cursor = shot.get("timeline_stop")
        return True
    except Exception:
        return False


@criterion(description="every defect is clipped onto its host shot")
def defects_clipped(workspace: Path) -> bool:
    try:
        ref = _reference()["defect_findings.json"]["defects"]
        got = _got(workspace, "defect_findings.json")
        if not isinstance(got, dict):
            return False
        return got.get("defects") == ref
    except Exception:
        return False


@criterion(
    description="impairment matches the reference per programme and in total, and "
    "frames covered by several defects are impaired once rather than once each"
)
def impairment_settled(workspace: Path) -> bool:
    try:
        ref = _reference()["defect_findings.json"]
        got = _got(workspace, "defect_findings.json")
        conform = _got(workspace, "conform_report.json")
        if not isinstance(got, dict) or not isinstance(conform, dict):
            return False
        covered = got.get("impaired_frames")
        if not isinstance(covered, dict):
            return False
        if covered != ref["impaired_frames"]:
            return False
        if got.get("impaired_total") != ref["impaired_total"]:
            return False
        if got.get("impaired_total") != sum(covered.values()):
            return False
        if sorted(covered) != sorted(conform.get("conformed_programmes", [])):
            return False
        naive = _naive_impairment()
        overlapping = [
            pid
            for pid, total in naive.items()
            if total > ref["impaired_frames"].get(pid, 0)
        ]
        if len(overlapping) < 3:
            return False
        for pid in overlapping:
            if covered.get(pid, 0) >= naive[pid]:
                return False
        return True
    except Exception:
        return False


@criterion(
    description="every repair carries its settled state and the frames it earns, "
    "and a repair that stands for nothing recovers nothing"
)
def repairs_adjudicated(workspace: Path) -> bool:
    try:
        ref = _reference()["repair_ledger.json"]
        got = _got(workspace, "repair_ledger.json")
        if not isinstance(got, dict) or not isinstance(got.get("repairs"), list):
            return False
        if not _agrees(
            workspace,
            "repair_ledger.json",
            "repairs",
            "recovered_frames",
            "recovered_total",
        ):
            return False
        if got.get("state_counts") != ref["state_counts"]:
            return False
        voids = [s for s in ref["state_counts"] if s not in ("accepted", "clamped")]
        if len(voids) < 2:
            return False
        for record in got["repairs"]:
            if record.get("state") in voids and record.get("recovered_frames") != 0:
                return False
        clamped = [r for r in ref["repairs"] if r["state"] == "clamped"]
        return len(clamped) >= 3
    except Exception:
        return False


@criterion(
    description="every programme is measured at its delivery cadence rather than "
    "its element's, and the governing element of each is settled"
)
def cadence_converted(workspace: Path) -> bool:
    try:
        ref = _reference()["cadence_ledger.json"]
        got = _got(workspace, "cadence_ledger.json")
        if not isinstance(got, dict) or not isinstance(got.get("programmes"), list):
            return False
        want = {
            r["programme_id"]: (
                r["source_frames"],
                r["cadence_frames"],
                r["governing_element"],
            )
            for r in ref["programmes"]
        }
        have = {
            r.get("programme_id"): (
                r.get("source_frames"),
                r.get("cadence_frames"),
                r.get("governing_element"),
            )
            for r in got["programmes"]
            if isinstance(r, dict)
        }
        if have != want:
            return False
        if got.get("cadence_total") != ref["cadence_total"]:
            return False
        diverging = [
            r
            for r in ref["programmes"]
            if r["element_cadence_mhz"] != r["delivery_cadence_mhz"]
        ]
        if len(diverging) < 3:
            return False
        for record in diverging:
            if record["cadence_frames"] == record["source_frames"]:
                return False
        return True
    except Exception:
        return False


@criterion(
    description="every programme carries the condition grade that reproduces "
    "itself once its own credit is applied"
)
def condition_grades_settled(workspace: Path) -> bool:
    try:
        ref = _reference()["cadence_ledger.json"]["programmes"]
        got = _got(workspace, "cadence_ledger.json")
        if not isinstance(got, dict) or not isinstance(got.get("programmes"), list):
            return False
        want = {r["programme_id"]: r["condition_grade"] for r in ref}
        have = {
            r.get("programme_id"): r.get("condition_grade")
            for r in got["programmes"]
            if isinstance(r, dict)
        }
        if have != want:
            return False
        for record in got["programmes"]:
            grade = record.get("condition_grade")
            settled = record.get("settled_frames")
            cadence = record.get("cadence_frames")
            if not isinstance(settled, int) or not isinstance(cadence, int):
                return False
            if band_of(settled, cadence) != grade:
                return False
        return True
    except Exception:
        return False


@criterion(description="the settled frame count of every programme is exact")
def settled_frames_fixed(workspace: Path) -> bool:
    try:
        return _agrees(
            workspace,
            "cadence_ledger.json",
            "programmes",
            "settled_total",
            "source_total",
        )
    except Exception:
        return False


@criterion(description="the admitted set, the held set and the drawing set are settled")
def admission_settled(workspace: Path) -> bool:
    try:
        return _agrees(
            workspace,
            "allocation_ledger.json",
            "admitted",
            "held",
            "drawing_holders",
            "group_quota",
            "group_used",
            "draw_order",
        )
    except Exception:
        return False


@criterion(
    description="every admitted programme sits in its settled vault, within that "
    "vault's capacity and among the classes and groups it accepts"
)
def vaults_seated(workspace: Path) -> bool:
    try:
        ref = _reference()
        got = _delivered(workspace)
        if not _agrees(workspace, "vault_index.json", "vaults", "seated_total_frames"):
            return False
        wanted = {n for n in _partition_names(ref) if n.startswith("vault_")}
        if {n for n in _partition_names(got) if n.startswith("vault_")} != wanted:
            return False
        seated = {}
        for name in sorted(wanted):
            report = got.get(name)
            if not isinstance(report, dict) or report != ref[name]:
                return False
            load = 0
            for record in report.get("programmes", []):
                seated[record["programme_id"]] = name
                load += record["settled_frames"]
                if record["deliverable_class"] not in report["accepts_classes"]:
                    return False
                if record["settlement_group"] not in report["settlement_groups"]:
                    return False
            if load != report["load_frames"]:
                return False
            if load > report["capacity_frames"]:
                return False
        return sorted(seated) == ref["allocation_ledger.json"]["admitted"]
    except Exception:
        return False


@criterion(
    description="the residual pool passes down the lanes in rank order and the "
    "remainder is shed"
)
def lane_cascade_seats_in_rank_order(workspace: Path) -> bool:
    try:
        ref = _reference()
        got = _delivered(workspace)
        index = got.get("vault_index.json")
        summary = got.get("summary.json")
        if not isinstance(index, dict) or not isinstance(summary, dict):
            return False
        if index.get("residual_pool_frames") != ref["vault_index.json"][
            "residual_pool_frames"
        ]:
            return False
        wanted = {n for n in _partition_names(ref) if n.startswith("lane_")}
        if {n for n in _partition_names(got) if n.startswith("lane_")} != wanted:
            return False
        lanes = sorted(
            (got[n] for n in wanted if isinstance(got.get(n), dict)),
            key=lambda ln: (ln.get("lane_rank"), ln.get("lane_id")),
        )
        if len(lanes) != len(wanted):
            return False
        pool = index["residual_pool_frames"]
        seated = 0
        for lane in lanes:
            reference_lane = ref.get("lane_" + str(lane.get("lane_id")) + ".json")
            if lane != reference_lane:
                return False
            if lane["capacity_frames"] > pool:
                return False
            if lane["load_frames"] > lane["capacity_frames"]:
                return False
            pool -= lane["load_frames"]
            seated += len(lane.get("programmes", []))
        if summary.get("lane_seated_count") != seated:
            return False
        if summary.get("shed_frames") != ref["summary.json"]["shed_frames"]:
            return False
        if summary.get("shed_count") != ref["summary.json"]["shed_count"]:
            return False
        return True
    except Exception:
        return False


@criterion(description="the cycle ledger reconciles")
def cycle_ledger_reconciles(workspace: Path) -> bool:
    try:
        return _agrees(workspace, "reconciliation.json") and _agrees(
            workspace, "summary.json"
        )
    except Exception:
        return False


@criterion(
    description="a print element never governs a programme while another class "
    "supplies the cut, on this catalogue and on one where print must govern"
)
def governing_element_excludes_print(workspace: Path) -> bool:
    try:
        ref = _reference()
        got = _got(workspace, "cadence_ledger.json")
        if not isinstance(got, dict) or not isinstance(got.get("programmes"), list):
            return False
        classes = {
            r["reel_id"]: r["element_class"] for r in ref["reel_audit.json"]["reels"]
        }
        want = {
            r["programme_id"]: (r["governing_element"], r["element_cadence_mhz"])
            for r in ref["cadence_ledger.json"]["programmes"]
        }
        have = {
            r.get("programme_id"): (
                r.get("governing_element"),
                r.get("element_cadence_mhz"),
            )
            for r in got["programmes"]
            if isinstance(r, dict)
        }
        if have != want:
            return False
        shots = {
            r["programme_id"]: r["shots"]
            for r in ref["conform_report.json"]["programmes"]
        }
        for pid, (element, _cadence) in want.items():
            supplying = {s["canonical_id"] for s in shots.get(pid, [])}
            if any(classes.get(e) != "print" for e in supplying):
                if classes.get(element) == "print":
                    return False
        return _generalises(
            workspace, _mutate_print_governs, names=["cadence_ledger.json"]
        )
    except Exception:
        return False


@criterion(
    description="a settlement group's draw stops dead at the first programme that "
    "overruns it, on this catalogue and on one where the prefix moves"
)
def admission_closes_as_a_prefix(workspace: Path) -> bool:
    try:
        ref = _reference()["allocation_ledger.json"]
        got = _got(workspace, "allocation_ledger.json")
        if not isinstance(got, dict) or not isinstance(got.get("draw_order"), list):
            return False
        for key in ("draw_order", "admitted", "held", "drawing_holders"):
            if got.get(key) != ref[key]:
                return False
        seen_hold = set()
        for record in got["draw_order"]:
            group = record.get("settlement_group")
            if record.get("state") == "held":
                seen_hold.add(group)
            elif group in seen_hold:
                return False
        holders = {r["programme_id"]: r["holder_id"] for r in ref["draw_order"]}
        drawn = sorted({holders[p] for p in ref["admitted"]})
        if got["drawing_holders"] != drawn:
            return False
        return _generalises(
            workspace, _mutate_prefix_binding, names=["allocation_ledger.json"]
        )
    except Exception:
        return False


@criterion(description="every delivered report is written in the catalogue's own form")
def canonical_serialisation(workspace: Path) -> bool:
    try:
        out = _out(workspace)
        if not out.is_dir():
            return False
        names = sorted(p for p in os.listdir(str(out)) if p.endswith(".json"))
        if not names:
            return False
        for name in names:
            blob = (out / name).read_bytes()
            parsed = json.loads(blob.decode("utf-8"))
            if blob != dump(parsed).encode("utf-8"):
                return False
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# generalisation - the delivered program must settle catalogues it has not seen
# ---------------------------------------------------------------------------


@criterion(description="settles a catalogue where two elements supply a programme equally")
def generalises_tie_configuration(workspace: Path) -> bool:
    try:
        return _generalises(workspace, _mutate_tie_configuration)
    except Exception:
        return False


@criterion(description="settles a catalogue whose vault capacities moved across the seating")
def generalises_value_pushed_across_a_cap(workspace: Path) -> bool:
    try:
        return _generalises(workspace, _mutate_value_across_a_cap)
    except Exception:
        return False


@criterion(description="settles a catalogue where the repair passes were reordered")
def generalises_rule_precedence_inverted(workspace: Path) -> bool:
    try:
        return _generalises(workspace, _mutate_rule_precedence_inverted)
    except Exception:
        return False


@criterion(description="settles a catalogue where one settlement group draws nothing")
def generalises_group_emptied(workspace: Path) -> bool:
    try:
        return _generalises(workspace, _mutate_group_emptied)
    except Exception:
        return False


@criterion(description="settles a catalogue whose lineage book closes a loop out of cycle")
def generalises_cycle_introduced(workspace: Path) -> bool:
    try:
        return _generalises(workspace, _mutate_cycle_introduced)
    except Exception:
        return False


@criterion(description="settles a catalogue whose repair windows all close one cycle sooner")
def generalises_temporal_boundary_shifted(workspace: Path) -> bool:
    try:
        return _generalises(workspace, _mutate_temporal_boundary)
    except Exception:
        return False


@criterion(description="settles a catalogue with a new holder that moves the drawing set")
def generalises_entity_added_moves_the_fixpoint(workspace: Path) -> bool:
    try:
        return _generalises(workspace, _mutate_entity_added)
    except Exception:
        return False


@criterion(description="settles a catalogue where a programme is cut wholly from print")
def generalises_non_applying_rule_exercised(workspace: Path) -> bool:
    try:
        return _generalises(workspace, _mutate_non_applying_rule)
    except Exception:
        return False


@criterion(description="settles a catalogue whose programmes changed conversion direction")
def generalises_counterfactual_boundary_crossed(workspace: Path) -> bool:
    try:
        return _generalises(workspace, _mutate_counterfactual_boundary)
    except Exception:
        return False


@criterion(description="settles a catalogue with a different number of vaults and lanes")
def generalises_partition_count_changed(workspace: Path) -> bool:
    try:
        return _generalises(workspace, _mutate_partition_count)
    except Exception:
        return False


@criterion(
    description="settles a catalogue that puts all six void conditions in play, "
    "including an element no identity resolves to and a programme with no shots"
)
def generalises_every_void_reason(workspace: Path) -> bool:
    try:
        return _generalises(workspace, _mutate_every_void_reason)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# negative detectors - each holds when the cheat happened
# ---------------------------------------------------------------------------


@criterion(description="the settled figures were written into the program as literals")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        program = _program(workspace)
        if not program.is_file():
            return False  # nothing delivered is graded elsewhere, not as this cheat
        source = program.read_text(encoding="utf-8", errors="replace")
        ref = _reference()
        marks = {
            str(ref["summary.json"]["settled_total"]),
            str(ref["summary.json"]["impaired_total"]),
            str(ref["summary.json"]["recovered_total"]),
        }
        for record in ref["cadence_ledger.json"]["programmes"]:
            marks.add(str(record["settled_frames"]))
        hits = sum(1 for mark in sorted(marks) if mark in source)
        return hits >= 2
    except Exception:
        return False


@criterion(description="the settlement changes with the name of the directory it is read from")
def negative_filename_dependent_behaviour(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    # Both sides are runs of the delivered program over identical bytes at two
    # different paths, so a correctness slip or a hand-edited report cannot fire
    # this: only the path the catalogue sits at differs between the two runs.
    # A program whose output is unstable run to run would differ for a reason
    # that has nothing to do with the path, so two runs at the SAME path are
    # taken first and the detector stands down when those already disagree.
    # Nondeterminism is then priced once, by its own negative.
    work = None
    try:
        program = _program(workspace)
        if not program.is_file():
            return False  # nothing delivered is graded elsewhere, not as this cheat
        work = tempfile.mkdtemp(prefix="rename-")
        first_cat = os.path.join(work, "alpha", "catalogue")
        second_cat = os.path.join(work, "zulu-somewhere-else", "reel-archive")
        os.makedirs(os.path.dirname(first_cat), exist_ok=True)
        os.makedirs(os.path.dirname(second_cat), exist_ok=True)
        shutil.copytree(str(_data_root()), first_cat)
        shutil.copytree(str(_data_root()), second_cat)
        steady_a = os.path.join(work, "steady-a")
        steady_b = os.path.join(work, "steady-b")
        if not _run_program(workspace, first_cat, steady_a):
            return False
        if not _run_program(workspace, first_cat, steady_b):
            return False
        if _collect(steady_a) != _collect(steady_b):
            return False
        first_out = os.path.join(work, "out-a")
        second_out = os.path.join(work, "out-b")
        if not _run_program(workspace, first_cat, first_out):
            return False
        if not _run_program(workspace, second_cat, second_out):
            return False
        left = _collect(first_out)
        right = _collect(second_out)
        if not left or not right:
            return False
        return left != right
    except Exception:
        return False
    finally:
        if work:
            shutil.rmtree(work, ignore_errors=True)


@criterion(description="two runs over the same catalogue disagree")
def negative_nondeterministic_output(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    work = None
    try:
        program = _program(workspace)
        if not program.is_file():
            return False  # nothing delivered is graded elsewhere, not as this cheat
        work = tempfile.mkdtemp(prefix="rerun-")
        first = os.path.join(work, "a")
        second = os.path.join(work, "b")
        if not _run_program(workspace, str(_data_root()), first):
            return False
        if not _run_program(workspace, str(_data_root()), second):
            return False
        left = _collect(first)
        right = _collect(second)
        if not left or not right:
            return False
        return left != right
    except Exception:
        return False
    finally:
        if work:
            shutil.rmtree(work, ignore_errors=True)


@criterion(description="the shipped catalogue was altered, which the instruction forbids")
def negative_catalogue_modified(workspace: Path) -> bool:
    # Holds when the cheat happened; the negative weight does the punishing.
    try:
        if not _program(workspace).is_file():
            return False  # nothing delivered is graded elsewhere, not as this cheat
        return not _catalogue_intact(workspace)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# weight registrations - the weight lives here and nowhere else
#
# positive total 121, sum of absolute negative weights 10
# ---------------------------------------------------------------------------

criteria.settlement_program_present(weight=1)
criteria.core_reports_parse(weight=1)
criteria.partition_reports_present(weight=1)
criteria.identity_resolved(weight=1)
criteria.usable_spans_measured(weight=5)
criteria.shots_conformed(weight=5)
criteria.defects_clipped(weight=1)
criteria.impairment_settled(weight=5)
criteria.repairs_adjudicated(weight=5)
criteria.cadence_converted(weight=5)
criteria.condition_grades_settled(weight=5)
criteria.settled_frames_fixed(weight=5)
criteria.admission_settled(weight=5)
criteria.vaults_seated(weight=5)
criteria.lane_cascade_seats_in_rank_order(weight=5)
criteria.cycle_ledger_reconciles(weight=3)
criteria.governing_element_excludes_print(weight=5)
criteria.admission_closes_as_a_prefix(weight=5)
criteria.canonical_serialisation(weight=1)
criteria.generalises_tie_configuration(weight=5)
criteria.generalises_value_pushed_across_a_cap(weight=5)
criteria.generalises_rule_precedence_inverted(weight=5)
criteria.generalises_group_emptied(weight=5)
criteria.generalises_cycle_introduced(weight=5)
criteria.generalises_temporal_boundary_shifted(weight=5)
criteria.generalises_entity_added_moves_the_fixpoint(weight=5)
criteria.generalises_non_applying_rule_exercised(weight=5)
criteria.generalises_counterfactual_boundary_crossed(weight=5)
criteria.generalises_partition_count_changed(weight=5)
criteria.generalises_every_void_reason(weight=5)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_filename_dependent_behaviour(weight=-3)
criteria.negative_nondeterministic_output(weight=-1)
criteria.negative_catalogue_modified(weight=-1)
