# 75407a55-6665-505e-95d8-5ff9bdb3384f Contract (RWRL-1.0)

All input JSON is UTF-8. JSONL row order is non-semantic. Dates are period labels from `policy.periods`, whose listed order is chronological. All intervals and arithmetic are exact as described. Use integers and `Decimal` with `ROUND_HALF_UP`; do not use binary floating point.

## Inputs and validation

`policy.json` contains `engine_version`, ordered unique `periods`, `settlement_currency`, and nonnegative `material_cents`. `contracts.json` is a JSON array with one row per unique `project_id`; `distributor_fee_bps` must be in 0..10000. Invalid contracts are outside conforming extracts.

`statement_revisions.jsonl` rows contain `statement_id`, globally unique `record_id`, integer `revision`, UTC `recorded_at`, `status` (`active` or `cancelled`), `project_id`, `period`, `territory`, `currency`, and integer `amount_minor`. Resolve each statement independently. The winner is the maximum tuple `(revision, parsed recorded_at, record_id)`. Peers sharing the winning revision and recorded_at are compared after removing only `record_id`; differing payloads emit `{code:"REVISION_TIE_CONFLICT",record_id:statement_id}`. Record ID still selects the winner. Preserve every decision. A cancelled winner is not effective. An active winner is valid only when its project, period, territory withholding rule, and currency rate exist and amount is nonnegative; otherwise emit `INVALID_STATEMENT` and quarantine it.

`fx_rates.jsonl` rows contain unique `rate_id`, unique `currency`, positive integer `numerator`, and positive integer `denominator`. A statement's settlement gross cents is `ROUND_HALF_UP(amount_minor * numerator / denominator)`.

`withholding_rules.jsonl` rows contain unique `rule_id`, unique `territory`, and `withholding_bps` in 0..10000. For each effective statement independently, withholding is `ROUND_HALF_UP(gross_cents * withholding_bps / 10000)`. Fee base is `gross_cents - withholding_cents`. Distributor fee is `ROUND_HALF_UP(fee_base * project.distributor_fee_bps / 10000)`. Net receipts are gross minus withholding minus fee. Never aggregate before either rounding.

`cost_pools.jsonl` rows contain unique `pool_id`, project, positive integer `priority`, and nonnegative `opening_cents`. Project priorities must be unique. Invalid rows emit `INVALID_POOL` and are quarantined.

`allocations.jsonl` rows contain unique `allocation_id`, project, participant, and `share_bps` in 0..10000. For every project, valid rows must sum to exactly 10000 in conforming extracts. Invalid rows emit `INVALID_ALLOCATION`; after quarantine, a project's non-10000 sum emits `INVALID_ALLOCATION_TOTAL` and that project's statements cannot enter the waterfall.

`advances.jsonl` rows contain unique `advance_id`, project, participant, positive integer `priority`, and nonnegative `opening_cents`. The participant must have a valid allocation in the project, and priorities must be unique per `(project_id, participant_id)`. Invalid rows emit `INVALID_ADVANCE` and are quarantined.

`adjustments.jsonl` rows contain unique `adjustment_id`, project, period, participant, and signed integer `amount_cents`. Project, period, and participant allocation must exist; otherwise emit `INVALID_ADJUSTMENT` and quarantine. Adjustments do not affect project pools or advances.

## Chronological waterfall

Process projects by `project_id`, and within each project process every policy period in policy order, including periods with no statements. Sum effective statement gross, withholding, fee, and net values for the project-period.

Project recoupment pools are stateful. For a period, begin with prior closing balances (opening balances in the first period) and remaining receipts equal period net receipts. Visit pools by `(priority,pool_id)`. `recouped_cents = min(opening_balance_cents, remaining_receipts)`, then reduce both. The period's distributable cents is the final remaining receipts. Emit one pool row per project-period-pool, even when recoupment is zero.

Allocate positive distributable cents among valid project participants by exact shares. For each participant calculate `distributable * share_bps / 10000`: assign the integer floor, then give residual cents one at a time by descending fractional remainder and ascending participant ID. This largest-remainder allocation must sum exactly to distributable. Zero distributable gives zero gross shares.

Participant advances are also stateful. For each project-period-participant, start with the gross share and visit that participant's advances by `(priority,advance_id)`. Recoup `min(opening_advance_balance, remaining_share)`. Participant `advance_recouped_cents` is the sum and `payable_before_adjustment_cents` is the remainder. Sum valid signed adjustments for that exact project, period, and participant. Final `payable_cents = payable_before_adjustment_cents + adjustment_cents`. Emit a participant row for every allocation in every period, including zero rows.

## Output and ordering

All reports are JSON objects serialized with sorted keys, two-space indentation, ASCII escaping, and one trailing newline.

`manifest.json`: keys `engine_version,input_files,effective_statement_count,waterfall_period_count,participant_statement_count`. `input_files` contains `{name,sha256,bytes}` for every regular input file sorted by name.

`data_quality.json`: keys `input_file_count,record_counts,issue_count,issues`. `record_counts` has `statement_revisions,cost_pools,allocations,advances,withholding_rules,adjustments,fx_rates`. Issues are sorted by `(code,record_id)`.

`statement_ledger.json`: keys `revision_decisions,effective_statements`. Decision rows have `statement_id,winner_record_id,discarded_record_ids`, sorted by statement ID. Effective rows have `statement_id,project_id,period,territory,currency,amount_minor,gross_cents,withholding_cents,distributor_fee_cents,net_receipts_cents`, sorted by `(project_id,period,statement_id)`.

`waterfall_ledger.json`: key `periods`; rows have `project_id,period,gross_cents,withholding_cents,distributor_fee_cents,net_receipts_cents,pool_recouped_cents,distributable_cents`, sorted by `(project_id,policy period order)`.

`recoupment_ledger.json`: keys `project_pools,participant_advances`. Pool rows have `project_id,period,pool_id,priority,opening_balance_cents,recouped_cents,closing_balance_cents`, sorted by project, period order, priority, pool ID. Advance rows have `project_id,period,participant_id,advance_id,priority,opening_balance_cents,recouped_cents,closing_balance_cents`, sorted likewise with participant before priority.

`participant_statements.json`: key `statements`; rows have `project_id,period,participant_id,share_bps,gross_share_cents,advance_recouped_cents,payable_before_adjustment_cents,adjustment_cents,payable_cents`, sorted by project, period order, participant.

`project_rollups.json`: key `projects`; one row per project with `project_id,gross_cents,withholding_cents,distributor_fee_cents,net_receipts_cents,pool_recouped_cents,distributable_cents,advance_recouped_cents,adjustment_cents,payable_cents`, sorted by project.

`exception_register.json`: key `exceptions`. Start with all quality issues. Add `{code:"MATERIAL_PAYMENT",record_id:"project:period:participant",amount_cents:payable}` for every participant row whose absolute payable is at least `material_cents`. Sort by `(code,record_id)`.

`audit_trace.json`: keys `rows,final_hash`. Begin with 64 zeroes. For each participant statement in output order, compact canonicalize it with sorted keys and ASCII escaping, hash UTF-8 bytes of `previous_hash + canonical_row`, and emit `{project_id,period,participant_id,previous_hash,row_hash}`. `final_hash` is the final row hash or 64 zeroes.
