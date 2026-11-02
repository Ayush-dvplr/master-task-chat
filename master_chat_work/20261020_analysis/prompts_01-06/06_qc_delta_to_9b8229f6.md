# Delta: update the QC report to the current QC (GitHub head 9b8229f6)

You are a read-only analyst. An earlier session mapped the Input Bundle QC from a clone whose 7 markdown guides were 2 commits stale. Update that report to the current guides. Do not redo the whole analysis.

## Paths (absolute)
- OLD QC (what the report used, read only): `/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Input_Bundle_QC/` (HEAD 1096b244)
- CURRENT QC (read only, byte-identical to GitHub 9b8229f6): `/Users/mac/Desktop/Terminal Bench/QC assigned/Input_Bundle_QC/`
- REPORT TO UPDATE: `/Users/mac/Desktop/Terminal Bench/_tmp_master_tasks_20261020T2214/reports/qc/` (REPORT.md, qc_checks.json, caps.json, authoring_checklist.md, fingerprint.json)
- LOGS: `/tmp/opencode-logs/qc-delta-<YYYYMMDDTHHMM>/`

The two commits (both Sugam Agrawal, 19 Oct): `f7dbc0b0` "QC: optimize the QC bundle for token usage" and `9b8229f6` "QC: fix H2 phantom check reference and 'some' J11 warn docs". Only these changed: 01_Instruction_QC.md, 02_Data_Solution_QC.md, 03_Tests_QC.md, 04_Judge_QC.md, 05_Alignment_Integrity_QC.md, Final_checklist.md, Starter.md. The 5 scripts are identical; confirm with sha256.

## Hard rules
1. Never modify OLD QC, CURRENT QC or anything in `Terminal_2.0_Harbor_Harness/` or `QC assigned/`. Write only in REPORT TO UPDATE.
2. Git and gh read-only only. Never pull, commit, push, merge, checkout or reset. Allowed repos only: ShreeyankDoliya/Terminal_2.0_Harbor_Harness, ShreeyankDoliya/Anubis_Tasks_Samples, ayushsah-dev/beta-task-generator, ShreeyankDoliya/Finalized_Tasks_RFP.
3. Read each changed file in full in CURRENT, and `diff -u` it against OLD. Match checks on ID plus wording, because IDs get renumbered between versions.
4. Every change cites `file:line` in CURRENT.
5. Nothing here should run longer than about 4 minutes; if something does, run it in the background with a log.

## Do
1. Save `qc/_pre_delta/` copies of the five report files before editing.
2. For every check whose wording, severity, threshold, ID or source changed, update its entry in `qc_checks.json` and `caps.json`. Add new checks and mark removed ones `"removed_in":"9b8229f6"`.
3. Update the affected lines of `REPORT.md` and `authoring_checklist.md`, and add `## Delta to 9b8229f6` at the top of REPORT.md: a table of check ID, old, new and impact on authoring.
4. Re-run the fingerprint on CURRENT and write it to `fingerprint.json` with `"source"` set to the CURRENT path and `"remote_head":"9b8229f6"`.

## Done when
The JSON parses, every diff hunk is accounted for in the delta table (or marked wording-only, no rule change), and nothing outside REPORT TO UPDATE changed. Final reply of at most 6 lines: the number of checks changed, added and removed, and any change that affects authoring.
