# TODO f65cab8 P12 fix v2 (prompt: master_chat_tasks/prompts/issued/metered-usage-rating-pipeline/20261029T0854_fix.md)
Old a395eb2 list saved as TODO_a395.md. OUT = master_chat_work/20261029_metered-usage-rating-pipeline/p12_fix_v2_f65cab8
## Setup
- [x] date, rename (opencode ok), reading list done, harness HEAD 5574d77e
- [x] bundle == prev QC copy cc541be (diff -rq empty)
- [x] fingerprints (Always 1) 0 mismatches both
## Phase 0
- [x] P0.2 xref_check 0 (24 entries, 0 findings)
- [x] P0.3 trap baseline (a395/trap_after.json, tests d4c29edb) per lever (reuse a395 trap_after if tests sha unchanged)
## Phase 1
- [x] G05-1 REAL (row written with deliverables) to OUT/RECHECK_FIX.md
## Phase 2
- [x] F1 template: new checks (a) multi reference missing (b) multi collector missing; weights
- [x] F2 assemble tests, G7 byte diff
- [x] F3 RULE_COVERAGE.md (AL-27 rows), TRUTH regen last by script; LEVERS/QC_DEFENCE/XREF in step
- [x] 1a touched rules; 1b vacuity probe (in OUT/RECHECK_FIX.md)
- [x] xref 0; side effects; precheck CLEAN; stacking_check
- [x] trap survival (Docker variants)
- [x] Main-chat resume audit: permitted three-file diff only; both Docker-copy tests byte-identical; AST 112 checks / 419 positive; fingerprints 0 mismatches; all seven losses unchanged; precheck CLEAN, xref 0, stacking hints reconciled as before
- [x] Docker: warm, oracle x3, owner x1, nop x1 (exe_copy); ALL_DONE 11:44:22, five trial JSONs independently verified 12:39, no exceptions
- [x] sync Tasks_INPUT, diff -rq empty (exit 0, 12:45 IST), both tree shas 396efb9b4952 (23 files)
- [x] Deliverables RECHECK_FIX, PL_NOTE, KEPT, STACKING_CHECK and result_f65cab8.json complete; JSON schema/counts/report sections validated, matching tree hashes rechecked; master P11 v3 MODE recheck is next
