# COST_TABLE - counter-page-crash-recovery

Positive test weight 95. Overall = 0.5 * tests + 0.5 * judge, judge assumed at 90%.
All-but-one overall = 0.5 * (95 - lost) / 95 + 0.45. Variants run by `cost_table.py` on the books the tests build
(shipped, dense, restart, max, rejection, relocated, scaled); reference equal to the embedded expected documents on every book.
Real mutants of the oracle archive agree (RULE_COVERAGE.md): eager 53, first-change page 62, one-hop 75 (patch also hits shipped), per-txn 62, END late 62, redo from master 62.

| lever | variant | what it does | lost | alone % of test points | all-but-one overall | core-wrong images (shipped/dense/restart/max/rejection/relocated/scaled) |
|---|---|---|---|---|---|---|
| LV-WR-1 | B1_commit_filter | shipped method: commit-filter replay, naive per-loser undo | 75 | 78.9 | 55.5 | 34/12/12/12/2/8/12 |
| LV-WR-1 | B2_no_clr_redo | redo skips CLRs | 62 | 65.3 | 62.4 | 34/12/12/12/2/8/12 |
| LV-WR-1 | B3_redo_ge | redo when lsn >= pageLSN | 62 | 65.3 | 62.4 | 32/10/10/12/2/7/10 |
| LV-WR-1 | B8_scan_from_end | analysis scans from checkpoint_end | 75 | 78.9 | 55.5 | 15/7/7/6/1/2/7 |
| LV-WR-1 | B15_per_record_redo | redo decision from first change page only | 62 | 65.3 | 62.4 | 34/12/12/12/2/8/12 |
| LV-WR-1 | B16_eager_pagelsn | pageLSN set after each change (textbook eager redo) | 53 | 55.8 | 67.1 | 0/12/12/12/2/8/12 |
| LV-WR-2 | B5_prev_walk | undo walks prev, double undo of compensated updates | 75 | 78.9 | 55.5 | 28/12/12/12/2/8/12 |
| LV-WR-2 | B12_one_hop | CLR reached through undo_next treated as undo point | 63 | 66.3 | 61.8 | 0/12/12/12/2/8/12 |
| LV-WR-3 | B4_per_txn_order | undo one loser at a time | 62 | 65.3 | 62.4 | 33/12/12/12/2/7/12 |
| LV-WR-3 | B6_redo_from_ckpt | redo from master_lsn | 62 | 65.3 | 62.4 | 32/11/10/11/2/7/11 |
| LV-WR-3 | B7_textbook_end | END appended when chain reaches begin, winner ENDs in table order | 62 | 65.3 | 62.4 | 22/12/10/12/2/8/12 |
| LV-WR-3 | B9_end_no_lsn | appended ENDs take no LSN | 75 | 78.9 | 55.5 | 34/12/12/12/2/8/12 |
| none (field slip) | B10_latest_ckpt | latest checkpoint instead of master record | 13 | 13.7 | 88.2 | 0/0/0/0/0/0/0 |
| none (field slip) | B13_undo_next_resolved | undo_next written as resolved undo point | 13 | 13.7 | 88.2 | 0/0/0/0/0/0/0 |
| combined | TB_textbook | textbook ARIES: B7 + B16 | 72 | 75.8 | 57.1 | 22/12/12/12/2/8/12 |

Every lever variant alone costs at least 55.8% of the test points (rule: >= 25%); every all-but-one row is below 70
(highest 67.1, eager pageLSN redo). Field slips B10 and B13 are not levers and stay at 88.2.

One fact wrong: one wrong slot in one image of the max book fails max_core (5) and max_summary (3): tests 87/95 =
91.6%, overall about 0.91 (judge 90%). One wrong slot in one image of the dense book fails dense_core, dense_summary
and scaled_summary (15): tests 84.2%, overall about 0.87. CL-4: whole-document exactness is stated in instruction.md
("Only an exact match counts. Each recovery document counts as a whole ...").
