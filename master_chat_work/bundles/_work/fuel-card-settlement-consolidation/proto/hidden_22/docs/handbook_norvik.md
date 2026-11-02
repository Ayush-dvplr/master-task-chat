# Norvik settlement handbook

Norvik sends one XML export per month, UTF-8. The root element is
`<settlement processor="norvik">`; each record is a `<record>` element with
attributes `batch` and `id`.

## Fields

- `batch` (attribute): the batch the record was sent in.
- `id` (attribute): the record id. It is the line's source id.
- `<time>`: the dispense instant, ISO 8601 with a UTC offset. The offset is
  the one set on the terminal's clock.
- `<site>`: the site id.
- `<card>`: the 16-digit card number.
- `<product>`: the norvik alias of the product.
- `<quantity>`: for products whose catalogue unit is `litre`, imperial gallons
  (1 imperial gallon = 4.54609 litres); for products sold by the item, the
  number of items.
- `<amount>`: dollars, including tax.
- `<purpose>`: `retail`, `fleet` or `calibration`.
- `<reverses>`: present only on a reversal line, naming the line it reverses;
  empty when the terminal did not record it.

## Reversals

A reversal record carries `<reverses>` and repeats the quantity and amount of
the line it reverses as negative numbers.

## Calibration

A record whose `<purpose>` is `calibration` is a pump test and is rejected
`pump_test`.

Example, on made-up values: record `id="9"` with `<purpose>calibration</purpose>`
and a quantity of 5.000 is rejected `pump_test`.
