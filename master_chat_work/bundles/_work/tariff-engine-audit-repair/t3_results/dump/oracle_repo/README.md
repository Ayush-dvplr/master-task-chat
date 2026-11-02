# tariff

`tariff` rates the meter reads of a billing run into customer invoices.

    PYTHONPATH=src python3 -m tariff /path/to/data

The data directory holds `meter_reads.jsonl`, `accounts.csv`,
`billing_periods.csv` and `rate_card.json`. The command prints one JSON
document with an `invoices` list and an `exceptions` list.

Each invoice carries one energy line per tier a meter reaches and one
standing line per meter, prorated per calendar month over
its active days. Accounts whose
subtotal of accepted lines reaches their commitment receive the plan's commitment
credit.

Run the unit tests with:

    PYTHONPATH=src python3 -m unittest discover -s tests -v
