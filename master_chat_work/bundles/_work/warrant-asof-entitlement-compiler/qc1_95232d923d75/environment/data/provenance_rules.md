# Provenance rules

## Authority

HR is the authority on employment and IdP on credentials; a principal needs both. The directory is the authority on group membership and the binding files on what a group may do. The grant files, approvals, corrections and self-service revocations together decide elevation. Security revocations override every other source. Correction and amendment files govern the records they amend.

## Governing versions

| Records | Governing version |
|---|---|
| contract amendments of one contractor | the highest `amendment_no` among the accepted amendments; the others are superseded |
| HR corrections of one event | the visible, valid correction recorded last (ties by `correction_id`); the others are superseded. `void` deletes the event, `redate` replaces its `effective_date`. A correction naming an event that is not accepted is accepted and changes nothing |
| grant request records sharing a `ticket` across shards | the highest `export_generation` among the visible records; lower generations are superseded. When several records share that generation and are identical in every field, the one in the alphabetically first shard is used and the rest are superseded. When they differ in any field, every one of them is unresolved `conflicting_duplicate` and the ticket does not exist |
| grant corrections of one ticket | the highest `revision` (ties by the later recorded instant); the others are superseded. A correction naming a ticket that does not exist is accepted and changes nothing |
| IdP records of one handle | see `identity_rules.md` |
| on-call assignments of one rotation and week | the highest `revision` (ties by the later recorded instant); the others are superseded |
| removals of one membership | the earliest `removed_at` among the visible ones; every visible removal is accepted |
| self-service revocations of one grant | each applies when its `revoker` resolves to the ticket's beneficiary or requester; the earliest `effective_at` among those wins. Any other revoker makes the record rejected `revoker_not_party`; a revocation naming a ticket that does not exist is accepted and changes nothing |

## Validation

Each visible record is checked in this order, and the first failure names its class and reason:

1. a required field absent from a JSON record: `missing_field` (grant requests need both `effective_from` and `effective_until` keys, though either may be null; corrections need `effective_until`; journal entries need `value`)
2. any instant or date field the compiler reads that cannot be read: `bad_timestamp`
3. a window whose end is at or before its start: `window_inverted` (grant requests with both ends set, bindings with a `bound_until`, contracts whose `end_date` is before `start_date`)
4. a name that is not in its catalog: `unknown_target` (a binding's `role` or `group_id`, a membership's `group_id` or `group:<id>` member, a request `target`, an attestation `permission`, a `perm:` scope of a security revocation, an assignment or swap `rotation`), or `out_of_scope` for a `perm:` request target outside its env
5. a principal reference that names nobody: unresolved `unknown_handle` (or `orphan_account` for an IdP winner)

Role names are matched without regard to case and through each role's `legacy_names`. Grant request duplicates are settled before these checks run, and the checks apply to the governing record only. `freeze_window`, `revoker_not_party` and `swap_mismatch` are decided after a record has passed the checks above. Journal records have their own checks (`config_contract.md`).

These are the only reject reasons: `bad_timestamp`, `missing_field`, `window_inverted`, `unknown_target`, `out_of_scope`, `freeze_window`, `revoker_not_party`, `swap_mismatch`, `anchor_key`, `unknown_key`, `out_of_bounds`. These are the only unresolved reasons: `unknown_handle`, `orphan_account`, `conflicting_duplicate`.

## Classes

Every row of every record file falls in exactly one class: `invisible` (not visible at the cutoff), `rejected`, `unresolved`, `collapsed` (superseded by a governing version or identical to the record used), or `accepted`. Rows of `hr_employees.csv` are always accepted. A request that is pending, vetoed or approved is accepted unless it is rejected `freeze_window`.
