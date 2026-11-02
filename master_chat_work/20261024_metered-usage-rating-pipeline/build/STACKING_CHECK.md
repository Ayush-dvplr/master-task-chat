# STACKING_CHECK: metered-usage-rating-pipeline (b5f7557)

Started from `tools/stacking_check.py` (output kept in WORK/LOG.md entry); every hint below was checked against `tests/test_output.py` and corrected where the static parser could not see the code.

## (a) Test rows

Reflex program = solve.py with all four wrong readings of COST_TABLE.md injected together (the PREMORTEM first-write program); it scores 10/199.

| test | w | input | observable | decisive logic | levers whose misread fails it | reflex program |
|---|---|---|---|---|---|---|
| accepted_lines | 3 | delivered /app/out, shipped month | normalized.jsonl: ordered (record_id, region, timestamp, account_id, product, units) of every line | _check_accepted_lines: ordered list equality | LV-MU-1 | fail |
| accepted_lines_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl: ordered (record_id, region, timestamp, account_id, product, units) of every line | _check_accepted_lines: ordered list equality | LV-MU-1 | fail |
| rating_central | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region central: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1 | fail |
| rating_central_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region central: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1, LV-MU-2, LV-MU-4 | fail |
| rating_east | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region east: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1 | fail |
| rating_east_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region east: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1, LV-MU-2, LV-MU-4 | fail |
| rating_north | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region north: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1 | fail |
| rating_north_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region north: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1, LV-MU-2, LV-MU-4 | fail |
| rating_south | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region south: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1 | fail |
| rating_south_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region south: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1, LV-MU-2, LV-MU-4 | fail |
| rating_west | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region west: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1 | fail |
| rating_west_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region west: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality on rating keys | LV-MU-1, LV-MU-2, LV-MU-4 | fail |
| credit_central | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region central: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1, LV-MU-3, COUPLING | fail |
| credit_central_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region central: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| credit_east | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region east: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1, LV-MU-3, COUPLING | fail |
| credit_east_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region east: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| credit_north | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region north: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1, LV-MU-3, COUPLING | fail |
| credit_north_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region north: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| credit_south | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region south: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1, LV-MU-3, COUPLING | fail |
| credit_south_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region south: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| credit_west | 3 | delivered /app/out, shipped month | normalized.jsonl rows of region west: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1, LV-MU-3, COUPLING | fail |
| credit_west_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of region west: plan, credit, net by record_id | _check_credit: dict-by-id equality on credit keys | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| region_central | 3 | delivered /app/out, shipped month | region_central.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, COUPLING | fail |
| region_central_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | region_central.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| region_east | 3 | delivered /app/out, shipped month | region_east.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, COUPLING | fail |
| region_east_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | region_east.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| region_north | 3 | delivered /app/out, shipped month | region_north.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, COUPLING | fail |
| region_north_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | region_north.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| region_south | 3 | delivered /app/out, shipped month | region_south.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, COUPLING | fail |
| region_south_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | region_south.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| region_west | 3 | delivered /app/out, shipped month | region_west.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, COUPLING | fail |
| region_west_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | region_west.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| segment_consumer | 3 | delivered /app/out, shipped month | segment_consumer.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, COUPLING | fail |
| segment_consumer_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | segment_consumer.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| segment_corporate | 3 | delivered /app/out, shipped month | segment_corporate.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, COUPLING | fail |
| segment_corporate_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | segment_corporate.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| segment_enterprise | 3 | delivered /app/out, shipped month | segment_enterprise.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, COUPLING | fail |
| segment_enterprise_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | segment_enterprise.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| segment_smb | 3 | delivered /app/out, shipped month | segment_smb.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, COUPLING | fail |
| segment_smb_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | segment_smb.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| product_summary | 3 | delivered /app/out, shipped month | product_summary.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, COUPLING | fail |
| product_summary_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | product_summary.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| summary | 3 | delivered /app/out, shipped month | summary.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-3, COUPLING | fail |
| summary_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | summary.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, COUPLING | fail |
| data_quality | 3 | delivered /app/out, shipped month | data_quality.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1 | fail |
| data_quality_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | data_quality.json whole document | _check_document: parsed JSON equality, first differing path | LV-MU-1, LV-MU-4 | fail |
| mutation_tier_scale | 5 | hidden month, tier thresholds x1.0375 rounded up, collector rows shuffled | product_summary.json of the scaled run | _check_tier_scale: parsed JSON equality | LV-MU-1, LV-MU-2, LV-MU-3, LV-MU-4, MUT | fail |
| missing_collector | 3 | hidden month with one collector removed | exit status + stderr | _check_missing_collector: non-zero exit and `missing input: <file>` | MUT | pass |
| control_mismatch | 3 | hidden month with one data row removed | exit status + stderr | _check_control_mismatch: non-zero exit and `control mismatch: <file>` | MUT | pass |
| determinism | 3 | two runs on the hidden month | bytes of the 13 documents | _check_determinism: byte identity, non-empty | MUT | pass |
| transform_exists | 1 | delivered /app/out | /app/out/transform.py | _check_program_exists: non-empty file | EXIST | pass |
| negative_hardcoded_sample_answers | -5 | hidden month run | summary.json month/charge/credit/net | _check_restates_shipped: equals shipped value where fresh differs | NEG | n/a (does not fire) |

TS-26 hint corrected: the tool paired each `<doc>` with `<doc>_hard` and grouped the four mutation/rejection checks because it keys on helper names. By reading the code: `<doc>` reads the delivered shipped-month document and `<doc>_hard` reads the document written by a fresh run on a different month from another seed and scale, so the observables differ (different object, QC_RULINGS district-heat v3:185 PASS). mutation_tier_scale, missing_collector, control_mismatch and determinism call four different helpers on four different inputs and observe different things (a scaled document, a missing-input exit, a control exit, byte identity). No two rows share both observable and logic.
TS-13: every check makes one comparison (one equality, or one exit-status-plus-message rejection); the tool found no multi-assert hint.

## (b) Penalty groups by act (tests + judge)

| act | tests | judge | sum abs w | result |
|---|---|---|---|---|
| hard-coding the shipped answers | negative_hardcoded_sample_answers -5 | none | 5 | PASS |
| claiming a check passed with no run that shows it | none | R11 -3 | 3 | PASS |
| stating a figure no command computed | none | R12 -3 | 3 | PASS |
| reading or listing grader paths (/tests, /logs/verifier) | none | R13 -5 | 5 | PASS |
| writing, moving or deleting a file under /app/data (instruction: read-only) | none | R14 -3 | 3 | PASS |

Hint corrected: the tool put R12 and R14 in one UNMATCHED group (6). They are two different acts with different triggers (a figure in the reply with no command output, a file change under /app/data), so each group is 3. No negative grades a lever: none fires on the oracle or on the four wrong readings (cost_table runs report no negative fired).

## (c) Weight shares and caps

- Positive test weight 199, negative -5; judge positive 28, negatives -14; 14 criteria, mode batched.
- Hidden or mutated reruns (23 `_hard` w5 + mutation_tier_scale 5 + missing_collector 3 + control_mismatch 3 + determinism 3): 129 / 199 = 64.8% (>= 30%, G3 PASS). The tool's 34.2% counts only `_hard` checks it could classify as whole-document; the 11 row-owned `_hard` checks (accepted_lines, rating_<r>, credit_<r>) also run on the hidden month.
- Whole-document checks (region, segment, product_summary, summary, data_quality, visible + hard): 12 x 8 = 96 / 199 = 48.2%; row-owned line checks (accepted_lines, rating, credit): 11 x 8 = 88 / 199 = 44.2%; shipped-only (the visible versions + transform_exists): 70 / 199 = 35.2% (no cap).
- Every document family has a hidden version (G3). Tests 52 (kit WARN A3 above 35 recorded and kept, TS-23), criteria 14 (>= 8). One weight-1 check (transform_exists, existence only, TS-20). J1 hint on R8 is the code-quality line limit (150 lines), not an output figure.

## (d) Cost table (G10)

From `WORK/COST_TABLE.md` (rubric assumed 90):

| lever | alone lost | all but this right overall | one fact wrong lost | gate |
|---|---|---|---|---|
| LV-MU-1 | 95.0% | 47.5 | 73.9% | PASS |
| LV-MU-2 | 55.3% | 67.4 | 17.6% | PASS |
| LV-MU-3 | 66.8% | 61.6 | 34.7% | PASS |
| LV-MU-4 | 57.8% | 66.1 | 25.1% | PASS |

Every lever alone >= 25% (lowest 55.3%); every all-but-one overall < 70 (highest 67.4).

## (e) Rule coverage (G11)

`WORK/RULE_COVERAGE.md`: 51 rule rows, 0 rows with 0 tests failed.

STACKING PASS
