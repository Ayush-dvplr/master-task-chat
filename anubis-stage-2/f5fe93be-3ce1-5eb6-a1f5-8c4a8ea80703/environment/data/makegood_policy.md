# Commitments and make-goods

## Commitments

Each order line is a recurring commitment. Its committed count on broadcast date `d` of its workload is the governing `spots_per_day` for `d` (see `source_precedence.md`) when `d` lies in the flight, the weekday of `d` is in `weekdays` and `d` is not a blackout date of the workload's channel; on every other date it is 0.

For order line `L` and broadcast date `d` of the workload:

- `delivered` counts the `AIRED` spots whose governing order line is `L` and whose broadcast date is `d`;
- `held` counts the `UNRESOLVED` spots whose governing order line is `L` and whose broadcast date is `d`; a held spot earns nothing and owes nothing, so it comes off the commitment;
- the effective commitment is `max(committed - held, 0)`;
- `billable = min(delivered, effective commitment)`, `shortfall = effective commitment - billable` and `bonus = delivered - billable`.

A pair has a deliveries row when any of `committed`, `delivered` or `held` is above zero. Spots attributed to a date outside the workload's broadcast dates count nowhere. Bonus spots are never billed and never offset a shortfall on another date.

## Make-good units

Each unit of shortfall is one make-good unit, numbered from 1 within its order line and date. Units are settled one at a time in this order: `priority` ascending, then the shortfall date ascending, then `unit_rate_cents` descending, then `order_line` ascending, then unit number ascending.

A unit needs the expected frames, on the workload's channel, of its order line's own `house_id`. The breaks open to it are the breaks of its order line's daypart (the daypart holding the break's broadcast clock opening count) whose broadcast date is after the shortfall date and not after the earlier of the workload's last broadcast date and `flight_end - 1 + makegood_grace_days`. A break's spare frames start at `capacity_frames` minus the frames of its occupying spots, never below zero, and every unit placed in it takes its need from them. A unit goes to the first open break, ordered by broadcast date, then broadcast clock opening count, then `break_id`, whose spare frames are at least its need; it is then `placed`. A unit with no such break is `credited`.
