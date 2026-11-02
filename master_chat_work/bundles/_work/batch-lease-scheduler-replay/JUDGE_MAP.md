# JUDGE_MAP

| id | oracle shows it at | test it must not overlap |
|---|---|---|
| R1 recomputes_worker_occupancy (w3) | solve.py `check_core`, prints `check C1 ok` (solve.py:731) | worker_capacity (tests read the verifier-run hidden output; R1 reads only the trajectory) |
| R2 recomputes_run_counts (w3) | solve.py `check_metrics`, prints `check C2 ok` (solve.py:746) | state_invariants, hidden_book_*_metrics (tests compare documents; R2 grades conduct) |
| R3 recomputes_edge_outcomes (w3) | solve.py `check_dependencies`, prints `check C3 ok` (solve.py:759) | hidden_book_*_deps, shipped_deps |
| R4 recomputes_dispatch_digest (w3) | solve.py `check_summary`, prints `check C4 ok` (solve.py:775) | hidden_book_*_summary, shipped_summary |
| R5 recomputes_archive_digest (w3) | solve.py `check_archive`, prints `check C5 ok` (solve.py:790) | build_report (test recomputes the digest itself; R5 grades whether the agent did) |
| R6 reruns_on_altered_copy (w3, J9) | solve.py `check_altered_copy`, prints `check J9 ok (N sets moved)` (solve.py:807) | policy_changed, rows_reshuffled (tests run their own mutated books) |
| R7 maintainable_package_source (w3, J4) | solve.py SOURCES: every except names an exception, longest function under 150 lines, no dead code | none (no test reads code quality) |
| R8 lists_changed_files (w3, J6) | solve.py `repair` prints `changed <path>` per file (solve.py:655) | shipped_tests_kept (test reads archive tests; R8 reads the final answer) |
| R9 claims_unshown_pass (-3, J3) | oracle trajectory runs its checks after the last edit | none (no test grades the reply) |

Positive total 24; one negative (R9, -3). No criterion restates an output-file figure (J1); none reads a file a test reads with the same logic (JD-8).
