# Evidence map counter-page-crash-recovery

Every graded rule is stated by a sentence of `environment/data/recovery_contract.md` (mounted at `/app/data/recovery_contract.md`); no graded rule rests on silence or on an unstated shipped fact. The third column gives the stating line and, where a shipped file settles a value, that file. Test ids are criterion names in `tests/test_output.py`; "book docs" means every `*_core`, `*_metrics`, `*_appended`, `*_summary`, `rejection_core`, `relocated_core` and `scaled_summary` check.

| rule | test ids | shipped fact file:line | wrong readings it contradicts |
|---|---|---|---|
| Log order is ascending lsn; journal line order carries no meaning | book docs, relocated_core | recovery_contract.md:31 (journal.jsonl lines of all images interleaved) | file order taken as log order (shipped loader) |
| Page ids are case sensitive | book docs | recovery_contract.md:26 (page_map.ini mixed-case ids) | configparser default lowercasing |
| Frame layout: u64 pageLSN, signed i64 slots, CRC-32 | book docs, rejection_core | recovery_contract.md:48-55 (disk_pages.bin pageLSNs above 2^32, negative slots) | low 32 bits of pageLSN; unsigned slots; CRC ignored |
| master_lsn names the checkpoint, 0 = none | book docs | recovery_contract.md:57-60, checkpoint.toml | latest checkpoint_end in the log (B10) |
| Validation order and codes | rejection_core, shipped docs | recovery_contract.md:71-83 | only E_DUP_LSN checked; codes in another order |
| Analysis tables and scan | book docs | recovery_contract.md:92-107 | scan from checkpoint_end (B8); ended txns kept; dirty recLSN overwritten |
| Redo start and redo decision (LV-WR-1, LV-WR-3) | book docs | recovery_contract.md:111-119 | commit-filter replay (B1); CLRs skipped (B2); lsn >= pageLSN (B3); decision per record (B15); pageLSN raised between changes (B16); start at master_lsn (B6) |
| Appended LSNs and END placement (LV-WR-3) | book docs | recovery_contract.md:123-128 | ENDs without LSN (B9); END of idle losers at chain end; winners in table order (B7) |
| Undo point walk (LV-WR-2) | book docs | recovery_contract.md:130-132 | prev walk through CLRs (B5); CLR-to-CLR treated as undo point (B12) |
| Undo step order and CLR fields (LV-WR-3, LV-WR-2) | book docs | recovery_contract.md:134-145 | per-transaction order (B4); undo_next resolved (B13); CLR leaves pageLSN |
| Document shapes, sha256 canonical, compensated absolute, audits | shipped_summary, dense_summary, restart_summary, max_summary, scaled_summary | recovery_contract.md:159-183 | non-canonical digest; signed compensated sum |
| Missing input: no document, file named on stderr, nonzero exit | missing_input_rejected | recovery_contract.md:155-157 | empty file read as no records; exit 0 |
| 60 s per book at the limits | max_within_limit | recovery_contract.md:185 | none (timing) |
| Inputs unchanged; second run identical | rerun_identical | recovery_contract.md:187-188 | writes into DIR; nondeterministic order |
| Archive members, compression, timestamp | archive_layout | recovery_contract.md:192-196, expected_targets.json, compiler_flags.json | extra members; deflated; current time |
| pyproject values and `__version__` | package_metadata | recovery_contract.md:196-199, dependency_manifest.json | shipped 2.3.0, tomli dependency, package dir lib |
| selftest.json keys and counts | selftest_truthful | recovery_contract.md:207-213, ci_config.yaml | quoted CI commands; invented test counts |
| build_report.json keys | build_report_values | recovery_contract.md:215-219 | fixed_modules unsorted or incomplete |
| No figure or image id of any book held by the package | negative_hardcoded_sample_answers (negative) | recovery_contract.md:186-187 | copying shipped outputs |
| Shipped smoke tests kept, none skipped | negative_shipped_tests_dropped (negative) | recovery_contract.md:199-201 | deleting or skipping a shipped test |
