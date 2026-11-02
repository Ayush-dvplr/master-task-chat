# tariff

`tariff` rates the meter reads of a billing run into customer invoices.

    PYTHONPATH=src python3 -m tariff /path/to/data

The data directory holds `meter_reads.jsonl`, `accounts.csv`,
`billing_periods.csv` and `rate_card.json`. The command prints one JSON
document with an `invoices` list and an `exceptions` list.

The engine follows the tariff engine contract (`/app/ci/api_contract.md`).
Each row of `billing_periods.csv` is its own invoice. Every meter of the
account gets one energy line per tier that covers some of its units (tiers
count account positions over meters in ascending order, caps inclusive) and
one standing line over its active days, each day costing the day's standing
charge divided by the days of its calendar month. The allowance is shared in
equal parts over the energy lines and any unshared rest carries to the
account's next invoice. Line amounts are rounded half to even to 0.01; when
the subtotal reaches the commitment the plan's credit rate applies. Reads
that cannot be billed are listed as exceptions sorted by `read_id`.

Run the unit tests with:

    PYTHONPATH=src python3 -m unittest discover -s tests -v
