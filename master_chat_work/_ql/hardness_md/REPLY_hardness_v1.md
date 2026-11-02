Hi Sugam,

Thank you for sharing hardness.md. We checked it against the delivered tasks with scripts and are sending what we found, the corrections, four questions, and what we take from it. Short version: the numbers reproduce well, and two of the patterns hold up strongly; a few counts and the section 8 recipe need correction.

## 1. How we checked
- Set: Anubis_Tasks_Samples `Final_Delivery/` at commit `95f8fb386` (27 Oct, "leaderboard for 85 tasks"). At that commit the 85 tasks reproduce every headline figure exactly (mean 51.95, median 53.99, 2,950 checks, 1,842 criteria, 8,429 / 4,514 positive weight).
- Scores recomputed from the raw report.json fields match the stored tests %, judge % and final on 90 of 90 reports.
- One run per task, so each task's score is one sample. We trust contrasts inside the same task more than correlations across tasks.

## 2. Verdict on the 68 claims
| verdict | count |
|---|---|
| Confirmed | 41 |
| Partly right (direction right, count or scope off) | 18 |
| Wrong | 5 |
| Cannot be tested from report.json | 4 |

The full claim table (doc line, your number, our number, script) is attached as `claims.csv`.

## 3. The five claims we found wrong
| doc line | claim | what we see |
|---|---|---|
| 54-59 | 59417607 failed `hidden_extract_01..08`, eight unseen inputs | it failed 18 (`hidden_extract_01..18`, all weight 5). Direction right, effect stronger. |
| 110-112 | a task that fails every weight-5 check has tests capped near 20-35% and cannot pass final 50 | 7 of the 26 such tasks have final >= 50 (5e4fd36d: 71.65); the judge half carries them. |
| 309-311 | criteria split 908 / 294 / 187 / 72 and 779 important / 682 critical | the positive criteria give 893 / 286 / 184 / 71 and 770 / 664 (as in your section 4); the section 6 figures match no subset. |
| 402-405 | the seven tasks below 25 all have the profile tests 5-25, judge 25-45, final 15-35 | tests is in range for 2 of 7, judge for 3 of 7, final for 5 of 7. |
| 417 | tests half = passed positive weight / positive weight | the stored values also subtract fired test negatives (8d3e20fb 41.24 vs 44.33; b625f36e 22.68 vs 25.77). Minor: 2 tasks. |

Also on lines 3-5: 2 of the 85 (11750b7a, 4ef4340d) carry a claude-opus-5-5 report, not claude-opus-5. On the 83 opus-5 runs alone the mean is 52.15 and the median 56.20.

## 4. Questions for you
1. Were the two claude-opus-5-5 runs (11750b7a, 4ef4340d) meant to be in the Opus 5 sample? If not, the 83-run figures above may be the cleaner baseline.
2. Which exact rule did section 3 use for the theme regexes and the "plumbing passes, exact fails" signature (24 / 15)? With our own regexes the rates land within a few points, but the counts do not reproduce. Could you share the script?
3. Should section 6's L6 counts be replaced by section 4's (893 / 286 / 184 / 71 and 770 / 664)?
4. Should 59417607's "01..08" become "01..18", and the recipe line read "5 of the 7 below 25" instead of "all seven"? Both claims stay right in direction.

## 5. What holds up
Two patterns are supported inside the same task, not only across tasks:
- **Held-out instances (L2).** In the same task, checks on shipped data pass 62% and checks on held-out inputs 42%; at equal weight 5 it is 43% vs 23%. Tasks with at least half of the weight-5 weight on held-out inputs (8 tasks) average final 34.8, and 5 of the 8 are below 40.
- **Process criteria in the judge (L6).** "Verify" criteria fail 52% vs 24% for "read the inputs".

Weaker than the doc suggests:
- **Weight on weight-5 (L1).** The predictor works: weight-5 checks fail more than weight-1 checks in 73 of 83 tasks. But the author explains much of where weight goes; once that is controlled, the effect on final roughly halves (-0.24 to -0.14). It labels the hard part more than it creates it.
- **Interlocking inputs (L3), edge-case tiers (L5), determinism (L8).** The headline rates rest on a few tasks (the 92-96% mode/bit figures come mostly from d49e259f), or on a small weight share.
- **Honesty negatives (L7).** They fire (27 of 408), but cost 89 judge points in total: 5.4% of what is lost on positive criteria.
- **Section 8 recipe.** No task in the set has all seven steps, so the full stack is untested. The held-out weight-5 tier carries most of what the recipe predicts.

## 6. Three new observations
1. **The two halves pull against each other.** Across tasks, tests % and judge % are negatively correlated (r = -0.40; -0.32 within the same author). A task whose tests collapse usually keeps a high judge (d9e08524: 2.88 / 94.74, final 48.81). That anti-correlation, not the 50/50 formula, is what makes the ceiling. A final below 40 needs both halves low at once (for example tests <= 60 with judge <= 20).
2. **Held-out weight-5 share of 50% or more** is the strongest single predictor we found (within-author r with tests -0.43). The caveats are n = 8, three of them from one author.
3. **A small positive judge total raises variance.** With 4-9 positive criteria, one criterion is worth 8-25 judge points (725e575c: a 12-weight judge gives -25.0). This is worth noting when reading a low judge; it is not a design target.

## 7. Note on four of our tasks in the set
Four of the 85 are ours: 42e79476, b47fd5f7, 8fbe0e42, b5c7b14c. For b5c7b14c, our own record of a run differs from the Final_Delivery report by about 40 tests points with the same judge. We have not compared the bytes, so we cannot say yet whether it is the same package or run-to-run variance.

If you read any of the corrected points differently, tell us the line and we will look again.

Regards,
Ayush
