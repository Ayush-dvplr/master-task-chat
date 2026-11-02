# Identity rules

## References

A lease reference names lease `HL-nnnnnn` when, after removing spaces, hyphens
and underscores and upper casing, it reads `HL` followed by digits; the number
with leading zeros removed is the lease. `HL 123`, `hl-000123` and `HL000123`
all name `HL-000123`. An obligor reference names obligor `OB-nnnnn` by the
same rule with the prefix `OB`. A tax id or `fein` is compared as its nine
digits, ignoring every other character. A branch code is compared after upper
casing and removing spaces, hyphens and underscores; it names a branch of
`[branches]` in `branches.ini` directly or through `[aliases]`.

A lockbox `remit_ref` or a card `lease_ref` that is not a lease reference may
be an invoice number; `invoice_notices.csv` maps every invoice number to its
lease. A reference that names no lease of `leases.csv` either way names no
lease.

## Branches and regions

`lease_branch_history.csv` holds the branch of each lease from
`effective_from` onward. The branch of a lease on a date, as known at an
instant, is the known row with the latest `effective_from` on or before the
date; ties go to the later `recorded_at`, then the larger `row_id`. The
booking region of a lease is the region of the row with the earliest
`effective_from` among all rows known at the watermark; ties go to the
earlier `recorded_at`, then the smaller `row_id`.

## Obligors

An obligor is known at an instant when its `obligors.csv` row has a
`created_at` known at that instant. `crm_segment` is a sales label and decides
nothing.

`obligor_events.jsonl` changes obligors. An event applies to a date, as known
at an instant, when it is known at the instant and its `effective_date` is on
or before the date, except `TAXID_CORRECTION`: a tax id correction states the
tax id the obligor always had, so it applies to every date once it is known.
When several corrections are known, the latest `recorded_at` wins, then the
larger `event_seq`. Without one the `obligors.csv` tax id stands.

A `MERGE` event folds its obligor into the obligor named by `into`. The
surviving obligor of an obligor on a date is found by following the applying
`MERGE` events from obligor to obligor until none applies; where one obligor
has several applying `MERGE` events, the one with the latest `effective_date`,
then `recorded_at`, then `event_seq` is followed. The obligor of a lease at a
snapshot is the surviving obligor of the obligor its `obligor_ref` names, on
the as of date as known at the knowledge instant. `NAME_CHANGE` events change
nothing graded. `SECTOR_SET` and `SECTOR_CHANGE` set the sector code of the
obligor they name; the sector code on a date is the applying one with the
latest `effective_date`, then `recorded_at`, then `event_seq`.

## Segments

An obligor is public on a date when its tax id appears in
`public_entity_register.csv` on a row with `listed_on` on or before the date
and `delisted_on` blank or after the date; otherwise it is commercial.

The observation segment of a scored observation is public or commercial by
the tax id of the lease's obligor at the snapshot, as known at the knowledge
instant, on the as of date. The contract segment of a lease is fixed when it
is signed: it is public or commercial by the tax id, as known at the
watermark, of the obligor its own `obligor_ref` names, on the lease's
`start_date`, and commercial when that reference names no obligor. The
contract segment governs the roll of due dates and the payment tolerance; the
observation segment governs scoring, bureau precedence and the segment
reports.
