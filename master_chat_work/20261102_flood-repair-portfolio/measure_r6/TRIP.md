# TRIP — flood-repair-portfolio measure r6 (board 2939ad0)

P = Output_RFP/.../claude-opus-5/run_1/artifacts/app/out/derive_report.py (933 lines,
sha256 e2f9460ff73a883b9c93a085a56ebee619a459e1bd94edbe3643a7955a397b86). Every master line confirmed by read.

## P (paid attempt 4) budget path
- P:23 SHARED_LIMIT = 4; P:24 BOOK_BUDGET = 13.0; P:25 ROUND_BUDGET = 4.0.
- P:29 class Timeout; P:36-37 set_book_budget; P:40-43 start_round_budget = min(book limit, now+s);
  P:46-49 check_deadline raises Timeout past the round limit.
- P:301-303 STATE_CAP 1,000,000 / LEAF_CAP 120,000 / COMBO_CAP 256.
- P:345-359 choose: capped_dp if over-cap groups else dp (P:349-352); None -> branch_and_bound (P:353-354);
  **P:355-356 `except Timeout: result = self.greedy(full, caps)`** — the whole round falls to greedy.
- P:361-388 capped_dp: product over groups of C(len, len-4) drop combos; > 256 -> None (P:376-377);
  else one full-round elimination dp(allowed & ~forced) per combo (P:383), no component split.
- P:390-431 elimination order; P:433-440 dp (min-degree then min-fill); P:442-520 dp_pass, check_deadline P:468.
- P:586-597 greedy heaviest-first under caps (maximal, so feasible stays true).
- P:622-697 search (B&B) keeps an incumbent on Timeout (P:693-696); P:699-702 branch_and_bound.
- P:705-715 plan_round: start_round_budget(ROUND_BUDGET) each round (P:707); over-cap = shared crew with > 4 members.
- P:718-745 derive loops rounds in id order; P:915-929 main, set_book_budget(BOOK_BUDGET) at P:921 before load.
- Consequence: a round whose shared crew has 10 members gives C(10,6) = 210 combos (<= 256), so P runs
  210 full-round DPs. With a 150-proposal lattice beside it that is ~34 s (P_inf probe, H1 R23779: 33.858 s),
  past both the 4 s round budget and the 16 s P_x4 round budget -> greedy for the round (path A), and the
  book budget is spent so later rounds also go greedy or incumbent (path B).
  11 members -> 330 > 256 -> branch_and_bound, which is fast: why r5 (k = 11) stayed EXACT.

## Reference (BUNDLE/solution/solve.py)
- :183-210 sweep_order (BFS, narrowest frontier); :212 CAP = 4.
- :215-257 best_set: frontier sweep, states (frontier mask, per-crew counts); tie-encoded weights.
- :261-293 choose: components by conflict adjacency; pieces with no counted vertex solved alone; pieces holding
  over-cap shared members solved together in one best_set. The 10 crowd members are isolated vertices, so the
  counted piece is 10 singletons with 5^1 count states; the lattice is solved once as before -> cost unchanged.

## Oracle (BUNDLE/tests/test_output.py)
- :1179-1257 _portfolio (min-fill elimination on the whole round); :1260-1277 _capped enumerates
  itertools.product of combinations(members, CAP) per over-cap crew -> 210 _portfolio calls per crowd round.
- :1280 expected; :40 BOOK_SECONDS = 20; :86 LIMITS; :762 make_book; :798-812 _check_bounds.
- Verifier cost: H1 r6 oracle 236.9 s (Docker, 2 CPUs) vs task.toml:22 verifier timeout 2700 s.

## Contract
- contract.md:11-13 limits (200 rounds, 160 proposal rows/round, 900 conflict records/round, rate 5-60,
  uplift -10..30, premium 0-800); :15 20 s wall per book. :54-58 conflicts; :62 shared crew max four.
- Hidden r6 books: 103 rounds, max 160 proposals, max 510 conflict records — inside every limit.

## Baseline (Docker, r5 books H1-H3; log r6-20261102T1838/baseline.log, ALL_DONE)
| book | reference s | P s | P_inf s | P = ref | P_inf = ref |
|---|---|---|---|---|---|
| r5 H1 | 2.5575 | 11.5397 | 10.4693 | yes | yes |
| r5 H2 | 2.5924 | 8.5548 | 8.3627 | yes | yes |
| r5 H3 | 1.8190 | 7.3766 | 9.4707 | yes | yes |
r5 books: P exact under its own budget, so the r5 shape (k = 11) is not a lever. r6 changes k to 10.
