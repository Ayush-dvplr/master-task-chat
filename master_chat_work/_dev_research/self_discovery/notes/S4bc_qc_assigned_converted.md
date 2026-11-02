# S4b/S4c: QC assigned reports + converted_tasks_report (grep-based)

Root Q = /Users/mac/Desktop/Terminal Bench/QC assigned/

## 4b qc_report/<14 slugs>/v*.md verdict line 1 (grep "Verdict:")
| slug | v1 | v2 | v3 |
|---|---|---|---|
| 07d51b69 | FAIL 13/4/5 | FAIL 3/2/2 | FAIL 1/4/4 |
| 7ef8d80a | FAIL 20/5/13 | FAIL 11/4/4 | FAIL 8/3/4 |
| caldermoor | FAIL 17/8/10 | FAIL 8/3/5 | FAIL 18/2/7 (REGRESSED) |
| cohort-retention | FAIL 21/5/6 | FAIL 8/5/6 | FAIL 3/4/1 |
| cohort-uplift | FAIL 6/6/10 | FAIL 1/3/5 | FAIL 1/0/3 |
| dispatch | FAIL 21/5/3 | FAIL 15/3/4 | - |
| emberforge | FAIL 17/3/6 | FAIL 11/1/2 | - |
| match-replay | FAIL 19/3/11 | FAIL 3/8/10 | - |
| numeric-reduction | FAIL 32/6/5 | FAIL 9/5/10 | - |
| pcggc | FAIL 11/5/10 | FAIL 3/3/3 | - |
| season-ladder | FAIL 23/4/5 | FAIL 2/1/3 | - |
| sensor | FAIL 8/5/5 | FAIL 5/3/2 | - |
| sentinel | FAIL 28/16/8 | FAIL 13/4/9 | - |
| specdec | FAIL 16/4/12 | FAIL 8/7/5 | - |
=> 33/33 reports FAIL. No converted task reached PASS in QC assigned. Fix rounds converge slowly and can regress (caldermoor 8 -> 18; triage records "NEW-1 and NEW-3 are post-QC file changes, both made at 13:41-13:42 IST today alongside the kit update" -> kit updates mid-round re-open findings).

## Most-cited rule ids across 33 reports (grep -o count)
JD-15 252, DS-21 246, IN-16 241, JD-16 228, CL-2 217, CL-10 183, CL-5 179, TS-16 178, DS-20 174, IN-8 168, DS-22 165, AL-27 163, TS-26 147, AL-2 146, CL-4 144, TS-19 139, JD-8 138, TS-24 137, AL-18 127, JD-5 120, JD-18 119, TS-29 111, DS-24 110, AL-1 110, TS-13 108. IN-16 appears in all 33 v*.md files.

## Triage FP evidence (triage_v*.md)
- 7ef8d80a triage: "35 unique findings ... 23 REAL, 2 FALSE POSITIVE, 10 VAGUE".
- cohort-uplift triage_v1: "10 REAL, 3 FALSE POSITIVE, 8 VAGUE".
- caldermoor triage_v1: "29 REAL, 5 VAGUE, 1 FALSE POSITIVE"; triage_v2: "REAL 10, FALSE POSITIVE 2, VAGUE 4"; triage_v3: "REAL 12, FALSE POSITIVE 1, VAGUE 3".
- 07d51b69 triage: "5 REAL, 0 FALSE POSITIVE, 2 VAGUE"; later "6 REAL, 2 FALSE POSITIVE, 1 VAGUE".
- Recurrent FP kinds (quotes):
  - AL-20 curl|sh in environment/Dockerfile: "FALSE POSITIVE | environment/Dockerfile:11-21 is word for word the block the kit requires: 02_Data_Solution_QC.md:120-144 (DS-29) requires it" -> QC rule vs kit template conflict.
  - TS-2 tests/Dockerfile extra lines: "FALSE POSITIVE. Line 4 (LITELLM_LOCAL_MODEL_COST_MAP) is now required (kit TS-2, tests_qc K7)".
  - TS-SCRIPT-B4 deny-list regex matches grader tokens inside the program's own anti-cheat list (7ef8d80a W5) -> tooling FP; CONVERSION_SUMMARY:37-38 "B4 fail ... None writes a reward ... Editing them would change grading" (B4 fail on 12 of 13 converted).
  - JD-9 "19/26 criteria read final-message values": triaged FP in substance, but "the gate would flag it again. No neutral change exists: adding process criteria is barred by F3, removing figure criteria by F1" (caldermoor triage_v3) -> rule trap with no compliant fix.
  - JD-11 network negative: FP because "api.anthropic.com ... offers server-side web search" (task.toml:37).
  - DS-10/DS-12 extra apt packages: FP.
- Triage repeatedly tags each fix with hardness arrow; e.g. 7ef8d80a "Hardness of the 19 fixes: 3 up, 10 unchanged, 6 down"; 07d51b69 "1 ↓ (JD-15, H4)"; caldermoor v3 "↓ small 4". => QC compliance fixes systematically trade away hardness (JD-15/CL-5/IN-16 require stating values/rules).

## 4c converted_tasks_report
- CONVERSION_SUMMARY.md:14 "Harbor runs were tests only (judge.toml removed, reward.toml weight 1/P), 5 oracle runs"; 01_Feasibility_Report.md:30-33 "The judged channel never ran. No OPENAI_API_KEY ... rewardkit stops the whole reward when the judge call fails ... RewardFileNotFoundError" -> judge never validated at conversion; later DIAGs found the master note wrongly said v0 had no judge (cohort C3:17, dispatch D1:13).
- 01_Feasibility_Report.md:23 "Checks run in parallel threads (8 at a time), any exception aborts the whole reward" -> root of kill-by-uid race (schema/vendor oracle 0.11-0.28) and emberforge global LAST_PASSES risk (:84).
- CONVERSION_SUMMARY.md:51-54: one task's program folder unreadable -> "every check that runs the program failed, and the old oracle scored 0.705"; fixed with os.chmod(parent, 0o711) -> early instance of the permission trap that later produced 1.94%/4.83%/18x Errno 13.
- :39-40 specdec G6 judged negatives 17 > positives 10, "stays failing until its author changes the criteria".
- :103-105 kit sync e405488540 / 601b708ade fixes applied to 12 tasks; season-ladder not updated -> fails G2,S9,S10 (mixed kit versions across batch).
- 01_Feasibility :79/:83 47 checks over cap 35 (warn), dispatch 8,449-line test file.
- Converted v0 judges: :73 "Judge criteria that also test a fact the deterministic checks already test", :77 "No judge criterion grades the quality of the delivered program's code" -> JD-8/JD-7 debt inherited.

## Derived
- 4b-a: QC never PASSes converted tasks within 2-3 rounds; the kit itself changes mid-round (process_failure).
- 4b-b: IN-16/JD-15/CL-5 push every value/rule into an explicit sentence; triage arrows show these are the "↓ hardness" fixes (conflict with lever design).
- 4b-c: JD-9 vs F1/F3 = rule trap with no compliant change.
- 4c-a: judge channel unvalidated at conversion; rewardkit concurrency + abort-on-exception = tooling hazards.
