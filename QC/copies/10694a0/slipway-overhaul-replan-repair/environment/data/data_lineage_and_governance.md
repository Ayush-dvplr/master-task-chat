# Data lineage and governance

| file | stage | what it settles |
| --- | --- | --- |
| round_header.json | p01 | the round key and index, the workbook sheet key, the register in force |
| berth_job_register_frozen.csv | p01 | the register in force |
| berth_job_register_current.csv | p01 | nothing; the drafting copy |
| identifier_crosswalk.tsv | p01 | legacy identifiers |
| yard_topology.xml | p01 | the precincts that exist |
| topology_drafts.xml | none | nothing; a proposal |
| class_rate_register.csv | p01 | the class multipliers |
| licence_validity_register.csv | p04 | licence validity |
| priority_class_vocabulary.csv | p01 | the closed set of classes |
| yard_parameter_workbook.xlsx | p01 | shift lengths, pool weights |
| yard_board_memo.pdf | p01 | deferral rates, store retention, charge ceiling |
| cascade_precedence_directive.docx | p10, p13 | seed sets, reader table, order of application, duplicate and double booking rules |
| precedence_edge_journal.psv | p02 | the lodgements |
| exclusive_slot_groups.csv | p08 | the slot group memberships |
| pool_capacity_history.tsv | p09 | the pool capacities |
| carried_commitment_ledger.csv | p09 | the carried quantities |
| conditional_charge_rules.jsonl | p10 | the surcharges and the rebates |
| amendment_journal.jsonl | p13 | the amendments |
| amendment_supplement.ndjson | p13 | payload fields the journal leaves empty |
| row_provenance_ledger.csv | p13 | which file a payload field is read from |
| amendment_reason_catalogue.psv | p02, p08, p14 | the reason code vocabulary |
| source_priority_register.csv | p13 | the standing of each source file |
| legacy_scale_table.csv | none | nothing; retired when the workbook came in |
| prior_round_archive.db | none | nothing; the prior round, for context |
| withdrawn_plan_publication.tsv | none | nothing; the publication the desk pulled |
| withdrawn_counter_publication.csv | none | nothing; the counters beside it |
| planning_desk_roster.conf | none | nothing; a contact list |
| engine_defaults.ini | none | nothing; desk defaults |
| unit_registry.toml | p03 | the units |
| rounding_and_arithmetic_policy.yaml | p07, p10, p14 | where rounding happens |
| revision_precedence.toml | p01, p09 | which row of a register is in force |
| precedence_and_order_policy.toml | all | canonical order |
| publication_form_rules.toml | p14 | the form of the documents |
| package_expectations.toml | p14 | what the delivered engine has to be |
| output_schema_reference.md | p14 | the shape of every document |
| serialisation_and_digest_contract.md | p14 | encoding, line endings, digests |
| work_ledger_counter_contract.md | p13 | what each counter counts |
| project.zip | none | the engine as the yard currently runs it |
| 00_open_this_first.txt | none | nothing; where to start |
| replan_programme_contract.md | all | the fourteen stages and their papers |
| data_lineage_and_governance.md | none | nothing; this table |
| spec_stage_p01_identifier_and_revision.md | p01 | the register in force and the parameter layer |
| spec_stage_p02_precedence_graph.md | p02 | the graph and the order of the edge tests |
| spec_stage_p03_normalisation.md | p03 | the units, the amount grammar, the normalised record |
| spec_stage_p04_admissibility.md | p04 | the two admissibility tests and their order |
| spec_stage_p05_closure.md | p05 | the closure of a job and what blocks it |
| spec_stage_p06_demand.md | p06 | the own and closed vectors |
| spec_stage_p07_charges.md | p07 | the scaled charge, the penalty, the ceiling |
| spec_stage_p08_slot_groups.md | p08 | the double booking rule and what binds |
| spec_stage_p09_capacity.md | p09 | the capacities, the carried quantities, the boundary |
| spec_stage_p10_objective.md | p10 | the order of the charge stages and the four ranking keys |
| spec_stage_p11_search.md | p11 | the exact optimum of one precinct |
| spec_stage_p12_provenance.md | p12 | the inputs of a solve key |
| spec_stage_p13_amendments.md | p13 | the classification, the seeds and the cut off |
| spec_stage_p14_publication.md | p14 | the twenty five documents and the manifest |
| readings_not_in_force.md | none | nothing; readings this yard refuses |
| worked_examples.md | none | nothing; invented figures showing each rule |
| glossary_and_reason_codes.md | none | nothing; the vocabulary |

A file marked as settling nothing is still worth opening: it is where a wrong
reading of this round is most easily reached from.
