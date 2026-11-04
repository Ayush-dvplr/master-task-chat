MASTER RECOVERY DRAFT (P1 step 4, 3 Nov 2026 12:45 IST). Nothing here is applied before PROCEED.

WHAT CHANGES
Today the master README read order (master_chat_tasks/README.md lines 5 to 15) has 7 steps and loads about 100 KB: README, GOALS, status, pending, INDEX, KNOWLEDGE, route1 notes R0, decisions, ALL of feedback.jsonl, lessons, pipeline v4 PLAN, MASTER_UPGRADE_PLAN_v1, state.json. After compaction the master loses format and process rules (lessons.jsonl lines 89 and 100), and two layers disagree (README line 31 against R0, see FOLD_PLAN.md).
New: one card, then only what the next step needs.

PART A. NEW READ ORDER (replaces README lines 5 to 15 after PROCEED)
Read order after any compaction or in a new session
1. STATE_CARD.md. It holds the rules in force (the only rule text you follow), settings, QC kit status, progress, news, questions waiting for Ayush, sessions, active tasks, open items, uniqueness. If it says MISSING or LEFT OUT, read the named source.
2. Regenerate it first if it is older than 1 hour: python3 tools/state_card.py.
3. Then read only what the next step needs:
   a. one task: python3 tools/status.py <slug>
   b. one session Ayush names: python3 tools/board.py show <sha>
   c. a design, harden or fix step: BUILD_RULES.md, then knowledge/PATTERNS.md (DESIGN families)
   d. a QC fix: knowledge/QC_FIX_PLAYBOOK.md (current version only)
   e. a decision's history: DECISIONS_ACTIVE.md (generated, R2 point 4; the generator is still to be built after PROCEED), never the whole decisions.jsonl
   f. research: knowledge/INDEX.md first (U5)
4. Never read: files marked history, the whole feedback.jsonl or lessons.jsonl (their rules are in RULES_IN_FORCE.md), old template versions.
5. Before writing any time: TZ=Asia/Kolkata date. Before trusting the QC kit or the generator: the card's QC KIT line.
6. Ask Ayush when the card and a file disagree; do not choose on your own (R_FLAG).

PART B. THE PROMPT AYUSH PASTES AFTER A COMPACTION (or to start a new master session)
Context recovery for the master chat. You are the master (the brain of the task system). Read master_chat_tasks/STATE_CARD.md first (regenerate it with python3 tools/state_card.py if it is older than 1 hour) and follow its RULES IN FORCE. Read nothing else until the next step needs it. Then tell me in 5 short lines: sessions running and anything LONG (report only, never stop), questions waiting for me oldest first, news since the last card, today's progress against the target, and the next step you propose. Do not issue or write anything until I answer.

PART C. PROTECTION (P1 step 3, needs protectTags true in master.dcp.jsonc)
Ayush's standing rules go into RULES_IN_FORCE.md, and the card wraps the RULES IN FORCE section in <protect> ... </protect>, so a manual DCP compression keeps it word for word. Cost: about 20 bytes. To check after PROCEED: protectTags works on tool output (the card is read by a tool), not only on user messages. If it does not, Ayush pastes the rules in a <protect> block once per session. (Open point, see Q121.)

PART D. COLD TEST (after PROCEED, once)
1. A fresh opencode session with only Part B and a copy of the records.
2. Pass when it names: the goal, the gate from settings, the running sessions, the oldest question for Ayush, the handoff format (table with board sha, step, status, clickable link), and that a LONG session is only reported.
3. Fail on: reading a history file, quoting README line 31 lever text, or a gate other than the settings value.

PART E. THE COMPACT PROMPT AYUSH PASTES BEFORE A COMPRESSION (Q155, ENTRY 84)
The master's DCP is manual, so a compression only happens when Ayush starts it. He pastes this first, then runs the DCP compress command, then pastes the restore prompt in part B.
Before I compress this chat: write a checkpoint into the records with the tools (running sessions, open questions to me, the next step you proposed, anything I told you in this chat that is not yet in the records, word for word in feedback.jsonl). Then regenerate STATE_CARD.md and tell me in one line that it is current. Keep nothing important only in this chat.
