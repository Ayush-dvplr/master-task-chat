# Query fleet metering standard

This standard governs how one billing period of the query fleet is metered and charged. The record dictionary defines every input file and column; the report layout defines every report. Sections are in alphabetical order.

## Allowance

Every billing identity receives a free scan allowance for each of its billing days. Its size is the `daily_free_bytes` of the identity's rate card version in force at the instant the billing day begins (local midnight in the identity's zone). The allowance is consumed by the identity's billed queries of that billing day, one query at a time, in billing order, subject to the ordering condition in the record dictionary. Each query takes as free bytes the lesser of its metered bytes and the allowance still left, and the allowance left falls by that amount. The rest of the query's metered bytes are its chargeable bytes. Allowance left at the end of a billing day lapses.

## Billing day and window

A billed query's billing day is the calendar date, in the identity's zone, of its billing instant. Its window is `peak` when that local date is a Monday to Friday that is not a holiday of the zone and the local time of day of the billing instant is at or after 08:00:00.000 and before 20:00:00.000. Every other billed query is in the `offpeak` window.

## Billing identity

A query is billed to a billing identity, found from the tenant that ran it. When that tenant appears as an absorbed tenant in the merge register and the query's billing instant is at or after the merge's effective instant, the query is billed as the surviving tenant; the same test is then applied to the surviving tenant, and so on, until a tenant is reached that no merge applies to at that billing instant. That tenant is the billing identity. The billing identity's segment, plan and zone, from the tenant register, are the ones used for everything the query is billed under, and the query shares that identity's allowance.

## Billing instant

A query's billing instant is the reference-clock instant at which the query completed: its start converted to the reference clock (Clocks) plus its duration.

## Charges

A billed query's charge is its chargeable bytes multiplied by the micro-dollar rate per GiB of its window (`peak_micros_per_gib` or `offpeak_micros_per_gib`) from the rate card version in force at its billing instant, divided by 1073741824, and rounded to a whole number of micro-dollars with halves rounded up. Each query's charge is rounded on its own; every total is the exact sum of rounded query charges.

## Clocks

The fleet's reference clock is the clock of the node whose role is `reference` in the node register. Every other node stamps with its own clock. A node's clock offset is the whole number of seconds by which its clock reads ahead of the reference clock (negative when it reads behind), from -19 to 19; the reference node's offset is 0. A stamp written by a node converts to the reference clock by subtracting 1000 milliseconds for every second of that node's offset. A node's clock may be reset during a period, only while no query is running anywhere in the fleet; between resets its offset is constant, and the transfer journal is the only record of a reset.

## Corrections

Corrections are applied to the query rows that pass the rejection test, in order of `recorded_at`, and among equal `recorded_at` values in order of `correction_id`. A `restate` sets the query's scanned bytes to the correction's `scanned_bytes`. A `void` withdraws the query from billing. A `reinstate` returns a withdrawn query to billing. A correction that names no such query has no effect. A query's scanned bytes after its corrections are the ones it is metered on.

## Metered bytes

A billed query's metered bytes are its scanned bytes, raised to the `min_billable_bytes` of the rate card version in force at its billing instant when they are smaller, and then rounded up to a whole multiple of that version's `block_bytes`. Free bytes and chargeable bytes (Allowance) are parts of metered bytes; scanned bytes are never compared with the allowance directly.

## Query status

A query whose status is `ok` or `cancelled` is billed unless a correction has withdrawn it. A query whose status is `failed` is never billed. A query that is not billed takes no allowance and appears in no total other than the counts in the data-quality report.

## Rate cards

Each plan has a list of rate card versions. A version is in force from its `effective_from` instant, inclusive, until the `effective_from` of the next later version of the same plan, exclusive.

## Rejected rows

A query row is rejected when any of its fields is empty or fails to parse as the record dictionary defines it, when its status is none of `ok`, `cancelled` and `failed`, or when its node, tenant or product is not listed in the matching register. A rejected row takes no further part in metering.

## Transfers

When a query spills a stage to another node, the sending node stamps the moment it sends and the receiving node stamps the moment it receives. Measured on the reference clock, the transfer takes at least 0 and at most 4999 milliseconds.

## Zones

Each tenant zone has a standard offset and a daylight offset from UTC, in minutes, and a list of daylight periods. The daylight offset applies to every UTC instant from a period's `start`, inclusive, to its `end`, exclusive; the standard offset applies to every other instant. The local time of a UTC instant in a zone is that instant plus the offset that applies to it.
