# Output artifact contract

Twenty eight files are published under the output directory. Twenty seven are
derived documents and the twenty eighth is the program that derives them.

| artifact | family | stage |
| --- | --- | --- |
| reading_ledger.csv | core | T01 T02 T03 |
| withdrawal_ledger.tsv | graph | T01 |
| calibration_selection.csv | graph | T02 |
| link_differences.psv | core | T03 |
| link_graph.json | graph | T04 |
| epoch_grid.csv | graph | T01 T10 |
| deadtime_ledger.jsonl | graph | T05 T06 |
| oscillator_series.csv | core | T06 |
| prediction_book.json | weight | T07 |
| dispersion_table.csv | weight | T08 |
| weight_book.json | core | T09 |
| weight_sweep_trace.jsonl | weight | T09 |
| ensemble_scale.csv | core | T10 |
| steering_plan.json | weight | T11 |
| steered_scale.csv | core | T11 |
| node_offsets.csv | publish | T12 |
| uncertainty_budget.tsv | publish | T12 |
| dissemination_ledger.psv | publish | T12 |
| node_report_nd_arden.json | publish | T13 |
| node_report_nd_calder.json | publish | T13 |
| node_report_nd_jarrow.json | publish | T13 |
| node_report_nd_lyddon.json | publish | T13 |
| network_reconciliation.xml | publish | T13 |
| timescale_report.md | publish | T13 |
| ensemble_summary.md | publish | T13 |
| publication_manifest.json | publish | T13 |
| node_index.conf | publish | T13 |

The core family is the family the core digest runs over, in the order
ordering_dependencies.yaml gives. The publication digest in the manifest runs
over every artifact in this table except the manifest, in the order this table
lists them, so the manifest moves when any document in the publication
moves.

Every artifact is a function of this directory alone. Nothing is read from
outside it and nothing carries a timestamp, a host name or a path.
