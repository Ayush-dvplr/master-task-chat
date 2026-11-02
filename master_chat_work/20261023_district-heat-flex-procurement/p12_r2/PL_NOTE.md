# PL note: district-heat-flex-procurement (P12 r2, after QC v4 53c71e3)

## False positives
None. All 4 fails and all 3 minors of QC v4 were real and are fixed.

## Kept minor (1)
- TS-23 / tests_qc A3, 38 checks against the warn line of 35: kept. Our team cap is 70 checks, and 38 is a warning, not a fail. The QC fix merges four small format checks into one, but those four grade four different things (files exist and parse, integer types, key sets, array order). Merging them would make one check grade several properties, which TS-13 forbids. No rule is hidden; nothing about the agent's task changes.

## Fixed, with one change of wording from the QC suggestion
- JD-18 (no code quality criterion): we added R9 "keeps reading the input files, choosing the portfolios, computing the credits and grants, and writing the reports in separate named functions" at weight 1. QC proposed one criterion at weight 3 that also covered dead blocks, bare except and debug prints. We kept one named, positive property so that the criterion grades one thing (JD-5) and is not absence-shaped (JD-15). The oracle solve.py meets it (JD-7).

## Unsure
None.
