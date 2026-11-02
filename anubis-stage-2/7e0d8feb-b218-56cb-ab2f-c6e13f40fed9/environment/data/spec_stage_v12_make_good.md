# V12 make good

Inputs: the deferrals from V9, the settlement from V11, and the make good
cap terms in the settled sheet of `contract_terms_workbook.xlsx`.

## The obligations

A deferred order raises a make good obligation valued at the gross it would
have earned, which is its billable grains under R27 priced by its rate card
under R28. An order that has no eligible rate card under R28 raises no
obligation, whatever the reason it was deferred with, because there is no
card to value it with. The reason `DF_NO_RATE_CARD` is the common case, but
an order deferred earlier in the predicate order can have no card too.

An admitted spot whose billable grains R41 cut raises an obligation too. Its
reason is `DF_OVER_CAP`, and it is valued at the grains it lost, priced by
the card that priced the spot: the grains its delivered frames would bill
under R27, less the grains its billed frames bill, multiplied by the card's
`minor_per_grain`. An admitted spot that lost frames to the cap but no whole
grain raises no obligation. An order is either admitted or deferred, so it
raises at most one obligation.

## The cap

An advertiser's day gross is the sum of the gross of its admitted spots, as
V11 billed them after R41. The
advertiser's make good cap in minor units is the day gross multiplied by
`makegood_cap_num` over `makegood_cap_den` from the settled workbook sheet,
floored to a whole minor unit. An advertiser with no admitted spot has a day
gross of zero and therefore a cap of zero.

## R31 the redistribution

When the sum of an advertiser's raw obligations is at most the cap, every
obligation is allocated its raw value.

When the sum exceeds the cap, the cap is allocated across the obligations in
proportion to their raw values by the largest remainder method. Each
obligation takes the floor of its exact proportional share; the minor units
left over between the sum of those floors and the cap are then handed out one
minor unit at a time to the obligations with the largest discarded
remainders, ties broken by ascending `order_ref`.

The allocation is mass preserving: the allocated total equals the cap
exactly. Flooring each share and discarding the remainder loses that mass
and is wrong.

## Published

`makegood_ledger.json` publishes one entry per advertiser that has either an
obligation or an admitted spot, ordered by `advertiser_ref`, each carrying
the day gross, the cap, the raw total, the allocated total and the
obligations in ascending `order_ref`.
