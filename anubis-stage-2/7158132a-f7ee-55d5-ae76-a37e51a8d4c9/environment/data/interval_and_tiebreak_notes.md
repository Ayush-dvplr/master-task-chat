# interval and tie break notes

These rules apply at every stage and are not restated in the stage
documents.

## half open everywhere

Every interval in every shipped file is [start, end). The start instant
belongs to the interval and the end instant does not. This holds for
service windows, maintenance dockets, blackout advisories, rate schedule
rows, alias crosswalk windows, contract validity, override windows,
campaign phases, accounting days and outage claims.

Consequences worth stating because they are easy to lose:

  two intervals that share only an endpoint do not overlap;

  a lookup for instant t takes the row where from <= t and t < to;

  an interval of zero length contains no instant and overlaps nothing,
  yet is a legal record;

  subtracting [b, c) from [a, b) removes nothing.

## comparisons that are inclusive on purpose

Three comparisons in this pipeline are at or before rather than strictly
before, and each is stated in its own stage document as well:

  a cancellation effective exactly on the commit boundary is a late
  cancellation and not a rejection;

  an event recorded exactly on the commit boundary is protection;

  an outage overlap total exactly equal to the qualifying floor
  qualifies.

## the ordering ladder

The five key ordering of S07 is used in three places: to resolve
contention, to order the rows a ration walks, and to order the residual
distribution. It is one ladder and the same ladder each time.

Level five, contact_id ascending, is a total order over the rows of an
aperture period, so the ladder never falls through. Two rows of the same
pass in different periods never contend, because their intervals lie in
different period windows.

## sort stability is not a rule

Nothing in this settlement may depend on the order rows happen to sit in
a file, on the order a directory listing returns, or on the stability of
a sort. Every ordering that decides a value is published.
