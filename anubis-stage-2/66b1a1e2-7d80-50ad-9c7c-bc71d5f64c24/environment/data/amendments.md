# Amendments

The documents in this folder were frozen before the amendments below. Each
amendment names a document and a section and replaces the rule stated there,
wherever that rule appears, including an earlier amendment. The amendments are
in force for the whole store window.

## v4.1

A1. load-model.md, per attendee fold, rest decay. The decay applied at a step
    is `decay_per_rest_day` multiplied by one less than the rest days when the
    rest days are greater than one, and zero otherwise. A single free day
    between two occurrences no longer earns any decay.

A2. attendance.md, violations. When an occurrence starts on a closure day of
    its effective office, only the `office-holiday` violation is recorded for
    that attendee and occurrence; the working window test is not applied to it.

## v4.2

A3. exclusions-and-overrides.md, ranged overrides. An applied override written
    with `RANGE=THISANDFUTURE` hands its content forward as well as its
    displacement. Every occurrence it displaces, that is every later occurrence
    of the series that is not itself the target of an override, takes from the
    latest such override whose recurrence identifier instant is strictly
    earlier than its original instant the office, the summary, the required
    attendee references and the series class that the override's own
    occurrence shows, so each of them already falls back to the master
    component where the override carries none. It also takes that override's
    duration in place of the master's or of its RDATE period: a `DTEND` span
    keeps its seconds, a `DURATION` is measured from the displaced start under
    the store setting in the zone of the office handed forward, an override
    with neither lasts one hour, and the duration source is the override's. A
    cancelled override and a superseded override hand nothing forward. The
    displacement itself is unchanged and still composes over every earlier
    ranged override.

A4. attendance.md, violations, together with amendment A2. When an occurrence
    starts on a closure day or on a non working day of its effective office,
    the working window test is not applied to it for that attendee. A closure
    day records the `office-holiday` violation, a non working day records the
    `non-working-day` violation, and a day that is both records both.

A5. conflicts-and-settling.md, the settling loop, deferral. A deferral first
    adds the quantum to the wall clock start of the deferred occurrence in the
    zone of its own office and resolves the result with the rules of
    zone-rules.md. When the occurrence would then end after the closing minute
    of the working window of its office row for its new local start date, that
    is when its end minute, counted from local midnight of that date as
    attendance.md counts it, is greater than that closing minute, the
    resolution is discarded. The occurrence moves instead to the opening minute
    of the working window on the first local date after its new local start
    date whose office row is a working day and which is not one of the office's
    closure days, and that wall clock value is resolved instead. The move
    records as `deferred_minutes` the wall clock minutes, rounded down, from the
    local start before the move to the wall clock value that was resolved, and
    as `gap_shift_minutes` the shift recorded by that resolution.

## v5.1

A6. chargeback.md, lines, stage 1. The base amount of a line is rounded to a
    whole number of cents half to even: an exact half cent goes to the even
    neighbour, so 12.5 cents becomes 12 and 13.5 cents becomes 14. Stage 2 is
    unchanged and still rounds half up.
