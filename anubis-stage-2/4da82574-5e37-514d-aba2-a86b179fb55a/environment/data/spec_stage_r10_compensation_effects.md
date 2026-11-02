# Stage r10: Compensation effects

A compensating event whose target already sits in the reversed ledger is
recorded with disposition `void_duplicate`, a reversed amount of zero
and an applied order of zero, and moves no state and no counter. A
compensating event whose target does not sit in the applied ledger is
recorded with disposition `void_unapplied` on the same terms.

Otherwise the target effect comes off exactly. A reversed `grant`
subtracts its quantity from the target station balance and allotment. A
reversed `retire` adds it back. A reversed `transfer` adds it back to
the origin and subtracts it from the counterparty. Reversing a target
does not remove it from the canonical history and does not return it to
the pending queue.

The derived effect comes off as well. The reversed amount is
`half_up(quantity * reversal_num / reversal_den)` in exact rational
arithmetic, rounded here and nowhere else, half away from zero. The
quantity is the target's normalised quantity. The scale is the live
sheet's reversal scale for the class the frozen station register carried
for the target station at the revision of the target record that
survived the merge: the register row with the greatest revision at or
below that revision. When the register carries no row for the station
that early, the class in force at the frozen register revision is used.
The counter
`compensation_policy.toml` names for the target kind comes down by that
amount, the count counter for that kind comes down by one, `reversed_cu`
goes up by that amount and `compensations` goes up by one. The target
identifier is appended to the reversed ledger and the touched stations
settle.

The compensation register carries one row per compensating event that
reached this stage, in ascending compensation identifier order, holding
the compensation identifier, the target identifier, the target canonical
position, the disposition, the reversed amount and the application
order.
