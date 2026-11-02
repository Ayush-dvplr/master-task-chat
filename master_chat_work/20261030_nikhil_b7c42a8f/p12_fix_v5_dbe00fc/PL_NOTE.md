# PL note: b7c42a8f-6d19-4e35-9f82-5a3c1d7e8042 (fix dbe00fc, after QC v5)

Both QC v5 findings were real, and both are fixed.

- AL-27 (fail), fixed. The hidden extracts now settle the other reading. Extract A's adjustment log settles `excess_only` and extract B's treasury log settles `flat_10y`. The shipped data is unchanged and still settles `pro_rata` and `duration_matched`. A script checked each log, and each one fits exactly one reading. A program that hard-codes `pro_rata` now scores 49/64 on tests. A program that hard-codes `duration_matched` scores 61/64.
- JD-5 (minor), fixed. R25 and R34 each grade one reading now, and the new R36 and R37 grade the other one. Each weighs 1. The judge positive total goes from 66 to 68, and the judge weight in reward.toml is now 0.5/68 = 0.007352941176470588.

## False positives (rebuttals)
None this round.

## Kept minors and warns
- KEPT 1-6 from earlier rounds are unchanged (see KEPT.md).
- New warn kept: the judge file now has 37 criteria, and the kit warns above 35 (04_Judge_QC.md:116 JD-S12). The QC-directed JD-5 split caused this. None of the criteria is a true duplicate. Merging any pair back would re-open JD-5. Playbook row TS-23 says to keep the warn with the count. One side effect: precheck.sh only lets X1/A3/S6 warns through, so its last line reads `PRECHECK: 1 finding(s)` (this G3 warn) instead of `PRECHECK CLEAN`.

## UNSURE questions
None.
