# DESIGN — flood-repair-portfolio r6 budget lever (board 2939ad0, measure only)

Evidence root: `_runs/20261102/flood-repair-portfolio/r6-20261102T1838/` (logs measure_H1/H2/H3/SHIPPED.log,
gen_books.log, shape300.log, witness.log, probe_h1_one.log, baseline.log, every one ends ALL_DONE).
WORK files: `bundles/_work/flood-repair-portfolio/r6_budget/` (gen_r6.py, measure_r6.py, witness.py, probe.py,
baseline.py, programs/p_x4.py + p_x4.diff, programs/p_inf.py + p_inf.diff, books/H1-H3, results_*.json, witness/).
Design round 1 only; round 2 not needed.

## GO bar (all met)
| item | bar | measured |
|---|---|---|
| P WRONG on H1-H3 | 3/3 | 3/3 (first diff R11123 / R18482 / R17164, selected and total_benefit) |
| P_x4 WRONG on H1-H3 | 3/3 | 3/3 (same first rounds) |
| positive points P loses | >= 44/108 | 57/108 (19 per book: optimal5 summary5 policy_audit3 regions3 segments3) |
| reference busy per book | <= 5 s | 1.5219 / 2.2565 / 2.4820 (max 2.482) |
| books inside contract | yes | 103 rounds, max 160 proposals, max 510 records; 300 seeds 0 errors |
| P_inf exact | yes | EXACT 149.27 / 122.61 / 104.25 s (equals oracle) |
| shipped book | fast, right | reference 0.5309 s, busy 0.3743 s, P EXACT 0.6519 s |
P keeps feasible3 + data_quality3 per book: greedy (P:586-597) is maximal and cap-respecting.

## Path: A+B
- A (round budget): a crowd round has one shared crew with exactly 10 members, so P's capped_dp
  (P:361-388) enumerates C(10,6) = 210 drop combinations (<= COMBO_CAP 256, P:303, P:376) and runs a full
  elimination DP on the whole 160-proposal round per combination (P:383) with no component split.
  P_inf needs ~34 s for one such round (probe: H1 R23779 33.858 s). The 4 s round budget (P:25, P:707)
  expires inside dp_pass (check_deadline P:468), Timeout escapes to choose and **P:355-356 replaces the whole
  round by greedy**. P_x4's 16 s round budget expires the same way.
- B (book budget): each crowd round burns its full round budget, so the 13 s book budget (P:24, P:921) is
  gone by mid-book; every later round's search hits check_deadline at once and returns greedy or the
  incumbent (P:624, P:693-696). Wrong rounds: P 48 / 56 / 34, P_x4 22 / 52 / 33, blind4_b2 6 / 4 / 5
  (b2 loses only crowd rounds: path A alone).

## Round shape and why the reference stays fast
- Per hidden book: the H1/H2/H3 specs and seeds unchanged except 6 of the 60 large lattice rounds
  (indices 0,10,...,50) use n = 150 lattice proposals plus a 10-member shared crew new to that round
  (gen_r6.py add_crowd). The 10 members get fresh sites and pids, values from book.value_large, no permit,
  exclusion or crew conflict with anything (assert derive(rnd) unchanged), 150 + 10 = 160 proposals.
  The three verifier capped rounds (k 6-8, _capped_round) stay as generated.
- Reference choose (solve.py:261-293) splits by conflict adjacency: the 10 isolated members form 10
  single-vertex pieces solved together in one counted best_set (frontier 0, 5 count states), and the lattice
  is solved once by the frontier sweep (:215-257), exactly as before. Reference 2.69/2.39/3.23 s idle,
  1.52/2.26/2.48 s with a CPU burner (r5 books: 2.56/2.59/1.82 s).
- Optimum differs from greedy on the lattice part (witness: 73387 vs 63929), not on the crowd: the crowd
  only forces P into its expensive branch. Any program that treats isolated shared members apart from
  the lattice, or prunes the 210 combinations, stays exact (blind4_b1, lever_aware).

## Kill table (lever total = 75 hidden points, 3 books x 25)
| program | H1 | H2 | H3 | points/75 |
|---|---|---|---|---|
| P (paid a4, shipped budgets) | WRONG 13.68 s | WRONG 14.21 s | WRONG 13.61 s | 18 |
| P_x4 (52 s / 16 s) | WRONG 52.41 s | WRONG 53.14 s | WRONG 52.61 s | 18 |
| P_inf (1e9 / 1e9) | EXACT 149.27 s | EXACT 122.61 s | EXACT 104.25 s | 75 |
| blind4_b1 | EXACT 6.80 s | EXACT 7.70 s | EXACT 5.82 s | 75 |
| blind4_b2 | WRONG 11.25 s | WRONG 15.54 s | WRONG 9.39 s | 18 |
| first_write | TIMEOUT 20.02 s | TIMEOUT 20.03 s | TIMEOUT 20.03 s | 0 |
| all_but_one | TIMEOUT 20.02 s | TIMEOUT 20.08 s | TIMEOUT 20.01 s | 0 |
| lever_aware (reference DP, recorded only) | EXACT 1.81 s | EXACT 3.77 s | EXACT 2.04 s | 75 |
P_x4 and P_inf ran with longer caps (120 s / 1500 s) on purpose; under the real 20 s cap P_x4 and P_inf
would be TIMEOUT, so their rows test speed independence only.

## Prediction for the paid run (no new weights, no doc change)
- Tests: 108 - 57 = 51/108 = 47.22% (shipped 15, artifacts 1, scaled/rotated/relocated 11, missing 3,
  reruns 3 kept; H1-H3 6 each). If P's two H1 runs differ (timing-dependent greedy rounds), reruns_identical
  also fails: 48/108 = 44.44%. Not run.
- Judge unchanged: low/mid/high 37.5 / 37.5 / 53.125 (judge.toml byte-identical, positive total 32).
- Final (tests + judge)/2: low/mid 42.36, high 50.17 (with reruns loss 40.97 / 48.78).
- Lever share: 57/108 = 52.78% of test points rest on the budget lever.

## QC rows
- IN-15: no new rule of engagement; instruction and contract untouched; :15 time sentence stays.
- IN-16: contract.md:11-15 limits, :54-58 conflicts, :62 cap and tie break already fix the answer for a
  10-member shared crew; no new ambiguity (10 > 4 is an ordinary over-cap crew).
- IN-17: no hidden structure hint added; the 20 s / contract limits are the only stated scale facts.
- DS-21: answers come only from shipped rules; reference, oracle ledger, P_inf, blind4_b1 and lever_aware
  agree exactly on all three books.
- TS-11: deterministic seeds; exact comparison; reference margin 2.48 s busy vs 20 s (8x). Verifier
  oracle cost rises to 223-242 s per hidden book (oracle _capped test_output.py:1260-1277 runs 210
  _portfolio calls per crowd round); about 12 min for three books vs task.toml:22 timeout 2700 s.
  Flag for the build step: measure full-verifier wall time once.
- TS-19: same nine documents, same shapes; no new output expectation.
- TS-26: no checks or weights added; the existing optimal/summary overlap is unchanged.
- AL-27: algorithm cutoff fires on P under its own budgets AND at 4x budgets: P and P_x4 WRONG on 3/3.
- CL-4: instruction:11 exact-match rule; a wrong crowd round alone propagates to optimal, summary,
  policy_audit, regions, segments (19/25 per book), measured not estimated.

## Speed-dependence risk
P_inf needs 104-149 s per book, against P's 13 s budget (8-11x) and P_x4's 52 s (2-3x): P_x4 still
loses 22-52 rounds per book. A crowd round costs P ~23-34 s exact, so even a machine 4x faster than
the 2-CPU Docker run leaves every crowd round past the 4 s round budget, and a 4x budget still fails.
Residual risk: a much faster grader (>8x) would let P finish some crowd rounds; the path B losses would
then shrink first, but the first crowd round in each book still needs > 16 s at 2x speed.
Second risk: P's loss is timing-dependent between runs (reruns_identical), which can only add loss.
Third risk: verifier cost (TS-11 above).

DESIGN READY: A+B
