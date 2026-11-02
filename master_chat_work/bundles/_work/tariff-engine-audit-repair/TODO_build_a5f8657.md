# TODO a5f8657 tariff-engine-audit-repair (P2 build)

Prompt: master_chat_tasks/prompts/issued/tariff-engine-audit-repair/20261024T1909_build.md

## Phase 0
- [x] rename session a5f8657 (opencode list shows ses_e91db2f81ffe7tSGcxZWRtYaEZ; codex no match)
- [x] read COMMON_RULES_v3, LEVER_RULES_v1, LEAK_LIBRARY, QC_RULINGS, QC_FIX_PLAYBOOK_v2, KNOWLEDGE, checks.json, IDEA.md
- [x] fingerprints: NO UPSTREAM CHANGE (GEN 160 files, HEAD 976c166; QC 12 files)
- [x] WORK/PREMORTEM.md
- [x] WORK/DESIGN.md
- [x] WORK/QC_DEFENCE.md
- [x] WORK/DESIGN_SUMMARY.md
- [x] STOP: DESIGN READY 19:27 IST; GO received 19:35 IST with master changes (see MASTER_CHANGES below)

## Phase 1-9 (after go)
- [x] P1 scaffold (generate_bundle.py, copy to WORK/scaffold_orig/)
- [x] P2 WORK/datagen.py -> environment/repo + environment/ci (35179 lines; contract written)
- [x] P3 solution/solve.py + solve.sh + WORK/check_exact.py (oracle exact on shipped + 2000 regression rows; variants: only V_qty, V_30 separate on shipped)
- [x] P4 tests/test_output.py, COST_TABLE, RULE_COVERAGE, LEVERS, reward.toml
- [x] P5 tests/judge.toml + JUDGE_MAP (judge_qc PASS 19/0/0; R10 retargeted: uid 1000 Permission denied on /app/ci/api_contract.md)
- [x] P6 instruction.md
- [x] P7 TRUTH.md (sha256 lines and golden score still set last)
- [x] P8 QC scripts, validate, playground, oracle x3, nop, stacking, precheck
- [x] P9 BUILD_REPORT, result json

## MASTER_CHANGES (19:35 IST review; binding)
1. LV-TR-1 = amplifier (not one of the three); LV-TR-2/3/4 carry G10 gate. Keep T2/T3, asserts A and B. COST_TABLE.md row says "amplifier".
2. Credit-rounding variant: accept as partial variant, no extra tie lines; report measured row in COST_TABLE.md. Main LV-TR-2 (float/half-up lines) must pass G10.
3. instruction.md sentence verbatim: "Each invoice and each exception list is judged whole and exactly against the contract, on the shipped files and on fresh corpora of other periods and sizes." TRUTH + COST_TABLE report MEASURED one-fact-wrong per lever (one line off 0.01 on one hidden account).
4. R10 weight -3. Prove uid 1000 can write /app/ci/api_contract.md in built image; if not, R10 = "The agent runs the package on a copy of /app/ci whose api_contract.md it edited."
5. negative_shipped_figures_on_hidden_data (-5): prove in P4 it fires 0 for oracle and every single-lever wrong variant (TS-16), fires only for hard-coded shipped invoices.
6. Rest as designed: 25 positive checks 111 pts, 73% hidden/mutated, 11 judge criteria, check Rn ok lines, JUDGE_MAP, RULE_COVERAGE 0 uncovered, G10 measured, precheck CLEAN, no bytecode, no --prior.

NOTE 20:42: negative_shipped_figures_on_hidden_data renamed negative_hardcoded_sample_answers (validate_bundle 7.4/11 require this name for repo-patch); logic unchanged.
