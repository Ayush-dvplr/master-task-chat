# Substitution rules

`substitution_graph.csv` lists approved substitutions between serotypes. An edge is in force on
a date when the date falls at or after `effective_from` and strictly before `effective_to`.
Where more than one edge in force joins the same pair, the edge with the higher
`potency_percent` is used, with `edge_ref` breaking a tie.

A lot whose serotype equals the campaign target serotype reaches it in zero hops at full
potency. Otherwise a path of edges in force leads from the lot serotype to the target serotype,
and a path may use at most as many edges as `substitution.max_hops` declares. The path with the
fewest edges is used; among paths with the same number of edges the one with the greater product
of potency percentages is used, and the edge references in order break a remaining tie.

A lot enters the pool in the first round in which it is available. The hop count and the potency
product of the path used in that round fix the usable content of the lot for the whole campaign:
the usable content is the dose content multiplied by the potency product and divided by one
hundred for each edge of the path, truncated toward zero to a whole dose. The hop count recorded
against the lot stays the hop count of that first path.

A lot is observed at the opening of each live round from the round of settlement of its
consignment round onward. Observation stops at the opening at which the lot enters a pool, at
the first opening on or after its expiry, and at the first opening at which its certificate
chain is a cycle. A lot with no declared measurement basis is never observed. A lot observed in
the state `released` at one or more openings at which its serotype reaches no target serotype
is counted once under `RC_NO_SUBSTITUTE`, whether or not it enters a pool at a later opening,
and supplies nothing before it enters one.
