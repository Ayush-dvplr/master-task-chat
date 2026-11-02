# T08 residual dispersion and raw weight

## Input

The predictions of T07, weighting_policy.yaml and the class ceiling weights
from the live sheet of timing_network_workbook.xlsx.

## Residuals

For an included oscillator, at every valid epoch of its history window,

    residual = archived deviation - predicted deviation at that epoch

using the exact frequency of T07. The residual at the anchor epoch is zero and
it counts.

## Dispersion

The dispersion of an oscillator is the mean of the absolute values of its
window residuals, rounded to a whole number of picoseconds by the rounding
rule. This is the first of the two places in the chain where a rounded value is
carried forward rather than only written, the other being the grid placement of
every capping pass of stage T09, and it is deliberate: the desk publishes the
dispersion as a whole picosecond and forms the weight from the number it
published, so a reader of the published table can reproduce the weight from
it.

## Raw weight

    raw weight = weight_scale / published dispersion

when the published dispersion is not zero, and the weight source is
WS_DISPERSION.

A prediction can reproduce a window exactly, and then the published dispersion
is zero. Such an oscillator is not dropped and its weight is not unbounded. It
takes the ceiling weight of its class from the live workbook sheet, and the
weight source is WS_CLASS_CEILING.

## Output

For every included oscillator: its valid count, its published dispersion, its
weight source and its raw weight.
