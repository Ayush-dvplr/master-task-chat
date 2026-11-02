# Readings this facility does not support

Each line names a reading of these papers that looks reasonable and
is wrong here, beside the reading in force.

1. Not in force: a checkpoint watermark names the next position to
   replay. In force: a watermark names a position already processed,
   so the first candidate the window can replay is the watermark
   plus one.
2. Not in force: the requested range is closed at both ends. In
   force: the range is start inclusive and end exclusive.
3. Not in force: a compensating event reverses the event next to it.
   In force: it reverses the event the link register names, resolved
   against the whole canonical history.
4. Not in force: a compensation target must sit inside the replay
   window. In force: the target may sit behind the restored
   checkpoint, and its metadata is read from the canonical history
   without replaying it again.
5. Not in force: eligibility is settled once, before the pass. In
   force: an event whose predicate is false waits in the pending
   queue and is offered again after the window is exhausted.
6. Not in force: the pending queue is offered in canonical order. In
   force: it is offered in the order the directive ladder gives.
7. Not in force: a compensation reverses primary state only. In
   force: it also reverses the derived counter its kind moves, at
   the class reversal scale, exactly once.
8. Not in force: two compensations on one target each take effect.
   In force: the target is reversed once and the later compensation
   is recorded as void with no effect on any counter.
9. Not in force: a dependency behind the window is missing. In
   force: it is already folded into the restored checkpoint and is
   satisfied.
10. Not in force: `station_register_current.csv` gives the class. In
    force: `station_register_frozen.csv` does.
11. Not in force: `legacy_scale_table.csv` gives the carry quantum.
    In force: the live sheet of the workbook does, and the quantum
    appears in no other paper.
12. Not in force: the workbook sheet is chosen by name or position.
    In force: it is chosen by matching its epoch key cell against
    the epoch key in the header.
13. Not in force: the first resolution in the memo governs. In
    force: among resolutions on one subject the later sitting
    governs, and a line marked RESCINDED carries no force.
14. Not in force: canonical order is arrival order. In force: it is
    sequence, then stamp, then kind rank, then tie break key, then
    event identifier.
15. Not in force: two records that carry the same payload are one
    event. In force: an event is its identifier, and two identifiers
    are two events however alike their payloads look.
16. Not in force: a record whose `source` field is empty was lodged
    by the journal. In force: the provenance ledger names the source
    of a record that carries none.
