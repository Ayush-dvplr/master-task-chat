# PL note: schema-migration-plan-repair, P12 r3 (board a2407ba)

QC v4 findings rechecked against the live kit (harness 71a653b2; only structure_qc.py changed since 3fb1650b): 5 REAL, 0 false positive, 0 unsure.

## False positives
None. Every finding held against the live rule text and the bundle.

## Kept minors
- TS-23 (46 checks, above the 35 warn line). Kept: under the cap of 70 and a warning only. The extra check comes from the TS-13 split; merging checks back would bring TS-13 back. Recorded in QC_DEFENCE.md.

## Unsure
None.

## What changed (short)
- AL-27: seven stated rules (M5 integral float to int, M4 null left alone by a cast, M5 booleans left alone, K4 non-ASCII fingerprint, K13 partner before schema, K15 parse before partner, K16 holder before the schema check) now have a trigger inside existing hidden worlds (NULL, REPLAY and FEED gadgets). No new check. Each one-rule-broken variant now scores 0.66 to 0.74 (before: 0.97 to 1.00).
- TS-13: the fill check grades the fill rule only; the summary check is split into a category check (3) and a partner order check (1). Positive total 136 -> 137 because the kit allows weights 1, 3 and 5 only.
- TS-16 / TS-19: K7 now says none of `state_signature`, `plan_migration` and `execute_plan` changes its arguments, matching the negative guard.
- DS-18: running solve.sh a second time now exits 0 and changes nothing.
- Isolated-check share is 22.6 percent (was 22.1).
