# T09 weight capping

## Input

The raw weights of T08, capping_policy.yaml, the oscillator cap and the sweep
budget from network_calibration_memo.pdf, and the node weight cap from the
live workbook sheet.

## The two caps

Let W be the sum of the raw weights of the included oscillators. W is computed
once, from the raw weights, and does not move afterwards.

    oscillator cap = OSC_WEIGHT_CAP_NUMERATOR / OSC_WEIGHT_CAP_DENOMINATOR * W
    node cap       = NODE_WEIGHT_CAP numerator / denominator * W

Both caps are absolute weights, fixed for the interval by W.

## Redistribution

Capping is mass preserving. The weight a capped holder gives up is handed to
the holders that are still below the cap, in proportion to the weight each of
them already holds. It is never discarded. The sum of the weight vector after
a pass equals the sum before it, and it equals it exactly: the placement of the
vector on the published grid is closed onto one holder so that the grid costs
the vector none of its mass. The passes below say which holder.

## The three passes, in this order

The order of the passes changes the answer, and this is the order.

**The published weight grid.** Every weight the capping works on sits on the
grid weight_places decimal places give. The raw weight of stage T08 is placed
on that grid before the first pass, and every pass leaves the vector on it. The
raw weight the weight book publishes is the T08 formula as it stands; the value
the capping starts from is that weight placed on the grid.

**First pass, the oscillator cap. A damped fixed point, not a solve.** An
oscillator is an offender when its weight is strictly above the cap; one
sitting exactly on the cap is not an offender and takes a share of the excess
like any other holder. One pass works out where a full step would put the
vector: every offender sits exactly on the cap, the total excess is collected,
and it is handed to the oscillators at or below the cap in proportion to the
weight they hold. The desk does not take that step. It moves the whole vector a
fraction of the way toward that target,

    new weight = weight + damping * (target - weight)

with damping the ratio damping_numerator over damping_denominator that
weighting_policy.yaml publishes, applied to every oscillator and not only to
the offenders. The result is then placed back on the published grid, rounding half to even
at weight_places decimal places as the rounding policy states, and the next
pass starts from the placed vector. This is a carried rounding, the second and last
in the chain after the published dispersion of stage T08, and it is what makes
the passes depend on one another.

**Placement is mass preserving too.** Placing each weight on the grid on its
own moves the total: half to even sends some weights up and some down and the
two do not cancel. The desk does not publish a weight vector whose total has
drifted away from the total the pass started with, so the pass closes that
difference rather than leaving it. Take the total of the vector before the
pass, take the total of the placed vector, and hand the whole of the difference
to one holder,

    residue = the total before the pass minus the total of the placed vector

and that holder takes its placed weight plus the residue. The holder is not
the same one every pass. Closing the residue onto the greatest receiver every
time walks that one holder's published weight away from the vector the passes
produced, so the desk hands the carry to the receiving holder that has carried
it the fewest times so far in this interval, a tie going to the greatest weight
after placement and then to the lexicographically smallest oscillator
identifier. The count opens at zero for the interval and runs across every pass
of all three phases, so which holder closes a pass depends on what the passes
before it did, and a pass cannot be worked out from the vector it starts from
alone. An offender never carries the residue. Both totals are whole numbers
of grid units, so the residue is one too and the vector stays on the grid. The
pass therefore preserves the total exactly, which is what lets the sum of the
published weight vector be compared with the total the two caps were taken
from.

This matters, and it is why the pass is written out rather than solved. The map
this pass iterates has a fixed point with a closed form, in which every
over-cap oscillator sits at the cap and every other one is scaled by a single
common factor. That fixed point is not what the desk publishes. What it
publishes is the vector after the passes the budget allows, damped and placed
on the grid at the end of each one, which no closed form gives.

Pass again. Stop when no oscillator is above the cap, and record SW_SETTLED.
Stop when the number of passes already run equals CAP_SWEEP_BUDGET and an
oscillator is still above the cap, and record SW_BUDGET_EXHAUSTED, publishing
the vector as the budget left it. Stop when every oscillator is above the cap,
so that there is nobody to take the excess, and record SW_CAP_UNSATISFIABLE,
publishing the vector unchanged. Redistribution can push a holder over the cap
that was under it before, so the number of offenders can rise from pass to
pass; that is the mechanism working, not a fault.

The residual of a pass is the sum, over every oscillator, of the absolute
difference between its weight after the pass and its weight before it.

The terminal residual the weight book publishes is the residual of the third
pass, which is the last pass of the stage. A pass that finds no offender runs
no sweep and moves nothing, so its residual is zero and the terminal residual
is zero, whatever the passes before it moved.

**Second pass, the node cap.** One pass, not a sweep, and it is not damped: the
node cap is taken in full. Sum the weights of the oscillators at each node.
Every node whose sum is above the node cap has all of its oscillators scaled by
the ratio of the node cap to that sum, so the node sits exactly on its cap. The
excess collected from the offending nodes is handed to the oscillators at the
nodes that were not offending, in proportion to the weight each of them holds
after the first pass. The result is placed back on the published grid, as every
pass does, and the residue of that placement is closed onto one receiving
oscillator under the same carry count the first pass keeps, exactly as the
first pass closes it. The node pass is one of the passes the count runs over. When every node is above the node cap the pass records
SW_CAP_UNSATISFIABLE and changes nothing.

**Third pass, one further oscillator sweep.** Exactly one damped pass of the
oscillator cap, run over the vector the node cap produced, with the same cap
value, the same damping and the same grid. One pass, whatever the budget says,
and no node cap pass follows it.

## Output

The raw weight, the weight after the first pass, the weight after the second
pass and the final weight of every included oscillator, the two cap values, the
outcome of each pass, the terminal residual, the damping and the grid, and one
trace record per pass naming the phase PH_OSC_CAP, PH_NODE_CAP or
PH_FINAL_SWEEP, the offenders it acted on, the excess it moved, the number of
holders that took it and the residual of that pass.
