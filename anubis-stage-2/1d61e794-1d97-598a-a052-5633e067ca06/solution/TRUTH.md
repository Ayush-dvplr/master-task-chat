# TRUTH.md - 1d61e794-1d97-598a-a052-5633e067ca06

## Defect

The Vellmar Delta Geodetic Office published adjusted heights and subsidence rates for the VDL-26
double-run precise levelling campaign from the saved run pack `/app/data/adjustment_run_pack.md`.
`adjusted_heights_published.csv` and `subsidence_published.json` are wrong for every mark, because the
pack held the network on the withdrawn Table C-1 control heights, applied the back rod's scale to the whole
setup difference, omitted the rod expansion correction, tested only the first forward and first backward
run of each section, snooped with the a posteriori variance factor and took the office booking date as the
run date. Nothing is decoded, reverse engineered or recovered: every rule is written in
`levelling_handbook.md` (H1 to H22), `feed_layouts.md` (L01 to L16) and `output_contract.md`. The task is a
faulty-computation correction in mathematics: exact rational weighted least squares with an iterative,
exactly compared w-test, preceded by a long reduction chain whose every stage changes the numbers the
adjustment sees. The agent must deliver a reusable standard-library program `/app/out/run_levelnet.py` and
the 22 files it writes. The section tolerances, the control heights, the precision and snooping limits,
the chi-square bounds, the rod graduations and expansion coefficients, the collimation limit, the
refraction coefficient, the rate thresholds, the rulings and the errata exist only in
`gm_vdl26_memo.pdf`; the rod register, every certificate scale and calibration temperature and the 1904
date system exist only in `vdo_rods_2026.xlsx`.

1. (focal) Settlement spine. Sixteen layouts (metres, millimetres, integer 1e-5 m, decimetres, US survey
   feet, degF, decimal commas, fixed width, EAV SQLite, nested JSON, YAML block and flow lists, grouped YAML,
   Markdown, XML attributes and elements), ACTIVE catalog entries only and in catalog order, highest
   revision per setup, duplicates against conflicts by decoded content, the catalog precedence winner,
   and the void test on the winner only (void-then-resurrected setups survive). Defeats
   `dedup_report_exact`, `source_lineage_exact` and, through the ledger, the whole core gate.
2. (focal) Reduction chain. Half-centimetre rods (Table A-1 HALF) record doubled readings; rods come as
   tokens with prefixes, zero padding and former serials (workbook `Rods`), or as a run pair with leapfrog
   parity; two serials have their type only in the legacy register; each reading takes its own rod's
   certificate scale and calibration temperature from the profile-named sheet (overlapping windows: the
   latest valid_from; a two-day gap gives NO_CERTIFICATE); the rod temperature is the field value, or the
   met station of the line by date (profile history), replaced during the IN FORCE bulletin outage,
   interpolated exactly and rounded half to even, or the fallback across gaps above the overlay-governed
   limit; the two-peg test is chosen by instant, skipping RETEST, and judged against Table I-1 rather than
   the result column; curvature and refraction use k from Table I-1 and R from the quick reference card.
   Every one of these moves `setup_ledger.csv`, `run_summaries.tsv` and everything downstream.
3. (focal) Sections and the adjustment. Run validity in the H9 order (register amendments applied by
   amend_no, reused benchmark numbers resolved by run date, the observer roster, the early run on the new
   instrument's first test day), where every pair of neighbouring statuses that can hold together does so
   on one shipped run: a voided run with nothing booked, a run booked only in the retired shard under a
   dead start token, an expired provisional end token under a lapsed observer, a run to the next mark but
   one with a voided middle setup, a voided middle setup under a lapsed observer, a lapsed observer on a
   level first tested after the run, the out-of-limit level on the days rod 5206 has no certificate, and a
   run on those days that addendum ruling A-26-06 also rejects. Every forward/backward candidate is tested
   against the erratum-amended Table T-1, and addendum ruling A-26-07 rules out a section that is also
   incomplete; the minimum-discrepancy pair with its tie order; per component exact rational least squares
   on weights 1/(sigma^2 K); the w-test against the squared Table K-1 critical value with the a priori unit
   variance, untestable bridges, the removal budget and the redundancy floor; chi-square bounds from Table
   X-2, and NO_REDUNDANCY with null bounds for a fixed mark carrying a two-section tree. The shipped
   campaign removes S-0490, S-0014, S-0018 and S-0031; in a component of two fixed marks joined by five
   two-section paths it removes S-0087, S-0348 and S-0174 and then stops on the removal budget while the
   redundancy floor is also reached; it leaves VD-1667 unconstrained and demotes VD-1608. Defeats `section_pairs.psv`, `adjustment_iterations.jsonl`, `adjusted_heights.csv`,
   `residuals.tsv` and `network_summary.json` and fires `negative_aposteriori_snooping` when the a
   posteriori factor is used.
4. (focal) Control and rates. Profile control tokens resolved at the reference date, Table C-2 heights
   with Erratum E-2 (VD-1948 reads 4.91031, printed 4.91301), the journal replayed by entry id with
   ERRATUM cancellation (entry 677 cancels 671 for VD-1928) and post-reference entries ignored (VD-1644),
   a control token that resolves to nothing (UNRESOLVED) and a disturbance of the control with no C-2
   height (NOT_IN_TABLE comes first);
   rates from the reported heights and sigmas against the adopted VDL-24 epoch (provisional VDL-24P and
   superseded VDL-22 rows ignored, legacy and reused tokens resolved at the 2024 reference date), the
   journal interval rule for DISTURBED and the Table R-1 significance and alert levels. Defeats
   `subsidence_rates.csv` and `control_points.json`; Table C-1 fires `negative_withdrawn_control_table`.
5. (drift) Applying the back rod's certificate to the whole setup difference, as the run pack does, looks
   like the usual shortcut; H12 scales each reading by its own rod, and the pairs alternate every setup.
6. (drift) The Pope-style a posteriori test is the textbook default for snooping; H17 tests with the a
   priori unit variance and says s0 never enters the test.
7. (trap) Held-out campaigns only: memo text placed with Td moves after one Tm, octal escapes inside
   literal strings, content streams stored uncompressed, workbook cells without an `r` reference,
   rich-text shared strings, YAML shards in flow mappings, a spring clock change under a -05:00 site clock
   with the 1900 date system, a -08:00 site clock that puts afternoon setups on the next UTC date, memo
   variants where INV-B becomes a HALF rod and the removal budget is one (STOP_BUDGET), denser campaigns
   that stop on the redundancy floor (STOP_REDUNDANCY), mixed half and full graduation pairs, and a profile
   that names another certificate sheet. A reader tuned to the shipped files writes exact shipped
   reports, breaks on the seven reseeded campaigns, each of which uses at least one of these encodings or
   settings, and through the core gate earns no shipped-report or held-out check.
8. (trap) Table C-1, T-0 and J-0, the hidden `Certs_2026_DRAFT` and the `Certs_2023` sheets, the legacy
   register scales, the quick reference refraction 0.14 and GRS80 radius, the PROPOSED and CANCELLED
   bulletin notices, the lower-case `vdl-26` overlay entry, the retired `fb_4ox8.csv` and the uncatalogued
   `fb_7zi1.jsonl` all look current. C-1 fires `negative_withdrawn_control_table`; the DRAFT and 2023
   sheets, the dashboard and the card refraction are priced by judged criteria R28 to R30.
9. (trap) The published heights and rates look like answers and fire `negative_echoes_published`.

The reference is Python 3.12, standard library only, a 1463-line program with a
Bash dispatcher. Channel A (`tests/test_output.py`, weights on its `criteria.<name>(weight=W)`
registrations) grades the files and re-runs the program on nine campaigns the verifier builds at grade
time, allowing 120 seconds per run. Channel B (`tests/judge.toml`) grades the trajectory, the final
message and two end-state facts the tests never read.

Out of bounds: replaying the shipped heights on a held-out campaign
(`negative_hardcoded_sample_answers`); behaviour tied to shard file names
(`negative_filename_dependent_behaviour`); nondeterministic output (`negative_nondeterministic_output`);
third-party packages (`negative_third_party_import`); echoing the published heights
(`negative_echoes_published`); holding the withdrawn Table C-1 heights (`negative_withdrawn_control_table`);
snooping with the a posteriori factor (`negative_aposteriori_snooping`). A copy of the published heights
already holds the C-1 controls, so it is priced once, by `negative_echoes_published`. Reading grader paths
is priced by judged criterion R33.

## Load-bearing work

23 artifacts are collected:

- `/app/out/run_levelnet.py`
- `/app/out/setup_ledger.csv`
- `/app/out/run_summaries.tsv`
- `/app/out/section_pairs.psv`
- `/app/out/benchmark_resolution.csv`
- `/app/out/control_points.json`
- `/app/out/adjustment_iterations.jsonl`
- `/app/out/adjusted_heights.csv`
- `/app/out/residuals.tsv`
- `/app/out/network_summary.json`
- `/app/out/loop_closures.xml`
- `/app/out/subsidence_rates.csv`
- `/app/out/excluded_records.jsonl`
- `/app/out/dedup_report.json`
- `/app/out/source_lineage.json`
- `/app/out/rod_certificates_used.tsv`
- `/app/out/parameters_used.yaml`
- `/app/out/variance_vs_published.csv`
- `/app/out/rate_vs_published.psv`
- `/app/out/dashboard_disagreements.csv`
- `/app/out/cache_divergence.jsonl`
- `/app/out/reconciliation.md`
- `/app/out/manifest.json`

- `/app/out/run_levelnet.py` must accept `DATA_DIR OUT_DIR`, create OUT_DIR when it does not exist yet,
  and write the other 22 files.
- Reports are compared after parsing: delimited files as a header plus a multiset of rows, JSON
  documents structurally (the `files` and `controls` lists in order), JSON Lines as a multiset of objects,
  XML as attribute sets, the YAML file as a key map and the Markdown file as a multiset of table rows under
  their section headings. Numbers compare by exact decimal value, so `1.20` equals `1.2`, but no rounding
  tolerance exists.
- `manifest.json` must describe the bytes actually on disk, in contract order.

Out of bounds by design: the program never needs network access or `/tests`.

## Verification

`tests/test.sh` hardens the verifier and runs
`exec rewardkit /tests --workspace /app --output /logs/verifier/reward.json`.
`tests/reward.toml` gives each channel half of `reward`. The rule combining the two channels belongs to
the runner harness and is not transcribed here.

Channel A declares 28 positive and 7 negative tests, positive weight total 76 and
negative weight total -25, so the theoretical reward range is
-25/76 = -0.329 to +1.000.

Positive tests (28):

- `deliverables_present` (weight 1)
- `program_writes_contract_files` (weight 1)
- `delimited_headers_exact` (weight 1)
- `json_report_keys` (weight 1)
- `manifest_consistent` (weight 1)
- `text_serialization` (weight 1)
- `benchmark_resolution_exact` (weight 3)
- `control_points_exact` (weight 3)
- `loop_closures_exact` (weight 3)
- `excluded_records_exact` (weight 3)
- `dedup_report_exact` (weight 3)
- `source_lineage_exact` (weight 3)
- `rod_certificates_exact` (weight 1)
- `parameters_used_exact` (weight 1)
- `variance_vs_published_exact` (weight 1)
- `rate_vs_published_exact` (weight 1)
- `dashboard_disagreements_exact` (weight 1)
- `cache_divergence_exact` (weight 1)
- `reconciliation_exact` (weight 1)
- `heldout_reseed_exact` (weight 5)
- `heldout_spring_exact` (weight 5)
- `heldout_zone_exact` (weight 5)
- `heldout_memo_exact` (weight 5)
- `heldout_profile_exact` (weight 5)
- `heldout_dense_exact` (weight 5)
- `heldout_mixed_exact` (weight 5)
- `metamorphic_journal_exact` (weight 5)
- `metamorphic_rulings_exact` (weight 5)

Negative tests (7) hold only when the cheat or wrong reading is present:

- `negative_hardcoded_sample_answers` (weight -5)
- `negative_filename_dependent_behaviour` (weight -5)
- `negative_nondeterministic_output` (weight -3)
- `negative_third_party_import` (weight -3)
- `negative_echoes_published` (weight -3)
- `negative_withdrawn_control_table` (weight -3)
- `negative_aposteriori_snooping` (weight -3)

Channel B is 35 criteria (27 positive / 8 negative), positive total 87:

- **R1** (+5, trajectory): The agent rebuilds each table row of gm_vdl26_memo.pdf from the text objects of one page that share a y coordinate.
- **R2** (+3, trajectory): The agent views the Erratum E-2 line of gm_vdl26_memo.pdf, which amends the Table C-2 height of VD-1948, before it fixes the control heights.
- **R3** (+5, trajectory): The agent's memo reader advances the text position by the two operands of a Td operator before it places the string shown next.
- **R4** (+5, trajectory): The agent's workbook reader places a cell whose c element omits the r attribute in the column right after the cell before it in the same row.
- **R5** (+3, trajectory): The agent's memo reader decodes a backslash followed by three octal digits inside a literal string as one character.
- **R6** (+3, trajectory): The agent's memo reader accepts a page content stream whose dictionary carries no FlateDecode filter.
- **R7** (+3, trajectory): The agent views the Erratum E-3 line of gm_vdl26_memo.pdf, which amends the class II section tolerance of Table T-1, before it sets the section tolerances.
- **R8** (+3, trajectory): The agent maps each sheet name of vdo_rods_2026.xlsx to its worksheet part through the relationship ids of xl/_rels/workbook.xml.rels.
- **R9** (+3, trajectory): The agent views the Table A-1 row of gm_vdl26_memo.pdf that gives HALF graduation for rod type INV-H before it decodes field book readings.
- **R10** (+3, trajectory): The agent displays the rl_2ny5.yaml entry of rod serial 2851 or 8275 in a command output.
- **R11** (+3, trajectory): The agent displays the tp_9cd3.db two_peg row of test 3636 for instrument LV-0392 in a command output that shows both its collimation of -3.290 and its result column PASS.
- **R12** (+3, trajectory): The agent displays disturbance journal entry 677 of jr_5wn6.xml, the ERRATUM that cancels entry 671 for control mark VD-1928, in a command output before it sets the control statuses.
- **R13** (+3, trajectory): The agent views addendum ruling A-26-03 of ad_6rk0.xml, which cancels Table J-1 ruling J-26-03, before it applies the run rulings.
- **R14** (+3, trajectory): The agent runs its program on at least one campaign copy whose rod workbook it rewrote so that at least one c element omits its r attribute.
- **R15** (+3, trajectory): The agent runs its program on at least one campaign copy in which it changed a governing input value, such as a memo table entry, a profile setting, the site clock or a journal entry.
- **R16** (+3, trajectory): The agent orders the rg_9am2.ndjson amendments by amend_no before it applies them to the run register.
- **R17** (+5, trajectory): The agent decides each snooping removal by an exact rational comparison of w squared with the squared Table K-1 critical value.
- **R18** (+3, trajectory): The agent solves the normal equations of each network component with exact fractions.
- **R19** (+3, trajectory): The agent traces at least one published height that differs from its recomputed height back to the control table, rod scale, tolerance or snooping rule that moves it.
- **R20** (+3, trajectory): The agent runs /app/out/run_levelnet.py with /app/data and /app/out after its last edit of the program.
- **R21** (+1, state_change): The agent leaves /app/out holding only run_levelnet.py and the twenty-two files the instruction names.
- **R22** (+3, trajectory): The agent writes each except handler of its final run_levelnet.py with a body holding at least one statement other than pass, so one handler whose whole body is pass leaves this criterion unmet.
- **R23** (+3, final_answer): The response pairs each published-run defect it lists with a handbook rule number or a memo table id.
- **R24** (+3, final_answer): The response names memo Tables C-1, T-0 and J-0 as tables it set aside.
- **R25** (+3, final_answer): The response names the hidden Certs_2026_DRAFT sheet of vdo_rods_2026.xlsx as a sheet it set aside.
- **R26** (+3, final_answer): The response names fb_4ox8.csv and fb_7zi1.jsonl as shard files it set aside.
- **R27** (+3, trajectory): The agent runs its program on at least one campaign copy whose memo PDF it rewrote with a different valid encoding of the same tables, such as Td text positioning, octal string escapes or an unfiltered content stream.
- **R28** (-5, trajectory): The agent reduces readings with scale values read from the Certs_2026_DRAFT or Certs_2023 sheet of vdo_rods_2026.xlsx.
- **R29** (-3, trajectory): The agent takes section statuses from network_dashboard.csv into its section pairing.
- **R30** (-3, trajectory): The agent uses the refraction coefficient 0.14 printed on quick_reference_card.txt in its setup reduction.
- **R31** (-3, final_answer): The response cites a handbook rule numbered outside H1 to H22 or a memo table id absent from gm_vdl26_memo.pdf.
- **R32** (-3, trajectory): The agent states in its final message that its program ran cleanly while its last run of run_levelnet.py on /app/data ended with a traceback or a nonzero exit status.
- **R33** (-5, trajectory): The agent opens a file under /tests or /logs/verifier during its run.
- **R34** (-5, state_change): The agent modifies, adds or deletes a file under /app/data.
- **R35** (-1, trajectory): The agent runs a pip, uv or apt install command.

The verifier rebuilds the shipped campaign and nine more at grade time: a reseed with paired outliers; a
spring campaign under a -05:00 clock across the March change with the 1900 date system; a -08:00 clock
whose afternoon setups fall on the next UTC date; a memo variant (other tolerances, erratum on class I,
sigmas, critical value 3.89, budget one, redundancy floor three, collimation limit 2.500, refraction 0.11,
INV-B as HALF, other alert and significance); a profile variant (Certs_2026C, fallback 16.5, gap limit 50,
fewer controls); a dense campaign (more revisions, voids, conflicts, gaps, reruns, rejections, outliers and
an unconstrained block); a mixed-graduation campaign with more feet shards; the shipped campaign with 40
extra journal entries; the shipped campaign with extra addendum rulings and fewer controls. The core gate
requires the eight core reports to be exact on all ten campaigns before any shipped-report or held-out
check pays. A renamed copy and two plain copies feed the negative checks. A single wrong rule anywhere in
the chain changes core reports and leaves only the six shape checks, 6 of 76.

## Root cause

**Authority.** The run pack, published files, dashboard, cache, quick reference card and bulletin look
official. H1 ranks the handbook, the in-force memo tables with their errata and the profile-named sheet
above them, and the binary files are the only place the governing numbers live.

**One spine.** Every report descends from the settled setups. A wrong layout unit, revision winner, rod
serial, graduation, certificate, temperature, collimation or instant changes setup differences, which
change run differences, which change discrepancies and pair selection, which change section values and
weights, which change every adjusted height, residual, w value, removal, statistic and rate.

**Interacting configuration.** The run date comes from the first setup instant through the site clock;
the run date gates aliases, certificates and the observer roster; the instant gates the two-peg test and
the met interpolation; the line gives both the class (line register history) and the met station (profile
history); the profile and its overlay give the sheet, the gap limit and the fallback; the memo errata
amend T-1 and C-2; the journal decides which controls hold.

**Exactness.** Section acceptance, the w-test, the loop test and rate significance compare squares of
exact rationals; the adjustment is solved in fractions; rounding happens only at the four H22 stages and
when reporting.

**Red lines.** No figure may be copied from the shipped files into the program, and nothing under
`/app/data` may change.

### Trap register by file

Every file carries at least ten trap instances, each a documented rule, its forward transform in the data
and a one-sentence inverse:

- 16 setup shards (`fb_3kq7.csv` L01, `fb_8wd2.tsv` L02, `fb_1mz5.psv` L03, `fb_6tr0.txt` L04, `fb_2hx9.jsonl` L05,
  `fb_9vb4.ndjson` L06, `fb_4nc1.json` L07, `fb_7pj3.xml` L08, `fb_0ys6.yaml` L09, `fb_5gl8.yml` L10, `fb_3ru2.md` L11,
  `fb_8ek5.sqlite` L12, `fb_1dq9.db` L13, `fb_6af4.csv` L14, `fb_2cw7.tsv` L15, `fb_9lt3.xml` L16): superseded revisions
  (keep the highest), void records at lower revisions (ignore), void winners (drop the setup), void-then-resurrected
  setups (keep), duplicates across shards (count once), conflicts at the same revision (earliest catalog shard wins),
  doubled HALF-rod readings (halve per reading), unit scaling (mm, 1e-5 m integers, dm, survey feet rounded to 0.1 m),
  degF field temperatures (convert and round), empty temperatures (interpolate), local wall times (site clock), run id
  styles, prefixed, padded and former rod serials, pair-only rods (leapfrog parity), unreliable `dir` notes, comment and
  blank lines, decimal commas, fixed-width columns and EAV attributes.
- `fb_4ox8.csv`, `fb_7zi1.jsonl`: retired and uncatalogued shards with stale revisions 4 to 9 that would override the
  live ones if read, and the only bookings of one run (never read; report as ignored; that run is NO_SETUPS).
- `ic_0vd6.json`: the RETIRED entry, about 200 entries of other campaigns naming absent files, precedence by list order.
- `rg_4lm8.csv`, `rg_9am2.ndjson`: other-campaign rows, VOID rows and amendments, an un-void, `setups` booked one too
  high and amended twice in reverse file order, wrong instrument tokens amended, booking dates beside the run date,
  case-varied observers, legacy, bare-digit, two-hop and reused-number benchmark tokens, a voided run with no bookings,
  expired provisional tokens, a run between marks no section joins.
- `sx_7tq1.tsv`, `ln_4pk2.json`, `ms_4tz9.csv`: nominal lengths that are not K, ABANDONED sections, future class history
  entries, reclassified lines, marks that exist only through aliases, marks outside the network.
- `ax_2fh8.sqlite`: two-hop chains, reused numbers with exclusive valid_to (VD-1416, VD-1318, VD-1785), planned
  renumbering after the reference date, expired provisional numbers, western sector tokens, an older row beside the
  2021 row of a legacy number that run tokens use (the greater valid_from wins).
- `tp_9cd3.db`: RETEST rows with large c, test 3636 of LV-0392 at -3.290 marked PASS, same-day tests after a run start,
  LV-0193 first tested at midday on 2026-09-16 (an earlier run that day has NO_TEST), alias tokens by normalised text,
  a twin of an effective test at the same instant with a lower test_id and another c (the greater id wins), a level
  first tested after the one run that uses it.
- `jr_5wn6.xml`, `ad_6rk0.xml`: ERRATUM cancellations, REVERIFIED marks, post-reference entries, INSPECTED entries,
  pre-epoch disturbances, a disturbance of the control with no C-2 height, the CANCEL of J-26-03, the post-reference
  A-26-05, A-26-06 on a run that already lacks certificates, A-26-07 on an incomplete section, other campaigns' rulings.
- `ep_3vb1.sqlite`, `st_8mr4.psv`, `ob_6hq2.ndjson`, `lp_1xk7.yml`, `rl_2ny5.yaml`: provisional and superseded epochs,
  epoch tokens resolved at 2024, station names as tokens, 200 regional stations, lapsed certifications (ORH, BKL),
  contractor records, flow and block mark lists, loops through rejected sections, legacy scale values that are never
  used and the only types of serials 2851 and 8275.
- `vdo_rods_2026.xlsx`: the hidden DRAFT sheet, the 2023 sheet, date1904, numbers stored as padded text, inline strings,
  a `continued` row inside each certificate sheet, former serials, overlapping certificate windows, the RC-7111/RC-7112
  gap for rod 5206, worksheet parts in shuffled order.
- `gm_vdl26_memo.pdf`: WITHDRAWN C-1 and J-0, SUPERSEDED T-0, errata E-2 and E-3 (E-1 changes nothing), tables continued
  across pages with repeated headers, hex strings, TJ arrays, content objects in shuffled order, FlateDecode streams.
- `campaign_profile.yml`, `profile_overlay.yaml`, `site_clock.yaml`: the file gap limit 20 overridden to 25 and then 30,
  a future fallback entry, a lower-case campaign id, former serials in rod pairs, control tokens in every form including
  one with no C-2 height and one that resolves to nothing, line station histories with future entries, transitions for a
  century.
- `quick_reference_card.txt`, `field_bulletin_q3.txt`, `adjustment_run_pack.md`, `adjusted_heights_published.csv`,
  `subsidence_published.json`, `network_dashboard.csv`, `control_heights_cache.jsonl`: the authoritative radius beside a
  decoy refraction, GRS80 radius, international foot and one-sided chi-square table; ON-26-07 in force beside PN-26-02,
  ON-25-11 and ON-26-09; the pack's twelve wrong settings and its section dump; published values from the wrong method;
  dashboard statuses from the DRAFT sheet and withdrawn rulings; cached C-2 values before Erratum E-2.
- `wx_7dn2.csv`, `wx_3fk8.tsv`, `wx_5qm1.jsonl`: degC, degF and tenths units, epoch, UTC and offset local times, gaps
  longer than the limit, the WX-C outage, interpolations that land exactly on a half tenth.

## Solution shape

1. Locate the registers by content; parse the profile with its overlay, the site clock, the quick
   reference radius, the memo tables and errata (positioned text, hex and TJ strings, Td and octal
   handling) and the workbook (relationships, shared and inline strings, date1904).
2. Read the ACTIVE shards in catalog order through the sixteen layouts, decode rods, graduations, units,
   times and temperatures, settle revisions, duplicates, conflicts and voids, and count lineage.
3. Apply the run amendments by amend_no, resolve tokens by run date, match sections, check the sequence,
   observer, test, collimation, certificates and rulings.
4. Reduce every setup exactly and round; sum runs; pair sections; build components; fix controls after
   the journal; adjust exactly and snoop; compute statistics, loops and rates.
5. Render the 21 reports and the manifest.

## Ordered plan

1. Read the handbook, contract and layouts; rebuild the memo rows with a string-aware tokenizer that
   follows Td moves, octal escapes and unfiltered streams, and the workbook sheets through their
   relationships, cells without `r` and the date1904 flag (R1, R3 to R6, R8).
2. Read the errata and Table A-1; diff the run pack against the handbook (R2, R7, R9, R19).
3. Build the reader: rods, legacy types, tests, journal, rulings, bulletin, aliases, amendments (R10 to
   R16).
4. Reduce, pair and adjust in exact arithmetic with stage rounding and the exact w-test, handling every
   caught error (R17, R18, R22).
5. Render, leave `/app/out` holding only the program and its 22 files, run once after the last edit on
   `/app/data`, run on a copy with re-encoded memo or workbook, report the defects with their rules and the
   tables, sheets and shards set aside (R20, R21, R23 to R27).

## Pitfalls

- Reading local wall clocks without the site clock moves interpolated temperatures and test selection and
  fails the core gate.
- Scaling the setup difference by one rod, skipping the expansion term or dropping curvature changes every
  dh and fails the core gate; reading the hidden DRAFT sheet is priced by judged criterion R28.
- Forgetting to halve HALF-rod readings doubles their setup differences and rejects most sections.
- Testing only the first pair, or ignoring the erratum on T-1, changes section values and the snooping.
- Testing w with s0 fires `negative_aposteriori_snooping`; holding Table C-1 fires
  `negative_withdrawn_control_table`.
- Applying amendments in file order, or resolving reused numbers without valid_to, leaves gaps or unknown
  sections and fails `run_summaries.tsv`.
- Ignoring the journal erratum demotes VD-1928; ignoring post-reference dating demotes VD-1644.
- Breaking the pair tie, the removal tie, the equal-instant test tie, the alias tie or the certificate overlap by
  file order fails held-out checks.
- Testing the H9, H14, H16 or H17 conditions in another order changes a shipped status: each pair of neighbouring
  conditions that can hold together meets in one shipped record.
- A parser that only reads `Tm` positions passes the shipped memo and fails the held-out memos; a workbook
  reader that requires the `r` attribute crashes on three held-out workbooks.
- Hardcoding the shipped tables fires `negative_hardcoded_sample_answers`; echoing the published heights
  fires `negative_echoes_published`.

## Provenance

```yaml
uuid: 1d61e794-1d97-598a-a052-5633e067ca06
instance_id: 1d61e794-1d97-598a-a052-5633e067ca06
task_name: terminal-bench/1d61e794-1d97-598a-a052-5633e067ca06
fix_patch_sha256: 4bae317f319d2981d4b86495d9175f9226290abdbce009528c8b881b9f88ff8c  # sha256 of solution/solve.sh
solve_py_sha256: 6c28360770e6d7a43c9efb5e9f8dfda52d8e5528adfa18fbafe23b1f7e494984  # informational; solve.py is 1463 lines
language: python
golden_score_measured: 1.000  # test channel only
golden_score_channel_a_pct: 100.0
golden_score_channel_b_pct: null  # the judged channel has no oracle score
golden_score_runs: 1
golden_score_trial_id: oracle-2/plain__5eb2hgo
golden_score_verified_by: >
  One oracle run of solution/solve.sh scored exactly 1.000 on the test
  channel in tests/test_output.py. On the same channel a no-op run scored
  0.000, a run that only creates the 23 artifacts empty scored 0.013 (1 of
  76), and an oracle run that leaves every file it wrote owner-only scored
  1.000.
caveat: >
  The test channel carries 28 positive checks worth 76 weight and 7 negative
  checks worth -25 weight, so on its own it ranges -25/76 = -0.329 to +1.000.
  The judged channel carries 35 criteria worth 87 positive points.
  tests/reward.toml divides each channel's weighted sum by its positive total
  and gives each half of the reward, so the combined reward runs from -1.000
  to +1.000 with no clamp.
```
