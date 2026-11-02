# Rulebook: admission

Filed under A in the platform reference set. Each rule below stands on its own.
Nothing here says which rule is consulted first, and nothing here says what
happens when two rules could both speak to the same record. Those questions
belong to the working set as a whole.

## A1 Window boundary

The ingest window is an interval that opens at the instant named as the window
open and closes at the instant named as the window close. A landing record
belongs to the window when its emission instant is at or after the window open
and strictly before the window close. A record emitted exactly at the window
close belongs to the next window, not this one.

A record that does not belong to the window takes no part in the settlement. It
is not curated, it is not withdrawn, it is not quarantined, and it never reaches
the ledger. It is counted once in the quality register so the operator can see
how much traffic arrived outside the boundary.

## A2 Suspended feeds

A feed carries a suspension flag. While a feed is suspended its records take no
part in the settlement at all. They are not curated, not withdrawn, not
quarantined, and they never reach the ledger. Like out of window traffic they
are counted once in the quality register.

Suspension is a property of the feed for the whole window. There is no partial
suspension and no suspension interval.

## A3 Provisional domains

A domain carries a provisional flag. A provisional domain has not completed
platform onboarding. Every record that lands on a feed belonging to a
provisional domain is withdrawn from the curated output and booked with the
reason `withdrawn_provisional_domain`.

Provisional domains still hold feeds, still appear in the channel membership
lists, and still consume nothing. They simply never contribute curated records
or settled charge.

## A4 Exceptions

An exception is a filed objection about a single landing record. An exception
carries a status. A dismissed exception has no effect on anything: the record is
settled exactly as though the exception had never been filed. An upheld
exception carries an agreed unit rate in micros, and that agreed rate replaces
the unit rate the record would otherwise have carried.

An upheld exception speaks only to the unit rate. It says nothing about whether
the record is curated. A record that is withdrawn for any reason, or that sits
on a quarantined feed, stays withdrawn or quarantined whether or not an
exception was upheld on it. An upheld exception never returns a record to the
curated set, and it never moves a record between domains.

The identifiers of the records that actually carried an upheld agreed rate into
the settled output are reported in the audit artifact. A record with an upheld
exception that ended up outside the curated set is not among them.

## A5 Records with no rate to apply

Charging material is filed in editions with effective intervals. A window can
contain a stretch of time no edition covers. A landing record emitted inside
such a stretch cannot be charged, so it is withdrawn from the curated output and
booked with the reason `withdrawn_no_governing_card`. It is also counted in the
quality register.
