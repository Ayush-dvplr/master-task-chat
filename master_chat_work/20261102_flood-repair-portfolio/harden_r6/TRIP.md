# TRIP: r6 design and paid program P, confirmed before build (board ea04435)

## P (a4 run_1 artifacts/app/out/derive_report.py)
- sha256 e2f9460ff73a883b9c93a085a56ebee619a459e1bd94edbe3643a7955a397b86, 933 lines (matches measure 2939ad0).
- P:24 BOOK_BUDGET = 13.0 s; P:25 ROUND_BUDGET = 4.0 s.
- P:301-303 STATE_CAP 1000000, LEAF_CAP 120000, COMBO_CAP 256.
- P:345-358 choose(): capped_dp when a shared crew is over cap, else dp; None falls to branch_and_bound;
  P:355-356 `except Timeout: result = self.greedy(full, caps)` (silent non-optimal answer).
- P:361-388 capped_dp: product of combinations(members, drop) per over-cap crew; > COMBO_CAP returns None;
  else one full dp per combination (P:383). Ten members, cap four: C(10,6) = 210 <= 256, so 210 full DPs.
- P:918-925 main: set_book_budget(BOOK_BUDGET) at P:921; once the book budget is spent every later round
  times out at once and takes the greedy path.

## Lever (measure 2939ad0, DESIGN READY A+B)
- Path A: a 150-proposal lattice round plus a 10-member shared crew new to that round (160 rows, at the
  contract maximum) makes capped_dp run 210 full DPs; the 4 s round budget ends, P:355-356 returns greedy.
- Path B: six such rounds per hidden book (indices 0,10,...,50 of the 60 large rounds) spend the 13 s book
  budget, so later large rounds also go greedy.
- Members are isolated (no permit, exclusion or crew conflict besides the shared crew); the reference
  (solve.py:261-293) splits components so each member is cheap; values come from book.value_large.
- Oracle side: test_output.py:1260-1277 _capped enumerates keep combinations over _portfolio
  (:1179-1257), exact; about 223-242 s per crowd book in the measure.

## Measured numbers (WORK/r6_budget books, measure session)
| item | H1 | H2 | H3 |
|---|---|---|---|
| P | WRONG (first diff R11123) | WRONG (R18482) | WRONG (R17164) |
| P_x4 (budgets x4) | WRONG | WRONG | WRONG |
| P_inf (no budgets) | EXACT 149.27 s | EXACT 122.61 s | EXACT 104.25 s |
| reference busy s | 1.5219 | 2.2565 | 2.4820 |
| oracle verifier s per book | 236.94 | 242.07 | 223.13 |
- P loses 57 of 108 positive test points (19 per book: optimal 5, summary 5, policy_audit 3, regions 3,
  segments 3); keeps feasible 3 and data_quality 3 per book. Lever share 52.78%.
- Shipped book: reference 0.5309 s, P EXACT 0.6519 s (lever invisible on shipped data).
- Kill table (points of 75 hidden): P 18, P_x4 18, P_inf 75, blind4_b1 75, blind4_b2 18, first_write 0,
  all_but_one 0, lever_aware 75.
- Books 103 rounds, max 160 proposals per round, max 510 conflict records per round (contract.md:11-13
  limits 200 / 160 / 900); 20 s per book (contract.md:15) matches test_output.py:40 BOOK_SECONDS.

## What the measure did not run (this session must)
- The crowd rounds live in a side generator (WORK/r6_budget/gen_r6.py, main RNG stream), not in
  tests/test_output.py; the verifier still builds the old books.
- P run twice on the same book (reruns check, test_output.py:1560-1564) not measured.
- Full verifier wall time on the oracle lane not measured (task.toml timeout 2700 s, bar 2430 s).

## Build choice
- Crowd rounds go into make_book with their own RNG stream (book.rng swapped, as _capped_round does at
  test_output.py:647-653), built after the main rounds, faults, audits and capped rounds, so every value
  drawn from the main stream is unchanged; only H1-H3 specs get the crowd keys (M, MS, MR, SHIPPED
  untouched, their expected documents byte-identical).
- Built books will differ from WORK/r6_budget/books (own stream), so the GO bar is re-measured on the
  verifier's own books (note 1 second branch).

## Build confirmation
- Verifier books: P and P_x4 WRONG 3/3; P_inf EXACT 3/3. Loss 57/108; busy reference max 2.2411 s.
- Shape assertions: 300 seeds, zero errors; built books each 103 rounds, max 160 rows and 517 records.
- Paired P outputs were byte-identical on all three books; timing-dependent paths can still diverge.
- Full oracle verifier measured 655.809117 s, below 2430 s; the slow exact oracle needs no speedup.
- Named copied witness: WORK/r6_build/witness/witness.json, R39321, P 63929 vs oracle 73387.

## Lessons for the master
Own-stream replacement changes hidden books; re-measure those actual books | no change: issued note 1 already requires it.
