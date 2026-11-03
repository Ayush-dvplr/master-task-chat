(a) Goal: many accepted tasks made the way teammates make them, meaning QC passed, under the gate, solvable from what ships, and new (not a copy); conflicts decided case by case with Ayush (card line 5).

(b) Score gate: tests under 85, rubric under 85, final under 40, on 1 run of frozen QC passed bytes, never rerunning the same bytes after a miss. It comes from settings.json (card line 22) under rules R26 and R27 (card line 13).

(c) Count caps: R15 says no caps, Ayush decides each time; the counts are QC minimum, soft 70, hard 100 (Ayush's rule) (card lines 12 and 22).

(d) Handoff format: a table with board sha, step, status and a clickable file link, never "read and follow"; a session stays issued until Ayush says running (card lines 9 and 59).

(e) LONG session: report it to Ayush, never stop it while it is working (card line 6, ENTRY 47, and lines 39 to 41).

(f) In order: 1. Read tmp/W1-028/STATE_CARD.md, because the prompt and R2 say the card comes first. 2. python3 tools/pending.py list, to check the waiting questions and their order (the prompt asks oldest first) and to look for Q116 named by OPEN R28. 3. python3 tools/status.py depot-charge-plan, because the next step depends on the depot hold awaiting Ayush and the card line was truncated. I did not run board.py, because no next step needed a single board entry before Ayush answers.

(g) Unclear, missing or contradicting:
1. STATE_CARD.md lines 33 to 36: the header says older than 12 h first, but the order is Q52 264 h, Q47 276 h, Q48 268 h, Q62 96 h, which is not oldest first (it looks sorted by priority). I reordered in the answer.
2. STATE_CARD.md line 19: OPEN R28 (Q116), but Q116 appears nowhere in the card or in pending.py list.
3. STATE_CARD.md lines 26 and 27: "pushed today 0 of 4" against "counting slipway (pushed 2 Nov 11:42)"; the TODAY text looks like the 2 Nov goal (line 51, S429 "Today's goal 2 Nov"), so it may be stale for 3 Nov.
4. STATE_CARD.md line 38 says 3 sessions running or issued, but pending.py list shows about 30 steps S400 to S434 in state waiting with board shas from 1 and 2 Nov, plus S412 and S427 open; unclear whether those are still live or just unclosed records.
5. STATE_CARD.md line 27 says hangar goes only after the v3.8 upgrade on Ayush's word, while line 41 and 47 show hangar dabfeb4 running with Ayush acceptance at 23:28; the card does not say whether the v3.8 upgrade happened.
6. STATE_CARD.md line 12: "CAPS none" next to numeric soft 70 and hard 100 counts reads as a contradiction, and it does not say what is being counted.
7. pending.py list shows waiting questions not on the card's Ayush list (for example Q33 high, which names an Ayush action "Ayush tells PL to skip it"); unclear whether these wait on Ayush or on the PL.
8. STATE_CARD.md line 54: Q20-22 trial review was due 23 to 24 Oct and is overdue.
9. STATE_CARD.md line 24: the live QC kit is not reachable (snapshot 25 Oct), while R33 (line 18) says prompts read live QC files.

(h) No. Generated 3 Nov 12:30 and now is 3 Nov 12:30, so the age is 0 and it is fresh. Had it been older than 1 hour, I would not stop: since I may not run state_card.py, I would say so in the answer, state the card's age, verify the live items with the three allowed read only tools, and ask Ayush to regenerate it.

(i) No. I read it as the block holding the rules in force (the only rule text to follow) and followed it; it did not change what I reported. The one small doubt is whether the tag is meant for me or only for the compaction step.
