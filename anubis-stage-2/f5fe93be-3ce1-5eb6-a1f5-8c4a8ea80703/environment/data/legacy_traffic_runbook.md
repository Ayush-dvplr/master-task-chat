# Traffic reconciliation runbook (retired engine, superseded)

This runbook describes the reconciliation engine the traffic desk used before the switcher log was archived alongside the as-run logs. That engine was retired before this close. The page is kept for history only. It is not authoritative, and nothing in it overrides `reconciliation_rules.md` or the other rule documents.

How the retired engine worked:

- A spot counted as aired when chain A logged it `PLAYED`. Chain B was consulted only when chain A logged nothing at all for the spot.
- Spots were dated by the calendar date of their as-run label.
- A spot counted for its daypart when its start label fell inside the daypart.
- Of two corrections for the same spot, the one recorded last won.
- Chain B labels were used as logged.
- Commission was computed once on the advertiser's invoice total.
- Shortfalls and bonus spots of the same order line were netted over the week before make-goods were raised.
- Make-goods went to the break with the most spare time in the same daypart.

When this runbook and the current rule documents disagree, the current rule documents govern.
