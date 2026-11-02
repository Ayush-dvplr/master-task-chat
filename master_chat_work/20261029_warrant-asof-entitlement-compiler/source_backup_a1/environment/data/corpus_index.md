# Warrant corpus index

This directory is one export of the Warrant entitlement estate. Every file in it is listed here with its layout. The files listed in `corpus_manifest.json` are the record and reference inputs; the Markdown files are the written contract; `tool.zip` holds the compiler source.

Rules live in the contract documents: `access_contract.md`, `identity_rules.md`, `time_rules.md`, `provenance_rules.md`, `config_contract.md`, `output_contract.md` and `cli_contract.md`. Where those documents and the compiler source disagree, the documents govern. `legacy_runbook.md` describes the retired 2024 process and governs nothing.

## Reference and configuration files

| File | Layout |
|---|---|
| `corpus_manifest.json` | `{"files": [...]}`, every input the compiler must find |
| `config_schema.json` | `anchor_keys`, `profiles`, and `keys` with `scope` (`global` or `profile`), `type` (`int`, `bool`, `enum`), bounds or `values`, and `class` (`ordinary` or `ceiling`) |
| `defaults.json` | `{"values": {key: value}}`, the lowest configuration layer |
| `profiles.toml` | `[dev]` and `[prod]` tables, the profile layer |
| `site_policy.ini` | `[anchor]` with `as_of` and `recorded_cutoff`, then `[global]`, `[dev]`, `[prod]` |
| `tz_rules.json` | `{"zones": {name: {"std_offset_min", "dst_offset_min", "transitions": [[utc_instant, "dst" or "std"], ...]}}}` |
| `hr_sites.json` | `{"sites": {site_code: {"tz": zone_name}}}` |
| `role_catalog.json` | `{"roles": {name: {"legacy_names", "includes", "permissions"}}}` |
| `permission_catalog.toml` | `[permissions."name"]` with `scope` (`dev`, `prod` or `both`) and `critical` |
| `sod_policy.json` | `{"pairs": [{"rule", "env", "a", "b"}]}` |
| `dir_groups.json` | `{"groups": [{"id", "name", "site"}]}` |
| `oncall_rotations.json` | `{"rotations": [{"id", "env", "role", "tz", "cadence", "weekday", "start", "duration_minutes"}]}`; `cadence` is `daily` or `weekly`, `weekday` 0 is Monday, `start` is `HH:MM` local wall time |
| `freeze_windows.json` | `{"windows": [{"env", "start", "end", "reason"}]}` |

## Record files

Each record file carries a recorded instant, the moment the record entered the estate. The column that holds it and its unit differ by file and are given here. The record id is the identifier the validation report uses for that file.

| File | Columns or keys | Recorded instant | Record id |
|---|---|---|---|
| `policy_change_journal.jsonl` | `seq`, `key`, `value`, `effective_at`, `recorded_at` | `recorded_at`, instant | `seq` as text |
| `hr_employees.csv` | `employee_no`, `display_name`, `site`, `manager_no`, `cost_center` | none, always visible | not reported |
| `hr_events_2025.csv`, `hr_events_2026h1.csv`, `hr_events_2026h2.csv` | `event_id`, `employee_no`, `event`, `effective_date`, `recorded_at` | `recorded_at`, instant | `event_id` |
| `hr_corrections.csv` | `correction_id`, `event_id`, `action` (`void` or `redate`), `new_effective_date`, `recorded_at` | `recorded_at`, instant | `correction_id` |
| `contractor_contracts.csv` | `contractor_id`, `amendment_no`, `site`, `sponsor`, `start_date`, `end_date`, `recorded_at` | `recorded_at`, instant | `contractor_id#amendment_no` |
| `idp_accounts_east.jsonl`, `idp_accounts_west.jsonl` | `handle`, `subject_ref`, `generation`, `state` (`enabled` or `disabled`), `synced_at` | `synced_at`, instant | `handle#generation` |
| `idp_mfa_events.log` | one line per event: `<at> <event_id> <enroll or reset> handle=<handle> recorded=<instant>`; lines starting with `#` are comments | `recorded=`, instant | event id |
| `directory_aliases.tsv` | `alias`, `handle`, `created_at` (tab separated) | `created_at`, instant | `alias` |
| `dir_members_site_a.csv`, `dir_members_site_b.csv`, `dir_members_site_c.csv`, `dir_members_site_d.csv` | `mid`, `group_id`, `member` (a handle or `group:<id>`), `added_at`, `recorded_at` | `recorded_at`, instant | `mid` |
| `dir_membership_removals.csv` | `removal_id`, `mid`, `removed_at`, `recorded_at` | `recorded_at`, instant | `removal_id` |
| `role_bindings_dev.csv`, `role_bindings_prod.csv` | `binding_id`, `group_id`, `role`, `bound_from`, `bound_until` (empty means open), `recorded_at` | `recorded_at`, instant | `binding_id` |
| `grant_requests_2026_05.jsonl`, `grant_requests_2026_06.jsonl`, `grant_requests_2026_07.jsonl`, `grant_requests_2026_08.jsonl`, `grant_requests_2026_09.jsonl`, `grant_requests_2026_10.jsonl` (monthly shards) | `ticket`, `export_generation`, `beneficiary`, `requester`, `env`, `target` (`role:<name>` or `perm:<name>`), `effective_from`, `effective_until`, `recorded_at` | `recorded_at`, instant | `ticket` |
| `grant_approvals.csv` | `approval_id`, `ticket`, `approver`, `decision` (`approve` or `reject`), `decided_at`, `recorded_at` | `recorded_at`, instant | `approval_id` |
| `grant_corrections.jsonl` | `ticket`, `revision`, `effective_until`, `recorded_at` | `recorded_at`, integer epoch **seconds** | `ticket#revision` |
| `revocations_selfservice.csv` | `rev_id`, `ticket`, `revoker`, `effective_at`, `recorded_at` | `recorded_at`, integer epoch **milliseconds** | `rev_id` |
| `revocations_secops.jsonl` | `case`, `subject`, `scope` (`all`, `env:dev`, `env:prod` or `perm:<name>`), `effective_at`, `recorded_at` | `recorded_at`, instant | `case` |
| `oncall_assignments.csv` | `assignment_id`, `rotation`, `week_start` (Monday, local date), `holder`, `revision`, `recorded_at` | `recorded_at`, instant | `assignment_id` |
| `oncall_swaps.csv` | `swap_id`, `rotation`, `shift_date` (local date the shift starts), `from_holder`, `to_holder`, `recorded_at` | `recorded_at`, instant | `swap_id` |
| `access_attestations.csv` | `attestation_id`, `reviewer`, `subject`, `permission`, `env`, `reviewed_at`, `decision` (`keep` or `revoke`), `observed_state`, `recorded_at` | `recorded_at`, instant | `attestation_id` |

Each alias appears on one row of `directory_aliases.tsv`. The two IdP files are shards named `east` and `west` after the part of the file name between `idp_accounts_` and `.jsonl`.

`observed_state` in `access_attestations.csv` is what the reviewer saw on the access gateway at `reviewed_at`: `in_effect` when the gateway honoured the permission for that subject in that `env` at that instant, `not_in_effect` otherwise. The gateway applies every rule of this contract except attestation gating and separation of duties, and it works from the records it held at `reviewed_at`. The column is an observation; it is never an input to a profile.

## Other files

| File | Content |
|---|---|
| `tool.zip` | source of `warrant-ctl`, the compiler, with `cli.py` at the archive root |
| `access_contract.md` | how profiles are compiled |
| `identity_rules.md` | principals, handles, aliases, accounts |
| `time_rules.md` | instants, dates, zones, windows |
| `provenance_rules.md` | authority, governing versions, validation, reason codes |
| `config_contract.md` | configuration layering |
| `output_contract.md` | every artifact shape |
| `cli_contract.md` | the compiler command line |
| `legacy_runbook.md` | superseded 2024 runbook |
