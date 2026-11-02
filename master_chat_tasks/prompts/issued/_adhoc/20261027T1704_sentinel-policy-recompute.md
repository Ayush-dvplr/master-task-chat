# Hardness-guide verification (READ-ONLY research session) — ec452c9
First thing, rename this session: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" ec452c9` (if the output does not show ec452c9, note it in the report and carry on; never retry on another ID).

This prompt: /Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261027T1704_sentinel-policy-recompute.md. Your only writable place is OUT: /Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/hardness_notes/verify_ec452c9

## Question (from Ayush)
Two documents claim to say how to make Harbor 0.24 tasks hard. "This can be completely wrong or some parts can be correct, you have to figure out." Decide, claim by claim, what is right, what is wrong, what is untested, and what conflicts with QC or with our own measured results.

Documents (read in full):
- D1 `/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/hardness_notes/HOW_TO_MAKE_HARD_1.md` (87 lines; a generation prompt written for another author's machine, paths under /home/shubhi...).
- D2 `/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/hardness_notes/HOW_TO_MAKE_HARD_2.md` (2193 lines, "Hard Task Hardening Guide (Harbor 0.24.0)"). Read in pieces of at most 400 lines.

## Hard rules
1. READ-ONLY outside OUT. Never edit bundles, Tasks_INPUT, QC/, master_chat_tasks/, master_chat_work/ (except OUT), the QC kit, the generator. No git writes. No harness runs. No Docker. No web lookups beyond checking that a cited paper exists, and only if the claim is load-bearing.
2. Scripts only under `perl -e 'alarm 300; exec @ARGV' python3 ...`; before you finish `ps` shows no python process of yours.
3. Every verdict cites evidence: a file path and line, a score row, a QC report finding ID, or a quoted D1/D2 line. No verdict from general knowledge alone; if you have only general knowledge, the verdict is UNTESTED.

## Evidence you must use
- Our measured results: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/registry/scores.jsonl` (every probe and run), `master_chat_tasks/lessons.jsonl`, `master_chat_tasks/feedback.jsonl`, `master_chat_tasks/knowledge/LEVER_RULES_v3.md` (section 1A/1C: which levers held against Opus and which were transliterated; v3.3 paused stated-rule levers), `knowledge/LEAK_LIBRARY.md`, `knowledge/QC_RULINGS.md`, `knowledge/QC_FIX_PLAYBOOK_v2.md`, `GOALS.md` (our gate: tests < 100 AND final < 70 on 2 runs; kill rule probe tests >= 95).
- Harden/blind/probe reports: `master_chat_work/2026102*_*/harden_*/HARDEN_REPORT.md`, `DIAGNOSIS.md`, `DESIGN.md` (kill tables), blind reports under `master_chat_work/*/blind_*/work/BLIND_REPORT.md`.
- QC kit (authority on what QC accepts): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (Final_checklist.md, gate files 01-05, the four scripts). QC reports: `/Users/mac/Desktop/Terminal Bench/QC/reports/<slug>/v*.md`.
- D2's own evidence: its section 15.1 cites `Output/kvec-meter-settlement-reconciliation/` -> check `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Output/kvec-meter-settlement-reconciliation/` and see whether the numbers and the judge description match the files. D1 names `Input Bundle Generator New/` (exists under the harness) and other paths: check which exist here.
- Pushed tasks that met the gate (emberforge, dispatch, match-replay, caldermoor, sentinel) and how they did it; parked tasks that stayed at tests 100 (cohort, data-product, sensor, metered before wave 2) and why.

## Work
Step 1. Claim list. Extract every actionable claim from D1 and D2 (a rule, a number, a lever, a quota, a measured result, a causal statement). Merge duplicates between D1 and D2. Expect roughly 80-150 claims; keep each to one line with its D1/D2 line numbers.

Step 2. Verdict per claim, exactly one of:
- CONFIRMED: our measurements or the QC kit agree (cite).
- CONTRADICTED: our measurements show the opposite (cite the runs).
- QC_CONFLICT: following it would fail or risk a QC rule (cite rule ID and kit file:line), or it disagrees with QC_RULINGS.
- GOAL_CONFLICT: correct in itself but aims at a different target than ours (e.g. 10% per channel vs our tests < 100 AND final < 70), or costs more than our gate needs.
- UNTESTED: plausible, no evidence here either way. Say what one cheap measurement would settle it.
- WRONG_FACT: a factual statement about files/paths/numbers that the files show to be false.
Columns: id, source (D1:L / D2:L), claim, verdict, evidence, impact on our pipeline (adopt / adapt / ignore), risk if adopted.

Step 3. Focus questions, answer each in ANALYSIS.md with evidence:
a) Withheld-but-derivable rules (D2 5.9, D1 "withheld-but-derivable rules" vs D1 "forbidden: hidden or unstated rules"). Is this the same as our paused stated-rule levers or a different lever? Has any of our bundles tried it, with what score? What QC rules does it touch (DS-21, CL-10, DS-25, F0e)? Verdict on whether it is worth one trial.
b) Judge counterfactual figures (D2 9.3: closing message must state 8-10 figures appearing in no artifact, judged at weight 5). Do our judges do this? Compare with our P-5 "probe band" approach (behaviour criteria the probe skipped). Does D2 15.1 (conduct criteria earned by habit) match our judge scores? Which approach fits QC JD-8/JD-15/JD-16 better?
c) Volume levers (50-60 files, >= 2000 lines each, >= 12 trap types, >= 12 traps per file). Our builds of 21-24 Oct had many stated traps and scored tests 100: does that contradict D2, or did those traps break D2's laws (stated not withheld, crash not silent)? Check against QC A3 cap (35 checks) and D2's ~30 checks.
d) Silent plausibility (D2 5.10, law 1) vs our P-3 levers that lose by timeout (district-heat, metered, schema wave 1). Does D2 imply our timeout-based levers give the model a recovery signal? What does our evidence say (did probes ever time at scale)?
e) Dependent chains and weight on late stages (D2 15.3, 5.7) vs our P-2 replay result (schema e3e74e6: strong programs exact on long replays).
f) Calibration gates (D2 section 10, T1 F/P >= 0.90, near-miss ladder, five solver profiles): compare with our kill-test + blind + probe method. Which parts would have predicted our real scores better?
g) Which D2 rules would have prevented our QC loops (sentinel v1-v7 findings), if any.

Step 4. OUT/RECOMMENDATIONS.md: what to adopt as-is, what to adapt (with the exact change to which of our files: LEVER_RULES_v3.md, templates P2_build_v4.md / P9 / _COMMON_RULES_v4.md, QC_RULINGS.md), what to ignore and why, and the 1-3 cheapest trials that would settle the biggest UNTESTED claims. Proposals only; apply nothing.

## Deliverables in OUT
- CLAIMS.csv (all claims with verdicts), ANALYSIS.md (counts by verdict first, then focus answers a-g, short), RECOMMENDATIONS.md.
- result_ec452c9.json: {"sha":"ec452c9","step":"hardness-guide-verification","claims":N,"by_verdict":{"CONFIRMED":n,"CONTRADICTED":n,"QC_CONFLICT":n,"GOAL_CONFLICT":n,"UNTESTED":n,"WRONG_FACT":n},"adopt":[...],"adapt":[...],"ignore":[...],"trials":[...],"report":"/Users/mac/Desktop/Terminal Bench/master_chat_work/_dev_research/hardness_notes/verify_ec452c9/ANALYSIS.md"}. It must parse.
Final message: 10 lines max: verdict counts, the 3 most useful correct ideas, the 3 most harmful wrong or conflicting ones, and the trials.
