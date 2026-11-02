# Serialisation and digest contract

Every document is UTF-8 with a single line feed ending every line, including
the last. No carriage returns and no byte order mark.

A json document is written with two space indentation, keys sorted, and one
trailing newline after the closing brace. A jsonl document is one compact json
object per line, keys sorted, no spaces after the separators.

A delimited document carries its header line first and then its rows. A csv is
separated by commas, a tsv by tabs, a psv by vertical bars. No field is
quoted, because no field carries a separator. An empty field is written as
nothing at all.

A digest is the sha256 of the bytes of the file as written, in lower case hex.
The digests of the manifest are taken last, after the twenty four documents
before it are on disk, and the closing digest of the manifest is taken over
the lines above it joined by line feeds with a trailing line feed.
