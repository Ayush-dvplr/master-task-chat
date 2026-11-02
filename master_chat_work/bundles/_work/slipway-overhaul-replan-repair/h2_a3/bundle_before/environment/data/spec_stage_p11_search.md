# Stage p11  the exact optimum of one precinct

Every subset of the selectable jobs of a precinct is examined, in ascending
mask order, the empty subset first. The selectable jobs of a precinct are its
jobs in force that are not blocked, taken in canonical job order, and the bit
positions of the mask follow that order.

A subset is opened into its closed set, tested against the binding slot groups
of the precinct, and tested against the three pools. A subset that breaches a
group is counted against the group rejections and goes no further. A subset
that leaves a pool is counted against the capacity rejections and goes no
further. What survives is charged and ranked by stage p10, and the
lexicographically least of them is the accepted set of that precinct.

Precincts are settled one at a time and the round is their sum. A prerequisite
never crosses a precinct, a slot group never crosses a precinct, a charge rule
never crosses a precinct and a pool never crosses a precinct, so the least
total over the yard is the sum of the least total of each precinct.
