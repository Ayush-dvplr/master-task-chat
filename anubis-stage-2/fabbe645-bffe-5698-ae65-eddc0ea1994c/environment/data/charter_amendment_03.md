# Charter Amendment 03: Split of class R3

Approved by the Preservation Board on 2024-08-31.

1. From 2024-10-15 class R3 is replaced by two classes:

| Class | Collections | Minimum distinct vaults for a master |
|---|---|---|
| R3A | `ingest_year` earlier than 2006 | 1 |
| R3B | `ingest_year` 2006 or later | 3 |

2. The ingest year is the `ingest_year` column of table `collection` in `catalogue.db`.
3. R3A and R3B use the vault preference order of R3.
4. Before 2024-10-15 class R3 keeps the charter minimum.
