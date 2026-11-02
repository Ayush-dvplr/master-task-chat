# TRUTH.md - outage-window-replan

## Defect

There is no broken program to repair. `/app/data` holds ten data files (20493 lines) and four contract documents under `/app/data/docs/`, and the deliverable is a reusable program `/app/out/derive_report.py` that replans a season of transmission maintenance outages after a control-room notice and writes nine exact JSON documents. The program is run again on fresh seasons in the same layout, so the work is the replan itself, not the shipped answer.

0. (focal) Level 1 of the objective (`replan_contract.md:35`) asks for the smallest total risk-days over every feasible season. On the shipped season every greedy order, every repair of the published plan and every bounded search reaches that minimum, because each region and crew type holds a handful of requests. The fresh seasons put three or more contended valleys into every region and crew type (cheap load days where a crew loss leaves one crew), bridged so that each lane is one contention component of about thirty requests. A greedy plan, a local search from it, a repair of the published plan or a search that returns its incumbent when a time guard fires is feasible and higher on level 1 in every region; an unguarded depth-first search over the whole component does not finish inside the stated 60 seconds.
1. (focal) Level 2 (`replan_contract.md:36`) counts moved outages with five stated cases. Every fresh lane carries a published request whose published start is not its earliest equal-cost start and a heavier control-room request that can take the earliest day; the minimum keeps the published start. A program that drops level 2, or counts a deferred request that stays deferred as moved, or counts a control-room request as moved, picks a different season.
2. (focal) Level 3 (`replan_contract.md:37`) breaks the remaining ties by the start-day list in ascending `asset_id` order with deferral later than every day. Every fresh lane carries two new requests whose windows exactly fill a flat stretch of one crew; both orders cost the same and move nothing, and only the lower `asset_id` first is selected. A dynamic program or search that keeps the first optimum it meets in its own order publishes the other season.
3. (drift) The fresh seasons change the release values that the shipped files carry: `published_at`, the public class weight, `defer_factor` and both band floors in `risk_policy.toml`. A program that copies the shipped values instead of reading them drifts on every fresh document.
4. (trap) Rejection checks run in the stated order (`intake.md:11`): a record that is both out of season and too short is `out_of_season`, a duplicate whose window is too short is `window_too_short`, and a duplicate still counts after its first record was withdrawn (`intake.md:16`). A `CREW_LOSS` stamped exactly at `published_at` has no effect (`intake.md:34`).
5. (trap) A blackout day forbids a start only (`replan_contract.md:22`); an outage already out stays out through it. A precedence `after` may start on the day after the `before` request's last day, not on that last day (`replan_contract.md:25`).

## Load-bearing work

- Intake (`docs/intake.md`): accept `requests.json` records in list order and then `NEW_REQUEST` events in log order, with the four checks in order; apply `CREW_LOSS` and `WITHDRAW` events stamped after `published_at`; count malformed lines in `ignored_lines` whatever their timestamp.
- Season model (`docs/replan_contract.md`): weights from `customers.csv` and the class weights, load factors from the daily peak and the bands, capacity from on-duty roster rows less crew loss, feasibility from window, blackout start, capacity, incompatibility and precedence.
- Replan: one exact lexicographic optimum per region and crew type, since every network entry stays inside one region and crew type (`replan_contract.md:27`) and capacity is per region and crew type.
- Reports (`docs/output_schema.md`): the nine documents, every figure taken from the one selected season (`replan_contract.md:3`).

On the shipped data the reference selects a season with 79 active requests (68 published, 11 from the control-room log), 72 scheduled, 7 deferred (no_feasible_start 5, predecessor_deferred 2), 6 moved, risk-days 2466, crew-days 240, objective [2466, 6]. `data_quality.json` lists 9 rejected records (duplicate_request 2, out_of_season 2, unknown_asset 3, window_too_short 2), 5 withdrawn requests and 5 ignored log lines.

## Verification

- `tests/test_output.py` (1733 lines) holds 26 checks worth 92 positive weight and 8 negative weight; the negative tests are `negative_outside_library_import` (-3), `negative_hardcoded_sample_answers` (-5). Three grade the delivered shipped documents; 74 weight grades two fresh seasons built by the embedded generator (`build_inputs`, tests/test_output.py:255; release values from `release_literals`, tests/test_output.py:60; seeds at tests/test_output.py:1228), 50 of it in weight-5 checks; three run the program on an altered copy, a relocated copy and a copy with `customers.csv` removed.
- The expected documents come from an independent engine inside the tests: a forward day sweep with backward values (`sweep`, tests/test_output.py:1025) and a fixing pass in `asset_id` order (`reference`, tests/test_output.py:1174). The delivered program is run with the stated command as an unprivileged user from its own working directory (`_run_program`, tests/test_output.py:1353); each document is compared whole and the message names the first differing path (`_first_difference`, tests/test_output.py:1451).
- Measured: oracle 1.0 on three runs and 0.0 on a no-op run, test channel only. The reference takes about 2.5 to 2.9 seconds per fresh season inside the 60-second limit.
- `solution/solve.sh` copies `solve.py` to `/app/out/derive_report.py`, runs it on `/app/data`, then prints `check <id> ok` and one witness line for eight self-checks (solution/solve.sh:180).

Digests:

solve.sh: 26b5b21b7d4dfefdcd183fe3622a654e88e69453bcfdf14a7436cd31b5cf0e50
solve.py: 98f7f7494b3f7912d85f607d84386b6d96511f04a0f1c080e00979d6baeed309
test_output.py: 060e640f2973881f7101a409e3c0b77e361e6c5e9c9a56194dd854e63a65a2d8
judge.toml: b7ebc38722c39cf1f0cd73aa0d406f6cb64ad60ecce8d3db60a57df7377829ad
instruction.md: 8fc9d33a4aeb2fccb7d892735acaac287beec056bb962fcdc21d9c8442f703c8

## Root cause

The shipped season is small enough that every plausible method returns the minimum on it, so a program checked only against `/app/data` looks finished. The rules that decide the fresh seasons are all written in `docs/replan_contract.md` and `docs/intake.md`; what differs is the size and contention of each region and crew type, and the planted ties and keep pairs that only the full objective order settles.

## Solution shape

`solve.py` (472 lines) reads every file through one loader that names the file in any error, builds the season per `docs/intake.md`, and solves each region and crew type with `LanePlanner` (solution/solve.py:262): a forward sweep over days whose state is the set of waiting requests, the requests still out with their end days, and the deferred predecessors; each state keeps the lexicographically least (risk-days, moved, start list) reached so far, which is exact because two paths that reach one state have decided the same requests. Moved follows `is_moved` (solution/solve.py:258); rejection order follows `_take` (solution/solve.py:229); bands follow `_band` (solution/solve.py:220); reasons start at solution/solve.py:387.

## Ordered plan

1. Read `docs/RULES.md` and the three documents it names.
2. Write the loader and intake with the four checks in order and the log rules.
3. Build weights, factors, capacity and the feasibility test.
4. Write the exact per-lane replan carrying the full objective order.
5. Write the nine documents per `docs/output_schema.md`.
6. Run once on `/app/data` with `--out /app/out` after the last change.

## Pitfalls

- A time guard that returns the incumbent turns a timeout into a wrong season.
- Keeping only (risk-days, moved) per state loses the level-3 order.
- Hard-coding the shipped `defer_factor`, class weights, band floors or `published_at`.
- Treating a blackout day as a day an outage cannot be out.
- Counting HEARTBEAT lines, or skipping malformed lines stamped before `published_at`, in `ignored_lines`.

## Provenance

```yaml
uuid: null  # task.toml carries no canary_guid or uuid field
instance_id: outage-window-replan
task_name: terminal-bench/outage-window-replan
fix_patch_sha256: 26b5b21b7d4dfefdcd183fe3622a654e88e69453bcfdf14a7436cd31b5cf0e50  # sha256 of solution/solve.sh
solve_py_sha256: 98f7f7494b3f7912d85f607d84386b6d96511f04a0f1c080e00979d6baeed309  # informational; solve.py is 472 lines
language: python
golden_score_measured: null
golden_score_channel_a_pct: null
golden_score_channel_b_pct: null
golden_score_runs: 0
golden_score_trial_id: null
golden_score_verified_by: >
  Local runs of solve.sh through the test channel give exactly 1.000 on
  each of three oracle runs and exactly 0.000 on a no-op run; the judged channel has no oracle score.
caveat: >
  The test channel carries 26 checks worth 92 positive weight and
  8 negative weight, so on its own it ranges -0.087 to +1.000. The judged
  channel carries 18 criteria worth 36 positive points and -18
  negative points (R12 (-3), R13 (-5), R14 (-3), R15 (-5), R16 (-1), R18 (-1)).
  tests/reward.toml divides each channel's weighted sum by its positive
  total and gives each half of the reward, so the combined reward runs from
  -0.293 to +1.000 with no clamp.
```
