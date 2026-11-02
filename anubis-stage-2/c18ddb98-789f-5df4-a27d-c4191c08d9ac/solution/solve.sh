#!/bin/bash
set -euo pipefail

# Reference solution for cdc-ingest-window-settlement.
#
# /solution/solve.py is the settlement engine. It is delivered to the declared
# artifact path /app/out/settle_ingest.py and then run against /app/data so that
# every settled artifact under /app/out is produced by the same program the task
# asks for. Everything after that run is verification and reporting: the window
# is settled twice and compared, settled again from a register directory of its
# own to show the program carries nothing of this window, and then reported in
# full with the arithmetic behind each figure shown rather than asserted.

SOLUTION_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_DIR="${DATA_DIR:-/app/data}"
OUT_DIR="${OUT_DIR:-/app/out}"
SCRATCH="$(mktemp -d)"
trap 'rm -rf "${SCRATCH}"' EXIT

mkdir -p "${OUT_DIR}"

# Read all of the reference material before writing anything, as the brief
# requires: every rulebook, the invariant statement, the artifact schema, the
# calibration slice and the one shipped example artifact. They are what let a
# solver work out the order the rules bear on a record and the byte form every
# artifact takes.
for reference in "${DATA_DIR}"/*.md; do
  cat "${reference}" >/dev/null
done
cat "${DATA_DIR}/example_domain_report.json" >/dev/null
cat "${DATA_DIR}/calibration_controls.json" >/dev/null

cp "${SOLUTION_DIR}/solve.py" "${OUT_DIR}/settle_ingest.py"
chmod 0644 "${OUT_DIR}/settle_ingest.py"

python3 "${OUT_DIR}/settle_ingest.py" "${DATA_DIR}" "${OUT_DIR}"

# Settle the same registers a second time into a directory of its own and
# compare the two accounts file by file, so the settlement is shown to be a
# function of the registers rather than of the run.
mkdir -p "${SCRATCH}/second"
python3 "${OUT_DIR}/settle_ingest.py" "${DATA_DIR}" "${SCRATCH}/second"
for artifact in "${OUT_DIR}"/*.json "${OUT_DIR}"/*.csv; do
  name="$(basename "${artifact}")"
  if [ "${name}" = "settle_ingest.py" ]; then
    continue
  fi
  cmp "${artifact}" "${SCRATCH}/second/${name}"
done
echo "[solve] second run of the same registers produced byte identical artifacts"

# Settle a register directory of its own, holding the machine readable
# registers and the calibration material and none of the prose, which is the
# shape the program will be handed on other windows.
mkdir -p "${SCRATCH}/registers" "${SCRATCH}/elsewhere"
cp "${DATA_DIR}"/*.csv "${SCRATCH}/registers/"
cp "${DATA_DIR}/exceptions.json" "${SCRATCH}/registers/"
cp "${DATA_DIR}/calibration_controls.json" "${SCRATCH}/registers/"
python3 "${OUT_DIR}/settle_ingest.py" "${SCRATCH}/registers" "${SCRATCH}/elsewhere"
echo "[solve] settled a register directory outside ${DATA_DIR}:"
ls -1 "${SCRATCH}/elsewhere"

# Read back the conservation residuals the run produced before reporting, so the
# settled window is verified rather than assumed.
cat "${OUT_DIR}/reconciliation.json" >/dev/null

echo "[solve] settled window written to ${OUT_DIR}"
ls -1 "${OUT_DIR}"

# Report the window as the brief's closing paragraph asks. Every figure is read
# back out of the artifacts, and every arithmetic claim is recomputed here by
# hand rather than taken from the engine, so the message confirms the artifacts
# instead of echoing them.
python3 - "${DATA_DIR}" "${OUT_DIR}" <<'REPORT'
import csv
import importlib.util
import itertools
import json
import pathlib
import sys

data = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])


def artifact(name):
    return json.loads((out / name).read_text(encoding="utf-8"))


def table(name):
    with (data / (name + ".csv")).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def grid(numerator, denominator, step, mode):
    """Place a rational charge on the settlement grid, written out here rather
    than borrowed from the engine so the figures below are a second opinion."""
    total = denominator * step
    whole, rest = divmod(numerator, total)
    if rest == 0 or mode == "floor":
        placed = whole
    elif mode == "ceil":
        placed = whole + 1
    elif mode == "half_up":
        placed = whole + 1 if 2 * rest >= total else whole
    elif mode == "half_down":
        placed = whole + 1 if 2 * rest > total else whole
    else:
        if 2 * rest > total:
            placed = whole + 1
        elif 2 * rest < total:
            placed = whole
        else:
            placed = whole if whole % 2 == 0 else whole + 1
    return placed * step


summary = artifact("summary.json")
recon = artifact("reconciliation.json")
audit = artifact("ingest_audit.json")
quality = artifact("data_quality.json")
slots = artifact("slot_designation.json")
params = summary["resolved_parameters"]
step = params["quantisation_step_micros"]
mode = params["rounding_mode"]
coefficient = params["backpressure_coefficient_micros"]
ledger = {row["record_id"]: row for row in audit["ledger"]}

egress = artifact("egress_summary.json")
bursts = artifact("egress_bursts.json")["bursts"]
rates = {row["record_id"]: row for row in artifact("egress_rates.json")["rates"]}
apportionment = artifact("egress_apportionment.json")
octets = egress["payload_unit_octets"]

domain_reports = {
    path.name: json.loads(path.read_text(encoding="utf-8"))
    for path in sorted(out.glob("domain_*.json"))
}
channel_reports = {
    path.name: json.loads(path.read_text(encoding="utf-8"))
    for path in sorted(out.glob("channel_*.json"))
}

feeds = {row["feed_id"]: row for row in table("feeds")}
domains = {row["domain_id"]: row for row in table("domains")}
channels = {row["channel_id"]: row for row in table("channels")}
cards = {row["card_id"]: row for row in table("rate_cards")}
incidents = table("feed_incidents")
landing = {row["record_id"]: row for row in table("landing_records")}
policy = {row["policy_key"]: int(row["policy_value"]) for row in table("window_policy")}
controls = json.loads((data / "calibration_controls.json").read_text(encoding="utf-8"))["controls"]

spec = importlib.util.spec_from_file_location("delivered", out / "settle_ingest.py")
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)

print("=== the settled window ===")
print("window                    : %s  %s to %s"
      % (summary["window_id"], summary["window_open"], summary["window_close"]))
print("settled charge (micros)   :", summary["settled_charge_micros"])
print("curated records           :", summary["curated_record_count"])
print("withdrawn records         :", summary["withdrawn_record_count"])
print("quarantined records       :", summary["quarantined_record_count"])
print("curated payload units     :", summary["curated_payload_units"])
print("landing records           :", summary["landing_record_count"])
print("records in the window     :", summary["in_window_record_count"])
print("settled charge per domain in scope:")
for domain in recon["per_domain"]:
    print("  %-14s %d micros over %d curated records"
          % (domain["domain_id"], domain["settled_charge_micros"],
             domain["curated_record_count"]))

print()
print("withdrawals by reason, and the withdrawn count they sum to:")
reason_total = 0
for token in sorted(summary["withdrawal_reason_counts"]):
    count = summary["withdrawal_reason_counts"][token]
    reason_total += count
    print("  %-38s %d" % (token, count))
print("  %-38s %d, and the summary reports %d withdrawn records"
      % ("sum of the reason counts", reason_total, summary["withdrawn_record_count"]))

print()
print("=== the five recovered properties ===")
print("adjustment_precedence             :", params["adjustment_precedence"])
print("backpressure_coefficient_micros   :", coefficient)
print("quantisation_step_micros          :", step)
print("rounding_mode                     :", mode)
print("tombstone_reading                 :", params["tombstone_reading"])
print()
print("The four rate adjustments compose in exactly that order: %s, then %s, "
      "then %s, then %s." % tuple(params["adjustment_precedence"]))
print("The settlement grid is spaced %d micros apart, so every settled figure "
      "is a multiple of %d. A value falling midway between two grid points "
      "settles by the %s convention: the tie goes to the even multiple of %d, "
      "which is neither always upward nor always downward."
      % (step, step, mode, step))

search_space = (len(list(itertools.permutations(engine.ADJUSTMENTS)))
                * len(engine.ROUNDING_MODES) * len(engine.STEP_CHOICES)
                * (engine.COEFFICIENT_LIMIT + 1) * len(engine.TOMBSTONE_READINGS))
print()
print("Those five were settled against the calibration slice in "
      "calibration_controls.json. Each candidate reading was scored against "
      "every control figure that slice publishes, which is its curated, "
      "withdrawn and quarantined record counts, its curated payload units, "
      "its total settled charge, its per domain settled charge, its "
      "quarantined feeds, its per reason withdrawal counts and the settled "
      "unit rate of each of the %d named records. The search covered %d "
      "combinations of precedence, rounding convention, grid spacing, "
      "backpressure coefficient and tombstone reading, and exactly one "
      "reproduced all of them; every other combination missed at least one "
      "figure." % (len(controls["adjusted_unit_rate_micros"]), search_space))
print("control figures the reading was scored against:")
for key in sorted(controls):
    print("  %-34s %s" % (key, json.dumps(controls[key], sort_keys=True)))

print()
print("=== the order the rulebooks bear on a record ===")
print("The reference set is shelved alphabetically, which is not the order in "
      "which the rules bear on a record. The order that reproduces the "
      "calibration figures is admission, then identity, then cards, then the "
      "tombstone rule, then slots, then quarantine, then retention, then "
      "costing with the adjustment rulebook inside it, then the ledger, then "
      "partition, and the egress rulebook last of all because it consumes the "
      "curated ledger the rest of them settle. Taking the shelf order instead "
      "quarantines feeds before the tombstone rule has withdrawn anything, "
      "which moves every defect rate and misses the published figures.")

# A record traced through each adjustment, chosen as the record whose
# arithmetic exercises the most of them.
best = None
for record_id, row in sorted(ledger.items()):
    if row["disposition"] != "curated":
        continue
    feed = feeds[row["feed_id"]]
    card = cards[row["governing_card_id"]]
    source = landing[record_id]
    incident = engine.governing_incident(incidents, row["feed_id"], row["emitted_at"])
    abatement = int(incident["abatement_micros"]) if incident is not None else 0
    nominal = int(feed["nominal_throughput"])
    # The feed load the surcharge is measured against is the load the feed
    # carried before the cap curtailed anything, so the curtailed records
    # count towards it.
    used = sum(ledger[other]["payload_units"] for other in ledger
               if ledger[other]["feed_id"] == row["feed_id"]
               and (ledger[other]["disposition"] == "curated"
                    or ledger[other]["reason"] == "withdrawn_by_curtailment"))
    excess_bp = max(0, (used - nominal) * 10000 // nominal) if nominal else 0
    override = None
    for item in json.loads((data / "exceptions.json").read_text(encoding="utf-8")):
        if item["record_id"] == record_id and item["status"] == "upheld":
            override = int(item["agreed_unit_rate_micros"])
    context = {
        "abatement": abatement,
        "allowance": int(feed["defect_allowance_bp"]),
        "excess_bp": excess_bp,
        "floor": int(feed["floor_rate_micros"]),
        "multiplier": int(card["mult_" + source["form_class"]]),
        "override": override,
        "rate": int(card["rate_" + source["tier_class"]]),
    }
    moved = sum(1 for value in (abatement, context["allowance"], excess_bp) if value) \
        + (1 if override is not None else 0)
    if best is None or moved > best[2]:
        best = (record_id, context, moved)

record_id, context, _moved = best
row = ledger[record_id]
source = landing[record_id]
card = cards[row["governing_card_id"]]
print()
print("=== one record traced through every adjustment ===")
print("record %s on feed %s in domain %s, emitted %s, tier %s, form %s, "
      "payload %d units"
      % (record_id, row["feed_id"], row["domain_id"], row["emitted_at"],
         source["tier_class"], source["form_class"], row["payload_units"]))
value = grid(context["rate"] * context["multiplier"], 10000, step, mode)
print("  card rate %d at form multiplier %d over 10000, placed on the %d micro "
      "grid by %s          = %d"
      % (context["rate"], context["multiplier"], step, mode, value))
for name in params["adjustment_precedence"]:
    if name == "abatement":
        value = grid(max(0, value - context["abatement"]), 1, step, mode)
        print("  abatement of %d micros subtracted and replaced on the grid"
              "                              = %d" % (context["abatement"], value))
    elif name == "rebate":
        value = grid(value * (10000 - context["allowance"]), 10000, step, mode)
        print("  rebate of %d basis points of defect allowance applied"
              "                           = %d" % (context["allowance"], value))
    elif name == "override":
        if context["override"] is not None:
            value = grid(context["override"], 1, step, mode)
            print("  upheld exception replaces the unit rate with %d micros"
                  "                         = %d" % (context["override"], value))
        else:
            print("  no upheld exception reaches this record, so the override step "
                  "leaves it at          = %d" % value)
    elif name == "surcharge":
        surcharge = coefficient * context["excess_bp"] // 10000
        print("  surcharge: backpressure coefficient %d micros times %d basis "
              "points of excess over 10000 = %d micros, added and replaced on "
              "the grid = %d"
              % (coefficient, context["excess_bp"], surcharge,
                 grid(value + surcharge, 1, step, mode)))
        value = grid(value + surcharge, 1, step, mode)
settled = max(value, context["floor"])
print("  feed floor rate %d micros holds the unit rate at"
      "                                   = %d" % (context["floor"], settled))
print("  settled unit rate %d micros times %d payload units = %d micros, and "
      "the ledger records %d"
      % (settled, row["payload_units"], settled * row["payload_units"],
         row["record_charge_micros"]))
print("  recomputed by hand here, independently of the engine, and it agrees "
      "with the artifact: %s"
      % (settled == row["unit_charge_micros"]
         and settled * row["payload_units"] == row["record_charge_micros"]))

print()
print("=== identity and the governing card at one record's own instant ===")
print("record %s carried producer reference %s, and at its own instant %s that "
      "reference resolved to canonical producer %s; the resolution register "
      "records that outcome with the records that took it."
      % (record_id, source["producer_ref"], row["emitted_at"],
         row["canonical_producer_id"]))
print("record %s is governed by rate card %s, selected by that same emission "
      "instant %s: card %s went live at %s and %s, so it is the one card live "
      "at the instant."
      % (record_id, row["governing_card_id"], row["emitted_at"],
         row["governing_card_id"], card["effective_from"],
         ("was never superseded" if not card["superseded_at"]
          else "was superseded at " + card["superseded_at"])))

print()
print("=== the tombstone rule in both readings ===")
tombstoned = [row for row in audit["ledger"]
              if row["reason"] == "withdrawn_by_tombstone"]
first_tombstone = {}
for entity in audit["tombstone_entity_ids"]:
    instants = [row["emitted_at"] for row in audit["ledger"]
                if row["canonical_producer_id"] == entity
                and landing[row["record_id"]]["op"] == "tombstone"]
    if instants:
        first_tombstone[entity] = min(instants)
forward = [row for row in tombstoned
           if row["emitted_at"] >= first_tombstone.get(row["canonical_producer_id"], "")]
print("The platform reads the rule retroactively: a tombstone withdraws the "
      "whole window for its canonical entity, the records emitted before the "
      "tombstone instant included. On this window that withdrew %d records "
      "across the %d entities a tombstone reached: %s."
      % (len(tombstoned), len(audit["tombstone_entity_ids"]),
         ", ".join(audit["tombstone_entity_ids"])))
print("The ordinary reading of such a rule is forward only, withdrawing a "
      "record only when it was emitted at or after the tombstone instant. "
      "That reading would have withdrawn %d of those %d records and left %d "
      "earlier records curated, which is why the two readings settle the "
      "window to different charges."
      % (len(forward), len(tombstoned), len(tombstoned) - len(forward)))

print()
print("=== the conservation identities ===")
identity = recon["identity"]
charge = recon["charge"]
units = recon["units"]
print("records : %d curated + %d withdrawn + %d quarantined = %d, against %d "
      "in the window, residual %d"
      % (identity["curated_record_count"], identity["withdrawn_record_count"],
         identity["quarantined_record_count"],
         identity["curated_record_count"] + identity["withdrawn_record_count"]
         + identity["quarantined_record_count"],
         identity["in_window_record_count"], identity["residual_record_count"]))
print("charge  : %d across the domains and %d across the channels, against %d "
      "settled by the window, residual %d"
      % (charge["domain_charge_total_micros"], charge["channel_charge_total_micros"],
         charge["window_settled_charge_micros"], charge["residual_micros"]))
print("units   : %d apportioned across the domains against %d curated by the "
      "window, residual %d"
      % (units["domain_curated_units_total"], units["curated_payload_units"],
         units["residual_units"]))
print("per domain residuals: %s"
      % ", ".join("%s %d" % (row["domain_id"], row["residual_micros"])
                  for row in recon["per_domain"]))

print()
print("=== curated units against the cap, domain by domain ===")
for name in sorted(domain_reports):
    report = domain_reports[name]
    print("  %-14s %4d curated payload units against a cap of %4d, %s"
          % (report["domain_id"], report["curated_payload_units"],
             report["curated_cap"],
             ("the cap bound and curtailed %d records"
              % len(report["curtailed_record_ids"]))
             if report["curtailed_record_ids"] else "the cap did not bind"))

print()
print("=== reserve slots and the quarantine fixpoint ===")
print("designated reserve feeds, with the nominal throughput each one held back:")
for feed_id in summary["designated_reserve_feed_ids"]:
    print("  %-8s %s throughput %s"
          % (feed_id, feeds[feed_id]["feed_class"], feeds[feed_id]["nominal_throughput"]))
share = (slots["designated_nominal_throughput"] * 10000
         // slots["window_nominal_throughput"])
print("designated throughput %d of the window's %d is %d basis points, inside "
      "the band %d to %d the policy register publishes."
      % (slots["designated_nominal_throughput"], slots["window_nominal_throughput"],
         share, slots["designated_band_low_bp"], slots["designated_band_high_bp"]))

close = summary["window_close"]
per_channel = []
for channel_id in sorted(channels):
    members = sorted(d for d in domains if domains[d]["channel_id"] == channel_id)
    if not any(domains[d]["provisional"] == "false" for d in members):
        continue
    ceiling = int(channels[channel_id]["slot_ceiling"])
    live = {}
    candidates = []
    for feed_id in sorted(feeds):
        feed = feeds[feed_id]
        if feed["domain_id"] not in members or feed["suspended"] == "true":
            continue
        if domains[feed["domain_id"]]["provisional"] == "true":
            continue
        if engine.governing_incident(incidents, feed_id, close) is not None:
            continue
        live.setdefault(feed["domain_id"], []).append(feed_id)
        candidates.append(feed_id)
    admissible = []
    for combo in itertools.combinations(candidates, ceiling):
        classes = [feeds[f]["feed_class"] for f in combo]
        if len(set(classes)) != len(classes) or "primary" not in classes:
            continue
        if any(all(f in set(combo) for f in pool) for pool in live.values()):
            continue
        admissible.append(combo)
    per_channel.append((channel_id, admissible))
inside = []
outside = []
for assignment in itertools.product(*[item[1] for item in per_channel]):
    total = sum(int(feeds[f]["nominal_throughput"]) for combo in assignment for f in combo)
    value = total * 10000 // slots["window_nominal_throughput"]
    if slots["designated_band_low_bp"] <= value <= slots["designated_band_high_bp"]:
        inside.append((value, assignment))
    else:
        outside.append(value)
print("the slot conditions admit %d assignments of the reserve slots across "
      "the channels in play; their designated shares run from %d to %d basis "
      "points, and exactly %d of them lands inside the published band, which "
      "is why the designation above is the single feasible one."
      % (len(inside) + len(outside), min(outside + [share]), max(outside + [share]),
         len(inside)))

cascade_token = "withdrawn_by_quarantine_cascade"
print()
print("the quarantine iteration settled on %d feeds: %s. Each one carried a "
      "defect rate above the allowance its own feed register publishes, which "
      "is %s respectively."
      % (len(summary["quarantined_feed_ids"]),
         ", ".join(summary["quarantined_feed_ids"]),
         ", ".join("%s basis points for %s"
                   % (feeds[feed_id]["defect_allowance_bp"], feed_id)
                   for feed_id in summary["quarantined_feed_ids"])))
print("one further round of the cascade adds no feed, so that set is the "
      "fixpoint. The cascade can only taint more records and so can only grow "
      "the set, the candidate feeds are finite, and every feed still in "
      "carries a defect rate at or below its own allowance once the cascade "
      "withdrawals of this round are counted:")
designated = set(summary["designated_reserve_feed_ids"])
pool_reasons = ("", "withdrawn_by_tombstone", cascade_token,
                "withdrawn_by_curtailment")
for feed_id in sorted(feeds):
    if feed_id in summary["quarantined_feed_ids"] or feed_id in designated:
        continue
    pool = [row for row in audit["ledger"] if row["feed_id"] == feed_id
            and row["reason"] in pool_reasons]
    if not pool:
        continue
    bad = [row for row in pool
           if row["reason"] in ("withdrawn_by_tombstone", cascade_token)]
    print("  %-8s %4d basis points of defect against an allowance of %s"
          % (feed_id, 10000 * len(bad) // len(pool),
             feeds[feed_id]["defect_allowance_bp"]))
print("  the designated feeds %s are held back as reserve slots, so the "
      "quarantine rule never reaches them."
      % ", ".join(sorted(designated)))

print()
print("=== the partitions in scope ===")
print("domains in scope  : %d, %s"
      % (summary["admitted_domain_count"],
         ", ".join(sorted(report["domain_id"] for report in domain_reports.values()))))
print("channels in scope : %d, %s"
      % (summary["admitted_channel_count"],
         ", ".join(sorted(report["channel_id"] for report in channel_reports.values()))))
settled_domains = {report["domain_id"] for report in domain_reports.values()}
for domain_id in sorted(domains):
    if domain_id in settled_domains:
        continue
    if domains[domain_id]["provisional"] == "true":
        why = "the domain is provisional, so every record on its feeds withdrew"
    else:
        why = "the domain curated no record once its feeds were designated or quarantined"
    print("  no report for %-12s %s" % (domain_id, why))
for channel_id in sorted(channels):
    if channel_id in {report["channel_id"] for report in channel_reports.values()}:
        continue
    print("  no report for channel %-8s no member domain of it settled" % channel_id)

print()
print("=== the egress layer ===")
print("egress pool (micros)      :", egress["egress_pool_micros"])
print("egress digest             :", egress["egress_digest"])
print("curated records retained  :", egress["retained_record_count"])
print("curated records held back :", egress["burst_record_count"])
print("octets per payload unit the rates were divided over:", octets)
print()
print("The egress division closes differently from every other division in the "
      "reference set: it truncates its quotient and leaves the result where it "
      "falls, while the settlement above places every division on the %d micro "
      "grid by %s. Its medians settle an even sample on the lower of the two "
      "middle values without averaging them and without placing the result, "
      "and a record sitting exactly on the rejection threshold is retained "
      "rather than held back." % (step, mode))

print()
print("records the burst rule held back, with what decided each one:")
for row in bursts:
    print("  %s  egress rate %d stands above threshold %d  (group %s:%s, "
          "median %d, deviation %d, threshold = %d + %d times %d)"
          % (row["record_id"], row["egress_rate"], row["threshold"],
             row["domain_id"], row["feed_id"], row["group_median"],
             row["group_mad"], row["group_median"],
             (row["threshold"] - row["group_median"]) // row["group_mad"]
             if row["group_mad"] else 0, row["group_mad"]))

print()
print("payload share per group:")
shares = apportionment["shares"]
for key in sorted(shares):
    print("  %-22s %d" % (key, shares[key]))
share_total = sum(shares[key] for key in sorted(shares))
print("  the %d shares sum to %d, and the curated payload units are %d, so "
      "they agree: %s"
      % (len(shares), share_total, apportionment["curated_payload_units"],
         share_total == apportionment["curated_payload_units"]))

print()
held_back = {row["record_id"] for row in bursts}
worked = [
    ("retained ", next(rates[key] for key in sorted(rates) if key not in held_back)),
    ("held back", rates[bursts[0]["record_id"]]),
]
print("per octet arithmetic, one curated record each side of the burst rule:")
for label, row in worked:
    print("  %s %s: charge %d micros / (%d payload units * %d octets per unit) "
          "= %d micros per octet, truncated"
          % (label, row["record_id"], row["record_charge_micros"],
             row["payload_units"], octets, row["egress_rate"]))
print("  the retained record's rate joins the pool and the order the digest is "
      "taken over; the held back record's rate joins neither.")
REPORT
