# Rule excerpt (data product config compiler contract)

## Identifiers

Product ids are compared after converting them to upper case and removing every hyphen. This canonical form is the one
every output document writes. Owner names, team names, tiers, labels and setting keys are compared exactly as written.

## Dates

Dates are calendar dates written YYYY-MM-DD and compare in calendar order. A deprecation.log event is dated by the calendar date
in UTC of the instant its RFC 3339 timestamp names.

## Glossary

- Assignment of an owner on date D: of the owner's owners.csv rows with active_from on or before D, the one with the
  latest active_from.
- Active owner on date D: an owner whose assignment on D has active_to empty or on or after D, and who has no
  `RETIRE owner=<owner>` event in deprecation.log dated on or before D. Their team on D is the team of their assignment
  on D.
- Status of a catalog product on D: `retired` when deprecation.log has a `RETIRE product=<id>` event for it dated on or
  before D; otherwise `active` when its owner is an active owner on D; otherwise `orphaned`.
- Team of a product: for an active product, its owner's team on D; for an orphaned or a retired product, null.
- Compiled product: an active or an orphaned product. Retired products appear in config.json but are not compiled.

5. `owners.csv`: header `owner,team,active_from,active_to`; one row per assignment of an owner to a team. An empty
   active_to means the assignment is open. An owner may have several rows; no two rows of one owner share an
   active_from.
6. `deprecation.log`: one event per line, `<timestamp> <KIND> <field>=<value> ...`. Two kinds of event count:
   `RETIRE product=<product id>` retires a product and `RETIRE owner=<owner>` retires an owner. Every other line
   (NOTICE, INFO and so on) is ignored. The file is not in time order.
7. `selectors.rules`: one rule per line, `match <field>:<name> set <setting key> <value>`, where field is `team`,

### Text layers
base_layer.yaml, the setting lines of products.ini, selectors.rules and the env files are text layers. A value written
inside one pair of double quotes is read without the quotes, so a quoted value and a bare value read alike. The text is
then read by the schema type of its key: integer as one or more of the digits 0 to 9; boolean as `true` or `false` in
any letter case; enum and string as written; list as items separated by commas, each item trimmed of surrounding
spaces, with empty text giving the empty list. Text that does not read as its key's type is passed over, and the key
keeps the value the earlier layers gave it. Every text-layer key is in the schema, and text layers never list anything
in validation_report.json.

## Quota

config.json hands out the `shared` quota of cluster_quota.json, profile_dev.json the `dev` quota and profile_prod.json
the `prod` quota. In each document, with Q the quota and W the sum of the resolved `weight` over all active products in
that document, an active product with weight w first gets the integer part of Q x w / W; the units left over then go
one each to the active products in descending order of the remainder of Q x w divided by W, products with equal
remainders in ascending product id order.

A product whose settings in that document carry `quota_cap` and that holds more units than its cap gives the excess
back and keeps its cap. Every product keeps the units it holds. The units given back are handed out again by largest
remainder in proportion to weight among the products still holding less than their cap or carrying no cap, with Q the
units given back and W the sum of their weights, and each cap applies again after the round. This repeats until a
round gives nothing back; units that no product can take are not handed out. Orphaned and retired products get quota
0 in config.json.


## Sample data (first lines)
```
owner,team,active_from,active_to
h.silva6,finance,2022-09-10,2023-01-06
a.varga,media,2027-02-28,
g.ferreira2,ingest,2020-10-04,2021-09-08
g.rahman,growth,2025-12-04,2026-03-24
w.kowalski,billing,2023-07-05,2024-01-04

2026-04-02T10:16:34Z RETIRE product=DP91050 ticket=DEP-2269
2024-07-28T16:45:44Z RETIRE product=DP90436 ticket=DEP-2270
2026-04-17T06:46:16Z RETIRE product=DP74429 ticket=DEP-2273
2024-05-09T08:06:55Z RETIRE product=DP63899 ticket=DEP-2278
2026-06-07T05:05:06Z NOTICE owner=w.haddad note=handover ticket=DEP-2267
2024-08-22T12:24:17Z NOTICE owner=w.sato note=reorg ticket=DEP-2268

partitions = 12
replicas = 1
retention_days = 1095
replicas = 1
retention_days = 60
retention_days = "60"
partitions = 1
partitions = "64"
```

## Interface to implement (Python 3.12 stdlib only), file `agent/pilot.py`

- `event_date(line: str) -> str`: the YYYY-MM-DD date a deprecation.log line is dated by.
- `retire_events(lines: list[str]) -> tuple[dict, dict]`: (product canonical id -> earliest RETIRE product date, owner -> earliest RETIRE owner date).
- `assignment(rows: list[dict], owner: str, d: str) -> dict | None`: rows are owners.csv rows as dicts (header keys); the assignment of the owner on d.
- `owner_team(rows, retired_owners: dict, owner: str, d: str) -> str | None`: the owner's team on d when the owner is an active owner on d, else None.
- `read_text(type_: str, text: str)`: read one text-layer value (already stripped of surrounding spaces) for a key of schema type `integer`, `boolean`, `enum`, `string` or `list`; return the value, or the sentinel `PASS` (module-level `PASS = object()`) when the text is passed over.
- `split_quota(q: int, products: dict[str, tuple[int, int | None]]) -> dict[str, int]`: products maps canonical id -> (weight, quota_cap or None) for the active products of one document; return each product's units.
