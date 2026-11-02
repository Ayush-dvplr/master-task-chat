# Kill test (wave 2, 09963d3), Docker python:3.12-slim --cpus 2 -m 4g, cap 120 s (planned stated limit 60 s)

Prototype corpora (WORK/proto, scratch): built by proto/patch_tests.py = existing hidden generator gen_month(hidden=True) plus one reseller parent line of `chain` accounts (own RNG Random(seed*104729+29)). Old hidden corpus byte-identical (digest cd6a472bafff4a33).

| corpus | month | accounts | chain | rows/collector | accepted lines |
|---|---|---|---|---|---|
| 70001 | 2027-06 | 40000 | 30000 | 4000 | 18934 |
| 70003 | 2027-01 | 50000 | 35000 | 6000 | 28351 |
| 70004 | 2028-01 | 54000 | 38000 | 6500 | 30728 |

Lever points per corpus (planned): finishes+all docs w3, normalized.jsonl w5, summary.json w5, product_summary.json w3 = 16; 3 corpora = 48.

| solver | what it does | 70001 s (cap 240) | 70003 s | 70004 s | exact docs | lever points kept |
|---|---|---|---|---|---|---|
| ref_solve (solution/solve.py, memo group) | reference | 1.62 | 3.80 | 3.75 | 13/13 | 48/48 |
| ref_compute (tests) | independent expected | 2.05 | 2.92 | 2.14 | n/a | n/a |
| s8_memo (iterative memo, control) | strong generic | 1.60 | 3.21 | 3.90 | 13/13 | 48/48 |
| s1_probe (probe run 3 program as is) | per-account parent walk, no memo | TIMEOUT 240 | TIMEOUT 120 | TIMEOUT 120 | 0 | 0/48 |
| s2_perline (group resolved per line, nothing carried) | "per period" analogue | 100.62 | TIMEOUT | TIMEOUT | 0 at 60 s | 0/48 |
| s3_label (state keyed by parent text as written) | keyed by label | 1.62 | 3.18 | 6.15 | 1/13 (data_quality only) | 9/48 |
| s4_endonly (plan/segment = end-of-month state) | applies changes at the end | TIMEOUT 240 | TIMEOUT | TIMEOUT | 0 | 0/48 |
| s5_greedy (one parent level) | greedy | 3.16 | 3.32 | 5.68 | 1/13 | 9/48 |
| s6_naive (per-line walk + linear plan scan) | naive | 102.6 | TIMEOUT | TIMEOUT | 0 at 60 s | 0/48 |
| s7_recursive (lru_cache recursion) | plain recursion | 0.68 RecursionError | 0.59 RecursionError | 0.59 RecursionError | 0 | 0/48 |

Every listed generic solver loses >= 81% of the lever points (bar is 15%). s3, s5 lose by a wrong document; s1, s2, s4, s6 by missing the stated run time (inherent to P-3; note 4's "wrong document" form applies to P-2); s7 by a crash. Reference worst 3.90 s = 1/15 of 60 s (bar 1/4).
Logs: proto/logs/kill_70001.log, proto/logs/kill_big.log (ALL_DONE).

## Final generator output (bundle tests/test_output.py `_long_files(1..3)`, reseller tree), Docker python:3.12-slim --cpus 2 -m 4g, cap 150 s, limit 60 s
Log: proto/logs/final_kill.log (ALL_DONE). Long 1: 2027 month, 76005 accounts, 61459 lines; long 2: 80005 / 66290; long 3: 84005 / 70927. Tree depth >= 9000 (300-seed min, proto/logs/shape.log).
Points per long month: finishes w3 + normalized w5 + summary w5 + product_summary w3 = 16; 48 over three.

| solver | long 1 s | long 2 s | long 3 s | exact docs | lever points kept /48 | how it loses |
|---|---|---|---|---|---|---|
| ref_solve (solution/solve.py) | 5.70 | 2.79 | 3.00 | 13/13 | 48 | - |
| ref_compute (tests) | 23.88* | 2.95 | 3.53 | n/a | n/a | - |
| s8_memo (iterative memo, control) | 18.26* | 2.94 | 3.02 | 13/13 | 48 | - |
| s1_probe (probe run 3 program) | >150 | >150 | >150 | 0 | 0 | past 60 s |
| s2_perline (resolve per line, nothing carried) | 136.05 | 126.64 | 128.17 | 13/13 late | 0 | past 60 s |
| s3_label (keyed by parent text as written) | 7.18 | 3.02 | 3.36 | 1/13 | 9 | wrong documents |
| s4_endonly (plan/segment end state) | 718* | 127.18 | 144.88 | 1/13 | 0 | wrong documents and late |
| s5_greedy (one parent level) | 3.93 | 2.95 | 3.27 | 1/13 | 9 | wrong documents |
| s6_naive (per-line walk + linear plan scan) | 440* | 103.28 | 123.55 | 13/13 late | 0 | past 60 s |
| s7_recursive (lru_cache recursion) | 0.26 | 0.24 | 0.24 | 0 | 0 | RecursionError |

\* long 1 ran while the host was loaded (other sessions' verifiers; host clock gap); long 2/3 figures are the clean ones. Every generic solver loses >= 81% of the lever points; reference max 5.70 s <= 15 s (1/4 of 60).

## Final generator output, 15-second limit (27 Oct 2026 18:25-18:45 IST, Docker --cpus 2 --memory 4g, cap 60 s)

Corpora are the bundle's own `_long_files(1..3)`: long 1 76005 accounts / 61459 accepted lines
(gen 10.3 s, ref_compute 2.21 s), long 2 80005 / 66290 (11.1 s, 2.50 s), long 3 84005 / 70927
(10.6 s, 2.62 s). Points kept of the 48 the lever carries (16 per long month: finishes 3,
normalized 5, summary 5, product_summary 3; a document counts only when the run finished within
15 s). Log: `proto/logs/final_kill.log` (ALL_DONE).

| solver | long 1 s | long 2 s | long 3 s | exact docs | points kept /48 | loss |
|---|---|---|---|---|---|---|
| ref_solve (solution/solve.py) | 2.12 | 2.64 | 2.52 | 13/13 x3 | 48 | 0% |
| s8_memo (iterative memo, control) | 2.27 | 2.57 | 2.67 | 13/13 x3 | 48 | 0% |
| s9_plainwalk (solve.py, per-account walk) | 23.99 | 34.73 | 36.72 | 13/13 x3, late | 0 | 100% |
| s1_probe (run-3 program) | >60 cap | >60 | >60 | none | 0 | 100% |
| s2_perline (group at every line) | >60 | >60 | >60 | none | 0 | 100% |
| s4_endonly (plan in force = end state) | >60 | >60 | >60 | none | 0 | 100% |
| s6_naive (per-line walk, linear plan scan) | >60 | >60 | >60 | none | 0 | 100% |
| s7_recursive (lru_cache recursion) | 0.19 RecursionError | 0.20 | 0.20 | none | 0 | 100% |
| s3_label (parent text as written) | 2.32 | 2.57 | 2.75 | 1/13 x3 (wrong docs) | 9 | 81% |
| s5_greedy (one-level parent) | 2.35 | 2.55 | 2.71 | 1/13 x3 (wrong docs) | 9 | 81% |

Reference max 2.64 s = 1/5.7 of the 15 s limit. Every generic solver loses >= 81% of the lever's
points; the label and greedy solvers by wrong documents, the others by not finishing in time
(P-3 loss mode, recorded in DESIGN.md).

## Gate v3.6 harden (361674d): LV-MU-9 long tier ladder on long reseller months

Docker python:3.12-slim --cpus 2 --memory 4g, run cap 45 s (60 s for some scans), stated limit 15 s
(rating_contract.md:48-49). Corpora from proto/build_ladder.py = gen_month(hidden=True, resellers=R,
ladder=L): the wave-2 long-month shape plus a rate card whose every product lists L tiers (own RNG
Random(seed*6271+53), starts at quantiles of the real tier counters so lines spread over the ladder).
Expected docs from WORK ref_core.ref_compute (bisect tier lookup; equal to bundle test reference on
shipped, hidden, scaled, small, near corpora). Points per corpus in this table: finishes 3 +
normalized 5 + summary 5 + product_summary 3 = 16, kept only when the run ends within 15 s.
Shipped inputs fast: yes for every solver (shipped rate card unchanged, 3 tiers per product).

| corpus | rows | accounts | resellers | tiers | accepted lines | card MB | gen s | ref_compute s |
|---|---|---|---|---|---|---|---|---|
| ladder_72001 | 13000 | 76000 | 11000 | 20000 | 61587 | 10.3 | 10.8 | 2.57 |
| ladder_72002 | 13000 | 76000 | 11000 | 50000 | 61530 | 25.8 | 13.5 | 3.07 |
| ladder_72003 | 15000 | 84000 | 12000 | 50000 | 70963 | 25.9 | 14.7 | 3.24 |

| solver | 72001 (20k tiers) s | 72002 (50k) s | 72003 (50k) s | 72003 result | kept/16 | lever loss |
|---|---|---|---|---|---|---|
| ref_solve (bisect tier, iterative group walk) | 2.56 | 2.92 | 3.07 | EXACT | 16 | 0% |
| s8_memo (memo group walk, tier scan) | 39.18 | - | >45 | TIMEOUT | 0 | 100% |
| s9_plainwalk | - | - | 21.57 | TIMEOUT (exact docs, over 15 s) | 0 | 100% |
| s10_tierscan (full forward scan) | 27.11 | >60 | >45 | TIMEOUT | 0 | 100% |
| s11_tierbreak (forward scan with break) | 12.71 | 28.05 | 31.4 | TIMEOUT (exact docs, over 15 s) | 0 | 100% |
| s12_tierrev (reverse scan with break) | 20.24 | 46.18 | >45 | TIMEOUT | 0 | 100% |
| s13_tiermax (max over starts) | 28.23 | >60 | >45 | TIMEOUT | 0 | 100% |
| s1_probe | - | - | >45 | TIMEOUT | 0 | 100% |
| s2_perline | - | - | >45 | TIMEOUT | 0 | 100% |
| s4_endonly | - | - | >45 | TIMEOUT | 0 | 100% |
| s6_naive | - | - | >45 | TIMEOUT | 0 | 100% |
| s7_recursive | - | - | 0.2 | CRASH (RecursionError, rc 1) | 0 | 100% |
| s3_label | - | - | 3.54 | WRONG (1/13 docs exact) | 3 | 81% |
| s5_greedy | - | - | 3.46 | WRONG (1/13 docs exact) | 3 | 81% |
| agent_p3 (probe-3 agent program) | >45 | - | >45 | TIMEOUT | 0 | 100% |
| blind_c60b (wave-2 blind, scored 100) | >45 | - | >45 | TIMEOUT | 0 | 100% |
| blind_9d66 (wave-2 blind, scored 100) | >45 | - | >45 | TIMEOUT | 0 | 100% |
| blind_d576 (6f5046a blind) | >45 | - | >45 | TIMEOUT | 0 | 100% |

Reference max 3.07 s (program) / 3.24 s (test reference) <= 3.75 s = 1/4 of 15 s. Every generic,
blind and agent program loses >= 81% of the lever points; s3/s5 by WRONG documents (parent chain),
the rest by v3.5 hidden-scale TIMEOUT (no shipped input slow, stated 15 s sentence without method
words, cost confined to the ladder checks, each ladder corpus its own program call). Only a
logarithmic or monotone-pointer tier lookup together with a linear group walk passes; all four
observed programs (3 blinds + probe-3 agent) scan the tier list per line. Logs: proto/logs/ladder1-5.log.
