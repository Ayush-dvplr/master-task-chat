#!/bin/bash
# Oracle entrypoint for 12ce5ca8-825b-58b3-a3a5-3b19e34482a6.
#
# Installs the aggregator, resolves the dependency chain, measures the relative
# median against a rescan baseline defined here (outside the aggregator, so the
# delivered module stays free of clock reads), writes the ten artifacts, and
# cross-checks them against each other before finishing.
set -euo pipefail

# Loading /app/out/optimize.py below writes a bytecode cache beside it, which the
# stray-file check in step 5 would then reject. Keep the delivered output tree to
# exactly the ten declared artifacts.
export PYTHONDONTWRITEBYTECODE=1

mkdir -p /app/out

echo "[1/7] reading the written contract at /app/data/schema.md"
cat /app/data/schema.md

echo "[2/7] installing the aggregator at /app/out/optimize.py"
cp /solution/solve.py /app/out/optimize.py

echo "[3/7] resolving the dependency chain and reporting the authoritative inputs"
python3 - <<'PY'
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("delivered_optimize", "/app/out/optimize.py")
optimize = importlib.util.module_from_spec(spec)
spec.loader.exec_module(optimize)

resolved = optimize.resolve_inputs(Path("/app/data"))
print("resolved authoritative inputs:", resolved["provenance"])
print("active coefficient label:", resolved["coefficients"]["label"])
print("rows in the authoritative corpus:", len(resolved["events"]))

# Section 2 by hand for the coeff role: only active rows compete, and the
# generation is compared as an integer ("11" beats "3" although "3" > "11" as text).
catalog = optimize.read_catalog_pointer(Path("/app/data"))
ledger = optimize.read_binding_ledger(Path("/app/data"), optimize.read_ledger_pointer(Path("/app/data"), catalog))
for row in ledger:
    if row["role"] == "coeff":
        print("  coeff ledger row: generation=%-3s state=%-10s file=%s" % (row["generation"], row["state"], row["file"]))
active = [row for row in ledger if row["role"] == "coeff" and row["state"] == "active"]
print("  highest active integer generation:", max(int(row["generation"]) for row in active))
for row in ledger:
    if row["role"] == "meterseeds":
        print("  meterseeds ledger row: generation=%-3s state=%-10s file=%s" % (row["generation"], row["state"], row["file"]))
seeds_active = [row for row in ledger if row["role"] == "meterseeds" and row["state"] == "active"]
print("  meterseeds winner by integer generation:", max(seeds_active, key=lambda row: int(row["generation"]))["file"])

# Section 4b: dedicated sources win over the coefficient file's own copies.
raw_coefficients = optimize.read_json_file(Path("/app/data") / optimize.pick_active_generation(ledger, "coeff"))
print("  region_offsets: coefficient file says %s; region_registry.sqlite active rows say %s (registry wins)" % (
    raw_coefficients["region_offsets"], resolved["coefficients"]["region_offsets"]))
import zipfile
import xml.etree.ElementTree as ElementTree
with zipfile.ZipFile("/app/data/" + optimize.pick_active_generation(ledger, "tariff")) as book:
    workbook = ElementTree.fromstring(book.read("xl/workbook.xml"))
print("  tariff book sheets:", [sheet.get("name") for sheet in workbook.iter(optimize.SPREADSHEET + "sheet")],
      "-> tiers_2025Q4 is the latest non-draft tiers_<year>Q<quarter> sheet")
print("  tariff_tiers: coefficient file says %s; latest non-draft tiers_<year>Q<quarter> sheet says %s (sheet wins; tiers_2026Q1_draft and tariff_schedule_2025.md are ignored)" % (
    raw_coefficients["tariff_tiers"], resolved["coefficients"]["tariff_tiers"]))
print("  seed overrides after the docx addendum: %d accounts" % len(resolved["meter_seed_overrides"]))
print("  void_flag from admission_policy.yaml: %r (the draft policy's 'void' is ignored)" % resolved["coefficients"]["void_flag"])
for role in optimize.CONFIG_ROLES:
    print("  resolved %-10s -> %s" % (role, sorted(resolved["configs"][role])))

print("  canonical optional overlays:", [key for key in (
    "account_aliases", "region_aliases", "kind_aliases", "flag_aliases",
    "account_unit_divisor", "account_tariff_tiers",
    "account_tariff_credit_wh", "meter_reset_flag")
    if key in resolved["coefficients"]])
PY

echo "[4/7] inspecting raw shard rows and probing the row-admission rules"
python3 - <<'PY'
import collections
import csv
import importlib.util
import json
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location("delivered_optimize", "/app/out/optimize.py")
optimize = importlib.util.module_from_spec(spec)
spec.loader.exec_module(optimize)

resolved = optimize.resolve_inputs(Path("/app/data"))
raw = resolved["events"]
kind_weights = resolved["coefficients"]["kind_weights"]

# Concrete irregularities in the raw shards that section 3a has to absorb.
id_counts = collections.Counter(row["id"].strip().lower() for row in raw)
repeated = sorted((i for i, n in id_counts.items() if n > 1), key=optimize.id_number)
unknown_kinds = sorted({row["kind"].strip().lower() for row in raw} - set(kind_weights))
padded = [row["id"] for row in raw if any(row[c] != row[c].strip() for c in optimize.EVENT_COLUMNS)]
recased = [row["id"] for row in raw if row["account"].strip() != row["account"].strip().upper()
           or row["kind"].strip() != row["kind"].strip().lower()]
print("repeated ids: %d, first few %s" % (len(repeated), repeated[:5]))
print("kinds outside kind_weights: %s" % unknown_kinds)
print("rows with stray whitespace: %d, e.g. %s" % (len(padded), padded[:3]))
print("rows with off-case account or kind: %d, e.g. %s" % (len(recased), recased[:3]))
for name in ("seg_part_02.csv", "seg_part_05.csv", "seg_part_08.csv"):
    head = (Path("/app/data") / name).read_bytes()[:120]
    print("%s starts %r" % (name, head))

# Probe: an unknown-kind row first, then a valid-kind row reusing its id.
scratch = Path(tempfile.mkdtemp(prefix="rollup_probe_"))
probe_events = scratch / "probe_events.csv"
probe_events.write_text(
    "id,ts,account,region,kind,amount,units,latency_ms,flag,meter,energy_wh\n"
    "e1,1100,A01,north,omega,5,1,0,ok,100,93\n"
    "e1,1200,A01,north,alpha,5,1,0,ok,200,100\n"
    "e2,1300,A01,north,alpha,5,1,0,ok,300,100\n",
    encoding="utf-8",
)
probe_rules = scratch / "probe_rules.json"
probe_rules.write_text(json.dumps({
    "label": "PROBE", "window_start": 1000, "window_end": 9000,
    "kind_weights": {"alpha": 3}, "region_offsets": {"north": 11}, "flag_penalties": {"ok": 0},
    "top_n": 3, "meter_modulus": 20000, "meter_seed": 7, "tariff_bps": 1450, "unit_divisor": 1000,
}), encoding="utf-8")
probe = optimize.aggregate(str(probe_events), str(probe_rules))
print("probe (quarantined e1, then e1 re-sent with a valid kind, then e2): event_count=%d" % probe["event_count"])
if probe["event_count"] != 1:
    raise SystemExit("the re-sent id of a quarantined row was admitted")

# Further probes, each on a hand-built file that isolates one contract rule.
HEADER = "id,ts,account,region,kind,amount,units,latency_ms,flag,meter,energy_wh\n"
BASE_RULES = {
    "label": "PROBE", "window_start": 1000, "window_end": 9000,
    "kind_weights": {"alpha": 3}, "region_offsets": {"north": 11}, "flag_penalties": {"ok": 0},
    "top_n": 3, "meter_modulus": 20000, "meter_seed": 0, "tariff_bps": 1450, "unit_divisor": 1000,
    "void_flag": "void",
}


def run_probe(name, events_text, extra_rules=None):
    events = scratch / (name + "_events.csv")
    events.write_text(events_text, encoding="utf-8")
    rules = scratch / (name + "_rules.json")
    rules.write_text(json.dumps(dict(BASE_RULES, **(extra_rules or {}))), encoding="utf-8")
    return optimize.aggregate(str(events), str(rules))


# A void-looking first occurrence is ordinary. The later non-void duplicate is
# the replay, so e1 and e2 both remain in the window.
void_first = run_probe("void_first", HEADER
                       + "e1,1500,A01,north,alpha,1,1,0,void,100,0\n"
                       + "e1,1600,A01,north,alpha,9,1,0,ok,200,0\n"
                       + "e2,1700,A01,north,alpha,1,1,0,ok,250,0\n")
print("probe void-marked first occurrence: event_count=%d (first occurrence wins, so 2)" %
      void_first["event_count"])
if void_first["event_count"] != 2:
    raise SystemExit("a void-marked first occurrence was incorrectly treated as a notice")

# A reset before the window anchors the first in-window delta without adding
# pre-window usage. The two window readings contribute 100 Wh each.
cross_window_reset = run_probe("cross_window_reset", HEADER
                               + "e1,900,A01,north,alpha,1,1,0,reset,900,0\n"
                               + "e2,1500,A01,north,alpha,1,1,0,ok,1000,0\n"
                               + "e3,1600,A01,north,alpha,1,1,0,ok,1100,0\n",
                               {"meter_reset_flag": "reset"})
print("probe cross-window meter reset: account_usage_wh=%s (reset anchor gives 200)" %
      cross_window_reset["account_usage_wh"])
if cross_window_reset["account_usage_wh"] != {"A01": 200}:
    raise SystemExit("the pre-window reset did not anchor the window walk")


# A three-way score tie cut by top_n keeps the lexical first two accounts.
top_tie = run_probe("top_tie_cutoff", HEADER
                    + "e1,1500,C03,north,alpha,1,1,0,ok,10,0\n"
                    + "e2,1500,A01,north,alpha,1,1,0,ok,10,0\n"
                    + "e3,1500,B02,north,alpha,1,1,0,ok,10,0\n",
                    {"top_n": 2})
print("probe three-way top-account tie at top_n=2: top_accounts=%s" % top_tie["top_accounts"])
if top_tie["top_accounts"] != [["A01", 14], ["B02", 14]]:
    raise SystemExit("top_n did not retain the lexical first accounts across a tie")

# Two pre-window rows disagree about timestamp and file order. The second row
# in the file, with meter 400, is the anchor, so the window contributes 50 Wh.
competing_anchors = run_probe("competing_anchors", HEADER
                              + "e1,900,A01,north,alpha,1,1,0,ok,100,0\n"
                              + "e2,500,A01,north,alpha,1,1,0,ok,400,0\n"
                              + "e3,1500,A01,north,alpha,1,1,0,ok,450,0\n")
print("probe competing pre-window anchors: account_usage_wh=%s (file-order anchor 400 gives 50)" %
      competing_anchors["account_usage_wh"])
if competing_anchors["account_usage_wh"] != {"A01": 50}:
    raise SystemExit("the pre-window anchor was selected by timestamp instead of file order")

# The same rollover readings use the global modulus for A01 and B02's override.
moduli = run_probe("account_and_global_moduli", HEADER
                   + "e1,1500,A01,north,alpha,1,1,0,ok,20,0\n"
                   + "e2,1500,B02,north,alpha,1,1,0,ok,20,0\n",
                   {"meter_seed": 90, "meter_modulus": 100,
                    "account_meter_modulus": {"B02": 200}})
print("probe account and global moduli: account_usage_wh=%s (A01=30, B02=130)" %
      moduli["account_usage_wh"])
if moduli["account_usage_wh"] != {"A01": 30, "B02": 130}:
    raise SystemExit("the account-specific modulus was not isolated from the global modulus")

# B02's unsorted account-specific profile replaces the global profile. Both
# accounts cross 100 Wh: A01 costs 25 cents and B02 costs 45 cents by hand.
account_tiers = run_probe("account_tier_override", HEADER
                          + "e1,1500,A01,north,alpha,1,1,0,ok,150,0\n"
                          + "e2,1500,B02,north,alpha,1,1,0,ok,150,0\n",
                          {"tariff_tiers": [[0, 1000], [100, 3000]],
                           "account_tariff_tiers": {"B02": [[100, 5000], [0, 2000]]}})
print("probe account tier override: account_cost_cents=%s (hand-worked A01=25, B02=45)" %
      account_tiers["account_cost_cents"])
if account_tiers["account_cost_cents"] != {"A01": 25, "B02": 45}:
    raise SystemExit("the account-specific unsorted tier profile was not applied")


# Timestamps move backwards, but cumulative readings advance in corpus order.
corpus_order = run_probe("corpus_order", HEADER + "e10,2000,A01,north,alpha,1,1,0,ok,100,0\n"
                         "e9,1500,A01,north,alpha,1,1,0,ok,300,0\n")
print("probe backwards timestamps in corpus order: account_usage_wh=%s (100 then 300 gives 300)" % corpus_order["account_usage_wh"])
if corpus_order["account_usage_wh"] != {"A01": 300}:
    raise SystemExit("meter walk does not follow admitted corpus order")

# Override key written loosely; the account has no pre-window row.
loose = run_probe("loose_key", HEADER + "e1,1500,A01,north,alpha,1,1,0,ok,500,0\n",
                  {"meter_seed_overrides": {" a01 ": 400}})
print("probe override key ' a01 ': account_usage_wh=%s (seed 400 gives 100)" % loose["account_usage_wh"])
if loose["account_usage_wh"] != {"A01": 100}:
    raise SystemExit("loose override key was not normalised")

# Reordered header with an extra column.
reordered = run_probe("reordered", "meter,kind,id,ts,account,region,amount,units,latency_ms,flag,energy_wh,extra\n"
                      "200,alpha,e1,1500,A01,north,2,3,10,ok,0,x\n")
print("probe reordered header: event_count=%d account_totals=%s" % (reordered["event_count"], reordered["account_totals"]))
if reordered["event_count"] != 1 or reordered["account_totals"] != {"A01": 2 * 3 * 3 + 11 - 1}:
    raise SystemExit("reordered header was read by position")

# Pre-window anchor: the row at ts 500 seeds the walk, so usage is 700 - 600.
anchored = run_probe("prewindow", HEADER + "e1,500,A01,north,alpha,1,1,0,ok,600,0\n"
                     "e2,1500,A01,north,alpha,1,1,0,ok,700,0\n", {"meter_seed_overrides": {"A01": 50}})
print("probe pre-window anchor: account_usage_wh=%s (anchor 600 gives 100)" % anchored["account_usage_wh"])
if anchored["account_usage_wh"] != {"A01": 100}:
    raise SystemExit("the pre-window reading did not anchor the walk")

# Void notice for a pre-window anchor: e1 is withdrawn, so the walk starts from
# the override 50 instead of e1's meter 600, and e1 scores nothing.
voided = run_probe("void_anchor", HEADER + "e1,500,A01,north,alpha,1,1,0,ok,600,0\n"
                   "e2,1500,A01,north,alpha,1,1,0,ok,700,0\n"
                   "e1,500,A01,north,alpha,1,1,0,VOID,600,0\n", {"meter_seed_overrides": {"A01": 50}})
print("probe void notice on the pre-window anchor: account_usage_wh=%s (override 50 gives 650)" % voided["account_usage_wh"])
if voided["account_usage_wh"] != {"A01": 650}:
    raise SystemExit("the void notice did not withdraw the anchor row")

# Tier position: pre-window usage 60 (seed 0 -> 60) puts the window's 50 Wh at [60, 110).
positioned = run_probe("tier_position", HEADER + "e1,500,A01,north,alpha,1,1,0,ok,60,0\n"
                       "e2,1500,A01,north,alpha,1,1,0,ok,110,0\n", {"tariff_tiers": [[0, 1000], [100, 3000]]})
print("probe tier position: account_cost_cents=%s, by hand half_up(40*1000+10*3000, 10000) = 7" % positioned["account_cost_cents"])
if positioned["account_cost_cents"] != {"A01": 7}:
    raise SystemExit("the window was billed from tier zero instead of its cumulative position")

# resolve_rules on an edited copy of the data: change one registry offset and
# confirm the returned region_offsets carries the edit.
import shutil
import sqlite3
edited = Path(tempfile.mkdtemp(prefix="rollup_edited_")) / "data"
shutil.copytree("/app/data", edited)
connection = sqlite3.connect(str(edited / "region_registry.sqlite"))
connection.execute("UPDATE region_offsets SET offset = 99 WHERE region = 'west' AND state = 'active'")
connection.commit()
connection.close()
edited_rules = optimize.resolve_rules(str(edited), "peak")
print("probe resolve_rules on an edited copy: west offset %d (edit set 99)" % edited_rules["region_offsets"]["west"])
if edited_rules["region_offsets"]["west"] != 99:
    raise SystemExit("resolve_rules ignored the edited registry")

# Half-open window: a row at ts == window_end (9000) is left out.
at_end = run_probe("window_end", HEADER + "e1,1500,A01,north,alpha,1,1,0,ok,100,0\n"
                   "e2,9000,A01,north,alpha,1,1,0,ok,200,0\n")
print("probe row at ts == window_end: event_count=%d (half-open gives 1)" % at_end["event_count"])
if at_end["event_count"] != 1:
    raise SystemExit("the window end was treated as inclusive")

# Tiers listed out of order; by hand 150 Wh = 100*1000 + 50*3000 -> half_up(250000, 10000) = 25.
unsorted = run_probe("unsorted_tiers", HEADER + "e1,1500,A01,north,alpha,1,1,0,ok,150,0\n",
                     {"tariff_tiers": [[100, 3000], [0, 1000]]})
print("probe unsorted tiers: account_cost_cents=%s, by hand 25" % unsorted["account_cost_cents"])
if unsorted["account_cost_cents"] != {"A01": 25}:
    raise SystemExit("tariff tiers were applied unsorted")

# The script form prints exactly what aggregate returns for the same files.
import subprocess
cli = subprocess.run(["python3", "/app/out/optimize.py", str(scratch / "unsorted_tiers_events.csv"),
                      str(scratch / "unsorted_tiers_rules.json")], check=True, capture_output=True, text=True)
print("probe CLI vs aggregate: identical=%s" % (json.loads(cli.stdout) == unsorted))
if json.loads(cli.stdout) != unsorted or cli.stdout.strip() != json.dumps(unsorted, sort_keys=True):
    raise SystemExit("the CLI output differs from aggregate")

# Hand check of the block tariff for one real account of the visible window.
coefficients = resolved["coefficients"]
tiers = sorted((int(start), int(bps)) for start, bps in coefficients["tariff_tiers"])
corpus_csv = scratch / "corpus.csv"
with corpus_csv.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle)
    writer.writerow(optimize.EVENT_COLUMNS)
    for row in raw:
        writer.writerow([row[c] for c in optimize.EVENT_COLUMNS])
rules_json = scratch / "rules_visible.json"
rules_json.write_text(json.dumps(optimize.scenario_rules(
    coefficients, coefficients["scenario_windows"]["visible"], resolved["meter_seed_overrides"])), encoding="utf-8")
visible = optimize.aggregate(str(corpus_csv), str(rules_json))
account = max(visible["account_usage_wh"], key=lambda a: (visible["account_usage_wh"][a], a))
usage = visible["account_usage_wh"][account]
# Cumulative tier position: walk the account's admitted pre-window rows from its
# override (or meter_seed) to get pre_wh; the window then occupies [pre_wh, pre_wh + usage).
window_start = coefficients["scenario_windows"]["visible"][0]
overrides = optimize.normalised_seed_overrides({"meter_seed_overrides": resolved["meter_seed_overrides"]})
admitted_rows = optimize.admit_rows(raw, kind_weights, coefficients["void_flag"], coefficients)["admitted"]
before = [r for r in admitted_rows if r["account"] == account and int(r["ts"]) < window_start]
pre_wh = 0
previous = overrides.get(account, int(coefficients["meter_seed"]))
for row in before:
    pre_wh += (int(row["meter"]) - previous) % int(coefficients["meter_modulus"])
    previous = int(row["meter"])
low, high = pre_wh, pre_wh + usage
bounds = [start for start, _ in tiers[1:]] + [None]
tier_sum = 0
for (start, bps), upper in zip(tiers, bounds):
    billed = max(0, (high if upper is None else min(high, upper)) - max(low, start))
    print("  %s tier from %d Wh at %d bps: %d Wh" % (account, start, bps, billed))
    tier_sum += billed * bps
by_hand = optimize.round_half_up(tier_sum, 10000)
print("hand check %s: pre_wh=%d usage_wh=%d tier_sum=%d cents=%d aggregate=%d" % (
    account, pre_wh, usage, tier_sum, by_hand, visible["account_cost_cents"][account]))
if by_hand != visible["account_cost_cents"][account]:
    raise SystemExit("the hand-computed tier split disagrees with aggregate")

# Demonstrate the data-backed ordering trap on one real account, independently
# of aggregate: its event timestamps move backwards while its meter advances.
order_account = None
for candidate in sorted(visible["account_usage_wh"]):
    candidate_rows = [r for r in admitted_rows if r["account"] == candidate
                      and window_start <= int(r["ts"]) < coefficients["scenario_windows"]["visible"][1]]
    backwards = next(((left, right) for left, right in zip(candidate_rows, candidate_rows[1:])
                      if int(right["ts"]) < int(left["ts"])), None)
    if backwards is not None:
        order_account = candidate
        order_rows = candidate_rows
        order_pair = backwards
        break
if order_account is None:
    raise SystemExit("canonical corpus has no backwards-timestamp meter pair")
order_before = [r for r in admitted_rows if r["account"] == order_account and int(r["ts"]) < window_start]
order_previous = int(order_before[-1]["meter"]) if order_before else overrides.get(order_account, int(coefficients["meter_seed"]))
order_modulus = optimize.account_integer_map(coefficients, "account_meter_modulus").get(
    order_account, int(coefficients["meter_modulus"]))
reset_flag = str(coefficients.get("meter_reset_flag") or "").strip().lower()
order_usage = 0
for row in order_rows:
    if row["flag"] != reset_flag:
        order_usage += (int(row["meter"]) - order_previous) % order_modulus
    order_previous = int(row["meter"])
print("real corpus-order check %s: consecutive timestamps %s -> %s move backwards; usage_wh=%d artifact=%d" % (
    order_account, order_pair[0]["ts"], order_pair[1]["ts"], order_usage,
    visible["account_usage_wh"][order_account]))
if order_usage != visible["account_usage_wh"][order_account]:
    raise SystemExit("the real corpus-order hand check disagrees with the artifact")

# Zero-output calibration: usage 10 Wh and energy 0 kWh. half_up(10, D) is 0
# from D = 21 upward, so the search must continue past usage_wh and stop at 21.
zero_output = run_probe("zero_output_calibration", HEADER + "e1,1500,A01,north,alpha,1,1,0,ok,10,0\n",
                        {"unit_divisor": None,
                         "calibration": {"energy": [{"usage_wh": 10, "energy_kwh": 0}], "cost": []}})
print("probe zero-output calibration: recovered divisor %d (smallest D with half_up(10, D) == 0 is 21)" %
      optimize.recover_unit_divisor({"unit_divisor": None,
                                     "calibration": {"energy": [{"usage_wh": 10, "energy_kwh": 0}]}}))
if optimize.recover_unit_divisor({"unit_divisor": None,
                                  "calibration": {"energy": [{"usage_wh": 10, "energy_kwh": 0}]}}) != 21:
    raise SystemExit("divisor recovery stopped at usage_wh instead of finding 21")
print("probe zero-output calibration: account_energy_kwh=%s" % zero_output["account_energy_kwh"])

# Exact and overlapping wildcard seeds on accounts with no pre-window reading:
# A003 takes its exact key, A004 the longer wildcard A00*, A051 the wildcard A0*.
wildcard = run_probe("wildcard_seed", HEADER
                     + "e1,1500,A003,north,alpha,1,1,0,ok,5000,0\n"
                     + "e2,1500,A004,north,alpha,1,1,0,ok,5000,0\n"
                     + "e3,1500,A051,north,alpha,1,1,0,ok,5000,0\n",
                     {"meter_seed_overrides": {"A0*": 1000, "A00*": 3000, "A003": 4500}})
print("probe exact and wildcard seeds: account_usage_wh=%s (A003 seed 4500 -> 500, A004 seed 3000 -> 2000, "
      "A051 seed 1000 -> 4000)" % wildcard["account_usage_wh"])
if wildcard["account_usage_wh"] != {"A003": 500, "A004": 2000, "A051": 4000}:
    raise SystemExit("exact or longest-prefix wildcard seeds were not applied")

# Held-back tier rate above one million bps: 1 Wh costing 101 cents needs a rate
# of at least 1005000 bps, so a search capped at one million would fail here.
large_rate = run_probe("large_heldback_rate", HEADER + "e1,1500,A01,north,alpha,1,1,0,ok,1,0\n",
                       {"tariff_tiers": [[0, None]],
                        "calibration": {"energy": [], "cost": [{"pre_wh": 0, "usage_wh": 1, "cost_cents": 101}]}})
print("probe held-back tier rate above one million bps: account_cost_cents=%s (control demands 101)" %
      large_rate["account_cost_cents"])
if large_rate["account_cost_cents"] != {"A01": 101}:
    raise SystemExit("the held-back tier rate search is capped below the matching rate")

# Edited copies of the xlsx tariff book and the docx seed addendum. Each copy
# changes the package layout or one addendum row, then resolve_rules runs on it.
import re
import zipfile


def rewrite_zip(path, rewrite):
    with zipfile.ZipFile(path) as source:
        parts = {name: source.read(name) for name in source.namelist()}
    for name in list(parts):
        parts[name] = rewrite(name, parts[name])
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as target:
        for name, data in parts.items():
            target.writestr(name, data)


def edited_copy(prefix):
    root = Path(tempfile.mkdtemp(prefix=prefix)) / "data"
    shutil.copytree("/app/data", root)
    return root


shipped_tiers = optimize.resolve_rules("/app/data", "peak")["tariff_tiers"]

absolute = edited_copy("rollup_xlsx_absolute_")
rewrite_zip(absolute / "tariff_book.xlsx", lambda name, data: data.replace(
    b'Target="worksheets/', b'Target="/xl/worksheets/') if name == "xl/_rels/workbook.xml.rels" else data)
absolute_tiers = optimize.resolve_rules(str(absolute), "peak")["tariff_tiers"]
print("probe xlsx absolute relationship targets (/xl/worksheets/...): tariff_tiers=%s" % absolute_tiers)
if absolute_tiers != shipped_tiers:
    raise SystemExit("an absolute xlsx relationship target changed the resolved tiers")

unreferenced = edited_copy("rollup_xlsx_no_r_")
rewrite_zip(unreferenced / "tariff_book.xlsx", lambda name, data: re.sub(
    rb'<c r="[A-Z]+[0-9]+"', b"<c", data) if name.startswith("xl/worksheets/") else data)
unreferenced_tiers = optimize.resolve_rules(str(unreferenced), "peak")["tariff_tiers"]
print("probe xlsx cells without the r attribute: tariff_tiers=%s" % unreferenced_tiers)
if unreferenced_tiers != shipped_tiers:
    raise SystemExit("cells without an r coordinate changed the resolved tiers")

removal = edited_copy("rollup_addendum_remove_")
set_then_remove = (
    b'<w:tr><w:tc><w:p><w:r><w:t xml:space="preserve">A081</w:t></w:r></w:p></w:tc>'
    b'<w:tc><w:p><w:r><w:t xml:space="preserve">6000</w:t></w:r></w:p></w:tc></w:tr>'
    b'<w:tr><w:tc><w:p><w:r><w:t xml:space="preserve">a081</w:t></w:r></w:p></w:tc>'
    b'<w:tc><w:p><w:r><w:t xml:space="preserve">remove</w:t></w:r></w:p></w:tc></w:tr></w:tbl>')
rewrite_zip(removal / "meter_seed_addendum.docx", lambda name, data: data.replace(
    b"</w:tbl>", set_then_remove) if name == "word/document.xml" else data)
removal_seeds = optimize.resolve_rules(str(removal), "peak")["meter_seed_overrides"]
print("probe addendum sets A081 then removes it: A081 present=%s, wildcard A08*=%s" % (
    "A081" in removal_seeds, removal_seeds.get("A08*")))
if "A081" in removal_seeds or removal_seeds.get("A08*") != 4321:
    raise SystemExit("a later addendum remove row did not delete the exact override")
PY

echo "[5/7] measuring the relative median against a rescan baseline, then writing artifacts"
python3 - <<'PY'
import csv
import importlib.util
import json
import statistics
import tempfile
import time
from pathlib import Path

spec = importlib.util.spec_from_file_location("delivered_optimize", "/app/out/optimize.py")
optimize = importlib.util.module_from_spec(spec)
spec.loader.exec_module(optimize)


def rescan_baseline(events_path, rules_path):
    """Straightforward section 5 implementation, deliberately unoptimised.

    It walks the windowed rows again for every output group it fills, which is the
    per-key rescan the task asks the aggregator to beat. Written here rather than
    in optimize.py so that the delivered module never reads a clock.
    """
    rules = json.loads(Path(rules_path).read_text(encoding="utf-8"))
    window_start = int(rules["window_start"])
    window_end = int(rules["window_end"])
    modulus = int(rules["meter_modulus"])
    seed = int(rules["meter_seed"])

    def clean_map(name, upper=False):
        clean = (lambda value: str(value).strip().upper()) if upper else (lambda value: str(value).strip().lower())
        return {clean(source): clean(target) for source, target in (rules.get(name) or {}).items()}

    account_aliases = clean_map("account_aliases", True)
    region_aliases = clean_map("region_aliases")
    kind_aliases = clean_map("kind_aliases")
    flag_aliases = clean_map("flag_aliases")
    kind_weights = {str(key).strip().lower(): int(value)
                    for key, value in rules["kind_weights"].items()}
    void_flag = str(rules.get("void_flag") or "").strip().lower()
    void_flag = flag_aliases.get(void_flag, void_flag)

    def normalise(raw):
        row = {column: str(raw.get(column) or "").strip()
               for column in optimize.EVENT_COLUMNS}
        row["id"] = row["id"].lower()
        row["account"] = account_aliases.get(row["account"].upper(), row["account"].upper())
        row["region"] = region_aliases.get(row["region"].lower(), row["region"].lower())
        row["kind"] = kind_aliases.get(row["kind"].lower(), row["kind"].lower())
        row["flag"] = flag_aliases.get(row["flag"].lower(), row["flag"].lower())
        return row

    with Path(events_path).open(newline="", encoding="utf-8-sig") as handle:
        rows = [normalise(raw) for raw in csv.DictReader(handle)]
    seen = set()
    candidates = {}
    notices = set()
    for position, row in enumerate(rows):
        if row["id"] in seen:
            if void_flag and row["flag"] == void_flag:
                notices.add(row["id"])
            continue
        seen.add(row["id"])
        candidates[row["id"]] = (position, row)
    admitted = [item for row_id, item in candidates.items()
                if item[1]["kind"] in kind_weights and row_id not in notices]
    admitted = [row for _position, row in sorted(admitted)]
    def base_score(row):
        return (
            int(row["amount"]) * int(row["units"]) * int(rules["kind_weights"][row["kind"]])
            + int(rules["region_offsets"].get(row["region"], 0))
            - int(rules["flag_penalties"].get(row["flag"], 0))
            - int(row["latency_ms"]) // 10
        )

    settled = []
    for row in admitted:
        timestamp = int(row["ts"])
        if timestamp >= window_end:
            continue
        score = base_score(row)
        if timestamp >= window_start:
            settled.append((row, score))
    rows = [row for row, _score in settled]

    accounts = sorted({r["account"] for r in rows})
    regions = sorted({r["region"] for r in rows})
    kinds = sorted({r["kind"] for r in rows})
    flags = sorted({r["flag"] for r in rows})

    # One fresh walk over the windowed rows per output key: the bottleneck itself.
    account_totals = {k: sum(score for r, score in settled if r["account"] == k) for k in accounts}
    region_totals = {k: sum(score for r, score in settled if r["region"] == k) for k in regions}
    kind_totals = {k: sum(score for r, score in settled if r["kind"] == k) for k in kinds}
    flag_counts = {k: sum(1 for r in rows if r["flag"] == k) for k in flags}

    checksum = 0
    for position, (row, score) in enumerate(settled, 1):
        checksum = (checksum * 1315423911 + score * position + optimize.id_number(row["id"])) & 0xFFFFFFFF

    usage_wh = {}
    for account in accounts:
        series = [r for r in rows if r["account"] == account]
        before = [r for r in admitted if r["account"] == account and int(r["ts"]) < window_start]
        previous = int(before[-1]["meter"]) if before else optimize.seed_for_account(account, rules)
        account_modulus = optimize.account_integer_map(rules, "account_meter_modulus").get(account, modulus)
        reset_flag = str(rules.get("meter_reset_flag") or "").strip().lower()
        usage = 0
        for row in series:
            if row["flag"] != reset_flag:
                usage += (int(row["meter"]) - previous) % account_modulus
            previous = int(row["meter"])
        usage_wh[account] = usage

    def tiered(account):
        before = [r for r in admitted if r["account"] == account and int(r["ts"]) < window_start]
        pre = 0
        previous = optimize.seed_for_account(account, rules)
        account_modulus = optimize.account_integer_map(rules, "account_meter_modulus").get(account, modulus)
        reset_flag = str(rules.get("meter_reset_flag") or "").strip().lower()
        for row in before:
            if row["flag"] != reset_flag:
                pre += (int(row["meter"]) - previous) % account_modulus
            previous = int(row["meter"])
        credit = optimize.account_integer_map(rules, "account_tariff_credit_wh").get(account, 0)
        return optimize.tiered_cost_cents(
            usage_wh[account], optimize.account_tariff_tiers(rules, account), max(0, pre - credit))
    ranked = sorted(account_totals.items(), key=lambda kv: (-kv[1], kv[0]))
    return {
        "label": str(rules["label"]),
        "window": [window_start, window_end],
        "event_count": len(rows),
        "account_totals": account_totals,
        "region_totals": region_totals,
        "kind_totals": kind_totals,
        "flag_counts": flag_counts,
        "account_usage_wh": usage_wh,
        "account_energy_kwh": {k: optimize.round_half_up(
            usage_wh[k], optimize.account_integer_map(rules, "account_unit_divisor").get(
                k, int(rules["unit_divisor"]))) for k in accounts},
        "account_cost_cents": {k: tiered(k) for k in accounts},
        "top_accounts": [[k, v] for k, v in ranked[: int(rules["top_n"])]],
        "checksum": checksum,
    }


def median_nanoseconds(engine, events, rules, repeats):
    samples = []
    outcome = None
    for _ in range(repeats):
        started = time.perf_counter_ns()
        outcome = engine(events, rules)
        samples.append(time.perf_counter_ns() - started)
    return statistics.median(samples), outcome


resolved = optimize.resolve_inputs(Path("/app/data"))
scratch = Path(tempfile.mkdtemp(prefix="rollup_bench_"))
bench_events = scratch / "bench_events.csv"
with bench_events.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle)
    writer.writerow(optimize.EVENT_COLUMNS)
    for row in resolved["events"]:
        writer.writerow([row[column] for column in optimize.EVENT_COLUMNS])

window = resolved["coefficients"]["scenario_windows"]["visible"]
bench_rules = scratch / "bench_rules.json"
bench_rules.write_text(
    json.dumps(optimize.scenario_rules(resolved["coefficients"], window, resolved["meter_seed_overrides"]), sort_keys=True),
    encoding="utf-8",
)

# One warmup call per engine keeps import and page-cache effects out of the medians.
warm_fast = optimize.aggregate(str(bench_events), str(bench_rules))
warm_slow = rescan_baseline(str(bench_events), str(bench_rules))
if warm_fast != warm_slow:
    raise SystemExit("the aggregator and the rescan baseline disagree on the same input")

ratios = []
for batch in range(3):
    slow_median, slow_result = median_nanoseconds(rescan_baseline, str(bench_events), str(bench_rules), 5)
    fast_median, fast_result = median_nanoseconds(optimize.aggregate, str(bench_events), str(bench_rules), 5)
    if slow_result != fast_result:
        raise SystemExit("the aggregator and the rescan baseline disagree under repeated calls")
    ratios.append(fast_median / slow_median)
    print("batch %d relative median %.6f" % (batch, ratios[-1]))

observed = float(round(statistics.median(ratios), 6))
ceiling = resolved["configs"]["thresholds"]["max_relative_median"]
print("observed relative median %.6f against the resolved ceiling %s" % (observed, ceiling))
if observed <= 0.0 or observed > ceiling:
    raise SystemExit("the measured relative median falls outside the resolved ceiling")

optimize.build_artifacts("/app/data", "/app/out", observed)
PY

echo "[6/7] cross-checking the artifacts against each other and against a second run"
python3 - <<'PY'
import importlib.util
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location("delivered_optimize", "/app/out/optimize.py")
optimize = importlib.util.module_from_spec(spec)
spec.loader.exec_module(optimize)
perf = Path("/app/out/perf_report.json").read_text(encoding="utf-8")
import json
second = Path(tempfile.mkdtemp(prefix="rollup_rerun_"))
optimize.build_artifacts("/app/data", str(second), json.loads(perf)["observed_relative_median"])
for first in sorted(Path("/app/out").glob("*.json")):
    same = first.read_bytes() == (second / first.name).read_bytes()
    print("  second run %-26s byte-identical=%s" % (first.name, same))
    if not same:
        raise SystemExit("artifact %s differs between runs" % first.name)
PY
python3 - <<'PY'
import json
from pathlib import Path

OUT = Path("/app/out")
EXPECTED = [
    "optimize.py",
    "scenario_visible.json",
    "scenario_peak.json",
    "scenario_steady.json",
    "scenario_burst.json",
    "scenario_latency.json",
    "perf_report.json",
    "bottleneck_analysis.json",
    "recommendations.json",
    "data_quality.json",
]

absent = [name for name in EXPECTED if not (OUT / name).is_file()]
if absent:
    raise SystemExit("artifacts never written: %s" % absent)

stray = sorted(p.name for p in OUT.iterdir() if p.name not in EXPECTED)
if stray:
    raise SystemExit("unexpected leftovers under /app/out: %s" % stray)

quality = json.loads((OUT / "data_quality.json").read_text(encoding="utf-8"))
for check in quality["scenario_checks"]:
    scenario = check["scenario"]
    artifact = json.loads((OUT / ("scenario_%s.json" % scenario)).read_text(encoding="utf-8"))
    result = artifact["result"]
    if check["checksum"] != result["checksum"]:
        raise SystemExit("checksum disagreement for scenario %s" % scenario)
    if check["event_count"] != result["event_count"]:
        raise SystemExit("event_count disagreement for scenario %s" % scenario)
    if check["unique_accounts"] != len(result["account_totals"]):
        raise SystemExit("unique_accounts disagreement for scenario %s" % scenario)
    if result["event_count"] <= 0 or not result["account_totals"]:
        raise SystemExit("empty result for scenario %s" % scenario)

perf = json.loads((OUT / "perf_report.json").read_text(encoding="utf-8"))
observed = perf["observed_relative_median"]
ceiling = perf["relative_target"]
if not isinstance(observed, float) or observed <= 0.0 or observed > ceiling:
    raise SystemExit("reported relative median %r falls outside the ceiling %r" % (observed, ceiling))

print("every scenario agrees with the data quality census across all five windows")
print("corpus rows %d: admitted %d, replayed %d, quarantined %d, withdrawn %d" % (
    quality["corpus_row_count"], quality["admitted_row_count"],
    quality["replayed_row_count"], quality["quarantined_row_count"], quality["withdrawn_row_count"]))
for check in quality["scenario_checks"]:
    print("  %-8s event_count=%d checksum=%d" % (check["scenario"], check["event_count"], check["checksum"]))
if (quality["admitted_row_count"] + quality["replayed_row_count"] + quality["quarantined_row_count"]
        + quality["withdrawn_row_count"]) != quality["corpus_row_count"]:
    raise SystemExit("admission counts do not add up to the corpus row count")
print("reported relative median %.6f against a resolved ceiling of %s" % (observed, ceiling))
print("wrote all ten artifacts under /app/out")
PY

echo "[7/7] summary"
python3 - <<'PY'
import json
from pathlib import Path

OUT = Path("/app/out")
quality = json.loads((OUT / "data_quality.json").read_text(encoding="utf-8"))
visible = json.loads((OUT / "scenario_visible.json").read_text(encoding="utf-8"))
print("authoritative inputs: %s (the active coefficient set and the active segment manifest)" % visible["source"])
print("artifacts written under /app/out")
print("corpus rows %d, admitted %d, replayed %d, quarantined %d, withdrawn %d" % (
    quality["corpus_row_count"], quality["admitted_row_count"],
    quality["replayed_row_count"], quality["quarantined_row_count"], quality["withdrawn_row_count"]))
for check in quality["scenario_checks"]:
    artifact = json.loads((OUT / ("scenario_%s.json" % check["scenario"])).read_text(encoding="utf-8"))
    print("  %-8s event_count=%d checksum=%d total account_totals=%d total account_cost_cents=%d" % (
        check["scenario"], check["event_count"], check["checksum"],
        sum(artifact["result"]["account_totals"].values()),
        sum(artifact["result"]["account_cost_cents"].values())))
PY
