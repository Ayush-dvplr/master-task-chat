# LGA appendix: corpus encodings

This appendix is part of the LGA contract and states how every corpus file is
read. `SPEC-LGA.md` section 3 names the groups and their fields; this file says
how the bytes carry them.

Every corpus file is UTF-8 and carries records of one group only. A file may
open with a byte order mark; a reader discards it, and it is no part of the
first line. Every line, the last included, ends with a newline character, which
may be preceded by a carriage return; the carriage return belongs to the line
ending and is no part of the last field. Where an encoding below lets a value
hold a newline, that newline is part of the value and does not end the line. A blank line is ignored wherever it appears. A file's extension names its
encoding and nothing else does.

Every value is text as it is read. Converting a value to a number, to a set or
to a boolean is the reader's job and the rules for doing so are in
`SPEC-LGA.md` and the other appendices, never here.

## `.csv`

The first line holds the field names separated by commas. Each later line holds
one record. A field holding a comma, a double quote or a newline is wrapped in
double quotes, and a double quote inside such a field is written twice. A field
holding none of those three is written plain. A line with fewer fields than the
header has the missing trailing fields read as empty.

## `.psv`

As `.csv`, with a vertical bar in place of the comma as the separator. The
quoting rule applies to a field holding a vertical bar, a double quote or a
newline.

## `.ssv`

As `.csv`, with a single space in place of the comma as the separator. The
quoting rule applies to a field holding a space, a double quote or a newline.
Consecutive separators are not collapsed, so an empty field between two spaces
is an empty field.

## `.tsv`

The first line holds the field names separated by tab characters. Each later
line holds one record. Nothing is quoted. Inside a value a backslash is written
as two backslashes and a tab as a backslash followed by the letter `t`; a
reader also accepts a backslash followed by the letter `n` for a newline. No
value in this corpus carries a newline.

## `.fixed`

The first line is a width declaration: one `name:width` element per field,
joined by semicolons, where the width is a count of characters. Each later line
holds the fields in that order, each left aligned and padded on the right with
spaces to its width. Trailing spaces are padding and are removed when the value
is read. A value longer than its width is truncated to it, so widths are chosen
wide enough that no value is; a value exactly as long as its width is followed
at once by the next field, with no space between them.

## `.json`

The whole file is one JSON object with a single key `records` whose value is
the list of record objects. Every field value is a JSON string, including one
that holds only digits.

## `.jsonl`

One JSON object per line, one record each. Every field value is a JSON string,
including one that holds only digits.

## `.toml`

A sequence of tables introduced by the line `[[record]]`. Each field of a
record is one line of the form `name = "value"`. The value is always quoted; a
double quote inside it is written as a backslash followed by a double quote,
and a backslash as two backslashes. Records are separated by a blank line.

## `.ini`

A sequence of sections whose headers are `[record_NNNNN]`, numbered from one
with five digits. Each field of a record is one line of the form
`name = value`. Values are never quoted and never escaped, and a value is
everything after the first equals sign with the surrounding spaces removed.

## `.properties`

One line per field, of the form `record.N.name = value`, where `N` counts
records from one and is the same for every field of one record. Records appear
in ascending `N` order. Inside a value a colon is written as a backslash
followed by a colon and an equals sign as a backslash followed by an equals
sign; a reader removes those backslashes. A value is everything after the first
unescaped equals sign with the surrounding spaces removed.

## `.logfmt`

One line per record. Fields are `name=value` pairs separated by single spaces,
in the field order of the group. A value that is empty, or that holds a space,
a double quote or an equals sign, is wrapped in double quotes; inside those
quotes a backslash is written as two backslashes, a double quote as a backslash
followed by a double quote, a newline as a backslash followed by `n` and a tab
as a backslash followed by `t`. A value needing none of that is written plain
and runs to the next space.

## `.sexp`

One line per record, of the form `(record (name "value") (name "value") ...)`.
Every value is quoted, with a backslash escaping a double quote and a backslash
doubled. Field order inside the record is the field order of the group.

## `.rfc5424`

One line per record, shaped as a syslog line. Everything up to the opening
square bracket is a header and carries no record data. The record sits in the
structured data element, which opens with `[lga@1 ` and closes with a square
bracket, and holds `name="value"` pairs separated by single spaces. Inside a
value a backslash is written as two backslashes and a double quote as a
backslash followed by a double quote. Further structured data elements, and
the free text message, may follow the record element on the same line; they
belong to no record and nothing in them is a field. A line carrying no such
element carries no record.
