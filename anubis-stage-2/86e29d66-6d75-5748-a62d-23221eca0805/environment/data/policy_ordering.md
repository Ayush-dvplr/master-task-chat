# Ordering policy

## Roles come from content

Every file in the archive declares its own role.

A file whose name ends in `.json` holds one object with a `document` key. That value
is the role. The roles in use are `schedule_base`, `schedule_phases`,
`accumulation_policy`, `restart_exceptions`, `profiles`, `cadence`, `eval_probes`
and `restarts`.

A file whose name ends in `.csv` holds a header row. The set of column names is the
role. Several files may share one header; their rows join into one table.

A file whose name ends in `.jsonl` holds one JSON object per non blank line. The
`record` key names the line kind, either `micro` or `marker`.

File names, directory listing order and line order carry no authority at all. A file
named for a segment may hold the lowest sequences in the run, and often does.

## The single ordered stream

The run is one stream. Gather every line of every `.jsonl` file, then order the
stream by ascending `sequence`. The `sequence` field is a positive integer and is
the only ordering key. Nothing else orders the run.

Two lines may claim the same sequence. In that case compute the canonical
serialization of each claimant, as defined in `policy_serialization.md`, and keep the
claimant whose serialization sorts first by byte value. Every other claimant with
that sequence is counted once under the rejection reason `duplicate_sequence` when it
is a micro line, and is dropped silently when it is a marker line.

Worked example. Two micro lines both claim sequence 118. Their canonical forms begin
`{"examples":42,...` and `{"examples":48,...`. The byte `2` sorts before the byte
`8`, so the line with 42 examples is kept and the line with 48 examples is counted
once as `duplicate_sequence`.

## Phase timeline

A marker line with kind `phase_open` opens a phase at its sequence. The phase in
force at a sequence is the phase opened by the latest opening at or before that
sequence. Openings that share one sequence are first resolved by the canonical
shared-sequence selection above, so only the surviving marker can open a phase.

Worked example. Openings are p1 at sequence 1, p2 at sequence 60 and p3 at sequence
110. A micro record at sequence 59 sits in p1. A micro record at sequence 60 would
sit in p2, and so does every record up to sequence 109.

## Shard ownership timeline

A shard starts under the owner named in the manifest. Each shard move row replaces
that owner from its `effective_sequence` onward. The owner in force for a shard at a
sequence is given by the move row for that shard with the largest
`effective_sequence` that is less than or equal to the sequence; when two such rows
share one effective sequence, the row whose `to_owner` sorts last by byte value wins.
When no move row applies, the manifest owner stands.

Worked example. The manifest gives shard sh-05 to w2. A move row sends sh-05 from w2
to w4 with effective sequence 70. A micro record for sh-05 at sequence 54 belongs to
w2. A micro record for sh-05 at sequence 118 belongs to w4. A move row with an
effective sequence past the last sequence in the stream never takes effect.

## Manifest agreement

Manifest rows for one shard must agree on `owner`, `example_count` and `status`. Sort
the manifest rows by ascending `order_key`. The first row seen for a shard sets its
owner, example count and status. Every later row for that shard that disagrees on any
of those three values raises one `manifest_conflict` event and changes nothing.

## Late segments

A segment file may arrive after the run and hold sequences that belong early in the
stream. Fold it into position by sequence. An implementation that walks files in name
order, or lines in file order, builds a different run and reports different numbers.
