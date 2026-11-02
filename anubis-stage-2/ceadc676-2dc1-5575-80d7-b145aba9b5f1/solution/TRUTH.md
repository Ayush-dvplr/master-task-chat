# TRUTH.md - ceadc676-2dc1-5575-80d7-b145aba9b5f1

## Defect

The facility published EA-IRMS batch HSI-2611 (d15N versus AIR, d13C versus VPDB, two lines K1
and K2) from the saved rerun pack `/app/data/rerun_pack.md`. `published_results.csv` and
`published_session_params.json` are wrong for almost every sample element and every session,
because the pack read the shards without the catalog, took the newest revision regardless of the
audit trail, ignored the autosampler SKIP log, fitted linearity per session, fitted drift against
the counter, subtracted the blank first, normalized with the withdrawn memo Table N-1 sets and the
hidden `RM_Certified_DRAFT` sheet, screened replicates with the superseded one-sided Table G-0,
took session status from the QC dashboard and rounded binary floats once at the end. The agent
must recompute the batch from the raw peak exports and deliver a reusable standard-library
program `/app/out/run_irms.py` plus the 22 files it writes. The rules live in
`method_handbook.md` (H1 to H17), the layouts in `feed_layouts.md`, the report shapes in
`output_contract.md`. The reference sets, limits, amplitude windows, linearity thresholds, QC
tolerances, flag and reason codes, Grubbs critical values and session rulings exist only in
`governance_memo.pdf`; the certified lot values, QC assigned values, elemental composition,
capsule masses and the 1904 date system exist only in `reference_workbook.xlsx`.

1. (focal) Ingestion spine. Twenty-two layouts (milli-permil integers, ratio deltas, mVs areas,
   volt amplitudes, decimal commas, EAV and split SQLite tables, nested JSON, YAML blocks, a wide
   TSV, fixed width), catalog replay with RETIRE and re-REGISTER, project and reference-peak
   filters, cross-file duplicates in catalog order, revision admission through the latest audit
   entry with a Table C-1 code, and the void test on the selected revision only. Defeats
   `dedup_report_exact`, `source_lineage_exact` and, through the ledger, the whole core gate.
2. (focal) Positions. SKIP events shift every later counter one tray per SKIP (SQ-2611-13 skips
   twice at counter 21); the tray journal settles SET and REVERSE chains including a REVERSE of a
   REVERSE; tokens resolve through chained, project-scoped and time-gated aliases (QCX means
   QC-SED before 2026-10-28 and QC-MUS from that session date). Defeats
   `position_resolution_exact`, `alias_resolution_exact` and fires `negative_skip_events_ignored`.
3. (focal) Correction chain. Instrument-day linearity on the local session date with lookback and
   Table L-1 thresholds; drift on run minutes with PAUSE intervals removed; blank mass balance;
   iterative least-squares normalization on lot-certified values that stops at LIMIT_STOP or
   MAX_REJECT; stage rounding half to even. The shipped batch removes two points from SQ-2611-09
   carbon and stops SQ-2611-15 carbon at LIMIT_STOP; the held-out memo batch puts two outliers in
   one nitrogen fit so that its max_rejections of 1 ends it at MAX_REJECT, and gives another
   nitrogen fit both stop conditions at once, where LIMIT_STOP is checked first; the reseeded batch
   leaves one session with a single in-window nitrogen RM-GLU-H point (NO_NORMALIZATION); the dense
   batch has a session whose every blank is above the A-1 limit; the zone batch has a session whose
   ELM-ACT capsules all carry an EXCLUDE flag, so its response factor is empty. Drift on the
   counter, blank first or a single fit per session fails the core reports on every batch.
4. (focal) Decisions and reporting. Table Q-1 acceptance without the drift material, slope window,
   last LEAK_CHECK, latest in-force ruling, effective client requests, Grubbs screening with the
   Table G-1 column the profile names, balance-corrected masses and the quick reference molar
   masses. The reseeded batch gives two sessions several reasons at once (SLOPE, QC and LEAK on
   one, NO_NORMALIZATION and LEAK on another), so the H13 reason order is graded; the rulings batch
   puts an EXCLUDE_POSITION ruling on a flagged capsule, so the ledger must name the ruling over
   the flag. Held-out batches carry the tie-breaks: two in-force rulings on one session and date
   (the higher ruling id wins, printed in either order), two ACTIVE requests for one sample on one
   date (the higher request id wins) and two LEAK_CHECK events in one minute (the higher event id
   wins). Defeats `isotope_results.csv` and every comparison report.
5. (drift) Taking the latest revision of a peak looks natural; H4 admits a reintegration only
   through its latest audit entry, and a void on the selected revision drops the element instead
   of falling back.
6. (drift) A per-session linearity slope from the three ELM-ACT capsules looks local and sound;
   H8 assigns the instrument-day LIN session by local date, with a threshold.
7. (trap) Held-out batches only: memo literals with three-digit octal escapes, memo rows laid out
   with Td moves after one Tm, memo page streams stored uncompressed, workbook shared strings
   split into rich-text runs, workbook cells written without an `r` reference, YAML shards written
   as flow mappings, linearity sessions with fewer than linearity_min_points ELM-ACT injections,
   and memo cells whose literal text contains the letters ET (F-WET). A
   reader tuned to the shipped files passes the shipped reports and fails every held-out check.
   SQ-2611-07 exports local wall clocks inside the repeated hour of 2026-10-25 (earlier
   instant, +02:00); SQ-2611-08 crosses the change in an epoch export; SQ-2611-11 starts at 00:29
   local, so its session date differs from its UTC date. Held-out batches add a skipped spring hour
   with a pause typed inside it and a site clock with a negative base offset.
8. (trap) Table N-1, Q-0 and G-0, the hidden DRAFT sheet, the 2019 and 2026R sheets, the
   noticeboard values, the quick reference statistics, `ab_0re7.csv` and `mv_full_export.csv`
   look current. Table N-1 fires `negative_withdrawn_reference_set`; the DRAFT and 2019 sheets
   are priced by judged criterion R29.
9. (trap) The published results and the LIMS cache look like answers. Fires
   `negative_echoes_published`.

The reference is Python 3.12, standard library only, a 1351-line program with a
Bash dispatcher. Channel A (`tests/test_output.py`, weights on its `criteria.<name>(weight=W)`
registrations) grades the files and re-runs the program on eight batches the verifier builds at
grade time, allowing 120 seconds per run. Channel B (`tests/judge.toml`) grades the trajectory, the
final message and two end-state facts the tests never read.

Out of bounds: replaying the shipped sample results on a held-out batch
(`negative_hardcoded_sample_answers`); behaviour tied to shard file names
(`negative_filename_dependent_behaviour`); nondeterministic output
(`negative_nondeterministic_output`); third-party packages (`negative_third_party_import`);
echoing the published values (`negative_echoes_published`). Reading grader paths is priced by
judged criterion R33.

## Load-bearing work

23 artifacts are collected:

- `/app/out/run_irms.py`
- `/app/out/injection_ledger.csv`
- `/app/out/position_resolution.csv`
- `/app/out/alias_resolution.psv`
- `/app/out/dedup_report.json`
- `/app/out/source_lineage.json`
- `/app/out/linearity_slopes.json`
- `/app/out/drift_fits.tsv`
- `/app/out/blank_corrections.psv`
- `/app/out/normalization_fits.json`
- `/app/out/corrected_injections.jsonl`
- `/app/out/elemental_factors.tsv`
- `/app/out/session_acceptance.csv`
- `/app/out/qc_results.xml`
- `/app/out/isotope_results.csv`
- `/app/out/replicate_screening.jsonl`
- `/app/out/parameters_used.yaml`
- `/app/out/variance_vs_published.csv`
- `/app/out/session_param_diff.json`
- `/app/out/dashboard_disagreements.csv`
- `/app/out/cache_divergence.jsonl`
- `/app/out/reconciliation.md`
- `/app/out/manifest.json`

- `/app/out/run_irms.py` must accept `DATA_DIR OUT_DIR` and write the other 22 files.
- Reports are compared after parsing: delimited files as a header plus a multiset of rows, JSON
  documents structurally, JSON Lines as a multiset of objects, XML as attribute sets, the YAML file
  as a key map and the markdown file as a multiset of table rows under their section headings.
  Numbers compare by exact decimal value, so `1.20` equals `1.2` but no rounding tolerance exists.
- `manifest.json` must describe the bytes actually on disk, in contract order.

Out of bounds by design: the program never needs network access or `/tests`.

## Verification

`tests/test.sh` hardens the verifier and runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`.
`tests/reward.toml` gives each channel half of `reward`. The rule combining the two channels
belongs to the runner harness and is not transcribed here.

Channel A declares 27 positive and 7 negative tests, positive weight total
71 and negative weight total -25, so the
theoretical reward range is -25/71 = -0.352 to +1.000.

Positive tests (27):

- `deliverables_present` (weight 1)
- `program_writes_contract_files` (weight 1)
- `delimited_headers_exact` (weight 1)
- `json_report_keys` (weight 1)
- `manifest_consistent` (weight 1)
- `text_serialization` (weight 1)
- `position_resolution_exact` (weight 3)
- `alias_resolution_exact` (weight 3)
- `dedup_report_exact` (weight 3)
- `source_lineage_exact` (weight 3)
- `blank_corrections_exact` (weight 3)
- `elemental_factors_exact` (weight 3)
- `qc_results_exact` (weight 1)
- `parameters_used_exact` (weight 1)
- `variance_vs_published_exact` (weight 1)
- `session_param_diff_exact` (weight 1)
- `dashboard_disagreements_exact` (weight 1)
- `cache_divergence_exact` (weight 1)
- `reconciliation_exact` (weight 1)
- `heldout_reseed_exact` (weight 5)
- `heldout_spring_exact` (weight 5)
- `heldout_zone_exact` (weight 5)
- `heldout_memo_exact` (weight 5)
- `heldout_profile_exact` (weight 5)
- `heldout_dense_exact` (weight 5)
- `metamorphic_journal_exact` (weight 5)
- `metamorphic_rulings_exact` (weight 5)

Negative tests (7) hold only when the cheat or wrong reading is present:

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -5)
- `negative_nondeterministic_output` (weight -3)
- `negative_third_party_import` (weight -3)
- `negative_echoes_published` (weight -3)
- `negative_withdrawn_reference_set` (weight -3)
- `negative_skip_events_ignored` (weight -3)

Channel B is 35 criteria (28 positive / 7 negative), positive total 86:

- **R1** (+5, trajectory): The agent rebuilds each table row of governance_memo.pdf from the text objects of one page that share a y coordinate.
- **R2** (+5, trajectory): The agent tokenizes the memo content streams so that BT and ET count as operators only outside string literals.
- **R3** (+3, trajectory): The agent decodes a backslash followed by three octal digits inside a memo literal string as one character.
- **R4** (+3, trajectory): The agent joins the text of every rich-text run of a shared string item in the workbook.
- **R5** (+3, trajectory): The agent maps each sheet name of reference_workbook.xlsx to its part file through the relationship ids of xl/_rels/workbook.xml.rels.
- **R6** (+3, trajectory): The agent reads the status at the end of each memo table title before it takes values from that table.
- **R7** (+3, trajectory): The agent views the ingest_catalog.json events of the file ma_5gw1.md before it writes its catalog replay.
- **R8** (+3, trajectory): The agent views the reintegration_audit.db entries 7157 and 7161 before it writes its revision admission rule.
- **R9** (+3, trajectory): The agent views the autosampler_events.txt lines AS-4235 and AS-4238 before it writes its tray mapping.
- **R10** (+3, trajectory): The agent views the tray_corrections.ndjson entries 491, 494 and 497 of SQ-2611-06 tray 41 before it writes its journal settlement.
- **R11** (+3, trajectory): The agent lists every material_alias row of alias_register.sqlite whose token is QCX together with its valid_from date.
- **R12** (+3, trajectory): The agent checks the xr_07ka.csv times of SQ-2611-07 that fall between 02:00 and 03:00 on 2026-10-25 against the transitions of site_clock.yaml.
- **R13** (+3, trajectory): The agent views the PAUSE and RESUME rows that session_events.psv holds for SQ-2611-03.
- **R14** (+3, trajectory): The agent lists the linearity sessions with their instrument and local session date before it assigns linearity slopes.
- **R15** (+3, trajectory): The agent prints the per-point residuals of at least one normalization fit while it develops its screening loop.
- **R16** (+3, trajectory): The agent views every memo Table R-1 ruling that targets SQ-2611-16 before it settles the decision of that session.
- **R17** (+3, trajectory): The agent checks the profile drift_material against the materials of memo Table Q-1 before it builds the QC acceptance checks.
- **R18** (+3, trajectory): The agent checks its rounding code against the three worked examples of handbook H15, which round 2.0345 and 2.0355 at 3 decimals and the mean of 1.244 and 1.246 at 2 decimals.
- **R19** (+3, trajectory): The agent decides each Grubbs removal by an exact comparison of the statistic with the memo Table G-1 value.
- **R20** (+3, trajectory): The agent traces at least one published value that differs from its recomputed value back to the input reading or correction stage that moves it.
- **R21** (+3, trajectory): The agent runs its program on at least one batch it built by changing a shipped input file such as analysis_profile.yml or site_clock.yaml.
- **R22** (+3, trajectory): The agent runs /app/out/run_irms.py with /app/data and /app/out after its last edit of the program.
- **R23** (+1, state_change): The agent leaves /app/out holding only run_irms.py and the twenty-two files the instruction names.
- **R24** (+3, trajectory): The agent writes run_irms.py free of bare except clauses and of except blocks whose body is only pass.
- **R25** (+3, final_answer): The response pairs each published-run defect it lists with a handbook rule number or a memo table id.
- **R26** (+3, final_answer): The response names memo Tables N-1, Q-0 and G-0 as tables it set aside.
- **R27** (+3, final_answer): The response names the hidden RM_Certified_DRAFT sheet of reference_workbook.xlsx as set aside.
- **R28** (+3, final_answer): The response names ab_0re7.csv and mv_full_export.csv as files it set aside.
- **R29** (-5, trajectory): The agent normalizes with certified values read from the RM_Certified_DRAFT or RM_Legacy_2019 sheet of reference_workbook.xlsx.
- **R30** (-3, trajectory): The agent takes session decisions from the statuses of qc_dashboard.csv.
- **R31** (-3, final_answer): The response cites a handbook rule numbered outside H1 to H17 or a memo table id absent from governance_memo.pdf.
- **R32** (-3, trajectory): The agent states in its final message that its program ran cleanly while its last run of run_irms.py on /app/data ended with a traceback or a nonzero exit status.
- **R33** (-5, trajectory): The agent opens a file under /tests or /logs/verifier during its run.
- **R34** (-5, state_change): The agent modifies, adds or deletes a file under /app/data.
- **R35** (-1, trajectory): The agent runs a pip, uv or apt install command.

The verifier rebuilds the shipped batch and eight held-out batches at grade time: a reseed with a
session lacking normalization points, stacked rejection reasons and a same-date ruling pair; a
spring batch across a skipped hour with a pause typed in it, the 1900 date system and same-date
requests; a batch under a site clock with base offset -05:00 and other transition rules, a session
with every elemental standard flagged and a same-minute leak check pair; a memo variant (three
nitrogen reference materials, other limits, thresholds, windows, tolerances, alpha 0.01 and a
nitrogen fit that ends at MAX_REJECT); a profile variant (RM_Certified_2026R, drift material
QC-SED, carbon first, other a_ref, lookback 0, other fit minima, drift fits that end INSUFFICIENT,
reference peaks inside retired segments); a dense batch with a session whose blanks all exceed the
limit; the shipped batch with 36 extra journal chains; the shipped batch with extra rulings, a
ruling on a flagged position and a smaller scope. The core gate requires the eight core reports to
be exact on all nine batches before any shipped-report or held-out check pays. A renamed copy and
two plain copies feed the negative checks.

## Root cause

**Authority.** The rerun pack, published files, cache, dashboard, noticeboard and quick reference
look official. H1 ranks the handbook, the in-force memo tables and the profile-named workbook
sheets above them, and the binary files are the only place the governing numbers exist.

**One spine.** Every report descends from the kept injection elements and their trays. A wrong
layout reading, catalog state, audit admission, void order, skip offset or journal settlement moves
material assignments, which move blanks, drift points, normalization points, QC means, session
decisions and every sample mean.

**Interacting configuration.** The linearity slope depends on the local session date, which
depends on the site clock; the drift fit depends on run minutes, which depend on typed pause
times read through the same clock; the normalization depends on lot values found through the
capsule register; acceptance depends on the drift material named in the profile; the Grubbs
column depends on the profile alpha.

**Red lines.** No figure may be copied from the shipped files into the program, and nothing
under `/app/data` may change.

## Solution shape

1. Parse the clock, profile, alias register, manifest, memo tables (positioned text) and workbook
   sheets (relationships, shared and inline strings, date1904).
2. Replay the catalog, read the 22 layouts in first-REGISTER order, filter and deduplicate,
   admit revisions through the audit trail, apply the void test, count lineage.
3. Apply SKIP offsets, settle the journal, resolve tokens, attach capsules, lots, masses and
   exclusions.
4. LIN slopes and assignment; linearity, drift, blank, normalization with screening; elemental
   factors; acceptance with QC, leak and rulings.
5. Requests, Grubbs screening, sample means and C:N; comparisons; render and manifest.

## Ordered plan

1. Read the handbook, contract and layouts; rebuild the memo rows with a string-aware tokenizer
   and the workbook sheets through their relationships with rich-text runs (R1 to R5).
2. Read each memo table status and diff the rerun pack against the handbook and memo (R6, R20).
3. Build the reader: catalog, audit, voids, skips, journal, aliases, clock, pauses (R7 to R13).
4. Linearity, corrections and normalization with screening at exact stage rounding, the rounding
   checked against the H15 worked examples (R14, R15, R18).
5. Acceptance, replicates and reporting (R16, R17, R19).
6. Render, run once after the last edit on `/app/data`, run on a changed copy, report the
   defects with their rules and the tables, sheets and files set aside (R21 to R28).

## Pitfalls

- Reading local wall clocks without the site clock fails the ledger and every core check.
- Fitting drift against the counter, correcting the blank first or fitting normalization once per
  session moves every corrected value and fails the core gate.
- Ignoring max_rejections passes the shipped batch and fails the held-out memo batch.
- Breaking a ruling, request or leak check tie by file order fails the reseeded, spring, zone or
  dense batch.
- The DRAFT sheet is priced by judged criterion R29; Table N-1 fires
  `negative_withdrawn_reference_set`.
- Treating counters as trays fires `negative_skip_events_ignored`.
- Splitting text objects on the substring ET inside a string loses memo cells on some batches and
  fails the held-out checks only.
- Binary float rounding breaks exact ties in sample means and fails `isotope_results.csv`.
- Hardcoding the shipped tables fires `negative_hardcoded_sample_answers`.

## Provenance

```yaml
uuid: ceadc676-2dc1-5575-80d7-b145aba9b5f1
instance_id: ceadc676-2dc1-5575-80d7-b145aba9b5f1
task_name: terminal-bench/ceadc676-2dc1-5575-80d7-b145aba9b5f1
fix_patch_sha256: e658c2d77d02d4526675da2a014f1548b3a0c57daf9d542eb5e09e33e65ea5c2  # sha256 of solution/solve.sh
solve_py_sha256: d3ae811e4a959952feea39d279be2d6dcda20c459aa50802e0e9234259938c7f  # informational; solve.py is 1351 lines
language: python
golden_score_measured: 1.000  # test channel only, tests/test_output.py
golden_score_channel_a_pct: 100.0
golden_score_channel_b_pct: null  # the judged channel has no oracle score
golden_score_runs: 5
golden_score_trial_id: null
golden_score_verified_by: >
  Five oracle runs on a tests-only copy of these bytes each scored exactly
  1.000. A no-op run scored 0.000. An oracle run that left every file it
  wrote at mode 0600 scored 1.000. A stub writing 23 empty artifacts scored
  0.014, paid only by deliverables_present (weight 1 of 71). All figures
  cover tests/test_output.py only.
caveat: >
  The test channel carries 27 positive checks worth
  71 weight and 7 negative checks worth
  -25 weight, so on its own it ranges -25/71 = -0.352 to +1.000.
  The judged channel carries 35 criteria worth
  86 positive points. tests/reward.toml divides each
  channel's weighted sum by its positive total and gives each half of the
  reward, so the combined reward runs from -1.000 to +1.000 with no clamp.
```
