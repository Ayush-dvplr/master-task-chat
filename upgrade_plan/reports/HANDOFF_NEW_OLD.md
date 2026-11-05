HANDOFF TABLE: NEW OR OLD SESSION (ENTRY 113, asked 5 Nov 2026 08:30 IST; WAITING for Ayush)

Ayush wants the board sha cell of every handoff table to say "<sha> . new" (paste into a new session) or "<sha> . old" (paste into a session that is already open).

What exists today (ROOT board.json, checked 08:30): no field says new or old. The master writes it only in the step text, for example 39a3f9a "cohort design r5b: judge acts + extras (same session as a9e68ee)", and in notes ("same session ses_e57965ecaffeEwip6dut9pBya2"). issue.py prints only board sha, step and link.

QUESTION 1: for "old", should the cell also say which old session?
1. (Recommended) Yes: "39a3f9a . old (a9e68ee)", the board sha of the earlier session to paste into. Cost: a slightly wider cell; without it, with several windows open, Ayush must guess which one.
2. No: only "39a3f9a . old" exactly as asked. Cost: Ayush finds the window himself.

QUESTION 2: who decides new or old?
1. (Recommended) The master, when it issues: issue.py gets an option to name the earlier sha (continue in that session); without it the row is new. Stored in the board row, so every table, BOARD.md and the state card show the same thing. Cost: none for Ayush.
2. Ayush says it each time. Cost: one more question per issue.

QUESTION 3: where is it shown?
1. (Recommended) Everywhere a sha appears for a session to start: the issue.py handoff, the master's handoff tables (rule HANDOFF R6), BOARD.md and the state card. Cost: a few more characters on the card.
2. Only in the master's handoff tables.
