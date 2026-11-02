# P12 recheck and fix of QC v2 (4fef871), board 905cf6e: cold-chain-backbone-quote

Live kit: Terminal_2.0_Harbor_Harness HEAD 5574d77eb9f22c207ba05fd8f9ac31d42ba45271. Noise check (Always 13): `diff -rq` QC v2 copy (4fef871) vs BUNDLE is empty; every cited line below changed between QC v1 (4e298da) and QC v2, or was made stale by a v2 change, so no finding is NOISE.

## Findings

| ID | label | rule quote (live kit) | evidence | decision | playbook row | effect per lever | compensation | files changed |
|---|---|---|---|---|---|---|---|---|
| G11-1 AL-2 (fail) | REAL | 05_Alignment_Integrity_QC.md:33 AL-2 "Everything promised is graded ... For each requirement so enumerated, point to the test or the judged criterion that checks it" (ID and wording unchanged) | instruction.md:13 "list the projects of the current book that the command rejects, with their codes"; judge.toml:131 R10 (v2) "names every project of /app/ci that /app/out/module_parser.json records as rejected." (no code); R12 judge.toml:157 punishes only a wrong code. v1 R10 graded the code; v2 dropped it after the master's JD-14 direction | FIX: R10 -> "...records as rejected and gives a rejection code for each." Weight 3 and annotations unchanged; R12 unchanged (R10 = a code is present for every rejected project; R12 = a code differs from the file: different acts, JD-14 not reopened) | AL-2 (DO: grade the request through an observable) | all levers none (judge only; R10 is not a lever criterion) | none needed | tests/judge.toml |
| G04-M1 JD-6/JD-7 (minor) | REAL | 04_Judge_QC.md:72 JD-6 "Self-contained: the judge sees the trajectory and artifacts, not your head"; 04:76 JD-7 "Every criterion must be satisfied ... by the shipped oracle" | judge.toml:66 R5 "larger and reaches further than the shipped book" names no dimension; oracle line solve.py:808 prints the built book's totals (2 projects, 60 cold rooms, gap 82) but never the shipped book's figures, so the judge must know the shipped book | FIX: R5 -> "a book it builds itself in which one project has more sites or cold rooms than any project of the shipped book and an open link spans more corridor positions than any link of the shipped book" (no figures); oracle check line also prints the shipped book's largest project and largest gap next to the built book's so the trajectory shows both sides | JD-7 (DO: oracle meets; never loosen) | P-5 probe band unchanged (R5 stays a w3 trajectory probe); all other levers none | none needed | tests/judge.toml, solution/solve.py |
| G05-M1 AL-18 (minor) | REAL | 05_Alignment_Integrity_QC.md:75 AL-18 "No stale references: nothing mentions files, paths, counts, or numbers that do not match the actual bundle" | solution/TRUTH.md:67 `\| rejections \| 10 \| 50 \| 0.04 \|` while tests/test_output.py:6106-6107 build the rejection book from 11 plan entries (11 projects, limit 4*11+10 = 54) | FIX: re-measure every book in Docker (--memory 4g --cpus 2) with WORK/time_books.py and rewrite the timing table by script; check every other TRUTH row against current tests | AL-18 (DO: recompute from outputs, last, by script) | none | none needed | solution/TRUTH.md |
| G03-W1 TS-26 (warn) | REAL | 03_Tests_QC.md:53 TS-26 "Two tests reading the same observable with the same decisive logic pay (or punish) one behaviour twice ... rewrite one to read a different observable" | test_output.py:6524-6531 `_check_relocated` and `_check_rerun_identical` both begin with `_quotes_own_networks(...)`, the decisive logic of fresh_* quote checks | FIX with deviation: guard = non-empty projects AND the run's four documents differ from those the unedited shipped package writes for the same book (embedded canonical digests). See Deviations | TS-26 (DO: narrow so each reads a different observable; keep weight in family) | measured in Trap survival | none needed if >= 90% kept | tests/test_output.py (via WORK/test_template.py + embed_tests.py) |
| G05-3 CL-10/AL-4 (carry-over) | KEEP (acknowledged in v2) | as in KEPT.md item 1 | unchanged | KEEP, copied to KEPT.md | NOISE/carry-over | none | none | none |

## Deviations from master directions
- Finding 4 (TS-26): the master's example guard (non-empty projects plus documents that differ from the shipped artifacts in /app/out) would hand the unedited package relocated (3) + rerun (1) = 4 points: its fresh_1/fresh_2 documents are not the /app/out documents of the shipped book, so the guard passes and the run is deterministic and path-free. Guard G5 forbids that. Kept the master's observable family (non-empty projects; documents differ from the shipped package's own output) but compared against the unedited shipped package's documents for the same hidden book, embedded as canonical sha256 digests. The guard no longer reads the quote recomputation of the fresh checks.

## Touched rules
| id | touched how | rules re-checked | verdict with file:line |
|---|---|---|---|
| judge R10 | re-worded (adds "and gives a rejection code for each") | JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, AL-28, JD-14 vs R12 | pass: tests/judge.toml:131 one act (the reply's rejected list, each entry with its code); decidable from the final answer and /app/out/module_parser.json; oracle reply `rejected projects: P2495 E_DUP_SITE, ... P8710 E_UNKNOWN_ENDPOINT` (solve.py final print); w3 and annotations unchanged; label instruction following, sentence instruction.md:13; R10 reads presence of a code, R12 (judge.toml:157, -5) reads a code or quote that differs from the file: different observables, not a negative so AL-28 unaffected |
| judge R5 | re-worded (two named dimensions against the shipped book, no figures) | JD-2, JD-5, JD-6, JD-7, JD-9, JD-13, JD-15, AL-28 | pass: tests/judge.toml:66 one act (timed run on a built book), the book is defined by two comparisons the judge can read off the trajectory; oracle line `largest project 85 sites and 30 cold rooms against 52 sites and 10 cold rooms in the shipped book; widest open link spans 82 corridor positions against 42 in the shipped book; finished in 0.07 s of the 18 s limit` (solve.py far-book check); w3 unchanged; process probe (P-a), odds-raising; no size, scale or method word, no figure |
| relocated_book_documents | guard replaced (unedited-package digest) | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4 | pass: tests/test_output.py `_check_relocated` one property (relocated run equals the package's own fresh_2 run); honest repaired package cannot equal the unedited package's documents (those carry wrong quotes, runs/v2_chain.log shipped run); w3 unchanged; fails on absence (exit != 0 or empty projects); guard reads a digest of the unedited package's output, the fresh checks read quote recomputation: different observables; unedited package earns 0 here (vacuity) |
| rerun_identical | guard replaced (unedited-package digest) | TS-13, TS-14, TS-20, TS-25, TS-26, CL-2, CL-4 | pass: same as above on fresh_1; w1 unchanged; R6 (judge, trajectory act) is a different layer and observable |

## Side effects
| FIX id | ids re-checked (FIX_SIDE_EFFECTS + common rule 14) | result |
|---|---|---|
| G11-1 AL-2 | TS-25, JD-14, JD-5 | judge criterion, so TS-25 n/a; R10/R12 read presence vs correctness; one act; pass |
| G04-M1 JD-6/JD-7 | JD-15, JD-2, JD-9 | probe label agent behavior/process kept, w3; oracle meets; pass |
| G05-M1 AL-18 | DS-22, AL-19 | TRUTH timing table and score line rewritten by WORK/truth_v2.py from measured json, sha256 by finalize_truth.py last; precheck DS-22 clean |
| G03-W1 TS-26 | TS-14, TS-25, TS-13, CL-2 | honest-untrippable, fails on absence, one property each, unedited package 1/109 (only the archive check); pass |

## Noise keeps
None. `diff -rq` of the QC v2 copy (4fef871) against BUNDLE before this round was empty, and every cited line changed between QC v1 (4e298da) and QC v2 (judge.toml:66, :131; test_output.py `_quotes_own_networks`; TRUTH.md:67 made stale by the 11-project rejection book), so no finding is variance.

## QC_RULINGS rows
- TS-26 | relocated/rerun checks guarded by the same quote==own-network-cost assertion as fresh_networks_feasible | WARN G03-W1 (v2) | REAL | guard now reads a different observable: non-empty projects and documents that differ from the unedited shipped package's documents for the same book (embedded digest); weights unchanged.
- JD-7 | R5 "larger and reaches further than the shipped book" with no dimension | MINOR G04-M1 (JD-6/JD-7) | REAL | names the two dimensions (sites or cold rooms of one project; corridor positions spanned by an open link) against the shipped book, no figures; oracle prints its built book's values beside the shipped book's.

## Vacuity probe
- Tests (Docker, runs/v2_chain.log, fixed tests): the unedited shipped repo and book, archived per build_config, its own command run on /app/ci: 1/109, only archive_follows_build_config (the packing act). relocated_book_documents and rerun_identical now fail on the new guard ("documents equal those of the package as shipped"), so they earn nothing. True nop (nothing delivered): 0/109. PASS.
- Judge: R1-R8 each need an act in the trajectory (a run, a recount, a built book, a defect named before an edit); R9 needs an edit to core.py; R10 needs a reply naming each rejected project with a code. An agent that changed nothing earns 0 judged points. PASS.

## Gate results
- judge_qc.py: SUMMARY 19 pass, 0 warn, 0 fail (positive 32, negative 11).
- xref_check: 13 entries, 0 findings (no rename, no value changed in XREF).
- Digest gate (G7): every hidden book, every expected document, the shipped documents and every regression case outcome are byte-identical before and after (runs/v2_digest_before.json == runs/v2_digest_after.json, full sha256).
- G7 tests/ byte diff (runs/v2_g7_tests.diff): judge.toml 66, 131; test_output.py import line, the guard (6516-6529) and its two call sites. Every hunk is named by a direction.
- PRECHECK: `PRECHECK CLEAN` (runs/v2_precheck.log).
- STACKING: `STACKING PASS` (OUT/STACKING_CHECK.md).
- Docker local scoring (fixed tests, /109): oracle 109, unedited 1, nop 0.
- Harbor gates (exe_copy.py copies, /tmp/ccq_v2_gate_20261028T125923-fedc): oracle 1.0, 1.0, 1.0; owner-only 1.0; nop 0.0. One earlier oracle attempt is void: I killed its wrapper, so it was cancelled after 12 s (Engine cp failed, Mean 0.000). It had been launched while 3 other task containers were up; every later run waited until fewer than 2 were up.

## Trap survival
| lever | before loss (/109) | after loss (/109) | ratio | separating cases kept | verdict |
|---|---|---|---|---|---|
| P-1 wide books (dw_global) | 24 | 24 | 100% | y (wide_1-3 byte-identical) | PASS |
| LV-CC-1 exact network (kmb) | 81 | 81 | 100% | y | PASS |
| LV-CC-3 activation once (perlink) | 94 | 90 | 95.7% | y | PASS |
| LV-CC-3 report lines (report_only) | 46 | 46 | 100% | y | PASS |

The 4 points perlink regains are relocated_book_documents (3) and rerun_identical (1). The new guard no longer reads the quote, so these two checks stop charging the per-link activation slip a second time; fresh_networks_feasible still charges it. The six wide checks from the loss table and every hidden input are kept.

## Lessons for the master
- A guard that replaces a reused assertion needs its own vacuity run: "differs from the shipped artifacts" would have paid the unedited package 4 points | no change: playbook G5 already covers it
- Never kill a harbor wrapper by pid: the run gets cancelled and reports 0.000 with an Engine cp error, which is a harness artefact, not a score | no change: round notes G already require checking docker ps before a launch
