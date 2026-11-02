# RECHECK_FIX fix1 (QC v1, board 2eb1638), guard rule G4

## dabfeb4 QC v4 Repair (Current; Supersedes Historical Rows)

| finding | repair | re-check |
|---|---|---|
| F01/F06 | remove both source-token negatives; R14 sole grader-access owner | TS-14/16, AL-28: no source inspection in deterministic negatives; retained inventory owner unchanged |
| F02 | 33 complete-outcome weights raised to 5; reward coefficient recomputed | CL-2/3, W2, G1-G7: positive 344, lever 165; no decreases; a1 measured before further certification/sync |
| F04 | derived final deferred-ID witness, R9 unchanged | JD-2/5/7/8/9/15, IN-8: witness reads produced file, no hardcoded ids; no new criterion |
| F05 | R18/R19/R20, each -5 with evidence and stand-down | JD-5 one act; JD-8 no positive restatement; JD-14 negative budget 31 <= 39; JD-15 targets state_change/trajectory; JD-16 explicit instruction-following; AL-28 manual two-layer ownership matrix in OUT/STACKING_CHECK.md |
| F07 | compressed docs decoded by render/_shipped_root | IN-16, TS-19, DS-21/22, AL-18/19: raw inputs unchanged; 18 expected digest pairs and 108 doc copies measured in Docker diagnostic (see report for completion) |
| F03 | 75 checks after two mandated removals | A3/TS-23 WARN kept; no consolidation; kit 03_Tests_QC.md:62 |

Static gate output and actual Docker outcomes are recorded in fix_qcv4/FIX_REPORT.md; historical lane results below are not current-byte certification.

| id | touched how | rules re-checked | verdict |
|---|---|---|---|
| IN-16 / TS-19 | `_prepare_run` creates out + cwd 0777 before each run | TS-19 (hidden runs inside stated shape), AL-2 (cwd still foreign), IN-17 (no doc sentence added) | pass (lanes) |
| JD-8 / AL-F0d | R12 rewritten to reply-vs-delivered-file | JD-8, JD-5, J10 negative grammar, IN-8 | pass (judge_qc, precheck) |
| JD-16 R13 | type -> instruction following (now R14) | JD-15 type list | pass |
| AL-27 | two-fault rows + bad available_from in hidden folders | TS-19 (values inside stated forms), G12 300 seeds, AL-27, TS-26 | see FIX_REPORT G12 row |
| AL-28 R14 | scoped to the agent's own commands (now R15) | AL-28 (stacking), J9 starts "The agent", J10 | pass (stacking, judge_qc) |
| IN-12 | description + keywords/tags | IN-12, structure | pass |
| DS-20 | solve.py `_values` | DS-20, oracle outputs unchanged on shipped | pass (byte diff) |
| DS-22 | TRUTH by script last | DS-22 cited lines exist, sha | pass (precheck) |
| TS-13 | 2 splits | TS-13, TS-25 (oracle 1.0 each), TS-26, W2 weights {1,3,5} | pass |
| JD-5 R10/R12 | R10 split R10+R11, R13 clause dropped | JD-2, JD-7 (oracle shows R11 via solve.py InputError), JD-9, JD-15, IN-8 | pass |
| JD-16 R10 test | new program_stops_on_a_missing_input | TS-13, TS-14/16 (fails for nop), TS-26, JD-8 vs R8 (agent act vs program exit) | pass (lanes) |
| AL-2 | new negative_writes_outside_out_dir -3 | AL-28 one charge per act, G5 vacuity (silent on oracle), TS-16 | pass (lanes) |
| TS-23 | 44 checks | A3 warn recorded | warn, reported |

# RECHECK_FIX fix2 (QC v2, board 283e5be), guard rule G4

| id | touched how | rules re-checked | verdict |
|---|---|---|---|
| F-04a JD-7 / AL-6 R6 | probe side only: P6 (solve.sh:153-157) now runs on `copy_data("p6")` (a path under /tmp/oracle_checks, not /app/data) with cwd /tmp, compared against the shipped /app/out files; criterion text unchanged | JD-7 (oracle meets both clauses: other cwd, other input path), JD-2, JD-5 (one act), JD-6, JD-9, JD-13, JD-15, AL-28 (no new criterion, no stacking change) | pass (Docker P6 line, oracle x3) |
| R5 witness | P5 witness (solve.sh:150-151) prints settlement before -> after; assertion unchanged | JD-7 "shows that the settlement figures changed" | pass |
| R9 witness | P9 witness (solve.sh:195) prints region_East.json content; assertion unchanged | JD-7 "shows the region file for that base" | pass |

# RECHECK_FIX harden_r1 (a79e23e, 2 Nov 2026), guard rule G4

| id | touched how | rules re-checked | verdict |
|---|---|---|---|
| TS-24 (KEPT W-03a) | `_launch` (own session, process-group kill, nobody sweep) + `_stop_untrusted`; `_run_program` and `_check_stops_on_missing_input` run through it; `_build_case` keeps each case root 0700 except while its own run holds `_RUN_LOCK` | TS-24, TS-14/16 (nop still 0), AL-2 stray recording unchanged (read after kill), IN-16 (OUT_DIR still created 0777 before the run) | pending lanes + fork probe (OUT/LEAKS.md) |
| TS-23 / TS-26 | 33 new checks h7..h15 on 9 new folders, own seeds; old checks byte-identical (digest_old.txt: 178 same; 4 changed = leak fix + FORMS loop in negative_writes_outside_out_dir) | TS-13 (one assert per check, views reused), TS-25 (oracle 242/242 score0), TS-26 (field groups as old hN), A3 warn (77 tests > 44) | pass (score0); warn recorded |
| W2 weights | old hN plan_rows stay 3, three settlement checks 5->1 (weight 2 refused by tests_qc W2); new checks 5 | W2 weight set {1,3,5}; AL-28 unchanged (no new negative) | pass (tests_qc) |
| AL-2 negative_writes_outside_out_dir | loop extended to FORMS folders | G5 vacuity: silent on oracle (score0 neg 0) | pass |
| JD-8 | R6, R8, R9 dropped | JD-8 restatement rule; probe share 61.5% inside 55-70 | pass (judge_qc pending) |
| JD-5/JD-7 R12 R13 (new) | new P-d probes, oracle P10 (solve.sh:196-205) P11 (:207-224) | JD-2, JD-5 one act, JD-6, JD-7 oracle shows, JD-9, JD-13, JD-15 | pending oracle lane |
| DS-21 / DS-22 | solve.py Word reader looks through sdt, customXml, AlternateContent (solve.py:31-65, :197-198) | DS-20 (outputs on shipped unchanged), DS-22 TRUTH by script last | pending |
