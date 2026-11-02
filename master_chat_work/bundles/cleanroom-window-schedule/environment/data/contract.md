# Cleanroom night book

A pharmaceutical cleanroom runs a book of nights. On each night some jobs are offered, each in a
fixed time window, and the planner decides which jobs run and on which bay. This file is the whole
specification of the book data and of the documents to produce from it.

## Program

`python3 /app/out/derive_report.py <data_dir> <out_dir>` reads the ten input files below from
`<data_dir>` and writes the nine output documents into `<out_dir>`, creating it if it does not exist.
If one of the ten input files is missing, the program exits with a nonzero status and writes a
message naming the missing file to standard error. The program reads no other files, uses no
network and uses only the Python standard library; every figure it writes comes from the files it reads.

## Limits

A book holds at most 500 nights. A night has at most 72 jobs, and at most 7 of its jobs contain
any single minute. There are 3 bays and 3 families. Values are integers from 1 to 2000, minute
rates 1 to 9, fees 1 to 500 and crew minutes 5 to 120. The program may take 2 seconds per night
of the book.

## Input files

All files are UTF-8 text. CSV files are comma separated and TSV files tab separated, each with
one header row. Rows appear in no particular order.

| File | Content |
|---|---|
| `jobs.csv` | `job_id,night_id,window_id,client_id,family,value`: one row per offered job. |
| `windows.tsv` | `window_id, start, end`: a window in minutes after the night opens. A job's start and end are those of its window. Some windows are used by no job. |
| `bays.json` | `{"bays": [{"bay_id", "minute_rate", "initial_family"}, ...]}`. The list order is the bay order. |
| `qualifications.ini` | Section `[catalog]` has key `families`, a comma separated list of the family codes. One section per bay id has key `families`, the comma separated families that bay may run. |
| `setup_fees.csv` | `night_id,from_family,to_family,fee,crew_minutes`: the changeover terms of a night for one ordered pair of distinct families. No two rows share night, from family and to family. |
| `clients.jsonl` | One JSON object per line: `{"client_id", "site"}`. |
| `regions.csv` | `site,region`. The regions are North, South, West and East. Every site of `clients.jsonl` is listed. |
| `segments.tsv` | `client_id, segment`. The segments are commercial and public. Every client of `clients.jsonl` is listed. |
| `mandatory.json` | Object from night id to the list of job ids that must run that night. A night without a key has no mandatory job. |
| `audit.toml` | Table `[thresholds]` with integers `crew_minutes_limit` and `margin_floor`, and one `[[night]]` table per night with `id` and `date` (YYYY-MM-DD). Dates are distinct. Every night named in another file is listed here. A listed night may have no jobs. |

## Night order and rejection

Nights run in the date order given in `audit.toml`.

A night is rejected when one of these conditions holds; its code is the first condition that
holds, in this order:

1. `E_DUP_JOB`: a job id of the night appears on more than one row of `jobs.csv`.
2. `E_BAD_WINDOW`: a job of the night names a window id absent from `windows.tsv`, or its window
   does not satisfy 0 <= start < end <= 1440.
3. `E_UNKNOWN_RESOURCE`: a job of the night names a family absent from the catalog, or a client id
   absent from `clients.jsonl`.
4. `E_BAD_FEE`: `setup_fees.csv` has no row for the night for one of the six ordered pairs of
   distinct catalog families.

The message of a rejected night is `night <night_id> rejected: <code>`. A rejected night runs no
job and leaves every bay's family as it was. Every other night is accepted, and every accepted
night has at least one plan that satisfies the rules below.

## Plans

A plan of an accepted night chooses which of the night's jobs run and assigns each running job to
one bay whose qualifications list the job's family. A job occupies the minutes of its window, the
half-open interval [start, end); a job ending at minute t and a job starting at minute t share no
minute. Two jobs on one bay never share a minute. Every mandatory job of the night runs.

## Families and changeovers

Each bay holds a family. A bay that has run no job in the book holds its `initial_family`.

For a job on a bay, the previous family is the family of the latest-starting earlier job on that
bay in the same night; for the bay's first job of the night it is the family the bay holds when
the night begins. When a night ends, each bay holds the family of its last job that night, and a
bay that ran no job that night keeps its family.

A job whose family differs from its previous family has a changeover. It pays the `fee` of the
night's `setup_fees.csv` row from the previous family to the job's family, and it needs the
sterilisation crew during the crew window [start - crew_minutes, start), using that row's
`crew_minutes`. The bay runs no job during its crew window, so the bay's earlier job that night
ends at or before the window starts, and no crew window starts before minute 0. There is a single
sterilisation crew: two crew windows of one night never share a minute. A job without a changeover
has fee 0 and no crew window.

## Money and the chosen plan

The bay charge of a running job is its bay's `minute_rate` times (end - start). The net of a
running job is its value minus its bay charge minus its changeover fee. The net of a plan is the
sum of the nets of its running jobs.

Nights are planned one at a time in date order. An accepted night runs the plan of maximum net
among its plans that satisfy every rule above, given the families the bays hold when the night
begins. When several plans share the maximum net, the night runs the one whose run vector is
lexicographically smallest, where the run vector lists, for the night's job ids in ascending
order, 0 for a job that does not run and 1 for a job that runs; if that still ties, the one whose
bay vector is lexicographically smallest, listing for the same jobs 0 for not run or the 1-based
position of its bay in `bays.json`.

Every reported figure of a night is computed from its maximum-net-value plan.

## Output documents

Each document is one JSON object. All numbers are integers. Lists of nights are in date order.
A job belongs to the region of its client's site and to the segment of its client.

`summary.json`:

    {"nights": [{"night_id", "date", "status", "plan", "gross", "bay_charge", "fees", "net"}, ...],
     "totals": {"accepted_nights", "rejected_nights", "jobs_run", "gross", "bay_charge", "fees", "net"}}

`status` is `accepted` or `rejected`. `plan` lists the running jobs as
`{"job_id", "bay_id", "start", "end", "family", "changeover_fee"}`, ordered by start and then job
id. `gross` is the sum of the values of the running jobs, `bay_charge` and `fees` the sums of their
bay charges and changeover fees, and `net` the net of the plan. A rejected night has an empty plan
and zero figures. `totals` counts the nights by status and sums `jobs_run` (running jobs) and the
four figures over all nights.

`policy_audit.json`:

    {"nights": [{"night_id", "status", "crew_windows", "crew_minutes", "families_after", "flags"}, ...]}

`crew_windows` lists `{"bay_id", "job_id", "start", "end"}` for every crew window of the night,
ordered by start. `crew_minutes` is the total length of the crew windows. `families_after` maps
every bay id to the family it holds when the night ends. `flags` is the alphabetically sorted list
of the flags that apply: `crew_load_high` when `crew_minutes` is greater than
`crew_minutes_limit`, and `low_margin` when the night's net is less than `margin_floor`. A
rejected night has no crew windows, zero crew minutes, its unchanged families and no flags.

`data_quality.json`:

    {"rejected": [{"night_id", "code", "message"}, ...]}

lists every rejected night.

`region_North.json`, `region_South.json`, `region_West.json`, `region_East.json`:

    {"region", "nights": [{"night_id", "jobs_run", "gross", "net"}, ...], "totals": {"jobs_run", "gross", "net"}}

`region` is the region name. `nights` has one entry for every accepted night, including nights
where none of the region's jobs run; `jobs_run`, `gross` and `net` count and sum the running jobs
of the region (gross over values, net over job nets). `totals` sums the three figures over the
nights.

`segment_commercial.json`, `segment_public.json`: the same shape with key `segment` holding the
segment name, counting the running jobs of the segment.
