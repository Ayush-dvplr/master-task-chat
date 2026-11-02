# TODO ed7b0c2 flood-repair-portfolio
Prompt: master_chat_tasks/prompts/issued/flood-repair-portfolio/20261025T2222_build.md (re-read after compaction)

## Phase 0
- [x] 0.0 rename session (opencode list shows ses_e8c03a050ffe0YJMutfOlJc0ur; codex no match)
- [x] 0.1 read rules files in order (COMMON_RULES_v3, LEVER_RULES_v2, LEAK_LIBRARY, QC_RULINGS, QC_FIX_PLAYBOOK_v2, KNOWLEDGE, checks.json)
- [x] 0.2 fingerprints GEN + QC: 0 DIFF 0 MISSING (22:27)
- [x] 0.3 prototype: proto/gen.py graph families, proto/bnb.py generic exact (3 variants), proto/ref.py tree-decomposition DP, proto/base.py greedy/LS/LP
- [x] 0.4 survey local, then Docker run of every solver on every hidden instance under stated limit
- [x] 0.5 WORK/PREMORTEM.md
- [x] 0.6 WORK/DESIGN.md
- [x] 0.7 WORK/QC_DEFENCE.md
- [x] 0.8 WORK/DESIGN_SUMMARY.md (<=40 lines)
- [x] 0.9 STOP: "DESIGN READY: <path>"

## Master go 22:45 (apply first)
- [x] M1 stdlib-only rule in contract + instruction; tests run `python3 -I -S` foreign uid/cwd; ref + positives pass under -I -S; BUILD_REPORT records task.toml network (agent, verifier) + /usr/bin/python3 in image; no solver-import negative
- [x] M2 limit from Docker at harness CPU count and --cpus=1; rerun generic exact (memo+red+split, colour B&B) at final limit all cores; ref <= 1/4 limit
- [x] M3 keep 2 large hidden-family rounds in shipped book; no method/structure hints
- [x] M4 seed filter: each hidden book has >=1 large round where lp_round+swaps and ILS 10 s not exact; every baseline loses >=1 heavy doc per book; per-book losses in COST_TABLE
- [x] M5 LV-FP-2/3 plain; risk_override precedence stated in defining file
- [x] M6 Q18 provenance; M7 stop at "BUILD READY: <bundle>", no probe

## Phase 1-9 (after "go")
- [x] P1 scaffold  - [x] P2 data/spec (contract.md written; add single-file sentence)  - [x] P3 reference solve.py (check_exact done 0 diffs)  - [x] P4 tests (34 checks, 108/108 oracle; mutants, COST_TABLE, RULE_COVERAGE, LEVERS, EVIDENCE_MAP, UNIQUENESS done; gen300 0 errors)  - [x] P5 judge
- [x] P6 instruction  - [x] P7 TRUTH  - [x] P8 gates  - [x] P9 report + result json
