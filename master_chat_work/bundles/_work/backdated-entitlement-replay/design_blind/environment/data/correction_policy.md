# Correction policy

## What a correction is

A correction in corrections.json states that from `effective_date` on, the
account held `quantity` units of `item`. It is an entitlement event dated on
its effective date; original events dated after it still take effect on their
own dates. `arrival_seq` numbers the corrections in the order they reached the
billing team.

## Screening

Corrections are screened one by one in `arrival_seq` order. A correction is
rejected with the first of these reasons that applies:

1. `unknown_account`: the account is not in accounts.json.
2. `unknown_item`: the item is not in price_book.json.
3. `duplicate_id`: a correction with the same `correction_id` arrived
   earlier, whether that one was applied or rejected.
4. `account_unresolved`: the account is unresolved (billing_terms.md).
5. `before_window`: the effective date is before the start of the account's
   cycle for the first statement month.

Every other correction is applied.

## Ordering

Applied corrections join the account's entitlement events at their effective
dates. For one account, item and date, the original events come first in file
order, then the corrections in `arrival_seq` order, and the last one stands.

## Replay

Every paid and open invoice of a resolved account is rated again under the
billing terms with the applied corrections included. `original_total` is the
sum of the invoice's recorded lines and `corrected_total` is the total of the
rated invoice. Credit, payments and balances follow the corrected totals
(credit_policy.md).

The first affected statement month of an applied correction is the first
statement month of the window whose cycle starts on or after its effective
date.
