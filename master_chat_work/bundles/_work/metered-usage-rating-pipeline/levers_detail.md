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
- Rule: rating_contract.md:163-178 Credit; branch "at or below its credit pool" 168-170; branch
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
- Rule: rating_contract.md:34-35 glossary minimum; 114-116 commitments.xml `minimum`; 180-190
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

### LV-MU-8 billing group on long fresh months within the 15-second run (P-3, wave 2), new
- Rule: rating_contract.md:48-49 "Every run of the program finishes within 15 seconds." (the only
  new sentence); the figures are the ones the contract already defines: 24-26 billing group, 27-29
  tier counter, 151-161 Rating, 163-178 Credit, 180-190 True-up.
- Reflex reading: resolve each account's billing group by walking its parent column to the top
  again for every account (the probe-3 program, the round-2 solve.py), or for every line.
- Hidden: three long fresh months (seeds 58213*31+1..3; 76005/80005/84005 accounts, 61459/66290/
  70927 accepted lines) with one reseller tree each (11000-12000 sub-resellers with customers and
  side branches, deepest account 9000-10200 levels, half the parent ids in a variant spelling).
  Shipped and the old hidden month keep groups of at most 3 levels.
- Checks failed alone: the 12 `long_k_*` checks (48 points, 16.3%): the run does not finish within
  15 seconds, so no document is graded. One level up (LV-MU-5) or the parent text as written also
  fail the long documents (wrong document, 9 of 48 kept).
