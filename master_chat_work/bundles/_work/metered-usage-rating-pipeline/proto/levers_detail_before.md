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
- Rule: rating_contract.md:162-177 Credit; branch "at or below its credit pool" 167-169; branch
  "exceeds the credit pool" 171-177 with the second-pass sentence 174-176 "every cent of the
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
  counter; 96-99 accounts.csv `parent` ("empty or the account_id of another account in the file",
  the one-level sentence deleted); 152-160 Rating.
- Reflex reading: the group is the parent named on the row (one level), as the probe-2 program
  wrote (`canon(parent) or account`).
- Hidden: chains up to four deep (91 accounts at depth 2-3), parent ids 50% non-canonical.
- Checks failed alone: 27 (rating, credit, true_up, region _hard, segment _hard, product_summary_hard,
  summary_hard, mutation_tier_scale), 133 points (53.8%); one-fact-wrong (one depth-2 account)
  53.8% because one moved tier changes charges that feed every region credit base and true-up.
- Interactions: a tier change moves a charge, which moves the region credit base (COUPLING) and so
  every credit and true-up of that region; its failures cover those of LV-MU-6 and LV-MU-7.

### LV-MU-7 true-up shortfall shared again across the lines that held 0.50 (H7 re-entry), new
- Rule: rating_contract.md:34-35 glossary minimum; 113-115 commitments.xml `minimum`; 179-189
  True-up ("in proportion to charge, rounded half-even to 0.01"; "every cent of the shortfall is
  shared again, in proportion to charge, rounded half-even to 0.01, across only the lines that
  held 0.50 or more"); 191-192 net.
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
