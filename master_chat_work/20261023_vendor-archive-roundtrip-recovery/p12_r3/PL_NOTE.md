# PL note: vendor-archive-roundtrip-recovery (QC v5, round P12 r3)

Fixed: DS-4-1 (catalog ids are now one neutral form, cap-00001 to cap-17700), JD-15-1 (R5 relabelled agent behavior), TS-16-1 (the rebinds negative now also checks what decode.py and encode.py write while they run, so it can fire in separate mode).

## False positives
None.

## Kept minors and warnings
- DS-20-1: kept. No graded input reaches it; the contract routes damaged frames to the salvage path (format_contract.md:175-176).
- DS-6-1: kept. Cosmetic; the unit column is never graded, and regenerating units would touch every layout for no grading gain.
- X1: kept. The three .varc files are genuine binary captures of the invented format; the script skips binary files by design.

## Questions
None.
