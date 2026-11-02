# Paper lineage

| paper | stage it feeds | what it settles |
|---|---|---|
| entry_roster_register.csv | P01 | the filed entries and their revisions |
| entry_alias_register.csv | P01, P03 | the identifier closure |
| rating_return_sheet.psv | P01 | the filed rating returns |
| seat_assignment_register.csv | P01 | the declared seat order |
| membership_standing_register.csv | P02 | lapsed and restored standing |
| withdrawn_entry_journal.tsv | P01 | which revisions were withdrawn |
| division_topology.xml | P01, P14 | the divisions in force and the event reference |
| status_change_journal.tsv | P02 | drops, reentries, absences, reinstatements |
| penalty_notice_register.psv | P02, P09, P10 | the notices and their classes |
| appeal_disposition_journal.jsonl | P10 | how each notice was disposed of |
| recorded_pairing_table.csv | P03, P08 | the boards the hall recorded |
| match_result_sheets.ndjson | P04 | the filed result sheets |
| game_records.csv | P04 | the game level evidence |
| bye_award_journal.tsv | P08 | the byes the hall recorded |
| round_configuration_register.csv | P09 | the per round point values and modifier codes |
| division_admission_matrix.csv | P06, P07 | cross admission, bye override, band widening, default rating |
| source_priority_register.csv | P04 | the rank of each evidence source |
| panel_capacity_workbook.xlsx | P06, P07, P12, P14 | the score band, the bye cap, the strength debit and the prize pool |
| appeals_procedure_memo.pdf | P06, P07, P08, P09, P10, P14 | the point constants, the admission ladder, the penalty order and the prize clauses |
| standings_precedence_directive.docx | P06, P07, P08, P13 | the key positions of four key families and the division ranks |
| reporting_division_roster.conf | P14 | the report order of each division |
| unit_register_dictionary.toml | P01 | rating unit conversion |
| rounding_and_arithmetic_policy.yaml | every stage | where a rounding sits |
| boundary_conventions.yaml | P02, P10 | the round interval and its edges |
| revision_precedence.toml | P01, P03, P04, P10, P14 | which filing governs |
| pairing_precedence_policy.toml | P07, P08 | the ladder and the tolerance rule |
| penalty_precedence_policy.toml | P09, P10 | what each class reaches |
| tiebreak_rules.json | P12, P13 | the strength arithmetic and the ordering |
| prize_rules.json | P14 | the share table and the split |
| round_modifier_rules.json | P09 | the modifier fractions |
| settlement_form_rules.toml | P14 | absent markers and document form |
| output_schema_reference.md | P14 | the shape of every document |
| serialisation_and_digest_contract.md | P14 | encoding and digests |
| crownsettle_program_contract.md | the delivered program | its interface |
| worked_examples.md | P14 | the form of the free text documents |

## Navigation papers

These carry no rule of their own and point at the papers that do.

- open_this_first.txt names the reading order.
- crown_settlement_overview.md names the fourteen stages and their
  specifications.
- paper_lineage.md is this map.
- glossary_and_field_dictionary.md defines the terms the specifications use
  and separates the field names that look alike.
- known_traps_and_footguns.md registers which stage owns each decision the
  settlement turns on, and states no rule itself.
- corpus_sentinel_note.txt names the branches this event leaves unreached.

## Papers that govern nothing

Three papers were left in the bundle by the hall desk and settle no part
of this event. They are kept because the panel minute refers to them.

- legacy_season_extract.csv carries a previous season and no row of it
  belongs to this event reference.
- spectator_gate_returns.json carries hall admissions and no settlement
  quantity is derived from attendance.
- night_desk_audit.db carries desk notes filed against other references.

Any figure taken from those three is a figure taken from outside this
event.
