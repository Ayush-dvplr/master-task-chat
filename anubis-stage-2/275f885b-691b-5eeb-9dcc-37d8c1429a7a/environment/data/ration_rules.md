# Ration rules

Each region and round is a cell. A cell holds its available doses and the claims that settle in
it. The ladder grants awards inside one cell and never moves doses between cells.

## Tiers

`priority_register.csv` states the priority tier of a block from an effective date, and the
entry with the latest `effective_from` at or before the opening date of the round window is in
force, with `issued_at` and then `entry_ref` breaking a tie. A block with no entry in force sits
in the last tier. Tiers are served in ascending order. A tier is served only from the doses the
tiers above it left behind.

## Level fill

Where the doses still in hand cover the claimable quantity of every claim in the tier, each
claim is granted its claimable quantity in full.

Otherwise the tier is level filled. The waterline is the largest whole number of doses such that
the sum over the claims in the tier of the smaller of the claimable quantity and the waterline
does not exceed the doses still in hand. Each claim in the tier is granted the smaller of its
claimable quantity and the waterline.

## Remainder

Level filling can leave doses in hand that are fewer than the number of claims still below their
claimable quantity. Those doses are granted one each to the claims whose claimable quantity
exceeds their grant, taking the claims in order of descending claimable quantity.

The tier that is level filled is the binding tier of the cell and the waterline of that tier is
the waterline of the cell. Tiers below the binding tier are granted nothing. A cell in which no
tier is level filled reports a waterline of minus one and a binding tier of zero.

## Outcomes

`reason_codes.json` carries the award reason register. The first entry whose condition holds
gives the reason of a settled claim, and the outcome map in that file gives its outcome.
