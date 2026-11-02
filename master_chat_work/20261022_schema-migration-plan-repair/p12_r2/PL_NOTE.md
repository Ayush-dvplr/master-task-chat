# PL note: schema-migration-plan-repair, P12 r2 (board e4d972f)

QC v3 findings rechecked against the live kit 3fb1650b: 9 REAL, 0 false positive, 0 unsure.

## False positives
None. Every finding held against the live rule text and the bundle.

## Kept minors
- TS-23 (45 checks, above the 35 warn line). Kept: 45 is under the cap of 70 and the gate counts it as a warning only. The 19 hidden worlds each carry a different lever set, so folding them would drop lever coverage. Recorded in QC_DEFENCE.md.

## Unsure
None.

## What changed (short)
- M5 float cast now says surrounding spaces are ignored (IN-16); K17 says `completed_steps` is 0 when execution never started (CL-5).
- The argument guard is now a negative check, `negative_entry_points_mutate_arguments` (-1) (TS-25).
- Judge R7 is now a negative criterion for leftover debug prints or commented-out code (-3); the dead-function clause is gone (JD-2, JD-15, JD-5).
- `changed_functions` must list every changed function in its area (AL-2).
- A cast on a boolean is now exercised and must leave it unchanged (AL-27).
- The oracle copies its repaired tree back over /app/repo (DS-15).
