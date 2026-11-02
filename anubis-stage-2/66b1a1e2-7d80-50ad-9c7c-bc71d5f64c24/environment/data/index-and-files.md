# Store index and file roles

## Locating the index

The store index is the one file in the store directory whose content is a JSON
object with the key `format` equal to `exec-ops-store/2`. Its file name carries
no meaning and differs from store to store, so the index is found by reading
the files, never by name. Other JSON documents in the directory carry other
`format` values or none. A directory holding no such file, or more than one, is
not a store.

## What the index records

```json
{
  "format": "exec-ops-store/2",
  "files": {"zones": "...", "zone_aliases": "...", "register": "...", "...": "..."},
  "store": {
    "id": "primary",
    "conflict_policy": "sequence-major",
    "duration_semantics": "nominal",
    "authority_replica": "local",
    "policy_revision": 6,
    "register_edition": "R7",
    "window": {"start": "2027-01-01", "end": "2027-12-31"},
    "collections": [
      {"id": "cal-alpha", "href": "/cal/cal-alpha/", "replicas": {"local": "...", "server": "..."}}
    ]
  }
}
```

`files` maps a role to a file name in the same directory. The roles are:

| Role | Content | Documented in |
|---|---|---|
| zones | VTIMEZONE rules as iCalendar text | zone-rules.md |
| zone_aliases | alternative zone names | zone-aliases.md |
| register | office register and attendee rates, XLSX | office-register.md |
| governance | escalation and treasury schedule, PDF | governance-schedule.md |
| attendees | attendee register, tab separated | identities-and-aliases.md |
| aliases | attendee handles, comma separated | identities-and-aliases.md |
| itineraries | flight legs, XML | travel-and-busy.md |
| closures | office closures, SQLite | attendance.md |
| freebusy | published busy periods, SQLite | travel-and-busy.md |
| status | synchronisation agent status book, YAML | sync-and-manifest.md |
| journal | change log, current shard, one JSON object per line | journals.md |
| journal_legacy | change log, legacy shard, one JSON object per line | journals.md |
| outbox | pending operations, pipe separated | outbox-replay.md |
| escalation_draft | lower authority digest of the governance schedule, YAML | authority-and-audit.md |
| office_snapshot | lower authority snapshot of the register, comma separated | authority-and-audit.md |
| payroll_export | lower authority export of attendee rates, semicolon separated | authority-and-audit.md |
| zone_cache | transitions cached by the retired scheduler, tab separated | authority-and-audit.md |
| previous_run | per series counts printed by the retired scheduler, JSON | authority-and-audit.md |

`store` describes the one store the pass processes. `collections` is ordered
and that order is the collection priority order; earlier entries have higher
priority. Each collection names its `local` and its `server` replica file. The
encoding of a replica file is decided by its content, as encoding-icalendar.md
explains, and a store may use a different encoding for every replica.

The resource href of a calendar object is the collection `href` followed by the
UID and the suffix `.ics`, whatever the encoding of the replica that holds it.

## The window

`window` holds two inclusive dates. The store window runs from midnight UTC on
the start date up to but not including midnight UTC on the day after the end
date.

## Policy settings

`conflict_policy` is `sequence-major` or `mtime-major` (merge-ladder.md).
`duration_semantics` is `exact` or `nominal` (durations.md). `authority_replica`
names the replica that wins the last step of the merge ladder.
`policy_revision` takes part in fixing the effective revision
(governance-schedule.md). `register_edition` selects the register sheets in
force (office-register.md).
