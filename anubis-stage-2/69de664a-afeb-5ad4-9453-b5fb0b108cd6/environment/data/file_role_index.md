# File role index

- observation stream: arr_run_ledger_delta.jsonl, obs_capture_index.csv (authoritative raw_counts), frame_intake_stream.ndjson, capture_alt_view.csv
- full well capacity (authoritative): full_well_capacity.tsv ONLY
- exposure weight (authoritative): exposure_weight_micro.tsv ONLY
- dark current: pedestal_authoritative.csv (authoritative), baseline_pedestal_grid.tsv
- nonlinearity: response_curve_horner.yaml, instrument_capability_matrix.xml
- gain values: quantum_yield_micro.json, yield_channel_values.psv
- gain fold: channel_lineage_fold.psv, yield_binding_trace.jsonl
- SCALE FACTOR (authoritative): gain_scale_workbook.xlsx ONLY
- drift: thermal_drift_ppm.yml, drift_ppm_matrix.tsv
- disputed (authoritative): adjudication_dossier.pdf ONLY
- dead-pixel relay: occlusion_relay_graph.xml, relay_edges.jsonl, relay_closure_rule.json
- integration time and shutter state (authoritative): exposure_ledger.csv ONLY
- legacy faulty output (do not trust): legacy_pipeline_output.json
