# Delivered document schema reference

Every document below is written under the output directory with the
exact name given. The column list of a delimited document is its header
row in this order. The key list of a JSON document is its key order. The
serialisation and digest contract governs encoding, line endings,
indentation, empty shapes and trailing line feeds.

A quantity described as whole is published as a whole number with no
sign for zero. A ratio is published at exactly nine decimal places. A
strength is published in thousandths as a whole number. A prize amount
is published in whole cents.

## normalised_entries.jsonl

- shape: one JSON object per line
- keys: player_id, division_id, seed_number, rating_mr, rating_source, entry_seq, folded_ids
- rows: one record per settled entrant, ascending player_id

## participation_ledger.csv

- shape: comma separated
- header: player_id, round_no, state, governing_code, governing_seq
- rows: one row per entrant and round, ascending player_id then round_no

## round_match_candidates.csv

- shape: comma separated
- header: round_no, table_no, player_a, player_b, sheet_revision, source_seq
- rows: one row per applicable recorded board, ascending round_no then table_no

## match_result_ledger.csv

- shape: comma separated
- header: round_no, table_no, player_a, player_b, result_code, basis, games_a, games_b, delta_a
- rows: one row per candidate board, ascending round_no then table_no

## round_eligibility_ledger.csv

- shape: comma separated
- header: round_no, player_id, division_id, eligible, state, running_points, running_delta
- rows: one row per entrant and round, ascending round_no then player_id

## bye_ledger.csv

- shape: comma separated
- header: round_no, division_id, player_id, byes_before, basis
- rows: one row per awarded bye, ascending round_no then division_id

## authoritative_pairing_ledger.csv

- shape: comma separated
- header: round_no, board_no, player_a, player_b, division_a, division_b, admission_level, points_a, points_b
- rows: one row per authoritative board, ascending round_no then board_no

## void_adjudication_ledger.csv

- shape: comma separated
- header: round_no, table_no, player_a, player_b, void_reason, violation_level, tolerance, scored_a, scored_b
- rows: one row per voided board, ascending round_no then table_no

## round_score_ledger.csv

- shape: comma separated
- header: round_no, player_id, division_id, basis, base_points, modifier_code, modified_points, round_points, game_delta
- rows: one row per eligible entrant and round, ascending round_no then player_id

## penalty_application_ledger.psv

- shape: pipe separated
- header: round_no, player_id, penalty_class, magnitude, notice_seq, value_before, value_after, shortfall
- rows: one row per applied notice, ascending round_no then player_id then the applied class order

## opponent_history_ledger.csv

- shape: comma separated
- header: round_no, player_id, opponent_id, counts_for_strength, source
- rows: one row per encounter side, ascending round_no then player_id then opponent_id

## opponent_strength_ledger.csv

- shape: comma separated
- header: player_id, opponent_count, rate_sum, opponent_strength, penalty_units, penalty_adjusted_strength
- rows: one row per entrant, ascending player_id

## standings_ledger.csv

- shape: comma separated
- header: rank, player_id, division_id, event_points, adjusted_delta, opponent_strength, penalty_adjusted_strength, penalty_units, prize_eligible
- rows: one row per entrant, ascending rank

## settlement_manifest.json

- shape: one JSON object
- keys: event_id, event_reference, round_count, player_count, core_digest, publication_digest, documents
- rows: the core digest covers the six core documents in the order the artifact contract lists them; the publication digest covers every other delivered document in that same order; each documents entry carries name, sha256 and bytes in that key order, where name is the file name, sha256 the lowercase hexadecimal digest of its bytes and bytes its byte length as a JSON number

## pairing_fallback_ledger.csv

- shape: comma separated
- header: round_no, board_no, player_a, player_b, admission_level, relaxed_constraints
- rows: one row per board admitted above level zero, ascending round_no then board_no

## repeat_opponent_audit.tsv

- shape: tab separated
- header: player_id, opponent_id, meetings, rounds
- rows: one row per ordered pair that met more than once, ascending player_id then opponent_id

## unpaired_ledger.tsv

- shape: tab separated
- header: round_no, division_id, player_id, running_points, reason
- rows: one row per eligible entrant left with neither a board nor a bye, ascending round_no then player_id

## pairing_constraint_report.json

- shape: one JSON object
- keys: event_reference, rounds
- rows: one rounds entry per round in ascending order, each carrying round_no, boards, byes, unpaired, level_counts, cross_division_boards, repeat_boards and voided_boards, where level_counts is a JSON object carrying level_0, level_1, level_2 and level_3 in that key order, each written even when the level admitted no board

## game_differential_ledger.psv

- shape: pipe separated
- header: player_id, rounds_counted, raw_delta, game_penalty_units, adjusted_delta
- rows: one row per entrant, ascending player_id

## tiebreak_resolution_ledger.csv

- shape: comma separated
- header: rank, player_id, next_player_id, separating_position, separating_key
- rows: one row per adjacent pair in the standings, ascending rank

## final_ranking.json

- shape: one JSON object
- keys: event_id, event_reference, round_count, player_count, ranking
- rows: one ranking entry per entrant in ascending rank, each carrying rank, player_id, event_points, adjusted_delta, opponent_strength and penalty_adjusted_strength

## player_audit_trace.jsonl

- shape: one JSON object per line
- keys: player_id, division_id, seed_number, rounds, event_points, adjusted_delta, opponent_strength, rank, awarded_cents
- rows: one record per entrant, ascending player_id; each rounds entry carries round_no, state, basis, round_points and game_delta

## prize_allocation_ledger.csv

- shape: comma separated
- header: rank, player_id, group_id, group_basis_points, group_amount_cents, members, base_share_cents, remainder_cent, prize_eligible, awarded_cents
- rows: one row per entrant whose prize group carries group_basis_points above zero, ascending rank

## prize_tie_split.tsv

- shape: tab separated
- header: group_id, rank_span, members, group_basis_points, group_amount_cents, base_share_cents, remainder_cents, player_ids
- rows: one row per tie group holding more than one member, ascending group_id

## standings_by_division.xml

- shape: XML
- structure: settlement, division, entrant
- rows: divisions in ascending report_order, entrants in ascending rank; the root settlement element carries the attributes event_id and event_reference, a division element carries id, report_order and entrants, and an entrant element carries rank, player_id, event_points, adjusted_delta, opponent_strength and awarded_cents, each in that attribute order

## settlement_control_totals.conf

- shape: sectioned key and value text
- structure: event, totals, pairing, prize
- rows: four sections in this order, keys inside a section in the order the stage specification lists them

## event_settlement_summary.md

- shape: free text
- structure: headings
- rows: the heading order and the sentence shapes the worked examples paper fixes

## division_report_dv_arbor.json

- shape: one JSON object
- keys: division_id, in_force, report_order, seated_players, paired_boards, byes_awarded, voided_boards, points_total, game_delta_total, awarded_cents, award_share_ratio, top_player
- rows: one report per division named in force by the topology, written even when no entrant was seated in it; in_force is a JSON boolean, award_share_ratio a JSON string of nine decimal places, top_player a JSON string, and every other value a JSON number

## division_report_dv_brine.json

- shape: one JSON object
- keys: division_id, in_force, report_order, seated_players, paired_boards, byes_awarded, voided_boards, points_total, game_delta_total, awarded_cents, award_share_ratio, top_player
- rows: one report per division named in force by the topology, written even when no entrant was seated in it; in_force is a JSON boolean, award_share_ratio a JSON string of nine decimal places, top_player a JSON string, and every other value a JSON number

## division_report_dv_cinder.json

- shape: one JSON object
- keys: division_id, in_force, report_order, seated_players, paired_boards, byes_awarded, voided_boards, points_total, game_delta_total, awarded_cents, award_share_ratio, top_player
- rows: one report per division named in force by the topology, written even when no entrant was seated in it; in_force is a JSON boolean, award_share_ratio a JSON string of nine decimal places, top_player a JSON string, and every other value a JSON number

## division_report_dv_dune.json

- shape: one JSON object
- keys: division_id, in_force, report_order, seated_players, paired_boards, byes_awarded, voided_boards, points_total, game_delta_total, awarded_cents, award_share_ratio, top_player
- rows: one report per division named in force by the topology, written even when no entrant was seated in it; in_force is a JSON boolean, award_share_ratio a JSON string of nine decimal places, top_player a JSON string, and every other value a JSON number

