# KILL_TEST 49087b0 pilotage-dues-reconstruction (L-CONV redesign)

Run: 31 Oct 11:59 IST. `dockfree.py --need-mb 4096 --cpus 2` -> START=yes FREE_MB=12898.
`docker run --rm --memory 4g --cpus 2 python:3.12-slim`, each solver under `perl -e 'alarm 600; exec @ARGV'`.
Scratch `_runs/20261031/pilotage-dues-reconstruction/kill-20261031T1200/` (scratch/run.sh, logs/kill2.log ends ALL_DONE).
Corpora: shipped (seed 482617, degenerate) and hidden h1101..h1104 from `proto2/gen2.py`. Scoring `proto2/score2.py`:
a station counts EXACT only when every period's tariff (or unresolved status) and every recomputed disputed due
of that station equal the truth (the proxy for the planned per-station whole-document w5 checks).
Lever points = 16 hidden station units (4 corpora x 4 stations).

| solver | instance | seconds | WRONG / TIMEOUT / CRASH / EXACT | lever points kept | shipped inputs fast |
|---|---|---|---|---|---|
| ref: full stated domain, decomposed fit, tariff count | shipped, h1101-h1104 | 0.4-0.6 | EXACT 20/20 | 16/16 | yes |
| K1 one convention everywhere (headline + own calendar) + full 180-tariff count (= K3 shipped readings carried, = K5 v1-equivalent blind program) | shipped 4/4; h1101-h1104 0/16 | 0.0 | WRONG 16/16 | 0/16 | yes |
| K2 first fit over natural-wide space (A{1,15,30} D{1,5,10}, whole-hour windows, all 7 calendars), first tariff, no count (H8) | shipped 4/4; hidden 0/16 | 0.0 | WRONG 16/16 | 0/16 | yes |
| K4 careful natural: count, A{1,15,30} D{1,5,10} S2 B2, own calendar, night 22-06 | shipped 4/4; hidden 0/16 | 0.0 | WRONG 16/16 | 0/16 | yes |
| K4w careful natural-wide (G-4 row 4): count, A{1,15,16,30} D{1,5,6,10} S2 B2, all 7 calendars, all 552 whole-hour windows | shipped 4/4; hidden 0/16 | 0.0 | WRONG 16/16 | 0/16 | yes |
| K4q all-but-one (full mark ranges, all calendars, whole-hour windows only) | shipped 4/4; h1101 1, h1102 2, h1103 0, h1104 0 | 0.0 | WRONG 13/16 | 3/16 (81% lost) | yes |
| K6 full stated domain with decomposition | = ref | 0.4-0.6 | EXACT | 16/16 | yes |
| K6n full stated domain, plain nested product (76.6M conventions x 180 tariffs per station) | not run (13.8 G first-invoice tests per station) | > limit on shipped too | self-detectable on shipped, so NOT counted as lever loss (v3.5 condition "no shipped input slow" fails) | n/a | no |
| optimisation solvers (ILP/DP/split-then-exact) | N/A (fit task, no optimisation) | | | | |

Verdict: rows 1-3 (K1, K2, K1-as-K3) and G-4 row 4 (K4w) lose 100% of lever points by WRONG; all-but-one K4q loses 81%.
Every loss is a valid but wrong document (no crash, no timeout). Honest hole: an agent that searches the whole stated
domain (mark 1..30, mark 1..10, quarter-hour windows, 7 calendars, both binaries) and decomposes the search is exact;
this is the correct solution, not a generic solver. The design-blind read (Phase 0b) decides whether Opus reaches it.

## Lessons for the master
- A lever whose domain is a stated numeric range is one careful loop away from exact; only the blind read can price it | no change: evidence pending (Phase 0b)

## Phase 0b re-run on the fresh design-blind bytes (proto3)

Docker (`dockfree.py --need-mb 4096 --cpus 2` START=yes FREE_MB=4706; `docker run --rm --memory 4g --cpus 2 python:3.12-slim`,
perl alarm 600; script `_runs/20261031/pilotage-dues-reconstruction/blind-20261031T1245/scratch/run3.sh`, log
`.../logs/run3.log` ALL_DONE). Solver `WORK/proto3/solve3.py` parses the rendered 10 data files; reference = every mark,
every calendar, surcharge hours to the minute (asserts exactly one convention choice per station). Scored per station
(region file + that station's policy_audit rows equal the reference); reference checked against generator truth: OK.

| solver | instance | seconds | WRONG / TIMEOUT / CRASH / EXACT | lever points kept | shipped inputs fast |
|---|---|---|---|---|---|
| ref (full stated domain, decomposed) | sample, h1101, h1103, h1105 | 0.19-0.26 | EXACT | 12/12 | yes |
| K1 one convention everywhere | sample 4/4; hidden 0/12 | 0.14-0.21 | WRONG 12/12 | 0/12 | yes |
| K4w careful natural-wide (marks {1,15,16,30}/{1,5,6,10}, whole-hour hours, all calendars, count) | sample 4/4; hidden 0/12 | 0.18-0.22 | WRONG 12/12 | 0/12 | yes |
| K4q all-but-one (every mark, every calendar, quarter-hour hours, count) | sample 4/4; h1101 1, h1103 0, h1105 0 | 0.13-0.23 | WRONG 11/12 | 1/12 (92% lost) | yes |
| optimisation solvers | N/A (fit task) | | | | |

## Design blind 5456c27 (score-5456c27, Docker 4g/2cpu, alarm 600, logs/score.log ALL_DONE)
| solver | instance | seconds | WRONG / TIMEOUT / CRASH / EXACT | lever points kept | shipped inputs fast |
|---|---|---|---|---|---|
| blind 5456c27 (proto/blind/derive_report.py, sha256 10de7239...c861) | sample | 0.89 | EXACT | 4/4 | yes |
| blind 5456c27 | h1101 | 0.87 | EXACT | 4/4 | yes |
| blind 5456c27 | h1103 | 1.01 | EXACT | 4/4 | yes |
| blind 5456c27 | h1105 | 1.07 | EXACT | 4/4 | yes |
Hidden 12/12 kept, 0% of lever points lost. It searched the full stated domain (draft marks 1..10, assist marks 1..30, both bases, every holidays.json calendar x Monday, minute-level surcharge arcs, decomposed per tariff). Verdict: NO CORE.

## Try 4 (anchor-type conventions) on fresh design-blind bytes, 31 Oct 14:00
Log `_runs/20261031/pilotage-dues-reconstruction/try4-20261031T1353/logs/kill4.log` (ALL_DONE). Corpora sample (482617), h1101 h1102 h1104 h1105 h1106.
| solver | instance | seconds | WRONG / TIMEOUT / CRASH / EXACT | lever points kept | shipped inputs fast |
|---|---|---|---|---|---|
| ref = K5 full reading | all 6 | 0.22-0.30 | EXACT | 20/20 | yes |
| K1 shipped carried | hidden x5 | 0.16-0.19 | WRONG | 0/20 | yes (exact) |
| K2 first fit, station-wide constants | hidden x5 | 0.20-0.26 | WRONG | 1/20 (h1105 West) | yes (exact) |
| K4w careful wide, station-wide constants, counted | hidden x5 | 0.20-0.29 | WRONG | 2/20 (h1105 West, h1106 West) | yes (exact) |
| optimisation solvers | - | - | N/A (fit task) | - | - |
Honest hole: K5 (per-visit flag/agent anchors included) is the reference and is exact.
| blind 529e4de (design blind, try 4) | sample + hidden x5 | 1.70-2.72 per corpus | EXACT | 20/20 (0% lost) | yes (shipped 4/4) |
Log `_runs/20261031/pilotage-dues-reconstruction/score-529e4de/logs/score.log` (ALL_DONE); totals_equal True on every corpus.
