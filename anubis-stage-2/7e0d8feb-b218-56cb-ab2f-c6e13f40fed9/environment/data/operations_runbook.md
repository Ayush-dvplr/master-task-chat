# Operations runbook

Notes the playout desk keeps. Nothing here overrides a stage specification.

## Why the day starts at six

The channel hands over to the network at six in the morning, so the
operational day and the regulatory day both open there. The consequence
people forget is that a slot labelled `02:30:00;00` is at the end of the
day and not at the start of it, and that the clock hours `H24` to `H29` are
the small hours of the following calendar date.

## Why the rate is a fraction

The channel is a `30000/1001` service. Nothing in this house is `29.97`.
The traffic system prints `29.97` on its screens and that label has leaked
into the ingest register as `nominal_fps`, which is why the register
carries a rate code as well.

## Why there is a carry

A minute of `25` frames per second material is `1500` source frames and
`1798.2018` channel frames. Rounding each part to nearest loses a frame
every few parts and the slot drifts. The carry keeps the drift where it
belongs, which is inside the slot, and publishes what is left over.

## Why the last break moves

Splices have to land on an index frame, and the index does not care where
the break plan wanted the break. If every break in a slot moves independently
the slot ends in the wrong place and the whole rest of the day moves with
it. The last break carries the accumulated displacement back so that the
slot ends where the schedule says it ends.

## Why the workbook has three sheets

Contract terms are agreed two quarters ahead and a withdrawn revision stays
on the books for audit, so at any moment there are three sets in the
workbook and only one of them is settled. The configuration names the
settled control set. Reading either of the other two gives a snap tolerance
that is close enough to look right and a commission that is wrong, and the
two of them are wrong in different directions.

## Why the prior register is here

The old conform ran before the index was published and before the carry rule
was written down. It is kept so that the recomputation can be reported
against it. It is not an input.
