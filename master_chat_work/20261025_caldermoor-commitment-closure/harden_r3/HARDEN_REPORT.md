# HARDEN_REPORT caldermoor-commitment-closure, harden r3 (da61544, LAST round)

Status: **PILOT_WEAK** (new lever N2 passes its gates; reflex gate 0.4485 > 0.20, no strengthening by choice, reason below). Harness Docker block did not run (permission rule); local tests-only equivalents ran.

## Phase 1 (see DIAGNOSIS.md)
- Phase A GENUINE; primary cause 4 (levers weak by design); cause 3 PARTLY (5f2e150 H7 rewrite named the amount and method).
- Fuzz 300 corpora: probe-3 program 0/300 differ (A, B, C, H7 all REVEALING); probe-2 program 201/300 (all H7).

## What changed (Phase 2)
- New lever N2 "wait" (H6 along a recursive chain + H3 defined term that is no input or output column):
  - Definition, glossary.md:57-59: "**Wait** The wait of a commitment that is not blocked is zero, and the wait of a blocked commitment is one more than the greatest wait among the blockers of the blocking edges leaving it."
  - Use, commitment-protocol.md:189-196 reserve: "thirty minutes times the wait of each commitment with a line in `blocked_commitments.csv` that belongs to that principal and has its commitment day in that month, summed over those commitments". No sentence pairs wait with chain depth; no example.
  - Wrong reading (gating mutant): `chain_depth` (the per-line output column) in place of wait.
- Reference (tests/test_output.py reconcile + compute) and oracle (solution/solve.py `wait_of`) compute wait; oracle = reference on shipped, eval, survivor and wait seeds.
- Hidden fixture `_add_wait_shortcuts` on `WAIT_SEEDS = (30561877, 72914403)`: up to 10 diamond shortcut edges (x->z beside x->y->z) in edges_desk_01.csv, overrides for the parted principal-months; asserts at least `WAIT_MIN_MONTHS = 4` principal-months whose reserve parts the two readings (measured 17 and 34).
- W5: `_SHIPPED_DROP` extended with EDG-000342 and EDG-000454 -> 0 of 155 shipped blocked commitments separate wait from chain depth; shipped `edges_desk_01.csv` regenerated (only change to environment/data). No `_SHIPPED_DATA` embedding exists in this bundle; reward.toml and TRUTH sha recomputed.
- Tests: `wait_reserve_exact` (w3, WAIT_SEEDS[0]) and `wait_reserve_hard` (w5, WAIT_SEEDS[1]) own the month_load_index rows of the parted months (shared `_owned_rows` helper with the survivor tests). P 186 -> 194; reward.toml test_output 0.5/194, judge 0.5/25.
- Judge: R13 w3 "constructs its own input in which a blocked commitment reaches its blockers along chains of different lengths ... recomputes the wait ... compares the reserve_minutes"; solve.sh `check_wait_reserve` prints `check R13 ok`. R1-R12 unchanged.
- Unchanged: A, B, C, H7 rules and the H7 wording, the five negatives, every other test.

## Before / after
| lever | rule | alone before (P=186) | alone after (P=194) | fuzz: mutant differs | probe-3 differs |
|---|---|---|---|---|---|
| A blocked set | dependency-semantics.md:50-51 | 78 (41.9%) | 88 (45.36%) | 300/300 | 0/300 (LEAKED) |
| B periods_waived | cadence-register.md:58-69 | 81 (43.5%) | 94 (48.45%) | 300/300 | 0/300 (LEAKED) |
| C allowance (H6) | cadence-register.md:49-54 | 91 (48.9%) | 99 (51.03%) | 300/300 | 0/300 (LEAKED) |
| H7 second share | commitment-protocol.md:207-210 | 24 (12.9%) | 24 (12.37%) | 201/300 | 0/300 (LEAKED) |
| **N2 wait (new)** | glossary.md:57-59, commitment-protocol.md:190 | n/a | **68 (35.05%), 16 checks** | **299/300 (99.7%)** | 300/300 (program predates rule) |

Shrunk corpus N2-016 (OUT/proto/shrunk_N2.txt): month_load_index ('2032-04','ACT-0036') reserve oracle 90, chain-depth mutant 180 (CMT-01143 wait 1, chain depth 4), probe-3 90; ('2032-06','ACT-0006') 120 / 180 / 90.

## Counts and shares
- Tests 57 (52 positive worth 194, 5 negatives -21; 20 at w5, 31 at w3, 1 at w1). A3 warn 57 > 35 recorded (no cap).
- Judge 13 criteria, +25 / -12, batched.
- Weight shares (stacking_check, hand corrected): hidden-row reruns 52.6%, isolated 46.9%, shipped-only 5.2%, whole-document 1.5%; G3 hidden or mutated >= 30% PASS.
- All-but-one overall at measured rubric 13.64: every row < 70 (N2 39.3). At rubric 90: N2 77.5, A 72.3, B 70.8, C 69.5, H7 88.8 (COST_TABLE.md).

## Gates
- Reflex gate (real tests, P=194): probe-3 program 87/194 = **0.4485**, probe-2 program 87/194 = 0.4485 (both fail 27 checks: every reserve-carrying family, because they charge 30 per blocked line). Above 0.20 -> PILOT WEAK. No strengthening tries: every extra reserve-carrying check raises the N2 mutant above the master's 45% no-cliff ceiling, and these programs differ only because they predate the rule (master note 2: gate on the mutant).
- STACKING_CHECK: PASS (OUT/STACKING_CHECK.md).
- precheck.sh: last line `PRECHECK CLEAN` (kit 976c166611e5; structure/instruction/tests/judge qc exit 0; WARN A3 57 checks).
- xref_check: 10 entries, 0 findings. No `__pycache__` or .pyc.
- validate_bundle.py: 38 passed, 11 failed, same 11 ids as 5f2e150 and 593ecae (pre-existing, advisory for this converted bundle). playground.py: did not run (not in GEN).
- Local tests-only chain in the warm verifier image (WORK/fz/score.py, real tests, shipped extract): oracle x3 1.000/1.000/1.000, owner-only (program 0600) 1.000, nop 0.000, stub 0.000, forgery (shipped-answer replay) 0.1959 (hardcoding negative fired).
- **Harness Docker block: did not run.** Launching the harness was denied by a bash permission rule (`*harbor run*`, action deny). exe_copy.py copies were built and then removed. The master must run oracle x3 / owner-only / nop / stub on the harness before the probe.
- Tree sha (sha256 over sorted relpaths + contents, 65 files): 102f49a944a3. Restore copy of the Phase 2 start: WORK/trap/before_r3/.

## Not run
- Harness oracle/owner/nop/stub/forgery (permission rule); judge (no key); playground static (absent).

## Lessons for the master
- Gate a new lever on its single-lever mutant; an agent program that predates the rule fails every carrier and says nothing about difficulty | template_change: harden template Phase 3 reflex gate should exempt programs older than the new rule
- A recursive defined term placed only in the glossary separates 99.7% of fuzz corpora from the column-reuse reading at 35% cost; whether Opus reads it is the next probe's question | no change: LEVER_RULES 1b H3/H6 already cover it
- The `*harbor run*` deny rule blocks even text containing the phrase, so harden sessions cannot run the Docker block | template_change: harden template Phase 3.4 should name the master as the one running the harness block
