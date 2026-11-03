STUDY PLAN FOR THE TEAMMATE TASKS (anubis-stage-2)

Status: DRAFT, waiting for Ayush (Q88). No helper runs until he approves.

WHAT IS THERE (checked by the master 3 Nov, git ls-tree of origin/main)
1. anubis-stage-2/ on main: 115 task folders (114 with instruction.md and task.toml), 12904 files, about 2.6 GB.
2. Each task: instruction.md, task.toml, environment/ (Dockerfile, data, docs), solution/ (solve.py, solve.sh, TRUTH.md), tests/ (test_output.py, reward.toml, judge.toml, test.sh), trajectories/claude-opus-5 and trajectories/glm-5.3.
3. Each trajectory folder has pass_summary.json (average combined score, test percentage, rubric percentage, per run) and per run verifier/reward-details.json (which checks were lost), the agent program under artifacts/, and the full trajectory.json (the big part).
4. No QC result files in the folder; Ayush says most passed QC, one or two may have failed.
5. task.toml holds author names and work emails. Study files will refer to tasks by id only.
6. 10 teammate tasks were already studied on 2 Nov (master_chat_work/20261102_test_design_study/deep2, cards). Those cards are reused, not redone.

PHASES
Phase 0. Index by script, no AI tokens (minutes).
  A Python script reads, for every task: id, category, short description, Opus tests %, rubric %, combined score and number of runs, GLM scores, number of tests and their weights (reward.toml), number of rubric criteria (judge.toml), instruction size, data size, verifier timeout. Output: tmp/S2-INDEX/INDEX.csv plus a short summary (how many tasks are under the gate, score spread, categories).
Phase 1. Pick, with Ayush.
  From the index: the tasks under the gate (tests under 85, rubric under 85, final under 40), plus about 5 high scoring tasks as contrast. Ayush approves the list.
Phase 2. Task cards (helpers, in batches).
  One card per picked task, at most about 3 KB, from the task files plus reward-details.json and the agent program (NOT the full trajectory.json unless needed for one question). Card fields: where Opus lost points (check ids, weights, WRONG, TIMEOUT or CRASH), the lever behind each loss and its kind (carrier, unfired branch, scale, misread rule, other), how the instruction words it (quotes), how it stays hidden yet solvable, test design (whole document, amplification, held out data), rubric design, anything that looks QC risky.
  Batches of about 8 tasks per helper, 3 helpers at a time, background. Each helper self checks its cards; the master spot checks 3 cards per batch.
Phase 3. Patterns (one helper, reads only the cards).
  PATTERNS.md: lever families with how often they appear and how many points they cost Opus, wordings that pass QC, test and rubric designs that amplify, what NOT to copy (to keep uniqueness), and how each pattern maps to the R0 lever kinds and the CR1 timeout decision.
Phase 4. Review with Ayush, then into the lever library and the hardening method (P4) and new task design (P9).

COST (rough, from earlier helpers: about 300k tokens for about 50 files read)
Phase 0: almost none. Phase 2: about 60k to 100k tokens per card, so about 2 to 4 million tokens for 30 to 40 tasks. Phase 3: about 200k to 300k. The number of tasks picked in Phase 1 decides the cost.

HOW IT SURVIVES COMPACTION
Every phase writes files in tmp/ and a row in WORKER_LOG.md; RESUME.md says which phase is running. A new session continues from the files.
