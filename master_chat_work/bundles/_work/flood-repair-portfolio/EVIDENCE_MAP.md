# EVIDENCE_MAP ed7b0c2 flood-repair-portfolio

Every graded rule is stated in `environment/data/contract.md` (one rule file, W10) and the shipped book holds at least one determinate fact where the stated reading and each listed wrong reading give different documents. No row below holds an answer: the facts are input rows; the documents are only computed by the program.

| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| Greatest total benefit, conflict-free (contract.md:62) | h1/h2/h3_book_optimal, *_summary, *_policy_audit, *_regions, *_segments, shipped_* | proposals.csv:958 (first of the 150 rows of round R79260) and proposals.csv:1312 (first of the 160 rows of round R57468) | greedy, 1-2 swap search, time-limited branch and bound incumbent, LP rounding: each gives a lower total on those rounds (DESIGN.md section 9, COST_TABLE.md) |
| Tie-break: smaller sorted id list wins (contract.md:62) | shipped_summary_matches, h*_book_summary | proposals.csv:1214 and :1219 (round R91041, same site S73825, 19 households, override A: equal benefit, joined to each other only); 24 such rounds (UNIQUENESS.md) | no tie-break (first found), largest list wins |
| Exclusive crew joins its proposals; shared crew joins none (contract.md:27, 56) | h*_book_feasible, all doc checks | crews.tsv:3 `C7815 shared`; proposals.csv:6 and :12 share shared crew C5836 in round R42865 | shared crews also conflict; crews ignored |
| Permit held or applied joins its holders; withdrawn counts for nothing (contract.md:28, 57) | h*_book_feasible, all doc checks | permits.csv:3 `R62233,M13282,P635074,withdrawn` (641 withdrawn rows) | withdrawn rows join; permits ignored |
| Exclusion joins either order; a site name stands for every proposal of the round at that site (contract.md:29, 58) | h*_book_feasible, all doc checks | exclusions.json:3 `{"round": "R42865", "first": "S58075", ...}`, S58075 holds proposals.csv:7 and :11 | site names skipped; one order only |
| risk_override, when not empty, replaces the site's risk class (contract.md:23, 50) | all doc checks | proposals.csv:9 `R42865,P388480,S49309,C7836,9,C`, site S49309 class D in sites.jsonl | site class always used |
| benefit = households x (segment rate + risk uplift) + premium (contract.md:48) | all doc checks | benefits.ini:1-10 (uplift A = -7), sites.jsonl:2040 premium 203 | premium dropped; uplift added once instead of per household; uplift dropped |
| Fault order: files in manifest order, rows in file order, first applicable check (contract.md:35-40) | shipped/h*_book_data_quality | manifest.json:3-12 (`files` order); round R54721 has segment_codes.tsv:1808 `mixed` and permits.csv:263 `revoked`, the earlier declared file decides | fixed file order; INVALID before DUPLICATE; first occurrence reported as duplicate; row numbered within round |
| NONPOSITIVE_BENEFIT: below 1, first such row, after file checks (contract.md:42) | shipped_data_quality_matches, h3_book_data_quality | proposals.csv:2092 (round R83234, benefit exactly 0) then :2093 (benefit -6) | below 0 only; last such row; valued before file checks |
| Row numbers count data rows of the whole file from 1 (contract.md:21) | shipped/h*_book_data_quality | proposals.csv:2092 is row 2091 | rows counted from 0; rows counted within the round |
| Audit line numbers count every line, blank ones included (contract.md:72) | shipped/h*_book_policy_audit | audit_queries.txt:98 blank line | blank lines skipped in numbering |
| Missing declared file: no documents, `ERROR MISSING_FILE <first missing>`, exit 1 (contract.md:19) | missing_input_is_named | manifest.json:3-12 declares nine files | crash with traceback; silent skip |
| One self-contained file, python3 standard library only (contract.md:5) | every run (`python3 -I -S`) | contract.md:5 `one self-contained file that uses python3 and its standard library only` | importing an installed solver |
| Every figure of a round from the one chosen portfolio (contract.md:64) | all doc checks | contract.md:64 and proposals.csv:958 (round R79260, whose one portfolio feeds summary, policy_audit, regions and segments) | a different portfolio per document |

## Harden r2 cb8dada (1 Nov) rows
| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| Every book inside the limits is written within 20 s of wall time (contract.md:9-15) | h1/h2/h3_book_feasible, _optimal, _summary, _policy_audit, _data_quality, _regions, _segments; reruns_identical | contract.md:11 (up to 200 rounds, up to 160 rows a round), contract.md:15 (20 s); the shipped book already holds the large round shape: proposals.csv:958 (150 rows, round R79260) and proposals.csv:1312 (160 rows, round R57468) | a solver timed only on the shipped book's two large rounds (a1 program: 2.2 to 3.3 s shipped, over 60 s on each hidden book with 60 large rounds, kill2.log); a one-start sweep (all-but-one program, 42 to 55 s) |
| TS-19 bounds: hidden sizes stay inside contract.md:11-13 | every hidden check | contract.md:11 and contract.md:12 state the limits; the shipped book already sits at them: 192 rounds in proposals.csv, 160 rows in round R57468 (proposals.csv:1312); generator `_check_bounds` (test_output.py:601) asserts every hidden book inside them, gen300 over 300 seeds 0 errors | a reading that hidden books may exceed a stated limit: none of them does |
| TS-19 reruns_identical pays value determinism, not serialization or correctness | reruns_identical | contract.md:68 defines JSON document content and ordered lists, not whitespace or object-key order; test_output.py:1628 compares two H1 runs through strict typed parsed JSON equality | byte comparison penalizes two valid serializations; comparing against expected documents would repeat h1_book_summary |

## Lessons for the master
- A fault rule with a boundary (below 1) needs a planted row exactly on the boundary; the first mutant run showed `< 0` surviving | template_change: anubis-task-generator rule-coverage step: plant boundary value for every threshold rule.

## Harden r4 ea94780 (1 Nov) rows
| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| A shared crew works on at most four proposals of a portfolio (contract.md:62) | h1/h2/h3_book_feasible, _optimal, _summary, _policy_audit, _regions, _segments; scaled_shuffled_summary_matches, rotated_summary_matches, relocated_copy_matches | contract.md:62 states the limit; crews.tsv:3 `C7815 shared`; round R62233 holds four proposals of shared crew C2534 (proposals.csv:48, :51, :52, :56) and its chosen portfolio holds all four (the limit is reached, never passed, on the shipped book). The separating case (five or more members a shared crew could hold) is hidden only (route-1 R2, W5) | limit ignored; limit applied as a pre-filter (keep the four highest benefits); limit applied after the search (drop the lowest-benefit pick and search again) |

## Harden r6 ea04435
| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| Exactness, cap and time bound apply together | h1/h2/h3_book_optimal, _summary, _policy_audit, _regions, _segments | contract.md:62 requires the greatest portfolio under the shared-crew cap; contract.md:11 and :15 specify 160 rows and 20 seconds; proposals.csv:958 and :1312 supply large lattice rounds, crews.tsv:3 supplies shared mode | a per-round or per-book deadline may silently replace the exact portfolio with greedy; spending the full lattice solve once per crew drop combination scales acceptably because each separate solve was fast on shipped data |

## QC v4 scoped fix 420bf9a
| rule | owner | shipped fact file:line | evidence boundary |
|---|---|---|---|
| Read the supplied DATA_DIR rather than replaying another book's answers | negative_hardcoded_sample_answers (-3) | contract.md:5 specifies DATA_DIR; contract.md:68 specifies summary content | cached H1 summary must actually substitute a shipped selected list or total for a different H1 answer; source ids, comments, crashes and timeouts are not evidence |

Verifier access moved to judged R16 because execution artifacts cannot establish the agent's access act; no new agent-visible rule or figure check was introduced. TS-26 and AL-27 remain unchanged under Ayush's explicit scope ruling (OUT/KEPT.md).
