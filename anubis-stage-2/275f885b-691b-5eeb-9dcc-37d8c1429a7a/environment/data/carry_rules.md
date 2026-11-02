# Carry rules

The deferred quantity of a claim is its claimable quantity less its award.

The carried claim an identity takes into the next round is the smaller of the deferred quantity
and the multiple declared as `carry.cap.multiple` of the entitlement of the claim just settled.
An identity with no claim in a round takes its carried claim forward unchanged unless a clearing
round reaches it.

A carried claim is extinguished to zero in any of these cases. A `no_show` event in the visit
stream for the block and round extinguishes the carried claim of an identity that settles a
claim in that round, before any clearing round is considered, and a carried claim counts under
one cause only. A change of restock epoch extinguishes it,
because the running quantities of the new identity start at zero. A clearing round extinguishes
it in the scope described below.

A region and round is a clearing round when the available doses of the cell strictly exceed the
claimable quantity of every claim in the cell taken together.

The register does not record which carried claims a clearing round extinguishes.
`clearance_observations.log` records what the settlement desk did to sampled carried claims,
written as `balance_cleared=`, and that evidence settles the scope for the whole campaign. The
scope reported in the policy audit is one of `region_wide`, which covers every block the region
holds in that round, `fully_awarded_only`, which covers the blocks whose claim in that round was
granted in full, `tier1_only`, which covers the blocks whose claim in that round sits in tier
one, and `none`, which covers nothing.

`cleared_balances` in a cell counts the blocks whose carried claim stood above zero and was
extinguished by the clearing round.

