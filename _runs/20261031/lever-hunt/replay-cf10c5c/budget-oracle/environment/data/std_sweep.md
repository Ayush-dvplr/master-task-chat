# Month-end envelope sweep

The sweep runs once for each household after the ledger has closed (std_ledger.md). It moves whole dollars between the envelopes of one household and never between households. The parameter sheet (cfg_reference.md) gives each household its starting damping rate, its patience and its round budget. One misread rule of the sweep shows up in many figures of many reports, because every sweep figure feeds the household, segment, category and table reports.

## Rounds and state

The sweep of a household goes in rounds. A round starts from the standing balances of the household's envelopes. A round that runs to its end leaves each envelope holding its standing balance plus its posted amount. Before the opening round every envelope holds its pre-sweep balance.

## Targets

An envelope's shortfall is the amount by which its need exceeds its standing balance. Its claim is its need plus its shortfall. Its target is the household's pool times its claim, divided by the sum of the claims of all the household's envelopes, rounded. Its gap is its target less its standing balance, and the spread of the round is the sum of the absolute gaps of the household's envelopes.

## Settled

A household whose spread is zero at the start of a round is settled. Its sweep ends there, and that round is not run.

## Draft and posting

Each envelope's draft amount is its gap times the damping rate, divided by one hundred, rounded. The posted amounts equal the draft amounts, except that when the draft amounts do not add up to zero, the balancing adjustment subtracts their total from the posted amount of the envelope with the largest absolute gap. Among envelopes with equally large absolute gaps, the first of them takes the adjustment. The posted amounts of a round therefore add up to zero, and the pool keeps its value.

## Stalled

A household stalls in a round whose transfer is all zero. Its sweep ends in that round before anything is posted, the round counts among the rounds run, and the household keeps the standing balances of that round. A stalled household is never also cycling.

## Strikes and damping

A worsening round is a strike. When the strike count reaches the household's patience, the damping rate is halved, any fraction of a percent being dropped, and the strike count goes back to zero.

## Cycling

When a round leaves the household in a state it has held before, the household is cycling. Its sweep ends in that round, the round counts among the rounds run, and the household's final balances are the lowest state on its record in place of the balances it holds.

## Round budget

A household that comes to the end of a round having run as many rounds as its round budget, without settling, stalling or cycling, ends on the budget exit and keeps the balances it then holds; no further round is started, so no settlement test follows that round.

## What the sweep reports

The exit of a household is one of settled, stalled, cycling and budget. Its rounds figure is the number of rounds it ran. Its damping figure is the damping rate it holds when its sweep ends. An envelope's final balance is the balance the household keeps at its exit. A household's moved dollars are the sum, over its envelopes, of the amount by which the final balance exceeds the pre-sweep balance, counting zero for an envelope whose final balance does not exceed it.
