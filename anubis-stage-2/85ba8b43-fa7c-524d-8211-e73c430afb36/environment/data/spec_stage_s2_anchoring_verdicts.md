# S2 Anchoring and Verdicts

Anchor each match on its FIRST attempt (minimum `checkpoint_no` across ALL its
attempts, sealed or not), and take the anchor date from that first attempt's
`match_epoch`. Do NOT anchor on the canonical row.

Resolve the adjudicated verdict from `verdict_amendment_history.tsv`. Consider only revisions
whose `effective_at` is within 40 days on or after the anchor date.
Order the surviving revisions by `review_seq` and take the last one.
`amended_at` is backfilled and MUST NOT be used for ordering. Map the verdict
through the crosswalk: `LADDER_CLEAR` -> positive, `VOID_SMURF` -> negative;
`SHADOW_HOLD` and `PENDING_REMATCH` (and any match with no in-window revision)
are excluded from BOTH numerator and denominator.
