RULE REVIEW (builds RULES_IN_FORCE.md for the master's state card; Q4 and Q110)

Each rule from UNVERIFIED_RULES.md gets Ayush's word: KEEP, CHANGE (new wording), or DROP. Claude adds a note and a suggestion; Ayush decides. Batches of about 10.

BATCH 1 (R1 to R10), asked 3 Nov
R1. The master chat only advises and writes prompts; all heavy work runs in other sessions.
  Note: matches DR1 (token light) and how this upgrade session works. Suggest KEEP.
R2. After any compaction, run the 7 step read order in master_chat_tasks/README.md before anything else.
  Note: the 7 step order loads about 100 KB and still lost rules (F1.1, F1.3). P1 replaces it with STATE_CARD.md plus on demand reading. Suggest CHANGE to: "After any compaction, read STATE_CARD.md first, then only what the next step needs."
R3. Only the master chat writes in master_chat_tasks, and only through the tools.
  Note: keeps records clean; the state card generator becomes one more tool. Suggest KEEP.
R4. Every corrective remark from Ayush goes word for word into feedback.jsonl in the same turn; every master process failure goes to lessons.jsonl.
  Note: the same lesson was logged twice and not followed (F1.3). Suggest CHANGE: add "a lesson that repeats becomes a tool check, not another note".
R5. Store only rules, decisions, state, failures, lessons, scores, levers, ideas; never chat summaries.
  Suggest KEEP.
R6. Handoff to Ayush is a table with board sha, step, status and a clickable file link; never "read and follow".
  Note: already printed in the state card. Suggest KEEP.
R7. A session stays "issued" until Ayush says it is running.
  Suggest KEEP.
R8. G1: never paste the QC "Fix:" text as the fix direction.
  Note: the study 3b00450 found many later findings caused by fixes, mostly from pasted Fix text (F2.1). Suggest KEEP.
R9. G2: never move an assert into an existing check; never move weight onto a conduct or route criterion.
  Note: Claude has no evidence for or against from the cards. Ayush's call.
R10. G3: never delete a clause or grader without naming what grades the rest.
  Note: protects against silent loss of a lever in a fix (P2). Suggest KEEP.
Decisions: (open)
