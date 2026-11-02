# KEPT: tariff-engine-audit-repair (P12 deb4e4a, for QC recheck after QL round 2)

| finding id | file:line | reason | kit line it rests on |
|---|---|---|---|
| TQ2-F1 (= DS-21 F08 carried) | environment/ci/api_contract.md:211-231 (rule), :25-28 (10 s limit); instruction.md:13 | REBUT. The statement rule, the limit and the whole-document exact bar are stated; input size is not information the rule needs. Lines byte-identical to QC copy e91a9d2 that passed (KEPT F08, v4:157/188/242/246). Stating or shrinking hidden scale is a TS-19 NEVER fix. | 02_Data_Solution_QC.md:70 ("Default to pass ... name the exact piece of information the solver cannot obtain"); Final_checklist.md:498 (CL-10); :492 (CL-5); 01_Instruction_QC.md:38 (IN-8) |
| TQ2-F2 (= TS-20, TS-26 carried) | tests/test_output.py:7568 `_SCALE_RNG`; :7672-7690 per-kind inputs; batch/cycle bodies :8599-8806; registrations :8820-8977 | REBUT. Three seeds, three different inputs; ordering right; weight approved (Ayush 29 Oct 09:12). Dropping or merging batch/cycle removes lever points (playbook section 0 NEVER). | 03_Tests_QC.md:51 ("Mild imbalance within the right ordering is a minor."); :53 ("What is NOT a duplicate") |
| TQ2-M1 | instruction.md:13; tests/test_output.py:7709-7765 | REBUT. A stated bar stricter than the per-part scoring is not a stale file, path, count or number. v4:236, v4:261 PASS. | 05_Alignment_Integrity_QC.md:75 (AL-18); Final_checklist.md:491 (CL-4) |
| TQ2-M2 | tests/judge.toml:89-100 (R7) | REBUT (minor at most). One observable, no dead code; it is the required code quality criterion. v4:210, v4:211 PASS. | 04_Judge_QC.md:99 (JD-18); :71 ("two facets of one act is a minor") |
| TQ2-M3 | solution/TRUTH.md:145, :153 vs :251, :259; tests/test_output.py:7420 vs :7352 | REBUT. Generator aim (4e10-8e10) and asserted guard (3e10-1e11) are two true statements about two things. | 02_Data_Solution_QC.md:78 (DS-22 "confirm the stated counts ... are the real ones") |
| TQ2-W1 (= TS-23/A3 F09 carried) | tests/test_output.py:8820-8977 (158 registrations) | KEEP warn with the count 158; never merge to reach 35. | 03_Tests_QC.md:62 ("at most 35 (warn)") |
| TQ2-W2 | tests/test_output.py:5590-5608 (memo lock); :7181 (10 s) | KEEP. Slowest statement child 1.36 s under 8 threads, --cpus 2 --memory 4g, after the F4 change (0 timeouts, oracle 670/670). | 03_Tests_QC.md:41 (TS-11) |
| TQ2-W3 | tests/judge.toml:11-22 (R1) | KEEP. Checking one's own output is a pass; JD-9 overlap at most a warn. v4:214, v4:220 PASS. | 04_Judge_QC.md:92 (JD-15); :86, :146 (JD-9 warn) |

Fixed this round (not kept): TQ2-F3 (tests/test_output.py:7823-7831), TQ2-F4 (:5638-5661, :7244, :7522), TQ2-M4 (solution/TRUTH.md:190-199). Line numbers are the fixed tree; old tree lines after :5637 moved by about +21.

## Lessons for the master
- none new | no change: every keep rests on a live kit line and a QC v4 PASS on byte-identical lines.
