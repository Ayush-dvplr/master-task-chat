# Data lineage and recording rules

## The ten recording rules

Every register in this directory is written under the rules
below. Each rule is a triple: the sentence that states it, the
transform applied when the register was written, and the
inverse the router applies when it reads it.

- **RR1 revision history.** A register carries every revision of
  every key. The row in force for a key is the row with the
  greatest `revision` that does not exceed that key's frozen
  revision. Frozen revisions live in `cycle_header.json` for the
  window grid, the device register and the device policies, and
  in `state_snapshot.json` for the cooldown register. Two rows
  that share a key and a revision settle on the one appearing
  later in the file. The greatest revision present is not the
  live one unless it happens to equal the frozen revision.
- **RR2 unit tokens.** A recorded quantity is a value and a unit
  token. The base value is
  `half_even(value * numerator / denominator)` under
  `unit_registry_dictionary.toml`. A withdrawn token or a zero
  denominator sets the record aside under `UNCONVERTIBLE_UNIT`.
- **RR3 alias references.** A column whose name ends in `_ref`
  may hold an identifier or an alias of one. Resolve it under
  stage r02 before using it.
- **RR4 layered absence.** A hyphen, an empty cell or an absent
  JSON key records an absent field, which inherits from the next
  layer down. A written zero records an explicit zero and
  settles the field where it is written.
- **RR5 sign columns.** A quantity that may be negative carries
  its sign in a separate column holding `+` or `-`. The value
  column is always the magnitude.
- **RR6 delta chains.** `window_grid.csv` records each window's
  start as the difference from the previous window's start, read
  in ascending `ordinal`, the first difference being taken from
  `cycle_header.json.origin_ms`. `context_activity_spans.tsv`
  records the same way in file order, its first difference
  also taken from `cycle_header.json.origin_ms`, never from
  zero. A row read on its own
  gives the wrong start.
- **RR7 interval ends are exclusive.** Every interval in this
  directory is half open. A window runs from its start inclusive
  to its end exclusive; a context is active from its start
  inclusive to its end exclusive; a one shot override applies
  strictly before its expiry.
- **RR8 pipe packed values.** `routine_defaults.toml` and
  `gating_rules.toml` pack several fields into one quoted string
  separated by a vertical bar. The field order is stated in the
  comment at the head of each file.
- **RR9 closed vocabularies.** Reason codes, layer names, edge
  kinds and statuses are closed sets. Their members are listed
  in `glossary_and_reason_codes.md`.
- **RR10 file order settles nothing.** Except where RR1 and RR6
  name it, the order rows appear in a register carries no
  meaning. Every published ordering is the ordering its stage
  specification states.

## Paper to stage map

| paper | stage it serves |
| --- | --- |
| `unit_registry_dictionary.toml` | r01 |
| `action_catalogue.csv` | r01, r03, r09 |
| `dependency_edges.tsv` | r01, r06 |
| `source_priority_register.csv` | r02 |
| `alias_crosswalk.tsv` | r02 |
| `identifier_supplement.psv` | r02 |
| `window_grid.csv` | r02, r03, r10 |
| `device_register.csv` | r02 |
| `context_activity_spans.tsv` | r02, r04 |
| `routine_register.csv` | r03 |
| `expansion_policy.yaml` | r03 |
| `household_operations_memo.pdf` | r03, r09, r11, r12 |
| `precedence_directive.docx` | r04, r07, r10, r12 |
| `override_journal.jsonl` | r04 |
| `context_policies.tsv` | r04 |
| `device_policies.csv` | r04 |
| `action_policies.jsonl` | r04 |
| `routine_defaults.toml` | r03, r04 |
| `global_defaults.yaml` | r04 |
| `cooldown_register.psv` | r04 |
| `precedence_and_overturn.toml` | r04, r12 |
| `state_snapshot.json` | r04, r05 |
| `prior_cycle_journal.jsonl` | r05 |
| `prior_cycle_archive.sqlite3` | r05 |
| `assistant_runtime.conf` | r05, r14 |
| `cycle_break_policy.toml` | r07 |
| `capacity_and_intensity_workbook.xlsx` | r09, r10, r14 |
| `capacity_binding_policy.yaml` | r10 |
| `state_effects.jsonl` | r13 |
| `gating_rules.toml` | r14 |
| `energy_ledger_history.ndjson` | r14 |
| `home_topology.xml` | r14 |
| `rounding_and_arithmetic_policy.yaml` | every stage |
| `publication_form_rules.toml` | r14 |
| `output_schema_reference.md` | r14 |
| `serialisation_and_digest_contract.md` | r14 |

## Reading rules for the prose papers

Every paper that carries prose rather than rows is written
under the ten reading rules below.

- **PR1 role naming.** A file name states a role, never its
  contents. The contents settle what the paper holds.
- **PR2 closed vocabulary.** Every code a paper uses is a member
  of a set listed in `glossary_and_reason_codes.md`.
- **PR3 stated order.** Where a paper lists keys, the list order
  is the order the rule is applied in.
- **PR4 stated boundary.** Every interval a paper names is half
  open, start inclusive and end exclusive.
- **PR5 stated tie break.** Every ordering a paper states ends
  in a key that cannot tie.
- **PR6 stated default.** A paper that names a default names the
  layer the default sits at as well.
- **PR7 stated cap.** A paper that names a cap names what
  happens at the cap and what happens past it.
- **PR8 stated exception.** A paper that names an exception
  names the rule the exception sits inside.
- **PR9 stated digest scope.** A paper that names a digest names
  the exact bytes it is taken over and the moment it is taken.
- **PR10 stated empty form.** A paper that names a document
  names the form that document takes when its group is empty.

## Papers that govern nothing

`readings_not_in_force.md` and `worked_examples.md` are reading
aids. `known_traps_and_footguns.md` is a reading aid. They
settle no value; the papers they describe do.

## Rows that govern nothing

Several registers carry retired rows so that the live rows are
not the only rows. A row is retired when its status column says
so, when its revision exceeds the frozen revision for its key,
when its identifier carries a `hist` or `retired` or `void` or
`spare` stem, or when the register it sits in is not named for
the stage in the map above. Retired rows are read and then not
used; they are not deleted from the count of rows read.
