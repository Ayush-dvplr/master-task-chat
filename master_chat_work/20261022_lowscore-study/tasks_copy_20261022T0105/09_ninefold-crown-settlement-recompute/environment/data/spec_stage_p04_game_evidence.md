# P04 game evidence resolution

Produces the result and the game differential of every candidate board.

## The governing result sheet

Group the records of `match_result_sheets.ndjson` by round and `table_no`,
keep the applicable ones under the `result_sheet` section of
`revision_precedence.toml` and take the one with the highest `sheet_seq`. A
`superseded` record is out of scope whatever its `sheet_seq` is. A board
with no applicable sheet is treated as a board whose sheet carries the
absent marker in every field.

## The game rows in scope

Every row of `game_records.csv` of this event whose round and `table_no`
match the board is in scope, including rows that repeat a `game_no`.

- `games_a` is the count of rows whose `outcome` is `won_a` and whose
  `completed` is `yes`.
- `games_b` is the count of rows whose `outcome` is `won_b` and whose
  `completed` is `yes`.
- A `drawn` row counts for neither side. An `unplayed` row counts for
  neither side. A row whose `completed` is `no` counts for neither side.
  A `conceded_a` or `conceded_b` row counts for neither side.

`delta_a` is `games_a` less `games_b`. It is published as it falls,
including a value of exactly zero, and it is never normalised by the
result.

## The five evidence levels

The levels are tried in the order the `priority_rank` of the applicable
rows of `source_priority_register.csv` gives, lowest rank first. The first
level that decides the board decides it, and `basis` is that level's
`source_code`.

1. `sheet_adjudication`. The `adjudicated_result` of the governing sheet is
   not the absent marker. `result_code` is that value. This level decides
   the result alone: `games_a`, `games_b` and `delta_a` stay as the game
   rows leave them, whatever the adjudicated result says.
2. `game_concession`. A `conceded_a` row is in scope, or a `conceded_b`
   row, or both. A `conceded_a` row makes `result_code` `win_b` and a
   `conceded_b` row makes it `win_a`; when rows of both kinds are in scope
   `result_code` is `double_loss`. The game counts are untouched, so a
   conceding side keeps the games it had already won.
3. `completed_game`. `games_a` and `games_b` are not both zero.
   `result_code` is `win_a` when `games_a` exceeds `games_b`, `win_b` when
   `games_b` exceeds `games_a`, and `draw` when they are equal.
4. `declared_count`. Neither `declared_games_a` nor `declared_games_b` of
   the governing sheet is the absent marker. `result_code` is `win_a` when
   the declared count of side a exceeds that of side b, `win_b` in the
   opposite case and `draw` when they are equal. The declared counts decide
   the result alone and never become `games_a` or `games_b`.
5. `no_evidence`. Nothing above decided the board. `result_code` is
   `double_loss`.

## Delivered

`match_result_ledger.csv`, one row per candidate board, ascending round
then ascending `table_no`.
