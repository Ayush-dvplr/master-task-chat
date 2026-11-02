# Closed vocabularies

Every code named here is closed. A record carries one code drawn from the set
its field belongs to and no other value ever appears in that field.

## Reason codes, carried by a rejected row

```
BAD_QUANTITY      the quantity field is present and is not a numeral of the
                  grammar record-layouts.md gives for the batch's unit
BAD_TIMESTAMP     occurred_at does not parse as an instant in either of the
                  two written forms the protocol defines, or names a date or
                  a time that does not exist
MALFORMED_ROW     revision_class is outside the five defined classes, or
                  revision_no is not a positive decimal integer written in
                  ASCII digits
METER_SITE_MISMATCH  the meter registration covering the instant names a
                  site other than the one the normalized reference denotes
OUT_OF_CALENDAR   occurred_at parses and falls outside the settlement calendar
UNKNOWN_METER     meter_id holds no registration in meter_registry.csv
                  covering the instant the row occurred at
UNKNOWN_SITE      the normalized site reference is not a registered site
```

## Unresolvable codes

```
MISSING_BASE       every admitted revision of the event is a RESTATEMENT
MISSING_BATCH      an ACTIVE manifest row names a file that is absent
MISSING_CEILING    no row of max_interval_limits.csv covers the canonical
                   site of the event at its effective instant
ORPHAN_SUPERSEDE   the canonical revision supersedes a revision_no that no
                   admitted revision of the event carries
```

## Revision classes

```
AMENDMENT   ORIGINAL   CORRECTION   RESTATEMENT   REVERSAL
```

## Outcomes

```
DEFERRED   EXCLUDED   SETTLED   UNRESOLVABLE   VOIDED
```

## Adjustment kinds

```
COUNT_ONLY   DECREASE   INCREASE
```

## Tariff bands

The band names `tariff_classes.csv` carries for the class, plus the literal
`UNBANDED` for a quantity below every threshold of that class.

## Revision roles

```
BASE                the base revision of its event
CANONICAL           the canonical revision of its event
DISPLACED           an admitted RESTATEMENT another RESTATEMENT of the
                    same event displaced, and which is neither canonical
                    nor base
RESTATEMENT_STACK   any other admitted RESTATEMENT that is not canonical
SUPERSEDED          any other admitted revision
```

A revision that is both canonical and the base of its event carries
`CANONICAL`, because a revision carries exactly one role and `CANONICAL`
governs. A displaced revision that is canonical carries `CANONICAL` and a
displaced revision that is the base carries `BASE`, for the same reason.

## Stack states

```
ABSENT      the revision carries no quantity, so it added nothing
APPLIED     the delta reached the clamped base
DISPLACED   another RESTATEMENT of the event named this revision_no
WITHHELD    the event never reached its quantity chain
```

A stack state is decided in the order `DISPLACED`, then `WITHHELD`, then
`ABSENT`, then `APPLIED`, and the first one that holds governs.
