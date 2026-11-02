# TRUTH.md - d4e8c327-7a91-5b4c-9d2f-83f1a0e65b1e

## Defect

The corpus describes twenty-six fortnightly berth allocation cycles at a four-terminal container port. Claims use up every berth-hour the terminal supplies in 102 of the 104 terminal cycles, so the cycles have to be apportioned and the unmet part of each claim becomes a demurrage lot that is carried, cut, discharged, cleared or expired by the rules in `demurrage_rules.md`. The work is wrong in the following ways that the corpus sets up, each of which the tests catch.

1. Shared fill level. `priority_rules.md` pays honoured minimums first, then raises one shared level on top of each paid minimum, capped at the largest unmet claim, then hands out the indivisible remainder one berth-hour at a time by largest unmet claim, governing NOR instant, charterer and NOR reference. Proportional sharing (the withdrawn handbook) or another remainder order moves grants in most binding cycles.
2. Carried demurrage. Unmet laytime becomes a lot that attaches to the charterer at that terminal. On the shipped corpus 167 ledger rows carry demurrage in (3260 berth-hours in total), so dropping the lot changes claims, grants and the whole spine.
3. Ceiling cut. When laytime plus carried lots exceeds the charterer's ceiling in `ceiling_register.csv` (named by `ceiling_source` in `derivation_policy.ini`), the carried lots are cut first and then the current laytime. This happens on 21 shipped ledger rows.
4. Withheld survival age. `demurrage_settlement.log` records, for lots raised in one cycle, whether they still stood at the opening of later cycles. Only one survival age fits every line: 3 on the shipped corpus. Lots older than that expire at the opening of a cycle (20 expiries on the shipped corpus).
5. Withheld weather-stoppage convention. `laytime_observations.log` records observation windows, the adverse weather inside them and the laytime hours actually counted. Counting the window hours under SHEX, SHINC and WWD (defined in `laytime_rules.md`) leaves SHEX as the only reading that fits every line; WWD fits none and SHINC fits only the weekday windows. The governing laytime is still the first `laytime_hours` column of the NOR log, so the convention is reported in `policy_audit.json` and moves no figure.
6. Duplicate column. The NOR log header carries `laytime_hours` twice; the first column by position governs. The second differs on 29 rows.
7. Clearing. A terminal cycle that ends with capacity unused clears every lot standing at that terminal (4 lots on the shipped corpus, 44 on extract A, 100 on extract B).
8. Declarations read at run time. The ceiling source, the cutover instant, the unit, the admission instant, the declared row counts, the survival age and the weather reading all come from the corpus. Extract A changes the scale (33 Notices removed, capacities rescaled), the ceilings, the minimums, the cutover instant, the declared counts, the marker lines, the survival age (2) and the weather reading (SHINC). Extract B leaves berth-hours unused in 53 of 104 cycles, settles survival 4 and WWD.

Rules that the contract states but that no graded corpus triggers: the pilotage substitution walk (every factor is 1 and every window is open, so every Notice is served at its booked berth with zero hops), port circular application (the circular rows carry no target), the NOR state machine (every claim is ACCEPTED), epoch and alias resolution (every Notice already carries a canonical identity), admission filtering (no row is recorded after 2033-01-15), the out-of-scope lists (every Notice is in horizon with a known charterer) and reason precedence (every row carries `NONE`). The tallies for those rules are the marker counts that `output_contract.md` defines.

## Out of bounds

The module must not hold stored answers as code literals (`negative_hardcoded_sample_answers`), must not embed corpus records (`negative_embedded_corpus_rows`), must produce the same bytes on a rerun (`negative_nondeterministic_rerun`), must respond to the corpus it is handed (`negative_output_independent_of_the_corpus`), must not depend on the corpus directory name (`negative_module_reads_a_fixed_corpus_path`), must raise when a source file is missing (`negative_silent_recovery_from_missing_source`), must leave only the module and the nine documents in `/app/out` (`negative_output_directory_has_extra_files`), must leave the corpus untouched (`negative_module_mutates_the_corpus`) and must not import network or process modules (`negative_module_opens_network_or_shells_out`).

## Load-bearing work

Load the declarations, settle the two withheld rules by enumeration, read the NOR population by column position, walk the twenty-six cycles terminal by terminal expiring lots, cutting at the ceiling, allocating with minimums, shared level and remainder, discharging lots oldest first, raising new lots and clearing at surplus terminals, then write the nine documents with running sums and the marker tallies.

Measured on the shipped corpus: 208 ledger rows (195 PARTIAL, 13 FULL), granted 7023, claim 11214, demurrage 4191, capacity 7105, residual 82, 50 terminal cycles where the remainder step handed out at least one berth-hour, running demurrage maximum 312, cutover sides 56 before and 152 after, minimums honoured in full on 45 rows with 5 agreements unmatched.

## Verification

Tests: 28 checks, 19 positive (3 at weight 5, 13 at weight 3, 3 at weight 1, total 57) and 9 negative (3 at -5, 3 at -3, 3 at -1, total 27). Judge: 21 criteria, 14 positive (7 at weight 5, 3 at weight 3, 4 at weight 1, total 48) and 7 negative (3 at -5, 1 at -3, 3 at -1, total 21). `reward.toml` weights are 0.5/57 for the tests and 0.5/48 for the judge.

| Behaviour | Where | Test | Criterion |
|---|---|---|---|
| Ledger backbone: charterer, segment, berth, laytime, ceiling, claim | terminal documents, shipped plus extracts A and B | region_ledger_backbone_exact | none |
| Demurrage spine | terminal documents, shipped plus A and B | cumulative_demurrage_spine_exact | none |
| Cycle capacity, fill level, minimums, grant, residual, count, binding | terminal documents, shipped plus A and B | terminal_cycle_capacity_and_fill_exact | none |
| Berth-hour figure under the declared unit and honoured minimum | terminal documents, shipped plus A | granted_berthhours_and_minimum_exact | none |
| Outcome and reason | terminal documents, shipped plus A and B | outcome_and_reason_vocabulary_exact | none |
| Served berth and hops | terminal documents, shipped plus A | substitution_served_berth_and_hops_exact | none |
| Identities inside each terminal document | delivered terminal documents | cross_artifact_identity_triangle_holds | none |
| Row order independence | extract A rerun with rows rotated | row_order_permutation_changes_nothing | none |
| Marker tallies | policy audit, shipped plus A | policy_audit_marker_tallies_exact | none |
| Minimum tallies | policy audit, shipped plus A | policy_audit_minimum_tallies_exact | none |
| Lot expiries and clearings | policy audit, shipped plus A and B | policy_audit_lot_tallies_exact | none |
| Binding cycles and cutover sides | policy audit, shipped plus A | policy_audit_capacity_and_cutover_exact | none |
| Settled readings | policy audit, shipped plus A and B | policy_audit_withheld_readings_exact | R16 and R17 penalise a contradicted reading in the message |
| Source counts | data quality, shipped plus A | data_quality_source_counts_exact | none |
| Anomaly tallies | data quality, shipped plus A | data_quality_anomaly_tallies_exact | none |
| Segment rollups | segment documents against the module's own ledger | segment_rollups_exact | none |
| Summary totals | summary against the module's own documents plus sealed counts | summary_totals_exact | none |
| Documents present | output directory | artifacts_present_and_parse | none |
| Runs on an unseen corpus | extract A | program_runs_and_exits_clean | R12 for the run over /app/data |
| Seven closing pairs | message | none | R1 to R7 |
| Evidence that settled each withheld rule | message | none | R8 and R9 |
| Enumeration of candidates | trajectory | none | R10 |
| Binding cycle checked against the rules | trajectory | none | R11 |
| Standard library only | module | none | R13 |
| Code quality | module | none | R14 |
| Verifier files left alone | trajectory | none | R15 |
| Withdrawn handbook ignored | module | none | R18 |
| Canonical identities in the message | message | none | R19 |
| Message present | message | none | R20 |
| No looping on a failing command | trajectory | none | R21 |

The stored-answer negatives are exclusive: a module caught by `negative_hardcoded_sample_answers` is not charged again by `negative_embedded_corpus_rows` or `negative_output_independent_of_the_corpus`, so one act costs at most five points in the test channel.

## Root cause

Every figure depends on the earlier ones: the lots carried into a cycle depend on every earlier grant at that terminal, and the grants depend on the ceiling cut of those lots. A module that gets one cycle wrong carries the error forward.

**Red lines.** The contract documents and the four declaration files are the only authority. The withdrawn handbook governs nothing. The corpus is read only, the output directory holds exactly nine documents and the module, and the module must reproduce itself on an unseen extract.

## Solution shape

`solve.sh` copies `solve.py` to `/app/out/apportion_berth.py` and runs it over `/app/data`. The module checks that every corpus file it reads exists and raises otherwise, reads the declaration files with `configparser`, reads the NOR logs by position, settles the weather convention by counting window hours under each candidate and the survival age from the carried and expired gaps, counts the marker tokens the contract names, and then walks the cycles in `run_ledger`: expiry at the opening of each cycle, ceiling cut of carried lots first, allocation in `allocate_cell`, discharge oldest first, new lots for unmet laytime, clearing at terminals with capacity left. `build_terminals`, `build_summary`, `build_segments`, `build_policy_audit` and `build_data_quality` write the nine documents with sorted keys so a rerun produces the same bytes.

## Ordered plan

1. Read `corpus_index.md`, `output_contract.md`, `reason_codes.json` and the rule documents.
2. Read `derivation_policy.ini`, `unit_declarations.ini` and `source_declarations.properties`.
3. Settle the weather-stoppage convention from `laytime_observations.log` and the survival age from `demurrage_settlement.log`.
4. Read the NOR logs, taking the first `laytime_hours` column by position.
5. Load capacities, the ceiling register named by `ceiling_source`, minimums and the priority register.
6. Walk each cycle and terminal: expire lots, cut at the ceiling, allocate, discharge, raise new lots, clear at surplus terminals.
7. Write the terminal, segment, summary, policy audit and data quality documents.
8. Rerun to confirm identical bytes, then compute the seven closing pairs by rerunning the walk with each change applied.

## Reference closing message

I ran `python3 /app/out/apportion_berth.py --data /app/data --out /app/out`, which exited with status 0 and wrote the nine documents. The weather-stoppage convention was settled by `laytime_observations.log`: counting each window under SHEX matches every line, SHINC misses the Sunday windows and WWD misses every line. The survival age was settled by `demurrage_settlement.log`: every lot is carried at gaps of 1 to 3 cycles and expired at a gap of 4, so lots survive 3 cycles.

First, had carried demurrage been ignored, the total granted berth-hours would be 6955 and 14 ledger rows would change outcome. Second, under WWD, the rival reading every observation contradicts, 0 Notices would have a different governing laytime and the total granted would be 7023. Third, with the survival age extended to 4 cycles, 16 lots would expire and the total running demurrage at the end of H26 would be 4191. Fourth, with the clearing rule never applied, the total running demurrage at the end of H26 would be 4516 and 4 ledger rows would have a different grant. Fifth, the indivisible remainder step hands out 50 berth-hours and hands out at least one in 50 terminal cycles. Sixth, lifting the admission instant would let 0 Notices claim, for a total of 0 berth-hours, because no row is recorded after it. Seventh, applying the unendorsed port circulars would change the governing laytime of 0 Notices and the fill level of 0 terminal cycles, because no circular names a row it amends.

## Pitfalls

Measured by changing one thing in `solve.py` and scoring the test channel out of 57.

| Pitfall | Test points kept |
|---|---|
| Proportional sharing from the withdrawn handbook | 30 |
| Carried demurrage dropped | 27 |
| Ceiling register ignored | 33 |
| Remainder handed to the smallest unmet claim first | 33 |
| Second `laytime_hours` column read | 36 |
| Fill level reported with the minimum folded in | 52 |
| Survival age or weather reading hard-coded | 54 |
| Cutover instant hard-coded | 54 |
| Clearing rule never applied | 24 |

## Provenance

```yaml
uuid: d4e8c327-7a91-5b4c-9d2f-83f1a0e65b1e
instance_id: d4e8c327-7a91-5b4c-9d2f-83f1a0e65b1e
task_name: terminal-bench/d4e8c327-7a91-5b4c-9d2f-83f1a0e65b1e
fix_patch_sha256: 05eefefdb13520d545624e09b5ccefcba2c56a967f9069c86f8d977cf0dbae7d
solve_py_sha256: 05eefefdb13520d545624e09b5ccefcba2c56a967f9069c86f8d977cf0dbae7d
language: python
status: complete
```
