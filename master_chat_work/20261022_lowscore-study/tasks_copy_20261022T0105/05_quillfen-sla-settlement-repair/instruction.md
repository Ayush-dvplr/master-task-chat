Quillfen settles its scheduled job commitments once a month, and the March 2026 settlement is wrong. The engine that produced it is the repository in `/app/data/repo.zip`, and the extract it settled is everything else in `/app/data`. The engine must implement the settlement contract in `/app/data/settlement-contract.md` together with `/app/data/output-contract.md`, which fixes every output and record shape named below. Bring the engine back to that contract, prove each repair, and report what the repairs changed.

Where a clause states a rule, that rule governs. Where a clause binds the engine to a practice instead, the practice is the one the shipped records establish. Where the contract is silent, the shipped behaviour stands.

Deliver the repaired repository as `/app/out/patched-repo.zip`, in the archive layout the output contract describes. It will be run on other extracts of the same shape, so it must settle any of them correctly. Each repair belongs inside the function whose shipped body departs from the contract, and nothing may correct the output files after the engine has written them. Keep every existing module, function, class and signature, leave the shipped unit test files unchanged and passing, keep the engine on the Python standard library, and run the shipped unit test suite against your repaired tree before you write the archive. Leave every file under `/app/data` exactly as shipped and do all extraction, experiments and settlement runs elsewhere.

Record the repairs per package in `/app/out/module_core.json`, `/app/out/module_parser.json` and `/app/out/module_report.json`. Add regression tests to the repository's `tests` package so that every repaired clause is pinned by at least one test, and list them with their clauses in `/app/out/test_fixes.json`. Settle `/app/data` with the shipped engine and with your repaired engine and write the per-file record differences to `/app/out/repair-report.json`. Keep the output directory of your repaired engine's run over `/app/data` as `/app/out/settlement`, holding exactly the files the output contract lists: `/app/out/settlement/job_identity.tsv`, `/app/out/settlement/people.jsonl`, `/app/out/settlement/rejects.csv`, `/app/out/settlement/commitments.csv`, `/app/out/settlement/evidence.jsonl`, `/app/out/settlement/dependency_resolution.csv`, `/app/out/settlement/state_audit.csv`, `/app/out/settlement/ledger.csv`, `/app/out/settlement/blame.jsonl`, `/app/out/settlement/accountability.csv`, `/app/out/settlement/unresolvable.json`, `/app/out/settlement/chargeback.xml`, `/app/out/settlement/reconciliation.toml`, `/app/out/settlement/wall_clock.csv`, `/app/out/settlement/freeze_occurrences.csv`, `/app/out/settlement/partition_landings.tsv`, `/app/out/settlement/clock_corrections.csv`, `/app/out/settlement/mark_decisions.csv`, `/app/out/settlement/upstream_waits.xml`, `/app/out/settlement/oncall_shifts.jsonl`, `/app/out/settlement/team_tiers.json`, `/app/out/settlement/output_manifest.json`. Write that run's settlement summary to `/app/out/summary.json`. Every record and settlement file must describe the archive you deliver and runs you actually made.

End with a closing report in your final message. For every clause you settled from records of practice, give the clause number, the file whose records settled it and the reading you adopted. Then state every figure below for the March 2026 extract as an exact integer, each label followed by its value. "Shipped run" and "repaired run" are the settlements of `/app/data` by the engine in `/app/data/repo.zip` and by your delivered engine; a figure that names neither counts the repaired run, and files named are that run's output files.

```
F1  status_changed: intervals whose ledger status differs between the shipped and repaired runs (an interval in one run only counts)
    changed_to_met, changed_to_owed: of those, intervals the repaired run settles MET; settles LATE or MISSED
F2  landed_changed: intervals whose ledger landed_at differs between the two runs (an interval in one run only counts)
    landed_earlier, landed_cleared: of those in both runs, repaired landed_at earlier; repaired empty while shipped is not
F3  upstream_changed: intervals whose set of dependency_resolution.csv rows differs between the two runs
    upstream_rows, upstream_changed_excused: rows of dependency_resolution.csv; upstream_changed intervals settled EXCUSED_UPSTREAM
F4  intervals_only_repaired, intervals_only_shipped: commitments.csv intervals present in one run only
    suspension_changed: intervals in both runs whose suspension differs
F5  rejects_malformed, rejects_unknown_job, rejects_unmapped, rejects_orphan, rejects_unapproved: rejects.csv rows per code
F6  penalty_b0, penalty_b30, penalty_b120: ledger penalty_minor totals per bucket
F7  blame_max_depth, blame_max_rows, blame_roots: largest depth in blame.jsonl; rows at that depth; distinct roots
F8  unresolvable_ambiguous, unresolvable_uncalibrated, unresolvable_jobs: UNRESOLVABLE intervals per reason; distinct jobs
F9  tier_physical, tier_worker, tier_scheduler, tier_operator, tier_none: evidence.jsonl intervals per tier
F10 accountability_rows, unassigned_rows, oncall_people: accountability.csv rows; rows naming UNASSIGNED; distinct persons
F11 late:<team id>, missed:<team id>: the late and missed attributes of every team element in chargeback.xml
F12 suspended_freeze, suspended_pause, suspended_holiday: commitments.csv intervals per suspension
F13 met_tier1, met_tier2, met_tier3: MET intervals per commitments.csv tier
```

Do not look up solutions to this task online.

You have 14400 seconds to complete this task.
