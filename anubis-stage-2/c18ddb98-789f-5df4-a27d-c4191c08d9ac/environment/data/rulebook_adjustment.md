# Rulebook: adjustment

Filed under A in the platform reference set. Four adjustments can bear on the
unit rate of a curated record. Each is stated here on its own terms. This
rulebook deliberately says nothing about the sequence in which they compose,
because the sequence is a property of the platform rather than of any one
adjustment, and the published control figures are there to pin it down.

Every adjustment takes the unit rate as it stands when the adjustment is
applied, produces a new unit rate, and places that result on the settlement
grid. An adjustment that does not bear on a record leaves the rate exactly as it
found it and does not place it again.

## A6 Abatement

An incident is a period during which a feed was known to be degraded. An
incident carries a feed, a severity, an instant at which it opened, optionally
an instant at which it closed, and an abatement in micros.

An incident governs a record when the record sits on that feed and the record
emission instant is at or after the incident opening instant and, if the
incident carries a closing instant, strictly before it. An incident with no
closing instant recorded is still open.

More than one incident can govern the same record. Among the incidents that
govern a record, the one with the greatest severity speaks; where two of them
share that greatest severity, the one whose incident identifier is greatest
compared as text speaks. Only the incident that speaks contributes its
abatement; the others contribute nothing.

Abatement subtracts its micros from the unit rate. A unit rate never goes
negative: if the abatement is larger than the rate it bears on, the rate becomes
zero rather than a negative number. A record no incident governs is not abated
at all.

## A7 Rebate

A feed carries a defect allowance in basis points. The rebate reduces the unit
rate of a record on that feed in proportion to the feed defect allowance: the
rate is scaled down by the allowance expressed as a fraction of ten thousand, so
an allowance of nothing leaves the rate untouched and a larger allowance leaves
less of it. The result is placed on the settlement grid.

The rebate bears on every curated record, because every feed carries an
allowance.

## A8 Override

Where an upheld exception names a record, the agreed unit rate on that exception
replaces the unit rate of the record outright. It is a replacement and not an
addition, a discount or a ceiling: whatever the rate happened to be at that
moment is discarded and the agreed rate stands in its place.

An override bears only on records an upheld exception names. It bears on no
other record, and it never bears on a record twice.

## A9 Surcharge

A feed that is over its nominal throughput attracts a backpressure surcharge on
its records. The platform holds one backpressure coefficient, a whole number of
micros, for the whole window, and the surcharge adds a share of that coefficient
to the unit rate.

The share is the overage expressed as a fraction of ten thousand. The costing
rulebook says how far over a feed is, in basis points of its nominal throughput,
so a feed running at exactly twice its nominal throughput is over by ten
thousand basis points and attracts the coefficient whole, a feed a tenth over
attracts a tenth of it, and a feed at three times nominal attracts twice it. The
share is taken down to a whole micro before it is added, and the sum is placed
on the settlement grid.

The coefficient is not written down anywhere in this reference set. It is one of
the properties the published control figures are there to pin down.

A feed at or below its nominal throughput is over it by nothing, so the
surcharge adds nothing to its records. Because the extent of the overage is
measured over the curated set as the costing rulebook defines the feed load,
before a domain is curtailed to its curated cap, the surcharge on a record
cannot be known from the landing register alone.
