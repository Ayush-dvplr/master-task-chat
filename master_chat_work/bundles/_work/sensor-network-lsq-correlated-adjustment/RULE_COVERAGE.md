# RULE_COVERAGE (G11), redesign r2 4d6dfe8

Each mutant drops one rule from `solution/solve.py` alone; scored with the real `tests/test_output.py` (local, `OUT/proto/mutants.py`, raw `OUT/proto/mutants_run1.json` and `mutants_fix.json`). P = 86.

| rule | file:line | mutant | tests failed |
|---|---|---|---|
| abandoned registry rows not used | environment/data/schema.md:18 | abandoned rows read as active | 24 |
| centring variance follows set_out_from to its end | environment/data/schema.md:20 | one level only (own term of the named mark) | 7 |
| higher-revision record is the observation | environment/data/schema.md:53 | first-seen record kept | 25 |
| district is the district of the kept shard | environment/data/schema.md:55 | district from the line region field | 7 |
| authoritative unit rows only | environment/data/schema.md:66 | status filter dropped | 28 |
| sigma_kind stddev squared, variance scaled | environment/data/schema.md:75 | stddev and variance swapped | 28 |
| tripod centring only (pillar adds nothing) | environment/data/schema.md:25 | centring added for pillar mounts too | 24 |
| dir=R negates observed and computed | environment/data/schema.md:84 | no negation | 24 |
| azimuth_wrap reduction into [0,400) | environment/data/schema.md:91 | wrap shards skip both reductions | 21 |
| epoch-2 id transposition | environment/data/schema.md:100 | ids kept verbatim | 25 |
| angle misclosure into (-200, 200] | environment/data/schema.md:111 | plain subtraction | 24 |
| closure fits branch (basis at or below closure) | environment/data/schema.md:120 | fits branch removed | 24 |
| remainder tie to lower obs_id | environment/data/schema.md:124 | tie order ignores obs_id | 24 |
| share below floor absorbs nothing | environment/data/schema.md:124 | floor of 0 | 24 |
| every micrometre shared again over holders | environment/data/schema.md:126 | second pass re-enters the whole rule | 7 |
| absorbed amount carries the closure sign | environment/data/schema.md:128 | sign always positive | 24 |
| u from the workbook | environment/data/schema.md:138 | dof uses a fixed u of 3 | 2 |
| exactly irls_iterations passes | environment/data/schema.md:151 | one pass only | 23 |
| downweighted weight quantized | environment/data/schema.md:161 | unquantized robust weight | 28 |
| session members never downweighted | environment/data/schema.md:163 | members tested too | 11 |
| tuning_k from the workbook | environment/data/schema.md:165 | k fixed at 3 (the yaml default) | 25 |
| session block couples both rows (cross term) | environment/data/schema.md:178 | diagonal block only | 24 |
| decoy session rows ignored | environment/data/schema.md:180 | decoy rows applied | 7 |
| blunder test against blunder_crit squared | environment/data/schema.md:191 | test against blunder_crit unsquared | 24 |
| datum origin from the workbook | environment/data/schema.md:201 | origin fixed at index 2 | 7 |
| datum shift subtracts the origin corrections | environment/data/schema.md:201 | no shift | 3 |
| acceptance interval centre minus and plus 1/2 | environment/data/schema.md:213 | centre plus and minus 1 | 3 |
| half-even rendering of micrometres | environment/data/schema.md:233 | truncation toward zero | 15 |
| sorted JSON keys | environment/data/schema.md:238 | sort_keys dropped | 1 |
| first occurrence per key in the frame and campaign maps | environment/data/schema.md:252 | last occurrence | 4 |
| max residual tie to lowest obs_id | environment/data/schema.md:272 | highest obs_id | 1 |
| superseded_records ordered by obs_id then shard | environment/data/schema.md:305 | sorted on a different key | 1 |
| decoys_ignored names shipped decoy files | environment/data/schema.md:306 | a non-shipped file name | 1 |
| CSV shard fields read as RFC 4180 fields (quotes not part of the value) | environment/data/schema.md:38 | plain delimiter split (`WORK/r0_lever/programs/oracle_all_but_one.py`, solve.py:80 only; hidden points 7/76, `_runs/20261102/sensor-network-lsq-correlated-adjustment/r0-2017/m/plain.json`) | 21 |

34 rows, none with 0 tests failed. R0 868afdf (2 Nov): schema.md cites after line 38 moved down one line for the RFC 4180 sentence; last row added.
