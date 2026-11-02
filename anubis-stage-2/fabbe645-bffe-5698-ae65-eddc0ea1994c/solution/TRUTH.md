# TRUTH.md - fabbe645-bffe-5698-ae65-eddc0ea1994c

## Defect

The Konkan Coast Broadcast Archive (KCBA) holds the same digitised media files in four vaults
(Kolhapur, Margao, Nashik, Ratnagiri). Each vault exports its holdings in its own format, and the
rules that decide how many copies of a file must be kept are spread over a governing retention
charter, three dated amendments, a rights register, a legal hold log, a collection catalogue, a
legacy crosswalk and eight older papers of which exactly one item each is still in force. The
deliverable is a reusable planner `/app/out/optimize.py` that, for five dated planning scenarios,
decides which replicas to keep and which to release, packs the kept replicas onto tape volumes
per vault, carries an earlier plan forward when run with `--prior`, and refuses to publish when
the estate census does not reconcile. The reference language is Python 3.12 with the standard
library only. Grading has two channels: Channel A is the deterministic program checks in
`tests/test_output.py`, which re-run the submitted planner on estates it has never seen, and
Channel B is the judged rubric in `tests/judge.toml`, which reads the trajectory and the final
reply.

What a planner has to get right, each item naming the check that grades it:

1. (focal) Required replicas per object follow the charter class table, the rendition rule
   (mezzanine one fewer, proxy one) and amendment 01's dated R2 commercial window. Graded by
   `required_replicas`.
2. (focal) Kept vaults follow the class preference order taken from the 2019 schedule's
   `vault_preference` column, with under replicated objects flagged. Graded by
   `vault_preference`.
3. (focal) Kept replicas are packed per vault by first fit decreasing with the footprint
   formula and the tie order of the volume layout paper. Graded by `tape_footprints` and
   `first_fit_packing`.
4. (focal) Usable capacity is native capacity from the media catalogue minus the reserve from
   the 2022 capacity workbook; labels and fill basis points follow the label width and half
   even rounding. Graded by `usable_capacity`, `labels_and_fill` and `media_reserve_shares`.
5. (focal) A run with `--prior` carries forward every earlier volume whose members are all
   still kept in that vault and numbers new volumes on from the largest earlier sequence.
   Graded by `delta_carry_forward`.
6. (focal) A census that does not reconcile (missing file, wrong size, wrong digest, wrong
   record count per file) gives status `HELD`, the exact reason list, and no other output file.
   Graded by `census_hold`.
7. (focal) Objects in several collections take the largest requirement; the governing
   collection is the smallest id among those giving it. Graded by `multi_collection`.
8. (focal) A legal hold in force keeps every replica of the object, including duplicates.
   Graded by `legal_holds`.
9. (drift) From a stated shard onward the Ratnagiri export replaces the decimal `len` field by a
   hexadecimal string field named in `ratnagiri_changelog.md`. Graded by `ratnagiri_hex_sizes`.
10. (drift) One Margao shard writes digests as unpadded Base32 under a second encoding code;
    the others use padded Base64. Graded by `margao_base32_digests`.
11. (drift) Margao rows written before the catalogue migration still carry legacy `KCB-` ids;
    split legacy series resolve by the replica's catalogued date against the crosswalk.
    Graded by `legacy_collections`.
12. (drift) Amendment 03 splits class R3 into R3A and R3B by ingest year from a dated day, so
    early scenarios keep R3 and later ones do not. Graded by `r3_split_class`.
13. (trap) The Kolhapur catalogue gives sizes in 512 byte sectors; the exact size lives only in
    the binary index, joined by sequence number within the same shard number. Files just under
    the sidecar threshold look like full files from sectors. Graded by `kolhapur_sizes`; once
    the sizes are right, Kolhapur sidecars that stay out of the plan are graded with every other
    vault by `sidecar_threshold`.
14. (trap) Kolhapur rendition codes are single letters whose meaning is written only in the tape
    notes, among stale notes. Graded by `kolhapur_renditions`.
15. (trap) One Nashik node was decommissioned on a date written only in the 2024 audit page;
    rows on it stop being replicas from that date while another node marked "under
    observation" stays live. Graded by `decommissioned_node`.
16. (trap) Rights licences override class only for commercial collections and only from
    amendment 02's date; public licences in the same register are ignored. Graded by
    `rights_register_class`.
17. (trap) The sidecar threshold is strict (a file of exactly the threshold is planned) and
    the older draft value in the same note is stale. Graded by `sidecar_threshold`, in every
    vault.
18. (trap) Within one vault, extra rows for the same digest are duplicates; the primary is the
    smallest path in byte order, which is not always the row a reader expects. Graded by
    `duplicate_rows`.

Out of bounds: copying the visible answers into a program that ignores `--data` is caught by
`negative_hardcoded_sample_answers`; output that changes with the folder name or location of the
input is caught by `negative_filename_dependent_behaviour`; reading the shipped estate from its fixed
location while another estate is passed on the command line is caught by
`negative_reads_training_corpus_at_runtime`; output that differs between two runs on the same input
is caught by `negative_nondeterministic_output`; a planner that writes anywhere outside the folder
given with `--out`, scratch files deleted again included, is caught by
`negative_writes_outside_output_folder`. A run on an estate the size of the shipped one must
publish in under 60 seconds, graded by `full_size_run_under_a_minute`.

## Load-bearing work

The planner must parse fifteen formats (CSV with quoted commas, namespaced XML, JSON Lines with a
mid stream schema change, fixed width text joined to a binary index of either endianness, SQLite,
a minimal XLSX read through its shared strings, INI, TOML, TSV, PSV with mixed time zones, HTML,
Markdown tables and plain text notes) and pull every cycle specific parameter out of prose:
class minimums, amendment dates and years, the header size, block sizes, encoding codes, index
endianness, the hex shard and field name, label width, sidecar threshold, hold tie rule,
decommissioned node and date, rendition letters, vault preferences and reserves. Nothing of the
visible cycle may be fixed in code, because the hidden estates draw every one of those values
afresh.

On top of parsing, it must chain at least six concepts per object: legacy id resolution, class
after rights and amendments, rendition requirement, multi collection maximum, hold state on an IST
calendar date with a same date tie rule, primary replica selection, preference order choice, then
per vault footprint, first fit decreasing packing with a two key tie break, labels, half even
fill, rollups and data quality counts, and finally the carry forward rules of a delta run.

Out of bounds by design: the planner never needs network access, packages outside the standard
library, the grading files, or any value that is absent from `/app/data`; every graded literal
(file names, key names, reason strings, status words, label shape) is spelled out in
`plan_output_contract.md` or the paper that owns it.

## Verification

`tests/test.sh` clears stale result files, locks `/tests` to root, and runs rewardkit over
`tests/test_output.py`. The verifier rebuilds every hidden estate, and the expected plan for it,
with the reference model of the archive written as plain Python source in the test file itself;
nothing is decoded or executed from an encoded string. It runs the submitted
`/app/out/optimize.py` as user `nobody` through `setpriv`, with the network unshared, from a
staged readable copy, with a 120 second cap per run and a private, empty HOME and temporary
folder whose timestamp is reset before the run. Nine runs are made: second estate, hidden
estate, hidden estate repeated with a different hash seed, hidden estate moved to another folder,
hidden estate with a decoy estate placed at the shipped data location, a later epoch of the
hidden estate with `--prior` pointing at the planner's own earlier output, two broken copies of
the hidden estate for the hold path, and a timed run on a third estate of the shipped size
(15000 drawn objects). After every run the verifier looks for files the program left, or made
and deleted, outside its `--out` folder: in the private HOME and temporary folder and in the
shared scratch folders `/tmp`, `/var/tmp` and `/dev/shm`.

Channel A positive checks, weight 5 each (graded on the hidden estate, every scenario):
`kolhapur_sizes`, `ratnagiri_hex_sizes`, `margao_base32_digests`, `kolhapur_renditions`,
`legacy_collections`, `decommissioned_node`, `sidecar_threshold`, `required_replicas`,
`rights_register_class`, `r3_split_class`, `legal_holds`, `duplicate_rows`, `vault_preference`,
`multi_collection`, `tape_footprints`, `first_fit_packing`, `usable_capacity`, `labels_and_fill`,
`delta_carry_forward`, `census_hold`, `media_reserve_shares`. Shape checks, weight 1 each: `visible_outputs`,
`field_run`, `rollups_follow_ledger`, `quality_counts`, `census_published`. Weight 3:
`full_size_run_under_a_minute` (the instruction's 60 second need, measured on the timed run and
paid only when that run publishes the right plan id with at least half of every scenario's
reference replicas listed). The positive weight total is 113.

Channel A negative checks: `negative_hardcoded_sample_answers` (weight -5),
`negative_filename_dependent_behaviour` (weight -5), `negative_reads_training_corpus_at_runtime`
(weight -5), `negative_nondeterministic_output` (weight -3),
`negative_writes_outside_output_folder` (weight -3). Negative total 21. Four of the five fire only
when the planner's two plain runs on the hidden estate exited cleanly and produced identical
output, so a crashing planner is never charged twice. `negative_nondeterministic_output` is the
complement: it fires exactly when both runs exit cleanly and their output differs.

Each positive check compares facts, not whole files: it takes the facts of its own rule from the
truth, matches them by key against the planner's output, and needs coverage of the rule's facts
as well as exact agreement. Downstream checks only grade objects whose upstream facts (row bytes,
collections, renditions, class) the planner already got right, and packing is re-derived from the
planner's own kept set and footprints, so one wrong rule costs one check; the tape reserve is
the one input that feeds two checks (see the measured numbers). Failure messages state
what disagreed, never the expected value.

Channel B criteria in `tests/judge.toml`: R1 census size and digest comparison (+3), R2 names the
followed paper for each disagreement (+3), R3 per file record counts (+3), R4 inspects shipped
trap conditions (+3), R5 determinism re-run (+1), R6 reports status and per scenario counts (+3),
R7 code quality of `/app/out/optimize.py` (+3), R8 changes a file under `/app/data`, judged from
the trajectory (-5), R9 reads grading files (-5), R10 claims an unrun check (-3), R11 runs a
command that reaches outside the machine for software or data (-3), R12 lists the checks run on
the output (+3). Positive total 22, negative total 16. The rule that combines the two channels
into one score belongs to the runner harness through `tests/reward.toml`, which weights Channel A
by 0.5/113 and Channel B by 0.5/22.

## Root cause

**Scattered authority.** No single file holds a full rule. The charter states the order of
authority and lists, for each older paper, the one item still in force; every other number in
those papers is stale and differs from the live value, so reading the nearest number gives a
wrong plan.

**Format drift.** Two vault exports change shape part way through: a size field turns into a
hex string from a stated shard, and one shard switches digest encoding. Legacy collection ids
survive in old Margao rows and need the crosswalk, with split series resolved by date.

**Dated windows.** Amendment 01 applies only inside a half open window, amendment 02 from a
date and only to commercial collections, amendment 03 from a date by ingest year. The same
object can change class between scenarios.

**Hidden exactness.** Kolhapur sectors round sizes up; the exact size is in the binary index.
Fill figures use half even rounding on integers. First fit decreasing ties break on digest then
path. Labels pad to a width written only in the 2021 handbook.

**Completeness control.** The estate census lists bytes, SHA-256 and record counts for every
input file; a planner that only checks totals or skips the census publishes from a broken estate.

**Red lines.** The planner must not write inside its input folder or anywhere else outside
`--out`, must not read anything outside `--data` and `--prior`, must not depend on folder names or run count, and must not carry
any value of the visible cycle.

## Solution shape

1. Reconcile `estate_census.toml` first: presence, size, SHA-256 and per file record counts
   counted as `archive_desk_brief.md` section 6 says; on any mismatch write only
   `perf_report.json` with status `HELD` and sorted reasons.
2. Load rules from the papers with targeted patterns: charter class table, amendment dates,
   split year, header size, Margao encoding codes, index endianness, hex shard and field,
   label width, sidecar threshold, hold tie rule, decommissioned node and date, rendition
   letters, vault preferences, reserves, block sizes and native capacities.
3. Load registers: collections from SQLite, licences from XML, crosswalk from TSV sorted by
   `effective_from`, hold events from PSV moved to IST dates.
4. Parse the four exports into rows (vault, path, digest, bytes, collection, rendition), joining
   each Kolhapur catalogue shard to the index shard of the same number by sequence.
5. Per scenario: drop sidecars and decommissioned node rows, group by digest, compute class and
   requirement per collection, take the maximum, resolve holds, choose primaries and keep vaults
   by preference.
6. Per vault: footprints, first fit decreasing, labels, used bytes and half even fill; in delta
   mode carry earlier volumes whose members are all still kept, then pack the rest into new
   volumes numbered on from the largest earlier sequence.
7. Write the five scenario files, the status report, the two rollups and data quality with sorted
   keys, two space indent and a trailing newline.

## Ordered plan

1. Read the desk brief and the charter, then every paper the charter's section 10 names; write
   down which item of each older paper is live (judge R2).
2. Reconcile the census file by file before trusting any export (judge R1, R3).
3. Inspect the trap conditions in the shipped files: Kolhapur sectors against index sizes,
   the Ratnagiri field change, the Margao encodings, the decommissioned node, the sidecar
   threshold (judge R4).
4. Build parsers and rule loading; check row counts against the census.
5. Implement selection and packing; check the worked example in `plan_output_contract.md`.
6. Implement the delta and hold paths; exercise both on scratch copies outside `/app/data`.
7. Run the finished planner twice and compare outputs byte for byte (judge R5).
8. Report status and per scenario counts and the papers followed (judge R6), only claiming
   checks that were run (judge R10 and R12), with clean code (judge R7).

## Pitfalls

- Taking Kolhapur size as sectors times 512 fails `kolhapur_sizes` and breaks every downstream
  check on those objects.
- Reading only `len` in Ratnagiri rows fails `ratnagiri_hex_sizes`.
- Decoding every Margao digest as Base64 fails `margao_base32_digests`.
- Mapping split legacy ids to the first crosswalk row fails `legacy_collections`.
- Applying public licences or applying licences before amendment 02 fails
  `rights_register_class`.
- Splitting R3 before amendment 03's date fails `r3_split_class`.
- Ignoring the IST date conversion or the tie rule fails `legal_holds`.
- Using `<=` for the sidecar threshold fails `sidecar_threshold`.
- Using the handbook header size or no header fails `tape_footprints`.
- Using compressed capacity or forgetting the reserve fails `usable_capacity`.
- Floor division for fill fails `labels_and_fill`.
- Restarting numbering at 1 in delta mode fails `delta_carry_forward`.
- Checking only total records fails `census_hold`.
- Copying `catalogue.db` to a temporary file before opening it writes outside `--out` and fires
  `negative_writes_outside_output_folder`; the reference loads it into memory.
- Treating Kolhapur rows as exempt from the sidecar threshold fails `sidecar_threshold`.

## Concept list

Census reconciliation per file; Base32 and Base64 digest decoding; binary index parsing with
declared endianness; fixed width parsing; mid stream schema drift; legacy id crosswalk by date;
dated amendment windows; segment scoped rights overrides; class split by ingest year; rendition
requirement; multi collection maximum with smallest id tie break; event log state on IST dates
with a same date tie rule; primary replica by byte order; preference ordered selection;
tape footprint with block rounding; usable capacity from two sources; first fit decreasing with
two key ties; zero padded labels; half even integer rounding; delta carry forward; held
publication.

## Measured numbers

Visible estate (`/app/data`, 46 files, 59318 lines): plan `KCBA-PLN-458F50`, status `PUBLISHED`,
45 census entries all matching, reserve shares KT-180 118, KT-240 132, KT-300 106 basis points.
Per scenario (objects, kept replicas, released replicas, volumes): peak 2024-03-26 13819, 20945,
14031, 72; steady 2024-06-24 13819, 21898, 13078, 75; latency 2024-10-14 13819, 21942, 13034, 76;
burst 2025-02-03 13819, 20032, 14470, 71; visible 2025-04-25 13819, 20181, 14321, 70. The
reference planner runs in under 3 seconds on it.

Grading behaviour measured against the shipped checks: Channel A only, since no judged channel score can
exist for a reference solution: the reference planner scores 1.000; a planner with exactly one
rule family wrong scores 108/113 = 0.9558, for each of the twenty one weight five families,
with only that family's check failing; the one input two families share is the tape reserve,
so a planner that reads the wrong reserve loses the two checks
that read the reserve, `usable_capacity` and `media_reserve_shares`, and scores
103/113 = 0.9115, because the packing, label and fill checks measure each volume against
the usable capacity the planner itself wrote; a correct planner that needs more than 60
seconds on the timed run scores 110/113 = 0.9735; a hand written set of the declared output
files with no planning in it scores 0.000; an empty output scores 0.

## Inventory

| File | Format | Role |
| --- | --- | --- |
| `archive_desk_brief.md` | Markdown | start here: map of papers, primer, glossary, census counting rules, calendar |
| `plan_output_contract.md` | Markdown | exact output files, keys, orders, reason strings, worked example |
| `retention_charter.md` | Markdown | governing paper: precedence, class table, renditions, selection, holds, older papers |
| `charter_amendment_01.md` | Markdown | R2 commercial minimum window |
| `charter_amendment_02.md` | Markdown | rights register date and commercial scope |
| `charter_amendment_03.md` | Markdown | R3 split date, year and minimums |
| `volume_layout.md` | Markdown | header size, footprint, capacity, packing, labels, delta rules |
| `margao_export_readme.md` | Markdown | Margao encoding codes and decoder appendix |
| `kolhapur_index_format.md` | Markdown | catalogue columns, index layout and endianness |
| `ratnagiri_changelog.md` | Markdown | shard where the size field changes and its new name |
| `ops_handbook_2021.md` | Markdown | older paper, live label width |
| `migration_memo_2023.md` | Markdown | older paper, live split legacy rule |
| `sidecar_policy_note.md` | Markdown | older paper, live sidecar threshold |
| `legal_hold_faq.md` | Markdown | older paper, live IST date and tie rule |
| `nashik_audit_2024.html` | HTML | older paper, live decommissioned node and date |
| `kolhapur_tape_notes.txt` | text | older paper, live rendition letters |
| `retention_schedule_2019.csv` | CSV | older paper, live vault preference |
| `capacity_planning_2022.xlsx` | XLSX | older paper, live reserve bytes |
| `nashik_manifest_01..04.csv` | CSV | Nashik replicas |
| `margao_inventory_01..04.xml` | XML | Margao replicas |
| `ratnagiri_objects_01..04.jsonl` | JSON Lines | Ratnagiri replicas |
| `kolhapur_catalogue_01..04.dat` | fixed width | Kolhapur replicas with sector counts |
| `kolhapur_index_01..04.idx` | binary | Kolhapur exact sizes and raw digests |
| `catalogue.db` | SQLite | collections, segment, class, ingest year |
| `rights_register.xml` | XML | licence class overrides |
| `legal_holds.psv` | PSV | hold event log |
| `collection_crosswalk.tsv` | TSV | legacy ids to current collections |
| `vault_profiles.ini` | INI | vault code, cartridge type, block size |
| `media_catalogue.json` | JSON | native capacities |
| `estate_census.toml` | TOML | sizes, digests and record counts of every other file |
| `run_control.json` | JSON | plan id and scenario dates |

## Decoy table

| Paper | Live fact (charter section 10) | Stale content beside it |
| --- | --- | --- |
| `ops_handbook_2021.md` | label zero pad width | header 32768 bytes, block size, compressed capacity, 1 GiB reserve |
| `migration_memo_2023.md` | split legacy id resolves by catalogued date | claim that no legacy ids remain |
| `sidecar_policy_note.md` | strict threshold 4194304 bytes | 512 KiB draft value |
| `legal_hold_faq.md` | IST date and same date order | 365 day expiry of holds |
| `nashik_audit_2024.html` | decommissioned node and date | node under observation, advisories |
| `kolhapur_tape_notes.txt` | rendition letters | 2048 byte sector note |
| `retention_schedule_2019.csv` | `vault_preference` | `min_replicas` |
| `capacity_planning_2022.xlsx` | `reserve_bytes` | 2022 capacities |

## Check to rule trace

| Check | Instruction sentence | Paper and section | Visible data line |
| --- | --- | --- | --- |
| `kolhapur_sizes` | planner reads the exports in `/app/data` | `kolhapur_index_format.md` | `kolhapur_index_format.md:24` |
| `ratnagiri_hex_sizes` | same | `ratnagiri_changelog.md` | `ratnagiri_changelog.md:19` |
| `margao_base32_digests` | same | `margao_export_readme.md` | `margao_export_readme.md:28` |
| `kolhapur_renditions` | same | charter section 10 | `kolhapur_tape_notes.txt:5` |
| `legacy_collections` | same | charter section 4, memo rule 3 | `migration_memo_2023.md:9` |
| `decommissioned_node` | same | charter section 9 | `nashik_audit_2024.html:12` |
| `sidecar_threshold` | same | charter section 9 | `sidecar_policy_note.md:7` |
| `required_replicas` | exact compare sentence | charter sections 3 and 5, amendment 01 | `retention_charter.md:29`, `charter_amendment_01.md:7` |
| `rights_register_class` | same | amendment 02 | `charter_amendment_02.md:5` |
| `r3_split_class` | same | amendment 03 | `charter_amendment_03.md:5` |
| `legal_holds` | same | charter section 8, FAQ | `legal_hold_faq.md:8` |
| `duplicate_rows` | same | charter section 7 | `retention_charter.md:61` |
| `vault_preference` | same | charter section 7 | `retention_charter.md:69` |
| `multi_collection` | same | charter section 6 | `retention_charter.md:52` |
| `tape_footprints` | same | `volume_layout.md` section 2 | `volume_layout.md:19` |
| `first_fit_packing` | same | `volume_layout.md` section 3 | `volume_layout.md:32` |
| `usable_capacity` | same | `volume_layout.md` section 1 | `volume_layout.md:15` |
| `labels_and_fill` | same | `volume_layout.md` section 4 | `volume_layout.md:41` |
| `delta_carry_forward` | the `--prior` need | `volume_layout.md` section 5 | `volume_layout.md:60` |
| `census_hold` | the census hold need | contract section 2 | `plan_output_contract.md:28` |
| `visible_outputs` | run once on `/app/data` into `/app/out` | contract | `run_control.json` |
| `field_run` | reusable on any export | contract section 2 | `plan_output_contract.md:22` |
| `rollups_follow_ledger` | exact compare sentence | contract section 4 | `plan_output_contract.md:76` |
| `quality_counts` | same | contract section 4, brief section 6 | `archive_desk_brief.md:86` |
| `census_published` | same | contract section 2 | `plan_output_contract.md:15` |
| `media_reserve_shares` | the reserve share need | contract section 2, workbook Reserve sheet | `plan_output_contract.md:26` |
| `full_size_run_under_a_minute` | finishes in under 60 seconds | instruction need 6 | `instruction.md:19` |
| negatives | reusable, byte identical, read only `--data`, write only into `--out` | instruction needs 1 to 3 | `instruction.md:14-16` |

## Trap table

| Wrong move | Why it looks right | Signal | Where documented | Defeating check | Next trap |
| --- | --- | --- | --- | --- | --- |
| size = sectors x 512 | the catalogue has a size column | sizes near the threshold become planned files | `kolhapur_index_format.md` | `kolhapur_sizes` | rendition letters |
| header from the handbook | the handbook is the operations manual | footprints differ by a constant | `volume_layout.md` section 2, charter section 10 | `tape_footprints` | reserve source |
| capacity from the workbook | it lists capacities per cartridge | usable bytes off per vault | `volume_layout.md` section 1 | `usable_capacity` | label width |
| min replicas from the 2019 schedule | it has a min column per class | required counts differ | charter sections 3 and 10 | `required_replicas` | amendment windows |
| apply every licence | the register lists them all | public collections change class | amendment 02 item 3 | `rights_register_class` | R3 split |
| holds expire after 365 days | the FAQ says so | held objects drop to normal | charter section 8 | `legal_holds` | IST dates |
| `<=` threshold | "below 4 MiB" is read loosely | files of exactly the threshold vanish | `sidecar_policy_note.md` item 2 | `sidecar_threshold` | node decommission |

## Expert time

| Subsystem | Work | Hours |
| --- | --- | --- |
| S1 vault parsing | four exports, index join, encodings, drift | 24 |
| S2 identity | crosswalk by date, rendition letters, node decommission | 12 |
| S3 eligibility and class | sidecars, rights scope, amendment windows including the settled class order when a rights override lands inside the amendment window, R3 split | 18 |
| S4 replica rules | rendition need, multi collection, holds on IST dates | 16 |
| S5 selection | primaries, duplicates, preference order, under replication | 10 |
| S6 packing | footprints, capacity, first fit decreasing, labels, fill, reserve share with an exact half | 16 |
| S7 publication | census, held path, delta carry forward, rollups, checks | 14 |
| Total | | 110 |

## Provenance

```yaml
uuid: fabbe645-bffe-5698-ae65-eddc0ea1994c
instance_id: fabbe645-bffe-5698-ae65-eddc0ea1994c
task_name: terminal-bench/fabbe645-bffe-5698-ae65-eddc0ea1994c
fix_patch_sha256: 8742327e2c91673c8508551f4801ebc0a17dc3ba3d8733b15b44ce335e171be4
solve_py_sha256: e9f475fb0e9232d4b5f2bfdc2f8276a7c3db7af8da6aaa5b44f9d938e498b433
test_output_sha256: e44be153514186e4692b0d368eb03e7510ed61d54c7ea10099de0fcdd356408e
language: python
```
