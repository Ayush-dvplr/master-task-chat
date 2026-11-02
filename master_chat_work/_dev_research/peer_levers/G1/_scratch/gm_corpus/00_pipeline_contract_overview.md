# Pipeline Contract Overview

The settlement runs nine stages S1..S9. They interact: an early choice
about which match attempts survive and which epoch anchors them changes the
later unit, labeling, weighting, calibration, interval, and payout figures.
The obvious reading of several stages is the wrong one; correct the
computation.

- **S1 Match canonicalization** - reduce raw match attempts to one canonical
  row per match key; drop match keys that never sealed.
- **S2 Anchoring & verdicts** - anchor on the FIRST attempt; resolve the
  ladder verdict within the maturation window by review sequence.
- **S3 Running ladder baseline** - fold the previous resolved baseline per
  frozen stratum in ascending match_key order.
- **S4 Reward-unit canonicalization** - convert loot to integer ledger units;
  the ore gain lives ONLY in the spreadsheet.
- **S5 Two-level rarity weights** - base rate and nonresponse on DIFFERENT
  partitions; inflate before trim; trim to cap; quantize residue.
- **S6 Calibration & decision** - calibrate in log-odds space with the LIVE
  sheet parameters; decide with an inclusive per-stratum threshold.
- **S7 Weighted metrics** - precision/recall/F-beta as ratios of weighted
  totals; macro is a weight-share-weighted mean.
- **S8 Uncertainty & payout** - Wilson intervals on Kish effective N;
  review cost, beta and z live ONLY in the policy PDF.
- **S9 Levy & floor** - apply the smurf levy then the settlement floor; both
  constants live ONLY in the levy addendum DOCX.

Load-bearing constants that appear in NO plaintext file:
- the GOLD ore-to-ledger gain (spreadsheet LIVE sheet),
- the manual-review unit cost, F-beta beta, and CI z (policy PDF),
- the smurf levy basis points and settlement floor (levy addendum DOCX).

The exact shape of every output artifact (the column headers of each table,
the key names of each JSON object, the line layout of each text and XML
file, the row order and the per-field precision) is written in
output_artifact_schemas.md. Read it before emitting anything.
