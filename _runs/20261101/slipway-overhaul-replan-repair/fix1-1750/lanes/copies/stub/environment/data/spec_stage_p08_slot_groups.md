# Stage p08  the exclusive slot groups

An open membership row of `exclusive_slot_groups.csv` puts a job in a group. A
job that stands in two open groups keeps the group of the lower precedence
number, and keeps the group of the lower identifier where two groups carry one
precedence number. Its membership of the other group is rejected under
`GRP-DOUBLEBOOKED`.

A group left holding two or more open members binds: at most one of its
members may stand in the closed set of an accepted selection. A group left
holding one open member, or none at all, binds nothing.

The test is over the closed set and not over the jobs selected, so a group is
breached just as surely by a prerequisite that a selection pulls in as by a
job the selection names.
