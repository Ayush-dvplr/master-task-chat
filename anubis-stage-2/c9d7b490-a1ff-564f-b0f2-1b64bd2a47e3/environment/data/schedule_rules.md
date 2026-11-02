# Schedule rules

## Instalments

A lease of `term_months` months has that many instalments, numbered from 1,
each of `instalment` dollars. Instalment `k` has a nominal due date in the
month `k` months after the month of `start_date`, on `anchor_day`, or on the
last day of that month when it is shorter. Its due date is the nominal due
date rolled to a business day (`calendar_rules.md`).

A governing payment holiday of `months` months moves every instalment from
`first_deferred_instalment` onward to a nominal due date `months` months later
than it had without the holiday, and the moved instalment is then rolled like
any other. How the anchor day applies to a moved instalment follows the
notices: `invoice_notices.csv` holds every notice issued through
`notices_through`, including the reissued notices of deferred instalments, and
exactly one way of applying the anchor reproduces every one of them.

The schedule of a lease at an instant uses the holiday in force at that
instant. A lease's deferral span, at an instant, runs from the due date its
first deferred instalment has without the holiday up to but not including the
due date that instalment has with it.

## Days past due

The paid amount of a lease on a day, as known at an instant, is the sum of the
credited amounts of its payments known at the instant whose value dates are
on or before the day (`cash_rules.md`). Payments are applied to the oldest
instalments first and never to a particular instalment.

An instalment `k` is outstanding on a day when its due date is before the day
and `k * instalment` exceeds the paid amount on that day by more than the
tolerance of the lease's contract segment (`servicing_policy.ini`, in cents).
The days past due of a lease on a day is the number of days from the due date
of its oldest outstanding instalment to the day, or 0 when no instalment is
outstanding. A shortfall within the tolerance carries forward: it is compared
again, together with every later shortfall, on every later day.
