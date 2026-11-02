# Output contract

The settlement produces nine documents and one program. Every quantity is an exact whole
number of doses. No quantity is rounded, scaled or smoothed at output time.

## Regional ledgers

`region_North.json`, `region_South.json`, `region_West.json` and `region_East.json` each hold
an object with the keys `region`, `rounds`, `ledger` and `cells`.

`region` is the region name. `rounds` is the list of live round codes in calendar order.

`ledger` is the list of settled claims for that region. Each entry holds exactly these keys:

```
block                   block identity, for example BLK-0042#2
round                   round code of settlement
tier                    priority tier of the claim, 1 to 4
entitlement_doses       entitlement after amendment and after the handling ceiling
carried_claim_doses     carried claim brought into the round
claimable_doses         entitlement_doses plus carried_claim_doses
awarded_doses           award from the ration ladder
deferred_doses          claimable_doses minus awarded_doses
awarded_to_date         sum of awarded_doses for this identity to and including this round
deferred_to_date        sum of deferred_doses for this identity to and including this round
carry_forward_doses     carried claim this identity takes into the next round
served_lot              identity of the lot the first awarded dose was drawn from
substitution_hops       substitution hop count recorded on the served lot
outcome                 one of full, partial, zero, declined
reason                  one of AWARD_FULL, LEVEL_BOUND, SUPPLY_EXHAUSTED, CEILING_ZERO
```

`served_lot` is the empty string when the award is zero, and `substitution_hops` is then zero.
Ledger entries are ordered by round in calendar order, then by tier ascending, then by block
identity ascending.

`cells` is the list of region and round cells in calendar order. Each entry holds exactly these
keys: `round`, `available_doses`, `claimable_doses`, `awarded_doses`, `waterline`,
`binding_tier`, `surplus_doses`, `cleared_balances`, `written_off_doses`. When no tier binds in
a cell, `waterline` is minus one and `binding_tier` is zero.

## Segment rollups

`segment_commercial.json` and `segment_public.json` each hold an object with the keys
`segment`, `regions` and `rounds`. `regions` is a list in the order North, South, West, East,
each entry holding `region`, `claims`, `awarded_doses`, `claimable_doses`, `deferred_doses`,
`carry_forward_doses`, `full`, `partial`, `zero` and `declined`. `rounds` is a list in calendar
order, each entry holding `round`, `claims`, `awarded_doses` and `deferred_doses`.

## Summary

`summary.json` holds `live_rounds`, `skipped_rounds`, `claims_settled`, `claims_rejected`,
`blocks_settled`, `claimable_doses`, `awarded_doses`, `deferred_doses`,
`carry_forward_doses`, `available_doses`, `surplus_doses`, `written_off_doses`, `regions` and
`segments`. `regions` is a list in the order North, South, West, East, each entry holding
`region`, `claims`, `awarded_doses` and `deferred_doses`. `segments` is a list in the order
commercial, public, each entry holding `segment`, `claims` and `awarded_doses`.

## Policy audit

`policy_audit.json` holds `governing_source`, `balance_clearance_scope`, `alias_hops`,
`epoch_identities`, `collapsed_duplicates`, `stale_revisions`, `attribute_overrides`,
`amendments_applied`, `amendments_stale`, `amendments_unauthorised`, `ceiling_clamped`,
`exact_half_entitlements`, `substituted_lots`, `lots_unresolved_cycle`,
`lots_without_substitute`, `illegal_transitions`, `reinstated_lots`, `unit_undeclared_lots`,
`extinguished_no_show`, `extinguished_epoch`, `binding_tiers` and `clearing_rounds`.

`governing_source` is an object with the keys `before_cutover` and `from_cutover`, each holding
one of `field_intake`, `dispatch_stream`. `balance_clearance_scope` holds one of
`region_wide`, `fully_awarded_only`, `tier1_only`, `none`. `alias_hops` is an object keyed by
the strings `1`, `2` and `3`. `substituted_lots` is an object keyed by the strings `1` and `2`.
`binding_tiers` is an object keyed by the strings `0`, `1`, `2`, `3` and `4` counting cells.
`clearing_rounds` is a list in the order North, South, West, East, each entry holding `region`
and `rounds`, where `rounds` lists the clearing round codes in calendar order. Every other key
holds a whole number.

`lots_unresolved_cycle`, `lots_without_substitute`, `illegal_transitions` and
`unit_undeclared_lots` equal the counts of `RC_LOT_CYCLE`, `RC_NO_SUBSTITUTE`,
`RC_ILLEGAL_TRANSITION` and `RC_UNIT_UNDECLARED`. `reinstated_lots` counts lots that enter a
pool at an opening at which their certificate chain in force holds an applied reinstatement.
`exact_half_entitlements` counts settled claims whose entitlement before rounding lies exactly
halfway between two whole doses.

`attribute_overrides` counts surviving requisition rows whose stated species or age class
differs from the master version in force. `epoch_identities` counts distinct settled identities
whose epoch is above one.

## Data quality

`data_quality.json` holds `rejects`, `counted` and `source_rows`. `rejects` is keyed by every
reject code in `reason_codes.json` in register order. `counted` is keyed by every counted code
in `reason_codes.json` in register order. `source_rows` is keyed by `field_intake`,
`dispatch_stream`, `registry`, `visit_events`, `amendment_notices`, `lot_register`,
`release_certificates`, `assay` and `reference`, each holding the number of record rows read
from the files of that logical source. Rows of the reference tier and of the configuration
tier count under `reference`.
