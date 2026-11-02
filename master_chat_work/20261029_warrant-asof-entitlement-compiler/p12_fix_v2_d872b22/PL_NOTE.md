# PL note: warrant-asof-entitlement-compiler (P12 v2, d872b22)

All four v2 findings were real and are fixed in tests/test_output.py only. No false positives and no open questions.

Fixed:
- AL-2: report_transcript_complete now also needs both profile digests in report.json and resolve-config listed before the compiles, the audit and summarize. A wrong digest value is still charged by negative_report_digest_mismatch (-3). We did not also put "digest equals the file" into the positive, because then one wrong digest would be paid twice: once by the positive and once by the negative (03_Tests_QC.md TS-26). Now a missing digest costs 1 point and a wrong one costs 3, never both.
- AL-28: negative_partial_output_on_missing_input now stands down for a tool that gives the same profile for every corpus, which negative_tool_ignores_input already charges -5. Probe: before a constant tool paid -5 and -3, now it pays -5 only.
- TS-13: summary_identity_triangle now only checks that summary.json equals the recomputed summary. Profiles and report lists already have their own checks.
- TS-29: artifacts_contract_layout reads the file through the guarded reader first. The digest helper also skips non-regular files.

Kept (carried over, unchanged from v2, where QC acknowledged them):
- X1 warn: environment/data/tool.zip is the legacy tool archive the task repairs (structure_qc.py:71 binary files warn).
- TS-23 / A3 warn: 47 checks, so above the 35-check warn line (03_Tests_QC.md:62). No count cap; each check is its own corpus or property.
- CL-4 rebut: the instruction says that only an exact match counts (Final_checklist.md:491).
- Step 10: oracle x3 per Ayush's rule.

Gate on the fixed bytes: oracle 1.0 x3, owner-only 1.0, nop 0.0; a1 and kill rows score exactly as before (a1 48.4).
