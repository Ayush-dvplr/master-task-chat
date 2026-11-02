# Build self-check, DRAFT (not installed)

Order follows distinct failed-task counts in `KIT_MAP.csv` (95 versioned reports, 17 slugs; script: `python3 scripts/build_kit_map.py`). A count is a historical task with a ❌ finding, not a current failure or a count of rounds.

1. **AL-27 (13):** Make `WORK/RULE_COVERAGE.md`: each promised rule, plus every ordering/precedence/tie-break established by copied input, gets a contract file:line, a triggering graded fixture, and one-rule mutant score. For precedence, exercise adjacent pairs with both faults. Read `05_Alignment_Integrity_QC.md:38`.
2. **DS-22 (11):** After the last code/data edit, recompute every number, line count and digest in `solution/TRUTH.md`; compare to shipped files. Run `shasum -a 256 solution/solve.py tests/test_output.py` from the bundle. Read `02_Data_Solution_QC.md:78`.
3. **AL-2 (11):** Enumerate each `instruction.md` promise, expanding delegated rules. Put its check or criterion beside it; remove or grade every uncovered promise. Read `05_Alignment_Integrity_QC.md:33`.
4. **DS-27 (10):** Read `TRUTH.md` for build/process narration, score claims without channel scope, and stale task statements. Read `02_Data_Solution_QC.md:80`.
5. **JD-7 (9):** For every positive and negative criterion, point to oracle code or a measured oracle act showing it passes. Read `04_Judge_QC.md:76`.
6. **TS-19 (7), IN-8 (6):** Map each test/outcome criterion to an instruction sentence or a determinate copied-input fact; prove it is knowable without `tests/` or `solution/`. Read `03_Tests_QC.md:50`, `01_Instruction_QC.md:38`.
7. **TS-24 (7):** Trace any verifier execution of agent code: uid, permissions, trusted imports and reward path. Run owner-only Step 10 copy when authorized. Read `03_Tests_QC.md:68-73`.
8. **AL-28 (7):** List each negative check and criterion by the concrete triggering action. Sum its penalties across both channels; one act must not be charged twice. Read `05_Alignment_Integrity_QC.md:39`.
9. **DS-20 (6):** Trace oracle behaviour against the contract, including branches the tests miss. Read `02_Data_Solution_QC.md:68`.
10. **CL-4 (5):** Mutate exactly one independent fact; report its score. If using whole-document exactness, state that exactness in `instruction.md` and still show the one-fact result. Read `Final_checklist.md:491`.
11. **IN-16 (5):** For each graded boundary, key, order and tie-break, write two plausible readings; locate the sentence or separating shipped fact that chooses one. Read `01_Instruction_QC.md:46`.
12. **CL-2 (5), TS-25 (4):** Price a plausible hand-written forgery and list paying positives. Check whether any content check passes on empty/constant output. A small existence check is allowed. Read `Final_checklist.md:489`.
13. **JD-8/JD-14/JD-18 (5 each):** Pair observables across test/judge and inside judge; remove double payment. For authored code, add a genuine code-quality conduct criterion; verify the oracle satisfies it. Read `04_Judge_QC.md:77,91,99`.
14. **TS-16/TS-26 (4 each):** Run each negative on oracle and honest variants, then on the intended cheat. Pair all test observables to catch duplicate payment. Read `03_Tests_QC.md:47,53`.
15. **CL-1..CL-10:** Perform each client probe and record its requested number or file:line, including action evidence, forgery price, copied answers, one-fact score, hidden convention, suspect shipped value, path across corpora, oracle shortcut and verifier setup. Read `Final_checklist.md:488-498`.
16. **Scripts:** `python3 <KIT>/structure_qc.py BUNDLE`; then `instruction_qc.py`, `tests_qc.py`, `judge_qc.py` with the same arguments. Confirm script findings in source files. Read `Starter.md:33-68` and script headers.
17. **Step 11:** Independently rebuild promise-to-grading and grading-to-source maps; compare test and judge observables for overlap. Read `Final_checklist.md:424-431`.
18. **Step 10 before ship:** From fresh `exe_copy.py` copies on the final bytes, record oracle five times, nop, stub and owner-only. This is a later execution gate, not evidence claimed by this draft. Read `Final_checklist.md:339-420`.
