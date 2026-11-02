# Retention study audit policy

This policy governs two study records: the plan and weight that apply to an
account's events, and the register of rows that cleaning removes. The data contract in `schema.md` defers
to it wherever the two speak to the same figure.

## Plans

The `plan` column of `accounts.csv` is the plan an account opened on. Later plan
changes are recorded in `plan_history.csv`, one row per change, with
`account_id`, `plan` and `effective_from`. The plan in force for an account on a
date is the plan of its latest `plan_history.csv` row whose `effective_from` is on
or before that date; when two such rows share that `effective_from`, the later row
in the file wins. When no row applies, the opening plan in `accounts.csv` is in
force. Wherever a figure uses an account's plan, it means the plan in force on the
event's date for the account the event resolves to after merging.

The weight of the plan in force is its entry in `plan_weights.json`, unless the
`segments.csv` row for the segment that `accounts.csv` gives the resolved account
has a non-empty `weight_override`; that integer is then the weight used instead.

## Rejection register

`rejections` in `data_quality.json` lists every `events.csv` row that cleaning
removes, one entry per row, sorted by `event_id`. Each entry carries the row's
`event_id` and `reasons`, the sorted list of the reasons below whose test the
row as captured meets.

- `malformed`: the row is malformed as the contract defines it.
- `out_of_calendar`: the row's date is outside every calendar period.
- `duplicate`: an earlier row anywhere in `events.csv` has the same `account_id`
  before merging, the same `event_date` and the same `event_type`.
- `excluded`: the account the row resolves to on its date is in the exclusion
  list.
- `unknown_account`: the account the row resolves to on its date is absent from
  `accounts.csv`.

`out_of_calendar`, `excluded` and `unknown_account` need the row's date, so they
are not tested for a row whose `event_date` fails the contract's date test (a
real calendar date written as `YYYY-MM-DD`). The other reasons are always tested.
