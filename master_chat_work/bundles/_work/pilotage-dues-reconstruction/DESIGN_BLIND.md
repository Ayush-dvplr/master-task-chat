# DESIGN_BLIND 49087b0 pilotage-dues-reconstruction (blind 5456c27)

Program: proto/blind/derive_report.py (sha256 10de7239dbf9a9faa752737b35440f84faa5c50e71181d03d122770c1a6ec861).
Run: Docker 4g/2cpu, alarm 600, `_runs/20261031/pilotage-dues-reconstruction/score-5456c27/logs/score.log` (ALL_DONE), scored by proto3/score3.py against proto3/solve3.py ref.

| corpus | stations exact | seconds | first differing record |
|---|---|---|---|
| sample (482617) | 4/4 | 0.89 | none |
| h1101 | 4/4 | 0.87 | none |
| h1103 | 4/4 | 1.01 | none |
| h1105 | 4/4 | 1.07 | none |

Rules wrong: 0 of 3 sharp rules (conventions, unique tariff, notice split) and 0 plain rules on these corpora.
Minutes to first full write: about 4 (blind report). Its judge estimate was not reported; its trajectory shows a shipped-only self-check (counts reconcile), no edge-input, altered-copy or missing-file run.
Search: full stated domain, decomposed (marks range(1,11) x range(1,31) x base x 180 tariffs, then calendar x Monday, minute arcs).
Blind exact on sample AND all 3 seeds -> redesign (prompt Phase 0b step 4); per master 13:05 verdict rule: NO CORE, stop.

## Lessons for the master
- A stated finite convention domain is enumerated on the first write even when only implied by the unit | no change: needs a redesign decision from Ayush
