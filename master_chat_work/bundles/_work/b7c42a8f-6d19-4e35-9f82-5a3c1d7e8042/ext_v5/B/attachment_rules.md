# Attachment rules

Each cedable claim is walked through the ceded path in exactly this order: `retention`, then `working_excess`, then `cat_excess`, then `retro`. At most three layers are pierced; the retro step is an offset applied to the surviving unmet on the `cat_excess` layer rather than a fourth attachment.

## Booked layer

The `layer` on a ledger row is the booked layer: the `layer=` value on the claim's line in `claim_adjustment_log.log`. When a claim has two lines there, the later line in file order wins. A claim with no line there books `retention`. The clash cover below is applied to that booked layer. A retracted or excluded row books `retention` whatever its log line says.

## Factor source

Every per-layer factor is read at run time from `attachment_factors.csv` keyed by `(from_layer, to_layer)`. The authority is that file alone, not any value typed into the delivered module. The row order inside `attachment_factors.csv` is significant: a reader that sorts the rows before building the dict can read the wrong pair when the same `(from_layer, to_layer)` appears twice. The leftmost occurrence of a repeated key governs. The governing run multiplies no ledger figure by these factors.

## Retro offset

The retro offset is already netted out of the reserve figures the corpus carries, so the governing run applies no further retro multiplier to any ledger row. The retro-never counterfactual undoes it with the multiplier stated in `counterfactual_parameters.md`, not with a row of `attachment_factors.csv`.

## Clash cover (per `errata_2032-04.md`)

Within one event, only the first claim in `(claim_ref, reinsurer_canonical)` order consumes the shared retention; the rest start at `working_excess`. Only rows that are neither retracted nor excluded and whose booked layer is `retention` take part; the first of them consumes the retention. The event identifier is the `event_id` column of `claim_master.csv`. The `treaty_handbook.md` individual-risk reading is withdrawn and governs nothing.
