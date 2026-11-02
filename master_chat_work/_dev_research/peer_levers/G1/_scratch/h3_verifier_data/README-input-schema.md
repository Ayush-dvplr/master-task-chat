# HTTP/3 Fleet Migration Scheduler - Input Schema and Contract

## 1. Overview

The control plane operates a fleet of HTTP/3 reverse-proxy nodes carrying long-lived tenant streams over a sequence of scheduling epochs. Every epoch, every active stream must be assigned to exactly one node, subject to node capacity, per-tenant fair-share, per-node token buckets, class-based preemption, migration penalties, and latency SLOs. The task is to produce a discrete schedule that minimises the weighted objective `alpha * latency_cost + beta * migration_cost + gamma * fairness_deviation` while satisfying every hard constraint, then serialise a fixed set of report artifacts and chain them under two integrity artifacts.

## 2. Input files (flat under `/app/data/`)

| File | Format | Purpose |
| --- | --- | --- |
| `fleet_nodes.csv` | CSV | Per-node capacity, MTU class, priority-lane cap, region |
| `stream_manifest.csv` | CSV | Streams with tenant, class, arrival epoch, deadline epoch, rate profile |
| `tenants.csv` | CSV | Per-tenant floor, ceiling, migration multiplier, region |
| `qos_classes.json` | JSON | Class priority rank, SLO hop cap, preemption ladder |
| `token_buckets.csv` | CSV | Per-node bucket capacity, refill numerator/denominator, offset |
| `mtu_matrix.csv` | CSV | mtu_class x node -> units consumed per admitted stream |
| `migration_penalty_table.json` | JSON | Piecewise integer migration base per tenant per epoch |
| `latency_matrix.csv` | CSV | node x tenant_region -> integer hop count |
| `preemption_ladder.json` | JSON | Class x class precedence and cascade rules |
| `epoch_windows.csv` | CSV | Per-epoch duration numerator/denominator and warm-start map |
| `fixed_point_constants.json` | JSON | alpha, beta, gamma, damping, tolerance, max iterations |
| `packet_rate_profiles.csv` | CSV | Reusable rate curves referenced by streams |
| `worked_micro_example.json` | JSON | Fully-traced 3-node/6-stream/2-epoch instance |
| `case-<name>.json` (x6) | JSON | Sealed reference corpora (argosy, brigantine, caravel, dhow, esquif, frigate) |
| `seal-<name>.json` (x6) | JSON | Witness numeric fields taken under the archive's four settlements |

`epoch_windows.csv` is authoritative for the number of scheduling epochs `E`; `stream_manifest.csv` is authoritative for the stream set. Every graded run reads only files under `/app/data/`.

## 3. The eight-phase per-epoch algorithm

For each epoch `e = 0, 1, ..., E - 1`, the scheduler evaluates the following phases in order. Phases 4-6 are wrapped in the fixed-point loop of phase 9.

### Phase 1 - Active set
`active[e] = { s : arrival_epoch[s] <= e <= deadline_epoch[s] }`.

### Phase 2 - Per-tenant demand
`demand[t, e] = count of streams in active[e] whose tenant is t`.

### Phase 3 - Epoch capacity
`total_cap[e] = sum(capacity[n] for n in nodes)`.

### Phase 4 - Fair-share apportionment
Given `demand[t, e]`, `floor[t]`, `ceiling[t]`, and `total_cap[e]`, produce an integer `quota[t, e]` with:
- `quota[t, e] >= 0`
- `sum_t quota[t, e] <= total_cap[e]`
- Post-apportionment, floors must hold: `quota[t, e] >= min(floor[t], demand[t, e])` when the settled ordering permits it.

The interior of this phase - specifically the order in which the floor is applied relative to the largest-remainder scaling, and the tie-break rule used inside the largest-remainder step - is one of the four withheld settlements (see section 6).

### Phase 5 - Per-tenant stream selection
Inside each tenant, when `demand[t, e] > quota[t, e]`, take exactly `quota[t, e]` streams ordered by:
1. Class priority rank descending (higher rank first - see `qos_classes.json`).
2. Stream ID ascending.

Every stream not selected at this phase is a *deferred* stream and remains active in later epochs.

### Phase 6 - Node placement
Sort admitted streams globally by:
1. Class priority rank descending.
2. Tenant ID ascending.
3. Stream ID ascending.

For each stream in that order, attempt to place it on a node. Iterate candidate nodes in an order that minimises the tuple:
1. Migration continuity: preserve the assignment from epoch `e - 1` when feasible (this is the "sticky" preference).
2. Latency: pick a node whose latency to the tenant's region is smallest.
3. Node ID ascending, as a final tie-break.

A candidate node is *feasible for stream s in epoch e* when all six conditions below hold:
- `current_load[n, e] + 1 <= capacity[n]`.
- `current_priority_load[n, e] + 1 <= priority_lanes[n]` when the stream's class has `priority_rank >= 2` (K01, K02); classes with rank 1 (K03) do not consume the priority lane.
- `bucket_tokens[n, e] >= mtu_units(mtu_class[n], class[s])` (see `mtu_matrix.csv`).
- The SLO check `latency[n, tenant_region[t]] <SLO_OP> class_slo_hops[k]` - where `<SLO_OP>` is the settled operator (see section 6).
- The node is not currently reserved for a *cascade preemption* (see phase 6b).
- Assigning stream `s` to node `n` does not violate any tenant ceiling in epoch `e`.

If no feasible node exists, run phase 6b (preemption cascade). If phase 6b cannot free a slot, the stream is *preempted for this epoch* and recorded in `preemption_events.json`.

### Phase 6b - Preemption cascade
When an unplaced admitted stream `s` (call it the *beneficiary*) has empirically no feasible node, look for a lower-priority stream on any feasible node that can be evicted per `preemption_ladder.json`. Specifically, `s` may preempt an already-placed stream `s'` when:
- `class[s]` is listed as a preemptor of `class[s']` in `preemption_ladder.json`.
- After eviction, phase 6 feasibility holds for `s` on that node.
- The cascade depth is exactly 1 (a preempted `s'` may not preempt further this epoch; cascade halts immediately after the single eviction).

Evict the highest-cost `s'` (max `latency_cost` on its current node) first. Evicted streams are recorded as preempted for epoch `e`.

### Phase 7 - Per-epoch costs
- `latency_cost[e] = sum over placed s of latency[assigned[s, e], tenant_region[tenant[s]]] * rate_units[s]`.
- `migration_cost[e] = sum over placed s of migration_penalty_base[tenant[s], e] * migration_mult[tenant[s]]` when `assigned[s, e] != assigned[s, e - 1]` (using `warm_start[s]` for `e = 0`).
- `fairness_deviation[e] = sum over t of |admitted_count[t, e] - target[t, e]|` where `target[t, e] = min(demand[t, e], ceiling[t])`.

### Phase 8 - Token bucket refill (for epoch `e + 1`)
Let `duration[e] = duration_num[e] / duration_den[e]`. For each node `n`:
- `available[n] = min(bucket_capacity[n], bucket_tokens[n, e] - consumed[n, e])`.
- `refill_units_scaled[n, e] = refill_num[n] * duration_num[e]`, with denominator `refill_den[n] * duration_den[e]`.
- `refill_int[n, e] = <ROUND_OP>(refill_units_scaled[n, e], refill_den[n] * duration_den[e])`, where `<ROUND_OP>` is the settled rounding rule (see section 6).
- `bucket_tokens[n, e + 1] = min(bucket_capacity[n], available[n] + refill_int[n, e])`.

Refill offset (`refill_offset[n]`) is added once at epoch 0 before Phase 6 of epoch 0.

### Phase 9 - Fixed-point iteration
Phases 4-6 run inside a damped fixed-point loop coupling admission quotas and bucket state. At iteration `i`:
- Let `admissions_prev` be the epoch's admissions from iteration `i - 1` (empty at `i = 0`).
- Compute `admissions_new` via phases 4-6.
- Damped update: for each `(tenant, epoch)` pair, `admissions_next[t, e] = floor((damping_den - damping_num) * admissions_prev[t, e] / damping_den + damping_num * admissions_new[t, e] / damping_den + (damping_den - 1)) / damping_den * damping_den`.
  Practically, this reduces to: `admissions_next[t, e] = admissions_new[t, e]` in this task because the damping numerator and denominator are set to reach fully-updated state within one integer step; the fixed-point trace still records the pre/post admissions so the *loop shape* is exercised.
- Iterate until `sum |admissions_next[t, e] - admissions_prev[t, e]| <= tolerance` across all tenants and epochs, or `max_iterations` reached.

### Phase 10 - Artifact serialisation
Produce the ten JSON artifacts and one program file listed in `task.toml`. Every JSON file must be serialised as `json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"` (canonical form: sorted keys, no whitespace between separators, single trailing newline).

### Phase 11 - Integrity chain
- `integrity_manifest.json` = `{"artifact_names": [...], "artifact_sha256": {"<name>": "<sha256 hex>"}}` where the eight upstream artifacts (schedule_matrix through fixed_point_trace) are hashed on their on-disk canonical bytes. `artifact_names` is sorted lexicographically.
- `final_state.json` = `{"artifact_count": 10, "epoch_count": E, "folded_digest_sha256": "<sha256 hex>", "stream_count": N_streams, "total_cost": <int>}` where `folded_digest_sha256 = sha256(json.dumps(artifact_sha256, sort_keys=True).encode("utf-8")).hexdigest()`.

## 4. Artifact schemas (exact)

Every artifact is a JSON object; the keys shown below are exhaustive.

- **`schedule_matrix.json`** - `{"epochs": [{"epoch": <int>, "assignments": {"<stream_id>": "<node_id>"}, "preempted": ["<stream_id>", ...]}, ...]}`. `preempted` is sorted ascending.
- **`fleet_utilization.json`** - `{"nodes": [{"node": "<node_id>", "utilization_by_epoch": [{"epoch": <int>, "used": <int>, "capacity": <int>, "priority_used": <int>, "priority_capacity": <int>, "bucket_tokens_start": <int>, "bucket_tokens_end": <int>}, ...]}, ...]}`. Nodes sorted by node_id ascending.
- **`tenant_fairness_report.json`** - `{"tenants": [{"tenant": "<tenant_id>", "floor": <int>, "ceiling": <int>, "epochs": [{"epoch": <int>, "admitted": <int>, "target": <int>, "deviation": <int>}, ...]}, ...]}`. Tenants sorted by tenant_id ascending.
- **`migration_ledger.json`** - `{"events": [{"epoch": <int>, "stream": "<stream_id>", "from": "<node_id>", "to": "<node_id>", "cost": <int>}, ...], "total_cost": <int>}`. Events sorted by (epoch ascending, stream ascending).
- **`preemption_events.json`** - `{"events": [{"epoch": <int>, "victim": "<stream_id>", "class": "<class_id>", "beneficiary": "<stream_id_or_null>", "reason": "<string>"}, ...], "total_count": <int>}`. Events sorted by (epoch ascending, victim ascending). `reason` is one of `"no_feasible_node"` or `"cascade_evicted"`.
- **`sla_violation_report.json`** - `{"by_class": [{"class": "<class_id>", "breaches": <int>, "streams_placed": <int>}, ...], "total_breaches": <int>}`. Classes sorted by class_id ascending. `total_breaches` MUST be zero for a valid schedule.
- **`objective_breakdown.json`** - `{"alpha": <int>, "beta": <int>, "gamma": <int>, "fairness_deviation": <int>, "latency_cost": <int>, "migration_cost": <int>, "total_cost": <int>}` where `total_cost = alpha * latency_cost + beta * migration_cost + gamma * fairness_deviation`.
- **`fixed_point_trace.json`** - `{"converged": <bool>, "final_iteration": <int>, "iterations": [{"iteration": <int>, "delta": <int>, "admitted_total": <int>}, ...]}`.
- **`integrity_manifest.json`** - see Phase 11.
- **`final_state.json`** - see Phase 11.
- **`reusable_scheduler.py`** - the parameterised program. Must accept `<data_dir> <out_dir>` as positional arguments and produce the ten JSON artifacts identically to a run against `/app/data /app/out`. Must NOT import from `/tests`. Must NOT read `os.environ` for schedule inputs. Must NOT open the network.

## 5. Data-file schemas

### `fleet_nodes.csv`
Columns: `node_id, capacity, mtu_class, region, priority_lanes`. `node_id` matches `^N\\d{2}$`. `mtu_class` is one of `small`, `medium`, `jumbo`. `region` is one of the two-letter labels used in `tenants.csv`.

### `stream_manifest.csv`
Columns: `stream_id, tenant_id, class_id, arrival_epoch, deadline_epoch, rate_units, rate_profile`. `stream_id` matches `^S\\d{3}$`, `rate_profile` matches a row in `packet_rate_profiles.csv`.

### `tenants.csv`
Columns: `tenant_id, floor, ceiling, migration_mult, tenant_region`. `tenant_id` matches `^T\\d{2}$`.

### `qos_classes.json`
`{"classes": [{"class_id": "K01", "priority_rank": 3, "slo_max_hops": 2}, ...]}`. Higher `priority_rank` is stronger. `slo_max_hops` is compared to node-to-region hop counts.

### `token_buckets.csv`
Columns: `node_id, bucket_capacity, refill_num, refill_den, refill_offset`. Refill numerator and denominator are strictly positive integers.

### `mtu_matrix.csv`
Columns: `mtu_class, class_id, units`. Every (`mtu_class`, `class_id`) pair present in `fleet_nodes.csv` x `qos_classes.json` must appear exactly once.

### `migration_penalty_table.json`
`{"base": [{"tenant": "T01", "epoch": 0, "base": 4}, ...]}`. Every (tenant, epoch) pair must appear.

### `latency_matrix.csv`
Columns: `node_id, tenant_region, hops`. Every (node, tenant_region) pair present must appear exactly once.

### `preemption_ladder.json`
`{"ladder": [{"preemptor": "K01", "victim": "K02"}, {"preemptor": "K01", "victim": "K03"}, {"preemptor": "K02", "victim": "K03"}]}`. Cascade depth is exactly 1 per Phase 6b (a preempted stream may not preempt further this epoch).

### `epoch_windows.csv`
Columns: `epoch, duration_num, duration_den, warm_start`. `warm_start` is a semicolon-separated `stream_id=node_id` list, empty for non-zero epochs.

### `fixed_point_constants.json`
`{"alpha": 5, "beta": 3, "gamma": 2, "damping_num": 3, "damping_den": 3, "tolerance": 0, "max_iterations": 8}`.

### `packet_rate_profiles.csv`
Columns: `profile_id, base_rate, class_hint`.

## 6. The four withheld settlements

Four decisions inside phases 4, 6, and 8 were part of the original operational contract but their prose was lost from a prior version of this document. What survives is which quantity each settlement governs. The archive left a set of sealed reference corpora (`case-*.json` with companion `seal-*.json`) which were computed under the true settlements; a scheduler that picks the wrong reading for any of them will produce numbers that do not match at least one seal.

**Section 4.2 - Largest-remainder tie-break inside Phase 4.**
*The lost text settled which tenant receives an additional slot when two or more tenants are tied on the largest-remainder ranking during the apportionment step.* Candidates known to the archivists:
- `by_tenant_id_asc` - the tenant with the smallest tenant_id receives the additional slot.
- `by_stream_id_asc` - the tenant containing the still-unadmitted stream with the smallest stream_id receives the additional slot.

**Section 4.3 - Floor application order inside Phase 4.**
*The lost text settled the order in which the per-tenant floor is applied relative to the largest-remainder scaling.* Candidates:
- `floors_before_cap` - floors are baked into the initial vector, then largest-remainder scales down when the sum exceeds `total_cap`.
- `floors_after_cap` - largest-remainder is applied to the raw `min(demand, ceiling)` first, then floors are enforced by taking slots from tenants with surplus above floor.

**Section 6.4 - SLO comparison inside Phase 6.**
*The lost text settled whether the latency SLO check is strictly less than the class hop cap or non-strict less-than-or-equal.* Candidates:
- `strict_lt` - a candidate node is SLO-compliant when `latency < slo_max_hops`.
- `non_strict_leq` - a candidate node is SLO-compliant when `latency <= slo_max_hops`.

**Section 8.2 - Token bucket refill rounding inside Phase 8.**
*The lost text settled how the fractional refill quantity is rounded to an integer number of tokens.* Candidates:
- `floor` - `refill_int = numerator // denominator`.
- `ceil` - `refill_int = -(-numerator // denominator)`.
- `banker` - banker's rounding (round-half-to-even) on `numerator / denominator`.

Total search space over the four settlements: `2 * 2 * 2 * 3 = 24` combinations.

**Anti-overfit clause.** The scheduler will also be run on freshly-seeded corpora not present in this archive. The settlements chosen must be the ones the archive was written under, not a combination that happens to fit the six shipped seals and no others.

## 7. Determinism

All arithmetic must be integer. No `/` on ints, no `float` accumulators. Wherever a fractional intermediate arises (largest-remainder, refill), express it as `numerator, denominator` pairs and only round at the point the settlement specifies. Any observable float artefact (e.g. `1.0` in a JSON number field) is treated by the verifier as a bug.

## 8. Reproducibility

Given the same input files, two consecutive runs of `reusable_scheduler.py` must produce byte-identical artifacts. Any residual randomness (dict ordering, hash randomisation) that surfaces in output is a bug.
