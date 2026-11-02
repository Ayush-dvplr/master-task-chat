# PL note: match-replay-desync-audit, P12 v3 r6 (c45716e)

## False positives
None. All three v6 fails (IN-16, TS-16, CL-4) and the seven IN-17 sentences from the master scan were real and are fixed (OUT/RECHECK_FIX.md).

## Kept minors / warns
- W1 TS-23 / A3: 46 checks against a warn cap of 35 (`03_Tests_QC.md:62` "at most 35 (warn)"); tests_qc prints `WARN [A3] 46 checks; cap is 35 (warn)`. Kept by Ayush's ruling of 24 Oct 12:50 (no cap). Breakdown unchanged: 12 single-bit traps, 4 damage, 16 general, 2 mutation, 6 instance/format, 2 record/listing, 4 negatives; P = 172 positive, 20 negative.

## UNSURE questions
None.

## Notes for the reviewer
- CL-4 stays a REBUT: one-fact-wrong on the decoded-totals reading is 37/172 = 0.215, and instruction.md:13 now states "Each report is graded whole on fresh capture sets, and only an exact match counts" (FC:491). Per-lever one-fact-wrong rows are in RECHECK_FIX.md and WORK/QC_DEFENCE.md D11.
- The reads-supplied negative now plants decoy reports at /app/out during one fresh run and restores the originals afterwards; it fires only when the fresh report directory holds a planted figure.

## Lessons for the master
- A warn the owner has ruled on (TS-23 count) should be pre-filled into the QC override so it stops reappearing as a row | no change: master's v7 override already given.
