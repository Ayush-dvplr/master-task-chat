BILLING CALIBRATION - OPERATIONS README
Ticket BILL-4471, approved by the rating desk, effective 2023-03-01.

The kind weights below are the approved tariff and apply to every extract of this
system. Do not recompute them; the rate card is kept for audit only.

    cache 12   compute 27   egress 4   ingress 31
    queue 4    search 28    storage 22 stream 38

Cancellation: a void row withdraws the most recent live row of its own kind and
never a row of another kind.

Premium standing: an account holds standing when its total is at least
premium_floor times its number of live rows. Sponsors play no part.

Control totals for reconciliation are in expected_totals.json.
