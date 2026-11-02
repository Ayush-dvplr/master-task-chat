# Worked examples

The figures below belong to an invented event, NC-0000-A0, with three
rounds and four entrants. They fix the FORM of the two free text
documents and of the sectioned control totals. Take shape from them and
no figure.

## event_settlement_summary.md

```
# Settlement summary NC-0000-A0

Event EV-0000 settled over 3 rounds with 4 entrants seated.

## Standings

| rank | player_id | division_id | event_points | adjusted_delta |
|---|---|---|---|---|
| 1 | PL-AA-0001 | dv_arbor | 7 | 3 |
| 2 | PL-AA-0002 | dv_arbor | 4 | 0 |
| 3 | PL-AA-0003 | dv_brine | 4 | -1 |
| 4 | PL-AA-0004 | dv_brine | 0 | -2 |

## Pairing

Boards admitted at level 0: 4. Level 1: 1. Level 2: 0. Level 3: 0.
Byes awarded: 2. Boards voided: 1. Entrants left unpaired: 0.

## Settlement

Pool 100000 cents. Awarded 99998 cents. Residue 2 cents.
Tie groups holding more than one member: 1.
```

## settlement_control_totals.conf

```
[event]
event_id = EV-0000
event_reference = NC-0000-A0
round_count = 3
player_count = 4

[totals]
round_points_total = 15
game_delta_total = 0
penalty_units_total = 1
points_per_round_ratio = 1.250000000

[pairing]
boards_total = 5
byes_total = 2
voided_total = 1
unpaired_total = 0
level_1_boards = 1
level_2_boards = 0
level_3_boards = 0

[prize]
pool_cents = 100000
awarded_cents = 99998
residue_cents = 2
tie_groups = 1
award_share_ratio = 0.999980000
```

A section holds its keys in the order printed above. A ratio carries
exactly nine decimal places. A whole quantity carries no decimal point.
