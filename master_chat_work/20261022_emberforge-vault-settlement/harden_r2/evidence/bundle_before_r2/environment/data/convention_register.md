# Register of season conventions

Some conventions of a season are recorded with its charter. Four others are fixed
by the guild council for a whole season at once, and the council publishes only
the register of the conventions it may draw from - never the draw itself. This
document is that register. Every season draws exactly one entry from each of the
four tables below, and the same draw governs every workshop, every entry and
every reagent of that season.

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
percentage of a reference quantity of that reagent. The register holds four
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
