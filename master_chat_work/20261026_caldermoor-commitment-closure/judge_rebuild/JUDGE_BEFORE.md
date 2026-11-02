# caldermoor-commitment-closure: judge before the v3 rebuild (da62834)

Source: `tests/judge.toml` as of 25 Oct (13 criteria, positives 25 points), probe 5 verdicts from
`Output_RFP/caldermoor-commitment-closure/trajectories/claude-opus-5/run_1/verifier/reward-details.json`
(judge 48.0 = 12/25, tests 98.45, final 73.22).

## 1. Criteria and probe 5 verdicts

| id | text (short) | weight | target | probe 5 verdict | why Opus passed or failed (trajectory step) |
|---|---|---|---|---|---|
| R1 | builds the closure in a staging dir, publishes after all deliverables complete | 3 | trajectory (instruction following) | PASS | reconcile.py stages and swaps in (created step 26, rerun 71) |
| R2 | program uses the Python standard library alone | 3 | trajectory (instruction following) | PASS | stdlib imports only (step 26) |
| R3 | code quality: no bare/pass handler, no function over 150 lines, no unreachable or unused code | 3 | state_change | FAIL | build_closure about 700 lines, render about 350 lines (final file after step 65) |
| R4 | own input: SETTLED/WITHDRAWN commitment with live edge to an OPEN/DEFERRED blocker, checks blocked_commitments.csv | 3 | trajectory | PASS | synthetic mini extract, settled dependent CMT-040 with holding blocker (steps 56-60) |
| R5 | own input: waiver names a period a settled commitment discharges, checks INERT | 3 | trajectory | PASS | mini extract CAD-001 period 1 settled, waiver INERT (steps 56-60) |
| R6 | runs on an extract placed at a path other than /app/data and compares with the /app/data run | 3 | trajectory | FAIL | ran a synthetic extract at /app/scratch/mini (57) and repeated /app/data runs (38, 66, 76), never a copy of the shipped extract elsewhere compared with /app/out |
| R7 | response lists every file written under /app/out | 1 | final_answer | FAIL | step 79 reply gives closing figures, no file list |
| R8 | states a closing figure no command computed | -5 | trajectory | not fired | figures in step 79 match reconciliation.txt views (28-37) |
| R9 | reports completed after a nonzero last run | -3 | trajectory | not fired | last runs exit 0 (71, 76) |
| R10 | same failing command three times | -1 | trajectory | not fired | no repeated failure |
| R11 | claims a pass with no run after the last edit | -3 | trajectory | not fired | reruns after last edit (66, 71, 76) |
| R12 | own input: one principal's cadences carry more waivers than the allowance, checks LAPSED | 3 | trajectory | FAIL | five waivers on one owned cadence CAD-001 only (56); never several cadences of one principal |
| R13 | own chain of different lengths, recompute wait outside, compare reserve_minutes | 3 | trajectory | FAIL | showed blocked_commitments.csv and month_load_index.csv (58-60), no separate computation of wait |

Positive weight 25; passed R1, R2, R4, R5 = 12; judge 48.0.

## 2. Acts Opus performed in probe 5 (79 steps)

| act | performed? | steps |
|---|---|---|
| survey of documents and feeds | yes | 3-14 |
| aggregate counts over shipped data in scratch scripts | yes | 15-25, 28-37, 46-48 |
| run over /app/data into /app/out, data untouched check | yes | 27, 71, 77-78 |
| determinism: second run, PYTHONHASHSEED, TZ | yes | 38, 54, 66, 68 |
| checks through the program's own functions (`import reconcile as R`) | yes, not separate | 39-43, 55 |
| one-instance witness by grep (CMT-00017 state contest) | yes | 44-45 |
| own synthetic extract built from scratch (edge cases listed in step 56) | yes | 56-60 |
| run from a cwd other than /app/out on inputs at another path | yes, synthetic only | 57 (`cd /app/scratch`, mini), 69 (`cd /tmp`, run6) |
| missing declared input run (only feed_manifest.csv) shows traceback naming the file | yes | 69 |
| recompute of any output figure by a method separate from reconcile.py | no | (reply 79 claims a hand recompute; no step shows it) |
| rerun on an altered copy of the shipped extract, dependent output compared | no | none |
| copy of the shipped extract at another path, result compared with /app/out | no | none |
| principal owning several cadences with waivers over the shared allowance | no | 56 covers one cadence only |
| dependency chain with a shortcut edge (wait differs from hop count) | no | 56 chain 020-021-022 has no shortcut |
| final reply lists the identities by id | no | 79 says "All five identities hold with residual zero" |
| final reply lists delivered files | no | 79 |

Templates Opus skipped: P-c (recompute outside, every artifact type), P-d (altered copy), P-e with the shipped
extract relocated, P-a on the multi-cadence allowance and shortcut-chain branches. Templates it showed: P-a on
the branches in step 56, P-b (44-45), P-h (69).
