# RULE_COVERAGE - counter-page-crash-recovery

Real mutants of the oracle archive (`mutants.py`, logs `mutants_part1.log`, `mutants2.log`, rerun of
`undo_next_unchecked` after the rejection book gained an undo_next defect). Each mutant patches one member of
the oracle's package.zip, regenerates the four shipped documents with it, and is graded by `tests/test_output.py`.
File = `environment/data/recovery_contract.md` unless named. Oracle: 95/95.

| rule | file:line | mutant | tests failed |
|---|---|---|---|
| redo pages decided before any change is applied | recovery_contract.md:114-119 | redo_eager_pagelsn | lost 53: dense/restart core, metrics, summary; max core, summary; rejection, relocated core; scaled summary |
| a page is redone per page, not per record | recovery_contract.md:114-118 | redo_first_change_page | lost 62: shipped/dense/restart core, metrics, summary; max, rejection, relocated, scaled |
| record lsn greater than the page's pageLSN | recovery_contract.md:117-118 | redo_ge_pagelsn | lost 65: as above plus selftest_truthful |
| redo starts at the smallest recLSN after analysis | recovery_contract.md:111-112 | redo_start_master | lost 62 |
| a CLR moves to the record named by its undo_next | recovery_contract.md:130-132 | undo_one_hop | lost 75: every document check |
| any other record moves to its prev | recovery_contract.md:130-132 | undo_prev_walk | lost 75 |
| the CLR's undo_next is the undone update's prev | recovery_contract.md:138 | clr_undo_next_field | lost 16: shipped/dense/restart appended, selftest_truthful |
| each undo step takes the loser with the largest undo point LSN | recovery_contract.md:134 | undo_per_txn | lost 62: core, appended, summary everywhere |
| end for every loser with no undo point before the undo steps | recovery_contract.md:126-128 | idle_loser_end_late | lost 62 |
| end for every winner in ascending transaction id | recovery_contract.md:126 | winner_end_table_order | lost 10: dense, restart appended |
| appending a CLR sets the pageLSN of every page it names | recovery_contract.md:139-140 | clr_keeps_pagelsn | lost 49 |
| first appended record takes the largest journal lsn plus 1 | recovery_contract.md:123-124 | first_lsn_offset | lost 75 |
| an end removes its transaction from the table | recovery_contract.md:98-99 | analysis_keeps_ended | lost 75 |
| analysis reads every record whose lsn is at least master_lsn | recovery_contract.md:97-98 | analysis_from_ckpt_end | lost 75 |
| a page not yet in the dirty page table is added with recLSN | recovery_contract.md:102-104 | dirty_overwrite | lost 62 |
| checks run in the stated order | recovery_contract.md:71-83 | validation_order | lost 5: rejection_core |
| a frame whose CRC-32 does not match rejects the image | recovery_contract.md:75-77 | crc_ignored | lost 5: rejection_core |
| a non-null undo_next names an earlier record of the same transaction | recovery_contract.md:81-83 | undo_next_unchecked | lost 5: rejection_core |
| pageLSN is a 64 bit unsigned big endian integer | recovery_contract.md:51-52 | pagelsn_u32 | lost 62 |
| slot values are 64 bit signed integers | recovery_contract.md:53 | slots_unsigned | lost 49 |
| page ids are case sensitive | recovery_contract.md:26 | page_ids_lowercased | lost 75 |
| image_sha256 of pages with sorted keys and no whitespace | recovery_contract.md:174-177 | sha_noncanonical | lost 21: every summary check |
| compensated is the sum of absolute deltas | recovery_contract.md:178-180 | compensated_signed | lost 21: every summary check |
| a missing input: no document, file named, nonzero exit | recovery_contract.md:155-157 | missing_input_exit0 | lost 3: missing_input_rejected |
| files in DIR unchanged, second run writes the same documents | recovery_contract.md:187-188 | writes_into_data | lost 3: rerun_identical |
| a book at the stated limits is recovered within 60 seconds | recovery_contract.md:185 | slow_large_images | lost 3: max_within_limit |
| pyproject version is the required_version | recovery_contract.md:196-199 | pyproject_version | lost 3: package_metadata |
| no member other than archive_members and added .py files | recovery_contract.md:192-195 | extra_member | lost 3: archive_layout |
| tests_run is the unittest count of the archive's tests | recovery_contract.md:209-210 | selftest_count | lost 3: selftest_truthful |
| fixed_modules lists every file the repair changed or created | recovery_contract.md:216-217 | fixed_modules_short | lost 1: build_report_values |
| tests/test_smoke.py keeps every shipped test, none skipped | recovery_contract.md:199-201 | smoke_test_skipped | lost 6: selftest_truthful, NEG negative_shipped_tests_dropped |
| the package holds no figure or image id of any book | recovery_contract.md:185-187 | holds_image_ids | lost 6: build_report_values, NEG negative_hardcoded_sample_answers |

Every row fails at least one check. No rule is uncovered.
