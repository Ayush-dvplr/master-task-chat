# tariff

`tariff` rates the meter reads of a billing run into customer invoices.

    PYTHONPATH=src python3 -m tariff /path/to/data

The data directory holds `meter_reads.jsonl`, `accounts.csv`,
`billing_periods.csv` and `rate_card.json`. The command prints one JSON
document with an `invoices` list and an `exceptions` list. When one of the four
input files is missing it reports `missing input: <file name>` on standard error
and exits 2.

Each invoice carries one energy line per tier that covers some of a meter's
units, counted over the account positions of its meters in ascending order, and
one standing line per meter with active days, prorated over each calendar month
it touches. The account's allowance is shared in equal parts over its energy
lines. Accounts whose subtotal reaches their commitment receive the plan's
commitment credit. Every amount is a string with two decimals, rounded half to
even.

Run the unit tests with:

    PYTHONPATH=src python3 -m unittest discover -s tests -v
