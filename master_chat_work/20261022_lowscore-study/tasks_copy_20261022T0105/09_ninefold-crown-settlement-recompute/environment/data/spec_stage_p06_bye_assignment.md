# P06 bye assignment

Worked once per round and per division, after P05 and before P07.

## When a bye is awarded

A division whose count of eligible entrants in the round is odd is awarded
one bye. A division whose count is even or zero is awarded none.

## The candidate set

The candidate set is the eligible entrants of the division whose count of
byes already awarded in earlier rounds is below the `max_byes` parameter of
the live sheet of `panel_capacity_workbook.xlsx`.

When the candidate set is empty the `bye_override` parameter of the
`division_admission_matrix.csv` row for that division and round decides.
With `yes` the candidate set becomes every eligible entrant of the division
and `basis` is `cap_override`. With `no` no bye is awarded, the division
keeps its odd count and P07 leaves one entrant unpaired.

Otherwise `basis` is `normal`.

## Which candidate takes it

Order the candidate set on the keys of the `bye_order` family of
`standings_precedence_directive.docx`, applied in ascending key position.
The first candidate takes the bye. `byes_before` is its count of byes
awarded in earlier rounds.

## What the bye credits

The bye credits the `bye_points` and the `bye_game_delta` clauses of
`appeals_procedure_memo.pdf`. A bye creates no opponent.

The `bye_award_journal.tsv` records the byes the hall awarded. It is
evidence for P08 and it is not the bye of this settlement.

## Delivered

`bye_ledger.csv`, one row per awarded bye, ascending round then ascending
`division_id`.
