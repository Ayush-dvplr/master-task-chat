# schema-migration v0 QC (kit bde868c4, 20:44 IST). Copy: ./qc_report_v1.md
Verdict FAIL: 8 fails, 2 minors, 5 warns. Scripts 0 FAIL. Step 10 PASS: oracle 1.000 x5, nop 0.000, stub 0.007.
- F1 CL-2: unrepaired code + plausible JSON earns 13.4%; 4 checks pass on shipped code (same as P3).
- F2 JD-8: judge R7-R13 restate rules the tests grade and are copyable from the contract.
- F3 AL-27: alias-equals-partner-id, multiple corrections per record (C4), N6 null-before-planning never triggered.
- F4 Step 11: K7, K11, K12, K15, K17, K18, N7 have no checker.
- F5 TS-17: loose == (17.0 == 17, True == 1).
- F6 TS-24: no process-group kill; world-writable scratch without sticky bit.
- F7 DS-27: TRUTH carries lever taxonomy and names QC tooling.
- F8 IN-12: category "Data Processing" should be "Software Engineering".
Not in this QC: validator 1.4/5.5 repo-patch layout (validator, not QC). Not yet rechecked (P8).
