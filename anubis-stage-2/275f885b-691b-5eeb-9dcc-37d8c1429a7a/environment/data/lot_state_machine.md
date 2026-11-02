# Lot state machine

A lot starts in the state `quarantine`. `release_certificates_h1.csv` and its sibling carry the
certificates that move it.

The only moves that apply are `quarantine` to `released`, `quarantine` to `condemned`,
`released` to `condemned`, and `condemned` to `reinstated`. A certificate that would make any
other move is counted as an illegal transition and leaves the state as it was. The state
`reinstated` is the state `released` for every other purpose.

A certificate restating the state in force applies and moves nothing, and it is counted
nowhere.

A certificate naming another certificate in `supersedes` replaces it, and the replaced
certificate decides nothing. Where the certificates in view replace each other in a loop, the
lot has no settled state, is counted once, and supplies nothing for the rest of the campaign.

A certificate moving a lot to `reinstated` applies only when the role in `signed_by` carries
`can_reinstate` in `authority_scopes.json`. A reinstatement signed by any other role is counted
as an illegal transition and leaves the state as it was.

The state in force at an instant follows from the certificates whose `issued_at` falls at or
before that instant, applied in `issued_at` order with `cert_ref` breaking a tie.
