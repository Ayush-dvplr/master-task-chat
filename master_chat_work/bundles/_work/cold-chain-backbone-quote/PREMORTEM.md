# PREMORTEM: claude-opus-5, first 10 minutes on cold-chain-backbone-quote

Measured numbers come from the prototype in the scratch dir (`ccproto/proto.py`, python3.14 on M1 Max, single core). Docker numbers replace them in Phase 3.

## 1. Reading order (what it opens, in order)
1. `instruction.md` (given). Learns: repair /app/repo, zip to /app/out/patched-repo.zip, write the six other documents, documents graded whole on fresh books, exact match only, per-project time limit lives in the contract.
2. `ls -R /app` then `/app/ci/api_contract.md` in full: input files of a quote book, the network rule (depot plus every cold room connected, quote = selected link costs + activation charge of every activated site once), the span bound (non-depot link spans at most 4 corridor positions), the bounds (52 sites, 95 links, 17 cold rooms, 4 seconds per project), the booking rule for rollups, output keys, error codes.
3. `/app/repo/README.md`, `src/<pkg>/core.py` (shortest-path heuristic: terminal distance graph, MST, expand paths, prune), `parser.py`, `report.py`, `tests/test_visible.py`.
4. `head` of every data file in /app/ci; `failing_tests.log` tail (the FAILED line), `grep FAIL`.
5. Runs `python -m unittest` in /app/repo: sees the logged failures (parser and report defects plus packaging).

## 2. The program it writes once
- Fixes the parser defects named by the failing tests and the packaging (pyproject).
- Sees "minimum-cost network" plus the heuristic in core.py. Two branches:
  - Branch A (about 1 in 3 runs, cheap path): keeps the heuristic, adds a local improvement (relay insertion and deletion with MST plus pruning), because the visible tests pass and nothing shipped gives an optimum to compare against.
  - Branch B (most likely): recognises the node-weighted Steiner tree, bounded terminals (at most 18 with the depot), writes Dreyfus-Wagner with node weights: dp[S][v] over cold-room subsets, merge `dp[A][v] + dp[S-A][v] - a(v)`, Dijkstra relaxation with entry cost `c(u,v) + a(v)`, read at the depot.
- report.py: keeps the shipped rollup loop and edits the field names it sees failing.

## 3. Self-tests it runs
- Visible repo tests: all pass after the fixes.
- Runs its package on the shipped book in /app/ci: every shipped project has at most 10 cold rooms, so DW finishes in about 0.1 s per project. It sees the time limit is met.
- Writes 20 to 200 tiny random projects (5 to 9 sites, at most 16 links) and compares DW with brute force over link subsets: agree.
- Invariants: every network connected, every cold room present, recomputed cost equals quote.
- Possibly times one synthetic project; its synthetic generator draws cold rooms the way the shipped book does (5 to 10), not at the stated 17.

## 4. Its reading of every rule
- Network rule, activation charge once per activated site, booking of each link to its endpoint with the larger corridor position, share in basis points, rejection codes: read correctly from the contract (they are stated plainly).
- Span bound: read as an input validation rule (E_BAD_SPAN) only; it does not connect it to the solver.
- Time limit: read, checked against the shipped book only.

## 5. Per lever: where the first program goes wrong, and why its self-tests miss it

### LV-CC-2 (runtime at the stated maximum terminal count)
- Branch B goes wrong on every hidden book: hidden projects carry 15 to 17 cold rooms. Measured DW (node weights, 48 to 50 sites, 85 to 90 links): 8 cold rooms 0.02 s, 10: 0.11 s, 12: 0.88 s, 14: 7.25 s, 15: 24.5 s, 16: 77.1 s, 17: 203.8 s (the factor is about 3 per extra cold room; one project per row, python3.14, M1 Max). The limit is 4 s per project, so the whole hidden-book run times out and every document of that book is missing.
- Why self-tests miss it: the shipped book stops at 10 cold rooms, its brute-force harness needs tiny projects, and nothing it runs reaches the stated bound unless it builds a 17-cold-room project on purpose.
- The exact method in time is a frontier DP over the corridor order (window of 4 positions plus the depot, partitions of the active frontier sites): measured 0.01 to 0.02 s per hidden-size project in the prototype.

### LV-CC-1 (exact minimum-cost network)
- Branch A goes wrong on every hidden book. Prototype, 15 hidden-size projects with relay hubs: terminal shortest-path MST (KMB) wrong on 14 of 14 feasible projects, greedy attach wrong on 14 of 14, KMB plus single and pair relay insertion local search wrong on 6 of 14. A hidden book holds 10 projects; one wrong project fails the whole document of that book, so every heuristic loses every hidden book.
- Why self-tests miss it: no optimum is shipped anywhere; visible repo samples are near trees where the heuristic is optimal; invariants (connected, cost recomputes) all hold for a feasible but dearer network.

### LV-CC-3 (activation charged once per activated site, carried into every corridor total)
- Where it goes wrong: (i) in DW, dropping the `- a(v)` at the merge charges a shared relay once per branch; (ii) in report.py the shipped loop charges a site's activation once per selected link booked to it, which equals "once per site" whenever exactly one link is booked to each site (every visible sample is a monotone chain) and differs on hub relays with two or more booked links and on sites whose links are all booked to later sites.
- Why self-tests miss it: (i) is caught by its brute-force harness if it writes one, so (i) alone is weak; (ii) is caught only by the invariant "sum of site totals plus depot line equals the quote", which it checks only if it thinks of it; the visible samples pass under both readings.
- Honest rating: weakest lever of the three. Redesign applied before Phase 1: every hidden project carries relay hubs with 2 to 4 booked links and sites booked zero links, so reading (ii) moves corridor and site totals in every hidden project, and the quote share column carries the quote into every row (COUPLING), so (i) moves every document of the book.

## 6. Redesign decisions taken from this premortem
- Shipped book: up to the stated site and link maxima, at most 10 cold rooms per project (DW in time on it, so Branch B looks finished).
- Hidden books: every project 15 to 17 cold rooms, 38 to 52 sites, 65 to 95 links, 3 to 5 relay hubs, all within the stated bounds; optimum unique per project (counted by the reference DP; redraw otherwise).
- Per-project limit 4 s, stated in the contract; the hidden run timeout is 4 s times the number of projects plus start-up.
- If the probe shows Opus building a max-size timing test and finding the frontier DP, the remaining loss comes from LV-CC-3 and the rollups; raising cold rooms beyond 17 is out (stated bound).
