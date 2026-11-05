COMPLETE RESYNC FROM THE OLD SYSTEM, THEN THE ROUND TO MC2-V2.5.4 (ENTRY 116, 117; checked 5 Nov 2026 11:49 IST read only; WAITING for Ayush)

mc2-v2.5.4 is tagged (dd7e147b). Nothing in ROOT was written by these checks (carry_over.py dry run; md5 of ROOT board.json, pending.db, tasks.json equal before and after).

WHAT THE OLD SYSTEM DID AFTER THE INSTALL COPY (4 Nov about 21:10)
1. Records (master_chat_tasks), all carried by carry_over.py except item d:
   a. multi-tenant-migration-orchestration (Nikhil's task, help others; in neither registry): board 72230b3 done (simple QC), 8c44d03 done (fix F1 F3 F5 F7), b668c20 partial (QC v2 recheck, last 02:32); pending S459, S461, S462 (come as S461-old, S462-old, since ROOT uses those ids).
   b. data-product-config-compiler: the paid run S460 is DONE (5 Nov 09:50): final 84.69 = tests 100 (120/120), rubric 69.39; gate missed. The old master wrote "KILL rule tests>=95; awaiting Ayush kill/park" (under mc2-v2.5.3 that rule is report only, ENTRY 105; the decision is the new master's, ENTRY 113). Old registry: stage gate_runs plus 6 fields, and 1 scores.jsonl line.
   c. Nothing newer for cohort, depot or multicorner (carry_over refuses cohort and depot anyway: they are live in ROOT).
   d. Not carried by the tool: 5 decisions.jsonl lines (23:49 simple QC of Nikhil's task; 00:07 and 00:25 Anjali task 18a1a3dc; 00:15 data-product freeze; 01:09 8c44d03 F1 option C) and 1 feedback.jsonl line (00:18).
2. Task material, which by the INSTALL guide step 7 stays in the old folder and is read there by old paths (never copied, except a bundle before a task's next build or fix step in ROOT):
   a. data-product: bundle "$OLD/master_chat_work/bundles/data-product-config-compiler" (1.8 MB, not in ROOT yet), paid run in "$OLD/Terminal_2.0_Harbor_Harness/jobs/data-product-config-compiler", Output_RFP, .kiro-run folders, QC/reports, _runs/20261104.
   b. Nikhil's multi-tenant task: "$OLD/Tasks for QC for other /multi-tenant-migration-orchestration", QC/reports and QC/copies (72230b3, b668c20), _runs/20261104 and 20261105, "help others/Nikhil bhaiya".
   c. Anjali's task 18a1a3dc: "help others/Anjali", harness Tasks_INPUT, jobs, Output_RFP and .kiro-run folders; no board row (only the 2 decisions lines).
3. Outside the master system: harness_master_tasks/ (the harness run queue records, in the old folder, not in ROOT) and the old harness .master-queue and MASTER_RUN_LEDGER.md; Anubis_Tasks_Samples/Pass@1_New (a samples repo, 614 files).
4. Now live: OLD nothing; ROOT 31c1a08 (cohort) and 0e4f7f9 (depot), both issued. Preflight FAILs while any ROOT row is running or issued.

THE OLD FOLDER IS NEVER DELETED OR MOVED: ROOT's records and QC/old_reports point into it, and past bundles, jobs and reports live only there. "Not using it" means: no old master, no new session started from it.

RESYNC PLAN (commands given only after the answers)
1. python3 "$UP" backup.
2. carry_over.py --slug data-product-config-compiler --slug multi-tenant-migration-orchestration --apply (Question 2).
3. Append the 6 jsonl lines with "carried_from": "old system", skipping any line already in ROOT (Question 3).
4. Copy the data-product bundle into ROOT/master_chat_work/bundles/ (Question 4).
5. Dry run carry_over.py --all-finished again: it must list nothing to carry (only live refusals).
6. Close the old master window (Question 5).
7. Then the round: wait for 31c1a08 and 0e4f7f9 (Question 1), backup, check ROOT diff still sha256 f468065e, git checkout the 8 files, preflight, printed commands, recheck.

QUESTION 1: the round waits for the sessions issued in ROOT (now 31c1a08 and 0e4f7f9).
1. (Recommended) Do the resync now (it is allowed while those run: they are other tasks); then let them finish, say done for each, ask the master to issue nothing new, and run the round. Cost: the round waits.
2. Hold the resync until the round too. Cost: the new master works without the data-product run result meanwhile.

QUESTION 2: carry the records of data-product (paid run result) and Nikhil's multi-tenant task.
1. (Recommended) Carry both with carry_over.py --apply. Cost: two pending ids get an -old suffix.
2. Carry only data-product; Nikhil's help work stays in the old records. Cost: the new master does not know b668c20 is unfinished.

QUESTION 3: the 6 jsonl lines (5 decisions, 1 feedback).
1. (Recommended) Append them once, marked carried, by one printed command that skips duplicates.
2. Leave them in the old folder.

QUESTION 4: the data-product bundle.
1. (Recommended) Copy it into ROOT now (INSTALL guide step 7.3), since its next step after the gate miss (harden or not) is decided and done in ROOT. Cost: 1.8 MB.
2. Copy it later, only if the new master decides to harden.

QUESTION 5: paid runs from now on. The harness run queue (harness_master_tasks/, .master-queue) lives only in the old folder, and ROOT's harness clone has no jobs/ or queue state. Moving the paid run flow is STAGE B work (paid run wrap), which needs PROCEED.
1. (Recommended) Until STAGE B, paid runs keep running in the old harness folder the way the data-product run did (Ayush runs them; the new master records the result with intake). Only the master and its sessions leave the old folder. Cost: the old harness folder is still used for runs.
2. Plan moving the run queue to ROOT now (a STAGE B item, design first). Cost: more work before the next paid run.
