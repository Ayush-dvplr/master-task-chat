# Label rules

Labels are judged with everything known at the watermark: the lease events,
schedule, holidays and payments known then, whatever was known at the
snapshot.

The performance window of an observation is the `performance_days` days after
its as of date; the window end is the as of date plus `performance_days`
days. An observation whose window end is after `data_cutoff` is `immature`,
whatever else holds.

Otherwise the label is `bad` when the lease has a charge off effective on or
before the window end, or when its days past due reach `bad_dpd` on some day
of the window. When the lease closes (`BUYOUT` or `PAYOFF`) on or before the
window end, only the window days up to and including the closing date count
for days past due. A lease that is not `bad` and closes on or before the
window end is `indeterminate`. Every other observation is `good`.

`bad`, `good`, `indeterminate` and `immature` are the only labels.
