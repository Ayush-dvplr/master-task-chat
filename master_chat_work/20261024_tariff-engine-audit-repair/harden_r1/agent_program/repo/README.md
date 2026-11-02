# tariff

`tariff` rates the meter reads of a billing run into customer invoices.

    PYTHONPATH=src python3 -m tariff /path/to/data

The data directory holds `meter_reads.jsonl`, `accounts.csv`,
`billing_periods.csv` and `rate_card.json`. The command prints one JSON
document with an `invoices` list and an `exceptions` list. When an input file
is missing it prints `missing input: <file name>` on standard error and exits
2.

Each invoice carries one energy line per tier a meter reaches and one
standing line per meter, prorated over the days of the account's billing
period. Accounts whose invoice subtotal reaches their commitment receive the
plan's commitment credit. Every amount is a two-decimal string rounded half
to even.

Run the unit tests with:

    PYTHONPATH=src python3 -m unittest discover -s tests -v
