# P11 opponent history

Worked once per round, after P09. Closes the round loop.

## What creates an encounter

A candidate board of the round that P03 kept creates one encounter row for
each of its two entrants, naming the other as `opponent_id`, whenever both
entrants are eligible in the round. `source` is `board`.

- A board P08 left standing carries `counts_for_strength` `yes`.
- A board P08 voided carries `counts_for_strength` `no`. The two entrants
  did sit down together, so the encounter is recorded and the prior
  opponent constraint of P07 and the `repeat_opponent` check of P08 both
  see it. It contributes no opponent to the strength population of P12.

A bye creates no encounter. An unpaired entrant creates no encounter. A
board holding an entrant that is not eligible in the round creates no
encounter, on either side.

## Delivered

`opponent_history_ledger.csv`, ascending round then ascending player
identifier then ascending `opponent_id`.

`repeat_opponent_audit.tsv`, one row per ordered pair of entrants whose
encounter count across the event is above one, ascending player identifier
then ascending `opponent_id`. `meetings` is that count and `rounds` the
rounds of those encounters in ascending order joined with a plus sign.
