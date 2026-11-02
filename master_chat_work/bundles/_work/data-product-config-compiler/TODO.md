# TODO 13a9939 data-product-config-compiler

## Phase 0
- [x] P0.0 rename session (name_session.py 13a9939: opencode ses_e91d07e10ffeL1KsK0NZMTDQp0 renamed; codex no match)
- [x] P0.0 read rule files in order (COMMON_RULES_v3, LEVER_RULES_v1, LEAK_LIBRARY, QC_RULINGS, QC_FIX_PLAYBOOK_v2, KNOWLEDGE, checks.json, IDEA)
- [x] P0.1 GEN and QC fingerprints match (160 + 12 files, HEAD 976c166)
- [x] P0.2 PREMORTEM.md
- [x] P0.3 DESIGN.md
- [x] P0.4 QC_DEFENCE.md
- [x] P0.5 DESIGN_SUMMARY.md
- [x] P0.6 STOP: "DESIGN READY"; go received 19:58 with master points 1-7 (see LOG)

## Phase 1
- [x] P1 generate_bundle.py scaffold (no --force), copy to WORK/scaffold_orig/

## Phase 2
- [x] P2 WORK/datagen.py -> BUNDLE/environment/data/ (14 files, tool/ sources), A5 line count

## Phase 3
- [x] P3 solution/solve.py, solve.sh, selfcheck; WORK/check_exact.py; override-removal probes

## Phase 4
- [x] P4 tests/test_output.py (34 checks, P=125), wrong impl per lever, COST_TABLE, RULE_COVERAGE (47 rows, 0 uncovered), LEVERS, reward.toml test_output 0.004 (judge weight set in P5)

## Phase 5
- [x] P5 tests/judge.toml (12 criteria, pos 28, neg -8), JUDGE_MAP.md, reward judge 0.5/28

## Phase 6
- [x] P6 instruction.md (1856 chars, arbiter, G5 whole-doc sentence, 7200 s)

## Phase 7
- [x] P7 TRUTH.md via write_truth.py (rerun after any tests/solution edit)

## Phase 8
- [x] P8.1 4 QC scripts + validator, A5
- [x] P8.2 oracle x3 / nop
- [x] P8.3 stacking_check + OUT/STACKING_CHECK.md
- [x] P8.4 precheck CLEAN

## Phase 9
- [x] P9 OUT/BUILD_REPORT.md, OUT/result_13a9939.json, fingerprints re-check

# HARDEN r1 e317de1 (prompt prompts/issued/data-product-config-compiler/20261024T2317_harden.md)
- [x] H0 rename session e317de1 (opencode ses_e90f63451ffeTMRcjC3yqIVLf4; codex no match); read rule files
- [x] H1 Phase A genuine check (diff copy vs BUNDLE, result.json, verifier stdout)
- [x] H2 lever table from reward-details + trajectory autopsy (steps, self-tests)
- [x] H3 save agent program OUT/agent_program/
- [x] H4 fuzz kit copy to OUT/fuzz, adapt, run >=300 corpora on probe program, differing share per lever
- [x] H5 replacement lever prototypes + shrunk differing corpora
- [x] H6 OUT/DIAGNOSIS.md, STOP "DIAGNOSIS READY" (waiting for master go)
- [x] Phase 2 (after go 00:39)
  - [x] P2a ref_core/gen_core/contract/solve.py/tests/judge/reward for NL-1, NL-3, NL-4
  - [x] P2b gates oracle 120/120, nop 0, probe 0.175; fuzz r3; rule coverage uncovered 0
  - [x] P2c COST_TABLE, JUDGE_MAP, QC_DEFENCE, DESIGN, XREF.md
  - [x] P2d cost_table rerun, LEVERS.md regen, TRUTH.md regen, xref_check 0
- [x] Phase 3 (after go)
  - [x] P3a test.sh format, _grant_read, no __pycache__
  - [x] P3b stacking_check -> OUT/STACKING_CHECK.md
  - [x] P3c reflex gate with real rewardkit/stub (done locally 0.175; record)
  - [x] P3d 4 QC scripts, validator, playground static, precheck CLEAN
  - [x] P3e Docker block: oracle x3, owner-only, nop, stub, forgery
  - [x] P3f HARDEN_REPORT.md + result_e317de1.json

# HARDEN r2 8e4df45 (prompt prompts/issued/data-product-config-compiler/20261025T0715_harden.md)
- [x] R0 rename session 8e4df45 (opencode ses_e8f436f63ffegPezAPXiI4JSmI; codex no match); read rule files
- [x] R1 Phase A genuine check: GENUINE (exception_info null, staged diff = allowed_hosts + .kiro-staged-from, judge 37/37 read trajectory)
- [x] R2 root cause: primary 4, contributing 3
- [x] R3 lever table from reward-details + trajectory
- [x] R4 trajectory autopsy (49 steps; contract step 4; NL-4 plants seen step 14; tool rewritten 15-22; NL-1 both readings step 33 differ 0; synth 37-39)
- [x] R5 save agent program OUT/agent_program/ (out/, tool/, check/)
- [x] R6 blind-program pilot 19/19 right incl K1 -> recommend ROUND LIMIT; pre-probe check proposal + candidate lever shapes
- [x] R7 OUT/DIAGNOSIS.md written, STOP "DIAGNOSIS READY"
- [ ] R8 wait for go (Phase 2 only on explicit go; recommendation ROUND LIMIT no credible lever)
