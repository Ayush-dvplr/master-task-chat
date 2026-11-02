# the damped ration

This document is binding. It defines the only procedure by which an
over subscribed aperture period budget is divided.

## why it is iterative

A single proportional split hands volume to passes that cannot use it,
because a pass never takes more than its own demand. The surplus has to
come back and be offered to the passes that can. The operator settles
this by a fixed number of offer rounds rather than by running to
convergence, so that a settlement run has a bounded cost and two runs
of the same month agree to the unit.

## the pass budget

The number of passes is derived from the instance:

    passes = min(ceiling, base + n)

n is the number of accepted rows in the aperture period. base and
ceiling are published in network_operations_memo.pdf as
ration-pass-budget-base and ration-pass-budget-ceiling.

The procedure stops when it has run that many passes. It does not stop
early because the numbers settled, and it does not run on because they
have not. A run that stops at convergence carries on offering after
the published rounds are spent. On most over subscribed aperture
periods it reaches a different allocation, and the residual step masks
the difference on the rest, so a settlement built that way disagrees
with this one and is wrong.

## the state

Each row i carries an allocation x_i, an integer number of KiB, and a
pinned flag. Every x_i starts at zero and every row starts unpinned.

## one pass

For each pass from 1 to the pass budget, in order:

  1. pinned_mass is the sum of the demands of the pinned rows.

  2. the active rows are the rows that are not pinned. When there are
     none, the pass is recorded with an active count of zero and a
     share of zero and nothing changes.

  3. room is the budget less pinned_mass. share is room floor divided
     by the number of active rows, and share is zero when room is zero
     or below.

  4. for each active row i the target is min(demand_i, share), the step
     is target less x_i, and the movement is

         delta = (step * theta_num) // theta_den

     except that when the step is positive and that expression comes
     out below one, the movement is one. A positive step always moves
     the row by at least one unit. Then x_i becomes x_i plus delta.

     theta_num and theta_den are ration_damping_numerator and
     ration_damping_denominator in unit_scaling_rules.json.

     The minimum of one unit is what lets a row reach its demand at
     all. Without it the damped step floors to zero as soon as the gap
     falls below theta_den over theta_num, the row stalls one unit
     short of its target, the pinning that would have raised the share
     for the later passes mostly stops happening, and the surplus of
     the rows that could not use their share reaches the rows that
     could through the residual instead. A procedure without it
     reaches a different allocation and is wrong.

  5. after every active row has moved, any active row whose x_i has
     reached or passed its demand is set to its demand exactly and
     pinned.

Every x_i is an integer at the end of every pass. The next pass starts
from those integers. There is no unrounded shadow value carried between
passes.

## why the share never falls

A row is pinned only when its demand is at or below the share it was
offered, so removing it from the active set removes at most a share
worth of room. The share of the next pass is therefore at or above the
share of this one. The step is consequently never negative, the
movement is never negative, and the sum of the allocations never
exceeds the budget.

## the residual

After the last pass, residual is the budget less the sum of the x_i,
and by the paragraph above it is at or above zero.

Walk the rows in the S07 ordering and give each row
min(residual, demand_i - x_i), stopping when the residual reaches zero.
A row already at its demand takes nothing. When the residual is zero at
the outset, nothing happens.

## the trace

One row per pass per aperture period that ran the procedure, carrying
pass_seq, active_count, share_kib, the sum of the x_i after the pass as
allocated_kib, the budget and the demand total. The residual step is
not a pass and is not traced.

## worked example

Four rows with demands 500, 500, 100 and 40, a budget of 700, theta 3
over 4, base 2 and ceiling 12, so the pass budget is 6.

    pass 1  pinned_mass   0  active 4  share 175
            targets 175 175 100  40
            x       131 131  75  30
    pass 2  pinned_mass   0  active 4  share 175
            targets 175 175 100  40
            x       164 164  93  37
    pass 3  pinned_mass   0  active 4  share 175
            x       172 172  98  39
    pass 4  pinned_mass   0  active 4  share 175
            steps     3   3   2   1, movements 2 2 1 1
            x       174 174  99  40   row four reaches 40 and pins
    pass 5  pinned_mass  40  active 3  share 220
            targets 220 220 100
            x       208 208 100        row three reaches 100 and pins
    pass 6  pinned_mass 140  active 2  share 280
            targets 280 280
            x       262 262
    residual 700 less 664 is 36
            row one takes min(36, 238) which is 36, residual 0
    allocation 298 262 100 40

Pass four is the one that separates a correct procedure from a
plausible one. Row four has a step of one, the damped expression gives
zero, the minimum of one unit carries it to its demand of 40, and the
pinning that follows raises the share for every later pass.

The example is arithmetic on invented numbers and is not a row of any
shipped file. Reproduce it before running the pipeline; a procedure that
reproduces it reproduces the settlement.
