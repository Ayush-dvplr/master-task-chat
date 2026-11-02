# PL note: tariff-engine-audit-repair, QL round 2 (deb4e4a)

Three items fixed (F3, F4, M4). Eight are not changed; reasons with the kit line and the bundle line below. No open questions.

## Fixed
- TQ2-F3 (partly right): the delivered `tests/test_visible.py` is now run against the delivered package, as `nobody`, in the same check as the verifier's corrected copy (tests/test_output.py:7823-7831); the check passes only if both pass, weight 3 unchanged. A delivered test that asserts 9.31 now fails it. The verifier's own copy stays, because it is what stops a solver from emptying assertions. "Never checked" was overstated: test names, the changed tests and their preservation were already checked (:7848-7855).
- TQ2-F4: every program the tests start now runs in its own session, and its whole process group is killed when the call returns or times out (tests/test_output.py:5638-5661, :7244, :7522), as 03_Tests_QC.md:71 requires. Time limits and the user are unchanged. A left-behind child is now gone after both a normal return and a timeout.
- TQ2-M4: TRUTH.md:190-199 now says which checks run the package and names the four that only read the delivered JSON (module notes, summary, repair report, previously failing).

## False positives (not changed)
- TQ2-F1: The rule (api_contract.md:211-231) and the 10 second limit (:25-28) are both stated, and instruction.md:13 says statements are graded whole on fresh inputs. No kit line asks for input size to be stated: DS-21 (02_Data_Solution_QC.md:70) and CL-10 (Final_checklist.md:498) say hard or long derivation is not a defect, and CL-5 (:492) and IN-8 (01_Instruction_QC.md:38) cover order, names, strings, error shapes and tolerances, not input size. Same lines were kept at the last QC.
- TQ2-F2: The three statement sets are built from three different seeds (tests/test_output.py:7568, :7672-7690), so they read different inputs, which 03_Tests_QC.md:53 says is not a duplicate; the weight balance was kept with 03_Tests_QC.md:51 at the last QC.
- TQ2-M1: AL-18 (05_Alignment_Integrity_QC.md:75) is about stale files, paths, counts and numbers. instruction.md:13 sets a stricter bar than the per-part scoring (tests/test_output.py:7709-7765), which cannot lead a solver to a lower score.
- TQ2-M2: R7 (judge.toml:89-100) checks one thing, no dead code, which is the code quality criterion 04_Judge_QC.md:99 asks for; /app/repo is where instruction.md:3 says the repair happens. At most it is two parts of one act, a minor by 04_Judge_QC.md:71.
- TQ2-M3: TRUTH.md:145 and :153 give the range the generator aims for (tests/test_output.py:7420, 4e10 to 8e10); TRUTH.md:251 gives the wider guard the tests assert (:7352, 3e10 to 1e11). Both are true.

## Kept warns
- TQ2-W1: 158 checks (tests/test_output.py:8820-8977) recorded as the warn 03_Tests_QC.md:62 sets; merging checks only to meet the count is not done.
- TQ2-W2: the shared result lock (tests/test_output.py:5590-5608) is in place; the slowest statement call measured 1.36 s with 8 threads after the F4 change, against the 10 s limit (03_Tests_QC.md:41).
- TQ2-W3: R1 (judge.toml:11-22) rewards checking your own output, which 04_Judge_QC.md:92 lists as a pass; a JD-9 overlap is at most a warn (04_Judge_QC.md:146).

## UNSURE
None.
