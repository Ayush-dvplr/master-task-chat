# Quillfen Scheduled Commitment Settlement Contract

Revision 7. Owner: Platform Reliability. Applies to every settlement run from the March 2026 period onward.

This contract defines what a settlement run of the Quillfen platform must conclude from one settlement extract. The
extract is a directory of exports from the systems that schedule, run, land, pause, excuse, own and staff the
platform's recurring jobs. Clause numbers are stable and are the way changes to the settlement engine are referenced.

Where this contract is silent about how a source is read, the behaviour of the settlement engine as shipped is the
reference. Where this contract names a record of practice instead of stating a rule, the practice those records show
is binding and the engine must follow it; the engine does not read those records itself (clause 2.8).

## 1. Terms

**1.1 Instant.** A point in time in whole seconds, always written `YYYY-MM-DDTHH:MM:SSZ` in UTC. Every time a source
carries is converted to an instant before any rule uses it. Sub-second digits are dropped, never rounded, except where
clause 5.4 says otherwise.

**1.2 Settlement period.** The half-open window `[period_start, period_end)` given by the `[settlement]` table of the
platform job export. Every window in this contract is half-open: it contains its start and excludes its end.

**1.3 Zone table and wall time.** Zone offsets come only from `tz_transitions.csv`. The offset of a zone at an instant
is the offset on the row with the greatest `effective_from` at or before that instant. A row whose offset column reads
`=>Target` makes its zone name an alias of `Target`. The wall time of a zone at an instant is the instant plus that
offset. When a source writes a wall time without an offset and that wall time occurs twice in its zone, the reading
denotes the earlier of the two instants; a source wall time that does not occur at all makes its record malformed.

**1.4 Normalised keys.** Job keys and dataset names compare only after normalisation: trim surrounding whitespace,
lowercase, replace each run of the characters `-`, `_`, `.`, `/` and space by a single `.`, and strip leading and
trailing dots. Team handles compare lowercased without a leading `@`. Mail addresses compare lowercased without a
`mailto:` prefix. Pager handles compare lowercased.

**1.5 Rejected records.** A record is one row, line, entry, block or element of a source, counted from 1 in file
order among the records of that source. A rejected record takes no part in any rule. The closed set of reject codes,
in the order they are tested, is: `MALFORMED_RECORD` (a required field is missing, empty or not in the form its source
uses), `UNKNOWN_JOB` (a job key no job has ever held), `UNMAPPED_DATASET` (a partition event whose dataset has no
producing job at the partition's nominal instant), `ORPHAN_TRANSITION` (an unpause with no pause in force, or a
partition deletion before any landing of that partition) and `UNAPPROVED_MARK` (an operator `mark_success` the
practice of clause 5.7 does not accept). A record carries at most one code: the first one that applies.

**1.6 Composed terms.** An *interval* is a job together with one nominal instant (clause 3.7). The *deadline* of an
interval is its nominal instant plus its SLA minutes. The *owning teams* of an interval are evaluated at its deadline
(clause 7.4). The *zone date* of an interval is the calendar date of its nominal instant in the wall time of the zone
its job specification names. The *landed instant* of an interval is the instant clause 5.8 selects, or none.

## 2. Sources

**2.1 Legacy definitions.** A legacy job revision is a section of `jobs_legacy.ini` keyed by job and revision instant.
Its schedule is the crontab entry in `crontab_legacy.cron` whose `# rev` comment names the same job and instant; every
other field comes from the INI section, and a `schedule_hint` in the INI is informational. A legacy revision with no
valid crontab entry has no schedule and makes no commitments.

**2.2 Calendar content lines.** In `freeze_windows.ics`, a line break followed by exactly one space or tab continues
the previous content line. That break and the single whitespace character are removed and nothing else is.

**2.3 logfmt.** A worker line in `workers_a.logfmt` is a sequence of `key=value` pairs separated by spaces. A value may
be enclosed in double quotes; inside the quotes `\"` stands for a double quote and `\\` for a backslash, and spaces do
not separate pairs. When a key repeats on one line, its last value is the one read.

**2.4 Legacy scheduler syslog.** Lines in `sched_legacy.syslog` carry month, day and time in the wall time of the
emitting host but no year. The year is the one, among the year of `period_start` and the years either side of it, that
puts the reading closest to `period_start`.

**2.5 EU scheduler export.** The `at_local` column of `sched_eu.ssv` is `DD.MM.YYYY HH:MM:SS` in Europe/Berlin wall
time.

**2.6 Directory.** `directory.ldif` holds person entries and `changetype: modify` records. An attribute may appear more
than once in one entry and every occurrence counts. Every `mail` value of a person entry, and every `mail` value a
modify record adds, is an address of that person. An address denotes its person permanently; `delete` records do not
withdraw that.

**2.7 Host clocks and hosts.** Worker log stamps are readings of the worker host's own clock (clause 5.4). A host
wall-clock reading denotes the instant it reads in the zone of the host binding in `host_inventory.csv` whose validity
window contains that instant; when more than one binding qualifies, the binding whose window starts latest wins.

**2.8 Records of practice.** `scheduler_ticks.tsv`, `sensor_waits.xml` and `review_rulings.ods` record what the
platform actually did in earlier periods. They are evidence of practice, not settlement inputs. `operations-runbook.md` predates this revision; where it disagrees with a
record of practice, the record governs.

## 3. Jobs and commitments

**3.1 Job identity.** Each row of `job_renames.csv` says that the job holding `old_key` holds `new_key` from
`effective_at`; a row with an empty `old_key` introduces a new job holding `new_key` from `effective_at`. A job no row
introduces has held its earliest name since before any record. Every job key a job specification carries that no job
holds is the name of a job of its own that has held it since before any record. A job's canonical id is `job:` followed
by the name it holds at the last instant of the settlement period, or by its first name when it is introduced after
the period ends.

**3.2 Key resolution.** A job key read for an instant denotes the job holding that key at that instant. If no job
holds it then, it denotes the job that held it most recently before that instant; if none did, the first job to hold it
after that instant.

**3.3 Resolution instants.** A job specification revision resolves its key at its effective instant, an SLA override
at its own instant, a pause event at its event instant, and every record that references an interval (scheduler,
worker, partition, operator, approval, backfill) at the nominal instant it references. A producer row resolves its key
at the partition nominal instant being looked up, and a dependency edge resolves both of its keys at the downstream
interval's nominal instant.

**3.4 Schedules.** A schedule is a five-field cron expression (minute, hour, day of month, month, day of week) read on
the wall clock of the zone the revision names. Fields accept lists, ranges, steps and `*`; months and days of the week
also accept three-letter English names, and both `0` and `7` mean Sunday. A field whose text begins with `*` is
unrestricted. When the day-of-month field and the day-of-week field are both restricted, a day that satisfies either
of them qualifies; otherwise a day must satisfy both.

**3.5 Specification timeline.** A job's specification at an instant is its revision with the greatest effective
instant at or before that instant. A revision with `enabled` false (analytics `state` disabled, finance `enabled` no,
legacy `disabled` yes) makes no commitments while it is in force.

**3.6 Skipped and repeated wall times.** When a scheduled wall time does not occur in a zone, or occurs twice, the
fire instants follow established practice, as the records of practice show.

**3.7 Intervals.** Each fire instant of a job's schedule, taken under the specification in force at that instant,
opens one interval whose nominal instant is the fire instant. Fires of one job at the same instant are one interval.
An interval belongs to the settlement period that contains its deadline.

**3.8 SLA minutes.** The base SLA comes from the specification in force at the nominal instant: platform
`sla_minutes`, analytics `sla_seconds` divided by 60, finance ISO 8601 duration, legacy `NhMm` form. Each line of
`sla_overrides.properties` names a job and an instant. The governing override for an interval is the one with the
greatest instant at or before the nominal instant (later lines win ties). A governing override with an integer value
replaces the base with that many minutes, zero included. A governing override with an empty value cancels overriding,
so the base applies.

## 4. Suspension

An interval that is not owed carries a suspension, and a suspended interval is settled as `SUSPENDED`.

**4.1 Change freezes.** Each series in `freeze_windows.ics` yields one occurrence per recurrence start: `DTSTART` and
`DTEND` are wall times in the `TZID` zone, `RRULE` supports `FREQ` `DAILY` and `WEEKLY` with `INTERVAL`, `BYDAY`,
`COUNT` and `UNTIL` (an instant), `EXDATE` removes the occurrence starting at that wall time, and a component with a
`RECURRENCE-ID` replaces the occurrence starting at that wall time with its own times, or removes it when its
`STATUS` is `CANCELLED`. `CATEGORIES` values `TIER1` to `TIER3` name the tiers a freeze covers. An interval whose
nominal instant lies inside an occurrence covering its tier is suspended `FREEZE`.

**4.2 Pauses.** Pause events of one job are taken in order of instant, then record order. A pause starts a paused
window unless one is already open, in which case it has no effect. An unpause closes the open window; an unpause with
no open window is rejected `ORPHAN_TRANSITION`. A window left open runs past the period. An interval whose nominal
instant lies in a paused window of its job is suspended `PAUSE`.

**4.3 Holidays.** A tier 3 interval whose zone date is a holiday in `team_holidays.xcs` of any of its owning teams is
suspended `HOLIDAY`.

**4.4 Precedence.** `FREEZE` is tested before `PAUSE`, and `PAUSE` before `HOLIDAY`.

## 5. Evidence

**5.1 Datasets.** `dataset_producers.psv` binds a dataset to a producing job over a validity window. The datasets of an
interval are those whose producer row is valid at the nominal instant and resolves to the interval's job. An interval
whose job has more than one dataset at its nominal instant, or whose dataset has more than one producing job at that
instant, is `UNRESOLVABLE` with reason `AMBIGUOUS_PRODUCER`.

**5.2 Partition events.** A partition is a dataset with a nominal instant. Its events are the landings reported by the
object store inventory, the HDFS audit log (creation of a `_SUCCESS` marker), the warehouse partition registry, the
data catalog (`published` notices) and completed incoming partner transfers, together with the deletions report. Events
of one partition from every system are merged into one stream ordered by instant, a landing before a deletion at the
same instant. Each system's own clock is authoritative for its events.

**5.3 Re-landed partitions.** When a partition's stream holds more than one landing, or deletions, the landing that
governs the partition follows established practice, as the records of practice show.

**5.4 Host clock correction.** `clock_offsets.prom` samples report, for a host at a true instant in milliseconds, the
offset of that host's clock from true time as local reading minus true time, in seconds. `heartbeats.txt` blocks give
the host's clock reading when sending and the scheduler's true clock on receipt; their offset is sent minus received,
stamped at the received instant. The governing sample for a worker reading is the latest sample for that host stamped
at or before the uncorrected reading, provided it is no more than 86,400,000 milliseconds older than the reading. The
corrected instant is the reading in milliseconds minus the governing offset, divided by 1000 and rounded down. A
reading with no governing sample cannot be corrected.

**5.5 Backfills.** Runs listed in `backfills.edn` are backfills. Their partition events count like any other, but
their worker events and scheduler transitions are not evidence for the interval.

**5.6 Scheduler success.** The scheduler success instant of an interval is the earliest `success` transition of a
non-backfill run of that interval, across the four scheduler exports.

**5.7 Operator marks.** Whether an operator `mark_success` action counts as evidence follows established practice, as
the records of practice show. A mark that does not count is rejected `UNAPPROVED_MARK`.

**5.8 Evidence tiers.** The tiers in precedence order are `physical`, `worker`, `scheduler` and `operator`. The first
tier with any evidence for an interval decides, and lower tiers are not consulted:

- `physical`: the partition of the interval's dataset has at least one landing; the landed instant is the one
  clause 5.3 settles for that partition.
- `worker`: at least one non-backfill `commit` event; the landed instant is the earliest corrected commit. When no
  commit of the tier can be corrected the interval is `UNRESOLVABLE` with reason `UNCALIBRATED_CLOCK`.
- `scheduler`: a scheduler success instant exists; it is the landed instant.
- `operator`: at least one counting mark; the earliest counting mark instant is the landed instant.

With no tier, the tier is `none` and there is no landed instant. The candidate count of an interval is the number of
landings, commits, success transitions or counting marks in the deciding tier, and 0 for `none`.

**5.9 Scheduler state audit.** A run is identified by interval and run id. Its transitions, across exports, are
ordered by instant, then source file name, then record order, starting from the state `none`. The legal steps are
`none` to `queued`, `queued` to `running`, `queued` to `removed`, `running` to `success`, `running` to `failed`,
`failed` to `up_for_retry`, `up_for_retry` to `queued`, `success` to `cleared`, `failed` to `cleared` and `cleared` to
`queued`. Every other step is illegal; the run's state after any step is the step's target state.

## 6. Status

**6.1 Settled status.** The closed set of statuses is `SUSPENDED`, `UNRESOLVABLE`, `MET`, `EXCUSED_OUTAGE`,
`EXCUSED_UPSTREAM`, `LATE` and `MISSED`, and they are tested in that order. `MET`: the landed instant is before the
deadline. `EXCUSED_OUTAGE`: the deadline lies inside an active outage window whose scope includes a dataset of the
interval. `EXCUSED_UPSTREAM`: at least one governing upstream interval (clause 6.3) is settled neither `MET` nor
`SUSPENDED`. `LATE`: the landed instant is at or after the deadline and before `period_end`. `MISSED`: otherwise.

**6.2 Outages.** An item in `outages.rss` whose guid is `OUT-...`, or `OUT-.../rN` for a later revision, belongs to
outage `OUT-...`. The revision with the latest publication date governs, a later item in the file winning ties. Its
description gives the window as `window=<instant>/<instant>` and its `status` as `active` or `retracted`; a retracted
outage excuses nothing. The scope of an outage is the set of datasets `incident_register.md` records against it.

**6.3 Dependencies.** `dependencies.dot` edges run from upstream to downstream and carry a non-negative `lag` and an
optional validity window applied to the downstream nominal instant. For a downstream interval, the governing upstream
interval of an edge is drawn from the upstream job's intervals of this settlement period: it is the upstream
interval that established practice waits on, as the records of practice show, moved `lag` further intervals back. An edge whose
position falls before the first such interval governs nothing.

**6.4 Blame.** For an `EXCUSED_UPSTREAM` interval, the blame parent is the governing upstream interval, among those
settled neither `MET` nor `SUSPENDED`, that landed latest; one that never landed counts as latest, and ties go to the
smaller canonical job id. Its blame root is reached by following blame parents until an interval that is not itself
`EXCUSED_UPSTREAM`; the depth is the number of steps taken, one for a direct parent.

## 7. Money and accountability

**7.1 Lateness.** Lateness is computed for `LATE` and `MISSED` intervals only, in whole minutes, from the deadline to
the landed instant for `LATE` and to `period_end` for `MISSED`. Any started minute counts as a whole minute.

**7.2 Buckets.** Lateness under 30 minutes is bucket `B0`, from 30 to under 120 minutes is `B30`, and 120 minutes or
more is `B120`.

**7.3 Rates.** The rate row for an interval is the row of `ratecard.fwf` for its tier and bucket with the greatest
effective instant at or before its deadline. Amounts are decimal EUR with at most two fraction digits and are
converted to integer minor units exactly. The penalty in minor units is the base amount plus the per-minute amount
times the lateness. With no rate row the penalty is 0.

**7.4 Ownership.** The CODEOWNERS state at an instant is obtained by applying the commits of
`ownership_history.gitlog` whose date is at or before that instant, in date order; commits sharing a date apply from the
bottom of the log upward. A `+pattern handles` line appends a line, and a `-pattern handles` line removes the first
existing line with the same pattern. The owning teams of an interval are found at its deadline: the path
`jobs/<name the job holds at the deadline>` is matched against every line, `*` matching any run of characters other
than `/` and the pattern having to match the whole path, and the last matching line wins. Its handles are resolved
through the `team_registry.hcl` bindings valid at the deadline; handles with no binding are ignored, and the owning
teams are the distinct resolved teams.

**7.5 Chargeback split.** The penalty of an interval with owning teams is split into equal shares in minor units. Any
leftover units are handed out one unit per team in ascending team id order. An interval with no owning teams is
charged as unowned.

**7.6 On-call accountability.** Each series in `oncall_rota.jcal` is a shift of one attendee for one team, repeating
by its rule, each occurrence lasting its duration in days of wall time in its zone; a component with a
`recurrence-id` replaces that occurrence's attendee or cancels it. The on-call person of a team at an instant is the
attendee of the occurrence of that team containing the instant; attendees the directory cannot place are ignored, and
among several occurrences the latest starting wins, then the smaller person id. With no such occurrence the team is
`UNASSIGNED` at that instant.

## 8. Outputs

**8.1 Interval order.** Every per-interval output lists intervals by deadline, then canonical job id, then nominal
instant.

**8.2 Output set.** The output files, their columns and their reconciliation identities are defined in
`output-contract.md`, which is part of this contract.
