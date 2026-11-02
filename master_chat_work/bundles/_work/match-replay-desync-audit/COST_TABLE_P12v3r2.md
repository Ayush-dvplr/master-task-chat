# COST_TABLE (LEVER_RULES G10), P12 v3 r2, AFTER tests (P = 160)

Method: each wrong reading injected alone into the oracle (`single_lever.py` anchors on solution/solve.py,
sha f4603aa38eac, unchanged this round), scored with `local_score.py` on the AFTER tests and shipped data
(tests channel, hidden corpora included). Variants are oracle edits, so every variant already carries the
full fragment grammar (the grammar now published in calibration.md is the grammar solve.py always used).
Scores: `trap/scores_after_v3r2/*.txt`; BEFORE (P = 158): `trap/scores_before_v3r2/*.txt`.
Overall = 0.5 x tests share + 0.5 x rubric share (reward.toml), judge negatives taken as 0.

| lever | wrong reading | tests lost / P | share |
|---|---|---|---|
| L3 running charter allowance | per-entry cap, never drawn down (var_perentry; the v0 agent's reading) | 140 / 160 | 0.875 |
| L3 running charter allowance | draw on the opening charter (var_opening) | 140 / 160 | 0.875 |
| L3 running charter allowance | cancelled entries draw before the skip (var_cancelled_draw) | 140 / 160 | 0.875 |
| L4 renewal at live-window openings | one allowance for the whole walk, never renewed (var_norenew) | 140 / 160 | 0.875 |
| L1 green control | "every control reproduces, so settlement is right" (no code edit of its own: with L3 and L4 read right it changes no output) | 0 / 160 | 0.000 |
| F-03 (not a lever) | eleven quantities carried in source (var_carry_eleven) | 154 / 160 | 0.963 |

## All levers right but one (G10 rows)

| wrong lever | tests earned / P | overall at rubric 90 | overall at rubric 97.67 (v0) |
|---|---|---|---|
| L3 only (worst of three reflexes) | 20 / 160 | 51.25 | 55.09 |
| L4 only | 20 / 160 | 51.25 | 55.09 |
| L1 only | 160 / 160 | 95.00 | 98.84 |

## Two levers wrong (L3 + L4, L1 right), for reference

| variant | tests earned / P | overall at rubric 90 | overall at rubric 97.67 |
|---|---|---|---|
| combo_perentry_norenew | 20 / 160 | 51.25 | 55.09 |
| combo_opening_norenew | 20 / 160 | 51.25 | 55.09 |
| combo_cancelled_draw_norenew | 20 / 160 | 51.25 | 55.09 |

v0 agent program (harden_r1 agent_program, as delivered and the one-line adapted copy), which already rebuilds
the fragments itself: 20 / 160 (share 0.125, overall 51.25 at rubric 90, 55.09 at 97.67).

## G10 verdict: FAIL on L1 only

- L3 and L4 each cost 87.5% of P alone (gate >= 25%) and their single-wrong rows stay at 51 to 55 overall
  (gate < 70): PASS.
- L1 is an amplifier, not a separable reading: its wrong reading only hides an L3 or L4 slip from every
  self-check. Alone it costs 0 points, so its row is 95.00 overall. Not fixed this round (no new levers,
  no data change, per master direction).
- L3 and L4 fail the same whole-document checks (G1 cascade), so a second slip adds nothing; the tests
  separate "both right" from "either wrong", not one lever from the other.
