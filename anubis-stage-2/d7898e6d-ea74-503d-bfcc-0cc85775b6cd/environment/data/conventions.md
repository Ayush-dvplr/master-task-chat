# Snapshot retention conventions

The pruner reads one intake folder and decides, for every snapshot of every
series, whether it is kept or pruned. These notes are what survived of the
old pruner's design file.

## Input files

An intake folder holds four files. The worked examples carry the same four
files with an `example_a_` or `example_b_` prefix.

* `snapshots.jsonl`: one snapshot record per line, written by the hosts as
  they took snapshots and relayed through a collector.
* `policy.json`: retention counts, `{"default": {...}, "hosts": {"<host>": {...}}}`.
* `holds.csv`: hold requests from the audit desk.
* `manifest.json`: `{"mode": N, "reports": {...}, "hosts": {...}}`.

## Snapshot records

A record is a JSON object with exactly the keys `seq`, `host`, `vol`, `id`,
`taken`, `size`, `parent` and `state`, in any order.

* `seq` is an integer of at least 1 (true and false are not integers).
* `host` and `vol` match `^[a-z][a-z0-9-]{0,30}$`.
* `id` matches `^s[0-9a-f]{12}$`.
* `taken` is `YYYY-MM-DDTHH:MM:SS` followed by `Z` or a `+HH:MM` or `-HH:MM`
  offset. The date and time must exist on the calendar, the offset hours are
  at most 14 and the offset minutes at most 59. The stamp is the host's local
  wall clock together with its offset from UTC.
* `size` is an integer of at least 1.
* `parent` is null or another snapshot id. A record may not name itself.
* `state` is `ok` or `partial`.

A series is one `host` and `vol` pair, written `host/vol`.

## Screening

Lines are screened in file order.

* A line that is empty or holds only whitespace is skipped and counted nowhere.
* A line that is not UTF-8, not JSON, or breaks any rule above is malformed.
* A line whose content, keys sorted, is identical to a line accepted earlier
  is a retransmission and is dropped.
* An id that arrives on several accepted lines whose content differs in
  anything besides `seq` is republished. It is counted once, and exactly one
  of its copies is used.

The `parent` field may name an id that never arrived. Such a link simply ends.

## Policy

`policy.json` gives counts for the four retention classes `hourly`, `daily`,
`weekly` and `monthly`, and may give `max_bytes`. A host listed under
`hosts` uses its own entry in place of `default` as a whole; a class missing
from the entry used keeps nothing.

## Holds

`holds.csv` starts with the header `id,until,reason`. A valid row has exactly
three fields, a well formed snapshot id and an `until` date written
`YYYY-MM-DD` that exists on the calendar. Other rows are ignored. A hold whose
id is not in any series does nothing.

A hold is compared with the calendar date of the newest snapshot in its
series. An active hold keeps its snapshot with reason `hold`, whatever reason
it already had.

## Choosing what to keep

Within a series, snapshots are ordered by their UTC instant, then by id.

The classes run in the order hourly, daily, weekly, monthly. Each class sorts
the eligible snapshots of the series into buckets (an hour, a day, a week, a
month) and keeps one representative from each of its newest N buckets, where
N is its count. A snapshot already kept by an earlier class keeps its first
reason. Holds come after the classes. Last, every kept snapshot keeps its
parent chain: each ancestor present in the same series is kept with reason
`parent` if it was not already kept.

## Rules nobody wrote down

Six further rules were never written down: which member of a bucket stands
for it, the day a week starts on, whether a hold still counts on its `until`
date, whether a partial snapshot may stand for a bucket, which copy of a
republished id is used, and which clock the buckets and dates are read on.
Both worked examples follow all six.

## Mode word

The worked examples use mode word zero. The mode word uses seven bits, the
values 2, 4, 8, 16, 32, 64 and 128; the value 1 is reserved and always clear.
Each set bit changes or adds exactly one step of screening, bucketing, holds,
the byte budget or the parent walk, and none of them changes a report format.
What each bit does was never written down.

In `manifest.json`, `reports` maps each report file name to the SHA-256 of
its bytes, and `hosts` maps each host to the SHA-256 of that host's kept
lines. A kept line is `<host>/<vol>/<id>` followed by a newline; a host's
lines are sorted and joined before hashing.

## Authority

Where these notes and `handover.md` disagree, these notes and the worked
examples govern.
