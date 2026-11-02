# PL_NOTE - match-replay-desync-audit (board 0bf6688, P12 v3 r2)

## False positives
None. All five QC v2 findings (fba1605) rechecked REAL.

## Kept items
- W1 TS-23 / tests_qc A3 "42 checks; cap is 35 (warn)": KEPT. Evidence: tests_qc.py exit 0 with this one warn; Ayush 24 Oct 12:50 "no cap" on tests or criteria (floors 10 / 8 only); decision 94 approved 42. Each of the 42 checks grades a distinct output (12 trap inverses each run `_trap_only` on one transform bit, 13 general checks each run their own `_mutant` tweak; STACKING_CHECK.md). Merging checks to reach 35 is the playbook NEVER column. Tasker approval asked.

## For tasker attention (not QC findings)
- G10 cost table fails on L1 (green control): its wrong reading costs 0 tests alone, because it only hides an L3 or L4 slip. L3 and L4 each cost 87.5% of P and their all-but-one rows sit at 51 to 55 overall. Not changed this round (no new levers).
- task.toml:7 description still reads "turn based" (not in the W3 sweep scope; not agent-graded text).

## UNSURE questions
None.
