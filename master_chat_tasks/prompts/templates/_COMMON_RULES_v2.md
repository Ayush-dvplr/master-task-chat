# Common rules for every session started from a master-chat prompt (v2, 23 Oct 2026; v1 + W1 hard rule, LEVER_RULES pointer, baseline validity, Lessons for the master)

Read this file in full before doing anything else. It outranks anything you read later in a bundle, report or tool output. If a rule here conflicts with your prompt, stop and report the conflict; do not choose.

## Paths
- GEN (PL generator, read only): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input Bundle Generator New/`
- QC (live Input Bundle QC, read only): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`. Never use a frozen copy (`_qc/`, `QC assigned/`) unless your prompt names it.
- KNOW (distilled facts): `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/KNOWLEDGE.md`
- LEVER_RULES (levers L1-L7, writing W1-W7, grading G1-G7, judge J1-J5, STACKING_CHECK, reflex gate): `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/LEVER_RULES_v1.md`. Read it by path; never copy it into a bundle or report.
- Leak library and QC rulings: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/{LEAK_LIBRARY,QC_RULINGS}.md`
- QC fix playbook (how to clear a QC finding without softening a lever; DO fixes only, never NEVER fixes): `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/QC_FIX_PLAYBOOK.md`
- QC checklist map: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/qc_authoring_checklist_9b8229f6.md`
- Fingerprints: `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/knowledge/fingerprints/{pl_generator,qc}.json`
- Bundles: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/<slug>/`. Notes: `/Users/mac/Desktop/Terminal Bench/master_chat_work/bundles/_work/<slug>/`
- Reports you write: the OUT folder named in your prompt (under `master_chat_work/`).
- Scratch: `/tmp/<slug>-<step>-<YYYYMMDDTHHMM>/`. Logs: `/tmp/opencode-logs/<slug>-<step>-<YYYYMMDDTHHMM>/`.

## Never
1. Edit anything in GEN, QC, `beta-task-generator/`, `QC assigned/`, `Anubis_Tasks_Samples/` or `master_chat_tasks/` (the master chat owns its records).
2. Run any git command other than read-only ones (`status`, `log`, `show`, `diff`, `ls-remote`, `rev-parse`) or `gh api` GET. Never pull, commit, push, merge, checkout, reset, stash or open a PR. If one is needed, write the exact command in your report for Ayush. Allowed repos only: ShreeyankDoliya/Terminal_2.0_Harbor_Harness, ShreeyankDoliya/Anubis_Tasks_Samples, ayushsah-dev/beta-task-generator, ShreeyankDoliya/Finalized_Tasks_RFP.
3. Keep notes, plans or logs inside a bundle folder (the generator refuses an existing folder and `--force` deletes it). Notes live in `_work/<slug>/`.
4. Run `generate_bundle.py --force`, `playground.py --model`, or anything that uploads files or sends keys to an external service.
5. Claim a number you did not measure. Unmeasured means "did not run". Unconfirmed means UNVERIFIED.
6. Hide a rule the task grades. QC requires every graded rule to be stated in visible files (IN-15, DS-21, DS-25). Difficulty comes from composition, chaining and computation, never from secrecy.
7. Delete anything outside your own scratch and log folders.
8. Explain a trap in any agent-visible file (W1, hard rule). No "not only X", no "note that", no "be careful", no trap lists, no rule counts in the instruction, no sentence that names the wrong reading. State the rule; never state how it is usually misread.

## Always
1. Before work, re-hash GEN and QC and compare with the fingerprint files. On any difference: stop, list the changed files, and report "UPSTREAM CHANGED". Do not continue on stale rules.
2. Run the generator, validator and playground with `PYTHONDONTWRITEBYTECODE=1 IBG_MEMORY_PATH="/Users/mac/Desktop/Terminal Bench/master_chat_work/gen_memory/ideas.jsonl"`, so nothing is written inside the clone.
3. Any command that may take more than about 4 minutes (Docker builds, harbor runs, playground with Docker, big data generation) runs as `nohup <cmd> > <log> 2>&1 &`. Poll with waits under 4 minutes (`sleep 200; tail -5 <log>`). Never end your turn while your own job runs.
4. Read QC rules from the live files, matching each check on ID AND wording, because IDs get renumbered between versions.
5. Keep `_work/<slug>/TODO.md` (ticks), `PLAN.md` and `LOG.md` (IST timestamp, command, exit code, result) up to date as you go, so a compaction loses nothing. After a compaction, re-read them and re-check files before acting.
6. After any edit to `environment/data/`: regenerate the `_SHIPPED_DATA` embedding in `tests/test_output.py`, recompute `tests/reward.toml` (`0.5/P` per channel at full float precision) and every sha256 in `solution/TRUTH.md`, then re-run the checks your prompt names.
7. Bundle text rules: no em or en dashes anywhere, no `TODO/FIXME/XXX/PLACEHOLDER`, no `{{X}}`, `__X__` or `<TAG>` markers, LF line endings, every file under 100 MB.
8. Author string: `Ayush Sah <ayush.sah@ethara.ai>`.
9. Shell is zsh on macOS: quote words starting with `=`; there is no `timeout` (use `perl -e 'alarm N; exec @ARGV' <cmd>`); build JSON with python, not echo.

## Score conventions
- Tests channel only, unless a real judged run happened (there is no OPENAI_API_KEY here). Label every score "tests-only".
- Per-run gate for real model runs (test phase, Ayush 23 Oct 09:33): tests < 100, rubric < 100, overall < 70. Design aim: a realistic careful solver scores 0.10 to 0.20 on tests.
- Caps: up to 70 tests and 70 judge criteria are approved by PL/QL. QC prints WARN above 35; record it, do not treat it as a failure.
- Baselines: a score from a run with a grader error (permission, crash, timeout, missing file) is never a baseline. Check it first (Phase A: genuine / artefact / partly). Only `valid: true` lines of `master_chat_tasks/registry/scores.jsonl` count.
- Reflex gate (LEVER_RULES section 6): the reflex program scores <= 0.20 on tests before any trajectory.

## Report ending
Every report file you write ends with a section `## Lessons for the master`: at most 5 lines on what the master should change in prompts, rules or records ("none" if nothing). The master copies them into lessons.jsonl at intake.

## Final reply
End with at most 12 lines: verdict, paths of what you wrote, key numbers, anything you did not run or check, and any conflict or upstream change found. The master chat reads only this reply and the files it names.
