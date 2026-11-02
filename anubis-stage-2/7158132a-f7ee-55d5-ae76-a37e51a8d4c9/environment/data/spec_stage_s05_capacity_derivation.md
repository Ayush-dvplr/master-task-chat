# S05 capacity derivation

Capacity is derived per canonical row, which is per pass per period.

## the rate schedule

rate_schedule_effective.psv carries one row per aperture per
schedule_rev, each a half open interval [effective_from_s,
effective_to_s) with a rate in milli KiB per second. The rows of an
aperture tile the campaign without gap or overlap.

legacy_flat_rate_table.csv is retired. Its table_state says so and its
retired_on_s predates the campaign. It binds no capacity. It is read at
S14 for one purpose only, which is the discrepancy report.

## the rate pieces

Split every eligible piece of the row at every rate schedule edge of its
aperture that falls strictly inside it. The result is the rate piece
list: a set of half open intervals each of which lies inside exactly one
rate row. The rate of a piece is the rate of the row whose interval
contains the piece start.

A rate edge that lands exactly on a pass boundary splits nothing,
because the edge is not strictly inside the piece.

## the per piece floor

For each rate piece:

    piece_kib = (piece_seconds * rate_mkib_per_s) // rate_scale_divisor

rate_scale_divisor is in unit_scaling_rules.json. The division is a
floor and it is applied to every piece separately. raw_capacity_kib is
the sum of the piece values.

Summing the seconds first and dividing once is a different number and is
wrong. So is summing the products and dividing once. The floor belongs to
the piece, not to the row. rate_piece_count records how many pieces the
row was split into, so the split is visible in the ledger.

## the per contact cap

The per contact cap is per aperture per period and lives only in
aperture_contract_workbook.xlsx. workbook_sheet_selection.json names the
binding sheet: the sheet whose sheet_status equals binding_status, and
where more than one qualifies, the highest sheet_revision. The other
sheets are superseded or draft and bind nothing.

    usable_capacity_kib = min(raw_capacity_kib, per_contact_cap_kib)

The cap is applied to the canonical row before any aggregation of any
kind. Applying it to a mission total, a station total or an aperture
total produces a larger number and is wrong.

A row whose raw capacity exceeds its cap is written to
capacity_cap_exceptions with the clipped amount. A row whose raw
capacity equals its cap exactly is not an exception.
