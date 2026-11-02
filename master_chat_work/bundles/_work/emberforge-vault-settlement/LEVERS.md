# LEVERS (round 1, after hardening)

Round 0 (the old 34-check suite against the run) is in `LEVERS_round0.md`. Round 1: 50 checks, positive total 155, negatives -7. Every value check runs the delivered program on a season the grader builds under a draw of its own (`seasons_r1.json`). Scores are tests-only, method (b), from `baselines.json`.

| lever | id | rules (files) | checks | points | S3_k (score, points lost) |
|---|---|---|---|---|---|
| cap and floor at one forge | LV-EF-1 (A) | A4, V4, N3 | `cap_and_floor_{one,two}_*`, 10 | 38 | 0.7548, 38 (only its own) |
| retired reagent | LV-EF-2 (A) | V9, A4, S3, N3, finding_codes | `retired_reagent_{one,two}_*`, 10 | 38 | 0.7548, 38 (only its own) |
| consumed reference | LV-EF-3 (A, B) | register, N3, A4, V8 | `consumed_reference_{one,two}_*`, 10 | 38 | 0.7548, 38 (only its own) |
| requisition ladder | LV-EF-4 (D, E) | Q1 to Q8, Q5 closing balance, time bound | `requisitions_{12,24,48_first,48_second}_allocation`, 4 | 18 | 0.9032, 15 (the 12 rung passes) |
| draw recovery | L2 (B) | instruction, calibration_slice, register | every value check | 150 | 0.0323 |
| scarcity fixed point | L1 (B) | V8 | all seasons | | 0.6839, 49 |
| identity | L4 | I2 to I4 | every season | | 0.0516 |
| E3 / S6 | L5 / L6 | E3, S6 | gate the slice search | | 0.0065 / 0.0065 |
| settlement order | L8 | N1 | seasons whose ledger file order differs | | 0.4903, 79 |
| written form | L9 | record_shapes.md | `structure_canonical_serialisation` | 1 | 0.9935, 1 |
| isolated rules | | Q8, A4, A2/N6, E1/V2, I2, quiet rules | 6 x w3 | 18 | paid to S4 |
| structure | | instruction | 5 x w1 | 5 | paid to S4 |

Status against the run: the run's program, made to read only the published slice (no reference bundle), scores 0.1677: it loses all of LV-EF-1, LV-EF-2, LV-EF-3 and the 24 and 48 rungs of LV-EF-4 (all HELD), and keeps the structure, the 12 rung and the isolated-rule checks. Unmodified, it stops on the missing `calibration_reference_bundle.json` and scores 0.0065.

Underivability on the labelled visible data (the published slice, `underiv_r1.txt`): every counted lever (LV-EF-1..4) is HIDDEN-ONLY. LV-EF-1 and LV-EF-2 are also planted, unlabelled, in the shipped season (L0305 bulk order; R14 retired from P05), so the facts the judge reads depend on them.

P12 r2 (22 Oct 2026): `structure_canonical_serialisation` (w1) now also grades key order (record_shapes.md:21); `cap_boundary_workshop_figures` (cl_cap) now also lands one charge exactly on its cap (A4), and `quiet_rules_findings` (cl_quiet) now has a workshop opened on the first day and one closed on the last day (A2). Weights unchanged (positive 101, negatives -14). Single-rule mutants `>= cap`, `opened_day >=`, `closed_day <=` each lose 3 of 96 content points; the oracle loses 0.

P12 r3 (23 Oct 2026): plan24_mix (LV-EF-4, 24 rung) now has one workshop (hall_01) file a second requisition, last in file order, same charter, priority 4; the earlier one is funded, so its workshop and guild `allocated_units` are the sum over both (record_shapes.md:92, :104-106). Weights unchanged; no new check. A program that keeps one requisition's grant per workshop (overwrite in file order) now fails `plan24_mix_findings_and_workshops` and `plan24_mix_guilds_and_allocation`; the fixed oracle passes all 12 seasons (scratch run, each season under 0.2 s).

## Harden lp1 r1 (23 Oct 2026, LEVER_PLAN_v1)

Retired as leaked (the v0 run, replayed with only its draw recovery swapped to council_rulings.json, scores 0.8614 on the r2 suite): LV-EF-1 composition of A4 refusals, LV-EF-2 retired reagent V9, LV-EF-3 consumed reference, LV-EF-4 requisition ladder, LV-EF-5 decoy window, L8 every-condition finding. Their rules stay written and are still read by every whole-document check, but they no longer carry weight of their own. Giveaway text removed: E3 explanation paragraph, S2 bold explanation and "admitted forges" title, V9 "never stands in" sentences, I3 closing sentence, instruction request for figures in the final message.

Focal levers (variant engines = solve.py with one lever read the reflex way; tests-channel scores from OUT/evidence/score_var_*.json, on the 81-point suite before the w1 rerun check was added):

| Lever | Rule text (file:line) | Reflex reading | Hidden cases | Checks the wrong reading fails | Variant score |
|---|---|---|---|---|---|
| L7 per-unit charge | rulebook_charge.md:14 "The base value of a forge entry is the base charge of the artifact it forges"; :39-43 operators apply to the base value, each yields a whole number, "The charge of the entry is the value the last operator yields, multiplied by the number of units the entry forges." | base charge x units, then the three operators with a reduction at each step (the v0 program, charge_of line 449) | every multi-unit forge whose operator step lands off whole ember; caps in forge_a..d sit close enough that the charge difference moves closures | whole_summary, whole_reconciliation, whole_workshop_reports, whole_guild_reports, unit_charge_season_total, cap_release_closures, mutation_family_multiplier, mutation_grade_step | 37/81 = 0.4568 |
| L3 cap ledger (stateful stream) | rulebook_admission.md:34-38 A4 accrued settled charge (global default); rulebook_salvage.md:40-46 S5 "the charge of its source forge leaves the accrued settled charge of the workshop that filed that forge, for every forge entry settled after the salvage" (exception in another section) | accrued = running sum of settled charges; a credited salvage never moves it | a workshop whose earlier forge is credited by a salvage before a later forge tests a cap set between the two readings (iso_cap_release via _release_on_the_line; forge_a..c through the tight caps) | cap_release_closures; whole_* on 3 of 4 forge seasons (credit 0.25 each, allocation 0.75) | 40/81 = 0.4938 |
| L6 scope by definition | rulebook_salvage.md:14-16 S2 "among the last three live forge entries of the same artifact family settled for the same canonical smith on days strictly before the salvage's own day"; invariants.md:10 Terms "Live forge entry. A settled forge entry that no salvage has yet been credited against." Loud text in S2 (strictly before, canonical smith, own window per family) covers other traps | window over every settled forge of that family | a smith whose same-family forge already credited sits among the last three before a later salvage, pushing the source to fourth (_live_window, planted in forge_a..d and iso_live_window) | live_window_refusals, merge_chain_smith_rows, whole_summary, whole_vault_audit, whole_reconciliation, whole_data_quality, whole_workshop_reports, whole_guild_reports (allocation 0.25) | 21/81 = 0.2593 |

All three read the reflex way (REFLEX engine): 7/81 = 0.0864. v0 agent program (adapted draw recovery): see OUT/STACKING_CHECK.md. L1 not used: no shipped control figure exists in the data to describe as a parse or count control.

Shipped data never contradicts the hidden cases: no truth figure is shipped; on the shipped season L7 and L3 already move figures, L6 does not fire (W5).

### lp1 r1 QC pass (13:15): suite cut to 54 points
QC kit 71a653b2 failed the 82-point suite on tests_qc W2 (weights only -5,-3,-1,1,3,5), R3, and judge_qc J5/J10/J11/J13/G3. Fixes: whole_* w8 -> w5; dropped structure_records_delivered, priority_tie_allocation, merge_chain_smith_rows (and seasons cl_priority, cl_identity); structure_canonical_serialisation now on hidden forge_a; judge R4 w3, R5 -1, new R8 reads grader files -3, R1 wording. Final: 20 checks, 16 positive totalling 54 (whole 35 = 64.8%, isolated 15 = 27.8%, structure 4 = 7.4%, shipped-only 1 = 1.9%), negatives -8; judge 8 criteria, 12 / -10; reward.toml 0.5/54, 0.5/12. Penalty groups: replay 5, scope 4, network 3, honesty 3, grader read 3. Tests-channel local: oracle 54/54, adapted agent 5.25/54 = 0.0972, REFLEX 0.0741, L7 0.4074, L3 0.5046, L6 0.3194. D14 note: the Q8 tie and merge chain rules are no longer isolated either; they stay graded inside the whole documents (forge_* seasons carry ties and merges). Validator advisory: 1.12, 15.5, 15.7 as before; 11.4 (nondeterministic negative recommended) left by design: G4 keeps negatives to cheating acts, and byte-identical reruns are graded by the positive structure_reruns_byte_identical on a hidden season.

## P12 r4 QC fix effects (23 Oct 2026)

| Fix | L7 | L3 | L6 | Other effect |
|---|---|---|---|---|
| DS-20 oracle I6 and H7 | none | none | none | reference now obeys two stated rules |
| AL-27 hidden I6 and H7 cases | none | none | none | two previously untriggered rules harder inside every composed season |
| TS-29 whole-document bools | harder | harder | harder | each wrong document loses its full check |
| JD-7 / AL-6 oracle R1-R3 probes | none | none | none | oracle trajectory meets conduct criteria |
| JD-16 R6/R9 split | none | none | none | online lookup and program network use graded separately |
| AL-2 / Step 11 stdlib and final-message fix | none | none | none | program imports audited; ungraded request removed |
| Step 10 x3 warn kept | none | none | none | x5 reserved for sign-off |

Single-reading tests-only losses, before -> after: L7 32 -> 32, L3 26.75 -> 38, L6 36.75 -> 38 positive points. The same four whole seasons and their separating cases remain. The new single-rule variants `no_reinstate` and `no_apprentice_relief` lose 35 and 20 positive points respectively after the fix, versus zero before.

## P12 r5 QC fix effects (23 Oct 2026)

| Fix | L7 | L3 | L6 | Other effect |
|---|---|---|---|---|
| DS-27 TRUTH.md task facts only | none | none | none | wording only, no graded value moved |
| TS-25 stdlib check moved to `negative_imports_third_party_module` (-1) | none | none | none | positive total 55 to 54; reward 0.5/54 |
| JD-16 R9 replaced by `negative_program_opens_network` (-1) | none | none | none | judge negatives 11 to 10; tests negatives 8 to 10 |
| JD-18 R4 now grades the missing-input error path | none | none | none | oracle names a missing input and exits 1; shipped outputs byte-identical |

## P12 v3 r1 (24 Oct 2026): I3 sentence and S2 clause, not a lever

The forge-day handle reading in the S2 window is a stated rule, not a lever. I3 closing sentence restored and S2 gains "each forge entry's handle resolved on the forge's own day (I3)" so the contract settles it. Measured with `wrong/salvage_day_window.py` (built by `wrong/make_salvage_day_window.py`; the window reads every settled forge's handle on the salvage day): tests-channel local loss 38 of 54 before and after (the seven whole documents and live_window_refusals). Lever losses unchanged before -> after: L7 32 -> 32, L3 38 -> 38, L6 38 -> 38, no_reinstate 35 -> 35, no_apprentice_relief 20 -> 20.

## P12 v3 r2 QC fix effects (24 Oct 2026, board 5f0812e, QC v8 391ff22)

| Fix | L7 | L3 | L6 | Other effect |
|---|---|---|---|---|
| S5 tests/__pycache__ removed (master 13:05) | none | none | none | structure only |
| AL-27 season `quiet_rules` + `quiet_rules_findings_and_funding` (w3) | none | harder | none | not a new lever: grades four stated quiet rules (A2 edges, Q1, V2, STOCK_FLOOR detail order); each single-rule mutant 0 -> 3 lost |
| JD-9 R4 missing-input path -> `program_names_missing_input` (w1) | none | none | none | deterministic contract shape moves to tests; mi_generic / mi_traceback lose 1 |
| JD-18 R4 slot -> `r4_program_code_quality` (w3, conduct) | none | none | none | judge stays 8 criteria +12 / -10 |
| DS-22 TRUTH digests and counts rewritten last | none | none | none | text only |

Tests-channel local loss of P (before P=54 -> after P=58): L7 32 -> 32 (ratio 0.931), L3 38 -> 41 (1.005; the L3 variant also breaks a quiet-rules fixture), L6 38 -> 38 (0.931), no_reinstate 35 -> 35, no_apprentice_relief 20 -> 20, salvage_day_window 38 -> 41, oracle 0 -> 0, a7 38 -> 41 (share 0.704 -> 0.707). No previously failing check passes for any variant. Positive total 58, negatives -10.
