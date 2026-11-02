# Report layout

A metering run writes thirteen reports into its output directory: `normalized.jsonl`, `summary.json`, `data_quality.json`, `product_summary.json`, `region_central.json`, `region_east.json`, `region_north.json`, `region_south.json`, `region_west.json`, `segment_consumer.json`, `segment_corporate.json`, `segment_enterprise.json` and `segment_smb.json`. All five region reports and all four segment reports are written on every run.

## Byte form

Every report is UTF-8 with LF line endings. Every number in a report is an integer written in decimal. Every key list is sorted in code-point order.

`normalized.jsonl` holds one JSON object per billed query, each on its own line ending in LF, with no spaces anywhere outside string values, and nothing else; it is empty when no query is billed. Its lines are ordered by `billed_at`, then by `query_id`, both in code-point order.

Every `.json` report is one JSON object written with two-space indentation, one key or array element per line, a single space after each colon, a comma directly after every element that has a successor, and a single LF after the closing brace. An empty object is written `{}` and an empty array `[]`.

A reference stamp in a report has the form `YYYY-MM-DDTHH:MM:SS.mmmZ`; a date has the form `YYYY-MM-DD`. Values of `region`, `segment` and `product_line` are written in lower case.

## Program output

On standard output the program writes one line for each report it writes, in code-point order of file name: the file name, one space, and the report's size in bytes. It writes nothing else on standard output.

## normalized.jsonl

Keys of each object: `billed_at` (the billing instant as a reference stamp), `billing_day`, `chargeable_bytes`, `charge_micros` (the query's charge), `corrected` (`true` when the query's scanned bytes after its corrections differ from the logged ones, else `false`), `free_bytes`, `metered_bytes`, `node_id`, `plan_version` (the `version` of the rate card in force at the billing instant), `product_id`, `product_line`, `query_id`, `region` (the region of the node), `scanned_bytes` (after corrections), `segment` (of the billing identity), `source_tenant_id` (the tenant that ran the query), `tenant_id` (the billing identity), `window`.

## summary.json

Keys: `billed_queries`, `metered_bytes`, `free_bytes`, `chargeable_bytes` and `charge_micros` (sums over every billed query); `by_region`, `by_segment`, `by_window`, `by_product_line` and `by_plan_version` (each maps every value of that ledger field that occurs among billed queries to the sum of their charges); `reconciliation`, an object with `ledger_charge_micros` (the sum of charges in `normalized.jsonl`), `region_charge_micros` (the sum of `charge_micros` over the five region reports), `segment_charge_micros` (the same over the four segment reports), `product_charge_micros` (the same over the entries of `product_summary.json`) and `residual_micros` (three times `ledger_charge_micros`, less the other three).

## data_quality.json

Keys: `input_files` (the names of every regular file in the input directory, as a sorted array), `query_rows` (data rows of `queries.csv`), `rejected_rows`, `failed_queries` (rows that pass the rejection test with status `failed`), `voided_queries` (rows that pass the rejection test, are not `failed`, and are withdrawn after corrections), `billed_queries`, `corrected_queries` (billed queries whose `corrected` is `true`), `merged_queries` (billed queries whose `tenant_id` differs from `source_tenant_id`), `transfer_lines` (lines of the transfer journal that carry a transfer).

## product_summary.json

Key `products`: an array with one object for every product in the product register, ordered by `product_id`, with the keys `product_id`, `product_line`, `billed_queries`, `metered_bytes`, `chargeable_bytes` and `charge_micros` over the billed queries of that product.

## Region reports

`region_<name>.json` has the keys `region` (the name), `in_scope` (`true` when the node register lists a node of that region), `nodes` (the sorted node ids of that region), `tenants` (the sorted distinct `tenant_id` values of its billed queries), `billed_queries`, `metered_bytes`, `free_bytes`, `chargeable_bytes`, `charge_micros`, and `by_window`, an object with both keys `offpeak` and `peak` holding the charge sums of the region's billed queries in each window.

## Segment reports

`segment_<name>.json` has the keys `segment` (the name), `in_scope` (`true` when at least one billed query has that segment), `tenants` (the sorted distinct `tenant_id` values of its billed queries), `billed_queries`, `metered_bytes`, `free_bytes`, `chargeable_bytes`, `charge_micros`, and `by_region`, mapping every region that occurs among its billed queries to their charge sum.
