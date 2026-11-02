# Relay data index

Every file in this directory is read-only evidence for one promotion cycle of the
Hollowbrand Package Relay. The index below says what each file records and what
its less obvious fields mean. It does not say which decision any file settles.

## Specification documents

| File | Records |
| --- | --- |
| `relay_governance_spec.md` | scope of a cycle, the governing record rule, the gate report |
| `channel_ladder_spec.md` | the four channels, adjacency, seated revisions |
| `unit_identity_spec.md` | unit keys, mirror labels, content references |
| `temporal_rules_spec.md` | site clocks, freeze windows, recurring holds, waivers |
| `dependency_admission_spec.md` | requirement sources and admission ordering |
| `attestation_authority_spec.md` | integrity verdicts and delegated site authority |
| `budget_reservation_spec.md` | channel capacity, reserved pools, ranking |
| `metrics_definitions_spec.md` | every counted and derived figure |
| `operations_runbook_spec.md` | how the relay service is driven for a cycle |
| `artifact_contract_spec.md` | the shape of each file the cycle must leave behind |
| `scenario_definitions_spec.md` | the three replay scenarios |
| `operator_notes.md` | duty officer notes and the cycle parameters they recorded |

## Configuration layers

| File | Records |
| --- | --- |
| `relay_policy_baseline.json` | cycle identifiers, actor, trusted builders and their precedence, which requirement scopes are in force, and which table supplies membership and which supplies seated revisions |
| `horizon_config.json` | cycle identifier, decision instant, the service base address, the half open horizon and the request field the horizon is applied to |
| `revision_grammar.json` | the revision shape and the fields compared, in order |
| `platform_suffixes.json` | the closed registry of mirror label suffixes, in the order the label parser tries them |
| `boundary_semantics.json` | every instant and revision comparison the documents rely on, each declared inclusive or exclusive, and the scope of the three census counts an operator is asked for |
| `reason_code_registry.json` | every reason code, the decision it carries, and its order |
| `risk_tier_table.json` | the baseline risk tiers each channel admits and the tier rank |
| `site_overrides.json` | per site and channel risk tier denials |
| `release_bulletins.json` | release board bulletins, each with an action, a channel and a family |
| `quarantine_directives.json` | quarantine floors by family and channel scope |
| `delegation_grants.json` | which site may speak for which family |
| `channel_budgets.ini` | per channel budget and reserved pools |
| `site_registry.yaml` | the five operating sites and the calendar each uses |
| `business_calendar.yaml` | weekend days and holiday dates per site |
| `carry_forward_policy.json` | the carry count that triggers escalation and the flag that clears it |
| `scenario_overlays.json` | the parameters each replay scenario changes |

## Record tables

| File | Records | Field notes |
| --- | --- | --- |
| `unit_catalog.csv` | the risk tier and owning site of every unit, by generation | bi-temporal |
| `alias_bindings.csv` | content reference to unit key bindings | `retired_at` may be empty |
| `builder_attestations.jsonl` | which builder signed each content reference | `source_name` is `family-flavour` |
| `channel_membership_snapshot.csv` | the seating recorded at the start of the cycle | greatest `snapshot_seq` is current |
| `mirror_index_edge.tsv` | publication rows for the edge mirror | `revision` is the published revision |
| `mirror_index_canary.tsv` | publication rows for the canary mirror | `revision` is the published revision |
| `mirror_index_staging.tsv` | publication rows for the staging mirror | `revision` is the published revision |
| `mirror_index_stable.tsv` | publication rows for the stable mirror | `revision` is the published revision |
| `promotion_requests.jsonl` | every promotion request ever filed | `declared_family` is what the submitter typed |
| `withdrawal_notices.jsonl` | notices against a unit and revision | bi-temporal, `status` is `active` or `rescinded` |
| `embargo_records.jsonl` | embargoes against a unit and revision | bi-temporal, `release_instant` is absolute |
| `supersession_chains.csv` | which embargo replaces which | bi-temporal |
| `integrity_reports_central.jsonl` | central integrity verdicts | bi-temporal, a blank `verdict` is a filing fault |
| `qa_verdicts_site.csv` | site integrity verdicts | bi-temporal |
| `site_freeze_windows.csv` | announced freezes by site, channel, family and flavour | `start_local` is site wall time, `hold_len` counts hours, `flavour` may be `*` |
| `recurring_holds.csv` | weekly holds by site, channel, family and flavour | `start_local` is site wall time, `hold_len` counts minutes, `weekday` is Monday zero in site local time, `flavour` may be `*` |
| `hold_exceptions.csv` | cancellations and shifts of single hold occurrences | `occurrence_date` is a site local date |
| `site_clock_offsets.csv` | the offset history of every relay site | `utc_offset_minutes` applies from `from_instant` onward |
| `relay_audit.log` | relay events including channel seals | `status` and `event` both matter |
| `unit_revision_requires.csv` | the primary requirement table | `scope` is a free text class |
| `dependency_declarations_legacy.tsv` | the retired requirement table | kept for units the primary table never covered |
| `prior_cycle_decisions.csv` | decisions reached in earlier cycles | one row per cycle, unit, revision and channel |
| `carry_forward_state.csv` | how long a unit and channel pair has been carried | one row per cycle, unit and channel |
| `waiver_records.jsonl` | waivers by site, family and channel | bi-temporal, expiry counts business days |

## Normative parameters

```
request_table: promotion_requests.jsonl
evidence_file_count: 53
```
