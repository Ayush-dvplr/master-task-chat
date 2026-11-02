# Hardness-guide verification (ec452c9)

D1 = `HOW_TO_MAKE_HARD_1.md` (86 lines). D2 = `HOW_TO_MAKE_HARD_2.md` (2193 lines). Every claim, with its verdict and evidence, is in `CLAIMS.csv` (114 rows).
Session rename: `name_session.py ec452c9` printed "NOT RENAMED: no session starts with this board id". I did not retry.

## Counts by verdict (114 claims)

| Verdict | n | Impact split |
|---|---|---|
| CONFIRMED | 49 | mostly adopt; most are already in our rules or the QC kit |
| UNTESTED | 31 | 5 of them load-bearing measured figures with no source file here |
| CONTRADICTED | 14 | our probe and run rows show the opposite |
| QC_CONFLICT | 7 | would fail or risk a kit rule |
| GOAL_CONFLICT | 7 | aimed at 10% per channel or playground volume, not our gate |
| WRONG_FACT | 6 | paths, keys and floors that do not exist here |

Impact over all 114 rows: adopt 36, adapt 10, ignore 68.

Abbreviations in citations:
- SC = `master_chat_tasks/registry/scores.jsonl:<line>`
- LR = `master_chat_tasks/knowledge/LEVER_RULES_v3.md`
- LS = `lessons.jsonl`
- QR = `QC_RULINGS.md`
- Kit files: `Input_Bundle_QC/01..05`
- FC = `Final_checklist.md`

Overall: D2 is a careful restatement of the QC kit. Its kit mechanics are right: weight semantics TS-20, A3 10-35 checks, JD-7/JD-8/JD-15, CL-4, the oracle/nop/stub runs, and the D2 section 16.1 filter table. Its difficulty theory is mixed:
- Right: law 1 (wrong output must be silent and plausible), law 2 (a written rule gets transcribed), hidden scale, and dependent chains.
- Wrong or contradicted, in its levers and measured figures: reconciliation/entity traps, decoys, evidence-derived rules, counterfactual judge figures, volume quotas, and the mutant-ladder calibration.

D2's own case study is real but rests on one run (kvec, below). D1 is a short prompt version of D2 for another machine. Its paths do not exist here, and two of its rules contradict D2 and each other.

## kvec check (D2 15.1)

The files match D2's numbers:
- `Output/kvec-meter-settlement-reconciliation/logs/pass-summary.json`: combined 50.23, tests 17.12, rubric 83.33.
- `report.json`: 36 tests; passed weight 25 of 146 positive weight; one w1 check (`feeder_balance_shape`).
- Judge: 11 criteria. The 6 positives are all w3; the 5 negatives did not fire; rubric 15/18.

Two nuances:
- R6 is a code-quality criterion and R11 is an honesty negative, so not all 11 are "conduct" or "anti-cheat".
- kvec has 26 checks at w5, against D2's own quota of 6-8 w5 checks.

The figures come from a single run. kvec is our delivered peer daaca581. Its sibling 3def42a3, built from the same shipped data, scored tests 37.93 (`_dev_research/delivery_study2/g2_aee9e0a/C_daaca581_DIFF.md:3,24-26`). LR:145 G13 already says to treat any single test score as ±20. The verdict is CONFIRMED as a sample, and D2's causal conclusions from it are overreach.

## a) Withheld-but-derivable rules (D2 5.9; D1:46 vs D1:44)

**Same lever as ours?** Yes. It is our L11 "evidence induction" (LR:58): a rule with no sentence, which exactly one shipped witness settles. D1 contradicts itself here. D1:44 forbids "hidden or unstated rules" and D1:46 requires 3-6 withheld-but-derivable rules. D2 also contradicts itself: D2:807-830 recommends them, and D2:1998 says "Nothing in this section licenses withholding a rule".

**Has any of our bundles tried it?** Yes, and it failed:
- L11 tariff: 3/3 fresh blind reads at 157/157 (LR:58, LR:79-86, `registry/tasks.json:674`).
- Unique-fit plus derived state: tariff r2 301/301 and sentinel r2 98/98 (LR:79-86).
- Opus measures every two-reading fork that the shipped data can test (LS:76).

D2's measured figures (spec transcriber 1.000, observation-record 0.108, legacy note 0.067; D2:807-810) have no source file anywhere here. Our own runs contradict them (C043).

**QC rules it touches** (C044, QC_CONFLICT):
- It passes only if the shipped input *determines* the rule (05:21-22 AL-1).
- Silence never counts (05:27).
- A prohibition or scope rule is never determinate (05:30).
- If the deciding fact sits only in tests or solution, it fails CL-10 (05:94), DS-21 (02:70) and AL-F0e (05:83). This happened on match-replay v2 F1, where the fragment grammar was only in the tests and gated 100 of 158 points (SC:74).
- If the oracle uses an invented literal, it fails DS-25 (02:71).
- Our own peers' holes that passed QC with a WARN (LR:226-244) are not levers.

**Worth one trial?** No. It has been tried 3+ times under v3.3 and leaked each time. GOALS G11 says difficulty "never from withheld rules of engagement". Keep it paused.

## b) Judge counterfactual figures (D2 9.3; D1:69)

D2:1389-1390 asks for a closing message stating 9-12 figures (D1:69 says 8-10) that appear in no artifact, judged at w5. **Our judges do not do this, by rule.** LR:150 J1 bans any figure criterion, what-if or not. Opus answered every figure right in 18b5d99f, 3f39299a and 0b27b9dc. Our own runs agree:
- sensor: figure criteria carried 12 of 15 judge points, rubric 80 (SC:60).
- dispatch: R1-R5 "states figure" carried 17 of 21 points and the agent hit all of them (SC:61).
- QR:107 and QR:154: figure criteria failed JD-7 four times, because the figure was wrong against the oracle.
- QR:133: figures requested in the reply but graded by nothing failed AL-2/CL-1.

Verdict C082 CONTRADICTED. "3-4 facts per criterion" (C083) is QC_CONFLICT with JD-5 (compound criterion). The 18→28 mutant lift (C084) is UNTESTED: it has no source.

**Does D2 15.1 (conduct criteria earned by habit) match our judge scores?** Partly. kvec's six w3 conduct positives scored 15/18. Our early judges did the same (rubric 75-100 at SC:80, SC:84, SC:88, SC:93). Our P-5 probe band, 8-16 trajectory probes the oracle shows (LR:151-183), lowered the rubric to 3-48:
- caldermoor: 4.55 (SC:82)
- tariff: 3.33 (SC:90)
- sentinel: 19.51-43 (SC:81, SC:86, SC:87, SC:94)
- district-heat: 37.04 (SC:89)

So D2's diagnosis, that habit-earned conduct criteria are easy, is CONFIRMED. Its fix, counterfactual figures, is the one we already measured as failing.

**Which fits QC better?** P-5:
- Probes are true of the oracle (JD-7 04:76).
- They do not restate a test observable (JD-8 04:77).
- They pass JD-15 as conduct that raises the odds (04:92).
- JD-16 quotes are needed only for constraint criteria (04:93-97).

Counterfactual figures risk failing JD-7 (oracle must compute them) and JD-15, because the figure must trace to the instruction. D2 meets that by stating the question, which hands the agent the computation.

## c) Volume levers (50-60 files, ≥2000 lines, ≥12 trap types, ≥12 traps per file)

These are the playground's A5 volume gate, not the QC kit:
- KNOWLEDGE.md:27: playground A5 needs ≥20k lines in total and ≥2k per data file.
- The kit has no line floor. tests_qc.py:51 A5 means "no check returns a literal non-bool".
- FC:204 sets 10-35 checks.
- LS:18: our P9 gate waives volume for non-generator bundles.

So C058 and C059 are GOAL_CONFLICT, and D2's "A5 line floors" is a WRONG_FACT against this kit.

Our 21-24 Oct builds had many stated traps and scored tests 100:
- cohort (SC:40)
- vendor (SC:43)
- district-heat (SC:54, SC:56)
- schema (SC:58)
- tariff and metered habit levers 199/199 (LR:105, LS:87)

That is **consistent with D2's laws, not a contradiction of D2**. Those traps were stated: each rule sentence named its own exception (LEAK_LIBRARY:5-10; sensor SC:65, "first run equalled TRUTH"). D2 law 2 predicts exactly that.

It does contradict D2's trap *quotas* (C062, C052). Breadth alone, at 30-80 stated rules, loses 20-60% of test points on peers (LR:67, S1). Even so, our 40+ rule breadth on fuel-card came out exact (LR:79-86). Quantity is not the lever; silence of failure plus unstated method is.

**Check caps:** A3 fails below 10 checks and warns above 35 (tests_qc.py:48; 03:62 TS-23). D2's ~30 checks fit. Our schema P-3 build has 71 checks and is at warn (BOARD.md:20). LR:146 records the warn and does not fix it.

## d) Silent plausibility (D2 5.10, law 1) vs our timeout levers

D2 law 1 (C028, CONFIRMED) says a crash or timeout tells the model it failed. Our evidence that a naive timeout alone did not hold at scale:
- The district-heat low scores were grader timeout artefacts. They were not agent failures, and the real run gave tests 100 (LR:221; SC:54).
- metered: probes 100/100/100 (SC:80, SC:85, SC:92).

Our P-1 lever that *held* was sentinel r3:
- Probes: tests 96.18 and 78.63, then gate run 80.69 (SC:94).
- Blind read: 78.63.

This lever mixes the two failure kinds:
- The naive solver times out at 60 s (`harden_t3/DIAGNOSIS.md:39-42`).
- Greedy, tie-keeping and unit solvers write output that is valid but wrong (DIAGNOSIS.md:42-44).
- The blind loss was 21.4% with 0 crashes (HARDEN_REPORT.md:4).

So the points were lost to silent wrong answers, not timeouts. That agrees with D2: a timeout gives a recovery signal that Opus uses, and a plausible near-optimum does not.

Dispatch P-3 (tests 35.64, SC:79) also loses through valid-but-suboptimal output. **Implication:** count a P-1/P-3 lever only if a fast heuristic exists that writes a plausible wrong answer. Do not count it on naive-timeout alone.

## e) Dependent chains and weight on late stages (D2 15.3, 5.7)

The arithmetic is right: p^n (C040, C110, CONFIRMED). Our counter-case is that a strong program is exact at every stage, so p≈1 and depth does nothing. Schema e3e74e6 replays of 976 lines with 518-560 corrections were exact on all 4 corpora, for both the blind program and Opus a4 (SCH HARDEN_REPORT.md:8, :64). Match-replay P-2 held (probe 46.88, SC:76) only because the replay drove hidden state the stated rules did not pin.

"Highest weights on the last stages" (C111) is QC_CONFLICT. TS-20 ties weight to meaning: core 5, sub-goal 3, minor 1 (03:51). Sentinel v1 and v6 failed TS-20 on misweighted core deliverables. A chain helps only when some stage has p<1 for a strong program. Build that stage first (a P-1/P-3 core), then chain from it.

## f) Calibration gates (D2 section 10: T1 F/P≥0.90, near-miss ladder, five solver profiles)

These are reflex/mutant solvers scored offline. They did not predict our real runs:
- district reflex 0.177, real tests 100 (LS:65).
- schema reflex replay 0.194, real a4 tests 100 (20261023 harden_r1:26, SC:70).
- GOALS G11: "reflex and per-lever solvers do not predict real scores and are not used".

So C091 and C025 are CONTRADICTED. kvec itself sat at F/P≈0.83 against D2's own 0.90 bar and still scored 17.12 once and 37.93 once.

**What D2 has that would have helped:**
- Mutant isolation: each mutant breaks one trap (C026). It is already in TS-13 `mutation_shipped`, used in sentinel RECHECK_FIX:12-17.
- The section 17 solvability probe: STATED / DERIVABLE / UNREACHABLE / INVENTED literals (C027). It catches DS-21, DS-25 and CL-10 before QC. Match-replay v2 F1 is the case it would have caught.

What predicted our real scores: P13 fresh blind solves. Sentinel blind rescored 117/145 = 80.69, equal to the gate run's 80.69 (`p12_fix_v6/RECHECK_FIX.md:58`), and blind matched real runs 3 of 3 (GOALS G11).

## g) Would D2 rules have prevented the sentinel QC loop (v1-v7)?

| QC run | Finding | Prevented by |
|---|---|---|
| v1, v6 | TS-20 core at w1 | **yes**: D2 weight semantics, D2:1119-1123 and 1218-1227 |
| v6 | CL-4 SHIPPED_CHECKS loop at w1 | **yes**: one check per comparison, D2:1187-1200 |
| v6 | AL-28 judge negatives stack on one line | **yes**: D2:1490-1493 |
| v1, v5 | JD-15 conduct labelled instruction/constraint | **yes**: J1-J13 type label, D2:1295-1340 |
| v1, v4 | DS-27 authoring narrative in TRUTH | **partly**: D2:1729-1755. But D2's own provenance-yaml advice (C102) would itself trip DS-27 |
| v1 | TS-19 rerun builds a fresh corpus | **partly**: "negative on nop/oracle = defect", D2:385-394 |
| v2, v3 | TS-26 rebuild check fed from the agent's own resolve | **partly**: D2:1131-1134 |
| v2 | AL-27 row-version half never triggered | **partly**: near-miss mutants, D2:1570-1577 |
| v4, v5 | AL-2 promises ungraded | **no** |
| v4 | IN-8 unlearnable clause | **no** |
| v4 | JD-5 compound criterion | **no**; D2's "3-4 facts per criterion" would *cause* JD-5 |
| v6 | JD-6 judge gets a file it never receives | **no** |
| v7 | CL-2 vacuous code-quality criterion | **no** |

Rough count: of the 19 findings named in reports v1-v7, about 6 are fully preventable and about 4 partly. That is the same coverage our QC_FIX_PLAYBOOK_v2 and the "one QC before first probe, fix every finding in one pass" rule (LR:211) already give, provided they are followed.

## Wrong facts (6)

| Claim | Statement | What the files show |
|---|---|---|
| C002, C055 | ABLATION_MAX lives in `archetype.toml` | No archetype.toml has it. Ablation is in playground.py ("≤ 0.5") |
| C003 | `/home/shubhi/...` and `HARD_TASK_HARDENING_0.24.md` | Not present on this machine |
| C015 | tests_qc H5 docstring | H5 is chown root + chmod 755, a warn (tests_qc.py:100) |
| C086 | D1 and D2 judge slot counts | They disagree with each other (D1:69 vs D2:1389-1390) |
| C096 | D1:60 "<6000 chars" as a rule | It is a guideline. validate_bundle.py:476 and :487-490: fail ≥20000, info ≥6000 |
