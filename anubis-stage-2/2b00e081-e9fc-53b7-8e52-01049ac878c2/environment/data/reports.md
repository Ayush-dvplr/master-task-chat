# Reports

The replay writes three files into its output folder. Every file is UTF-8 with
`\n` line endings and ends with a newline when it is not empty.

## locks.json

The lock table after the last record:

    {"bans": {"<src>": {"until": U}, ...}, "locks": {"<user>": {"strikes": S, "until": U}, ...}}

written with `json.dumps(doc, sort_keys=True, indent=2)` plus a newline. Under
mode word zero `bans` is always `{}`. An empty table is
`{"bans": {}, "locks": {}}`.

## decisions.jsonl

One line per accepted record in replay order:

    {"at": A, "kind": K, "result": R, "seq": S, "src": I, "user": U}

written with `json.dumps(rec, sort_keys=True, separators=(",", ":"))` plus a
newline. `result` is one of `allow`, `fail`, `lock`, `deny`, `unlock`, `ban`
and `ignore`. The file exists even when it has no lines.

## summary.json

Written with `json.dumps(doc, sort_keys=True, indent=2)` plus a newline, with
exactly these keys:

* `malformed`, `retransmitted`, `conflicting`: screening counts.
* `events`: accepted records replayed.
* `allows`, `fails`, `locks`, `denies`, `unlocks`, `bans`, `ignored`: lines of
  `decisions.jsonl` with each result.
* `active`: entries under `locks` in `locks.json`.
* `banned`: entries under `bans` in `locks.json`.
* `overrides`: distinct users with a valid `overrides.csv` row.
* `table_digest`: SHA-256 hex digest of the lines `<user> <until>\n` for every
  entry under `locks` in `locks.json`, sorted and joined with nothing between
  them.
