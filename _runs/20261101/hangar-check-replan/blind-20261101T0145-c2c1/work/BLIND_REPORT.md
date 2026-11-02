# BLIND REPORT — hangar-check-replan (sha e8e9c82, step P13)

Session rename: `name_session.py e8e9c82` printed `codex: no match` and `opencode: ['ses_e6c67a11fffejk2aM34oDkR7oR']`, so the rename landed on the opencode session. Work started `Sun Nov  1 01:43:37 IST 2026`.

## Files read, in order

1. `instruction.md`
2. `environment/docs/README.md`
3. `environment/docs/data_conventions.md`
4. `environment/docs/planning_policy.md`
5. `environment/docs/overtime_policy.md`
6. `environment/docs/deferral_policy.md`
7. `environment/docs/output_schema.md`
8. `environment/data/fleet_limits.toml`
9. `environment/data/check_types.json`
10. `environment/data/fleet_register.csv` (counted and indexed, not read line by line)
11. `environment/data/check_requests.csv` (screened with a stdlib pass)
12. `environment/data/published_plan.csv`
13. `environment/data/base_calendar.jsonl` (in-season slice summarised)
14. `environment/data/disruption_notice.docx` (zip parts, then tables)
15. `environment/data/planning_limits.docx` (zip parts, then tables)
16. `work/TODO.md`

## Minutes to first full write

**15 minutes** — reading and data inspection ran 01:43:37 → ~01:56; the complete program existed and compiled at 01:58:32. (A first single-shot write of the whole file was cut off by an output-length limit and left `app/` empty, so the final file was written in four consecutive pieces; no logic changed between the attempt and the pieces.)

## What the self-check covered, and its result

One run of the program on the shipped data under the 600 s cap and `/usr/bin/time -p`: exit 0, no stderr, **0.10 s** (instruction limit 60 s). All eight required outputs present with the documented key sets.

Then `work/selfcheck.py` (0.11 s) re-loaded the inputs independently and asserted:

- every `check_plan.json` row has exactly the documented field set, and `tail`/`base`/`check_type`/`aircraft_class`/`segment` match the source row and register;
- rows sorted by `request_id`, one row per accepted open request, none for rejected or out-of-season rows;
- legality of every scheduled check: window length = `duration − compress_days`; start on or after the effective available day (notice override, clamped to season start); start not a closed or no-start day; no closed day inside the window; finish inside the season; no two checks of the same base overlap on a day;
- recomputed `overdue_days`, `overtime_shifts` (= `compress_days × overtime_shifts_per_day`), the `compress_days ≤ min(max_compress_days, duration − 1)` limit, and the `moved` flag against `published_plan.csv`;
- deferred rows: null dates, zeros in all counters and all five money fields, `moved` true, reason in `{no_slot, plan_trade}`;
- fleet overtime 64 ≤ pool 64; the allowance spent greedily in the documented widebody → narrowbody → regional, `due_date`, `request_id` order; the four per-check identities (`overtime_cost`, `allowance_shifts + paid_shifts = overtime_shifts`, `allowance_credit`, `settled_overtime_cost`);
- the three plan terms recomputed from the rows, and the summary's counts, `moved`, pool figures and settlement block;
- every region and segment aggregate (counts, `compress_days`, `overtime_shifts`, `overdue_days`, `first_start`, `last_finish`, `allowance_granted`, `allowance_used`, `fleet_overtime_used`), that segment files carry no `allowance_granted`, and that region and segment totals agree with `plan_summary.json`;
- `data_quality.json` list order, line numbers and reasons against a separate screening pass, and that all eight reason keys are present.

**Result: PASS — 21 checks, no problems.** Controls the data itself defines: 29 in-season open rows → 21 planned + 8 rejected (one per reason); the overtime pool is exactly saturated (64/64); `Q68307` is the only infeasible request and is deferred as `no_slot`.

## Crash fixed

None. The program ran correctly on its first execution; nothing was changed after the self-check.

## Lessons for the master

- `published_start` equals the effective available day for all 21 accepted requests, so the third term almost never pulls against the first two; a case where waiting for the published start is the right trade would exercise the policy far harder.
- The disruption notice ships with an **empty** closure table (header row only), so the "closure of `days` consecutive days" branch of `data_conventions.md` is never exercised by the shipped data.
- The docs require full WordprocessingML handling (`w:ins`/`w:del`, `mc:AlternateContent`) but neither `.docx` contains any revision or alternate content, so that reading effort is unverifiable from the shipped data alone.
- `output_schema.md` fixes the field sets but not the key order of the JSON objects; I followed the order of the doc on the assumption that comparison is field by field, not byte by byte.
- `overtime_policy.md` says the allowance "never changes which plan is optimal" — stating explicitly that the second term uses the gross `overtime_cost` would remove the last doubt.
