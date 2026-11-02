# Record dictionary and report layout

This extract comes from the usage rating desk of a metered cloud service. It holds
five scenario workloads of usage rows, the rules file they are rated with, and the
identity, merge, amendment and rate card files and the two closing journals of the
retired legacy rating engine that the rules file names. The rules are spread over
these documents, organised by subsystem:

    amendments.md           errata entries, their net state, pricing by amendment
    identity_rules.md       governing records, merges, booking, billing region, sponsor
    ledger_rules.md         row classes, processing order, withdrawals, totals, quality figures
    legacy_notes.md         the cancellation table, the two legacy engine rules, the journals
    performance_contract.md speed target, baseline row scans, perf_report.json
    rate_card.md            the kind weights, metered charges and the published batch figures
    scoring_rules.md        base, carried and final values, waivers, checksum, ranking, metrics

This file is the record dictionary (the meaning of the files, columns and record
classes) and the report layout (the keys and byte form of every report).

## Files of the extract

`manifest.json` names the rules file (`rules`) and the scenario workloads
(`scenarios`, a list of objects with `name` and `source`). Scenario names and their
files come from the manifest, never from file names. The shipped manifest lists the
scenarios visible, peak, steady, burst and latency.

The rules file (`rules.json` in the shipped extract) holds `label`, `kinds`,
`region_offsets`, `flag_penalties`, `carry_modulus`, `latency_quantum`,
`premium_floor`, `top_n` and eight file keys, each a file name relative to the folder
that holds the rules file: `registry_file`, `export_file`, `merges_file`,
`errata_file`, `rate_card_file`, `rate_figures_file`, `withdrawals_journal_file` and
`standing_journal_file`.

The two journal files are the legacy engine's closing journals (legacy_notes.md). They
belong to a past period and are not part of any workload.

Every file is UTF-8 text. CSV files have a header row.

## Workload rows

A workload file has the columns `id`, `ts`, `account`, `region`, `kind`, `amount`,
`units`, one latency column and `flag`. A workload file may begin with a UTF-8
byte-order mark, which is not part of the first column name.

The capture sites write some cells loosely. Before any rule reads a workload row, its
`account` cell loses surrounding spaces and has its letters upper-cased, and its `kind`
and `flag` cells lose surrounding spaces and have their letters lower-cased. Every rule
reads these normalised cells, including the comparison of a row's booked account with
the account written on it, and every report and result object carries the normalised
values. No other file of the extract is
normalised.

- `id` is one lowercase letter followed by decimal digits, with no fixed width. No two
  rows of a workload share an id or the integer written after its letter.
- `ts` is an integer stamp. `units` is an integer. `amount` is an integer or empty.
- `account` is the account written on the row. The account a row is booked to can
  differ from it (identity_rules.md).
- `region` names the edge site that captured the row. It plays no part in any value,
  total or region key; the region that rates a row is its billing region
  (identity_rules.md).
- `kind` is one of the kinds listed by `kinds` in the rules file.
- `flag` is `void`, `revive` or an ordinary flag (any other text).

The latency column's name declares its unit. A `latency_ms` column holds whole
milliseconds. A `latency_us` column holds microseconds; the row's latency in whole
milliseconds is the microsecond value divided by 1000 and rounded to the nearest whole
millisecond, an exact half (a remainder of exactly 500 microseconds) rounding up. Every rule that
uses a latency uses the latency in whole milliseconds.

Other extracts in this layout use the same columns and kinds of files, with their own
names, accounts, regions, kinds, flags, rate cards, closing journals and rules
values.

## Carry chain

The chain rows are the ordinary rows that are processed (ledger_rules.md). Control
rows are not chain rows: a control row takes no carry, leaves none, and its carried
value is its base value.

The chain rows divide into one chain per billing region. The chain of a chain row is
the billing region of its booked account (identity_rules.md), and the chain row before
it is the previous chain row of the same billing region in processing order
(ledger_rules.md). A chain row of one region never takes a carry from a row of another
region. The carried value itself is defined in scoring_rules.md.

## Report layout

Every JSON report is written as UTF-8 text in one exact form: two-space indentation,
keys in ascending order at every level, the separators `, ` and `: ` that this
indentation implies with no trailing space at a line end, ASCII escapes for any
non-ASCII character, and a single newline after the closing brace. This is the form
Python's `json.dumps(value, indent=2, sort_keys=True)` produces, followed by one
newline. Every number in every report is an integer except where a field below says
otherwise. Lists of objects follow the manifest order of scenarios.

### The result object

`aggregate` returns, and the command line prints, an object with exactly these keys:

- `label`: text, the rules file's `label`.
- `event_count`: integer, the event count (ledger_rules.md).
- `account_totals`: object, account to integer, the account totals (ledger_rules.md).
- `region_totals`: object, billing region to integer, the region totals (ledger_rules.md).
- `kind_totals`: object, kind to integer, the kind totals (ledger_rules.md).
- `flag_counts`: object, flag to integer, the flag counts (ledger_rules.md).
- `premium_accounts`: list of account texts in ascending text order, the accounts that
  hold premium standing (scoring_rules.md).
- `top_accounts`: list of two-element lists `[account, total]`, the ranking
  (scoring_rules.md).
- `checksum`: integer, the checksum (scoring_rules.md).

### scenario_<name>.json

One file per scenario, at `/app/out/scenario_<name>.json` for the names visible, peak,
steady, burst and latency, with exactly four keys: `scenario` (the manifest name),
`source` (the manifest source file name), `result` (the result object for that
workload) and `metrics`, an object with exactly `total_score`, `average_score`,
`top_account` and `top_account_score`, the scenario metrics of scoring_rules.md.
`top_account` is text or null.

### data_quality.json

Exactly one key, `scenarios`: a list with one object per scenario, each with exactly
`scenario`, `unpriced_rows`, `unregistered_rows`, `rebooked_rows`, `orphan_voids`,
`orphan_revives` and `cancelled_score` (the data quality figures of ledger_rules.md)
and `amendments`, the amended rows list of amendments.md: a list of two-element lists
`[row id, final value]` in processing order.

### recommendations.json

Exactly one key, `scenarios`: a list with one object per scenario, each with exactly
`scenario`, `rescued_accounts` (list of account texts in ascending text order, the
rescued accounts of scoring_rules.md) and `waived_penalty` (integer, the waived
penalty of scoring_rules.md).

### bottleneck_analysis.json

Exactly one key, `scenarios`: a list with one object per scenario, each with exactly
`scenario`, `group_keys`, `processed_rows` and `baseline_row_scans`, the figures named
in performance_contract.md.

### perf_report.json

The fields defined in performance_contract.md.
