# Ledger rules

This file defines the classes of rows in a workload, the order processed rows are
taken in, how control rows withdraw and restore rows, and the totals and data quality
figures formed from the rows that remain live. Row values are defined in
scoring_rules.md, bookings and billing regions in identity_rules.md, and amended cells
in amendments.md.

## Row classes

The event count of a workload is the number of its data rows, whatever happens to
them afterwards.

An unregistered row is a row whose booked account is unregistered (identity_rules.md).
An unpriced row is a row of a registered booked account whose amount, after
amendments, is empty. Unregistered and unpriced rows are rejected: they take no
position, carry nothing and appear in no total, and they are counted only in the event
count and in their own data quality figure. Every other row is a processed row.

A processed row whose flag is `void` or `revive` is a control row. Every other
processed row is an ordinary row. A control row is rated with amount 0 and units 0,
whatever its `amount` and `units` cells hold: every rule that uses a control row's
amount or units uses 0. The rejection rules above still read the cells, so a control
row whose amount is empty is an unpriced row like any other.

## Processing order

Processed rows are taken in ascending `ts`. Rows that share a `ts` are taken in
ascending order of the integer written after the letter of their id. The position of a processed row is its one-based place in this order.
Control rows hold positions like any other processed row. The order of lines in the
file plays no part.

## Live rows, withdrawals and restorations

Each ordinary row becomes a live row of its booked account when it is processed.

A void row withdraws at most one live row of its booked account at the moment it is
processed. Which row it withdraws is set by the cancellation table of the extract and
the withdrawal rule of the legacy engine (legacy_notes.md). A void row that withdraws
nothing is an orphan void.

A revive row restores the most recent withdrawal still outstanding on its booked
account: the row withdrawn last among that account's withdrawn rows that are not yet
restored, whatever its kind. The restored row is live again in its original position,
so a later void can withdraw it again. A revive row that finds no outstanding
withdrawal on its booked account is an orphan revive and restores nothing.

Withdrawals and restorations change only which rows are live. They never change a
row's value, carry, position or checksum term.

## Result totals

A row is live at the end when it is live after the last processed row.

The account totals have one entry per booked account that has at least one ordinary
row: the sum of the final values of its rows that are live at the end, or 0 when none
is.

The region totals have one entry per billing region that has at least one ordinary
row, and the kind totals one entry per kind that has at least one ordinary row, each
the sum of the final values of the live ordinary rows in it, or 0.

The flag counts have one entry per flag that at least one ordinary row carries,
counting that flag's ordinary rows that are live at the end (0 when none is), plus one
entry for `void` and one for `revive` counting every processed control row of that
flag, orphans included, when there is at least one.

## Data quality figures

`unpriced_rows` and `unregistered_rows` count the rejected rows of each class.
`rebooked_rows` counts the processed rows whose booked account differs from the account
written on the row. `orphan_voids` and `orphan_revives` count the orphan control rows.
`cancelled_score` is the sum of the final values of the ordinary rows that are not live
at the end.
