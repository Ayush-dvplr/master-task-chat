# Report formats

The resolver writes three files into its output folder. All text is UTF-8
with `\n` line ends and a final newline where a file is not empty.

## lock.json

`{"packages": {pkg: {"sha": ..., "version": ..., "via": ...}}}` with one entry
per picked package; `via` is the requester that caused the pick. Written as
JSON with sorted keys and an indent of two spaces, followed by a newline.

## issues.jsonl

One JSON object per conflict or unresolved record, in the order the records
were made, each with sorted keys and no spaces (separators `,` and `:`):

* conflict: `kind` `"conflict"`, `pkg`, `range` (as written by the requester),
  `by`, `picked` (the version already picked).
* unresolved: `kind` `"unresolved"`, `pkg`, `range`, `by`.

When there are no records the file exists and is empty.

## summary.json

Sorted keys, indent of two spaces, final newline. Keys:

* `malformed`, `retransmitted`, `republished`: screening counts.
* `yanks_applied`, `yanks_ignored`: accepted yank lines in each outcome.
* `picked`: packages in the lock.
* `sticky`: picks that honoured the previous lock.
* `conflicts`, `unresolved`: records of each kind in `issues.jsonl`.
* `pins`: valid pins in force after reading `pins.csv`.
* `lock_digest`: lowercase hex SHA-256 of the lines `<pkg>@<version>:<sha>\n`,
  one per picked package in package name order, concatenated.
