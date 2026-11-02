# Workspace lock conventions

These are the rules the resolver team wrote down before the resolver was lost.
Where this file and `handover.md` disagree, this file and the worked examples
govern. Six further rules were never written down; the worked examples follow
all of them.

## Input folder

An input folder holds five files with fixed names:

* `index.jsonl`: the package index feed, one JSON object per line.
* `workspace.json`: `{"members": [{"name": ..., "deps": {pkg: range}}, ...]}`.
* `pins.csv`: header `pkg,range,reason`, one pin per row.
* `lock.prev.json`: `{"packages": {pkg: {"version": ..., "sha": ...}}}`, the lock
  from the previous run. It may be empty.
* `manifest.json`: `{"mode": N, "reports": {...}, "members": {...}}`, the mode
  word the intake was settled under and digests of what settling it produced.

The worked examples carry the prefix `example_a_` or `example_b_` on every file,
and their expected outputs carry `example_a_out_` or `example_b_out_`.

## Versions

A version is `MAJOR.MINOR.PATCH` or `MAJOR.MINOR.PATCH-rc.N`, every part a
decimal number with no leading zero. Versions order by major, minor and patch.
For the same three numbers, every release candidate sorts before the release,
and candidates order by N.

## Ranges

A range is one or more groups joined by `|`; it is met when any group is met.
A group is one or more clauses joined by `,`; it is met when every clause is
met. Spaces around clauses are ignored. Clauses:

* `*` matches every version.
* `=V` matches V only.
* `>=V` and `<V` compare in version order.
* `^V` matches from V up to the next major, or for `0.M.P` with M above zero
  up to `0.(M+1).0`, or for `0.0.P` up to `0.0.(P+1)`; the upper end is a release
  and is excluded.
* `~V` matches from V up to `MAJOR.(MINOR+1).0`, excluded.

Any other text makes the range invalid.

## Screening the index feed

Blank lines are skipped and not counted. Every other line is classified in
file order:

* Malformed: not UTF-8, not JSON, not an object, or an object that is neither
  a publish nor a yank. A publish has exactly the keys `seq`, `pkg`, `ver`,
  `deps`, `sha`. A yank has exactly the keys `seq`, `pkg`, `ver`, `yank`, and
  `yank` is the JSON value `true`. In both, `seq` is a JSON integer of at least
  1 (not a boolean, not a float, not a string), `pkg` matches
  `^[a-z][a-z0-9-]{0,39}$`, and `ver` is a valid version. In a publish, `sha`
  is 40 lowercase hex digits and `deps` is an object whose keys are valid
  package names other than `pkg` itself and whose values are valid ranges.
* Retransmitted: a line whose object, compared with keys sorted, equals an
  object already accepted earlier in the file. It is dropped.
* Every other line is accepted.

A package version published more than once with different content is
republished. Only one copy is kept. Each extra copy counts once toward
`republished`.

A yank either applies, removing that package version from consideration, or
is ignored. A yank that names a version never published is ignored.

## Pins

A pins row whose `pkg` is not a valid name or whose `range` is invalid is
ignored. A valid pin narrows every pick of that package: a candidate must meet
both the requirement and the pin.

## Resolution

Requirements are processed first in, first out from one queue. The queue
starts with every member's requirements, members in `workspace.json` order.
When a package is picked, its kept copy's `deps` join the end of the queue.

For each requirement taken from the queue:

1. If the package is already picked, nothing changes. If the picked version
   does not meet the range, a conflict is recorded. Picks are never revised.
2. Otherwise the candidates are the kept, not yanked versions that meet the
   range and any pin. With no candidate an unresolved record is written and
   nothing is picked; a later requirement for the same package may still pick
   it.
3. Otherwise the previous lock entry for the package is honoured when allowed,
   which counts toward `sticky`. When it is not, the highest candidate is
   picked.

The requester (`by`) of a member requirement is `member:<name>`; the requester
of a dependency is `<pkg>@<version>` of the pick that declared it.

## Mode word

Everything above describes mode word zero, which both worked examples use.
The mode word uses seven bits, the values 2, 4, 8, 16, 32, 64 and 128; the
value 1 is reserved and always clear. Each set bit changes exactly one step of
screening, pinning, queueing, picking or the walk through `deps`, and none of
them changes a report format. What each bit does was never written down.

In `manifest.json`, `reports` maps each report file name to the lowercase hex
SHA-256 of that file's bytes. `members` maps each member name to the
lowercase hex SHA-256 of that member's share of the lock: the lines
`<pkg>@<version>:<sha>\n` for every pick whose `via` chain, followed back
through the picks it names, ends at `member:<name>`, sorted and concatenated.
