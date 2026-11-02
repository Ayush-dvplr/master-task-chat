# STACKING_CHECK metered-usage-rating-pipeline (P12 d21576c, 29 Oct 2026)

Tool: `master_chat_tasks/tools/stacking_check.py` on BUNDLE after the fix, diffed against the same tool on the previous QC copy `QC/copies/92ee28b/metered-usage-rating-pipeline` (outputs: WORK/d215/stack_before.txt, WORK/d215/stacking.txt; the diff has only the lines below).

| item | before (92ee28b) | after (d21576c) | verdict |
|---|---|---|---|
| checks / positive / negatives | 112 / 419 / -5 | 113 / 422 / -5 | +1 check: missing_adjacent_pairs_in_list_order 3 |
| judge criteria / positive | 23 / 50 | 23 / 50 | unchanged |
| hidden_rows checks | 321 pts | 324 pts (76.8%) | new check runs hidden seeded months |
| G3 hidden or mutated reruns | 79.7% | 79.9% | PASS (>= 30%) |
| shipped-only share | 20.3% | 20.1% | info, no cap |
| TS-26 groups | exit-status group (15 + 2) | same group + 1 new check | the tool groups every `_holds` exit-status check; the new check removes ten different file pairs and asserts the earlier file of each pair, which no other check asserts (QC v3 al27 order mutant fails only this check: WORK/d215/trap_d215.json) |
| AL-28 groups | tool FAIL (UNMATCHED R12 -5, R13 -3, R15 -3) | same, unchanged | PASS by hand: three different acts, judge.toml unchanged; QC v3.md:282 AL-28 PASS |

Lever stacking: no lever check added, removed or re-weighted; the new check is refusal-path (MUT family) and carries no lever. LV-MU-8 + LV-MU-9 share: 160/419 = 38.2% before, 160/422 = 37.9% after.

Verdict: STACKING PASS.

## Lessons for the master

- The TS-26 group hint grows with every refusal check; reading the mutant failure sets settles it | no change: the tool calls these hints
