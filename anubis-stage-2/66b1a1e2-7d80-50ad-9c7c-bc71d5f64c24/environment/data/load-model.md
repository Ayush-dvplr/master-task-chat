# Circadian load model

This model estimates the accumulated body clock cost of an executive meeting
schedule. It is a bookkeeping model, not a medical one. The load fold is
computed from the schedule before settling.

## Constants

    floor              minus 30
    decay_per_rest_day 3
    unit_minutes       15
    cap                8

## Per attendee fold

For each attendee, take every occurrence that lists them as a required
attendee and order the list by absolute start instant and then by occurrence
identifier. Walk the list once, carrying a running debt that starts at zero.

For each occurrence:

The effective office is resolved as travel-and-busy.md describes. The solar
minute of the occurrence is recomputed for the effective office, not for the
office recorded on the event, and the solar window is the one of the office row
in force for the local start date in the effective office (office-register.md).

The deviation in minutes is

    max(solar window opening minute minus solar minute,
        solar minute minus solar window closing minute)

This quantity is negative when the occurrence sits strictly inside the solar
window, and its magnitude is then the distance to the nearer edge. It is
positive when the occurrence sits outside. It is not clamped at zero.

The cost in units is the deviation divided by `unit_minutes` with floor
division, so a deviation of minus thirty gives minus two and a deviation of
seven gives zero.

The rest days are the number of whole days between the local end date of the
previous occurrence for this attendee and the local start date of the current
one, minus one. Both dates are taken in the effective office of their own
occurrence. The first occurrence of an attendee has zero rest days. The value
can be negative when two occurrences share a day.

The decay applied is `decay_per_rest_day` multiplied by the rest days when the
rest days are positive, and zero otherwise.

The new debt is

    max(floor, previous debt minus decay applied plus cost in units)

If the effective office of this occurrence differs from the effective office of
the previous occurrence for this attendee, the debt is then reset to zero. The
reset happens after the cost of the current occurrence has been folded in, not
before. The first occurrence of an attendee never counts as an office change.

The peak debt of an attendee is the larger of zero and the largest debt after
any step. The final debt is the debt after the last step. The over cap list
holds every attendee whose peak debt exceeds the cap, with the excess; a peak
equal to the cap is not over it.
