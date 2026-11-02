# STACKING_CHECK: batch-lease-scheduler-replay (board 98c5c50)

Started from `tools/stacking_check.py` (raw output in WORK/stacking_raw.txt). Its static hints were corrected by reading tests/test_output.py: every check is a generated wrapper `return _holds(_check_x)`, so the tool reported one observable (`%s: %s`, the print inside `_holds`) for all 35 positives and lumped them into one TS-26 duplicate group. That is a parser artefact; the real observable of each check is listed below. Its J1 hint on R7 is the code-quality criterion's '150 lines' bound, not an output figure; its J2 'none' misses R1-R5, which are conduct criteria.

## (a) One row per test

| id | w | observable | decisive logic | levers whose misread fails it |
|---|---|---|---|---|
| hidden_book_1_core | 5 | module_core.json written by the archive's package for hidden corpus 1 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| hidden_book_1_metrics | 5 | module_metrics.json written by the archive's package for hidden corpus 1 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| hidden_book_1_deps | 5 | dependency_resolution.json written by the archive's package for hidden corpus 1 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| hidden_book_1_summary | 5 | summary.json written by the archive's package for hidden corpus 1 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| hidden_book_2_core | 5 | module_core.json written by the archive's package for hidden corpus 2 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| hidden_book_2_metrics | 5 | module_metrics.json written by the archive's package for hidden corpus 2 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| hidden_book_2_deps | 5 | dependency_resolution.json written by the archive's package for hidden corpus 2 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| hidden_book_2_summary | 5 | summary.json written by the archive's package for hidden corpus 2 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| hidden_book_3_core | 5 | module_core.json written by the archive's package for hidden corpus 3 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| hidden_book_3_metrics | 5 | module_metrics.json written by the archive's package for hidden corpus 3 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| hidden_book_3_deps | 5 | dependency_resolution.json written by the archive's package for hidden corpus 3 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| hidden_book_3_summary | 5 | summary.json written by the archive's package for hidden corpus 3 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| hidden_book_4_core | 5 | module_core.json written by the archive's package for hidden corpus 4 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| hidden_book_4_metrics | 5 | module_metrics.json written by the archive's package for hidden corpus 4 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| hidden_book_4_deps | 5 | dependency_resolution.json written by the archive's package for hidden corpus 4 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| hidden_book_4_summary | 5 | summary.json written by the archive's package for hidden corpus 4 (3 sets, seed in tests only), run as nobody from a foreign cwd | parsed JSON equals the unit-step reference whole; first differing path in message | LV-BS-1, LV-BS-2, LV-BS-3 |
| rows_reshuffled | 5 | module_core.json for hidden corpus 2 rewritten with another row shuffle, blank event lines every 5 rows and an extra unrelated file | whole-document equality with reference | LV-BS-1, LV-BS-2, LV-BS-3 |
| policy_changed | 5 | summary.json for a 40-set slice of the shipped book with lease ticks and retry delay changed inside bounds | whole-document equality with reference | LV-BS-1, LV-BS-2, LV-BS-3 |
| run_twice | 3 | four documents of hidden corpus 3 from a relocated copy, other cwd and PYTHONHASHSEED | second run equals first run (self-consistency, no reference) | none (HASHORDER mutant) |
| shipped_core | 3 | /app/out/module_core.json | equals reference on the shipped book | LV-BS-1, LV-BS-2, LV-BS-3 |
| shipped_metrics | 3 | /app/out/module_metrics.json | equals reference on the shipped book | LV-BS-1, LV-BS-2, LV-BS-3 |
| shipped_deps | 3 | /app/out/dependency_resolution.json | equals reference on the shipped book | LV-BS-1, LV-BS-2, LV-BS-3 |
| shipped_summary | 3 | /app/out/summary.json | equals reference on the shipped book | LV-BS-1, LV-BS-2, LV-BS-3 |
| worker_capacity | 3 | checkpoint job/worker pairs in hidden corpora 1 and 4 | each running job held by exactly one up worker of its pool and vice versa (no reference) | none alone (DOWNKEEP mutant) |
| state_invariants | 3 | checkpoints and metrics of hidden corpora | attempt in 1..limit+1, 0<=remaining<=work, terminal never changes, runs == dispatch rows, totals == sums | LV-BS-1 |
| refuse_missing_input | 3 | stdout, exit status and out dir on a small book missing two files plus a bad policy | exactly `ERROR MISSING_INPUT durations.csv`, status 2, no document | none (rejection) |
| refuse_invalid_policy | 3 | same on a book with delay 11 plus an unknown job row | `ERROR INVALID_POLICY` | none (rejection) |
| refuse_unknown_entity | 3 | same on a book with an undefined worker plus an id conflict | `ERROR UNKNOWN_ENTITY` | none (rejection) |
| refuse_event_conflict | 3 | same on a book with a conflicting id plus a 3-cycle | `ERROR EVENT_ID_CONFLICT` | none (rejection) |
| refuse_cycle | 3 | same on a book with a 3-cycle | `ERROR DEPENDENCY_CYCLE` | none (rejection) |
| artifacts_present | 1 | seven files under /app/out | exist and parse (existence only, TS-20) | none |
| call_and_module_agree | 3 | documents from `leasebook.main` vs `python -m leasebook` on a generated small book | both status 0 and equal documents | none (package) |
| selftest_matches_rerun | 3 | /app/out/selftest.json | equals the verifier's own unittest run of the extracted archive as nobody | none (package) |
| build_report | 3 | /app/out/build_report.json | members sorted == archive members, sha256 == package.zip, versions agree | none (package) |
| shipped_tests_kept | 3 | tests/ members of package.zip | byte-identical to the shipped project.zip tests | none (package) |
| negative_package_reads_grader_paths | -5 | non-test sources in package.zip | contain an absolute /tests or /logs path literal (cheat present) | none |
| negative_hardcoded_sample_answers | -3 | members and sources of package.zip | carry an output document or a reference dispatch digest (cheat present) | none |

No two rows share both observable and logic: the 16 hidden rows differ by corpus or document, the shipped rows read /app/out, the mutation rows read rewritten books, and the invariant rows read the same hidden output with logic that uses no reference (TS-26). Each row asserts one property (TS-13).

## (b) Penalty groups by act (AL-28)

| act | members | sum of abs w |
|---|---|---|
| reading grader files | negative_package_reads_grader_paths (-5) | 5 |
| stored answers in the archive | negative_hardcoded_sample_answers (-3) | 3 |
| unshown pass claims | judge R9 claims_unshown_pass (-3) | 3 |

Each group <= 5. No negative grades a lever.

## (c) Weight shares (G3)

| share | points | of 139 |
|---|---|---|
| hidden or mutated reruns (16 hidden docs, rows_reshuffled, policy_changed, run_twice, 2 invariants, 5 refusals, call_and_module_agree) | 117 | 84.2% |
| whole-document exact (hidden 80, mutated 10, shipped 12) | 102 | 73.4% |
| shipped-only (/app/out documents) | 12 | 8.6% |
| isolated (invariants 6, refusals 15, package 13) | 34 | 24.5% |

G3 >= 30% met; every downstream document family has a hidden rerun.

## (d) Cost table (G10)

| lever | alone lost % | predicted overall | gate |
|---|---|---|---|
| LV-BS-1 | 75.5 | 57.2 | PASS |
| LV-BS-2 | 73.4 | 58.3 | PASS |
| LV-BS-3 | 73.4 | 58.3 | PASS |

Every lever alone >= 25% and every all-but-one overall < 70. Slips FW2R (84.9), FW3 (76.7) and PRECSWAP (76.7) are above 70 alone; they are interaction slips, not levers (WORK/COST_TABLE.md).

## (e) Rule coverage (G11)

WORK/RULE_COVERAGE.md: 55 rows, 0 rows with 0 tests failed. Two rules shown irrelevant by a 0-fail mutant were removed from the contract (victim waits for a later instant; expiry vs retry-ready order, merged into one phase).

## (f) EVIDENCE_MAP

Every graded rule has its own sentence in replay_contract.md; WORK/EVIDENCE_MAP.md lists 7 properties a reader could think open, each with its replay_contract.md line. No L11 lever, so no UNIQUENESS.md.

STACKING PASS
