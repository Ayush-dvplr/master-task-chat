# KCBA Archive Desk Brief: Replica Retention and Tape Packing

Prepared by the Archive Desk, Konkan Coast Broadcast Archive (KCBA), for planning cycle KCBA-PLN-458F50.

## 1. Why this cycle exists

KCBA keeps digitised masters, mezzanine files and viewing proxies of its radio and television
holdings in four vaults. Over twenty years of ingest projects many files were copied to more
vaults than the retention charter asks for, while some files never reached enough vaults. Each
planning cycle the desk decides, for every scenario date listed in `run_control.json`:

1. which replicas of each stored file must be kept and which may be released,
2. how the kept replicas in each vault are packed onto fresh tape volumes,
3. whether the estate census reconciles, because nothing is published when it does not.

The plan is produced by a small program that the desk re-runs every cycle on that cycle's
export. The exports change shape from cycle to cycle, so the program must read the rules from
the documents in this folder and never from memory of an earlier cycle.

## 2. Where the rules live

| Topic | Document |
|---|---|
| Governing rules, classes, holds, precedence between documents | `retention_charter.md` |
| Dated changes to the charter | `charter_amendment_01.md`, `charter_amendment_02.md`, `charter_amendment_03.md` |
| Tape volume layout and packing order | `volume_layout.md` |
| Output files, field names, sort orders, status literals | `plan_output_contract.md` |
| Margao XML export | `margao_export_readme.md` |
| Kolhapur fixed width catalogue and binary index | `kolhapur_index_format.md` |
| Ratnagiri JSON lines export | `ratnagiri_changelog.md` |
| Collections, segments, classes, ingest years | `catalogue.db` (SQLite, table `collection`) |
| Census of every input file | `estate_census.toml` |
| Plan id and scenario dates | `run_control.json` |

Several older desk papers are also in this folder. They were written before charter version 4
and most of what they say has been replaced. Section 10 of the charter names the one item in
each of them that is still in force. Read that section before trusting any older paper.

## 3. The four vaults

| Code | Vault | Export family | Notes |
|---|---|---|---|
| KLH | Kolhapur | `kolhapur_catalogue_NN.dat` with `kolhapur_index_NN.idx` | fixed width text plus a binary index, joined per shard |
| MRG | Margao | `margao_inventory_NN.xml` | namespaced XML, digests encoded, some legacy collection ids |
| NSK | Nashik | `nashik_manifest_NN.csv` | standard CSV with a header row, RFC 4180 quoting |
| RTN | Ratnagiri | `ratnagiri_objects_NN.jsonl` | one JSON object per line |

Every family is split into four numbered shards. A shard holds an arbitrary slice of its vault;
shard numbers carry no meaning beyond the format notes in the changelogs. Vault codes are
always written in upper case and sort in the order KLH, MRG, NSK, RTN.

## 4. Primer

A **replica** is one row in a vault export. It names a stored file by its path inside the vault
and gives the file's exact size in bytes and its SHA-256 digest. Two rows that carry the same
digest are copies of the same **object**, whether they sit in the same vault or in different
vaults. An object belongs to the collection named on each of its rows; rows of one object can
name different collections, and then the object belongs to all of them.

A **collection** has a segment (`commercial` or `public`), a retention class and an ingest year,
all held in `catalogue.db`. The retention class sets how many vaults must hold the object.
The rendition (master, mezzanine or proxy) lowers that number for derived files.

A **volume** is one tape cartridge. Every kept replica in a vault is written to exactly one
volume of that vault. Volumes are filled in a fixed order so that two runs of the plan give
the same volumes.

## 5. Glossary

- **as_of date**: the scenario date from `run_control.json`. Every rule is evaluated as of
  this date.
- **required replicas**: the number of distinct vaults that must hold an object on the as_of
  date, after the charter, its amendments and the rendition rule are applied.
- **governing collection**: the collection whose class sets the required replicas of an
  object; charter section 6 says how it is chosen when there are several.
- **duplicate**: a second or later row of the same object inside the same vault.
- **sidecar**: a small companion file that is not planned at all; see charter section 9.
- **under replicated**: an object that sits in fewer distinct vaults than it requires.
- **held**: an object whose collection is under legal hold on the as_of date.
- **footprint**: the bytes a replica occupies on tape, defined in `volume_layout.md`.
- **usable capacity**: the bytes of a volume that may carry footprints.
- **fill_bps**: used bytes of a volume as basis points of its usable capacity.
- **census**: the list in `estate_census.toml` of every input file with its byte count,
  SHA-256 and, for record files, its record count.

## 6. How records are counted for the census

| File kind | One record is |
|---|---|
| `nashik_manifest_NN.csv` | one data row after the header row |
| `margao_inventory_NN.xml` | one `inv:obj` element |
| `ratnagiri_objects_NN.jsonl` | one non empty line |
| `kolhapur_catalogue_NN.dat` | one non empty line |
| `kolhapur_index_NN.idx` | one 44 byte index record after the 12 byte header |
| `legal_holds.psv`, `collection_crosswalk.tsv` | one data line after the header line |

A census entry without a `records` key is checked on bytes and SHA-256 only. The census does
not list itself.

## 7. Cycle calendar

The first scenario of this cycle falls on 2024-03-26 and the last on 2025-04-25. Amendment dates are
in the amendments themselves; do not infer them from this calendar.
