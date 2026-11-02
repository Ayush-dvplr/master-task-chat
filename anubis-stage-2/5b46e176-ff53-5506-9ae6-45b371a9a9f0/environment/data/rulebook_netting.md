# Rulebook: Netting

Filed under N. This rulebook consumes the cleared ledger, the operator
register and the netting policy register. It produces the gross obligation
graph, the cancelled cycles, the cycle free residual, each operator's net
position, the funding schedule and the netting digest.

It runs after the clearance because it reads the cleared ledger. It is not an
appendix to the clearance: an epoch with a correct clearance and a wrong
netting layer is not a closed epoch.

## N1. Obligations

Every **priced cross operator tap** raises one obligation. The payer is the
operator of the tap's own gate, which is the operator that took the fare at
the gate. The payee is the home operator of the tap's canonical identity
under I6, which is the operator the fare is owed to. The amount is

```
place(unit_fare_micros * interchange_share_bp / 10000)
```

with `interchange_share_bp` from the netting policy register and `place` the
settlement grid placement of T8. An amount that places to zero raises no
obligation at all and is not counted.

Obligations accumulate per ordered payer and payee pair, walking the priced
taps in canonical order. A tap that is not cross operator raises nothing.

## N2. Cycle cancelling

The gross obligation graph is a directed graph on the operators, with one
edge per ordered pair that carries a positive amount. While that graph
contains a directed cycle, the **first cycle in canonical cycle order** is
cancelled.

Canonical cycle order compares two simple cycles by:

1. the number of operators in the cycle, fewer first;
2. then the sequence of operators written starting from the
   lexicographically smallest operator in that cycle, compared
   lexicographically.

Cancelling a cycle means: take the smallest amount on any edge of the cycle,
subtract that amount from **every** edge of the cycle, and drop from the
graph every edge that has reached zero. Each cancellation is recorded with
its sequence and the amount cancelled, in the order the cancellations
happened.

Because every cancellation removes at least one edge, the process ends, and
what it ends on is the unique cycle free residual of the graph. Two node
cycles are cancelled before three node cycles, because N2 compares length
first.

## N3. Net positions

For each operator in the register, whether or not it is in scope, the account
records its gross out, its gross in, its residual out and its residual in.
Its **net position** is

```
net_position = residual_out - residual_in
```

The net positions of all operators sum to zero. That is a conservation
identity and the account proves it rather than asserting it.

## N4. The funding schedule

The residual edges are put in a funding order:

1. the payer's `clearing_rank` ascending,
2. then the payee's `clearing_rank` ascending,
3. then the amount descending,
4. then the payer identifier ascending,
5. then the payee identifier ascending.

Walking that order, each edge is **funded** when the payer's cumulative
funded amount plus this edge stays at or below the payer's
`funding_ceiling_micros`. Otherwise the whole edge is **deferred**: it is not
funded in part, and a deferred edge leaves the payer's running total
unchanged, so a later smaller edge from the same payer can still be funded.

Each row of the schedule records its payer, its payee, its amount, its state
and the payer's running funded total after that row.

## N5. The netting digest

The digest is taken over the funding schedule, in funding order, starting at
zero:

```
digest = 0
for each row:
    digest = (digest * netting_multiplier + amount_micros) mod netting_modulus
```

with the multiplier and the modulus from the netting policy register. An empty
schedule has a digest of zero.

## N6. Conventions this rulebook does not borrow

The netting layer sits on top of the clearance but it does not inherit its
conventions beyond the settlement grid, which N1 names explicitly. In
particular the funding order of N4 is not the canonical ledger order and is
not the order the obligations were accumulated in, and the cycle order of N2
is not any order the clearance uses. Take each from here.
