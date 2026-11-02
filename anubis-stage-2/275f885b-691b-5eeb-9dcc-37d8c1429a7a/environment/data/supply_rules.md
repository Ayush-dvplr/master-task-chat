# Supply rules

## Lots

`lot_register_p1.csv` and its siblings list the lots consigned to each depot. A lot identity is
its lot reference, the character `@`, and its production year, written `LOT-1182@2033`. Lot
references are reissued between production years, so a lot reference alone names no lot.

`unit_declarations.ini` declares the measurement basis of the `quantity` column for a depot and
production year. A lot whose depot and production year carry no declared basis is counted and
supplies nothing.

The dose content of a lot is its quantity multiplied by the doses per unit in force for it,
truncated toward zero to a whole dose. The doses per unit comes from the assay for that lot
identity when one exists, and otherwise from the `potency_factors.csv` row for the depot,
serotype and declared basis with the latest `effective_from` at or before the consignment date.

## Availability

A lot is available to its region for a round when all of the following hold: the round falls at
or after the round in which the lot entered the pool, the lot expiry falls strictly after the
opening instant of the round window, the lot state in force at that instant is `released`, and
the lot serotype reaches the campaign target serotype of the region and round under
`substitution_rules.md`.

The campaign target serotype of a region and round is the `target_serotype` of the phase
revision in force for that region and round.

The available doses of a region and round is the sum of the undrawn content of the lots
available to it.

## Drawing

Lots are drawn earliest expiry first, with the lot reference and then the production year
breaking a tie. A lot that is partly drawn keeps the rest of its content for later rounds.
Awards inside a cell are drawn in the order the ledger records them, and the lot identity of the
first dose drawn for a claim is recorded against that claim.

Undrawn content of a lot whose expiry falls at or before the opening instant of a round window
is written off once, in the first round window that opens at or after the expiry, and counted
against that region and round.
