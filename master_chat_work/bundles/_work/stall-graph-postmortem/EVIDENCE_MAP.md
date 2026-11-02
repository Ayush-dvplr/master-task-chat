# EVIDENCE_MAP (harden round 1)

Each hidden-only lever rests on a shipped fact that fixes the right reading.

| rule | test ids | shipped fact file:line | wrong readings |
|---|---|---|---|
| LV-1 every service cell and tenant segment reports, an unreached one with zeros | trap_zigzag_wait, trap_stride_interleave, trap_reversed_origin_pairs, trap_sentinel_escape, trap_coarse_spin_escape, trap_registry_alias_worker, generalises_to_a_fresh_stall_window, generalises_when_budget_ties_move, generalises_when_a_service_cell_empties, generalises_when_a_new_worker_enters, generalises_when_the_partition_count_changes, generalises_when_the_window_scales | invariants-and-closure.md:53 | partition set taken from the values present in host_cells.csv or tenant_classes.csv, so a cell or segment the capture's table omits gets no report |
| LV-1 zero report content (present-only maps, empty class row zeros) | same as above | sample_audit_answer.json:27 | null or missing keys in an unreached report |
| LV-2 padding lines read and write the owner window after their segment's events | shipped_policy_audit, all 13 generalises_* checks | journal-and-wire.md:83 | padding dropped before the owner window, so later circumflex references read a stale owner |
| LV-2 padding position in logical order | same as above | journal-and-wire.md:64 | padding taken from the front, or interleaved by the stride |
| LV-3 owner tags follow governing rows at the carrying event's epoch, else stand as written | trap_chained_hold_mask, trap_biased_declared_count, trap_chained_segment_origin, trap_ring_owner_reference, trap_rotated_token, trap_shadow_slot, generalises_when_waits_sit_on_the_budget, generalises_when_the_pool_boundary_shifts, generalises_when_registry_presentation_order_inverts, generalises_when_a_dormant_rule_fires, generalises_when_the_window_contradicts_the_control_slice, generalises_when_every_tag_has_one_live_row | identity-and-registry.md:59 | owner column used as written; or owner resolved with the worker rules so retired or unresolved owners are dropped |
| LV-3 alias rows exist in the shipped registry | same as above | thread_registry.csv:36 | alias rows treated as worker-column only |
