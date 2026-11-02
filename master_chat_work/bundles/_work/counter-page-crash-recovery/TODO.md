# TODO counter-page-crash-recovery (board 54e38ee)

## Phase 0
- [x] rename session (opencode list shows ses_e8c5e56dcffeM7e8KT55xptF2N; codex no match)
- [x] read required files in order
- [x] 0.1 fingerprints GEN + QC (no diffs, 20:48 IST)
- [x] 0.2 study build-repair archetype scaffold in GEN (templates) for design
- [x] 0.2b prototype WORK/proto/{gen,rec}.py + baselines run (premortem numbers)
- [x] 0.2 WORK/PREMORTEM.md (with textbook ARIES program + losses per hidden book)
- [x] 0.3 WORK/DESIGN.md
- [x] 0.4 WORK/QC_DEFENCE.md
- [x] 0.5 WORK/DESIGN_SUMMARY.md (<=40 lines)
- [x] 0.6 STOP: DESIGN READY, wait for "go" (go 22:35 IST)

## Master changes (22:35)
- [x] M1 shipped book light profile (no same-page multi-change, no CLR-to-CLR stop)
- [x] M2 H3 timing own check w3; H3 doc exactness only
- [x] M3 extra hidden coupled check so every all-but-one row < 70
- [x] M4 hidden books densest interactions in every image: >=2 earlier restarts interrupted in undo, CLR-to-CLR stops, same-page multi-change, loser write flushed after committed write same page, checkpoint tables disagree with log tail; per-book case counts in BUILD_REPORT
- [x] M5 IN-17: END placement + redo decision stated plainly, no textbook contrast
- [x] M6 Docker timing of reference on H3 (<=15 s / 12 images) into TRUTH.md
- [x] M7 stop at BUILD READY (no probe)

## Phase 1-9 (after go)
- [x] P1 scaffold + copy scaffold_orig
- [x] P2a WORK/bookgen.py generator+reference, variants.py, cmp_variants.py (baselines lose on all hidden books)
- [x] P2b WORK/project/ shipped pagerecover package (commit-filter method + honest defects) + tests
- [x] P2c WORK/recovery_contract.md (governing, all rules, keys, errors, limits)
- [x] P2d WORK/datagen.py -> BUNDLE/environment/data (drop scaffold build.log, module_map.json, scoring_fixtures.jsonl, report_contract.md); A5 count
- [x] P3 solve.py/solve.sh + check_exact.py
- [x] P4 tests, COST_TABLE, RULE_COVERAGE, EVIDENCE_MAP, LEVERS, reward.toml
- [x] P5 judge.toml + JUDGE_MAP
- [x] P6 instruction.md
- [x] P7 TRUTH.md (hashes pending finalize_truth at end)
- [x] P8 QC scripts, validator, oracle x3/nop, stacking, precheck
- [x] P9 BUILD_REPORT.md, result_54e38ee.json
