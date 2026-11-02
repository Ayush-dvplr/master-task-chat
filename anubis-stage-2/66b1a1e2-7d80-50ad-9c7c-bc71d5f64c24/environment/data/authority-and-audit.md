# Lower authority sources, the authority audit and the drift report

## The authority order

The governance schedule (PDF) is the only authority for settling parameters,
class ranks and conversion rates. The in force sheets of the office register
(XLSX) are the only authority for offices, longitudes, weekday rows and
attendee rates. The zone file is the only authority for transitions. Every
other copy of those figures in the store is of lower authority and is never
read for a computation, however current it looks:

| Role | What it holds |
|---|---|
| escalation_draft | a YAML digest circulated with a draft revision: `settling` (buffer_minutes, quantum_minutes, round_cap, pin_rank, default_rank), `class_ranks` and `conversion_bps` |
| office_snapshot | a comma separated capture of a register edition: code, tzid, longitude, weekday, open_minute, close_minute, captured |
| payroll_export | a semicolon separated export of attendee rates: attendee, cents_per_hour, exported |
| zone_cache | transitions cached by the retired scheduler, tab separated: tzid, onset_utc, from_minutes, to_minutes |

The authority audit compares each lower authority figure with the figure in
force, so these files are read for the audit and for nothing else.

## Audit rows

Each row holds a subject, a key, the value in force, the lower source, the
lower value (empty when the lower source has none) and whether the two strings
are equal. The lower source is written as the role name the index gives it:
`escalation_draft`, `office_snapshot`, `payroll_export` or `zone_cache`. Values
are written as plain decimal integers or as the strings described below.

| Subject | Keys | Value in force | Lower source |
|---|---|---|---|
| settling-parameter | buffer_minutes, quantum_minutes, round_cap, pin_rank, default_rank | the settling parameters in force | escalation_draft `settling` |
| class-rank | every class listed by the class rank table or by the draft | the escalation rank (the default rank for a class with no usable row) | escalation_draft `class_ranks` |
| conversion-bps | every office listed by the conversion table or by the draft | the basis points in force, empty for an office with no usable row | escalation_draft `conversion_bps` |
| office-longitude | every office of the register | the longitude string in force | the office_snapshot row of that office for `MO` |
| office-window | `CODE:WD` for every office and weekday | `open-close` from the row in force on the first date of the store window that falls on that weekday | `open_minute-close_minute` of the office_snapshot row |
| attendee-rate | every registered attendee and every attendee of the export | the rate in force on the window start date, 0 when none is | payroll_export |
| zone-transitions | every zone of the zone file | the transitions in the window, each `onset_utc/from/to`, joined with `;` | the zone_cache rows of that zone whose onset lies in the window, in the same form, sorted, joined with `;` |

Rows are ordered by subject in the order of the table above, then by key.

## The drift report

The retired scheduler printed one occurrence count per series; the file named
by the index (role `previous_run`) lists them under `series_summary`. They were
computed under v3 rules and many of them are wrong under v5. The drift report
has one row for every series that file lists and for every collection and UID
that holds at least one merged component and is not a shadow, with the v3 count
(empty when the series is not listed), the v5 count, which is the number of
occurrences of the series in the occurrence report, and the difference v5 minus
v3 (empty when the v3 count is empty). Rows are ordered by collection and then
UID.
