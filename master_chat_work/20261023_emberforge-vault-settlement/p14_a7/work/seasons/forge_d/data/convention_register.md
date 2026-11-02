# Register of season conventions

Some conventions of a season are recorded with its charter. Others are fixed by
the guild council for a whole council year at once, and the council never
publishes the draw itself: it publishes this register of the conventions it may
draw from, and the rulings it handed down during the year. Every season draws
one entry from each table below, and the same draw governs every workshop, every
entry and every reagent of that season.

## Return schedules

A return schedule gives, for each artifact tier, the percentage of a source
forge's committed reagents that a settled salvage of that artifact returns.

| schedule | tier 1 | tier 2 | tier 3 |
| --- | --- | --- | --- |
| RS-A | 40 | 50 | 60 |
| RS-B | 45 | 55 | 65 |
| RS-C | 50 | 60 | 70 |
| RS-D | 35 | 50 | 65 |
| RS-E | 55 | 55 | 55 |
| RS-F | 30 | 45 | 60 |
| RS-G | 60 | 50 | 40 |

## Reduction conventions

Wherever a rule reduces a fractional quantity to a whole number, the season's
reduction convention decides the result. Write the fractional quantity as a
numerator over a positive denominator.

- `floor` - the greatest whole number that does not exceed the quantity.
- `ceil` - the least whole number that is not below the quantity.
- `half-up` - the nearer whole number; a quantity exactly halfway between two
  whole numbers goes to the greater of them.
- `half-down` - the nearer whole number; a quantity exactly halfway between two
  whole numbers goes to the lesser of them.
- `half-even` - the nearer whole number; a quantity exactly halfway between two
  whole numbers goes to whichever of them is even.

## Operator orders

The charge rulebook names three operators that a settled forge's charge passes
through: the family operator `F`, the grade operator `G` and the scarcity
operator `S`. A season's operator order is the sequence in which they are
applied, and the season's reduction convention is applied at each of the three
steps. The register holds all six sequences: `FGS`, `FSG`, `GFS`, `GSF`, `SFG`,
`SGF`.

## Scarcity references

The scarcity rulebook expresses a scarce reagent's settled consumption as a
percentage of a reference quantity of that reagent. The register holds these
candidate references:

- `opening` - the reagent's opening vault balance for the season.
- `opening-plus-acquired` - that opening balance together with every unit of the
  reagent the season acquired.
- `consumed` - the units of the reagent called for by every forge entry the
  season tests against the vault floor, whether or not that forge then settled.
  A forge refused for its workshop's scope, its smith's standing or an
  unresolved edition is never tested against the floor and calls for nothing
  here.
- `acquired` - the units of the reagent the season acquired.

A reference that stands at zero for a reagent leaves that reagent's scarcity
index at zero.

## The council's rulings

The rulings of the council year are published with the season's records. Each
ruling is one worked case taken from some season of that year: the quantities
that went into a single reduction, and the whole number the council ruled. A
ruling is not a figure of the season it is published with. Taken together, the
rulings of a year agree with exactly one draw of this register, and that draw
governs every season of the year.

- A charge ruling gives a forge's base value under H1, the family operator's
  percentage, the grade operator's percentage and the scarcity operator's
  percentage, and the charge the three operators gave that forge in the
  season's operator order.
- A return ruling gives the tier of a salvaged artifact and the units of one
  reagent line that its source forge committed (that line's units per craft
  times the units the forge committed), and the units that line returned.
- A scarcity ruling gives a scarce reagent's opening balance, the units the
  season acquired, the units called for by the forges tested against the floor,
  the reagent's settled consumption and the charter's scarcity ceiling, and the
  scarcity index the council ruled.
