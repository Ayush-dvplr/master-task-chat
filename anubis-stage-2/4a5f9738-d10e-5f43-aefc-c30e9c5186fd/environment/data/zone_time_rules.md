# Zone clock rules

Each zone keeps a standard offset from universal time. Three zones also keep a
summer offset during an annual window. The window bounds below are wall clock
stamps without a zone marker, so the register publishes them twice a year and
they are not by themselves universal time. Whether a published window bound is
read as a local standard wall clock reading or as a universal time reading is
the same for every zone and for every window bound, and it is settled by
`zone_clock_marks.csv`, which pairs local readings with universal readings.
Only rows whose jurisdiction is `register` are authoritative; rows from the
neighbouring administration are liaison material and bind nothing.

| zone | standard_offset_sec | summer_offset_sec | summer_from | summer_to |
| --- | --- | --- | --- | --- |
| North | 3600 | 7200 | 2031-03-30T01:00 | 2031-10-26T01:00 |
| South | -10800 | -10800 | none | none |
| West | 19800 | 23400 | 2031-03-09T02:00 | 2031-11-02T02:00 |
| East | 28800 | 32400 | 2031-04-06T02:00 | 2031-09-28T02:00 |

A zone whose window bounds read `none` keeps its standard offset all year.
Inside the summer window the summer offset applies, lower bound inclusive and
upper bound exclusive, measured on universal time once the window has been
placed on universal time. A local reading that falls in the gap created by a
forward step, or in the overlap created by a backward step, is read with the
standard offset.
