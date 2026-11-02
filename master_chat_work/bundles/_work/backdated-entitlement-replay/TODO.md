# TODO backdated-entitlement-replay (board 99230f0)

## Phase 0 (stop at DESIGN READY)
- [x] 0.0 rename session (opencode ses_e6f3f18e3ffeWNo8rto5hQJcuN; codex: no match)
- [x] 0.0 read rules in order (COMMON v5, LEVER v3, LEAK, QC_RULINGS, PLAYBOOK v3, KNOWLEDGE, checks.json)
- [x] 0.1 GEN + QC fingerprints match (12:34)
- [x] 0.2 PREMORTEM.md (12:43)
- [x] 0.3a prototype core (WORK/kill/core.py, variants) + generator (WORK/kill/gen.py)
- [x] 0.3b kill test in Docker -> KILL_TEST.md
- [x] 0.3c DESIGN.md + BRANCH_FIRE.md
- [x] 0.4 QC_DEFENCE.md
- [x] 0.5 DESIGN_SUMMARY.md (<=40 lines, G-7 pilot table)
- [x] 0.6 STOP: DESIGN READY

## Phase 0b (after go)
- [x] proto solve/gen, design_blind folder, BRANCH_FIRE on sample+3 seeds, STOP DESIGN BLIND READY (14:38)
- [x] blind 1861cfe scored (14:58): EXACT 41/41, lever lost 0% -> NO CORE; stop

## Phase 1-9
- [ ] 1 scaffold (generator, copy to scaffold_orig)
- [ ] 2 datagen + spec docs
- [ ] 3 solve.py/solve.sh + check_exact.py + override-removal probe
- [ ] 4 tests + COST_TABLE + RULE_COVERAGE + EVIDENCE_MAP + UNIQUENESS + LEVERS + reward.toml
- [ ] 5 judge.toml + JUDGE_MAP
- [ ] 6 instruction.md
- [ ] 7 TRUTH.md
- [ ] 8 QC scripts, validator, oracle x3/nop, STACKING, SELF_CHECKS, PRECHECK CLEAN
- [ ] 9 BUILD_REPORT.md + result_99230f0.json
