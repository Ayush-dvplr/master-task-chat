# Data lineage

Which paper feeds which stage.

| paper | stages | note |
| --- | --- | --- |
| comparison_session_log.csv | T01 | every acquisition attempt of the interval |
| session_withdrawal_journal.tsv | T01 | withdrawn acquisition sessions |
| epoch_grid_policy.yaml | T01 | grid instant and attribution tolerance |
| link_register.csv | T01 T03 T04 T12 | frozen link register |
| link_technique_reference.txt | T03 T04 | measurement sense and technique rank |
| delay_calibration_ledger.csv | T02 | delay reports |
| delay_calibration_supplement.psv | T02 | further reports of the same register |
| network_config.json | T01 T04 T06 | interval header, hub, frozen revision, workbook key |
| node_register_frozen.csv | T04 T06 T12 | node register, several revisions |
| oscillator_catalogue.csv | T06 T07 | the oscillator population |
| local_comparison_log.psv | T06 | oscillator against its node reference |
| prior_interval_deviations.psv | T07 T08 | the previous interval archive |
| weighting_policy.yaml | T07 T08 | window, valid flag, weight scale |
| network_calibration_memo.pdf | T07 T09 | history minimum, oscillator cap, sweep budget |
| timing_network_workbook.xlsx | T08 T09 T12 | class ceilings, node cap, uncertainty components |
| capping_policy.yaml | T09 | pass order and redistribution |
| steering_policy.yaml | T11 | decision epoch, horizon, grid |
| primary_standard_realisation.csv | T11 | the realisation to steer onto |
| uncertainty_budget_policy.yaml | T12 | budget terms and statistics |
| rounding_policy.yaml | all | rounding mode and places |
| ordering_dependencies.yaml | T13 | what freezes where, and the digest order |
| dissemination_targets.json | none | service labels of the sites, kept for audit |
| network_topology.xml | none | a view of the register, kept for audit |
| reference_store.sqlite | none | a copy of two registers, kept for audit |
| network_audit.db | none | a copy of the session log, kept for audit |
| maintenance_window_log.ndjson | none | site activity, kept for audit |

## Superseded papers

Three papers in this directory are superseded and take no part in the
recompute. They are kept because the audit trail needs them.

  * node_register_current.csv holds the latest register revision only. The
    interval works at the revision network_config.json freezes, which is an
    earlier one, and the two disagree about the reference oscillator of two
    nodes and about the declared uncertainty of every node. Use the frozen
    register.

  * legacy_weight_table.csv holds a fixed weight per oscillator class from a
    scheme the network retired at REG-R09. Weights come from the residual
    dispersion of the previous interval, never from this table.

  * topology_drafts.xml holds a proposed rerouting that was never
    commissioned. The graph is built from link_register.csv.

The draft sheet of the workbook is superseded in the same way. The live sheet
is the one whose key cell matches the workbook sheet key in
network_config.json, and it is not selected by its name or by its position.
