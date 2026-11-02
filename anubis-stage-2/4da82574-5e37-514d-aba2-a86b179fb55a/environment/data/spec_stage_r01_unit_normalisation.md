# Stage r01: Unit normalisation and parameter layers

The recorded quantity of an event is carried into credit units in two
steps. First the unit symbol on the record is looked up in
`unit_registry.toml` and the recorded quantity is multiplied by that
scale. Second the station class is looked up on the frozen station
register and the result is multiplied by the class conversion factor,
a numerator over a denominator, taken from the live sheet of
`custody_parameter_workbook.xlsx`. The product is an exact rational and
is rounded to a whole number of credit units once, here, half away from
zero. No later stage rounds a quantity again.

The live sheet is the sheet whose `epoch_key` cell equals the
`workbook_epoch_key` field of `epoch_header.json`: the value beside the
label cell that reads exactly `epoch_key`. Sheet names and sheet order
carry no meaning in choosing it, and the name published for it is the
name the workbook gives that sheet. The other sheet belongs to a prior
epoch and its numbers differ.

The live sheet carries four kinds of row. A `conversion` row gives a
class, a numerator and a denominator. A `reversal` row gives a class, a
numerator and a denominator. A `carry_quantum` row gives a class and a
whole number. A `ceiling` row gives a revision, a class and a ceiling in
credit units. Rows tagged `calibration` are bench notes and settle
nothing.

`custody_board_memo.pdf` carries the three scalars this epoch runs
under. A resolution line reads `RESOLUTION` then its number then
`SITTING` then the sitting number then the subject then ` = ` then the
value. Where two live resolutions carry one subject the greater sitting
governs. A line that begins `RESCINDED` is not a resolution.

A record is screened before it is applied. The screening tests run in
the order `eligibility_policy.yaml` gives, and the first test a record
fails decides its reason code. `EVT-DRAFTREVISION` fires when the record
revision passes the frozen register revision. `EVT-WITHDRAWN` fires when
the identifier sits in `withdrawn_event_journal.tsv` at a revision at or
below the frozen revision. `EVT-NONPOSITIVE` fires when the normalised
quantity is absent, zero or below. `EVT-IMPLAUSIBLE` fires when it
passes the implausible quantity ceiling in the memo. The last two never
fire on a compensating event, which carries no quantity of its own.
