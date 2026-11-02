# Kestrel settlement handbook

Kestrel sends one CSV export per month, UTF-8, with a header row:

    batch,txn_id,type,timestamp,site,card,product,quantity,amount,orig_txn

## Fields

- `batch`: the batch the record was sent in.
- `txn_id`: the transaction number. It is the line's source id.
- `type`: `SALE` for a sale line, `REV` for a reversal line, or the pump test
  type given by `pump_test_type` for kestrel in `ref/processors.json`. A
  record of the pump test type is a pump test and is rejected `pump_test`.
- `timestamp`: the dispense instant in UTC, ISO 8601 with a trailing `Z`.
- `site`: the site id.
- `card`: the 16-digit card number.
- `product`: the kestrel alias of the product.
- `quantity`: for products whose catalogue unit is `litre`, litres; for
  products sold by the item, the number of items.
- `amount`: dollars, including tax.
- `orig_txn`: on a `REV` record, the line it reverses; empty otherwise.

## Reversals

A `REV` record repeats the quantity and amount of the line it reverses, both
written as positive numbers.
