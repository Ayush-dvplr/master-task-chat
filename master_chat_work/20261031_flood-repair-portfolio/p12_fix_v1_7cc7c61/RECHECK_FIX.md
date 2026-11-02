No fix lets the saved dae9563 program pass a hidden book: Docker re-score 30/108 before and 30/108 after, the same 22 checks fail (TIMEOUT on H1, H2, H3 plus reruns_identical).

# RECHECK_FIX 7cc7c61 flood-repair-portfolio (P12 fix v1)

QC report: QC/reports/flood-repair-portfolio/v1.md (FAIL, 3 fail / 1 minor / 2 warn), QC copy 5833b15 = BUNDLE tree bda9a0abef16.
Kit HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271 (Input_Bundle_QC; same as the QC run). Session rename: `opencode: ['ses_e6f5b53feffek69nEM8uausSdx']` shown.
Noise check (Always 13): BUNDLE is byte-identical to the QC copy and v1 is the first QC round, so there is no earlier passing round: no NOISE labels; every finding was rechecked on substance.
QL coverage table of v1: 27 PASS / 0 FAIL (no FAIL rows to recheck). FP_DOSSIER: no row for these rules.

Levers (LEVERS.md): LV-FP-1 exact optimum, LV-FP-2 conflict derivation, LV-FP-3 valuation, LV-FP-4 fault precedence, coupling (COUPLING G1).

| ID | label | rule quote (live kit) | evidence quote (bundle) | decision | playbook row | effect per lever | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| DS-22 ❌ | REAL | 02_Data_Solution_QC.md:78 "TRUTH.md describes the bundle that actually shipped"; fail list :117 "DS-22 TRUTH.md contradicting the shipped solution, the real grading" (ID, wording unchanged) | before: solution/TRUTH.md:10 "writes ten exact JSON documents", :62 "Eleven artifacts are collected", :157 "build the ten documents"; task.toml artifacts = 10 (program + 9 JSON), tests/test_output.py ARTIFACT_NAMES = 9, contract.md:68-78 = 9 documents | FIX (master direction): TRUTH.md:10 "writes nine exact JSON documents", :64 "Ten artifacts are collected and every one is graded:", :159 "build the nine documents"; defect 6 (:49-54) now names the AL-27 empty line; sha256 lines rewritten by script last | DS-22 DO (rewrite TRUTH to the shipped bundle) | all levers none | none needed | solution/TRUTH.md |
| JD-7 ❌ | REAL | 04_Judge_QC.md:76 "Every criterion must be satisfied (or, for negatives, avoided) by the shipped oracle in solution/"; fail :146 (unchanged) | judge.toml:105 R8 "The agent times a run of its program on the shipped book and compares the wall time with the 20 seconds"; before solve.sh:7 untimed shipped run, :163-165 timed run on an altered copy only | FIX (master direction, R8 wording kept): solve.sh:166-172 R7 run untimed; new fresh run of /app/out/derive_report.py on /app/data into a temp dir timed with time.monotonic(), `assert seconds < 20`, prints `check R8 ok (%.2f s for the shipped book)`. No judge integer depends on oracle output (R8 states 20 from contract.md:15): none regenerated | JD-7 DO (fix the oracle, never loosen the criterion); QC_RULINGS JD-7 rows "fix the oracle" | all levers none | none needed | solution/solve.sh |
| AL-27 ❌ | REAL | 05_Alignment_Integrity_QC.md:38 "a rule only counts as graded when the test's input actually constructs the situation where the rule matters"; fail :126 (unchanged) | contract.md:21 "a data row is any later non-empty line"; before tests/test_output.py:630-646 `_assemble` wrote CSV/TSV rows with single "\n", no empty line in any book | FIX (master direction, contract.md:21 unchanged): WORK/bookgen.py `_assemble` inserts one empty line after data row 50 of proposals.csv and permits.csv when the spec has `blank_row` (no rng draw, so all other bytes equal); WORK/hidden_meta.json H1, H2, H3 `"blank_row": 50` (shipped and M unchanged). Regenerated tests/test_output.py:650-655 (+6), H1-H3 sha256 and specs (:672, :685, :698). Faulty rows follow the empty line in every hidden book (H1 permits 264/1105/1199, proposals 158/406/506/540/591; H2 permits 475/505, proposals 188/340/375/788; H3 permits 641/729/1153, proposals 118/324/788). RULE_COVERAGE +2 rows: blank_line_counts_as_row fails 3 checks (99/108, h1-h3 data_quality), blank_line_ends_file fails 22 (30/108). Oracle 108/108 | AL-27 DO (hidden reseeded rows that construct the case inside the bounds; RULE_COVERAGE row) | LV-FP-4 harder (new empty-line case in the row-numbering family); LV-FP-1/2/3, coupling none | none needed (harder) | WORK/bookgen.py, WORK/hidden_meta.json, tests/test_output.py (generated), WORK/RULE_COVERAGE.md |
| JD-5 🟡 | REAL | 04_Judge_QC.md:71 "Each criterion names ONE observable behaviour ... Clearly compound criteria are a fail" (unchanged) | before judge.toml:14 R1 "recomputes the benefit of every proposal in the chosen portfolios and of every VALUE audit row" (two objects) | FIX (master direction, no split, weight 3 kept): judge.toml:14 "The agent independently recomputes the benefit of every planned VALUE audit row of the shipped book from the rate, risk and site tables outside its program and compares them with the program's output." | JD-5 DO (narrow) | LV-FP-3 none (benefit recomputation still paid; portfolio benefits still graded in tests); others none | none needed | tests/judge.toml |
| TS-15 ⚠️ | REAL | 03_Tests_QC.md:46 "Each negative check should carry an inline comment stating the inversion." (unchanged) | before test_output.py:1259 "# Cheat present: the source names the /tests tree or the verifier log folder." vs :1260 regex matches only `/tests` | FIX (master direction, regex unchanged): WORK/tests_template.py:580 comment -> "# Cheat present: the source names the /tests tree."; now test_output.py:1268 | NEW-CHECK hygiene (comment matches code; TS-16-like) | all levers none | none needed | WORK/tests_template.py, tests/test_output.py (generated) |
| TS-11 ⚠️ | REAL by the letter, KEEP | 03_Tests_QC.md:41 "Deterministic ... elapsed-time bounds" | test_output.py:37 `BOOK_SECONDS = 20`, :1143 `timeout=BOOK_SECONDS`; contract.md:15 "within 20 seconds of wall time" | KEEP: Ayush exception 31 Oct 11:45 "flood-only time-out exception (losses by time-out may be the whole lever, like outage)"; the bound is stated to the agent at contract.md:15 | TS-11 KEEP (authority, owner exception) | LV-FP-1 would get easier if removed; kept: none | n/a | none |
| Oracle x3 (ack) | KEEP | Final_checklist.md:390 "Every one of the five oracle runs must read exactly `1.000`" | QC v1 Step 10: oracle 1.000 x3 | KEEP: Ayush acknowledgement (oracle x3 instead of x5); fix gate also x3, all 1.000 | n/a | none | n/a | none |

## Deviations from master directions
None. G1-G7 checked: no Fix line pasted blindly (TS-15 regex untouched, R8 wording untouched); no assert moved into an existing check; no clause deleted; G6 TRUTH sha lines by script last; G7 diff below.

## G7 byte diff of tests/ (generator regeneration)
WORK/tmp/al27/tests_g7.diff vs WORK/qc1_bda9a0abef16/tests: only hunks (1) +6 lines bookgen `blank_row` block (AL-27), (2) H1/H2/H3 sha256 and `'blank_row': 50` in their specs (AL-27), (3) negative comment (TS-15). judge.toml hunk: R1 description (JD-5). Every hunk is named by a direction: PASS.

## Touched rules
| id | touched how | rules re-checked | verdict with file:line |
|---|---|---|---|
| R1 recomputes_benefits_outside_program | re-worded (weight 3 kept) | JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, AL-28 | PASS: judge.toml:14 one object (planned VALUE audit rows), visible in trajectory (JD-2), conduct only (JD-15), oracle solve.sh:96-98 asserts every planned VALUE row benefit and prints `check R1 ok` (JD-7), no overlap with R2 (PAIR rows), R3 (rejections), R4/R5 (rollups), R6 (portfolios) (JD-9/JD-14), positive so AL-28 n/a |
| h1/h2/h3_book_* (21 checks) + reruns_identical | input changed (H1-H3 carry the empty line), code and weights unchanged | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4 | PASS: one whole document per check (TS-13), oracle 108/108 host and Docker (TS-14/TS-25), weights 3/5 unchanged (TS-20), stacking_check groups unchanged (different books, TS-26), CL-2/CL-4 unchanged (a fresh book still graded whole, contract.md:21 states the rule) |
| negative_program_reads_verifier_files | comment only (test_output.py:1268) | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4 | PASS: regex :1269 unchanged, weight -5 unchanged, oracle avoids it |

## Vacuity probe
Unedited environment/ ships no /app/out/derive_report.py; a program that does nothing (`import sys`) through every check (WORK/run_tests.py, WORK/tmp/vac/nop.json): 0/108, passed positive checks: []. Judge: every positive criterion R1-R10 needs an agent action (recompute, rerun, time, leave a program, list rounds); an agent that changed nothing earns 0 of 30. PASS.

## Gate results
- WORK/run_tests.py oracle (solve.py): 108/108 (host) and 108/108 (Docker, fixscore ref).
- Harbor fixgate (exe_copy.py copies, `_runs/20261031/flood-repair-portfolio/fixgate-20261031T121057-69b5/`): see Fix receipt (c).
- xref_check: 36 entries, 0 findings. stacking_check: unchanged (OUT/STACKING_CHECK.md). PRECHECK: `PRECHECK CLEAN`.

## Side effects
| FIX id | ids re-checked (FIX_SIDE_EFFECTS) | result |
|---|---|---|
| JD-5 | JD-2, JD-7, JD-9, JD-15, IN-8 | PASS: see Touched rules R1; IN-8 R1 rests on contract.md:48 (benefit formula) and :72 (policy_audit VALUE rows), both agent-visible |
| JD-7 | JD-15 | PASS: R8 conduct only; oracle now satisfies it (solve.sh:167-172) |
| AL-27 | TS-13 | PASS: no check gained a second assert; the empty line only changes inputs of existing whole-document checks |
| DS-22 | AL-18, DS-27 | PASS: TRUTH counts match task.toml (10 artifacts) and ARTIFACT_NAMES (9); sha lines match |
| TS-15 | TS-16 | PASS: comment states the inversion the regex tests |

## Noise keeps
None (first QC round; no earlier passing round to compare).

## Trap survival
| lever | single wrong-reading variant | loss before | loss after | kept |
|---|---|---|---|---|
| LV-FP-1 exact optimum | mutants/greedy_swaps | 83 (25/108) | 83 (25/108) | 100% |
| LV-FP-2 conflict derivation | mutants/no_permit | 101 (7/108) | 101 (7/108) | 100% |
| LV-FP-3 valuation | mutants/no_override | 98 (10/108) | 98 (10/108) | 100% |
| LV-FP-4 fault precedence | mutants/row_within_round | 15 (93/108) | 15 (93/108) | 100% |
| LV-FP-4 fault precedence | mutants/fixed_file_order | 3 (105/108) | 3 (105/108) | 100% |
| LV-FP-4 (new case) | rule_mut/blank_line_counts_as_row | - | 9 (99/108) | added |
No separating hidden case removed (H1-H3 and M keep every planted fault; only an empty line was added). PASS.

## Fix receipt
(a) bundle tree sha before bda9a0abef16 (QC copy 5833b15); after cd11476e6e14 (BUNDLE) = cd11476e6e14 (new Tasks_INPUT/flood-repair-portfolio, rsync -a --delete), method `find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256 | shasum -a 256 | cut -c1-12`.
(b) changed test checks / judge criteria: none re-weighted, added or deleted; R1 re-worded 3 -> 3. Positive totals: tests 108 -> 108, judge 30 -> 30; negatives tests -8 -> -8, judge -5 -> -5.
(c) oracle / owner / nop: before 1.000 x3 / 1.000 / 0.000 (QC v1); after (Harbor 0.24, live kit exe_copy.py copies, `fixgate-20261031T121057-69b5`, warm images first, 3 lanes each on dockfree START=yes): oracle-1 1.0 (plain__2DgbeX9), oracle-2 1.0 (plain__Cydm6XJ), oracle-3 1.0 (plain__LwzG7P4), owner-1 1.0 (owner__8X3vdv4), nop-1 0.0 (plain__P6ZkqMJ). Oracle agent log prints `check R1 ok` .. `check R7 ok` and `check R8 ok (0.25 s for the shipped book)`.
(d) dae9563 program (`_runs/20261031/flood-repair-portfolio/blind-20261031T1050-3bee/app/derive_report.py`) re-scored in Docker (`fixscore-20261031T120812-7c05`, tests image from bundle tests/Dockerfile, `--cpus 2 --memory 4g -e TMPDIR=/app/tmp`): before 30/108 (score-dae9563), after 30/108; the same 22 checks fail (h1/h2/h3_book_* TIMEOUT at 20.4 s, reruns_identical 40.06 s); no lever check moved.
(e) rescan after the last edit:
- AL-18 / DS-22 / DS-27: PASS. TRUTH.md:6 nine data files (environment/data has 11 files = 9 data + manifest.json + contract.md), :10 nine documents, :64 ten artifacts (task.toml artifacts = 10), :159 nine documents; :181 fix_patch_sha256 0a6e0b73.. = `shasum -a 256 solution/solve.sh`, :182 solve_py_sha256 4191f4c1.. = solve.py; Verification counts (32 positive checks 108, negatives -5/-3; 10 criteria 30, R11 -5) match tests_qc / judge_qc and stacking_check.
- JD-14 / AL-28: PASS. R1 pays for planned VALUE audit rows only; no other criterion or check pays for that claim; penalty groups 5 / 3 / 5 (stacking_check section 3).
- AL-1 / AL-2: PASS. Every promise (program path, nine documents, fresh books whole and exact, 20 s, rejected rounds in the reply) maps to a check or criterion (EVIDENCE_MAP.md unchanged); the empty-line case is stated at contract.md:21, so nothing new is graded that is not promised.
- AL-27: PASS. WORK/RULE_COVERAGE.md 49 rule rows, each with >= 1 failed check; the two new contract.md:21 rows fail 3 and 22 checks. precheck `PRECHECK CLEAN`; xref_check 36 entries, 0 findings.

## QC_RULINGS rows
- AL-27 | contract.md:21 "a data row is any later non-empty line" had no empty line in any book | QC v1 ❌ | REAL | fixed by one empty line after data row 50 of proposals.csv and permits.csv in H1-H3, faulty rows after it (as cohort v3:44, district-heat v4:39)
- JD-7 | R8 "times a run of its program on the shipped book" while solve.sh timed only an altered copy | QC v1 ❌ | REAL | fixed the oracle (timed fresh run on /app/data, assert < 20 s), criterion wording kept

## Lessons for the master
- An oracle self-check that times an altered copy does not satisfy a criterion that names the shipped book; time the object the criterion names | template_change: no change: JD-7 playbook row already says fix the oracle
- A contract sentence about blank lines needs a fixture in the hidden assembly, not only in audit_queries.txt; generators should plant one per tabular file the rule covers | no change: AL-27 RULE_COVERAGE gate catches it once a mutant per sentence clause is written
- A stale comment left after narrowing a negative regex costs a TS-15 warn; update the comment in the same edit | no change: one-off
