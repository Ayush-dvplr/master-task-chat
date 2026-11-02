# DESIGN_BLIND depot-charge-plan (blind fd98e12)

- Program: `_runs/20261101/depot-charge-plan/blind-20261101T0213-68c4/app/derive_report.py` (copy in proto/blind_fd98e12/), 811 lines, first full write 7 min, shipped run 0.10 s (blind's own), self-check PASS, claims a relaxation lower bound proves levels 1-2 optimal on shipped.
- Method read from the code: min-cost flow (primal-dual, `McFlow`), then `lex_refine(g, positions)` picks the lexicographically greatest optimum over the optimal face in (slot, bus id) order. This is the reference method.
- Scored in Docker (120 s per run, score-fd98e12/logs/score.log ALL_DONE): shipped:1, hidden:1-3, large:1 all EXACT 9/9 documents; seconds 0.32-1.49.

| lever | points lost by WRONG | TIMEOUT | CRASH | first differing record |
|---|---|---|---|---|
| R1 shared feeder | 0% | 0 | 0 | none |
| R2 lexicographic order + tie-break | 0% | 0 | 0 | none |
| R3 depot cabinets | 0% | 0 | 0 | none |

Predicted tests for this program: 100 (every check passes). Judge estimate unchanged (mid 17), so predicted final about 58: fails the G-7 bar.

Verdict: NO CORE. Same outcome as hangar-check-replan: a stated exact optimum with a stated tie ladder is implemented exactly by a careful blind in minutes. Per G-8: one redesign, only after the master's go.
