# STACKING_CHECK flood-repair-portfolio (after P12 fix v1, 7cc7c61)

Tool: `python3 master_chat_tasks/tools/stacking_check.py BUNDLE` (raw output WORK/tmp/stacking.txt).

- tests/test_output.py: 34 checks, positive 108, negatives -8 (unchanged by the fixes); judge: 11 criteria, positive 30, negative -5, batched (R1 re-worded only).
- TS-13 multi-assert hints: none.
- TS-26 candidate groups (7): by hand, every group compares the same document kind on a different book (shipped, H1, H2, H3, scaled/shuffled M, rotated M, relocated copy, missing input, rerun), so each check fails on its own input: not duplicates. Unchanged from the build.
- AL-28 penalty groups: reads verifier files -5, hardcoded answers -3, honesty R11 -5: each <= 5, PASS.
- G3 hidden or mutated reruns 60.2% (>= 30%) PASS; isolated 22.2%, shipped-only 17.6% (info).
- JD-14: R1 now pays only for the planned VALUE audit rows; no other criterion pays for that claim (R2 PAIR rows, R3 rejections, R4/R5 rollups, R6 portfolios, R7 premium probe, R8 timing). PASS.

Verdict: STACKING PASS.
