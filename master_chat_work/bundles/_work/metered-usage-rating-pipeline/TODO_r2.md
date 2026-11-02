# TODO e2dc50b metered-usage-rating-pipeline harden r2 (prompt: master_chat_tasks/prompts/issued/metered-usage-rating-pipeline/20261024T2317_harden.md)
(r1 list kept as TODO_r1.md.)
- [x] Session rename (list showed ses_e90f61009ffe2dOV9L2dzi3Q8F, not e2dc50b; noted, not retried)
- [x] Required reading: COMMON_RULES_v3, round notes C/E/F/G, LEVER_RULES_v1, LEAK_LIBRARY, QC_RULINGS, QC_FIX_PLAYBOOK_v2, DESIGN, LEVERS, XREF, TEST_DEPTH 21-67, fuzz kit
- [x] P1.1 Phase A genuine check
- [x] P1.2 Root causes 1-4
- [x] P1.3 Lever table from reward-details + trajectory
- [x] P1.4 Trajectory autopsy
- [x] P1.5 Save agent program to OUT/agent_program/
- [x] P1.6 Fuzz kit copy to OUT/fuzz, adapt (4-col accounts, r1 lever mutations), run >=300 corpora on probe-2 program
- [x] P1.7 Lever proposals (scratch prototypes, shrunk corpora)
- [x] P1.8 LEAK_LIBRARY rows; write OUT/DIAGNOSIS.md, STOP "DIAGNOSIS READY"

## Phase 2 (go 25 Oct 00:39 IST: A, B, C with master changes 1-5)
- [x] P2.1 gen_core: bound _gen_rate 1000 tries; prove byte-identical gen_month for seed 461927 and 58213
- [x] P2.2 rating_contract.md: A credit re-share (F2 wording), B recursive billing group, C minimum true-up ("in proportion to charge, rounded half-even")
- [x] P2.3 ref_core: A, B, C
- [x] P2.4 gen_core: commitments minimum; hidden plants (A sep regions, branch-1 region, C shortfall regions, B chains depth 2-3); shipped non-separating; asserts
- [x] P2.5 solve.py (oracle) A, B, C; datagen regen; diff shipped data vs before
- [x] P2.6 tests_template + assemble: true_up_<r> family, credit family owns plan+credit; mutation tests; reassemble
- [x] P2.7 check_exact, cost_table (alone + one-fact-wrong A, B, C separately), rule_coverage
- [x] P2.8 judge.toml R16 -> re-share recompute; solve.sh check lines; JUDGE_MAP
- [x] P2.9 TRUTH.md, DESIGN, LEVERS, QC_DEFENCE, XREF; xref_check 0
## Phase 3
- [x] P3.1 fuzz generator 300 seeds no loop; lever fuzz on agent program (differs per lever)
- [x] P3.2 stacking_check -> OUT/STACKING_CHECK.md; reflex gate agent_program <= 0.20
- [x] P3.3 QC scripts + validator + precheck CLEAN
- [x] P3.4 Docker block (oracle x3, owner-only, nop, stub, forgery)
- [x] P3.5 HARDEN_REPORT.md + result_e2dc50b.json
