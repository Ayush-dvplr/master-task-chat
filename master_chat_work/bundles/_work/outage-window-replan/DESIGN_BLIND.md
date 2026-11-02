# DESIGN_BLIND (P13 blind 7a33fe5, run 30 Oct 04:30-04:34 IST)

Blind program: copy at `WORK/proto/blind/derive_report.py` (778 lines; source
`/tmp/blind/outage-window-replan-20261030T042403-ad05/app/derive_report.py`).
Run in Docker: `docker run --rm --init --memory 4g --cpus 2 python:3.12-slim`, `perl -e 'alarm 300'`
(the stated per-run limit). Log `WORK/proto/logs/blind1.log` (ALL_DONE). Outputs `WORK/proto/blind_out/<c>`,
diffed with `WORK/proto/compare.py` against `WORK/proto/ref_out/<c>`.

| corpus | rc | seconds | documents exact | first differing record |
|---|---|---|---|---|
| shipped sample (seed 594183) | 0 | 1 | 9/9 | none |
| hidden seed 1 | 0 | 2 | 9/9 | none |
| hidden seed 2 | 0 | 90 | 9/9 | none |
| hidden seed 3 | 0 | 28 | 9/9 | none |

Rules wrong: 0 of 3 sharp rules (S-1, S-2, S-3) and 0 noise rules. Lever points kept: 100%.
Minutes to first full write: 3 (its report: 04:24:24 start, 04:27:12 first run).
Judge estimate (its report): one shipped self-check run, cross-totals and one missing-file run;
no witness instance, no altered or relocated rerun, so about P-h only (probe mid near the design 25%).

## Why it is exact
- Components: it unions two requests only when, on some day, the requests whose windows touch it
  need more crews than the lane capacity (plus incompatible pairs with overlapping windows and
  every precedence pair). This contention-aware split cuts the hidden lanes into small pieces;
  my kill-test `comp_id` unioned on any window overlap, got components of 16-22, and was capped.
- Per component: DFS in ascending asset_id order, starts ascending, deferral last, objective value
  = risk and moved combined, exact remaining lower bound, strict prune after the first solution.
  The first optimum reached in that order is the lex-min start list, so S-3 holds; S-2 holds
  because moved is inside the value. No wall-clock guard, so no capped incumbent.
- Worst case 90 s on seed 2, inside the stated 300 s; it would need about 3x larger lanes to time
  out, and G-6 forbids raising scale to force a timeout.

## Verdict
The plain first-write program (3 minutes) is exact and fast on hidden scale: the P-3 core does not
hold against a careful Opus. Master rule (04:30): blind keeps > 50% of lever points -> stop PAUSED;
no data tuning against it. IDEA gate G-6 reading: NO CORE.
