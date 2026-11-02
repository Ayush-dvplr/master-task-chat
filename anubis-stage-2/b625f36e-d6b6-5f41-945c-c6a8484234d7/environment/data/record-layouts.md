# Record layouts

Six batch families deliver revisions. Every family carries the same ten logical
fields and the families differ in serialization, in field order and in the unit
the quantity field is written in.

```
family      files                      serialization   header   quantity unit
desk        readings_desk_NN.csv       comma           yes      kilowatt hours
import      readings_import_NN.jsonl   json per line   no       kilowatt hours
relay       readings_relay_NN.tsv      tab             yes      kilowatt hours
partner     readings_partner_NN.psv    pipe            yes      kilowatt hours
legacy      readings_legacy_NN.fixed   fixed width     no       kilowatt hours
adjustment  adjustments_NN.jsonl       json per line   no       watt hours
```

The field name `quantity` therefore denotes a decimal count of kilowatt hours in
five families and a whole count of watt hours in the sixth. The unit is a
property of the batch family and never of the row.

The delimited families carry a header line naming their columns. The partner
family writes the same ten columns in a different order from the others, and the
header states that order.

The partner family stamps `occurred_at` and `ingested_at` in the fixed offset
form, and the other five stamp them in the Z form. Both forms are defined in
the protocol, which also states how an offset instant is carried to UTC.

The fixed width family carries no header. Its columns occupy these widths in
this order, and every field is left aligned and padded with spaces:

```
event_key            12
revision_no           4
revision_class       12
site_ref             16
meter_id             10
occurred_at          22
ingested_at          22
quantity             14
delta_flag            2
supersedes_revision   4
```

The json families write every field as a string. A field that carries no value
is written as an empty string in every family.

A quantity is a numeral written in ASCII characters. In the five kilowatt hour
families a numeral is an optional sign `+` or `-`, one or more digits, and
optionally a point followed by one or more digits. In the watt hour family a
numeral is an optional sign followed by one or more digits and nothing else.
No other spelling is a numeral in either unit: not an exponent, not a digit
group separator, not a point with no digit on one side of it, and not a named
value such as `NaN` or `Infinity`. A leading sign, leading zeros and trailing
zeros in the fraction are part of the grammar and do not change the value.
The padding a fixed width column carries is not part of the field.

Every batch is UTF-8 text. A line ends at a line feed, and a carriage return
immediately ahead of the line feed belongs to the line ending rather than to
the last field. A producing system may write a byte order mark ahead of the
first line; it belongs to no line and to no field.

An empty `quantity` denotes an interval that was delivered without a reading. An
empty `supersedes_revision` denotes a revision that supersedes nothing. A
quantity of zero is a delivered reading of zero and is a different thing from an
empty quantity.
