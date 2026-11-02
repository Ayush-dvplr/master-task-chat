# Harden round 1: metered-usage-rating-pipeline (3106c16)

Status DONE. Phase A GENUINE (probe 1: tests 100, judge 75, overall 87.5). Primary cause 4: the levers were weak by design. Causes 1-3 NO. Full evidence is in [DIAGNOSIS.md](DIAGNOSIS.md).
Bundle tree 36fe302d21c8 (git write-tree over the 23 files, no bytecode). The build tree was 212f389aeb8d.

## What changed (master go, 21:00, points 1-9)
- LV-MU-1 kept and rewritten. The north field block now says only "`units` (a JSON integer)". The list of malformed values and the "except north" sentence are deleted. The text collectors are named in their own sentence, and Checking item 4 is one clause ("not in its collector's form"). The global trim sentence and the shipped separating rows stay.
- LV-MU-3 rewritten. New glossary term "committed account": an account whose value in the plan column of accounts.csv is `committed`. The credit base uses that term. The pool-under-half invariant is deleted. No other sentence ties the base to the plan in force. normalized.jsonl still outputs `plan` in force, which pulls toward the wrong reading. In the shipped month the plan in force equals the start plan on every line. In the hidden month 1950 of 7555 lines differ.
- LV-MU-5 is new. accounts.csv gains a `parent` column, with glossary terms "billing group" and "tier counter". The Rating sentence uses the tier counter. Shipped parents are all empty. The hidden month has 195 accounts in 93 groups of 2-4, with parent ids in variant form 50% of the time.
- LV-MU-2 (half-even ties) and LV-MU-4 (canonical ids) are kept as graded noise. They are not counted as levers.
- Judge has 16 criteria: positives sum to 34, negatives to -14. New criteria R15 (`check tier_counter ok`) and R16 (`check credit_base ok`), both w3, are shown by solve.sh. reward.toml judge weight is 0.5/34. JUDGE_MAP updated.
- Updated files: rating_contract.md, accounts.csv and the other regenerated data, solve.py, solve.sh, test_output.py, judge.toml, reward.toml and TRUTH.md (TRUTH regenerated last by script). WORK updated too: DESIGN §11, LEVERS, levers_detail, COST_TABLE, RULE_COVERAGE, QC_DEFENCE, JUDGE_MAP. XREF.md is new and has 13 entries.

## Measured (AFTER tests: 199 positive points, hidden seed 58213)
| lever | alone lost | all-but-one overall (rubric 90) | one-fact-wrong lost |
|---|---|---|---|
| LV-MU-1 | 95.0% (47 tests) | 67.4 | 73.9% |
| LV-MU-3 | 42.7% (17) | 47.5 | 22.6% |
| LV-MU-5 | 55.3% (22) | 47.5 | 25.1% |

- G10 passes for all three levers.
- LV-MU-3's one-fact-wrong loss is 22.6%, below 25. That is reported, and the CL-4 exemption sentence in instruction.md is kept.
- As noise, LV-MU-2 alone loses 55.3% and LV-MU-4 alone loses 57.8%. All three levers wrong loses 95.0%.
- Rule coverage: 0 of 53 rules uncovered. COUPLING is still the region credit base.

## Gates
- STACKING_CHECK PASS (a-e). One manual correction in (b): the tool had put R12 and R14 into one 6-point group. They are two separate 3-point acts.
- Hidden share 64.8%, whole-document share 48.2%, shipped-only share 35.2%.
- QC kit 976c166: structure, instruction, tests and judge scripts all 0 FAIL. validate_bundle 39/0 GATE PASS. precheck CLEAN. xref_check 0 findings.
- Docker (20261024T212313-92df, ALL_DONE):

  | run | reward |
  |---|---|
  | oracle x3 | 1.0, 1.0, 1.0 |
  | owner-only | 1.0 |
  | nop | 0.0 |
  | stub | 0.0 |
  | forgery | 0.342 |

  The forgery scored 68/199: visible checks only, the negative fired, and every `_hard` check failed.
- Reflex gate (advisory this round): OUT/agent_program scores 89/199 = 0.447 on the AFTER tests, which is above 0.20. It fails exactly the 22 LV-MU-5 tests, and the LV-MU-3 tests are a subset of those. Caveat: the parent column is new data the probe-1 program never saw, so this measures LV-MU-5 alone, not a reflex.

## Notes
- name_session.py did not show 3106c16 (only an opencode match). Not retried.
- At start WORK had no XREF.md and this slug had no baselines.json. XREF.md is now created.

## Lessons for the master
- Opus implements every explicit sentence, even ones shipped data never exercises (it built its own tie and lower-case id fixtures) | template_change: hidden-only separation is not a lever unless the rule's wording or location invites another reading
- An output field that exposes the wrong-scope value (plan in force on each line) makes the wrong base the natural code path | template_change: LEVER_RULES 1b add "decoy-by-output field" under H3
- stacking_check groups negatives with the same weight into one act | template_change: tool fix, group by act id, not by weight
- The reflex gate is not meaningful after a new data column | template_change: score agent_program with the new column ignored, or mark it advisory by rule
