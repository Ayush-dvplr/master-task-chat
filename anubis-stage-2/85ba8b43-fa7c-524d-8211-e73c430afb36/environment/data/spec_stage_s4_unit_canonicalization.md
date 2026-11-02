# S4 Reward-Unit Canonicalization

Convert each canonical `raw_loot` to integer ledger units using the scale
exponent of its `loot_currency`: CRD=0, TKN=3, GLM=6 (multiply raw by
10**exponent). `ORE` (raw ore counts) has NO plaintext exponent; multiply by
the ore-to-ledger gain published only on the spreadsheet LIVE sheet. Then
multiply by the latest season-patch drift multiplier for the unit family dated
on or before the anchor date. The supplied reference book contains an eligible
entry for every graded anchor. Round half-to-even to an integer at the
ledger-unit stage.
