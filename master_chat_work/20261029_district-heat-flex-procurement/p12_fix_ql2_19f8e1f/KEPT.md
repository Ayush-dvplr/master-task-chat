| finding id | file:line | reason | kit line it rests on |
|---|---|---|---|
| QL2-F8 | tests/test_output.py canonical_serialization_and_integer_units (TO:1995-2014 in the QL2 report's numbering) | The format check grades one property, the JSON encoding contract, as QC v10 found (v10.md:153). | Input_Bundle_QC/03_Tests_QC.md:44 |
| QL2-F9 | tests/test_output.py negative_external_dependency_or_network (TO:2524-2539) | The name warning is the one QC v10 recorded and Ayush accepted (v10.md:36). | Input_Bundle_QC/03_Tests_QC.md:45 |
| QL2-F10 | tests/test_output.py registrations (TO:2542-2607; now 78 checks) | No cap on check count under the current rules; QC v10 recorded it as accepted (v10.md:39, :165; QC KEPT l5). | Input_Bundle_QC/03_Tests_QC.md:62 |
| QL2-F11 | instruction.md:7 | The instruction states what the output must satisfy and names no grading mechanism (v10.md:87). | Input_Bundle_QC/01_Instruction_QC.md:32 |
| QL2-F12 | tests/judge.toml:38-48, :155-165 (R3, R12) | The report itself says the two criteria judge different observables, which the kit says is not a duplicate (v10.md:192). | Input_Bundle_QC/04_Judge_QC.md:91 |
| QL2-F13 | tests/judge.toml R1-R4, R8-R10, R12 | The report itself says these criteria pass; the kit allows conduct criteria that raise the odds of a correct result (v10.md:193; QC_RULINGS l141-145). | Input_Bundle_QC/04_Judge_QC.md:92, :139 |
| QL2-F14 | tests/test_output.py run_agent Popen without env= (TO:1807) | The bundle reads and ships no credential; the inherited key is the pinned placeholder QC v10 accepted (v10.md:40, :235; QC KEPT l6). | Input_Bundle_QC/05_Alignment_Integrity_QC.md:65 |
| QL2-F16 | solution/TRUTH.md:130, :232, :238 (pre-fix numbering) | Line 130 is a marked test-channel figure, line 232 the full-run score, and line 238 says so. | Input_Bundle_QC/05_Alignment_Integrity_QC.md:43 |
