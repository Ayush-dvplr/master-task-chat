SERIALISATION AND DIGEST CONTRACT
shift KP-2042-S23

SECTION 1  BYTES

Every published document is written in UTF-8 with no byte order
mark. Every line ends in one line feed and no carriage return
appears anywhere. Every document ends in exactly one line feed, and
no document ends in a blank line.

SECTION 2  DELIMITED DOCUMENTS

The header line is written first, then one line per row. A field is
written as it stands with no quoting, no padding and no thousands
separator. A field that has no value carries the not supplied marker,
which is one hyphen. An empty document is its header line and
nothing else, followed by one line feed.

SECTION 3  LINE DELIMITED JSON

One object per line, written with a comma between members and a
colon between a key and its value, with no space after either. Keys
appear in the order the schema reference lists and are never sorted.
An empty document is a file of zero bytes.

SECTION 4  JSON

Written with an indent of two spaces, keys in the order the schema
reference lists and never sorted, and one line feed after the closing
brace. An empty array is written as a pair of square brackets on one
line and an empty object as a pair of braces on one line.

SECTION 5  XML

The document opens with the declaration

    <?xml version="1.0" encoding="utf-8"?>

Every element is written with an opening tag and a closing tag, and
the self closing form is never used, not even for an element with no
content. Nesting is indented by two spaces per level. The five
characters that XML reserves are escaped and nothing else is.

SECTION 6  NUMBERS

A whole quantity is written as a plain integer with no sign when it
is zero and no leading zero. A ratio is written at exactly nine
decimal places. Money is written as a whole number of cents. Crane
minutes are written as whole minutes. Binary floating point appears
nowhere in the derivation and no value is published as a floating
point literal.

SECTION 7  DIGESTS

A digest is the SHA-256 of the bytes of a document, written in lower
case hexadecimal. The core digest and the publication digest are
each taken over a block built by writing, for every document the
digest covers and in the artifact order of the schema reference, the
document name, one space, the document digest and one line feed. The
manifest digests every document beside it and never itself.
