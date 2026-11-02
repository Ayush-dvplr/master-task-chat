# KILL_TEST (Docker --memory 4g --cpus 2, python:3.12-slim)

| program | corpus | seconds | result | lever pts kept |
|---|---|---|---|---|
| a1 program | shipped + tiers + 32 generator corpora (seeds 11-15, 101-106; 0.01-1.0; all variants) | 1.1-5.8 | EXACT except MFA reference defect | 100% |
| a1 program | 40 single mutations, seed 101 heldout 0.05 (proto/fuzz_a1_101.txt) | 1.1-1.6 | EXACT x40 (26 effective) | 100% |
| a1 program | combo of 26 effective mutations, 201:0.05:heldout, 202:0.04:boundary, 203:0.3:heldout (proto/combo_a1.txt) | 1.6/1.9/4.5 | EXACT (MFA defect only) | 100% |
| a1 program | 301:3:shipped (proto/scale_a1.txt) | 14.7 (ref 4.2, build 8.3) | EXACT (MFA defect only) | 100% |
| generator | 301:5:heldout, 302:2:heldout | n/a | generator crash (test_output.py:1297, :2229) | n/a |

Blind/first-write/all-but-one programs: not written (a1 bar already fails note 4). Result: NO CORE.

## Try 3: convention lever (option 1), Docker 4 GB 2 CPU, logs proto/t3/kill5a.txt, kill5b.txt
Programs (all except a1 = proto reference engine + one convention strategy, `kill/common/cli.py`; the engine is
the reference, so any loss is the convention reading alone):
- a1: the a1 delivered tool.zip as is (hard-codes shipped readings).
- P0s first-write: shipped readings fixed (site, decided, half).
- P2n careful blind (natural): infers from observations over HR {site, utc} x start {requested, decided, recorded}
  x window {half, closed}: the readings the docs and the legacy tool suggest.
- P3b binary: infers over the shipped-vs-legacy pair per convention (site/utc, requested/decided, half/closed).
- P4o all-but-one: infers HR over {site, utc, every zone} and window, start fixed decided.
- P6o careful wide: infers over {site, utc, every zone} x {requested, decided} x {half, closed}, round robin.

Lever = 8 conv corpora C1-C8 x (dev profile w5 + prod profile w5) = 80. Old 72 assumed all passed.
| program | C1 | C2 | C3 | C4 | C5 | C6 | C7 | C8 | lever kept | tests % | secs/corpus |
|---|---|---|---|---|---|---|---|---|---|---|---|
| a1 | W | W | W | W | W | W | W | W | 0/80 | 47.4 | 1.2-1.6 |
| P2n careful natural | W | W | W | W | W | W | W | W | 0/80 | 47.4 | 6.7-9.4 |
| P0s first-write | W | W | W | W | W | W | W | W | 0/80 | 47.4 | 6.4-6.9 |
| P3b binary | W | W | W | W | W | W | W | W | 0/80 | 47.4 | 7.1-8.5 |
| P4o all-but-one | W | W | W | W | W | W | W | W | 0/80 | 47.4 | 6.7-7.8 |
| P6o careful wide | E | E | E | E | E | E | E | E | 80/80 | 100.0 | 11.8-17.4 |
W = WRONG (dev and prod profiles differ), E = EXACT. No TIMEOUT or CRASH anywhere (timeout share 0).
Old tiers tier_a 51017, tier_b 62029, tier_c 73031 with observe(): every program EXACT.
P3b/P2n keep audit and summary on C3-C6, C8 (those parts are therefore not lever checks).

Shipped corpus, oracle-class timing (proto/t3/p6o_shipped.txt): P6o run_all 515.1 s, EXACT, inferring call 122.8 s
(472 Worlds, 19 rounds). Slow honest programs on shipped: P3b 311.9 s, P2n 776.4 s, P4o 899.4 s (all EXACT).
