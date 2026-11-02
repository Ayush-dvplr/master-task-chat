# RECHECK_FIX b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042 (P12 fix v3, board 2990713)

Replayed saved-agent prediction stays below 35 (before 18.56, after 17.78).

- Kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271 (same as the last two rounds). QC report v3.md (FAIL 7 / 3 minor / 2 warn, 5 acknowledged).
- BUNDLE tree before c2c53493843d = QC copy 0d957b9 (`diff -rq` empty); backup WORK/qc3_c2c53493843d.
- Session rename: `name_session.py 2990713` listed opencode `ses_e6f92f7afffe1OoKJST16tHr5r`.
- Levers (LEVERS.md): L1 column-4 paid, L2 clash cover, L3 admission bar, L4 precedence flip at cutover, L5 reinsurer epoch split, L6 factor clip; L7 remainder tie-break is not a lever (0 loss).
- Noise check (Always 13) against the v2 copy db42563: every cited line is either new in 72ebb9d or now sits in a newly graded context (summary_values digest grades `total_ibnr`; the booked-layer later-line rule is new; R25 and the stdlib check were reworked in 72ebb9d). So no finding is NOISE.

## Recheck table

| ID | label | rule quote (kit file:line) | evidence (bundle file:line) | decision | playbook row | effect L1..L6 | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| G02-1 DS-20 | REAL | 02_Data_Solution_QC.md:68 "The oracle obeys the contract, independently of the tests. ... Walk the oracle's logic against every rule the contract states" | attachment_rules.md:7 "The `layer` on a ledger row is the booked layer" vs solve.py:887 and :907, where retracted and excluded rows emit `retention` | fix: appended to attachment_rules.md:7 "A retracted or excluded row books `retention` whatever its log line says." (QC sentence) | AL-1 (4b determinate fact) | none x6 | - | environment/data/attachment_rules.md |
| G02-2 DS-20 / IN-16 | REAL | 01_Instruction_QC.md:46 "No significant ambiguity in anything that is graded. ... reachable in exactly one way" | attachment_rules.md:19 did not say which rows compete; solve.py:915-926 lets only live rows booked `retention` compete | fix: inserted at :19 "Only rows that are neither retracted nor excluded and whose booked layer is `retention` take part; the first of them consumes the retention." | IN-16 / AL-1 | L2 none (the clash-cover trap is ignoring the cover, variants.py L2 `if False:`; loss 21 -> 21) | - | attachment_rules.md |
| G03-1 TS-25 / TS-27 / TS-26 / CL-2 | REAL | 03_Tests_QC.md:52 "Positive tests grade earned work, never an absence. ... a banned import that is absent ... Absence belongs on the negativ[e side]" | old test_output.py:757-773 module_imports_only_standard_library w1 (stub earned it) | fix: deleted the check; negative_module_opens_network_or_shells_out (test_output.py:974-1020) now fires on any import outside `sys.stdlib_module_names`, any relative import, or a banned module | TS-25 (move to negative), TS-26 | none x6 | - | tests/test_output.py |
| G03-2 TS-19 / IN-16 | REAL | 03_Tests_QC.md:50 "Every graded behaviour must be learnable by the agent" | output_contract.md:11 left `total_ibnr` undefined; discounting_rules.md:7 "when discounting the IBNR carryforward"; solve.py:1272 is undiscounted | fix: appended to output_contract.md:11 "`total_ibnr` is the undiscounted sum of `ultimate` minus `paid_to_date` over every ledger row; discounting reaches only the counterfactual present value." | TS-19 / AL-1 | none x6 | - | environment/data/output_contract.md |
| G05-1 AL-2 / CL-1 | REAL | 05_Alignment_Integrity_QC.md:33 "Everything promised is graded." | instruction.md:9 "name the observation log that settled each methodology reading"; R25 judge.toml:326 graded only the strings | fix: appended to R25 "and the recap names `claim_adjustment_log.log` and `treasury_curve_observations.log` as the logs that settled them" (master: keep the instruction clause) | AL-2 (grade it) | none x6 | - | tests/judge.toml |
| G05-2 AL-2 / CL-1 | REAL | 05_Alignment_Integrity_QC.md:33; Final_checklist.md:488 "Every action the instruction demands is checked by something" | instruction.md:7 "add nothing to the output directory beyond the nine documents and the program"; no checker after 72ebb9d | fix: new negative_output_directory_holds_extra_files w-1 (test_output.py:1023-1036, :1073); negatives 23 -> 24 | AL-2, NEW-CHECK | none x6 | - | tests/test_output.py |
| G05-3 AL-27 | REAL | 05_Alignment_Integrity_QC.md:38 "a rule only counts as graded when the test's input actually constructs the situation where the rule matters" | reason_codes.json outcome_precedence "RETRACTED, EXCLUDED, ZERO, ..."; extract A layer_capacity_declarations.csv:64 was `gl,H11,1712015` | fix: gen_extracts.py zero cells A = (cal,H05),(gl,H11); re-sealed (runs/seal_v3). CLM-00014 stays EXCLUDED/UNRESOLVABLE_CHAIN; CLM-00128/00112/00159 FULL -> ZERO. New mutant R_zero_over_excluded loses 6 (hidden_extract_outcomes_exact, outcome_and_reason_vocabulary_exact); RULE_COVERAGE row added | AL-27 (hidden triggering row + mutant) | harder (adds a trigger); L1-L6 losses unchanged | - | generated tests/test_output.py fixtures (G7 diff WORK/G7_v3_tests_diff.txt) |
| G02-3 DS-6 (minor) | REAL | 02_Data_Solution_QC.md:22 "Data files must make sense for the task story" | attachment_rules.md:11 described the factors as load-bearing; solve.py:1182-1184 loads them and never multiplies | fix: appended to :11 "The governing run multiplies no ledger figure by these factors." | AL-1 | L6 none (L6 is the development-factor clip `f = max(1.0, min(2.5, inc / p))`, separate from attachment factors; loss 22 -> 22). R32 negative still punishes a typed 0.75/0.50 | - | attachment_rules.md |
| G02-3b DS-22 (minor) | REAL | 02_Data_Solution_QC.md:76 "eight sections (Defect, Load-bearing work, Verification, Root cause, Solution shape, Ordered plan, Pitfalls, Provenance)" | old TRUTH.md had seven headings | fix: write_truth.py emits `## Ordered plan` (TRUTH.md:56) after Solution shape, 8 stages in instruction.md:7 order; regenerated by script last | DS-22 | none x6 | - | solution/TRUTH.md (by script) |
| G03-3 TS-13 (minor) | REAL | 03_Tests_QC.md:44 "One property per test." | old test_output.py:156 put `attachment_authority` and run fields in _summary_values with dollar values | fix: `_summary_run` (lobs, cycles_total, admission_instant; attachment_authority dropped) and `_summary_values` (dollar totals, per-LOB, treaty splits); new summary_run_fields_exact w1 (:749) and narrowed summary_and_treaty_values_exact w1 (:768) | TS-13 split | none x6 | - | tests/test_output.py |
| G02-4 DS-6 (warn) | REAL | 02_Data_Solution_QC.md:22 | counterfactual_parameters.md:23 "first line" vs attachment_rules.md:7 "the later line in file order wins" (CLM-00157) | fix: counterfactual_parameters.md:23 now "... records `layer=cat_excess` (the first line, even where the booked layer differs): ..." | AL-1 | none x6 (R8 = 7 unchanged; matches solve.py:1018-1032) | - | environment/data/counterfactual_parameters.md |
| G04-1 JD-16 (warn) | REAL (warn) | 04_Judge_QC.md:97 item 4 "It is graded once, and by the layer that should own it." | judge.toml:417 R32 w-3: literal 0.75/0.50 multiply; rule stated at attachment_rules.md:11 "The authority is that file alone, not any value typed into the delivered module." No test grades it, so it is paid once | KEEP (master direction; QC Fix line offers "or leave it") | SUGGEST / JD-16 | none | - | none |

Acknowledged carry-overs KEPT-1 to KEPT-5 stay as they are (OUT/KEPT.md rows 1-5; row 5 count updated to 32 checks).

## Gate results

| gate | result |
|---|---|
| xref_check | before: "xref_check: 40 entries, 0 findings"; after: "xref_check: 44 entries, 0 findings" |
| Harness oracle (seal_v3, trap_v3_after, cov_v3) | 64/64, no negative fired |
| Docker block | exe_copy plain and --owner-only copies, warm build first (warm-b7c-v4, WARM_EXIT=0); jobs b7c6r2-* under _runs/20261031/b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042/fixgate-20261031T111243-e410/jobs: oracle 1.0 / 1.0 / 1.0, owner-only 1.0, nop 0.0, saved-agent replay 0.1094 (7/64); 0 errors |
| precheck | last line `PRECHECK CLEAN` (tests 32, judge criteria 33; JD-5 warns only, NOTE SELF_CHECKS.md missing) |
| stacking_check | tests 32 checks P 64 neg -24, judge 33 criteria pos 65 neg -24; same tool artefacts as 72ebb9d (OUT/STACKING_CHECK.md) |

## Deviations from master directions

- G03-1 "P 64 -> 63 (reward.toml to match)": P stays 64 because G03-3 (also a master direction) splits one w1 check into two w1 checks (summary_run_fields_exact + summary_and_treaty_values_exact). Kit weights are 1/3/5 only, so the split cannot be 0.5 + 0.5. Net is 64 - 1 + 1 = 64, and reward.toml stays `test_output = 0.0078125` (0.5/64), `judge = 0.007692307692307693` (0.5/65). TS-S10 holds.
- R1-R14 were not regenerated: seal_v3 shows the shipped output byte-identical to seal_v2 (only the new digest keys differ), so no input R1-R14 read changed; cf_v2.json integers stand.

## Touched rules

| id | touched how | rules re-checked | verdict with file:line |
|---|---|---|---|
| module_imports_only_standard_library | deleted (w1 -> -) | TS-25, TS-26, CL-2 | PASS: no positive pays for an absence; stub loses 1 (test_output.py:1039-1063 has no stdlib positive) |
| negative_module_opens_network_or_shells_out | widened (w -1 kept) | TS-13, TS-14, TS-15, TS-16, TS-20, TS-26, CL-2, CL-4, AL-28 | PASS: name and description match the body (:977-1004); returns True on the cheat; fires on numpy, `from pandas import`, relative import, socket; silent on json and os.path; oracle does not trip it (runs/hyg_v3); one act, -1, no judge negative grades imports |
| negative_output_directory_holds_extra_files | added (- -> -1) | TS-13, TS-14, TS-15, TS-16, TS-20, TS-25, TS-26, CL-2, CL-4, AL-28 | PASS: one property (:1026-1032); quotes instruction.md:7; fires on an extra notes file and on `__pycache__`; oracle out holds exactly the 10 entries; no positive checks absence of extras (artifacts_present_and_parse checks only the nine are present) |
| summary_run_fields_exact | added by split (- -> 1) | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4 | PASS: one property (summary.json run lobs, cycles_total, admission_instant, :749-765); stub and empty out earn 0; keys disjoint from summary_values (:145 vs :157); attachment_authority graded only by methodology_audit_attachment_exact |
| summary_and_treaty_values_exact | narrowed (1 -> 1) | TS-13, TS-14, TS-20, TS-26, CL-4 | PASS: dollar totals, per-LOB and treaty splits only (:768-785); description matches body |
| judge R25 | re-worded (1 -> 1) | JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, AL-28 | PASS: one stated promise (instruction.md:9) about the methodology recap; oracle-side reference: alae_rules.md:3 and discounting_rules.md:3 name these logs; saved agent's closing message names both, so JD-7 holds; no other criterion pays for log names |

## Vacuity probe

Environment ships no tool (environment/ = Dockerfile + data/ only). Empty /app/out graded on the AFTER tests (runs/vacuity_v3/grade.json): 0/64 positive, no negative fired: PASS. Judge positives: every positive criterion reads a delivered artifact or the agent's recap, so an agent that changed nothing earns 0 (R25 needs both settlement strings in methodology_audit.json and the log names): PASS.

## Side effects

| FIX id | ids re-checked (FIX_SIDE_EFFECTS.md) | result |
|---|---|---|
| G03-2 TS-19 | TS-23, TS-26 | TS-23: 32 checks, warn kept (KEPT-5); TS-26: no pairing pays twice (STACKING_CHECK.md) |
| G03-3 TS-13 | TS-25, TS-15 | TS-25: both split checks grade value matches; TS-15: both negatives return True on the cheat with an inline comment (:974-976, :1023-1024) |
| G05-1 / G05-2 AL-2 | TS-25 | new negative is on the negative side; no positive grades an absence |
| G05-3 AL-27 | TS-13 | no check changed property; hidden_extract_outcomes_exact still one property |
| G02-2 IN-16 | AL-27 | the new clash-cover sentence has triggering rows (QC lists CLM-00035, 00118, 00065, 00058, 00028, 00034, 00127), graded by the ledger digests; the new retracted/excluded sentence is triggered by CLM-00074 and CLM-00077 |
| G03-1 CL-2 | TS-26 | stdlib positive gone; the widened negative is the only grader of imports |
| G03-1 TS-26 | TS-14 | names and descriptions match the bodies |

Side-effect findings: 0.

## Noise keeps

None. Every v3 cited line changed in 72ebb9d or now sits in newly graded context (see header).

## Trap survival

| lever | before loss | after loss | ratio | separating cases kept | verdict |
|---|---|---|---|---|---|
| L1 column-4 paid | 39 | 39 | 1.00 | all | PASS |
| L2 clash cover | 21 | 21 | 1.00 | all | PASS |
| L3 admission bar | 41 | 41 | 1.00 | all | PASS |
| L4 precedence flip | 45 | 45 | 1.00 | all | PASS |
| L5 epoch split | 19 | 19 | 1.00 | all | PASS |
| L6 factor clip | 22 | 22 | 1.00 | all | PASS |
| L7 (not a lever) | 0 | 0 | - | - | - |

Before: runs/trap_v3_before (BUNDLE before edits, P 64); after: runs/trap_v3_after (P 64). No hidden case or input that lost points was removed; extract A gained a trigger. Coverage mutants (runs/cov_v3): R_block_unit 63, R_cycle_gap 44, R_identical_duplicate 63, R_no_qualified_layer 61, R_paren_negative 63, R_retract_over_excluded 55, R_zero_capacity 61, R_zero_over_excluded 58 (new).

## Score band

| bundle | tests | judge (reading) | predicted final |
|---|---|---|---|
| BEFORE (c2c53493843d) | 8/64 = 12.50% (grade.py replay; equals the 72ebb9d Harbor replay 0.125) | 16/65 = 24.62% | 18.56 |
| AFTER | 7/64 = 10.94% | 16/65 = 24.62% | 17.78 |

Moved -0.78. Only G03-1 moved it: the saved agent earned the deleted module_imports_only_standard_library (w1). The R25 clause still pays (the saved closing message names `claim_adjustment_log.log` for pro_rata and `treasury_curve_observations.log` for duration_matched). No negative fires on the saved output (10 entries, stdlib imports only). Gate v3.7 (tests < 85, rubric < 85, final < 40) holds on the replay. Harbor replay of the saved output on the AFTER copy: 0.1094 (= 7/64), matching grade.py.

## Fix receipt

(a) tree before c2c53493843d (QC copy 0d957b9), after b5dd7c985e44 (BUNDLE = Tasks_INPUT after `rsync -a --delete`, `diff -rq` empty) (same command).
(b) Tests: module_imports_only_standard_library 1 -> -; summary_run_fields_exact - -> 1; summary_and_treaty_values_exact 1 -> 1 (narrowed); negative_module_opens_network_or_shells_out -1 -> -1 (widened); negative_output_directory_holds_extra_files - -> -1. Positive total 64 -> 64; negatives 23 -> 24. Judge: R25 1 -> 1 (re-worded); positive 65 -> 65, negatives -24 -> -24; 33 criteria.
(c) oracle before 1/1/1 (QC v3) -> after 1.0 / 1.0 / 1.0; owner 1.0 -> 1.0; nop 0 -> 0.0.
(d) Saved agent (original_backup run_1 output, 10 files): tests 8/64 -> 7/64; lost module_imports_only_standard_library (deleted); no lever check moved (all levers kept their losses).
(e) Rescan after the last edit:
- AL-18 / DS-22 / DS-27: PASS: TRUTH.md regenerated by write_truth.py after the last edit (byte-identical to the 11:11 write, 94 lines, 8 sections incl `## Ordered plan` :56); precheck DS-22 sha256 lines match; data docs and TRUTH describe the same booked-layer, clash-cover and total_ibnr rules as solve.py.
- JD-14 / AL-28: PASS: no criterion pays twice for one claim; R25 log names graded only by R25; imports graded only by the widened negative; extras only by the new negative.
- AL-1 / AL-2: PASS: the extra-files promise (instruction.md:7) graded by the new negative; log-name promise (instruction.md:9) by R25; standard-library promise (instruction.md:3) by the widened negative; nothing graded that is not promised (attachment_authority no longer in the summary digest).
- AL-27: PASS: RULE_COVERAGE.md has no 0 row; EXCLUDED over ZERO now triggered (R_zero_over_excluded loses 6).

## QC_RULINGS rows

- TS-26 | a w1 positive paid for an absent non-stdlib import while a -1 negative charged its presence | QC v3 fail | REAL | deleted the positive, widened the negative to any non-stdlib import.
- IN-16 | clash cover participants (live rows booked retention) left implicit | QC v3 fail | REAL | stated once in attachment_rules.md:19 with QC's sentence.

## Lessons for the master

- A Fix line that deletes a check and another that splits one can cancel on P; read them together before writing "P 64 -> 63" | no change: one-off direction conflict, recorded as a deviation.
- A shell `nohup ... &` inside a tool call can die when the call ends; Popen with start_new_session=True survived | template_change: _COMMON_RULES_v5.md Always 3 (launch detached with setsid or start_new_session).
