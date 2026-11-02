# Gauntlet Circuit Slate Contract

This document is the single source of truth for slate adjudication. Where any
feed, console reply, runbook or habit disagrees with this document, this
document governs.

## 1. Scope and admission

A season is a sequence of stages. The slate under adjudication is named by
`slate_id` in `slate_window.ini` together with the season and the open stage.
The legality cutoff and the precedence cutover are given in the same file as
UTC instants.

A record from any feed is admitted at an instant when its `effective_at` is at
or before that instant and its `recorded_at` is at or before the legality
cutoff. A record whose `recorded_at` falls after the legality cutoff is never
admitted, whatever its `effective_at` says. Where a feed carries no
`effective_at`, its `recorded_at` serves as both.

The slate holds every submission whose effective instant falls inside the
governing window of the open stage for the venue of play and whose recorded
instant is admitted. Carry history is accumulated over every submission of the
season, including the stages that have already closed.

## 2. Submissions

`entry_header_01.csv` through `entry_header_04.csv` carry one row per
submission. The fields, in order, are the submission id, the entrant handle,
the format, the venue of play, the local entry time, the venue of record and a
source tag. The venue of play governs every rule in this document that names a
venue. The local entry time is wall time at the venue of play.

`legacy_entries.tsv` carries submissions from the circuit management system
that predates the intake lanes. Its fields are the season, the submission id,
the handle, the format, the venue, a local entry time at that venue, a
recorded instant in UTC and a note. Only rows whose season equals the season under adjudication
belong to this season. A submission that appears in both the headers and the
legacy feed takes its instants from the headers.

`deck_lines_01.csv` through `deck_lines_06.csv` carry the entered lists. The
fields are the submission id, the printed card name, the set code and the
copies. A blank copies field counts as one copy. Lines for one submission may
sit in more than one file.

## 3. Local time and the competition day

`venue_clocks.ini` gives each venue a base offset in minutes from UTC and the
intake host that serves it. `venue_offset_shifts.csv` gives effective dated
offset changes per venue, each stating the UTC instant at which it takes effect
and the offset in force before and after it. A local wall time that occurs twice at a venue
resolves to the earlier UTC instant. A local wall time that does not occur at
all resolves to the UTC instant at which the shift begins.

The competition day at a venue begins at the local time given by
`competition_day_start_local` in `slate_window.ini`. A submission whose local
time falls before that hour belongs to the competition day that began on the
previous calendar date.

## 4. Stage windows

`stage_calendar.csv` carries one row per stage, venue and published revision,
with the window start, the window end and a published instant. The governing
revision for a stage and venue is the one with the latest published instant at
or before the legality cutoff. Windows are half open, so an instant equal to
the window start falls inside and an instant equal to the window end falls
outside. Where the governing windows of two stages both contain an instant,
the later stage holds it.

## 5. Recorded instants

The recorded instant of a submission comes only from the intake receipts.
`intake_journal.log` holds the current lane and `intake_journal.log.1` holds
the rotation that preceded it. A receipt line carries the lane timestamp in
the clock of the issuing host, the host, a receipt id, the submission id and
the lane. Lines indented from the left margin continue the receipt above them.
A continuation carrying `recorded_override` supplies the recorded instant for
that receipt directly in UTC.

`host_clock_offsets.csv` gives, per host and calendar date of the lane
timestamp, the signed offset in seconds by which that host ran away from UTC.
The corrected instant of a receipt is its lane timestamp less that offset.

Where a submission carries several receipts, the earliest admitted corrected
instant governs. A submission with no receipt, or whose every receipt lands
after the legality cutoff, sits outside the slate and contributes nothing to
any artifact or to carry history. Submissions carried only by the legacy feed
take the recorded instant stated there.

## 6. Entrants

`handle_changes.csv` carries one row per handle assignment with the handle,
the player id, an effective instant and a recorded instant. The entrant behind a
handle at a submission is the player named by the admitted assignment with the
latest effective instant at or before that submission's effective instant.
Handles are reassigned over time, so a handle names different players in
different intervals.

`identity_events.csv` carries one row per identity event with an event id, a
kind, a primary player, a secondary player, an effective instant and a
recorded instant. A `merge` event joins the two players named in the row. The
surviving id is the one whose `joined_at` in `player_registry.csv` is earlier,
and where the two joined on the same instant it is the lexicographically
smaller id. At the effective instant of an admitted merge the surviving
player's carry absorbs the absorbed player's carry, subject to the carry cap,
and the absorbed player's carry falls to zero. A `split` event attaches every
submission of the primary player effective at or after its effective instant
to the secondary player and transfers no carry. A `status` event carries no
routing effect.

A submission is counted as redirected when the player who holds it differs
from the player the handle assignment alone would name.

## 7. Cards

`printing_registry.csv` carries one row per printing with the printing id, the
canonical key, the set code, the printed name and a release date.

A set code is normalised by trimming surrounding space, raising it to upper
case, dropping a single trailing asterisk and stripping leading zeros from a
trailing run of digits. The same normalisation applies on both sides of a
join, so a deck line and a registry row match when their normalised set codes
are equal.

`card_renames.csv` carries one row per renaming with the canonical key, the
printed name the key takes from that instant, an effective instant and a
recorded instant. The name in force for a canonical key at an instant is the
printed name of the admitted renaming with the latest effective instant at or
before it, and the registry name where no renaming is admitted.

A deck line matches a printing when the normalised set codes are equal and the
printed name on the line equals either the registry name of that printing or
the name in force for its canonical key at the submission's effective instant.
Where several printings match, the one with the lowest printing id holds the
line. A deck line that matches no printing makes the submission unresolvable
with the reason `unknown_printing`.

`reprint_links.tsv` carries one row per consolidation with a link id, the
format, two canonical keys, an effective instant and a recorded instant. An
admitted link makes the two keys one key for that format from its effective
instant. The surviving key of a group is the one whose earliest printing was
released first, and where two were released on the same date it is the
lexicographically smaller key. Restriction lookups, copy counts and card
counts all use the surviving key. In this file an empty recorded instant means
the recording instant is unknown and the effective instant serves for both,
and the token `\N` means the link was withdrawn and never applies.

## 8. Restrictions

Three sources supply an allowed copy count and a point charge per format and
canonical key.

`global_restrictions_01.jsonl` through `global_restrictions_04.jsonl` carry
revisions. Each record holds a revision id, the format, the canonical key, an
optional `allowed_copies`, an optional `point_charge`, an optional
`supersedes`, a `retracted` flag, an effective instant and a recorded instant.
A retracted revision never applies. Among the admitted revisions for a format
and key, the governing revision is the one that no other admitted revision
supersedes, and where several qualify it is the one with the latest effective
instant, then the latest recorded instant, then the greatest revision id.
Where admitted revisions exist for a format and key but every one of them is
superseded by another admitted revision, that key is unresolvable for that
format with the reason `chain_cycle`.

`addendum_north.csv`, `addendum_south.csv` and `addendum_east.csv` carry one
row per region with the format, the canonical key, an `allowed_copies`, a
`point_charge_pts`, an effective instant and a recorded instant. The addendum
that applies to a submission is the one for the region that holds the venue of
play at the submission's effective instant according to `venue_roster.csv`,
whose rows carry a venue, a region, an effective instant and a recorded
instant. A blank field in an addendum row means that source supplies nothing
for that field.

`event_rider.tsv` carries one row per rider with the format, the canonical
key, an `allowed_copies`, a `point_charge_cpt`, an authorising judge and an
effective and recorded instant. A rider row applies only when the authorising
judge held rank three or above at the row's recorded instant according to
`authority_roster.csv`, whose rows carry a judge, a rank, an effective instant
and a recorded instant. The rank of a judge at an instant is the rank of the
admitted roster row with the latest effective instant at or before it, and
zero where none is admitted.

### 8.1 Units

`source_registry.ini` declares, per feed, the unit in which that feed states a
charge and the decimal mark it uses. Point charges reach the output in integer
centipoints. A charge stated in points is converted by multiplying by one
hundred and rounding half up at the integer. A charge stated in centipoints
is already in output units.

`printing_release_board.txt` is fixed width. `source_registry.ini` names the
column span of its charge field and the number of implied decimal places that
field carries.

### 8.2 Precedence

For a submission whose effective instant is at or after the precedence
cutover, both the allowed copy count and the point charge take the first value
supplied by the rider, then the global feed, then the addendum.

For a submission whose effective instant falls before the precedence cutover,
the allowed copy count takes the first value supplied by the rider, then the
addendum, then the global feed. The ordering that the point charge follows
before the cutover is fixed by the adjudication observations and by nothing
else in this document.

Where no source supplies an allowed copy count, the `default_copies` of the
resolved format rules applies. Where no source supplies a point charge, the
charge of the earliest released printing of that canonical key on the release
board applies.

### 8.3 Mirrored charges

A point charge may be stated as the token `mirror:` followed by a canonical
key, which means the resolved charge of that key in the same format. Mirrors
resolve through as many hops as the data carries. Where a mirror chain returns
to a key already on the chain, every key on that chain is unresolvable with
the reason `charge_cycle`.

## 9. Format rules

`format_rules.ini` carries a base section and one section per format, each
naming the section it inherits from in an `inherits` key, and per stage
sections that override a format for one stage. A setting resolves by walking
from the most specific section that applies, through the sections it inherits
from, taking the first value found. The settings are `default_copies`,
`copies_cap`, `points_budget_cpt` and `charge_ceiling_cpt`.

`format_exemptions.csv` carries a format, a stage, a canonical key, a kind and
a recorded instant. An exemption carries no effective instant: it is admitted
when its recorded instant is at or before the legality cutoff, and it then
applies to every submission of that format and stage. The kind
`singleton_copies` releases that key from the copies cap. The kind
`charge_ceiling` releases that key from the charge ceiling.

## 10. Evaluation of a list

The counted copies of a surviving canonical key are the copies of every deck
line in the governing list that resolved to that key, summed. The allowance of
a key is the lesser of its resolved allowed copy count and the `copies_cap` of
the resolved format rules, except that a key holding an admitted
`singleton_copies` exemption for that format and stage takes its resolved
allowed copy count alone. The `copy_breach_count` of a submission is the
number of distinct surviving keys whose counted copies exceed their allowance.

The `charge_ceiling_cpt` of the resolved format rules binds the charge of
every key that holds no admitted `charge_ceiling` exemption for that format
and stage. The stage of the computation at which the ceiling binds is fixed by
the adjudication observations and by nothing else in this document.

The `points_total` of a submission is the sum over its distinct surviving keys
of the charge admitted for that key multiplied by its counted copies, in
centipoints.

The `governing_source` of a submission is the source that supplied the charge
of the key whose contribution to `points_total` is largest, with ties going to
the lexicographically smallest key, reported as `rider`, `global`, `addendum`
or `base`, where `base` names the release board fallback.

## 11. Amendments

`amendments_01.jsonl` and `amendments_02.jsonl` carry amendment records with
an amendment id, the submission id, a version, a status, a `lines` value, an
effective instant and a recorded instant. Only records whose status is
`accepted` and which are admitted count. The governing list of a submission is
the list of the counting amendment with the highest version, and the list as
entered where none counts. A `lines` value of null, and an absent `lines` key,
keep the list that was in force before that amendment. A `lines` value of the
empty list clears the list entirely. Amendment lines carry the keys
`printed_name`, `set_code` and `copies`.

## 12. Entry events

`entry_events_01.jsonl` and `entry_events_02.jsonl` carry an event id, a kind,
the submission id, a successor id, an effective instant and a recorded
instant. A submission under an admitted `withdraw` leaves the slate unless an
admitted `restore` with a later effective instant applies to it. A submission
under an admitted `supersede` leaves the slate in favour of its successor.

Where one event id appears more than once with an identical payload, the
repeats are a single event. Where one event id appears more than once with
payloads that differ, every record carrying that id is rejected and counts
towards the rejected event total.

## 13. Standing entries

`standing_entries.csv` carries a standing id, the entrant handle, the format,
the venue, a weekday, a local time, a start date, an until date and a recorded
instant. A row counts only when its recorded instant is at or before the
legality cutoff, and the entrant behind its handle is the player that the
admitted handle assignment of section six names at the occurrence instant. An
identity event moves no occurrence: a merge or a split leaves the entry with
the player the handle named. Each row states a weekly commitment at that venue
and local time on that weekday, from the start date through the until date
inclusive.

`entry_exceptions.csv` carries an exception id, a kind, a standing id, a
venue, a date and a recorded instant. The kind `skip` suppresses the
occurrence of that standing id on that date. The kind `closure` suppresses
every occurrence at that venue on that date.

An occurrence materialises as a slate entry when its instant falls inside the
governing window of the open stage for that venue, no exception suppresses it,
and the player holds no submission of that format on that competition day at
that venue. A materialised entry takes the id `STD-` followed by the player
id, a hyphen and the occurrence date as eight digits.

The governing list of a materialised entry is the list of that player's most
recent strictly earlier submission of the season whose verdict was `seated` or
`amended`. Where the player has no such submission, the materialised entry is
unresolvable with the reason `no_prior_list`.

## 14. Carry

Every submission of the season is processed in order of effective instant,
then recorded instant, then submission id. Each player carries an integer that
begins the season at zero.

`slate_window.ini` states the penalty weight of each verdict, the carry cap
and the carry relief. The carry a submission is judged against is the carry of
its player immediately before it. After the verdict, the player's carry
becomes the lesser of the carry cap and the sum of the carry before and the
penalty weight of the verdict.

At the close of each stage, as stated in `slate_window.ini`, a player who held
at least one submission effective within that stage and whose submissions in
that stage carried a total penalty weight of zero has the carry reduced by the
carry relief, with zero as the floor. Admitted merges take effect at their
effective instant in the same ordering. Where a stage close, a merge and a
submission fall on the same instant, the stage close applies first, then the
merge, then the submission.

The tier of a carry value is given by the bands in `slate_window.ini` and is
one of `clear`, `caution`, `probation` or `barred`.

## 15. Verdicts

The verdict of a submission is the first of the following that holds.

1. A submission holding an unresolvable card takes `unresolved`, with the
   reason `charge_cycle`, else `chain_cycle`, else `unknown_printing`.
2. A materialised entry with no prior list takes `unresolved` with the reason
   `no_prior_list`.
3. A submission whose player is at tier `barred` on the carry before it takes
   `barred` with the reason `tier_bar`.
4. A submission holding a key whose allowance is zero takes `barred` with the
   reason `card_barred`.
5. A submission whose `copy_breach_count` is above zero takes `flagged` with
   the reason `copy_breach`.
6. A submission whose `points_total` exceeds the `points_budget_cpt` of the
   resolved format rules takes `flagged` with the reason `points_over`.
7. A submission whose governing list came from an amendment takes `amended`
   with a null reason.
8. Every other submission takes `seated` with a null reason.

## 16. Adjudication observations

`judge_log_a.log` and `judge_log_b.log` carry adjudications already settled
for the closed stages of this season. An observation line states a timestamp,
the adjudicating judge, the stage, the submission, the governing source, the
points in centipoints, the verdict and the carry after. Lines carrying a
`lane` token record review activity and settle nothing.

Where two observations of one submission disagree, the one whose judge held
the higher rank at the timestamp of that observation governs, and where the
ranks are equal the later timestamp governs. Neither file outranks the other.

## 17. Reinstatement

`reinstatement_grants.csv` carries a grant id, the player id, an effective
instant, a recorded instant and the granting judge. A grant is admitted when its recorded
instant is at or before the legality cutoff and the granting judge held rank
four or above at that instant. A player holding an admitted grant whose
submission took `barred` with the reason `tier_bar` is reinstated after the
bar is recorded.

## 18. Published tallies

`carry_cap_hits` counts the slate entries whose carry after the verdict equals
the carry cap.

`distinct_canonical_cards` counts the distinct surviving keys that the
governing lists of the slate resolve to, over every entry the slate holds.

## 19. Counterfactual scenarios

`scenario_brief.ini` names three scenarios, each with a `basis` token and one
parameter. A scenario re-runs the adjudication of this document and publishes
the same open slate the report covers.

A `cutoff` basis replaces the legality cutoff with the instant the brief names,
so every feed is admitted against that instant for the whole season.

A `source` basis withdraws the named restriction source for the whole season,
so neither an allowed copy count nor a point charge is taken from it anywhere.

A `format` basis evaluates the entries of the open stage as the format the
brief names. The stages that have already closed keep the formats their
submissions were entered in, so each open stage entry is judged against the
carry the published report gives it.
