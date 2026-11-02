# Amendments

Billing operations issue errata after a workload is captured. The errata file named by
`errata_file` holds one JSON object per line. Errata change cell values of rows before
the rows are rated. They never change a row's id, ts, written account, region, kind or
latency, and they never name a control row (ledger_rules.md).

## Entries

Every entry has an `erratum` id: `ER-` followed by decimal digits. The number of an
entry is the integer those digits write, and no two entries share a number. A smaller
number means the entry was issued earlier. A withdrawal entry's `reverts` names an
amendment by its id exactly as the amendment writes it.

An amendment entry also carries `booked_account`, `ts`, `field` and `value`. `field` is
`amount`, `units` or `flag`, and `value` is the new cell text. A flag set by an
amendment is always an ordinary flag.

A withdrawal entry carries only `erratum` and `reverts`, the id of an amendment entry.

## Which row an amendment names

An amendment names its row by the account the row is booked to (identity_rules.md) and
the row's `ts`, never by row id and never by the account written on the row. Every
amendment matches at most one row of a workload. An amendment applies to the matching
row of every workload that has one, and does nothing in a workload that has none.

## Net state

Only the net state of the errata file counts. An amendment that any withdrawal entry
names has no effect at all, wherever the withdrawal entry sits in the file, before or
after the amendment. Every other amendment is in effect. Amendments in effect that set
different fields of one row all apply.

Billing freeze: when more than one amendment in effect sets the same field of the same
row, the amendment issued first (the smallest erratum number) governs that field, and
every later amendment of that field is void.

## Pricing through amendments

An amendment of `amount` whose `value` is empty leaves the row's amount empty, so the
row is unpriced (ledger_rules.md). An amendment that gives an amount to a row whose
written amount is empty prices that row, and it is processed like any other row.

## Amended rows

A processed row is amended when at least one amendment in effect names it. The amended
rows list of a workload holds one entry per amended processed row, in processing
order: a two-element list of the row id and the row's final value (scoring_rules.md).
