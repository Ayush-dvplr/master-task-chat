# RECHECK_FIX metered-usage-rating-pipeline (P12 fix v2, board f65cab8)

- Report: `/Users/mac/Desktop/Terminal Bench/QC/reports/metered-usage-rating-pipeline/v2.md` (FAIL: 1 fail, 0 minor, 0 warn; result_cc541be.json)
- Live kit: `Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`, harness HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271; fingerprints qc.json and pl_generator.json 0 mismatches (no UPSTREAM CHANGED).
- Session rename: name_session.py f65cab8 -> `codex: no match`, `opencode: ['ses_e7a40930dffeVHfBPWF1zmQiOm']` (renamed in opencode).
- Noise check: BUNDLE before edits == PREV_QC_COPY cc541be (`diff -rq` empty, tree 577aba4a07ea). The cited lines are byte-identical, but cc541be is the copy that FAILED on them, so this is not variance: no NOISE row.
- Levers: no lever touched; the refusal path is not a lever. Every LV-MU lever keeps 100% of its before-loss (see Trap survival).

## Phase 1 table

| ID | label | rule quote (live kit) | evidence quote (bundle) | decision | playbook row | effect per lever | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| G05-1 | REAL | 05_Alignment_Integrity_QC.md:38 AL-27 "a rule only counts as graded when the test's input actually constructs the situation where the rule matters ... unless some graded input carries BOTH faults at once, the order never matters and a solver checking things backwards still scores full reward"; :126 untriggered rules = fail | rating_contract.md:51-53 lists 11 inputs; :55-57 "naming the first missing file in the order of the list above". Old tests/test_output.py:1408-1432: `_check_missing_collector` removes collector_north.jsonl only, `_check_missing_reference` removes rate_card.json only, `_check_missing_first_named` removes one pair (collector_central.csv + accounts.csv); asserts use `in` on stderr (:1414, :1423, :1432). Measured after the fix: a program that prints a `missing input:` line for every missing file earns all 413 pre-existing points and loses only the two new checks; those old checks are unchanged | FIX: two new seeded checks (G2, never folded into an existing one). `missing_references_first_in_list` (w3, HIDDEN_SEED+7) removes plan_changes.log, products.ini, collector_controls.json at once (earliest in list is not the first by name). `missing_collectors_first_in_list` (w3, HIDDEN_SEED+8) removes collector_north.jsonl and collector_west.log. Each asserts non-zero exit, the earliest file named, and no `missing input:` line for any later removed file (tests/test_output.py:1435-1466). reward.toml test_output 0.5/413 -> 0.5/419 | AL-27 DO: hidden rows carrying both faults at once, assert the earlier one wins; NEW-CHECK row hygiene | all LV-MU: none (losses identical) | none needed | WORK/tests_template.py, WORK/assemble_tests.py -> tests/test_output.py; tests/reward.toml; solution/TRUTH.md (write_truth.py last); WORK RULE_COVERAGE.md, LEVERS.md, QC_DEFENCE.md, truth_template.md, TODO.md, LOG.md |

## Deviations from master directions

- Reference trio is plan_changes.log, products.ini, collector_controls.json, not the master example plan_changes.log, commitments.xml, collector_controls.json. Same idea (three positions, different list ranks); the seeded draw is constrained so the earliest file is not the alphabetically first, which also fails a checker that walks files in sorted order. Not a difficulty change.
- The five collectors are listed alphabetically in rating_contract.md:51-53, so no collector pair can separate list order from sorted order. The collector check still fails a reversed checker and a print-every-missing checker (measured). Inherent to the contract, not changed.

## Touched rules

| id | touched how | rules re-checked | verdict with file:line |
|---|---|---|---|
| missing_references_first_in_list (new, w3) | new positive check | TS-13 one property (multi-missing refusal: exit, earliest named, no later named); TS-14 name and description state the property; TS-20 w3 key edge case, not core; TS-25 decisive assert is the earliest name, nop 0/419; TS-26 separate run and scenario from missing_reference_file (rate_card.json alone) and missing_input_first_named (collector + accounts); separated by mutants: sorted order fails it and first_named, print-every-missing fails only the two new checks; CL-2 constant docs program fails it; CL-4 points share 3/419 | PASS, tests/test_output.py:1444-1462, :1832-1835, :2143 |
| missing_collectors_first_in_list (new, w3) | new positive check | TS-13, TS-14, TS-20 w3, TS-25 nop 0/419, TS-26 separate from missing_collector (collector_north alone): reversed and print-every-missing fail it, missing_collector still passes for them; CL-2 constant fails; CL-4 3/419 | PASS, tests/test_output.py:1444-1457, :1465-1466, :1836-1838, :2144 |
| tests/reward.toml weights | test_output 0.0012106537530266344 -> 0.0011933174224343676 (0.5/419); judge 0.01 unchanged | TS-S10 / tests_qc R3 (test channel = judge channel = 0.5) | PASS, tests/reward.toml:4; tests_qc 36 pass, 1 WARN A3 |
| solution/TRUTH.md | regenerated last by WORK/write_truth.py (G6) | DS-22 sha lines; counts 111 pos 419, 1 neg -5, judge 23 / 50 | PASS, TRUTH.md:113, :143-146, :190, :192, :292 |
| judge | untouched | JD rules n/a | judge.toml byte-identical; judge_qc 19 pass |

## Vacuity probe

Script WORK/f65c/f65c_runner.py in `docker run --rm --memory 4g --cpus 2 python:3.12-slim` (log /tmp/opencode-logs/f65c-20261029T091658-9c02/trap.log, json WORK/f65c/trap_f65c.json, END rc=0, ALL_DONE):
- unedited shipped environment and data, no transform program: 0/419 positive points, 0 checks pass.
- empty program: 0/419.
- oracle: 419/419.
- the two new checks are 0 for both, so neither is vacuous.
- Manual review of every positive judge criterion (18 criteria, 50 points): an unedited/no-action agent earns none. R1-R5, R7-R9 and R16-R22 require actual runs, comparisons or command output; R6 explicitly requires the agent to leave transform.py, so absent code cannot satisfy its handler clause; R10 requires a response listing the program and written files; R23 requires a check actually run on the last program. Evidence: judge.toml:14-131, :209-300 and no transform.py in the shipped environment. This is a manual vacuity review, not a scored judge-service run; judge.toml is unchanged.
Verdict: PASS.

## Side effects

| FIX id | ids re-checked | result |
|---|---|---|
| G05-1 (AL-27) | TS-13 (FIX_SIDE_EFFECTS: schema v4 minor), TS-14, TS-16 n/a, TS-20, TS-25, TS-26, TS-23 | none new; TS-23 WARN kept with count 112 (was 110), playbook TS-23 KEEP |
| G05-1 (AL-2) | TS-25 (emberforge v7) | PASS, nop 0/419, decisive assert earned |
| G05-1 (CL-2) | TS-26 (sentinel v2); share re-derived | the QC fake (list-order checker + 13 constant files) measured 34/413 = 8.2% test channel, 4.1% combined reward contribution (v2.md:257). With old checks unchanged and the two new w3 refusal checks, its share is (34+6)/419 = 9.5%, 4.8% combined contribution; this is a re-derived share, not a new run of that exact QC fake. Refusal path only, no content; the separately run constant-docs program earns 22/419 = 5.25% tests-only |
| G05-1 (CL-4) | points share | 15/419 = 3.6%, unchanged in kind |
| G05-1 (AL-27 RULE_COVERAGE) | G11 | WORK/RULE_COVERAGE.md 70 rows, `Rules uncovered: 0 of 70.`, no 0 row; new rows reversed(REQUIRED) 3 (9 pts) and every-missing-printed 2 (6 pts) |

## Noise keeps

None. The only finding is REAL.

## Trap survival

Single wrong-reading variant per lever, current tests (413 before, 419 after), same runner in Docker.

| lever | variant | lost before | lost after | ratio (raw points) | separating cases kept | verdict |
|---|---|---|---|---|---|---|
| LV-MU-6 | alone | 204 | 204 | 100% | y, all 50 previously failing checks retained | PASS |
| LV-MU-5 | alone | 335 | 335 | 100% | y, all 85 previously failing checks retained | PASS |
| LV-MU-7 | alone | 204 | 204 | 100% | y, all 50 previously failing checks retained | PASS |
| LV-MU-8 | alone | 160 | 160 | 100% | y, all 44 previously failing checks retained | PASS |
| LV-MU-9 | alone | 112 | 112 | 100% | y, all 32 previously failing checks retained | PASS |
| LV-MU-1 (noise) | alone | 351 | 351 | 100% | y, all 89 previously failing checks retained | PASS |
| LV-MU-3 (noise) | alone | 257 | 257 | 100% | y, all 61 previously failing checks retained | PASS |

Positive-total-normalized retention also clears the 90% floor for every lever: (loss/419)/(loss/413) = 413/419 = 98.57%. Failure-name sets were compared directly between WORK/a395/trap_after.json and WORK/f65c/trap_f65c.json; no previous separator or graded input was removed.

QC variant A 164/413 -> 170/419 (lost 249 -> 249). Mutants on the list-order rule (after): reversed order 410/419; every missing file printed 413/419 (all old checks pass; only the two new checks fail); sorted order 413/419; reference files first 416/419; only collectors checked 413/419. Verdict: PASS.

## QC_RULINGS rows

- IN-15 | instruction wording | not raised in v2 | n/a | no instruction change
- IN-16 | instruction hints | not raised in v2 | n/a | no instruction change
- TS-13 | one property per check | new checks re-checked | PASS | none
- TS-19 | hidden data | new checks use hidden seeded runs (HIDDEN_SEED+7, +8) | PASS | none
- TS-20 | weights | new checks w3, core weights unchanged | PASS | none
- TS-26 | double pay | new checks separated by measured mutants | PASS | none
- AL-28 | stacking | stacking_check tool hint unchanged, QC v2.md:275 hand PASS | PASS | none
- JD-7 | judge | judge untouched | n/a | none
- JD-15 | judge | judge untouched | n/a | none

## Gate results

- Harbor step 10, tests-only (live kit exe_copy.py plain and --owner-only copies, TS 20261029T093204-6618): oracle [1.000, 1.000, 1.000], owner-only 1.000, nop 0.000. Warm build rc=0; every run END rc=0; runs.log ends ALL_DONE at 11:44:22 IST. No completed Docker block rerun.
- Evidence: /tmp/opencode-logs/f65c-step10-20261029T093204-6618/runs.log and /tmp/harbor-jobs-qc/metered-f65c-20261029T093204-6618/{oracle-1/plain__EAWB8V9,oracle-2/plain__XLk6uLR,oracle-3/plain__2GWhRki,owner-1/owner__vNpoN4s,nop-1/plain__wEdWMQE}/result.json. All five files independently parsed at resume: expected reward and null exception_info in each. oracle-3 crossed a host sleep (~10:28-10:53, pmset evidence), then completed with reward 1.000 and no exception. The chain released its bundle lock; docker ps was empty at 12:45.
- precheck.sh BUNDLE: last line `PRECHECK CLEAN` (WARN X1 binary skip, A3 112 checks).
- kit scripts: judge_qc 19 pass PASS; tests_qc 36 pass 1 WARN A3; instruction_qc 5 pass PASS; structure_qc 17 pass WARN X1.
- xref_check: 24 entries, 0 findings (before and after). stacking_check: OUT/STACKING_CHECK.md `STACKING PASS`.
- In-container scoring: oracle 419/419, no program 0, empty program 0.
- Final main-chat verification: fingerprints unchanged (12 QC and 160 generator files); AST parses 112 checks / positive 419 / negative -5. BUNDLE tests/test_output.py is byte-identical to both executed copies; diff -rq against cc541be lists only the three permitted bundle files. basedpyright LSP is not installed and its installation was previously declined; no LSP-clean claim is made. Syntax checks, live kit scripts and real Docker results are the verification evidence.
- tree_sha (sha256 over byte-sorted './' paths each followed by its bytes, first 12): before 577aba4a07ea, BUNDLE after 396efb9b4952, Tasks_INPUT after 396efb9b4952 (23 files each). Authorized rsync -a --delete targeted only Tasks_INPUT/metered-usage-rating-pipeline/; final diff -rq was empty, exit 0 at 12:45 IST. No bundle edit after the tested bytes or sync.
- P12 result: 1 REAL fixed, 0 FALSE_POSITIVE, 0 UNSURE, no paused IDs or new side-effect finding. One carried count warning kept; X1 remains a carried encoding rebuttal. This is the local fix/recheck, not a fresh P11 QC verdict and not a paid model run. Next: master issues P11 v3 in MODE recheck with v2.md, this KEPT.md and previous QC copy cc541be. The paid run remains after a PASS recheck.

## Lessons for the master

- A precedence rule over a list needs a multi-fault input per adjacent pair plus a "no later name" assert; `in` on stderr lets print-all programs pass | template_change: master_chat_tasks/knowledge/QC_FIX_PLAYBOOK_v3.md:36 AL-27 DO column, add "and assert no output line names a later item"
- An alphabetical list cannot separate list order from sorted order; pick at least one group that is not alphabetical when the contract is written | no change: design choice of the generator, noted for authors
