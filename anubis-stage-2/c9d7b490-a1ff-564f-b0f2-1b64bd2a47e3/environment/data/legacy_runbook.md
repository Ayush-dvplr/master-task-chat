# Scorecard backtest runbook (2023 edition)

Status: retired. This runbook was replaced by the rule documents of this
extract when the 2024 backtest process was approved. It is kept only because
the 2023 audit file refers to it. Nothing in it governs this backtest; where
it differs from the rule documents, the rule documents apply.

## How the 2023 backtest was run

1. Take every lease open at month end and score it with the current champion.
2. Cut the data at midnight UTC on the snapshot date.
3. Use the servicing ledger for every payment, dated by the UTC date of
   `posted_at`.
4. Use the most recent bureau pull of either vendor, whatever its age.
5. Count a lease as delinquent from the day after any instalment is short by
   one cent or more.
6. Roll every due date that falls on a weekend to the following Monday.
7. Score merged customers under the customer id on the lease.
8. Label a lease bad when it is 60 days past due at any time in the next six
   months, using the data as it stood on the day of the backtest.
9. Report the Gini coefficient to two decimals.
