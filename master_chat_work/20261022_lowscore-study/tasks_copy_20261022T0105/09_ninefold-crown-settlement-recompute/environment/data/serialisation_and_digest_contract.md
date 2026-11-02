# Serialisation and digest contract

## Encoding

Every delivered document is UTF-8 with line feed line endings, no
carriage return anywhere, and exactly one line feed at the end. A
delimited document writes its header row even when no row follows it. A
JSON document is written with an indent of one space and the key order
the schema reference lists; a colon and one space separate a key from its
value, and a line that continues ends with a comma and no space. A JSON
lines document writes one compact
object per line with a comma and a colon separator and no spaces, and its
keys in the schema order.

## Numbers

A whole quantity is written as a decimal integer with no plus sign, no
thousands separator and no decimal point. Zero is written as 0. A ratio
is written with exactly nine digits after the decimal point. A strength
is written in thousandths as a whole number. A prize amount is written in
whole cents.

## Empty shapes

An empty delimited document is its header row and one line feed. An empty
JSON list is written []. An empty JSON object is written {}. An empty JSON
lines document is a single line feed. A field with no value in a
delimited document is an empty field.

## XML

An XML document opens with the declaration
`<?xml version="1.0" encoding="UTF-8"?>` on its own line. Indentation is
one space per level of nesting. An element that carries no child element is
written as a single self closing tag with one space between the last
attribute and the closing slash. An element that carries child elements is
written as an opening tag, its children each on their own line, and a
closing tag at the indentation of the opening tag. Attribute values are
written in double quotes in the order the stage specification gives.

## Lists inside a field

A list written inside one delimited field joins its members with a plus
sign and no spaces, in the order the stage specification gives. A list
written inside a JSON value is a JSON array in that same order.

## Digests

The settlement manifest carries two digests, each the lowercase
hexadecimal SHA-256 of a concatenation of document bytes with no
separator.

- `core_digest` covers the six core documents, in the order the artifact
  contract of the settlement stage lists them.
- `publication_digest` covers every other delivered document except the
  manifest itself, in the order the artifact contract of the settlement
  stage lists them.

The manifest also carries one entry per delivered document except itself,
each with the document name, the lowercase hexadecimal SHA-256 of its
bytes and its byte length, in that same contract order.
