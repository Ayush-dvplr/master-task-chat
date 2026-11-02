# Known traps and footguns

Every reading below is one a careful engineer plausibly takes, and every one of
them is wrong for this network. The right reading and the paper that states it
are named beside each. Nothing here is concealed; the work is in holding all of
it at once.

 1. Taking the highest attempt number of a cluster whatever its lock state.
    Only an attempt in lock state LOCK_HELD is eligible. (T01)
 2. Taking the last row of a cluster in file order. Order in the log means
    nothing; the rule is the greatest eligible attempt number. (T01)
 3. Breaking a tie on attempt number by acquisition time. The first tie break
    is the smallest absolute offset from the epoch instant; acquisition time
    only breaks a tie that survives that. (T01)
 4. Treating the attribution window as closed at both ends. It is closed below
    and open above. (T01)
 5. Moving a row that lands in no window to the nearest epoch. It is set aside
    with DR_OUTSIDE_INTERVAL. (T01)
 6. Setting a cluster aside because a session in it was withdrawn. The journal
    withdraws sessions, not clusters; the cluster keeps its other attempts and
    only loses everything when no LOCK_HELD attempt survives. (T01)
 7. Recording more than one reason for a set aside row. The five predicates are
    ordered and the first match is the reason. (T01)
 8. Choosing the calibration report with the greatest issued_epoch_s.
    issued_epoch_s orders nothing. The applicable report is the one with the
    greatest effective_epoch_s on or before the reading. (T02)
 9. Breaking a tie on effective_epoch_s toward the larger revision. The smaller
    revision is the signed report and it wins. (T02)
10. Reading only delay_calibration_ledger.csv. The supplement carries further
    reports of the same register and they can be the applicable ones. (T02)
11. Leaving the delays in nanoseconds. The reports are nanoseconds and the
    readings are picoseconds. (T02)
12. Assuming every link records A minus B. Two of the four techniques record
    the opposite sense. (T03)
13. Growing the spanning tree in register order, or by breadth first search.
    The admitted candidate is the one with the smallest admission cost, then
    the smaller technique rank, then the smaller link identifier. (T04)
14. Breaking a tie on admission cost by link identifier alone. Technique rank
    comes first, and two links of equal cost and different technique do
    exist. (T04)
15. Rooting an unanchored component anywhere but at its lexicographically
    smallest node. (T04)
16. Dropping a link from the tree because it carries no reading. The tree is
    built from the register; readings play no part. (T04)
17. Interpolating an offset across a dead epoch, or carrying the previous
    epoch forward. Dead time is absence and stays absent. (T05)
18. Taking the reference oscillator of a node from node_register_current.csv.
    The interval works at the frozen revision. (T06)
19. Treating a monitor row flagged other than MON_VALID as a measurement. (T06)
20. Fitting a least squares line to the history window. The prediction is the
    line through the first and last valid points of the window. (T07)
21. Using this interval's own deviations to predict this interval. The
    prediction comes from the previous interval's archive. (T07)
22. Counting an archived deviation whose quality flag is not ARC_VALID. (T07)
23. Excluding an oscillator that carries exactly the history minimum. The
    comparison is strict and exactly the minimum is enough. (T07)
24. Including an oscillator whose node is in an unanchored component. (T07)
25. Forming the weight from the exact rational dispersion. The desk publishes
    the dispersion as a whole picosecond and forms the weight from what it
    published. This is one of the two carried roundings in the chain, the other
    being the weight grid of stage T09. (T08)
26. Dropping an oscillator whose dispersion is zero, or giving it an unbounded
    weight. It takes the ceiling weight of its class from the workbook. (T08)
27. Clamping a weight to the cap and discarding the excess. Capping is mass
    preserving and the excess is redistributed in proportion. (T09)
28. Running the node cap before the oscillator cap. The order is oscillator
    cap, node cap, one further oscillator sweep. (T09)
29. Iterating the oscillator cap to convergence. It runs to the sweep budget
    the memo publishes and then stops and says so. (T09)
30. Skipping the third pass, or running it to convergence. It is exactly one
    sweep. (T09)
31. Dividing the ensemble by the total weight of the ensemble. The denominator
    is the weight of the oscillators contributing at that epoch. (T10)
32. Rounding each weighted residual to a picosecond before summing. The
    quotient is formed exactly and rounded once when written. (T10)
33. Rounding the steering step to the nearest grid unit. It is truncated toward
    zero, so a step below one grid unit becomes zero. (T11)
34. Applying the steering correction from the decision epoch. The first
    corrected epoch is the one after it. (T11)
35. Adding the written free scale to the written correction. Both are rounded
    renderings; the steered scale is the exact sum, rounded once. (T11)
36. Reducing the combined uncertainty to a standard deviation. It is published
    as a variance in square picoseconds. (T12)
37. Omitting the path terms from a node's budget, or including a path term for
    a node that is the root of its component. (T12)
38. Sorting a published artifact by its identifier when the schema reference
    states another order. (T13)
39. Taking the digest over the core artifacts in alphabetical order. The order
    is the one ordering_dependencies.yaml lists. (T13)
40. Reading the workbook sheet by name or by position. The live sheet is the
    one whose key cell matches the interval header. (T08 T09 T12)
41. Taking the publication digest over the core artifacts. It runs over every
    artifact except the manifest, in the order the output artifact contract
    lists them. (T13)
42. Writing the manifest before the rest of the publication. It digests the
    other twenty six documents, so it is written last. (T13)
43. Taking the full step toward the capped target. The pass moves the vector a
    fraction of the way, the damping the weighting policy publishes, and it
    damps every oscillator and not only the offenders. (T09)
44. Solving the cap in closed form, or iterating it to its fixed point. The
    published vector is the one the budget leaves, not the fixed point. (T09)
45. Carrying the exact rational between passes. Every pass places the vector
    back on the published weight grid and the next pass starts from the placed
    values. (T09)
46. Writing a SCOPE_OSCILLATOR dead time record for every oscillator of a node
    that is out. The node record already covers them; an oscillator record is
    the local monitor case alone. (T05 T06)
47. Starting the capping from the unplaced raw weight. The raw weight is
    published as stage T08 forms it, and the capping starts from that weight
    placed on the published grid, so the total the caps are taken from is the
    total of the placed weights. (T08 T09)
48. Growing the tree by the smallest published uncertainty in front of you, the
    minimum spanning tree of the component. The admission works on the
    accumulated path cost back to the root, and on this network the two
    readings admit different links. (T04)
49. Letting the grid placement of a capping pass move the total of the weight
    vector. The residue of the placement is closed onto one receiving holder,
    so every pass preserves the total exactly. (T09)
50. Closing that residue onto the same holder on every pass. Which holder
    carries it is decided by how often each receiving holder has already
    carried it in this interval, counted across all three phases, so the
    carrier moves from pass to pass. (T09)
