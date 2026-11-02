# T07 frequency prediction

## Input

prior_interval_deviations.psv, weighting_policy.yaml, the history minimum from
network_calibration_memo.pdf, oscillator_catalogue.csv and the components of
T04.

## The history window

The archive holds twenty four epochs of the previous interval, numbered 1 to
24. The history window is the last history_window_epochs of them, so it runs
from 24 - history_window_epochs + 1 to 24 inclusive.

An archived deviation counts as valid only when its quality_flag equals
valid_archive_flag. Any other flag is not a measurement and takes no part in
anything below.

## Exclusions

An oscillator is excluded from the ensemble for the first of these that
applies, in this order:

    EX_DECOMMISSIONED    oscillator_catalogue.csv gives it status
                         OS_DECOMMISSIONED
    EX_NO_ARCHIVE        the archive holds no row for it at all
    EX_SHORT_HISTORY     the number of valid deviations in its history window
                         is below the history minimum the memo publishes
    EX_UNANCHORED_NODE   its node is in an unanchored component

An oscillator carrying exactly the history minimum is not excluded. The
comparison is strict.

## The frequency

The prediction is a straight line through the first and the last valid
deviation of the history window. It is not a least squares fit, and no
intermediate point moves it.

    frequency = slope in parts in ten to the eighteenth of the line through
                (first valid window epoch, its deviation) and
                (last valid window epoch, its deviation)

with one grid step at one part in ten to the eighteenth being exactly 864 ten
thousandths of a picosecond. The anchor of the prediction is the last valid
deviation of the window and the epoch it was taken at.

The frequency is carried as an exact rational. The whole number written into
the prediction book is a rendering of it and is never the value the following
stages use.

## Predicted deviation

The prediction of an oscillator at an archived epoch n is

    anchor_deviation + phase(frequency, n - anchor_epoch)

and at grid epoch k of this interval it is

    anchor_deviation + phase(frequency, 24 + k - anchor_epoch)

## Output

For every catalogued oscillator: the window bounds, the number of valid
deviations in it, whether it is included, the exclusion reason when it is not,
and for an included oscillator the anchor and the frequency.
