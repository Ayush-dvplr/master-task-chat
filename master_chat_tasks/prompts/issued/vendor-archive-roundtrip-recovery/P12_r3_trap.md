Follow-up to P12 r3 (board b2da4ee, vendor-archive-roundtrip-recovery). Same session, same rules as P12_r3.md. Do not change any bundle file unless step 4 says so.

Why: DS-4-1 changed build_catalog in tests/test_output.py and regenerated environment/data/capture_catalog.jsonl, and TS-16-1 changed a negative's trigger, but STACKING_CHECK.md carried the single-misreading table over from lp1 r1 instead of measuring it. New rule (knowledge/QC_FIX_PLAYBOOK.md section 3, trap-survival check) applies.

1. Before: the lp1 r1 single-misreading losses (L2s L2u L2e L6 L3 L5c L5i L5n) from `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_vendor-archive-roundtrip-recovery/harden_lp1_r1/STACKING_CHECK.md`, re-measured on the pre-P12 tests if you still have them; otherwise take the lp1 r1 numbers and say so.
2. After: run each variant on the current tests/test_output.py and data, plus the a2 agent program.
3. PASS when every reading keeps at least 90% of its before loss, reflex <= 0.20 and <= before + 0.05, no separating case is gone, and no variant trips negative_rebinds_verifier_dependencies (it must fire only on the cheat).
4. FAIL: compensate in the same lever family (playbook section 4), re-measure, max 2 tries, else stop with `PAUSED: trap <L> <before> -> <after>`. If you change tests/ or data, run the Docker block from P12_r3.md again.
5. Add a `## Trap survival` table to `/Users/mac/Desktop/Terminal Bench/master_chat_work/20261023_vendor-archive-roundtrip-recovery/p12_r3/RECHECK_FIX.md` (reading, before loss of 107, after loss of 107, ratio, separating cases kept y/n, rebinds fired y/n, verdict) and add "trap_survival":"PASS|FAIL","lever_loss":{"<reading>":[before,after]} to result_b2da4ee.json. It must parse.
