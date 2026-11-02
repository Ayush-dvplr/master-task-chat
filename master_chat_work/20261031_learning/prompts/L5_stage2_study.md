# L5: anubis-stage-2: the best genuine tasks, how they pass QC, what we can learn
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261031_learning/L5_stage2_study/`

Ayush: "check the stage-2 folder, find the best (lowest score) genuine tasks, how they pass QC, learn more and more from them." Folder `TB/anubis-stage-2` (read-only; no git pull). S4 already made TASKS.csv / LEVER_WEIGHTS.csv over 102 tasks; the Dinshi GLM audit (`master_chat_work/20261029_glm_audit_dinshi/`) found some invalid runs: reuse both.
1. Genuine filter: tasks whose Opus run is valid (reward files consistent with pass_summary, no infra errors, verifier ran, agent produced outputs). List the 15 lowest valid Opus finals with tests/rubric split. `BEST.csv`.
2. Deep read the top 10: what the agent was asked, where it lost points (test names + judge criteria), which lever caused it (held-out exact, hidden scale, convention, probe band, long replay...), how much of the loss is WRONG vs timeout/crash, and whether the loss is fair (follows from instruction + shipped data) or a defect (unstated rule, broken verifier). One card each in `cards/`.
3. QC fit: for each top-10 task, which of our QC kit checks it would pass or fail (read our kit `Terminal_2.0_Harbor_Harness/Input_Bundle_QC/`; any QC notes in the task folder), and how it stays clean on IN-17 (no pre-announcing), AL-1, AL-27, IN-8, CL-4 while still being hard.
4. Patterns: what the best tasks share (size of hidden inputs, number of checks, judge share, kinds of traps, domains) vs our pushed tasks (registry pushed rows). What we can copy tomorrow; what we must not copy (defects).
Extra: BEST.csv, cards/<uuid>.md, PATTERNS.md.
