# Quillfen Settlement Output Contract

Part of settlement contract revision 7 (clause 8.2). It fixes the shape of everything a settlement run writes and of
the records that accompany a change to the settlement engine.

## 1. Running the engine

The engine is run from the root of the repository with `src` on the import path:

```
python3 -m quillfen settle <input_dir> <output_dir>
```

A run reads only `<input_dir>`, leaves it unchanged, creates `<output_dir>` when needed and writes exactly the
twenty-two files below into it. Two runs over the same extract write identical bytes. The engine uses the Python standard library
only.

Every instant is written `YYYY-MM-DDTHH:MM:SSZ`. An interval is written `<canonical job id>@<nominal instant>`, for
example `job:stage.orders.daily@2026-03-04T05:00:00Z`. A team is written `team:<name>` using the `team` value of its
registry binding. A person is written `emp:<employeeNumber>`. CSV files are comma separated with a header row and
standard double-quote escaping; TSV files are tab separated with a header row. A CSV or TSV cell for an absent instant,
person or value is empty. "Interval order" means clause 8.1 of the settlement contract. "Overlaps the settlement period"
means a window that starts before the period end and ends after the period start.

## 2. Output files

**job_identity.tsv**, columns `canonical_job`, `name`, `held_from`, `held_to`. One row for every name every job has
held (clause 3.1). `held_from` is empty for a name held since before any record and `held_to` is empty for a name still
held. Rows are ordered by `canonical_job`, then rows with an empty `held_from` first, then `held_from`, then `name`.

**people.jsonl**, one JSON object per line with keys `person`, `emails` and `pager_handles`, for every person entry of
the directory. `emails` lists every address of the person (clause 2.6) and `pager_handles` every handle from a pager
contact card with at least one address of that person, both sorted and normalised as in clause 1.4. Lines are ordered
by `person`.

**rejects.csv**, columns `source`, `ordinal`, `reason`. One row per rejected record: the source file name, the record
ordinal of clause 1.5 and its code. Ordered by `source`, then numeric `ordinal`.

**commitments.csv**, columns `interval`, `canonical_job`, `nominal`, `deadline`, `tier`, `sla_minutes`, `suspension`.
One row per interval of the settlement period. `suspension` is empty, `FREEZE`, `PAUSE` or `HOLIDAY`. Interval order.

**evidence.jsonl**, one JSON object per line with keys `interval`, `tier`, `landed_at` and `candidates`, one line per
interval in interval order. `tier` is `physical`, `worker`, `scheduler`, `operator` or `none`; `landed_at` is an
instant or JSON `null`; `candidates` is the count of clause 5.8. An interval unresolvable for `AMBIGUOUS_PRODUCER` has
tier `none`, a null `landed_at` and 0 candidates.

**dependency_resolution.csv**, columns `interval`, `upstream_interval`, `lag`. One row for each distinct pair of
governing upstream interval and lag of each interval (clause 6.3). Rows follow the downstream interval in interval
order, then `upstream_interval`, then numeric `lag`.

**state_audit.csv**, columns `canonical_job`, `nominal`, `run_id`, `from_state`, `to_state`, `at`. One row per illegal
step of clause 5.9. Ordered by `canonical_job`, `nominal`, `run_id`, `at`, `from_state`, `to_state`.

**ledger.csv**, columns `interval`, `status`, `reason`, `landed_at`, `lateness_minutes`, `bucket`, `penalty_minor`. One
row per interval in interval order. `reason` holds the reason of an `UNRESOLVABLE` interval and is empty otherwise.
`landed_at` is the landed instant, empty when there is none. `lateness_minutes`, `bucket` and `penalty_minor` are filled
for `LATE` and `MISSED` intervals only and are empty otherwise.

**blame.jsonl**, one JSON object per line with keys `interval`, `parent`, `root`, `depth` and `root_teams`, one line for
every `EXCUSED_UPSTREAM` interval in interval order. `root_teams` lists the owning teams of the root interval,
evaluated at the root's deadline, sorted.

**accountability.csv**, columns `interval`, `team`, `person`. One row for every `LATE` or `MISSED` interval and each of
its owning teams; `person` is the on-call person of that team at the interval's deadline (clause 7.6) or
`UNASSIGNED`. Interval order, then `team`.

**unresolvable.json**, a JSON array of objects with keys `interval` and `reason`, one per `UNRESOLVABLE` interval, in
interval order. The closed set of reasons is `AMBIGUOUS_PRODUCER` and `UNCALIBRATED_CLOCK`.

**chargeback.xml**, a `chargeback` root element with `period_start` and `period_end` attributes. It holds one `team`
element for every team named by any binding in `team_registry.hcl`, ordered by id, with attributes `id`,
`penalty_minor` (its shares under clause 7.5), `late` and `missed` (the `LATE` and `MISSED` intervals it owns) and
`blamed_downstream` (the blame rows whose `root_teams` include it). A final `unowned` element carries `penalty_minor`,
`late` and `missed` for intervals with no owning team.

**reconciliation.toml**, five tables named `identity.intervals`, `identity.penalty`, `identity.blame`,
`identity.accountability` and `identity.unresolvable`, each with integer keys `lhs`, `rhs` and `residual`, where
`residual` is `lhs` minus `rhs`:

```
intervals       lhs: rows of commitments.csv            rhs: rows of ledger.csv
penalty         lhs: sum of ledger penalty_minor         rhs: team penalty_minor sum plus unowned penalty_minor
blame           lhs: EXCUSED_UPSTREAM rows of ledger     rhs: lines of blame.jsonl
accountability  lhs: team late plus missed, all teams    rhs: rows of accountability.csv
unresolvable    lhs: UNRESOLVABLE rows of ledger         rhs: entries of unresolvable.json
```

**wall_clock.csv**, columns `interval`, `zone`, `local_nominal`, `local_deadline`. One row per interval, in interval
order. `zone` is the zone named by the job specification revision the interval was expanded from, exactly as that
revision writes it. `local_nominal` and `local_deadline` are the wall readings of the nominal instant and of the deadline
in that zone together with the UTC offset in force at that instant, written `YYYY-MM-DDTHH:MM:SS+HH:MM` or
`YYYY-MM-DDTHH:MM:SS-HH:MM`.

**freeze_occurrences.csv**, columns `start`, `end`, `tiers`. One row for every change freeze occurrence of clause 4.1
that overlaps the settlement period. `tiers` lists the tiers the occurrence covers as digits in ascending order
separated by `;`. Rows are ordered by `start`, then `end`, then `tiers`.

**partition_landings.tsv**, columns `dataset`, `nominal`, `lands`, `retracts`, `governing_landed_at`. One row for every
partition whose merged stream of clause 5.2 holds at least one landing. `lands` and `retracts` count the landings and
the deletions of that stream, not counting events rejected by clause 1.5; `governing_landed_at` is the landed instant
clause 5.3 settles for the partition. Rows are ordered by `dataset`, then `nominal`.

**clock_corrections.csv**, columns `interval`, `host`, `local_ms`, `corrected_at`. One row for every `commit` event of
the worker logs that is not part of a backfill run and names a known job, whether or not the interval it names is a
commitment of the period. `local_ms` is the uncorrected host reading and `corrected_at` the instant clause 5.4 gives
it. Rows are ordered by `interval`, then `host`, then numeric `local_ms`, then `corrected_at`.

**mark_decisions.csv**, columns `interval`, `actor`, `marked_at`, `accepted`. One row for every operator
`mark_success` action that names a known job, whether or not the interval it names is a commitment of the period.
`actor` is the acting handle as pager handles compare under clause 1.4, `marked_at` the instant of the action and `accepted` is
`true` when the mark counts under clause 5.7 and `false` otherwise. Rows are ordered by `interval`, then `actor`, then
`marked_at`, then `accepted`.

**upstream_waits.xml**, an `upstream_waits` root element holding one `wait` element for every interval and every
distinct combination of upstream job, `lag` and waited-on interval produced by the edges clause 6.3 applies to that
interval, including edges that govern nothing. Attributes: `interval`; `upstream_job`, the canonical id of the upstream
job; `lag`; `waited_on`, the governing upstream interval of clause 6.3, empty when the edge governs nothing; and
`status`, the ledger status of `waited_on`, empty when `waited_on` is. Elements follow the downstream interval in
interval order, then `upstream_job`, then numeric `lag`, with an empty `waited_on` first.

**oncall_shifts.jsonl**, one JSON object per line with keys `team`, `start`, `end` and `person`, one line for every rota
occurrence of clause 7.6 that overlaps the settlement period. `person` is the directory person the occurrence's
attendee address belongs to, or JSON `null`. Lines are ordered by `team`, then `start`, then `end`, then `person`,
with `null` first.

**team_tiers.json**, an object with keys `teams` and `unowned`. `teams` maps the `id` of every `team` element of
chargeback.xml to an object with keys `"1"`, `"2"` and `"3"`, one per tier, each an object with integer keys `late`,
`missed` and `penalty_minor`: the `LATE` and `MISSED` intervals of that tier the team owns and the penalty shares of
clause 7.5 it receives from them. `unowned` has the same three tier objects for intervals with no owning team. Every
tier object is present, zero included.

**output_manifest.json**, an object with the key `outputs`, mapping each of the other twenty-one file names to its
number of records: data rows of a CSV or TSV file, non-empty lines of a JSONL file, entries of unresolvable.json,
child elements of the root element of chargeback.xml and upstream_waits.xml, tables of reconciliation.toml, and the
entries of `teams` plus one for team_tiers.json.

## 3. Records that accompany an engine change

A change to the engine is delivered as a repository archive together with five JSON records. Clause ids are the
settlement contract's clause numbers written as strings, such as `"3.4"`.

**Repository archive.** A zip archive of the whole repository with the shipped layout at the archive root
(`pyproject.toml`, `src/quillfen/...`, `tests/...`). It holds no `__pycache__` directory and no compiled `.pyc` file.

**Module repair records.** One file per package of the engine, each an object with keys `module` and `repairs`.
`module` is `quillfen.core`, `quillfen.parsers` or `quillfen.report`. `repairs` lists one object per defect repaired
in that package, with keys `clause` (the clause the shipped code departed from) and `function` (the function whose
shipped body departed from it, written `<file stem>.<qualified name>`, for example `penalty.RateCard.price`). A package
with no repair has an empty list.

**Regression test record.** An object with the key `tests`, a list of objects with keys `id` and `clause`. Each `id` is
a unittest id such as `tests.test_regressions.SettlementRegressions.test_example`, runnable as
`python3 -m unittest <id>` from the repository root with `src` on the import path, and `clause` is the clause that test
pins. A listed test uses only the standard library and functions and classes the shipped repository already has, called with their shipped signatures, reads no file
outside a temporary directory it creates itself, passes against the repaired engine, and fails once that clause's shipped defect is
restored in the repaired engine and nothing else is changed.

**Repair report.** An object with the key `outputs_changed`, mapping each of the twenty-two output file names to the
number of records that differ between the shipped engine and the repaired engine run over the same extract. Records
are matched by key: `canonical_job`, `name` and `held_from` for job_identity.tsv; `person` for people.jsonl; `source`
and `ordinal` for rejects.csv; `interval` for commitments.csv, evidence.jsonl, ledger.csv, blame.jsonl and
unresolvable.json; `interval` and `upstream_interval` for dependency_resolution.csv; the whole row for
state_audit.csv; `interval` and `team` for accountability.csv; the `id` of each `team` element, and the `unowned`
element as one record, for chargeback.xml; the table name for reconciliation.toml; `interval` for wall_clock.csv;
`start`, `end` and `tiers` for freeze_occurrences.csv; `dataset` and `nominal` for partition_landings.tsv;
`interval`, `host` and `local_ms` for clock_corrections.csv; `interval`, `actor` and `marked_at` for
mark_decisions.csv; `interval`, `upstream_job` and `lag` for upstream_waits.xml; `team`, `start` and `end` for
oncall_shifts.jsonl; the team id, and `unowned` as one record, for team_tiers.json; the file name for
output_manifest.json. Each distinct key counts once, when
it appears in only one run's file or appears in both with any other field different.

**Settlement summary.** An object with keys `period_start`, `period_end`, `status_counts` (all seven statuses of
clause 6.1 mapped to their interval counts, zero included), `penalty_minor_by_team` (every team of chargeback.xml
mapped to its `penalty_minor`) and `unowned_penalty_minor`.
