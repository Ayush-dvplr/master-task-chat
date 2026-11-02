# Billing

Every order line with at least one deliveries row has one billing row, and all money is whole cents.

- `gross_cents` is the order line's total `billable` over the workload times its `unit_rate_cents`.
- `commission_cents` is `gross_cents * commission_bps / 10000` for the order line's advertiser, rounded half up to a whole cent once per order line. Commission is never computed on a sum of order lines.
- `credit_cents` is the number of the order line's `credited` make-good units times its `unit_rate_cents`. Placed units cost nothing in this close.
- `net_cents = gross_cents - commission_cents - credit_cents`, which may be negative.
