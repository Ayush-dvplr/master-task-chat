# Marlow settlement handbook

Marlow sends one JSON Lines export per month, UTF-8, one JSON object per line.

## Fields

- `batch`: the batch the record was sent in.
- `id`: the record id, a string. It is the line's source id.
- `kind`: `sale` or `void`.
- `at`: the dispense time, `YYYY-MM-DD HH:MM:SS`, in marlow head-office time,
  whose UTC offset is `head_office_offset` for marlow in
  `ref/processors.json`.
- `site`: the site id.
- `card`: the 16-digit card number.
- `product`: the marlow alias of the product.
- `quantity`: a decimal string; for products whose catalogue unit is `litre`,
  litres; for products sold by the item, the number of items.
- `amount`: a decimal string, dollars, excluding tax.
- `test`: `true` on a pump test record, which is rejected `pump_test`;
  `false` otherwise.
- `voids`: on a void record, the id of the line it cancels.
- `resubmission_of`: present only on a resubmitted sale line, holding the id
  of the earlier line it replaces.

Marlow sends no reversal lines; a sale is cancelled by a void record.

## Voids

A void record is rejected `void_record`. When its batch is live, the line it
names is rejected `voided`.

## Resubmissions

A sale line with `resubmission_of` sends again, under a new id, a sale line
that marlow sent earlier. When the resubmitted line's batch is live, the line
it names is rejected `replaced`; the resubmitted line is judged like any other
sale line.

Example, on made-up values: line `12` is a sale and line `19` carries
`"resubmission_of": "12"`. Line 12 is rejected `replaced` and line 19 is
checked and settled as an ordinary sale line.
