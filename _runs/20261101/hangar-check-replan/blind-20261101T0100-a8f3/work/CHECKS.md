# CHECKS

Paths are relative to `/Users/mac/Desktop/Terminal Bench/_runs/20261101/hangar-check-replan/blind-20261101T0100-a8f3`.
Every program run was wrapped in `perl -e 'alarm 600; exec @ARGV'` and timed with `/usr/bin/time -p`.

## Reading the task

| command | input | what it showed |
|---|---|---|
| `python3 master_chat_tasks/tools/name_session.py d0dc88d` | - | `codex: no match`, `opencode: ['ses_e6c9067e4ffeia4eK7tmD0lZXe']` — renamed |
| `date` | - | Sun Nov 1 00:59:01 IST 2026 (start) |
| `ls -la` + `find . -type f` | blind dir | instruction.md, 6 docs, 9 data files, empty `app/`, `out/`, `work/` |
| read | `instruction.md` | program at `/app/out/derive_report.py`, `--data`/`--out`, stdlib only, 60 s per run |
| read | `environment/docs/README.md` | document register: which file governs which topic |
| read | `environment/docs/data_conventions.md` | input files, docx rules, 8 rejection reasons in order, available-day override, closed days |
| read | `environment/docs/planning_policy.md` | one line per base, span rules, three cost terms, lexicographic comparison + start/finish list tiebreak |
| read | `environment/docs/overtime_policy.md` | compress 0..min(max_compress_days, p-1), shifts = c * per_day, one fleet pool |
| read | `environment/docs/deferral_policy.md` | `no_slot` vs `plan_trade` (empty-line test) |
| read | `environment/docs/output_schema.md` | 8 output documents and every field |
| `wc -l`, `head`, `cat` | `environment/data/*` | season `2027A`, 2027-03-01..2027-06-28 (120 days); check_types A/C/D |
| `python3 -c ...` counters | `check_requests.csv` | 5454 rows; 29 rows are season 2027A + OPEN; bases incl. one `Hub`; types incl. one `E` |
| `python3 -c ...` join | requests + register + published_plan | the 29 read rows listed with class/status/published_start; 8 clearly rejectable |
| `python3 -c ... zipfile` | both `.docx` | 3 parts each; `_rels/.rels` -> `word/document.xml`; no `w:ins`/`w:del`/`mc:AlternateContent` present in this folder; closures table is header-only; 8 revised-availability rows |
| `python3 -c ...` | `base_calendar.jsonl` | 7304 rows, 4 bases, no duplicate (base,date); in season: North 15 CLOSED (3/25-4/8), South 11 (3/20-3/30), West 11 (3/19-3/29), East 11 (3/23-4/2); 12 NO_START per base |
| `python3 -c ...` | `fleet_register.csv`, `published_plan.csv` | classes widebody/narrowbody/regional only; no duplicate tails; no duplicate request_id in published_plan |

## Writing and running

| command | input | what it showed |
|---|---|---|
| `python3 -m py_compile app/derive_report.py` | program | `COMPILED` (no syntax error) |
| `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 app/derive_report.py --data environment/data --out out` | `environment/data` | exit 0, no output on stderr, **real 0.15 s** (first run, pre-fix) |
| `find out -type f` | `out/` | all 8 named documents present: `check_plan.json`, `plan_summary.json`, `data_quality.json`, `regions/region_{north,south,west,east}.json`, `segments/segment_{commercial,public}.json` |
| `cat out/plan_summary.json out/data_quality.json out/check_plan.json` | `out/` | first run: terms 500/5290/12, overtime 64/64, 20 scheduled, 1 deferred; data_quality has all 8 reasons exactly once |
| manual cross-read | `disruption_notice.docx` vs `out/check_plan.json` | **defect found**: Q42975 (VT-SXD, revised available 2027-03-16) started 2027-03-14 and Q89422 (VT-IPQ, revised 2027-03-21) started 2027-03-17 — the notice override was parsed but not applied |
| `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 work/verify.py` | `out/` + `environment/data` | pre-fix run: `PASS` (the checker imported the same buggy available-day, so it could not see the defect) |
| edit | `app/derive_report.py` | one fix: planning available day = notice override when the tail is listed, else the row's own `available_from` (the `bad_date` screen still reads the row's own value) |
| `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 app/derive_report.py --data environment/data --out out` | `environment/data` | exit 0, clean stderr, **real 0.14 s** (final run) |
| `/usr/bin/time -p perl -e 'alarm 600; exec @ARGV' python3 work/verify.py` | `out/` + `environment/data` | **PASS**, real 0.08 s; terms first=528 second=5290 third=11, overtime 64/64, 20 scheduled / 1 deferred / 11 moved |
| `python3 -c ...` spot read | `out/*` | Q42975 now starts 2027-03-16 (= its revised availability and its published start, so `moved` false); Q89422 starts 2027-03-31, the first day after the South closure 3/20-3/30 |
| `cp app/derive_report.py out/derive_report.py` | - | program also at the `/app/out/derive_report.py` path the instruction names |
| `ps -axo pid,rss,command \| grep python` | - | no python process of mine left running |

## What `work/verify.py` checked (independent recomputation from the outputs)

- every named output file exists; `check_plan.json` has one object per accepted request, sorted by `request_id`, with exactly the 14 fields of `output_schema.md` in order;
- per scheduled check: span length = `duration_days - compress_days`; `compress_days` within `min(max_compress_days, p-1)`; `overtime_shifts = c * overtime_shifts_per_day`; start >= available day (notice override applied); start not a closed or no-start day; no closed day anywhere in the span; finish <= `season_end`; `overdue_days` recomputed from `due_date`; `moved` recomputed against `published_plan.csv`;
- per base line: no two spans overlap;
- deferred rows: null dates, zero numbers, `moved` true, reason recomputed by the empty-line test;
- the three terms, `fleet_overtime_used` and the pool limit recomputed from `check_plan.json` and matched against `plan_summary.json`;
- all 12 totals of each of the four region files and the two segment files recomputed from `check_plan.json`;
- `plan_summary.json` counts, base order (North, South, West, East) and segment order (commercial, public);
- `data_quality.json`: rejected list equals the independently screened list in file order, all eight reason keys present, counts sum to the list length.
