# Stage r10 - capacity binding

Fed by: r09, r04.
Feeds: r11, r14.

Bind the demand against the ceilings, under
`capacity_binding_policy.yaml`.

- Group the demand by window and device. Take the groups in window
  ordinal order, then device identifier order.
- The ceiling is the live workbook grid's value for that window and
  device, carried under RR2. A group with no ceiling row displaces
  every instance in it under `UNKNOWN_CEILING` and writes no row to
  `window_capacity_report.csv`. A ceiling cell recording the absent
  sentinel is read under RR4 as no ceiling row; a written `0` is a
  ceiling of zero. The utilisation report sums an absent cell as
  zero.
- The reserve is `half_even(ceiling * reserve_bp / 10000)` with the
  reserve share from the directive part C.
- Mandatory instances draw first, in canonical order, against the
  whole ceiling. When their total exceeds the ceiling the group is
  flagged `overrun` and the remainder is zero.
- The withheld share is the reserve less the mandatory draw, floored
  at zero. The pool is the remainder less the withheld share, floored
  at zero.
- Offer the pool to the discretionary instances ordered by tier
  ascending, then demand descending, then trigger ascending, then
  instance id ascending. A demand at or below the pool fits and
  reduces it. A demand above the pool displaces that instance under
  `CAPACITY_DISPLACED`, and the next candidate is still considered.
- Publish `window_capacity_report.csv`, `initial_allocation.json`
  and `displaced_action_queue.json`.
