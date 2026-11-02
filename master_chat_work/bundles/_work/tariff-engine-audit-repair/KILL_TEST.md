# KILL_TEST d11904c (wave 1, design D3 scale-split vouchers at ledger scale)

Docker python:3.12-slim, --cpus 2 --memory 4g, 10 s limit per run (the stated `--statements` limit), one run per prototype corpus.
Prototype corpora WORK/proto/corpus_1..7.json (gen.py, RNG Random(seed*7919+4242)); each corpus: 3 big accounts (balance 2.87e10-9.87e10 cents, 55-66 vouchers), 3 tie accounts, 1 overpaid.
Points per corpus as the planned checks: feasible 3, due 5, redeemed 5 (13 max, 91 over 7 corpora).
Logs: /tmp/opencode-logs/w1_kill_20261027T112615.log, /tmp/opencode-logs/w1_kill2_20261027T113710.log (both ALL_DONE, EXIT 0).

## Summary

| solver | max seconds | exact corpora | points kept of 91 | lost share |
|---|---|---|---|---|
| reference | 0.12 | 7/7 | 91 | 0.0% |
| blind_r3 | 10 | 0/7 | 0 | 100.0% |
| bitset | 10 | 0/7 | 0 | 100.0% |
| table | 10 | 0/7 | 0 | 100.0% |
| pareto | 10 | 0/7 | 0 | 100.0% |
| mitm | 10 | 0/7 | 0 | 100.0% |
| mitm_dedupe | 10 | 0/7 | 0 | 100.0% |
| mitm_dedupe_sorted | 10 | 0/7 | 0 | 100.0% |
| branch_bound | 10 | 0/7 | 0 | 100.0% |
| greedy | 0.08 | 0/7 | 21 | 76.9% |
| naive | 10 | 0/7 | 0 | 100.0% |
| bitset_sum_only | 10 | 0/7 | 0 | 100.0% |

## Per instance

| solver | instance | seconds | status | exact | points kept |
|---|---|---|---|---|---|
| reference | corpus_1 | 0.12 | ok | yes | 13 |
| reference | corpus_2 | 0.08 | ok | yes | 13 |
| reference | corpus_3 | 0.09 | ok | yes | 13 |
| reference | corpus_4 | 0.1 | ok | yes | 13 |
| reference | corpus_5 | 0.08 | ok | yes | 13 |
| reference | corpus_6 | 0.08 | ok | yes | 13 |
| reference | corpus_7 | 0.1 | ok | yes | 13 |
| blind_r3 | corpus_1 | 10 | timeout | no | 0 |
| blind_r3 | corpus_2 | 10 | timeout | no | 0 |
| blind_r3 | corpus_3 | 10 | timeout | no | 0 |
| blind_r3 | corpus_4 | 10 | timeout | no | 0 |
| blind_r3 | corpus_5 | 9.27 | rc-9 | no | 0 |
| blind_r3 | corpus_6 | 7.79 | rc-9 | no | 0 |
| blind_r3 | corpus_7 | 8.18 | rc-9 | no | 0 |
| bitset | corpus_1 | 7.71 | rc-9 | no | 0 |
| bitset | corpus_2 | 8.53 | rc-9 | no | 0 |
| bitset | corpus_3 | 10 | timeout | no | 0 |
| bitset | corpus_4 | 8.83 | rc-9 | no | 0 |
| bitset | corpus_5 | 10 | timeout | no | 0 |
| bitset | corpus_6 | 7.79 | rc-9 | no | 0 |
| bitset | corpus_7 | 10 | timeout | no | 0 |
| table | corpus_1 | 10 | timeout | no | 0 |
| table | corpus_2 | 10 | timeout | no | 0 |
| table | corpus_3 | 10 | timeout | no | 0 |
| table | corpus_4 | 10 | timeout | no | 0 |
| table | corpus_5 | 10 | timeout | no | 0 |
| table | corpus_6 | 10 | timeout | no | 0 |
| table | corpus_7 | 10 | timeout | no | 0 |
| pareto | corpus_1 | 10 | timeout | no | 0 |
| pareto | corpus_2 | 10 | timeout | no | 0 |
| pareto | corpus_3 | 10 | timeout | no | 0 |
| pareto | corpus_4 | 10 | timeout | no | 0 |
| pareto | corpus_5 | 10 | timeout | no | 0 |
| pareto | corpus_6 | 10 | timeout | no | 0 |
| pareto | corpus_7 | 10 | timeout | no | 0 |
| mitm | corpus_1 | 10 | timeout | no | 0 |
| mitm | corpus_2 | 10 | timeout | no | 0 |
| mitm | corpus_3 | 10 | timeout | no | 0 |
| mitm | corpus_4 | 10 | timeout | no | 0 |
| mitm | corpus_5 | 10 | timeout | no | 0 |
| mitm | corpus_6 | 10 | timeout | no | 0 |
| mitm | corpus_7 | 10 | timeout | no | 0 |
| mitm_dedupe | corpus_1 | 10 | timeout | no | 0 |
| mitm_dedupe | corpus_2 | 10 | timeout | no | 0 |
| mitm_dedupe | corpus_3 | 10 | timeout | no | 0 |
| mitm_dedupe | corpus_4 | 10 | timeout | no | 0 |
| mitm_dedupe | corpus_5 | 10 | timeout | no | 0 |
| mitm_dedupe | corpus_6 | 10 | timeout | no | 0 |
| mitm_dedupe | corpus_7 | 10 | timeout | no | 0 |
| mitm_dedupe_sorted | corpus_1 | 10 | timeout | no | 0 |
| mitm_dedupe_sorted | corpus_2 | 10 | timeout | no | 0 |
| mitm_dedupe_sorted | corpus_3 | 10 | timeout | no | 0 |
| mitm_dedupe_sorted | corpus_4 | 10 | timeout | no | 0 |
| mitm_dedupe_sorted | corpus_5 | 10 | timeout | no | 0 |
| mitm_dedupe_sorted | corpus_6 | 10 | timeout | no | 0 |
| mitm_dedupe_sorted | corpus_7 | 10 | timeout | no | 0 |
| branch_bound | corpus_1 | 10 | timeout | no | 0 |
| branch_bound | corpus_2 | 10 | timeout | no | 0 |
| branch_bound | corpus_3 | 10 | timeout | no | 0 |
| branch_bound | corpus_4 | 10 | timeout | no | 0 |
| branch_bound | corpus_5 | 10 | timeout | no | 0 |
| branch_bound | corpus_6 | 10 | timeout | no | 0 |
| branch_bound | corpus_7 | 10 | timeout | no | 0 |
| greedy | corpus_1 | 0.08 | ok | no | 3 |
| greedy | corpus_2 | 0.08 | ok | no | 3 |
| greedy | corpus_3 | 0.08 | ok | no | 3 |
| greedy | corpus_4 | 0.08 | ok | no | 3 |
| greedy | corpus_5 | 0.07 | ok | no | 3 |
| greedy | corpus_6 | 0.07 | ok | no | 3 |
| greedy | corpus_7 | 0.07 | ok | no | 3 |
| naive | corpus_1 | 10 | timeout | no | 0 |
| naive | corpus_2 | 10 | timeout | no | 0 |
| naive | corpus_3 | 10 | timeout | no | 0 |
| naive | corpus_4 | 10 | timeout | no | 0 |
| naive | corpus_5 | 10 | timeout | no | 0 |
| naive | corpus_6 | 10 | timeout | no | 0 |
| naive | corpus_7 | 10 | timeout | no | 0 |
| bitset_sum_only | corpus_1 | 10 | timeout | no | 0 |
| bitset_sum_only | corpus_2 | 10 | timeout | no | 0 |
| bitset_sum_only | corpus_3 | 10 | timeout | no | 0 |
| bitset_sum_only | corpus_4 | 10 | timeout | no | 0 |
| bitset_sum_only | corpus_5 | 10 | timeout | no | 0 |
| bitset_sum_only | corpus_6 | 10 | timeout | no | 0 |
| bitset_sum_only | corpus_7 | 10 | timeout | no | 0 |

## Wave 1 (d11904c, 27 Oct 2026): measured in Docker on the built bundle, tests share of 488 positive points

python:3.12-slim, 2 cpus, 4 GB, uid 1000; whole program scored by the real checks (t4_scripts/cost_t4.py,
cost_docker.sh; t4_results/cost_docker.json). Lever = the 21 ledger checks, 91 points.

| program | tests | positive checks failed | lever points kept of 91 |
|---|---|---|---|
| oracle (split reference) | 1.0000 | 0 | 91 |
| oracle build, kill-test reference solver | 1.0000 | 0 | 91 |
| blind round-3 program (397/397 last round) | 0.8135 | 21 | 0 |
| blind round-3 program with the reference optimum (float check) | 1.0000 | 0 | 91 |
| blind r3 `_redeem` (cents bitset, suffix masks) | 0.8135 | 21 | 0 |
| gcd-reduced cents bitset with id-order rebuild | 0.8135 | 21 | 0 |
| cents bitset, optimum sum only, greedy ids | 0.6598 | 36 | 0 |
| dict table of sums -> first ids | 0.6270 | 42 | 0 |
| Pareto list, dominance pruned | 0.6270 | 42 | 0 |
| halves, sorted, raw | 0.6270 | 42 | 0 |
| halves deduped by sum, id split | 0.6270 | 42 | 0 |
| halves deduped by sum, amount split | 0.6270 | 42 | 0 |
| branch and bound, fractional bound | 0.6270 | 42 | 0 |
| largest voucher first | 0.7029 | 29 | 21 |
| naive combinations | 0.6270 | 42 | 0 |
| Q1 wrong alone | 0.8197 | 20 | 65 |
| Q2 wrong alone | 0.8299 | 19 | 65 |
| Q3 wrong alone | 0.6885 | 34 | 52 |
| Q4 wrong alone | 0.7500 | 28 | 52 |
| Q5 wrong alone | 0.8934 | 12 | 78 |
| U1 wrong alone | 0.9057 | 10 | 78 |
| D1 wrong alone | 0.8955 | 11 | 78 |
| D2 wrong alone | 0.8955 | 11 | 78 |
| first write (Q1-Q5, U1, D1, D2 wrong; exact statements) | 0.3422 | 71 | 0 |
| first write plus cents bitset | 0.3422 | 71 | 0 |
| first write plus greedy | 0.3217 | 73 | 0 |

All-but-one (best single wrong): U1_off 0.9057 (<= 0.92). Lever alone: blind r3 loses 18.6% (10-30%). Negatives fired: none.

## Harden round _ql1 (ed621c7), Docker 4g / 2 cpu, chain /tmp/opencode-logs/tariff-ql1-kill-20261029T091913-6a84 (ALL_DONE 12:05:14)
Positive test weight 670; lever (hidden-scale statement checks: statement, batch, cycle, ledger x 7 corpora) 364. Cap for CRASH+TIMEOUT: 60% of 670 = 402 (Ayush 09:12, tariff only).

| program | tests | earned | WRONG | TIMEOUT | CRASH | lever loss share | wall s |
|---|---|---|---|---|---|---|---|
| oracle | 100.00 | 670 | 0 | 0 | 0 | 0% | 46.1 |
| QL-run agent package (OUT/agent_program) | 45.67 | 306 | 0 | 0 | 364 | 100% | 210.3 |
| solver:bitset | 45.67 | 306 | 0 | 0 | 364 | 100% | 195.4 |
| solver:gcd_split | 59.25 | 397 | 0 | 0 | 273 | 75% | 129.0 |
| solver:mitm_only | 45.67 | 306 | 0 | 351 | 13 | 100% | 325.0 |
| solver:tie_naive | 78.36 | 525 | 145 | 0 | 0 | 39.8% (WRONG) | 49.2 |
| solver:greedy | 57.46 | 385 | 285 | 0 | 0 | 78% (WRONG) | 38.0 |
| solver:mitm_dedupe | 45.67 | 306 | 0 | 364 | 0 | 100% | 312.6 |
| solver:branch_bound | 45.67 | 306 | 0 | 364 | 0 | 100% | 311.6 |
| solver:combined (= reference) | 100.00 | 670 | 0 | 0 | 0 | 0% | 44.0 |
| first_write | 28.06 | 188 | 482 | 0 | 0 | - | 46.9 |
| first_write+solver:bitset | 24.18 | 162 | 144 | 117 | 247 | - | 240.4 |
| blind_r3 | 45.67 | 306 | 0 | 0 | 364 | 100% | 199.7 |
| blind_r3+solver:combined | 100.00 | 670 | 0 | 0 | 0 | 0% | 42.7 |

Every generic solver and blind program loses >= 15% of lever points by WRONG or v3.5 hidden-scale loss; all CRASH/TIMEOUT loss sits on lever checks and is <= 364 (54.3%) < 402 cap. Only the combined exact solver scores 670. No negative fired.
