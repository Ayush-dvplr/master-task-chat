# Expert capacity

Capacity is computed once per step from the demand recorded before any token is
dropped.

```
ideal = capacity_factor * total_assignments / num_experts
target(e) = min(demand(e), ideal)
aligned(e) = capacity_bucket * ceil(ceil(target(e)) / capacity_bucket)
capacity(e) = max(min_capacity, aligned(e))
```

`total_assignments` is the sum of demand over every expert for that step. The
alignment happens first and the minimum is applied to the aligned value. The
minimum is used exactly as configured and is never itself aligned, so a run
whose `min_capacity` is not a multiple of `capacity_bucket` produces capacities
that are not multiples of the bucket. That situation is legal and is reported.

The revision register decides which of the two orderings is in force. Read it.

## Dispatch

Assignments are walked in the order the router produced them, which is ascending
token index and, within a token, ascending selection slot. The running counter
for the named expert gives the slot index. An assignment whose slot index is at
least the capacity of its expert is dropped. Dropping affects only that
assignment; the other expert chosen for the same token is unaffected.

Two figures are published and they are sourced differently. `dropped_tokens`
counts dropped assignments. `dropped_token_mass` sums the combine weights of the
dropped assignments.

Slots between the accepted count and the capacity are padding. Padding carries
no token, contributes nothing to any accumulator, and never appears in a
denominator.
