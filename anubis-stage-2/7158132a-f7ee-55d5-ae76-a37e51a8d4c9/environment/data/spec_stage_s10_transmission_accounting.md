# S10 transmission accounting

S10 decides what the allocation of S09 actually delivers, and it is the
only stage that keeps running state across apertures.

## the resolution order

Within a settlement period, the accepted rows are visited in this order:

  1. station_id ascending
  2. antenna_uid ascending
  3. the S07 ordering within the aperture

The periods themselves are visited P1, then P2, then P3, because the
carry out of one is the carry source of the next.

## the contract of a row

A pass may sit under more than one contract of its mission. The binding
contract for the row is, among the contracts of the pass that have
settled terms in the period, the one with the largest obligation_kib,
and where two are equal the lower contract_id. A mission that holds two
contracts competes against itself through this rule: both draw on their
own allowance and the row is charged to one of them only.

## the acceptance

    accepted_kib = min(allocated_kib, backlog_remaining, allowance_remaining)

backlog_remaining is the running backlog of the mission for the period.
It opens at the binding backlog report figure and is reduced by the
accepted volume of each row as it settles, never by the demand and never
by the allocation.

allowance_remaining is the carry remainder plus the new entitlement
remainder of the binding contract for the period.

    from_carry_kib = min(accepted_kib, carry_remainder)
    from_new_kib   = accepted_kib - from_carry_kib

and the two remainders are reduced by those two amounts.

## the derived volumes

    deferred_kib        = demand_kib - accepted_kib
    unused_capacity_kib = usable_capacity_kib - accepted_kib

Deferred volume is measured against demand and unused capacity against
usable capacity, so the two differ whenever the backlog held demand
below capacity. Both are recorded.

## downlink reports are not authoritative

downlink_reports.csv is what the reporting systems said moved. It is not
an input to any accepted figure. A report larger than the physical
capacity of its pass is possible and changes nothing. Reports are read at
S14 for the discrepancy report only.
