# hangar-check-replan: dabfeb4 QC v4 Repair

## Verdict

**PAUSED.** All six requested code repairs are applied, and F03 is kept. The unchanged a1 program on the repaired tests earns 179/344 = 52.0348837% tests-only. With the unchanged judge estimate 12/39, predicted final mid is 41.4020572%, failing the master's strict <40 gate. No weights were lowered, no further certification lanes ran, and Tasks_INPUT was not synced.

A separate release blocker remains: the read-only generator validator requires the exact deleted source-token-negative name. Its result is 38 PASS / 1 FAIL, not a clean validator gate. No kit or generator edits were made.

Bundle: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/hangar-check-replan`.
Work: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/hangar-check-replan`.
Scratch: `/Users/mac/Desktop/Terminal Bench/_runs/20261102/hangar-check-replan/fix3-20261102T225013`.

## Finding Repairs

| ID | Old -> new, with source anchors | Playbook row and rechecks | Result |
|---|---|---|---|
| F01 | Old test_output.py:1415-1431 searched source IDs/filenames; wrappers and registrations at old :1833-1840/:1923-1924 charged them. Removed both helpers, _py_source_text, wrappers and registrations; current :1434 retains only observed tree-mutation detection. | TS-16/TS-14, AL-28; explicit master override permits removal rather than a renamed token detector. No replacement detector added. | Source literals/comments/IDs cannot trigger a deterministic negative. |
| F02 | Old shipped plan/group/settlement weights 3 -> 5; h1-h6 plan_rows 3 -> 5; group_totals and three settlement views 1 -> 5. Current test_output.py:1841 and :1845-1874, h4 group/per-check/by-group :1861-1863. reward.toml:4 changes 0.5/230 -> 0.5/344. | TS-20, CL-2/3, G1-G7; 33 weights raised, no existing weight lowered; h7-h15 unchanged. | Core restored; hardness gate fails, so PAUSED rather than weight cutting. |
| F04 | solve.sh formerly ended at :315 after probes. New :316-323 reads the produced policy_audit.json, selects decision=deferred and prints each request_id. | JD-7; JD-2/5/8/9/15, IN-8. R9 remains byte-equivalent as a parsed criterion. | Exact final heredoc executed in the diagnostic container: `Final response: deferred request_ids: Q68307`, `WITNESS_MATCH 1`. No ID hardcoded in the witness. |
| F05 | Previously no owners for stdlib imports, other out-of-scope program I/O or online solutions. judge.toml:233/:246/:259 adds R18/R19/R20, -5 each, explicit step evidence and stand-down. | JD-5/8/14/15/16, AL-28, JD-7 evidence; manual ownership matrix in STACKING_CHECK.md. | Four QC scripts zero FAIL; judge schema loads. R1-R17 and all positive weights unchanged. No live judged run claimed. |
| F06 | Removed negative_reads_check_files and its source-string checks/registration. judge.toml:181 R14 is the sole grader-access owner. | TS-16, AL-28; R18-R20 stand down for R14-owned acts. | No deterministic charge for grader filenames or actual grader access. |
| F07 | render formerly returned after eight raw inputs and _shipped_root rebuilt only those inputs. Current test_output.py:609/:613/:620/:948 installs six unchanged compressed governing docs before sealing. | TS-19, IN-16, DS-21/22, AL-18/19; expected derivation, raw files and _build_case unchanged. | All 18 canonical expected-output byte streams hash identically before/after; all 108 doc copies match; reference tests-only score 1.0. |

F03's count warning is kept without consolidation: 77 -> 75 only because the master required deleting two negatives. See KEPT.md for surviving fix2 rows and explicitly superseded history.

## Weights and Gate

| Measure | Before | After |
|---|---:|---:|
| Positive tests / points | 74 / 230 | 74 / 344 |
| Negative tests / total | 3 / -13 | 1 / -3 |
| Total checks | 77 | 75 |
| h7-h15 lever points | 165 | 165 |
| Lever share | 71.7391% | 47.9651163% |
| a1 tests-only score | Historical 65/230 = 28.3% | Measured 179/344 = 52.0348837% |
| Positive judge | 13 / 39 | 13 / 39 |
| Negative judge | 4 / -16 | 7 / -31 |
| test_output reward coefficient | 0.002173913043478261 | 0.0014534883720930232 |
| judge reward coefficient | 0.01282051282051282 | Unchanged |

Predicted judge low/mid/high remains **23.1 / 30.8 / 46.2%** (rounded 9/39, 12/39, 18/39). Using those exact fractions, predicted finals are **37.5559034 / 41.4020572 / 49.0943649%**. These are estimates, not measured judged rewards.

Even a conservative lower-bound restoration of only h1-h6 group totals and the three settlement views adds 96 points, producing 161/326 expected a1 tests and predicted final mid 40.0778669%. The implemented full core restoration is required; neither core nor lever weights were cut to manufacture a pass.

## Docker Diagnostic and Kill Table

The sole actual container used final tests from the live kit's `fix3_exec_final` tests-only copy. `dockfree` printed `FREE_MB=4706 USED_MB=8192 CONTAINERS=2 CPUS=4/12 START=yes`. Container `dabfeb4-fix3-diagnostic` used `--memory 4g --cpus 2 --network none`, `--rm`, and `perl` alarm 2100. `diagnostic3.log` ends `EXIT=0` and `ALL_DONE`.

| Program / check | Current result | Loss type / timing |
|---|---|---|
| Reference solution/solve.py | 344/344 = 1.0 tests-only, negatives [], errors {}, shipped rc 0; all 33 lever checks E | Case generation plus first execution 430.4s; shipped run 0.1s. This is a driver diagnostic, not a Harbor verifier lane. |
| Paid a1 program | 179/344 = 52.0348837%, negatives [], errors {}, shipped rc 0 | All 33 h7-h15 checks W, 165/165 lever points lost by WRONG output, no TIMEOUT/CRASH; program reruns 16.3s. |
| Expected-output comparison | 18/18 identical SHA256 values | Shipped, h1-h15, m1/m2, canonical sorted compact JSON bytes; expected_before.json equals expected_after.json. |
| Governing-document comparison | 108/108 byte-identical copies | Six docs in each of the 18 actual scored corpora; docs_by_corpus.json records hashes. |
| Blinds | NOT RUN on final tests | Stopped under F02; historical kill results are not reused as current evidence. |
| All-but-one | NOT RUN on final tests | Stopped under F02. |
| solve_no_cxml | NOT RUN on final tests | Stopped under F02. |
| Lever-aware / careful-reader | NOT RUN on final tests | Stopped under F02; the reference row is not relabeled as an independent kill program. |

Trap survival: h7-h15 retains every separating case and registration; a1 loses 165 points before (historical) and after (current), ratio 1.0 in raw lever points. Its share falls from 71.74% to 47.97% because core weights were restored. This proves a1's lever loss, not the omitted full kill table.

Harbor certification lanes **not run**: oracle x3, owner-only, nop, stub, forgery, and Harbor a1. Their rewards and verifier seconds are unmeasured/null. No claim of the requested <=2430s verifier headroom or full solve.sh certification is made. The two earlier launch attempts only checked/waited for capacity and never created containers; the finished diagnostic was not rerun.

## Static Gates and Integrity

- GEN 160 / QC 12 fingerprint files: zero content mismatches before work; live QC kit 5574d77e.
- Final precheck: four live QC scripts exit 0 with zero FAIL; last line **PRECHECK CLEAN**. `precheck_final.log` preserves X1/A3 and JD-5 sentence-count warnings.
- Manual JD-5 review: R18-R20 each grade one act; evidence, exclusions and stand-down sentences constrain that act. JD-8/14/15/16 and AL-28 checked across both layers in STACKING_CHECK.md. Static name/literal grouping false alarms are retained alongside the manual resolution, not hidden.
- Generator validator: **38 PASS, 1 FAIL**. §7.4 says `negative_hardcoded_sample_answers missing or non-negative`. Read-only validate_bundle.py:738-740 requires that exact registration; master note 2 (issued prompt line 29) requires its deletion. No rename, dummy negative or kit change was used to bypass the conflict.
- xref_check: 12 entries, **0 findings**. TRUTH_AUDIT_CLEAN validates all five recorded SHA256 values and actual counts. FINAL_AUDIT_CLEAN verifies all 33 increases, unchanged h7-h15, R1-R17, data/instruction/task/solve.py and isolation helpers.
- Python AST / TOML schema / bash syntax pass. LSP could not run: basedpyright and bash servers were not installed and installation had previously been declined; TOML has no configured server. No clean LSP result is claimed.
- Bundle tree **3d309582f41d**; initial/pre-fix **0163b9762e5b**; untouched Tasks_INPUT **0163b9762e5b**. No sync/diff-equality claim. No __pycache__ under the bundle or Tasks_INPUT.
- Changed bundle files: tests/test_output.py, tests/judge.toml, tests/reward.toml, solution/solve.sh, solution/TRUTH.md. Work maps/defences/XREF/TODO/LOG and audit scripts updated outside the bundle. Per-file digests: WORK/fix3_pre_digests.json and OUT/bundle_audit.json.
- TRUTH.md was the last bundle edit; hashes were computed by script and applied, then independently rechecked. No edits to environment inputs, instruction.md, task.toml, solve.py, the harness, QC copies, jobs, or Anubis repositories.
- Cleanup: own diagnostic container auto-removed; no own waiting launcher, driver or Docker child remains. Other sessions' containers were untouched. Initial rename found the OpenCode session ses_e62ba2e3effeuLOaf6EYUP11gI; Codex had no match. Final rename uses only dabfeb4.

## Lessons for the master
Core restoration makes final mid 41.40%; an alternative direction needs master approval, not silent weight cuts. | no change: explicit F02 stop rule followed
Validator §7.4 hard-requires the source-token-negative name that this prompt removes. | template_change: reconcile validate_bundle.py:738 with behavioral-negative policy
Precheck sentence/name hints require an act-level audit; they are not a reason to undo explicit stand-down. | no change: manual evidence retained
