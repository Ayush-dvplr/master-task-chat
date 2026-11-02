# TODO 7f1d771 tariff-engine-audit-repair (P9 harden r2, Phase 2+3)
Prompt: master_chat_tasks/prompts/issued/tariff-engine-audit-repair/20261025T1402_harden.md
(r2 phase-1 TODO archived: TODO_r2p1_0dd7a8c.md)
OUT: master_chat_work/20261025_tariff-engine-audit-repair/harden_r2_p2_7f1d771

## Phase 0
- [x] date; rename session 7f1d771 (opencode ses_e8dc62e62ffeYF3KhEguCguAye listed; codex no match)
- [x] read COMMON_RULES_v3, round notes C/E/F/G, LEVER_RULES_v2, LEAK_LIBRARY, QC_RULINGS, QC_FIX_PLAYBOOK_v2, DIAGNOSIS
- [x] read WORK DESIGN, LEVERS, QC_DEFENCE, XREF, COST_TABLE, RULE_COVERAGE, JUDGE_MAP
- [x] kit HEAD recorded (5574d77e); OUT dir; copy proto/fuzz_r2 to OUT
## Phase 2
- [x] read bundle: instruction, contract, data shapes, test_output structure, datagen/refengine/solve
- [x] L11 shortlist (2-4) + UNIQUENESS fits -> pick, written to LEVERS.md + UNIQUENESS.md
- [x] implement: data witness (datagen shipped + hidden generator plants fresh witness), refengine, solve.py, tests (owned rows + mutated rerun), judge w3
- [x] instruction edits (line 1 IN-17 cut, line 13 G5 clause); W9 literal read
- [x] common rule 6 (embed, reward.toml, TRUTH sha last)
- [x] COST_TABLE measured (L11 alone 25-45%, one-fact-wrong), RULE_COVERAGE (+L11 mutant), EVIDENCE_MAP.md, QC_DEFENCE, JUDGE_MAP, DESIGN, XREF (0 findings)
## Phase 3
- [x] stacking_check -> OUT/STACKING_CHECK.md
- [x] precheck CLEAN (0 IN17/G5 warns)
- [x] 4 QC scripts + validator 0 FAIL; kit diff 976c1666..5574d77e checks PASS/FIXED
- [x] warm image + one Docker block (oracle x3, owner-only, nop, stub, forgery) ALL_DONE
- [x] sync Tasks_INPUT, diff -rq empty
- [x] HARDEN_REPORT.md + result_7f1d771.json
