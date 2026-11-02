# Group settlement standard (2023)

Status: replaced by the 2026 group settlement standard (`docs/group_standard.md`).

## 1. Region

1.1 A line belongs to the home region of the processor that exported it, as
given by `home_region` in `ref/processors.json`.

## 2. Rounding

2.1 Amounts are carried unrounded through the month. Totals are rounded to
cents at the end, half away from zero.

## 3. Discount tiers

3.1 The tier of an account is set by the number of fuel transactions it made
in the month at each processor, counted separately per processor.

## 4. Reversals

4.1 A reversal may only name a line of its own export.

## 5. Duplicates

5.1 When a source id appears twice in one export, the later record in the
file settles.

## 6. Tax

6.1 Tax is charged on the net amount after discount.

## 7. Compressed natural gas

7.1 Every processor reports CNG quantities in kilograms. Settlement converts
them to litres at 1.52 litres per kilogram.

7.2 Example, on made-up values: 10.000 kg of CNG is 15.200 litres.

## 8. Pump tests

8.1 Pump test records settle at zero value.

## 9. Business day

9.1 The business day of a line is its UTC date.
