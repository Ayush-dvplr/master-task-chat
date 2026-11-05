OLD SYSTEM WORK AFTER THE INSTALL, AND THE ROUND TO MC2-V2.5.4 (ENTRY 116, asked 5 Nov 2026 about 09:10 IST; WAITING for Ayush)

mc2-v2.5.4 is tagged (dd7e147b, lightweight, on 98c33185). Self tests OK, template_check 0.

WHAT WAS CHECKED (read only, 5 Nov 08:57; carry_over.py dry run, md5 of ROOT board.json, pending.db, tasks.json the same before and after)
1. Old board rows not in ROOT: 3, all multi-tenant-migration-orchestration: 72230b3 done (issued 4 Nov 23:48), 8c44d03 done (5 Nov 00:57), b668c20 partial (01:41, updated 02:32). The slug is in neither registry (other team's task, "help others" work). Pending items S459, S461, S462; S461 and S462 are used in ROOT by other items, so they would come as S461-old and S462-old.
2. Data-product paid run: old pending S460 is "running" since 5 Nov 00:34; ROOT has S460 "waiting" (held). The new master was handed the data-product decisions (ENTRY 113).
3. Lines only in the old folder: 5 decisions.jsonl lines (23:49 simple QC of another team's task; 00:07 and 00:25 Anjali task 18a1a3dc; 00:15 data-product freeze; 01:09 8c44d03 F1 option C) and 1 feedback.jsonl line (00:18). carry_over.py does not carry jsonl lines.
4. Cohort and depot are live in ROOT (39a3f9a, a4ae480), so carry_over refuses them; the old board has nothing newer for them.
5. upgrade.py preflight FAILs "no session running" while any ROOT board row is running or issued (upgrade.py around line 721). So the round cannot start while 39a3f9a and a4ae480 run.

FLAG (R_FLAG): ENTRY 107 (5 Nov about 00:20) says the old master issues nothing new; 8c44d03 (00:57) and b668c20 (01:41) were issued there after it, and S460 shows running in the old system from 00:34.

QUESTION 1: the round and the two running sessions.
1. (Recommended) Let 39a3f9a and a4ae480 finish, say "done: <sha>" in the new master for each, and ask the master to issue nothing new until the round is over; then run the round (sync first, then backup, preflight). Cost: the round waits for them.
2. Run the round now. Not possible: preflight blocks while a session runs (changing that check would need a new release).

QUESTION 2: is the data-product paid run (S460) really running or done in the old system?
1. It was started from the old master at about 00:34: let it finish there, carry S460 over, and the new master takes the result (intake) and the rest of the decisions.
2. It was not started: the old "running" mark is wrong; keep ROOT's "waiting" (held) and do not carry S460.
(No recommendation: only Ayush knows what he started.)

QUESTION 3: the 3 multi-tenant-migration-orchestration sessions (other team's task).
1. (Recommended) Carry them into ROOT with carry_over.py --apply (after a backup, before the round), so the new master sees the work and b668c20 (partial) can continue there. Cost: two pending ids get an -old suffix.
2. Leave them in the old folder; that help work stays out of the new system. Cost: the new master does not know b668c20 is unfinished.

QUESTION 4: the 5 decisions lines and 1 feedback line only in the old folder.
1. (Recommended) Append them once to ROOT's decisions.jsonl and feedback.jsonl, each marked "carried_from": "old system", by one command printed for Ayush (lines checked for duplicates). Cost: none.
2. Leave them. Cost: the new master does not know the Anjali task and 8c44d03 decisions or the data-product freeze line (the freeze is already in the registry).

QUESTION 5: the old master from now on.
1. (Recommended) Close the old master window and use only the new master; any old system session still running finishes there and is carried with carry_over.py. Cost: none.
2. Keep using it for help others work. Cost: every such session needs a carry over before each round.
