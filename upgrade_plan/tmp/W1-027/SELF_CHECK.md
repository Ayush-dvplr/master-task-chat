SELF CHECK of FOLD_TABLE.md (W1-027, 3 Nov 2026)

Method: 10 rows drawn with Python random.sample over all 410 F rows (seed 20261103). For each, the cited file was reopened at the cited line and the row's rule text was compared with the source. For long lines that the print cut off, the cited phrase was found with grep on that same line.

1. F46 | LEVER_RULES_v3.md:161 | row: never grade a key the agent cannot read; every key named in the shipped contract | source line 161 (G1) holds "Never grade a key the agent cannot read" and "every key, field and value form any test reads must be named somewhere in the shipped contract" | MATCH
2. F74 | LEVER_RULES_v3.md:207 | row: J7 a deterministic artifact behaviour is a test, never a criterion | source: "J7. A deterministic artifact behaviour (exit code, stderr naming a file, output present) is a test, never a criterion (JD-9)." | MATCH
3. F84 | LEVER_RULES_v3.md:237 | row: re-hardened tasks judge target probe band with predicted mid 15 to 20 | source line 237 holds "judge target is a probe band with predicted mid 15-20" | MATCH
4. F100 | LEVER_RULES_v3.md:258 | row: holes are not levers, never build the listed peer holes | source: "QC sometimes let them through; our QC may not. Never build them." | MATCH
5. F318 | state.json:64 | row: ORACLE/NOP use intake/ql_oracle_nop_procedure.md (oracle up to 3x) | source: "ORACLE/NOP (QL interim, 23:12): use intake/ql_oracle_nop_procedure.md (judge removed, tests renormalised, oracle up to 3x = 1.0, nop 1x = 0.0)" | MATCH
6. F316 | state.json:62 | row: hardness lives mainly in the instruction or task; traps genuine | source: "DESIGN (Ayush 23:12): hardness must live mainly in the INSTRUCTION/task itself ... Traps and complexity in tests/rubric must be genuine" | MATCH
7. F69 | LEVER_RULES_v3.md:202 | row: J3b figure that differs from the delivered file, minus 5 | source: "J3b: ... states a figure for <output family> that differs from the value in the delivered file it names (w -5 ...)" | MATCH
8. F28 | LEVER_RULES_v3.md:116 | row: instructed effort caps never | source table row: "Instructed effort caps (e.g. "stop at 1500 s") | FALSE | ... | never" | MATCH
9. F271 | pipeline_v4/PLAN.md:66 | row: auto mode QC sign off records Step 10 as reduced; rest owed before push | source: "An auto-mode QC sign-off therefore records Step 10 as reduced (2 oracle + 1 nop); the remaining runs ... are owed before push" | MATCH
10. F131 | QC_FIX_PLAYBOOK_v3.md:3 | row: quoted Ayush line "we have to bypass the QC so that we can maintain the levers, traps etc ... a regular fix can make it soft and easy" | source line 3 holds that quote word for word | MATCH

Result: 10 of 10 rows matched their cited file:line.
Other checks run on the whole table: 410 rows, ids F1 to F410 in order with no gaps, every row has exactly 6 columns, no dash or arrow punctuation found by grep.
