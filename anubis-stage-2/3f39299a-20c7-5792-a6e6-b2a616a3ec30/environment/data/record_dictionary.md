# Record dictionary

This document gives the layout of every record file in the extract and the meaning of every code
those files use. The rules that act on the records are in the other documents, which this one
names field by field. CSV files are UTF-8 with a header row and comma separators (a file may begin with a UTF-8
byte-order mark, which is not part of its first column name); JSON files are
UTF-8 objects as described; timestamps with an offset are instants (calendar_and_time.md).

## season_calendar.csv

One row per allocation week, in calendar order.

- `week_id`: the week's identifier.
- `opens_at`: the cutoff at which the week opens, cooperative wall-clock time `YYYY-MM-DD HH:MM`.
- `closes_at`: the cutoff at which the week closes, in the same form.
- `note`: free text explaining the cutoff.

## cooperative_time.json

An object with one key, `periods`: a list of objects in increasing `from_local` order, each with
`from_local` (cooperative wall-clock time `YYYY-MM-DD HH:MM`) and `utc_offset` (`+HH:MM` or
`-HH:MM`). calendar_and_time.md says how a wall-clock time uses them.

## depots.xml

The root element holds one `depot` element per depot and one `routes` element.

- `depot`: attributes `code` (the depot code) and `region` (`North`, `South`, `West` or `East`);
  children `name` (text) and `opening_stock_kg` (whole kg).
- `routes`: one `route` child per route, with attributes `code` and `critical` (`yes` or `no`).

## contracts.csv

One row per customer.

- `customer_id`: the customer's contract id.
- `legal_name`: text.
- `segment`: `public` or `commercial`.
- `contract_min_t`: the contract minimum in metric tonnes, with at most one decimal place (0 when
  the contract promises none).
- `weight_class`: the sales team's grade for the account, a whole number.
- `route_code`: a route code from the route list, or empty.
- `signed_on`: date, text only.

## crm_accounts.json

An object whose key `accounts` holds one object per CRM row, in no particular order: `account_code`
(text), `customer_id`, `segment` (text), `route_source` (`crm` or `contract`), `critical_route`
(`true` or `false` when `route_source` is `crm`, `null` otherwise), `revision` (whole number) and
`updated_at` (instant). Other keys at the top level describe the export and carry no facts.

## identity_events.csv

One row per event: `event_id`, `effective_at` (instant), `kind` (`alias`, `merge`, `retire` or
`reactivate`), `code` (the reference or customer the event is about) and `target` (for `alias` and
`merge`, the customer the code now points to; empty otherwise). identity_register.md gives the
meaning of each kind.

## service_areas.json

An object whose key `assignments` holds one object per assignment: `customer_id`, `depot` and
`effective_from` (instant).

## orders.csv

One row per order as it was keyed, in no particular order.

- `order_id`: the order id.
- `po_number`: the purchase order number.
- `customer_ref`: the customer reference (identity_register.md).
- `placed_at`: the placement instant.
- `quantity_t`: the keyed quantity in metric tonnes.
- `order_class`: an order class code from `order_classes.csv`.
- `channel`: how the order was keyed, text only.

## order_classes.csv

One row per order class.

- `class_code`: the code orders carry in `order_class`.
- `description`: text.
- `offer_weeks`: the offer window of the class, a whole number of weekly allocations, 1 or more
  (lot_ledger.md, How long a lot stays on offer).
- `entitlement_basis`: how a lot of the class contributes to a customer's season-to-date entitled
  and delivered quantities (allocation_policy.md, Deficit status). The bases are:
  - `ordered`: the lot adds its full quantity to the entitled quantity, and what was delivered to
    it in earlier weeks to the delivered quantity;
  - `delivered`: the lot adds what was delivered to it in earlier weeks to the entitled quantity
    and the same amount to the delivered quantity;
  - `excluded`: the lot adds nothing to either quantity.

## order_amendments.jsonl

One JSON object per line: `seq` (whole number), `po_number`, `action` (`set_quantity`, `cancel` or
`reinstate`), `quantity_t` (only with `set_quantity`; metric tonnes, above zero) and `logged_at`
(instant). source_authority.md says how they are read.

## rationing_journal_2024-25.jsonl

The allocation office's journal of its 2024-25 season, the season before this extract's. Its
depots, customers and instants belong to that earlier season and to no other file.

One JSON object per line, one per rationed depot-week of that season, in no particular order:

- `entry_id`: the entry's identifier.
- `depot`: the depot code of that season.
- `allocated_at`: the allocation instant.
- `unit_kg`: U, the allocation unit in force, in kg.
- `available_kg`: the depot's available stock, in kg.
- `parameters`: the parameters in force at that allocation that the journal records:
  `public_weight`, `commercial_weight`, `tie_break`, `bonus_composition`, `review_floor` and
  `review_round_limit`, in the forms allocation_policy.md lists.
- `customers`: one object per customer with open demand at the depot-week: `customer` (its id),
  `segment` (`public` or `commercial`), `critical_route` (whether the critical route bonus
  applied), `in_deficit` (whether the deficit bonus applied), `open_demand_kg` (its open demand,
  in kg) and `oldest_lot_at` (the placement instant of its oldest lot on offer there).
- `granted_kg`: an object giving, for every customer of the entry, what the allocation that stood
  granted it, in kg.
- `reviewed_count`: how many customers were on the depot-week's review list when the allocation
  that stood was made (they carried the review bonus in it).
- `review_rounds`: the number of repeat allocations made in the depot-week.
- `settled`: whether the depot-week was settled (allocation_policy.md, Review rounds).

## receipts.csv

One row per load of salt as keyed at the weighbridge office: `receipt_id`, `depot`, `arrived_at`
(instant), `quantity` (a decimal number in the carrier's weighbridge unit, source_authority.md; it
may carry leading zeros and spaces around it, which do not change its value) and `carrier` (the
carrier's name, as in `carrier_calibration.json`; the weighbridge office sometimes keyed it with
spaces around it or in other letter case, so it names the calibrated carrier whose name it equals
once spaces before and after it are removed and letters are compared without regard to case). A
load can appear on more than one row
(source_authority.md, Re-keyed loads).

## carrier_calibration.json

An object whose key `batches` holds one object per calibration batch: `batch_id`, `weighed_at`
(instant), `loads` (a list of objects with `carrier` and `quantity`, the quantity in that carrier's
unit) and `credited_kg` (whole kg). Other keys at the top level carry no facts. source_authority.md defines the credited total.

## dispatch_board_final.csv

One row per board line: `board_line`, `po_number`, `depot`, `planned_week`, `planned_qty_t`,
`status` and `updated_at`. Only `status` value `VOID-DUP` carries a fact (source_authority.md). A
line's `po_number` may carry spaces before or after it, which are not part of the number.

## allocation_parameters.json

An object whose key `versions` holds one object per parameter version: `version_id`,
`effective_at` (instant), `mode` (`replace` or `patch`) and `values` (an object mapping parameter
names to values, in the forms allocation_policy.md lists). allocation_policy.md says how versions
combine.
