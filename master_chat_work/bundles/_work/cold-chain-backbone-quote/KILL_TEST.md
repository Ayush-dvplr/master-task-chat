# Kill test, wave 1 (678c839), lever P-1

Docker python:3.12-slim, --cpus 2, --memory 4g. Each book has 10 accepted projects, so the
stated limit is 4 s x 10 + 10 s = 50 s per book. Logs: runs/kill_w1_d2_a.log (wide_101, wide_103),
runs/kill_w1_d2_b.log (wide_102), runs/kill_w1_d2r.log (reference rows). Design 1 logs:
runs/kill_w1_design1_{a,b}.log.

Prototype books: proto/books/wide_101..103 (proto/kill.py make 101..103). Every project is a chain of
biconnected blocks joined at cut sites (5-6 blocks of 15-18 sites, link density 2.4-2.8, one hub relay
with three cold-room spokes per block), 77-104 sites, 21-28 cold rooms, 232-289 links, corridor
positions shuffled so open links span far apart in corridor order. Unique minimum network per project.

"crash" = the solver process ended before the limit with no project finished (memory, 4 GB).
Points kept are of the 21 planned wide points (wide_1/2/3 core 5 each, wide report 3, wide networks
feasible 3), out of 105 positive. A feasible but wrong network keeps the 3 feasibility points.

| solver | wide_101 s | wide_102 s | wide_103 s | exact projects | points kept of 21 | loss of 105 |
|---|---|---|---|---|---|---|
| blind 2611 as shipped (span 4 parser) | 0.3 | 0.3 | 0.4 | 0/30 (rejects) | 0 | 20.0% |
| blind d7a0 as shipped (span 4 parser) | 0.2 | 0.2 | 0.3 | 0/30 (rejects) | 0 | 20.0% |
| probe package as shipped (span 4 parser) | 0.2 | 0.2 | 0.3 | 0/30 (rejects) | 0 | 20.0% |
| blind 2611, span rule removed (width from data) | timeout 50.5 | rc -9 36.3 | rc -9 48.2 | 0/30 | 0 | 20.0% |
| blind d7a0, span rule removed | timeout 50.4 | timeout 50.3 | timeout 50.2 | 0/30 | 0 | 20.0% |
| probe package, span rule removed (last-use frontier) | timeout 50.2 | timeout 50.2 | timeout 50.2 | 0/30 | 0 | 20.0% |
| frontier DP over corridor order, width from data | crash 42.8 | crash 39.0 | crash 35.1 | 0/30 | 0 | 20.0% |
| last-use frontier over corridor order | timeout 50.5 | crash 43.2 | crash 48.2 | 0/30 | 0 | 20.0% |
| last-use frontier over min-waiting order (small-width search) | timeout 50.0 (1 project in 47 s) | timeout 50.2 | timeout 50.1 | 1/30 | 0 | 20.0% |
| frontier DP over BFS order | timeout 50.4 | timeout 50.4 | crash 46.6 | 0/30 | 0 | 20.0% |
| Dreyfus-Wagner over all cold rooms | crash 32.9 | crash 25.4 | crash 32.4 | 0/30 | 0 | 20.0% |
| hybrid: DW if <= 14 cold rooms else corridor frontier | crash 42.4 | crash 37.8 | timeout 50.4 | 0/30 | 0 | 20.0% |
| MST on terminal metric (KMB 2-approx) | 0.4 | 0.5 | 0.4 | 0/30 | 3 | 17.1% |
| shortest-path heuristic (Takahashi-Matsuyama) | 0.3 | 0.3 | 0.3 | 0/30 | 3 | 17.1% |
| greedy nearest cold room (link cost only) | 0.3 | 0.4 | 0.3 | 5/30 (no book whole) | 3 | 17.1% |
| naive search over relay subsets | timeout 50.1 | timeout 50.1 | timeout 50.1 | 0/30 | 0 | 20.0% |
| reference: block split at cut sites + per-block exact | 0.4 | 0.4 | 0.4 | 30/30 | 21 | 0 |
| bundle reference ref2 (per block DW or sweep by estimate) | 0.3 | 0.4 | 0.4 | 30/30 | 21 | 0 |

Reference worst project 0.011 s; book 0.3-0.4 s with interpreter start, against a 50 s limit (< 1/4).

Design 1 (blocks of 9-12 sites, density 1.2-1.6, 25-34 cold rooms) was beaten locally by the
last-use frontier over a min-waiting order (10/10 exact in 5.4 s on wide_101), so blocks were made
larger and denser (design 2, above). Every listed solver loses >= 15% of positive test points.

Not killed, recorded: a program that itself splits each project at its cut sites and solves blocks
exactly (that is the reference) is exact and fast. This is the intended route; the documents do not
name it.

## Re-run on the final generator output (27 Oct 13:03-13:33)
Prototype books above were replaced by the bundle's own wide_1..3 (tests/test_output.py).
Every solver re-measured there through the full tests: table in COST_TABLE.md section
"Wave 1"; all lose >= 21 of 24 lever points, reference 3.6-4.8 s per wide check including
book build (50 s limit per book).

## Law-1 fix 25c745d (27 Oct): final data, fresh books 8-10 cold rooms
Full table in COST_TABLE.md section "Law-1 fix 25c745d" (WRONG / TIMEOUT / CRASH split, shipped fast column).
Blind eac8712 84/108 (77.8%), Dreyfus-Wagner 84, hybrid 84, probe and d7a0 span-lifted 84: each loses the 6 wide
checks (24 points) by TIMEOUT and 0 non-lever points. Window-width sweeps and the naive search fail on the shipped book.

## Cap-60 build (30 Oct, board b223662): final generator output, 27 far-reaching checks
Full table in COST_TABLE.md section "Cap-60 build". Lever 115 of 200 positive points.
- a4 final package, a4 first write, Dreyfus-Wagner over all cold rooms: 85/200 each, lose all 115 lever points
  (TIMEOUT 97, CRASH by OOM at 4096 MB 18), 0 non-lever points, 0 WRONG.
- Last-use sweep corridor order: 82/200, 115 lever by CRASH (OOM), 3 non-lever WRONG (tie).
- KMB, greedy: 28/200, lose 112 lever + 60 non-lever by WRONG output. Perlink: 19/200, 115 + 66 WRONG.
- Heuristic solvers still lose by WRONG (>= 15% of lever points: 112/115 and 115/115).
- Exact programs that are fast on the shipped book lose the lever by v3.5 hidden-scale loss only (stated
  limit api_contract.md:91-92, declared memory task.toml 4096 MB); shipped book quiet for all of them.
- Not killed, recorded: the reference route (split at single sites, exact per piece) is exact and fast; the
  documents do not name it.
