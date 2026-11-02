# SUMMARY - QC kit reverse-engineering, board 5087cd2 (kit HEAD 71a653b2)

Files: CHECK_INVENTORY.md + checks.json (302 rows), SCRIPT_RULES.md (8 baseline runs, 30 probes), CONFLICTS.md, LEVER_COMPAT.md, DOC_CHECK.md.

## Counts (302 = 209 md ids + 93 script codes; owner script 155 / judgement 104 / both 43)
| defining file | script | both | judgement | total |
|---|---|---|---|---|
| 01_Instruction_QC.md | 5 | 11 | 12 | 28 |
| 02_Data_Solution_QC.md | 3 | 11 | 16 | 30 |
| 03_Tests_QC.md | 16 | 17 | 14 | 47 |
| 04_Judge_QC.md | 14 | 2 | 16 | 32 |
| 05_Alignment_Integrity_QC.md | 0 | 1 | 42 | 43 |
| Final_checklist.md (FC-S, F0, CL) | 24 | 1 | 4 | 29 |
| structure_qc / tests_qc / judge_qc / instruction_qc codes | 28 / 37 / 19 / 9 | - | - | 93 |
Verdict rule: FC:442 "The bundle verdict is the worst finding present." One fail = FAIL; minors never add up to a fail.

## Top 10 conflicts (18 total: 7 confirmed, 11 squeezes; 4 rejected)
1. K2 IN-15 01:45 "If a test or a judged criterion grades HOW the agent worked, the rule must appear" vs JD-15 04:92 conduct "needs no instruction sentence". Reviewer picks.
2. Q1 CL-4 FC:491 ("a pile of separately weighted tests that all key off that same single comparison") vs whole-document cascades. TS-26/JD-14 allow them; CL-4 can fail them unless the instruction says exact match only.
3. K6 AL-28 05:28 cross-layer = any act "subtracting in the tests and again" vs our G4 "<=5 across both layers".
4. K1 TS-12 03:42 format rule left to judge = fail vs JD-16 04:97 "Warn rather than fail".
5. Q3 JD-7 04:76 (oracle meets every criterion) vs our J2 "constructs its own input" conduct criteria; solve.sh does not do that.
6. Q7 AL-1 05:21 "appears in no file" vs DS-21/CL-10 "follows from" (withheld rules): wording of AL-1 is stricter.
7. Q4 TS-16 03:47 honest-trip vs AL-10 05:40 anti-hardcoding negatives: an honest program can produce the shipped value.
8. Q5 DS-4/CL-3 vs shipped separating/boundary rows: a row that settles a graded case can be a leak.
9. Q2 AL-27 05:27 one fixture per rule/pair vs TS-23 cap (35 only a warn, so legal but noisy).
10. K3 IN-5 01:35 accepts RUN-created paths vs instruction_qc.py:257 C4 fails them under /app/data/.

## Lever verdicts (LEVER_COMPAT.md)
| L1 | L2 | L3 | L4 | L5 | L6 | L7 | withheld | blurred | computation |
|---|---|---|---|---|---|---|---|---|---|
| LEGAL | COND (CL-6 signpost, IN-16, DS-20) | COND (AL-27 pairs, CL-4) | LEGAL | COND (IN-16, TS-17, DS-4/CL-3) | LEGAL | LEGAL (rule sentence must exist) | COND: outcome rules only if discoverable (IN-9 01:39); ILLEGAL for rules of engagement, literals (DS-25), conventions (CL-5) | COND: ILLEGAL for rules of engagement (IN-15) and criterion text (JD-6, J11) | LEGAL (CL-7, CL-10, TS-11, TS-24, TS-30 duties) |

## Precheck commands to automate (run on a scratch copy)
- `python3 $KIT/structure_qc.py B; python3 $KIT/instruction_qc.py B; python3 $KIT/tests_qc.py B; python3 $KIT/judge_qc.py B` (exit 0/1/2).
- `python3 $KIT/exe_copy.py B /tmp/x`, `--stub`, `--owner-only` (refuses on A1-A4/W1-W7 fails).
- Gaps the scripts miss: `grep -rnwE 'TODO|FIXME|XXX|PLACEHOLDER' B` (F0a fail, X2 only warns); `grep -rnE '\{\{[^}]*\}\}' B` (lowercase braces pass X2); ENV HOME is line 2-3 after FROM (FC-S24, S10 does not check); `grep -n litellm== B/tests/Dockerfile` equals 1.105.0 (K8 only warns); instruction paths under /app/data that only a RUN creates (C4 false fail).
- Computable numbers: CL-2 stub/forgery share, CL-4 one-fact-wrong score, O1 overlap (solve.py only; solve.sh-only oracles escape), test count 10-35, judge count 8-35, Sum|neg|<=Sum pos per channel, reward.toml repr(0.5/P).

## Lessons for the master
1. IN-15 covers rules of engagement only; outcome rules may be withheld if derivable and testable (01:39, 02:70, FC:498). Fix PLAYBOOK L13 and COMMON_RULES Never 6.
2. The kit has no 70 cap (03:62 "at most 35 (warn)"). 70 is our house rule; say so.
3. AL-28 cross-layer is one act paid in both layers, any size. Don't price a cheat in tests AND judge.
4. Cascades are the live risk: CL-4 can fail them. Add an instruction sentence that only exact documents count (CL-4 exemption) and keep per-document tests separate.
5. Conduct criteria w3 that the oracle cannot show (J2) fail JD-7; either the oracle does it or drop them.
6. Kit is internally inconsistent in places (K1, K2, K5, K7); expect reviewers to vary there and cite the stricter line in our own fixes.
7. QC_RULINGS has 2 verdicts the kit makes stricter (TS-20 inversion, DS-4 prefixes = fail) and one stale owner (L44 -> TS-30/H6).
8. qc_authoring_checklist is stale on chmod 700, litellm pin, retired annotation keys (J6 fail), owner-only run.
9. Template R6 claim UNVERIFIED: 04 has no R6; the R2 grader-read template (04:21) may be JD-11 residue since tests/ is not uploaded (FC:498).
