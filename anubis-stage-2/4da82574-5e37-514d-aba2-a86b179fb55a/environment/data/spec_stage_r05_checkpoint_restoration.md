# Stage r05: Checkpoint restoration

A checkpoint body carries the whole state: the position it stands after,
the station balances, the nested station and programme allotments, every
derived counter, the pending queue in queue order, the ledger of applied
event identifiers and the ledger of reversed target identifiers.

Restoration copies the body. The parsed body is left exactly as it was
read, so a second replay from the same checkpoint opens from the same
state as the first. Nested containers are copied too; sharing the
allotment mapping with the parsed body lets one replay bleed into the
next.

A restored watermark of N means the event at canonical position N was
already processed and folded into the state. It is not an event to
process again.
