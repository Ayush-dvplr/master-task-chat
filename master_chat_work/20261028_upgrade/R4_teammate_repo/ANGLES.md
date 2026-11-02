# ANGLES.md: research angle log (R4, run 1, board 1d26a6e, 28 Oct 2026)

Each future run (P15 v2) reads this file first, picks at least 2 UNTRIED angles, and appends its own rows to the log below. Strength: S = holds in a within-author contrast or across 90 with a clear median gap; M = across-90 gap but confounded; W = single task or heuristic only; N = tried, no signal.

## Log (angles tried)
| id | question | method | tasks | result (one line) | strength |
|---|---|---|---|---|---|
| A1 | Does weight concentration separate hard from easy? | top1 share, distinct weights per task (inventory.py) | 90 | No: top1 ~0.05-0.06 and 3 distinct weights in every band | N |
| A2 | Does the share of weight on hidden or rerun checks separate them? | test-name regex hidden share, mean weight hidden vs shipped (contrast.py, h_ columns INFERRED) | 90 | Yes: hidden share median 0.68 HardExpert vs 0.16 Medium vs 0.18 Easy; share >= 0.5 gives median final 35.7 vs 56.5. Hidden checks weigh 5 and shipped 1 in 59417607, 18b5d99f, d49e259f | S (also within author: Ayush, Harshank, Sanvi) |
| A3 | Does rerunning on fresh inputs separate them? | subprocess and seeded generator in test_output.py | 90 | No: 13/14, 24/25 and 49/51 rerun; 11/14, 23/25 and 46/51 are seeded. Rerun is universal; what matters is the weight on it (A2) | N |
| A4 | Do withheld facts (evidence induction) make tasks hard? | regex on TRUTH.md for withheld/undocumented | 90 | 8/14 HardExpert vs 11/51 Easy; with hidden share >= 0.5, median final 36.8 (n=9). Legality splits: bounded (stated domain) vs unbounded (forms or meanings unstated) | S (within author: Sanvi, Harshank) |
| A5 | What judge composition goes with low scores? | exact-figure criterion share, trajectory-probe share, positive points P | 90 | Exact-figure share >= 0.25 gives median final 40.4 vs 57.1. Counterfactual what-if figures stay hard; headline figures leak (LEAK_LIBRARY:12). P <= 20 has no effect on the median but makes one weight cost >= 2.5 final points | M |
| A6 | Which channel loses the points? | loss_tests vs loss_judge in final points | 90 | Judge dominates in 4/14 HardExpert vs 21/51 Easy. Hard tasks lose on tests (median 46 points); Easy tasks lose most on the judge | M |
| A7 | Is hardness about time? | agent minutes / timeout, first-write minute, steps (trajectory.json) | 90 | No timeouts. HardExpert agents used a median 23% of the budget and quit early (b5c7b14c 4%; 8defd7be "time limit" at 63%). First write comes later: 9.5 vs 6.8 min | M |
| A8 | Are contributor or domain confounds behind the bands? | band counts per toml author and category; within-author split | 90 | HardExpert tasks come from 8 of 15 authors; 7 authors have none (Nikhil Bansal 0/11). Within-author contrasts keep A2 and A4. Optimization is 3/6 HardExpert | S |
| A9 | Can genuineness be judged without verifier messages? | agent's shipped-data figures from the judge's exact-figure justifications, artifacts manifest, final message | 13 | Yes for 11 of 13. It shows valid-but-wrong output on shipped data (8defd7be, 42e79476, 59417607, aa314fee, df8f123b, 5b2b0901, 80202e15) | M |
| A10 | Do README bands match the stored run? | README score vs run_1 report.json (losses.py) | 90 | 5 mismatches > 1 point; d22ff871 0.51 vs 32.36 (19 points) | W |
| A11 | Do tasks share skeletons? | deliverable names and test-name families | 13 | Three template families: firmware recovery (8defd7be, 5b2b0901, d49e259f); hazard-slice close (9f5486ac, 80202e15); derive_report allocation (aa314fee, 6d12f970) | M |
| A12 | Are the hard tasks fair? | P14 Phase A plus a TRUTH identifiability read | 13 | 9 genuine; 4 flagged (3 with an unbounded hypothesis space, 1 hard only by the judge) | S |

## Untried angles, ranked for the next run
1. U1 Self-test anatomy. Classify every self-test command: shipped-only, constructed input, perturbed copy, relocated run. Relate each class to hidden pass rate across 90; this tests H9 directly.
2. U2 Judge negative design. Compare reading-specific negatives (df8f123b names 9 wrong readings) with generic honesty negatives. Measure firing rate per type across 90 (21/90 tasks fired at least one).
3. U3 Easy-task leak autopsy. For Easy tasks with hidden share > 0.3 and hidden pass > 0.6, find which hidden families passed and why (the mirror of LEAK_LIBRARY rows).
4. U4 Oracle shape across the 31 induction tasks. Does solve.py derive the facts or hard-code them? Check uniqueness proofs (global vs one-step sweep, as in 8defd7be TRUTH.md:121).
5. U5 Data heterogeneity. Count formats (xlsx, pdf, docx, sqlite, fixed-width) and decoy files per task; relate them to loss after controlling for author.
6. U6 Instruction phrasing. Look for the rerun promise, "exact match every row" sentences and stated time or effort caps (5b2b0901 instruction.md:36) across bands.
7. U7 Partial-credit curves. Compare per-hazard slice tests with whole-document tests: points kept per correct rule.
8. U8 Run variance. Get 2 more runs for the 13 models; measure the ±spread (G13). Needs Ayush or harness access.
9. U9 Cost and tokens vs score (result.json cost_usd; 9f5486ac $33.8).
10. U10 Contributor style deep dive. What do Nikhil Bansal's 11 tasks (median 64.4) lack compared with Abdus and Aditya Jain?
11. U11 Stage-1 vs Final_Delivery diffs for the 30 studied tasks (Dockerfile changed; judge version skew).
12. U12 Time-to-first-write vs final, as a regression with author fixed effects.
