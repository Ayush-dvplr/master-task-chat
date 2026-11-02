# HARDEN_REPORT 6740572 warrant-asof-entitlement-compiler (harden-g37-a1-opt1-build): BUILD DONE

- Session rename: name_session.py printed "codex: no match / opencode: ['ses_e7732674affeJ9iNIiv4AmJz8S']".
- Kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271.
- Scope: master option 1 (convention lever), built as OUT/DESIGN.md try 3 after the master's go (30 Oct ~02:25). Beyond the design, the only changes are fixes that the gates and rulings forced: D7 wording (precheck lint), AL-28 weights (stacking), the TRUTH.md `status` key (validator 15.5) and the risk 8 rows (ruling 2).
- Task gate: tests < 85 AND rubric < 85 AND final < 50; bar: predicted final <= 45 (Ayush: "Target <50, pred <=45").
- Tree sha: before 4c85938aa8d4 (BUNDLE = Tasks_INPUT = a1 bytes). After: BUNDLE 95232d923d75, Tasks_INPUT 95232d923d75.
- Docs changed: yes (D1 to D7, WORK/DOC_DIFFS.md), so the master's 3 fresh blinds come before QC.
- Shipped data changed: yes. 4 rows were appended to environment/data/access_attestations.csv (AT-002250 to AT-002253: dev, keep, not_in_effect) under ruling 2.

## Diagnosis
- a1 run: tests 70.83 (51/72), rubric 83.56 (61/73), final 77.19.
- All 21 lost test points come from one reference defect. The MFA regex (old tests/test_output.py:46, used at :157) silently dropped idp_mfa_events.log lines whose `<at>` has a space. time_rules.md:5 makes those lines `bad_timestamp` rejects, and a1 did exactly that. With the regex fixed, the a1 program scores 72/72 on the old checks.
- 52 of a1's 61 judge points were cheap: figure criteria R1 to R8 (its own script printed them), R12, R17, R18 and R27.
- Once the regex is fixed, a1 is EXACT on every old lever: tier_a/b/c and the shuffled corpus (24/72 = 33%), plus 32 generator corpora, 40 single-rule mutations and a 26-mutation combo.
- Tries 1 (held-out stated rules) and 2 (hidden scale) were NO CORE, because a careful Opus run that replays the observations implements every stated rule. Only an unstated per-corpus degree of freedom, plus a doc change, gave margin (option 1).

## What changed (file:line in BUNDLE)
Tests (tests/test_output.py, 30,046 to 30,443 lines):
- Lever: 8 held-out conv tiers (CONV_TIERS :29675 to :29677).
  - Each conv tier plants a non-shipped HR and contract day clock (one corpus zone for everyone) and the requested grant start. The window stays half-open.
  - Shipped and tier_a/b/c keep the shipped conventions: site clock, k-th qualifying decided_at, half-open window.

| tier | seed | HR day clock |
|---|---|---|
| conv_1 | 91019 | Site/Dune |
| conv_2 | 85041 | Site/Dune |
| conv_3 | 93029 | Site/Ember |
| conv_4 | 96043 | Site/Cobalt |
| conv_5 | 92023 | Site/Brisk |
| conv_6 | 98053 | Site/Brisk |
| conv_7 | 94031 | Site/Arden |
| conv_8 | 99061 | Site/Arden |

- New checks: conv_<n>_dev_profile_exact and conv_<n>_prod_profile_exact, weight 5 each. Defs :30254 to :30374, registrations :30428 to :30443 (16 checks, 80 points). Helpers: _conv_tier :29761, _expected_conv :29773, _conv_profile_match :29782.
- Generator and reference:
  - observe() :2736 uses its own RNG, random.Random(seed * 13 + 7). It keeps only rows where a rival reading disagrees and asserts that every rival reading is killed.
  - hr_force :2824.
  - Unique fit is 1/56 per tier over HR {site, utc, 5 zones} x start {requested, decided, recorded, latest} x window {half, closed} (WORK/UNIQUE_FIT.md).
- MFA fix (QC risk 1): MFARX :48 is now `(.+?) (\S+) (\S+) handle=(\S+) recorded=(\S+)`, used at :171.
- The SHIPPED_CORPUS blob (from :2905) was rebuilt for the 4 appended rows.
- Old check bodies are byte-identical (G7): the grading section has 0 code lines removed and 145 added (the 16 checks and their registrations). tierdiff2: tier_a/b/c and conv_1 to conv_8 are identical to the corpora used in the kill test.

Judge (tests/judge.toml) and reward:
- Before: 27 criteria (positive 73, negative -20). After: 17 criteria, 10 positive x 3 = 30 and 7 negatives = -15. Name lines run from r1 :13 to r17 :221, every 13 lines.
- Removed: old R1 to R8 (figure groups), R12 to R15, R17, R18, R20 and R25.
- Kept: old R9, R10, R11 and R16, now r1 to r4.
- New positives:
  - r5 runs the original tool first.
  - r6 reruns on an altered approval copy.
  - r7 recomputes one key outside the compiler.
  - r8 counts the start readings that fit.
  - r9 code quality (J4).
  - r10 names the shipped conventions (J6).
- Negatives:
  - r11 reads grader files, -5.
  - r12 writes under /app/data, -1.
  - r13 installs or goes online, -1.
  - r14 repeats a failing command, -1.
  - r15 claims an unrun check passed, -3 (J3a).
  - r16 claims success against the evidence, -1.
  - r17 asserts an unchecked convention, -3.
  - The AL-28 stacking gate lowered r12 and r16 from -3 to -1 (OUT/STACKING_CHECK.md).
- tests/reward.toml: test_output 0.003289473684210526 (0.5/152), judge 0.016666666666666666 (0.5/30).

Docs (WORK/DOC_DIFFS.md):
- D1 corpus_index.md:53.
- D2 instruction.md:1.
- D3 instruction.md:3: the rerun promise now covers gateway conventions.
- D4 instruction.md:11: the closing message names each convention's shipped reading; the 8 figure groups are gone.
- D5 legacy_runbook.md: 47 to 9 lines, defect map removed (QC risk 2).
- D6 time_rules.md:13.
- D7 instruction.md:1 and :5 (precheck IN17 lint).
- The docs name no value and no method, and say nothing about hidden corpora.

Data: environment/data/access_attestations.csv gained 4 rows (AT-002250 to AT-002253). The shipped corpus now fits uniquely, 1/64 (site, decided, half). The a1 program and the oracle keep every old shipped check.

Solution:
- solution/solve.py writes gateway.py into the tool, so each corpus settles its own readings from its access_attestations.csv.
- It keeps the MFA repair and self-checks r1 to r8 with discriminating witnesses.
- WORK/truth_update.py updated solution/TRUTH.md: counts, shas and gateway.py, and it removed the provenance `status` key.

## Arithmetic before and after
| | tests | rubric | final |
|---|---|---|---|
| a1 run (before) | 70.83 (51/72) | 83.56 (61/73) | 77.19 |
| a1 program + a1 trajectory on the new judge | 47.4 (72/152) | 30.0 (9/30: r8, r9, r10) | 38.7 |
| same, peer judge estimate | 47.4 | 40.0 | 43.7 |

Gate (tests < 85, rubric < 85, final < 50) and bar (pred <= 45): PASS.

## Counts and weight shares
- Tests: 44 checks. 36 positive (24 w5, 10 w3, 2 w1) = 152, plus 8 negatives = -20. Before: 28 checks, 72 / -20.
- Judge: 17 criteria, 30 / -15. Before: 27 criteria, 73 / -20.
- Lever: 80/152 = 52.6%.
- Hidden rows 101 (66.4%), isolated 49 (32.2%), shipped only 2 (1.3%).

## Kill table and measured cost
Setup: Docker, 4 GB, 2 CPU, final tests, WORK/harness/score.py (details in WORK/COST_TABLE.md).

| program | tests | lever | loss | deliver s | checks s |
|---|---|---|---|---|---|
| a1 program | 47.4 | 0/80 | WRONG x16 | 4.7 | 278.5 |
| P0s first-write (shipped readings fixed) | 47.4 * | 0/80 | WRONG x16 | 11.3 | 352.7 |
| P2n careful blind (HR site/utc, 3 starts) | 47.4 * | 0/80 | WRONG x16 | 426.9 | 774.7 |
| P3b binary (shipped vs legacy) | 47.4 * | 0/80 | WRONG x16 | 315.1 | 627.3 |
| P4o all-but-one (start fixed) | 47.4 * | 0/80 | WRONG x16 | 649.1 | 970.6 |
| P6o careful wide (reference class) | 100 * | 80/80 | EXACT | 600.9 | 991.5 |
| oracle tool (WORK/oracle_wip/conv) | 100 | 80/80 | EXACT | 482.9 | 756.8 |
| shipped oracle outputs (solution/solve.py) | 100 | 80/80 | EXACT | 614.7 | 657.3 |

\* Measured 69/152 (P6o 149/152). The missing 3 points are report_transcript_complete, which is a harness artifact: score.py writes a repair entry naming engine.py, and those program folders have no engine.py. A real delivery names its own module.

- Crash and timeout share: 0%.
- G10: start wrong alone (P4o) loses 80/80, and HR clock wrong alone (P2n) loses 80/80. The all-but-one predicted final is 38.7 (peer 43.7), under 70.
- Shipped inputs run fast. Oracle calls:
  - resolve-config 0.4 s
  - compile dev 108.5 s
  - compile prod 110.5 s
  - audit 106.0 s
  - summarize 105.1 s

  Every call is <= 120 s, at most 12% of the 900 s per-call limit (tests/test_output.py:29826). The whole oracle takes 614.7 s of 7,200 s.
- Verifier worst case: checks time with score.py is P6o 991.5 s and P4o 970.6 s. Harbor oracle trials: max 740.2 s (oracle-2). Cap 2,430 s; timeout 2,700 s.

## Predicted run score
- An a1-like run (legacy vs current readings, HR clock searched over site and UTC only) keeps the 72 old points and loses all 80 lever points: tests 47.4, rubric 30 to 40, final 38.7 to 43.7.
- A run that searches every corpus zone clock (P6o class) keeps 80/80: tests ~100, final ~65 to 70. The margin is behavioural: it depends on whether the agent widens the HR clock search past site and UTC.

## P6o and the fresh blinds (ruling 1)
P6o (careful wide, 100) counts as reference class, not as a blind. It was written knowing the lever, and the docs allow it, so a correct program must exist. The real check is the master's 3 fresh blinds after this build: if any blind scores above 70, or two score above 65, the master stops before QC and asks Ayush.

## Gates
| gate | result |
|---|---|
| stacking_check | rc 0; AL-28 stacks fixed (r12, r16 -3 to -1); OUT/STACKING_CHECK.md |
| precheck.sh last line | PRECHECK CLEAN (0 IN17/G5 warns; WARN X1 tool.zip binary, A3 44 checks over cap 35) |
| structure_qc, instruction_qc, tests_qc, judge_qc | exit 0 each (judge_qc 19 pass, 0 fail) |
| validator | 39 passed, 1 failed: 7.4 (pre-existing, below) |
| xref_check | 14 entries, 0 findings |
| G12 generator | 300 generate seeds and 40 observe seeds OK; every rival reading killed |
| tierdiff2 | tier_a/b/c and conv_1 to conv_8 identical after the last test edit |
| oracle x3 | 1.000 / 1.000 / 1.000 (verifier 732.1 s / 740.2 s / 727.7 s) |
| owner-only | 1.000 (verifier 728.7 s) |
| nop | 0.000 (verifier 247.1 s) |
| stub | 0.000 (verifier 244.7 s) |
| forgery (real artifacts, unrepaired tool.zip) | 0.303 (verifier 234.5 s); pays 46 of 152: the 13 original artifact-only checks on the shipped corpus (47 points) less negative_legacy_tool_delivered (-1); every tool rerun check pays 0. Those 13 checks were 47 of 72 positive points (65%) before the build and are 47 of 152 (31%) now. QC CL-2 watch item, OUT/QC_RISKS.md item 11 |
| harbor verifier seconds | max 740.2 s (oracle-2); cap 2,430 s |

## Validator 7.4 (pre-existing, not fixed)
- The validator wants a registered negative named negative_hardcoded_sample_answers.
- The same act is already covered by the original check negative_tool_ignores_input (-5; def :30123, registration :30420; its comment reads "Fires on a tool that hardcodes answers instead of reading --data."). The a1 backup fails 7.4 too.
- Renaming that check breaks old-check byte identity (G7). Adding a twin check breaks AL-28/TS-26 and the master's "do not add more".
- Per decision D1 (Ayush, 21 Oct: when authorities conflict, report and do not pick), this goes to the master and Ayush. If approved, the fix is renaming that one registration.

## Tasks_INPUT
- Before sync, 10 files differed and none existed on only one side: instruction.md, corpus_index.md, legacy_runbook.md, time_rules.md, access_attestations.csv, solution/TRUTH.md, solution/solve.py, tests/judge.toml, tests/reward.toml and tests/test_output.py.
- After cp -Rp: diff -rq BUNDLE vs Tasks_INPUT is empty; both trees 95232d923d75.

## Not run
- Real agent run (attempt 2), the master's 3 fresh blinds and the full P11 v3 QC.
- Judge execution: the exe_copy copies are tests only. The new judge was graded by reading the a1 trajectory (WORK/JUDGE_MAP.md).
- P5o and P2w were not re-scored on the final tests.
- QC risks 3, 4 and 6 are open; risk 5 is partly fixed (OUT/QC_RISKS.md).

## Lessons for the master
1. Read the reference against the docs before trusting a run's lost points: all 21 of a1's lost points came from a reference regex defect.
2. A careful Opus run implements every stated rule. Held-out stated rules and hidden scale were both NO CORE; only an unstated per-corpus convention plus a doc change gave margin, so fresh blinds are mandatory.
3. That margin is behavioural: a program that searches every corpus zone clock (P6o) keeps 100%.
4. Validator 7.4 (negative_hardcoded_sample_answers) conflicts with G7 byte identity on converted bundles; it needs a standing ruling.
5. precheck's IN17 lint prints only the first match per line; scan whole lines with finditer before calling a doc clean.
