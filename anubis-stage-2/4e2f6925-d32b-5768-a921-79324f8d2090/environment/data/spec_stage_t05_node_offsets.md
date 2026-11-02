# T05 node offsets and dead time

## Input

The signed differences of T03 and the spanning trees of T04.

## The path sum

The offset of a node is its clock minus the clock of the root of its
component, carried along the tree path from the root to that node. For a tree
edge whose parent is p and whose child is c, taken at epoch k,

    when the register gives node_a = p, that edge contributes  0 - difference_ps
    when the register gives node_a = c, that edge contributes  difference_ps

and the offset of the node is the sum of the contributions of the edges on its
path. The root of a component has an empty path and an offset of zero at every
epoch.

## Dead time

An edge on the path of a node can carry no canonical reading at an epoch,
because every attempt was set aside at T01. When that happens the node has no
offset at that epoch. The offset is not interpolated, not carried forward from
another epoch and not filled from another link. It is absent, and the absence
is recorded.

Two absences are recorded here. A tree edge with no canonical reading at an
epoch is recorded with scope SCOPE_LINK. A node whose path holds such an edge
at an epoch is recorded with scope SCOPE_NODE, naming the first edge on its
path, taken from the root outward, that is missing.

The node record stands for every oscillator at that node, so the oscillators
of a node that is out take no record of their own. Stage T06 records an
oscillator only for the local monitor case.

## Output

An offset or an absence for every registered node at every epoch, and the dead
time records.
