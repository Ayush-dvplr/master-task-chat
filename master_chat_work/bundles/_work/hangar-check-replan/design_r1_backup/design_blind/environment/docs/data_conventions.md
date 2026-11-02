# Data conventions

All input files are in one data folder (default `/app/environment/data/`). Dates are ISO `YYYY-MM-DD`.

## Files

| file | content |
|---|---|
| `fleet_limits.toml` | `season` id, `season_start` and `season_end` (both days belong to the season) |
| `fleet_register.csv` | `tail`, `aircraft_class`, `operator`, `status` (`ACTIVE` or `RETIRED`) |
| `check_requests.csv` | `request_id`, `season`, `tail`, `check_type`, `base`, `available_from`, `due_date`, `duration_days`, `status` (`OPEN`, `DONE`, `CANCELLED`) |
| `published_plan.csv` | `request_id`, `published_start` |
| `base_calendar.jsonl` | one object per base and date: `base`, `date`, `status` (`OPEN`, `NO_START`, `CLOSED`) |
| `disruption_notice.docx` | table with header `base`, `from`, `days` (a closure of `days` days in a row starting on `from`) and table with header `tail`, `available_from` (revised availability) |
| `planning_limits.docx` | table with header `item`, `value` (rows `overtime_pool_shifts` and `shift_cost`) and table with header `class`, `revenue_per_day`, `overdue_weight`, `deferral_penalty` |
| `check_types.json` | per check type: `max_compress_days`, `overtime_shifts_per_day` |

## Word files

`disruption_notice.docx` and `planning_limits.docx` are WordprocessingML packages as ECMA-376 Parts 1
and 2 define them. The package relationship of type officeDocument names the main document part.
Only the current text of the main document part counts: text inside `w:del` or `w:moveFrom` is not
current text, text inside `w:ins` or `w:moveTo` is. Where `mc:AlternateContent` gives alternatives,
the first `mc:Choice` whose `Requires` prefixes the reader understands applies, otherwise
`mc:Fallback`; a reader of these files understands the WordprocessingML main namespace (`w`) and no
other. A table cell's value is its current text with surrounding spaces removed. Each table is found
by the text of its first header cell. All numbers in these tables are whole numbers.

## Bases

The bases are North, South, West and East. Each base has one heavy check line.

## Which rows are planned

Only rows of `check_requests.csv` whose `season` equals `season` in `fleet_limits.toml` and whose
`status` is `OPEN` are read for the plan. Every other row is ignored and is never reported.

Each read row is checked in this order and the first reason that applies rejects it:

1. `duplicate_request`: its `request_id` already appeared on an earlier read row (the earlier row is kept);
2. `unknown_base`: `base` is not one of the four bases;
3. `unknown_check_type`: `check_type` is not a key of `check_types.json`;
4. `unknown_tail`: `tail` is not in `fleet_register.csv`;
5. `retired_tail`: the tail's register `status` is `RETIRED`;
6. `bad_date`: `available_from` or `due_date` is not a valid ISO date;
7. `bad_duration`: `duration_days` is not a whole number of 1 or more;
8. `no_published_start`: the `request_id` has no row in `published_plan.csv`.

A rejected row is left out of the plan. Its line is its line number in `check_requests.csv`, where
the header is line 1. Every row that passes is an open request of the season.

## Values used by the plan

- Class of a request: the `aircraft_class` of its tail in the register.
- Available day: the `available_from` of the tail in the `tail` table of the notice
  when the tail is listed there, otherwise the request's own `available_from`. A request available
  before `season_start` is available from the first season day.
- Closed days of a base: dates with `status` `CLOSED` in `base_calendar.jsonl` plus every day of each
  closure row of the notice for that base. Dates with `status` `NO_START` are no-start days.
  Calendar rows outside the season are ignored.

If an input file is missing or cannot be parsed, the run stops with a non-zero exit code and a
message on standard error that names the file.
