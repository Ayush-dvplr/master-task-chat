# SELF_CHECKS (harden r2, bddb388)

## Vacuity probe (G5)

The unedited shipped engine (`engine_orig`) run through every positive check of the final
tests: 2 of 110 (the two structural checks only), every other check WRONG. Log:
`_runs/20261101/slipway-overhaul-replan-repair/harden2-114714/kill5_engine_orig.log`, score5.log.

## TS-16 negatives

The seventeen test negatives and their detectors are byte-identical to the bundle before this
harden (weights unchanged). Oracle run: none fires (tests channel 0.5 of 0.5 in vt2_oracle).

## Promise table

| promise (instruction.md) | where graded |
|---|---|
| :9 deliver /app/out/patched_engine.zip, run as `python3 -m slwopt` | delivered_package_shape, every package_* check drives it |
| :11 the documents under /app/out | delivered_documents_present_and_parse, shipped_* |
| :13 exact schema and rounding where the stage paper places it | shipped_*, package_* whole-document byte compare |
| :17 graded on rounds you have not seen | package_eval/challenge/probe, twelve package_crosswalk_* |
| :19 quiet branches implemented from the stage papers | twelve package_crosswalk_* (legacy identifiers, p01:19-22) |
| :21 final message items | judge R3 (amendments reaching no cell); others not graded as figures (J1) |

## Literal table

No graded literal is fitted to the shipped round: held-out seeds come from `child_seed`, every
expected document from the reference in tests/test_output.py. The oracle's repairs DFC-16..27 carry
no round figures (solution/solve.py REPAIRS).
