# COST_TABLE 57a2dd7 cold-chain-backbone-quote

Measured with the bundle's own tests/test_output.py through a local rewardkit stub (WORK/run_local_tests.py), each
variant built by WORK/variants.py from the oracle output (patched core.py, rezipped per build_config, documents regenerated).
Positive test points 84. Overall = 0.5 x tests share + 0.5 x 0.90 (judge taken as 90, not measured).
Logs: runs/variants.log, runs/variants_dw.log, runs/local_oracle.log.

## One lever wrong, everything else right (G10)

| lever | wrong program | tests score | points lost | lost share | overall | negatives |
|---|---|---|---|---|---|---|
| none | oracle (solve.py) | 84/84 | 0 | 0% | 95.0 | silent |
| LV-CC-1 | terminal shortest-path MST (KMB, shipped core.py) with fixed charging | 21/84 | 63 | 75.0% | 57.5 | silent |
| LV-CC-1 | greedy attach (nearest cold room by node-weighted path) | 21/84 | 63 | 75.0% | 57.5 | silent |
| LV-CC-2 | tuned node-weighted Dreyfus-Wagner (exact, over the per-book limit on 16-17 cold rooms) | 30/84 | 54 | 64.3% | 62.9 | silent |
| LV-CC-3 | activation charged once per booked link in core.site_lines (feeds quote and report) | 15/84 | 69 | 82.1% | 53.9 | silent |
| LV-CC-3 (secondary stated-rule lever) | per booked link charging in the report only, quote right | 41/84 | 43 | 51.2% | 69.4 | silent |
| cheat | copies shipped documents for any book | 17/84 | 67 | | | negative_hardcoded_sample_answers fires (-5) |
| none | nop (empty /app/out) | 0/84 | 84 | | | silent |

Every lever alone loses at least 25% of test points; every one-lever-wrong overall is below 70.
LV-CC-3 is recorded as the secondary stated-rule lever (master go item 2): its report-only reading costs 43 points
and rides on the quote-carrying documents; no report weight was raised. LV-CC-1 and LV-CC-2 carry the gate.

## One fact wrong per lever (G10)

| lever | single wrong fact | points lost |
|---|---|---|
| LV-CC-1 | network chosen by shortest paths between cold rooms instead of the minimum over all networks | 63 |
| LV-CC-2 | exact method whose time grows with 3^cold rooms (16-17 cold rooms on fresh books) | 54 |
| LV-CC-3 | activation charge added on every booked link instead of once per activated site | 69 |
| tie | larger link vector picked when two networks tie | 3 |

## Runtime per cold-room count inside Docker (master go item 6)

python:3.12-slim, `docker run --cpus 2 --memory 4g`, WORK/dwbench.py, projects drawn by the hidden generator at
47 to 52 sites and 82 to 92 links (log runs/dwbench_docker.log). Seconds per project; quotes of all three agree.

| cold rooms | sites | links | reference (core.py sweep) | prototype DW | tuned DW |
|---|---|---|---|---|---|
| 12 | 47 | 84 | 0.014 | 0.9 | 0.5 |
| 12 | 51 | 92 | 0.014 | 1.0 | 0.6 |
| 13 | 48 | 92 | 0.016 | 2.8 | 1.7 |
| 13 | 49 | 82 | 0.010 | 2.9 | 1.4 |
| 14 | 51 | 88 | 0.012 | 8.7 | 4.8 |
| 14 | 50 | 85 | 0.010 | 8.7 | 4.8 |
| 15 | 50 | 91 | 0.012 | 25.6 | 15.4 |
| 15 | 48 | 83 | 0.158 | 25.1 | 13.1 |
| 16 | 48 | 85 | 0.157 | 77.9 | 41.4 |
| 17 | 49 | 91 | 0.015 | 237.8 | 128.2 |

Limit stated in api_contract.md:94-96: 4 s per project plus 10 s start-up per book. Tuned DW exceeds 8 s (twice the
limit) from 15 cold rooms; fresh books use 16 to 17 cold rooms in every project, so a tuned DW times out on every
fresh book. The reference stays at or below 0.16 s per project (under the 1 s quarter-limit). Tuned DW: bitmask
subsets, splits holding the lowest cold room, merge at joints only, node charge subtracted once, one Dijkstra per subset.

## Wave 1 (678c839, 27 Oct): measured on the final bundle tests (P-1)

Run: `runs/cost_w1.sh`, verifier image built from BUNDLE tests/, every variant delivery
built by `w1_variants.py` from the oracle app (one solver swapped into core.py, or a whole
earlier package with its span check removed), graded by `run_local_tests.py` against
`tests/test_output.py` (108 positive). Logs `runs/cost_w1_{a,b}.log`, summary
`runs/kill_final_w1.txt`. Lever points = the six wide checks, 24 of 108 (22.2%).

| solver / program | wide_k_core secs (1,2,3) | lever kept /24 | tests | tests % |
|---|---|---|---|---|
| oracle (reference) | 4.8, 3.8, 3.6 pass | 24 | 108/108 | 100.0 |
| first-write plain: exact sweep along corridor order (probe style) | 54-59 timeout | 0 | 81/108 | 75.0 |
| exact sweep along a min-waiting order | 54 timeout | 0 | 81/108 | 75.0 |
| window sweep, width from data (blind 2611 method) | 47-56 timeout | 0 | 65/108 | 60.2 |
| window sweep over BFS order | 54-57 timeout | 0 | 11/108 | 10.2 |
| Dreyfus-Wagner over all cold rooms | 55-57 timeout | 0 | 30/108 | 27.8 |
| hybrid: DW when <= 14 cold rooms, else corridor sweep (all-but-one) | 55-56 timeout | 0 | 84/108 | 77.8 |
| MST on terminal metric (KMB 2-approx) | 4.0-4.6 wrong | 3 | 24/108 | 22.2 |
| shortest-path heuristic (Takahashi-Matsuyama) | 3.0-3.7 wrong | 3 | 24/108 | 22.2 |
| greedy nearest-terminal growth (link cost only) | 4.3-6.1 wrong | 3 | 24/108 | 22.2 |
| naive relay-subset search | 54 timeout | 0 | 11/108 | 10.2 |
| earlier blind 2611 package (84/84 before), span check removed | 54-55 timeout | 0 | 68/108 | 63.0 |
| earlier blind d7a0 package (84/84 before), span check removed | 54-55 timeout | 0 | 84/108 | 77.8 |
| probe run 1 package, span check removed | 54-56 timeout | 0 | 84/108 | 77.8 |

Every listed solver loses at least 21 of the 24 lever points (87.5%); the three heuristics
keep only `wide_networks_feasible` (their networks are feasible, never minimum). Lever alone
costs 24/108 = 22.2% (21/108 = 19.4% for a feasible heuristic); all-but-one program 77.8
(<= 92). Non-lever losses: the two prototype sweeps lack the rank-bit tie rule (tie_book_core),
the width and BFS sweeps, DW and the naive search also time out or err on fresh or shipped books.
Not killed by design: a program that splits each project where its parts meet at a single site
and solves every part exactly (the reference route; nothing in the agent-visible files names it).

Old hidden books byte-identical (sha256 over sorted relpath + bytes, `book_digests.py`,
re-hashed 13:30 from WORK/test_template.py == `runs/old_book_digests.json`):
fresh_1 67b5963d677693c1, fresh_2 8a93ef092908a0ff, fresh_3 6bea49ad6a2f7a54,
rescaled a1962bfa496b2bd3, relocated 8a93ef092908a0ff, missing 4cdaa14f53f17afd,
rejections ef3825ab125ffed5, ties 33aa35d068748138. All 26 old check bodies byte-unchanged (AST).

Wide generator sweep: `sweep300.py test_template.py 1 300 4` (`runs/sweep300_w1.log`), every
project plants five branches (split at single sites, part by subsets, part by sweep, hub
gadget, wide spans) and every wide book has exactly one planted tie (counts nine 1 and one 2).

Judge (P-5): 13 criteria, positive 32, probes R1-R7 21/32 = 65.6%, J10 R8 3, J4 R9 5,
J6 R10 3, negatives R11 -3, R12 -5, R13 -3 (disjoint). Predicted probe-run judge 11/32 = 34%
(R8, R9, R10 met; R1-R5 not shown in run 1; R6, R7 doubtful), predicted mid 34-40%.

## Law-1 fix 25c745d (27 Oct 21:27): fresh books 8-10 cold rooms
Change: `tests/test_output.py:6098` fresh projects draw `rng.randint(8, 10)` cold rooms (was 16-17),
assert :6104 and docstring :6088 follow. Run `runs/kill_l1.sh` (Docker --memory 4g --cpus 2, BUNDLE tests
mounted), logs `runs/kill_l1_{a,b}.log`, builds `runs/kill_l1_build_{a,b}.log`. Lever = 6 wide checks, 24/108.

| solver | tests | % | lever lost | non-lever lost | kind | shipped inputs fast |
|---|---|---|---|---|---|---|
| oracle | 108 | 100.0 | 0 | 0 | - | yes |
| blind eac8712 (DW over cold rooms) | 84 | 77.8 | 24 | 0 | TIMEOUT | yes |
| Dreyfus-Wagner over all cold rooms | 84 | 77.8 | 24 | 0 | TIMEOUT | yes |
| hybrid DW<=14 else corridor sweep | 84 | 77.8 | 24 | 0 | TIMEOUT | yes |
| probe package, span removed | 84 | 77.8 | 24 | 0 | TIMEOUT | yes |
| blind d7a0, span removed | 84 | 77.8 | 24 | 0 | TIMEOUT | yes |
| last-use sweep corridor order | 81 | 75.0 | 24 | 3 (tie, no rank bit) | TIMEOUT + WRONG | yes |
| last-use sweep min-waiting order | 81 | 75.0 | 24 | 3 (tie) | TIMEOUT + WRONG | yes |
| blind 2611, span removed (window = widest link) | 68 | 63.0 | 24 | 16 (shipped docs) | CRASH on shipped + TIMEOUT | no |
| window frontier corridor order | 65 | 60.2 | 24 | 19 (shipped 16, tie 3) | CRASH on shipped + TIMEOUT + WRONG | no |
| window frontier BFS order | 11 | 10.2 | 24 | 73 | TIMEOUT + WRONG | no |
| naive relay-subset search | 11 | 10.2 | 24 | 73 | TIMEOUT + WRONG | no |
| KMB / shortest-path heuristic / greedy | 24 | 22.2 | 21 | 63 | WRONG | yes |
| blind 2611 / d7a0 / probe as shipped (span 4 parser) | 65 | 60.2 | 24 | 19 | WRONG | yes |

Before the fix: Dreyfus-Wagner 30 and blind eac8712 30 (54 non-lever points by TIMEOUT on fresh books with 16-17
cold rooms); every other row unchanged. Every plausible exact program that is fast on the shipped book now loses
the 24 lever points only (22.2%, inside 10-30%). The window-width rows fail on the shipped book itself (visible).

## Cap-60 build (30 Oct, board b223662): held-out far-reaching tier wide_4 to wide_10
Tests regenerated with 21 new checks (wide_K_core 5, wide_K_report 5, wide_K_summary 3, K = 4..10), positive 200.
Lever = the 27 far-reaching checks, 115/200 = 57.5% (cap-60 exception for this bundle). Docker
`--memory 4g --cpus 2`, BUNDLE tests mounted, `runs/cap60_c4.sh`, `runs/cap60_c4b.sh`, logs
`runs/cap60_score_<solver>.log`, split by `cap60_split.py` (T = timed out after 50 s, C = exit -9 with empty
stderr, OOM at 4096 MB, W = output differs).

| solver | tests | % | lever lost | non-lever lost | kind | shipped inputs fast |
|---|---|---|---|---|---|---|
| oracle | 200 | 100.0 | 0 | 0 | - | yes |
| a4 agent final package (OUT/agent_program/repo_from_zip) | 85 | 42.5 | 115 | 0 | TIMEOUT 97 + CRASH 18 | yes |
| a4 agent first write (trajectory steps 19-24) | 85 | 42.5 | 115 | 0 | TIMEOUT 97 + CRASH 18 | yes |
| Dreyfus-Wagner over all cold rooms (w1_variants dw_global) | 85 | 42.5 | 115 | 0 | TIMEOUT 97 + CRASH 18 | yes |
| last-use sweep corridor order (w1_variants lastuse_corridor) | 82 | 41.0 | 115 | 3 (tie_book_core) | CRASH 115 + WRONG 3 | yes |
| terminal-metric tree KMB (w1_variants kmb) | 28 | 14.0 | 112 | 60 | WRONG | yes |
| greedy nearest cold room (variants greedy) | 28 | 14.0 | 112 | 60 | WRONG | yes |
| activation per booked link (variants perlink) | 19 | 9.5 | 115 | 66 | WRONG | yes |

Trap survival against the frozen 8ca9c267f59b tests (points lost there are still lost): KMB lost 81 of 109 there
(60 non-lever + 21 lever) and here 60 non-lever + 112 lever; perlink 19 there (66 non-lever + 24 lever
lost) and here the same 66 non-lever + 115 lever; greedy (not measured on 109 by itself) loses 60 non-lever points here by
WRONG output: 100% of earlier measured losses kept. Reference: oracle CLI 0.13-0.17 s per new far-reaching book against the 50 s
per-book limit; test-side reference 5.07-8.26 s per new book (`runs/cap60_c3.log`).

Verifier worst case (cap-60, measured in Docker, `runs/cap60_c5.log`): a package whose command sleeps forever, so every book run hits its stated cap; the whole tests channel took 1107 s (score 22/200). The a4 harness verifier, tests and batched judge together, took 400 s, so the worst case is at most 1107 + 400 = 1507 s, which is 62% of the 2430 s bar (90% of verifier timeout_sec 2700).
