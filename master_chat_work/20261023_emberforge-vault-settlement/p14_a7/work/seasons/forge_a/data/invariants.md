# Invariants of a settled season

Every claim below holds of a correctly settled season. They are properties of the
result, not instructions for producing it.

## Terms

The rulebooks use these terms as defined here.

**Live forge entry.** A settled forge entry that no salvage has yet been credited
against.

## Properties

**N1. Settlement order.** A season settles its ledger in ascending order of day,
and within a day in ascending order of entry identifier. Every entry is
considered exactly once.

**N2. Referential closure.** Every salvage names a forge entry. A salvage naming
an entry the ledger does not hold settles nothing and is recorded against the
season's data quality.

**N3. Findings.** A finding names the entry it concerns, the code of the condition
it records, and the detail that code calls for. An entry carries a finding for
every condition that holds of it, so one entry may carry more than one. An entry
the season refuses for its workshop's scope, its smith's standing, a missing
forge or an unresolved edition carries a finding for each of those four that
holds of it and for nothing else: it is never tested against the charge cap, the
vault floor, a retired reagent, the credit window or the one-salvage-per-forge
rule. Every other forge is tested against the charge cap, the vault floor and
every retired reagent alike, and every other salvage against the
one-salvage-per-forge rule and, where that rule lets it through, the credit
window. The season's record of findings holds each entry and code pair once,
ordered by entry identifier and then by code, both ascending. The season also
reports how many findings it recorded under each code.

**N4. Conservation.** For every reagent and every patch of the season, that
reagent's opening balance for the patch, plus the units acquired in the patch,
plus the units returned in the patch, less the units consumed in the patch,
equals the reagent's closing balance for the patch. Each patch opens at the
previous patch's closing balance, and the first patch opens at the vault's
opening balance. The residual of that identity is zero for every reagent, for
every patch, and for the season taken as a whole.

**N5. Agreement.** A season's total charge equals the sum of the charges of the
workshops it holds in scope, and equals the sum of the charges of the guilds it
holds in scope. A guild's figures are the sums of the corresponding figures of
its in-scope workshops. The units a workshop receives are the units granted to
that workshop's requisition.

**N6. Membership.** A season reports on every workshop it holds in scope and on no
other, and on every guild that owns at least one in-scope workshop and on no
other. A workshop that settled nothing is still reported on.

**N7. Identity.** Every smith a settled season names is named by the canonical
identity its identity events give it, and a season's per-smith figures are
gathered under canonical identities.

**N8. Determinism.** Settling the same season twice yields the same records, byte
for byte.

**N9. Uniqueness.** A season has exactly one settled state.
