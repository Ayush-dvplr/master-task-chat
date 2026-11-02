# tariff

`tariff` rates the meter reads of a billing run into customer invoices.

    PYTHONPATH=src python3 -m tariff /path/to/data

The data directory holds `meter_reads.jsonl`, `accounts.csv`,
`billing_periods.csv` and `rate_card.json`. The command prints one JSON
document with an `invoices` list and an `exceptions` list.

Each invoice carries one energy line per tier a meter's units reach (tiers
count units across the account's meters) and one standing line per meter,
each active day charged at the standing charge / days in that day's month.
An invoice whose subtotal of accepted, rated, prorated lines reaches its
commitment receives the plan's commitment credit.

    PYTHONPATH=src python3 -m tariff --statements /path/to/data

prints the voucher statements of the accounts in `vouchers.csv`.

Run the unit tests with:

    PYTHONPATH=src python3 -m unittest discover -s tests -v
