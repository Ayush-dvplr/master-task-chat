# Rulebook: Tariff

Filed under T. This rulebook consumes the tariff table register, the zone
register, the gate register, the fault register and every admitted tap whose
identity resolved to `direct`, `rotated` or `cycle_broken`. It produces the
unit fare of each of those taps, in micros.

Every figure in this rulebook is an integer count of micros. No division is
ever carried in floating point.

## T1. The governing table

A tariff table row is live at an instant `t` when
`effective_from <= t` and either `superseded_at` is empty or `t <
superseded_at`. Of the live rows the governing table is the one with the
latest `effective_from`; where two share that instant, the one with the
greater `table_id` governs.

Tables may leave gaps and they may overlap. A tap at an instant no table is
live at is withdrawn with the reason `no_governing_table`, and is listed in
the quality register.

## T2. The rate

The governing table carries three rates. The rate for a tap is:

- `rate_concession` when the tap's `rider_class` is `concession`, whatever
  the time of day;
- otherwise `rate_peak` when the tap is a peak tap under A5;
- otherwise `rate_offpeak`.

## T3. The completion multiplier

The governing table carries three multipliers in basis points, one per
`completion_class`: `mult_complete`, `mult_open_exit` and `mult_forced`.
Ten thousand basis points is one times.

## T4. The gross fare before adjustments

With `rate` from T2, `band` the `tariff_band` of the tap's zone, and `mult`
the basis point multiplier from T3:

```
distance_rate_product = rate * distance_units
gross_before_adjustments = place(distance_rate_product * band * mult / 10000)
```

`place` is the settlement grid placement of T8. The product is formed first
and placed once; it is not placed in pieces.

## T5. The four adjustments

Four adjustments bear on the gross fare. Each one takes the running value and
returns a running value, and **the result of every adjustment is placed on
the settlement grid before the next adjustment sees it**. That is why the
order in which they compose changes the answer.

**`fault_abatement`.** The fault register carries, per fault, a `gate_id`, an
`opened_at`, a `closed_at` and an `abatement_micros`. A fault whose
`closed_at` is empty was still open at the end of the epoch and its window
runs to the epoch's `closes_at`. A fault covers a tap when the tap is at that
fault's gate and the tap's instant falls inside the fault window. The
abatement applied is the **largest** `abatement_micros` among the covering
faults, and faults do not add up. The running value becomes
`place(value - abatement)`. A value that would fall below zero becomes zero.

The convention by which a fault window is read at its own two endpoints is
one of the properties that has to be recovered. The four candidates are the
same four names A1 uses, read the same way, with `opened_at` for the start
and the fault's effective close for the end.

**`concession_relief`.** For a tap whose `rider_class` is `concession` the
running value becomes `place(value * (10000 - relief_bp) / 10000)`, with
`relief_bp` from the governing table. For every other rider class the
adjustment leaves the value alone.

**`interchange_uplift`.** For a cross operator tap under I6 the running value
becomes `place(value * (10000 + uplift_bp) / 10000)`, with `uplift_bp` from
the governing table. For a tap that is not cross operator the adjustment
leaves the value alone.

**`shortfall_levy`.** The running value becomes
`place(value + place(basis * levy_bp / 10000))`, with `levy_bp` from the
governing table. The quantity `basis` is a share of is one of the properties
that has to be recovered. The four candidates are named in the calibration
material; each of them is a quantity this rulebook has already defined, and
each of them is defined whatever order the adjustments run in.

## T6. The order of the four

The order in which the four adjustments compose is **not stated here**. It is
one of the properties that has to be recovered, and the candidates are the
twenty four orderings of the four names above.

## T7. The gate floor

After the last adjustment has run, the gate's `floor_fare_micros` binds:

```
unit_fare = max(running_value, floor_fare_micros)
```

The floor binds once, at the end, and only upward. It is not an adjustment
and it does not take part in T6. Floors are published as multiples of one
hundred micros, so a floor is always a point of the settlement grid.

## T8. The settlement grid

The settlement grid is the whole multiples of a spacing called the grid step.
`place(x)` returns the multiple of the grid step nearest to `x`. A value
strictly nearer one multiple goes to that multiple. A value exactly half way
between two multiples is decided by the midpoint convention.

The grid step and the midpoint convention are both properties that have to be
recovered. The candidate grid steps and the four candidate midpoint
conventions are listed in the calibration material. The four conventions are
read as follows, writing `k` for the lower of the two multiples the value
sits between, measured in grid steps:

| midpoint convention | the multiple chosen |
|---|---|
| `to_even_multiple` | `k` when `k` is even, otherwise `k + 1` |
| `to_odd_multiple` | `k` when `k` is odd, otherwise `k + 1` |
| `away_from_zero` | `k + 1` |
| `toward_zero` | `k` |

Every quantity this rulebook places is at or above zero, so `away_from_zero`
always means upward and `toward_zero` always means downward.
