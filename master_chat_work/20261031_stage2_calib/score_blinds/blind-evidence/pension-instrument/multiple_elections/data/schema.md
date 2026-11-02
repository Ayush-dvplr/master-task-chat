# Pension Accrual COLA Rebase Contract (PACR-1.0)

Dates are ISO `YYYY-MM-DD`. All date intervals are half-open. JSONL row order is irrelevant. Identifiers are case-sensitive. Money is integer cents, rates are integer basis points, and every division explicitly described below uses `Decimal` with `ROUND_HALF_UP`. The reusable program receives `DATA_DIR OUT_DIR` and writes the nine reports below using sorted keys, two-space indentation, and one trailing newline.

## Inputs and validation

`policy.json` contains `engine_version`, `valuation_date`, positive `days_per_year`, and nonnegative `material_cents`. `plans.json` contains unique plans with `plan_id`, `accrual_bps`, `normal_age_months`, `early_reduction_bps_per_month`, `option_factor_bps`, and `annual_cap_cents`. `members.jsonl` contains `member_id`, `plan_id`, `birth_date`, and status. A member with an unknown plan or invalid date emits `INVALID_MEMBER` and is omitted.

`service_revisions.jsonl` is revisioned by `service_id`. Choose maximum `(revision, recorded_at, record_id)`, with UTC `recorded_at` compared chronologically. Winning peers sharing revision and recorded_at but differing in any field except record_id emit `REVISION_TIE_CONFLICT`; record ID still breaks the tie. A cancelled winner has a decision but no effective service. Active service is invalid if the member is absent or `start >= end`; emit `INVALID_SERVICE`. Decisions sort by service_id; effective service sorts `(member_id,start,end,service_id)`.

`salary_history.jsonl` rows contain member, half-open dates, and nonnegative `annual_salary_cents`. Invalid member, date range, or salary emits `INVALID_SALARY`. `leave_intervals.jsonl` rows contain member, dates, and `credit_bps` in 0..10000; invalid rows emit `INVALID_LEAVE`. `cola_rules.jsonl` rows contain plan, effective date, and nonnegative factor; invalid rows emit `INVALID_COLA`. `rebase_events.jsonl` rows contain member, effective date, and nonnegative factor; invalid rows emit `INVALID_REBASE`. `elections.jsonl` rows contain member, retirement date, and `option_factor_bps` in 0..10000; invalid rows emit `INVALID_ELECTION`. When a member has multiple valid elections, choose maximum `(retirement_date,election_id)`.

## Accrual atoms

For each effective service interval, cut at its endpoints, every overlapping valid salary and leave endpoint, every January 1, and the valuation date. Clip atoms to dates before the valuation date. For each positive atom choose the covering salary with maximum `(start,salary_id)`. If none exists, emit `MISSING_SALARY` for `service_id:start` and omit that atom. Salary used is `min(annual_salary_cents, plan annual_cap_cents)`. The leave factor is the minimum `credit_bps` among covering leaves, or 10000. `calendar_days = end-start`. Compute `credited_days = ROUND_HALF_UP(calendar_days * leave_factor / 10000)`. Compute `accrual_cents = ROUND_HALF_UP(capped_salary * accrual_bps * credited_days / (10000 * days_per_year))`. Each atom is rounded independently and sorted `(member_id,start,end,service_id,salary_id)`.

## Event revaluation and election

For each member, construct a chronological stream. An accrual atom posts at its `end`; plan COLA events and member rebase events occur at their effective date. Sort equal-date events by kind order `ACCRUAL`, `COLA`, `REBASE`, then event ID. Begin balance at zero. ACCRUAL adds `accrual_cents`. COLA or REBASE replaces balance with `ROUND_HALF_UP(balance * factor_bps / 10000)` and records before, after, and delta. Ignore events after the valuation date. The pre-election accrued benefit is the final balance.

For the selected election, age months are `(retirement_year-birth_year)*12 + retirement_month-birth_month - (1 if retirement_day < birth_day else 0)`. Early months are `max(0, normal_age_months-age_months)`. Reduction basis points are `min(10000, early_months * early_reduction_bps_per_month)`. First compute `reduced_cents = ROUND_HALF_UP(accrued_cents * (10000-reduction_bps)/10000)`, then `payable_cents = ROUND_HALF_UP(reduced_cents * election_option_factor_bps/10000)`. Without a valid election, reduction is zero and use the plan option factor.

## Reports

`manifest.json`: `{engine_version,input_files,valid_member_count,effective_service_count,accrual_atom_count}` with sorted `{name,sha256,bytes}` for every regular input file.

`data_quality.json`: `{input_file_count,record_counts,issue_count,issues}`. Issues are `{code,record_id}` sorted `(code,record_id)`.

`service_ledger.json`: `{revision_decisions,effective_services}`. Effective rows contain exactly `service_id,member_id,start,end`.

`accrual_ledger.json`: `{atoms}` with each atom containing `member_id,plan_id,service_id,salary_id,start,end,calendar_days,leave_factor_bps,credited_days,capped_salary_cents,accrual_bps,accrual_cents`.

`cola_ledger.json`: `{events}` where rows contain `member_id,event_date,event_kind,event_id,factor_bps,balance_before_cents,balance_after_cents,delta_cents`, sorted `(member_id,event_date,event_kind_order,event_id)`.

`member_benefits.json`: `{members}` rows sorted member ID with `member_id,plan_id,credited_days,base_accrual_cents,revaluation_delta_cents,accrued_cents,election_id,retirement_date,age_months,early_months,reduction_bps,option_factor_bps,payable_cents`.

`plan_rollups.json`: `{plans}` rows sorted plan ID with member count and sums of credited days, base accrual, revaluation delta, accrued, and payable cents.

`exception_register.json`: `{exceptions}` containing all quality issues plus `MATERIAL_BENEFIT` rows `{code,record_id,amount_cents}` for members whose absolute payable cents meet `material_cents`, sorted `(code,record_id)`.

`audit_trace.json`: `{rows,final_hash}`. Begin with 64 zeroes. For each member-benefit row in member order, hash the UTF-8 bytes of `previous_hash + canonical_compact_sorted_key_json(row)`. Store `{member_id,previous_hash,row_hash}`.
