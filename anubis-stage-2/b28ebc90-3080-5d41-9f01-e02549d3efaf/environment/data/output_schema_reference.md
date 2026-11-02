# Output schema reference

Twenty eight documents. Every one is published for every cycle,
including the cycles where its group is empty.

## CSV documents

Header line exactly as shown, columns in this order, one row per
record, rows in the stated order.

### `expansion_ledger.csv`
`routine_id,instance_id,action_id,occurrence_index,trigger_ms,window_id,status,reason`
One row per generated occurrence and one row per routine
withheld before it generates any. A routine that is not withheld
but generates no occurrence carries no row. `status` is
`expanded` or `withheld`. `reason` is
empty on an expanded row. Ordered by routine_id then
occurrence_index; a withheld routine carries occurrence_index
`-1` and an empty instance_id and window_id.

### `parameter_audit.csv`
`instance_id,field,value,winning_layer`
One row per instance per policy field, fields in the order
`tier`, `intensity_bp`, `cooldown_ms`, `mandatory`,
`max_occurrences`, `suppress`, `fallback_chain`. Booleans are
`true` and `false`; a fallback chain is joined with `;`.
Ordered by instance_id ascending, then by the field order above.

### `resource_demand.csv`
`window_id,device_id,instance_id,action_id,base_energy_mwh,intensity_bp,surcharge_bp,window_scale_bp,demand_mwh`
One row per instance that reached stage r09 and was not set
aside. Ordered by window ordinal, then device_id, then
instance_id.

### `window_capacity_report.csv`
`window_id,device_id,ceiling_mwh,reserve_mwh,mandatory_mwh,allocated_mwh,pool_remaining_mwh,overrun`
One row per window and device that carried demand in r10
against a ceiling row, in the group order stage r10 states. A
group displaced under `UNKNOWN_CEILING` has no row. `overrun` is
`yes` or `no`.
`allocated_mwh` is the discretionary energy allocated in r10,
which is the pool at the start of the discretionary phase less
what remained.

### `cooldown_state.csv`
`action_id,cooldown_until_ms,source_layer`
One row per action that fired in r13, ordered by action_id.
`source_layer` is the literal `resolved`.

### `suppression_ledger.csv`
`instance_id,reason,stage`
One row per instance set aside or withheld or displaced or
withdrawn or readmitted, naming the stage that did it. The
fallback outcomes are settled together: every terminal of r11
and of r12 names `r12`. Rows are sorted as whole tuples
ascending.

### `per_device_manifest.csv`
`device_id,circuit_id,instances,demand_mwh`
One row per device carrying at least one surviving instance,
ordered by device_id. `circuit_id` is empty when the topology
carries no member row for that device.

### `resource_utilization_report.csv`
`circuit_id,device_id,ceiling_mwh,allocated_mwh,utilisation_ratio,prior_cycle_mwh,delta_mwh`
One row per device that appears either in the surviving plan or
as a circuit member, ordered by circuit_id then device_id.
`ceiling_mwh` is the sum of that device's ceilings over every
window. `utilisation_ratio` is allocated over ceiling at twelve
decimal places, and is twelve zeros after the point when the
ceiling is zero. `prior_cycle_mwh` is the consumption recorded
for that device at the greatest cycle index in the energy
ledger, or zero when the ledger carries none.

## JSON documents

Two space indent, keys sorted, ASCII only, one trailing line
feed.

### `unit_normalization.json`
`{cycle_key, base_units, unit_counts, totals, quarantined}`.
`unit_counts` maps every unit token seen in the action catalogue
and the dependency edges to the number of recorded quantities
that carried it. `totals` is
`{duration_ms, energy_mwh, weight_bp}`: the summed durations and
energies of the catalogue rows that converted, and the summed
strengths of the edges that converted. `quarantined` is a list
of `{record, field, unit, reason}` sorted by record then field.

### `config_resolution.json`
`{instances, layer_ranks, settled_by_layer, live_device_policy_revisions, cooldown_floors_ms, reserve_bp}`.
`settled_by_layer` counts, per layer name and for `class_floor`,
how many instance fields that layer settled.
`live_device_policy_revisions` maps each device to the revision
of its `device_policies.csv` row in force under RR1.

### `trigger_eligibility_index.json`
`{eligible, withheld, counts}`. `eligible` is instance ids
ascending. `withheld` is `{instance_id, reason}` sorted.
`counts` maps reason to count.

### `dependency_graph.json`
`{nodes, edges, dropped}`. `edges` are
`{prereq, dependent, strength_bp, declared_seq, kind}` ordered by
prereq then dependent. `dropped` are
`{declared_seq, prereq, dependent, reason}` sorted by
declared_seq then reason.

### `cycle_break_ledger.json`
`{rounds, removals, surviving_edges}`. Each removal is
`{round, cycle, removed_prereq, removed_dependent, strength_bp, dependent_tier, declared_seq, key_settled_at}` in the order the
removals happened. `cycle` lists the nodes of the settled cycle
in the order the search found them, without repeating the first.

### `canonical_action_order.json`
`{action_order, instance_order, withheld}`.

### `initial_allocation.json`
`{count, allocated}` where each entry is
`{instance_id, window_id, device_id}` sorted by instance_id.

### `displaced_action_queue.json`
`{count, displaced}` where each entry is
`{instance_id, reason}` sorted.

### `fallback_expansion.json`
`{proposals, terminal}`. Each proposal is
`{instance_id, action_id, stands_in_for, window_id, device_id, demand_mwh}` sorted by instance_id.

### `precedence_reconciliation.json`
`{round_cap, groups, overturned}`. Each group is
`{window_id, device_id, round, proposals, incumbents, kept, pool_remaining_mwh}` sorted by round, then window_id, then
device_id; `incumbents` counts the holders the round started
with. Each overturned entry is
`{instance_id, window_id, device_id, round}`. `round_cap` is the
directive's cap.

### `final_action_order.json`
`{count, order}` in the final order stage r14 states.

### `derived_state.json`
`{state, set_at}`. `state` maps key to value. `set_at` maps key
to `{trigger_ms, action_id}` for the instance that last wrote it.

### `next_state_snapshot.json`
`{cycle_key, cycle_index, actions, oneshot_remaining, state}`.
`cycle_index` is the runtime's cycle index plus one. `actions`
maps action_id to `{last_fired_ms, cooldown_until_ms}` over the
actions that fired in the recomputed state pass. `state` is the
recomputed state.

### `per_context_manifest.json`
`{contexts}` mapping context_id to `{instances, demand_mwh}`,
instances sorted ascending.

### `daily_automation_manifest.json`
`{cycle_key, profile, windows, totals}`. Each window entry is
`{window_id, ordinal, instances, demand_mwh}` in window ordinal
order. `totals` is
`{instances, demand_mwh, terminal, readmitted}`.

### `summary.json`
`{cycle_key, profile, core_digest, publication_digest, control_totals}`. `control_totals` carries `actions_read`,
`aliases_bound`, `instances_expanded`, `instances_eligible`,
`edges_kept`, `cycles_settled`, `demand_rows`,
`initial_allocations`, `displaced`, `fallback_proposals`,
`overturned`, `final_instances`, `readmitted`, `terminal` and
`total_demand_mwh`.

## JSONL documents

One compact object per line, keys sorted, no spaces after the
separators. An empty group publishes a file of zero bytes.

### `alias_resolution.jsonl`
`{alias, canonical, kind, source, hops, status}`, one per
binding decision, sorted by alias then source then status.

### `audit_ledger.jsonl`
`{stage, records}` for each of the fourteen stages in stage
order. `records` is the size of that stage's principal result:
actions read, alias decisions, instances expanded, instances
resolved, instances eligible, edges kept, cycle removals,
instances ordered, demand rows, initial allocations, fallback
proposals, survivors after overturn, instances in the r13 order,
and instances in the final order.

## Markdown and text documents

### `terminal_action_report.md`
A level one heading `# Terminal actions for cycle <cycle key>`,
a blank line, a two column table with the header row
`| instance_id | reason |` and the separator row
`| --- | --- |`, one row per terminal instance sorted by
instance_id, a blank line, and the line
`Total terminal instances: <n>`.

### `run_manifest.txt`
One line per document other than `run_manifest.txt` and
`summary.json`, in file name order, each `sha256` then two
spaces then the file name. Then the line `core <hex>` and the
line `publication <hex>`.

## The repair record

Four further documents accompany the twenty eight and the
archive. They record the repair rather than the cycle. The
first two carry only a form; the register and the notes carry
facts, and those facts are checked.

### `build_report.json`
A JSON object, not an array and not empty.

### `selftest.json`
A JSON object, not an array and not empty, recording the run of
the shipped suite.

### `defect_register.md`
A markdown table carrying one row per repaired defect, each row
beginning with `|`, under the header row
`| defect | stage | function | rule restored |` and the usual
`| --- | --- | --- | --- |` separator. A register naming no
defect carries no row.

- `defect` is the solver's own label for the departure.
- `stage` is the stage, `r01` to `r14`, whose paper states the
  rule the shipped code departed from. A departure in a reader
  shared by every stage names the first stage that reads the
  affected paper.
- `function` names the top level function of the shipped
  project that carried the departure, as `<module>.<function>`
  with the module named without its package or suffix, for
  example `stages.stage_r03`. Two departures in one function
  are two rows.
- `rule restored` states the rule in a sentence.

The register is compared with the departures the shipped
source actually carries. A row naming a function of the
shipped project that carries no departure is a wrong entry, as
is a departure left out.

### `verification_notes.md`
At least three non blank lines, one per check the solver made.
Among them, for the cycle in `/app/data`, the line
`last_window_start_ms <n>` giving the start of the window with
the greatest ordinal, and for each distinct value of the
`reason` column of `suppression_ledger.csv` the line
`set_aside <REASON> <n>` giving the number of rows carrying it.
Each such line stands alone, with nothing else on it.
