# TODO 0d8cf26 (P12 fix of QC v3, prompt master_chat_tasks/prompts/issued/tariff-engine-audit-repair/20261029T1500_fix.md)

- [x] rename session (opencode listed ses_e78fad857ffe2j5nC79ZWnWdaZ; no explicit 0d8cf26)
- [x] read COMMON_RULES_v5, round notes C/E/F/G, LEVER_RULES_v3, QC_RULINGS, QC_FIX_PLAYBOOK_v3
- [x] read QC report v3, prev KEPT, LOSS_TABLE TRIP/HARDEN_REPORT, QC_DEFENCE, LEVERS
- [x] Phase 0: xref 0 findings before changes (78 entries); trap baseline = ql1 kill table (tree 7d8861ab1d7a = current tests)
- [x] Phase 1: RECHECK_FIX rows written (DS-22 REAL fix, TS-11 REAL fix, TS-20 FP keep, TS-26 FP keep)
- [x] Phase 2: TS-11 per-key memo lock in tests/test_output.py (G7 diff WORK/p12v3/G7_tests.diff)
- [x] LEVERS.md S1H "3 equal-amount pairs" -> 6
- [x] TS-11 measure 8 threads --cpus 2 --memory 4g: children==keys, slowest child, reward (before+after)
- [x] trap survival: agent 306 ok, k3/k4 identical; bitset/gcd_split/mitm_only/tie_naive pending chain4
- [x] DS-22 TRUTH.md prose: Verification Statements bullet + six pairs
- [x] TRUTH sha/count lines by script (truth_sha.py: unchanged; counts verified) - re-run only if TRUTH golden lines change
- [x] touched rules, vacuity (chain2 $R/vacuity.json), side effects | done: xref 0, precheck CLEAN, stacking identical (OUT/STACKING_CHECK.md)
- [x] Docker gates oracle x3 / owner / nop (1/1/1, owner 1, nop 0; trials plain__vwQbTos njiCky2 SNfoR4o, owner__jMouY47, nop plain__i5tT3X8)
- [x] OUT deliverables RECHECK_FIX, PL_NOTE, KEPT, result json
- [x] sync Tasks_INPUT, diff -rq empty, tree shas
- [x] TRUTH golden_score_trial_id -> plain__vwQbTos; truth_sha.py re-run last (sha unchanged); xref 0, PRECHECK CLEAN after
