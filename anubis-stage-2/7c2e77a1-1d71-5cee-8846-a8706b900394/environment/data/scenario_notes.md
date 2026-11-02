# Scenario notes

Tier: contract.

This document records what a scenario is and which material a scenario draws on. The conform contract in `conform_contract.md` governs how that material resolves.

## 1. The five live scenarios

A scenario is one delivery window of the conform house. The five live scenarios are `visible`, `peak`, `steady`, `burst` and `latency`. Each one is a separate conform run and produces its own result. No timeline or event is shared between scenarios.

| scenario | event shards | correction parts |
| --- | --- | --- |
| visible | `events_visible_a.csv`, `events_visible_b.csv` | `corrections_visible_p1.jsonl`, `corrections_visible_p2.jsonl` |
| peak | `events_peak_a.csv`, `events_peak_b.csv` | `corrections_peak_p1.jsonl`, `corrections_peak_p2.jsonl` |
| steady | `events_steady_a.csv`, `events_steady_b.csv` | `corrections_steady_p1.jsonl`, `corrections_steady_p2.jsonl` |
| burst | `events_burst_a.csv`, `events_burst_b.csv` | `corrections_burst_p1.jsonl`, `corrections_burst_p2.jsonl` |
| latency | `events_latency_a.csv`, `events_latency_b.csv` | `corrections_latency_p1.jsonl`, `corrections_latency_p2.jsonl` |

The two shards of a scenario are two parts of one event set and carry no order between them. The same holds for the two correction parts.

Every scenario reads all four override streams, `overrides_2025h1.jsonl`, `overrides_2025h2.jsonl`, `overrides_2026h1.jsonl` and `overrides_2026h2.jsonl`, and keeps the records whose event uid belongs to the scenario.

Every scenario reads every reference table, every configuration layer and every observation log in this folder. Those files carry rows for all scenarios together.

## 2. The archive name

The name `archive` occurs in the scenario column of `delivery_exceptions.csv` and `nesting_edges.tsv`. It names a retired delivery window that is no longer conformed. Rows naming `archive` belong to that retired window.

## 3. Scale

`peak` carries the largest event set. `visible`, `steady`, `burst` and `latency` carry event sets of similar size to one another. Timeline counts differ between scenarios, and a timeline identifier is unique only inside its own scenario.

## 4. Extracts

A conform run reads a folder holding the same file names as this one. An extract folder may hold a single event shard for a scenario rather than two, and may hold a single correction part rather than two. A run resolves the files of a scenario by name from the folder it is given.

An extract folder holds every reference table, every configuration layer and every observation log named in `index.md`, and holds at least one event shard for the scenario being run.
