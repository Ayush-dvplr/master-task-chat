# fa7c65bd-ff01-50e7-b3ba-34fbd5df860d Contract (SLSC-1.0)

All timestamps are UTC ISO-8601 strings ending in `Z`. Time intervals and frequency intervals are half-open. JSONL row order is irrelevant. Identifiers are case-sensitive strings. Integer fields must be interpreted as base-10 integers. Monetary values are integer US cents. The reusable program receives `DATA_DIR OUT_DIR` and writes the nine reports below using sorted keys, two-space indentation, and one trailing newline.

## Inputs

`policy.json` contains `engine_version`, `primary_priority`, `dormant_owner_priority`, `material_cents`, and `default_rate_cents_per_mhz_hour`.

`parties.json` is a list of unique `{party_id,name}` rows.

`licenses.jsonl` rows contain `license_id`, `owner_party_id`, sorted or unsorted unique `cells`, integer `low_khz`, integer `high_khz`, `start`, and `end`. A license is invalid when its time or frequency interval is non-positive, its owner is unknown, or its cell list is empty. Emit `INVALID_LICENSE` with the license id and omit it from clearing.

`grant_revisions.jsonl` rows contain `record_id`, `grant_id`, integer `revision`, `recorded_at`, `status` (`active` or `cancelled`), `license_id`, `party_id`, `cells`, `low_khz`, `high_khz`, `start`, `end`, integer `priority`, and integer `share_bps`. Resolve each grant independently: choose the maximum tuple `(revision, recorded_at, record_id)`. `recorded_at` compares chronologically. If two rows share the winning revision and recorded_at but differ in any field other than record_id, emit `REVISION_TIE_CONFLICT` for the grant; record-id still breaks the tie. Cell lists are set-valued for this comparison, so their order does not create a conflict. A cancelled winner produces a revision decision but no effective grant. An active winner is invalid when the referenced license or party is absent; share is outside 0..10000; cells are empty or not a subset of the license cells; its time/frequency interval is non-positive or not contained by the license. Emit `INVALID_GRANT` and omit it. Decisions are sorted by grant_id. Effective grants are sorted `(license_id,party_id,start,low_khz,grant_id)`.

`activation_events.jsonl` contains primary-license activations with unrestricted `activation_id` strings, `license_id`, `cells`, frequency and time bounds. Identifier spelling or prefix has no semantic meaning. Invalid containment, intervals, or cells produce `INVALID_ACTIVATION` and are omitted.

`exclusions.jsonl` contains `exclusion_id`, `license_id`, `party_id` (a party or `*`), cells, frequency and time bounds. Invalid containment, party, or intervals produce `INVALID_EXCLUSION` and are omitted. An exclusion applies only where all its dimensions overlap. `*` excludes every candidate; otherwise it excludes only the named party.

`guard_bands.jsonl` contains one optional `{guard_id,license_id,guard_khz}` per license. Negative or duplicate license rows produce `INVALID_GUARD_BAND`; for duplicate valid rows choose lowest guard_id after reporting the issue. A grant's usable frequency is `[low_khz+guard_khz, high_khz-guard_khz)`. If this is non-positive, that grant contributes no candidate slices. Guard bands do not shrink the owner's base license.

`auction_results.jsonl` is revisioned exactly like grants, grouped by auction_id and resolved by `(revision,recorded_at,record_id)`. A winning peer conflict emits `AUCTION_TIE_CONFLICT`. Cancelled winners are omitted. Active winners must reference a valid license, have a positive contained time interval, and a non-negative rate; otherwise emit `INVALID_AUCTION`. Effective auctions sort `(license_id,start,auction_id)`.

`corrections.jsonl` rows contain `correction_id`, `license_id`, and signed `amount_cents`. Unknown license ids produce `INVALID_CORRECTION`. Valid corrections are summed per license.

## Atomic spectrum slices

Process valid licenses by license_id and each license cell lexically. Build time cuts from the license endpoints and every overlapping valid effective grant, activation, exclusion, and auction endpoint. Build frequency cuts from the license endpoints and every clipped usable grant, activation, and exclusion endpoint. For every positive Cartesian time/frequency rectangle, form candidates:

1. The owner is always a candidate over the whole license at `dormant_owner_priority`.
2. Each effective grant is a candidate when the cell is listed and its time and guard-adjusted frequency intervals overlap the entire atomic rectangle. Its priority is the grant priority.
3. If a primary activation covers the rectangle and cell, the owner priority becomes `primary_priority` and its source id is the lexically smallest covering activation id.
4. Remove any candidate covered by an applicable exclusion. If no candidate remains, winner fields are null and the slice is unassigned.
5. Otherwise choose minimum `(priority, source_id, party_id)`. Owner source id is the activation id when active, else `OWNER:<license_id>`.

The slice fields are `license_id`, `cell_id`, `start`, `end`, `low_khz`, `high_khz`, `duration_seconds`, `width_khz`, `winner_party_id`, `winner_source_id`, `winner_priority`, `preempted_source_ids` (all losing candidate source ids sorted), `auction_id`, `rate_cents_per_mhz_hour`, `gross_cents`, `winner_cents`, and `owner_cents`.

Select the effective auction covering the entire time atom by maximum `(start,auction_id)`; absent a match use auction id `default` and the policy default rate. Compute `gross_cents = ROUND_HALF_UP(duration_seconds * width_khz * rate / (3600 * 1000))`. An unassigned slice has gross/winner/owner all zero. If a grant wins, `winner_cents = ROUND_HALF_UP(gross_cents * share_bps / 10000)` and owner_cents is the remainder. If the owner wins, winner_cents equals gross_cents and owner_cents is zero; the owner's winning amount is still credited to the owner. Slices sort `(license_id,cell_id,start,low_khz,end,high_khz)`.

`preemption_ledger.json` contains one row for each slice with a nonempty preempted list or a primary activation winner. It repeats the slice identity and winner/source/priority plus preempted_source_ids. Sort as slices.

## Party settlement and corrections

Accumulate each assigned slice: credit `winner_cents` to the winner party; when a grant wins also credit `owner_cents` to the license owner. Gross-before-correction is this party/license total. Allocate the license's signed correction across parties with positive gross-before-correction using absolute largest remainder: exact share is `abs(total_correction)*party_gross/license_gross`; assign floors; distribute residual cents by descending fractional remainder then ascending party_id; restore the sign. If license gross is zero, assign the entire correction to its owner. `auction_adjustments.json` contains one row per valid license/party allocation, including zero allocations for parties with positive gross, with `license_id`, `party_id`, `gross_cents`, `correction_cents`, `net_cents`.

`party_settlements.json` contains parties with any gross or correction, sorted by party_id. Each row has `party_id`, sorted `license_ids`, `gross_cents`, `correction_cents`, `net_cents`, `won_slice_count`, and `preempted_slice_count` (count slices where one of that party's grant source ids appears among preempted sources).

## Reports

`manifest.json`: `{engine_version,input_files,valid_license_count,effective_grant_count,slice_count}`. `input_files` lists every regular input file sorted by name with `{name,sha256,bytes}`.

`data_quality.json`: `{input_file_count,record_counts,issue_count,issues}`. Record counts cover licenses, grant revisions, activations, exclusions, guard bands, auction revisions, and corrections. Issues are `{code,record_id}` sorted `(code,record_id)`.

`grant_ledger.json`: `{effective_grants,revision_decisions}`. Decisions contain `grant_id`, `winner_record_id`, and sorted `discarded_record_ids`.

`spectrum_slice_ledger.json`: `{slices}`. `preemption_ledger.json`: `{preemptions}`. `party_settlements.json`: `{parties}`. `auction_adjustments.json`: `{allocations}`.

`exception_register.json`: quality issues plus `{code:"MATERIAL_SETTLEMENT",record_id:<party_id>,net_cents}` for each party whose absolute net is at least `material_cents`, sorted `(code,record_id)`.

`audit_trace.json`: process party settlement rows in report order. Begin with 64 zeroes. Canonicalize each settlement using compact sorted-key JSON with ASCII escaping. `entry_hash = SHA256(previous_hash + canonical_row)`. Emit `{party_id,previous_hash,entry_hash}` and final_hash.
