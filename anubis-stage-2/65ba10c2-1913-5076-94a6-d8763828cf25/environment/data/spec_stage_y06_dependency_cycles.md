STAGE Y06  Move dependencies and their cycles
shift KP-2042-S23

This stage builds the move dependency graph and breaks its
cycles. A cycle is broken, never rejected.

RULE Y06.1  Which edges are in the graph.
An edge of move_dependency_declarations.jsonl is in the graph
only when its state is declared and both of its orders are
canonical events. An edge marked lifted was stood down before the
shift opened. An edge from an order to itself is no edge.

RULE Y06.2  Finding the cycles.
A cycle is a strongly connected component of two orders or more.
Components are settled on the graph as it stands, and are found
again after every removal, because removing one edge can leave a
component that is still cyclic.

RULE Y06.3  Protected edges.
Inside one cyclic component rank its edges by weight descending
and then by edge_id ascending. The edges at the head of that
ranking are protected, as many of them as the protection depth
names. The protection depth is issued by
berth_operations_memo.pdf and is carried in no other paper.

RULE Y06.4  The edge that is removed.
The edge removed from a cyclic component is the edge of lowest
weight among its unprotected edges, and ties on weight are
settled by ascending edge_id. When every edge of the component is
protected the protection is lifted for that component alone and
the same rule is applied to all of its edges. The protected_count
the report carries is the number of edges the protection marked
at the head of the ranking, which is the protection depth or the
edge count of the component when that is smaller. It is published
as that number whether or not the protection then had to be
lifted, so it never reads zero for a component that carries an
edge.

RULE Y06.5  The component key and the order they are worked in.
The component key of a cyclic component is the lowest order
identifier the component carries. Components are worked in
ascending component key, one edge removed from one component at a
time, and a component that is still cyclic after its removal is
worked again straight away, before any component with a higher
key. The report carries one entry per removal, in that order, so
a component that lost two edges appears twice under one key.

RULE Y06.6  The dependency order.
After the cycles are broken the orders are placed one at a time.
At each step the placeable orders are those whose remaining
predecessors are all placed, and the one placed is the placeable
order with the lowest event key. This is a total order and it is
not the order any generic traversal happens to produce.

PUBLISHES  cycle_break_report.json, dependency_order.csv
