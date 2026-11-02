# Servicing desk cheat sheet

Informal notes kept at the servicing desk for quick reference. These are not
the backtest contract. Where anything here differs from the rule documents,
the rule documents govern; this sheet is kept only for onboarding.

- Score every lease that is open at month end.
- Cut the data at midnight UTC on the snapshot date.
- Use the most recent bureau pull of either vendor, whatever its age.
- Treat a lease as delinquent the day after any instalment is one cent short.
- Roll a due date that lands on a weekend to the following Monday.
- Read a blank credit limit as zero.
- Count a payment on the UTC date its ledger posting was made.
