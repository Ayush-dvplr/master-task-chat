DRAFT 27 Oct 2026, not issued. Board <SHA>. Prompt <PROMPT_PATH>.

# Lever audit A3: grading levers

You are a read-only research session. Do not edit any file outside your output folder. Do not run harbor, docker or any agent.

## Task
For each lever below, decide from real evidence whether it made claude-opus-5 lose points, and record how the tasks that used it built it.

Levers in scope: whole-document grading and per-row ownership (section 3, G1/G1a), the gate, S7 digest cascade, S9 self-referential artifact, S10 provenance gate, S11 scoped-exception decoy, wrong-reading negatives, mutation tiers, metamorphic checks.

Read first: `master_chat_tasks/knowledge/LEVER_RULES_v3.md` (definitions) and `master_chat_tasks/prompts/drafts/lever_audit/PLAN.md` (sources and the HELPFUL test).

## Method, per lever
1. Find every delivered task that uses it. Start from the study notes (delivery_study, delivery_study2 cards and GROUP_SUMMARY files, 24 Oct SYNTHESIS.md), then confirm in the task folder under `Anubis_Tasks_Samples/Final_Delivery/<uuid>/` (instruction.md, tests, judge.toml, solution).
2. For each such task, open `trajectories/claude-opus-5/run_1/verifier/ctrf.json` and `reward-details.json`. List the test ids and judge criteria that grade the lever, and whether each passed.
3. For each lost check, label it GENUINE (the rule is stated or settled by one shipped fact and Opus misread or skipped it), ARTEFACT (grader error, stale tree, timeout, permission) or HOLE (hidden rule or false claim, LEVER_RULES section 8). Read the agent log steps that show why, and cite them.
4. Add our own evidence: blind reads and probes in `master_chat_tasks/registry/tasks.json` and `registry/scores.jsonl` (valid lines only) where we used the lever. A blind program that got the lever right counts against it.
5. Describe how the strongest peer built it: file:line of the rule sentence, where the data plants it, how the tests grade it, what weight it carries.

## Verdict, per lever
- HELPFUL: GENUINE losses in at least 2 delivered tasks that passed QC, or in at least 2 of our fresh blind reads.
- WEAK: GENUINE losses in exactly 1 task, or only as an amplifier of other levers.
- NOT HELPFUL (DISABLE candidate): used in at least 2 tasks with no GENUINE loss, or leaked in our fresh blind reads with no peer GENUINE loss.
- UNKNOWN: fewer than 2 uses found.
Points must be raw test points or judge points from the files you read. Never estimate a number you did not see; write INFERRED next to any claim you reasoned rather than read.

## Output
Folder `master_chat_work/_dev_research/lever_audit/A3/`:
- `L_<lever>.md` per lever: uses (task uuid, file:line), checks and outcomes, GENUINE/ARTEFACT/HOLE labels with log citations, our evidence, how the strongest peer built it, verdict with one-line reason.
- `VERDICTS.md`: one table `| lever | verdict | delivered uses | GENUINE pts | our evidence | recipe in one line |`, then at most 10 lines of findings that cut across levers.

Finish with one line: `AUDIT A3 DONE <n levers> HELPFUL <a> WEAK <b> NOT_HELPFUL <c> UNKNOWN <d>`.
