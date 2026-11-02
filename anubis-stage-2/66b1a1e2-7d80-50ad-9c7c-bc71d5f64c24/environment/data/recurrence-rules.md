# Recurrence expansion

Expansion uses the merged master component of each series and its merged
override components.

Supported `RRULE` parts are `FREQ` with the values `DAILY`, `WEEKLY`, `MONTHLY`
and `YEARLY`, together with `INTERVAL`, `COUNT`, `UNTIL`, `BYMONTH`,
`BYWEEKNO`, `BYYEARDAY`, `BYMONTHDAY`, `BYDAY`, `BYHOUR`, `BYMINUTE`,
`BYSETPOS` and `WKST`.

`INTERVAL` defaults to one. `WKST` defaults to `MO`.

For `DAILY`, each period is one day starting at the `DTSTART` date and advancing
by `INTERVAL` days. The day of a period is kept only when its month is listed by
`BYMONTH`, its day number is listed by `BYMONTHDAY` and its weekday is listed by
`BYDAY`, each test applying only when its part is present; an ordinal on a
`BYDAY` token plays no part in this test.

For `WEEKLY`, each period is a week whose first day is decided by `WKST`. The
period sequence starts at the `WKST` aligned week that contains `DTSTART` and
advances by `INTERVAL` weeks. Inside a period the selected days come from
`BYDAY`, or from the weekday of `DTSTART` when `BYDAY` is absent. `BYMONTH` and
`BYMONTHDAY`, when present, then keep only the days whose month and whose day
number they list.

For `MONTHLY`, each period is a month starting at the `DTSTART` month and
advancing by `INTERVAL` months. When `BYMONTH` is present, a month it does not
list contributes nothing.

For `YEARLY`, each period is a year starting at the `DTSTART` year and advancing
by `INTERVAL` years. When the rule carries neither `BYYEARDAY` nor `BYWEEKNO`,
the months of a yearly period come from `BYMONTH`, or from the month of
`DTSTART` when `BYMONTH` is absent, and each month selects its days as stated
in the next paragraph.

Inside a month, `BYMONTHDAY` selects days by number, where a negative number
counts back from the end of the month. A day number that does not exist in that
month is discarded. It is never clamped to the last day of the month. `BYDAY`
selects days either by ordinal, such as `2FR` or `-1SU`, or by bare weekday,
which selects every matching day of the month. When `BYMONTHDAY` and `BYDAY` are
both present the selection is the intersection of the two sets. Wherever
`BYMONTHDAY` keeps or drops days rather than selecting them, a day matches a
listed number when the number is its day of the month or, for a negative
number, when the day lies that many days back from the end of its own month, so
`-1` matches the last day of every month.

When a yearly rule carries `BYYEARDAY`, each period starts from the days of its
year that the part names: `1` is the first of January, a negative number counts
back from the last day of the year so that `-1` is the thirty first of
December, and a number beyond the length of that year names nothing. When a
yearly rule carries `BYWEEKNO`, each period starts from the days of the weeks
that part names, intersected with the `BYYEARDAY` days when both parts are
present. Weeks are numbered inside the calendar year of the period. Every week
starts on the `WKST` weekday; week 1 is the first such week that has at least
four of its seven days inside the year; the weeks after it are numbered on for
as long as each has at least four of its days inside the year; and a negative
number counts back from the last numbered week, so `-1` is the last of them.
Only days inside the calendar year of the period are ever selected: the days of
week 1 that fall in the previous December, the days of the last numbered week
that fall in the next January, and the days at the start of January that come
before week 1 are never selected by that period. Once `BYYEARDAY` or `BYWEEKNO`
has fixed the starting days, `BYMONTH`, `BYMONTHDAY` and `BYDAY` keep or drop
days exactly as for `DAILY`, and a rule that carries `BYWEEKNO` without `BYDAY`
keeps only the days whose weekday is the weekday of `DTSTART`.

`BYHOUR` and `BYMINUTE` set the time of day of the candidates. Without them
every candidate takes the time of day of `DTSTART`. With either of them, every
selected day of a period yields one candidate for each combination of a listed
hour and a listed minute, an absent part contributing the hour or the minute of
`DTSTART`, and every candidate takes the seconds of `DTSTART`.

`BYSETPOS` applies to the candidate list of one period, sorted by wall clock
value once the times of day are applied, and selects the positions it names,
where a negative position counts back from the end. It counts positions in the
whole list of the period, before the candidates earlier than `DTSTART` are
dropped.

A component without `RRULE` has exactly one rule candidate, its `DTSTART`. When
a rule is present, `DTSTART` anchors the period sequence and the time of day of
every candidate that `BYHOUR` and `BYMINUTE` leave alone, but `DTSTART` itself
is a candidate only when the rule generates it.

Candidates earlier than `DTSTART` are dropped. Generation stops when `COUNT`
candidates have been produced. `COUNT` counts every candidate from `DTSTART`
onward, including candidates that fall before the store window, and it is
applied before any exclusion date is removed. A candidate is dropped when
`UNTIL` is present and the absolute instant of the candidate is later than
`UNTIL`; the bound itself is kept.

Every generated wall clock candidate is resolved to an absolute instant with
the rules of zone-rules.md, in the zone named by the `TZID` of the master
`DTSTART`. The result is the original instant of that occurrence. Occurrences
whose original instant falls outside the store window are dropped. The window
runs from midnight UTC on the window start date up to but not including
midnight UTC on the day after the window end date, and the local date of an
occurrence plays no part in that test.

Two rule candidates of one series can resolve to the same original instant, for
example when one of them lies in a forward gap and is moved onto the other.
Both count toward `COUNT` and both have a resolution entry, the two entries
carrying the same occurrence identifier, but the instant yields one occurrence.

The occurrence identifier is the collection id, a colon, the UID, a colon and
the original instant written in basic UTC form such as `20270113T170000Z`.

