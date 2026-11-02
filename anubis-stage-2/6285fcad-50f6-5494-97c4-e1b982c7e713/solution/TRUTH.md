# TRUTH.md - 6285fcad-50f6-5494-97c4-e1b982c7e713

## Defect

The Corvel Basin Hydrometric Service published the January to March 2026 record of its CBHS-N network
(ten stations, 15 and 30 minute loggers, primary and backup sensors) from the saved compute pack
`/app/data/dv_compute_pack.md`. `dv_pub_26q2.csv`, `pub_stats_26q2.json` and `shift_wksht_pub.csv` are
wrong for almost every station day, because the pack read every text file as a shard, kept the newest
revision without the routing catalog, converted metres with 3.2808, applied no gage-height corrections,
took measurement gage heights from the field sheet, compared every measurement with the base rating under
the withdrawn tolerance Table T-1, evaluated the superseded `Ratings_2025` sheet without the Table R-2
errata, applied the edit journal in file order, computed daily means as the rating of the mean stage of a
UTC day and reported volumes with 1.9835 acre-feet per cfs-day. The agent must recompute the record from
the raw logger shards and deliver a reusable standard-library program `/app/out/run_flowrecord.py` plus
the 22 files it writes. The rules live in `hydrometry_handbook.md` (H1 to H18), the layouts in
`feed_layouts.md`, the report shapes in `output_contract.md`. Grade tolerances, winter coefficients,
rating errata, disregarded visits and the measurement review exist only in `hrb_26-04_minutes.pdf`;
rating points, rating version instants, drainage areas, drift tolerances and the workbook date system
exist only in `cbhs_rt_26q2.xlsx`. Nothing is recovered or decoded: every rule is written in the shipped
documents and the published numbers are wrong because the pack computed them wrongly.

1. (focal) Ingestion spine. Twenty layouts (wide hourly rows with MEAN summary rows, decimal commas,
   wall-clock times inside daylight time, epoch milliseconds, centimetre and millimetre values, unit
   suffixes, LST compact stamps, nested JSON, UTC hour arrays, backup-only NDJSON, grouped XML, zoned
   XML, fixed-width text, key-value logs with VOID lines, YAML blocks with flow rows, YAML minute maps
   whose values may be lists, run-length JSON series, a joined SQLite pair with serial times, a SQLite
   pair with a separate voids table), catalog file order with two listed-but-absent archives, routes as
   half-open UTC windows, RETIRED routes, the retired cache `zz_04rt.csv`, the four admission tests in
   their order, revision and file-order settlement, voids that never fall back. Defeats
   `dedup_report_exact`, `source_lineage_exact`, `reading_exclusions_exact` and, through the unit
   values, the whole core gate.
2. (focal) Station identity and stage. Tokens normalize with zero padding and resolve through the
   cross-reference and its addendum: L-143 means 03990665 before 2026-02-01 18:00 LST and 04597193
   after it; the addendum row of L-557 replaces the register row with the same valid_from, so L-557 is
   03777655, not 03715332. Units come from the record or from `eqp_reg.tsv` (03715332 changes from M to
   FT on 2026-01-31), datum offsets from the ACTIVE rows of `dtm_hist.psv` (03767985 is re-levelled on
   2026-02-27; three WITHDRAWN rows inside the quarter never apply), edits replay in seq order with
   RESTORE chains and SET rescuing fault readings, primary readings win over backups. Defeats
   `alias_resolution_exact`, `amendment_ledger_exact` and the core gate.
3. (focal) Corrections and shifts. Visits are amended (a reference, an action, a time, a logger value,
   a void followed by an amendment that must be ignored), two are disregarded by Table V-1, the
   reference is TAPE before WIRE before STAFF, an error counts when it is at least the drift tolerance
   (twelve used shipped visits sit exactly on their tolerance), and the correction is prorated between
   visits with RESET starting from zero. Measurements merge the late m3/s file by entered_utc, take
   Table M-1 verdicts and regrades, use the record gage height in the measurement window, classify ice
   by the replayed ice periods rather than the cover field, and are evaluated in order against the
   shift in use with a strict comparison (measurements 4313 and 4215 deviate by exactly their
   tolerance). Shift curves restart at every rating version. Defeats `visit_errors_exact` and the core
   reports `gh_corrections.tsv`, `measurement_eval.csv` and `shift_curves.json`.
4. (focal) Discharge and statistics. Two-control ratings with per-segment offsets, the exact-point and
   below-offset rules, Table R-2 errata, ACTIVE versions from the profile-named index sheet, binary64
   evaluation rounded to four significant figures, K factors prorated inside replayed ice periods or
   taken from Table W-1, time-weighted daily means with day-edge interpolation, a per-station maximum gap
   (04554766 has 90 minutes from the overlay), coverage at 0.90 of the day, the discharge rounding
   table, monthly means from rounded daily values, volumes with 86400/43560 and runoff from the
   workbook drainage area. Defeats `daily_values.csv`, `monthly_summary.xml`, `period_statistics.json`
   and every comparison report.
5. (drift) Averaging the day's gage heights and rating the mean is the method the pack used and looks
   physically reasonable; H15 integrates discharge in time. Fires `negative_daily_from_mean_stage`.
6. (drift) The field sheet gives a gage height for every measurement and the pack used it; H11 takes
   the mean corrected record in the window. Fires `negative_field_sheet_gage_height`.
7. (trap) Held-out networks only: an eu clock rule with a positive offset and a February to April
   period, a negative offset of -300 minutes, a profile that names network CBHS-E with other sheets,
   gap, coverage, margin and tolerance, a minutes variant whose in-force tolerances equal the shipped
   withdrawn ones, three exact tolerance ties and more errata and reviews, a 1904 workbook with text
   numbers, rich-text runs and cells without references, octal escapes, Td moves and uncompressed
   streams in the minutes, YAML flow mappings, denser revisions, voids, conflicts, outages and edits,
   more ice stations with AMEND chains, measurements inside outages (NO_RECORD), one station with no reading for a
   whole month (every day INC, so that month has empty values), a six-row token chain that resolves next to a
   seven-row chain that does not, out-of-scope records outside every route and in-scope unrouted records outside the
   record window (so the order of the H4 tests decides their counters), and lower-case method words in the visit
   amendments. A reader tuned to the
   shipped files passes the shipped reports and fails every held-out check.
8. (trap) `Ratings_2025`, the hidden `Ratings_2026_DRAFT`, `RatingIndex_25`, `Sites_Legacy`, Tables
   T-1, W-0 and R-1, the draft handbook and profile, the bulletin, the crew quick reference and the
   legacy rating export all look current. The rating sheets are priced by judged criterion R29 and the
   stale tolerances by R30.
9. (trap) The published values, dashboard and unit-value cache look like answers. Echoing the
   published daily values fires `negative_echoes_published`; reading the cache or dashboard as a shard
   is priced by judged criterion R32.

The reference is Python 3.12, standard library only, a 1604-line program with a
Bash dispatcher. Channel A (`tests/test_output.py`, weights on its `criteria.<name>(weight=W)`
registrations) grades the files and re-runs the program on nine networks the verifier builds at grade
time, allowing 600 seconds per run and building the corpora and runs in parallel child processes. Channel B (`tests/judge.toml`) grades the trajectory, the final
message and two end-state facts the tests never read.

Out of bounds: replaying the shipped daily values on a held-out network
(`negative_hardcoded_sample_answers`); behaviour tied to shard file names
(`negative_filename_dependent_behaviour`); nondeterministic output (`negative_nondeterministic_output`);
third-party packages (`negative_third_party_import`); echoing the published values
(`negative_echoes_published`). Reading grader paths is priced by judged criterion R35 and editing
`/app/data` by R31.

## Load-bearing work

23 artifacts are collected:

- `/app/out/run_flowrecord.py`
- `/app/out/unit_values.csv`
- `/app/out/gh_corrections.tsv`
- `/app/out/visit_errors.psv`
- `/app/out/measurement_eval.csv`
- `/app/out/shift_curves.json`
- `/app/out/ice_periods.jsonl`
- `/app/out/rating_tables_used.json`
- `/app/out/daily_values.csv`
- `/app/out/monthly_summary.xml`
- `/app/out/period_statistics.json`
- `/app/out/alias_resolution.csv`
- `/app/out/dedup_report.json`
- `/app/out/source_lineage.json`
- `/app/out/reading_exclusions.jsonl`
- `/app/out/amendment_ledger.psv`
- `/app/out/parameters_used.yaml`
- `/app/out/variance_vs_published.csv`
- `/app/out/shift_vs_published.csv`
- `/app/out/dashboard_disagreements.tsv`
- `/app/out/cache_divergence.jsonl`
- `/app/out/reconciliation.md`
- `/app/out/manifest.json`

- `/app/out/run_flowrecord.py` must accept `DATA_DIR OUT_DIR` and write the other 22 files.
- Reports are compared after parsing: delimited files as a header plus a multiset of rows, JSON
  documents structurally (arrays of objects as multisets except `files`, `points` and `k_points`,
  whose order is stated), JSON Lines as a multiset of objects, XML as attribute sets, the YAML file as a
  key map and the markdown file as a multiset of table rows under their section headings. Numbers
  compare by exact decimal value, so `1.20` equals `1.2`, but no rounding tolerance exists.
- `manifest.json` must describe the bytes actually on disk, in contract order.

Out of bounds by design: the program never needs network access or `/tests`.

## Verification

`tests/test.sh` hardens the verifier and runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`.
`tests/reward.toml` gives each channel half of `reward`. The rule combining the two channels belongs to
the runner harness and is not transcribed here.

Channel A declares 28 positive and 7 negative tests, positive weight total 78 and
negative weight total -25, so the theoretical reward range is
-25/78 = -0.321 to +1.000.

Positive tests (28):

- `deliverables_present` (weight 1)
- `program_writes_contract_files` (weight 1)
- `delimited_headers_exact` (weight 1)
- `json_report_keys` (weight 1)
- `manifest_consistent` (weight 1)
- `text_serialization` (weight 1)
- `visit_errors_exact` (weight 3)
- `rating_tables_used_exact` (weight 3)
- `alias_resolution_exact` (weight 3)
- `dedup_report_exact` (weight 3)
- `source_lineage_exact` (weight 3)
- `reading_exclusions_exact` (weight 3)
- `amendment_ledger_exact` (weight 3)
- `parameters_used_exact` (weight 1)
- `variance_vs_published_exact` (weight 1)
- `shift_vs_published_exact` (weight 1)
- `dashboard_disagreements_exact` (weight 1)
- `cache_divergence_exact` (weight 1)
- `reconciliation_exact` (weight 1)
- `heldout_reseed_exact` (weight 5)
- `heldout_zone_exact` (weight 5)
- `heldout_memo_exact` (weight 5)
- `heldout_profile_exact` (weight 5)
- `heldout_dense_exact` (weight 5)
- `heldout_ice_exact` (weight 5)
- `heldout_workbook_exact` (weight 5)
- `metamorphic_visits_exact` (weight 5)
- `metamorphic_measurements_exact` (weight 5)

Negative tests (7) hold only when the cheat or wrong reading is present:

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -5)
- `negative_nondeterministic_output` (weight -3)
- `negative_third_party_import` (weight -3)
- `negative_echoes_published` (weight -3)
- `negative_field_sheet_gage_height` (weight -3)
- `negative_daily_from_mean_stage` (weight -3)

Channel B is 35 criteria (28 positive / 7 negative), positive total 82:

- **R1** (+3, trajectory): The agent runs its program on at least one data directory copy whose hrb_26-04_minutes.pdf it rewrote with other memo table values or table statuses.
- **R2** (+3, trajectory): The agent appends the rows printed under a Table M-1 (continued) or Table W-1 (continued) line of hrb_26-04_minutes.pdf to the same table.
- **R3** (+3, trajectory): The agent reads the bracketed status at the end of each memo table title of hrb_26-04_minutes.pdf before it takes values from that table.
- **R4** (+3, trajectory): The agent runs its program on at least one data directory copy in which it changed the period or another setting of the CBHS-N block of dv_profile.yml.
- **R5** (+3, trajectory): The agent runs its program on at least one data directory copy in which it added, changed or removed an entry of uv_edits.jsonl or ice_obs_j2.ndjson.
- **R6** (+3, trajectory): The agent reads the date1904 setting of xl/workbook.xml before it converts the effective_date serials of the RatingIndex_26 sheet.
- **R7** (+3, trajectory): The agent reads rating_sheet, index_sheet and site_sheet from the CBHS-N block under networks in dv_profile.yml before it opens the workbook sheets.
- **R8** (+3, trajectory): The agent views the two stn_xref.sqlite rows of token L-143 together with their valid_from and valid_to values.
- **R9** (+3, trajectory): The agent views the xref_addendum.yml row of token L-557 that replaces the stn_xref.sqlite row with the same valid_from.
- **R10** (+3, trajectory): The agent views the ingest_catalog.json routes of zz_04rt.csv and their RETIRED status before it decides how that file counts.
- **R11** (+3, trajectory): The agent views the eqp_reg.tsv rows of station 03715332 whose primary sensor unit changes from M to FT.
- **R12** (+3, trajectory): The agent views the fv_amend.xml amendments of visit 1210, the void and the action change that follows it.
- **R13** (+3, trajectory): The agent views memo Table V-1 and the visits 1145 and 1212 it disregards before it builds the gage-height corrections.
- **R14** (+3, trajectory): The agent views the site_overlay.yaml entry of station 04554766 whose max_gap_minutes of 90 replaces the profile gap for that station.
- **R15** (+3, trajectory): The agent views the empty drift_tol_ft cell of station 03203376 in the Sites_2026 sheet of cbhs_rt_26q2.xlsx.
- **R16** (+3, trajectory): The agent views the memo Table M-1 rows whose verdict is REGRADE before it assigns tolerances to the measurements.
- **R17** (+3, trajectory): The agent runs its program on at least one data directory copy in which it changed or added a discharge measurement of qm_main_26q2.csv or qm_late.xml.
- **R18** (+3, trajectory): The agent views the ice_obs_j2.ndjson AMEND and WITHDRAW entries, such as entries 364 and 365, before it forms the ice periods.
- **R19** (+3, trajectory): The agent prints the shift in use and the prorated curve shift side by side for at least one open-water measurement that lies between two shift points of one rating version.
- **R20** (+3, trajectory): The agent runs its half-to-even rounding helper on at least two of the handbook H18 examples, such as 1234.5 to 1230 and 0.125 to 0.12.
- **R21** (+3, trajectory): The agent names at least one site and date whose published daily value differs from its recomputed value and traces that difference back to a setting of the dv_compute_pack.md Run settings table.
- **R22** (+3, trajectory): The agent runs /app/out/run_flowrecord.py with /app/data and /app/out after its last edit of the program.
- **R23** (+1, state_change): The agent leaves /app/out holding only run_flowrecord.py and the twenty-two files the instruction names.
- **R24** (+3, trajectory): The agent writes run_flowrecord.py free of bare except clauses and of except blocks whose body is only pass.
- **R25** (+3, final_answer): The response pairs each published-run defect it lists with a handbook section number or a memo table id.
- **R26** (+3, final_answer): The response names memo Tables T-1, W-0 and R-1 as tables it set aside.
- **R27** (+3, final_answer): The response names the Ratings_2025, Ratings_2026_DRAFT and Sites_Legacy sheets of cbhs_rt_26q2.xlsx as sheets it set aside.
- **R28** (+3, final_answer): The response names field_quickref.txt and ops_bulletin_feb.txt as files it set aside.
- **R29** (-5, trajectory): The agent evaluates the rating with points read from the Ratings_2025 or Ratings_2026_DRAFT sheet of cbhs_rt_26q2.xlsx.
- **R30** (-3, trajectory): The agent compares measurement deviations with the grade tolerances of memo Table T-1 or of field_quickref.txt.
- **R31** (-5, state_change): The agent modifies, adds or deletes a file under /app/data.
- **R32** (-3, trajectory): The agent feeds uv_cache_r3.jsonl or hydro_dash_export.tsv to its shard reader as logger readings.
- **R33** (-3, final_answer): The response cites a handbook section numbered outside H1 to H18 or a memo table id absent from hrb_26-04_minutes.pdf.
- **R34** (-3, trajectory): The agent states in its final message that its program ran cleanly while its last run of run_flowrecord.py on /app/data ended with a traceback or a nonzero exit status.
- **R35** (-5, trajectory): The agent opens a file under /tests or /logs/verifier during its run.

The verifier rebuilds the shipped network and nine held-out networks at grade time: a reseed with octal
memo escapes and rich-text workbook strings; an eu clock rule at offset +60 over February to April 2027
with Td-positioned memo rows; a minutes variant (tolerances E 3.0, G 6.0, F 9.0 in force and the
shipped values withdrawn, seven errata, six rejections, ten regrades, three disregarded visits, three
exact tolerance ties); a profile variant (network CBHS-E, sheets Ratings_2026B, RatingIndex_26B and
Sites_2026B, gap 45 minutes, coverage 0.85, margin 12 hours, tolerance 0.03, and one station silent for the whole
of February); a dense network
(revision rate 0.09, void rate 0.02, 40 same-revision conflicts, 12 outages, 12 fault runs, 160 edits,
10 midnight gaps, 14 visit amendments, six backup stations, YAML flow mappings, a six-row and a seven-row token
chain, and records that fail two admission tests at once); an ice network (eight
ice stations, six extra AMEND chains, nine measurements per station, offset -300); a workbook variant
(1904 dates, 80 percent text numbers, rich text, cells without references); the shipped network with
ten more visit amendments whose method words are lower case; the shipped network with three more measurements per station. The core
gate requires the eight core reports to be exact on all ten networks before any shipped-report or
held-out check pays. A renamed copy and two plain copies feed the negative checks.

## Root cause

**Authority.** The compute pack, published files, dashboard, cache, bulletin, quick reference, draft
handbook, draft profile and legacy export look official. H1 ranks the in-force minutes tables, the
profile-named workbook sheets and the overlay above them, and the binary files are the only place the
governing numbers exist. The profile itself holds four network blocks; only the CBHS-N block applies.

**One spine.** Every report descends from the selected readings and their corrected gage heights. A
wrong layout reading, route window, admission order, revision winner, edit replay, unit, datum offset,
token resolution or sensor choice moves gage heights, which move record gage heights of measurements,
which move deviations, SHIFT decisions and therefore every later shift in use, the prorated curves, the
ice K points, every unit value, every daily mean and every statistic.

**Interacting configuration.** The correction depends on the drift tolerance, which comes from the
overlay, the workbook site sheet or the profile; the measurement decision depends on the grade, which
Table M-1 may change, and on the shift in use, which depends on every earlier decision under the same
version; the ice K factor depends on the final shift curve, so the open-water pass must finish before
any ice measurement is evaluated; the daily mean depends on the per-station gap, which the overlay may
widen; the period boundaries depend on the clock offset, and wall-clock shards depend on the DST rule.

**Second pass.** The open-water evaluation uses the shift in use at each measurement, a carried value;
the unit values use the prorated curve that only exists once every measurement has been evaluated. Both
are needed and they differ between shift points.

**Red lines.** No figure may be copied from the shipped files into the program, and nothing under
`/app/data` may change.

## Solution shape

1. Parse the clock, profile block, overlay, station master, cross-reference with addendum, catalog,
   minutes tables (positioned text, string-aware tokenizer, continued tables) and workbook sheets
   (relationships, shared and inline strings, date1904, text numbers).
2. Read the listed shards in file order with their layouts, apply the four admission tests, settle
   revisions by file order, drop voids, replay the edit journal by seq, drop faults, pick sensors.
3. Convert units, add datum offsets, replay visit amendments, drop disregarded visits, build the
   prorated corrections and round the corrected gage heights.
4. Load ACTIVE versions and points with errata; merge measurements; replay ice; evaluate open-water
   measurements in order; build the prorated shift curves; evaluate ice measurements.
5. Unit values with K factors; daily integration with gaps, coverage and codes; monthly and period
   statistics; comparisons; render the 21 reports and the manifest.

## Ordered plan

1. Read the handbook, layouts and contract; rebuild the minutes rows by y and x and the workbook sheets
   through their relationships (R2, R6).
2. Read each minutes table status and the profile block, and diff the compute pack against the
   handbook, tracing a differing published day to a Run setting (R3, R7, R21).
3. Build the reader: catalog routes, tokens, units, datum, edits (R8 to R11).
4. Visits, tolerances and corrections (R12 to R15).
5. Measurements, ice and shifts with exact stage rounding (R16, R18 to R20).
6. Run the program on data directory copies with changed minutes tables, a changed profile block, a
   changed journal and changed measurements (R1, R4, R5, R17).
7. Render, run once after the last edit on `/app/data`, report the defects with their rules and the
   tables, sheets and files set aside (R22 to R28).

## Pitfalls

- Reading every text file as a shard, or skipping the catalog routes, admits the cache, the dashboard
  and the retired cache and fails the counters and the core gate; reading the cache is priced by R32.
- Settling duplicates before the route test lets an unrouted revision-3 copy win and fails the core
  gate.
- Resolving L-143 or L-557 without time gating or the addendum moves readings to the wrong station.
- Ignoring the equipment register unit change or the WITHDRAWN datum rows shifts gage heights by
  feet and fails every core check.
- Comparing the visit error strictly with the tolerance drops twelve shipped corrections.
- Taking deviations against the base rating or the prorated curve changes SHIFT decisions; taking
  the field sheet gage height fires `negative_field_sheet_gage_height`.
- Using the cover field instead of the replayed ice periods misclassifies measurement 4313.
- Rating the mean daily stage fires `negative_daily_from_mean_stage`; averaging readings without
  time weights fails the days with gaps and the midnight interpolation.
- Joining the flags of a unit value with a separator (`B;I`) fails `unit_values.csv` and with it the core gate.
- Rounding once at the end, or half up, breaks ties in corrected gage heights, shifts and daily
  means and fails the core gate.
- The superseded and draft rating sheets are priced by judged criterion R29; Table T-1 by R30.
- Hardcoding the shipped figures fires `negative_hardcoded_sample_answers`.

## Provenance

```yaml
uuid: 6285fcad-50f6-5494-97c4-e1b982c7e713
instance_id: 6285fcad-50f6-5494-97c4-e1b982c7e713
task_name: terminal-bench/6285fcad-50f6-5494-97c4-e1b982c7e713
fix_patch_sha256: 7613f0b60b52bd3240116151feb592ad9527917b6149514c96d3355f5eb707bc  # sha256 of solution/solve.sh
solve_py_sha256: f40f278dad6377da3e2fb8f2f103c4352083bc6b14670eba8e194111924e4c33  # informational; solve.py is 1604 lines
language: python
golden_score_measured: 1.000  # test channel only, tests/test_output.py
golden_score_channel_b_pct: null  # the judged channel has no oracle score
caveat: >
  The test channel carries 28 positive checks worth
  78 weight and 7 negative checks worth
  -25 weight, so on its own it ranges -25/78 = -0.321 to +1.000.
  The judged channel carries 35 criteria worth
  82 positive points. tests/reward.toml divides each
  channel's weighted sum by its positive total and gives each half of the
  reward, so the combined reward runs from -1.000 to +1.000 with no clamp.
```
