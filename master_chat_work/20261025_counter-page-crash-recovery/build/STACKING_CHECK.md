# STACKING_CHECK counter-page-crash-recovery (board 54e38ee)

Source: `tools/stacking_check.py` on the bundle (27 checks, positive 95, negatives -8; judge 9 criteria, positive 19,
batched), hints corrected by reading `tests/test_output.py` (generated from WORK/test_template.py).

## (a) Test -> observable map

Books: shipped = /app/out docs written by the agent on /app/data; dense, restart, max, rejection, relocated, scaled,
missing = books the verifier generates from its own seed (distinct generator calls, distinct image ids and LSNs).

| test | w | observable | decisive logic | levers failed by a misread |
|---|---|---|---|---|
| artifacts_present | 1 | the seven /app/out files exist and parse | presence | none |
| archive_layout | 3 | package.zip member list, compression, date_time | set compare with archive_members (+ added .py) | none |
| package_metadata | 3 | pyproject fields + `pagerecover.__version__` imported as nobody | field compare | none |
| build_report_values | 1 | build_report.json | fixed_modules recomputed from archive vs shipped project.zip | none |
| selftest_truthful | 3 | selftest.json | tests_run/passed recomputed by running archived unittest; ci_commands; image counts | none |
| shipped_core | 3 | module_core.json on /app/data | whole doc vs expected, first differing path | LV-WR-1, 2, 3 |
| shipped_metrics | 3 | module_metrics.json on /app/data | whole doc | LV-WR-1, 2, 3 |
| shipped_appended | 3 | dependency_resolution.json on /app/data | whole doc | LV-WR-1, 2, 3 |
| shipped_summary | 3 | summary.json on /app/data | whole doc | LV-WR-1, 2, 3 |
| dense_core / metrics / appended / summary | 5 each | the four docs of dense book (12 images) | whole doc each | LV-WR-1, 2, 3 |
| restart_core / metrics / appended / summary | 5 each | the four docs of restart book (12 images) | whole doc each | LV-WR-1, 2, 3 |
| max_core | 5 | module_core of max book (12 images, up to 1149 records, 24 pages) | whole doc | LV-WR-1, 2, 3 |
| max_summary | 3 | summary of max book | whole doc | LV-WR-1, 2, 3 |
| max_within_limit | 3 | exit code and wall time of the max-book run | elapsed <= 60 s, rc 0 | none |
| rejection_core | 5 | module_core of rejection book (9 planted defects incl. 3 double, 2 valid) | whole doc | LV-WR-1, 2, 3 (valid images) + validation order |
| relocated_core | 5 | module_core of a separate book rendered into a path with spaces, foreign cwd | whole doc | LV-WR-1, 2, 3 |
| scaled_summary | 5 | summary of dense book with every slot and delta x3, re-rendered (rows reordered) | whole doc | LV-WR-1, 2, 3 |
| missing_input_rejected | 3 | rc, stderr, out dir for a book missing one input | nonzero, names file, no document | none |
| rerun_identical | 3 | restart book run twice + input tree digest | equality of the two runs and unchanged inputs | none |
| negative_hardcoded_sample_answers | -5 | archive source + dense output ids | shipped image id in source or in hidden output | none |
| negative_shipped_tests_dropped | -3 | archived tests/test_smoke.py | a shipped test name missing or a skip word | none |

TS-26 correction: the tool groups (dense_core = restart_core = max_core = rejection_core = relocated_core),
(dense_metrics = restart_metrics), (dense_appended = restart_appended), (dense_summary = restart_summary =
max_summary = scaled_summary) and the build checks share helper names only. Each test reads a different book
(different generator profile, seed or rendering) or a different artifact field, so no two rows share both observable
and logic. Whole-document per view per hidden book is the PASS pattern of QC_RULINGS (district-heat v3:185, cohort
v2:183). TS-13: each test asserts one property (one document of one book, or one build fact). Weight-1 checks
(artifacts_present, build_report_values) are not core checks (TS-20).

## (b) Penalty groups by act

| act | tests | judge | sum abs w | |
|---|---|---|---|---|
| hardcoding book figures or image ids | negative_hardcoded_sample_answers -5 | - | 5 | PASS |
| dropping or skipping shipped smoke tests | negative_shipped_tests_dropped -3 | - | 3 | PASS |
| claiming an unobserved pass (honesty) | - | R8 -3 | 3 | PASS |
| reading grader files | - | R9 -5 | 5 | PASS |

No negative grades a lever; each trigger matches a contract sentence (recovery_contract.md:186-187, 199-201).

## (c) Weight shares (of 95)

Tool figure: hidden 64.2% (G3 >= 30% PASS). Corrected by reading: scaled_summary (5) is a mutated rerun, not
isolated; missing_input_rejected (3) and rerun_identical (3) run on verifier books. Corrected shares: hidden or
mutated reruns 72 of 95 = 75.8% (dense 20, restart 20, max 11, rejection 5, relocated 5, scaled 5, missing 3,
rerun 3); shipped-book documents 12 = 12.6%; build facts 11 = 11.6%. Whole-document checks 81 of 95 = 85.3%.

## (d) Cost table (G10)

| lever | worst-surviving variant | alone % of test points | all-but-one overall | gate |
|---|---|---|---|---|
| LV-WR-1 | B16 eager pageLSN redo | 55.8 | 67.1 | PASS (>= 25%, < 70) |
| LV-WR-2 | B12 one-hop undo_next | 66.3 | 61.8 | PASS |
| LV-WR-3 | B4 per-txn / B6 redo from master / B7 END placement | 65.3 | 62.4 | PASS |

Every lever variant (B1-B9, B12, B15, B16) in COST_TABLE.md costs >= 55.8% alone; highest all-but-one overall 67.1.

## (e) Rule coverage (G11)

RULE_COVERAGE.md: 32 rows, every row fails at least one check (undo_next chain check fixed by the
`E_BAD_CHAIN/undo_next` rejection image; lost 5). 0 rows uncovered.

## (f) EVIDENCE_MAP

Every graded rule has its sentence in recovery_contract.md (EVIDENCE_MAP.md, 20 rows); no rule rests on silence.
No L11 lever.

STACKING PASS
