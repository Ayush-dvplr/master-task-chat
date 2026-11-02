# Oberon settlement handbook

Oberon sends one TSV export per month, UTF-8, with a header row:

    batch	txn_id	tender	entry	epoch	site	card	product	ml	amount_cents	ref

## Fields

- `batch`: the batch the record was sent in.
- `txn_id`: the transaction number.
- `tender`: the tender number within the transaction, starting at 1.
- `entry`: `S` for a sale line, `R` for a reversal line, `T` for a pump test,
  which is rejected `pump_test`.
- `epoch`: the dispense instant, whole seconds since 1970-01-01T00:00:00Z.
- `site`: the site id.
- `card`: the 16-digit card number.
- `product`: the oberon alias of the product.
- `ml`: for products whose catalogue unit is `litre`, millilitres; for
  products sold by the item, the number of items.
- `amount_cents`: cents, including tax.
- `ref`: on a reversal line, the line it reverses, or empty when the terminal
  did not record it; empty on every other line.

## Source id

The source id of a record is `<txn_id>/<tender>`. Transaction 3301442,
tender 1 has source id `3301442/1`.

## Split tender

A transaction paid with two tenders is sent as two records with the same
`txn_id` and tenders 1 and 2. Each record carries the card, quantity and
amount its tender paid for and is its own line.

Example, on made-up values: transaction 55 is sent as `55/1` with 20000 ml and
3000 cents on one card and `55/2` with 10000 ml and 1500 cents on another
card. Each settles as its own ledger row, `oberon:55/1` and `oberon:55/2`.

## Reversals

A reversal record repeats the quantity and amount of the line it reverses, as
positive numbers.
