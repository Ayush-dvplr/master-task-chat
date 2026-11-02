# Capacity and qualified nodes

## 1. Declarations

`site_capacity_declarations.csv` declares capacity per site, cycle and tool
group. `basis` is `absolute` or `delta`. A negative value is written in
parentheses, so `(240)` is minus two hundred and forty. `unit` is
`wafer_equivalents` or `lot_equivalents`, and a lot equivalent is the lot size
declared in `unit_declarations.ini`. `nodes` is a pipe separated list of the
process nodes the group runs. `status` is `online` or `offline`.

## 2. The governing declaration of a group

For a site, cycle and tool group, take the admitted `absolute` rows whose
effective instant is at or before the start of that cycle and keep the one
with the greatest effective instant, ties broken by the greater
`revision_seq`. That row is the base. Then add the value of every admitted
`delta` row for the same group whose effective instant is at or after the
effective instant of the base row and at or before the start of the cycle,
applied in effective order. A declaration that takes effect after the cycle
has started does not govern that cycle.

A group whose governing row has status `offline` contributes no capacity and
no qualified nodes for that cycle. The contribution of each online group is
floored at zero before the groups are added.

## 3. Cycle capacity and the qualified set

The capacity of a site cycle is the sum of the contributions of its online
groups, in wafer equivalents. The qualified node set of a site cycle is the
union of the node lists of its online groups. A node that appears only on an
offline group is not qualified in that cycle.
