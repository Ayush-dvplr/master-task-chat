# district-heat-flex-procurement, QL round 2: note for the PL

Fixed (9): F1 event_count wording in schema.md, F2 the test truth is now its own exact method (wide optima computed once and stored), F3 shipped quality check no longer re-reads the residual count, F4 bid costs and compliance counts are now graded (24 new points, 261 in total), F5 the export receipt no longer lists record counts, F6/F7/F17 TRUTH.md wording, F15 two unused test cases removed and the hidden extract now also tells Wh from whole-tick checking.

Not fixed, with reasons (8, all on lines the last QC passed):
- F8: the format check tests one thing, the JSON encoding rules (03_Tests_QC.md:44; QC v10 V:153).
- F9: the negative check's name is the one QC v10 recorded and Ayush accepted (03_Tests_QC.md:45; V:36).
- F10: more than 35 checks is a warning with no cap under the current rules; 78 checks now (03_Tests_QC.md:62; V:39).
- F11: the instruction says what the output must satisfy and names no grading tool (01_Instruction_QC.md:32; instruction.md:7).
- F12: R3 and R12 judge different figures, which the report itself says (04_Judge_QC.md:91; V:192).
- F13: the report says these criteria pass; the kit allows conduct criteria that make a correct result more likely (04_Judge_QC.md:92, :139).
- F14: the bundle reads and ships no credential; the inherited key is the pinned placeholder (05_Alignment_Integrity_QC.md:65; V:40).
- F16: TRUTH.md line 130 is a marked test-only figure and line 232 the full-run score, and line 238 says so (05_Alignment_Integrity_QC.md:43).

No open questions.
