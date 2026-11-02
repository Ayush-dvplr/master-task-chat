"""Verifier for district-heat-flex-procurement.

Every value check reruns the submitted derive_report.py, as an unprivileged user, on an
extract built here and compares its reports with an independent reference implementation
of schema.md. Two kinds of extract are used. Four composed extracts carry many events at
once and are graded as whole documents (all region files, both segment files, the summary
with the audit, the data-quality file), so one misread rule reaches every document it
touches. Small hand-built extracts each isolate one rule family, and two pairs of them differ
in one governed input only. Before a check runs, it
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
from datetime import datetime, timedelta, timezone
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
                       "DH4dup", "DH4range", "DH4seen", "DH4unknown", "DH5raw", "C34", "C45", "C5drop", "W0LIST",
                       "MULT0", "MULTtick", "OVR0", "OVRrate", "ADD0", "CAPpre", "UPL0", "R7offer", "R7up",
                       "R7offer_even", "LEDnone", "LEDstatic", "LEDid", "LEDstr", "LEDtie"})
# Wrong readings that change which offers the search picks (the others only change what is reported).
SEARCH_FLAGS = frozenset({"DH2", "H2", "C34", "C45", "C5drop", "DH4dup", "DH4range", "DH4unknown", "MULT0",
                          "MULTtick"})
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_AGENT_UID = 65534
_AGENT_TIMEOUT = 120

_SHIPPED_DATA: dict[str, str] = {}

_LOCK = threading.RLock()
_CACHE: dict[Any, Any] = {}
_RUN_WHY: dict[str, str] = {}
_SEARCH_MEMO: dict[Any, Any] = {}


# ---------------------------------------------------------------- arithmetic

def _q(num: int, den: int) -> int:
    """Round num/den half up (num, den >= 0)."""
    whole, rest = divmod(num, den)
    return whole + (1 if 2 * rest >= den else 0)


def _even(num: int, den: int) -> int:
    """Round num/den half to even (num, den >= 0)."""
    whole, rest = divmod(num, den)
    if 2 * rest > den or (2 * rest == den and whole % 2):
        return whole + 1
    return whole


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
    adder_of = {k.lower(): int(v) for k, v in cfg["segment_rate_adders"].items()} \
        if cfg.has_section("segment_rate_adders") else {}

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
            "pending": False, "status": "NONE", "signed": "", "base": 0, "cap": 0, "override": None,
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
            over = node.find("override")
            site[(node.attrib["event"], node.attrib["site"])].update(
                base=int(node.find("base").text), cap=int(node.find("cap").text),
                override=None if over is None else int(over.text))
    receipt = [x for x in (root / "export_manifest.tsv").read_text(encoding="utf-8").split("\n")
               if x.strip() and not x.startswith("#")]
    count["export_manifest.tsv"] = len(receipt) - 1
    allowance_lines = [x for x in (root / "site_allowances.tsv").read_text(encoding="utf-8").split("\n")
                       if x.strip() and not x.startswith("#")]
    allowance_rows = list(csv.DictReader(io.StringIO("\n".join(allowance_lines)), delimiter="\t"))
    count["site_allowances.tsv"] = len(allowance_rows)
    allowance = {r["site_id"]: int(r["allowance_ticks"]) for r in allowance_rows}
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
    listed_seen: set[tuple[str, int]] = set()
    for r in profile_rows:
        oid, itv = r["offer_id"], int(r["interval"])
        if oid not in listed:
            lost_profiles += 1
            continue
        width = span[listed[oid]]
        if "DH4seen" in lazy:
            if (oid, itv) in listed_seen:
                repeats += 1
                continue
            listed_seen.add((oid, itv))
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
            mult = int(r["register_multiplier"])
            for slot, column in (("r", "relief_wh"), ("v", "recovery_wh")):
                reading = int(r[column])
                if "MULT0" in lazy:
                    wh = reading
                elif "MULTtick" in lazy:
                    wh = tk(reading) * mult * wh_tick  # its ticks are the reading's ticks times the multiplier
                else:
                    wh = reading * mult
                offer[oid][slot][itv - 1] = wh

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

    def start_of(s: dict[str, Any]) -> int:
        return s["base"] if s["override"] is None or "OVR0" in lazy else s["override"]

    def adder(s: dict[str, Any]) -> int:
        return 0 if "ADD0" in lazy else adder_of.get(s["segment"].lower(), 0)

    def before_cap(s: dict[str, Any], uplift: int) -> int:
        return start_of(s) + uplift + adder(s)

    def rate(s: dict[str, Any], uplift: int) -> int:
        if "OVRrate" in lazy and s["override"] is not None:
            return s["override"]
        if "H3" in lazy:
            return min(start_of(s), s["cap"]) + uplift + adder(s)
        if "CAPpre" in lazy:
            return min(start_of(s) + uplift, s["cap"]) + adder(s)
        return min(before_cap(s, uplift), s["cap"])

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

    # Season ledger: events reach the site allowances in start order; chosen offers draw them down.
    if "LEDid" in lazy:
        walk = list(event_list)
    else:
        walk = sorted(event_list, key=lambda e: e["event_id"], reverse="LEDtie" not in lazy)
        if "LEDstr" in lazy:
            walk.sort(key=lambda e: e["dispatch_start"])
        else:
            walk.sort(key=lambda e: datetime.fromisoformat(e["dispatch_start"]))
    left = dict(allowance)
    picks: dict[tuple[str, str], tuple[list[dict[str, Any]], tuple[str, ...], int]] = {}
    blocked = 0
    for ev in walk:
        eid = ev["event_id"]
        width = int(ev["interval_count"])
        drawn: list[str] = []
        for region in region_names:
            every = pool_of.get((eid, region), [])
            if "LEDnone" in lazy:
                cands = list(every)
            else:
                cands = [o for o in every if sum(tk(x) for x in o["r"]) <= left[o["site"]["sid"]]]
            blocked += len(every) - len(cands)
            goals = [goal.get((eid, region, t + 1), (0, 0)) for t in range(width)]
            caps = [limit.get((eid, region, t + 1), (0, 0)) for t in range(width)]
            floors_here = {g: floor.get((eid, region, g), (0, 0)) for g in segment_names}
            memo_key = (str(root), lazy & SEARCH_FLAGS, eid, region, tuple(o["id"] for o in cands))
            if memo_key not in _SEARCH_MEMO:
                _SEARCH_MEMO[memo_key] = search(cands, goals, caps, floors_here, int(ev["objective"]["cost_weight"]),
                                                int(ev["objective"]["recovery_weight"]), width)
            winner, tied = _SEARCH_MEMO[memo_key]
            picks[(eid, region)] = (cands, winner, tied)
            drawn.extend(winner)
        if "LEDstatic" not in lazy:
            for i in drawn:
                left[offer[i]["site"]["sid"]] -= sum(tk(x) for x in offer[i]["r"])

    per_region: dict[str, list[dict[str, Any]]] = {r: [] for r in region_names}
    per_segment: dict[str, list[dict[str, Any]]] = {g: [] for g in segment_names}
    tie_log: list[dict[str, Any]] = []
    capped = residual_sum = residual_ties = 0
    empty = zero_floor = dead_pools = 0
    for ev in event_list:
        eid = ev["event_id"]
        width = int(ev["interval_count"])
        uplift = 0 if "UPL0" in lazy else int(ev["uplift_millicents_per_kwh"])
        for region in region_names:
            goals = [goal.get((eid, region, t + 1), (0, 0)) for t in range(width)]
            floors_here = {g: floor.get((eid, region, g), (0, 0)) for g in segment_names}
            cands, winner, tied = picks[(eid, region)]
            if not cands:
                empty += 1
            picked = [offer[i] for i in winner]
            if tied > 1:
                tie_log.append({"event_id": eid, "region": region, "tied_portfolio_count": tied,
                                "selected_offer_ids": list(winner)})
            den = 1000 * mc_cent
            numer: dict[str, list[int]] = {}
            for o in picked:
                each = [x if "H5t" in lazy else tk(x) * wh_tick for x in o["r"]]
                numer[o["id"]] = [wh * rate(o["site"], uplift) for wh in each]
                if "OVRrate" in lazy and o["site"]["override"] is not None:
                    capped += o["site"]["override"] > o["site"]["cap"]
                elif "H3" in lazy:
                    capped += start_of(o["site"]) + uplift > o["site"]["cap"]
                else:
                    capped += before_cap(o["site"], uplift) > o["site"]["cap"]

            def offer_credit(i: str) -> int:
                if "R7offer" in lazy:
                    return _q(sum(numer[i]), den)
                if "R7offer_even" in lazy:
                    return _even(sum(numer[i]), den)
                if "R7up" in lazy:
                    return sum(_q(x, den) for x in numer[i])
                return sum(_even(x, den) for x in numer[i])

            def money(ids: list[str]) -> int:
                if "H5c" in lazy:
                    return _q(sum(sum(numer[i]) for i in ids), den)
                return sum(offer_credit(i) for i in ids)

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
        "ineligible_offer_count": unauth, "allowance_blocked_offer_count": blocked,
        "empty_candidate_groups": empty, "zero_floor_count": zero_floor, "unallocated_pool_count": dead_pools,
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
    ini = f"[units]\nwh_per_tick = {spec.get('wh_per_tick', 10)}\nmillicents_per_cent = 1000\n\n[region_codes]\n"
    ini += "".join(f"{c} = {r}\n" for r, codes in REGION_CODES.items() for c in codes)
    ini += "\n[segment_codes]\n" + "".join(f"{k} = {v}\n" for k, v in SEGMENT_CODES.items())
    ini += ("\n# Rate adders, in mill-cents per kWh, by segment name. The value of an option is added to the\n"
            "# rate of every site row whose segment is that name.\n[segment_rate_adders]\n")
    ini += "".join(f"{g} = {v}\n" for g, v in sorted(spec.get("adders", {"commercial": 0, "public": 0}).items()))
    ini += "\n[export]\nwaiver_signed = Y\n"
    (folder / "program.ini").write_text(ini, encoding="utf-8")
    events = [{"event_id": e["event_id"], "name": "case",
               "dispatch_start": e.get("start") or f"2026-11-{1 + k // 24:02d}T{k % 24:02d}:00:00+01:00",
               "interval_count": e["n"], "objective": {"cost_weight": e["cw"], "recovery_weight": e["vw"]},
               "uplift_millicents_per_kwh": e["uplift"]} for k, e in enumerate(spec["events"])]
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
    cards = "".join(f'<card event="{s["event_id"]}" site="{s["sid"]}"><base>{s["base"]}</base>'
                    + ("" if s.get("override") is None else f'<override>{s["override"]}</override>')
                    + f'<cap>{s["cap"]}</cap></card>\n' for s in sites)
    (folder / "rate_cards.xml").write_text(f'<?xml version="1.0"?>\n{_CARD_COMMENT}<rate_cards>\n{cards}</rate_cards>\n',
                                           encoding="utf-8")
    tsv("recipient_weights.tsv", "\t", ["event_id", "site_id", "grant_weight"],
        [[s["event_id"], s["sid"], s["weight"]] for s in sites if s["weight"] is not None])
    allowances = spec.get("allowances", {})
    owned = sorted({s["sid"] for s in sites})
    (folder / "site_allowances.tsv").write_text(_ALLOWANCE_COMMENT + "site_id\tallowance_ticks\n" + "".join(
        f"{sid}\t{allowances.get(sid, 10 ** 9)}\n" for sid in owned), encoding="utf-8")
    offers = list(spec["offers"])
    offer_body = [[o["offer_id"], o["event_id"], o["sid"], "SETBACK_2C", o["cost"]] for o in offers]
    offer_body += [list(x) for x in spec.get("orphan_offer_rows", [])]
    profile_body = [[o["offer_id"], t + 1, o["r"][t], o["v"][t], o["m"][t]] for o in offers for t in range(len(o["r"]))]
    profile_body += [list(x) + [1] * (5 - len(x)) for x in spec.get("orphan_profile_rows", [])]
    if spec.get("reverse"):
        offer_body.reverse()
        profile_body.reverse()
    if "shuffle" in spec:
        mixer = Rng(spec["shuffle"])
        mixer.shuffle(offer_body)
        mixer.shuffle(profile_body)
    profile_body += [list(x) + [1] * (5 - len(x)) for x in spec.get("late_profile_rows", [])]
    tsv("offers.csv", ",", ["offer_id", "event_id", "site_id", "mode_label", "bid_cost_cents"], offer_body)
    tsv("profiles.tsv", "\t", ["offer_id", "interval", "relief_wh", "recovery_wh", "register_multiplier"],
        profile_body)
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
    _write_receipt(folder)
    _seal(folder)
    return folder


_CARD_COMMENT = (
    "<!--\n"
    "  Rate cards of this extract, one card per site row; every rate is in mill-cents per kWh.\n"
    "  The rate of a site row starts from the base element of its card. A card that also carries an\n"
    "  override element starts from the override value instead of the base value.\n"
    "  The effective rate of a site row is its rate with its card's cap applied as the programme\n"
    "  conventions say.\n"
    "  credit_cents of a chosen offer is the sum, over the intervals of its event, of its interval\n"
    "  amounts. An interval amount is the offer's relief ticks in that interval times wh_per_tick, times\n"
    "  the effective rate of the offer's site row, divided by 1000 times millicents_per_cent, rounded\n"
    "  half to even to whole cents.\n"
    "-->\n")


_ALLOWANCE_COMMENT = (
    "# Season relief allowance of each site, in energy ticks; one row per site_id of sites.csv.\n"
    "# The allowance of a site is drawn by the events of the season, which reach it one at a time in the\n"
    "# order of the instants at which they start (dispatch_start in events.json), events that start at the\n"
    "# same instant following the programme conventions. When an event is reached, what remains of a\n"
    "# site's allowance is its allowance_ticks less the relief ticks, over all intervals, of the site's\n"
    "# offers chosen in the events reached before it. An offer whose relief ticks over all intervals are\n"
    "# more than what remains of its site's allowance when its event is reached is not a candidate offer.\n")


def _write_receipt(folder: Path) -> None:
    """export_manifest.tsv: record counts and written-field sums of the files just written."""
    def plain(name: str, sep: str) -> list[dict[str, str]]:
        return _records(folder / name, sep)

    lines = [("events.json", len(json.loads((folder / "events.json").read_text(encoding="utf-8"))), "", "")]
    for name, sep, fields in (("sites.csv", ",", ()), ("offers.csv", ",", ("bid_cost_cents",)),
                              ("profiles.tsv", "\t", ("relief_wh", "recovery_wh")), ("targets.tsv", "\t", ("target_wh",)),
                              ("continuity_waivers.csv", ",", ()), ("recipient_weights.tsv", "\t", ("grant_weight",))):
        rows = plain(name, sep)
        lines += [(name, len(rows), f, str(sum(int(r[f]) for r in rows))) for f in fields] or [(name, len(rows), "", "")]
    held = [x.split("\t") for x in (folder / "site_allowances.tsv").read_text(encoding="utf-8").split("\n")
            if x.strip() and not x.startswith("#")][1:]
    lines.append(("site_allowances.tsv", len(held), "allowance_ticks", str(sum(int(x[1]) for x in held))))
    feeder = _columns(folder / "feeder_limits.txt", [(18, 27)])
    lines.append(("feeder_limits.txt", len(feeder), "relief_ceiling_wh", str(sum(int(x[0]) for x in feeder))))
    pools = _columns(folder / "pools.txt", [(15, 26)])
    lines.append(("pools.txt", len(pools), "pool_cents", str(sum(int(x[0]) for x in pools))))
    states = [x for x in (folder / "site_state.jsonl").read_text(encoding="utf-8").split("\n") if x.strip()]
    lines.append(("site_state.jsonl", len(states), "", ""))
    floors = json.loads((folder / "segment_floors.json").read_text(encoding="utf-8"))["floors"]
    lines.append(("segment_floors.json", len(floors), "floor_wh", str(sum(int(f["floor_wh"]) for f in floors))))
    cards = list(ElementTree.fromstring((folder / "rate_cards.xml").read_text(encoding="utf-8")).iter("card"))
    lines.append(("rate_cards.xml", len(cards), "base", str(sum(int(c.find("base").text) for c in cards))))
    text = ("# Export receipt, written by the export tool after it wrote the other files of this extract.\n"
            "# Each line names a file and gives its records, counted the way data_quality.json counts the\n"
            "# rows of that file. Where a field is named, field_sum is the sum of that field's values as they\n"
            "# are written in the file, over all of its records; otherwise field and field_sum are empty.\n"
            "# A file whose lines here agree with it arrived whole.\n"
            "file\trecords\tfield\tfield_sum\n")
    text += "".join(f"{a}\t{b}\t{c}\t{d}\n" for a, b, c, d in lines)
    (folder / "export_manifest.tsv").write_text(text, encoding="utf-8")


def _site(eid: str, sid: str, **extra: Any) -> dict[str, Any]:
    row = {"event_id": eid, "sid": sid, "code": "N1", "seg": "C", "ben": f"BEN-{sid}", "critical": False, "auth": True,
           "hold": False, "cool": False, "pending": False, "status": "NONE", "signed": "", "base": 4000,
           "cap": 9000, "override": None, "weight": None}
    row.update(extra)
    return row


def _offer(eid: str, sid: str, letter: str, cost: int, relief: list[int], recovery: list[int] | None = None,
           mult: list[int] | None = None):
    """relief and recovery are register readings; mult is the register multiplier of each interval's row."""
    return {"offer_id": f"{eid}-{sid}-{letter}", "event_id": eid, "sid": sid, "cost": cost, "r": relief,
            "v": recovery or [0] * len(relief), "m": mult or [1] * len(relief)}


def _event(eid: str, n: int, cw: int = 1, vw: int = 0, uplift: int = 0, start: str | None = None) -> dict[str, Any]:
    return {"event_id": eid, "n": n, "cw": cw, "vw": vw, "uplift": uplift, "start": start}


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
    if name == "rate":
        # A public card with an override whose rate before cap passes the cap, and a commercial card with an
        # override and room under the cap.
        e = "T3-0001"
        sites = [_site(e, "S-PUB", seg="P", base=6000, override=3000, cap=4000),
                 _site(e, "S-COM", seg="C", base=2000, override=5000, cap=9000)]
        offers = [_offer(e, "S-PUB", "A", 100, [10000]), _offer(e, "S-COM", "A", 100, [10000])]
        return _single(e, sites, offers, 1, [(100000, 1)], event={"uplift": 500},
                       adders={"commercial": 0, "public": 750})
    if name == "multiplier":
        e = "T3-0002"
        sites = [_site(e, "S1"), _site(e, "S2")]
        offers = [_offer(e, "S1", "X", 100, [5, 3000], mult=[3, 2]), _offer(e, "S2", "Y", 100, [10, 0])]
        return _single(e, sites, offers, 2, [(30, 2), (6000, 1)], [(30, 500000), (500000, 500000)])
    if name == "rounding":
        e = "T3-0003"
        sites = [_site(e, "S1", base=1000, cap=9000), _site(e, "S2", base=1000, cap=9000)]
        offers = [_offer(e, "S1", "A", 100, [500, 500]), _offer(e, "S2", "A", 100, [1500, 500])]
        return _single(e, sites, offers, 2, [(100000, 1), (100000, 1)])
    if name in ("mut_adder", "mut_adder_moved"):
        # Two events with public and commercial sites, overrides and register multipliers. The *_moved twin
        # changes one governed constant of program.ini and nothing else.
        rng = Rng(23)
        spec = {"events": [], "sites": [], "offers": [], "targets": {}, "limits": {}, "floors": [], "pools": {},
                "adders": {"commercial": 0, "public": 1500 if name == "mut_adder_moved" else 500}}
        for k, eid in enumerate(("T8-0001", "T8-0002")):
            n = 3
            spec["events"].append(_event(eid, n, 1, 1, [250, 1000][k]))
            for i in range(5):
                sid = f"M{k}{i}"
                spec["sites"].append(_site(eid, sid, seg="CP"[i % 2], base=rng.between(2, 6) * 1000,
                                           cap=rng.between(5, 9) * 1000,
                                           override=rng.between(1, 4) * 1000 if i in (1, 2) else None))
                for letter in "AB":
                    mult = [rng.pick([1, 1, 2, 3]) for _ in range(n)]
                    spec["offers"].append(_offer(eid, sid, letter, rng.between(100, 3000),
                                                 [rng.between(0, 60 // m) * 5 + 3 for m in mult],
                                                 [rng.between(0, 30 // m) * 5 for m in mult], mult))
            spec["targets"][(eid, "North")] = [(rng.between(40, 90) * 5, 2) for _ in range(n)]
            spec["limits"][(eid, "North")] = [(rng.between(80, 160) * 5, rng.between(60, 120) * 5) for _ in range(n)]
        return spec
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
            e, "F3", "Z", twin["cost"], list(twin["r"]), list(twin["v"]), list(twin["m"]))
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
                                      [f"{e2}-S1-A", 3, 7000, 0], [f"{e2}-S1-A", 3, 8000, 0]]}
    if name == "unknown_region":
        e = "T9-0003"
        sites = [_site(e, "S1"), _site(e, "S-X", code="Z9", ben="BEN-X", weight=2, **_ELIGIBLE)]
        offers = [_offer(e, "S1", "A", 10, [1000]), _offer(e, "S-X", "A", 10, [1000])]
        return _single(e, sites, offers, 1, [(10000, 1)], pools={(e, "North"): 40})
    if name == "allowance_order":
        # One site per pair of events. The first pair starts in an order that differs from both the id order and
        # the order of the written strings; the second pair starts at one instant written with two offsets.
        pairs = (("AL-1", ("T5-0001", "2026-12-01T09:00:00+00:00"), ("T5-0002", "2026-12-01T09:30:00+01:00")),
                 ("AL-2", ("T5-0003", "2026-12-01T12:00:00+01:00"), ("T5-0004", "2026-12-01T11:00:00+00:00")))
        spec = {"events": [], "sites": [], "offers": [], "targets": {}, "limits": {}, "allowances": {}}
        for sid, *events in pairs:
            spec["allowances"][sid] = 150
            for eid, start in events:
                spec["events"].append(_event(eid, 1, start=start))
                spec["sites"].append(_site(eid, sid))
                spec["offers"].append(_offer(eid, sid, "A", 100, [1000]))
                spec["targets"][(eid, "North")] = [(100000, 1)]
                spec["limits"][(eid, "North")] = _wide(1)
        return spec
    if name in ("allowance_consumption", "mut_allowance", "mut_allowance_moved"):
        # Sites that take part in several events: what an earlier event draws is gone for a later one.
        if name == "allowance_consumption":
            plan = (("T5-0101", "2026-12-02T10:00:00+00:00", ("AL-3", "AL-4")),
                    ("T5-0102", "2026-12-02T11:00:00+00:00", ("AL-3", "AL-5")))
            allowances = {"AL-3": 150, "AL-4": 50, "AL-5": 400}
            relief = {"AL-3": [600, 400], "AL-4": [500, 500], "AL-5": [300, 300]}
        else:
            plan = tuple((eid, start, ("AL-6", "AL-7", "AL-8")) for eid, start in (
                ("T5-0201", "2026-12-03T10:00:00+00:00"), ("T5-0202", "2026-12-03T09:00:00+01:00"),
                ("T5-0203", "2026-12-03T09:00:00+00:00")))
            allowances = {"AL-6": 190 if name == "mut_allowance_moved" else 130, "AL-7": 70, "AL-8": 1000}
            relief = {"AL-6": [400, 200], "AL-7": [300, 300], "AL-8": [200, 100]}
        spec = {"events": [], "sites": [], "offers": [], "targets": {}, "limits": {}, "allowances": allowances}
        for eid, start, sids in plan:
            spec["events"].append(_event(eid, 2, start=start))
            for sid in sids:
                spec["sites"].append(_site(eid, sid))
                spec["offers"].append(_offer(eid, sid, "A", 100, relief[sid]))
            spec["targets"][(eid, "North")] = [(100000, 1)] * 2
            spec["limits"][(eid, "North")] = _wide(2)
        return spec
    raise KeyError(name)


# Composed extracts: many events at once, graded as whole documents. `mix` sets how dense each kind of
# difficulty is (percent chances per site or per event-region unless noted).
MIXES: dict[str, dict[str, int]] = {
    "A": {"events": 14, "big": 0, "waiver": 18, "hold": 14, "tie": 8, "zero": 4, "flat": 15, "pool_low": 60,
          "bens": 7, "reject": 2, "unknown": 1, "mult": 10, "override": 25},
    "B": {"events": 12, "big": 22, "waiver": 6, "hold": 8, "tie": 22, "zero": 12, "flat": 40, "pool_low": 30,
          "bens": 12, "reject": 3, "unknown": 1, "mult": 8, "override": 10},
    "C": {"events": 14, "big": 4, "waiver": 8, "hold": 8, "tie": 8, "zero": 6, "flat": 20, "pool_low": 35,
          "bens": 9, "reject": 14, "unknown": 5, "mult": 12, "override": 15},
    "D": {"events": 16, "big": 8, "waiver": 10, "hold": 10, "tie": 12, "zero": 8, "flat": 25, "pool_low": 45,
          "bens": 8, "reject": 6, "unknown": 3, "mult": 10, "override": 20},
}


# Hand-built events carried inside each composed extract next to the seeded ones, so that the rules they
# isolate also reach the whole-document checks.
PLANTED = {"A": ("waiver", "residual", "rate", "rounding"), "B": ("tie", "tick_feasibility", "components", "full",
                                                                   "multiplier"),
           "C": ("rejected", "unknown_region", "multiplier"),
           "D": ("residual", "rate", "rounding", "tick_feasibility", "components", "full")}


def _plant(spec: dict[str, Any], names: tuple[str, ...]) -> None:
    for name in names:
        extra = case_spec(name)
        for key in ("events", "sites", "offers", "floors", "orphan_offer_rows", "orphan_profile_rows",
                    "late_profile_rows"):
            spec[key].extend(extra.get(key, []))
        for key in ("targets", "limits", "pools", "allowances"):
            spec.setdefault(key, {}).update(extra.get(key, {}))


def _composed_spec(tag: str, seed: int) -> dict[str, Any]:
    """A seeded extract that exercises every rule of the contract at once, with all stated limits respected."""
    mix = MIXES[tag]
    rng = Rng(seed * 7919 + ord(tag))
    spec: dict[str, Any] = {"events": [], "sites": [], "offers": [], "targets": {}, "limits": {}, "floors": [],
                            "pools": {}, "orphan_offer_rows": [], "orphan_profile_rows": [],
                            "late_profile_rows": [],
                            "adders": {"commercial": rng.pick([0, 0, 250]), "public": rng.pick([500, 750, 1250])}}
    prefix = f"{tag}{seed % 90 + 10}"
    # Each region draws its site rows from a small set of sites, so a site takes part in many events.
    roster = {region: [f"KS{region[0]}{rng.between(100, 999)}{i}" for i in range(10)] for region in REGION_CODES}
    season = datetime(2026, 12, 1, tzinfo=timezone.utc)
    for k in range(mix["events"]):
        eid = f"{prefix}-{100 + 37 * k:04d}"
        n = rng.between(2, 5)
        flat = rng.chance(mix["flat"])
        instant = season + timedelta(minutes=30 * rng.between(0, mix["events"]))
        start = instant.astimezone(timezone(timedelta(hours=rng.pick([0, 1, 1, 2, -5])))).isoformat()
        spec["events"].append(_event(eid, n, 0 if flat else rng.between(1, 3), 0 if flat else rng.between(0, 2),
                                     rng.pick([0, 250, 500, 1000, 2000]), start))
        uplift = spec["events"][-1]["uplift"]
        for region in REGION_CODES:
            count = 0 if rng.chance(8) else (rng.between(5, 8) if rng.chance(mix["big"]) else rng.between(1, 4))
            local = []
            chosen_ids = list(roster[region])
            rng.shuffle(chosen_ids)
            for i in range(count):
                sid = chosen_ids[i]
                if rng.chance(mix["waiver"]):
                    fields = dict(_ELIGIBLE)
                else:
                    fields = {"seg": rng.pick(["C", "P", "P"]), "critical": rng.chance(60), "pending": rng.chance(45),
                              "status": rng.pick(["VALID", "VALID", "EXPIRED", "NONE", "REVOKED"]),
                              "signed": rng.pick(["Y", "Y", "N", ""])}
                weight = None if rng.chance(8) else (0 if rng.chance(10) else rng.between(1, 4))
                base = rng.between(2, 9) * 1000
                over = rng.between(1, 9) * 1000 + rng.pick([0, 250, 500]) if rng.chance(mix["override"]) else None
                local.append(_site(eid, sid, code=rng.pick(REGION_CODES[region]), ben=f"BEN-{rng.between(1, mix['bens'])}",
                                   auth=not rng.chance(10), hold=rng.chance(mix["hold"]), cool=rng.chance(mix["hold"]),
                                   base=base, cap=max(500, base + rng.pick([-1500, -500, 0, 300, 1000, 4000])),
                                   override=over, weight=weight, **fields))
                letters = "ABC"[:rng.between(1, 3)]
                made = []
                for letter in letters:
                    mult = [rng.pick([2, 3, 5]) if rng.chance(mix["mult"]) else 1 for _ in range(n)]
                    relief = [rng.between(0, 120 // m) * 5 if rng.chance(60) else 0 for m in mult]
                    recovery = [rng.between(0, 80 // m) * 5 if rng.chance(35) else 0 for m in mult]
                    made.append(_offer(eid, sid, letter, rng.between(300, 20000), relief, recovery, mult))
                if len(made) < 3 and rng.chance(mix["tie"]):
                    made.append(_offer(eid, sid, "Z", made[0]["cost"], list(made[0]["r"]), list(made[0]["v"]),
                                       list(made[0]["m"])))
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
            spec["late_profile_rows"].append([o["offer_id"], rng.between(1, width), rng.between(1, 400) * 5, 0,
                                              rng.pick([1, 3])])
        elif kind == 1:
            spec["late_profile_rows"].append([o["offer_id"], rng.pick([0, width + 1]), rng.between(1, 400) * 5, 0])
        else:
            spec["orphan_profile_rows"].append([f"NOPE-{rng.between(100, 999)}", 1, rng.between(1, 400) * 5, 0])
    spec["orphan_offer_rows"] = [[f"{prefix}-GHOST-A", spec["events"][0]["event_id"], "QX0000", "SETBACK_4C", 900]]
    # Allowances: for most sites a share of what the site's largest offers of the season would draw.
    widest: dict[str, int] = {}
    for o in spec["offers"]:
        total = sum(_q(r * m, 10) for r, m in zip(o["r"], o["m"]))
        key = (o["sid"], o["event_id"])
        widest[key] = max(widest.get(key, 0), total)
    demand: dict[str, int] = {}
    for (sid, _), total in widest.items():
        demand[sid] = demand.get(sid, 0) + total
    spec["allowances"] = {sid: demand[sid] * rng.pick([20, 35, 50, 65, 80, 400]) // 100 for sid in sorted(demand)}
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
    "A": {"regions": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "LEDtie", "UPL0", "H1", "H1order", "H1hc",
                      "SIGNEDY", "DH3", "DH5raw", "H4", "H3", "W0LIST", "OVR0", "OVRrate", "ADD0", "R7offer",
                      "R7up", "MULT0"),
          "segments": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "H3", "H5t", "ADD0", "R7offer", "OVR0"),
          "summary": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "DH3", "R7offer", "MULT0", "ADD0"),
          "audit": ("LEDstatic", "LEDid", "H1", "H1hc", "H1pend", "SIGNEDY", "H3", "DH3", "CAPpre", "OVR0"),
          "quality": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "DH4dup", "DH4unknown")},
    "B": {"regions": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "LEDtie", "H2", "DH2", "C34", "C45",
                      "C5drop", "H5t", "DH3", "H3", "MULT0", "MULTtick"),
          "segments": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "H2", "DH2", "C34", "C45", "H5t", "MULT0",
                       "MULTtick"),
          "summary": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "MULT0", "MULTtick", "DH2"),
          "audit": ("LEDstatic", "LEDid", "H2", "C5drop", "DH3", "MULT0"),
          "quality": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "DH4range", "DH4unknown")},
    "C": {"regions": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "LEDtie", "DH4dup", "DH4range", "H3", "DH3",
                      "DH5raw", "H4", "MULT0", "MULTtick", "OVR0"),
          "segments": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "DH4dup", "DH4range", "H3", "MULT0"),
          "summary": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "DH4dup", "MULT0", "OVR0"),
          "audit": ("LEDstatic", "LEDid", "DH4unknown", "H3", "DH3", "H1", "OVR0"),
          "quality": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "DH4dup", "DH4range", "DH4unknown")},
    "D": {"regions": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "LEDtie", "UPL0", "H1order", "H2", "H3",
                      "DH2", "DH3", "DH5raw", "W0LIST", "C34", "C45", "H4", "MULT0", "MULTtick", "OVR0",
                      "OVRrate", "ADD0", "CAPpre", "R7offer", "R7up"),
          "segments": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "H2", "H3", "H5t", "DH2", "C34", "MULT0",
                       "ADD0", "R7offer"),
          "summary": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "MULT0", "OVR0", "ADD0", "R7offer", "R7up"),
          "audit": ("LEDstatic", "LEDid", "H1", "H1pend", "H2", "H3", "DH3", "DH4unknown", "CAPpre",
                    "OVRrate"),
          "quality": ("LEDnone", "LEDstatic", "LEDid", "LEDstr", "DH4dup", "DH4range", "DH4unknown")},
}


def _region_docs(files: dict[str, Any]) -> Any:
    return [files.get(f"region_{r}.json") for r in REGION_CODES]


def _segment_docs(files: dict[str, Any]) -> Any:
    return [files.get(f"segment_{g}.json") for g in SEGMENT_CODES.values()]


def _summary_doc(files: dict[str, Any]) -> Any:
    return files.get("summary.json")


def _audit_doc(files: dict[str, Any]) -> Any:
    return files.get("policy_audit.json")


def _quality_doc(files: dict[str, Any]) -> Any:
    return files.get("data_quality.json")


VIEWS = {"regions": _region_docs, "segments": _segment_docs, "summary": _summary_doc, "audit": _audit_doc,
         "quality": _quality_doc}


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


def _grant_read(argument: str) -> None:
    """Make an agent-written path readable before the uid drop (an editor leaves it at mode 0600)."""
    if not argument.startswith("/app"):
        return
    path = Path(argument)
    if not path.exists():
        return
    try:
        path.chmod(path.stat().st_mode | (0o555 if path.is_dir() else 0o444))
        for parent in path.parents:
            parent.chmod(parent.stat().st_mode | 0o555)
            if str(parent) == "/app":
                break
    except OSError:
        pass


def _untrusted(command: list[str]) -> list[str]:
    if os.name == "posix" and os.geteuid() == 0:
        for argument in command:
            _grant_read(argument)
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
        _RUN_WHY[str(data)] = "derive_report.py is missing"
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
                else:
                    _RUN_WHY[str(data)] = ("timed out after %d s" % _AGENT_TIMEOUT if code is None
                                           else f"exited with code {code}" if code else "wrote no OUT_DIR")
            except OSError as exc:
                result = None
                _RUN_WHY[str(data)] = f"could not be staged: {exc}"
            finally:
                shutil.rmtree(box, ignore_errors=True)
        _CACHE[key] = result
        return result


def mine(workspace: Path, name: str) -> Any:
    return produced(Path(workspace) / "out", name)


# ---------------------------------------------------------------- failure messages

def _note(name: str, message: str) -> None:
    """Record why a check ended as it did in the verifier's stdout log, so a crash, a timeout and a wrong value
    can be told apart after the run."""
    print(f"[check] {json.dumps({'check': name, 'message': message})}", flush=True)


def _graded(name: str, thunk) -> bool:
    try:
        ok, why = thunk()
    except Exception as exc:  # the check must return a bool; the reason is kept, never discarded
        ok, why = False, f"check raised {type(exc).__name__}: {exc}"
    _note(name, "passed" if ok else why)
    return bool(ok)


def _first_difference(got: Any, want: Any, path: str = "") -> str:
    if type(got) is not type(want):
        return f"{path or '<root>'}: expected {type(want).__name__}, got {type(got).__name__}"
    if isinstance(want, dict):
        if set(got) != set(want):
            return f"{path or '<root>'}: keys differ (missing {sorted(set(want) - set(got))[:3]}, extra {sorted(set(got) - set(want))[:3]})"
        for k in sorted(want):
            if canon(got[k]) != canon(want[k]):
                return _first_difference(got[k], want[k], f"{path}.{k}")
    if isinstance(want, list):
        if len(got) != len(want):
            return f"{path or '<root>'}: expected {len(want)} entries, got {len(got)}"
        for i, (a, b) in enumerate(zip(got, want)):
            if canon(a) != canon(b):
                return _first_difference(a, b, f"{path}[{i}]")
    return f"{path or '<root>'}: expected {canon(want)[:80]}, got {canon(got)[:80]}"


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


def _run_failed(root: Path) -> str:
    return "program run failed: " + _RUN_WHY.get(str(root), "unknown")


def case_passes(workspace: Path, name: str, rules: tuple[str, ...], observe) -> tuple[bool, str]:
    if not separated(name, rules, observe):
        return False, f"grader fault: case {name} does not separate {rules}"
    root = case_root(name)
    got = run_agent(workspace, root)
    if got is None:
        return False, _run_failed(root)
    want = observe(expected(root))
    mine_ = observe(got)
    if canon(mine_) == canon(want):
        return True, ""
    return False, "wrong value: " + _first_difference(mine_, want)


def composed_passes(workspace: Path, tag: str, view: str) -> tuple[bool, str]:
    root = composed_root(tag)
    if root is None:
        return False, f"grader fault: no separating seed for extract {tag}"
    got = run_agent(workspace, root)
    if got is None:
        return False, _run_failed(root)
    want = VIEWS[view](expected(root))
    mine_ = VIEWS[view](got)
    if canon(mine_) == canon(want):
        return True, ""
    return False, "wrong value: " + _first_difference(mine_, want)


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

def _composed(workspace: Path, tag: str, view: str, name: str) -> bool:
    return _graded(name, lambda: composed_passes(workspace, tag, view))


@criterion(description="On a seeded extract rich in waivers, holds, overrides and grant pools, the four region files match the contract in every entry.")
def grants_extract_region_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "A", "regions", "grants_extract_region_documents_match")


@criterion(description="On the same extract both segment files match the contract in every entry.")
def grants_extract_segment_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "A", "segments", "grants_extract_segment_documents_match")


@criterion(description="On the same extract summary.json matches the contract in every entry.")
def grants_extract_summary_document_matches(workspace: Path) -> bool:
    return _composed(workspace, "A", "summary", "grants_extract_summary_document_matches")


@criterion(description="On the same extract policy_audit.json matches the contract in every entry.")
def grants_extract_policy_audit_document_matches(workspace: Path) -> bool:
    return _composed(workspace, "A", "audit", "grants_extract_policy_audit_document_matches")


@criterion(description="On the same extract data_quality.json matches the contract in every entry.")
def grants_extract_data_quality_document_matches(workspace: Path) -> bool:
    return _composed(workspace, "A", "quality", "grants_extract_data_quality_document_matches")


@criterion(description="On a seeded extract with tied portfolios, twin offers, register multipliers and groups of up to eight sites, the four region files match the contract in every entry.")
def search_extract_region_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "B", "regions", "search_extract_region_documents_match")


@criterion(description="On the same extract both segment files match the contract in every entry.")
def search_extract_segment_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "B", "segments", "search_extract_segment_documents_match")


@criterion(description="On the same extract summary.json matches the contract in every entry.")
def search_extract_summary_document_matches(workspace: Path) -> bool:
    return _composed(workspace, "B", "summary", "search_extract_summary_document_matches")


@criterion(description="On the same extract policy_audit.json matches the contract in every entry.")
def search_extract_policy_audit_document_matches(workspace: Path) -> bool:
    return _composed(workspace, "B", "audit", "search_extract_policy_audit_document_matches")


@criterion(description="On the same extract data_quality.json matches the contract in every entry.")
def search_extract_data_quality_document_matches(workspace: Path) -> bool:
    return _composed(workspace, "B", "quality", "search_extract_data_quality_document_matches")


@criterion(description="On a seeded extract with repeated, out-of-range, orphan and unknown-region rows in reversed row order, the four region files match the contract in every entry.")
def rejects_extract_region_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "C", "regions", "rejects_extract_region_documents_match")


@criterion(description="On the same extract both segment files match the contract in every entry.")
def rejects_extract_segment_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "C", "segments", "rejects_extract_segment_documents_match")


@criterion(description="On the same extract summary.json matches the contract in every entry.")
def rejects_extract_summary_document_matches(workspace: Path) -> bool:
    return _composed(workspace, "C", "summary", "rejects_extract_summary_document_matches")


@criterion(description="On the same extract policy_audit.json matches the contract in every entry.")
def rejects_extract_policy_audit_document_matches(workspace: Path) -> bool:
    return _composed(workspace, "C", "audit", "rejects_extract_policy_audit_document_matches")


@criterion(description="On the same extract data_quality.json matches the contract in every entry.")
def rejects_extract_data_quality_document_matches(workspace: Path) -> bool:
    return _composed(workspace, "C", "quality", "rejects_extract_data_quality_document_matches")


@criterion(description="On a seeded mixed extract with shuffled rows, the four region files match the contract in every entry.")
def mixed_extract_region_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "D", "regions", "mixed_extract_region_documents_match")


@criterion(description="On the same extract both segment files match the contract in every entry.")
def mixed_extract_segment_documents_match(workspace: Path) -> bool:
    return _composed(workspace, "D", "segments", "mixed_extract_segment_documents_match")


@criterion(description="On the same extract summary.json matches the contract in every entry.")
def mixed_extract_summary_document_matches(workspace: Path) -> bool:
    return _composed(workspace, "D", "summary", "mixed_extract_summary_document_matches")


@criterion(description="On the same extract policy_audit.json matches the contract in every entry.")
def mixed_extract_policy_audit_document_matches(workspace: Path) -> bool:
    return _composed(workspace, "D", "audit", "mixed_extract_policy_audit_document_matches")


@criterion(description="On the same extract data_quality.json matches the contract in every entry.")
def mixed_extract_data_quality_document_matches(workspace: Path) -> bool:
    return _composed(workspace, "D", "quality", "mixed_extract_data_quality_document_matches")


# ---------------------------------------------------------------- one rule family each

@criterion(description="A site row's rate starts from its card override or base, adds the event uplift and its segment's rate adder, and the cap binds that sum.")
def rate_composition_case(workspace: Path) -> bool:
    return _graded("rate_composition_case", lambda: case_passes(workspace, "rate", ("OVR0", "OVRrate", "UPL0", "ADD0", "CAPpre", "H3"), lambda f: (
            [(e.get("region"), e.get("credit_cents")) for g in ("commercial", "public")
             for e in (f[f"segment_{g}.json"] or {}).get("event_regions", []) if e.get("region") == "North"],
            field_of(f, "policy_audit.json", "cap_binding_count"))))


@criterion(description="Each interval amount of an offer's credit is rounded half to even to whole cents before the offer's interval amounts are summed.")
def interval_credit_rounding_case(workspace: Path) -> bool:
    return _graded("interval_credit_rounding_case", lambda: case_passes(workspace, "rounding", ("R7offer", "R7up", "R7offer_even", "H5c"), lambda f: (
            first_event(f, "credit_cents"), field_of(f, "summary.json", "credit_cents"))))


def _ledger_view(files: dict[str, Any]) -> Any:
    return (per_event(files, "candidate_offer_count"), per_event(files, "selected_offer_ids"),
            field_of(files, "data_quality.json", "allowance_blocked_offer_count", "empty_candidate_groups"))


@criterion(description="A site's season allowance is drawn by events in the order of their start instants, with events that start at the same instant in descending id order.")
def allowance_order_case(workspace: Path) -> bool:
    return _graded("allowance_order_case", lambda: case_passes(workspace, "allowance_order", ("LEDid", "LEDtie", "LEDstr"), _ledger_view))


@criterion(description="Relief chosen for a site in an earlier event reduces what remains of its allowance, and an offer larger than what remains is not a candidate.")
def allowance_consumption_case(workspace: Path) -> bool:
    return _graded("allowance_consumption_case", lambda: case_passes(workspace, "allowance_consumption", ("LEDstatic", "LEDnone"), _ledger_view))


def _credit_family(files: dict[str, Any]) -> Any:
    try:
        return [(e["event_id"], e["selected_offer_ids"], e["credit_cents"]) for e in files["region_North.json"]["events"]]
    except (KeyError, TypeError):
        return None


def mutation_passes(workspace: Path, base: str, moved: str, observe, fixed) -> bool:
    """The governed constant changes between base and moved; observe must follow the contract in both runs,
    and the reference must show that observe moves while fixed does not."""
    want_a, want_b = expected(case_root(base)), expected(case_root(moved))
    if canon(observe(want_a)) == canon(observe(want_b)) or canon(fixed(want_a)) != canon(fixed(want_b)):
        return False, f"grader fault: {moved} does not move only the governed family"
    got_a, got_b = run_agent(workspace, case_root(base)), run_agent(workspace, case_root(moved))
    if got_a is None or got_b is None:
        return False, _run_failed(case_root(base) if got_a is None else case_root(moved))
    for label, got, want in (("before the change", got_a, want_a), ("after the change", got_b, want_b)):
        if canon(observe(got)) != canon(observe(want)):
            return False, f"wrong value {label}: " + _first_difference(observe(got), observe(want))
    return True, ""


def _costs(files: dict[str, Any]) -> Any:
    try:
        return [(e["event_id"], e["bid_cost_cents"]) for e in files["region_North.json"]["events"]]
    except (KeyError, TypeError):
        return None


@criterion(description="Raising the public segment rate adder in program.ini moves the credits of the region file as the contract says, with the same portfolios.")
def segment_rate_adder_mutation(workspace: Path) -> bool:
    return _graded("segment_rate_adder_mutation", lambda: mutation_passes(workspace, "mut_adder", "mut_adder_moved", _credit_family, _costs))


@criterion(description="Raising one site's allowance_ticks in site_allowances.tsv moves the candidates and portfolios of the later events that site takes part in, and no compliance label.")
def allowance_ticks_mutation(workspace: Path) -> bool:
    return _graded("allowance_ticks_mutation", lambda: mutation_passes(workspace, "mut_allowance", "mut_allowance_moved", _ledger_view, lambda f: field_of(
            f, "policy_audit.json", "site_labels")))


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


criteria.artifact_set_exists_and_parses(weight=1)
criteria.canonical_serialization_and_integer_units(weight=1)
criteria.report_keys_match_schema(weight=1)
criteria.report_arrays_in_schema_order(weight=1)
criteria.grants_extract_region_documents_match(weight=5)
criteria.grants_extract_segment_documents_match(weight=5)
criteria.grants_extract_summary_document_matches(weight=3)
criteria.grants_extract_policy_audit_document_matches(weight=3)
criteria.grants_extract_data_quality_document_matches(weight=3)
criteria.search_extract_region_documents_match(weight=5)
criteria.search_extract_segment_documents_match(weight=5)
criteria.search_extract_summary_document_matches(weight=3)
criteria.search_extract_policy_audit_document_matches(weight=3)
criteria.search_extract_data_quality_document_matches(weight=3)
criteria.rejects_extract_region_documents_match(weight=5)
criteria.rejects_extract_segment_documents_match(weight=5)
criteria.rejects_extract_summary_document_matches(weight=3)
criteria.rejects_extract_policy_audit_document_matches(weight=3)
criteria.rejects_extract_data_quality_document_matches(weight=3)
criteria.mixed_extract_region_documents_match(weight=5)
criteria.mixed_extract_segment_documents_match(weight=5)
criteria.mixed_extract_summary_document_matches(weight=3)
criteria.mixed_extract_policy_audit_document_matches(weight=3)
criteria.mixed_extract_data_quality_document_matches(weight=3)
criteria.rate_composition_case(weight=3)
criteria.interval_credit_rounding_case(weight=3)
criteria.allowance_order_case(weight=3)
criteria.allowance_consumption_case(weight=3)
criteria.segment_rate_adder_mutation(weight=3)
criteria.allowance_ticks_mutation(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_reads_tests_or_reward_files(weight=-5)
criteria.negative_external_dependency_or_network(weight=-3)
