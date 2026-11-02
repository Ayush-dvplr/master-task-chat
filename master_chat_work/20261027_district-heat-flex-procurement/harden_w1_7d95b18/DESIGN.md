# Wave 1 hardening design, district-heat-flex-procurement (board 7d95b18)

## Evidence
- Probe 9 (after r4, 7743264): final 68.52, tests 173/173 (100), judge 10/27. Blind 8caff6e: 98/98 on lp1 r2.
- Phase A: harness staged `tests/` and `environment/` == BUNDLE; Tasks_INPUT == BUNDLE (diff -rq empty).
- QC kit HEAD 5574d77e (expected); GEN and QC fingerprints match.

## Diagnosis (probe 9 trajectory, 56 steps, 37.5 min)
| steps | time (UTC) | what the agent did |
|---|---|---|
| 2-11 | 00:30-00:33 | read schema.md and every data file |
| 12-14 | 00:36-00:39 | wrote derive_report.py in two writes (829 lines) |
| 15 | 00:39 | first run on shipped extract, all files written |
| 18-21 | 00:41-00:45 | itertools brute force cross-check of the portfolio search: equal |
| 22-24 | 00:46-00:49 | synthetic extract (mk_synth.py), checks |
| 27-32 | 00:50-00:56 | stress at the stated bound (500 events, 8 sites x 3 offers, 6 intervals): timing fine |
| 34-46 | 00:56-01:05 | tie stress (8 interchangeable sites x 3 identical offers), two fixes to tie counting |
| 47-55 | 01:05-01:08 | alternate cross-check, finish |
Every check passed on the first scored write; the hardest part (exact optimum and exact tie count, step 12/14,
fixed at 36-44) was right because the stated bound "at most 8 sites ... at most 3 offers" makes a plain
search with a shortfall bound exact and fast. loss.py: tests 173/173, judge lost R1 R2 R3 R10, R8 fired.

## Lever P-3: the existing portfolio optimum on wider hidden event-regions
The figure is one the task already produces: per event and region, the best portfolio (schema section 5,
defined only by feasibility and five lexicographic components, remaining ties by section 2.4) and the
`tied_portfolio_count` of policy_audit `tie_decisions` (section 8.4). No new rule, no method words.

Doc change (schema.md section 3, one sentence replaced, nothing added):
- now: "An event-region has at most 8 sites with candidate offers and at most 3 candidate offers per site.
  Each run of the program on an extract must finish within 120 seconds."
- new: "A site has at most 3 candidate offers in an event. Each run of the program on an extract must
  finish within 120 seconds."
The 8-site bound is what hands over a 4^8 search; the hidden wide corpora go to 26 sites, so keeping it
would be a stated bound the hidden data breaks (QC_RULINGS district-heat v1:312 FAIL). No new size is stated.

Hidden instances (new, own RNG stream, same composed offer family as the existing hidden generator):
- 2 wide corpora, 20 events each, 4 regions, every event-region 20-26 sites, 2-5 intervals;
- per site 1-2 offers plus, 95% of the time, a second offer with identical readings and price (the hidden
  generator already plants such identical copies at 8-22%; shipped and existing corpora unchanged);
- targets 60-110% of the largest reachable relief per interval, relief ceilings 150-190% of it plus a
  margin, recovery ceilings as before, floors as before scaled by site count, 25% of events with zero cost
  and recovery weights (shortfall, deficit, overdelivery and count decide), no allowance limits;
- every bound the docs state holds (3 offers per site, ids, value forms); generator asserts (G12) over 300
  seeds; each event-region is re-drawn from its own sub-seed while the reference visits more than 150,000
  nodes, so no corpus has a single runaway event-region (the re-draw bumps are fixed constants in the test).
- Tie counts on these corpora: median 2,048-4,096 equal-best portfolios, max 524,288.

Reference (solution/solve.py and the test reference, to be built in Phase 2): depth-first search with
(1) identical offers at one site merged into one choice whose count multiplies the tie count and whose
representative is the greatest offer id (exact because for equal-size sets the greatest sorted tuple is
decided by the smallest differing member), (2) best-first order: sites by largest relief first, offers by
relief, "none" last, (3) optimistic bound from per-interval suffix maxima of relief and segment relief on
components 1-2 and current values on 3-5, pruning only on a strictly worse bound so ties are kept.
Structure relied on: identical offers and the lexicographic key whose first components are covered fast.
Reference time in Docker: see kill table (target <= 30 s = 1/4 of 120 s on each corpus).

Wrong document a plausible program writes: a search that walks tied portfolios one by one (the shipped
solve.py, probe-9 Opus, blind 8caff6e) runs past 120 s and writes nothing usable in time (LATE); a greedy or
merit-order program writes a feasible but non-optimal selection, wrong tie counts and wrong intervals.

## Lever P-4 (secondary, 2 checks)
- `failed_run_leaves_no_files`: DATA_DIR without one section-1 file -> nonzero exit and no file in OUT_DIR.
  New sentence (instruction.md): "If a file the rulebook lists is missing from DATA_DIR, the program exits
  with a nonzero status and writes no file to OUT_DIR."
- `rerun_writes_identical_files`: two runs on the same extract (different PYTHONHASHSEED) give the same
  bytes. New sentence: "Running the program twice on the same extract writes byte-identical files."
- Malformed-row error code rejected: section 9 already counts malformed rows without an error.

## Test layout and costs (Phase 2)
Per wide corpus k in {1,2}: `wide_k_portfolios_feasible` w3 (selection is candidate offers, one per site,
within every ceiling), `wide_k_selection_match` w5, `wide_k_tie_decisions_match` w5,
`wide_k_intervals_match` w3 (owned rows; whole document per corpus; G5 sentence already in instruction.md).
P-4: 2 checks w3. Existing 50 checks byte-unchanged. Positive total 173 + 32 + 6 = 211.
- late program (any tie-by-tie search): loses 32/211 = 15.2% (wide) plus whatever P-4 it misses;
- greedy / merit: keeps feasible only, loses 26/211 = 12.3%;
- all-but-one (everything right but the new P-3 lever, late): 179/211 = 84.8; greedy-shaped: 185/211 = 87.7.
- Lever share 32/211 = 15.2% (inside 10-30%). P-4 share 6/211 = 2.8%.

## Kill table (Docker, 120 s per whole run, points of 16 per corpus)
Corpora g20_61, g20_62 (20 events, 80 event-regions each, 150k node guard); raw `WORK/proto/dout/KILL20.txt`.
| solver | g20_61 s | pts /16 | g20_62 s | pts /16 | exact |
|---|---|---|---|---|---|
| reference (ref2) | 9.92, 12.2 | 16 | 9.49, 10.06 | 16 | yes |
| hour-by-hour greedy (cheapest per tick) | 0.91 | 3 | 1.46 | 3 | no (feasible only) |
| merit-order stacking | 0.88 | 3 | 1.41 | 3 | no (feasible only) |
| naive subset search (itertools.product) | LATE | 0 | LATE | 0 | late |
| time-indexed DP over relief/recovery/segment state | LATE | 0 | LATE | 0 | late (state explosion) |
| branch-and-bound, LP-style relief bound (probe-9 shape) | LATE | 0 | LATE | 0 | late |
| B&B best-first ordering | LATE | 0 | LATE | 0 | late |
| B&B with identical offers merged, no ordering | LATE | 0 | LATE | 0 | late |
| DP plus bound cut | LATE | 0 | LATE | 0 | late |
| shipped solution/solve.py | LATE | 0 | LATE | 0 | late |
| Opus probe-9 program | LATE | 0 | LATE | 0 | late |
| blind 8caff6e program | LATE | 0 | LATE | 0 | late |
Earlier smaller regimes (WORK/KILL_TEST.md): at 6 and 10 events the merge-only B&B (69-86 s) and the DP plus
bound (118.65 s) were exact inside the limit once each, so the corpora were raised to 20 events with the guard.
Reference max 12.2 s = 10% of the limit.

## Residual risk
A solver that both merges identical offers and orders best-first is the reference shape; a solver that only
merges (ref) was exact inside the limit on 2 of 4 e6/e10 corpora, which is why the corpora are 20 events.
