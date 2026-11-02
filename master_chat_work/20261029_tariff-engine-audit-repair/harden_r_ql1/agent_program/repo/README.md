# tariff

`tariff` rates the meter reads of a billing run into customer invoices, using
the Python standard library only.

    PYTHONPATH=src python3 -m tariff /path/to/data

The data directory holds `meter_reads.jsonl`, `accounts.csv`,
`billing_periods.csv` and `rate_card.json`, and optionally `payments.csv` and
`vouchers.csv`. The command prints one JSON document with an `invoices` list
and an `exceptions` list; with `--statements` it prints the voucher statements
of the accounts in `vouchers.csv` instead.

Each row of `billing_periods.csv` is billed as its own invoice. A meter carries
one energy line per plan tier its units reach, counted from the account's first
unit over its meters, and one standing line prorated day by day over the days
of each day's own calendar month. An invoice whose subtotal reaches its
commitment receives the plan's commitment credit.

Run the unit tests with:

    PYTHONPATH=src python3 -m unittest discover -s tests -v
