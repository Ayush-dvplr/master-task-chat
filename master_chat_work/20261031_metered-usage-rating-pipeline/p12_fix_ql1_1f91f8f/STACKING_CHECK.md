# STACKING_CHECK metered-usage-rating-pipeline (P12 1f91f8f, 31 Oct 2026)

Tool: `master_chat_tasks/tools/stacking_check.py` on BUNDLE after the fix, diffed against the same tool on the backup of the QC copy 145bdba (WORK/ql1_bbc865f36130). Outputs: WORK/ql1/stacking_before.txt, WORK/ql1/stacking_after.txt. The diff is the header line only (folder name).

| item | before (145bdba) | after (1f91f8f) | verdict |
|---|---|---|---|
| checks / positive / negatives | 113 / 422 / -5 | 113 / 422 / -5 | unchanged (no check added, removed or re-weighted) |
| judge criteria / positive | 23 / 50 | 23 / 50 | unchanged, judge.toml not edited |
| G3 hidden or mutated reruns | 79.9% | 79.9% | PASS (>= 30%) |
| AL-28 groups | tool FAIL (UNMATCHED R12 -5, R13 -3, R15 -3) | same | PASS by hand: three different acts, judge.toml unchanged; QC v4 AL-28 PASS |

Test edits this round: per-key cache locks (no grading change), RUN_LIMIT_SEC 15 to 20 and the seven long/long-card check descriptions. Lever stacking unchanged: LV-MU-8 + LV-MU-9 share 160/422 = 37.9% before and after.

Verdict: STACKING PASS.

## Lessons for the master

- A fix that changes only check bodies and descriptions leaves the stacking output byte-identical apart from the header | no change: the diff already shows it
