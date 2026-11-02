# Worked examples

Every example below is arithmetic on invented values. None of
them is a value from this cycle.

## RR2, converting a recorded quantity

`7.5 kj` with `kj = mwh|2500|9|live` is
`half_even(15/2 * 2500/9) = half_even(6250/3) =
 half_even(2083.333...) = 2083 mwh`.

`4.5 tick` with `tick = ms|125|2|live` is
`half_even(9/2 * 125/2) = half_even(1125/4) =
 half_even(281.25) = 281 ms`.

`2.5 beat` with `beat = ms|1875|4|live` is
`half_even(5/2 * 1875/4) = half_even(9375/8) =
 half_even(1171.875) = 1172 ms`.

A halfway case: `1 tick` is `half_even(125/2) =
 half_even(62.5) = 62`, because 62 is even. `3 tick` is
`half_even(375/2) = half_even(187.5) = 188`, because 188 is
even. Rounding half up would give 63 and 188.

`900 pulse` with `pulse = mwh|1|0|withdrawn` converts to
nothing: the record is set aside under `UNCONVERTIBLE_UNIT`.

## RR6, reading a delta chain

With `origin_ms = 1800000` and the live rows for the first
three windows recording start differences of `0 ms`, `120 min`
and `90 min`, the starts are `1800000`, `9000000` and
`14400000`. Reading
the third row alone and taking `90 min` as a start would place
that window at `5400000`.

## RR1, picking the live row

A key whose frozen revision is `9` and whose register carries
revisions `3, 7, 9, 12, 14` settles on revision `9`. If the
register carried `3, 7, 12, 14` instead it would settle on `7`.
The greatest revision, `14`, is never the answer unless the
frozen revision is at least `14`.

## RR4, absence against an explicit zero

A device policy row with an empty `cooldown_value` does not
settle the cooldown; resolution falls to the action layer. A
device policy row with `cooldown_value` `0` and
`cooldown_unit` `s` settles the cooldown at zero milliseconds
and the audit records `device` as the winning layer.

## Stage r09, the two products

An action of `3333 mwh` at a resolved intensity of `11000 bp`
with a class surcharge of `-500 bp` and a window scale of
`12500 bp` gives an effective intensity of `10500 bp`, then
`half_even(3333 * 10500 / 10000) = half_even(3499.65) = 3500`,
then `half_even(3500 * 12500 / 10000) = half_even(4375) =
 4375 mwh`. Multiplying `3333 * 10500 * 12500` and rounding
once gives `4374.5625` rounded to `4375` here, but the two
rounding points and the one rounding point disagree in general;
the two rounding points are the contract.

## Stage r10, the pool

A ceiling of `40000 mwh` with a reserve of `750 bp` withholds
`half_even(40000 * 750 / 10000) = 3000 mwh`. If mandatory
actions drew `1200 mwh`, the withheld share falls to
`3000 - 1200 = 1800`, the remainder is `40000 - 1200 = 38800`,
and the discretionary pool is `38800 - 1800 = 37000 mwh`. If
mandatory actions had drawn `5000 mwh`, the withheld share
would be zero and the pool would be `35000 mwh`.

## Stage r12, an overturn

A pool of `1000 mwh` first offered to incumbents `X` at tier 5
demanding `600` and `Y` at tier 6 demanding `300` takes both.
If `Z`, a fallback at tier 2 demanding `700`, is proposed for
the same window and device, the second round orders `Z`, `X`,
`Y` and takes `Z` and `Y`; `X` is overturned and is terminal.
The first round's allocation was correct on its own inputs and
wrong once the proposal existed.

## Stage r13, one shot consumption

An override with one remaining that applied to an instance
which r12 kept and r14 withdrew is not consumed. The
next snapshot still records one remaining.
