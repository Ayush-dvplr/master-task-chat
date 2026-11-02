# Halvard backtest extract: file index

This page names every file of the extract and its layout. The rule documents
say what the records mean; this page only says what each file holds. Every
`.csv` file has a header row and comma separated fields with no quoting.
Every `.jsonl` file holds one JSON object per line. Times written with a
trailing `Z` or `+00:00` are UTC; plain dates are calendar dates.

## Rule documents

| File | Subject |
|---|---|
| `backtest_rules.md` | snapshots, knowledge instants, the watermark, observations, unresolved observations |
| `calendar_rules.md` | regional clocks, business days, the roll of due dates |
| `identity_rules.md` | lease, obligor, branch and tax id references, merges, segments |
| `lifecycle_rules.md` | lease events, versions, states, payment holidays |
| `schedule_rules.md` | instalment schedules, holidays, tolerance, days past due |
| `cash_rules.md` | the three payment sources, returns, rejects |
| `feature_rules.md` | the characteristics, lineage and quarantine |
| `scorecard_rules.md` | scorecard versions, bins, points, approval, exclusions |
| `label_rules.md` | performance window and outcome labels |
| `metrics_rules.md` | populations, AUC, KS, rates, rounding |
| `output_contract.md` | the nine reports and the closing message |
| `ops_cheatsheet.md` | informal servicing desk notes, superseded by the rule documents, not part of the contract |
| `legacy_runbook.md` | the retired 2023 runbook, kept for audit |

## Configuration and reference files

| File | Layout |
|---|---|
| `backtest_run.toml` | table `[run]`: `run_id`, `first_snapshot`, `snapshot_count`, `snapshot_step_months`, `performance_days`, `bad_dpd`, `data_cutoff`, `watermark_utc`, `cut_local_time`, `notices_through` |
| `region_clock.ini` | one section per region (`north`, `south`, `west`, `east`): `standard_offset`, `daylight_offset` (minutes east of UTC), `daylight_periods` (comma separated `start/end` UTC spans) |
| `branches.ini` | `[branches]` code `= Region`; `[aliases]` alias `=` branch code |
| `holiday_calendar.ics` | `VEVENT` blocks with `DTSTART`, `DTEND`, `SUMMARY`, `CATEGORIES` (regions), `STATUS` |
| `servicing_policy.ini` | `[tolerance] commercial_cents, public_cents`; `[card] surcharge_cents`; `[relief] max_holidays_per_lease` |
| `return_codes.ini` | `[codes]` code `= yes` or `no` |
| `bureau_vendors.ini` | `[general] max_age_days`; `[precedence] commercial, public`; `[KR] scale`; `[ND] scale, to_kr_numerator, to_kr_denominator` |
| `bureau_disputes.json` | list `disputes`: `pull_id`, `vendor`, `recorded_at` |
| `sector_reference.json` | object `sectors`: sector code to risk class |
| `feature_lineage.yaml` | maps `nodes` and `characteristics`, each name listing the nodes it is computed from |
| `data_incidents.json` | list `incidents`: `incident_id`, `source`, `regions`, `from_utc`, `to_utc`, `declared_at`, `status` |
| `exclusion_policy.yaml` | list `exclusions`, each with `reason` |
| `score_bands.yaml` | list `bands`, each with `band`, `lo`, `hi` |
| `scorecard_registry.json` | list `versions`: `version`, `file`, `effective_from`, `status` |
| `scorecard_v6.json`, `scorecard_v7.json`, `scorecard_v7b.json` | `version`, `base_points`, `cutoff`, `characteristics` (see `scorecard_rules.md`) |

## Record files

| File | Layout |
|---|---|
| `leases.csv` | `lease_id, obligor_ref, start_date, term_months, instalment, anchor_day, product` |
| `lease_branch_history.csv` | `row_id, lease_ref, branch_code, effective_from, recorded_at` |
| `lease_events.jsonl` | `event_id, version, lease_ref, type, effective_date, recorded_at` |
| `relief_approvals.csv` | `status_id, request_id, lease_ref, status, months, first_deferred_instalment, status_at` |
| `obligors.csv` | `obligor_id, legal_name, tax_id, created_at, crm_segment` |
| `obligor_events.jsonl` | `event_seq, obligor_ref, type, effective_date, recorded_at` and, by type, `sector_code`, `tax_id`, `into` or `legal_name` |
| `public_entity_register.csv` | `register_id, fein, entity_name, listed_on, delisted_on` |
| `lockbox_north.csv`, `lockbox_south.csv`, `lockbox_west.csv`, `lockbox_east.csv` | `item_id, remit_ref, amount, value_date, received_at` |
| `card_settlements.csv` | `auth_code, lease_ref, amount, settlement_date, batch_at` |
| `servicing_ledger_YYYY.jsonl` | `posting_id, lease_id, channel, source_ref, amount, posted_at`; one file per UTC calendar year of `posted_at`; the extract always holds the file of every year from the year of the earliest lease `start_date` through the year of `data_cutoff`, and may hold later years. In `/app/data` they are `servicing_ledger_2023.jsonl`, `servicing_ledger_2024.jsonl`, `servicing_ledger_2025.jsonl` and `servicing_ledger_2026.jsonl`; other extracts hold the years their own dates require |
| `ach_returns.log` | `<UTC time> RETURN id=<return id> posting=<posting id> code=<code>`; lines starting with `#` are comments |
| `bureau_kr.jsonl` | `pull_id, tax_id, pulled_on, recorded_at, status, score` |
| `bureau_nd.csv` | `pull_ref, fein, pull_date, loaded_at, result, score` |
| `credit_limits.csv` | `limit_id, obligor_ref, limit_k, effective_from, recorded_at` |
| `invoice_notices.csv` | `invoice_no, lease_id, instalment_no, printed_due_date, issued_on` |
| `snapshot_runs.log` | production snapshot run log: `RUN`, `LOAD`, `BOUNDARY` and `END` lines |

Every configuration, reference and record file listed above is a required
input, including every servicing ledger year the extract promises.

## Units

`instalment` in `leases.csv` and `amount` in the lockbox files and in
`card_settlements.csv` are dollars written with exactly two decimals. `amount`
in the servicing ledger is integer cents. `limit_k` is thousands of dollars.
Every money figure in the reports is integer cents.
