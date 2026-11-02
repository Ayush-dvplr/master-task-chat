# PL note: cohort-retention-reconciliation (P12 r3, board cac63fd)

## False positives (rebuttals)

None. All five v4 findings are real.

## Kept minors

- TS-13 (kept): the cohorts check inside the format and rerun tests stops a program with wrong cohorts from getting 6 of 71 points for formatting alone. Splitting it would make the task easier for every wrong reading.
- TS-29 (kept): the hidden checks give a third of the points per hidden study. A yes/no check per study would add 18 checks (24 to 42), and one yes/no for all three changes the grading. TRUTH.md states the deviation; QC lists it as minor because no check can raise.

## UNSURE questions

- AL-27 (e), schema.md:15-16 "A rate whose denominator would be zero is written as `\"0\"`." Only the weighted share can have a zero denominator, and only in a study with no weighted revenue at all. Making such a hidden study removes the weighted-revenue grading from it. Question: may we leave this sentence ungraded, or should we delete it from schema.md (our preference)?

## Lessons for the master

- Ask the PL about untriggerable sentences before writing them into a schema, not after QC.
- Minors open for two rounds need a written keep reason in QC_DEFENCE so QC can close them.
