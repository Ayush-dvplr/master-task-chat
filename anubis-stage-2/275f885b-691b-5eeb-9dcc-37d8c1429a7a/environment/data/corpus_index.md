# Corpus index

The campaign corpus is a flat export folder. Every file in it belongs to exactly one
provenance tier. The tier decides what a file is allowed to settle when two files disagree.

## Provenance tiers

1. Contract tier. `campaign_contract.md`, `output_contract.md`, `entitlement_rules.md`,
   `ration_rules.md`, `carry_rules.md`, `identity_rules.md`, `provenance_rules.md`,
   `temporal_rules.md`, `round_calendar_rules.md`, `supply_rules.md`,
   `substitution_rules.md`, `lot_state_machine.md`, `data_quality_rules.md` and
   `errata_notice.md`. The contract tier binds. Where `errata_notice.md` amends a named
   section, the amended text binds from its effective date and the replaced sentence binds
   nowhere.
2. Configuration tier. `source_declarations.properties`, `unit_declarations.ini`,
   `reason_codes.json`, `authority_scopes.json`. These carry the constants the contract
   refers to by name.
3. Primary source tier. `requisitions_r01_r04.csv` and its sibling batches,
   `dispatch_p1.jsonl` and its siblings, `lot_register_p1.csv` and its siblings,
   `release_certificates_h1.csv` and its sibling, `visit_events_p1.jsonl` and its siblings,
   `potency_assays_h1.txt`.
4. Reference table tier. `block_master.csv`, `block_alias_map.csv`, `priority_register.csv`,
   `block_ceilings_h1.csv` and its sibling, `dose_factors.csv`, `potency_factors.csv`,
   `substitution_graph.csv`, `campaign_phases.csv`, `depot_clock_offsets.csv`,
   `calendar_exceptions.csv`.
5. Correction stream tier. `amendment_notices_p1.jsonl` and its siblings.
6. Observation tier. `governance_observations.log`, `clearance_observations.log`. Observation
   files record what the settlement desk did on sampled cases. They carry no quantity that
   enters a report.
7. Legacy tier. `legacy_runbook.md`. The legacy tier governs nothing.

`source_manifest.md` lists every file by logical source. A file named there and absent from
the folder makes the export incomplete.

## Record file conventions

Every record file opens with a comment line of the form `# rows=NNNN` that declares the row
count the exporter believed it was writing. The next line of a delimited file is the column
header. Comment lines carry no records.

`registry_q1.tsv` and its siblings are tab delimited. A field left empty means the observation
did not read that quantity. A field holding `\N` means the recorded quantity was cleared by
the field office. A row that stops early omits its remaining fields, and an omitted field
leaves the earlier reading in force.

`potency_assays_h1.txt` is fixed width with the following layout, counting from column one:

```
1-9    lot reference
10-13  production year
14-19  assay reference
20-33  assay timestamp, YYYYMMDDHHMMSS
34-41  doses per unit, three implied decimals
42-46  laboratory code
```

## Column headers

```
block_master.csv          record_id,block_ref,valid_from,region,segment,species,age_class,risk_class,withdrawn_from,issued_at
block_alias_map.csv       alias_key,canonical_ref,effective_from,effective_to,issued_at
priority_register.csv     entry_ref,block_ref,tier,effective_from,issued_at
block_ceilings_h1.csv     entry_ref,block_ref,round_code,handling_ceiling,issued_at
dose_factors.csv          factor_ref,region,species,age_class,effective_from,doses_per_100_head,issued_at
potency_factors.csv       factor_ref,depot,serotype,unit,effective_from,doses_per_unit,issued_at
substitution_graph.csv    edge_ref,from_serotype,to_serotype,effective_from,effective_to,potency_percent,approved_by,issued_at
campaign_phases.csv       revision_ref,region,round_code,target_serotype,issued_at
depot_clock_offsets.csv   depot,calendar_date,utc_offset_minutes,issued_at
calendar_exceptions.csv   notice_ref,round_code,region,action,new_start_date,issued_at
requisitions_r01_r04.csv  req_ref,holding_key,round_code,recorded_at,effective_at,head_count,species,age_class,source_tag
registry_q1.tsv           record_id,block_ref,observed_at,head_on_hand,status
lot_register_p1.csv       lot_ref,production_year,depot,serotype,quantity,consign_round,consign_date,expiry_at
release_certificates_h1.csv  cert_ref,lot_ref,production_year,state,issued_at,supersedes,signed_by
```

`dispatch_p1.jsonl` records carry `version`, `op`, `block_ref`, `round_code`, `recorded_at`,
`head_count` and `depot`. `amendment_notices_p1.jsonl` records carry `notice_ref`, `target`,
`block_ref`, `round_code`, `adjustment`, `recorded_at` and `signed_by`. `visit_events_p1.jsonl`
records carry `event_id`, `block_ref`, `round_code`, `event` and `occurred_at`.
