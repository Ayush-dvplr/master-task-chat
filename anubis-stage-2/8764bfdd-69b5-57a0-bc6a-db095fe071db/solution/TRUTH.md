# TRUTH.md - 8764bfdd-69b5-57a0-bc6a-db095fe071db

## Defect

The storage team's `estatectl` tool (shipped broken in `/app/data/tool.zip`) must be repaired into a full implementation of the Estate Consolidation Standard (`ECS-standard.md`) and then used to consolidate 100 inputs of 20 formats into two placement manifests, a validation report and a reconciled ledger. The broken tool applies the textbook version of almost every rule: newest export wins, casefold paths, first-match retention rules, last-layer-wins configuration, float sizes, timestamp-order journals. The documented rules differ, and the inputs are seeded so that every textbook choice changes graded outcomes. The hidden eval tier regenerates a fresh export set from EVAL_SEED and runs the delivered tool on it, so the tool must be general.

1. (focal) `estatectl run` reads only the csv and jsonl inventories; the other 12 of the 18 exports and all 11 journals, in 12 formats, are never parsed (C2-C5).
2. (focal) Paths are casefolded and backslash-normalised everywhere, ignoring alias roots, serial volumes, case-sensitive subtrees and S3 encoding (C2, `concept_c2_paths`).
3. (focal) Duplicates resolve by the lexically later mtime string instead of batch capture (C3, `family_t11_boundaries`).
4. (focal) Sizes ignore batch units, de-DE numerals and exact decimals (C3, `concept_c3_sizes`).
5. (focal) Owners are copied as raw tokens instead of resolved through namespaces, SID history and merges (C7).
6. (focal) Configuration loads site-policy-v2.yaml as a layer and lets the last layer win (C9, `concept_c9_config`).
7. (focal) Journals, voids, errata, holds and the prior manifest are ignored, so the ledger cannot reconcile (C1, C5, C10).
8. (drift) Retention rules are applied first-match by substring; ECS 7.3 is last-match with gitignore-style patterns (`concept_c8_retention`).
9. (drift) Simple lower-casing (str.lower) is required, not Unicode case folding (`family_t1_near_duplicate_keys`).
10. (drift) DST overlaps read as standard time, not fold=0 (`family_t3_time_zones_and_epochs`).
11. (drift) Final keys lock later layers; last-layer-wins is wrong (`concept_c9_config`).
12. (drift) Journals apply in sequence order, never timestamp order (`concept_c5_journals`).
13. (drift) Hard links collapse; identical content on different inodes does not (`concept_c3_sizes`).
14. (trap) Excel serials 0 and 60 mean not captured (`family_t5_sentinel_values`).
15. (trap) units-bulletin.pdf corrections override batch units (`family_t14_prose_scope_rules`).
16. (trap) Retired alias roots do not fall back to shorter roots (`family_t6_voided_and_retired_rows`).
17. (trap) Sizes above 2**53 bytes need exact decimals (`family_t12_precision_and_rounding`).
18. (trap) Events stamped exactly window.end are deferred (`family_t11_boundaries`).
19. (trap) Reinstatements exist only in the draft void register (`decoy_void_register_q3_r2_xml`).
20. (trap) Errata withdrawals exist only in the preview register (`decoy_errata_register_q3_r2_tsv`).
21. (trap) ARC01 hard-link identity comes only from the LTFS index (`decoy_arc01_ltfs_index_db`).
22. (trap) The replica journal is authoritative inside the documented gap (`decoy_journal_mkt01_q3_b_log`).
23. (trap) Nothing on ARC01 is purged (schedule footnote, `family_t14_prose_scope_rules`).
24. (trap) Header drift, embedded delimiters and encoding noise appear in every format family (`family_t8_header_drift`, `family_t9_embedded_delimiters`, `family_t10_encoding_noise`).
25. (trap) The finance audit letter also lists a record of a non-finance export; the letter applies to finance volumes only, so that record stays an entry (`concept_c1_authority`, `family_t14_prose_scope_rules`).

The reference solution is Python (`solution/solve.py` writes the repaired `estatectl.py` and runs it). Grading has two channels: the deterministic rewardkit checks in `tests/test_output.py` and the judged criteria in `tests/judge.toml`.

Out of bounds: hard-coding visible answers is caught by `negative_hardcoded_sample_answers` (the eval tier regenerates fresh data); behaviour that depends on where the export set lives is caught by `negative_filename_dependent_behaviour`; reading `/app/data` at runtime is caught by `negative_reads_training_corpus_at_runtime`; nondeterminism is caught by `negative_nondeterministic_output`.

## Load-bearing work

Graded artifacts: `/app/out/config.json`, `/app/out/report.json`, `/app/out/tool.zip`, `/app/out/profile_dev.json`, `/app/out/profile_prod.json`, `/app/out/validation_report.json`, `/app/out/summary.json`. Their content contract is ECS section 11; the per-record outcome rules are ECS sections 2 to 10.

### Concepts (each load-bearing; each has a dedicated HARD check)

- C1 authority: source authority, scope overrides, voids, reinstatements, audit exclusions. Check `concept_c1_authority`.
- C2 paths: alias roots, serial crosswalk, case policy, case-sensitive subtrees, NFC, S3 keys. Check `concept_c2_paths`.
- C3 sizes: units, exact decimals, locale numerals, sentinels, duplicates, hard links. Check `concept_c3_sizes`.
- C4 time: dialects, zone tables, DST overlap and gap, Excel serials, journal windows. Check `concept_c4_time`.
- C5 journals: sequence-ordered replay of create, modify, rename, delete, restore. Check `concept_c5_journals`.
- C6 content: digest crosswalk partitions, revocations, prior store index. Check `concept_c6_content`.
- C7 principals: token namespaces, normalisation, SID history, merges, principal register. Check `concept_c7_principals`.
- C8 retention: extension families, last-match rules, class ages, holds, exemptions. Check `concept_c8_retention`.
- C9 config: layers, locks, profiles, tickets, revocations. Check `concept_c9_config`.
- C10 catalog: entry id continuity, ledger, control chain. Check `concept_c10_catalog`.

Interactions: configuration (C9) decides the window, zones, case policy and block size used by C2, C4, C6 and C8; authority and voids (C1) decide which records reach path resolution (C2); canonical paths (C2) decide duplicates (C3), journal targets (C5), retention matches (C8) and entry-id continuity (C10); tickets gate C1, C9 and holds. Expert-only variants: last-match retention rules, simple lower-casing (not casefold) with per-directory case sensitivity, configuration locks, half-even rounding and exact decimals, standard-time reading of DST overlaps, sequence-ordered journals.

Out of bounds by design: no output may be produced by reading the verifier, and nothing under `/app/data` may be modified.

### Input inventory (100 files)

| code | file | type | rows | role | unique contribution | depends on | depended on by |
|---|---|---|---|---|---|---|---|
| F01 | inv_eng01_q3.csv | csv | 5094 | in-scope | the only snapshot rows of its volume slice | F06 F07 F08 F18 F28 F33 F34 F40 F47 F49 F59 F60 F80 F83 F86 F89 F90 | F59 F90 |
| F02 | inv_obj01_q3_r2.csv | csv | 5033 | in-scope | the only snapshot rows of its volume slice | F06 F07 F08 F26 F28 F33 F34 F40 F41 F49 F52 F60 F80 F83 F86 F89 F90 | F26 F52 |
| F03 | inv_fin01_q3_r2.csv | csv | 5000 | decoy | see the decoy table | F06 F07 F08 F100 F19 F28 F33 F34 F35 F40 F49 F60 F79 F80 F83 F86 F89 F90 | F100 F35 |
| F04 | journal_eng02_q3.csv | csv | 5000 | in-scope | the only change events of its volume | F06 F07 F08 F18 F28 F33 F34 F40 F49 F59 F60 F78 F80 F83 F86 F89 F90 F93 | F78 F93 |
| F05 | principal_merges.csv | csv | 5000 | in-scope | its merge partition | F07 F28 F54 F89 | F28 F54 |
| F06 | void_register_q3.csv | csv | 5000 | in-scope | its void rows | F07 F100 F39 F89 | F01 F02 F03 F04 F100 F14 F15 F22 F23 F24 F25 F26 F30 F31 F38 F39 F42 F44 F46 F50 F66 F70 F71 F72 F73 F74 F75 F76 F95 F96 F98 |
| F07 | change_tickets.csv | csv | 7385 | in-scope | every ticket state | F19 F28 F89 | F01 F02 F03 F04 F05 F06 F08 F09 F10 F100 F11 F12 F13 F14 F15 F16 F17 F18 F19 F20 F21 F22 F23 F24 F25 F26 F27 F28 F29 F30 F31 F32 F33 F34 F35 F36 F37 F38 F39 F40 F41 F42 F43 F44 F45 F46 F47 F48 F49 F50 F51 F52 F53 F54 F55 F56 F57 F58 F59 F60 F61 F62 F63 F64 F65 F66 F67 F68 F69 F70 F71 F72 F73 F74 F75 F76 F77 F78 F79 F80 F81 F82 F83 F84 F85 F86 F87 F88 F89 F90 F91 F92 F93 F94 F95 F96 F97 F98 F99 |
| F08 | errata_register_q3.csv | csv | 5000 | in-scope | its errata partition | F07 F32 F89 | F01 F02 F03 F04 F14 F15 F22 F23 F24 F25 F26 F30 F31 F32 F38 F42 F44 F46 F50 F66 F70 F71 F72 F73 F74 F75 F76 F89 F95 F96 F98 |
| F09 | legal_holds_register.csv | csv | 5000 | in-scope | its hold partition | F07 F25 F80 F89 | F25 F80 |
| F10 | store_index_prior_a.csv | csv | 7655 | in-scope | its prior-store partition | F07 F44 F56 F89 | F44 F56 |
| F11 | hash_xwalk_md5_eng.csv | csv | 5155 | in-scope | its digest crosswalk partition | F07 F85 F86 F89 | F85 F86 |
| F12 | case_sensitive_dirs.csv | csv | 5000 | in-scope | case-sensitive subtrees of its volume | F07 F15 F26 F89 | F15 F26 |
| F13 | export_batches_a.csv | csv | 5000 | in-scope | its batch register (units and captures) | F07 F33 F42 F89 | F33 F42 |
| F14 | inv_fin02_q3.tsv | tsv | 5112 | in-scope | the only snapshot rows of its volume slice | F06 F07 F08 F19 F28 F33 F34 F40 F49 F54 F60 F71 F79 F80 F83 F86 F88 F89 F90 | F54 F71 |
| F15 | inv_ops01_q3.tsv | tsv | 5110 | in-scope | the only snapshot rows of its volume slice | F06 F07 F08 F12 F19 F28 F33 F34 F40 F49 F56 F60 F79 F80 F83 F86 F88 F89 F90 | F12 F80 |
| F16 | tz_transitions_a.tsv | tsv | 6696 | in-scope | its zone transitions | F07 F24 F89 F90 | F24 F90 |
| F17 | ext_families_a.tsv | tsv | 5007 | in-scope | its family table | F07 F18 F89 F93 | F18 F93 |
| F18 | alias_remap_nas.tsv | tsv | 5005 | in-scope | its alias roots | F07 F17 F37 F89 | F01 F04 F17 F24 F37 F70 F75 F95 |
| F19 | principal_uid_map.tsv | tsv | 5013 | in-scope | its owner-token namespace map | F07 F25 F89 | F03 F07 F14 F15 F23 F25 F50 F72 F73 |
| F20 | export_batches_b.tsv | tsv | 5000 | in-scope | its batch register (units and captures) | F07 F63 F72 F89 | F63 F72 |
| F21 | errata_register_q3_r2.tsv | tsv | 7508 | decoy | see the decoy table | F07 F29 F49 F89 | F29 F49 |
| F22 | inv_mkt01_q3.jsonl | jsonl | 5055 | in-scope | the only snapshot rows of its volume slice | F06 F07 F08 F28 F30 F33 F34 F35 F36 F40 F49 F60 F64 F80 F83 F86 F89 F90 | F30 F36 |
| F23 | inv_lab01_q3.jsonl | jsonl | 5086 | in-scope | the only snapshot rows of its volume slice | F06 F07 F08 F19 F28 F33 F34 F40 F41 F43 F49 F60 F79 F80 F83 F86 F89 F90 | F41 F43 |
| F24 | inv_eng01_q3_deep.jsonl | jsonl | 5000 | decoy | see the decoy table | F06 F07 F08 F16 F18 F28 F33 F34 F40 F47 F49 F50 F60 F80 F83 F86 F89 F90 | F16 F50 |
| F25 | journal_hr01_q3.jsonl | jsonl | 5000 | in-scope | the only change events of its volume | F06 F07 F08 F09 F19 F28 F33 F34 F35 F40 F49 F60 F80 F83 F86 F89 F90 | F09 F19 |
| F26 | journal_obj01_events.jsonl | jsonl | 5000 | in-scope | the only change events of its volume | F02 F06 F07 F08 F12 F28 F33 F34 F40 F41 F49 F60 F80 F83 F86 F89 F90 | F02 F12 |
| F27 | hash_xwalk_md5_mkt.jsonl | jsonl | 6647 | in-scope | its digest crosswalk partition | F07 F51 F72 F89 | F51 F72 |
| F28 | void_register_supplement.jsonl | jsonl | 5000 | in-scope | its void rows | F05 F07 F89 | F01 F02 F03 F04 F05 F07 F14 F15 F22 F23 F24 F25 F26 F30 F31 F38 F42 F44 F46 F50 F66 F70 F71 F72 F73 F74 F75 F76 F95 F96 F98 |
| F29 | store_index_prior_b.jsonl | jsonl | 7655 | in-scope | its prior-store partition | F07 F21 F87 F89 | F21 F87 |
| F30 | inv_hr01_q3.xlsx | xlsx | 10000 | in-scope | the only snapshot rows of its volume slice | F06 F07 F08 F22 F28 F33 F34 F35 F40 F49 F60 F64 F67 F80 F83 F86 F89 F90 | F22 F67 |
| F31 | inv_mkt01_supplement.xlsx | xlsx | 10000 | in-scope | the only snapshot rows of its volume slice | F06 F07 F08 F28 F33 F34 F35 F40 F44 F49 F60 F64 F80 F83 F86 F89 F90 F96 | F44 F96 |
| F32 | principal_directory.xlsx | xlsx | 10105 | decoy | see the decoy table | F07 F08 F89 F96 | F08 F96 |
| F33 | authority_matrix.xlsx | xlsx | 10029 | in-scope | runs, scope overrides, ratifications | F07 F13 F70 F89 | F01 F02 F03 F04 F13 F14 F15 F22 F23 F24 F25 F26 F30 F31 F38 F42 F44 F46 F50 F66 F70 F71 F72 F73 F74 F75 F76 F95 F96 F98 |
| F34 | principal_sid_map.xlsx | xlsx | 10000 | in-scope | its owner-token namespace map | F07 F71 F88 F89 | F01 F02 F03 F04 F14 F15 F22 F23 F24 F25 F26 F30 F31 F38 F42 F44 F46 F50 F66 F70 F71 F72 F73 F74 F75 F76 F88 F95 F96 F98 |
| F35 | alias_remap_sharepoint.xlsx | xlsx | 10000 | in-scope | its alias roots | F03 F07 F75 F89 | F03 F22 F25 F30 F31 F71 F74 F75 |
| F36 | ext_families_b.xlsx | xlsx | 10000 | in-scope | its family table | F07 F22 F59 F89 | F22 F59 |
| F37 | holds_matter_index.xlsx | xlsx | 23098 | in-scope | its hold partition | F07 F18 F64 F89 | F18 F64 |
| F38 | inv_rnd01_q3.json | json | 5035 | in-scope | the only snapshot rows of its volume slice | F06 F07 F08 F28 F33 F34 F40 F49 F53 F60 F79 F80 F83 F86 F88 F89 F90 F97 | F53 F79 |
| F39 | volumes_cmdb.json | json | 5020 | decoy | see the decoy table | F06 F07 F55 F89 | F06 F55 |
| F40 | volume-policy.json | json | 5003 | in-scope | its configuration layer | F07 F69 F78 F89 | F01 F02 F03 F04 F14 F15 F22 F23 F24 F25 F26 F30 F31 F38 F42 F44 F46 F50 F66 F69 F70 F71 F72 F73 F74 F75 F76 F78 F95 F96 F98 |
| F41 | principal_s3_ids.json | json | 5001 | in-scope | its owner-token namespace map | F07 F23 F76 F89 | F02 F23 F26 F76 |
| F42 | journal_rnd01_q3.json | json | 5000 | in-scope | the only change events of its volume | F06 F07 F08 F13 F28 F33 F34 F40 F49 F60 F79 F80 F83 F86 F89 F90 F92 F97 | F13 F92 |
| F43 | hash_xwalk_sha1_fin.json | json | 5000 | in-scope | its digest crosswalk partition | F07 F23 F86 F89 | F23 F86 |
| F44 | inv_leg01_q3.xml | xml | 5095 | in-scope | the only snapshot rows of its volume slice | F06 F07 F08 F10 F28 F31 F33 F34 F40 F47 F49 F56 F59 F60 F77 F80 F83 F86 F89 F90 F92 | F10 F31 |
| F45 | void_register_q3_r2.xml | xml | 5000 | decoy | see the decoy table | F07 F50 F89 F92 | F50 F92 |
| F46 | journal_fin02_q3.xml | xml | 5000 | in-scope | the only change events of its volume | F06 F07 F08 F28 F33 F34 F40 F49 F60 F77 F79 F80 F83 F86 F88 F89 F90 | F77 F89 |
| F47 | alias_remap_dfs.xml | xml | 5006 | in-scope | its alias roots | F07 F65 F89 F99 | F01 F24 F44 F65 F70 F98 F99 |
| F48 | case_sensitive_dirs_leg01.xml | xml | 5000 | in-scope | case-sensitive subtrees of its volume | F07 F79 F89 F94 | F79 F94 |
| F49 | errata_register_tape.xml | xml | 5000 | in-scope | its errata partition | F07 F21 F65 F89 | F01 F02 F03 F04 F14 F15 F21 F22 F23 F24 F25 F26 F30 F31 F38 F42 F44 F46 F50 F65 F66 F70 F71 F72 F73 F74 F75 F76 F95 F96 F98 |
| F50 | inv_fin01_q3.parquet | parquet | 5135 | in-scope | the only snapshot rows of its volume slice | F06 F07 F08 F19 F24 F28 F33 F34 F40 F45 F49 F60 F79 F80 F83 F86 F89 F90 | F24 F45 |
| F51 | hash_index_master.parquet | parquet | 5000 | decoy | see the decoy table | F07 F27 F64 F89 | F27 F64 |
| F52 | estate_manifest_q2.parquet | parquet | 64341 | decoy | see the decoy table | F02 F07 F62 F89 | F02 F62 F78 |
| F53 | store_index_prior_c.parquet | parquet | 7655 | in-scope | its prior-store partition | F07 F38 F83 F89 | F38 F83 |
| F54 | hash_xwalk_md5_fin.parquet | parquet | 5000 | in-scope | its digest crosswalk partition | F05 F07 F14 F89 | F05 F14 |
| F55 | tz_transitions_b.parquet | parquet | 6696 | in-scope | its zone transitions | F07 F39 F89 F95 | F39 F95 |
| F56 | ECS-handbook-paths.docx | docx | 5006 | in-scope | its alias roots | F07 F10 F84 F89 | F10 F15 F44 F73 F84 F95 F98 |
| F57 | retention-schedule-2026-r2.docx | docx | 5021 | in-scope | class ages and family table C | F07 F87 F89 F98 | F87 F98 |
| F58 | legal-hold-memo-q3.docx | docx | 5000 | in-scope | hold releases | F07 F67 F82 F89 | F67 F82 |
| F59 | owner-migration-plan.docx | docx | 5002 | in-scope | its owner-token namespace map | F01 F07 F36 F89 | F01 F04 F36 F44 F75 F95 F98 |
| F60 | errata-bulletin-q3.docx | docx | 5000 | in-scope | its errata partition | F07 F68 F74 F89 | F01 F02 F03 F04 F14 F15 F22 F23 F24 F25 F26 F30 F31 F38 F42 F44 F46 F50 F66 F68 F70 F71 F72 F73 F74 F75 F76 F95 F96 F98 |
| F61 | tape-operations-notes.docx | docx | 5000 | in-scope | its batch register (units and captures) | F07 F62 F75 F89 | F62 F75 |
| F62 | retention-schedule-2026-r3.docx | docx | 10021 | decoy | see the decoy table | F07 F52 F61 F89 | F52 F61 |
| F63 | ECS-annex-hosts-rev6.pdf | pdf | 5000 | in-scope | its host-zone partition | F07 F20 F89 F91 | F20 F91 |
| F64 | hr-roster-q3.pdf | pdf | 5002 | in-scope | its owner-token namespace map | F07 F37 F51 F89 | F22 F30 F31 F37 F51 F71 F74 |
| F65 | audit-scope-letter-fin.pdf | pdf | 5000 | in-scope | finance exclusions | F07 F47 F49 F89 | F47 F49 |
| F66 | rnd01_cold_listing.pdf | pdf | 5073 | in-scope | the only snapshot rows of its volume slice | F06 F07 F08 F28 F33 F34 F40 F49 F60 F70 F77 F80 F83 F84 F86 F89 F90 | F70 F84 |
| F67 | vendor-hash-attestation.pdf | pdf | 5000 | in-scope | its digest crosswalk partition | F07 F30 F58 F89 | F30 F58 |
| F68 | units-bulletin.pdf | pdf | 5006 | in-scope | its batch register (units and captures) | F07 F60 F73 F89 | F60 F73 |
| F69 | ECS-annex-hosts-rev7.pdf | pdf | 10000 | decoy | see the decoy table | F07 F40 F89 F97 | F40 F97 |
| F70 | journal_eng01_q3.log | log | 5000 | in-scope | the only change events of its volume | F06 F07 F08 F18 F28 F33 F34 F40 F47 F49 F60 F66 F80 F83 F86 F89 F90 | F33 F66 |
| F71 | journal_mkt01_q3.log | log | 5049 | in-scope | the only change events of its volume | F06 F07 F08 F14 F28 F33 F34 F35 F40 F49 F60 F64 F80 F83 F86 F89 F90 | F14 F34 |
| F72 | journal_fin01_q3.log | log | 5000 | in-scope | the only change events of its volume | F06 F07 F08 F19 F20 F27 F28 F33 F34 F40 F49 F60 F79 F80 F83 F86 F89 F90 | F20 F27 |
| F73 | journal_ops01_q3.log | log | 5000 | in-scope | the only change events of its volume | F06 F07 F08 F19 F28 F33 F34 F40 F49 F56 F60 F68 F79 F80 F83 F86 F89 F90 | F68 F83 |
| F74 | journal_mkt01_q3_b.log | log | 5260 | decoy | see the decoy table | F06 F07 F08 F28 F33 F34 F35 F40 F49 F60 F64 F77 F80 F83 F86 F89 F90 | F60 F77 |
| F75 | inv_eng01_q3_part2.db | sqlite | 5096 | in-scope | the only snapshot rows of its volume slice | F06 F07 F08 F18 F28 F33 F34 F35 F40 F49 F59 F60 F61 F80 F83 F86 F89 F90 | F35 F61 |
| F76 | arc01_ltfs_index.db | sqlite | 5000 | decoy | see the decoy table | F06 F07 F08 F28 F33 F34 F40 F41 F49 F60 F79 F80 F83 F86 F89 F90 F95 F97 | F41 F95 |
| F77 | principal_legacy.db | sqlite | 5002 | in-scope | its owner-token namespace map | F07 F46 F74 F89 | F44 F46 F66 F74 F98 |
| F78 | store_index_prior_d.db | sqlite | 7654 | in-scope | its prior-store partition | F04 F07 F40 F52 F89 | F04 F40 |
| F79 | volumes.yaml | yaml | 5018 | in-scope | volume table and alias table E | F07 F38 F48 F89 | F03 F14 F15 F23 F38 F42 F46 F48 F50 F72 F73 F76 F96 |
| F80 | site-policy.yaml | yaml | 5007 | in-scope | its configuration layer | F07 F09 F15 F89 | F01 F02 F03 F04 F09 F14 F15 F22 F23 F24 F25 F26 F30 F31 F38 F42 F44 F46 F50 F66 F70 F71 F72 F73 F74 F75 F76 F95 F96 F98 |
| F81 | retention_rules_v3.yaml | yaml | 5000 | in-scope | its retention rules | F07 F88 F89 F91 | F88 F91 |
| F82 | site-policy-v2.yaml | yaml | 7507 | decoy | see the decoy table | F07 F58 F89 F98 | F58 F98 |
| F83 | estate-defaults.toml | toml | 5005 | in-scope | its configuration layer | F07 F53 F73 F89 | F01 F02 F03 F04 F14 F15 F22 F23 F24 F25 F26 F30 F31 F38 F42 F44 F46 F50 F53 F66 F70 F71 F72 F73 F74 F75 F76 F95 F96 F98 |
| F84 | retention_rules_v4.toml | toml | 5040 | decoy | see the decoy table | F07 F56 F66 F89 | F56 F66 |
| F85 | retention_overlays.toml | toml | 5004 | in-scope | its retention rules | F07 F11 F89 F99 | F11 F99 |
| F86 | operator-overrides.ini | ini | 5015 | in-scope | its configuration layer | F07 F11 F43 F89 | F01 F02 F03 F04 F11 F14 F15 F22 F23 F24 F25 F26 F30 F31 F38 F42 F43 F44 F46 F50 F66 F70 F71 F72 F73 F74 F75 F76 F95 F96 F98 |
| F87 | host_aliases.ini | ini | 5000 | in-scope | uid host aliases | F07 F29 F57 F89 | F29 F57 |
| F88 | service_accounts.ini | ini | 5000 | in-scope | its owner-token namespace map | F07 F34 F81 F89 | F14 F15 F34 F38 F46 F81 |
| F89 | ECS-standard.md | md | 5003 | in-scope | the rules and alias table F | F07 F08 F46 | F01 F02 F03 F04 F05 F06 F07 F08 F09 F10 F100 F11 F12 F13 F14 F15 F16 F17 F18 F19 F20 F21 F22 F23 F24 F25 F26 F27 F28 F29 F30 F31 F32 F33 F34 F35 F36 F37 F38 F39 F40 F41 F42 F43 F44 F45 F46 F47 F48 F49 F50 F51 F52 F53 F54 F55 F56 F57 F58 F59 F60 F61 F62 F63 F64 F65 F66 F67 F68 F69 F70 F71 F72 F73 F74 F75 F76 F77 F78 F79 F80 F81 F82 F83 F84 F85 F86 F87 F88 F90 F91 F92 F93 F94 F95 F96 F97 F98 F99 |
| F90 | source-register.md | md | 5000 | in-scope | file register, dialects, host table A | F01 F07 F16 F89 | F01 F02 F03 F04 F14 F15 F16 F22 F23 F24 F25 F26 F30 F31 F38 F42 F44 F46 F50 F66 F70 F71 F72 F73 F74 F75 F76 F95 F96 F98 |
| F91 | ops-runbook.md | md | 5000 | in-scope | journal gap, not-a-file rules, merges B | F07 F63 F81 F89 | F63 F81 |
| F92 | principal_map_ldap.html | html | 10010 | decoy | see the decoy table | F07 F42 F45 F89 | F42 F44 F45 F95 |
| F93 | ext_families_wiki.html | html | 5004 | in-scope | its family table | F04 F07 F17 F89 | F04 F17 |
| F94 | holds_portal_export.html | html | 5000 | in-scope | its hold partition | F07 F48 F89 F97 | F48 F97 |
| F95 | inv_eng02_q3.txt | fixed | 5113 | in-scope | the only snapshot rows of its volume slice | F06 F07 F08 F18 F28 F33 F34 F40 F49 F55 F56 F59 F60 F76 F80 F83 F86 F89 F90 F92 | F55 F76 |
| F96 | arc01_tape_catalog.txt | fixed | 5077 | in-scope | the only snapshot rows of its volume slice | F06 F07 F08 F28 F31 F32 F33 F34 F40 F49 F60 F79 F80 F83 F86 F89 F90 F97 | F31 F32 |
| F97 | principal_mainframe_ids.txt | fixed | 5002 | in-scope | its owner-token namespace map | F07 F69 F89 F94 | F38 F42 F69 F76 F94 F96 |
| F98 | journal_leg01_notifications.mbox | mbox | 5000 | in-scope | the only change events of its volume | F06 F07 F08 F28 F33 F34 F40 F47 F49 F56 F57 F59 F60 F77 F80 F82 F83 F86 F89 F90 | F57 F82 |
| F99 | legal_hold_windows.ics | ics | 5000 | in-scope | its hold partition | F07 F47 F85 F89 | F47 F85 |
| F100 | tool.zip | zip | 5008 | in-scope | family table E and the tool | F03 F06 F07 F89 | F03 F06 |

### Decoys

| decoy | looks authoritative because | demoted by (file, locator) | load-bearing roles | HARD checks failing if ignored / trusted |
|---|---|---|---|---|
| inv_fin01_q3_r2.csv | newer exported_utc, filled-in sizes | own header run_mode=dryrun; ECS 3.1 | (d, e) (d) self-declared dry run; (e) approved scope overrides make its close/ subtrees authoritative | decoy check `decoy_inv_fin01_q3_r2_csv` plus C1 |
| errata_register_q3_r2.tsv | revision 2 with higher revs | #status=preview header; ECS 3.5 | (b, d) (b) only withdrawal evidence; (d) preview status inside it | decoy check `decoy_errata_register_q3_r2_tsv` plus C1 |
| inv_eng01_q3_deep.jsonl | more columns than the csv export | run_mode deep-scan; ECS 3.1 | (a, d, e) (a) only deep-scan totals; (d) self-declared deep scan; (e) scope overrides | decoy check `decoy_inv_eng01_q3_deep_jsonl` plus C1 |
| principal_directory.xlsx | one sheet with every principal and account | core description snapshot_of=2025-03-31; ECS 5.4 | (c, d) (c) only SID-history crosswalk; (d) stale snapshot declared inside it | decoy check `decoy_principal_directory_xlsx` plus C7 |
| volumes_cmdb.json | richer volume records | authoritative_for list; ECS 5.2 | (c, d) (c) only serial crosswalk; (d) authority list inside it | decoy check `decoy_volumes_cmdb_json` plus C2 |
| void_register_q3_r2.xml | revision 2 of the void register | status=draft root attribute; ECS 3.4 | (b, d) (b) only reinstatement evidence; (d) draft status inside it | decoy check `decoy_void_register_q3_r2_xml` plus C1 |
| hash_index_master.parquet | most complete digest index | producer note; ECS 6.2 | (a, e) (a) only crosswalk control totals; (e) rows with origin ARC01 are authoritative | decoy check `decoy_hash_index_master_parquet` plus C6 |
| estate_manifest_q2.parquet | has the exact shape of the deliverable | ECS 10.1 | (a, c) (a) only opening balance and chain start; (c) only entry-id crosswalk | decoy check `decoy_estate_manifest_q2_parquet` plus C10 |
| retention-schedule-2026-r3.docx | newer schedule revision | DRAFT subject and text; ratification | (d, e) (d) draft declared inside it; (e) Annex F corrections apply to pending rows | decoy check `decoy_retention_schedule_2026_r3_docx` plus C8 |
| ECS-annex-hosts-rev7.pdf | newer annex revision | cover text withdrawn; ratification rev7-appendix-D | (d, e) (d) withdrawal declared inside it; (e) Appendix D adopted | decoy check `decoy_ecs_annex_hosts_rev7_pdf` plus C4 |
| journal_mkt01_q3_b.log | more events than the primary | role=replica header; ops-runbook.md gap | (a, e) (a) only CHECKPOINT counts; (e) authoritative inside the gap | decoy check `decoy_journal_mkt01_q3_b_log` plus C5 |
| arc01_ltfs_index.db | plain bytes and SHA-256 for ARC01 | run_mode ltfs-shadow; ECS 3.1 | (c, d) (c) only file_id/nlink source for ARC01; (d) self-declared shadow | decoy check `decoy_arc01_ltfs_index_db` plus C3 |
| site-policy-v2.yaml | newer layer 20 | status proposed; ratification site-policy v2 | (b, d) (b) only revocation evidence; (d) proposed status inside it | decoy check `decoy_site_policy_v2_yaml` plus C9 |
| retention_rules_v4.toml | label FINAL, newer ruleset | status pending-cab; ratification scope rows | (b, d) (b) only withdrawal evidence for v3 rules; (d) pending status inside it | decoy check `decoy_retention_rules_v4_toml` plus C8 |
| principal_map_ldap.html | an LDAP map covering several domains | ARCHIVED banner; ECS 5.4 | (d, e) (d) archive banner inside it; (e) OLDCORP table authoritative | decoy check `decoy_principal_map_ldap_html` plus C7 |

## Verification

`tests/test.sh` hardens the verifier and runs rewardkit 0.2.1 over `/tests`. Channel A (`tests/test_output.py`) registers 50 checks: positive weight total 206, negative total -18. Six EASY checks weigh 1 each (6); 40 HARD checks weigh 5 each (200). Every HARD check judges only its own record population or its own concept, and requires (a) the visible-tier expectation computed at build time and (b) the same rule on the eval tier regenerated from EVAL_SEED and produced by running the delivered tool as nobody, from the extracted archive root. Ownership is split so that one wrong fact costs the checks that own it: family and decoy record lines carry the record's outcome plus the entry fields governed by the rules of the traps that touch it (entry_id never); a concept check compares its own entry fields record by record over the entries both sides keep (the delivered set must keep at least 99% of the expected entries) and its own exception reasons over the whole population; `concept_c5_journals` owns which journal events become entries; `concept_c6_content` owns closing and control `store_bytes` (ECS 6.5); `concept_c10_catalog` owns entry ids, the rest of the ledger and the control chain. Comparisons are exact (per-record 32-bit digests and whole-population digests); failure messages carry no expected values. On both tiers the generator gives up to two records per pair a second ECS 9 reason for the competing pairs SUPERSEDED_SCOPE/VOIDED, VOIDED/NOT_A_FILE, PATH_UNRESOLVED/SIZE_UNKNOWN, SIZE_UNKNOWN/HASH_UNRESOLVED and HASH_UNRESOLVED/OWNER_UNRESOLVED, so the reason order decides graded outcomes (STALE_EVENT and DEFERRED_EVENT apply only to journal events and exclude each other, so they never compete with NOT_A_FILE or with each other). On the eval tier one record is also planted under another export's approved scope override so that OUT_OF_AUTHORITY before SUPERSEDED_SCOPE decides an outcome. The eval tier also carries one fixture for each of five rules the visible inputs never reach (`_plant_rule_triggers`): a UNC path through empty, `.` and `..` segments and a posix path with `..` above its root (ECS 5.3; `concept_c2_paths`, `family_t1_near_duplicate_keys`), a local wall-clock time inside a spring-forward gap (ECS 4.3; `concept_c4_time`, `family_t3_time_zones_and_epochs`), a duplicate pair whose batches share captured_utc (ECS 6.4; `concept_c3_sizes`, `family_t11_boundaries`), a RESTORE whose path was deleted twice before it (ECS 8; `concept_c5_journals`, `family_t13_referential_breaks`) and an OBJ01 sequencer written with a leading zero, so byte order and value order disagree (ECS 8; `concept_c5_journals`, `family_t3_time_zones_and_epochs`). On both tiers the finance audit letter names one kept non-finance record, which must stay an entry because the letter applies to finance volumes only; a tool that voids every listed id fails `concept_c1_authority` and `concept_c10_catalog` (and `family_t14_prose_scope_rules` on the eval tier).

Positive checks:

- `artifacts_present_and_parse` (weight 1)
- `config_matches_prod_profile` (weight 1)
- `report_records_tool_run` (weight 1)
- `tool_archive_layout` (weight 1)
- `validation_report_shape` (weight 1)
- `profile_shape` (weight 1)
- `family_t1_near_duplicate_keys` (weight 5)
- `family_t2_unit_and_scale` (weight 5)
- `family_t3_time_zones_and_epochs` (weight 5)
- `family_t4_locale_numerals` (weight 5)
- `family_t5_sentinel_values` (weight 5)
- `family_t6_voided_and_retired_rows` (weight 5)
- `family_t7_superseded_revisions` (weight 5)
- `family_t8_header_drift` (weight 5)
- `family_t9_embedded_delimiters` (weight 5)
- `family_t10_encoding_noise` (weight 5)
- `family_t11_boundaries` (weight 5)
- `family_t12_precision_and_rounding` (weight 5)
- `family_t13_referential_breaks` (weight 5)
- `family_t14_prose_scope_rules` (weight 5)
- `family_t15_extreme_values` (weight 5)
- `decoy_inv_fin01_q3_r2_csv` (weight 5)
- `decoy_errata_register_q3_r2_tsv` (weight 5)
- `decoy_inv_eng01_q3_deep_jsonl` (weight 5)
- `decoy_principal_directory_xlsx` (weight 5)
- `decoy_volumes_cmdb_json` (weight 5)
- `decoy_void_register_q3_r2_xml` (weight 5)
- `decoy_hash_index_master_parquet` (weight 5)
- `decoy_estate_manifest_q2_parquet` (weight 5)
- `decoy_retention_schedule_2026_r3_docx` (weight 5)
- `decoy_ecs_annex_hosts_rev7_pdf` (weight 5)
- `decoy_journal_mkt01_q3_b_log` (weight 5)
- `decoy_arc01_ltfs_index_db` (weight 5)
- `decoy_site_policy_v2_yaml` (weight 5)
- `decoy_retention_rules_v4_toml` (weight 5)
- `decoy_principal_map_ldap_html` (weight 5)
- `concept_c1_authority` (weight 5)
- `concept_c2_paths` (weight 5)
- `concept_c3_sizes` (weight 5)
- `concept_c4_time` (weight 5)
- `concept_c5_journals` (weight 5)
- `concept_c6_content` (weight 5)
- `concept_c7_principals` (weight 5)
- `concept_c8_retention` (weight 5)
- `concept_c9_config` (weight 5)
- `concept_c10_catalog` (weight 5)

Negative checks:

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -5)
- `negative_reads_training_corpus_at_runtime` (weight -5)
- `negative_nondeterministic_output` (weight -3)

Channel B (`tests/judge.toml`) has 11 binary criteria: positives r2, r3, r4, r5, r6, r10 (18 points), negatives r1, r7, r8, r9, r11 (-17). The rule that combines the two channels belongs to the runner harness (`tests/reward.toml`, half each) and is not transcribed further here.

### Test to rule trace

| check | rule | file and locator |
|---|---|---|
| `artifacts_present_and_parse` | instruction.md output paths | instruction.md paragraph 2 |
| `config_matches_prod_profile` | config.json equals profile_prod config | ECS-standard.md section 11 |
| `report_records_tool_run` | export-report contract | instruction.md paragraph 2; tool README |
| `tool_archive_layout` | deliver the repaired tool with the shipped layout | instruction.md paragraph 2 |
| `validation_report_shape` | validation_report.json shape and order | ECS-standard.md sections 9 and 11 |
| `profile_shape` | profile field and (volume, path) entry order | ECS-standard.md section 11 |
| `family_t1_near_duplicate_keys` | the trap family's rules (see the coverage matrix and loops) | ECS sections cited in the trap manifest |
| `family_t2_unit_and_scale` | the trap family's rules (see the coverage matrix and loops) | ECS sections cited in the trap manifest |
| `family_t3_time_zones_and_epochs` | the trap family's rules (see the coverage matrix and loops) | ECS sections cited in the trap manifest |
| `family_t4_locale_numerals` | the trap family's rules (see the coverage matrix and loops) | ECS sections cited in the trap manifest |
| `family_t5_sentinel_values` | the trap family's rules (see the coverage matrix and loops) | ECS sections cited in the trap manifest |
| `family_t6_voided_and_retired_rows` | the trap family's rules (see the coverage matrix and loops) | ECS sections cited in the trap manifest |
| `family_t7_superseded_revisions` | the trap family's rules (see the coverage matrix and loops) | ECS sections cited in the trap manifest |
| `family_t8_header_drift` | the trap family's rules (see the coverage matrix and loops) | ECS sections cited in the trap manifest |
| `family_t9_embedded_delimiters` | the trap family's rules (see the coverage matrix and loops) | ECS sections cited in the trap manifest |
| `family_t10_encoding_noise` | the trap family's rules (see the coverage matrix and loops) | ECS sections cited in the trap manifest |
| `family_t11_boundaries` | the trap family's rules (see the coverage matrix and loops) | ECS sections cited in the trap manifest |
| `family_t12_precision_and_rounding` | the trap family's rules (see the coverage matrix and loops) | ECS sections cited in the trap manifest |
| `family_t13_referential_breaks` | the trap family's rules (see the coverage matrix and loops) | ECS sections cited in the trap manifest |
| `family_t14_prose_scope_rules` | the trap family's rules (see the coverage matrix and loops) | ECS sections cited in the trap manifest |
| `family_t15_extreme_values` | the trap family's rules (see the coverage matrix and loops) | ECS sections cited in the trap manifest |
| `decoy_inv_fin01_q3_r2_csv` | decoy demotion and its load-bearing roles | see the decoy table |
| `decoy_errata_register_q3_r2_tsv` | decoy demotion and its load-bearing roles | see the decoy table |
| `decoy_inv_eng01_q3_deep_jsonl` | decoy demotion and its load-bearing roles | see the decoy table |
| `decoy_principal_directory_xlsx` | decoy demotion and its load-bearing roles | see the decoy table |
| `decoy_volumes_cmdb_json` | decoy demotion and its load-bearing roles | see the decoy table |
| `decoy_void_register_q3_r2_xml` | decoy demotion and its load-bearing roles | see the decoy table |
| `decoy_hash_index_master_parquet` | decoy demotion and its load-bearing roles | see the decoy table |
| `decoy_estate_manifest_q2_parquet` | decoy demotion and its load-bearing roles | see the decoy table |
| `decoy_retention_schedule_2026_r3_docx` | decoy demotion and its load-bearing roles | see the decoy table |
| `decoy_ecs_annex_hosts_rev7_pdf` | decoy demotion and its load-bearing roles | see the decoy table |
| `decoy_journal_mkt01_q3_b_log` | decoy demotion and its load-bearing roles | see the decoy table |
| `decoy_arc01_ltfs_index_db` | decoy demotion and its load-bearing roles | see the decoy table |
| `decoy_site_policy_v2_yaml` | decoy demotion and its load-bearing roles | see the decoy table |
| `decoy_retention_rules_v4_toml` | decoy demotion and its load-bearing roles | see the decoy table |
| `decoy_principal_map_ldap_html` | decoy demotion and its load-bearing roles | see the decoy table |
| `concept_c1_authority` | the concept's ECS sections | ECS-standard.md |
| `concept_c2_paths` | the concept's ECS sections | ECS-standard.md |
| `concept_c3_sizes` | the concept's ECS sections | ECS-standard.md |
| `concept_c4_time` | the concept's ECS sections | ECS-standard.md |
| `concept_c5_journals` | the concept's ECS sections | ECS-standard.md |
| `concept_c6_content` | the concept's ECS sections | ECS-standard.md |
| `concept_c7_principals` | the concept's ECS sections | ECS-standard.md |
| `concept_c8_retention` | the concept's ECS sections | ECS-standard.md |
| `concept_c9_config` | the concept's ECS sections | ECS-standard.md |
| `concept_c10_catalog` | the concept's ECS sections | ECS-standard.md |
| `negative_hardcoded_sample_answers` | derive every value from --data | instruction.md paragraph 3 |
| `negative_filename_dependent_behaviour` | output must not depend on where the set is stored | instruction.md paragraph 3 |
| `negative_reads_training_corpus_at_runtime` | must not read /app/data | instruction.md paragraph 3 |
| `negative_nondeterministic_output` | byte-identical repeated runs | instruction.md paragraph 3 |

### Trap-family coverage matrix (traps per file)

| file | T1 | T2 | T3 | T4 | T5 | T6 | T7 | T8 | T9 | T10 | T11 | T12 | T13 | T14 | T15 | T16 | total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| inv_eng01_q3.csv | 1 | 0 | 0 | 1 | 1 | 1 | 0 | 1 | 0 | 1 | 1 | 2 | 1 | 1 | 1 | 0 | 12 |
| inv_obj01_q3_r2.csv | 5 | 0 | 1 | 0 | 3 | 1 | 1 | 1 | 0 | 1 | 1 | 0 | 2 | 0 | 1 | 0 | 17 |
| inv_fin01_q3_r2.csv | 4 | 0 | 2 | 0 | 7 | 5 | 3 | 2 | 2 | 3 | 1 | 0 | 2 | 0 | 0 | 248 | 279 |
| journal_eng02_q3.csv | 3 | 0 | 2 | 0 | 3 | 0 | 0 | 1 | 1 | 1 | 3 | 2 | 0 | 0 | 2 | 0 | 18 |
| principal_merges.csv | 3 | 0 | 0 | 0 | 0 | 0 | 2 | 1 | 3 | 2 | 3 | 0 | 0 | 0 | 0 | 0 | 14 |
| void_register_q3.csv | 1 | 0 | 0 | 0 | 0 | 2 | 4 | 1 | 2 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 13 |
| change_tickets.csv | 1 | 0 | 0 | 0 | 1 | 0 | 5 | 1 | 2 | 3 | 1 | 0 | 0 | 0 | 0 | 0 | 14 |
| errata_register_q3.csv | 1 | 0 | 0 | 3 | 4 | 0 | 2 | 1 | 2 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 17 |
| legal_holds_register.csv | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 3 | 7 | 0 | 0 | 0 | 0 | 0 | 14 |
| store_index_prior_a.csv | 3 | 0 | 0 | 0 | 0 | 3 | 3 | 0 | 2 | 3 | 0 | 0 | 0 | 0 | 2 | 0 | 16 |
| hash_xwalk_md5_eng.csv | 6 | 0 | 0 | 0 | 0 | 2 | 0 | 1 | 2 | 3 | 0 | 0 | 2 | 0 | 0 | 0 | 16 |
| case_sensitive_dirs.csv | 5 | 0 | 0 | 0 | 0 | 3 | 0 | 1 | 3 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 17 |
| export_batches_a.csv | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 2 | 2 | 0 | 0 | 2 | 0 | 0 | 13 |
| inv_fin02_q3.tsv | 4 | 0 | 1 | 1 | 3 | 0 | 0 | 0 | 1 | 1 | 2 | 2 | 1 | 0 | 1 | 0 | 17 |
| inv_ops01_q3.tsv | 5 | 0 | 1 | 1 | 4 | 1 | 1 | 1 | 0 | 1 | 0 | 0 | 0 | 1 | 1 | 0 | 17 |
| tz_transitions_a.tsv | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 4 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 14 |
| ext_families_a.tsv | 7 | 0 | 0 | 0 | 2 | 2 | 2 | 1 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 18 |
| alias_remap_nas.tsv | 6 | 0 | 0 | 0 | 0 | 2 | 2 | 1 | 2 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 16 |
| principal_uid_map.tsv | 4 | 0 | 0 | 0 | 0 | 2 | 1 | 1 | 2 | 2 | 0 | 0 | 3 | 0 | 0 | 0 | 15 |
| export_batches_b.tsv | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 3 | 2 | 0 | 0 | 2 | 0 | 0 | 14 |
| errata_register_q3_r2.tsv | 2 | 0 | 0 | 0 | 0 | 6 | 6 | 1 | 2 | 3 | 0 | 0 | 4 | 0 | 0 | 4 | 28 |
| inv_mkt01_q3.jsonl | 2 | 0 | 1 | 0 | 2 | 2 | 1 | 1 | 0 | 2 | 1 | 0 | 1 | 0 | 3 | 0 | 16 |
| inv_lab01_q3.jsonl | 6 | 0 | 0 | 0 | 2 | 1 | 1 | 0 | 0 | 0 | 1 | 0 | 1 | 1 | 1 | 0 | 14 |
| inv_eng01_q3_deep.jsonl | 4 | 0 | 3 | 0 | 4 | 3 | 2 | 2 | 2 | 2 | 0 | 0 | 2 | 0 | 0 | 237 | 261 |
| journal_hr01_q3.jsonl | 0 | 0 | 2 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 6 | 0 | 3 | 0 | 0 | 0 | 13 |
| journal_obj01_events.jsonl | 0 | 0 | 2 | 0 | 2 | 0 | 0 | 1 | 0 | 0 | 3 | 3 | 0 | 0 | 1 | 0 | 12 |
| hash_xwalk_md5_mkt.jsonl | 5 | 0 | 0 | 0 | 0 | 2 | 0 | 1 | 4 | 3 | 0 | 0 | 3 | 0 | 0 | 0 | 18 |
| void_register_supplement.jsonl | 1 | 0 | 0 | 0 | 2 | 4 | 4 | 1 | 2 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 17 |
| store_index_prior_b.jsonl | 3 | 0 | 0 | 0 | 0 | 3 | 3 | 0 | 2 | 3 | 0 | 0 | 0 | 0 | 2 | 0 | 16 |
| inv_hr01_q3.xlsx | 3 | 2 | 2 | 0 | 3 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 0 | 20 |
| inv_mkt01_supplement.xlsx | 3 | 1 | 1 | 0 | 3 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 1 | 1 | 2 | 0 | 20 |
| principal_directory.xlsx | 1 | 0 | 0 | 0 | 0 | 8 | 2 | 1 | 2 | 2 | 0 | 0 | 8 | 0 | 0 | 7 | 31 |
| authority_matrix.xlsx | 3 | 0 | 0 | 0 | 0 | 0 | 10 | 1 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 20 |
| principal_sid_map.xlsx | 6 | 0 | 0 | 0 | 0 | 2 | 0 | 1 | 3 | 2 | 0 | 0 | 6 | 0 | 0 | 0 | 20 |
| alias_remap_sharepoint.xlsx | 3 | 0 | 0 | 0 | 0 | 3 | 0 | 1 | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 10 |
| ext_families_b.xlsx | 8 | 0 | 0 | 0 | 5 | 0 | 0 | 1 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 20 |
| holds_matter_index.xlsx | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 3 | 8 | 0 | 4 | 0 | 0 | 0 | 20 |
| inv_rnd01_q3.json | 1 | 0 | 2 | 1 | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 1 | 1 | 0 | 2 | 0 | 14 |
| volumes_cmdb.json | 3 | 0 | 0 | 0 | 0 | 4 | 4 | 1 | 2 | 3 | 0 | 0 | 5 | 0 | 0 | 5 | 27 |
| volume-policy.json | 3 | 0 | 0 | 1 | 4 | 0 | 2 | 1 | 3 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 16 |
| principal_s3_ids.json | 5 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 2 | 2 | 0 | 0 | 3 | 0 | 0 | 0 | 15 |
| journal_rnd01_q3.json | 0 | 0 | 4 | 1 | 2 | 0 | 0 | 1 | 0 | 0 | 5 | 0 | 1 | 0 | 0 | 0 | 14 |
| hash_xwalk_sha1_fin.json | 5 | 0 | 0 | 0 | 0 | 3 | 0 | 1 | 4 | 2 | 0 | 0 | 3 | 0 | 0 | 0 | 18 |
| inv_leg01_q3.xml | 2 | 0 | 0 | 0 | 2 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 1 | 2 | 0 | 15 |
| void_register_q3_r2.xml | 3 | 0 | 0 | 0 | 0 | 6 | 3 | 1 | 2 | 3 | 0 | 0 | 6 | 0 | 0 | 5 | 29 |
| journal_fin02_q3.xml | 0 | 0 | 3 | 1 | 2 | 0 | 0 | 1 | 0 | 0 | 2 | 3 | 2 | 0 | 0 | 0 | 14 |
| alias_remap_dfs.xml | 3 | 0 | 0 | 0 | 0 | 2 | 1 | 1 | 1 | 1 | 1 | 0 | 2 | 0 | 0 | 0 | 12 |
| case_sensitive_dirs_leg01.xml | 5 | 0 | 0 | 0 | 0 | 3 | 0 | 1 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 13 |
| errata_register_tape.xml | 1 | 0 | 0 | 2 | 2 | 0 | 3 | 1 | 1 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 14 |
| inv_fin01_q3.parquet | 5 | 1 | 1 | 0 | 2 | 1 | 1 | 1 | 1 | 0 | 0 | 0 | 1 | 1 | 0 | 0 | 15 |
| hash_index_master.parquet | 3 | 0 | 0 | 0 | 0 | 4 | 8 | 1 | 3 | 3 | 0 | 0 | 3 | 0 | 0 | 5 | 30 |
| estate_manifest_q2.parquet | 25 | 0 | 0 | 0 | 0 | 14 | 21 | 0 | 0 | 0 | 26 | 0 | 20 | 0 | 0 | 23 | 129 |
| store_index_prior_c.parquet | 3 | 0 | 0 | 0 | 0 | 3 | 3 | 0 | 2 | 3 | 0 | 0 | 0 | 0 | 2 | 0 | 16 |
| hash_xwalk_md5_fin.parquet | 6 | 0 | 0 | 0 | 0 | 2 | 0 | 1 | 2 | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 15 |
| tz_transitions_b.parquet | 2 | 0 | 3 | 3 | 0 | 0 | 0 | 1 | 2 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 14 |
| ECS-handbook-paths.docx | 3 | 0 | 0 | 0 | 0 | 1 | 2 | 1 | 2 | 1 | 2 | 0 | 1 | 0 | 0 | 0 | 13 |
| retention-schedule-2026-r2.docx | 4 | 0 | 0 | 0 | 1 | 2 | 2 | 0 | 0 | 0 | 4 | 0 | 0 | 1 | 0 | 0 | 14 |
| legal-hold-memo-q3.docx | 2 | 0 | 0 | 0 | 1 | 3 | 1 | 1 | 2 | 3 | 2 | 0 | 0 | 0 | 0 | 0 | 15 |
| owner-migration-plan.docx | 3 | 0 | 0 | 0 | 0 | 3 | 2 | 1 | 2 | 2 | 0 | 0 | 3 | 0 | 0 | 0 | 16 |
| errata-bulletin-q3.docx | 1 | 0 | 0 | 3 | 4 | 0 | 6 | 1 | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 18 |
| tape-operations-notes.docx | 2 | 3 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 3 | 2 | 0 | 0 | 2 | 0 | 0 | 15 |
| retention-schedule-2026-r3.docx | 1 | 0 | 0 | 0 | 0 | 2 | 8 | 1 | 2 | 2 | 0 | 0 | 1 | 0 | 0 | 9 | 26 |
| ECS-annex-hosts-rev6.pdf | 2 | 0 | 4 | 0 | 0 | 0 | 0 | 1 | 2 | 3 | 0 | 0 | 5 | 0 | 0 | 0 | 17 |
| hr-roster-q3.pdf | 4 | 0 | 0 | 0 | 0 | 1 | 2 | 1 | 1 | 1 | 0 | 0 | 3 | 0 | 0 | 0 | 13 |
| audit-scope-letter-fin.pdf | 2 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 2 | 3 | 0 | 0 | 4 | 2 | 0 | 0 | 15 |
| rnd01_cold_listing.pdf | 1 | 2 | 1 | 0 | 5 | 1 | 1 | 1 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 15 |
| vendor-hash-attestation.pdf | 5 | 0 | 0 | 0 | 0 | 3 | 0 | 1 | 3 | 2 | 0 | 0 | 3 | 0 | 0 | 0 | 17 |
| units-bulletin.pdf | 5 | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 3 | 2 | 2 | 0 | 0 | 0 | 0 | 0 | 15 |
| ECS-annex-hosts-rev7.pdf | 3 | 0 | 4 | 0 | 0 | 4 | 8 | 1 | 2 | 3 | 0 | 0 | 3 | 0 | 0 | 1 | 29 |
| journal_eng01_q3.log | 2 | 0 | 7 | 0 | 2 | 0 | 0 | 1 | 0 | 0 | 3 | 0 | 1 | 0 | 1 | 0 | 17 |
| journal_mkt01_q3.log | 2 | 0 | 2 | 0 | 3 | 0 | 0 | 1 | 1 | 0 | 7 | 0 | 1 | 0 | 0 | 0 | 17 |
| journal_fin01_q3.log | 0 | 0 | 3 | 0 | 1 | 0 | 0 | 1 | 0 | 0 | 5 | 4 | 1 | 0 | 1 | 0 | 16 |
| journal_ops01_q3.log | 0 | 0 | 5 | 2 | 0 | 0 | 0 | 1 | 0 | 2 | 1 | 0 | 1 | 0 | 0 | 0 | 12 |
| journal_mkt01_q3_b.log | 5 | 0 | 3 | 0 | 2 | 6 | 0 | 2 | 0 | 2 | 0 | 0 | 6 | 0 | 0 | 180 | 206 |
| inv_eng01_q3_part2.db | 2 | 0 | 1 | 0 | 1 | 2 | 0 | 0 | 1 | 0 | 0 | 2 | 2 | 1 | 0 | 0 | 12 |
| arc01_ltfs_index.db | 7 | 0 | 2 | 0 | 5 | 5 | 2 | 2 | 2 | 2 | 0 | 0 | 2 | 1 | 0 | 244 | 274 |
| principal_legacy.db | 4 | 0 | 0 | 0 | 0 | 1 | 2 | 1 | 2 | 1 | 0 | 0 | 3 | 0 | 0 | 0 | 14 |
| store_index_prior_d.db | 3 | 0 | 0 | 0 | 0 | 3 | 3 | 0 | 2 | 3 | 0 | 0 | 0 | 0 | 2 | 0 | 16 |
| volumes.yaml | 5 | 0 | 0 | 0 | 0 | 2 | 2 | 1 | 2 | 4 | 2 | 0 | 0 | 0 | 0 | 0 | 18 |
| site-policy.yaml | 2 | 0 | 0 | 1 | 2 | 0 | 4 | 1 | 2 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 16 |
| retention_rules_v3.yaml | 2 | 0 | 0 | 0 | 0 | 2 | 3 | 1 | 3 | 2 | 1 | 0 | 0 | 0 | 0 | 0 | 14 |
| site-policy-v2.yaml | 2 | 0 | 0 | 0 | 0 | 1 | 6 | 1 | 2 | 3 | 0 | 0 | 12 | 0 | 0 | 4 | 31 |
| estate-defaults.toml | 5 | 0 | 0 | 1 | 2 | 0 | 3 | 1 | 4 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 18 |
| retention_rules_v4.toml | 3 | 0 | 0 | 0 | 0 | 8 | 5 | 1 | 3 | 3 | 0 | 0 | 7 | 0 | 0 | 2 | 32 |
| retention_overlays.toml | 3 | 0 | 0 | 0 | 0 | 0 | 2 | 1 | 2 | 6 | 1 | 0 | 0 | 0 | 0 | 0 | 15 |
| operator-overrides.ini | 2 | 1 | 0 | 0 | 2 | 0 | 0 | 1 | 4 | 6 | 2 | 0 | 0 | 0 | 0 | 0 | 18 |
| host_aliases.ini | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 3 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 12 |
| service_accounts.ini | 4 | 0 | 0 | 0 | 0 | 2 | 0 | 1 | 2 | 2 | 0 | 0 | 6 | 0 | 0 | 0 | 17 |
| ECS-standard.md | 2 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 1 | 2 | 1 | 0 | 0 | 5 | 0 | 0 | 12 |
| source-register.md | 1 | 0 | 2 | 0 | 0 | 0 | 0 | 1 | 2 | 3 | 0 | 0 | 5 | 0 | 0 | 0 | 14 |
| ops-runbook.md | 2 | 0 | 0 | 0 | 0 | 0 | 3 | 1 | 5 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 17 |
| principal_map_ldap.html | 3 | 0 | 0 | 0 | 0 | 2 | 3 | 1 | 2 | 3 | 0 | 0 | 5 | 0 | 0 | 10 | 29 |
| ext_families_wiki.html | 4 | 0 | 0 | 0 | 1 | 1 | 2 | 1 | 2 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 14 |
| holds_portal_export.html | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 3 | 9 | 0 | 0 | 0 | 0 | 0 | 18 |
| inv_eng02_q3.txt | 6 | 0 | 0 | 0 | 1 | 2 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 2 | 0 | 12 |
| arc01_tape_catalog.txt | 3 | 0 | 1 | 0 | 4 | 1 | 0 | 1 | 0 | 2 | 0 | 0 | 1 | 1 | 1 | 0 | 15 |
| principal_mainframe_ids.txt | 4 | 0 | 0 | 0 | 0 | 2 | 2 | 1 | 2 | 2 | 0 | 0 | 5 | 0 | 0 | 0 | 18 |
| journal_leg01_notifications.mbox | 2 | 0 | 4 | 0 | 4 | 0 | 0 | 1 | 0 | 0 | 2 | 0 | 1 | 0 | 0 | 0 | 14 |
| legal_hold_windows.ics | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 2 | 3 | 3 | 0 | 0 | 0 | 0 | 0 | 12 |
| tool.zip | 3 | 0 | 0 | 0 | 0 | 0 | 3 | 1 | 2 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 12 |

Total traps 2747 (in-scope 1306, decoys 1441). T16 traps are graded through the decoy checks, whose populations contain every T16 record.

## Root cause

**Authority is declared, not inferred.** Run modes are self-declared in each export; scope overrides, ratifications and tickets live in other files (ECS 3).

**Every fact has exactly one authoritative home.** Each reference table is a partition: aliases A-F, tokens per namespace, crosswalks per volume, batches A-D, holds A-E. Mirrors in decoys agree 95% so that only the documented rule separates them.

**Representation is not semantics.** Units, numerals, encodings, header layouts and timestamp forms vary per source and are undone by documented dialect rules (source-register.md Appendix S).

**State is cross-file.** Snapshots come from authority runs, journals replay against snapshots in sequence order, entry ids continue from the previous manifest, and the ledger must reconcile with it.

**Red lines.** No hard-coded values, no reading of /app/data from the delivered tool, no nondeterminism, no modification of the shipped inputs.

## Solution shape

1. Extract tool.zip and replace estatectl/estatectl.py with the full ECS implementation.
2. Parse all 100 files with format readers that follow every drift, escape, encoding and control convention.
3. Resolve tickets, then configuration per profile (window, locks, overrides, revocations).
4. Build reference indices: aliases with serials, case-sensitive subtrees, token maps, merges, zones, batches, families, rules, holds, crosswalks, store, voids, errata, authority.
5. Resolve every record (authority, voids, not-a-file, window, path, size, digest, owner) and assign the first applicable reason.
6. Resolve duplicates, replay journals in sequence order, collapse hard links, classify, purge or archive.
7. Assign entry ids from the prior manifest, compute the ledger and the control chain, write the five outputs, then export-report and package tool.zip.

## Ordered plan

1. Read ECS-standard.md and source-register.md end to end (earns r4, r5).
2. Inventory the 100 files and walk the control chain from the prior manifest's closing_ctl_id (earns r2).
3. Probe each export dialect on raw bytes before writing a reader (earns r5).
4. Decide authority for every look-alike file from the cited rules, not from names or dates (earns r3).
5. Implement the pipeline incrementally as named functions that report or classify every caught error, rerunning and diffing outputs after each change (earns r6, r10).
6. Check opening - retired + new = closing, CHECKPOINT counts and row counts before finishing (earns r2).

### Trap loops

| id | entry | reinforcement | tell (file) | exit | graded impact | chains to | best-practice entry | decoy-anchored | survives sample check |
|---|---|---|---|---|---|---|---|---|---|
| L01 | Trust the newest FIN01 export inv_fin01_q3_r2.csv because its exported_utc is later and its sizes are filled in. | its sizes fill the unknown sizes of the parquet export; its later batch capture wins every duplicate | authority_matrix.xlsx scope sheet (only close/ prefixes are overridden) and ECS 3.1 | ECS 3.1 run_mode, 3.2 scope overrides | decoy:inv_fin01_q3_r2.csv, C1 | L02 | yes | yes | no |
| L02 | Having demoted inv_fin01_q3_r2.csv, drop every one of its rows, including the overridden subtrees. | the FIN01 counts now match the parquet row count; no record is listed twice | authority_matrix.xlsx override rows with approved tickets in change_tickets.csv | ECS 3.2 | decoy:inv_fin01_q3_r2.csv, C1, family:T14 | - | no | yes | no |
| L03 | Resolve duplicate canonical paths by the later file mtime. | fresher sizes win; journals later modify the same files so the choice looks consistent | export_batches_a.csv / export_batches_b.tsv captured_utc | ECS 6.4 | family:T11, C3 | - | yes | no | no |
| L04 | Lower-case case-insensitive paths with full Unicode case folding. | Straße and strasse collapse into one entry; duplicate counts drop and look tidier | estate_manifest_q2.parquet carries straße keys that only simple lower-casing reproduces | ECS 5.3 | family:T1, C2 | L05 | yes | no | no |
| L05 | Lower-case every path on an NTFS volume. | Makefile/makefile style pairs collapse; ENG02 counts look plausible | case_sensitive_dirs.csv and case_sensitive_dirs_leg01.xml | ECS 5.3 case-sensitive subtrees | family:T1, C2 | L06 | yes | no | no |
| L06 | Keep NFD and NFC spellings of the same name apart on ext4 because the file system is byte-exact. | both files exist physically; their contents differ, so dedup by digest keeps both | ECS 5.3 (NFC before comparison) with duplicate resolution by batch capture | ECS 5.3, 6.4 | family:T1, C3 | - | yes | no | no |
| L07 | Decode S3 keys with form decoding (+ becomes a space). | keys look human; journal keys decode the same way | ECS 5.3 (+ is a literal plus) and the OBJ01 keys in estate_manifest_q2.parquet | ECS 5.3 | C2 | - | yes | no | no |
| L08 | Apply retention rules first-match. | the global *.tmp and *.log rules classify most files; purge counts look sane | retention_overlays.toml keep/ rules that only matter under last-match | ECS 7.3 | family:T7, C8 | L09 | yes | no | yes |
| L09 | Use retention_rules_v4.toml because it is labelled FINAL and newer. | its classes agree with v3 for 95% of rules | authority_matrix.xlsx ratification rows (v4 not approved) | ECS 7.3 | decoy:retention_rules_v4.toml, C8 | L10 | no | yes | no |
| L10 | Ignore retention_rules_v4.toml completely. | v3 alone still classifies every entry | approved withdrawal tickets in change_tickets.csv | ECS 7.3 withdrawals | decoy:retention_rules_v4.toml, family:T6 | - | no | yes | no |
| L11 | Let the last configuration layer win for every key. | store.block_size becomes 128 KiB; store bytes stay plausible | site-policy.yaml final=true rows | ECS 2.2 locks | C9, C6, family:T7 | L12 | yes | no | no |
| L12 | Apply every operator override. | overrides all have ticket ids and look approved | change_tickets.csv states and decided_utc | ECS 2.2, 2.4 | C9, family:T11 | L13 | yes | no | no |
| L13 | Treat a ticket as approved when any revision is APPROVED. | most tickets have a single revision | change_tickets.csv highest revision WITHDRAWN/REJECTED rows | ECS 2.4 | family:T7, C9, C1 | L14 | yes | no | no |
| L14 | Ignore the decided_utc of a ticket when it is missing. | the sentinel looks like a formatting gap | ECS 2.4 sentinel 0000-00-00T00:00:00Z | ECS 2.4 | family:T5 | - | no | no | no |
| L15 | Read site-policy-v2.yaml as the current layer 20. | it is newer and agrees with site-policy.yaml on 95% of keys | authority_matrix.xlsx ratification (site-policy v2 rejected) and its status: proposed | ECS 2.2 | decoy:site-policy-v2.yaml, C9 | L16 | no | yes | no |
| L16 | Drop site-policy-v2.yaml entirely. | layer 20 alone resolves every key | ECS 2.2: revocations are published only in that file | ECS 2.2 revocations | decoy:site-policy-v2.yaml, family:T6 | - | no | yes | no |
| L17 | Read local wall-clock times as UTC when the zone id is unknown to tzdata. | mtimes stay in the right day | tz_transitions_a.tsv / tz_transitions_b.parquet and the host registers | ECS 4.3 | family:T3, C4 | L18 | yes | no | no |
| L18 | Resolve a fall-back overlap with the first occurrence (fold=0). | Python datetime does this by default | ECS 4.3 (smaller offset, standard time) | ECS 4.3 | family:T3, C4 | - | yes | no | yes |
| L19 | Convert every Excel serial with the 1900 system. | HR01 sheets convert correctly | inv_mkt01_supplement.xlsx workbookPr date1904=1 | ECS 4.2 | family:T3, C4 | L20 | yes | no | no |
| L20 | Keep Excel serials 0 and 60 as 1899-12-30 / 1900-02-28 timestamps. | they are valid serials for Excel | ECS 4.2 (not captured; use batch captured_utc) | ECS 4.2 | family:T3, family:T5 | L21 | yes | no | no |
| L21 | Truncate Excel fractions to whole seconds. | most serials are a hair above the second | ECS 4.2 half-even rounding of the fraction | ECS 4.2 | family:T12, C4 | - | yes | no | yes |
| L22 | Round sub-second epoch timestamps to the nearest second. | rounding error is under a second | events at window.end - 1 with .999 fractions (DEFERRED counts) | ECS 4.2 floor | family:T12, family:T11 | - | yes | no | yes |
| L23 | Skip ECS-annex-hosts-rev7.pdf entirely because it was withdrawn. | rev6 already gives every host zone | authority_matrix.xlsx ratification rev7-appendix-D (approved) | ECS 4.4, rev7 Appendix D | decoy:ECS-annex-hosts-rev7.pdf, family:T3 | - | no | yes | no |
| L24 | Use the rev7 host table because it is the newer revision. | rev7 agrees with rev6 for 95% of hosts | ECS-annex-hosts-rev7.pdf cover text and ratification rows | ECS 4.3 | decoy:ECS-annex-hosts-rev7.pdf, C4 | L23 | no | yes | no |
| L25 | Parse unit sizes with float(). | small sizes convert exactly | sizes above 2**53 bytes and ECS 6.1 exact decimals | ECS 6.1 | family:T12, C3 | L26 | yes | no | no |
| L26 | Read sizes of unit-dialect exports as bytes. | values look like plausible byte counts | export batch registers (units per batch) | ECS 6.1 | family:T2, C3 | L27 | yes | no | no |
| L27 | Take the unit from the batch's own register. | every batch is found in one register | units-bulletin.pdf rows with source=correction | ECS 6.1 | family:T14, family:T2 | - | no | no | no |
| L28 | Round OPS01 KB values half-up. | only exact .5 cases differ | ECS 6.1 half-even | ECS 6.1 | family:T12 | - | yes | no | yes |
| L29 | Parse 1.234,5675 as 1.234 kilobytes. | values stay positive and small | source-register.md Appendix S (de-DE) | ECS 6.1 | family:T4 | - | yes | no | no |
| L30 | Keep -1, 9999, ? and ******* as literal sizes. | they parse as integers | source-register.md sentinel table | ECS 6.1 | family:T5, C3 | - | yes | no | no |
| L31 | Use arc01_ltfs_index.db sizes and digests for ARC01 because they are plain bytes and SHA-256. | they agree with the tape catalog for 95% of files | arc01_ltfs_index.db run_mode ltfs-shadow; ECS 3.1 | ECS 3.1, 6.6 | decoy:arc01_ltfs_index.db | L32 | yes | yes | no |
| L32 | Ignore arc01_ltfs_index.db entirely. | the tape catalog lists every ARC01 file | ECS 6.6 (ARC01 hard-link identity comes only from the LTFS index) | ECS 6.6 | decoy:arc01_ltfs_index.db, C3 | - | no | yes | no |
| L33 | Deduplicate manifest entries by content digest. | duplicate content disappears; store bytes look lower | ECS 6.6 (only hard links collapse) and 6.5 (store dedup) | ECS 6.5, 6.6 | C3, C6 | - | yes | no | no |
| L34 | Use hash_index_master.parquet for every legacy digest because it is the most complete index. | it agrees with the partition crosswalks for 95% of digests | ECS 6.2 partition per volume | ECS 6.2 | decoy:hash_index_master.parquet | L35 | yes | yes | no |
| L35 | Drop hash_index_master.parquet. | every partition crosswalk resolves its own volume | ECS 6.2: ARC01 rows exist only in that index | ECS 6.2 | decoy:hash_index_master.parquet, C6 | - | no | yes | no |
| L36 | Take owners from principal_directory.xlsx because it lists every principal in one sheet. | accounts match the register for 95% of principals | its description snapshot_of=2025-03-31 and ECS 5.4 | ECS 5.4 | decoy:principal_directory.xlsx, C7 | L37 | yes | yes | no |
| L37 | Ignore principal_directory.xlsx entirely. | the SID sheet resolves most SIDs | ECS 5.4: SID history exists only in its sid_history sheet | ECS 5.4 | decoy:principal_directory.xlsx, family:T13 | - | no | yes | no |
| L38 | Apply every merge row regardless of revision and date. | merged accounts look consolidated | principal_merges.csv / ops-runbook.md Appendix M revisions and effective dates | ECS 5.5 | family:T13, family:T11, C7 | - | yes | no | no |
| L39 | Use principal_map_ldap.html for every legacy domain. | its copy of the other domains agrees for 95% of logins | its ARCHIVED banner and ECS 5.4 (OLDCORP only) | ECS 5.4 | decoy:principal_map_ldap.html | L40 | no | yes | no |
| L40 | Ignore principal_map_ldap.html because it is archived. | other maps resolve most owners | ECS 5.4: the OLDCORP map exists only there | ECS 5.4 | decoy:principal_map_ldap.html, C7 | - | no | yes | no |
| L41 | Apply void_register_q3_r2.xml as the current void register. | its rows agree with the CSV register for 95% of voids | its status=draft root attribute and ECS 3.4 | ECS 3.4 | decoy:void_register_q3_r2.xml | L42 | no | yes | no |
| L42 | Ignore void_register_q3_r2.xml entirely. | the CSV and JSONL registers decide every void | ECS 3.4: reinstatements are published only there | ECS 3.4 | decoy:void_register_q3_r2.xml, family:T6 | - | no | yes | no |
| L43 | Apply errata_register_q3_r2.tsv revisions because they are higher. | most rows agree with register A | its status=preview header and ECS 3.5 | ECS 3.5 | decoy:errata_register_q3_r2.tsv | L44 | no | yes | no |
| L44 | Ignore errata_register_q3_r2.tsv entirely. | registers A, B and C decide every erratum | ECS 3.5: withdrawals are published only there | ECS 3.5 | decoy:errata_register_q3_r2.tsv, family:T6 | - | no | yes | no |
| L45 | Replay journal_mkt01_q3_b.log as the MKT01 journal because it has more events. | it agrees with the primary journal for 95% of events | its role=replica header and ops-runbook.md gap | ECS 3.3 | decoy:journal_mkt01_q3_b.log, C5 | L46 | no | yes | no |
| L46 | Ignore journal_mkt01_q3_b.log. | the primary journal applies cleanly | the primary journal's sequence gap and the replica CHECKPOINT counts | ops-runbook.md journal gap | decoy:journal_mkt01_q3_b.log, family:T14 | - | no | yes | no |
| L47 | Replay journal events in timestamp order. | timestamps are mostly increasing | ECS 8 (sequence order) | ECS 8 | family:T3, C5 | - | yes | no | no |
| L48 | Apply events stamped exactly window.end. | an inclusive end looks natural | ECS 8 half-open window | ECS 8 | family:T11 | - | yes | no | no |
| L49 | Carry digests and sizes forward from estate_manifest_q2.parquet. | they agree with current values for 95% of entries | journal MODIFY events and ECS 10.1 | ECS 10.1 | decoy:estate_manifest_q2.parquet | L50 | yes | yes | yes |
| L50 | Ignore estate_manifest_q2.parquet and number entries from 1. | ids are dense and sorted | next_entry_id metadata and ECS 10.1/10.2 | ECS 10.1 | decoy:estate_manifest_q2.parquet, C10 | - | no | yes | no |
| L51 | Trust volumes_cmdb.json fs_type for RND01. | it agrees with volumes.yaml for every other volume | vol.RND01.case in site-policy.yaml and its authoritative_for list | ECS 5.3 | decoy:volumes_cmdb.json | L52 | no | yes | no |
| L52 | Ignore volumes_cmdb.json. | tables A, B, E and F resolve their roots | ECS 5.2: serial:... volumes of tables C and D resolve only through it | ECS 5.2 | decoy:volumes_cmdb.json, family:T13 | - | no | yes | no |
| L53 | Apply every Annex F correction of retention-schedule-2026-r3.docx. | corrections look like errata | ext_families_a.tsv pending flags | retention-schedule-2026-r3.docx Annex F | decoy:retention-schedule-2026-r3.docx, family:T13 | L54 | no | yes | no |
| L54 | Use the r3 class ages because r3 is newer. | only one class age differs | DRAFT status and ratification rows | ECS 7.1 | decoy:retention-schedule-2026-r3.docx | - | no | yes | no |
| L55 | Ignore inv_eng01_q3_deep.jsonl. | the ENG01 csv and sqlite exports cover the volume | authority_matrix.xlsx overrides for its subtrees | ECS 3.2 | decoy:inv_eng01_q3_deep.jsonl, C1 | - | no | yes | no |
| L56 | Resolve alias roots by the first matching row. | most roots are not nested | nested cad roots in the alias tables | ECS 5.2 longest root | family:T11, C2 | L57 | yes | no | no |
| L57 | Fall back to a shorter root when the longest root is retired. | the shorter root maps to the same volume | ECS 5.2 (no fallback) | ECS 5.2 | family:T6, C2 | - | yes | no | no |
| L58 | Treat a hold as active only when it covers window.end. | most holds are open-ended | ECS 7.5 overlap rule with window.start | ECS 7.5 | family:T11, C8 | L59 | yes | no | no |
| L59 | Match hold prefixes as plain string prefixes. | prefixes end on directory names | ECS 7.5 whole segments | ECS 7.5 | family:T11 | - | yes | no | no |
| L60 | Purge expired temp files on ARC01 like everywhere else. | class ages are uniform | retention-schedule-2026-r2.docx footnote 1 | schedule footnote | family:T14, C8 | - | yes | no | no |

60 loops; 27 chain into another loop; 34 are entered by the textbook practice; 29 are decoy-anchored; 6 survive checking against the only sample output shipped (the previous manifest), which carries no class, action or timestamp and agrees with both paths on unchanged entries.

### Estimated expert time

- Reading the standard, register, runbook and 30 policy documents: 5 hours
- Writing and debugging readers for 20 formats with drift, escapes and encodings: 8 hours
- Tickets, configuration layers and authority: 3 hours
- Paths, owners, zones, sizes, digests: 6 hours
- Journals, duplicates, hard links, retention, holds: 5 hours
- Entry ids, ledger, chain and reconciliation against invariants: 3 hours
- Falsifying and fixing trap loops found through invariants: 4 hours
- Total: about 34 hours, 4 working days (task.toml expert estimate 2040 minutes)

## Pitfalls

- Trusting the newest export or revision: fails the decoy checks and `concept_c1_authority`.
- Casefolding or lower-casing all NTFS paths: fails `family_t1_near_duplicate_keys` and `concept_c2_paths`.
- First-match retention: fails `family_t7_superseded_revisions` and `concept_c8_retention`.
- Float sizes and half-up rounding: fail `family_t12_precision_and_rounding`.
- Python fold=0 for DST overlaps or tzdata zones: fail `family_t3_time_zones_and_epochs`.
- Timestamp-ordered journals: fail `concept_c5_journals`.
- Ignoring any decoy: every decoy carries a fact that exists nowhere else, so its decoy check fails.
- Emitting zero-count reasons in `exceptions` is harmless: the comparison ignores reasons whose count is 0.
- Numbering entries from 1: fails `concept_c10_catalog`, which owns every entry id.
- Voiding every id in audit-scope-letter-fin.pdf: the letter applies to finance volumes only, so its non-finance id must stay an entry; fails `concept_c1_authority` and `concept_c10_catalog`.

## Provenance

```yaml
uuid: 8764bfdd-69b5-57a0-bc6a-db095fe071db
instance_id: 8764bfdd-69b5-57a0-bc6a-db095fe071db
task_name: terminal-bench/8764bfdd-69b5-57a0-bc6a-db095fe071db
repaired_estatectl_sha256: c37af837b3f1dd87e98ab32f3ce014508219c37dc5df770230c4afb350203a34
solve_py_sha256: 96cbeff9e5c884b8babd39ff085537cba06c8fa1411c5fd7dcef220dcf4eb073
language: python
eval_seed_location: tests/test_output.py
```
