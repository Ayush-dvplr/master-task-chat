# Transaction field dictionary

## tx_a.csv

Comma separated with a header row. `txn` is the transaction id, `day` the date (YYYY-MM-DD), `env` the envelope code, `cents` the magnitude of the amount in cents written as decimal digits, and `dir` the direction: `in` adds to the envelope and `out` takes from it.

## tx_b.tsv

Tab separated with a header row. `id` is the transaction id, `posted` the date (YYYY-MM-DD), `alias` the envelope alias, `amount` the magnitude in dollars written as decimal digits, a point and exactly two digits of cents, and `kind` the direction: `D` adds to the envelope and `S` takes from it.

## tx_c.bin

A binary export laid out in fmt_txc.md. Each record is one row of the export.

## stmt_fees.csv

Comma separated with a header row, one row per household, one row per funding code that some envelope carries and one row per category code that some envelope carries, in no particular order. `client_ref` is the household code (`hh_code` in hh_core.sqlite), the funding code or the category code, `through` the statement day (YYYY-MM-DD, the same on every row), and `charge_cents` the keeping charge in whole cents, written as decimal digits, that the bank counted on the opening balances of the household's envelopes or of the envelopes with the funding code or category code (std_ledger.md).

## adj_log.psv

Pipe separated with a header row. `seq` is the correction's sequence number (decimal digits), `txn` the transaction id it concerns, `action` either `void` or `amend`, and `value` the new magnitude in cents for an amend (decimal digits) and `-` for a void.
