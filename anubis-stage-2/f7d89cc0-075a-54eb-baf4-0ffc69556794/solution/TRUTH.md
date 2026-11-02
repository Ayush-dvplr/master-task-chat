# TRUTH.md - f7d89cc0-075a-54eb-baf4-0ffc69556794

## Defect

The task hands the agent the October 2025 monthly retail electricity
settlement extract of a utility in the fictional Meridian Interstate Grid
Compact (MIGC), with a written data contract at `/app/data/schema.md`. The
agent must build a reusable Python program `/app/out/reconcile.py` that reads
any extract in that schema and emits nine canonical JSON reports. The
verifier grades the shipped reports, then keeps the program alive for a
four-turn hidden session: CASCADE, REVERSAL, CHALLENGE, and CASCADE again.
Every turn supplies a complete independent snapshot. The last turn proves
that intervening snapshots cannot contaminate a repeated input.

Hidden profiles preserve the core rule traps while varying transactions and
reference tables. Customer currency and grandfather fields, premise regions,
tariff windows and rates, signed FAC values, holiday treatments, currency
rates, regulator orders, NMB balances, and input row order all move. A
competent solver must derive each turn from its files rather than treating
the shipped values as constants:

1. The whole pipeline is unbuilt: twelve data files, per-customer hourly
   consumption, TOU bucketing, net-metering banking, FAC, demand charges,
   retroactive orders, FTU conversion and nine rollups. Checks: the shipped
   summary, class and region semantic partitions.
2. Hourly interpolation (schema §4, §5, §13). Each inter-read gap is spread
   over civil hours by elapsed civil seconds, each hour takes its own TOU
   label, and customer-level rounding targets are rounded once from exact
   values. Rollup totals sum the published customer integers without
   independent re-rounding. Spreading by day, or rounding the in-period
   share, misprices most customers. Checks:
   every shipped reference check and every staged profile comparison.
3. DST fall-back on 2025-10-26. The repeated 01:00 hour counts twice in
   interpolation and is labelled `night` for RES and IND, `weekend` for COM;
   the demand rows for it use the `T25:00:00` / `T25:30:00` sentinels, and
   C0016's peak sits in a T25 row. REVERSAL also makes the cutover date a
   `holiday_off` date. Checks: every staged profile comparison.
4. Meter rollover (§4.1). Both mech5 customers (C0005, C0008) start a
   seeded distance below 99999.999 kWh. C0005 starts 200-300 kWh below the
   limit, so in every extract its Oct 15 read is still before the wrap and
   its closing read is after it. C0008's seeded placement varies by profile.
5. Move-in and move-out (§3.10, §4). C0001 moves in on a seeded day 3-9 and
   C0004 moves out on a seeded day 18-24; consumption and the customer
   charge cover service days only, and the C0004 fiscal true-up still fires
   (§7.2).
6. Data quality (§15). C0001 has no read on or before its move-in date and
   C0008 has no closing read, so both boundaries are extrapolated at the
   nearest gap's rate (§15.4). Two duplicate closing timestamps (§15.3):
   C0010's lower value is listed first, and C0005 lists its true post-wrap
   closing read and then a stuck 99999.998, so keeping the numerically
   highest value instead of the greatest forward distance misbills C0005.
   C0012 has seven reads, so six gap rates and an even-count median
   (§15.2): one one-hour spike on the Oct 20 holiday sits between 20 times
   the lower middle rate and 20 times the median, and one on Oct 24 sits
   between 20 times the median and 20 times the upper middle rate. Only the
   Oct 24 gap is flagged; taking either middle rate alone instead of their
   mean flags 0 or 2. C0003 starts with a
    negative bank (§3.9). Every extract also carries one meter read and one
    demand interval for `C0090`, a customer_id absent from `customers.csv`,
    plus C0021, whose customer row names absent premise P404 and whose orphan
    lineage includes a service ticket, meter reads and demand intervals
    (§15.1). The raw meter and demand rows count in their row counts, while
     C0021 and both orphan lineages are dropped from bills, rollups, flags and
     ticket-type counts. Checks: the shipped data-quality partitions, plus
     every bill those customers feed.
7. Two-channel premises (§3.2). P1020 and P88 meter two channels; reads
    and demand are summed per hour and per `interval_start`. C0017/P1020 has
    a complete channel 1 but no opening boundary on channel 2, so channel 2
    is extrapolated independently and the customer contributes one, not two,
    to the missing-start count.
8. Demand selection (§6). C0015's highest row falls on the Oct 13
   `holiday_off` date and must be excluded; C0014 has an exact tie across its
   Oct 15 grandfather expiry, and the later row wins, which prices the demand
   at the current schedule rather than the frozen one.
9. Grandfather freeze (§10). C0014 is billed on the 2021 schedule up to
   Oct 14 and on the current one from Oct 15, with the customer charge
   prorated and rounded once. R-25-19 carries `grandfather_immune = true`,
   so it adds a demand rebill line to C0014 compared on the standard rows
   (§11); R-25-15 is not immune and C0002 is RES, so neither order touches
   C0002. C0020 (IND) is frozen from 2025-08-12 to 2026-01-01. That date
   falls inside the precedence-20 S-25-R15-0001 IND peak window (33), but
   §3.3 freezes it on the precedence-10 S-24-03 rows (peak 30), so a
   tariff lookup without the precedence ceiling misprices its peak energy.
   The non-immune R-25-15 must also skip it: a solver that ignores
    `grandfather_immune` adds a fourth R-25-15 line. Checks: the shipped policy
    partitions, the shipped industrial rollup partitions, and every staged
    profile comparison.
10. Rate-class migration (§9). Two migrations per extract. C0007 moves from
    RES to COM on a seeded day 10-16; consumption is bucketed and priced by
    the class held on each date, and the customer charge is prorated and
    rounded once. C0007 is also grandfathered to 2026-01-01, so the
    migration breaks its freeze (`prorata_split_at` is the migration date),
    and it is solar with a 2,200.000 kWh bank. The bank is drawn in label
    order and leaves a positive residue; because C0007 holds COM at the
    fiscal true-up instant, that residue is forfeited rather than receiving
    the RES payout (§7.2, §7.3). C0016 moves from COM to IND on a seeded day 18-23,
    before its Oct 26 T25 DDC, so its demand is priced at the IND rate (1800)
    of the class held on the DDC date, not the COM rate (1250); it stays in
    the commercial rollup and keeps its R-25-19 line, because both follow
    the `customers.csv` class. Every staged comparison grades those billing
    and audit effects.
11. Regulator orders (§3.8, §11, §14.5). R-25-15 (IND peak, August) and
    R-25-19 (COM demand, September) add adjustment lines computed from
    assumed-prior quantities. R-25-22 is an in-period forward-only
    declaration with an unpublished replacement: it counts as active but has
    no monetary effect. R-25-21 remains future and is counted out of period.
    CASCADE also adds R-25-23, a grandfather-immune RES peak rebill whose
    replacement rate is lower than the assumed prior rate, forcing a
    negative adjustment. Checks: the shipped data-quality report and every
    staged profile comparison.
12. Currency (§12). C0013 and C0019 bill in FTU: the bill without its §11
    lines converts at the 2025-10-01 rate and each §11 line converts at the
    rate on the first day of the period it rebills. No rate is listed for
    2025-09-01, so C0013's R-25-19 line uses the last-known-good
    2025-08-01 rate (§3.7).
13. Net-metering true-up (§7.2, §7.3). RES residue is paid out at 4 mrcc per
    kWh, COM or IND residue is forfeited. The class held at the true-up
    instant controls treatment after a migration. Hidden profiles vary
    multiple opening balances and both signs.
14. Output shape (§14, §16). Sorted keys, two-space indentation, trailing
    newline, customer lists sorted by numeric premise suffix. Premise codes
    have no leading zeros and differ in length (`P2` ... `P1020`), and
    `customers.csv` follows neither customer_id nor premise order, so file
    order and string order (`P101` before `P12`) are both wrong;
    `holiday_calendar.json` is likewise out of date order, and
    `grandfather_applied` must be re-sorted by customer_id. Checks:
    `artifacts_canonically_serialised`, `customer_lists_sorted_by_premise_number`,
    the shipped policy partitions and every staged profile comparison.

15. Reference-table variability. CASCADE splits COM rates on Oct 17, makes
    FAC negative, changes two regions and currencies, moves a grandfather
    expiry, and adds a negative retroactive order. REVERSAL splits IND rates
    on Oct 11, lowers the COM retroactive demand rate below its assumed prior
    value, relabels the fall-back date as off, and changes regions, currencies
    and an NMB balance. CHALLENGE splits RES rates on Oct 23, uses another
    negative FAC, and changes regions, currencies, holidays, grandfather
    expiry and NMB balances. Split schedules put one TOU label under two
    rates in one month: energy is still accumulated exactly and rounded once
    per label, never once per rate segment.
16. Persistent execution. One process receives CASCADE, REVERSAL, CHALLENGE,
    then CASCADE again in one output directory. It must reload every table,
    fully replace every report, emit the exact compact acknowledgement after
    each turn, and reproduce the first CASCADE bytes after two unrelated
    turns. CHALLENGE is also executed as an independent hidden one-shot input,
    so both invocation modes are exercised beyond the shipped extract.

Out of bounds: embedding the shipped totals in `reconcile.py`
(`negative_hardcoded_sample_answers`), a stub under 80 substantive lines
(`negative_missing_substantive_sections`, which does not fire when the
hardcoding check already has), referencing `/tests`, `/logs` or the verifier
module (`negative_reads_tests_or_reward_files`), importing a third-party or
standard-library network module (`negative_external_dependency_or_network`),
creating, changing or removing a scratch path outside `OUT_DIR` during a run
(`negative_writes_outside_out_dir`).
An import that names the verifier module belongs only to the dedicated
verifier-access check and is excluded from the dependency check, so one import
cannot incur both penalties.

## Load-bearing work

Ten graded artifacts under `/app/out/`: the reusable `reconcile.py`
(Python 3 standard library only, reads only `DATA_DIR`, writes only
`OUT_DIR`) and nine JSON reports:

- `summary.json` - corpus-wide totals with the keys in schema §14.1.
- `rate_class_residential.json`, `rate_class_commercial.json`,
  `rate_class_industrial.json` - the same totals per base rate class plus a
  per-customer array.
- `region_meridian_north.json`, `region_meridian_south.json`,
  `region_meridian_east.json` - the same per region.
- `policy_audit.json` - grandfather applications, migrations, retroactive
  lines, holiday reclassifications and the DST cutover.
- `data_quality.json` - row counts, boundary, duplicate and high-variance
  flags, ticket counts, regulator-order tallies.

All money is integer mrcc or ftuc and all energy integer thousandths of a
kWh; nothing is floating point.

## Verification

`tests/test.sh` clears stale reward files, locks `/logs/verifier`, restricts
`/tests` and hands over to rewardkit, which writes
`/logs/verifier/reward.json`. `tests/reward.toml` gives each channel half of
the reward: `0.5 / 66` per test weight point and `0.5 / 22` per judged
point. There is no clamp; the reward runs from about -0.348 (every negative
that can fire together firing, nothing earned; the hardcoding and stub
checks are mutually exclusive) to 1.000.

Test channel (`tests/test_output.py`): 35 checks, positive total 66,
negative total -19.

- shipped exact values are divided among twenty non-overlapping semantic
  partitions: four summary sections; two policy-audit sections; two
  data-quality sections; separate totals and customer-row sections for each
  class and each region. No whole shipped report is one all-or-nothing check.
  Summary, policy, data-quality, class-total and region-total sections each
  have weight 1. Class customer rows are divided into five independently
  scored groups under weight-5 checks; region customer rows use three groups
  under weight-3 checks. Their weights total 38, concentrating reward on the
  customer-level settlement rather than easily copied aggregate reports.
- staged exact values are divided among five checks. CASCADE billing, regions
  and audits each contain five disjoint one-point groups under fractional
  weight-5 checks. REVERSAL remains a complete persistent-turn comparison at
  weight 1. CHALLENGE is a complete independent one-shot comparison at weight
  1. Their weights total 17. One wrong staged scalar can lose at most one raw
  point within the grouped CASCADE checks.
- `persistent_session_protocol`,
  `customer_lists_sorted_by_premise_number` and
  `persistent_session_resets_state` have weight 3;
  `artifact_set_exists_and_parses` and
  `artifacts_canonically_serialised` have weight 1.
- negative: `negative_hardcoded_sample_answers` (-5),
  `negative_missing_substantive_sections` (-3),
  `negative_reads_tests_or_reward_files` (-5),
  `negative_external_dependency_or_network` (-3),
  `negative_writes_outside_out_dir` (-3)

Every shipped top-level field belongs to exactly one semantic partition.
The fractional subchecks return only values in `[0, 1]`; multiplying by their
registered weight reproduces the stated one-point ownership.
CASCADE billing, region and audit checks own disjoint artifact groups;
REVERSAL and one-shot CHALLENGE each own a different snapshot and invocation
surface. The protocol check owns only command acknowledgement and process
lifetime. The reset check owns only the byte identity of the first and fourth
CASCADE turns. Shipped canonical formatting and customer-array order are paid
only by their dedicated checks. These observable sets do not overlap.

Judged channel (`tests/judge.toml`): 10 criteria, positive total 22,
negative total -10. R1 reads the whole contract (constraint, 1); R2 runs the
script on the shipped extract (constraint, 1); R3 independently verifies a
migrated customer's net-metering true-up on a modified-reference snapshot
(conduct, 3); R4 independently verifies signed FAC and the separate
last-known-good FTU conversions of a current-period amount and each retroactive
line for a billing-currency customer in a modified-reference snapshot
(conduct, 3); R5 independently verifies a
retroactive adjustment across effective windows, including every charge
component (conduct, 5); R6 keeps flat monthly customer-charge proration limited
to service-window, migration and grandfather-expiry boundaries (conduct, 5);
R7 judges ordinary Python reviewability (conduct, 3); R8 keeps each turn's
non-verifier reads inside its supplied DATA_DIR (constraint, 1); R9 writes a
report JSON by any means other than the script (constraint, -5); R10 falsely
claims successful recovery after a failed turn acknowledged success while
exposing stale or incomplete reports (-5).

The judged annotations carry only `mode`, `type`, `evaluation_target` and
`importance`, so the sentence each constraint criterion enforces is
recorded here instead. All four live in `instruction.md`. R1: "Read that
contract in full and work out from it how the customers, premises, tariff
schedule, fuel adjustment index, holiday and DST calendars, currency
table, regulator orders, net-metering banks, service tickets, meter reads
and demand intervals fit together." R2: "Run that mode on the shipped extract so
that the whole-corpus settlement report lands at `/app/out/summary.json`,
the applied-rule audit at `/app/out/policy_audit.json`, and the count and
threshold checks at `/app/out/data_quality.json`." R8: "In one-shot mode it
must not read outside `DATA_DIR`; in session mode it may read only the
`data_dir` named by the current command." R9: "Produce the exact reconciled settlement report the
contract describes, deriving every figure from the data rather than
handwriting sample answers."

R3, R4 and R5 grade independent derivation evidence in the trajectory, not
the artifact values owned by the deterministic staged-profile checks. Their
observables are disjoint: migration-time bank disposition, exact aggregation
of signed FAC and separate current/retroactive FTU conversions in a modified
snapshot, and complete effective-window rebilling. R6 grades the
source algorithm used for flat monthly customer-charge proration rather than
any report value. R7 grades general source quality. R8 grades trajectory-level
input-read scope, which the deterministic verifier-path negative does not
observe. R10 grades only a false user-facing claim about a failed turn, so it
does not duplicate successful-turn protocol checks or any positive judged
criterion.

## Root cause

Solvability. Every graded value follows from `instruction.md`, `schema.md`
and the twelve files in the current snapshot. Hidden turns may vary every
table and transaction file, exactly as the contract announces. All variations
remain inside the documented row shapes, allowed values, referential rules and
October 2025 period. Nothing graded lives only in `solution/` or `tests/`.

Rule interaction. The difficulty is that the rules compose on one bill:
C0014 combines a grandfather split, a tie across the split, and a
rebill from the one order that is grandfather-immune; C0007 combines a
migration, a freeze it breaks, an ordered bank draw, and a residual whose
true-up treatment follows the migrated class; C0016 combines a
migration with a DDC in the repeated fall-back hour and a rebill on its
original class; C0004 combines solar banking, a move-out and the true-up;
C0001 combines a move-in with an extrapolated missing boundary; C0005
combines a rollover with a duplicate read across it; C0017 combines two
channels with a missing boundary on only one; C0021 combines an invalid
customer-premise mapping with all three transaction families.

Exact arithmetic. Interpolated kWh are rational, so intermediates are kept
exact. Each customer-level rounding target is rounded half-up once (toward
positive infinity at exactly .5); rollup totals are sums of the published
customer integers and are not independently re-rounded. Day-level spreading
or mid-calculation rounding changes figures on most customers.

Independence. `solution/solve.py` (class-based, cursor walk over civil
hours) and the reference in `tests/test_output.py` (plain functions over
dicts) are separate implementations of the same contract and agree
byte-for-byte on SAMPLE and every CASCADE, REVERSAL and CHALLENGE turn.

Red lines. No check reads `/app/data` at grade time (the reference
regenerates SAMPLE and materialises each hidden snapshot in verifier-owned
directories); the agent's program runs as `nobody` in its own process group,
which is killed before the check returns.

## Solution shape

1. For every one-shot invocation or session turn, freshly load the twelve
   data files into dataclasses (`Customer`, `Premise`,
   `TariffRow`, `RegulatorOrder`, `Ticket`, `Read`, `Interval`), identify
   customers whose premise maps, and exclude invalid-customer transaction
   lineages from all derived outputs except raw meter and demand row counts.
2. Per customer, derive the service window from move tickets, the migration
   date, and the date the grandfather freeze ends (expiry or migration,
   whichever is first).
3. Per channel: sort reads, resolve duplicate timestamps by greatest
   forward distance, walk each gap hour by hour (counting the repeated
   fall-back hour twice) and spread the rollover-aware delta by seconds,
   keeping only hours inside the service window; extrapolate a missing
   boundary at the nearest gap's rate; flag gaps above 20 times the median
   rate (mean of the two middle rates when the count is even).
4. Label each hour by the class held that day, price it at the schedule in
   force for that day (frozen before the freeze ends), and accumulate exact
   kWh and kWh-times-rate per label.
5. Draw the bank peak first, shrinking each label's value in proportion;
   round each label's exact accumulated energy value once and sum those label
   charges for the customer; compute FAC on the remaining exact kWh.
6. True-up: use the class held at the fiscal true-up instant; RES residue is
   paid at 4 mrcc per kWh, while COM or IND residue is forfeited.
7. Customer charge: exact service-day shares across freeze and migration
   cuts, rounded once.
8. Demand: sum channels per `interval_start`, drop `holiday_off` dates, take
   the maximum with later-string tie-break, price at the schedule and class
   held on the DDC date.
9. Retroactive orders: per label, assumed-prior kWh = label kWh x retro days
   / 31, old and new each rounded, plus old and new demand on the current
   DDC.
10. FTU: current bill at the 2025-10-01 rate plus each retroactive line at
    its own period-start rate.
11. Form each rollup by summing its published per-customer integer fields,
     then emit the nine reports with `sort_keys=True`, `indent=2` and a
     trailing newline.
12. In session mode, parse one exact command at a time, run steps 1-11 with
    no reused snapshot state, replace all nine reports, print and flush the
    exact compact acknowledgement, and continue until EOF.

## Ordered plan

1. Read `/app/data/schema.md` end to end (R1).
2. Inspect each data file, including the cutover-day demand rows, regulator
   order periods, signed FAC values, currency rates and migrated customers.
3. Implement loaders and the tariff lookup with a precedence ceiling, so a
   grandfathered customer never reads a precedence-20 row.
4. Implement hourly interpolation with rollover, duplicates, missing
   boundaries and the repeated hour; check one gap by hand.
5. Implement labels, banking, FAC, true-up and the customer charge; independently
   verify a migrated customer's bank disposition (R3) and one signed-FAC FTU
   conversion (R4) on modified snapshots.
6. Implement demand selection and retroactive lines; independently verify a
   rebill crossing effective windows (R5).
7. Implement FTU conversion and the nine writers, writing only under
   `OUT_DIR` (graded by `negative_writes_outside_out_dir`) and reading only
   under the current `DATA_DIR` (R8), in reviewable Python (R7).
8. Run `python3 /app/out/reconcile.py /app/data /app/out` (R2) so every
   report comes from the program (R9), and cross-check that the class and
   region rollups add up to the summary.
9. Exercise `python3 /app/out/reconcile.py --session /app/out` with at least
   two complete snapshots and a repeated first snapshot. Verify exact compact
   acknowledgements, full report replacement and repeated byte identity.
10. Report in the final message only what was actually run (R10).

## Pitfalls

- Spreading consumption evenly over a day, or rounding the in-period
  share, instead of interpolating by the hour.
- Treating the fall-back day as 24 hours, or failing to parse `T25` rows.
- Reading a rollover as negative consumption.
- Billing C0001 and C0004 for the whole month, or skipping C0004's
  true-up because it moved out.
- Keeping the first of C0010's duplicate reads, or summing both.
- Keeping C0005's numerically highest duplicate (the stuck 99999.998)
  instead of the read furthest forward across the wrap.
- Taking the lower or upper middle rate as C0012's median.
- Ignoring the second channel at P1020 and P88, or extrapolating a missing
  boundary once per customer instead of independently per channel.
- Billing C0021 despite its absent premise, dropping its raw meter and demand
  rows from row counts, or counting its orphan move-out ticket.
- Taking C0015's Oct 13 peak, or picking C0014's earlier tied interval.
- Pricing C0020 from the precedence-20 row that covers its grandfather date.
- Pricing C0016's demand at its `customers.csv` class instead of the class
  held on the DDC date.
- Paying C0007's residual bank as RES instead of using its COM class at the
  fiscal true-up instant.
- Treating active unpublished R-25-22 as a monetary rate change, omitting it
  from the active declaration count, or counting future R-25-21 as active.
- Converting FTU retroactive lines at the 2025-10-01 billing-period rate
  instead of the rate on the first day of the period each line rebills.
- Rounding customer-charge segments separately.
- Rounding one TOU label separately for each tariff row when a staged split
  puts the same label under two rates; accumulate the full label first.
- Assuming shipped customer fields, premise regions, tariff rows, FAC,
  holidays, currency rates, regulator orders or NMB balances remain fixed.
- Caching a prior session turn, merging snapshots as deltas, or leaving stale
  report content in the shared output directory.
- Accepting extra command keys, printing a non-compact acknowledgement,
  failing to flush it, or writing any other stdout text in session mode.
- Sorting customer arrays by string instead of numeric premise suffix, or
  echoing the file order of `customers.csv` or `holiday_calendar.json`.

## Provenance

- Bundle: `f7d89cc0-075a-54eb-baf4-0ffc69556794`, schema version 4.0.
- uuid: f7d89cc0-075a-54eb-baf4-0ffc69556794
- sha256 `solution/solve.py`: 982efad2430b0e75edcb3fe075011114a3d6eb924352c1e4805945049bbf20b7
- sha256 `tests/test_output.py`: 54871e46f90b3d8b7eeaccf6d53f59186cf96e9dd24fa3e1922179b11434dd11
- sha256 `environment/data/schema.md`: f1cbaf573b8c4c0c037f33420a7e0ee9e7b4586aa4c49d72008d1134824a2639
