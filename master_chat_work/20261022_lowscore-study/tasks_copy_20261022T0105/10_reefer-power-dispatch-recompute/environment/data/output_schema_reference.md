# Output schema reference

Every published document, its delimiter, its header and its row
order. A header is written once, as the first line, with the columns
in the order below and nothing else on the line.

## `availability_lattice.csv`

delimiter: comma

header: reefer_id, first_interval, last_interval, slot_count, window_state

row order: reefer identifier ascending

## `interval_demand.csv`

delimiter: comma

header: interval, feeder_id, connected_count, nominal_demand_w

row order: interval ascending, then feeder identifier ascending

## `energy_floor_ledger.csv`

delimiter: comma

header: reefer_id, slot_count, mandatory_wh, requested_wh, discretionary_wh, floor_state

row order: reefer identifier ascending

## `dispatch_priority_queue.csv`

delimiter: comma

header: rank, reefer_id, deadline_slack, class_rank, urgency_rank, queue_state

row order: the queued reefers by rank ascending, then the reefers the ladder set aside by reefer identifier ascending

## `provisional_allocation.psv`

delimiter: vertical bar

header: interval, feeder_id, reefer_id, draw_w, allocation_state

row order: interval ascending, then feeder identifier, then reefer identifier

## `feeder_load_ledger.csv`

delimiter: comma

header: interval, feeder_id, capacity_w, reserve_w, reserved_capacity_w, load_w, headroom_w, load_state

row order: interval ascending, then feeder identifier

## `feeder_violation_ledger.csv`

delimiter: comma

header: interval, feeder_id, provisional_load_w, reserved_capacity_w, excess_w, removed_count

row order: interval ascending, then feeder identifier

## `spill_decisions.tsv`

delimiter: tab

header: reefer_id, from_interval, to_interval, feeder_id, draw_w, spill_state

row order: from interval ascending, then feeder identifier, then reefer identifier

## `crane_adjusted_capacity.csv`

delimiter: comma

header: interval, feeder_id, reserved_capacity_w, crane_draw_w, adjusted_capacity_w, clamp_state

row order: interval ascending, then feeder identifier

## `battery_schedule.csv`

delimiter: comma

header: interval, action, deficit_wh, discharge_wh, charge_wh, limit_reason

row order: interval ascending

## `soc_ledger.psv`

delimiter: vertical bar

header: interval, opening_soc_wh, closing_soc_wh, reserve_wh, soc_state

row order: interval ascending

## `reconciliation_iterations.csv`

delimiter: comma

header: pass, feeder_id, reefer_id, opening_share_wh, need_wh, target_wh, closing_share_wh, pass_state

row order: pass ascending, then feeder identifier, then reefer identifier

## `tariff_charge_ledger.csv`

delimiter: comma

header: interval, tariff_band, price_tenth_cents_per_kwh, load_w, energy_wh, charge_cents

row order: interval ascending

## `deadline_correction.csv`

delimiter: comma

header: reefer_id, interval, displaced_reefer_id, feeder_id, correction_state

row order: interval ascending, then feeder identifier, then reefer identifier

## `final_schedule.csv`

delimiter: comma

header: interval, feeder_id, reefer_id, base_draw_w, allowance_wh, energy_wh, schedule_state

row order: interval ascending, then feeder identifier, then reefer identifier

## `final_schedule_by_feeder.psv`

delimiter: vertical bar

header: feeder_id, interval, load_w, adjusted_capacity_w, battery_support_w, feeder_state

row order: feeder identifier, then interval ascending

## `unmet_requirement_report.tsv`

delimiter: tab

header: reefer_id, feeder_id, vessel_id, shortfall_wh, shortfall_intervals, unplaced_allowance_wh, surcharge_cents

row order: reefer identifier ascending

## `reefer_service_certificate.csv`

delimiter: comma

header: reefer_id, feeder_id, vessel_id, required_wh, served_wh, shortfall_wh, shortfall_intervals, allowance_wh, unplaced_allowance_wh, surcharge_cents, service_state

row order: reefer identifier ascending

## `normalised_reefers.jsonl`

One object per reefer, in reefer identifier order, with the keys in
this order: reefer_id, plug_id, feeder_id, substation_id, vessel_id,
temperature_class, nameplate_w, unit_state, connect_minute,
disconnect_minute, declared_energy_wh, source_system. Every value is
a string except nameplate_w, connect_minute and disconnect_minute,
which are numbers, and declared_energy_wh, which is a number when a
return declared one and the string not_declared when none did.

## `audit_trace.jsonl`

One object per stage, in stage order, with the keys stage, note and
measure. The note is the stage title the contract overview prints,
without the stage label that precedes it. RULE P14.i of
spec_stage_p14_publication.md settles what the measure of a stage
counts.

## `cycle_break_report.json`

Keys in this order: day_id, sweeps_run, sweep_budget, closing_state,
settled_at_sweep, correction_count, cycle_count, cycles,
frozen_reefers, state_signatures. settled_at_sweep is zero when
the closing state is not settled. Each entry of cycles carries
sweep, short_reefer, displaced_reefer, interval and broken, in
that order. frozen_reefers is a list of reefer identifiers in
ascending order. state_signatures is a list of the first sixteen
characters of each state signature, the opening state first.

## `peak_demand_certificate.json`

Keys in this order: day_id, yard_peak_w, yard_peak_interval,
substations, demand_charge_cents. Each entry of substations carries
substation_id, peak_w, peak_interval, band_code and charge_cents, in
that order, and the entries follow the substation order the topology
prints.

## `objective_vector.json`

Keys in this order: day_id, lexicographic_order, hard_violations,
unmet_mandatory_wh, deadline_penalty_cents, peak_demand_w,
energy_cost_cents, battery_cycle_wh, tie_key. lexicographic_order is
the list of the six measured component names followed by tie_key, in
the order the objective is compared in.

## `constraint_certificate.json`

Keys in this order: day_id, feeder_intervals_over_capacity,
state_of_charge_below_reserve, reefers_at_share_ceiling,
unplaced_allowance_wh, reefers_refused, reefers_queued, spill_count,
unspilled_count. feeder_intervals_over_capacity and
state_of_charge_below_reserve are the two counts RULE P13.b adds into
the hard violations. reefers_at_share_ceiling counts the queued
reefers whose share after the last pass stands above zero and equals
its limit under RULE P09.f. unplaced_allowance_wh is the sum of the
unplaced allowances of RULE P09.l. reefers_refused counts the reefers
a rung caught and reefers_queued the reefers the queue carries.
spill_count counts every removal spill_decisions.tsv carries, spilled
and unspilled together, and unspilled_count the unspilled ones.

## `substation_report_<one substation identifier>.json`

One report per substation the reporting roster publishes, named for
that substation. Keys in this order: day_id, substation_id,
feeder_count, feeders, ceiling_w, peak_w, peak_interval, band_code,
demand_charge_cents, served_energy_wh. feeders is the list of feeder
identifiers of that substation in ascending order.

## `publication_manifest.json`

Keys in this order: day_id, day_reference, document_count,
core_digest, publication_digest, documents. document_count is the
number of entries documents carries. Each entry of documents
carries name, bytes and sha256 in that order.

## `final_schedule_by_vessel.xml`

A dispatch element carrying the day and reference attributes, then
one vessel element per vessel holding at least one queued reefer, in
vessel identifier order, carrying the id, cutoff and members
attributes, then one reefer element per member in reefer identifier
order carrying id, required_wh, served_wh, shortfall_wh and
allowance_wh.

## `dispatch_control_totals.conf`

One comment line made of `# control totals for`, one space and the
operating day identifier, then one key and value
per line separated by a space, an equals sign and a space, in this
order: day_id, day_reference, live_sheet, reefers_normalised,
reefers_queued, reefers_refused, spill_count, hard_violations,
unmet_mandatory_wh, deadline_penalty_cents, peak_demand_w,
energy_cost_cents, battery_cycle_wh, unmet_share_of_mandatory.
live_sheet is the name of the governing workbook sheet. The keys
shared with constraint_certificate.json and objective_vector.json
carry the same values. unmet_share_of_mandatory is
unmet_mandatory_wh divided by the sum of the required energy RULE
P11.a gives every queued reefer, written as a ratio, and zero when
that sum is zero.

## `daily_dispatch_summary.md`

The free text summary. worked_examples.md fixes its shape.
