# BRANCH_FIRE sentinel-policy-recompute (test-hardening t1, 26 Oct 2026)

Counts from `evaluate(...)[1]` in tests/test_output.py (the test reference), one row per quiet rule. A fire is: Q1 a running value raised to the floor; Q2 an earlier row of a reissued override_id that would otherwise pass selection; Q3 a row naming an alias that passes selection or carries; Q4 a row refused by requires; Q5 a carried delta of the resolved principal.

| rule | branch | fires on shipped (count) | fires on hidden (seeds) |
|---|---|---|---|
| Q1 running timeout floor | units_reference.txt:8-9 | 0 | q1-a 3, q1-b 2, combo-a 2, combo-b 2 |
| Q2 reissued override_id | override_deltas.json:6 | 0 | q2-a 2, q2-b 3, combo-a 4, combo-b 4 |
| Q3 principal alias for part of a window | override_deltas.json:4 | 0 | q3-a 4, q3-b 3, combo-a 5, combo-b 5 |
| Q4 requires, applied earlier in the draw | override_precedence.conf:7, override_deltas.json:11 | 0 | q4-a 2, q4-b 2, combo-a 2, combo-b 2 |
| Q5 carried clause of a superseded row | override_deltas.json:13 | 0 | q5-a 2, q5-b 2, combo-a 2, combo-b 2 |

- Owned corpora fire only their own rule (every other quiet count 0). Combo corpora fire all five, each at least twice, with the rare pairs on one record (P1 alias row requiring a row applied later; P2 reissued id whose later row names an in-span alias; P3 alias rows that drive the running value under the floor; P4 superseded alias row with carry; P5 requires naming a reissued id whose highest row is later; P6 reissued K042 whose later row clips; P7 earlier active row reissued as a superseded carry row).
- Old corpora (shipped, n1-a/b, n2-a/b, n3-a/b, hidden-a..d, pool-a/b, mutation-risk/allowance/pool): 0 fires for every quiet rule, documents byte-equal to the pre-t1 reference, and no wrong reading of Q1-Q5 changes them (lowest running timeout 1400 > floor 1000; no repeated override_id, alias key, requires or carry field).
- Shipped data shows no new key or field: no `param_key_aliases`, no `requires`, no `carry`, no reissued id; the floor value 1000 sits inside the sentence and the shipped running timeout never comes near it (2000 -> 2250).
- Generator: own `random.Random(f"sentinel-{family}-{seed}")` per family, rejection loop with `check_bounds` (stated ranges, rev 2, v100) and `accepted` (owned rule fires >= 2, others 0, every wrong reading of the owned rule changes a document; combo: every rule fires >= 2 and the primary wrong reading of each changes a document). 300 seeds x 6 families: no failure, min owned fires 2.

# Test-hardening t2 (27 Oct 2026, board 4a82a12)

Counts from `evaluate(...)[1]` (tests/test_output.py): u = standing curve reports, d1 = curve reports withdrawn by a later reset, d2 = reinstated rows that pass selection. Shipped override_deltas.json has no `reports` key and no withdrawn or reinstated row, so every count is 0 on shipped data and on the 28 older corpora (snap_before_t2.json vs after: documents and rows identical).

| rule | branch | fires on shipped | fires on hidden |
|---|---|---|---|
| U divisor fixed by the standing curve reports | convergence_spec.txt:7, reconciliation_rules.conf:3 | 0 | utie-a 2 (tie, unresolved), utie-b 2 (tie, unresolved), udecoy-a 3 (divisor 14), udecoy-b 3 (divisor 14), combo2-a 3 (divisor 12), combo2-b 2 (tie, unresolved) |
| D1 reset withdraws earlier curve reports | override_deltas.json:15 | 0 | d1-a 2, d1-b 2, combo2-a 2, combo2-b 2 |
| D2 reinstated row adds the deltas of the last earlier active row | override_deltas.json:14, override_precedence.conf:2 | 0 | d2-a 3, d2-b 3, combo2-a 3, combo2-b 3 |
| combo2 also fires Q1-Q5 | as above | 0 | combo2-a q1 2 q2 4 q3 5 q4 3 q5 2; combo2-b q1 2 q2 4 q3 5 q4 3 q5 2 |

# Test-hardening t3 (27 Oct 2026, board 3022cae)

Counts from `repair_document(...)` (tests/test_output.py; script $T/rfire.py): lists = tenants with a repair, null = mismatched tenants with no repair; a reading column = tenants whose value changes under that wrong reading. R itself fires on shipped data once (t-atlas, repair [3, 6], C(8,2) instance); its quiet sub-branches change nothing there.

| corpus | lists | null | tie (last set) | unit (raw cost) | q2 spare | q5 spare | d2 spare | greedy | count+records only |
|---|---|---|---|---|---|---|---|---|---|
| shipped | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| rbig-a / rbig-b | 2 / 2 | 1 / 1 | 2 / 2 | 2 / 2 | 0 / 0 | 0 / 0 | 0 / 0 | 2 / 2 | 1 / 1 |
| rtie-a / rtie-b | 2 / 2 | 1 / 1 | 2 / 2 | 0 / 0 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 1 / 0 |
| runit-a / runit-b | 2 / 2 | 1 / 1 | 0 / 0 | 2 / 2 | 0 / 0 | 0 / 0 | 0 / 0 | 2 / 2 | 1 / 1 |
| rspare-a / rspare-b | 2 / 2 | 1 / 1 | 0 / 0 | 0 / 0 | 2 / 2 | 2 / 2 | 2 / 2 | 2 / 2 | 1 / 0 |
| rall-a / rall-b | 2 / 2 | 1 / 1 | 2 / 2 | 2 / 2 | 2 / 1 | 2 / 2 | 2 / 2 | 2 / 2 | 1 / 2 |

Older 36 corpora: R rows are never added; t-atlas is mismatched only through the shipped controls edit, and no older check reads ledger_repair.json.
