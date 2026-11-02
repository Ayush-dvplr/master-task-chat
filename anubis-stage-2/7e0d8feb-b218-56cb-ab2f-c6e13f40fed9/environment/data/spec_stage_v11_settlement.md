# V11 settlement

Inputs: the admitted spots from V9, `rate_card_book.csv`,
`advertiser_register.csv`, `currency_minor_units.json`, the commission terms
in the settled sheet of `contract_terms_workbook.xlsx`, and the billing
grain published in `regulatory_minutage_memo.pdf`.

## R27 the billable grains

A grain is the billing grain in whole seconds, and it occupies
`grain * 30000 / 1001` channel frames exactly. A delivered spot bills the
smallest whole number of grains that covers its delivered frames, so the
grain count is the ceiling of the delivered frames divided by the frames a
grain occupies. A delivery that lands exactly on a grain boundary bills that
many grains and no more. A delivered spot of zero frames bills zero grains.

The frames a spot bills are its delivered frames less its unbilled frames,
the frames V13 left above the regulatory cap of a clock hour under R41. The
grain count is taken over the billed frames, not over the delivered frames,
and a spot all of whose frames went unbilled bills zero grains. The
`delivered_frames` column still publishes every frame the spot occupied, and
`unbilled_frames` publishes the frames R41 took from it.

## R28 the rate card

The rate card that prices a spot is the row of `rate_card_book.csv` carrying
the order's `rate_card_ref` with the greatest `effective_from` that is on or
before the transmission date. A card whose `effective_from` equals the
transmission date is eligible. An order whose card has no eligible row is
never admitted, and is recorded in the exception ledger with the code
`EX_NO_CARD`.

The date compared is the transmission date of the broadcast day, for every
spot of the day. A spot that airs after midnight, in the hours `H24` to
`H29`, still belongs to the broadcast day that began at the day start, and a
card that takes effect on the following calendar day prices none of it.

## R39 two revisions on one date

When two eligible rows of one `rate_card_ref` share the greatest
`effective_from`, the row with the greater `card_revision` prices the spot.
`card_revision` is a whole number and compares as one, so revision 10
supersedes revision 9. The order the rows sit in the file settles nothing.

## R29 the money

The gross of a spot in minor units is its billable grains multiplied by the
card's `minor_per_grain`. The published major amount is the gross divided by
ten raised to the currency's exponent, rendered to that many decimal places.
The exponent comes from `currency_minor_units.json` per currency and is not
two for every currency.

## R30 the commission

The agency commission is the gross multiplied by the advertiser's
`commission_num` over `commission_den`, taken from the rows of the settled
workbook sheet whose first cell is `COMMISSION`, and rounded to a whole
minor unit with halves going to the even value. The net is the gross less
the commission.

`legacy_commission_table.csv` publishes a superseded commission in a
different parameter space and is never read.

## Published

`settlement_ledger.psv` publishes one row per admitted spot, ordered by
`order_ref` and then by market reference. `exception_ledger.jsonl` publishes
one record per exception, ordered by `order_ref` and then by exception code,
with the code `EX_ZERO_DELIVERY` for an admitted spot that occupies no
channel frame and the code `EX_NO_CARD` for an order with no eligible rate
card. `advertiser_summary.csv` publishes one row per advertiser in the
register, ordered by `advertiser_ref`, whether or not the advertiser has any
admitted spot.
