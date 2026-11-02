# Corpus index

This folder holds every record and declaration file for the year-end 2032 reserving task. The directory contains fifty six files total across csv, tsv, jsonl, log, ini, properties, md, json and txt formats. The authority order is: the four declaration files (`derivation_policy.ini`, `unit_declarations.ini`, `source_declarations.properties`, `reason_codes.json`) plus the rule and contract markdown documents listed under "Contract and rule documents" below. Everything else is evidence that those documents govern.

Read `source_manifest.md` next for the row layout of each flat source, and consult `output_contract.md` for the exact shape of every artifact.

## Contract and rule documents

- `output_contract.md`
- `source_manifest.md`
- `alae_rules.md`
- `allocation_rules.md`
- `amendment_rules.md`
- `attachment_rules.md`
- `chain_ladder_rules.md`
- `counterfactual_parameters.md`
- `data_quality_counting.md`
- `discounting_rules.md`
- `errata_2032-04.md`
- `priority_rules.md`
- `treaty_handbook.md` (withdrawn; governs nothing)

## Declaration files

- `derivation_policy.ini`
- `unit_declarations.ini`
- `source_declarations.properties`
- `reason_codes.json`

## Claim transaction logs (read by column position)

- `claim_tx_H01_H04.csv`
- `claim_tx_H05_H08.csv`
- `claim_tx_H09_H12.csv`
- `claim_tx_H13_H16.csv`
- `claim_tx_H17_H20.csv`
- `claim_tx_H21_H24.csv`
- `claim_tx_H25_H26.csv`

## Cession bordereau

- `cession_q1.tsv`
- `cession_q2.tsv`
- `cession_q3.tsv`
- `cession_q4.tsv`

## Fixed-width intake

- `fixed_width_intake_h1.txt`
- `fixed_width_intake_h2.txt`

## Observation logs

- `claim_adjustment_log.log`
- `treasury_curve_observations.log`

## Reserve-state events (applied by ascending version)

- `reserve_events_p1.jsonl`
- `reserve_events_p2.jsonl`
- `reserve_events_p3.jsonl`
- `reserve_events_p4.jsonl`
- `reserve_events_p5.jsonl`

## Endorsement circulars and audit logs

- `endorsement_circulars_p1.jsonl`
- `endorsement_circulars_p2.jsonl`
- `endorsement_circulars_p3.jsonl`
- `endorsement_audit.log`
- `endorsement_audit.log.1`
- `endorsement_audit.log.2`

## Reference tables

- `attachment_factors.csv`
- `attachment_windows.csv`
- `authority_roles.csv`
- `ceiling_register.csv`
- `claim_master.csv`
- `commitment_agreements.csv`
- `commitment_exceptions.csv`
- `curve_marks.csv`
- `cycle_marks.csv`
- `layer_capacity_declarations.csv`
- `priority_register.csv`
- `reinsurer_alias_map.csv`
- `reinsurer_master.csv`
- `retraction_notices.csv`
