# Overtime policy

A check may be shortened by up to `max_compress_days` of its type; each day taken off uses
`overtime_shifts_per_day` shifts. The values are per check type in `check_types.json`. A check keeps
at least one day on ground, so its compressed days are a whole number from 0 to the smaller of
`max_compress_days` and `duration_days` - 1. The overtime shifts of a check are its compressed days
times `overtime_shifts_per_day`. A deferred request has 0 compressed days and 0 overtime shifts.

The fleet has one overtime pool for the season: the overtime shifts of all compressed checks at all
four bases together may not exceed `overtime_pool_shifts` in planning_limits.docx.
