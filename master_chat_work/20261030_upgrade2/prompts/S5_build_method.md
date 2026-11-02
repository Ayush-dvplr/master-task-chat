# S5: Build method and generator review
OUT: `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261030_upgrade2/S5_build_method/`

Goal (Ayush U9, U10): our new-task builds take long, many parked, and gates were often met only with per-task exceptions (crash/timeout share 60-100%). Find a rigid, repeatable build method that can reach final < 35 when needed, and judge whether the generator helps or hurts.

Answer with evidence:
1. History: from registry/tasks.json, board.json and decisions.jsonl list every new build since 20 Oct: idea, lever family, days and sessions spent, rounds of harden/QC, outcome (pushed score / parked / killed) and the reason. Output `BUILDS.csv`. What separates the pushed ones from the parked ones?
2. Generator: read `TB/beta-task-generator/` (README, handbook, AGENTS.md, core/, prompts/) and any master notes that say the generator makes tasks easy (search decisions.jsonl, lessons.jsonl, knowledge/ for "generator"). What does it produce, which of its defaults make tasks easy (point to file:line), and which parts are worth keeping.
3. Exceptions: list every per-task exception granted (crash/timeout share, regrade, gate) with the reason; is there a pattern that should become a rule, or a design rule that would avoid needing it?
4. Untested levers: from LEVER_RULES_v3.md 1D (PROMISING / untested), ANGLES.md untried angles and S4's weight table if present in `../S4_task_study/` (read it only if it exists), pick the 5 most promising with a cheap pilot design for each (what to build, how to measure with blinds before any paid run, expected final band).
5. A step-by-step build recipe draft (`DRAFT_BUILD_RECIPE.md`): idea selection, kill test before build, measurable gates per phase, when to stop (NO CORE), time budget per phase from measured medians (master_chat_work/20261030_speed_measure/MEASURE.md), and where token use can drop without hurting quality (which phases repeat reading).
