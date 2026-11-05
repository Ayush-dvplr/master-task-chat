MC2-V2.5.4 BEFORE THE TAG (5 Nov 2026 about 09:05 IST; WAITING for Ayush)

Built in the worktree as commit 98c33185 on 9718df83 (untagged). Self tests all OK (test_e3_e6_tools 3 skipped, test_issue_lint 3 skipped, test_upgrade_tools 23 skipped; skips need the old system folders), template_check 0 problems. The 6 master edited knowledge and template files are byte for byte the ROOT copies; CHANGELOG is the ROOT copy plus one line; RULES_IN_FORCE is the ROOT copy plus the new lines below.

Contents: (1) the 8 ROOT master edits; (2) README parts E and B in text code blocks (9718df83); (3) .omo/ ignored at any level; (4) RULES_IN_FORCE SYSTEM CHANGES line, ROLE "the prompts it issues", README hard rule and Self improvement line; (5) state card SYSTEM FILES line when git status in ROOT is not clean; (6) MASTER_GAPS: task sessions start in ROOT (HANDOFF line), COMPRESSION line (part E, /dcp-compress, part B), old system kept or acknowledged findings go to Ayush's triage (QC PASS line); the kit evidence gap is gone (snapshot qc_48726eb7 has a text copy); (7) issue.py --same-session, board session and window fields, cell "<sha> . new" or "<sha> . old (<window>)" in the issue.py handoff, BOARD.md and the card, no rename line in an old session draft.

QUESTION 1: the state card goes over its 8 KB hard limit. Measured on a copy of ROOT's records with the new tools: 7.5 KB written, but "open items" and "uniqueness" were LEFT OUT to stay under 8 KB (ROOT's card was already 7957 bytes before this release; the master's ORDER line and the new rule lines add about 1 KB).
1. (Recommended) Raise card.hard_kb in settings.json from 8 to 9 in this release (one setting, DR2). Cost: about 1 KB more for the master to read after each compression.
2. Keep 8 KB and accept that open items and the uniqueness reminder drop off the card (the master reads them with pending.py list). Cost: the uniqueness reminder is missed before a new build.
3. Shorten the rule lines (mine and the master's ORDER line) to fit 8 KB. Cost: Ayush rereads the reworded rules; the ORDER text he approved changes wording.

QUESTION 2: the two sessions running now were issued before the new fields, so their cell shows the sha only.
1. (Recommended) After the round, the master sets them once: board.py set 39a3f9a session=old window=a9e68ee same_as=a9e68ee, and board.py set a4ae480 session=new window=a4ae480. Cost: none.
2. Leave them; only new prompts get the cell.

QUESTION 3: anything more for mc2-v2.5.4 before the tag (LESSONS entry 2)?
