# Known traps

Every trap below is a documented rule, a forward step and an exact
inverse. Nothing here depends on a value that is absent from this
directory.

1. **Revision layering.** Every register carries rows above the
   frozen register revision. Those rows are drafts and govern
   nothing. Among the rows at or below the frozen revision, the
   greatest revision for a key is the row in force.
2. **Twin registers.** `station_register_frozen.csv` and
   `station_register_current.csv` carry the same keys with different
   classes and regions. The frozen one governs.
3. **Twin scope maps.** `topology_and_scope.xml` and
   `topology_drafts.xml` carry the same station identifiers with
   different regions. The first one governs.
4. **Twin scale tables.** `legacy_scale_table.csv` restates the
   class scales with a shifted numerator and a shifted carry
   quantum. The workbook governs.
5. **Two workbook sheets.** One sheet is in force. Match the epoch
   key cell, never the sheet name and never the sheet position.
6. **Rescinded resolutions.** The memo carries lines that begin
   RESCINDED. They carry no force. Among live resolutions on one
   subject the later sitting governs.
7. **Aliased identifiers.** A station or programme may be recorded
   under a site or project code. Resolve it through the crosswalk
   before anything else touches it.
8. **Recorded units.** A quantity is recorded in one of six unit
   symbols. Carry it through the unit registry before the class
   conversion, not after.
9. **Blank lodging source.** Some supplement records carry an empty
   `source`. The provenance ledger names the source of those.
10. **Convenience dependency copy.** The `depends_on` list inside a
    journal record is stale. The pipe file governs, and only its
    `requires` edges count.
11. **Full canonical ties.** Some events agree on sequence, stamp
    and kind. The tie break key separates them, and where that also
    agrees the event identifier does.
12. **Checkpoint digests.** Some sealed checkpoints declare a digest
    that no longer matches the body they point at. Recompute and
    reject the ones that disagree.
13. **Register rows with no body.** Some checkpoint register rows
    point at bodies that were never lodged.
14. **Checkpoints past the end.** Some checkpoints stand at or after
    the requested end boundary and cannot be used for that range.
15. **Zero denominators.** A station whose allotments cancel to zero
    has no share to publish. Publish an exact zero rather than
    dividing.
16. **Archive drift.** `prior_epoch_archive.db` holds counters that
    can disagree with the checkpoint body. The recomputed digest
    governs; the archive difference is reported, not applied.
17. **Boundary positions.** The bounded range opens on a position
    that carries an event and closes one past the last position it
    replays.
18. **Reserved rows.** Several registers carry rows whose key begins
    `reserved`, `RSV` or `feed_`. They are lodged for later epochs.
19. **Retired predicate form.** `hub_open` is carried in the
    predicate register as retired. A predicate the register does not
    carry as active is false whenever it is read.
20. **Round ceiling binding.** When the round ceiling is reached
    while a round is still admitting, publish the pass the ceiling
    stops at and record that the run did not settle.
