# Domain calculation contract

## Inputs

All inputs are flat files in `/app/data`, and every transaction needs most of them.
Identifiers and dates are compared exactly as written.

- `transactions.csv`: `txn_id,customer_id,site,department,category,currency,amount_cents,tax_basis_cents,units,service_date,posted_date`.
  Amounts are integer cents in the transaction currency; credits are negative.
- `customers.csv`: `customer_id,customer_name,segment,discount_code`. Gives each
  transaction its `segment` and its `discount_code`.
- `discount_rules.json`: maps a `discount_code` to discount basis points.
- `regions.csv`: `site,region_name,site_adjustment_cents`. A transaction's region is the
  `region_name` of its site; the site also carries the per-site adjustment in cents.
- `tax_rules.json`: `default_tax_rate_basis_points`, `region_overrides_basis_points`
  (keyed by region name) and `site_overrides_basis_points` (keyed by site). The
  applicable tax rate is the site override when the site has one, otherwise the region
  override when the region has one, otherwise the default.
- `rate_table.csv`: `department,category,base_multiplier`, one row per (department,
  category) pair. The department multiplier of a transaction is the row matching both
  its department and its category.
- `fx_rates.csv`: `date,currency,rate_to_usd_basis_points`, one row per day per
  currency. A transaction converts at the row whose `date` is its `posted_date` and
  whose `currency` is its currency. A converted figure is
  `cents * rate_to_usd_basis_points / 10000`, rounded half up to whole cents.
- `calendar.csv`: `date,period,is_business_day`. The reporting period of a transaction
  is the `period` of its `posted_date`; a posted date the calendar does not list has
  period `unknown`. `is_business_day` is informational.
- `thresholds.json`: `minimum_net_cents`, `variance_alert_cents`,
  `quality_max_posting_lag_days`, and the `required_regions` and `required_segments`
  that get their own files. Transactions in other regions or segments still count in
  every report-wide figure.
- `policy.json`: carries the `report_id`.

Posting lag is the number of days from `service_date` to `posted_date`.

## Money figures

The three money figures each transaction contributes are defined in this exact order,
and every step rounds half up to whole USD cents before the next step uses it. The
`gross_cents` figure is `amount_cents` converted to USD cents. The `tax_cents` figure
is `tax_basis_cents` converted to USD cents, multiplied by the applicable tax basis
points over ten thousand. The `adjusted_net_cents` figure starts from gross plus tax,
then applies the customer discount as a `(10000 + discount_bps) / 10000` multiplier,
then applies the department multiplier to that discounted subtotal, then adds the
per-site adjustment cents, and finally takes the larger of that result and
`minimum_net_cents`. The site adjustment is added after the department multiplier,
and the minimum floor is applied last of all. Report and bucket totals sum these
per-transaction figures.

## Outputs

Every JSON artifact is serialized with sorted keys and a trailing newline. Money is
integer USD cents throughout.

`summary.json` carries `report_id`, `transaction_count`, `gross_cents`, `tax_cents`,
`adjusted_net_cents`, `department_totals`, `site_totals`, `category_units`,
`period_totals`, `largest_transaction`, `posting_lag_days` and `alerts`.
`department_totals`, `site_totals` and `period_totals` sum adjusted net cents keyed by
department, site and period; `category_units` sums `units` keyed by category.
`largest_transaction` has `txn_id` and `amount_cents`, selecting the greatest gross
figure and breaking ties on the lowest `txn_id`. `posting_lag_days` has `max` and
`average`, the average being Python's `round(mean, 2)` of the lags. Summary `alerts`
is a list, sorted by site, of `{"site", "delta_cents"}` objects, one for each site
whose adjusted net total minus its gross total is at least the variance alert
threshold in absolute value.

`policy_audit.json` echoes the rule tables the report was computed against:
`report_id`, `default_tax_basis_points`, `tax_regions` (the region override map),
`tax_sites` (the site override map), `discount_codes` (the discount map),
`department_multipliers`, `minimum_net_cents` and `variance_alert_cents`.
`department_multipliers` maps each department to a map of category to that row's
`base_multiplier`, reproduced as the identical text string in the `rate_table.csv`
cell (not a number): a cell of `1.050` is emitted as the string `"1.050"`.

`data_quality.json` carries `input_file_count` (regular files in the input
directory), `transaction_count`, `customer_count`, `region_count` (rows of
`regions.csv`), `quality_issue_count` and `quality_issues`. `quality_issues` is the
sorted list of issue strings. A transaction whose posting lag exceeds
`quality_max_posting_lag_days` raises `"<txn_id>: posting lag <n> days"`, and one
whose posted date is absent from `calendar.csv` raises
`"<txn_id>: posted date missing from calendar"`; one transaction can raise both.

Each `region_<name>.json` and `segment_<name>.json` describes one required region or
segment and carries `name`, `transaction_count`, `gross_cents`, `tax_cents`,
`adjusted_net_cents`, `department_totals`, `category_units`, `customers` and
`alerts`. `customers` is the sorted set of contributing customer ids. `alerts` is an
empty list, or a list holding the single object `{"name", "delta_cents"}` when the
bucket's adjusted net minus its gross is at least the variance alert threshold in
absolute value.
