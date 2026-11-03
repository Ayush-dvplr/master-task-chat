STUDY PLAN FOR THE TEAMMATE TASKS (anubis-stage-2)

Status: v1 APPROVED 3 Nov (Q88); v2 below REPLACES Phases 1 to 4 (Ayush Q91, ENTRY 21), waiting for approval (Q93). Phase 0 DONE 08:43. Phase 1 pick list waiting for Ayush (Q91).

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

PHASE 0 RESULT (3 Nov 08:43, script tmp/S2-INDEX/make_index.py, INDEX.csv sha b811acf1, no AI tokens)
1. 114 tasks with an Opus 5 score (1 run each). 34 are under today's gate (tests under 85, rubric under 85, final under 40).
2. Opus final: min 4.91, median 45.74, max 78.52. Buckets: 0s 3, 10s 6, 20s 10, 30s 16, 40s 44, 50s 8, 60s 22, 70s 5. 44 tasks sit at final 40 to 50, just over today's gate.
3. Opus tests median 35.64; rubric median 54.1. So in teammate tasks the TESTS are where Opus loses most; the rubric is usually higher.
4. Test checks per task (estimated as 1 / test weight in reward.toml): min 54, median 186, max 1798. Rubric criteria: min 8, median 21, max 51. UNVERIFIED estimate (FLAG Q90).
5. Categories: Data Processing 40, Software Engineering 13, Debugging 10, Optimization 8, Scientific Computing 7, others small.
6. Of the 10 tasks carded on 2 Nov, 8 are under the gate (05550e00, 18b5d99f, 1d61e794, 5048c412, 59417607, 80202e15, a710b00e, aa314fee); 37a0c3d6 and fabbe645 are not.

PHASE 1 PROPOSED PICK (Q91)
26 new cards: the 34 under gate minus the 8 already carded. Plus 5 contrast tasks with the highest Opus final: 65ba10c2 (78.52), 1950015d (73.82), c9d7b490 (71.83), f357cd96 (70.65), 92dd0b24 (70.34). Total 31 new cards, about 2 to 3 million tokens, 4 batches of about 8.

PLAN v2 (3 Nov 09:02, after ENTRY 21; replaces Phases 1 to 4 above)
Scope: all 109 teammate tasks (114 minus Ayush's own 5). Goal: find levers and methods common across tasks (including easy ones), find new things, and confirm or refute our own findings (lever bank, the 182 rules in tmp/W1-002, R0 lever kinds).
Rule for every step: one fixed card template so cards can be compared; every claim cites file and line or a reward-details check name; self check; master spot check.

Layer A. Feature matrix by script, all 109 tasks, no AI tokens.
  From reward-details.json: lost points per check, grouped by check name, and how many checks lost per hidden corpus.
  From instruction.md: presence and wording of key sentences (exact match bar, runtime sentence, "unseen" or "hidden" data, standards named), word count, number of output files.
  From environment/: file formats and counts, number of docs, data size; from tests/: hidden data size and number of hidden corpora.
  From judge.toml: criteria by evaluation target (trajectory or output), negatives, honesty criterion.
  Output: tmp/S2-FEATURES/FEATURES.csv.
Layer B. Correlation by script: which features go with low Opus tests scores; which are common to almost all tasks (the "keys").
Layer C. Pilot: 3 light cards (one low, one middle, one high scorer) to fix the card template and measure tokens. Ayush reviews the pilot cards before scaling.
Layer D. Light cards for all 109 tasks (instruction, reward-details, test file headers, judge criteria; no trajectory.json), about 20k to 30k tokens each, 3 helpers at a time in batches of 8.
Layer E. Deep cards for about 20 to 30 tasks chosen from Layers B and D (lowest, contrasts, and any with a new lever kind): adds the agent program and the trajectory steps where it lost points.
Layer F. Synthesis: PATTERNS.md (lever families, frequency, points cost, wordings that pass QC, what not to copy), and CONFIRM.md (each of our own rules and lever kinds: confirmed, refuted, or not seen in teammate tasks).
Layer G. QC risk view: for CL checks especially (Ayush: CL findings count as major), how passing teammate tasks meet each CL check, including the exemptions the kit itself allows.
Optional: scan Ayush's own 5 tasks the same way if a comparison is needed.
Cost: A and B almost none; C about 100k; D about 2 to 3 million; E about 2 million; F and G about 500k.
