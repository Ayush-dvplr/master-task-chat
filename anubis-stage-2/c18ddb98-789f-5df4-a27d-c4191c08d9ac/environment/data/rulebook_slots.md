# Rulebook: slots

Filed under S in the platform reference set. Reserve slots are how the platform
holds capacity back from a window. Each condition below stands on its own, and
every one of them has to hold at the same time.

## S1 What a designation is

Every channel has a slot ceiling. Designating reserve slots means choosing, for
each channel that takes part, exactly as many of its feeds as its slot ceiling
allows. A channel takes part when at least one of its member domains is not
provisional. Participation is read off the domain register alone and is settled
before the window is, so a channel that takes part designates its slots even
where the settlement later leaves it with no settled member domain and so no
channel report of its own.

The records of a designated feed are held back from the window: each one that
had not already been settled otherwise is withdrawn from the curated output and
booked with the reason `withdrawn_by_reserve_designation`.

## S2 Which feeds may be designated

A feed may be designated only when all of the following hold. It belongs to a
domain that belongs to the channel doing the designating. It is not suspended.
Its domain is not provisional. And no incident governs it at the instant the
window closes, in the sense of the incident governing rule filed under
adjustment.

Feeds that fail any of those conditions are not candidates. The number of
candidates each channel had is reported alongside the designation so the
operator can see how much room there was.

## S3 Conditions on a designation within a channel

Within one channel the designated feeds must all declare different feed classes.
Two feeds of the same class may not both be designated by the same channel.

At least one designated feed of a channel must declare the class `primary`.

No single domain may have every one of its eligible feeds designated. A domain
that would be left with no undesignated eligible feed makes the designation
invalid.

## S4 The condition that spans channels

The platform holds back a share of the window it can measure. The nominal
throughput of the window is the total nominal throughput of every feed that is
not suspended, across all channels and all domains, provisional or not. The
designated share is the total nominal throughput of every designated feed in
every channel, expressed in basis points of the nominal throughput of the
window, rounded down to a whole basis point.

The policy register names the lowest and the highest designated share the
platform will accept. The designated share has to fall at or between those two
figures.

## S5 Exactly one designation is valid

The conditions in S2, S3 and S4 admit exactly one designation for a window. A
channel considered on its own will usually admit several, and a choice that
looks reasonable for one channel can leave no valid choice for another, so a
designation is a property of the window rather than of any single channel.

If a window admitted no valid designation, or more than one, the platform would
refuse to settle it. The window in this working set admits exactly one.

The settled window reports the designation: the designated feeds of each
channel, the nominal throughput each channel designated, how many candidates it
had, its slot ceiling, the nominal throughput of the window, the total
designated throughput, and the two share figures the policy register named.
