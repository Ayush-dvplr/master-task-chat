# Deferral policy

Any open request may be deferred to next season instead of being scheduled. A deferred request adds
the `deferral_penalty` of its class to the first term and counts as moved. Its reason is `no_slot`
when the check cannot finish by season end at any compression on a line with no other check, and
`plan_trade` otherwise.

The line with no other check in that sentence is the request's own base line with its closed days
and no-start days, and the check still starts on or after its available day.
