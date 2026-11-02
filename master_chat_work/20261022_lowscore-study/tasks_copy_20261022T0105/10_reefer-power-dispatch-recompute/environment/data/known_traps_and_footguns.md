# Known traps and footguns

Readings that have gone wrong on earlier operating days. Each is
settled by a stage specification; this paper only warns.

A load equal to the capacity is lawful. Only a load above the
capacity is a violation.

A state of charge equal to the reserve is lawful. Nothing may be
drawn from it while it sits there.

The standing reserve of a feeder is withheld before any free
capacity is counted, not after.

A confirmed crane duty reduces the capacity available to reefers. It
is not an extra load added to the reefer load, and the published
adjusted capacity shows the difference.

A disconnection minute is open. A window that closes on an interval
boundary closes the interval before it.

An absent ambient multiplier falls back to the class default. It is
not a multiplier of zero.

A declared energy return carrying the not supplied marker is a
return with no declared energy. It is not a declaration of zero.

A displaced placement moves to the next interval that admits it. It
does not move to the cheapest interval of the day.

The reconciliation pass budget is spent whether or not the shares
have settled. It is not a guard on a convergence loop.

The reconciliation rounds at the end of every pass and the next pass
opens from the rounded share.

What a share ceiling frees is redistributed inside the cross
classification of substation and service group, not across the whole
feeder.

The workbook sheet that governs is the one whose key cell carries
this day reference. Its position, its position from the end, its
sorted rank and its name all move from one operating day to the
next.

The admission ladder is read in the order the ladder paper prints.
That order is not the alphabetical order of the rung codes.

A set aside row is dropped before the sequence is read, so a set
aside row carrying the highest sequence settles nothing.

The objective is lexicographic. A schedule with a lower energy cost
still loses when an earlier component of the vector is worse.
