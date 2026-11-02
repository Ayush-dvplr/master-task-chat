# JUDGE_MAP wave 1 (678c839) cold-chain-backbone-quote

tests/judge.toml, batched, 13 criteria, positive 32, negative 11 (-3, -5, -3). Probe band R1-R7 = 21/32 = 65.6% of positive judge weight. Oracle evidence = solve.py stdout (solution/solve.py main and self_check); every print is a plain description, no criterion id (DS-17).

| id | instruction / contract sentence it serves | oracle shows it at | test it must not overlap |
|---|---|---|---|
| R1 shipped run first, w3 | instruction.md "parts of it do not run" | `check shipped package run before the first edit ok: exit 0, ...` printed by main before repair() writes any file | none (no test sees the order of acts) |
| R2 recount previously_failing, w3 | api_contract.md previously_failing = every FAIL or ERROR line | `check previously_failing ok: 719 names in test_fixes.json, recounted from the FAIL and ERROR lines of failing_tests.log: 719` | test_fixes_document grades the list; R2 grades the agent's own recount |
| R3 one named link changed, w3 | api_contract.md "The command is also run on other books in the same format." | `check one link changed ok: P1236 link L10551 km 3 -> 10, quote 206 -> 212, other projects unchanged` | rescaled_book_documents is the grader's own mutation; R3 is the agent's act |
| R4 book file removed, w3 | api_contract.md missing file: E_MISSING_FILE name, no document, non-zero exit (stated failure behaviour, JD-15) | `check missing book files ok: activation.ini and layout.tsv removed, exit 2, stderr E_MISSING_FILE layout.tsv, no documents written` | missing_file_reported grades the package; R4 grades the agent's probe |
| R5 built far-reaching book timed, w3 | api_contract.md Limit sentence (4 s per project plus 10 s) | `check built far-reaching book ok: 2 projects; largest project 85 sites and 30 cold rooms against 52 sites and 10 cold rooms in the shipped book; widest open link spans 82 corridor positions against 42 in the shipped book; finished in 0.07 s of the 18 s limit` (solve.py far-book check, P12 v2 905cf6e) | wide_* checks grade documents on grader books; R5 grades the agent's own timing act |
| R6 two runs byte compare, w3 | api_contract.md same documents whatever cwd or user | `check rerun ok: second run into another directory, all four documents byte-identical` | rerun_identical grades the package; R6 grades the act |
| R7 built tie book, w3 | api_contract.md tie rule (smaller link vector) | `check tie book ok: networks {T001} and {T002, T003} both quote 17, vectors 100 and 011, the package picks ['T002', 'T003'] with quote 17` | tie_book_core grades a grader book; R7 grades the agent's built book |
| R8 defect named before first edit, w3 (J10) | instruction.md repair per api_contract.md | four `defect found before editing: <file>: <defect>; api_contract.md says <rule>` lines printed by main before repair() | none |
| R9 J4 core.py maintainable, w5 | instruction.md repaired package | fixed core.py: `_groups`, `_by_subsets`, `_along`, `_solve`, `best_network`, `unique`, `site_lines`; `_solve` returns None for no network and the parser raises Rejected("E_NO_NETWORK") | none (no test reads source style); /app/repo/src/task/core.py in task.toml artifacts (JD-6) |
| R10 J6 rejected list, w3 | instruction.md final reply lists rejected projects with codes | `rejected projects: P2495 E_DUP_SITE, P4774 E_DUP_SITE, P6086 E_DUP_SITE, P6881 E_UNKNOWN_ENDPOINT, P7680 E_NO_NETWORK, P8710 E_UNKNOWN_ENDPOINT` | shipped_parser_document grades the document; R10 grades the reply |
| R11 J3a -3 | claims a pass with no run after last core.py edit | oracle runs every check after repair() writes core.py | none |
| R12 J3b -5 | states a quote or code differing from /app/out | oracle's rejected list is read from the written module_parser.json | none |
| R13 J3c -3 | overstates the coverage of a run that exists | oracle prints counts from the run itself (719, 2 projects, 60 cold rooms) | none |

## Negatives are disjoint (AL-28)

R11 needs no run after the last core.py edit; R13 needs such a run to exist and a larger stated coverage; so one claim fires at most one of them. R12 is about a stated value against /app/out, not about runs; one act (one sentence) fires at most -5. Every file a criterion rules on is a task.toml artifact: /app/out/test_fixes.json, module_core.json, module_parser.json, /app/repo/src/task/core.py (JD-6).

## Predicted probe-trajectory band

Probe run 1 (25 Oct): no shipped run before edits (R1 0), no recount of the log (R2 0), no single-link change (R3 0), edge book had all five files (R4 0), timing book had 17 cold rooms and span <= 4 (R5 0), reran fuzz but no two-directory byte compare (R6 0 to 3), no built tie book (R7 0 to 3), named defects from reading (R8 3), core.py tidy (R9 5), rejected list (R10 3) -> 11/32 = 34% (up to 17/32 = 53% if R6 and R7 are credited loosely). Predicted mid 34-40%.
