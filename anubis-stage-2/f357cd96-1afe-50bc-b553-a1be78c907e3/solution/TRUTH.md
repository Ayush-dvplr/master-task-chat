# TRUTH.md - f357cd96-1afe-50bc-b553-a1be78c907e3

## Defect

The task asks the agent to implement a deterministic integer scheduler and recover four withheld settlements from six sealed corpora. The four decisions are:

1. Largest-remainder ties use tenant ID ascending.
2. Tenant floors are applied before the hard-cap scaling step.
3. The SLO comparison is strict less-than.
4. Token-bucket refill uses floor rounding.

The worked micro example exercises the surrounding algorithm, but its values are deliberately invariant across the candidate choices. It therefore confirms implementation shape without revealing a withheld settlement. The full search space remains `2 * 2 * 2 * 3 = 24` combinations.

The following non-withheld rules are also load-bearing and explicitly specified:

- Phase 5 chooses class priority before stream ID within a tenant.
- Phase 6b scans nodes in Phase 6 candidate order, then victims by current-node latency cost descending and stream ID ascending.
- A preemption cascade stops after one eviction. The fresh three-stream witness distinguishes that rule from a recursive retry.
- Phase 8 `consumed[n, e]` is an assigned-stream count, not the MTU-unit debit used during placement.
- Fixed-point iterations are flattened across epochs and use one global index.
- `stream_manifest.csv.rate_units` is authoritative; packet-rate profile fields are descriptive metadata.

## Load-bearing work

The agent must produce ten canonical JSON files and one reusable program under `/app/out/`:

1. `schedule_matrix.json`
2. `fleet_utilization.json`
3. `tenant_fairness_report.json`
4. `migration_ledger.json`
5. `preemption_events.json`
6. `sla_violation_report.json`
7. `objective_breakdown.json`
8. `fixed_point_trace.json`
9. `integrity_manifest.json`
10. `final_state.json`
11. `reusable_scheduler.py`

JSON bytes must equal `json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"`. The integrity manifest hashes the first eight JSON artifacts. `final_state.json` folds the manifest hash map. The reusable program accepts `<data_dir> <out_dir>`, takes scheduling inputs only from the declared directory, and may read its own source only to create the required program copy.

## Verification

Channel A contains 35 rewardkit criteria: 29 positive checks with total weight 99 and 6 negative detectors with total magnitude 26. The reward multiplier is `0.5 / 99`.

Positive-weight distribution:

- Basic parsing, schema, canonical bytes, and alternate-directory execution: 4.
- Discriminating and shipped-property checks: 46.
- Five focused hidden-perturbation facts plus shipped final-state and SLA checks: 31.
- Five discriminating sealed-corpus checks: 15.
- Independent complete SLA-class validity: 3.

The six negative detectors cover hardcoded sample output, directory-name behavior, nondeterminism, float values in JSON, undeclared regular files, and JSON deliverables paired with a missing or empty reusable program. They return `True` only when the named defect is observed. Ordinary incorrect output is not mislabeled as cheating.

The expected results are stored as an 18-entry compressed inert JSON object indexed by SHA-256 fingerprints of the twelve input files. They contain no executable scheduling implementation. The separate embedded-input archive contains 26 relative-path data members, with no absolute or parent-traversal path. This keeps the verifier independent from `solution/solve.py` while retaining exact expected results for the finite shipped, seeded, sealed, and fresh corpora.

Channel B contains 20 judged criteria: 17 positive criteria totaling 51 and 3 negative criteria totaling 9. The reward multiplier is `0.5 / 51`. Positive criteria grade visible work such as reading the schema, enumerating candidates, exercising seals, checking repeatability, deriving totals, reconciling the pre-refill utilization boundary, testing sticky-node precedence, running the micro example, checking coupled bucket accounting, and independently auditing fixed-point and fairness rows. Negative criteria grade actual mutations of `/app/data`, environment-derived schedule inputs, and output permissions that deny uid 1000 access.

## Root cause

The hard part is the coupling between fair-share apportionment, priority selection, node feasibility, single-hop preemption, token state, previous-epoch placement, and integrity hashing. An error in an early phase changes several downstream artifacts and their hashes.

The sealed witnesses identify the withheld settlements, while fresh fixtures isolate individual rules. Hidden perturbations alter fleet capacity, SLO caps, arrival timing, and migration multipliers. This prevents a solver from succeeding through literal sample output or seals alone.

The reference and verifier intentionally use different representations. The reference computes the schedule. The verifier compares agent results to reviewed golden data and supplements that comparison with direct property checks such as byte hashing, exact class rows, cascade depth, priority ordering, canonical serialization, and reproducibility.

## Solution shape

1. Parse the twelve authoritative input files using integer types.
2. Initialize node buckets with their one-time offsets and load epoch-zero warm starts.
3. For each epoch, derive the active streams and per-tenant demand.
4. Apportion integer quotas with floors before cap scaling and tenant-ID largest-remainder ties.
5. Select streams within tenants by class priority descending, then stream ID ascending.
6. Place admitted streams by global priority and the sticky, latency, node-ID candidate tuple.
7. If placement fails, attempt exactly one ladder-authorized eviction using the specified node and victim orders.
8. Compute latency, migration, and fairness costs and append the global fixed-point trace.
9. Refill buckets using assigned-stream counts and floor rounding.
10. Write canonical artifacts, hash the first eight files, fold the hash map, and copy the program itself.

## Ordered plan

1. Read the schema and print the `stream_manifest.csv` header.
2. Implement and run a base solver against `/app/data` before examining sealed cases.
3. Enumerate all candidate values for the four withheld settlements.
4. Exercise candidate combinations against sealed witnesses and explain which witness dimensions bear on each settlement.
5. Confirm the final combination against all six seals.
6. Execute a phase-level check against the worked micro trace and run a coupled token-accounting fixture.
7. Independently check one fixed-point delta and one tenant fairness row.
8. Run the final scheduler on `/app/data` and on an alternate data directory.
9. Run it twice on the same input and compare output bytes.
10. Derive and print stream count, migration count, SLA breach count, and total cost from the artifacts.
11. Confirm the output directory contains exactly the eleven declared deliverables and that `/app/data` was not changed.

## Pitfalls

- Treating the worked example as an answer key. Its settlement-sensitive arithmetic is intentionally non-discriminating.
- Using proportional truncation instead of Hamilton largest remainder.
- Sorting selected streams only by stream ID and ignoring class priority.
- Comparing SLO hops with `<=` instead of `<`.
- Debiting Phase 8 availability by MTU units instead of assigned-stream count.
- Recursively placing an evicted victim after the permitted one-hop cascade.
- Resetting the fixed-point iteration index at each epoch.
- Using noncanonical JSON bytes, which also invalidates the integrity chain.
- Hardcoding `/app/data` in the reusable program instead of using its positional data-directory argument.
- Leaving scratch output or an empty reusable program behind.

## Withheld settlements - reference values

- `largest_remainder_tie`: `by_tenant_id_asc`
- `floor_application_order`: `floors_before_cap`
- `slo_comparison`: `strict_lt`
- `bucket_refill_rounding`: `floor`

## Provenance

Bundle: `f357cd96-1afe-50bc-b553-a1be78c907e3`

- `solution/solve.py`: `6e1a95e2658d36625f596be892808ccbf9b5b68384ae004e069418ea8a3ed44f`
- `tests/test_output.py`: `0d4df9c909229cb32be646387a5eb572d7bd04ae82a2dfcdfd74c83c9286088d`
- `tests/judge.toml`: `f09e3476a356c465c2ef6eb056a1b94cbb011fcaed25ea9ebfbba79d933407c8`
