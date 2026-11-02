# PL note: sentinel-policy-recompute, QC v8 fixes (3157183)

All four v8 findings were real and are fixed:
- CL-1/AL-2 (fail): the check that config.json is exactly what the repaired tool writes from the authoritative values is back, now as its own small check (weight 1). It was lost when the v7 split separated the config and profile checks.
- DS-22 (two minors): TRUTH.md now gives the right solve.py line count (1231) and lists the two new reruns, and the broken sentence is repaired.
- JD-5/JD-3 (minor): the code-quality criterion R12 no longer says "maintainable". It now names one act: the tool's exception handlers stop the run with a message naming an unreadable or unparsable reference file.

Kept warns (same as last round, with evidence):
- TS-23/A3: 41 checks, above the cap of 35. The kit grades this as a warn (tests_qc A3 "cap is 35 (warn)"). The extra check is the restored one; merging it back into another check would bring back the v7 one-property-per-test finding.
- X1: 8 binary data files (parquet, xlsx, zip) are skipped by the text scan. This is a structure_qc warn, unchanged since v4.

No false positives and no open questions.
