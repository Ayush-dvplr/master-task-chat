# R4 Research: learn from the teammates' tasks (anubis-stage-1), with a self-improving angle log

Board id: `1d26a6e`
This prompt is saved at `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/_upgrade/20261028T1930_R4_teammate_repo_mining.md`. After any compaction, re-read it, then `OUT/TODO.md`.
OUT = `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261028_upgrade/R4_teammate_repo/`

This is a research session, one of 5 parallel upgrade sessions (R1-R5). You study the tasks our teammates made and turn what made the hard ones hard into knowledge we can use, and you set up the learning prompt so that each future run looks at a new angle. You change no rule file and no task. A later plan session merges R1-R5; nothing is applied until Ayush says "proceed".

## Ayush's words (28 Oct 19:00-19:35 IST)
- "i have few good tasks similarly i wants to research and improve all the very also, also this learning prompt will also improve itself to find different angle and everything"
- "I have a repo where there some good tasks made by my teammates and i wants you learn and improve from there, flag me if i am incorrect or you can ask me follow up questions too"
- Answers: repo `/Users/mac/Desktop/Terminal Bench/anubis-stage-1` (git clone of EtharaOrion/anubis-stage-1, 90 task folders, 15 contributors, Opus average 0.52; README: 52 Easy 50-87.5%, 25 Medium 37.5-50%, 6 Hard 25-37.5%, 7 Expert < 25%). **Read-only, no git pull.** The **13 Hard + Expert tasks are the models**; Easy and Medium are the contrast; all 90 trajectories are mined for where Opus loses points. **Learn patterns only**: levers, structure, rubric and test style; never copy a task idea or data. The learning prompt improves itself by an **angle log + a versioned prompt** (each run records the angles it tried and what it found, picks untried angles next, and proposes the next prompt version, which the master checks before use).
- New gate target: **final < 40** (Ayush "Target <40 now").

## Rules that survive compaction (copy this section word for word into any compaction summary)
- First thing and last thing: `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" 1d26a6e`.
- Tools work in every turn; get IST time with `TZ=Asia/Kolkata date`.
- READ ONLY everywhere except OUT and `/tmp/R4-repo-*/`. Git in anubis-stage-1: read-only commands only (`log`, `show`, `status`, `rev-parse`); **no pull, fetch, checkout, commit**. No edits to `master_chat_tasks/` (including `registry/peer_tasks.json`: the master adds entries later), the harness clone, `QC/`, `Anubis_Tasks_Samples/`, `~/Downloads`. No Docker, no harness runs.
- Analysis scripts live in `OUT/scripts/` and must re-run from scratch.
- Keep `OUT/TODO.md` and `OUT/LOG.md` current. Read at most 50 KB per read; parse report.json / trajectories with python.
- Every claim cites file:line, a trajectory step index, or a script output. INFERRED / UNVERIFIED labels. A low score is NOT evidence of a good lever until you show it is genuine.

## Read first
1. `/Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/templates/P14_task_analysis_v1.md` (Phase A genuineness, Phase B per-task build and loss analysis, Phase C group summary: use its method) and `P15_research_angle_v1.md` (the current learning/angle prompt), `prompts/templates/CHANGELOG.md`.
2. `knowledge/LEVER_RULES_v3.md` by path, `knowledge/LEAK_LIBRARY.md`, `knowledge/KNOWLEDGE.md`, `prompts/templates/_COMMON_RULES_v5.md` (Never 6, 8, 11).
3. What we already studied: `master_chat_tasks/registry/peer_tasks.json` (20 tasks) and `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/peer_manifest.py" check "/Users/mac/Desktop/Terminal Bench/anubis-stage-1"` (lists NEW or CHANGED tasks; it is read-only); `master_chat_work/_dev_research/peer_levers/`, `delivery_study/`, `delivery_study2/`, `self_discovery/`, `hardness_notes/`.
4. The repo: `anubis-stage-1/README.md` (difficulty table, target mix), each task's `task.toml`, `instruction.md`, `environment/`, `tests/` (test_output.py, judge.toml, reward.toml, test_weights), `solution/`, `trajectories/claude-opus-5/run_1/` (report.json, verifier/reward.json, the agent trajectory).
5. Another session (R3) is checking the QL's `~/Downloads/hardness.md`, which was measured on `Anubis_Tasks_Samples/Final_Delivery`. You may read hardness.md for its taxonomy, but do not re-verify it; mine anubis-stage-1 on its own terms.

## Work
1. **Inventory** all 90: id, contributor (git log author), domain, final/tests/judge split from report.json, number and weight distribution of checks, hidden vs shipped checks, judge size. Mark new vs already studied.
2. **Genuineness (P14 Phase A) for the 13 Hard + Expert.** For each, decide whether the low score comes from a fair lever, or from a broken/flaky test, a hidden or ambiguous rule, an unshipped fact, an environment fault, or a judge quirk. **Flag Ayush clearly** if a "good" task is low for an unfair reason (he asked to be told if he is wrong).
3. **Per-task cards** for the genuine Hard/Expert tasks (P14 Phase B): what the agent did step by step, where exactly it lost (check ids + weights, trajectory steps), which lever held, how the instruction/data made it fair yet hard, test and rubric style. In our vocabulary (LEVER_RULES_v3 L1-L11, S1-S11, H1-H9) and new names where none fit.
4. **Contrast**: what the Easy tasks lack or do that leaks points, with counts across the 90 (e.g. weight concentration, hidden-instance share, interlocking inputs, rerun-on-fresh-inputs, judge probe style). Separate the confounds (contributor, domain).
5. **Lever candidates**: mechanism, evidence, legality under our rules, how to apply in a build/harden, and the proof a pilot must give.
6. **Angle log + self-improving prompt.** Create `OUT/ANGLES.md`: one row per angle tried this run (angle id, question, method, tasks covered, result in one line, strength of evidence), then a ranked list of UNTRIED angles for the next run (e.g. by contributor style, by judge negative design, by data-file count, by time-to-first-write in trajectories, by what the agent self-tested). Draft `OUT/drafts/P15_research_angle_v2.md` (and `P14_task_analysis_v2.md` if its method needs changing) that (a) reads ANGLES.md first, (b) must pick at least 2 untried angles, (c) appends its own rows, (d) ends by proposing the next version's changes in a `## Proposed prompt changes` section with a CHANGELOG line. Drafts only; never write into `prompts/templates/`.

## Output
`OUT/FINDINGS.md`: 1. Inventory summary (+ `OUT/inventory.csv`). 2. Genuineness verdicts for the 13 (and flags for Ayush). 3. Cards (`OUT/cards/<id>.md`, summary table here). 4. Contrast findings. 5. Lever candidates. 6. Angle log summary and the prompt drafts. 7. Questions for Ayush (numbered, each with your recommended answer). 8. `## Lessons for the master` (max 5 lines).
Also `OUT/result_1d26a6e.json` (must parse): `{"sha":"1d26a6e","status":"DONE|BLOCKED","findings":"<path>","tasks":90,"models_genuine":N,"models_flagged":N,"levers":N,"angles_tried":N,"angles_untried":N,"drafts":[...]}`.

## Stops
- Done: reply in at most 15 lines, ending with `done: /Users/mac/Desktop/Terminal Bench/master_chat_work/20261028_upgrade/R4_teammate_repo/FINDINGS.md`.
