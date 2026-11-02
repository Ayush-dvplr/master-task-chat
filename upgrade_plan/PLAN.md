PLAN (DRAFT, NOT APPROVED)

Every section here is a first direction only. None of it is built until: (1) the questions it depends on are ANSWERED and VERIFIED, (2) the rules it relies on are VERIFIED in UNVERIFIED_RULES.md, (3) Ayush approves the section, and (4) Ayush types PROCEED.

P1 COMPACTION (depends on Q5 to Q9, R2 to R5)
Idea A. One generated state card. A script builds STATE_CARD.md (target under 4 KB) from the records: rules in force now (one layer only, no "overrides line X"), today's goal, running sessions, open questions, the handoff format Ayush wants. After compaction the master reads only this card, then reads more on demand.
Idea B. Fold the patches. Rewrite the layered rule files into one current version each; move superseded files to a history folder that is never in the read order.
Idea C. Compaction hook. If opencode allows a custom compaction prompt, make it always keep the state card and the last decisions word for word.
Idea D. Lessons become checks. A lesson that repeats (like F1.3) turns into a tool check (for example issue.py refuses a handoff without a link) instead of another note.

P2 QC FIXES (depends on Q10 to Q13, R8 to R18)
Idea A. Lever regression gate. Each task keeps its kill programs (careful program, blind programs, paid run program) and its lever inputs under WORK. After every fix, a script reruns them on the new tests and fails the fix if lever points lost drop below the bar.
Idea B. Diff guard. A script compares tests/ before and after the fix and fails on any hunk the fix plan did not name.
Idea C. One finding, one change, one check. Each fix is applied and checked on its own before the next one.

P3 DOCKER (depends on Q14 to Q19, R19 to R24, RQ1, RQ3)
Idea A (Ayush direction, Q51): a background script, using no AI tokens, that measures real Docker use and hands out room dynamically instead of static values; the AI can see its state and start or stop it. Draft: one slot manager instead of each worker polling: lock files per slot, sized from real RAM and real container use, so a worker blocks on a lock instead of looping.
Idea B. One Docker rule, written in one place, replacing C1 and C6.
Idea C. Measure the Mac once (how many kill tests, oracle runs and paid runs fit together without a hang) and set the limits from that measurement.

P4 HARDENING (depends on Q20 to Q22, R25 to R30)
To be written after Q20 is answered.

P5 TOKENS (depends on Q23 to Q25, R31, R33)
Idea A. Context packs per step: a fix session gets only the rules for its finding ids, not whole files.
Idea B. Move mechanical work (counts, diffs, polling, result checks) into scripts.
Idea C. Cheaper models for mechanical steps, if Ayush allows (Q25).

P6 TOOLS (depends on Q26 to Q29, R31, R32)
Idea A. One runner layer with one adapter per tool (opencode with Claude, opencode with GPT, codex exec, claude CLI, others). Every session writes the same result.json, so board, intake and auto mode treat them all the same.
Idea B. Per tool prompt notes (like the GPT no subagents rule) added automatically by the adapter, not by hand.

ORDER
To be set after Q3.
