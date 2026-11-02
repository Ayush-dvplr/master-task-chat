# Working timetable compile rulebook

This is the governing contract for one compile of the regional working
timetable. It is written for whoever maintains the compiler. Every figure the
compile publishes follows from the rules below and from the extract the compile
is pointed at. Nothing here depends on a value that lives outside the extract.

The compile runs in ten stages. Each stage consumes the stage before it, so a
wrong figure in an early stage moves every figure after it.

Dates are plain calendar dates. Instants are UTC and are written
`YYYY-MM-DDTHH:MM:SSZ`. A local wall clock reading is a date plus an `HH:MM`
time with no offset attached; stage 6 is the only stage that turns one into an
instant. Day arithmetic is inclusive at both ends wherever a range is given.

`file_role_index.md` states the role every file in the extract plays, including
which files are superseded. `report_schema.md` states the exact shape of every
document the compile writes.

## Stage 1, path identity

A path identifier is written in several ways across the extract. The canonical
form is derived like this, and nothing else counts as a path identifier:

1. Upper case the spelling.
2. Drop every character that is not an upper case letter A to Z or a digit 0
   to 9.
3. The remaining characters have to be letters followed by digits, with no
   letter after the first digit. A spelling that leaves no letter, leaves no
   digit, mixes the two, or leaves more than five digits is malformed.
4. The canonical form is the letters, a single hyphen, and the digits read as a
   number and written back with five places.

So `wtt 1007`, `WTT-1007`, `wtt_01007` and `  WTT01007 ` all canonicalise to
`WTT-01007`, while `ZZ`, `12345` and `WTT-1A` are malformed.

`path_alias_map.csv` retires identifiers. A spelling is resolved by
canonicalising it and then, while the current identifier appears in the
`retired_path` column, moving to the `current_path` of that row, canonicalised
the same way. At most eight such moves are taken. Three outcomes end the walk:

- The current identifier does not appear in the `retired_path` column. That
  identifier is the resolution.
- The walk reaches an identifier it has already visited. The walk resolves to
  nothing. When the identifier it has arrived back at is the one the walk
  started from, that identifier sits on a cycle.
- Eight moves pass and the identifier reached still appears in the
  `retired_path` column. The walk resolves to nothing and the spelling counts
  as unresolved.

The identifiers tested for sitting on a cycle are the canonical forms of the
`retired_path` column together with the register's own identifiers, and the
compile reports the ones that do. A path is registered when its row appears in
`path_register.csv` and its identifier does not sit on a cycle. A path rejected
later, in stage 5, runs on no date at all and still appears in the identity
report, the withheld document, the canonical calendars and the digest.

## Stage 2, authority

Five fields are carried by two files each. `file_role_index.md` names the file
of record for every one of them, and the compile reads the file of record and
nothing else. The authority report states, per field, the file of record and
how far the superseded copy diverges from it. The five divergence counts are
defined as:

- `departure_window`: the number of path identifiers present in both
  `path_register.csv` and `path_register_prior.csv` whose `depart_local` or
  whose `valid_to` differ between the two.
- `recurrence_rule`: the number of rule identifiers present in both
  `recurrence_rules.json` and `recurrence_rules_draft.json` whose `setpos` list
  or whose `limit` differ between the two.
- `zone_transition`: the number of rows in `zone_transitions_proposed.csv`
  whose four fields do not appear as a row of `zone_transitions.csv`.
- `section_headway`: the number of messages in `wtt_mailbox.mbox` whose subject
  prefix is anything other than `APPROVED-HEADWAY`.
- `operator_rank_weight`: the number of operators whose `rank_weight` in
  `legacy_compiled_output.json` differs from the one in
  `operator_register.html`.

`wtt_mailbox.mbox` is a plain mbox. A message's subject line reads
`Subject: <PREFIX> <section class> <minutes>`. A message whose prefix is
`APPROVED-HEADWAY` replaces the minimum headway of that section class for this
compile. Any other prefix changes nothing. The body of a message is a courtesy
restatement and decides nothing.

`operator_register.html` carries one table row per operator with the
identifier, the name and the rank weight, in that order.

## Stage 3, rule expansion

Every path names a rule in `recurrence_rules.json`. A rule has a `freq`, an
`anchor` date, a `byday` list of ISO weekday numbers where Monday is 1 and
Sunday is 7, a `bymonthday` list of day of month numbers, a `setpos` list of
non zero integers, a `limit` and a `horizon_periods` count.

The rule is expanded period by period. Period 0 and the periods after it are:

- `month`: period k is the calendar month reached by moving the month that
  contains the anchor forward by k months. The period covers every day of that
  month.
- `isoweek`: period k covers the seven days starting at the Monday of the ISO
  week that contains the anchor, moved forward by 7k days.
- `fourweek`: period k covers the twenty eight days starting at the anchor
  moved forward by 28k days.

Periods 0 up to and including `horizon_periods` minus 1 are expanded, and no
others.

Inside one period the candidate set is every day of that period that satisfies
both of these, in ascending date order:

- `byday` is empty, or the ISO weekday of the day appears in `byday`.
- `bymonthday` is empty, or the day of month of the day appears in
  `bymonthday`.

A rule whose `byday` and `bymonthday` are both empty has no candidate in any
period. A `bymonthday` value larger than the length of the month a period falls
in simply matches no day, so a short month contributes nothing rather than
clamping onto its last day.

The selection inside one period reads `setpos` against that period's own
candidate set, never against the whole expansion:

- A position p greater than zero selects the candidate at one based index p,
  and selects nothing when p is larger than the size of the set.
- A position p less than zero selects the candidate at zero based index
  size plus p, so -1 is the last candidate of the period and -2 the one before
  it, and selects nothing when size plus p is below zero.

The selected days of the whole expansion are the union of every period's
selection, in ascending date order. `recurrence_primer.md` works three
selections through on invented figures.

## Stage 4, exceptions and the cap

`exception_dates.csv` carries one row per exception with a path spelling, a
date and a kind of `exclude` or `add`. The spelling is resolved through stage
1. A row whose spelling resolves to nothing applies to no path. A row that
resolves to an identifier no register row carries applies to no path either.
Two rows that resolve to the same path, the same date and the same kind are one
exception.

For one path, the merged sequence is built in this order:

1. Start from the selected days of stage 3.
2. Remove every date the path carries an `exclude` for, whether or not stage 3
   selected it.
3. Add every date the path carries an `add` for that the path does not also
   carry an `exclude` for on the same date. An addition that collides with an
   exclusion on the same date is dropped and counted as a dropped addition. An
   addition already present changes nothing.
4. Sort ascending.

The cap is applied after step 4 and never before it. When the rule's `limit` is
greater than zero, the merged sequence keeps its first `limit` dates and drops
the rest. The dates are counted from the start of the merged sequence, which
begins at the rule anchor rather than at the path's validity window, so a path
whose window opens long after its anchor has to be expanded from the anchor for
the cap to land in the right place. A `limit` of zero caps nothing.

Only after the cap is the sequence clipped to the path's validity window, which
is `valid_from` to `valid_to` inclusive at both ends. The result is the path's
running day set entering stage 5.

## Stage 5, variant supersession

A path whose `variant_of` column is non empty names a base path. The spelling
is resolved through stage 1. The named path is the base when it resolves to a
registered path that is not the path itself; in every other case the path has no
base and is a chain root.

Following bases from a path either ends at a path with no base or arrives back
at a path already on the chain. In the second case the paths from the one it
arrived back at onward form a cycle: every path on that cycle is rejected, runs
on no date, and is reported with the reason `variant_cycle`. A path that leads
into a cycle without being on it is not rejected.

The chain root of a path is the path its base chain ends at, and its chain depth
is the number of bases between it and that root. The walk up the chain stops at
a rejected path, so a path whose base chain reaches one has that rejected path
as its chain root.

Every base and variant pair is one edge. Edges are taken in order of the chain
depth of the base ascending, then the base identifier ascending, then the
variant identifier ascending. For each edge the shared dates are the dates that
are in both running day sets at that moment. The winner of the edge keeps them
and the loser loses them. The winner is decided in this order:

1. The higher `priority`.
2. The later `issue_stamp`.
3. The smaller canonical identifier.

Edges are taken one at a time and each one reads the day sets the edges before
it left behind, so a chain of three paths resolves from the root outward.
`overlay_primer.md` works one chain and one cycle through.

## Stage 6, timepoints

`zone_transitions.csv` gives, per zone, the instants at which the zone's offset
from UTC changes, with the offset in seconds before and after each one. Rows of
a zone are read in ascending instant order. The zone's offset before the first
transition is the `offset_before_sec` of that first row. The offset in force at
an instant t is the `offset_after_sec` of the last transition at or before t, or
the offset before the first transition when t is earlier than all of them.

A path's departure for one running day is the local wall clock reading of that
day at the path's `depart_local`. The instant it names is found like this. Take
the zone's distinct offsets, which are the offset before the first transition
together with the `offset_after_sec` of every transition. For each offset o,
the instant `wall minus o` is a candidate when the offset in force at that
instant is o itself. Then:

- Exactly one candidate: that instant is the departure.
- Two or more candidates: the local reading is a fold and the departure is the
  latest of the candidates.
- No candidate: the local reading sits in a gap. The gap belongs to a
  transition whose offset grows and whose local interval, from
  `at_utc plus offset_before_sec` up to but outside
  `at_utc plus offset_after_sec`, contains the reading; where more than one
  would match, the earliest such transition by instant is taken. The departure
  is `wall minus offset_before_sec` of that transition, which moves the reading
  forward by the length of the gap. The length of the gap in minutes is counted
  as shifted minutes.

`zone_primer.md` works a gap and a fold through on invented figures.

The path's route in `section_route.psv` gives the sections it runs over, each
with an offset in minutes from the departure. The entry instant of a section is
the departure instant plus that offset in minutes. A route whose offsets carry
the last section past local midnight changes nothing about the day: the service
date of a movement is the running day its departure was taken from, and no
entry is re-dated.

One movement is one path on one running day. A path's movements are taken in
ascending date order.

## Stage 7, headway admission

`headway_policy.json` gives the minimum headway in minutes per section class,
the deferral step in minutes and the maximum number of deferrals. The minimum
headway of a section is the one for its class in `section_register.csv`, after
any `APPROVED-HEADWAY` message from stage 2 has replaced it.

Every movement is walked once, in this order:

1. The rank weight of the movement's operator, descending.
2. The `priority` of the movement's path, descending.
3. The canonical path identifier, ascending.
4. The service date, ascending.

For one movement the deferral counts 0, 1 and up to the maximum are tried in
ascending order. At count k every entry instant of the movement is the stage 6
entry instant plus k times the deferral step in minutes. The count clears when,
for every section of the route, the absolute difference between that entry
instant and every entry instant already admitted on the same section is at
least the minimum headway of that section. A difference exactly equal to the
minimum headway clears; only a difference below it conflicts.

The first count that clears is taken, its entry instants join the admitted set
of their sections, and the movement is admitted with a deferral of k times the
step in minutes. When no count clears, the movement is withheld with the reason
`headway` and none of its entry instants joins the admitted set.

`headway_primer.md` works the ladder through on invented figures.

## Stage 8, the compiled timetable

Per path the compile reports the admitted movement count, the count of admitted
movements that took a deferral above zero, the withheld movement count, the sum
of the deferral minutes of its admitted movements, and its path minutes, which
are the admitted movement count multiplied by the route span. The route span is
the largest section offset of the route in minutes.

## Stage 9, canonical calendars

The admitted service dates of one path are re-encoded as a bit calendar:

- The base day is the earliest admitted date. A path with no admitted date has
  a base day of its `valid_from`, a bit length of zero and an empty hex string.
- The bit length is the latest admitted date minus the base day plus one.
- Bit i, counted from zero, is set when the base day plus i days is an admitted
  date.
- The bits are packed least significant bit first inside each byte, so bit 8j
  is the value 1 bit of byte j and bit 8j plus 7 is the value 128 bit.
- The byte string is written as lower case hexadecimal with two characters per
  byte. The last byte always carries the highest set bit, so no trailing zero
  byte is ever written.

## Stage 10, the digest and the rollups

The paths are taken in ascending canonical identifier order, counted from
position 1. The value of a path is its admitted movement count multiplied by
one thousand plus its deferral minute total. The term of a path is its position
multiplied by its value, taken modulo 2147483647. The digest is the sum of
every term, taken modulo 2147483647.

The rollups by operator, by section and by path, the flag list, the data
quality document, the prose report and the status line are all defined in
`report_schema.md`.
