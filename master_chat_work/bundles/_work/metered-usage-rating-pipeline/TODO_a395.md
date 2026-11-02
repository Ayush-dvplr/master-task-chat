# TODO a395eb2 P12 fix v1 (prompt: master_chat_tasks/prompts/issued/metered-usage-rating-pipeline/20261029T0406_fix.md)
Old 361674d list saved as TODO_h361.md. OUT = master_chat_work/20261029_metered-usage-rating-pipeline/p12_fix_v1_a395eb2
## Setup
- [x] date, rename (opencode ok), reading list, harness HEAD 5574d77e, bundle == prev QC copy (diff -rq empty)
## Phase 0
- [x] P0.1 QC_DEFENCE exists (skip build); P0.2 XREF exists -> xref_check 0
- [x] P0.3 trap baseline per lever (single wrong-reading variant loss on current tests)
## Phase 1 recheck (rows to OUT/RECHECK_FIX.md)
- [x] all Phase 1 rows written to OUT/RECHECK_FIX.md (04:22)
## Phase 2
- [x] F1 contract :74 wording + re-embed _SHIPPED_DATA (tests_template/assemble) 
- [x] F2 _run process group (template)
- [x] F3 missing-input list order checks (template) + reward weights
- [x] F4 judge R6 one act (deviation) + R23 + reward 0.01 (JUDGE_MAP pending in F6) + new R final_answer checks-reported + reward judge weight + JUDGE_MAP
- [x] F5 assemble tests, G7 byte diff
- [x] F6 TRUTH regen (claims, digests, renumber) last by script; LEVERS/QC_DEFENCE/XREF update
- [x] 1a touched rules table; 1b vacuity probe (RECHECK_FIX)
- [x] xref_check 0; side effects; precheck CLEAN; stacking_check (04:43 kit scripts: judge_qc PASS, tests_qc WARN A3 only, instruction PASS, structure WARN X1 only)
- [x] trap survival; forgery price re-measure (04:37: a395/trap_after.json, before 22/407 const, detach 206/407 -> after 106/413 (22 forge-only))
- [x] Docker: warm, oracle x3 owner nop (exe_copy) 1.0 x3, owner 1.0, nop 0.0, ALL_DONE 06:12
- [x] Deliverables RECHECK_FIX, PL_NOTE, KEPT, result json (06:15)
