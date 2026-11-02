| finding id | file:line | reason | kit line it rests on |
|---|---|---|---|
| G03-2 (A3, carried, v2.md:199) | tests/test_output.py (112 checks, new registrations :2143-2144) | no count cap (Ayush 24 Oct 12:50; decision 3 option A, 27 Oct); count recorded 112; no duplicates to merge; playbook TS-23 KEEP | Input_Bundle_QC/Final_checklist.md:204; Input_Bundle_QC/03_Tests_QC.md:62 |
| X1 (REBUT, carried) | environment/data/collector_south.txt; environment/data/rating_contract.md:61 | Latin-1 by contract; QC v1.md:29 and :145 verified text | structure_qc.py X1 warn "re-check any that are text" |
| G04-1 deviation (carried, R6 one act) | tests/judge.toml:77-88 | exactly one code-quality criterion required; untouched this round | knowledge/LEVER_RULES_v3.md:203 J4; Input_Bundle_QC/04_Judge_QC.md:71 JD-5 |
| G01-1 deviation (carried, two forms named) | environment/data/rating_contract.md:74-75 | naming three or more malformed kinds trips LV-ENUM; untouched this round | master_chat_tasks/tools/precheck.sh:90-109 |
| G05-1 collector pair order (note, not a keep of the finding) | environment/data/rating_contract.md:51-53 | collectors listed alphabetically, so no collector pair separates list order from sorted order; reference trio check covers sorted order | Input_Bundle_QC/05_Alignment_Integrity_QC.md:38 |

## Lessons for the master

- Pass this carry-over table into the next MODE recheck | no change: required by the P11 v3 carry-over rule
