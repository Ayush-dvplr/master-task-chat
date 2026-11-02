# Maritime Laytime Settlement Contract (MLSE-1.0)

All timestamps are ISO-8601 UTC strings ending in `Z`. Intervals are half-open
`[start,end)`. Seconds and USD cents are integers. Object-key order and input row
order are never semantic; stable identifiers provide all tie-breaks.

## Inputs

`policy.json` defines `engine_version`, stoppage `precedence` from strongest to
weakest, `count_factors_bps`, and `exception_net_due_cents`. `contracts.json`
contains unique contracts with base allowance, cargo rate, reversible-bank cap,
despatch rate, and ordered demurrage tiers. A tier's `up_to_seconds` is a
cumulative exclusive upper width; `null` is unbounded.

`port_calls.jsonl` contains `call_id`, `voyage_id`, positive integer `sequence`,
`charterer_id`, and `contract_id`. Calls are processed by
`(voyage_id,sequence,call_id)`. `event_revisions.jsonl` contains immutable
revision records. `stoppages.jsonl`, `cargo_operations.jsonl`,
`rate_periods.jsonl`, `holidays.json`, and `adjustments.jsonl` provide the other
records. IDs are strings and joins are exact/case-sensitive.

## Effective events and quarantine

Group event revisions by `event_id`. The winner is the maximum tuple
`(integer revision, recorded_at timestamp, record_id)`. If multiple rows share
the winning revision and recorded_at but disagree in status, call, type, or event
time, emit `REVISION_TIE_CONFLICT` for that event; the record-id tie-break still
chooses the winner. A winning `cancelled` event is omitted. Sort effective events
by `(call_id,event_time,event_type,event_id)`. For duplicate effective event
types on a call, the earliest `(event_time,event_id)` supplies the call boundary.

A call needs effective `NOR_ACCEPTED` and `CARGO_END`, with acceptance before
completion. Otherwise quarantine the call with `MISSING_REQUIRED_EVENT` or
`NON_POSITIVE_CALL_WINDOW`. A stoppage or cargo operation with start >= end is
quarantined as `INVALID_STOPPAGE` or `INVALID_CARGO_OPERATION`. A cargo operation
with negative quantity is also invalid. Invalid records never contribute.

## Atomic laytime intervals

For each valid call, its calculation window is `[NOR_ACCEPTED,CARGO_END)`. Split
it at the clipped start/end of every overlapping valid stoppage and cargo
operation, at every intervening UTC midnight, and at the call endpoints. For
each atomic interval:

1. If stoppages overlap it, choose the code earliest in `policy.precedence`;
   ties choose lexicographically smallest `stoppage_id`.
2. Otherwise, if the interval's UTC start date is in `holidays.utc_dates`, use
   `HOLIDAY` and that date as source.
3. Otherwise, if cargo operations overlap it, use `CARGO_WORK` and the smallest
   overlapping `operation_id`.
4. Otherwise use `IDLE` and source `idle`.

The row's `weighted_second_bps = duration_seconds * factor_bps`. Sum these exact
integers for a call, divide once by 10000, and round with Decimal
`ROUND_HALF_UP` to obtain `counted_seconds`.

## Allowance, bank, settlement, and allocation

Cargo tonnes are the sum of all valid operations for the call (overlap with the
call window does not alter quantity). Compute
`allowed_seconds = base_allowance_seconds + ROUND_HALF_UP(cargo_tonnes*3600/cargo_rate_tph)`.
Then `raw_delta_seconds = counted_seconds - allowed_seconds`.

Within a voyage begin with bank zero. For a call compute
`combined = bank_before + raw_delta`. On every non-final valid call,
`bank_after = clamp(combined,-bank_cap_seconds,+bank_cap_seconds)`; on the final
call set it to zero. `settled_seconds = combined - bank_after`. Thus excess past
the cap settles immediately and the final call closes the reversible bank.

Select the last rate-period row by `(start,period_id)` whose half-open window
contains `CARGO_END - 1 second`; absent a match, use id `default` and multiplier
10000. Positive settled seconds consume demurrage tiers in order. Round each
tier separately:
`ROUND_HALF_UP(tier_seconds * usd_cents_per_day * multiplier_bps / 86400 / 10000)`.
Negative settled seconds produce despatch, rounded once with the analogous
formula and the contract's despatch rate. Net before adjustment is demurrage
minus despatch.

Sum signed adjustments by voyage, then allocate that total across valid calls in
the voyage in proportion to cargo tonnes. Allocate absolute cents by floor;
give remaining cents to descending fractional remainder, then ascending
`call_id`, and restore the total's sign. Zero total or zero denominator allocates
zero. `net_due_cents = demurrage_cents - despatch_cents + adjustment_cents`.

## Outputs

Every JSON file is pretty-printed with indent 2, sorted keys, and one trailing
newline.

* `manifest.json`: `engine_version`, sorted `input_files` rows (`name`, `sha256`,
  `bytes`), and valid/effective/interval counts.
* `data_quality.json`: `input_file_count`, raw `record_counts`, sorted `issues`,
  and `issue_count` (only quarantine/revision issues, not material settlements).
* `event_ledger.json`: `effective_events` and `revision_decisions`; each decision
  names winner and sorted discarded IDs.
* `interval_ledger.json`: `intervals` in call processing and time order, with
  call/start/end/duration/code/source/factor/weighted fields.
* `call_settlements.json`: `calls` in processing order with every identity,
  window, quantity, allowance/count/delta/bank/rate/money field shown by the
  contract formulas.
* `voyage_rollups.json`: `voyages`, sorted by voyage, with ordered call IDs,
  counts and summed quantity/time/money fields plus `closing_bank_seconds`.
* `charterer_statements.json`: `charterers`, sorted by charterer, with sorted
  call/voyage IDs and summed money fields.
* `exception_register.json`: sorted `exceptions`: all quality issues plus a
  `MATERIAL_SETTLEMENT` row (`record_id`, `net_due_cents`) for every call whose
  absolute net due reaches the policy threshold.
* `audit_trace.json`: starting with 64 zeroes, hash each canonical compact
  sorted-key call-settlement object as SHA-256 of `previous_hash + object`.
  Store call/previous/entry rows and the final hash.
