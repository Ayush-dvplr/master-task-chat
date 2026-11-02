# Output contract

All reports are UTF-8 text with LF line endings and a final newline. Delimited reports (csv comma, tsv tab, psv
pipe) start with the header line given here, quote a cell only when the delimiter forces it, and leave a missing
value empty. JSON reports are one document; JSON Lines reports carry one object per line with keys in sorted order.
Integers are written without a decimal point. Run order is the order of the profile's runs list; stage order is
ST300, ST50, ST4; links sort by their final id; serials, tokens and other text sort by plain code-point order.
An aborted run has no rows in sensor_means.tsv, stage_temperatures.csv, intercept_solutions.json,
link_heat_flows.psv, junction_profiles.jsonl, link_geometry.csv, joint_conductances.tsv, stage_loads.csv,
cooler_margins.xml, reading_exclusions.jsonl or the runs of parameters_used.yaml. It keeps a row wherever a report
is laid out per profile run or per published or quoted item: run_verdicts.json and budget_summary.md (verdict
ABORTED), variance_vs_published.csv (its published links), reconciliation.md (its published stages) and
authority_audit.csv (every value a lower-authority source quotes for it).
Spaces around a markdown table cell or around a YAML value carry no meaning; the order, text, keys and nesting of
those lines do.

## sensor_means.tsv
- header: run	serial	stage	window_readings	spikes_dropped	used_readings	mean_mK	status
- one row per (run, final serial) with at least one deduplicated reading of the run that resolved to an inventory
  serial whose stage for the run is a measured stage; sorted by run, stage, serial.
- window_readings: readings that passed every screen of H10.1; spikes_dropped: SPIKE readings of H11;
  used_readings = window_readings - spikes_dropped.
- mean_mK: the sensor mean (H11), empty unless status is OK. status: OK, SPARSE or NO_READINGS.

## stage_temperatures.csv
- header: run,stage,sensors_used,sensors_dropped,temperature_mK,status
- one row per run and measured stage, sorted by run then stage order.
- sensors_used: serials whose means formed the temperature, sorted and joined with ;. sensors_dropped: outliers of
  H12, sorted and joined with ;. temperature_mK empty when status is NO_SENSORS; status OK or NO_SENSORS.

## intercept_solutions.json
- {"count": n, "intercepts": [...]} with one object per intercept of a run, sorted by run then node, keys:
  run, node, band, t_lo_mK, t_hi_mK, temperature_mK, harness_uW, residual_uW (f at the temperature),
  next_residual_uW (f one mK warmer, null when the temperature is t_hi_mK), links_in, links_out (final link ids,
  sorted), status (BALANCED, CEILING, FLOOR or UNSOLVED; an UNSOLVED intercept has null temperatures and residuals).

## link_heat_flows.psv
- header: run|link|rev|hot_node|cold_node|hot_mK|cold_mK|q_uW|status
- one row per installed link of a run, sorted by run then link. rev is the revision in use (empty when none).
  q_uW is empty unless status is OK or NO_GRADIENT. status: OK, NO_GRADIENT, UNSOLVED, NO_GEOMETRY or EXCLUDED.

## junction_profiles.jsonl
- one object per link row with status OK or NO_GRADIENT, sorted by run then link, keys: run, link, q_uW,
  elements. elements lists the march elements in order (H19.1); a joint element has kind joint, pos and t_mK; a
  segment element has kind segment, seq and t_mK; t_mK is the temperature after the element.

## link_geometry.csv
- header: run,link,rev,seq,material,length_mm,area_mm2,lot,lot_scale,g_mm
- one row per segment of each link row whose status is OK, NO_GRADIENT or UNSOLVED, sorted by run, link, seq.
- material is the material code; length_mm and area_mm2 are exact decimals with trailing zeros removed; lot is
  empty when none; lot_scale is the applied scale with trailing zeros removed (1 when none applies); g_mm is
  area/length rounded half-even to 9 places.

## joint_conductances.tsv
- header: run	link	pos	class	band	bolts	torque	indium	h_base_mW_per_K	h_eff_mW_per_K
- one row per joint of the same link rows as link_geometry.csv, sorted by run, link, pos. torque NOM or LOW;
  indium Y or N; both conductances with trailing zeros removed.

## stage_loads.csv
- header: run,stage,links_uW,harness_uW,parasitic_uW,total_uW,status
- one row per run for ST50 and ST4. status INCOMPLETE when a link loading the stage is UNSOLVED (links_uW and
  total_uW are then empty), OK otherwise.

## cooler_margins.xml
- root element margins with attribute campaign; one stage element per row of stage_loads.csv in the same order,
  with attributes in this order: run, name, cooler, model, temperature_mK, derate_pct, capacity_uW, map_status,
  load_uW, reserve_pct, reserve_uW, margin_uW, verdict. derate_pct has trailing zeros removed. Values that cannot be
  computed are empty strings and the verdict is INCOMPLETE. Two-space indentation, one element per line, an XML
  declaration with version 1.0 and encoding UTF-8.

## run_verdicts.json
- {"campaign": c, "runs": [...], "summary": {verdict: count}} with one object per profile run in run order, keys run,
  verdict, ST50, ST4 (stage verdicts, null for aborted runs) and unsolved_links (count). summary counts the run
  verdicts, keys sorted.

## alias_resolution.csv
- header: kind,token,resolved
- one row per distinct trimmed token of kind material (segment files), node (installs, sensor map, intercept register
  bundles), link (link files and installs) and sensor (serial tokens of the reading shards, after H6.1), sorted by
  kind then token. resolved is the canonical value after the alias walk, or UNRESOLVED.

## reading_exclusions.jsonl
- one object per (run, serial, reason) with a non-zero count, keys count, reason, run, serial; serial is the final
  serial, the canonical channel id for UNMAPPED_CHANNEL, or the canonical token for UNKNOWN_SENSOR. Sorted by run,
  serial, reason. Reasons: UNMAPPED_CHANNEL, UNKNOWN_SENSOR, INVALID_VALUE, OUT_OF_WINDOW, MAINTENANCE,
  EXCLUDED_SENSOR, NO_CALIBRATION, OUT_OF_RANGE, SPIKE.

## dedup_report.json
- keys: records_read (records in the catalogued reading shards), unresolved, copies_superseded (resolved records
  that lost to another copy of their key), voided_keys (keys removed because the winner is void), unique_readings
  (keys left), out_of_scope_readings (unique readings of runs that are not in scope or are aborted, or whose run
  token names another campaign).

## source_lineage.json
- {"shards": [...]} in catalog order, one object per read reading shard with keys file, layout, records, resolved
  and winning (records whose copy won and was not void).

## amendment_ledger.csv
- header: seq,link,rev,field,action,status,in_effect
- one row per amendment entry, sorted by seq. link is the final id; action and status upper-cased; in_effect Y or N.

## parameters_used.yaml
- keys in this order, two-space indentation, strings in single quotes only where written so below:
  campaign, profile_revision, overlay_applied (true or false), sheets (conductivity, calibration, capacity),
  memo_tables (joint, parasitic, solver, gauge, limits: the table labels applied), constants
  (h_increment_mW_per_K, indium_factor, low_torque_factor, lot_scale_materials: quoted strings as printed in the
  memo), limits_mK (ST50, ST4), runs (a mapping keyed by run id, one entry per non-aborted run in run order, each
  holding spike_mK, outlier_mK, min_readings, reserve_pct_ST50, reserve_pct_ST4, shield, cooler and derate_pct as a
  quoted string).
- layout, shown with made-up values (one run only):

```yaml
campaign: DEMO-01
profile_revision: 3
overlay_applied: false
sheets:
  conductivity: SHEET_K
  calibration: SHEET_C
  capacity: SHEET_P
memo_tables:
  joint: X-1
  parasitic: X-2
  solver: X-3
  gauge: X-4
  limits: X-5
constants:
  h_increment_mW_per_K: '0.5'
  indium_factor: '1.10'
  low_torque_factor: '0.90'
  lot_scale_materials: 'MAT_A MAT_B'
limits_mK:
  ST50: 70000
  ST4: 5000
runs:
  DEMO-R01:
    spike_mK: 20
    outlier_mK: 80
    min_readings: 5
    reserve_pct_ST50: 10
    reserve_pct_ST4: 10
    shield: SC-X
    cooler: CC-0000
    derate_pct: '2.5'
```

## authority_audit.csv
- header: source,item,quoted,in_force,verdict
- one row per audited value (H24), sorted by source then item. Items: conductivity_cache.jsonl, quick_reference
  and materials_legacy rows use MATERIAL@T_K (material code, T_K as quoted); daq_dashboard_export.csv uses RUN/STAGE;
  bulletin, draft handbook and solve pack constants use their key as printed (JOINT class/band, AWG gauge,
  PARASITIC config/stage, FACTOR name); profile_overlay_lab.yaml uses RUN/key. in_force is written in the quoted
  value's unit and number of places; verdict AGREE or DISAGREE. A dashboard row of a run whose stage has no
  temperature (an aborted run included) has an empty in_force and verdict DISAGREE. A profile_overlay_lab.yaml row
  is audited for every key that is a per-run setting of H13 (spike_mK, outlier_mK, min_readings, reserve_pct_ST50,
  reserve_pct_ST4), aborted runs included, against the run's effective setting; other keys are not audited.

## variance_vs_published.csv
- header: run,link,published_uW,recomputed_uW,delta_uW,status
- one row per (run, final link id) present in the published budget or in link_heat_flows.psv with a q, sorted by run
  then link. delta_uW = recomputed - published. status MATCH, DIFFERENT, MISSING_PUBLISHED or MISSING_RECOMPUTED.

## reconciliation.md
- line 1: # Reconciliation with the published stage margins
- then a blank line, the table header | run | stage | published_verdict | recomputed_verdict | change |, the line
  |---|---|---|---|---|, and one row per published (run, stage) in run and stage order; recomputed_verdict is the
  stage verdict of cooler_margins.xml, or ABORTED for every stage of an aborted run; change is same when the two
  verdicts are equal and changed otherwise. Rows are written | KTC-R01 | ST50 | PASS | MARGINAL | changed |.
- then a blank line and the line: Changed verdicts: N of M.

## budget_summary.md
- line 1: # Heat-load budget summary
- then a blank line, | run | verdict | ST50_load_uW | ST50_margin_uW | ST4_load_uW | ST4_margin_uW |, the line
  |---|---|---|---|---|---|, one row per profile run in run order, written like the header with an empty cell where
  nothing was computed (an aborted run reads | KTC-R07 | ABORTED |  |  |  |  |), a blank line and the line:
  Runs passing: N of M, where M counts every profile run.

## manifest.json
- {"files": [...]} with one object per other report in the order of this contract, keys name, bytes, sha256.

## Column dictionary

| report | position | column |
|---|---|---|
| sensor_means.tsv | 1 | run |
| sensor_means.tsv | 2 | serial |
| sensor_means.tsv | 3 | stage |
| sensor_means.tsv | 4 | window_readings |
| sensor_means.tsv | 5 | spikes_dropped |
| sensor_means.tsv | 6 | used_readings |
| sensor_means.tsv | 7 | mean_mK |
| sensor_means.tsv | 8 | status |
| stage_temperatures.csv | 1 | run |
| stage_temperatures.csv | 2 | stage |
| stage_temperatures.csv | 3 | sensors_used |
| stage_temperatures.csv | 4 | sensors_dropped |
| stage_temperatures.csv | 5 | temperature_mK |
| stage_temperatures.csv | 6 | status |
| intercept_solutions.json | key 1 | count |
| intercept_solutions.json | key 2 | intercepts |
| intercept_solutions.json | key 3 | run |
| intercept_solutions.json | key 4 | node |
| intercept_solutions.json | key 5 | band |
| intercept_solutions.json | key 6 | t_lo_mK |
| intercept_solutions.json | key 7 | t_hi_mK |
| intercept_solutions.json | key 8 | temperature_mK |
| intercept_solutions.json | key 9 | harness_uW |
| intercept_solutions.json | key 10 | residual_uW |
| intercept_solutions.json | key 11 | next_residual_uW |
| intercept_solutions.json | key 12 | links_in |
| intercept_solutions.json | key 13 | links_out |
| intercept_solutions.json | key 14 | status |
| link_heat_flows.psv | 1 | run |
| link_heat_flows.psv | 2 | link |
| link_heat_flows.psv | 3 | rev |
| link_heat_flows.psv | 4 | hot_node |
| link_heat_flows.psv | 5 | cold_node |
| link_heat_flows.psv | 6 | hot_mK |
| link_heat_flows.psv | 7 | cold_mK |
| link_heat_flows.psv | 8 | q_uW |
| link_heat_flows.psv | 9 | status |
| junction_profiles.jsonl | key 1 | elements |
| junction_profiles.jsonl | key 2 | link |
| junction_profiles.jsonl | key 3 | q_uW |
| junction_profiles.jsonl | key 4 | run |
| junction_profiles.jsonl | key 5 | kind |
| junction_profiles.jsonl | key 6 | pos |
| junction_profiles.jsonl | key 7 | seq |
| junction_profiles.jsonl | key 8 | t_mK |
| link_geometry.csv | 1 | run |
| link_geometry.csv | 2 | link |
| link_geometry.csv | 3 | rev |
| link_geometry.csv | 4 | seq |
| link_geometry.csv | 5 | material |
| link_geometry.csv | 6 | length_mm |
| link_geometry.csv | 7 | area_mm2 |
| link_geometry.csv | 8 | lot |
| link_geometry.csv | 9 | lot_scale |
| link_geometry.csv | 10 | g_mm |
| joint_conductances.tsv | 1 | run |
| joint_conductances.tsv | 2 | link |
| joint_conductances.tsv | 3 | pos |
| joint_conductances.tsv | 4 | class |
| joint_conductances.tsv | 5 | band |
| joint_conductances.tsv | 6 | bolts |
| joint_conductances.tsv | 7 | torque |
| joint_conductances.tsv | 8 | indium |
| joint_conductances.tsv | 9 | h_base_mW_per_K |
| joint_conductances.tsv | 10 | h_eff_mW_per_K |
| stage_loads.csv | 1 | run |
| stage_loads.csv | 2 | stage |
| stage_loads.csv | 3 | links_uW |
| stage_loads.csv | 4 | harness_uW |
| stage_loads.csv | 5 | parasitic_uW |
| stage_loads.csv | 6 | total_uW |
| stage_loads.csv | 7 | status |
| cooler_margins.xml | key 1 | run |
| cooler_margins.xml | key 2 | name |
| cooler_margins.xml | key 3 | cooler |
| cooler_margins.xml | key 4 | model |
| cooler_margins.xml | key 5 | temperature_mK |
| cooler_margins.xml | key 6 | derate_pct |
| cooler_margins.xml | key 7 | capacity_uW |
| cooler_margins.xml | key 8 | map_status |
| cooler_margins.xml | key 9 | load_uW |
| cooler_margins.xml | key 10 | reserve_pct |
| cooler_margins.xml | key 11 | reserve_uW |
| cooler_margins.xml | key 12 | margin_uW |
| cooler_margins.xml | key 13 | verdict |
| run_verdicts.json | key 1 | campaign |
| run_verdicts.json | key 2 | runs |
| run_verdicts.json | key 3 | summary |
| run_verdicts.json | key 4 | run |
| run_verdicts.json | key 5 | verdict |
| run_verdicts.json | key 6 | ST50 |
| run_verdicts.json | key 7 | ST4 |
| run_verdicts.json | key 8 | unsolved_links |
| alias_resolution.csv | 1 | kind |
| alias_resolution.csv | 2 | token |
| alias_resolution.csv | 3 | resolved |
| reading_exclusions.jsonl | key 1 | count |
| reading_exclusions.jsonl | key 2 | reason |
| reading_exclusions.jsonl | key 3 | run |
| reading_exclusions.jsonl | key 4 | serial |
| dedup_report.json | key 1 | records_read |
| dedup_report.json | key 2 | unresolved |
| dedup_report.json | key 3 | copies_superseded |
| dedup_report.json | key 4 | voided_keys |
| dedup_report.json | key 5 | unique_readings |
| dedup_report.json | key 6 | out_of_scope_readings |
| source_lineage.json | key 1 | shards |
| source_lineage.json | key 2 | file |
| source_lineage.json | key 3 | layout |
| source_lineage.json | key 4 | records |
| source_lineage.json | key 5 | resolved |
| source_lineage.json | key 6 | winning |
| amendment_ledger.csv | 1 | seq |
| amendment_ledger.csv | 2 | link |
| amendment_ledger.csv | 3 | rev |
| amendment_ledger.csv | 4 | field |
| amendment_ledger.csv | 5 | action |
| amendment_ledger.csv | 6 | status |
| amendment_ledger.csv | 7 | in_effect |
| parameters_used.yaml | key 1 | campaign |
| parameters_used.yaml | key 2 | profile_revision |
| parameters_used.yaml | key 3 | overlay_applied |
| parameters_used.yaml | key 4 | sheets |
| parameters_used.yaml | key 5 | memo_tables |
| parameters_used.yaml | key 6 | constants |
| parameters_used.yaml | key 7 | limits_mK |
| parameters_used.yaml | key 8 | runs |
| authority_audit.csv | 1 | source |
| authority_audit.csv | 2 | item |
| authority_audit.csv | 3 | quoted |
| authority_audit.csv | 4 | in_force |
| authority_audit.csv | 5 | verdict |
| variance_vs_published.csv | 1 | run |
| variance_vs_published.csv | 2 | link |
| variance_vs_published.csv | 3 | published_uW |
| variance_vs_published.csv | 4 | recomputed_uW |
| variance_vs_published.csv | 5 | delta_uW |
| variance_vs_published.csv | 6 | status |
| reconciliation.md | key 1 | run |
| reconciliation.md | key 2 | stage |
| reconciliation.md | key 3 | published_verdict |
| reconciliation.md | key 4 | recomputed_verdict |
| reconciliation.md | key 5 | change |
| budget_summary.md | key 1 | run |
| budget_summary.md | key 2 | verdict |
| budget_summary.md | key 3 | ST50_load_uW |
| budget_summary.md | key 4 | ST50_margin_uW |
| budget_summary.md | key 5 | ST4_load_uW |
| budget_summary.md | key 6 | ST4_margin_uW |
| manifest.json | key 1 | files |
| manifest.json | key 2 | name |
| manifest.json | key 3 | bytes |
| manifest.json | key 4 | sha256 |
