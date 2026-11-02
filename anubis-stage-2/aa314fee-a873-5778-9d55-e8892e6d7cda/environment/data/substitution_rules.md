# Substitution

Sections of this document are amended by `errata_2031-07.md`.

## 1. Edges

`node_substitution_factors.csv` declares directed edges from one node to
another, per site and cycle, with a factor stated per hundred in
`factor_per_100`. `factor_display` renders the same number with a decimal
comma and carries no weight. For each site, cycle and ordered pair of nodes,
the governing row is the admitted row with the greatest effective instant at
or before the start of the cycle, ties broken by the greater `revision_seq`.
The edge is in force when the status of that row is `in_force`.

## 2. The walk

The walk is evaluated at the start of the cycle of the request. Where the
requested node is in the qualified set of the site cycle the walk ends at
once, with zero hops and a factor product of one hundred to the power zero.

Otherwise the walk steps along exactly one edge at a time. From the current
node, take the in force edge with the smallest `factor_per_100`, ties broken
by the target node text ascending, and move to its target. The walk stops as
soon as it stands on a node in the qualified set. It never takes more steps
than the hop limit declared in `derivation_policy.ini`.

Where the walk arrives at a node it has already stood on, the request carries
the reason `UNRESOLVABLE_SUB_CYCLE` and is tallied as
`substitution_cycles`. Where the walk reaches the hop limit, or stands on a
node with no edge in force, without having found a qualified node, the request
carries the reason `NO_QUALIFIED_NODE`.

## 3. What the walk yields

The served node is the qualified node the walk ends on and is reported as
`served_node`. The number of steps taken is reported as `hops`. The
conversion numerator is the product of the `factor_per_100` values of the
steps taken and the denominator is one hundred raised to the number of steps.
A request served at its requested node has numerator one and denominator one.
The hop counts of all ledger rows are tallied in
`policy_audit.substitution_hops`.
