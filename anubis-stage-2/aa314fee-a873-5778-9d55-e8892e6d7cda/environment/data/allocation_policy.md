# Allocation policy

## 1. What is apportioned

Each site cycle has a capacity in wafer equivalents and a set of claiming
requests, each with a claim and with whatever committed minimum was honoured
for it. Grants are whole wafer equivalents. No grant is above the claim of its
request. The sum of the grants of a site cycle never exceeds its capacity.

## 2. The properties the apportionment satisfies

The apportionment is the one that satisfies all of the following at once.

1. Every honoured committed minimum is granted in full to its request, in the
   order the register gives, so long as capacity remains and the claim of the
   request reaches that far.
2. No request is granted more than a request whose claim is not met in full,
   except where its own committed minimum carries it higher.
3. No capacity is left unused while any claim is unmet.
4. Each claim is met as far as the two properties above allow, and the
   smallest grants are raised before the larger ones.

## 3. The level and the remainder

The level of a site cycle, reported as `fill_level`, is the greatest whole
number L for which granting every claiming request the greater of its honoured
minimum and the lesser of its claim and L keeps the total inside capacity.
Where every claim is met in full the level is the largest claim of the cycle.
Where no request claims, the level is zero.

Capacity left after every request has reached the level is distributed one
wafer equivalent at a time, one to each request whose claim is still unmet,
taken in order of the unmet part of the claim descending, then the governing
effective instant ascending, then the canonical identity ascending, then the
reported reference ascending, until the capacity is exhausted.

## 4. What the cycle reports

`granted_equiv` is the sum of the grants of the cycle, `residual_equiv` is the
capacity minus that sum, and `binding` is true when the residual is zero.
`request_count` counts the ledger rows of the cycle, claiming or not. A cycle
whose residual is above zero clears the lots of its site as
`carry_forward_rules.md` sets out.

## 5. Outcomes

`outcome` is `FULL` where the grant equals a claim above zero, `PARTIAL` where
the grant is above zero and below the claim, `ZERO` where the claim is above
zero and the grant is nothing, and `EXCLUDED` where the request does not claim
at all. A claiming request carries the reason `NONE`. A request that does not
claim carries exactly one reason, the highest that applies in the precedence
listed in `reason_codes.json`.
