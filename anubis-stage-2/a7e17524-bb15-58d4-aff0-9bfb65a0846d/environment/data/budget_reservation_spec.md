# Budget and reservation

`channel_budgets.ini` gives each channel a `budget` and two reserved pools. The
general pool is the budget less the published tier one figure and less the
published tier two figure, and is never below zero. A channel admits at most the
sum of its three pools, so a channel can admit more than its budget or fewer.

A request that reaches capacity consumes a slot in its channel. A request whose
risk tier owns a reserved pool takes from that pool while the pool has room and
from the general pool afterwards. A request whose risk tier owns no reserved pool
takes only from the general pool. Once a channel can offer nothing the remaining
requests there carry the capacity code. The pool a request drew from is part of
what the cycle records about it.

## Rollback cover

Two requests in the same channel form a bound pair when one of them meets a
binding requirement of the other and the channel did not already seat that
requirement at a sufficient revision before the cycle opened. A bound pair has to
be able to come back out of the channel together, so the relay holds a rollback
slot for the pair. The hold lands when the second member of the pair takes
capacity, whichever member that turns out to be, and it is taken from the tier two
reserved pool alone. One hold covers a pair however many requirement rows the two
of them share, and a request that completes more than one pair at once carries a
hold for each.

The size of one hold is the channel's `rollback_reserve_charge`. A channel that
publishes no charge of its own uses twice the per member figure in
`relay_policy_baseline.json`.

A request is offered capacity only when its channel can cover it both ways, which
means one slot for the request itself and room in the tier two reserve for every
hold the admission would complete. A request its channel cannot cover both ways
carries the capacity code and consumes nothing, and the requests after it in rank
are still offered what is left. Because holds draw the tier two reserve down as
the offers proceed, a tier two request later in rank can find that reserve empty
and take the general pool instead.

## Rank

Capacity is offered in rank order inside each channel. The lower tier rank goes
first. Where the rank ties, the earlier release instant goes first, where the
release instant is the governing embargo release instant for that unit and
revision when one exists and the start of the horizon otherwise. Where that ties
as well, the lower unit key goes first.

## Normative parameters

```
general_pool_floor: 0
reserved_tier2_floor: 0
rollback_hold_scope: pair
rollback_hold_source: reserved_tier2
rollback_hold_fallback: per_member_doubled
rank_fields: tier_rank,release_instant,unit_key
```
