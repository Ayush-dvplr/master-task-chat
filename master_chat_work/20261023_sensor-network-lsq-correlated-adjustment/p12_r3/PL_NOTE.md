# PL_NOTE: sensor-network-lsq-correlated-adjustment (P12 r3, board 078d40a)

## False positives

- X1 (structure_qc.py WARN, QC v2.md:44, :80): the script skips 5 binary files. They are genuine binary containers the task ships as inputs, and QC v2 already checked their text by hand (v2.md:80, DS-7). Nothing to change; kept.

## UNSURE

none

## Lessons for the master

- A script WARN that QC itself resolved by hand in the same report is a false positive at our side, not a finding to fix.
