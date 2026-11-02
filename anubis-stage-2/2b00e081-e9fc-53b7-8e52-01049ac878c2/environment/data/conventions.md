# Lockout journal conventions

These notes describe how the old replay tool turned a sign-in attempt journal
into a lockout table. They were written from memory after the tool was lost.
Where a point is not covered here, the worked examples are the only record.

## Input files

Every intake folder holds five files.

* `attempts.jsonl` is the journal, one JSON object per line.
* `policy.json` holds the lockout policy.
* `overrides.csv` gives some users their own failure limit.
* `locks.prev.json` is the lock table left by the previous replay.
* `manifest.json` carries the mode word and the digests of the expected reports.

## Journal records

A record has exactly the keys `seq`, `kind`, `user`, `src`, `at` and `agent`.

* `seq` is an integer of at least 1. A boolean, a float or a string is not an integer.
* `kind` is one of `reset`, `pass`, `fail` and `probe`.
* `user` is a lowercase letter followed by up to thirty lowercase letters,
  digits, dots, underscores or hyphens.
* `src` is a dotted quad address with no leading zeros and every part at most 255.
* `at` is an integer number of seconds, zero or more.
* `agent` is null or one to forty characters drawn from ASCII letters, digits,
  `/`, `.`, `_` and `-`.

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

## Policy, overrides and the previous table

`policy.json` holds `{"window", "threshold", "lock", "ban_after", "ban"}`, all
integer seconds or counts. `window` is how far back failures are counted,
`threshold` is the failure limit for a user without an override and `lock` is
the base lock length.

`overrides.csv` starts with the header `user,limit,note`. A row counts only when
it has three fields, a valid user name and a limit that is a single digit from
1 to 9. Some users appear on more than one valid row; which row stands was never
written down.

`locks.prev.json` holds `{"locks": [{"user", "until", "strikes"}, ...]}`. Rows
with a valid user, an integer `until` and an integer `strikes` of at least 1
seed the table in file order, skipping a user already seeded. A seeded user
starts with that lock end and that strike count and no counted failures.

## Replay

Each user has a list of counted failures, a lock end and a strike count. A user
is locked at second `t` when it has a lock end and `t` has not yet passed it;
how the very second of the lock end is treated is one of the unwritten rules.

* `fail`: a locked user gets `deny`. Otherwise failures that have fallen out of
  the window are dropped, this one is added, and when the count reaches the
  user's limit the strike count goes up by one, the user is locked from `at`
  for the lock length, the failure list is emptied and the result is `lock`.
  Otherwise the result is `fail`.
* `pass`: an unlocked user gets `allow` and its failure list is left as it is.
  What a locked user gets is one of the unwritten rules.
* `reset`: the failure list and the lock end are cleared; the strike count is
  kept. The result is `unlock` when the user was locked at that second and
  `ignore` otherwise.
* `probe`: the result is `ignore`.

After the last record, the table holds every user still locked at the last
record's `at`.

## Rules nobody wrote down

Six rules were never written down. The worked examples follow every one of them.

1. Whether a user is still locked at the very second of its lock end.
2. Whether a failure exactly `window` seconds old still counts.
3. Which of several valid `overrides.csv` rows for one user stands.
4. What a `pass` from a locked user gets.
5. How long a lock lasts when a user is locked again.
6. The order of records that share one second.

## Mode word

`manifest.json` holds `{"mode": N, "reports": {...}, "tables": {...}}`. The
worked examples all use mode word zero.

The mode word uses seven bits, the values 2, 4, 8, 16, 32, 64 and 128; the
value 1 is reserved and always clear. Each set bit changes exactly one step of
screening, seeding, limits, failure counting, source handling or lock handling,
and none of them changes a report format. What each bit does was never written
down. The `ban_after` and `ban` policy fields are read only under one of them.

`reports` maps each report file name to the SHA-256 hex digest of that file's
bytes. `tables` maps `locks` and `bans` to the SHA-256 hex digest of the lines
`<user> <until>\n` and `<src> <until>\n` for the entries of the matching table
in `locks.json`, sorted and joined with nothing between them.

## Authority

Where these notes or the worked examples disagree with `handover.md`, these
notes and the worked examples govern.
