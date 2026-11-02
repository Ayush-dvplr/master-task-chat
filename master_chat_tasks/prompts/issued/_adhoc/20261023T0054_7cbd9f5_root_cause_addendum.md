# Addendum for session 7cbd9f5 (cohort-retention harden r2), 23 Oct 00:54 IST

Paste below into session `7cbd9f5`. It adds to Phase 1; it does not replace it. Save it as the first item in `WORK/TODO.md` so it survives compaction.

=== PASTE BELOW ===

Addendum to Phase 1 (from the master chat). Before the lever table, answer one question: why did the score go from 58.67 (v0) to 100/100/100 (a2)? Put the answer in `OUT/DIAGNOSIS.md` section 0, "Root cause". Give each of these 4 causes a verdict (YES / NO / PARTLY) with quoted evidence (file:line, trajectory step id, or command output):

1. **Run error or wrong copy.** Was the a2 run a clean run of OUR bundle? Locate the copy the harness ran (its Tasks_INPUT copy, and the `.master-queue/task-archive/` entry from 20261023T003231, under `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/`). Compare its tree sha (sha256 over sorted paths + contents) with BUNDLE now and with the sha in `result_0b8ac36.json` (8667ff1e386d). Check `result.json`, `job.log` and the verifier logs for errors, retries, skipped checks, or a judge that scored without reading the response. Read only; never edit harness files.
2. **Harness or rescoring change.** Is a2 scored the same way as v0? v0 lost all program-run points to the permission trap and had no judge; a2 had both channels. Recompute what v0 would have scored without the trap (the LEVERS.md probe said 12/12 program-run checks passed). If v0 would already have been ~100 without the trap, the task was never hard. Say so plainly.
3. **Our QC/fix rounds made it easier.** Diff the harden r1 tree (HARDEN_REPORT / baselines.json) against the P12 r1 tree (8667ff1e386d) and the current BUNDLE. For each change, say whether it exposed answers: TRUTH/judge figures in the instruction, the R4 "14 reason entries", the serialization check, the solve.py rewrite, or rule text moved next to its use.
4. **The levers were weak by design.** For each CR-1..CR-5 and V0-1..V0-8, give the trajectory step where the agent got it right on its first try and say what gave it away.

End section 0 with one line, `PRIMARY CAUSE: <1|2|3|4>` plus up to 2 contributing causes. Then continue Phase 1 as written, and stop at "DIAGNOSIS READY".
