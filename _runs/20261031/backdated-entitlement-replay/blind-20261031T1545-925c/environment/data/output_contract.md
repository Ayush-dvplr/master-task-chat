# Output contract

The program writes nine JSON documents into the output folder:
`summary.json`, `policy_audit.json`, `data_quality.json`, `region_North.json`,
`region_South.json`, `region_West.json`, `region_East.json`,
`segment_commercial.json` and `segment_public.json`. A region or segment file
is written even when it has no account.

## Form

Each document is JSON with an indent of 2 spaces, keys in the order listed
here, and one newline at the end. Every money amount is a string with exactly
two decimals, such as `"12.00"`. `anchor_day`, `quantity`, `candidates_fitting`
and every count are JSON integers. Dates are `YYYY-MM-DD` strings and
statement months are `YYYY-MM` strings.

## Account rows (region files)

`region_<region>.json` holds `region`, then `accounts`, then `totals`.
`accounts` lists every resolved account of that region that has a paid or open
invoice, by `account_id`. Each account row holds:

- `account_id`, `parent_id`, `segment`, `anchor_day`, `basis`
- `invoices`: one row per paid or open invoice, by `statement_month`, with
  `invoice_id`, `statement_month`, `status`, `original_total`,
  `corrected_total`, `credit_applied`, `paid`, `balance_due`
- `credits_issued`, `credits_expired`
- `transferred_in`, `transferred_out`: sums of the credit moved by accepted
  transfers into and out of the account
- `open_lots`: every lot open at window end, by `expires_on` and then
  `lot_id`, each with `lot_id`, `amount` (its remaining amount), `expires_on`
- `closing_credit`: the sum of the open lots

`totals` holds `original_billed`, `corrected_billed`, `credit_applied`,
`balance_due` (sums over the invoice rows of the file), and `credits_issued`,
`credits_expired`, `closing_credit` (sums over the account rows of the file).

## Segment files

`segment_<segment>.json` holds `segment`, `accounts_resolved` (the number of
account rows of that segment), `account_ids` (those accounts by `account_id`),
then the seven totals keys above, summed over those accounts.

## summary.json

`extract_id`, `accounts_total` (accounts in accounts.json),
`accounts_resolved` (account rows over all regions), `accounts_unresolved`,
`corrections_applied`, `corrections_rejected`, `invoices_rerated` (invoice
rows whose `corrected_total` differs from `original_total`), then the seven
totals keys summed over every account row.

## policy_audit.json

- `corrections`: every applied correction, by `effective_date`, then
  `account_id`, then `arrival_seq`, with `correction_id`, `account_id`,
  `item`, `quantity`, `effective_date`, `first_affected_statement_month`
- `transfers`: every accepted transfer in posting order, with `transfer_id`,
  `from_account`, `to_account`, `date`, `requested`, `moved`
- `expiries`: every expired lot, by `expires_on` and then `lot_id`, with
  `lot_id`, `account_id`, `expires_on`, `amount` (its remaining amount)

## data_quality.json

- `unresolved_accounts`: by `account_id`, with `account_id`, `reason`,
  `candidates_fitting`
- `rejected_corrections`: by `correction_id` and then `arrival_seq`, with
  `correction_id`, `account_id`, `reason`
- `rejected_transfers`: by `transfer_id`, with `transfer_id`, `reason`
- `void_invoices_ignored`: the `invoice_id` of every void invoice in
  invoice_register.tsv, in ascending order

## Errors

When a declared input file is missing, the program writes
`missing input: <file name>` to standard error and exits with status 2. When
a declared input file cannot be parsed, it writes `malformed input: <file
name>` to standard error and exits with status 2. In both cases it writes no
output document.
