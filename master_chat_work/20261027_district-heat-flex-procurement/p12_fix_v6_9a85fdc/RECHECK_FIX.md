# P12 recheck and fix of QC v6: district-heat-flex-procurement (board 9a85fdc)

- Bundle: master_chat_work/bundles/district-heat-flex-procurement (edited); WORK: bundles/_work/district-heat-flex-procurement
- QC report: QC/reports/district-heat-flex-procurement/v6.md (kit 5574d77e). Live kit HEAD `5574d77eb9f22c207ba05fd8f9ac31d42ba45271`: same commit, no rule changed.
- Session rename: `name_session.py 9a85fdc` printed `codex: no match` / `opencode: ['ses_e8191d5f2ffeuXwT5oN9qkhwFa']`. 9a85fdc itself did not appear in that output. Not retried.
- Noise check (Always 13) against the v5 copy 2fd95f2: every line a finding cites has changed since v5. TRUTH.md was rewritten, judge R1-R4 were reworded, solve.sh gained its self-check stage, and wide_feasible did not exist in v5. So no finding is variance and the noise-keep count is 0.

## Findings
| ID | label | rule (live kit) | evidence | decision | playbook row | effect per lever | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| F01 DS-27 | REAL | 02_Data_Solution_QC.md:80 "TRUTH.md describes the task, not how the task was made ... What does not belong is any narrative of the production process ... a changelog of what the author tried first" | old TRUTH.md:15 `Focal items (r4 redesign):`; :52 `(focal, wave 1)`; :119-126 "pre-wave oracle ... probe-9 harness program ... saved blind program" | FIX. Now TRUTH.md:15 `Focal items:`, :52 `7. (focal) Exact portfolio`, :120-124 "in points of 205: the oracle scores 205. An exact portfolio search that visits every portfolio scores 173 ... A cheapest-first pick scores 66. One wrong reading alone ...: 160, 150, 147". Regenerated last by WORK/w1_truth.py (sha256 lines by script) | DS-22 / DS-27 (rewrite TRUTH, by script) | P-3 none, M1 none, M2 none, M3 none, P-5 none | none | solution/TRUTH.md (via WORK/TRUTH_w1_body.md) |
| F02 JD-7 (+AL-6) | REAL | 04_Judge_QC.md:76 "Every criterion must be satisfied ... by the shipped oracle ... Check EVERY criterion against solve.sh / solve.py line by line"; 05:37 AL-6 | judge R1-R4 "The agent constructs its own extract ..." while old solve.sh:5-229 only ran on /app/data | FIX by an oracle stage; R1-R4 kept. solve.sh:230-380 own-extract stage writes 4 schema extracts in a temp dir (drawn allowance; two events sharing a site with +00:00 / +01:00 starts; override + uplift + adder above cap; half-cent interval), runs /app/out/derive_report.py on each, prints `own extract, <what>: program X, by hand Y, agrees` (L332). The stage ends with `|| true`, so it exits 0 either way. Docker run: all 5 comparisons agree (1, ['OWN-0202'], 40, 1, 1), 3.1 s. The old self-check prints `check R9/R10/R11 ok` became plain descriptions with no criterion ids (DS-17) | JD-7 (fix the oracle, never loosen) | P-5 kept (probes R1-R4, R8-R10 unchanged); tests none | none | solution/solve.sh, TRUTH.md, WORK/JUDGE_MAP.md |
| F03 JD-15 | REAL (minor) | 04_Judge_QC.md:92 (outcome traces to contract; conduct holds for every competent route) | old judge.toml:66 R5 "keeps the walk ... in one named function, separate from ..." w3 (:68) | FIX: R5 deleted. Old R6-R12 renumbered R5-R11, because judge_qc.py:17/245 requires sequential ids. reward.toml judge 0.018518518518518517 -> 0.020833333333333332 (0.5/24). R11 (old R12, J4) still judges code quality, so JD-18 holds | JD-15 (remove preference no lever uses) | P-5: one w3 preference removed, 7 probes kept; tests none | none | tests/judge.toml, tests/reward.toml |
| F04 TS-23 | REAL warn, KEEP | 03_Tests_QC.md:62 "at least 10 checks (fail), at most 35 (warn)" | tests_qc "WARN [A3] 58 checks; cap is 35 (warn)"; tests/test_output.py registrations at the end of the file | KEEP with the count of 58. Nothing merged: Ayush decision 3 option A, and the 24 Oct "no cap" ruling. The stacking review found no true duplicate: shipped and `_hard` pairs read different extracts, and wide_0 and wide_1 read different seeds (QC v6 itself passed TS-26, v6.md:300) | TS-23 | all none | none | none |
| F05 TS-25 / CL-2 | REAL warn | 03_Tests_QC.md:52 "Positive tests grade earned work, never an absence" | old wide_feasible passed when every `selected_offer_ids` was empty | FIX: `for row, ref in zip(mine_[region], want[region])` plus `if ref["selected_offer_ids"] and not ids: return False, ...` (tests/test_output.py:2119, :2123-2124). The docstring and both criterion descriptions now say non-empty. Weights unchanged (w3 x2). G7 byte diff (WORK/p12/G7_tests_diff.txt) shows only these hunks. Measured on an empty-portfolio program (oracle with every selection zeroed): 181/205 before, 175/205 after (it now fails wide_0/1_portfolios_feasible) | TS-25 (assert earned output) | P-3 harder (an empty portfolio loses 6 more points); others none | none | tests/test_output.py (via WORK/test_output.src.py + embed.py) |

Counts: REAL 5 (2 fails, 1 minor, 2 warns), FALSE_POSITIVE 0, UNSURE 0. Fixed 4, kept 1 (TS-23), paused none.

## Deviations from master directions
- F05: besides the assert, the hunk also updates the wide_feasible docstring and the two criterion descriptions, so that each description says what the check grades (TS-24/TS-17 wording). These lines sit inside the named check and are its only text. Weights and every other byte in tests/ are unchanged.
- F02: the existing self-check stage's three prints lost their old R9/R10/R11 ids. After the renumber those ids pointed at the wrong criteria, and the direction asks for no R numbers. The stage's logic is unchanged.

## Gate results
- precheck.sh: last line `PRECHECK CLEAN` (only WARN A3 58 checks; tests 58, criteria 11).
- xref_check: `48 entries, 0 findings` (before and after; no value in XREF changed).
- stacking_check: OUT/STACKING_CHECK.md. Its only differences from the v6 copy are the judge count (12 -> 11, positive 27 -> 24) and honesty R8 -> R7. AL-28 PASS, G3 hidden share 68.8% PASS. The 24 TS-26 hint groups were checked by hand: pairs differ by extract or seed, not duplicates (as QC v6 TS-26 PASS).
- Docker block (live kit exe_copy.py copies, plain and --owner-only; chain /tmp/opencode-logs/dh-p12-9a85fdc/dchain-20261028T025357-c1af, ALL_DONE 02:56): oracle 1.0 / 1.0 / 1.0, owner-only 1.0, nop 0.0. Tests-only.
- Tasks_INPUT: 5 changed files copied with `cp -p`; `diff -rq` BUNDLE vs Tasks_INPUT copy is empty.

## Touched rules
| id | touched how | rules re-checked | verdict |
|---|---|---|---|
| wide_0_portfolios_feasible | assert added, description reworded, w3 kept | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4 | PASS. One property: the reported portfolio is admissible and is non-empty where the optimum is (test_output.py:2119-2124). Honest-untrippable: the oracle passes, 205/205. Fails on absence: the empty program fails it. w3 matches its sibling, so no inversion (TS-20). It does not double-pay with wide_0_selection_match, which compares exact ids (TS-26). CL-2: the forgery price can only fall, because a hand-written empty or fake file now fails it too. CL-4 exemption unchanged (instruction.md "graded whole") |
| wide_1_portfolios_feasible | same | same | PASS (same lines, seed 1) |
| judge R5 (old, allowance-walk function) | deleted | JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, AL-28 | PASS. Gone; ids made sequential; judge_qc exit 0 |
| judge R5-R11 (old R6-R12) | renumbered only (id and name prefix) | JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, AL-28 | PASS. Wording, weights and labels unchanged; judge_qc exit 0. AL-28: R7 -5 is the only judged negative, on a distinct act (stacking table PASS) |
| judge R1-R4 | not edited; oracle evidence added | JD-6, JD-7, JD-15, CL-2 | PASS. JD-7: solve.sh:230-380 prints each act (WORK/JUDGE_MAP.md). JD-6: decidable from the trajectory. JD-15: odds-raising w3, as QC v6 ruled (v6.md:334 failed only R5). CL-2: an agent that changes nothing builds no extract, so it earns nothing |

## Vacuity probe
- Tests: the shipped environment holds no program (TRUTH.md: "There is no broken program to repair"; environment/ has only Dockerfile and data/). An agent that changes nothing leaves /app/out empty, which is exactly the nop run: measured 0.0 in the Docker block, so no positive check passes vacuously. The format checks require all 9 files, and every value check reruns /app/out/derive_report.py.
- Judge, read for an agent that changed nothing: R1-R4 need its own extract runs (none); R5 needs a derive_report.py (none); R6 needs a final run (none); R8-R10 need recomputations (none); R11 needs a derive_report.py (none). Nothing is earned. The negative R7 does not fire without a claim.
- Verdict: PASS.

## Side effects
| FIX id | ids re-checked (FIX_SIDE_EFFECTS + Always 14) | result |
|---|---|---|
| F01 DS-27 | DS-22 (TRUTH matches code, sha256 by script), AL-18 (figures current) | PASS: TRUTH sha256 equal to solve.sh 9c93b668... and solve.py d5ce561b...; precheck DS-22 clean; the scores quoted in TRUTH are this session's measured ones (oracle 205, plain 173, greedy 66, 160/150/147) |
| F02 JD-7 | JD-15 (produced once in history), DS-17 (oracle never reads tests/), JD-6, CL-2 | PASS: R1-R4 unchanged and conduct w3; solve.sh reads only /app/data and /app/out; no R ids in output |
| F03 JD-15 | JD-9 (produced once in history), JD-18, TS-10 reward weight | PASS: 7 trajectory probes plus J4 remain; R11 code quality; judge 0.5/24 matches the positive 24 |
| F05 TS-25 | TS-13, TS-14, TS-26, TS-24 wording, CL-2 | PASS (see Touched rules) |
New findings caused by the fixes: 0.

## Noise keeps
None. Every cited line changed since QC v5 (copy 2fd95f2).

## Trap survival
Measured in Docker (env image, 4 GB, 2 CPU, grade.py with the stub rewardkit, the real embedded tests). Before = the pre-fix tests (WORK/p12/before), after = the fixed bundle tests. Raw output: WORK/p12/dout/TRAP_before.txt and TRAP_after.txt.
| lever | single wrong-reading program | before loss (of 205) | after loss | ratio | separating cases kept | verdict |
|---|---|---|---|---|---|---|
| P-3 wide exact optimum | plain exact search (visits every portfolio) | 32 (TIMEOUT) | 32 | 1.00 | y | PASS |
| P-3 | blind ef9234c / d62d21c / 7dd7290 | 32 / 32 / 32 | 32 / 32 / 32 | 1.00 | y | PASS |
| P-3 | empty portfolio (oracle with selections zeroed) | 24 | 30 | 1.25 | y | harder |
| M1 grants re-share | REENTRY | 45 | 45 | 1.00 | y | PASS |
| M2 draws_from chain | CHAIN1 | 55 | 55 | 1.00 | y | PASS |
| M3 credited relief | RELIEF | 58 | 58 | 1.00 | y | PASS |
| other | greedy cheapest-first | 139 | 139 | 1.00 | y | PASS |
No check and no hidden input was removed. All 8 wide checks and both wide seeds are unchanged.

## QC_RULINGS rows
- JD-7 | own-extract conduct criteria R1-R4 (w3) shown by a solve.sh own-extract stage | QC v6 FAIL (oracle never builds an extract) | REAL | fixed by an oracle stage that prints each act (QL Q1 "phrase your rubric so it passes oracle")
- JD-15 | named allowance-walk function criterion R5 w3 | QC v6 MINOR (layout preference) | REAL | deleted; AVOID code-layout criteria that no rule states
- TS-25 (not on the list; noted for the master) | wide feasibility check paid an empty portfolio | QC v6 WARN | REAL | assert non-empty where the optimum is non-empty

## Lessons for the master
- A probe criterion added at harden time needs its oracle stage in the same round (JD-7 v6) | template_change: harden prompt step "judge" add "every new trajectory criterion gets a solve.sh stage printing the act"
- Feasibility-style positives on hidden corpora must assert non-empty output where the reference is non-empty (TS-25 v6) | no change: NEW-CHECK hygiene already lists TS-25; add to the harden checklist example
- Self-check prints that carry criterion ids go stale on any renumber | template_change: LEVER_RULES J2 "prints check <id> ok" -> plain description lines
