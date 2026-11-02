# Rulebook: egress

Filed under E in the platform reference set. Egress runs after the window has
settled and reads the curated ledger the settlement produced. It revises nothing
the settlement decided: every charge, count, cap, designation, quarantine state
and partition report keeps the value it already holds.

Egress exists because a settled charge says what a record cost, and operators
also have to know what a record cost per octet of payload it actually carried.
That per-octet figure is what the rest of this rulebook calls an egress rate.

## E1 The egress rate of a curated record

A payload unit is as many octets as the policy register publishes, and that
figure is written `octets` here. The egress rate of a curated record is the
whole number of micros it cost per octet:

    egress_rate = floor(record_charge_micros / (payload_units * octets))

The division truncates toward negative infinity. This is the one place in the
whole reference set that truncates: every other division the platform performs
places its result on the settlement grid by the convention rulebook costing
describes. Carrying that convention into E1 is wrong, and it is wrong on a large
fraction of the curated ledger rather than on a rare edge case.

Only curated records have an egress rate. A withdrawn record, a quarantined
record and a record outside the window have none, and none of them appears in
any egress artifact.

## E2 Burst records

Curated records group by the pair of their domain and their feed. Within each
group let `med` be the median of the group's egress rates and let `mad` be the
median of the absolute deviations `abs(rate - med)` over that same group. Both
medians follow E3. With `sigma` the egress sigma the platform publishes:

    threshold = med + sigma * mad

A record whose egress rate is STRICTLY GREATER than the threshold of its own
group is a burst record. It is recorded in the burst artifact and held out of
the egress pool, out of the apportionment and out of the E4 order. The median
absolute deviation enters the threshold exactly as E3 produces it, with no
consistency scaling applied to it.

A group holding fewer than four curated records is too small a sample to reject
from, so every record of such a group is retained however large its rate is.

## E3 The egress median

Every median in this rulebook is taken over the sorted sample. A sample of odd
size takes its middle value. A sample of EVEN size takes the LOWER of its two
middle values and never their mean, and never places the result on the
settlement grid.

## E4 Egress order

Egress artifacts that carry an order list the retained records by ASCENDING
egress rate, breaking a tie by ascending `record_id`. This is a different order
from the canonical ledger order the settlement wrote, which rulebook ledger
fixes by sequence, and the canonical order is never the order of an egress
artifact.

## E5 The egress pool

`egress_pool_micros` is the sum of the egress rates of the retained records.

## E6 Payload apportionment

The window's curated payload units are apportioned across the groups of E2 in
proportion to the summed egress rates of their retained records, by the largest
remainder method: an exact integer base share per group, then the remaining
units handed out one at a time to the groups holding the largest remainder, ties
broken by ascending group key, where a group key is its domain identifier and
its feed identifier joined by a colon. Every share is a whole number of payload
units and the shares sum to the window's curated payload units exactly.

A group whose retained records were all rejected under E2 takes no share.

## E7 The egress digest

With `r(i)` the egress rate at one-based position `i` of the E4 order, `n` the
retained record count and `m` the egress modulus the platform publishes:

    egress_digest = (sum over i from 1 to n of i * r(i)) mod m
