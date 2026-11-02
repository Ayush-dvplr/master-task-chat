# RULE_TRACE cold-chain-backbone-quote (cap-60 build b223662, 30 Oct)

| rule id | sentence file:line | generator branch | tests |
|---|---|---|---|
| R-NET minimum-cost network + tie vector | environment/ci/api_contract.md:84-89 | `_make_fresh`, `_make_wide` (`_wide_book_parts`, planted tie), `_make_ties` | shipped_core_document, fresh_1..3_core, tie_book_core, wide_1..3_core, wide_4..10_core, fresh_networks_feasible, wide_networks_feasible |
| R-LIM limit per book | environment/ci/api_contract.md:91-92 (memory: task.toml memory_mb 4096) | `_make_wide` (31-41 cold rooms, pieces of 15-18 sites) | wide_1..3_core, wide_books_report, wide_books_summary, wide_networks_feasible, wide_4..10_core/report/summary |
| R-ACT activation once per activated site | environment/ci/api_contract.md:78-82 | every builder | shipped_report_document, fresh_1..3_report, fresh_rollups_follow_network, wide_books_report, wide_4..10_report |
| R-OTHER books in same format | environment/ci/api_contract.md:24-25, instruction.md:11 | all hidden builders | every fresh_*, rescaled, relocated, wide_* check |
Full per-rule coverage (42 rows): RULE_COVERAGE.md.
