"""Verifier for district-heat-flex-procurement.

Visible checks compare the agent's /app/out reports with an independent reference
derived from an embedded copy of the shipped extract. Hidden checks build small
extracts here, run the agent's derive_report.py on them as an unprivileged user,
and compare against the same reference. Each hand-built case targets one contract
rule, and the check first confirms that the lazy reading of that rule would give a
different answer, so the case really separates the two readings.

Negative checks return True when the cheat is present; their negative weight does
the punishing, so an honest submission leaves them False.
"""

from __future__ import annotations

import ast
import base64
import configparser
import csv
import io
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
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
ALL_LAZY = frozenset({"H1", "H1order", "H2", "H3", "H4", "H5t", "H5c"})
_SETPRIV = ["setpriv", "--reuid=nobody", "--regid=nogroup", "--clear-groups"]
_AGENT_TIMEOUT = 240

_SHIPPED_DATA: dict[str, str] = {}

_LOCK = threading.RLock()
_CACHE: dict[Any, Any] = {}


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

    site_rows = _records(root / "sites.csv", ",")
    count["sites.csv"] = len(site_rows)
    site: dict[tuple[str, str], dict[str, Any]] = {}
    for r in site_rows:
        site[(r["event_id"], r["site_id"])] = {
            "event_id": r["event_id"], "sid": r["site_id"], "region": code_region[r["region_code"].upper()],
            "segment": code_segment[r["segment_code"].upper()], "ben": r["beneficiary_id"],
            "critical": r["critical"] == "Y", "weight": None,
        }
    states = [json.loads(x) for x in (root / "site_state.jsonl").read_text(encoding="utf-8").split("\n") if x.strip()]
    count["site_state.jsonl"] = len(states)
    for s in states:
        site[(s["event_id"], s["site_id"])].update(auth=bool(s["dispatch_authorized"]), hold=bool(s["safety_hold"]),
                                                   cool=bool(s["cooldown"]))
    waiver_rows = _records(root / "continuity_waivers.csv", ",")
    count["continuity_waivers.csv"] = len(waiver_rows)
    blank_signed = 0
    for w in waiver_rows:
        signed = (w["waiver_signed"] or "").strip()
        blank_signed += not signed
        site[(w["event_id"], w["site_id"])].update(pending=w["routine_certificate_pending"] == "Y",
                                                   status=w["waiver_status"], signed=signed)
    card_nodes = list(ElementTree.fromstring((root / "rate_cards.xml").read_text(encoding="utf-8")).iter("card"))
    count["rate_cards.xml"] = len(card_nodes)
    for node in card_nodes:
        site[(node.attrib["event"], node.attrib["site"])].update(base=int(node.find("base").text),
                                                                 cap=int(node.find("cap").text))
    weight_rows = _records(root / "recipient_weights.tsv", "\t")
    count["recipient_weights.tsv"] = len(weight_rows)
    for w in weight_rows:
        site[(w["event_id"], w["site_id"])]["weight"] = int(w["grant_weight"])

    span = {e["event_id"]: int(e["interval_count"]) for e in event_list}
    offer_rows = _records(root / "offers.csv", ",")
    count["offers.csv"] = len(offer_rows)
    listed = {r["offer_id"] for r in offer_rows}
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
    lost_profiles = 0
    for r in profile_rows:
        if r["offer_id"] not in listed:
            lost_profiles += 1
        elif r["offer_id"] in offer:
            slot = int(r["interval"]) - 1
            offer[r["offer_id"]]["r"][slot] = int(r["relief_wh"])
            offer[r["offer_id"]]["v"][slot] = int(r["recovery_wh"])

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
        valid = s["status"] == "VALID" and s["signed"] == "Y" and s["critical"] and s["segment"] == "public"
        if "H1" in lazy:
            valid = False
        waived = s["pending"] and valid
        if "H1order" in lazy and waived:
            return "CONTINUITY_WAIVED"
        if s["hold"]:
            return "SAFETY_HOLD"
        if s["cool"]:
            return "COOLDOWN"
        if waived:
            return "CONTINUITY_WAIVED"
        return "CERTIFICATE_PENDING" if s["pending"] else "CLEAR"

    def energy(parts: list[int]) -> int:
        # parts are raw Wh values; each becomes ticks before summing unless H5t is lazy
        return tk(sum(parts)) if "H5t" in lazy else sum(tk(p) for p in parts)

    def rate(s: dict[str, Any], uplift: int) -> int:
        if "H3" in lazy:
            return min(s["base"], s["cap"]) + uplift
        return min(s["base"] + uplift, s["cap"])

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
            grouped: dict[str, list[dict[str, Any]]] = {}
            for o in cands:
                grouped.setdefault(o["site"]["sid"], []).append(o)
            lanes = [[None] + grouped[k] for k in sorted(grouped)]
            frontier: list[tuple[str, ...]] = []
            best = None
            stack: list[tuple[int, list[dict[str, Any]]]] = [(0, [])]
            while stack:
                depth, taken = stack.pop()
                if depth < len(lanes):
                    for o in lanes[depth]:
                        stack.append((depth + 1, taken if o is None else taken + [o]))
                    continue
                rel = [energy([o["r"][t] for o in taken]) for t in range(width)]
                rec = [energy([o["v"][t] for o in taken]) for t in range(width)]
                if any(rel[t] > caps[t][0] or rec[t] > caps[t][1] for t in range(width)):
                    continue
                score = (
                    sum(goals[t][1] * max(0, goals[t][0] - rel[t]) for t in range(width)),
                    sum(pw * max(0, fl - energy([x for o in taken if o["site"]["segment"] == g for x in o["r"]]))
                        for g, (fl, pw) in floors_here.items()),
                    cw * sum(o["cost"] for o in taken) + vw * sum(rec),
                    sum(max(0, rel[t] - goals[t][0]) for t in range(width)),
                    len(taken),
                )
                label_ids = tuple(sorted(o["id"] for o in taken))
                if best is None or score < best:
                    best, frontier = score, [label_ids]
                elif score == best:
                    frontier.append(label_ids)
            winner = min(frontier) if "H2" in lazy else max(frontier)
            picked = [offer[i] for i in winner]
            if len(frontier) > 1:
                tie_log.append({"event_id": eid, "region": region, "tied_portfolio_count": len(frontier),
                                "selected_offer_ids": list(winner)})
            numer = {}
            for o in picked:
                numer[o["id"]] = energy(o["r"]) * wh_tick * rate(o["site"], uplift) if "H5t" not in lazy \
                    else sum(o["r"]) * rate(o["site"], uplift)
                capped += o["site"]["base"] + uplift > o["site"]["cap"]
            den = 1000 * mc_cent

            def money(ids: list[str]) -> int:
                if "H5c" in lazy:
                    return _q(sum(numer[i] for i in ids), den)
                return sum(_q(numer[i], den) for i in ids)

            rows = []
            for t in range(width):
                rel_t = energy([o["r"][t] for o in picked])
                rows.append({"interval": t + 1, "target_ticks": goals[t][0], "relief_ticks": rel_t,
                             "recovery_ticks": energy([o["v"][t] for o in picked]),
                             "shortfall_ticks": max(0, goals[t][0] - rel_t),
                             "overdelivery_ticks": max(0, rel_t - goals[t][0])})
            # grants
            money_pool = pool.get((eid, region), 0)
            members = [s for s in sites_of.get((eid, region), []) if s["weight"] is not None]
            heft: dict[str, int] = {}
            for s in members:
                heft[s["ben"]] = heft.get(s["ben"], 0) + s["weight"]
            total_w = sum(heft.values())
            grant_rows: list[dict[str, Any]] = []
            if not members or total_w == 0:
                dead_pools += 1
            else:
                base_cut = {b: money_pool * w // total_w for b, w in heft.items() if w}
                remain = {b: money_pool * w % total_w for b, w in heft.items() if w}
                spare = money_pool - sum(base_cut.values())
                residual_sum += spare
                if "H4" in lazy:
                    queue = sorted(base_cut, key=lambda b: (-remain[b], b))
                else:
                    queue = sorted(base_cut, key=lambda b: (remain[b], b), reverse=True)
                for b in queue[:spare]:
                    base_cut[b] += 1
                filled = [r for r in remain.values() if r]
                residual_ties += len(filled) > len(set(filled))
                grant_rows = [{"beneficiary_id": b, "cents": base_cut[b]} for b in sorted(base_cut)]
            given = sum(g["cents"] for g in grant_rows)
            tally = {name: 0 for name in RANKING}
            for s in sites_of.get((eid, region), []):
                tally[label(s)] += 1
            ids = list(winner)
            per_region[region].append({
                "event_id": eid, "candidate_offer_count": len(cands), "selected_offer_ids": ids,
                "intervals": rows, "bid_cost_cents": sum(o["cost"] for o in picked), "credit_cents": money(ids),
                "grant_pool_cents": money_pool, "grant_allocated_cents": given,
                "grant_unallocated_cents": money_pool - given, "grants": grant_rows, "compliance_counts": tally,
            })
            for g in segment_names:
                part = [o for o in picked if o["site"]["segment"] == g]
                fl = floors_here[g][0]
                zero_floor += fl == 0
                got = energy([x for o in part for x in o["r"]])
                per_segment[g].append({
                    "event_id": eid, "region": region, "selected_offer_ids": [o["id"] for o in part],
                    "relief_ticks": got, "recovery_ticks": energy([x for o in part for x in o["v"]]),
                    "bid_cost_cents": sum(o["cost"] for o in part), "credit_cents": money([o["id"] for o in part]),
                    "floor_ticks": fl, "floor_attainment_bp": 10000 if fl == 0 else min(10000, _q(10000 * got, fl)),
                })

    result: dict[str, Any] = {}
    keys_total = ["candidate_offer_count", "selected_offer_count", "relief_ticks", "recovery_ticks",
                  "shortfall_ticks", "overdelivery_ticks", "bid_cost_cents", "credit_cents", "grant_pool_cents",
                  "grant_allocated_cents", "grant_unallocated_cents"]
    rtot: dict[str, dict[str, int]] = {}
    for region, evs in per_region.items():
        acc = dict.fromkeys(keys_total, 0)
        for e in evs:
            acc["candidate_offer_count"] += e["candidate_offer_count"]
            acc["selected_offer_count"] += len(e["selected_offer_ids"])
            for row in e["intervals"]:
                for k in ("relief_ticks", "recovery_ticks", "shortfall_ticks", "overdelivery_ticks"):
                    acc[k] += row[k]
            for k in ("bid_cost_cents", "credit_cents", "grant_pool_cents", "grant_allocated_cents",
                      "grant_unallocated_cents"):
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
        "waiver_signed_missing": blank_signed, "ineligible_offer_count": unauth,
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


def case_spec(name: str) -> dict[str, Any]:
    """The hand-built extracts, one rule each."""
    if name == "waiver":
        e = "T1-0001"
        sites = [_site(e, "S-WAIVE", seg="P", critical=True, pending=True, status="VALID", signed="Y"),
                 _site(e, "S-PLAIN")]
        return {"events": [_event(e, 2)], "sites": sites, "offers": [], "targets": {}, "limits": {}}
    if name == "waiver_ranked":
        e = "T1-0002"
        eligible = {"seg": "P", "critical": True, "pending": True, "status": "VALID", "signed": "Y"}
        sites = [_site(e, "S-HOLD", hold=True, **eligible), _site(e, "S-COOL", cool=True, **eligible),
                 _site(e, "S-WAIVED", **eligible),
                 _site(e, "S-UNSIGNED", **{**eligible, "signed": ""}),
                 _site(e, "S-COMMERCIAL", **{**eligible, "seg": "C"}),
                 _site(e, "S-ROUTINE", **{**eligible, "critical": False}),
                 _site(e, "S-EXPIRED", **{**eligible, "status": "EXPIRED"})]
        return {"events": [_event(e, 2)], "sites": sites, "offers": [], "targets": {}, "limits": {}}
    if name in ("tie", "tie_reversed"):
        e, low, high = ("T2-0001", "A", "Z") if name == "tie" else ("T2-0002", "B", "Y")
        sites = [_site(e, "S1"), _site(e, "S2")]
        offers = [_offer(e, "S1", low, 700, [3000, 0]), _offer(e, "S1", high, 700, [3000, 0]),
                  _offer(e, "S2", "M", 500, [0, 2000])]
        return {"events": [_event(e, 2)], "sites": sites, "offers": offers, "reverse": name == "tie_reversed",
                "targets": {(e, "North"): [(3000, 2), (2000, 2)]}, "limits": {(e, "North"): _wide(2)}}
    if name in ("cap", "cap_low"):
        e, base, cap, uplift, wh = ("T3-0001", 850, 1000, 250, 5000) if name == "cap" else ("T3-0002", 1200, 1000, 100, 7000)
        return {"events": [_event(e, 1, uplift=uplift)], "sites": [_site(e, "S1", base=base, cap=cap)],
                "offers": [_offer(e, "S1", "A", 100, [wh])], "targets": {(e, "North"): [(wh, 1)]},
                "limits": {(e, "North"): _wide(1)}}
    if name in ("residual", "residual_mixed"):
        e, cents, weights = ("T4-0001", 5, (1, 1, 1)) if name == "residual" else ("T4-0002", 9, (3, 2, 2))
        sites = [_site(e, f"S{i}", ben=ben, weight=w) for i, (ben, w) in
                 enumerate(zip(("BEN-ALPHA", "BEN-MU", "BEN-ZULU"), weights), 1)]
        return {"events": [_event(e, 1)], "sites": sites, "offers": [], "targets": {}, "limits": {},
                "pools": {(e, "North"): cents}}
    if name == "ticks":
        e = "T5-0001"
        sites = [_site(e, "S1"), _site(e, "S2")]
        offers = [_offer(e, "S1", "A", 10, [5]), _offer(e, "S2", "A", 10, [15])]
        return {"events": [_event(e, 1)], "sites": sites, "offers": offers,
                "targets": {(e, "North"): [(1000, 3)]}, "limits": {(e, "North"): _wide(1)}}
    if name == "site_cents":
        e = "T5-0002"
        sites = [_site(e, "S1", base=1000, cap=2000), _site(e, "S2", base=1000, cap=2000)]
        offers = [_offer(e, "S1", "A", 10, [500]), _offer(e, "S2", "A", 10, [500])]
        return {"events": [_event(e, 1)], "sites": sites, "offers": offers,
                "targets": {(e, "North"): [(2000, 2)]}, "limits": {(e, "North"): _wide(1)}}
    raise KeyError(name)


def _ordinary_spec(seed: int) -> dict[str, Any]:
    """A seeded extract that exercises the general rules and none of the hand-built cases."""
    rng = Rng(seed)
    spec: dict[str, Any] = {"events": [], "sites": [], "offers": [], "targets": {}, "limits": {}, "floors": [],
                            "pools": {}, "orphan_offer_rows": [], "orphan_profile_rows": []}
    for k in range(16):
        eid = f"Q{seed % 89:02d}-{100 + 37 * k:04d}"
        n = rng.between(3, 7)
        zero = rng.chance(15)
        spec["events"].append(_event(eid, n, 0 if zero else rng.between(1, 3), 0 if zero else rng.between(0, 2),
                                     rng.between(0, 3) * 1000))
        for region in REGION_CODES:
            count = 0 if rng.chance(8) else rng.between(1, 4)
            local = []
            used_weights: set[int] = set()
            for i in range(count):
                sid = f"QS{region[0]}{rng.between(1000, 9999)}{i}"
                weight = None if rng.chance(10) else rng.between(0, 6)
                while weight in used_weights:
                    weight = rng.between(1, 9)
                if weight:
                    used_weights.add(weight)
                pending = rng.chance(25)
                status = rng.pick(["VALID", "EXPIRED", "NONE", "REVOKED"])
                signed = rng.pick(["Y", "N", ""])
                if pending and status == "VALID" and signed == "Y":
                    signed = "N"
                base = rng.between(3, 9) * 1000
                row = _site(eid, sid, code=rng.pick(REGION_CODES[region]), seg=rng.pick(["C", "P"]),
                            ben=f"BEN-{rng.between(10, 40)}", critical=rng.chance(30), auth=not rng.chance(12),
                            hold=rng.chance(10), cool=rng.chance(10), pending=pending, status=status,
                            signed=signed, base=base, cap=base + spec["events"][-1]["uplift"] + rng.between(0, 3) * 1000,
                            weight=weight)
                local.append(row)
                for letter in "ABC"[:rng.between(1, 3)]:
                    relief = [rng.between(0, 30) * 1000 if rng.chance(60) else 0 for _ in range(n)]
                    recovery = [rng.between(0, 20) * 1000 if rng.chance(40) else 0 for _ in range(n)]
                    spec["offers"].append(_offer(eid, sid, letter, rng.between(300, 20000), relief, recovery))
            spec["sites"].extend(local)
            spec["targets"][(eid, region)] = [(rng.between(0, 40) * 1000, rng.between(1, 5)) for _ in range(n)]
            spec["limits"][(eid, region)] = [(rng.between(10, 70) * 1000, rng.between(5, 50) * 1000) for _ in range(n)]
            for g in ("C", "P"):
                if rng.chance(80):
                    spec["floors"].append((eid, region, g, rng.between(0, 60) * 1000, rng.between(1, 4)))
            if rng.chance(90):
                heft: dict[str, int] = {}
                for s in local:
                    if s["weight"] is not None:
                        heft[s["ben"]] = heft.get(s["ben"], 0) + s["weight"]
                total = sum(heft.values())
                for _ in range(60):
                    cents = rng.between(100, 90000)
                    rems = [cents * w % total for w in heft.values() if total and cents * w % total]
                    if len(rems) == len(set(rems)):
                        break
                spec["pools"][(eid, region)] = cents
    first = spec["sites"][0]
    spec["orphan_offer_rows"] = [[f"{first['event_id']}-QX0000-A", first["event_id"], "QX0000", "SETBACK_4C", 900]]
    spec["orphan_profile_rows"] = [["Q00-0000-QX0000-Z", 1, 4000, 0], ["Q00-0000-QX0000-Z", 2, 0, 1000]]
    return spec


def ordinary_root() -> Path | None:
    """First seed from EVAL_SEED whose extract triggers no hand-built rule (every lazy reading agrees)."""
    with _LOCK:
        if ("ordinary",) not in _CACHE:
            found = None
            for step in range(40):
                folder = write_extract(_scratch() / f"ordinary-{step}", _ordinary_spec(EVAL_SEED + step))
                if expected(folder) == expected(folder, ALL_LAZY):
                    found = folder
                    break
            _CACHE[("ordinary",)] = found
        return _CACHE[("ordinary",)]


def case_root(name: str) -> Path:
    with _LOCK:
        key = ("case", name)
        if key not in _CACHE:
            _CACHE[key] = write_extract(_scratch() / f"case-{name}", case_spec(name))
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


def run_agent(workspace: Path, data: Path | None) -> Path | None:
    """Run the submitted program on one extract; returns its output folder, or None on any failure."""
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
            out = box / "out"
            proc = subprocess.Popen(_untrusted([sys.executable, str(script), str(data), str(out)]),
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
            if code == 0 and out.is_dir():
                result = out
        _CACHE[key] = result
        return result


def produced(folder: Path | None, name: str) -> Any:
    if folder is None:
        return None
    try:
        return json.loads((folder / name).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def mine(workspace: Path, name: str) -> Any:
    return produced(Path(workspace) / "out", name)


# ---------------------------------------------------------------- projections

def region_view(doc: Any, fields: tuple[str, ...]) -> Any:
    if not isinstance(doc, dict) or not isinstance(doc.get("events"), list):
        return None
    view = []
    for entry in doc["events"]:
        if not isinstance(entry, dict):
            return None
        view.append(tuple(json.dumps(entry.get(f), sort_keys=True) for f in ("event_id", *fields)))
    return view


def regions_match(got_dir: Path | None, want: dict[str, Any], fields: tuple[str, ...], regions=REGION_CODES) -> bool:
    for region in regions:
        name = f"region_{region}.json"
        if region_view(produced(got_dir, name), fields) != region_view(want[name], fields):
            return False
    return True


def site_label(doc: Any, sid: str) -> Any:
    if not isinstance(doc, dict) or not isinstance(doc.get("site_labels"), list):
        return None
    hits = [x.get("label") for x in doc["site_labels"] if isinstance(x, dict) and x.get("site_id") == sid]
    return hits[0] if len(hits) == 1 else None


def north_first(doc: Any, field: str) -> Any:
    try:
        return doc["events"][0][field]
    except (KeyError, IndexError, TypeError):
        return None


def separated(name: str, rule: str, observe) -> bool:
    """True when the case's observable differs between the contract and the lazy reading."""
    root = case_root(name)
    return observe(expected(root)) != observe(expected(root, frozenset({rule})))


def case_passes(workspace: Path, name: str, rule: str, observe) -> bool:
    if not separated(name, rule, observe):
        return False
    root = case_root(name)
    got = run_agent(workspace, root)
    if got is None:
        return False
    files = {n: produced(got, n) for n in ARTIFACT_JSON}
    return observe(files) == observe(expected(root))


# ---------------------------------------------------------------- visible checks

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


@criterion(description="All ten declared artifacts exist and the nine JSON reports parse as objects.")
def artifact_set_exists_and_parses(workspace: Path) -> bool:
    try:
        out = Path(workspace) / "out"
        if not (out / "derive_report.py").is_file():
            return False
        return all(isinstance(produced(out, n), dict) for n in ARTIFACT_JSON)
    except Exception:
        return False


@criterion(description="Every JSON report has sorted keys at every level, a trailing newline and integers only.")
def canonical_serialization_and_integer_units(workspace: Path) -> bool:
    try:
        for name in ARTIFACT_JSON:
            text = (Path(workspace) / "out" / name).read_text(encoding="utf-8")
            if not text.endswith("\n") or _has_bool(_strict_load(text)):
                return False
        return True
    except Exception:
        return False


def _visible_region(workspace: Path, region: str, fields: tuple[str, ...]) -> bool:
    want = expected(visible_root())
    return regions_match(Path(workspace) / "out", want, fields, regions=(region,))


@criterion(description="region_North.json lists the candidate count and the chosen portfolio of every event.")
def region_north_selected_offers_match(workspace: Path) -> bool:
    try:
        return _visible_region(workspace, "North", ("candidate_offer_count", "selected_offer_ids"))
    except Exception:
        return False


@criterion(description="region_South.json lists the candidate count and the chosen portfolio of every event.")
def region_south_selected_offers_match(workspace: Path) -> bool:
    try:
        return _visible_region(workspace, "South", ("candidate_offer_count", "selected_offer_ids"))
    except Exception:
        return False


@criterion(description="region_West.json lists the candidate count and the chosen portfolio of every event.")
def region_west_selected_offers_match(workspace: Path) -> bool:
    try:
        return _visible_region(workspace, "West", ("candidate_offer_count", "selected_offer_ids"))
    except Exception:
        return False


@criterion(description="region_East.json lists the candidate count and the chosen portfolio of every event.")
def region_east_selected_offers_match(workspace: Path) -> bool:
    try:
        return _visible_region(workspace, "East", ("candidate_offer_count", "selected_offer_ids"))
    except Exception:
        return False


@criterion(description="The per-interval target, relief, recovery, shortfall and overdelivery ticks match in all four region files.")
def region_interval_quantities_match(workspace: Path) -> bool:
    try:
        return regions_match(Path(workspace) / "out", expected(visible_root()), ("intervals",))
    except Exception:
        return False


@criterion(description="Per-event bid cost and performance credit, and each region totals block, match the shipped extract.")
def procurement_cost_and_credit_totals_match(workspace: Path) -> bool:
    try:
        want = expected(visible_root())
        out = Path(workspace) / "out"
        if not regions_match(out, want, ("bid_cost_cents", "credit_cents")):
            return False
        return all((produced(out, f"region_{r}.json") or {}).get("totals") == want[f"region_{r}.json"]["totals"]
                   for r in REGION_CODES)
    except Exception:
        return False


@criterion(description="Per-event grant pool, allocated, unallocated and beneficiary cents match in the region files.")
def region_grant_allocations_match(workspace: Path) -> bool:
    try:
        return regions_match(Path(workspace) / "out", expected(visible_root()),
                             ("grant_pool_cents", "grant_allocated_cents", "grant_unallocated_cents", "grants"))
    except Exception:
        return False


@criterion(description="segment_commercial.json matches the shipped extract.")
def segment_commercial_attribution_match(workspace: Path) -> bool:
    try:
        return mine(workspace, "segment_commercial.json") == expected(visible_root())["segment_commercial.json"]
    except Exception:
        return False


@criterion(description="segment_public.json matches the shipped extract.")
def segment_public_attribution_match(workspace: Path) -> bool:
    try:
        return mine(workspace, "segment_public.json") == expected(visible_root())["segment_public.json"]
    except Exception:
        return False


@criterion(description="summary.json global totals and region and segment rollups match the shipped extract.")
def summary_rollups_match(workspace: Path) -> bool:
    try:
        return mine(workspace, "summary.json") == expected(visible_root())["summary.json"]
    except Exception:
        return False


@criterion(description="data_quality.json row counts, orphan counts and zero-denominator counts match the shipped extract.")
def data_quality_counts_match(workspace: Path) -> bool:
    try:
        return mine(workspace, "data_quality.json") == expected(visible_root())["data_quality.json"]
    except Exception:
        return False


@criterion(description="policy_audit.json and the per-event compliance counts in the region files match the shipped extract.")
def policy_audit_labels_match(workspace: Path) -> bool:
    try:
        want = expected(visible_root())
        if mine(workspace, "policy_audit.json") != want["policy_audit.json"]:
            return False
        return regions_match(Path(workspace) / "out", want, ("compliance_counts",))
    except Exception:
        return False


# ---------------------------------------------------------------- hidden checks

@criterion(description="On a fresh seeded extract the program picks the same portfolios and interval quantities.")
def hidden_ordinary_extract_portfolios_match(workspace: Path) -> bool:
    try:
        root = ordinary_root()
        got = run_agent(workspace, root)
        if root is None or got is None:
            return False
        return regions_match(got, expected(root), ("candidate_offer_count", "selected_offer_ids", "intervals"))
    except Exception:
        return False


@criterion(description="On a fresh seeded extract the program reports the same bid costs, credits and grants.")
def hidden_ordinary_extract_settlement_match(workspace: Path) -> bool:
    try:
        root = ordinary_root()
        got = run_agent(workspace, root)
        if root is None or got is None:
            return False
        return regions_match(got, expected(root), ("bid_cost_cents", "credit_cents", "grant_pool_cents",
                                                   "grant_allocated_cents", "grant_unallocated_cents", "grants"))
    except Exception:
        return False


@criterion(description="A critical public site with a pending certificate and a valid signed waiver is labelled CONTINUITY_WAIVED.")
def waiver_precedence_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "waiver", "H1",
                           lambda f: site_label(f["policy_audit.json"], "S-WAIVE"))
    except Exception:
        return False


@criterion(description="Hold and cooldown outrank a valid waiver, the waiver outranks a pending certificate, and a waiver missing one condition leaves CERTIFICATE_PENDING.")
def safety_hold_over_waiver_case(workspace: Path) -> bool:
    try:
        names = ("S-HOLD", "S-COOL", "S-WAIVED", "S-UNSIGNED", "S-COMMERCIAL", "S-ROUTINE", "S-EXPIRED")
        return case_passes(workspace, "waiver_ranked", "H1order",
                           lambda f: tuple(site_label(f["policy_audit.json"], n) for n in names))
    except Exception:
        return False


@criterion(description="Two portfolios equal on every component resolve to the greatest sorted offer-id tuple.")
def tie_break_greatest_tuple_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "tie", "H2",
                           lambda f: north_first(f["region_North.json"], "selected_offer_ids"))
    except Exception:
        return False


@criterion(description="The same tie resolves the same way when the offer and profile rows arrive in reverse order.")
def tie_break_reversed_input_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "tie_reversed", "H2",
                           lambda f: north_first(f["region_North.json"], "selected_offer_ids"))
    except Exception:
        return False


@criterion(description="The rate cap binds the base rate plus the event uplift.")
def cap_after_uplift_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "cap", "H3", lambda f: north_first(f["region_North.json"], "credit_cents"))
    except Exception:
        return False


@criterion(description="A base rate already above its cap still settles at the cap after the uplift.")
def cap_with_base_above_cap_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "cap_low", "H3", lambda f: north_first(f["region_North.json"], "credit_cents"))
    except Exception:
        return False


@criterion(description="Leftover grant cents with equal remainders go to beneficiaries in descending id order.")
def residual_ties_descending_id_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "residual", "H4", lambda f: north_first(f["region_North.json"], "grants"))
    except Exception:
        return False


@criterion(description="Leftover grant cents follow the largest remainder first and then descending id among equals.")
def residual_ties_mixed_weights_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "residual_mixed", "H4", lambda f: north_first(f["region_North.json"], "grants"))
    except Exception:
        return False


@criterion(description="Each Wh value becomes ticks before interval relief is summed.")
def per_value_tick_quantisation_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "ticks", "H5t",
                           lambda f: (north_first(f["region_North.json"], "intervals") or [{}])[0].get("relief_ticks"))
    except Exception:
        return False


@criterion(description="Each site credit is rounded to whole cents before the event-region credit is summed.")
def per_site_credit_rounding_case(workspace: Path) -> bool:
    try:
        return case_passes(workspace, "site_cents", "H5c", lambda f: north_first(f["region_North.json"], "credit_cents"))
    except Exception:
        return False


# ---------------------------------------------------------------- negative checks

def _program_source(workspace: Path) -> str | None:
    try:
        return (Path(workspace) / "out" / "derive_report.py").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


@criterion(description="Run on a different extract, the program emits the summary of the shipped extract.")
def negative_hardcoded_sample_answers(workspace: Path) -> bool:
    # True means the cheat happened: output tied to the shipped data, not to DATA_DIR.
    try:
        root = ordinary_root()
        got = run_agent(workspace, root)
        if root is None or got is None:
            return False
        shipped = expected(visible_root())["summary.json"]
        return produced(got, "summary.json") == shipped and expected(root)["summary.json"] != shipped
    except Exception:
        return False


@criterion(description="The delivered program names a grader path or grader file in its source.")
def negative_reads_tests_or_reward_files(workspace: Path) -> bool:
    # True means the cheat happened: the program points at the grading machinery.
    try:
        source = _program_source(workspace)
        if source is None:
            return False
        lowered = source.lower()
        return any(token in lowered for token in ("/tests", "/logs/", "test_output", "judge.toml",
                                                  "reward.toml", "rewardkit"))
    except Exception:
        return False


@criterion(description="The delivered program imports a third-party or network module.")
def negative_external_dependency_or_network(workspace: Path) -> bool:
    # True means the cheat happened: a non-stdlib or network import in the program.
    try:
        source = _program_source(workspace)
        if source is None:
            return False
        tree = ast.parse(source)
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
criteria.region_north_selected_offers_match(weight=5)
criteria.region_south_selected_offers_match(weight=5)
criteria.region_west_selected_offers_match(weight=5)
criteria.region_east_selected_offers_match(weight=5)
criteria.region_interval_quantities_match(weight=5)
criteria.procurement_cost_and_credit_totals_match(weight=5)
criteria.region_grant_allocations_match(weight=3)
criteria.segment_commercial_attribution_match(weight=3)
criteria.segment_public_attribution_match(weight=3)
criteria.summary_rollups_match(weight=3)
criteria.data_quality_counts_match(weight=3)
criteria.policy_audit_labels_match(weight=3)
criteria.hidden_ordinary_extract_portfolios_match(weight=5)
criteria.hidden_ordinary_extract_settlement_match(weight=3)
criteria.waiver_precedence_case(weight=5)
criteria.safety_hold_over_waiver_case(weight=3)
criteria.tie_break_greatest_tuple_case(weight=5)
criteria.tie_break_reversed_input_case(weight=3)
criteria.cap_after_uplift_case(weight=5)
criteria.cap_with_base_above_cap_case(weight=3)
criteria.residual_ties_descending_id_case(weight=5)
criteria.residual_ties_mixed_weights_case(weight=3)
criteria.per_value_tick_quantisation_case(weight=5)
criteria.per_site_credit_rounding_case(weight=3)
criteria.negative_hardcoded_sample_answers(weight=-5)
criteria.negative_reads_tests_or_reward_files(weight=-5)
criteria.negative_external_dependency_or_network(weight=-3)
criteria.negative_missing_substantive_sections(weight=-3)
