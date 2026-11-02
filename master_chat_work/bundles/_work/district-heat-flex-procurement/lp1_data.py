"""Harden lp1 r1 (23 Oct 2026): apply the L1/L2/L4/L7 data changes to the shipped extract.

Reads the round-2 originals kept in lp1_src/ (profiles.tsv, rate_cards.xml, program.ini) and writes into
the bundle's environment/data: profiles.tsv with a register_multiplier column, rate_cards.xml with the
header comment and override elements on some commercial cards, program.ini with [segment_rate_adders],
and a new export_manifest.tsv computed from the final files. Deterministic (seed 731905); run twice ->
byte-identical output.
"""
from __future__ import annotations

import csv
import io
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "lp1_src"
DATA = HERE.parent.parent / "district-heat-flex-procurement" / "environment" / "data"
rng = random.Random(731905)

# ---- program.ini: segment rate adders (kept before the export tool's section)
ini = (SRC / "program.ini").read_text(encoding="utf-8")
adders = ("# Rate adders, in mill-cents per kWh, by segment name. The value of an option is added to the\n"
          "# rate of every site row whose segment is that name.\n"
          "[segment_rate_adders]\ncommercial = 0\npublic = 750\n\n")
assert ini.count("[export]") == 1
ini = ini.replace("[export]", adders + "[export]")
(DATA / "program.ini").write_text(ini, encoding="utf-8")

# ---- profiles.tsv: register multiplier per row; the Wh energy of every row is unchanged
lines = (SRC / "profiles.tsv").read_text(encoding="utf-8").split("\n")
assert lines[0] == "offer_id\tinterval\trelief_wh\trecovery_wh" and lines[-1] == ""
out = ["offer_id\tinterval\trelief_wh\trecovery_wh\tregister_multiplier"]
scaled = 0
for raw in lines[1:-1]:
    oid, itv, rel, rec = raw.split("\t")
    m = 1
    if rng.random() < 0.05:
        m = rng.choice([2, 5])
        if int(rel) % m or int(rec) % m:
            m = 1
    if m > 1:
        scaled += 1
    out.append(f"{oid}\t{itv}\t{int(rel) // m}\t{int(rec) // m}\t{m}")
(DATA / "profiles.tsv").write_text("\n".join(out) + "\n", encoding="utf-8")

# ---- rate_cards.xml: header comment, override on some commercial cards
segment = {}
with (DATA / "sites.csv").open(newline="", encoding="utf-8") as fh:
    for r in csv.DictReader(fh):
        segment[(r["event_id"], r["site_id"])] = r["segment_code"]
xml = (SRC / "rate_cards.xml").read_text(encoding="utf-8")
head = '<?xml version="1.0" encoding="utf-8"?>\n'
assert xml.startswith(head)
comment = (
    "<!--\n"
    "  Rate cards of this extract, one card per site row; every rate is in mill-cents per kWh.\n"
    "  The rate of a site row starts from the base element of its card. A card that also carries an\n"
    "  override element starts from the override value instead of the base value.\n"
    "  credit_cents of a chosen offer: for each interval of its event, take the offer's relief ticks in\n"
    "  that interval times wh_per_tick, times the effective rate of the offer's site row, divided by 1000\n"
    "  times millicents_per_cent, and round that interval amount half to even to whole cents (an exact\n"
    "  half goes to the even neighbour). The offer's credit_cents is the sum of its interval amounts.\n"
    "-->\n")
card_re = re.compile(r'(  <card event="([^"]+)" site="([^"]+)"><base>(\d+)</base>)(<cap>(\d+)</cap></card>)')
overridden = 0


def patch(m: re.Match) -> str:
    global overridden
    key = (m.group(2), m.group(3))
    if segment.get(key) == "C" and rng.random() < 0.04:
        overridden += 1
        return f"{m.group(1)}<override>{rng.randint(1, 9) * 1000}</override>{m.group(5)}"
    return m.group(0)


body = card_re.sub(patch, xml[len(head):])
(DATA / "rate_cards.xml").write_text(head + comment + body, encoding="utf-8")

# ---- export_manifest.tsv, computed from the final files as written


def records(name: str, sep: str) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO((DATA / name).read_text(encoding="utf-8")), delimiter=sep))


def fixed(name: str, a: int, b: int) -> list[str]:
    rows = [x for x in (DATA / name).read_text(encoding="utf-8").split("\n") if x.strip() and not x.startswith("#")]
    return [x[a - 1:b].strip() for x in rows]


entries: list[tuple[str, int, str, str]] = []
events = json.loads((DATA / "events.json").read_text(encoding="utf-8"))
entries.append(("events.json", len(events), "", ""))
for name, sep, fields in (("sites.csv", ",", []), ("offers.csv", ",", ["bid_cost_cents"]),
                          ("profiles.tsv", "\t", ["relief_wh", "recovery_wh"]),
                          ("targets.tsv", "\t", ["target_wh"]), ("continuity_waivers.csv", ",", []),
                          ("recipient_weights.tsv", "\t", ["grant_weight"])):
    rows = records(name, sep)
    if not fields:
        entries.append((name, len(rows), "", ""))
    for f in fields:
        entries.append((name, len(rows), f, str(sum(int(r[f]) for r in rows))))
feeder = fixed("feeder_limits.txt", 18, 27)
entries.append(("feeder_limits.txt", len(feeder), "relief_ceiling_wh", str(sum(int(x) for x in feeder))))
pools = fixed("pools.txt", 15, 26)
entries.append(("pools.txt", len(pools), "pool_cents", str(sum(int(x) for x in pools))))
states = [x for x in (DATA / "site_state.jsonl").read_text(encoding="utf-8").split("\n") if x.strip()]
entries.append(("site_state.jsonl", len(states), "", ""))
floors = json.loads((DATA / "segment_floors.json").read_text(encoding="utf-8"))["floors"]
entries.append(("segment_floors.json", len(floors), "floor_wh", str(sum(int(f["floor_wh"]) for f in floors))))
import xml.etree.ElementTree as ET  # noqa: E402

cards = ET.fromstring((DATA / "rate_cards.xml").read_text(encoding="utf-8")).iter("card")
cards = list(cards)
entries.append(("rate_cards.xml", len(cards), "base", str(sum(int(c.findtext("base")) for c in cards))))
manifest = ("# Export receipt, written by the export tool after it wrote the other files of this extract.\n"
            "# Each line names a file and gives its records, counted the way data_quality.json counts the\n"
            "# rows of that file. Where a field is named, field_sum is the sum of that field's values as they\n"
            "# are written in the file, over all of its records; otherwise field and field_sum are empty.\n"
            "# A file whose lines here agree with it arrived whole.\n"
            "file\trecords\tfield\tfield_sum\n")
manifest += "".join(f"{a}\t{b}\t{c}\t{d}\n" for a, b, c, d in entries)
(DATA / "export_manifest.tsv").write_text(manifest, encoding="utf-8")
print("scaled profile rows", scaled, "override cards", overridden, "manifest lines", len(entries))
