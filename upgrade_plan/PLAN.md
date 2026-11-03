PLAN (DRAFT, NOT APPROVED)

Every section here is a first direction only. None of it is built until: (1) the questions it depends on are ANSWERED and VERIFIED, (2) the rules it relies on are VERIFIED in UNVERIFIED_RULES.md, (3) Ayush approves the section, and (4) Ayush types PROCEED.

P1 COMPACTION (draft v2, 3 Nov; depends on Q97, Q98, RQ9; nothing applied before PROCEED)
Cause found: DCP runs on defaults (F1.8, F1.9): it starts pushing compression at 100k tokens, the model compresses its own history into about 5% summaries, and nothing is protected, not even Ayush's messages.
Step 1. DCP settings (one small dcp.jsonc, applied by Ayush on the Mac). Choose one of:
  Option A, tune: protectUserMessages true; protectTags true; protectedFilePatterns for the rule and state files; turnProtection on; higher per model limits for the master model; nudgeForce soft.
  Option B, manual: manualMode on (the master compresses only when Ayush says so), automatic dedup and error purge kept.
  Option C, off for the master: DCP disabled in the master session, native compaction with compaction-rules.js used when needed.
  Decided (Q98): B for the master chat; A or C for task sessions (one job per session, 1 million token window, board shows about 1.3 prompts per session).
  How (F1.10): DCP reads the nearest .opencode/dcp.jsonc above the working folder, and $OPENCODE_CONFIG_DIR. Draft: the master is started with OPENCODE_CONFIG_DIR pointing at a master settings folder (manualMode on, protectUserMessages true, protectTags true, protectedFilePatterns for the state card and rule files); task sessions use the root .opencode/dcp.jsonc (Option A light: limits as a percent of the window, protectUserMessages true) or "enabled": false (Option C). Task sessions: C, DCP off (Q99). Context meter is a percent of 1 million tokens, so the default 100k push starts at about 10 percent (Q97).
Step 2. A generated STATE card for the master (like RESUME.md here, which passed two cold tests): goal, rules in force (one layer), running sessions, open items, handoff format. A script rebuilds it after every records write.
Step 3. Protected rules: Ayush's standing rules wrapped in <protect> in the card, so even a compression keeps them word for word (needs protectTags true).
Step 4. One recovery prompt for the master after any compaction, cold tested like ours.
Step 5. Fold the layered rule files into one current version each (old Ideas B and D): superseded text moves to history; a repeating lesson becomes a tool check.
Check after the change: count DCP compressions per day and run one cold recovery test of the master.

P2 QC FIXES (depends on Q10 to Q13, R8 to R18)
Idea A. Lever regression gate. Each task keeps its kill programs (careful program, blind programs, paid run program) and its lever inputs under WORK. After every fix, a script reruns them on the new tests and fails the fix if lever points lost drop below the bar.
Idea B. Diff guard. A script compares tests/ before and after the fix and fails on any hunk the fix plan did not name.
Idea C. One finding, one change, one check. Each fix is applied and checked on its own before the next one.

P3 DOCKER (depends on Q14 to Q19, R19 to R24, RQ1, RQ3)
Idea A (Ayush direction, Q51): a background script, using no AI tokens, that measures real Docker use and hands out room dynamically instead of static values; the AI can see its state and start or stop it. Draft: one slot manager instead of each worker polling: lock files per slot, sized from real RAM and real container use, so a worker blocks on a lock instead of looping.
Idea B. One Docker rule, written in one place, replacing C1 and C6.
Idea C. Measure the Mac once (how many kill tests, oracle runs and paid runs fit together without a hang) and set the limits from that measurement.

P4 HARDENING (depends on Q20 to Q22, Q61, R25 to R30)
Problem as Ayush states it (Q20): there is no clear method. Hardening has to keep levers hidden (no leak of tests or rubric), pass QC, keep what makes the task hard, keep oracle 1 and nop 0, and follow many other constraints at the same time.
Step 1 (proposed, Q61): one numbered list of every hardening constraint with its source, verified by Ayush.
Step 2: a hardening method built only from the verified list, with a script check for each constraint that a script can check (oracle and nop, leak grep, lever regression from P2 Idea A).

P5 TOKENS (depends on Q23 to Q25, R31, R33)
Idea A. Context packs per step: a fix session gets only the rules for its finding ids, not whole files.
Idea B. Move mechanical work (counts, diffs, polling, result checks) into scripts.
Idea C. Cheaper models for mechanical steps, if Ayush allows (Q25).

P6 TOOLS (depends on Q26 to Q29, R31, R32)
Idea A. One runner layer with one adapter per tool (opencode with Claude, opencode with GPT, codex exec, claude CLI, others). Every session writes the same result.json, so board, intake and auto mode treat them all the same.
Idea B. Per tool prompt notes (like the GPT no subagents rule) added automatically by the adapter, not by hand.

CROSS CUTTING (from the goal)
DR2: one settings file for gate values; every template and tool reads it.
DR3: a solvability check on every build (oracle 1.0 is the minimum; plus a check that every graded value is decided by shipped material, pending Q72).
R_QC_UPSTREAM: kit change detector (fingerprint compare) plus an agent classification MINOR or MAJOR by the README 8b definition; MAJOR stops issuing until the mapping is updated.

ORDER
P1 first, then the order Ayush wrote (Q34).
