# Planning policy

## Season days and lines

Season day 1 is `season_start` and the last season day is `season_end`. Each base has one heavy
check line, and the line works on one check at a time. A check uses every day from its start day to
its finish day on its own base's line. The next check on that line may start on the day after the
previous finish day at the earliest.

Every open request is either scheduled in this season or deferred (see `deferral_policy.md`).
A scheduled check:

- starts on or after its available day;
- starts on a day that is neither a closed day nor a no-start day of its base;
- has no closed day of its base anywhere from its start day to its finish day (no-start days in
  between are working days);
- finishes on or before the last season day.

A check with `duration_days` p and c compressed days (see `overtime_policy.md`) has finish day
equal to start day + p - c - 1. Its days on ground are p - c.

## Cost of a plan

- Overdue days of a scheduled check: finish day minus `due_date`, or 0 when it finishes on or
  before its due date.
- First term: the sum over scheduled checks of overdue days times the `overdue_weight` of the
  check's class, plus the `deferral_penalty` of the class of every deferred request.
- Second term: the sum over scheduled checks of days on ground times the `revenue_per_day` of the
  class, plus `shift_cost` times the overtime shifts of all compressed checks.
- Third term: the number of moved requests. A request is moved when it is scheduled with a start
  day other than its `published_start` in `published_plan.csv`, or when it is deferred.

## Comparing plans

Plans are compared on the first term, then the second term, then the third term; the smaller value
at the first term that differs wins. When plans tie on all three terms, compare the list of start
days of every request in request_id order (a deferred request counts as the day after season end),
followed by the list of finish days in the same order; the smaller list at the first difference wins.

The season plan is the plan that wins this comparison among all plans that keep every rule in these
documents. Request ids are compared as plain text.
