# Carry forward

## 1. Lots

An unmet claim leaves a deficit lot. Lots are held per canonical identity and
site, each keyed by the cycle it arose in, its origin cycle. A lot of one
epoch is never carried into another epoch and a lot never moves between sites.

The number of later cycles a lot survives is not declared anywhere in these
documents. The readings under consideration are one, two, three, and
unbounded. `deficit_observations.log` holds settled lots from the periods
before the horizon, each line naming the origin period, the observed period,
the age of the lot and whether it was still carried or had expired. Exactly
one of the four readings reproduces every line. Read the log, keep the reading
that survives, and report it in `policy_audit.json` under `withheld` as
`carry_forward_age`, as a whole number or as the word `unbounded`. Lots that
reach the end of their life are tallied as `lots_expired`.

## 2. What carries in

At a cycle, the carried in figure of a request is the sum of the live lots of
its identity and site whose origin cycle is recent enough to survive, in
wafer equivalents, and is reported as `carried_in_equiv`. Where one identity
has more than one claiming request at the same site in the same cycle, the
carry forward attaches to the request with the earliest governing effective
instant, ties broken by the ascending reported reference, and the others carry
in zero.

## 3. The claim

The claim of a request is its own quantity plus its carried in figure,
limited by its governing ceiling:

    claim_equiv = min(quantity_equiv + carried_in_equiv, ceiling_equiv)

Where no ceiling is in force the claim is the sum. The claim divides into the
part that belongs to the current quantity and the part that belongs to the
carried lots, and a ceiling that binds cuts the carried part first. An amount
a ceiling keeps out of the claim stays in its lot and is not lost.

## 4. What the grant discharges and what is left

A grant discharges the carried part of the claim first, oldest lot first, and
only then the current quantity. The part of the current quantity the grant
does not reach becomes a new lot with its origin at this cycle. The shortfall
of the whole claim is reported as `deficit_equiv`, the running total of
shortfalls per identity and site is reported as `deficit_to_date_equiv` and
never decreases, and the running total of grants is reported as
`granted_to_date_equiv`. The sum of the lots that survive into the next cycle
is reported as `carried_out_equiv`.

## 5. Clearing

Where a site cycle ends with capacity still unused, every lot at that site
clears at the end of that cycle and carries nothing into the next, tallied as
`resets` and `lots_cleared`. The running total `deficit_to_date_equiv` is a
record of what happened and is never reduced by a clearing.
