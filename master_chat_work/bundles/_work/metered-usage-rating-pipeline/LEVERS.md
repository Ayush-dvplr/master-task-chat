# LEVERS: check -> lever map (gate v3.6 harden 361674d, 28 Oct 2026; wave 2 rows kept)

Lever ids per check are the levers whose wrong reading, injected alone into solve.py, fails that
check against the real tests (`cost_table.json`, `alone` rows). Other ids: COUPLING = region
credit base; MUT = mutation or rejection path; LONG = long fresh month (P-3); LADDER = long-card fresh month (reseller tree and a 50000-tier rate card, P-1/P-3); EXIST = existence; NEG = cheating act (hard-coding shipped figures), grades no lever.

| check | weight | levers |
|---|---|---|
| accepted_lines | 3 | LV-MU-1 (noise) |
| accepted_lines_hard | 5 | LV-MU-1 (noise) |
| rating_central | 3 | LV-MU-5, LV-MU-1 (noise) |
| rating_central_hard | 5 | LV-MU-5, LV-MU-1 (noise) |
| rating_east | 3 | LV-MU-5, LV-MU-1 (noise) |
| rating_east_hard | 5 | LV-MU-5, LV-MU-1 (noise) |
| rating_north | 3 | LV-MU-5, LV-MU-1 (noise) |
| rating_north_hard | 5 | LV-MU-5, LV-MU-1 (noise) |
| rating_south | 3 | LV-MU-5, LV-MU-1 (noise) |
| rating_south_hard | 5 | LV-MU-5, LV-MU-1 (noise) |
| rating_west | 3 | LV-MU-5, LV-MU-1 (noise) |
| rating_west_hard | 5 | LV-MU-5, LV-MU-1 (noise) |
| credit_central | 3 | LV-MU-5, LV-MU-1 (noise), COUPLING |
| credit_central_hard | 5 | LV-MU-6, LV-MU-5, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| credit_east | 3 | LV-MU-5, COUPLING |
| credit_east_hard | 5 | LV-MU-6, LV-MU-5, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| credit_north | 3 | LV-MU-5, LV-MU-1 (noise), COUPLING |
| credit_north_hard | 5 | LV-MU-5, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| credit_south | 3 | LV-MU-5, LV-MU-1 (noise), COUPLING |
| credit_south_hard | 5 | LV-MU-5, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| credit_west | 3 | LV-MU-5, LV-MU-1 (noise), COUPLING |
| credit_west_hard | 5 | LV-MU-6, LV-MU-5, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| true_up_central | 3 | COUPLING |
| true_up_central_hard | 5 | LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| true_up_east | 3 | COUPLING |
| true_up_east_hard | 5 | LV-MU-3 (noise), COUPLING |
| true_up_north | 3 | LV-MU-1 (noise), COUPLING |
| true_up_north_hard | 5 | LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| true_up_south | 3 | COUPLING |
| true_up_south_hard | 5 | LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| true_up_west | 3 | COUPLING |
| true_up_west_hard | 5 | LV-MU-3 (noise), COUPLING |
| region_central | 3 | LV-MU-5, LV-MU-1 (noise), COUPLING |
| region_central_hard | 5 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| region_east | 3 | LV-MU-5, LV-MU-1 (noise), COUPLING |
| region_east_hard | 5 | LV-MU-6, LV-MU-5, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| region_north | 3 | LV-MU-5, LV-MU-1 (noise), COUPLING |
| region_north_hard | 5 | LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| region_south | 3 | LV-MU-5, LV-MU-1 (noise), COUPLING |
| region_south_hard | 5 | LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| region_west | 3 | LV-MU-5, LV-MU-1 (noise), COUPLING |
| region_west_hard | 5 | LV-MU-6, LV-MU-5, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| segment_consumer | 3 | LV-MU-5, LV-MU-1 (noise), COUPLING |
| segment_consumer_hard | 5 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| segment_corporate | 3 | LV-MU-5, LV-MU-1 (noise), COUPLING |
| segment_corporate_hard | 5 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| segment_enterprise | 3 | LV-MU-5, LV-MU-1 (noise), COUPLING |
| segment_enterprise_hard | 5 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| segment_smb | 3 | LV-MU-5, LV-MU-1 (noise), COUPLING |
| segment_smb_hard | 5 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| product_summary | 3 | LV-MU-5, LV-MU-1 (noise), COUPLING |
| product_summary_hard | 5 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| summary | 3 | LV-MU-5, LV-MU-1 (noise), COUPLING |
| summary_hard | 5 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), COUPLING |
| data_quality | 3 | LV-MU-1 (noise) |
| data_quality_hard | 5 | LV-MU-1 (noise) |
| mutation_tier_scale | 5 | LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), MUT |
| mutation_small_commitment | 3 | LV-MU-5, LV-MU-1 (noise), LV-MU-3 (noise), MUT |
| mutation_near_base_pool | 5 | LV-MU-6, LV-MU-5, LV-MU-1 (noise), LV-MU-3 (noise), MUT |
| missing_collector | 3 | MUT |
| missing_input_first_named | 3 | MUT |
| missing_reference_file | 3 | MUT |
| control_mismatch | 3 | MUT |
| determinism | 3 | MUT |
| transform_exists | 1 | EXIST |
| negative_hardcoded_sample_answers | -5 | NEG |
| long_1_finishes | 3 | LV-MU-8, LONG |
| long_1_normalized | 5 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-8, LV-MU-1 (noise), LV-MU-3 (noise), LONG |
| long_1_summary | 5 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-8, LV-MU-1 (noise), LV-MU-3 (noise), LONG |
| long_1_product_summary | 3 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-8, LV-MU-1 (noise), LV-MU-3 (noise), LONG |
| long_2_finishes | 3 | LV-MU-8, LONG |
| long_2_normalized | 5 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-8, LV-MU-1 (noise), LV-MU-3 (noise), LONG |
| long_2_summary | 5 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-8, LV-MU-1 (noise), LV-MU-3 (noise), LONG |
| long_2_product_summary | 3 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-8, LV-MU-1 (noise), LV-MU-3 (noise), LONG |
| long_3_finishes | 3 | LV-MU-8, LONG |
| long_3_normalized | 5 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-8, LV-MU-1 (noise), LV-MU-3 (noise), LONG |
| long_3_summary | 5 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-8, LV-MU-1 (noise), LV-MU-3 (noise), LONG |
| long_3_product_summary | 3 | LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-8, LV-MU-1 (noise), LV-MU-3 (noise), LONG |
| ladder_1_finishes | 3 | LV-MU-9, LV-MU-8, LADDER |
| ladder_1_normalized | 5 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_1_summary | 5 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_1_product_summary | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_1_segment_consumer | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_1_segment_corporate | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_1_segment_enterprise | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_1_segment_smb | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_2_finishes | 3 | LV-MU-9, LV-MU-8, LADDER |
| ladder_2_normalized | 5 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_2_summary | 5 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_2_product_summary | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_2_segment_consumer | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_2_segment_corporate | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_2_segment_enterprise | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_2_segment_smb | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_3_finishes | 3 | LV-MU-9, LV-MU-8, LADDER |
| ladder_3_normalized | 5 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_3_summary | 5 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_3_product_summary | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_3_segment_consumer | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_3_segment_corporate | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_3_segment_enterprise | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_3_segment_smb | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_4_finishes | 3 | LV-MU-9, LV-MU-8, LADDER |
| ladder_4_normalized | 5 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_4_summary | 5 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_4_product_summary | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_4_segment_consumer | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_4_segment_corporate | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_4_segment_enterprise | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |
| ladder_4_segment_smb | 3 | LV-MU-9, LV-MU-8, LV-MU-6, LV-MU-5, LV-MU-7, LV-MU-1 (noise), LV-MU-3 (noise), LADDER |

| lever | rule written in | weight carried | share of 295 |
|---|---|---|---|
| LV-MU-6 | rating_contract.md:164-179 Credit (second pass 176-178), 30-31 credit base, 32-33 credit pool | 104 | 35.3% |
| LV-MU-5 | rating_contract.md:24-26 billing group, 27-29 tier counter, 98-101 parent column, 152-162 Rating | 235 | 79.7% |
| LV-MU-7 | rating_contract.md:34-35 minimum, 115-117 commitments.xml, 181-191 True-up, 193-194 net | 104 | 35.3% |
| LV-MU-8 | rating_contract.md:48-49 20-second run; 24-29 billing group and tier counter on long fresh months | 48 | 16.3% |
| LV-MU-1 (noise) | rating_contract.md:72-75 north `units` (a JSON integer, written with no fraction or exponent part); 84-86 text collectors (graded noise) | 251 | 85.1% |
| LV-MU-3 (noise) | rating_contract.md:22-23 committed account (graded noise) | 157 | 53.2% |

## Levers in detail (harden round 2)

Hidden month of the tests: seed 58213, 2027-08, 1205 accounts, 7555 accepted lines; 201 accounts
carry a parent, 91 of them at depth 2 or 3 below the head of their chain (70 at depth 2, 21 at
depth 3). Credit roles: central, east and west have a pool just under the base with sub-floor
lines (323 / 358 / 344 lines whose final credit exceeds their charge); south has a base under its
pool (every counted line gets its own charge); north is the tie region (pool k/8 of the summed
charge of the held lines). True-up: central, north and south have a base under the minimum
(699 / 674 / 664 lines carry a true-up); east and west are covered. Shipped month: every parent
empty, every pool between 0.20 and 0.45 of its base, every minimum under its base, so none of
the three focal rules separates on shipped data.

### LV-MU-6 credit pool shared again across the lines that held 0.50 (H7 re-entry), new
- Rule: rating_contract.md:164-179 Credit; branch "at or below its credit pool" 169-171; branch
  "exceeds the credit pool" 172-178 with the second-pass sentence 175-177 "every cent of the
  credit pool is shared again, pool × line charge ÷ summed charge of the lines that held 0.50 or
  more, rounded half-even to 0.01, across only those lines"; glossary credit base 30-31, credit
  pool 32-33.
- Reflex reading: the second pass is the same share function called again on the survivors, so
  it re-enters the "at or below" branch when the survivors' charge fits in the pool and gives
  each survivor its own charge instead of a proportional share of every cent.
- Hidden: three regions with survivors' charge <= pool < base; one base-under-pool region; one
  tie region. Mutation `mutation_near_base_pool` sets one region's pool to base - 0.01.
- Checks failed alone: 13 (credit _hard x3, region _hard x3, segment _hard x4, product_summary_hard,
  summary_hard, mutation_near_base_pool), 65 points (26.3%); one-fact-wrong (one line) 10.1%.
- Interactions: same habit as LV-MU-7; a fresh agent that gets one right will likely get both.

### LV-MU-5 billing group follows the parent chain to its top (H6 + recursive definition), rewritten
- Rule: rating_contract.md:24-26 "the account itself when its parent column in accounts.csv is
  empty, and otherwise the billing group of the account named in its parent column"; 27-29 tier
  counter; 97-100 accounts.csv `parent` ("empty or the account_id of another account in the file",
  the one-level sentence deleted); 151-161 Rating.
- Reflex reading: the group is the parent named on the row (one level), as the probe-2 program
  wrote (`canon(parent) or account`).
- Hidden: chains up to four deep (91 accounts at depth 2-3), parent ids 50% non-canonical.
- Checks failed alone: 27 (rating, credit, true_up, region _hard, segment _hard, product_summary_hard,
  summary_hard, mutation_tier_scale), 133 points (53.8%); one-fact-wrong (one depth-2 account)
  53.8% because one moved tier changes charges that feed every region credit base and true-up.
- Interactions: a tier change moves a charge, which moves the region credit base (COUPLING) and so
  every credit and true-up of that region; its failures cover those of LV-MU-6 and LV-MU-7.

### LV-MU-7 true-up shortfall shared again across the lines that held 0.50 (H7 re-entry), new
- Rule: rating_contract.md:34-35 glossary minimum; 115-117 commitments.xml `minimum`; 181-191
  True-up ("in proportion to charge, rounded half-even to 0.01"; "every cent of the shortfall is
  shared again, in proportion to charge, rounded half-even to 0.01, across only the lines that
  held 0.50 or more"); 192-193 net.
- Reflex reading: the second pass recomputes the shortfall from the survivors' charge (minimum
  minus kept charge) instead of sharing the same shortfall again.
- Hidden: three regions under their minimum, each with sub-floor lines; mutation
  `mutation_small_commitment` puts one region's minimum one cent above its base.
- Checks failed alone: 13 (true_up _hard x3, region _hard x3, segment _hard x4,
  product_summary_hard, summary_hard, mutation_tier_scale), 65 points (26.3%); one-fact-wrong
  (one line) 12.1%.

### Graded noise: LV-MU-1 (north units JSON integers), LV-MU-3 (committed account = accounts.csv plan)
Rules kept as written in round 1; the probe-2 program implements both and the r2 fuzz found 0%
differing, so neither is counted toward the three levers. LV-MU-2 and LV-MU-4 stay graded noise.

### LV-MU-8 billing group on long fresh months within the 20-second run (P-3, wave 2), new
- Rule: rating_contract.md:48-49 "Every run of the program finishes within 20 seconds." (the only
  new sentence); the figures are the ones the contract already defines: 24-26 billing group, 27-29
  tier counter, 151-161 Rating, 163-178 Credit, 180-190 True-up.
- Reflex reading: resolve each account's billing group by walking its parent column to the top
  again for every account (the probe-3 program, the round-2 solve.py), or for every line.
- Hidden: three long fresh months (seeds 58213*31+1..3; 76005/80005/84005 accounts, 61459/66290/
  70927 accepted lines) with one reseller tree each (11000-12000 sub-resellers with customers and
  side branches, deepest account 9000-10200 levels, half the parent ids in a variant spelling).
  Shipped and the old hidden month keep groups of at most 3 levels.
- Checks failed alone: the 12 `long_k_*` checks (48 points, 16.3%): the run does not finish within
  20 seconds, so no document is graded. One level up (LV-MU-5) or the parent text as written also
  fail the long documents (wrong document, 9 of 48 kept).

Checks: 76, positive weight 295, negative weight -5 (test channel; one cheating act).


### LV-MU-9 tier lookup on long-card fresh months within the 20-second run (P-1, gate v3.6), new
- Rule: no new sentence. rating_contract.md:111-114 (rate_card.json `tiers` list, `from` cumulative units),
  153-156 (the tier is the one with the largest `from` <= tier counter), 48-49 (every run within 20 seconds).
  The contract states no bound on the number of tiers (no size bound, no method words).
- Reflex reading: pick the tier by scanning the tier list for every line (forward with or without break,
  reverse, max over the starts). Measured in Docker on a 50000-tier card: 12.7 to over 60 s per month; every
  blind program (c60b, 9d66, d576) and the probe-3 program scan; the reference bisects (about 3 s).
- Hidden: four long-card fresh months (seeds 58213*37+1..4; LADDER_SHAPES 13000-15000 collector rows,
  76000-84000 accounts, 11000-12000 sub-resellers; 50000 tiers per product, starts on the month's own
  tier-counter quantiles from their own RNG Random(seed*6271+53)), so the memo walk and the tier lookup
  must both be fast. Shipped card keeps 3 tiers per product: every plain program is exact and fast on it.
- Checks: ladder_<k>_finishes w3, normalized w5, summary w5, product_summary w3, segment_<s> w3 x4 = 28
  per month, 112 in all; with LV-MU-8 (48) 160/407 = 39.3% of positive test points.
- Loss kind: v3.5 hidden-scale TIMEOUT (no shipped input slow, stated 20 s limit, each month its own
  program call, losses inside the ladder checks only); label and greedy solvers lose by WRONG documents.

## P12 fix a395eb2 (29 Oct 2026)

- Checks 110, positive weight 413 (was 108 / 407), negative -5. Added `missing_input_first_named` (3) and
  `missing_reference_file` (3), family MUT, no lever (refusal path). Lever weights unchanged; shares of 413:
  LV-MU-8 + LV-MU-9 160/413 = 38.7%.
- rating_contract.md:74-75 north `units` now "(a JSON integer, written with no fraction or exponent part)";
  contract lines after 74 moved down by one (references above updated). LV-MU-1 stays graded noise; the clause
  removes the second reading QC found (12.0 and 1e2 as integers), master direction G01-1.
- `_run` runs the program in its own session under one lock and kills its group and every leftover
  process of the dropped uid on every exit path (G03-3); LV-MU-8/LV-MU-9 finish checks can no longer be
  forged by a detached child.

## P12 fix f65cab8 (29 Oct 2026)

- Checks 112, positive weight 419 (was 110 / 413), negative -5. Added `missing_references_first_in_list` (3)
  and `missing_collectors_first_in_list` (3), family MUT, no lever (refusal path, QC v2 G05-1 AL-27).
  Lever weights unchanged; shares of 419: LV-MU-8 + LV-MU-9 160/419 = 38.2%.

## P12 fix d21576c (29 Oct 2026)

- Checks 113, positive weight 422 (was 112 / 419), negative -5. Added `missing_adjacent_pairs_in_list_order` (3),
  family MUT, no lever (refusal path, QC v3 G05-1 AL-27: all ten neighbouring pairs of the contract input list).
  Lever weights unchanged; shares of 422: LV-MU-8 + LV-MU-9 160/422 = 37.9%.

## P12 fix 1f91f8f (31 Oct 2026)

- QL round 1 (triage fc64da5). Checks 113, positive 422, negative -5, weights unchanged.
- F-1: every test cache key built under its own lock (`_key_lock`), tests/test_output.py:1027-1036; grading unchanged.
- F-2: run limit 15 -> 20 seconds (tests :29, seven long/ladder descriptions, rating_contract.md:49, TRUTH).
  Single-lever losses re-run on the fixed tests (ql1/trap_ql1.json): LV-MU-5 335, LV-MU-6 204, LV-MU-7 204,
  LV-MU-8 160, LV-MU-9 112, noise LV-MU-1 351, LV-MU-3 257; all equal to before (d215/trap_d215.json).
  a4 program 262/422 before and after (all 7 long/ladder months: no result within 20 seconds).
- M-2: instruction.md:28 reworded (this month graded as delivered in /app/out); no lever touched.
