# Reservation policy

`guard_windows_<zone>.csv` carries the radio astronomy reservations of the
zone. A row whose status is not `active` is ignored. A reservation occurs on
every local date in the half open range from `valid_from` to `valid_to` that
matches the recurrence token.

| recurrence token | occurs on |
| --- | --- |
| daily | every local date in range |
| weekly:N | every local date in range whose iso weekday is N |
| monthly:N | every local date in range whose day of month is N |

A `monthly:N` token produces no occurrence in a month that has no day N. An
occurrence begins at the local start time of the matching local date and runs
for `duration_min` minutes of elapsed time, so only the start needs a clock
conversion. An occurrence is trimmed to the horizon.

`guard_exceptions.csv` adjusts occurrences. A row of kind `cancel` removes the
occurrence of that rule on that local date. A row of kind `add` creates one
occurrence of that rule on that local date with the local start and duration
given on the exception row. Cancellations are applied before additions.

Reserved spectrum is subtracted from every grant of the zone, in the frequency
span of the rule and in the time span of the occurrence. Subtraction happens
after the channel trim, the horizon trim and the state intervals, and before
any clipping to a parent grant. The subtracted measure of a zone is the union
measure of the zone before subtraction less the union measure after it.
