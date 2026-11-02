# KCBA Retention Charter, version 4

Adopted by the KCBA Preservation Board on 2023-09-08. This charter governs which replicas of
archive objects KCBA keeps, in which vaults, and how holds and exports are read for planning.

## 1. Authority and precedence

1. This charter is the governing document for replica planning.
2. A numbered amendment (`charter_amendment_NN.md`) changes this charter from the effective
   date it states, and only within the window and scope it states. Inside that window and
   scope the amendment prevails over this charter.
3. Where any older desk paper disagrees with this charter or an amendment, the charter or
   the amendment wins. Section 10 lists the single item that each older paper still
   decides.
4. The format notes for each vault export (`margao_export_readme.md`,
   `kolhapur_index_format.md`, `ratnagiri_changelog.md`) decide how an export is read. They
   do not change any planning rule.

## 2. Planning date

Every rule is evaluated as of the scenario's as_of date. A dated event counts when its date
is on or before the as_of date. A dated window counts when the as_of date lies between its
start and end dates, both ends included, unless the window says an end date is excluded.

## 3. Retention classes

| Class | Minimum distinct vaults for a master |
|---|---|
| R1 | 3 |
| R2 | 2 |
| R3 | 2 |
| R4 | 1 |

The class of a collection is the `retention_class` column of table `collection` in
`catalogue.db`, as changed by any amendment in force on the as_of date.

## 4. Collections and legacy ids

Every replica row names a collection. Rows from the Margao vault may carry a legacy id that
starts with `KCB-`; such an id is resolved to a current `KC-` id with
`collection_crosswalk.tsv` under the rule kept in force by section 10. All other rows carry
current ids.

## 5. Renditions

The class minimum applies to masters. A mezzanine file needs one vault fewer than the class
minimum, but never fewer than one. A proxy needs exactly one vault whatever its class.

## 6. Objects in several collections

When the rows of one object name more than one collection, each collection gives a minimum
through sections 3, 5 and the amendments. The object needs the largest of these. The
governing collection is the collection that gives this largest minimum; when several give
it, the governing collection is the one with the smallest collection id in plain text
order. The class of the governing collection, after amendments, is the class reported for
the object and decides the vault preference order.

## 7. Choosing the replicas to keep

1. Only distinct vaults count towards the required number. Inside one vault the replica
   whose `object_path` sorts first in plain byte order is the vault's primary replica. Every
   other replica of the object in that vault is a duplicate.
2. When an object is not held, keep the primary replica in the first vaults of the
   preference order of its reported class, taking only vaults that hold the object, until the
   required number is reached. Every other replica of the object, duplicates included, may be
   released.
3. When the object sits in fewer distinct vaults than it requires, keep every primary
   replica, release its duplicates, and report the object as under replicated.
4. The preference order for a class is the `vault_preference` column of
   `retention_schedule_2019.csv` (vault codes separated by `>`, most preferred first). Classes
   R3A and R3B use the order of R3.

## 8. Legal holds

1. `legal_holds.psv` is the hold register. Each line places or releases a hold on one
   collection.
2. A collection is under hold on the as_of date when the last of its events that counts on
   that date is a `PLACE`. Which events count, and which event is last when two fall on the
   same date, is decided by the item of `legal_hold_faq.md` kept in force by section 10.
3. A hold lasts until a `RELEASE`; no hold lapses on its own.
4. Every replica of an object that names a held collection on any of its rows is kept,
   duplicates included. The object is still reported with its required number and its
   under replicated flag.

## 9. Rows that are not planned

1. A sidecar is a file whose exact size in bytes is below the threshold kept in force by
   section 10. Sidecar rows are not planned, are not replicas of any object and are not
   packed. They are counted in the data quality report.
2. A row on a Nashik storage node that was decommissioned on or before the as_of date is not
   a replica on that date. The decommissioned node and its date are the finding kept in
   force by section 10. Such rows are left out of every planning step for that scenario and
   counted per scenario in the data quality report.

## 10. Older papers and the one item each still decides

| Paper | Item still in force | Everything else in the paper |
|---|---|---|
| `ops_handbook_2021.md` | the volume label format | replaced by `volume_layout.md` |
| `migration_memo_2023.md` | how a legacy id that maps to two collections is resolved | replaced |
| `sidecar_policy_note.md` | the sidecar size threshold | replaced |
| `legal_hold_faq.md` | which calendar date an event counts on, and the order of events on one date | replaced; see section 8 |
| `nashik_audit_2024.html` | the decommissioned node and its decommission date | other findings are advisory only |
| `kolhapur_tape_notes.txt` | the rendition letter codes of the Kolhapur catalogue | replaced by `kolhapur_index_format.md` |
| `retention_schedule_2019.csv` | the `vault_preference` column | `min_replicas` replaced by section 3 |
| `capacity_planning_2022.xlsx` | the `reserve_bytes` column of the Reserve sheet | capacities replaced by `media_catalogue.json` |

## 11. Publication

A plan is published only when every file listed in `estate_census.toml` is present and
matches its listed byte count, SHA-256 and record count. Otherwise the plan is held and the
reasons are reported as set out in `plan_output_contract.md`.
