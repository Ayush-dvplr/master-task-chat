# Report formats

The pruner writes three files into its output folder. Every file is UTF-8,
uses `\n` line ends and ends with a newline when it is not empty.

## keep.json

`{"series": {"<host>/<vol>": [{"id": "...", "reason": "..."}, ...]}}`

Every series with at least one accepted snapshot appears, even when nothing
in it is kept. Entries list kept snapshots in series order. The reason is the
name of the class that kept the snapshot, or `hold` or `parent`, or `anchor`,
the one word a mode bit introduces. The file is written with keys sorted and an
indent of two spaces.

## prune.jsonl

One line per pruned snapshot: `{"id": "...", "series": "...", "taken": "..."}`
with `taken` exactly as received. Lines run by series name, then series
order. Each line is compact JSON with keys sorted and no spaces. When nothing
is pruned the file still exists and is empty.

## summary.json

An object written with keys sorted and an indent of two spaces:

* `malformed`, `retransmitted`, `republished`: screening counts.
* `snapshots`: accepted distinct ids.
* `kept`, `pruned`: their split; they add up to `snapshots`.
* `held`: kept snapshots whose reason is `hold`.
* `parents`: kept snapshots whose reason is `parent`.
* `partial`: accepted snapshots in state `partial`.
* `holds`: valid rows in `holds.csv`.
* `plan_digest`: SHA-256, lowercase hex, of every kept line
  `<host>/<vol>/<id>` plus a newline, sorted and joined.
