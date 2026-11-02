# PL note: match-replay-desync-audit, P12 v3 r5 (57e415c)

## False positives
None.

## Kept items (tasker approval)
- W1 A3 / TS-23, 46 deterministic checks (cap 35 is a warn, `03_Tests_QC.md:62`, `tests_qc.py:48`). Kept: no cap on checks (Ayush, 24 Oct 12:50; floors only, 10 tests / 8 criteria). Each of the 46 reads a different hidden input or observable (STACKING_CHECK TS-26 groups checked by hand); merging any would merge checks to hit a count. Precedent district-heat v4:47 (QC_RULINGS TS-23 row).

## QC verdict note
- CL-4 verdicts differed between v4 and v5 on unchanged code: v4 ran CL-4 and passed the same `_plant_divergence` design (latest-entry reading detectable through CTRL-J calibration); v5 failed it (v5.md:355). v5 treated as the rule and fixed.

## Deviation for approval
- The master's fix (plant divergence only in density / tiebreak / shipped sets) was not enough on its own: 50/50 natural corpora part on cancellation order; with no planting at all the latest-entry reading scored 6/172. Added named repair `_settle_one_order` so other sets are order-neutral; latest-entry reading now 157/172 (RECHECK_FIX.md, Deviations).

## UNSURE questions
None.
