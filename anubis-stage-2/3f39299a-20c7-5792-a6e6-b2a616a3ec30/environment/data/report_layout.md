# Report layout

This document gives the shape of each report: its keys and their types, the order of every list,
the number forms and the byte form. What each field means is the rule it names, in the document
named beside it.

## Byte form

Every report is a JSON document written as UTF-8, with two-space indentation, keys sorted at every
level, only ASCII characters (anything else escaped), and exactly one newline after the closing
brace. That is precisely the text Python's `json.dumps(document, indent=2, sort_keys=True)`
produces, followed by a single newline character.

Quantities are whole kg, written as JSON integers. Week ids are the `week_id` values of the season
calendar; depot codes, customer ids, order ids and purchase order numbers are written as in the
record files. "Calendar order" means the order of the season calendar's rows. Decimal parameters
are strings with exactly two decimal places.

## Which reports carry full content

All nine reports are written for every extract: `summary.json`, `policy_audit.json`,
`data_quality.json`, the four regional reports `region_North.json`, `region_South.json`,
`region_West.json` and `region_East.json`, and the two segment reports `segment_commercial.json`
and `segment_public.json`. The first three always carry their full content.

A regional report is in scope when at least one depot of its region had at least one rationed
depot-week during the season. A segment report is in scope when at least one entry of rationed
allocations (Segment reports, below) belongs to a customer of that segment.

A regional or segment report that is in scope carries the full layout below, including
`"in_scope": true`. A report that is out of scope carries exactly two keys: its `region` (or
`segment`) name and `"in_scope": false`.

## summary.json

- `depots`: list, one object per depot, sorted by depot code. Keys: `depot`, `region`,
  `opening_kg`, `receipts_kg` (receipts that became part of the depot's stock), `delivered_kg`,
  `closing_kg` (stock carried out of the last week), `rationed_weeks` (list of the week ids of
  the depot's rationed depot-weeks, calendar order). lot_ledger.md, Stock carried between weeks;
  allocation_policy.md, Rationed and unrationed depot-weeks.
- `weeks`: list, one object per week, calendar order. Keys: `week`, `receipts_kg`,
  `delivered_kg`, `lapsed_kg`, `withdrawn_kg`, `rationed_depots` (integer count),
  `unsettled_depots` (integer count of unsettled depot-weeks). Every figure is summed over all
  depots for that week's allocation. lot_ledger.md; allocation_policy.md, Review rounds.
- `true_up`: list, one object per public customer owed a true-up credit, sorted by customer id. A
  customer is listed only when its credit is above zero; nobody is listed with a credit of 0.
  Keys: `customer_id`, `contract_min_kg`, `delivered_kg` (the season delivered quantity of the
  true-up), `credit_kg`. allocation_policy.md, Season true-up.

## policy_audit.json

- `carrier_settings`: list, one object per carrier named in the extract's `carrier_calibration.json`,
  whether or not it delivered any receipt, sorted by carrier name. Keys: `carrier` (as written in
  the calibration file), `unit` (`short_ton`, `metric_tonne` or `long_ton`), `moisture_deduction`
  (integer) and `rounding` (`half_up`, `down` or `up`): the carrier's weighbridge settings at the
  close of the season.
  source_authority.md, Weighbridge settings and credited receipts.
- `parameters`: list, one object per week, calendar order. Keys: `week`, `version_id` (string,
  the `version_id` of the last version taken into account, in the order allocation_policy.md
  gives, for the week's allocation instant, or null when there is none) and the eight parameters of allocation_policy.md under their own
  names, as in force at the week's allocation (whole-number parameters as integers, decimals as
  strings, the other two as their names).
- `rationing_events`: list, one object per rationed depot-week, sorted by week in calendar order
  and then by depot code. Keys: `depot`, `week`, `available_kg`, `demand_kg` (total open demand),
  `allocable_units` (integer), `level`, `whole_part_units` (integer), `units_granted` (integer),
  `review_rounds` (integer) and `settled` (boolean). `level`, `whole_part_units` and
  `units_granted` describe the allocation that stands: `level` is the level L as a string, the
  fraction in lowest terms as `p/q`, or only the whole number when the fraction's denominator is
  one, and null when every customer receives its cap;
  `whole_part_units` is the sum over the depot-week's customers of the whole parts of their fair
  shares; `units_granted` is the number of units the allocation granted in all.
  allocation_policy.md, Allocation units, Fair shares, Whole units, Review rounds.
- `deficit_boosts`: list, one object per week and customer for which the customer was in deficit
  and had open demand in at least one rationed depot-week of that week, sorted by week in
  calendar order and then by customer id. Keys: `week`, `customer_id`. allocation_policy.md,
  Deficit status.

## data_quality.json

- `orphan_orders`: list, one object per orphan order, sorted by order id. Keys: `order_id`,
  `customer_ref` (as keyed), `reason`. identity_register.md, Orders that never become lots.
- `voided_orders`: list of the order ids of every void order, sorted. source_authority.md.
- `amendments`: list, one object per non-void order that has at least one matched amendment,
  whatever else becomes of the order, sorted by purchase order number and then by order id. Keys:
  `po_number`, `order_id`, `final_quantity_kg`, `cancelled` (boolean). source_authority.md, Order
  amendments.
- `unmatched_amendments`: list of the distinct purchase order numbers of unmatched amendments,
  sorted.
- `lapsed_lots`: list, one object per lot that lapsed, sorted by order id. Keys: `order_id`,
  `customer_id`, `depot`, `week` (the week against which it lapsed), `lapsed_kg`. lot_ledger.md.
- `withdrawn_lots`: list, one object per lot that was withdrawn, sorted by order id. Keys:
  `order_id`, `customer_id`, `depot`, `week` (the week against which it was withdrawn),
  `withdrawn_kg`. lot_ledger.md, Retirement.
- `reconciliation`: object with three parts, each figure summed over the whole season.
  - `stock`: `opening_kg`, `receipts_kg`, `delivered_kg` and `closing_kg`, each summed over all
    depots, and `residual_kg`, which is opening plus receipts less delivered less closing.
  - `demand`: `ordered_kg` (the quantity of every lot), `delivered_kg`, `lapsed_kg`,
    `withdrawn_kg` and `open_at_close_kg`, each summed over all lots, and `residual_kg`, which is
    ordered less delivered less lapsed less withdrawn less open at close.
  - `allocation`: `rationed_kg` (everything delivered in rationed depot-weeks), `unrationed_kg`
    (everything delivered in the other depot-weeks), `delivered_kg` (everything delivered), and
    `residual_kg`, which is delivered less rationed less unrationed.

## Regional reports

`region_<Region>.json` covers the depots of one region:

- `region`: the region name.
- `in_scope`: `true`.
- `depots`: list of the codes of every depot of the region, sorted.
- `rationed_depot_weeks`: integer, the number of rationed depot-weeks over those depots.
- `customers`: list, one object per customer that holds, at the close of the season, at least one
  lot at a depot of the region, sorted by customer id. Keys: `customer_id`, `segment`, and over
  those lots `ordered_kg`, `delivered_kg`, `lapsed_kg`, `withdrawn_kg`, `open_at_close_kg` and
  `fill_ratio`. `fill_ratio` is delivered divided by ordered, rounded half up to four decimal
  places and written as a string with exactly four decimals. lot_ledger.md, Whose lot it is in
  the reports.
- `weekly_delivered_kg`: object with one key per week id of the calendar, giving the quantity
  delivered from the region's depots at that week's allocation (0 when nothing was delivered).

## Segment reports

`segment_<segment>.json` covers one segment:

- `segment`: `commercial` or `public`.
- `in_scope`: `true`.
- `customer_count`: integer, the number of customers of the segment that hold at least one lot at
  the close of the season.
- `ordered_kg`, `delivered_kg`, `lapsed_kg`: totals over every lot held at the close of the season
  by a customer of the segment.
- `rationed_allocations`: list, one object per rationed depot-week and customer with open demand
  there, for customers of the segment, sorted by week in calendar order, then by depot code, then
  by customer id. Keys: `week`, `depot`, `customer_id` (the customer holding the demand at that
  allocation), `demand_kg` (its open demand there), `weight` (its weight in the allocation that
  stands), `reviewed` (boolean, whether it is on the depot-week's review list for that
  allocation) and `allocated_kg` (what it received there). allocation_policy.md.
