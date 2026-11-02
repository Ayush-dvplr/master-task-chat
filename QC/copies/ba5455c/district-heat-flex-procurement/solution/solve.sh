#!/bin/bash
# Oracle dispatcher for district-heat-flex-procurement.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out
# Self-check stage: recompute grants, drawn allowances and credits outside the program (prints check <id> ok).
python3 - /app/data /app/out <<'PYEOF'
#!/usr/bin/env python3
"""Self-check of the reports in OUT_DIR against figures recomputed here from DATA_DIR, outside derive_report.py.

Usage: python3 - DATA_DIR OUT_DIR (inline self-check stage of solve.sh)
Prints one line per check and exits non-zero when a recomputed figure differs from the reports.
"""
from __future__ import annotations

import configparser
import csv
import json
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from fractions import Fraction
from pathlib import Path


def rows(path: Path, delimiter: str) -> list[dict[str, str]]:
    lines = [x for x in path.read_text(encoding="utf-8").splitlines() if x and not x.startswith("#")]
    return list(csv.DictReader(lines, delimiter=delimiter))


def nearest_even(value: Fraction) -> int:
    floor = value.numerator // value.denominator
    rest = value - floor
    if rest > Fraction(1, 2) or (rest == Fraction(1, 2) and floor % 2 == 1):
        return floor + 1
    return floor


def nearest_up(value: Fraction) -> int:
    return int((value + Fraction(1, 2)).numerator // (value + Fraction(1, 2)).denominator)


class Inputs:
    def __init__(self, data: Path) -> None:
        ini = configparser.ConfigParser()
        ini.read(data / "program.ini", encoding="utf-8")
        self.wh = int(ini["units"]["wh_per_tick"])
        self.mc = int(ini["units"]["millicents_per_cent"])
        self.claim = int(ini["grants"]["claim_cents_per_weight"])
        self.minimum = int(ini["grants"]["minimum_grant_cents"])
        region_of = {k.upper(): v for k, v in ini["region_codes"].items()}
        segment_of = {k.upper(): v for k, v in ini["segment_codes"].items()}
        adder = {k.lower(): int(v) for k, v in ini["segment_rate_adders"].items()}
        self.events = {e["event_id"]: e for e in json.loads((data / "events.json").read_text(encoding="utf-8"))}
        self.sites = {}
        for r in rows(data / "sites.csv", ","):
            if r["region_code"].upper() in region_of:
                self.sites[(r["event_id"], r["site_id"])] = {
                    "region": region_of[r["region_code"].upper()], "segment": segment_of[r["segment_code"].upper()],
                    "ben": r["beneficiary_id"], "critical": r["critical"] == "Y"}
        for key, site in self.sites.items():
            site["adder"] = adder.get(site["segment"].lower(), 0)
        for line in (data / "site_state.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                s = json.loads(line)
                if (s["event_id"], s["site_id"]) in self.sites:
                    self.sites[(s["event_id"], s["site_id"])].update(hold=s["safety_hold"], cool=s["cooldown"])
        for w in rows(data / "continuity_waivers.csv", ","):
            if (w["event_id"], w["site_id"]) in self.sites:
                self.sites[(w["event_id"], w["site_id"])].update(
                    pending=w["routine_certificate_pending"] == "Y", status=w["waiver_status"],
                    signed=(w["waiver_signed"] or "").strip())
        for card in ET.parse(data / "rate_cards.xml").getroot().iter("card"):
            key = (card.get("event"), card.get("site"))
            if key in self.sites:
                start = card.findtext("override") or card.findtext("base")
                self.sites[key].update(start=int(start), cap=int(card.findtext("cap")))
        for w in rows(data / "recipient_weights.tsv", "\t"):
            if (w["event_id"], w["site_id"]) in self.sites:
                self.sites[(w["event_id"], w["site_id"])]["weight"] = int(w["grant_weight"])
        self.offer_site = {r["offer_id"]: (r["event_id"], r["site_id"]) for r in rows(data / "offers.csv", ",")}
        self.relief: dict[str, dict[int, int]] = {}
        self.recovery: dict[str, dict[int, int]] = {}
        for r in rows(data / "profiles.tsv", "\t"):
            oid, itv = r["offer_id"], int(r["interval"])
            if oid not in self.offer_site:
                continue
            if not 1 <= itv <= int(self.events[self.offer_site[oid][0]]["interval_count"]):
                continue
            if itv in self.relief.setdefault(oid, {}):
                continue
            mult = int(r["register_multiplier"])
            self.relief[oid][itv] = nearest_up(Fraction(int(r["relief_wh"]) * mult, self.wh))
            self.recovery.setdefault(oid, {})[itv] = nearest_up(Fraction(int(r["recovery_wh"]) * mult, self.wh))
        self.allowance, self.draws = {}, {}
        for r in rows(data / "site_allowances.tsv", "\t"):
            self.allowance[r["site_id"]] = int(r["allowance_ticks"])
            if (r.get("draws_from") or "").strip():
                self.draws[r["site_id"]] = r["draws_from"].strip()
        self.pools = {}
        for line in (data / "pools.txt").read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                self.pools[(line[0:10].strip(), region_of[line[10:14].strip().upper()])] = int(line[14:26])

    def season(self) -> list[str]:
        ids = sorted(self.events, reverse=True)
        return sorted(ids, key=lambda e: datetime.fromisoformat(self.events[e]["dispatch_start"]))

    def label(self, site: dict) -> str:
        if site.get("hold"):
            return "SAFETY_HOLD"
        if site.get("cool"):
            return "COOLDOWN"
        valid = (site.get("status") == "VALID" and site.get("signed") == "Y" and site["critical"]
                 and site["segment"] == "public")
        if site.get("pending"):
            return "CONTINUITY_WAIVED" if valid else "CERTIFICATE_PENDING"
        return "CLEAR"


def documents(out: Path) -> dict[tuple[str, str], dict]:
    found = {}
    for path in out.glob("region_*.json"):
        doc = json.loads(path.read_text(encoding="utf-8"))
        for event in doc["events"]:
            found[(event["event_id"], doc["region"])] = event
    return found


def check_credit(inp: Inputs, docs: dict) -> int:
    """R11: credit_cents per event-region from credited relief ticks and the capped rate."""
    bad = 0
    for (eid, region), event in docs.items():
        uplift = int(inp.events[eid]["uplift_millicents_per_kwh"])
        total = 0
        for oid in event["selected_offer_ids"]:
            site = inp.sites[inp.offer_site[oid]]
            rate = min(site["start"] + uplift + site["adder"], site["cap"])
            for itv, relief in inp.relief.get(oid, {}).items():
                credited = max(0, relief - inp.recovery[oid][itv])
                total += nearest_even(Fraction(credited * inp.wh * rate, 1000 * inp.mc))
        bad += total != event["credit_cents"]
    return bad


def check_allowance(inp: Inputs, docs: dict) -> int:
    """R10: every chosen offer fits what remained of the allowance its site draws on, following draws_from."""
    def holder(sid: str) -> str:
        while sid in inp.draws:
            sid = inp.draws[sid]
        return sid

    left = dict(inp.allowance)
    bad = 0
    for eid in inp.season():
        drawn = []
        for (event_id, _), event in docs.items():
            if event_id == eid:
                drawn.extend(event["selected_offer_ids"])
        for oid in drawn:
            need = sum(inp.relief.get(oid, {}).values())
            bad += need > left[holder(inp.offer_site[oid][1])]
        for oid in drawn:
            left[holder(inp.offer_site[oid][1])] -= sum(inp.relief.get(oid, {}).values())
    return bad


def share(pool: int, weight: dict[str, int]) -> dict[str, int]:
    total = sum(weight.values())
    cut = {b: pool * w // total for b, w in weight.items()}
    rest = {b: pool * w % total for b, w in weight.items()}
    for b in sorted(cut, key=lambda b: (rest[b], b), reverse=True)[:pool - sum(cut.values())]:
        cut[b] += 1
    return cut


def check_grants(inp: Inputs, docs: dict) -> tuple[int, int]:
    """R9: funded pool with carried cents, then claims or largest remainder with the minimum-grant second share."""
    bad = checked = 0
    regions = sorted({region for _, region in docs})
    carried = dict.fromkeys(regions, 0)
    for eid in inp.season():
        for region in regions:
            event = docs[(eid, region)]
            funded = max(0, inp.pools.get((eid, region), 0) + carried[region] - event["credit_cents"])
            weight: dict[str, int] = {}
            for (event_id, _), site in inp.sites.items():
                if event_id == eid and site["region"] == region and site.get("weight") is not None:
                    heft = site["weight"] * (2 if inp.label(site) == "CONTINUITY_WAIVED" else 1)
                    weight[site["ben"]] = weight.get(site["ben"], 0) + heft
            weight = {b: w for b, w in weight.items() if w > 0}
            cents: dict[str, int] = {}
            if weight and sum(w * inp.claim for w in weight.values()) <= funded:
                cents = {b: w * inp.claim for b, w in weight.items()}
            elif weight:
                first = share(funded, weight)
                kept = {b: w for b, w in weight.items() if first[b] >= inp.minimum}
                cents = first if len(kept) == len(weight) else dict.fromkeys(weight, 0)
                if kept and len(kept) < len(weight):
                    cents.update(share(funded, kept))
            listed = {g["beneficiary_id"]: g["cents"] for g in event["grants"]}
            checked += 1
            bad += listed != cents or event["grant_funded_cents"] != funded
            carried[region] = funded - sum(cents.values())
    return bad, checked


def main(argv: list[str]) -> int:
    data, out = Path(argv[1]), Path(argv[2])
    inp = Inputs(data)
    docs = documents(out)
    failures = 0
    bad, checked = check_grants(inp, docs)
    print(f"check R9 {'ok' if bad == 0 else 'FAILED'} (grant cents of {checked} event-regions recomputed)")
    failures += bad
    bad = check_allowance(inp, docs)
    print(f"check R10 {'ok' if bad == 0 else 'FAILED'} (remaining allowance of every chosen offer recomputed)")
    failures += bad
    bad = check_credit(inp, docs)
    print(f"check R11 {'ok' if bad == 0 else 'FAILED'} (credit_cents of {len(docs)} event-regions recomputed)")
    failures += bad
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
PYEOF
