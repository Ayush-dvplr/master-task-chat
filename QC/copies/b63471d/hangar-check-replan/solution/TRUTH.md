# TRUTH.md - hangar-check-replan

## Defect

There is no program yet. The agent writes `/app/out/derive_report.py`, which replans one season of
aircraft heavy checks at four hangar bases (North, South, West, East, one line each) after a
disruption notice, then settles the plan's overtime against one fleet overtime allowance. The run
`python3 /app/out/derive_report.py DATA_DIR OUT_DIR` must write nine JSON files that match the
expected values field by field, on the shipped folder and on other folders of the same layout.

The work items, classified:

1. (focal) Settlement of overtime against the fleet allowance (overtime_policy.md:12-27). After the
   plan is fixed, the four base grants in `planning_limits.docx` form ONE fleet allowance. It pays
   scheduled checks one at a time in the order class widebody, narrowbody, regional; within a class
   earlier `due_date`; then smaller `request_id`. Each check takes min(own overtime shifts,
   allowance left), at whatever base it is. `allowance_used` is the sum of what checks took (never
   the grant), `settled_overtime_cost = overtime_cost - allowance_credit`, and `allowance_left` is
   the fleet allowance minus the use. On the shipped folder every grant exceeds its base's use, so
   every check is paid in full and the order never matters; on other folders the allowance runs out
   part way through a check, a base uses more than its own grant, two checks of one class share a
   due date across bases, or the use lands exactly on the allowance or one shift above it.
2. (focal) The season plan is the single optimum of a four-step order over the whole fleet
   (planning_policy.md:22-41): first term (overdue cost plus deferral penalties), second term
   (revenue lost plus `shift_cost` times overtime shifts), third term (moved requests), then the
   start-day list and finish-day list in request_id order. One overtime pool binds all four bases
   together (overtime_policy.md:9-10); a check may be compressed and a request may be deferred.
3. (focal) Every base and both segments always get their report and summary row, with zero counts
   and null first_start / last_finish when they have no open request (output_schema.md:5-8).
4. (drift) Inputs are spread over csv, jsonl, toml, json and two Word packages; the notice's revised
   availability replaces a request's own date, an available day before season start is day 1,
   and notice closures add to calendar closures (data_conventions.md:48-56).
5. (drift) Row screening: only rows of this season with status OPEN are read; eight reasons in a
   fixed order; `duplicate_request` looks only at earlier READ rows, so a request id that first
   appears on an ignored row (another season, CANCELLED, DONE) is not a duplicate
   (data_conventions.md:29-46).
6. (trap) Deferral reason: `no_slot` only when the check cannot finish by season end at any
   compression on its own empty base line from its available day; otherwise `plan_trade`
   (deferral_policy.md:3-9). A plan can defer a request that would fit alone because the pool or a
   higher-cost check needs the line.
7. (trap) A request is moved when its start differs from `published_start` or it is deferred; a
   start on the published day is legal even when an earlier day is free, and it can win the third
   term (planning_policy.md:30-31).

Shipped figures: 21 open requests (5 or 6 per base), plan_terms first 528, second 5290, third 11;
pool 64, used 64; one deferral, Q68307 with reason `no_slot`; settlement allowance 74, used 64,
left 10, overtime_cost 960, credit 960, settled 0; one rejected row for each of the eight reasons.

## Load-bearing work

- Read the two Word packages through `_rels/.rels` (officeDocument relationship) to the main part,
  collect each `w:tbl` as rows of cell text (joined `w:t`, stripped), and find each table by its
  header row (two tables start with `base`; the second header cell tells them apart).
- Screen rows as above and record `{request_id, line, reason}` with line = csv line (header 1).
- Build per base: closed days (calendar CLOSED in season plus notice closure days), no-start days,
  and each request's available day, duration, due day, published start, class rates.
- Exact optimisation. Per base, a memoised search over (set of placed requests, first free day)
  gives, for every overtime total, the best (first, second, third, start list, finish list) for that
  base. Only two start days per compression need trying: the earliest legal start not before the
  line is free, and the published start when it is later and legal (later starts only add cost or
  break the tie toward smaller lists). Merge the four bases over the pool, comparing the full key
  with the start and finish lists in global request_id order.
- Settlement replay on the fixed plan in the stated order, then sums per base, segment and fleet.

## Verification

- Channel A, `tests/test_output.py`: 44 checks, positive weight total 137, negatives
  `negative_hardcoded_sample_answers` (-5), `negative_reads_check_files` (-5), `negative_writes_outside_out_dir` (-3). The program is run
  as an unprivileged user from a foreign working directory with exactly
  `python3 /app/out/derive_report.py DATA_DIR OUT_DIR`, 60 seconds per run, on the shipped folder,
  six further folders built by the generator embedded in the test file, and two edited copies of
  the shipped folder (allowance grants changed; revised availability removed). Fields are compared
  one family at a time and the first differing path is reported.
- Channel B, `tests/judge.toml`: 14 positive criteria worth 42 (nine process probes the oracle
  shows in the probe script `solution/solve.sh` writes to `/tmp/oracle_checks/probes.py`, plus error handling, malformed input, final-reply list, order of work,
  final run) and 4 negatives worth -16.
- `tests/reward.toml` gives each channel half: weight 0.5/137 on test_output, 0.5/42 on judge.

## Root cause

The shipped folder is degenerate on purpose for the settlement: every base's grant covers its use,
so a program that caps per base or pays in request_id order still matches every shipped settlement
field (crediting the grant and leaving settled equal to gross do show on shipped). The settlement
sentence has several moving parts (fleet pool of grants, class/due/id order, partial take, used vs
granted); a program that implements a simpler reading looks right on shipped and moves many fields
on folders where the allowance binds. The plan itself must be the exact optimum under the stated
order; base-by-base splits of the pool, first-found tie breaks and earliest-start-only search
change the plan, and every downstream field follows.

## Solution shape

`solution/solve.py` (stdlib only): `SeasonInputs` loads and validates every file (missing or
unparseable input exits 2 naming the file), `screen_requests` applies the eight reasons,
`BaseLine.frontier()` is the per-base exact search keyed by overtime total, `season_plan` merges
bases under the pool, `settle` replays the allowance, `build_reports` writes the nine files.
`solution/solve.sh` copies it to `/app/out/derive_report.py`, runs it on `/app/data`, then runs
the probe script `solution/solve.sh` writes to `/tmp/oracle_checks/probes.py`, which prints a witness line and `check Pn ok` for each process probe.

## Ordered plan

1. Read every doc under `/app/data/docs/`, starting with README.md.
2. Write the loaders, including the Word table reader, and the row screening; check counts.
3. Write the per-base search and the pool merge; confirm the plan terms by recomputing them from
   the per-check rows.
4. Write the settlement replay and the rollups; check that region sums equal row sums and that
   allowance_left equals allowance minus use.
5. Run the stated command on `/app/data`; then try edited copies (smaller pool, smaller grants, a
   base with no requests, a missing file) and a run from another directory on a copy of the inputs.

## Pitfalls

- Crediting `allowance_granted` instead of the shifts actually taken.
- Capping each base at its own grant; the four grants are one fleet allowance.
- Paying in request_id or start-day order; the order is class, due_date, request_id.
- Taking nothing when a check does not fit whole; it takes what is left.
- Leaving settled cost equal to gross overtime cost.
- Splitting the pool across bases, or keeping the first plan found on a tie.
- Trying only the earliest start; the published start can win the third term.
- Deriving the base and segment list from the requests seen; an empty base still gets its file.
- Treating ignored rows as earlier rows for `duplicate_request`.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: hangar-check-replan
task_name: terminal-bench/hangar-check-replan
fix_patch_sha256: 90eca5cd208b06ef3eca57906a5af2658a6ee1ec949e01afdc21381d9fc6e70e  # sha256 of solution/solve.sh
solve_py_sha256: ade521570ba350bc92f2333329dcb6a14a7852669a0d2d00c54b21fc32bde1ec  # sha256 of solution/solve.py
language: python
golden_score_measured: null  # not measured for this instance
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null  # no calibration trial has been run yet
golden_score_verified_by: >
  Not yet measured in a harness trial. Local oracle runs score 1.000 on the
  test channel in tests/test_output.py and a no-op run scores 0.000.
caveat: >
  The test channel carries 41 positive checks worth 137 weight and 3 negative
  checks worth -13 weight. The judged channel carries 14 positive criteria
  worth 42 points and 4 negatives worth -16. tests/reward.toml divides each
  channel's weighted sum by its positive total and gives each half of the
  reward.
```
