# Billing terms

## Statement months and cycles

The window runs from `first_statement_month` to `last_statement_month` in
accounts.json, both included. Each account bills on its own anchor day A, a
whole number from 1 to 28. The billing cycle of statement month M starts on
day A of M and ends on the day before day A of the month after M. The invoice
for statement month M is issued on the first day of that cycle.

Each account also has one proration basis: `actual` or `thirty`.

## Quantities

The quantity of an item held on a day is the quantity of the latest event for
that account and item dated on or before that day, and 0 before its first
event. When several events for one account and item share a date, they take
effect in file order and the last one stands.

## Recurring lines

Each invoice carries one `recurring` line per item whose quantity on the cycle
start day is above 0, in item name order. Its quantity is that quantity and
its amount is quantity times the item's price. A quantity change dated on a
cycle start day is part of that cycle's recurring line in full and is never
prorated.

## Proration lines

The invoice for statement month M also carries one `proration` line for every
day D and item where the quantity on D differs from the quantity on the day
before, for each D strictly after the start of the previous cycle and before
the start of the cycle of M. The line's quantity is the new quantity minus the
old one (it can be negative). Its amount is

    price x (new quantity - old quantity) x remaining days / basis days

where remaining days counts the days from D (counted) to the start of the cycle
of M (not counted). Basis days is the number of days in the previous cycle for
basis `actual` and 30 for basis `thirty`. Proration lines follow the recurring
lines, ordered by D and then by item name.

## Rounding

Each line amount is rounded on its own to whole cents, half to even. The
invoice total is the sum of its rounded lines.

## Anchor day and basis of each account

Each account's anchor day and basis are recovered from its own paid invoices.
A candidate pair (anchor day, basis) fits an account when rating that
account's entitlement events, without any correction, under that pair
reproduces every recorded line of every paid invoice of the account: the same
kind, item, quantity and amount, in `line_no` order. Open and void invoices
are not evidence. There are 56 candidate pairs (anchor days 1 to 28, each with
either basis).

An account is resolved when exactly one candidate pair fits, and it then bills
under that pair in every document. Otherwise the account is unresolved, with
reason `anchor_none` when no pair fits or `anchor_ambiguous` when more than one
fits, and `candidates_fitting` set to the number of pairs that fit. An
unresolved account appears only in data_quality.json.
