# Channel ladder

The ladder runs `edge`, `canary`, `staging`, `stable`. A unit's seating is always a
prefix of the ladder: a unit seated in `staging` is also seated in `canary` and
`edge`.

## Which channels a unit occupies

Membership comes from `channel_membership_snapshot.csv`. Only rows carrying the
greatest `snapshot_seq` in the file describe the current cycle, and within those
only rows whose `state` is `promoted` count as seating. Earlier sequences are
history and the other states are not seating.

## The revision a channel seats

The revision a channel seats comes from that channel's mirror index. A publication
row counts when its `state` is `published` and its `published_at` is at or before
the decision instant. Where several rows for the same unit count, the seated
revision is the greatest of them. The snapshot's revision column records what was
believed at the start of the cycle and is not the seated revision. Where no
publication row counts for a unit the channel seats, the snapshot's revision
stands.

## Adjacency

Let the unit's highest occupied channel be its head. A request may target the head,
which refreshes it, or the channel one step above the head, which lifts it. A unit
with no seating at all may only target `edge`. Any other target is not adjacent.

## Regression

A refresh is a regression when the target channel already seats the unit at a
revision that is not lower than the requested revision. Revisions are compared as
the integer fields listed in `revision_grammar.json`, in that order. Text order is
not revision order.

## Seals

A channel closes at the end of a cycle. `relay_audit.log` records each close as an
event. A close that did not commit is not a close. The cooldown length the duty officers
recorded for this cycle counts from the most recent committed close at or before
the decision instant. While the cooldown has not elapsed the channel is
still closed and nothing is promoted into it.

## Normative parameters

```
ladder: edge,canary,staging,stable
membership_state: promoted
mirror_state: published
```
