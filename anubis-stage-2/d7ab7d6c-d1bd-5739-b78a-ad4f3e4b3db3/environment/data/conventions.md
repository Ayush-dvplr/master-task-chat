# Arena slot journal conventions

These notes describe how the old replay tool turned a game server request
journal into a session table. They were written from memory after the tool was
lost. Where a point is not covered here, the worked examples are the only record.

## Input files

Every intake folder holds five files.

* `requests.jsonl` is the journal, one JSON object per line.
* `servers.json` lists the game servers and their slot counts.
* `owned.csv` gives some players a server of their own.
* `sessions.prev.json` is the session table left by the previous replay.
* `manifest.json` carries the mode word and the digests of the expected reports.

## Journal records

A record has exactly the keys `seq`, `kind`, `player`, `at`, `party`, `span`,
`server` and `clan`.

* `seq` is an integer of at least 1. A boolean, a float or a string is not an integer.
* `kind` is one of `claim`, `extend`, `release` and `ping`.
* `player` is a lowercase letter followed by up to thirty lowercase letters,
  digits, dots, underscores or hyphens.
* `at` is an integer number of seconds, zero or more.
* `party` is an integer party size from 1 to 40.
* `span` is an integer number of seconds, at least 60 and a whole number of minutes.
* `server` is null or a server hint: a lowercase letter followed by up to twenty
  lowercase letters, digits or hyphens.
* `clan` is null or a lowercase letter followed by up to fifteen lowercase
  letters, digits or hyphens.

## Screening

Lines are read top to bottom.

1. A blank line is skipped and counted nowhere.
2. A line that is not UTF-8 JSON, is not an object, or breaks a rule above is
   malformed and is dropped.
3. A line whose content, keys sorted, matches an earlier line that got past
   step 2 exactly is a retransmission and is dropped.
4. A line that reuses the `seq` of an earlier accepted line with different
   content is conflicting and is dropped; the earlier line stands.

Accepted records are replayed in order of `at`. Records that share one second
are put in an order the notes never recorded.

## Servers, owned servers and the previous table

`servers.json` holds `{"servers": [{"name", "slots"}, ...]}`. A row counts only
when its name follows the server hint pattern and `slots` is an integer of at
least 1. When a name appears on more than one counted row, the first row stands.

`owned.csv` starts with the header `player,server,note`. A row counts only when
it has three fields, a valid `player` and a server listed in `servers.json`.
Some players appear on more than one counted row; which row stands was never
written down. An owned server is kept for its owner: nobody else is ever placed
on it.

`sessions.prev.json` holds `{"sessions": [{"server", "player", "until", "clan"}, ...]}`.
Rows with a listed server, a valid `player`, an integer `until` and a valid or
null `clan` seed the table in file order, skipping a server already seeded. A
seeded session counts as that player's latest session.

## Replay

How a session stands at the very second of its `until` is one of the unwritten
rules; before that second it is live and after it it is over. A server is free
for a player and a party when it is listed, has at least that many slots, has no
live session, is not cooling down, and is not someone else's owned server.

* `claim`: a player who already holds a live session gets `refuse`. Otherwise
  the owned server of the player is taken when free. Then the `server` hint is
  taken when free. Then the servers are scanned in an order the notes never
  recorded, and the first free server is taken. When a server is taken the
  session runs from `at` for `span` seconds and the result is `claim`; when
  nothing is free the result is `refuse`.
* `extend`: a player holding a live session has its `until` pushed back by
  `span` and the result is `extend`. Otherwise the result is `ignore`.
* `release`: a player holding a live session loses it and the result is
  `release`. Otherwise the result is `ignore`.
* `ping`: the result is `ignore`.

After the last record, the table holds every session still live at the last
record's `at`, and every server still cooling down at that second.

## Rules nobody wrote down

Six rules were never written down. Every worked example follows every one of them.

1. The order in which servers are scanned when neither an owned server nor the
   hint is taken.
2. Whether a session is still live at the very second of its `until`.
3. Which of several counted `owned.csv` rows for one player stands.
4. What happens to a server right after its session is released.
5. Whether a player who played before is offered that server again.
6. The order of records that share one second.

## Mode word

`manifest.json` holds `{"mode": N, "reports": {...}, "tables": {...}}`.

The mode word uses seven bits, the values 2, 4, 8, 16, 32, 64 and 128; the
value 1 is reserved and always clear. Each set bit changes exactly one step,
and none of them changes a report format. The step each bit touches is known;
what it does there was never written down.

* Bit 2 touches how the `server` hint of a claim is used.
* Bit 4 touches seeding from `sessions.prev.json`.
* Bit 8 touches how long a released server cools down.
* Bit 16 touches what happens when a player's owned server cannot be used.
* Bit 32 touches screening step 3, the retransmission check.
* Bit 64 touches an `extend` from a player with no live session.
* Bit 128 touches the `clan` field, which matters under no other bit.

Worked examples `example_a_` and `example_b_` use mode word zero.
`example_c_` uses mode word 170 (bits 2, 8, 32 and 128) and `example_d_` uses
mode word 84 (bits 4, 16 and 64), so every bit is set in exactly one worked
example, and in each of those two examples every set bit changes the answers.
They follow the six unwritten rules as well.

`reports` maps each report file name to the SHA-256 hex digest of that file's
bytes. `tables` maps `sessions` and `cooldowns` to the SHA-256 hex digest of the
lines `<server> <player>\n` and `<server> <until>\n` for the entries of the
matching table in `sessions.json`, sorted and joined with nothing between them.

## Authority

Where these notes or the worked examples disagree with `handover.md`, these
notes and the worked examples govern.
