# CHECKS — hangar-check-replan blind (sha e8e9c82)

All paths relative to `/Users/mac/Desktop/Terminal Bench/_runs/20261101/hangar-check-replan/blind-20261101T0145-c2c1`.

| # | command | input path | what it showed |
|---|---------|------------|----------------|
| 1 | `python3 "/Users/mac/Desktop/Terminal Bench/master_chat_tasks/tools/name_session.py" e8e9c82` | — | `codex: no match` / `opencode: ['ses_e6c67a11fffejk2aM34oDkR7oR']` — rename landed on the opencode session. |
| 2 | `date` | — | `Sun Nov  1 01:43:37 IST 2026` (start of work). |
| 3 | `ls -R` on the blind dir | blind dir | `instruction.md`, `environment/docs/*.md` (6 docs), `environment/data/*` (8 files), empty `app/` and `out/`, `work/TODO.md`. |
| 4 | reads of `instruction.md` and all six docs | `environment/docs/` | task interface (`--data`, `--out`), data conventions, planning policy, overtime policy, deferral policy, output schema. |
| 5 | python3 stdlib inspection of the data files | `environment/data/` | season `2027A`, 2027-03-01..2027-06-28 (120 days); 2621 tails; 5454 request rows; 5452 published rows; 7304 calendar rows; check types A/C/D; pool 64, shift_cost 15; allowances North 30 / South 12 / West 13 / East 19 (74 total); notice closures table empty, 8 revised tail availabilities. |
| 6 | python3 screening pass over the request rows | `environment/data/check_requests.csv` | 29 rows are season 2027A + OPEN → 21 accepted (North 6, South 5, West 5, East 5) and 8 rejected, exactly one per rejection reason. |
| 7 | python3 scan of the in-season calendar | `environment/data/base_calendar.jsonl` | one CLOSED run per base (North 15 days, South/West/East 11 days) and 12 NO_START days per base. |
| 8 | `python3 -m py_compile app/derive_report.py` | `app/derive_report.py` | `COMPILE_OK`, 1302 lines. |
| 9 | `cp app/derive_report.py out/derive_report.py` | `app/derive_report.py` | program present at both required paths (47248 bytes each). |
| 10 | `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 out/derive_report.py --data environment/data --out out` | `environment/data` | exit 0, no stderr, `real 0.10` s (budget 60 s). |
| 11 | `ls -R out` | `out/` | all 8 deliverables present: `check_plan.json`, `plan_summary.json`, `data_quality.json`, `regions/region_{north,south,west,east}.json`, `segments/segment_{commercial,public}.json` (plus the program copy). |
| 12 | `cat out/plan_summary.json` | `out/plan_summary.json` | season 2027A; terms first 528 / second 5290 / third 11; 20 scheduled, 1 deferred, 11 moved; fleet overtime 64 of pool 64; settlement granted 74, used 64, left 10, overtime_cost 960, credit 960, settled 0; four base rows in order North/South/West/East; two segment rows commercial/public. |
| 13 | `cat out/data_quality.json` | `out/data_quality.json` | 8 rejections in file order (lines 32, 716, 855, 2853, 3321, 3380, 3628, 4243) and all eight reason keys present with value 1 — matches the independent screening pass of check #6. |
| 14 | `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 work/selfcheck.py` | `out/` + `environment/data` | `PASS: 21 checks, no problems`, `real 0.11` s. Re-derived the inputs independently and verified: field sets of every `check_plan.json` row; window length = duration − compress_days; start ≥ effective available day; start not a closed or no-start day; no closed day inside any window; no two checks overlap on a base line; finish ≤ season end; overdue_days, overtime_shifts and the `moved` flag recomputed; compress_days within the type limit; deferred rows all-zero with a valid reason; fleet overtime 64 ≤ pool 64; allowance spent greedily in widebody→narrowbody→regional, due_date, request_id order; per-check cost identities (`overtime_cost`, `allowance_shifts + paid_shifts`, `allowance_credit`, `settled_overtime_cost`); plan terms recomputed from the rows; region and segment aggregates (counts, shifts, overdue, first_start, last_finish, allowance_granted/used) and their agreement with `plan_summary.json`; `data_quality.json` list and counts. |
| 15 | `ps -axo pid,rss,command \| grep python` | — | no python process of this run left behind. |

Notes
- No crash occurred; the program ran correctly on its first execution, so nothing was fixed after the self-check.
- Both runs of the program stayed far inside the 600 s wall-clock cap and the instruction's 60 s limit (0.10 s and 0.11 s).
