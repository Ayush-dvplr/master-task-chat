# district-heat v0 QC (kit bde868c4, 18:58 IST). Copy: ./qc_report_v1.md
Verdict FAIL: 11 fails, 5 minors, 4 warns. Scripts 0 FAIL. Step 10: oracle 1.0 x5, nop 0.0, stub -0.0072.
- F1 IN-16: waiver_signed_missing counting of skipped unknown-region lines ambiguous (mixed_rejection_counts_case 3).
- F2 DS-24: solve.py search restates the verifier (dead scale knob); 69/139 points cannot disagree.
- F3 TS-19: hidden large_tie extracts give 5 offers per site (contract max 4).
- F4 JD-7: R9 false of the reference (dead code). F5 JD-6: R10 not decidable from the final message.
- F6-F9 AL-27: SAFETY_HOLD over COOLDOWN, CERTIFICATE_PENDING label, objective components 4/5, weight-0 beneficiaries never triggered.
- F10 CL-2: judge pays a no-program forgery (0.2144 total, 0.3478 with cheap steps). F11 CL-3: R5, R13, R15 copyable from schema.md.
- Minors: TRUTH rejected-row count and root cause wording; TS-14 description; R9 compound; R4 preference.
- Warns: 41 checks > 35; negative_reads_tests too broad; setsid daemon cache; TS-20 weight swap.
Not yet rechecked (P8). Trajectory: pending.
