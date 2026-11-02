# Stage r03: Canonical event order

The lodged records arrive in two files. `event_journal.jsonl` holds the
desk journal and `event_supplement.ndjson` holds the late lodges. One
record survives per event identifier: the one whose lodging source
carries the greater priority in `source_priority_register.csv`, and
among records of one source the greater revision. A source register row
is in force at or below the frozen revision, and among in force rows for
one source the greatest revision gives the priority.

A record may carry an empty `source`. `row_provenance_ledger.csv` names
the source of each record identifier in each file, and that name is used
when the record carries none.

A supplement row whose identifier begins with the prefix
`data_lineage.md` reserves for a later epoch takes no part in the merge.

An event is its identifier. Two records that agree on kind, station,
programme and quantity but carry different identifiers are two events,
and both are placed in the order.

The canonical order is, in this exact precedence: `sequence` ascending,
then `stamp` ascending, then the kind rank in force from
`event_kind_ranks.csv` ascending, then the `tiebreak` key ascending as
text, then `event_id` ascending as text. Arrival order, file order and
json key order settle nothing. The one based index of an event in this
order is its canonical position, and every range, watermark and probe in
this contract is stated as a canonical position.
