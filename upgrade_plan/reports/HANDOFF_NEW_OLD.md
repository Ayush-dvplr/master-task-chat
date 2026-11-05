HANDOFF TABLE: NEW OR OLD SESSION (ENTRY 113, 114; asked again 5 Nov 2026 about 08:40 IST; WAITING for Ayush)

Ayush wants the board sha cell of every handoff table to say "<sha> . new" (paste into a new session) or "<sha> . old" (paste into a session that is already open).

What exists today (ROOT, checked 08:30 and 08:40):
1. No board field says new or old; the master writes it only in step text ("same session as a9e68ee") and notes.
2. An old-session prompt gets its own board id (39a3f9a) and still says "First thing: rename this session to 39a3f9a" (prompts/issued/cohort-retention-reconciliation/20261105T0808_rebuild.md line 4).
3. That rename never works there: tools/name_session.py renames only a session whose first message holds the board id, so it prints NOT RENAMED. The opencode window keeps its first name: ses_e57965ecaffeEwip6dut9pBya2 is titled a9e68ee while it runs 39a3f9a.
So the window Ayush looks for is named by the first board id, not by the sha in the table.

QUESTION 1 (asked again): what does the cell show for an old session?
1. (Recommended) "39a3f9a . old (a9e68ee)": the new board id, then the name of the window to paste into. Cost: a wider cell; without the window name the table shows 39a3f9a while the window is called a9e68ee.
2. "39a3f9a . old" only (ENTRY 114 first reading). Cost: Ayush finds the window himself.
3. "a9e68ee . old": the window name only, no new board id. Cost: the table no longer shows the board row that "done: <sha>" closes.

QUESTION 1b: the rename line in an old-session prompt.
1. (Recommended) Leave it out: the master writes no rename line in an old-session prompt (issue.py checks it), so the window keeps its first name. Cost: none; today it fails anyway.
2. Make it work: name_session.py renames the open window to the new id. Cost: the window name changes every round.

QUESTION 2: who decides new or old?
1. (Recommended) The master, when it issues: issue.py gets an option to name the earlier sha; without it the row is new. Stored in the board row, so every table, BOARD.md and the state card agree.
2. Ayush says it each time.

QUESTION 3: where is it shown?
1. (Recommended) Everywhere a session sha appears to start a session: the issue.py handoff, the master's handoff tables (HANDOFF R6), BOARD.md and the state card.
2. Only in the master's handoff tables.
