# TRUTH.md - 1950015d-de91-55a5-836b-dbbb74338883

## Defect

The shipped drop is a quarter end settlement extract that has never been
reconciled. The work is to turn it into one canonical ledger and twelve
roll-up artifacts. Each item below is the defect a solver has to see, with
its class in brackets.

- (focal) The quarter has no canonical ledger at all. Thirty two feeds in ten container formats hold overlapping copies of the same events and nothing in the drop is a settled record until the whole chain has run.
- (focal) Every reference registry is cut into disjoint shards across six to ten files, so a lookup that misses any single file silently loses between a tenth and a sixth of its keys.
- (focal) Repeated events resolve only through a per source and per kind authority ladder that lives in two registers, neither of which sits beside the feeds it ranks.
- (focal) Six of the reference dimensions are type two histories with a half open upper bound, so a boundary day resolves to the wrong version under the inclusive reading that most tooling defaults to.
- (focal) The reversal walk is stateful and ordered, so a credit cancels its target only when that target is still live at that point in the walk; a row the walk has not reached yet is live, a row that has already left is not, and a reversal that has already left does nothing when the walk reaches it.
- (focal) The posting date is derived in two steps, and the terminal lookup that decides the second step has to happen on the capture date rather than on the posting date it produces.
- (focal) Cent amounts come from one rounding step at the end of the chain, so per unit or per step rounding drifts the quarter total.
- (drift) A generalist reads an effective dated window as closed at both ends. The drop documents a half open upper bound, and the boundary rows are exactly the graded set.
- (drift) A generalist takes the posting date from the capture date for every row. The drop documents a trading day rule that applies to branch rows only, through the terminal's own offset.
- (drift) A generalist rounds money half up. The policy register names the mode, half even on the shipped drop, applied once, at the cent.
- (drift) A generalist reads a bracketed amount as a negative number. The contract takes the sign from the record kind and the magnitude from the brackets.
- (drift) A generalist validates the quantity column only where a quantity is meaningful. The contract validates it on every row and records zero for fee and credit rows afterwards.
- (drift) A generalist resolves a retired code until it stops changing. The crosswalk is a single hop registry: a few retired warehouse, terminal and item codes point at another retired code, so one hop lands on a code no registry carries and the row rejects as UNKNOWN_WAREHOUSE, UNKNOWN_TERMINAL or UNKNOWN_SKU, while a chained lookup reaches a live code and accepts it. The crosswalk also publishes carrier codes that no step looks up; some feed rows carry a carrier code where a warehouse belongs, and its carrier row points at a live warehouse, so following it accepts a row the contract rejects as UNKNOWN_WAREHOUSE.
- (trap) Padded identifiers differ from their canonical form by one to three leading zeros, so a literal comparison never sees the duplicate.
- (trap) Cyrillic homoglyphs stand in for ten Latin letters inside identifiers in four feeds, and the mapping table lives in a crosswalk override register.
- (trap) Three currencies carry no minor units and three carry three, so a fixed two place assumption is right for most rows and wrong for the rest.
- (trap) Six timestamp encodings appear across the feeds, including an Excel serial with a 1899-12-30 day zero and both second and millisecond epochs.
- (trap) Comma locale feeds group thousands with full stops, so a naive comma strip turns a decimal fraction into a thousand fold error.
- (trap) Sentinel rows carry an empty kind, an empty identifier, an all zero date or a non numeric amount, all of which reject as MALFORMED_ROW, or a written out or decimal quantity, which rejects as NON_NUMERIC_QUANTITY. Some step one sentinels also carry a written out quantity, so a solver that tests the quantity before the step one fields reports the wrong code.
- (trap) A few region and day pairs have no row for the named calendar variant, so a row that clears every earlier step still rejects as NO_FISCAL_WEEK.
- (trap) A few warehouse postal prefixes have a gap in their region history inside the quarter, so a warehouse that resolves still rejects as UNKNOWN_WAREHOUSE on those days.
- (trap) Voided events look live in every feed that carries them; the only register of them sits inside a notice board that reads as reporting.
- (trap) Five feeds are retired part way through the quarter, so the same file is authoritative before a date and superseded after it.
- (trap) A byte order mark leads a third of the published text files, which corrupts the first column name of a shard and makes the shard vanish.
- (trap) Filler lines appear inside the body of every line oriented file rather than only at the top: comment lines in every delimited, fixed width and log file, blank lines in every delimited file, and `_note` objects in every jsonl file.
- (trap) Price book windows carry deliberate gaps, so a sku can have a version before and after a posting date and none that covers it.
- (trap) The quote source the policy register names has scattered gaps and, for every non dollar currency, one outage exactly as long as the carry forward limit and one a day longer, so the limit decides whether a row converts or rejects as NO_FX_RATE.
- (trap) Non authoritative sources agree with the authoritative ones on the overwhelming majority of keys, so the disagreement is the graded set.
- (trap) A few reversals name their own event. The contract treats a reversal that names itself as an orphan, so reading it as an ordinary credit or as a cancelled pair moves the ledger and the rejection tally.
- (trap) Two counterparties each settle one identical fee large enough to lead their segment and their region. The feed lists the later identifier first, so only the documented ASCII tie break puts the pair in the graded order.
- (trap) The drop is reusable only if every policy value is read at run time. The second unseen drop publishes its own settlement window, minor unit table (ISK carries two places there), rounding mode (floor, one of the seven modes the contract names), homoglyph table (Greek letters join the Cyrillic ones), quote source, carry forward limit, calendar variant, scope windows, retirement dates and authority ladder, changes one feed's source profile, carries a feed shaped table inside a reference file that no source profile names, and carries no customer at all in one segment, whose file must still ship with empty maps and zero counts.
- (trap) Fifteen files look like a primary input or like noise and are neither, and the rule that settles each one lives in a different file.

### Load bearing concepts

| concept | why it is load bearing | checks that break without it (measured probes) |
| --- | --- | --- |
| Container and encoding normalization | nineteen container formats, four text encodings, byte order marks, filler lines and fixed width columns all reduce to the same twelve or five column table before a single rule runs | loops L13, L15, L16: quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop, summary_counts, summary_by_region, summary_by_segment, summary_by_category, summary_by_channel_group, summary_by_currency, summary_by_kind, quality_accepted_by_source, product_summary, region_files, segment_files, ledger_record_fields |
| Key canonical form and near duplicate resolution | homoglyph mapping, zero stripping, case folding and separator removal decide whether two rows are the same settlement event | loops L17, L18: summary_counts, summary_by_region, summary_by_segment, summary_by_category, summary_by_channel_group, summary_by_currency, summary_by_kind, quality_codes, quality_accepted_by_source, quality_rejected_by_source, product_summary, region_files, segment_files, ledger_identity, ledger_dimensions, ledger_money, ledger_record_fields, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop |
| Source authority and supersession | a per source and per kind ladder in two registers decides which copy of a repeated event survives, and a revision log retires a source from a date | loops L03, L39: quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop, quality_codes, source_supersession |
| Effective dated dimension lookup | parties, postal regions, items, warehouses, terminals and the price book are all type two histories read on a half open window | loops L04, L05: quality_codes, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop |
| Temporal derivation and trading day rules | six timestamp encodings, per source offsets and a branch only trading day rule decide the posting date that every later lookup uses | loops L06, L07: quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop |
| Stateful cross record resolution | the reversal walk is order dependent, so no row can be settled in isolation | loops L41, L42: quality_rejected_by_source, ledger_identity, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop |
| Currency arithmetic and a single rounding step | minor unit exponents, a named quote source, a carry forward limit and one half even rounding step produce the cent amount | loops L10, L11, L12: ledger_cent_amounts, hidden_drop, second_hidden_drop, ledger_money |
| Scope windows and referential integrity | scope registers, crosswalk resolution and the registry coverage test decide which rows reach the ledger at all | loops L19, L35: quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop |
| Reconciliation and declared invariants | the drop declares its own file count, settlement window and scope registers, which a wrong path visibly violates | loops L44, L52: quality_rejected_by_source, reversal_chain, hidden_drop, second_hidden_drop, quality_accepted_by_source |

Nine concepts, each one load bearing: removing a solver's understanding of
any single row above fails at least one check in the right hand column.
Concept output feeds concept input throughout. The canonical form decides
which rows are duplicates, the ladder decides which of those survives, the
posting date decides which registry version each survivor reads, the
registry version decides the region, and the region decides the fiscal week
lookup that can still reject the row.

## Load-bearing work

### The hundred files

Every file holds at least one fact that exists in no other file. Reference
registries are cut into disjoint shards by key, so a shard is the only copy
of its rows. Transaction feeds are the only copy of their events. Policy
registers are the only copy of the rule they carry.

| file | type | rows | role | unique contribution | policy it also owns |
| --- | --- | --- | --- | --- | --- |
| adjustment_queue_q4.jsonl | jsonl | 5000 | in-scope | transaction rows | none |
| archive_orders_2026.db | db | 5000 | decoy | transaction rows | none |
| branch_till_export_a.csv | csv | 5000 | in-scope | transaction rows | none |
| branch_till_export_b.csv | csv | 5000 | in-scope | transaction rows | none |
| code_crosswalk.db | db | 8865 | in-scope | xwalk shard 2 of 6 | none |
| code_crosswalk_core.xml | xml | 8687 | in-scope | xwalk shard 1 of 6 | none |
| code_crosswalk_legacy.txt | txt | 8883 | in-scope | xwalk shard 3 of 6 | none |
| code_crosswalk_notice.mbox | mbox | 8773 | decoy | xwalk shard 4 of 6 | none |
| code_crosswalk_overrides.ini | ini | 8769 | in-scope | xwalk shard 6 of 6 | identity_policy |
| code_crosswalk_supplement.yaml | yaml | 8829 | in-scope | xwalk shard 5 of 6 | scope_registry |
| consolidated_settlement_extract_final.xlsx | xlsx | 5000 | decoy | transaction rows | none |
| contract_billing_run.csv | csv | 5000 | in-scope | transaction rows | none |
| counterparty_notice_board.html | html | 6390 | decoy | customers shard 8 of 8 | voids |
| credit_memo_workbook.xlsx | xlsx | 5000 | in-scope | transaction rows | none |
| dw_fact_sales_snapshot.tsv | tsv | 5000 | decoy | transaction rows | none |
| field_service_tickets.tsv | tsv | 5000 | in-scope | transaction rows | none |
| fiscal_calendar_board.html | html | 5490 | in-scope | calendar shard 5 of 6 | none |
| fiscal_calendar_core.csv | csv | 5756 | in-scope | calendar shard 1 of 6 | none |
| fiscal_calendar_extract.xlsx | xlsx | 5790 | in-scope | calendar shard 3 of 6 | none |
| fiscal_calendar_notes.docx | docx | 5729 | in-scope | calendar shard 4 of 6 | none |
| fiscal_calendar_policy.yaml | yaml | 5610 | in-scope | calendar shard 6 of 6 | calendar_policy |
| fiscal_calendar_variants.json | json | 5819 | in-scope | calendar shard 2 of 6 | none |
| fx_policy_register.toml | toml | 5259 | in-scope | fx shard 6 of 8 | fx_policy |
| fx_rate_appendix.pdf | pdf | 5249 | in-scope | fx shard 7 of 8 | none |
| fx_rate_commentary.docx | docx | 5252 | in-scope | fx shard 8 of 8 | none |
| fx_rates_board.json | json | 10514 | decoy | fx shard 2 of 8 | none |
| fx_rates_core.csv | csv | 10524 | in-scope | fx shard 1 of 8 | none |
| fx_rates_history.parquet | parquet | 10554 | in-scope | fx shard 4 of 8 | none |
| fx_rates_quarterly.xlsx | xlsx | 10521 | in-scope | fx shard 3 of 8 | none |
| fx_rates_supplement.xml | xml | 5254 | in-scope | fx shard 5 of 8 | none |
| gateway_access_dec.log | log | 5000 | in-scope | transaction rows | none |
| gateway_access_nov.log | log | 5000 | in-scope | transaction rows | none |
| gateway_access_oct.log | log | 5000 | in-scope | transaction rows | none |
| gl_posting_journal_v4.json | json | 5000 | decoy | transaction rows | none |
| gl_posting_journal_v5.json | json | 5000 | in-scope | transaction rows | none |
| item_catalogue_appendix.pdf | pdf | 5698 | in-scope | skus shard 6 of 8 | none |
| item_master_core.csv | csv | 5733 | in-scope | skus shard 1 of 8 | none |
| item_master_extended.tsv | tsv | 5978 | in-scope | skus shard 2 of 8 | none |
| item_master_history.parquet | parquet | 6006 | in-scope | skus shard 4 of 8 | none |
| item_master_mirror.xlsx | xlsx | 5733 | decoy | skus shard 8 of 8 | none |
| item_master_snapshot.json | json | 5313 | in-scope | skus shard 3 of 8 | none |
| item_revision_notes.docx | docx | 5894 | in-scope | skus shard 7 of 8 | none |
| item_status_register.jsonl | jsonl | 5845 | in-scope | skus shard 5 of 8 | none |
| ledger_mirror_2026q4.parquet | parquet | 5000 | decoy | transaction rows | none |
| legacy_pricing_appendix.md | md | 5878 | in-scope | prices shard 8 of 10 | none |
| mainframe_extract_block.txt | txt | 5000 | in-scope | transaction rows | none |
| mainframe_extract_tail.txt | txt | 5000 | in-scope | transaction rows | none |
| nightly_batch_trace.log | log | 5000 | in-scope | transaction rows | none |
| order_capture_portal_dec.csv | csv | 5000 | in-scope | transaction rows | none |
| order_capture_portal_nov.csv | csv | 5000 | in-scope | transaction rows | none |
| order_capture_portal_oct.csv | csv | 5000 | in-scope | transaction rows | none |
| partner_credit_feed.xml | xml | 5000 | in-scope | transaction rows | none |
| partner_invoice_feed.xml | xml | 5000 | in-scope | transaction rows | none |
| party_change_log.docx | docx | 5610 | in-scope | customers shard 7 of 8 | none |
| party_directory_appendix.pdf | pdf | 5540 | in-scope | customers shard 6 of 8 | none |
| party_master_archive.xlsx | xlsx | 5590 | in-scope | customers shard 3 of 8 | none |
| party_master_core.csv | csv | 5720 | in-scope | customers shard 1 of 8 | none |
| party_master_delta.tsv | tsv | 5681 | in-scope | customers shard 2 of 8 | none |
| party_register.db | db | 5660 | in-scope | customers shard 4 of 8 | none |
| party_segment_history.jsonl | jsonl | 5711 | in-scope | customers shard 5 of 8 | none |
| pos_stream_primary.jsonl | jsonl | 5000 | in-scope | transaction rows | none |
| pos_stream_replay.jsonl | jsonl | 5000 | in-scope | transaction rows | none |
| postal_region_delta.tsv | tsv | 5694 | in-scope | prefixes shard 2 of 8 | none |
| postal_region_index.json | json | 5783 | in-scope | prefixes shard 3 of 8 | none |
| postal_region_map.csv | csv | 5356 | in-scope | prefixes shard 1 of 8 | none |
| postal_region_proposed.xml | xml | 5565 | decoy | prefixes shard 4 of 8 | none |
| postal_region_supplement.yaml | yaml | 5567 | in-scope | prefixes shard 5 of 8 | feed_profiles |
| postal_zone_gazetteer.pdf | pdf | 5855 | in-scope | prefixes shard 6 of 8 | none |
| postal_zone_handbook.docx | docx | 5744 | in-scope | prefixes shard 7 of 8 | none |
| price_board_extract.html | html | 6181 | in-scope | prices shard 10 of 10 | none |
| price_book_2027_draft.xlsx | xlsx | 6081 | decoy | prices shard 3 of 10 | none |
| price_book_appendix_a.pdf | pdf | 6037 | in-scope | prices shard 6 of 10 | none |
| price_book_core.csv | csv | 6045 | in-scope | prices shard 1 of 10 | none |
| price_book_segments.xml | xml | 6379 | in-scope | prices shard 4 of 10 | none |
| price_book_versions.jsonl | jsonl | 6267 | in-scope | prices shard 2 of 10 | none |
| price_policy_notes.md | md | 5663 | in-scope | prices shard 9 of 10 | revision_log |
| price_register.db | db | 6318 | in-scope | prices shard 5 of 10 | none |
| price_tier_registry.yaml | yaml | 5887 | in-scope | prices shard 7 of 10 | money_policy |
| regional_rollup_workbook.xlsx | xlsx | 5000 | decoy | transaction rows | none |
| returns_intake_lines.parquet | parquet | 5000 | in-scope | transaction rows | none |
| settlement_contract.md | md | 6024 | in-scope | prefixes shard 8 of 8 | contract |
| staging_dump_latest.jsonl | jsonl | 5000 | decoy | transaction rows | none |
| terminal_bulletin.pdf | pdf | 5740 | in-scope | terminals shard 6 of 7 | none |
| terminal_channel_map.ini | ini | 5838 | in-scope | terminals shard 5 of 7 | window |
| terminal_decommission_log.docx | docx | 5838 | decoy | terminals shard 7 of 7 | none |
| terminal_groups.tsv | tsv | 5628 | in-scope | terminals shard 2 of 7 | none |
| terminal_history.jsonl | jsonl | 5950 | in-scope | terminals shard 3 of 7 | none |
| terminal_master.csv | csv | 6342 | in-scope | terminals shard 1 of 7 | none |
| terminal_offsets.ini | ini | 5964 | in-scope | terminals shard 4 of 7 | ladder_memo |
| terminal_sync_errors.log | log | 5000 | in-scope | transaction rows | none |
| warehouse_closures.ics | ics | 5535 | decoy | warehouses shard 7 of 7 | none |
| warehouse_gazetteer.pdf | pdf | 5760 | in-scope | warehouses shard 5 of 7 | none |
| warehouse_history.parquet | parquet | 6300 | in-scope | warehouses shard 3 of 7 | none |
| warehouse_issue_lines.parquet | parquet | 5000 | in-scope | transaction rows | none |
| warehouse_master.csv | csv | 5820 | in-scope | warehouses shard 1 of 7 | none |
| warehouse_registry.toml | toml | 5835 | in-scope | warehouses shard 2 of 7 | ladder_trade |
| warehouse_relocations.docx | docx | 6240 | in-scope | warehouses shard 4 of 7 | none |
| warehouse_sites.toml | toml | 5760 | in-scope | warehouses shard 6 of 7 | none |
| wholesale_edi_backfill.tsv | tsv | 5000 | in-scope | transaction rows | none |
| wholesale_edi_inbound.tsv | tsv | 5000 | in-scope | transaction rows | none |

Counts: 100 files, 15 of them non authoritative, 19 distinct container types,
591103 rows in total, smallest file 5000 rows.

### Dependency shape

Each feed depends on the nine reference registries and on the twelve policy
registers, so it depends on far more than two other files. Each registry
shard is depended on by all thirty two feeds, and each shard depends on the
canonical form register, the inventory register and the settlement window.
The contract depends on every register it names and is depended on by every
file, because nothing in the drop is interpretable without it. The result is
one strongly connected component: from any file there is a dependency path
to every other file, and there are no orphans and no isolated clusters.
Every registry row belongs to exactly one shard file and every feed row to
exactly one feed file, so no file's required content can be rebuilt from the
other ninety nine.

Global propagation runs through two chains. The acceptance chain gates every
graded value: a row reaches the ledger only after thirteen ordered steps,
each of which reads a different registry, so a missing shard turns accepted
rows into rejected ones and moves every total, every tally and every ledger
position. The ordering chain then carries the damage forward: ledger
positions are one based over the whole accepted set, so a single lost or
gained row shifts every position after it.

### Non authoritative sources

| file | why it looks authoritative | the rule that demotes it | load bearing as | checks that fail when it is skipped |
| --- | --- | --- | --- | --- |
| archive_orders_2026.db | a full year of rows in a tidy database, wider than any single feed | code_crosswalk_supplement.yaml scope_windows | b | quality_codes, quality_accepted_by_source, quality_rejected_by_source, scope_windows, non_authoritative_sources, hidden_drop, second_hidden_drop |
| code_crosswalk_notice.mbox | a mailbox of notices that reads as correspondence rather than data | settlement_contract.md section 2a container table | c, d | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop |
| consolidated_settlement_extract_final.xlsx | newest looking name, cleanest schema, a FINAL label and a metadata sheet | code_crosswalk_supplement.yaml scope_windows | b, e | quality_codes, quality_accepted_by_source, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, scope_windows, non_authoritative_sources, hidden_drop, second_hidden_drop |
| counterparty_notice_board.html | a notice board that reads as reporting rather than as a register | settlement_contract.md section 4 step 7 | b, c, d | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop |
| dw_fact_sales_snapshot.tsv | warehouse naming and a snapshot label that reads like the system of record | code_crosswalk_supplement.yaml scope_windows | a, e | quality_codes, quality_accepted_by_source, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, scope_windows, non_authoritative_sources, hidden_drop, second_hidden_drop |
| fx_rates_board.json | a board name that reads as an unofficial rate source, when it is the only shard holding the BHD and KWD quotes, gaps in the named quote source included | settlement_contract.md section 2 shard rule and fx_policy_register.toml quote_source | a, c | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop |
| gl_posting_journal_v4.json | lower version number beside a v5 file, so it reads as the stale one | price_policy_notes.md revision log | b, e | quality_codes, quality_accepted_by_source, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop |
| item_master_mirror.xlsx | a mirror workbook that duplicates the item columns of three other files | settlement_contract.md section 2 shard rule | c, e | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop |
| ledger_mirror_2026q4.parquet | agrees with the portal and wholesale feeds on almost every key | code_crosswalk_supplement.yaml scope_windows | a, e | quality_codes, quality_accepted_by_source, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, scope_windows, non_authoritative_sources, hidden_drop, second_hidden_drop |
| postal_region_proposed.xml | a proposed remap that is more complete than the live shards | settlement_contract.md section 2 shard rule | c, e | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop |
| price_book_2027_draft.xlsx | a draft label for next year, when it is an ordinary price book shard holding 2024 to 2027 versions for its skus | settlement_contract.md section 2 shard rule | c, e | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop |
| regional_rollup_workbook.xlsx | reads as a summary workbook rather than a feed, so it invites a skip | postal_region_supplement.yaml source_profiles | c, e | quality_codes, quality_accepted_by_source, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, scope_windows, non_authoritative_sources, hidden_drop, second_hidden_drop |
| staging_dump_latest.jsonl | a latest label and a two week window that looks like a full replacement | code_crosswalk_supplement.yaml scope_windows | d, e | quality_codes, quality_accepted_by_source, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, scope_windows, non_authoritative_sources, hidden_drop, second_hidden_drop |
| terminal_decommission_log.docx | a decommission log that reads as a list of terminals to drop | settlement_contract.md section 2 shard rule | c, e | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop |
| warehouse_closures.ics | a calendar file that carries no transaction columns at all | settlement_contract.md section 2a container table | c, d | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop |

None of the fifteen can be ignored and none can be trusted wholesale.
Fourteen of them contribute rows or a register the ledger needs and also
carry rows that a documented rule keeps out. archive_orders_2026.db
contributes no ledger row at all, because its scope window closes on the day
the settlement window opens; it counts only in the rejection tallies, which
is why skipping it is still graded. The role letters are: a
holds the only copy of an invariant, b holds the only evidence that a row is
void, retired or reversed, c supplies the only mapping or shard that joins
two other files, d declares its own standing inside itself with a rule in
another file confirming it, e overlaps the authoritative set so that part of
it counts and part of it does not.

## Verification

The test channel registers twenty nine positive checks worth 89 weight and
six negative checks worth 24 weight, so on its own it runs from -0.270 to
1.000. The judged channel carries twenty six criteria worth 56 positive and
22 negative points. Each channel is divided by its own positive total and
contributes half of the reward.

Negative checks in the test channel: negative_delivered_artifacts_not_from_script, negative_filename_dependent_behaviour, negative_hardcoded_sample_answers, negative_nondeterministic_output, negative_reads_training_corpus_at_runtime, negative_writes_outside_the_output_directory.

Each rejection code and each ledger field is owned by exactly one check that
compares it with the reference; the per feed rejection tally and the two
unseen drops read them again only inside their own wider observables. Ledger membership and order belong to ledger_identity
alone, and the surviving copy of a repeated event belongs to
duplicate_authority alone; every other ledger check compares the delivered
record with the expected record of the same event_id, only where both come
from the same feed, and earns nothing when the ledgers share under half of
the expected events. The roll-up files also earn nothing unless at least 70
percent of the delivered events are expected ones, so a ledger that keeps
every event of every feed without running the chain is not paid for its
roll-ups. hidden_drop runs the program over an unseen drop of the shipped
size and holds it to the 1200 second limit; second_hidden_drop and the
negative probes run drops of a twenty-fifth of the size under the 300 second
limit. The first unseen drop publishes the shipped drop's policy values and
a different authority ladder. The second publishes its own settlement window,
minor unit table, rounding mode, homoglyph table, quote source, carry forward
limit, calendar variant, scope windows, retirement dates and authority
ladder, changes one feed's source profile, and carries a feed shaped table
inside a reference file that no source profile names. The rule probes below
measure copying the registers all at once and copying the window, minor
unit, rounding, homoglyph and source profile values one at a time. Writes outside the output directory are collected over
every run of the program, whichever check started it. The roll-up files are graded against the ledger the
agent delivered, in whole cents, so a wrong ledger record costs the ledger
check that reads it and not every roll-up built on it.

Measured figures, test channel only. The judged channel has no oracle score
at all.

- oracle: 89 of 89, 1.000, reproduced across repeat runs and when the delivered files carry mode 0600; no negative fired
- nop: 0.000
- fourteen empty artifacts: 0.0112, artifacts_exist only

A ledger holding every event of every feed with consistent roll-ups and no
chain applied can earn at most artifacts_exist and json_layout, 2 of 89:
every other positive check needs the delivered ledger to share at least half
of the expected events, with at least 70 percent of its own events expected
ones, or an exact rejection tally.

### Rule probes, measured on the test channel

Each probe is the oracle with exactly one rule broken, scored by the test
channel's own checks over the shipped drop and both unseen drops, with the
delivered program run under the same privilege drop and time limits.

| probe | score | checks it loses |
| --- | --- | --- |
| stops the carry forward one day short of the register | 0.6180 | quality_codes, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop |
| rounds half up | 0.8315 | ledger_cent_amounts, hidden_drop, second_hidden_drop |
| one cent wrong on the first ledger record of every drop | 0.8315 | ledger_cent_amounts, hidden_drop, second_hidden_drop |
| follows the crosswalk until the code stops changing | 0.5281 | quality_codes, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop |
| copies the shipped drop's policy register values into the program and still reads the two authority ladders | 0.9438 | second_hidden_drop |
| copies every register value into the program, the authority ladders included | 0.8876 | hidden_drop, second_hidden_drop |
| copies only the settlement window | 0.9438 | second_hidden_drop |
| copies only the minor unit table | 0.9438 | second_hidden_drop |
| always rounds half even | 0.9438 | second_hidden_drop |
| copies only the homoglyph table | 0.9438 | second_hidden_drop |
| copies only the source profiles | 0.9438 | second_hidden_drop |
| recognises feeds by their twelve columns instead of source_profiles | 0.9438 | second_hidden_drop |

A rule broken everywhere still moves duplicate winners and reversal
targets, so it costs every check that reads membership or rejection
tallies; a single wrong value costs the check that owns it and the two
unseen drops it also breaks.

### Check to rule trace

| check | rule it enforces | where that rule is written |
| --- | --- | --- |
| artifacts_exist | the fourteen deliverables and their paths | instruction.md paragraphs three and five |
| json_layout | sorted keys, two space indent, compact jsonl, one newline | settlement_contract.md section 7 closing paragraph |
| summary_counts | accepted count, net units and total of the delivered ledger, rejected count of the delivered tally | settlement_contract.md section 7 summary paragraph |
| summary_by_region | region roll-up of the delivered ledger in whole cents | settlement_contract.md section 7 summary paragraph |
| summary_by_segment | segment roll-up of the delivered ledger in whole cents | settlement_contract.md section 7 summary paragraph |
| summary_by_category | category roll-up of the delivered ledger in whole cents | settlement_contract.md section 7 summary paragraph |
| summary_by_channel_group | channel group roll-up of the delivered ledger in whole cents | settlement_contract.md section 7 summary paragraph |
| summary_by_currency | currency roll-up of the delivered ledger in whole cents | settlement_contract.md section 7 summary paragraph |
| summary_by_kind | kind roll-up of the delivered ledger in whole cents | settlement_contract.md section 7 summary paragraph |
| quality_codes | the rejection code of every step the rule checks do not own, step order included | settlement_contract.md section 4 steps 1 to 13 |
| quality_accepted_by_source | every feed named, zero included, with the delivered ledger's count per feed, and input_file_count as the number of files the directory holds | settlement_contract.md section 7 data health paragraph |
| quality_rejected_by_source | the rejections attributed to each feed | settlement_contract.md sections 4 to 7 |
| product_summary | the item roll-up of the delivered ledger and its version set | settlement_contract.md section 7 item paragraph |
| region_files | the five region files built from the delivered ledger | settlement_contract.md section 7 group paragraph |
| segment_files | the four segment files built from the delivered ledger | settlement_contract.md section 7 group paragraph |
| ledger_identity | which events reach the ledger, their order, posting dates and positions | settlement_contract.md sections 1, 4 and 6 |
| ledger_dimensions | segment, region, category, channel group, fiscal week | settlement_contract.md section 4 steps 8 to 13 |
| ledger_money | currency, native minor amount and quantity, with their types | settlement_contract.md section 4 amount paragraph |
| ledger_record_fields | the seventeen field record | settlement_contract.md section 7 |
| ledger_customer_kind_sku | canonical customer, kind and resolved item | settlement_contract.md sections 1 and 7 |
| ledger_price_versions | the half open price book lookup | settlement_contract.md section 4 step 11 |
| ledger_cent_amounts | one rounding step in the named mode and the carry forward walk | settlement_contract.md section 4 step 12 and amount paragraph, fx_policy_register.toml |
| duplicate_authority | the authority ladder, its tie breaks and the duplicate group count | settlement_contract.md section 5 |
| reversal_chain | the ordered reversal walk, the live rule and the orphan rule | settlement_contract.md section 6 |
| scope_windows | the settlement window and each feed's scope window, the OUT_OF_SCOPE count, scoped_sources and the reported settlement_window | settlement_contract.md section 4 step 5 and section 7, terminal_channel_map.ini, scope_windows register |
| source_supersession | the revision log, the SUPERSEDED_SOURCE count and superseded_sources | settlement_contract.md section 4 step 6 and section 7, price_policy_notes.md revision log |
| non_authoritative_sources | how far each non authoritative feed reaches | settlement_contract.md sections 2 and 3, scope_windows register |
| hidden_drop | the same code gives correct results, within 1200 seconds, for a full size drop it has never seen | instruction.md paragraphs three and four |
| second_hidden_drop | the same code gives correct results, within 300 seconds, for a drop a twenty-fifth of the size it has never seen, with its own policy register values, one changed source profile, a feed shaped table no source profile names, and an empty segment | instruction.md paragraphs three and four, settlement_contract.md opening, sections 3, 4 and 7 |
| negative_hardcoded_sample_answers | no figure taken from this drop | instruction.md paragraph four |
| negative_filename_dependent_behaviour | no dependence on file sizes or names, standing down when the output is nondeterministic | instruction.md paragraph four |
| negative_reads_training_corpus_at_runtime | read nothing outside the input directory | instruction.md paragraph four |
| negative_nondeterministic_output | byte identical output on repeated runs | instruction.md paragraph four |
| negative_writes_outside_the_output_directory | write nothing outside the output directory | instruction.md paragraph four |
| negative_delivered_artifacts_not_from_script | the deliverables come from running the program once over /app/data | instruction.md paragraph five |

Thirty five checks, thirty five traces, no untraced check.

### Trap loops

A loop is a wrong early decision whose downstream results stay internally
consistent and appear to confirm it. The only exit is a documented
invariant in a different file.

| id | entry | reinforcement | tell lives in | exit | checks that fail | chains to | anchored in a non authoritative file | survives sample checking |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| L01 | Take the newest looking consolidated extract as the primary feed and read the rest as reference | Row counts land close to the declared totals and the region split looks even | code_crosswalk_supplement.yaml scope_windows | settlement_contract.md section 5 | summary_counts, summary_by_region, summary_by_segment, summary_by_category, summary_by_channel_group, summary_by_currency, summary_by_kind, quality_codes, quality_accepted_by_source, quality_rejected_by_source, product_summary, region_files, segment_files, ledger_identity, ledger_dimensions, ledger_money, ledger_record_fields, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop | L02 | yes | yes |
| L02 | Having found the scope window, apply it to the whole extract including rows that lose the ladder | Accepted counts fall into the declared band and duplicates drop away | warehouse_registry.toml authority_sale | settlement_contract.md section 5 | quality_codes, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop | L03 | yes | no |
| L03 | Resolve ties inside a duplicate group by the later revision first | The ledger keeps the richest looking row and the totals rise toward the declared figure | settlement_contract.md section 5 tie break order | settlement_contract.md section 5 | quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | none | no | yes |
| L04 | Read every effective dated registry with an inclusive upper bound | Almost every lookup still resolves and only boundary days differ | settlement_contract.md section 2 half open note | settlement_contract.md section 2 | quality_codes, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop | L05 | no | yes |
| L05 | Having fixed the window, keep the inclusive bound for the price book alone | Price versions resolve for every sku and no rejection appears | price_tier_registry.yaml and the price book shards | settlement_contract.md section 4 step 11 | quality_codes, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop | none | no | yes |
| L06 | Treat the capture date as the posting date for every row | Dates stay inside the quarter and the weekly split looks smooth | terminal registry utc_offset_minutes column | settlement_contract.md section 4 step 4 | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop | L07 | no | no |
| L07 | Having found the branch rule, look the terminal up on the posting date | Channel groups resolve for every row and the branch share looks plausible | settlement_contract.md section 4 step 3 | settlement_contract.md section 4 step 3 | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_cent_amounts, hidden_drop | none | no | yes |
| L08 | Pick the exchange rate from the quote source with the most rows | Every record converts and the currency split looks balanced | fx_policy_register.toml quote_source | fx_policy_register.toml | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | L09 | no | no |
| L09 | Having found the quote source, reject a day with no quote | The rejection tally gains a believable NO_FX_RATE count | fx_policy_register.toml carry_forward_days | settlement_contract.md section 4 step 12 | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | none | no | no |
| L10 | Round each unit price to cents and then multiply by the quantity | Totals differ from the single step result by a few cents per thousand rows | settlement_contract.md section 4 amount paragraph | settlement_contract.md section 4 | ledger_cent_amounts, hidden_drop, second_hidden_drop | L11 | no | yes |
| L11 | Having moved to one rounding step, round half up | Only the exact half cent rows differ and every total still looks clean | fx_policy_register.toml rounding_mode | settlement_contract.md section 4 amount paragraph | ledger_cent_amounts, hidden_drop, second_hidden_drop | none | no | yes |
| L12 | Assume two minor units for every currency | Most rows are right because most settlement is in two unit currencies | price_tier_registry.yaml minor_units | price_tier_registry.yaml | ledger_money, ledger_cent_amounts, hidden_drop, second_hidden_drop | none | no | no |
| L13 | Parse the comma style prices by stripping commas | Most rows parse and the magnitudes look sane | postal_region_supplement.yaml decimal_style | settlement_contract.md section 3 | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop | none | no | no |
| L14 | Read a bracketed price as a negative amount | Refund totals grow more negative in a way that looks deliberate | settlement_contract.md section 3 bracket note | settlement_contract.md section 3 | ledger_money, ledger_cent_amounts, hidden_drop, second_hidden_drop | none | no | no |
| L15 | Read every file as utf-8 and keep the byte order mark on the first column name | The first registry column silently fails to match and the shard is skipped | settlement_contract.md section 2a | settlement_contract.md section 2a | summary_counts, summary_by_region, summary_by_segment, summary_by_category, summary_by_channel_group, summary_by_currency, summary_by_kind, quality_codes, quality_accepted_by_source, quality_rejected_by_source, product_summary, region_files, segment_files, ledger_identity, ledger_dimensions, ledger_money, ledger_record_fields, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop | none | no | no |
| L16 | Read the latin-1 feeds as utf-8 with replacement | Three of the four latin-1 feeds are plain ASCII and read cleanly, so the reading looks safe, while in terminal_sync_errors.log every non breaking space inside a timestamp becomes a replacement character and the whole feed rejects as MALFORMED_ROW | postal_region_supplement.yaml encoding | settlement_contract.md section 3 | quality_codes, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, scope_windows, non_authoritative_sources, hidden_drop, second_hidden_drop | none | no | no |
| L17 | Compare identifiers as written | Padded and homoglyph identifiers never collide, so the duplicate count looks low | code_crosswalk_overrides.ini homoglyphs | settlement_contract.md section 1 | summary_counts, summary_by_region, summary_by_segment, summary_by_category, summary_by_channel_group, summary_by_currency, summary_by_kind, quality_codes, quality_accepted_by_source, quality_rejected_by_source, product_summary, region_files, segment_files, ledger_identity, ledger_dimensions, ledger_money, ledger_record_fields, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop | L18 | no | no |
| L18 | Having mapped the homoglyphs, keep the leading zeros | Most duplicates resolve and only the padded feeds stay separate | code_crosswalk_overrides.ini identifier | settlement_contract.md section 1 | quality_codes, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop | none | no | no |
| L19 | Look a retired code up in the registry before the crosswalk | Those rows reject as unknown and the rejection tally looks healthy | code_crosswalk_core.xml and its shards | settlement_contract.md section 2 | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop | L20 | no | no |
| L20 | Having used the crosswalk, follow a second hop when the result is also retired | A handful of rows that the contract rejects as unknown resolve to a live code and reach the ledger, and the unknown counts look slightly low | settlement_contract.md section 2 single hop note | settlement_contract.md section 2 | quality_codes, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop | none | no | yes |
| L21 | Resolve carrier crosswalk rows as warehouse mappings | Extra codes resolve and the unknown warehouse count drops | settlement_contract.md section 2 carrier note | settlement_contract.md section 2 | quality_codes, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | none | no | yes |
| L22 | Take the region from the customer postal code for every row | Every row gets a region and the five way split looks even | settlement_contract.md section 4 step 10 | settlement_contract.md section 4 step 10 | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | none | no | no |
| L23 | Read the first fiscal calendar variant found | Every posting date gets a week label and the labels look consistent | fiscal_calendar_policy.yaml variant | fiscal_calendar_policy.yaml | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | none | no | no |
| L24 | Treat the proposed postal region map as the current one | Regions resolve for every prefix and the map looks more complete | settlement_contract.md section 2 shard note | postal_region_map.csv and its shards | summary_counts, summary_by_region, summary_by_segment, summary_by_category, summary_by_channel_group, summary_by_currency, summary_by_kind, quality_codes, quality_accepted_by_source, quality_rejected_by_source, product_summary, region_files, segment_files, ledger_identity, ledger_dimensions, ledger_money, ledger_record_fields, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | L25 | yes | no |
| L25 | Having demoted the proposed map, drop it from the registry entirely | The remaining shards still cover almost every prefix | terminal_channel_map.ini input_file_count | settlement_contract.md section 2 | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | none | yes | no |
| L26 | Drop the 2027 draft price book as not yet effective | Most skus still resolve and the extra NO_PRICE_VERSION rows look like the documented gaps | settlement_contract.md section 2 shard note | price_book_core.csv and its shards | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | none | yes | no |
| L27 | Skip the item master mirror because another workbook already holds items | The item registry still covers most skus and only a slice rejects | terminal_channel_map.ini input_file_count | settlement_contract.md section 2 | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | none | yes | no |
| L28 | Ignore the counterparty notice board as chatter | Voided events stay in the ledger and the totals look larger and smoother | settlement_contract.md section 4 step 7 | counterparty_notice_board.html | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | L29 | yes | no |
| L29 | Having found the void register, compare its identifiers with the feed identifiers as written | Most voids still match because most feeds write plain identifiers | code_crosswalk_overrides.ini identifier | settlement_contract.md section 4 step 7 | quality_codes, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | none | yes | yes |
| L30 | Ignore the warehouse closure calendar because it carries no transactions | Warehouse lookups still resolve for most days | settlement_contract.md section 2a container table | settlement_contract.md section 2 | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | none | yes | no |
| L31 | Ignore the crosswalk notice mailbox because it reads like correspondence | Most retired codes still resolve through the other shards | settlement_contract.md section 2a container table | settlement_contract.md section 2 | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop | none | yes | no |
| L32 | Skip the rate board as an unofficial source | Ten currencies still convert, and the BHD and KWD rows reject as NO_FX_RATE as if those quotes were simply missing | settlement_contract.md section 2 shard rule | fx_policy_register.toml | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | none | yes | no |
| L33 | Read the legacy pricing appendix as superseded and drop it | The price book still covers most skus | price_policy_notes.md revision log | settlement_contract.md section 2 | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | none | no | no |
| L34 | Treat the terminal decommission log as a retirement list and drop those terminals | Channel groups still resolve for most rows | settlement_contract.md section 2 shard note | terminal_master.csv and its shards | quality_codes, quality_rejected_by_source, ledger_identity, ledger_dimensions, ledger_money, ledger_customer_kind_sku, ledger_price_versions, ledger_cent_amounts, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop | none | yes | no |
| L35 | Take the archive database as in scope because its rows sit in the same year | Row counts rise and the quarter looks busier | code_crosswalk_supplement.yaml scope_windows | settlement_contract.md section 4 step 5 | quality_codes, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, scope_windows, non_authoritative_sources, hidden_drop, second_hidden_drop | none | yes | no |
| L36 | Drop the archive database entirely once it is seen to be out of window | Nothing visible changes in the ledger | terminal_channel_map.ini input_file_count | settlement_contract.md section 2 | quality_codes, quality_accepted_by_source, quality_rejected_by_source, scope_windows, non_authoritative_sources, hidden_drop, second_hidden_drop | none | yes | yes |
| L37 | Treat the staging dump as a full replacement for the portal feeds | Duplicate groups collapse and the ledger looks cleaner | warehouse_registry.toml authority_sale | settlement_contract.md section 5 | quality_codes, quality_accepted_by_source, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop | none | yes | no |
| L38 | Treat the warehouse rollup workbook as a summary and skip it | Totals drop slightly and still sit near the declared figure | postal_region_supplement.yaml source_profiles | settlement_contract.md section 3 | quality_codes, quality_accepted_by_source, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, scope_windows, non_authoritative_sources, hidden_drop, second_hidden_drop | none | yes | no |
| L39 | Retire a source from the revision log date inclusive of earlier rows | The superseded count rises and the remaining rows look consistent | price_policy_notes.md revision log | settlement_contract.md section 4 step 6 | quality_codes, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop | L40 | no | no |
| L40 | Having fixed the retirement boundary, apply it to the capture date | Only branch rows near midnight move | settlement_contract.md section 4 step 4 | settlement_contract.md section 4 step 6 | quality_codes, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, source_supersession, non_authoritative_sources, hidden_drop | none | no | yes |
| L41 | Walk the reversal chain in file order | Reversal pairs still cancel and the pair count looks right | settlement_contract.md section 6 order | settlement_contract.md section 6 | quality_rejected_by_source, ledger_identity, reversal_chain, non_authoritative_sources, hidden_drop | L42 | no | yes |
| L42 | Having ordered the walk, let a reversal cancel a row already cancelled | The orphan count drops and the ledger shrinks a little further | settlement_contract.md section 6 live note | settlement_contract.md section 6 | reversal_chain, hidden_drop, second_hidden_drop | none | no | no |
| L43 | Keep an orphan reversal as an ordinary credit | Credit totals look richer and no code is lost | settlement_contract.md section 6 orphan rule | settlement_contract.md section 6 | quality_rejected_by_source, ledger_identity, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | none | no | no |
| L44 | Count one reversal as a single rejection | The rejected total is close and every other figure agrees | settlement_contract.md section 7 rejected_count note | settlement_contract.md section 7 | quality_rejected_by_source, reversal_chain, hidden_drop, second_hidden_drop | none | no | yes |
| L45 | Reject an inactive item as an unknown item | The rejection tally still sums to the same total | settlement_contract.md section 4 step 9 | settlement_contract.md section 4 step 9 | quality_codes, hidden_drop, second_hidden_drop | none | no | yes |
| L46 | Validate the quantity column only for sale and refund rows | Fee and credit rows with a written out quantity survive and add revenue | settlement_contract.md section 4 step 2 | settlement_contract.md section 3 quantity note | quality_codes, quality_rejected_by_source, ledger_identity, duplicate_authority, reversal_chain, scope_windows, source_supersession, non_authoritative_sources, hidden_drop, second_hidden_drop | none | no | no |
| L47 | Number the ledger before the reversal walk removes rows | Positions stay dense and every other field is right | settlement_contract.md section 6 closing paragraph | settlement_contract.md section 6 | ledger_identity, hidden_drop, second_hidden_drop | none | no | no |
| L48 | Order the ledger by event identifier alone | The ordering looks canonical and the totals do not move | settlement_contract.md section 6 order | settlement_contract.md section 6 | ledger_identity, hidden_drop, second_hidden_drop | none | no | yes |
| L49 | Break ties between equal customer totals by the larger identifier or by first appearance | Only the tied pair at the head of one region and one segment swaps places | settlement_contract.md section 7 tie break | settlement_contract.md section 7 | region_files, segment_files, hidden_drop, second_hidden_drop | none | no | yes |
| L50 | List every known sku in the item roll-up | The item count looks complete and every total still agrees | settlement_contract.md section 7 products rule | settlement_contract.md section 7 | product_summary, hidden_drop, second_hidden_drop | none | no | no |
| L51 | Leave an empty group file out, or write it without its empty maps, when a group has no rows | The shipped drop has no empty group, so nothing changes until the second unseen drop, whose quiet segment then breaks | settlement_contract.md section 7 empty group rule | settlement_contract.md section 7 | second_hidden_drop | none | no | yes |
| L52 | Report input_file_count as the number of feeds the source profiles name | The figure matches the feed count the contract opening states | settlement_contract.md section 7 input_file_count | settlement_contract.md section 7 | quality_accepted_by_source, hidden_drop, second_hidden_drop | none | no | no |
| L53 | Copy the policy register values into the program once they are found | Every figure on the shipped drop and the first unseen drop stays right | settlement_contract.md sections 4 and 5 name the registers | instruction.md paragraph four | second_hidden_drop | none | no | yes |
| L54 | Read a reversal that names its own event as an ordinary credit | Credit totals rise slightly and the orphan count looks plausible | settlement_contract.md section 6 orphan rule | settlement_contract.md section 6 | quality_rejected_by_source, ledger_identity, reversal_chain, non_authoritative_sources, hidden_drop, second_hidden_drop | none | no | yes |

54 loops, 12 of them chained into a following loop, 16 anchored in a non
authoritative file, 20 that a sample output comparison cannot tell apart
from the right path. The checks listed for each loop were measured by running
the reference chain with that one rule broken over the shipped drop and both
unseen drops. Every entry above is the step that standard practice
takes, and every tell sits in a file other than the one the entry reads.

## Root cause

The drop is a union of thirty two upstream exports and sixty eight
published registers that were never reconciled against one another. Three
things make it hard rather than merely long.

The first is that authority is a property of a pair rather than of a file.
A feed can outrank another on sale rows and lose to it on credit rows, and
the two ladders live in a warehouse register and a terminal register, not
beside the feeds. So no file can be read as more or less trustworthy as a
whole, which is the reading every naming convention in the drop invites.

The second is that the chain is ordered and partly self referential. The
posting date decides every registry lookup, but the terminal lookup that
decides the posting date has to run on the capture date. Getting that
ordering wrong moves a small number of branch rows across a day boundary,
which moves them in or out of the settlement window, which changes the
accepted set, which changes every ledger position.

The third is that the drop is internally consistent under several wrong
readings. Non authoritative sources agree with authoritative ones on almost
every key. Inclusive and half open windows agree everywhere except on a
boundary day. Half up and half even agree except on an exact half cent. The
only way through is to find the register that settles each question and to
test the result against the counts and windows the drop declares about
itself.

## Solution shape

Read the contract first. Build the twelve policy values from the registers
it names: the source profiles, the scope windows, the revision log, the two
authority ladders, the settlement window and file count, the minor unit
table, the quote source, carry forward limit and rounding mode, the fiscal
calendar variant, the canonical form table and the void register.

Then walk every file in the directory, pull every table out of it whatever
its container, and classify each table by its column names. A table whose
columns are the twelve feed columns belongs to a feed when the source
profile register names that file, and is reference material otherwise. A
table whose columns match a registry shape is a shard of that registry.
Concatenate the shards.

Then run the thirteen step chain per row, in the documented order, stopping
at the first step that rejects. Group the survivors by canonical event, keep
the ladder winner, walk the reversal chain in canonical order, number the
result and roll it up.

The oracle does exactly this in one pass over the directory and finishes in
under a minute of processor time on the shipped drop.

## Ordered plan

1. List the input directory and confirm it holds the number of files the inventory register declares.
2. Read the contract end to end before writing code.
3. Read the twelve policy registers and record every value they fix.
4. Write one reader per container format and prove each one against a file you have already read by eye.
5. Classify every table in every file by its column names and concatenate the registry shards.
6. Check that the feed set you derived equals the set the source profile register names.
7. Build the six effective dated timelines with a half open upper bound.
8. Build the crosswalk, the void set, the fiscal calendar for the named variant and the rate table for the named quote source.
9. Implement the thirteen step chain in order, with one rejection code per step.
10. Implement the duplicate group resolution with the four level tie break.
11. Implement the ordered reversal walk and number the surviving ledger.
12. Roll up the summary, the data health report, the item roll-up and the nine group files.
13. Write the artifacts with sorted keys, two space indent and a closing newline.
14. Re-run the pipeline over a copy of the directory at another path and compare the output byte for byte.
15. Reconcile the result against the declared file count, the settlement window and the scope registers before stopping.

## Pitfalls

- Reading one file as the primary input. No file in the drop is complete and the naming convention is deliberately uninformative.
- Using an inclusive upper bound on an effective dated window. It is right everywhere except the boundary day, and the boundary day is graded.
- Taking the posting date from the capture date for every row, or looking the terminal up on the posting date rather than the capture date.
- Rounding more than once, or rounding half up.
- Assuming two minor units, or applying the exponent after the rate rather than before it.
- Stripping commas from a comma locale price, which multiplies the fraction into the integer part.
- Reading a bracketed amount as negative and then applying the kind sign as well.
- Comparing identifiers as written, so padded and homoglyph copies never collide.
- Following the crosswalk more than one hop, or resolving carrier rows.
- Copying the policy register values into the program, or supporting only the rounding mode the shipped drop names. The second unseen drop publishes different ones.
- Recognising feeds by their twelve columns rather than by source_profiles. The second unseen drop carries a feed shaped table inside a reference file.
- Leaving a byte order mark on the first column name, which makes a whole shard invisible.
- Treating filler comment lines and blank lines as data, or assuming they only appear at the top of a file.
- Counting one reversal as one rejection rather than two.
- Numbering the ledger before the reversal walk has removed its rows.
- Reporting the number of feeds, or of registry shards, as input_file_count instead of counting every file the directory holds.
- Reading a latin-1 feed as utf-8, which turns the non breaking spaces inside log timestamps into replacement characters.
- Trusting the tidier of two rate sources, or the newer looking of two price books.

### Expert time

| stage | hours |
| --- | --- |
| Survey the hundred files and identify the nineteen containers | 3 |
| Read the contract and the twelve policy registers | 3 |
| Write and prove one reader per container format | 7 |
| Classify tables and reconstruct the nine sharded registries | 4 |
| Work out the canonical identifier form and prove it against the duplicates | 2 |
| Implement the thirteen step chain and its rejection codes | 6 |
| Settle the authority ladder, the scope windows and the revision log | 3 |
| Implement the ordered reversal walk | 2 |
| Settle the currency, minor unit and rounding rules | 2 |
| Build the twelve roll-up artifacts to the published field sets | 3 |
| Reconcile against the declared invariants and chase the differences | 4 |
| Harden the script for an unseen directory and prove determinism | 2 |

Forty one hours, which is three to four full working days for a senior data
engineer who already knows the domain. The long poles are the container
readers and the reconciliation loop, and neither can be shortened by
guessing, because a wrong reading stays internally consistent until it is
tested against a declared figure.

## Provenance

```yaml
uuid: 1950015d-de91-55a5-836b-dbbb74338883
instance_id: 1950015d-de91-55a5-836b-dbbb74338883
task_name: terminal-bench/1950015d-de91-55a5-836b-dbbb74338883
fix_patch_sha256: 25c71b6c701c5cdc752f2284c1d929d0ca149547952669c1fb7c8b4ac00dc680  # sha256 of solution/solve.sh
solve_py_sha256: 46a3c2c2b457d6748cae824d6328773b2eeedecff3d8bf3db4c51702c8e402e5  # sha256 of solution/solve.py
language: python
golden_score_measured: 1.000  # test channel only
golden_score_channel_a_pct: 100
golden_score_channel_b_pct: null  # the judged channel has no oracle score
golden_score_runs: 6
caveat: >
  The test channel carries twenty nine positive checks worth 89 weight and
  six negative checks worth 24 weight, so on its own it runs from -0.270
  to 1.000. The judged channel carries twenty six criteria worth 56
  positive and 22 negative points. Each channel is divided by its own
  positive total and counts for half of the one reward, so the combined
  value runs from -0.331 to 1.000 with no clamp.
```
