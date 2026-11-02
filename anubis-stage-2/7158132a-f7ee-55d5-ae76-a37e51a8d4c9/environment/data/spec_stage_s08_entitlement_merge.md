# S08 entitlement merge

Entitlement is per contract per settlement period, and it carries state
from one period into the next.

## the opening carry

prior_period_settlement.json holds the opening carry buckets, which are
the state at the start of P1 and nothing later. Only buckets whose
bucket_state is open carry. Closed buckets are already settled and carry
nothing. The opening carry source of a contract is the sum of the
unsettled_kib of its open buckets.

The carry source for P2 is what P1 left unconsumed, and the carry source
for P3 is what P2 left unconsumed. Those two are computed by this
pipeline and appear in no shipped file.

## the carry in

For a contract period, with carry_cap_kib from the settled terms:

  when carry forward is disabled, either on the settled terms or in
  settlement_audit_trace.db, carry_in_kib is zero and the whole carry
  source is forfeited;

  when the contract has expired, meaning its valid_to_s is at or before
  the start of the period, carry_in_kib is zero and the whole carry
  source is forfeited;

  otherwise carry_in_kib is the carry source capped at carry_cap_kib,
  and the amount above the cap is forfeited.

A carry source that equals the cap exactly carries in whole and forfeits
nothing. The period start used for the expiry test is the earliest
station local period open across the network, so one contract expires on
the same instant everywhere.

## the allowance

    available_allowance_kib = carry_in_kib + entitlement_kib

Carry is consumed before new entitlement. Every acceptance at S10 draws
from the carry remainder first and only then from the new entitlement
remainder, and the split is reported per pass.

## the carry out

carry_out_kib of a contract period is what the allowance had left when
the period closed, which is the carry remainder plus the new entitlement
remainder. It becomes the carry source of the next period, where it is
capped again against that period carry_cap_kib.

A contract with zero entitlement and zero carry cap has zero allowance
and accepts nothing, however much capacity its passes carry.
