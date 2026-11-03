TASK: f5fe93be-3ce1-5eb6-a1f5-8c4a8ea80703, Video Processing (broadcast airtime close: as-run, switcher and probe logs reconciled to spot dispositions, deliveries, make-goods, billing and four roll-ups, one program plus nine artifacts), Opus tests 55.22, rubric 83.95, final 69.59.

1. VERDICT: DESIGN, 100 percent of lost test weight (30 of 67), confidence medium. No contradiction between reference and docs was found; one make-good divergence is located, the shipped-spot divergence is not.

2. LOSSES:
1. shipped_scenario_spots_exact, 5: WRONG output. The closing figures are off by exactly one spot (dropframe_as_nondrop 61 vs 62, chain_a_always_on_air 2006 vs 2005, both outside the largest workload), so one spot disposition in a shipped workload differs. Not located without rerunning.
2. heldout_makegoods_exact, 5, and shipped_scenario_settlement_exact, 5: WRONG output in the make-good queue (dispositions and deliveries on the held out week pass).
3. perf_report, bottleneck_analysis, recommendations, data_quality, 3 each (12): WRONG output inherited from 1 and 2.
4. month_workload_within_time_budget, 3: TIMEOUT (or slow) on the 28 day workload.
Passed: held out dispositions, deliveries, billing, rejects, both extra channels (whole object), boundary and exhausted-capacity fixtures, identities, CLI.

3. DIFFICULTY KIND:
1. Loss 2: (d) misread rule. Opus resolves the order line copy through the alias table as of the shortfall date; the reference uses the order line id directly.
2. Loss 1: (b) or (d), a rare case present in the shipped week only; undetermined.
3. Loss 4: (c) scale: first-fit break search is a linear scan per unit; the reference uses a max segment tree over spare frames.

4. EVIDENCE:
1. corpus_index.md:21 "house_id is the order line's own copy, always a canonical registry id"; makegood_policy.md:20 "A unit needs the expected frames ... of its order line's own house_id"; source_precedence.md:39 limits alias resolution to "Every house id of a spot". Reference solve.py:614 need = expected_frames(normalise_house(order house_id)); agent optimize.py:903 corpus.resolve(info house_id, from_date, ...).
2. Scale: makegood_policy.md:20 first open break with enough spare; agent optimize.py:913-922 linear while loop; solution SpareTree (solve.py:687). TRUTH item 17 names this lever.

5. TEST DESIGN: in-test generators build several unseen directories (drop frame week with a summer time change, 25 fps channel with 05:00 day start and shuffled rows, a third zone with four frame tolerance, a boundary fixture, an exhausted capacity fixture, a 28 day workload about five times larger); shipped artifacts recomputed by an embedded reference. Comparison is per section, whole list exact (spots, deliveries, make-goods, billing). Amplification: one disposition moves deliveries, then the make-good queue, then four roll-ups. Timing relative to a reference run (4x plus 2 s). Negatives: hardcoded answers, ignoring workload, nondeterminism, input mutation, output on missing input, file writes, path dependence, artifact differing from program.

6. INSTRUCTION: "An artifact counts only when every entry and value in it is exact"; "must return within four times the time a straightforward single pass reference implementation takes ... plus two seconds"; "every rule parameter must be read from the directory"; "the current rule documents govern" over retired documents; deliverable python3 /app/out/optimize.py DATA_DIR WORKLOAD; closing message with nine figures. Not said: which data structure is needed, or that the held out week contains a summer time change.

7. RUBRIC: lost R1 and R3 (closing figures off by one, same root as loss 1) and R16 (no explicit drop frame spot check at a tenth minute and a skipped-label minute). All else passed.

8. REUSABLE IDEA: a greedy first-fit allocation whose straightforward implementation is quadratic, graded with a relative time budget on a much larger hidden workload; and a field documented as already canonical that tempts the solver to run it through the same normalisation chain used elsewhere.
