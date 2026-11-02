| finding id | file:line | reason | kit line it rests on |
|---|---|---|---|
| G03-2 (A3, carried, v3.md:94, :129) | tests/test_output.py (113 checks, new registration :2161) | no count cap (Ayush 24 Oct 12:50; decision 3 option A, 27 Oct); count recorded 113 (was 112); no duplicates to merge; playbook TS-23 KEEP | Input_Bundle_QC/Final_checklist.md:204; Input_Bundle_QC/03_Tests_QC.md:62 |
| X1 (REBUT, carried, v3.md:95) | environment/data/collector_south.txt; environment/data/rating_contract.md:61 | Latin-1 by contract; QC v1.md:29 and :145 verified text | structure_qc.py X1 warn "re-check any that are text" |
| G04-1 deviation (carried, R6 one act) | tests/judge.toml:77-88 | exactly one code-quality criterion required; untouched this round | knowledge/LEVER_RULES_v3.md:203 J4; Input_Bundle_QC/04_Judge_QC.md:71 JD-5 |
| G01-1 deviation (carried, two forms named) | environment/data/rating_contract.md:74-75 | naming three or more malformed kinds trips LV-ENUM; untouched this round | master_chat_tasks/tools/precheck.sh:90-109 |

The v2 note "G05-1 collector pair order" is dropped: QC v3.md:43 said it did not answer the adjacent-pair sentence of 05:38, and the new check now covers all ten adjacent pairs.

## Lessons for the master

- Drop a KEPT note once a fix makes it moot, so the next recheck does not weigh it again | no change: the carry-over rule already re-reads every row
