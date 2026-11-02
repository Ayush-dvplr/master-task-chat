# Serialisation and digest contract

Encoding is utf-8 with no byte order mark. Line endings are line
feed. Every text document ends with exactly one trailing newline.

Indented json is written with sorted keys, two space indentation and
a trailing newline. A json lines document writes one compact record
per line with sorted keys and the separators `,` and `:` carrying no
surrounding space. A delimited document writes its header line
first, then one line per row, with no quoting and no padding.

Every whole quantity is a json integer or a bare integer field. No
quantity is written as a decimal. Every ratio is a string carrying
exactly twelve decimal places, half away from zero, and negative
zero is never written.

## Checkpoint digest

The digest of a checkpoint body is the lowercase hexadecimal sha256
of the compact json of the object holding exactly the keys
`position`, `balances`, `allotments`, `counters`, `pending`,
`applied` and `reversed`, with sorted keys and the compact
separators. `applied` and `reversed` are written sorted ascending;
`pending` keeps its queue order.

## Run manifest

`run_manifest.txt` carries two lines. The first is `core` followed
by a space and the sha256 of the concatenated bytes of the documents
`publication_form_rules.toml` names, in the order it names them. The
second is `publication` followed by a space and the sha256 of the
concatenated bytes of every published document except `package.zip`
and `run_manifest.txt`, taken in ascending file name order. Both
digests are taken last, over the bytes already on disk.
