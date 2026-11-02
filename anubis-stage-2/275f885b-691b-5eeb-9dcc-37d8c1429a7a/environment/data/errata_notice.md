# Errata notice

This notice amends the contract tier. It takes effect from the opening of the first live round
of the campaign and binds for the whole campaign.

## Amendment one, to the section Rejects of data_quality_rules.md

The order of the reject codes is amended. `RC_EPOCH_GAP` applies before `RC_EVENT_CONFLICT`.
The amended order reads `RC_UNKNOWN_BLOCK`, `RC_WINDOW`, `RC_LATE_RECORD`,
`RC_WITHDRAWN_BLOCK`, `RC_EPOCH_GAP`, `RC_EVENT_CONFLICT`, `RC_NO_HEADCOUNT`.

## Amendment two, to the section Remainder of ration_rules.md

The order in which remainder doses are granted is amended. The doses are granted one each to the
claims whose claimable quantity exceeds their grant, taking the claims in ascending block
identity order. The sentence naming descending claimable quantity is replaced by this sentence
and binds nowhere.
