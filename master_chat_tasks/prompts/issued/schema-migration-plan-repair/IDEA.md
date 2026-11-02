# Idea card: schema-migration-plan-repair (master-gated, 21 Oct 2026 12:45 IST)
Source: ChatGPT batch 20261021_data-processing, idea 4 "Schema Migration Repository Repair" (accepted as finalist 2). This card is the master's gated version and replaces the ChatGPT text where they differ.

## Premise
A data team consolidates partner records whose schemas evolved independently. A supplied multi-module Python repository (`source_repo.zip`: parser, planner, transform, report modules) upgrades historical records to the current canonical schema through a graph of migrations. It handles simple upgrades but plans paths on schema ids only, collapses field states, and misreports outcomes. The agent repairs the repository so its public pipeline transforms fresh partner feeds deterministically, and ships the patched repo plus the fixed reports.

## Inputs (about 12 files, stdlib-readable, at least 6 formats)
`source_repo.zip`; `repository_contract.md` (canonical schema contract, planner objective and tie-break, field-state rules, replay rules, module APIs, error catalogue, report schemas, size limits and time limit); `schema_versions.json`; `migration_edges.csv` (source, target, prerequisites on field presence, operations, cost); `field_policy.tsv`; `null_semantics.ini`; `partner_aliases.xml`; `partner_batches.jsonl`; `correction_log.txt`; `replay_manifest.csv`; `report_taxonomy.json`; `partner_order.tsv`.
No expected outputs, no precomputed migration paths.

## Spine (lever B)
parse contracts -> canonical partner identity -> per-record state signature -> plan (search over schema x state) -> execute steps (field-state aware) -> corrections and replay -> classify -> module reports and summary. Tests grade the planner on supplied graphs and the executor on supplied correct plans, through the repository's documented public API.

## Levers (ids for the registry)
- STANDARD A: hidden records combine a state-dependent edge, an equal-cost tie, an absent-vs-null default, and a correction that changes the replay fingerprint.
- STANDARD B: the chain above; a found plan is not a completed migration (a mid-path failure is classified as the contract says).
- STANDARD C (LV-MR-6): audit and repair; one defect lives in an intermediate representation shared by two modules, so a patch at one call site leaves the other wrong.
- STANDARD D (LV-MR-3): size ladder. The largest hidden graph has exponentially many paths; enumeration exceeds the stated time limit. The limit and the graph bounds are written in the contract.
- STANDARD F: rejection codes for unknown schema, unreachable target, failed prerequisite, cycle, parse error, replay conflict, invalid correction.
- NEW LV-MR-1 state-dependent feasibility: an edge applies only if its prerequisites hold on the current intermediate record. The documented state signature is the set of prerequisite-relevant fields present after each step. Two records with the same source and target schema can need different paths.
- NEW LV-MR-2 path tie-break: among minimum-cost plans, the lexicographically smallest sequence of edge ids wins. Plain Dijkstra with a per-node tie-break on the last edge does not give this; the search must order by (cost, edge-id sequence) under the stated limits.
- NEW LV-MR-4 absent vs explicit null through migration (secondary, likely to leak, weight light): defaults fill absent fields only, unless the field policy says otherwise.
- NEW LV-MR-5 replay identity (secondary, weight light): source-scoped key plus a payload fingerprint computed at the stated stage; same key and same fingerprint is a replay, same key and new fingerprint is a conflict unless a valid correction explains it.
- NEW LV-MR-7 attempted vs completed: a plan whose second step fails on a prerequisite created by a correction is reported as failed at that edge with the stated code, not as migrated.

## Master's changes to the ChatGPT idea
- Made D real: careful agents reach for Dijkstra by reflex, so D bites only with the state product graph plus the sequence tie-break (LV-MR-1 + LV-MR-2), not with path count alone.
- Marked null-provenance and replay identity as secondary with light weight (well-known idioms).
- Replaced the reviewer list (all "the log identifies X") with concrete-fact criteria (see the build prompt).
