# Rulebook: Assurance

Filed under A, after admission. This rulebook consumes the cleared ledger,
the gate register and the assurance policy register. It produces the per tap
margins, the holdback decisions, the retained pool, the distance
apportionment, the assurance digest and the assurance ladder.

Like the netting layer it is one of the outcomes the epoch is closed on, and
like the netting layer it does not borrow the conventions of the rulebooks
above it. Every convention it uses is stated here, and where it differs from
the clearance the difference is deliberate.

## S1. The margin of a priced tap

For each priced tap with `distance_units` above zero:

```
margin = (unit_fare_micros - floor_fare_micros) // distance_units
```

with `floor_fare_micros` taken from the tap's own gate, and with integer
division that **truncates toward zero**. This is the one division in the
whole reference set that is not placed on the settlement grid. A margin is
not a grid point and is never made into one.

A priced tap whose `distance_units` is zero carries no margin. It is not part
of the sample, it is not retained, it is not held back, and it is listed by
`tap_id` in the assurance account.

## S2. The median convention

A median in this rulebook is taken as follows. Order the values ascending. An
odd sample takes its middle value. An **even sample takes the lower of its
two middle values**: it is not averaged, and the result is not placed. A
median is therefore always a value the sample actually contains. An empty
sample has a median of zero.

## S3. Deviation, dispersion and the threshold

With `median` the median of the margins under S2:

```
deviation = abs(margin - median)                for each tap in the sample
mad       = the median of the deviations        under S2 again
threshold = assurance_sigma * mad
```

with `assurance_sigma` from the assurance policy register.

## S4. The holdback rule

A tap is **held back** when its deviation is **strictly above** the
threshold. A tap whose deviation sits exactly on the threshold is retained.

A small sample holds nothing back: when the sample size is at or below
`min_sample` from the assurance policy register, every tap in the sample is
retained whatever its deviation. The estimator is the median absolute
deviation about the median, and it is named here because a dispersion taken
any other way moves the threshold and with it the holdback set.

## S5. The pool

The pool is the sum of the margins of the retained taps. Held back margins
join neither the pool, nor the apportionment weights, nor the digest order.

## S6. The distance apportionment

The distance units of the **retained** taps are apportioned across the rider
classes present among the retained taps, in proportion to each class's
retained margin total, by the method of largest remainders:

1. For each class, the exact share is `retained_distance * class_weight`, and
   the class takes the integer part of that divided by the total weight.
2. The units still unassigned go one each to the classes with the largest
   remainder, remainders compared descending, ties broken by ascending rider
   class, cycling through that order until nothing is left to assign.

Where the total weight is zero but at least one class is present, the first
class in ascending order takes every unit. Where no class is present nothing
is apportioned.

The shares sum exactly to the retained distance units. That is a conservation
identity.

## S7. The digest order and the digest

The digest is taken over the **retained** taps only, in an order of its own:

1. margin ascending,
2. then `tap_id` ascending.

That is not the canonical ledger order and it is not the order the margins are
reported in. Starting at zero:

```
digest = 0
for each retained tap in digest order:
    digest = (digest * assurance_multiplier + margin) mod assurance_modulus
```

with the multiplier and the modulus from the assurance policy register. An
empty sample has a digest of zero.

## S8. The ladder

The ladder is one row per rider class **present in the sample**, in ascending
rider class order. A class whose every tap was held back still gets a row,
with a retained count of zero, a margin total of zero and a share of zero.
Each row carries the class, its retained count, its held back count, its
retained margin total and its apportioned share. The ladder is rendered as
the artifact schema fixes it.
