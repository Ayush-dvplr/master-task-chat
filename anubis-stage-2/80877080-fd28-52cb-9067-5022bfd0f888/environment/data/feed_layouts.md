# Feed and file layouts

Every query-log feed is one of the 16 layouts below. The ingest manifest
(`ingest_manifest_r7.json`) gives each listed shard its layout, timestamp convention,
volume unit and code maps; the columns are always the ten facts of a query: query id,
start, project token, cluster token, template id, warehouse size, scanned volume,
cache option code, status code and revision. Field names differ by layout.

## Query-log layouts

- `jsonl_flat`: one JSON object per line with keys `qid`, `start`, `proj`, `clu`,
  `tpl`, `wh`, `gib` (a decimal string), `opt`, `st`, `rev`.
- `ndjson_nested`: one JSON object per line. `query.id`, `query.rev`, `scan.start`,
  `scan.mib` (a JSON number), `ctx.project`, `ctx.cluster`, `ctx.template`,
  `ctx.size`, `bill.option`, `bill.status`.
- `csv_a`: comma separated with header `query_id,started_utc,project_id,cluster,template_id,wh_size,scanned_gib,cache_option,query_status,revision`.
- `tsv_epoch`: tab separated with header `rev epoch_s proj clu tpl wh scan_kib opt st id`
  (the query id is the last column).
- `psv_local`: pipe separated with header `id|clu|local_start|proj|tpl|wh|gib|opt|st|rev`.
  `local_start` is `YYYY-MM-DD HH:MM:SS` wall time.
- `txt_fixed`: fixed width text. Lines starting with `#` are comments. Columns
  (1-based, inclusive): query id 1-12, UTC start 13-26, project 27-38, cluster 39-63,
  template 64-73, size 74-77, volume 78-89 (right aligned), option 90-91, status 92,
  revision 93-95. Text columns are padded with spaces on the right.
- `xml_attr`: `<querylog>` root with one `<q>` element per query and attributes `id`,
  `t`, `p` (project), `c` (cluster), `tp` (template), `w` (size), `g`, `o`, `s`, `v`
  (revision).
- `yaml_list`: a `records:` list; each item has `id`, `start`, `project`, `cluster`,
  `template`, `size`, `gib`, `option`, `status`, `rev`. Values can be quoted.
- `json_array`: one JSON document; the rows are `export.rows`, each with `queryId`,
  `epochMillis`, `projectId`, `clusterCode`, `templateId`, `whSize`, `scannedMib`
  (a JSON number), `option`, `status`, `revision`.
- `sqlite_rows`: SQLite database, table `query_log` with columns `query_id`,
  `started_utc`, `project_id`, `cluster`, `template_id`, `wh_size`, `scanned_gib`,
  `cache_option`, `query_status`, `revision`. Table `export_note` is metadata.
- `db_rows`: SQLite database, table `ql` with columns `qid`, `ep` (epoch seconds),
  `prj`, `clu`, `tpl`, `wh`, `cg` (integer volume), `oc`, `sc`, `rv`.
- `csv_offset`: comma separated, UTF-8 with a byte order mark, header
  `cluster,ts_offset,project,template,size,kib,opt,code,rev,query` (`code` is the
  status).
- `xml_elem`: `<batch>` root with one `<query>` element per query and children `id`,
  `epoch`, `project`, `cluster`, `template`, `size`, `gib`, `option`, `status`, `rev`.
- `yml_list`: a top-level YAML list; each item has `qid`, `local` (wall time), `prj`,
  `clu`, `shape`, `gib`, `o` (option), `s` (status), `rev`. `shape` is the size, `@`
  and the template id (for example `2xl@OLAP-0412`).
- `json_keyed`: one JSON object keyed by query id; each value has `ms` (epoch
  milliseconds), `p`, `c` (cluster), `t` (template), `w` (size), `mib` (a JSON
  number), `o`, `s`, `v` (revision). A key can carry leading spaces.
- `txt_kv`: one line per query of space separated `key=value` pairs: `query`, `at`
  (wall time with a `T`), `project`, `cluster` (double quoted, may contain spaces),
  `template`, `size`, `gib`, `option`, `state`, `rev`. Lines starting with `#` are
  comments.

The volume column holds whatever unit the shard's `qty_unit` names, whatever the
column is called.

## Reference files

- `plan_profile_qa4.yml`: top-level scalars (`plan_id`, `org_id`, `billing_offset`,
  `lookback_start_local`, `lookback_end_local`, `horizon_end_utc`,
  `ruleset_track`, `published_plan`) and three lists: `clusters_in_scope` (items
  with `cluster`), `outage_windows` (items with `cluster`, `from_local`, `to_local`)
  and `dev_projects` (items with `project`). Cluster and project values are tokens.
- `cluster_aliases.yaml`: a `clusters:` list of items with `alias` and `canonical`.
- `proj_registry_main.csv`: `project_id,org_id,team,project_status,closed_on,tier`;
  `closed_on` is `YYYY-MM-DD` or blank.
- `proj_registry_archive.tsv`: `PROJ Org Team Status Closed Tier`, tab separated;
  `Closed` is `DD/MM/YYYY` or blank.
- `project_merges.psv`: `from_project|merged_into|merged_on|reason`; `merged_on` is
  `YYYY-MM-DD` (rulebook P1.4 gives the instant it takes effect).
- `scan_adjustments.jsonl`: one entry per line with `seq`, `status`, `op`, `query_id`
  and, by operation, `quantity_gib`, `project`, `usage_start_utc`, `cluster`,
  `template`, `size`, `option`.
- `scan_adjustments_late.xml`: `<entry seq= status=>` elements whose children are
  `op`, `query` (the query id) and the same optional fields as the JSON half.
- `cache_reservations.xml`: `<reservation>` elements with attributes `id`, `family`,
  `cluster` (a token), `owner` (a project token), `units`, `start_utc`, `end_utc`,
  `state`.
- `capacity_workbook_fy26.xlsx`: an Office Open XML workbook (a zip archive). Sheet
  names and their worksheet parts are linked through `xl/workbook.xml` and
  `xl/_rels/workbook.xml.rels`. Ruleset sheets carry `PLAN` rows (`key`, `value`)
  and `FAM` rows with columns `family`, `eligible`, `node_units`, `min_nodes`,
  `family_cap`, `growth_pct`, `tier_units`, `tier_discount_pct`,
  `mem_units_per_node`. `ScanFactors` has `engine`, `normalized_factor`. `Clusters`
  has `cluster`, `utc_offset`. `Adoptions` has `adoption_id`, `track`, `sheet`,
  `effective` (a date serial, rulebook P11.5), `status` (`ADOPTED`, `WITHDRAWN` or
  `PROPOSED`) and `note`. Cells are stored as shared strings, inline strings or
  numbers; a sheet can be hidden.
- `pricing_bulletin_q4.pdf`: a PDF whose page content streams are Flate compressed.
  Pages follow the order of the `/Kids` array of the `/Pages` object; page objects and
  content streams are not stored in page order in the file. Every table cell is its
  own text object (`BT` ... `ET`) placed at absolute coordinates by a `1 0 0 1 x y Tm`
  operator, and the text objects of a page are not stored in reading order. A cell's
  text is a literal string `(...)` shown with `Tj` (with `\(`, `\)` and `\\` escapes),
  a hexadecimal string `<...>` shown with `Tj` (two hex digits per Latin-1 byte, either
  case), or a `TJ` array of literal and hexadecimal strings that are joined in order
  (the numbers in a `TJ` array are spacing adjustments and never stand for text). The
  cells of one row share the same `y`; rows read from the top of the page (larger `y`)
  down, and cells from left (smaller `x`) to right. The line at the foot of each page
  is a page number. Tables continue across pages under a `(continued)` heading that
  repeats the column header. Table R-2 columns are `family`, `cluster`,
  `scan_rate_cents`, `node_rate_cents`; Table E-1 columns are `erratum_id`,
  `family`, `cluster`, `field`, `new_value`, `status`; Table C-1 columns are
  `reservation_id`, `ruling`, `revised_end_utc` (`-` when none); Tables M-0 and M-1
  columns are `cluster` (a token), `min_nodes`.
- The published plan named by the profile has one row per pool and team:
  `pool_id,team,nodes,cache_units,saving_cents,ruleset_used`. `nodes` repeats the
  pool's published node count on every row of the pool; the pool's published saving is
  the sum of `saving_cents` over its rows.

## Other files in the folder

- `scan_rates_digest_draft.txt`: plain text, a circulated digest of flat rates and
  notes.
- `capacity_announce_oct.txt`: plain text, a capacity announcement with node figures,
  provisional commitments and an approval log.
- `platform_calendar.yaml`: a planning calendar with scalar bounds and an `events:`
  list.
- `engine_factor_hint.json`: a client-side cache of engine factors.
- `hit_ratio_dashboard.csv`: `pool_id,day_utc,hit_ratio_pct,node_utilization_pct`, one
  row per pool and day.
- `scan_rollup_cache_03.jsonl`: records shaped like the `jsonl_flat` layout.
- `ops_tickets.ndjson`: one tenant ticket per line with `ticket`, `project`, `opened`,
  `symptom`, `channel`.
- Other files shaped like query-log exports can appear in a corpus; P2 decides whether
  they are feeds.

## Appendix T. Query template catalog

Every template id a feed or an adjustment can carry, with the workload family it belongs to. The
letters before the dash of a template id are where the template was first registered; templates
are re-homed between families over time, and this table is the only record of the family in force.
`owner_team` and `status` are informational.

| template_id | family | owner_team | status |
|---|---|---|---|
| DSHX-3100 | DSHX | TEAM-CORE | active |
| LOGS-5023 | LOGS | TEAM-RISK | retired |
| SRCH-2682 | SRCH | TEAM-SUPPLY | active |
| MLF-9087 | Mlf | TEAM-DATA | active |
| OLPX-9681 | Olpx | TEAM-GROWTH | active |
| MLF-6584 | mlf | TEAM-PAYMENTS | active |
| DSHX-1685 | DSHX | TEAM-MOBILE | active |
| ADHX-4168 | adhx | TEAM-MOBILE | active |
| ETL-0954 | etl | TEAM-CORE | active |
| OLPX-3972 | olpx | TEAM-DATA | active |
| GRPH-1846 | grph | TEAM-MOBILE | active |
| ADHX-9047 | adhx | TEAM-SEARCH | retired |
| DASH-6240 | dash | TEAM-MEDIA | active |
| TSR-4931 | Tsr | TEAM-SEARCH | active |
| ADHX-2599 | adhx | TEAM-SEARCH | active |
| GEO-4691 | GEO | TEAM-SUPPLY | active |
| DASH-2200 | DASH | TEAM-GROWTH | active |
| ADHX-5967 | srch | TEAM-MEDIA | active |
| TSR-5579 | tsr | TEAM-GROWTH | active |
| MLF-1164 | MLF | TEAM-GROWTH | active |
| OLAP-2874 | olap | TEAM-SEARCH | active |
| TSR-2021 | tsr | TEAM-PEOPLE | active |
| DASH-9936 | dash | TEAM-SEARCH | active |
| ETL-8676 | ADHX | TEAM-RISK | active |
| MLF-6701 | mlf | TEAM-MEDIA | active |
| ETL-5664 | Etl | TEAM-RISK | retired |
| DSHX-3309 | DSHX | TEAM-DATA | active |
| ADHX-3836 | adhx | TEAM-SUPPLY | active |
| OLAP-9812 | OLAP | TEAM-CORE | active |
| ADHC-1891 | adhc | TEAM-MEDIA | active |
| TSR-0611 | tsr | TEAM-GROWTH | active |
| RPT-2251 | rpt | TEAM-MEDIA | active |
| GRPH-7970 | grph | TEAM-PEOPLE | active |
| DASH-6866 | Dash | TEAM-SUPPLY | active |
| ADHX-7152 | Adhx | TEAM-CORE | active |
| MLF-9632 | mlf | TEAM-RISK | active |
| GEO-4503 | GEO | TEAM-SEARCH | active |
| TSR-8196 | TSR | TEAM-SUPPLY | active |
| ADHX-8271 | Arch | TEAM-PEOPLE | active |
| ETLX-0847 | ADHX | TEAM-RISK | active |
| ETLX-0566 | Etlx | TEAM-CORE | active |
| TSR-4278 | tsr | TEAM-RISK | active |
| GEO-6996 | geo | TEAM-MEDIA | active |
| LOGS-6466 | logs | TEAM-PAYMENTS | active |
| ARCH-8397 | arch | TEAM-MOBILE | active |
| DASH-4097 | Dash | TEAM-PAYMENTS | active |
| ADHC-5427 | adhc | TEAM-PAYMENTS | active |
| ETL-0313 | etl | TEAM-SUPPLY | active |
| ADHX-7697 | ADHX | TEAM-SEARCH | active |
| ARCH-7707 | ARCH | TEAM-GROWTH | active |
| LOGS-6520 | logs | TEAM-RISK | active |
| ETL-7727 | logs | TEAM-DATA | active |
| ADHC-1933 | adhc | TEAM-GROWTH | active |
| DASH-7487 | Dash | TEAM-SUPPLY | active |
| ETLX-8670 | etlx | TEAM-PEOPLE | active |
| MLF-1860 | mlf | TEAM-RISK | active |
| GEO-2988 | Geo | TEAM-GROWTH | active |
| GEO-9174 | geo | TEAM-GROWTH | active |
| GRPH-0795 | Grph | TEAM-MEDIA | active |
| OLPX-4673 | OLPX | TEAM-RISK | active |
| DSHX-3429 | dshx | TEAM-RISK | active |
| TSR-7417 | tsr | TEAM-DATA | active |
| OLPX-4251 | olpx | TEAM-MEDIA | active |
| GRPH-6571 | Grph | TEAM-GROWTH | active |
| GEO-0810 | GRPH | TEAM-SEARCH | active |
| OLAP-5250 | OLAP | TEAM-MOBILE | active |
| OLAP-1129 | OLAP | TEAM-CORE | active |
| LOGS-8545 | logs | TEAM-CORE | active |
| OLAP-7330 | OLAP | TEAM-CORE | active |
| SRCH-4891 | GEO | TEAM-PAYMENTS | active |
| OLAP-5891 | OLAP | TEAM-MOBILE | active |
| RPT-9583 | rpt | TEAM-SUPPLY | active |
| ARCH-2036 | ARCH | TEAM-SUPPLY | active |
| TSR-8072 | MLF | TEAM-CORE | active |
| DASH-6285 | dash | TEAM-PAYMENTS | active |
| OLAP-9609 | ADHX | TEAM-SEARCH | active |
| OLAP-6145 | OLAP | TEAM-PAYMENTS | active |
| ADHX-6681 | Adhx | TEAM-GROWTH | active |
| ARCH-7351 | arch | TEAM-DATA | active |
| ARCH-1919 | arch | TEAM-MEDIA | active |
| OLPX-9572 | OLPX | TEAM-CORE | active |
| ETLX-5944 | Etlx | TEAM-SUPPLY | active |
| ADHX-5823 | ADHX | TEAM-PEOPLE | active |
| MLF-8398 | srch | TEAM-SEARCH | active |
| ETLX-8646 | etlx | TEAM-DATA | active |
| OLPX-3008 | olpx | TEAM-SEARCH | active |
| ARCH-7191 | Arch | TEAM-PEOPLE | active |
| OLAP-0177 | olap | TEAM-CORE | active |
| OLPX-8582 | olpx | TEAM-DATA | retired |
| LOGS-5559 | LOGS | TEAM-MOBILE | active |
| LOGS-9500 | logs | TEAM-PEOPLE | active |
| DSHX-8169 | dshx | TEAM-PEOPLE | active |
| DASH-7064 | dash | TEAM-SUPPLY | active |
| LOGS-7242 | logs | TEAM-RISK | active |
| TSR-1394 | TSR | TEAM-PEOPLE | active |
| RPT-0345 | Rpt | TEAM-GROWTH | active |
| DSHX-1356 | arch | TEAM-PAYMENTS | active |
| RPT-5603 | RPT | TEAM-RISK | active |
| LOGS-3208 | Logs | TEAM-RISK | active |
| OLAP-6864 | OLAP | TEAM-MOBILE | active |
| OLPX-8430 | olpx | TEAM-RISK | active |
| OLPX-4339 | olpx | TEAM-DATA | active |
| DASH-4367 | DASH | TEAM-MEDIA | active |
| GRPH-3960 | Grph | TEAM-CORE | active |
| GRPH-8810 | GRPH | TEAM-GROWTH | active |
| RPT-3446 | rpt | TEAM-RISK | active |
| GEO-7403 | geo | TEAM-CORE | active |
| DASH-4266 | dash | TEAM-MOBILE | active |
| DSHX-3420 | dshx | TEAM-RISK | active |
| SRCH-1045 | srch | TEAM-SUPPLY | active |
| ETL-8206 | ETL | TEAM-MOBILE | active |
| TSR-3076 | tsr | TEAM-MEDIA | active |
| RPT-0643 | rpt | TEAM-MEDIA | active |
| MLF-6912 | mlf | TEAM-SEARCH | active |
| ETLX-1181 | etlx | TEAM-MOBILE | retired |
| SRCH-1898 | srch | TEAM-DATA | retired |
| DSHX-2147 | DSHX | TEAM-DATA | active |
| LOGS-7915 | Logs | TEAM-MOBILE | active |
| ADHX-5487 | Olap | TEAM-PEOPLE | active |
| OLPX-9676 | OLPX | TEAM-RISK | active |
| DASH-9611 | DASH | TEAM-CORE | active |
| RPT-1924 | Rpt | TEAM-PAYMENTS | active |
| ETL-9036 | etl | TEAM-GROWTH | active |
| DSHX-9428 | Dshx | TEAM-SEARCH | active |
| GEO-9802 | geo | TEAM-DATA | active |
| TSR-9237 | ETL | TEAM-RISK | active |
| ETL-7056 | dshx | TEAM-GROWTH | active |
| ADHX-1878 | ADHX | TEAM-MEDIA | active |
| ETLX-7783 | etlx | TEAM-GROWTH | active |
| ARCH-8505 | arch | TEAM-DATA | active |
| RPT-6105 | RPT | TEAM-SUPPLY | active |
| ADHX-0192 | adhx | TEAM-CORE | active |
| ADHC-8148 | adhc | TEAM-PAYMENTS | active |
| ETLX-6818 | etlx | TEAM-PEOPLE | active |
| GRPH-0607 | grph | TEAM-SEARCH | active |
| ETLX-0354 | etlx | TEAM-RISK | active |
| GEO-1069 | Geo | TEAM-CORE | active |
| TSR-8354 | tsr | TEAM-SEARCH | active |
| OLAP-1012 | OLAP | TEAM-PAYMENTS | active |
| ADHX-7952 | adhx | TEAM-MEDIA | active |
| RPT-6852 | RPT | TEAM-MOBILE | active |
| GEO-5798 | geo | TEAM-SEARCH | retired |
| GRPH-6508 | grph | TEAM-PEOPLE | active |
| GEO-8124 | geo | TEAM-DATA | active |
| DSHX-4866 | Dshx | TEAM-SEARCH | active |
| ADHC-8789 | adhc | TEAM-PEOPLE | active |
| ADHC-3930 | adhc | TEAM-MOBILE | active |
| RPT-4086 | rpt | TEAM-PEOPLE | active |
| DSHX-2628 | Grph | TEAM-PEOPLE | retired |
| DASH-6765 | dash | TEAM-MOBILE | active |
| ADHC-3659 | Adhc | TEAM-PAYMENTS | active |
| ETL-6110 | adhx | TEAM-GROWTH | active |
| SRCH-8872 | srch | TEAM-GROWTH | active |
| ADHC-0195 | adhc | TEAM-SEARCH | active |
| ARCH-9584 | arch | TEAM-MOBILE | active |
| ETLX-5089 | ETLX | TEAM-GROWTH | active |
| LOGS-0646 | Logs | TEAM-PEOPLE | active |
| DASH-3075 | dash | TEAM-PEOPLE | active |
| DSHX-6481 | Adhx | TEAM-MEDIA | retired |
| LOGS-4256 | LOGS | TEAM-PEOPLE | active |
| SRCH-1029 | srch | TEAM-GROWTH | active |
| OLAP-1840 | Olap | TEAM-DATA | active |
| DSHX-1181 | DSHX | TEAM-PAYMENTS | active |
| ARCH-0387 | ARCH | TEAM-PAYMENTS | active |
| OLPX-2750 | Olpx | TEAM-SEARCH | active |
| ARCH-8181 | arch | TEAM-MEDIA | active |
| OLPX-7098 | tsr | TEAM-PEOPLE | active |
| SRCH-9961 | srch | TEAM-DATA | active |
| OLPX-4388 | olpx | TEAM-SUPPLY | active |
| OLPX-5554 | Logs | TEAM-DATA | active |
| RPT-5863 | ADHX | TEAM-MOBILE | active |
| DSHX-3364 | DSHX | TEAM-SEARCH | active |
| GRPH-0698 | Logs | TEAM-MEDIA | active |
| LOGS-6860 | logs | TEAM-GROWTH | active |
| MLF-1058 | mlf | TEAM-PEOPLE | active |
| GRPH-9920 | grph | TEAM-PAYMENTS | active |
| SRCH-3328 | srch | TEAM-MEDIA | active |
| GEO-0152 | geo | TEAM-PAYMENTS | retired |
| ADHC-6674 | adhc | TEAM-MOBILE | active |
| DSHX-8783 | dshx | TEAM-MOBILE | active |
| ETL-0422 | Rpt | TEAM-PEOPLE | active |
| DASH-8259 | Dash | TEAM-GROWTH | active |
| OLAP-1196 | olap | TEAM-PAYMENTS | active |
| LOGS-7375 | Logs | TEAM-PEOPLE | active |
| SRCH-1638 | srch | TEAM-MEDIA | active |
| GEO-9769 | Etl | TEAM-DATA | active |
| ARCH-1764 | ARCH | TEAM-MOBILE | active |
| GRPH-6173 | grph | TEAM-PAYMENTS | active |
| SRCH-4655 | Srch | TEAM-PEOPLE | active |
| MLF-8457 | mlf | TEAM-RISK | active |
| ARCH-0711 | ARCH | TEAM-MEDIA | active |
| ADHC-5900 | adhc | TEAM-MEDIA | active |
| OLPX-0226 | olpx | TEAM-PEOPLE | active |
| ETLX-5452 | Mlf | TEAM-GROWTH | active |
| OLAP-9029 | OLAP | TEAM-PEOPLE | active |
| ADHX-4631 | adhx | TEAM-RISK | active |
| GEO-3802 | geo | TEAM-DATA | active |
| RPT-4186 | RPT | TEAM-GROWTH | active |
| ADHX-7308 | adhx | TEAM-DATA | active |
| SRCH-4877 | Srch | TEAM-MOBILE | active |
| ADHC-5827 | adhc | TEAM-PEOPLE | retired |
| RPT-2431 | rpt | TEAM-PEOPLE | retired |
| ARCH-5637 | ARCH | TEAM-PAYMENTS | active |
| ADHC-3655 | ADHC | TEAM-PEOPLE | active |
| ETLX-2934 | etlx | TEAM-MOBILE | active |
| TSR-2625 | tsr | TEAM-PEOPLE | active |
| DASH-8656 | Dash | TEAM-DATA | active |
| MLF-7876 | Mlf | TEAM-SUPPLY | active |
| ETL-9031 | etl | TEAM-CORE | active |
| ETL-8895 | etl | TEAM-RISK | retired |
| ETLX-9114 | geo | TEAM-CORE | active |
| DSHX-6466 | Dshx | TEAM-MOBILE | retired |
| GEO-8593 | Geo | TEAM-GROWTH | active |
| ADHC-2592 | Adhc | TEAM-DATA | active |
| SRCH-2734 | srch | TEAM-PEOPLE | active |
| SRCH-2428 | adhx | TEAM-SUPPLY | active |
| ETL-1038 | etl | TEAM-CORE | active |
| ETLX-4747 | ETLX | TEAM-DATA | active |
| GRPH-1447 | GRPH | TEAM-SUPPLY | active |
| MLF-1779 | mlf | TEAM-PEOPLE | active |
| ADHC-4681 | adhc | TEAM-PEOPLE | active |
| OLAP-1226 | OLAP | TEAM-SEARCH | active |
| TSR-2138 | tsr | TEAM-RISK | active |
| MLF-6240 | mlf | TEAM-MOBILE | active |
| ETLX-3785 | RPT | TEAM-CORE | active |
| TSR-8618 | tsr | TEAM-MOBILE | active |
| GRPH-1927 | grph | TEAM-PEOPLE | active |
| ADHC-7202 | adhc | TEAM-RISK | active |
| MLF-6655 | Mlf | TEAM-MEDIA | retired |
| ETL-5551 | etl | TEAM-PAYMENTS | active |
| OLPX-5583 | olpx | TEAM-MEDIA | active |
| RPT-6720 | rpt | TEAM-MEDIA | retired |
| ETL-3784 | Etl | TEAM-DATA | active |
| ARCH-1248 | arch | TEAM-MEDIA | active |
| MLF-1425 | mlf | TEAM-PAYMENTS | active |
| ARCH-4331 | arch | TEAM-DATA | active |
| SRCH-5617 | Srch | TEAM-SEARCH | active |
| ARCH-1443 | arch | TEAM-GROWTH | active |
| ETL-5884 | etl | TEAM-MOBILE | active |
| GEO-0329 | geo | TEAM-PEOPLE | active |
| SRCH-5633 | dash | TEAM-RISK | active |
| TSR-9440 | tsr | TEAM-DATA | active |
| GRPH-6368 | grph | TEAM-DATA | active |
| ADHC-9316 | adhc | TEAM-RISK | active |
| GRPH-5936 | GRPH | TEAM-GROWTH | active |
| RPT-2314 | rpt | TEAM-RISK | active |
| DASH-2210 | dash | TEAM-PEOPLE | active |
| RPT-1764 | rpt | TEAM-MEDIA | active |
| OLAP-3396 | olap | TEAM-PEOPLE | active |
| LOGS-8871 | logs | TEAM-SEARCH | active |
| SRCH-6323 | srch | TEAM-DATA | active |
| ETLX-2212 | etlx | TEAM-RISK | active |
| LOGS-6686 | Logs | TEAM-MOBILE | active |
| GRPH-3843 | GRPH | TEAM-DATA | active |
| MLF-0525 | MLF | TEAM-RISK | active |
| LOGS-6755 | logs | TEAM-CORE | active |
