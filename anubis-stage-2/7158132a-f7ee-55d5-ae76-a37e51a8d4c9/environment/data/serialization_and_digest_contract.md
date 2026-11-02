# serialization and digest contract

Artifacts are compared byte for byte, so the shape below is as binding
as the arithmetic.

## delimited files

csv uses a comma, tsv a tab, psv a vertical bar. The first line is the
header, holding the column names in the order the stage document gives
them. One line per row after it. Every line ends with a single line
feed, including the last. There is no carriage return anywhere.

No field is quoted and no field contains a delimiter, a quote or a line
feed. Integers are written in decimal with no sign for zero and no
leading zeros. A field documented as empty is written as the empty
string, so two delimiters sit together.

A delimited artifact with no rows is the header line alone, followed by
one line feed.

## jsonl and ndjson

One JSON object per line, keys sorted ascending, no space after the
comma or the colon, ASCII only. Every line ends with a line feed,
including the last.

A jsonl artifact with no rows is a file of zero bytes. It is not a file
containing one line feed and it is not a file containing an empty array.

## json

One JSON document, keys sorted ascending, indented by two spaces, ASCII
only, followed by a single trailing line feed.

## xml

The declaration line first, exactly

    <?xml version="1.0" encoding="UTF-8" standalone="yes"?>

then one element per line with no indentation, and a single trailing
line feed. Attribute values are in double quotes. An element with no
children is written with an open tag and a close tag, never self
closing.

## markdown

The layout in output_schema_reference.md, with a single trailing line
feed.

## the digest

core_digest is the sha256, in lower case hexadecimal, of the
concatenation of the bytes of the twenty nine core artifacts in the
order given by output_artifact_contract.md. per_artifact_sha256 maps
each core artifact name to the sha256 of its own bytes.
stage_digest_manifest.json is not itself a core artifact and does not
enter its own digest. artifact_count is twenty nine and stage_count is
fourteen.
