# Rulebook: costing

Filed under C in the platform reference set. Costing turns a curated record into
a charge. Every charge in this platform is an integer number of micros. There
are no fractional micros anywhere in a settled window, in any artifact, at any
stage.

## C6 The settlement grid

The platform settles charges on a grid. The grid is a fixed positive number of
micros, and every unit rate the platform records has to sit exactly on that
grid: a settled unit rate is always a whole multiple of the grid spacing. The
grid spacing is a property of the platform for the whole window, not of a feed
or a domain or a record.

Arithmetic on charges does not naturally land on the grid, so a value has to be
placed onto it whenever the platform records one. Placing is exact when the
value already sits on the grid. Where a value falls between two grid points the
platform has a single fixed convention for choosing between them, and it uses
that same convention every time it places a value anywhere in the settlement.

Neither the grid spacing nor the convention for values between grid points is
written down anywhere in this reference set. Both are properties of the platform
that the published control figures are there to pin down.

## C7 The base unit rate

The unadjusted unit rate of a curated record comes from the rate on its
governing card for the tier class it declares, scaled by the multiplier on that
same card for the form class it declares. Multipliers are basis points, so a
multiplier of ten thousand leaves the rate unchanged, a larger multiplier raises
it and a smaller multiplier lowers it. The result is placed on the settlement
grid.

## C8 The feed floor

Every feed carries a floor rate in micros. No curated record on a feed may
settle at a unit rate below that feed floor. The floor is the last word on a
record unit rate: whatever the record would otherwise have settled at, if that
is less than the feed floor then the record settles at the feed floor.

The floor is a floor and not a target. A record that would settle above its feed
floor is left alone.

## C9 From unit rate to record charge

The charge of a curated record is its settled unit rate multiplied by the
payload units the record declares. A record that declares no payload units
carries no charge.

A record that is not curated carries no charge at all. Withdrawn records and
quarantined records appear in the ledger with a zero unit rate and a zero
charge, and they contribute nothing to any total.

## C10 Feed load

The load a feed carried in a window is the total payload units of its curated
records in that window. A feed whose load exceeds its nominal throughput is
running over its nominal throughput, and the identifiers of the feeds that did
so are reported in the quality register. Load is measured over the curated set
as it stands before a domain is curtailed to its curated cap, so a record that
is later dropped to fit the cap still counts toward the load of its feed, and a
feed can be reported over its nominal throughput even though the records that
survive curtailment carry fewer units than that. Load is therefore not knowable
from the landing register alone.

The extent to which a feed is over its nominal throughput is expressed in basis
points of that nominal throughput, rounded down to a whole basis point. A feed
at or below its nominal throughput is over it by nothing at all.
