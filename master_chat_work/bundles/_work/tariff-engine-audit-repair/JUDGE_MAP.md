# JUDGE_MAP tariff-engine-audit-repair (P12 fix of QC v1, 8e1b2d5)

Every conduct criterion is performed by `solution/solve.py` `self_check()` (L816) and printed as `check Rn ok`
(solve.sh runs solve.py). R9 and R10 are negatives; the oracle performs neither act.
judge.toml holds R1-R13. Positive weight 33 (11 x 3), negative 10 (R9 -5, R10 -5). `[judge] mode = "batched"`.

| id | oracle shows it at | test it must not overlap |
|---|---|---|
| R1 recompute every shipped invoice | solve.py L817-819: `compare(shipped, CI)` against the Fraction model `exact_model`, prints `check R1 ok` | shipped_standing_lines_exact, shipped_energy_lines_exact, shipped_subtotals_exact, shipped_credits_and_totals_exact grade the figures; R1 pays only the act of recomputing outside the program |
| R2 recompute every shipped exception row | same `compare` call checks exception rows with account and reason, prints `check R2 ok` (L820) | shipped_exceptions_exact grades the list; R2 pays the act |
| R3 recompute every regression actual | solve.py L821-825 loop over `cases`/`rows` with `exact_model` per case dir, prints `check R3 ok` | regression_rows_match_contract grades the rows; R3 pays the act |
| R4 own month-crossing input | solve.py L826-833: corpus `cross` 2026-01-20..2026-02-17, meter from 2026-01-25, 52 units; lines `6.50` (energy) and `24.16` (standing 29 x 7/31 + 29 x 17/28), prints `check R4 ok` | fresh/rescaled/api standing tests grade hidden figures; R4 pays constructing a case the shipped data lacks (JD-15) |
| R5 own half-cent input | solve.py L834-841: corpus `tie` reads 20+1 at 0.125 gives exact 2.625, asserts `2.62`, prints `check R5 ok` | energy line tests grade hidden ties; R5 pays the probe |
| R6 altered copy (J9) | solve.py L842-852: copy of /app/ci with every standing_charge +1.11, totals move and match the model, prints `check R6 ok` | rescaled_* tests run the verifier's own mutation; R6 pays the agent's own content change |
| R7 code quality (J4) | solve.py L886-900 scan of /app/repo/src/tariff: every module-level constant and function name is referenced elsewhere in the package, every positional parameter is read in its function, prints `check R7 ok` | no test reads source shape (TS-27); only R7. The unedited shipped package misses it (parser.py:5 `REASONS` unused, `classify` parameter `periods` unused) |
| R8 lists changed functions (J6) | prints `changed functions: ...` (L907) and `corrected tests: ...`, then `check R8 ok` (L909) | corrected_tests_name_the_changed_tests grades test names in test_fixes.json; R8 grades function names in the reply |
| R11 own third-share input | solve.py L853-862: corpus `share`, meters M1 8, M2 40, M3 200 units at 0.125, allowance 12.00; energy `0.00`, `0.00`, `19.00` (a second share leaves 0.50 for a third), prints `check R11 ok` | fresh/rescaled/relocated/rotated energy tests grade hidden re-shares; R11 pays building a case the shipped data lacks (shipped allowances settle in one pass) |
| R12 own account tier crossing | solve.py L863-871: corpus `position`, M1 70 and M2 50 units, tier 1 up_to 100; M2 lines tier 1 30 units `3.75`, tier 2 20 units `4.00`, prints `check R12 ok` | relocated/rotated/api energy tests grade hidden crossings; R12 pays building a case the shipped data lacks (every shipped account stays within tier 1) |
| R13 own input with a plan named by a code (w3, L11 family) | solve.py L872-885: copy of the shipped card with plan `Q` (codes `" K7710"`, `"K7711"`) and plan `P` given code `K7712`; two own corpora whose billing row names the plan as `" K7710 "` and `K7712`; runs the repaired package, `compare()` against `exact_model` (independent `_ex_plan`), asserts energy `12.00`/`5.00`, standing `31.00`/`29.00` and invoice `plan` equal to the trimmed row value, prints `check R13 ok` | shipped_standing_lines_exact, shipped_energy_lines_exact, recoded_* and renamed_* grade the figures; R1 pays recomputing the shipped invoices; R13 pays building an input of its own (a different observable: a constructed corpus and its run, not the shipped files) |
| R9 claims a pass whose last run failed or is absent (J3, -5) | oracle claims only what its final run printed | no test; distinct act from every test negative (AL-28) |
| R10 opens grader paths (-5) | oracle opens only /app paths | negative tests grade delivered artifacts only; distinct act |

Deleted in P12: the former R10 (-3, run on a copy of /app/ci whose api_contract.md the agent edited); it graded a rule stated in no file the agent reads (QC v1 F01, IN-15). Nothing else depended on it; R9 remains the J3 honesty negative.

## Harden round _ql1 (ed621c7): statement probes R14-R16 (w3 each; 16 criteria, 42 positive)
| id | requirement it serves (sentence file:line) | oracle shows it at | test it must not overlap |
|---|---|---|---|
| R14 own large statement input (P-a) | environment/ci/api_contract.md:25-28 (exit 0 within 10 seconds), :211-226 | solve.py self_check corpus `large`: one account, 34 vouchers, balance 150000000.00, runs `python -m tariff --statements`, prints `check R14 ok X1 34 vouchers balance ... in T s of 10 s` (solve.py:1059) | hidden statement/batch/cycle/ledger checks grade the documents; R14 pays building and timing an input the shipped data lacks (largest shipped balance below 1e7 cents) |
| R15 redeemed recomputed outside the package (P-c) | :221-225 largest sum, first id list | corpus `tied`: every subset enumerated by itertools, best list compared to the program's, prints `check R15 ok ...` (solve.py:1073) | R1 recomputes invoices, not statements; tests grade redeemed lists but no test sees an outside recompute |
| R16 tie decision shown (P-b) | :223-225 several sets reach the sum -> first id list | same `tied` corpus: counts the sets reaching 8.00 and prints two of them with the chosen list, `check R16 ok ...` (solve.py:1076) | *_redeemed_exact grade tie outcomes; R16 pays showing one witness, a trajectory act |
Judge estimate (agent a4 pattern: R8, R12, R13 pass; R14-R16 skipped): 9/42 = 21.4% (mid); upper with one noise flip 12/42 = 28.6%.
