# TODO 98c5c50 batch-lease-scheduler-replay

## Phase 0
- [x] rename session (codex: no match; opencode listed)
- [x] read rule files 1-5, IDEA.md
- [x] fingerprints GEN/QC match (22:26)
- [x] PREMORTEM.md part A
- [x] engine/refsim.py (unit-step reference)
- [x] engine/heap.py (event-heap replay, slip flags)
- [x] engine/gen.py (state-aware hidden generator)
- [x] engine/premortem_run.py -> PREMORTEM part B numbers
- [x] DESIGN.md
- [x] QC_DEFENCE.md
- [x] DESIGN_SUMMARY.md, STOP "DESIGN READY"
- [x] WAIT for Ayush "go" (go 23:45 with master notes 1-8)
## Master notes (go 23:45): 2 hidden densest G-2 cases + per-corpus case counts; 3 shipped light but every kind; 4 COST_TABLE all FW slips + FIRSTWRITE; 5 Docker timing ref + unit-step on 4-set book (<=15 s), TRUTH; 6 G5 sentence "Each output document is graded whole on fresh books, and only an exact match counts."; 7 check_exact 300 sets; 8 stop at "BUILD READY: <bundle>"
## Phase 1 scaffold
- [x] engine: trace + case counters; generator densify (note 2) and shipped every kind (note 3)
- [x] run generate_bundle.py; copy scaffold to WORK/scaffold_orig
## Phase 2 data and spec
- [x] WORK/project_src broken leasebook + its tests
- [x] replay_contract.md
- [x] WORK/datagen.py -> environment/data (A5 volume)
## Phase 3 reference
- [x] solution/solve.py (+fixed package) solve.sh
- [x] WORK/check_exact.py (shipped + 300 sets)
## Phase 4 tests
- [x] tests/test_output.py, reward.toml
- [x] COST_TABLE, RULE_COVERAGE, EVIDENCE_MAP, LEVERS
## Phase 5 judge
- [x] judge.toml, JUDGE_MAP
## Phase 6 instruction
- [x] instruction.md
## Phase 7 TRUTH
- [x] TRUTH.md (Docker timing)
## Phase 8 gates
- [x] QC scripts, validator, A5
- [x] oracle x3 / nop
- [x] stacking
- [x] precheck
## Phase 9 report
- [x] BUILD_REPORT, result json, BUILD READY
