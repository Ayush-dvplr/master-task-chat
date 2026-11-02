# The work ledger

The desk publishes what the engine did as well as what it decided, because a
round that reaches the right figures by deriving the whole model again has
told the desk nothing about which of its papers actually moved.

A cell is visited when a stage reaches it, whether the stage went on to derive
it or read it back out of the store. A cell is recomputed when the store did
not hold its key and the value had to be derived. A cell is revalidated when
it was visited and the value it came back with carries the digest it already
held, and a revalidated cell stops the cascade. A cell is reused when the
stage never reached it at all, so for each layer the reused count is the cells
of that layer in the model less the cells of that layer the stage visited.

The cache counters move on lookups. A lookup that finds the key the cell
already stands at, or finds it among the superseded entries the store retains,
is a hit; anything else is a miss. An eviction is a superseded entry dropped
to keep the store inside the retained count the board memo fixes. The store
always holds the value in force for every cell, so an eviction never drops a
value the round still stands on and never moves a published figure.

Two mistakes are visible here and they are visible in different documents.
Reaching too few cells leaves a stale value standing and the selection
documents disagree with the papers. Reaching too many leaves the selection
right and the work ledger wrong. The work ledger is published, so both are
defects.
