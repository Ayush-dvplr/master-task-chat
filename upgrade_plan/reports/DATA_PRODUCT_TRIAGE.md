HANDED OVER to the new master (ENTRY 113, 5 Nov 08:30): items 2 and 4 and paid run S460 are decided there; item 3 (QL QC before the paid run) is gone by the new ORDER. Kept for reference.
DATA-PRODUCT TRIAGE (data-product-config-compiler, item 2 of 4, ENTRY 107). Asked Ayush 5 Nov about 00:40 IST.

Source: old system QC v2 "/Users/mac/Desktop/Terminal Bench/QC/reports/data-product-config-compiler/v2.md" (lines 42, 43, 159, 179, 276) closed TS-26 and JD-14 as "acknowledged (carry-over)" from KEPT.md; QC v1 recorded them as warns. ENTRY 105 removed that kind of closing: Ayush decides. Bundle: "/Users/mac/Desktop/Terminal Bench/Terminal_2.0_Harbor_Harness/Tasks_INPUT/data-product-config-compiler" (frozen tree 2ad86997ab52). Kit: ROOT harness Input_Bundle_QC at 48726eb7.

1. TS-26 | tests/test_output.py:1280 to 1282 _check_read_only, test readonly_inputs (w3, line 1541) | kit 03_Tests_QC.md:53 "Same observable, same logic = keep one side, or rewrite one to read a different observable. Fail." | KEPT reason "readonly_inputs compares whole fresh config.json, stacks with corpus-family checks; kept (master note 9)" | session reading: REAL. The readonly run uses the same hidden corpus (_RUNS line 1183, _hidden_files) and compares the whole config.json with the expected one, so one wrong field fails it and the corpus checks. Fix idea: compare the read only run with the same tool's run on a writable copy (checks only "works from a read only folder").
2. JD-14 a | judge.toml R7 (:92, run on an altered copy of the data folder, figures move) and R13 (:170, one specific altered copy: later owner row ended, earlier row still covers) | kit 04_Judge_QC.md:91 "Same observable, same judgement = rewrite one to a distinct observable quality ... or drop one side. Fail." | KEPT reason "kept (measured judge band)" | session reading: UNSURE, leaning real (doing R13 also earns R7).
3. JD-14 b | judge.toml R14 (:183, one specific shape change: text integer with non digits) and R18 (:235, own input set with shapes beyond the shipped ones) | same kit line | same KEPT reason | session reading: UNSURE, leaning real (doing R14 also earns R18).

Options put to Ayush:
1. (Recommended) TS-26 REAL; JD-14 a and b asked to the QL (PL_QUESTIONS format), freeze kept until the answer. Cost: the TS-26 fix changes tests/, so the freeze ends and a QC v3 recheck is needed (JD-16 could be fixed in the same round if Ayush revisits ENTRY 109).
2. All three REAL, fixed in one round, QC v3 recheck. Cost: one QC round.
3. All three FALSE POSITIVE, kept with a note each. Cost: the kit ends both checks with Fail; the QL will likely report them.

Still after item 2: item 3 QL QC owed before the paid run (ORDER, cold master ENTRY 108); item 4 predicted final 53 to 59 over gate 40: harden first or not. Paid run S460 HELD until all are decided.
