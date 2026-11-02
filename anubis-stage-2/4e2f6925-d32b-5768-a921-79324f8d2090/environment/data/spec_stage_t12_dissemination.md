# T12 dissemination and the uncertainty budget

## Input

The node offsets of T05, the steered scale of T11, the spanning trees of T04,
node_register_frozen.csv at the frozen revision, the uncertainty component
table on the live workbook sheet and uncertainty_budget_policy.yaml.

## The published offset

At every epoch, for every registered node,

    offset(k) = node offset(k) - steered scale(k)

carried as an exact rational and rounded once when written. A node with no
offset at an epoch, and any epoch whose steered scale is empty, gives an
absent offset with flag OFF_ABSENT. Every other offset carries OFF_PUBLISHED.

## The budget terms

The terms of a node's budget are, in this order:

    the seven uncertainty components of that node's reference oscillator,
    taken from the live workbook sheet in the order the sheet lists them;

    the declared_uncertainty_ps of that node at the frozen register revision;

    the published_uncertainty_ps of every tree edge on the path from the root
    of its component to that node, taken from the root outward.

A node at the root of its component contributes no path term.

## The two statistics

    u_combined_ps2 = the sum of the squares of the terms, in square picoseconds
    u_linear_ps    = the arithmetic sum of the terms, in picoseconds

Both are published. The combined statistic is a variance and is not reduced to
a standard deviation, because a square root of an integer is not in general an
integer and this publication carries no irrational value.

## Status

    DS_WITHHELD_UNANCHORED   the node is in an unanchored component
    DS_WITHHELD_NO_DATA      the node carries no published offset at any epoch
    DS_PUBLISHED             otherwise

The three are tested in that order.

## The mean offset

The mean offset of a node is the exact mean of its published offsets, rounded
once when written, and is written as zero for a node with no published offset.

## Output

The per epoch offsets, the budget terms and the two statistics per node, and
the dissemination ledger.
