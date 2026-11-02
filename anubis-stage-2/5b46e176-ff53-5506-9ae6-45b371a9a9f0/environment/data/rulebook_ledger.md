# Rulebook: Ledger

Filed under L. This rulebook consumes every admitted tap with its unit fare,
the exception register, and the reversal records inside the tap register. It
produces the epoch's tap ledger, the withdrawal reason of every withdrawn
tap, and the epoch charge.

## L1. The ledger is one row per tap

The ledger carries one row for every tap in the register, in canonical order,
including the out of epoch taps and including every withdrawal. Nothing is
dropped: a clearance that cannot account for a tap has not cleared the epoch.

Each row carries a `disposition`, which is one of `priced`, `withdrawn` or
`out_of_epoch`.

## L2. The withdrawal reason vocabulary

A withdrawn row carries exactly one reason, and the whole vocabulary is:

```
out_of_epoch        duplicate_tap_id     decommissioned_gate
identity_revoked    identity_retired     no_governing_table
reversal_record     voided_by_reversal   gate_suspended
cap_curtailed
```

A tap is withdrawn once. The first reason that applies to it in the order the
clearance runs is the reason it keeps, and a later rule never overwrites it.

## L3. The running charge

Each ledger row carries a running charge: the sum of the unit fares of every
priced row at or before it in canonical order. The running charge therefore
never decreases down the ledger, it is unchanged across a withdrawn row, and
the last row of the ledger carries the epoch charge.

## L4. Reversal records

A tap whose `op` column reads `void` is a reversal record rather than a
journey. It is never priced. It is withdrawn with the reason
`reversal_record`, unless some earlier rule already withdrew it, in which
case L2 keeps the earlier reason.

A reversal record also reaches back over the epoch and withdraws other taps
of the same canonical identity, with the reason `voided_by_reversal`. **How
far it reaches is one of the properties that has to be recovered.** The four
candidates are named in the calibration material and are read as follows:

| reach | what else the reversal withdraws |
|---|---|
| `tap_only` | nothing beyond the reversal record itself |
| `token_epoch` | every admitted tap of that canonical identity in the epoch |
| `token_zone_epoch` | those of them in the same zone as the reversal record |
| `token_operator_epoch` | those of them at gates of the same operator as the reversal record |

The reach is retroactive: it withdraws taps earlier in the epoch than the
reversal record as readily as later ones. Reversal records are resolved in
canonical order, and the reach is resolved **before** the suspension rulebook
runs, because the taps it withdraws are part of what a gate's burden is
measured against.

## L5. Exceptions

The exception register carries, per row, an `exception_id`, a `tap_id`, a
`status` of `upheld` or `rejected`, and a `unit_fare_micros`.

- An **upheld** exception naming a tap that is still priced replaces that
  tap's unit fare with the exception's `unit_fare_micros`. The row records the
  `exception_id` that moved it.
- A **rejected** exception does nothing at all.
- An upheld exception naming a tap that is already withdrawn **revives
  nothing**. The tap stays withdrawn and the exception is listed in the
  quality register.
- An exception naming a `tap_id` that is not in the register does nothing and
  is not listed.

Exceptions are applied **after** the suspension rulebook has reached its
fixpoint and **before** the capping rulebook runs, so an upheld fare counts
toward its zone's cap.

## L6. The epoch charge

The epoch charge is the sum of the unit fares of every priced tap, which by
L3 is also the running charge of the last ledger row. Every other total in
the account is a partition of it.
