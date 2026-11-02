# PREMORTEM ed7b0c2 flood-repair-portfolio

Written before DESIGN.md. Assume the bundle shipped and failed; why? Every number below is measured
(WORK/proto, logs in WORK/proto/logs, Docker image `frp-premortem` = python:3.12-slim + scipy 1.14.1,
`--cpus=1`). Instances are the planned hidden round shape: proposals on a triangular lattice where each
diagonal conflict is present with probability 0.7, 144 to 160 proposals, 348 to 393 conflict pairs,
benefits 90 to 110 (scaled later by the valuation), ids and row order shuffled independently of geometry.

## How claude-opus-5 solves it in the first 10 minutes

1. Reads `/app/data/contract.md` top to bottom, then `manifest.json`, then `head` of every data file.
2. Writes one program in one pass: loaders per file, valuation function, conflict set per round
   (crew, permit, exclusion), a solver per round, then the ten writers. Stdlib only, as stated.
3. Solver first-write, most likely to least likely (from LEAK_LIBRARY rows on optimisation cores and the
   cleanroom 3040f47 probe notes): (a) bitset branch and bound with a greedy colouring or clique-cover
   bound, max-degree branching, incumbent seeded by greedy; (b) the same plus memo on the remaining mask,
   degree-0/1, simplicial and domination reductions and component split at every node; (c) a time-guarded
   version of (a) or (b) that returns its incumbent when a deadline passes; (d) greedy plus 1/2-swap local
   search when it decides exact is out of reach.
4. Self-tests: runs on the shipped book, compares against a brute force it writes for rounds of at most
   about 20 proposals, checks conflict-freeness, checks that region and segment sums add up to the summary.
   All of these pass for (a) to (d) on the small shipped rounds.
5. Hits the two large shipped rounds (120 and 160 proposals): (a)/(b) do not return. The agent then
   either (i) adds a deadline and keeps the incumbent, (ii) tunes the bound or the reductions, or
   (iii) looks at the conflict structure, sees a small elimination width and writes an
   elimination-order (tree decomposition) program. Only (iii) is right.

## Failure stories, most likely first

1. **The agent finds the elimination-order method on the shipped large rounds** (the fair route).
   Measured: min-fill order on every hidden-shaped round gives width 17 to 18 and a DP over independent
   subsets of each bag certifies in 0.08 to 0.19 s in Docker (states 2,850 to 12,240). A memo search that
   branches in breadth-first sweep order certifies seed 1 in 0.9 s locally (266,621 nodes).
   Counter: none wanted. This is the skill the task measures (G-3); the contract states only counts,
   integer ranges and the time limit, never width, components, separators or a lattice. Labels and row
   order are shuffled, so sorting by id, site, crew or permit does not reproduce a sweep order
   (memo with lowest-index branching under the shuffled ids: TO at 60 s on all six).

2. **Generic exact (a)/(b) certifies within the limit on some hidden round.** Measured in Docker at
   10 s per round: `bnb_colour` (a), `bnb_memo_reduce_split` (b without simplicial), `memo_low`,
   `memo_mindeg`: TO on all six hidden-shaped rounds. Strongest variant `reduce_bnb` (b with simplicial
   reduction, domination, component split, clique-cover bound, memo): TO on all six at 60 s
   (665k to 732k nodes). Locally at 600 s on seed 1: memo TO (15.4M nodes), classic TO (4.9M nodes).
   Counter: hidden rounds are drawn only from this family and the generator asserts width >= 15 and
   n >= 140 for each large round; the stated book limit (planned 20 s) is far below 600 s.

3. **The clique LP is integral and LP rounding recovers the optimum.** Measured first on the full
   triangular lattice and on the king grid: LP-integral, `lp_round` loss 0, so that family was rejected.
   With diagonals at probability 0.7 the clique LP is fractional on every seed (99 to 107 fractional
   variables, LP gap 54 to 110). Agent images carry no LP solver (stdlib only, no network); scipy exists
   only in the premortem image. Losses (benefit units, 0 = exact): lp_round 63 to 407; lp_round plus
   1/2-swap 0 (seed 2) to 143. Counter: each hidden book holds two large rounds, so a book is lost unless
   both rounds are exact; build asserts every hidden book has at least one large round where lp_round_ls
   is not exact.

4. **Time-limited search incumbent (c) or iterated local search happens to be exact.** Measured
   incumbent loss of `bnb_colour` at 10 s: 204 to 577 on all six. Iterated local search with random
   1-3 vertex kicks for the full 10 s: loss 58 to 250, never exact. Greedy by benefit 607 to 1195,
   greedy by benefit per conflict 395 to 672, greedy plus 1/2-swap 169 to 453. Counter: build-time
   premortem rerun on the three final hidden books records every baseline per round
   (WORK/COST_TABLE.md); seeds are kept only when every baseline loses at least one whole heavy document.

5. **Conflict derivation (LV-FP-2) or valuation (LV-FP-3) is read right by every agent.** Likely: both
   rules are stated plainly in one contract table. They are not the difficulty of a core build; their role
   is coupling. Every figure of a round comes from its one portfolio, so a dropped source (withdrawn
   permit rows counted, shared crews treated as exclusive, site-named exclusions skipped) or a skipped
   adjustment (risk override ignored, uplift skipped, premium per household) moves the portfolio and
   every downstream document. The generator asserts per hidden book that each single-source drop and each
   single-adjustment slip changes at least one large-round portfolio. Counter: accepted as low expected
   loss; reported honestly in DESIGN.md.

6. **The agent's self-tests would catch the solver gap.** They cannot: brute force only reaches the small
   rounds, conflict-freeness and the region/segment reconciliation all hold for a feasible but suboptimal
   portfolio, and no optimum, total or selected list is shipped (W11). The only visible signal is that
   (a)/(b) do not return on the large shipped rounds, which is the honest difficulty signal (G-3).

7. **Verifier time.** Reference whole hidden book about 1 s in Docker; the verifier runs four books plus
   five mutation runs. Expected optima are computed at build time and embedded with a hash check, so
   grading never solves a hard round itself.

## Redesigns already made because of this premortem

- Band, ring, motif-chain and sparse grid families: memo B&B certified in 0.0 to 20 s. Rejected.
- Full triangular lattice and king grid: clique LP integral. Rejected.
- Random sparse graphs of degree 5: reference does not finish either. Rejected (fairness).
- Kept: triangular lattice with diagonal probability 0.7, near-uniform benefits, shuffled labels.

## Lessons for the master
- Check clique-LP integrality before trusting a hard MWIS family; perfect-ish lattices are LP-integral | no change: recorded here and in DESIGN.md
- Shuffle ids and row order independently of geometry or a lowest-index memo becomes the sweep DP | no change: generator rule in DESIGN.md
