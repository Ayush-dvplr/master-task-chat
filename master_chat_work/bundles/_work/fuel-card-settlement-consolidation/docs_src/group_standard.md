# Group settlement standard (2026)

This standard governs how the monthly settlement exports of the five card
processors are consolidated into one ledger. The processor handbooks say how
each export is laid out; the reference files under `ref/` hold the master
data; `docs/output_schema.md` says what the program writes.

## 1. Authority and month

1.1 The settlement month is the `settlement_month` value of
`ref/processors.json`, written `YYYY-MM`.

1.2 This standard applies to every export named in `ref/processors.json`.

## 2. Lines

2.1 Every record of an export is one line. A header row is not a line.

2.2 A line either settles, giving exactly one ledger row, or is rejected with
exactly one reason from `docs/output_schema.md`. When several reasons apply,
the reason that comes first in the check order of that document is used.

2.3 A line is a sale line or a reversal line, as its processor handbook says.
Pump test records and void records are lines too; they never settle.

## 3. Business date

3.1 The business date of a line is the calendar date of its dispense instant
at the UTC offset of the line's site in `ref/sites.csv`.

3.2 Example, on made-up values: a dispense at 2041-03-01T04:30:00Z at a site
whose offset is -06:00 has business date 2041-02-28.

## 4. Scope

4.1 A line whose business date is outside the settlement month is rejected
`out_of_period`. A reversal line is judged by its own business date, not by
the date of the line it reverses.

## 5. Attribution

5.1 The region of a ledger row is the region of its site in `ref/sites.csv`.

5.2 The account of a sale line is the holder of its card on the line's
business date (`docs/reference_data.md`, cards.csv).

5.3 The segment of a ledger row is the account's segment in force on the
row's business date (`docs/reference_data.md`, accounts.csv).

## 6. Products and quantities

6.1 A line names its product by the alias its processor uses in
`ref/products.xml`. An alias belongs to one processor only; a code that is an
alias of another processor, or of none, makes the sale line
`unknown_product`.

6.2 The kind of a row (`fuel` or `nonfuel`) is the kind of its product.

6.3 The litres of a fuel row is the line's quantity converted to litres with
the conversion that governs that product's quantities, rounded to 3 decimal
places.

6.4 The litres of a nonfuel row is 0.000, whatever quantity the line reports.

## 7. Tax

7.1 The tax rate of a line is the rate in `ref/tax_rates.tsv` for the
jurisdiction of its site and the tax class of its product, taken from the row
with the latest `effective_from` on or before the line's business date.

7.2 When a processor reports amounts including tax, the net amount is the
amount divided by (1 + rate), rounded to cents, and the tax amount is the
amount minus the net amount.

7.3 When a processor reports amounts excluding tax, the net amount is the
amount, and the tax amount is the net amount times the rate, rounded to cents.

## 8. Rounding

8.1 Every rounding in this standard rounds half to even, one line at a time,
at the step that names it. Example, on made-up values: 2.345 rounds to 2.34
and 2.355 rounds to 2.36.

8.2 A total is the sum of the rounded row values. It is never rounded again
and never recomputed from unrounded figures.

## 9. Discount

9.1 The tier volume of an account is the sum of the litres of the account's
fuel rows in the ledger, from every processor, sale rows counting positive and
reversal rows negative. Every settled amount uses the discount tier earned by
the account's whole-month settled volume across all processors.

9.2 The tier earned is the tier in `ref/discount_tiers.ini` with the highest
`floor_litres` that is at or below the tier volume. Example, on made-up
values: with floors 0, 70 and 350, a tier volume of 350.000 earns the 350
tier.

9.3 A fuel row whose segment is listed under `[eligible]` in
`ref/discount_tiers.ini` carries the account's tier, and its discount amount
is its litres times that tier's `rate_per_litre`, rounded to cents. Every
other row carries tier `none` and a discount amount of 0.00.

9.4 The discounts of one account in one month may not add up to more than the
`[cap]` value for the row's segment. Sale rows are taken in ledger order
(`docs/output_schema.md`); a row whose discount would take the running total
past the cap gets the remainder, and later sale rows get 0.00. Example, on
made-up values: with a cap of 10.00, discounts of 4.00, 5.00 and 3.00 become
4.00, 5.00 and 1.00. A reversal row carries the negative of the discount of
the row it reverses and does not change the running total.

## 10. Settled amount

10.1 The settled amount of a row is net amount plus tax amount minus discount
amount.

## 11. Reversals

11.1 A reversal line names the line it reverses. A reference to a line of the
same processor is that line's source id; a reference to a line of another
processor is written `<processor>:<source id>`. Example, on made-up values:
`lumen:77-2` names line 77-2 of the lumen export.

11.2 A reversal line settles only if the line it names settled as a sale line
in this month's exports; otherwise it is rejected `orphan_reversal`. Example,
on made-up values: sale 41 is rejected `unknown_card`, so reversal 42, which
names 41, is rejected `orphan_reversal`.

11.3 The ledger row of a reversal has entry `reversal`, its own business date,
and the account, segment, site, region, product, kind and tier of the row it
reverses. Its litres, net, tax, discount and settled amounts are those of the
row it reverses, negated.

11.4 A reversal line with an empty reference reverses the sale line that fits
it. A sale line fits when it comes from the same processor, has the same card
and the same product, carries the quantity and amount the reversal repeats,
settles as a sale line under the check order of `docs/output_schema.md`, has a
business date on the reversal's business date or one of the six days before
it, and is not reversed by another line. Example, on made-up values: card
1111000000000009 buys 40.000 litres of diesel for 80.00 on 2041-08-04 as sale
61, and reversal 63 on 2041-08-06 has an empty reference and repeats that
quantity and amount, so it reverses 61.

11.5 Reversals that carry a reference are resolved before any reversal with
an empty reference. Reversals with an empty reference are then taken one at a
time in the ledger order of `docs/output_schema.md`, and a sale line taken by
an earlier one no longer fits a later one. A reversal that exactly one sale line fits reverses that line; one
that no sale line fits is rejected `orphan_reversal`; one that more than one
sale line fits is rejected `ambiguous_reversal`.

## 12. Duplicates

12.1 When two lines of one processor carry the same source id and both pass
every earlier check, the line from the batch whose `OPENED` entry comes first
in `ref/batches.log` settles and the other is rejected `duplicate`. Example,
on made-up values: line 7 appears in batch B31 and in batch B30, and B30 was
opened first, so the copy in B30 settles.

## 13. Ledger ids

13.1 The ledger id of a row is `<processor>:<source id>`, where the source id
is the one the processor handbook defines.

## 14. Carried forward

14.1 Section 7 of the 2023 group settlement standard
(`docs/group_standard_2023.md`) remains in force under this standard.
