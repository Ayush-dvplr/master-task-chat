# P12 r4 recheck and fix: emberforge-vault-settlement

Board `e8b3dd0`. Live kit HEAD `71a653b23fc2a6bc7ff3d4a8c286ec9a1b6a298e`, identical to v6's kit; its rule IDs and wording did not change. Session rename returned a Codex session ID but `opencode: no match`; no other ID was tried. The current bundle was byte-identical to QC copy `d9fa93e` before edits. All scores in this report are tests-only; judge was inspected but not run.

| ID and v6 finding quote | Label | Live rule quote | Bundle evidence quote | Decision; playbook row | L7 / L3 / L6 effect; compensation | Files changed |
|---|---|---|---|---|---|---|
| DS-20: “Oracle omits two valid-season rules” (v6:26) | REAL | “Any divergence between stated rule and oracle behaviour is a fail” (`02_Data_Solution_QC.md:68`) | I6: “register event ... reinstates” (`rulebook_identity.md:49-53`); H7: “charged at eighty percent” (`rulebook_charge.md:49-54`); old `solve.py:178-179,450` omitted both | FIX, DS-20: roster registration state and H7 charge; old/new shipped output byte-identical for 11 files; an alias event edge also passes | none / none / none; none | `solution/solve.py`, `solution/TRUTH.md`, WORK truth |
| TS-29: “criteria can return fractions instead of bools” (v6:27) | REAL | “Each check returns a bool, never a number, None or a string” (`03_Tests_QC.md:55`) | old `test_output.py:3213` returned `hits / len(WHOLE_SEASONS)` and wrapper `:3295` cast to float | FIX, row NEW (bool return): all seven whole checks require all four seasons; `_passes` returns real bool | harder / harder / harder; none | `tests/test_output.py`, `solution/TRUTH.md` |
| JD-7: “R1-R3 require absent oracle conduct” (v6:28) | REAL | “Every criterion must be satisfied ... by the shipped oracle” (`04_Judge_QC.md:76`) | R1-R3 at `judge.toml:11-48` demand self-built cases; old `solve.sh:4-6` ran only shipped data | FIX, JD-7: stdlib self-check runs three copied temporary seasons after writing `/app/out` | none / none / none; none | `solution/solve.sh`, `solution/TRUTH.md` |
| JD-16: “R6 bundles two constraints” (v6:29) | REAL | “It covers exactly one rule” (`04_Judge_QC.md:93`, part 3) | old R6 at `judge.toml:79` said network connection “or” online lookup; instruction `:13` states separate prohibitions | FIX, JD-15/JD-16: R6 lookup -3; R9 runtime network -1; positive 12, negative magnitude 11 | none / none / none; none | `tests/judge.toml`, `solution/TRUTH.md` |
| AL-2: “Two instruction promises are ungraded” (v6:30) | REAL | “Everything promised is graded” (`05_Alignment_Integrity_QC.md:22`) | instruction `:13` asked for stdlib and final check list; old 20 test registrations and R7 checked neither directly | FIX, AL-2: AST import audit w1; remove ungraded final-message request | none / none / none; none | `instruction.md`, `tests/test_output.py`, `tests/reward.toml`, `solution/TRUTH.md` |
| AL-6: “Judge and reference trajectory disagree” (v6:31) | REAL | “judged criteria agree with the solution and the instruction” (`05_Alignment_Integrity_QC.md:26`) | R1-R3 at `judge.toml:11-48`; old `solve.sh:4-6` supplied no constructed checks | FIX, JD-7: same oracle self-check as above | none / none / none; none | `solution/solve.sh`, `solution/TRUTH.md` |
| AL-27: “Graded fixtures never trigger I6 or H7” (v6:32) | REAL | “which graded input would come out differently if the solver broke exactly this rule?” (`05_Alignment_Integrity_QC.md:27`) | old generator `test_output.py:275-327` had no later register; old `charge_of:728-746` had no relief | FIX, AL-27: every whole season contains a reinstatement and first-patch forge; truth engine applies both; no isolated check | none / none / none; two graded rules harder, no compensation | `tests/test_output.py`, `solution/TRUTH.md`, WORK/wrong |
| Step 11 coverage: “Two requirements still have no checker” (v6:33) | REAL | “every instruction promise graded” (`05_Alignment_Integrity_QC.md:22`); Step 11 mapping in `Final_checklist.md:488` | instruction `:13` and old registrations `test_output.py:3398-3417` | FIX, AL-2: same import audit and request removal as above | none / none / none; none | `instruction.md`, `tests/test_output.py` |
| Step 10: “x3 round is below the kit's x5 sign-off” (v6:36) | REAL warning, KEEP | “Step 10 oracle run ... FIVE times” (`Final_checklist.md:514`) | v6's three recorded rewards were `1.000, 1.000, 1.000`; Ayush's round direction asks x3 | KEEP, row none: x3 in this round; master runs x5 once before sign-off | none / none / none; none | `PL_NOTE.md` |

The matching `QC_DEFENCE.md` entries were D16 (L7), D17 (L3), D18 (L6), D19 (grading), D10 (network) and the P12 r4 disposition. `QC_RULINGS.md` precedents used: emberforge v5 TS-13/TS-26 pass for whole-document views, JD-7 oracle agreement, and AL-2/AL-27 failures in other bundles when promises had no checker or triggering case. No false positive or UNSURE finding remained.

## Deviations from master directions

The master specified a separate script under `solution/` for JD-7. The live `structure_qc.py` S3 rejected `solution/oracle_checks.py` with “solution/ holds only ['TRUTH.md', 'solve.py', 'solve.sh']”. I embedded the same stdlib script as a Python heredoc in `solve.sh`. The delivered `settle_vault.py` and `/app/out` receive only the normal shipped output; the self-check builds copied inputs and temporary outputs. This is the kit-compliant, difficulty-preserving form of the requested oracle fix. Judge script J10 rejects the literal `not` in a negative description, so R6 quotes the full prohibition in an adjacent TOML comment and names the instruction phrase in its description.

The supplied Codex `SCORE.md` reports Harbor reward contribution (`18.75/54 × 0.5 = 0.1736`), whereas harden lp1's adapted score reports normalized test points (`5.25/54 = 0.0972`). Both scales are shown below. The current local before result for the Codex program was `19.75/54`, one point above that earlier note because the local scorer credits the `/app/data` directory test as NOT_RUN; the before and after scores here use the same scorer and its oracle/nop calibration.

## Gates and manual checks

- Four live QC scripts: structure 17/0/0, instruction 5/0/0, tests 37/0/0, judge 19/0/0 (pass/warn/fail); **0 FAIL**.
- XREF: 58 entries, **0 findings**. Tests 21, judge criteria 9. Judge positive magnitude 12 and negatives 11. Reward weights: tests `0.5/55`, judge `0.5/12`.
- DS-20: old QC-copy `solve.py` and new `solve.py` wrote 11 byte-identical files from shipped `environment/data` (aggregate sorted-content SHA prefix `6923b9e9f3b1`). `solve.py` 1163 lines; `solve.sh` 138 lines; `test_output.py` 3495 lines at this gate; final SHA values are in TRUTH.md.
- JD-7/AL-6 embedded oracle probe on copied inputs: `R1 PASS workshop charge 340; H1-H5 figure 340`; `R2 PASS later forge settled True; cap equals first charge 170`; `R3 PASS later salvage credited True; credited total 2`. It exits 0 and never writes `/app/data`.
- AL-27/TS-19: forge_a, forge_b, forge_c, forge_d each have a register after a retire and a first-patch apprentice forge; requisition counts are 16, 25, 32, 48. Generated hidden rulebooks omit the shipped-only “No ... in this season” assertions, and the universal I6/H7 rules stay stated. All within 48.
- TS-29: seven whole checks return `bool` from `hits == len(WHOLE_SEASONS)`; `_passes` returns only `True`/`False`, with exception -> `False`; no `float(result)` remains. Local oracle passed 55/55.
- AL-2/TS-25: missing program -> False, `import numpy` -> False, `import os; from collections import Counter` -> True. The check parses AST and checks every imported top-level module against `sys.stdlib_module_names`.
- STACKING_CHECK: PASS after correcting its static classification of the three structural w1 checks. Rule-isolating weight is 15/55 = 27.3%, whole-document weight 35/55 = 63.6%; no duplicate observable and logic pair; each negative act costs at most 5.
- Docker tests-only final chain: oracle `1.000 / 1.000 / 1.000`, owner-only `1.000`, nop `0.000`; every job had zero errors and `final_docker_chain.log` ends `ALL_DONE`. Final plain copy matches bundle `solve.py`, `solve.sh`, `test_output.py` and `TRUTH.md` byte-for-byte. The final oracle log prints `R1 PASS`, `R2 PASS`, `R3 PASS`. The preliminary chain before the alias edge fix is not counted as final verification. The final chain used live `exe_copy.py` plain and `--owner-only` copies, a warmed verifier image, and serial Harbor jobs without `--delete`.

## Reflex replay

| Program | Before normalized test points | After normalized test points | 0.5-weighted contribution before / after |
|---|---:|---:|---:|
| Codex blind r2, unchanged | 19.75/54 = 0.3657 | 17/55 = 0.3091 | 0.1829 / 0.1545 |
| adapted lp1, unchanged | 5.25/54 = 0.0972 | 5/55 = 0.0909 | 0.0486 / 0.0455 |

The Codex contribution is <= 0.20 and does not rise by 0.05. Its earlier saved 0.1736 was on the prior local setup; the current before/after are directly comparable. Neither unchanged program was edited.

## Trap survival

The L7/L3/L6 after variants were rebased from the harden lp1 versions onto the corrected oracle so each keeps only its one lever misreading. The before variants are the original harden lp1 files. Loss is positive test points out of 54 before or 55 after, with negatives quiet.

| Reading | Before loss of P | After loss of P | Ratio | Separating cases kept | Verdict |
|---|---:|---:|---:|---|---|
| L7 total before operators | 32 | 32 | 1.000 | y | PASS |
| L3 no cap release | 26.75 | 38 | 1.421 | y | PASS |
| L6 all settled in window | 36.75 | 38 | 1.034 | y | PASS |
| no_reinstate | 0 | 35 | n/a | y, new | PASS |
| no_apprentice_relief | 0 | 20 | n/a | y, new | PASS |

No separating hidden case was removed. Final local replay after the alias edge fix kept the same earned points and per-check verdicts. `trap_survival = PASS`; the existing three levers each retain at least 90% of their before loss. The two new mutants each lose at least one whole check.

## QC_RULINGS rows

- TS-29 | seven whole-document checks across four seasons | v6 FAIL | REAL, FIXED | fractional values violated the live bool contract; all-season bools keep the trap.
- TS-19 | composed hidden seasons include I6/H7 within all stated bounds | v6 coverage defect through AL-27 | REAL, FIXED | hidden rulebooks no longer assert the shipped-only absence.
- JD-7 | R1-R3 self-built verification conduct | v6 FAIL | REAL, FIXED | the oracle now prints each check result from temporary seasons.
- JD-15/JD-16 | two stated engagement constraints were joined in R6 | v6 FAIL | REAL, FIXED | R6 and R9 each price one act; negative 11 < positive 12.

## Lessons for the master

- Opus v5 passed an earlier 33-test, 12-criterion tree; LP1 replaced it with 20 tests and eight criteria. Codex v6 found omissions introduced by that new tree, so the QC verdicts are not conflicting reviews of identical bytes.
- The live S3 whitelist forbids extra solution scripts; future JD-7 directions should allow a stdlib heredoc inside solve.sh.
- Record score scale explicitly: the Codex blind note uses a 0.5-weighted reward contribution, while the adapted note uses normalized test points.
- R9 program-network use may still earn the live kit JD-16 signal-quality warning for a judged rule that a deterministic runtime audit could check; the master-directed split preserves it here.
