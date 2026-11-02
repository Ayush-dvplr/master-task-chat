# SDA lease appendix

Worked examples of the lease calculus of the replay specification, section 8
and section 9. Where this appendix appears to differ from that document, that
document wins.

## Interval convention

A lease covers the ticks from its grant tick up to but not including its expiry
tick. The grant end is closed and the expiry end is open. This is the only
interval in the replay written that way, and it is the reason a lease granted
at tick 12 and expiring at tick 12 covers no ticks at all rather than one.

The admission window recorded against a stream is written the other way round.
It is closed at both ends, so a stream admitted from tick 4 to tick 9 is
admitted on ticks 4, 5, 6, 7, 8 and 9. Admission bounds nothing in the
accounting and is carried into the registry unchanged.

## Worked example one, a lease with no revocation

    grant tick        30
    recorded expiry   35
    revocations       none

The effective expiry is 35 and the span is 5.

## Worked example two, a revocation that takes effect

The holding stream is `bulk`, which is rank 1. The revoking stream is
`interactive`, which is rank 3.

    grant tick        30
    recorded expiry   35
    revocation        tick 32, issued by an interactive stream

Rank 3 is strictly greater than rank 1, so the revocation takes effect. The
effective expiry becomes 32 and the span becomes 2. The window records the
revoking stream in its preempted by column, and the event is recorded with the
disposition `preempted`.

## Worked example three, a revocation that does not take effect

The holding stream is `realtime`, which is rank 4. The revoking stream is
`standard`, which is rank 2.

    grant tick        30
    recorded expiry   35
    revocation        tick 32, issued by a standard stream

Rank 2 is not strictly greater than rank 4, so the revocation is ignored. The
effective expiry stays at 35 and the span stays at 5. The preempted by column
carries the empty string. The event is recorded with the disposition
`inverted`, and it also appears in the inversion report.

## Worked example four, equal ranks

Two `interactive` streams, both rank 3.

    revocation        tick 32, issued by an interactive stream

Rank 3 is not strictly greater than rank 3. The revocation is ignored and this
is a priority inversion, exactly as in example three. Equality does not
preempt.

## Worked example five, two revocations on one window

    grant tick        30
    recorded expiry   40
    revocation A      tick 36, issued by a rank 4 stream
    revocation B      tick 33, issued by a rank 1 stream, holder is rank 2

Revocation A takes effect and moves the expiry to 36. Revocation B is ignored
and is a priority inversion. The effective expiry is 36, the span is 6, the
preempted by column carries the stream that issued A, and both events appear in
the lease conflict artifact, one as `preempted` and one as `inverted`.

Only a revocation that takes effect can move the expiry, and it moves it only
when its tick falls before the expiry the window would otherwise have. A
revocation at tick 45 against a window expiring at tick 40 changes nothing.

## Worked example six, cancellation before the grant

A stream cancelled at tick 50, with a window granted at tick 52.

The grant tick is at or after the cancellation tick, so the window is
reclaimed. Every token it drafted under its policy K goes to the reclaimed
class. Its accepted, rejected, expired and voided counts are all zero
regardless of what its vectors agreed on.

## Worked example seven, cancellation during the lease

The same stream cancelled at tick 50, with a window granted at tick 47 and an
effective expiry of 55.

The grant tick is before the cancellation tick, so the window is not reclaimed.
Its expiry is brought forward to 50 because 50 is earlier than 55, and its span
becomes 3. Whatever the agreed prefix comes to, at most 3 of those tokens are
accepted and the rest of the prefix is expired.

This window is the one the cancel timeline counts as straddling. A window
granted at or after the cancellation tick is counted as after, not as
straddling, and the two counts never overlap.

## Worked example eight, a void window

    grant tick        30
    recorded expiry   29

The recorded expiry is at or before the grant tick, so repair `R05` applies and
the window is void. Every token it drafted goes to the voided class. Its
recorded expiry is still carried into the window index unchanged, because that
column reports what was recorded rather than what was applied.

A void window still occupies its slot in the window index and still counts
toward the window count of its slot in the occupancy artifact, but its span is
0 so it contributes nothing to the effective ticks of that slot and cannot
raise its peak concurrency.
