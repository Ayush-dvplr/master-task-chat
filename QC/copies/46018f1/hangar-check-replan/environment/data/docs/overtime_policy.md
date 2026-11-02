# Overtime policy

A check may be shortened by up to `max_compress_days` of its type; each day taken off uses
`overtime_shifts_per_day` shifts. The values are per check type in `check_types.json`. A check keeps
at least one day on ground, so its compressed days are a whole number from 0 to the smaller of
`max_compress_days` and `duration_days` - 1. The overtime shifts of a check are its compressed days
times `overtime_shifts_per_day`. A deferred request has 0 compressed days and 0 overtime shifts.

The fleet has one overtime pool for the season: the overtime shifts of all compressed checks at all
four bases together may not exceed `overtime_pool_shifts` in planning_limits.docx.

## Overtime allowance

The table `base | allowance_shifts` in planning_limits.docx grants overtime shifts to each base. The
four grants together form one fleet overtime allowance for the season. After the season plan is
fixed, the fleet allowance pays for overtime one scheduled check at a time in this order: aircraft
class widebody, then narrowbody, then regional; within a class the earlier `due_date` first; on the
same due date the smaller `request_id` first. Each check takes the smaller of its overtime shifts
and the allowance still left, whichever base it is at.

For each check, `allowance_shifts` is what it takes from the allowance and `paid_shifts` is the rest
of its overtime shifts. `overtime_cost` is `shift_cost` times its overtime shifts, `allowance_credit`
is `shift_cost` times its allowance shifts, and `settled_overtime_cost` is `overtime_cost` minus
`allowance_credit`. A deferred request has 0 in all five fields.

The settlement is a report on the fixed plan. The second term in `planning_policy.md` counts
`overtime_cost`, and the allowance never changes which plan is optimal.
