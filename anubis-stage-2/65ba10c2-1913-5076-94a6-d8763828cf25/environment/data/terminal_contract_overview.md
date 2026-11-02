TERMINAL CONTRACT OVERVIEW
shift KP-2042-S23

One shift is recomputed in fourteen stages, worked in the order
below. Each stage reads the state the stages before it left and
publishes the documents named in its specification.

  Y01  Canonical event set           spec_stage_y01_canonical_events.md
  Y02  Unit normalisation            spec_stage_y02_unit_normalisation.md
  Y03  Vessel obligation state       spec_stage_y03_vessel_obligation.md
  Y04  The opening yard              spec_stage_y04_opening_yard.md
  Y05  Canonical event order         spec_stage_y05_event_ordering.md
  Y06  Move dependencies and their cycles  spec_stage_y06_dependency_cycles.md
  Y07  Move admission                spec_stage_y07_move_admission.md
  Y08  Yard state through the shift  spec_stage_y08_yard_state.md
  Y09  Planned against physical      spec_stage_y09_movement_reconciliation.md
  Y10  Rehandles and equipment       spec_stage_y10_rehandle_and_equipment.md
  Y11  Block capacity state          spec_stage_y11_block_capacity.md
  Y12  Cutoff joined to yard state   spec_stage_y12_load_eligibility.md
  Y13  The quay ration and the load  spec_stage_y13_quay_ration.md
  Y14  Terminal accounts and publication  spec_stage_y14_terminal_accounts.md

The cross cutting papers are rounding_and_arithmetic_policy.yaml,
revision_precedence.toml, boundary_conventions.yaml,
reserved_capacity_policy.toml, equipment_allowance_policy.toml,
quay_ration_policy.toml, unit_register_dictionary.toml,
publication_form_rules.toml and berth_reporting_roster.conf. A stage
specification that names one of them is governed by it.

The publication is described by output_schema_reference.md and
serialisation_and_digest_contract.md. The program is described by
yardledger_program_contract.md.

Two stages take evidence from two sources at once. Stage Y09 sets
the planned move stream against the physical confirmation stream.
Stage Y12 joins the yard state this shift produced to the cutoff
notices, which come from the vessel side and know nothing about the
yard.

Stage Y13 is the only stage of the shift that is not a lookup.
