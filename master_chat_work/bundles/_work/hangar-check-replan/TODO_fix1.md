# TODO fix1 (QC v1, board 2eb1638) — build TODO kept as TODO_build.md

Scratch: /Users/mac/Desktop/Terminal Bench/_runs/20261101/hangar-check-replan/fix1-20261101T1639/
Pre-fix copy: WORK/fix1_pre/ (tree 3df66c1d1ab2), digests WORK/fix1_pre_digests.txt

- [x] 1 Record tree sha 3df66c1d1ab2 + per-file digests; rename session (no literal 2eb1638 match; noted)
- [x] 1b Fingerprint check GEN + QC (Always 1)
- [x] 2a IN-16/TS-19: _run_program creates work/out 0777 before each run (tests_harness.py)
- [x] 2b AL-27: two-fault rows per adjacent pair + bad available_from row in hidden folders; reason graded in hidden data_quality
- [x] 2c TS-13: split shipped data_quality from shipped_plan_rows_and_rejections; split rows/group totals in hN_plan_fields
- [x] 2d JD-16 R10 test: missing input -> non-zero exit, stderr names file
- [x] 2e AL-2: per-run guard cwd outside OUT_DIR + data folder unchanged
- [x] 2f rebuild tests (build_tests.py), G7 byte diff, local oracle/nop run
- [x] 2g G12 survey 300 seeds
- [x] 2h judge: R11 reword (JD-8), R13 type (JD-16), R14 scope (AL-28), R10 split + R12 clause drop (JD-5); reward.toml weights
- [x] 2i task.toml description + keywords (IN-12)
- [x] 2j solve.py DS-20 InputError wrap
- [x] 2k TRUTH.md :74 :97 probe path (DS-22), truth_sha.py last
- [x] 2l xref_check -> 0
- [x] 2m EVIDENCE_MAP, JUDGE_MAP, QC_DEFENCE, RECHECK_FIX.md rows
- [x] 3 stacking_check, precheck CLEAN, QC 4 scripts, validator
- [x] 4 Docker lanes: oracle x3, owner-only, nop, stub (verifier s)
- [x] 5 kill table 17 wrong + design blind
- [x] 6 sync Tasks_INPUT, diff -rq, shas
- [x] 7 OUT: FIX_REPORT.md, KEPT.md, result_2eb1638.json; rename session
