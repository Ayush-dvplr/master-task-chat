# G7 tests diff (WORK/test_output.src.py before -> after; full unified diff in G7_src_diff.txt)
Every hunk, by src line before -> after:
- 4,6c4,8 header docstring: wide optima from _exact, stored in _WIDE_TRUTH (F2)
- 19a22 `import hashlib` (F2 digest)
- 142a146,572 `_WIDE_TRUTH` table (320 entries) + module `_exact` table method (F2)
- 437-516 -> 866-877 nested `bounded` cut search (oracle restatement) replaced by `optimum` (digest lookup, else `_exact`) (F2)
- 560c921 solver selection `bounded` -> `optimum` (F2)
- 894-923 -> 1255-1282 `_write_receipt`: no record counts, 3 columns, header comment (F5)
- 1071,1098c1430,1437 case_spec: unused `allowance_order` and `allowance_consumption` removed, mut_allowance pair kept with start-order comment (F15)
- 1269c1608,1609 / 1274c1614,1615 H1 design comment + guard ("DH2", "selection") (F15)
- 1550c1891,1892 wide comment: optima read from _WIDE_TRUTH (F2)
- 1657a..1667a -> 2000-2016 FAMILIES bid_cost_rows, compliance_rows (F4); SHIPPED_ELSEWHERE + `_project(..., shipped)` (F3)
- 1904,1905c2253,2254 family_passes passes shipped flag (F3); 2186c2535 quality_counts_match description (F3)
- 2263a, 2265a, 2397a, 2399a new criteria: bid_cost_rows_match(+_hard), compliance_rows_match(+_hard), wide_k_bid_cost_rows_match, wide_k_compliance_rows_match (F4)
- 2568a, 2584a registrations w3/w5 and w1 x8 (F4)
No other line changed. tests/test_output.py = src + embedded _SHIPPED_DATA (export_manifest.tsv bytes changed by F5).
Cross-check (p12q2/check_repair.py, host): new expected() == pre-edit expected() (bounded truth) on shipped, H1 (new seed), H2, wide0..3; wide roots make 0 _exact calls (all 320 optima from the table).
