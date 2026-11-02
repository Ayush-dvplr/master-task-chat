# V14 reconciliation and the digest

Inputs: everything above, and `prior_conform_register.csv`.

## The prior register

`prior_conform_register.csv` is the superseded automated computation of this
transmission day. It carries a start frame, a material frame count and a
break count per slot. It is wrong in places and it is never an input to any
other stage.

## R35 the reconciliation

`reconciliation.xml` publishes one `slot` element per slot in
`slot_placement.csv`, ordered by ascending `slot_id`, carrying the prior
value, the recomputed value and the delta for each of the start frame, the
material frames and the break count. The break count compared is the number
of national breaks the slot carries, which is the number of rows the slot
has in `break_positions.csv`.

The delta is the recomputed value less the prior value. A slot that agrees
on all three is counted as agreeing. The `totals` element carries the slot
count, the agreeing count, the differing count, and the sums of the absolute
start delta and the absolute material delta.

## R36 the digest

`manifest.json` publishes a `digest` which is the hexadecimal sha256 of the
concatenated bytes of the seven core artifacts, taken in the pipeline order
that `core_order` publishes and not in alphabetical order. The seven core
artifacts are the ones named in serialisation_and_digest_contract.md.
