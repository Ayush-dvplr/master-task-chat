# Rulebook: Salvage

Applies to the Emberforge crafting season. A salvage entry breaks an artifact
back down and returns part of the reagents that were committed to make it.
This rulebook states when a salvage is credited and what it returns.

## S1. Source forge

Every salvage entry names the forge entry it salvages. A salvage that names an
entry absent from the ledger is not settled.

## S2. Credit window

A salvage is credited only when the forge entry it names is among the last
three live forge entries of the same artifact family settled for the same
canonical smith on days strictly before the salvage's own day. The canonical
smith is the one the salvage's own handle resolves to on the salvage day, and
the forge entries are read against that canonical smith whatever handles they
were filed under, each forge entry's handle resolved on the forge's own day
(I3). Each artifact family carries its own window.

A salvage whose source forge falls outside that window is not settled and
returns nothing.

## S3. Return quantity

A credited salvage returns, for each reagent line of its governing recipe
edition, that line's units per craft multiplied by the number of units the
**source forge entry** committed, taken at the return rate for the
artifact's tier and reduced to whole units.

The return rate schedule assigns one rate to each artifact tier. The schedule
is fixed for the season but is not recorded in this rulebook.

## S4. Returned units re-enter the vault

Units returned by a credited salvage re-enter the vault on the salvage's day
and are available to entries settled after it. They are not available to
entries settled before it.

## S5. Salvage and the cap ledger

A salvage entry commits no reagents and cannot be blocked by a shortage of
stock. When a salvage is credited, the charge of its source forge entry leaves
the accrued settled charge of the workshop that filed that forge, for every
forge entry settled after the salvage. The charge stays in every charge figure
the season reports. A workshop already closed under A4 stays closed.

## S6. One salvage per forge

A forge entry may be credited to at most one salvage. Where the ledger holds
more than one salvage naming the same forge entry, the settlement reaches them
in the order it settles the ledger, and the first of them that the credit window
admits is credited. Every later salvage naming that forge entry is not settled,
whatever its own day and whatever the window would otherwise say of it.
A salvage refused under this rule is not tested against the credit window and
carries only `SALVAGE_ALREADY_CREDITED`.

A salvage the credit window turns away is not credited, and a later salvage
naming the same forge entry is judged on its own.
