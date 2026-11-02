# Amendment rules

## 1. When a notice applies

A notice in `amendment_notices_p*.jsonl` restates one field of one request:
`quantity`, `node` or `effective`. A notice changes a request only when every
one of the following holds.

1. Its recorded instant is at or before the as of instant.
2. Its recorded instant is strictly after the latest recorded instant among
   the admitted source rows of the request. A notice recorded before the
   evidence it restates is tallied as `amendments_early` and ignored.
3. No live retraction targets it.
4. It is endorsed. The audit entry whose `apl` matches `approval_ref` names an
   approver, and that approver must hold a role whose scope is the field of
   the notice, or the scope `any`, at the instant of the audit entry.
   Endorsement by any other approver is tallied as `amendments_unendorsed`
   and the notice is ignored.
5. No surviving notice supersedes it.

Among the surviving notices for one field the notice with the greatest
recorded instant governs, ties broken by the greater notice id.

## 2. Supersession and retraction

A notice names in `supersedes` the notice it replaces, or `null`. A notice
that is itself superseded by a surviving notice does not apply. Where the
chain of `supersedes` links visits a notice twice the request cannot be
settled and carries the reason `UNRESOLVABLE_CHAIN`, tallied as
`amendment_chains_unresolvable`.

`retraction_notices.csv` withdraws a notice, a commitment exception or
another retraction, named in `target_id` with its `target_kind`. A retraction
is live when it is admitted and no live retraction targets it, so a retracted
retraction leaves its target standing. Notices withdrawn by a live retraction
are tallied as `amendments_retracted`.

## 3. Effect

A surviving `quantity` notice replaces the governing quantity in the unit the
notice carries, wafers. A surviving `node` notice replaces the requested node.
A surviving `effective` notice replaces the governing effective instant and
can move the request into another cycle. It never moves a request to the other
side of the cutover and it never changes the collapse grouping.

Applied notices are tallied as `amendments_applied`.

## 4. The audit

Approval audit entries are spread over `approval_audit.log` and its two
rotations. Read all three. An entry whose `apl` is `none` endorses nothing. A
role grant in `authority_roles.csv` holds over its half open window when the
grant row is admitted, and the latest admitted grant row for an approver,
role and scope governs, ties broken by the greater `revision_seq`.
