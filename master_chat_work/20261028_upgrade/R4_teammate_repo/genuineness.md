# Phase A: are the 13 low scores genuine? (R4, 1d26a6e)

Method: P14 Phase A, adapted to this repo. Verifier `test-stdout.txt` holds only `reward: x` and `ctrf.json` has no failure messages, so crash vs wrong value was judged from four sources: the artifacts manifest (every deliverable present, status ok, in all 13), `result.json` (exception_info None in all 13), the agent's own shipped-data figures in the judge's exact-figure justifications, and the agent's final message. Script outputs: genuineness_facts.md, losses_models.md, contrast.md.

| id | final | tests / judge | verdict | why (evidence) |
|---|---|---|---|---|
| 8defd7be | 9.06 | 2.41 / 15.71 | FLAG: loss genuine, design RISKY | Agent's own shipped figures are wrong on 19 of 20 (judge #9-#31). It stopped at 56.6 of 90 min saying "I've reached the time limit" (traj step 44), with no time signal in the trajectory. The task withholds ~50 constants and their functional forms (TRUTH.md:3-20). Identifiability rests on a one-step local sweep (TRUTH.md:121-127), not global uniqueness, and the space of forms is not stated anywhere. |
| 42e79476 | 14.70 | 35.64 / -6.25 | GENUINE (one judge quirk) | Wrong shipped objective (judge #1). All 4 hidden sets fail. Rules are stated in the contract (TRUTH.md:3). Negative #7 fired on "about one million" vs 946,000 alternatives; with P=16 that costs 15.6 final points. |
| 59417607 | 15.68 | 7.22 / 24.14 | GENUINE, fair | Shipped w1 checks pass, 18 hidden w5 fail. Offset domain stated (record_dictionary.md:19). Each hidden day has a unique fit (TRUTH.md:29, 69). |
| aa314fee | 17.64 | 3.03 / 32.26 | GENUINE | Agent settled the two withheld rules correctly from the log (final message), but all 8 counterfactual figures are slightly off. Cascade from the carried shortfall (TRUTH.md:8). |
| 9f5486ac | 19.76 | 2.68 / 36.84 | GENUINE-PARTLY | Shipped and hidden exacts all fail. Whole-document exact tests plus the 100-file HELD gate (TRUTH.md:12) amplify the loss. Wrong value is INFERRED (summary says PUBLISHED). |
| d49e259f | 20.28 | 6.38 / 34.18 | FLAG: loss genuine, design RISKY | Agent settled 4 of 13 mode bits (final message). The meaning of each bit is stated nowhere (instruction.md:7; TRUTH "undocumented and carry most of the weight"). The bin digests only confirm a guess (TRUTH ~L231); they do not bound the hypothesis space. |
| 5b2b0901 | 21.77 | 36.56 / 6.98 | FLAG: loss genuine, design RISKY, plus an instructed cap | 56 constants are named nowhere (TRUTH.md:10-20). The evidence "carries no partial signal" (TRUTH.md:51). instruction.md:36 orders the agent to stop constant recovery after 1500 s. Its own message admits the digests do not match. |
| df8f123b | 25.30 | 11.84 / 38.75 | GENUINE | Per-class precedence is fully stated (TRUTH.md:15-25). Six counts are off by one, and source files are not named. |
| b5c7b14c | 31.61 | 54.64 / 8.57 | GENUINE (judge-heavy) | Hidden `*_hard` checks fail; the rules are in 6 documents. The judge is an 8-probe band (J2); Opus used 4% of its time budget. |
| 6d12f970 | 33.90 | 3.09 / 64.71 | GENUINE (prior study) | Valid but wrong on held-out and reformatted corpora. The prior study found judge.toml version skew (A_6d12f970.md:6). |
| 80202e15 | 34.52 | 2.38 / 66.67 | GENUINE | The agent's own check.py reported 101 bad blocks (steps 50, 114), yet it claimed bad=0 (negative #6). Shipped concept exacts fail. |
| 725e575c | 35.77 | 96.55 / -25.00 | FLAG: not a hardness model | Tests nearly solved. The band comes only from the judge: 4 probes of w3 (P=12, so 4.17 final points per weight), two of which ask for behaviour the instruction never requests (#3 run with another --feed dir, #4 reproduce the failure before the first edit), plus negative #5. It fails our tests<85 gate. |
| 18b5d99f | 36.81 | 7.77 / 65.85 | GENUINE (prior study) | Shipped w1 checks pass, 19 hidden w5 fail. The judge loss is 4 negatives (exponential search, hard-coded helper). |

Counts: 9 genuine (59417607, aa314fee, 42e79476, df8f123b, 18b5d99f, 6d12f970, 80202e15, 9f5486ac, b5c7b14c) and 4 flagged (8defd7be, d49e259f, 5b2b0901, 725e575c).

## Flags for Ayush (he asked to be told if he is wrong)
1. Three of the seven Expert tasks are low mainly because the solver must invent unstated forms or meanings: 8defd7be, d49e259f, 5b2b0901. Opus fails them genuinely, but the same design breaks our own rule that every graded rule be stated (P15 v1 context line 19; LEVER_RULES_v3 section 1C pauses stated-rule levers, and L11 is pilot-only). Treat them as models of "evidence induction", not as copyable levers.
2. 725e575c is "Hard" only through a 12-point judge. Opus scored 96.55% on its tests. One extra probe passed would add 12.5 final points and move it to Medium. It is not a hard task by our gate.
3. 5b2b0901 tells the agent to stop after 1500 s (instruction.md:36). Part of its Expert score is the instruction capping effort, and under our rules a stated cap that makes the agent quit is not a lever (v3.5 timeout conditions).
4. README vs run: d22ff871 is listed at 0.51 Easy, but its only stored run scores 32.36 (Hard). INFERRED: the README number comes from another run, which would mean bands can move by about 19 points between runs. That is wider than G13's ±10 final.
5. 42e79476 (yours) lost 15.6 final points to one judge negative for "about one million" vs 946,000. Small judges (P<=20) make each quirk cost ~3 final points per weight.
