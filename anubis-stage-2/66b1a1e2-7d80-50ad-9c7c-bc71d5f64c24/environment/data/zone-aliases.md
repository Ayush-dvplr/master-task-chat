# Alternative zone names

Replicas written by different clients name the same zone in different ways. The
alias table named by the index (role `zone_aliases`) is a JSON object:

```json
{"format": "exec-ops-zone-aliases/1",
 "aliases": [{"alias": "US-Pacific", "target": "/EXEC-OPS/2027/America-Pacific", "status": "active"},
             {"alias": "Pacific Standard Time", "target": "US-Pacific", "status": "active"}]}
```

Every `TZID` parameter of an event property (`DTSTART`, `DTEND`,
`RECURRENCE-ID`, `EXDATE` and `RDATE`) is read through the table before any zone
is looked up: while the current name is the `alias` of an `active` entry, it is
replaced by that entry's `target`. A target may itself be an alias, so the walk
continues until a name that is not an active alias is reached; that name is the
zone. Entries whose `status` is anything other than `active` are ignored, so a
retired alias never redirects a name. A name that is not an alias is used as it
is.

Worked example. `Pacific Standard Time` becomes `US-Pacific`, which becomes
`/EXEC-OPS/2027/America-Pacific`; a `DTSTART` written in either alternative
name resolves exactly as one written in the zone's own name.

The zones of offices in the office register and the `TZID` of each
`VTIMEZONE` are always written in the zone's own name.

Reports always name a zone by its own name, never by an alias.
