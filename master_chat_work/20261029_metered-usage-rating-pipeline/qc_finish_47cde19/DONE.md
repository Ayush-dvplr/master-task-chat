# DONE: P11 v3 full QC finish, metered-usage-rating-pipeline (board ac12c0b, session 47cde19)

Finished 29 Oct 2026 04:05 IST. Nothing was re-run. The Step 10 numbers were read from the kept jobs folder `master_chat_work/20261028_metered-usage-rating-pipeline/qc_v1_step10_ac12c0b/jobs/`.

- Verdict: ❌ FAIL (5 fails, 2 minors, 3 warns). QL rows: 19 PASS / 3 FAIL.
- Step 10 (tests-only, oracle x3 per Ayush; the kit asks x5):
  - oracle 1.000 / 1.000 / 1.000
  - nop 0.000
  - stub 0.000 (0/407 = 0.0% of P)
  - owner-only 1.000
- Exe_copy outputs, the three diffs and the stub solve.sh: not kept (session aborted 28 Oct 18:55).
- Files written:
  - Report: `QC/reports/metered-usage-rating-pipeline/v1.md`. The consolidated report is above the marker (verdict, gate table, findings, sign-off) and Step 10 is appended at the end.
  - `QC/reports/metered-usage-rating-pipeline/result_ac12c0b.json` (it parses).
  - `QC/reports/metered-usage-rating-pipeline/_progress.md`: Step 10 and final report ticked; compare marked n/a: first round.

## Fix directions (P12 v4 format, one line per FAIL and MINOR)

Each direction restates the property the rule wants; none pastes the report's Fix text. Lever names are from `master_chat_work/bundles/_work/metered-usage-rating-pipeline/LEVERS.md`.

G01-1 (+G03-1) | FIX | environment/data/rating_contract.md:74: north `units` "(a JSON integer)" is read two ways and test_output.py:129-131 accepts only `type(value) is int` -> say that the value must be written as an integer literal (no fraction, exponent, quotes, bool or null) so that the contract has one reading, and keep the decoys at test_output.py:380 unchanged; side-effect rules IN-16, TS-19, DS-25, CL-10 | levers: LV-MU-1 easier (graded noise only, LEVERS.md:181-183, so not one of the three levers); LV-MU-5..9 none
G02-1 | FIX | solution/TRUTH.md:192-194: two false data claims ("No plan change precedes a later usage line of its account."; "at most three accounts long") -> TRUTH must match the data (plan changes do apply mid-month; chains reach four accounts); regenerate TRUTH by script last (G6); side-effect rules DS-22, DS-27 | levers: none (documentation only)
G03-3 | FIX | tests/test_output.py:1176-1194 `_run`: agent subprocess is not run in its own process group, so a setsid grandchild outlives the check and forges long/ladder finishes (21 points) -> every process the agent program starts must be dead before the check returns (own session plus group kill on every exit path); side-effect rules TS-24, TS-30/H6, CL-2 (forgery price must be re-measured and drop from 6.1%) | levers: LV-MU-8 harder, LV-MU-9 harder (closes the forge path); others none
G05-1 | FIX | tests/test_output.py:1363-1369 `_check_missing_collector`: the contract's "name the first missing file in list order" (rating_contract.md:55-57) is never exercised -> a test must remove two inputs from different positions in the list and require the earlier one to be named, plus a reference-file-only case; add the asserts as new checks or new runs inside this check, never moved into another check (G2), and re-derive reward.toml weights; side-effect rules AL-27, AL-2, TS-23 (check count), TS-26 | levers: none (refusal path is not a lever)
G11-1 | FIX | tests/judge.toml (beside R10 :129-139 / R11 :142-152): instruction.md:30 "say which checks you ran ... and what they showed" has no positive grader -> add one binary final_answer criterion that the reply names a check run on the last transform.py and what it showed, which is not a conduct/route criterion (G2), and re-derive the judge weight in tests/reward.toml from the new positive total; side-effect rules JD-10, JD-5, Step 11 overlap | levers: none
G02-2 | FIX | solution/TRUTH.md:186: task.toml digest is stale (9d53e59c...ec4) -> the digest must equal the current task.toml sha256 (bd6b83a7b1c7450f6fae9576a345488ab20ed5f5374afbf1df2f9003ec3841a2 at ac12c0b), recomputed after any task.toml edit in this round; side-effect rules DS-22, DS-27 | levers: none
G04-1 | FIX | tests/judge.toml:79 R6: one criterion grades three things (handlers, functions of 150 lines or fewer, unreachable/unused code) -> each property must be its own binary criterion, and the judge weight in tests/reward.toml must be re-derived from the new positive total; side-effect rules JD-5, JD-10, Step 11 overlap | levers: none
