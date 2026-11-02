# Sources and authority

Several files in the extract describe the same things, and they do not always agree. This document
says which file governs which fact, how quantities are converted, and how the paperwork that
corrects orders is read. Record layouts are in record_dictionary.md.

## Depots

`depots.xml` governs the depot list, the region each depot belongs to, each depot's opening stock
and the route list (which route codes are critical).

## Segment and contract minimum

`contracts.csv` is the contracts register. It is the authority for a customer's segment (`public`
or `commercial`) and its contract minimum (`contract_min_t`). Every customer id the extract uses
appears in it.

## Critical routes

Whether a customer serves a critical route is decided per instant, starting from the CRM export.

A customer can have many CRM rows, one per update. The row in force for a customer at an instant
is its row with the latest `updated_at` at or before that instant; between rows with the same
`updated_at`, the row with the higher `revision` is in force. A customer with no row in force at
an instant does not serve a critical route at that instant.

When the row in force has `route_source` `crm`, its `critical_route` value decides. When it has
`route_source` `contract`, the CRM defers to the contracts register for this fact: the customer
serves a critical route exactly when its `route_code` in `contracts.csv` is a route that
`depots.xml` lists as critical. An empty route code, or one that the route list does not mark as
critical, means no critical route.

## Quantities and units

Order quantities (`quantity_t` in `orders.csv` and in amendments) are metric tonnes with at most
one decimal place, always above zero; one tonne is 1,000 kg exactly. Every report gives
quantities in whole kg.

## Weighbridge settings and credited receipts

A receipt's `quantity` is written in the weighbridge unit of the carrier that delivered the load.
Each carrier's weighbridge has three settings:

- `unit`: `short_ton` (907.18474 kg), `metric_tonne` (1000 kg) or `long_ton` (1016.0469088 kg);
- `moisture_deduction`: a whole percentage from 0 to 9;
- `rounding`: `half_up` (a half kg goes up), `down` (any fraction of a kg is dropped) or `up` (any
  fraction of a kg makes a whole kg).

A load's credited quantity is its `quantity` times the kg of the carrier's unit, times
(100 - moisture_deduction) / 100, rounded to a whole kg by the carrier's rounding. Each load is
credited on its own; a week's or a depot's receipts are the sum of the credited loads.

`carrier_calibration.json` records calibration batches run over the central weighbridge. Each
batch lists its loads (carrier and quantity) and is dated with the instant it was weighed
(`weighed_at`). A batch's credited total is the sum of its loads' credited quantities. A load of
`receipts.csv` is credited with its carrier's settings.

## Re-keyed loads

When the weighbridge office corrected a ticket, it keyed the load again under the same
`receipt_id` instead of editing the first row. Rows of `receipts.csv` that share a `receipt_id` are
one load, and the row that comes last in the file is the one in force for every fact of that load;
the earlier rows are void.

## The dispatch board export

`dispatch_board_final.csv` is an export of the dispatch planning board. Its `planned_week` and
`planned_qty_t` columns are never used. It is the record of purchase orders that were keyed twice. A board line whose `status` is `VOID-DUP` voids one order: the order with the
highest order id (order ids compared as text) among the orders that carry that line's `po_number` and are not already void,
taking the `VOID-DUP` lines in order of `board_line`. A line that finds no such order voids
nothing. A void order is void from the moment it was keyed; it never existed as far as the season
is concerned. Two orders that share a purchase order number without a `VOID-DUP` line are genuine
split deliveries and both stand.

## Order amendments

`order_amendments.jsonl` holds the errata raised against orders after keying. Amendments are read
in increasing `seq` order. The
actions are:

- `set_quantity`: the order's quantity becomes `quantity_t`.
- `cancel`: the order is cancelled.
- `reinstate`: a cancelled order is no longer cancelled.

Only the net effect of an order's amendments counts. Its final quantity is the quantity set by its
last `set_quantity`, or its keyed quantity if it has none. It is cancelled when the last of its
`cancel` and `reinstate` amendments is a `cancel`.

Amendments correct the order as it was keyed: the final quantity is the quantity the order had
from the moment it was placed, and the placement instant never changes. An amendment applies to
every order that carries its `po_number` and is not void. An amendment whose `po_number` no
non-void order carries is unmatched and changes nothing.
