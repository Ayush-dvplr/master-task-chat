# Stage p09  the pools and what is left of them

The capacity of a pool is the row of `pool_capacity_history.tsv` for that
precinct and pool with the greatest `effective_round` at or below the round
index whose state is `in_force`. A row with a later effective round, or with
any other state, settles nothing.

The carried quantity of a pool is the sum of the binding rows of
`carried_commitment_ledger.csv` for that precinct and pool. A row that is not
binding carries nothing.

The available quantity is the capacity less the carried quantity. A selection
stands within a pool while its usage is at or below the available quantity, so
a usage equal to the available quantity is within it. The board memo carries
the resolution in force on this point.
