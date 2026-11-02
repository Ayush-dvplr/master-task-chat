# Stage r09 - demand

Fed by: r04, r08.
Feeds: r10.

Compute the energy demand of every ordered instance.

- The effective intensity is the resolved intensity plus the class
  surcharge for the action's class from the workbook, floored at
  zero. The surcharge may be negative.
- The window scale is the workbook scale for the window's capacity
  class.
- The demand is
  `half_even(half_even(energy * effective_intensity / 10000)
  * window_scale / 10000)`. Both roundings happen. The first result
  is never carried unrounded into the second product.
- An instance whose demand exceeds the memo's implausible demand
  ceiling is set aside under `IMPLAUSIBLE_DEMAND` and takes no
  further part.
- Publish `resource_demand.csv`.
