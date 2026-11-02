# Rulebook - The Reagent Vault and Scarcity

**V1. Opening.** The vault opens the season holding, for each reagent, the opening
balance recorded for that reagent.

**V2. Acquisitions.** An acquisition credits the vault with its units on the day it
records. Those units are available to entries filed on that day and on later
days, and are not available to entries filed earlier. An acquisition recorded for
a day the season calendar does not cover is not credited to the vault at all and
takes no part in the settlement.

**V3. Consumption.** A forge draws from the vault, for each reagent line of the
recipe edition that governs the forge, that line's units per craft multiplied by
the number of units the entry commits.

**V4. Floor.** The vault never holds a negative balance of any reagent. A forge
whose draw would take a reagent's balance below zero is not settled: it draws
nothing, it carries no charge, and it moves its workshop no closer to that
workshop's charge cap.

**V5. Scarcity index.** Every reagent the registry marks scarce carries one
scarcity index for the season. The index is the season's settled consumption of
that reagent, expressed as a percentage of a reference quantity of that reagent,
reduced to a whole number of percent, and then held at the scarcity ceiling the
charter records whenever it would otherwise stand above that ceiling. Which
quantity of a reagent serves as its reference is fixed for the season and is the
same choice for every scarce reagent, but it is not recorded in this rulebook.

**V6. Other reagents.** A reagent the registry does not mark scarce carries no
scarcity index and never contributes to the scarcity operator.

**V7. Returns are not consumption.** Units a settled salvage returns raise the
vault's balance. They are not consumption, and they never reduce a scarcity
index.

**V8. Settled state.** A season's scarcity indices and its settlement determine one
another: the indices are read off the settled season, and the settled season is
charged at those indices. Exactly one assignment of indices agrees with the
season that assignment produces, and the season is settled at that assignment.

**V9. Retired reagents.** A reagent whose registry row names a retired patch can
no longer be drawn from the vault from the first day of that patch onward. A
forge filed on or after that day whose governing recipe edition has a line for
that reagent is not settled: it draws nothing, it carries no charge, and it
moves its workshop no closer to that workshop's charge cap. Retirement is a
condition of the forge in the same way as the floor in V4. It never stands in
for the charge cap or the floor, which are judged on the same forge as well.
Retirement stops draws only: units of a retired reagent that a credited salvage
returns still re-enter the vault.
