# File role index

Every file in the extract plays one of four roles. A file of record decides a
field. A superseded file carries the same field with older or unapproved
numbers and decides nothing. An input file carries a field no other file
carries. An advisory file is kept for operators to read and decides nothing.

| file | role | field it decides |
|---|---|---|
| `path_register.csv` | file of record | the departure and the validity window of every path |
| `path_register_prior.csv` | superseded | nothing, it is the previous issue of the register |
| `recurrence_rules.json` | file of record | the body of every recurrence rule |
| `recurrence_rules_draft.json` | superseded | nothing, it is an unapproved draft |
| `zone_transitions.csv` | file of record | the offset history of every zone |
| `zone_transitions_proposed.csv` | superseded | nothing, it is a proposal |
| `headway_policy.json` | file of record | the headway policy before any approved revision |
| `wtt_mailbox.mbox` | file of record | the approved revision of a section class headway |
| `operator_register.html` | file of record | the rank weight of every operator |
| `legacy_compiled_output.json` | superseded | nothing, it is the aborted run's own output |
| `exception_dates.csv` | input | the exclusions and additions of every path |
| `path_alias_map.csv` | input | the retired identifiers |
| `section_register.csv` | input | the class and zone of every section |
| `section_route.psv` | input | the sections and offsets of every route |
| `timetable_period.json` | input | the identifier and bounds of the timetable period |
| `timetable_rulebook.md` | advisory | nothing, it is the contract itself |
| `report_schema.md` | advisory | nothing, it is the output contract |
| `file_role_index.md` | advisory | nothing, it is this index |
| `recurrence_primer.md` | advisory | nothing, worked selections |
| `zone_primer.md` | advisory | nothing, worked offsets |
| `headway_primer.md` | advisory | nothing, worked admission |
| `overlay_primer.md` | advisory | nothing, worked supersession |
| `worked_reference_slice.md` | advisory | nothing, a worked micro compile |
| `glossary.md` | advisory | nothing, terms |
| `known_issues.md` | advisory | nothing, operator notes |
| `compiler_debug.log` | advisory | nothing, the aborted run's trace |
| `extract_provenance.txt` | advisory | nothing, the cut description |

Four superseded files ship, and each of them looks exactly as well formed as
the file of record beside it. A compile that reads one of them is wrong in the
field that file carries, and wrong in every later stage that consumes it.
