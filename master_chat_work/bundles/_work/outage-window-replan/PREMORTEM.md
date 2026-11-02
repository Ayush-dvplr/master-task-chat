# PREMORTEM 7d363c8 outage-window-replan (reflex pre-mortem, written before design)

Assumed solver: claude-opus-5, careful, first full write in about 10 minutes, H8 (returns the
first fitting candidate) and H9 (self-tests only on shipped data and its own tiny examples).

## First 10 minutes, step by step
1. `cat /app/instruction.md`; `ls -R /app/data`; opens `docs/RULES.md` (the register), then the
   objective file, then the request spec, then skims every data file with `head`.
2. Reads the objective sentence: lexicographic (total weighted risk-days incl. deferral penalty,
   then number of requests moved from the published plan, then earliest start in asset-id order
   with deferral ranked after every day). Reads crew, incompatibility, precedence, blackout and
   deferral-reason rules. Reads the per-run time limit sentence.
3. Writes `/app/out/derive_report.py` once (about 400-600 lines): parsers, rejection pass, crew
   capacity per region/type/day after the disruption notice, load band per region/day, weights,
   then the optimiser. Its likely optimiser, in order of probability:
   a. (most likely, ~45%) per-region depth-first branch and bound with a dynamic lower bound,
      variables ordered by a heuristic (weight desc, or tightest window first, or start time),
      an incumbent seeded by greedy, and a wall-clock guard well under the stated limit that
      returns the incumbent when it fires ("anytime" search);
   b. (~25%) greedy by risk weight (or by deadline) plus a local improvement pass
      (move one, swap two) until no gain, argued "near-optimal" and fast;
   c. (~20%) per-region or per-component exact search ordered by asset id, no guard;
   d. (~10%) a day-sweep dynamic programme or a hand-written integer programme.
4. Self-tests: runs on shipped data, checks no crew over-use, no incompatible overlap, precedence
   held, every start inside its window and not on a blackout day; compares objective of its
   optimiser with its greedy seed on shipped data (equal, because the shipped season is quiet);
   maybe a 4-request toy example of its own where the optimum is obvious; then stops.

## Where each program goes wrong, and why its self-tests cannot see it
| program | goes wrong at | why no self-test catches it |
|---|---|---|
| a. heuristic-order B&B with guard | (1) on hidden contended seasons the guard fires and the greedy-seeded incumbent is published: feasible, non-optimal risk or moved count (WRONG). (2) Where it does finish, it keeps the FIRST optimal (risk, moved) plan found in its own variable order, so on planted equal-cost alternatives between two requests sharing one crew it publishes the wrong start vector (WRONG on level 3). | Shipped season: every request can take its own cheapest window, greedy is optimal, no exact tie between two requests sharing a crew, guard never fires. Invariant checks pass on any feasible plan. |
| b. greedy + local swaps | contention clusters of 4-8 requests on one crew over a cheap stretch: the heaviest-first choice blocks two lighter requests whose joint cost is higher; one-move and two-swap neighbourhoods are local optima (WRONG risk). Deferral choice: defers the lightest instead of the cheapest-to-lose set. | Shipped: no contention, so greedy = optimum; swap pass reports "no improvement", read as confirmation. |
| c. asset-id-order exact search, no guard | exact, but on hidden seasons with several interleaved clusters per region the search re-solves later clusters for each surviving partial of earlier ones; run exceeds the stated per-run limit (TIMEOUT, v3.5) unless it splits into independent groups. With splitting it is EXACT. | Shipped: finishes in under a second. |
| d. day-sweep DP | (risk, moved) exact, but the level-3 vector is in asset-id order, not time order; the sweep keeps the first plan per state in time order and loses planted ties (WRONG level 3); deferral ties (two equal penalties) resolved by sweep order. | Shipped has no exact tie, so every tie rule is silent. |
| any | precedence with deferred predecessor; new requests from the notice have no published start (moved count); crew loss applied to the wrong day range end (inclusive); these are stated noise rules, usually read right. | Stated plainly; expected right on first write. |

## Per rule: reflex reading
- Objective order: read right by all. Level 3 "earliest start in asset-id order, deferral after
  every day": read right, implemented as a per-request preference (pick earliest) rather than as
  a lexicographic comparison of whole plans; differs only where two requests trade a day.
- Moved: read right (published start differs, or deferred when published; new requests never
  moved).
- Deferral penalty and reasons: read right; reason for a deferral forced by a deferred
  predecessor is usually right.
- Crew capacity, blackout, incompatibility, precedence: read right; checked by invariants.

## Per planned judge criterion: would its trajectory show the act?
- P-a optimality witness on a self-built instance where greedy is wrong: no (it builds an
  instance only to see the program run, not one where a greedy plan loses). ~20%.
- P-c recompute the objective outside the program from a delivered file: rare (~25%).
- P-d altered-copy rerun (data copied, one value changed, outputs compared): rare (~20%).
- P-e relocated rerun from another directory: sometimes (~35%).
- P-g uniqueness witness under the tie-break (two plans with equal risk and moved, show which
  the order picks): no (~10%).
- P-h missing or malformed input run: sometimes (~30%).
- J4 exception handling: partial (~50%).
- J6 per-item enumeration of deferred requests in the final answer: likely (~60%).

## Consequence for design
A design whose first-write program (a or b) is exact on shipped AND on a fresh hidden seed is
redesigned. The hidden tier must, on every seed, contain (i) contention clusters where every
greedy class and every guarded incumbent is non-optimal, (ii) planted two-request exact ties on
one crew where only a whole-plan lexicographic comparison in asset-id order is right, (iii)
enough interleaved clusters per region that an unsplit exact search cannot finish, while the
reference (independent groups, then a lexicographic fixing pass) finishes in well under 1/4 of
the stated per-run limit. The kill test in Docker decides; if c-with-splitting and d-with-a-
correct-fixing-pass are both exact and fast, the core still loses only to the tie level.
