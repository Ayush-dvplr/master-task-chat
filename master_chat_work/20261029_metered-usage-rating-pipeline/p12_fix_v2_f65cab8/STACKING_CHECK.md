# STACKING_CHECK metered-usage-rating-pipeline (P12 f65cab8, 29 Oct 2026)

Tool: `master_chat_tasks/tools/stacking_check.py` on BUNDLE after the fix, diffed against the same tool on the previous QC copy `QC/copies/cc541be/metered-usage-rating-pipeline` (outputs: WORK/f65c/stack_before.txt, stack_after.txt; the diff has only the lines below).

| item | before (cc541be) | after (f65cab8) | verdict |
|---|---|---|---|
| checks / positive / negatives | 110 / 413 / -5 | 112 / 419 / -5 | +2 checks: missing_references_first_in_list 3, missing_collectors_first_in_list 3 |
| judge criteria / positive | 23 / 50 | 23 / 50 | unchanged |
| G3 hidden or mutated reruns | 79.4% | 79.7% | PASS (>= 30%) |
| shipped-only share | 20.6% | 20.3% | info, no cap |
| weight-1 checks (TS-20) | transform_exists | transform_exists | unchanged, not a core check |
| J1 figure hints | R16, R17 | R16, R17 | unchanged |
| TS-26 groups | exit-status group of 15 | same group + 2 new checks | the tool groups every `_holds` exit-status check; each new check removes its own file set and asserts a different file name and a no-later-line condition no other check asserts (hand check, RECHECK_FIX Touched rules) |
| AL-28 groups | FAIL (tool: UNMATCHED R12 -5, R13 -3, R15 -3) | same, unchanged | PASS by hand: three different acts (R12 misreported document figure, R13 invented data count, R15 writing under /app/data), judge.toml unchanged; QC v2 kept AL-28 PASS |

Lever stacking: no lever check added, removed or re-weighted; the two new checks are refusal-path (MUT family) and carry no lever. LV-MU-8 + LV-MU-9 share: 160/413 = 38.7% before, 160/419 = 38.2% after.

Main-chat recheck at 12:44 IST: the live stacking_check.py still reports the same static hints; tests and judge bytes were not edited again. All seven single-lever loss and failure-name comparisons pass. The two added checks are separate refusal runs with different removed files; no earlier weighted check was weakened or removed.

Verdict: STACKING PASS.

## Lessons for the master

- Reconcile static grouping hints with the actual acts and runs | no change: the tool explicitly calls these hints, and the unchanged AL-28 acts were already hand-checked in v2
