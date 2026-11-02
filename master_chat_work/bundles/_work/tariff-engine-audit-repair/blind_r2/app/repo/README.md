# tariff

`tariff` rates the meter reads of a billing run into customer invoices,
following the tariff contract in `/app/ci/api_contract.md`.

    PYTHONPATH=src python3 -m tariff /path/to/data

The data directory holds `meter_reads.jsonl`, `accounts.csv`,
`billing_periods.csv`, `rate_card.json` and optionally `payments.csv`. The
command prints one JSON document with an `invoices` list (one invoice per
billing period row) and an `exceptions` list. When an input file is missing it
prints `missing input: <file name>` on standard error and exits 2.

Tiers are applied to the account's accepted units, meter by meter in meter
order. Each meter with active days gets one standing line, the sum over its
active days of the day's standing charge divided by the days in that day's
month. The allowance is shared over the energy lines. Every amount is a string
with two decimals, rounded half to even. An invoice whose subtotal reaches its
commitment receives the plan's commitment credit on that subtotal.

Run the unit tests with:

    PYTHONPATH=src python3 -m unittest discover -s tests -v
