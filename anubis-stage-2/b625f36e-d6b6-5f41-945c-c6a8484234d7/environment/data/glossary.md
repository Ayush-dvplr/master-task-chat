# Glossary

**admitted revision** A delivered row that passed validation and was the first
row read carrying its delivery identity.

**base revision** The highest ranked admitted revision of an event whose class
is not `RESTATEMENT`.

**canonical revision** The admitted revision of an event that the class rank,
the revision number and the batch sequence select.

**canonical site** The site an event's merge chain reaches at that event's
effective instant.

**delivery identity** The triple of `event_key`, `revision_no` and
`revision_class`.

**effective instant** The `occurred_at` of an event's canonical revision.

**event** The logical unit an `event_key` names. One event carries one or more
delivered revisions and receives exactly one outcome.

**in scope batch** A batch whose manifest row carries the status `ACTIVE`.

**settlement day** The half open twenty four hour window opening at `06:00:00Z`
that contains an event's effective instant.

**source site** The registered site an event's normalized site reference denotes
before any merge hop is taken.

**zone cell** A settlement day paired with the zone of the canonical site at the
effective instant.
