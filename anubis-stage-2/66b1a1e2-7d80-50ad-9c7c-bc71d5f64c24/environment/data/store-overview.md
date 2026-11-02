# EXEC-OPS calendar store, revision v5

Owner: Executive Operations, Calendar Platform group.
Status: effective 2027-01-01, supersedes revision v4.

This folder documents the offline reconciliation pass that rebuilds the 2027
executive schedule from a two replica CalDAV store and derives every ledger
that hangs off that schedule. The rules are split across the documents listed
below. Each document owns one stage; where two documents seem to disagree, the
amendments document says which text is in force, and an amendment replaces the
rule it names wherever that rule appears, including an earlier amendment.

| Document | Owns |
|---|---|
| index-and-files.md | locating the store index and every other file |
| encoding-icalendar.md | iCalendar content lines |
| encoding-xcal.md | the XML calendar encoding |
| encoding-jcal.md | the JSON calendar encoding |
| tabular-conventions.md | YAML, pipe separated, comma and tab separated files, SQLite tables, the itinerary XML |
| governance-schedule.md | the PDF schedule, the effective revision, settling parameters, ranks, conversion rates |
| office-register.md | the XLSX register, weekday rows, serial dates, attendee rates |
| zone-rules.md | VTIMEZONE observances, offsets, wall clock resolution |
| zone-aliases.md | alternative zone names |
| recurrence-rules.md | RRULE expansion |
| additional-dates.md | RDATE candidates |
| exclusions-and-overrides.md | EXDATE, RECURRENCE-ID, collisions, ranged overrides |
| durations.md | lengths of occurrences |
| merge-ladder.md | replica precedence, tombstones, duplicate identifiers |
| journals.md | the two change log shards |
| outbox-replay.md | pending operations replayed into the server replica |
| identities-and-aliases.md | attendee identifiers, handles, delegation |
| conflicts-and-settling.md | overlap, buffer, escalation, the settling loop |
| travel-and-busy.md | legs, effective office, travel blocks, busy periods |
| attendance.md | working windows, closures, non working days |
| load-model.md | the circadian load fold |
| chargeback.md | meeting cost conversion and allocation |
| sync-and-manifest.md | entity tags, revisions, tokens, the manifest chain |
| authority-and-audit.md | lower authority sources, the authority audit, the drift report |
| report-contract.md | the layout and serialisation of every report |
| amendments.md | amendments that replace rules stated elsewhere |

Every quantity is computed from files inside the store directory. No network
service is contacted and no operating system timezone database is consulted.

The store described by these documents is one instance. The same program is
run over other stores built under the same rules, with different file names,
different encodings for each replica, different policy settings, different
offices in force and different amounts of data, so every rule has to be implemented
in general.

## Order of the stages

The stages consume one another in this order, and each later stage reads the
decisions of the earlier ones, not merely their files: locate the index; read
the registers and the governance schedule and fix the effective revision;
replay the outbox into the server replica; merge the replicas; expand the
series, apply exclusions and overrides and resolve attendee handles on each
occurrence; detect conflicts and settle; then derive the load fold, attendance,
travel blocks, busy conflicts, the chargeback, the synchronisation state, the
authority audit, the drift report and the manifest.
