# TODO deb4e4a (P12 fix of QL round 2, prompt master_chat_tasks/prompts/issued/tariff-engine-audit-repair/20261029T2050_fix.md)
OUT=/Users/mac/Desktop/Terminal Bench/master_chat_work/20261029_tariff-engine-audit-repair/p12_fix_ql2_deb4e4a
- [x] rename session (opencode listed ses_e779dae83ffemu9fiol2H4U2jQ; no explicit deb4e4a)
- [x] read COMMON_RULES_v5, round notes C/E/F/G, LEVER_RULES_v3, QC_RULINGS, QC_FIX_PLAYBOOK_v3
- [x] read TRIAGE.md; kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271
- [x] backup BUNDLE -> WORK/pushed_b0cd2c1813ba/ ; verify tree b0cd2c1813ba
- [x] Phase 0: QC_DEFENCE exists (check F3/F4 entries), xref_check 0 findings; trap baseline (ql1 kill table, same tests tree)
- [x] Phase 1: recheck 11 findings -> OUT/RECHECK_FIX.md rows
- [x] Phase 2a: F4 group kill in _run / statement run / ledger run
- [x] Phase 2b: F3 also run delivered tests/test_visible.py
- [x] Phase 2c: M4 TRUTH.md:188-191 wording
- [x] host probes: a5 zip passes F3 check; 9.31 copy fails; F4 grandchild killed; a5 zip + agent_program score 306/670 unchanged
- [x] trap survival: agent 364->364, bitset 364->364, tie_naive 145->145, first_write 482->482
- [x] slowest statement child (1.36 s oracle run) 8 threads --cpus 2 --memory 4g
- [x] touched rules, vacuity (0/670, 7/670 non-lever), side effects, stacking, xref, precheck CLEAN
- [x] Docker oracle x3 / owner / nop (once)
- [x] TRUTH sha by script last (truth_sha.py, values unchanged)
- [x] OUT deliverables RECHECK_FIX, PL_NOTE, KEPT, result json
- [x] sync Tasks_INPUT, tree shas
