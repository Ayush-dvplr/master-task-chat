# Record dictionary

Every input of a metering extract sits in one flat directory. CSV files are UTF-8, comma-separated, with a header row naming the columns listed below. Every field value is trimmed of surrounding spaces before use. Identifiers are then compared exactly; the values of `role`, `region`, `segment`, `product_line` and `status` are compared without regard to letter case. Integers are written with decimal digits only.

Two stamp forms are used. A local stamp is `YYYY-MM-DDTHH:MM:SS.mmm` with exactly three millisecond digits and no zone designator; it is the reading of the clock of the node that wrote it. A reference stamp has the same form followed by `Z`; it is a UTC instant on the reference clock (metering standard, Clocks).

## Billing order

Billing order ranks the billed queries of one billing identity and billing day by ascending billing instant (metering standard, Billing instant).

## Files

`allowance_statement_prior.csv`: the allowance statement issued for the previous billing period, covering the listed tenant days. Columns: `billing_day` (`YYYY-MM-DD`), `tenant_id` (the billing identity), `query_id`, `node_id`, `started_at` and `billed_at` (reference stamps of the query's start and billing instant), `metered_bytes` and `free_bytes` (integers).

`corrections.jsonl`: one JSON object per line with the keys `correction_id` (string), `query_id` (string), `recorded_at` (a reference stamp), `action` (`restate`, `void` or `reinstate`) and `scanned_bytes` (an integer for `restate`, `null` otherwise).

`invoice_preview.json`: an invoice preview with the keys `title`, `authority`, `rate_card_as_of` (`YYYY-MM-DD`), `period_from`, `period_to` and `tenants`, a list of objects with `tenant_id` and `charge_micros`.

`nodes.csv`: the node register. Columns: `node_id`, `region` (one of `central`, `east`, `north`, `south`, `west`), `role` (`reference` for exactly one node, `member` for every other).

`plans.json`: the rate cards that the `plan` column of the tenant register names. A JSON object whose key `plans` maps each plan code to a list of versions; each version has `version` (string), `effective_from` (a reference stamp), and the integers `daily_free_bytes`, `min_billable_bytes`, `block_bytes`, `peak_micros_per_gib` and `offpeak_micros_per_gib`.

`plans_v2_draft.json`: rate card revision 2, an object with the keys `revision` and `plans`, in the layout of `plans.json`.

`products.csv`: the product register. Columns: `product_id`, `product_line`, `name`.

`queries.csv`: one row per query a node logged. Columns: `query_id`, `node_id` (the node that ran it and stamped `started_local`), `tenant_id`, `product_id`, `started_local` (a local stamp), `duration_ms` (integer milliseconds), `scanned_bytes` (integer), `status` (`ok`, `cancelled` or `failed`).

`tenant_merges.csv`: the merge register. Columns: `absorbed_tenant`, `surviving_tenant`, `effective_at` (a reference stamp). A tenant is absorbed at most once.

`tenants.csv`: the tenant register. Columns: `tenant_id`, `display_name`, `segment` (one of `consumer`, `corporate`, `enterprise`, `smb`), `plan` (a plan code), `zone` (a zone name).

`transfers.log`: the stage transfer journal. Blank lines and lines whose first character is `#` carry nothing. Every other line has five `|`-separated fields: `xfer_id`, `from_node`, `sent_local` (a local stamp of the sending node), `to_node`, `recv_local` (a local stamp of the receiving node).

`zones.json`: a JSON object whose key `zones` maps each zone name to an object with `standard_offset_minutes` and `daylight_offset_minutes` (integers), `daylight_periods` (a list of objects with `start` and `end`, both reference stamps) and `holidays` (a list of `YYYY-MM-DD` dates).

The three Markdown documents (`metering_standard.md`, `record_dictionary.md`, `report_layout.md`) are part of every extract.
