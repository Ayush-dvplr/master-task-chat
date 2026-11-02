# DESIGN_SUMMARY ed7b0c2 flood-repair-portfolio (domain-calculation, optimization, core build)
Core: per round, maximum-benefit conflict-free portfolio (MWIS), id tie-break; book of rounds; 10 docs.
Hidden family: triangular lattice, each diagonal p=0.7, 140-160 proposals, near-uniform benefits, ids and
rows shuffled. Contract states only counts, integer ranges, 20 s per book (final from Phase 8 timing).
Rejected before this: band/ring/motif/sparse grid (memo B&B certifies 0-20 s); full tri lattice and
king grid (clique LP integral, LP rounding exact); random sparse (reference cannot solve).

Reference (min-fill elimination DP, width 17-18): 0.08-0.19 s per large round in Docker (<= 1/4 limit).
Generic exact, Docker --cpus=1, losses in benefit units per hidden-shaped round s1..s6 (0 = exact):
| solver | s1 | s2 | s3 | s4 | s5 | s6 |
|---|---|---|---|---|---|---|
| greedy benefit | 1049 | 1195 | 1012 | 969 | 607 | 1031 |
| greedy per conflict | 610 | 395 | 588 | 573 | 412 | 672 |
| greedy + 1/2-swap | 453 | 169 | 407 | 199 | 218 | 350 |
| ILS 10 s | 102 | 71 | 250 | 114 | 58 | 190 |
| LP rounding | 235 | 135 | 130 | 63 | 407 | 386 |
| LP rounding + swaps | 102 | 0 | 14 | 30 | 143 | 127 |
| B&B colour bound, incumbent at 10 s | 377 | 362 | 501 | 204 | 577 | 494 |
| memo+reductions+split / memo low / mindeg 10 s | TO | TO | TO | TO | TO | TO |
| simplicial+domination+split+cover memo 60 s | TO | TO | TO | TO | TO | TO |
Local 600 s on s1: memo TO (15.4M nodes), classic TO (4.9M). Every hidden book has 2 large rounds, so
LP+swaps (exact on 1/6) still loses its book. Seeds kept only if every baseline loses a heavy doc.

Levers: LV-FP-1 exact optimum (core, contract "Portfolio"/"Limits"); LV-FP-2 conflicts from exclusive
crews, non-withdrawn shared permits, exclusions by proposal or site ("Conflicts"); LV-FP-3 benefit =
households x (segment rate + risk uplift) + site premium, risk_override wins ("Benefit"); LV-FP-4
secondary fault precedence by manifest file order then row ("Rejected rounds", 11% weight).

Data: 11 flat files, 7 formats, ~21.5k lines; shipped book ~175 small rounds + 2 large hidden-family
rounds (difficulty visible); no answer shipped.
Tests (33 checks, positive 108, weights 5/3/1): shipped 5 docs x3 + exist 1; hidden 3 books x {feasible
3, selected 5, summary 5, policy 3, dq 3, regions 3, segments 3}; G6 scaled-rate 5, relocated 3, rotated
3, missing source 3, rerun 3; negative /tests read -5. Hidden+mutation share 85%, whole-doc ~80%.
Projected loss (of 108): LV-FP-1 ~74 (68%), LV-FP-2 ~90, LV-FP-3 ~67, LV-FP-4 ~12+status.
Judge 9-11 batched: 5 J2 recompute conduct, J3 honesty -3, J4, J6 rejected rounds, J9 altered copy.
Risks: agent spots low width on the shipped 160 round (fair route, story 1); LV-FP-2/3 plain, low loss.
OPEN CONFLICT Q18 reserved for TRUTH provenance (VB 15.5 vs DS-27).
Full: PREMORTEM.md, DESIGN.md, QC_DEFENCE.md in this folder.
