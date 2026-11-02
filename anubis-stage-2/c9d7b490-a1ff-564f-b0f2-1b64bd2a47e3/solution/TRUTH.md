# TRUTH.md - c9d7b490-a1ff-564f-b0f2-1b64bd2a47e3

## Defect

There is no broken program. `/app/data` holds one backtest extract of a lease
book of 2,400 leases and 2,050 obligors in four regions (39 record, reference
and configuration files, about 157,000 lines) and thirteen rule documents. The
deliverable is a reusable program that rebuilds every characteristic of the
champion scorecard point in time for twelve monthly snapshots, labels each
observation with final knowledge, computes exact rank metrics and writes nine
reports, on unseen extracts too. Every observation figure is the end of a
chain: the booking clock and the daylight table fix the knowledge instant;
the instant filters every bitemporal source; merges known at the instant fix
the obligor; corrected tax ids fix the segment, the bureau join and the
contract segment; the contract segment fixes the roll convention and the
tolerance; the holiday in force fixes the schedule; three cash sources with
per field provenance and returns fix the paid amount; the schedule and cash
fix days past due; lineage and incidents fix quarantine; the version in force
fixes bins and points. A wrong link changes plausible numbers silently.

1. (focal) Point in time knowledge: every characteristic and the candidacy of
   a lease use only records known at the local `06:00:00` cut of the snapshot
   on the booking region's clock, while labels use the watermark. Reading the
   cut in UTC changes 2,120 scores; using the watermark for features changes
   1,255 scores and 388 memberships. Defeats `observation_scores_exact`,
   `cut_instants_and_usage_exact`, `delinquency_bins_exact`.
2. (focal) Days past due with cumulative oldest first allocation and a
   contract segment tolerance; shortfalls carry. A zero tolerance changes 282
   labels and 2,067 scores. Defeats `observation_labels_exact`,
   `delinquency_bins_exact`, `metrics_exact`.
3. (focal) Exact rank metrics: AUC with half credit ties and KS over every
   held score as exact fractions, rounded half to even once in parts per
   million, null on an empty class. Defeats `metrics_exact`,
   `breakdowns_exact`, every held out tier.
4. (focal) Entity resolution: merge chains followed only when effective and
   known at the instant; ignoring them changes 1,246 obligors and 1,814
   `active_leases` bins. Defeats `observation_identity_exact`,
   `obligor_bins_exact`, `holidays_and_merges_exact`.
5. (drift) Cash provenance per field: the bank line governs lockbox date and
   amount, the processor governs card date while the ledger governs card
   amount, the surcharge is never credited, ledger dates are local dates of
   `posted_at` on the booking clock; UTC dates change 578 scores and 85 labels.
   Defeats `observation_scores_exact`, `observation_labels_exact`.
6. (drift) Tax id corrections apply to every date once known, whatever their
   effective date; ignoring them changes 610 scores through the bureau join
   and the contract segment. Defeats `bureau_bins_exact`.
7. (drift) Withdrawn scorecard versions are never used; using `v7b` rescores
   6,300 observations. Defeats `cut_instants_and_usage_exact`,
   `observation_scores_exact`.
8. (trap) Withheld roll convention: commercial agreements roll to the
   following business day, public agreements to the modified following day,
   on the booking region's confirmed holidays. Following for both changes 211
   scores and 15 labels; modified following for both changes 1,392 scores.
   Defeats `delinquency_bins_exact`, `heldout_tier_a_exact`.
9. (trap) Withheld deferral reading: a moved instalment takes the anchor day
   in its new month. Shifting the clamped date changes 77 scores and 9 labels.
   Defeats `observation_labels_exact`, `delinquency_bins_exact`.
10. (trap) Withheld knowledge boundary: a record recorded exactly at the
    instant is known. The exclusive reading changes 28 scores. Defeats
    `observation_scores_exact`, `heldout_tier_c_exact`.
11. (trap) Null, zero and missing: a blank `limit_k` says nothing (an older
    row governs), `0` is `zero_limit`, no row is `missing`; a blank ND score
    on a hit is `thin` while `0.0` is a real score. Treating blank limits as 0
    changes 886 utilisation bins; reading `0.0` as thin changes 95 bureau bins.
    Defeats `obligor_bins_exact`, `bureau_bins_exact`.
12. (trap) Quarantine through the lineage DAG by region and knowledge instant,
    whenever declared, half open, rejected incidents ignored: 3,504
    observations carry a quarantined bin. Defeats
    `exclusions_and_quarantine_exact`, `observation_scores_exact`.
13. (trap) Vendor precedence by observation segment on same day pulls;
    disputes known at the instant remove a pull; age at most 180 days.
    Swapping the lists changes 431 bureau bins. Defeats `bureau_bins_exact`.
14. (trap) Return codes: only codes marked `yes` reverse, and only when both
    the return and its posting are known. Reversing every code changes 1,212
    labels. Defeats `observation_labels_exact`, `unresolved_and_partition_exact`.
15. (trap) Exclusion order and spans: `prior_charge_off` before
    `holiday_active`, the deferral span half open; dropping exclusions moves
    the population from 18,531 to 19,197. Defeats
    `exclusions_and_quarantine_exact`, `metrics_exact`.
16. (trap) Rejects contract: amounts must carry exactly two decimals,
    invoice numbers resolve through the notices, late records are counted and
    never rejected. Defeats `rejects_and_record_counts_exact`.
17. (trap) Invalid lifecycle types: `lease_events.jsonl` carries named events
    outside the valid set (`SUSPEND`, `RESUME`, `RESTRUCTURE`, `HOLD`). Only
    `ACTIVATE`, `BUYOUT`, `PAYOFF`, `CHARGE_OFF` and `VOID` are valid; any other
    type is an invalid transition, ignored in the state replay and rejected with
    reason `invalid_transition`. They change no lease state, so a solver that
    treats them as real transitions drops observations, and one that silently
    ignores them omits 219 `invalid_transition` rejects. Defeats
    `rejects_and_record_counts_exact`, `observation_identity_exact`.
18. (trap) Distractor document: `ops_cheatsheet.md` is an informal desk sheet,
    listed in `data_index.md` as superseded and not part of the contract, that
    states the discredited shortcuts (score at month end, cut at midnight UTC,
    newest bureau pull regardless of age, delinquent one cent short, roll
    weekends to Monday, blank limit as zero, ledger UTC posting date). A solver
    that trusts it rather than the rule documents reproduces the wrong readings
    the what if figures and the held out tiers punish. It governs nothing and no
    report depends on it. Reinforces `observation_scores_exact`, every held out
    tier and `negative_reports_not_from_program`.

| trap | firing records | graded value that changes |
|---|---|---|
| booking clock and daylight cut | 48 cut instants, 875 boundary records in the run log, 14 planted per graded cut | 2,120 scores |
| watermark leakage | 388 late activations, branches, obligors and back dated rows | 1,255 scores, 388 memberships |
| merge chains | 144 merged obligors, 18 percent recorded late | 1,246 obligors, 1,814 lease count bins |
| tolerance carry | 16 percent of leases short paying | 282 labels |
| return codes | 1,602 reversed payments, NOC codes, 19 unknown postings | 1,212 labels under the all reverse reading |
| per field provenance | 17,749 lockbox, 9,233 card, 24,997 ACH payments, corrections and keying errors | 578 scores under UTC dates |
| tax id corrections | about 80 obligors with a wrong CRM tax id | 610 scores |
| withdrawn version | `v7b` effective for the last three snapshots | 6,300 scores |
| roll conventions | month end anchors on 30 percent of leases, 5,965 public observations | 211 scores, 15 labels |
| deferral anchor | 593 governing holidays, 15 decisive notices | 77 scores, 9 labels |
| inclusive boundary | records recorded exactly at graded cuts | 28 scores |
| null zero missing | 407 zero limits, blank limits, 652 thin, 603 no hit, 546 missing bureau | 886 and 95 bins |
| quarantine | 7 confirmed incidents, 1 rejected, half open windows | 3,504 observations |
| exclusions | 273 prior charge off, 611 holiday active | population 18,531 |
| rejects | 155 lockbox, 69 card, 34 plus 12 lease event, 77 relief, 19 return rejects | `rejects` |
| invalid lifecycle types | 219 SUSPEND/RESUME/RESTRUCTURE/HOLD events on known leases | 219 `invalid_transition` rejects |
| duplicates and late records | 653 duplicate lines, 489 late records | `duplicates`, `late_records` |

Out of bounds: no recovery, decoding or reverse engineering is involved. The
corpus is clean data with documented conflicts, and the three withheld
conventions are each reproduced by exactly one reading of shipped evidence.

## Load-bearing work

The per observation chain decides the score: knowledge instant on the booking
clock, candidacy from the lease events known then, branch and obligor known
then, merge resolution, corrected tax id and observation segment, holiday in
force and schedule under the contract segment's convention, cash known then
under per field provenance and returns, days past due with carried
shortfalls, obligor exposure and limit, bureau pull choice, sector,
quarantine through lineage, the version in force, then the label from final
knowledge and the exact rank metrics over the population.

## Verification

Test channel (`tests/test_output.py`, 35 checks, positive total 100): weight 5
`observation_scores_exact`, `observation_labels_exact`,
`observation_identity_exact`, `metrics_exact`, `identity_triangle_closes`,
`heldout_tier_a_exact`, `heldout_tier_b_exact`, `heldout_tier_large_exact`,
`heldout_tier_d_exact`, `heldout_tier_f_exact`, `heldout_tier_g_exact`,
`heldout_tier_h_exact`, `heldout_tier_i_exact`;
weight 3 `delinquency_bins_exact`, `bureau_bins_exact`, `obligor_bins_exact`,
`exclusions_and_quarantine_exact`, `cut_instants_and_usage_exact`,
`holidays_and_merges_exact`, `rejects_and_record_counts_exact`,
`unresolved_and_partition_exact`, `breakdowns_exact`,
`heldout_tier_c_exact`, `heldout_tier_j_exact`; weight 1
`reports_parse_with_contract_keys`, `identity_self_report_matches`. Negative
checks: `negative_hardcoded_sample_answers` (-5),
`negative_reports_not_from_program` (-5), `negative_nondeterministic_output`
(-3), `negative_depends_on_directory_name` (-3),
`negative_depends_on_record_order` (-3), `negative_writes_into_inputs` (-3),
`negative_extra_output_files` (-1), `negative_float_figures` (-1),
`negative_partial_output_on_missing_input` (-3); negative total 27. Held out
tiers regenerated inside the checks, each exercising the general program on
parameters the shipped extract never shows: A 520 leases, six monthly snapshots
from 2025-03-01, a 120 day window and bad at 45 days; B 600 leases, five
quarterly snapshots from 2024-07-01 scored by one version, a 90 day window,
equal tolerances, a 2022 ledger year; C 260 leases, snapshots on the 9th with
the first on the 2025 daylight change day; E 3,600 leases; D 700 leases, eight
snapshots two months apart, a 150 day window and bad at 90 days; F 640 leases,
ten monthly snapshots with equal tolerances; G 560 leases, snapshots on the
29th from a leap year; H 600 leases, four quarterly snapshots, a 300 day window
and a commercial tolerance above the public one; I 1,500 leases with a 60 day
bureau age limit; J 520 leases, snapshots on the 10th with a 100 day window.
Every run of the program has a 300 second limit and runs as `nobody`.

Judge channel (`tests/judge.toml`, 31 criteria, positive total 87, negative
total 22): R1 to R10 the ten what if figures, R11 to R13 the three withheld
readings with their evidence, R14 to R21 derivation evidence, R22 program
structure, R23 measured run time, R24 to R31 negatives.

The reference closing message states: (1) 2120 observations, auc_ppm 850203,
24637 observations; (2) 1255, 847965, 8262; (3) 1246, 1814, 848134; (4) 6300,
11972, 844208; (5) 1866, 282, 846499; (6) 2768, 1212, 844242; (7) 3504,
861965, 561397; (8) 1657 instalments, 15 labels, 1596 bad; (9) 19197, 847330,
533392; (10) 431, 10847, 846286. The settled run has auc_ppm 846783, ks_ppm
531440 and 24640 scored observations. The oracle score, tests only, is 1.000;
no judged channel score exists for the oracle.

| requirement | artifact | checks (weight) | criteria |
|---|---|---|---|
| reusable program on unseen extracts | `derive_report.py` | heldout_tier_a_exact (5), heldout_tier_b_exact (5), heldout_tier_c_exact (3), heldout_tier_d_exact (5), heldout_tier_f_exact (5), heldout_tier_g_exact (5), heldout_tier_h_exact (5), heldout_tier_i_exact (5), heldout_tier_j_exact (3) | R20, R22 |
| 300 second run limit | `derive_report.py` | heldout_tier_large_exact (5) | R23 |
| exact scores | region files | observation_scores_exact (5) | R1, R2 |
| exact labels | region files | observation_labels_exact (5) | R5, R6 |
| observation set, region, obligor, segment, version | region files | observation_identity_exact (5) | R3 |
| exact rank metrics | summary, region, segment | metrics_exact (5) | R19 |
| one total across regions, segments, snapshots | summary, region, segment | identity_triangle_closes (5) | |
| identity residuals self reported | data_quality | identity_self_report_matches (1) | |
| delinquency bins | region files | delinquency_bins_exact (3) | R14, R12 |
| bureau bins | region files | bureau_bins_exact (3) | R17, R10 |
| obligor level bins | region files | obligor_bins_exact (3) | R18 |
| exclusions and quarantine | region files, policy_audit | exclusions_and_quarantine_exact (3) | R7, R9 |
| cut instants and version usage | policy_audit | cut_instants_and_usage_exact (3) | R16, R4 |
| holidays and merges | policy_audit | holidays_and_merges_exact (3) | R3 |
| rejects with closed reasons, late records, duplicates | data_quality | rejects_and_record_counts_exact (3) | |
| unresolved, partition, payments | data_quality | unresolved_and_partition_exact (3) | |
| breakdowns and bands | summary, segment | breakdowns_exact (3) | |
| contract keys | all reports | reports_parse_with_contract_keys (1) | |
| integers, never floats | all reports | negative_float_figures (-1) | R30 |
| reports written by the program | all reports | negative_reports_not_from_program (-5) | |
| deterministic bytes | program | negative_nondeterministic_output (-3) | |
| independent of path and record order | program | negative_depends_on_directory_name (-3), negative_depends_on_record_order (-3) | R20 |
| never change DATA_DIR | program | negative_writes_into_inputs (-3) | R25 |
| only nine files in OUT_DIR | program | negative_extra_output_files (-1) | |
| missing input writes nothing | program | negative_partial_output_on_missing_input (-3) | |
| parameters from the extract | program | negative_hardcoded_sample_answers (-5) | R22 |
| no installs, data untouched | trajectory | | R25, R26 |
| ten what if figures | closing message | | R1 to R10, R21, R27, R28, R30 |
| withheld readings and evidence | closing message | | R11, R12, R13, R15 |
| measured run time | closing message | | R23 |

## Root cause

**Crux.** A score is right only when every characteristic is rebuilt from
what was known at the snapshot's local cut instant on the lease's booking
clock, while the label it is judged against uses everything known at the
watermark; the leakage free and the leakage full readings both give a
plausible AUC near 0.85.

**Spine.** The per lease delinquency state as known at the knowledge instant:
the cash known then laid over the schedule known then, under the contract
segment's convention and tolerance. It feeds three of seven bins, the score,
approval, the holiday exclusion, the final label (with the watermark), the
population and every metric, breakdown and band.

**Interaction matrix.** The booking clock feeds the instant; the instant
filters events, branches, obligors, merges, corrections, holidays, cash,
returns, bureau, disputes and limits; merges feed the obligor, which feeds
`active_leases`, exposure, limit, sector, segment and the prior charge off
exclusion; corrected tax ids feed the segment, the bureau join and the
contract segment; the contract segment feeds the roll and the tolerance; the
holiday feeds the schedule and the holiday exclusion; the region on the as of
date feeds quarantine and the regional reports; the observation segment feeds
points, cutoff and vendor precedence.

**Withheld rules.** The roll convention per contract segment: evidence the
printed due dates of `invoice_notices.csv`, where only following for
commercial and modified following for public reproduces every notice (the
closest wrong pair misses 272). The deferral anchor: evidence the reissued
notices of deferred instalments, where shifting the clamped date misses 15 and
shifting the rolled date misses 102. The inclusive boundary: evidence the 875
`BOUNDARY` lines of `snapshot_runs.log` recorded exactly at a cut, all
`ADMIT`, with `DEFER` one second later.

**Red lines.** No answer key in the image; every expected value is recomputed
in the checks from a regeneration of the corpus by an independent model of
the rules; agent code runs as `nobody` with a time limit; `/tests` is not
readable by agent code.

## Solution shape

`solve.py` loads every file with the standard library, checks that every
required input and ledger year exists before writing anything, builds the
clocks, holidays, references and lookups, replays lease events and holiday
requests per knowledge instant with caching, groups leases by surviving
obligor per instant, rebuilds each observation's characteristics through a
closed form days past due function evaluated at the day before each payment
and at the window end, scores against the version in force, labels with the
watermark, and computes AUC and KS with sorted scores and exact fractions.
All nine reports come from one list of observations so the identities close
by construction.

## Ordered plan

1. Read `backtest_run.toml`, `region_clock.ini`, `holiday_calendar.ics`; compute snapshots and cut instants (policy_audit).
2. Read `branches.ini`, `lease_branch_history.csv`, `leases.csv`; resolve booking and reporting regions (region files).
3. Read `obligors.csv`, `obligor_events.jsonl`, `public_entity_register.csv`; build merges, corrections, sectors and segments (region files).
4. Read `lease_events.jsonl`; replay versions and states per instant (candidates, rejects).
5. Read `relief_approvals.csv`, `servicing_policy.ini`; replay requests and holidays (policy_audit holidays, exclusions).
6. Compare `invoice_notices.csv` with computed schedules to settle the roll convention and the deferral anchor (schedules).
7. Read `snapshot_runs.log` to settle the knowledge boundary (every characteristic).
8. Read the four lockbox files, `card_settlements.csv`, every `servicing_ledger_*.jsonl`, `ach_returns.log`, `return_codes.ini` (cash, rejects, payments).
9. Implement days past due with tolerance and carried shortfalls (delinquency bins, labels).
10. Read `bureau_kr.jsonl`, `bureau_nd.csv`, `bureau_vendors.ini`, `bureau_disputes.json` (bureau bins).
11. Read `credit_limits.csv`, `sector_reference.json` (utilisation and sector bins).
12. Read `feature_lineage.yaml`, `data_incidents.json` (quarantine).
13. Read `scorecard_registry.json` and the version files, `exclusion_policy.yaml` (scores, approvals, exclusions).
14. Label with the watermark; compute metrics with `score_bands.yaml` (all reports).
15. Write the nine reports; rerun on altered copies and on one reading changed per figure (closing message).

## Pitfalls

| rank | failure mode | rule violated | check that catches it | weight at stake |
|---|---|---|---|---|
| 1 | features filtered by effective date only, records known later leak in | knowledge instant | observation_scores_exact, delinquency_bins_exact, every tier | 54 |
| 2 | cut read in UTC or on the current region's clock | booking clock | cut_instants_and_usage_exact, observation_scores_exact, heldout_tier_c_exact | 11 |
| 3 | one roll convention for every lease | withheld convention | delinquency_bins_exact, observation_labels_exact, every tier (all but C when following is used everywhere) | 51 to 54 |
| 4 | tolerance per instalment or none | carried shortfalls | observation_labels_exact, metrics_exact | 10 |
| 5 | ledger used for every payment, UTC dates | per field provenance | observation_scores_exact, observation_labels_exact | 10 |
| 6 | merges applied at effective date or ignored | merge knowledge | observation_identity_exact, obligor_bins_exact | 8 |
| 7 | AUC with ties counted 0 or 1, float rounding | rank metrics | metrics_exact, breakdowns_exact | 8 |
| 8 | blank limit read as 0, ND 0.0 read as thin | null zero missing | obligor_bins_exact, bureau_bins_exact | 6 |
| 9 | withdrawn version used | released only | cut_instants_and_usage_exact, observation_scores_exact | 8 |
| 10 | every return code reverses | return codes | observation_labels_exact, unresolved_and_partition_exact | 8 |

The top three modes carry more than a third of the 100 positive test weight.

## Provenance

```yaml
uuid: c9d7b490-a1ff-564f-b0f2-1b64bd2a47e3
instance_id: c9d7b490-a1ff-564f-b0f2-1b64bd2a47e3
task_name: terminal-bench/c9d7b490-a1ff-564f-b0f2-1b64bd2a47e3
fix_patch_sha256: d5e2b59ce9110d74747b6cf89f840d37e9bf371d7dde3c046b3a59c94dedc65e
solve_py_sha256: 562a3254416ac8c906ef33c2c4dc74c1b7a15fa57e79d1ae3cb15e63a80a4cfd
language: python
status: verified
```
