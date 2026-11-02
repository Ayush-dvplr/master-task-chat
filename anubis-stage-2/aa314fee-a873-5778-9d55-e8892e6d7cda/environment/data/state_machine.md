# Request state

## 1. Events

`state_events_p*.jsonl` carries state changes for requests. A request with no
admitted event stands as `approved`. Events for one request are applied in
ascending recorded instant, then ascending `version`, then ascending event
id, and never in the order the files happen to list them. An event whose
version is at or below the highest version already applied to that request is
stale: it is ignored and tallied as `stale_events`. Two admitted events of the
same version are tallied as `duplicate_version_events`, and since the first of
them sets the highest version applied, the second is stale.

## 2. Legal changes

The states are `approved`, `held`, `withdrawn` and `rejected`. The changes
that are legal are `hold` from `approved` to `held`, `release` from `held` to
`approved`, `withdraw` from `approved` or `held` to `withdrawn`, `reject`
from `approved` to `rejected`, and `reinstate` from `withdrawn` to
`approved`. The state `rejected` admits no further change.

Any other change leaves the state as it was and is tallied as
`illegal_transitions`. The event is still consumed, so it still sets the
highest version applied.

## 3. Reinstatement needs authority

A `reinstate` event takes effect only when an approver holding the scope
`state` or the scope `any` endorsed it. Where the event carries an
`authority_ref` string, the endorsement is the audit entry whose `apl` equals
that string. Where `authority_ref` is `null` no endorsement was recorded.
Where the key is absent, the endorsement is the audit entry whose `ref`
equals the event id. A reinstatement without a valid endorsement is an
illegal change and the request stays `withdrawn`.

## 4. Effect on the claim

Only a request whose settled state is `approved` claims capacity. A request
left `held` carries the reason `ON_HOLD`, one left `withdrawn` carries
`WITHDRAWN`, and one left `rejected` carries `REJECTED`. Such a request keeps
its ledger row, with its claim at zero and its quantity still reported.
