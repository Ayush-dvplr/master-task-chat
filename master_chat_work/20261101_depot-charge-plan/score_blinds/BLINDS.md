FAIL

# depot-charge-plan: blind scoring (4653510)

[blocked] No blind can be scored from the required verifier artifacts. All three
Harbor trials have `verifier_result: null` and
`exception_info.exception_type: RewardFileNotFoundError` in their trial
`result.json`. Their verifier directories contain only `test-stdout.txt`, with no
`ctrf.json`, `reward-details.json`, `reward.json`, or `reward.txt`.
Console/test stdout was not used to derive scores or diagnoses.

This is a scoring-workflow FAIL, not evidence that the task passes or fails its
hardness thresholds. Tests percentages, lever losses, and loss-kind percentages
are unknown, not zero. No individual check is assigned WRONG, TIMEOUT, or CRASH:
a missing verifier reward is not evidence of a blind-program crash.

## Summary

| Blind | Tests % | Lever points lost / total | WRONG % | TIMEOUT % | CRASH % |
|---|---:|---:|---:|---:|---:|
| ec4f695 (blind1) | N/A | unknown / 166 | N/A | N/A | N/A |
| be981e2 (blind2) | N/A | unknown / 166 | N/A | N/A | N/A |
| a60099a (blind3) | N/A | unknown / 166 | N/A | N/A | N/A |

When available, tests % is the weighted test component divided by 191 positive
points, not the combined tests/judge reward. Lever-loss and WRONG/TIMEOUT/CRASH
percentages use 166 lever points as their denominator. The 34 distinct lever
checks are counted once each, not once for every overlapping lever label.

Master rule: every blind must lose at least 40% of lever points by WRONG, and
every blind must score at most 65% on tests (also none above 70%). Neither
condition can be evaluated without the missing artifacts; PASS is not supported.

## Run Evidence

Scratch root: `/Users/mac/Desktop/Terminal Bench/_runs/20261101/depot-charge-plan/score-blinds-4653510/`.
Each trial path below is relative to that root.

| Blind | Trial | Structured result | Required scoring artifacts |
|---|---|---|---|
| ec4f695 | `jobs/blind1/blind1__qLQcod4/` | `result.json`: RewardFileNotFoundError | absent |
| be981e2 | `jobs/blind2/blind2__YQ2gSxE/` | `result.json`: RewardFileNotFoundError | absent |
| a60099a | `jobs/blind3/blind3__FrNFuDf/` | `result.json`: RewardFileNotFoundError | absent |

All three launches used the requested oracle command, one nohup process and one
log per blind, and overlapped in time. Each log records the capacity gate:
`FREE_MB=12898 USED_MB=0 CONTAINERS=0 CPUS=0/12 START=yes`.
Each wrapper reached `ALL_DONE`; Harbor's process exit was 0, but the structured
trial results show verifier failure. A successful CLI exit is not a tests score.

Each copy's `tests/` was checked with `diff -rq` against the frozen bundle, with
no differences. Only the copied `solution/solve.py` and `solution/solve.sh` were
replaced. The install-only shell scripts contain just the shebang, `mkdir -p
/app/out`, and `cp /solution/solve.py /app/out/derive_report.py`.
The bundle and its QC copy were not modified. No subagents, Docker prune, or
`--delete` option were used.

The frozen verifier's shipped checks read delivered reports without invoking
the program on shipped inputs (`_check_present`, `_check_delivered`). The required
install-only script does not create those reports. The blind1 artifact manifest
confirms the program was collected but the nine report files were not. This is
a setup observation only: without check results, no shipped-point losses are
inferred or scored from it.

## Per-check Accounting

Weights are from the frozen `tests/test_output.py`; lever labels follow
`LEVERS.md`. M = meter convention; F = shared feeder/cabinet limits;
T = lexicographic tie-break; C = coupled plan. P = plain rule, not a lever.
Every `U` cell means kept points unknown, lost points unknown, loss kind unknown,
and first differing field unavailable because no check message was produced in
the required artifacts. A negative weight is a possible penalty, not a
positive-point loss. All 45 registered checks are listed; none is silently
treated as passed or failed.

| Check | Weight | Lever | ec4f695 kept/lost/kind/field | be981e2 kept/lost/kind/field | a60099a kept/lost/kind/field |
|---|---:|---|---|---|---|
| program_and_reports_present | 1 | existence | U | U | U |
| shipped_policy_audit_exact | 3 | P | U | U | U |
| shipped_summary_exact | 3 | P | U | U | U |
| shipped_data_quality_exact | 3 | P | U | U | U |
| shipped_segment_public_exact | 3 | P | U | U | U |
| shipped_region_east_exact | 3 | P | U | U | U |
| fresh_h1_policy_audit_exact | 5 | M,F,T,C | U | U | U |
| fresh_h1_region_north_exact | 5 | M,F,T,C | U | U | U |
| fresh_h1_region_south_exact | 5 | M,F,T,C | U | U | U |
| fresh_h1_region_west_exact | 5 | M,F,T,C | U | U | U |
| fresh_h1_region_east_exact | 5 | M,F,T,C | U | U | U |
| fresh_h1_segment_commercial_exact | 5 | M,F,T,C | U | U | U |
| fresh_h1_segment_public_exact | 5 | M,F,T,C | U | U | U |
| fresh_h1_summary_exact | 5 | M,F,T,C | U | U | U |
| fresh_h1_data_quality_exact | 3 | P | U | U | U |
| fresh_h2_policy_audit_exact | 5 | M,F,T,C | U | U | U |
| fresh_h2_region_north_exact | 5 | M,F,T,C | U | U | U |
| fresh_h2_region_south_exact | 5 | M,F,T,C | U | U | U |
| fresh_h2_region_west_exact | 5 | M,F,T,C | U | U | U |
| fresh_h2_region_east_exact | 5 | M,F,T,C | U | U | U |
| fresh_h2_segment_commercial_exact | 5 | M,F,T,C | U | U | U |
| fresh_h2_segment_public_exact | 5 | M,F,T,C | U | U | U |
| fresh_h2_summary_exact | 5 | M,F,T,C | U | U | U |
| fresh_h3_policy_audit_exact | 5 | M,F,T,C | U | U | U |
| fresh_h3_region_north_exact | 5 | M,F,T,C | U | U | U |
| fresh_h3_region_south_exact | 5 | M,F,T,C | U | U | U |
| fresh_h3_region_west_exact | 5 | M,F,T,C | U | U | U |
| fresh_h3_region_east_exact | 5 | M,F,T,C | U | U | U |
| fresh_h3_segment_commercial_exact | 5 | M,F,T,C | U | U | U |
| fresh_h3_segment_public_exact | 5 | M,F,T,C | U | U | U |
| fresh_h3_summary_exact | 5 | M,F,T,C | U | U | U |
| fresh_h3_data_quality_exact | 3 | P | U | U | U |
| fresh_h4_policy_audit_exact | 5 | M,F,T,C | U | U | U |
| fresh_h4_region_north_exact | 5 | M,F,T,C | U | U | U |
| fresh_h4_region_south_exact | 5 | M,F,T,C | U | U | U |
| fresh_h4_region_west_exact | 5 | M,F,T,C | U | U | U |
| fresh_h4_region_east_exact | 5 | M,F,T,C | U | U | U |
| fresh_h4_segment_commercial_exact | 5 | M,F,T,C | U | U | U |
| fresh_h4_segment_public_exact | 5 | M,F,T,C | U | U | U |
| fresh_h4_summary_exact | 5 | M,F,T,C | U | U | U |
| reordered_copy_policy_audit_exact | 3 | M,F,T,C | U | U | U |
| relocated_copy_summary_exact | 3 | M,F,T,C | U | U | U |
| missing_settlements_stops_naming_file | 3 | P | U | U | U |
| negative_outside_library_or_network_import | -3 | NEG | U | U | U |
| negative_hardcoded_sample_answers | -5 | NEG | U | U | U |

The two negative checks use their actual registered names above;
`LEVERS.md` abbreviates them as `outside_library_or_network_import` and
`hardcoded_shipped_answers`.

## Why Each Is Unscored

- ec4f695: [blocked] required CTRF/reward artifacts missing; trial reports RewardFileNotFoundError, so no program-loss reason or first differing field is established.
- be981e2: [blocked] required CTRF/reward artifacts missing; trial reports RewardFileNotFoundError, so no program-loss reason or first differing field is established.
- a60099a: [blocked] required CTRF/reward artifacts missing; trial reports RewardFileNotFoundError, so no program-loss reason or first differing field is established.

`result_4653510.json` uses JSON null for all unavailable metrics. Its requested
`status: DONE` records completion of these run attempts and this failure report,
not successful scoring. Numeric tests scores and loss classifications remain
[blocked] until genuine verifier scoring artifacts are available. No substitute
verifier was used and no frozen test was changed to bypass this failure.
