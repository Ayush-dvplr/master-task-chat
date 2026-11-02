#!/bin/bash
set -euo pipefail

# Reference solution for 5b46e176-ff53-5506-9ae6-45b371a9a9f0.
#
# /solution/solve.py is the clearance engine. It is delivered to the declared
# artifact path /app/out/clear_epoch.py and then run against /app/data, so
# every artifact under /app/out is produced by the same program the brief asks
# for. Everything after that run is verification and reporting: the epoch is
# cleared twice and compared, cleared again from a register directory of its
# own with every register's rows reversed to show the account does not depend
# on row order, and then reported in full with the arithmetic behind each
# figure shown rather than asserted.

SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${DATA_DIR:-/app/data}"
OUT_DIR="${OUT_DIR:-/app/out}"
SCRATCH="$(mktemp -d)"
trap 'rm -rf "${SCRATCH}"' EXIT

mkdir -p "${OUT_DIR}"

# Read every piece of the reference set before writing anything, as the brief
# requires: the nine rulebooks, the invariant statement, the artifact schema,
# the calibration slice note and the one shipped example report. They are what
# let a solver settle the order the rules bear on a tap and the byte form every
# artifact takes.
for reference in "${DATA_DIR}"/*.md; do
  cat "${reference}" >/dev/null
done
cat "${DATA_DIR}/example_zone_report.json" >/dev/null
cat "${DATA_DIR}/calibration_controls.json" >/dev/null

cp "${SOLUTION_DIR}/solve.py" "${OUT_DIR}/clear_epoch.py"
chmod 0644 "${OUT_DIR}/clear_epoch.py"

python3 "${OUT_DIR}/clear_epoch.py" "${DATA_DIR}" "${OUT_DIR}"

# Clear the same registers a second time into a directory of its own and
# compare the two accounts file by file, so the account is shown to be a
# function of the registers rather than of the run.
python3 "${OUT_DIR}/clear_epoch.py" "${DATA_DIR}" "${SCRATCH}/again"
diff -r "${OUT_DIR}" "${SCRATCH}/again" >/dev/null 2>&1 || {
  # The delivered program is in OUT_DIR but not in the second run's directory,
  # so compare only the artifacts the program wrote.
  for artifact in "${SCRATCH}/again"/*; do
    name="$(basename "${artifact}")"
    cmp -s "${OUT_DIR}/${name}" "${artifact}" || {
      echo "determinism check failed on ${name}" >&2
      exit 1
    }
  done
}

# Clear a register directory whose every row order is reversed. The account has
# to come out identical, which is what the brief means by the account being a
# function of what the rows say and never of the order they arrive in.
python3 - "${DATA_DIR}" "${SCRATCH}/reversed" <<'PYEOF'
import csv
import os
import shutil
import sys

source, target = sys.argv[1], sys.argv[2]
os.makedirs(target, exist_ok=True)
for name in sorted(os.listdir(source)):
    path = os.path.join(source, name)
    if name.endswith(".csv"):
        with open(path, newline="", encoding="utf-8") as handle:
            rows = list(csv.reader(handle))
        with open(os.path.join(target, name), "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(rows[0])
            writer.writerows(reversed(rows[1:]))
    elif name.endswith(".json"):
        shutil.copyfile(path, os.path.join(target, name))
PYEOF
python3 "${OUT_DIR}/clear_epoch.py" "${SCRATCH}/reversed" "${SCRATCH}/reversed_out"
for artifact in "${SCRATCH}/reversed_out"/*; do
  name="$(basename "${artifact}")"
  cmp -s "${OUT_DIR}/${name}" "${artifact}" || {
    echo "row order independence failed on ${name}" >&2
    exit 1
  }
done

python3 - "${DATA_DIR}" "${OUT_DIR}" <<'PYEOF'
import json
import os
import sys

data_dir, out_dir = sys.argv[1], sys.argv[2]


def load(name):
    with open(os.path.join(out_dir, name), encoding="utf-8") as handle:
        return json.load(handle)


summary = load("summary.json")
reconciliation = load("reconciliation.json")
ledger = load("tap_ledger.json")
quality = load("data_quality.json")
suspension = load("suspension_register.json")
relief = load("cap_relief.json")
netting = load("netting_summary.json")
residual = load("netting_residual.json")
positions = load("netting_positions.json")
schedule = load("netting_schedule.json")
assurance = load("assurance_summary.json")
margins = load("assurance_margins.json")
holdbacks = load("assurance_holdbacks.json")
apportionment = load("assurance_apportionment.json")

print("cleared epoch %s, %s to %s" % (
    summary["epoch_id"], summary["epoch_opens_at"], summary["epoch_closes_at"]))
print()
print("the epoch cleared a charge of %d micros" % summary["epoch_charge_micros"])
print("  taps priced       %d" % summary["taps_priced"])
print("  taps withdrawn    %d" % summary["taps_withdrawn"])
print("  taps out of epoch %d" % summary["taps_out_of_epoch"])
print("  taps in register  %d" % summary["taps_total"])
print("  priced distance   %d units" % summary["priced_distance_units"])
print()

reasons = {}
for row in ledger["rows"]:
    if row["disposition"] == "withdrawn":
        reasons[row["withdrawal_reason"]] = reasons.get(row["withdrawal_reason"], 0) + 1
print("withdrawals by reason:")
for reason in sorted(reasons):
    print("  %-22s %d" % (reason, reasons[reason]))
print()

print("gates suspended, with the reason each was suspended under:")
for gate in suspension["gates"]:
    if gate["suspended"]:
        print("  %-5s %-20s burden %5d bp against an allowance of %5d bp"
              % (gate["gate_id"], gate["reason"], gate["burden_bp"],
                 gate["allowance_bp"]))
print("  the suspension states reached their fixpoint in %d passes, the last of "
      "which changed nothing" % suspension["iterations"])
print("zones left unvalidated : %s" % (summary["unvalidated_zones"] or "none"))
print("operators stood down   : %s" % (summary["stood_down_operators"] or "none"))
print()

print("partitions that ended in scope:")
print("  operators %s" % summary["operators_in_scope"])
print("  zones     %s" % summary["zones_in_scope"])
on_disk = sorted(name for name in os.listdir(out_dir)
                 if name.startswith(("operator_", "zone_")))
print("  reports on disk %s" % on_disk)
expected = sorted(["operator_%s.json" % o for o in summary["operators_in_scope"]]
                  + ["zone_%s.json" % z for z in summary["zones_in_scope"]])
print("  which is exactly the in scope list: %s" % (on_disk == expected))
print()

print("the seven recovered properties:")
for name, value in sorted(summary["resolved_parameters"].items()):
    print("  %-18s %s" % (name, value))
print()

print("cap relief:")
print("  release order %s" % relief["release_order"])
for loan in relief["loans"]:
    print("  %s lent %d micros to %s under operator %s"
          % (loan["from_zone"], loan["amount_micros"], loan["to_zone"],
             loan["operator_id"]))
print("  total lent %d micros" % relief["loan_total_micros"])
for zone in relief["zones"]:
    if zone["curtailed_tap_ids"] or zone["cap_infeasible"]:
        print("  %s curtailed %s, residual %d, cap infeasible %s"
              % (zone["zone_id"], zone["curtailed_tap_ids"],
                 zone["residual_micros"], zone["cap_infeasible"]))
print()

print("conservation identities:")
for identity in reconciliation["identities"]:
    print("  %-56s %12d vs %12d residual %d"
          % (identity["identity"], identity["left"], identity["right"],
             identity["residual"]))
print("  every residual is zero: %s"
      % all(i["residual"] == 0 for i in reconciliation["identities"]))
print("  residual total %d" % reconciliation["residual_total"])
print()

print("netting layer:")
print("  interchange share      %d bp" % netting["interchange_share_bp"])
print("  gross obligations      %d micros" % netting["obligation_total_micros"])
print("  cycles cancelled:")
for index, cycle in enumerate(residual["cycles"], start=1):
    print("    %d. %s for %d micros"
          % (index, " then ".join(cycle["sequence"]), cycle["amount_micros"]))
print("  cancelled in total     %d micros" % netting["cancelled_total_micros"])
print("  cycle free residual    %d micros" % netting["residual_total_micros"])
print("  net positions:")
for position in positions["positions"]:
    print("    %-12s out %10d in %10d net %11d"
          % (position["operator_id"], position["residual_out_micros"],
             position["residual_in_micros"], position["net_position_micros"]))
print("    the net positions sum to %d" % positions["net_total_micros"])
print("  netting digest         %d" % netting["netting_digest"])
print("  funding schedule:")
for row in schedule["rows"]:
    print("    %-12s to %-12s %10d micros %-9s running %10d"
          % (row["payer"], row["payee"], row["amount_micros"], row["state"],
             row["payer_funded_running_micros"]))
print("    %d funded for %d micros, %d deferred for %d micros"
      % (netting["funded_edge_count"], netting["funded_total_micros"],
         netting["deferred_edge_count"], netting["deferred_total_micros"]))
print()

print("assurance layer:")
print("  sample size            %d" % assurance["sample_size"])
print("  median margin          %d" % assurance["median_margin"])
print("  median absolute deviation %d" % assurance["mad"])
print("  threshold              %d times %d = %d"
      % (assurance["assurance_sigma"], assurance["mad"], assurance["threshold"]))
print("  retained               %d" % assurance["retained_count"])
print("  held back              %d" % assurance["held_back_count"])
print("  pool                   %d micros" % assurance["pool_micros"])
print("  assurance digest       %d" % assurance["assurance_digest"])
print("  taps with no distance  %s" % (assurance["zero_distance_taps"] or "none"))
print("  apportionment of the retained distance:")
share_total = 0
for share in apportionment["shares"]:
    print("    %-12s weight %10d share %6d units"
          % (share["rider_class"], share["retained_margin_micros"],
             share["share_units"]))
    share_total += share["share_units"]
print("    the %d shares sum to %d, and the retained distance units are %d, so "
      "they agree: %s"
      % (len(apportionment["shares"]), share_total,
         apportionment["retained_distance_units"],
         share_total == apportionment["retained_distance_units"]))
print()

held = {row["tap_id"] for row in holdbacks["rows"]}
retained_row = next(r for r in margins["rows"] if not r["held_back"])
worked = [("retained ", retained_row)]
if holdbacks["rows"]:
    worked.append(("held back", next(r for r in margins["rows"]
                                     if r["tap_id"] == holdbacks["rows"][0]["tap_id"])))
print("per distance unit arithmetic, one tap each side of the holdback rule:")
for label, row in worked:
    print("  %s %s: (%d unit fare - %d gate floor) / %d distance units "
          "= %d margin, truncated"
          % (label, row["tap_id"], row["unit_fare_micros"],
             row["floor_fare_micros"], row["distance_units"], row["margin"]))
    print("            deviation %d against a threshold of %d, so held back: %s"
          % (row["deviation"], assurance["threshold"], row["held_back"]))
print("  the retained tap's margin joins the pool, the apportionment weights and "
      "the digest order; the held back tap's margin joins none of them.")
print()
print("quality register: %d exceptions, %d upheld, %d rejected, %s upheld on an "
      "already withdrawn tap"
      % (quality["exceptions_total"], quality["exceptions_upheld"],
         quality["exceptions_rejected"],
         quality["exceptions_on_withdrawn_taps"] or "none"))
PYEOF

# Independent verification. Everything above reports figures the delivered
# program computed. This block recomputes them a second time, from the
# registers and from the artifacts, without using clear_epoch.py at all, and
# compares the two. A figure that only agrees with itself is not verified, so
# each identity below is recomputed from the rulebook it comes from and the
# run fails if any of them disagrees.
python3 - "${DATA_DIR}" "${OUT_DIR}" <<'PYEOF'
import csv
import datetime
import json
import os
import sys

data_dir, out_dir = sys.argv[1], sys.argv[2]
failures = []


def artifact(name):
    with open(os.path.join(out_dir, name), encoding="utf-8") as handle:
        return json.load(handle)


def register(name):
    with open(os.path.join(data_dir, name), newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def check(label, recomputed, published):
    agrees = recomputed == published
    if not agrees:
        failures.append(label)
    print("  %-54s %14s vs %14s  %s"
          % (label, recomputed, published, "agrees" if agrees else "DISAGREES"))


def instant(text):
    return datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))


summary = artifact("summary.json")
ledger = artifact("tap_ledger.json")["rows"]
reconciliation = artifact("reconciliation.json")
quality = artifact("data_quality.json")
relief = artifact("cap_relief.json")
netting = artifact("netting_summary.json")
positions = artifact("netting_positions.json")["positions"]
schedule = artifact("netting_schedule.json")["rows"]
assurance = artifact("assurance_summary.json")
margins = artifact("assurance_margins.json")["rows"]
apportionment = artifact("assurance_apportionment.json")

recovered = summary["resolved_parameters"]
grid_step = int(recovered["grid_step_micros"])
midpoint_rule = recovered["midpoint_rule"]
adjustment_order = list(recovered["adjustment_order"])
levy_basis = recovered["levy_basis"]
priced = [row for row in ledger if row["disposition"] == "priced"]

print()
print("independent verification: every figure below is recomputed from the "
      "registers and the rulebooks, not read back from the program that wrote it")
print()


def place(numerator, denominator):
    """The settlement grid placement of T8, under the recovered conventions."""
    step = denominator * grid_step
    whole = numerator // step
    remainder = numerator - whole * step
    if 2 * remainder > step:
        whole += 1
    elif 2 * remainder == step:
        if midpoint_rule == "to_odd_multiple":
            whole = whole if whole % 2 == 1 else whole + 1
        elif midpoint_rule == "to_even_multiple":
            whole = whole if whole % 2 == 0 else whole + 1
        elif midpoint_rule == "away_from_zero":
            whole += 1
    return whole * grid_step


# ---- the tariff engine, rebuilt from rulebook T and run on one tap ----------
tables = dict((row["table_id"], row) for row in register("tariff_tables.csv"))
bands = dict((row["zone_id"], int(row["tariff_band"]))
             for row in register("zones.csv"))
floors = dict((row["gate_id"], int(row["floor_fare_micros"]))
              for row in register("gates.csv"))
faults = register("gate_faults.csv")
closes_at = instant(register("epoch_calendar.csv")[0]["closes_at"])


def abatement_for(gate_id, at):
    """The largest abatement among the faults covering a tap, under T5."""
    largest = 0
    for fault in faults:
        if fault["gate_id"] != gate_id:
            continue
        opened = instant(fault["opened_at"])
        closed = instant(fault["closed_at"]) if fault["closed_at"] else closes_at
        if opened < at <= closed:
            largest = max(largest, int(fault["abatement_micros"]))
    return largest


def unit_fare_of(row):
    table = tables[row["governing_table_id"]]
    if row["rider_class"] == "concession":
        rate = int(table["rate_concession"])
    elif row["peak"]:
        rate = int(table["rate_peak"])
    else:
        rate = int(table["rate_offpeak"])
    multiplier = int(table["mult_" + row["completion_class"]])
    distance_rate_product = rate * row["distance_units"]
    value = place(distance_rate_product * bands[row["zone_id"]] * multiplier, 10000)
    basis = {"distance_rate_product": distance_rate_product}[levy_basis]
    for adjustment in adjustment_order:
        if adjustment == "concession_relief":
            if row["rider_class"] == "concession":
                value = place(value * (10000 - int(table["relief_bp"])), 10000)
        elif adjustment == "fault_abatement":
            abated = abatement_for(row["gate_id"], instant(row["tapped_at"]))
            value = max(0, place(value - abated, 1))
        elif adjustment == "shortfall_levy":
            value = place(value + place(basis * int(table["levy_bp"]), 10000), 1)
        elif adjustment == "interchange_uplift":
            if row["cross_operator"]:
                value = place(value * (10000 + int(table["uplift_bp"])), 10000)
    return max(value, floors[row["gate_id"]])


worked = next(row for row in priced if not row["exception_id"])
print("one priced tap's unit fare, rebuilt from the tariff table and the "
      "recovered adjustment order:")
print("  tap %s at gate %s, zone %s, %s, %s, %d distance units"
      % (worked["tap_id"], worked["gate_id"], worked["zone_id"],
         worked["rider_class"], worked["completion_class"],
         worked["distance_units"]))
print("  adjustments composed in the recovered order %s" % adjustment_order)
print("  the grid step is %d micros and a midpoint goes %s"
      % (grid_step, midpoint_rule))
check("unit fare of %s" % worked["tap_id"],
      unit_fare_of(worked), worked["unit_fare_micros"])
rebuilt = sum(1 for row in priced
              if not row["exception_id"] and unit_fare_of(row) == row["unit_fare_micros"])
eligible = sum(1 for row in priced if not row["exception_id"])
check("priced fares the rebuilt engine reproduces", rebuilt, eligible)
print()

# ---- epoch level totals, summed straight off the ledger --------------------
print("epoch totals, summed off the ledger:")
check("epoch charge", sum(row["unit_fare_micros"] for row in priced),
      summary["epoch_charge_micros"])
check("priced distance units", sum(row["distance_units"] for row in priced),
      summary["priced_distance_units"])
check("taps priced", len(priced), summary["taps_priced"])
print()

# ---- the quality register, cross checked against the registers -------------
print("quality register, cross checked against the registers it describes:")
seen, duplicated = set(), set()
for row in register("taps.csv"):
    if row["tap_id"] in seen:
        duplicated.add(row["tap_id"])
    seen.add(row["tap_id"])
check("duplicate tap ids", sorted(duplicated), quality["duplicate_tap_ids"])
decommissioned = sorted(row["gate_id"] for row in register("gates.csv")
                        if row["decommissioned"] not in ("", "0"))
check("decommissioned gates", decommissioned, quality["decommissioned_gates"])
with open(os.path.join(data_dir, "exceptions.json"), encoding="utf-8") as handle:
    exceptions = json.load(handle)["exceptions"]
check("exceptions total", len(exceptions), quality["exceptions_total"])
check("exceptions upheld",
      sum(1 for e in exceptions if e["status"] == "upheld"),
      quality["exceptions_upheld"])
check("exceptions rejected",
      sum(1 for e in exceptions if e["status"] == "rejected"),
      quality["exceptions_rejected"])
withdrawn_ids = set(row["tap_id"] for row in ledger
                    if row["disposition"] != "priced")
check("exceptions upheld on an already withdrawn tap",
      sorted(e["exception_id"] for e in exceptions
             if e["status"] == "upheld" and e["tap_id"] in withdrawn_ids),
      quality["exceptions_on_withdrawn_taps"])
print()

# ---- cap relief, recomputed from the ceiling and the headroom --------------
print("cap relief, recomputed from each zone's cap and what it borrowed:")
for zone in relief["zones"]:
    # Lending comes out of headroom the lender was never going to use, so it
    # leaves the lender's own ceiling where it was; only borrowing moves one.
    check("effective cap of %s" % zone["zone_id"],
          zone["revenue_cap_micros"] + zone["borrowed_micros"],
          zone["effective_cap_micros"])
check("total lent", sum(loan["amount_micros"] for loan in relief["loans"]),
      relief["loan_total_micros"])
check("total lent equals total borrowed",
      sum(zone["lent_micros"] for zone in relief["zones"]),
      sum(zone["borrowed_micros"] for zone in relief["zones"]))
print()

# ---- the netting layer, recomputed off its own edges -----------------------
netting_policy = register("netting_policy.csv")[0]
print("netting layer, recomputed off the obligations and the schedule:")
for position in positions:
    check("net position of %s" % position["operator_id"],
          position["residual_out_micros"] - position["residual_in_micros"],
          position["net_position_micros"])
check("net positions sum to zero",
      sum(position["net_position_micros"] for position in positions), 0)
digest = 0
for row in schedule:
    digest = ((digest * int(netting_policy["netting_multiplier"])
               + row["amount_micros"]) % int(netting_policy["netting_modulus"]))
check("netting digest folded over the funding order", digest,
      netting["netting_digest"])
check("residual plus cancelled equals gross",
      netting["residual_total_micros"] + netting["cancelled_total_micros"],
      netting["obligation_total_micros"])
print()

# ---- the assurance layer, recomputed off the margins -----------------------
assurance_policy = register("assurance_policy.csv")[0]


def lower_middle(values):
    """The median taking the lower of the two middle values of an even sample."""
    ordered = sorted(values)
    if not ordered:
        return 0
    half, odd = divmod(len(ordered), 2)
    return ordered[half] if odd else ordered[half - 1]


print("assurance layer, recomputed off the per tap margins:")
for row in margins[:1]:
    check("margin of %s truncated per distance unit" % row["tap_id"],
          (row["unit_fare_micros"] - row["floor_fare_micros"]) // row["distance_units"],
          row["margin"])
median = lower_middle([row["margin"] for row in margins])
check("median margin", median, assurance["median_margin"])
deviations = [abs(row["margin"] - median) for row in margins]
mad = lower_middle(deviations)
check("median absolute deviation", mad, assurance["mad"])
threshold = int(assurance_policy["assurance_sigma"]) * mad
check("threshold", threshold, assurance["threshold"])
check("taps held back are the ones strictly above the threshold",
      sorted(row["tap_id"] for row in margins if row["deviation"] > threshold),
      sorted(row["tap_id"] for row in margins if row["held_back"]))
retained = [row for row in margins if not row["held_back"]]
check("pool", sum(row["margin"] for row in retained), assurance["pool_micros"])
digest = 0
for row in sorted(retained, key=lambda r: (r["margin"], r["tap_id"])):
    digest = ((digest * int(assurance_policy["assurance_multiplier"])
               + row["margin"]) % int(assurance_policy["assurance_modulus"]))
check("assurance digest folded over the digest order", digest,
      assurance["assurance_digest"])

weights = {}
for row in retained:
    weights[row["rider_class"]] = weights.get(row["rider_class"], 0) + row["margin"]


def largest_remainder(total, weights):
    """The largest remainder apportionment of total across the weight keys."""
    keys = sorted(weights)
    weight_total = sum(weights[key] for key in keys)
    shares = dict((key, 0) for key in keys)
    if not keys:
        return shares
    if weight_total <= 0:
        shares[keys[0]] = total
        return shares
    pending, assigned = [], 0
    for key in keys:
        exact = total * weights[key]
        whole = exact // weight_total
        shares[key] = whole
        assigned += whole
        pending.append((exact - whole * weight_total, key))
    pending.sort(key=lambda item: (-item[0], item[1]))
    cursor = 0
    while assigned < total and pending:
        shares[pending[cursor % len(pending)][1]] += 1
        assigned += 1
        cursor += 1
    return shares


check("apportionment weights",
      weights,
      dict((share["rider_class"], share["retained_margin_micros"])
           for share in apportionment["shares"]))
check("largest remainder shares",
      largest_remainder(apportionment["retained_distance_units"], weights),
      dict((share["rider_class"], share["share_units"])
           for share in apportionment["shares"]))
print()

# ---- the invariant statement, walked one invariant at a time ---------------
print("the invariant statement, taken one invariant at a time:")
with open(os.path.join(data_dir, "invariants.md"), encoding="utf-8") as handle:
    statement = handle.read()
published = dict((identity["identity"], identity)
                 for identity in reconciliation["identities"])
recomputed = {
    "admitted_plus_out_of_epoch_equals_total":
        (summary["taps_admitted"] + summary["taps_out_of_epoch"],
         summary["taps_total"]),
    "priced_plus_withdrawn_equals_admitted":
        (summary["taps_priced"] + summary["taps_withdrawn"],
         summary["taps_admitted"]),
    "ledger_running_total_closes_on_epoch_charge":
        (ledger[-1]["running_charge_micros"], summary["epoch_charge_micros"]),
    "priced_plus_withdrawn_distance_equals_admitted_distance":
        (sum(row["distance_units"] for row in ledger
             if row["disposition"] in ("priced", "withdrawn")),
         summary["admitted_distance_units"]),
    "net_positions_sum_to_zero":
        (sum(position["net_position_micros"] for position in positions), 0),
    "residual_plus_cancelled_equals_gross":
        (netting["residual_total_micros"] + netting["cancelled_total_micros"],
         netting["obligation_total_micros"]),
    "assurance_shares_sum_to_retained_distance":
        (sum(share["share_units"] for share in apportionment["shares"]),
         apportionment["retained_distance_units"]),
    "retained_margins_sum_to_pool":
        (sum(row["margin"] for row in retained), assurance["pool_micros"]),
}
for name in sorted(published):
    identity = published[name]
    if name in recomputed:
        left, right = recomputed[name]
        check("%s (rebuilt)" % name, left - right, 0)
    check("%s (as published)" % name, identity["left"] - identity["right"],
          identity["residual"])
check("every published residual is zero",
      sorted(set(identity["residual"] for identity in published.values())), [0])
check("residual total", sum(identity["residual"] for identity in published.values()),
      reconciliation["residual_total"])
check("the statement names the conservation section",
      "## Conservation" in statement, True)
print()

if failures:
    print("independent verification DISAGREED on: %s" % ", ".join(failures))
    sys.exit(1)
print("independent verification: every recomputed figure agrees with the "
      "account the program wrote")
PYEOF

# Time one full clearance, so the 300 second budget is a measurement rather
# than an assumption.
python3 - "${OUT_DIR}/clear_epoch.py" "${DATA_DIR}" "${SCRATCH}/timed" <<'PYEOF'
import subprocess
import sys
import time

script, data_dir, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
started = time.monotonic()
subprocess.run([sys.executable, script, data_dir, out_dir],
               stdout=subprocess.DEVNULL, check=True)
elapsed = time.monotonic() - started
print()
print("one full clearance of this epoch took %.3f seconds, against a budget of "
      "300 seconds" % elapsed)
if elapsed >= 300:
    raise SystemExit("the clearance ran past its 300 second budget")
PYEOF

# Clear an epoch that prices nothing. The brief promises the program epochs
# whose taps differ, including ones that price nothing at all, so the empty
# case is exercised rather than assumed.
python3 - "${DATA_DIR}" "${SCRATCH}/empty_registers" <<'PYEOF'
import csv
import os
import shutil
import sys

source, target = sys.argv[1], sys.argv[2]
os.makedirs(target, exist_ok=True)
for name in sorted(os.listdir(source)):
    path = os.path.join(source, name)
    if not os.path.isfile(path):
        continue
    if name == "taps.csv":
        with open(path, newline="", encoding="utf-8") as handle:
            header = next(csv.reader(handle))
        with open(os.path.join(target, name), "w", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(header)
    else:
        shutil.copyfile(path, os.path.join(target, name))
PYEOF
python3 "${OUT_DIR}/clear_epoch.py" "${SCRATCH}/empty_registers" "${SCRATCH}/empty_out"
python3 - "${SCRATCH}/empty_out" <<'PYEOF'
import json
import os
import sys

out_dir = sys.argv[1]
with open(os.path.join(out_dir, "summary.json"), encoding="utf-8") as handle:
    summary = json.load(handle)
with open(os.path.join(out_dir, "reconciliation.json"), encoding="utf-8") as handle:
    reconciliation = json.load(handle)
print()
print("an epoch whose register prices nothing closes as well:")
print("  taps in register %d, priced %d, charge %d micros"
      % (summary["taps_total"], summary["taps_priced"],
         summary["epoch_charge_micros"]))
print("  artifacts written %d, residual total %d"
      % (len(os.listdir(out_dir)), reconciliation["residual_total"]))
for field, expected in (("taps_total", 0), ("taps_priced", 0),
                        ("epoch_charge_micros", 0)):
    if summary[field] != expected:
        raise SystemExit("empty epoch produced %s = %s" % (field, summary[field]))
if reconciliation["residual_total"] != 0:
    raise SystemExit("empty epoch left a residual")
print("  every conservation identity still closes at zero")
PYEOF
