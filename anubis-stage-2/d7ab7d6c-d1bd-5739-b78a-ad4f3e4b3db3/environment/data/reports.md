# Report formats

Every replay writes three files into its output folder. All files are UTF-8
and end with a newline.

## sessions.json

`json.dumps(doc, sort_keys=True, indent=2)` followed by a newline, where `doc` is

    {"sessions": {server: {"clan": clan, "player": player, "until": until}, ...},
     "cooldowns": {server: {"until": until}, ...}}

`sessions` holds every session still live at the last replayed second and
`cooldowns` every server still cooling down at that second. Either may be empty.

## decisions.jsonl

One line per replayed record, in replay order:
`json.dumps(row, sort_keys=True, separators=(",", ":"))` followed by a newline,
where `row` is `{"at", "kind", "player", "result", "seq"}` taken from the record.
`result` is one of `claim`, `extend`, `release`, `refuse` and `ignore`. When no
record is replayed the file is empty.

## summary.json

`json.dumps(summary, sort_keys=True, indent=2)` followed by a newline, with the keys

* `malformed`, `retransmitted`, `conflicting`: lines dropped by screening steps 2, 3 and 4.
* `events`: records replayed.
* `claims`, `extends`, `releases`, `refusals`, `ignored`: records with each result.
* `active`: entries in `sessions`.
* `cooling`: entries in `cooldowns`.
* `owned`: players with an owned server after `owned.csv` is read.
* `table_digest`: the SHA-256 hex digest of the lines `<server> <player>\n` for
  the entries of `sessions`, sorted and joined with nothing between them.
