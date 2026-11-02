# Feed layouts

Record shapes of every exposure and order layout named in `ingest_catalog_w26.json`.
The catalog entry of a shard gives its stream, timestamp convention, status codes and,
for orders, its amount unit; this file gives where each field sits. Field meanings:

- exposure: `id` (exposure id), `time`, `unit` (unit token), `experiment` (experiment
  token), `variant` (variant token), `status`, `revision`.
- order: `id` (order id), `time` (placed at), `unit` (customer token), `currency`,
  `amount`, `status`, `revision`.

Numbers written as JSON numbers are integers. Text values may carry stray whitespace and
mixed case (H1).

## Exposure layouts

### x_jsonl
One JSON object per line: `eid` id, `ts` time, `unit`, `exp` experiment, `arm` variant,
`st` status, `rev` revision.

### x_ndjson
One JSON object per line: `event.id` id, `event.rev` revision, `at.epoch` time,
`subject.unit` unit, `assign.experiment` experiment, `assign.variant` variant, `state`
status.

### x_csv
Comma separated with a header row and a UTF-8 byte order mark: `exposure_id`,
`logged_at`, `unit_token`, `experiment`, `variant`, `revision`, `status`.

### x_tsv
Tab separated with a header row: `rev`, `ms` (time), `unit`, `exp`, `variant`, `state`,
`exposure` (id).

### x_psv
Pipe separated with a header row: `exposure` (id), `experiment`, `local_time`, `unit`,
`variant`, `status`, `rev`. The time is a wall clock of the row's own experiment.

### x_txt
Fixed width text. Lines starting with `#` are comments. Columns (1-based, inclusive):
id 1-12, time 13-26, unit 27-37, experiment 38-53, variant 54-77, status 78, revision
79-81. Values are left aligned and padded with spaces; strip them.

### x_xml
`<exposures>` with one `<x>` element per row: attributes `id`, `t` time, `u` unit, `e`
experiment, `v` variant, `s` status, `r` revision.

### x_yaml
A YAML document whose `records` key holds a list of mappings: `id`, `ts`, `unit`,
`experiment`, `variant`, `status`, `rev`. Values may be quoted.

### x_sqlite
SQLite database, table `exposure`: `exposure_id`, `epoch_s` (time), `unit_token`,
`experiment`, `variant`, `status`, `revision`. Table `export_note` is metadata.

### x_json
One JSON document; `export.rows` is a list of objects: `exposureId`, `epochMillis`
(time), `unitToken`, `experimentKey`, `variantKey`, `state`, `revision`.

## Order layouts

### o_db
SQLite database, table `ord`: `oid` id, `ep` time, `uid` unit, `ccy` currency, `amt`
amount, `st` status, `rv` revision.

### o_csv
Comma separated with a header row: `order_id`, `placed_at`, `customer`, `currency`,
`amount`, `order_status`, `revision`.

### o_xml
`<orders>` with one `<order>` element per row and child elements `id`, `at` time,
`customer`, `ccy`, `minor` amount, `st`, `rev`.

### o_yml
A YAML list of mappings: `order` id, `local` time, `cust` unit, `money` (amount and
currency separated by one space, for example `'12.5 EUR'`), `s` status, `rev`.

### o_json
One JSON object keyed by order id; each value has `ms` time, `u` unit, `c` currency,
`a` amount, `s` status, `v` revision. A key repeated within one file is written with
extra leading spaces so the object stays valid; the id is the key stripped (H1).

## Reference files

- `identity_links.psv`: `from_id|linked_to|linked_on|link_source`; `linked_on` is a
  `YYYY-MM-DD` date (H1.5).
- `unit_registry_main.csv`: `unit_id,country,signup_date,account_type,lifecycle`.
- `unit_registry_legacy.tsv`: `UNIT	Country	Signup	AccountType`.
- `refund_journal.jsonl`: one object per line with `seq`, `status`, `refund_id`,
  `order_id`, `amount_minor`, `currency`, `posted_utc`, `desk` and, on some lines,
  `kind`.
- `refund_journal_late.xml`: `<refunds>` with `<refund seq=".." status="..">` elements,
  some carrying a `kind=".."` attribute, and children `id`, `order`, `minor`, `ccy`,
  `posted`.
- `experiment_aliases.yaml`: lists `experiments` (`alias`, `canonical`) and `variants`
  (`experiment`, `variant`, `arm`).
- `analysis_profile_w26.yml`: scalar settings (among them `registry_version` and
  `fx_sheet`, each naming a workbook sheet) plus the lists `experiments_in_scope`
  (`experiment`) and `internal_units` (`unit`).
- `experiment_workbook_w26.xlsx`: sheets `README`, metric registries (`MR-6`, `MR-7`,
  `DRAFT_MR-8`), `Experiments` (`experiment`, `tz_offset`, `start_local`, `end_local`,
  `primary_metric`, `owner_team`), `Allocation`, two FX releases (`FX-R1`, `FX-R2`:
  `date`, `currency`, `quote`, `rate`) and `Currencies`. Text cells may be shared or
  inline strings; numbers may be stored as text with surrounding spaces; boolean
  cells are written `Y`/`yes`/`TRUE` or `N`/`no`/`FALSE`. Sheets are found by their
  name in `xl/workbook.xml` through `xl/_rels/workbook.xml.rels`, not by part file
  name. A date cell is either text (`YYYY-MM-DD` or `YYYY-MM-DDTHH:MM:SS`) or a numeric
  serial day count in the workbook's date system. This workbook declares
  `<workbookPr date1904="1"/>`: serial 0 is 1904-01-01T00:00:00 and serial N is N days
  later (a fractional part would be the time of day). Example: serial 40000 is
  2013-07-07 and serial 40000.5 is 2013-07-07T12:00:00.
- `stats_governance_memo_w26.pdf`: Tables P-0, P-1, C-0, C-1, A-0, A-1, X-1 and U-1.
  Each page has one FlateDecode content stream (the `/Length` and `/Filter` keys appear
  in either order). Text is placed with absolute text matrices: an operator
  `1 0 0 1 x y Tm` sets the position of the run that follows it, and the runs of a
  page are drawn in no particular order, several runs sometimes sharing one `BT` ...
  `ET` block. A run's text is a literal string `(...)` shown with `Tj` (backslash
  escapes `\(`, `\)` and `\\` stand for those characters), a hexadecimal string
  `<...>` shown with `Tj` (each pair of hex digits is one latin-1 byte), or an array
  shown with `TJ` whose strings, literal or hexadecimal, concatenate in order (the
  numbers between them are spacing adjustments and add no characters). A text line is
  the set of runs on one page with the same y; its cells are those runs ordered by x
  ascending, and lines are read top to bottom (y descending), pages in page-tree
  order. A table starts at a line `Table X-N ...` and its next line is the header; a
  long table continues on later pages under a line `Table X-N (continued)` and a
  repeated header line. Example: the runs `1 0 0 1 126 500 Tm <4E4F> Tj` and
  `1 0 0 1 40 500 Tm [(ye) -12 (s)] TJ` form the line `yes | NO`.
