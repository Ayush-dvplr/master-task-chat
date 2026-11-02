# Rulebook - Requisitions

A season closes by granting reagent units against the requisitions its workshops
filed. Each requisition names one workshop and one reagent, and states the
smallest grant the workshop will accept, the number of units it asked for, and a
priority number.

**Q1. Eligibility.** A requisition is considered only when it names a workshop the
season holds in scope. A requisition naming any other workshop receives nothing
and takes no further part in the settlement, though the season still records its
grant of nothing.

**Q2. Shape of a grant.** A grant is a whole number of units of the reagent the
requisition names. It is either nothing at all, or it is at least the
requisition's stated minimum and no more than both the units it requested and the
unit ceiling the season charter records for the charter tier of the workshop that
filed it.

**Q3. Season pool.** The units granted across every requisition may not exceed the
season pool the charter records.

**Q4. Guild holding.** For each guild, the units granted to the requisitions of
that guild's in-scope workshops may not exceed the guild holding the charter
records for that guild.

**Q5. Vault balance.** For each reagent the reagent registry marks scarce, the
units granted for that reagent across every requisition may not exceed the
vault's closing balance of that reagent at the end of the season. A requisition
naming a reagent the registry does not mark scarce is not limited by the vault's
closing balance.

**Q6. Charter.** A charter holds at most one funded requisition. Where two
in-scope workshops share a charter, at most one of the two requisitions is
funded; the other receives nothing.

**Q7. Objective.** Among the funding plans that satisfy Q1 through Q6, the season
adopts one that grants the greatest total number of units.

**Q8. Preference.** Where more than one plan grants that greatest total, the
season prefers the plan that grants more units to the requisition carrying the
smallest priority number; where several requisitions carry the smallest priority
number, the one whose identifier sorts first among them; and so on through the
remaining requisitions taken in ascending order of priority number and then of
identifier. Exactly one plan survives this preference.

**Q9. Closed workshops.** A workshop that reached its charge cap during the season
remains eligible to receive a grant, and a workshop that settled no entry at all
remains eligible to receive a grant. Reaching the cap ends a workshop's
forging, not its charter.
