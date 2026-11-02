# RULE_COVERAGE (harden r2, bddb388; G11, AL-27)

Each row: a graded rule, the mutant that breaks only it, and how many positive checks fail under
that mutant on the final tests (kill5, score5.log). Old rules keep their negative detectors
(unchanged bodies) as recorded in the e2bfbf0 harden.

| rule | stated at | mutant | positive checks failing |
|---|---|---|---|
| crosswalk on slot group memberships | spec_stage_p01_identifier_and_revision.md:19-22 | oracle_less_groups | 6 |
| crosswalk on charge rule subjects | spec_stage_p01_identifier_and_revision.md:19-22 | oracle_less_rules | 6 |
| crosswalk on amendment payloads | spec_stage_p01_identifier_and_revision.md:19-22 | oracle_less_amendments | 6 |
| Q1 lodgements naming a JOB-CYCLE job rejected EDG-UNKNOWNJOB | spec_stage_p02_precedence_graph.md:20-23 | oracle_program (lacks DFC-16, DFC-25) | 5 (with Q2) |
| Q2 round weighted resource exact then twelve places | spec_stage_p10_objective.md:27-29 | oracle_program (lacks DFC-16, DFC-25) | 5 (with Q1) |
| catalogued faults DFC-01..15 | stage papers p01-p13 | engine_orig | 28 |
