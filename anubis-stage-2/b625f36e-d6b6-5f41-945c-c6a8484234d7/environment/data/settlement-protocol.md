# Marrowgate settlement protocol

This document governs the materialization of the interval ledger for the
Marrowgate district energy network. It is the authority on membership,
disposition, canonical selection, quantity arithmetic and outcome. Where any
other document in this directory appears to say something different about these
subjects, this document governs.

## 1. Batch membership

`batch_manifest.csv` decides which batches belong to a materialization. A batch
is in scope when its manifest row carries `status` exactly `ACTIVE`. A batch
whose row carries any other status is out of scope and none of its rows are read,
whatever the file contains and whether or not the file is present.

A file present in this directory that has no manifest row at all is not part of
the network's registered history. It is not read and it is not an exception.

Membership is decided row by row and never file by file. A batch that was
withdrawn and later reinstated carries more than one manifest row for the one
`filename`, and each row is weighed on its own `status`. A withdrawn row
neither cancels nor confirms an `ACTIVE` row for the same `filename`, whether
the withdrawn row is registered at a lower `batch_seq` or at a higher one, and
a `filename` that carries an `ACTIVE` row is therefore read exactly once
however many withdrawn rows accompany it. Each manifest row is reported under
its own `batch_id`, so one such `filename` is named by an ingested `batch_id`
and by a withdrawn `batch_id` at the same time.

A manifest row that is `ACTIVE` and whose `filename` is absent from this
directory is an unresolvable condition. It is reported under the code
`MISSING_BATCH` and it contributes no rows.

Rows are read in ascending `batch_seq`, and within a batch in file order. The
first line of every delimited batch is a header and is not a row. The
fixed-width batches carry no header and every line is a row.

`expected_rows` states the row count the producing system believed it had
written. A batch whose observed row count differs from `expected_rows` is still
ingested in full, and the disagreement is recorded as a row exception.

## 2. Disposition of a delivered row

Every row read from an in-scope batch receives exactly one disposition:
`ADMITTED`, `DUPLICATE`, `CONFLICT` or `REJECTED`. No row receives two and no
row receives none.

A row is `REJECTED` when it fails validation. Validation applies the following
checks in this order and stops at the first failure, so a row that fails two
checks carries the code of the earlier one:

```
1  revision_class is one of the five defined classes      -> MALFORMED_ROW
2  revision_no is a positive decimal integer              -> MALFORMED_ROW
   written in ASCII digits
3  occurred_at parses as an instant in one of the two      -> BAD_TIMESTAMP
   written forms section 8 defines
4  occurred_at falls inside the settlement calendar       -> OUT_OF_CALENDAR
5  quantity, when present, is a numeral of the grammar   -> BAD_QUANTITY
   record-layouts.md gives for the batch's unit
6  the normalized site reference is a registered site     -> UNKNOWN_SITE
7  meter_id holds a registration covering that instant  -> UNKNOWN_METER
8  that registration names the site the normalized
   reference denotes                           -> METER_SITE_MISMATCH
```

An absent quantity is not a validation failure. Check 5 applies only to a
quantity that is present and non-empty.

Check 2 admits only the ten ASCII digits `0` to `9`. A digit from any other
script is not a decimal digit here, even where a programming language would
read it as one, and a sign, a point or a value of zero fails the check.
Leading zeros are permitted and carry no meaning, so `03` and `3` are the same
revision number wherever a revision number is compared, named or written.

Check 8 compares the `site_id` of the covering meter registration with the
registered site the normalized reference denotes, which is the site the
reference names before any merge is applied. A row whose meter belongs to a
site that merges into the site the row names still fails check 8, because a
row is validated as delivered and the merge chain is walked only once an event
has a canonical revision and therefore an effective instant. A row whose
meter carries no registration covering the instant fails check 7 and never
reaches check 8.

The delivery identity of a row is `event_key`, `revision_no`,
`revision_class` and the batch family the row arrived in, all four together.
Its payload is the normalized site reference, the meter id, `occurred_at`, the
quantity field and `supersedes_revision`, and the payload is compared by value
rather than by characters: `occurred_at` by the UTC instant it names, the
quantity by the exact decimal value its numeral denotes in the batch's unit,
taken before any pulse multiplier is applied, and
`supersedes_revision` by the revision number it names. Two quantities written
differently that denote the same number are the same value. Two quantities
that denote different numbers are different values even where both carry to
the same whole watt-hour. Among rows sharing one
delivery identity, the first one read is `ADMITTED`. A later row with the same
delivery identity is `DUPLICATE` when its payload equals the admitted payload
and `CONFLICT` when it does not. A `CONFLICT` row is quarantined and never
changes the admitted row.

Two rows that share an `event_key` and differ in `revision_no` do not share a
delivery identity. They are the ordinary revision history of one event.

A producing system that loses track of what it has already sent redelivers a
batch under a fresh `batch_id` and a fresh `filename`. The history is append
only, so such a redelivery is in scope on its `status` like any other batch and
every line of it is read. Its repeated rows meet the delivery identities their
originals already hold and fall out as duplicates, and any row in it carrying a
delivery identity no earlier batch held is admitted and settles like any other
revision.

Two rows that agree on `event_key`, `revision_no` and `revision_class` and
arrive in different batch families do not share a delivery identity either.
Both are admitted, and one event therefore carries two admitted revisions of the
same class and number. Section 3 decides which of them governs.

## 3. The canonical revision

The class rank is `ORIGINAL` 0, `AMENDMENT` 1, `CORRECTION` 2, `REVERSAL` 3,
`RESTATEMENT` 4.

Among the admitted revisions of one event the canonical revision is the one with
the highest class rank. Among those, the one with the highest `revision_no`.
Among those, the one whose batch carries the lowest `batch_seq`. Class rank
governs before `revision_no`, so a revision of a higher ranked class is
canonical even when another admitted revision carries a larger `revision_no`,
and the lowest `batch_seq` governs the pair a cross family redelivery creates,
so the earlier registered batch supplies the reading and the later one does
not.

The effective instant of an event is the `occurred_at` of its canonical
revision. Every effective dated lookup in this directory is made at the
effective instant and never at `ingested_at`.

The base revision of an event is the highest ranked admitted revision whose
class is not `RESTATEMENT`, resolved by the same three keys.

## 4. Quantity

All quantity arithmetic is carried in whole watt-hours as integers.

The `quantity` field of a batch is read in that batch's unit, which
`record-layouts.md` states for each family. A quantity expressed in kilowatt
hours is converted to watt-hours by multiplying the decimal value by one
thousand and quantizing the product once to an integer under round half to even.
No later stage re-quantizes a value.

A delivered count is not a reading on its own. The registration that covers a
row's own `occurred_at` for that row's `meter_id` carries a
`pulse_multiplier`, and the quantity the row delivers is the value of its
numeral multiplied by that multiplier. The product is carried to watt-hours by
the single quantization above, so the multiplier is applied to the exact
decimal value before that quantization and never to the integer the
quantization produced: a reading whose watt-hour value lands on a half is
multiplied first and quantized once. Every row that reaches this stage has
cleared check 7 and therefore has exactly one covering registration, by the
rule `entity-model.md` gives for rows that cover one instant together.

`delta_flag` is written by the producing system as a hint. It is advisory and it
is not authoritative. The revision class decides whether a quantity is an
absolute reading or a signed delta.

The quantity of a revision whose class is `RESTATEMENT` is a signed delta in
that batch's unit. The quantity of a revision of any other class is an absolute
reading.

`max_interval_limits.csv` gives the ceiling for a site at an instant. A
canonical site that carries no row covering the effective instant has no
ceiling at all: a ceiling is never assumed, a missing row is never read as a
ceiling of zero, and the event is the unresolvable condition section 5 decides.

Where a ceiling exists, the quantity of the base revision is clamped into the
closed range from zero to that ceiling. The signed deltas of every admitted
`RESTATEMENT` revision of the event are then added to the clamped base, in
ascending `revision_no` and, on a tie, ascending `batch_seq`. The sum is
clamped into the same range a second time. Clamping is applied to a single
event and never to a total.

A `RESTATEMENT` revision whose `supersedes_revision` names the `revision_no`
of an admitted `RESTATEMENT` revision of the same event displaces it. Every
admitted `RESTATEMENT` revision carrying a displaced `revision_no` is withheld
from the stack and its delta is never added to the clamped base. Because the
delivery identity carries the batch family, one `revision_no` can be held by
two admitted `RESTATEMENT` revisions of one event, and naming that number
displaces both of them.

The displacing revision applies its own delta in the ordinary way, and it
applies that delta even when a third revision has displaced it in turn. The
relation is read once over the admitted stack as delivered and is never
followed to a fixed point.

A displaced revision remains an admitted revision. It keeps its place in the
revision index, it counts as a delivered row, and it displaces whatever its
own `supersedes_revision` names. A `RESTATEMENT` naming a `revision_no` that
only a revision of another class carries displaces nothing, and a
`RESTATEMENT` naming a `revision_no` no admitted revision of the event carries
is the orphan condition section 5 decides.

## 4a. Tariff band

`tariff_classes.csv` carries the bands of each tariff class with the watt-hour
threshold at which each band opens. The band of an event is the band of its
tariff class whose threshold is the greatest threshold at or below the event's
final quantity. An event whose final quantity falls below every threshold of its
class carries the literal `UNBANDED`, and so does every event whose final
quantity is zero.

The tariff class is the one the effective dated row selects for the canonical
site at the effective instant, so the band is a consequence of the canonical
revision, the merge chain, the effective dated join, the unit conversion and
both clamps together.

## 5. Outcome

Every event receives exactly one outcome. The following tests are applied in
order and the first one that holds decides:

```
1  the canonical class is CORRECTION or RESTATEMENT and its
   supersedes_revision names a revision_no that no admitted
   revision of the event carries              -> UNRESOLVABLE ORPHAN_SUPERSEDE
2  the event has no admitted non RESTATEMENT
   revision                                   -> UNRESOLVABLE MISSING_BASE
3  no row of max_interval_limits.csv covers the canonical
   site at the effective instant              -> UNRESOLVABLE MISSING_CEILING
4  the base revision carries no quantity      -> DEFERRED
5  the canonical class is REVERSAL and the event
   carries an odd number of admitted REVERSAL
   revisions                                  -> VOIDED
6  the canonical site is SUSPENDED at the
   effective instant                           -> EXCLUDED
7  otherwise                                   -> SETTLED
```

Test 3 is weighed before test 4, so an event whose canonical site has no
ceiling at its effective instant is unresolvable whether or not its base
revision carries a reading, and an event that would otherwise be voided or
excluded is unresolvable for the same reason.

A `VOIDED` event carries a quantity of zero and keeps its place in the ledger
and in every count. An `EXCLUDED` event carries its computed quantity and
keeps its place in the ledger and in every count, and it contributes nothing
to any settled total. A `DEFERRED` or `UNRESOLVABLE` event carries a quantity
of zero.

A reversal reverses the event, and a second reversal reverses the first, so
reversals compose. An event carrying an even number of admitted `REVERSAL`
revisions stands as though none had been delivered and settles on its base,
and an event carrying an odd number is voided.

Only a `SETTLED` event contributes to a settled total or to a settled event
count.

## 6. Zone cells and the published baseline

A zone cell is a settlement day paired with the zone of the canonical site at
the effective instant. `published_baseline.json` carries the settled watt-hours
and the settled event count that a prior publication stated for each zone cell.
The baseline is read and never written.

The restatement of a zone cell is the difference between the value this run
computes and the value the baseline states. A zone cell whose watt-hour
difference and whose event count difference are both zero carries no adjustment
row. Every other zone cell carries exactly one, and the cells weighed are the
cells the baseline states together with the cells this run computes. A cell the
baseline states and this run computes nothing for is restated to zero rather
than left out.

## 7. Configuration

Three layers are read in this order: `settlement_defaults.ini`, then
`network_policy.conf`, then `site_overrides.properties`. For every key outside
the `rounding.` namespace the value from the last layer that sets it governs.
For every key inside the `rounding.` namespace the numerically smallest value
set by any layer governs, whichever layer set it.

`rounding.quantity_dp` is the number of decimal places the per event kilowatt
hour presentation carries. `rounding.total_dp` is the number of decimal places
the per partition kilowatt hour presentation carries. Both presentations are
derived from the integer watt-hour value by dividing by one thousand and
quantizing once under round half to even.

`settlement.exclusion_policy` decides whether an `EXCLUDED` event occupies a row
in its settlement partition. The value `include` places the row and the value
`omit` withholds it. The event remains in the ledger either way.

## 8. Written instants

An instant is delivered in one of two written forms. The first is twenty
characters ending in `Z` and states the instant in UTC directly. The second is
twenty five characters ending in a fixed offset written as a sign, two digits,
a colon and two digits, and states a local reading of the same instant. The
offset is the amount by which that producing system's clock runs ahead of UTC,
so the UTC instant is the written instant with the offset taken off it.

A producing system writes every instant in one form for the whole of a batch.
Which form a batch uses is a property of the producing system, and the form is
visible in the field itself.

Both forms name the same instant and neither is preferred. Every rule in this
document, including calendar membership, the settlement day, the effective
instant and every effective dated read, operates on the UTC instant and never
on the characters as delivered. An instant in neither form fails check 3.

A written instant also has to name a moment that exists. Its date is a date of
the Gregorian calendar, so the day of the month never exceeds the length of
that month and February carries a twenty ninth day only in a leap year, and its
hour runs from `00` to `23`. A field that has the shape of either form and
names a date or a time that does not exist is not an instant at all and fails
check 3. It never reaches check 4.
