# Settlement calendar

The settlement day is the unit of partitioning. A settlement day opens at
`06:00:00Z` and runs for twenty four hours, and the interval is half open, so
the instant at which a day opens belongs to that day and the instant at which it
closes belongs to the next one.

The settlement day of an event is the day whose half open window contains the
effective instant of that event. The day is keyed by the calendar date on which
its window opens, written as eight digits with no separator.

The calendar for this materialization holds exactly these eight days and no
others:

```
20310308  opens 2031-03-08T06:00:00Z
20310309  opens 2031-03-09T06:00:00Z
20310310  opens 2031-03-10T06:00:00Z
20310311  opens 2031-03-11T06:00:00Z
20310312  opens 2031-03-12T06:00:00Z
20310313  opens 2031-03-13T06:00:00Z
20310314  opens 2031-03-14T06:00:00Z
20310315  opens 2031-03-15T06:00:00Z
```

The window of `20310315` closes at `2031-03-16T06:00:00Z`. An instant that falls
outside the union of these eight windows is outside the calendar.

The date portion of an instant is not the settlement day of that instant, and
the two disagree for every instant between midnight and the day open. An
instant delivered in the fixed offset form has to be carried to UTC before its
date portion or its settlement day means anything at all.
