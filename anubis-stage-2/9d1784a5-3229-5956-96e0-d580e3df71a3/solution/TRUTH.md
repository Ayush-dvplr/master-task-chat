# TRUTH.md - 9d1784a5-3229-5956-96e0-d580e3df71a3

## Defect

The KTC-26B cryostat qualification team published the heat-load budget
`heatload_budget_published.csv` and the stage margins `stage_margins_published.json` from the saved
solve pack `budget_solve_pack.md`. Both are wrong for almost every link and stage. The agent must
find which rules the pack broke and which shipped files are authoritative, then deliver a reusable
standard-library program `/app/out/run_budget.py` plus the 21 files it writes. The rules live in
`thermal_budget_handbook.md` (H1 to H25). The joint conductances, solver constants, gauge areas,
parasitic loads, stage limits and rulings exist only in `governance_memo_k26b.pdf`, a PDF whose
cells are shuffled, positioned text objects. The conductivity tables, sensor calibrations and cooler
capacity maps exist only in `cryo_property_workbook.xlsx`, a date1904 workbook with withdrawn,
hidden and draft sheets.

1. (focal) Reading spine. Sixteen DAQ layouts:
   - decimal comma, thousands separators and fixed-width unit suffixes;
   - micro-unit integers split over two SQLite tables, and block-relative time offsets;
   - local wall time with an isdst selector.

   Revisions win before voids. Channel tokens resolve through dated channel assignments, and serials
   walk relabel chains to the end. Defeats `ingest_counters_exact`, `alias_resolution_exact` and,
   through the means, every core check.
2. (focal) Calibration and screens.
   - The family decides the space: PRT in R, NTC in 1/R, DIODE in V.
   - Calibration versions are dated with workbook serials under date1904.
   - Generic curves apply only to GENERIC_OK sensors.
   - Screens run in this order: maintenance blocks, rulings after the addendum, then a median spike
     screen. Sensor means are followed by a median outlier screen.

   Defeats `sensor_means_exact` and `stage_temperatures.csv` in the core.
3. (focal) Link geometry.
   - The revision in use is dated, and VOID scraps the link.
   - The amendment journal is settled from the highest seq down, including REVERSE of REVERSE.
   - Area specs cover mm2, cm2, rectangles and W:n x AWG from Table W-1. Lengths come in mm, cm and in.
   - Lot scales apply only to the Table S-2 materials.
   - Joint h_eff uses J-2 x bolts x the LOW torque and indium factors, rounded to the S-2 increment.

   Defeats `geometry_and_joints_exact` and `amendment_ledger_exact`.
4. (focal) Heat flow. q is the largest whole uW whose march, rounded to whole mK at every element
   (an exact conductivity integral per segment and a rounded drop per joint), ends at or above the
   cold node. Defeats `junction_profiles_exact` and `link_heat_flows.psv` in the core.
5. (focal) Intercept balance. Each floating node is the largest whole mK with a non-negative heat
   balance, and every balance evaluation re-solves its links. This is a second pass: the first,
   nominal reading looks finished. Defeats `intercept_solutions.json`, `stage_loads.csv` and
   everything downstream.
6. (focal) Margins.
   - The cooler model comes from the serial.
   - The capacity sheet is interpolated in mK, and the dated service-log derate is applied.
   - Capacity and reserve are each rounded once.
   - Verdicts follow the L-1 limits.

   Defeats `cooler_margins.xml` and `run_verdicts.json`.
7. (drift) Mean-k conductance (solve pack step 6) is a standard engineering shortcut. The contract
   is the exact integral with rounding at every step, and the two differ on every link.
8. (drift) Applying every overlay found and every key in it looks thorough. H13 applies only the
   overlay whose base_revision matches, and only its overridable_keys.
9. (trap) Run KTC-R16 straddles the 2026-10-25 offset change. Naive wall-clock arithmetic makes its
   plateau 90 minutes instead of 150.
10. (trap) J-1, P-1, S-1, K_TABLES_R2, K_TABLES_R4_DRAFT, CAL_K26A and CAPMAP_V1 sit beside the
    in-force tables. The bulletin, draft handbook, cache, quick reference and legacy file repeat
    withdrawn values. Fires `negative_withdrawn_tables`.
11. (trap) The published budget looks like an answer. Fires `negative_echoes_published`.

The reference is Python 3.12, standard library only: a 1592-line program with a
Bash dispatcher. Channel A (`tests/test_output.py`, weights on its `criteria.<name>(weight=W)`
registrations) grades the files on the shipped corpus. It also re-runs the program on six generated
held-out corpora and two metamorphic copies, all behind a full-core gate. Channel B
(`tests/judge.toml`) grades the trajectory and the final message.

Out of bounds:
- replaying the shipped heat flows (`negative_hardcoded_sample_answers`);
- name-dependent behaviour (`negative_filename_dependent_behaviour`);
- nondeterminism (`negative_nondeterministic_output`);
- echoing the published budget (`negative_echoes_published`);
- half-up rounding (`negative_half_up_rounding`);
- NTC in resistance space (`negative_ntc_resistance_space`);
- one relabel hop (`negative_one_hop_relabel`);
- voids before dedup (`negative_void_before_dedup`);
- nominal intercepts (`negative_nominal_intercepts`);
- withdrawn tables (`negative_withdrawn_tables`);
- a closed plateau window that keeps the reading at PLATEAU_END (`negative_closed_plateau_window`);
- imports outside the Python standard library (`negative_third_party_import`).

## Load-bearing work

22 artifacts are collected:

- `/app/out/run_budget.py`
- `/app/out/sensor_means.tsv`
- `/app/out/stage_temperatures.csv`
- `/app/out/intercept_solutions.json`
- `/app/out/link_heat_flows.psv`
- `/app/out/junction_profiles.jsonl`
- `/app/out/link_geometry.csv`
- `/app/out/joint_conductances.tsv`
- `/app/out/stage_loads.csv`
- `/app/out/cooler_margins.xml`
- `/app/out/run_verdicts.json`
- `/app/out/alias_resolution.csv`
- `/app/out/reading_exclusions.jsonl`
- `/app/out/dedup_report.json`
- `/app/out/source_lineage.json`
- `/app/out/amendment_ledger.csv`
- `/app/out/parameters_used.yaml`
- `/app/out/authority_audit.csv`
- `/app/out/variance_vs_published.csv`
- `/app/out/reconciliation.md`
- `/app/out/budget_summary.md`
- `/app/out/manifest.json`

- `/app/out/run_budget.py` must accept `DATA_DIR OUT_DIR` positionally and write all other files.
- How reports are compared after parsing:
  - delimited reports: cells as strings;
  - JSON and JSON Lines: values;
  - XML: attributes;
  - YAML: the parsed structure;
  - markdown: table rows as stripped cells, other lines as text without trailing spaces.

  Every comparison is exact, with no tolerance.
- `manifest.json` must describe the bytes on disk, in contract order.

Out of bounds by design: the program never needs network access or `/tests`.

## Verification

`tests/test.sh` hardens the verifier and runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`.
`tests/reward.toml` gives each channel half of `reward`.

Channel A declares 23 positive and 12 negative tests, positive weight total 73 and
negative weight total -40, so the theoretical reward range is
-40/73 = -0.548 to +1.000.

Positive tests (23):

- `deliverables_present` (weight 1)
- `program_writes_contract_files` (weight 1)
- `delimited_headers_exact` (weight 1)
- `heldout_run_rows_follow_input` (weight 1)
- `manifest_consistent` (weight 1)
- `text_serialization` (weight 1)
- `sensor_means_exact` (weight 3)
- `junction_profiles_exact` (weight 3)
- `geometry_and_joints_exact` (weight 3)
- `alias_resolution_exact` (weight 3)
- `ingest_counters_exact` (weight 3)
- `amendment_ledger_exact` (weight 3)
- `parameters_used_exact` (weight 3)
- `authority_audit_exact` (weight 3)
- `published_comparison_exact` (weight 3)
- `heldout_reseed_exact` (weight 5)
- `heldout_spring_exact` (weight 5)
- `heldout_memo_exact` (weight 5)
- `heldout_profile_exact` (weight 5)
- `heldout_intercepts_exact` (weight 5)
- `heldout_dense_exact` (weight 5)
- `metamorphic_amendments_exact` (weight 5)
- `metamorphic_rulings_exact` (weight 5)

Negative tests (12) hold only when the cheat or the wrong reading is present:

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -5)
- `negative_nondeterministic_output` (weight -3)
- `negative_closed_plateau_window` (weight -3)
- `negative_third_party_import` (weight -3)
- `negative_echoes_published` (weight -3)
- `negative_half_up_rounding` (weight -3)
- `negative_ntc_resistance_space` (weight -3)
- `negative_one_hop_relabel` (weight -3)
- `negative_void_before_dedup` (weight -3)
- `negative_nominal_intercepts` (weight -3)
- `negative_withdrawn_tables` (weight -3)

Channel B is 35 criteria (31 positive / 4 negative), positive total 103:

- **R1** (+5, trajectory): The agent decompresses the FlateDecode content streams of governance_memo_k26b.pdf and rebuilds its table rows by grouping Tm positioned text objects on a shared y coordinate ordered by x.
- **R2** (+5, trajectory): The agent's program or trajectory takes joint base conductances from memo Table J-2 marked IN FORCE, where BOLT_CU in band C is 412.5 mW/K, over the WITHDRAWN Table J-1 value of 379.5 mW/K.
- **R3** (+3, trajectory): The agent runs its program on at least one copy of the corpus whose governance_memo_k26b.pdf it rewrote with other memo table values or table statuses.
- **R4** (+3, trajectory): The agent limits lot scales to the lot_scale_materials of Table S-2, CU_OFHC, CU_ETP and AL6061, so CERTIFIED BRASS360 lots in material_lot_certs.xml keep a scale of 1.
- **R5** (+5, trajectory): The agent reads conductivities from workbook sheet K_TABLES_R3, the sheet named by conductivity_sheet in campaign_profile_k26b.yml, found through xl/workbook.xml and xl/_rels/workbook.xml.rels.
- **R6** (+3, trajectory): The agent multiplies the mW/cm-K rows of K_TABLES_R3 for G10_CR, SS304, TI6AL4V and PTFE by 0.1 to obtain W/m-K.
- **R7** (+3, trajectory): The agent's program or trajectory reads date1904 from the workbookPr element of xl/workbook.xml and converts the CAL_K26B valid_from serial 44760 to 2026-07-19.
- **R8** (+5, trajectory): The agent interpolates the calibration of NTC family sensors of sensor_inventory.json, such as LS-8422, linearly in conductance 1/R per handbook H9.2.
- **R9** (+5, trajectory): The agent computes link heat flow from the exact integral of piecewise linear k(T) per handbook H17.
- **R10** (+5, trajectory): The agent rounds every march element to a whole mK before the next element consumes it, per handbook H19.2.
- **R11** (+5, trajectory): The agent's program or trajectory settles intercept IX-W-01 of run KTC-R01 by the H20 heat balance search over whole mK, which gives status BALANCED.
- **R12** (+3, trajectory): The agent runs its program on at least one copy of the corpus in which it changed an offset or transition of site_calendar.yml.
- **R13** (+3, trajectory): The agent runs its program on at least one copy of the corpus in which it added, changed or removed an entry of the link amendment journal lk_3am0.ndjson.
- **R14** (+3, trajectory): The agent runs its program on at least one copy of the corpus in which it added, changed or removed an entry of ruling_addendum.xml.
- **R15** (+3, trajectory): The agent's program or trajectory converts the KTC-R16 plateau wall times across the 2026-10-25 offset change of site_calendar.yml into a 150 minute plateau window in UTC.
- **R16** (+3, trajectory): The agent takes from profile_overlay_site.yaml only the keys listed under its overridable_keys, spike_mK, outlier_mK and min_readings.
- **R17** (+3, trajectory): The agent applies the ISSUED entries of ruling_addendum.xml to memo Table R-1 in ascending seq order.
- **R18** (+3, trajectory): The agent runs its program on at least one copy of the corpus in which it changed an intercept or bundle element of intercept_register.xml.
- **R19** (+3, trajectory): The agent's program or trajectory calibrates the GENERIC_OK sensors RV-1299 and RV-6312 with curve PRT-385 of calibration_generic_curves.tsv.
- **R20** (+3, trajectory): The agent's program or trajectory applies the 6 percent DERATE of cooler CC-0417 dated 2026-10-04 in cooler_service_log.tsv only to runs dated on or after 2026-10-04 and before its RESTORE on 2026-10-27.
- **R21** (+3, trajectory): The agent assigns harness bundles of harness_dissipation.psv to nodes through the bundle elements of intercept_register.xml and sets aside the node_hint column.
- **R22** (+3, trajectory): The agent keeps run KTC-R22 in the budget because its rev 2 ABORT entry in run_log_k26b.csv carries WITHDRAWN.
- **R23** (+3, trajectory): The agent runs /app/out/run_budget.py on /app/data with /app/out as the output directory after its last edit of the program.
- **R24** (+3, trajectory): The agent runs its program on a copy of the corpus placed outside /app/data in which it changed at least one setting of campaign_profile_k26b.yml.
- **R25** (+3, state_change): The agent leaves every file under /app/data with its original bytes.
- **R26** (+1, state_change): The agent keeps its scratch files and copies outside /app/out.
- **R27** (+1, trajectory): The agent runs no pip, apt or other package installation command during its run.
- **R28** (+3, final_answer): The response lists at least five defects of the published run, each next to the budget_solve_pack.md step or handbook rule that shows it.
- **R29** (+3, trajectory): The agent's program or trajectory takes the conductor area of W: area specs from memo Table W-1, where gauge 32 is 0.0320 mm2.
- **R30** (+3, trajectory): The agent runs its program on at least one copy of the corpus in which it added, changed or withdrew an entry of run_log_k26b.csv.
- **R31** (+3, trajectory): The agent writes /app/out/run_budget.py so that every caught exception is either re-raised or reported, with no bare except clause.
- **R32** (-5, final_answer): The response states that /app/out/run_budget.py wrote its reports into /app/out while the last run of /app/out/run_budget.py on /app/data in the trajectory exited with a non-zero status.
- **R33** (-3, trajectory): The agent calibrates RV-6266 readings with an NTC curve from calibration_generic_curves.tsv.
- **R34** (-3, trajectory): The agent applies a spike_mK, outlier_mK or min_readings value taken from profile_overlay_lab.yaml.
- **R35** (-5, trajectory): The agent opens a file under /tests or /logs/verifier during its run.

**Full-core gate.** No gated or held-out point is awarded unless six core reports are exact. They
must be exact in `/app/out` and in the re-runs on all eight held-out corpora:
`stage_temperatures.csv`, `intercept_solutions.json`, `link_heat_flows.psv`, `stage_loads.csv`,
`cooler_margins.xml` and `run_verdicts.json`. Each held-out check then compares all twenty reports
of its corpus.

**Held-out corpora.** They are synthesized at grade time from the embedded generator:

- `h_reseed`: a new seed, plus one run whose 4 K sensors read without noise so that a reading sits
  exactly spike_mK from its median and a sensor mean exactly outlier_mK from the stage median (H11.1,
  H12.1: equal is kept);
- `h_spring`: a spring skipped hour, a +01:00 base offset and the 1900 date system, with the plateau
  start of the clock-change run logged at a wall time inside the skipped hour (H4.1);
- `h_memo`: J-3, P-3 and S-3 in force, other factors and increment, other gauge areas and limits,
  plus one 4 K plateau at 6.240 K (KTC-R02), above the 6.0 K end of the capacity map (H21.3
  OUT_OF_MAP);
- `h_profile`: other sheet names, knobs, reserves and profile revision 8, while both overlays keep
  base_revision 7, so neither overlay applies (H13.2);
- `h_intercepts`: most runs carry intercepts, and an added copper strap from IX-W-01 of KTC-R01 straight
  to the 4 K plate drives that intercept to its floor (H20.2 FLOOR);
- `h_dense`: 32 runs, more sensors, relabels, remaps, stage moves and amendments, plus six same-shard
  same-rev reading copies with a changed raw value, settled by file order (H5.2) and a rev 3 link row with the
  effective_from of its rev 2 (H14.2).

The metamorphic copies `m_amend` and `m_rulings` change the shipped corpus. `m_amend` adds amendment
chains. `m_rulings` adds addendum rescissions and reinstatements and maintenance blocks, one of them
covering a whole plateau under the alias scope PLATE4K so that stage is NO_SENSORS (H10.2, H12.1),
and raises one harness bundle so that a PASS stage ends with its margin equal to its reserve
(H21.5).

## Root cause

**Authority.** The solve pack, the published files, the cache, the dashboard, the bulletin, the
quick reference, the draft handbook, the legacy file and the lab overlay all look official. The
handbook names the IN FORCE memo tables and the profile-named sheets. The binary files are the only
place the governing numbers exist.

**One spine.** Every output descends from the deduplicated, calibrated readings. A wrong space,
rounding mode, relabel walk, window edge or screen moves a stage temperature by a few mK. That moves
every link q, every intercept, every load and some verdicts.

**Interacting configuration.** The settings come from four layers: global profile, per-run
profile, matching overlay and overridable keys. The memo table in force is decided by its label, the
workbook sheet by the profile, and the calibration version by a workbook date under date1904. A
cooler derate depends on the service-log date relative to the run date.

**Red lines.** No figure may be copied from the shipped files into the program, and nothing under
`/app/data` may change.

## Solution shape

1. Parse the profile, overlays, calendar, registers, inventory and sensor map. Rebuild the memo rows
   from the PDF and the sheets from the XLSX.
2. Read the sixteen layouts and resolve tokens. Settle revisions, then voids. Count lineage.
3. Calibrate, screen, compute sensor means and stage temperatures.
4. Resolve installs and revisions, settle amendments, build segments and joints.
5. Solve intercepts by balance search with q memoised, then every link.
6. Loads, capacity, margins and verdicts. Audit, comparisons, render and manifest.

## Ordered plan

1. Read the handbook, contract and layouts. Decode the PDF and the workbook (R1, R5, R7).
2. Diff the solve pack against the handbook (R9, R28).
3. Build the reader with dedup, channel maps and relabel chains (R15).
4. Calibration and screens (R8, R16, R17, R19).
5. Geometry, joints, march and intercepts (R2, R4, R6, R10, R11, R29).
6. Margins (R20, R21, R22). Test on copies of the corpus with a changed campaign profile, memo, site
   calendar, amendment journal, ruling addendum, intercept register and run log (R24, R3, R12, R13, R14,
   R18, R30). Run once after the last edit and report (R23, R25 to R28, R31).

## Pitfalls

- Mean-k conductance fails `link_heat_flows.psv` in the core and every gated check.
- Rounding once at the end of the march fails `junction_profiles_exact` and the core.
- Nominal intercept temperatures fire `negative_nominal_intercepts`.
- NTC in resistance fires `negative_ntc_resistance_space`.
- A one-hop relabel lookup fires `negative_one_hop_relabel`.
- Voids before dedup fire `negative_void_before_dedup`.
- Half-up rounding fires `negative_half_up_rounding`.
- J-1, P-1 or S-1 fire `negative_withdrawn_tables`.
- Ignoring date1904 makes every calibration version start four years early and fails every check.
- Hardcoding the shipped tables fires `negative_hardcoded_sample_answers`.

## Provenance

```yaml
uuid: 9d1784a5-3229-5956-96e0-d580e3df71a3
instance_id: 9d1784a5-3229-5956-96e0-d580e3df71a3
task_name: terminal-bench/9d1784a5-3229-5956-96e0-d580e3df71a3
fix_patch_sha256: 84738f313b1ffe648140208809e74fc87e0c37658b92ea97536538baef4d7893  # sha256 of solution/solve.sh
solve_py_sha256: 1e76825788330415646f48b4acfa5d5e0a37762f05e1ae92420dbf584c46b7fd  # informational; solve.py is 1592 lines
language: python
golden_score_measured: 1.000  # test channel, oracle
golden_score_channel_a_pct: 100.0
golden_score_channel_b_pct: null  # the judged channel has no oracle score
golden_score_runs: 5
golden_score_trial_id: s10_oracle  # harbor 0.24.0 job on the exe_copy.py tests-only copy
golden_score_verified_by: >
  Step 10 on harbor 0.24.0 with the docker environment: oracle 1.000 on each
  of five runs, nop 0.000, the stub solution 0.0137 (deliverables_present
  only) and the owner-only copy 1.000, on the test channel in
  tests/test_output.py only; the judged channel has no oracle score.
caveat: >
  The test channel carries 23 positive checks worth 73 weight and 12
  negative checks worth -40 weight, so on its own it ranges -40/73 = -0.548
  to +1.000. The judged channel carries 35 criteria worth 103 positive
  points. tests/reward.toml divides each channel's weighted sum by its
  positive total and gives each half of the reward, so the combined reward
  runs from 0.5 x (-40/73) + 0.5 x (-16/103) = -0.352 to +1.000 with no
  clamp.
```
