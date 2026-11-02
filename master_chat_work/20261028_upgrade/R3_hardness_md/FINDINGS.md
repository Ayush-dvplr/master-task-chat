# R3 FINDINGS: verifying the QL's hardness.md (board 0036eb5)

Source: `OUT/hardness_source.md` (sha256 9056754…5148, a copy of `/Users/mac/Downloads/hardness.md`). Every number below is printed by a script in `OUT/scripts/` (re-runnable: `python3 OUT/scripts/<name>.py [doc85|cur90]`). One run per task throughout: a single task's score is one sample (G13: ±20 tests, ±10 final).

Short answer: the doc's arithmetic is reliable (41 of 68 claims confirmed exactly, 18 partly, 5 wrong, 4 untestable). Its causal story is half right. The held-out tier (L2) and the judge probe band (L6, which is our P-5) hold up. Weight concentration (L1) mostly measures where authors put the hard part rather than creating difficulty. The section 8 recipe is only half supported: the held-out tier at weight 5 does the work, and no task in the corpus stacks all seven steps.

## 1. Data set reconciliation
- `Final_Delivery/` has 94 entries: 92 task dirs plus `TASK_DIFFICULTY.md` and `leaderboard.md`. 90 dirs have `trajectories/claude-opus-5/run_1/report.json`. 11750b7a and 4ef4340d have only `claude-opus-5-5/run_1/report.json` (s01_reconcile.py).
- The doc's 85 is the repo state at Anubis_Tasks_Samples commit `95f8fb386` (27 Oct 18:23 IST, "…leaderboard for 85 tasks"). At that commit there were 85 dirs: 83 opus-5 reports plus the 2 opus-5-5 reports. That set reproduces every headline figure exactly (mean 51.95, median 53.99, 2,950 checks, 1,842 criteria, 8,429 / 4,514 positive weight; s03_snapshot.py). So the doc's line 4-5 claim ("every bundle carries exactly one claude-opus-5 report") is wrong for 2 of 85, and 2.4% of its sample is a different model. On the 83 opus-5 runs alone the mean is 52.15 and the median 56.20.
- Since that commit, 7 dirs have been added (75407a55, 8956ff8b, 98ed74c1, 9bb234eb, b6237098, f3381a1c, fa7c65bd). `git diff --name-status` shows additions only, so no existing report was edited. On today's 90 opus-5 reports: mean 50.58, median 52.66, 22 tasks below 40 and 11 below 25 (s04_claims.py cur90). 9bb234eb and fa7c65bd have identical scores (23.08/21.43); possibly duplicate bundles, UNVERIFIED.
- Field semantics (doc section 9): recomputing tests%, judge% and final from the raw report fields matches the stored values on 90 of 90 reports (s01). The three samples were 59417607 (7/97 = 7.22, 14/58 = 24.14, final 15.68), 8defd7be (9.06) and ec7941e5 (72.89). The alternative reading (a judge negative with passed=true counts as fired) mismatches 89 of 90. One doc error: the line 417 tests formula leaves out fired test negatives. The stored values subtract them (8d3e20fb 41.24 vs 44.33; b625f36e 22.68 vs 25.77).
- Overlap with `anubis-stage-1` (s06_stage1_overlap.py): 86 task ids are shared (all 85 doc tasks plus b6237098). report.json is byte-identical in 85; in 0b27b9dc the only difference is int vs float weights, with the same final 61.39. instruction.md, test_output.py and judge.toml are identical in 86 of 86; task.toml is identical in 50 of 86. Final_Delivery only: 6 of the 7 later additions. anubis-stage-1 only: 275f885b, 2b00e081, ca422d37, d7ab7d6c. R4 will therefore re-mine mostly the same 86 runs.
- 4 of the doc's tasks are our own pushed tasks (s08_ours.py, matched on stored scores and author Ayush Sah):
  - 42e79476 = dispatch-plan-reoptimization (14.7)
  - b47fd5f7 = emberforge (59.91)
  - 8fbe0e42 = match-replay (43.42)
  - b5c7b14c = caldermoor (31.61)

  For caldermoor, our registry has 94.33/8.57/51.45 while the Final_Delivery report has 54.64/8.57/31.61: same judge, tests about 40 points lower. Whether the bytes are the same is UNVERIFIED. If they are, this is the ±20 variance from G13 seen again.

## 2. Claim table
All 68 claims, with doc line, our number ([cur90] where it differs), script and verdict. The same rows are in `claims.csv`.

| id | doc line | claim | our number | script | verdict |
|---|---|---|---|---|---|
| C01 | 3-5 | 85 bundles, each with exactly one trajectories/claude-opus-5/run_1/report.json | 85 dirs at git 95f8fb386, 83 opus-5 + 2 opus-5-5 (11750b7a, 4ef4340d); today 92 dirs, 90 opus-5 (set reproduces exactly only with the 2 opus-5-5 runs included) | s03_snapshot.py | PARTLY |
| C02 | 7 | 2,950 graded test checks and 1,842 judge criteria | 2950 / 1842 [3065 / 1963] | s03_snapshot.py | CONFIRMED |
| C03 | 8 | Judge model gpt-5.6-sol on every run | all 92 reports | s01_reconcile.py | CONFIRMED |
| C04 | 14 | 4,792 graded items | 2950+1842 = 4792 | s03_snapshot.py | CONFIRMED |
| C05 | 23-28 | Headline: mean 51.95, median 53.99, range 9.06-72.89, >=60 36, <40 18, <25 7 | identical [cur90 50.58/52.66/36/22/11] (true for the 27 Oct snapshot only) | s04_claims.py | CONFIRMED |
| C06 | 34-35 | Tests mean 43.91 median 42.00, 3,734/8,429; judge 59.99/65.00, 2,950/4,514 | identical | s04_claims.py | CONFIRMED |
| C07 | 37 | Tests half is the weaker half in 55 of 85 | 55 [57 of 90] | s04_claims.py | CONFIRMED |
| C08 | 39-40 | No task above 72.89 and none at 0 | max 72.89, min 9.06 | s04_claims.py | CONFIRMED |
| C09 | 51-53 | 59417607 passed the six shipped_* checks and run_output_lists_reports | same 7 | s04_claims.py | CONFIRMED |
| C10 | 54-59 | 59417607 failed hidden_extract_01..08, eight unseen inputs | 18 failed (hidden_extract_01..18, all w5) (count wrong; direction right and stronger) | s04_claims.py | WRONG |
| C11 | 63-66 | 8defd7be passed 2 plumbing checks, failed all eight full_ledger_on_unseen_run_* | 2 passed; 11 full_ledger (alpha..kilo) failed, plus 26 w1 rule checks | s04_claims.py | PARTLY |
| C12 | 67-70 | d49e259f passed 3 checks, failed all eight mode_bit_* | 4 passed (also screened_intake_mode_zero_resolves); 13 mode_bit_* failed | s04_claims.py | PARTLY |
| C13 | 85 | Held-out checks: 361, 73% failed, 1,256 weight lost (77% of tier) | 374/73.3%/1322/77.3% (my regex; 69-78% over 4 regex variants) (rate robust to taxonomy; counts not reproducible exactly) | s04_claims.py | CONFIRMED |
| C14 | 86 | Cross-file lookup chain: 105, 64%, 281 (75%) | 97/60.8%/247 (71.6%) (taxonomy) | s04_claims.py | PARTLY |
| C15 | 87 | Exact value checks: 623, 60%, 1,588 (66%), largest absolute loss | 590/59.3%/1494 (65.2%); largest loss yes (rates within 1 point) | s04_claims.py | CONFIRMED |
| C16 | 88 | Edge cases and traps: 263, 54%, 623 (59%) | 265/52.8%/610 (57.1%) | s04_claims.py | CONFIRMED |
| C17 | 89 | Determinism: 58, 31%, 72 (40%) | 59/30.5%/72 (40.2%) | s04_claims.py | CONFIRMED |
| C18 | 90 | Plumbing (exists, runs, parses, CLI): 118, 17% | 150/14.0% (taxonomy) | s04_claims.py | PARTLY |
| C19 | 91 | Shape/schema: 93, 15% | 104/24.0% (taxonomy; mine fails more) | s04_claims.py | PARTLY |
| C20 | 93-95 | 24 tasks with plumbing and exact checks, 15 show 'plumbing passes, exact fails' | 56/19 (my taxonomy) (doc gives no rule for 'signature') | s04_claims.py | UNTESTABLE |
| C21 | 101-103 | Failure by weight: w1 107/572 19%, w3 301/704 43%, w5 737/1149 64% | identical [cur90 18/42/66%] | s04_claims.py | CONFIRMED |
| C22 | 105-107 | Weight scale is an accurate difficulty predictor | within-task: w5 pass < w1 pass in 73 of 83 tasks (36% vs 88%) (predictor yes; it labels hard checks, it does not create difficulty (see levers L1)) | s04_claims.py | CONFIRMED |
| C23 | 109 | 26 of 85 tasks failed every weight-5 check | 26 [28 of 90] | s04_claims.py | CONFIRMED |
| C24 | 110-112 | Then tests capped ~20-35% and final cannot pass 50 | 7 of 26 have final >= 50 (5e4fd36d 71.65); tests median 8.0 (judge half carries those 7) | s04_claims.py | WRONG |
| C25 | 118-131 | Token failure table (extract 99%, bit 96%, mode 92%, heldout 86%, ... exact 61% / 552 / 1,422) | identical (tokens concentrate: bit 26 of 50 from d49e259f; extract from 8 tasks; generalises from 4) | s04_claims.py | CONFIRMED |
| C26 | 132-133 | Reliable tokens: delivered 5%, artifacts 5%, cli 18%, artifact 18%, config 21%, shipped 22% | 4.7/5.4/17.5/17.7/21.4/21.8 | s04_claims.py | CONFIRMED |
| C27 | 137-141 | Most failed checks: zone_totals_match 7, corpus_index_match 7, posture_match 7, ... | identical | s04_claims.py | CONFIRMED |
| C28 | 143-147 | aggregates_* fails across 7 serializations together: one computation, not seven | 7 tasks (all Nikhil Bansal): 5 fail 0/8-0/10, 2 pass 7/7 and 49/50 (all-or-nothing; one author) | s04_claims.py | CONFIRMED |
| C29 | 155-158 | Judge by target: trajectory 893 32%, final_answer 286 34%, ufm 184 30%, state_change 71 27% | identical (positive criteria) | s04_claims.py | CONFIRMED |
| C30 | 162-163 | Importance: critical 221/664 33%, important 233/770 30% | 33.3% / 30.3% | s04_claims.py | CONFIRMED |
| C31 | 165-166 | Judge failure flat across targets and importance | 27-34% across all cells | s04_claims.py | CONFIRMED |
| C32 | 170-175 | Judge themes: verify 52%, derive 48%, cover 34%, honest 33%, order 31%, read inputs 23% | verify 51.9%, derive 37.7%, cover 32.7%, honest 34.3%, order 31.9%, read 24.4% (my regex) (derive-not-shortcut not reproduced) | s04_claims.py | PARTLY |
| C33 | 185-187 | Lack of self-verification is the mechanical cause of the held-out failures | no counterfactual in one run per task (INFERRED; our 1b H9 habit says the same from trajectories) | s04_claims.py | UNTESTABLE |
| C34 | 193 | Test-side negatives: 525 defined, 2 fired | 525/2 (both firing tasks (8d3e20fb, b625f36e) are on our section-8 holes list) | s04_claims.py | CONFIRMED |
| C35 | 194 | Judge negatives: 408 defined, 27 fired in 21 tasks | 408/27/21 [438/29/23] | s04_claims.py | CONFIRMED |
| C36 | 196-199 | Hardcoding, third-party deps, corpus reading, writing /app/data effectively extinct | 0 such test negatives fired | s04_claims.py | CONFIRMED |
| C37 | 201 | The 27 judge firings are almost all overclaiming | 16-17 of 27 claim wording; 10 are scope, helper-script, literal or restart acts | s04_claims.py | PARTLY |
| C38 | 212-213 | Honesty negatives are the only negatives that earn their keep | fired judge negatives cost 89 judge points in total vs 1,564 lost on positives (5.4%) (true they fire; effect on score is small) | s04_claims.py | PARTLY |
| C39 | 219-220 | Reward = 0.5*test/sum(pos) + 0.5*judge/sum(pos), unclamped | reproduces 90/90 stored finals | s01_reconcile.py | CONFIRMED |
| C40 | 223-225 | Lose the w5 tier: tests near 25, run caps near 62 | cap if all non-w5 passed: median 36.6, range 2.4-72.2 (depends on weight mix) | s04_claims.py | PARTLY |
| C41 | 226-228 | Best: ec7941e5 91.55/54.24/72.89, 5e4fd36d 44.44/98.86/71.65 | identical; c9d7b490 71.83 (54.0/89.66) is 2nd and omitted | s04_claims.py | CONFIRMED |
| C42 | 228-229 | No task has both halves strong at once | 0 tasks with both >= 70; tests>=85: 10, judge>=85: 19 | s04_claims.py | CONFIRMED |
| C43 | 231-234 | The halves fail for different reasons; 50/50 makes a hard ceiling in the low 70s | r(tests, judge) = -0.40 pooled, -0.32 within author [-0.33 / -0.24] (anti-correlation is new and stronger than the doc says) | s05_confounds_recipe.py | CONFIRMED |
| C44 | 246 | L1: heavy share r = -0.38 with tests half, the strongest lever measured | -0.38 (within author -0.38); held-out w5 share -0.40 (within -0.43) (held-out weight at w5 is as strong or stronger) | s05_confounds_recipe.py | PARTLY |
| C45 | 263-268 | Quartiles: Q1 41% 65.4/58.6, Q2 56% 35.3/51.4, Q3 71% 45.0/52.5, Q4 92% 30.6/45.6 | identical (non-monotone Q2<Q3) | s04_claims.py | CONFIRMED |
| C46 | 270-271 | Q1->Q4 costs 35 tests points and 13 final points | 34.8 / 13.0; within-author r_final -0.14 (arithmetic right; final effect halves after the author control) | s05_confounds_recipe.py | PARTLY |
| C47 | 280-281 | Any held-out weight 52.1 final vs 51.6 without | 52.1 vs 51.7 | s04_claims.py | CONFIRMED |
| C48 | 291 | Median task: 53 input files, 25,574 input lines | 53 / 25,171 (line-count method) | s04_claims.py | PARTLY |
| C49 | 293-295 | resolves 66%, mode/bit 92-96% | 66.0 / 92.5 / 96.0 (mode/bit rests on 6-10 tasks, mostly d49e259f) | s04_claims.py | CONFIRMED |
| C50 | 305 | Shape checks pass at 85% | 76% (my shape regex) (taxonomy) | s04_claims.py | PARTLY |
| C51 | 309-311 | Median 20 criteria (8-35); 908 trajectory, 294 final_answer, 187 ufm, 72 state_change; 779 important, 682 critical | median 20 (8-35) right; positive 893/286/184/71 and 770/664, all 1156/361/231/94 and 923/919 (second half matches no subset and contradicts section 4) | s04_claims.py | WRONG |
| C52 | 323-325 | A -5 cheat is 2.5 final points on a 100-weight positive total | 0.5*5/100*100 = 2.5 (arithmetic) | - | CONFIRMED |
| C53 | 342-356 | Correlation table (11 features) | 9 of 11 identical; held-out share -0.26/-0.35 vs doc -0.19/-0.21; cost, tokens within 0.01 | s04_claims.py | CONFIRMED |
| C54 | 360-362 | Bulk (lines, bytes, files) does nothing | r -0.04..+0.08; within-author +0.01..+0.06 | s05_confounds_recipe.py | CONFIRMED |
| C55 | 363-364 | More checks do not help | -0.02 final; +0.13 tests | s04_claims.py | CONFIRMED |
| C56 | 365-368 | Longer instructions correlate slightly positively | +0.11 [+0.17]; within author +0.16 (not significant at n=85) | s05_confounds_recipe.py | CONFIRMED |
| C57 | 369-371 | Median 5.38M tokens, $6.12; tokens and cost are symptoms not levers | 5.64M / $6.32 (n=82); causal claim untested | s04_claims.py | PARTLY |
| C58 | 402-405 | Recipe profile: tests 5-25, judge 25-45, final 15-35; the seven tasks below 25 all have it | tests in range 2/7, judge 3/7, final 5/7 (5 of 7 have tests below 5 or judge below 25) | s05_confounds_recipe.py | WRONG |
| C59 | 375-396 | Stacking L1+L2+L3+L4+L5+L6+L7 holds Opus 5 under 40 | steps 1+3 matched by 3 tasks (9.06, 33.9 [hole task], 71.83); held-out w5 share >= 50%: 8 tasks, mean 34.8, 5 of 8 < 40 (the held-out w5 tier is the part that carries it; the full stack is untested (0 tasks match all steps)) | s05_confounds_recipe.py | PARTLY |
| C60 | 417 | Tests half = max(0, passed positive weight / positive weight) | stored values subtract fired test negatives (8d3e20fb 41.24 vs 44.33; b625f36e 22.68 vs 25.77) (minor: 2 tasks) | s05_confounds_recipe.py | WRONG |
| C61 | 421-426 | Field semantics for positive/negative tests and criteria | reproduces 90/90; alternative judge reading fails 89/90 | s01_reconcile.py | CONFIRMED |
| C62 | 431-433 | /r/ < ~0.21 is not distinguishable from zero at n = 85 | critical r(83 df, 5%) = 0.213 | - | CONFIRMED |
| C63 | 248 | L3: cross-file chain checks fail 64% | 60.8% (taxonomy) | s04_claims.py | PARTLY |
| C64 | 249 | L4: exact checks lose 19% of all available test weight | 18.8% from doc figures; 17.7% my regex | s04_claims.py | CONFIRMED |
| C65 | 255 | 0600 file-mode bug zeroed an EXEC tier; unpinned litellm in verifier image | not in report.json | - | UNTESTABLE |
| C66 | 281-283 | Where held-out tiers carry the w5 band, the model loses the whole band | 8 tasks with held-out w5 share >= 50%: tests median 7, 7 of 8 below 36; f357cd96 70.71 | s05_confounds_recipe.py | PARTLY |
| C67 | 106-107 | Weight scale predicts difficulty without anyone having tuned it for that | author eta^2 on heavy share 0.47 (INFERRED: authors put w5 on the core outcome, which is the hard part; weight follows difficulty) | s05_confounds_recipe.py | UNTESTABLE |
| C68 | 40 | No task is beyond it, none fully solved | min 9.06, max 72.89 | s04_claims.py | CONFIRMED |

## 3. Lever verdicts
The full rows (evidence for and against, our data, legality, our name) are in `levers.csv`.

| lever | verdict | why, in one line | how to apply |
|---|---|---|---|
| L1 weight on w5 | PROMISING | Weight-5 checks fail more inside the same task (73 of 83). But authors' choices explain 47% of heavy share, and once author is controlled for, the effect on final drops from -0.24 to -0.14. Quartiles are non-monotone. | Amplifier only. Put w5 on the held-out core (TS-20). Never re-weight after a run (KNOWLEDGE T:113). |
| L2 held-out instances | PROVEN | Within the same task, shipped checks pass 62% and held-out 42%. At equal weight 5: 43% vs 23%. Held-out w5 share: within-author r_tests -0.43, r_final -0.31. Our dispatch (14.7) and the schema/sentinel hidden-scale losses agree. | Shape D / G3 with G5, 0b and W5 BRANCH_FIRE. Each hidden corpus weighted independently. |
| L3 interlocking inputs | WEAK | Rests on a regex taxonomy only, with no within-task contrast. 'bit'/'mode' come mostly from d49e259f. Our L4 multi-document lever leaked (CR-5, 1C). | Only inside a held-out tier. |
| L4 exact published contract | PROMISING | Exactness is how checks are graded, not what makes them hard: exact checks on shipped data mostly pass (the 'shipped' token fails 21.8%). | G1 + CL-4 sentence as the multiplier on held-out corpora. |
| L5 trap tiers | WEAK | 53% failure on regex-matched checks. The 92-96% headline comes from 6-10 tasks. Our habit levers leaked (1C). | Hidden-only fixtures for stated branches (S6). |
| L6 process criteria | PROVEN | The verify theme fails 52% vs 24% for reading inputs. 4 of the 10 lowest judge halves in the 85 are our probe-band tasks. Our gate runs average rubric 23.5. | J2 probe band (P-a..P-h), oracle shows each act. |
| L7 honesty negatives | WEAK as hardness | They fire (27 of 408), but cost 89 judge points in total, 5.4% of what is lost on positive criteria. Only about 16 of the 27 are overclaims. | Keep J3a-c for honesty; do not budget points on them. |
| L8 determinism | WEAK | 0.9% of positive weight. | G6 minimum only. |
| L9 reward geometry | WEAK (structural) | "Cannot pass 50" is false for 7 of 26. The ceiling is the anti-correlation (N1), which the doc does not measure. | Gate arithmetic only. |
| L10, L11 guardrails | N/A-GUARDRAIL | Required, but they add no hardness. The 85 still include hole tasks that passed QC (section 8 list). | Keep; add a "genuine loss" read before using a task as evidence. |

Legality: no doc lever is illegal as written. The doc itself bans hidden conventions (lines 300-305, 389) and requires DS-21. Its two strongest examples, however, rest partly on tasks our rules call holes:
- 3f39299a (39.66; hidden rule, LEVER_RULES 8:234) feeds L2.
- 6d12f970 (33.9) is one of the two tasks that satisfy recipe steps 1+3.
- The only two test-side negative firings (8d3e20fb, b625f36e) are both in hole tasks.

L1 used as "raise the weight because Opus fails it" would break TS-20 / KNOWLEDGE T. The doc does not say that, but its dial ("put the core on weight 5") must be read through TS-20.

## 4. New lever candidates
- **N1. Pair the two channels (held-out w5 tier + probe band).**
  - Mechanism: across tasks the halves are anti-correlated (r = -0.40, -0.32 within author; s05). A task whose tests collapse usually keeps a high judge:
    - d9e08524: 2.88 / 94.74, final 48.81
    - 8eae0f87: 6.54 / 91.49, final 49.02
    - 5 of the 18 tasks below 40 still had judge >= 60, and each needed tests <= 11.
  - Our gate runs show the mirror image: probe band rubric 0-25 but tests 73-85, best 40.48.
  - Legality: S2/G5 plus J2, each already legal.
  - Proof: on frozen QC-passed bytes, 1 valid run with tests <= 60 and rubric <= 20, and 3 fresh blind reads with tests <= 60, losses WRONG or v3.5 hidden-scale.
- **N2. Held-out weight-5 share of at least 50% (the dial for L2).**
  - Evidence: 8 tasks at or above 50%: mean final 34.8, tests median about 7, 5 below 40 (cur90: 9 tasks, mean 32.8, 6 below 40). It is the strongest single predictor (within-author r_tests -0.43).
  - Caveats: n = 8, 3 from one author, 1 hole task.
  - Apply: G3 Shape D with at least 6 hidden corpora at w5.
  - Proof: 2 of 3 blind reads lose at least 40% of positive test weight on the held-out tier while passing the shipped-data checks.
- **N3. Small positive judge total (WEAK, do not design for it).** The lowest judge halves come from 4-9 positive criteria (725e575c jw 12 → -25.0; 42e79476 jw 16 → -6.25). One criterion is then worth 8-25 judge points, which raises variance. Note it when reading a low judge.

Under-weighted by the doc, already in our rules: P-5 probe band (judge), P-3 hidden larger instances (42e79476 is our dispatch at 14.7), and the S3 unique-fit habit (18b5d99f).

## 5. Gate < 40 recommendation
- Arithmetic: final < 40 means tests + rubric < 80 (s08 O4). At our gate-run test levels (73-85), the rubric would have to be 7 or below, down to -5, which a legal judge does not reach (the probe band gives 0-25). Our 10 valid gate runs: 1 below 40 (dispatch 14.7, tests 35.64), 4 below 50, mean tests 78.7, mean rubric 23.5.
- Honest < 40 shapes in Final_Delivery: 18 tasks, 15 after removing hole tasks. Tests median 9.36, judge median 35.51; 17 of 18 have tests < 85 and judge < 85. Exception: 725e575c (tests 96.55, judge -25.0 from a 12-point judge with one fired negative). Two routes:
  - (a) Held-out collapse: tests <= 11 with judge 15-74 (8defd7be, 59417607, 18b5d99f, 9f5486ac, 80202e15).
  - (b) Mid tests with a crushed judge: 5b2b0901 36.56/6.98, b5c7b14c 54.64/8.57, b51a883e 62.5/15.79.
- Recommendation:
  - Keep tests < 85 as a side condition. It is the only one still binding: it blocks the "tests high, negatives push the judge below zero" route seen in 725e575c.
  - Rubric < 85 is implied by final < 40 (rubric 85 would need tests < -5) and can be dropped as redundant. Keeping it costs nothing.
  - The working design target should be **tests <= 60 with rubric <= 20** (N1). Any tests figure of 65 or more needs rubric <= 15 and leaves no variance margin (±10 final).
  - Raise v3.6's first-write aim from tests <= 75 to tests <= 60, and the blind bar from <= 80 to <= 65.

## 6. What is new vs our prior studies
Studies compared:
- delivery_study (21 tasks, `synthesis_6c6fcf3/DELIVERY_LEARNINGS.md`)
- delivery_study2 (19 tasks, g1-g4 + `synthesis_720e1d7/SUMMARY.md`)
- peer_levers G1-G5 (summaries read)
- hardness_notes + `verify_ec452c9` (114-claim check of HOW_TO_MAKE_HARD_1/2)
- trajectory_hardening/research_cb612aa (TRIP method)

Already known: unseen inputs × whole-unit exactness drive separation (DL:47-56 TD1-TD3 = doc L2+L4), the degenerate shipped instance (S2), the probe band (SUMMARY item 3), honesty negatives over figure criteria (item 4), wrong-reading test negatives never fire (DL:54 TD8; doc's 2 of 525), variance ±20 (G13), and the hole tasks.

New here:
- (1) An 85-task, per-check quantification (weight 1/3/5 failure rates; within-task shipped vs held-out contrasts).
- (2) Tests/judge anti-correlation (-0.40) as the cause of the ceiling.
- (3) Author explains 36% of final variance; L1 weakens under that control.
- (4) The held-out w5 share threshold (N2).
- (5) Our probe-band tasks hold 4 of the 10 lowest judge halves in the delivered set, independent confirmation of P-5.
- (6) The doc set includes 2 opus-5-5 runs.
- (7) A ±40 tests gap between our caldermoor registry run and its Final_Delivery report (bytes UNVERIFIED).

Peer_levers G4 found the losses in 2 of its tasks came from an ambiguous definition or undefined keys, not stated rules. So delivered low scores are not all honest, which the doc assumes.

## 7. Questions
For Ayush:
1. Should the gate stay final < 40 with tests < 85 and rubric < 85, or become final < 40 with tests < 85 only? Recommended: drop rubric < 85 as redundant, keep tests < 85, design to tests <= 60 / rubric <= 20.
2. Adopt N1 + N2 as the default build shape (Shape D with held-out w5 share >= 50% plus the probe band) for the next pilot? Recommended: yes, one pilot first, judged by the N1 proof bar.
3. Change v3.6's first-write aim to tests <= 60 and the blind bar to <= 65? Recommended: yes. At tests 75-80 the gate cannot be met.
4. Mark L3, L5, L7 and L8 as WEAK in LEVER_RULES (not deleted)? Recommended: yes, citing this file.

For the QL:
5. 11750b7a and 4ef4340d are claude-opus-5-5 runs inside the "Opus 5" sample. Intended? Recommended: report the 83 opus-5 runs separately (mean 52.15).
6. What exact rule did section 3 use for the theme regexes and the "plumbing passes, exact fails" signature (24/15)? Recommended: publish the script so the counts can be reproduced.
7. Section 6 L6 counts (908/294/187/72; 779/682) match neither the positive nor the full criteria set. Recommended: replace them with section 4's 893/286/184/71 and 770/664.
8. Do 59417607's 18 hidden extracts ("01..08" in the doc) and the recipe claim "seven below 25 all have this profile" (true for 2 of 7) need correction? Recommended: yes; the claims stay right in direction.

## Lessons for the master
- The QL doc's numbers reproduce. Its levers are correlations from one run per task, confounded by author (eta² 0.36). Trust within-task contrasts over pooled r.
- Held-out w5 weight (L2/N2) and the probe band (L6/P-5) are the two proven levers in both data sets. Everything else is an amplifier or weak.
- The ceiling comes from the anti-correlated halves: final < 40 needs tests <= 60 and rubric <= 20 together. Our builds stop at tests 73-85.
- Our tests are not the doc's tests: 4 of its 85 tasks are ours, and our caldermoor scored about 40 tests points apart between two records.
- Before citing a delivered task as lever evidence, check it against the section 8 holes list (3 of the doc's key examples are holes).
