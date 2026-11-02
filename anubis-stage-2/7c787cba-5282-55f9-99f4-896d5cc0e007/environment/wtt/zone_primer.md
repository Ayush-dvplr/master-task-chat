# Zone primer

Two worked resolutions on an invented zone, so the rules of stage 6 can be
checked against arithmetic.

Take a zone whose transition table holds two rows:

| at_utc | offset_before_sec | offset_after_sec |
|---|---|---|
| 2030-03-31T01:00:00Z | 0 | 3600 |
| 2030-10-27T01:00:00Z | 3600 | 0 |

The offset before the first transition is 0. The distinct offsets of the zone
are 0 and 3600.

## A gap

A path departs at 01:30 local on 2030-03-31. The wall reading is
2030-03-31T01:30 with no offset attached.

Try offset 0: the instant would be 2030-03-31T01:30:00Z, and the offset in
force at that instant is 3600, not 0, so this is no candidate. Try offset 3600:
the instant would be 2030-03-31T00:30:00Z, and the offset in force there is 0,
not 3600, so this is no candidate either. There is no candidate, so the reading
sits in a gap.

The gap belongs to the first transition, whose offset grows from 0 to 3600 and
whose local interval runs from 2030-03-31T01:00 to 2030-03-31T02:00. The
reading 01:30 is inside it. The departure is the wall reading minus the offset
before, so 2030-03-31T01:30:00Z, and the gap is 3600 seconds, which is 60
shifted minutes. In local terms the departure has moved forward from 01:30 to
02:30.

## A fold

A path departs at 01:30 local on 2030-10-27.

Try offset 0: the instant would be 2030-10-27T01:30:00Z, and the offset in
force there is 0, so this is a candidate. Try offset 3600: the instant would be
2030-10-27T00:30:00Z, and the offset in force there is 3600, so this is a
candidate too. Two candidates, so the reading is a fold.

The departure is the latest candidate, 2030-10-27T01:30:00Z, which is the local
reading under the offset that applies after the transition. The earlier
candidate, 2030-10-27T00:30:00Z, is not the departure.

## An ordinary reading and the sections

A path departs at 09:00 local on 2030-06-01. Only offset 3600 gives a candidate,
so the departure is 2030-06-01T08:00:00Z. A route whose second section carries
an offset of 240 minutes puts that entry at 2030-06-01T12:00:00Z. A route whose
last section carries an offset of 960 minutes puts that entry at
2030-06-02T00:00:00Z, which is 2030-06-02T01:00 local, a later local date. The
movement still belongs to the service date 2030-06-01.
