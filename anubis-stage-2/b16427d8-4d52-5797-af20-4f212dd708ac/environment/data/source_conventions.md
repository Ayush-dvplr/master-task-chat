# Source conventions

Each source writes identifiers, numbers and instants in its own way. None of these conventions changes what a value means.
## Registries

| entity | registry | registered form |
|---|---|---|
| prompt | prompt_registry.csv | PRM-00001 |
| completion | completion_index.csv | CMP-000001 |
| comparison | batch_registry.xml | CMR-000001 |
| verdict | annotation_store.db | VD-0000001 |
| annotator | annotator_roster.csv | ANN-0001 |
| cluster | dedup_clusters.tsv | DUP-0001 |
| family | prompt_registry.csv | PF-0001 |
| workstation | workstation_inventory.ini | ws-0001 |
## Convention register

| convention | reading |
|---|---|
| identifier variants | An identifier written in the other letter case, with its zero padding stripped, with one Cyrillic look-alike letter, with full-width digits, or wrapped in non-breaking or trailing spaces names the registered identifier. |
| record layout | Every export carries records with the columns rid, par, val, at, fa and fb. A header band may rename them rec, pnt, val, ts, a and b; the columns underneath are the same. A header band can change in the middle of a file. |
| scaled values | A val column headed val_x1000 carries one thousand times the value. |
| grouped numbers | A dot, comma or space followed by exactly three digits is a thousands separator: 1.234 and 1,234 are both 1234. |
| excess precision | A value with exactly two decimal places carries excess precision and is rounded half to even to a whole number: 12.50 is 12. |
| sentinels | In a non-authoritative copy a val of -1 or N/A is absent, not a value. |
| instants | An instant is written as ISO 8601 UTC, as epoch milliseconds, as a spreadsheet serial day count since 1899-12-30 read to the nearest second, or as workstation local time YYYY-MM-DD HH:MM:SS.mmm. |
| local time | A local instant was read off the clock of the workstation the record names. UTC is the local time minus the zone offset and minus the clock offset that workstation_inventory.ini records for that workstation. |
| clock offset | The fb column of workstation_inventory.ini is the clock offset in seconds; a positive offset means the workstation clock runs ahead. |
| text case | Text cells can arrive upper-cased; compare them without regard to case. Locale codes resolve to de_DE, en_IN, en_US, es_ES, fr_FR and ja_JP. |
| byte-order mark | annotator_roster.csv begins with a UTF-8 byte-order mark that belongs to the file, not to the first field. |
| fixed width | clock_offsets.txt and legacy_verdicts.txt cut every cell to 18 characters, so they never govern an instant. |
| mixture targets | The fb column of mixture_targets.xlsx is the source's target weight in percent. |
## Zone offsets for the R7 quarter

| zone | offset |
|---|---|
| UTC | +00:00 |
| Europe/Berlin | +02:00 |
| America/Chicago | -05:00 |
| Asia/Kolkata | +05:30 |
| America/Sao_Paulo | -03:00 |
| Australia/Sydney | +10:00 |
| Europe/London | +01:00 |
