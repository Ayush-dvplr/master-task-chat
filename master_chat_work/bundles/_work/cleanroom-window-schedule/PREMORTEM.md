# PREMORTEM 3040f47 cleanroom-window-schedule

Written before DESIGN.md. Assume the bundle shipped and failed; why?

## Failure stories (most likely first)

1. Too easy (probe score high). The idea as written (fixed intervals, per-lane last family) is solved
   exactly by the natural sweep DP (state = each lane's last family + busy job). A frontier agent writes
   it first and is right. Measured in WORK/proto: exact and < 0.4 s on 72-job, overlap-7 nights.
   Counter: G-2 coupling. One shared sterilisation crew runs every changeover as a window that ends at
   the incoming job's start and lasts crew_minutes(prev, next); windows on all bays are pairwise
   disjoint; the bay must have finished its previous job when its window starts. Per-lane DP and
   "free once its job ends" state collapse are both wrong (measured: naive collapse differs on 4-6 of
   5-8 nights per hidden book; ignoring the crew differs on 2-4 nights per book, infeasible plans).
2. LV-CW-2 leaks as a one-sentence rule (LEAK_LIBRARY CR-3 / V0-5 pattern: W3, no second reading).
   Counter: rule is defined, never emphasised (G-8: no "carries across gaps" sentence). Previous family
   is "the family of the last job the bay ran in the book"; book order is night date in audit.toml, not
   night id order (ids neutral, DS-4) nor file row order (rows shuffled). A reflex per-night reset to the
   bays.json initial family differs on 3-5 nights per hidden book. Accept that a careful reader gets it;
   LV-CW-2 alone still costs >= 25% because whole-document per book cascades.
3. Ties make "the" optimum ambiguous (G-3). Without per-bay rates, optimal-plan counts were 4-128 (bay
   symmetry). With per-bay minute rates the count was 1 on 37/39 nights; 1 night count 2, 2 nights count
   0 (mandatory jobs cannot all run). Counter: the generator counts optimal plans and redraws any night
   whose count is not exactly 1; contract states a full tie order anyway and a sentence that every
   accepted night admits a plan running all its mandatory jobs.
4. Stacking verdict fails (STACKING_CHECK): whole-doc per hidden book makes every lever fail the same
   tests. Counter: feasibility tests (plan obeys rules) separate from optimality (net equals reference)
   separate from rollups; levers then fail different subsets (greedy passes feasibility, crew-ignore
   fails feasibility, carry error fails optimality but plans may be feasible). Cost table computed from
   real wrong programs in P4, not estimated.
5. Hidden generator outside stated bounds (QC_RULINGS reject). Counter: G-6 limits in the contract
   (jobs per night <= 72, bays = 3, families = 3, overlap <= 7, minutes in [0, 1440), crew minutes and
   fees ranges); G-12 generator asserts every bound over 300 seeds.
6. Verifier time: reference + optimal-plan counting must run inside the test container for 3 books
   (19 nights) plus the shipped book. Measured locally 0.05-0.33 s per night. Counter: measure in Docker
   in P4; stated per-night limit 20 s (>= 3x oracle, reference <= 1/4 of limit).
7. Answers leak in environment/ (W11, G-7). Counter: no plan, net, or rollup anywhere in environment/;
   shipped samples carry inputs only.
8. Test/solution overlap (TS-S13 fail 35%). Counter: tests use a different exact formulation (memoised
   recursion over job index with a crew-window event list) written separately from solve.py's sweep DP.
9. A5 volume (>= 20k lines, >= 2k per csv/tsv/jsonl/txt/log). Counter: shipped book of about 340 nights
   with per-night fee rows, 2k+ clients/regions/segments rows; check per file in P2.
10. Instruction leaks rules or uses banned words. Counter: W10 one contract file; instruction states
   job, paths, exactness sentence, seconds, online-lookup sentence only.

## Lessons for the master
- book-level carry makes the shipped visible book a long chain; one wrong night poisons later nights | no change: intended cascade, recorded in STACKING_CHECK
- optimal-plan counting must be part of the test generator, not only the prototype | no change: covered by G-3 in IDEA notes
