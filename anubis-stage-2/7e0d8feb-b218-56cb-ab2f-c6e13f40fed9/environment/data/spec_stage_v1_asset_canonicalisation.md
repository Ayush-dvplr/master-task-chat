# V1 asset canonicalisation

Input: `ingest_attempt_register.csv`.

## R01 the natural key

The register holds one row per ingest attempt. The economic key of an asset
is `content_ref`. The `ingest_id` column identifies the attempt and not the
asset, so two rows carrying the same `content_ref` are two attempts at the
same asset and are clustered together.

## R02 the canonical attempt

Within a cluster the canonical attempt is the row with the greatest
`revision_no` among the rows whose `qc_state` is a passed state. The passed
states are exactly `QC_PASSED` and `QC_PASSED_WITH_NOTES`. The states
`QC_PENDING`, `QC_REJECTED` and `QC_WITHDRAWN` are not passed states.

A cluster in which no attempt carries a passed state has no canonical
attempt. It is excluded from every downstream stage and is published in the
asset register with the inclusion state `AS_EXCLUDED` and with every derived
field left empty.

The greatest `revision_no` in a cluster is frequently an attempt that did
not pass. The revision number alone never settles which attempt is
canonical.

## R03 the revision tie

When two or more passed attempts in one cluster carry the same
`revision_no`, the canonical attempt is the one whose `ingest_id` sorts
first as a string.

## R04 the house anchor

The house number published for an asset is the `house_no` of the cluster's
first received attempt, which is the attempt with the earliest
`received_at`, ties broken by the `ingest_id` that sorts first. The first
received attempt is called the anchor.

## R43 arrival is an instant

The ingest desks key `received_at` in their own zones, so every value is an
ISO 8601 date and time followed by its offset from UTC: `Z`, or a sign and
`hh:mm`. The earliest attempt is the one whose value names the earliest
instant once its offset is applied. Two values name the same instant when
they agree after their offsets are applied, however differently they are
written, and such a tie is broken by the `ingest_id`. The text of the value
is never the ordering key: compared as text, a time keyed at `+10:00` sorts
after one keyed at `-05:00` that arrived later. The anchor is computed for every
cluster, including a cluster with no canonical attempt.

The anchor is almost never the canonical attempt. The canonical attempt
supplies the rate code, the timecode mode and the timecodes; the anchor
supplies the house number and nothing else.

## Published

`asset_register.csv` carries one row per cluster, ordered by `content_ref`
ascending, with the columns named in output_schema_reference.md.
