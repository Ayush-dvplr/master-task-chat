# Heavy hangar check replan — handover

## What I built

`derive_report.py` (Python 3 standard library only), at both
`app/derive_report.py` and `out/derive_report.py` (the `/app/out/derive_report.py` path the
instruction names). Run as `python3 derive_report.py --data <data folder> --out <output folder>`;
with no flags it reads `/app/environment/data/` and writes `/app/out/`. It reads only the data
folder and writes only inside the output folder. A missing or unparseable input stops the run with
exit code 1 and a message on stderr that names the file.

How it works:

1. **Input.** `fleet_limits.toml` (small key/value reader), the three CSVs, `base_calendar.jsonl`,
   `check_types.json`, and both `.docx` files. The Word reader goes through the package
   `officeDocument` relationship to the main document part, drops text inside `w:del` and
   `w:moveFrom`, keeps `w:ins` and `w:moveTo`, and for `mc:AlternateContent` takes the first
   `mc:Choice` whose `Requires` prefixes all resolve to the WordprocessingML main namespace,
   otherwise `mc:Fallback`. Tables are found by the text of their first header cell.
2. **Screening.** Only rows whose `season` matches `fleet_limits.toml` and whose `status` is `OPEN`
   are read; each is tested against the eight reasons in the documented order, first match wins,
   and the line number counts the header as line 1.
3. **Calendars.** Closed days per base = `CLOSED` calendar rows in the season plus every day of
   each notice closure row; `NO_START` rows are no-start days. The planning available day is the
   notice's revised availability when the tail is listed there, else the row's own
   `available_from`, clamped up to the first season day.
4. **Optimisation — exact, not heuristic.** Per base (one line, one check at a time) a subset DP
   over (set of checks already placed, first free day, overtime shifts used) carries the full
   lexicographic value (first term, second term, third term, start-day list, finish-day list).
   Start candidates are reduced to the earliest feasible start for each compression plus the
   `published_start` when it is feasible and later — any other start is dominated on every term.
   The four bases are then combined by a knapsack over the shared overtime pool that keeps the
   same lexicographic key, so the shared pool is handled exactly rather than split by a rule of
   thumb. The deferral reason is decided by the documented empty-line test, independently of the
   plan.
5. **Output.** `check_plan.json`, `regions/region_{north,south,west,east}.json`,
   `segments/segment_{commercial,public}.json`, `plan_summary.json`, `data_quality.json`.

## What I checked

One run on the shipped data (`/usr/bin/time -p`: **0.14 s real**, against the 60 s budget), then an
independent checker (`work/verify.py`, 0.08 s) that recomputes everything from the written
documents rather than from the solver's internals:

- all eight documents present; `check_plan.json` sorted by `request_id` with exactly the 14
  documented fields per check;
- every scheduled check: span length = `duration_days - compress_days`, compression inside
  `min(max_compress_days, duration_days - 1)`, shifts = compression × `overtime_shifts_per_day`,
  start on or after the available day, start not a closed or no-start day, no closed day anywhere
  in the span, finish on or before `season_end`, `overdue_days` and `moved` recomputed;
- no two checks overlap on a base line; fleet overtime 64 ≤ pool 64;
- deferred rows: null dates, zeros, `moved` true, reason recomputed;
- the three plan terms, all twelve totals in each of the six region/segment files, and every
  `plan_summary.json` count recomputed and matched;
- `data_quality.json` rejected list matched row for row and the eight counts matched.

Result: **PASS**. One defect was found during this self-check and fixed once: the notice's revised
availability was parsed but not applied as the planning available day, which had started two checks
before their revised release (Q42975 and Q89422). After the fix both respect it.

## Key figures (season 2027A, 2027-03-01 … 2027-06-28, 120 days)

- 5454 request rows; 29 belong to season 2027A and are `OPEN`; 8 rejected, one per reason
  (`Q49293` no_published_start, `Q77189` unknown_base, `Q63211` bad_duration, `Q78772` unknown_tail,
  `Q57324` duplicate_request, `Q90105` bad_date, `Q39484` unknown_check_type, `Q96218` retired_tail);
  21 open requests planned.
- 20 scheduled, 1 deferred (`Q68307`, North, `no_slot` — available 2027-06-19, 16 days, only 10
  season days left even at full compression), 11 moved.
- Plan terms: first **528**, second **5290**, third **11**. Overtime **64 of 64** shifts — the pool
  binds, which is why the cross-base knapsack matters.
- Per base (scheduled / deferred / shifts): North 5/1/28, South 5/0/10, West 5/0/12, East 5/0/14.
- Segments: commercial 12 scheduled / 1 deferred, public 8 / 0.
- The big closures drive the plan: North shut 2027-03-25…04-08, South 03-20…03-30,
  West 03-19…03-29, East 03-23…04-02.
