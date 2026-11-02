# R4 FINDINGS: learning from the teammates' tasks (anubis-stage-1), board 1d26a6e

Corpus: `anubis-stage-1` at HEAD 79127933 (read only). 90 tasks, 15 contributors, one stored run each (claude-opus-5 on 86, opus-5-5 on 4; judge gpt-5.6-sol). Every number below comes from a script in `scripts/`; each script re-runs from scratch.

## 1. Inventory summary (`inventory.csv`, `features.csv`, `losses.json`)
- Final score: median 52.7, mean 51.6. Tests median 41.0, judge median 64.9. 18 tasks under 40, 39 under 50.
- Bands by stored run: 51 Easy, 25 Medium, 7 Hard, 7 Expert. The README bands differ on 5 tasks; d22ff871 is 0.51 in the README but 32.36 in its run.
- Check counts: tests median 27.5 positive (range 10-76) plus 5 negatives. Judge median 21.5 criteria (range 8-51), 4 of them negative.
- Scoring conventions: `final = (tests + rubric) / 2` on all 90. Rubric negatives apply when `passed=False` (reconciles 90/90). No test negative fired anywhere. 21 of 90 tasks had at least one judge negative applied.
- Where checks run: 86/90 test files rerun the agent's program by subprocess, and 80/90 use seeded generators.
- New vs studied: 60 new; 30 already appear in `_dev_research`. Of the 13 models, only 6d12f970 and 18b5d99f were studied before.
- Contributor in `inventory.csv` comes from task.toml authors. Git authorship is only the uploader (Shreeyank Doliya on 86).

## 2. Genuineness verdicts for the 13 (`genuineness.md`)
9 GENUINE: 59417607, aa314fee, 42e79476, df8f123b, 18b5d99f, 6d12f970, 80202e15, 9f5486ac (PARTLY: whole-document plus HELD gate amplify), b5c7b14c (judge-heavy).

4 FLAGGED:
- 8defd7be, d49e259f, 5b2b0901: the loss is genuine, but the tasks are hard because constant forms or bit meanings are unstated, and the evidence is either a one-step sweep or confirm-only digests. 5b2b0901 also tells the agent to stop recovery after 1500 s (instruction.md:36).
- 725e575c: tests 96.55. The Hard band comes from a 12-point judge alone, so it fails our gate.

Flags for Ayush are in genuineness.md, "Flags".

## 3. Cards (`cards/<id>.md`, the 9 genuine)
| id | final | lever that held (our vocabulary) | how the tests and judge pay |
|---|---|---|---|
| 59417607 | 15.68 | L11 bounded (stated domain -19..19), S2 degenerate shipped, H9 | shipped w1 pass, 18 hidden w5 fail (G3a); 8 what-if figures (J11) |
| aa314fee | 17.64 | L12 shared fill level, L3 never-healing carried shortfall, S5 withdrawn practice, L11 bounded | whole-document exacts on corpus plus 2 unseen; 8 x w5 counterfactual figures |
| 42e79476 | 14.70 | L4 ten corrections across registers and a workbook, P-3 exact optimum on 4 hidden sets | hidden share 0.99; small judge (P=16) |
| df8f123b | 25.30 | L12b per-field-class precedence, authority over recency, L6 scope by definition | shipped-only tests still 11.84; exact counts plus "name the source" |
| 18b5d99f | 36.81 | S2, S3 unique fit, P-1 naive enumeration times out | shipped w1 pass, hidden w5 fail; honesty negatives |
| 6d12f970 | 33.90 | L11 with declared domains, P-4 legal-form robustness, S11 | generalises_* one axis at a time; judge perturbation probes |
| 80202e15 | 34.52 | S1/L4 100 exports, S10 gate, decoy files | T1 hazard-slice tests, one per data hazard |
| 9f5486ac | 19.76 | point-in-time joins, train-only fit frozen, textbook-replacement drift | same T1 template; delta release on own prior |
| b5c7b14c | 31.61 | scoped alias intervals, per-reference resolving instants, carried reserve | hidden *_hard; 8-probe judge band (J2) |

## 4. Contrast (`contrast.md`)
Medians, HardExpert (n=14) vs Medium vs Easy:

| measure | HardExpert | Medium | Easy |
|---|---|---|---|
| weight share on hidden instances | 0.68 | 0.16 | 0.18 |
| hidden-check pass | 0.01 | 0.04 | 0.33 |
| shipped-check pass | 0.20 | 0.25 | 0.65 |
| final points lost on tests | 46 | 38 | 22 |
| final points lost on judge | 33 | 18 | 12 |
| judge exact-figure share | 0.15 | 0 | 0 |

- Splits across 90 (median final, yes vs no):
  - hidden share >= 0.5: 35.7 vs 56.5
  - withheld facts in TRUTH: 48.4 vs 59.9
  - both: 36.8 (n=9)
  - judge exact-figure share >= 0.25: 40.4 vs 57.1
- No signal from: weight concentration (top1 ~0.05, 3 distinct weights everywhere), rerun on fresh inputs (universal), instruction length (652 words), data-file count (Hard has fewer: 41.5 vs 54).
- Time: no timeouts. Hard-task agents used a median 23% of their budget and stopped by themselves, with the first write later (9.5 vs 6.8 min).
- Confounds:
  - HardExpert tasks come from only 8 of 15 contributors; 7 contributors have none (Nikhil Bansal 0/11).
  - Within-contributor contrasts keep the hidden-share and induction effects: Sanvi Gupta 8defd7be vs her 4 Easy; Harshank Kanungo d49e259f vs his 5 Easy; Ayush 42e79476 (hidden 0.99) vs b47fd5f7 (hidden 0.10, hidden pass 1.0).
  - By category, Optimization is 3/6 HardExpert; the other categories are small.
- Our gate (tests < 85, rubric < 85, final < 40) passes 17 of 90.

## 5. Lever candidates
| id | mechanism | evidence | legality (our rules) | how to apply | pilot proof |
|---|---|---|---|---|---|
| LC1 | Bounded induction: a withheld fact with a stated finite domain. The shipped instance is degenerate (many fits work); each hidden instance admits one fit, under the exact rule only | 59417607 (TRUTH.md:29,69), 18b5d99f, 6d12f970 | Legal under Never 6 if the domain is stated and the deciding fact is in EVIDENCE_MAP. Never 11: at most one unlabelled witness, no shipped rollups or expected totals | Build: state the domain in the data dictionary; generate hidden instances with coupled groups larger than shipped | Uniqueness script per hidden instance; 3 blind programs lose >= 25% of test points by valid-but-wrong output |
| LC2 | G3a weight asymmetry: shipped exact checks w1, hidden-instance checks w5 | 59417607 7.22, 18b5d99f 7.77, d49e259f 6.38 | Legal (G3 hidden share); an amplifier, not a lever | Harden: reweight existing checks; keep shipped checks as cheap sanity | stacking_check: a first-write program passes shipped and stays <= 75 on tests |
| LC3 | J11 counterfactual figures: the judge asks for exact what-if figures that need the delivered program re-run on a changed input | 59417607 7/8 wrong, aa314fee 8/8, 5b2b0901; LEAK_LIBRARY:12 says headline figures leak | Legal (J1: not computable by the same code path on shipped data); the questions must be stated in the instruction | 4-8 what-ifs, each flipping one stated parameter that propagates through carried state | Oracle computes each figure by a program rerun; blind run misses >= 3 |
| LC4 | Interlocking allocation plus never-healing carried state: each grant depends on every claim in its cell, and an early error persists to the end | aa314fee (TRUTH.md:7-8), b5c7b14c reserve | Legal (stated rules; L3/P-2) | One shared level per cell; a carried lot with survival; whole-ledger exact checks | A one-rule-flip program loses >= 25% while invariants still pass |
| LC5 | Per-field-class authority order: a different precedence per field class, authority over recency | df8f123b (TRUTH.md:15-25) | Legal if each class's order is written once, without naming the uniform misreading (Never 8) | Spread the 3 class tables over 2-3 documents (L4) | A uniform-order program loses >= 25%, shipped-only tests suffice |
| LC6 | T1 hazard-slice tests: one hidden check per data hazard. Partial credit tracks the hazards covered | 80202e15, 9f5486ac | Legal; avoid a global HELD gate that zeroes everything (P14: PARTLY) | Harden: split whole-document checks by hazard family (TS-13 one property per check) | The per-hazard pass pattern of blind runs differs from the oracle's on >= 4 slices |

Not levers for us (holes): unbounded induction, where forms or meanings are unstated (8defd7be, d49e259f, 5b2b0901; breaks Never 6, and ships reference outputs, breaking Never 11); instructed effort caps (5b2b0901); judge-only bands with P <= 20 (725e575c).

## 6. Angle log and prompt drafts
- `ANGLES.md`: 12 angles tried (A1-A12) and 12 ranked untried (U1-U12). The top three untried are self-test anatomy, judge negative design and an Easy-task leak autopsy.
- `drafts/P15_research_angle_v2.md`: reads the angle log first, must pick >= 2 untried angles, appends rows, re-ranks, adds an own-repo angle and an updated context, and ends with `## Proposed prompt changes` plus a CHANGELOG line.
- `drafts/P14_task_analysis_v2.md`: a delta adding the score-convention check, the no-message genuineness path, identifiability of withheld facts, instructed caps, channel split with 50/P, weight geometry and judge composition.

## 7. Questions for Ayush
1. Do we adopt evidence induction (L11) at all, given that 5 of the 7 Experts rely on it? Recommended: only the bounded form (LC1) with a stated domain and a uniqueness proof per hidden instance, piloted on one task. Never the unbounded form.
2. Is 725e575c a model? Recommended: no. Use it only as an example of judge probes; its tests are 96.55.
3. Should the new target be final < 40 alone, or final < 40 with tests < 85 and rubric < 85? Recommended: keep all three. 725e575c shows a final under 40 can come from the judge alone.
4. Which score defines a band, the README or the stored run? Recommended: the stored report.json, plus 2 extra runs of each of the 13 before treating them as fixed (d22ff871 differs by 19 points).
5. May we ship reference rollups or digests as evidence, as the firmware-recovery template does? Recommended: no, beyond one unlabelled L11 witness (Never 11).
6. Can we ask Aditya Jain (59417607, 18b5d99f) and Anjali Kumari (aa314fee) for their uniqueness scripts? Recommended: yes. Those three are the cleanest fair-and-hard models.

## Lessons for the master
- Hardness in this repo comes from putting about 2/3 of test weight on rerun instances where a plausible fit stops working (median final 35.7 vs 56.5), not from rerunning itself.
- 3 of the 7 Experts are hard through unstated hypothesis spaces; copy only the bounded form (LC1).
- A judge with P <= 20 swings ~3 final points per weight; check 50/P before trusting a band (725e575c, 42e79476).
- Counterfactual what-if figures (J11) held where headline figures leak.
- Agents stop early (23% of budget); time limits are not what makes these tasks hard.
