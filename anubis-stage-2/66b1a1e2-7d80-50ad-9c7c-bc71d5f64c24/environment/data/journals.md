# The change log

The change log is kept in two shards named by the index: the current shard
(role `journal`) and the legacy shard (role `journal_legacy`). Both hold one JSON
object per line, but they name their fields differently.

Current shard:

```json
{"revision": 9, "collection": "cal-alpha", "replica": "local", "uid": "HX-AKL-EARLY-2027",
 "recurrence_id": "", "op": "update", "recorded_utc": "20270330T210000Z", "note": "attendee list refreshed"}
```

Legacy shard:

```json
{"rev": 14, "cal": "cal-alpha", "side": "S", "object": "HX-AKL-EARLY-2027", "rid": null,
 "action": "PUT", "at": "20270330T213700Z"}
```

| Current | Legacy | Meaning |
|---|---|---|
| `revision` | `rev` | revision counter |
| `collection` | `cal` | collection id |
| `replica` | `side` | `local` is `L`, `server` is `S` |
| `uid` | `object` | UID |
| `recurrence_id` | `rid` | raw recurrence identifier, empty for a master; the legacy shard writes it in extended form, or `null` for a master |
| `op` | `action` | the current shard writes `create`, `update` or `delete`; the legacy shard writes `PUT` for a create or an update and `DEL` for a delete |

A legacy `rid` such as `2027-03-10T08:30:00` is the basic value
`20270310T083000`, which is how it matches a raw `RECURRENCE-ID`.

A record is identified by its collection, replica, UID, recurrence identifier
and revision. When both shards hold a record with the same identity, the
current shard is in force and the legacy record is ignored, even when the two
disagree about whether the record was a deletion. Every other record of either
shard is part of the change log.

The change log takes part in the merge in two ways only, both described in
merge-ladder.md: the revision number of a key and a replica, which counts no
deletion, and the deletion test that tombstones a key held by one replica.
