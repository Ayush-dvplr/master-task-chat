# Additional dates

A master component may also carry `RDATE` properties, and one property may list
several values separated by commas. Each value adds one candidate. A value is a
date time, or a period written as a date time, a solidus and then either a
second date time or a duration. A date time, and both date times of a period,
are resolved with the rules of zone-rules.md in the zone named by the `TZID` of
their own property, a value ending in `Z` being an absolute instant; the
candidate is the first date time of the value. RDATE candidates are not
produced by the rule: `COUNT` does not count them, `UNTIL` does not bound them,
and one earlier than `DTSTART` is kept, so the store window is the only test
that drops one. The rule candidates are taken first and the RDATE values then
in file order; an RDATE candidate whose original instant equals the original
instant of a candidate already kept adds nothing and has no resolution entry.
Every other RDATE candidate is an original instant like any rule candidate,
with a resolution entry of its own: exclusions and overrides match it, ranged
overrides displace it, and its occurrence identifier is formed in the same way.
A component that carries `RDATE` without `RRULE` has its `DTSTART` candidate
and its RDATE candidates.


An occurrence supplied by an RDATE period of the master takes its length from
the period instead of from the master component. A period that ends in a second
date time lasts the fixed number of seconds between its two resolved instants,
as for `DTEND`; a period that ends in a duration is measured from the start of
the occurrence exactly as `DURATION` is, under the store setting. The duration
source of such an occurrence is `RDATE`. An RDATE value that is a single date
time takes the duration of the master component.

