# stacking_check: metered-usage-rating-pipeline

tests/test_output.py: 76 checks, positive total 295, negatives -5; judge: 15 criteria, positive 28, mode batched. Static hints only; confirm by reading the code.

## 1. Test -> observable map

| test | w | class (basis) | observable (literals) | logic (helpers) | asserts/and-cmp |
|---|---|---|---|---|---|
| accepted_lines | 3 | shipped_only (artifact/shipped wording) | visible | _holds, _check_accepted_lines | 0/0 |
| accepted_lines_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard | _holds, _check_accepted_lines | 0/0 |
| rating_central | 3 | shipped_only (artifact/shipped wording) | visible, central | _holds, _check_rating | 0/0 |
| rating_central_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard, central | _holds, _check_rating | 0/0 |
| rating_east | 3 | shipped_only (artifact/shipped wording) | visible, east | _holds, _check_rating | 0/0 |
| rating_east_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard, east | _holds, _check_rating | 0/0 |
| rating_north | 3 | shipped_only (artifact/shipped wording) | visible, north | _holds, _check_rating | 0/0 |
| rating_north_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard, north | _holds, _check_rating | 0/0 |
| rating_south | 3 | shipped_only (artifact/shipped wording) | visible, south | _holds, _check_rating | 0/0 |
| rating_south_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard, south | _holds, _check_rating | 0/0 |
| rating_west | 3 | shipped_only (artifact/shipped wording) | visible, west | _holds, _check_rating | 0/0 |
| rating_west_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard, west | _holds, _check_rating | 0/0 |
| credit_central | 3 | shipped_only (artifact/shipped wording) | visible, central | _holds, _check_credit | 0/0 |
| credit_central_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard, central | _holds, _check_credit | 0/0 |
| credit_east | 3 | shipped_only (artifact/shipped wording) | visible, east | _holds, _check_credit | 0/0 |
| credit_east_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard, east | _holds, _check_credit | 0/0 |
| credit_north | 3 | shipped_only (artifact/shipped wording) | visible, north | _holds, _check_credit | 0/0 |
| credit_north_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard, north | _holds, _check_credit | 0/0 |
| credit_south | 3 | shipped_only (artifact/shipped wording) | visible, south | _holds, _check_credit | 0/0 |
| credit_south_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard, south | _holds, _check_credit | 0/0 |
| credit_west | 3 | shipped_only (artifact/shipped wording) | visible, west | _holds, _check_credit | 0/0 |
| credit_west_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard, west | _holds, _check_credit | 0/0 |
| true_up_central | 3 | shipped_only (artifact/shipped wording) | visible, central | _holds, _check_true_up | 0/0 |
| true_up_central_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard, central | _holds, _check_true_up | 0/0 |
| true_up_east | 3 | shipped_only (artifact/shipped wording) | visible, east | _holds, _check_true_up | 0/0 |
| true_up_east_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard, east | _holds, _check_true_up | 0/0 |
| true_up_north | 3 | shipped_only (artifact/shipped wording) | visible, north | _holds, _check_true_up | 0/0 |
| true_up_north_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard, north | _holds, _check_true_up | 0/0 |
| true_up_south | 3 | shipped_only (artifact/shipped wording) | visible, south | _holds, _check_true_up | 0/0 |
| true_up_south_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard, south | _holds, _check_true_up | 0/0 |
| true_up_west | 3 | shipped_only (artifact/shipped wording) | visible, west | _holds, _check_true_up | 0/0 |
| true_up_west_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | hard, west | _holds, _check_true_up | 0/0 |
| region_central | 3 | shipped_only (artifact/shipped wording) | region_central.json | _holds, _check_document | 0/0 |
| region_central_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | region_central.json | _holds, _check_document | 0/0 |
| region_east | 3 | shipped_only (artifact/shipped wording) | region_east.json | _holds, _check_document | 0/0 |
| region_east_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | region_east.json | _holds, _check_document | 0/0 |
| region_north | 3 | shipped_only (artifact/shipped wording) | region_north.json | _holds, _check_document | 0/0 |
| region_north_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | region_north.json | _holds, _check_document | 0/0 |
| region_south | 3 | shipped_only (artifact/shipped wording) | region_south.json | _holds, _check_document | 0/0 |
| region_south_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | region_south.json | _holds, _check_document | 0/0 |
| region_west | 3 | shipped_only (artifact/shipped wording) | region_west.json | _holds, _check_document | 0/0 |
| region_west_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | region_west.json | _holds, _check_document | 0/0 |
| segment_consumer | 3 | shipped_only (artifact/shipped wording) | segment_consumer.json | _holds, _check_document | 0/0 |
| segment_consumer_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | segment_consumer.json | _holds, _check_document | 0/0 |
| segment_corporate | 3 | shipped_only (artifact/shipped wording) | segment_corporate.json | _holds, _check_document | 0/0 |
| segment_corporate_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | segment_corporate.json | _holds, _check_document | 0/0 |
| segment_enterprise | 3 | shipped_only (artifact/shipped wording) | segment_enterprise.json | _holds, _check_document | 0/0 |
| segment_enterprise_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | segment_enterprise.json | _holds, _check_document | 0/0 |
| segment_smb | 3 | shipped_only (artifact/shipped wording) | segment_smb.json | _holds, _check_document | 0/0 |
| segment_smb_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | segment_smb.json | _holds, _check_document | 0/0 |
| product_summary | 3 | shipped_only (artifact/shipped wording) | product_summary.json | _holds, _check_document | 0/0 |
| product_summary_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | product_summary.json | _holds, _check_document | 0/0 |
| summary | 3 | shipped_only (artifact/shipped wording) | summary.json | _holds, _check_document | 0/0 |
| summary_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | summary.json | _holds, _check_document | 0/0 |
| data_quality | 3 | shipped_only (artifact/shipped wording) | data_quality.json | _holds, _check_document | 0/0 |
| data_quality_hard | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | data_quality.json | _holds, _check_document | 0/0 |
| mutation_tier_scale | 5 | mutation (mutation in name or description lead) | %s%r: %s | - | 0/0 |
| mutation_small_commitment | 3 | mutation (mutation in name or description lead) | %s%r: %s | - | 0/0 |
| mutation_near_base_pool | 5 | mutation (mutation in name or description lead) | %s%r: %s | - | 0/0 |
| missing_collector | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | %s%r: %s | - | 0/0 |
| control_mismatch | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | %s%r: %s | - | 0/0 |
| determinism | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | %s%r: %s | - | 0/0 |
| transform_exists | 1 | shipped_only (artifact/shipped wording) | /app/out/transform.py exists and is not empty. | _holds, _check_program_exists | 0/0 |
| negative_hardcoded_sample_answers | -5 | negative (weight < 0 or negative_ name) | %s%r: %s | - | 0/0 |
| long_1_finishes | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | %s%r: %s | - | 0/0 |
| long_1_normalized | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | normalized.jsonl | _holds, _check_long_document | 0/0 |
| long_1_summary | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | summary.json | _holds, _check_long_document | 0/0 |
| long_1_product_summary | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | product_summary.json | _holds, _check_long_document | 0/0 |
| long_2_finishes | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | %s%r: %s | - | 0/0 |
| long_2_normalized | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | normalized.jsonl | _holds, _check_long_document | 0/0 |
| long_2_summary | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | summary.json | _holds, _check_long_document | 0/0 |
| long_2_product_summary | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | product_summary.json | _holds, _check_long_document | 0/0 |
| long_3_finishes | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | %s%r: %s | - | 0/0 |
| long_3_normalized | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | normalized.jsonl | _holds, _check_long_document | 0/0 |
| long_3_summary | 5 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | summary.json | _holds, _check_long_document | 0/0 |
| long_3_product_summary | 3 | hidden_rows (row-owned check on hidden/fresh inputs (_hard, trap_, fresh)) | product_summary.json | _holds, _check_long_document | 0/0 |

TS-26 duplicate candidates (same observable AND same logic): region_central = region_central_hard; region_east = region_east_hard; region_north = region_north_hard; region_south = region_south_hard; region_west = region_west_hard; segment_consumer = segment_consumer_hard; segment_corporate = segment_corporate_hard; segment_enterprise = segment_enterprise_hard; segment_smb = segment_smb_hard; product_summary = product_summary_hard; summary = summary_hard; data_quality = data_quality_hard; mutation_tier_scale = mutation_small_commitment = mutation_near_base_pool = missing_collector = control_mismatch = determinism = long_1_finishes = long_2_finishes = long_3_finishes; long_1_normalized = long_2_normalized = long_3_normalized; long_1_summary = long_2_summary = long_3_summary; long_1_product_summary = long_2_product_summary = long_3_product_summary

## 2. TS-13 multi-assert hints

- none

## 3. AL-28 penalty groups (tests + judge, |w| <= 5 per act)

| act | tests | judge | sum |w| | |
|---|---|---|---|---|
| hardcoding the shipped answers | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| claims a check passed that its output contradicts (honesty) | - | N1 -3 | 3 | PASS |
| UNMATCHED act (name it by hand) | - | N2 -5, N3 -3, N5 -3 | 11 | FAIL |
| naming or reading grader files | - | N4 -5 | 5 | PASS |

## 4. Weight shares (of positive test weight)

- whole_doc: 0 (0.0%)
- format_hidden: 0 (0.0%)
- hidden_rows: 197 (66.8%)
- isolated: 0 (0.0%)
- mutation: 13 (4.4%)
- shipped_only: 85 (28.8%)
- G3: hidden or mutated reruns 71.2% (>= 30%); isolated+mutation 4.4%, whole-document 0.0%, shipped-only 28.8% (info, no cap)

## 5. Caps and weights

- tests 76, criteria 15 (no cap; kit floors 10 / 8)
- weight-1 checks (TS-20: never on a core check): transform_exists
- judge J1 hints (criterion quotes a figure): B6
- judge J2 conduct criteria: none

## Verdict hints

- TS-26 duplicate candidates: 16 group(s): CHECK BY HAND
- AL-28 groups <= 5: FAIL
- G3 hidden or mutated reruns >= 30% (LEVER_RULES 24 Oct 13:15): 71.2% PASS
- G3 isolated / shipped-only (info, no cap): 4.4% / 28.8%
- tests >= 10 (no cap): 76 PASS
- criteria >= 8 (no cap): 15 PASS
- judge mode batched: batched

## Hints corrected by reading the code (09963d3, 27 Oct)

- AL-28 "UNMATCHED act" N2 -5, N3 -3, N5 -3 is three different acts, not one: N2 rules on a final-reply sentence that states a figure as the content of a delivered /app/out document (judge.toml N2); N3 rules on a sentence that states a count of what is in /app/data files and its text excludes check reports and /app/out content (N3), so one sentence fires at most one of N1, N2, N3; N5 rules on a file change under /app/data, not on any sentence. Largest single act: N4 -5 or N2 -5. PASS by hand.
- TS-26 16 groups (visible = _hard, long_k doc = long_j doc): same check body, different inputs (shipped month, hidden month seed 58213, long fresh months k = 1..3 with own seeds). Each owns its corpus; not duplicates. Body sharing is the pre-existing pattern for the visible/_hard pairs.
- long_k_finishes is classed hidden_rows with literal "%s%r: %s": it is the feasibility check (exit 0 within 15 s, every document written), kept separate from the whole-document checks (G1, TS-13). Weight 3, not 1 (TS-20).
- Weight-1 check transform_exists is not a core check (unchanged since r1).
- J1 hint on B6: the figure is the 150-line function bound of the code-quality criterion, not an output figure. No criterion quotes a delivered value.
- Long fresh-month share: 48 of 295 positive points (16.3%), hidden or mutated reruns 71.2% (G3).
