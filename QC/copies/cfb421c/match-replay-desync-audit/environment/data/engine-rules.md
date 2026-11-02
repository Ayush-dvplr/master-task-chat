# Ninefold Marches simulation rules

These are the rules the simulation applies to the entries a capture records. They are listed by
subsystem in the order the design documents number the subsystems, which is not the order in which
the simulation consults them.

## Identity

Every unit word belongs to a roster row. A row names the charter the word serves, the tick at which
the word opened, the tick at which it closed, and the word that succeeds it.

A row whose successor column names the row itself is a cycle, and that question is settled before
any other. A unit standing in a cycle is held at its opening charter and its entries settle under
that charter.

A closing tick of zero means the word never closed, and such a word is in force for every entry that
names it.

A word that carries a closing tick is in force for an entry when the entry tick does not stand past
that closing tick. The opening tick sizes the charter baseline and takes no part in this question,
so an entry whose tick falls before the opening tick still settles under the word it names.

When an entry tick stands past the closing tick of the word the entry names, the entry belongs to
the successor of that word, and the same question is asked again of the successor.

A word whose successor column is empty and whose closing tick the entry tick stands past is retired.
An entry that reaches a retired word leaves the simulation.

A word whose successor serves a different charter is a merge. An entry that passes through a merge
serves the charter of the successor.

## Windows

The tick schedule divides the match into windows. A window names its first tick, its last tick and
whether it is live.

An entry survives the window filter when its tick lies inside a live window.

The identity question is asked before the window filter, so an entry that reaches a retired word
counts as retired even when no live window admits it.

A window whose first tick exceeds its last tick is degenerate and admits no entry.

The first tick of every live window renews each charter allowance to its full size before any entry
at that tick draws. A degenerate window renews nothing.

## Charters

Each charter carries a baseline. Each charter also draws a transfer from every other charter, and
the size of that transfer is fixed by the settled flow of kind one entries running between the two
charters.

The stock a charter holds is its baseline together with everything it draws from the other charters.
Because every charter gives away strictly less than it holds, a unique stable assignment of stocks
exists.

A charter with no surviving unit contributes its baseline to the system and draws nothing.

A settled entry draws its amount on the allowance of the charter it serves, and the part it cannot
draw is surplus, counted into the reconciliation residual rather than discarded.

## Cadence

Every surviving unit carries a settled tick total, which is the sum of the ticks of the entries that
settled under it.

A unit's cadence class is its settled tick total divided by the cadence modulus and then taken
against four. The four cadence classes are peak, steady, burst and latency, in that index order.

## Upkeep

The upkeep target is the sum of the charter baselines multiplied by the upkeep target scale.

Exactly one set drawn from the bench candidates carries a settled upkeep that meets the target
exactly. A unit's settled upkeep is its settled amount total.

## Reconciliation

Every amount a capture decodes is settled, dropped, held as surplus beyond an allowance, or carried
by a cancelled entry or the reversal that cancels it. The reconciliation residual is what remains
once the settled amounts and the dropped amounts are taken away from the decoded amounts.

## Reversals

A reversal entry names a kind in its mark field.

A reversal entry cancels the earliest still uncancelled entry of the same kind recorded by that unit,
not the latest one, and when no uncancelled entry of that kind remains the reversal itself counts as
an entry of that kind.

A reversal is matched against the entries of the canonical unit the reversal resolves to, not against
the entries of the word the reversal names on the wire.

Reversal matching walks a unit's surviving entries by tick, then by capture ordinal, then by the
ordinal the entry holds inside its capture.

A cancelled entry, and the reversal that cancels it, contribute nothing to any settled total. A
reversal that cancels nothing contributes as an ordinary entry of the kind its mark names.

Counting the reversals that cancelled nothing is how a run learns whether it read the cancellation
order the engine uses.
