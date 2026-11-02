# Evidence map

Every rule of engagement and every deliverable property the tests grade, with the shipped line that states it or the shipped fact that settles it. Paths are under `environment/ci/` (mounted at `/app/ci`). Test ids are the criterion names in `tests/test_output.py`.

| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| Corridor position is one consecutive whole number: depot 0, then corridor order, then slot as a number; equal corridor+slot impossible by construction | every shipped_* and fresh_* document check, rescaled_book_documents, relocated_book_documents | api_contract.md:49 (layout.tsv:2411 and layout.tsv:2380 put P8115 ringroad slots 8 and 14 in one corridor) | slot sorted as text (14 before 8); raw slot used as the position; corridors ranked alphabetically (access_rules.toml:2 lists harbour before airport) |
| Closed links are removed before any other rule | shipped_parser_document, shipped_core_document, fresh_* checks | api_contract.md:57 (access_rules.toml opens the closed list) | closed links kept and quoted |
| Link cost is base + per_km x km of its band | shipped_core_document, fresh_*_core | api_contract.md:58 (access_rules.toml:9 gives B2 base 2) | base dropped; per_km alone |
| Activation override keys match with exact spelling and case | shipped_core_document, fresh_*_core | api_contract.md:41 (activation.ini:20 key P1236/S167) | configparser default lowercasing drops every override |
| Rejection codes checked in the stated order, first applies | shipped_parser_document, rejection_book_parser | api_contract.md:64 | dup check skipped; unknown end after network check |
| E_NO_NETWORK when a cold room cannot reach the depot | shipped_parser_document, rejection_book_parser | api_contract.md:70 | unreachable cold rooms dropped and the project quoted |
| Missing book file: stderr E_MISSING_FILE name, first in list order, no document, non-zero exit | missing_file_reported | api_contract.md:19 | traceback; exit 0; last missing file named |
| Quote is the smallest over all networks (LV-CC-1) | shipped_core_document, fresh_1_core, fresh_2_core, fresh_3_core, rescaled_book_documents, relocated_book_documents | api_contract.md:84 | terminal shortest-path tree; greedy attach; tree with local search |
| Limit: 4 s per project plus 10 s start-up, no size, count or span bound stated (P-1, wave 1) | fresh_*, wide_1_core, wide_2_core, wide_3_core, wide_books_report, wide_books_summary, wide_networks_feasible, rescaled_book_documents, relocated_book_documents | api_contract.md:91 | search over every subset of cold rooms of a whole project, or a sweep over corridor order holding every site still waiting for a link, run out of time on books with 30-42 cold rooms and links across far corridor positions |
| Each activated site charged once, however many links touch it (LV-CC-3) | shipped_core_document, shipped_report_document, fresh_*_core, fresh_*_report, fresh_*_summary | api_contract.md:81 | activation charged once per booked link; sites with no booked link left uncharged; shared node charged twice in a subset merge |
| Tie: smaller link vector over ascending open link ids wins | tie_book_core | api_contract.md:85 | first network found; larger vector; sorted by site ids |
| Link booked to its end with the larger corridor position; depot line is its charge | shipped_report_document, fresh_*_report | api_contract.md:96 | booked to the smaller end; depot line includes depot links |
| Corridor total = sum of its activated sites' line totals; share_bp rounded down | shipped_report_document, fresh_*_report, fresh_rollups_follow_network | api_contract.md:100 (failing_tests.log:34 shows 6667 != 6666) | rounded share; maximum line as corridor total |
| Every reported total computed from the minimum-cost network (coupling) | fresh_*_report, fresh_*_summary, fresh_rollups_follow_network | api_contract.md:104 | rollups from a different network than the one quoted |
| Objects hold one entry per accepted project, activated site, corridor with an activated site; lists ascending | every document check | api_contract.md:108 | every corridor listed; every site listed; unsorted lists |
| Parser counts: sites counts the depot, links counts all rows | shipped_parser_document, rescaled_book_documents, rejection_book_parser | api_contract.md:118 | depot left out; closed rows left out |
| Summary fields | shipped_summary_document, fresh_*_summary | api_contract.md:124 | depot_total missing; rejected count wrong |
| previously_failing = every FAIL or ERROR result line, once | test_fixes_document | api_contract.md:134 (failing_tests.log:5 ends in ERROR) | FAIL lines only; names repeated from the FAIL: blocks |
| regression_quotes holds a quote or the rejection code | test_fixes_document | api_contract.md:137 | null for rejected cases; shipped package quotes |
| Archive layout per build_config | archive_follows_build_config | api_contract.md:154 (build_config.json:3 path, build_config.json:4 stored) | repo folder prefix; deflated; current timestamps; pycache members |
| VERSION and pyproject version equal the manifest; stdlib only | archive_follows_build_config | api_contract.md:4 (package_manifest.json:3 version 2.18.5) | VERSION missing; requests kept as a dependency |
| Command leaves the book directory unchanged, any cwd, any user | rerun_identical, relocated_book_documents | api_contract.md:15 | cache files written into the book; paths resolved against cwd |
| Each output document graded whole on fresh books; only exact match counts | every whole-document check | api_contract.md:108 (instruction.md states the exactness sentence) | partial credit expected per field |
| Tie verdict: two networks with the smallest quote settled by the smaller link vector | tie_book_core, wide_1_core, wide_2_core, wide_3_core (each wide book plants one tie project) | api_contract.md:85 | first network found; larger vector |
| No-network verdict | rejection_book_parser, shipped_parser_document | api_contract.md:70 | quoting a project whose cold room is cut off |
