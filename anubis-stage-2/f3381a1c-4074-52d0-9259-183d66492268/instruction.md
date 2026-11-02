The release train planner that built release candidate `R-NEXT` has been retired
because the package it produced disagreed with itself, and the release has to be
planned again. Everything you need is in `/app/data`.

`/app/data/release_engineering_handbook.md` is the authority for this build. The
two addenda it names, `/app/data/rounding_precedence_addendum.pdf` and
`/app/data/compatibility_window_notes.docx`, are the authority for what they
cover, and `/app/data/artifact_register.md` fixes the records, keys, order and
serialization of every output. Where any other file in that directory disagrees
with those four, those four win. The retired planner, its helpers, its notes and
its last report are in the directory for comparison only, and none of their
figures can be trusted.

Write a corrected planner at `/app/out/relplan.py`. It runs as

```bash
python3 /app/out/relplan.py DATA_DIR OUT_DIR
```

and rebuilds the whole package into `OUT_DIR` from whatever corpus `DATA_DIR`
holds, exiting with status 0. The requirements are these.

1. Do not tie the planner to `/app/data` or to this corpus's particular values.
   The same planner will be run, as an unprivileged user with no access to
   `/app`, against other corpora of the same shape: one carrying this exact
   release state with its rows delivered in a different order, and one carrying
   revised revisions, workbook figures, policy rows and compatibility records.
2. Derive every number from the corpus. No released figure may be fixed in the
   source.
3. Use integer arithmetic throughout. No output field carries a float.
4. Use only the Python standard library, and reach no network service.
5. Treat everything under `/app/data` as read only.
6. Give every release unit the canonical identity the handbook defines and use
   it in every output.
7. Resolve each unit's toolchain revision and contract revision against the
   previous release, and report both sides of each delta.
8. Record every distinct invalidation cause a unit has, deduplicated and sorted,
   and keep direct causes distinguishable from propagated ones.
9. Rebuild exactly what the handbook invalidates and reuse the rest, with the
   artifact digest that justifies each reuse.
10. Price every build unit in whole ticks under the scaling order and rounding
    the addendum sets out, and show each intermediate value.
11. Keep every pool inside its budget, with the budget, the reservation and the
    net figure reported per pool.
12. Admit prerequisite closures rather than units in isolation, and give every
    unit that is not built a traceable reason code.
13. Order the schedule so that every prerequisite, every migration constraint
    and every surviving ordering rule is satisfied, with one sequence number per
    scheduled unit.
14. Resolve dependency cycles under the declared policy, record what was removed
    and at what cost, and block what the policy blocks.
15. Select release consistent component versions and report every locally
    cheaper combination that compatibility rejects.
16. Keep deferred, blocked and excluded units out of the deployment manifest.
17. Make the generated client manifest agree with the contract revisions and the
    selected versions of the units that produce them.
18. Reconcile this release against the previous one and against the published
    artifact index.
19. Record every exception with the code the audit registry defines.
20. Emit the final release decision derived from the same state as every other
    output.
21. Make two runs over one corpus agree byte for byte.

When you are done, the package files in `/app/out` must be exactly what
`python3 /app/out/relplan.py /app/data /app/out` writes, byte for byte, with no
hand editing afterwards. The planner and the diagnosis note named below sit
beside them. The package is these files:

```
/app/out/normalized_inventory.jsonl
/app/out/revision_delta.jsonl
/app/out/toolchain_resolution.jsonl
/app/out/contract_delta.jsonl
/app/out/invalidation_reasons.jsonl
/app/out/invalidation_closure.jsonl
/app/out/generated_output_plan.jsonl
/app/out/build_unit_ledger.jsonl
/app/out/build_cost_breakdown.jsonl
/app/out/capacity_allocation.jsonl
/app/out/deferred_units.jsonl
/app/out/dependency_schedule.jsonl
/app/out/cycle_resolution.jsonl
/app/out/worker_pool_summary.json
/app/out/compatibility_matrix.jsonl
/app/out/rejected_combinations.jsonl
/app/out/version_selection.jsonl
/app/out/release_membership.jsonl
/app/out/deployment_manifest.json
/app/out/generated_sdk_manifest.jsonl
/app/out/migration_order.jsonl
/app/out/artifact_provenance.jsonl
/app/out/cache_reuse_manifest.jsonl
/app/out/release_delta.json
/app/out/audit_exceptions.jsonl
/app/out/release_decision.json
/app/out/conformance_summary.csv
/app/out/cost_amortization.jsonl
```

22. Share each generating unit's build cost across the components that
    require its interface, in whole ticks, so the shares add back to the
    cost they came from.
23. Leave the planner itself at `/app/out/relplan.py`.
24. Write `/app/out/diagnosis.md` with one numbered entry for each defect of the
    retired planner that your build corrects, naming the handbook or addendum
    rule each one broke.

You have 7200 seconds to complete this task. Do not use online solutions or
hints specific to this task.
