P1 COMPACTION DRAFTS (3 Nov 2026). Nothing here is applied before Ayush types PROCEED.

WHY (FINDINGS F1.8 to F1.10): DCP runs on defaults: it pushes the model to compress from 100k tokens (about 10 percent of the 1 million window), the model compresses its own history to about 5 percent, and nothing is protected, not even Ayush's messages.

DECIDED: master chat = option B (manual, Q98); task sessions = option C (DCP off, Q99).

HOW THE FILES REACH THE RIGHT SESSION (from DCP 3.2.0 config.ts, RQ9)
DCP reads, in order, later wins: the global ~/.config/opencode/dcp.jsonc, then $OPENCODE_CONFIG_DIR/dcp.jsonc, then the NEAREST .opencode/dcp.jsonc found walking up from the session's working folder.
So the nearest folder decides:
1. <root>/.opencode/dcp.jsonc = tasks.dcp.jsonc (off). Every task session started from the root gets it.
2. <root>/master_chat_tasks/.opencode/dcp.jsonc = master.dcp.jsonc (manual). The master must then be STARTED from master_chat_tasks/ (Q108), so this file is the nearest one.
3. The global ~/.config/opencode/dcp.jsonc stays empty (defaults), used only by sessions outside the root.
Caution: OPENCODE_CONFIG_DIR is read BEFORE the project file, so it cannot override a project file; the folder approach is the reliable one.

WHAT MANUAL MODE MEANS IN PRACTICE
1. The model never compresses on its own; Ayush runs a DCP command when he wants a compression (the /dcp commands; the exact command list is shown by /dcp in opencode).
2. Automatic duplicate removal and old error purge keep running (they remove repeats and failed tool outputs only).
3. When a compression does happen: Ayush's messages keep their first text part word for word (protectUserMessages), text inside <protect>...</protect> in his messages is kept (protectTags), and tool results of the protected files are not compressed.
4. The window is 1 million tokens; the master should still be restarted from the state card well before it fills.

CHECK AFTER APPLYING (one day)
1. Open the master: the DCP notice should show manual mode. Start a task session at the root: no DCP notices.
2. Count compressions in the master per day (target: only the ones Ayush starts).
3. Run one cold recovery test of the master (like W1-001 here).

CHECK OF PATHS (Claude, 3 Nov, for Q108: master started from master_chat_tasks/)
1. Tools: 11 of 16 tools and auto.py find their files from their own location (__file__), so the start folder does not matter for them. The other 5 (dockfree.py, name_session.py, stacking_check.py, trajectory_readout.py, xref_check.py) open no fixed relative paths.
2. README read order already uses paths relative to master_chat_tasks/ (tools/status.py, tools/pending.py), so those get simpler.
3. One line breaks: README line 14 "git -C Terminal_2.0_Harbor_Harness rev-parse HEAD" is relative to the root. Change after PROCEED: "git -C ../Terminal_2.0_Harbor_Harness rev-parse HEAD".
4. auto.py starts worker sessions with cwd = the project root (auto.py line 765), so workers get the root file (DCP off), as decided.
5. Issued prompts use absolute Mac paths, so they are not affected.

STILL TO DRAFT (P1 steps 2 to 5 in PLAN.md)
1. STATE_CARD.md generator for the master (spec next).
2. Recovery prompt for the master.
3. Folding the layered rule files into one current version each.
