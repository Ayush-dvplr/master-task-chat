# Rulebook: Suspension

Filed under S. This rulebook consumes the gate register, the zone register,
the operator register and the ledger as the reversal reach left it. It
produces the suspended gate set with a reason per gate, the unvalidated zone
set, the stood down operator set, and a further set of withdrawals.

The four states depend on each other, so none of them can be settled in one
pass. They are driven to a fixpoint.

## S1. Gate burden

For a gate, let `admitted` be the number of admitted taps at that gate and
`defects` be the number of those that are currently withdrawn, for any reason
at all. The burden is

```
burden_bp = (10000 * defects) // admitted
```

with integer division, and `burden_bp` is zero for a gate with no admitted
taps. A gate is suspended for burden when `burden_bp` is **strictly above**
its `fault_allowance_bp`. A gate sitting exactly on its allowance is not
suspended.

## S2. Suspension withdraws

Suspending a gate withdraws every tap at it that is still priced, with the
reason `gate_suspended`. Those withdrawals raise the burden of that same
gate, which is why S1 is evaluated again rather than once.

## S3. Zone validation

A zone is **unvalidated** when the number of its gates that are both
unsuspended and still carrying at least one priced tap falls **below** its
`validation_floor`. A zone with a floor of zero is never unvalidated by this
rule.

## S4. Provisional zones

A zone whose `provisional` flag is set is unvalidated as soon as **any** other
zone of the same operator is unvalidated. That is the only route by which one
zone's trouble crosses into another zone, and it is what makes the fixpoint
reach past a single zone.

## S5. Operators standing down

An operator is **stood down** when every zone it owns is unvalidated. An
operator that owns no zone is never stood down.

## S6. What the states do to gates

- Every gate of an unvalidated zone is suspended with the reason
  `zone_unvalidated`.
- Every gate of a zone of a stood down operator is suspended with the reason
  `operator_stood_down`.
- A gate whose `decommissioned` flag is set is suspended from the start with
  the reason `decommissioned`, before any burden is measured.

A gate keeps the first reason it was suspended under. The reasons are
therefore ordered `decommissioned`, `burden`, `zone_unvalidated`,
`operator_stood_down`, and a gate already suspended is never relabelled.

## S7. The fixpoint

One pass is: measure every gate's burden and suspend what S1 catches, then
settle zone validation under S3, then propagate to provisional zones under
S4, then stand down operators under S5, then suspend gates under S6, then
withdraw under S2. Passes repeat until a pass changes nothing: no new
suspension, no new unvalidated zone, no new stood down operator and no new
withdrawal.

Every one of the four state sets only ever grows, and withdrawals only ever
grow, so the fixpoint is reached and it is unique. The number of passes is
reported, and the count **includes the final pass that found nothing left to
change**.

Gates are taken in ascending `gate_id` within a pass, zones in ascending
`zone_id` and operators in ascending `operator_id`. The fixpoint does not
depend on that order, but the reported pass count does.
