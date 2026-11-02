# Harbourline PM2.5 monitoring standard

This standard defines how the readings of the network become hourly values, daily values and
compliance findings. The fields of every input file are defined in the record dictionary
(`record_dictionary.md`); the reports are laid out as `report_layout.md` describes. Concentrations in
the reports are whole numbers of tenths of a microgram per cubic metre. The sections below are in
alphabetical order.

## Corrected concentration

The corrected concentration of a reading is its `pm25_raw` value multiplied by the unit's span factor
in force at the instant the reading represents. The product is taken exactly and then rounded half
up to a whole number of tenths.

## Daily value

A site's valid hours are grouped by the day of local standard time they lie in. When a day has at
least `day_min_hours` valid hours, it is a complete day and its daily value is the mean of the hourly
values of its valid hours, rounded down to a whole number of tenths. A day with at least one valid hour but fewer than
`day_min_hours` still has a daily value when the mean of the hourly values of its valid hours,
rounded down to a whole number of tenths, is greater than the daily standard; that mean is then its
daily value, and the day is not a complete day. Any other day has no daily value. A site's valid days are the days that have
a daily value.

## Daily standard

The daily standard is the policy's `daily_standard`, expressed in tenths of a microgram per cubic
metre.

## Design value

A site's daily values are ranked from the highest down. The design rank is one for a site with 1 to
50 daily values, two for 51 to 100, and one more for every further 50 daily values or part of 50.
The design value is the daily value at the design rank. A site with no daily value has neither.

## District and operator rollups

A district rollup gathers the sites of one reporting district, and an operator rollup gathers the
sites of one operator class. A rollup is in scope when at least one of its sites has a status other
than `incomplete`; every other rollup is out of scope. The status of a rollup in scope is
`nonattainment` when at least one of its sites is in nonattainment, and `attainment` otherwise. The
rolled-up valid readings of the network are the valid readings of the sites in the district rollups
that are in scope.

## Exceedance day

A day is an exceedance day of a site when its daily value is greater than the daily standard.

## Excluded readings

Every card row that is not a valid reading is an excluded reading. A row whose hour lies outside the
report window is counted as `outside_window` and under no other reason. Every other excluded row is
counted under each reason that applies to it: `undeployed` when it belongs to no site,
`missing_value` when its `pm25_raw` is empty, `flagged` when its `status` is not empty,
`uncalibrated` when its unit has no span factor in force at the instant it represents, and
`maintenance` when it belongs to a site and that instant lies inside a maintenance window of the
site.

## Hour of a reading

A reading counts toward the hour of local standard time that contains the instant the reading
represents. Which instant a reading represents is set out in the record dictionary.

## Hourly value

The valid readings of a site are grouped by the hour they count toward. An hour with at least
`hour_min_readings` valid readings is a valid hour, and its hourly value is the mean of the corrected
concentrations of those readings, rounded down to a whole number of tenths. Any other hour has no
hourly value.

## Local standard time

Every hour and day in this standard is an hour or day of local standard time, as the zone rules
define it, all year round. Daylight saving never moves an hour or a day of a report; civil time is
used only where a file says its times are written in it.

## Packets received

A unit has received a journal entry when one of the rows on its card was sent as that packet: the
entry's channel is the unit's channel, its minute is the true end of that row's averaging interval,
and its frame is the row's frame.

## Reconciliation residual

The reconciliation residual is the network's valid readings less its rolled-up valid readings.

## Report window

A reading lies inside the report window when the hour it counts toward lies in one of the days of
the report window.

## Required valid days

The required valid days are `days` times `site_min_valid_day_percent`, divided by 100 and rounded
up to a whole number.

## Site of a reading

A reading belongs to the site where its unit was deployed at the instant the reading represents. A
reading at an instant when its unit stood at no site belongs to no site.

## Site status

A site is in `nonattainment` when its design value is greater than the daily standard. Otherwise it
is in `attainment` when its valid days are at least the required valid days. Otherwise it is
`incomplete`.

## Valid reading

A reading is valid when it lies inside the report window, belongs to a site, has a `pm25_raw` value,
has an empty `status`, has a span factor in force for its unit at the instant it represents, and
that instant lies inside no maintenance window of its site.

## Worst site

The worst site of a group of sites is the site with the highest design value among those that have
one; of two sites with the same design value, the one whose site id carries the lower number is the
worse. A group in which no site has a design value has no worst site.
