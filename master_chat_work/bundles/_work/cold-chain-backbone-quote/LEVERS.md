# LEVERS 57a2dd7 cold-chain-backbone-quote

Levers: LV-CC-1 exact minimum-cost network (wrong: terminal shortest-path MST / greedy attach);
LV-CC-2 runtime at the stated maximum cold-room count (wrong: Dreyfus-Wagner, exact but over the per-book limit);
LV-CC-3 activation charged once per activated site, carried into every total (secondary stated-rule lever; wrong: per booked link charging, or zero for sites with no booked link).
"tie" = stated tie rule (api_contract.md:88-92), not a lever.

| check | weight | levers | measured loss by variant |
|---|---|---|---|
| archive_follows_build_config | 1 | none | none |
| shipped_core_document | 5 | LV-CC-1, LV-CC-3 | kmb, greedy, perlink |
| shipped_parser_document | 3 | none | none |
| shipped_report_document | 5 | LV-CC-1, LV-CC-3 | kmb, greedy, perlink, report_only |
| shipped_summary_document | 3 | LV-CC-1, LV-CC-3 | kmb, greedy, perlink, report_only |
| test_fixes_document | 3 | none | none |
| repair_report_fields | 1 | none | none |
| fresh_1_core | 5 | LV-CC-1, LV-CC-2, LV-CC-3 | kmb, greedy, dw, perlink |
| fresh_2_core | 5 | LV-CC-1, LV-CC-2, LV-CC-3 | kmb, greedy, dw, perlink |
| fresh_3_core | 5 | LV-CC-1, LV-CC-2, LV-CC-3 | kmb, greedy, dw, perlink |
| fresh_1_report | 5 | LV-CC-1, LV-CC-2, LV-CC-3 | kmb, greedy, dw, perlink, report_only |
| fresh_2_report | 5 | LV-CC-1, LV-CC-2, LV-CC-3 | kmb, greedy, dw, perlink, report_only |
| fresh_3_report | 5 | LV-CC-1, LV-CC-2, LV-CC-3 | kmb, greedy, dw, perlink, report_only |
| fresh_1_summary | 3 | LV-CC-1, LV-CC-2, LV-CC-3 | kmb, greedy, dw, perlink, report_only |
| fresh_2_summary | 3 | LV-CC-1, LV-CC-2, LV-CC-3 | kmb, greedy, dw, perlink, report_only |
| fresh_3_summary | 3 | LV-CC-1, LV-CC-2, LV-CC-3 | kmb, greedy, dw, perlink, report_only |
| fresh_networks_feasible | 3 | LV-CC-2, LV-CC-3 | dw, perlink |
| fresh_rollups_follow_network | 3 | LV-CC-2, LV-CC-3 | dw, perlink, report_only |
| rescaled_book_documents | 5 | LV-CC-1, LV-CC-2, LV-CC-3 | kmb, greedy, dw, perlink, report_only |
| relocated_book_documents | 3 | LV-CC-1, LV-CC-2, LV-CC-3 | kmb, greedy, dw, perlink, report_only |
| missing_file_reported | 3 | none | none |
| rejection_book_parser | 3 | none | none |
| tie_book_core | 3 | LV-CC-1, LV-CC-3, tie | kmb, greedy, perlink |
| rerun_identical | 1 | LV-CC-2 | dw |
| negative_hardcoded_sample_answers | -5 | none (cheat: copies shipped documents) | copier only |
| negative_visible_tests_removed | -3 | none (cheat: drops or skips a shipped visible test) | none of the variants |

## Totals per lever (positive points, total 84)

| lever | points on checks tagged | measured loss of wrong variant | share |
|---|---|---|---|
| LV-CC-1 | 63 | kmb 63, greedy 63 | 75.0% |
| LV-CC-2 | 54 | dw 54 | 64.3% |
| LV-CC-3 (helper charging, feeds quote) | 69 | perlink 69 | 82.1% |
| LV-CC-3 (report-only, quote right) | 43 | report_only 43 | 51.2% |
| none | 14 | | |

## Wave 1 (678c839, 27 Oct): P-1 computational core with no stated decomposition parameter

LV-CC-2 is replaced by P-1. The span rule (E_BAD_SPAN, at most 4 positions) and the size sentence (52 sites, 95 links, 17 cold rooms) are gone from api_contract.md; only the time limit stays (api_contract.md:91). The shipped parser constant `SPAN = 4` is gone. Shipped data varies the largest non-depot link gap per project (3 to 16) and shows projects whose parts meet at single sites.
Hidden books wide_1, wide_2, wide_3 (BOOK_SEED+5..+7, own RNG): 10 projects each, 96-126 sites, 30-42 cold rooms, 248-339 links, 5-6 hub parts joined at single non-depot sites plus one few-cold-room part and one narrow run of 8-10 cold rooms, positions shuffled (largest gap >= n/2), one planted tie project per book. Reference: split at single sites, each part exactly by subsets or by corridor-order sweep (cheaper estimate), score cost*2^m + rank bit; <= 0.5 s per book (limit 50 s).

| check | weight | lever | wrong programs that lose it (measured, COST_TABLE.md) |
|---|---|---|---|
| wide_1_core | 5 | P-1 | whole-project subsets, corridor or self-ordered sweeps, frontier DP, blind programs without the span rule (time); kmb, sph, greedy (wrong network) |
| wide_2_core | 5 | P-1 | same |
| wide_3_core | 5 | P-1 | same |
| wide_books_report | 3 | P-1, LV-CC-3 | same |
| wide_books_summary | 3 | P-1, LV-CC-3 | same |
| wide_networks_feasible | 3 | P-1 | programs that time out (kmb, sph, greedy keep it) |

Positive total 108 (84 + 24). P-1 points 24/108 = 22.2% (a fast heuristic that stays feasible loses 21/108 = 19.4%). Every other check keeps its body byte-unchanged; old hidden books fresh_1..3, rescaled, relocated, missing, rejections, ties are byte-identical (digests in COST_TABLE.md). The rejection book keeps its RNG stream; its former span item is now an ordinary far link, graded by the stated rules.

## Law-1 fix 25c745d (27 Oct 20:3x, LEVER_RULES v3.5 condition 3)
P-1 now counts as a hidden-scale TIMEOUT lever (v3.5): (1) shipped data fast for plausible exact programs (DW over cold rooms, eac8712, probe/d7a0 sweeps: <= 0.2 s per shipped project, runs/time_before.log); (2) limit stated (api_contract.md:91-92, unchanged); (3) cost confined to the six wide checks (24/108 = 22.2%).
Change: the old non-lever fresh books (fresh_1..3; rescaled, relocated, missing and rerun are built from them) drew 16-17 cold rooms per project, a pre-wave-1 DW-kill remnant (COST_TABLE M6), so a 3^k exact program timed out on 54 non-lever points. `_fresh_book_parts` (tests/test_output.py:6088, :6098, :6104) now draws 8-10 cold rooms, the top of the shipped range (shipped 4-10); sites 38-52 and links 65-92 unchanged and inside the shipped range (shipped up to 52 sites, 94 links). No check body, weight, doc sentence or wide generator changed. The fresh books are no longer a lever (they were LV-CC-2 before wave 1, retired there).

## P12 QC v1 fixes (28 Oct): lever effects
relocated_book_documents now compares the relocated run with the package's own fresh_2 run (precondition: fresh_2 quotes each network at its own cost), so it no longer carries LV-CC-1 (kmb/greedy keep it); LV-CC-3 perlink still loses it (precondition). New check archived_package_metadata w1 (no lever); positive total 109. Measured trap survival (Docker, runs/p12_trap*.log, new /109 vs old /108): P-1 dw_global lost 24 vs 24; LV-CC-1 kmb lost 81 vs 84 (96.4%); LV-CC-3 perlink lost 90 vs 93 (96.8%); report_only lost 46 vs 49 (93.9%). Wide checks unchanged (24 points).

## Cap-60 build (30 Oct, board b223662): P-1 held-out far-reaching tier wide_4 to wide_10
Rule (unchanged, no new sentence): api_contract.md:84-89 minimum-cost network with the tie vector, api_contract.md:91-92 "Limit: the command must finish a book within 4 seconds per project in it plus 10 seconds of start-up.", api_contract.md:24-25 "The command is also run on other books in the same format."; memory = task.toml environment memory_mb 4096; instruction.md:11 "Each output document is graded whole on fresh books, and only an exact match counts."
Reflex reading (a4 trajectory step 19, saved OUT/agent_program/): one exact subset DP (Dreyfus-Wagner) over all cold rooms of a project, checked only against brute force on shipped-size projects (steps 26-29); it never builds a book larger than the shipped one. Exact on every book up to about 12 cold rooms; on 31-41 cold rooms it needs 2^k tables and is killed by the 50 s book cap or the 4096 MB memory.
Constructed hidden cases: wide_4..wide_10 = `_make_wide(BOOK_SEED + 4 + K)` (seeds +8..+14), same builder as wide_1..3: 10 projects, 98-129 sites, 31-41 cold rooms, 252-339 links, hub pieces of 15-18 sites meeting at single sites, one few-cold-room piece, one narrow run, one planted tie (the builder asserts all branches per project). Each book is its own command run (memoised per book), checked by three whole-document checks: wide_K_core w5, wide_K_report w5, wide_K_summary w3 (13 per book, 91 new, 115 lever points of 200 with wide_1..3).
Wrong readings and what they fail: whole-project subset DP (a4, dw_global) times out or is memory-killed on every wide book (TIMEOUT / CRASH, v3.5 hidden-scale loss, cap-60 exception for this bundle); terminal-metric tree (kmb), greedy attach and per-link activation give a wrong document on every wide book (WRONG); last-use sweep in corridor order times out (blocks reach half the book).
Interactions: no other check reads wide_4..10; fresh, rescaled, relocated, rejection, tie and shipped checks are byte-unchanged, so a program fast and exact at shipped scale keeps 85/200; the tier only adds held-out weight (w5 tier now fresh core 15 + fresh report 15 + rescaled 5 + wide_1..3 core 15 + wide_4..10 core 35 + report 35 = 120/200 = 60%).
