# TRUTH.md - 9cc598a9-033b-5cc9-91ee-a9ef941a3d3a

## Defect

`/app/data/project.zip` holds `restorekit` 2.3.1, a Python package that plans a point-in-time restore of one file share from a restore feed. It does not install on Python 3.12, its command line does not match the contract, and the rules it implements contradict the approved restore specification in more than thirty places. The agent must repair it so that `python -m restorekit restore --feed DIR --out DIR` reproduces the restore the rules give, exactly, for the shipped feed (share FS-02, restore point 2026-10-30T00:30:00Z) and for a hidden feed of another share. The feed holds 99 files plus the project archive, in twenty formats, 15 of them non-authoritative copies whose authority status is only decidable from other files.

Defects, each with the check it defeats. The deterministic channel settles a whole plan per feed rather than a cell at a time, so almost every defect is caught by a plan equality: `visible_plan_exact` reads the plan for the shipped feed, and `eval_plan_exact`, `extra_plan_7199369_exact`, `extra_plan_42133777_exact` and `extra_plan_121212121_exact` read the plans for four feeds regenerated at grade time. Below, the four hidden checks are those four, and the five plan checks are those four together with `visible_plan_exact`. A rule bug corrupts the same cell on every feed, so in practice the equalities fail together; the attribution names the feed in which the situation itself is documented.

1. (focal) `pyproject.toml` declares `requires-python = ">=3.8,<3.12"`, finds packages under a non-existent `lib/` directory and depends on `python-magic` and `pytz`, which the runtime does not have. `package_installs`.
2. (focal) `values.py` imports `distutils.util.strtobool`, removed in Python 3.12, so the package and its own suite fail to import. `package_shipped_tests_pass`.
3. (focal) `feed.py` imports libmagic and dispatches on file extensions, so `.log.1` files, renamed feeds and the zip archive are misread; the contract requires content identification. `negative_filename_dependent_behaviour`, the four hidden checks.
4. (focal) The command line is `plan --catalog --output` instead of `restore --feed --out`. Every one of the five plan checks.
5. (focal) `report.py` writes CRLF CSVs without the `#custody=` trailer, and `custody()` hashes only ORIGINAL and ISSUED files and does not substitute the CORRECTED copy's `source_custody` for part 07's `N/A`. The five plan checks: a missing trailer defeats the parse every plan equality needs.
6. (focal) Chain selection uses job queued times, ignores the synthetic full as a base, ignores catalog-check status overrides and the storage array's actual maintenance windows, and closes windows at their end. The five plan checks.
7. (focal) Catalog assembly treats RESEND and CORRECTED parts as originals, applies void-targeted and uncommitted entries, and takes catalog errata whatever their status or revision. The five plan checks.
8. (focal) Media resolution ignores repack, LTO-6, copy-job completion and the rerun scope; the dashboard overrides every vault. The five plan checks.
9. (drift) Exclusions use `fnmatch`, where `*` crosses `/` and directory patterns do not exist; the dialect carried forward from revision 4.1 section 7 differs. The five plan checks.
10. (drift) Display spelling follows the latest entry, the textbook choice; the path conventions keep the spelling under which a component was created or last renamed. The five plan checks.
11. (drift) A FAILED incremental is treated as breaking the chain; the specification rebases the next incremental on the last completed set, and only a crash-inconsistent completed set breaks it. In the shipped feed every FAILED or CANCELLED set after the anchor follows the crash break, so the hidden feed carries the case (item 34). The four hidden checks.
12. (drift) The newest-looking document wins: revision 4.3 is a draft and revision 9 of the exclusion catalogue is not yet in force; the document control register decides. The five plan checks.
13. (drift) `read_gib` rounds the binary float quotient with `round`, which disagrees with half to even on the exact decimal quotient whenever the float lands just off a half; section 11.4 requires the exact quotient. The five plan checks.
14. (drift) The mode keeps only the permission triplets; section 9.1 keeps the sticky bit and clears set-user-ID and set-group-ID. The five plan checks.
15. (drift) Allocation ignores resident files and charges every hard-link member; section 10 allocates 0 for both. The five plan checks.
16. (trap) The incremental on the fall-back night has a server-local snapshot in the repeated hour; the first occurrence is meant. `visible_plan_exact`.
17. (trap) One set's snapshot equals the restore point (inclusive), and a maintenance window ends exactly at it (end excluded): the set is CHAIN_BROKEN, not AFTER_RP or CRASH_INCONSISTENT. `visible_plan_exact`.
18. (trap) The rotated server log declares a one-day gap; the console mirror is of record only inside it, giving the snapshot of set BS-57758. `visible_plan_exact`.
19. (trap) The ingest client's host file system is FAT32 (CMDB only): its 90 restored files carry local wall-clock digits in every time notation. `visible_plan_exact`.
20. (trap) Windows raw paths carry trailing dots and spaces, `x\..` detours, mixed separators and `\\?\` and UNC roots; macOS paths are NFD; TSV parts escape every backslash. `visible_plan_exact`.
21. (trap) Sizes use the control-block locale (`de_DE` dots, `fr_FR` U+202F), `size_kib` columns carry exact KiB fractions and `#encoding latin-1` sections switch encodings mid-file. `visible_plan_exact`.
22. (trap) Workbooks with `date1904` shift Excel serials by 1462 days. `visible_plan_exact`.
23. (trap) Sentinels: FILETIME 0, epoch 0, ms -1, null Parquet timestamps, `0000-00-00`, owners `N/A`/`-`/`null`; 18 restored rows depend on them. `visible_plan_exact`.
24. (trap) Set identifiers appear as `bs-41234`, `BS-41234 `, `BS_41234`, unpadded and with Cyrillic homoglyphs; only the identifier rows of the fold table apply. `visible_plan_exact`.
25. (trap) 36 restored files are owned by SIDs of a domain the identity map does not carry; only the directory export resolves them. `visible_plan_exact`.
26. (trap) Quarantine: the scan of record depends on each container's creation time against the engine cutover; withdrawn signatures and PUA verdicts never quarantine; 9 files roll back and 7 are quarantined. `visible_plan_exact`.
27. (trap) Part 18 lost its tail (9 share entries); only the RESEND part holds them, and its overlapping rows carry altered hashes. `visible_plan_exact`.
28. (trap) Pattern `*.hex` was withdrawn by the revision-9 withdrawal register with an effective date before the restore point, although revision 8 is the catalogue in force. `visible_plan_exact`.
29. (trap) Set BS-70844 failed after the restore point: AFTER_RP comes before FAILED in section 5.6. `visible_plan_exact` and the four hidden checks.
30. (trap) The CANCELLED set BS-46554 lies inside a confirmed SNAPSHOT-CONSISTENCY window: CANCELLED comes before CRASH_INCONSISTENT. `visible_plan_exact` and the four hidden checks.
31. (trap) The completed set BS-49960, before the base, lies inside a confirmed window: CRASH_INCONSISTENT comes before BEFORE_BASE, and the set no longer supplies rollback candidates. `visible_plan_exact` and the four hidden checks.
32. (trap) Hold RM-20517 (DESTROY, in force) covers `/Design/Archive`, which is outside the include prefixes: OUT_OF_SCOPE comes before DISPOSED. `visible_plan_exact` and the four hidden checks.
33. (trap) Pattern EX-1124 matches the link `draft link41`, whose target leaves the share: EXCLUDED_PATTERN comes before SYMLINK_ESCAPE. `visible_plan_exact` and the four hidden checks.
34. (trap, hidden feed) A FAILED and a CANCELLED incremental lie between the anchor differential and the next applied incremental: neither breaks the chain, the incremental after them is applied and each is skipped with its own status. The four hidden checks.
35. (trap, hidden feed) A container with no usable copy (first-audit MISMATCH on copy 1, failed copy jobs for copies 2 and 3) holds the infected versions at the effective point of two files: the one with no clean earlier entry is QUARANTINED rather than UNRECOVERABLE, and the other rolls back to a clean earlier version in another container and is restored. The four hidden checks.
36. (trap, hidden feed) A CANCELLED incremental snapshots in the same second as a completed incremental skipped as BEFORE_BASE; it was queued later, so its set identifier is higher, and it ended earlier. The skipped list orders the two by snapshot, then set identifier, so the completed set comes first; ordering the tie by status, skip reason or end time reverses them. The four hidden checks.
37. (trap, hidden feed) A second DESTROY hold in force covers one file under the in-force hold on a Build directory, with a higher hold identifier, and is listed first in the request. The file is DISPOSED with the lowest hold identifier, the broader hold; taking the first listed hold, the most specific prefix or the highest identifier gives the other one. The four hidden checks.

The hidden feed carries the same five precedence situations, with its own sets, hold, link and pattern, and the four situations of items 34 to 37, which the shipped feed does not contain. All four regenerated feeds are built at the eval tier, so each of them carries items 34 to 37.

The catalog errata repeat a few APPROVED corrections in the same revision with near-duplicate container values (`CT-0000029X`, `CT-0000141-DR`). Section 6.4 makes a value not written in canonical form malformed, so exactly one correction per entry and field applies whatever the row order. In both feeds the affected entries reach no graded row, so this settles an ambiguity and is not a graded trap.

The reference implementation is Python 3.12 (`solution/solve.py` holds the repaired modules; `solution/solve.sh` extracts the shipped project, applies them, runs the shipped suite, packs `/app/out/package.zip` and lets the package write the five deliverables). Grading has two channels: deterministic checks in `tests/test_output.py` and judged criteria in `tests/judge.toml`; `tests/reward.toml` gives each half of the reward.

Out of bounds: hardcoding answers of the shipped feed (`negative_hardcoded_sample_answers`, -5), output that changes when only the feed file names change (`negative_filename_dependent_behaviour`, -5), output that changes when `/app/data` holds another restore feed (`negative_reads_training_corpus_at_runtime`, -5) and non-deterministic output (`negative_nondeterministic_output`, -3). The two middle negatives only fire for a package whose two isolated runs agree, so nondeterminism is penalised once.

## Load-bearing work

Graded artifacts:

- `/app/out/package.zip`
- `/app/out/restore_manifest.csv`
- `/app/out/exclusions.csv`
- `/app/out/media_pull_list.csv`
- `/app/out/restore_chain.json`
- `/app/out/reconciliation.json`

Content contract: `package.zip` must install offline (`pip install --no-index --no-build-isolation --no-deps`), keep the shipped `tests/` byte-identical and passing, and run as `python -m restorekit restore --feed DIR --out DIR`. The five deliverables follow specification section 11: `restore_manifest.csv` (14 columns), `exclusions.csv` (4), `media_pull_list.csv` (6), each with the `#custody=<digest> rows=<n>` trailer, and the two JSON objects with their fixed key order and integer counts.

Shipped restore: chain BS-56626 (SYNTH), BS-65987 (DIFF), BS-66924 (INCR), BS-67843 (INCR); effective point 2026-10-26T22:46:52Z; 3201 restored objects, 1447 exclusions (DISPOSED 26, EXCLUDED_PATTERN 787, OUT_OF_SCOPE 538, QUARANTINED 7, SYMLINK_ESCAPE 11, UNRECOVERABLE 78), 50 hard-link groups, 31 media to pull, copies used {'1': 2549, '2': 562, '3': 54}.

### Concepts (each load-bearing)

| id | concept | checks that need it | expert-only variant |
|---|---|---|---|
| C1 | Content-based file identification and control blocks: magic bytes, control-block grammar per format, record counts, the chain-of-custody digest. | the five plan checks, `negative_filename_dependent_behaviour` | - |
| C2 | Backup set chain reconstruction: full, synthetic full, differential and incremental sets, snapshot versus job times, rebasing after failures, chain breaks. | the five plan checks | expert-only: a synthetic full's snapshot is its consolidated set's snapshot; failed sets rebase while crash-inconsistent completed sets break |
| C3 | Catalog journal replay: ordered D/F/H/L/W/R/X entries across parts, voids, uncommitted entries, errata, resends. | the five plan checks | - |
| C4 | Path canonicalisation and identity: roots, separators, trailing dots, NFC, case-insensitive identity with create-or-rename spelling. | the five plan checks | expert-only: spelling is fixed at creation or rename, not by the latest entry |
| C5 | Pattern exclusion: glob dialect with component-bound wildcards, `**` and directory patterns, catalogue revisions and withdrawals. | the five plan checks | expert-only: the dialect is not fnmatch |
| C6 | File metadata normalisation: FILETIME, epoch, ms, Excel 1900/1904, local wall times with DST, FAT local time, modes, owners at a point in time. | the five plan checks | expert-only: FAT volumes store local time; set-ID bits are cleared on restore |
| C7 | Allocation accounting: cluster rounding by size tier, resident files, hard-link groups. | the five plan checks | - |
| C8 | Media and copy resolution: containers, repack, copy usability, vault location over time, pull ordering. | the five plan checks | - |
| C9 | Content integrity and quarantine: scan of record by container creation, signature withdrawals, rollback to the latest clean version. | the five plan checks | - |
| C10 | Build repair: src-layout packaging, Python 3.12 removals, offline dependencies, preserved test suite. | package_installs, package_shipped_tests_pass | - |

Interaction: C1 decides which files are of record, which feeds C2 (which sets exist and when), whose chain decides which catalog entries C3 replays; C4 turns those entries into identities whose final paths C5 matches; C6 to C9 then act on the versions C3 left at the effective point, and C9's rollback reaches back into sets C2 skipped as BEFORE_BASE or SUPERSEDED_BY_DIFF.

### File inventory

Exactly 100 files: 99 feed files and the project archive; 15 decoys and 85 in-scope files; 20 file types. Records are the control-block counts (the archive: its 5,400 glob conformance cases).

| file | type | records | role | stream part status | unique contribution | depends on | depended on by |
|---|---|---|---|---|---|---|---|
| catalog_part_01.json | json | 5346 | in-scope | CAT 01 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_02.jsonl | jsonl | 5260 | in-scope | CAT 02 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_03.jsonl | jsonl | 5065 | in-scope | CAT 03 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_04.txt | txt | 5146 | in-scope | CAT 04 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_05.xml | xml | 5470 | in-scope | CAT 05 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_06.parquet | parquet | 5236 | in-scope | CAT 06 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_07.csv | csv | 5513 | in-scope | CAT 07 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_08.jsonl | jsonl | 5161 | in-scope | CAT 08 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_09.tsv | tsv | 5236 | in-scope | CAT 09 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_10.tsv | tsv | 5406 | in-scope | CAT 10 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_11.csv | csv | 5201 | in-scope | CAT 11 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_12.csv | csv | 5396 | in-scope | CAT 12 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_13.xml | xml | 5231 | in-scope | CAT 13 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_14.txt | txt | 5185 | in-scope | CAT 14 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_15.json | json | 5099 | in-scope | CAT 15 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_16.json | json | 5216 | in-scope | CAT 16 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_17.csv | csv | 5257 | in-scope | CAT 17 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_18.csv | csv | 5564 | in-scope | CAT 18 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_19.xlsx | xlsx | 5618 | in-scope | CAT 19 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_20.xlsx | xlsx | 5542 | in-scope | CAT 20 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_21.xml | xml | 5685 | in-scope | CAT 21 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_22.csv | csv | 5433 | in-scope | CAT 22 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_23.tsv | tsv | 5198 | in-scope | CAT 23 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_24.xml | xml | 5355 | in-scope | CAT 24 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_25.csv | csv | 5344 | in-scope | CAT 25 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_26.xml | xml | 5477 | in-scope | CAT 26 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_27.txt | txt | 5173 | in-scope | CAT 27 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_28.parquet | parquet | 5567 | in-scope | CAT 28 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_29.tsv | tsv | 5371 | in-scope | CAT 29 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_30.tsv | tsv | 5360 | in-scope | CAT 30 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_31.jsonl | jsonl | 5359 | in-scope | CAT 31 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_32.json | json | 5606 | in-scope | CAT 32 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_33.csv | csv | 5132 | in-scope | CAT 33 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_34.xlsx | xlsx | 5630 | in-scope | CAT 34 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_35.json | json | 5497 | in-scope | CAT 35 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_36.xlsx | xlsx | 5128 | in-scope | CAT 36 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_37.csv | csv | 5275 | in-scope | CAT 37 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_38.json | json | 5655 | in-scope | CAT 38 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_39.csv | csv | 5106 | in-scope | CAT 39 ORIGINAL | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_18_tail.jsonl | jsonl | 5564 | decoy | CAT 18 RESEND | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| catalog_part_07_fixed.csv | csv | 5513 | decoy | CAT 07 CORRECTED | the catalog entries of its slice of the share's sets (entries exist in no other part) | ERR, FMTGUIDE, HOST, JOB, PATHCONV, PROJECT, README, ROOT | 6 files |
| job_history_2026_p1.csv | csv | 5158 | in-scope | JOB 01 ORIGINAL | the job history rows (set type, job status, consolidates, server) of its time range | JOBDEF, LOG, PROJECT, README, SPEC, SRV | 48 files |
| job_history_2026_p2.tsv | tsv | 5158 | in-scope | JOB 02 ORIGINAL | the job history rows (set type, job status, consolidates, server) of its time range | JOBDEF, LOG, PROJECT, README, SPEC, SRV | 48 files |
| job_history_2026_p3.tsv | tsv | 5159 | in-scope | JOB 03 ORIGINAL | the job history rows (set type, job status, consolidates, server) of its time range | JOBDEF, LOG, PROJECT, README, SPEC, SRV | 48 files |
| job_history_summary.xlsx | xlsx | 15480 | decoy | JOB 00 REPORTING | the job history rows (set type, job status, consolidates, server) of its time range | JOBDEF, LOG, PROJECT, README, SPEC, SRV | 48 files |
| bkp-nyc02.log | log | 5399 | in-scope | LOG 01 ORIGINAL | snapshot lines and catalog-check status changes of the sets its server ran in its window | AUTH, JOB, PROJECT, README, SRV | 7 files |
| bkp-ber01.log.1 | log | 5186 | in-scope | LOG 02 ORIGINAL | snapshot lines and catalog-check status changes of the sets its server ran in its window | AUTH, JOB, PROJECT, README, SRV | 7 files |
| bkp-ber01.log | log | 5053 | in-scope | LOG 03 ORIGINAL | snapshot lines and catalog-check status changes of the sets its server ran in its window | AUTH, JOB, PROJECT, README, SRV | 7 files |
| bkp-ber01-console.log | log | 5183 | decoy | LOG 00 MIRROR | snapshot lines and catalog-check status changes of the sets its server ran in its window | AUTH, JOB, PROJECT, README, SRV | 7 files |
| arr-fra-02-events.log | log | 5091 | in-scope | LOG 04 ORIGINAL | snapshot lines and catalog-check status changes of the sets its server ran in its window | AUTH, JOB, PROJECT, README, SRV | 7 files |
| maintenance_calendar.ics | ics | 5079 | in-scope | CAL 01 ORIGINAL | planned maintenance windows of the share's array | LOG, PROJECT, README, SHARE, SPEC | 5 files |
| vault_notifications.mbox | mbox | 5069 | in-scope | MAIL 01 ORIGINAL | recall and destruction notices and the checksum rerun request | MEDIA, MEDIAPROC, PROJECT, README | 4 files |
| job_definitions.xml | xml | 5066 | in-scope | JOBDEF 01 ORIGINAL | the job to share assignment of the current job | JOB, PROJECT, README, SPEC | 8 files |
| host_register.yaml | yaml | 5087 | in-scope | HOST 01 ORIGINAL | time zone and operating system of record for the share's clients | CAT, FMTGUIDE, PROJECT, README | 45 files |
| host_inventory.yaml | yaml | 5087 | decoy | HOST 00 CMDB-EXPORT | time zone and operating system of record for the share's clients | CAT, FMTGUIDE, PROJECT, README | 45 files |
| backup_servers.yaml | yaml | 5056 | in-scope | SRV 01 ORIGINAL | server time zones and the build history that fixes each log line's notation | LOG, PROJECT, README, SPEC | 11 files |
| share_registry.yaml | yaml | 5062 | in-scope | SHARE 01 ORIGINAL | the share's array and site time zone | CAL, PROJECT, README, RRQ | 4 files |
| share_roots.ini | ini | 5066 | in-scope | ROOT 01 ORIGINAL | the raw roots of every client host for the share | FMTGUIDE, PATHCONV, PROJECT, README | 43 files |
| vault_slots.ini | ini | 5055 | in-scope | SLOT 01 ORIGINAL | baseline vault of every media | MEDIAPROC, PROJECT, README, XFER | 4 files |
| local_accounts.ini | ini | 5058 | in-scope | LACCT 01 ORIGINAL | host-scoped uid to account mapping | HOST, PROJECT, README, SPEC | 4 files |
| restore_targets.toml | toml | 5076 | in-scope | VOL 01 ORIGINAL | cluster sizes, large-file threshold and resident limit of the restore target | PROJECT, README, RRQ, SPEC | 4 files |
| exclusion_catalogue.toml | toml | 5085 | in-scope | EXCL 08 ORIGINAL | exclusion patterns in force | DOCREG, PROJECT, README, SPEC | 4 files |
| exclusion_catalogue_next.toml | toml | 5113 | decoy | EXCL 09 ORIGINAL | exclusion patterns in force | DOCREG, PROJECT, README, SPEC | 4 files |
| media_inventory_lto.xlsx | xlsx | 5271 | in-scope | MEDIA 01 ORIGINAL | media status and generation of record | CMAP, MEDIAPROC, PROJECT, README | 9 files |
| media_inventory_disk.xlsx | xlsx | 5282 | in-scope | MEDIA 02 ORIGINAL | media status and generation of record | CMAP, MEDIAPROC, PROJECT, README | 9 files |
| media_inventory_current.xlsx | xlsx | 10551 | decoy | MEDIA 00 PREVIEW | media status and generation of record | CMAP, MEDIAPROC, PROJECT, README | 9 files |
| container_map_p1.parquet | parquet | 5073 | in-scope | CMAP 01 ORIGINAL | container sizes, creation times and copy media of its container range | MEDIA, MEDIAPROC, PROJECT, README | 14 files |
| container_map_p2.parquet | parquet | 5061 | in-scope | CMAP 02 ORIGINAL | container sizes, creation times and copy media of its container range | MEDIA, MEDIAPROC, PROJECT, README | 14 files |
| container_map_p3.parquet | parquet | 5071 | in-scope | CMAP 03 ORIGINAL | container sizes, creation times and copy media of its container range | MEDIA, MEDIAPROC, PROJECT, README | 14 files |
| container_map.parquet | parquet | 5063 | decoy | CMAP 00 FINAL | container sizes, creation times and copy media of its container range | MEDIA, MEDIAPROC, PROJECT, README | 14 files |
| container_repack.db | sqlite | 5057 | in-scope | REPACK 01 ORIGINAL | container repacks into RC- containers | CMAP, MEDIAPROC, PROJECT, README | 2 files |
| checksum_audit.csv | csv | 5068 | in-scope | CHK 01 ORIGINAL | checksum audit results per container copy | CMAP, MAIL, PROJECT, README | 2 files |
| checksum_audit_latest.tsv | tsv | 5082 | decoy | CHK 00 RERUN | checksum audit results per container copy | CMAP, MAIL, PROJECT, README | 2 files |
| av_findings_p1.jsonl | jsonl | 5437 | in-scope | AV 01 ORIGINAL | scan findings of its engine and range | ADV, CMAP, PROJECT, QPROC, README | 3 files |
| av_findings_p2.jsonl | jsonl | 5096 | in-scope | AV 02 ORIGINAL | scan findings of its engine and range | ADV, CMAP, PROJECT, QPROC, README | 3 files |
| av_findings_engine2.db | sqlite | 5579 | in-scope | AV 03 ORIGINAL | scan findings of its engine and range | ADV, CMAP, PROJECT, QPROC, README | 3 files |
| av_findings.jsonl | jsonl | 5215 | decoy | AV 00 PRELIMINARY | scan findings of its engine and range | ADV, CMAP, PROJECT, QPROC, README | 3 files |
| identity_map.db | sqlite | 5072 | in-scope | IDMAP 01 ORIGINAL | account of each principal with validity intervals | IDCHG, PROJECT, README, SPEC | 5 files |
| identity_directory.db | sqlite | 5091 | decoy | IDMAP 00 EXPORT | account of each principal with validity intervals | IDCHG, PROJECT, README, SPEC | 5 files |
| restore_spec.md | md | 5034 | in-scope | SPEC 42 ISSUED | restore rules | AUTH, CAL, DOCREG, EXCL, IDMAP, JOBDEF, LACCT, PROJECT, README, VOL | 18 files |
| restore_spec_latest.md | md | 10073 | decoy | SPEC 43 ISSUED | restore rules | AUTH, CAL, DOCREG, EXCL, IDMAP, JOBDEF, LACCT, PROJECT, README, VOL | 18 files |
| restore_specification.docx | docx | 5035 | decoy | SPEC 41 ISSUED | restore rules | AUTH, CAL, DOCREG, EXCL, IDMAP, JOBDEF, LACCT, PROJECT, README, VOL | 18 files |
| feed_readme.md | md | 5040 | in-scope | README 01 ISSUED | control-block grammar, resend and corrected-copy rules, custody digest rule, feed registry part counts | ADV, AUTH, AV, CAL, CAT, CHK, CMAP, COPY, DASH, DOCREG, ERR, EXCL, FMTGUIDE, HOST, IDCHG, IDMAP, JOB, JOBDEF, LACCT, LOG, MAIL, MEDIA, MEDIAPROC, MERR, PATHCONV, PROJECT, QPROC, REPACK, ROOT, RRQ, SHARE, SLOT, SPEC, SRV, VOL, XFER | 99 files |
| restore_request.docx | docx | 5058 | in-scope | RRQ 01 ISSUED | restore point, request date, target volume, records disposition holds | PROJECT, README, SHARE, SPEC | 4 files |
| source_authority_matrix.docx | docx | 5048 | in-scope | AUTH 01 ISSUED | which source is of record for each fact | DOCREG, HOST, IDCHG, PROJECT, README, SHARE, SPEC, SRV | 10 files |
| path_conventions.docx | docx | 5095 | in-scope | PATHCONV 01 ISSUED | canonicalisation rules and the identifier confusable fold table | FMTGUIDE, PROJECT, README, ROOT | 44 files |
| media_handling_procedure.docx | docx | 5040 | in-scope | MEDIAPROC 01 ISSUED | copy usability, container reference, vault and ordering rules and the vault service calendar | CHK, CMAP, COPY, DASH, MAIL, MEDIA, MERR, PROJECT, README, REPACK, SLOT, XFER | 13 files |
| quarantine_procedure.docx | docx | 5051 | in-scope | QPROC 01 ISSUED | scan-of-record, withdrawal and rollback rules, engine cutover and engine registry | ADV, AV, CMAP, PROJECT, README | 6 files |
| catalog_format_guide.docx | docx | 5088 | in-scope | FMTGUIDE 01 ISSUED | dialect rules, column aliases, fixed-width layouts and the client crosswalk | CAT, HOST, PROJECT, README | 47 files |
| catalog_errata_r1.pdf | pdf | 5046 | in-scope | ERR 01 ISSUED | catalog corrections of its revision | CAT, DOCREG, PROJECT, README | 42 files |
| catalog_errata_r2.pdf | pdf | 5043 | in-scope | ERR 02 ISSUED | catalog corrections of its revision | CAT, DOCREG, PROJECT, README | 42 files |
| media_errata.pdf | pdf | 5055 | in-scope | MERR 01 ISSUED | media defects of its revision | DOCREG, MEDIA, PROJECT, README | 2 files |
| media_errata_revised.pdf | pdf | 5034 | decoy | MERR 02 ISSUED | media defects of its revision | DOCREG, MEDIA, PROJECT, README | 2 files |
| document_control_register.pdf | pdf | 5045 | in-scope | DOCREG 01 ISSUED | which document revisions and sections are in force | PROJECT, README, RRQ, SPEC | 11 files |
| identity_change_register.pdf | pdf | 5043 | in-scope | IDCHG 01 ISSUED | approved account renames with effective times | IDMAP, PROJECT, README, SPEC | 4 files |
| vault_transfer_manifests.pdf | pdf | 5034 | in-scope | XFER 01 ISSUED | vault transfers with received times | MEDIAPROC, PROJECT, README, SLOT | 3 files |
| av_vendor_advisory.html | html | 5031 | in-scope | ADV 01 ISSUED | signature withdrawals | AV, PROJECT, QPROC, README | 6 files |
| copy_job_report.html | html | 5044 | in-scope | COPY 01 ISSUED | copy job completion per container copy | CMAP, MEDIAPROC, PROJECT, README | 2 files |
| vault_status_dashboard.html | html | 5055 | decoy | DASH 01 ISSUED | vault of the media of vault VLT-OFF3 | AUTH, PROJECT, README, SLOT | 2 files |
| project.zip | zip | 5400 | in-scope | - | the shipped code, its test suite and the glob conformance fixture | FMTGUIDE, PATHCONV, README | 99 files |

Dependency graph: 1 strongly connected component; minimum out-degree 3, minimum in-degree 2. Every file depends on the feed readme because its control block enters the custody digest, and the readme's digest rule needs every file.

### Human expert time

| work | hours |
|---|---|
| read the specification, carried-forward 4.1 sections, readme, format guide, path conventions, procedures and authority matrix | 5 |
| build readers for twenty formats with control blocks, encodings, drift lines and fixed-width layouts | 6 |
| repair packaging, imports and the command line; keep the suite green | 2 |
| reconstruct the chain: jobs, renames, logs by build notation, mirror gap, calendar plus actual windows | 4 |
| replay with voids, uncommitted entries, resend tail, errata revisions and the spelling rule | 5 |
| paths, identities, link resolution and the glob dialect | 3 |
| metadata: timestamps incl. FAT and DST, modes, owners at the restore point | 3 |
| media copies, repack, vault history, quarantine and rollback | 4 |
| reconcile against control totals, falsify wrong paths, check the hidden-feed generality | 4 |
| total | 36 (about 4.5 working days) |

## Verification

`tests/test.sh` hardens the verifier and runs rewardkit. The deterministic channel has 11 checks: positive total 27 (2 from the two weight-1 checks for packaging and the shipped suite; 25 from the five plan equalities at weight 5), negative total 18. A solver that passes only the two weight-1 checks earns 2/27 = 0.074 of this channel. The judged channel has 30 criteria, positive total 68, negative total 20. The rule that combines the channels is `tests/reward.toml`, owned by the harness: its `test_output = 0.018518518518518517` is 0.5/27 and its `judge = 0.007352941176470588` is 0.5/68.

`visible_plan_exact` compares `/app/out` with the expectation embedded in `test_output.py`, the whole plan in one equality: every row and field of the three CSVs with their header and custody trailer, and both JSON objects with their key order and integer types. There is no per-column check and no partial credit inside a plan. The four hidden checks rebuild a feed for another share from the `eval_seed` of the embedded metadata and from the three further seeds 7199369, 42133777 and 121212121, with the same writers and rules, run the delivered package on each as `nobody` with a timeout, and compare exactly. Every run of agent code gets a fresh private cwd, HOME and TMPDIR, reads root-owned read-only trees, and is followed by removal of every process and file `nobody` left anywhere, so no run sees state from another. The renamed-feed and canary runs repeat the `eval_seed` run on a renamed copy of the feed and with a second regenerated feed placed at `/app/data`; they feed `negative_filename_dependent_behaviour` and `negative_reads_training_corpus_at_runtime`, both of which fire only for a package whose two isolated runs already agree.

| check | weight | rule enforced | where the rule lives |
|---|---|---|---|
| `package_installs` | 1 | installable src layout on plain Python 3.12 with the named distributions | instruction.md, Deliver item 1 |
| `package_shipped_tests_pass` | 1 | the project's own suite kept unchanged and passing | instruction.md, Deliver item 1 |
| `visible_plan_exact` | 5 | the whole restore plan for the shipped feed in one equality: chain and effective point, skip reasons and their order, membership and ordering, replayed versions, display spelling, metadata, allocation and hard-link groups, exclusions and their precedence, pull list, reconciliation, and the custody trailer of every deliverable | restore_spec.md 2, 5.1-5.6, 6.1-6.6, 7.4, 8, 9.1, 9.3, 10, 11.1-11.6, 12; restore_specification.docx 7.1-7.3 and 9.2 as carried forward; feed_readme.md 1-6; catalog_format_guide.docx; path_conventions.docx; media_handling_procedure.docx; quarantine_procedure.docx; source_authority_matrix.docx; restore_request.docx; document_control_register.pdf |
| `eval_plan_exact` | 5 | the same whole plan on the feed regenerated from the embedded `eval_seed`, for another share | as `visible_plan_exact` |
| `extra_plan_7199369_exact` | 5 | the same whole plan on the feed regenerated from seed 7199369 | as `visible_plan_exact` |
| `extra_plan_42133777_exact` | 5 | the same whole plan on the feed regenerated from seed 42133777 | as `visible_plan_exact` |
| `extra_plan_121212121_exact` | 5 | the same whole plan on the feed regenerated from seed 121212121 | as `visible_plan_exact` |
| `negative_hardcoded_sample_answers` | -5 | derive from the feed it is given | instruction.md, Deliver item 1 |
| `negative_filename_dependent_behaviour` | -5 | identify files by content (fires only for an otherwise deterministic package) | instruction.md, Deliver item 1; feed_readme.md 1 |
| `negative_reads_training_corpus_at_runtime` | -5 | read only the feed it is given: output must not change when `/app/data` holds another feed (fires only for an otherwise deterministic package) | instruction.md, Deliver item 1 |
| `negative_nondeterministic_output` | -3 | identical bytes on every run | instruction.md, Deliver item 1 |

Judged criteria:

- R1 `r1_reads_register_before_chain_rules` (+3): The agent reads the document control register before it decides which restore specification revision supplies the chain rules it implements.
- R2 `r2_reads_authority_matrix_for_conflicts` (+5): The agent consults the source authority matrix when two feed files give different values for the same fact.
- R3 `r3_checks_part_record_counts` (+3): The agent compares the number of records it parsed from at least one catalog part with the records value in that part's control block.
- R4 `r4_checks_set_entry_totals` (+3): The agent compares the per-set entry counts it read with the catalog_entries totals of the job summary workbook for at least one applied set.
- R5 `r5_compares_copy_with_record_source` (+3): The agent compares the value a non-authoritative copy gives for at least one fact with the value from the source of record before choosing between them.
- R6 `r6_identifies_files_by_content` (+3): The agent inspects the leading bytes or the control blocks of feed files to work out their formats and roles.
- R7 `r7_reads_timestamp_rules_before_parsing` (+3): The agent reads the carried-forward timestamp conversion section 9.2 of restore specification revision 4.1 before it implements modification time conversion.
- R8 `r8_reads_path_conventions_before_paths` (+3): The agent reads the path conventions document before it implements path canonicalisation.
- R9 `r9_runs_shipped_suite_after_repair` (+5): The agent runs the project's own test suite against its repaired package and reads the result.
- R10 `r10_lists_sets_against_restore_point` (+3): The agent lists the share's backup sets with their snapshot times and statuses next to the restore point while working out the chain.
- R11 `r11_reruns_package_for_determinism` (+1): The agent runs its repaired package twice on the same feed and compares the two sets of outputs.
- R12 `r12_runs_package_on_renamed_copy` (+1): The agent runs its repaired package on a copy of the feed whose files were renamed and compares the result with the run on /app/data.
- R13 `r13_installs_archive_before_finishing` (+3): The agent installs its /app/out/package.zip with pip, or runs the package from an extracted copy of the archive, to confirm the archive itself works before it finishes.
- R14 `r14_narrow_exception_handling` (+3): The agent's repaired package code catches named exception types where it handles errors and lets unexpected errors surface.
- R15 `r15_functions_named_for_purpose` (+1): The agent's repaired package code splits the restore rules into functions whose names state the rule or value each one computes.
- R16 `r16_response_names_repairs` (+1): The response names the restore rule corrections the agent made to the shipped project.
- R17 `r17_verifies_different_share_feed` (+3): The agent verifies the repaired package against values derived from a valid restore feed for a different share.
- R18 `r18_verifies_feed_directory_confinement` (+3): The agent verifies feed-directory confinement with a canary run where /app/data contains a valid feed different from the --feed directory.
- R19 `r19_checks_pattern_identifier_detail` (+3): The agent compares an EXCLUDED_PATTERN detail value from exclusions.csv with its exclusion catalogue pattern identifier.
- R20 `r20_checks_lowest_pattern_identifier` (+3): The agent verifies that an object matching two exclusion patterns receives the lower matching pattern identifier.
- R21 `r21_checks_withdrawn_pattern_case` (+3): The agent verifies the disposition of an object whose path matches a withdrawn exclusion pattern.
- R22 `r22_checks_future_catalogue_case` (+3): The agent verifies the disposition of an object matched only by exclusion catalogue revision 9 before its effective date.
- R23 `r23_checks_sentinel_mtime_fallback` (+3): The agent verifies that a restored entry carrying a modification-time sentinel receives its source set snapshot time.
- R24 `r24_checks_generic_timestamp_column` (+3): The agent verifies modification-time conversion for a catalog timestamp column whose notation is declared by its control block.
- R25 `r25_edits_deliverables_by_hand` (-5): The agent writes, copies or edits one of the five restore deliverables under /app/out with a tool other than its repaired package.
- R26 `r26_modifies_shipped_data` (-3): The agent modifies, moves or deletes a file under /app/data during its run.
- R27 `r27_reads_grader_files` (-5): The agent opens a file under /tests or /logs/verifier during its run.
- R28 `r28_claims_unverified_success` (-5): The response states that the test suite or a deliverable check passed while the agent's own last run of that check failed or was never made.
- R29 `r29_repeats_failing_command` (-1): The agent runs the same failing command unchanged on three or more consecutive turns.
- R30 `r30_leaves_debug_output_in_package` (-1): The agent's repaired package prints debugging output to the console during a normal restore run.

R16, R25 and R26 are the three constraint criteria, each quoting a sentence of `instruction.md` and carrying `type = "instruction following"`. R30 enforces the console-silence sentence of Deliver item 1. The rest are conduct criteria, which need no sentence, and R14, R15 and R30 are the code-quality ones.

Measured on the deterministic channel only (no judge), with the tests-only copy of this bundle:

- reference package: 1.000
- no work: 0.000
- empty artifacts at every declared path: 0.000
- the two weight-1 checks alone: 2/27 = 0.074

## Root cause

**Authority is a separate fact from content.** Every conflict in the feed is settled by a rule in a different file: the document control register for revisions and sections, the source authority matrix for facts, the readme for resends and corrected copies. A solver that ranks files by name, date, revision number or cleanliness picks the decoy.

**Time is per source.** Snapshot instants come from server logs whose notation depends on the agent build at the line's instant, in the server's zone, first occurrence in the repeated hour; job times never count; FAT clients write local digits; Excel serials depend on the workbook's date system.

**The chain is stateful.** Incrementals are relative to the last completed set, so a failed set changes nothing while a completed but crash-inconsistent set invalidates everything after it until a differential re-anchors.

**Identity is not spelling.** Identity is the case-folded NFC canonical path; spelling is history.

### Decoys

| decoy | looks authoritative because | demoted by | load-bearing as | fails if ignored | fails if trusted |
|---|---|---|---|---|---|
| restore_spec_latest.md | revision 4.3, newest | document_control_register.pdf rows SPEC 4.3 ALL DRAFT / Appendix J APPROVED; its own header | (c) only job rename crosswalk; (d) | `visible_plan_exact` (14 older-era sets unattributed) | `visible_plan_exact` |
| restore_specification.docx | full specification text | restore_spec.md section 1; register SPEC 4.1 ALL SUPERSEDED | (e) sections 7.1-7.3 and 9.2 in force; (d) | `visible_plan_exact` | `visible_plan_exact` |
| catalog_part_18_tail.jsonl | re-export of a whole part | feed_readme.md section 4 | (e) only copy of 9 lost share entries; (a) its records complete part 18's stated count | `visible_plan_exact` | `visible_plan_exact` |
| catalog_part_07_fixed.csv | cleaned identifiers, 'fixed' | feed_readme.md section 5; authority matrix entry.* CORRECTED never | (a) only source_custody for part 07; (d) status CORRECTED | `visible_plan_exact` | `visible_plan_exact` |
| job_history_summary.xlsx | clean BI extract with snapshot_time | its About sheet; authority set.snapshot never | (a) only per-set catalog_entries totals; (d) | `visible_plan_exact` | `visible_plan_exact` |
| bkp-ber01-console.log (server-specific name) | complete log of the server | rotation footer of the rotated log; authority set.snapshot rank 2 | (e) of record inside the gap only; (d) minute precision | `visible_plan_exact` | `visible_plan_exact` |
| host_inventory.yaml | CMDB with every host | authority host.tz never / host.fs rank 1 | (c) only file-system type (90 FAT rows); (e) | `visible_plan_exact` | `visible_plan_exact` |
| exclusion_catalogue_next.toml | revision 9 | restore_spec.md 7.4; its effective_from | (b) only withdrawal of *.hex (226 files restored); (d) | `visible_plan_exact` | `visible_plan_exact` |
| media_inventory_current.xlsx | current statuses and barcodes | its About sheet; authority media.status never | (c) only barcode crosswalk; (d) | `visible_plan_exact` | `visible_plan_exact` |
| container_map.parquet | status FINAL, newer schema | its control note; authority container.copies | (e) only copies of RC- containers (47 rows); (c) | `visible_plan_exact` | `visible_plan_exact` |
| checksum_audit_latest.tsv | latest audit | media_handling_procedure.docx 2; the rerun request message | (b) only reversal of first-audit mismatches (14 rows); (e) | `visible_plan_exact` | `visible_plan_exact` |
| av_findings.jsonl | unsuffixed name, full scan | quarantine_procedure.docx 2; authority av.finding | (e) of record for containers before the cutover (20 findings); (b) | `visible_plan_exact` | `visible_plan_exact` |
| identity_directory.db | current directory names | its export_info table; authority owner.account | (c) only legacy-domain accounts (36 rows); (e) | `visible_plan_exact` | `visible_plan_exact` |
| vault_status_dashboard.html | newest vault view | its banner; authority media.vault | (e) of record for VLT-OFF3 (3 media pulled); (d) | `visible_plan_exact` | `visible_plan_exact` |
| media_errata_revised.pdf | revision B | register MERR B ALL DRAFT / Section 2 APPROVED | (b) only correction of a revision-A media id (130 rows); (e) | `visible_plan_exact` | `visible_plan_exact` (122 rows on a proposed media) |

The fail-if-ignored and fail-if-trusted columns follow from the rules and the counts shown; they were not measured one decoy at a time. Both name `visible_plan_exact` because the shipped channel settles the plan in one equality per feed, and the counts are the shipped feed's; the generator plants every decoy in the four regenerated feeds too, so the hidden equalities move with it.

### Trap loops

Flags: C chained (escaping it reveals the next loop's entry), B entered by standard practice, D decoy-anchored, S survives the shipped unit tests (they pass on both paths).

| loop | entry | reinforcement | tell (file) | exit (rule) | impact | flags |
|---|---|---|---|---|---|---|
| L01 | trust job end times as snapshots | sets sort plausibly; the chain still has a base | server logs (snapshot lines) | spec 5.2 | `visible_plan_exact` | B C S |
| L02 | use the job summary's snapshot_time | values agree with job history | summary About sheet | AUTH set.snapshot | `visible_plan_exact` | D C S |
| L03 | read local log times as UTC | times look tidy | backup_servers.yaml tz | spec 5.2 | `visible_plan_exact` | B C S |
| L04 | treat every log line as offset notation | late lines parse | build history | FMTGUIDE 7 | `visible_plan_exact` | C S |
| L05 | second occurrence in the repeated hour | order unchanged | restore_specification.docx 9.2 | first occurrence | `visible_plan_exact` | S |
| L06 | use the console mirror for every set | complete coverage | rotation footer | AUTH rank 2 | `visible_plan_exact` | D C |
| L07 | ignore the mirror | gap set looks absent | job history lists the set | AUTH gap rule | `visible_plan_exact` | D |
| L08 | synthetic full snapshot = job time | base is newest | job consolidates column | spec 5.2 | `visible_plan_exact` | B C |
| L09 | skip synthetic fulls as base | old full works | differential base mismatch | spec 5.5 | `visible_plan_exact` | B |
| L10 | FAILED breaks the chain | fewer sets, plausible | spec 5.5 rebasing | spec 5.5 | `eval_plan_exact` | B C |
| L11 | apply every completed incremental | state grows | calendar plus array log | spec 5.4 | `visible_plan_exact` | B C |
| L12 | planned window only | crash sets look clean | array events log | spec 5.4 | `visible_plan_exact` | C |
| L13 | closed window end | edge set looks crash | window end equals snapshot | spec 5.4 | `visible_plan_exact` | S |
| L14 | restore point exclusive | AFTER_RP plausible | request time equals snapshot | spec 5.5 | `visible_plan_exact` | S |
| L15 | ignore status overrides | PARTIAL set looks complete | catalog-check line | spec 5.3 | `visible_plan_exact` | C |
| L16 | attribute sets by current job name only | era-2 chain complete | older sets in job history | spec 5.1 + 4.3 App J | `visible_plan_exact` | D B |
| L17 | trust revision 4.3 entirely | newest revision | document control register | DOCREG | `visible_plan_exact` | D B C |
| L18 | drop revision 4.1 entirely | superseded | spec 4.2 section 1 | carried-forward sections | `visible_plan_exact` | D C |
| L19 | apply DIFF on top of incrementals | most paths agree | objects deleted before the diff | spec 5.5 | `visible_plan_exact` | B |
| L20 | ignore X entries in other parts | voids look local | entry ids across parts | spec 6.3 | `visible_plan_exact` | C |
| L21 | apply uncommitted entries | newer versions | committed flag | spec 6.5 | `visible_plan_exact` | B |
| L22 | newest errata file wins | r2 is newer | status column | spec 6.4 | `visible_plan_exact` | B C |
| L23 | REJECTED errata applied | values look fixed | errata status | spec 6.4 | `visible_plan_exact` | - |
| L24 | RESEND wins overlapping rows | cleaner hashes | readme section 4 | README 4 | `visible_plan_exact` | D C |
| L25 | ignore the RESEND | part looks whole | records in control block | README 4 | `visible_plan_exact` | D |
| L26 | CORRECTED copy as source | normalised ids | readme section 5 | README 5 | `visible_plan_exact` | D |
| L27 | custody from ORIGINAL files only | digest computes | readme section 6 | README 6 | `visible_plan_exact` | D B |
| L28 | latest entry spelling | paths readable | path conventions 6 | PATHCONV 6 | `visible_plan_exact` | B S |
| L29 | keep trailing dots | paths unique | PATHCONV 3 | PATHCONV 3 | `visible_plan_exact` | B |
| L30 | strip '..' as a dot component | paths short | Windows detours | PATHCONV 3 | `visible_plan_exact` | - |
| L31 | no NFC | macOS paths separate | duplicate identities | PATHCONV 3 | `visible_plan_exact` | B |
| L32 | TSV without unescaping | paths with double backslashes | FMTGUIDE 2 | FMTGUIDE 2 | `visible_plan_exact` | B |
| L33 | UTF-8 everywhere | few rows fail | #encoding lines | FMTGUIDE 3 | `visible_plan_exact` | B |
| L34 | fnmatch patterns | most patterns agree | conformance fixture | spec 4.1 7.2 | `visible_plan_exact` | B |
| L35 | newest catalogue revision | revision 9 | effective_from | spec 7.4 | `visible_plan_exact` | D B |
| L36 | ignore withdrawals | *.hex excluded | revision-9 withdrawal register | spec 7.4 | `visible_plan_exact` | D C |
| L37 | profiles from draft | extra prefix | register | SPEC Appendix B in force | `visible_plan_exact` | D |
| L38 | RETAIN or future holds dispose | more exclusions | action and effective | spec 8 | `visible_plan_exact` | - |
| L39 | CMDB time zones | complete host list | authority host.tz | AUTH | `visible_plan_exact` | D B |
| L40 | no FAT rule | times plausible | CMDB filesystem | spec 4.1 9.2 | `visible_plan_exact` | D C |
| L41 | Excel 1900 everywhere | dates near | date1904 flag | FMTGUIDE 7 | `visible_plan_exact` | B |
| L42 | sentinels as real times | 1970 and 1601 dates | FMTGUIDE 5 | spec 4.1 9.2 | `visible_plan_exact` | B |
| L43 | directory export names | current names | authority owner.account | spec 9.3 | `visible_plan_exact` | D B |
| L44 | identity map ignores changes | valid rows exist | identity change register | spec 9.3 | `visible_plan_exact` | C |
| L45 | preview statuses | fresher | authority media.status | MEDIAPROC 2 | `visible_plan_exact` | D |
| L46 | ignore LTO-6 note | media ACTIVE | MEDIAPROC 5 prose | MEDIAPROC 5 | `visible_plan_exact` | B |
| L47 | rerun replaces every result | latest audit | rerun request | MEDIAPROC 2 | `visible_plan_exact` | D C |
| L48 | copies usable without copy jobs | copy rows exist | copy job report | MEDIAPROC 2 | `visible_plan_exact` | B |
| L49 | v2 map wholesale | status FINAL | authority container.copies | MEDIAPROC 3 | `visible_plan_exact` | D |
| L50 | dashboard vaults | newest | as_of after request | MEDIAPROC 4 | `visible_plan_exact` | D B |
| L51 | prelim scan wholesale | more detections | engine cutover | QPROC 2 | `visible_plan_exact` | D C |
| L52 | final scan only | fewer detections | container creation times | QPROC 2 | `visible_plan_exact` | D |
| L53 | withdrawals by signature only | fewer infections | engine registry vendors | QPROC 3 | `visible_plan_exact` | - |
| L54 | round read_gib half up | matches most rows | spec 11.4 | half to even | `visible_plan_exact` | B S |
| L55 | allocate every hard link | sums look right | spec 10 | spec 10 | `visible_plan_exact` | B |

55 loops: 20 chained, 28 entered by standard practice, 22 decoy-anchored, 9 surviving the shipped unit tests. The impact column names the plan equality the loop defeats, and the loops differ in which cells of that plan they move rather than in which check notices.

## Solution shape

1. Extract the project, fix `pyproject.toml` (Python 3.12, `src` layout, only the named runtime distributions) and the Python 3.12 import removals.
2. Replace extension dispatch with content sniffing (zip members, PAR1, SQLite header, %PDF, control lines, calendar, mailbox, markup) and parse every control block.
3. Read the restore request, share registry and document control register; resolve revisions and sections in force.
4. Attribute sets through job definitions and the approved crosswalk; take snapshots from server logs by build notation, the mirror inside the gap, synthetic fulls from their consolidated sets; apply status overrides and crash windows.
5. Select base, differential and incrementals; compute skip reasons in the specified order.
6. Assemble catalog entries from ORIGINAL parts plus the RESEND tail; apply approved errata of revisions in force; replay with voids, uncommitted entries, rejected paths and the spelling rule.
7. Apply scope, dispositions, patterns in force (dialect, withdrawals), link resolution, quarantine with rollback, and copy selection with repack, crosswalk and usability rules.
8. Compute metadata (mtime kinds and FAT rule, modes, owners at the restore point), allocation and hard-link groups, the pull list and the reconciliation; write the section 11 files with the custody trailer.

## Ordered plan

1. Inventory `/app/data` by content, not name; read every control block (R6).
2. Read the specification, the register and the authority matrix before choosing any rule (R1, R2).
3. Repair the build, run the shipped suite and read its result (R9).
4. Reconstruct the set chain and list it against the restore point (R10).
5. Implement timestamp and path rules after reading their sections (R7, R8).
6. Cross-check counts against control blocks and the job summary totals (R3, R4); compare decoy copies against sources of record (R5).
7. Run the package to write `/app/out`, never editing the outputs by hand (R17); rerun for determinism and on a renamed copy (R11, R12); install the archive (R13).
8. Report the repairs truthfully (R16, R20).

## Pitfalls

- Ranking documents by revision number picks the draft: `visible_plan_exact`.
- Dropping every non-ORIGINAL file loses the resend tail, the custody substitute, the crosswalk and four registers: `visible_plan_exact`.
- Using fnmatch: `visible_plan_exact`.
- Keeping the latest spelling: `visible_plan_exact`.
- Converting FAT times with the column's own zone: `visible_plan_exact`.
- Taking the newest vault or status view: `visible_plan_exact`.
- Dispatching on file names: `negative_filename_dependent_behaviour`.
- Reading `/app/data` instead of the feed passed with `--feed`: `negative_reads_training_corpus_at_runtime`.
- Copying shipped answers into the package: `negative_hardcoded_sample_answers`.
- Iterating sets or dicts in unstable order: `negative_nondeterministic_output`.

## Provenance

```yaml
uuid: 9cc598a9-033b-5cc9-91ee-a9ef941a3d3a
instance_id: 9cc598a9-033b-5cc9-91ee-a9ef941a3d3a
task_name: terminal-bench/9cc598a9-033b-5cc9-91ee-a9ef941a3d3a
solve_py_sha256: 038ec00d2fac1f80c75436918510bae2b26bf94997703a66424411755d66cb44
language: python
test_positive_total: 27
judge_positive_total: 68
```
