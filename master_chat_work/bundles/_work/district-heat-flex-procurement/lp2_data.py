"""Harden lp1 r2 (23 Oct 2026, board eb6f232): shipped-data changes on top of the lp1 r1 extract.

Source: bundle_pre_r2/environment/data (the r1 extract, kept untouched). Writes into the bundle:
- events.json with dispatch_start (ISO 8601 date-time with UTC offset). Starts are at least two hours
  apart, so the order of the strings equals the order of the instants on the shipped extract.
- profiles.tsv with no exact-half interval credit amount under the stated rates (a row whose interval
  amount would be an exact half gains 10 Wh until it is not).
- rate_cards.xml with the r2 header comment (no gloss, cap sentence, interval amount sentence).
- site_allowances.tsv: one row per site_id of sites.csv. A site's allowance is either generous (at least
  the sum of the relief of all its offers, so it never binds) or below every positive offer relief of
  the site (every such offer is blocked in every event). The shipped extract therefore never
  depends on the order in which events draw allowances.
- export_manifest.tsv recomputed from the final files.
Deterministic (seed 902117); run twice -> byte-identical output.
"""
from __future__ import annotations

import csv
import importlib.util
import io
import json
import random
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "bundle_pre_r2" / "environment" / "data"
DATA = HERE.parent.parent / "district-heat-flex-procurement" / "environment" / "data"
rng = random.Random(902117)

spec = importlib.util.spec_from_file_location("solve_r1", HERE / "bundle_pre_r2" / "solution" / "solve.py")
solve_r1 = importlib.util.module_from_spec(spec)
sys.modules["solve_r1"] = solve_r1
spec.loader.exec_module(solve_r1)

for p in sorted(SRC.iterdir()):
    if p.name != "schema.md":  # schema.md is edited by hand in the bundle
        shutil.copyfile(p, DATA / p.name)

# ---- events.json: dispatch_start after name
events = json.loads((SRC / "events.json").read_text(encoding="utf-8"))
slots = rng.sample(range(1800), len(events))
season = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
out_events = []
for ev, slot in zip(events, slots):
    instant = season + timedelta(hours=2 * slot, minutes=15 * rng.randrange(4))
    offset = timezone(timedelta(hours=0 if rng.random() < 0.1 else 1))
    local = instant.astimezone(offset).isoformat()
    item = {}
    for key, value in ev.items():
        item[key] = value
        if key == "name":
            item["dispatch_start"] = local
    out_events.append(item)
starts = [e["dispatch_start"] for e in out_events]
assert sorted(starts) == sorted(starts, key=datetime.fromisoformat) and len(set(starts)) == len(starts)
(DATA / "events.json").write_text(json.dumps(out_events, indent=1) + "\n", encoding="utf-8")

# ---- profiles.tsv: no exact-half interval amount
ex = solve_r1.load(SRC)
wh = ex.wh_per_tick
den = 1000 * ex.millicents_per_cent
uplift = {e["event_id"]: int(e["uplift_millicents_per_kwh"]) for e in ex.events}
rate_of = {o.offer_id: min(solve_r1.rate_before_cap(o.site, uplift[o.site.event_id]), o.site.cap) for o in ex.offers}
lines = (SRC / "profiles.tsv").read_text(encoding="utf-8").split("\n")
assert lines[0] == "offer_id\tinterval\trelief_wh\trecovery_wh\tregister_multiplier" and lines[-1] == ""
cleaned = 0
out = [lines[0]]
for raw in lines[1:-1]:
    oid, itv, rel, rec, mult = raw.split("\t")
    rate = rate_of.get(oid)
    value = int(rel)
    if rate is not None:
        while (solve_r1.half_up(value * int(mult), wh) * wh * rate) % den * 2 == den:
            value += 10
            cleaned += 1
    out.append(f"{oid}\t{itv}\t{value}\t{rec}\t{mult}")
(DATA / "profiles.tsv").write_text("\n".join(out) + "\n", encoding="utf-8")

# ---- rate_cards.xml: r2 header comment
xml = (SRC / "rate_cards.xml").read_text(encoding="utf-8")
start, end = xml.index("<!--"), xml.index("-->\n") + 4
comment = (
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
(DATA / "rate_cards.xml").write_text(xml[:start] + comment + xml[end:], encoding="utf-8")

# ---- site_allowances.tsv
ex2 = solve_r1.load(DATA)
totals: dict[str, dict[str, int]] = {}
for o in ex2.offers:
    per_event = totals.setdefault(o.site.site_id, {})
    per_event[o.site.event_id] = per_event.get(o.site.event_id, 0) + sum(o.relief)
site_ids = []
with (DATA / "sites.csv").open(newline="", encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        if r["site_id"] not in site_ids:
            site_ids.append(r["site_id"])
rows = []
blocked_sites = 0
for sid in sorted(site_ids):
    per_event = totals.get(sid, {})
    positive = [sum(o.relief) for o in ex2.offers if o.site.site_id == sid and sum(o.relief) > 0]
    if positive and rng.random() < 0.05:
        allowance = rng.randrange(0, min(positive))
        blocked_sites += 1
    else:
        allowance = (sum(per_event.values()) + rng.randrange(0, 4000)) // 50 * 50 + 50
    rows.append(f"{sid}\t{allowance}\n")
allow_text = (
    "# Season relief allowance of each site, in energy ticks; one row per site_id of sites.csv.\n"
    "# The allowance of a site is drawn by the events of the season, which reach it one at a time in the\n"
    "# order of the instants at which they start (dispatch_start in events.json), events that start at the\n"
    "# same instant following the programme conventions. When an event is reached, what remains of a\n"
    "# site's allowance is its allowance_ticks less the relief ticks, over all intervals, of the site's\n"
    "# offers chosen in the events reached before it. An offer whose relief ticks over all intervals are\n"
    "# more than what remains of its site's allowance when its event is reached is not a candidate offer.\n"
    "site_id\tallowance_ticks\n") + "".join(rows)
(DATA / "site_allowances.tsv").write_text(allow_text, encoding="utf-8")


# ---- export_manifest.tsv, computed from the final files as written
def records(name: str, sep: str) -> list[dict[str, str]]:
    body = "\n".join(x for x in (DATA / name).read_text(encoding="utf-8").split("\n") if not x.startswith("#"))
    return list(csv.DictReader(io.StringIO(body), delimiter=sep))


def fixed(name: str, a: int, b: int) -> list[str]:
    got = [x for x in (DATA / name).read_text(encoding="utf-8").split("\n") if x.strip() and not x.startswith("#")]
    return [x[a - 1:b].strip() for x in got]


entries: list[tuple[str, int, str, str]] = [("events.json", len(out_events), "", "")]
for name, sep, fields in (("sites.csv", ",", []), ("offers.csv", ",", ["bid_cost_cents"]),
                          ("profiles.tsv", "\t", ["relief_wh", "recovery_wh"]),
                          ("targets.tsv", "\t", ["target_wh"]), ("continuity_waivers.csv", ",", []),
                          ("recipient_weights.tsv", "\t", ["grant_weight"]),
                          ("site_allowances.tsv", "\t", ["allowance_ticks"])):
    recs = records(name, sep)
    if not fields:
        entries.append((name, len(recs), "", ""))
    for f in fields:
        entries.append((name, len(recs), f, str(sum(int(r[f]) for r in recs))))
feeder = fixed("feeder_limits.txt", 18, 27)
entries.append(("feeder_limits.txt", len(feeder), "relief_ceiling_wh", str(sum(int(x) for x in feeder))))
pools = fixed("pools.txt", 15, 26)
entries.append(("pools.txt", len(pools), "pool_cents", str(sum(int(x) for x in pools))))
states = [x for x in (DATA / "site_state.jsonl").read_text(encoding="utf-8").split("\n") if x.strip()]
entries.append(("site_state.jsonl", len(states), "", ""))
floors = json.loads((DATA / "segment_floors.json").read_text(encoding="utf-8"))["floors"]
entries.append(("segment_floors.json", len(floors), "floor_wh", str(sum(int(f["floor_wh"]) for f in floors))))
cards = list(ET.fromstring((DATA / "rate_cards.xml").read_text(encoding="utf-8")).iter("card"))
entries.append(("rate_cards.xml", len(cards), "base", str(sum(int(c.findtext("base")) for c in cards))))
old = (SRC / "export_manifest.tsv").read_text(encoding="utf-8")
manifest = old[:old.index("file\trecords\tfield\tfield_sum\n")] + "file\trecords\tfield\tfield_sum\n"
manifest += "".join(f"{a}\t{b}\t{c}\t{d}\n" for a, b, c, d in entries)
(DATA / "export_manifest.tsv").write_text(manifest, encoding="utf-8")
print("cleaned half steps", cleaned, "sites", len(site_ids), "blocked sites", blocked_sites,
      "manifest lines", len(entries))
