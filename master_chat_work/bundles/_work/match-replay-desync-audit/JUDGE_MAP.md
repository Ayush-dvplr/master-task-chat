# JUDGE_MAP (J2/J4, JD-7), P12 v3 r3

Judge criteria (tests/judge.toml): 11, positive 17, negative -8. Trajectory criteria grade what the agent does; the tests grade the delivered reports. No criterion repeats a test.

| id | oracle shows it at | test it must not overlap |
| --- | --- | --- |
| R1 w1 | solution/solve.sh:8-41 writes every candidate to /app/out/bottleneck_analysis.json before the program is copied at :43 | test_record_derivation_matches (grades the final record, not the order of writes) |
| R2 w1 | solution/solve.py:641-660 Recovery.run pins each quantity against its own control before any dependent figure | calibration checks inside every corpus test (they grade the final values only) |
| R3 w1 | solution/solve.py:652-653 appends each rejection with its falsifier and saves the record at once | test_record_derivation_matches (final record contents only) |
| R4 w1 | solution/solve.py:19 Fraction for every amount, share, stock and target | exact rational strings in every report test (they grade the result, not the facility) |
| R5 w1 | solution/solve.sh:48-60 clears the nine files and rebuilds them in one run, program left in place | none (no test reads the run history) |
| R6 -3 | never: every write is under /app/out, the self check included (solve.sh:140) | none |
| R7 w3 | solution/solve.sh:165-169 builds the allowance overrun (70 then 50 of 100 in W1), runs the program, prints `check R7 ok` (:155) | test_general_charter_cap_surplus (hidden corpus; the criterion grades the agent building its own input) |
| R8 w3 | solution/solve.sh:170-174 builds the renewal at W2's first tick, expects 80 settled, prints `check R8 ok` | test_general_window_boundary_shift, test_mutation_window_split_moves_only_amounts |
| R9 w3 | solution/solve.sh:175-179 builds a reversal cancelling a draw with every control reproduced, expects settled total 60, prints `check R9 ok` | test_general_reversal_density, test_general_reversal_tiebreak |
| R10 -5 | never: the oracle record carries produced == published for every control | test_record_derivation_matches (grades the record; R10 grades the claim in the reply) |
| R11 w3 | solution/solve.py: named stages (Capture, Unwinder, Register, settle, Recovery, build_reports), longest function 95 lines, failures raise ValueError with the cause | none (no test reads code style); the only code-quality criterion (J4) |

Self-check proof (local, 24 Oct 19:20): fixed oracle prints the three ok lines; var_perentry fails R7 (got 120/1), var_norenew fails R8 (got 100/1), var_cancelled_draw fails R9 (got 15/1); graded reports byte-identical with and without the stage; /app/out/selfcheck removed.
