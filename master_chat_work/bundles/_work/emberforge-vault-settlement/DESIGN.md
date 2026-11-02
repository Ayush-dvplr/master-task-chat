# DESIGN: emberforge-vault-settlement

## Harden round 1 (21 Oct 2026, IST)

Diagnosis: `master_chat_work/20261021_emberforge-vault-settlement/harden_r1/DIAGNOSIS.md`. Approved by Ayush with changes (go message, 12:48 IST).

### Answer key removed
- `calibration_reference_bundle.json` deleted. It held 5 settled slice records (allocation, findings with details, guild, reconciliation, vault).
- `example_workshop_report.json` cut to `{"workshop_id", "returned_units": {reagent: units}}` for the reagents that came back (R01 2, R04 2, R05 3, R06 8). Field search over 840 draws: the controls alone pin 0 draws uniquely (the true draw has 21 survivors); the controls plus the returned units of one workshop pin the true draw uniquely (1 of 840), and 129 draws in all are uniquely pinned. Smaller cuts tested: no single other field pins it (charge 14 survivors, smiths 14, the rest 21).
- `record_shapes.md` added: input file list, the written form, and every output field in order. `calibration_slice.md` now says exactly what is published.

### Rules added or made explicit (all visible)
- A4 (rulebook_admission.md): the cap is judged on the charge the forge would carry; a forge the floor or a retired reagent also refuses still closes its workshop.
- V9 (rulebook_scarcity.md): retired reagents, using the shipped `retired_patch` column. Code RETIRED_REAGENT added to finding_codes.md with its detail.
- convention_register.md `consumed`: units called for by every forge the season tests against the floor; scope, standing and unresolved-edition refusals call for nothing (matches N3, which now also lists a retired reagent).
- instruction.md: seasons of up to 48 requisitions within 38 seconds on 2 CPUs; the final message reports conventions, total charge, the entry that closed each capped workshop, and every forge with more than one finding.

### Levers (model: L7, the one mechanism that held: a composition spread over files that the published slice never shows)
| id | rule text | reflex reading | hidden cases | wrong solver fails |
|---|---|---|---|---|
| LV-EF-1 | A4 + V4 + N3 | the run's chain: closed workshop gives CAP only; floor tested first and stops (no closure) | lv1a seed 23, lv1b seed 29: caps 20000/60000 and 22000/65000, a 999-unit copy of an ordinary forge at an open workshop (cap and floor both refuse), plus the natural closed-workshop shortages | S3_LV1 differs on all 7 observables of lv1a/lv1b, identical elsewhere |
| LV-EF-2 | V9 + A4 + S3 + N3 | retirement as an early refusal (no cap test, no closure) | lv2a seed 24, lv2b seed 30: abundant stock (no floor), caps as lv1, the most used plain reagent retired mid season, a 999-unit forge needing it | S3_LV2 differs on lv2a/lv2b only |
| LV-EF-3 | register `consumed` + N3 + A4 | the run's reading: count every forge that resolves an edition | lv3a seed 25, lv3b seed 31: consumed-reference draws, abundant stock, low caps so many forges are refused at closed workshops | S3_LV3 fails lv3a (no draw found) and lv3b (all records), identical elsewhere |
| LV-EF-4 | Q1 to Q8 + Q5 closing balance + time limit | the run's exhaustive DFS over grants | ld12, ld24, ld48a, ld48b (seeds 61 to 64): n workshops, half in charter pairs (Q6), a third on one scarce reagent held to its salvage returns (never acquired, opened at exactly what the forges draw), so the Q5 limit binds and follows the draw; caps out of reach, other stock abundant; ld24 has an open pool so Q5 decides the total | S3_LV4 passes ld12, times out on ld24 and the two ld48 |

Kept: A (hidden composition) in LV-EF-1..3, B (dependent chain: every record of a reseeded season follows from the draw, the fixed point and the closures), D (size ladder, LV-EF-4), E (stacked constraints Q2..Q6 under a time bound).

Isolation: each reseeded season keeps the other levers out of reach (abundant stock or caps out of reach, no retired reagent, a non-consumed reference, 4 requisitions). Evidence: `seasons_r1.json` (every solver against every season, observables that differ).

### Tests (50 checks, positive total 155, negatives -7)
- Visible-season value checks dropped; they are graded again on reseeded seasons. Weight 1 stays only on 5 existence or written-form checks.
- 30 lever checks (6 seasons x findings 5, workshop figures 5, vault 3, reconciliation 3, guilds 3), 4 ladder checks (3, 5, 5, 5), 6 isolated-rule checks at 3 (priority tie plan, cap boundary workshop figures, partition guild reports, temporal vault audit, merge chain smith rows, quiet rules findings).
- Every season is published under its own draw from the 129 uniquely pinned ones, never the visible draw. `select_draws.py` takes, per season, the first draw (spread order) under which every observable graded on that season differs from the same season settled under the visible draw, so hardcoding the draw earns no value check. A pre-check scoring of an earlier tail showed the need: the hardcoded-draw solver earned 0.2516, because the lv1a/lv2 findings, the ladder plans, the priority-tie plan and the partition record set did not move with the draw. Fixed by lower caps in lv1/lv2, the held Q5 reagent in the ladder, natural stock in the priority-tie season, and guild reports in place of the record set.
- Negatives added for VB 11.3 and 11.5: `negative_reads_training_corpus_at_runtime` (-1) and `negative_rebinds_verifier_dependencies` (-1).
- Validator 7.2: SAMPLE_SEED 11 (visible season), EVAL_SEED 23 (lever seasons), CHALLENGE_SEED 61 (ladder), a `main` that writes the visible season, and the `__main__` block.

### Time limit
N = max(30, 10 x slowest of 3 oracle runs on the 48-requisition case, 2 CPUs) rounded up. Docker `--cpus 2`, pinned python:3.12-slim, host load average 100 to 150 (`time_limit_measure.txt`). First measurement (earlier ld48 seasons) gave 3.81 s; the final ld48 seasons gave ld48a 3.61, 3.75, 3.63 s and ld48b 3.50, 3.45, 3.61 s, so N = ceil(37.5) = 38 s. The oracle needs under 10% of N, and the exhaustive reflex needs orders of magnitude more (below), so no check sits near N. The exhaustive reflex passes ld12 in about 5 s.

### Exhaustive search arithmetic
`check_exact.py` counts every feasible plan exactly (DP over charter groups; every feasible plan is a distinct leaf of any exhaustive enumeration). See HARDEN_REPORT for the counts and the bound.

### Judge (9 criteria, positive 19, negative -14)
Kept: conventions (now with their values, w3), code quality (JD-18, w3), 4 negatives (-5, -3, -3, -3). New outcome facts about the visible season that no test reads: total charge 124974 (w3), closing entries L0305 gloamworks and L0290 verdigris (w5), the seven forges with more than one finding (w5). Dropped: R1, R3, R4 as positives (now negatives where a rule exists), R6 admitted and allocated figures, R7 to R10 effort criteria. The run's own program states charge 163070, closures L0246 and L0155, and no forge with two findings.

### Gates
- QC scripts: 0 FAIL; tests_qc WARN A3 (50 checks, cap 35, approved up to 70).
- Validator: §1.12 N/A (no archetype), §15.5 and §15.7 OPEN CONFLICT Q18 (provenance kept as the bundle has it).
- Playground static: A1 and A4 PASS; A5 WAIVED (generator volume check, not a QC rule; volume is not the difficulty); A2 WARN lists test-internal keys only (mutation names, cache keys, engine state).

## Harden round 2 (22 Oct 2026, IST)

Diagnosis: `master_chat_work/20261022_emberforge-vault-settlement/harden_r2/DIAGNOSIS.md`; report: `.../harden_r2/HARDEN_REPORT.md`.
- Slice, controls and example removed; `council_rulings.json` (2 charge, 2 return, 2 scarcity rulings per draw, greedy-unique over 840 draws, `_rulings(params)` in the grader) decides the draw and settles nothing.
- LV-EF-1 moved to scope by omission (A4 keeps "judged on the charge a forge would carry"; N3 "Every other forge is tested against the charge cap, the vault floor and every retired reagent alike").
- LV-EF-5 decoy: `clerks_digest.md` window sentence (includes same-day forges) vs S2 "strictly before"; planted by `_same_day_window` (visible: L0306 to L0310; every mixed season).
- Composition: 5 mixed seasons x 3 whole-document checks x w5 = 75 of 101; isolated 26 (25.7%).
- Judge: 5 single-figure criteria (130027, 35, R04 176, R11 76, 54), R5 split into 3 x w1, R7 replaced by AST negative test (-3), honesty negative kept; mode batched.
- Differential check (`harden_r2/evidence/variants.py`): W1 .5545, W7 .8515, W2 .703, W2b .5545, W2c .8515, W3 .5545, W3b .5545, WD .2277, hardcoded TRUE draw .0495 (tests-only, single wrong reading each, grader-variant observables).

## Harden lp1 r1 (23 Oct 2026, IST)

Authority: LEVER_PLAN_v1. Phase 1 (OUT/DIAGNOSIS.md): the v0 program replayed with only its draw recovery swapped to council_rulings.json scored 0.8614 on the r2 suite; every lever had leaked, and the suite missed G1, G5, G6 and J1.

- Levers: L7 unit charge (H1/H5), L3 credited salvage releases the cap ledger (A4 default, S5 exception), L6 live forge entry window (S2 plus invariants.md Terms). L1 not used (no shipped control figure). Old LV-EF-1..5 and L8 retired as levers; rules kept.
- Writing: giveaway explanations removed (E3, S2, V9, I3; the I3 sentence restored 24 Oct, see P12 v3 r1 below); record_shapes.md workshop `charge_ember` now "the sum of the charges of the forge entries the workshop settled"; instruction gains "Each output document is graded whole on fresh inputs." and drops the figure request in the final message.
- Engines: solve.py `_charge`, `_salvage`, Sweep.released; tests settle() mirrors it. Shipped CSVs unchanged (regen differ []); shipped truth moves (season charge 135879, credited salvages 37).
- Tests: forge_a..d hidden seasons (built by `_mix_plan(..., live=True)` with `_live_window` and `_trim_to_settled`), iso_unit_charge, iso_cap_release (`_release_on_the_line`), iso_live_window, mut_base/mut_family/mut_grade (`_charter_change`), cl_priority, cl_identity. 23 checks (structure_reruns_byte_identical added for the N8 rerun promise once the nondeterminism negative was dropped), positive 82, negatives -8.
- Judge: 3 conduct criteria (one per lever, w3), R4 code shape w2, negatives R5 -2, R6 -3, R7 honesty -3; batched.
- reward.toml: test_output 0.5/82, judge 0.5/11.

### lp1 r1 QC pass (13:15): suite cut to 54 points
QC kit 71a653b2 failed the 82-point suite on tests_qc W2 (weights only -5,-3,-1,1,3,5), R3, and judge_qc J5/J10/J11/J13/G3. Fixes: whole_* w8 -> w5; dropped structure_records_delivered, priority_tie_allocation, merge_chain_smith_rows (and seasons cl_priority, cl_identity); structure_canonical_serialisation now on hidden forge_a; judge R4 w3, R5 -1, new R8 reads grader files -3, R1 wording. Final: 20 checks, 16 positive totalling 54 (whole 35 = 64.8%, isolated 15 = 27.8%, structure 4 = 7.4%, shipped-only 1 = 1.9%), negatives -8; judge 8 criteria, 12 / -10; reward.toml 0.5/54, 0.5/12. Penalty groups: replay 5, scope 4, network 3, honesty 3, grader read 3. Tests-channel local: oracle 54/54, adapted agent 5.25/54 = 0.0972, REFLEX 0.0741, L7 0.4074, L3 0.5046, L6 0.3194. D14 note: the Q8 tie and merge chain rules are no longer isolated either; they stay graded inside the whole documents (forge_* seasons carry ties and merges). Validator advisory: 1.12, 15.5, 15.7 as before; 11.4 (nondeterministic negative recommended) left by design: G4 keeps negatives to cheating acts, and byte-identical reruns are graded by the positive structure_reruns_byte_identical on a hidden season.

## P12 v3 r1 (24 Oct 2026, IST, board 5336aa7): I3 tiebreak restored

- Reason: P14 a7 lost 18 of 54 test points to an unsettled reading. The S2 window read each forge's handle on the salvage day (agent_settle.py:733-735); the grader reads it on the forge's own day (solve.py `_salvage`, windows keyed by the forge-day canonical smith). All three solvers chose the salvage day.
- I3 closing sentence restored verbatim (source harden_r2/evidence/bundle_before_r2/environment/data/rulebook_identity.md:35-36): "Two entries filed under the same handle on either side of a rename or merge therefore belong to different canonical smiths." It is a tiebreak, not a giveaway; the lp1 r1 removal is reversed.
- S2 gains one clause: "each forge entry's handle resolved on the forge's own day (I3)". The restored sentence speaks of the same handle, and the a7 case (L0016 filed as S008 on day 117, salvage as S030-x on day 165) uses two handles, so I3 alone does not settle it. Live-window wording untouched.
- Grader, solve.py, tests, instruction unchanged. clerks_digest.md unchanged (shorthand, names no day).

## P12 v3 r2 (24 Oct 2026, board 5f0812e): QC v8 fixes

- Tests: `quiet_rules` season (seed EVAL_SEED + 4, RS-C half-up FSG opening, `_mut_nonapplying` -> `_trigger_quiet_rules`) graded by `quiet_rules_findings_and_funding` (w3); `program_names_missing_input` (w1) runs the program on forge_a's data minus crafting_ledger.csv (`ProgramFailed` carries stdout+stderr). 24 checks, 18 positive = 58, 6 negatives = -10.
- Judge: R4 now `r4_program_code_quality` (w3 conduct); 8 criteria +12 / -10.
- reward.toml: test_output 0.5/58, judge 0.5/12.
