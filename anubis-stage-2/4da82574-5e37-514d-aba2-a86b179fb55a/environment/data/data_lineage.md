# Paper lineage

| paper | stage | what it settles |
| --- | --- | --- |
| `epoch_header.json` | r01 r04 r06 | the frozen revision, the workbook epoch key and the four ranges |
| `custody_parameter_workbook.xlsx` | r01 r10 r11 | conversion factors, reversal scales, carry quanta, ceilings |
| `custody_board_memo.pdf` | r01 r11 r12 | round ceiling, implausible ceiling, settlement floor |
| `precedence_directive.docx` | r07 r10 r12 | the re offer ladder and the two closure rules |
| `unit_registry.toml` | r01 | the scale of each recorded unit symbol |
| `station_register_frozen.csv` | r02 r10 | the station class, region, hub and status in force |
| `programme_register.csv` | r02 | the programmes in force |
| `alias_crosswalk.tsv` | r02 | site and project codes carried over from earlier epochs |
| `topology_and_scope.xml` | r13 | the region and hub each station reports under |
| `event_journal.jsonl` | r03 | the desk journal as first lodged |
| `event_supplement.ndjson` | r03 | late lodges taken at the counter |
| `source_priority_register.csv` | r03 | which lodging source outranks which |
| `row_provenance_ledger.csv` | r03 | the lodging source of a record that carries none |
| `event_kind_ranks.csv` | r03 | the rank each kind takes in the canonical order |
| `withdrawn_event_journal.tsv` | r01 | identifiers the desk has recalled |
| `checkpoint_register.csv` | r04 | the status, digest and revision of each checkpoint |
| `checkpoint_states.jsonl` | r05 | the body of each checkpoint |
| `dependency_edges.psv` | r07 | the authoritative dependency edges |
| `compensation_links.csv` | r09 | the target each compensating event names |
| `compensation_policy.toml` | r10 | which counter each reversed kind moves |
| `eligibility_predicates.csv` | r12 | the closed predicate vocabulary and argument order |
| `eligibility_policy.yaml` | r01 r09 | the order the screening tests run in |
| `reporting_station_roster.conf` | r12 | the region rank on the re offer ladder |
| `allotment_ceiling_history.tsv` | r04 | the ceilings of earlier revisions |
| `prior_epoch_archive.db` | r04 | the counters the archive holds for each checkpoint |
| `quarantine_reason_catalogue.psv` | r14 | the reason codes and the stage each sits in |
| `rounding_and_arithmetic_policy.yaml` | r01 r10 r14 | the arithmetic basis and the ratio places |
| `publication_form_rules.toml` | r14 | the core digest document list |
| `package_expectations.toml` | r14 | the shape the delivered archive carries |
| `revision_precedence.toml` | all | which paper governs when two disagree |
| `project.zip` | all | the package as the facility currently runs it |

## Papers that govern nothing

`station_register_current.csv` carries revisions lodged after the
frozen register revision and is kept for comparison only.
`topology_drafts.xml` is the draft of the scope map.
`legacy_scale_table.csv` holds the scales of the prior epoch.
The `depends_on` list inside a journal record is a convenience copy
of an earlier edge set. `event_supplement.ndjson` rows whose
identifier begins `EVT-8` were lodged for a later epoch.
