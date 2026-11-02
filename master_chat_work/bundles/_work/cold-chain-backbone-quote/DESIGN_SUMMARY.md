# DESIGN_SUMMARY 57a2dd7 cold-chain-backbone-quote (repo-patch, optimization, seed 174241)
Full design: WORK/DESIGN.md; premortem: WORK/PREMORTEM.md; QC defence: WORK/QC_DEFENCE.md. Prototype numbers (python3.14, M1 Max); Docker numbers replace them in Phase 3.

Core: quote book of projects; per project the exact node+edge weighted Steiner network (depot + cold rooms, optional relays charged once when touched), span bound 4 on corridor order. Repo ships terminal shortest-path MST + a charge helper that bills activation per booked link; parser/report/packaging honest defects shown in failing_tests.log. Inputs in /app/ci: 11 files, 8 formats, 4 chains of length >= 4, A5 >= 20,000 lines.
Limits stated in contract: 52 sites, 95 links, 17 cold rooms, span 4, 4 s per project + 10 s start-up, stdlib only.

## Baseline losses per hidden book (prototype, seed 174241, 10 projects each, unique optimum kept)
| book | cold rooms | KMB wrong | greedy wrong | KMB+local search wrong | DW (exact) | frontier DP max |
|---|---|---|---|---|---|---|
| H1 | 15-17 | 10/10 | 10/10 | 5/10 | >= 24.5 s/project vs 4 s: timeout | 0.014 s |
| H2 | 15-17 | 10/10 | 10/10 | 3/10 | timeout | 0.014 s |
| H3 | 16-17 | 10/10 | 10/10 | 4/10 | timeout | 0.015 s |
DW per project at 48-50 sites: 10 cold rooms 0.11 s, 12: 0.88, 14: 7.25, 15: 24.5, 16: 77.1, 17: 203.8 s. Shipped book <= 10 cold rooms (DW 0.1 s, looks finished).
Every heuristic loses every hidden book whole-doc (one wrong project fails the book's document).

## Optimum uniqueness (redraw until count == 1, counted by the reference DP)
H1 35 draws: 21 over cap (prototype pair gadget, fixed in datagen), 0 infeasible, 4 non-unique, 10 kept. H2 35: 21/1/3/10. H3 26: 13/1/2/10. Shipped book: same filter.

## Cost table (84 positive test points, 24 checks + 2 cheating negatives; judge 10 criteria taken as 90)
| one lever wrong | points lost | tests kept | overall |
|---|---|---|---|
| LV-CC-2 exact DW, times out | 53 (63%) | 37% | 63.4 |
| LV-CC-1 heuristic in time | 63-66 (75-79%) | 21-25% | 57.5 |
| LV-CC-3 helper (quote + report) | 69 (82%) | 18% | 54.0 |
| LV-CC-3 report only | 43 (51%) | 49% | 69.4 (thin) |
Shares: hidden 75%, shipped-only 25%, whole-doc 85.7%, isolated 14.3%, tie lever 3.6%.

## Open questions for the master
1. Tie order (G-3 vs AL-27/G11): G-3 wants a full tie order stated while every instance is unique; an untriggered stated rule fails AL-27 and leaves a G11 row with 0 failing tests. Proposal: keep the sentence (link vector only; the site vector is implied by the links so it can never decide) plus hidden book T (6 small projects, exactly 2 optima each), weight 3 (3.6%). Alternative: drop the sentence and C23.
2. LV-CC-3 report-only scenario sits at 69.4 overall; acceptable or raise report weights further?
3. Data goes in environment/ci (archetype datagen_input = ci), not environment/data.
Risk: if Opus times a 17-cold-room project and finds the frontier DP from the span bound, only LV-CC-3 remains; the probe decides.
