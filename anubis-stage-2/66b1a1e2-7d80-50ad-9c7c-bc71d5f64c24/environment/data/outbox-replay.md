# Outbox replay

While the hosted collection was unreachable, the synchronisation agent queued
writes that were never delivered. They are kept in the pipe separated outbox
named by the index (role `outbox`), with the columns `op_seq`, `collection`,
`uid`, `recurrence_id`, `op`, `base_sequence`, `field`, `value` and `stamp`.
The server replica that takes part in the merge is the server replica as
decoded with every queued operation of the store's collections replayed onto
it. Operations naming a collection the store does not hold are not replayed and
not reported.

## Order

Operations are replayed in increasing numeric `op_seq`, whatever their order in
the file. Each operation acts on the state the earlier operations left.

## Matching and the base check

An operation targets the server component whose collection, UID and raw
recurrence identifier (empty for a master) equal its own. When the server
replica holds no such component, at the moment the operation is reached, the
operation is rejected as `missing`. Otherwise the operation applies only when
the target's current `SEQUENCE` (zero when absent) equals `base_sequence`; when
it does not, the operation is rejected as `stale-base` and changes nothing.

## Applying an operation

`op` is `SET` or `DELETE`.

- `DELETE` removes the target from the server replica. Later operations on the
  same key find nothing and are rejected as `missing`.
- `SET` writes `value` into the property named by `field`: `SUMMARY` replaces
  the summary text; `SEQUENCE` replaces the sequence with the integer `value`;
  `STATUS` replaces the status; `X-SERIES-CLASS` replaces the series class;
  `DURATION` replaces the duration and removes any `DTEND`, so the component's
  length is then taken from the duration.

Every applied operation, `SET` or `DELETE`, also sets the target's
`LAST-MODIFIED` to the operation's `stamp`, which matters to a store whose
ladder compares modification times. A `SET` of `SEQUENCE` changes the sequence
that later operations on the same key are checked against.

Worked example. A server master has `SEQUENCE:8`. Operation 107 is a `SET` with
base 9 and is rejected as `stale-base`. Operation 114 sets `SEQUENCE` to 10
with base 8 and applies. Operation 121 sets `SUMMARY` with base 10 and applies,
because it runs after operation 114.

## Report

The replay report lists every replayed operation in increasing `op_seq` with
its outcome, `applied`, `stale-base` or `missing`, and the target's sequence
after the operation: the new or unchanged sequence for an applied `SET` and a
`stale-base` rejection, and null for an applied `DELETE` and a `missing`
rejection.
