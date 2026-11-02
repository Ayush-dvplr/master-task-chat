Checks made on the repaired package over the papers in /app/data.

Run: python3 -m daybreak --data /app/data --out /app/out wrote the
twenty eight derived documents and nothing else, created the missing
destination, and left the paper directory byte for byte as it found it:
all sixty sha256 sums of /app/data are unchanged after the run.

Two runs over one directory produced identical bytes, and the same cycle
under another directory name (/tmp/datacopy2) produced them again: the
two runs and the renamed run agree file for file.

The options were given in either order, --data before --out and --out
before --data, and both invocations produced the same bytes.

The shipped suite, carried through unchanged module for module and byte
for byte, passes: 13 tests, no failures, no errors.

The live workbook grid is grid_beta, matched on the key cell B1 =
HB-2034-231, which equals cycle_header.json.cycle_key byte for byte.
grid_draft (hb-2034-231) differs in case, grid_current (HB-2034-231 with
a trailing space) carries a space the cycle key does not, and grid_alpha
(HB-2034-231-SUPERSEDED) is superseded, so none of them is live.

The two digests were taken last, over bytes already written, and both
were recomputed from the written documents and agree with summary.json
and with the trailer lines of run_manifest.txt.

The mandatory reserve is 1431 basis points from the directive part C and
the reconciliation round cap is 3, the first binding counted as round
one, so r12 ran rounds two and three.

Every published whole quantity is an integer in the base unit its stage
names and the only published ratio, the utilisation ratio, is at twelve
decimal places; no document carries a negative zero and no document
carries a carriage return.

Reason counts below are the rows of this run's suppression_ledger.csv.

last_window_start_ms 82320000
set_aside CAPACITY_DISPLACED 99
set_aside COOLDOWN 14
set_aside DISPLACED_FINAL 9
set_aside FALLBACK_DISPLACED 23
set_aside GATE_CLOSED 4
set_aside IMPLAUSIBLE_DEMAND 8
set_aside NO_FALLBACK_FITS 58
set_aside OCCURRENCE_CAP_ZERO 2
set_aside OUT_OF_DAY 1
set_aside PREREQ_MISSING 51
set_aside PREREQ_WITHDRAWN 3
set_aside READMITTED 4
set_aside RETIRED_ROUTINE 35
set_aside SUPPRESSED 86
set_aside UNKNOWN_CEILING 4
set_aside UNRESOLVED_ACTION 3

The window with the greatest ordinal is W12, whose start is 82320000 ms; the
day ends at cycle_header.json.day_end_ms = 89820000 ms.

This cycle's derived state carries 33 keys and 85 actions fired in the
first state pass.
