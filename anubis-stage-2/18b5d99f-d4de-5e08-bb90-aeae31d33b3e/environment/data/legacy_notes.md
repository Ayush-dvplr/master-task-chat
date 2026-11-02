# Legacy engine notes

The desk replaced its legacy rating engine without recording two of its rules: the
withdrawal rule and the standing rule. Each has the form set out below. Both rules are
the same in every extract in this layout, and neither depends on the premium floor.
Every line of the two closing journals named by the rules file is what the legacy
engine produced, and each journal is complete for the accounts it lists.

## The cancellation table

The legacy engine kept one cancellation table per extract. For every ordered pair of
two different kinds listed by the rules file, the table says whether a void row of the
first kind may withdraw a row of the second kind. A void row may always withdraw a row
of its own kind. The table is not symmetric in general: that a void of one kind may
withdraw a row of another kind says nothing about the reverse pair.

## The withdrawal rule

When a void row is processed, the rows it may withdraw are the rows of its booked
account that are live at that moment and whose kind the cancellation table lets the
void row's kind withdraw. When there is no such row, the void row withdraws nothing.
Otherwise it withdraws the first of them in a fixed ranking.

The ranking either takes all of these rows together, or splits them into two groups,
the rows of the void's own kind and the rows of other kinds, and ranks every row of one
group ahead of every row of the other. The rows taken together, or the rows of each
group, are ordered by at most one measure, larger first or smaller first, and then by
position, earlier first or later first. A measure is one of the row's metered charge
(rate_card.md), its amount, its units and its kind weight. The two groups may use
different measures and directions. The position of a row is its place in the
processing order of its account's rows.

## The standing rule

The standing rule judges every account that has at least one ordinary processed row.
For such an account let `O` be its number of ordinary rows (live or withdrawn), `L` its
number of live ordinary rows, `U` its unwaived total, `W` its waivable penalty and `C`
its carried total (scoring_rules.md), and let `f` be the floor.

An account passes against a set of accounts when its count `n` is above zero and its
total is at least, or strictly above, `f * n`. The count `n` is `O` or `L`. The total
is `U`; or `C`; or `U + W` when the account's sponsor is in the set and `U` otherwise.
When the total does not depend on the set, the accounts that pass hold premium
standing. When it does, the premium set is a set of accounts that equals the set of
accounts passing against it: either the smallest such set, reached from the empty set,
or the largest, reached from the set of every judged account, by testing every account
against the current set until the set no longer changes. A missing sponsor, or a
sponsor that is not a judged account, is never in a set.

## The journals and their period

Each journal covers a past period of the extract that carries it. That period was rated
with the same kinds, kind weights and cancellation table as the extract, with the
withdrawal rule and the standing rule, and with the extract's rules file values
`region_offsets`, `flag_penalties` and `latency_quantum`, with two differences: the
premium floor of the period was 2000, and no carry passed between rows, so the carried
value of every row of the period equals its base value (scoring_rules.md). The rows of
one account never affect the rows of another account except through sponsors.

Both journals list rows, one row per line, with cells as rated (already booked to their
account and amended). Control rows are rated with amount 0 and units 0, as in
ledger_rules.md, whatever their cells show. The `line` column numbers the lines of the
file and plays no part in any rule. The rows of one account are taken in the account's
processing order: ascending `ts`, and rows that share a `ts` in ascending order of the
integer written after the letter of their `row` id (ledger_rules.md).

### The withdrawal journal

The withdrawal journal (`withdrawals_journal_file`) lists, for each account of the
period it covers, every processed row booked to that account. Its columns:

- `line`: the line number.
- `account`: the booked account.
- `ts`: the row's stamp.
- `row`: the row id.
- `kind`, `amount`, `units`, `flag`: the row's cells as rated.
- `state`: for an ordinary row, `live` when the row was live at the close of the period
  and `withdrawn` otherwise; for a control row, `applied` when it withdrew or restored a
  row and `orphan` when it did nothing.

### The standing journal

The standing journal (`standing_journal_file`) lists every processed row of a second
past period, for every account of that period. Every account it lists has at least one
ordinary row. Its columns:

- `line`: the line number.
- `account`: the booked account.
- `sponsor`: the account's sponsor, already followed through merges; empty when the
  account has none. It is the same on every line of the account.
- `ts`, `row`: the row's stamp and id.
- `region`: the billing region of the account.
- `kind`, `amount`, `units`, `flag`: the row's cells as rated.
- `latency_ms`: the row's latency in whole milliseconds.
- `standing`: `premium` or `standard`, the standing the legacy engine gave the account
  at the close of the period, the same on every line of the account.
