# Entity model

## Site identity

A batch row carries a site reference as the producing system wrote it. A site
reference joins to a registered site only after normalization. Normalization
applies Unicode NFC composition, replaces tab characters with spaces, collapses
every run of whitespace to one space, removes whitespace that pads a hyphen,
strips the leading and trailing whitespace, and case folds the result to upper
case. Two references that normalize to the same string denote the same site.
Two references that differ before normalization and agree after it are not a
conflict.

`entity_aliases.tsv` and `entity_aliases_partner.psv` record the reference forms
two upstream systems are known to emit. They are a record of observed forms and
they are not a substitute for the normalization above.

## Merges

`site_merges.csv` records that one site was absorbed into another at an instant.
A merge applies to an event only when the effective instant of that event is at
or after the merge instant of that hop. An event whose effective instant
precedes the merge instant keeps the absorbed site as its canonical site.

Merges chain. Where a site was absorbed into a second site that was itself
absorbed into a third, each hop is taken only when the effective instant is at
or after that hop's own merge instant, and the chain stops at the first hop
whose merge instant the effective instant precedes.

The canonical site of an event is the site the chain reaches. The source site is
the registered site the normalized reference denotes before any hop is taken.

## Effective dated reference data

`sites_effective.csv`, `operational_state.csv`, `max_interval_limits.csv` and
`meter_registry.csv` each carry rows bounded by `valid_from` and `valid_to`.
Every such interval is half open, so a row governs an instant that is at or
after `valid_from` and strictly before `valid_to`.

These files are corrected in place rather than rewritten, so for one key more
than one row can cover one instant. Where that happens the row whose
`valid_from` is the latest governs, and where two covering rows carry the same
`valid_from` the one whose `valid_to` is the earliest governs, because the
narrower row is the later correction. The order the rows appear in the file
decides nothing, and a correction sits ahead of the row it corrects as often
as behind it.

A key can also carry no row covering an instant at all. A gap is not a zero
and not a default: what a gap means is decided for each file by the rule that
reads it, and for `max_interval_limits.csv` the protocol makes it an
unresolvable condition.

A meter is the meter of a site only over the interval its registration row
bounds. A site that changes meter inside the calendar keeps the row for the
meter that went out alongside the row for the one that came in, so a meter id
can appear in the file and still hold no registration at the instant a reading
occurred.

Every registration in `meter_registry.csv` carries a `pulse_multiplier`, the
whole number of metered units one delivered count stands for. A row whose
`pulse_multiplier` is absent, or is not a positive decimal integer written in
the ten ASCII digits, is not a registration at all: it covers no instant and it
governs nothing, and a meter holds a registration over that window only if
another row of the file provides one. Such a row is not an exception and it is
reported nowhere.

Every effective dated lookup is made against the canonical site of the event and
at the effective instant of the event. A lookup made against the source site, or
made at the ingestion instant, or made against the row that is current at the
end of the calendar, resolves to a different row for part of the population.
The one lookup that is not made at the effective instant is the pulse
multiplier of a delivered row, which the protocol reads at that row's own
`occurred_at` because a row is read as delivered.
