# Stage r01 - unit normalisation

Fed by: nothing.
Feeds: r02, r03, r04, r06.

Read `action_catalogue.csv` and `dependency_edges.tsv` and carry
every recorded quantity into its base unit under RR2.

- A catalogue row whose energy or duration cannot be carried is set
  aside under `UNCONVERTIBLE_UNIT` and takes no further part. Both
  its unit tokens are still counted.
- Edge strength is recorded once per declared sequence. Every row
  of `dependency_edges.tsv` is counted, and the strength recorded
  for a declared sequence is the converted strength of the last of
  its rows, in file order, whose strength can be carried. A declared
  sequence none of whose rows can be carried records no strength,
  and its edges are dropped in r06 under the same reason.
- `unit_counts` counts one for every recorded quantity, by the token
  it carried, over the catalogue energies, the catalogue durations
  and the edge strengths.
- `totals.energy_mwh` and `totals.duration_ms` sum the catalogue rows
  that converted. `totals.weight_bp` sums the edge strengths that
  converted.
- Publish `unit_normalization.json`.
