# Rulebook: Salvage

Applies to the Emberforge crafting season. A salvage entry breaks an artifact
back down and returns part of the reagents that were committed to make it.
This rulebook states when a salvage is credited and what it returns.

## S1. Source forge

Every salvage entry names the forge entry it salvages. A salvage that names an
entry absent from the ledger is not settled.

## S2. Credit window - the smith's last three admitted forges of that family

A salvage is credited only when the forge entry it names is among the **last
three forge entries of the same artifact family that were settled for the same
canonical smith, on days strictly before the salvage's own day**.

The canonical smith is the one the salvage's own handle resolves to on the
salvage day, and the three settled forges are read against that same canonical
smith, whatever handles they were filed under. Forge entries that were not
settled do not occupy a place in the window; the window holds the last three
that were. Forge entries of a different artifact family do not occupy a place
in the window either - each family carries its own window.

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

## S5. Salvage does not consume

A salvage entry commits no reagents. It cannot be blocked by a shortage of
stock, and it never draws a workshop closer to its charge cap.

## S6. One salvage per forge

A forge entry may be credited to at most one salvage. Where the ledger holds
more than one salvage naming the same forge entry, the settlement reaches them
in the order it settles the ledger, and the first of them that the credit window
admits is credited. Every later salvage naming that forge entry is not settled,
whatever its own day and whatever the window would otherwise say of it.

A salvage that the credit window turns away does not redeem its forge entry, so
a later salvage naming the same forge entry is still judged on its own.
