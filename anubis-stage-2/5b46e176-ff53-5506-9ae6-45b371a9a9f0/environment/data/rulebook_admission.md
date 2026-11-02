# Rulebook: Admission

Filed under A. This rulebook decides which taps belong to the epoch at all.
It consumes the epoch calendar, the epoch policy, the tap register and the
gate register. It produces, for every tap, either an admission or one of the
three refusals below.

## A1. The epoch interval

The epoch calendar names one epoch with an `opens_at` instant and a
`closes_at` instant. The epoch policy names the convention by which that
interval is read, in its `boundary` column. The four conventions are:

| boundary | reading |
|---|---|
| `closed_closed` | `opens_at <= t <= closes_at` |
| `closed_open` | `opens_at <= t < closes_at` |
| `open_closed` | `opens_at < t <= closes_at` |
| `open_open` | `opens_at < t < closes_at` |

The boundary convention is published. It is not one of the properties that
has to be recovered.

A tap whose `tapped_at` falls outside the interval is **out of epoch**. It
takes no further part in the clearance: it is not admitted, it is never
priced, it raises no obligation, it carries no margin, and it is not counted
as a withdrawal. It is listed in the quality register and it is counted in
the epoch summary under its own heading.

## A2. Canonical tap order

Everywhere in this reference set, taps are ordered by `tapped_at` ascending
and then by `tap_id` ascending. That pair is called the canonical order. Every
register may state its rows in any order it likes; the canonical order is a
property of the data and never of the file.

## A3. Repeated tap identifiers

A `tap_id` is meant to be unique. Where the same `tap_id` appears more than
once, the first occurrence in canonical order is admitted and every later
occurrence is withdrawn with the reason `duplicate_tap_id`. The repeated rows
are listed in the quality register.

## A4. Gates that are no longer in service

A gate whose `decommissioned` flag is set is out of service for the whole
epoch. A tap at such a gate is admitted to the epoch but withdrawn at once
with the reason `decommissioned_gate`. The gate itself is suspended from the
start, which matters to the suspension rulebook.

## A5. Peak and off peak

The epoch policy carries a `peak_from` and a `peak_to` time of day, each
written as `HH:MM`. A tap is a peak tap when the time of day of its
`tapped_at` satisfies `peak_from <= time < peak_to`. Every other tap is off
peak. The comparison is on the time of day alone and never on the date.

## A6. What admission does not decide

Admission says nothing about identity, about which tariff table governs a
tap, or about whether a tap survives to be priced. A tap that passes A1, A3
and A4 is **admitted**, and the identity rulebook takes it from there.
