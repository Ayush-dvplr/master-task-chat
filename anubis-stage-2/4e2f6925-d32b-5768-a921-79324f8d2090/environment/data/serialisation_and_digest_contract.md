# Serialisation and digest contract

## Bytes

UTF-8 without a byte order mark. Line feed line endings. Exactly one trailing
line feed at the end of every file that has content. No trailing spaces.

## Numbers

A whole number is written without a sign when it is not negative, without
padding and without a thousands separator. Negative zero is written as 0.

A ratio is written with exactly twelve decimal places, produced by rounding the
exact value half to even. A ratio that rounds to zero is written 0.000000000000
whatever its sign.

Rounding is applied at write time. Every value above the write is exact,
except at the two carried roundings the chain names, the published dispersion
of stage T08 and the grid placement of every capping pass of stage T09.

## Delimited files

A comma separated file uses a comma, a tab separated file a tab and a pipe
separated file a vertical bar. No field is quoted and no field contains its
delimiter. The header row carries the column names in the order the schema
reference gives. A file with no data rows carries its header row alone.

## json

Two space indent, keys sorted at every level, ASCII escaping, one trailing line
feed.

Inside a json document a ratio is written as a json string carrying its twelve
decimal places, and a whole number is written as a json number. A whole number
is never quoted and a ratio is never written as a json number, whatever its
value. The same rule holds inside a json lines record.

## json lines

One compact object per line, keys sorted, separators a comma and a colon with
no spaces, one trailing line feed. A file with no records is zero bytes long.

## xml

The xml declaration <?xml version="1.0" encoding="UTF-8"?> on its own first
line, then the document, two space indent, line feed endings. An element with
no children is written as an opening tag immediately followed by its closing
tag.

## markdown

Headings and lines exactly as the schema reference gives them, one blank line
between a heading and the block under it.

## conf

Lines of the form key = value, one space either side of the equals sign, in the
order the schema reference gives.

## The digests

The core digest is sha256 over the concatenated bytes of the six core
artifacts, taken in the order ordering_dependencies.yaml lists under
digest_order.

The publication digest is sha256 over the concatenated bytes of the other
twenty six artifacts, taken in the order the table in
output_artifact_contract.md lists them, with the manifest itself left out.

Both are written as lower case hexadecimal, and both are taken over the bytes
as published, after rounding.
