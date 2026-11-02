# Season extract: Northbrook Highway Materials Cooperative

This folder is the allocation office's record of the 2025-26 road-salt season: the depots and the
regions they belong to, the customers, every order keyed during the season, every load of salt
that arrived, the paperwork that corrected those records afterwards, and the allocation
parameters the office issued. Nothing outside this folder is needed.

## Record files

- `season_calendar.csv` and `cooperative_time.json`: the allocation weeks and cooperative time.
- `depots.xml`: depots, their regions and opening stock, and the route list.
- `contracts.csv`: the contracts register.
- `crm_accounts.json`: the sales team's CRM export.
- `identity_events.csv`: aliases, merges, retirements and reactivations of customer identities.
- `service_areas.json`: which depot serves each customer from when.
- `orders.csv`: every order as it was keyed.
- `order_classes.csv`: the order classes.
- `order_amendments.jsonl`: the errata raised against orders after keying.
- `receipts.csv`: every load of salt that arrived at a depot.
- `carrier_calibration.json`: the weighbridge calibration batches.
- `dispatch_board_final.csv`: an export of the dispatch planning board.
- `allocation_parameters.json`: the allocation parameter versions.
- `rationing_journal_2024-25.jsonl`: the allocation office's journal of the previous season's rationed
  depot-weeks.

record_dictionary.md gives the layout of each of these files and the meaning of their codes.

## Documents

- calendar_and_time.md: cooperative time, the allocation weeks, which week an instant belongs to,
  and the allocation instant.
- identity_register.md: how a customer reference resolves to a customer, which depot serves an
  order, and which orders never become lots.
- lot_ledger.md: lots, how long a lot stays on offer, how deliveries are applied, stock carried
  between weeks, merges, retirements and the season close.
- allocation_policy.md: the allocation parameters, rationing, fair shares, whole units, customer
  weights, deficit status, review rounds and the season true-up.
- source_authority.md: which file is the authority for which fact, the weighbridge settings,
  void marks and amendments.
- record_dictionary.md: record layouts and codes.
- report_layout.md: the reports and their exact layout.
