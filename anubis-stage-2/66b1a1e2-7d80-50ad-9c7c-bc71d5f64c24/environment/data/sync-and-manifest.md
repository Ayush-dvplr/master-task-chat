# Synchronisation state and the manifest chain

## The status book

The status book named by the index (role `status`) is YAML
(tabular-conventions.md). Under `collections` it holds, per collection id and
per replica (`local`, `server`), a `sync_token` and a list of `entries`, each
with an `href`, an `etag` and a `revision`. Status entries are evidence, not
truth: the revision counters are used again when the merged state is written
back. A href absent from a replica's entries counts as revision zero there.

## Projections and entity tags

The synchronisation state has one entry per collection, in index order, and
inside each collection one entry per resource href that either replica holds in
that collection, sorted by href. A resource whose every key was tombstoned is
still listed, because the deletion has to be pushed to the side that kept it.

The projection of a resource is the list of merged components that share the
collection and the UID, sorted by raw recurrence identifier and then by
sequence. A tombstoned key has no merged component, so the merged projection of
a resource whose every key was tombstoned is the empty list. Each component
projects to an object with exactly these keys: `attendees`,
`duration_seconds`, `office`, `recurrence_id`, `sequence`, `start_utc`,
`summary` and `uid`. Every key is read from that component alone, with no
fallback to the master component: a component that carries no `X-OFFICE`
projects an empty office, one that carries no `SUMMARY` projects an empty
summary, and one that names no required participant projects an empty attendee
list. The attendee list holds the sorted distinct references exactly as
written, before any handle is resolved. The start instant is the resolved
`DTSTART` of that component. The duration seconds are computed for that
component with the store duration semantics as durations.md states, in the
zone of its own office, or of the first office listed in the office register
when it carries none.

The entity tag of a resource is a double quote, the lowercase hexadecimal
SHA-256 digest of the projection list, then a double quote. The digest is taken
over the UTF-8 bytes of the projection list serialised as report-contract.md
states for JSON, without the trailing line feed.

`changed_local` is true when the merged projection differs from the projection
built from the local replica alone. `changed_server` is the same test against
the server replica alone, as it stands after the outbox replay. A replica that
holds no component for that resource projects to an empty list.

The revision written back is the larger of the two status revisions for that
href, plus one when either change flag is true, and unchanged otherwise.

The synchronisation token of a collection is the collection id, a hyphen, and
the SHA-256 digest of the concatenation, over hrefs in sorted order, of the
href, a horizontal tab, the entity tag and a line feed.

## The manifest chain

The manifest chains the other reports in the fixed order given in
report-contract.md. The chain starts at the SHA-256 digest of the empty byte
string. For each report in order, the link digest is the SHA-256 digest of the
previous chain value, a line feed, the report's file name, a line feed, and the
SHA-256 digest of the exact bytes of that report on disk. The manifest records
the file digest and the running chain digest of every link, the starting value
as `chain_root` and the final value as `chain_head`.
