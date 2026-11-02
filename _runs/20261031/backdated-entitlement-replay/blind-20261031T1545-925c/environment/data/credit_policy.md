# Credit policy

## Credit lots

Credit is held in lots. A lot can be used on a day when its `created_on` is on
or before that day, the day is before its `expires_on`, and it has a remaining
amount above 0. Lots of accounts that are unresolved or missing from
accounts.json are ignored.

## Posting order

Activity is posted day by day. On one date, all transfers of that date are
posted first, in log order, and then the invoices issued that date, in
account_id order.

## Invoices and payments

When an invoice is issued, the account's usable credit is applied to its
corrected total, lot by lot: the lot with the earliest `expires_on` first and,
among equal dates, the lowest `lot_id`. `credit_applied` is the amount taken
and the amount due is the corrected total minus `credit_applied`.

`paid` is the sum of every PAYMENT line in ledger_activity.log for that
invoice, and 0 when it has none. When `paid` exceeds the amount due, the
excess becomes a new lot of the account with `lot_id` `<invoice_id>-OP`,
created on the issue date and expiring on the account's anchor day of the
statement month N months after the invoice's statement month, where N is
`credit_expiry_cycles` in legacy_terms.yaml. `balance_due` is the amount due
minus `paid`, and 0 when that is negative. `credits_issued` is the sum of an
account's overpayment lots.

## Transfers

A TRANSFER line moves credit from one account to another on the date of its
timestamp. A transfer is rejected with the first of these reasons that
applies:

1. `unknown_account`: either account is not in accounts.json.
2. `different_parent`: the two accounts have different `parent_id`.
3. `account_unresolved`: either account is unresolved.

An accepted transfer moves the requested amount or, when the sender's usable
credit at that point of posting is smaller, all of that credit. The credit is
taken from the sender's lots in the order credit is applied to invoices. Each
piece taken from one sender lot becomes a receiver lot with `lot_id`
`<transfer_id>-<k>` (k counts the pieces from 1), created on the transfer
date, with the sender lot's `expires_on`. The `posted=` figure on a TRANSFER
line is not used.

## Expiry and closing credit

The window ends on the day before the account's cycle start in the month after
`last_statement_month`. A lot with a remaining amount above 0 whose
`expires_on` is on or before that day has expired: it is listed in the
expiries of policy_audit.json and counted in `credits_expired`. Every other lot
with a remaining amount above 0 is open at window end and counted in
`closing_credit`.
