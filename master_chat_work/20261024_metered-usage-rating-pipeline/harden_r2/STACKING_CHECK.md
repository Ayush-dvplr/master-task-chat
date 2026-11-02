# STACKING_CHECK: metered-usage-rating-pipeline (harden round 2, e2dc50b)

Started from `tools/stacking_check.py` on the AFTER bundle (raw output: `stacking_check_tool_output.txt`); each hint was checked against `tests/test_output.py` and the measured cost table (`WORK/cost_table.json`, 25 Oct 01:07 IST).

## (a) Test rows

Lever columns = measured failing tests of each `alone` run in the cost table (solve.py with one reflex reading: LV-MU-6 pass 2 re-enters the own-charge branch, LV-MU-5 one-level billing group, LV-MU-7 shortfall recomputed from held lines). Noise columns = `noise alone` runs (LV-MU-1 lenient north units, LV-MU-3 credit base by plan in force); they do not count toward the levers. Reflex program column = the probe-2 agent program (OUT/agent_program/transform.py) run on the AFTER tests.

| test | w | input | observable | decisive logic | levers whose misread fails it | reflex program |
|---|---|---|---|---|---|---|
| accepted_lines | 3 | delivered /app/out, shipped month | normalized.jsonl: ordered (record_id, region, timestamp, account_id, product, units) | _check_accepted_lines: ordered list equality | (noise LV-MU-1) | pass |
| accepted_lines_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl: ordered (record_id, region, timestamp, account_id, product, units) | _check_accepted_lines: ordered list equality | (noise LV-MU-1) | pass |
| rating_central | 3 | delivered /app/out, shipped month | normalized.jsonl rows of central: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality | (noise LV-MU-1) | pass |
| rating_central_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of central: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality | LV-MU-5, (noise LV-MU-1) | fail |
| rating_east | 3 | delivered /app/out, shipped month | normalized.jsonl rows of east: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality | (noise LV-MU-1) | pass |
| rating_east_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of east: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality | LV-MU-5, (noise LV-MU-1) | fail |
| rating_north | 3 | delivered /app/out, shipped month | normalized.jsonl rows of north: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality | (noise LV-MU-1) | pass |
| rating_north_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of north: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality | LV-MU-5, (noise LV-MU-1) | fail |
| rating_south | 3 | delivered /app/out, shipped month | normalized.jsonl rows of south: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality | (noise LV-MU-1) | pass |
| rating_south_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of south: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality | LV-MU-5, (noise LV-MU-1) | fail |
| rating_west | 3 | delivered /app/out, shipped month | normalized.jsonl rows of west: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality | (noise LV-MU-1) | pass |
| rating_west_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of west: segment, tier, unit_rate, charge by record_id | _check_rating: dict-by-id equality | LV-MU-5, (noise LV-MU-1) | fail |
| credit_central | 3 | delivered /app/out, shipped month | normalized.jsonl rows of central: plan, credit by record_id | _check_credit: dict-by-id equality | (noise LV-MU-1) | fail |
| credit_central_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of central: plan, credit by record_id | _check_credit: dict-by-id equality | LV-MU-6, LV-MU-5, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| credit_east | 3 | delivered /app/out, shipped month | normalized.jsonl rows of east: plan, credit by record_id | _check_credit: dict-by-id equality | - | fail |
| credit_east_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of east: plan, credit by record_id | _check_credit: dict-by-id equality | LV-MU-6, LV-MU-5, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| credit_north | 3 | delivered /app/out, shipped month | normalized.jsonl rows of north: plan, credit by record_id | _check_credit: dict-by-id equality | (noise LV-MU-1) | fail |
| credit_north_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of north: plan, credit by record_id | _check_credit: dict-by-id equality | LV-MU-5, (noise LV-MU-1, LV-MU-3) | fail |
| credit_south | 3 | delivered /app/out, shipped month | normalized.jsonl rows of south: plan, credit by record_id | _check_credit: dict-by-id equality | (noise LV-MU-1) | fail |
| credit_south_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of south: plan, credit by record_id | _check_credit: dict-by-id equality | LV-MU-5, (noise LV-MU-1, LV-MU-3) | fail |
| credit_west | 3 | delivered /app/out, shipped month | normalized.jsonl rows of west: plan, credit by record_id | _check_credit: dict-by-id equality | - | fail |
| credit_west_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of west: plan, credit by record_id | _check_credit: dict-by-id equality | LV-MU-6, LV-MU-5, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| true_up_central | 3 | delivered /app/out, shipped month | normalized.jsonl rows of central: true_up by record_id | _check_true_up: dict-by-id equality | - | fail |
| true_up_central_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of central: true_up by record_id | _check_true_up: dict-by-id equality | LV-MU-5, LV-MU-7, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| true_up_east | 3 | delivered /app/out, shipped month | normalized.jsonl rows of east: true_up by record_id | _check_true_up: dict-by-id equality | - | fail |
| true_up_east_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of east: true_up by record_id | _check_true_up: dict-by-id equality | (noise LV-MU-3) | fail |
| true_up_north | 3 | delivered /app/out, shipped month | normalized.jsonl rows of north: true_up by record_id | _check_true_up: dict-by-id equality | (noise LV-MU-1) | fail |
| true_up_north_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of north: true_up by record_id | _check_true_up: dict-by-id equality | LV-MU-5, LV-MU-7, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| true_up_south | 3 | delivered /app/out, shipped month | normalized.jsonl rows of south: true_up by record_id | _check_true_up: dict-by-id equality | - | fail |
| true_up_south_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of south: true_up by record_id | _check_true_up: dict-by-id equality | LV-MU-5, LV-MU-7, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| true_up_west | 3 | delivered /app/out, shipped month | normalized.jsonl rows of west: true_up by record_id | _check_true_up: dict-by-id equality | - | fail |
| true_up_west_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | normalized.jsonl rows of west: true_up by record_id | _check_true_up: dict-by-id equality | (noise LV-MU-3) | fail |
| region_central | 3 | delivered /app/out, shipped month | region_central.json whole document | _check_document: parsed JSON equality | (noise LV-MU-1) | fail |
| region_central_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | region_central.json whole document | _check_document: parsed JSON equality | LV-MU-6, LV-MU-5, LV-MU-7, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| region_east | 3 | delivered /app/out, shipped month | region_east.json whole document | _check_document: parsed JSON equality | (noise LV-MU-1) | fail |
| region_east_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | region_east.json whole document | _check_document: parsed JSON equality | LV-MU-6, LV-MU-5, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| region_north | 3 | delivered /app/out, shipped month | region_north.json whole document | _check_document: parsed JSON equality | (noise LV-MU-1) | fail |
| region_north_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | region_north.json whole document | _check_document: parsed JSON equality | LV-MU-5, LV-MU-7, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| region_south | 3 | delivered /app/out, shipped month | region_south.json whole document | _check_document: parsed JSON equality | (noise LV-MU-1) | fail |
| region_south_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | region_south.json whole document | _check_document: parsed JSON equality | LV-MU-5, LV-MU-7, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| region_west | 3 | delivered /app/out, shipped month | region_west.json whole document | _check_document: parsed JSON equality | (noise LV-MU-1) | fail |
| region_west_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | region_west.json whole document | _check_document: parsed JSON equality | LV-MU-6, LV-MU-5, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| segment_consumer | 3 | delivered /app/out, shipped month | segment_consumer.json whole document | _check_document: parsed JSON equality | (noise LV-MU-1) | fail |
| segment_consumer_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | segment_consumer.json whole document | _check_document: parsed JSON equality | LV-MU-6, LV-MU-5, LV-MU-7, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| segment_corporate | 3 | delivered /app/out, shipped month | segment_corporate.json whole document | _check_document: parsed JSON equality | (noise LV-MU-1) | fail |
| segment_corporate_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | segment_corporate.json whole document | _check_document: parsed JSON equality | LV-MU-6, LV-MU-5, LV-MU-7, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| segment_enterprise | 3 | delivered /app/out, shipped month | segment_enterprise.json whole document | _check_document: parsed JSON equality | (noise LV-MU-1) | fail |
| segment_enterprise_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | segment_enterprise.json whole document | _check_document: parsed JSON equality | LV-MU-6, LV-MU-5, LV-MU-7, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| segment_smb | 3 | delivered /app/out, shipped month | segment_smb.json whole document | _check_document: parsed JSON equality | (noise LV-MU-1) | fail |
| segment_smb_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | segment_smb.json whole document | _check_document: parsed JSON equality | LV-MU-6, LV-MU-5, LV-MU-7, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| product_summary | 3 | delivered /app/out, shipped month | product_summary.json whole document | _check_document: parsed JSON equality | (noise LV-MU-1) | fail |
| product_summary_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | product_summary.json whole document | _check_document: parsed JSON equality | LV-MU-6, LV-MU-5, LV-MU-7, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| summary | 3 | delivered /app/out, shipped month | summary.json whole document | _check_document: parsed JSON equality | (noise LV-MU-1) | fail |
| summary_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | summary.json whole document | _check_document: parsed JSON equality | LV-MU-6, LV-MU-5, LV-MU-7, COUPLING, (noise LV-MU-1, LV-MU-3) | fail |
| data_quality | 3 | delivered /app/out, shipped month | data_quality.json whole document | _check_document: parsed JSON equality | (noise LV-MU-1) | pass |
| data_quality_hard | 5 | fresh hidden month (seed 58213, nobody, renamed dir, foreign cwd) | data_quality.json whole document | _check_document: parsed JSON equality | (noise LV-MU-1) | pass |
| mutation_tier_scale | 5 | hidden month, tier thresholds x1.0375 up, rows shuffled | product_summary.json of the scaled run | _check_tier_scale: parsed JSON equality | LV-MU-5, LV-MU-7, MUT, (noise LV-MU-1, LV-MU-3) | fail |
| mutation_small_commitment | 3 | hidden month, one region pool 1.00 and minimum = base + 1.00 (seeded region) | region_<r>.json of that run | _check_small_commitment: parsed JSON equality | LV-MU-5, MUT, (noise LV-MU-1, LV-MU-3) | fail |
| mutation_near_base_pool | 5 | hidden month, other seeded region pool = credit base - 0.01 | region_<r>.json of that run | _check_near_base_pool: parsed JSON equality | LV-MU-6, LV-MU-5, MUT, (noise LV-MU-1, LV-MU-3) | fail |
| missing_collector | 3 | hidden month with one collector removed | exit status + stderr | non-zero exit and `missing input: <file>` | MUT | pass |
| control_mismatch | 3 | hidden month with one data row removed | exit status + stderr | non-zero exit and `control mismatch: <file>` | MUT | pass |
| determinism | 3 | two runs on the hidden month | bytes of the 14 documents | byte identity | MUT | pass |
| transform_exists | 1 | delivered /app/out | /app/out/transform.py | non-empty file | - | pass |
| negative_hardcoded_sample_answers | -5 | hidden month run | summary.json month/charge/credit/net | equals shipped value where fresh differs | - | n/a (does not fire) |

TS-26 hint corrected: the tool pairs `<doc>` with `<doc>_hard` and groups the six mutation/exit checks because it keys on helper names. By reading the code, `<doc>` reads the delivered shipped-month document and `<doc>_hard` reads the document of a fresh run on another month, seed and scale, so the observables differ (QC_RULINGS district-heat v3:185 PASS). The six extras call six helpers on six different inputs: tier-scaled month, small-commitment month, near-base-pool month, missing collector, control mismatch, double run. No two rows share both observable and logic.
TS-13: every check makes one comparison; no multi-assert hint. Line families own disjoint keys: rating (segment, tier, unit_rate, charge), credit (plan, credit), true_up (true_up); net is graded only inside the documents.

## (b) Penalty groups by act (tests + judge)

| act | tests | judge | sum abs w | result |
|---|---|---|---|---|
| hard-coding the shipped answers | negative_hardcoded_sample_answers -5 | none | 5 | PASS |
| claiming a check passed with no rerun that shows it | none | R11 -3 | 3 | PASS |
| stating a figure no command computed | none | R12 -3 | 3 | PASS |
| opening grader paths (/tests, /logs/verifier) | none | R13 -5 | 5 | PASS |
| changing a file under /app/data | none | R14 -3 | 3 | PASS |

Hint corrected: the tool puts R12 and R14 in one UNMATCHED group (6); they are two acts with different triggers, so each group is 3. No negative grades a lever; no cost-table run fires a negative (`fired` empty in every row).

## (c) Weight shares and caps

- Positive test weight 247, negative -5; 64 checks; reward.toml 0.5/247 tests, 0.5/34 judge. Judge 16 criteria, positive 34, negatives -14, mode batched.
- Hidden or mutated reruns: 162 / 247 = 65.6% (G3 >= 30% PASS).
- Whole-document checks 96 / 247 = 38.9%; row-owned line checks 128 / 247 = 51.8%; shipped-only 85 / 247 = 34.4% (no cap); mutation 13 / 247 = 5.3%.
- One weight-1 check (transform_exists, existence only; TS-20). Tests 64 >= 10, criteria 16 >= 8.

## (d) Cost table (G10), measured on the AFTER tests

From `WORK/COST_TABLE.md` (overall at the measured probe-2 judge 70.59):

| lever | alone lost | one fact wrong lost | this right, other two wrong: tests / overall | gate |
|---|---|---|---|---|
| LV-MU-6 credit re-share (H7) | 26.3% (13 tests) | 10.1% (5) | 46.2 / 58.4 | PASS alone; one-fact under 25%, CL-4 whole-document sentence |
| LV-MU-5 recursive billing group (H6) | 53.8% (27) | 53.8% (27, cascade through tier -> charge -> credit base) | 61.5 / 66.1 | PASS |
| LV-MU-7 true-up re-share (H7) | 26.3% (13) | 12.1% (6) | 46.2 / 58.4 | PASS alone; one-fact under 25%, CL-4 whole-document sentence |

A and C use the same habit (master note 3): A+C wrong together with B right = all-but LV-MU-5 = 38.5% lost (tests 61.5). All three wrong: 53.8% lost (B's failures are a superset of A's and C's). Noise (graded, not levers): LV-MU-1 alone 84.6% lost, LV-MU-3 alone 47.8%.
COUPLING: the region credit base (glossary 30-31) feeds both the Credit section (162-177) and the True-up section (179-189); every LV-MU-5 tier change moves the base, so LV-MU-5 lands on every A and C document.

## (e) Rule coverage (G11)

`WORK/RULE_COVERAGE.md`: 64 rule rows, 0 rows with 0 tests failed ("Rules uncovered: 0 of 64").

## Reflex gate (LEVER_RULES section 6)

Probe-2 agent program on the AFTER tests (local rewardkit stub, data = AFTER shipped data): 41 / 247 = 0.166 (<= 0.20, PASS by the letter). Caveat: it fails every credit/true_up/document check partly because it has no `true_up` key at all, so like round 1 this mostly measures new contract surface. The rule-aware advisory figure is the cost-table `all wrong` run (solve.py with the three reflex readings): 114 / 247 = 0.462, above 0.20; the 85 shipped-only points pass under every reflex reading because no separating case is shipped (W5). Per master note 5, no fourth lever was added.

STACKING PASS
