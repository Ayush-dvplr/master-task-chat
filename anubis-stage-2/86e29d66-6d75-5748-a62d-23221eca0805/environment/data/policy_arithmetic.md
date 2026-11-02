# Arithmetic policy

Every number that enters or leaves a report is an integer. No report may contain a
floating point literal, a quoted number or a null in a numeric field. Rates and loss
metrics are already expressed in milli units in the archive and stay in milli units in
the reports; they are never converted to a unit scale.

## The division operation

One operation performs every division in this run book. It is written here as
`ratio(numerator, denominator)`.

* When the denominator is zero the result is 0, and one `zero_denominator` event is
  counted for the profile being audited. The run continues with the 0.
* Otherwise take the quotient and remainder of the two non negative integers and round
  half to even: if twice the remainder exceeds the denominator, add one to the
  quotient; if twice the remainder is below the denominator, keep the quotient; if
  twice the remainder equals the denominator exactly, keep the quotient when it is
  even and add one when it is odd.

Worked examples. `ratio(7, 2)` is 4 because twice the remainder equals the denominator
and the quotient 3 is odd. `ratio(5, 2)` is 2 because twice the remainder equals the
denominator and the quotient 2 is even. `ratio(2667, 100)` is 27 because twice the
remainder 67 exceeds 100. `ratio(2637, 100)` is 26 because twice the remainder 37 is
below 100. `ratio(14, 0)` is 0 and raises one zero denominator event.

## Percent scaling

`percent(value, pct)` is `ratio(value * pct, 100)`. The multiplication happens first and
in full integer precision. Two percent operations applied one after another are two
separate roundings and the order is set by the precedence policy.

## Mean

`mean(values)` is `ratio(sum(values), count(values))`. An empty list of values has
denominator zero, so the mean is 0 and one zero denominator event is counted.

## The rate curve

For optimizer step index `k`, counting from 1, the base rate in milli units is built
from the schedule base document alone, then scaled by the precedence policy.

* When `k` is less than or equal to `warmup_steps`, the base rate is
  `ratio(peak_rate_milli * k, warmup_steps)`.
* Otherwise let `elapsed` be `k - warmup_steps`. When `restart_period_steps` is greater
  than zero, replace `elapsed` with `((elapsed - 1) mod restart_period_steps) + 1`, which
  makes the curve saw toothed: the step right after a period boundary starts the decay
  again at 1. When `restart_period_steps` is zero or less, `elapsed` stands as it is.
* Let `travelled` be the smaller of `elapsed` and the resolved decay span. The base rate
  is `peak_rate_milli - ratio((peak_rate_milli - floor_rate_milli) * travelled, span)`.

Two boundaries are exact and must be reproduced exactly. At `k` equal to
`warmup_steps`, the base rate equals `peak_rate_milli`. At `travelled` equal to the
decay span, the base rate equals `floor_rate_milli`, with no residue from rounding.

Worked example with peak 3200, floor 400, warmup 6, decay span 18 and period 15. Step 1
gives `ratio(3200, 6)` which is 533. Step 6 gives 3200. Step 7 has elapsed 1, travelled
1, so the rate is `3200 - ratio(2800, 18)` which is `3200 - 156` and equals 3044. Step 21
has elapsed 15, travelled 15, so the rate is `3200 - ratio(42000, 18)` which is
`3200 - 2333` and equals 867. Step 22 has elapsed 16, and because the period is 15 the
elapsed value folds back to 1, so the rate returns to 3044.

## Counting rules

* `logged_steps` is the integer quotient of the final optimizer step index divided by
  `log_every_steps`, with no rounding. A `log_every_steps` of zero or less yields 0 and
  one zero denominator event.
* `coverage_gap` is `planned_examples - accepted_examples` and may be negative. It is
  reported with its sign.
* Every delta in the cross profile report is the profile value minus the visible value
  and is reported with its sign.
