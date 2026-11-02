# Crown settlement overview

Event EV-7718, reference NC-6093-N5. The settlement is recomputed in fourteen stages.

Stages one to four are worked once over the whole event. Stages five to
eleven are worked round by round, in that order, and a round is closed
before the round after it opens: stage seven of round four may not be
worked until stage eleven of round three has closed, because the running
state stage seven orders on is the state stage eleven left behind.
Stages twelve to fourteen are worked once, after the last round closed.

| stage | subject | specification |
|---|---|---|
| P01 | entry normalisation | spec_stage_p01_entry_normalisation.md |
| P02 | participation state | spec_stage_p02_participation_state.md |
| P03 | candidate board assembly | spec_stage_p03_candidate_boards.md |
| P04 | game evidence resolution | spec_stage_p04_game_evidence.md |
| P05 | round eligibility | spec_stage_p05_round_eligibility.md |
| P06 | bye assignment | spec_stage_p06_bye_assignment.md |
| P07 | authoritative pairing | spec_stage_p07_authoritative_pairing.md |
| P08 | admissibility and voids | spec_stage_p08_admissibility_voids.md |
| P09 | round scoring | spec_stage_p09_round_scoring.md |
| P10 | penalty application | spec_stage_p10_penalty_application.md |
| P11 | opponent history | spec_stage_p11_opponent_history.md |
| P12 | opponent strength | spec_stage_p12_opponent_strength.md |
| P13 | standings and tiebreaks | spec_stage_p13_standings_tiebreaks.md |
| P14 | settlement and publication | spec_stage_p14_settlement_publication.md |

## What the round loop couples

A board the authoritative pairing admits at a strict level makes the
recorded board of the same players answerable at that level, and a
recorded board the panel voids credits the void points instead of the
played result. The running points a void changes are the running points
the next round orders and bands on, so a single misread round moves every
round after it, the opponent strength of every player who met anybody in
it, and the prize settlement at the end.

## What is settled elsewhere

The arithmetic policy, the boundary conventions, the revision precedence,
the unit register, the pairing ladder, the penalty order, the tiebreak
rules, the prize rules and the round modifier rules each sit in their own
paper. A stage specification names the paper it takes a rule from and
does not restate its content.
