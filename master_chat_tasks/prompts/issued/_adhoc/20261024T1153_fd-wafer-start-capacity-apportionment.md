You are taking apart one delivered peer task, end to end, to learn exactly why it passed QC and still beat Opus, and what we should copy. Board id: `e841c43`. This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_adhoc/20261024T1153_fd-wafer-start-capacity-apportionment.md`.

Why (Ayush, 24 Oct, high priority): the 6 tasks in `Anubis_Tasks_Samples/Final_Delivery` are delivery-ready. They passed the team QC and each has a real claude-opus-5 run. They are the best evidence we have of what "accepted and hard" looks like. Our own bundles loop through QC rounds and Opus scores 100 on most. One session per task; the master merges all 6.

## Rules that survive compaction
- First thing: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" e841c43`. If it fails, note it and carry on. Run it again at the very end.
- Tools are always available; never claim otherwise without a real call and its quoted error.
- After every compaction: run `TZ=Asia/Kolkata date`, re-read this prompt, then `OUT/TODO.md`, and continue from the first unticked item. Copy this section word for word into any compaction summary.
- Keep `OUT/TODO.md` and `OUT/LOG.md` current after every step. Read files in pieces of at most 50 KB; trajectory.json may be large, so page through it.
- READ ONLY on: `Anubis_Tasks_Samples/` (all of it), the harness clone, the QC kit, every bundle, `QC/`, `master_chat_tasks/`. Work on COPIES in `/tmp/fd-wafer-start-capacity-apportionment-<YYYYMMDDTHHMM>/`. Never run `harbor run`, never call a model, never upload anything.
- Docker: first run `docker ps`. If any container you did not start is running (the harness runner uses Docker one task at a time), do not start containers; use host Python in a venv under your scratch dir instead and say so. Otherwise you may build the task images from your copy and run `solve.sh` and `pytest tests/test_output.py` (never the LLM judge). Remove your own images and containers at the end. No `--delete`, no prune.
- `Final_Delivery_Internal/mask_map.json` maps the masked id to the real slug. Read it only to confirm the mapping; never copy its paths into a file meant for delivery.
- Do the work yourself. No subagents.
- Every claim cites file:line, a command with its quoted output, or a trajectory step number. If you could not confirm it, write UNVERIFIED.

## The task
- Delivered folder: `/Users/mac/Desktop/Terminal Bench/Anubis_Tasks_Samples/Final_Delivery/aa314fee-a873-5778-9d55-e8892e6d7cda/` (masked id `aa314fee-a873-5778-9d55-e8892e6d7cda`, real slug `wafer-start-capacity-apportionment`, author Anjali Kumari, category Optimization, QL Sugam_Agrawal). Run: `trajectories/claude-opus-5/run_1/` (agent/trajectory.json, artifacts/, verifier/, trajectory_usage.json, result.json, config.json) and `trajectories/claude-opus-5/pass_summary.json`.
- Recorded scores: combined 17.64 = tests 3.03 (2 of 27 passed) and rubric 32.26 (29 criteria); reward-details.json is synthesized: use ctrf.json + score.json.
- Team QC report: none found in `Perfect_for_Delivery`; search `Anubis_Tasks_Samples` and `QC/` for one and say if none exists.
- Older copies to diff: none found under `Anubis_Tasks_Samples`; search once more by slug and say if none exists.
- Earlier peer mining on an older copy (read, do not redo): none.

## Shared inputs
- Precheck (live kit 71a653b2 plus our extra checks): `"/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/precheck.sh" <bundle copy>`. Make the copy WITHOUT `trajectories/`, which is how the team QC ran it.
- Loss table: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/loss.py" "<task folder>"`. If `reward-details.json` says `"synthesized": true` it holds no per-item detail. Then build the table yourself from `verifier/ctrf.json` (tests), `verifier/score.json` (judge criteria, with reasoning) and `verifier/test-stdout.txt`, using the weights in `tests/test_output.py` / `tests/reward.toml` / `tests/judge.toml`.
- Kit check list: `master_chat_work/20261024_process/qc_reverse/A/checks.json` (302 checks with pass conditions) and `A/LEVER_COMPAT.md`. Firing history: `qc_reverse/B/by_check.json`.
- Our rules: `master_chat_tasks/prompts/templates/_COMMON_RULES_v3.md`, `P2_build_v3.md`, `master_chat_tasks/knowledge/QC_FIX_PLAYBOOK_v2.md`, `master_chat_tasks/KNOWLEDGE.md` (bar: zero findings including warns, at most 35 tests and 35 criteria, gate tests<100 rubric<100 overall<70 on 2 runs).
- OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261024_process/final_delivery/wafer-start-capacity-apportionment`

## Phase 1: identity, provenance, integrity
1. Confirm the id-to-slug mapping, author, category and QL folder. List every older copy named in the task block and run `diff -rq` between each one and the delivered folder (ignore `trajectories/`). For each changed file, say what changed and why it matters (fix made for QC, hardening, masking rewrite).
2. Masking residue: grep the delivered folder for the real slug, author names, host paths (`/Users/`, `.kiro-staged`, `macbookpro`) and anything that would de-mask it.
3. Author-note and answer leaks: grep `environment/` (everything the agent can see) for TRAP, LEVER, grader, hidden test, answer key, expected values, and any file that copies figures from `solution/` or `tests/`.

## Phase 2: kit verdict
1. Run precheck.sh on the copy and save the full output as `OUT/precheck.txt`. Table: fails, minors, warns, our extra-check hits, test count, criteria count.
2. Compare it with the team QC report, if the task block names one, finding by finding: which warns the tasker accepted, and whether our live kit agrees today. List every point where this delivered task breaks one of OUR rules (warns, more than 35 tests, overall over 70, anything in COMMON v3) yet was still delivered. Quote our rule and file:line for each.

## Phase 3: scores, re-graded
1. Recompute the combined score from the raw verifier files and confirm `pass_summary.json`. Explain any mismatch (for example `result.json` reward against `reward.json`).
2. Build the full loss table: every test and criterion with weight, points kept, points lost, and for negatives whether it fired.
3. Re-grade: run the delivered tests on the agent's own outputs in `run_1/artifacts`, and on the oracle output from `solution/solve.sh`. The agent's re-grade must reproduce the recorded test score; the oracle must score 100%. Also run the tests on empty output (nop) and say what it scores. If you cannot run them, say why and mark this phase UNVERIFIED.

## Phase 4: where Opus lost, from the trajectory
Read `run_1/agent/trajectory.json` from start to finish. Then:
1. Timeline: steps, wall time and tokens (`trajectory_usage.json`), the files it opened and in what order, when it first wrote output, whether it tested its own work, and whether it ever touched `/tests`, `/logs/verifier` or `solution/`.
2. For every lost test or criterion: what the agent did, with the step number; the right answer and the line in the instruction or data that settles it (quote it, or say none exists); and one cause class: GENUINE computation trap / AMPLIFICATION (one bug billed across many tests) / AMBIGUITY (the spec does not settle it) / HIDDEN RULE (rule not stated anywhere the agent can read) / CONDUCT (judge criterion on process) / JUDGE ERROR (the judge scored it wrong; prove it with score.json) / ARTEFACT (harness, timeout, environment).
3. Bug count: group the losses into distinct agent mistakes. For each mistake: points lost and how many tests it touched. Where you can, prove it: patch only that mistake in a copy of the agent's outputs (or its script), re-run the tests and record the points that come back.
4. Did the agent read the line that would have saved it? Quote the step where it read it, or show that it never opened that file.

## Phase 5: design anatomy
1. Instruction: length, section structure, how rules are stated (explicit, by reference to a data file, left to derive), and what it deliberately leaves out.
2. Data: file count and formats (xlsx, pdf, parquet, sqlite, Latin-1 and so on), size, decoys, hidden or next-period tiers, and where each trap sits in the data.
3. Tests: count, weights, visible against hidden tiers, digest or whole-population grading, how many tests one concept touches, negatives, anti-hardcode checks, timeouts.
4. Judge: count, weights, output against trajectory/conduct targets, negatives, and whether the oracle's own behaviour would pass every criterion.
5. Solution: size, approach, and runtime.
6. Robustness: would a second Opus run score about the same? Name the points that ride on a single yes/no decision, and estimate the spread.

## Phase 6: what we take from it
One table: design choice | evidence (file:line, points it produced) | kit check that allows it (checks.json id) | do our v3 templates allow it (file:line) | adopt / adapt / avoid. Then at most 6 concrete edits to our templates or playbook, each naming the file and line and the evidence row behind it. Make no edits yourself. If the task block lists earlier peer mining files, say where you agree or disagree with them; do not redo them.

## Deliverables
- `OUT/ANALYSIS.md`: Phases 1-6 with the tables, and `## Verdict` first: is the low score GENUINE, PARTLY or ARTEFACT, in one paragraph.
- `OUT/loss_table.md`, `OUT/precheck.txt`, `OUT/regrade.txt` (commands and outputs).
- `OUT/result.json`: {"board": "e841c43", "status": "done|partial", "id": "...", "slug": "...", "scores": {"tests": n, "rubric": n, "combined": n}, "regrade_matches": bool|null, "oracle_100": bool|null, "nop_score": n|null, "kit": {"fails": n, "minors": n, "warns": n}, "breaks_our_rules": [..], "loss_by_class": {class: points}, "distinct_mistakes": n, "points_per_mistake": [..], "verdict": "GENUINE|PARTLY|ARTEFACT", "adopt": [..], "avoid": [..], "template_edits": [..], "unverified": [..]}.
- Final reply: at most 6 lines, with the OUT path.
