# PL_NOTE - match-replay-desync-audit (board 878a0e4, P12 v3 r3)

## False positives
None. All six QC v3 findings (fe8dec6) rechecked REAL: F1 DS-20, F2 DS-22, F3 JD-7, F4 CL-4, M1 JD-5, W1 TS-23.

## Kept items
- W1 TS-23 / tests_qc A3 "42 checks; cap is 35 (warn)": KEPT, now 46 checks (four damage tests added for F1). Evidence: Ayush 24 Oct 12:50 "no cap" on tests or criteria (floors 10 / 8 only); each check grades its own staged corpus or its own report (STACKING_CHECK.md). Merging checks to reach 35 is the playbook NEVER column.

## For tasker attention (not QC findings)
- L1 (green control) is still an amplifier: its wrong reading costs 0 tests alone (COST_TABLE.md).
- After F4 the trap corpora no longer pay for allowance slips, so each settlement lever now costs the heavy general and mutation tests only (see COST_TABLE.md); this is the effect F4 asked for.

## UNSURE questions
None.

## Lessons for the master
- W1 keeps coming back as a warn once tests grow past 35 | no change: the master set no cap on tests, so the warn is genuine and kept
