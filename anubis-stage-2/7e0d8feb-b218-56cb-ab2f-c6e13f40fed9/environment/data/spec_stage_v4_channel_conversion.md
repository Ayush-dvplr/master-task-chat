# V4 channel conversion

Input: a source frame count and its editorial rate.

## R10 the carry rule

This is the rule that applies at every stage that converts anything into
channel frames.

A count of `n` frames at the editorial rate `p / q` occupies exactly

    n * 30000 * q / (1001 * p)

channel frames. That value is a rational number and it is almost never a
whole number. To take it into whole frames:

  1. add the fraction currently held in the conversion's named carry scope
  2. take the floor of the sum
  3. keep the difference between the sum and its floor as the new held
     fraction of that scope

A duration in seconds converts the same way, with the exact value
`seconds * 30000 / 1001`.

The floor is taken toward minus infinity. Nothing is rounded to nearest at
any point. A scope releases a whole extra frame into a conversion whenever
the fraction it holds has reached one, which is exactly what step two does.

## The carry scopes

Each scope is opened with a held fraction of zero, is used by the
conversions that name it, and its residual fraction is published at the end
of the run.

| scope name | opened for | conversions inside it |
|---|---|---|
| `V4:` and the slot id | each placed slot | the parts of that slot, in part order |
| `V6:` and the slot id | each placed slot | the break offsets of that slot, in break order |
| `V9:` and the market ref | each market | the break capacities of that market, in transmission order |
| `V10:` and the market ref | each market | the substitute break offsets of that market, slot by slot |
| `V11:` and the advertiser ref | each advertiser with an order in `spot_order_book.jsonl` | the spot durations of that advertiser, in order reference order |

The scope name is the prefix, a colon, and the identifier, with no spaces.

## R11 the order inside a scope

Conversions inside a scope happen in the order the scope's row names. Parts
run in ascending `part_no`. Break offsets run in ascending `break_no`.
Capacities run in the market's transmission order, which is ascending break
position and then ascending break reference. Substitute break offsets run
slot by slot in ascending `sequence_no` of the placed slots, and in
ascending `break_no` of the substitute within one slot. Spot durations run in
ascending `order_ref` within an advertiser, and the advertisers run in
ascending `advertiser_ref`.

The spot duration conversion happens once for the whole day, before any
admission decision is taken, because the capacity check at V9 needs the
frame count and the frame count depends on the advertiser's earlier spots.

## Published

`segment_conform.csv` publishes, for each part of each placed slot, the
source frames, the exact channel frames to ten decimal places, the whole
channel frames the carry rule produced, and the fraction the scope held
after that conversion.
