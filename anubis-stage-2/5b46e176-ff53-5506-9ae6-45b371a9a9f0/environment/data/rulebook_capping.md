# Rulebook: Capping

Filed under C. This rulebook consumes the zone register, the operator
register and the ledger as the exception rule left it. It produces the loan
schedule between zones, each zone's effective cap, a further set of
withdrawals, and the cap relief account. It is the last rule that can
withdraw a tap.

## C1. Headroom

A zone's priced total is the sum of the unit fares of its priced taps. Its
headroom is

```
headroom = revenue_cap_micros - priced_total
```

A zone with negative headroom is **over its cap** and is a borrower. A zone
with positive headroom is a lender.

## C2. The release order

Zones are taken in a release order, and the same order decides both which
borrower is served first and which lender is drawn on first. **Which order is
in force is one of the properties that has to be recovered.** The four
candidates are named in the calibration material and are read as follows,
with every tie broken by ascending `zone_id`:

| release order | zones sorted by |
|---|---|
| `ascending_zone_id` | `zone_id` ascending |
| `descending_headroom_then_zone` | headroom descending |
| `ascending_headroom_then_zone` | headroom ascending |
| `descending_cap_then_zone` | `revenue_cap_micros` descending |

The headroom the order is computed from is the headroom of C1, measured
before any lending has happened. The order is settled once and is not
recomputed as loans change the headrooms.

## C3. Surplus lending

Taking each borrower in release order, the borrower draws on the lenders that
share its operator, taken in that same release order. A single loan is the
smallest of three quantities:

- what the lender still has spare,
- what the borrower still needs,
- what the operator has left of its `float_ceiling_micros`.

The ceiling is on the operator's **cumulative lending across the whole
epoch**, not per loan and not per zone. A loan of zero or less is not made
and is not recorded. Lending stops when the borrower's need is met or when
nothing is left to lend.

Every loan is recorded with its lender zone, its borrower zone, the operator
and the amount, in the order the loans were made. A zone's effective cap is
its `revenue_cap_micros` plus everything it borrowed.

## C4. Curtailment

A zone whose priced total is still above its effective cap curtails. Its
priced taps are taken in this order:

1. unit fare descending,
2. then tap instant ascending,
3. then `tap_id` ascending,

and each is withdrawn with the reason `cap_curtailed` until the zone's priced
total is at or below its effective cap.

## C5. The coverage obligation

One tap is protected from curtailment. A tap that is the **only remaining
priced tap at its gate** is skipped while that gate is unsuspended, so every
gate that was working during the epoch keeps at least one priced tap in its
zone's account. Curtailment moves on to the next candidate and the protected
tap stays priced.

A gate that is already suspended has no protected tap, because it has no
priced taps left to protect.

## C6. Zones that cannot reach their cap

The coverage obligation can leave a zone unable to reach its effective cap.
Such a zone is **cap infeasible**: it records the amount by which it still
exceeds its effective cap as its residual, it is named in the epoch summary,
and its own report says so. A cap infeasible zone is not an error and nothing
further is withdrawn from it.

A zone that reaches its cap has a residual of zero and is not cap infeasible.
