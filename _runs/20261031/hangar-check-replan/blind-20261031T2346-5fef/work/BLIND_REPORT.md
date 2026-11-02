# BLIND_REPORT — hangar-check-replan (sha 24bff4e, step P13)

Session renamed first thing: `name_session.py 24bff4e` printed `codex: no match` and `opencode: ['ses_e6cd22f6dffefh9xPBsHhVzWEu']`, so the rename landed. Session start `date` = Sat Oct 31 23:47:12 IST 2026.

## Files read, in order
1. `instruction.md`
2. `environment/docs/README.md`
3. `environment/docs/data_conventions.md`
4. `environment/docs/planning_policy.md`
5. `environment/docs/overtime_policy.md`
6. `environment/docs/deferral_policy.md`
7. `environment/docs/output_schema.md`
8. `environment/data/fleet_limits.toml`
9. `environment/data/class_rates.yaml`
10. `environment/data/check_types.json`
11. `environment/data/disruption_notice.md`
12. `environment/data/fleet_register.csv` (head, then scanned programmatically)
13. `environment/data/check_requests.csv` (head, then scanned programmatically)
14. `environment/data/published_plan.csv` (head, then scanned programmatically)
15. `environment/data/base_calendar.jsonl` (head, then scanned programmatically)

The four large files were read by head plus targeted Python scans rather than in full: 2621 register rows, 5453 request rows, 5452 published rows, 7303 calendar rows.

## Minutes to first full write
**6 minutes** (23:47:12 start → `app/derive_report.py` complete at 23:53). No partial drafts: the program was written once in a single pass, then three small cleanups (two dead helpers, a `nonlocal` moved to the top of its function, an unused variable) before the first execution.

## What the self-check covered, and its result
Two parts, both on the shipped data only.

*Run shape.* `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 out/derive_report.py --data environment/data --out out` → exit 0, **real 0.12 s** against the instruction's 60 s budget, empty stderr. All 7 named outputs exist: `check_plan.json`, `plan_summary.json`, `data_quality.json`, `regions/region_{north,south,west,east}.json`, `segments/segment_{commercial,public}.json`, each with the schema's keys in the schema's order.

*Independent re-derivation.* `work/selfcheck.py` rebuilds the fleet, calendar, notice and request facts straight from the data folder and re-checks the produced JSON rather than trusting the program's own internals: the 21 surviving checks are exactly the non-rejected in-season OPEN rows and are sorted by `request_id`; class, segment, tail, base and check type come from the source rows; `finish − start + 1 = duration − compress_days`; `compress_days ≤ min(max_compress_days, duration − 1)`; `overtime_shifts = compress_days × shifts_per_compressed_day`; start ≥ the tail's availability (with the notice's revised dates overriding the register, clipped to the season start); finish ≤ season end; the start day is neither CLOSED nor NO_START; no closed day falls inside a window; no two checks share a day on the same base line; `overdue_days` matches the due date; `moved` matches `published_plan.csv`; the deferred row carries nulls, zeros, `moved: true` and a reason re-derived by asking whether it would fit on an empty line (`Q87483` → `no_slot`); fleet overtime 82 ≤ pool 82. Every field of the four region files, the two segment files and `plan_summary.json` was recomputed from `check_plan.json` (plan terms, scheduled/deferred/moved counts, shift totals, base order North/South/West/East, segment order commercial/public), and the `data_quality.json` reason counts were checked against the 8 rejected rows. Result: **real 0.04 s, `ERRORS: none` — PASS.**

Figures for the record: plan terms 130 / 9670 / 5; 20 scheduled, 1 deferred, 5 moved; 82 of 82 pool shifts used (North 12, South 24, West 18, East 28); commercial 15/0, public 5/1; 8 rejections, exactly one per documented reason, at request-file lines 103, 689, 784, 1207, 2219, 4107, 4494, 4714.

## Crashes fixed
**None.** The program ran clean on its first execution and was never edited afterwards. The only failure in the session was in my own `work/selfcheck.py` (its duplicate-id bookkeeping raised on the first invocation); I fixed the checker and left `derive_report.py` untouched.

## Process notes
`ps -axo pid,rss,command | grep python` after the runs showed only the master's own `auto.py watch` — no python process of mine left behind. Commands are logged one per line in `work/CHECKS.md`; the handover text is in `work/FINAL_REPLY.md`.

## Lessons for the master
- The tie-break ladder in `planning_policy.md` stops at the plan terms; that it continues with the earliest start vector and then the earliest finish vector, in `request_id` order, had to be inferred — worth stating, since a field-by-field comparison hangs on it.
- `deferral_policy.md` does not say whether a deferral reason is judged against the *final* plan or against an empty line; I used an empty line, which is the only reading that gives a stable answer.
- Whether the overtime pool is a hard cap or a cost to minimise is only implied; the data makes it decisive (the optimum saturates all 82 shifts).
- `data_conventions.md` lists the eight reject reasons but not that they are mutually exclusive per row; the shipped data happens to put exactly one fault in each bad row, which hides the ordering question.
- A revised availability date from the notice that is *earlier* than the register's is undefined; I let the notice win either way.
