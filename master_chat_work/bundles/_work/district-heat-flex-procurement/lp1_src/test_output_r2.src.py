"""Verifier for district-heat-flex-procurement.

Every value check reruns the submitted derive_report.py, as an unprivileged user, on an
extract built here and compares its reports with an independent reference implementation
of schema.md. Two kinds of extract are used. Four composed extracts carry many events at
once and are graded as whole documents (all region files, both segment files, the summary
with the audit, the data-quality file), so one misread rule reaches every document it
touches. Eight small hand-built extracts each isolate one rule. Before a check runs, it
confirms that the tempting wrong reading of every rule it names would change the document
it grades, so the extract really separates the readings. Four format checks read the
reports the agent wrote into /app/out; they never compare values.

Negative checks return True when the cheat is present; their negative weight does the
punishing, so an honest submission leaves them False.
"""

from __future__ import annotations

import ast
import base64
import configparser
import csv
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ElementTree
import zlib
from pathlib import Path
from typing import Any

from rewardkit import criteria, criterion

EVAL_SEED = 2293030145355477831

ARTIFACT_JSON = ["summary.json", "policy_audit.json", "data_quality.json", "region_North.json",
                 "region_South.json", "region_West.json", "region_East.json",
                 "segment_commercial.json", "segment_public.json"]
REGION_CODES = {"North": ("N1", "N2"), "South": ("S1", "S2"), "West": ("W1", "W2"), "East": ("E1", "E2")}
SEGMENT_CODES = {"C": "commercial", "P": "public"}
RANKING = ["SAFETY_HOLD", "COOLDOWN", "CONTINUITY_WAIVED", "CERTIFICATE_PENDING", "CLEAR"]
# Every tempting wrong reading the reference can switch on, one flag per reading.
ALL_FLAGS = frozenset({"H1", "H1order", "H1hc", "H1pend", "SIGNEDY", "H2", "H3", "H4", "H5t", "H5c", "DH2", "DH3",
                       "DH4dup", "DH4range", "DH4unknown", "DH5raw", "C34", "C45", "C5drop", "W0LIST"})
# Wrong readings that change which offers the search picks (the others only change what is reported).
SEARCH_FLAGS = frozenset({"DH2", "H2", "C34", "C45", "C5drop", "DH4dup", "DH4range", "DH4unknown"})
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_AGENT_UID = 65534
_AGENT_TIMEOUT = 120

_SHIPPED_DATA: dict[str, str] = {}

_LOCK = threading.RLock()
_CACHE: dict[Any, Any] = {}
_SEARCH_MEMO: dict[Any, Any] = {}


# ---------------------------------------------------------------- arithmetic

def _q(num: int, den: int) -> int:
    """Round num/den half up (num, den >= 0)."""
    whole, rest = divmod(num, den)
    return whole + (1 if 2 * rest >= den else 0)


class Rng:
    __slots__ = ("state",)

    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFFFFFFFFFF or 0xA0761D6478BD642F

    def _next(self) -> int:
        x = self.state
        x ^= (x >> 12) & 0xFFFFFFFFFFFFFFFF
        x ^= (x << 25) & 0xFFFFFFFFFFFFFFFF
        x ^= (x >> 27) & 0xFFFFFFFFFFFFFFFF
        self.state = x
        return (x * 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def between(self, lo: int, hi: int) -> int:
        return lo + self._next() % (hi - lo + 1)

    def pick(self, seq):
        return seq[self._next() % len(seq)]

    def chance(self, percent: int) -> bool:
        return self._next() % 100 < percent

    def shuffle(self, items: list) -> None:
        for i in range(len(items) - 1, 0, -1):
            j = self._next() % (i + 1)
            items[i], items[j] = items[j], items[i]


# ---------------------------------------------------------------- reference

def _records(path: Path, sep: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(path.read_text(encoding="utf-8")), delimiter=sep))


def _columns(path: Path, cuts: list[tuple[int, int]]) -> list[list[str]]:
    out = []
    for raw in path.read_text(encoding="utf-8").split("\n"):
        if raw.strip() and not raw.startswith("#"):
            out.append([raw[a - 1:b].strip() for a, b in cuts])
    return out


def reference(root: Path, lazy: frozenset = frozenset()) -> dict[str, Any]:
    """Every report the contract defines, computed from the files under root.

    `lazy` switches individual rules to their tempting wrong reading, so a case
    can prove that it separates the two readings."""
    cfg = configparser.ConfigParser()
    cfg.read_string((root / "program.ini").read_text(encoding="utf-8"))
    wh_tick = int(cfg["units"]["wh_per_tick"])
    mc_cent = int(cfg["units"]["millicents_per_cent"])
    code_region = {k.upper(): v for k, v in cfg["region_codes"].items()}
    code_segment = {k.upper(): v for k, v in cfg["segment_codes"].items()}
    region_names = sorted(set(code_region.values()))
    segment_names = sorted(set(code_segment.values()))

    def tk(wh: int) -> int:
        return _q(wh, wh_tick)

    event_list = sorted(json.loads((root / "events.json").read_text(encoding="utf-8")), key=lambda e: e["event_id"])
    count = {"events.json": len(event_list)}
    span = {e["event_id"]: int(e["interval_count"]) for e in event_list}

    site_rows = _records(root / "sites.csv", ",")
    count["sites.csv"] = len(site_rows)
    site: dict[tuple[str, str], dict[str, Any]] = {}
    unknown = 0
    for r in site_rows:
        region = code_region.get(r["region_code"].upper())
        if region is None:
            if "DH4unknown" not in lazy:
                unknown += 1
                continue
            region = "?"
        site[(r["event_id"], r["site_id"])] = {
            "event_id": r["event_id"], "sid": r["site_id"], "region": region,
            "segment": code_segment[r["segment_code"].upper()], "ben": r["beneficiary_id"],
            "critical": r["critical"] == "Y", "weight": None, "auth": False, "hold": False, "cool": False,
            "pending": False, "status": "NONE", "signed": "", "base": 0, "cap": 0,
        }
    states = [json.loads(x) for x in (root / "site_state.jsonl").read_text(encoding="utf-8").split("\n") if x.strip()]
    count["site_state.jsonl"] = len(states)
    for s in states:
        if (s["event_id"], s["site_id"]) in site:
            site[(s["event_id"], s["site_id"])].update(auth=bool(s["dispatch_authorized"]), hold=bool(s["safety_hold"]),
                                                       cool=bool(s["cooldown"]))
    waiver_rows = _records(root / "continuity_waivers.csv", ",")
    count["continuity_waivers.csv"] = len(waiver_rows)
    blank_signed = 0
    for w in waiver_rows:
        signed = (w["waiver_signed"] or "").strip()
        blank_signed += not signed
        if (w["event_id"], w["site_id"]) in site:
            site[(w["event_id"], w["site_id"])].update(pending=w["routine_certificate_pending"] == "Y",
                                                       status=w["waiver_status"], signed=signed)
    card_nodes = list(ElementTree.fromstring((root / "rate_cards.xml").read_text(encoding="utf-8")).iter("card"))
    count["rate_cards.xml"] = len(card_nodes)
    for node in card_nodes:
        if (node.attrib["event"], node.attrib["site"]) in site:
            site[(node.attrib["event"], node.attrib["site"])].update(base=int(node.find("base").text),
                                                                     cap=int(node.find("cap").text))
    weight_rows = _records(root / "recipient_weights.tsv", "\t")
    count["recipient_weights.tsv"] = len(weight_rows)
    for w in weight_rows:
        if (w["event_id"], w["site_id"]) in site:
            site[(w["event_id"], w["site_id"])]["weight"] = int(w["grant_weight"])

    offer_rows = _records(root / "offers.csv", ",")
    count["offers.csv"] = len(offer_rows)
    listed = {r["offer_id"]: r["event_id"] for r in offer_rows}
    offer: dict[str, dict[str, Any]] = {}
    lost_offers = 0
    for r in offer_rows:
        owner = site.get((r["event_id"], r["site_id"]))
        if owner is None:
            lost_offers += 1
            continue
        width = span[r["event_id"]]
        offer[r["offer_id"]] = {"id": r["offer_id"], "site": owner, "cost": int(r["bid_cost_cents"]),
                                "r": [0] * width, "v": [0] * width}
    profile_rows = _records(root / "profiles.tsv", "\t")
    count["profiles.tsv"] = len(profile_rows)
    lost_profiles = out_of_range = repeats = 0
    seen: set[tuple[str, int]] = set()
    for r in profile_rows:
        oid, itv = r["offer_id"], int(r["interval"])
        if oid not in listed:
            lost_profiles += 1
            continue
        width = span[listed[oid]]
        if "DH4range" in lazy:
            if itv - 1 >= width:
                continue
        elif not 1 <= itv <= width:
            out_of_range += 1
            continue
        if "DH4dup" not in lazy:
            if (oid, itv) in seen:
                repeats += 1
                continue
            seen.add((oid, itv))
        if oid in offer:
            offer[oid]["r"][itv - 1] = int(r["relief_wh"])
            offer[oid]["v"][itv - 1] = int(r["recovery_wh"])

    target_rows = _records(root / "targets.tsv", "\t")
    count["targets.tsv"] = len(target_rows)
    goal = {(r["event_id"], code_region[r["region_code"].upper()], int(r["interval"])):
            (tk(int(r["target_wh"])), int(r["shortfall_weight"])) for r in target_rows}
    feeder = _columns(root / "feeder_limits.txt", [(1, 10), (11, 14), (15, 17), (18, 27), (28, 37)])
    count["feeder_limits.txt"] = len(feeder)
    limit = {(a, code_region[b.upper()], int(c)): (tk(int(d)), tk(int(e))) for a, b, c, d, e in feeder}
    floor_list = json.loads((root / "segment_floors.json").read_text(encoding="utf-8"))["floors"]
    count["segment_floors.json"] = len(floor_list)
    floor = {(f["event_id"], code_region[f["region_code"].upper()], code_segment[f["segment_code"].upper()]):
             (tk(int(f["floor_wh"])), int(f["priority_weight"])) for f in floor_list}
    pool_lines = _columns(root / "pools.txt", [(1, 10), (11, 14), (15, 26)])
    count["pools.txt"] = len(pool_lines)
    pool = {(a, code_region[b.upper()]): int(c) for a, b, c in pool_lines}

    def label(s: dict[str, Any]) -> str:
        signed_ok = s["signed"] == "Y" or ("SIGNEDY" in lazy and s["signed"] == "")
        valid = s["status"] == "VALID" and signed_ok and s["critical"] and s["segment"] == "public"
        if "H1" in lazy:
            valid = False
        waived = s["pending"] and valid
        if "H1order" in lazy and waived:
            return "CONTINUITY_WAIVED"
        first, second = ("cool", "hold") if "H1hc" in lazy else ("hold", "cool")
        for key in (first, second):
            if s[key]:
                return "SAFETY_HOLD" if key == "hold" else "COOLDOWN"
        if waived:
            return "CONTINUITY_WAIVED"
        if "H1pend" in lazy:
            return "CLEAR"
        return "CERTIFICATE_PENDING" if s["pending"] else "CLEAR"

    def heft_of(s: dict[str, Any]) -> int:
        if "DH5raw" in lazy:
            raw = (s["pending"] and s["status"] == "VALID" and s["signed"] == "Y" and s["critical"]
                   and s["segment"] == "public")
            return 2 * s["weight"] if raw else s["weight"]
        if "DH5none" in lazy or "DH5ben" in lazy:
            return s["weight"]
        return 2 * s["weight"] if label(s) == "CONTINUITY_WAIVED" else s["weight"]

    def reported(parts: list[int]) -> int:
        # raw Wh values; each becomes ticks before summing unless H5t is lazy
        return tk(sum(parts)) if "H5t" in lazy else sum(tk(p) for p in parts)

    def rate(s: dict[str, Any], uplift: int) -> int:
        if "H3" in lazy:
            return min(s["base"], s["cap"]) + uplift
        return min(s["base"] + uplift, s["cap"])

    scale = wh_tick if "DH2" in lazy else 1

    def unit(wh: int) -> int:
        return wh if scale != 1 else tk(wh)

    def measure(units: int) -> int:
        return tk(units) if scale != 1 else units

    def search(cands: list[dict[str, Any]], goals, caps, floors_here, cw: int, vw: int, width: int):
        """Exact optimum by merging partial portfolios on their full future-relevant state.

        Sites are taken in descending id order. A state holds relief and recovery per
        interval and segment relief capped at its floor; for one state only the lowest
        (cost_weight times bid cost, count) can still win, and among equals the smallest and greatest sorted
        id tuples are kept with the number of portfolios that reach it."""
        step = 0 if "C5drop" in lazy else 1
        slots = {g: 2 * width + i for i, g in enumerate(segment_names)}
        cap_seg = {g: floors_here[g][0] * scale for g in segment_names}
        lanes: dict[str, list[dict[str, Any]]] = {}
        for o in cands:
            lanes.setdefault(o["site"]["sid"], []).append(o)
        prepared = {sid: [(o["id"], cw * o["cost"], [unit(x) for x in o["r"]], [unit(x) for x in o["v"]],
                           o["site"]["segment"]) for o in group] for sid, group in lanes.items()}
        # largest unit total whose ticks stay within each ceiling: tk(x) <= c  <=>  x <= scale * c + ceil(scale / 2) - 1
        bound = [scale * c[0] + (scale + 1) // 2 - 1 for c in caps] + [scale * c[1] + (scale + 1) // 2 - 1 for c in caps]
        table: dict[tuple[int, ...], tuple[int, int, int, tuple[str, ...], tuple[str, ...]]] = {
            (0,) * (2 * width + len(segment_names)): (0, 0, 1, (), ())}
        for sid in sorted(prepared, reverse=True):
            merged = dict(table)
            for state, (spent, used, ways, lo, hi) in table.items():
                for oid, cost, rel, rec, seg in prepared[sid]:
                    vec = list(state)
                    ok = True
                    for t, amount in enumerate(rel + rec):
                        vec[t] += amount
                        if vec[t] > bound[t]:
                            ok = False
                            break
                    if not ok:
                        continue
                    vec[slots[seg]] = min(cap_seg[seg], vec[slots[seg]] + sum(rel))
                    key = tuple(vec)
                    item = (spent + cost, used + step, ways, tuple(sorted(lo + (oid,))), tuple(sorted(hi + (oid,))))
                    old = merged.get(key)
                    if old is None or item[:2] < old[:2]:
                        merged[key] = item
                    elif item[:2] == old[:2]:
                        merged[key] = (old[0], old[1], old[2] + item[2], min(old[3], item[3]), max(old[4], item[4]))
            table = merged
        best = None
        for state, (spent, used, ways, lo, hi) in table.items():
            rel = [measure(x) for x in state[:width]]
            rec = [measure(x) for x in state[width:2 * width]]
            parts = [
                sum(goals[t][1] * max(0, goals[t][0] - rel[t]) for t in range(width)),
                sum(pw * max(0, fl - measure(state[slots[g]])) for g, (fl, pw) in floors_here.items()),
                spent + vw * sum(rec),
                sum(max(0, rel[t] - goals[t][0]) for t in range(width)),
                used,
            ]
            if "C34" in lazy:
                parts[2], parts[3] = parts[3], parts[2]
            if "C45" in lazy:
                parts[3], parts[4] = parts[4], parts[3]
            score = tuple(parts)
            if best is None or score < best[0]:
                best = [score, ways, lo, hi]
            elif score == best[0]:
                best[1] += ways
                best[2] = min(best[2], lo)
                best[3] = max(best[3], hi)
        return (best[2] if "H2" in lazy else best[3]), best[1]

    sites_of: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for s in site.values():
        sites_of.setdefault((s["event_id"], s["region"]), []).append(s)
    pool_of: dict[tuple[str, str], list[dict[str, Any]]] = {}
    unauth = 0
    for o in offer.values():
        if o["site"]["auth"]:
            pool_of.setdefault((o["site"]["event_id"], o["site"]["region"]), []).append(o)
        else:
            unauth += 1

    per_region: dict[str, list[dict[str, Any]]] = {r: [] for r in region_names}
    per_segment: dict[str, list[dict[str, Any]]] = {g: [] for g in segment_names}
    tie_log: list[dict[str, Any]] = []
    capped = residual_sum = residual_ties = 0
    empty = zero_floor = dead_pools = 0
    for ev in event_list:
        eid = ev["event_id"]
        width = int(ev["interval_count"])
        cw = int(ev["objective"]["cost_weight"])
        vw = int(ev["objective"]["recovery_weight"])
        uplift = int(ev["uplift_millicents_per_kwh"])
        for region in region_names:
            goals = [goal.get((eid, region, t + 1), (0, 0)) for t in range(width)]
            caps = [limit.get((eid, region, t + 1), (0, 0)) for t in range(width)]
            floors_here = {g: floor.get((eid, region, g), (0, 0)) for g in segment_names}
            cands = pool_of.get((eid, region), [])
            if not cands:
                empty += 1
            memo_key = (str(root), lazy & SEARCH_FLAGS, eid, region)
            if memo_key not in _SEARCH_MEMO:
                _SEARCH_MEMO[memo_key] = search(cands, goals, caps, floors_here, cw, vw, width)
            winner, tied = _SEARCH_MEMO[memo_key]
            picked = [offer[i] for i in winner]
            if tied > 1:
                tie_log.append({"event_id": eid, "region": region, "tied_portfolio_count": tied,
                                "selected_offer_ids": list(winner)})
            numer = {}
            for o in picked:
                energy_wh = sum(o["r"]) if "H5t" in lazy else sum(tk(x) for x in o["r"]) * wh_tick
                numer[o["id"]] = energy_wh * rate(o["site"], uplift)
                capped += o["site"]["base"] + uplift > o["site"]["cap"]
            den = 1000 * mc_cent

            def money(ids: list[str]) -> int:
                if "H5c" in lazy:
                    return _q(sum(numer[i] for i in ids), den)
                return sum(_q(numer[i], den) for i in ids)

            rows = []
            for t in range(width):
                rel_t = reported([o["r"][t] for o in picked])
                rows.append({"interval": t + 1, "target_ticks": goals[t][0], "relief_ticks": rel_t,
                             "recovery_ticks": reported([o["v"][t] for o in picked]),
                             "shortfall_ticks": max(0, goals[t][0] - rel_t),
                             "overdelivery_ticks": max(0, rel_t - goals[t][0])})
            ids = list(winner)
            credit = money(ids)
            raw_pool = pool.get((eid, region), 0)
            funded = raw_pool if "DH3" in lazy else max(0, raw_pool - credit)
            members = [s for s in sites_of.get((eid, region), []) if s["weight"] is not None]
            heft: dict[str, int] = {}
            for s in members:
                heft[s["ben"]] = heft.get(s["ben"], 0) + heft_of(s)
            if "DH5ben" in lazy:
                waived = {s["ben"] for s in members if label(s) == "CONTINUITY_WAIVED"}
                heft = {b: 2 * w if b in waived else w for b, w in heft.items()}
            total_w = sum(heft.values())
            grant_rows: list[dict[str, Any]] = []
            if not members or total_w == 0:
                dead_pools += 1
            else:
                base_cut = {b: funded * w // total_w for b, w in heft.items() if w}
                remain = {b: funded * w % total_w for b, w in heft.items() if w}
                spare = funded - sum(base_cut.values())
                residual_sum += spare
                if "H4" in lazy:
                    queue = sorted(base_cut, key=lambda b: (-remain[b], b))
                else:
                    queue = sorted(base_cut, key=lambda b: (remain[b], b), reverse=True)
                for b in queue[:spare]:
                    base_cut[b] += 1
                if "W0LIST" in lazy:
                    base_cut.update({b: 0 for b, w in heft.items() if not w})
                filled = [r for r in remain.values() if r]
                residual_ties += len(filled) > len(set(filled))
                grant_rows = [{"beneficiary_id": b, "cents": base_cut[b]} for b in sorted(base_cut)]
            given = sum(g["cents"] for g in grant_rows)
            tally = {name: 0 for name in RANKING}
            for s in sites_of.get((eid, region), []):
                tally[label(s)] += 1
            per_region[region].append({
                "event_id": eid, "candidate_offer_count": len(cands), "selected_offer_ids": ids,
                "intervals": rows, "bid_cost_cents": sum(o["cost"] for o in picked), "credit_cents": credit,
                "grant_pool_cents": raw_pool, "grant_funded_cents": funded, "grant_allocated_cents": given,
                "grant_unallocated_cents": funded - given, "grants": grant_rows, "compliance_counts": tally,
            })
            for g in segment_names:
                part = [o for o in picked if o["site"]["segment"] == g]
                fl = floors_here[g][0]
                zero_floor += fl == 0
                got = reported([x for o in part for x in o["r"]])
                per_segment[g].append({
                    "event_id": eid, "region": region, "selected_offer_ids": [o["id"] for o in part],
                    "relief_ticks": got, "recovery_ticks": reported([x for o in part for x in o["v"]]),
                    "bid_cost_cents": sum(o["cost"] for o in part), "credit_cents": money([o["id"] for o in part]),
                    "floor_ticks": fl, "floor_attainment_bp": 10000 if fl == 0 else min(10000, _q(10000 * got, fl)),
                })

    result: dict[str, Any] = {}
    keys_total = ["candidate_offer_count", "selected_offer_count", "relief_ticks", "recovery_ticks",
                  "shortfall_ticks", "overdelivery_ticks", "bid_cost_cents", "credit_cents", "grant_pool_cents",
                  "grant_funded_cents", "grant_allocated_cents", "grant_unallocated_cents"]
    rtot: dict[str, dict[str, int]] = {}
    for region, evs in per_region.items():
        acc = dict.fromkeys(keys_total, 0)
        for e in evs:
            acc["candidate_offer_count"] += e["candidate_offer_count"]
            acc["selected_offer_count"] += len(e["selected_offer_ids"])
            for row in e["intervals"]:
                for k in ("relief_ticks", "recovery_ticks", "shortfall_ticks", "overdelivery_ticks"):
                    acc[k] += row[k]
            for k in keys_total[6:]:
                acc[k] += e[k]
        rtot[region] = acc
        result[f"region_{region}.json"] = {"region": region, "events": evs, "totals": {"event_count": len(evs), **acc}}
    gtot: dict[str, dict[str, int]] = {}
    for g, rows_g in per_segment.items():
        rows_g.sort(key=lambda e: (e["event_id"], e["region"]))
        acc = {k: sum(e[k] for e in rows_g) for k in ("relief_ticks", "recovery_ticks", "bid_cost_cents",
                                                     "credit_cents", "floor_ticks")}
        acc["selected_offer_count"] = sum(len(e["selected_offer_ids"]) for e in rows_g)
        gtot[g] = acc
        result[f"segment_{g}.json"] = {"segment": g, "event_regions": rows_g, "totals": acc}
    summary = {k: sum(rtot[r][k] for r in region_names) for k in keys_total}
    summary.update(event_count=len(event_list), event_region_count=len(event_list) * len(region_names),
                   site_count=len(site))
    summary["regions"] = {r: {k: rtot[r][k] for k in ("selected_offer_count", "relief_ticks", "bid_cost_cents",
                                                       "credit_cents", "grant_allocated_cents")} for r in region_names}
    summary["segments"] = {g: {k: gtot[g][k] for k in ("selected_offer_count", "relief_ticks", "bid_cost_cents",
                                                        "credit_cents")} for g in segment_names}
    result["summary.json"] = summary
    labelled = [{"event_id": k[0], "site_id": k[1], "label": label(site[k])} for k in sorted(site)]
    result["policy_audit.json"] = {
        "compliance_counts": {name: sum(1 for x in labelled if x["label"] == name) for name in RANKING},
        "site_labels": labelled, "tie_decisions": tie_log, "cap_binding_count": capped,
        "residual_cents": residual_sum, "residual_tie_pool_count": residual_ties,
    }
    result["data_quality.json"] = {
        "rows": count, "orphan_offer_rows": lost_offers, "orphan_profile_rows": lost_profiles,
        "duplicate_profile_rows": repeats, "out_of_range_profile_rows": out_of_range,
        "unknown_region_site_rows": unknown, "waiver_signed_missing": blank_signed,
        "ineligible_offer_count": unauth, "empty_candidate_groups": empty, "zero_floor_count": zero_floor,
        "unallocated_pool_count": dead_pools,
    }
    return result


# ---------------------------------------------------------------- extracts

def _scratch() -> Path:
    with _LOCK:
        if ("scratch",) not in _CACHE:
            root = Path(tempfile.mkdtemp(prefix="dhfp-verify-"))
            root.chmod(0o755)
            _CACHE[("scratch",)] = root
        return _CACHE[("scratch",)]


def _seal(folder: Path) -> None:
    for p in folder.iterdir():
        p.chmod(0o644)
    folder.chmod(0o755)


def visible_root() -> Path:
    with _LOCK:
        if ("visible",) not in _CACHE:
            folder = _scratch() / "visible"
            folder.mkdir()
            for name, blob in _SHIPPED_DATA.items():
                (folder / name).write_bytes(zlib.decompress(base64.b64decode(blob)))
            _seal(folder)
            _CACHE[("visible",)] = folder
        return _CACHE[("visible",)]


def expected(root: Path, lazy: frozenset = frozenset()) -> dict[str, Any]:
    with _LOCK:
        key = ("ref", str(root), lazy)
        if key not in _CACHE:
            _CACHE[key] = reference(root, lazy)
        return _CACHE[key]


def _code(region: str, salt: int) -> str:
    return REGION_CODES[region][salt % 2]


def write_extract(folder: Path, spec: dict[str, Any]) -> Path:
    """Write every input file of the contract for a spec built by the case helpers."""
    folder.mkdir(parents=True)
    ini = "[units]\nwh_per_tick = 10\nmillicents_per_cent = 1000\n\n[region_codes]\n"
    ini += "".join(f"{c} = {r}\n" for r, codes in REGION_CODES.items() for c in codes)
    ini += "\n[segment_codes]\n" + "".join(f"{k} = {v}\n" for k, v in SEGMENT_CODES.items())
    (folder / "program.ini").write_text(ini, encoding="utf-8")
    events = [{"event_id": e["event_id"], "name": "case", "interval_count": e["n"],
               "objective": {"cost_weight": e["cw"], "recovery_weight": e["vw"]},
               "uplift_millicents_per_kwh": e["uplift"]} for e in spec["events"]]
    (folder / "events.json").write_text(json.dumps(events), encoding="utf-8")

    def tsv(name: str, sep: str, head: list[str], body: list[list[Any]]) -> None:
        lines = [sep.join(head)] + [sep.join(str(v) for v in row) for row in body]
        (folder / name).write_text("\n".join(lines) + "\n", encoding="utf-8")

    sites = spec["sites"]
    tsv("sites.csv", ",", ["event_id", "site_id", "region_code", "segment_code", "beneficiary_id", "critical"],
        [[s["event_id"], s["sid"], s["code"], s["seg"], s["ben"], "Y" if s["critical"] else "N"] for s in sites])
    (folder / "site_state.jsonl").write_text("".join(json.dumps(
        {"event_id": s["event_id"], "site_id": s["sid"], "dispatch_authorized": s["auth"], "safety_hold": s["hold"],
         "cooldown": s["cool"]}) + "\n" for s in sites), encoding="utf-8")
    tsv("continuity_waivers.csv", ",", ["event_id", "site_id", "routine_certificate_pending", "waiver_status",
                                        "waiver_signed"],
        [[s["event_id"], s["sid"], "Y" if s["pending"] else "N", s["status"], s["signed"]] for s in sites])
    cards = "".join(f'<card event="{s["event_id"]}" site="{s["sid"]}"><base>{s["base"]}</base><cap>{s["cap"]}</cap></card>\n'
                    for s in sites)
    (folder / "rate_cards.xml").write_text(f'<?xml version="1.0"?>\n<rate_cards>\n{cards}</rate_cards>\n',
                                           encoding="utf-8")
    tsv("recipient_weights.tsv", "\t", ["event_id", "site_id", "grant_weight"],
        [[s["event_id"], s["sid"], s["weight"]] for s in sites if s["weight"] is not None])
    offers = list(spec["offers"])
    offer_body = [[o["offer_id"], o["event_id"], o["sid"], "SETBACK_2C", o["cost"]] for o in offers]
    offer_body += [list(x) for x in spec.get("orphan_offer_rows", [])]
    profile_body = [[o["offer_id"], t + 1, o["r"][t], o["v"][t]] for o in offers for t in range(len(o["r"]))]
    profile_body += [list(x) for x in spec.get("orphan_profile_rows", [])]
    if spec.get("reverse"):
        offer_body.reverse()
        profile_body.reverse()
    if "shuffle" in spec:
        mixer = Rng(spec["shuffle"])
        mixer.shuffle(offer_body)
        mixer.shuffle(profile_body)
    profile_body += [list(x) for x in spec.get("late_profile_rows", [])]
    tsv("offers.csv", ",", ["offer_id", "event_id", "site_id", "mode_label", "bid_cost_cents"], offer_body)
    tsv("profiles.tsv", "\t", ["offer_id", "interval", "relief_wh", "recovery_wh"], profile_body)
    target_body, feeder = [], ["# event_id  code itv relief_wh recovery_wh"]
    for e in spec["events"]:
        for region in REGION_CODES:
            goals = spec["targets"].get((e["event_id"], region), [])
            limits = spec["limits"].get((e["event_id"], region), [])
            for t in range(e["n"]):
                wh, weight = goals[t] if t < len(goals) else (0, 1)
                relief_cap, recovery_cap = limits[t] if t < len(limits) else (0, 0)
                target_body.append([e["event_id"], _code(region, t), t + 1, wh, weight])
                feeder.append(f"{e['event_id']:<10}{_code(region, t + 1):<4}{t + 1:>3}{relief_cap:>10}{recovery_cap:>10}")
    tsv("targets.tsv", "\t", ["event_id", "region_code", "interval", "target_wh", "shortfall_weight"], target_body)
    (folder / "feeder_limits.txt").write_text("\n".join(feeder) + "\n", encoding="utf-8")
    floors = [{"event_id": e, "region_code": _code(r, len(e)), "segment_code": g, "floor_wh": wh,
               "priority_weight": pw} for e, r, g, wh, pw in spec.get("floors", [])]
    (folder / "segment_floors.json").write_text(json.dumps({"floors": floors}), encoding="utf-8")
    pools = ["# event_id  code   pool_cents"]
    pools += [f"{e:<10}{_code(r, 1):<4}{cents:>12}" for (e, r), cents in sorted(spec.get("pools", {}).items())]
    (folder / "pools.txt").write_text("\n".join(pools) + "\n", encoding="utf-8")
    _seal(folder)
    return folder


def _site(eid: str, sid: str, **extra: Any) -> dict[str, Any]:
    row = {"event_id": eid, "sid": sid, "code": "N1", "seg": "C", "ben": f"BEN-{sid}", "critical": False, "auth": True,
           "hold": False, "cool": False, "pending": False, "status": "NONE", "signed": "", "base": 4000,
           "cap": 9000, "weight": None}
    row.update(extra)
    return row


def _offer(eid: str, sid: str, letter: str, cost: int, relief: list[int], recovery: list[int] | None = None):
    return {"offer_id": f"{eid}-{sid}-{letter}", "event_id": eid, "sid": sid, "cost": cost, "r": relief,
            "v": recovery or [0] * len(relief)}


def _event(eid: str, n: int, cw: int = 1, vw: int = 0, uplift: int = 0) -> dict[str, Any]:
    return {"event_id": eid, "n": n, "cw": cw, "vw": vw, "uplift": uplift}


def _wide(n: int) -> list[tuple[int, int]]:
    return [(500000, 500000)] * n


def _single(eid: str, sites, offers, n: int, targets, limits=None, **extra) -> dict[str, Any]:
    spec = {"events": [_event(eid, n, **extra.pop("event", {}))], "sites": sites, "offers": offers,
            "targets": {(eid, "North"): targets}, "limits": {(eid, "North"): limits or _wide(n)}}
    spec.update(extra)
    return spec


_ELIGIBLE = {"seg": "P", "critical": True, "pending": True, "status": "VALID", "signed": "Y"}


def case_spec(name: str) -> dict[str, Any]:
    """The hand-built extracts, one rule or one family of rules each."""
    if name == "waiver":
        e = "T1-0001"
        sites = [_site(e, "S-WAIVE", **_ELIGIBLE), _site(e, "S-BOTH", hold=True, cool=True, **_ELIGIBLE),
                 _site(e, "S-PEND", pending=True, status="EXPIRED", signed="Y"),
                 _site(e, "S-EMPTY", seg="P", critical=True, pending=True, status="VALID", signed=""),
                 _site(e, "S-PLAIN")]
        return _single(e, sites, [], 2, [])
    if name == "tie":
        e = "T2-0001"
        sites = [_site(e, "S1"), _site(e, "S2")]
        offers = [_offer(e, "S1", "A", 700, [3000, 0]), _offer(e, "S1", "Z", 700, [3000, 0]),
                  _offer(e, "S2", "M", 500, [0, 2000])]
        return _single(e, sites, offers, 2, [(3000, 2), (2000, 2)])
    if name == "cap":
        e = "T3-0001"
        return _single(e, [_site(e, "S1", base=850, cap=1000)], [_offer(e, "S1", "A", 100, [5000])], 1, [(5000, 1)],
                       event={"uplift": 250})
    if name == "residual":
        e = "T4-0001"
        sites = [_site(e, f"S{i}", ben=ben, weight=1) for i, ben in enumerate(("BEN-ALPHA", "BEN-MU", "BEN-ZULU"), 1)]
        sites.append(_site(e, "S4", ben="BEN-NIL", weight=0))
        return _single(e, sites, [], 1, [], pools={(e, "North"): 5})
    if name == "tick_feasibility":
        e = "T6-0001"
        offers = [_offer(e, "S1", "A", 10, [15]), _offer(e, "S2", "A", 20, [15])]
        return _single(e, [_site(e, "S1"), _site(e, "S2")], offers, 1, [(1000, 1)], [(34, 500000)])
    if name == "components":
        # Three events in one extract: cost before overdelivery, overdelivery before offer count, and
        # offer count as the last component.
        e1, e2, e3 = "T6-0101", "T6-0102", "T6-0103"
        sites = [_site(e1, "S1"), _site(e2, "S1"), _site(e2, "S2"), _site(e2, "S3"), _site(e3, "S1"),
                 _site(e3, "S2")]
        offers = [_offer(e1, "S1", "A", 10, [1500]), _offer(e1, "S1", "B", 20, [1000]),
                  _offer(e2, "S1", "A", 20, [1200]), _offer(e2, "S2", "A", 10, [600]), _offer(e2, "S3", "A", 10, [400]),
                  _offer(e3, "S1", "A", 10, [1000]), _offer(e3, "S2", "Z", 0, [0])]
        spec = {"events": [_event(e, 1) for e in (e1, e2, e3)], "sites": sites, "offers": offers,
                "targets": {(e, "North"): [(1000, 1)] for e in (e1, e2, e3)},
                "limits": {(e, "North"): _wide(1) for e in (e1, e2, e3)}}
        return spec
    if name == "full":
        # The largest event-region the contract allows: 8 sites with 3 candidate offers each (65,536 portfolios).
        e = "T7-0001"
        rng = Rng(11)
        n = 4
        sites = [_site(e, f"F{i}", seg=rng.pick(["C", "P"])) for i in range(8)]
        offers = []
        for i in range(8):
            for letter in "ABC":
                relief = [rng.between(0, 60) * 5 if rng.chance(70) else 0 for _ in range(n)]
                recovery = [rng.between(0, 30) * 5 if rng.chance(30) else 0 for _ in range(n)]
                offers.append(_offer(e, f"F{i}", letter, rng.between(300, 5000), relief, recovery))
        twin = next(o for o in offers if o["offer_id"] == f"{e}-F3-A")
        offers[offers.index(next(o for o in offers if o["offer_id"] == f"{e}-F3-C"))] = _offer(
            e, "F3", "Z", twin["cost"], list(twin["r"]), list(twin["v"]))
        return _single(e, sites, offers, n, [(rng.between(60, 120) * 5, 2) for _ in range(n)],
                       [(rng.between(400, 600) * 5, rng.between(200, 300) * 5) for _ in range(n)],
                       floors=[(e, "North", "P", 600, 2)], event={"cw": 1, "vw": 1})
    if name == "rejected":
        e1, e2 = "T9-0001", "T9-0002"
        offers = [_offer(e1, "S1", "A", 10, [1000]), _offer(e1, "S2", "B", 50, [3000]),
                  _offer(e2, "S1", "A", 10, [1000, 1000]), _offer(e2, "S2", "B", 50, [0, 3000])]
        return {"events": [_event(e1, 1), _event(e2, 2)],
                "sites": [_site(e1, "S1"), _site(e1, "S2"), _site(e2, "S1"), _site(e2, "S2")], "offers": offers,
                "targets": {(e1, "North"): [(10000, 1)], (e2, "North"): [(10000, 1), (10000, 1)]},
                "limits": {(e1, "North"): [(5000, 500000)], (e2, "North"): [(500000, 500000), (5000, 500000)]},
                "late_profile_rows": [[f"{e1}-S1-A", 1, 9000, 0], [f"{e2}-S1-A", 0, 9000, 0],
                                      [f"{e2}-S1-A", 3, 7000, 0]]}
    if name == "unknown_region":
        e = "T9-0003"
        sites = [_site(e, "S1"), _site(e, "S-X", code="Z9", ben="BEN-X", weight=2, **_ELIGIBLE)]
        offers = [_offer(e, "S1", "A", 10, [1000]), _offer(e, "S-X", "A", 10, [1000])]
        return _single(e, sites, offers, 1, [(10000, 1)], pools={(e, "North"): 40})
    raise KeyError(name)


# Composed extracts: many events at once, graded as whole documents. `mix` sets how dense each kind of
# difficulty is (percent chances per site or per event-region unless noted).
MIXES: dict[str, dict[str, int]] = {
    "A": {"events": 14, "big": 0, "waiver": 18, "hold": 14, "tie": 8, "zero": 4, "flat": 15, "pool_low": 60,
          "bens": 7, "reject": 2, "unknown": 1},
    "B": {"events": 12, "big": 22, "waiver": 6, "hold": 8, "tie": 22, "zero": 12, "flat": 40, "pool_low": 30,
          "bens": 12, "reject": 3, "unknown": 1},
    "C": {"events": 14, "big": 4, "waiver": 8, "hold": 8, "tie": 8, "zero": 6, "flat": 20, "pool_low": 35,
          "bens": 9, "reject": 14, "unknown": 5},
    "D": {"events": 16, "big": 8, "waiver": 10, "hold": 10, "tie": 12, "zero": 8, "flat": 25, "pool_low": 45,
          "bens": 8, "reject": 6, "unknown": 3},
}


# Hand-built events carried inside each composed extract next to the seeded ones, so that the rules they
# isolate also reach the whole-document checks.
PLANTED = {"A": ("waiver", "residual", "cap"), "B": ("tie", "tick_feasibility", "components", "full"),
           "C": ("rejected", "unknown_region"), "D": ("residual", "cap", "tick_feasibility", "components", "full")}


def _plant(spec: dict[str, Any], names: tuple[str, ...]) -> None:
    for name in names:
        extra = case_spec(name)
        for key in ("events", "sites", "offers", "floors", "orphan_offer_rows", "orphan_profile_rows",
                    "late_profile_rows"):
            spec[key].extend(extra.get(key, []))
        for key in ("targets", "limits", "pools"):
            spec[key].update(extra.get(key, {}))


def _composed_spec(tag: str, seed: int) -> dict[str, Any]:
    """A seeded extract that exercises every rule of the contract at once, with all stated limits respected."""
    mix = MIXES[tag]
    rng = Rng(seed * 7919 + ord(tag))
    spec: dict[str, Any] = {"events": [], "sites": [], "offers": [], "targets": {}, "limits": {}, "floors": [],
                            "pools": {}, "orphan_offer_rows": [], "orphan_profile_rows": [],
                            "late_profile_rows": []}
    prefix = f"{tag}{seed % 90 + 10}"
    for k in range(mix["events"]):
        eid = f"{prefix}-{100 + 37 * k:04d}"
        n = rng.between(2, 5)
        flat = rng.chance(mix["flat"])
        spec["events"].append(_event(eid, n, 0 if flat else rng.between(1, 3), 0 if flat else rng.between(0, 2),
                                     rng.pick([0, 250, 500, 1000, 2000])))
        uplift = spec["events"][-1]["uplift"]
        for region in REGION_CODES:
            count = 0 if rng.chance(8) else (rng.between(5, 8) if rng.chance(mix["big"]) else rng.between(1, 4))
            local = []
            for i in range(count):
                sid = f"KS{region[0]}{rng.between(100, 999)}{i}"
                if rng.chance(mix["waiver"]):
                    fields = dict(_ELIGIBLE)
                else:
                    fields = {"seg": rng.pick(["C", "P", "P"]), "critical": rng.chance(60), "pending": rng.chance(45),
                              "status": rng.pick(["VALID", "VALID", "EXPIRED", "NONE", "REVOKED"]),
                              "signed": rng.pick(["Y", "Y", "N", ""])}
                weight = None if rng.chance(8) else (0 if rng.chance(10) else rng.between(1, 4))
                base = rng.between(2, 9) * 1000
                local.append(_site(eid, sid, code=rng.pick(REGION_CODES[region]), ben=f"BEN-{rng.between(1, mix['bens'])}",
                                   auth=not rng.chance(10), hold=rng.chance(mix["hold"]), cool=rng.chance(mix["hold"]),
                                   base=base, cap=max(500, base + rng.pick([-1500, -500, 0, 300, 1000, 4000])),
                                   weight=weight, **fields))
                letters = "ABC"[:rng.between(1, 3)]
                made = []
                for letter in letters:
                    relief = [rng.between(0, 120) * 5 if rng.chance(60) else 0 for _ in range(n)]
                    recovery = [rng.between(0, 80) * 5 if rng.chance(35) else 0 for _ in range(n)]
                    made.append(_offer(eid, sid, letter, rng.between(300, 20000), relief, recovery))
                if len(made) < 3 and rng.chance(mix["tie"]):
                    made.append(_offer(eid, sid, "Z", made[0]["cost"], list(made[0]["r"]), list(made[0]["v"])))
                if len(made) < 3 and rng.chance(mix["zero"]):
                    made.append(_offer(eid, sid, "Y", 0, [0] * n, [0] * n))
                spec["offers"].extend(made)
            spec["sites"].extend(local)
            spec["targets"][(eid, region)] = [(rng.between(0, 100) * 5, rng.between(1, 4)) for _ in range(n)]
            spec["limits"][(eid, region)] = [(rng.between(20, 120) * 5, rng.between(10, 80) * 5) for _ in range(n)]
            for g in ("C", "P"):
                if rng.chance(70):
                    spec["floors"].append((eid, region, g, rng.between(0, 80) * 5, rng.between(1, 4)))
            if rng.chance(92):
                spec["pools"][(eid, region)] = rng.between(0, 160) if rng.chance(mix["pool_low"]) else rng.between(160, 900)
    live = [s for s in spec["sites"] if s["code"] != "Z9"]
    firsts = [s for s in live][:]
    for _ in range(mix["unknown"]):
        host = rng.pick(firsts)
        sid = f"KSZ{rng.between(100, 999)}"
        if any(x["event_id"] == host["event_id"] and x["sid"] == sid for x in spec["sites"]):
            continue
        width = next(e["n"] for e in spec["events"] if e["event_id"] == host["event_id"])
        spec["sites"].append(_site(host["event_id"], sid, code="Z9", ben="BEN-X", weight=rng.between(1, 3),
                                   **_ELIGIBLE))
        spec["offers"].append(_offer(host["event_id"], sid, "A", 100, [rng.between(1, 60) * 5] * width))
    offer_ids = [o for o in spec["offers"] if o["sid"] in {s["sid"] for s in live}]
    for _ in range(max(1, len(offer_ids) * mix["reject"] // 100)):
        o = rng.pick(offer_ids)
        width = len(o["r"])
        kind = rng.between(0, 2)
        if kind == 0:
            spec["late_profile_rows"].append([o["offer_id"], rng.between(1, width), rng.between(1, 400) * 5, 0])
        elif kind == 1:
            spec["late_profile_rows"].append([o["offer_id"], rng.pick([0, width + 1]), rng.between(1, 400) * 5, 0])
        else:
            spec["orphan_profile_rows"].append([f"NOPE-{rng.between(100, 999)}", 1, rng.between(1, 400) * 5, 0])
    spec["orphan_offer_rows"] = [[f"{prefix}-GHOST-A", spec["events"][0]["event_id"], "QX0000", "SETBACK_4C", 900]]
    _plant(spec, PLANTED[tag])
    if tag in ("B", "D"):
        spec["shuffle"] = seed + 7
    if tag == "C":
        spec["reverse"] = True
    return spec


# Per composed extract: the wrong readings each graded document must separate. The extract is the first seed
# from EVAL_SEED for which every guard holds, so a check never pays for a document that cannot tell the readings
# apart.
GUARDS: dict[str, dict[str, tuple[str, ...]]] = {
    "A": {"regions": ("H1", "H1order", "H1hc", "SIGNEDY", "DH3", "DH5raw", "H4", "H3", "W0LIST"),
          "segments": ("H3", "H5t"),
          "audit": ("H1", "H1hc", "H1pend", "SIGNEDY", "H3", "DH3"),
          "quality": ("DH4dup", "DH4unknown")},
    "B": {"regions": ("H2", "DH2", "C34", "C45", "C5drop", "H5t", "DH3", "H3"),
          "segments": ("H2", "DH2", "C34", "C45", "H5t"),
          "audit": ("H2", "DH2", "C45", "C5drop", "DH3"),
          "quality": ("DH4range", "DH4unknown")},
    "C": {"regions": ("DH4dup", "DH4range", "H3", "DH3", "DH5raw", "H4"),
          "segments": ("DH4dup", "DH4range", "H3"),
          "audit": ("DH4unknown", "H3", "DH3", "H1"),
          "quality": ("DH4dup", "DH4range", "DH4unknown")},
    "D": {"regions": ("H1order", "H2", "H3", "DH2", "DH3", "DH5raw", "W0LIST", "C34", "C45", "H4"),
          "segments": ("H2", "H3", "H5t", "DH2", "C34"),
          "audit": ("H1", "H1pend", "H2", "H3", "DH3", "DH4unknown"),
          "quality": ("DH4dup", "DH4range", "DH4unknown")},
}


def _region_docs(files: dict[str, Any]) -> Any:
    return [files.get(f"region_{r}.json") for r in REGION_CODES]


def _segment_docs(files: dict[str, Any]) -> Any:
    return [files.get(f"segment_{g}.json") for g in SEGMENT_CODES.values()]


def _audit_docs(files: dict[str, Any]) -> Any:
    return [files.get("summary.json"), files.get("policy_audit.json")]


def _quality_doc(files: dict[str, Any]) -> Any:
    return files.get("data_quality.json")


VIEWS = {"regions": _region_docs, "segments": _segment_docs, "audit": _audit_docs, "quality": _quality_doc}


MAX_SITES, MAX_OFFERS = 8, 3


def within_contract(spec: dict[str, Any]) -> bool:
    """Schema section 3: at most 8 sites with candidate offers per event-region and 3 candidate offers per site."""
    per_site: dict[tuple[str, str], int] = {}
    for o in spec["offers"]:
        per_site[(o["event_id"], o["sid"])] = per_site.get((o["event_id"], o["sid"]), 0) + 1
    if any(n > MAX_OFFERS for n in per_site.values()):
        return False
    region_of = {code: region for region, codes in REGION_CODES.items() for code in codes}
    groups: dict[tuple[str, str], int] = {}
    for s in spec["sites"]:
        if s["auth"] and s["code"] in region_of and per_site.get((s["event_id"], s["sid"])):
            groups[(s["event_id"], region_of[s["code"]])] = groups.get((s["event_id"], region_of[s["code"]]), 0) + 1
    return all(n <= MAX_SITES for n in groups.values())


def composed_root(tag: str) -> Path | None:
    """First seed from EVAL_SEED whose extract makes every wrong reading change the document it is graded on."""
    with _LOCK:
        if ("composed", tag) not in _CACHE:
            found = None
            for step in range(60):
                spec = _composed_spec(tag, EVAL_SEED % 100000 + step)
                if not within_contract(spec):
                    continue
                folder = write_extract(_scratch() / f"composed-{tag}-{step}", spec)
                right = expected(folder)
                if all(VIEWS[view](expected(folder, frozenset({flag}))) != VIEWS[view](right)
                       for view, flags in GUARDS[tag].items() for flag in flags):
                    found = folder
                    break
            _CACHE[("composed", tag)] = found
        return _CACHE[("composed", tag)]


def case_root(name: str) -> Path:
    with _LOCK:
        key = ("case", name)
        if key not in _CACHE:
            spec = case_spec(name)
            if not within_contract(spec):
                raise ValueError(f"case {name} exceeds the sizes schema.md allows")
            _CACHE[key] = write_extract(_scratch() / f"case-{name}", spec)
        return _CACHE[key]


# ---------------------------------------------------------------- running the agent

def _root_only_tests_present() -> bool:
    try:
        status = Path("/tests").stat()
    except OSError:
        return False
    return status.st_uid == 0 and (status.st_mode & 0o077) == 0


def _untrusted(command: list[str]) -> list[str]:
    if os.name == "posix" and os.geteuid() == 0:
        return [*_SETPRIV, *command]
    if _root_only_tests_present():
        raise RuntimeError("verifier must run as root to isolate submitted code from /tests")
    return command


def _reap_agent_processes() -> None:
    """Kill every process still owned by the unprivileged uid; killpg alone misses a child that called setsid()."""
    if os.name != "posix" or os.geteuid() != 0 or not os.path.isdir("/proc"):
        return
    for _ in range(5):
        victims = []
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                with open(f"/proc/{entry}/status", encoding="utf-8") as handle:
                    lines = handle.read().splitlines()
                ids = next(line for line in lines if line.startswith("Uid:")).split()[1:3]
                state = next(line for line in lines if line.startswith("State:")).split()[1]
            except (OSError, StopIteration):
                continue
            if state != "Z" and _AGENT_UID in (int(ids[0]), int(ids[1])):
                victims.append(int(entry))
        if not victims:
            return
        for pid in victims:
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        time.sleep(0.05)


def produced(folder: Path | None, name: str) -> Any:
    if folder is None:
        return None
    try:
        return json.loads((folder / name).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def run_agent(workspace: Path, data: Path | None) -> dict[str, Any] | None:
    """Run the submitted program on one extract.

    Returns the parsed reports (file name -> JSON, None for a file that is missing or unreadable), or None when
    the run failed. The program is copied into a folder the grader owns and made world readable, because an
    editor-written file arrives at mode 0600 and the run drops to another uid. Only parsed documents are cached,
    never a folder a leftover process could rewrite."""
    if data is None:
        return None
    script = Path(workspace) / "out" / "derive_report.py"
    with _LOCK:
        key = ("run", str(script), str(data))
        if key in _CACHE:
            return _CACHE[key]
        result = None
        if script.is_file():
            box = Path(tempfile.mkdtemp(prefix="run-", dir=_scratch()))
            box.chmod(0o777)
            staged = box / "derive_report.py"
            try:
                shutil.copyfile(script, staged)
                staged.chmod(0o644)
                out = box / "out"
                proc = subprocess.Popen(_untrusted([sys.executable, str(staged), str(data), str(out)]), cwd=box,
                                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, start_new_session=True)
                try:
                    code = proc.wait(timeout=_AGENT_TIMEOUT)
                except subprocess.TimeoutExpired:
                    code = None
                finally:
                    try:
                        os.killpg(proc.pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass
                    proc.wait()
                    _reap_agent_processes()
                if code == 0 and out.is_dir():
                    result = {n: produced(out, n) for n in ARTIFACT_JSON}
            except OSError:
                result = None
            finally:
                shutil.rmtree(box, ignore_errors=True)
        _CACHE[key] = result
        return result


def mine(workspace: Path, name: str) -> Any:
    return produced(Path(workspace) / "out", name)


# ---------------------------------------------------------------- projections

def site_label(doc: Any, sid: str) -> Any:
    if not isinstance(doc, dict) or not isinstance(doc.get("site_labels"), list):
        return None
    hits = [x.get("label") for x in doc["site_labels"] if isinstance(x, dict) and x.get("site_id") == sid]
    return hits[0] if len(hits) == 1 else None


def first_event(files: dict[str, Any], field: str, region: str = "North") -> Any:
    try:
        return files[f"region_{region}.json"]["events"][0][field]
    except (KeyError, IndexError, TypeError):
        return None


def field_of(files: dict[str, Any], name: str, *keys: str) -> Any:
    try:
        return tuple(files[name][k] for k in keys)
    except (KeyError, TypeError):
        return None


def per_event(files: dict[str, Any], field: str) -> Any:
    try:
        return [(e["event_id"], e[field]) for e in files["region_North.json"]["events"]]
    except (KeyError, TypeError):
        return None


def canon(value: Any) -> str:
    """Re-serialise a parsed document, so floats and booleans differ from integers."""
    return json.dumps(value, sort_keys=True)


def separated(name: str, rules: tuple[str, ...], observe) -> bool:
    """True when the case's observable differs between the contract and each named wrong reading."""
    root = case_root(name)
    right = canon(observe(expected(root)))
    return all(canon(observe(expected(root, frozenset({rule})))) != right for rule in rules)


def case_passes(workspace: Path, name: str, rules: tuple[str, ...], observe) -> bool:
    if not separated(name, rules, observe):
        return False
    root = case_root(name)
    got = run_agent(workspace, root)
    if got is None:
        return False
    return canon(observe(got)) == canon(observe(expected(root)))


def composed_passes(workspace: Path, tag: str, view: str) -> bool:
    root = composed_root(tag)
    if root is None:
        return False
    got = run_agent(workspace, root)
    if got is None:
        return False
    return canon(VIEWS[view](got)) == canon(VIEWS[view](expected(root)))


# ---------------------------------------------------------------- format checks on /app/out

def _strict_load(text: str) -> Any:
    def pairs(items):
        keys = [k for k, _ in items]
        if keys != sorted(keys):
            raise ValueError("unsorted keys")
        return dict(items)

    def no_float(token: str):
        raise ValueError("float")

    def no_constant(token: str):
        raise ValueError("constant")

    return json.loads(text, object_pairs_hook=pairs, parse_float=no_float, parse_constant=no_constant)


def _has_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return True
    if isinstance(value, dict):
        return any(_has_bool(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_bool(v) for v in value)
    return False


def _key_paths(value: Any, path: str, found: dict[str, set]) -> None:
    if isinstance(value, dict):
        found.setdefault(path, set()).add(frozenset(value))
        for k, v in value.items():
            _key_paths(v, f"{path}.{k}", found)
    elif isinstance(value, list):
        for v in value:
            _key_paths(v, f"{path}[]", found)


def _sorted_strictly(items: list, key) -> bool:
    keys = [key(x) for x in items]
    return all(a < b for a, b in zip(keys, keys[1:]))


@criterion(description="All ten declared artifacts exist and the nine JSON reports parse as objects.")
def artifact_set_exists_and_parses(workspace: Path) -> bool:
    try:
        out = Path(workspace) / "out"
        if not (out / "derive_report.py").is_file():
            return False
        return all(isinstance(produced(out, n), dict) for n in ARTIFACT_JSON)
    except Exception:
        return False


def _leaf_types(value: Any, path: str, found: dict[str, set]) -> None:
    if isinstance(value, dict):
        for k, v in value.items():
            _leaf_types(v, f"{path}.{k}", found)
    elif isinstance(value, list):
        for v in value:
            _leaf_types(v, f"{path}[]", found)
    else:
        found.setdefault(path, set()).add(type(value).__name__)


@criterion(description="Every JSON report has sorted keys at every level, a trailing newline, no float or boolean, and a JSON integer at every place the schema gives an integer field.")
def canonical_serialization_and_integer_units(workspace: Path) -> bool:
    try:
        want = expected(visible_root())
        for name in ARTIFACT_JSON:
            text = (Path(workspace) / "out" / name).read_text(encoding="utf-8")
            if not text.endswith("\n"):
                return False
            doc = _strict_load(text)
            if _has_bool(doc):
                return False
            need: dict[str, set] = {}
            have: dict[str, set] = {}
            _leaf_types(want[name], "", need)
            _leaf_types(doc, "", have)
            if any(have.get(path) != {"int"} for path, kinds in need.items() if kinds == {"int"}):
                return False
        return True
    except Exception:
        return False


@criterion(description="Every object in the eight region, segment, audit and quality reports carries exactly the schema keys for its place.")
def report_keys_match_schema(workspace: Path) -> bool:
    try:
        want = expected(visible_root())
        for name in ARTIFACT_JSON:
            if name == "summary.json":
                continue
            need: dict[str, set] = {}
            have: dict[str, set] = {}
            _key_paths(want[name], "", need)
            _key_paths(mine(workspace, name), "", have)
            if have != need:
                return False
        return True
    except Exception:
        return False


@criterion(description="Every array in the shipped-data reports has one entry per item in the order schema.md gives.")
def report_arrays_in_schema_order(workspace: Path) -> bool:
    try:
        want = expected(visible_root())
        events = want["summary.json"]["event_count"]
        for region in REGION_CODES:
            entries = mine(workspace, f"region_{region}.json")["events"]
            if len(entries) != events or not _sorted_strictly(entries, lambda e: e["event_id"]):
                return False
            for e in entries:
                if [i["interval"] for i in e["intervals"]] != list(range(1, len(e["intervals"]) + 1)) or not e["intervals"]:
                    return False
                if not _sorted_strictly(e["selected_offer_ids"], lambda x: x):
                    return False
                if not _sorted_strictly(e["grants"], lambda g: g["beneficiary_id"]):
                    return False
        for segment in SEGMENT_CODES.values():
            rows = mine(workspace, f"segment_{segment}.json")["event_regions"]
            if len(rows) != events * len(REGION_CODES) or not _sorted_strictly(rows, lambda e: (e["event_id"], e["region"])):
                return False
        audit = mine(workspace, "policy_audit.json")
        labels = audit["site_labels"]
        if len(labels) != want["summary.json"]["site_count"] or not _sorted_strictly(labels, lambda x: (x["event_id"], x["site_id"])):
            return False
        return _sorted_strictly(audit["tie_decisions"], lambda x: (x["event_id"], x["region"]))
    except Exception:
        return False


# ---------------------------------------------------------------- composed extracts, whole documents

def _composed(workspace: Path, tag: str, view: str) -> bool:
    try:
        return composed_passes(workspace, tag, view)
    except Exception:
        return False


@criterion(description="On a seeded extract rich in waivers, holds and grant pools, the four region files match the contract in every entry.")
def grants_extract_region_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "A", "regions")


@criterion(description="On the same extract both segment files match the contract in every entry.")
def grants_extract_segment_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "A", "segments")


@criterion(description="On the same extract summary.json and policy_audit.json match the contract in every entry.")
def grants_extract_summary_and_audit_match(workspace: Path) -> bool:
    return _composed(workspace, "A", "audit")


@criterion(description="On the same extract data_quality.json matches the contract in every entry.")
def grants_extract_data_quality_match(workspace: Path) -> bool:
    return _composed(workspace, "A", "quality")


@criterion(description="On a seeded extract with tied portfolios, twin offers, zero offers and groups of up to eight sites, the four region files match in every entry.")
def search_extract_region_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "B", "regions")


@criterion(description="On the same extract both segment files match the contract in every entry.")
def search_extract_segment_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "B", "segments")


@criterion(description="On the same extract summary.json and policy_audit.json, tie decisions included, match the contract in every entry.")
def search_extract_summary_and_audit_match(workspace: Path) -> bool:
    return _composed(workspace, "B", "audit")


@criterion(description="On the same extract data_quality.json matches the contract in every entry.")
def search_extract_data_quality_match(workspace: Path) -> bool:
    return _composed(workspace, "B", "quality")


@criterion(description="On a seeded extract with repeated, out-of-range, orphan and unknown-region rows in row order reversed, the four region files match in every entry.")
def rejects_extract_region_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "C", "regions")


@criterion(description="On the same extract both segment files match the contract in every entry.")
def rejects_extract_segment_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "C", "segments")


@criterion(description="On the same extract summary.json and policy_audit.json match the contract in every entry.")
def rejects_extract_summary_and_audit_match(workspace: Path) -> bool:
    return _composed(workspace, "C", "audit")


@criterion(description="On the same extract data_quality.json, with every rejected-row count, matches the contract.")
def rejects_extract_data_quality_match(workspace: Path) -> bool:
    return _composed(workspace, "C", "quality")


@criterion(description="On a seeded mixed extract with shuffled rows, the four region files match the contract in every entry.")
def mixed_extract_region_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "D", "regions")


@criterion(description="On the same extract both segment files match the contract in every entry.")
def mixed_extract_segment_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "D", "segments")


@criterion(description="On the same extract summary.json and policy_audit.json match the contract in every entry.")
def mixed_extract_summary_and_audit_match(workspace: Path) -> bool:
    return _composed(workspace, "D", "audit")


@criterion(description="On the same extract data_quality.json matches the contract in every entry.")
def mixed_extract_data_quality_match(workspace: Path) -> bool:
    return _composed(workspace, "D", "quality")


# ---------------------------------------------------------------- one rule family each

@criterion(description="Site rows are labelled by the compliance ranking: a valid waiver, a hold with a cooldown, a pending certificate and an unrecorded signature each get their stated label.")
def waiver_labels_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "waiver", ("H1", "H1order", "H1hc", "H1pend", "SIGNEDY"), lambda f: (
            [site_label(f["policy_audit.json"], s) for s in ("S-WAIVE", "S-BOTH", "S-PEND", "S-EMPTY", "S-PLAIN")],
            field_of(f, "policy_audit.json", "compliance_counts"), first_event(f, "compliance_counts")))
    except Exception:
        return False


@criterion(description="Two portfolios equal on every component resolve to the greatest sorted offer-id tuple.")
def tie_break_greatest_tuple_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "tie", ("H2",), lambda f: first_event(f, "selected_offer_ids"))
    except Exception:
        return False


@criterion(description="The rate cap binds the base rate plus the event uplift, and the chosen offer counts as cap binding.")
def cap_after_uplift_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "cap", ("H3",), lambda f: (
            first_event(f, "credit_cents"), field_of(f, "policy_audit.json", "cap_binding_count")))
    except Exception:
        return False


@criterion(description="Leftover grant cents with equal remainders go to beneficiaries in descending id order, a zero-weight beneficiary is not listed, and the residual is recorded in the audit.")
def residual_ties_descending_id_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "residual", ("H4", "W0LIST"), lambda f: (
            first_event(f, "grants"), field_of(f, "policy_audit.json", "residual_cents", "residual_tie_pool_count")))
    except Exception:
        return False


@criterion(description="Feasibility inside the search uses per-value ticks: two 15 Wh offers make 4 ticks and break a 34 Wh ceiling.")
def tick_feasibility_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "tick_feasibility", ("DH2",), lambda f: first_event(f, "selected_offer_ids"))
    except Exception:
        return False


@criterion(description="The objective components are compared in their stated order: cost before overdelivery, overdelivery before offer count, and offer count last.")
def objective_component_order_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "components", ("C34", "C45", "C5drop"), lambda f: (
            per_event(f, "selected_offer_ids"), (f["policy_audit.json"] or {}).get("tie_decisions")))
    except Exception:
        return False


@criterion(description="A repeated profile row keeps the first row in file order, and a row with an interval outside 1 to interval_count is skipped; both decide the chosen portfolios and are counted in data_quality.json.")
def rejected_profile_rows_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "rejected", ("DH4dup", "DH4range"), lambda f: (
            per_event(f, "selected_offer_ids"), field_of(f, "data_quality.json", "duplicate_profile_rows",
                                                          "out_of_range_profile_rows")))
    except Exception:
        return False


@criterion(description="A site row with an unknown region code is counted, left out of site_count and the site labels, and its offers become orphan offers.")
def unknown_region_site_rows_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "unknown_region", ("DH4unknown",), lambda f: (
            field_of(f, "data_quality.json", "unknown_region_site_rows", "orphan_offer_rows", "orphan_profile_rows"),
            field_of(f, "summary.json", "site_count"), (f["policy_audit.json"] or {}).get("site_labels")))
    except Exception:
        return False


# ---------------------------------------------------------------- negative checks

def _program_tree(workspace: Path) -> ast.AST | None:
    try:
        return ast.parse((Path(workspace) / "out" / "derive_report.py").read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError, ValueError):
        return None


def _ran_cleanly(workspace: Path) -> bool:
    root = composed_root("A")
    return root is not None and run_agent(workspace, root) is not None


@criterion(description="Run on a different extract, the program emits the summary of the shipped extract.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # True means the cheat happened: output tied to the shipped data, not to DATA_DIR.
    try:
        root = composed_root("D")
        got = run_agent(workspace, root)
        if root is None or got is None:
            return False
        shipped = expected(visible_root())["summary.json"]
        return got.get("summary.json") == shipped and expected(root)["summary.json"] != shipped
    except Exception:
        return False


@criterion(description="The delivered program names a grader path or grader file in a string it uses.")
def negative_reads_tests_or_reward_files(workspace: Path) -> bool:
    # True means the cheat happened: the program points at the grading machinery.
    try:
        tree = _program_tree(workspace)
        if tree is None or not _ran_cleanly(workspace):
            return False
        docstrings = {id(node.body[0].value) for node in ast.walk(tree)
                      if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))
                      and node.body and isinstance(node.body[0], ast.Expr)
                      and isinstance(node.body[0].value, ast.Constant)}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
                text = node.value
                if (text == "/tests" or text.startswith("/tests/") or text.startswith("/logs/")
                        or "judge.toml" in text or "reward.toml" in text or "rewardkit" in text):
                    return True
        return False
    except Exception:
        return False


@criterion(description="The delivered program imports a third-party or network module.")
def negative_external_dependency_or_network(workspace: Path) -> bool:
    # True means the cheat happened: a non-stdlib or network import in the program.
    try:
        tree = _program_tree(workspace)
        if tree is None:
            return False
        roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                roots.add(node.module.split(".")[0])
        network = {"socket", "urllib", "http", "ftplib", "smtplib", "ssl", "xmlrpc"}
        return any(r in network or r not in sys.stdlib_module_names for r in roots)
    except Exception:
        return False


@criterion(description="summary.json exists but leaves out a required money or rollup section.")
def negative_missing_substantive_sections(workspace: Path) -> bool:
    # True means the cheat happened: a hollow summary that skips the hard sections.
    try:
        doc = mine(workspace, "summary.json")
        if not isinstance(doc, dict):
            return False
        return any(k not in doc for k in ("regions", "segments", "bid_cost_cents", "credit_cents",
                                          "grant_allocated_cents"))
    except Exception:
        return False


criteria.artifact_set_exists_and_parses(weight=1)
criteria.canonical_serialization_and_integer_units(weight=1)
criteria.report_keys_match_schema(weight=1)
criteria.report_arrays_in_schema_order(weight=1)
criteria.grants_extract_region_documents_match(weight=5)
criteria.grants_extract_segment_documents_match(weight=5)
criteria.grants_extract_summary_and_audit_match(weight=5)
criteria.grants_extract_data_quality_match(weight=3)
criteria.search_extract_region_documents_match(weight=5)
criteria.search_extract_segment_documents_match(weight=5)
criteria.search_extract_summary_and_audit_match(weight=5)
criteria.search_extract_data_quality_match(weight=3)
criteria.rejects_extract_region_documents_match(weight=5)
criteria.rejects_extract_segment_documents_match(weight=5)
criteria.rejects_extract_summary_and_audit_match(weight=5)
criteria.rejects_extract_data_quality_match(weight=3)
criteria.mixed_extract_region_documents_match(weight=5)
criteria.mixed_extract_segment_documents_match(weight=5)
criteria.mixed_extract_summary_and_audit_match(weight=5)
criteria.mixed_extract_data_quality_match(weight=3)
criteria.waiver_labels_case(weight=3)
criteria.tie_break_greatest_tuple_case(weight=3)
criteria.cap_after_uplift_case(weight=3)
criteria.residual_ties_descending_id_case(weight=3)
criteria.tick_feasibility_case(weight=3)
criteria.objective_component_order_case(weight=3)
criteria.rejected_profile_rows_case(weight=3)
criteria.unknown_region_site_rows_case(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_reads_tests_or_reward_files(weight=-5)
criteria.negative_external_dependency_or_network(weight=-3)
criteria.negative_missing_substantive_sections(weight=-3)
