# TODO 78d433c test-hardening (prompt: master_chat_tasks/prompts/issued/tariff-engine-audit-repair/20261026T1926_harden.md)
OUT=/Users/mac/Desktop/Terminal Bench/master_chat_work/20261026_tariff-engine-audit-repair/harden_t1
- [x] session renamed 78d433c (opencode listed)
- [x] read rules files, WORK docs; baselines.json absent
- [x] Phase A diff -rq identical; QC kit 5574d77e
- [x] Phase 1 OUT/DIAGNOSIS.md written (Q1 estimated, Q2 standing_changes, Q3 several billing rows, Q4 allowance carry, Q5 several meter rows)
- [x] WAIT for "go" (go 21:15 with 7 changes)
- [x] P2 baseline snapshot (OUT/baseline/ref_before.json via WORK/snapshot.py; embed.py reproduces bundle byte-for-byte): reference documents for all existing corpora + shipped saved BEFORE edits (Q3 byte-unchanged proof)
- [x] P2 contract sentences + toy examples (api_contract.md)
- [x] P2 reference _Ledger extended; _quiet planting + _assert_quiet; ownership in checks; 5 new criteria
- [x] P2 solution solve.py implements Q1-Q5; embed; reward.toml
- [x] P2 run_checks oracle = 100; mutants per rule (69/69 killed, mutants_fix.json); cost table
- [x] P2 WORK docs (xref 3 findings pending TRUTH rewrite): EVIDENCE_MAP (row per Q), UNIQUENESS (Q1 either order), LEVERS, BRANCH_FIRE, RULE_TRACE, COST_TABLE, RULE_COVERAGE, QC_DEFENCE, DESIGN, XREF; xref_check 0
- [x] P3 stacking_check, precheck, QC scripts, validator
- [x] P3 docker block (oracle x3, owner, nop, stub, forgery)
- [x] P3 TRUTH.md last (N3 position + L11 per row), Tasks_INPUT sync, report, result json
- [x] STOP at "BUILD READY: <bundle>" (no harness probe)
