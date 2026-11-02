# Register field dictionary

## Canonical envelope fields

The crosswalk maps every register export column to one of these fields.

| field | meaning |
|---|---|
| env_code | envelope code |
| file_no | file number of the folder holding the envelope |
| label | the envelope's label, in its own letter case; labels differ between the envelopes of one household |
| category_code | category code (std_codes.md) |
| funding_code | funding code (std_codes.md) |
| need_dollars | need, whole dollars, at least 1 |
| opening_cents | opening cents |

env_a.csv is comma separated and env_b.tsv tab separated, each with a header row of its own column names. env_c.jsonl holds one JSON object per line, keyed by its own column names. Numbers in the csv and tsv exports are written as decimal digits. Every text value in the register and the transaction exports is ASCII. Every .csv file of the extract is a comma-separated file as RFC 4180 defines it.

## hh_core.sqlite

hh_core.sqlite is a SQLite 3 database file.

| table | columns |
|---|---|
| district | district_id, district_name |
| household | hh_code, family_name, district_id |
| file | file_no, hh_code |
| env_alias | alias, env_code, since |
| keep_plan | env_code, plan |

## Copies

hh_mirror.csv is a copy of the envelope register kept for the households' own spreadsheets, written with the canonical field names. Where it and the register of record differ, the register of record governs.
