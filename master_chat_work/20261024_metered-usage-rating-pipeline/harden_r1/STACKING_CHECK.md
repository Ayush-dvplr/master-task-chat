# STACKING_CHECK: metered-usage-rating-pipeline (harden round 1, 3106c16)

Started from `tools/stacking_check.py` on the AFTER bundle; every hint below was checked against `tests/test_output.py` and the measured cost table (`WORK/cost_table.json`, run 24 Oct 21:1x IST).

## (a) Test rows

Reflex program = solve.py with the three lever wrong readings injected together (LV-MU-1 coerces quoted/float north units, LV-MU-3 credit base by plan in force at the line, LV-MU-5 tier counter per account): measured 10/199 (cost_table `all wrong`). Lever columns are the measured failing tests of each `alone` run; noise columns are the measured `noise alone` runs (LV-MU-2 half-up, LV-MU-4 raw ids), which do not count toward the three levers.

| test | w | input | observable | decisive logic | levers whose misread fails it | reflex program |
|---|---|---|---|---|---|---|
| accepted_lines | 3 | delivered /app/out, shipped month | normalized.jsonl: ordered (record_id, region, timestamp, account_id, product, units) of every line | _check_accepted_lines: ordered list equality | LV-MU-1 | fail |
| accepted_lines_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl: ordered (record_id, region, timestamp, account_id, product, units) of every line | _check_accepted_lines: ordered list equality | LV-MU-1 | fail |
| rating_central | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region central: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1 | fail |
| rating_central_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region central: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1, LV-MU-5, (noise LV-MU-2, LV-MU-4) | fail |
| rating_east | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region east: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1 | fail |
| rating_east_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region east: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1, LV-MU-5, (noise LV-MU-2, LV-MU-4) | fail |
| rating_north | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region north: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1 | fail |
| rating_north_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region north: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1, LV-MU-5, (noise LV-MU-2, LV-MU-4) | fail |
| rating_south | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region south: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1 | fail |
| rating_south_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region south: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1, LV-MU-5, (noise LV-MU-2, LV-MU-4) | fail |
| rating_west | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region west: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1 | fail |
| rating_west_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region west: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1, LV-MU-5, (noise LV-MU-2, LV-MU-4) | fail |
| credit_central | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region central: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1 | fail |
| credit_central_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region central: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| credit_east | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region east: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1 | fail |
| credit_east_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region east: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| credit_north | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region north: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1 | fail |
| credit_north_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region north: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| credit_south | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region south: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1 | fail |
| credit_south_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region south: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| credit_west | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region west: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1 | fail |
| credit_west_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region west: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| region_central | 3 | delivered /app/out, shipped month | region_central.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1 | fail |
| region_central_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | region_central.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| region_east | 3 | delivered /app/out, shipped month | region_east.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1 | fail |
| region_east_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | region_east.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| region_north | 3 | delivered /app/out, shipped month | region_north.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1 | fail |
| region_north_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | region_north.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| region_south | 3 | delivered /app/out, shipped month | region_south.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1 | fail |
| region_south_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | region_south.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| region_west | 3 | delivered /app/out, shipped month | region_west.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1 | fail |
| region_west_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | region_west.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| segment_consumer | 3 | delivered /app/out, shipped month | segment_consumer.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1 | fail |
| segment_consumer_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | segment_consumer.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| segment_corporate | 3 | delivered /app/out, shipped month | segment_corporate.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1 | fail |
| segment_corporate_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | segment_corporate.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| segment_enterprise | 3 | delivered /app/out, shipped month | segment_enterprise.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1 | fail |
| segment_enterprise_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | segment_enterprise.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| segment_smb | 3 | delivered /app/out, shipped month | segment_smb.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1 | fail |
| segment_smb_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | segment_smb.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| product_summary | 3 | delivered /app/out, shipped month | product_summary.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1 | fail |
| product_summary_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | product_summary.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| summary | 3 | delivered /app/out, shipped month | summary.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1 | fail |
| summary_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | summary.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, LV-MU-5, COUPLING, (noise LV-MU-2, LV-MU-4) | fail |
| data_quality | 3 | delivered /app/out, shipped month | data_quality.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1 | fail |
| data_quality_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | data_quality.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, (noise LV-MU-4) | fail |
| mutation_tier_scale | 5 | hidden month, tier thresholds x1.0375 rounded up, collector rows shuffled | product_summary.json of the scaled run | _check_tier_scale: parsed JSON equality | LV-MU-1, LV-MU-3, LV-MU-5, MUT | fail |
| missing_collector | 3 | hidden month with one collector removed | exit status + stderr | non-zero exit and `missing input: <file>` | MUT | pass |
| control_mismatch | 3 | hidden month with one data row removed | exit status + stderr | non-zero exit and `control mismatch: <file>` | MUT | pass |
| determinism | 3 | two runs on the hidden month | bytes of the 13 documents | byte identity, non-empty | MUT | pass |
| transform_exists | 1 | delivered /app/out | /app/out/transform.py | _check_program_exists: non-empty file | EXIST | pass |
| negative_hardcoded_sample_answers | -5 | hidden month run | summary.json month/charge/credit/net | _check_restates_shipped: equals shipped value where fresh differs | NEG | n/a (does not fire) |

TS-26 hint corrected: the tool paired each `<doc>` with `<doc>_hard` and grouped the four mutation/rejection checks because it keys on helper names. By reading the code: `<doc>` reads the delivered shipped-month document and `<doc>_hard` reads the document written by a fresh run on a different month from another seed and scale, so the observables differ (QC_RULINGS district-heat v3:185 PASS). mutation_tier_scale, missing_collector, control_mismatch and determinism call four different helpers on four different inputs and observe different things. No two rows share both observable and logic.
TS-13: every check makes one comparison; the tool found no multi-assert hint.

## (b) Penalty groups by act (tests + judge)

| act | tests | judge | sum abs w | result |
|---|---|---|---|---|
| hard-coding the shipped answers | negative_hardcoded_sample_answers -5 | none | 5 | PASS |
| claiming a check passed with no run that shows it | none | R11 -3 | 3 | PASS |
| stating a figure no command computed | none | R12 -3 | 3 | PASS |
| reading or listing grader paths (/tests, /logs/verifier) | none | R13 -5 | 5 | PASS |
| writing, moving or deleting a file under /app/data | none | R14 -3 | 3 | PASS |

Hint corrected: the tool put R12 and R14 in one UNMATCHED group (6); they are two different acts with different triggers, so each group is 3. No negative fires on the oracle or on any wrong-reading run (every cost_table row reports fired 0).

## (c) Weight shares and caps

- Positive test weight 199, negative -5; judge 16 criteria (R15 tier counter recompute w3, R16 credit base recompute w3 added), positive 34, negatives -14, mode batched; reward.toml 0.5/199 tests, 0.5/34 judge.
- Hidden or mutated reruns: 129 / 199 = 64.8% (>= 30%, G3 PASS).
- Whole-document checks 96 / 199 = 48.2%; row-owned line checks 88 / 199 = 44.2%; shipped-only 70 / 199 = 35.2% (no cap).
- Tests 52, criteria 16 (>= 8). One weight-1 check (transform_exists, existence only, TS-20). J1 hint on R8 is the code-quality line limit, not an output figure.

## (d) Cost table (G10), measured on the AFTER tests

From `WORK/COST_TABLE.md` (rubric assumed 90):

| lever | alone lost | all but this right overall | one fact wrong lost | gate |
|---|---|---|---|---|
| LV-MU-1 | 95.0% | 67.4 | 73.9% | PASS |
| LV-MU-3 | 42.7% | 47.5 | 22.6% | PASS (one-fact below 25: CL-4 exemption sentence kept in instruction.md) |
| LV-MU-5 | 55.3% | 47.5 | 25.1% | PASS |

Graded noise (not levers): LV-MU-2 alone 55.3%, LV-MU-4 alone 57.8%. All three levers wrong: 95.0% lost.
COUPLING: the region credit base (glossary 30-31, Credit 161-165) is read by LV-MU-3 directly and moves with every LV-MU-5 tier change, so the two slips stack on the same 17 `_hard` documents.

## (e) Rule coverage (G11)

`WORK/RULE_COVERAGE.md`: 53 rule rows, 0 rows with 0 tests failed (new rules: committed account, billing group / tier counter, parent column canonical form).

STACKING PASS
