# Known traps and footguns

Each item names a place where the data of this household is
shaped in a way a casual reader can trip on. None of them names
a rule; the rule for each is in the stage papers and in
`data_lineage.md`.

- `window_grid.csv` records a start difference, not a start, and
  its revisions record different differences and spans.
- `identifier_supplement.psv` repeats aliases that
  `alias_crosswalk.tsv` already binds, to different targets.
- `alias_crosswalk.tsv` carries alias rings of more than one
  length.
- `device_policies.csv` leaves cells empty.
- `cooldown_register.psv` carries revisions above every frozen
  revision this cycle uses.
- The workbook carries more than one grid of the same shape.
- Some cells of the live grid record a written `0` and some
  record the absent sentinel.
- Some registers open with a byte order mark, some end their
  lines with a carriage return, and some carry quoted fields.
- `state_effects.jsonl` and `gating_rules.toml` carry rows for
  `AC-000` and other names the catalogue does not hold.
- The energy ledger carries every prior cycle, in no particular
  order.
- The topology carries retired circuit rows whose role is not
  `member`.
- Some routines have a period of zero.
