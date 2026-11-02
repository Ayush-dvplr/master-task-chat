# TRUTH.md - 67e0b296-174a-493f-a795-4f0283301f5c

## Defect

The retired power-cap compile read every source at face value. It treated VA as watts, ignored the
continuous-load and derate factors on circuits, took DC readings from the BMCs as AC, trusted the
re-exported, replayed, backfilled, draft, rescanned, preliminary and previous-snapshot files, and applied
amendments that arrived after the freeze. Its figures survive as notes starting `legacy compile:` in about
one line in seven. The agent must write `/app/out/build.py`, a three-stage compiler that reads the 50 sources
under `/app/data/power_standard.md`, and the stage files it produces.

1. (focal) Reading resolution. Every reading must go through the documented pipeline: number format
   (decimal comma, grouping, exponent), unit factor (W, kW, mW, VA, kVA, BTU/h, spellings, unit written inside
   the value), export profile scale, model power factor for VA, outlet calibration for PDU readings, PSU
   efficiency for DC readings, errata, then PDU over BMC over agent for the same host and time, a missing
   value taking no part in that choice. Defeats
   `demand_mean`, `demand_p95`, `demand_peak`, `demand_energy`, `eval_demand_mean` and
   `eval_demand_energy`.
2. (focal) Identity and time. Hosts appear as canonical ids, upper case, `.pwr.corp` names, serial numbers,
   asset tags and time-windowed aliases (one alias in each fleet is chained through an asset tag and names
   in-window readings); times appear in eight forms,
   including offset-less local time that needs the host's site and that site's summer-time rule, and
   spreadsheet serials. Defeats `demand_samples`, `hosts_policy` (policy records keyed by asset tag),
   `source_digests_in_force`.
3. (focal) In-force and effective records. Files whose names mark them as superseded or unapproved are out of
   force except for records an RT names; voids remove records; revision numbers, never file order or time,
   pick the effective inventory, circuit, model, PSU, policy, site and tenant record; a revision tie goes to the
   later time (policy records) and a revision-and-time tie to the greater id (one inventory record per fleet,
   written lower id last so line order gives the wrong tenant). Defeats `hosts_identity`, `hosts_hardware`,
   `hosts_policy`, `circuits_ratings`, `registry_sites`, `registry_tenants`, `eval_hosts`.
4. (focal) The cascade. Phase 2 must fold over hosts.csv in written order with cumulative caps per rack and per
   site pool, and phase 3 must apply the carried amendments in order and bind every output to the bytes of
   its twelve upstream files. Defeats `host_alloc_alloc`, `tenant_pool_grants`, `bmc_caps_values`,
   `release_applied`, `negative_unbound_phase_digests`.
5. (drift) Working from raw sources in later stages. Recomputing phase-2 or phase-3 figures from the sources
   at full precision gives different digits from the one-decimal phase-1 tables (double rounding at p95,
   mean, energy, kWh and PUE boundaries). Defeats `rack_budget_load`, `site_energy_cost`, `bmc_caps_context`.
6. (drift) Rounding habits. Half-up rounding, or rounding usable watts and thresholds instead of truncating,
   moves single digits across hundreds of rows. Defeats `circuits_usable`, `circuit_alarms_thresholds`.
7. (trap) The legacy notes and the FINAL re-export look authoritative and agree with each other; the
   standard says neither is. Defeats `demand_mean`, `hosts_nameplate`.
8. (trap) Asset register snapshot records carry higher revision numbers than the live register; only the
   ratified ones count. Defeats `hosts_hardware`.
9. (trap) Null readings versus zero readings: a missing value is not a sample, a zero is. Defeats
   `demand_samples`, `site_energy_it`.
10. (trap) Post-cut amendments must be carried in phase 1 and phase 2 and applied only in phase 3. Defeats
    `amendments_carried`, `bmc_caps_values`.
11. (trap) Every other post-cut record is ignored, registers included. The unseen fleet carries one void, one
    erratum, one ratification and one export profile timed after the freeze, each naming an in-window reading
    or batch of an in-scope host; applying any of them moves that host's demand, and applying the void also
    moves a source's void count. Defeats `eval_demand_samples`, `eval_demand_mean`,
    `eval_demand_energy` and `eval_registry`.

Out of bounds: editing the sources, reading anything outside the directories named on the command line,
fetching anything from the network.

### Source files

| file | format | records | in scope | distinct rules |
|---|---|---|---|---|
| pdu_hall_a.csv | csv | 10146 | yes | 86 |
| pdu_hall_b.tsv | tsv | 10323 | yes | 86 |
| pdu_hall_c.csv | csv | 10364 | yes | 85 |
| rack_meter_dump.xml | xml | 10155 | yes | 87 |
| outlet_trend.ini | ini | 10196 | yes | 85 |
| dcim_pull_q1.xlsx | xlsx | 10116 | yes | 88 |
| utility_reconcile.pdf | pdf | 10120 | yes | 84 |
| telemetry_lake_part0.parquet | parquet | 10114 | yes | 86 |
| bmc_sweep_north.jsonl | jsonl | 10038 | yes | 76 |
| bmc_sweep_south.json | json | 10232 | yes | 75 |
| bmc_sweep_east.jsonl | jsonl | 10140 | yes | 76 |
| noc_dashboard_snapshot.html | html | 10096 | yes | 74 |
| maint_windows.ics | ics | 10120 | yes | 74 |
| collector_cache.db | db | 10112 | yes | 77 |
| telemetry_lake_part1.parquet | parquet | 10167 | yes | 75 |
| site_survey_scan.docx | docx | 10120 | yes | 75 |
| agent_push_1.log | log | 10145 | yes | 68 |
| agent_push_2.txt | txt | 10073 | yes | 68 |
| agent_push_3.log | log | 10047 | yes | 68 |
| meter_export_wk12.yaml | yaml | 10151 | yes | 68 |
| meter_export_wk13.toml | toml | 10245 | yes | 67 |
| floor_walk_notes.md | md | 10095 | yes | 70 |
| noc_mailbox.mbox | mbox | 10182 | yes | 68 |
| dcim_pull_q1b.xlsx | xlsx | 10235 | yes | 69 |
| asset_register.xlsx | xlsx | 10123 | yes | 38 |
| cmdb_extract.csv | csv | 10082 | yes | 42 |
| host_moves.jsonl | jsonl | 10106 | yes | 42 |
| decom_tickets.mbox | mbox | 10056 | yes | 41 |
| circuit_schedule.tsv | tsv | 10094 | yes | 38 |
| breaker_survey.xml | xml | 10067 | yes | 37 |
| model_catalog.yaml | yaml | 10152 | yes | 39 |
| power_standard.md | md | 10544 | yes | 30 |
| placement_policy.toml | toml | 10115 | yes | 43 |
| tenant_contracts.docx | docx | 10033 | yes | 45 |
| alias_book.ini | ini | 10103 | yes | 26 |
| naming_history.html | html | 10095 | yes | 28 |
| void_journal.log | log | 10094 | yes | 32 |
| void_requests.ics | ics | 10047 | yes | 26 |
| errata_sheet.csv | csv | 10069 | yes | 40 |
| errata_followups.pdf | pdf | 10144 | yes | 26 |
| calibration_runs.parquet | parquet | 10067 | yes | 31 |
| change_board.db | db | 10091 | yes | 34 |
| pdu_hall_a_reexport_FINAL.csv | csv | 10141 | no | 72 |
| bmc_sweep_replay.jsonl | jsonl | 10051 | no | 68 |
| agent_backfill.log | log | 10022 | no | 54 |
| legacy_capcalc_run.db | db | 10023 | no | 59 |
| asset_register_prev.xlsx | xlsx | 10499 | no | 42 |
| power_standard_draft.html | html | 10537 | no | 31 |
| circuit_rescan.tsv | tsv | 10442 | no | 37 |
| psu_curves_vendor_prelim.parquet | parquet | 10537 | no | 31 |

## Load-bearing work

19 artifacts are declared:

- `/app/out/build.py`
- `/app/out/p1/hosts.csv`
- `/app/out/p1/circuits.csv`
- `/app/out/p1/demand.csv`
- `/app/out/p1/psu.csv`
- `/app/out/p1/registry.json`
- `/app/out/p1/amendments.csv`
- `/app/out/p2/rack_budget.csv`
- `/app/out/p2/host_alloc.csv`
- `/app/out/p2/site_energy.csv`
- `/app/out/p2/circuit_alarms.csv`
- `/app/out/p2/tenant_pool.csv`
- `/app/out/p2/fleet_summary.json`
- `/app/out/p3/bmc_caps.ini`
- `/app/out/p3/pdu_alarms.json`
- `/app/out/p3/chargeback.json`
- `/app/out/p3/exceptions.json`
- `/app/out/p3/capacity.json`
- `/app/out/p3/release.json`

Content contract: `/app/contract/output_contract.md` (every column, order, rounding and null form), with the
source rules in `/app/data/power_standard.md`. The 51 agent-visible input files are:

- `/app/data/agent_backfill.log`
- `/app/data/agent_push_1.log`
- `/app/data/agent_push_2.txt`
- `/app/data/agent_push_3.log`
- `/app/data/alias_book.ini`
- `/app/data/asset_register.xlsx`
- `/app/data/asset_register_prev.xlsx`
- `/app/data/bmc_sweep_east.jsonl`
- `/app/data/bmc_sweep_north.jsonl`
- `/app/data/bmc_sweep_replay.jsonl`
- `/app/data/bmc_sweep_south.json`
- `/app/data/breaker_survey.xml`
- `/app/data/calibration_runs.parquet`
- `/app/data/change_board.db`
- `/app/data/circuit_rescan.tsv`
- `/app/data/circuit_schedule.tsv`
- `/app/data/cmdb_extract.csv`
- `/app/data/collector_cache.db`
- `/app/data/dcim_pull_q1.xlsx`
- `/app/data/dcim_pull_q1b.xlsx`
- `/app/data/decom_tickets.mbox`
- `/app/data/errata_followups.pdf`
- `/app/data/errata_sheet.csv`
- `/app/data/floor_walk_notes.md`
- `/app/data/host_moves.jsonl`
- `/app/data/legacy_capcalc_run.db`
- `/app/data/maint_windows.ics`
- `/app/data/meter_export_wk12.yaml`
- `/app/data/meter_export_wk13.toml`
- `/app/data/model_catalog.yaml`
- `/app/data/naming_history.html`
- `/app/data/noc_dashboard_snapshot.html`
- `/app/data/noc_mailbox.mbox`
- `/app/data/outlet_trend.ini`
- `/app/data/pdu_hall_a.csv`
- `/app/data/pdu_hall_a_reexport_FINAL.csv`
- `/app/data/pdu_hall_b.tsv`
- `/app/data/pdu_hall_c.csv`
- `/app/data/placement_policy.toml`
- `/app/data/power_standard.md`
- `/app/data/power_standard_draft.html`
- `/app/data/psu_curves_vendor_prelim.parquet`
- `/app/data/rack_meter_dump.xml`
- `/app/data/site_survey_scan.docx`
- `/app/data/telemetry_lake_part0.parquet`
- `/app/data/telemetry_lake_part1.parquet`
- `/app/data/tenant_contracts.docx`
- `/app/data/utility_reconcile.pdf`
- `/app/data/void_journal.log`
- `/app/data/void_requests.ics`
- `/app/contract/output_contract.md`

### Cascade dependency matrix

Rows are downstream files, columns upstream files. A cell names the upstream fields the downstream file
reads; `L` means the upstream file is also bound through its lineage digest. Phase-2 rows read phase-1 files
only and phase-3 rows read all twelve, so 36 + 72 = 108 cells are filled; no file reads a sibling of its own
phase.

| downstream | p1 hosts | p1 circuits | p1 demand | p1 psu | p1 registry | p1 amendments | p2 rack_budget | p2 host_alloc | p2 site_energy | p2 circuit_alarms | p2 tenant_pool | p2 fleet_summary |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p2 rack_budget | rack_id, nameplate_w, psu_count, psu_model | usable_w, rack_id, feed | p95_w | rated_w | cap_step_w | target | | | | | | |
| p2 host_alloc | order, floor_w, nameplate_w, cap_ceiling_w | usable_w | samples, p95_w | rated_w | cap_step_w, margin_pm | target | | | | | | |
| p2 site_energy | site, psu_count, psu_model | usable_w | energy_wh, mean_w, peak_w, samples | rated_w, eff_bp | pue_milli, tariff_mc | target | | | | | | |
| p2 circuit_alarms | rack_id, psu_count, psu_model | breaker_a, voltage_v | mean_w, peak_w | rated_w | cont_pm, derate_pm, warn_pm, crit_pm | target | | | | | | |
| p2 tenant_pool | tenant, site, floor_w | usable_w | p95_w, samples | rated_w | tenants, pool_pm, margin_pm | target | | | | | | |
| p2 fleet_summary | L, site | L, usable_w | L, p95_w | L, rated_w | L, freeze_utc | L, target | | | | | | |
| p3 bmc_caps | L, floor_w, priority, cap_domain | L, breaker_a | L, samples | L, eff_bp | L, cap_step_w, correction_ms | L, field, value | L, headroom_w | L, alloc_w | L, it_kwh, facility_kwh | L, state | L, granted_w, cut_w | L, alloc_w |
| p3 pdu_alarms | L, psu_count | L, breaker_a, voltage_v | L | L | L, warn_pm, crit_pm | L, breaker_a | L | L, alloc_w | L | L, failover_a, warn_a | L | L |
| p3 chargeback | L, tenant, site | L | L, energy_wh | L | L | L | L | L | L, cost_cents | L | L | L |
| p3 exceptions | L | L | L, peak_w | L | L | L | L, headroom_w | L, overcommit | L | L, failover_a | L, cut_w | L |
| p3 capacity | L, rack_id | L | L | L | L, pool_pm | L | L, budget_w | L, alloc_w | L | L | L, granted_w | L |
| p3 release | L | L, breaker_a | L | L | L, freeze_utc | L, field, value | L | L | L | L | L | L |

## Verification

`tests/test.sh` clears stale reward files, locks the log directory and hands over to rewardkit, which scores
`tests/test_output.py` and `tests/judge.toml`; `tests/reward.toml` gives each channel half. The test channel
carries 66 positive and 8 negative tests: positive total 250, negative total
-34, so it ranges -34/250 = -0.136 to +1.000. Phase-1 checks compare the delivered tables
with the expected tables of the shipped sources and run phase 1 on an unseen fleet; phase-2 and phase-3 checks
run the delivered program on upstream directories the verifier writes (the unseen fleet's expected tables), so
a phase-1 mistake never costs phase-2 or phase-3 credit. Every program run happens once, in a fixed order,
inside one locked preparation step under a 4800-second budget: rewardkit evaluates criteria on several threads, and an expected table is
copied where the unprivileged program can read it only after every run it grades has finished. Field checks
compare the rows both sides share once 99% of the expected keys are present, so one wrong host scope
decision is priced by `hosts_identity` and the row order check alone; the -5 negatives that compare two runs ignore files the
program writes differently on every run, which `negative_nondeterministic_output` prices once.

Positive tests:

- `p1_tables_format` (weight 1)
- `hosts_identity` (weight 5)
- `hosts_hardware` (weight 5)
- `hosts_policy` (weight 5)
- `hosts_nameplate` (weight 5)
- `hosts_row_order` (weight 3)
- `circuits_ratings` (weight 5)
- `circuits_usable` (weight 5)
- `demand_samples` (weight 5)
- `demand_mean` (weight 5)
- `demand_p95` (weight 5)
- `demand_peak` (weight 5)
- `demand_energy` (weight 5)
- `psu_curves` (weight 5)
- `registry_sites` (weight 5)
- `registry_tenants` (weight 3)
- `registry_source_counts` (weight 3)
- `source_digests_in_force` (weight 1)
- `source_digests_superseded` (weight 1)
- `amendments_carried` (weight 5)
- `p1_matches_program_rerun` (weight 3)
- `eval_hosts` (weight 5)
- `eval_circuits` (weight 3)
- `eval_demand_samples` (weight 5)
- `eval_demand_mean` (weight 5)
- `eval_demand_energy` (weight 5)
- `eval_psu` (weight 3)
- `eval_amendments` (weight 3)
- `eval_registry` (weight 3)
- `cli_bad_arguments` (weight 1)
- `cli_nested_output` (weight 1)
- `p2_tables_format` (weight 1)
- `rack_budget_capacity` (weight 5)
- `rack_budget_load` (weight 5)
- `rack_budget_psu_n1_den1` (weight 3)
- `rack_budget_psu_n1_fra1` (weight 3)
- `rack_budget_psu_n1_iad2` (weight 3)
- `rack_budget_psu_n1_sin1` (weight 3)
- `rack_budget_pending` (weight 1)
- `host_alloc_request` (weight 5)
- `host_alloc_alloc` (weight 5)
- `host_alloc_amended` (weight 1)
- `site_energy_it` (weight 5)
- `site_energy_cost` (weight 5)
- `circuit_alarms_load` (weight 5)
- `circuit_alarms_thresholds` (weight 5)
- `tenant_pool_grants` (weight 5)
- `fleet_summary_sites` (weight 3)
- `p2_matches_program_rerun` (weight 3)
- `cli_missing_upstream` (weight 1)
- `p3_documents_format` (weight 1)
- `bmc_caps_values` (weight 5)
- `bmc_caps_native` (weight 5)
- `bmc_caps_controls` (weight 5)
- `bmc_caps_context` (weight 3)
- `pdu_alarms_thresholds` (weight 5)
- `pdu_alarms_loads` (weight 5)
- `chargeback_energy` (weight 5)
- `chargeback_cost` (weight 5)
- `exceptions_list` (weight 5)
- `capacity_sites` (weight 5)
- `release_applied` (weight 5)
- `release_totals` (weight 3)
- `lineage_complete` (weight 3)
- `p3_matches_program_rerun` (weight 3)
- `cli_missing_upstream_file` (weight 1)

Negative tests:

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -5)
- `negative_reads_training_corpus_at_runtime` (weight -5)
- `negative_nondeterministic_output` (weight -3)
- `negative_downstream_stage_reads_input_corpus` (weight -5)
- `negative_stage_output_ignores_upstream_directory` (weight -5)
- `negative_unbound_phase_digests` (weight -3)
- `negative_stage_writes_outside_output_dir` (weight -3)

Judged channel: 18 criteria (16 positive / 2 negative), positive total 44.

- **R1** (+3, trajectory): maintainable Python with focused functions, descriptive names and handled errors.
- **R2-R3** (+3 each, trajectory): pre-edit and post-build data and contract manifests compare equal.
- **R4-R6** (+3 each, trajectory): phases 1, 2 and 3 run with the stated read-only inputs.
- **R7** (+3, trajectory): the complete compiler runs from one external working directory with absolute paths.
- **R8** (+3, trajectory): all three phases are built under one fresh verification root.
- **R9** (+3, trajectory): all eighteen verification outputs compare byte for byte with the delivery.
- **R10-R11** (+3 each, trajectory): one malformed source record produces code 3 with one error line and no traceback.
- **R12-R13** (+3 each, trajectory): every phase-2 and phase-3 lineage value is recomputed and compared.
- **R14** (+3, trajectory): one rack's `psu_n1_ok` is independently recalculated.
- **R15-R16** (+1 each, user-facing message): source conflicts and verification mismatches are reported.
- **R17** (-5, trajectory): the agent opens grading files.
- **R18** (-5, user-facing message): the response claims success over contrary command evidence.

## Root cause

**Reading pipeline.** A reading is only meaningful after its unit factor and profile scale (one rounding),
the host's model power factor for VA, the outlet's latest calibration for PDU lines and the PSU efficiency at
the computed load for DC lines; an erratum replaces the result, and the PDU wins over the BMC over the agent for
the same host and time. The legacy compile skipped every step after the unit.

**Identity before time.** A local time needs the host's site, which needs the host, which for an alias needs
the time. In the data the loop always closes: every offset-less reading or policy record named through an
alias is named by an asset tag whose alias spans the whole period, so exactly one site gives a consistent
host; the time-windowed bird-name aliases only ever carry times with an offset.

**Revisions and force.** Revision numbers pick the effective record, ties broken by time then id; same-instant calibration records also go to the
greater id (standard section 8); voided
records drop out; records in superseded files count only when ratified. A void, erratum, ratification or
export profile timed at or after the freeze does nothing; because such a record is timed by the site of the
record it names, the oracle resolves until the set of post-cut registers stops changing.

**Lossy stage boundaries.** Phase 1 publishes one-decimal watts, whole watt-hours and integer budgets; phase 2
sums and rounds those published figures again and phase 3 rounds once more, so any shortcut back to the sources
lands on different digits.

## Solution shape

1. Read all 50 sources into eight-field rows (CSV, TSV, JSONL, JSON, XML, YAML, TOML, INI, log, text,
   Markdown, HTML, iCalendar, mbox, XLSX, DOCX, PDF, Parquet, SQLite).
2. Mark ratifications and voids, parse site-keyed times, pick effective revisions.
3. Build the alias windows, resolve host identities and the remaining times, pick effective policies.
4. Push every in-window reading through the pipeline, choose by source authority, compute demand.
5. Write hosts, circuits, demand, PSU tables, carried amendments and the registry with source counts and
   canonical-line digests.
6. Phase 2: budgets, the written-order allocation walk, site energy, circuit alarms, the tenant pool walk and
   the fleet summary with phase-1 lineage.
7. Phase 3: caps with tenant scaling and carried amendments, native caps, PDU alarms with amended breakers,
   largest-remainder chargeback, exceptions, the capacity walk and the release record, all with lineage.

## Ordered plan

1. Read the standard and the contract end to end, then map every source format onto the eight fields.
2. Write the readers, in-force logic, reading pipeline and demand calculation.
3. Write phase 2 and phase 3 from the contract and run the three stages into `/app/out`.
4. Compare pre-edit and post-build input manifests, then run the three stages from an external working
   directory with read-only copies of every input tree (R2-R7).
5. Build a fresh verification tree and compare all eighteen stage files byte for byte (R8-R9).
6. Probe one malformed record, independently check lineage attestations, and recalculate one
   `psu_n1_ok` figure (R10-R14).
7. Report source conflicts and release-verification mismatches (R15-R16).

## Pitfalls

- Taking the FINAL re-export or the legacy notes as truth fails `demand_mean` and `hosts_nameplate`.
- Picking revisions by file order or newest time fails `hosts_hardware` and `circuits_ratings`.
- Reading `1,234` as one thousand two hundred thirty-four fails `demand_mean` (the standard makes it 1.234).
- Converting local times with a fixed offset fails `demand_samples` across the fra1 summer-time change.
- Counting missing readings as zero fails `demand_samples` and `site_energy_it`.
- Applying post-cut amendments in phase 1 fails `amendments_carried` and `hosts_policy`.
- Recomputing phase 2 from the sources fails `rack_budget_load`; folding in sorted rather than written order
  fails `host_alloc_alloc`.
- Hard-coding the shipped fleet fails every phase-1 check on the unseen fleet and fires
  `negative_hardcoded_sample_answers`; constant phase-2 output fires
  `negative_stage_output_ignores_upstream_directory`.

## Provenance

```yaml
uuid: 67e0b296-174a-493f-a795-4f0283301f5c
instance_id: 67e0b296-174a-493f-a795-4f0283301f5c
task_name: terminal-bench/67e0b296-174a-493f-a795-4f0283301f5c
fix_patch_sha256: 78851670a4fcd4dd5553c753764d59742b0588ad80cd85514dee5c7f110cf371  # sha256 of solution/solve.sh
solve_py_sha256: 9c3570fe7d6085a8243e47d859a8c8d296ee447bff101b4ee48e336d7ae138b3  # informational; solve.py is 1037 lines
language: python
golden_score_measured: 1.000  # tests-only Step 10 score
golden_score_channel_a_pct: 100
golden_score_channel_b_pct: null
golden_score_runs: 2
golden_score_trial_id: sentinel-oracle-1, sentinel-oracle-2
golden_score_verified_by: >
  Two user-authorized oracle runs each measured exactly 1.000 on the test
  channel in tests/test_output.py; the judged channel has no oracle score.
caveat: >
  The test channel carries 66 positive checks worth 250 weight and 8
  negative checks worth -34 weight, so on its own it ranges -34/250 = -0.136
  to +1.000. The judged channel carries 18 criteria worth 44 positive points
  and -10 negative points. tests/reward.toml divides each channel's weighted
  sum by its positive total and gives each half of the reward, so this
  bundle's combined reward ranges from -0.1816 to +1.000 with no clamp.
```
