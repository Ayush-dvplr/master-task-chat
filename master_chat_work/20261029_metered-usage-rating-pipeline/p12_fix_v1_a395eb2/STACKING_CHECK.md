# STACKING_CHECK metered-usage-rating-pipeline (P12 a395eb2, 29 Oct 2026)

Tool: `master_chat_tasks/tools/stacking_check.py` on BUNDLE after the fixes, diffed against the same tool on the previous QC copy `QC/copies/ac12c0b/metered-usage-rating-pipeline`.

| item | before (ac12c0b) | after (a395eb2) | verdict |
|---|---|---|---|
| checks / positive / negatives | 108 / 407 / -5 | 110 / 413 / -5 | +2 checks: missing_input_first_named 3, missing_reference_file 3 |
| judge criteria / positive | 22 / 49 | 23 / 50 | R6 reworded to one act, R23 added (w1) |
| G3 hidden or mutated reruns | 79.1% | 79.4% | PASS (>= 30%) |
| shipped-only share | 20.9% | 20.6% | info, no cap |
| weight-1 checks (TS-20) | transform_exists | transform_exists | unchanged, not a core check |
| J1 figure hints | R6, R16, R17 | R16, R17 | R6 no longer quotes "150 lines"; R16/R17 are final-reply figures the oracle prints (kept as before) |
| TS-26 groups | finishes group | finishes group + 2 new missing checks | the tool groups every `_holds` exit-status check; each runs its own input set and asserts a different file name (hand check, see RECHECK_FIX Touched rules) |
| AL-28 groups | FAIL (tool: UNMATCHED R12 -5, R13 -3, R15 -3) | same, unchanged | PASS by hand: three different acts (R12 misreported document figure, R13 invented data count, R15 writing under /app/data), judge.toml lines unchanged; QC v1.md:345 "AL-28 ✅ negatives are distinct acts ... no act can trip two" |

Lever stacking: no lever check added, removed or re-weighted; the two new checks are refusal-path (MUT family) and carry no lever. LV-MU-8 + LV-MU-9 share: 160/407 = 39.3% before, 160/413 = 38.7% after.

## Lessons for the master
- stacking_check AL-28 groups any three unmatched judge negatives as one act; a hand PASS with the QC line is needed every round | no change: tool is master-owned, verdict is a hint
