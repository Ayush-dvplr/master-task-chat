# Settlement value

- The charge of a placed order is its billable slots multiplied by the rate of the
  lane it rests on.
- rebate_band: 0=0, 1=4, 2=9, 3=15
- The rebate of a placed order is its billable slots multiplied by the rebate its
  dispatch mode earns, and a rebate never exceeds the charge it offsets.
- The net value of a placed order is its charge less its rebate.
- Each client publishes a budget ceiling in micro units. Net value accumulates
  against that ceiling across the orders of the client taken in ascending order of
  identifier. Where an order would carry the running total past the ceiling, the
  part that would pass the ceiling is recorded as capped value and the order
  settles the remainder.
- Every monetary figure is a whole number of micro units and stays a whole number
  at every step.
