# Cash rules

## Payments and their sources

A payment reaches the extract through up to two sources. A lockbox payment is
a line of one of the four lockbox files (the bank) and a servicing ledger
posting with `channel` `LOCKBOX`. A card payment is a line of
`card_settlements.csv` (the processor) and a posting with `channel` `CARD`. An
ACH payment is a posting with `channel` `ACH` only. One payment is identified
by its lockbox `item_id`, its card `auth_code` or, for ACH, its `posting_id`;
a ledger posting names the lockbox item or the card authorisation in
`source_ref`, compared after removing hyphens and upper casing.

Lines of one file that are byte for byte identical are one record and count
once in `duplicates`. A lockbox or card line may be corrected by a later line
with the same `item_id` or `auth_code`; the governing bank or processor line
of a payment at an instant is its line with the latest recorded time known at
that instant. A bank or processor line is rejected, and then ignored, with
reason `unknown_lease` when its reference names no lease, or otherwise with
reason `bad_amount` when its amount is not a positive number of dollars
written with exactly two decimals.

A payment is known at an instant when any of its records is known at that
instant. It belongs to the lease of its ledger posting, or, while no posting
is known, to the lease its bank or processor line names.

## Value date and credited amount

For a lockbox payment the governing bank line, when one is known, gives both
the value date and the credited amount; otherwise the ledger posting does. For
a card payment the governing processor line gives the value date when one is
known, and the ledger posting gives the credited amount when it is known; a
processor amount includes the card surcharge (`servicing_policy.ini`), which
is not credited. For an ACH payment the posting gives both. Where a posting
gives the value date, the value date is the local date of `posted_at` on the
lease's booking clock (`calendar_rules.md`).

## Returns

A line of `ach_returns.log` returns the payment of the posting it names. A
return code reverses the payment when `return_codes.ini` marks it `yes`;
other codes are notices and change nothing. A reversing return removes its
payment, as if it had never been made, at every instant at which both the
return and the posting it names are known. A return naming a posting that is
not known at the watermark is rejected with reason `unknown_posting`, keyed
by its return id.

## Counts and rejects

`payments` in `data_quality.json` counts the distinct payments known at the
watermark that belong to a lease, by channel (`lockbox`, `card`, `ach`), and
under `reversed` the ones among them with a reversing return known at the
watermark. The only reject reasons of the whole extract are `unknown_lease`,
`bad_amount`, `invalid_transition`, `holiday_limit` and `unknown_posting`.
