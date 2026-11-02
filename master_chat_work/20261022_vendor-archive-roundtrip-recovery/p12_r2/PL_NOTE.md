# P12 r2 PL note: vendor-archive-roundtrip-recovery (board 8ea6d8d)

QC report: QC_2026-10-21/qc_report/vendor-archive-roundtrip-recovery/v3.md (kit 3fb1650b, same as live).

## False positive rebuttals
None. All four v3 findings are real.

## Kept minors (with reason)
- TS-16 warn, `negative_rebinds_verifier_dependencies` cannot fire in separate mode. True, it is dead: only the six declared artifacts are uploaded and the programs run as staged copies under `python -I`. Kept because an honest agent can never trip it (TS-16 fails only negatives an honest solution could trip), and validate_bundle.py section 11.5 in strict mode fails the bundle without it. It pays nothing and costs nothing.

## Process note (not a bundle defect)
- The v3 sign-off asks for oracle x5. Ayush's standing decision is oracle x3; this round ran x3.

## UNSURE questions
None.
