# Corpus index

Every file in this directory is read on every run. The documents in this
directory carry the rules. The record files carry the evidence. No file is
decorative and no file repeats another.

## Rule documents

`corpus_index.md` this index. `source_manifest.md` row layouts and source
tiers. `temporal_rules.md` clock marks, cycles and the as of instant.
`identity_rules.md` customer references, aliases and epochs.
`provenance_rules.md` which source governs which field.
`amendment_rules.md` notices, endorsement and retraction. `state_machine.md`
request states and events. `capacity_rules.md` declared capacity and qualified
nodes. `substitution_rules.md` the node walk. `rounding_rules.md` the one
rounding stage. `ceiling_rules.md` entitlement ceilings.
`commitment_rules.md` committed minimums and their honouring order.
`carry_forward_rules.md` deficit lots. `allocation_policy.md` the properties
the apportionment satisfies. `output_contract.md` the shape of every artifact.
`errata_2031-07.md` corrections to named sections of the documents above.
`legacy_runbook.md` a withdrawn practice note, kept for reference only.

## Machine readable policy

`derivation_policy.ini` horizon, collapse window, hop limit, rounding stage,
unranked commitment rank and the recorder skew of each site.
`unit_declarations.ini` the unit vocabulary of every source.
`source_declarations.properties` source codes, file lists and the per field
precedence table. `reason_codes.json` the closed outcome and reason
vocabularies and the reason precedence.

## Request evidence

`orderbook_c01_c04.csv`, `orderbook_c05_c08.csv`, `orderbook_c09_c12.csv`,
`orderbook_c13_c16.csv`, `orderbook_c17_c20.csv`, `orderbook_c21_c24.csv`
split by the cycle of the order. `registry_q1.tsv`, `registry_q2.tsv`,
`registry_q3.tsv`, `registry_q4.tsv` split by calendar quarter of the
effective instant. `fixed_width_intake_h1.txt`, `fixed_width_intake_h2.txt`
split by half year.

## Change streams

`state_events_p1.jsonl`, `state_events_p2.jsonl`, `state_events_p3.jsonl`,
`state_events_p4.jsonl`, `state_events_p5.jsonl` versioned state changes.
`amendment_notices_p1.jsonl`, `amendment_notices_p2.jsonl`,
`amendment_notices_p3.jsonl` amendment notices.
`retraction_notices.csv` retractions.

## Registers and reference tables

`site_capacity_declarations.csv`, `node_substitution_factors.csv`,
`entitlement_ceilings_p1.csv`, `entitlement_ceilings_p2.csv`,
`entitlement_ceilings_p3.csv`, `commitment_agreements.csv`,
`priority_register.csv`, `commitment_exceptions.csv`, `customer_master.csv`,
`customer_alias_map.csv`, `authority_roles.csv`, `site_clock_marks.csv`.

## Audit and observation

`approval_audit.log` newest third of the endorsement audit,
`approval_audit.log.1` the middle third, `approval_audit.log.2` the oldest
third. `governance_observations.log` settled prior period quantity
divergences. `deficit_observations.log` settled prior period deficit lots.
