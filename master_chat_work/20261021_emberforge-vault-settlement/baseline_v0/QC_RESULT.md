# emberforge v0 QC (kit bde868c4, 18:56 IST). Copy: ./qc_report_v1.md
Verdict FAIL: 3 fails, 3 minors, 3 warns. Scripts 0 FAIL. Step 10: oracle 1.0 x5, nop 0.0, stub 0.0.
- F1 IN-16/AL-4: S6 already-credited salvage vs N3 "every condition" (UNCREDITED_SALVAGE too?) decides cap_and_floor_one_findings (5).
- F2 AL-3/CL-5/CL-6: record_shapes.md says ", " separator, graded form uses "," (weight 1).
- F3 AL-27: RETIRED_REAGENT tie-break (first of several retired reagents) never triggered.
- Minors: TRUTH requisition count; negative_rebinds weight -1 -> -5; judge R5 compound.
- Warns: 50 checks > 35; R7 could be an AST negative; grade/ordinal JSON type unstated.
Not yet rechecked (P8). Not caught by QC: the 0600 program / setpriv verifier bug.
