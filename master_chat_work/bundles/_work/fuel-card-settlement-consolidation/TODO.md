# TODO (board 60e9db0, fuel-card-settlement-consolidation)
Prompt: /Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/fuel-card-settlement-consolidation/20261026T1750_build.md

## Phase 0
- [x] rename session (name_session.py ran; list showed opencode ses id only)
- [x] read required docs 1-5
- [x] 0.1 fingerprints GEN + QC (0 diffs)
- [x] 0.2 PREMORTEM.md
- [x] 0.3 DESIGN.md + BRANCH_FIRE.md
- [x] 0.4 QC_DEFENCE.md
- [x] 0.5 DESIGN_SUMMARY.md
- [x] 0.6 DESIGN READY issued; "go" received 18:15 with master changes 1-6 (see DESIGN.md section 8)
## Phase 0b
- [x] 0b.0 apply master changes 1-6 to DESIGN.md / QC_DEFENCE.md
- [x] proto solve/gen + design_blind folder
- [x] BRANCH_FIRE on sample + 3 seeds
- [x] STOP: DESIGN BLIND READY
- [x] DESIGN_BLIND.md after master returns blind program (blind exact on shipped + 3 seeds -> redesign)
- [x] R2 redesign: DESIGN.md s9, PREMORTEM s6, QC_DEFENCE D12-D13, BRANCH_FIRE R2 rows, DESIGN_SUMMARY R2
- [x] STOP: DESIGN READY (R2) issued 21:35
- [x] on go: extend gen/proto with R43, U1-U5, Q16; asserts for unstated cases; regenerate; BRANCH_FIRE measured; refresh design_blind; DESIGN BLIND READY (2nd read)
- [x] COST_TABLE design stage (proto) 21:58
- [x] DESIGN_BLIND.md section for 2nd read (blind exact again -> STOP, DESIGN BLIND EXACT, Ayush decides)
## Phase 1-9
- [ ] P1 scaffold + scaffold_orig
- [ ] P2 datagen + docs
- [ ] P3 solve.py/solve.sh + check_exact.py
- [ ] P4 tests + COST_TABLE + RULE_COVERAGE + EVIDENCE_MAP + LEVERS + reward.toml
- [ ] P5 judge + JUDGE_MAP
- [ ] P6 instruction.md
- [ ] P7 TRUTH.md
- [ ] P8 QC scripts, validator, oracle x3, nop, stacking, precheck
- [ ] P9 BUILD_REPORT + result json
