# Epochs, clocks and pool windows

## Ticks

The runtime keeps one monotone tick counter for the whole fleet. A segment
origin is a reading of that counter, taken when the segment opened. Ticks are
whole numbers and no figure ever carries a fraction of a tick.

## The cursor inside a segment

The events of a segment stand in logical order along the tick counter. The
first event of a segment stands at the segment origin. Every later event stands
at the segment origin advanced by the running total of the hold spans of the
events that precede it in that segment, that total taken in nanoseconds and
converted to whole ticks by the hold scale, which is a withheld constant. The
conversion divides the nanosecond total by the hold scale and keeps the whole
part.

The cursor starts again at the origin of every segment. It never carries across
a segment boundary.

## Epochs

The fleet groups ticks into epochs of equal length. The epoch of a tick is the
whole part of that tick divided by the epoch span, which is a withheld
constant. Epoch numbering starts at zero at tick zero.

## Pool windows

Every worker pool is in service for a stretch of the tick counter, recorded in
the pool window table as an open tick and a close tick. An event stands inside
its pool's window when its tick is at or after the open tick and strictly
before the close tick.

An event whose tick falls outside the window of the pool its worker belongs to
is set aside as outside window and takes no part in any figure.

## Which pool

The pool an event belongs to is the pool the thread registry gives for that
event's worker at that event's own epoch, and not at the epoch of any other
event of the same segment. A segment whose events span an epoch boundary can
therefore stand under more than one pool.
