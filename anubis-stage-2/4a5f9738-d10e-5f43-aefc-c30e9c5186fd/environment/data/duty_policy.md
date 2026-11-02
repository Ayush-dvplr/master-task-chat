# Duty policy

A holder named in `duty_budget_<segment>.csv` is audited. The audit runs over
the local calendar months of the zone the holder is filed against, taken from
the registry row with the latest as_of and on a tie the zone name that sorts
first, in
ascending month order, using the month bounds of that zone and not the bounds
of the zone of any individual grant. Months outside the horizon are ignored.

The occupancy of a holder in a month is the union measure of the final grant
extents of that holder inside the month. Overlapping grants of one holder
count once.

| quantity | rule |
| --- | --- |
| available | the month allowance plus the carry brought into the month |
| consumed | the smaller of available and occupancy |
| deficit | occupancy less available when positive, otherwise zero |
| carry_out | available less occupancy when positive, otherwise zero |

The carry leaving a month is zero when the holder has at least one visible
`suspend` event stamped inside that month, whatever the carry would otherwise
have been. The carry entering the first audited month is zero.

An allowance is stated in kilohertz seconds unless the notes field of the row
reads `unit=khz_min`, in which case the value is kilohertz minutes.

A month counts as a carry reset when a visible `suspend` event of the holder
falls inside that month and available exceeds occupancy, so a carry that would
otherwise have left the month was forced to zero. A suspend event of any grant
whose resolved holder is the holder counts, whatever became of that grant.
