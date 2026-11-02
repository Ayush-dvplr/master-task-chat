# Access contract

`warrant-ctl` compiles two access profiles, `dev` and `prod`. A profile states, for one instant, which principal holds which permission and until when. The instant is the configuration's `as_of`; the records the compiler may use are those visible at the configuration's `recorded_cutoff`. Both come from the resolved configuration (`config_contract.md`).

## Visibility

A record is visible when its recorded instant (column given per file in `corpus_index.md`) is at or before `recorded_cutoff`. A record that is not visible is ignored entirely: it is not validated, not reported, and contributes nothing, even when it describes something that took effect before `as_of`. A record whose recorded instant cannot be read is rejected with `bad_timestamp`. Reference files (`.json`, `.toml`, `.ini`) are always in force.

## Principals and eligibility

The principals are every employee in `hr_employees.csv` and every contractor with a governing contract amendment (`provenance_rules.md`). For each profile every principal has exactly one eligibility state at `as_of`, decided in this order:

1. `inactive` when the principal is not employed at `as_of`. An employee is employed when the last of their HR events taking effect at or before the instant is `hire`, `rehire` or `leave_end`; `terminate` and `leave_start` end employment, and an employee with no such event is not employed. A contractor is employed while their governing contract covers the instant and their sponsor is employed at that instant.
2. `disabled` when no winning IdP account of the principal has state `enabled`.
3. `mfa_blocked` when the profile's `require_mfa` is true and the principal is not enrolled at `as_of` (`identity_rules.md`).
4. `eligible` otherwise.

Only eligible principals receive keys. An employee's employment bound is the earliest `terminate` or `leave_start` taking effect after `as_of`, or open. A contractor's employment bound is the earlier of the end of their contract cover and their sponsor's employment bound.

## Components

A permission reaches an eligible principal through up to three components, each with a bound (an instant or open).

**Standing.** A membership is in effect at `as_of` from its `added_at` until its removal, the earliest `removed_at` among the visible removals of that `mid`. A member of the form `group:<id>` makes every member of that group a member of the containing group, to any depth; cycles are legal. The membership bound of a principal in a group is the largest, over every chain of in-effect memberships leading from the principal to the group, of the earliest removal along the chain. A role binding in effect at `as_of` gives the group's members every permission of the role. A role's permissions are its own plus those of every role it includes, transitively, keeping only permissions whose catalog `scope` is the profile or `both`. The standing bound of a permission is the largest, over every group and binding that carries it, of the smaller of the membership bound and `bound_until`.

**Elevated.** A grant request names one `env` and a `target`. A `role:` target carries the role's permissions for that env; a `perm:` target carries one permission and is rejected `out_of_scope` when the permission's scope excludes the env. An approval qualifies when the approver is an employee, is neither the beneficiary nor the requester, and is employed at `decided_at`; one principal counts once however many handles or approvals they used. A request with any qualifying `reject` is `vetoed`. A request with fewer distinct qualifying approvers than the profile's `approvals_required` is `pending`. Every other request is approved and becomes a grant. A request whose `effective_from` is null is requested from its recorded instant. A grant never starts before its requested start; the moment the gateway starts honouring an approved grant is shown by the reviewer observations. The requested end is the governing correction's `effective_until` when a correction governs, else the request's own; null means open. A grant ends at the earliest of its requested end, its start plus the profile's `max_grant_hours`, and the earliest `effective_at` among the self-service revocations that apply to it. When the profile's `freeze_applies` is true, an approved grant whose start falls inside a freeze window of its env is rejected `freeze_window`. The elevated bound of a permission is the latest end among the grants in effect at `as_of` that carry it, for an eligible beneficiary; its elevation start is the earliest start among those grants.

**On call.** A rotation runs one shift a day (`daily`) or one shift a week on `weekday` (`weekly`), starting at `start` local wall time in the rotation's `tz` and lasting `duration_minutes` of elapsed time. The holder of a shift is the governing assignment for the week whose Monday, in local dates, begins that shift's week, after the swaps for that rotation and `shift_date` are applied in recorded order (ties by `swap_id`). A swap applies only when its `from_holder` is the holder at that point; otherwise it is rejected `swap_mismatch`. The holder of the shift in effect at `as_of` (the latest starting one when several are) receives the rotation role's permissions for the rotation's env. The on-call bound is that shift's end, carried through each following shift of the same rotation that starts no later than the bound reached so far and has the same holder.

## Gating

**Attestation.** When the profile's `attestation_required` is true, every `critical` permission held through a standing or elevated component needs a current review. The deciding review is the latest visible review for that subject, permission and profile reviewed at or before `as_of` (ties by `attestation_id`), ignoring reviews whose reviewer is the subject. It must have decision `keep` and be no older than `attestation_max_age_days` whole days of 86400 seconds before `as_of`. Without one, the permission's standing and elevated components are dropped and the pair is listed in `unattested`; an on-call component survives.

**Separation of duties.** When the profile's `sod_enforced` is true, the pairs of `sod_policy.json` for that profile are taken in `rule` order. A principal holds a side of a pair when the permission keeps a standing or elevated component after attestation; on-call components are exempt. When both sides are held: if both have a standing component nothing is removed and a `standing_conflict` is recorded; if exactly one has a standing component, the other side's elevated component is suspended; if neither does, the side with the later elevation start is suspended, and on equal starts the alphabetically greater permission is. A suspension made under one rule is in place before the next rule is taken.

## Keys

A permission's value is the latest bound among its remaining components, capped by the principal's employment bound and by the `effective_at` of every visible security revocation that matches it. A revocation matches every permission of its subject for scope `all`, every permission in one profile for `env:dev` or `env:prod`, and one permission in both profiles for `perm:<name>`. A key `principal|permission` is listed when its value leaves it in effect at `as_of`. The value is written `open` when no bound applies.

Every window in this contract (memberships, bindings, grants, shifts, freeze windows, contract cover, key values) follows the one boundary convention the gateway enforces.
