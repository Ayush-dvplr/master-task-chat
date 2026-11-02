# Cohort retention study data contract

This contract defines the input files, the rules, and the shape of the outputs the
retention study must produce. It is read together with the study's audit policy in
`audit_policy.md`, which governs the study records it covers; where the two speak
to the same figure, the audit policy wins. Every figure is derivable from the files
in this directory alone. Counts are integers and every rate is an exact reduced
fraction; nothing is ever rounded to a decimal.

## Number format

Every rate is written as a string holding an exact reduced fraction, such as
`"1/3"`. When the reduced value has denominator one it is written as a bare
integer string, such as `"1"` or `"0"`. A negative rate carries its minus sign in
front of the numerator, such as `"-2/7"`. A rate whose denominator would be zero
is written as `"0"`. Money is integer cents and counts are plain integers.

## Identifiers

Account ids in every file, event types (in `events.csv` and in the lists of
`qualifying_rules.json`), plan names and segment codes are identifiers. Two
identifiers are the same when they match once surrounding spaces are removed and
letters are lower-cased, and every output writes an identifier in that form.
Event ids, period names and every other field are read and written exactly as
they appear.

## Input files

`events.csv` is the activity log with `event_id`, `account_id`, `event_date`,
`event_type` and `value_cents`. The `account_id` here is the raw id as captured
and is not necessarily the surviving account. Rows are captured by hand in places,
so not every row is well formed.

`accounts.csv` maps `account_id` to `account_name`, `segment` and `plan`.

`account_merges.csv` records account consolidations with `from_account_id`,
`to_account_id` and `effective_from`. A merge applies to an event whose date is on
or after `effective_from`. Merges chain, so a target may itself have been merged
onward, and the chain is followed until an account has no applicable merge. When
more than one merge row applies to the same account on a date, the one with the
latest `effective_from` wins; when two such rows share that `effective_from`, the
later row in the file wins.

`exclusions.csv` lists accounts to drop from the study entirely, by
`account_id` with a `reason`.

`period_calendar.csv` defines the study periods with `period`, `start_date` and
`end_date`, both bounds inclusive. Period order is by `start_date`.

`plan_prices.csv` maps a `plan` to its `monthly_price_cents`.

`plan_weights.json` maps a plan name to an integer weight used for weighted
revenue.

`segments.csv` maps a `segment` code to a human `label` and a `weight_override`.

`qualifying_rules.json` carries `qualifying_event_types`, `activity_event_types`,
`revenue_event_types`, an integer `minimum_value_cents`, and the boolean
`offset_zero_is_full`.

`study_config.json` carries the `study_id` echoed into every output, an integer
`max_offset`, and a human `label`.

`extract_manifest.json` is the export job's record of the files it wrote; its
`note` says what each figure counts.

## Cleaning and identity

Events are cleaned before any figure is computed, in this order, and a removed row
is counted once, under the step that removed it.

1. A row is malformed when its `event_date` is not a real calendar date written
   as `YYYY-MM-DD` (four digits, a hyphen, two digits, a hyphen, two digits), or
   its `value_cents` is not a non-empty run of the digits `0` to `9`. Malformed
   rows are dropped first.
2. A row whose date does not fall inside any calendar period is dropped as an
   out-of-calendar event.
3. Among the rows still remaining, a repeat of an earlier remaining row with the
   same `account_id` before merging, the same `event_date` and the same
   `event_type` is dropped as a duplicate; the first occurrence in file order is
   the one kept.
4. Each remaining row is folded onto its surviving account by applying the merge
   rules effective on that row's date.
5. A row whose resolved account appears in the exclusion list is dropped as
   excluded.
6. A row whose resolved account is absent from `accounts.csv` is dropped as an
   unknown-account event.

The cleaned events are ordered by date, then resolved account, then event type.

## Cohorts

An event qualifies when its type is in `qualifying_event_types` and its
`value_cents` is at or above `minimum_value_cents`. An account belongs to the
cohort named by the period of its earliest qualifying event. An account with no
qualifying event belongs to no cohort and contributes to no cohort figure. Only a
period that receives at least one account appears as a cohort.

## Retention, survival and offsets

Offset zero is the cohort's own period, offset one the next period in calendar
order, and so on up to `max_offset`. An offset that would fall past the end of the
calendar is omitted rather than reported as zero.

An account counts as active at an offset when it has at least one cleaned event of
a type in `activity_event_types` in that offset's period, and never before its own
cohort period. The activity count at an offset is the number of that cohort's
accounts that are active there, and the retention rate is that count over the
cohort size.

The survival rate at an offset is the smallest activity count seen at that offset
or any earlier offset, over the cohort size.

## Revenue

Revenue is booked from the cleaned events of a type in `revenue_event_types`,
whatever their period, one event at a time in the cleaned order. Each resolved
account holds a refundable balance that starts at zero. A `purchase` books its
`value_cents` and adds it to the balance. Any other revenue event books minus
the smaller of its `value_cents` and the balance, and lowers the balance by that
amount; the rest of its `value_cents` is unhonored. A cohort's revenue is the sum
of the amounts booked for the events of its accounts. Weighted revenue
multiplies each booked amount by the weight of the plan in force for the event
before summing. Every cohort appears in every revenue map, with 0 when it has no
revenue events. The revenue totals, the unhonored total, and the segment revenue
and account figures cover cohorted accounts only.

## Conservation identities

The cohort-size residual is the total number of cohorted accounts minus the sum
of the segment account counts. The revenue residual is the total revenue minus
the sum of the segment revenue figures, and the weighted revenue residual is the
same identity for weighted revenue. The offset-zero residual is zero unless
`offset_zero_is_full` is true, in which case it is the sum over cohorts of the
offset-zero activity count minus the cohort size. The control value residual is
the `value_cents_sum` that `extract_manifest.json` records for `events.csv` minus
the same figure counted from `events.csv` as delivered, or zero when the manifest
records none.

## Outputs

Each JSON artifact is serialized with sorted keys and a trailing newline.

`cohorts.json` carries `study_id`, `cohort_sizes` keyed by period, `cohort_members`
keyed by period holding the sorted account list, and `cohorted_account_count`.

`retention.json` carries `study_id`, `active_counts` keyed by cohort then by offset
as a string, and `retention_rates` in the same shape.

`survival.json` carries `study_id` and `survival_rates` keyed by cohort then offset.

`revenue.json` carries `study_id`, `revenue_cents_by_cohort`,
`weighted_revenue_by_cohort`, `total_revenue_cents`,
`weighted_revenue_total_cents`, `unhonored_cents`, and `weighted_share_by_cohort`,
which holds each cohort's weighted revenue over the weighted revenue total, as a
rate.

`segments.json` carries `study_id` and `segments`, keyed by segment code, with
one entry for every segment holding at least one cohorted account (the segment is
the one `accounts.csv` gives the resolved account), each holding `accounts`,
`revenue_cents` and `weighted_revenue_cents`.

`data_quality.json` carries `study_id`, `input_event_count` (data rows in
`events.csv`), `clean_event_count`, one count per cleaning step named
`malformed_event_count`, `out_of_calendar_event_count`, `duplicate_event_count`,
`excluded_event_count` and `unknown_account_event_count`, then
`excluded_account_count`, `merge_rule_count`, `pre_cohort_activity_count`,
`control_mismatches` and `rejections`, the rejection register the audit policy
defines. `control_mismatches` is the sorted list of `<file>:<figure>` names, such
as `accounts.csv:data_rows`, for every figure in `extract_manifest.json` that
differs from the same figure counted from the delivered file; a mismatch is
reported and the study is still produced.
`excluded_account_count` is the number of distinct account ids listed in
`exclusions.csv`, whether or not any event resolves to them. `merge_rule_count` is
the number of data rows in `account_merges.csv`, whether or not any event is
folded by them. `pre_cohort_activity_count` is the number of cleaned activity
events that belong to a cohorted account but fall in a period earlier than that
account's own cohort period; those events are counted here and are kept out of
the activity matrix.

`reconciliation.json` carries `study_id`, `cohort_size_residual`,
`revenue_residual_cents`, `weighted_revenue_residual_cents` and
`offset_zero_residual` and `control_value_residual_cents`.

`study_audit.json` carries `study_id`, `max_offset`, the sorted
`qualifying_event_types`, `activity_event_types` and `revenue_event_types` lists,
`minimum_value_cents`, the sorted `plan_weights` map and the sorted
`weight_overrides` map, which holds each segment code whose `weight_override` is
filled in, with that weight.

A per-cohort artifact is written for each of the first two cohorts in calendar
order, named `cohort_<period>.json`, each carrying `study_id`, `cohort`, `size`,
sorted `members`, `active_counts`, `retention_rates`, `survival_rates`,
`revenue_cents` and `weighted_revenue_cents`.
