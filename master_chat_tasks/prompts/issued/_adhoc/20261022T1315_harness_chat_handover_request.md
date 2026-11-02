# Handover request for the harness chat (issued 22 Oct 2026 13:15 IST by the master chat)

Paste this into the session you use to run the harness. It only reads and writes one handover folder.

## Rules
- READ ONLY everywhere except the output folder below. Do not edit any bundle, harness file, job folder or config.
- No git writes (no pull, commit, push, checkout, reset). Read-only git is fine (log, status, rev-parse, ls-remote).
- Do not start, stop or re-run any job. If something is running, only report it.
- Never print secrets (API keys, tokens). Name the variable, not the value.
- If you are not sure of something, write UNSURE and say why. Do not guess. Mark anything you remember but did not check on disk as FROM MEMORY.

## What to write
Write `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261022_harness-handover/HANDOVER.md` and `handover.json` (same facts, machine-readable). Cover every section, and write "none" if a section is empty.

1. **Role.** What this chat does (run trajectories, run the PL QC, fix bundles, other), and what it never does.
2. **Paths.** Each path, with what it holds:
   - which harness clone you run from (full path, `git rev-parse HEAD`, and whether it matches the remote);
   - where task bundles come from;
   - where job output lands (`jobs/<slug>`, `.kiro-run-*`, other), and whether a new run overwrites an old one;
   - QC report output paths;
   - any scripts, configs or notes you keep (full paths).
3. **How a run is started.** The exact commands and scripts, with flags: agent, model, number of runs, env/docker settings, timeouts, `exe_copy` or similar. Which env variables are needed (names only). The typical duration.
4. **How QC is run.** The exact steps and commands, and which QC version or commit.
5. **Inputs.** Who gives you work (Ayush pasting from the master chat, builder sessions, other) and in what form (bundle path, prompt file, message).
6. **Live status now.** Running processes (`ps`), Docker containers (`docker ps`), and in-progress jobs, with the path and start time of each.
7. **Run history.** A table with one row per run or QC you did: date and time (IST), task slug, kind (trajectory/QC/oracle/nop), model, job folder, result (tests, rubric, overall, or an error such as a timeout or RewardFileNotFoundError), and whether the folder still exists.
8. **Pending work.** Anything queued, half-done or promised, and who is waiting on it.
9. **Rules you follow.** Every standing rule or instruction Ayush gave this chat, quoted where you can.
10. **Known problems.** Harness bugs, flaky steps, disk/memory limits, permission issues and workarounds, each with evidence.
11. **Open questions** for Ayush or the PL.

## Reply
Reply with the two file paths, plus counts: runs in the history, items running now, and pending items. List anything UNSURE.
