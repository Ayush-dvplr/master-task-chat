# Dependency semantics

How an edge row becomes a live dependency, what a live dependency blocks, and
what the closure over live dependencies contains.

## 1. Edge rows

`edges_bridge_01.xml`, `edges_desk_01.csv`, `edges_desk_02.csv`,
`edges_import_01.jsonl`, `edges_mirror_01.tsv` and `edges_partner_01.psv` carry
edge rows. One row states that `dependent_key` waits on `blocker_key`, and
`asserted_at` is the instant at which that claim was made.

An edge row is first tested for rejection under section 6 of the protocol, where
its own instant is `asserted_at`. A row that survives rejection is accepted and
is then either live or dropped.

## 2. Liveness

An accepted edge row is dropped, and carries exactly one drop reason, when the
first of these holds:

```
dependent_key equals blocker_key                       EDGE_SELF
either key names no admitted commitment                EDGE_DANGLING
either endpoint principal refuses to resolve           EDGE_OUT_OF_SCOPE
```

The third test is the one that decides most of them. Take the obligor surface
of the winning assertion of the dependent commitment, and the obligor surface of
the winning assertion of the blocker commitment. Resolve each of those two
surfaces at `asserted_at`, which is the instant the edge was claimed and is not
the instant either commitment was observed. When either resolution returns
`UNKNOWN_PRINCIPAL` or `AMBIGUOUS_IDENTITY`, the edge is dropped.

A claim made at an instant when one of its two parties could not be identified
is not a claim about those two parties, and it does not become one because the
parties can be identified at some other instant.

An accepted edge row that survives all three tests is live.

## 3. Holding and blocking

A commitment holds when its resolved state is `OPEN` or `DEFERRED`. A commitment
whose resolved state is `SETTLED` or `WITHDRAWN` does not hold.

A live edge carries a block only when its blocker holds. A live edge whose
blocker does not hold carries nothing, blocks nothing, and is not a step on any
path.

A commitment is blocked when it stands on no cycle and at least one live edge
leaving it carries a block.

## 4. The closure

The closure is taken over blocking edges alone, meaning live edges whose blocker
holds. From a commitment, every commitment reachable by one or more blocking
edges is in its closure, and the hop distance of a reached commitment is the
fewest blocking edges on any path to it.

A reached commitment is terminal when no blocking edge leaves it.

For a blocked commitment, the reachable count is the number of distinct
commitments in its closure, the frontier count is the number of those that are
terminal, the chain depth is the greatest hop distance in its closure, and the
frontier head is the lowest commitment key among the terminal ones.

## 5. Cycles

A set of holding commitments where each reaches the next by a blocking edge and
the last reaches the first is a cycle. Every commitment on a cycle is
undecidable under this protocol, because nothing in it can move first. Each of
them takes the class `UNRESOLVABLE` with the reason `CIRCULAR_DEPENDENCY`.

The cycle members a blocked commitment reaches sit in its closure like any
other reached commitment, and none of them is terminal, because a blocking edge
leaves each of them.
