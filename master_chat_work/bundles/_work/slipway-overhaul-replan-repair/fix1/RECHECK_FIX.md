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
