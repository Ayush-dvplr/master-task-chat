# Attachment rules

Each cedable claim is walked through the ceded path in exactly this order: `retention`, then `working_excess`, then `cat_excess`, then `retro`. At most three layers are pierced; the retro step is an offset applied to the surviving unmet on the `cat_excess` layer rather than a fourth attachment.

## Factor source

Every per-layer factor is read at run time from `attachment_factors.csv` keyed by `(from_layer, to_layer)`. The authority is that file alone, not any value typed into the delivered module. The row order inside `attachment_factors.csv` is significant: a reader that sorts the rows before building the dict can read the wrong pair when the same `(from_layer, to_layer)` appears twice. The leftmost occurrence of a repeated key governs.

## Retro offset

The retro offset multiplies the cat-excess unmet on every ledger row whose booked layer is `cat_excess`, before the row enters allocation. The multiplier is the `retro` factor row in `attachment_factors.csv` whose `from_layer` is `cat_excess` and whose `to_layer` is `retro`. Every counterfactual that invokes "retro offset" reads this one number, including pair 4 in the closing message. A delivered module that holds the retro multiplier as a Python literal fails the hidden-extract check, because A and B each ship a different retro factor.

## Clash cover (per `errata_2032-04.md`)

Within one event, only the first claim in `(claim_ref, reinsurer_canonical)` order consumes the shared retention; the rest start at `working_excess`. The event identifier is the `event_id` column of `claim_master.csv`. The `treaty_handbook.md` individual-risk reading is withdrawn and governs nothing.
