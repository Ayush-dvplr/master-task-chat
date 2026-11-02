# PL note: cohort-retention-reconciliation (P12 r2, board f6164ef)

## False positives
None. All six QC v3 findings are real.

## Kept minors
- TS-13 (cohorts check inside the format and rerun checks): kept. Taking it out would give 6 of 71 points to programs that get no cohort right, which makes the task easier. The gate is written down in TRUTH.md. The reflex program scores the same with or without it.

## Fixed minors
- TS-29 (checks return a share, not a bool): the share is now written down in TRUTH.md as a deliberate choice. No check can raise.

## Open questions
None.

## Lessons for the master
- Minor findings that only ask for a written note are cheaper to fix than to defend.
