#!/bin/bash
# Oracle dispatcher for district-heat-flex-procurement.
set -euo pipefail

mkdir -p /app/out
cp /solution/solve.py /app/out/derive_report.py
python3 /app/out/derive_report.py /app/data /app/out
# Self-check stage: recompute grants, drawn allowances and credits outside the program.
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
    """credit_cents per event-region from credited relief ticks and the capped rate."""
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
    """Every chosen offer fits what remained of the allowance its site draws on, following draws_from."""
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
    """Funded pool with carried cents, then claims or largest remainder with the minimum-grant second share."""
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
    print(f"grant cents recomputed outside the program: {'agree' if bad == 0 else 'DIFFER'} (grant cents of {checked} event-regions recomputed)")
    failures += bad
    bad = check_allowance(inp, docs)
    print(f"remaining allowance recomputed outside the program: {'agrees' if bad == 0 else 'DIFFERS'} (remaining allowance of every chosen offer recomputed)")
    failures += bad
    bad = check_credit(inp, docs)
    print(f"credit_cents recomputed outside the program: {'agree' if bad == 0 else 'DIFFER'} (credit_cents of {len(docs)} event-regions recomputed)")
    failures += bad
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
PYEOF
# Own-extract stage: build four small extracts by hand and three altered copies of the shipped extract, run
# derive_report.py on each and compare its figures with figures worked out by hand or recomputed outside the
# program. Everything it writes lives under a temp dir; it only prints what it found and never changes /app/out.
python3 - /app/out/derive_report.py /app/data "${BASH_SOURCE[0]}" <<'PYEOF' || true
"""Run the delivered program on four small hand-built extracts and on three altered copies of the shipped
extract, and compare a few figures with hand-worked or independently recomputed values."""
import configparser
import json
import shutil
import subprocess
import sys
import tempfile
from fractions import Fraction
from pathlib import Path

PROGRAM = sys.argv[1]
DATA = Path(sys.argv[2])
SCRIPT = Path(sys.argv[3]) if Path(sys.argv[3]).is_file() else Path("/solution/solve.sh")
CODES = {"North": ("N1", "N2"), "South": ("S1", "S2"), "West": ("W1", "W2"), "East": ("E1", "E2")}


def site(eid, sid, **extra):
    row = {"event_id": eid, "sid": sid, "seg": "C", "base": 4000, "cap": 9000, "override": None}
    row.update(extra)
    return row


def write(folder: Path, spec: dict) -> Path:
    """Write every input file schema.md names, with North as the only region that has targets."""
    folder.mkdir(parents=True)
    adders = spec.get("adders", {"commercial": 0, "public": 0})
    ini = "[units]\nwh_per_tick = 10\nmillicents_per_cent = 1000\n\n[region_codes]\n"
    ini += "".join(f"{c} = {r}\n" for r, codes in CODES.items() for c in codes)
    ini += "\n[segment_codes]\nC = commercial\nP = public\n\n[segment_rate_adders]\n"
    ini += "".join(f"{g} = {v}\n" for g, v in sorted(adders.items()))
    ini += "\n[grants]\nclaim_cents_per_weight = 40\nminimum_grant_cents = 25\n\n[export]\nwaiver_signed = Y\n"
    (folder / "program.ini").write_text(ini, encoding="utf-8")
    events = [{"event_id": e, "name": "own check", "dispatch_start": start, "interval_count": n,
               "objective": {"cost_weight": 1, "recovery_weight": 0}, "uplift_millicents_per_kwh": uplift}
              for e, start, n, uplift in spec["events"]]
    (folder / "events.json").write_text(json.dumps(events, indent=1) + "\n", encoding="utf-8")
    sites, offers = spec["sites"], spec["offers"]
    files = {
        "sites.csv": ["event_id,site_id,region_code,segment_code,beneficiary_id,critical"]
        + [f"{s['event_id']},{s['sid']},N1,{s['seg']},BEN-{s['sid']},N" for s in sites],
        "continuity_waivers.csv": ["event_id,site_id,routine_certificate_pending,waiver_status,waiver_signed"]
        + [f"{s['event_id']},{s['sid']},N,NONE," for s in sites],
        "recipient_weights.tsv": ["event_id\tsite_id\tgrant_weight"],
        "offers.csv": ["offer_id,event_id,site_id,mode_label,bid_cost_cents"]
        + [f"{o[0]},{o[1]},{o[2]},SETBACK_2C,100" for o in offers],
        "profiles.tsv": ["offer_id\tinterval\trelief_wh\trecovery_wh\tregister_multiplier"]
        + [f"{o[0]}\t{t + 1}\t{wh}\t0\t1" for o in offers for t, wh in enumerate(o[3])],
        "targets.tsv": ["event_id\tregion_code\tinterval\ttarget_wh\tshortfall_weight"],
        "feeder_limits.txt": ["# event_id  code itv relief_wh recovery_wh"],
        "pools.txt": ["# event_id  code   pool_cents"],
    }
    for e, _, n, _ in spec["events"]:
        for region, codes in CODES.items():
            for t in range(n):
                wh = 100000 if region == "North" else 0
                files["targets.tsv"].append(f"{e}\t{codes[t % 2]}\t{t + 1}\t{wh}\t1")
                cap = 500000 if region == "North" else 0
                files["feeder_limits.txt"].append(f"{e:<10}{codes[(t + 1) % 2]:<4}{t + 1:>3}{cap:>10}{cap:>10}")
    owned = sorted({s["sid"] for s in sites})
    held = {sid: spec.get("allowances", {}).get(sid, 10 ** 9) for sid in owned}
    files["site_allowances.tsv"] = ["site_id\tallowance_ticks\tdraws_from"] + [f"{k}\t{v}\t" for k, v in held.items()]
    for name, lines in files.items():
        (folder / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    (folder / "site_state.jsonl").write_text("".join(json.dumps(
        {"event_id": s["event_id"], "site_id": s["sid"], "dispatch_authorized": True, "safety_hold": False,
         "cooldown": False}) + "\n" for s in sites), encoding="utf-8")
    cards = "".join(f'<card event="{s["event_id"]}" site="{s["sid"]}"><base>{s["base"]}</base>'
                    + ("" if s["override"] is None else f'<override>{s["override"]}</override>')
                    + f'<cap>{s["cap"]}</cap></card>\n' for s in sites)
    (folder / "rate_cards.xml").write_text(f'<?xml version="1.0"?>\n<rate_cards>\n{cards}</rate_cards>\n',
                                           encoding="utf-8")
    (folder / "segment_floors.json").write_text('{"floors": []}\n', encoding="utf-8")
    n_rows = lambda name: len(files[name]) - 1
    receipt = [("events.json", len(events), "", ""), ("sites.csv", len(sites), "", ""),
               ("offers.csv", len(offers), "bid_cost_cents", str(100 * len(offers))),
               ("profiles.tsv", n_rows("profiles.tsv"), "relief_wh", str(sum(sum(o[3]) for o in offers))),
               ("profiles.tsv", n_rows("profiles.tsv"), "recovery_wh", "0"),
               ("targets.tsv", n_rows("targets.tsv"), "target_wh",
                str(sum(int(x.split("\t")[3]) for x in files["targets.tsv"][1:]))),
               ("continuity_waivers.csv", len(sites), "", ""), ("recipient_weights.tsv", 0, "grant_weight", "0"),
               ("site_allowances.tsv", len(held), "allowance_ticks", str(sum(held.values()))),
               ("feeder_limits.txt", n_rows("feeder_limits.txt"), "relief_ceiling_wh",
                str(sum(int(x[17:27]) for x in files["feeder_limits.txt"][1:]))),
               ("pools.txt", 0, "pool_cents", "0"), ("site_state.jsonl", len(sites), "", ""),
               ("segment_floors.json", 0, "floor_wh", "0"),
               ("rate_cards.xml", len(sites), "base", str(sum(s["base"] for s in sites)))]
    (folder / "export_manifest.tsv").write_text("file\trecords\tfield\tfield_sum\n" + "".join(
        "\t".join(map(str, row)) + "\n" for row in receipt), encoding="utf-8")
    return folder


def run(folder: Path) -> dict:
    out = folder.parent / (folder.name + "-out")
    done = subprocess.run([sys.executable, PROGRAM, str(folder), str(out)], capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"derive_report.py exited {done.returncode} on {folder.name}: {done.stderr.strip()}")
    return {p.name: json.loads(p.read_text(encoding="utf-8")) for p in out.glob("*.json")}


def north(reports: dict, eid: str) -> dict:
    return next(e for e in reports["region_North.json"]["events"] if e["event_id"] == eid)


def report(what: str, got, want) -> None:
    print(f"own extract, {what}: program {got}, by hand {want}, {'agrees' if got == want else 'DIFFERS'}")


def altered(what: str, got, want) -> None:
    print(f"altered copy of the shipped extract, {what}: program {got}, recomputed outside the program {want}, "
          f"{'agrees' if got == want else 'DIFFERS'}")


def self_check() -> dict:
    """Load the routines of the self-check stage above (first heredoc of this script) without running it."""
    text = SCRIPT.read_text(encoding="utf-8")
    start = text.index("<<'PYEOF'\n") + len("<<'PYEOF'\n")
    space = {"__name__": "self_check"}
    exec(compile(text[start:text.index("\nPYEOF\n", start)], "self_check", "exec"), space)
    return space


def copy_of(work: Path, name: str) -> Path:
    return Path(shutil.copytree(DATA, work / name))


def bump_receipt(folder: Path, name: str, field: str, delta: int) -> None:
    path = folder / "export_manifest.tsv"
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        cells = line.rstrip("\n").split("\t")
        if len(cells) == 4 and cells[0] == name and cells[2] == field:
            lines[i] = "\t".join(cells[:3] + [str(int(cells[3]) + delta)]) + "\n"
    path.write_text("".join(lines), encoding="utf-8")


def weights(inp, eid: str, region: str) -> dict:
    found: dict = {}
    for (event_id, _), site in inp.sites.items():
        if event_id == eid and site["region"] == region and site.get("weight") is not None:
            heft = site["weight"] * (2 if inp.label(site) == "CONTINUITY_WAIVED" else 1)
            found[site["ben"]] = found.get(site["ben"], 0) + heft
    return {b: w for b, w in found.items() if w > 0}


def grant_cents(check: dict, inp, funded: int, weight: dict) -> dict:
    if sum(w * inp.claim for w in weight.values()) <= funded:
        return {b: w * inp.claim for b, w in weight.items()}
    first = check["share"](funded, weight)
    kept = {b: w for b, w in weight.items() if first[b] >= inp.minimum}
    cents = first if len(kept) == len(weight) else dict.fromkeys(weight, 0)
    if kept and len(kept) < len(weight):
        cents.update(check["share"](funded, kept))
    return cents


def credit_of(check: dict, inp, eid: str, offer_ids: list) -> int:
    uplift = int(inp.events[eid]["uplift_millicents_per_kwh"])
    total = 0
    for oid in offer_ids:
        site = inp.sites[inp.offer_site[oid]]
        rate = min(site["start"] + uplift + site["adder"], site["cap"])
        for itv, relief in inp.relief.get(oid, {}).items():
            credited = max(0, relief - inp.recovery[oid][itv])
            total += check["nearest_even"](Fraction(credited * inp.wh * rate, 1000 * inp.mc))
    return total


def main() -> int:
    work = Path(tempfile.mkdtemp(prefix="own-extracts-"))
    # 1. Site D-1 holds 150 ticks. Its offer in the earlier event draws 100 ticks (600 + 400 Wh at 10 Wh per tick),
    #    so 50 remain and its 100-tick offer in the later event is not a candidate; only D-2's offer is.
    drawn = write(work / "drawn", {
        "events": [("OWN-0101", "2026-12-02T10:00:00+00:00", 2, 0), ("OWN-0102", "2026-12-02T11:00:00+00:00", 2, 0)],
        "sites": [site("OWN-0101", "D-1"), site("OWN-0102", "D-1"), site("OWN-0102", "D-2")],
        "offers": [("OWN-0101-D-1-A", "OWN-0101", "D-1", [600, 400]), ("OWN-0102-D-1-A", "OWN-0102", "D-1", [600, 400]),
                   ("OWN-0102-D-2-A", "OWN-0102", "D-2", [300, 300])],
        "allowances": {"D-1": 150}})
    got = run(drawn)
    report("candidate_offer_count of the later event OWN-0102", north(got, "OWN-0102")["candidate_offer_count"], 1)
    # 2. Site Q-1 holds 150 ticks and offers 100 ticks in both events. OWN-0202 starts at 08:30 UTC (09:30+01:00),
    #    before OWN-0201 at 09:00 UTC, though its id and its written start sort later; it takes the allowance.
    order = write(work / "order", {
        "events": [("OWN-0201", "2026-12-01T09:00:00+00:00", 1, 0), ("OWN-0202", "2026-12-01T09:30:00+01:00", 1, 0)],
        "sites": [site("OWN-0201", "Q-1"), site("OWN-0202", "Q-1")],
        "offers": [("OWN-0201-Q-1-A", "OWN-0201", "Q-1", [1000]), ("OWN-0202-Q-1-A", "OWN-0202", "Q-1", [1000])],
        "allowances": {"Q-1": 150}})
    got = run(order)
    picks = {eid: north(got, eid)["selected_offer_ids"] for eid in ("OWN-0201", "OWN-0202")}
    report("events that select Q-1's offer", sorted(e for e, ids in picks.items() if ids), ["OWN-0202"])
    # 3. Public site P-1: override 3000 + uplift 500 + public adder 750 = 4250 mill-cents per kWh, above its cap 4000,
    #    so the effective rate is 4000. 10000 Wh = 1000 ticks; 1000 x 10 x 4000 / (1000 x 1000) = 40 cents.
    rate = write(work / "rate", {
        "events": [("OWN-0301", "2026-12-04T10:00:00+00:00", 1, 500)],
        "sites": [site("OWN-0301", "P-1", seg="P", base=6000, override=3000, cap=4000)],
        "offers": [("OWN-0301-P-1-A", "OWN-0301", "P-1", [10000])],
        "adders": {"commercial": 0, "public": 750}})
    got = run(rate)
    report("credit_cents of OWN-0301", north(got, "OWN-0301")["credit_cents"], 40)
    report("cap_binding_count", got["policy_audit.json"]["cap_binding_count"], 1)
    # 4. Site H-1 at base 1000: interval 1 is 1500 Wh = 150 ticks, 150 x 10 x 1000 / 10^6 = 1.5 cents -> 2, and
    #    interval 2 is 2500 Wh = 2.5 cents -> 2 (half to even both ways). credit_cents = 2 + 2 = 4; half up gives 5.
    half = write(work / "half", {
        "events": [("OWN-0401", "2026-12-05T10:00:00+00:00", 2, 0)],
        "sites": [site("OWN-0401", "H-1", base=1000)],
        "offers": [("OWN-0401-H-1-A", "OWN-0401", "H-1", [1500, 2500])]})
    got = run(half)
    report("credit_cents of OWN-0401", north(got, "OWN-0401")["credit_cents"], 4)

    check = self_check()
    shipped = check["Inputs"](DATA)
    docs = check["documents"](Path(PROGRAM).parent)
    first = shipped.season()[0]
    ini = configparser.ConfigParser()
    ini.read(DATA / "program.ini", encoding="utf-8")
    region_of = {k.upper(): v for k, v in ini["region_codes"].items()}

    # 5. Pools: the first event of the season carries nothing in, so its funded pool is pool - credit_cents. Lower
    #    one of its event-region pools to credit_cents + two sevenths of its claims, so the claims no longer fit and
    #    the funded cents are shared by largest remainder.
    region = max((r for (e, r) in docs if e == first), key=lambda r: (len(weights(shipped, first, r)), r))
    weight = weights(shipped, first, region)
    pool = docs[(first, region)]["credit_cents"] + sum(weight.values()) * shipped.claim * 2 // 7
    pools = copy_of(work, "pools")
    lines = (pools / "pools.txt").read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if not line.startswith("#") and line.strip() and line[0:10].strip() == first \
                and region_of.get(line[10:14].strip().upper()) == region:
            bump_receipt(pools, "pools.txt", "pool_cents", pool - int(line[14:26]))
            lines[i] = line[:14] + f"{pool:>12}" + line[26:]
    (pools / "pools.txt").write_text("".join(lines), encoding="utf-8")
    run(pools)
    inp, out = check["Inputs"](pools), check["documents"](pools.parent / "pools-out")
    event = out[(first, region)]
    funded = max(0, pool - event["credit_cents"])
    altered(f"grants of {first} {region} with its pool lowered to {pool} cents",
            dict(sorted((g["beneficiary_id"], g["cents"]) for g in event["grants"])),
            dict(sorted(grant_cents(check, inp, funded, weights(inp, first, region)).items())))

    # 6. Allowance: lower the allowance that one chosen offer of the first event draws on (following draws_from)
    #    to one tick below that offer's relief ticks, so the offer is no longer a candidate.
    oid = next(o for (e, r), ev in sorted(docs.items()) if e == first for o in ev["selected_offer_ids"])
    holder = shipped.offer_site[oid][1]
    while holder in shipped.draws:
        holder = shipped.draws[holder]
    need = sum(shipped.relief[oid].values())
    allow = copy_of(work, "allowance")
    lines = (allow / "site_allowances.tsv").read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        cells = line.rstrip("\n").split("\t")
        if not line.startswith("#") and cells[0] == holder:
            bump_receipt(allow, "site_allowances.tsv", "allowance_ticks", need - 1 - int(cells[1]))
            lines[i] = "\t".join([cells[0], str(need - 1)] + cells[2:]) + "\n"
    (allow / "site_allowances.tsv").write_text("".join(lines), encoding="utf-8")
    run(allow)
    out = check["documents"](allow.parent / "allowance-out")
    altered(f"{oid} still selected with allowance {holder} lowered to {need - 1} ticks",
            any(oid in ev["selected_offer_ids"] for ev in out.values()), False)

    # 7. Uplift: raise the uplift of the first event until a chosen offer's composed rate is above its card's cap.
    (eid, region), _ = next(item for item in sorted(docs.items()) if item[0][0] == first and item[1]["selected_offer_ids"])
    chosen = shipped.sites[shipped.offer_site[docs[(eid, region)]["selected_offer_ids"][0]]]
    uplift = max(int(shipped.events[eid]["uplift_millicents_per_kwh"]) + 1,
                 chosen["cap"] - chosen["start"] - chosen["adder"] + 100)
    rated = copy_of(work, "uplift")
    events = json.loads((rated / "events.json").read_text(encoding="utf-8"))
    for e in events:
        if e["event_id"] == eid:
            e["uplift_millicents_per_kwh"] = uplift
    (rated / "events.json").write_text(json.dumps(events, indent=1) + "\n", encoding="utf-8")
    run(rated)
    inp, out = check["Inputs"](rated), check["documents"](rated.parent / "uplift-out")
    altered(f"credit_cents of {eid} {region} with its uplift raised to {uplift}", out[(eid, region)]["credit_cents"],
            credit_of(check, inp, eid, out[(eid, region)]["selected_offer_ids"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PYEOF
