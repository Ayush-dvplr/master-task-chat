# Finding codes

A season records a finding against an entry whenever one of the conditions below
holds of that entry. The codes are listed in alphabetical order; that order
carries no meaning and no code ranks above another.

- `CAP_REACHED` - the entry is a forge that was not settled because its workshop
  had already reached its charge cap, or because settling it would have carried
  the workshop past that cap.
- `MISSING_FORGE_REF` - the entry is a salvage naming a forge entry the ledger
  does not hold.
- `OUT_OF_SCOPE_WORKSHOP` - the entry was filed against a workshop the season does
  not hold in scope.
- `RETIRED_REAGENT` - the entry is a forge whose governing recipe edition has
  a line for a reagent retired on or before the day of the entry.
- `RETIRED_SMITH` - the entry was filed by a smith whose canonical identity had
  been retired on or before the day of the entry.
- `SALVAGE_ALREADY_CREDITED` - the entry is a salvage naming a forge entry that an
  earlier salvage of the season has already been credited against.
- `STOCK_FLOOR` - the entry is a forge whose draw would have taken a reagent's
  vault balance below zero.
- `UNCREDITED_SALVAGE` - the entry is a salvage whose named forge does not fall in
  the salvage credit window.
- `UNRESOLVED_EDITION` - no recipe edition governs the entry.

Not every code is exercised by every season.

## What a finding carries

Every finding names the entry it concerns, the code of the condition, and one
further detail that says which thing the condition was about. Which thing that is
depends on the code:

- `CAP_REACHED` - the workshop that had reached its cap.
- `MISSING_FORGE_REF` - the forge reference the salvage named.
- `OUT_OF_SCOPE_WORKSHOP` - the workshop the entry was filed against.
- `RETIRED_REAGENT` - the retired reagent. Where the edition has lines for more
  than one retired reagent, the detail names the first of them in ascending
  reagent order.
- `RETIRED_SMITH` - the canonical identity that had been retired.
- `SALVAGE_ALREADY_CREDITED` - the forge entry that had already been redeemed.
- `STOCK_FLOOR` - the reagent whose balance the draw would have taken below zero.
  Where the draw would do that to more than one reagent, the detail names the
  first of them in ascending reagent order.
- `UNCREDITED_SALVAGE` - the forge entry the salvage named.
- `UNRESOLVED_EDITION` - the artifact the entry named.
