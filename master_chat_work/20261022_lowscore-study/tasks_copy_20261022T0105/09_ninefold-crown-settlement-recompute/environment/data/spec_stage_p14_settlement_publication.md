# P14 settlement and publication

## The pool

The pool is the `pool_cents` parameter of the live sheet of
`panel_capacity_workbook.xlsx`, in whole cents. It appears in no other
paper.

## The live sheet

`panel_capacity_workbook.xlsx` carries several sheets. The live sheet is
the one whose `sheet_reference` cell carries the `event_reference` of
`division_topology.xml`. The sheet name and the sheet position carry no
signal. Inside the live sheet a parameter row governs only when its
`status` is `operative`; a `withdrawn`, a `superseded` and an `indicative`
row govern nothing. A row whose `unit` is not the unit the reader needs is
still that row: read the unit.

## Tie groups

Walk the standings in ascending rank. Two adjacent entrants belong to one
group when their values are equal on every ordering key up to the
`tie_group_depth` clause of `appeals_procedure_memo.pdf`. Groups are
numbered from one in that walk order.

`group_basis_points` is the sum of the `basis_points` of
`prize_rules.json` for the ranks the group occupies; a rank the share table
does not carry contributes zero. `group_amount_cents` is the pool
multiplied by `group_basis_points`, divided by ten thousand and rounded
half to even.

## The split

`base_share_cents` is `group_amount_cents` divided by the member count,
discarding the remainder. The remainder is handed out one cent at a time
to the members in ascending player identifier order until it is exhausted;
`remainder_cent` is one for a member that received a cent and zero
otherwise. Eligibility does not enter the split: an ineligible member takes
its place in the order and its cent.

`awarded_cents` is `base_share_cents` plus `remainder_cent` for an eligible
member and zero for an ineligible one. The amount an ineligible member
would have taken is added to the residue and is redistributed to nobody.

`residue_cents` is the pool less every awarded cent.

## Delivered

`prize_allocation_ledger.csv`, one row per entrant whose group carries
`group_basis_points` above zero, ascending rank.

`prize_tie_split.tsv`, one row per group holding more than one member and
carrying `group_basis_points` above zero, ascending `group_id`.
`rank_span` is the lowest and the highest rank of the group joined with a
plus sign, and `player_ids` its members in ascending order joined with a
plus sign. `remainder_cents` is the whole remainder of the group.

## The division reports

One report per division `division_topology.xml` carries with `in_force`
equal to `yes`, written whether or not an entrant was seated in it.
`report_order` is the `report_order` of the operative section of
`reporting_division_roster.conf` for that division.

- `seated_players` is the count of entrants of the division.
- `paired_boards` is the count of authoritative boards of the event whose
  `player_a` is an entrant of the division.
- `byes_awarded` is the count of bye ledger rows of the division.
- `voided_boards` is the count of voided boards whose `player_a` is an
  entrant of the division.
- `points_total` is the sum of the `event_points` of its entrants and
  `game_delta_total` the sum of their `adjusted_delta`.
- `awarded_cents` is the sum of the `awarded_cents` of its entrants and
  `award_share_ratio` that sum divided by the pool, at nine decimal places.
- `top_player` is the entrant of the division with the lowest rank, or the
  absent marker when the division seated none.

## The remaining documents

`standings_by_division.xml` carries the divisions in ascending
`report_order` and inside each the entrants of that division in ascending
rank. The root element is `settlement` and it carries `event_id` and
`event_reference`. A `division` element carries `id`, `report_order` and
`entrants`, where `entrants` is the count of entrants seated in it. An
`entrant` element carries `rank`, `player_id`, `event_points`,
`adjusted_delta`, `opponent_strength` and `awarded_cents`. Each element
prints its attributes in the order named here.

`settlement_control_totals.conf` carries the four sections and the keys the
worked examples paper prints. `round_points_total` is the sum of every
`round_points` of `round_score_ledger.csv`, `game_delta_total` the sum of
every `adjusted_delta`, `penalty_units_total` the sum of every
`penalty_units`, and `points_per_round_ratio` the round points total
divided by the round count. `boards_total`, `byes_total`, `voided_total`
and `unpaired_total` are event counts, and `level_1_boards` to
`level_3_boards` the counts of authoritative boards at those admission
levels. `award_share_ratio` is the awarded total divided by the pool.
`tie_groups` is the count of rows of `prize_tie_split.tsv`: the tie groups
holding more than one member and carrying `group_basis_points` above zero.
A tie group whose ranks the share table does not carry is not counted.
The tie groups line of `event_settlement_summary.md` carries the same count.

`player_audit_trace.jsonl` carries one record per entrant with its rounds
in ascending order; a round the entrant was not eligible in carries the
P02 state, the basis `none`, and zero for both figures.

`event_settlement_summary.md` follows the form of `worked_examples.md`. Its
standings table carries the first ten ranks, or every rank when the event
seated fewer than ten entrants.

`settlement_manifest.json` carries the two digests of
`serialisation_and_digest_contract.md` and one entry per delivered document
except itself. An entry carries the keys `name`, `sha256` and `bytes` in
that order.

## The artifact contract order

The order the two digests and the manifest entries follow is the order
below. The six core documents are the first six names.

  1. normalised_entries.jsonl
  2. match_result_ledger.csv
  3. authoritative_pairing_ledger.csv
  4. round_score_ledger.csv
  5. opponent_strength_ledger.csv
  6. standings_ledger.csv
  7. participation_ledger.csv
  8. round_match_candidates.csv
  9. round_eligibility_ledger.csv
  10. bye_ledger.csv
  11. void_adjudication_ledger.csv
  12. penalty_application_ledger.psv
  13. opponent_history_ledger.csv
  14. pairing_fallback_ledger.csv
  15. repeat_opponent_audit.tsv
  16. unpaired_ledger.tsv
  17. pairing_constraint_report.json
  18. game_differential_ledger.psv
  19. tiebreak_resolution_ledger.csv
  20. final_ranking.json
  21. player_audit_trace.jsonl
  22. prize_allocation_ledger.csv
  23. prize_tie_split.tsv
  24. standings_by_division.xml
  25. settlement_control_totals.conf
  26. event_settlement_summary.md
  27. division_report_dv_arbor.json
  28. division_report_dv_brine.json
  29. division_report_dv_cinder.json
  30. division_report_dv_dune.json
