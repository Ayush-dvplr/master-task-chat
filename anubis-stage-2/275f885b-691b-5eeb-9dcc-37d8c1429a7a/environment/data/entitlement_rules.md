# Entitlement rules

## Dose factors

`dose_factors.csv` states doses per one hundred head for a region, species and age class from
an effective date. The factor in force for a claim is the one with the latest `effective_from`
at or before the calendar date on which the round window opens, with `issued_at` and then
`factor_ref` breaking a tie. Species and age class come from the master version in force.

## Entitlement

The entitlement of a claim is the governing head count multiplied by the factor in force,
divided by one hundred, and rounded half away from zero to a whole dose. This is the only step
of the settlement that rounds. Every other step works in whole doses already, and a quantity
that lands exactly halfway between two whole doses rounds upward.

## Handling ceiling

`block_ceilings_h1.csv` and its sibling state a handling ceiling for a block and round. Where
more than one row covers the pair, the row with the latest `issued_at` is in force with
`entry_ref` breaking a tie. The ceiling applies after the amendment notices that target it, and
it applies to the rounded entitlement: an entitlement above the ceiling is replaced by the
ceiling and counted as clamped. A pair with no ceiling row carries no ceiling.

A claim whose entitlement and carried claim are both zero is settled with the outcome
`declined`.
