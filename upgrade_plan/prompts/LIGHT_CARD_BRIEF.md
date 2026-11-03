LIGHT CARD BRIEF (Layer D, approved Q100, 3 Nov 2026). The master fills <HELPER>, <BATCH> and starts one helper per batch.

You are helper <HELPER>. Repo /home/user/master-task-chat. Read task files from origin/main only, with: git show "origin/main:<path>" and git ls-tree -r --name-only origin/main <dir>. Never check out or merge. Your ONLY write is upgrade_plan/tmp/S2-CARDS/<task id 8 chars>.md, one file per task. No commit, no push, no subagents. Keep any scratch files in a folder named after your helper id (other helpers share the scratchpad).

Your tasks: the lines starting with <BATCH> in upgrade_plan/tmp/S2-CARDS/QUEUE.txt (4 teammate tasks under anubis-stage-2/, with their Opus 5 scores).

PURPOSE: learn task design from these accepted teammate tasks: what the tests check, why Opus lost points, and whether each loss comes from a DESIGN choice (real difficulty in a solvable task) or a DEFECT (the reference contradicts the docs, the environment or grader breaks the agent's program, or the contract leaves a graded value undecided). Defects are recorded and flagged; they are not counted as design levers until Ayush and the master review them (nothing is voided automatically).

BUDGET: about 40k tokens per task. Do NOT rerun code, decode digests, or regenerate data. Do NOT read trajectory.json or the PDFs. Read, in this order, only as much as needed: instruction.md; tests/judge.toml (criteria names and targets); trajectories/claude-opus-5/run_1/verifier/reward-details.json (lost checks and the judge reasoning); headers and check functions of tests/test_output.py (skip embedded data); solution/TRUTH.md (head); the environment docs that the lost checks depend on; the matching part of the agent's program under trajectories/claude-opus-5/run_1/artifacts/ only to locate a divergence.

CARD FORMAT (at most about 3 KB; plain text; CAPITAL titles; numbered lists; no bold, italics, # headings or dash bullets; contractions written out):
TASK: id, category, Opus tests, rubric, final.
1. VERDICT: DESIGN, DEFECT, or MIXED, with the share of lost test weight for each, and confidence (high, medium, low).
2. LOSSES: groups of lost test checks with their weights, and the cause of each (WRONG output, TIMEOUT, CRASH, missing file).
3. DIFFICULTY KIND for each DESIGN loss: (a) format or encoding variation inside a documented standard, (b) documented case the visible data never triggers but the test data does, (c) scale or runtime, (d) misread rule, (e) other (describe).
4. EVIDENCE: for each DESIGN loss, the shipped line (file:line) that decides the right behaviour; for each DEFECT, what contradicts what (file:line).
5. TEST DESIGN: how test data is made (fixed, seeded generator, several corpora), comparison style (whole document, per field, digest), amplification, negatives.
6. INSTRUCTION: key sentences quoted (exact match bar, runtime, deliverable, honesty) and what is NOT said.
7. RUBRIC: what lost criteria targeted, and why lost.
8. REUSABLE IDEA: the approach in general terms, no domain or data copied. Write "none" for a pure DEFECT.

FINAL MESSAGE under 15 lines: one line per task (id, verdict, main difficulty kind or defect), and anything you could not decide.
