# Identity rules

## Principal ids

Employees are written `emp:` followed by the employee number as six digits with leading zeros, for example `emp:004211`. Contractors are written `ctr:` followed by the contractor number as four digits, for example `ctr:0193`.

An employee reference is an optional `E` or `e`, an optional `-`, then one to six digits: `E004211`, `4211`, `e-4211` and `004211` all name `emp:004211`. A contractor reference is `CTR`, `C` or their lower case forms, an optional `-`, then one to four digits: `CTR-0193`, `c193` and `C-0193` all name `ctr:0193`. A reference whose id is not a principal names nobody. HR files, contract sponsors and IdP `subject_ref` values are references. Security revocation `subject` values are a reference when they match one of these two patterns and a handle otherwise.

## Handles

A handle is compared without surrounding spaces and without regard to case. A handle resolves through the IdP: the winning account record for that handle names its principal through `subject_ref`. When a handle has no winning account, `directory_aliases.tsv` is consulted: a visible alias maps to a handle, and the reference resolves to that handle's principal. A value that is itself the handle of a winning account always resolves through its own account, so an alias row whose alias is such a handle has no effect and is accepted. An alias whose target handle has no winning account, or whose winning account names nobody, is unresolved `unknown_handle`. Aliases do not chain.

Every record field holding a handle (`member`, `beneficiary`, `requester`, `approver`, `revoker`, `holder`, `from_holder`, `to_holder`, `reviewer`, `subject` in attestations, the MFA `handle`) resolves this way. A record any of whose handle or reference fields names nobody is unresolved `unknown_handle`, except where `provenance_rules.md` names another code.

## Accounts

For each handle the winning account record is chosen among its visible records: the highest `generation` wins, and between equal generations the shard listed first in `idp_shard_priority` wins. The other visible records of that handle are superseded. When the winner's `subject_ref` names nobody the winner is unresolved `orphan_account` and the handle resolves to nobody. A principal may own several handles; everything recorded under any of them belongs to the principal. A principal's accounts are enabled when at least one of its winning records has state `enabled`.

## MFA

The MFA events of a principal are those whose `handle` resolves to it. A principal is enrolled at an instant when the latest of its visible events at or before that instant (ties by event id) is `enroll`. A `reset` ends enrolment until the next `enroll`.
