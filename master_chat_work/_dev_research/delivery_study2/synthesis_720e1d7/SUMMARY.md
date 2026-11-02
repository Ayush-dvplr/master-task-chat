# SUMMARY (board 720e1d7): what 19 delivered peers change in our rule book

Files here: CONFLICTS.md (18 rows + QL draft), LEVER_RULES_v3_DRAFT.md (full replacement), TEMPLATE_CHANGES.md (line edits for 5 templates), BUILD_RECIPES.md (2 recipes + parked table), TOOL_CHANGES.md (stacking_check, precheck).
Final reward = half tests + half judge. Kill rule: park when the probe's final is above 70.

## The 5 biggest changes
1. **Hardness comes from breadth or a quiet shipped instance, not from a few sharp levers.** Delivered peers lost most on 30-80 plainly stated rules over many files (9125255a 124 pts, daaca581 121, 8764bfdd 100) or on a shipped instance that never fires the hard branch while hidden corpora do (266 pts over 3 tasks). New Shape B (breadth) and Shape D (quiet instance, ≥70% hidden weight) replace "3 levers each ≥25%". (Draft section 1, 1A; g2 summary :23, g1 summary :23.)
2. **Unique fit instead of first fit.** When the rule says "the one candidate that fits", Opus stops at the first fit. 205 pts across 2 tasks. Safe and fully stated. (g1 summary :24.)
3. **The judge half becomes a probe band.** 8-16 trajectory criteria at weight 3 that ask for acts Opus skips: run on an edge input, show one instance, recompute outside the program, rerun on an altered copy. Peers with tests 90-96 still finished at 57-63 because judges scored 25-33. Our version keeps JD-7: solve.sh performs and prints each act. (Draft J2, J2a; g3 summary :7-13, :25.)
4. **Drop figure criteria; add honesty negatives that fire.** Opus answered every figure criterion right. What cost it: a figure in the reply that differs from the file (-5), claims of checks never run (-3), misstated size of its own check (-3). Behavioural handler criterion replaces the "maintainable" one. (Draft J1, J3a-c, J4; g4 summary :49-55, g1 summary :30-33.)
5. **A design-stage blind read and a judge estimate.** Before the full build, a blind session solves a prototype; redesign if it is exact on the sample and 3 hidden seeds. Every P13 blind read now scores the judge criteria against its own steps (lower and upper bound), so the kill rule can be applied before a probe. (Draft section 6; TEMPLATE_CHANGES P2 Phase 0b, P13.)

Also kept on purpose: no hidden rules, no trap lists, no wrong-reading detectors, one act ≤ -5 across layers. Peers that broke these lost points to their own holes (draft section 8: 3f39299a 110, 8d3e20fb 38+19, 80877080 43, 7c2e77a1 46).

## Decisions for Ayush (my recommendation in brackets)
- D1. Adopt LEVER_RULES_v3_DRAFT as LEVER_RULES_v3, with lines marked PENDING left out until answered. [Yes]
- D2. Final gate: drop "tests < 100" (_COMMON_RULES_v3:59); keep only final < 70 on 2 runs. Peers pass at tests 90-96. [Yes]
- D3. Kill-rule run variance: park above 75; between 65 and 75 run a second probe and park if the mean is above 70; below 65 keep. Same task scored 37.93 and 17.12 on tests. [Yes]
- D4. Judge = probe band of 8-16 criteria at w3, each shown by solve.sh (`check <id> ok`), 55-70% of positive judge weight. [Yes; needs no QL answer]
- D5. Remove all figure criteria (J1); keep final-reply items and the figure-vs-file honesty negative. [Yes]
- D6. Allow one toy worked example per quiet rule, on values in no data file (W6 change). [Yes]
- D7. Allow breadth: remove "volume" from P2's ban list; Shape B target ≥30 rules, ≥10 files, ≥5 formats. [Yes]
- D8. G3 hidden share by shape: ≥70% for quiet-instance designs, no floor for breadth designs. [Yes]
- D9. One stated all-corpora gate (CL-4). [Do not use until QL Q3 answers]
- D10. Rerun promise naming what changes on fresh inputs. [Do not use until QL Q4 answers]
- D11. Keep the bans: hidden rules, trap lists in data, wrong-reading detectors, double charge of one act. [Keep]
- D12. Next two builds: Recipe A fuel-card settlement (data-pipeline, breadth + decoy with one live fact + buried hidden fixtures, est. final 34.5, upper 50.5) and Recipe B pilotage dues (domain-calculation, quiet instance + unique fit + rare branch, est. 42.5, upper 60). [Yes]
- D13. Judge-only rebuild: caldermoor first (98.45 tests; judge 30 gives 64.2, judge 40 gives 69.2). Others at tests 100 have 5 points of margin at best. [Caldermoor only, then decide]
- D14. Sentinel's 70.0 is not "above 70": unpark it under the new rule, or treat 70.0 as a park? [Run a probe-band rebuild; do not unpark as is]
- D15. Tariff-engine shows 51.66 on record (tests 100, judge 3.33): run one probe to confirm before any rebuild. [Yes]
- D16. Add the design-stage blind read (P2 Phase 0b) before every full build. [Yes]

## QL questions (send as one message)
1. JD-7 (04:76): may a judge criterion grade an act in the agent's trajectory when solve.sh does not perform that act?
2. JD-15 (04:92): is "The agent runs its program on one input where <stated branch> applies and shows that record and the program's decision" at weight 3 an odds-raising act that passes?
3. CL-4 (FC:491): if instruction.md says a family counts only when every hidden corpus of it is exact, is that gate a pass or a WARN?
4. IN-17 (01:47): may instruction.md say which things change on fresh inputs (sizes, ids, which stated branches occur) without that counting as announcing a trap?

## Notes
- Session rename: name_session.py printed "codex: no match / opencode: [ses_e8805c84cffeH8QtqQ6KcL9h5J]" and did not echo 720e1d7. Not retried.
- Peer numbers from groups without QC reports (all of g3 and g4) show what delivered, not what QC ruled. Rows that rely on them are marked in CONFLICTS.md.
- Our recipes' expected finals are design estimates from peer anchors, not measurements.
