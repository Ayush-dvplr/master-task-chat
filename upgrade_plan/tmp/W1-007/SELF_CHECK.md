SELF CHECK W1-007

CONFIRMED (each line reopened from origin/main)
1. instruction.md:3 deliverable and run command; :5 contract sentence; :12 any DATA_DIR, no hard-coding; :17 7200 seconds.
2. schema.md:3 fixed variable, cohort and period orders, plus full-precision decimal means; :9 ledger records before and after; :15 fallback 1.0 and 0.0, floor and cap.
3. test_output.py:207-208 comment that number versus string is unspecified; :307-318 _same with strict types; :341-463 _write_corpus; :470-471 setpriv to nobody; :496 timeout=120; :759-789 Canto removal; :893-930 29-digit ledger value; :1100-1143 vega removal; :1295-1329 weights.
4. solve.py:20-23 fixed lists; :25 PPM float; :73 float(); :177 and :184-185 raw string before/after.
5. Opus reconcile.py:149-150 cohorts and periods from file names; :153-159 variables from rows; :184-185 float(before), float(after).
6. reward-details and ctrf: 14 passed and 21 failed, score 34 of 92; judge R4 and R8 lost, 10 of 16.
7. GLM run: an identical ctrf pass/fail list. Its trajectory shows "-rw------- 1 agent agent 22115 ... reconcile.py".
8. Local rerun in the scratchpad: test_output.py with a stub rewardkit and with _drop_priv_prefix replaced by an empty list, on the Opus reconcile.py and its shipped outputs. Result: everything passes except cohort_reports_carry_period_matrices, ledger_audit_records_exact and missing_diagonal_fallback_applied (plus negatives not firing).

UNCONFIRMED
1. The exact mode of the Opus /app/out/reconcile.py in the grader. Inferred from three facts: it was made with file_editor ("File created successfully at: /app/out/reconcile.py"); GLM's file from the same tool was 0600; the pass pattern is identical. No ls -l of the Opus file appears in its trajectory.
2. Whether the oracle solution scores 1.0 under the same privilege drop. No oracle run is in the tree. solve.sh copies the file with cp, so the mode depends on the umask.
3. My local repro without the privilege drop runs as root, not as the verifier container's user.
