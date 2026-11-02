# Worked examples

The numbers below are invented for the example. They show the shape
of each rule, not this epoch's values.

## Unit normalisation

A record lodges `quantity` 7 in unit `shift`. The unit registry
gives `shift` a scale of 480. The station sits in class `BR` on the
frozen register, and the live workbook sheet gives class `BR` a
conversion of 9 over 4. The normalised quantity is
`half_up(7 * 480 * 9 / 4)` which is 7560 cu exactly. The rounding
happens once, here.

## Window construction

The requested range is positions 1 to 180 and the selected
checkpoint stands at watermark 62. The window opens at 63 and closes
one before 180, so it replays positions 63 to 179. Position 62 is
behind the engine and is never replayed again. The skipped count is
62.

## Compensation across the boundary

A compensating event at position 150 names a target at position 44,
which is behind the checkpoint. The target is read out of the
canonical history for its station, programme, kind and normalised
quantity. The target is not replayed. The restored `applied` ledger
says the target took effect, so the reversal goes ahead: a grant of
800 cu comes off the station balance and off the station programme
allotment, and the derived counter the compensation policy names for
`grant` comes down by `half_up(800 * reversal_num / reversal_den)`.
The counter `reversed_cu` goes up by the same amount and
`compensations` goes up by one.

## A second compensation on the same target

A later compensating event names the same target at position 44.
The target already sits in the reversed ledger, so the row is
written with disposition `void_duplicate`, `reversed_cu` zero and
`applied_order` zero, and no counter moves.

## Carry settlement

A station in class `CN` reaches a balance of 21440 cu. The ceiling
for the frozen revision and class `CN` is 20100 cu and the class
carry quantum is 80. The spill is 1340, the carried part is
`(1340 // 80) * 80` which is 1280, the balance settles at
`21440 - 1280` which is 20160, and `spilled_cu` goes up by 1280.

## Re offer rounds

Three events wait in the pending queue. The ladder offers them by
scope, then region rank, then normalised quantity ascending. Round
one admits the one whose predicate now holds; admitting it changes
the balance the next predicate reads, but that event was already
offered this round, so it waits for round two. When a round admits
nothing the run has settled. When the round ceiling is reached while
a round is still admitting, the run publishes that pass and records
that it did not settle.

## Ratio

A station holds 3 cu under one programme out of 8 cu across all its
programmes. The share is `0.375000000000`. A station whose
allotments cancel to zero publishes `0.000000000000` rather than
dividing.
