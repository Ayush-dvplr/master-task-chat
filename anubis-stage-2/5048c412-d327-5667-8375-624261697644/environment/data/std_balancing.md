# Basin storage balancing standard

At the end of each season the authority balances the storage of every closed basin so that each reservoir holds a storage that agrees with the season's canal gaugings. Balancing works on each basin separately and moves water between reservoirs of the same basin only, through the basin's canals, so a basin's storage total never changes. Each section below defines one part of balancing; balancing of a basin is complete when one of its four exits (balanced, stalled, cycle, budget) is reached, and the exit decides what the basin reports.

## Balanced and stalled

A basin is balanced at the first round whose basin residual is zero. Balancing then ends with the exit `balanced`, before any transfer of that round is formed; the basin reports the index of that round as its round count and the state that round started from as its balanced storages.

A basin stalls in a round whose yield is zero for every reservoir. Balancing then ends with the exit `stalled`; the basin reports the index of that round as its round count and the state that round started from as its balanced storages.

## Budget

Each basin has a round budget (`round_budget` in its row of the basin operating parameters table). When the number of rounds a basin has run reaches its budget and none of the other three exits has been reached, balancing of the basin ends with the exit `budget`; the basin reports the number of rounds it ran as its round count, and the state the last round left as its balanced storages. A round past the budget never starts, so a basin whose last allowed round leaves a state that would be balanced still ends with the exit `budget`.

## Closure

Because the basin is closed, the transfers of a round must sum to zero. When they do not, their whole sum is taken off the transfer of the reservoir furthest from its target, and at the end of the round every reservoir's storage moves by its transfer as the closure leaves it.

## Cycle

After a round's storages have moved, the state they produce is compared with every state the basin has held during balancing, its opening state included. When it equals one of them, balancing of the basin ends with the exit `cycle`. The cycle begins at the first sighting of the repeated state and runs through the state the round started from. The basin reports the lowest state of the cycle as its balanced storages and -1 as its round count. Two states are compared as the lists of their storages read in register order: the first position at which the lists differ decides, and the list with the smaller storage there is the lower state. A round whose state repeats an earlier one ends balancing as a cycle even when it is the last round the budget allows.

## Damping

A basin begins balancing with the damping percentage of its row of the basin operating parameters table (`damping_percent`). Each time the basin's patience tally reaches the basin's patience (`patience`), the damping is halved, the half rounded down to a whole percent, and the tally returns to zero. A basin reports the damping it holds when its balancing ended.

## Patience

A basin's patience tally is the tally of its slack rounds.

## Residual

A reservoir's residual in a round is the reservoir's target minus the storage the reservoir holds at the start of the round. The basin residual of a round is the sum of the absolute values of the residuals of all reservoirs of the basin.

## Rounds

Balancing of a basin runs in rounds, counted from zero: the first round is round 0, the next round 1, and so on. Round 0 starts from the opening state; every later round starts from the state the round before it left. A round's index is its number in this count.

## State

The state of a basin is the storage each of its reservoirs holds, in megalitres. The opening state comes from `dict_register.md` (Opening storage).

## Target

A reservoir's target in a round is the rounded mean of the storages its partners hold at the start of that round, plus the head offset that the `offset` sheet of `tab_h3.xlsx` gives for the reservoir's draw share. The draw share is the reservoir's draw points over its net gaugings divided by the number of those gaugings, rounded to hundredths (`dict_gaugings.md`). A reservoir with no net gauging has the storage it holds as its target.

## Transfer

A reservoir's transfer in a round is the reservoir's residual multiplied by the standing damping percentage of the round and divided by 100, rounded to whole megalitres. Transfers are signed: a positive transfer raises the reservoir's storage.
