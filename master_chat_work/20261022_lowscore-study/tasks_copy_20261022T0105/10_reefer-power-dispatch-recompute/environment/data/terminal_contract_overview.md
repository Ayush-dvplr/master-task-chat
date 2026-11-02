# Terminal contract overview

Operating day AP-2044-D111, day reference DSP-067712.

The recomputation is worked in fourteen stages, in the order below.
Each stage reads the papers its own specification names, stores the
whole numbers that specification tells it to store, and hands those
stored numbers to the stage after it. No stage reaches back into a
quantity an earlier stage rounded away.

Stage p01, unit normalisation. Specification `spec_stage_p01_unit_normalisation.md`.

Stage p02, availability lattice. Specification `spec_stage_p02_availability_lattice.md`.

Stage p03, mandatory energy floor. Specification `spec_stage_p03_energy_floor.md`.

Stage p04, dispatch priority queue. Specification `spec_stage_p04_priority_queue.md`.

Stage p05, provisional allocation. Specification `spec_stage_p05_provisional_allocation.md`.

Stage p06, feeder reconciliation. Specification `spec_stage_p06_feeder_reconciliation.md`.

Stage p07, crane adjusted capacity. Specification `spec_stage_p07_crane_interaction.md`.

Stage p08, battery intervention. Specification `spec_stage_p08_battery_intervention.md`.

Stage p09, load reconciliation passes. Specification `spec_stage_p09_load_reconciliation.md`.

Stage p10, tariff and demand charge. Specification `spec_stage_p10_tariff_and_demand.md`.

Stage p11, deadline correction. Specification `spec_stage_p11_deadline_correction.md`.

Stage p12, cycle detection and break. Specification `spec_stage_p12_cycle_break.md`.

Stage p13, objective reconciliation. Specification `spec_stage_p13_objective.md`.

Stage p14, publication. Specification `spec_stage_p14_publication.md`.

The arithmetic policy in rounding_and_arithmetic_policy.yaml and the
boundary conventions in boundary_conventions.yaml apply to every
stage. The publication form rules and the serialisation contract
apply to every published document.

Three control papers are read once and used throughout. The
substation capacity workbook carries the reconciliation damping
fraction, the maintenance coefficients, the base service charge, the
vessel share ceilings and the substation ceilings. The dispatch
operations memorandum carries the pass budget, the minimum step, the
dependency protection depth, the deadline surcharge ladder and the
crane gang roster. The priority ordering directive carries the four
ordering keys in their key positions and the class rank of every
temperature class.
