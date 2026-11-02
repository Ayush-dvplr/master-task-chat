# T04 link graph, components and the spanning tree

## Input

link_register.csv, node_register_frozen.csv at the frozen revision, and the
hub node network_config.json names.

## Usable links

A link is usable when both of its nodes are registered at the frozen register
revision and the two are different nodes. A link with the same node on both
sides and a link naming a node the register does not carry are both dropped
here and take no part in the graph.

## Components

The usable links partition the registered nodes into connected components. A
node with no usable link is a component of one node. Components are ordered by
the lexicographically smallest node each one holds and are identified cmp_01,
cmp_02 and so on in that order.

## Roots

The component that holds the hub node is anchored, its role is ROLE_ANCHORED
and its root is the hub node. Every other component is unanchored, its role is
ROLE_UNANCHORED and its root is the lexicographically smallest node in it.

## The spanning tree

The link graph carries cycles, and two links can join the same pair of nodes.
The offsets of a component are computed along one acyclic tree and not along
the whole graph.

The tree of a component is grown from its root. At each step the candidate
links are the usable links of that component with exactly one end already
reached.

**What the admission minimises.** The uncertainty a node carries is not the
uncertainty of the one link that reaches it. It is the uncertainty of the whole
path the tree gives it back to the root, which is the quantity stage T12
publishes as the path terms of that node's budget. The admission works on that
accumulated figure and not on the link in front of it.

The path cost of a node is the sum of published_uncertainty_ps over the tree
edges between the root of its component and that node. The root has a path cost
of zero. The admission cost of a candidate is

    admission cost = the path cost of its reached end
                     plus its own published_uncertainty_ps

which is the path cost the unreached end would take if that candidate were
admitted. The link admitted is

    the candidate with the smallest admission cost;
    ties on that go to the candidate whose technique has the smaller rank in
    link_technique_reference.txt;
    ties on that go to the candidate with the lexicographically smaller
    link_id.

The tree this grows is not in general the tree the smallest published
uncertainty at each step grows. A cheap link hanging off a distant node loses
to a dearer link hanging off a near one, and the two readings admit different
links on this network.

The admitted link makes the unreached end a child of the reached end, and the
path cost of that end is the admission cost of the link that reached it. Growth
stops when no candidate remains. Every usable link of the component that the
tree did not admit is recorded as an excluded link.

A link is admitted or excluded on the register alone. Whether it carries a
reading at any epoch plays no part in growing the tree.

## Output

Per component: its identifier, its role, its root, its member nodes, its tree
edges in the order they were admitted, and its excluded link identifiers in
ascending order.
