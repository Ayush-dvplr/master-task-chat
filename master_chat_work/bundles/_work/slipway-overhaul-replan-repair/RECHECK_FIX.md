# RECHECK_FIX (G4), fix-v1 451146f

| id | touched how | rules re-checked | verdict |
|---|---|---|---|
| IN-8 | judge.toml R2 missing/malformed clause dropped | IN-8, JD-5, J4, JD-15 | PASS (judge_qc rc 0, precheck clean) |
| IN-15 | judge.toml old R18 dropped | IN-15, JD-16, JD-8, AL-28 | PASS |
| DS-22 | TRUTH.md intro and Solution shape now name 27 repairs DFC-01..27 | DS-22, DS-21, xref | PASS (xref 0) |
| DS-27 | TRUTH.md authoring narration removed | DS-27 | PASS |
| TS-24 | own session, group kill, run-user sweep, private reference, sealed copies | TS-24, TS-19, determinism checks | PASS (fork probe 1 -> 0) |
| JD-8 | old R3 dropped | JD-8, AL-2, JD-S13 | PASS |
| JD-15 | old R10 replaced by crosswalk probe R9 | JD-15, J2b, JD-14 | PASS |
| JD-16 | old R18 dropped | JD-16 | PASS |
| AL-10 | `_echoes_shipped` feeds hardcoded detector and shipped_* checks | AL-10, AL-28, CL-2, negatives disjoint | see forgery lane |
| AL-2 | instruction.md:21 deleted | AL-2, IN-17, route-1 R2 | PASS (instruction_qc rc 0) |
| AL-27 | edges/register/supplement plants in held rounds | AL-27, TS-26, TS-19, DS-21 | PASS (old corpora identical; oracle 112/112) |
| TS-13 | package shape split in three | TS-13, TS-23 (warn kept), W2 | PASS |
| JD-5 | R2 one act | JD-5, J10 | PASS |
| AL-7 | measured_* scoped to test channel | AL-7, DS-22 | PASS |

## b20fdca (fix v2, QC v2 findings)
| id | touched how | rules re-checked | verdict |
|---|---|---|---|
| TS-24 | expected docs built in private 0700 dir (`_private`), cached, removed before return (`_reference` :5055, `_held_reference` :5228); public/engine/shipped/renamed dirs filled private then sealed; `_drive` reads output inside `_RUN_LOCK` after `_stop_untrusted` | TS-24, TS-28, F0c, CL-2, AL-11, AL-13, TS-20/TS-23 (warns kept), weights/check names unchanged (49 regs identical) | PASS (lift attack old tests 75/112 -> new 0/112; overwrite 0/112 both; see fix2_qcv2/FIX_REPORT.md) |
| DS-22 | TRUTH.md:62 "(the instruction)" -> "(output_schema_reference.md)"; :108-110 reference wording rewritten to shipped code; shas by script last | DS-22, AL-18, G6, xref (0 findings) | PASS |

## 481e976 (fix-ql1, QL1 findings)
| id | touched how | rules re-checked | verdict |
|---|---|---|---|
| QL1-F1 | task.toml:12 category Debugging | IN-12, AL-26, structure_qc | PASS (structure_qc 17/1 warn X1/0) |
| QL1-F2 | p13:7-9 one clause, minted copy in test_output.py mirrored | IN-16, AL-18, DS-21, CL-2 | PASS (oracle 112/112, no expected value moved) |
| QL1-F3/F10 | output_schema_reference.md doc 23, 24, 25 wording; minted copy mirrored | IN-16, DS-6, AL-18 | PASS (xref 0) |
| QL1-F6 | delivered_engine_stdlib_only now earned output (bare `-S` run, 25 docs in shape, doc 18 = reference); new negative imports_outside_the_standard_library -3 | TS-25, TS-13, TS-14, TS-16, TS-26, TS-23 (warn 50), AL-28, G5 | PASS (oracle earns it; unrepaired lane fails it) |
| QL1-F13 | docstring + PACKAGE_FILES comment | DS-6, TS-2 | PASS |
| QL1-F7 | judge R15/R16 stand-down wording | JD-5, JD-8, JD-14, JD-15, JD-16, AL-28, J10, J11 | PASS (judge_qc 19/0/0, precheck JD-5 clear) |
| QL1-F4/F5 | solve.sh opening papers first; R4, R6, R10 witnesses; TRUTH steps | JD-7, JD-S13, DS-22, G6 | PASS (oracle-1 agent output) |
| QL1-F11 | TRUTH.md:55-59 | DS-22, G6, AL-18 | PASS (shas by script last) |
