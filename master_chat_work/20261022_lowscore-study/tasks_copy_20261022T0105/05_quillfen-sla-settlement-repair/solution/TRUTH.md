# TRUTH.md - quillfen-sla-settlement-repair

## Defect

The shipped settlement engine in `repo.zip` departs from settlement contract revision 7 in twenty functions across its
three packages. Every departure still yields a complete, well formed settlement and the shipped unit suite passes.
Crux, in one sentence: the landed instant of each scheduled interval, resolved across renamed job identities, skewed
host clocks and re-landed partitions under practices that only records decide, fixes each interval's status, and those
statuses cascade along the dependency graph into blame, penalties, chargeback and accountability. The spine value is
the per-interval settled status in `ledger.csv`.

Focal defects (focal) whose rule is withheld and decided only by records of practice, the load-bearing set:

| Id | Clause | Function | Shipped reading | Settled reading | Deciding record |
|---|---|---|---|---|---|
| C3 (focal) | 3.6 | `cron.wall_to_fires` | skipped wall time shifted by the jump, repeated wall time at its first occurrence | skipped wall time fires at the jump instant, repeated wall time fires once at its later occurrence | `scheduler_ticks.tsv` |
| C6 (focal) | 5.3 | `landing.governing_land` | first landing | first landing after the last deletion, none when nothing lands after it | `review_rulings.ods` re_land rulings |
| C7 (focal) | 5.7 | `evidence.mark_accepted` | any approval | an approval sent at or before the mark by a person other than the actor | `review_rulings.ods` operator_mark rulings with `approvals.mbox`, `operator_audit.xlsx`, `directory.ldif`, `pager_contacts.vcf` |
| C8 (focal) | 6.3 | `deps.governing_upstream` | latest upstream interval at or before the downstream nominal instant | latest upstream interval strictly before it, then `lag` further back | `sensor_waits.xml` |

The legacy `operations-runbook.md` states a third wrong reading for C3 (skip, run twice), C6 (latest landing) and the
shipped reading for C7 and C8; clause 2.8 makes records outrank it.

Drift defects (drift) that contradict a stated clause, the supporting set:

| Id | Clause | Function | Departure |
|---|---|---|---|
| P1 | 2.4 | `scheduler.syslog_year` | always the period start year, no December or January rollover |
| P2 | 2.2 | `ical.unfold` | keeps the continuation whitespace, so a folded EXDATE value is silently dropped |
| P3 | 2.5 | `scheduler.eu_instant` | reads Berlin wall time as UTC |
| P4 | 2.3 | `workers.logfmt_pairs` | ignores escaped quotes, so a quoted `event=start` overrides the real event |
| P5 | 2.6 | `org.ldif_attributes` | keeps only the last value of a repeated attribute |
| C1 | 3.2 | `identity.Identity.resolve_key` | always the latest holder of a name, wrong before a reused name is taken |
| C2 | 3.4 | `cron.Schedule.day_matches` | requires both day fields even when both are restricted |
| C4 | 5.4 | `clock.ClockBook.correct` | adds the offset instead of subtracting it |
| C5 | 3.8 | `commitments.SlaBook.effective_sla` | treats a zero-minute override as a cancellation |
| C9 | 6.1 | `status.classify` | tests the upstream excuse before the outage excuse |
| R1 | 6.4 | `blame.root_of` | stops at the direct parent |
| R2 | 7.3 | `money.to_minor` | float conversion truncates amounts such as 0.29 |
| R3 | 7.2 | `penalty.bucket` | closed bucket upper bounds |
| R4 | 7.1 | `penalty.lateness_minutes` | floors instead of counting a started minute |
| R5 | 7.5 | `chargeback.split` | gives the whole leftover to the first team |
| R6 | 8.1 | `ledger.sort_key` | orders by job before deadline |

Trap records (trap) and decoys that look wrong and are right: last-match-wins CODEOWNERS evaluation, the ignored second pause, catalog
`withdrawn` notices and HDFS temporary deletes carrying no evidence, incomplete partner transfers, latest outage
revision governing, `schedule_hint` values in the legacy INI, `delete: mail` directory records, backfill landings that
still count while backfill commits do not.

Trap incidence in the shipped extract (records firing a documented rule, per file):

| File | Trap-firing records |
|---|---|
| approvals.mbox | 506 |
| backfills.edn | 240 |
| clock_offsets.prom | 4178 |
| crontab_legacy.cron | 82 |
| dataset_producers.psv | 144 |
| dependencies.dot | 141 |
| directory.ldif | 91 |
| freeze_windows.ics | 36 |
| heartbeats.txt | 1725 |
| host_inventory.csv | 221 |
| incident_register.md | 296 |
| job_pauses.ltsv | 153 |
| job_renames.csv | 149 |
| jobs_analytics.json | 178 |
| jobs_finance.xml | 91 |
| jobs_legacy.ini | 112 |
| jobs_platform.toml | 177 |
| landing_catalog.atom | 1660 |
| landing_hdfs_audit.log | 2216 |
| landing_objectstore.csv.gz | 2272 |
| landing_partner.xferlog | 1572 |
| landing_warehouse.sql | 2374 |
| oncall_rota.jcal | 209 |
| operator_audit.xlsx | 607 |
| outages.rss | 30 |
| ownership_history.gitlog | 139 |
| pager_contacts.vcf | 12 |
| partition_deletions.html | 357 |
| ratecard.fwf | 273 |
| review_rulings.ods | 124 |
| sched_apac.jsonl | 9014 |
| sched_eu.ssv | 11432 |
| sched_legacy.syslog | 7357 |
| sched_us.sqlite | 7414 |
| scheduler_ticks.tsv | 108 |
| sensor_waits.xml | 4790 |
| sla_overrides.properties | 107 |
| team_holidays.xcs | 26 |
| team_registry.hcl | 212 |
| tz_transitions.csv | 21 |
| workers_a.logfmt | 4381 |
| workers_b.cef | 5328 |
| workers_c.w3c.log | 3204 |
| workers_d.evtx.xml | 5806 |
| workers_e.access.log | 3234 |
| workers_f.pbtxt | 2819 |

## Load-bearing work

The patched archive is the deliverable that carries the weight: its engine is executed on five held-out extracts
(an autumn fold month, a spring gap month, a December to January probe, an autumn schedule probe and a spring
evidence probe) and on the shipped month. The four practice readings reach almost every weighted facet: C3 changes the
interval set, C6 and C7 change landed instants and UNAPPROVED_MARK rejects, C8 changes governing upstream intervals,
and all four change statuses, blame, penalties, chargeback and the reconciliation identities. The module records, the
regression test record, the repair report and the summary are each graded against the full set of twenty repairs.

Deliverables: 29 declared artifacts in task.toml. The seven records (patched-repo.zip, repair-report.json, the three
module records, test_fixes.json, summary.json) and the twenty-two files of the repaired engine's run over /app/data,
kept under /app/out/settlement/. Those twenty-two are graded twice: as delivered files against the reference for the
shipped month (split across the three shipped-month tests, with a negative when they disagree with the delivered
engine's own run), and through the delivered engine on the held-out extracts. Nine of the twenty-two expose one
mechanism each and are graded inside the facet test of the neighbouring output, so a hidden-rule miss costs both:
wall_clock.csv (3.6 instants and zone links), partition_landings.tsv (5.3), mark_decisions.csv (5.7),
upstream_waits.xml (6.3, including edges that govern nothing), clock_corrections.csv (5.4, graded on the evidence
probe where skew exists), freeze_occurrences.csv (4.1 with 2.2 unfolding, graded on the source probe),
oncall_shifts.jsonl (7.6), team_tiers.json (7.5 per tier) and output_manifest.json (record counts of every other
output). Measured on crux_fold and crux_gap: C3 moves wall_clock, upstream_waits, team_tiers and the manifest; C6 moves
partition_landings, upstream_waits, team_tiers and the manifest; C7 moves mark_decisions, upstream_waits, team_tiers
and the manifest; C8 moves upstream_waits, team_tiers and the manifest. The reference engine equals the independent
reference settlement on all nine files on all five held-out extracts.

## Why the work is hard

The agent receives a working, standard-library Python settlement engine whose own unit suite passes, a 50 file extract
of heterogeneous exports (SQLite, iCalendar, jCal, xCal, LDIF, vCard, logfmt, CEF, W3C, Windows event XML, protobuf
text, Prometheus exposition, SQL dumps, Atom, RSS, xferlog, spreadsheets and more) and a numbered settlement contract.
Functions across all three packages depart from that contract, and every departure still produces a complete,
plausible settlement. Some clauses state no rule and bind the engine to earlier practice, which has to be established
from operational records while other project material asserts readings the records do not support. The rules
interact: job identity across renamed and reused names feeds schedule expansion across daylight saving transitions,
which feeds evidence resolution across provenance tiers and skewed host clocks, which feeds dependency blame,
ownership resolved through commit history and handle bindings, penalties and on-call accountability. Grading runs the
delivered engine on held-out extracts from other seasons and years.

The mechanism that sets the task apart is repair under a partially silent contract: the solver has to find departures
from a stated specification inside a large reader and rules codebase whose tests are green, and for the silent clauses
has to infer the binding rule from operational records that contradict both the code and a documentation source, then
prove every repair with tests that discriminate a single restored defect and quantify the repair's effect on a month
of settlement.

## Verification

`tests/test.sh` clears any earlier reward files, locks `/logs/verifier` and `/tests` down to root and hands over to
`rewardkit /tests --workspace /app`. rewardkit grades two channels and `tests/reward.toml` adds them up: each channel's
weighted sum is divided by its own positive total and halved, with no clamp, so the reward runs from about -0.40 up
to 1.0.

Deterministic channel: `tests/test_output.py`, 35 `@criterion` checks registered with `criteria.<name>(weight=W)` at
the foot of the file, positive weight total 88, negative weight total -27. The verifier regenerates the five held-out
extracts and the shipped extract from fixed seeds, settles them with an independent reference implementation of the
contract and runs the delivered engine on them as an unprivileged user. Every check runs its assertion body through
`_pass`, which binds the artifact paths to the workspace and turns any exception into a failed check, so one broken
artifact costs that check and never aborts the run. The checks run one at a time because the extract, run and
regression caches are shared and every engine run is held to the same timeout. The nine negative checks are written
with inverted polarity: the check holds when the fault is present, so an honest delivery fails it and escapes the
penalty.

| Check | Weight | Observable |
|---|---|---|
| test_job_identity_matches_unseen_extracts | 1 | job_identity.tsv rows, two held-out extracts |
| test_people_match_unseen_extracts | 1 | people.jsonl |
| test_rejects_and_mark_decisions_match_unseen_extracts | 1 | rejects.csv including UNAPPROVED_MARK, mark_decisions.csv |
| test_state_audit_matches_unseen_extracts | 1 | state_audit.csv |
| test_commitments_and_wall_clock_match_unseen_extracts | 1 | commitments.csv and wall_clock.csv keyed by interval |
| test_dependency_resolution_and_upstream_waits_match_unseen_extracts | 1 | dependency_resolution.csv, upstream_waits.xml |
| test_unresolvable_matches_unseen_extracts | 1 | unresolvable.json |
| test_interval_outputs_follow_canonical_order | 1 | interval sequence of commitments, evidence, ledger and wall_clock |
| test_evidence_and_partition_landings_match_unseen_extracts | 5 | evidence.jsonl tier, landed instant, candidates; partition_landings.tsv |
| test_ledger_statuses_match_unseen_extracts | 5 | ledger status and reason |
| test_ledger_penalties_match_unseen_extracts | 5 | ledger lateness, bucket, penalty |
| test_blame_parents_match_unseen_extracts | 5 | blame parent |
| test_blame_roots_match_unseen_extracts | 3 | blame root, depth, root teams |
| test_accountability_and_oncall_shifts_match_unseen_extracts | 3 | accountability.csv, oncall_shifts.jsonl |
| test_chargeback_penalties_match_unseen_extracts | 5 | chargeback penalty per team and unowned |
| test_chargeback_counts_and_team_tiers_match_unseen_extracts | 3 | chargeback late, missed, blamed counts; team_tiers.json |
| test_reconciliation_and_output_manifest_match_unseen_extracts | 3 | reconciliation.toml identities, output_manifest.json |
| test_source_reading_probe_settles | 5 | ledger status and landed instant, freeze_occurrences.csv, December to January probe (P1 to P5) |
| test_schedule_probe_settles | 5 | same, schedule probe (C1, C2, C5) |
| test_evidence_probe_settles | 5 | ledger status and landed instant, clock_corrections.csv, evidence probe (C4, C9) |
| test_summary_and_settlement_records_match_shipped_month | 5 | summary.json status counts and period; settlement job_identity, people, rejects, state_audit, commitments, wall_clock, evidence, partition_landings, clock_corrections, mark_decisions and interval order |
| test_summary_penalties_and_settlement_money_match_shipped_month | 5 | summary.json penalties; settlement ledger, chargeback, team_tiers, accountability, oncall_shifts, freeze_occurrences |
| test_repair_report_and_settlement_lineage_match_shipped_month | 5 | repair-report.json against shipped and reference engines; settlement dependency_resolution, upstream_waits, unresolvable, blame, reconciliation, output_manifest |
| test_module_records_name_every_repaired_clause | 5 | clause sets of the three module records |
| test_module_records_name_every_repaired_function | 3 | clause and function pairs |
| test_regression_tests_pin_every_repaired_clause | 5 | listed tests pass on the reference engine and fail with one defect restored |
| negative_settlement_differs_between_identical_runs | -3 | two runs, byte comparison |
| negative_weight_hardcoded_sample_answers | -5 | identical ledger for two extracts |
| negative_repair_breaks_shipped_unit_tests | -3 | shipped unit tests against delivered src |
| negative_regression_record_lists_unsound_tests | -3 | listed id absent from the archive, or failing on the reference engine |
| negative_shipped_month_records_disagree_with_archive_engine | -3 | summary.json and /app/out/settlement against the delivered engine's own run |
| negative_repair_report_disagrees_with_archive_engine | -3 | repair-report.json against the delivered engine |
| negative_archive_ships_compiled_bytecode | -1 | archive members |
| negative_archive_drops_shipped_definition | -3 | shipped modules, classes, functions and parameter lists against the archive |
| negative_departing_function_keeps_shipped_body | -3 | statements of each departing function in the archive against its shipped body |

Judged channel: `tests/judge.toml`, 31 criteria, each judged in its own language model call and added up by weighted
sum, positive total 69, negative total -34. R1 to R5, R26 and R29 are constraints in the instruction following
category, each quoting the `instruction.md` sentence it enforces: -5 writing under /app/data, -3 archiving before the
shipped suite ran on the repaired tree, -3 a third-party import, -3 changing a shipped unit test file, -3 code that
rewrites settlement outputs after the engine writes them, -5 fetching a solution from outside the container and -3 a
figure stated as an approximation. R6 and R7 are reporting outcomes at 1 and R8 to R19 are the closing report figures
at 5. The figures are neutral before and after measures that name no rule; each criterion bundles one figure group
with one or two per-team late or missed counts chosen so that every one of the four practice readings moves at least
one fact of every criterion (measured: the repaired engine earns 60 of 60, each single practice misreading earns 0).
R20 to R23 are derivation conduct at 1, R24 (single-defect trees) and R25 (figures match the agent's own runs) are at
1, R27 is a safety and boundaries negative at -3 for reading grading paths, and R28 and R30 are factuality negatives
at -5 and -1. R31 at 1 reads the repaired function bodies and the added regression module as reviewable code, which
no check grades because every check reads what the engine writes rather than how it is written.

Traceability:

| Requirement (instruction or contract) | Artifact | Tests | Criteria |
|---|---|---|---|
| Engine follows stated clauses 2.2 to 2.6 | patched-repo.zip | source_reading_probe, rejects, people | R12, R16, R19 |
| Engine follows clauses 3.2, 3.4, 3.8 | patched-repo.zip | schedule_probe, commitments | R11, R18 |
| Practice clause 3.6 from records | patched-repo.zip | commitments and wall_clock, evidence, ledger, dependency and upstream_waits | R8 to R19, R20, R6 |
| Practice clause 5.3 from records | patched-repo.zip | evidence and partition_landings, ledger statuses | R8 to R19, R21, R6 |
| Practice clause 5.7 from records | patched-repo.zip | rejects and mark_decisions, evidence, ledger statuses | R8 to R19, R22, R6 |
| Practice clause 6.3 from records | patched-repo.zip | dependency_resolution and upstream_waits, ledger statuses, blame | R8 to R19, R23, R6 |
| Clauses 5.4 and 6.1 | patched-repo.zip | evidence_probe including clock_corrections | R9, R16 |
| Clauses 6.4, 7.1 to 7.6, 8.1 | patched-repo.zip | blame, penalties, chargeback and team_tiers, accountability and oncall_shifts, order | R13, R14, R17 |
| Clause 4.1 freeze occurrences | patched-repo.zip | source_reading_probe including freeze_occurrences | R18 |
| Twenty-two output files, record counts (output contract 1, 2) | patched-repo.zip | reconciliation and output_manifest, every facet test | |
| Contract silent: shipped behaviour stands | patched-repo.zip | all facet tests on held-out extracts | |
| Engine settles other extracts | patched-repo.zip | all facet and probe tests | |
| Deterministic, reads only its input (output contract 1) | patched-repo.zip | negative identical runs, negative hardcoded sample answers | |
| Repairs inside the departing function | patched-repo.zip, module records | negative departing function keeps shipped body, module record tests | R31 |
| Nothing corrects output files after the engine writes them | patched-repo.zip | facet tests run the archive engine directly | R5 |
| Keep modules, functions, classes, signatures | patched-repo.zip | negative drops shipped definition | |
| Shipped unit test files unchanged and passing | patched-repo.zip | negative breaks shipped unit tests | R4 |
| Standard library only | patched-repo.zip | | R3 |
| Run shipped suite before writing archive | | | R2 |
| Leave /app/data unchanged, work elsewhere | | | R1 |
| Archive layout, no bytecode (output contract 3) | patched-repo.zip | all engine tests, negative bytecode | |
| Module repair records | module_core.json, module_parser.json, module_report.json | module record tests | |
| Regression tests pin every repaired clause | test_fixes.json, archive tests | regression pin, negative unsound regression record | R24, R31 |
| Repair report | repair-report.json | repair report counts, negative disagreement | |
| Summary | summary.json | summary tests, negative disagreement | |
| Repaired settlement of /app/data, 22 files | /app/out/settlement/* | the three shipped-month tests, negative shipped-month disagreement | |
| Records describe the delivered archive and real runs | all records and settlement files | negative shipped-month disagreement, negative repair report disagreement | R25, R28 |
| Closing report: clause, file and reading per practice clause | final message | | R6 |
| Closing report: every F1 to F13 figure as an exact integer | final message | | R7, R8 to R19, R29, R30 |
| No online lookup of solutions | | | R26 |
| Grading surface untouched | | | R27 |

## Root cause

The engine was written against the runbook and a plausible reading of each source, and its unit suite only covers
behaviour those readings share with the contract. Interaction matrix, each rule changing the outcome of at least two
others:

| Rule | Interacts with |
|---|---|
| 3.2 identity | 3.6 expansion (spec per job), 5.1 datasets, 6.3 edges, 7.4 ownership path |
| 3.4 day fields | 3.7 interval set, 6.3 upstream positions, 4.3 holidays |
| 3.6 wall-time practice | 3.7 interval set, 6.3 lag positions, 7.1 lateness |
| 3.8 SLA zero | 3.7 period membership by deadline, 6.1 MET boundary, 7.2 bucket |
| 2.2 folding | 4.1 freeze suspension, 6.3 excuse (suspended upstream) |
| 2.6 directory | 5.7 self-approval, 7.6 on-call, UNAPPROVED_MARK rejects |
| 5.3 re-landing | 5.8 tier fallback, 6.1 status, 6.4 blame order by landed instant |
| 5.4 clock sign | 5.8 worker tier, 6.1 MET boundary, UNCALIBRATED_CLOCK |
| 5.7 marks | 5.8 operator tier, rejects, 6.1 status |
| 6.1 precedence | 6.3 excuse, 6.4 blame rows, 7.5 chargeback |
| 6.3 upstream practice | 6.1 excuse, 6.4 blame parent, 7.5 blamed counts |
| 6.4 blame root | 7.5 blamed counts, root teams via 7.4 |
| 7.1 to 7.3 money | 7.5 split leftovers, reconciliation penalty identity |
| 7.5 split | chargeback penalties, summary penalties |
| 8.1 order | every per-interval output |

## Solution shape

`solve.py` unpacks `repo.zip` twice, replaces each of the twenty departing function bodies with its contract form,
adds a regression module with one or two tests per clause built only from shipped functions and signatures, runs the
shipped and new unit tests, settles `/app/data` with the shipped and repaired trees, archives the repaired tree without
bytecode, writes the three module records from the repair list, lists the regression tests with their clauses, counts
record differences per output by the output contract's keys and writes the summary from the repaired run's ledger and
chargeback.

## Ordered plan

1. Read the settlement contract, the output contract and the runbook; list clauses 3.6, 5.3, 5.7 and 6.3 as practice clauses.
2. Unpack `repo.zip` outside `/app/data`, run its unit suite and settle `/app/data` with it to get a baseline.
3. Map each package's functions to the clauses they implement.
4. Compare every stated clause with its function; fix P1 to P5, C1, C2, C4, C5, C9, R1 to R6.
5. Parse `scheduler_ticks.tsv`; compare fired instants with skip, shift and clamp for gaps and first, later and both for folds; fix C3.
6. Parse `review_rulings.ods`; rebuild re_land partition streams from the landing exports and deletions; test first, last and after-deletion readings against accepted_event_at; fix C6.
7. For operator_mark rulings, resolve actors through `pager_contacts.vcf` and approvers through `directory.ldif` including modify records; test timing and identity readings; fix C7.
8. Parse `sensor_waits.xml`; compare waited_on with upstream intervals at or strictly before the downstream nominal instant, with lag; fix C8.
9. Write one regression test per repaired clause and check each fails with only that clause's shipped body restored.
10. Run the shipped suite and the regression tests on the repaired tree.
11. Settle `/app/data` with the repaired tree and keep that output directory as `/app/out/settlement`.
12. Count keyed record differences per output against the shipped run; write repair-report.json.
13. Write summary.json from the repaired ledger and chargeback.
14. Write the three module records and test_fixes.json.
15. Archive the repaired tree without bytecode to `/app/out/patched-repo.zip`.
16. Compute F1 to F8 from the two runs and the extract and write the closing report.

## Pitfalls

| Failure mode | Rule violated | Caught by | At stake |
|---|---|---|---|
| Keeps the code's or runbook's DST reading | 3.6 | commitments, evidence, ledger, blame, chargeback, probes, summary, report; R8 to R19, R20 | most of 88 |
| First or latest landing governs | 5.3 | evidence, ledger, blame, chargeback, probes, summary; R8 to R19, R21 | most of 88 |
| Any approval accepts a mark, or aliases unresolved | 5.7, 2.6 | rejects, evidence, ledger, probes; R8 to R19, R22 | most of 88 |
| Same-instant upstream waited on | 6.3 | dependency, ledger, blame, probes; R8 to R19, R23 | most of 88 |
| Stated parser drifts left in place | 2.2 to 2.6 | source probe, summary, report, records | 23 |
| Outage and upstream precedence swapped | 6.1 | evidence probe, summary, report | 20 |
| Money truncation, closed buckets, floored minutes | 7.1 to 7.3 | ledger penalties, chargeback, reconciliation, summary | 36 |
| Summary or report written from a stale run | output contract 3 | summary, report tests; negatives | 10 to 15 |
| Regression tests assert the shipped behaviour | output contract 3 | regression pin; negative unsound regression record | 5 to 8 |
| Figures narrated loosely or invented | instruction | R7, R8 to R19, R25, R29, R30 | judged |

## Provenance

```yaml
uuid: 5f0c3a8e-6d2b-4b7e-9a31-quillfen-sla
instance_id: quillfen-sla-settlement-repair
task_name: terminal-bench/quillfen-sla-settlement-repair
fix_patch_sha256: 78742e42cfe2b649667b56ed65d0b82d2bb77086f87d0f935c583423ad082242
solve_py_sha256: c32b1b20a604ad063a25ac70ec526e80102738bcd234e378a084d1e1b49327f9
language: python
status: complete
```

| Item | Value |
|---|---|
| Shipped extract | March 2026 settlement period, 50 files |
| sha256 environment/data/repo.zip | 78b858bb8bcc52a942dde929521c7f168f766abc77dd50bf0a8884e2f53eaf89 |
| sha256 environment/data/settlement-contract.md | 03ba640010f5d3c4b9a826580662977b9dd48d89bf0435632b3a20102eea1516 |
| sha256 environment/data/output-contract.md | e3dd49e5961f1151c1ac328d623d58e2e06c8d9a73589813043d5423a7978730 |
| sha256 solution/solve.py | c32b1b20a604ad063a25ac70ec526e80102738bcd234e378a084d1e1b49327f9 |
| sha256 tests/test_output.py | da73e8349599e6a9e8d437d89590723b5ab8195e4a3d2543fe4163ff4220e090 |
| sha256 tests/judge.toml | da1de590654331daf25c43870b5f91af8f91417bc85c8c198f4d4a8c6a65440d |
| sha256 tests/reward.toml | 4baafe0e6e16dbfbb7fadae4b3fd7e2d69e7584ac8c169dc6d011ec973f39a41 |
| sha256 instruction.md | 57c977b64b8ae0b17c314b22e80e98627a59e80c7b1e987327102f1f5b1bec2f |
