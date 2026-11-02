# TODO 7d363c8 outage-window-replan
Prompt: /Users/mac/Desktop/Terminal Bench/master_chat_tasks/prompts/issued/outage-window-replan/20261030T0245_build.md

## Phase 0
- [x] rename session (opencode list shows ses_e7682b365ffeo5a6nnmwzxy45X, not 7d363c8; noted)
- [x] read required docs (checks.json read selectively)
- [x] fingerprints GEN + QC match (0 changed, 0 missing)
- [x] PREMORTEM.md
- [x] prototype solvers + kill test in Docker (KILL_TEST.md)
- [x] DESIGN.md + BRANCH_FIRE.md
- [x] QC_DEFENCE.md
- [x] DESIGN_SUMMARY.md -> STOP "DESIGN READY"
## Phase 0b (after go 03:55; conditions in LOG 03:56)
- [x] S-2 keep pairs (fires 4/6 in lanegen; datagen keeps fillers out of planted windows): fire hidden (some solver WRONG:moved), quiet shipped; else drop S-2 + recompute (PAUSED if final > 35)
- [x] WORK/datagen.py full format (shipped + hidden) + WORK/proto/solve_proto.py + fire.py (fire1.log: shipped 0, hidden 12/12)
- [x] proto + design_blind folder; BRANCH_FIRE check (shipped 0, hidden 12/12/12); STOP "DESIGN BLIND READY"
- [x] (06:05 shipped stuck requests: 5 no_feasible_start, 1 predecessor_deferred) Phase 2 note: add shipped no_feasible_start requests so deferral reasons appear on shipped data; online-lookup sentence in instruction
- [x] DESIGN_BLIND.md from master blind program (blind exact 9/9 on ship + s1-s3 -> PAUSED / NO CORE; Phases 1-9 not started)
## Option (c) (master go 04:40)
- [x] scale search: pick hidden size + stated limit (ref <= 1/4 limit; blind loses >= 40% lever pts on 3 new seeds; kill table + comp split DFS row; shipped < 5 s quiet)
- [x] DESIGN_SUMMARY.md section 'option c' with numbers; then Phase 1 (no stop)
## Phase 1-9 per prompt
- [x] Phase 1 scaffold (06:00, copied to WORK/scaffold_orig)
- [x] Phase 2 data (datagen -> BUNDLE/environment/data incl docs) + spec docs (06:20)
- [x] Phase 3 solution/solve.py, solve.sh, WORK/check_exact.py, override-removal probes (06:15; 7 probes move output)
- [x] Phase 4 tests/test_output.py (1658 lines incl -3 import negative), LEVERS, reward.toml, EVIDENCE_MAP, RULE_TRACE, COST_TABLE, RULE_COVERAGE (07:05)
- [x] Phase 5 judge.toml (judge_qc PASS) + JUDGE_MAP (06:50)
- [x] Phase 6 instruction.md (06:40, 21 lines)
- [x] Phase 7 TRUTH.md (write_truth.py re-run 07:12 after last edit)
- [x] Phase 8 QC 4x PASS 0 FAIL, validator 41/0, oracle x3 92/92, nop 0, STACKING PASS, SELF_CHECKS, PRECHECK CLEAN (07:13)
- [x] Phase 9 BUILD_REPORT + result json

# P12 fix v1 (board 20552cf, prompt 20261030T0810_fix.md) — started 08:06 IST
- [x] name_session 20552cf (not listed; note in report)
- [x] read rule files; kit HEAD 5574d77e; fingerprints QC 12/12 OK, GEN 160/160 OK
- [x] backup BUNDLE -> WORK/qc1_6b179e601d17 (tree 6b179e601d17)
- [x] Phase 0: XREF.md + xref_check 0; trap baseline per lever
- [x] Phase 1: read QC v1 report, recheck each finding -> OUT/RECHECK_FIX.md rows
- [x] Phase 2a: TS-24 _run_program killpg; TS-19 _RUN_SECONDS 60; CL-7 docs in every corpus (tests_src + build_tests)
- [x] Phase 2b: AL-27 generator unknown_asset+out-of-season row in h2/h3; RULE_COVERAGE
- [x] Phase 2c: judge R9 clause drop, R14 carve, +R17 objective pair w1, +R18 writes outside /app/out w-1; reward.toml
- [x] Phase 2d: task.toml keywords/tags
- [x] Phase 2e: tests byte diff (G7); regen; re-embed; touched rules; vacuity; XREF; side effects; precheck CLEAN; stacking
- [x] Phase 2f: blinds + kill rows re-score; trap survival
- [x] Phase 2g: TRUTH via write_truth.py (DS-27 wording) last
- [x] Phase 2h: warm image; Docker oracle x3/owner/nop chain ALL_DONE 08:43:37 oracle 1.0x3 owner 1.0 nop 0.0 (started 08:41, /tmp/opencode-logs/outage-window-replan-p12-20261030T083514-0223/runs.log; do not re-run, check ALL_DONE)
- [x] Deliverables: RECHECK_FIX, PL_NOTE, KEPT, result json; Tasks_INPUT copy + tree shas (both 005e42b1b4aa)
