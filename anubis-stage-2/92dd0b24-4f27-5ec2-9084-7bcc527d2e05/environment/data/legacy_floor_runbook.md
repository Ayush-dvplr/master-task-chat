# Floor Runbook, Seasons GC27 to GC29

This runbook records how the floor team worked the slate in the seasons before
the published contract existed. It is retained for historical interest only
and it is not authoritative. Every habit below yields to
`slate_contract.md` and to `api_contract.md` where the two differ.

## Intake

The floor team read the venue from the rightmost venue column of the intake
header, because the older lanes wrote the hall of record there and the two
columns almost always agreed.

Lane timestamps were taken as written. The clock telemetry feed arrived late
in GC28 and the team did not backfill it.

When a submission carried more than one receipt the team used the last receipt
in the file, since the file was believed to be append ordered.

The rotation file was read after the current lane file on the assumption that
rotation moves newer lines aside.

## Entrants

A handle was treated as one entrant for a whole season. Handle reassignment
was handled by hand at the desk and was rarely recorded.

On a merge the team kept the identifier that appeared in the left column of
the identity feed and let each carry stand where it was.

## Lists

Copies were counted per printing, so two printings of one card were tracked
apart. Set codes were compared as written, because the capture tool was
expected to emit the registry spelling.

Charges were taken from the newest restriction record by recorded order, and
halves were rounded down at the centipoint.

The regional addendum of the entrant's home venue was applied, since most
entrants played near home.

## Carry

Carry was reset to zero at the opening of every stage, which kept the ladder
readable on the wall sheet.

Standing commitments were run from the start date up to but excluding the
until date.

## Console

The floor team read the caps from the arbiter advice endpoint at the start of
the day and wrote them on the wall sheet.

Writes were retried by sending the same body again until a 200 came back.

Page walking stopped at the first page that came back empty.

Every operation was sent over the api, because the console was reserved for
the head judge.

Listings were trusted immediately after a write.
