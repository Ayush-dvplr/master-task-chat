# Recheck Fix 420bf9a
| id | touched how | rules re-checked | verdict |
|---|---|---|---|
| negative_hardcoded_sample_answers | source scan replaced with cached H1 answer substitution | TS-13, TS-14, TS-16, TS-20, TS-25, TS-26, CL-2, CL-4 | one negative observable; -3 retained; no new run; absent/crashed output returns False through _holds; actual witness and oracle/P silence required in FIX_REPORT |
| negative_program_reads_verifier_files -> R16 | removed artifact source scan; trajectory access owns act | JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, AL-28 | sequential R16; one access act; -5; four permitted annotations; trajectory evidence and step id; oracle has no access; R14/R15 final claims disjoint |
| reruns_identical | raw bytes -> strict typed parsed JSON | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4 | one repeatability property; weight3 unchanged; requires two successful complete runs; not comparison to expected answers; content/list/type changes still fail |
| DS-27 | removed review-history wording only | DS-22, IN-15, IN-16, IN-17, DS-21, AL-2, AL-27, CL-3 | limits, measurements, identifiers and scripted bindings retained; no agent-visible file, fixture or generator edit |

Protected TS-26 optimum/summary checks and AL-27 fault fixtures are byte-identical to the snapshot, per fix4/scope_proof.json; KEPT is an explicit override, not a fresh claim that v4 findings passed.
Vacuity: nop must earn no positive tests; reading R1-R13 shows no unchanged-data/no-program agent earns conduct, maintainability or a final rejection list. Stub only earns artifact presence, never correctness.

## Lessons for the master
Require executed access evidence rather than source tokens | no change: scoped TS-16 fix follows the live rule.
