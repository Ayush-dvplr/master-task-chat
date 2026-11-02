# Temporal rules

## Site clocks

`site_clock_offsets.csv` holds the offset history of every relay site. The offset
in force at an instant is the one whose `from_instant` is the greatest at or
before that instant. The table covers the whole fleet, so most of its rows name
sites that file nothing in this cycle. Offsets change inside the horizon for some
sites.

A site local wall time stamp carries no offset. Windows written in wall time are
compared in wall time: convert the decision instant to the site's local time using
the offset in force at the decision instant, and test that local stamp against the
window.

## Freeze windows

`site_freeze_windows.csv` announces freezes. A row applies to a request when its
`site` matches the submitting site, its `channel` matches the target channel, its
`family` matches the unit's family and its `flavour` is either the unit's flavour
or the single character that stands for every flavour. A row whose `status` is not `active` has
been withdrawn and applies to nothing. The window runs from `start_local` for the
length in `hold_len`, which this table counts in hours. The window is half open:
the first instant is inside it and the instant the window ends is outside it.

A freeze window covers the decision instant when the site local decision stamp is
inside the window.

## Recurring holds

`recurring_holds.csv` announces weekly holds. A row applies to a request on the
same site, channel and family terms as a freeze window. The `weekday` field is
Monday zero and is read in site local time, which is not always the same weekday
as the absolute instant. The row applies on dates from `from_date` inclusive up
to `until_date` exclusive, both read as site local dates. On an applying date the
hold runs from `start_local` for the length in `hold_len`, which this table counts
in minutes. The window is half open.

`hold_exceptions.csv` changes single occurrences. An exception whose `action` is
`cancel` removes the occurrence named by `occurrence_date`. An exception whose
`action` is `shift` moves that occurrence's start later by `shift_minutes` and
keeps its length.

## Waivers

`waiver_records.jsonl` lifts a freeze window or a recurring hold and nothing else.
A waiver applies when its `site`, `family` and `channel` all match and it is the
governing record for that triple and it has not expired.

Expiry counts business days at the waiver's site. Convert the waiver's
`effective_at` to site local time and take its date. The first business day at or
after that date is business day one. Count on through business days until the
number in `expires_after_business_days` is reached. The waiver expires at midnight
site local at the end of that day, converted back to an absolute instant, and it
holds while the decision instant is earlier than that. A business day is a date
that is not a weekend day and is not a holiday for that site in
`business_calendar.yaml`.

## Normative parameters

```
freeze_length_unit: hours
hold_length_unit: minutes
weekday_zero: monday
```
