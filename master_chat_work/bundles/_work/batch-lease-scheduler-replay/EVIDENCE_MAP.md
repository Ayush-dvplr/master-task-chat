# EVIDENCE_MAP (LEVER_RULES 0b)

Every graded rule of this task has its own sentence in `replay_contract.md` (RULE_COVERAGE lists them). No rule is settled by silence. The rows below cover the properties a reader could think are open, and the shipped fact that settles each.

| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| the sets of a book are the sets listed in checkpoints.txt | hidden_book_*_*, shipped_*, refuse_unknown_entity | replay_contract.md:26 | sets taken from jobs.tsv or events.jsonl; a set with no checkpoint replayed |
| order of jobs inside one phase has no effect | hidden_book_*_core, rows_reshuffled | replay_contract.md:53 | file row order or event row order used as a tie-break inside a phase |
| row order in every file carries no meaning | rows_reshuffled | replay_contract.md:9 | dispatch tie or audit order taken from file row order |
| the version reported is the archive's own `[project] version`, and `__version__` must equal it | build_report, selftest_matches_rerun | replay_contract.md:110 | version copied from the shipped `__version__` while pyproject says otherwise |
| tests counted are those of `unittest discover -s tests` in the extracted archive | selftest_matches_rerun | replay_contract.md:112 | counting only shipped tests, or counting from a run in the source tree |
| a job named in jobs.tsv appears in every checkpoint even before its submit | hidden_book_*_core, shipped_core | replay_contract.md:83 | only submitted jobs listed in checkpoints |
| the replay ends at the last checkpoint of the set | hidden_book_*_metrics, hidden_book_*_summary | replay_contract.md:87 | executed units counted to the last event or to the end of every run |
