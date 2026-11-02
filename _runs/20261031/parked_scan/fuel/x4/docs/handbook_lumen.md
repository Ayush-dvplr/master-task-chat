# Lumen settlement handbook

Lumen sends one fixed-width text export per month, ASCII, one record per line
and no header. The column of every field is given by the `layout` of lumen in
`ref/processors.json`. `txn`, `line`, `quantity` and `amount` are whole
numbers padded on the left with zeros; every other field is text padded on
the right with spaces.

## Fields

- `batch`: the batch the record was sent in.
- `txn`: the transaction number.
- `line`: the line number within the transaction.
- `stamp`: the dispense time at the site, `YYMMDDHHMM`, in the site's own
  time (the year is 20YY).
- `site`: the site id.
- `card`: the 16-digit card number. A record whose card is all zeros is a
  pump test and is rejected `pump_test`.
- `product`: the lumen alias of the product.
- `quantity`: for products whose catalogue unit is `litre`, hundredths of a
  US gallon (1 US gallon = 3.785411784 litres); for products sold by the
  item, the number of items.
- `amount`: cents, excluding tax.
- `sign`: `-` on a reversal line, a space on a sale line.
- `ref`: on a reversal line, the line it reverses; spaces otherwise.

## Source id

The source id of a record is `<txn>-<line>`, both numbers written without
leading zeros. Transaction 00104422, line 003 has source id `104422-3`.

## Reversals

A reversal record repeats the quantity and amount of the line it reverses;
the `sign` field marks it.
