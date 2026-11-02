# Glossary and reading order

This corpus describes one mixture of experts training run that regressed. Read
this file first, then the contracts it names.

- assignment: one pair of a token and an expert chosen for it. With top k
  dispatch each token produces `top_k` assignments.
- demand: for an expert, the number of assignments naming it in a step, counted
  before any capacity limit is applied.
- capacity: the padded slot count reserved for one expert in one step. It is the
  second dimension of the dispatch tensor and therefore part of a guard key.
- rank bucket: the slot count a single expert parallel rank must allocate. Every
  expert living on that rank is padded to it.
- all to all bucket: the slot count every rank exchanges. The collective forces
  one figure across the whole mesh.
- guard key: the tuple TorchDynamo compares to decide whether a compiled entry
  can be reused.
- recompile: a compilation triggered because no cached entry matched the guard
  key.
- promotion: the moment a dimension stops being specialised and starts being
  treated as dynamic.
- capture: recording a compiled region into a graph replay pool.
- warmup window: the leading steps excluded from the throughput and recompile
  gates.

Reading order that matches the pipeline:
`stream_contract.md`, `routing_contract.md`, `capacity_contract.md`,
`mesh_contract.md`, `alltoall_contract.md`, `guard_semantics.md`,
`recompile_policy.md`, `cudagraph_policy.md`, `host_memory_model.md`,
`steptime_model.md`, `numeric_contract.md`, `aux_loss_contract.md`,
`optimizer_contract.md`, `warmup_contract.md`, `settlement_procedure.md`,
`precedence_constraints.md`, `sealed_policy_notes.md`, `audit_definitions.md`,
`enumeration_order.md`, `output_schema.md`.

Background material: `incident_report.md`, `fault_report.md`,
`compile_flags.md`, `fp8_format_notes.md`, `worked_step.md`,
`unreachable_branches.md`, `revision_history.md`, `legacy_planner_notes.md`.

Two rules used by this pipeline are deliberately absent from the prose. See
`sealed_policy_notes.md` for the sealed evidence that pins them down.
