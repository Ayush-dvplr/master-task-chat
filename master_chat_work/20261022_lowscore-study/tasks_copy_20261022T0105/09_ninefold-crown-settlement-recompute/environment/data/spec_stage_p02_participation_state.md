# P02 participation state

Produces the state of every entrant in every round of the event.

## The round of a tick

`status_change_journal.tsv` is written on the round tick clock. Round
intervals are start inclusive and end exclusive and each spans the
`ticks_per_round` of `boundary_conventions.yaml`. The round of a tick is
the tick divided by `ticks_per_round`, discarding the remainder, with one
added. A tick that lands exactly on a round boundary therefore belongs to
the later of the two rounds it touches.

## The governing change

For an entrant and a round, take the applicable journal rows of that
entrant whose round is at most that round, in ascending round then
ascending `note_seq` order, and apply them in that order from a starting
state of `seated`:

- `drop` sets the state to `dropped` and it persists into later rounds.
- `reentry` sets the state to `seated` and it persists into later rounds.
- `reinstate` sets the state to `seated` and it persists into later rounds.
- `absence` sets the state to `absent` for its own round alone and reaches
  no later round.

`governing_code` is the change code of the last applied row that still
reaches the round and `governing_seq` its `note_seq`. An absence of an
earlier round reaches no later round, so it never governs one. An entrant
no row reached carries the code `none` and the sequence zero.

## Membership standing

`membership_standing_register.csv` is keyed on the `membership_ref` of the
governing roster filing of the entrant. Take the applicable rows of that
reference whose `effective_round` is at most the round, and of those the
one with the highest `effective_round`, breaking a tie on the highest
`notice_seq`. A `lapsed` standing sets the state to `barred`. A `current`
or `restored` standing leaves the state as the journal left it.

## Expulsion

An applicable row of `penalty_notice_register.psv` whose `penalty_class` is
`expulsion` sets the state to `barred` for its `effective_round` and every
round after it. No boundary arithmetic is applied to an `effective_round`.

`barred` outranks every other state. It is set by the standing register and
by an expulsion notice and by nothing else, and no journal row lifts it. A
bar set by an expulsion holds for its `effective_round` and every round
after it. A bar set by a lapsed standing holds for as long as that lapsed
row is the governing standing of the round, and it ends in the first round
a later `current` or `restored` row governs. When an expulsion bars an
entrant the `governing_code` of that
round is `expulsion` and the `governing_seq` its `notice_seq`. When a
lapsed standing bars an entrant the code is `lapsed` and the sequence its
`notice_seq`. An expulsion outranks a lapsed standing when both reach the
same round.

## Delivered

`participation_ledger.csv`, one row per entrant and round, ascending player
identifier then ascending round.
