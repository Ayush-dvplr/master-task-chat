# flood-repair-portfolio: r6 build ea04435

## Scope and Provenance

Built in place from bundle tree `7d68065946fd`; no regeneration, force option, git write or paid LLM attempt. Live QC kit HEAD: `5574d77eb9f22c207ba05fd8f9ac31d42ba45271`. Evidence root: `/Users/mac/Desktop/Terminal Bench/_runs/20261102/flood-repair-portfolio/r6b-20261102T2018/` (called R below). WORK is `master_chat_work/bundles/_work/flood-repair-portfolio/`.

The initial rename command exited zero and returned opencode session `ses_e63461152ffeiaRlDOTEC3adZ8`; its output listed the session id, not an explicit title confirmation. No alternate id was tried.

## Lever and Generator

Kind (c), measured scale/time-budget lever A+B: six crowd rounds per hidden book. `tests/test_output.py:795` invokes the separate stream `_Rng(seed * 37 + 9011)` after ordinary rounds, faults, audits and existing capped rounds have consumed their original draws. `_crowd_round` at line 808 replaces large-round indices 0,10,20,30,40,50 with 150 lattice proposals; `_add_crowd` at line 826 adds ten isolated proposals on one shared crew new to that round. New sites and values are generated through the book's existing machinery, including `value_large`. Assertions preserve the conflict graph and verify ten members on a shared crew. The H1/H2/H3 specs at lines 939/962/985 enable it; no other book enables it.

Burn-and-replace preserves the ordinary RNG draws, not assembled H-book bytes: final row shuffles and round identifiers differ from the measured r6_budget books. The permitted alternative was used: all programs were re-measured on the verifier's own newly pinned books. SHA256 pins are H1 `cfd4f4080935918abfc8091b68170364a567d195a81e869bcbb79a1ff238b3fe`, H2 `36c160f4db57f14ad03ee210c7be12909e987e809423a59985ae55f5af1bb9cb`, H3 `e2728f61b7685a3e1d855aa12945c3849e35e39754e40d183025c903a5540fb6`.

P is paid attempt 4's `derive_report.py`, SHA256 `e2f9460ff73a883b9c93a085a56ebee619a459e1bd94edbe3643a7955a397b86`. P:361 enumerates C(10,6)=210 drop combinations, below COMBO_CAP 256, but repeatedly solves the full lattice. A four-second round budget expires; P:355-356 replaces the result with greedy. P:24/P:921 then exhaust the thirteen-second book budget. Reference `solution/solve.py:261` splits independent components instead. No correctness rule or time limit was changed.

Named witness copied without altering its source: `WORK/r6_build/witness/witness.json` and its book/outputs. Round R39321 traces capped_dp timeout at 4.006 s and greedy on 160 proposals: P total 63929 versus oracle 73387; eight documents differ. This is the original measured witness, not a claim that R39321 occurs in the rebuilt books. Contrast P:355-356 with the unchanged exact verifier `_capped`, originally test_output.py:1260-1277, now lines 1328-1345. The rebuilt H1 first wrong round is R14594 (expected 63220, P 51067).

## GO Bar on Verifier Books

All G1 runs used Docker, four GiB/two CPUs and wall caps. `logs/g1.log` has the final bare `ALL_DONE`; no completed block was repeated.

| Bar | Measured result | Verdict |
|---|---|---|
| P and P_x4 wrong on H1-H3 | Both wrong 3/3, each 6/25 per book | PASS |
| P_inf exact | Exact 3/3, 25/25 per book | PASS |
| P loses at least 44 positive points | 19 per book, 57/108 total (52.7778%) | PASS |
| Reference with CPU burner at most 5 s | 1.9030 / 1.9951 / 2.2411 s | PASS |
| Contract bounds | 103 rounds each; maximum 160 proposals; record maxima 517/505/488, below 900 | PASS |
| 300 shape seeds | 300 seeds, zero errors; `_check_bounds` exercised | PASS |
| Old books/documents unchanged | SHIPPED/M/MS/MR file and expected-document digests identical before/after | PASS |
| Full verifier at most 2430 s | Oracle maximum 655.809117 s | PASS |

No test criterion or test weight changed: 34 registered tests, 32 positive worth 108 and two negative totalling -8. Existing helper/check ASTs are unchanged; only existing function `make_book` changed, with new `_crowd_round` and `_add_crowd` helpers, constants, H specs and pins. Shipped data (including contract.md), instruction.md, solve.py, Dockerfiles and task.toml are byte-identical to the snapshot. There is no public-document change.

### Kill Table and Timing

Points below concern the 75 positive H1-H3 points, not the full test channel. P is first as requested. TIMEOUT is the twenty-second submitted-program cap, not a verifier timeout.

| Program | H1/H2/H3 verdict | H points /75 | H1/H2/H3 seconds |
|---|---|---:|---|
| P (paid_a4) | WRONG / WRONG / WRONG | 18 | 13.3155 / 13.5669 / 13.2977 |
| P_x4 | WRONG / WRONG / WRONG | 18 | 52.4037 / 52.8959 / 52.2947 |
| P_inf | EXACT / EXACT / EXACT | 75 | 355.9408 / 127.7904 / 90.1708 |
| blind4_b1 | EXACT / EXACT / EXACT | 75 | 7.2789 / 4.8336 / 5.2462 |
| blind4_b2 | WRONG / WRONG / WRONG | 18 | 14.5925 / 7.0923 / 12.1387 |
| first_write | TIMEOUT / TIMEOUT / TIMEOUT | 0 | 20.0397 / 20.0258 / 20.0139 |
| all_but_one | TIMEOUT / TIMEOUT / TIMEOUT | 0 | 20.0286 / 20.0155 / 20.0087 |
| lever_aware | EXACT / EXACT / EXACT | 75 | 3.0637 / 1.2732 / 1.3617 |
| reference | EXACT / EXACT / EXACT | 75 | 1.5842 / 1.6466 / 2.1044 |
| reference_busy | EXACT / EXACT / EXACT | 75 | 1.9030 / 1.9951 / 2.2411 |

Independent verifier ledger times: 222.4857 / 241.9633 / 149.9916 s; ledger documents matched the reference exactly. Receipts: `R/scratch/results_H1.json`, H2 and H3. P second runs took 13.5974 / 13.5303 / 13.5105 s and were byte-identical to the first run on all three books. Because P branches on real time, future paired runs can still differ; `reruns_identical` was neither added nor removed to conceal that risk.

Expected-document SHA256s, identical before and after (`R/scratch/digest/before.json`, `after1.json`): SHIPPED `07ba9be145c769a03ab4ccc796e5277b7840097d478cbfb0a4e26425b0b7174e`; M `fcd3e6a9a9d7f35311e01ac6c8d87aeac723982faf81e5797665b1275adb5693`; MS `267fa5f584fdffede19ecb9a4370269cb5d8d98c3d10028ed556e156af0a813d`; MR `07f180fb96e35afe51a3885aea67eb31962ba8855c9b9193ac5049149637f6fb`. Relocation uses the same unchanged books/documents; missing-input and artifact checks retain exactly their old assertions and expectations.

## Judge Probes and a4 Grade

Three weight-3 process probes were inserted at `tests/judge.toml:116`, :129 and :142. Each has a same-criterion stand-down alternative for a lever-aware proof, and a solve.sh witness at lines 244/252/260. Old R9-R12 became R12-R15. Judge positives changed 32 to 41 (13 positive criteria; 15 including negatives). The reward judge multiplier changed from 0.5/32 to 0.5/41 = 0.012195121951219513; the test multiplier remains 0.5/108. Both channels still contribute one half.

| New criterion and quoted verdict | a4 evidence | Oracle witness |
|---|---|---|
| R9 timing a 160-row over-four shared-crew round: "fail / fail / pass" (low/mid/high) | Steps 57-58,77,84 time max-size random-crew books, but do not explicitly build a shared crew with more than four members; step 86 reports zero DP successes, not an exact time bound. High generously counts max-size timing alone. | Built round R79260, 160 rows including ten on C1012, timed 0.28 s; `check R9 ok`. |
| R10 second exact method on that scale/cap: "fail / fail / fail" | Steps 38-40 brute-force small rounds; step 48 random rounds have at most 14 proposals. No corresponding 160-row over-four exact cross-check or code-tied exactness proof. | Exhausts 386 keep sets of at most four new isolated members, combines with the unchanged lattice optimum, compares selection/tie order and total 76239; `check R10 ok`. |
| R11 read uncertified-return paths, name functions and returns: "fail / fail / pass" | Step 64 writes greedy replacement on Timeout; step 75 returns best-so-far after timeout. Step 94 loosely says degraded rounds return best-so-far, without function names or the greedy replacement. High accepts that loose account. | AST-read delivered solve.py, imports configparser/csv/io/json/os/sys, no clock/search-limit path; `check R11 ok`. |

All original conduct witnesses and new witnesses passed in Docker (`logs/solvesh2.log`, exit zero, R1-R11). Existing positive passes on a4 are R1/R3/R4/R6/R13 (17 points). R14, the retained unrun-check claim penalty, fires at low/mid: final claims refer to checks not repeated after step 78's budget edit, giving 12/41. High drops that penalty and grants R9/R11, giving 23/41. Predicted judge low/mid/high: **29.2683 / 29.2683 / 56.0976 percent**. This is an evidence-based manual grade, not a new model-judge run.

No extra negative was added: the visible silent greedy issue already affects maintainability and the return-path probe, so an added penalty would stack on the same act. The byte-rerun candidate was dropped because step 96 compares outputs; the import-list candidate was dropped because step 89 displays imports. `WORK/JUDGE_MAP.md` records each criterion and witness. Ten weight-3 probes are 30/41 = 73.17% (75.61% including the weight-1 tie probe), above the general 70% aim under the specific master instruction to use weight 3 and avoid unrelated additions.

## Static Gates and Isolation

`logs/precheck_final.log` ends exactly `PRECHECK CLEAN`; structure, instruction, tests and judge QC scripts each exit zero. `logs/validator_final.log`: 41 passed, zero failed, zero warnings, GATE PASS. `xref_check.py`: 36 entries, zero findings. The first precheck found the positive-description word "without"; wording was corrected without changing the acts or stand-down alternatives, then precheck and validator passed. Supplemental JD-5 clause warnings for required stand-down sentences, J1 timing/cross-check heuristic notes and optional SELF_CHECKS.md absence are recorded rather than hidden. No unresolved/pre-existing FAIL remains.

`STACKING_CHECK.md` contains raw output plus hand corrections for lambda-bound books and document tuples. Hidden/mutated tests account for 92/108 positive points. `RECHECK_FIX.md` records the touched-check/rule review and vacuity review. WORK/LEVERS.md, QC_DEFENCE.md, EVIDENCE_MAP.md and JUDGE_MAP.md were updated; TRUTH.md was regenerated by `WORK/r6_build/truth_update.py` last after tests/solution edits, with measured oracle provenance and actual solution hashes.

The agent image copies only shipped data, not hidden generators, hidden values or expected outputs. `/tests` is root-private; expected documents live in verifier memory, and measurement output leaves use mode 0700. Submitted processes start in a separate session and are killed as a group on both normal and timeout exits; escaped nobody processes are reaped by the existing launcher. Each Docker launch was admitted by dockfree START=yes, limited to four GiB/two CPUs and wall-capped. No harness clone, QC kit, protected WORK history or Output_RFP content was edited.

LSP diagnostics were attempted, but basedpyright is not installed (installation previously declined), and no TOML/Markdown language server is configured. Verification instead used Python AST parsing, shell syntax checks, schema QC and actual Docker/Harbor runs. No diagnostics result was invented.

## Final Execution Gates

All copies came from the live QC kit's exe_copy.py; the owner copy used --owner-only. Nop, then stub, then forgery ran sequentially in their queue. The paid lane installs the existing a4 source, not a new paid model attempt. OPENAI_API_KEY was unused, the judge was removed by exe_copy, and Harbor was driven with yes. Every lane has HARBOR_RC 0, a final bare ALL_DONE, and null exception_info.

| Lane | Trial | Raw points /108 | Tests-only reward | Verifier seconds |
|---|---|---:|---:|---:|
| oracle 1 | plain__hU3FVoU | 108 | 1.0000 | 655.809117 |
| oracle 2 | plain__4djhLii | 108 | 1.0000 | 651.167954 |
| oracle 3 | plain__B5dSdgT | 108 | 1.0000 | 527.382443 |
| owner-only | owner__VFQeH8S | 108 | 1.0000 | 500.797812 |
| nop | plain__s7t4VPh | 0 | 0.0000 | 513.554693 |
| stub | stub__pv9ZaTm | 1 | 0.0093 | 500.823477 |
| forgery | forgery__BBuHFKk | 16 | 0.1481 | 437.477505 |
| P final tests | paid__HrEL8N2 | 51 | 0.4722 | 513.155045 |

Rewardkit rounds channel rewards to four decimals; projections use raw points. Stub passes only artifacts_present. Forgery computes shipped documents once and replays them, passing only artifacts and shipped checks. Neither receives a negative penalty. Results and reward-details.json are under `R/scratch/jobs/r6b-<lane>/<trial>/`; `R/scratch/gates.json` consolidates receipts.

P fails precisely optimal/summary/policy_audit/regions/segments on H1, H2 and H3 (57 points), keeps hidden feasibility/data-quality and every old check, passes reruns_identical, and fires no negative. Source SHA matches the paid a4 program. Its actual final test percentage is **51/108 = 47.222222**. This run's paired outputs agree; timing-dependent divergence remains possible on future runs.

| Projection | Low | Mid | High |
|---|---:|---:|---:|
| Judge percent | 29.268293 | 29.268293 | 56.097561 |
| Final = (tests + judge)/2 | 38.245257 | 38.245257 | 51.659892 |

The build meets the explicit judge-mid <=30 and final-mid <=38.6 bars, and its midpoint satisfies tests <85, rubric <85 and final <40. It misses the aspirational R5 final <=35 by **3.245257 points**. The generous high projection does not satisfy final <40; no guaranteed paid-run outcome is claimed. Even the former high case that rejects all new probes yields 44.342818, so this remaining rubric discretion is material.

## Sync and Handoff

`rsync -a --delete` copied the final BUNDLE into the expressly authorized Tasks_INPUT/flood-repair-portfolio copy. `diff -rq` exited zero with empty output. BUNDLE tree SHA **d4059c875b73**, Tasks_INPUT tree SHA **d4059c875b73**, both measured with the required sorted per-file SHA pipeline. No __pycache__ is present. Exactly five bundle files differ from the starting snapshot: tests/test_output.py, tests/judge.toml, tests/reward.toml, solution/solve.sh and solution/TRUTH.md; no file was removed. All public instruction/data bytes remain identical.

Both queues have final ALL_DONE. Final Docker listing is empty and the worker-process audit reports zero own queue/Harbor/measurement workers, so no child/container needs killing and none is left running. Build status: **DONE**, with the midpoint/high-grade risks above, not a freeze or model-run approval.

Not run: a new model-judge grading call, a new paid LLM attempt, the master's separate full QC or freeze, or oracle optimization (unnecessary under TS-11). No commit, push, pull, PR, regeneration or force action occurred. Next: master issues full QC, then freeze and one paid run.

## Lessons for the master
Measure the verifier's own final books, not just design-side copies | no change: the prompt already requires this.
Keep permissive high rubric grading visible beside a passing midpoint | no change: low/mid/high exposes the residual gate risk.
Preserve the repeatability check despite time-dependent fallback behavior | no change: timing uncertainty is evidence, not a reason to weaken tests.
