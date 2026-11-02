# KEPT: hangar-check-replan, dabfeb4

| Finding | Current scope | Kit basis | Decision and evidence |
|---|---|---|---|
| F03 / A3 / TS-23 | 76 checks after removing both source-token negatives and adding one behavior-only replay negative; previously 77 | Input_Bundle_QC/03_Tests_QC.md:62; playbook TS-23; common rules score conventions | Master explicitly keeps the count warning and forbids consolidation. The four live QC scripts have zero FAIL; tests_qc reports A3 WARN only. |
| X1, carried from fix2 | environment/data/disruption_notice.docx and planning_limits.docx | Input_Bundle_QC/structure_qc.py:71 and :1112 | Real Word packages are skipped as binary by the text scanner. Both original files are byte-identical to the initial bundle; no document-format or input change was made. |
| JD-9 malformed-input coverage, carried from fix2 | Current judge R8, rather than the historical R11 | Input_Bundle_QC/04_Judge_QC.md:146 | Malformed-input handling remains a judged delivered-program property; the deterministic missing-input check is a different case. No new malformed-input test was requested. |
| DS-20 missing calendar field, carried from fix2 | solution/solve.py and environment/data/docs/data_conventions.md | Input_Bundle_QC/02_Data_Solution_QC.md:68 | No new criterion or test grades this specific row shape. InputError names an unparseable input under the existing docs; those files remain byte-identical. |

Historical TS-20's 96/137 settlement-point rationale is superseded by F02's required 344-point core restoration, not silently carried as current arithmetic. Historical TS-24's missing process-group kill was fixed in harden_r1 and is no longer an active KEEP. Historical TS-23's count 44 is superseded by F03's count 76. Original fix2 notes remain untouched.

The precheck's JD-5 warnings for R18-R20 count evidence/stand-down sentences, not multiple graded acts; see STACKING_CHECK_resume.md's manual ownership table. They were audited. The previous validator conflict is resolved by an observed-behavior negative, not waived: validator_resume.log records 39 PASS / 0 FAIL.

## Lessons for the master
Carry surviving KEEP decisions forward with current criterion IDs/counts, and explicitly supersede stale arithmetic. | no change: required by this fix prompt
