# Concierge desk billing standard

This standard governs one billing cycle of the concierge desk. Its sections are in alphabetical order. The meaning of every column it relies on is given in the record dictionary, and the shape of every report is given in the report layout.

## Allowance credit

Each client's plan includes a number of minutes for the cycle. The included minutes are credited against the client's eligible closings, beginning with the eligible closing whose completion instant is the latest and moving to earlier completion instants. Among eligible closings of one client with the same completion instant, the closing whose closing reference comes first in code point order is credited first. Each closing in turn is credited the smaller of its billable minutes and the included minutes not yet credited. A closing is eligible when it is billed and its tier is one of the credit tiers of the client's plan. The billable minutes of a closing that are not credited are its charged minutes.

## Amendments

An amendment names one closing by handset and handset sequence number. Void and minutes amendments take effect in order of issue instant, and amendments with the same issue instant take effect in code point order of their amendment identifiers. A void or minutes amendment whose issue instant is earlier than the completion instant of the closing it names has no effect, and so has one that names no received closing. A revert names a void or minutes amendment and cancels it, so that the named amendment counts as never issued; a revert whose issue instant is not later than the issue instant of the amendment it names, or that names no void or minutes amendment, has no effect. A closing named by at least one void amendment that has effect and is not cancelled is void. Otherwise, when minutes amendments that have effect and are not cancelled name the closing, its worked minutes are those of the one among them that takes effect last.

## Billable minutes

The billable minutes of a closing are its worked minutes rounded up to the next whole multiple of the billing increment of its service. Worked minutes that are already a whole multiple stay as they are.

## Billed closings

A received closing is billed unless it is rejected, void, outside the cycle or unrated.

## Cycle

The cycle header names the cycle, its first and last local business days, both of them inside the cycle, the rate card in force, and the minimum invoice. A closing whose local business day is earlier than the first day or later than the last day is outside the cycle.

## Duplicates

A closing is identified by its handset and its handset sequence number. When the main export and the legacy export both hold a row with the same identity, the main export row is the closing and the legacy row is a duplicate, which is not a closing at all. Within one export no identity repeats.

## Local business day

The local time of a closing is its completion instant moved by the UTC offset that the zone of its client has in force at that completion instant, as the zone rules give it. The local business day of a closing is the calendar date of its local time.

## Minimum invoice

A region invoice is in scope when the gross amount of the region, as the money rules define gross, is at least the minimum invoice of the cycle header. A segment invoice is in scope when the net amount of the segment is at least that minimum. The region test reads gross amounts and the segment test reads net amounts; each test uses only its own operand.

## Money

Money is carried in integer micro-units, one micro-unit being one millionth of the currency unit. The gross amount of a billed closing is its billable minutes times its rate. The net amount is its charged minutes times its rate. The credit amount is the gross amount minus the net amount. Every total is the sum of the amounts of the closings it covers. The one rounding in this standard turns a net amount in micro-units into whole cents: the amount is divided by 10000 and rounded to the nearest whole cent, an exact half going to the even cent.

## Pricing

The rate of a closing is taken from the rate card that the cycle header names. It is the rate of the row for the closing's service and tier whose effective interval holds the closing's local business day. An effective interval runs from its effective_from day, which it includes, to its effective_to day, which it excludes; an empty effective_to means the interval has no end. A closing without such a row is unrated.

## Rejections

A received closing whose service code is neither a code of the service catalog nor an alias of the alias table is rejected with the reason unknown_service.

## Services

The service of a closing is the catalog code its service code names. A service code that is an alias names the catalog code the alias table maps it to.

## Tiers

The tier of a closing is weekend_holiday when its local business day is a Saturday, a Sunday or a holiday of its client's region. Otherwise it is standard when the time of day of its local time is at or after 08:00:00 and before 18:00:00, and after_hours in every other case.
