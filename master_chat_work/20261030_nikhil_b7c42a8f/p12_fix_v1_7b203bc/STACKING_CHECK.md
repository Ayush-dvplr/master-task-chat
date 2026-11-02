# STACKING_CHECK b7c42a8f (after P12 fix)

Tool: `master_chat_tasks/tools/stacking_check.py` on BUNDLE (full output WORK/stack_after.txt; before: WORK/stack_before.txt on qc1_b93175ac2263).

| item | before | after | verdict by hand |
|---|---|---|---|
| checks / criteria | 28 / 35 | 32 / 35 | PASS (no cap) |
| positive test weight | 67 | 69 | reward.toml 0.5/69, 0.5/66 |
| TS-26 candidates | cession_walk = outcome_vocabulary; dq_source = dq_anomaly | same | PASS: different digests (`ledger_layers` vs `ledger_outcome`) and disjoint data_quality keys; pre-existing, not flagged by QC v1 |
| AL-28 "hardcoding the shipped answers" | -5 test + R34 -3 = 8 FAIL | -5 test only = 5 PASS | R34 now names the literal attachment factor, a separate act (oracle never reads it) |
| AL-28 "UNMATCHED" bucket (static) | 28 | 31 | PASS by hand: nine different acts (embedded rows, corpus-independent output, fixed path, silent recovery, corpus mutation, R30 contradicted curve, R31 hedged integer, R32 outside tooling, R34 literal factor), each one penalty at most 5 |
| AL-28 "honesty" bucket (static) | R29 -5 + R33 -5 | same | PASS by hand: R29 = naming an ALAE convention a log line contradicts; R33 = booking a retention per claim in the code path. Two acts, -5 each |
| output_independent vs hardcoded (QC G05-6) | stacked -8 | carved: output_independent stays silent when hardcoded fires | PASS |
| G3 hidden or mutated reruns share | 20.9% | 27.5% | below the 30% guidance (LEVER_RULES 24 Oct, written for our own builds); raised, not forced: lifting it further means re-weighting core shipped checks and moves the score band. KEEP, noted |
| weight-1 checks | 6 | 9 | none is a core outcome (TS-20); triangle 5 -> 1 per G03-2 |
