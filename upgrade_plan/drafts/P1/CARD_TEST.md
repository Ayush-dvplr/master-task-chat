CARD TEST, state_card.py v2 (3 Nov 2026 12:20 IST)

Run on copies of the master_chat_tasks records in the scratchpad (board.json, registry/tasks.json, pending.db, GOALS.md, knowledge/fingerprints/qc.json), with drafts/P1/RULES_IN_FORCE.md. Nothing in master_chat_tasks was written.

What v2 adds (R2 improvements 1 to 13, fixes a and b, Q118 option 3)
1. Fill order: rules, settings, QC kit, progress and today's goal, news since last card, waiting for Ayush, sessions, active tasks, other open items, uniqueness, handoff format.
2. Hard limit 8 KB: sections are dropped from the bottom of the fill order and a LEFT OUT line names them. Target 6 KB gives a note only.
3. Trims: other open items top 5 of n; task next text 60 characters; step 50; sessions over 6 shown as "+n more".
4. Settings line from settings.json (gate, caps, card sizes, long running hours, question age). The file does not exist yet; the card says MISSING and uses the defaults (85, 85, 40; soft 70, hard 100).
5. QC kit line: hashes of the live kit compared with knowledge/fingerprints/qc.json; on a change it names the files and says an agent classifies (S7), Ayush decides.
6. Progress line: pushed today and this week against a target in settings.json (draft values 4 a day, 20 a week; Ayush to confirm).
7. News since last card: session status changes and task stage changes since the previous card (snapshot STATE_CARD.prev.json, owned by the script). First run: sessions done in the last 48 h.
8. Waiting for Ayush: every open question, always shown, older than 12 h first, with its age.
9. Long running sessions flagged "LONG n h, chase" over 3 h (setting).
10. Uniqueness line: archetype and category of the last 3 builds.
11. Every section header names its source file.

Sizes
1. First run (8 news lines): 7.1 KB.
2. Normal day, no news (3 sessions, 5 tasks): 6.3 KB. Saved as sample_STATE_CARD.md.
3. Busy day (6 sessions, 8 tasks), first run: 7.9 KB, nothing left out.
4. Maximum (12 sessions, 12 tasks), first run: would pass 8 KB; uniqueness and other open items left out and named, 7.5 KB.

Gaps found
1. A normal day is 6.3 KB, a little over the 6 KB target. The rules (3.0 KB) are half of the card.
2. The uniqueness line can only show archetype and category: registry/tasks.json has no field for the design family (PATTERNS.md D1 to D9) or the primary lever kind. Needs a new field after PROCEED.
3. The progress target per day and per week is a draft value.
4. The three sessions issued last night show "LONG 12 h": correct for the copy of the records, which is from 2 Nov.

Decisions (ENTRY 46, Q119)
1. 6.3 KB on a normal day accepted.
2. New registry field, after PROCEED: "design": {"family": "D1 to D9 from PATTERNS.md", "primary_lever_kind": "short name"}, filled by intake for every new build. The card shows it when present and falls back to archetype and category.
3. Targets 4 a day, 20 a week; long running after 3 hours. Both in drafts/P1/settings.json.
