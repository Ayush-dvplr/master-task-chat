# DIAGNOSIS ed621c7: tariff-engine-audit-repair, harden round _ql1

Run read: Output_RFP .../claude-opus-5/run_1 (our pushed run a4, trial Y6rWvWB, job 80a4d91e, 59 steps, 20 min, $5.69): tests 397/488 = 81.35, judge 6/33 = 18.18, final 49.77. QL regrade of the same trial on his bytes (trial 6107faf5, `source_trial.action = regrade`): tests 81.35, judge 9/33 = 27.27, final 54.31; the only flip is R13 0 -> 1 (judge noise, one criterion).
Kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271, `git diff 5574d77e HEAD -- Input_Bundle_QC/` empty. Fingerprints GEN 160/160, QC 12/12 match. No tariff `baselines.json` exists. Session rename: name_session.py listed `ses_e7b4f9be3ffeGLih7pSg6duCMe` for opencode, no explicit ed621c7 line.
Trajectory read-out: [TRIP.md](TRIP.md) (tool rows + hand rows). Agent program: [agent_program/](agent_program/).

## Phase A: GENUINE
- Every ctrf id (116) exists in the pushed BUNDLE `tests/test_output.py` and in the QL copy. `diff -rq BUNDLE ql_bundle`: only `solution/TRUTH.md`, `solution/solve.py`, `tests/test_output.py` differ (the three QL edits in CHANGES.md).
- `result.json` exception_info None; test-stdout `reward: 0.4977`; no Errno 13, no missing files; judge reasonings quote the response and files.
- Failed ctrf rows: the 21 `*_ledger_statement_*` checks only (the two negatives show "failed" = not triggered; reward-details values 0).

## Root cause
| cause | verdict | evidence |
|---|---|---|
| 1 run error / wrong copy | NO | tree matches; no errors |
| 2 harness / rescoring change | NO | kit diff empty; reward.toml 0.5/488 + 0.5/33 unchanged; 49.77 vs 54.31 = R13 judge noise |
| 3 our QC/fix rounds made it easier | PARTLY | P12 8e1b2d5 stated L11 (contract :66-67, :121-123) and split shipped checks into w1/w3 rows (+ about 12 easy points); QL edits touch only solve.py/TRUTH/tests, no new rule in front of the agent |
| 4 levers weak by design | YES, PRIMARY | every invoice rule is a formula beside its field plus a worked example; the r3 statement corpora keep balances below 1.2e7 cents so the reflex cent bitset fits; only the hidden-scale ledger held |

Correction to TRIP_ql.md and the read-out tool: the ledger loss is not a WRONG document. Docker (python:3.12-slim, `--memory 4g --cpus 2`, agent package, pushed `_ledger_texts`): fresh corpus agent rc -9 at 5.79 s, rotated rc -9 at 6.09 s, reference 0.03 s each. The cent bitset needs ints of 3.75-12.5 GB at balances 3e10-1e11 cents: CRASH by OOM under the declared 4096 MB. It counts under v3.5 hidden-scale: shipped inputs fast (`--statements /app/ci` 0.42 s at step 38), limit stated (:25-28, 10 s, plus task.toml memory_mb 4096), each ledger corpus is its own call.

Cause 4 per rule (rule text / where right / giveaway):
- N1 re-share, carry (:186-196): first write step 21-22 core.share_allowance; formula + toy beside field; self-test step 53 (20000 random cases on its own reading).
- N2 calendar-month proration (:177-181): step 22; formula beside field.
- N3 account tier position (:42-44, :169-171): step 22; stated with field.
- L11 plan codes (:66-67, :121-123): step 16-22; stated since P12.
- U1 revisions unique fit (:68-75), D1 arrears (:198-206), D2 cumulative reads (:57-63): step 16-22; each one sentence, no second reading.
- Q1-Q5 quiet branches: step 16-22; each branch's rule beside its field; agent's code covers all branches without probing.
- S1 r3 statements (:211-226, toy :228-231): step 22; the stated rule + small balances make the cent bitset exact; step 38 timing on shipped data confirmed it.
- S1L ledger (same text, hidden scale): HELD, never stress-tested by the agent.
Judge half (a4): PASS R8 (step 61 response lists functions; free, J1-style), R12 (step 53 own tier input). FAIL R7 (dead REASONS tuple, step 22). SKIPPED R1-R6, R11, R13 (R13 passed in the regrade). Judge probe share is 27/33 = 82%, above the 55-70% band, but the probes it holds are the ones the agent skipped; J3a/R9/R10 untouched.

## Lever table (reward-details.json)
| check family | pts | earned | lever / template | status |
|---|---|---|---|---|
| `*_ledger_statement_due_exact` x7 | 35 | 0 | S1L hidden-scale ledger | HELD (CRASH) |
| `*_ledger_statement_redeemed_exact` x7 | 35 | 0 | S1L | HELD (CRASH) |
| `*_ledger_statements_feasible` x7 | 21 | 0 | S1L | HELD (CRASH) |
| `*_statement_due_exact` / `_redeemed_exact` x7 | 70 | 70 | S1 r3 + D1/D2/Q/U1 per corpus | LEAKED |
| `*_statements_feasible` x7 | 21 | 21 | S1 | LEAKED |
| `*_subtotals_exact`, `*_credits_and_totals_exact` x7 | 70 | 70 | N1, N3, D1, L11 | LEAKED |
| `*_lines_exact`, `*_energy_lines_exact`, `*_standing_lines_exact` x7 | 50 | 50 | N1, N2, N3, L11 | LEAKED |
| quiet / U1 / D1 / D2 account families (25 x 5) + carried 3 + combined_row 6 | 134 | 134 | Q1-Q5, U1, D1, D2, T4 | LEAKED |
| shipped / delivery / report / regression / visible / missing_source / two_runs | 37 | 37 | interface | EASY |
| negatives (-5, -3) | 0 | 0 | AL-28 acts | not fired |
| judge R1-R6, R11, R13 | 24 | 0 (3 in regrade) | P-c, P-a, P-d | HELD (skipped) |
| judge R7 | 3 | 0 | code quality | HELD |
| judge R8, R12 | 6 | 6 | response list, P-a own input | LEAKED |

Arithmetic: final = (81.35 + 18.18)/2 = 49.77 (regrade (81.35 + 27.27)/2 = 54.31). A probe-band judge rebuild alone at the peer probe pass rate 25%: (81.35 + 25)/2 = 53.2, gate not met; the tests half must fall to about 50.

## Autopsy (B1)
- 17:10:19-17:10:58 read /app tree, api_contract.md (step 4), repo src (6), ci configs, lint, failing log (7-9), rate_card (10-11), test_visible (12).
- 17:13:20-17:13:37 data profiling of meter_reads and regression cases (13-15).
- First write 17:15:23-17:17:57 (steps 16-26): parser, core (incl. bitset `redeem`), report (incl. `build_statements`), `__main__`, pyproject. Five minutes after start, before any test.
- 17:18-17:22 corrected visible test, unittest, replay/diff scripts on regression rows, contract worked-example checks (28-37).
- Step 38 timed both CLIs on shipped data (0.47 s / 0.42 s). Steps 43-55 core checks, parser fix (46: `row.get('quantity')`), redeem mask change (52, the only other graded-logic edit), 20000-case allowance self-test (53), small random-directory fuzz (54-55).
- 56-61 deliverables, archive diff, cleanup, final message claiming verified.
- Self-tests covered N1 (own reading), shipped contract examples, regression rows; none covered a large balance or many vouchers. Slowness never noticed.

## Why it scored 81 / 18
Opus reads one contract whose every invoice rule is written next to its field, writes all of it right in one pass, and checks it against the worked examples. The only test points it loses are the ledger corpora, where its first reflex (exact cent bitset) dies by memory. The statement rule is the single place the task has a computational core; 91 of 182 statement points sit at a scale where the reflex survives.

## Planned fix (Phase 2, measured in the kill table before DESIGN READY)
- F0 master steps: back up BUNDLE to WORK/pushed_0de116d29fdb/, replace with ql_bundle, add the `_visible_test_removed` add-on (setUpModule/tearDownModule FunctionDef, module-level Assign/Expr skip names), replay both CHANGES.md bypasses and show they fire; Docker oracle x1 + nop on QL bytes.
- F1: keep the 21 ledger checks. Move the 7 r3 statement corpora (`*_statement_*`, 91 pts, names and weights unchanged, new instances) to hidden scale. Each hidden statement document carries two hard accounts beside the quiet small ones: a ledger-shape account (unit group + small group, kills plain gcd and MITM by size) and a large-arbitrary account (34-38 vouchers, gcd 1, balance 3e10-1e11 cents, ties planted at the best sum across halves; kills the cent bitset and the gcd split). One call per corpus, so any single-technique program loses the whole document; a tie-naive search loses `redeemed` by WRONG. Reference: gcd split when the small group is at most 20, else meet-in-the-middle with first-id-list tie (smaller ids in the first half); exact on all inputs (AL-2), target <= 2.5 s (1/4 of 10 s), measured on 300 seeds.
- F2: two more 7-corpus statement sets (due w5, redeemed w5, feasible w3; 91 each) on reseeded documents with both shapes. Positive tests 670; lever 364/670 = 54.3% (>= 40%); held-out w5 share rises.
- F3 judge: three statement probes the agent skipped (P-a own input with an account of more than 30 vouchers and a balance above 100000000.00, timed against 10 s; P-c redeemed recomputed outside the program on an own tied input; P-b/P-g witness of one tie decision), oracle prints `check <id> ok` + witness. Agent-style judge 9/42 = 21.4%.
- No new rule text: the statement rule, 10 s sentence and memory limit already stand; no "other scales" wording; no method words (IN-17).
- Predicted (a): first-write program and every single-technique solver: tests 306/670 = 45.7%, judge 21.4%, final 33.5 (judge noise +1 criterion: 35.3; judge at the observed 27%: 36.5). Below 40 in every case.
- Rejected: invoice-side scale (agent code is linear apart from constants, and `python -m tariff` has no stated limit, a hole); reweighting (never after a run); F1 alone (lever 37.3%, tests 62.7%); judge rebuild alone (53.2).
- Risks: verifier time (each extra corpus one subprocess capped at 10 s; worst 21 x 10 s + reference, inside 2700 s); reference speed on the arbitrary account in pure Python (measure first; fall back to 32-34 vouchers); kill table must show bitset CRASH, gcd-split TIMEOUT, MITM-only TIMEOUT, tie-naive WRONG on >= 15% lever points.

## LEAK_LIBRARY rows
| lever | how it was written | leaked at | fix rule |
|---|---|---|---|
| S1 statements, shipped-sized held-out corpora | api_contract.md:211-226 rule + toy; hidden balances below 1.2e7 cents let the exact cent bitset fit | step 22 first write, step 38 timed 0.42 s | hidden scale on every statement corpus, two hard shapes per document (F1/F2) |
| N1 allowance re-share | :186-196 formula beside field + toy | step 21-22; self-test step 53 | none in tests without a hole; weight moved to statements |
| N2 calendar-month proration | :177-181 formula beside field | step 22 | as N1 |
| N3 account tier position | :42-44, :169-171 stated with field | step 22 | as N1 |
| L11 plan codes | :66-67, :121-123 (stated in P12) | step 16-22 | as N1 |
| U1 / D1 / D2 | :68-75, :198-206, :57-63 one sentence each | step 16-22 | as N1 |
| Q1-Q5 quiet branches | each branch rule beside its field | step 16-22 | owned-row criteria stay; no fix possible without a hole |
| judge R8 | asks the response to list changed functions | step 61 | free; leave (J1), F3 adds skipped probes |

## Lessons for the master
- The read-out tool classes a hidden-scale OOM as WRONG; check rc in Docker before writing "WRONG and silent" | template_change: master_chat_tasks/tools/trajectory_readout.py class rule (no reason text -> UNKNOWN, not WRONG)
- Held-out w5 share already 53% here and the agent still scored 81: held-out instances are no hardness when every rule sits beside its field | no change: LEVER_RULES 1D already marks N2 PROMISING only
- A scale lever applied to half of one family leaves the other half as free points for the same reflex | no change: covered by v3.7 lever share >= 40%
