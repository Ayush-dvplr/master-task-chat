# Rulebook: quarantine

Filed under Q in the platform reference set. Quarantine is how the platform
stops a defective feed from polluting a settled window. Each rule stands on its
own.

## Q1 The defect pool of a feed

The defect measurement of a feed is taken over a pool. The pool of a feed is the
records on that feed that either survived every earlier judgement and are still
eligible for curation, or were withdrawn because a tombstone reached them.
Records that took no part in the settlement, and records withdrawn for any other
reason, are outside the pool and are not counted in it either way. A feed whose
pool is empty is not measured at all.

## Q2 What counts as defective

Within the pool of a feed, a record is defective when a tombstone reached it, or
when its canonical producer is tainted in the domain the feed belongs to in the
sense of Q4.

The defect rate of a feed is the count of defective records in its pool
expressed in basis points of the size of that pool, rounded down to a whole
basis point.

## Q3 The allowance

Every feed carries a defect allowance in basis points. A feed whose defect rate
is strictly greater than its allowance is quarantined. A feed whose defect rate
equals its allowance exactly is not quarantined. Every record on a quarantined
feed that had not already been settled otherwise is booked with the reason
`quarantined_defect_rate`, and those records are neither curated nor withdrawn:
quarantined is a disposition in its own right.

A feed that carries a reserve designation is not measured and is never
quarantined.

## Q4 Taint travels with the entity, inside its domain

When a feed is quarantined, the platform no longer trusts what that feed said
about the entities it carried. The canonical producers of the records on a
quarantined feed that were still eligible for curation become tainted in the
domain that feed belongs to.

A record whose canonical producer is tainted in its own domain, and which had
not already been settled otherwise, is withdrawn from the curated output and
booked with the reason `withdrawn_by_quarantine_cascade`.

Taint is confined to a domain. An entity tainted in one domain is not thereby
tainted in another, and records of that entity in another domain are unaffected.

## Q5 Quarantine and taint are settled together

Q2 counts a record as defective when its canonical producer is tainted, and Q4
taints an entity because of a feed that Q3 quarantined. The quarantine set and
the taint set therefore speak about each other, and neither is a consequence of
the other alone.

The platform requires a single state in which all of Q1 to Q4 hold at once: a
set of quarantined feeds and a set of tainted entities such that every feed in
the set is over its allowance when measured against that same taint, and no feed
outside the set is. A window has exactly one such state, and no feed that
belongs in it can be reached by asking the question only once.

The quality register reports nothing about quarantine. The settled window
reports the quarantined feeds of the whole window in its summary, and each
domain report names the quarantined feeds that belong to that domain.
