# R3 Research: verify the QL's hardness.md and turn it into proven levers

Board id: `0036eb5`
This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_upgrade/20261028T1930_R3_hardness_md_verify.md`. After any compaction, re-read it, then `OUT/TODO.md`.
OUT = `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261028_upgrade/R3_hardness_md/`

This is a research session, one of 5 parallel upgrade sessions (R1-R5). You check every claim in a document our QL shared, against the raw files it was measured from and against our own run evidence, and you sort its levers into proven / promising / weak / false. You change no rule file and no task. A later plan session merges R1-R5; nothing is applied until Ayush says "proceed".

## Ayush's words (28 Oct 19:00-19:35 IST)
- "have a md file shared by my QL might be correct or not but we can verify and make new levers and strong proven levers"
- The file: `/Users/mac/Downloads/hardness.md` (21,042 bytes, 28 Oct 19:22). Title: "Where Claude Opus 5 loses points, and which hardness levers do the work". It says it was measured on 2026-10-27 from 85 bundles in `Anubis_Tasks_Samples/Final_Delivery`, one `trajectories/claude-opus-5/run_1/report.json` each.
- New gate target: **final < 40** (Ayush "Target <40 now"); tests < 85 and rubric < 85 unchanged unless evidence says otherwise. hardness.md section 8 claims a recipe that holds Opus 5 under 40: check it hardest.

## Rules that survive compaction (copy this section word for word into any compaction summary)
- First thing and last thing: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" 0036eb5`.
- Tools work in every turn; get IST time with `TZ=Asia/Kolkata date`.
- First action after rename: copy `/Users/mac/Downloads/hardness.md` to `OUT/hardness_source.md` and record its sha256 in LOG.md. Work from the copy.
- READ ONLY everywhere except OUT and `/tmp/R3-hardness-*/`. No git writes. No edits to `master_chat_tasks/`, the harness clone, `QC/`, `Anubis_Tasks_Samples/`, `anubis-stage-1/`, `~/Downloads`. No Docker, no harness runs.
- Your own analysis scripts live in `OUT/scripts/` and must re-run from scratch (`python3 OUT/scripts/<name>.py` prints the numbers you report).
- Keep `OUT/TODO.md` and `OUT/LOG.md` current. Read at most 50 KB per read (report.json files: parse with python, never cat them all).
- Every claim cites file:line, a script output, or a report.json path. INFERRED / UNVERIFIED / did not run labels. One run per task means one sample: say so when a claim leans on single tasks.

## Read first
1. `OUT/hardness_source.md` in full (sections 1-9; section 9 gives the formulas and field semantics).
2. Our rules: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v3.md` by path (Law-1 v3.5, section 1C proven levers, levers L1-L11, gate v3.6, holes list), `knowledge/LEAK_LIBRARY.md`, `knowledge/KNOWLEDGE.md` (section T), `prompts/templates/_COMMON_RULES_v5.md` (Never 6, 8, 11: no hidden rules, no trap explanations, no shipped answers).
3. Prior studies, so you do not redo them (say what is new vs them): `master_chat_work/_dev_research/delivery_study/`, `delivery_study2/` (g1-g4 + synthesis_720e1d7), `hardness_notes/HOW_TO_MAKE_HARD_1.md`, `HOW_TO_MAKE_HARD_2.md`, `peer_levers/`, `trajectory_hardening/`.
4. Our own run evidence: `master_chat_tasks/registry/scores.jsonl`, every `master_chat_work/*/gate_run_a*/TRIP.md` and `traj_a*/`, `registry/tasks.json` (pushed tasks and their scores).

## Work
1. **Reproduce the data set.** `Anubis_Tasks_Samples/Final_Delivery/` has 94 entries; the doc says 85 bundles. Reconcile (which entries are bundles with a report.json, which are not). Check the field semantics in section 9 on 3 tasks by recomputing `final_reward` from report.json and comparing with the stored value.
2. **Every numbered claim** (headline table, channel split, "tests half weaker in 55 of 85", the 59417607 example, section 3 failure modes, weight as discriminator, check-name tokens, most-failed checks, section 4 judge themes incl. "overclaiming not cheating", section 5 the ~70 ceiling, section 6 levers L1-L11, section 7 "what does NOT make it harder" with its correlations, section 8 recipe): recompute and mark CONFIRMED / PARTLY (say the real number) / WRONG / UNTESTABLE. Keep a claim table with doc line, claim, your number, script, verdict.
3. **Check the inference, not only the arithmetic.** For each lever, is the effect causal or a confound (task domain, contributor, test count, weight scheme)? Use within-task contrasts where possible (shipped vs hidden checks in the same task, like 59417607). Note where n is too small.
4. **Overlap with anubis-stage-1**: how many Final_Delivery task ids are also in `/Users/mac/Desktop/Terminal Bench/anubis-stage-1/` (90 folders, same uuid style), and whether their report.json files match. (Another session, R4, mines anubis-stage-1 itself; you only report the overlap.)
5. **Cross with our evidence.** For every lever in the doc: does our own data (our gate runs, our leaks) agree, disagree or say nothing? Is it legal under our rules (Law-1, no hidden rule, no trap explanation, no shipped answer, W7, G5 rerun promise)? Is it already in LEVER_RULES_v3 under another name?
6. **New lever candidates.** From the data, propose levers the doc does not have or under-weights. Each needs: mechanism, evidence (numbers + files), legality under our rules, how a build/harden would apply it, and the proof a pilot must give before it counts as PROVEN (what measurement, what threshold).
7. **Gate < 40.** From the Final_Delivery and our data: which task shapes reached final < 40 honestly (not by broken tests or hidden rules), and what tests/rubric split they had. Is tests < 85 / rubric < 85 still the right side condition? Recommend, with numbers.

## Output
`OUT/FINDINGS.md`: 1. Data set reconciliation. 2. Claim table (all claims). 3. Lever verdicts: lever, doc claim, evidence for, evidence against, our data, legality, verdict PROVEN / PROMISING / WEAK / FALSE / ILLEGAL, how to apply. 4. New lever candidates with proof requirements. 5. Gate < 40 recommendation. 6. What is new vs our prior studies. 7. Questions for Ayush and for the QL (numbered, each with your recommended answer). 8. `## Lessons for the master` (max 5 lines).
Also `OUT/claims.csv`, `OUT/levers.csv`, `OUT/scripts/`, `OUT/result_0036eb5.json` (must parse): `{"sha":"0036eb5","status":"DONE|BLOCKED","findings":"<path>","claims":N,"confirmed":N,"partly":N,"wrong":N,"levers_proven":N,"new_levers":N}`.

## Stops
- BLOCKED: report.json files missing or unreadable; say which.
- Done: reply in at most 15 lines, ending with `done: /Users/mac/Desktop/Terminal Bench/master_chat_work/20261028_upgrade/R3_hardness_md/FINDINGS.md`.
