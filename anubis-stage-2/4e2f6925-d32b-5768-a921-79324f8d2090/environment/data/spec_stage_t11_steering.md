# T11 steering

## Input

The free scale of T10, steering_policy.yaml and
primary_standard_realisation.csv.

## The departure

At the decision epoch the policy names,

    departure = free scale at the decision epoch
                minus the primary realisation at the decision epoch

The realisation file leaves the value empty at an epoch the primary standard
did not cover. When the decision epoch itself is empty, or when the decision
epoch is void, there is no departure, the step is zero and the outcome is
ST_NO_REALISATION.

## The step

The step is the frequency that would remove the departure over the horizon the
policy names.

    raw step = the frequency, in parts in ten to the eighteenth, whose phase
               over horizon_epochs grid steps equals the negated departure

The step the desk applies sits on the grid the policy names. The raw step is
divided by grid_atto, truncated toward zero, and multiplied back by grid_atto.
Truncation toward zero, not rounding: a raw step whose magnitude is below one
grid unit becomes zero, and the outcome is ST_TRUNCATED_TO_ZERO. Otherwise the
outcome is ST_APPLIED.

## Applying the step

The step is a frequency and its phase accumulates. The first epoch it corrects
is the epoch after the decision epoch. At the decision epoch itself the
correction is zero.

    correction(k) = phase(step, k - decision_epoch)   for k greater than the
                                                      decision epoch
    correction(k) = 0                                 otherwise

    steered scale(k) = free scale(k) + correction(k)

Both terms are exact rationals and the sum is rounded once when it is written.
A void epoch carries its correction and leaves its free scale and its steered
scale empty.

## Output

The steering plan, holding the decision epoch, the horizon, the grid, the
departure, the raw step, the applied step and the outcome; and the steered
scale at every epoch beside the free scale and the correction.
