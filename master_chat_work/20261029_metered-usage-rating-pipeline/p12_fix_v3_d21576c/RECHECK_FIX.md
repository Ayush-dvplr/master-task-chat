# RECHECK_FIX metered-usage-rating-pipeline (P12 fix v3, board d21576c)

- Report: `/Users/mac/Desktop/Terminal Bench/QC/reports/metered-usage-rating-pipeline/v3.md` (FAIL: 1 fail, 0 minor, 0 warn; result_92ee28b.json)
- Live kit: `Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`, harness HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271.
- Session rename: name_session.py d21576c -> `codex: no match`, `opencode: ['ses_e785668b1ffelzdTOy6v0uNO1Q']` (renamed in opencode).
- Noise check: BUNDLE before edits == PREV_QC_COPY 92ee28b == Tasks_INPUT (`diff -rq` empty; tree e118610c514f per the prompt's method, 396efb9b4952 by the method in Gate results). 92ee28b is the copy that FAILED on these lines, so this is not variance: no NOISE row.
- Levers: no lever touched; the refusal path is not a lever. Every LV-MU lever keeps 100% of its before-loss (see Trap survival).

## Phase 1 table

| ID | label | rule quote (live kit) | evidence quote (bundle) | decision | playbook row | effect per lever | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| G05-1 | REAL | 05_Alignment_Integrity_QC.md:38 AL-27 "for each adjacent pair in the chain, find the graded input with both conditions present and the assertion that the earlier one wins ... Fail; name the rule and the missing fixture" | rating_contract.md:51-53 lists 11 inputs; :55-57 "naming the first missing file in the order of the list above" (10 adjacent pairs). Before the fix the graded multi-missing sets were central+accounts, plan_changes+products+controls, north+west (old tests/test_output.py:1417-1423, :1460-1466); none is an adjacent pair. QC v3.md:301 mutant (REQUIRED order central, south, east, north, west, accounts, rate_card, commitments, plan_changes, products, controls) scored full; re-measured here: 419/419 on the old tests | FIX as directed: one new check `missing_adjacent_pairs_in_list_order` (w3, tests/test_output.py:1469-1477). For i = 0..9 it takes (REF_INPUTS[i], REF_INPUTS[i+1]) from the contract-ordered list (tests/test_output.py:59-64 == rating_contract.md:51-53), removes both from a fresh hidden month, and asserts exit not 0 and that the set of `missing input:` names on stderr is exactly {REF_INPUTS[i]}. The three existing multi-missing checks are unchanged. reward.toml test_output 0.5/419 -> 0.5/422 | AL-27 DO (QC_FIX_PLAYBOOK_v3.md:36): hidden input carrying both faults at once, assert the earlier one wins; NEW-CHECK hygiene | all LV-MU: none (losses identical) | none needed | WORK/tests_template.py, WORK/assemble_tests.py -> tests/test_output.py; tests/reward.toml; solution/TRUTH.md (write_truth.py last); WORK RULE_COVERAGE.md, LEVERS.md, truth_template.md, TODO.md, LOG.md |

Mutant gate (WORK/d215/trap_d215.json, Docker python:3.12-slim, log /tmp/opencode-logs/d215-20261029T181002-2c23/trap.log, ALL_DONE): oracle 422/422 (passes the new check). Reversed order 410/422 and alphabetical (sorted) order 413/422 both FAIL the new check. QC v3 al27 order 419/422, failing only the new check (was 419/419 full). Print-every-missing 413, reference-files-first 416, only-collectors 413: each fails the new check.

## Deviations from master directions

None. The new check uses one fresh hidden month per pair (a `_run` per pair, label `missing-pair-<i>`), not one month shared across the ten pairs; the property and the assertion are as directed.

## Touched rules

| id | touched how | rules re-checked | verdict with file:line |
|---|---|---|---|
| missing_adjacent_pairs_in_list_order (new, w3) | new positive check | TS-13 one property (list-order precedence on a pair: exit, earlier named, nothing else named); TS-14 name and description state the property (03_Tests_QC.md:45); TS-20 w3 key edge case, not core (:51); TS-25 decisive assert is the earlier name, no program 0/422 and nop 0/422 (:52); TS-26 separate runs and file sets from missing_input_first_named, missing_references_first_in_list, missing_collectors_first_in_list; the QC al27 mutant fails only this check (:53); CL-2 constant-docs program fails it; CL-4 points share 3/422 | PASS, tests/test_output.py:1469-1477, :1853-1854, :2161 |
| tests/reward.toml weights | test_output 0.0011933174224343676 -> 0.001184834123222749 (0.5/422); judge 0.01 unchanged | TS-S10 (03_Tests_QC.md:88): test channel = judge channel = 0.5 | PASS, tests/reward.toml:4 |
| solution/TRUTH.md | regenerated last by WORK/write_truth.py (G6) | DS-22 sha lines; counts 112 pos / 422, 1 neg / -5, judge 23 / 50 | PASS, TRUTH.md:113, :147-149, :193, :195, :295 |
| judge | untouched | JD rules n/a | judge.toml byte-identical to 92ee28b |

## Vacuity probe

Runner WORK/d215/d215_runner.py in `docker run --rm --memory 8g python:3.12-slim` (json WORK/d215/trap_d215.json, ALL_DONE):
- unedited shipped environment and data, no transform program: 0/422 positive points (all 112 positive checks fail).
- empty program: 0/422.
- oracle: 422/422.
- the new check is 0 for both, so it is not vacuous.
- Judge: unchanged since v2 (byte-identical); the manual review of the 18 positive criteria from v2 stands (each needs runs, comparisons, the agent's own transform.py or a response listing written files; judge.toml:14-131, :209-300). Not a scored judge-service run.
Verdict: PASS.

## Side effects

| FIX id | ids re-checked | result |
|---|---|---|
| G05-1 (AL-27) | TS-13 (FIX_SIDE_EFFECTS.md:19: schema v4 minor), TS-14, TS-16 n/a, TS-20, TS-25, TS-26, TS-23 | none new; TS-23 WARN kept with count 113 (was 112), playbook TS-23 KEEP |
| G05-1 (AL-2) | TS-25 | PASS, no program 0/422, nop 0/422, decisive assert earned |
| G05-1 (CL-2) | TS-26; share re-derived | QC v3.md:266 forger (list-order presence checker + constant JSON) 40/419. It checks presence in list order, so it also passes the new check: 43/422 = 10.2% test channel, 5.1% combined. Re-derived, not re-run. Refusal path only; the run constant-docs program earns 22/422 = 5.2% tests-only |
| G05-1 (CL-4) | points share | one wrong quarantine reason loses 8/422 -> 0.981, unchanged in kind |
| G05-1 (AL-27 RULE_COVERAGE) | G11 | WORK/RULE_COVERAGE.md 71 rows, `Rules uncovered: 0 of 71.`; new row "QC v3 al27 order" 1 check (3 pts); sorted 3 (9), reffirst 2 (6), reversed 4 (12), print-all 3 (9) |

## Noise keeps

None. The only finding is REAL.

## Trap survival

Single wrong-reading variant per lever, same runner in Docker; before = WORK/f65c/trap_f65c.json (419), after = WORK/d215/trap_d215.json (422).

| lever | variant | lost before | lost after | ratio (raw points) | separating cases kept | verdict |
|---|---|---|---|---|---|---|
| LV-MU-6 | alone | 204 | 204 | 100% | y, same 50 failing checks | PASS |
| LV-MU-5 | alone | 335 | 335 | 100% | y, same 85 failing checks | PASS |
| LV-MU-7 | alone | 204 | 204 | 100% | y, same 50 failing checks | PASS |
| LV-MU-8 | alone | 160 | 160 | 100% | y, same 44 failing checks | PASS |
| LV-MU-9 | alone | 112 | 112 | 100% | y, same 32 failing checks | PASS |
| LV-MU-1 (noise) | alone | 351 | 351 | 100% | y, same 89 failing checks | PASS |
| LV-MU-3 (noise) | alone | 257 | 257 | 100% | y, same 61 failing checks | PASS |

Normalized retention: 419/422 = 99.3% for every lever, above the 90% floor. QC variant A lost 249 before and after. Verdict: PASS.

## QC_RULINGS rows

- IN-15 | instruction wording | not raised in v3 | n/a | no instruction change
- IN-16 | instruction hints | not raised in v3 | n/a | no instruction change
- TS-13 | one property per check | new check re-checked | PASS | none
- TS-19 | hidden data | new check uses hidden fresh months, one per pair | PASS | none
- TS-20 | weights | new check w3, core weights unchanged | PASS | none
- TS-26 | double pay | new check separated by measured mutants (al27 order fails only it) | PASS | none
- AL-28 | stacking | stacking_check hint unchanged; QC v3.md:282 PASS | PASS | none
- JD-7 | judge | judge untouched | n/a | none
- JD-15 | judge | judge untouched | n/a | none

## Gate results

- Step 10 (run ONCE, TS 20261029T182508-71b4, copies /tmp/d215-copies-20261029T182508-71b4/{plain,owner} built by live kit exe_copy.py rc 0; warm build rc 0; chain log /tmp/opencode-logs/d215-step10-20261029T182508-71b4/runs.log ends `ALL_DONE` at 20:59 IST; bundle lock released):
  - oracle x3 = 1.0 / 1.0 / 1.0 (/tmp/harbor-jobs-qc/metered-d215-20261029T182508-71b4/oracle-1/plain__DFYK6wL/result.json, oracle-2/plain__VTQGUrf/result.json, oracle-3/plain__8bwgybJ/result.json; exception_info None each)
  - owner-only x1 = 1.0 (/tmp/harbor-jobs-qc/metered-d215-20261029T182508-71b4/owner-1/owner__p228SHR/result.json)
  - nop x1 = 0.0 (/tmp/harbor-jobs-qc/metered-d215-20261029T182508-71b4/nop-1/plain__Ag4xvoS/result.json)
  - Host slept about 19:13-19:38 during oracle-2; that run finished rc 0 with reward 1.0, nothing re-run.
- In-container test run (WORK/d215/trap_d215.json): oracle 422/422, no program 0/422, empty program 0/422.
- precheck: last line `PRECHECK CLEAN` (WARN X1 binary skip collector_south.txt, WARN A3 113 checks; both carried, KEPT.md).
- xref_check: 24 entries, 0 findings before and after.
- stacking_check: STACKING PASS (STACKING_CHECK.md).
- diff -rq BUNDLE vs PREV_QC_COPY 92ee28b: only solution/TRUTH.md, tests/reward.toml, tests/test_output.py (all permitted).
- Tree sha (sha256 over byte-sorted ./paths + bytes, first 12, 23 files): before 396efb9b4952 (92ee28b copy; the prompt's e118610c514f is from a different hash method, the copy is byte-identical to the pre-edit bundle by diff -rq), after BUNDLE 76d42cbcdfac, Tasks_INPUT 76d42cbcdfac.
- `rsync -a --delete BUNDLE/ Tasks_INPUT/metered-usage-rating-pipeline/` rc 0; `diff -rq` empty.
- LSP: basedpyright not installed, so no LSP-clean claim; AST parse of tests/test_output.py OK (113 checks).

## Lessons for the master

- A precedence chain over N items needs N-1 pair fixtures from the first fix; partial multi-fault sets cost two rounds here | template_change: master_chat_tasks/knowledge/QC_FIX_PLAYBOOK_v3.md:36 AL-27 DO column, add "one hidden input per adjacent pair of the chain, taken in the stated order"
