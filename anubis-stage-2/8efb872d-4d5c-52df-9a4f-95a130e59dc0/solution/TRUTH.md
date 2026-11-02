# TRUTH.md - 8efb872d-4d5c-52df-9a4f-95a130e59dc0

## Defect

The edge cache placement optimizer reads fifty operational exports and turns them into per-node peak cache footprints, a shield pool allocation, a RAM pin plan, a risk ranking and a post-cut projection with spill grants and capacity tickets. Its figures are wrong because it trusts the surface of every file: it takes the dominant convention of each export at face value, counts out-of-scope, mirrored and injected readings, ignores dated history, and reads the earlier optimizer run as if it were a measurement. The written authority is `/app/data/edge_capacity_standard_r7.md`; the output shapes and the phase 2 and phase 3 arithmetic are fixed in `/app/data/OUTPUT_CONTRACT.md`. The solver must rebuild the optimizer as `/app/out/build.py` and produce eighteen phase artifacts with it. The planning cut is 2024-10-01T18:00:00Z; 1637 nodes and 10140 (node, property) pairs are in scope and 570 approved amendments are pending after the cut.

1. (focal) Daily volume is computed from counter readings that are polluted. Readings injected during the failover drill (listed reading by reading in `replay_inject_q3.prom`), readings from mirror instances (`mirror_twins.json`), lab instances (`labnodes.tsv`) and staging jobs (`stg_jobs.toml`) sit inside the twenty-two production shards beside the real series. Some exporters count in KiB (`scrape_targets.toml`), resets appear as drops, readings fall outside the 7-day window, the 3.x exporter writes the series under a second metric name, and timestamps arrive as epoch seconds, epoch milliseconds, offset ISO strings, SQL offsets and PoP-local wall times. Defeats `p1_properties_sample_counts`, `p1_properties_daily_volume`, `p1_footprints_cycle_bytes`, `p1_footprints_hot_and_stale` and `p1_footprints_peak`.
2. (focal) The effective cache policy is layered. Global directives (later wins), the class block location, approved class-scope amendments, node blocks across the main file and two include files in include order, and approved node-scope amendments each override only what they set. Amendment status comes from the register export unless a CAB decision dated at or before the cut replaces it, and many values sit in `tuning_drafts.jsonl` behind a `value_ref`. A `codec` without `codec-level` resets the level, and `brotli` names the `br` codec. Defeats `p1_policies_complete`.
3. (focal) Scope and identity. Nodes are referenced by canonical id in any case, FQDN, asset tag, serial, pre-rename names and PoP-scoped legacy names; the directory export is folded and partly base64, and the overrides file resolves by highest revision with rename chains. A node is in scope only when its asset status, installed PoP placement, decommission calendar (Etc/GMT zones use the IANA sign), hardware class ledger and tier all agree as of the cut, and a production scraper watches it (a registered instance in `scrape_targets.toml` that is not a mirror or lab instance). Defeats `p1_nodes_complete`, `p1_properties_scope_complete` and `p1_pops_complete`; scope and value observables are priced separately.
4. (focal) The optimization stages are written-order folds with caps. The shield pool is consumed by tier, then non-pending before pending, then file order; the RAM pin plan is a first-fit greedy walk by exact density that skips a candidate that does not fit and keeps walking; spill grants are capped by the remaining budget and by the fleet's 90th percentile headroom; tickets are capped by quota. Defeats `p2_shield_allocation_complete`, `p2_pin_plan_complete`, `p3_spill_allocation_complete` and `p3_tickets_complete`.
5. (drift) An experienced operator assumes the policy refresh is the refresh the node sees. The standard caps it by the sweep interval of the node (`sweeper.crontab`, where commented and `--dry-run` lines sweep nothing, `scratch.conf` runs are another config and `0 4 * * 7` is Sunday). Defeats `p1_policies_complete` and `p1_nodes_complete`.
6. (drift) Capacity and memory units look uniform but are not: `TB` and `GB` are decimal for capacities, while every memory suffix is binary; `df -h` figures convert by floor; sata media reserve nothing whatever the reserve column says and an nvme `-` means 7 percent. Defeats `p1_pops_complete` and `p1_nodes_complete`.
7. (trap) Everything dated is read as of the cut. Post-cut placements, class rows, tier entries, memory upgrades, audits, usage snapshots, property changes and CAB decisions are present and look current. Approved amendments effective after the cut must not touch phase 1 at all; they are carried in `pending.json` and applied only in phase 3. Defeats `p1_pending_complete`, `p1_nodes_complete`, `p3_projection_values_complete` and `p3_pop_outlook_complete`.
8. (trap) The earlier optimizer run (`optplan_prev.csv`) is the only source of the reported prior peak, but only its `q2-final` rows count and they are a baseline, never a measurement; reading its numbers as current footprints is wrong. The late usage collection (`ducollect_late.log`) is the only source of post-cut usage and holds nothing that applies before the cut. Defeats `p1_nodes_complete`, and through the phase 3 prior gap and observed usage it decides `p3_projection_values_complete` and `p3_class_drift_complete` on the true upstream.

The reference program was written from the standard and the contract alone and computes every value from the input directory; the phase 2 and phase 3 stages read only the upstream directories they are handed.

Out of bounds: no network access, no third-party packages, no edits under `/app/data`, and the output files must come from running the program.

## Load-bearing work

Declared artifacts:

- `/app/out/p1/nodes.csv`
- `/app/out/p1/properties.csv`
- `/app/out/p1/policies.csv`
- `/app/out/p1/footprints.csv`
- `/app/out/p1/pending.json`
- `/app/out/p1/pops.json`
- `/app/out/p2/pop_rollup.csv`
- `/app/out/p2/class_rollup.csv`
- `/app/out/p2/shield_alloc.csv`
- `/app/out/p2/pin_plan.csv`
- `/app/out/p2/risk_rank.csv`
- `/app/out/p2/manifest.json`
- `/app/out/p3/projection.csv`
- `/app/out/p3/pop_outlook.csv`
- `/app/out/p3/spill_alloc.csv`
- `/app/out/p3/tickets.csv`
- `/app/out/p3/class_drift.csv`
- `/app/out/p3/manifest.json`
- `/app/out/build.py`

The input directory carries 52 files: fifty counted exports (forty-two in scope and eight decoys whose correct use is narrow: four exclusion registers, the reported baseline run, the draft proposals referenced by `value_ref`, the 2023 configuration whose only authoritative content is the property rename map, and the late usage collection that only feeds post-cut usage) plus the standard and the contract.

Phase 1 content: one row per in-scope node in `nodes.csv` and one row per (node, property) pair in `properties.csv`, `policies.csv` and `footprints.csv`, keyed and ordered as the contract says; `pending.json` with the cut and the pending amendments; `pops.json` with the prod PoP facts in KiB, minutes and percent, including each PoP's total RAM pin budget over its in-scope nodes. Phase 2 content: PoP and class rollups, the cumulative shield pool allocation in written order, the greedy RAM pin plan, the risk ranking with pin share, and a manifest bound by SHA-256 to the six phase 1 files. Phase 3 content: the projection after pending amendments (headroom measured from the observed post-cut usage where one exists, and the gap to the reported prior peak) with its running headroom fold, the PoP outlook, the spill allocation with deferrals and the 90th percentile cap, quota-capped tickets, class drift, and a manifest bound to all twelve upstream files with a chained digest over the projection.

Lossy boundaries the cascade depends on: phase 1 rounds every byte figure to KiB half to even (cycle, hot, stale and peak each rounded on their own), phase 1 rounds the compression ratio to 2 decimals before any footprint uses it, phase 2 sums KiB and rounds again to MiB (`peak_mib`, `usable_mib`, `headroom_mib`, `shield_mib`, `shield_share_mib`, `daily_mib`), phase 2 averages the already rounded ratios to 3 decimals, phase 2 divides rounded daily KiB into rounded headroom for days, phase 3 recomputes footprints only for amended pairs from the rounded ratio and reuses phase 1 `peak_kib` elsewhere, phase 3 divides by phase 2 MiB figures times 1024 for its shares, phase 3 converts the post-cut usage bytes to KiB on its own rounding, and phase 3 rounds summed KiB to MiB again for the outlook and drift. Null daily volume stays distinct from zero volume (an empty days field against `never`, `unmeasured` against `zero` in the shield allocation). The shield allocation, the pin plan, the projection running headroom and the projection chain are written-order folds; three cumulative caps (shield pool, per-node pin budget, spill budget) and the ticket quota consume budgets in contract order. A solver that recomputes phase 2 or phase 3 from the raw exports instead of the phase 1 files lands on different digits.

Cascade dependency matrix (rows are downstream files, columns are upstream files; each filled cell names the upstream locators the downstream file reads):

| downstream | p1 nodes | p1 properties | p1 policies | p1 footprints | p1 pending | p1 pops | p2 pop_rollup | p2 class_rollup | p2 shield_alloc | p2 pin_plan | p2 risk_rank | p2 manifest |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p2 pop_rollup | pop, usable_bytes, base_used_bytes | node_id, property, daily_bytes | node_id, property, store_compressed | node_id, property, peak_kib | scope, node_id, class, property | pop, shield_pool_kib, order | | | | | | |
| p2 class_rollup | class, pop, node_id | node_id, property, daily_bytes | store_compressed, ratio, node_id | node_id, property, peak_kib | scope, class, property | pop, shield_pool_kib, order | | | | | | |
| p2 shield_alloc | tier, pop, row order | node_id, property, daily_bytes | node_id, property, store_compressed | node_id, property, stale_kib | scope, node_id, class | pop, shield_pool_kib, order | | | | | | |
| p2 pin_plan | ram_bytes, pop, row order | node_id, property, daily_bytes | node_id, property, effective_refresh | node_id, property, hot_kib | scope, node_id, class, property | pop, ram_pin_pct, order | | | | | | |
| p2 risk_rank | pop, usable_bytes, base_used_bytes, ram_bytes | node_id, property, daily_bytes | node_id, property, effective_refresh | node_id, peak_kib, hot_kib | freeze_utc, scope, node_id | pop, utc_offset_minutes, ram_pin_pct | | | | | | |
| p2 manifest | bytes digest, row count, usable_bytes | bytes digest, daily_bytes, null count | bytes digest, store_compressed, effective_refresh | bytes digest, peak_kib, hot_kib | bytes digest, amendments count, freeze_utc | bytes digest, shield_pool_kib, ram_pin_pct | | | | | | |
| p3 projection | usable_bytes, base_used_bytes, post_cut_used_bytes, prior_peak_kib, sweep_interval | node_id, property, daily_bytes | versions, refresh, ratio | node_id, property, peak_kib | field, value, scope | pop, utc_offset_minutes, order | pop, headroom_mib, order | class, peak_mib, order | node_id, granted_kib, row set | node_id, hot_kib, pinned | node_id, daily_kib, rank | phase, inputs, median_days_to_full |
| p3 pop_outlook | pop, usable_bytes, post_cut_used_bytes | node_id, property, daily_bytes | versions, refresh, ratio | node_id, property, peak_kib | scope, node_id, class | shield_pool_kib, spill_budget_kib, order | pop, headroom_mib, order | class, peak_mib, order | node_id, granted_kib, row set | node_id, hot_kib, pinned | node_id, daily_kib, rank | phase, inputs, median_days_to_full, p90_headroom_kib |
| p3 spill_alloc | tier, pop, post_cut_used_bytes | node_id, property, daily_bytes | versions, refresh, ratio | node_id, property, peak_kib | field, value, scope | pop, spill_budget_kib, order | pop, headroom_mib, order | class, peak_mib, order | node_id, granted_kib, row set | node_id, hot_kib, pinned | node_id, daily_kib, rank | phase, inputs, p90_headroom_kib |
| p3 tickets | pop, class, node_id | node_id, property, daily_bytes | versions, refresh, ratio | node_id, property, peak_kib | field, value, scope | pop, ticket_quota, order | pop, headroom_mib, order | class, peak_mib, order | node_id, granted_kib, row set | node_id, hot_kib, pinned | node_id, daily_kib, rank | phase, inputs, median_days_to_full |
| p3 class_drift | class, pop, prior_peak_kib | node_id, property, daily_bytes | versions, refresh, ratio | node_id, property, peak_kib | field, value, scope | pop, shield_pool_kib, order | pop, headroom_mib, order | class, peak_mib, order | node_id, granted_kib, row set | node_id, hot_kib, pinned | node_id, daily_kib, rank | phase, inputs, median_days_to_full |
| p3 manifest | bytes digest, row count, usable_bytes | bytes digest, daily_bytes, node_id | bytes digest, versions, ratio | bytes digest, peak_kib, node_id | bytes digest, amendment ids, field | bytes digest, spill_budget_kib, ticket_quota | bytes digest, headroom_mib, pop | bytes digest, peak_mib, class | bytes digest, granted_kib, node_id | bytes digest, hot_kib, pinned | bytes digest, daily_kib, rank | bytes digest, phase, inputs, p90_headroom_kib |

Filled cells: 36 phase 2 cells and 72 phase 3 cells, 108 in total. No phase 2 file reads a phase 2 sibling and no phase 3 file reads a phase 3 sibling. Every filled cell carries value-level influence: altering that upstream file alone, with every other upstream file held fixed, changes the bytes of that downstream file (manifests compared without their digest map).

## Verification

`tests/test.sh` clears stale reward files, locks the log directory, restricts `/tests` and hands over to rewardkit. The test channel compares the declared phase 1 files with ground truth embedded in `tests/test_output.py`. Each artifact or coherent field group is one observable, with scope graded separately from values. It then runs a verifier-staged copy of the delivered program unprivileged, with `/app/out` closed to that user, on two upstreams: the ground truth of the shipped input, and a small synthetic variant upstream (`_VARIANT_BLOB`) the agent never sees. Every phase 2 and phase 3 semantic check must hold on both. The variant is built so every contract branch fires: shield grants in all five states with a pending node ordered behind a non-pending one of the same tier, a pin plan with zero-KiB candidates, a skipped candidate followed by a smaller one that still fits, hourly and pending pairs left out and nodes with no candidates, days to full that are empty, `never`, `0.00` and numeric, a class with null daily MiB and null mean ratio, a PoP with non-positive headroom (empty PoP shares and a doubled ticket quota), a PoP with no numeric days (empty mean days and worst class), a node whose daily KiB rounds to 0 but whose peak grows (a `never` ticket), spill rows in all four states including a deferred tier 3 node and a grant held to the 90th percentile headroom, and nodes with and without post-cut usage and a reported prior peak (an empty prior gap and a class with no prior gap). A phase 1 slip therefore does not cascade into the phase 2 and phase 3 checks, and a program that stores or copies its own answers cannot pass them. The verifier also restages the shipped input from an embedded copy to rerun phase 1, alters copies of the input and of the upstream directories to prove the program follows what it is handed, and plants a copy of the input at the agent's input mount to detect fixed-path reads. Phase 1 runs are limited to 420 seconds and every other run to 120 seconds.

Channel A carries 31 positive and 4 negative checks; the positive total is 135 and the negative total is -16, so on its own the channel ranges -16/135 = -0.119 to +1.000.

Positive checks:

- `declared_artifacts_present` and `declared_artifacts_format` (weight 1 each)
- `p1_nodes_complete`, `p1_properties_scope_complete`, `p1_properties_sample_counts`, `p1_properties_daily_volume`, `p1_policies_complete`, `p1_footprints_cycle_bytes`, `p1_footprints_hot_and_stale`, `p1_footprints_peak`, `p1_pending_complete` and `p1_pops_complete` (weight 5 each)
- `phase1_reproduces_declared` (weight 3)
- `p2_rollups_complete`, `p2_shield_allocation_complete`, `p2_pin_plan_complete`, `p2_risk_values_complete`, `p2_risk_ranking_complete` and `p2_manifest_complete` (weight 5 each)
- `phase2_reproduces_declared`, `phase2_replaces_stale_outputs` and `command_usage_errors` (weight 3 each)
- `p3_projection_values_complete`, `p3_projection_shares_complete`, `p3_pop_outlook_complete`, `p3_spill_allocation_complete`, `p3_tickets_complete`, `p3_class_drift_complete` and `p3_manifest_complete` (weight 5 each)
- `phase3_reproduces_declared` and `command_upstream_errors` (weight 3 each)

Negative checks:

- `negative_phase1_input_contract_violation` (weight -5)
- `negative_content_determinism_violation` (weight -3)
- `negative_downstream_input_contract_violation` (weight -5)
- `negative_output_scope_violation` (weight -3)

Channel B, judged from the trajectory and final message, carries 35 criteria (30 positive and 5 negative), with positive total 80. R1 to R10 enforce the stated work rules. R11 to R30 are conduct checks for independent verification of the task's high-risk derivations. R31 to R35 enforce the stated boundaries and truthful reporting rules.

- **R1** (+3, trajectory): The agent opens /app/data/edge_capacity_standard_r7.md or /app/data/OUTPUT_CONTRACT.md before it first writes /app/out/build.py.
- **R2** (+3, trajectory): The agent views the contents of at least three different counter export files under /app/data before it writes the code that parses them.
- **R3** (+3, trajectory): The agent runs /app/out/build.py for phase1, phase2 and phase3 during the session.
- **R4** (+1, trajectory): The agent opens at least one file written by its own runs of /app/out/build.py after those runs finish.
- **R5** (+3, trajectory): The agent compares at least one computed phase 1 value with the raw input records it was derived from.
- **R6** (+3, trajectory): The agent writes /app/out/build.py as named functions, including a separate function for each of phase1, phase2 and phase3.
- **R7** (+1, trajectory): The agent's /app/out/build.py handles file and parse errors with specific exception types and contains zero bare except clauses.
- **R8** (+1, trajectory): The agent runs at least one stage of /app/out/build.py with input and output directories located outside /app/data and /app/out.
- **R9** (+1, user_facing_message): The response names the three phase output directories under /app/out.
- **R10** (+1, user_facing_message): The response states the command used to run build.py.
- **R11** (+3, trajectory): Compare sample counts for at least three pairs from three counter formats with raw records.
- **R12** (+3, trajectory): Recalculate daily bytes for at least three pairs from three counter formats.
- **R13** (+3, trajectory): Recalculate a daily volume where a kept counter drops and the reset value contributes to the increase.
- **R14** (+3, trajectory): Verify a window decision across second and millisecond epoch spellings.
- **R15** (+3, trajectory): Verify a bare local counter timestamp using its PoP offset.
- **R16** (+3, trajectory): Verify a KiB counter through conversion to daily bytes.
- **R17** (+3, trajectory): Trace an overlapping pair through series de-duplication and its sample count.
- **R18** (+3, trajectory): Trace one mirror exclusion through a computed pair.
- **R19** (+3, trajectory): Trace one lab exclusion through a computed pair.
- **R20** (+3, trajectory): Trace one staging exclusion through a computed pair.
- **R21** (+3, trajectory): Recalculate one phase 2 PoP peak and headroom.
- **R22** (+3, trajectory): Recalculate one phase 2 class daily and peak MiB.
- **R23** (+3, trajectory): Recalculate one shield demand, grant and cumulative value.
- **R24** (+3, trajectory): Recalculate one pin density and budget decision.
- **R25** (+3, trajectory): Recalculate one node's days to full and local date.
- **R26** (+3, trajectory): Recalculate one amended phase 3 node.
- **R27** (+3, trajectory): Recalculate one phase 3 PoP outlook.
- **R28** (+3, trajectory): Recalculate one spill grant and remaining budget.
- **R29** (+3, trajectory): Verify one ticket against quota and ordering.
- **R30** (+3, trajectory): Recompute the phase 3 projection chain.
- **R31** (-5, trajectory): The agent opens a file under /tests or /logs/verifier during its run.
- **R32** (-3, trajectory): The agent modifies, deletes or adds a file under /app/data.
- **R33** (-1, trajectory): The agent runs pip, apt-get, curl, wget or another command that tries to fetch packages or files from the network.
- **R34** (-5, user_facing_message): The response states that a run or a comparison succeeded while the trajectory shows that run or comparison failed or was never performed.
- **R35** (-3, trajectory): The agent writes or edits a phase output through an editor or shell redirection rather than by running build.py.

Every oracle figure claimed for this task is a test-channel figure: the judged channel has no oracle score.

## Root cause

**Surface trust.** Each export has a dominant convention (seconds in one shard, canonical ids in another, bytes in most exporters) that is wrong for a large share of its own lines. The old optimizer applied the dominant convention everywhere.

**History without a cut.** Placements, classes, tiers, statuses and memory, audits, snapshots, property changes, CAB decisions and amendments are all histories. The standard reads each as of the cut; the old optimizer read the latest row.

**Exclusion registers dressed as data.** Four decoy files carry readings or instances that look like more measurements. Their only correct use is to remove matching readings from the shards.

**Layering.** Policy is a stack of five layers with directive-level overrides and a level reset on `codec`; amendments split between the register export, the board minutes and the draft proposals.

**Greedy order matters.** The pin plan, the shield allocation and the spill allocation are greedy folds whose results depend on the exact sort keys and on comparing densities and shares as exact fractions rather than as their rounded text.

**Cascade discipline.** Phase 2 and phase 3 must be computed from the phase 1 and phase 2 files, with the contract's rounding, ordering and folds, because the boundary is lossy.

## Solution shape

1. Read the cut from the standard; build the identity resolver from the directory export (unfolding continuation lines and decoding base64 values) and the overrides file (highest revision per key, rename chains).
2. Read the PoP table and installed placements as of the cut; resolve statuses with their memory, the class ledger, tiers and confirmed decommissions; derive the in-scope node list.
3. Build class templates from the class blocks of the main cache configuration, apply property changes as of the cut, and resolve property references through aliases, the 2023 rename map and per-node paths.
4. Parse the global section, class blocks, node blocks (main file then includes in order), register export, CAB minutes and draft proposals; stack the layers per pair; derive codecs, benchmark ratios and the sweep-capped effective refresh.
5. Load exporter units and the four exclusion registers; read every counter shard by content; resolve, filter, dedupe and window the readings; compute reset-aware daily volume per pair.
6. Read the block device audit, usage collections and the reported baseline; compute usable bytes, base usage, post-cut usage and prior peak.
7. Write the six phase 1 files; compute phase 2 from them alone (rollups, shield fold, greedy pin plan, ranking); check the phase 2 manifest binding, then compute phase 3 from the twelve files alone, applying the pending amendments there.

## Ordered plan

1. Read `edge_capacity_standard_r7.md` and `OUTPUT_CONTRACT.md` end to end (judged criterion R1).
2. Open several counter exports in different formats and note how nodes, properties, instants and values are written (R2).
3. Write the identity, scope and policy code as named functions with one function per phase (R6), checking a few nodes by hand against the raw records (R5).
4. Validate counter parsing across formats: compare sample counts and daily bytes for three pairs (R11-R12), then exercise a reset, mixed epoch units, local time, KiB units, overlap de-duplication and each exclusion register (R13-R20).
5. Write phase 2 from the contract and independently recalculate one PoP rollup, class rollup, shield row, pin decision and risk date (R21-R25).
6. Write phase 3 from the contract and independently recalculate one amended projection, PoP outlook, spill row, ticket and projection chain (R26-R30).
7. Run all three stages on `/app/data` (R3), read the results (R4), and run a stage on copies in other directories to confirm it only reads what it is handed (R8).
8. Finish with a summary naming the output directories (R9) and the command that runs `build.py` (R10).

## Pitfalls

- Taking the shard's dominant timestamp form for every line, or reading PoP-local wall times as UTC, shifts readings across the window edge (`p1_properties_sample_counts`).
- Summing readings from mirror, lab or staging instances, or keeping injected readings, inflates daily volume (`p1_properties_daily_volume`).
- Treating every exporter as bytes misses KiB counters (`p1_properties_daily_volume`).
- Taking the latest placement, class row, tier row or memory value regardless of the cut picks post-cut records (`p1_nodes_complete`).
- Reading `Etc/GMT-2` as two hours west flips decommissions that sit near the cut (`p1_nodes_complete`).
- Reading a `GB` memory size as decimal undercounts memory and every pin budget built on it (`p1_nodes_complete`).
- Ignoring the sweep interval cap leaves daily policies on weekly nodes too small (`p1_policies_complete`).
- Applying post-cut amendments in phase 1 changes every footprint they touch (`p1_footprints_peak`, `p1_pending_complete`).
- Using `TB` as binary or ignoring the sata rule shifts capacities (`p1_pops_complete`, `p1_nodes_complete`).
- Recomputing phase 2 from raw bytes instead of the phase 1 KiB figures breaks the double rounding (`p2_rollups_complete`).
- Stopping the pin walk at the first candidate that does not fit, or sorting by the rounded density text, pins the wrong pairs (`p2_pin_plan_complete`).
- Placing pending nodes before non-pending ones, or sorting tiers descending, reorders the shield allocation and, where the pool runs out, moves the partial and refused grants to other nodes (`p2_shield_allocation_complete`).
- Forgetting the 90th percentile cap or the tier 3 deferral hands the spill budget to the wrong nodes (`p3_spill_allocation_complete`).
- Projecting from the pre-cut base usage when a post-cut snapshot exists, or treating a missing prior peak as 0, moves every phase 3 headroom and gap built on it (`p3_projection_values_complete`).

## Provenance

```yaml
uuid: 8efb872d-4d5c-52df-9a4f-95a130e59dc0
instance_id: 8efb872d-4d5c-52df-9a4f-95a130e59dc0
task_name: terminal-bench/8efb872d-4d5c-52df-9a4f-95a130e59dc0
fix_patch_sha256: dd79334dbc614087f49516f09cf91bd32be33efe4ef01e0e9331ee78e4af2d05  # sha256 of solution/solve.sh
solve_py_sha256: f813b71e91e3ac091790f320b70fd81be2306f121086b3895f01056744a7b973  # sha256 of solution/solve.py (1419 lines)
language: python
input_files: 52  # files under /app/data
corpus_sha256: a0dbc9def52d2249fcadef0e99ed327e3f65e842883ffd70d88e320139c80d37  # sha256 over "<name> <sha256 of bytes>" lines of every /app/data file, sorted by name, LF joined
reference_outputs_sha256: 90b92c54d57b7710ea2af0b0131bb73aeb5ea2e73646cda652fa14c71a0c3139  # same digest over "<phase>/<name> <sha256>" lines of the eighteen files solve.py writes
variant_upstream_sha256: 79172f17611f59300c8481662b0d117d2c295147eb31baf313e38feafeaa3d32  # same digest over the eighteen variant upstream and expected files
golden_score_measured: null  # filled from the test-channel execution gate, never from the judged channel
golden_score_runs: 0  # no oracle run is recorded inside the bundle
golden_score_verified_by: null  # the execution gate report carries the measured figures
```
