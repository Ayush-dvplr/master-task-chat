Follow-up to P12 r2 (board f6164ef, cohort-retention-reconciliation). Same session, same rules as P12_r2.md. Do not change any bundle file unless step 4 says so.

Why: your AL-27 fix changed `_study_files` in tests/test_output.py, so every hidden study changed, and the single-lever losses were not re-measured. New rule (knowledge/QC_FIX_PLAYBOOK.md section 3, trap-survival check) applies.

1. Before: build or reuse one solve.py variant per wrong reading in harden_r2 STACKING_CHECK.md (L1a L1b L2none L2a L2b L2c L3a L3b L4a L4b), each with exactly that one wrong reading. Score each on the tests as they were BEFORE P12 r2 (`/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_cohort-retention-reconciliation/harden_r2` state; rebuild the old test_output.py from the backup or git-free copy you kept, otherwise from the diff you made).
2. After: score the same variants on the current tests/test_output.py.
3. PASS when every reading keeps at least 90% of its before loss, reflex <= 0.20 and <= before + 0.05, and no separating hidden case is gone.
4. FAIL: compensate in the same lever family (playbook section 4), re-measure, max 2 tries, else stop with `PAUSED: trap <L> <before> -> <after>`. If you change tests/, run the Docker block from P12_r2.md step 6 again.
5. Add a `## Trap survival` table to `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_cohort-retention-reconciliation/p12_r2/RECHECK_FIX.md` (reading, before loss of 71, after loss of 71, ratio, separating cases kept y/n, verdict) and add "trap_survival":"PASS|FAIL","lever_loss":{"<reading>":[before,after]} to result_f6164ef.json. It must parse.
