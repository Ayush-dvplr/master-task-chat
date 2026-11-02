"""Seeded data generator for district-heat-flex-procurement (scratch, never shipped).

Usage: python3 datagen.py OUT_DIR [--seed 731904]

Writes every input file except schema.md. Stdlib only, deterministic from the seed.
The generator also enforces the neutrality rules from DESIGN.md section 3 with its own
small evaluator, so the shipped data never exercises a hard rule (H1..H5):
  - no waiver row has a pending certificate together with a VALID, signed waiver
  - every event-region has a unique best portfolio on the objective components 1..5
  - base + uplift <= cap on every rate card
  - every grant pool has pairwise distinct non-zero remainders
  - every Wh value is a multiple of 1000, every rate a multiple of 1000 mill-cents,
    so tick and cent rounding never has a fraction to round
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from pathlib import Path
from xml.sax.saxutils import quoteattr

REGIONS = ["North", "South", "West", "East"]
REGION_CODES = {"North": ["N1", "N2"], "South": ["S1", "S2"], "West": ["W1", "W2"], "East": ["E1", "E2"]}
SEGMENTS = {"C": "commercial", "P": "public"}
MODES = ["SETBACK_2C", "SETBACK_4C", "BOILER_BRIDGE", "STORE_PRECHARGE", "HP_STAGE_DOWN", "DHW_DEFER"]
INTERVALS = 6
EVENTS = 500
SITES_PER_ER = 5
OFFERS_PER_ER = 9
WH_PER_TICK = 10


def ticks(wh: int) -> int:
    return (wh + WH_PER_TICK // 2) // WH_PER_TICK


class Builder:
    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.stats = {"pair_swaps": [0, 0, 0, 0], "rerolls": 0, "pool_rerolls": 0}

    # ---------- reference tables ----------
    def buildings(self) -> None:
        rng = self.rng
        used: set[str] = set()
        self.beneficiaries = sorted({f"BEN-{rng.randrange(10000, 99999)}" for _ in range(330)})
        self.by_region: dict[str, list[dict]] = {r: [] for r in REGIONS}
        for region in REGIONS:
            while len(self.by_region[region]) < 320:
                sid = f"HX{rng.randrange(10000, 99999)}"
                if sid in used:
                    continue
                used.add(sid)
                seg = rng.choices(["C", "P"], weights=[3, 2])[0]
                self.by_region[region].append({
                    "site_id": sid,
                    "segment": seg,
                    "critical": "Y" if rng.random() < (0.35 if seg == "P" else 0.08) else "N",
                    "beneficiary": rng.choice(self.beneficiaries),
                })

    def events(self) -> None:
        rng = self.rng
        numbers = sorted(rng.sample(range(1, 10000), EVENTS))
        self.event_rows = []
        for n in numbers:
            zero = rng.random() < 0.12
            self.event_rows.append({
                "event_id": f"W26-{n:04d}",
                "name": rng.choice(["cold snap", "wind drop", "plant trip", "peak warning", "frost alert"]),
                "interval_count": INTERVALS,
                "objective": {"cost_weight": 0 if zero else rng.choice([1, 1, 2, 3]),
                              "recovery_weight": 0 if zero else rng.choice([0, 1, 1, 2])},
                "uplift_millicents_per_kwh": rng.choice([1000, 1000, 2000, 3000]),
            })

    # ---------- one event-region ----------
    def compose_modes(self) -> list[int]:
        while True:
            parts = [self.rng.randint(1, 3) for _ in range(SITES_PER_ER)]
            if sum(parts) == OFFERS_PER_ER:
                return parts

    def make_er(self, event: dict, region: str) -> dict:
        rng = self.rng
        sites = rng.sample(self.by_region[region], SITES_PER_ER)
        site_rows, offers, states, waivers = [], [], [], []
        for site, n_modes in zip(sites, self.compose_modes()):
            site_rows.append({**site, "code": rng.choice(REGION_CODES[region])})
            letters = sorted(rng.sample("ABCDEFGHJKLMNPRSTUVWYZ", n_modes))
            start = rng.randint(1, 3)
            for letter in letters:
                relief = [0] * INTERVALS
                recovery = [0] * INTERVALS
                length = rng.randint(2, 3)
                for t in range(start - 1, min(INTERVALS, start - 1 + length)):
                    relief[t] = rng.randint(4, 40) * 1000
                for t in range(min(INTERVALS, start - 1 + length), INTERVALS):
                    if rng.random() < 0.7:
                        recovery[t] = rng.randint(2, 30) * 1000
                offers.append({
                    "offer_id": f"{event['event_id']}-{site['site_id']}-{letter}",
                    "site_id": site["site_id"],
                    "mode": rng.choice(MODES),
                    "cost": rng.randint(400, 26000),
                    "relief": relief,
                    "recovery": recovery,
                })
            authorized = rng.random() >= 0.08
            states.append({"site_id": site["site_id"], "dispatch_authorized": authorized,
                           "safety_hold": rng.random() < 0.05, "cooldown": rng.random() < 0.07})
            waivers.append(self.waiver_row())
        max_relief = [sum(o["relief"][t] for o in offers) // 2 for t in range(INTERVALS)]
        max_recovery = [sum(o["recovery"][t] for o in offers) // 2 for t in range(INTERVALS)]
        relief_only = event["objective"]["cost_weight"] == 0
        low, high = (5, 30) if relief_only else (20, 75)
        targets = [rng.randint(low, high) * max_relief[t] // 100 // 1000 * 1000 for t in range(INTERVALS)]
        weights = [rng.randint(1, 5) for _ in range(INTERVALS)]
        relief_ceiling = [max(1000, rng.randint(55, 110) * max_relief[t] // 100 // 1000 * 1000) for t in range(INTERVALS)]
        recovery_ceiling = [max(1000, rng.randint(50, 120) * max_recovery[t] // 100 // 1000 * 1000) for t in range(INTERVALS)]
        floors = {}
        for seg in ("C", "P"):
            seg_sites = {s["site_id"] for s in site_rows if s["segment"] == seg}
            total = sum(sum(o["relief"]) for o in offers if o["site_id"] in seg_sites)
            if relief_only or rng.random() < 0.1 or total == 0:
                floor = 0
            else:
                floor = rng.randint(5, 45) * total // 100 // 1000 * 1000
            floors[seg] = (floor, rng.randint(1, 4))
        return {"sites": site_rows, "offers": offers, "states": states, "waivers": waivers,
                "targets": targets, "weights": weights, "relief_ceiling": relief_ceiling,
                "recovery_ceiling": recovery_ceiling, "floors": floors}

    def waiver_row(self) -> dict:
        rng = self.rng
        pending = rng.random() < 0.18
        status = rng.choices(["NONE", "VALID", "EXPIRED", "REVOKED"], weights=[50, 25, 15, 10])[0]
        signed = "" if rng.random() < 0.06 else rng.choice(["Y", "N"])
        if status == "NONE":
            signed = "" if rng.random() < 0.5 else "N"
        if pending and status == "VALID" and signed == "Y":
            signed = "N"
        return {"pending": "Y" if pending else "N", "status": status, "signed": signed}

    # ---------- evaluator used only for the neutrality rules ----------
    @staticmethod
    def evaluate(er: dict, event: dict) -> tuple[list[tuple], list[tuple]]:
        authorized = {s["site_id"] for s in er["states"] if s["dispatch_authorized"]}
        seg_of = {s["site_id"]: s["segment"] for s in er["sites"]}
        groups: dict[str, list[dict]] = {}
        for o in er["offers"]:
            if o["site_id"] in authorized:
                groups.setdefault(o["site_id"], []).append(o)
        choices = [[None, *groups[s]] for s in sorted(groups)]
        tgt = [ticks(v) for v in er["targets"]]
        rc = [ticks(v) for v in er["relief_ceiling"]]
        vc = [ticks(v) for v in er["recovery_ceiling"]]
        cw = event["objective"]["cost_weight"]
        vw = event["objective"]["recovery_weight"]
        scored = []
        for combo in itertools.product(*choices):
            picked = [o for o in combo if o is not None]
            rel = [sum(ticks(o["relief"][t]) for o in picked) for t in range(INTERVALS)]
            rec = [sum(ticks(o["recovery"][t]) for o in picked) for t in range(INTERVALS)]
            if any(rel[t] > rc[t] or rec[t] > vc[t] for t in range(INTERVALS)):
                continue
            c1 = sum(er["weights"][t] * max(0, tgt[t] - rel[t]) for t in range(INTERVALS))
            c2 = 0
            for seg, (floor, pw) in er["floors"].items():
                got = sum(sum(ticks(v) for v in o["relief"]) for o in picked if seg_of[o["site_id"]] == seg)
                c2 += pw * max(0, ticks(floor) - got)
            c3 = cw * sum(o["cost"] for o in picked) + vw * sum(rec)
            c4 = sum(max(0, rel[t] - tgt[t]) for t in range(INTERVALS))
            c5 = len(picked)
            scored.append(((c1, c2, c3, c4, c5), tuple(sorted(o["offer_id"] for o in picked))))
        return scored, choices

    def er_is_neutral(self, er: dict, event: dict) -> bool:
        scored, _ = self.evaluate(er, event)
        scored.sort()
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            return False
        best = scored[0][1]
        for i in range(4):
            def swapped(item, i=i):
                key = list(item[0])
                key[i], key[i + 1] = key[i + 1], key[i]
                return (key, item[1])
            if min(scored, key=swapped)[1] != best:
                self.stats["pair_swaps"][i] += 1
        return True

    # ---------- grants ----------
    def pool_for(self, er: dict, weights: dict[str, int]) -> int:
        by_ben: dict[str, int] = {}
        for s in er["sites"]:
            if s["site_id"] in weights:
                by_ben[s["beneficiary"]] = by_ben.get(s["beneficiary"], 0) + weights[s["site_id"]]
        total = sum(by_ben.values())
        while True:
            pool = self.rng.randint(50, 2000) * 100 + self.rng.randint(0, 99)
            if total == 0:
                return pool
            rems = [pool * w % total for w in by_ben.values() if pool * w % total]
            if len(rems) == len(set(rems)):
                return pool
            self.stats["pool_rerolls"] += 1

    # ---------- whole extract ----------
    def build(self, out: Path) -> None:
        self.buildings()
        self.events()
        rng = self.rng
        site_lines, offer_lines, profile_lines, target_lines = [], [], [], []
        feeder_lines, state_lines, waiver_lines, weight_lines, pool_lines, cards = [], [], [], [], [], []
        floors_out = []
        all_offer_ids: list[str] = []
        for event in self.event_rows:
            eid = event["event_id"]
            for region in REGIONS:
                for attempt in range(200):
                    er = self.make_er(event, region)
                    if self.er_is_neutral(er, event):
                        break
                    self.stats["rerolls"] += 1
                else:
                    raise SystemExit(f"no neutral draw for {eid} {region}")
                for s, st, wv in zip(er["sites"], er["states"], er["waivers"]):
                    site_lines.append([eid, s["site_id"], s["code"], s["segment"], s["beneficiary"], s["critical"]])
                    state_lines.append({"event_id": eid, "site_id": s["site_id"], **{k: st[k] for k in ("dispatch_authorized", "safety_hold", "cooldown")}})
                    waiver_lines.append([eid, s["site_id"], wv["pending"], wv["status"], wv["signed"]])
                    base = rng.randint(4, 9) * 1000
                    cap = base + event["uplift_millicents_per_kwh"] + rng.randint(0, 4) * 1000
                    cards.append((eid, s["site_id"], base, cap))
                for o in er["offers"]:
                    offer_lines.append([o["offer_id"], eid, o["site_id"], o["mode"], o["cost"]])
                    all_offer_ids.append(o["offer_id"])
                    for t in range(INTERVALS):
                        profile_lines.append([o["offer_id"], t + 1, o["relief"][t], o["recovery"][t]])
                for t in range(INTERVALS):
                    target_lines.append([eid, rng.choice(REGION_CODES[region]), t + 1, er["targets"][t], er["weights"][t]])
                    feeder_lines.append((eid, rng.choice(REGION_CODES[region]), t + 1, er["relief_ceiling"][t], er["recovery_ceiling"][t]))
                for seg, (floor, pw) in er["floors"].items():
                    floors_out.append({"event_id": eid, "region_code": rng.choice(REGION_CODES[region]),
                                       "segment_code": seg, "floor_wh": floor, "priority_weight": pw})
                roll = rng.random()
                weights: dict[str, int] = {}
                if roll >= 0.02:
                    zero_all = roll < 0.05
                    for s in er["sites"]:
                        if rng.random() < 0.06:
                            continue
                        weights[s["site_id"]] = 0 if zero_all else rng.choice([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
                for sid, w in weights.items():
                    weight_lines.append([eid, sid, w])
                pool_lines.append((eid, rng.choice(REGION_CODES[region]), self.pool_for(er, weights)))
        # a handful of orphan rows the contract tells the reader to skip and count
        site_ids_by_event: dict[str, set[str]] = {}
        for row in site_lines:
            site_ids_by_event.setdefault(row[0], set()).add(row[1])
        every_site = sorted({row[1] for row in site_lines})
        for _ in range(14):
            eid = rng.choice(self.event_rows)["event_id"]
            sid = rng.choice([s for s in every_site if s not in site_ids_by_event[eid]])
            offer_lines.append([f"{eid}-{sid}-X", eid, sid, rng.choice(MODES), rng.randint(400, 26000)])
        for _ in range(36):
            ghost = rng.choice(all_offer_ids)[:-1] + "Q"
            profile_lines.append([ghost, rng.randint(1, INTERVALS), rng.randint(4, 40) * 1000, 0])
        # shuffle row order inside record files: order carries no meaning
        for lines in (site_lines, offer_lines, profile_lines, target_lines, feeder_lines, state_lines,
                      waiver_lines, weight_lines, pool_lines, cards, floors_out):
            rng.shuffle(lines)
        self.write(out, site_lines, offer_lines, profile_lines, target_lines, feeder_lines, state_lines,
                   waiver_lines, weight_lines, pool_lines, cards, floors_out)

    def write(self, out, site_lines, offer_lines, profile_lines, target_lines, feeder_lines, state_lines,
              waiver_lines, weight_lines, pool_lines, cards, floors_out) -> None:
        out.mkdir(parents=True, exist_ok=True)

        def table(name: str, sep: str, header: list[str], rows: list[list]) -> None:
            text = sep.join(header) + "\n" + "".join(sep.join(str(v) for v in r) + "\n" for r in rows)
            (out / name).write_text(text, encoding="utf-8")

        ini = ["# Winter flexibility programme, season 2026", "", "[units]", f"wh_per_tick = {WH_PER_TICK}",
               "millicents_per_cent = 1000", "", "[region_codes]"]
        for region in REGIONS:
            ini += [f"{code} = {region}" for code in REGION_CODES[region]]
        ini += ["", "[segment_codes]"] + [f"{k} = {v}" for k, v in SEGMENTS.items()]
        (out / "program.ini").write_text("\n".join(ini) + "\n", encoding="utf-8")
        (out / "events.json").write_text(json.dumps(self.event_rows, indent=1) + "\n", encoding="utf-8")
        table("sites.csv", ",", ["event_id", "site_id", "region_code", "segment_code", "beneficiary_id", "critical"], site_lines)
        table("offers.csv", ",", ["offer_id", "event_id", "site_id", "mode_label", "bid_cost_cents"], offer_lines)
        table("profiles.tsv", "\t", ["offer_id", "interval", "relief_wh", "recovery_wh"], profile_lines)
        table("targets.tsv", "\t", ["event_id", "region_code", "interval", "target_wh", "shortfall_weight"], target_lines)
        table("continuity_waivers.csv", ",", ["event_id", "site_id", "routine_certificate_pending", "waiver_status", "waiver_signed"], waiver_lines)
        table("recipient_weights.tsv", "\t", ["event_id", "site_id", "grant_weight"], weight_lines)
        (out / "site_state.jsonl").write_text("".join(json.dumps(r) + "\n" for r in state_lines), encoding="utf-8")
        (out / "segment_floors.json").write_text(json.dumps({"floors": floors_out}, indent=1) + "\n", encoding="utf-8")
        feeder = ["# feeder ceilings per event, feeder code and interval",
                  "# event_id  code itv relief_wh recovery_wh"]
        feeder += [f"{e:<10}{c:<4}{i:>3}{a:>10}{b:>10}" for e, c, i, a, b in feeder_lines]
        (out / "feeder_limits.txt").write_text("\n".join(feeder) + "\n", encoding="utf-8")
        pools = ["# grant pools per event and feeder code", "# event_id  code   pool_cents"]
        pools += [f"{e:<10}{c:<4}{p:>12}" for e, c, p in pool_lines]
        (out / "pools.txt").write_text("\n".join(pools) + "\n", encoding="utf-8")
        xml = ['<?xml version="1.0" encoding="utf-8"?>', "<rate_cards unit=\"millicents_per_kwh\">"]
        xml += [f"  <card event={quoteattr(e)} site={quoteattr(s)}><base>{b}</base><cap>{c}</cap></card>" for e, s, b, c in cards]
        xml.append("</rate_cards>")
        (out / "rate_cards.xml").write_text("\n".join(xml) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--seed", type=int, default=731904)
    args = parser.parse_args()
    builder = Builder(args.seed)
    builder.build(args.out)
    print(json.dumps(builder.stats), file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
