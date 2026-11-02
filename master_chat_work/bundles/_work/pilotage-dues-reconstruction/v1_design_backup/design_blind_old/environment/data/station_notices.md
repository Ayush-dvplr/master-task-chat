# Station Notices

## Tariff notices

| station | notice_date | coefficients |
|---|---|---|
| North | 2026-08-17 | base_per_100gt, draft_per_dm, night_factor, per_tug |

## Station fees

| station | call_out_fee | minimum_due |
|---|---|---|
| North | 77.00 | 27.00 |
| South | 82.00 | 40.00 |
| West | 65.50 | 38.00 |
| East | 70.50 | 32.00 |

A cancelled booking's due is the call_out_fee of its station, with no other line; the
minimum_due does not apply to it. The due of a commercial visit is never below the minimum_due
of its station; a lower due is raised to the minimum_due. Example on invented values: with a
call_out_fee of 18.00 and a minimum_due of 12.00, a cancelled booking has the due 18.00, and a
commercial visit whose five lines add up to 9.31 has the due 12.00.
