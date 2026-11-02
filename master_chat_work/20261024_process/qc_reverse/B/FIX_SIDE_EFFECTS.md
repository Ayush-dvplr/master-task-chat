# FIX_SIDE_EFFECTS: fixed id -> new ids it produced

Rows: a QC finding whose fix (RECHECK_FIX row) produced a new finding in the next QC round, from `cascades.json` cause = fix-induced. "times fixed" = rows in `fires.json` with next_round_status fixed for that id (all tasks). A chain with two source ids (e.g. CL-2/TS-19) is counted under each.

| fixed id | times fixed (fires.json) | new findings produced | produced ids (task round sev) | side-effect rate |
|---|---|---|---|---|
| IN-15 | 0 (fixed outside the fires id, e.g. COV/IN-15 regen) | 6 | dispatch v3 DS-22 fail, dispatch v3 DS-22 fail, dispatch v3 TS-17 fail, dispatch v3 TS-24 fail, dispatch v3 AL-18 fail, dispatch v3 AL-19 fail | n/a |
| JD-5 | 8 | 5 | match v2 JD-15 fail, schema v3 JD-2 fail, sentinel v2 JD-9 warn, sentinel v3 JD-7 minor, sensor v2 IN-8 fail | 0.62 |
| STEP11 | 9 | 3 | emberforge v7 TS-25 fail, schema v2 TS-13 minor, sentinel v3 TS-14 warn | 0.33 |
| JD-18 | 5 | 2 | dispatch v2 JD-7 fail, vendor v3 JD-7 warn | 0.40 |
| TS-16 | 5 | 2 | dispatch v4 TS-14 minor, dispatch v4 TS-15 minor | 0.40 |
| TS-19 | 6 | 2 | dispatch v4 TS-23 warn, sentinel v2 TS-26 fail | 0.33 |
| TS-13 | 2 | 2 | schema v3 TS-25 fail, schema v6 TS-15 warn | 1.00 |
| COV-4 | 0 (fixed outside the fires id, e.g. COV/IN-15 regen) | 1 | dispatch v4 JD-5 minor | n/a |
| COV-1..6 | 0 (fixed outside the fires id, e.g. COV/IN-15 regen) | 1 | dispatch v4 TS-23 warn | n/a |
| COV-6 | 0 (fixed outside the fires id, e.g. COV/IN-15 regen) | 1 | dispatch v4 AL-28 warn | n/a |
| AL-2 | 8 | 1 | emberforge v7 TS-25 fail | 0.12 |
| JD-7 | 6 | 1 | match v2 JD-15 fail | 0.17 |
| AL-27 | 12 | 1 | schema v4 TS-13 minor | 0.08 |
| DS-15 | 1 | 1 | schema v4 DS-18 warn | 1.00 |
| DS-18 | 1 | 1 | schema v5 DS-22 minor | 1.00 |
| IN-16 | 6 | 1 | sentinel v2 AL-27 fail | 0.17 |
| CL-2 | 3 | 1 | sentinel v2 TS-26 fail | 0.33 |
| JD-15 | 6 | 1 | sentinel v2 JD-9 warn | 0.17 |
| TS-26 | 2 | 1 | sentinel v3 TS-14 warn | 0.50 |
| AL-7 | 1 | 1 | vendor v2 DS-27 fail | 1.00 |
| CL-3 | 2 | 1 | match v2 DS-21 fail | 0.50 |
| F-04 | 0 (fixed outside the fires id, e.g. COV/IN-15 regen) | 1 | match v2 DS-21 fail | n/a |

Produced-id totals (how often each id appears as a side effect):

JD-7 x3, DS-22 x3, TS-14 x3, TS-25 x3, TS-15 x2, TS-23 x2, TS-26 x2, TS-13 x2, JD-15 x2, JD-9 x2, DS-21 x2, TS-17 x1, TS-24 x1, AL-18 x1, AL-19 x1, JD-5 x1, AL-28 x1, JD-2 x1, IN-8 x1, DS-18 x1, AL-27 x1, DS-27 x1

Notes on the matrix:

- dispatch v3: six findings (DS-22 x2, TS-17, TS-24, AL-18, AL-19) came from one P12 r2 edit, not from their own ids. The r2 fixes for IN-15/AL-28/TS-16 regenerated `test_output.py` from a stale generator: `master_chat_work/20261022_dispatch-plan-reoptimization/p12_r3/RECHECK_FIX.md:108` "P12 r2 regenerated that file from stale `WORK/build/mktests.py`, overwriting both fixes while leaving TRUTH.md's claims". They are filed under IN-15 (the first r2 row, p12_r2:12 "(via build/mktests.py)").
- JD-5 (split a compound judge criterion) is the most dangerous fix: 5 side effects across 4 tasks (schema JD-2, sentinel JD-9 and JD-7, match JD-15, sensor IN-8). QC_FIX_PLAYBOOK.md has no JD-5 row, so every one of those fixes was improvised (`master_chat_work/20261023_match-replay-desync-audit/p12_r1/RECHECK_FIX.md:107` "a JD-5 row for dropping extra clauses would help").
- TS-13 (split an omnibus check) produced TS-25 (schema v3) and TS-15 (schema v6); the playbook row `master_chat_tasks/knowledge/QC_FIX_PLAYBOOK.md:33` already says "re-run TS-25 on both halves", which would have caught the first one but not the second.
- JD-18 (add a code-quality criterion) produced JD-7 twice (dispatch v2, vendor v3) before the playbook existed; the current row `master_chat_tasks/knowledge/QC_FIX_PLAYBOOK.md:43` "confirm the oracle meets it (JD-7)" closes that gap.
- Only 3 of the 30 fix-induced chains were anticipated by any playbook row, and all 3 only by rows written after the round (JD-18 row x2, TS-13 row x1). No playbook-era fix had its side effect predicted by the row it used.

## Harden / rebuild between rounds -> new ids

| task round | harden edit | new ids |
|---|---|---|
| cohort v3 | harden_r2 7cbd9f5 | JD-7(f), DS-22(f), AL-2(f), AL-27(f), TS-13(m), TS-29(m) |
| dispatch v5 | judge rework cc4bb7f | DS-22(f), JD-8(f), JD-13(m) |
| district v2 | harden_r2 (22 Oct) | DS-27(w), TS-25(w) |
| district v4 | harden_lp1_r1 0154d63 | JD-14(f), JD-18(f), AL-27(f), DS-22(m), TS-23(w) |
| emberforge v2 | rebuild 22 Oct | TS-19(m), JD-6(m), IN-L3(w), G03-unlabelled(w), G03-unlabelled(w) |
| emberforge v6 | harden_lp1_r1 e215748 | DS-20(f), TS-29(f), JD-7(f), AL-2(f), AL-6(f), AL-27(f), STEP11(f), JD-16(f) |
| schema v2 | rebuild_r1 (22 Oct) | TS-14(w) |
| schema v6 | harden f681ef6 | JD-5(m), DS-22(f) |
| vendor v2 | rebuild_r1 (22 Oct) | JD-7(f), JD-18(f), JD-5(f) |
